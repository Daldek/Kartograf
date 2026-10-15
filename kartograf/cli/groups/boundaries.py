"""``kartograf boundaries``: administrative boundaries - PRG (GUGiK) (ADR-042 D9)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_level_choices


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    content.add_argument(
        "--level",
        metavar="POZIOM",
        default=None,
        help="Poziom jednostek obszaru - wymagany z --bbox/--sheet/--geometry: "
        f"{collection_level_choices(products)}. Jedna wartosc dotyczy kazdego "
        "kraju zadania; zadanie PL+CZ z roznymi: pl=POZIOM,cz=POZIOM",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``boundaries download`` and ``boundaries list-sources``."""
    commands = add_group(
        subparsers,
        "boundaries",
        help="Granice administracyjne: PRG",
        description="Granice jednostek administracyjnych i ewidencyjnych z PRG "
        "(GUGiK, PL) w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "boundaries",
        help="Pobierz granice: paczke wojewodztwa, plik krajowy albo obiekty obszaru",
        description="Pobierz granice PRG do magazynu wersji: paczke wojewodztwa "
        "(--teryt 2 cyfry; GML wszystkich poziomow), plik krajowy "
        "(--whole-country; SHP) albo jednostki jednego poziomu przecinajace "
        "obszar (--bbox/--sheet/--geometry z --level): jeden GeoPackage "
        "z pelnymi geometriami w ukladzie uslugi (EPSG:2180).",
        teryt_help="Kod TERYT wojewodztwa (2 cyfry, np. 12): paczka GML "
        "wszystkich poziomow; obszar powiatu: --bbox albo --geometry",
        area_result="jednostki poziomu --level przecinajace obszar (GeoPackage)",
        whole_country_help="Plik krajowy jednego kraju (wymaga --country pl albo "
        "cz); rozmiar z serwera w Warning przed pobraniem",
        content=_content,
    )
