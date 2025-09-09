"""FastAPI application for Cloud Storage Transfer Service"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import os
import tempfile
import uuid
from pathlib import Path
import asyncio
import logging

from ..storage_src.azure_blob import AzureBlobProvider
from ..storage_dest.local_fs import LocalFileSystemDestination
from ..engine.transfer import TransferEngine
from ..engine.config import TransferConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Cloud Storage Transfer Service API",
    description="REST API for transferring files between Azure Blob Storage and local storage",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory job store (in production, use a database)
transfer_jobs: Dict[str, Dict[str, Any]] = {}


class DownloadRequest(BaseModel):
    """Request model for download endpoint"""
    source_url: Optional[str] = Field(None, description="Azure Blob Storage URL")
    sas_token: Optional[str] = Field(None, description="SAS token for authentication")
    prefix: Optional[str] = Field(None, description="Filter files by prefix")
    max_files: Optional[int] = Field(None, description="Maximum number of files to download")
    destination_path: Optional[str] = Field("./downloads", description="Destination directory")
    overwrite: bool = Field(False, description="Whether to overwrite existing files")


class TransferJobResponse(BaseModel):
    """Response model for transfer job creation"""
    job_id: str
    status: str
    message: str
    created_at: datetime
    destination_path: str


class UploadResponse(BaseModel):
    """Response model for file upload"""
    status: str
    message: str
    blob_name: str
    blob_url: str
    size: int
    uploaded_at: datetime


def get_azure_provider(source_url: Optional[str] = None, sas_token: Optional[str] = None) -> AzureBlobProvider:
    """Create Azure provider from URL or environment variables"""
    
    if source_url:
        # Use provided URL
        return AzureBlobProvider.from_url(source_url, sas_token)
    else:
        # Try to get from environment
        storage_url = os.getenv('AZURE_STORAGE_URL')
        container = os.getenv('AZURE_CONTAINER_NAME')
        token = os.getenv('AZURE_SAS_TOKEN')
        
        if not storage_url:
            raise HTTPException(
                status_code=400,
                detail="No Azure credentials provided. Either provide source_url or set environment variables."
            )
        
        # Construct full URL
        full_url = storage_url.rstrip('/') + '/' + container
        if token:
            full_url += '?' + token.lstrip('?')
        
        return AzureBlobProvider.from_url(full_url)


async def run_transfer_job(job_id: str, provider: AzureBlobProvider, destination: LocalFileSystemDestination,
                          config: TransferConfig, prefix: Optional[str], max_files: Optional[int]):
    """Background task to run transfer job"""
    
    try:
        # Update job status
        transfer_jobs[job_id]['status'] = 'in_progress'
        transfer_jobs[job_id]['started_at'] = datetime.now()
        
        # Create transfer engine
        engine = TransferEngine(provider, destination, config)
        
        # Perform transfer
        logger.info(f"Starting transfer job {job_id}")
        results = engine.transfer_all(prefix=prefix, max_files=max_files)
        
        # Get summary
        summary = engine.get_summary()
        
        # Update job with results
        transfer_jobs[job_id].update({
            'status': 'completed' if summary['failed'] == 0 else 'completed_with_errors',
            'completed_at': datetime.now(),
            'progress': {
                'total_files': summary['total_files'],
                'completed_files': summary['completed'],
                'failed_files': summary['failed'],
                'skipped_files': summary['skipped'],
                'total_bytes': summary['total_size_bytes'],
                'transferred_bytes': summary['total_size_bytes']
            },
            'duration_seconds': summary['total_duration_seconds'],
            'errors': summary['failed_files']
        })
        
        logger.info(f"Transfer job {job_id} completed: {summary['completed']} files transferred")
        
    except Exception as e:
        logger.error(f"Transfer job {job_id} failed: {str(e)}")
        transfer_jobs[job_id].update({
            'status': 'failed',
            'completed_at': datetime.now(),
            'error': str(e)
        })


@app.post("/api/v1/transfer/download", response_model=TransferJobResponse, status_code=202)
async def download_files(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None)
):
    """
    Download files from Azure Blob Storage
    
    This endpoint initiates a background transfer job to download files from Azure Blob Storage.
    The job runs asynchronously and you can check its status using the job_id.
    """
    
    # Check API key if configured
    configured_api_key = os.getenv('API_KEY')
    if configured_api_key and x_api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        # Create provider
        provider = get_azure_provider(request.source_url, request.sas_token)
        
        # Validate provider
        if not provider.validate_config():
            raise HTTPException(status_code=400, detail="Failed to validate Azure Blob Storage connection")
        
        # Create destination
        dest_config = {
            'base_path': request.destination_path,
            'create_dirs': True,
            'use_datetime_folder': True
        }
        destination = LocalFileSystemDestination(dest_config)
        
        # Create transfer config
        config = TransferConfig()
        config.overwrite_existing = request.overwrite
        
        # Generate job ID
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Store job info
        transfer_jobs[job_id] = {
            'job_id': job_id,
            'status': 'pending',
            'created_at': datetime.now(),
            'destination_path': str(destination.session_path),
            'request': request.dict()
        }
        
        # Start background transfer
        background_tasks.add_task(
            run_transfer_job,
            job_id,
            provider,
            destination,
            config,
            request.prefix,
            request.max_files
        )
        
        return TransferJobResponse(
            job_id=job_id,
            status='pending',
            message='Transfer job initiated',
            created_at=transfer_jobs[job_id]['created_at'],
            destination_path=transfer_jobs[job_id]['destination_path']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating download: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/transfer/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    destination_path: Optional[str] = Form(None),
    date_folder: bool = Form(False),
    overwrite: bool = Form(False),
    container_url: Optional[str] = Form(None),
    sas_token: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None)
):
    """
    Upload a file to Azure Blob Storage
    
    This endpoint uploads a single file to Azure Blob Storage.
    The file is uploaded synchronously and returns the upload status immediately.
    """
    
    # Check API key if configured
    configured_api_key = os.getenv('API_KEY')
    if configured_api_key and x_api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        # Create provider
        provider = get_azure_provider(container_url, sas_token)
        
        # Validate provider
        if not provider.validate_config():
            raise HTTPException(status_code=400, detail="Failed to validate Azure Blob Storage connection")
        
        # Determine blob name
        if date_folder:
            date_str = datetime.now().strftime('%Y%m%d')
            blob_name = f"{date_str}/{destination_path or file.filename}"
            
            # Create date folder
            provider.create_folder(date_str)
        else:
            blob_name = destination_path or file.filename
        
        # Check if file exists and overwrite is false
        if not overwrite and provider.exists(blob_name):
            raise HTTPException(
                status_code=409,
                detail=f"File '{blob_name}' already exists and overwrite is false"
            )
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Upload to Azure
            success = provider.upload_file(tmp_file_path, blob_name, overwrite)
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to upload file to Azure Blob Storage")
            
            # Get file metadata
            metadata = provider.get_metadata(blob_name)
            
            # Construct blob URL
            if provider.container_url:
                base_url = provider.container_url.split('?')[0]  # Remove SAS token from URL
                blob_url = f"{base_url}/{blob_name}"
            else:
                # Fallback URL construction if container_url is not available
                blob_url = f"https://account.blob.core.windows.net/{blob_name}"
            
            return UploadResponse(
                status="success",
                message="File uploaded successfully",
                blob_name=blob_name,
                blob_url=blob_url,
                size=metadata.size,
                uploaded_at=metadata.last_modified
            )
            
        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/transfer/{job_id}")
async def get_transfer_status(
    job_id: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Get transfer job status
    
    Returns the current status and progress of a transfer job.
    """
    
    # Check API key if configured
    configured_api_key = os.getenv('API_KEY')
    if configured_api_key and x_api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if job_id not in transfer_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return transfer_jobs[job_id]


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns the health status of the API.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """
    Root endpoint
    
    Returns API information and available endpoints.
    """
    return {
        "name": "Cloud Storage Transfer Service API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
            "download": "/api/v1/transfer/download",
            "upload": "/api/v1/transfer/upload",
            "status": "/api/v1/transfer/{job_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)