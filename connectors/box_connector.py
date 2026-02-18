"""
Box Connector - Access Box.com cloud storage

Wraps the existing BoxAPI class with the BaseConnector interface.
Supports Developer Token (for quick testing) or Client Credentials Grant (CCG) authentication.
"""

import os
import tempfile
from datetime import datetime
from typing import List, Optional

from .base_connector import BaseConnector, FileInfo, FolderInfo

# Import the existing BoxAPI
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from boxAPI import BoxAPI
from logger import get_logger

logger = get_logger(__name__)


class BoxConnector(BaseConnector):
    """Connector for accessing Box.com cloud storage using Developer Token or CCG authentication."""
    
    source_type = "box"
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.xlsx', '.xlsm', '.xls', '.docx', '.png', '.jpg', '.jpeg', '.tiff'}
    
    def __init__(
        self, 
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        user_id: Optional[str] = None,
        developer_token: Optional[str] = None
    ):
        """
        Initialize Box connector with Developer Token or CCG authentication credentials.
        
        Args:
            client_id: Box application client ID (for CCG auth)
            client_secret: Box application client secret (for CCG auth)
            enterprise_id: Enterprise ID for service account authentication (for CCG auth)
            user_id: User ID for user-level authentication (alternative to enterprise_id, for CCG auth)
            developer_token: Developer token for quick testing (valid 60 min, takes priority over CCG)
        """
        self.developer_token = developer_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.enterprise_id = enterprise_id
        self.user_id = user_id
        self._box_api: Optional[BoxAPI] = None
        self._connected = False
        self._temp_dir = tempfile.mkdtemp(prefix="box_downloads_")
    
    def connect(self) -> bool:
        """Establish connection to Box using Developer Token or CCG authentication."""
        try:
            if self.developer_token:
                # Use developer token (takes priority)
                self._box_api = BoxAPI(developer_token=self.developer_token)
            else:
                # Use CCG authentication
                self._box_api = BoxAPI(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    enterprise_id=self.enterprise_id,
                    user_id=self.user_id
                )
            
            self._connected = True
            logger.info("Box connection established successfully")
            return True
        except Exception as e:
            logger.error(f"Box connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Box."""
        self._box_api = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if currently connected to Box."""
        return self._connected and self._box_api is not None
    
    def _ensure_connected(self):
        """Ensure we're connected before operations."""
        if not self.is_connected():
            raise ConnectionError("Not connected to Box. Call connect() first.")
    
    def list_folders(self, path: str = "/") -> List[FolderInfo]:
        """List folders at the given path in Box."""
        self._ensure_connected()
        
        try:
            # Get folder ID from path
            folder_id = self._box_api.get_folder_id_from_path(path)
            
            # Get folder items using box_sdk_gen API
            items_result = self._box_api._client.folders.get_folder_items(folder_id)
            entries = items_result.entries or []
            
            folders = []
            for item in entries:
                if item.type.value == "folder":
                    folder_path = f"{path.rstrip('/')}/{item.name}"
                    folders.append(FolderInfo(
                        id=item.id,
                        name=item.name,
                        path=folder_path,
                        source_type=self.source_type,
                        parent_path=path,
                        has_children=True  # Assume folders have children
                    ))
            
            logger.debug(f"Listed {len(folders)} folders in path: {path}")
            return sorted(folders, key=lambda f: f.name.lower())
            
        except Exception as e:
            logger.error(f"Error listing Box folders at '{path}': {e}")
            return []
    
    def list_files(
        self, 
        path: str = "/",
        extensions: Optional[List[str]] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """List files at the given path in Box."""
        self._ensure_connected()
        
        if extensions is None:
            extensions = list(self.SUPPORTED_EXTENSIONS)
        
        try:
            # Get documents from Box API
            docs = self._box_api.get_documents(path)
            
            files = []
            for doc in docs:
                ext = os.path.splitext(doc['name'])[1].lower()
                
                # Filter by extensions
                if extensions and ext not in extensions:
                    continue
                
                file_path = f"{path.rstrip('/')}/{doc['name']}"
                
                # Parse dates
                modified_at = None
                created_at = None
                if doc.get('modified_at'):
                    try:
                        modified_at = datetime.fromisoformat(doc['modified_at'].replace('Z', '+00:00'))
                    except:
                        pass
                if doc.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00'))
                    except:
                        pass
                
                files.append(FileInfo(
                    id=doc['id'],
                    name=doc['name'],
                    path=file_path,
                    size=doc.get('size') or 0,  # Handle both missing key and None value
                    modified_at=modified_at,
                    created_at=created_at,
                    source_type=self.source_type,
                    hash=doc.get('sha1'),
                    parent_path=path,
                    metadata={
                        'etag': doc.get('etag'),
                        'parent_id': doc.get('parent', {}).get('id') if doc.get('parent') else None
                    }
                ))
            
            # Recursively get files from subfolders if requested
            if recursive:
                subfolders = self.list_folders(path)
                for subfolder in subfolders:
                    files.extend(self.list_files(subfolder.path, extensions, recursive=True))
            
            logger.debug(f"Listed {len(files)} files in path: {path}")
            return sorted(files, key=lambda f: f.name.lower())
            
        except Exception as e:
            logger.error(f"Error listing Box files at '{path}': {e}")
            return []
    
    def download_file(self, file_id: str, save_path: str) -> str:
        """Download a file from Box to local storage."""
        self._ensure_connected()
        
        try:
            os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
            self._box_api.download_file(file_id, save_path)
            return save_path
        except Exception as e:
            raise IOError(f"Failed to download file {file_id}: {e}")
    
    def download_file_to_temp(self, file_id: str, filename: str) -> str:
        """
        Download a file to a temporary directory.
        
        Args:
            file_id: Box file ID
            filename: Filename to use for the downloaded file
            
        Returns:
            Path to downloaded file
        """
        save_path = os.path.join(self._temp_dir, filename)
        return self.download_file(file_id, save_path)
    
    def get_file_content(self, file_id: str) -> bytes:
        """Get file content as bytes without saving to disk."""
        self._ensure_connected()
        
        try:
            return self._box_api.download_file(file_id)
        except Exception as e:
            raise IOError(f"Failed to get file content {file_id}: {e}")
    
    def get_file_info(self, file_id: str) -> Optional[FileInfo]:
        """Get information about a specific file."""
        self._ensure_connected()
        
        try:
            # Use box_sdk_gen API
            file_obj = self._box_api._client.files.get_file_by_id(file_id)
            
            modified_at = None
            created_at = None
            if file_obj.modified_at:
                modified_at = file_obj.modified_at
            if file_obj.created_at:
                created_at = file_obj.created_at
            
            parent_path = "/"
            if file_obj.parent:
                parent_path = f"/{file_obj.parent.name}"
            
            return FileInfo(
                id=file_obj.id,
                name=file_obj.name,
                path=f"{parent_path}/{file_obj.name}",
                size=getattr(file_obj, 'size', None) or 0,  # Handle None size
                modified_at=modified_at,
                created_at=created_at,
                source_type=self.source_type,
                hash=getattr(file_obj, 'sha1', None),
                parent_path=parent_path,
                metadata={
                    'etag': getattr(file_obj, 'etag', None)
                }
            )
        except Exception as e:
            logger.error(f"Error getting file info for file_id '{file_id}': {e}")
            return None
    
    def get_folder_tree(self, path: str = "/", max_depth: int = 3) -> dict:
        """
        Get a tree structure of folders for UI display.
        
        Args:
            path: Starting path
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary representing folder tree
        """
        self._ensure_connected()
        
        def build_tree(current_path: str, depth: int) -> dict:
            if depth > max_depth:
                return {"folders": [], "truncated": True}
            
            folders = self.list_folders(current_path)
            return {
                "path": current_path,
                "folders": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "path": f.path,
                        "children": build_tree(f.path, depth + 1) if f.has_children else None
                    }
                    for f in folders
                ],
                "truncated": False
            }
        
        return build_tree(path, 1)
    
    def cleanup_temp_files(self):
        """Clean up temporary downloaded files."""
        import shutil
        try:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = tempfile.mkdtemp(prefix="box_downloads_")
        except:
            pass
