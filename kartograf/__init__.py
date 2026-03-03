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

from kartograf.cache.metadata import MetadataCache
from kartograf.core.geometry import find_sheets_for_geometry
from kartograf.core.parser_2000 import Parser2000, find_sheets_2000_for_bbox
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.hydrology.hsg import HSGCalculator
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.base import BaseProvider
from kartograf.providers.bdot10k import Bdot10kProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.gugik import GugikProvider
from kartograf.providers.gugik_nmpt import GugikNmptProvider
from kartograf.providers.gugik_orto import GugikOrtoProvider
from kartograf.providers.landcover_base import LandCoverProvider
from kartograf.providers.soilgrids import SoilGridsProvider

__version__ = "0.5.0"

__all__ = [
    # Cache
    "MetadataCache",
    # Core
    "SheetParser",
    "Parser2000",
    "BBox",
    "find_sheets_for_bbox",
    "find_sheets_2000_for_bbox",
    "find_sheets_for_geometry",
    # Download (NMT)
    "DownloadManager",
    "DownloadProgress",
    "DownloadResult",
    "FileStorage",
    # Land Cover
    "LandCoverManager",
    # Providers
    "BaseProvider",
    "GugikProvider",
    "GugikNmptProvider",
    "GugikOrtoProvider",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
    # Hydrology
    "HSGCalculator",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "DownloadError",
    # Version
    "__version__",
]
