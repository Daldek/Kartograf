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
from kartograf.download.cz_sheets import RESOLUTION_CZ
from kartograf.download.options import (
    COUNTRY_CHOICES,
    PRODUCT_CHOICES,
    RESOLUTION_PL,
    SCALE_2000_CHOICES,
    SYSTEM_CHOICES,
    VERTICAL_CRS_CZ,
    VERTICAL_CRS_PL,
)
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


_BBOX_EXPECTED = "Oczekiwano: min_x,min_y,max_x,max_y (np. 450000,550000,460000,560000)"
_BBOX_HELP = "Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: EPSG:2180)"
_SHEET_HELP = "Godlo arkusza (np. N-34-130-D)"
_GEOMETRY_HELP = "Plik geometrii (SHP albo GPKG); obszar = obwiednia obiektow"
_LAYER_HELP = (
    "Warstwa GPKG (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)"
)
BBOX_CRS_CHOICES = (
    "EPSG:2180",
    "EPSG:4326",
    "EPSG:2176",
    "EPSG:2177",
    "EPSG:2178",
    "EPSG:2179",
    "EPSG:5514",
    "EPSG:3045",
)


def _add_bbox_crs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bbox-crs",
        choices=BBOX_CRS_CHOICES,
        default="EPSG:2180",
        help="Uklad wspolrzednych --bbox (domyslnie EPSG:2180)",
    )


