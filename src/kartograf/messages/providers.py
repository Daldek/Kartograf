"""Messages of the providers: GUGiK (PL), CUZK (CZ), CORINE and SoilGrids."""

from kartograf.messages import Text

MESSAGES = {
    # ``providers.base``.
    "unknown_format": Text("Unknown format: {format}", "Nieznany format: {format}"),
    # ``providers.corine``.
    "capabilities_not_xml": Text(
        "{what}: GetCapabilities is not XML: {error}",
        "{what}: GetCapabilities nie jest XML: {error}",
    ),
    "wms_raster_layer_missing": Text(
        "{what}: the EEA WMS service has no raster layer 'Corine Land Cover {year} "
        "raster' (layers: {named}); the preview for this year is not available - "
        "change --year or set CLMS_CREDENTIALS",
        "{what}: usluga WMS EEA nie ma warstwy rastrowej 'Corine Land Cover {year} "
        "raster' (warstwy: {named}); podglad tego roku jest niedostepny - zmien "
        "--year albo ustaw CLMS_CREDENTIALS",
    ),
    "jwt_no_private_key": Text(
        "Failed to create the JWT assertion: private_key is missing",
        "Nie udalo sie utworzyc asercji JWT: brak private_key",
    ),
    "jwt_assertion_failed": Text(
        "Failed to create the JWT assertion: {error}",
        "Nie udalo sie utworzyc asercji JWT: {error}",
    ),
    "no_access_token": Text(
        "No access_token in the response: {result}",
        "Brak access_token w odpowiedzi: {result}",
    ),
    "token_exchange_failed": Text(
        "Token exchange failed: {error}",
        "Wymiana tokenu nie powiodla sie: {error}",
    ),
    "year_not_available": Text(
        "--year {year}: not available for --product corine; available: {ys}",
        "--year {year}: niedostepne dla --product corine; dostepne: {ys}",
    ),
    "no_clms_dataset": Text(
        "CORINE {year}: no CLMS dataset (years: {clms_years})",
        "CORINE {year}: brak zbioru CLMS (lata: {clms_years})",
    ),
    "clms_catalogue_what": Text(
        "CORINE {year} CLMS catalogue",
        "CORINE {year} katalog CLMS",
    ),
    "response_not_json": Text(
        "{what}: response is not JSON: {error}",
        "{what}: odpowiedz nie jest JSON: {error}",
    ),
    "unexpected_record_count": Text(
        "{what}: expected 1 record of dataset {uid}, got {count}",
        "{what}: oczekiwano 1 rekordu zbioru {uid}, jest {count}",
    ),
    "record_no_release_version": Text(
        "{what}: record without characteristics_release_major_version",
        "{what}: rekord bez characteristics_release_major_version",
    ),
    "bbox_wrong_crs": Text(
        "bbox must be in EPSG:2180, got {crs}. Convert with: "
        "SheetParser.get_bbox(crs='EPSG:2180').",
        "bbox musi byc w EPSG:2180, podano {crs}. Przelicz: "
        "SheetParser.get_bbox(crs='EPSG:2180').",
    ),
    "wms_image_transparent": Text(
        "CORINE {year} preview: the WMS image from {service} is fully transparent - "
        "the service has no CLC {year} data for this area (outside CORINE coverage or "
        "a country without this vintage); the version was not created, change --bbox "
        "or --year",
        "podglad CORINE {year}: obraz WMS {service} jest w calosci przezroczysty - "
        "usluga nie ma danych CLC {year} dla tego obszaru (poza zasiegiem CORINE albo "
        "kraj bez tego rocznika); wersja nie powstala, zmien --bbox albo --year",
    ),
    "proxy_task_failed": Text(
        "Task via proxy failed{reason}",
        "Zadanie przez proxy nie powiodlo sie{reason}",
    ),
    "clms_no_task_id": Text(
        "CLMS API did not return a TaskID: {result}",
        "API CLMS nie zwrocilo TaskID: {result}",
    ),
    "proxy_download_failed": Text(
        "Failed to download the file via proxy",
        "Nie udalo sie pobrac pliku przez proxy",
    ),
    "clms_task_no_url": Text(
        "CLMS task finished without DownloadURL",
        "Zadanie CLMS zakonczone bez DownloadURL",
    ),
    "clms_task_failed": Text(
        "CLMS task {status}: {detail}", "Zadanie CLMS {status}: {detail}"
    ),
    "clms_unknown_error": Text("unknown error", "nieznany blad"),
    "clms_direct_needs_creds": Text(
        "CLMS direct mode requires clms_credentials",
        "Tryb bezposredni CLMS wymaga clms_credentials",
    ),
    "clms_api_request_failed": Text(
        "CLMS API request failed: {error}",
        "Zapytanie API CLMS nie powiodlo sie: {error}",
    ),
    # ``providers.soilgrids``.
    "property_bdod": Text("bulk density", "gestosc objetosciowa"),
    "property_cec": Text("cation exchange capacity", "pojemnosc sorpcyjna"),
    "property_clay": Text("clay", "il"),
    "property_cfvo": Text("coarse fragments fraction", "frakcja szkieletowa"),
    "property_nitrogen": Text("total nitrogen", "azot calkowity"),
    "property_ocd": Text("organic carbon density", "gestosc wegla organicznego"),
    "property_ocs": Text(
        "organic carbon stock, depth 0-30cm only",
        "zasob wegla organicznego, tylko glebokosc 0-30cm",
    ),
    "property_phh2o": Text("pH in water (H2O)", "pH w wodzie (H2O)"),
    "property_sand": Text("sand", "piasek"),
    "property_silt": Text("silt", "pyl"),
    "property_soc": Text("organic carbon", "wegiel organiczny"),
    "property_description": Text("{name} ({units})", "{name} ({units})"),
    "unit_text": Text(
        "in the file {mapped}; {conventional} = value / {divisor}",
        "w pliku {mapped}; {conventional} = wartosc / {divisor}",
    ),
    "stat_mean": Text("mean", "srednia"),
    "stat_q0_05": Text("5th percentile", "5. percentyl"),
    "stat_q0_5": Text("median", "mediana"),
    "stat_q0_95": Text("95th percentile", "95. percentyl"),
    "stat_uncertainty": Text(
        "prediction uncertainty ({unit_text}; unitless)",
        "niepewnosc predykcji ({unit_text}; bez jednostki)",
    ),
    "depth_description": Text(
        "depth interval below the surface",
        "przedzial glebokosci ponizej powierzchni",
    ),
    "label_property": Text("property", "wlasciwosc"),
    "label_depth": Text("depth", "glebokosc"),
    "for_property": Text(" for {property}", " dla {property}"),
    "label_stat": Text("statistic", "statystyka"),
    "invalid_layer_option": Text(
        "Invalid {label}: {value}. Available{where}: {allowed}",
        "Nieprawidlowa {label}: {value}. Dostepne{where}: {allowed}",
    ),
    "invalid_property": Text(
        "Invalid property: {property}. Available: {properties}",
        "Nieprawidlowa wlasciwosc: {property}. Dostepne: {properties}",
    ),
    "edition_missing_in_title": Text(
        "SoilGrids GetCapabilities {property}: no edition in title {title!r} "
        "(expected 'SoilGrids250m <edition> - ...')",
        "SoilGrids GetCapabilities {property}: brak wydania w tytule {title!r} "
        "(oczekiwano 'SoilGrids250m <wydanie> - ...')",
    ),
    # ``providers.cuzk.client``.
    "query_description": Text("Query {url}", "Zapytanie {url}"),
    "query_failed": Text(
        "Query {url} failed: {error}",
        "Zapytanie {url} nieudane: {error}",
    ),
    "arcgis_error": Text(
        "ArcGIS error for {url}: {data_error}",
        "Blad ArcGIS dla {url}: {data_error}",
    ),
    "export_tiling_crs_mismatch": Text(
        "exportImage tiling requires bbox.crs == image_sr (bbox: {crs}, image_sr: "
        "{image_sr}) - normalise the bbox to the output CRS before export",
        "Kafelkowanie exportImage wymaga bbox.crs == image_sr (bbox: {crs}, image_sr: "
        "{image_sr}) - znormalizuj bbox do ukladu wyjsciowego przed eksportem",
    ),
    "export_not_tiff": Text(
        "exportImage did not return a TIFF (start of response: {snippet!r}) [{url}]",
        "exportImage nie zwrocil TIFF (poczatek odpowiedzi: {snippet!r}) [{url}]",
    ),
    "crs_overwrite_failed": Text(
        "exportImage: failed to overwrite CRS with {image_sr} in {output_path}: "
        "{error}",
        "exportImage: nie udalo sie nadpisac CRS na {image_sr} w {output_path}: "
        "{error}",
    ),
    "zip_unexpected_file_count": Text(
        "ZIP {url}: expected exactly 1 file '{unzip_single}', found {names_count}",
        "ZIP {url}: oczekiwano dokladnie 1 pliku '{unzip_single}', znaleziono "
        "{names_count}",
    ),
    "zip_corrupt": Text(
        "Corrupt ZIP from {url}: {error}",
        "Uszkodzony ZIP z {url}: {error}",
    ),
    "zip_extract_failed": Text(
        "Extracting ZIP {url} failed: {error}",
        "Rozpakowanie ZIP {url} nieudane: {error}",
    ),
    # ``providers.cuzk.laz``.
    "no_file_endpoint": Text(
        "Descriptor '{descriptor_key}' has no file endpoint {horizontal_crs}",
        "Deskryptor '{descriptor_key}' nie ma endpointu plikow {horizontal_crs}",
    ),
    "sheet_outside_system": Text(
        "Sheet code '{sheet}' is outside the {system} system",
        "Godlo '{sheet}' spoza systemu {system}",
    ),
    "openzu_file_unavailable": Text(
        "{error} - verify the sheet code in the KladyMapovychListu index (the sheet "
        "may be known to the index, but the openzu file is not available)",
        "{error} - zweryfikuj godlo w indeksie KladyMapovychListu (arkusz moze byc "
        "znany indeksowi, ale plik openzu niedostepny)",
    ),
    # ``providers.cuzk.raster``.
    "no_kron86_transform": Text(
        "No transformation Bpv (EPSG:8357) -> KRON86 (EPSG:9650) - GUGiK grids are "
        "not public",
        "Brak transformacji Bpv (EPSG:8357) -> KRON86 (EPSG:9650) - siatki GUGiK nie "
        "sa publiczne",
    ),
    "bbox_gtiff_only": Text(
        "CuzkRasterProvider.download_bbox supports only GTiff (requested: {format})",
        "CuzkRasterProvider.download_bbox obsluguje tylko GTiff (zadano: {format})",
    ),
    "no_cuzk_file": Text(
        "{sheet} ({model}, {vertical_crs}) has no CUZK file - ImageServer tile "
        "without a cheap source signal",
        "{sheet} ({model}, {vertical_crs}) nie ma pliku CUZK - kafel z ImageServer "
        "bez taniego sygnalu zrodla",
    ),
    "raster_no_crs": Text(
        "Raster {label} has no CRS - cannot determine (lon, lat) required by the "
        "vertical operation",
        "Raster {label} nie ma CRS - nie da sie wyznaczyc (lon, lat) wymaganych przez "
        "operacje pionowa",
    ),
    "raster_no_geotransform": Text(
        "Raster {label} has no usable geotransform (identity/non-rectangular) - "
        "cannot determine (lon, lat) for the vertical operation",
        "Raster {label} nie ma uzytecznej geotransformacji "
        "(jednostkowa/nieprostokatna) - nie da sie wyznaczyc (lon, lat) dla operacji "
        "pionowej",
    ),
    "crs_write_failed": Text(
        "failed to write CRS {crs} to {path}: {error}",
        "nie udalo sie wpisac CRS {crs} w {path}: {error}",
    ),
    # ``providers.cuzk.ruian``.
    "ruian_feature_bad_kod": Text(
        "RUIAN {layer_url}: feature without a valid 'kod' field: {attrs}",
        "RUIAN {layer_url}: obiekt bez poprawnego pola 'kod': {attrs}",
    ),
    "ruian_code_not_6_digits": Text(
        "RUIAN {layer_url}: katastralni uzemi code does not match the 6-digit "
        "pattern: {code!r}",
        "RUIAN {layer_url}: kod katastralniho uzemi spoza wzorca 6 cyfr: {code!r}",
    ),
    "ku_missing_name_field": Text(
        "RUIAN {layer_url}: katastralni uzemi {code} without field 'nazev'",
        "RUIAN {layer_url}: katastralni uzemi {code} bez pola 'nazev'",
    ),
    # ``providers.cuzk.sheets``.
    "sm5_hint": Text(
        "expected 2 or 4 capital letters + 2 digits, e.g. CTES96, AS91",
        "oczekiwano 2 albo 4 wielkich liter + 2 cyfr, np. CTES96, AS91",
    ),
    "invalid_sm5_code": Text(
        "Invalid SM5 sheet code: '{mapnom}' ({sm5_hint})",
        "Niepoprawne godlo SM5: '{mapnom}' ({sm5_hint})",
    ),
    "sm5_sheet_not_found": Text(
        "SM5 sheet '{mapnom}' does not exist in the KladyMapovychListu index (layer "
        "{sm5_layer})",
        "Arkusz SM5 '{mapnom}' nie istnieje w indeksie KladyMapovychListu (warstwa "
        "{sm5_layer})",
    ),
    "invalid_cuzk_sheet": Text(
        "Invalid CUZK sheet designation: '{mapnom}' (letters, digits and '-' allowed, "
        "e.g. 0510-D-11)",
        "Niepoprawne oznaczenie arkusza CUZK: '{mapnom}' (dozwolone litery, cyfry i "
        "'-', np. 0510-D-11)",
    ),
    "sheet_not_found": Text(
        "Sheet '{code}' does not exist in the KladyMapovychListu index (layer {layer})",
        "Arkusz '{code}' nie istnieje w indeksie KladyMapovychListu (warstwa {layer})",
    ),
    "bbox_crs_mismatch": Text(
        "{method} requires a bbox in {expected_crs} (the service returns geometries "
        "in this CRS, and the intersection filter requires a common CRS), got: {crs}",
        "{method} wymaga bbox w {expected_crs} (usluga zwraca geometrie w tym "
        "ukladzie, a filtr przeciec wymaga wspolnego CRS), otrzymano: {crs}",
    ),
    "feature_no_rings": Text(
        "Feature without 'rings' geometry in the KladyMapovychListu response: "
        "{attributes}",
        "Feature bez geometrii 'rings' w odpowiedzi KladyMapovychListu: {attributes}",
    ),
    "feature_no_mapnom": Text(
        "Feature without MAPNOM attribute in the KladyMapovychListu response: "
        "{feature}",
        "Feature bez atrybutu MAPNOM w odpowiedzi KladyMapovychListu: {feature}",
    ),
    "skip_bad_cache_entry": Text(
        "Skipping unusable sheet_cache entry ({error}): {payload}",
        "Pomijam niezdatny wpis sheet_cache ({error}): {payload}",
    ),
    # ``providers.pl.bdot10k``.
    "class_adja": Text(
        "Administrative division units",
        "Jednostki podzialu administracyjnego",
    ),
    "class_adms": Text("Localities", "Miejscowosci"),
    "class_bubd": Text("Buildings", "Budynki"),
    "class_buhd": Text("Hydrotechnical structures", "Budowle hydrotechniczne"),
    "class_buib": Text("Other structures", "Inne budowle"),
    "class_buin": Text("Engineering structures", "Budowle inzynierskie"),
    "class_buit": Text("Other technical installations", "Inne urzadzenia techniczne"),
    "class_busp": Text("Sports structures", "Budowle sportowe"),
    "class_butr": Text("Transport installations", "Urzadzenia transportowe"),
    "class_buuo": Text(
        "Road, railway and water reinforcements",
        "Umocnienia drogowe, kolejowe i wodne",
    ),
    "class_buwt": Text("Tall technical structures", "Wysokie budowle techniczne"),
    "class_buzm": Text("Earthworks", "Budowle ziemne"),
    "class_buzt": Text("Technical reservoirs", "Zbiorniki techniczne"),
    "class_kuho": Text("Hotel service complexes", "Kompleksy uslug hotelarskich"),
    "class_kuhu": Text("Bazaars and marketplaces", "Bazary i targowiska"),
    "class_kuko": Text("Transport complexes", "Kompleksy komunikacyjne"),
    "class_kumn": Text("Residential estates", "Osiedla mieszkaniowe"),
    "class_kuos": Text("Educational complexes", "Kompleksy oswiatowe"),
    "class_kuoz": Text(
        "Healthcare and social care complexes",
        "Kompleksy ochrony zdrowia i opieki spolecznej",
    ),
    "class_kupg": Text(
        "Industrial and commercial complexes",
        "Kompleksy przemyslowo-gospodarcze",
    ),
    "class_kupw": Text("Military training grounds", "Poligony wojskowe"),
    "class_kusc": Text(
        "Religious complexes and cemeteries",
        "Kompleksy sakralne i cmentarze",
    ),
    "class_kusk": Text(
        "Sports and recreation complexes",
        "Kompleksy sportowe i rekreacyjne",
    ),
    "class_kuza": Text(
        "Historic and heritage complexes",
        "Kompleksy zabytkowo-historyczne",
    ),
    "class_oikm": Text("Transport-related objects", "Obiekty zwiazane z komunikacja"),
    "class_oimk": Text("Wetlands", "Mokradla"),
    "class_oior": Text("Landmark objects", "Obiekty o znaczeniu orientacyjnym"),
    "class_oipr": Text("Natural objects", "Obiekty przyrodnicze"),
    "class_oisz": Text("Reed beds", "Szuwary"),
    "class_ptgn": Text("Wasteland", "Grunty nieuzytkowe"),
    "class_ptkm": Text("Transport areas", "Tereny komunikacyjne"),
    "class_ptlz": Text("Forest areas", "Tereny lesne"),
    "class_ptnz": Text("Undeveloped areas", "Tereny niezabudowane"),
    "class_ptrk": Text("Shrub vegetation", "Roslinnosc krzewiasta"),
    "class_ptso": Text("Storage sites", "Skladowiska"),
    "class_pttr": Text("Agricultural land", "Tereny rolne"),
    "class_ptut": Text("Permanent crops", "Uprawy trwale"),
    "class_ptwp": Text("Surface waters", "Wody powierzchniowe"),
    "class_ptwz": Text("Excavations and spoil heaps", "Wyrobiska i zwalowiska"),
    "class_ptzb": Text("Built-up areas", "Tereny zabudowane"),
    "class_rtlw": Text("Elevation lines", "Linie wysokosciowe"),
    "class_rtpw": Text("Elevation points", "Punkty wysokosciowe"),
    "class_skdr": Text("Roads", "Drogi"),
    "class_skjz": Text("Carriageways", "Jezdnie"),
    "class_skpp": Text("Crossings", "Przeprawy"),
    "class_skrp": Text(
        "Pedestrian and cycle routes",
        "Ciagi ruchu pieszego i rowerowego",
    ),
    "class_skrw": Text("Roundabouts and road junctions", "Ronda i wezly drogowe"),
    "class_sktr": Text("Tracks and track systems", "Tory i zespoly torow"),
    "class_suln": Text("Power lines", "Linie elektroenergetyczne"),
    "class_supr": Text("Pipelines", "Przewody rurowe"),
    "class_swkn": Text("Canals", "Kanaly"),
    "class_swrm": Text("Drainage ditches", "Rowy melioracyjne"),
    "class_swrs": Text("Rivers and streams", "Rzeki i strumienie"),
    "class_tcon": Text("Natura 2000 areas", "Obszary Natura 2000"),
    "class_tcpk": Text("Landscape parks", "Parki krajobrazowe"),
    "class_tcpn": Text("National parks", "Parki narodowe"),
    "class_tcrz": Text("Nature reserves", "Rezerwaty"),
    "layers_required": Text(
        "--layers: provide at least one BDOT10k layer code (4 letters, e.g. PTWP, "
        "SWRS)",
        "--layers: podaj co najmniej jeden kod warstwy BDOT10k (4 litery, np. PTWP, "
        "SWRS)",
    ),
    "layers_empty_code": Text(
        "--layers: empty layer code (extra comma?); provide BDOT10k codes separated "
        "by commas (4 letters, e.g. PTWP,SWRS)",
        "--layers: pusty kod warstwy (nadmiarowy przecinek?); podaj kody BDOT10k po "
        "przecinku (4 litery, np. PTWP,SWRS)",
    ),
    "layers_invalid_codes": Text(
        "Invalid BDOT10k layer codes: {bad} (4 letters, e.g. PTWP, SWRS)",
        "Nieprawidlowe kody warstw BDOT10k: {bad} (4 litery, np. PTWP, SWRS)",
    ),
    "layers_unknown_classes": Text(
        "--layers {unknown}: no such classes in BDOT10k; available: {bdot10k_classes}",
        "--layers {unknown}: brak takich klas w BDOT10k; dostepne: {bdot10k_classes}",
    ),
    "invalid_teryt_code": Text(
        "Invalid TERYT code: {code}",
        "Nieprawidlowy kod TERYT: {code}",
    ),
    "unsupported_format": Text(
        "Unsupported format: {format}. Use 'GPKG' or 'SHP'",
        "Nieobslugiwany format: {format}. Uzyj 'GPKG' albo 'SHP'",
    ),
    "layer_filter_gpkg_only": Text(
        "The BDOT10k layer filter works only with GPKG",
        "Filtr warstw BDOT10k dziala tylko z GPKG",
    ),
    "keep_raw_gpkg_only": Text(
        "keep_raw applies only to GPKG (SHP is already the original ZIP)",
        "keep_raw dotyczy tylko GPKG (SHP to juz oryginalny ZIP)",
    ),
    "raw_path_needs_keep_raw": Text(
        "raw_path requires keep_raw=True",
        "raw_path wymaga keep_raw=True",
    ),
    "unknown_voivodeship_code": Text(
        "Unknown voivodeship code: {woj_code}. Available codes: {keys}",
        "Nieznany kod wojewodztwa: {woj_code}. Dostepne kody: {keys}",
    ),
    "area_no_county": Text(
        "{what}: the area does not intersect any county (PRG)",
        "{what}: obszar nie przecina zadnego powiatu (PRG)",
    ),
    "area_multiple_counties": Text(
        "{what}: the area intersects {teryts_count} counties ({teryts}); use "
        "download_landcover(product='bdot10k', bbox=..., root=...) or download "
        "each county via --teryt",
        "{what}: obszar przecina {teryts_count} powiaty ({teryts}); uzyj "
        "download_landcover(product='bdot10k', bbox=..., root=...) albo pobierz "
        "kazdy powiat przez --teryt",
    ),
    "no_gpkg_in_zip": Text(
        "No GPKG files in ZIP. Contents: {namelist}",
        "Brak plikow GPKG w ZIP. Zawartosc: {namelist}",
    ),
    "package_missing_class_files": Text(
        "the BDOT10k package has no files for classes {absent} (no objects of these "
        "classes in the county)",
        "paczka BDOT10k nie ma plikow klas {absent} (brak obiektow tych klas w "
        "powiecie)",
    ),
    "raw_zip_save_failed": Text(
        "Failed to save the original BDOT10k ZIP {name}: {error}; previous "
        "{output_gpkg_name} (if any) unchanged",
        "Nie udalo sie zapisac oryginalnego ZIP BDOT10k {name}: {error}; poprzedni "
        "{output_gpkg_name} (jesli byl) bez zmian",
    ),
    "invalid_zip_file": Text(
        "Invalid ZIP file: {error}",
        "Nieprawidlowy plik ZIP: {error}",
    ),
    "package_extract_failed": Text(
        "Failed to extract or save the BDOT10k package ({name}): {error}",
        "Nie udalo sie rozpakowac ani zapisac paczki BDOT10k ({name}): {error}",
    ),
    "no_files_to_merge": Text("No files to merge", "Brak plikow do scalenia"),
    "table_in_multiple_files": Text(
        "BDOT10k package: table {table_name} occurs in more than one file ({name}) - "
        "merging would lose data",
        "Paczka BDOT10k: tabela {table_name} wystepuje w wiecej niz jednym pliku "
        "({name}) - scalenie zgubiloby dane",
    ),
    # ``providers.pl.gugik``.
    "index_other_variant_hint": Text(
        "The GUGiK sheet index has this sheet in {describe} {vertical_crs} - use "
        "{flags}",
        "Skorowidz GUGiK ma ten arkusz w {describe} {vertical_crs} - uzyj {flags}",
    ),
    "unsupported_record_format": Text(
        "{file_format} ({extension} file)",
        "{file_format} (plik {extension})",
    ),
    "no_format": Text("no format", "bez formatu"),
    "only_unsupported_records_hint": Text(
        "The GUGiK sheet index has only records for this sheet that Kartograf does "
        "not download: {unsupported} (record format inconsistent with the file or a "
        "variant outside the registry)",
        "Skorowidz GUGiK ma dla tego arkusza tylko rekordy, ktorych Kartograf nie "
        "pobiera: {unsupported} (format rekordu niezgodny z plikiem albo wariant "
        "spoza rejestru)",
    ),
    "no_data_for_sheet": Text(
        "No {describe} data for {sheet} (PL-{sheet_system} system, {vertical_crs})",
        "Brak danych {describe} dla {sheet} (uklad PL-{sheet_system}, {vertical_crs})",
    ),
    "vertical_crs_check_skipped": Text(
        "{sheet}: vertical CRS {vertical_crs} was not checked (hint skipped, service "
        "skipped until the end of the task): {error}",
        "{sheet}: nie sprawdzono ukladu {vertical_crs} (podpowiedz pominieta, usluga "
        "pomijana do konca zadania): {error}",
    ),
    "wcs_only_1m_grid": Text(
        "WCS download (download_bbox) is available only for the {product} 1m grid - "
        "download {describe} via download() (sheets)",
        "Pobieranie WCS (download_bbox) jest dostepne tylko dla siatki {product} 1m - "
        "{describe} pobierz przez download() (arkusze)",
    ),
    "wcs_format_unsupported": Text(
        "Unsupported WCS format: '{format}'. Supported formats: {keys}",
        "Nieobslugiwany format WCS: '{format}'. Obslugiwane formaty: {keys}",
    ),
    "wcs_withdrawn": Text(
        "WCS {product} 1m for {vertical_crs} is not available (service withdrawn by "
        "GUGiK). Download sheets by sheet code.",
        "WCS {product} 1m dla {vertical_crs} nie jest dostepny (usluga wycofana przez "
        "GUGiK). Pobierz arkusze przez godlo.",
    ),
    # ``providers.pl.gugik_laz``.
    "tile_unknown_xy_crs": Text(
        "Tile {sheet}: unrecognised uklad_xy {crs!r} (expected 'PL-1992' or "
        "'PL-2000:S5'..'S8')",
        "Kafel {sheet}: nierozpoznany uklad_xy {crs!r} (oczekiwano 'PL-1992' albo "
        "'PL-2000:S5'..'S8')",
    ),
    "area_crs_not_2180": Text(
        "area must be in EPSG:2180, got {crs}",
        "obszar musi byc w EPSG:2180, podano {crs}",
    ),
    "tile_unknown_xy_crs_skipped": Text(
        "Tile {sheet}: unrecognised uklad_xy {crs!r} - skipped",
        "Kafel {sheet}: nierozpoznany uklad_xy {crs!r} - pominiety",
    ),
    "unsupported_vertical_crs_init": Text(
        "Unsupported vertical CRS: '{vertical_crs}'. Supported: {indexes}",
        "Nieobslugiwany uklad wysokosci: '{vertical_crs}'. Obslugiwane: {indexes}",
    ),
    "provider_name": Text("GUGiK LAZ (point cloud)", "GUGiK LAZ (chmura punktow)"),
    "year_excludes_range": Text(
        "year is mutually exclusive with min_year/max_year",
        "year wyklucza sie z min_year/max_year",
    ),
    "bbox_crs_not_2180": Text(
        "bbox must be in EPSG:2180, got {crs}. Convert it first (e.g. "
        "SheetParser.get_bbox(crs='EPSG:2180')).",
        "bbox musi byc w EPSG:2180, podano {crs}. Najpierw przelicz (np. "
        "SheetParser.get_bbox(crs='EPSG:2180')).",
    ),
    "unsupported_vertical_crs": Text(
        "Unsupported vertical CRS: '{vcrs}'. Supported: {indexes}",
        "Nieobslugiwany uklad wysokosci: '{vcrs}'. Obslugiwane: {indexes}",
    ),
    "vintage_not_in_service": Text(
        "vintage {lo} does not exist in service {vcrs} (available: {years})",
        "rocznik {lo} nie istnieje w usludze {vcrs} (dostepne: {years})",
    ),
    "range_no_vintage": Text(
        "range {label} has no vintage in service {vcrs} (available: {years})",
        "przedzial {label} nie ma rocznika w usludze {vcrs} (dostepne: {years})",
    ),
    "unit_area_tiles": Text("area tiles", "kafli obszaru"),
    "subject_laz_tiles": Text("LAZ tiles", "kafli LAZ"),
    "wfs_axis_order_mismatch": Text(
        "WFS {layer}: server returned {returned} {returned:plural(tile|tiles)}, none "
        "intersects the requested bbox - axis order mismatch (report a bug)",
        "WFS {layer}: serwer zwrocil {returned} {returned:plural(kafel|kafle|kafli)}, "
        "zaden nie przecina zadanego bboxa - niezgodnosc kolejnosci osi (zglos blad)",
    ),
    # ``providers.pl.gugik_orto``.
    "no_wms_sheet_index": Text(
        "Source {key_value} has no WMS sheet index",
        "Zrodlo {key_value} nie ma skorowidza arkuszy WMS",
    ),
    "coverage_single_wcs_service": Text(
        "--coverage {coverage!r}: --product {product} has a single cutout WCS service "
        "({notes}) - omit --coverage",
        "--coverage {coverage!r}: --product {product} ma jedna usluge WCS wycinka "
        "({notes}) - bez --coverage",
    ),
    "coverage_required_cutout": Text(
        "--coverage required with --cutout --product {product}: {coverage_choices}",
        "--coverage wymagane z --cutout --product {product}: {coverage_choices}",
    ),
    "coverage_unknown_value": Text(
        "--coverage {coverage!r}: unknown value - available: {coverage_choices}",
        "--coverage {coverage!r}: nieznana wartosc - dostepne: {coverage_choices}",
    ),
    "resolution_required_cutout": Text(
        "--resolution required with --cutout --product {product} (cutout pixel): "
        "{labels}",
        "--resolution wymagane z --cutout --product {product} (piksel wycinka): "
        "{labels}",
    ),
    "resolution_unavailable_cutout": Text(
        "--resolution {resolution!r}: not available for the {variant} orthophoto "
        "cutout - available: {labels}",
        "--resolution {resolution!r}: niedostepne dla wycinka ortofotomapy {variant} "
        "- dostepne: {labels}",
    ),
    "product_no_wcs_cutout": Text(
        "--product {product} has no WCS cutout - omit --coverage and --resolution",
        "--product {product} nie ma wycinka WCS - pomin --coverage i --resolution",
    ),
    "resolution_needs_coverage": Text(
        "--resolution --product {product} applies only to the WCS cutout - give "
        "--coverage: {coverage_choices}",
        "--resolution --product {product} dotyczy tylko wycinka WCS - podaj "
        "--coverage: {coverage_choices}",
    ),
    "direction_not_oblique": Text(
        "--direction applies only to oblique orthophoto - --product {product} has no "
        "directions",
        "--direction dotyczy tylko orto ukosnej - --product {product} nie ma kierunkow",
    ),
    "direction_unknown": Text(
        "--product {product}: direction {direction!r} - available: {codes}",
        "--product {product}: kierunek {direction!r} - dostepne: {codes}",
    ),
    "product_with_direction": Text(
        "--product {product} (direction {direction})",
        "--product {product} (kierunek {direction})",
    ),
    "orto_no_data_for_sheet": Text(
        "No data {what} for {sheet} (PL-{sheet_system} system)",
        "Brak danych {what} dla {sheet} (uklad PL-{sheet_system})",
    ),
    "wcs_area_cutout_only": Text(
        "--product {product}: WCS area only as a cutout (give the cutout resolution)",
        "--product {product}: obszar WCS tylko jako wycinek (podaj resolution wycinka)",
    ),
    "wcs_cutout_gtiff_only": Text(
        "WCS cutout (coverage) is GTiff only - got format {format!r}; for PNG/JPEG "
        "use the provider without coverage",
        "Wycinek WCS (coverage) jest tylko GTiff - podano format {format!r}; "
        "PNG/JPEG: provider bez coverage",
    ),
    "wcs_cutout_color_only": Text(
        "WCS orthophoto cutout has only the {default_color} composition - got "
        "color={color!r}",
        "wycinek WCS ortofotomapy ma tylko kompozycje {default_color} - podano "
        "color={color!r}",
    ),
    "no_orthophoto_for_sheet": Text(
        "No {color} orthophoto for {sheet} (PL-{sheet_system} system){variants_note}",
        "Brak ortofotomapy {color} dla {sheet} (uklad PL-{sheet_system})"
        "{variants_note}",
    ),
    "sheet_variants_available": Text(
        ". Available variants of this sheet: {variants}",
        ". Dostepne warianty tego arkusza: {variants}",
    ),
    "unsupported_image_product": Text(
        "Unsupported PL image product: {product}",
        "Nieobslugiwany produkt obrazow PL: {product}",
    ),
    "direction_oblique_only": Text(
        "--direction applies only to oblique orthophoto - --product orto has no "
        "directions",
        "--direction dotyczy tylko orto ukosnej - --product orto nie ma kierunkow",
    ),
    # ``providers.pl.prg``.
    "prg_query_counties": Text("PRG query (counties)", "zapytanie PRG (powiaty)"),
    "invalid_county_teryt": Text(
        "PRG WFS: invalid county TERYT code {code!r}",
        "PRG WFS: nieprawidlowy kod TERYT powiatu {code!r}",
    ),
    "response_not_xml": Text(
        "PRG WFS: response is not XML: {error}",
        "PRG WFS: odpowiedz nie jest XML: {error}",
    ),
    "service_error": Text(
        "PRG WFS: service error ({tag}): {text}",
        "PRG WFS: blad uslugi ({tag}): {text}",
    ),
    "no_2d_point_list": Text(
        "PRG WFS: no two-dimensional GML point list",
        "PRG WFS: brak dwuwymiarowej listy punktow GML",
    ),
    "invalid_point_list": Text(
        "PRG WFS: invalid GML point list",
        "PRG WFS: nieprawidlowa lista punktow GML",
    ),
    "polygon_no_exterior": Text(
        "PRG WFS: polygon without an exterior ring",
        "PRG WFS: wielokat bez zewnetrznego pierscienia",
    ),
    "incomplete_returned": Text(
        "PRG WFS: incomplete response for {layer} (numberReturned={returned})",
        "PRG WFS: niepelna odpowiedz {layer} (numberReturned={returned})",
    ),
    "incomplete_matched": Text(
        "PRG WFS: incomplete response for {layer} (numberMatched={matched})",
        "PRG WFS: niepelna odpowiedz {layer} (numberMatched={matched})",
    ),
    "no_layer_geometry": Text(
        "PRG WFS: no geometry for {layer}",
        "PRG WFS: brak geometrii {layer}",
    ),
    "empty_multisurface": Text(
        "PRG WFS: empty MultiSurface geometry for {layer}",
        "PRG WFS: pusta geometria MultiSurface {layer}",
    ),
    "unknown_geometry": Text(
        "PRG WFS: unknown geometry for {layer}: {tag}",
        "PRG WFS: nieznana geometria {layer}: {tag}",
    ),
    "prg_query_layer": Text("PRG query ({layer})", "zapytanie PRG ({layer})"),
    "no_national_boundary": Text(
        "PRG WFS: no national boundary",
        "PRG WFS: brak granicy panstwa",
    ),
    "inconsistent_response": Text(
        "PRG WFS: inconsistent response: numberReturned={returned_attr}, codes {found}",
        "PRG WFS: niespojna odpowiedz: numberReturned={returned_attr}, kodow {found}",
    ),
    "incomplete_county_list": Text(
        "PRG WFS: incomplete county list ({returned} of {matched}) - reduce the area",
        "PRG WFS: niepelna lista powiatow ({returned} z {matched}) - zmniejsz obszar",
    ),
    "unknown_county_count": Text("an unknown number", "nieznanej liczby"),
    # ``providers.pl.skorowidz``.
    "no_coverage_hints": Text("{text}. {hints:join(; )}", "{text}. {hints:join(; )}"),
    "record_no_https_url": Text(
        "Layer {layer}: skipped record without HTTPS URL",
        "Warstwa {layer}: pominieto rekord bez URL HTTPS",
    ),
    "invalid_sheet_code": Text(
        "Layer {layer}: invalid sheet code {code!r}",
        "Warstwa {layer}: nieprawidlowe godlo {code!r}",
    ),
    "record_year_outside_partition": Text(
        "Layer {layer}: record {sheet} has year {record_year} outside the layer "
        "partition",
        "Warstwa {layer}: rekord {sheet} ma rok {record_year} poza partycja warstwy",
    ),
    "record_no_crs_resolution": Text(
        "Layer {layer}: record {sheet} without CRS or resolution - skipped",
        "Warstwa {layer}: rekord {sheet} bez ukladu lub rozdzielczosci - pominieto",
    ),
    "ogc_exception_report": Text(
        "{description}: OGC exception report: {excerpt}",
        "{description}: raport wyjatku OGC: {excerpt}",
    ),
    "not_sheet_index_template": Text(
        "{description}: response is not a GUGiK sheet index template",
        "{description}: odpowiedz nie jest szablonem skorowidza GUGiK",
    ),
    "cached_no_coverage": Text(
        "No data for {sheet} (from metadata cache)",
        "Brak danych dla {sheet} (z cache metadanych)",
    ),
    "missing_index_endpoint": Text(
        "No sheet index endpoint for {product}, {variant}",
        "Brak endpointu skorowidza dla {product}, {variant}",
    ),
    "no_campaign": Text("No campaign for {sheet}", "Brak kampanii {sheet}"),
    "wms_caps_invalid_xml": Text(
        "GUGiK WMS GetCapabilities {wms_endpoint}: invalid XML: {error}",
        "GUGiK WMS GetCapabilities {wms_endpoint}: nieprawidlowy XML: {error}",
    ),
    "wms_layer_pattern_mismatch": Text(
        "GetCapabilities layer {layer_name} of the product family does not match "
        "pattern {pattern} - NOT queried",
        "Warstwa GetCapabilities {layer_name} z rodziny produktu nie pasuje do wzorca "
        "{pattern} - NIE odpytywana",
    ),
    "wms_no_index_layers": Text(
        "GUGiK WMS GetCapabilities {wms_endpoint}: endpoint does not publish sheet "
        "index layers for this product",
        "GUGiK WMS GetCapabilities {wms_endpoint}: endpoint nie publikuje warstw "
        "skorowidza dla tego produktu",
    ),
    "descendant_sheet_available": Text(
        "Available descendant {sheet} - use --scale {scale}",
        "Dostepny potomek {sheet} - uzyj --scale {scale}",
    ),
    "index_other_system_hint": Text(
        "The sheet index has this area in PL-{system}: {sheet} ({scale}) - use this "
        "sheet code or {flags}",
        "Skorowidz ma ten obszar w PL-{system}: {sheet} ({scale}) - uzyj tego godla "
        "lub {flags}",
    ),
    # ``providers.pl.skorowidz_wfs``.
    "incomplete_result": Text("the result would be incomplete", "wynik bylby niepelny"),
    "error_incomplete": Text("{error} - {incomplete}", "{error} - {incomplete}"),
    "wfs_exception_report": Text(
        "{description}: OGC exception report: {details} - {incomplete}",
        "{description}: raport wyjatku OGC: {details} - {incomplete}",
    ),
    "sheet_error": Text("{sheet}: {error}", "{sheet}: {error}"),
    "type_pattern_mismatch": Text(
        "Feature type {text} of family {layer_prefix} does not match the pattern "
        "<prefix><year> - NOT queried",
        "Typ obiektu {text} z rodziny {layer_prefix} nie pasuje do wzorca "
        "<prefiks><rok> - NIE odpytywany",
    ),
    "wfs_response_unreadable": Text(
        "{description}: WFS response unreadable: {error} - {incomplete}",
        "{description}: odpowiedz WFS nieczytelna: {error} - {incomplete}",
    ),
    "no_feature_types": Text(
        "{description}: no feature types {prefix}<year> - {incomplete}",
        "{description}: brak typow obiektow {prefix}<rok> - {incomplete}",
    ),
    "types_shown_label": Text(
        "{types_count} types {prefix}",
        "{types_count} typow {prefix}",
    ),
    "wfs_paging_loop": Text(
        "WFS {endpoint}: paging loop - {incomplete}",
        "WFS {endpoint}: petla stronicowania - {incomplete}",
    ),
    "wfs_getfeature_page": Text(
        "WFS GetFeature {shown} (page {page})",
        "WFS GetFeature {shown} (strona {page})",
    ),
    "not_feature_collection": Text(
        "{description}: response is not a feature collection ({localname}) - "
        "{incomplete}",
        "{description}: odpowiedz nie jest kolekcja obiektow ({localname}) - "
        "{incomplete}",
    ),
    "number_returned_mismatch": Text(
        "{description}: numberReturned={returned!r}, features {found_count} - "
        "{incomplete}",
        "{description}: numberReturned={returned!r}, obiektow {found_count} - "
        "{incomplete}",
    ),
    "feature_repeated_page": Text(
        "{description}: feature {key_value} repeated from the previous page - server "
        "paging inconsistent - {incomplete}",
        "{description}: obiekt {key_value} powtorzony z poprzedniej strony - "
        "stronicowanie serwera niespojne - {incomplete}",
    ),
    "next_page_outside_service": Text(
        "{description}: next page outside the service ({following}) - {incomplete}",
        "{description}: strona next spoza uslugi ({following}) - {incomplete}",
    ),
    "year_outside_partition": Text(
        "Layer {layer}: record {sheet} has year {year} outside the layer partition",
        "Warstwa {layer}: rekord {sheet} ma rok {year} poza partycja warstwy",
    ),
}
