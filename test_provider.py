#!/usr/bin/env python3
"""Test AzureBlobProvider container_url property"""

import os
from dotenv import load_dotenv
from src.storage_src.azure_blob import AzureBlobProvider

# Load environment variables
load_dotenv()

def test_provider_from_env():
    """Test provider created from environment variables"""
    storage_url = os.getenv('AZURE_STORAGE_URL')
    container = os.getenv('AZURE_CONTAINER_NAME')
    token = os.getenv('AZURE_SAS_TOKEN')
    
    if not storage_url:
        print("No Azure credentials in environment")
        return
    
    # Test method 1: from environment-like config
    config = {
        'account_url': storage_url,
        'container_name': container,
        'sas_token': token
    }
    
    provider = AzureBlobProvider(config)
    print(f"Provider created from config:")
    print(f"  Container URL: {provider.container_url}")
    print(f"  Has container_url attr: {hasattr(provider, 'container_url')}")
    print()

def test_provider_from_url():
    """Test provider created from URL (like API does)"""
    storage_url = os.getenv('AZURE_STORAGE_URL')
    container = os.getenv('AZURE_CONTAINER_NAME')  
    token = os.getenv('AZURE_SAS_TOKEN')
    
    if not storage_url:
        print("No Azure credentials in environment")
        return
    
    # Construct full URL like the API does
    full_url = storage_url.rstrip('/') + '/' + container
    if token:
        full_url += '?' + token.lstrip('?')
    
    print(f"Testing from_url with: {full_url[:50]}...")
    
    provider = AzureBlobProvider.from_url(full_url)
    print(f"Provider created from URL:")
    print(f"  Container URL: {provider.container_url}")
    print(f"  Has container_url attr: {hasattr(provider, 'container_url')}")
    print()

if __name__ == "__main__":
    print("Testing AzureBlobProvider container_url property")
    print("=" * 50)
    test_provider_from_env()
    test_provider_from_url()