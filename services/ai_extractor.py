"""
AI Extractor - Universal AI extraction using OpenAI or Anthropic

Supports both:
- Legacy universal schema extraction
- Custom question-based extraction (dynamic prompts)
"""

import json
import os
from typing import Dict, List, Tuple, Optional, Any
from openai import OpenAI

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.universal_schema import (
    UniversalAIFields, 
    UNIVERSAL_EXTRACTION_PROMPT,
    validate_extraction
)
from services.validator import ExtractionValidator
from logger import get_logger

logger = get_logger(__name__)


def build_dynamic_prompt(questions: List[dict]) -> str:
    """
    Build a dynamic extraction prompt from a list of questions.
    
    Args:
        questions: List of dicts with 'question' and 'column_name' keys
        
    Returns:
        System prompt string for the AI
    """
    prompt = """You are a document data extraction assistant specializing in insurance and reinsurance documents.

You will be given a document and a list of questions to answer. Extract the requested information accurately.

**Important Guidelines:**
- For dates: Return in YYYY-MM-DD format when possible
- For financial amounts: Include currency symbol/code and commas (e.g., $1,000,000 or USD 1,000,000)
- For percentages: Return as number with % (e.g., 25%, 32.5%)
- For lists: Be comprehensive and include all relevant items
- If information is not found: Return an empty string "" - do NOT make up information
- If multiple values exist: Separate them with semicolons (;)

**Questions to Answer:**
"""
    
    # Build the JSON structure instruction
    json_structure = {}
    for i, q in enumerate(questions, 1):
        column_name = q.get("column_name", f"Field_{i}")
        question = q.get("question", "")
        prompt += f"\n{i}. {question}\n   → Store answer in field: \"{column_name}\"\n"
        json_structure[column_name] = f"<answer to question {i}>"
    
    prompt += f"""
**Response Format:**
Return your answers as a JSON object with exactly these fields:

```json
{json.dumps(json_structure, indent=2)}
```

Replace each placeholder with the actual extracted value, or an empty string if not found.
"""
    
    return prompt


