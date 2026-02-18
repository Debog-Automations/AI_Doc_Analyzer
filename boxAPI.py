"""
Box API Client for accessing Box.com files and folders.

This module provides a BoxAPI class for:
- Client Credentials Grant (CCG) authentication
- Folder path resolution
- Listing files in folders with pagination
- Downloading files for AI processing
"""

from box_sdk_gen import BoxCCGAuth, BoxClient, CCGConfig, BoxAPIError, BoxDeveloperTokenAuth
from typing import Optional, Generator, List, Dict
import os

from logger import get_logger

logger = get_logger(__name__)


class BoxAPI:
    """
    Box API client for server-to-server authentication and file operations.
    
    Supports:
    - Client Credentials Grant (CCG) authentication
    - Folder path resolution
    - Paginated file listing
    - File downloads for AI processing
    """
    
    def __init__(
        self, 
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        user_id: Optional[str] = None,
        developer_token: Optional[str] = None
    ):
        """
        Initialize Box API client with CCG or Developer Token authentication.
        
        Args:
            client_id: Box application client ID (required for CCG auth)
            client_secret: Box application client secret (required for CCG auth)
            enterprise_id: Enterprise ID for service account authentication
            user_id: User ID for user-level authentication (alternative to enterprise_id)
            developer_token: Developer token for quick testing (valid 60 min, no Enterprise needed)
            
        Note: 
            - For developer token auth: provide only developer_token
            - For enterprise/service account auth: provide client_id, client_secret, enterprise_id
            - For user-level auth: provide client_id, client_secret, user_id
            - If both enterprise_id and user_id are provided, enterprise_id takes precedence
        
        Raises:
            ValueError: If required credentials are not provided
        """
        self._developer_token = developer_token
        
        # If using developer token, skip CCG credential validation
        if not developer_token:
            if not client_id or not client_secret:
                raise ValueError("Both client_id and client_secret must be provided (or use developer_token)")
            
            if not enterprise_id and not user_id:
                raise ValueError("Either enterprise_id or user_id must be provided (or use developer_token)")
        
        self._client_id = client_id
        self._client_secret = client_secret
        self._enterprise_id = enterprise_id
        self._user_id = user_id
        self._auth = None
        self._client = None
        
        # Authenticate
        self.authenticate()
    
    def authenticate(self) -> BoxClient:
        """
        Authenticate using Developer Token or Client Credentials Grant.
        
        Returns:
            Authenticated Box Client instance
            
        Raises:
            RuntimeError: If authentication fails
        """
        try:
            if self._developer_token:
                # Developer Token authentication (for testing, valid 60 min)
                self._auth = BoxDeveloperTokenAuth(token=self._developer_token)
                self._client = BoxClient(auth=self._auth)
            elif self._enterprise_id:
                # Enterprise/Service Account CCG authentication
                config = CCGConfig(
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    enterprise_id=self._enterprise_id
                )
                self._auth = BoxCCGAuth(config=config)
                self._client = BoxClient(auth=self._auth)
            else:
                # User-level CCG authentication
                config = CCGConfig(
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    user_id=self._user_id
                )
                self._auth = BoxCCGAuth(config=config)
                self._client = BoxClient(auth=self._auth)
            
            # Test authentication by getting current user
            self._client.users.get_user_me()
            return self._client
        except BoxAPIError as e:
            raise RuntimeError(f"Box authentication failed: {e}") from e
    
    def get_folder_id_from_path(self, folder_path: str) -> str:
        """
        Resolve folder path string to folder ID.
        
        Args:
            folder_path: Absolute folder path (e.g., "/Documents/MyFolder")
                        Use "/" for root folder
        
        Returns:
            Folder ID as string
            
        Raises:
            ValueError: If folder path doesn't exist
            BoxAPIError: If API call fails
        """
        if not self._client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        # Handle root folder
        if folder_path == "/" or folder_path == "":
            return "0"
        
        # Start from root folder
        folder_id = "0"
        
        # Split path into segments, removing empty strings
        path_segments = [seg for seg in folder_path.strip("/").split("/") if seg]
        
        for segment in path_segments:
            try:
                # Get items in current folder
                items_result = self._client.folders.get_folder_items(folder_id)
                entries = items_result.entries or []
                
                # Search for folder with matching name
                folder_found = False
                for item in entries:
                    if item.type.value == "folder" and item.name == segment:
                        folder_id = item.id
                        folder_found = True
                        break
                
                if not folder_found:
                    raise ValueError(
                        f"Folder '{segment}' not found in path '{folder_path}'. "
                        f"Available folders in parent: {[i.name for i in entries if i.type.value == 'folder']}"
                    )
            except BoxAPIError as e:
                raise BoxAPIError(f"Error accessing folder '{segment}': {e}") from e
        
        return folder_id
    
    def get_file_id_from_path(self, file_path: str) -> str:
        """
        Resolve file path string to file ID.
        
        Args:
            file_path: Absolute file path (e.g., "/Documents/MyFolder/file.pdf")
        
        Returns:
            File ID as string
            
        Raises:
            ValueError: If file path doesn't exist
            BoxAPIError: If API call fails
        """
        if not self._client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        # Split path into folder path and filename
        path_parts = file_path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(f"Invalid file path: {file_path}. Must include at least folder and filename.")
        
        filename = path_parts[-1]
        folder_path = "/" + "/".join(path_parts[:-1])
        
        # Get folder ID
        folder_id = self.get_folder_id_from_path(folder_path)
        
        # Get items in folder
        items_result = self._client.folders.get_folder_items(folder_id)
        entries = items_result.entries or []
        
        # Search for file with matching name
        for item in entries:
            if item.type.value == "file" and item.name == filename:
                return item.id
        
        raise ValueError(
            f"File '{filename}' not found in folder '{folder_path}'. "
            f"Available files: {[i.name for i in entries if i.type.value == 'file']}"
        )
    
    def get_documents(
        self, 
        folder_path: str, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Dict]:
        """
        Get all documents (files) from folder with pagination.
        
        Args:
            folder_path: Absolute folder path (e.g., "/Documents/MyFolder")
            limit: Number of items per page (default: 100, max: 1000)
            offset: Starting offset for pagination (default: 0)
        
        Returns:
            List of file dictionaries with full metadata:
            - id: File ID
            - name: File name
            - type: Item type (always "file")
            - size: File size in bytes
            - modified_at: Last modified timestamp
            - created_at: Creation timestamp
            - sha1: File SHA1 hash
            - etag: File etag
            - parent: Parent folder info
            
        Raises:
            ValueError: If folder path doesn't exist
            BoxAPIError: If API call fails
        """
        if not self._client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        # Resolve folder path to ID
        folder_id = self.get_folder_id_from_path(folder_path)
        
        all_files = []
        current_offset = offset
        
        while True:
            try:
                # Get items in folder with explicit fields for full metadata
                # Box API returns "mini" representation by default, so we must specify fields
                items_result = self._client.folders.get_folder_items(
                    folder_id, 
                    limit=limit, 
                    offset=current_offset,
                    fields=["id", "name", "type", "size", "modified_at", "created_at", "sha1", "etag", "parent"]
                )
                entries = items_result.entries or []
                
                # Filter to only files and convert to dictionaries
                batch_files = []
                for item in entries:
                    if item.type.value == "file":
                        file_dict = {
                            "id": item.id,
                            "name": item.name,
                            "type": item.type.value,
                            "size": getattr(item, 'size', None),
                            "modified_at": item.modified_at.isoformat() if getattr(item, 'modified_at', None) else None,
                            "created_at": item.created_at.isoformat() if getattr(item, 'created_at', None) else None,
                            "sha1": getattr(item, 'sha1', None),
                            "etag": getattr(item, 'etag', None),
                            "parent": {
                                "id": item.parent.id if getattr(item, 'parent', None) else None,
                                "name": item.parent.name if getattr(item, 'parent', None) else None,
                            } if getattr(item, 'parent', None) else None,
                        }
                        batch_files.append(file_dict)
                
                all_files.extend(batch_files)
                
                # Check if there are more items
                if len(entries) < limit:
                    break
                
                current_offset += limit
                
            except BoxAPIError as e:
                raise BoxAPIError(f"Error listing files in folder: {e}") from e
        
        return all_files
    
    def get_documents_paginated(
        self, 
        folder_path: str, 
        limit: int = 100
    ) -> Generator[List[Dict], None, None]:
        """
        Get documents as a generator for memory-efficient pagination.
        
        Args:
            folder_path: Absolute folder path (e.g., "/Documents/MyFolder")
            limit: Number of items per page (default: 100, max: 1000)
        
        Yields:
            Batches of file dictionaries (same format as get_documents)
        
        Raises:
            ValueError: If folder path doesn't exist
            BoxAPIError: If API call fails
        """
        if not self._client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        # Resolve folder path to ID
        folder_id = self.get_folder_id_from_path(folder_path)
        
        current_offset = 0
        
        while True:
            try:
                # Get items in folder with explicit fields for full metadata
                # Box API returns "mini" representation by default, so we must specify fields
                items_result = self._client.folders.get_folder_items(
                    folder_id, 
                    limit=limit, 
                    offset=current_offset,
                    fields=["id", "name", "type", "size", "modified_at", "created_at", "sha1", "etag", "parent"]
                )
                entries = items_result.entries or []
                
                # Filter to only files and convert to dictionaries
                batch_files = []
                for item in entries:
                    if item.type.value == "file":
                        file_dict = {
                            "id": item.id,
                            "name": item.name,
                            "type": item.type.value,
                            "size": getattr(item, 'size', None),
                            "modified_at": item.modified_at.isoformat() if getattr(item, 'modified_at', None) else None,
                            "created_at": item.created_at.isoformat() if getattr(item, 'created_at', None) else None,
                            "sha1": getattr(item, 'sha1', None),
                            "etag": getattr(item, 'etag', None),
                            "parent": {
                                "id": item.parent.id if getattr(item, 'parent', None) else None,
                                "name": item.parent.name if getattr(item, 'parent', None) else None,
                            } if getattr(item, 'parent', None) else None,
                        }
                        batch_files.append(file_dict)
                
                if batch_files:
                    yield batch_files
                
                # Check if there are more items
                if len(entries) < limit:
                    break
                
                current_offset += limit
                
            except BoxAPIError as e:
                raise BoxAPIError(f"Error listing files in folder: {e}") from e
    
    def download_file(
        self, 
        file_id: str, 
        save_path: Optional[str] = None
    ) -> bytes:
        """
        Download file content from Box by file ID.
        
        Args:
            file_id: Box file ID
            save_path: Optional path to save file. If None, file is not saved to disk.
        
        Returns:
            File contents as bytes (suitable for passing to AI models)
            
        Raises:
            BoxAPIError: If file download fails
        """
        if not self._client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        try:
            # Download file content (returns BufferedIOBase stream)
            file_stream = self._client.downloads.download_file(file_id)
            file_content = file_stream.read() if file_stream else b''
            
            # Save to disk if path provided
            if save_path:
                os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(file_content)
            
            return file_content
            
        except BoxAPIError as e:
            raise BoxAPIError(f"Error downloading file {file_id}: {e}") from e
    
    def download_file_by_path(
        self, 
        file_path: str, 
        save_path: Optional[str] = None
    ) -> bytes:
        """
        Download file content from Box by file path.
        
        Args:
            file_path: Absolute file path (e.g., "/Documents/MyFolder/file.pdf")
            save_path: Optional path to save file. If None, file is not saved to disk.
        
        Returns:
            File contents as bytes (suitable for passing to AI models)
            
        Raises:
            ValueError: If file path doesn't exist
            BoxAPIError: If file download fails
        """
        # Resolve file path to file ID
        file_id = self.get_file_id_from_path(file_path)
        
        # Download using file ID
        return self.download_file(file_id, save_path)


if __name__ == "__main__":
    from dotenv import load_dotenv 
    load_dotenv()
    
    # Option 1: Developer Token (for testing, valid 60 minutes)
    # Get token from Box Developer Console > Your App > Configuration > Developer Token
    developer_token = os.getenv("BOX_DEVELOPER_TOKEN")
    
    if developer_token:
        # Use developer token (no Enterprise account needed)
        box_api = BoxAPI(developer_token=developer_token)
    else:
        # Option 2: CCG authentication (requires Enterprise account)
        box_api = BoxAPI(
            client_id=os.getenv("BOX_CLIENT_ID"),
            client_secret=os.getenv("BOX_CLIENT_SECRET"),
            user_id=os.getenv("BOX_USER_ID")
        )
    
    print(box_api.get_documents("/"))