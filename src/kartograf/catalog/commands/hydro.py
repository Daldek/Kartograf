"""``kartograf hydro``: hydrography - the HY-NET water network (CUZK) (ADR-042 D16)."""

from kartograf.catalog.commands._collection import (
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example

COMMANDS = collection_commands(
    "hydro",
    summary=(
        "Download the CZ water network (HY-NET) for an area or the national file",
        "Pobierz siec wod obszaru albo plik krajowy",
    ),
    description=(
        "Fetches the HY-NET hydrographic network of CUZK (INSPIRE "
        "Hydrography - Network): the stream segments and nodes that "
        "cross an area (one GeoPackage, EPSG:5514) or the national file"
        " (a ZIP with a GeoPackage, EPSG:3045). CZ only. Never "
        "overwrites.",
        (
            "Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow i "
            "wezly przecinajace obszar (--bbox/--geometry; jeden GeoPackage"
            " z pelnymi geometriami w ukladzie uslugi EPSG:5514) albo plik "
            "krajowy calej sieci (--whole-country --country cz; ZIP z "
            "GeoPackage w EPSG:3045, zapis 1:1)."
        ),
    ),
    area_result=(
        "Downloads the stream segments and nodes that intersect the "
        "area (one GeoPackage).",
        "odcinki ciekow i wezly przecinajace obszar (GeoPackage)",
    ),
    examples=(
        Example(
            {
                "product": "network",
                "country": "cz",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title="Water network for a rectangle in S-JTSK",
            title_pl="Siec wod dla prostokata w S-JTSK",
        ),
        Example(
            {"product": "network", "country": "cz", "whole_country": True},
            title="Water network: the national file",
            title_pl="Siec wod: plik krajowy",
        ),
    ),
    # sheet codes and TERYT select PL areas; HY-NET is CZ only
    sheet=False,
    whole_country=(
        "National file (needs `country=cz`): HY-NET.zip with a "
        "GeoPackage in EPSG:3045. The size is in a notice before the "
        "download.",
        (
            "Plik krajowy (wymaga --country cz): HY-NET.zip z GeoPackage w "
            "EPSG:3045; rozmiar z serwera w Warning przed pobraniem"
        ),
    ),
    check=(
        "Signal: the HTTP headers of the national HY-NET file; the "
        "network of an area has none (cannot be checked without "
        "downloading).",
        (
            "Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: "
            "naglowki HTTP (ETag/Last-Modified); siec obszaru nie ma "
            "taniego sygnalu (nie da sie sprawdzic bez pobrania), brakujacy"
            " plik = do pobrania"
        ),
    ),
    # one GeoPackage of the area or one national file: nothing to parallelise
    workers=None,
)

GROUPS = (
    collection_group(
        "hydro",
        (
            "Hydrography: the water network (HY-NET, CZ)",
            "Hydrografia: siec wod (HY-NET CZ)",
        ),
        (
            "The HY-NET hydrographic network (CUZK, CZ; INSPIRE Hydrography"
            " - Network) in the versioned store.",
            (
                "Siec hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - "
                "Network) w magazynie wersji."
            ),
        ),
    ),
)
