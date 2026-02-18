"""
Single File Extractor - Extract metadata and/or AI data from a single document.

Configure the settings below and run:
    python extract_single.py
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# CONFIGURATION - Edit these settings"
# =============================================================================

# Path to the file you want to extract data from
FILE_PATH = r"C:\Users\bogda\DebogAutomations\Clients\RobertKaplan\AI_Doc_Analyzer\InputFolder\XOL QS - Pronto - eff. 2023-01-01.pdf"
# FILE_PATH = r"C:\Users\bogda\DebogAutomations\Clients\RobertKaplan\AI_Doc_Analyzer\InputFolder\Red Point - Western Surplus Eff. 3-1-24.xlsm"
# Extraction mode:
#   "metadata" - Extract only file metadata (no AI, no API cost)
#   "ai"       - Extract only AI fields (sends document to OpenAI)
#   "both"     - Extract both metadata and AI fields
EXTRACTION_MODE = "ai"

# Output options
PRINT_RESULTS = True       # Print results to console
SAVE_TO_JSON = True        # Save results to a JSON file
SAVE_TO_EXCEL = False      # Save results to an Excel file

# PDF Processing options (overrides app settings if set)
#   None = Use app settings from Settings tab
#   True = Process all pages as images
#   False = Only process pages with tables/images
PROCESS_ALL_PAGES = None   # Set to True/False to override app settings
MAX_VISION_PAGES = None    # Set to a number to override app settings (ignored if PROCESS_ALL_PAGES=True)

# =============================================================================
# END CONFIGURATION
# =============================================================================


def check_if_processed(file_hash: str) -> tuple[bool, dict | None]:
    """
    Check if a file has been processed before by looking up its hash in the database.
    
    Args:
        file_hash: SHA-256 hash of the file
        
    Returns:
        Tuple of (has_been_processed, previous_record or None)
    """
    try:
        from services.dedup import DedupService
        
        dedup = DedupService()
        
        # Test connection first
        status = dedup.test_connection()
        if status['status'] != 'connected':
            print(f"  ⚠️ Database not available: {status.get('message', 'Unknown error')}")
            return False, None
        
        # Check if hash exists
        previous_record = dedup.get_document_by_hash(file_hash)
        
        if previous_record:
            print(f"  ✓ Found in database - processed on: {previous_record.get('processed_at', 'Unknown')}")
            return True, previous_record
        else:
            print("  ○ Not found in database - new document")
            return False, None
            
    except Exception as e:
        print(f"  ⚠️ Could not check database: {e}")
        return False, None


def extract_metadata(file_path: str) -> dict:
    """Extract metadata from a file."""
    from extractors.metadata_extractor import MetadataExtractor
    from services.hasher import FileHasher
    
    print(f"\n📋 Extracting metadata from: {os.path.basename(file_path)}")
    
    # Compute file hash
    print("  → Computing file hash...")
    file_hash = FileHasher.hash_file(file_path)
    
    # Check database for previous processing
    print("  → Checking database for previous processing...")
    has_been_processed, previous_record = check_if_processed(file_hash)
    
    # Extract all metadata
    fields = MetadataExtractor.extract_all(
        file_path=file_path,
        file_hash=file_hash,
        has_been_processed=has_been_processed
    )
    
    return fields.to_dict()


def load_pdf_settings() -> dict:
    """Load PDF settings from app config or use script overrides."""
    # Start with defaults
    settings = {
        "process_all_pages": False,
        "max_vision_pages": 10
    }
    
    # Load from app config
    config_path = "app_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                settings["process_all_pages"] = config.get("process_all_pages", False)
                settings["max_vision_pages"] = config.get("max_vision_pages", 10)
        except Exception:
            pass
    
    # Apply script overrides if set
    if PROCESS_ALL_PAGES is not None:
        settings["process_all_pages"] = PROCESS_ALL_PAGES
    if MAX_VISION_PAGES is not None:
        settings["max_vision_pages"] = MAX_VISION_PAGES
    
    return settings


def extract_ai_data(file_path: str) -> dict:
    """Extract AI data from a file."""
    from services.ai_extractor import AIExtractor
    from extractors import (
        extract_pdf_text,
        get_pages_needing_vision,
        extract_specific_pages_as_images,
        extract_pdf_as_images,
        extract_excel_content
    )
    
    print(f"\n🤖 Running AI extraction on: {os.path.basename(file_path)}")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    extractor = AIExtractor()
    
    if ext == '.pdf':
        # Load PDF settings
        pdf_settings = load_pdf_settings()
        process_all = pdf_settings["process_all_pages"]
        max_pages = pdf_settings["max_vision_pages"]
        
        # Extract PDF text
        print("  → Extracting text from PDF...")
        text_content = extract_pdf_text(file_path)
        
        # Get images based on settings
        print("  → Analyzing pages for visual content...")
        if process_all:
            reference_images = extract_pdf_as_images(file_path, dpi=100)
            print(f"  → Processing ALL {len(reference_images)} pages as images")
        else:
            vision_pages = get_pages_needing_vision(file_path, max_pages=max_pages)
            reference_images = extract_specific_pages_as_images(file_path, vision_pages, dpi=100)
            print(f"  → Processing {len(reference_images)} pages with tables/images (max: {max_pages})")
        
        print("  → Sending to AI for extraction...")
        fields, metadata = extractor.extract(text_content, reference_images)
        
    elif ext in ['.xlsx', '.xlsm', '.xls']:
        # Extract Excel content
        print("  → Extracting content from Excel...")
        content = extract_excel_content(file_path)
        
        print("  → Sending to AI for extraction...")
        fields, metadata = extractor.extract(content, None)
        
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    result = fields.to_flat_dict()
    result['_retries'] = metadata.get('retries', 0)
    result['_missing_fields'] = ', '.join(metadata.get('final_missing', []))
    
    return result


def save_to_json(data: dict, file_path: str, mode: str):
    """Save results to a JSON file."""
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{base_name}_{mode}_{timestamp}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n💾 Saved to: {output_path}")
    return output_path


def save_to_excel(data: dict, file_path: str, mode: str):
    """Save results to an Excel file."""
    import pandas as pd
    
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{base_name}_{mode}_{timestamp}.xlsx"
    
    # Convert to DataFrame (single row)
    df = pd.DataFrame([data])
    df.to_excel(output_path, index=False)
    
    print(f"\n📊 Saved to: {output_path}")
    return output_path


def print_results(data: dict, title: str):
    """Pretty print the results."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)
    
    for key, value in data.items():
        # Truncate long values for display
        str_value = str(value)
        if len(str_value) > 80:
            str_value = str_value[:77] + "..."
        print(f"  {key}: {str_value}")
    
    print('='*60)


