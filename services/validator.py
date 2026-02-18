"""
Validator Service - Validate AI extraction and retry for missing fields

Validates AI response against the universal schema and re-prompts
for missing required fields (max 2 retries).
"""

from typing import List, Dict, Any, Tuple, Optional, Callable
import json

from schemas.universal_schema import UniversalAIFields, validate_extraction


class ValidationResult:
    """Result of validation check."""
    
    def __init__(
        self,
        is_valid: bool,
        fields: UniversalAIFields,
        missing_fields: List[str] = None,
        errors: List[str] = None
    ):
        self.is_valid = is_valid
        self.fields = fields
        self.missing_fields = missing_fields or []
        self.errors = errors or []
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "fields": self.fields.to_flat_dict() if self.fields else {},
            "missing_fields": self.missing_fields,
            "errors": self.errors
        }


class ExtractionValidator:
    """
    Validates AI extraction results and handles retries.
    
    Features:
    - Validates response against UniversalAIFields schema
    - Identifies missing required fields
    - Supports retry with targeted prompts for missing fields
    """
    
    # Fields that should ideally be present
    PREFERRED_FIELDS = [
        "title",
        "document_type",
        "effective_date",
    ]
    
    # Fields that are strongly required
    REQUIRED_FIELDS = [
        "title",
        "document_type",
    ]
    
    MAX_RETRIES = 2
    
    def __init__(self, retry_callback: Optional[Callable] = None):
        """
        Initialize validator.
        
        Args:
            retry_callback: Function to call for retry extraction.
                           Signature: (missing_fields: List[str], context: str) -> dict
        """
        self.retry_callback = retry_callback
    
    def validate(self, data: dict) -> ValidationResult:
        """
        Validate extraction data against the schema.
        
        Args:
            data: Dictionary of extracted fields
            
        Returns:
            ValidationResult with validation status and parsed fields
        """
        errors = []
        
        # Parse and validate
        try:
            fields, missing = validate_extraction(data)
        except Exception as e:
            errors.append(f"Schema validation error: {str(e)}")
            fields = UniversalAIFields()
            missing = list(self.REQUIRED_FIELDS)
        
        # Check for required fields
        for field in self.REQUIRED_FIELDS:
            value = getattr(fields, field, None)
            if not value:
                if field not in missing:
                    missing.append(field)
        
        is_valid = len(missing) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            fields=fields,
            missing_fields=missing,
            errors=errors
        )
    
    def validate_and_retry(
        self,
        initial_data: dict,
        document_text: str,
        extract_func: Callable[[str, List[str]], dict]
    ) -> Tuple[UniversalAIFields, dict]:
        """
        Validate extraction and retry for missing fields if needed.
        
        Args:
            initial_data: Initial extraction result
            document_text: Original document text for retries
            extract_func: Function to call for extraction retry.
                         Signature: (document_text, missing_fields) -> dict
                         
        Returns:
            Tuple of (final validated fields, metadata dict)
        """
        result = self.validate(initial_data)
        
        metadata = {
            "retries": 0,
            "initial_missing": result.missing_fields.copy(),
            "final_missing": result.missing_fields,
            "validation_errors": result.errors
        }
        
        if result.is_valid:
            return result.fields, metadata
        
        # Retry for missing fields
        current_data = initial_data.copy()
        
        for attempt in range(self.MAX_RETRIES):
            if not result.missing_fields:
                break
            
            print(f"    Retry {attempt + 1}/{self.MAX_RETRIES} for missing fields: {result.missing_fields}")
            
            try:
                # Get additional data for missing fields
                retry_data = extract_func(document_text, result.missing_fields)
                
                # Merge with existing data
                for field, value in retry_data.items():
                    if value and (not current_data.get(field)):
                        current_data[field] = value
                
                # Re-validate
                result = self.validate(current_data)
                metadata["retries"] = attempt + 1
                metadata["final_missing"] = result.missing_fields
                
            except Exception as e:
                metadata["validation_errors"].append(f"Retry {attempt + 1} failed: {str(e)}")
                break
        
        return result.fields, metadata
    
    @staticmethod
    def build_retry_prompt(missing_fields: List[str]) -> str:
        """
        Build a targeted prompt for missing fields.
        
        Args:
            missing_fields: List of field names that are missing
            
        Returns:
            Prompt string for retry extraction
        """
        field_descriptions = {
            "title": "the document title (look at the header/first page)",
            "document_type": "the type of document (e.g., 'MGA Agreement', 'Quota Share Contract', 'Reinsurance Treaty')",
            "effective_date": "when the agreement takes effect (look for 'effective as of', 'commence on', 'effective date')",
            "executed_date": "when the document was signed/executed",
            "expiration_date": "when the agreement expires/terminates",
            "broker_name": "the broker or intermediary company name",
            "carrier_name": "the insurance carrier/company name",
            "mga_name": "the Managing General Agent name",
            "parties": "all parties to this agreement and their roles",
            "summary": "a 2-3 sentence summary of the document's purpose",
        }
        
        fields_text = "\n".join(
            f"- {field}: {field_descriptions.get(field, field)}"
            for field in missing_fields
        )
        
        return f"""The following information was not found in the initial extraction. Please look more carefully for:

{fields_text}

Search the entire document including:
- Headers and footers
- Signature blocks
- Recitals and preamble
- Schedules and exhibits
- Definitions sections

Return a JSON object with just these fields. Use null if truly not found after careful review."""

