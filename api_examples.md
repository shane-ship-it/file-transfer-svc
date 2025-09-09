# API Usage Examples

## Starting the API Server

```bash
# Install API dependencies (if not already installed)
poetry install --extras api

# Start the API server
poetry run python api_server.py

# The server will start on http://localhost:8080
# API documentation available at http://localhost:8080/docs
```

## API Endpoints

### 1. Health Check

```bash
# Check if API is running
curl http://localhost:8080/health
```

### 2. Download Files

Download files from Azure Blob Storage to local filesystem:

```bash
# Download all files with prefix "reports/"
curl -X POST http://localhost:8080/api/v1/transfer/download \
  -H "Content-Type: application/json" \
  -d '{
    "prefix": "reports/",
    "max_files": 100,
    "destination_path": "./downloads",
    "overwrite": true
  }'

# Download with explicit Azure credentials
curl -X POST http://localhost:8080/api/v1/transfer/download \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://account.blob.core.windows.net/container",
    "sas_token": "?sv=2021-06-08&ss=...",
    "prefix": "documents/",
    "max_files": 50,
    "overwrite": false
  }'
```

### 3. Upload File

Upload a single file to Azure Blob Storage:

```bash
# Upload file to specific path
curl -X POST http://localhost:8080/api/v1/transfer/upload \
  -F "file=@/path/to/local/file.txt" \
  -F "destination_path=uploads/myfile.txt" \
  -F "overwrite=true"

# Upload file to date folder (YYYYMMDD/)
curl -X POST http://localhost:8080/api/v1/transfer/upload \
  -F "file=@/path/to/local/file.txt" \
  -F "date_folder=true" \
  -F "overwrite=false"

# Upload with explicit Azure credentials
curl -X POST http://localhost:8080/api/v1/transfer/upload \
  -F "file=@/path/to/local/file.txt" \
  -F "container_url=https://account.blob.core.windows.net/container" \
  -F "sas_token=?sv=2021-06-08&ss=..." \
  -F "destination_path=uploads/myfile.txt"
```

### 4. Check Transfer Status

Check the status of a download transfer job:

```bash
# Get job status
curl http://localhost:8080/api/v1/transfer/{job_id}

# Example response:
{
  "job_id": "job_20240908_123456_abc123",
  "status": "completed",
  "progress": {
    "total_files": 100,
    "completed_files": 98,
    "failed_files": 2,
    "skipped_files": 0,
    "total_bytes": 1048576000
  },
  "started_at": "2024-09-08T12:34:56",
  "completed_at": "2024-09-08T12:35:42",
  "duration_seconds": 46.2
}
```

## Using with API Key Authentication

If API_KEY is configured in the environment:

```bash
# Set API key in environment
export API_KEY="your-secret-api-key"

# Include API key in requests
curl -X POST http://localhost:8080/api/v1/transfer/download \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prefix": "data/"}'
```

## Python Requests Examples

```python
import requests

# Base URL
base_url = "http://localhost:8080"

# Download files
response = requests.post(
    f"{base_url}/api/v1/transfer/download",
    json={
        "prefix": "reports/",
        "max_files": 10,
        "overwrite": True
    }
)
job_id = response.json()["job_id"]

# Check status
status = requests.get(f"{base_url}/api/v1/transfer/{job_id}")
print(status.json())

# Upload file
with open("local_file.txt", "rb") as f:
    response = requests.post(
        f"{base_url}/api/v1/transfer/upload",
        files={"file": f},
        data={
            "destination_path": "uploads/file.txt",
            "overwrite": "true"
        }
    )
print(response.json())
```

## Response Status Codes

- `200` - Success (upload completed)
- `202` - Accepted (download job started)
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `404` - Not Found (job ID not found)
- `409` - Conflict (file exists and overwrite=false)
- `500` - Internal Server Error

## Environment Configuration

The API uses the same `.env` file as the CLI:

```env
# .env file
AZURE_STORAGE_URL=https://youraccount.blob.core.windows.net
AZURE_CONTAINER_NAME=mycontainer
AZURE_SAS_TOKEN=?sv=2021-06-08&ss=...
API_KEY=optional-api-key-for-authentication
PORT=8080
```

## Testing the API

Run the included test script:

```bash
# Run API tests
poetry run python test_api.py
```

This will test all endpoints and show the results.