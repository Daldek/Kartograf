"""Messages of the command catalog: the declarations of ``geodesy``."""

from kartograf.messages import Text

MESSAGES = {
    "network_description": Text(
        "Control network (required with `product=control`). One value applies to "
        'every country of the task, or give {{"pl": "horizontal", "cz": '
        '"gnss"}}.{choice_text:skip}',
        "Sieć osnowy (--product control; wymagana): {choice_text}. Jedna wartość "
        "dotyczy każdego kraju zadania; zadanie PL+CZ (--country auto) z różnymi: "
        "pl=SIEĆ,cz=SIEĆ (np. pl=horizontal,cz=gnss)",
    ),
    "download_summary": Text(
        "Download control points, county packages, sheet archives or a quasi-geoid",
        "Pobierz punkty osnowy obszaru, paczkę powiatu, archiwum arkusza albo model "
        "quasi-geoidy",
    ),
    "download_description": Text(
        "`control`: network points that cross an area (GeoPackage; PL EPSG:2180, CZ "
        "EPSG:5514), a county package of the horizontal or vertical network "
        "(`teryt`), or the archive catalogues of 1:100000 sheets (`network` "
        "archive-*). `geoid`: the national quasi-geoid model, with `whole_country`. "
        "Files are stored as published; no model is applied.",
        "Pobierz do magazynu wersji. --product control: punkty sieci --network "
        "przecinające obszar (--bbox/--sheet/--geometry; GeoPackage w układzie "
        "usługi: PL EPSG:2180, CZ EPSG:5514; sieć CZ = suma jej warstw), paczka "
        "powiatu sieci horizontal albo vertical (--teryt 4 cyfry; wykazy "
        "współrzędnych XLS i opisy topograficzne JPG) albo archiwalne katalogi "
        "punktów arkuszy 1:100 000 obszaru (--network "
        "archive-1942|archive-kronsztadt60; skany PDF i TIFF). --product geoid: model "
        "quasi-geoidy, jeden plik krajowy (--whole-country --country pl: "
        "PL-geoid2021, TXT; --country cz: QGZU-2013, ZIP siatek TXT). Pliki "
        "zapisywane 1:1; Kartograf nie stosuje modeli do innych danych.",
    ),
    "teryt_description": Text(
        "TERYT code of a county (4 digits, `1201`): the package of the horizontal or "
        "vertical network (`network` horizontal or vertical).",
        "Kod TERYT powiatu (4 cyfry, np. 1201): paczka sieci poziomej albo "
        "wysokościowej (--network horizontal|vertical)",
    ),
    "area_result_description": Text(
        "Downloads the network points of the area (GeoPackage) or the archives of the "
        "1:100000 sheets of the area.",
        "punkty sieci obszaru (GeoPackage) albo archiwa arkuszy 1:100 000 obszaru",
    ),
    "whole_country_description": Text(
        "The national quasi-geoid model (`product=geoid`; needs `country` pl or cz). "
        "The size is in a notice before the download.",
        "Model quasi-geoidy kraju (--product geoid; wymaga --country pl albo cz); "
        "rozmiar z serwera w Warning przed pobraniem",
    ),
    "check_description": Text(
        "Signal: the release date of QGZU (CZ) in the ATOM feed; control points, "
        "packages, archives and PL-geoid2021 have none.",
        "Porównaj lokalne wersje ze źródłem bez pobierania: QGZU (CZ) - data wydania "
        "w feedzie ATOM; punkty osnów, paczki, archiwa i PL-geoid2021 nie mają "
        "taniego sygnału (nie da się sprawdzić bez pobrania), brakujące pliki = do "
        "pobrania",
    ),
    "example_pl_horizontal_control_county_package": Text(
        "PL horizontal control: a county package",
        "Osnowa pozioma PL: paczka powiatu",
    ),
    "example_pl_vertical_control_rectangle": Text(
        "PL vertical control for a rectangle",
        "Osnowa wysokościowa PL dla prostokąta",
    ),
    "example_cz_quasi_geoid_qgzu_2013_national_file": Text(
        "CZ quasi-geoid QGZU-2013: the national file",
        "Quasi-geoida QGZU-2013 (CZ): plik krajowy",
    ),
    "group_summary": Text(
        "Geodetic control and quasi-geoids: PRPOG, PL-geoid2021 (PL), Bodove pole, "
        "QGZU (CZ)",
        "Osnowy geodezyjne i quasi-geoidy: PRPOG, PL-geoid2021 (PL), Bodove pole, "
        "QGZU (CZ)",
    ),
    "group_description": Text(
        "Points of geodetic control networks (GUGiK, CUZK) and the quasi-geoid models "
        "PL-geoid2021 and QGZU-2013 in the versioned store.",
        "Punkty osnów geodezyjnych (GUGiK, CUZK) i modele quasi-geoidy PL-geoid2021 i "
        "QGZU-2013 w magazynie wersji.",
    ),
}
