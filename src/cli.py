"""Command-line interface for the transfer service"""

import click
import logging
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from .engine.config import TransferConfig
from .engine.transfer import TransferEngine
from .storage_src.azure_blob import AzureBlobProvider
from .storage_dest.local_fs import LocalFileSystemDestination

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_azure_url_from_env() -> Optional[str]:
    """Construct Azure URL from environment variables"""
    storage_url = os.getenv('AZURE_STORAGE_URL')
    
    if storage_url:
        # Check if URL already contains everything (container and SAS)
        if '?' in storage_url and '.blob.core.windows.net/' in storage_url:
            # Full URL with container and SAS - use as is
            return storage_url
        
        # Otherwise try to construct from parts
        container = os.getenv('AZURE_CONTAINER_NAME')
        sas_token = os.getenv('AZURE_SAS_TOKEN')
        
        if container:
            # Remove trailing slash from storage URL if present
            storage_url = storage_url.rstrip('/')
            
            # Construct full URL with container
            if sas_token:
                # Add SAS token if provided
                if not sas_token.startswith('?'):
                    sas_token = '?' + sas_token
                return f"{storage_url}/{container}{sas_token}"
            else:
                return f"{storage_url}/{container}"
    return None


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Path to configuration file (YAML or JSON)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """Cloud Storage Transfer Service CLI"""
    ctx.ensure_object(dict)
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    if config:
        ctx.obj['config'] = TransferConfig.from_file(config)
    else:
        ctx.obj['config'] = TransferConfig.from_env()


@cli.command()
@click.option('--url', '-u', help='Azure Blob Storage URL (uses .env if not provided)')
@click.option('--token', '-t', help='SAS token for authentication')
@click.option('--destination', '-d', default='./downloads', 
              help='Destination directory (default: ./downloads)')
@click.option('--file', '-f', help='Specific file to download')
@click.option('--prefix', '-p', help='Prefix to filter files')
@click.option('--overwrite', is_flag=True, help='Overwrite existing files')
@click.option('--max-files', '-m', type=int, help='Maximum number of files to transfer')
@click.option('--no-datetime-folder', is_flag=True, 
              help='Disable datetime folder organization (default: files go to downloads/YYYYMMDD_HHMMSS/)')
@click.pass_context
def download(ctx, url: Optional[str], token: Optional[str], destination: str, 
            file: Optional[str], prefix: Optional[str], overwrite: bool,
            max_files: Optional[int], no_datetime_folder: bool):
    """Download files from Azure Blob Storage"""
    
    try:
        # Use URL from command line or environment
        if not url:
            url = get_azure_url_from_env()
            if not url:
                click.echo("Error: No URL provided and Azure credentials not found in environment.", err=True)
                click.echo("Either provide --url or set AZURE_STORAGE_URL and AZURE_CONTAINER_NAME in .env", err=True)
                sys.exit(1)
            click.echo(f"Using Azure credentials from .env file")
        
        # Create provider from URL
        provider = AzureBlobProvider.from_url(url, token)
        
        # Validate provider
        if not provider.validate_config():
            click.echo("Failed to validate Azure Blob Storage connection", err=True)
            sys.exit(1)
        
        # Create destination with datetime folder option
        dest_config = {
            'base_path': destination, 
            'create_dirs': True,
            'use_datetime_folder': not no_datetime_folder  # Invert the flag
        }
        destination_obj = LocalFileSystemDestination(dest_config)
        
        # Validate destination
        if not destination_obj.validate_config():
            click.echo("Failed to validate destination", err=True)
            sys.exit(1)
        
        # Show download location
        click.echo(f"Downloading to: {destination_obj.session_path}")
        
        # Get config and update overwrite setting
        config = ctx.obj.get('config', TransferConfig())
        config.overwrite_existing = overwrite
        
        # Create transfer engine
        engine = TransferEngine(provider, destination_obj, config)
        
        # Perform transfer
        if file:
            # Transfer single file
            click.echo(f"Downloading file: {file}")
            result = engine.transfer_with_retry(file)
            
            if result.status.value == 'completed':
                click.echo(f"✓ Successfully downloaded {file} ({result.size} bytes)")
            elif result.status.value == 'skipped':
                click.echo(f"⊘ Skipped existing file: {file}")
            else:
                click.echo(f"✗ Failed to download {file}: {result.error}", err=True)
                sys.exit(1)
        else:
            # Transfer multiple files
            click.echo(f"Downloading files with prefix: {prefix or 'all'}")
            results = engine.transfer_all(prefix=prefix, max_files=max_files)
            
            # Display summary
            summary = engine.get_summary()
            click.echo("\n" + "="*50)
            click.echo("Transfer Summary:")
            click.echo(f"  Total files: {summary['total_files']}")
            click.echo(f"  Completed: {summary['completed']}")
            click.echo(f"  Failed: {summary['failed']}")
            click.echo(f"  Skipped: {summary['skipped']}")
            click.echo(f"  Total size: {summary['total_size_bytes']:,} bytes")
            click.echo(f"  Duration: {summary['total_duration_seconds']:.2f} seconds")
            click.echo(f"  Success rate: {summary['success_rate']:.1f}%")
            
            if summary['failed_files']:
                click.echo("\nFailed files:")
                for failed_file in summary['failed_files']:
                    click.echo(f"  - {failed_file}")
            
            # Exit with error if any transfers failed
            if summary['failed'] > 0:
                sys.exit(1)
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error during download")
        sys.exit(1)


