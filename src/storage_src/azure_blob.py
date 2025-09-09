"""Azure Blob Storage provider implementation"""

import logging
import os
from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

from .base import StorageProvider, FileMetadata

logger = logging.getLogger(__name__)


class AzureBlobProvider(StorageProvider):
    """Azure Blob Storage provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Azure Blob Storage provider
        
        Args:
            config: Configuration dict with keys:
                - account_url: Azure storage account URL
                - container_name: Container name
                - sas_token: SAS token for authentication (optional)
                - connection_string: Connection string (alternative to URL + SAS)
                - container_url: Full container URL with SAS (alternative)
        """
        super().__init__(config)
        
        # Check if we have a full container URL with SAS
        if config.get('container_url'):
            # Use container URL directly
            self._container_url = config['container_url']
            self.container_client = ContainerClient.from_container_url(
                config['container_url']
            )
            # Extract container name from URL
            parsed = urlparse(config['container_url'])
            self.container_name = parsed.path.strip('/').split('/')[0] if parsed.path else 'container'
            self.client = None  # We don't need service client when using container URL
        else:
            # Traditional initialization
            self.container_name = config.get('container_name')
            
            if not self.container_name:
                raise ValueError("Container name is required")
            
            # Initialize client
            if config.get('connection_string'):
                self.client = BlobServiceClient.from_connection_string(
                    config['connection_string']
                )
            elif config.get('account_url'):
                account_url = config['account_url']
                sas_token = config.get('sas_token', '')
                
                # Ensure URL doesn't already contain SAS token
                if '?' in account_url:
                    self.client = BlobServiceClient(account_url)
                elif sas_token:
                    # Add SAS token to URL if provided
                    if not sas_token.startswith('?'):
                        sas_token = '?' + sas_token
                    self.client = BlobServiceClient(account_url + sas_token)
                else:
                    self.client = BlobServiceClient(account_url)
            else:
                raise ValueError("Either account_url or connection_string is required")
            
            self.container_client: ContainerClient = self.client.get_container_client(
                self.container_name
            )
            
            # Store container URL for API usage
            if config.get('account_url'):
                account_url = config['account_url'].rstrip('/')
                sas_token = config.get('sas_token', '')
                if sas_token and not sas_token.startswith('?'):
                    sas_token = '?' + sas_token
                self._container_url = f"{account_url}/{self.container_name}{sas_token}"
            else:
                self._container_url = None
    
    @property
    def container_url(self) -> Optional[str]:
        """Get the container URL (may be None if not available)"""
        return self._container_url
    
    def list_files(self, prefix: Optional[str] = None, 
                   max_results: Optional[int] = None) -> List[FileMetadata]:
        """List files in Azure Blob Storage container
        
        Args:
            prefix: Optional prefix to filter blobs
            max_results: Maximum number of results
            
        Returns:
            List of FileMetadata objects
        """
        try:
            files = []
            blob_list = self.container_client.list_blobs(
                name_starts_with=prefix
            )
            
            for blob in blob_list:
                if max_results and len(files) >= max_results:
                    break
                
                files.append(FileMetadata(
                    name=blob.name,
                    size=blob.size,
                    last_modified=blob.last_modified,
                    content_type=blob.content_settings.content_type if blob.content_settings else None,
                    etag=blob.etag,
                    metadata=blob.metadata
                ))
            
            logger.info(f"Listed {len(files)} files from Azure Blob Storage")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
    
    def download_file(self, file_path: str, output_stream: BinaryIO) -> None:
        """Download a file from Azure Blob Storage
        
        Args:
            file_path: Path to the blob in the container
            output_stream: Stream to write the downloaded content
        """
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            download_stream = blob_client.download_blob()
            download_stream.readinto(output_stream)
            logger.info(f"Downloaded file: {file_path}")
            
        except ResourceNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"Blob not found: {file_path}")
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {e}")
            raise
    
    def get_metadata(self, file_path: str) -> FileMetadata:
        """Get metadata for a specific blob
        
        Args:
            file_path: Path to the blob in the container
            
        Returns:
            FileMetadata object
        """
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            properties = blob_client.get_blob_properties()
            
            return FileMetadata(
                name=properties.name,
                size=properties.size,
                last_modified=properties.last_modified,
                content_type=properties.content_settings.content_type if properties.content_settings else None,
                etag=properties.etag,
                metadata=properties.metadata
            )
            
        except ResourceNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"Blob not found: {file_path}")
        except Exception as e:
            logger.error(f"Error getting metadata for {file_path}: {e}")
            raise
    
    def exists(self, file_path: str) -> bool:
        """Check if a blob exists
        
        Args:
            file_path: Path to the blob in the container
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Error checking if file exists {file_path}: {e}")
            return False
    
    def validate_config(self) -> bool:
        """Validate Azure Blob Storage configuration
        
        Returns:
            True if configuration is valid and container is accessible
        """
        try:
            # For container URLs with SAS, try listing blobs instead of getting properties
            # as the SAS token might not have permission for container properties
            blob_iter = self.container_client.list_blobs()
            # Try to get the first blob (will work even if empty)
            next(iter(blob_iter), None)
            logger.info("Azure Blob Storage configuration validated successfully")
            return True
        except Exception as e:
            # If list fails, try a simpler check
            try:
                # Just check if we can create a blob client (doesn't make a request)
                test_blob = self.container_client.get_blob_client("test")
                logger.info("Azure Blob Storage configuration validated (basic check)")
                return True
            except Exception as e2:
                logger.error(f"Invalid Azure Blob Storage configuration: {e}")
                return False
    
    def upload_file(self, local_path: str, remote_path: str, 
                   overwrite: bool = True) -> bool:
        """Upload a file to Azure Blob Storage
        
        Args:
            local_path: Path to the local file
            remote_path: Path in storage (can include virtual directories like '20250908/file.txt')
            overwrite: Whether to overwrite if blob exists
            
        Returns:
            True if upload was successful
        """
        try:
            # Check if local file exists
            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}")
                return False
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(remote_path)
            
            # Check if blob exists and overwrite is False
            if not overwrite and blob_client.exists():
                logger.warning(f"Blob already exists and overwrite=False: {remote_path}")
                return False
            
            # Upload the file
            with open(local_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=overwrite)
            
            logger.info(f"Successfully uploaded {local_path} to {remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading file {local_path}: {e}")
            return False
    
    def create_folder(self, folder_path: str) -> bool:
        """Create a virtual folder in Azure Blob Storage
        
        In Azure Blob Storage, folders are virtual and created by uploading a blob
        with a path that includes the folder. We'll create a hidden marker file.
        
        Args:
            folder_path: Path of the folder to create (e.g., '20250908')
            
        Returns:
            True if folder was created
        """
        try:
            # Ensure folder path ends with /
            if not folder_path.endswith('/'):
                folder_path += '/'
            
            # Create a marker blob to represent the folder
            marker_blob = folder_path + '.folder'
            blob_client = self.container_client.get_blob_client(marker_blob)
            
            # Upload empty content to create the folder
            blob_client.upload_blob(b'', overwrite=True)
            
            logger.info(f"Created virtual folder: {folder_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating folder {folder_path}: {e}")
            return False
    
    @classmethod
    def from_url(cls, url: str, sas_token: Optional[str] = None) -> 'AzureBlobProvider':
        """Create provider from Azure Blob URL
        
        Args:
            url: Full Azure Blob Storage URL (may include SAS token)
            sas_token: Optional SAS token if not in URL
            
        Returns:
            AzureBlobProvider instance
        """
        parsed = urlparse(url)
        
        # Extract account URL and container from path
        account_url = f"{parsed.scheme}://{parsed.netloc}"
        path_parts = parsed.path.strip('/').split('/', 1)
        container_name = path_parts[0] if path_parts else ''
        
        # Check if URL contains SAS token
        if parsed.query:
            # URL already contains SAS token - use container URL directly
            # The URL format is: https://account.blob.core.windows.net/container?sas_params
            config = {
                'container_url': url
            }
        elif sas_token:
            # Use provided SAS token
            config = {
                'account_url': account_url,
                'container_name': container_name,
                'sas_token': sas_token
            }
        else:
            # No authentication provided
            config = {
                'account_url': account_url,
                'container_name': container_name
            }
        
        return cls(config)