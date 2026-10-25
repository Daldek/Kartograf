"""Messages of the command catalog: the declarations of ``names``."""

from kartograf.messages import Text

MESSAGES = {
    "format_description": Text(
        "Format of the national file (with `whole_country`; required): `geographic` "
        "PL GML, SHP or XLSX; `geographic` CZ GPKG or FGDB; `world` PL GML, SHP or "
        "XLSX.{choice_text:skip}",
        "Format pliku krajowego (--whole-country; wymagany): {choice_text}",
    ),
    "horizontal_crs_description": Text(
        "CRS of the Geonames (CZ) national file: EPSG:5514 or EPSG:3045; required "
        "with `whole_country` and `country=cz`. An area is always in the native CRS "
        "of the service (PL OGC:CRS84, CZ EPSG:5514): an equal value is accepted, "
        "another one is an error.",
        "Uklad pliku krajowego Geonames (CZ): EPSG:5514 albo EPSG:3045; wymagany przy "
        "--whole-country --country cz. Obszar: tylko uklad natywny uslugi (PL: "
        "OGC:CRS84, CZ: EPSG:5514) - rowny mu jest przyjmowany, inny to Error",
    ),
    "download_summary": Text(
        "Download geographic names of an area or the national files (PL, CZ, world)",
        "Pobierz nazwy geograficzne obszaru albo pliki krajowe",
    ),
    "download_description": Text(
        "`geographic`: PRNG (PL) or Geonames (CZ); `world`: Polish names of the world "
        "(PRNG). An area gives its features in one GeoPackage; `whole_country` "
        "fetches the original national files (PRNG: two files, settlements and "
        "physiographic objects) and needs `format`. Never overwrites.",
        "--product geographic: PRNG RP (--country pl) lub Geonames (--country cz); "
        "--product world: polskie nazwy swiata (--country pl). Dla obszaru pobierane "
        "sa obiekty w GeoPackage; --country pl przy --product world oznacza kraj "
        "zrodla, a nie granice pobrania. --whole-country wymaga --country pl/cz i "
        "--format; PRNG RP daje dwa pliki (miejscowosci i obiekty fizjograficzne).",
    ),
    "area_result_description": Text(
        "Downloads the geographic features of the area (GeoPackage; PL OGC:CRS84, CZ "
        "EPSG:5514).",
        "obiekty geograficzne w GeoPackage (PL: OGC:CRS84; CZ: EPSG:5514)",
    ),
    "whole_country_description": Text(
        "Original national files (needs `country` pl or cz and `format`; Geonames "
        "also needs `horizontal_crs`).",
        "Oryginalne pliki krajowe, tylko z --country pl/cz i --format; Geonames "
        "wymaga takze --horizontal-crs",
    ),
    "check_description": Text(
        "Signal: the release date of the Geonames national file in the ATOM feed; "
        "PRNG (PL) and area objects have none.",
        "Porownaj plik krajowy Geonames z data wydania w feedzie ATOM; PRNG (PL) i "
        "obiekty obszaru nie maja taniego sygnalu swiezosci (brakujace pliki = do "
        "pobrania)",
    ),
    "example_prng_names_rectangle_wgs84": Text(
        "PRNG names for a rectangle in WGS84",
        "Nazwy PRNG dla prostokata w WGS84",
    ),
    "example_cz_geonames_national_file_s_jtsk": Text(
        "CZ Geonames: the national file in S-JTSK",
        "Geonames CZ: plik krajowy w S-JTSK",
    ),
    "example_polish_names_world_rectangle_new_york": Text(
        "Polish names of the world for a rectangle (New York)",
        "Polskie nazwy swiata dla prostokata (Nowy Jork)",
    ),
    "group_summary": Text(
        "Geographic names: PRNG (PL and world), Geonames (CZ)",
        "Nazwy geograficzne: PRNG (PL i swiat), Geonames (CZ)",
    ),
    "group_description": Text(
        "Geographic names of an area as a GeoPackage or the original national files: "
        "PRNG (PL and the world), Geonames (CZ).",
        "Nazwy geograficzne obszaru w GeoPackage albo oryginalne pliki krajowe: PRNG "
        "(PL i swiat), Geonames (CZ).",
    ),
}
