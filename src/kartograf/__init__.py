"""Kartograf - download spatial data of Poland and Czechia into a versioned store.

Elevation (NMT/NMPT grids and archives, LAZ point clouds, CZ contours), imagery
(orthophotomaps, intensity, true and oblique orthophotomaps), land cover (BDOT10k, BDOO,
CORINE, ZABAGED, Data50, Data250), soil (SoilGrids, HSG), boundaries and addresses (PRG,
RUIAN, geomorphology), cadastre (EGiB, RCN, CZ cadastral map), 3D models, hydrography
(HY-NET), geographic names, topographic maps and geodesy (control networks,
quasi-geoids) from GUGiK, CUZK, Copernicus and ISRIC.

Every CLI command has one library function with the same choices and the same
result (ADR-037, ADR-044): ``elevation download`` and ``imagery download`` =
``download_data``/``check_data``, ``elevation availability`` =
``check_availability``, ``landcover download`` =
``download_landcover``/``check_landcover``, ``soil download`` =
``download_soil``/``check_soil``, ``soil hsg`` = ``calculate_hsg``/
``check_hsg`` (``--summary``: ``hsg_statistics``), the collection groups
(``boundaries``, ``cadastre``, ``models3d``, ``hydro``, ``names``, ``maps``,
``geodesy download``) = ``download_collection``/``check_collection``
(ADR-042), ``project`` = ``init_project``, ``add_project_task``,
``remove_project_task``, ``download_project``, ``check_project``,
``get_project_status``, ``verify_project`` (``open_project`` reads a
project, ADR-040). Every data report (``DataReport``, ``CollectionReport``,
``LandCoverReport``, ``SoilReport``, ``HsgReport``) has ``files`` and
``failed`` (``UnitFile``/``UnitFailure``), ``stale``, ``notices`` and ``ok``.
The store is read without writing to it (ADR-045): ``list_segments``,
``list_partitions``, ``iter_store``, ``read_sidecar``, ``describe_segment``,
``file_footprint``, ``link_target`` and ``pinned_transform``.

Every result is a JSON document (ADR-046): ``to_dict()``/``to_json()`` of a
report give the same ``kartograf-<kind>/1`` document as the CLI ``--json``
output and the MCP server ``kartograf-mcp``; an exception becomes a
``kartograf-error/1`` document with ``error_report`` (every ``KartografError``
has a stable ``code``, an ``exit_code`` and a ``hint``). ``list_commands`` and
``command_schema`` describe the commands (the list, and one command with its options
and allowed values);
``parse_command``, ``validate_command``, ``format_command``, ``run_command``
and ``check_command`` work on every command of the catalog as data: the last two
return the ``kartograf-result/1`` envelope (``CommandResult``: ``status``, ``items``,
``notices`` and the report as ``result``), as the CLI ``--json`` prints it. Other
reports of the document family: ``describe_sheet``, ``find_sheets``, ``list_sources``,
``list_layers``, ``get_cache_info``, ``get_cache_path``, ``clear_cache``,
``get_config``, ``store_root`` (the default store root with its source and marker,
without reading the store), ``describe_store``, ``list_store_entries`` and
``read_store_sidecar``.

Example usage::

    from kartograf import (
        BBox,
        DownloadManager,
        GugikProvider,
        SheetParser,
        download_data,
        download_laz_area,
        download_pl_cutout,
    )

    # Parse a map sheet identifier
    parser = SheetParser("N-34-130-D-d-2-4")
    print(f"Scale: {parser.scale}")

    # The `elevation download` / `imagery download` commands: files, failures,
    # notices, ok
    report = download_data(
        product="nmt",
        root="./data",
        sheet="N-34-130-D-d-2-4",
        resolution="1m",
        vertical_crs="EVRF2007",
    )
    print([item.file.path for item in report.files], report.ok)

    # Which years/resolutions an area has as a complete set of full sheets
    # (`elevation availability`): index and PRG only, nothing is downloaded
    from kartograf import check_availability
    availability = check_availability(
        product="nmt",
        country="pl",
        bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
    )
    newest = next(c for c in availability.combinations if c.complete)
    print(newest.year, newest.resolution, newest.download_hint[0])

    # Download NMT data (one sheet from GUGiK OpenData); every data choice
    # (product, resolution, vertical CRS, output) is explicit
    provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
    manager = DownloadManager(provider, root="./data")
    result = manager.download_sheet("N-34-130-D-d-2-4")
    print(result.files["N-34-130-D-d-2-4"][0].version_path)

    # LAZ tiles for an area: newest per area, sidecars, failures in result
    laz = download_laz_area(
        bbox=BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        root="./data",
        vertical_crs="EVRF2007",
    )

    # One NMT GeoTIFF for an area (PL cutout from GUGiK WCS, ADR-035)
    result = download_pl_cutout(
        bbox=BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        horizontal_crs="EPSG:2180",
        root="./data",
        vertical_crs="EVRF2007",
        product="nmt",
    )

    # Land cover and HSG in the same store (versions, report with the files)
    from kartograf import calculate_hsg, download_landcover
    lc = download_landcover(product="bdot10k", root="./data", teryt="1465")
    print(lc.files[0].file.path, lc.ok)  # data/landcover/pl_bdot10k_gpkg/...
    hsg = calculate_hsg(root="./data", sheet="N-34-130-D", depth="0-5cm")
    print(hsg.files[0].file.path, hsg.files[0].file.label)  # SoilGrids edition
"""

