"""
Download module for Kartograf.

This module contains classes for managing file downloads and storage:
- FileStorage: handles file path generation and storage operations
- DownloadManager: coordinates downloading of sheets and hierarchies
- DownloadProgress: progress information for download operations
"""

from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage

__all__ = ["DownloadManager", "DownloadProgress", "FileStorage"]
