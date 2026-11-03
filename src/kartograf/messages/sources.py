"""Messages of the source registry: descriptors, channels, variants and sidecars."""

from kartograf.messages import Text

MESSAGES = {
    # ``sources.descriptor``.
    "empty_segment_dimension": Text(
        "Empty storage segment dimension '{name}' (source '{source_key}') - give a "
        "value or None",
        "Pusty wymiar segmentu storage '{name}' (zrodlo '{source_key}') - podaj "
        "wartosc albo None",
    ),
    # ``sources.edition``.
    "edition_invalid_label": Text(
        "{what}: edition {raw!r} is not usable as a version label (allowed: "
        "[A-Za-z0-9._+-])",
        "{what}: wydanie {raw!r} nie nadaje sie na etykiete wersji (dozwolone "
        "[A-Za-z0-9._+-])",
    ),
    # ``sources.registry``.
    "product_name_nmt": Text("Digital Terrain Model", "Numeryczny Model Terenu"),
    "product_name_nmpt": Text(
        "Digital Surface Model",
        "Numeryczny Model Pokrycia Terenu",
    ),
    "nmt_wcs_notes": Text(
        "KRON86 GeoTIFF float32, EVRF2007 only image/x-aaigrid (saved as GeoTIFF "
        "float32); 1 m sheet grid",
        "KRON86 GeoTIFF float32, EVRF2007 tylko image/x-aaigrid (zapisywany jako "
        "GeoTIFF float32); siatka arkuszy 1 m",
    ),
    "nmpt_wcs_notes": Text(
        "heights only image/x-aaigrid (saved as GeoTIFF float32); 1 m via "
        "SCALEFACTOR=0.5 on the 1 m sheet grid",
        "wysokosci tylko image/x-aaigrid (zapisywany jako GeoTIFF float32); 1 m przez "
        "SCALEFACTOR=0.5 na siatce arkuszy 1 m",
    ),
    "sheet_source_name": Text(
        "{product_name} - {format} archive{shown_suffix} ({description}; source file)",
        "{product_name} - archiwum {format}{shown_suffix} ({description}; plik "
        "zrodlowy)",
    ),
    "sheet_index_source_file": Text(
        "GUGiK WFS sheet index; file as in the source (no conversion)",
        "skorowidz WFS GUGiK; plik jak w zrodle (bez konwersji)",
    ),
    "sheet_index_opendata": Text(
        "GUGiK WFS sheet index; OpenData sheets",
        "skorowidz WFS GUGiK; arkusze OpenData",
    ),
    "cz_file_note_sm5": Text(
        "SM5 sheets (S-JTSK, Bpv heights); file 1:1 from ZIP, CRS from the channel",
        "arkusze SM5 (S-JTSK, wysokosci Bpv); plik 1:1 z ZIP, CRS z kanalu",
    ),
    "cz_file_note_tm33": Text(
        "TM33 2x2 km tiles (ETRS89, EVRF2007 heights); file 1:1 from ZIP",
        "kafle TM33 2x2 km (ETRS89, wysokosci EVRF2007); plik 1:1 z ZIP",
    ),
    "cz_tm33_scheme": Text(
        "TM33 {{E_km}}_{{N_km}}, SW corner",
        "TM33 {{E_km}}_{{N_km}}, naroznik SW",
    ),
    "cz_sm5_scheme": Text(
        "SM5: 2 or 4 city letters + 2 digits (KladyMapovychListu index, layer 24); "
        "TM33 tiles {{E_km}}_{{N_km}} (layer 26)",
        "SM5: 2 albo 4 litery miasta + 2 cyfry (indeks KladyMapovychListu w. 24); "
        "kafle TM33 {{E_km}}_{{N_km}} (w. 26)",
    ),
    "cz_image_notes": Text(
        "The server supports imageSR, but ADR-024 forbids it - content reprojection "
        "is local only, a pinned operation",
        "Serwer obsluguje imageSR, ale ADR-024 zabrania - reprojekcja tresci "
        "wylacznie lokalna, przypieta operacja",
    ),
    "cz_zabaged_notes": Text(
        "22 land cover and hydrography layers (source names); full geometries of "
        "features intersecting the area",
        "22 warstwy pokrycia terenu i hydrografii (nazwy zrodla); pelne geometrie "
        "obiektow przecinajacych obszar",
    ),
    "cz_zabaged_area_omitted": Text(
        "the area result has 22 land cover and water layers; the full ZABAGED "
        "database is in the national file: --whole-country --horizontal-crs "
        "EPSG:5514|EPSG:3045",
        "wynik obszaru ma 22 warstwy pokrycia terenu i wod; pelna baza ZABAGED jest w "
        "pliku krajowym: --whole-country --horizontal-crs EPSG:5514|EPSG:3045",
    ),
    "zabaged_national_gpkg_note": Text(
        "national GPKG file (5.8 GB EPSG:5514, 6.7 GB EPSG:3045; layers of the full "
        "database under CUZK names), only with --whole-country",
        "plik krajowy GPKG (5,8 GB EPSG:5514, 6,7 GB EPSG:3045; warstwy pelnej bazy "
        "pod nazwami CUZK), tylko z --whole-country",
    ),
    "ruian_admin_name": Text(
        "RUIAN - boundaries of territorial units (regions, districts, municipalities, "
        "cadastral areas)",
        "RUIAN - granice jednostek terytorialnych (kraje, okresy, obce, k.u.)",
    ),
    "ruian_area_note": Text(
        "full geometries of units intersecting the area",
        "pelne geometrie jednostek przecinajacych obszar",
    ),
    "ruian_national_shp_note": Text(
        "national SHP file (approx. 253 MB), only with --whole-country",
        "plik krajowy SHP (ok. 253 MB), tylko z --whole-country",
    ),
    "hynet_network_name": Text(
        "HY-NET - hydrographic network (INSPIRE Hydrography - Network)",
        "HY-NET - siec hydrograficzna (INSPIRE Hydrography - Network)",
    ),
    "hynet_area_note": Text(
        "watercourse segments and network nodes intersecting the area "
        "(grade-separated crossings - relations without geometry - only in the "
        "national file)",
        "odcinki ciekow i wezly sieci przecinajace obszar (skrzyzowania bezkolizyjne "
        "- relacje bez geometrii - tylko w pliku krajowym)",
    ),
    "hynet_area_omitted": Text(
        "area result without grade-separated crossings (type "
        "WatercourseSeparatedCrossing: segment relations without geometry, the "
        "service does not count them in the area) - they are in the national file: "
        "--whole-country --country cz",
        "wynik obszaru bez skrzyzowan bezkolizyjnych (typ "
        "WatercourseSeparatedCrossing: relacje odcinkow bez geometrii, usluga nie "
        "liczy ich w obszarze) - sa w pliku krajowym: --whole-country --country cz",
    ),
    "hynet_national_gpkg_note": Text(
        "national GPKG file (approx. 194 MB) in EPSG:3045 (ATOM feed category), only "
        "with --whole-country",
        "plik krajowy GPKG (ok. 194 MB) w EPSG:3045 (kategoria feedu ATOM), tylko z "
        "--whole-country",
    ),
    "cz_dmr5g_name": Text(
        "DMR 5G - Digitalni model reliefu 5. generace (2 m, ImageServer: TM33 tile "
        "and cutout)",
        "DMR 5G - Digitalni model reliefu 5. generace (2 m, ImageServer: kafel TM33 i "
        "wycinek)",
    ),
    "cz_dmr4g_name": Text(
        "DMR 4G - Digitalni model reliefu 4. generace (5 m, SM5 sheets and TM33 tiles)",
        "DMR 4G - Digitalni model reliefu 4. generace (5 m, arkusze SM5 i kafle TM33)",
    ),
    "cz_dmp1g_name": Text(
        "DMP 1G - Digitalni model povrchu 1. generace (2 m, ImageServer: TM33 tile "
        "and cutout)",
        "DMP 1G - Digitalni model povrchu 1. generace (2 m, ImageServer: kafel TM33 i "
        "wycinek)",
    ),
    "cz_dmpok_name": Text(
        "DMP OK - Digitalni model povrchu z obrazove korelace (0.5 m, SM5 sheets and "
        "TM33 tiles)",
        "DMP OK - Digitalni model povrchu z obrazove korelace (0,5 m, arkusze SM5 i "
        "kafle TM33)",
    ),
    "cz_dmr5g_laz_name": Text(
        "DMR 5G - LAZ point cloud (SM5 sheets and TM33 tiles)",
        "DMR 5G - chmura punktow LAZ (arkusze SM5 i kafle TM33)",
    ),
    "cz_dmr4g_laz_name": Text(
        "DMR 4G - LAZ point cloud (5 m grid; SM5 sheets and TM33 tiles)",
        "DMR 4G - chmura punktow LAZ (siatka 5 m; arkusze SM5 i kafle TM33)",
    ),
    "cz_dmp1g_laz_name": Text(
        "DMP 1G - LAZ point cloud (SM5 sheets and TM33 tiles)",
        "DMP 1G - chmura punktow LAZ (arkusze SM5 i kafle TM33)",
    ),
    "cz_dmpok_laz_name": Text(
        "DMP OK - LAZ point cloud (image correlation; SM5 sheets and TM33 tiles)",
        "DMP OK - chmura punktow LAZ (korelacja obrazowa; arkusze SM5 i kafle TM33)",
    ),
    "cz_orto_name": Text(
        "Ortofoto CR (JPEG, SM5 sheets)",
        "Ortofoto CR (JPEG, arkusze SM5)",
    ),
    "cz_orto_notes": Text(
        "current vintage of the sheet (archival CUZK orthophotos are paid - out of "
        "scope); JPEG with JGW files in S-JTSK, TM33N and TM34N",
        "aktualny rocznik arkusza (archiwalne ortofoto CUZK sa platne - poza "
        "zakresem); JPEG z plikami JGW w S-JTSK, TM33N i TM34N",
    ),
    "cz_orto_sheet_scheme": Text(
        "SM5: 2 or 4 letters of the city + 2 digits; KladyMapovychListu index, layer "
        "24",
        "SM5: 2 albo 4 litery miasta + 2 cyfry; indeks KladyMapovychListu w. 24",
    ),
    "nmt100_vertical_crs_note": Text(
        "GUGiK does not declare the vertical CRS of NMT 100 m (ATOM feed and CSW "
        "record without a CRS; model from the NMT of the LPIS project) - vertical CRS "
        "unknown",
        "GUGiK nie deklaruje ukladu wysokosci NMT 100 m (feed ATOM i rekord CSW bez "
        "ukladu; model z NMT projektu LPIS) - uklad wysokosci nieznany",
    ),
    "nmt100_name": Text(
        "Digital terrain model 100 m (XYZ, voivodeship files; vertical CRS unknown)",
        "Numeryczny Model Terenu 100 m (XYZ, pliki wojewodztw; uklad wysokosci "
        "nieznany)",
    ),
    "nmt100_notes": Text(
        "GUGiK ATOM feed: one ZIP with an XYZ file per voivodeship (2019 edition); "
        "voivodeships of the area by PRG; ZIP saved 1:1",
        "feed ATOM GUGiK: jeden ZIP z plikiem XYZ na wojewodztwo (wydanie 2019); "
        "wojewodztwa obszaru wg PRG; ZIP zapisywany 1:1",
    ),
    "intensity_name": Text(
        "LIDAR intensity images (sheets by flight)",
        "Obrazy intensywnosci LIDAR (arkusze wg lotow)",
    ),
    "intensity_notes": Text(
        "GeoTIFF 1 band (reflection intensity), pixel 0.25 m; PL-1992 sheets (7-part "
        "sheet codes) and PL-2000 by flight",
        "GeoTIFF 1 pasmo (intensywnosc odbicia), piksel 0,25 m; arkusze PL-1992 "
        "(godla 7-czlonowe) i PL-2000 wg lotow",
    ),
    "true_orto_name": Text(
        "True orthophoto (true orto) of selected cities (sheets; WCS cutout)",
        "Prawdziwa ortofotomapa (true orto) wybranych miast (arkusze; wycinek WCS)",
    ),
    "true_orto_notes": Text(
        "GeoTIFF RGB, pixel 0.05 m; PL-1992 8-part sheets (GUGiK 1:2500 module) by "
        "flight",
        "GeoTIFF RGB, piksel 0,05 m; arkusze PL-1992 8-czlonowe (modul GUGiK 1:2500) "
        "wg lotow",
    ),
    "true_orto_extent": Text(
        "GUGiK true orto covers only selected cities (e.g. Gdansk)",
        "true orto GUGiK obejmuje tylko wybrane miasta (np. Gdansk)",
    ),
    "true_orto_wcs_desc": Text(
        "true orthophoto 0.05 m of selected cities (outside them pixels 0,0,0)",
        "prawdziwa ortofotomapa 0,05 m wybranych miast (poza nimi piksele 0,0,0)",
    ),
    "oblique_orto_name": Text(
        "Oblique orthophoto of selected cities (PL-2000 sheets, directions N, E, S, W)",
        "Ortofotomapa ukosna wybranych miast (arkusze PL-2000, kierunki N, E, S, W)",
    ),
    "oblique_orto_notes": Text(
        "GeoTIFF RGB, pixel 0.05 m; a sheet is 4 direction files (n, e, s, w); "
        "PL-2000 sheets (1:2000, 1:1000) by flight",
        "GeoTIFF RGB, piksel 0,05 m; arkusz to 4 pliki kierunkow (n, e, s, w); "
        "arkusze PL-2000 (1:2000, 1:1000) wg lotow",
    ),
    "oblique_orto_extent": Text(
        "GUGiK oblique orto covers only selected cities (e.g. Krakow, Gdansk)",
        "orto ukosna GUGiK obejmuje tylko wybrane miasta (np. Krakow, Gdansk)",
    ),
    "cz_contours_name": Text(
        "ZABAGED - 2D contours (vrstevnice; {fmt}, SM5 sheet ZIP)",
        "ZABAGED - warstwice 2D (vrstevnice; {fmt}, ZIP arkusza SM5)",
    ),
    "cz_contours_notes": Text(
        "SM5 sheets (S-JTSK, Bpv heights); ZIP stored 1:1, without unpacking or "
        "conversion",
        "arkusze SM5 (S-JTSK, wysokosci Bpv); ZIP zapisywany 1:1, bez rozpakowania i "
        "konwersji",
    ),
    "prng_world_name": Text(
        "PRNG - Polish geographic names of the world",
        "PRNG - polskie nazwy geograficzne swiata",
    ),
    "prng_poland_name": Text(
        "PRNG - geographic names of Poland",
        "PRNG - nazwy geograficzne RP",
    ),
    "prng_slow_response_note": Text(
        "OGC API PRNG request - the service takes approx. 80-95 s per page of objects "
        "(measured 2026-10-16), wait",
        "zapytanie OGC API PRNG - usluga odpowiada ok. 80-95 s na strone obiektow "
        "(pomiar 2026-10-16), czekaj",
    ),
    "bdot10k_maps_name": Text(
        "BDOT10k topographic map visualisations",
        "Wizualizacje map topograficznych BDOT10k",
    ),
    "cz_geonames_name": Text(
        "Geonames - geographic names of Czechia",
        "Geonames - nazwy geograficzne Czech",
    ),
    "prg_special_name": Text("PRG - special boundaries", "PRG - granice specjalne"),
    "prg_special_area_omitted": Text(
        "area result without census enumeration districts (collection "
        "GranicaObwoduSpisowego: the service takes minutes to respond) - they are in "
        "the national file: --whole-country --format SHP|GML",
        "wynik obszaru bez obwodow spisowych (kolekcja GranicaObwoduSpisowego: usluga "
        "odpowiada minutami) - sa w pliku krajowym: --whole-country --format SHP|GML",
    ),
    "prg_addresses_name": Text(
        "PRG - address points and streets",
        "PRG - punkty adresowe i ulice",
    ),
    "prg_addresses_service_note": Text(
        "address points and streets intersecting the area (service state)",
        "punkty adresowe i ulice przecinajace obszar (stan uslugi)",
    ),
    "prg_addresses_county_note": Text(
        "county SHP package: address points, streets, squares, localities (GUGiK does "
        "not publish voivodeship packages)",
        "paczka SHP powiatu: punkty adresowe, ulice, place, miejscowosci (GUGiK nie "
        "publikuje paczek wojewodztw)",
    ),
    "prg_addresses_national_note": Text(
        "national SHP file (approx. 564 MB) or GML (16 voivodeship files, approx. 804 "
        "MB), only with --whole-country",
        "plik krajowy SHP (ok. 564 MB) albo GML (16 plikow wojewodztw, ok. 804 MB), "
        "tylko z --whole-country",
    ),
    "rcn_daily_export_note": Text(
        "daily-refreshed export of {scope}: GeoPackage with layers "
        "transakcje_dzialki, transakcje_budynki, transakcje_lokale",
        "eksport {scope} odswiezany co dobe: GeoPackage z warstwami "
        "transakcje_dzialki, transakcje_budynki, transakcje_lokale",
    ),
    "rcn_name": Text(
        "RCN - real estate price register (transactions: plots, buildings, premises)",
        "RCN - rejestr cen nieruchomosci (transakcje: dzialki, budynki, lokale)",
    ),
    "cz_geomorphology_name": Text(
        "Geomorphological units of Czechia (from subprovincie to casti)",
        "Jednostki geomorfologiczne Czech (od subprovincie do casti)",
    ),
    "cz_geomorphology_note": Text(
        "full geometries of units of the --level level intersecting the area",
        "pelne geometrie jednostek poziomu --level przecinajacych obszar",
    ),
    "cz_cadastral_map_name": Text(
        "Cadastral map of Czechia (katastralni mapa: SHP, DXF, DGN, VFK)",
        "Mapa katastralna Czech (katastralni mapa: SHP, DXF, DGN, VFK)",
    ),
    "cz_cadastral_map_note": Text(
        "cadastral area (KU) package in one of the formats; KU of the area according "
        "to RUIAN; ZIP saved 1:1",
        "paczka katastralniho uzemi (KU) w jednym z formatow; KU obszaru wg RUIAN; "
        "ZIP zapisywany 1:1",
    ),
    "bdoo_name": Text(
        "BDOO - general geographic objects database (1:250 000)",
        "BDOO - baza danych obiektow ogolnogeograficznych (1:250 000)",
    ),
    "bdoo_gml_package_note": Text(
        "GML package of a voivodeship by vintage (2015, 2021-2026) saved 1:1; with "
        "--layers a ZIP of the files of the selected classes",
        "paczka GML wojewodztwa wg rocznika (2015, 2021-2026) zapisywana 1:1; z "
        "--layers ZIP plikow wybranych klas",
    ),
    "cz_feature_layers_note": Text(
        "{layers_count} feature layers (source names); full geometries of features "
        "intersecting the area",
        "{layers_count} warstw obiektowych (nazwy zrodla); pelne geometrie obiektow "
        "przecinajacych obszar",
    ),
    "cz_national_shp_note": Text(
        "national SHP file ({sizes}), only with --whole-country",
        "plik krajowy SHP ({sizes}), tylko z --whole-country",
    ),
    "mesh_product_name": Text(
        "3D city mesh models (OBJ mesh with textures)",
        "Modele siatkowe 3D miast (mesh OBJ z teksturami)",
    ),
    "mesh_tile_note": Text(
        "tile = file of a WFS index record (ZIP with OBJ, MTL and JPG saved 1:1); "
        "tile CRS from the record (PL-1992, PL-2000 S5-S7), heights PL-EVRF2007-NH",
        "kafel = plik rekordu indeksu WFS (ZIP z OBJ, MTL i JPG zapisywany 1:1); "
        "uklad kafla z rekordu (PL-1992, PL-2000 S5-S7), wysokosci PL-EVRF2007-NH",
    ),
    "trees_product_name": Text(
        "3D tree models (CityGML LoD1)",
        "Modele 3D drzew (CityGML LoD1)",
    ),
    "trees_county_package_note": Text(
        "county package (0.3-25 GB): GML files of 1:500 sheets, EPSG:2180 without "
        "vertical CRS; not every county has a package",
        "paczka powiatu (0,3-25 GB): pliki GML arkuszy 1:500, EPSG:2180 bez ukladu "
        "wysokosci; nie kazdy powiat ma paczke",
    ),
    "control_wfs_note": Text(
        "control points (and isogon zones) intersecting the area, service state",
        "punkty osnowy (i strefy izogon) przecinajace obszar, stan uslugi",
    ),
    "control_product_name": Text(
        "Basic control networks: horizontal, vertical, gravimetric, magnetic (with "
        "archives)",
        "Osnowy podstawowe: pozioma, wysokosciowa, grawimetryczna, magnetyczna (z "
        "archiwami)",
    ),
    "control_county_package_note": Text(
        "county package of the horizontal or vertical network: coordinate lists (XLS) "
        "and topographic descriptions (JPG), ZIP 1:1",
        "paczka powiatu sieci poziomej albo wysokosciowej: wykazy wspolrzednych (XLS) "
        "i opisy topograficzne (JPG), ZIP 1:1",
    ),
    "control_archive_notes": Text(
        "archival catalogues and point record cards of the 1:100,000 sheet (PDF and "
        "TIFF scans in historical CRSs), ZIP 1:1",
        "archiwalne katalogi i kartoteki punktow arkusza 1:100 000 (skany PDF i TIFF "
        "w ukladach historycznych), ZIP 1:1",
    ),
    "geoid2021_name": Text(
        "Quasi-geoid model PL-geoid2021 (PL-EVRF2007-NH)",
        "Model quasi-geoidy PL-geoid2021 (PL-EVRF2007-NH)",
    ),
    "geoid2021_notes": Text(
        "one national TXT file (latitude, longitude, zeta; 0.01 deg grid, 42 MB) "
        "saved 1:1, only with --whole-country",
        "jeden plik krajowy TXT (szerokosc, dlugosc, zeta; siatka 0,01 st., 42 MB) "
        "zapisywany 1:1, tylko z --whole-country",
    ),
    "cz_control_notes": Text(
        "points of the --network network intersecting the area (sum of its layers)",
        "punkty sieci --network przecinajace obszar (suma jej warstw)",
    ),
    "cz_qgzu2013_notes": Text(
        "one national file: ZIP of 17 TXT grids (58 MB) saved 1:1, only with "
        "--whole-country; release from the ATOM feed",
        "jeden plik krajowy: ZIP 17 siatek TXT (58 MB) zapisywany 1:1, tylko z "
        "--whole-country; wydanie z feedu ATOM",
    ),
    "orto_name": Text(
        "Orthophoto (sheets by campaign; WCS cutout Standard and High)",
        "Ortofotomapa (arkusze wg kampanii; wycinek WCS Standard i High)",
    ),
    "orto_standard_desc": Text(
        "latest available orthophotos",
        "najnowsze dostepne ortofotomapy",
    ),
    "orto_high_desc": Text(
        "orthophotos with a pixel of 10 cm or smaller",
        "ortofotomapy o pikselu 10 cm i mniejszym",
    ),
    "laz_name": Text(
        "LIDAR point clouds (ALS survey data)",
        "Chmury punktow LIDAR (dane pomiarowe ALS)",
    ),
    "laz_wms_notes": Text(
        "WMS of LAZ sheet indexes returns 401 - WFS is the only way",
        "WMS skorowidzy LAZ zwraca 401 - WFS jedyna droga",
    ),
    "bdot10k_name": Text(
        "BDOT10k - topographic objects database",
        "BDOT10k - baza danych obiektow topograficznych",
    ),
    "bdot10k_notes": Text(
        "archive of vintages 2014-2025 (state as of the start of the year), GML or "
        "SHP; county package saved 1:1",
        "archiwum rocznikow 2014-2025 (stan z poczatku roku), GML albo SHP; paczka "
        "powiatu zapisywana 1:1",
    ),
    "admin_name": Text(
        "PRG - boundaries of administrative and cadastral units",
        "PRG - granice jednostek administracyjnych i ewidencyjnych",
    ),
    "admin_notes": Text(
        "voivodeship package: GML of levels A01, A02, A03, A05, A06",
        "paczka wojewodztwa: GML poziomow A01, A02, A03, A05, A06",
    ),
    "national_shp_note": Text(
        "national SHP file (approx. 377 MB), only with --whole-country",
        "plik krajowy SHP (ok. 377 MB), tylko z --whole-country",
    ),
    "product_name_egib_map": Text(
        "EGiB - cadastral map (parcels and buildings)",
        "EGiB - mapa ewidencyjna (dzialki i budynki)",
    ),
    "county_export_note": Text(
        "county export refreshed daily: layers parcels, buildings and transactions "
        "(RCN)",
        "eksport powiatu odswiezany co dobe: warstwy dzialki, budynki i transakcje "
        "(RCN)",
    ),
    "county_wfs_note": Text(
        "aggregate service of county WFS: gaps in counties without integration, "
        "restricted attributes = brak_uprawnien",
        "usluga zbiorcza powiatowych WFS: luki w powiatach bez integracji, atrybuty "
        "zastrzezone = brak_uprawnien",
    ),
    "product_name_buildings": Text(
        "3D building models (CityGML LoD1, LoD2)",
        "Modele 3D budynkow (CityGML LoD1, LoD2)",
    ),
    "lod2_coverage_note": Text(
        "LoD2 does not cover the whole country (no county package = no data); "
        "national files (3.5-4.1 GB) out of scope",
        "LoD2 nie pokrywa calego kraju (brak paczki powiatu = brak danych); pliki "
        "krajowe (3,5-4,1 GB) poza zakresem",
    ),
    "clms_credentials_note": Text(
        "requires CLMS credentials (CLMS_CREDENTIALS)",
        "wymaga credentials CLMS (CLMS_CREDENTIALS)",
    ),
    "clms_no_credentials_note": Text(
        "without CLMS credentials: styled PNG from EEA WMS - preview, not data; 1990: "
        "DLR WMS in EPSG:4326",
        "bez credentials CLMS: stylizowany PNG z WMS EEA - podglad, nie dane; 1990: "
        "WMS DLR w EPSG:4326",
    ),
    "product_name_soilgrids": Text(
        "SoilGrids - global soil data",
        "SoilGrids - globalne dane glebowe",
    ),
    "soilgrids_bbox_note": Text(
        "WGS84 bbox only; transformation from EPSG:2180 is automatic",
        "tylko WGS84 bbox; transformacja z EPSG:2180 automatyczna",
    ),
    "country_name_pl": Text("Poland", "Polska"),
    "country_name_cz": Text("Czechia", "Czechy"),
    "unknown_source": Text(
        "Unknown source: '{key_value}'. Available: {sources}",
        "Nieznane zrodlo: '{key_value}'. Dostepne: {sources}",
    ),
    "source_no_channel": Text(
        "Source '{source_key}' has no {transport!r} channel{where} (channels: "
        "{channels})",
        "Zrodlo '{source_key}' nie ma kanalu {transport!r}{where} (kanaly: {channels})",
    ),
    "multiple_channels_ambiguous": Text(
        "Source '{source_key}' has several {transport!r} channels ({crs_list}) - "
        "selection requires the channel's horizontal CRS",
        "Zrodlo '{source_key}' ma kilka kanalow {transport!r} ({crs_list}) - wybor "
        "wymaga ukladu poziomego kanalu",
    ),
    "channels_differing_signals": Text(
        "{transport!r} channels of source '{source_key}' have different signals "
        "({signals}) - selection requires the channel's horizontal CRS",
        "Kanaly {transport!r} zrodla '{source_key}' maja rozne sygnaly ({signals}) - "
        "wybor wymaga ukladu poziomego kanalu",
    ),
    "sheet_asc_grid_name": Text(
        "{product_name} {shown} (ASC grid)",
        "{product_name} {shown} (siatka ASC)",
    ),
    "zabaged_name": Text(
        "ZABAGED - Zakladni baze geografickych dat CR (land cover and water)",
        "ZABAGED - Zakladni baze geografickych dat CR (pokrycie terenu i wody)",
    ),
    "ztm_name": Text(
        "ZTM - basic topographic maps of Czechia (zakladni topograficke mapy)",
        "ZTM - zakladni topograficke mapy Czech",
    ),
    "rcn_scope_county": Text("a county", "powiatu"),
    "rcn_scope_voivodeship": Text("a voivodeship", "wojewodztwa"),
    "cz_data_model_name": Text(
        "{dataset} - digital geographic model of Czechia ({scale})",
        "{dataset} - cyfrowy model geograficzny Czech ({scale})",
    ),
    "cz_control_name": Text(
        "Bodove pole - geodetic control networks of Czechia (horizontal, vertical, "
        "gravity, CZEPOS)",
        "Bodove pole - osnowy geodezyjne Czech (polohove, vyskove, tihove, CZEPOS)",
    ),
    "cz_qgzu2013_name": Text(
        "Kvazigeoid QGZU-2013 (TXT grids, Bpv)",
        "Kvazigeoid QGZU-2013 (siatki TXT, Bpv)",
    ),
    # ``sources.sidecar``.
    "sidecar_write_failed": Text(
        "Failed to write sidecar {sidecar_path}: {error}",
        "Nie udalo sie zapisac sidecara {sidecar_path}: {error}",
    ),
    "mandatory_sidecar_no_descriptor": Text(
        "Failed to write mandatory sidecar {sidecar_path}: no source descriptor "
        "({descriptor_key!r})",
        "Nie udalo sie zapisac obowiazkowego sidecara {sidecar_path}: brak "
        "deskryptora zrodla ({descriptor_key!r})",
    ),
    "mandatory_sidecar_failed": Text(
        "Failed to write mandatory sidecar {sidecar_path}: {error}",
        "Nie udalo sie zapisac obowiazkowego sidecara {sidecar_path}: {error}",
    ),
    "sidecar_for_file_failed": Text(
        "Failed to write sidecar for {data_path}: {error}",
        "Nie udalo sie zapisac sidecara dla {data_path}: {error}",
    ),
    # ``sources.variants``.
    "format_ascii_nmt": Text(
        "ASCII NMT - X Y Z points, ZIP",
        "ASCII NMT - punkty X Y Z, ZIP",
    ),
    "format_ascii_tbd": Text(
        "ASCII TBD - structure points and lines, ZIP",
        "ASCII TBD - punkty i linie struktury, ZIP",
    ),
    "format_dxf_description": Text("DXF contours", "warstwice DXF"),
    "format_dgn_description": Text("DGN contours", "warstwice DGN"),
    "model_desc_dmr5g": Text("terrain, DMR 5G", "teren, DMR 5G"),
    "model_desc_dmr4g": Text("terrain, 5 m grid", "teren, siatka 5 m"),
    "model_desc_dmp1g": Text("surface, DMP 1G", "powierzchnia, DMP 1G"),
    "model_desc_dmpok": Text(
        "surface, image correlation",
        "powierzchnia, korelacja obrazowa",
    ),
    "model_choice": Text("{model} ({description})", "{model} ({description})"),
    "model_choices": Text("{models:join}", "{models:join}"),
    "cz_vertical_text": Text(
        "Bpv (native to S-JTSK/SM5 and ImageServer services), EVRF2007 (native to "
        "ETRS89/TM33 files; pinned transformation from Bpv)",
        "Bpv (natywny dla S-JTSK/SM5 i uslug ImageServer), EVRF2007 (natywny dla "
        "plikow ETRS89/TM33; z Bpv przypieta transformacja)",
    ),
    "cz_laz_vertical_text": Text(
        "Bpv (SM5 sheets, S-JTSK) or EVRF2007 (TM33 tiles, ETRS89); point clouds "
        "without transformation",
        "Bpv (arkusze SM5, S-JTSK) albo EVRF2007 (kafle TM33, ETRS89); chmury punktow "
        "bez transformacji",
    ),
    "unknown_vertical_crs": Text("vertical CRS unknown", "uklad wysokosci nieznany"),
    "no_resolution_label": Text("no resolution", "bez rozdzielczosci"),
    "vertical_crs_labels": Text(
        "{vertical_crs}: {labels}",
        "{vertical_crs}: {labels}",
    ),
    "vertical_crs_labels_list": Text("{parts:join(; )}", "{parts:join(; )}"),
    "product_no_variants": Text(
        "--product {product} has no variants in {country}",
        "--product {product} nie ma wariantow w {country}",
    ),
    "format_unavailable": Text(
        "--format {format}: not available for {name} {country} - available: {tokens}",
        "--format {format}: niedostepny dla {name} {country} - dostepne: {tokens}",
    ),
    "vertical_undeclared_omit": Text(
        "{shown} ({country}): {unknown_vertical} (the source does not declare it) - "
        "omit --vertical-crs",
        "{shown} ({country}): {unknown_vertical} (zrodlo go nie deklaruje) - pomin "
        "--vertical-crs",
    ),
    "vertical_crs_only_named": Text(
        "{shown} ({country}) is only available in {named} - got --vertical-crs "
        "{vertical_crs}",
        "{shown} ({country}) jest dostepny tylko w {named} - podano --vertical-crs "
        "{vertical_crs}",
    ),
    "resolution_required": Text(
        "--resolution required for {shown} {country}: {labels_by_vertical_crs}",
        "--resolution wymagane dla {shown} {country}: {labels_by_vertical_crs}",
    ),
    "resolution_not_applicable": Text(
        "--resolution does not apply to {shown} (the sheet index gives no resolution) "
        "- omit --resolution",
        "--resolution nie dotyczy {shown} (skorowidz nie podaje rozdzielczosci) - "
        "pomin --resolution",
    ),
    "res_vertical_undeclared": Text(
        "{shown} {resolution} ({country}): {unknown_vertical} (the source does not "
        "declare it) - omit --vertical-crs",
        "{shown} {resolution} ({country}): {unknown_vertical} (zrodlo go nie "
        "deklaruje) - pomin --vertical-crs",
    ),
    "res_vertical_crs_mismatch": Text(
        "{shown} {resolution} ({country}) is only available in {named} - got "
        "--vertical-crs {vertical_crs}; available in {vertical_crs}: {labels}",
        "{shown} {resolution} ({country}) jest dostepny tylko w {named} - podano "
        "--vertical-crs {vertical_crs}; dostepne w {vertical_crs}: {labels}",
    ),
    "resolution_unavailable": Text(
        "{country} has no resolution {resolution} for {shown} - available: "
        "{labels_by_vertical_crs}",
        "{country} nie ma rozdzielczosci {resolution} dla {shown} - dostepne: "
        "{labels_by_vertical_crs}",
    ),
    "vertical_crs_required": Text(
        "--vertical-crs required for {name} {country}: {named_systems}",
        "--vertical-crs wymagane dla {name} {country}: {named_systems}",
    ),
    "cz_system_sm5": Text("SM5 sheets (S-JTSK)", "arkusze SM5 (S-JTSK)"),
    "cz_system_tm33": Text("TM33 tiles (ETRS89)", "kafle TM33 (ETRS89)"),
    "sheet_not_cz_system": Text(
        "Sheet code '{sheet}' does not belong to any CZ system (SM5 sheet, e.g. "
        "CTES96, or TM33 tile, e.g. 302_5550)",
        "Godlo '{sheet}' nie nalezy do zadnego systemu CZ (arkusz SM5, np. CTES96, "
        "albo kafel TM33, np. 302_5550)",
    ),
    "no_cz_raster_variants": Text(
        "--product {product} has no raster variants in CZ",
        "--product {product} nie ma wariantow rastrowych w CZ",
    ),
    "cz_resolution_required": Text(
        "--resolution required for {name} CZ: {cz_labels}",
        "--resolution wymagane dla {name} CZ: {cz_labels}",
    ),
    "cz_resolution_unavailable": Text(
        "CZ has no {resolution} resolution for {name} - available: {cz_labels}",
        "CZ nie ma rozdzielczosci {resolution} dla {name} - dostepne: {cz_labels}",
    ),
    "cz_sm5_resolution_limit": Text(
        "SM5 sheets of {name} CZ exist only in {cz_labels} - omit --resolution or "
        "give {sorted_labels}; {resolution}: a TM33 tile (e.g. 302_5550) or --bbox "
        "with --cutout",
        "Arkusze SM5 {name} CZ sa tylko w {cz_labels} - pomin --resolution albo podaj "
        "{sorted_labels}; {resolution}: kafel TM33 (np. 302_5550) albo --bbox z "
        "--cutout",
    ),
    "cz_vertical_crs_unavailable": Text(
        "{vertical_crs} is not available for CZ - available: {cz_vertical_text}",
        "{vertical_crs} nie jest dostepny dla CZ - dostepne: {cz_vertical_text}",
    ),
    "cz_laz_model_required": Text(
        "--model required for --product laz in CZ: {cz_model_text}",
        "--model wymagane dla --product laz w CZ: {cz_model_text}",
    ),
    "cz_laz_model_unknown": Text(
        "--model {model!r}: unknown value - available: {cz_model_text}",
        "--model {model!r}: nieznana wartosc - dostepne: {cz_model_text}",
    ),
    "cz_laz_vertical_unavailable": Text(
        "{vertical_crs} is not available for LAZ CZ - available: "
        "{cz_laz_vertical_text}",
        "{vertical_crs} nie jest dostepny dla LAZ CZ - dostepne: "
        "{cz_laz_vertical_text}",
    ),
    "cz_laz_native_vertical_only": Text(
        "LAZ CZ - {shown} exist only in {native}, but --vertical-crs {vertical_crs} "
        "was given (point clouds without transformation); {vertical_crs}: "
        "{alternative}, e.g. {example}, or an area (--bbox/--geometry)",
        "LAZ CZ - {shown} sa tylko w {native}, podano --vertical-crs {vertical_crs} "
        "(chmury punktow bez transformacji); {vertical_crs}: {alternative}, np. "
        "{example}, albo obszar (--bbox/--geometry)",
    ),
}
