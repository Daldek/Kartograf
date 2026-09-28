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
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    NoCoverageError,
    ParseError,
    ValidationError,
)
from kartograf.hydrology.hsg import HSGCalculator
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.base import BaseProvider, LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.cuzk import CuzkDmrProvider, create_dmr_provider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.soilgrids import SoilGridsProvider

__version__ = "0.7.0-dev"

__all__ = [
    # Cache
    "MetadataCache",
    # Core
    "SheetParser",
    "Parser2000",
    "ParserTM33",
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
    "GugikLazProvider",
    "LazTile",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
    "CuzkDmrProvider",
    "create_dmr_provider",
    # Hydrology
    "HSGCalculator",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "DownloadError",
    "NoCoverageError",
    # Version
    "__version__",
]
