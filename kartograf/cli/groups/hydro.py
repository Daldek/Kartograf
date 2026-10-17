"""``kartograf hydro``: hydrography - the HY-NET water network (CUZK) (ADR-042 D16)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands


def register(subparsers: argparse._SubParsersAction) -> None:
    """``hydro download`` and ``hydro list-sources``."""
    commands = add_group(
        subparsers,
        "hydro",
        help="Hydrografia: siec wod (HY-NET CZ)",
        description="Siec hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - "
        "Network) w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "hydro",
        help="Pobierz siec wod obszaru albo plik krajowy",
        description="Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow "
        "i wezly przecinajace obszar (--bbox/--geometry; jeden GeoPackage "
        "z pelnymi geometriami w ukladzie uslugi EPSG:5514) albo plik krajowy "
        "calej sieci (--whole-country --country cz; ZIP z GeoPackage "
        "w EPSG:3045, zapis 1:1).",
        area_result="odcinki ciekow i wezly przecinajace obszar (GeoPackage)",
        examples_of=(
            "kartograf hydro download --product network --country cz "
            "--bbox -470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514 -o ./data",
            "kartograf hydro download --product network --country cz "
            "--whole-country -o ./data",
        ),
        # sheet codes and TERYT select PL areas; HY-NET is CZ only
        sheet=False,
        whole_country_help="Plik krajowy (wymaga --country cz): HY-NET.zip "
        "z GeoPackage w EPSG:3045; rozmiar z serwera w Warning przed pobraniem",
        check_help="Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: "
        "naglowki HTTP (ETag/Last-Modified); siec obszaru nie ma taniego sygnalu "
        "(nie da sie sprawdzic bez pobrania), brakujacy plik = do pobrania",
        # one GeoPackage of the area or one national file: nothing to parallelise
        workers_help=None,
    )
