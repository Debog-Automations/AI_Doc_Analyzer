"""
Metadata Extractor - Extract programmatic fields from files

Extracts fields that don't require AI:
- File system metadata (name, size, path, extension)
- PDF metadata (Adobe ID, DocuSign ID, e-signature IDs)
- Excel metadata
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
import mimetypes


@dataclass
class ProgrammaticFields:
    """All programmatic fields that can be extracted without AI."""
    
    # File system fields
    source_path: str = ""
    filename: str = ""
    filename_without_extension: str = ""
    file_extension: str = ""
    document_size: int = 0
    document_size_formatted: str = ""
    
    # Hash and processing status
    file_hash: str = ""
    has_been_processed: bool = False
    
    # PDF-specific metadata
    adobe_document_id: Optional[str] = None
    docusign_document_id: Optional[str] = None
    esignature_id: Optional[str] = None
    
    # Document properties
    pdf_title: Optional[str] = None
    pdf_author: Optional[str] = None
    pdf_subject: Optional[str] = None
    pdf_creator: Optional[str] = None
    pdf_producer: Optional[str] = None
    pdf_creation_date: Optional[str] = None
    pdf_modification_date: Optional[str] = None
    pdf_page_count: int = 0
    
    # User-provided
    comment: str = ""
    
    # Additional metadata
    mime_type: Optional[str] = None
    file_created_at: Optional[str] = None
    file_modified_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper field names for output."""
        return {
            "SourcePathFilenameWksName": self.source_path,
            "FileName": self.filename,
            "FileName wo extension": self.filename_without_extension,
            "File Extension": self.file_extension,
            "Document Size": self.document_size,
            "Document Size Formatted": self.document_size_formatted,
            "File Hash": self.file_hash,
            "Has Been Processed": "Yes" if self.has_been_processed else "No",
            "Adobe Document ID": self.adobe_document_id or "",
            "Docusign Document ID": self.docusign_document_id or "",
            "E-signature ID": self.esignature_id or "",
            "Document Title": self.pdf_title or "",  # Renamed to avoid conflict with AI Title
            "Author": self.pdf_author or "",
            "Subject": self.pdf_subject or "",
            "Creator": self.pdf_creator or "",
            "Producer": self.pdf_producer or "",
            "Creation Date": self.pdf_creation_date or "",
            "Modification Date": self.pdf_modification_date or "",
            "Page Count": self.pdf_page_count,
            "Comment": self.comment,
            "MIME Type": self.mime_type or "",
            "File Created At": self.file_created_at or "",
            "File Modified At": self.file_modified_at or "",
        }


