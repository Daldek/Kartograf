"""``kartograf elevation``: NMT, NMPT (GUGiK), DMR 5G/4G (CUZK) and LAZ (ADR-039)."""

import argparse
from functools import partial

from kartograf.cli._args import (
    OUTPUT_TITLE,
    add_area_flags,
    add_quiet,
    add_update_flags,
)
from kartograf.cli.download_cmd import cmd_download
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_sheets import RESOLUTION_CZ
from kartograf.download.options import (
    COUNTRY_CHOICES,
    RESOLUTION_PL,
    SCALE_2000_CHOICES,
    SHEET_SYSTEM_CHOICES,
    VERTICAL_CRS_CZ,
    VERTICAL_CRS_PL,
    product_choices,
)

PRODUCTS = ("nmt", "nmpt", "laz")


def register(subparsers: argparse._SubParsersAction) -> None:
    """``elevation download`` and ``elevation list-sources``."""
    commands = add_group(
        subparsers,
        "elevation",
        help="Wysokosci: NMT, NMPT, DMR (CZ), chmury punktow LAZ",
        description="Dane wysokosciowe: arkusze NMT/NMPT z GUGiK (PL), DMR 5G/4G "
        "z CUZK (CZ), kafle LAZ z GUGiK (PL) albo jeden wycinek wysokosci "
        "(--cutout).",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz NMT, NMPT albo LAZ (arkusze, kafle albo wycinek)",
        description=(
            "Pobierz NMT, NMPT (GUGiK, PL), DMR 5G/4G (CUZK, CZ) albo chmury "
            "punktow LAZ (GUGiK, PL) do magazynu wersji. Dla PL --bbox/--geometry "
            "rozwija sie na arkusze zrodlowe (LAZ: kafle), a z --cutout "
            "--horizontal-crs daje JEDEN wycinek 1 m z WCS GUGiK (ADR-035); "
            "obszar CZ jest dostepny tylko jako wycinek (--cutout; exportImage "
            "pobierany natywnie w EPSG:5514, w innym ukladzie reprojektowany "
            "lokalnie). Dane zrodlowe 1:1 daja arkusze PL i arkusz SM5; kafel "
            "TM33 to lokalny warp z EPSG:5514 na siatke EPSG:3045 (ADR-024)."
        ),
    )

    selection = download.add_argument_group("Produkt i obszar")
    selection.add_argument(
        "--product",
        choices=PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {product_choices(PRODUCTS)}",
    )
    add_area_flags(
        selection,
        sheet_help="Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
        "rozwija sie na arkusze zrodla; LAZ: kafle przecinajace arkusz): PL-1992 "
        "(np. N-34-130-D-d-2-4), PL-2000 (np. 6.129.30.25.3), CZ SM5 (np. "
        "CTES96) albo CZ TM33 (np. 302_5550)",
        bbox_help="Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: "
        "EPSG:2180; ujemne wspolrzedne, np. EPSG:5514, podaj bez spacji: "
        "--bbox=-447000,...)",
        geometry_help="Plik geometrii obszaru (SHP albo GPKG): arkusze i kafle LAZ "
        "przecinajace obiekty; wycinek (--cutout) - obwiednia geometrii",
    )
    selection.add_argument(
        "--country",
        choices=["pl", "cz", "auto"],
        default=None,
        help="Kraj zrodla danych - wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac)",
    )

    product = download.add_argument_group("Parametry produktu")
    product.add_argument(
        "--resolution",
        "-r",
        metavar="RES",
        default=None,
        help="Rozdzielczosc siatki NMT - wymagana tam, gdzie jest wybor. PL: "
        f"{RESOLUTION_PL}; wycinek --cutout tylko 1m. CZ: "
        f"{RESOLUTION_CZ}; arkusz SM5 tylko 5m (mozna pominac). NMPT tylko "
        "1m (mozna pominac); LAZ bez rozdzielczosci. Jedna wartosc dotyczy "
        "kazdego kraju zadania; zadanie PL+CZ z roznymi: pl=WARTOSC,cz=WARTOSC "
        "(np. pl=1m,cz=2m)",
    )
    product.add_argument(
        "--vertical-crs",
        metavar="VCRS",
        default=None,
        help=f"Uklad wysokosci (wymagany). PL: {VERTICAL_CRS_PL}. CZ: "
        f"{VERTICAL_CRS_CZ}. Jedna wartosc dotyczy kazdego kraju zadania i musi "
        "byc dla niego dostepna; zadanie PL+CZ z roznymi ukladami: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=EVRF2007,cz=Bpv)",
    )
    product.add_argument(
        "--sheet-system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL "
        f"(bez --cutout): {SHEET_SYSTEM_CHOICES}. Wycinek --cutout: tylko "
        "1992 (mozna pominac). Nie dotyczy --sheet (uklad z godla), LAZ "
        "(uklad kazdego kafla z WFS) ani CZ",
    )
    product.add_argument(
        "--scale",
        metavar="SKALA",
        help="Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --cutout. Szczegoly: docs/USAGE.md 1.6",
    )

    cutout = download.add_argument_group("Wycinek zamiast arkuszy")
    cutout.add_argument(
        "--cutout",
        action="store_true",
        help="Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry; "
        "wymaga --horizontal-crs). PL: wycinek 1 m z WCS GUGiK (--product nmt "
        "albo nmpt, tylko --sheet-system 1992 i --resolution 1m) na siatce "
        "arkuszy, maska ladu PL (poza ladem nodata), plik <wsp>.tif (wersje "
        "w versions/, ponowne uruchomienie uzywa lokalnej wersji; --force "
        "pobiera); kompozycja lotow serwera (najnowszy lot arkuszy: pobierz "
        "arkusze bez --cutout); w trybie --geometry obejmuje CALA obwiednie "
        "geometrii. CZ: wycinek exportImage - obszar CZ (takze czesc CZ przy "
        "--country auto) wymaga --cutout",
    )
    cutout.add_argument(
        "--horizontal-crs",
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        choices=list(CUTOUT_CRS),
        default=None,
        help="Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad); "
        "reprojekcja lokalna przypieta operacja; natywny CZ: EPSG:5514",
    )

    campaigns = download.add_argument_group("Rok danych, loty i kafle (tylko PL)")
    campaigns.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        help="Tylko ten rok danych (rok pozyskania: aktualnosc NMT/NMPT, "
        "akt_rok LAZ); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu/kaflu = blad przed pobraniem; nie dziala z --cutout",
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
        "roku ograniczaja tylko dopuszczalne lata; LAZ: bez deduplikacji "
        "pokrycia; nie dziala z --cutout",
    )
    campaigns.add_argument(
        "--full-sheet",
        action="store_true",
        help="NMT/NMPT: gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --cutout ani z LAZ",
    )
    campaigns.add_argument(
        "--min-density",
        type=int,
        metavar="N",
        help="Tylko LAZ (--product laz; z innym produktem blad): zostaw kafle "
        "o gestosci punktow >= N pkt/m2",
    )

    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Katalog wyniku (wymagany); pliki trafiaja do "
        "<KATALOG>/<produkt>/<segment>/...",
    )
    add_update_flags(
        output,
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
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=4,
        help="Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    )
    add_quiet(output)
    download.set_defaults(_handler=partial(cmd_download, products=PRODUCTS))

    add_list_sources(
        commands, "elevation", PRODUCTS, lambda source: f"--product {source.product}"
    )
