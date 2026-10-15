"""``kartograf imagery``: orthophotomap sheets of GUGiK (ADR-039)."""

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
    IMAGERY_PRODUCTS,
    SCALE_2000_CHOICES,
    SHEET_SYSTEM_CHOICES,
    product_choices,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """``imagery download`` and ``imagery list-sources``."""
    commands = add_group(
        subparsers,
        "imagery",
        help="Obrazy lotnicze: ortofotomapa",
        description="Obrazy lotnicze: arkusze ortofotomapy z GUGiK (PL).",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz arkusze ortofotomapy",
        description=(
            "Pobierz arkusze ortofotomapy RGB z GUGiK (PL) do magazynu wersji; "
            "--bbox/--geometry rozwija sie na arkusze zrodlowe (godla PL-1992 "
            "albo PL-2000). Dane zrodlowe 1:1, bez rozdzielczosci i ukladu "
            "wysokosci do wyboru."
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
        "rozwija sie na arkusze zrodla): PL-1992 (np. N-34-130-D-d-2-4) albo "
        "PL-2000 (np. 6.129.30.25.3)",
        geometry_help="Plik geometrii obszaru (SHP albo GPKG): arkusze "
        "przecinajace obiekty",
    )
    selection.add_argument(
        "--country",
        # no CZ orthophoto in Kartograf yet: only the countries that give data
        choices=["pl", "auto"],
        default=None,
        help="Kraj zrodla danych - wymagany z --bbox/--geometry: pl (GUGiK) "
        "albo auto (kraj wg prostokatnych obwiedni PL i CZ; ortofotomapa jest "
        "tylko dla PL, wiec obszar przy granicy daje czesc PL, a obszar tylko "
        "w CZ - blad). Z --sheet kraj wynika z godla",
    )

    sheets = download.add_argument_group("Arkusze obszaru")
    sheets.add_argument(
        "--sheet-system",
        choices=["1992", "2000"],
        default=None,
        help="Uklad godel arkuszy PL - wymagany z --bbox/--geometry: "
        f"{SHEET_SYSTEM_CHOICES}. Nie dotyczy --sheet (uklad z godla)",
    )
    sheets.add_argument(
        "--scale",
        metavar="SKALA",
        help="Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Szczegoly: docs/USAGE.md 1.6",
    )

    campaigns = download.add_argument_group("Rok danych i loty (tylko PL)")
    campaigns.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        help="Tylko ten rok danych (rok pozyskania zdjec: aktualnosc "
        "ortofotomapy); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu = blad przed pobraniem",
    )
    campaigns.add_argument(
        "--min-year",
        type=int,
        metavar="ROK",
        help="Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK "
        "(wszystkie: --all-campaigns)",
    )
    campaigns.add_argument(
        "--max-year",
        type=int,
        metavar="ROK",
        help="Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK "
        "(wszystkie: --all-campaigns); sciezka standardowa nigdy nie cofa sie "
        "na starszy lot",
    )
    campaigns.add_argument(
        "--all-campaigns",
        action="store_true",
        help="Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
        "z flaga wszystkie loty z zakresu lat do <segment>/versions/; flagi "
        "roku ograniczaja tylko dopuszczalne lata",
    )
    campaigns.add_argument(
        "--full-sheet",
        action="store_true",
        help="Gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski",
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
        check_help="Porownaj lokalne wersje ze skorowidzem GUGiK i wypisz raport "
        "(aktualne / nowsza / do pobrania); niczego nie pobiera",
        upgrade_help="Pobierz nowsza tresc, gdy skorowidz ja wskazuje (domyslnie "
        "tylko informacja); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy arkusz zadania i odswiez liste "
        "kampanii z GUGiK; ta sama tresc = bez zmian, inna = nowa wersja; nic "
        "nie jest nadpisywane",
        plan_help="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1); z --upgrade: wykonaj plan (pozycje zmienione od "
        "planu = blad, bez pobrania)",
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

    add_list_sources(
        commands,
        "imagery",
        IMAGERY_PRODUCTS,
        lambda source: f"--product {source.product}",
    )
