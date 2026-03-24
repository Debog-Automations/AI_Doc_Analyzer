"""
AI Processor - Handles API calls (OpenAI or Anthropic) for document data extraction.
"""

import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    AI_PROVIDER,
    CORE_QUESTIONS,
    get_questions_for_document_type,
    get_field_names_for_questions,
    QUESTION_TO_FIELD
)


def get_client(provider: str = None, api_key: str = None):
    """Get configured AI client for the given provider."""
    provider = provider or AI_PROVIDER
    if provider == "anthropic":
        import anthropic
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set. Please add it to your .env file or Settings.")
        return anthropic.Anthropic(api_key=key)
    else:
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY not set. Please add it to your .env file or Settings.")
        return OpenAI(api_key=key)


# Anthropic request size limits
# Anthropic has a 32MB HTTP body limit; base64 images are the main risk factor
ANTHROPIC_MAX_IMAGES = 5        # max images per request
ANTHROPIC_MAX_TEXT_CHARS = 80_000  # ~20K tokens of text; well within 200K context


def _convert_images_for_anthropic(reference_images: list[dict]) -> list[dict]:
    """Convert OpenAI-style image dicts to Anthropic content blocks.

    Silently caps at ANTHROPIC_MAX_IMAGES to avoid 413 errors.
    """
    blocks = []
    for img in reference_images[:ANTHROPIC_MAX_IMAGES]:
        media_type = img.get("mime_type", "image/jpeg")
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": img["base64_image"]
            }
        })
    return blocks


# Pydantic models for structured output (OpenAI only)
class DocumentTypeResponse(BaseModel):
    """Response model for document type detection."""
    document_type: str = Field(description="The type of document (e.g., 'Reinsurance Contract', 'MGA Agreement', 'Broker Agreement', etc.)")
    confidence: str = Field(description="Confidence level: 'high', 'medium', or 'low'")


class ExtractionResponse(BaseModel):
    """Response model for data extraction with validation."""
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping question numbers (as strings: '1', '2', '3', etc.) to extracted answers. Use 'Not found' for missing information."
    )


_CLASSIFICATION_SYSTEM = """You are a document classification expert specializing in insurance and reinsurance documents.

Classify the document into one of these types:
- Reinsurance Contract (includes Quota Share, Excess of Loss, Treaty agreements)
- MGA Agreement (Managing General Agent agreements)
- Broker Agreement
- Insurance Policy
- Other (specify)

Provide your confidence level based on clear indicators in the document."""


def detect_document_type(
    text_content: str,
    reference_images: list[dict] = None,
    provider: str = None,
    api_key: str = None
) -> tuple[str, str]:
    """
    First pass: Quickly detect document type.

    Args:
        text_content: Document text content
        reference_images: Optional page images
        provider: "openai" or "anthropic" (defaults to AI_PROVIDER config)
        api_key: API key override

    Returns:
        Tuple of (document_type, confidence_level)
    """
    provider = provider or AI_PROVIDER
    client = get_client(provider=provider, api_key=api_key)

    intro = "Please identify the type of this document.\n\n"
    intro += "DOCUMENT EXCERPT:\n"
    intro += "=" * 50 + "\n"
    intro += text_content[:5000]
    intro += "\n" + "=" * 50

    if provider == "anthropic":
        content = [{"type": "text", "text": intro}]
        if reference_images and len(reference_images) > 0:
            content.extend(_convert_images_for_anthropic(reference_images[:1]))

        anthropic_system = _CLASSIFICATION_SYSTEM + (
            "\n\nRespond with a JSON object only (no markdown), with exactly these keys: "
            '{"document_type": "...", "confidence": "high|medium|low"}'
        )

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=256,
            system=anthropic_system,
            messages=[{"role": "user", "content": content}]
        )
        response_text = response.content[0].text.strip()
        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        parsed = json.loads(response_text)
        return parsed.get("document_type", "Other"), parsed.get("confidence", "low")

    else:
        # OpenAI structured output path
        content = [{"type": "text", "text": intro}]
        if reference_images and len(reference_images) > 0:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{reference_images[0]['mime_type']};base64,{reference_images[0]['base64_image']}",
                    "detail": "low"
                }
            })

        response = client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFICATION_SYSTEM},
                {"role": "user", "content": content}
            ],
            response_format=DocumentTypeResponse,
            temperature=0.1
        )
        result = response.choices[0].message.parsed
        return result.document_type, result.confidence


