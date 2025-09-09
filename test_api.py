#!/usr/bin/env python3
"""Test script for the Cloud Storage Transfer Service API"""

import requests
import json
import time
import os
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8080"

# Optional API key (if configured)
API_KEY = os.getenv("API_KEY", None)

# Headers
headers = {}
if API_KEY:
    headers["X-API-Key"] = API_KEY


def test_health():
    """Test health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✓ Health check passed\n")


def test_download():
    """Test download endpoint"""
    print("Testing download endpoint...")
    
    # Request body
    data = {
        "prefix": "32health",  # Download files starting with "32health"
        "max_files": 5,
        "destination_path": "./test_downloads",
        "overwrite": True
    }
    
    # Note: This uses environment variables for Azure credentials
    response = requests.post(
        f"{BASE_URL}/api/v1/transfer/download",
        json=data,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 202:
        job_id = response.json()["job_id"]
        print(f"✓ Download job created: {job_id}")
        
        # Check job status
        print(f"\nChecking job status...")
        time.sleep(2)  # Wait a bit for the job to start
        
        status_response = requests.get(
            f"{BASE_URL}/api/v1/transfer/{job_id}",
            headers=headers
        )
        
        print(f"Job Status: {json.dumps(status_response.json(), indent=2)}")
        return job_id
    else:
        print(f"✗ Download failed: {response.json()}")
    
    print()


def test_upload():
    """Test upload endpoint"""
    print("Testing upload endpoint...")
    
    # Create a test file
    test_file_path = "test_api_upload.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test file uploaded via API\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Prepare multipart form data
        with open(test_file_path, "rb") as f:
            files = {
                "file": ("test_api_upload.txt", f, "text/plain")
            }
            data = {
                "destination_path": "api_test/test_upload.txt",
                "date_folder": "false",
                "overwrite": "true"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/transfer/upload",
                files=files,
                data=data,
                headers=headers
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print(f"✓ Upload successful")
        else:
            print(f"✗ Upload failed")
            
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    print()


def test_upload_with_date_folder():
    """Test upload with date folder"""
    print("Testing upload with date folder...")
    
    # Create a test file
    test_file_path = "test_date_upload.txt"
    with open(test_file_path, "w") as f:
        f.write("Test file for date folder upload\n")
    
    try:
        with open(test_file_path, "rb") as f:
            files = {
                "file": ("test_date_upload.txt", f, "text/plain")
            }
            data = {
                "date_folder": "true",
                "overwrite": "true"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/transfer/upload",
                files=files,
                data=data,
                headers=headers
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print(f"✓ Upload with date folder successful")
        else:
            print(f"✗ Upload failed")
            
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    print()


def main():
    """Run all tests"""
    print("="*60)
    print("Cloud Storage Transfer Service API Tests")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    print(f"API Key configured: {'Yes' if API_KEY else 'No'}")
    print("="*60 + "\n")
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: API server is not running!")
        print(f"Please start the API server first:")
        print("  poetry run python api_server.py")
        return
    
    # Run tests
    test_health()
    job_id = test_download()
    test_upload()
    test_upload_with_date_folder()
    
    # Check final job status if we got a job_id
    if job_id:
        print(f"Checking final status of job {job_id}...")
        time.sleep(3)  # Wait for job to complete
        status_response = requests.get(
            f"{BASE_URL}/api/v1/transfer/{job_id}",
            headers=headers
        )
        final_status = status_response.json()
        print(f"Final Job Status: {final_status.get('status', 'unknown')}")
        if 'progress' in final_status:
            progress = final_status['progress']
            print(f"  Completed: {progress.get('completed_files', 0)} files")
            print(f"  Failed: {progress.get('failed_files', 0)} files")
            print(f"  Skipped: {progress.get('skipped_files', 0)} files")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()