def _add_quiet(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Bez paska postepu i linii statusu na stdout (Info:, Warning: "
        "i Error: na stderr zostaja)",
    )


def _layer_codes(text: str) -> tuple[str, ...]:
    """``--layers SWRS,PTWP`` -> ``("SWRS", "PTWP")``; codes checked by the library."""
    return tuple(code.strip() for code in text.split(","))


# Admissible values of the download data choices (0.8.0: no defaults): one
# wording for --help and for the library ``ValidationError`` of a missing value.


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
        ``Nieprawidlowy bbox: <reason>. Oczekiwano: ...`` for a number of values
        other than 4, a non-numeric value, NaN/inf or ``min > max``
        (``core.bbox.validate_bbox``; a point bbox is allowed).
    """
    parts = text.split(",")
    if len(parts) != 4:
        reason = f"oczekiwano 4 wartosci rozdzielonych przecinkami, podano {len(parts)}"
        raise ValidationError(f"Nieprawidlowy bbox: {reason}. {_BBOX_EXPECTED}")
    values = []
    for part in parts:
        try:
            values.append(float(part.strip()))
        except ValueError:
            reason = f"{part.strip()!r} nie jest liczba"
            raise ValidationError(
                f"Nieprawidlowy bbox: {reason}. {_BBOX_EXPECTED}"
            ) from None
    bbox = BBox(values[0], values[1], values[2], values[3], crs)
    try:
        validate_bbox(bbox)
    except ValidationError as e:
        raise ValidationError(f"Nieprawidlowy bbox: {e}. {_BBOX_EXPECTED}") from e
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
            "Pobieranie danych przestrzennych z GUGiK (PL), CUZK (CZ), Copernicus "
            "i ISRIC: NMT, NMPT, ortofotomapa, LAZ, BDOT10k, CORINE, SoilGrids"
        ),
        epilog="Przyklad: kartograf parse N-34-130-D --hierarchy",
    )

    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        help="pokaz wersje programu i zakoncz",
    )

    subparsers = parser.add_subparsers(dest="command", help="Komendy")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Rozpoznaj godlo arkusza i pokaz jego wlasciwosci",
        description="Rozpoznaj godlo arkusza i pokaz jego wlasciwosci",
    )
    parse_parser.add_argument(
        "sheet",
        metavar="GODLO",
        type=str.strip,
        help="Godlo arkusza (np. N-34-130-D, N-34-130-D-d-2-4)",
    )
    parse_parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="Pokaz hierarchie od arkusza do skali 1:1000000",
    )
    parse_parser.add_argument(
        "--children",
        action="store_true",
        help="Pokaz bezposrednie arkusze potomne",
    )
    parse_parser.add_argument(
        "--descendants",
        metavar="SKALA",
        help="Pokaz wszystkie arkusze potomne do skali docelowej (np. 1:10000)",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Pobierz NMT, NMPT, ortofotomape albo LAZ z GUGiK (PL) i CUZK (CZ)",
        description=(
            "Pobierz dane z GUGiK (PL: NMT, NMPT, ortofotomapa, LAZ) i CUZK "
            "(CZ: DMR 5G/4G). Dla PL --bbox/--geometry rozwija sie na "
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
        metavar="GODLO",
        default=None,
        # argparse does not strip whitespace; a sheet code with padding would reach
        # the system registry and the file name (parser review 2026-10-07, K5)
        type=str.strip,
        help="Godlo arkusza: PL-1992 (np. N-34-130-D-d-2-4), PL-2000 "
        "(np. 6.129.30.25.3), CZ SM5 (np. CTES96) albo CZ TM33 (np. 302_5550)",
    )
    download_parser.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: EPSG:2180; "
        "ujemne wspolrzedne, np. EPSG:5514, podaj bez spacji: --bbox=-447000,...)",
    )
    _add_bbox_crs(download_parser)
    download_parser.add_argument(
        "--country",
        choices=["pl", "cz", "auto"],
        default=None,
        help="Kraj zrodla danych - wymagany z --bbox/--geometry: "
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
        metavar="SKALA",
        help="Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --target-crs. Szczegoly: docs/USAGE.md 1.6",
    )
    download_parser.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Katalog wyniku (wymagany); pliki trafiaja do "
        "<KATALOG>/<produkt>/<segment>/...",
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
    _add_quiet(download_parser)
    download_parser.add_argument(
        "--vertical-crs",
        metavar="VCRS",
        default=None,
        help="Uklad wysokosci - wymagany dla --product nmt, nmpt i laz (orto "
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
        help="Rozdzielczosc siatki NMT - wymagana tam, gdzie jest wybor. PL: "
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
        metavar="ROK",
        help="Tylko ten rok danych (PL: rok pozyskania aktualnosc NMT/NMPT/orto, "
        "akt_rok LAZ); skrot --min-year ROK --max-year ROK; najnowszy lot "
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
        metavar="ROK",
        help="Tylko PL: dolna granica roku danych (wlacznie); najnowszy lot "
        "z lat >= ROK (wszystkie: --all-campaigns); nie dziala z --target-crs",
    )
    download_parser.add_argument(
        "--max-year",
        type=int,
        metavar="ROK",
        help="Tylko PL: gorna granica roku danych (wlacznie); najnowszy lot "
        "z lat <= ROK (wszystkie: --all-campaigns); sciezka standardowa nigdy "
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
        help="Tylko LAZ (--product laz; z innym produktem blad): zostaw kafle "
        "o gestosci punktow >= N pkt/m2",
    )
    download_parser.add_argument(
        "--geometry",
        metavar="PLIK",
        help="Plik geometrii obszaru (SHP albo GPKG): arkusze i kafle LAZ "
        "przecinajace obiekty; wycinek (--target-crs, CZ) - obwiednia geometrii",
    )
    download_parser.add_argument(
        "--layer",
        metavar="NAZWA",
        help=_LAYER_HELP,
    )
    download_parser.add_argument(
        "--system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL "
        f"(bez --target-crs): {SYSTEM_CHOICES}. Wycinek --target-crs: tylko "
        "1992 (mozna pominac). Nie dotyczy --sheet (uklad z godla), LAZ "
        "(uklad kazdego kafla z WFS) ani CZ",
    )
    download_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    )

    # Landcover command group
    landcover_parser = subparsers.add_parser(
        "landcover",
        help="Pobierz pokrycie terenu i dane glebowe (BDOT10k, CORINE, SoilGrids)",
        description="Pobierz pokrycie terenu albo dane glebowe z BDOT10k, CORINE "
        "lub SoilGrids do magazynu wersji",
    )
    landcover_subparsers = landcover_parser.add_subparsers(
        dest="landcover_command",
        help="Komendy landcover",
    )

    # Landcover download command
    lc_download = landcover_subparsers.add_parser(
        "download",
        help="Pobierz dane wybranego zrodla",
        description="Pobierz dane wybranego zrodla (--source) dla jednego "
        "obszaru: --teryt, --sheet, --bbox albo --geometry",
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
        metavar="KOD",
        help="Kod TERYT powiatu (4 cyfry, np. 1465; tylko BDOT10k)",
    )
    lc_download.add_argument(
        "--bbox",
        metavar="BBOX",
        help=_BBOX_HELP,
    )
    _add_bbox_crs(lc_download)
    lc_download.add_argument(
        "--sheet",
        metavar="GODLO",
        help=_SHEET_HELP,
    )
    lc_download.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        default=None,
        help="Wymagane dla corine: 2018, 2012, 2006, 2000 "
        "(edycje pokrycia terenu CLMS/WMS), 1990 (tylko podglad WMS)",
    )
    lc_download.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; pliki trafiaja do "
        "<KATALOG>/landcover/... i <KATALOG>/soil/... (wersje w versions/)",
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
        "--layers",
        metavar="KODY",
        type=_layer_codes,
        default=None,
        help="Tylko BDOT10k GPKG: zostaw wybrane warstwy, kody po przecinku "
        "(np. SWRS,PTWP); domyslnie wszystkie",
    )
    lc_download.add_argument(
        "--keep-raw",
        action="store_true",
        help="Tylko BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok pliku "
        "(wersja surowa w magazynie)",
    )
    lc_download.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help="Tylko BDOT10k obszaru (wiele powiatow): liczba rownoleglych "
        "pobran (domyslnie 1)",
    )
    lc_download.add_argument(
        "--geometry",
        metavar="PLIK",
        help=_GEOMETRY_HELP,
    )
    lc_download.add_argument(
        "--layer",
        metavar="NAZWA",
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
    _add_quiet(lc_download)

    # Landcover list-sources command
    landcover_subparsers.add_parser(
        "list-sources",
        help="Wypisz dostepne zrodla danych",
    )

    # Landcover list-layers command
    lc_layers = landcover_subparsers.add_parser(
        "list-layers",
        help="Wypisz warstwy wybranego zrodla",
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
        help="SoilGrids: grupy hydrologiczne gleb (HSG)",
        description="Przetwarzanie danych SoilGrids do analiz hydrologicznych",
    )
    soilgrids_subparsers = soilgrids_parser.add_subparsers(
        dest="soilgrids_command",
        help="Komendy soilgrids",
    )

    # Soilgrids HSG command
    sg_hsg = soilgrids_subparsers.add_parser(
        "hsg",
        help="Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
        description=(
            "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids "
            "dla wybranej glebokosci; uzyj statystyki mean (srednia) "
            "i oblicz grupy hydrologiczne HSG dla metody SCS-CN."
        ),
    )
    sg_hsg.add_argument(
        "--sheet",
        metavar="GODLO",
        help=_SHEET_HELP,
    )
    sg_hsg.add_argument(
        "--bbox",
        metavar="BBOX",
        help=_BBOX_HELP,
    )
    _add_bbox_crs(sg_hsg)
    sg_hsg.add_argument(
        "--geometry",
        metavar="PLIK",
        help=_GEOMETRY_HELP,
    )
    sg_hsg.add_argument(
        "--layer",
        metavar="NAZWA",
        help=_LAYER_HELP,
    )
    sg_hsg.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; wejscia w <KATALOG>/soil/..., HSG w "
        "<KATALOG>/hsg/... (plik poza magazynem: hsg_from_rasters)",
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
        help="Wypisz statystyki HSG po obliczeniu",
    )
    _add_quiet(sg_hsg)

    # Cache command group
    cache_parser = subparsers.add_parser(
        "cache",
        help="Zarzadzaj cache metadanych",
        description=(
            "Lokalny cache metadanych SQLite (odpowiedzi WMS, TERYT, indeks "
            "arkuszy CUZK)"
        ),
    )
    cache_subparsers = cache_parser.add_subparsers(
        dest="cache_command",
        help="Komendy cache",
    )

    cache_subparsers.add_parser(
        "stats",
        help="Pokaz statystyki cache (liczby wpisow, rozmiar bazy)",
    )

    cache_subparsers.add_parser(
        "clear",
        help="Usun wszystkie wpisy cache",
    )

    cache_subparsers.add_parser(
        "path",
        help="Pokaz sciezke pliku bazy cache",
    )

    return parser
