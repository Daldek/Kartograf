"""
Kartograf - download spatial data: NMT/NMPT/orthophoto/LAZ from GUGiK (PL),
DMR 5G/4G from CUZK (CZ), BDOT10k, CORINE (Copernicus) and SoilGrids (ISRIC).

Example usage::

    from kartograf import (
        BBox, DownloadManager, SheetParser, download_laz_area, download_pl_cutout
    )

    # Parse a map sheet identifier
    parser = SheetParser("N-34-130-D-d-2-4")
    print(f"Scale: {parser.scale}")

    # Download NMT data (one sheet from GUGiK OpenData)
    manager = DownloadManager(output_dir="./data")
    path = manager.download_sheet("N-34-130-D-d-2-4")

    # LAZ tiles for an area: newest per area, sidecars, failures in result
    laz = download_laz_area(BBox(637400, 487000, 637450, 487050, "EPSG:2180"))

    # One merged NMT GeoTIFF for an area (PL cutout, ADR-027)
    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"), "EPSG:2180"
    )

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
from kartograf.download.campaigns import CampaignRef
from kartograf.download.cutout import (
    PlCutout,
    PlCutoutResult,
    PlCutoutSheets,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_cutout,
    select_pl_cutout_sheets,
)
from kartograf.download.laz import (
    LazDownloadResult,
    LazTileFailure,
    download_laz_area,
    run_laz_download,
)
from kartograf.download.manager import (
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    SheetFetch,
)
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    CacheError,
    DownloadError,
    GridMismatchError,
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
from kartograf.providers.pl.gugik_laz import (
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.transport.http import get_with_retry, make_gugik_session
from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

__version__ = "0.7.1-dev"

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
    "SheetFetch",
    "CampaignRef",
    "FileStorage",
    # Download (PL cutout, ADR-027)
    "PlCutout",
    "PlCutoutResult",
    "PlCutoutSheets",
    "download_pl_cutout",
    "prepare_pl_cutout",
    "run_pl_cutout",
    "select_pl_cutout_sheets",
    # Download (LAZ tiles, D17)
    "LazDownloadResult",
    "LazTileFailure",
    "download_laz_area",
    "run_laz_download",
    # Land Cover
    "LandCoverManager",
    # Providers
    "BaseProvider",
    "GugikProvider",
    "GugikNmptProvider",
    "GugikOrtoProvider",
    "GugikLazProvider",
    "LazTile",
    "LazTileSelection",
    "SupersededLazTile",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
    "CuzkDmrProvider",
    "create_dmr_provider",
    # Hydrology
    "HSGCalculator",
    # Transport and mosaic (stable since 0.7.1)
    "get_with_retry",
    "make_gugik_session",
    "mosaic_and_crop",
    "check_source_grid",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "DownloadError",
    "NoCoverageError",
    "GridMismatchError",
    "CacheError",
    # Version
    "__version__",
]
