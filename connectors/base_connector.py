"""
Base Connector - Abstract interface for all document source connectors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Generator
from datetime import datetime


@dataclass
class FileInfo:
    """Information about a file from any source."""
    id: str  # Unique identifier (path for local, ID for cloud)
    name: str
    path: str  # Full path or source path
    size: int  # Size in bytes
    modified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    source_type: str = "unknown"  # "local", "box", "sharepoint", etc.
    mime_type: Optional[str] = None
    hash: Optional[str] = None  # SHA1 or similar if available
    parent_path: Optional[str] = None
    metadata: Optional[dict] = None  # Additional source-specific metadata
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_type": self.source_type,
            "mime_type": self.mime_type,
            "hash": self.hash,
            "parent_path": self.parent_path,
            "metadata": self.metadata
        }


@dataclass
class FolderInfo:
    """Information about a folder from any source."""
    id: str
    name: str
    path: str
    source_type: str = "unknown"
    parent_path: Optional[str] = None
    has_children: bool = False


class BaseConnector(ABC):
    """
    Abstract base class for document source connectors.
    
    All connectors must implement these methods to provide a consistent
    interface for browsing and downloading files from different sources.
    """
    
    source_type: str = "unknown"
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the source.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the source."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected to the source."""
        pass
    
    @abstractmethod
    def list_folders(self, path: str = "/") -> List[FolderInfo]:
        """
        List folders at the given path.
        
        Args:
            path: Path to list folders from (default: root)
            
        Returns:
            List of FolderInfo objects
        """
        pass
    
    @abstractmethod
    def list_files(
        self, 
        path: str = "/",
        extensions: Optional[List[str]] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """
        List files at the given path.
        
        Args:
            path: Path to list files from
            extensions: Optional list of extensions to filter (e.g., ['.pdf', '.xlsx'])
            recursive: Whether to include files in subfolders
            
        Returns:
            List of FileInfo objects
        """
        pass
    
    @abstractmethod
    def download_file(self, file_id: str, save_path: str) -> str:
        """
        Download a file to local storage.
        
        Args:
            file_id: Unique identifier for the file
            save_path: Local path to save the file
            
        Returns:
            Path to downloaded file
        """
        pass
    
    @abstractmethod
    def get_file_content(self, file_id: str) -> bytes:
        """
        Get file content as bytes without saving to disk.
        
        Args:
            file_id: Unique identifier for the file
            
        Returns:
            File content as bytes
        """
        pass
    
    def get_file_info(self, file_id: str) -> Optional[FileInfo]:
        """
        Get information about a specific file.
        
        Args:
            file_id: Unique identifier for the file
            
        Returns:
            FileInfo object or None if not found
        """
        # Default implementation - can be overridden for efficiency
        return None

