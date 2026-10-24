"""Declare ``kartograf models3d``.

3D models of GUGiK - buildings and trees (CityGML, powiat packages) and the mesh of
towns (OBJ tiles of an index) (ADR-042 D9; plan E, E5).
"""

from kartograf.catalog.commands._collection import (
    Products,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param
from kartograf.download.collections import collection_variant_choices


def _content(products: Products) -> tuple[Param, ...]:
    def lod_help() -> str:
        return (
            "Poziom szczegolowosci paczek modeli (wymagany, gdy produkt ma "
            f"kilka; jedyny mozna pominac): {collection_variant_choices(products())}"
        )

    return (
        Param(
            "lod",
            "int",
            (
                "Level of detail of the packages; required when the product has"
                " several (buildings: 1 or 2; trees: 1), may be omitted for the"
                " only one."
            ),
            metavar="N",
            allowed=lambda: choice_values(products(), "lod"),
            task=True,
            description_pl=lod_help,
        ),
        Param(
            "year",
            "int",
            (
                "Year: the release of the packages (required when the level has"
                " several releases, see `lod`; may be omitted for the only one)"
                " or the data year of mesh tiles (only the tiles of that year; "
                "without it every year)."
            ),
            metavar="ROK",
            allowed=lambda: choice_values(products(), "year"),
            task=True,
            description_pl=(
                "Rok: wydanie paczek (wymagany, gdy poziom ma kilka wydan - "
                "lista przy --lod; jedyne wydanie mozna pominac) albo rok "
                "danych kafli mesh (filtr: tylko kafle tego roku; bez niego "
                "kafle wszystkich lat)"
            ),
        ),
    )


COMMANDS = collection_commands(
    "models3d",
    summary=(
        "Download 3D models: building and tree county packages or city mesh tiles (PL)",
        "Pobierz paczki modeli 3D powiatow albo kafle mesh obszaru",
    ),
    description=(
        "`buildings` and `trees` (CityGML; `lod` and `year` choose the "
        "release): a county package (`teryt`) or the packages of the "
        "counties an area crosses. `mesh`: the city mesh tiles (OBJ "
        "with textures) that cross an area. Packages are stored as "
        "published. An area above 100 files or 10 GB is refused before "
        "any download: narrow it or choose a county.",
        (
            "Pobierz modele 3D do magazynu wersji. --product buildings "
            "(budynki) i trees (drzewa, CityGML LoD1 2023, paczka 0,3-25 "
            "GB): paczka powiatu (--teryt 4 cyfry) albo paczki kazdego "
            "powiatu, ktory obszar przecina (--bbox/--sheet/--geometry; "
            "powiaty z PRG); wydanie wybieraja --lod i --year. Brak paczki "
            "powiatu (LoD2 budynkow, drzewa czesci powiatow) = blad tego "
            "powiatu. --product mesh: kafle indeksu GUGiK przecinajace "
            "obszar (--bbox/--sheet/--geometry), kazdy plik kafla w "
            "katalogu swojego ukladu (1992 albo 2000/<strefa>, np. 2000/7);"
            " --year wybiera kafle jednego roku. Paczki ZIP zapisywane 1:1,"
            " uklad wysokosci z danych w sidecarze. Obszar, ktory dalby "
            "wiecej niz 100 plikow albo ponad 10 GB, konczy sie bledem "
            "przed pobraniem: zawez obszar albo wybierz powiat."
        ),
    ),
    teryt=(
        "TERYT code of a county (4 digits, `1261`): the model package "
        "of the county (`buildings`, `trees`).",
        (
            "Kod TERYT powiatu (4 cyfry, np. 1261): paczka modeli powiatu "
            "(buildings, trees)"
        ),
    ),
    examples=(
        Example(
            {"product": "buildings", "lod": 1, "year": 2024, "teryt": "1261"},
            title="Buildings LoD1 2024: a county package",
            title_pl="Budynki LoD1 2024: paczka powiatu",
        ),
        Example(
            {
                "product": "mesh",
                "country": "pl",
                "bbox": [566200, 244650, 566250, 244700],
                "bbox_crs": "EPSG:2180",
            },
            title="City mesh: tiles for a rectangle",
            title_pl="Mesh miast: kafle dla prostokata",
        ),
        Example(
            {"product": "trees", "teryt": "1261"},
            title="Trees LoD1 2023: a county package (0.3-25 GB)",
            title_pl="Drzewa LoD1 2023: paczka powiatu (0,3-25 GB)",
        ),
    ),
    area_result=(
        "Downloads the packages of the counties the area crosses (PRG; "
        "`buildings`, `trees`) or the mesh tiles of the area.",
        (
            "paczki powiatow przecinajacych obszar (PRG; buildings, trees) "
            "albo kafle mesh obszaru"
        ),
    ),
    check=(
        "Signal: for a mesh tile the label of its index record (date "
        "and work number); building and tree packages have none.",
        (
            "Porownaj lokalne wersje ze zrodlem bez pobierania: kafel mesh "
            "- etykieta rekordu indeksu (data i numer zgloszenia pracy); "
            "paczki budynkow i drzew nie maja taniego sygnalu (nie da sie "
            "sprawdzic bez pobrania), brakujace pliki = do pobrania"
        ),
    ),
    content=_content,
    rules=(
        ("Give `lod`, and `year` when the level has several releases.",),
        ("Podaj `lod` i `year`, gdy poziom ma kilka wydan.",),
    ),
)

GROUPS = (
    collection_group(
        "models3d",
        (
            "3D models: buildings and trees (CityGML), city meshes (OBJ)",
            "Modele 3D: budynki i drzewa (CityGML), mesh miast (OBJ)",
        ),
        (
            "GUGiK 3D models (PL) in the versioned store: buildings and "
            "trees (CityGML, county packages) and city mesh models (OBJ "
            "with textures, index tiles).",
            (
                "Modele 3D GUGiK (PL) w magazynie wersji: budynki i drzewa "
                "(CityGML, paczki powiatow) oraz modele siatkowe miast (mesh "
                "OBJ z teksturami, kafle indeksu)."
            ),
        ),
    ),
)
