"""
Argument parser definition for the Kartograf CLI.

This module builds the top-level ``argparse`` parser together with all
subcommand parsers (parse, download, landcover, soilgrids, cache).
"""

import argparse
import sys
from collections.abc import Sequence
from typing import Any, NoReturn

from kartograf._version import build_version
from kartograf.core.bbox import BBox, validate_bbox
from kartograf.download.cutout import SUPPORTED_TARGET_CRS
from kartograf.exceptions import ValidationError


class _LazyVersionAction(argparse.Action):
    """``--version`` resolving the build identifier only when requested."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            option_strings, dest=dest, default=argparse.SUPPRESS, nargs=0, **kwargs
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        sys.stdout.write(f"{parser.prog} {build_version()}\n")
        parser.exit()


def add_update_flags(
    parser: argparse.ArgumentParser,
    *,
    check_help: str,
    upgrade_help: str,
    force_help: str,
    plan_help: str,
) -> None:
    """Update modes of a store command (spec 4.2, 4.4): ``--check-updates``,
    ``--upgrade``, ``--force`` (mutually exclusive) and ``--plan PLIK``
    (with a mode only — checked in ``commands._dispatch``)."""
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-updates", action="store_true", help=check_help)
    modes.add_argument("--upgrade", action="store_true", help=upgrade_help)
    modes.add_argument("--force", action="store_true", help=force_help)
    parser.add_argument("--plan", metavar="PLIK", default=None, help=plan_help)


_BBOX_EXPECTED = "Expected: min_x,min_y,max_x,max_y (e.g., 450000,550000,460000,560000)"
_LAYER_HELP = (
    "Warstwa GPKG (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)"
)

# Admissible values of the download data choices (0.8.0: no defaults). One
# wording for --help and for the `Error:` of a missing value.
PRODUCT_CHOICES = (
    "nmt (Numeryczny Model Terenu; PL i CZ), nmpt (Numeryczny Model Pokrycia "
    "Terenu; PL, tylko 1m), orto (ortofotomapa RGB; PL), laz (chmura punktow "
    "LIDAR; PL)"
)
COUNTRY_CHOICES = (
    "pl (GUGiK), cz (CUZK), auto (kraje wg prostokatnych obwiedni PL i CZ; "
    "obszar w obu krajach daje osobne pliki per kraj)"
)
RESOLUTION_PL = "1m (NMT 1 m), 5m (NMT 5 m, tylko --vertical-crs EVRF2007)"
RESOLUTION_CZ = "2m (DMR 5G), 5m (DMR 4G)"
VERTICAL_CRS_PL = (
    "EVRF2007 (PL-EVRF2007-NH, uklad obowiazujacy), KRON86 (PL-KRON86-NH, "
    "uklad historyczny; nie dla NMT 5m)"
)
VERTICAL_CRS_CZ = (
    "Bpv (natywny uklad CUZK), EVRF2007 (transformacja z Bpv, "
    "ok. +0,11..+0,15 m, rosnaco S->N)"
)
SYSTEM_CHOICES = (
    "1992 (godla PL-1992, arkusze 1:10000), 2000 (godla PL-2000, strefy "
    "EPSG:2176-2179; wymaga --scale)"
)
SCALE_2000_CHOICES = (
    "1:5000, 1:2000, 1:1000, 1:500 (GUGiK publikuje arkusze PL-2000 najczesciej "
    "w 1:2000, takze w 1:1000 i 1:5000)"
)


def parse_bbox_arg(text: str, crs: str) -> BBox:
    """
    Parses the ``--bbox`` value (``"min_x,min_y,max_x,max_y"``) into a ``BBox``.

    One message for every input defect - callers do not catch the exception:
    ``ValidationError`` is a ``KartografError``, so ``main`` prints
    ``Error: ...`` to stderr and returns 1 (the hint comes with the error,
    not on stdout).

    Parameters
    ----------
    text : str
        Argument value; whitespace around numbers is allowed
    crs : str
        CRS in which the coordinates were given

    Raises
    ------
    ValidationError
        ``Invalid bbox format: <reason>. Expected: ...`` for a number of values
        other than 4, a non-numeric value, NaN/inf or ``min > max``
        (``core.bbox.validate_bbox``; a point bbox is allowed).
    """
    parts = text.split(",")
    if len(parts) != 4:
        reason = f"expected 4 comma-separated values, got {len(parts)}"
        raise ValidationError(f"Invalid bbox format: {reason}. {_BBOX_EXPECTED}")
    values = []
    for part in parts:
        try:
            values.append(float(part.strip()))
        except ValueError:
            reason = f"{part.strip()!r} is not a number"
            raise ValidationError(
                f"Invalid bbox format: {reason}. {_BBOX_EXPECTED}"
            ) from None
    bbox = BBox(values[0], values[1], values[2], values[3], crs)
    try:
        validate_bbox(bbox)
    except ValidationError as e:
        raise ValidationError(f"Invalid bbox format: {e}. {_BBOX_EXPECTED}") from e
    return bbox


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
        action=_LazyVersionAction,
        help="show program's version number and exit",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse and display information about a map sheet",
        description="Parse a map sheet code and display its properties",
    )
    parse_parser.add_argument(
        "sheet",
        metavar="SHEET",
        type=str.strip,
        help="Map sheet code (e.g., N-34-130-D, N-34-130-D-d-2-4)",
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
        help="Download geospatial data from GUGiK (PL) and CUZK (CZ)",
        description=(
            "Download geospatial data from GUGiK (PL: NMT, NMPT, orthophoto, LAZ) "
            "and CUZK (CZ: DMR 5G/4G). Dla PL --bbox/--geometry rozwija sie na "
            "arkusze zrodlowe, a z --target-crs daje JEDEN wycinek 1 m z WCS "
            "GUGiK (ADR-035); dla CZ --bbox/--geometry zawsze zwraca jeden wycinek "
            "(exportImage pobierany natywnie w EPSG:5514, z --target-crs "
            "reprojektowany lokalnie). Dane zrodlowe 1:1 daja arkusze PL "
            "i arkusz SM5; kafel TM33 to lokalny warp z EPSG:5514 na siatke "
            "EPSG:3045 (ADR-024)."
        ),
    )
    download_parser.add_argument(
        "--sheet",
        metavar="SHEET",
        default=None,
        # argparse does not strip whitespace; a sheet code with padding would reach
        # the system registry and the file name (parser review 2026-10-07, K5)
        type=str.strip,
        help="Map sheet code: PL-1992 (e.g. N-34-130-D-d-2-4), PL-2000 "
        "(e.g. 6.129.30.25.3), CZ SM5 (e.g. CTES96) or CZ TM33 (e.g. 302_5550)",
    )
    download_parser.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Bounding box: min_x,min_y,max_x,max_y (default CRS: EPSG:2180; "
        "ujemne wspolrzedne, np. EPSG:5514, podaj bez spacji: --bbox=-447000,...)",
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
        default=None,
        help="Kraj zrodla danych — wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac)",
    )
    download_parser.add_argument(
        "--target-crs",
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        choices=list(SUPPORTED_TARGET_CRS),
        default=None,
        help="Reprojekcja wyniku, wykonywana lokalnie przypieta operacja "
        "(tylko tryb --bbox/--geometry). PL: wycinek 1 m z WCS GUGiK (--product "
        "nmt albo nmpt, tylko --system 1992 i --resolution 1m) na siatce "
        "arkuszy, maska ladu PL (poza ladem nodata), nazwa z data pobrania "
        "<wsp>_RRRRMMDD.tif, kazde uruchomienie pobiera; kompozycja lotow "
        "serwera (najnowszy lot arkuszy: pobierz arkusze bez --target-crs); "
        "w trybie --geometry obejmuje CALA obwiednie geometrii. CZ: wycinek "
        "exportImage",
    )
    download_parser.add_argument(
        "--scale",
        metavar="SCALE",
        help="Skala arkuszy PL-2000 do pobrania — wymagana z --bbox/--geometry "
        "--system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona — "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --target-crs. Szczegoly: docs/USAGE.md 1.6",
    )
    download_parser.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default=None,
        help="Katalog wyniku (wymagany); pliki trafiaja do "
        "<DIR>/<produkt>/<segment>/...",
    )
    add_update_flags(
        download_parser,
        check_help="Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne / "
        "nowsza / do pobrania / nie da sie sprawdzic bez pobrania); niczego nie "
        "pobiera. Arkusze PL i LAZ: skorowidz/WFS, arkusze SM5: ETag, wycinki "
        "i TM33: bez taniego sygnalu",
        upgrade_help="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie "
        "tylko informacja); pliki bez taniego sygnalu zostaja lokalne "
        "(pobranie: --force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik zadania (arkusze, kafle LAZ, "
        "wycinki) i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, "
        "inna = nowa wersja; nic nie jest nadpisywane",
        plan_help="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1, przy --country auto jeden plan PL i CZ); z --upgrade: "
        "wykonaj plan (pozycje zmienione od planu = blad, bez pobrania)",
    )
    download_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    download_parser.add_argument(
        "--vertical-crs",
        metavar="VCRS",
        default=None,
        help="Uklad wysokosci — wymagany dla --product nmt, nmpt i laz (orto "
        f"go nie ma). PL: {VERTICAL_CRS_PL}. CZ: {VERTICAL_CRS_CZ}. Jedna "
        "wartosc dotyczy kazdego kraju zadania i musi byc dla niego "
        "dostepna; zadanie PL+CZ z roznymi ukladami: pl=WARTOSC,cz=WARTOSC "
        "(np. pl=EVRF2007,cz=Bpv)",
    )
    download_parser.add_argument(
        "--resolution",
        "-r",
        metavar="RES",
        default=None,
        help="Rozdzielczosc siatki NMT — wymagana tam, gdzie jest wybor. PL: "
        f"{RESOLUTION_PL}; wycinek --target-crs tylko 1m. CZ: "
        f"{RESOLUTION_CZ}; arkusz SM5 tylko 5m (mozna pominac). NMPT tylko "
        "1m (mozna pominac); orto i LAZ bez rozdzielczosci. Jedna wartosc "
        "dotyczy kazdego kraju zadania; zadanie PL+CZ z roznymi: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=1m,cz=2m)",
    )
    download_parser.add_argument(
        "--product",
        choices=["nmt", "nmpt", "orto", "laz"],
        default=None,
        help=f"Produkt (wymagany): {PRODUCT_CHOICES}",
    )
    download_parser.add_argument(
        "--year",
        type=int,
        metavar="YYYY",
        help="Tylko ten rok danych (PL: rok pozyskania aktualnosc NMT/NMPT/orto, "
        "akt_rok LAZ); skrot --min-year YYYY --max-year YYYY; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu/kaflu = blad przed pobraniem; nie dziala z --target-crs",
    )
    download_parser.add_argument(
        "--all-campaigns",
        action="store_true",
        help="Tylko PL: bez flagi najnowszy lot na arkusz w zakresie lat "
        "(jeden lot); z flaga wszystkie loty z zakresu lat do "
        "<segment>/versions/; flagi roku ograniczaja tylko dopuszczalne lata; "
        "LAZ: bez deduplikacji pokrycia; nie dziala z --target-crs",
    )
    download_parser.add_argument(
        "--min-year",
        type=int,
        metavar="YYYY",
        help="Tylko PL: dolna granica roku danych (wlacznie); najnowszy lot "
        "z lat >= YYYY (wszystkie: --all-campaigns); nie dziala z --target-crs",
    )
    download_parser.add_argument(
        "--max-year",
        type=int,
        metavar="YYYY",
        help="Tylko PL: gorna granica roku danych (wlacznie); najnowszy lot "
        "z lat <= YYYY (wszystkie: --all-campaigns); sciezka standardowa nigdy "
        "nie cofa sie na starszy lot; nie dziala z --target-crs",
    )
    download_parser.add_argument(
        "--full-sheet",
        action="store_true",
        help="Tylko PL NMT/NMPT/orto: gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --target-crs ani z LAZ",
    )
    download_parser.add_argument(
        "--min-density",
        type=int,
        metavar="N",
        help="LAZ only (--product laz; an error with other products): keep "
        "tiles with point density >= N points/m²",
    )
    download_parser.add_argument(
        "--geometry",
        metavar="FILE",
        help="Geometry file (SHP or GPKG) — download tiles intersecting features",
    )
    download_parser.add_argument(
        "--layer",
        metavar="NAME",
        help=_LAYER_HELP,
    )
    download_parser.add_argument(
        "--system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL — wymagany z --bbox/--geometry dla PL "
        f"(bez --target-crs): {SYSTEM_CHOICES}. Wycinek --target-crs: tylko "
        "1992 (mozna pominac). Nie dotyczy --sheet (uklad z godla), LAZ "
        "(uklad kazdego kafla z WFS) ani CZ",
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
        help="Download land cover and soil data (BDOT10k, CORINE, SoilGrids)",
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
        default=None,
        help="Wymagane: bdot10k (wektorowa baza topograficzna GUGiK), "
        "corine (CORINE Land Cover, Copernicus), soilgrids (gleby SoilGrids, ISRIC)",
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
        "--sheet",
        metavar="SHEET",
        help="Map sheet code (e.g., N-34-130-D)",
    )
    lc_download.add_argument(
        "--year",
        type=int,
        default=None,
        help="Wymagane dla corine: 2018, 2012, 2006, 2000 "
        "(edycje pokrycia terenu CLMS/WMS), 1990 (tylko podglad WMS)",
    )
    lc_download.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default=None,
        help="Wymagane: katalog magazynu; pliki trafiaja do "
        "<DIR>/landcover/... i <DIR>/soil/... (wersje w versions/)",
    )
    add_update_flags(
        lc_download,
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: SoilGrids "
        "i CORINE (CLMS) - wydanie zrodla; BDOT10k i podglad CORINE - brak "
        "taniego sygnalu (nie da sie sprawdzic bez pobrania)",
        upgrade_help="Pobierz nowsze wydanie SoilGrids/CORINE (domyslnie tylko "
        "informacja); BDOT10k i podglad CORINE zostaja lokalne (pobranie: "
        "--force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik (BDOT10k: takze odswiez powiaty "
        "z PRG); ta sama tresc = bez zmian, inna = nowa wersja",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    lc_download.add_argument(
        "--format",
        "-f",
        choices=["GPKG", "SHP"],
        default="GPKG",
        help="Tylko BDOT10k: GPKG (GeoPackage, domyslnie) lub SHP "
        "(archiwum ZIP z plikami Shapefile)",
    )
    lc_download.add_argument(
        "--geometry",
        metavar="FILE",
        help="Geometry file (SHP or GPKG) for area selection",
    )
    lc_download.add_argument(
        "--layer",
        metavar="NAME",
        help=_LAYER_HELP,
    )
    lc_download.add_argument(
        "--property",
        "-p",
        default=None,
        help="Wymagane dla soilgrids: bdod (gestosc objetosciowa), "
        "cec (pojemnosc sorpcyjna), cfvo (frakcja szkieletowa), clay (il), "
        "nitrogen (azot), ocd (gestosc wegla organicznego), "
        "ocs (zasob wegla organicznego), phh2o (pH), sand (piasek), "
        "silt (pyl), soc (wegiel organiczny)",
    )
    lc_download.add_argument(
        "--depth",
        "-d",
        default=None,
        help="Wymagane dla soilgrids: 0-5cm, 5-15cm, 15-30cm, 30-60cm, "
        "60-100cm, 100-200cm (przedzial glebokosci ponizej powierzchni)",
    )
    lc_download.add_argument(
        "--stat",
        default=None,
        help="Wymagane dla soilgrids: mean (srednia), Q0.05 (5. percentyl), "
        "Q0.5 (mediana), Q0.95 (95. percentyl), "
        "uncertainty (niepewnosc predykcji)",
    )
    lc_download.set_defaults(quiet=False)

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
        default=None,
        help="Wymagane: bdot10k (wektorowa baza topograficzna GUGiK), "
        "corine (CORINE Land Cover, Copernicus), soilgrids (gleby SoilGrids, ISRIC)",
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
            "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids "
            "dla wybranej glebokosci; uzyj statystyki mean (srednia) "
            "i oblicz grupy hydrologiczne HSG dla metody SCS-CN."
        ),
    )
    sg_hsg.add_argument(
        "--sheet",
        metavar="SHEET",
        help="Map sheet code (e.g., N-34-130-D)",
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
        help=_LAYER_HELP,
    )
    sg_hsg.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default=None,
        help="Wymagane: katalog magazynu; wejscia w <DIR>/soil/..., HSG w "
        "<DIR>/hsg/... (plik poza magazynem: hsg_from_rasters)",
    )
    sg_hsg.add_argument(
        "--depth",
        "-d",
        default=None,
        help="Wymagane: 0-5cm, 5-15cm, 15-30cm, 30-60cm, "
        "60-100cm, 100-200cm (przedzial glebokosci ponizej powierzchni)",
    )
    add_update_flags(
        sg_hsg,
        check_help="Porownaj wejscia clay/sand/silt z wydaniem SoilGrids i HSG "
        "z wejsciami bez pobierania i bez liczenia",
        upgrade_help="Pobierz nowsze wydanie wejsc (domyslnie tylko informacja); "
        "HSG liczony tylko dla nowego zestawu wejsc; z --plan wykonaj plan",
        force_help="Pobierz ponownie wejscia; HSG liczony tylko, gdy tresc "
        "wejsc sie zmienila (inaczej uzyta ponownie)",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    sg_hsg.add_argument(
        "--stats",
        action="store_true",
        help="Print HSG statistics after calculation",
    )
    sg_hsg.set_defaults(quiet=False)

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
