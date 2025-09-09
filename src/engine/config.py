"""Configuration management for the transfer service"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TransferConfig:
    """Configuration for transfer operations"""
    
    # Source configuration
    source_type: str = "azure_blob"
    source_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Destination configuration
    destination_type: str = "local_fs"
    destination_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Transfer settings
    batch_size: int = 10
    retry_attempts: int = 3
    retry_delay: int = 5
    concurrent_downloads: int = 5
    overwrite_existing: bool = False
    
    # API settings (for Cloud Run)
    api_port: int = 8080
    api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'TransferConfig':
        """Load configuration from environment variables"""
        config = cls()
        
        # Azure settings
        config.source_type = os.getenv('SOURCE_TYPE', 'azure_blob')
        config.source_settings = {
            'account_url': os.getenv('AZURE_STORAGE_URL', ''),
            'sas_token': os.getenv('AZURE_SAS_TOKEN', ''),
            'container_name': os.getenv('AZURE_CONTAINER_NAME', ''),
        }
        
        # Destination settings
        config.destination_type = os.getenv('DESTINATION_TYPE', 'local_fs')
        
        if config.destination_type == 'local_fs':
            config.destination_settings = {
                'base_path': os.getenv('LOCAL_SAVE_PATH', './downloads'),
            }
        elif config.destination_type == 'gcp_storage':
            config.destination_settings = {
                'project_id': os.getenv('GCP_PROJECT_ID', ''),
                'bucket_name': os.getenv('GCP_BUCKET_NAME', ''),
                'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
            }
        
        # Transfer settings
        config.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        config.retry_attempts = int(os.getenv('RETRY_ATTEMPTS', '3'))
        config.retry_delay = int(os.getenv('RETRY_DELAY', '5'))
        config.concurrent_downloads = int(os.getenv('CONCURRENT_DOWNLOADS', '5'))
        config.overwrite_existing = os.getenv('OVERWRITE_EXISTING', 'false').lower() == 'true'
        
        # API settings
        config.api_port = int(os.getenv('PORT', '8080'))
        config.api_key = os.getenv('API_KEY')
        
        return config
    
    @classmethod
    def from_file(cls, file_path: str) -> 'TransferConfig':
        """Load configuration from a YAML or JSON file"""
        config = cls()
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {path.suffix}")
        
        # Parse source configuration
        if 'source' in data:
            config.source_type = data['source'].get('type', 'azure_blob')
            config.source_settings = data['source'].get('settings', {})
            # Replace environment variable references
            config.source_settings = cls._replace_env_vars(config.source_settings)
        
        # Parse destination configuration
        if 'destination' in data:
            config.destination_type = data['destination'].get('type', 'local_fs')
            config.destination_settings = data['destination'].get('settings', {})
            config.destination_settings = cls._replace_env_vars(config.destination_settings)
        
        # Parse transfer settings
        if 'transfer' in data:
            transfer = data['transfer']
            config.batch_size = transfer.get('batch_size', 10)
            config.retry_attempts = transfer.get('retry_attempts', 3)
            config.retry_delay = transfer.get('retry_delay', 5)
            config.concurrent_downloads = transfer.get('concurrent_downloads', 5)
            config.overwrite_existing = transfer.get('overwrite_existing', False)
        
        # Parse API settings
        if 'api' in data:
            api = data['api']
            config.api_port = api.get('port', 8080)
            config.api_key = api.get('key')
        
        return config
    
    @staticmethod
    def _replace_env_vars(settings: Dict[str, Any]) -> Dict[str, Any]:
        """Replace ${ENV_VAR} references with actual environment values"""
        result = {}
        for key, value in settings.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                result[key] = os.getenv(env_var, '')
            else:
                result[key] = value
        return result
    
    def validate(self) -> bool:
        """Validate the configuration"""
        # Check source configuration
        if self.source_type == 'azure_blob':
            if not self.source_settings.get('account_url'):
                raise ValueError("Azure account URL is required")
            if not self.source_settings.get('container_name'):
                raise ValueError("Azure container name is required")
        
        # Check destination configuration
        if self.destination_type == 'local_fs':
            if not self.destination_settings.get('base_path'):
                self.destination_settings['base_path'] = './downloads'
        elif self.destination_type == 'gcp_storage':
            if not self.destination_settings.get('project_id'):
                raise ValueError("GCP project ID is required")
            if not self.destination_settings.get('bucket_name'):
                raise ValueError("GCP bucket name is required")
        
        # Validate numeric settings
        if self.batch_size < 1:
            raise ValueError("Batch size must be at least 1")
        if self.retry_attempts < 0:
            raise ValueError("Retry attempts cannot be negative")
        if self.concurrent_downloads < 1:
            raise ValueError("Concurrent downloads must be at least 1")
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'source': {
                'type': self.source_type,
                'settings': self.source_settings
            },
            'destination': {
                'type': self.destination_type,
                'settings': self.destination_settings
            },
            'transfer': {
                'batch_size': self.batch_size,
                'retry_attempts': self.retry_attempts,
                'retry_delay': self.retry_delay,
                'concurrent_downloads': self.concurrent_downloads,
                'overwrite_existing': self.overwrite_existing
            },
            'api': {
                'port': self.api_port,
                'key': self.api_key
            }
        }