"""``kartograf imagery``: orthophotomap - GUGiK sheets and WCS cutout (PL),
CUZK SM5 sheets (CZ) (ADR-039, ADR-042 D13, D14)."""

import argparse
from functools import partial

from kartograf.cli._args import (
    OUTPUT_TITLE,
    add_area_flags,
    add_quiet,
    add_update_flags,
)
from kartograf.cli.download_cmd import cmd_download, download_task_arguments
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    IMAGERY_PRODUCTS,
    SCALE_2000_CHOICES,
    SHEET_SYSTEM_CHOICES,
    product_choices,
)
from kartograf.download.orto_cutout import (
    ORTO_CUTOUT_CRS,
    coverage_choices,
    cutout_resolution_choices,
)
from kartograf.sources.descriptor import SourceDescriptor


def _source_choice(source: SourceDescriptor) -> str:
    """Flags selecting ``source`` in ``imagery download`` (``--country`` of a
    CZ source, as in ``elevation list-sources``)."""
    flags = f"--product {source.product}"
    if source.country == "CZ":
        return f"{flags} --country cz"
    return flags


def register(subparsers: argparse._SubParsersAction) -> None:
    """``imagery download`` and ``imagery list-sources``."""
    commands = add_group(
        subparsers,
        "imagery",
        help="Obrazy lotnicze: ortofotomapa PL i CZ",
        description="Obrazy lotnicze w magazynie wersji: ortofotomapa GUGiK (PL: "
        "arkusze i wycinek WCS) i CUZK (CZ: arkusze SM5).",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz arkusze ortofotomapy (PL, CZ) albo wycinek (PL)",
        description=(
            "Pobierz ortofotomape RGB do magazynu wersji. PL (GUGiK): arkusze "
            "wg kampanii (--bbox/--geometry rozwija sie na arkusze zrodlowe, "
            "godla PL-1992 albo PL-2000) albo jeden wycinek GeoTIFF z WCS "
            "(--cutout). CZ (CUZK): arkusze SM5 aktualnego rocznika (archiwalne "
            "ortofoto CUZK sa platne), JPEG z plikami JGW w S-JTSK, TM33N "
            "i TM34N (--bbox/--geometry rozwija sie na arkusze SM5). Arkusze: "
            "pliki zrodlowe 1:1, piksel zrodla."
        ),
    )

    selection = download.add_argument_group("Produkt i obszar")
    selection.add_argument(
        "--product",
        choices=IMAGERY_PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {product_choices(IMAGERY_PRODUCTS)}",
    )
    add_area_flags(
        selection,
        sheet_help="Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
        "PL rozwija sie na arkusze zrodla): PL-1992 (np. N-34-130-D-d-2-4), "
        "PL-2000 (np. 6.129.30.25.3) albo CZ SM5 (np. CTES96, AS91; JPEG i trzy "
        "pliki JGW)",
        geometry_help="Plik geometrii obszaru (SHP albo GPKG): arkusze "
        "przecinajace obiekty; wycinek (--cutout) - obwiednia geometrii",
    )
    selection.add_argument(
        "--country",
        choices=COUNTRIES,
        default=None,
        help="Kraj zrodla danych - wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac). Wycinek (--cutout) tylko PL: z auto obejmuje "
        "czesc PL",
    )

    sheets = download.add_argument_group("Arkusze obszaru")
    sheets.add_argument(
        "--sheet-system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL (bez "
        f"--cutout): {SHEET_SYSTEM_CHOICES}. Wycinek --cutout: tylko 1992 (mozna "
        "pominac). Nie dotyczy --sheet (uklad z godla) ani CZ (arkusze SM5; "
        "z --country auto dotyczy czesci PL)",
    )
    sheets.add_argument(
        "--scale",
        metavar="SKALA",
        help="Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ (arkusze "
        "SM5 1:5000; z --country auto dotyczy czesci PL) i --cutout. "
        "Szczegoly: docs/USAGE.md 1.6",
    )

    cutout = download.add_argument_group("Wycinek zamiast arkuszy (tylko PL)")
    cutout.add_argument(
        "--cutout",
        action="store_true",
        help="Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry, "
        "tylko PL; wymaga --horizontal-crs, --coverage i --resolution): GeoTIFF "
        "RGB z WCS GUGiK na siatce uslugi (obraz bez przeprobkowania, bez maski "
        "ladu), plik <wsp>.tif (wersje w versions/, ponowne uruchomienie uzywa "
        "lokalnej wersji; --force pobiera); kompozycja lotow serwera (bez "
        "wyboru roku); w trybie --geometry obejmuje CALA obwiednie geometrii",
    )
    cutout.add_argument(
        "--horizontal-crs",
        choices=[ORTO_CUTOUT_CRS],
        default=None,
        help="Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad): "
        "tylko uklad siatki uslugi (obraz bez przeprobkowania)",
    )
    cutout.add_argument(
        "--coverage",
        metavar="WARIANT",
        default=None,
        help="Wariant WCS wycinka - wymagany z --cutout (bez --cutout blad): "
        f"{coverage_choices()}",
    )
    cutout.add_argument(
        "--resolution",
        "-r",
        metavar="RES",
        default=None,
        help="Piksel wycinka - wymagany z --cutout (arkusze maja piksel zrodla: "
        f"bez --cutout blad): {cutout_resolution_choices()}",
    )

    campaigns = download.add_argument_group(
        "Rok danych i loty (tylko PL: z --country cz blad, z auto dotyczy czesci PL)"
    )
    campaigns.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        help="Tylko ten rok danych (rok pozyskania zdjec: aktualnosc "
        "ortofotomapy); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu = blad przed pobraniem; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--min-year",
        type=int,
        metavar="ROK",
        help="Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK "
        "(wszystkie: --all-campaigns); nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--max-year",
        type=int,
        metavar="ROK",
        help="Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK "
        "(wszystkie: --all-campaigns); sciezka standardowa nigdy nie cofa sie "
        "na starszy lot; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--all-campaigns",
        action="store_true",
        help="Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
        "z flaga wszystkie loty z zakresu lat do <segment>/versions/; flagi "
        "roku ograniczaja tylko dopuszczalne lata; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--full-sheet",
        action="store_true",
        help="Gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --cutout",
    )

    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Katalog wyniku (wymagany); pliki trafiaja do "
        "<KATALOG>/orto/<segment>/...",
    )
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne "
        "/ nowsza / do pobrania / nie da sie sprawdzic bez pobrania); niczego "
        "nie pobiera. Arkusze PL: skorowidz GUGiK, arkusze CZ: wydanie w feedzie "
        "ATOM CUZK, wycinek: bez taniego sygnalu",
        upgrade_help="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje "
        "(domyslnie tylko informacja); wycinek bez taniego sygnalu zostaje "
        "lokalny (pobranie: --force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik zadania (arkusze, wycinek) "
        "i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, inna = "
        "nowa wersja; nic nie jest nadpisywane",
        plan_help="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1, przy --country auto jeden plan PL i CZ); z --upgrade: "
        "wykonaj plan (pozycje zmienione od planu = blad, bez pobrania)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=4,
        help="Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    )
    add_quiet(output)
    download.set_defaults(
        _handler=partial(cmd_download, products=IMAGERY_PRODUCTS),
        _task=download_task_arguments,
    )

    add_list_sources(commands, "imagery", IMAGERY_PRODUCTS, _source_choice)
