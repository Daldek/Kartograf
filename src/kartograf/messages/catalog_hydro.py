"""Messages of the command catalog: the declarations of ``hydro``."""

from kartograf.messages import Text

MESSAGES = {
    "download_summary": Text(
        "Download hydrography: HY-NET (CZ), PGW water management plans (PL) or "
        "CAMELS-PL catchments (PL)",
        "Pobierz hydrografię: HY-NET (CZ), plany gospodarowania wodami PGW (PL) albo "
        "zlewnie CAMELS-PL (PL)",
    ),
    "download_description": Text(
        "HY-NET of CUZK: streams and nodes crossing an area (GeoPackage, EPSG:5514) "
        "or the national ZIP (EPSG:3045). PGW Wody Polskie: the national ZIP of the "
        "IIaPGW geodatabase (EPSG:2180) or its layers crossing an area (GeoPackage), "
        "read from that archive in the store. CAMELS-PL: the catchments and gauges "
        "of a release (two GeoPackages, EPSG:2180), read from its Zenodo ZIP by "
        "range requests. Never overwrites.",
        "Sieć wód HY-NET CUZK: cieki i węzły przecinające obszar (GeoPackage, "
        "EPSG:5514) albo krajowy ZIP (GeoPackage, EPSG:3045). PGW Wody Polskie: "
        "krajowy ZIP geobazy IIaPGW (EPSG:2180) albo obiekty jej warstw "
        "przecinające obszar (GeoPackage), czytane z tego archiwum w magazynie. "
        "CAMELS-PL: zlewnie i wodowskazy wydania (dwa GeoPackage, EPSG:2180), "
        "czytane z jego ZIP w Zenodo zapytaniami o zakres. Nigdy nie nadpisuje.",
    ),
    "area_result_description": Text(
        "HY-NET: downloads the stream segments and nodes that intersect the area (one "
        "GeoPackage); PGW: the whole features of the spatial layers that intersect the "
        "area's envelope (one GeoPackage, EPSG:2180), read from the national archive "
        "in the store (downloaded once when missing).",
        "HY-NET: odcinki cieków i węzły przecinające obszar (GeoPackage); PGW: całe "
        "obiekty warstw przestrzennych przecinające prostokąt obszaru (GeoPackage, "
        "EPSG:2180), czytane z archiwum krajowego w magazynie (pobieranego raz, gdy "
        "go brak)",
    ),
    "layers_description": Text(
        "PGW area only: the feature datasets of the geodatabase whose layers the "
        "GeoPackage holds, any letter case - PGW_WP (surface water bodies, their "
        "catchments, river basin districts, water regions), JCWPd (groundwater "
        "bodies), SIG (protected areas). Not given: every spatial layer.",
        "Tylko obszar PGW: zbiory obiektów geobazy, których warstwy trafią do "
        "GeoPackage, wielkość liter dowolna - PGW_WP (jednolite części wód "
        "powierzchniowych, ich zlewnie, obszary dorzeczy, regiony wodne), JCWPd "
        "(jednolite części wód podziemnych), SIG (obszary chronione). Bez opcji: "
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
    "version_description": Text(
        "CAMELS-PL only: the release whose files are read (its Zenodo record); without "
        "it the newest the registry supports. A release the registry refuses (1.0.0) "
        "or does not know is an error that names the releases it reads.",
        "Tylko CAMELS-PL: wydanie, którego pliki są czytane (jego rekord Zenodo); bez "
        "opcji najnowsze obsługiwane. Wydanie odrzucone (1.0.0) albo nieznane to "
        "błąd, który podaje czytane wydania.",
    ),
    "rule_version_applies_only_camels": Text(
        "--version applies only to --product camels",
        "--version dotyczy tylko --product camels",
    ),
    "whole_country_description": Text(
        "National file: with `country=cz` HY-NET.zip with a GeoPackage in EPSG:3045, "
        "with `country=pl` the ZIP of the IIaPGW geodatabase (File Geodatabase, "
        "EPSG:2180, edition 2023-09-15) or, for `product=camels`, the catchments and "
        "the gauging stations of a CAMELS-PL release (two GeoPackages, EPSG:2180; "
        "`version`). The size is in a notice before the download.",
        "Plik krajowy: z --country cz HY-NET.zip z GeoPackage w EPSG:3045, z "
        "--country pl ZIP geobazy IIaPGW (File Geodatabase, EPSG:2180, wydanie "
        "2023-09-15) albo, dla --product camels, zlewnie i wodowskazy wydania "
        "CAMELS-PL (dwa GeoPackage, EPSG:2180; --version); rozmiar w Warning przed "
        "pobraniem",
    ),
    "check_description": Text(
        "Signal: the HTTP headers of the national HY-NET file; the network of an area "
        "and the PGW archive have none (cannot be checked without downloading); a PGW "
        "area GeoPackage is current when it was written from the local archive. The "
        "CAMELS-PL files are current when a version holds the bytes the registry pins "
        "for the release (no transfer), and the record of its concept DOI tells of a "
        "newer release (a notice).",
        "Porównaj plik krajowy HY-NET ze źródłem bez pobierania: nagłówki HTTP "
        "(ETag/Last-Modified); sieć obszaru i archiwum PGW nie mają taniego sygnału "
        "(nie da się sprawdzić bez pobrania), GeoPackage obszaru PGW jest aktualny, "
        "gdy zapisano go z lokalnego archiwum; pliki CAMELS-PL są aktualne, gdy "
        "wersja ma bajty, które rejestr przypina dla wydania (bez pobierania), a "
        "rekord ich DOI koncepcji mówi o nowszym wydaniu (komunikat); brakujący plik "
        "= do pobrania",
    ),
    "example_water_network_rectangle_s_jtsk": Text(
        "Water network for a rectangle in S-JTSK",
        "Sieć wód dla prostokąta w S-JTSK",
    ),
    "example_water_network_national_file": Text(
        "Water network: the national file",
        "Sieć wód: plik krajowy",
    ),
    "example_pgw_national_archive": Text(
        "Water management plans: the national geodatabase archive",
        "Plany gospodarowania wodami: krajowe archiwum geobazy",
    ),
    "example_pgw_area_surface_waters": Text(
        "Water management plans: the surface water layers of a rectangle in EPSG:2180",
        "Plany gospodarowania wodami: warstwy wód powierzchniowych prostokąta w "
        "EPSG:2180",
    ),
    "example_camels_newest_release": Text(
        "CAMELS-PL: the catchment boundaries and gauging stations of the newest "
        "release",
        "CAMELS-PL: granice zlewni i wodowskazy najnowszego wydania",
    ),
    "example_camels_release": Text(
        "CAMELS-PL: the files of release 2.0.0",
        "CAMELS-PL: pliki wydania 2.0.0",
    ),
    "group_summary": Text(
        "Hydrography: the water network (HY-NET, CZ), the water management plans "
        "(PGW, PL) and the CAMELS-PL catchments (PL)",
        "Hydrografia: sieć wód (HY-NET CZ), plany gospodarowania wodami (PGW PL) i "
        "zlewnie CAMELS-PL (PL)",
    ),
    "group_description": Text(
        "The HY-NET hydrographic network (CUZK, CZ; INSPIRE Hydrography - Network), "
        "the IIaPGW geodatabase of the water management plans (PGW Wody Polskie, PL) "
        "and the catchment boundaries and gauging stations of CAMELS-PL (the gauges "
        "of IMGW-PIB, Zenodo) in the versioned store.",
        "Sieć hydrograficzna HY-NET (CUZK, CZ; INSPIRE Hydrography - Network), "
        "geobaza IIaPGW planów gospodarowania wodami (PGW Wody Polskie, PL) oraz "
        "granice zlewni i wodowskazy CAMELS-PL (wodowskazy IMGW-PIB, Zenodo) w "
        "magazynie wersji.",
    ),
}
