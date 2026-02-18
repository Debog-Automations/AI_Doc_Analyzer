"""
Schemas Package - Data models and validation schemas
"""

from .universal_schema import (
    UniversalAIFields,
    BusinessValue,
    PartyInfo,
    ExtractionResult,
    validate_extraction,
    UNIVERSAL_EXTRACTION_PROMPT
)

__all__ = [
    'UniversalAIFields',
    'BusinessValue',
    'PartyInfo',
    'ExtractionResult',
    'validate_extraction',
    'UNIVERSAL_EXTRACTION_PROMPT'
]

