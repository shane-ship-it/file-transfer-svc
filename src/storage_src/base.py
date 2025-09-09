"""Base classes for storage providers"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, BinaryIO
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileMetadata:
    """Metadata for a file in storage"""
    name: str
    size: int
    last_modified: datetime
    content_type: Optional[str] = None
    etag: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StorageProvider(ABC):
    """Abstract base class for storage providers"""
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialize the provider with configuration"""
        self.config = config
    
    @abstractmethod
    def list_files(self, prefix: Optional[str] = None, 
                   max_results: Optional[int] = None) -> List[FileMetadata]:
        """List files in the storage
        
        Args:
            prefix: Optional prefix to filter files
            max_results: Maximum number of results to return
            
        Returns:
            List of FileMetadata objects
        """
        pass
    
    @abstractmethod
    def download_file(self, file_path: str, output_stream: BinaryIO) -> None:
        """Download a file from storage
        
        Args:
            file_path: Path to the file in storage
            output_stream: Stream to write the downloaded content
        """
        pass
    
    @abstractmethod
    def get_metadata(self, file_path: str) -> FileMetadata:
        """Get metadata for a specific file
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            FileMetadata object
        """
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if a file exists
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the provider configuration
        
        Returns:
            True if configuration is valid
        """
        pass
    
    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str, 
                   overwrite: bool = True) -> bool:
        """Upload a file to storage
        
        Args:
            local_path: Path to the local file
            remote_path: Path in storage (can include virtual directories)
            overwrite: Whether to overwrite if file exists
            
        Returns:
            True if upload was successful
        """
        pass
    
    @abstractmethod
    def create_folder(self, folder_path: str) -> bool:
        """Create a virtual folder in storage
        
        Args:
            folder_path: Path of the folder to create
            
        Returns:
            True if folder was created (note: in blob storage, folders are virtual)
        """
        pass