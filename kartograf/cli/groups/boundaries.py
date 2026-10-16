"""``kartograf boundaries``: administrative boundaries - PRG (GUGiK) and RUIAN
(CUZK) (ADR-042 D9, D17)."""

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
        "kraju zadania; zadanie PL+CZ (--country auto) z roznymi: "
        "pl=POZIOM,cz=POZIOM (np. pl=gmina,cz=obec)",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``boundaries download`` and ``boundaries list-sources``."""
    commands = add_group(
        subparsers,
        "boundaries",
        help="Granice administracyjne: PRG (PL), RUIAN (CZ)",
        description="Granice jednostek administracyjnych i ewidencyjnych z PRG "
        "(GUGiK, PL) i jednostek terytorialnych z RUIAN (CUZK, CZ) w magazynie "
        "wersji.",
    )
    add_collection_commands(
        commands,
        "boundaries",
        help="Pobierz granice: paczke wojewodztwa, plik krajowy albo obiekty obszaru",
        description="Pobierz granice do magazynu wersji. PRG (PL): paczke "
        "wojewodztwa (--teryt 2 cyfry; GML wszystkich poziomow), plik krajowy "
        "(--whole-country --country pl; SHP) albo jednostki jednego poziomu "
        "przecinajace obszar (--bbox/--sheet/--geometry z --level; GeoPackage "
        "w EPSG:2180). RUIAN (CZ): plik krajowy (--whole-country --country cz; "
        "SHP) albo jednostki jednego poziomu przecinajace obszar (--bbox/"
        "--geometry z --level; GeoPackage w EPSG:5514). Obszar przy granicy "
        "z --country auto: osobny plik PL i CZ. Pelne geometrie jednostek "
        "w ukladzie uslugi.",
        teryt_help="Kod TERYT wojewodztwa (2 cyfry, np. 12): paczka GML "
        "wszystkich poziomow PRG; obszar powiatu: --bbox albo --geometry",
        area_result="jednostki poziomu --level przecinajace obszar (GeoPackage)",
        whole_country_help="Plik krajowy jednego kraju (wymaga --country pl albo "
        "cz; PRG i RUIAN: SHP w ZIP); rozmiar z serwera w Warning przed pobraniem",
        content=_content,
    )
