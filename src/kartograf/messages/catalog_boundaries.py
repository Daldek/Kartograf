"""Messages of the command catalog: the declarations of ``boundaries``."""

from kartograf.messages import Text

MESSAGES = {
    "level_description": Text(
        "Level of the units of an area; required with `bbox`, `sheet` or `geometry` "
        "for the products that have levels. One value applies to every country of the "
        'task, or give {{"pl": "gmina", "cz": "obec"}}.{collection_level_choices:skip}',
        "Poziom jednostek obszaru - wymagany z --bbox/--sheet/--geometry dla "
        "produktow z poziomami: {collection_level_choices}. Jedna wartosc dotyczy "
        "kazdego kraju zadania; zadanie PL+CZ (--country auto) z roznymi: "
        "pl=POZIOM,cz=POZIOM (np. pl=gmina,cz=obec)",
    ),
    "format_description": Text(
        "Format of the national file (with `whole_country`; required): SHP or GML for "
        "`addresses` and `special` PL.{choice_text:skip}",
        "Format pliku krajowego (--whole-country; wymagany): {choice_text}",
    ),
    "download_summary": Text(
        "Download boundaries or addresses: a unit package, a national file or area "
        "objects",
        "Pobierz granice albo adresy: paczke jednostki, plik krajowy albo obiekty "
        "obszaru",
    ),
    "download_description": Text(
        "`admin`: PRG (PL) voivodeship package, national file or the units of one "
        "`level` in an area; RUIAN (CZ) national file or units of a level. "
        "`addresses` (PL): address points and streets, a county package or the "
        "national file. `special` (PL): 44 kinds of special boundaries. "
        "`geomorphology` (CZ): units of a `level`. Never overwrites.",
        "Pobierz do magazynu wersji. --product admin: PRG (PL) - paczka wojewodztwa "
        "(--teryt 2 cyfry; GML wszystkich poziomow), plik krajowy (--whole-country "
        "--country pl; SHP) albo jednostki jednego poziomu przecinajace obszar "
        "(--level; GeoPackage w EPSG:2180); RUIAN (CZ) - plik krajowy (SHP) albo "
        "jednostki poziomu obszaru (GeoPackage w EPSG:5514). --product addresses "
        "(PL): punkty adresowe i ulice obszaru (GeoPackage w EPSG:2180), paczka SHP "
        "powiatu (--teryt 4 cyfry) albo plik krajowy (--whole-country --format "
        "SHP|GML). --product special (PL): 44 rodzaje granic specjalnych (sady, "
        "policja, skarbowe, lasy, wody, obszary morskie, ...) przecinajace obszar "
        "(GeoPackage w OGC:CRS84; obwody spisowe sa tylko w pliku krajowym) albo plik "
        "krajowy (--whole-country --format SHP|GML). --product geomorphology (CZ): "
        "jednostki poziomu --level przecinajace obszar (GeoPackage w EPSG:5514). "
        "Obszar przy granicy z --country auto: osobny plik PL i CZ. Pelne geometrie w "
        "ukladzie uslugi.",
    ),
    "teryt_description": Text(
        "TERYT code: voivodeship (2 digits, `12`): the GML package of every PRG level "
        "(`admin`); county (4 digits, `1261`): the SHP package of the address points "
        "(`addresses`).",
        "Kod TERYT: wojewodztwo (2 cyfry, np. 12) - paczka GML wszystkich poziomow "
        "PRG (admin); powiat (4 cyfry, np. 1261) - paczka SHP punktow adresowych "
        "(addresses)",
    ),
    "area_result_description": Text(
        "Downloads the objects that intersect the area (GeoPackage; `admin` and "
        "`geomorphology`: the units of `level`).",
        "obiekty przecinajace obszar (GeoPackage; admin i geomorphology: jednostki "
        "poziomu --level)",
    ),
    "whole_country_description": Text(
        "National file of one country (needs `country` pl or cz; `addresses` and "
        "`special` also need `format`). The size is in a notice before the download.",
        "Plik krajowy jednego kraju (wymaga --country pl albo cz; addresses i special "
        "takze --format); rozmiar z serwera w Warning przed pobraniem",
    ),
    "commands_rule": Text(
        "Give `level` with an area for `admin` and `geomorphology`.",
        "Podaj `level` z obszarem dla `admin` i `geomorphology`.",
    ),
    "example_prg_boundaries_voivodeship_package": Text(
        "PRG boundaries: a voivodeship package",
        "Granice PRG: paczka wojewodztwa",
    ),
    "example_pl_municipalities_rectangle": Text(
        "PL municipalities for a rectangle",
        "Gminy PL dla prostokata",
    ),
    "example_pl_address_points_national_file": Text(
        "PL address points: the national file",
        "Punkty adresowe PL: plik krajowy",
    ),
    "example_cz_municipalities_ruian_rectangle_s_jtsk": Text(
        "CZ municipalities (RUIAN) for a rectangle in S-JTSK",
        "Obce CZ (RUIAN) dla prostokata w S-JTSK",
    ),
    "example_pl_municipalities_cz_obce_rectangle_border": Text(
        "PL municipalities and CZ obce for a rectangle on the border (country auto)",
        "Gminy PL i obce CZ dla prostokata na granicy (--country auto)",
    ),
    "example_pl_special_boundaries_rectangle_takes": Text(
        "PL special boundaries for a rectangle (takes minutes)",
        "Granice specjalne PL dla prostokata (trwa minuty)",
    ),
    "example_cz_geomorphological_units_celky_rectangle": Text(
        "CZ geomorphological units (celky) for a rectangle",
        "Jednostki geomorfologiczne CZ (celky) dla prostokata",
    ),
    "group_summary": Text(
        "Boundaries and addresses: PRG (PL), RUIAN and geomorphological units (CZ)",
        "Granice i adresy: PRG (PL), RUIAN i jednostki geomorfologiczne (CZ)",
    ),
    "group_description": Text(
        "Administrative and cadastral boundaries, address points and special "
        "boundaries from PRG (GUGiK, PL), territorial units from RUIAN and "
        "geomorphological units (CUZK, CZ) in the versioned store.",
        "Granice jednostek administracyjnych i ewidencyjnych, punkty adresowe i "
        "granice specjalne z PRG (GUGiK, PL), jednostki terytorialne z RUIAN i "
        "jednostki geomorfologiczne (CUZK, CZ) w magazynie wersji.",
    ),
}
