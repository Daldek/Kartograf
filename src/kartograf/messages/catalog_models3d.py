"""Messages of the command catalog: the declarations of ``models3d``."""

from kartograf.messages import Text

MESSAGES = {
    "lod_description": Text(
        "Level of detail of the packages; required when the product has several "
        "(buildings: 1 or 2; trees: 1), may be omitted for the only "
        "one.{collection_variant_choices:skip}",
        "Poziom szczegółowości paczek modeli (wymagany, gdy produkt ma kilka; jedyny "
        "można pominąć): {collection_variant_choices}",
    ),
    "year_description": Text(
        "Year: the release of the packages (required when the level has several "
        "releases, see `lod`; may be omitted for the only one) or the data year of "
        "mesh tiles (only the tiles of that year; without it every year).",
        "Rok: wydanie paczek (wymagany, gdy poziom ma kilka wydań - lista przy --lod; "
        "jedyne wydanie można pominąć) albo rok danych kafli mesh (filtr: tylko kafle "
        "tego roku; bez niego kafle wszystkich lat)",
    ),
    "download_summary": Text(
        "Download 3D models: building and tree county packages or city mesh tiles (PL)",
        "Pobierz paczki modeli 3D powiatów albo kafle mesh obszaru",
    ),
    "download_description": Text(
        "`buildings` and `trees` (CityGML; `lod` and `year` choose the release): a "
        "county package (`teryt`) or the packages of the counties an area crosses. "
        "`mesh`: the city mesh tiles (OBJ with textures) that cross an area. Packages "
        "are stored as published. An area above 100 files or 10 GB is refused before "
        "any download: narrow it or choose a county.",
        "Pobierz modele 3D do magazynu wersji. --product buildings (budynki) i trees "
        "(drzewa, CityGML LoD1 2023, paczka 0,3-25 GB): paczka powiatu (--teryt 4 "
        "cyfry) albo paczki każdego powiatu, który obszar przecina "
        "(--bbox/--sheet/--geometry; powiaty z PRG); wydanie wybierają --lod i "
        "--year. Brak paczki powiatu (LoD2 budynków, drzewa części powiatów) = błąd "
        "tego powiatu. --product mesh: kafle indeksu GUGiK przecinające obszar "
        "(--bbox/--sheet/--geometry), każdy plik kafla w katalogu swojego układu "
        "(1992 albo 2000/<strefa>, np. 2000/7); --year wybiera kafle jednego roku. "
        "Paczki ZIP zapisywane 1:1, układ wysokości z danych w sidecarze. Obszar, "
        "który dałby więcej niż 100 plików albo ponad 10 GB, kończy się błędem przed "
        "pobraniem: zawęź obszar albo wybierz powiat.",
    ),
    "teryt_description": Text(
        "TERYT code of a county (4 digits, `1261`): the model package of the county "
        "(`buildings`, `trees`).",
        "Kod TERYT powiatu (4 cyfry, np. 1261): paczka modeli powiatu (buildings, "
        "trees)",
    ),
    "area_result_description": Text(
        "Downloads the packages of the counties the area crosses (PRG; `buildings`, "
        "`trees`) or the mesh tiles of the area.",
        "paczki powiatów przecinających obszar (PRG; buildings, trees) albo kafle "
        "mesh obszaru",
    ),
    "check_description": Text(
        "Signal: for a mesh tile the label of its index record (date and work "
        "number); building and tree packages have none.",
        "Porównaj lokalne wersje ze źródłem bez pobierania: kafel mesh - etykieta "
        "rekordu indeksu (data i numer zgłoszenia pracy); paczki budynków i drzew nie "
        "mają taniego sygnału (nie da się sprawdzić bez pobrania), brakujące pliki = "
        "do pobrania",
    ),
    "commands_rule": Text(
        "Give `lod`, and `year` when the level has several releases.",
        "Podaj `lod` i `year`, gdy poziom ma kilka wydań.",
    ),
    "example_buildings_lod1_2024_county_package": Text(
        "Buildings LoD1 2024: a county package",
        "Budynki LoD1 2024: paczka powiatu",
    ),
    "example_city_mesh_tiles_rectangle": Text(
        "City mesh: tiles for a rectangle",
        "Mesh miast: kafle dla prostokąta",
    ),
    "example_trees_lod1_2023_county_package_0_3_25_gb": Text(
        "Trees LoD1 2023: a county package (0.3-25 GB)",
        "Drzewa LoD1 2023: paczka powiatu (0,3-25 GB)",
    ),
    "group_summary": Text(
        "3D models: buildings and trees (CityGML), city meshes (OBJ)",
        "Modele 3D: budynki i drzewa (CityGML), mesh miast (OBJ)",
    ),
    "group_description": Text(
        "GUGiK 3D models (PL) in the versioned store: buildings and trees (CityGML, "
        "county packages) and city mesh models (OBJ with textures, index tiles).",
        "Modele 3D GUGiK (PL) w magazynie wersji: budynki i drzewa (CityGML, paczki "
        "powiatów) oraz modele siatkowe miast (mesh OBJ z teksturami, kafle indeksu).",
    ),
}