class AIExtractor:
    """
    Universal AI extraction using OpenAI or Anthropic.

    Features:
    - Single prompt for all document types
    - Supports both universal schema and custom questions
    - Validates response and retries for missing fields
    - Supports PDF images for visual context
    """

    MAX_RETRIES = 2
    OPENAI_MODEL = "gpt-4o"
    ANTHROPIC_MODEL = "claude-sonnet-4-6"

    # Keep legacy MODEL attribute pointing at OpenAI default for backward compat
    MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        """
        Initialize AI extractor.

        Args:
            api_key: Primary API key. Used for whichever provider is selected.
            provider: "openai" or "anthropic". Defaults to AI_PROVIDER env var.
            anthropic_api_key: Explicit Anthropic key (alternative to passing via api_key).
        """
        self.provider = provider or os.getenv("AI_PROVIDER", "openai")

        if self.provider == "anthropic":
            import anthropic as _anthropic
            key = api_key or anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable.")
            self.client = _anthropic.Anthropic(api_key=key)
            self._model = self.ANTHROPIC_MODEL
        else:
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")
            self.client = OpenAI(api_key=key)
            self._model = self.OPENAI_MODEL

        self.validator = ExtractionValidator()
    
    def extract_with_questions(
        self,
        text_content: str,
        questions: List[dict],
        reference_images: List[dict] = None
    ) -> Tuple[dict, dict]:
        """
        Extract data from document using custom questions.
        
        Args:
            text_content: Document text content
            questions: List of dicts with 'question' and 'column_name' keys
            reference_images: Optional list of page images for visual reference
                            Each dict should have: base64_image, mime_type, page_number
                            
        Returns:
            Tuple of (extracted data dict, metadata dict)
        """
        if not questions:
            logger.warning("No questions provided for extraction")
            return {}, {"error": "No questions provided"}
        
        logger.info(f"Extracting with {len(questions)} custom questions...")
        
        # Build dynamic prompt
        system_prompt = build_dynamic_prompt(questions)
        
        # Make extraction call - returns result and conversation history for potential follow-up
        raw_result, conversation_messages = self._call_ai_with_prompt(
            text_content,
            system_prompt,
            reference_images
        )
        
        # Get expected column names
        expected_columns = [q.get("column_name", "") for q in questions]
        
        # Check for missing fields and retry if needed
        missing = [col for col in expected_columns if not raw_result.get(col)]
        metadata = {
            "questions_count": len(questions),
            "retries": 0,
            "final_missing": []
        }
        
        if missing and len(missing) < len(expected_columns):
            # Some fields missing, retry as a follow-up in the same conversation
            logger.info(f"Following up for {len(missing)} missing fields...")
            retry_questions = [q for q in questions if q.get("column_name") in missing]
            retry_result = self._retry_extraction_followup(
                conversation_messages,
                retry_questions
            )
            
            # Merge results
            for col, value in retry_result.items():
                if value:
                    raw_result[col] = value
            
            metadata["retries"] = 1
        
        # Final check for missing
        metadata["final_missing"] = [col for col in expected_columns if not raw_result.get(col)]
        
        return raw_result, metadata
    
    def _call_ai_with_prompt(
        self,
        text_content: str,
        system_prompt: str,
        reference_images: List[dict] = None
    ) -> Tuple[dict, List[dict]]:
        """
        Make the AI API call with a custom prompt (OpenAI or Anthropic).

        Returns:
            Tuple of (raw extraction result as dictionary, conversation messages for follow-up)
        """
        intro = "Please analyze the following document and answer the questions.\n\n"
        intro += "DOCUMENT TEXT:\n"
        intro += "=" * 50 + "\n"
        intro += text_content
        intro += "\n" + "=" * 50

        if reference_images:
            intro += f"\n\nBelow are {len(reference_images)} page image(s) for visual reference:"

        if self.provider == "anthropic":
            # Apply size limits to avoid 413 errors
            _MAX_CHARS = 80_000
            _MAX_IMGS = 50

            truncated = text_content[:_MAX_CHARS]
            if len(text_content) > _MAX_CHARS:
                truncated += "\n\n[... document truncated for size ...]"

            trunc_intro = "Please analyze the following document and answer the questions.\n\n"
            trunc_intro += "DOCUMENT TEXT:\n"
            trunc_intro += "=" * 50 + "\n"
            trunc_intro += truncated
            trunc_intro += "\n" + "=" * 50
            if reference_images:
                capped = min(len(reference_images), _MAX_IMGS)
                trunc_intro += f"\n\nBelow are {capped} page image(s) for visual reference:"

            content = [{"type": "text", "text": trunc_intro}]
            if reference_images:
                for img in reference_images[:_MAX_IMGS]:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img.get("mime_type", "image/jpeg"),
                            "data": img["base64_image"]
                        }
                    })

            anthropic_system = system_prompt + "\n\nIMPORTANT: Respond with a JSON object only. Do not use markdown code fences."
            # Store so _retry_extraction_followup can reuse it
            self._current_system_prompt = anthropic_system

            response = self.client.messages.create(
                model=self._model,
                max_tokens=4000,
                system=anthropic_system,
                messages=[{"role": "user", "content": content}]
            )
            response_text = response.content[0].text.strip()

            # Build conversation history for potential follow-up
            messages = [
                {"role": "user", "content": content},
                {"role": "assistant", "content": response_text}
            ]

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

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ]
            response = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=4000,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content.strip()
            messages.append({"role": "assistant", "content": response_text})

        clean_response = response_text
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1])

        try:
            return json.loads(clean_response), messages
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            return {}, messages

    # Keep old name as alias for backward compatibility
    def _call_openai_with_prompt(self, text_content, system_prompt, reference_images=None):
        return self._call_ai_with_prompt(text_content, system_prompt, reference_images)
    
    def _retry_extraction_followup(
        self,
        conversation_messages: List[dict],
        questions: List[dict]
    ) -> dict:
        """
        Retry extraction as a follow-up in the same conversation.

        This continues the existing conversation without resending the document/images,
        which is more efficient and provides better context to the AI.

        Args:
            conversation_messages: The conversation history from the first call
            questions: List of question dicts for missing fields to retry

        Returns:
            Dictionary with extracted values for the missing fields
        """
        followup_msg = "Some fields in your response were empty. Please look again VERY carefully in the document for the following information:\n\n"
        for q in questions:
            followup_msg += f"- {q.get('question', '')} → field: \"{q.get('column_name', '')}\"\n"
        followup_msg += "\nReturn ONLY these fields as a JSON object. If you truly cannot find the information, return an empty string for that field."

        messages = conversation_messages + [{"role": "user", "content": followup_msg}]

        if self.provider == "anthropic":
            system = getattr(self, "_current_system_prompt", "You are a document extraction assistant. Return answers as JSON only.")
            response = self.client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=system,
                messages=messages
            )
            response_text = response.content[0].text.strip()
        else:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=2000,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse follow-up response as JSON")
            return {}
    
    def _retry_extraction(
        self,
        text_content: str,
        questions: List[dict],
        reference_images: List[dict] = None
    ) -> dict:
        """
        Retry extraction for specific questions that had empty results.
        
        Args:
            text_content: Document text
            questions: List of question dicts to retry
            reference_images: Optional page images
            
        Returns:
            Dictionary with extracted values
        """
        retry_prompt = """You are extracting specific information that may have been missed.
Look VERY carefully in the document for the following information.
If you truly cannot find it, return an empty string.

"""
        for q in questions:
            retry_prompt += f"- {q.get('question', '')} → field: \"{q.get('column_name', '')}\"\n"
        
        retry_prompt += "\nReturn as a JSON object with the field names as keys."
        
        content = []
        
        intro = "Please look carefully for this specific information:\n\n"
        intro += "DOCUMENT TEXT:\n"
        intro += "=" * 50 + "\n"
        intro += text_content[:15000]  # Limit for retry
        intro += "\n" + "=" * 50
        
        content.append({"type": "text", "text": intro})
        
        # Add first image only for retry
        if reference_images and len(reference_images) > 0:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{reference_images[0]['mime_type']};base64,{reference_images[0]['base64_image']}",
                    "detail": "low"
                }
            })
        
        if self.provider == "anthropic":
            anthropic_retry_prompt = retry_prompt + "\n\nReturn answers as a JSON object only."
            content_anthropic = [{"type": "text", "text": intro}]
            if reference_images and len(reference_images) > 0:
                content_anthropic.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": reference_images[0].get("mime_type", "image/jpeg"),
                        "data": reference_images[0]["base64_image"]
                    }
                })
            response = self.client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=anthropic_retry_prompt,
                messages=[{"role": "user", "content": content_anthropic}]
            )
            response_text = response.content[0].text.strip()
        else:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": retry_prompt},
                    {"role": "user", "content": content}
                ],
                max_tokens=2000,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}

    # ========== Legacy methods for backward compatibility ==========
    
    def extract(
        self,
        text_content: str,
        reference_images: List[dict] = None
    ) -> Tuple[UniversalAIFields, dict]:
        """
        Extract data from document using AI (legacy universal schema).
        
        Args:
            text_content: Document text content
            reference_images: Optional list of page images for visual reference
                            Each dict should have: base64_image, mime_type, page_number
                            
        Returns:
            Tuple of (UniversalAIFields, metadata dict)
        """
        logger.info("Extracting with universal schema...")
        
        # First extraction pass
        raw_result = self._call_openai(text_content, reference_images)
        
        # Validate and retry if needed
        fields, metadata = self.validator.validate_and_retry(
            initial_data=raw_result,
            document_text=text_content,
            extract_func=lambda text, missing: self._extract_missing_fields(text, missing, reference_images)
        )
        
        return fields, metadata
    
    def _call_openai(
        self,
        text_content: str,
        reference_images: List[dict] = None
    ) -> dict:
        """
        Make the OpenAI API call (legacy method).
        
        Returns raw extraction result as dictionary.
        """
        # Build message content
        content = []
        
        # Add text content
        intro = "Please analyze the following document and extract all available information.\n\n"
        intro += "DOCUMENT TEXT:\n"
        intro += "=" * 50 + "\n"
        intro += text_content
        intro += "\n" + "=" * 50
        
        if reference_images:
            intro += f"\n\nBelow are {len(reference_images)} page image(s) for visual reference:"
        
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
        
        # Make API call
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": UNIVERSAL_EXTRACTION_PROMPT},
                {"role": "user", "content": content}
            ],
            max_tokens=4000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        # Parse response
        response_text = response.choices[0].message.content.strip()
        
        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            return {}
    
    def _extract_missing_fields(
        self,
        text_content: str,
        missing_fields: List[str],
        reference_images: List[dict] = None
    ) -> dict:
        """
        Re-extract only the missing fields (legacy method).
        
        Args:
            text_content: Document text
            missing_fields: List of field names to extract
            reference_images: Optional page images
            
        Returns:
            Dictionary with extracted values for missing fields
        """
        retry_prompt = ExtractionValidator.build_retry_prompt(missing_fields)
        
        content = []
        
        intro = retry_prompt + "\n\n"
        intro += "DOCUMENT TEXT:\n"
        intro += "=" * 50 + "\n"
        intro += text_content[:10000]  # Limit for retry
        intro += "\n" + "=" * 50
        
        content.append({"type": "text", "text": intro})
        
        # Add first image only for retry
        if reference_images and len(reference_images) > 0:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{reference_images[0]['mime_type']};base64,{reference_images[0]['base64_image']}",
                    "detail": "low"
                }
            })
        
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are extracting specific missing fields from a document. Return only the requested fields as a JSON object."},
                {"role": "user", "content": content}
            ],
            max_tokens=1000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content.strip()
        
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}
    
    def extract_to_dict(
        self,
        text_content: str,
        reference_images: List[dict] = None
    ) -> dict:
        """
        Extract and return as flat dictionary (for Excel/CSV output).
        Legacy method using universal schema.
        
        Args:
            text_content: Document text content
            reference_images: Optional page images
            
        Returns:
            Flat dictionary with field names as keys
        """
        fields, metadata = self.extract(text_content, reference_images)
        result = fields.to_flat_dict()
        
        # Add metadata
        result['_retries'] = metadata.get('retries', 0)
        result['_missing_fields'] = ', '.join(metadata.get('final_missing', []))
        
        return result


