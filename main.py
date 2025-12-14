"""
AI Document Data Extractor

Usage:
    python main.py "path/to/document.pdf"
    python main.py "path/to/spreadsheet.xlsm"
"""

import sys
import os

from extractors import (
    extract_pdf_text,
    get_pdf_page_count,
    get_pages_needing_vision,
    extract_specific_pages_as_images,
    extract_excel_content
)
from ai_processor import extract_from_pdf_hybrid, extract_from_excel_content, format_extraction_results
from config import MAX_VISION_PAGES
from output_handler import write_to_excel, write_to_csv, get_extraction_summary


def process_file(file_path: str) -> tuple[dict, dict]:
    """
    Process a file and extract data based on its type.
    
    Args:
        file_path: Path to the file to process
        
    Returns:
        Tuple of (extracted_data, sources) where:
        - extracted_data: Dictionary of extracted field values
        - sources: Dictionary of source locations for each field (for logging)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    print(f"Processing: {file_path}")
    
    if ext == ".pdf":
        page_count = get_pdf_page_count(file_path)
        print(f"  PDF has {page_count} page(s)")
        
        # Extract full text content
        print("  Extracting text content...")
        text_content = extract_pdf_text(file_path)
        
        # Smart detection: find pages with tables/images that need vision
        print("  Analyzing pages for tables and images...")
        vision_pages = get_pages_needing_vision(file_path, max_pages=MAX_VISION_PAGES)
        
        if vision_pages:
            print(f"  Found {len(vision_pages)} page(s) with tables/images: {vision_pages}")
            reference_images = extract_specific_pages_as_images(file_path, vision_pages, dpi=100)
        else:
            print("  No tables/images detected, using text-only extraction")
            reference_images = None
        
        print("  Sending to OpenAI for analysis...")
        raw_results, sources = extract_from_pdf_hybrid(text_content, reference_images)
        
    elif ext in [".xlsx", ".xlsm"]:
        print("  Extracting Excel content...")
        content = extract_excel_content(file_path)
        
        print("  Sending to OpenAI for analysis...")
        raw_results, sources = extract_from_excel_content(content)
        
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported types: .pdf, .xlsx, .xlsm")
    
    # Format results with field names
    extracted_data = format_extraction_results(raw_results)
    
    return extracted_data, sources


def main():
    """Main entry point."""

    try:
        if len(sys.argv) < 2:
            print("Usage: python main.py <file_path>")
            print("  Supported file types: .pdf, .xlsx, .xlsm")
        
        file_path = sys.argv[1]
    except IndexError:
        print("No file path provided")
        file_path = "InputFolder/MGA Agreement - Bridger - eff. 2022-08-01.pdf"
        print(f"Using default file path: {file_path}")

    
    file_paths = [
        "InputFolder/MGA Agreement - Am. No. 1 - Bridger - eff. 2022-08-01.pdf",
        "InputFolder/QSRC - TMR - eff. 2024-04-01.pdf",
        "InputFolder/MGA Agreement - Bridger - eff. 2022-08-01.pdf",
        "InputFolder/XOL QS - Pronto - eff. 2023-01-01.pdf",
        "InputFolder/QSRC - Pronto (Core) - eff. 2023-01-01.pdf",
        "InputFolder/QSRC - End. No. 2 - Pronto (Core) - eff. 2023-03-09.pdf",
        "InputFolder/QSRC - End. No. 1 - Pronto (Core) - eff. 2023-01-01.pdf",
    ]


    for file_path in file_paths:
        try:
            # Process the file
            extracted_data, sources = process_file(file_path)
            
            # Print summary to console
            print("\n" + get_extraction_summary(extracted_data))
            
            # Log sources for debugging
            print("\n  Sources (where information was found):")
            for field, source in sources.items():
                print(f"    {field}: {source}")
            
            # Write to Excel (append to master file)
            filename = os.path.basename(file_path)
            excel_path = write_to_excel(filename, extracted_data, source_path=file_path)
            print(f"\nAppended to Excel: {excel_path}")
            
            # Write to timestamped CSV (one per run)
            csv_path = write_to_csv(filename, extracted_data, source_path=file_path)
            print(f"Saved individual CSV: {csv_path}")
            
        except FileNotFoundError as e:
            print(f"Error: {e}")
            # sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            # sys.exit(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            # sys.exit(1)


if __name__ == "__main__":
    main()

