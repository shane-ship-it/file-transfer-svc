"""Local filesystem destination implementation"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, BinaryIO, Optional
import shutil
from datetime import datetime

from .base import StorageDestination

logger = logging.getLogger(__name__)


class LocalFileSystemDestination(StorageDestination):
    """Local filesystem storage destination"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize local filesystem destination
        
        Args:
            config: Configuration dict with keys:
                - base_path: Base directory for saving files
                - create_dirs: Whether to create directories if they don't exist (default: True)
                - use_datetime_folder: Whether to create datetime subfolder (default: True)
                - datetime_format: Format for datetime folder (default: '%Y%m%d_%H%M%S')
        """
        super().__init__(config)
        self.base_path = Path(config.get('base_path', './downloads'))
        self.create_dirs = config.get('create_dirs', True)
        self.use_datetime_folder = config.get('use_datetime_folder', True)
        self.datetime_format = config.get('datetime_format', '%Y%m%d_%H%M%S')
        
        # Create datetime folder if enabled
        if self.use_datetime_folder:
            datetime_str = datetime.now().strftime(self.datetime_format)
            self.session_path = self.base_path / datetime_str
        else:
            self.session_path = self.base_path
        
        # Create base directory if it doesn't exist and create_dirs is True
        if self.create_dirs and not self.session_path.exists():
            self.session_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created session directory: {self.session_path}")
    
    def save_file(self, file_path: str, content_stream: BinaryIO,
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save a file to the local filesystem
        
        Args:
            file_path: Relative path where the file should be saved
            content_stream: Stream containing the file content
            metadata: Optional metadata (not used for local filesystem)
            
        Returns:
            True if save was successful
        """
        try:
            full_path = self.get_full_path(file_path)
            
            # Create parent directories if needed
            parent_dir = full_path.parent
            if self.create_dirs and not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {parent_dir}")
            
            # Write file
            with open(full_path, 'wb') as f:
                shutil.copyfileobj(content_stream, f)
            
            logger.info(f"Saved file: {full_path}")
            
            # Optionally save metadata as a sidecar file
            if metadata:
                self._save_metadata(full_path, metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}")
            return False
    
    def exists(self, file_path: str) -> bool:
        """Check if a file exists on the local filesystem
        
        Args:
            file_path: Relative path to check
            
        Returns:
            True if file exists, False otherwise
        """
        full_path = self.get_full_path(file_path)
        return full_path.exists()
    
    def create_directory(self, directory_path: str) -> bool:
        """Create a directory on the local filesystem
        
        Args:
            directory_path: Relative path of the directory to create
            
        Returns:
            True if directory was created or already exists
        """
        try:
            full_path = self.get_full_path(directory_path)
            full_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating directory {directory_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the local filesystem
        
        Args:
            file_path: Relative path of the file to delete
            
        Returns:
            True if file was deleted successfully
        """
        try:
            full_path = self.get_full_path(file_path)
            if full_path.exists():
                if full_path.is_file():
                    full_path.unlink()
                    logger.info(f"Deleted file: {full_path}")
                    
                    # Also delete metadata file if it exists
                    metadata_path = Path(str(full_path) + '.metadata.json')
                    if metadata_path.exists():
                        metadata_path.unlink()
                        
                    return True
                else:
                    logger.warning(f"Path is not a file: {full_path}")
                    return False
            else:
                logger.warning(f"File does not exist: {full_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_full_path(self, relative_path: str) -> Path:
        """Get the full path for a given relative path
        
        Args:
            relative_path: Relative path to convert
            
        Returns:
            Full path on the local filesystem
        """
        # Remove leading slash if present
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]
        
        return self.session_path / relative_path
    
    def validate_config(self) -> bool:
        """Validate local filesystem configuration
        
        Returns:
            True if configuration is valid
        """
        try:
            # Check if session path exists or can be created
            if not self.session_path.exists():
                if self.create_dirs:
                    # Try to create the directory
                    self.session_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created session directory: {self.session_path}")
                else:
                    logger.error(f"Session path does not exist: {self.session_path}")
                    return False
            
            # Check if we have write permissions
            test_file = self.session_path / '.test_write'
            try:
                test_file.touch()
                test_file.unlink()
                logger.info("Local filesystem configuration validated successfully")
                return True
            except Exception as e:
                logger.error(f"No write permission for session path: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Invalid local filesystem configuration: {e}")
            return False
    
    def _save_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> None:
        """Save metadata as a JSON sidecar file
        
        Args:
            file_path: Path to the main file
            metadata: Metadata to save
        """
        try:
            import json
            metadata_path = Path(str(file_path) + '.metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.debug(f"Saved metadata for {file_path}")
        except Exception as e:
            logger.warning(f"Could not save metadata: {e}")
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get the size of a file
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            File size in bytes or None if file doesn't exist
        """
        full_path = self.get_full_path(file_path)
        if full_path.exists() and full_path.is_file():
            return full_path.stat().st_size
        return None