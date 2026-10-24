"""Declare ``kartograf boundaries``.

Boundaries and addresses - PRG (GUGiK), RUIAN and geomorphological units (CUZK) (ADR-042
D9, D17; plan E, E3).
"""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param
from kartograf.download.collections import collection_level_choices


def _content(products: Products) -> tuple[Param, ...]:
    def level_help() -> str:
        return (
            "Poziom jednostek obszaru - wymagany z --bbox/--sheet/--geometry "
            f"dla produktow z poziomami: {collection_level_choices(products())}. "
            "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ "
            "(--country auto) z roznymi: pl=POZIOM,cz=POZIOM (np. pl=gmina,cz=obec)"
        )

    def format_help() -> str:
        return (
            "Format pliku krajowego (--whole-country; wymagany): "
            f"{choice_text(products(), 'format')}"
        )

    return (
        Param(
            "level",
            "per_country",
            (
                "Level of the units of an area; required with `bbox`, `sheet` "
                "or `geometry` for the products that have levels. One value "
                'applies to every country of the task, or give {"pl": "gmina", '
                '"cz": "obec"}.'
            ),
            metavar="POZIOM",
            allowed=lambda: choice_values(products(), "level"),
            task=True,
            description_pl=level_help,
        ),
        Param(
            "format",
            "str",
            (
                "Format of the national file (with `whole_country`; required): "
                "SHP or GML for `addresses` and `special` PL."
            ),
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
            description_pl=format_help,
        ),
    )


