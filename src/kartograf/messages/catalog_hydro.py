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
        "HY-NET of CUZK: the stream segments and nodes that cross an area "
        "(GeoPackage, EPSG:5514) or the national ZIP (GeoPackage, EPSG:3045). The "
        "IIaPGW geodatabase of PGW Wody Polskie (water management plans): the "
        "national ZIP (File Geodatabase, EPSG:2180) or the features of its spatial "
        "layers that cross an area (GeoPackage, EPSG:2180), read from that archive in "
        "the store (downloaded once). Never overwrites.",
        "Pobierz siec wod HY-NET do magazynu wersji: odcinki ciekow i wezly "
        "przecinajace obszar (--bbox/--geometry; jeden GeoPackage z pelnymi "
        "geometriami w ukladzie uslugi EPSG:5514) albo plik krajowy calej sieci "
        "(--whole-country --country cz; ZIP z GeoPackage w EPSG:3045, zapis 1:1); "
        "geobaze IIaPGW PGW Wody Polskie (plany gospodarowania wodami 2022-2027): "
        "archiwum krajowe 1:1 (--whole-country --country pl; ZIP z File Geodatabase "
        "w EPSG:2180) albo obiekty jej warstw przestrzennych przecinajace obszar "
        "(jeden GeoPackage w EPSG:2180), czytane z archiwum w magazynie, ktore "
        "pierwsze zadanie obszaru pobiera raz.",
    ),
    "area_result_description": Text(
        "HY-NET: downloads the stream segments and nodes that intersect the area (one "
        "GeoPackage); PGW: the whole features of the spatial layers that intersect the "
        "area's envelope (one GeoPackage, EPSG:2180), read from the national archive "
        "in the store (downloaded once when missing).",
        "HY-NET: odcinki ciekow i wezly przecinajace obszar (GeoPackage); PGW: cale "
        "obiekty warstw przestrzennych przecinajace prostokat obszaru (GeoPackage, "
        "EPSG:2180), czytane z archiwum krajowego w magazynie (pobieranego raz, gdy "
        "go brak)",
    ),
    "layers_description": Text(
        "PGW area only: the feature datasets of the geodatabase whose layers the "
        "GeoPackage holds, any letter case - PGW_WP (surface water bodies, their "
        "catchments, river basin districts, water regions), JCWPd (groundwater "
        "bodies), SIG (protected areas). Not given: every spatial layer.",
        "Tylko obszar PGW: zbiory obiektow geobazy, ktorych warstwy trafia do "
        "GeoPackage, wielkosc liter dowolna - PGW_WP (jednolite czesci wod "
        "powierzchniowych, ich zlewnie, obszary dorzeczy, regiony wodne), JCWPd "
        "(jednolite czesci wod podziemnych), SIG (obszary chronione). Bez opcji: "
        "wszystkie warstwy przestrzenne.",
    ),
    "rule_layers_applies_only_pgw": Text(
        "--layers applies only to --product pgw",
        "--layers dotyczy tylko --product pgw",
    ),
    "rule_layers_excludes_whole_country": Text(
        "--layers excludes --whole-country: the archive is stored as published",
        "--layers wyklucza --whole-country: archiwum jest zapisywane 1:1",
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
        "and the PGW archive have none (cannot be checked without downloading); a PGW "
        "area GeoPackage is current when it was written from the local archive.",
        "Porownaj plik krajowy HY-NET ze zrodlem bez pobierania: naglowki HTTP "
        "(ETag/Last-Modified); siec obszaru i archiwum PGW nie maja taniego sygnalu "
        "(nie da sie sprawdzic bez pobrania), GeoPackage obszaru PGW jest aktualny, "
        "gdy zapisano go z lokalnego archiwum; brakujacy plik = do pobrania",
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
    "example_pgw_area_surface_waters": Text(
        "Water management plans: the surface water layers of a rectangle in EPSG:2180",
        "Plany gospodarowania wodami: warstwy wod powierzchniowych prostokata w "
        "EPSG:2180",
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