def get_pdf_settings_from_config() -> dict:
    """
    Load PDF processing settings from app_config.json.
    
    Returns:
        dict with 'process_all_pages' and 'max_vision_pages'
    """
    import json
    config_path = "app_config.json"
    
    defaults = {
        "process_all_pages": False,
        "max_vision_pages": 10
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {
                    "process_all_pages": config.get("process_all_pages", defaults["process_all_pages"]),
                    "max_vision_pages": config.get("max_vision_pages", defaults["max_vision_pages"])
                }
        except Exception:
            pass
    
    return defaults


def extract_document(
    file_path: str,
    api_key: Optional[str] = None,
    questions: Optional[List[dict]] = None,
    process_all_pages: Optional[bool] = None,
    max_vision_pages: Optional[int] = None,
    provider: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> Tuple[dict, dict]:
    """
    Convenience function to extract data from a document file.

    Args:
        file_path: Path to the document (PDF or Excel)
        api_key: API key for the selected provider
        questions: Optional list of custom questions (if None, uses legacy schema)
        process_all_pages: If True, send all PDF pages as images. If None, uses config.
        max_vision_pages: Max pages to process (ignored if process_all_pages is True). If None, uses config.
        provider: "openai" or "anthropic" (defaults to AI_PROVIDER env var)
        anthropic_api_key: Explicit Anthropic key (alternative to api_key when provider="anthropic")

    Returns:
        Tuple of (extracted data dict, sources/metadata dict)
    """
    from extractors import (
        extract_pdf_text,
        get_pages_needing_vision,
        extract_specific_pages_as_images,
        extract_pdf_as_images,
        extract_excel_content
    )
    
    # Load settings from config if not provided
    if process_all_pages is None or max_vision_pages is None:
        pdf_settings = get_pdf_settings_from_config()
        if process_all_pages is None:
            process_all_pages = pdf_settings["process_all_pages"]
        if max_vision_pages is None:
            max_vision_pages = pdf_settings["max_vision_pages"]
    
    ext = os.path.splitext(file_path)[1].lower()
    
    extractor = AIExtractor(api_key=api_key, provider=provider, anthropic_api_key=anthropic_api_key)
    
    if ext == '.pdf':
        # Extract PDF text
        text_content = extract_pdf_text(file_path)
        
        # Get images based on settings
        if process_all_pages:
            # Send all pages as images
            reference_images = extract_pdf_as_images(file_path, dpi=100)
            logger.info(f"Processing all {len(reference_images)} pages as images")
        else:
            # Get images for pages with tables/graphics (limited)
            vision_pages = get_pages_needing_vision(file_path, max_pages=max_vision_pages)
            reference_images = extract_specific_pages_as_images(file_path, vision_pages, dpi=100)
            logger.info(f"Processing {len(reference_images)} pages with tables/images")
        
        if questions:
            result, metadata = extractor.extract_with_questions(
                text_content, questions, reference_images
            )
            return result, metadata
        else:
            fields, metadata = extractor.extract(text_content, reference_images)
            return fields.to_flat_dict(), metadata
        
    elif ext in ['.xlsx', '.xlsm', '.xls']:
        # Extract Excel content
        content = extract_excel_content(file_path)
        
        if questions:
            result, metadata = extractor.extract_with_questions(content, questions, None)
            return result, metadata
        else:
            fields, metadata = extractor.extract(content, None)
            return fields.to_flat_dict(), metadata
        
    else:
        raise ValueError(f"Unsupported file type: {ext}")
