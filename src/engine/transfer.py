"""Transfer engine for orchestrating file transfers"""

import logging
import time
from io import BytesIO
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

from ..storage_src.base import StorageProvider, FileMetadata
from ..storage_dest.base import StorageDestination
from .config import TransferConfig

logger = logging.getLogger(__name__)


class TransferStatus(Enum):
    """Status of a transfer operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TransferResult:
    """Result of a single file transfer"""
    source_path: str
    destination_path: str
    status: TransferStatus
    size: Optional[int] = None
    error: Optional[str] = None
    duration: Optional[float] = None


class TransferEngine:
    """Engine for orchestrating transfers between storage providers and destinations"""
    
    def __init__(self, provider: StorageProvider, destination: StorageDestination, 
                 config: TransferConfig):
        """Initialize the transfer engine
        
        Args:
            provider: Storage provider to download from
            destination: Storage destination to save to
            config: Transfer configuration
        """
        self.provider = provider
        self.destination = destination
        self.config = config
        self.results: List[TransferResult] = []
    
    def transfer_file(self, source_path: str, destination_path: Optional[str] = None,
                     overwrite: Optional[bool] = None) -> TransferResult:
        """Transfer a single file
        
        Args:
            source_path: Path to the file in the source storage
            destination_path: Optional destination path (uses source path if not provided)
            overwrite: Whether to overwrite existing files (uses config default if not specified)
            
        Returns:
            TransferResult object
        """
        start_time = time.time()
        
        if destination_path is None:
            destination_path = source_path
        
        if overwrite is None:
            overwrite = self.config.overwrite_existing
        
        # Check if file already exists at destination
        if not overwrite and self.destination.exists(destination_path):
            logger.info(f"Skipping existing file: {destination_path}")
            return TransferResult(
                source_path=source_path,
                destination_path=destination_path,
                status=TransferStatus.SKIPPED,
                duration=time.time() - start_time
            )
        
        try:
            # Get file metadata
            metadata = self.provider.get_metadata(source_path)
            
            # Download file to memory buffer
            buffer = BytesIO()
            self.provider.download_file(source_path, buffer)
            buffer.seek(0)
            
            # Save to destination
            success = self.destination.save_file(
                destination_path, 
                buffer,
                metadata={
                    'source': source_path,
                    'size': metadata.size,
                    'last_modified': str(metadata.last_modified),
                    'content_type': metadata.content_type
                }
            )
            
            if success:
                logger.info(f"Successfully transferred: {source_path} -> {destination_path}")
                return TransferResult(
                    source_path=source_path,
                    destination_path=destination_path,
                    status=TransferStatus.COMPLETED,
                    size=metadata.size,
                    duration=time.time() - start_time
                )
            else:
                return TransferResult(
                    source_path=source_path,
                    destination_path=destination_path,
                    status=TransferStatus.FAILED,
                    error="Failed to save file to destination",
                    duration=time.time() - start_time
                )
                
        except Exception as e:
            logger.error(f"Error transferring {source_path}: {e}")
            return TransferResult(
                source_path=source_path,
                destination_path=destination_path,
                status=TransferStatus.FAILED,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def transfer_with_retry(self, source_path: str, 
                           destination_path: Optional[str] = None) -> TransferResult:
        """Transfer a file with retry logic
        
        Args:
            source_path: Path to the file in the source storage
            destination_path: Optional destination path
            
        Returns:
            TransferResult object
        """
        last_result = None
        
        for attempt in range(self.config.retry_attempts + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt} for {source_path}")
                time.sleep(self.config.retry_delay)
            
            result = self.transfer_file(source_path, destination_path)
            last_result = result
            
            if result.status in [TransferStatus.COMPLETED, TransferStatus.SKIPPED]:
                return result
        
        logger.error(f"Failed to transfer {source_path} after {self.config.retry_attempts} retries")
        return last_result
    
    def transfer_batch(self, file_pairs: List[Tuple[str, Optional[str]]]) -> List[TransferResult]:
        """Transfer multiple files in parallel
        
        Args:
            file_pairs: List of (source_path, destination_path) tuples
            
        Returns:
            List of TransferResult objects
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.concurrent_downloads) as executor:
            # Submit all transfer tasks
            future_to_file = {
                executor.submit(self.transfer_with_retry, src, dest): (src, dest)
                for src, dest in file_pairs
            }
            
            # Process completed transfers
            for future in as_completed(future_to_file):
                src, dest = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    self.results.append(result)
                except Exception as e:
                    logger.error(f"Unexpected error transferring {src}: {e}")
                    result = TransferResult(
                        source_path=src,
                        destination_path=dest or src,
                        status=TransferStatus.FAILED,
                        error=str(e)
                    )
                    results.append(result)
                    self.results.append(result)
        
        return results
    
    def transfer_all(self, prefix: Optional[str] = None, 
                    max_files: Optional[int] = None) -> List[TransferResult]:
        """Transfer all files from the source
        
        Args:
            prefix: Optional prefix to filter files
            max_files: Maximum number of files to transfer
            
        Returns:
            List of TransferResult objects
        """
        # List all files from the source
        files = self.provider.list_files(prefix=prefix, max_results=max_files)
        logger.info(f"Found {len(files)} files to transfer")
        
        if not files:
            logger.warning("No files found to transfer")
            return []
        
        # Create file pairs for transfer
        file_pairs = [(f.name, None) for f in files]
        
        # Process in batches
        all_results = []
        for i in range(0, len(file_pairs), self.config.batch_size):
            batch = file_pairs[i:i + self.config.batch_size]
            logger.info(f"Processing batch {i//self.config.batch_size + 1} "
                       f"({len(batch)} files)")
            batch_results = self.transfer_batch(batch)
            all_results.extend(batch_results)
        
        return all_results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all transfer operations
        
        Returns:
            Dictionary with transfer statistics
        """
        total = len(self.results)
        completed = sum(1 for r in self.results if r.status == TransferStatus.COMPLETED)
        failed = sum(1 for r in self.results if r.status == TransferStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TransferStatus.SKIPPED)
        
        total_size = sum(r.size for r in self.results 
                        if r.size and r.status == TransferStatus.COMPLETED)
        total_duration = sum(r.duration for r in self.results if r.duration)
        
        return {
            'total_files': total,
            'completed': completed,
            'failed': failed,
            'skipped': skipped,
            'total_size_bytes': total_size,
            'total_duration_seconds': total_duration,
            'success_rate': (completed / total * 100) if total > 0 else 0,
            'failed_files': [r.source_path for r in self.results 
                           if r.status == TransferStatus.FAILED]
        }
    
    def clear_results(self) -> None:
        """Clear all transfer results"""
        self.results.clear()