"""
Deduplication Service - Track processed documents using PostgreSQL

Stores document hashes to skip already-processed files.
Uses Docker-hosted PostgreSQL for persistence.
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .hasher import FileHasher

Base = declarative_base()


class ProcessedDocument(Base):
    """SQLAlchemy model for tracking processed documents."""
    
    __tablename__ = 'processed_documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)  # 'local', 'box', etc.
    source_path = Column(Text, nullable=True)  # Original path/location
    file_size = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='completed')  # 'completed', 'failed', 'skipped'
    error_message = Column(Text, nullable=True)
    extraction_data = Column(Text, nullable=True)  # JSON string of extracted data
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'file_hash': self.file_hash,
            'filename': self.filename,
            'source_type': self.source_type,
            'source_path': self.source_path,
            'file_size': self.file_size,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'status': self.status,
            'error_message': self.error_message
        }


class DedupService:
    """
    Service for document deduplication using content hashes.
    
    Uses PostgreSQL (Docker) for persistent storage.
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        db_host: str = "localhost",
        db_port: int = 5432,
        db_name: str = "document_registry",
        db_user: str = "docanalyzer",
        db_password: str = "docanalyzer_secret"
    ):
        """
        Initialize the deduplication service.
        
        Args:
            database_url: Full PostgreSQL connection URL (takes precedence)
            db_host: Database host (default: localhost)
            db_port: Database port (default: 5432)
            db_name: Database name (default: document_registry)
            db_user: Database username (default: docanalyzer)
            db_password: Database password (default: docanalyzer_secret)
        """
        # Build connection string
        if database_url:
            self.database_url = database_url
        else:
            # Try to get from environment or config
            self.database_url = os.getenv(
                "DATABASE_URL",
                f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            )
        
        self.engine = None
        self.Session = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of database connection."""
        if not self._initialized:
            try:
                self.engine = create_engine(self.database_url, echo=False)
                
                # Create tables if they don't exist
                Base.metadata.create_all(self.engine)
                
                self.Session = sessionmaker(bind=self.engine)
                self._initialized = True
            except Exception as e:
                raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")
    
    def _get_session(self) -> Session:
        """Get a new database session."""
        self._ensure_initialized()
        return self.Session()
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection.
        
        Returns:
            Dict with connection status and details
        """
        try:
            self._ensure_initialized()
            session = self._get_session()
            # Simple query to test connection
            session.execute(text("SELECT 1"))
            session.close()
            return {
                'status': 'connected',
                'database_url': self.database_url.replace(
                    self.database_url.split(':')[2].split('@')[0], '***'
                )  # Hide password
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def compute_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hash string
        """
        return FileHasher.hash_file(file_path)
    
    def is_duplicate(self, file_path: str) -> bool:
        """
        Check if a file has already been processed (by content hash).
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file with same content was already processed
        """
        try:
            file_hash = self.compute_hash(file_path)
            return self.hash_exists(file_hash)
        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return False
    
    def hash_exists(self, file_hash: str) -> bool:
        """
        Check if a hash exists in the database.
        
        Args:
            file_hash: SHA-256 hash string
            
        Returns:
            True if hash exists
        """
        session = self._get_session()
        try:
            exists = session.query(ProcessedDocument).filter_by(
                file_hash=file_hash
            ).first() is not None
            return exists
        finally:
            session.close()
    
    def get_document_by_hash(self, file_hash: str) -> Optional[dict]:
        """
        Get document record by hash.
        
        Args:
            file_hash: SHA-256 hash string
            
        Returns:
            Document dict or None if not found
        """
        session = self._get_session()
        try:
            doc = session.query(ProcessedDocument).filter_by(
                file_hash=file_hash
            ).first()
            return doc.to_dict() if doc else None
        finally:
            session.close()
    
    def check_and_get_status(self, file_path: str) -> Dict[str, Any]:
        """
        Check file status: is it a duplicate? If so, when was it processed?
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with:
            - is_duplicate: bool
            - file_hash: str
            - previous_record: dict or None (if duplicate)
        """
        file_hash = self.compute_hash(file_path)
        previous = self.get_document_by_hash(file_hash)
        
        return {
            'is_duplicate': previous is not None,
            'file_hash': file_hash,
            'previous_record': previous
        }
    
    def register_document(
        self,
        file_path: str,
        file_hash: str,
        source_type: str = 'local',
        status: str = 'completed',
        error_message: Optional[str] = None,
        extraction_data: Optional[str] = None
    ) -> bool:
        """
        Register a processed document in the database.
        
        Args:
            file_path: Path to the file
            file_hash: SHA-256 hash of the file
            source_type: Source type ('local', 'box', etc.)
            status: Processing status
            error_message: Error message if failed
            extraction_data: JSON string of extracted data
            
        Returns:
            True if registered successfully
        """
        session = self._get_session()
        try:
            # Check if already exists
            existing = session.query(ProcessedDocument).filter_by(
                file_hash=file_hash
            ).first()
            
            if existing:
                # Update existing record
                existing.processed_at = datetime.utcnow()
                existing.status = status
                existing.error_message = error_message
                if extraction_data:
                    existing.extraction_data = extraction_data
            else:
                # Create new record
                filename = os.path.basename(file_path)
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
                
                doc = ProcessedDocument(
                    file_hash=file_hash,
                    filename=filename,
                    source_type=source_type,
                    source_path=file_path,
                    file_size=file_size,
                    status=status,
                    error_message=error_message,
                    extraction_data=extraction_data
                )
                session.add(doc)
            
            session.commit()
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            session.close()
    
    def get_all_documents(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """
        Get all processed documents.
        
        Args:
            limit: Maximum number of records
            offset: Starting offset
            
        Returns:
            List of document dictionaries
        """
        session = self._get_session()
        try:
            docs = session.query(ProcessedDocument)\
                .order_by(ProcessedDocument.processed_at.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            return [doc.to_dict() for doc in docs]
        finally:
            session.close()
    
    def get_document_count(self) -> int:
        """Get total count of processed documents."""
        session = self._get_session()
        try:
            return session.query(ProcessedDocument).count()
        finally:
            session.close()
    
    def get_documents_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        session_hashes: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated documents with extracted data, sorted by most recently processed.
        
        Args:
            page: Page number (1-indexed)
            per_page: Number of records per page
            session_hashes: Optional list of file hashes to filter to current session only
            
        Returns:
            Tuple of (list of document dicts with extraction data, total record count)
        """
        session = self._get_session()
        try:
            # Build base query
            query = session.query(ProcessedDocument)
            
            # Filter by session hashes if provided
            if session_hashes:
                query = query.filter(ProcessedDocument.file_hash.in_(session_hashes))
            
            # Get total count
            total_count = query.count()
            
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Get paginated results ordered by most recent first
            docs = query.order_by(ProcessedDocument.processed_at.desc())\
                .limit(per_page)\
                .offset(offset)\
                .all()
            
            # Convert to dicts with extraction data parsed
            results = []
            for doc in docs:
                doc_dict = {
                    'id': doc.id,
                    'file_hash': doc.file_hash,
                    'FileName': doc.filename,
                    'source_type': doc.source_type,
                    'source_path': doc.source_path,
                    'file_size': doc.file_size,
                    'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                    'Status': doc.status.capitalize() if doc.status else 'Unknown',
                    'error_message': doc.error_message
                }
                
                # Parse extraction_data JSON if present
                if doc.extraction_data:
                    try:
                        extraction = json.loads(doc.extraction_data)
                        if isinstance(extraction, dict):
                            # Merge extraction data into doc_dict
                            doc_dict.update(extraction)
                    except json.JSONDecodeError:
                        pass
                
                results.append(doc_dict)
            
            return results, total_count
            
        finally:
            session.close()
    
    def delete_document(self, file_hash: str) -> bool:
        """
        Delete a document record by hash.
        
        Args:
            file_hash: SHA-256 hash string
            
        Returns:
            True if deleted successfully
        """
        session = self._get_session()
        try:
            doc = session.query(ProcessedDocument).filter_by(
                file_hash=file_hash
            ).first()
            
            if doc:
                session.delete(doc)
                session.commit()
                return True
            return False
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            session.close()
    
    def clear_all(self) -> bool:
        """
        Clear all document records. Use with caution!
        
        Returns:
            True if cleared successfully
        """
        session = self._get_session()
        try:
            session.query(ProcessedDocument).delete()
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            session.close()


# Factory function for easy instantiation with config
def create_dedup_service(config: Optional[Dict[str, Any]] = None) -> DedupService:
    """
    Create a DedupService instance from configuration.
    
    Args:
        config: Optional configuration dict with db_host, db_port, db_name, 
                db_user, db_password keys. Falls back to environment variables.
    
    Returns:
        Configured DedupService instance
    """
    if config:
        return DedupService(
            db_host=config.get('db_host', 'localhost'),
            db_port=config.get('db_port', 5432),
            db_name=config.get('db_name', 'document_registry'),
            db_user=config.get('db_user', 'docanalyzer'),
            db_password=config.get('db_password', 'docanalyzer_secret')
        )
    
    # Use environment variables / defaults
    return DedupService()
