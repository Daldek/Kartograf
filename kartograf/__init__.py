"""
Kartograf - Tool for downloading spatial data from GUGiK.

This package provides tools for downloading Digital Terrain Model (NMT)
and Land Cover data from Polish GUGiK (Główny Urząd Geodezji i Kartografii)
and European Copernicus services.

Example usage::

    from kartograf import SheetParser, DownloadManager

    # Parse a map sheet identifier
    parser = SheetParser("N-34-130-D-d-2-4")
    print(f"Scale: {parser.scale}")

    # Download NMT data
    manager = DownloadManager(output_dir="./data")
    path = manager.download_sheet("N-34-130-D-d-2-4")

    # Download Land Cover data
    from kartograf import LandCoverManager
    lc_manager = LandCoverManager()
    lc_manager.download(godlo="N-34-130-D")
"""

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.base import BaseProvider
from kartograf.providers.bdot10k import Bdot10kProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.gugik import GugikProvider
from kartograf.providers.landcover_base import LandCoverProvider

__version__ = "0.3.1"

__all__ = [
    # Core
    "SheetParser",
    "BBox",
    # Download (NMT)
    "DownloadManager",
    "DownloadProgress",
    "FileStorage",
    # Land Cover
    "LandCoverManager",
    # Providers
    "BaseProvider",
    "GugikProvider",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "DownloadError",
    # Version
    "__version__",
]
