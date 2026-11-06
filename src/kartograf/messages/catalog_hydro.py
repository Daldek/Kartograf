"""Messages of the command catalog: the declarations of ``hydro``."""

from kartograf.messages import Text

MESSAGES = {
    "download_summary": Text(
        "Download hydrography: the CZ water network (HY-NET) or the PL water "
        "management plan data (PGW)",
        "Pobierz hydrografie: siec wod CZ (HY-NET) albo dane planow gospodarowania "
        "wodami PL (PGW)",
    ),
    "download_description": Text(
        "Fetches the HY-NET hydrographic network of CUZK (INSPIRE Hydrography - "
        "Network): the stream segments and nodes that cross an area (one GeoPackage, "
        "EPSG:5514) or the national file (a ZIP with a GeoPackage, EPSG:3045); and "
        "the IIaPGW geodatabase of PGW Wody Polskie (the water management plans "
        "2022-2027): the national archive as published (a ZIP with a File "
        "Geodatabase, EPSG:2180). Never overwrites.",
        "Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow i wezly "
        "przecinajace obszar (--bbox/--geometry; jeden GeoPackage z pelnymi "
        "geometriami w ukladzie uslugi EPSG:5514) albo plik krajowy calej sieci "
        "(--whole-country --country cz; ZIP z GeoPackage w EPSG:3045, zapis 1:1); "
        "geobaze IIaPGW PGW Wody Polskie (plany gospodarowania wodami 2022-2027): "
        "archiwum krajowe 1:1 (--whole-country --country pl; ZIP z File Geodatabase "
        "w EPSG:2180).",
    ),
    "area_result_description": Text(
        "HY-NET: downloads the stream segments and nodes that intersect the area (one "
        "GeoPackage).",
        "HY-NET: odcinki ciekow i wezly przecinajace obszar (GeoPackage)",
    ),
    "whole_country_description": Text(
        "National file: with `country=cz` HY-NET.zip with a GeoPackage in EPSG:3045, "
        "with `country=pl` the ZIP of the IIaPGW geodatabase (File Geodatabase, "
        "EPSG:2180, edition 2023-09-15). The size is in a notice before the download.",
        "Plik krajowy: z --country cz HY-NET.zip z GeoPackage w EPSG:3045, z "
        "--country pl ZIP geobazy IIaPGW (File Geodatabase, EPSG:2180, wydanie "
        "2023-09-15); rozmiar z serwera w Warning przed pobraniem",
    ),
    "check_description": Text(
        "Signal: the HTTP headers of the national HY-NET file; the network of an area "
        "and the PGW archive have none (cannot be checked without downloading).",
        "Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: naglowki HTTP "
        "(ETag/Last-Modified); siec obszaru i archiwum PGW nie maja taniego sygnalu "
        "(nie da sie sprawdzic bez pobrania), brakujacy plik = do pobrania",
    ),
    "example_water_network_rectangle_s_jtsk": Text(
        "Water network for a rectangle in S-JTSK",
        "Siec wod dla prostokata w S-JTSK",
    ),
    "example_water_network_national_file": Text(
        "Water network: the national file",
        "Siec wod: plik krajowy",
    ),
    "example_pgw_national_archive": Text(
        "Water management plans: the national geodatabase archive",
        "Plany gospodarowania wodami: krajowe archiwum geobazy",
    ),
    "group_summary": Text(
        "Hydrography: the water network (HY-NET, CZ) and the water management plans "
        "(PGW, PL)",
        "Hydrografia: siec wod (HY-NET CZ) i plany gospodarowania wodami (PGW PL)",
    ),
    "group_description": Text(
        "The HY-NET hydrographic network (CUZK, CZ; INSPIRE Hydrography - Network) and "
        "the IIaPGW geodatabase of the water management plans (PGW Wody Polskie, PL) "
        "in the versioned store.",
        "Siec hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - Network) i "
        "geobaza IIaPGW planow gospodarowania wodami (PGW Wody Polskie, PL) w "
        "magazynie wersji.",
    ),
}
