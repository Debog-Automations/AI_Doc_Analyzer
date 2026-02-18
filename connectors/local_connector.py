"""
Local Connector - Access local file system
"""

import os
import mimetypes
from datetime import datetime
from typing import List, Optional

from .base_connector import BaseConnector, FileInfo, FolderInfo


class LocalConnector(BaseConnector):
    """Connector for accessing local file system."""
    
    source_type = "local"
    
    def __init__(self, base_path: str = ""):
        """
        Initialize local connector.
        
        Args:
            base_path: Optional base path to use as root
        """
        self.base_path = base_path
        self._connected = True  # Local is always "connected"
    
    def connect(self) -> bool:
        """Local filesystem is always connected."""
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """No-op for local filesystem."""
        pass
    
    def is_connected(self) -> bool:
        """Always returns True for local filesystem."""
        return self._connected
    
    def _resolve_path(self, path: str) -> str:
        """Resolve path relative to base_path."""
        if self.base_path:
            if path.startswith("/"):
                path = path[1:]
            return os.path.join(self.base_path, path)
        return path
    
    def list_folders(self, path: str = "/") -> List[FolderInfo]:
        """List folders at the given path."""
        resolved_path = self._resolve_path(path)
        
        if not os.path.exists(resolved_path):
            return []
        
        folders = []
        try:
            for entry in os.scandir(resolved_path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    folders.append(FolderInfo(
                        id=entry.path,
                        name=entry.name,
                        path=entry.path,
                        source_type=self.source_type,
                        parent_path=resolved_path,
                        has_children=any(
                            e.is_dir() or e.is_file() 
                            for e in os.scandir(entry.path)
                        ) if os.access(entry.path, os.R_OK) else False
                    ))
        except PermissionError:
            pass
        
        return sorted(folders, key=lambda f: f.name.lower())
    
    def list_files(
        self, 
        path: str = "/",
        extensions: Optional[List[str]] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """List files at the given path."""
        resolved_path = self._resolve_path(path)
        
        if not os.path.exists(resolved_path):
            return []
        
        files = []
        
        def process_directory(dir_path: str):
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        
                        # Filter by extensions if specified
                        if extensions and ext not in extensions:
                            continue
                        
                        stat = entry.stat()
                        files.append(FileInfo(
                            id=entry.path,
                            name=entry.name,
                            path=entry.path,
                            size=stat.st_size,
                            modified_at=datetime.fromtimestamp(stat.st_mtime),
                            created_at=datetime.fromtimestamp(stat.st_ctime),
                            source_type=self.source_type,
                            mime_type=mimetypes.guess_type(entry.name)[0],
                            parent_path=dir_path
                        ))
                    elif entry.is_dir() and recursive and not entry.name.startswith('.'):
                        process_directory(entry.path)
            except PermissionError:
                pass
        
        process_directory(resolved_path)
        return sorted(files, key=lambda f: f.name.lower())
    
    def download_file(self, file_id: str, save_path: str) -> str:
        """
        Copy a local file to another location.
        
        For local files, file_id is the source path.
        """
        import shutil
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        shutil.copy2(file_id, save_path)
        return save_path
    
    def get_file_content(self, file_id: str) -> bytes:
        """Get file content as bytes."""
        with open(file_id, 'rb') as f:
            return f.read()
    
    def get_file_info(self, file_id: str) -> Optional[FileInfo]:
        """Get information about a specific file."""
        if not os.path.exists(file_id) or not os.path.isfile(file_id):
            return None
        
        stat = os.stat(file_id)
        return FileInfo(
            id=file_id,
            name=os.path.basename(file_id),
            path=file_id,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            created_at=datetime.fromtimestamp(stat.st_ctime),
            source_type=self.source_type,
            mime_type=mimetypes.guess_type(file_id)[0],
            parent_path=os.path.dirname(file_id)
        )

