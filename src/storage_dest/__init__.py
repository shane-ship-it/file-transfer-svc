"""Storage destinations module"""

from .base import StorageDestination
from .local_fs import LocalFileSystemDestination

__all__ = ['StorageDestination', 'LocalFileSystemDestination']