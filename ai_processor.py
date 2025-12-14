"""
AI Processor - Handles OpenAI API calls for document data extraction.
"""

import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

from config import (
    OPENAI_API_KEY, 
    OPENAI_MODEL, 
    CORE_QUESTIONS,
    get_questions_for_document_type,
    get_field_names_for_questions,
    QUESTION_TO_FIELD
)


def get_client() -> OpenAI:
    """Get configured OpenAI client."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set. Please add it to your .env file.")
    return OpenAI(api_key=OPENAI_API_KEY)


# Pydantic models for structured output
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


def detect_document_type(text_content: str, reference_images: list[dict] = None) -> tuple[str, str]:
    """
    First pass: Quickly detect document type.
    
    Args:
        text_content: Document text content
        reference_images: Optional page images
        
    Returns:
        Tuple of (document_type, confidence_level)
    """
    client = get_client()
    
    # Build message content
    content = []
    
    # Use first 5000 chars for type detection (faster and cheaper)
    intro = "Please identify the type of this document.\n\n"
    intro += "DOCUMENT EXCERPT:\n"
    intro += "=" * 50 + "\n"
    intro += text_content[:5000]
    intro += "\n" + "=" * 50
    
    content.append({"type": "text", "text": intro})
    
    # Add first image if available
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
            {
                "role": "system", 
                "content": """You are a document classification expert specializing in insurance and reinsurance documents.
                
Classify the document into one of these types:
- Reinsurance Contract (includes Quota Share, Excess of Loss, Treaty agreements)
- MGA Agreement (Managing General Agent agreements)
- Broker Agreement
- Insurance Policy
- Other (specify)

Provide your confidence level based on clear indicators in the document."""
            },
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


def extract_from_pdf_hybrid(text_content: str, reference_images: list[dict] = None) -> tuple[dict, dict]:
    """
    Extract data using two-pass hybrid approach:
    1. Detect document type
    2. Extract relevant fields based on type
    
    This is more efficient and accurate for large PDFs.
    
    Args:
        text_content: Full extracted text from the PDF
        reference_images: Optional list of page images for visual reference
        
    Returns:
        Tuple of (results_dict, sources_dict) where:
        - results_dict: Dictionary with field names as keys and extracted values
        - sources_dict: Dictionary with field names as keys and source locations for logging
    """
    print("  Pass 1: Detecting document type...")
    doc_type, confidence = detect_document_type(text_content, reference_images)
    print(f"    → Detected: {doc_type} (confidence: {confidence})")
    
    print("  Pass 2: Extracting relevant fields...")
    questions = get_questions_for_document_type(doc_type)
    print(f"    → Asking {len(questions)} targeted questions")
    
    client = get_client()
    
    # Build the message content
    content = []
    
    # Add the text content
    intro = f"This document has been identified as: {doc_type}\n\n"
    intro += "Please analyze the following document and extract the requested information.\n\n"
    intro += "FULL DOCUMENT TEXT:\n"
    intro += "=" * 50 + "\n"
    intro += text_content
    intro += "\n" + "=" * 50
    
    if reference_images:
        intro += f"\n\nBelow are {len(reference_images)} page image(s) for visual reference (to help with tables, formatting, etc.):"
    
    content.append({"type": "text", "text": intro})
    
    # Add reference images if provided
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
            {"role": "system", "content": build_extraction_prompt(questions)},
            {"role": "user", "content": content}
        ],
        max_tokens=4000,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    # Parse the JSON response
    response_text = response.choices[0].message.content.strip()
    
    # Handle potential markdown code blocks in response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])
    
    parsed_response = json.loads(response_text)
    
    # Handle both old format (flat) and new format (answers/sources)
    if "answers" in parsed_response:
        raw_answers = parsed_response.get("answers", {})
        raw_sources = parsed_response.get("sources", {})
    else:
        # Fallback for old format
        raw_answers = parsed_response
        raw_sources = {}
    
    # Convert question numbers to field names
    field_names = get_field_names_for_questions(questions)
    formatted_results = {}
    formatted_sources = {}
    
    for i, field_name in enumerate(field_names, 1):
        key = str(i)
        value = raw_answers.get(key, "Not found")
        formatted_results[field_name] = value if value else "Not found"
        
        source = raw_sources.get(key, "N/A")
        formatted_sources[field_name] = source if source else "N/A"
    
    # Add metadata fields
    formatted_results["Type"] = doc_type
    formatted_sources["Type"] = "Document classification"
    
    return formatted_results, formatted_sources


def extract_from_excel_content(content: str) -> tuple[dict, dict]:
    """
    Extract data from Excel content using two-pass approach.
    
    Args:
        content: Formatted string representation of Excel content
        
    Returns:
        Tuple of (results_dict, sources_dict) where:
        - results_dict: Dictionary with field names as keys and extracted values
        - sources_dict: Dictionary with field names as keys and source locations for logging
    """
    # Detect document type from Excel content
    print("  Pass 1: Detecting document type...")
    doc_type, confidence = detect_document_type(content, None)
    print(f"    → Detected: {doc_type} (confidence: {confidence})")
    
    print("  Pass 2: Extracting relevant fields...")
    questions = get_questions_for_document_type(doc_type)
    print(f"    → Asking {len(questions)} targeted questions")
    
    client = get_client()
    
    intro = f"This document has been identified as: {doc_type}\n\n"
    intro += f"Please analyze the following spreadsheet content and extract the requested information:\n\n{content}"
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": build_extraction_prompt(questions)},
            {"role": "user", "content": intro}
        ],
        max_tokens=4000,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    # Parse the JSON response
    response_text = response.choices[0].message.content.strip()
    
    # Handle potential markdown code blocks in response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])
    
    parsed_response = json.loads(response_text)
    
    # Handle both old format (flat) and new format (answers/sources)
    if "answers" in parsed_response:
        raw_answers = parsed_response.get("answers", {})
        raw_sources = parsed_response.get("sources", {})
    else:
        # Fallback for old format
        raw_answers = parsed_response
        raw_sources = {}
    
    # Convert question numbers to field names
    field_names = get_field_names_for_questions(questions)
    formatted_results = {}
    formatted_sources = {}
    
    for i, field_name in enumerate(field_names, 1):
        key = str(i)
        value = raw_answers.get(key, "Not found")
        formatted_results[field_name] = value if value else "Not found"
        
        source = raw_sources.get(key, "N/A")
        formatted_sources[field_name] = source if source else "N/A"
    
    # Add metadata fields
    formatted_results["Type"] = doc_type
    formatted_sources["Type"] = "Document classification"
    
    return formatted_results, formatted_sources


def format_extraction_results(raw_results: dict) -> dict:
    """
    Pass-through function for backward compatibility.
    The new extract functions return already-formatted results.
    
    Args:
        raw_results: Dict with field names as keys
        
    Returns:
        Same dict (already formatted)
    """
    return raw_results


