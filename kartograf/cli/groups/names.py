"""``kartograf names``: geographic names of Poland, Czechia and the world."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_choice_values


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    choices = "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, "format").items()
    )
    content.add_argument(
        "--format",
        metavar="FORMAT",
        help=f"Format pliku krajowego (--whole-country; wymagany): {choices}",
    )
    content.add_argument(
        "--horizontal-crs",
        metavar="EPSG:KOD",
        help="Uklad pliku krajowego Geonames (CZ): EPSG:5514 albo EPSG:3045; "
        "wymagany przy --whole-country --country cz. Obszar: uklad natywny uslugi",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the names download and list-sources commands."""
    commands = add_group(
        subparsers,
        "names",
        help="Nazwy geograficzne: PRNG (PL i swiat), Geonames (CZ)",
        description="Nazwy geograficzne obszaru w GeoPackage albo oryginalne "
        "pliki krajowe: PRNG (PL i swiat), Geonames (CZ).",
    )
    add_collection_commands(
        commands,
        "names",
        help="Pobierz nazwy geograficzne obszaru albo pliki krajowe",
        description="--product geographic: PRNG RP (--country pl) lub Geonames "
        "(--country cz); --product world: polskie nazwy swiata (--country pl). "
        "Dla obszaru pobierane sa obiekty w GeoPackage; --country pl przy "
        "--product world oznacza kraj zrodla, a nie granice pobrania. "
        "--whole-country wymaga --country pl/cz i --format; PRNG RP daje "
        "dwa pliki (miejscowosci i obiekty fizjograficzne).",
        area_result="obiekty geograficzne w GeoPackage (PL: OGC:CRS84; CZ: EPSG:5514)",
        whole_country_help="Oryginalne pliki krajowe, tylko z --country pl/cz "
        "i --format; Geonames wymaga takze --horizontal-crs",
        check_help="Porownaj plik krajowy Geonames z data wydania w feedzie "
        "ATOM; PRNG (PL) i obiekty obszaru nie maja taniego sygnalu swiezosci "
        "(brakujace pliki = do pobrania)",
        content=_content,
    )
