# API Module (Planned)

This directory is reserved for the REST API implementation that will enable:

## Planned Features

- **FastAPI-based REST API** for triggering transfers via HTTP
- **Google Cloud Run deployment** for serverless operation
- **Webhook support** for transfer completion notifications
- **Batch job scheduling** via API calls

## Planned Endpoints

- `POST /transfer` - Trigger a file transfer
- `GET /transfer/{id}` - Get transfer status
- `GET /files` - List available files
- `POST /upload` - Upload files via API

## Installation (When Implemented)

```bash
# Install with API support
poetry install --extras api
```

## Current Status

⚠️ **Not yet implemented** - This is a planned feature. The CLI interface (`src/cli.py`) currently provides all functionality.

To contribute to this feature, see the main project README.