"""``kartograf models3d``: 3D models of GUGiK - buildings and trees (CityGML,
powiat packages) and the mesh of towns (OBJ tiles of an index) (ADR-042 D9;
plan E, E5)."""

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
            lod_help,
            metavar="N",
            allowed=lambda: choice_values(products(), "lod"),
            task=True,
        ),
        Param(
            "year",
            "int",
            "Rok: wydanie paczek (wymagany, gdy poziom ma kilka wydan - lista "
            "przy --lod; jedyne wydanie mozna pominac) albo rok danych kafli mesh "
            "(filtr: tylko kafle tego roku; bez niego kafle wszystkich lat)",
            metavar="ROK",
            allowed=lambda: choice_values(products(), "year"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "models3d",
    summary="Pobierz paczki modeli 3D powiatow albo kafle mesh obszaru",
    description="Pobierz modele 3D do magazynu wersji. --product buildings "
    "(budynki) i trees (drzewa, CityGML LoD1 2023, paczka 0,3-25 GB): "
    "paczka powiatu (--teryt 4 cyfry) albo paczki kazdego powiatu, ktory "
    "obszar przecina (--bbox/--sheet/--geometry; powiaty z PRG); wydanie "
    "wybieraja --lod i --year. Brak paczki powiatu (LoD2 budynkow, drzewa "
    "czesci powiatow) = blad tego powiatu. --product mesh: kafle indeksu "
    "GUGiK przecinajace obszar (--bbox/--sheet/--geometry), kazdy plik "
    "kafla w katalogu swojego ukladu (1992 albo 2000/<strefa>, np. 2000/7); "
    "--year wybiera kafle jednego roku. Paczki ZIP zapisywane 1:1, uklad "
    "wysokosci z danych w sidecarze. Obszar, ktory dalby wiecej niz 100 "
    "plikow albo ponad 10 GB, konczy sie bledem przed pobraniem: zawez "
    "obszar albo wybierz powiat.",
    teryt="Kod TERYT powiatu (4 cyfry, np. 1261): paczka modeli "
    "powiatu (buildings, trees)",
    examples=(
        Example(
            {"product": "buildings", "lod": 1, "year": 2024, "teryt": "1261"},
            title="Budynki LoD1 2024: paczka powiatu",
        ),
        Example(
            {
                "product": "mesh",
                "country": "pl",
                "bbox": [566200, 244650, 566250, 244700],
                "bbox_crs": "EPSG:2180",
            },
            title="Mesh miast: kafle dla prostokata",
        ),
    ),
    area_result="paczki powiatow przecinajacych obszar (PRG; buildings, "
    "trees) albo kafle mesh obszaru",
    check="Porownaj lokalne wersje ze zrodlem bez pobierania: kafel "
    "mesh - etykieta rekordu indeksu (data i numer zgloszenia pracy); "
    "paczki budynkow i drzew nie maja taniego sygnalu (nie da sie sprawdzic "
    "bez pobrania), brakujace pliki = do pobrania",
    content=_content,
)

GROUPS = (
    collection_group(
        "models3d",
        "Modele 3D: budynki i drzewa (CityGML), mesh miast (OBJ)",
        "Modele 3D GUGiK (PL) w magazynie wersji: budynki i drzewa "
        "(CityGML, paczki powiatow) oraz modele siatkowe miast (mesh OBJ "
        "z teksturami, kafle indeksu).",
    ),
)
