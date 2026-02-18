"""
Services Package - Business logic and utilities
"""

from .hasher import FileHasher
from .dedup import DedupService
from .validator import ExtractionValidator, ValidationResult
from .ai_extractor import AIExtractor, extract_document
from .aws import AWSService
from .folder_scanner import (
    FolderScanner, 
    ScanResult,
    ScanFileInfo,
    save_result_to_json, 
    append_result_to_excel,
    get_metadata_columns,
    get_ai_columns,
    get_all_columns
)

__all__ = [
    'FileHasher', 
    'DedupService', 
    'ExtractionValidator', 
    'ValidationResult',
    'AIExtractor',
    'extract_document',
    'AWSService',
    'FolderScanner',
    'ScanResult',
    'save_result_to_json',
    'append_result_to_excel',
    'get_metadata_columns',
    'get_ai_columns',
    'get_all_columns',
    'ScanFileInfo'
]

