"""
AI Document Data Extractor

Usage:
    python main.py "path/to/document.pdf"
    python main.py "path/to/spreadsheet.xlsm"
"""

import sys
import os
import logging

# Initialize logging before other imports
from logger import setup_logging, get_logger

setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

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
    
    logger.info(f"Processing file: {file_path}")
    
    if ext == ".pdf":
        page_count = get_pdf_page_count(file_path)
        logger.info(f"PDF has {page_count} page(s)")
        
        # Extract full text content
        logger.debug("Extracting text content...")
        text_content = extract_pdf_text(file_path)
        logger.debug(f"Extracted {len(text_content)} characters of text")
        
        # Smart detection: find pages with tables/images that need vision
        logger.debug("Analyzing pages for tables and images...")
        vision_pages = get_pages_needing_vision(file_path, max_pages=MAX_VISION_PAGES)
        
        if vision_pages:
            logger.info(f"Found {len(vision_pages)} page(s) with tables/images: {vision_pages}")
            reference_images = extract_specific_pages_as_images(file_path, vision_pages, dpi=100)
            logger.debug(f"Extracted {len(reference_images)} page images for vision analysis")
        else:
            logger.info("No tables/images detected, using text-only extraction")
            reference_images = None
        
        logger.info("Sending to OpenAI for analysis...")
        raw_results, sources = extract_from_pdf_hybrid(text_content, reference_images)
        logger.debug(f"Received {len(raw_results)} fields from AI extraction")
        
    elif ext in [".xlsx", ".xlsm"]:
        logger.debug("Extracting Excel content...")
        content = extract_excel_content(file_path)
        logger.debug(f"Extracted Excel content: {len(content)} characters")
        
        logger.info("Sending to OpenAI for analysis...")
        raw_results, sources = extract_from_excel_content(content)
        logger.debug(f"Received {len(raw_results)} fields from AI extraction")
        
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported types: .pdf, .xlsx, .xlsm")
    
    # Format results with field names
    extracted_data = format_extraction_results(raw_results)
    
    return extracted_data, sources


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("AI Document Data Extractor - CLI Mode")
    logger.info("=" * 60)

    try:
        if len(sys.argv) < 2:
            logger.warning("Usage: python main.py <file_path>")
            logger.info("Supported file types: .pdf, .xlsx, .xlsm")
        
        file_path = sys.argv[1]
    except IndexError:
        logger.warning("No file path provided")
        file_path = "InputFolder/MGA Agreement - Bridger - eff. 2022-08-01.pdf"
        logger.info(f"Using default file path: {file_path}")

    
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
            
            # Log summary
            summary = get_extraction_summary(extracted_data)
            logger.info(f"\n{summary}")
            
            # Log sources for debugging
            logger.debug("Sources (where information was found):")
            for field, source in sources.items():
                logger.debug(f"  {field}: {source}")
            
            # Write to Excel (append to master file)
            filename = os.path.basename(file_path)
            excel_path = write_to_excel(filename, extracted_data, source_path=file_path)
            logger.info(f"Appended to Excel: {excel_path}")
            
            # Write to timestamped CSV (one per run)
            csv_path = write_to_csv(filename, extracted_data, source_path=file_path)
            logger.info(f"Saved individual CSV: {csv_path}")
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
        except ValueError as e:
            logger.error(f"Validation error: {e}")
        except Exception as e:
            logger.exception(f"An error occurred processing {file_path}: {e}")

    logger.info("Processing complete")


if __name__ == "__main__":
    main()
