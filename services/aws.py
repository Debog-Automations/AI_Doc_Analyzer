"""
AWS Service - Integration with RDS PostgreSQL and S3

Provides:
- RDS PostgreSQL connection for extracted data storage
- S3 uploads for original document copies
- Migration from SQLite to PostgreSQL
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


class DocumentRecord(Base):
    """PostgreSQL model for document records."""
    
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_path = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)  # S3 object key
    file_size = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='completed')
    error_message = Column(Text, nullable=True)


class ExtractionRecord(Base):
    """PostgreSQL model for extraction results."""
    
    __tablename__ = 'extractions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    extracted_data = Column(JSONB, nullable=True)
    ai_model = Column(String(100), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    retries = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AWSService:
    """
    AWS integration service for RDS PostgreSQL and S3.
    """
    
    def __init__(
        self,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: str = "us-east-1",
        s3_bucket: Optional[str] = None,
        rds_host: Optional[str] = None,
        rds_port: int = 5432,
        rds_database: str = "docanalyzer",
        rds_username: str = "postgres",
        rds_password: Optional[str] = None
    ):
        """
        Initialize AWS service.
        
        Args:
            aws_access_key: AWS access key ID
            aws_secret_key: AWS secret access key
            aws_region: AWS region
            s3_bucket: S3 bucket name
            rds_host: RDS hostname
            rds_port: RDS port (default 5432)
            rds_database: Database name
            rds_username: Database username
            rds_password: Database password
        """
        self.aws_access_key = aws_access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self.s3_bucket = s3_bucket or os.getenv("AWS_S3_BUCKET")
        self.rds_host = rds_host or os.getenv("AWS_RDS_HOST")
        self.rds_port = rds_port
        self.rds_database = rds_database or os.getenv("AWS_RDS_DATABASE", "docanalyzer")
        self.rds_username = rds_username or os.getenv("AWS_RDS_USERNAME", "postgres")
        self.rds_password = rds_password or os.getenv("AWS_RDS_PASSWORD")
        
        self._s3_client = None
        self._db_engine = None
        self._Session = None
    
    # ==================== S3 METHODS ====================
    
    def _get_s3_client(self):
        """Get or create S3 client."""
        if self._s3_client is None:
            if self.aws_access_key and self.aws_secret_key:
                self._s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.aws_region
                )
            else:
                # Use default credentials (IAM role, env vars, etc.)
                self._s3_client = boto3.client('s3', region_name=self.aws_region)
        return self._s3_client
    
    def upload_to_s3(
        self,
        file_path: str,
        s3_key: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a file to S3.
        
        Args:
            file_path: Local file path
            s3_key: S3 object key. If not provided, generates from date/filename.
            metadata: Optional metadata to attach to the object.
            
        Returns:
            S3 object key
        """
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        
        s3 = self._get_s3_client()
        
        # Generate S3 key if not provided
        if not s3_key:
            filename = os.path.basename(file_path)
            date_prefix = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"documents/{date_prefix}/{filename}"
        
        # Prepare extra args
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
        
        try:
            s3.upload_file(file_path, self.s3_bucket, s3_key, ExtraArgs=extra_args if extra_args else None)
            return s3_key
        except ClientError as e:
            raise IOError(f"Failed to upload to S3: {e}")
    
    def download_from_s3(self, s3_key: str, local_path: str) -> str:
        """
        Download a file from S3.
        
        Args:
            s3_key: S3 object key
            local_path: Local path to save file
            
        Returns:
            Local file path
        """
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        
        s3 = self._get_s3_client()
        
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            s3.download_file(self.s3_bucket, s3_key, local_path)
            return local_path
        except ClientError as e:
            raise IOError(f"Failed to download from S3: {e}")
    
    def list_s3_objects(self, prefix: str = "documents/") -> List[dict]:
        """
        List objects in S3 bucket.
        
        Args:
            prefix: S3 key prefix to filter
            
        Returns:
            List of object metadata dicts
        """
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        
        s3 = self._get_s3_client()
        
        objects = []
        paginator = s3.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })
            return objects
        except ClientError as e:
            raise IOError(f"Failed to list S3 objects: {e}")
    
    # ==================== RDS METHODS ====================
    
    def _get_db_engine(self):
        """Get or create database engine."""
        if self._db_engine is None:
            if not self.rds_host:
                raise ValueError("RDS host not configured")
            
            connection_string = (
                f"postgresql://{self.rds_username}:{self.rds_password}"
                f"@{self.rds_host}:{self.rds_port}/{self.rds_database}"
            )
            
            self._db_engine = create_engine(connection_string, echo=False)
            
            # Create tables if they don't exist
            Base.metadata.create_all(self._db_engine)
            
            self._Session = sessionmaker(bind=self._db_engine)
        
        return self._db_engine
    
    def _get_session(self) -> Session:
        """Get a database session."""
        self._get_db_engine()
        return self._Session()
    
    def save_document(
        self,
        file_hash: str,
        filename: str,
        source_type: str,
        source_path: str = None,
        s3_key: str = None,
        file_size: int = None,
        status: str = "completed",
        error_message: str = None
    ) -> int:
        """
        Save document record to RDS.
        
        Returns:
            Document ID
        """
        session = self._get_session()
        
        try:
            # Check if exists
            existing = session.query(DocumentRecord).filter_by(file_hash=file_hash).first()
            
            if existing:
                existing.processed_at = datetime.utcnow()
                existing.status = status
                existing.s3_key = s3_key or existing.s3_key
                existing.error_message = error_message
                session.commit()
                return existing.id
            
            doc = DocumentRecord(
                file_hash=file_hash,
                filename=filename,
                source_type=source_type,
                source_path=source_path,
                s3_key=s3_key,
                file_size=file_size,
                status=status,
                error_message=error_message
            )
            session.add(doc)
            session.commit()
            return doc.id
            
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def save_extraction(
        self,
        document_id: int,
        extracted_data: dict,
        ai_model: str = "gpt-4o",
        processing_time_ms: int = None,
        retries: int = 0
    ) -> int:
        """
        Save extraction results to RDS.
        
        Returns:
            Extraction ID
        """
        session = self._get_session()
        
        try:
            extraction = ExtractionRecord(
                document_id=document_id,
                extracted_data=extracted_data,
                ai_model=ai_model,
                processing_time_ms=processing_time_ms,
                retries=retries
            )
            session.add(extraction)
            session.commit()
            return extraction.id
            
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_document_by_hash(self, file_hash: str) -> Optional[dict]:
        """Get document record by hash."""
        session = self._get_session()
        
        try:
            doc = session.query(DocumentRecord).filter_by(file_hash=file_hash).first()
            if doc:
                return {
                    'id': doc.id,
                    'file_hash': doc.file_hash,
                    'filename': doc.filename,
                    'source_type': doc.source_type,
                    'source_path': doc.source_path,
                    's3_key': doc.s3_key,
                    'file_size': doc.file_size,
                    'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                    'status': doc.status
                }
            return None
        finally:
            session.close()
    
    def get_all_documents(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get all document records."""
        session = self._get_session()
        
        try:
            docs = session.query(DocumentRecord)\
                .order_by(DocumentRecord.processed_at.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            
            return [{
                'id': doc.id,
                'file_hash': doc.file_hash,
                'filename': doc.filename,
                'source_type': doc.source_type,
                's3_key': doc.s3_key,
                'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                'status': doc.status
            } for doc in docs]
        finally:
            session.close()
    
    def get_extractions_for_document(self, document_id: int) -> List[dict]:
        """Get all extractions for a document."""
        session = self._get_session()
        
        try:
            extractions = session.query(ExtractionRecord)\
                .filter_by(document_id=document_id)\
                .order_by(ExtractionRecord.created_at.desc())\
                .all()
            
            return [{
                'id': ext.id,
                'document_id': ext.document_id,
                'extracted_data': ext.extracted_data,
                'ai_model': ext.ai_model,
                'processing_time_ms': ext.processing_time_ms,
                'retries': ext.retries,
                'created_at': ext.created_at.isoformat() if ext.created_at else None
            } for ext in extractions]
        finally:
            session.close()
    
    # ==================== CONVENIENCE METHODS ====================
    
    def process_and_store(
        self,
        file_path: str,
        file_hash: str,
        extracted_data: dict,
        source_type: str = "local",
        upload_to_s3: bool = True
    ) -> dict:
        """
        Complete storage workflow: upload to S3 and save to RDS.
        
        Args:
            file_path: Local file path
            file_hash: SHA-256 hash
            extracted_data: Extraction results
            source_type: Source type
            upload_to_s3: Whether to upload file to S3
            
        Returns:
            Dict with document_id, extraction_id, s3_key
        """
        s3_key = None
        
        # Upload to S3 if configured and requested
        if upload_to_s3 and self.s3_bucket:
            try:
                s3_key = self.upload_to_s3(
                    file_path,
                    metadata={'hash': file_hash, 'source_type': source_type}
                )
            except Exception as e:
                print(f"Warning: S3 upload failed: {e}")
        
        # Save document to RDS
        doc_id = self.save_document(
            file_hash=file_hash,
            filename=os.path.basename(file_path),
            source_type=source_type,
            source_path=file_path,
            s3_key=s3_key,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else None
        )
        
        # Save extraction
        ext_id = self.save_extraction(
            document_id=doc_id,
            extracted_data=extracted_data,
            retries=extracted_data.get('_ai_retries', 0)
        )
        
        return {
            'document_id': doc_id,
            'extraction_id': ext_id,
            's3_key': s3_key
        }
    
    def test_connection(self) -> dict:
        """
        Test AWS connections.
        
        Returns:
            Dict with connection status for each service
        """
        results = {}
        
        # Test S3
        if self.s3_bucket:
            try:
                s3 = self._get_s3_client()
                s3.head_bucket(Bucket=self.s3_bucket)
                results['s3'] = {'status': 'connected', 'bucket': self.s3_bucket}
            except Exception as e:
                results['s3'] = {'status': 'error', 'message': str(e)}
        else:
            results['s3'] = {'status': 'not_configured'}
        
        # Test RDS
        if self.rds_host:
            try:
                engine = self._get_db_engine()
                with engine.connect() as conn:
                    conn.execute("SELECT 1")
                results['rds'] = {'status': 'connected', 'host': self.rds_host}
            except Exception as e:
                results['rds'] = {'status': 'error', 'message': str(e)}
        else:
            results['rds'] = {'status': 'not_configured'}
        
        return results