from kartograf.cache.metadata import MetadataCache
from kartograf.cache_info import CacheInfo, clear_cache, get_cache_info, get_cache_path
from kartograf.catalog import command_schema, list_commands
from kartograf.catalog.model import CommandCatalog, CommandList
from kartograf.commands import (
    CommandCall,
    check_command,
    format_command,
    parse_command,
    run_command,
    validate_command,
)
from kartograf.config import Config, StoreRoot, get_config, store_root
from kartograf.core.bbox import BBox, transform_bbox
from kartograf.core.geometry import find_sheets_for_geometry, get_overall_bbox
from kartograf.core.parser_2000 import Parser2000, find_sheets_2000_for_bbox
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.download.area import parent_request_for
from kartograf.download.availability import (
    AvailabilityArea,
    AvailabilityCampaign,
    AvailabilityCombination,
    AvailabilityRecord,
    AvailabilityReport,
    check_availability,
)
from kartograf.download.campaigns import CampaignRef
from kartograf.download.collections import (
    CollectionReport,
    check_collection,
    download_collection,
)
from kartograf.download.countries import (
    CountryPart,
    countries_for_bbox,
    split_bbox_by_country,
)
from kartograf.download.cutout import (
    PlCutoutResult,
    check_pl_cutout,
    download_pl_cutout,
)
from kartograf.download.cz_cutout import (
    CzCutoutResult,
    check_cz_cutout,
    download_cz_cutout,
)
from kartograf.download.cz_laz import (
    CzLazFailure,
    CzLazResult,
    check_cz_laz,
    download_cz_laz,
)
from kartograf.download.cz_orto import (
    CzOrtoResult,
    check_cz_orto_sheet,
    download_cz_orto_sheet,
)
from kartograf.download.cz_sheets import (
    CzSheetResult,
    check_cz_sheet,
    download_cz_sheet,
)
from kartograf.download.data import (
    DataReport,
    UnitFailure,
    UnitFile,
    check_data,
    download_data,
)
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.laz import (
    LazDownloadResult,
    LazTileFailure,
    check_laz_area,
    download_laz_area,
)
from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
from kartograf.download.orto_cutout import (
    ImageCutoutResult,
    check_image_cutout,
    download_image_cutout,
)
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.download.storage import FileStorage
from kartograf.download.versions import VersionRef
from kartograf.envelope import CommandResult, ResultItem
from kartograf.error_report import ErrorReport, error_report
from kartograf.exceptions import (
    CacheError,
    ConfigError,
    ConflictError,
    DownloadError,
    ForbiddenError,
    InvalidLayoutError,
    InvalidSidecarError,
    KartografError,
    MissingDependencyError,
    NoCoverageError,
    ParseError,
    StoreUnavailableError,
    UsageError,
    ValidationError,
    YearRangeError,
)
from kartograf.guide import AgentGuide, agent_guide
from kartograf.hydrology.hsg import (
    HsgReport,
    calculate_hsg,
    check_hsg,
    hsg_from_rasters,
    hsg_statistics,
)
from kartograf.landcover.manager import (
    LandCoverReport,
    SoilReport,
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
)
from kartograf.marker import StoreInit, check_store, init_store
from kartograf.notices import Notice
from kartograf.project import (
    FileCheck,
    PinnedFile,
    Project,
    ProjectCheck,
    ProjectReport,
    ProjectTask,
    TaskResult,
    add_project_task,
    check_project,
    download_project,
    get_project_status,
    init_project,
    open_project,
    remove_project_task,
    verify_project,
)
from kartograf.providers.base import BaseProvider, LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.cuzk import (
    CuzkLazProvider,
    CuzkRasterProvider,
    create_cz_raster_provider,
)
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
from kartograf.sheet_info import SheetInfo, SheetList, describe_sheet, find_sheets
from kartograf.source_info import (
    LayerList,
    SourceList,
    list_layers,
    list_sources,
)
from kartograf.sources.edition import Edition
from kartograf.store import (
    SegmentInfo,
    Sidecar,
    StoreEntry,
    describe_segment,
    iter_store,
    link_target,
    list_partitions,
    list_segments,
    read_sidecar,
)
from kartograf.store_documents import (
    StoreEntries,
    StoreOverview,
    StoreSidecar,
    describe_store,
    list_store_entries,
    read_store_sidecar,
)
from kartograf.store_geometry import Footprint, file_footprint, pinned_transform
from kartograf.transform.crs import PinnedTransform
from kartograf.transport.http import get_with_retry, make_gugik_session
from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