def main():
    """Main entry point."""
    # Validate file exists
    if not os.path.exists(FILE_PATH):
        print(f"❌ Error: File not found: {FILE_PATH}")
        sys.exit(1)
    
    print(f"\n🔍 Processing: {FILE_PATH}")
    print(f"📝 Mode: {EXTRACTION_MODE}")
    
    results = {}
    
    # Extract based on mode
    if EXTRACTION_MODE in ["metadata", "both"]:
        metadata = extract_metadata(FILE_PATH)
        results['metadata'] = metadata
        
        if PRINT_RESULTS:
            print_results(metadata, "METADATA EXTRACTION RESULTS")
    
    if EXTRACTION_MODE in ["ai", "both"]:
        ai_data = extract_ai_data(FILE_PATH)
        results['ai_extraction'] = ai_data
        
        if PRINT_RESULTS:
            print_results(ai_data, "AI EXTRACTION RESULTS")
    
    # Combine results for output
    if EXTRACTION_MODE == "both":
        combined = {**results.get('metadata', {}), **results.get('ai_extraction', {})}
    elif EXTRACTION_MODE == "metadata":
        combined = results.get('metadata', {})
    else:
        combined = results.get('ai_extraction', {})
    
    # Save outputs
    if SAVE_TO_JSON:
        save_to_json(combined, FILE_PATH, EXTRACTION_MODE)
    
    if SAVE_TO_EXCEL:
        save_to_excel(combined, FILE_PATH, EXTRACTION_MODE)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()