def build_extraction_prompt(questions: list) -> str:
    """Build the system prompt for data extraction."""
    questions_text = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))

    return f"""You are a document data extraction assistant specializing in insurance and reinsurance documents. Your task is to extract specific information from the provided document with high accuracy.

For each question below, provide the most accurate answer based on the document content. Guidelines:

**For Dates:**
- Return dates in ISO format (YYYY-MM-DD) when possible
- Common phrases: "effective as of", "commence on", "take effect", "remain in effect until", "shall expire on", "termination date"
- If only year/month, use YYYY-MM or YYYY

**For Financial Amounts:**
- Include currency symbol or code
- Use numeric format with commas (e.g., $1,000,000 or USD 1,000,000)

**For Percentages:**
- Return as number with % symbol (e.g., 25%)

**For Lists (Parties, Tables, Sections):**
- Return as comma-separated list or numbered list
- Be comprehensive but concise

**If Information Not Found:**
- Return "Not found" as the value

Questions to answer:
{questions_text}

Respond with a JSON object with two keys:
- "answers": object where keys are question numbers (as strings: "1", "2", "3", etc.) and values are your answers or "Not found"
- "sources": object where keys are question numbers and values are brief descriptions of where you found the information (e.g., "Page 1, Section 2.1" or "Article III, paragraph 4" or a short quote from the document). Use "N/A" if not found."""


def _parse_extraction_response(response_text: str) -> dict:
    """Parse extraction JSON from response text, handling markdown fences."""
    response_text = response_text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])
    return json.loads(response_text)


def _map_extraction_results(raw_answers: dict, raw_sources: dict, questions: list) -> tuple[dict, dict]:
    """Convert numbered question answers to field-name-keyed dicts."""
    field_names = get_field_names_for_questions(questions)
    formatted_results = {}
    formatted_sources = {}
    for i, field_name in enumerate(field_names, 1):
        key = str(i)
        value = raw_answers.get(key, "Not found")
        formatted_results[field_name] = value if value else "Not found"
        source = raw_sources.get(key, "N/A")
        formatted_sources[field_name] = source if source else "N/A"
    return formatted_results, formatted_sources


def extract_from_pdf_hybrid(
    text_content: str,
    reference_images: list[dict] = None,
    provider: str = None,
    api_key: str = None
) -> tuple[dict, dict]:
    """
    Extract data using two-pass hybrid approach:
    1. Detect document type
    2. Extract relevant fields based on type

    Args:
        text_content: Full extracted text from the PDF
        reference_images: Optional list of page images for visual reference
        provider: "openai" or "anthropic" (defaults to AI_PROVIDER config)
        api_key: API key override

    Returns:
        Tuple of (results_dict, sources_dict)
    """
    provider = provider or AI_PROVIDER

    print("  Pass 1: Detecting document type...")
    doc_type, confidence = detect_document_type(text_content, reference_images, provider=provider, api_key=api_key)
    print(f"    → Detected: {doc_type} (confidence: {confidence})")

    print("  Pass 2: Extracting relevant fields...")
    questions = get_questions_for_document_type(doc_type)
    print(f"    → Asking {len(questions)} targeted questions")

    client = get_client(provider=provider, api_key=api_key)

    intro = f"This document has been identified as: {doc_type}\n\n"
    intro += "Please analyze the following document and extract the requested information.\n\n"
    intro += "FULL DOCUMENT TEXT:\n"
    intro += "=" * 50 + "\n"
    intro += text_content
    intro += "\n" + "=" * 50

    if reference_images:
        intro += f"\n\nBelow are {len(reference_images)} page image(s) for visual reference (to help with tables, formatting, etc.):"

    system_prompt = build_extraction_prompt(questions)

    if provider == "anthropic":
        # Truncate text to avoid 413 / token-limit errors
        truncated = text_content[:ANTHROPIC_MAX_TEXT_CHARS]
        if len(text_content) > ANTHROPIC_MAX_TEXT_CHARS:
            truncated += "\n\n[... document truncated for size ...]"
            print(f"    → Text truncated to {ANTHROPIC_MAX_TEXT_CHARS} chars for Anthropic")

        anthropic_intro = f"This document has been identified as: {doc_type}\n\n"
        anthropic_intro += "Please analyze the following document and extract the requested information.\n\n"
        anthropic_intro += "FULL DOCUMENT TEXT:\n"
        anthropic_intro += "=" * 50 + "\n"
        anthropic_intro += truncated
        anthropic_intro += "\n" + "=" * 50
        if reference_images:
            capped = min(len(reference_images), ANTHROPIC_MAX_IMAGES)
            anthropic_intro += f"\n\nBelow are {capped} page image(s) for visual reference:"

        content = [{"type": "text", "text": anthropic_intro}]
        if reference_images:
            content.extend(_convert_images_for_anthropic(reference_images))

        anthropic_system = system_prompt + "\n\nIMPORTANT: Respond with a JSON object only. Do not use markdown code fences."

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            system=anthropic_system,
            messages=[{"role": "user", "content": content}]
        )
        response_text = response.content[0].text

    else:
        content = [{"type": "text", "text": intro}]
        if reference_images:
            for img in reference_images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['mime_type']};base64,{img['base64_image']}",
                        "detail": "low"
                    }
                })

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=4000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content

    parsed_response = _parse_extraction_response(response_text)

    if "answers" in parsed_response:
        raw_answers = parsed_response.get("answers", {})
        raw_sources = parsed_response.get("sources", {})
    else:
        raw_answers = parsed_response
        raw_sources = {}

    formatted_results, formatted_sources = _map_extraction_results(raw_answers, raw_sources, questions)
    formatted_results["Type"] = doc_type
    formatted_sources["Type"] = "Document classification"

    return formatted_results, formatted_sources