@cli.command()
@click.option('--url', '-u', help='Azure Blob Storage URL (uses .env if not provided)')
@click.option('--token', '-t', help='SAS token for authentication')
@click.option('--prefix', '-p', help='Prefix to filter files')
@click.option('--max', '-m', type=int, default=100, help='Maximum files to list')
@click.pass_context
def list_files(ctx, url: Optional[str], token: Optional[str], prefix: Optional[str], max: int):
    """List files in Azure Blob Storage"""
    
    try:
        # Use URL from command line or environment
        if not url:
            url = get_azure_url_from_env()
            if not url:
                click.echo("Error: No URL provided and Azure credentials not found in environment.", err=True)
                click.echo("Either provide --url or set AZURE_STORAGE_URL and AZURE_CONTAINER_NAME in .env", err=True)
                sys.exit(1)
            click.echo(f"Using Azure credentials from .env file")
        
        # Create provider from URL
        provider = AzureBlobProvider.from_url(url, token)
        
        # Validate provider
        if not provider.validate_config():
            click.echo("Failed to validate Azure Blob Storage connection", err=True)
            sys.exit(1)
        
        # List files
        files = provider.list_files(prefix=prefix, max_results=max)
        
        if not files:
            click.echo("No files found")
            return
        
        # Display files
        click.echo(f"Found {len(files)} files:")
        click.echo("-" * 80)
        click.echo(f"{'Name':<50} {'Size':>15} {'Last Modified'}")
        click.echo("-" * 80)
        
        total_size = 0
        for file in files:
            size_str = f"{file.size:,}" if file.size else "0"
            modified_str = file.last_modified.strftime("%Y-%m-%d %H:%M:%S") if file.last_modified else ""
            click.echo(f"{file.name:<50} {size_str:>15} {modified_str}")
            total_size += file.size or 0
        
        click.echo("-" * 80)
        click.echo(f"Total: {len(files)} files, {total_size:,} bytes")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error listing files")
        sys.exit(1)


@cli.command()
@click.option('--url', '-u', help='Azure Blob Storage URL (uses .env if not provided)')
@click.option('--token', '-t', help='SAS token for authentication')
@click.option('--file', '-f', required=True, type=click.Path(exists=True), 
              help='Local file to upload')
@click.option('--destination', '-d', help='Destination path in blob storage')
@click.option('--date-folder', is_flag=True, 
              help='Create and upload to a folder with current date (YYYYMMDD)')
@click.option('--overwrite', is_flag=True, help='Overwrite if file exists')
@click.pass_context
def upload(ctx, url: Optional[str], token: Optional[str], file: str, 
          destination: Optional[str], date_folder: bool, overwrite: bool):
    """Upload a file to Azure Blob Storage"""
    
    try:
        # Use URL from command line or environment
        if not url:
            url = get_azure_url_from_env()
            if not url:
                click.echo("Error: No URL provided and Azure credentials not found in environment.", err=True)
                click.echo("Either provide --url or set AZURE_STORAGE_URL and AZURE_CONTAINER_NAME in .env", err=True)
                sys.exit(1)
            click.echo(f"Using Azure credentials from .env file")
        
        # Create provider from URL
        provider = AzureBlobProvider.from_url(url, token)
        
        # Validate provider
        if not provider.validate_config():
            click.echo("Failed to validate Azure Blob Storage connection", err=True)
            sys.exit(1)
        
        # Get file path
        file_path = Path(file)
        file_name = file_path.name
        
        # Determine destination path
        if date_folder:
            # Create folder with current date
            date_str = datetime.now().strftime('%Y%m%d')
            remote_path = f"{date_str}/{destination or file_name}"
            
            click.echo(f"Creating date folder: {date_str}/")
            if provider.create_folder(date_str):
                click.echo(f"✓ Created folder: {date_str}/")
            else:
                click.echo(f"⊘ Folder may already exist: {date_str}/")
        else:
            remote_path = destination or file_name
        
        # Upload file
        click.echo(f"Uploading '{file}' to '{remote_path}'...")
        
        if provider.upload_file(str(file_path), remote_path, overwrite):
            # Get file size
            file_size = file_path.stat().st_size
            click.echo(f"✓ Successfully uploaded {file_name} ({file_size:,} bytes)")
            click.echo(f"  Destination: {remote_path}")
            
            # Verify upload
            if provider.exists(remote_path):
                metadata = provider.get_metadata(remote_path)
                click.echo(f"  Size in storage: {metadata.size:,} bytes")
                click.echo(f"  Last modified: {metadata.last_modified}")
        else:
            click.echo(f"✗ Failed to upload {file}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error during upload")
        sys.exit(1)


