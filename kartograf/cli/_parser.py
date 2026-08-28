"""
Argument parser definition for the Kartograf CLI.

This module builds the top-level ``argparse`` parser together with all
subcommand parsers (parse, download, landcover, soilgrids, cache).
"""

import argparse

from kartograf import __version__


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="kartograf",
        description=(
            "Tool for downloading spatial data from GUGiK (PL) and CUZK (CZ): "
            "DEM/NMT, NMPT, orthophoto, LAZ, BDOT10k, CORINE, SoilGrids"
        ),
        epilog="Example: kartograf parse N-34-130-D --hierarchy",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse and display information about a map sheet",
        description="Parse a map sheet identifier (godlo) and display its properties",
    )
    parse_parser.add_argument(
        "godlo",
        help="Map sheet identifier (e.g., N-34-130-D, N-34-130-D-d-2-4)",
    )
    parse_parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="Display the full hierarchy from this sheet up to 1:1000000",
    )
    parse_parser.add_argument(
        "--children",
        action="store_true",
        help="Display direct children of this sheet",
    )
    parse_parser.add_argument(
        "--descendants",
        metavar="SCALE",
        help="Display all descendants to target scale (e.g., 1:10000)",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Download geospatial data from GUGiK",
        description=(
            "Download geospatial data from GUGiK: NMT (terrain), NMPT (surface), "
            "or orthophoto. Dla PL --bbox/--geometry rozwija sie na arkusze "
            "zrodlowe, a z --target-crs daje JEDEN scalony wycinek (ADR-027); "
            "dla CZ --bbox/--geometry zawsze zwraca jeden wycinek (exportImage "
            "w ukladzie natywnym EPSG:5514) — dane zrodlowe 1:1 daje tryb "
            "godlowy (TM33/SM5)."
        ),
    )
    download_parser.add_argument(
        "godlo",
        nargs="?",
        default=None,
        help="Map sheet identifier (e.g., N-34-130-D-d-2-4)",
    )
    download_parser.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Bounding box: min_x,min_y,max_x,max_y (default CRS: EPSG:2180)",
    )
    download_parser.add_argument(
        "--bbox-crs",
        choices=[
            "EPSG:2180",
            "EPSG:4326",
            "EPSG:2176",
            "EPSG:2177",
            "EPSG:2178",
            "EPSG:2179",
            "EPSG:5514",
            "EPSG:3045",
        ],
        default="EPSG:2180",
        help="CRS for --bbox coordinates (default: EPSG:2180)",
    )
    download_parser.add_argument(
        "--country",
        choices=["pl", "cz", "auto"],
        default="auto",
        help="Kraj zrodla danych: pl (GUGiK), cz (CUZK) lub auto — wykrywany "
        "z godla/bboxa; bbox przecinajacy oba kraje pobiera osobne pliki "
        "per kraj (default: auto)",
    )
    download_parser.add_argument(
        "--target-crs",
        choices=["EPSG:2180", "EPSG:5514", "EPSG:3045"],
        default=None,
        help="Reprojekcja wyniku, wykonywana lokalnie przypieta operacja "
        "(tylko tryb --bbox/--geometry, tylko --product nmt; PL: jeden "
        "scalony wycinek GeoTIFF — w trybie --geometry obejmuje CALA "
        "obwiednie geometrii, bez maskowania do obiektow; nodata tam, "
        "gdzie nie siega zaden pobrany arkusz; CZ: wycinek exportImage)",
    )
    download_parser.add_argument(
        "--scale",
        metavar="SCALE",
        help="Download all descendants to target scale (e.g., 1:10000)",
    )
    download_parser.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default="./data",
        help="Output directory (default: ./data)",
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    download_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    download_parser.add_argument(
        "--vertical-crs",
        choices=["KRON86", "EVRF2007", "Bpv"],
        default=None,
        help="Uklad pionowy: PL default EVRF2007 (lub KRON86); CZ default Bpv "
        "(natywny) lub EVRF2007 (transformacja +0,12..0,14 m)",
    )
    download_parser.add_argument(
        "--resolution",
        "-r",
        choices=["1m", "5m", "2m"],
        default=None,
        help="Rozdzielczosc siatki: PL 1m/5m (default 1m), CZ 2m/5m (default 2m)",
    )
    download_parser.add_argument(
        "--product",
        choices=["nmt", "nmpt", "orto", "laz"],
        default="nmt",
        help="Data product: nmt (terrain), nmpt (surface), "
        "orto (orthophoto), laz (LIDAR point cloud). Default: nmt",
    )
    download_parser.add_argument(
        "--year",
        type=int,
        metavar="YYYY",
        help="LAZ only: restrict to a single acquisition year "
        "(default: newest available per tile)",
    )
    download_parser.add_argument(
        "--min-density",
        type=int,
        metavar="N",
        help="LAZ only: keep tiles with point density >= N points/m²",
    )
    download_parser.add_argument(
        "--geometry",
        metavar="FILE",
        help="Geometry file (SHP or GPKG) — download tiles intersecting features",
    )
    download_parser.add_argument(
        "--layer",
        metavar="NAME",
        help="Layer name for multi-layer GPKG (default: first layer)",
    )
    download_parser.add_argument(
        "--system",
        choices=["1992", "2000"],
        default=None,
        help="System godlowania dla --bbox/--geometry — tylko PL (default: 1992)",
    )
    download_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of parallel download threads (default: 4). "
        "Use 1 for sequential downloads.",
    )

    # Landcover command group
    landcover_parser = subparsers.add_parser(
        "landcover",
        help="Download land cover data (BDOT10k, CORINE)",
        description="Download land cover / soil data from BDOT10k, CORINE or SoilGrids",
    )
    landcover_subparsers = landcover_parser.add_subparsers(
        dest="landcover_command",
        help="Land cover commands",
    )

    # Landcover download command
    lc_download = landcover_subparsers.add_parser(
        "download",
        help="Download land cover data",
        description="Download land cover data from selected source",
    )
    lc_download.add_argument(
        "--source",
        "-s",
        choices=["bdot10k", "corine", "soilgrids"],
        default="bdot10k",
        help="Data source (default: bdot10k)",
    )
    lc_download.add_argument(
        "--teryt",
        metavar="CODE",
        help="TERYT code (4-digit powiat code, e.g., 1465)",
    )
    lc_download.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Bounding box: min_x,min_y,max_x,max_y in EPSG:2180",
    )
    lc_download.add_argument(
        "--godlo",
        metavar="GODLO",
        help="Map sheet identifier (e.g., N-34-130-D)",
    )
    lc_download.add_argument(
        "--year",
        type=int,
        default=2018,
        help="Reference year for CORINE (default: 2018)",
    )
    lc_download.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default="./data/landcover",
        help="Output directory (default: ./data/landcover)",
    )
    lc_download.add_argument(
        "--format",
        "-f",
        choices=["GPKG", "SHP"],
        default="GPKG",
        help="Output format for BDOT10k (default: GPKG)",
    )
    lc_download.add_argument(
        "--geometry",
        metavar="FILE",
        help="Geometry file (SHP or GPKG) for area selection",
    )
    lc_download.add_argument(
        "--layer",
        metavar="NAME",
        help="Layer name for multi-layer GPKG (default: first layer)",
    )
    lc_download.add_argument(
        "--property",
        "-p",
        default="soc",
        help="Soil property for SoilGrids (default: soc). "
        "Options: bdod, cec, cfvo, clay, nitrogen, ocd, ocs, phh2o, sand, silt, soc",
    )
    lc_download.add_argument(
        "--depth",
        "-d",
        default="0-5cm",
        help="Depth interval for SoilGrids (default: 0-5cm). "
        "Options: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm",
    )
    lc_download.add_argument(
        "--stat",
        default="mean",
        help="Statistic for SoilGrids (default: mean). "
        "Options: mean, Q0.05, Q0.5, Q0.95, uncertainty",
    )

    # Landcover list-sources command
    landcover_subparsers.add_parser(
        "list-sources",
        help="List available data sources",
    )

    # Landcover list-layers command
    lc_layers = landcover_subparsers.add_parser(
        "list-layers",
        help="List available layers for a source",
    )
    lc_layers.add_argument(
        "--source",
        "-s",
        choices=["bdot10k", "corine", "soilgrids"],
        default="bdot10k",
        help="Data source (default: bdot10k)",
    )

    # Soilgrids command group (for HSG calculation)
    soilgrids_parser = subparsers.add_parser(
        "soilgrids",
        help="SoilGrids data processing (HSG calculation)",
        description="Process SoilGrids data for hydrological analysis",
    )
    soilgrids_subparsers = soilgrids_parser.add_subparsers(
        dest="soilgrids_command",
        help="SoilGrids commands",
    )

    # Soilgrids HSG command
    sg_hsg = soilgrids_subparsers.add_parser(
        "hsg",
        help="Calculate Hydrologic Soil Groups from texture data",
        description=(
            "Download clay, sand, silt data from SoilGrids and calculate "
            "Hydrologic Soil Groups (HSG) for SCS-CN method"
        ),
    )
    sg_hsg.add_argument(
        "--godlo",
        metavar="GODLO",
        help="Map sheet identifier (e.g., N-34-130-D)",
    )
    sg_hsg.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Bounding box: min_x,min_y,max_x,max_y in EPSG:2180",
    )
    sg_hsg.add_argument(
        "--geometry",
        metavar="FILE",
        help="Geometry file (SHP or GPKG) for area selection",
    )
    sg_hsg.add_argument(
        "--layer",
        metavar="NAME",
        help="Layer name for multi-layer GPKG (default: first layer)",
    )
    sg_hsg.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default="./data/hsg",
        help="Output path or directory (default: ./data/hsg)",
    )
    sg_hsg.add_argument(
        "--depth",
        "-d",
        default="0-5cm",
        help="Depth interval (default: 0-5cm). "
        "Options: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm",
    )
    sg_hsg.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep intermediate clay/sand/silt files",
    )
    sg_hsg.add_argument(
        "--stats",
        action="store_true",
        help="Print HSG statistics after calculation",
    )

    # Cache command group
    cache_parser = subparsers.add_parser(
        "cache",
        help="Manage metadata cache",
        description=(
            "Manage the local SQLite metadata cache (WMS lookups, TERYT, "
            "CUZK sheet index)"
        ),
    )
    cache_subparsers = cache_parser.add_subparsers(
        dest="cache_command",
        help="Cache commands",
    )

    cache_subparsers.add_parser(
        "stats",
        help="Show cache statistics (entry counts, db size)",
    )

    cache_subparsers.add_parser(
        "clear",
        help="Delete all cached entries",
    )

    cache_subparsers.add_parser(
        "path",
        help="Show path to cache database file",
    )

    return parser
