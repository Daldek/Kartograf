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
            (
                "Format of the national file (with `whole_country`; required): "
                "`geographic` PL GML, SHP or XLSX; `geographic` CZ GPKG or "
                "FGDB; `world` PL GML, SHP or XLSX."
            ),
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
            description_pl=format_help,
        ),
        Param(
            "horizontal_crs",
            "str",
            (
                "CRS of the Geonames (CZ) national file: EPSG:5514 or "
                "EPSG:3045; required with `whole_country` and `country=cz`. An "
                "area is always in the native CRS of the service (PL OGC:CRS84,"
                " CZ EPSG:5514): an equal value is accepted, another one is an "
                "error."
            ),
            metavar="EPSG:KOD",
            task=True,
            description_pl=(
                "Uklad pliku krajowego Geonames (CZ): EPSG:5514 albo EPSG:3045;"
                " wymagany przy --whole-country --country cz. Obszar: tylko "
                "uklad natywny uslugi (PL: OGC:CRS84, CZ: EPSG:5514) - rowny mu"
                " jest przyjmowany, inny to Error"
            ),
        ),
    )


COMMANDS = collection_commands(
    "names",
    summary=(
        "Download geographic names of an area or the national files (PL, CZ, world)",
        "Pobierz nazwy geograficzne obszaru albo pliki krajowe",
    ),
    description=(
        "`geographic`: PRNG (PL) or Geonames (CZ); `world`: Polish "
        "names of the world (PRNG). An area gives its features in one "
        "GeoPackage; `whole_country` fetches the original national "
        "files (PRNG: two files, settlements and physiographic objects)"
        " and needs `format`. Never overwrites.",
        (
            "--product geographic: PRNG RP (--country pl) lub Geonames "
            "(--country cz); --product world: polskie nazwy swiata "
            "(--country pl). Dla obszaru pobierane sa obiekty w GeoPackage;"
            " --country pl przy --product world oznacza kraj zrodla, a nie "
            "granice pobrania. --whole-country wymaga --country pl/cz i "
            "--format; PRNG RP daje dwa pliki (miejscowosci i obiekty "
            "fizjograficzne)."
        ),
    ),
    examples=(
        Example(
            {
                "product": "geographic",
                "country": "pl",
                "bbox": [19.93, 50.055, 19.945, 50.065],
                "bbox_crs": "EPSG:4326",
            },
            title="PRNG names for a rectangle in WGS84",
            title_pl="Nazwy PRNG dla prostokata w WGS84",
        ),
        Example(
            {
                "product": "geographic",
                "country": "cz",
                "whole_country": True,
                "format": "GPKG",
                "horizontal_crs": "EPSG:5514",
            },
            title="CZ Geonames: the national file in S-JTSK",
            title_pl="Geonames CZ: plik krajowy w S-JTSK",
        ),
        Example(
            {
                "product": "world",
                "country": "pl",
                "bbox": [-74.02, 40.69, -73.92, 40.79],
                "bbox_crs": "EPSG:4326",
            },
            title="Polish names of the world for a rectangle (New York)",
            title_pl="Polskie nazwy swiata dla prostokata (Nowy Jork)",
        ),
    ),
    area_result=(
        "Downloads the geographic features of the area (GeoPackage; PL "
        "OGC:CRS84, CZ EPSG:5514).",
        ("obiekty geograficzne w GeoPackage (PL: OGC:CRS84; CZ: EPSG:5514)"),
    ),
    whole_country=(
        "Original national files (needs `country` pl or cz and "
        "`format`; Geonames also needs `horizontal_crs`).",
        (
            "Oryginalne pliki krajowe, tylko z --country pl/cz i --format; "
            "Geonames wymaga takze --horizontal-crs"
        ),
    ),
    check=(
        "Signal: the release date of the Geonames national file in the "
        "ATOM feed; PRNG (PL) and area objects have none.",
        (
            "Porownaj plik krajowy Geonames z data wydania w feedzie ATOM; "
            "PRNG (PL) i obiekty obszaru nie maja taniego sygnalu swiezosci"
            " (brakujace pliki = do pobrania)"
        ),
    ),
    content=_content,
)

GROUPS = (
    collection_group(
        "names",
        (
            "Geographic names: PRNG (PL and world), Geonames (CZ)",
            "Nazwy geograficzne: PRNG (PL i swiat), Geonames (CZ)",
        ),
        (
            "Geographic names of an area as a GeoPackage or the original "
            "national files: PRNG (PL and the world), Geonames (CZ).",
            (
                "Nazwy geograficzne obszaru w GeoPackage albo oryginalne pliki "
                "krajowe: PRNG (PL i swiat), Geonames (CZ)."
            ),
        ),
    ),
)