__version__ = "0.8.0.dev0"

__all__ = [
    # Cache
    "MetadataCache",
    # Notices
    "Notice",
    # Core
    "SheetParser",
    "Parser2000",
    "ParserTM33",
    "BBox",
    "find_sheets_for_bbox",
    "find_sheets_2000_for_bbox",
    "find_sheets_for_geometry",
    "get_overall_bbox",
    "transform_bbox",
    "parent_request_for",
    # Download (command level: `elevation download` / `imagery download`, spec 4.1)
    "download_data",
    "check_data",
    "DataReport",
    "UnitFile",
    "UnitFailure",
    # Download (collections: `boundaries`, `cadastre`, `models3d`, `hydro`,
    # `names`, `maps`, `geodesy download`; ADR-042)
    "download_collection",
    "check_collection",
    "CollectionReport",
    # Availability report (`elevation availability`, ADR-041)
    "check_availability",
    "AvailabilityReport",
    "AvailabilityCombination",
    "AvailabilityRecord",
    "AvailabilityCampaign",
    "AvailabilityArea",
    # Download (NMT)
    "DownloadManager",
    "DownloadProgress",
    "DownloadResult",
    "CampaignRef",
    "FileStorage",
    # Download (versioned store, update plan)
    "UpdateMode",
    "VersionedFile",
    "VersionRef",
    "PlanItem",
    "UpdatePlan",
    # Download (PL cutout: WCS ADR-035)
    "PlCutoutResult",
    "check_pl_cutout",
    "download_pl_cutout",
    # Download (PL image cutout: orthophotomap WCS Standard/High, true
    # orthophotomap; ADR-042 D14, ADR-044)
    "ImageCutoutResult",
    "check_image_cutout",
    "download_image_cutout",
    # Download (CZ cutout, countries)
    "CountryPart",
    "countries_for_bbox",
    "split_bbox_by_country",
    "CzCutoutResult",
    "check_cz_cutout",
    "download_cz_cutout",
    # Download (CZ sheet: SM5 sheet / TM33 tile, R4)
    "CzSheetResult",
    "check_cz_sheet",
    "download_cz_sheet",
    # Download (LAZ CZ: CUZK point clouds, plan B)
    "CzLazFailure",
    "CzLazResult",
    "check_cz_laz",
    "download_cz_laz",
    # Download (CZ orthophoto: SM5 sheet, JPEG + world files, ADR-042 D13)
    "CzOrtoResult",
    "check_cz_orto_sheet",
    "download_cz_orto_sheet",
    # Download (LAZ tiles, D17)
    "LazDownloadResult",
    "LazTileFailure",
    "check_laz_area",
    "download_laz_area",
    # Land cover and soil (`landcover download`, `soil download`, ADR-044)
    "download_landcover",
    "check_landcover",
    "LandCoverReport",
    "download_soil",
    "check_soil",
    "SoilReport",
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
    "CuzkRasterProvider",
    "CuzkLazProvider",
    "create_cz_raster_provider",
    # TERYT (PRG)
    "discover_teryts_for_bbox",
    "teryt_for_point",
    # Hydrology (`soil hsg`, ADR-044)
    "calculate_hsg",
    "check_hsg",
    "HsgReport",
    "hsg_statistics",
    "hsg_from_rasters",
    # Project manifest (kartograf-project.json, ADR-040)
    "init_project",
    "open_project",
    "add_project_task",
    "remove_project_task",
    "download_project",
    "check_project",
    "get_project_status",
    "verify_project",
    "Project",
    "ProjectTask",
    "PinnedFile",
    "ProjectReport",
    "TaskResult",
    "ProjectCheck",
    "FileCheck",
    # Transport and mosaic (stable since 0.7.1)
    "get_with_retry",
    "make_gugik_session",
    "mosaic_and_crop",
    "check_source_grid",
    # Store reading, without writing to it (Archiwista, ADR-045)
    "list_segments",
    "list_partitions",
    "iter_store",
    "StoreEntry",
    "read_sidecar",
    "Sidecar",
    "describe_segment",
    "SegmentInfo",
    "describe_store",
    "init_store",
    "check_store",
    "StoreInit",
    "StoreOverview",
    "list_store_entries",
    "StoreEntries",
    "read_store_sidecar",
    "StoreSidecar",
    "file_footprint",
    "Footprint",
    "link_target",
    "pinned_transform",
    "PinnedTransform",
    # Exceptions
    "KartografError",
    "ParseError",
    "ValidationError",
    "UsageError",
    "DownloadError",
    "NoCoverageError",
    "YearRangeError",
    "CacheError",
    "ConfigError",
    "InvalidSidecarError",
    "InvalidLayoutError",
    "StoreUnavailableError",
    "ConflictError",
    "ForbiddenError",
    "MissingDependencyError",
    # Sources, layers and the metadata cache as data (spec 5.4.6-5.4.9)
    "list_sources",
    "SourceList",
    "list_layers",
    "LayerList",
    "get_cache_info",
    "get_cache_path",
    "clear_cache",
    "CacheInfo",
    # The user settings as data (DEV-18.6)
    "get_config",
    "Config",
    "store_root",
    "StoreRoot",
    # Sheet codes and the catalog of the commands as data (spec 5.4.4, 5.4.5, 8.5)
    "describe_sheet",
    "SheetInfo",
    "find_sheets",
    "SheetList",
    "list_commands",
    "command_schema",
    "CommandList",
    "CommandCatalog",
    "agent_guide",
    "AgentGuide",
    # The command layer: a data command as data (spec 8.7; KB-2..KB-5)
    "CommandCall",
    "parse_command",
    "validate_command",
    "format_command",
    "run_command",
    "check_command",
    "CommandResult",
    "ResultItem",
    # Errors as data (`kartograf-error/1`, spec 6)
    "ErrorReport",
    "error_report",
    # Version
    "__version__",
]
