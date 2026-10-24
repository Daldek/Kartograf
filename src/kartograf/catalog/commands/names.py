"""``kartograf names``: geographic names of Poland, Czechia and the world."""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param


def _content(products: Products) -> tuple[Param, ...]:
    def format_help() -> str:
        return (
            "Format pliku krajowego (--whole-country; wymagany): "
            f"{choice_text(products(), 'format')}"
        )

    return (
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
        ),
        Param(
            "horizontal_crs",
            "str",
            "Uklad pliku krajowego Geonames (CZ): EPSG:5514 albo EPSG:3045; "
            "wymagany przy --whole-country --country cz. Obszar: tylko uklad "
            "natywny uslugi (PL: OGC:CRS84, CZ: EPSG:5514) - rowny mu jest "
            "przyjmowany, inny to Error",
            metavar="EPSG:KOD",
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "names",
    summary="Pobierz nazwy geograficzne obszaru albo pliki krajowe",
    description="--product geographic: PRNG RP (--country pl) lub Geonames "
    "(--country cz); --product world: polskie nazwy swiata (--country pl). "
    "Dla obszaru pobierane sa obiekty w GeoPackage; --country pl przy "
    "--product world oznacza kraj zrodla, a nie granice pobrania. "
    "--whole-country wymaga --country pl/cz i --format; PRNG RP daje "
    "dwa pliki (miejscowosci i obiekty fizjograficzne).",
    examples=(
        Example(
            {
                "product": "geographic",
                "country": "pl",
                "bbox": [19.93, 50.055, 19.945, 50.065],
                "bbox_crs": "EPSG:4326",
            },
            title="Nazwy PRNG dla prostokata w WGS84",
        ),
        Example(
            {
                "product": "geographic",
                "country": "cz",
                "whole_country": True,
                "format": "GPKG",
                "horizontal_crs": "EPSG:5514",
            },
            title="Geonames CZ: plik krajowy w S-JTSK",
        ),
        Example(
            {
                "product": "world",
                "country": "pl",
                "bbox": [-74.02, 40.69, -73.92, 40.79],
                "bbox_crs": "EPSG:4326",
            },
            title="Polskie nazwy swiata dla prostokata (Nowy Jork)",
        ),
    ),
    area_result="obiekty geograficzne w GeoPackage (PL: OGC:CRS84; CZ: EPSG:5514)",
    whole_country="Oryginalne pliki krajowe, tylko z --country pl/cz "
    "i --format; Geonames wymaga takze --horizontal-crs",
    check="Porownaj plik krajowy Geonames z data wydania w feedzie "
    "ATOM; PRNG (PL) i obiekty obszaru nie maja taniego sygnalu swiezosci "
    "(brakujace pliki = do pobrania)",
    content=_content,
)

GROUPS = (
    collection_group(
        "names",
        "Nazwy geograficzne: PRNG (PL i swiat), Geonames (CZ)",
        "Nazwy geograficzne obszaru w GeoPackage albo oryginalne "
        "pliki krajowe: PRNG (PL i swiat), Geonames (CZ).",
    ),
)
