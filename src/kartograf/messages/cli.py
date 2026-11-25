"""Messages of the CLI: the texts it prints for a person (``kartograf.cli``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``cli.commands``: the entry point.
    "no_command": Text("no command given", "nie podano komendy"),
    "plan_needs_mode": Text(
        "--plan needs --check or --upgrade",
        "--plan wymaga --check albo --upgrade",
    ),
    "remedy": Text("Remedy: {remedy}", "Remedium: {remedy}"),
    "debug_hint": Text(
        "Set KARTOGRAF_DEBUG=1 to see the full traceback.",
        "Ustaw KARTOGRAF_DEBUG=1, aby zobaczyć pełny traceback.",
    ),
    # Words every command of the CLI shares.
    "yes": Text("yes", "tak"),
    "no": Text("no", "nie"),
    "missing": Text("missing", "brak"),
    # ``cli.availability_cmd``.
    "header_crs": Text("CRS", "UKŁAD"),
    "header_sheets_yes_no": Text("SHEETS YES/NO", "ARKUSZE TAK/NIE"),
    "header_sheets_present": Text("SHEETS PRESENT/MISSING", "ARKUSZE SĄ/BRAK"),
    "header_size": Text("SIZE", "ROZMIAR"),
    "header_year": Text("YEAR", "ROK"),
    "header_flight": Text("FLIGHT", "NALOT"),
    "header_resolution": Text("RES.", "ROZDZ."),
    "header_heights": Text("HEIGHTS", "WYSOKOŚCI"),
    "header_complete": Text("COMPLETE", "KOMPLET"),
    "header_published": Text("PUBLISHED", "PUBLIKACJA"),
    "points_per_m2": Text("{densities} pts/m2", "{densities} pkt/m2"),
    "sheets_incomplete_count": Text("{count} incomplete", "{count} niepełne"),
    "campaign_complete": Text("complete", "komplet"),
    "campaigns_coverage": Text("    campaigns: {coverage}", "    kampanie: {coverage}"),
    "unit_sheets_short": Text("sheets", "ark."),
    "cz_dates_note": Text(
        "CUZK does not publish flight years; dates = file publication",
        "CUZK nie publikuje lat nalotu; daty = publikacja pliku",
    ),
    "complete_no_land": Text("no land", "brak lądu"),
    "sheets_missing_file": Text(
        "{sheets_missing_count} without a file ({area_text})",
        "{sheets_missing_count} bez pliku ({area_text})",
    ),
    "no_sheets_for_area": Text(
        "no sheets for {area_text}",
        "brak arkuszy dla {area_text}",
    ),
    "complete_no_parts": Text("no: {parts}", "nie: {parts}"),
    "pl_availability_header": Text(
        "Availability of {name} PL per GUGiK sheet index: area {area_text}, of which "
        "land {land_text}",
        "Dostępność {name} PL wg skorowidza GUGiK: obszar {area_text}, w tym ląd "
        "{land_text}",
    ),
    "unit_tiles": Text("tiles", "kafli"),
    "unit_sheets": Text("sheets", "arkuszy"),
    "pl_no_sheets_found": Text(
        "No {name} {unit} for the area in the GUGiK sheet index",
        "Brak {unit} {name} dla obszaru w skorowidzu GUGiK",
    ),
    "cz_availability_header": Text(
        "Availability of {name} CZ per CUZK sheet and file index: area {area_text}",
        "Dostępność {name} CZ wg indeksu arkuszy i plików CUZK: obszar {area_text}",
    ),
    "cz_no_sheets_found": Text(
        "No {name} sheets for the area in the CUZK index",
        "Brak arkuszy {name} dla obszaru w indeksie CUZK",
    ),
    "combination_details": Text("Combination details:", "Szczegóły kombinacji:"),
    "sheets_partial_list": Text(
        "    incomplete sheets ({sheets_partial_count}): {sheets_partial}",
        "    arkusze niepełne ({sheets_partial_count}): {sheets_partial}",
    ),
    "sheets_without_file": Text(
        "    sheets without a file ({sheets_missing_count}): {sheets_missing}",
        "    arkusze bez pliku ({sheets_missing_count}): {sheets_missing}",
    ),
    "uncovered_land_area": Text(
        "    land with no sheet of the combination: {area_text}",
        "    ląd bez żadnego arkusza kombinacji: {area_text}",
    ),
    "land_in_full_sheets": Text(
        "    land within full sheets: {share_text} ({area_text})",
        "    ląd w ramach pełnych arkuszy: {share_text} ({area_text})",
    ),
    "campaign_no_number": Text("no number", "bez numeru"),
    "records_to_download": Text(
        "    records to download: {sheets} {unit}, campaigns: {texts}",
        "    pobierane rekordy: {sheets} {unit}, kampanie: {texts}",
    ),
    "no_pl_land": Text(
        "The area has no PL land (sea or outside the national border) - nothing to "
        "download, so no download hint (sheets in the area: --details)",
        "Obszar nie ma lądu PL (morze albo poza granicą państwa) - nie ma czego "
        "pobierać, więc bez podpowiedzi pobrania (arkusze w obszarze: --details)",
    ),
    "no_full_combination": Text(
        "No combination covers all land of the area with full sheets (incomplete and "
        "missing sheets: --details)",
        "Żadna kombinacja nie pokrywa całego lądu obszaru pełnymi arkuszami (arkusze "
        "niepełne i brakujące: --details)",
    ),
    "newest_complete_combination": Text(
        "Newest complete combination: {label}",
        "Najnowsza kompletna kombinacja: {label}",
    ),
    "download_hint_line": Text(
        "  Download (add --root DIR): kartograf {hint}",
        "  Pobranie (dodaj --root KATALOG): kartograf {hint}",
    ),
    "remaining_commands_pl": Text(
        "  ... remaining commands: {rest} (all: --details or --json)",
        "  ... pozostałe polecenia: {rest} (wszystkie: --details albo --json)",
    ),
    "no_complete_cz_combination": Text(
        "No CZ combination has files for all sheets of the area (sheets without a "
        "file: --details)",
        "Żadna kombinacja CZ nie ma plików wszystkich arkuszy obszaru (arkusze bez "
        "pliku: --details)",
    ),
    "complete_cz_combinations": Text(
        "Complete CZ combinations (download: add --root DIR):",
        "Kompletne kombinacje CZ (pobranie: dodaj --root KATALOG):",
    ),
    "remaining_commands_cz": Text(
        "    ... remaining commands: {rest} (all: --details or --json)",
        "    ... pozostałe polecenia: {rest} (wszystkie: --details albo --json)",
    ),
    # ``cli.cache_cmd``.
    "stats_header": Text("Metadata cache statistics:", "Statystyki cache metadanych:"),
    "stats_records": Text("  Record entries: {records}", "  Wpisy rekordów: {records}"),
    "stats_campaigns": Text(
        "  Campaign entries: {campaigns}",
        "  Wpisy kampanii: {campaigns}",
    ),
    "stats_teryt": Text("  TERYT entries: {teryt}", "  Wpisy TERYT: {teryt}"),
    "stats_sheets": Text("  Sheet entries: {sheets}", "  Wpisy arkuszy: {sheets}"),
    "stats_index_areas": Text(
        "  Sheet index area entries: {index_areas}",
        "  Wpisy obszarów skorowidza: {index_areas}",
    ),
    "stats_atom_feeds": Text(
        "  ATOM feed entries: {atom_feeds}",
        "  Wpisy feedów ATOM: {atom_feeds}",
    ),
    "stats_size_no_file": Text(
        "  Database size: - (file not created yet)",
        "  Rozmiar bazy: - (plik jeszcze nie utworzony)",
    ),
    "stats_size_kb": Text(
        "  Database size: {db_size_kb:.1f} KB",
        "  Rozmiar bazy: {db_size_kb:.1f} KB",
    ),
    "stats_size_mb": Text(
        "  Database size: {size_mb:.1f} MB",
        "  Rozmiar bazy: {size_mb:.1f} MB",
    ),
    "stats_db_path": Text("  Database path: {path}", "  Ścieżka bazy: {path}"),
    "clear_removed_unreadable": Text(
        "Removed unreadable cache file: {path}",
        "Usunięto nieczytelny plik cache: {path}",
    ),
    "clear_cache_empty": Text(
        "Cache is empty: no cache file ({path})",
        "Cache jest pusty: nie ma pliku cache ({path})",
    ),
    "clear_done": Text("Cache cleared.", "Cache wyczyszczony."),
    # ``cli.catalog_cmd``.
    "list_footer": Text(
        "Command description with parameters and examples: kartograf commands schema "
        '--command "<group> <command>". JSON document: kartograf commands list --json.',
        "Opis komendy z parametrami i przykładami: kartograf commands schema "
        '--command "<grupa> <komenda>". Dokument JSON: kartograf commands list --json.',
    ),
    "group_products_header": Text("  Products:", "  Produkty:"),
    "group_commands_header": Text("  Commands:", "  Komendy:"),
    "param_header_required": Text("REQUIRED", "WYMAGANY"),
    "param_header_flag": Text("FLAG", "FLAGA"),
    "param_header_kind": Text("KIND", "RODZAJ"),
    "parameters_header": Text("Parameters:", "Parametry:"),
    "allowed_values": Text(
        "Allowed values: {allowed}",
        "Dozwolone wartości: {allowed}",
    ),
    "constraints_header": Text("Constraints:", "Ograniczenia:"),
    "rules_header": Text("Rules:", "Zasady:"),
    "examples_header": Text("Examples:", "Przykłady:"),
    "fact_kind": Text("kind: {kind}", "rodzaj: {kind}"),
    "fact_function": Text(
        "function: {function} -> {result_schema}",
        "funkcja: {function} -> {result_schema}",
    ),
    "fact_check": Text(
        "check: {check_function} -> {check_result_schema}",
        "sprawdzenie: {check_function} -> {check_result_schema}",
    ),
    "fact_effects": Text("effects: {effects}", "skutki: {effects}"),
    "inject_needs_block": Text(
        "--inject puts the block into a file: it needs the format agents-md-block",
        "--inject wstawia blok do pliku: wymaga --format agents-md-block",
    ),
    "inject_needs_block_hint": Text(
        "Run: kartograf commands guide --format agents-md-block --inject AGENTS.md",
        "Uruchom: kartograf commands guide --format agents-md-block --inject AGENTS.md",
    ),
    # ``cli.config_cmd``.
    "source_default": Text("default", "domyślnie"),
    "source_env": Text("variable", "zmienna"),
    "source_file": Text("file", "plik"),
    "state_error": Text("error: {error}", "błąd: {error}"),
    "state_exists": Text("exists", "istnieje"),
    "settings_file_line": Text(
        "Settings file: {path} ({state})",
        "Plik ustawień: {path} ({state})",
    ),
    "settings_header": Text("Settings:", "Ustawienia:"),
    "value_skipped": Text(
        "  (value skipped: {error})",
        "  (pominięto wartość: {error})",
    ),
    "ignored_config_key": Text(
        "  skipped key [kartograf] {setting_key}: {reason}",
        "  pominięto klucz [kartograf] {setting_key}: {reason}",
    ),
    "credentials_header": Text(
        "Credentials (environment variables only):",
        "Dane uwierzytelniające (tylko zmienne środowiskowe):",
    ),
    "credential_set": Text("set", "ustawione"),
    "store_no_directory": Text("no directory", "brak katalogu"),
    "store_line": Text(
        "Store: {root}  [{origin}]  {size}",
        "Magazyn: {root}  [{origin}]  {size}",
    ),
    # ``cli.download_cmd``.
    "download_sheets_progress": Text(
        "Downloading {total} sheets from {sheet} ({message})",
        "Pobieranie {total} arkuszy z {sheet} ({message})",
    ),
    "download_sheet_progress": Text(
        "Downloading {sheet} ({message})...",
        "Pobieranie {sheet} ({message})...",
    ),
    "laz_tiles_found": Text(
        "LAZ tiles found: {total}. Downloading, threads: {workers}...",
        "Znaleziono kafli LAZ: {total}. Pobieranie, wątki: {workers}...",
    ),
    "campaigns_to_download": Text(
        "  Campaigns {sheet} (to download {current} of {total}): {message}",
        "  Kampanie {sheet} (do pobrania {current} z {total}): {message}",
    ),
    "campaign_download_progress": Text(
        "  Downloading {sheet} {message} ({current}/{total})...",
        "  Pobieranie {sheet} {message} ({current}/{total})...",
    ),
    "plan_read_failed": Text(
        "could not read plan {plan_file}: {error}",
        "nie udało się odczytać planu {plan_file}: {error}",
    ),
    "plan_is_directory": Text(
        "--plan {plan_file}: is a directory - give a plan file, e.g. {path}",
        "--plan {plan_file}: to katalog - podaj plik planu, np. {path}",
    ),
    "plan_dir_missing": Text(
        "--plan {plan_file}: directory {directory} does not exist - create it or give "
        "another plan file",
        "--plan {plan_file}: katalog {directory} nie istnieje - utwórz go albo podaj "
        "inny plik planu",
    ),
    "plan_saved_info": Text(
        "Info: update plan saved to {plan_file}",
        "Info: zapisano plan aktualizacji {plan_file}",
    ),
    "plan_nothing_to_do": Text(
        "Info: plan {plan_file}: nothing to do (items are up to date or already done)",
        "Info: plan {plan_file}: brak pozycji do wykonania (pozycje są aktualne albo "
        "już wykonane)",
    ),
    "status_current": Text("up to date", "aktualne"),
    "tiles_progress": Text("  {current}/{total} tiles", "  {current}/{total} kafli"),
    "plan_newer": Text(
        "newer: {available} (local {local_label})",
        "nowsza: {available} (lokalna {local_label})",
    ),
    "plan_text_missing": Text("to download", "do pobrania"),
    "plan_text_unverifiable": Text(
        "cannot be checked without downloading",
        "nie da się sprawdzić bez pobrania",
    ),
    "plan_check_failed": Text(
        "could not check: {error}",
        "nie udało się sprawdzić: {error}",
    ),
    "plan_source_stale": Text(
        "Error: {store_path}: source has changed since the plan ({available_label}) - "
        "check again (--check)",
        "Error: {store_path}: źródło zmieniło się od planu ({available_label}) - "
        "sprawdź ponownie (--check)",
    ),
    "status_new": Text("new version", "nowa wersja"),
    "status_relabeled": Text("new label", "nowa etykieta"),
    "status_unchanged": Text("unchanged", "bez zmian"),
    "status_local": Text("local version", "lokalna wersja"),
    "status_reused": Text("reused", "użyta ponownie"),
    "status_written": Text("written", "zapisano"),
    "status_replaced": Text("replaced", "zastąpiono"),
    "plan_action_write": Text("to write", "do zapisania"),
    "plan_action_replace": Text("to replace (--force)", "do zastąpienia (--force)"),
    "plan_conflict": Text("conflict: {reason}", "konflikt: {reason}"),
    "plan_conflict_output_exists": Text(
        "the file exists (--force replaces it)",
        "plik istnieje (zastępuje go --force)",
    ),
    "plan_conflict_duplicate_output_name": Text(
        "the same file name twice in one request",
        "ta sama nazwa pliku w jednym żądaniu",
    ),
    "plan_conflict_output_in_store": Text(
        "the directory is a store (use --root)",
        "katalog jest magazynem (użyj --root)",
    ),
    "plan_conflict_nested_store": Text(
        "the store root is in, holds or has another store (a store does not nest)",
        "korzeń magazynu jest w innym magazynie, zawiera go albo ma go pod sobą "
        "(magazyn nie zagnieżdża się)",
    ),
    "plan_conflict_not_empty": Text(
        "the store root is not empty and is no store (use a new or empty directory)",
        "korzeń magazynu nie jest pusty i nie jest magazynem (podaj nowy albo pusty "
        "katalog)",
    ),
    "upgrade_force_exclusive": Text(
        "--upgrade and --force exclude each other (--upgrade fetches newer content, "
        "--force fetches everything again)",
        "--upgrade i --force wykluczają się (--upgrade pobiera nowszą treść, "
        "--force pobiera wszystko od nowa)",
    ),
    "relabeled_same_as": Text(
        " (file identical to {same_as})",
        " (plik identyczny z {same_as})",
    ),
    "existing_version": Text("existing version", "istniejąca wersja"),
    "newer_available": Text(
        "; newer {newer} available (--upgrade)",
        "; dostępna nowsza {newer} (--upgrade)",
    ),
    "unchecked_hint": Text(
        " (not checked; --check)",
        " (bez sprawdzania; --check)",
    ),
    "summary_reused": Text(
        "reused: {counts_reused}, ",
        "użyte ponownie: {counts_reused}, ",
    ),
    "version_summary": Text(
        "New: {counts_new}, relabelled: {counts_relabeled}, unchanged: "
        "{counts_unchanged}, local: {counts_local}, {reused}errors: {failed} "
        "({root})",
        "Nowe: {counts_new}, nowa etykieta: {counts_relabeled}, bez zmian: "
        "{counts_unchanged}, lokalne: {counts_local}, {reused}błędy: {failed} "
        "({root})",
    ),
    "plain_summary": Text(
        "Written: {counts_written}, replaced: {counts_replaced}, errors: {failed} "
        "({root})",
        "Zapisane: {counts_written}, zastąpione: {counts_replaced}, błędy: {failed} "
        "({root})",
    ),
    # ``cli.layers_cmd``.
    "classes_note": Text(
        "--layers writes a ZIP of the files of the selected classes. The package has "
        "files only for the classes whose objects exist in the voivodeship (up to "
        "2023): some classes missing = Info, all missing = voivodeship error.",
        "--layers zapisuje ZIP plików wybranych klas. Paczka ma pliki tylko tych "
        "klas, których obiekty są w województwie (do 2023): brak części klas = Info, "
        "brak wszystkich = błąd województwa.",
    ),
    "bdot10k_classes_note": Text(
        "BDOT10k classes ({count}): every code is accepted by --layers (with "
        "--format GPKG; code = OT_<CODE> in table names). A county package has tables "
        "only for the classes whose objects exist in the county: some selected "
        "classes missing = Info, all missing = county error.",
        "Klasy BDOT10k ({count}): każdy kod przyjmuje --layers (z --format GPKG; "
        "kod = OT_<KOD> w nazwach tabel). Paczka powiatu ma tabele tylko tych klas, "
        "których obiekty są w powiecie: brak części wybranych klas = Info, brak "
        "wszystkich = błąd powiatu.",
    ),
    "area_layers_note": Text(
        "Names = GeoPackage layers of the area (--bbox/--geometry); an area result "
        "always has all of these layers (--layers works only with --product bdot10k "
        "or bdoo). The national file (--whole-country) has the layers of the full "
        "database under CUZK names.",
        "Nazwy = warstwy GeoPackage obszaru (--bbox/--geometry); wynik obszaru ma "
        "zawsze wszystkie te warstwy (--layers działa tylko z --product bdot10k albo "
        "bdoo). Plik krajowy (--whole-country) ma warstwy pełnej bazy pod nazwami "
        "CUZK.",
    ),
    "soil_note": Text(
        'A SoilGrids file holds integers in ISRIC units ("in file"); value / divisor '
        "= conventional unit (same description in the sidecar: extra.units). A value "
        "of 0 means an area without data (sea, water, built-up, rock, ice); the file "
        "has no NoData tag.",
        'Plik SoilGrids to liczby całkowite w jednostkach ISRIC ("w pliku"); wartość '
        "/ dzielnik = jednostka konwencjonalna (ten sam opis w sidecarze: "
        "extra.units). Wartość 0 oznacza obszar bez danych (morze, woda, zabudowa, "
        "skały, lód); plik nie ma tagu NoData.",
    ),
    "classes_header_line1": Text(
        "  Feature classes (--layers) by vintage; code = OT_<CODE> in the file names",
        "  Klasy obiektów (--layers) wg rocznika; kod = OT_<KOD> w nazwach plików",
    ),
    "classes_header_line2": Text(
        "  of the voivodeship package.",
        "  paczki województwa.",
    ),
    "depths_only_owners": Text("  (only {owners})", "  (tylko {owners})"),
    "soil_depths_header": Text(
        "  Depths ({depth_note}):",
        "  Głębokości ({depth_note}):",
    ),
    "soil_properties_header": Text(
        "  Soil properties (in file = unit of the value in the file):",
        "  Właściwości gleb (w pliku = jednostka wartości w pliku):",
    ),
    "soil_statistics_header": Text("  Statistics:", "  Statystyki:"),
    "soil_download_selection": Text(
        "  Download selection: --property, --depth, --stat.",
        "  Wybór pobrania: --property, --depth, --stat.",
    ),
    "corine_intro": Text(
        "  CORINE: a single land cover classification.",
        "  CORINE: jedna klasyfikacja pokrycia terenu.",
    ),
    "corine_available_years": Text(
        "  Available years (--year, reference year):",
        "  Dostępne lata (--year, rok referencyjny):",
    ),
    "source_layers_header": Text(
        "Layers of source {source}:",
        "Warstwy źródła {source}:",
    ),
    # ``cli.parse_cmd``.
    "system_cz_tm33": Text("TM33 (CZ) - 2 x 2 km tile", "TM33 (CZ) - kafel 2 x 2 km"),
    "system_cz_sm5": Text(
        "SM5 (CZ) - sheet of the Statni mapa 1:5000",
        "SM5 (CZ) - arkusz Statni mapy 1:5000",
    ),
    "system_cz_ztm": Text(
        "ZTM (CZ) - topographic map sheet (--sheet-system {sheet_system})",
        "ZTM (CZ) - arkusz mapy topograficznej (--sheet-system {sheet_system})",
    ),
    "note_also_contours": Text(" (also contours)", " (także warstwice)"),
    "extent_from_cuzk_index": Text(
        "frame from the CUZK sheet index (read at download)",
        "rama z indeksu arkuszy CUZK (odczyt przy pobraniu)",
    ),
    "label_sheet_code": Text("Sheet:     {sheet}", "Godło:     {sheet}"),
    "label_system": Text("System:    {system}", "Układ:     {system}"),
    "label_extent": Text("Extent:    {extent}", "Zasięg:    {extent}"),
    "label_commands": Text("Commands:  {commands_text}", "Komendy:   {commands_text}"),
    "label_scale": Text("Scale:     {scale}", "Skala:     {scale}"),
    "label_components": Text("Parts:", "Człony:"),
    "commands_and": Text("{head} and {last}", "{head} i {last}"),
    "sheet_in_commands": Text("--sheet in {commands}", "--sheet w {commands}"),
    "label_zone": Text("  Zone: {zone}", "  Strefa: {zone}"),
    "label_native_crs": Text("  Native CRS: {crs}", "  Natywny CRS: {crs}"),
    "hierarchy_header": Text(
        "Hierarchy (from sheet to {top_scale}):",
        "Hierarchia (od arkusza do {top_scale}):",
    ),
    "no_child_sheets": Text(
        "Sheet {sheet} has no child sheets (finest scale {scale})",
        "Arkusz {sheet} nie ma arkuszy potomnych (najdokładniejsza skala {scale})",
    ),
    "child_sheets_header": Text(
        "Child sheets of {sheet} ({children_count}):",
        "Arkusze potomne {sheet} ({children_count}):",
    ),
    "descendant_sheets_header": Text(
        "Child sheets of {sheet} down to scale {scale} ({count}):",
        "Arkusze potomne {sheet} do skali {scale} ({count}):",
    ),
    "sheets_list_header": Text(
        "Sheets {system} {scale} ({count}):",
        "Arkusze {system} {scale} ({count}):",
    ),
    # ``cli.soil_cmd``.
    "hsg_legend_first": Text(
        "Legend: 1=A (high infiltration), 2=B (moderate),",
        "Legenda: 1=A (duża infiltracja), 2=B (umiarkowana),",
    ),
    "hsg_legend_second": Text(
        "         3=C (low), 4=D (very low)",
        "         3=C (mała), 4=D (bardzo mała)",
    ),
    "hsg_scs_cn_method": Text(
        "SCS-CN method: HSG + land use -> Curve Number",
        "Metoda SCS-CN: HSG + użytkowanie terenu -> Curve Number",
    ),
    "hsg_statistics_header": Text(
        "HSG statistics for the task area (groups: % of area with data):",
        "Statystyki HSG obszaru zadania (grupy: % powierzchni z danymi):",
    ),
    "hsg_nodata_area": Text(
        "  No data: {nodata_percent:.1f}% of the task area ({nodata_area_ha:.2f} ha)",
        "  Brak danych: {nodata_percent:.1f}% obszaru zadania ({nodata_area_ha:.2f} "
        "ha)",
    ),
    "hsg_task_area_total": Text(
        "  Task area: {total:.2f} ha",
        "  Obszar zadania: {total:.2f} ha",
    ),
    "hsg_group_line": Text(
        "  Group {group}: {percent:.1f}% ({area_ha:.2f} ha)",
        "  Grupa {group}: {percent:.1f}% ({area_ha:.2f} ha)",
    ),
    # ``cli.sources_cmd``.
    "header_directory": Text("DIRECTORY", "KATALOG"),
    "header_choice": Text("CHOICE", "WYBÓR"),
    "header_country": Text("COUNTRY", "KRAJ"),
    "header_provider": Text("PROVIDER", "DOSTAWCA"),
    "header_key": Text("KEY", "KLUCZ"),
    "header_name": Text("NAME", "NAZWA"),
    "directory_crs": Text("<crs>", "<układ>"),
    "directory_vertical_crs": Text("<vertical-crs>", "<układ-wys>"),
    "list_sources_note": Text(
        "CHOICE: a|b = one of the values. DIRECTORY: under --root; <crs> and "
        "<vertical-crs> follow from the choice, variant choices (scale, format, "
        "vintage) append _<value> segments.",
        "WYBÓR: a|b = jedna z wartości. KATALOG: pod --root; <układ> i <układ-wys> "
        "wynikają z wyboru, wybory wariantu (skala, format, rocznik) dopisują człony "
        "_<wartość>.",
    ),
    "sources_of_group": Text("Sources of group {group}:", "Źródła grupy {group}:"),
    "download_options_hint": Text(
        "Download options: kartograf {group} download --help",
        "Opcje pobrania: kartograf {group} download --help",
    ),
    # ``cli.store_cmd``.
    "header_product": Text("PRODUCT", "PRODUKT"),
    "store_empty": Text(
        "Store {root} is empty (no segments)",
        "Magazyn {root} jest pusty (brak segmentów)",
    ),
    "segment_unknown_registry": Text(
        "{name} [unknown in the registry]",
        "{name} [nieznany w rejestrze]",
    ),
    "store_segments_header": Text(
        "Store {root} ({rows_count} segments):",
        "Magazyn {root} ({rows_count} segmentów):",
    ),
    "more_entries_suffix": Text(", there are more", ", są dalsze"),
    "segment_entries_header": Text(
        "Segment {segment}: {entries_count} entries (limit {limit}{more})",
        "Segment {segment}: {entries_count} wpisów (limit {limit}{more})",
    ),
    "path_required": Text(
        "--path is required (store file)",
        "--path jest wymagane (plik magazynu)",
    ),
}