COMMANDS = collection_commands(
    "boundaries",
    summary=(
        "Download boundaries or addresses: a unit package, a national "
        "file or area objects",
        (
            "Pobierz granice albo adresy: paczke jednostki, plik krajowy "
            "albo obiekty obszaru"
        ),
    ),
    description=(
        "`admin`: PRG (PL) voivodeship package, national file or the "
        "units of one `level` in an area; RUIAN (CZ) national file or "
        "units of a level. `addresses` (PL): address points and "
        "streets, a county package or the national file. `special` "
        "(PL): 44 kinds of special boundaries. `geomorphology` (CZ): "
        "units of a `level`. Never overwrites.",
        (
            "Pobierz do magazynu wersji. --product admin: PRG (PL) - paczka"
            " wojewodztwa (--teryt 2 cyfry; GML wszystkich poziomow), plik "
            "krajowy (--whole-country --country pl; SHP) albo jednostki "
            "jednego poziomu przecinajace obszar (--level; GeoPackage w "
            "EPSG:2180); RUIAN (CZ) - plik krajowy (SHP) albo jednostki "
            "poziomu obszaru (GeoPackage w EPSG:5514). --product addresses "
            "(PL): punkty adresowe i ulice obszaru (GeoPackage w "
            "EPSG:2180), paczka SHP powiatu (--teryt 4 cyfry) albo plik "
            "krajowy (--whole-country --format SHP|GML). --product special "
            "(PL): 44 rodzaje granic specjalnych (sady, policja, skarbowe, "
            "lasy, wody, obszary morskie, ...) przecinajace obszar "
            "(GeoPackage w OGC:CRS84; obwody spisowe sa tylko w pliku "
            "krajowym) albo plik krajowy (--whole-country --format "
            "SHP|GML). --product geomorphology (CZ): jednostki poziomu "
            "--level przecinajace obszar (GeoPackage w EPSG:5514). Obszar "
            "przy granicy z --country auto: osobny plik PL i CZ. Pelne "
            "geometrie w ukladzie uslugi."
        ),
    ),
    teryt=(
        "TERYT code: voivodeship (2 digits, `12`): the GML package of "
        "every PRG level (`admin`); county (4 digits, `1261`): the SHP "
        "package of the address points (`addresses`).",
        (
            "Kod TERYT: wojewodztwo (2 cyfry, np. 12) - paczka GML "
            "wszystkich poziomow PRG (admin); powiat (4 cyfry, np. 1261) - "
            "paczka SHP punktow adresowych (addresses)"
        ),
    ),
    examples=(
        Example(
            {"product": "admin", "teryt": "12"},
            title="PRG boundaries: a voivodeship package",
            title_pl="Granice PRG: paczka wojewodztwa",
        ),
        Example(
            {
                "product": "admin",
                "country": "pl",
                "level": "gmina",
                "bbox": [550000, 220000, 590000, 270000],
                "bbox_crs": "EPSG:2180",
            },
            title="PL municipalities for a rectangle",
            title_pl="Gminy PL dla prostokata",
        ),
        Example(
            {
                "product": "addresses",
                "country": "pl",
                "whole_country": True,
                "format": "SHP",
            },
            title="PL address points: the national file",
            title_pl="Punkty adresowe PL: plik krajowy",
        ),
        Example(
            {
                "product": "admin",
                "country": "cz",
                "level": "obec",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title="CZ municipalities (RUIAN) for a rectangle in S-JTSK",
            title_pl="Obce CZ (RUIAN) dla prostokata w S-JTSK",
        ),
        Example(
            {
                "product": "admin",
                "country": "auto",
                "level": {"pl": "gmina", "cz": "obec"},
                "bbox": [18.60, 49.73, 18.66, 49.76],
                "bbox_crs": "EPSG:4326",
            },
            title=(
                "PL municipalities and CZ obce for a rectangle on the border "
                "(country auto)"
            ),
            title_pl="Gminy PL i obce CZ dla prostokata na granicy (--country auto)",
        ),
        Example(
            {
                "product": "special",
                "country": "pl",
                "bbox": [566200, 244650, 566250, 244700],
                "bbox_crs": "EPSG:2180",
            },
            title="PL special boundaries for a rectangle (takes minutes)",
            title_pl="Granice specjalne PL dla prostokata (trwa minuty)",
        ),
        Example(
            {
                "product": "geomorphology",
                "country": "cz",
                "level": "celek",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title="CZ geomorphological units (celky) for a rectangle",
            title_pl="Jednostki geomorfologiczne CZ (celky) dla prostokata",
        ),
    ),
    area_result=(
        "Downloads the objects that intersect the area (GeoPackage; "
        "`admin` and `geomorphology`: the units of `level`).",
        (
            "obiekty przecinajace obszar (GeoPackage; admin i "
            "geomorphology: jednostki poziomu --level)"
        ),
    ),
    whole_country=(
        "National file of one country (needs `country` pl or cz; "
        "`addresses` and `special` also need `format`). The size is in "
        "a notice before the download.",
        (
            "Plik krajowy jednego kraju (wymaga --country pl albo cz; "
            "addresses i special takze --format); rozmiar z serwera w "
            "Warning przed pobraniem"
        ),
    ),
    content=_content,
    rules=(
        ("Give `level` with an area for `admin` and `geomorphology`.",),
        ("Podaj `level` z obszarem dla `admin` i `geomorphology`.",),
    ),
)

GROUPS = (
    collection_group(
        "boundaries",
        (
            "Boundaries and addresses: PRG (PL), RUIAN and geomorphological units (CZ)",
            ("Granice i adresy: PRG (PL), RUIAN i jednostki geomorfologiczne (CZ)"),
        ),
        (
            "Administrative and cadastral boundaries, address points and "
            "special boundaries from PRG (GUGiK, PL), territorial units "
            "from RUIAN and geomorphological units (CUZK, CZ) in the "
            "versioned store.",
            (
                "Granice jednostek administracyjnych i ewidencyjnych, punkty "
                "adresowe i granice specjalne z PRG (GUGiK, PL), jednostki "
                "terytorialne z RUIAN i jednostki geomorfologiczne (CUZK, CZ) w"
                " magazynie wersji."
            ),
        ),
    ),
)