@cli.command()
@click.option('--url', '-u', help='Azure Blob Storage URL (uses .env if not provided)')
@click.option('--token', '-t', help='SAS token for authentication')
@click.option('--source-dir', '-s', required=True, type=click.Path(exists=True),
              help='Source directory to upload')
@click.option('--date-folder', is_flag=True,
              help='Create and upload to a folder with current date (YYYYMMDD)')
@click.option('--pattern', '-p', default='*', help='File pattern to match (e.g., *.txt)')
@click.option('--overwrite', is_flag=True, help='Overwrite existing files')
@click.pass_context
def upload_batch(ctx, url: Optional[str], token: Optional[str], source_dir: str,
                date_folder: bool, pattern: str, overwrite: bool):
    """Upload multiple files to Azure Blob Storage"""
    
    try:
        # Use URL from command line or environment
        if not url:
            url = get_azure_url_from_env()
            if not url:
                click.echo("Error: No URL provided and Azure credentials not found in environment.", err=True)
                click.echo("Either provide --url or set AZURE_STORAGE_URL and AZURE_CONTAINER_NAME in .env", err=True)
                sys.exit(1)
            click.echo(f"Using Azure credentials from .env file")
        
        # Create provider from URL
        provider = AzureBlobProvider.from_url(url, token)
        
        # Validate provider
        if not provider.validate_config():
            click.echo("Failed to validate Azure Blob Storage connection", err=True)
            sys.exit(1)
        
        # Get source directory
        source_path = Path(source_dir)
        
        # Find files matching pattern
        files = list(source_path.glob(pattern))
        
        if not files:
            click.echo(f"No files found matching pattern: {pattern}")
            return
        
        click.echo(f"Found {len(files)} file(s) to upload")
        
        # Create date folder if needed
        date_str = ""
        if date_folder:
            date_str = datetime.now().strftime('%Y%m%d')
            click.echo(f"Creating date folder: {date_str}/")
            if provider.create_folder(date_str):
                click.echo(f"✓ Created folder: {date_str}/")
        
        # Upload each file
        success_count = 0
        total_size = 0
        
        for file_path in files:
            if file_path.is_file():
                file_name = file_path.name
                
                # Determine remote path
                if date_folder:
                    remote_path = f"{date_str}/{file_name}"
                else:
                    remote_path = file_name
                
                click.echo(f"Uploading {file_name}...")
                
                if provider.upload_file(str(file_path), remote_path, overwrite):
                    file_size = file_path.stat().st_size
                    success_count += 1
                    total_size += file_size
                    click.echo(f"  ✓ Uploaded to {remote_path} ({file_size:,} bytes)")
                else:
                    click.echo(f"  ✗ Failed to upload {file_name}", err=True)
        
        # Summary
        click.echo("\n" + "="*50)
        click.echo("Upload Summary:")
        click.echo(f"  Successful uploads: {success_count}/{len(files)}")
        click.echo(f"  Total size uploaded: {total_size:,} bytes")
        if date_folder:
            click.echo(f"  Uploaded to folder: {date_str}/")
        
        if success_count < len(files):
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error during batch upload")
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate configuration"""
    
    try:
        config = ctx.obj['config']
        
        click.echo("Validating configuration...")
        
        # Validate config
        if config.validate():
            click.echo("✓ Configuration is valid")
        else:
            click.echo("✗ Configuration is invalid", err=True)
            sys.exit(1)
        
        # Display configuration
        click.echo("\nCurrent configuration:")
        click.echo(f"  Source type: {config.source_type}")
        click.echo(f"  Destination type: {config.destination_type}")
        click.echo(f"  Batch size: {config.batch_size}")
        click.echo(f"  Retry attempts: {config.retry_attempts}")
        click.echo(f"  Concurrent downloads: {config.concurrent_downloads}")
        click.echo(f"  Overwrite existing: {config.overwrite_existing}")
        
    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()