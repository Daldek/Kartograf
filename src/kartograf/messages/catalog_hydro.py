"""Messages of the command catalog: the declarations of ``hydro``."""

from kartograf.messages import Text

MESSAGES = {
    "download_summary": Text(
        "Download the CZ water network (HY-NET) for an area or the national file",
        "Pobierz siec wod obszaru albo plik krajowy",
    ),
    "download_description": Text(
        "Fetches the HY-NET hydrographic network of CUZK (INSPIRE Hydrography - "
        "Network): the stream segments and nodes that cross an area (one GeoPackage, "
        "EPSG:5514) or the national file (a ZIP with a GeoPackage, EPSG:3045). CZ "
        "only. Never overwrites.",
        "Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow i wezly "
        "przecinajace obszar (--bbox/--geometry; jeden GeoPackage z pelnymi "
        "geometriami w ukladzie uslugi EPSG:5514) albo plik krajowy calej sieci "
        "(--whole-country --country cz; ZIP z GeoPackage w EPSG:3045, zapis 1:1).",
    ),
    "area_result_description": Text(
        "Downloads the stream segments and nodes that intersect the area (one "
        "GeoPackage).",
        "odcinki ciekow i wezly przecinajace obszar (GeoPackage)",
    ),
    "whole_country_description": Text(
        "National file (needs `country=cz`): HY-NET.zip with a GeoPackage in "
        "EPSG:3045. The size is in a notice before the download.",
        "Plik krajowy (wymaga --country cz): HY-NET.zip z GeoPackage w EPSG:3045; "
        "rozmiar z serwera w Warning przed pobraniem",
    ),
    "check_description": Text(
        "Signal: the HTTP headers of the national HY-NET file; the network of an area "
        "has none (cannot be checked without downloading).",
        "Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: naglowki HTTP "
        "(ETag/Last-Modified); siec obszaru nie ma taniego sygnalu (nie da sie "
        "sprawdzic bez pobrania), brakujacy plik = do pobrania",
    ),
    "example_water_network_rectangle_s_jtsk": Text(
        "Water network for a rectangle in S-JTSK",
        "Siec wod dla prostokata w S-JTSK",
    ),
    "example_water_network_national_file": Text(
        "Water network: the national file",
        "Siec wod: plik krajowy",
    ),
    "group_summary": Text(
        "Hydrography: the water network (HY-NET, CZ)",
        "Hydrografia: siec wod (HY-NET CZ)",
    ),
    "group_description": Text(
        "The HY-NET hydrographic network (CUZK, CZ; INSPIRE Hydrography - Network) in "
        "the versioned store.",
        "Siec hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - Network) w "
        "magazynie wersji.",
    ),
}
