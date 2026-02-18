"""
File Hasher - Generate SHA-256 hashes for document deduplication
"""

import hashlib
from typing import Optional, BinaryIO
import os


class FileHasher:
    """
    Generates SHA-256 hashes for files.
    
    Used for deduplication - same content = same hash.
    """
    
    CHUNK_SIZE = 65536  # 64KB chunks for memory efficiency
    
    @staticmethod
    def hash_file(file_path: str) -> str:
        """
        Generate SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string (64 characters)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file can't be read
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(FileHasher.CHUNK_SIZE), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """
        Generate SHA-256 hash of bytes data.
        
        Args:
            data: Bytes to hash
            
        Returns:
            Hexadecimal hash string (64 characters)
        """
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def hash_stream(stream: BinaryIO) -> str:
        """
        Generate SHA-256 hash from a file-like stream.
        
        Args:
            stream: Binary file-like object
            
        Returns:
            Hexadecimal hash string (64 characters)
        """
        sha256_hash = hashlib.sha256()
        
        for chunk in iter(lambda: stream.read(FileHasher.CHUNK_SIZE), b""):
            sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def quick_hash(file_path: str, sample_size: int = 1024 * 1024) -> str:
        """
        Generate a quick hash using only the beginning and end of a file.
        
        Useful for very large files when full hash is too slow.
        Combines: file size + first N bytes + last N bytes.
        
        Args:
            file_path: Path to the file
            sample_size: Bytes to read from start and end (default: 1MB each)
            
        Returns:
            Hexadecimal hash string
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        sha256_hash = hashlib.sha256()
        
        # Include file size in hash
        sha256_hash.update(str(file_size).encode())
        
        with open(file_path, "rb") as f:
            # Read from beginning
            sha256_hash.update(f.read(sample_size))
            
            # If file is large enough, also read from end
            if file_size > sample_size * 2:
                f.seek(-sample_size, 2)  # Seek from end
                sha256_hash.update(f.read(sample_size))
        
        return sha256_hash.hexdigest()

