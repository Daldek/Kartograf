"""
Kartograf - download spatial data: NMT/NMPT/orthophoto/LAZ from GUGiK (PL),
DMR 5G/4G from CUZK (CZ), BDOT10k, CORINE (Copernicus) and SoilGrids (ISRIC).

Example usage::

    from kartograf import (
        BBox,
        DownloadManager,
        GugikProvider,
        SheetParser,
        download_laz_area,
        download_pl_cutout,
    )

    # Parse a map sheet identifier
    parser = SheetParser("N-34-130-D-d-2-4")
    print(f"Scale: {parser.scale}")

    # Download NMT data (one sheet from GUGiK OpenData); every data choice
    # (product, resolution, vertical CRS, output) is explicit
    provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
    manager = DownloadManager("./data", provider)
    path = manager.download_sheet("N-34-130-D-d-2-4")

    # LAZ tiles for an area: newest per area, sidecars, failures in result
    laz = download_laz_area(
        BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        output_dir="./data",
        vertical_crs="EVRF2007",
    )

    # One NMT GeoTIFF for an area (PL cutout from GUGiK WCS, ADR-035)
    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        "EPSG:2180",
        output_dir="./data",
        vertical_crs="EVRF2007",
        product="nmt",
    )

    # Land cover and HSG in the same store (versions, result with the file)
    from kartograf import HSGCalculator, LandCoverManager
    lc = LandCoverManager("./data", "bdot10k").download(teryt="1465")
    print(lc.file.path, lc.file.status)  # data/landcover/pl_bdot10k_gpkg/...
    hsg = HSGCalculator("./data").calculate_hsg_by_sheet(
        "N-34-130-D", depth="0-5cm", stat="mean"
    )
    print(hsg.file.path, hsg.file.label)  # data/hsg/..., SoilGrids edition
"""

from kartograf.cache.metadata import MetadataCache
from kartograf.core.geometry import find_sheets_for_geometry
from kartograf.core.parser_2000 import Parser2000, find_sheets_2000_for_bbox
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.campaigns import CampaignRef
from kartograf.download.countries import (
    CountryPart,
    countries_for_bbox,
    split_bbox_by_country,
)
from kartograf.download.cutout import (
    PlCutout,
    PlCutoutResult,
    check_pl_cutout,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_wcs_cutout,
)
from kartograf.download.cz_cutout import (
    CzCutoutResult,
    check_cz_cutout,
    download_cz_cutout,
    run_cz_cutout,
)
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.laz import (
    LazDownloadResult,
    LazTileFailure,
    check_laz_updates,
    download_laz_area,
    run_laz_download,
)
from kartograf.download.manager import (
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    SheetFetch,
)
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.download.storage import FileStorage
from kartograf.download.updates import (
    UpgradeReport,
    check_updates,
    upgrade,
)
from kartograf.download.versions import VersionRef
from kartograf.exceptions import (
    CacheError,
    DownloadError,
    KartografError,
    NoCoverageError,
    ParseError,
    ValidationError,
    YearRangeError,
)
from kartograf.hydrology.hsg import HSGCalculator, HsgResult, hsg_from_rasters
from kartograf.landcover.manager import (
    LandCoverAreaResult,
    LandCoverFailure,
    LandCoverManager,
    LandCoverResult,
)
from kartograf.providers.base import BaseProvider, LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.cuzk import CuzkDmrProvider, create_dmr_provider
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import (
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.pl.prg import discover_teryts_for_bbox, teryt_for_point
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.edition import Edition
from kartograf.transport.http import get_with_retry, make_gugik_session
from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

__version__ = "0.8.0-dev"

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
    # Download (versioned store, update plan)
    "UpdateMode",
    "VersionedFile",
    "VersionRef",
    "PlanItem",
    "UpdatePlan",
    "UpgradeReport",
    "check_updates",
    "upgrade",
    # Download (PL cutout: WCS ADR-035)
    "PlCutout",
    "PlCutoutResult",
    "check_pl_cutout",
    "download_pl_cutout",
    "prepare_pl_cutout",
    "run_pl_wcs_cutout",
    # Download (CZ cutout, countries)
    "CountryPart",
    "countries_for_bbox",
    "split_bbox_by_country",
    "CzCutoutResult",
    "check_cz_cutout",
    "download_cz_cutout",
    "run_cz_cutout",
    # Download (LAZ tiles, D17)
    "LazDownloadResult",
    "LazTileFailure",
    "check_laz_updates",
    "download_laz_area",
    "run_laz_download",
    # Land Cover
    "LandCoverManager",
    "LandCoverResult",
    "LandCoverAreaResult",
    "LandCoverFailure",
    "Edition",
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
    "Bdot10kPackage",
    "CorineProvider",
    "SoilGridsProvider",
    "CuzkDmrProvider",
    "create_dmr_provider",
    # TERYT (PRG)
    "discover_teryts_for_bbox",
    "teryt_for_point",
    # Hydrology
    "HSGCalculator",
    "HsgResult",
    "hsg_from_rasters",
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
    "YearRangeError",
    "CacheError",
    # Version
    "__version__",
]
