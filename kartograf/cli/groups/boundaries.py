"""``kartograf boundaries``: boundaries and addresses - PRG (GUGiK), RUIAN and
geomorphological units (CUZK) (ADR-042 D9, D17; plan E, E3)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import (
    collection_choice_values,
    collection_level_choices,
)


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    content.add_argument(
        "--level",
        metavar="POZIOM",
        default=None,
        help="Poziom jednostek obszaru - wymagany z --bbox/--sheet/--geometry "
        f"dla produktow z poziomami: {collection_level_choices(products)}. "
        "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ "
        "(--country auto) z roznymi: pl=POZIOM,cz=POZIOM (np. pl=gmina,cz=obec)",
    )
    formats = "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, "format").items()
    )
    content.add_argument(
        "--format",
        metavar="FORMAT",
        default=None,
        help=f"Format pliku krajowego (--whole-country; wymagany): {formats}",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``boundaries download`` and ``boundaries list-sources``."""
    commands = add_group(
        subparsers,
        "boundaries",
        help="Granice i adresy: PRG (PL), RUIAN i jednostki geomorfologiczne (CZ)",
        description="Granice jednostek administracyjnych i ewidencyjnych, punkty "
        "adresowe i granice specjalne z PRG (GUGiK, PL), jednostki terytorialne "
        "z RUIAN i jednostki geomorfologiczne (CUZK, CZ) w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "boundaries",
        help="Pobierz granice albo adresy: paczke jednostki, plik krajowy albo "
        "obiekty obszaru",
        description="Pobierz do magazynu wersji. --product admin: PRG (PL) - "
        "paczka wojewodztwa (--teryt 2 cyfry; GML wszystkich poziomow), plik "
        "krajowy (--whole-country --country pl; SHP) albo jednostki jednego "
        "poziomu przecinajace obszar (--level; GeoPackage w EPSG:2180); RUIAN "
        "(CZ) - plik krajowy (SHP) albo jednostki poziomu obszaru (GeoPackage "
        "w EPSG:5514). --product addresses (PL): punkty adresowe i ulice obszaru "
        "(GeoPackage w EPSG:2180), paczka SHP powiatu (--teryt 4 cyfry) albo "
        "plik krajowy (--whole-country --format SHP|GML). --product special "
        "(PL): 45 rodzajow granic specjalnych (sady, policja, skarbowe, lasy, "
        "wody, obszary morskie, ...) przecinajacych obszar (GeoPackage "
        "w OGC:CRS84) albo plik krajowy (--whole-country --format SHP|GML). "
        "--product geomorphology (CZ): jednostki poziomu --level przecinajace "
        "obszar (GeoPackage w EPSG:5514). Obszar przy granicy z --country "
        "auto: osobny plik PL i CZ. Pelne geometrie w ukladzie uslugi.",
        teryt_help="Kod TERYT: wojewodztwo (2 cyfry, np. 12) - paczka GML "
        "wszystkich poziomow PRG (admin); powiat (4 cyfry, np. 1261) - paczka "
        "SHP punktow adresowych (addresses)",
        area_result="obiekty przecinajace obszar (GeoPackage; admin i "
        "geomorphology: jednostki poziomu --level)",
        whole_country_help="Plik krajowy jednego kraju (wymaga --country pl albo "
        "cz; addresses i special takze --format); rozmiar z serwera "
        "w Warning przed pobraniem",
        content=_content,
    )
