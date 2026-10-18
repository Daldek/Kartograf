"""``kartograf hydro``: hydrography - the HY-NET water network (CUZK) (ADR-042 D16)."""

from kartograf.catalog.commands._collection import (
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example

COMMANDS = collection_commands(
    "hydro",
    summary="Pobierz siec wod obszaru albo plik krajowy",
    description="Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow "
    "i wezly przecinajace obszar (--bbox/--geometry; jeden GeoPackage "
    "z pelnymi geometriami w ukladzie uslugi EPSG:5514) albo plik krajowy "
    "calej sieci (--whole-country --country cz; ZIP z GeoPackage "
    "w EPSG:3045, zapis 1:1).",
    area_result="odcinki ciekow i wezly przecinajace obszar (GeoPackage)",
    examples=(
        Example(
            {
                "product": "network",
                "country": "cz",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title="Siec wod dla prostokata w S-JTSK",
        ),
        Example(
            {"product": "network", "country": "cz", "whole_country": True},
            title="Siec wod: plik krajowy",
        ),
    ),
    # sheet codes and TERYT select PL areas; HY-NET is CZ only
    sheet=False,
    whole_country="Plik krajowy (wymaga --country cz): HY-NET.zip "
    "z GeoPackage w EPSG:3045; rozmiar z serwera w Warning przed pobraniem",
    check="Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: "
    "naglowki HTTP (ETag/Last-Modified); siec obszaru nie ma taniego sygnalu "
    "(nie da sie sprawdzic bez pobrania), brakujacy plik = do pobrania",
    # one GeoPackage of the area or one national file: nothing to parallelise
    workers=None,
)

GROUPS = (
    collection_group(
        "hydro",
        "Hydrografia: siec wod (HY-NET CZ)",
        "Siec hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - "
        "Network) w magazynie wersji.",
    ),
)
