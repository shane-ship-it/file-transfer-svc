# Cloud Storage Transfer Service

A flexible, extensible service for downloading files from cloud storage providers (starting with Azure Blob Storage) and saving them to various destinations. The service can run locally or as a Google Cloud Run service.

## Features

- **Extensible Architecture**: Easy to add new storage providers and destinations
- **Azure Blob Storage Support**: Download and upload files using URL and SAS token
- **Multiple Destinations**: Save to local filesystem or Google Cloud Storage
- **Upload Capabilities**: Upload single files or batch upload directories
- **Date-based Organization**: Automatic datetime folders for downloads and date folders for uploads
- **Environment File Support**: Use .env file for credentials to avoid repetitive URL entry
- **Retry Logic**: Automatic retry with configurable attempts and delays
- **Parallel Transfers**: Concurrent downloads for better performance
- **CLI Interface**: Command-line tool for easy interaction
- **Cloud Run Ready**: Can be deployed as a serverless service

## Installation

### Prerequisites

- Python 3.9 or higher
- Poetry (for dependency management)

Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
# or
pip install poetry
```

### Local Installation

```bash
# Clone the repository
git clone <repository-url>
cd blob

# Install dependencies with Poetry
poetry install

# Install with optional dependencies (if needed)
poetry install --extras gcp  # For Google Cloud Storage support
poetry install --extras api  # For API/Cloud Run support
poetry install --extras all  # For all optional features
```

### Running the Application

#### Option 1: Using Poetry Shell (Recommended)
```bash
# Activate Poetry virtual environment
poetry shell

# Run commands directly
python main.py --help
python main.py download --file "myfile.txt"
python main.py list-files
```

#### Option 2: Using Poetry Run
```bash
# Run commands without activating shell
poetry run python main.py --help
poetry run python main.py download --file "myfile.txt"
poetry run python main.py list-files
```

#### Option 3: Using pip (Without Poetry)

If you don't have Poetry installed, you can use pip with the provided requirements.txt:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py --help
```

Note: The requirements.txt file is auto-generated from Poetry dependencies for compatibility.

## Usage

### Command Line Interface

The CLI automatically loads Azure credentials from `.env` file if present, so you don't need to provide `--url` and `--token` in every command.

#### Setup (Recommended)
```bash
# Copy and configure .env file
cp .env.example .env
# Edit .env with your Azure credentials

# Now you can run commands without --url (using Poetry)
poetry run python main.py download --file "myfile.txt"
poetry run python main.py list-files

# Or if you're in a Poetry shell
python main.py download --file "myfile.txt"
python main.py list-files
```

#### Download Commands

```bash
# Download using .env credentials (recommended)
python main.py download --file "path/to/file.txt"

# Download with explicit URL (overrides .env)
python main.py download \
  --url "https://account.blob.core.windows.net/container?sv=..." \
  --file "path/to/file.txt"

# Download all files with a prefix
python main.py download --prefix "documents/" --overwrite

# Download to custom location (default: ./downloads/YYYYMMDD_HHMMSS/)
python main.py download --destination "/custom/path" --file "myfile.txt"

# Download without datetime folder organization
python main.py download --file "myfile.txt" --no-datetime-folder
```

#### Upload Commands

```bash
# Upload a single file using .env credentials
python main.py upload --file "/local/file.txt"

# Upload to a date folder (creates YYYYMMDD/ in blob storage)
python main.py upload --file "/local/file.txt" --date-folder

# Upload with custom destination name
python main.py upload --file "/local/file.txt" --destination "renamed-file.txt"

# Batch upload files from a directory
python main.py upload-batch --source-dir "/local/folder" --pattern "*.txt"

# Batch upload to date folder
python main.py upload-batch --source-dir "/local/folder" --date-folder
```

#### List Files

```bash
# List files using .env credentials
python main.py list-files

# List with prefix filter
python main.py list-files --prefix "images/" --max 50

# List with explicit URL
python main.py list-files \
  --url "https://account.blob.core.windows.net/container?sv=..." \
  --prefix "documents/"
```

## Configuration Options

The service supports three configuration methods, with the following precedence (highest to lowest):
1. **Command-line arguments** - Override all other settings
2. **Configuration file (YAML)** - Structured configuration
3. **Environment variables (.env)** - Simple key-value pairs (default)

### Method 1: Environment Variables (.env File) - Recommended for Simple Setup

The service automatically loads environment variables from a `.env` file in the project root using python-dotenv. This is the recommended approach for local development.

1. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

2. Edit `.env` with your Azure credentials:
```env
# Azure Blob Storage Configuration
AZURE_STORAGE_URL="https://youraccount.blob.core.windows.net"
AZURE_SAS_TOKEN="sv=2021-06-08&ss=..."
AZURE_CONTAINER_NAME="mycontainer"

# Destination Configuration
LOCAL_SAVE_PATH=./downloads  # Default download location
```

