"""Base classes for storage destinations"""

from abc import ABC, abstractmethod
from typing import Dict, Any, BinaryIO, Optional
from pathlib import Path


class StorageDestination(ABC):
    """Abstract base class for storage destinations"""
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialize the destination with configuration"""
        self.config = config
    
    @abstractmethod
    def save_file(self, file_path: str, content_stream: BinaryIO, 
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save a file to the destination
        
        Args:
            file_path: Path where the file should be saved
            content_stream: Stream containing the file content
            metadata: Optional metadata to associate with the file
            
        Returns:
            True if save was successful
        """
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if a file already exists at the destination
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    def create_directory(self, directory_path: str) -> bool:
        """Create a directory at the destination
        
        Args:
            directory_path: Path of the directory to create
            
        Returns:
            True if directory was created or already exists
        """
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the destination
        
        Args:
            file_path: Path of the file to delete
            
        Returns:
            True if file was deleted successfully
        """
        pass
    
    @abstractmethod
    def get_full_path(self, relative_path: str) -> str:
        """Get the full path for a given relative path
        
        Args:
            relative_path: Relative path to convert
            
        Returns:
            Full path at the destination
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the destination configuration
        
        Returns:
            True if configuration is valid
        """
        pass