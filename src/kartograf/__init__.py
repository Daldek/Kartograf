"""
Kartograf - Tool for downloading NMT data from GUGiK.

This package provides tools for downloading Digital Terrain Model (NMT)
data from the Polish GUGiK (Główny Urząd Geodezji i Kartografii) service.

Example usage::

    from kartograf import SheetParser, DownloadManager

    # Parse a map sheet identifier
    parser = SheetParser("N-34-130-D-d-2-4")
    print(f"Scale: {parser.scale}")

    # Download NMT data
    manager = DownloadManager(output_dir="./data")
    path = manager.download_sheet("N-34-130-D-d-2-4")
"""

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.providers.base import BaseProvider
from kartograf.providers.gugik import GugikProvider

__version__ = "0.1.0"

__all__ = [
    # Core
    "SheetParser",
    # Download
    "DownloadManager",
    "DownloadProgress",
    "FileStorage",
    # Providers
    "BaseProvider",
    "GugikProvider",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "DownloadError",
    # Version
    "__version__",
]
