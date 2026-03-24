"""
PDF Extractor - Extracts text and converts PDF pages to images for OpenAI.
"""

import base64
import fitz  # PyMuPDF


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract all text content from a PDF with improved layout analysis.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Full text content of the PDF with page markers
    """
    try:
        # Try using pymupdf4llm for better layout preservation
        import pymupdf4llm
        
        # Use layout-aware extraction
        text_parts = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            # Get markdown text which preserves better structure
            md_text = pymupdf4llm.to_markdown(doc, pages=[page_num])
            
            if md_text.strip():
                text_parts.append(f"\n--- Page {page_num + 1} ---\n{md_text}")
        
        doc.close()
        return "\n".join(text_parts)
        
    except ImportError:
        # Fallback to basic extraction if pymupdf4llm not available
        doc = fitz.open(pdf_path)
        
        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if text.strip():
                text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")
        
        doc.close()
        return "\n".join(text_parts)


def extract_pdf_as_images(pdf_path: str, dpi: int = 150, max_pages: int = None) -> list[dict]:
    """
    Convert PDF pages to base64-encoded images.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for rendering (higher = better quality but larger)
        max_pages: Maximum number of pages to convert (None = all pages)
        
    Returns:
        List of dicts with page number and base64 image data
    """
    images = []
    
    doc = fitz.open(pdf_path)
    
    total_pages = len(doc)
    pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
    
    for page_num in range(pages_to_process):
        page = doc[page_num]
        
        # Render page to image at specified DPI
        # Default is 72 DPI, so we calculate zoom factor
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        # Get pixmap (image) of the page
        pixmap = page.get_pixmap(matrix=matrix)

        # Convert to JPEG (much smaller than PNG; quality=85 is fine for OCR/extraction)
        img_bytes = pixmap.tobytes("jpeg", jpg_quality=85)

        # Encode to base64
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        images.append({
            "page_number": page_num + 1,
            "base64_image": base64_image,
            "mime_type": "image/jpeg"
        })
    
    doc.close()
    
    return images


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def analyze_pdf_pages(pdf_path: str) -> list[dict]:
    """
    Analyze each page to determine content type (tables, images, text-only).
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dicts with page analysis results
    """
    doc = fitz.open(pdf_path)
    
    analysis = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Detect tables
        tables = page.find_tables()
        has_tables = len(tables.tables) > 0 if tables else False
        
        # Detect images
        images = page.get_images()
        has_images = len(images) > 0
        
        # Detect drawings/vector graphics
        drawings = page.get_drawings()
        has_drawings = len(drawings) > 0
        
        # Get text content
        text = page.get_text().strip()
        has_text = len(text) > 0
        
        # Determine if this page needs vision processing
        needs_vision = has_tables or has_images or has_drawings
        
        analysis.append({
            "page_number": page_num + 1,
            "has_tables": has_tables,
            "table_count": len(tables.tables) if tables else 0,
            "has_images": has_images,
            "image_count": len(images),
            "has_drawings": has_drawings,
            "has_text": has_text,
            "needs_vision": needs_vision
        })
    
    doc.close()
    
    return analysis


def get_pages_needing_vision(pdf_path: str, max_pages: int = None) -> list[int]:
    """
    Get list of page numbers that contain tables/images and need vision processing.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to return (None = all)
        
    Returns:
        List of page numbers (1-indexed) that need vision processing
    """
    analysis = analyze_pdf_pages(pdf_path)
    
    vision_pages = [p["page_number"] for p in analysis if p["needs_vision"]]
    
    # If no pages need vision, include first page as fallback
    if not vision_pages:
        vision_pages = [1]
    
    # Limit if max_pages specified
    if max_pages:
        vision_pages = vision_pages[:max_pages]
    
    return vision_pages


def extract_specific_pages_as_images(pdf_path: str, page_numbers: list[int], dpi: int = 100) -> list[dict]:
    """
    Convert specific PDF pages to base64-encoded images.
    
    Args:
        pdf_path: Path to the PDF file
        page_numbers: List of page numbers to convert (1-indexed)
        dpi: Resolution for rendering
        
    Returns:
        List of dicts with page number and base64 image data
    """
    images = []
    
    doc = fitz.open(pdf_path)
    
    for page_num in page_numbers:
        if page_num < 1 or page_num > len(doc):
            continue
            
        page = doc[page_num - 1]  # Convert to 0-indexed
        
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        pixmap = page.get_pixmap(matrix=matrix)
        img_bytes = pixmap.tobytes("jpeg", jpg_quality=85)
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        images.append({
            "page_number": page_num,
            "base64_image": base64_image,
            "mime_type": "image/jpeg"
        })
    
    doc.close()
    
    return images