3. Run commands without specifying URL:
```bash
# The service automatically uses .env credentials
python main.py download --file "myfile.txt"
python main.py upload --file "/local/file.txt"
python main.py list-files
```

Note: Command-line arguments always override .env settings if both are provided.

### Method 2: Configuration File (config.yaml) - For Advanced Setup

Use a YAML configuration file for more complex setups with multiple sources/destinations:

1. Copy `config.yaml.example` to `config.yaml`:
```bash
cp config.yaml.example config.yaml
```

2. Edit `config.yaml` with your settings:
```yaml
source:
  type: azure_blob
  settings:
    storage_url: "https://youraccount.blob.core.windows.net"
    container_name: "mycontainer"
    sas_token: "?sv=..."

destination:
  type: local_fs
  settings:
    base_path: "./downloads"
    use_datetime_folder: true

transfer:
  batch_size: 10
  retry_attempts: 3
  concurrent_downloads: 5
```

3. Run commands with the config file:
```bash
poetry run python main.py --config config.yaml download
poetry run python main.py --config config.yaml list-files
```

### Method 3: Command-Line Arguments - For Quick Operations

Override any configuration directly via command line:

```bash
# Override URL and destination
poetry run python main.py download \
  --url "https://account.blob.core.windows.net/container?sv=..." \
  --destination "/custom/path" \
  --overwrite

# Mix config file with CLI overrides
poetry run python main.py --config config.yaml download \
  --overwrite \
  --max-files 100
```

### Configuration Priority Example

If you have:
- `.env` file with `LOCAL_SAVE_PATH=./downloads`
- `config.yaml` with `destination.settings.base_path: /tmp/data`
- CLI argument `--destination /my/custom/path`

The service will use `/my/custom/path` (CLI argument wins)

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_STORAGE_URL` | Azure storage account URL | Required |
| `AZURE_SAS_TOKEN` | SAS token for authentication | Optional |
| `AZURE_CONTAINER_NAME` | Container name | Required |
| `DESTINATION_TYPE` | Destination type (local_fs, gcp_storage) | local_fs |
| `LOCAL_SAVE_PATH` | Local directory for downloads | ./downloads |
| `BATCH_SIZE` | Number of files per batch | 10 |
| `RETRY_ATTEMPTS` | Number of retry attempts | 3 |
| `CONCURRENT_DOWNLOADS` | Number of parallel downloads | 5 |

## Development

### Managing Dependencies

```bash
# Add a new dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Show installed packages
poetry show

# Export to requirements.txt (for compatibility)
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov

# Run specific test file
poetry run pytest tests/test_providers.py
```

### Code Formatting and Linting
```bash
# Format code with black
poetry run black src tests

# Sort imports
poetry run isort src tests

# Run linting
poetry run flake8 src tests

# Type checking
poetry run mypy src
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files
```

## Docker Deployment

### Build Docker Image
```bash
docker build -t blob-transfer .
```

### Run Locally with Docker
```bash
docker run -v /local/downloads:/data/downloads \
  -e AZURE_STORAGE_URL="https://account.blob.core.windows.net" \
  -e AZURE_SAS_TOKEN="?sv=..." \
  -e AZURE_CONTAINER_NAME="mycontainer" \
  blob-transfer python main.py download
```

## Google Cloud Run Deployment

### Prerequisites
- Google Cloud SDK installed
- Project configured with billing enabled

### Deploy to Cloud Run
```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/blob-transfer

# Deploy service
gcloud run deploy blob-transfer \
  --image gcr.io/PROJECT_ID/blob-transfer \
  --platform managed \
  --region us-central1 \
  --set-env-vars AZURE_STORAGE_URL=...,AZURE_SAS_TOKEN=...
```

## Architecture

The service follows a modular architecture:

- **Storage Sources (storage_src)**: Handle downloading from storage providers (Azure Blob, S3, GCS)
- **Storage Destinations (storage_dest)**: Handle saving to targets (Local FS, GCS, S3)
- **Transfer Engine**: Orchestrates transfers with retry and parallel processing
- **Configuration**: Flexible configuration via files, environment, or CLI args
- **Auto-organization**: Downloads go to `./downloads/YYYYMMDD_HHMMSS/` by default, uploads can use `YYYYMMDD/` folders

## Extending the Service

### Adding a New Storage Source

1. Create a new file in `src/storage_src/`
2. Inherit from `StorageProvider` base class
3. Implement required methods
4. Register in provider factory

### Adding a New Storage Destination

1. Create a new file in `src/storage_dest/`
2. Inherit from `StorageDestination` base class
3. Implement required methods
4. Register in destination factory

## Security Considerations

- Never commit SAS tokens or credentials to version control
- Use environment variables or secret managers for sensitive data
- Implement proper access controls for Cloud Run deployments
- Validate and sanitize all input paths

## License

MIT License - See LICENSE file for details