class MetadataExtractor:
    """
    Extract programmatic metadata from files.
    
    Supports:
    - All file types: file system metadata
    - PDF files: Document properties, IDs, signatures
    - Excel files: Workbook properties
    """
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    @staticmethod
    def extract_file_system_metadata(file_path: str) -> ProgrammaticFields:
        """
        Extract basic file system metadata.
        
        Args:
            file_path: Path to the file
            
        Returns:
            ProgrammaticFields with file system data
        """
        fields = ProgrammaticFields()
        
        fields.source_path = file_path
        fields.filename = os.path.basename(file_path)
        
        name, ext = os.path.splitext(fields.filename)
        fields.filename_without_extension = name
        fields.file_extension = ext.lower()
        
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            fields.document_size = stat.st_size
            fields.document_size_formatted = MetadataExtractor.format_size(stat.st_size)
            
            # File timestamps
            fields.file_created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
            fields.file_modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        fields.mime_type = mimetypes.guess_type(file_path)[0]
        
        return fields
    
    @staticmethod
    def extract_pdf_metadata(file_path: str, fields: Optional[ProgrammaticFields] = None) -> ProgrammaticFields:
        """
        Extract metadata from PDF files.
        
        Args:
            file_path: Path to the PDF file
            fields: Optional existing fields to update
            
        Returns:
            ProgrammaticFields with PDF metadata
        """
        if fields is None:
            fields = MetadataExtractor.extract_file_system_metadata(file_path)
        
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            
            # Page count
            fields.pdf_page_count = len(doc)
            
            # Document metadata
            metadata = doc.metadata or {}
            
            fields.pdf_title = metadata.get('title', '') or None
            fields.pdf_author = metadata.get('author', '') or None
            fields.pdf_subject = metadata.get('subject', '') or None
            fields.pdf_creator = metadata.get('creator', '') or None
            fields.pdf_producer = metadata.get('producer', '') or None
            fields.pdf_creation_date = metadata.get('creationDate', '') or None
            fields.pdf_modification_date = metadata.get('modDate', '') or None
            
            # Extract Adobe Document ID from /ID field
            # The ID is typically in the trailer
            try:
                # Get PDF trailer
                if hasattr(doc, 'pdf_trailer') and doc.pdf_trailer:
                    trailer = doc.pdf_trailer()
                    if trailer and 'ID' in trailer:
                        id_array = trailer['ID']
                        if id_array and len(id_array) > 0:
                            # First ID is the permanent document ID
                            fields.adobe_document_id = id_array[0].hex() if hasattr(id_array[0], 'hex') else str(id_array[0])
            except Exception:
                pass
            
            # Try to extract DocuSign and e-signature IDs from XMP metadata
            try:
                xmp = doc.metadata
                if xmp:
                    # DocuSign often adds custom properties
                    for key, value in xmp.items():
                        key_lower = key.lower()
                        if 'docusign' in key_lower:
                            fields.docusign_document_id = str(value)
                        elif 'esign' in key_lower or 'signature' in key_lower:
                            if not fields.esignature_id:
                                fields.esignature_id = str(value)
            except Exception:
                pass
            
            # Check XMP metadata for more IDs
            try:
                xmp_bytes = doc.xref_get_key(-1, "Metadata")
                if xmp_bytes and xmp_bytes[0] == 'stream':
                    # Parse XMP XML for DocuSign/e-signature info
                    xmp_stream = doc.xref_stream(-1)
                    if xmp_stream:
                        xmp_text = xmp_stream.decode('utf-8', errors='ignore')
                        
                        # Look for DocuSign envelope ID
                        import re
                        docusign_match = re.search(r'docusign.*?([a-f0-9\-]{36})', xmp_text, re.IGNORECASE)
                        if docusign_match:
                            fields.docusign_document_id = docusign_match.group(1)
                        
                        # Look for other e-signature IDs
                        esign_match = re.search(r'(?:esign|signature).*?id.*?["\']([^"\']+)["\']', xmp_text, re.IGNORECASE)
                        if esign_match and not fields.esignature_id:
                            fields.esignature_id = esign_match.group(1)
            except Exception:
                pass
            
            # Check document properties/info dict for custom fields
            try:
                # Get the Info dictionary
                if doc.is_pdf:
                    for xref in range(1, doc.xref_length()):
                        try:
                            obj_type = doc.xref_get_key(xref, "Type")
                            if obj_type and "Info" in str(obj_type):
                                # This is the info dict, check all keys
                                keys = doc.xref_get_keys(xref)
                                for key in keys:
                                    value = doc.xref_get_key(xref, key)
                                    if value:
                                        key_lower = key.lower()
                                        value_str = str(value[1]) if len(value) > 1 else str(value)
                                        
                                        if 'docusign' in key_lower and not fields.docusign_document_id:
                                            fields.docusign_document_id = value_str
                                        elif ('esign' in key_lower or 'signature' in key_lower) and not fields.esignature_id:
                                            fields.esignature_id = value_str
                        except Exception:
                            continue
            except Exception:
                pass
            
            doc.close()
            
        except ImportError:
            print("PyMuPDF not installed - cannot extract PDF metadata")
        except Exception as e:
            print(f"Error extracting PDF metadata: {e}")
        
        return fields
    
    @staticmethod
    def extract_excel_metadata(file_path: str, fields: Optional[ProgrammaticFields] = None) -> ProgrammaticFields:
        """
        Extract metadata from Excel files.
        
        Args:
            file_path: Path to the Excel file
            fields: Optional existing fields to update
            
        Returns:
            ProgrammaticFields with Excel metadata
        """
        if fields is None:
            fields = MetadataExtractor.extract_file_system_metadata(file_path)
        
        try:
            from openpyxl import load_workbook
            
            # Load workbook in read-only mode for efficiency
            wb = load_workbook(file_path, read_only=True, data_only=True)
            
            # Get document properties
            props = wb.properties
            if props:
                if props.title:
                    fields.pdf_title = props.title  # Reuse field
                if props.creator:
                    fields.pdf_author = props.creator  # Reuse field
                if props.subject:
                    fields.pdf_subject = props.subject
                if props.created:
                    fields.pdf_creation_date = props.created.isoformat() if props.created else None
                if props.modified:
                    fields.pdf_modification_date = props.modified.isoformat() if props.modified else None
            
            wb.close()
            
        except ImportError:
            print("openpyxl not installed - cannot extract Excel metadata")
        except Exception as e:
            print(f"Error extracting Excel metadata: {e}")
        
        return fields
    
    @staticmethod
    def extract_all(file_path: str, file_hash: str = "", has_been_processed: bool = False) -> ProgrammaticFields:
        """
        Extract all available metadata from a file.
        
        Args:
            file_path: Path to the file
            file_hash: Pre-computed hash (if available)
            has_been_processed: Whether file was previously processed
            
        Returns:
            ProgrammaticFields with all available metadata
        """
        # Start with file system metadata
        fields = MetadataExtractor.extract_file_system_metadata(file_path)
        
        # Set hash and processing status
        fields.file_hash = file_hash
        fields.has_been_processed = has_been_processed
        
        # Extract type-specific metadata
        ext = fields.file_extension.lower()
        
        if ext == '.pdf':
            fields = MetadataExtractor.extract_pdf_metadata(file_path, fields)
        elif ext in ['.xlsx', '.xlsm', '.xls']:
            fields = MetadataExtractor.extract_excel_metadata(file_path, fields)
        
        return fields

