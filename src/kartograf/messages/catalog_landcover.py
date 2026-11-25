"""Messages of the command catalog: the declarations of ``landcover``."""

from kartograf.messages import Text

MESSAGES = {
    "teryt_description": Text(
        "TERYT code: a BDOT10k county (4 digits, `1465`) or a BDOO voivodeship (2 "
        "digits, `12`).",
        "Kod TERYT: powiat BDOT10k (4 cyfry, np. 1465) albo województwo BDOO (2 "
        "cyfry, np. 12)",
    ),
    "whole_country_description": Text(
        "ZABAGED, Data50 and Data250 only: the national file instead of an area (a "
        "ZIP as published: ZABAGED GeoPackage of the whole base, several GB; Data50 "
        "and Data250 Shapefile, 230-760 MB; needs `horizontal_crs`). The size is in a "
        "notice before the download.",
        "Tylko ZABAGED, Data50 i Data250: plik krajowy zamiast obszaru (ZIP 1:1 - "
        "ZABAGED: GeoPackage pełnej bazy, kilka GB; Data50/Data250: Shapefile, "
        "230-760 MB; wymaga --horizontal-crs); rozmiar z feedu w Warning przed "
        "pobraniem",
    ),
    "year_description": Text(
        "Data year. CORINE (required): edition 2018, 2012, 2006 or 2000 (CLMS/WMS "
        "land cover), 1990 (WMS preview only). BDOT10k: archive year 2014-2025 (needs "
        "`format` GML or SHP; the original county ZIP), without it the current "
        "packages. BDOO (required): 2015 or 2021-2026 (the original voivodeship "
        "ZIP).{bdot10k_archive_choices:skip}{bdoo_year_choices:skip}",
        "Rok danych. CORINE (wymagany): wydanie (rok referencyjny) 2018, 2012, 2006, "
        "2000 (edycje pokrycia terenu CLMS/WMS), 1990 (tylko podgląd WMS). BDOT10k: "
        "rocznik archiwum (stan z początku roku) {bdot10k_archive_choices} - "
        "oryginalna paczka powiatu ZIP; bez --year bieżące paczki. BDOO (wymagany): "
        "rocznik {bdoo_year_choices} - oryginalna paczka województwa ZIP",
    ),
    "format_description": Text(
        "BDOT10k only: the current packages as GPKG (default) or SHP; with `year` "
        "(the yearly archive) GML or SHP is required.",
        "Tylko BDOT10k: bieżące paczki GPKG (GeoPackage, domyślnie) lub SHP (archiwum "
        "ZIP z plikami Shapefile); z --year (archiwum roczników) wymagany GML albo SHP",
    ),
    "layers_description": Text(
        "Layer or class codes, for example `SWRS` and `PTWP`; default all. Current "
        "BDOT10k GPKG: keeps the chosen layers. BDOO: a ZIP of the chosen classes of "
        "each package (no complex objects, XSD or metadata). Codes: `landcover "
        "list-layers`.",
        "Kody po przecinku (np. SWRS,PTWP); domyślnie wszystkie. Bieżące BDOT10k "
        "GPKG: zostaw wybrane warstwy. BDOO: ZIP plików wybranych klas z każdej "
        "paczki (bez obiektów złożonych, XSD i metadanych). Lista: landcover "
        "list-layers",
    ),
    "keep_raw_description": Text(
        "Current BDOT10k GPKG only: also keep the original GUGiK ZIP next to the file "
        "(a raw version in the store).",
        "Tylko bieżące BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok pliku (wersja "
        "surowa w magazynie)",
    ),
    "horizontal_crs_description": Text(
        "CRS of the national file; required with `whole_country` (ZABAGED, Data50, "
        "Data250). Area results are always in the service CRS EPSG:5514.",
        "Tylko --whole-country (ZABAGED, Data50, Data250; wymagany): układ pliku "
        "krajowego; wynik obszaru zawsze w układzie usługi EPSG:5514",
    ),
    "check_description": Text(
        "Signal: the release of CORINE (CLMS) and of the national ZABAGED, Data50 and "
        "Data250 files; BDOT10k, BDOO, the CORINE preview and CUZK areas have none.",
        "Porównaj lokalne wersje ze źródłem bez pobierania: CORINE (CLMS) i pliki "
        "krajowe ZABAGED, Data50, Data250 - wydanie źródła; BDOT10k, BDOO, podgląd "
        "CORINE i obszary CUZK - brak taniego sygnału (nie da się sprawdzić bez "
        "pobrania)",
    ),
    "workers_description": Text(
        "BDOT10k or BDOO area only (several counties or voivodeships): parallel "
        "transfers, default 1.",
        "Tylko obszar BDOT10k albo BDOO (wiele powiatów albo województw): liczba "
        "równoległych pobrań (domyślnie 1)",
    ),
    "rule_give_exactly_one_area_teryt_sheet_bbox": Text(
        "Give exactly one area: --teryt, --sheet, --bbox, --geometry or "
        "--whole-country",
        "Podaj dokładnie jeden obszar: --teryt, --sheet, --bbox, --geometry albo "
        "--whole-country",
    ),
    "rule_whole_country_needs_horizontal_crs": Text(
        "--whole-country needs --horizontal-crs",
        "--whole-country wymaga --horizontal-crs",
    ),
    "rule_keep_raw_applies_only_current_bdot10k": Text(
        "--keep-raw applies only to the current BDOT10k packages",
        "--keep-raw dotyczy tylko bieżących paczek BDOT10k",
    ),
    "rule_whole_country_applies_only_zabaged_data50": Text(
        "--whole-country applies only to ZABAGED, Data50 and Data250",
        "--whole-country dotyczy tylko ZABAGED, Data50 i Data250",
    ),
    "landcover_download_summary": Text(
        "Download land cover: BDOT10k, BDOO, CORINE, ZABAGED, Data50 or Data250",
        "Pobierz dane wybranego produktu pokrycia terenu",
    ),
    "landcover_download_rule": Text(
        "`year` is required for CORINE and BDOO.",
        "`year` jest wymagany dla CORINE i BDOO.",
    ),
    "example_bdot10k_county_package": Text(
        "BDOT10k: a county package",
        "BDOT10k: paczka powiatu",
    ),
    "example_bdoo_voivodeship_package_2023_archive": Text(
        "BDOO: a voivodeship package of the 2023 archive",
        "BDOO: paczka województwa z rocznika 2023",
    ),
    "example_corine_2018_sheet": Text(
        "CORINE 2018 for a sheet",
        "CORINE 2018 dla arkusza",
    ),
    "example_cz_zabaged_rectangle_s_jtsk": Text(
        "CZ ZABAGED for a rectangle in S-JTSK",
        "ZABAGED (CZ) dla prostokąta w S-JTSK",
    ),
    "landcover_list_layers_summary": Text(
        "List the layers, classes or years of a land-cover product (offline)",
        "Wypisz warstwy wybranego produktu",
    ),
    "landcover_list_layers_description": Text(
        "Lists the layers of BDOT10k, ZABAGED, Data50 and Data250, the BDOO classes "
        "per archive year or the CORINE years. Use it to choose `layers` and `year` "
        "for `landcover download`.",
        "Wypisz warstwy BDOT10k, ZABAGED, Data50 i Data250, klasy BDOO wg roczników "
        "albo lata CORINE (bez sieci)",
    ),
    "group_description": Text(
        "Command group (here: landcover); list_layers serves landcover and soil",
        "Grupa komend (tu: landcover); list_layers obsługuje landcover i soil",
    ),
    "example_classes_bdoo_per_archive_year": Text(
        "The classes of BDOO per archive year",
        "Klasy BDOO wg roczników",
    ),
    "example_years_corine": Text("The years of CORINE", "Roczniki CORINE"),
    "landcover_group_summary": Text(
        "Land cover: BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250",
        "Pokrycie terenu: BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250",
    ),
    "landcover_group_description": Text(
        "Land cover and general geographic databases in the versioned store: the "
        "vector databases BDOT10k and BDOO (GUGiK, PL), CORINE Land Cover "
        "(Copernicus, EU), ZABAGED, Data50 and Data250 (CUZK, CZ).",
        "Pokrycie terenu i bazy ogólnogeograficzne: wektorowe bazy BDOT10k i BDOO "
        "(GUGiK, PL), CORINE Land Cover (Copernicus, UE), ZABAGED, Data50 i Data250 "
        "(CUZK, CZ) w magazynie wersji.",
    ),
    "sheet_description": Text(
        "{sheet} BDOT10k: the counties that intersect the sheet; BDOO: the "
        "voivodeships.",
        "{sheet}; BDOT10k: powiaty przecinające arkusz, BDOO: województwa",
    ),
    "download_upgrade_description": Text(
        "Fetch a newer release of CORINE or of the CUZK national file (default: "
        "information only); BDOT10k, BDOO, the CORINE preview and the CUZK areas stay "
        "local (fetch them with --force); with --plan run the saved plan",
        "Pobierz nowsze wydanie CORINE albo pliku krajowego CUZK (domyślnie tylko "
        "informacja); BDOT10k, BDOO, podgląd CORINE i obszary CUZK zostają lokalne "
        "(pobranie: --force); z --plan wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file again (BDOT10k and BDOO: also refresh the area units from "
        "PRG); the same content = unchanged, other content = a new version",
        "Pobierz ponownie każdy plik (BDOT10k i BDOO: także odśwież jednostki obszaru "
        "z PRG); ta sama treść = bez zmian, inna = nowa wersja",
    ),
    "download_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (kartograf-plan/1); z "
        "--upgrade: wykonaj plan (pozycje zmienione od planu = błąd)",
    ),
    "landcover_download_description": Text(
        "Fetches one land-cover product for one area (`teryt`, `sheet`, `bbox` or "
        "`geometry`): BDOT10k county packages or archive, BDOO voivodeship packages, "
        "CORINE, or the ZABAGED, Data50 and Data250 GeoPackage of the area or the "
        "national file (CZ). Never overwrites: new content is a new version. {note} "
        "Not for soil (`soil download`).",
        "Pobierz dane wybranego produktu (--product) dla jednego obszaru: --teryt, "
        "--sheet, --bbox albo --geometry. BDOT10k obszaru = paczki każdego powiatu, "
        "który obszar przecina (PRG); z --year paczki z archiwum roczników BDOT10k "
        "(GML albo SHP, zapis 1:1). BDOO (--year wymagany): oryginalna paczka GML "
        "województwa (--teryt 2 cyfry; obszar = paczki województw, które przecina, wg "
        "PRG); --layers zostawia pliki wybranych klas. ZABAGED, Data50 i Data250 "
        "(CZ): obszar (--bbox/--geometry) = jeden GeoPackage warstw usługi w "
        "EPSG:5514 (ZABAGED: pokrycie terenu i wody, Data50/Data250: wszystkie "
        "warstwy obiektowe; nazwy CUZK, bez przeliczenia na kody BDOT10k; lista: "
        "landcover list-layers), --whole-country = plik krajowy z feedu ATOM CUZK "
        "(ZABAGED: GPKG, Data50/Data250: SHP; zapis 1:1). {note}",
    ),
}
