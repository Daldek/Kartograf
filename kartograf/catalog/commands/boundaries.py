"""``kartograf boundaries``: boundaries and addresses - PRG (GUGiK), RUIAN and
geomorphological units (CUZK) (ADR-042 D9, D17; plan E, E3)."""

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
            level_help,
            metavar="POZIOM",
            allowed=lambda: choice_values(products(), "level"),
            task=True,
        ),
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "boundaries",
    summary="Pobierz granice albo adresy: paczke jednostki, plik krajowy albo "
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
    teryt="Kod TERYT: wojewodztwo (2 cyfry, np. 12) - paczka GML "
    "wszystkich poziomow PRG (admin); powiat (4 cyfry, np. 1261) - paczka "
    "SHP punktow adresowych (addresses)",
    examples=(
        Example(
            {"product": "admin", "teryt": "12"},
            title="Granice PRG: paczka wojewodztwa",
        ),
        Example(
            {
                "product": "admin",
                "country": "pl",
                "level": "gmina",
                "bbox": [550000, 220000, 590000, 270000],
                "bbox_crs": "EPSG:2180",
            },
            title="Gminy PL dla prostokata",
        ),
        Example(
            {
                "product": "addresses",
                "country": "pl",
                "whole_country": True,
                "format": "SHP",
            },
            title="Punkty adresowe PL: plik krajowy",
        ),
        Example(
            {
                "product": "admin",
                "country": "cz",
                "level": "obec",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title="Obce CZ (RUIAN) dla prostokata w S-JTSK",
        ),
    ),
    area_result="obiekty przecinajace obszar (GeoPackage; admin i "
    "geomorphology: jednostki poziomu --level)",
    whole_country="Plik krajowy jednego kraju (wymaga --country pl albo "
    "cz; addresses i special takze --format); rozmiar z serwera "
    "w Warning przed pobraniem",
    content=_content,
)

GROUPS = (
    collection_group(
        "boundaries",
        "Granice i adresy: PRG (PL), RUIAN i jednostki geomorfologiczne (CZ)",
        "Granice jednostek administracyjnych i ewidencyjnych, punkty "
        "adresowe i granice specjalne z PRG (GUGiK, PL), jednostki terytorialne "
        "z RUIAN i jednostki geomorfologiczne (CUZK, CZ) w magazynie wersji.",
    ),
)
