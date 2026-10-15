"""``kartograf models3d``: 3D building models - CityGML (GUGiK) (ADR-042 D9)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_variant_choices


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    releases = collection_variant_choices(products)
    content.add_argument(
        "--lod",
        type=int,
        metavar="N",
        default=None,
        help=f"Poziom szczegolowosci modeli (wymagany): {releases}",
    )
    content.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        default=None,
        help="Rok wydania modeli - wymagany, gdy poziom ma kilka wydan (lista "
        "przy --lod); jedyne wydanie mozna pominac",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``models3d download`` and ``models3d list-sources``."""
    commands = add_group(
        subparsers,
        "models3d",
        help="Modele 3D budynkow: CityGML LoD1, LoD2",
        description="Modele 3D budynkow (CityGML, GUGiK, PL) w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "models3d",
        help="Pobierz paczki modeli 3D powiatu albo powiatow obszaru",
        description="Pobierz modele 3D budynkow do magazynu wersji: paczke "
        "powiatu (--teryt 4 cyfry) albo paczki kazdego powiatu, ktory obszar "
        "przecina (--bbox/--sheet/--geometry; powiaty z PRG). Wydanie wybieraja "
        "--lod i --year; paczka ZIP zapisywana 1:1, uklad wysokosci z danych "
        "w sidecarze. LoD2 nie pokrywa calego kraju (brak paczki powiatu = "
        "blad tego powiatu).",
        teryt_help="Kod TERYT powiatu (4 cyfry, np. 1261): paczka modeli powiatu",
        area_result="paczki powiatow przecinajacych obszar (PRG)",
        content=_content,
    )