def extract_from_excel_content(
    content: str,
    provider: str = None,
    api_key: str = None
) -> tuple[dict, dict]:
    """
    Extract data from Excel content using two-pass approach.

    Args:
        content: Formatted string representation of Excel content
        provider: "openai" or "anthropic" (defaults to AI_PROVIDER config)
        api_key: API key override

    Returns:
        Tuple of (results_dict, sources_dict)
    """
    provider = provider or AI_PROVIDER

    print("  Pass 1: Detecting document type...")
    doc_type, confidence = detect_document_type(content, None, provider=provider, api_key=api_key)
    print(f"    → Detected: {doc_type} (confidence: {confidence})")

    print("  Pass 2: Extracting relevant fields...")
    questions = get_questions_for_document_type(doc_type)
    print(f"    → Asking {len(questions)} targeted questions")

    client = get_client(provider=provider, api_key=api_key)

    intro = f"This document has been identified as: {doc_type}\n\n"
    intro += f"Please analyze the following spreadsheet content and extract the requested information:\n\n{content}"

    system_prompt = build_extraction_prompt(questions)

    if provider == "anthropic":
        # Truncate content to avoid 413 errors
        truncated_content = content[:ANTHROPIC_MAX_TEXT_CHARS]
        if len(content) > ANTHROPIC_MAX_TEXT_CHARS:
            truncated_content += "\n\n[... content truncated for size ...]"
            print(f"    → Excel content truncated to {ANTHROPIC_MAX_TEXT_CHARS} chars for Anthropic")

        anthropic_intro = f"This document has been identified as: {doc_type}\n\n"
        anthropic_intro += f"Please analyze the following spreadsheet content and extract the requested information:\n\n{truncated_content}"

        anthropic_system = system_prompt + "\n\nIMPORTANT: Respond with a JSON object only. Do not use markdown code fences."
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            system=anthropic_system,
            messages=[{"role": "user", "content": anthropic_intro}]
        )
        response_text = response.content[0].text

    else:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": intro}
            ],
            max_tokens=4000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content

    parsed_response = _parse_extraction_response(response_text)

    if "answers" in parsed_response:
        raw_answers = parsed_response.get("answers", {})
        raw_sources = parsed_response.get("sources", {})
    else:
        raw_answers = parsed_response
        raw_sources = {}

    formatted_results, formatted_sources = _map_extraction_results(raw_answers, raw_sources, questions)
    formatted_results["Type"] = doc_type
    formatted_sources["Type"] = "Document classification"

    return formatted_results, formatted_sources


def format_extraction_results(raw_results: dict) -> dict:
    """
    Pass-through function for backward compatibility.
    The new extract functions return already-formatted results.
    """
    return raw_results
