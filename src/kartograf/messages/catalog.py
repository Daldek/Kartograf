"""Messages of the command catalog: shared texts, sections, metavars and the parser."""

from kartograf.messages import Text

MESSAGES = {
    # ``catalog.shared``: the parameters every command has.
    "bbox_description": Text(
        "Area rectangle [min_x, min_y, max_x, max_y] in the CRS of bbox_crs, as "
        "numbers (metres, or degrees for EPSG:4326).",
        "Prostokąt obszaru: min_x,min_y,max_x,max_y (domyślny układ: EPSG:2180; "
        "współrzędne S-JTSK: --bbox-crs EPSG:5514, np. --bbox "
        "-447000,-1100000,-437000,-1090000)",
    ),
    "sheet_area_description": Text(
        "Sheet code (for example N-34-130-D): the area is the extent of that sheet, "
        "as bbox with its corners.",
        "Obszar = zasięg arkusza o tym godle (np. N-34-130-D), jak --bbox z jego "
        "narożnikami",
    ),
    "geometry_description": Text(
        "Vector file (SHP, GPKG or GeoJSON) with the area: the extent of its features "
        "is the area.",
        "Plik geometrii (SHP, GPKG albo GeoJSON); obszar = obwiednia obiektów",
    ),
    "layer_description": Text(
        "GPKG layer of geometry (default: the first one).",
        "Warstwa GPKG (domyślnie pierwsza; przy wielu warstwach Info z listą "
        "pozostałych)",
    ),
    "check_description": Text(
        "Plan without effects: compare the local versions with the source and return "
        "the plan (kartograf-plan/1: current, newer, to download, or cannot be "
        "checked without downloading); nothing is fetched or written. With "
        "`output_dir`: write, replace or conflict per target.",
        "Sprawdź aktualność lokalnych wersji bez pobierania",
    ),
    "update_description": Text(
        "Update mode. Omitted: keep the local versions and fetch the missing ones. "
        "upgrade: fetch newer content when the source signals it (store only). force: "
        "fetch every file again (store: the same content is unchanged, other content "
        "is a new version; `output_dir`: it replaces the files). CLI: --upgrade, "
        "--force.",
        "Tryb aktualizacji (pominięty: lokalne wersje, brakujące są pobierane)",
    ),
    "plan_description": Text(
        "Update plan (the result of a check) to run with update=upgrade; a position "
        "that changed since the plan stops the run. Store only. CLI: the file of "
        "--plan.",
        "Plan aktualizacji",
    ),
    "plain_note": Text(
        "`output_dir` writes plain files, not the store.",
        "--output-dir zapisuje zwykłe pliki, nie magazyn.",
    ),
    "plain_sheets_description": Text(
        "PL sheets: the newest FULL flight, not the newest one; a sheet with none is "
        "skipped (warning `skipped_incomplete`), all skipped is `no_data`.",
        "Arkusze PL: najnowszy PEŁNY lot, nie najnowszy; arkusz bez pełnego lotu jest "
        "pomijany (ostrzeżenie skipped_incomplete), a gdy wszystkie - no_data; "
        "--full-sheet nie działa, --all-campaigns wymaga magazynu",
    ),
    "product_description": Text("Product.", "Produkt (wymagany)"),
    "country_description": Text(
        "Country of the source: pl, cz or auto (split by the bounding boxes of PL and "
        "CZ).",
        "Kraj źródła danych",
    ),
    "sheet_description": Text("Sheet code.", "Godło arkusza"),
    "bbox_crs_description": Text(
        "CRS of bbox, required with it (the CLI defaults to EPSG:2180).",
        "Układ współrzędnych --bbox (domyślnie EPSG:2180)",
    ),
    "output_dir_description": Text(
        "Directory for plain files named as in the store (no sidecar, no versions). A "
        "repeated name, a store or an existing file (without `update` force) is a "
        "`conflict` and nothing is written. Store only: `update` upgrade and `plan`.",
        "Katalog na zwykłe pliki (nazwy jak w magazynie, bez sidecara i wersji, "
        "tworzony; istniejący plik to konflikt, --force go zastępuje; magazyn jest "
        "odrzucony). Wyklucza się z --root, --upgrade i --plan",
    ),
    "root_description": Text(
        "Store root: versions are written below it, one directory per product, never "
        "over existing ones. Default: the store of the user data directory "
        "(`KARTOGRAF_ROOT`, `[kartograf] root` of `nogat.toml`, else "
        "`<data_dir>/kartograf`).",
        "Katalog magazynu (domyślnie magazyn w katalogu danych użytkownika)",
    ),
    "workers_description": Text("Parallel transfers.", "Liczba równoległych pobrań"),
    "lang_description": Text(
        "Language of the text for people: pl or en (default: KARTOGRAF_LANG, then "
        "nogat.toml, then pl). The --json document, the error line and every notice "
        "of the library stay English.",
        "Język tekstu dla człowieka: pl albo en (domyślnie KARTOGRAF_LANG, potem "
        "nogat.toml, potem pl); dokument --json, linia błędu i komunikaty biblioteki "
        "zostają po angielsku",
    ),
    "section_selection": Text("Product and area", "Produkt i obszar"),
    "section_product": Text("Product parameters", "Parametry produktu"),
    "section_output": Text("Output and update", "Wynik i aktualizacja"),
    "product_choices_description": Text(
        "Product.{choices:skip}",
        "Produkt (wymagany): {choices}",
    ),
    "quiet_description": Text(
        "No progress bar or status lines on stdout (Info:, Warning: and Error: stay "
        "on stderr)",
        "Bez paska postępu i linii statusu na stdout (Info:, Warning: i Error: na "
        "stderr zostają)",
    ),
    "json_description": Text(
        "Print the result as one JSON document on stdout (the schema field names its "
        "type), without progress bar and text; an error as kartograf-error/1",
        "Wypisz wynik jako jeden dokument JSON na stdout (pole schema nazywa jego "
        "typ), bez paska postępu i tekstu; błąd jako kartograf-error/1",
    ),
    "upgrade_description": Text("Fetch newer content", "Pobierz nowszą treść"),
    "force_description": Text("Fetch again", "Pobierz ponownie"),
    "force_plain_description": Text(
        "{force}; with --output-dir it replaces the existing files",
        "{force}; z --output-dir zastępuje istniejące pliki",
    ),
    "check_source_description": Text("{common} {source}", "{common:skip}{source}"),
    "root_files_description": Text(
        "{root}{files:skip}",
        "{root:skip}Katalog magazynu (domyślnie magazyn użytkownika): {files} (wersje "
        "w versions/)",
    ),
    "output_dir_sheets_description": Text(
        "{output_dir} {sheets}",
        "{output_dir}. {sheets}",
    ),
    "with_plain_note": Text("{text} {note}", "{text} {note}"),
    "rule_target": Text(
        "Give at most one of: --output-dir (plain files) or --root (the store); "
        "without them the files go to the default store",
        "Podaj najwyżej jedno z: --output-dir (zwykłe pliki) albo --root (magazyn); "
        "bez nich pliki trafiają do magazynu domyślnego",
    ),
    "rule_output_dir_excludes": Text(
        "--output-dir excludes {flags} (they act on the versions of the store: use "
        "--root)",
        "--output-dir wyklucza {flags} (działają na wersjach magazynu: użyj --root)",
    ),
    # ``catalog.build``: a ``one_of`` group after the description of each option of it
    # (a Polish description has no final period, the English one has).
    "option_exactly_one_of": Text(
        "{description} Give exactly one of {names}.",
        "{description}. Podaj dokładnie jedno z: {names}.",
    ),
    "option_at_most_one_of": Text(
        "{description} Give at most one of {names}.",
        "{description}. Podaj najwyżej jedno z: {names}.",
    ),
    # ``catalog.shared``: ``list-sources`` of every group.
    "list_sources_summary": Text(
        "List the registered data sources of the {group} group (offline)",
        "{group:skip}Wypisz źródła danych grupy (rejestr źródeł, bez sieci)",
    ),
    "list_sources_group_description": Text(
        "Command group (here: {group}); list_sources serves every group",
        "Grupa komend (tu: {group}); list_sources obsługuje wszystkie grupy",
    ),
    "list_sources_product_description": Text(
        "Only the sources of this product (default: every product of the group).",
        "Tylko źródła tego produktu (domyślnie wszystkie produkty grupy)",
    ),
    "list_sources_description": Text(
        "For each source of the {group} group: the options that select it in `{group} "
        "download`, its directory in the store and the `dataset` key of its sidecar. "
        "Use it to see which variants exist; to see what exists for an area use "
        "`elevation availability`.",
        "Wypisz źródła danych grupy {group} z rejestru źródeł (bez sieci): WYBÓR = "
        "wymagane flagi wyboru źródła w download (a|b - jedna z wartości), KATALOG = "
        "katalog plików pod --root, KLUCZ = pole dataset w sidecarze pliku",
    ),
    "list_sources_rule": Text(
        "Offline: nothing is fetched.",
        "Bez sieci: nic nie jest pobierane.",
    ),
    "list_sources_example": Text(
        "The sources of the {group} group",
        "Źródła grupy {group}",
    ),
    # ``catalog.commands._collection``: the collection groups.
    "collection_country_description": Text(
        "Country of the source; required with bbox or geometry{whole}. auto splits "
        "the area between PL and CZ.{teryt}{ku}{sheet}{choices:skip}",
        "Kraj źródła - wymagany z --bbox/--geometry{whole}: "
        "{choices}{teryt}{ku}{sheet}",
    ),
    "collection_country_whole": Text(
        " and whole_country (auto is not allowed with it)",
        " i --whole-country (bez auto)",
    ),
    "collection_country_teryt": Text(" teryt implies pl.", ". Z --teryt tylko pl"),
    "collection_country_ku": Text(" ku implies cz.", ". Z --ku tylko cz"),
    "collection_country_sheet": Text(
        " A sheet code implies its country.",
        ". Z --sheet kraj wynika z godła",
    ),
    "collection_area_description": Text("{text} {result}", "{text}; {result}"),
    "collection_workers_description": Text(
        "Parallel file transfers when the task has several files (unit packages, "
        "sheets, the countries of auto); default 1.",
        "Liczba równoległych pobrań plików, gdy zadanie ma ich kilka (paczki "
        "jednostek obszaru, arkusze, kraje --country auto; domyślnie 1)",
    ),
    "collection_check_description": Text(
        "Cheap signal: the HTTP headers of the national CUZK files; GUGiK packages "
        "and area objects have none (reported as cannot be checked without "
        "downloading).",
        "Porównaj lokalne wersje ze źródłem bez pobierania: plik z sygnałem źródła "
        "(nagłówki HTTP plików krajowych CUZK) - porównanie bez pobrania; paczki "
        "GUGiK i obiekty obszaru nie mają taniego sygnału (nie da się sprawdzić bez "
        "pobrania), brakujące pliki = do pobrania",
    ),
    "collection_upgrade_description": Text(
        "Fetch newer content when the source signals it; files without a cheap signal "
        "stay local (fetch them with --force); with --plan run the saved plan",
        "Pobierz nowszą treść, gdy sygnał źródła ją wskazuje; pliki bez taniego "
        "sygnału zostają lokalne (pobranie: --force); z --plan wykonaj zapisany plan",
    ),
    "collection_force_description": Text(
        "Fetch every file of the task again; the same content = unchanged, other "
        "content = a new version; nothing is overwritten",
        "Pobierz ponownie każdy plik zadania; ta sama treść = bez zmian, inna = nowa "
        "wersja; nic nie jest nadpisywane",
    ),
    "collection_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (kartograf-plan/1); z "
        "--upgrade: wykonaj plan (pozycje zmienione od planu = błąd)",
    ),
    "rule_collection_one_of": Text(
        "Give exactly one choice: {flags}",
        "Podaj dokładnie jeden wybór: {flags}",
    ),
    "rule_collection_whole_country": Text(
        "--whole-country needs {countries:join( or )}",
        "--whole-country wymaga {countries:join( albo )}",
    ),
    # The titles of the sections of ``--help``.
    "section_result": Text("Result", "Wynik"),
    "section_sheets": Text("Sheets of the area", "Arkusze obszaru"),
    "section_cutout": Text("Cutout instead of sheets", "Wycinek zamiast arkuszy"),
    "section_cutout_pl": Text(
        "Cutout instead of sheets (PL only)",
        "Wycinek zamiast arkuszy (tylko PL)",
    ),
    "section_year_flights_tiles": Text(
        "Data year, flights and tiles (PL only)",
        "Rok danych, loty i kafle (tylko PL)",
    ),
    "section_year_availability": Text(
        "Data year (PL only - CUZK does not publish survey years: an error with "
        "--country cz, with --country auto the report covers the PL part only)",
        "Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z --country cz błąd, z "
        "--country auto raport tylko części PL)",
    ),
    "section_year_flights": Text(
        "Data year and flights (PL only: an error with --country cz, with auto it "
        "applies to the PL part)",
        "Rok danych i loty (tylko PL: z --country cz błąd, z auto dotyczy części PL)",
    ),
    # The placeholders of the values in ``--help`` and in the usage lines.
    "metavar_year": Text("YEAR", "ROK"),
    "metavar_version": Text("VERSION", "WERSJA"),
    "metavar_scale": Text("SCALE", "SKALA"),
    "metavar_file": Text("FILE", "PLIK"),
    "metavar_name": Text("NAME", "NAZWA"),
    "metavar_code": Text("CODE", "KOD"),
    "metavar_directory": Text("DIRECTORY", "KATALOG"),
    "metavar_command": Text("COMMAND", "KOMENDA"),
    "metavar_resolution": Text("RESOLUTION", "ROZDZIELCZOŚĆ"),
    "metavar_crs": Text("CRS", "UKŁAD"),
    "metavar_sheet": Text("SHEET", "GODŁO"),
    "metavar_level": Text("LEVEL", "POZIOM"),
    "metavar_network": Text("NETWORK", "SIEĆ"),
    "metavar_directions": Text("DIRECTIONS", "KIERUNKI"),
    "metavar_variant": Text("VARIANT", "WARIANT"),
    "metavar_codes": Text("CODES", "KODY"),
    "metavar_kind": Text("KIND", "RODZAJ"),
    "metavar_units": Text("UNITS", "JEDNOSTKI"),
    "metavar_epsg_code": Text("EPSG:CODE", "EPSG:KOD"),
    "metavar_depth": Text("DEPTH", "GŁĘBOKOŚĆ"),
    "metavar_depth_rule": Text("RULE", "REGUŁA"),
    "metavar_property": Text("PROPERTY", "WŁAŚCIWOŚĆ"),
    "metavar_stat": Text("STAT", "STATYSTYKA"),
    "metavar_lang": Text("LANG", "JĘZYK"),
    "metavar_product": Text("PRODUCT", "PRODUKT"),
    # ``catalog.cliparser``, ``catalog.build``: the parser and its errors.
    "parser_description": Text(
        "Download spatial data from GUGiK (PL), CUZK (CZ), Copernicus and ISRIC. The "
        "data commands are in groups by type of data: a data group has download "
        "(fetch into the store) and list-sources (the sources of the registry, "
        "offline), some groups also list-layers, availability or hsg. sheet "
        "recognizes sheet codes, commands describes the commands, cache is the local "
        "metadata cache.",
        "Pobieranie danych przestrzennych z GUGiK (PL), CUZK (CZ), Copernicus i "
        "ISRIC. Komendy danych są w grupach wg typu danych: grupa danych ma download "
        "(pobranie do magazynu) i list-sources (źródła z rejestru, bez sieci), część "
        "grup także list-layers, availability albo hsg. sheet rozpoznaje godła "
        "arkuszy, commands opisuje komendy, cache - lokalny cache metadanych.",
    ),
    "parser_epilog": Text(
        "Examples:\n"
        "  kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--resolution 1m --vertical-crs EVRF2007 --root ./data\n"
        "  kartograf boundaries download --product admin --teryt 12 --root ./data\n"
        "  kartograf elevation list-sources\n"
        "Command options: kartograf <group> <command> --help",
        "Przykłady:\n"
        "  kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--resolution 1m --vertical-crs EVRF2007 --root ./data\n"
        "  kartograf boundaries download --product admin --teryt 12 --root ./data\n"
        "  kartograf elevation list-sources\n"
        "Opcje komendy: kartograf <grupa> <komenda> --help",
    ),
    "version_help": Text(
        "show the version of the program and exit",
        "pokaż wersję programu i zakończ",
    ),
    "commands_help": Text("Commands", "Komendy"),
    "commands_title": Text("commands", "komendy"),
    "examples_header": Text("Examples:", "Przykłady:"),
    "removed_command": Text(
        "command '{command}' was removed in 0.8.0 - use {replacement}",
        "komenda '{command}' usunięta w 0.8.0 - użyj {replacement}",
    ),
    "removed_download_replacement": Text(
        "kartograf elevation download (--product nmt, nmpt, laz) or kartograf imagery "
        "download (--product orto)",
        "kartograf elevation download (--product nmt, nmpt, laz) albo kartograf "
        "imagery download (--product orto)",
    ),
    "removed_soilgrids_replacement": Text(
        "kartograf soil hsg (HSG groups) or kartograf soil download (SoilGrids "
        "properties)",
        "kartograf soil hsg (grupy HSG) albo kartograf soil download (właściwości "
        "SoilGrids)",
    ),
    "soilgrids_moved": Text(
        "SoilGrids has been in the soil group since 0.8.0 - use kartograf soil "
        "download or kartograf soil list-layers",
        "SoilGrids jest w grupie soil od 0.8.0 - użyj kartograf soil download albo "
        "kartograf soil list-layers",
    ),
    "hint_landcover_product": Text(
        "since 0.8.0 the product is chosen by --product, for example --product "
        "bdot10k; list: kartograf landcover list-sources",
        "od 0.8.0 produkt wybiera --product, np. --product bdot10k; lista: kartograf "
        "landcover list-sources",
    ),
    "hint_landcover_country": Text(
        "the country follows from --product (for example zabaged, data50, data250 = "
        "CZ)",
        "kraj wynika z --product (np. zabaged, data50, data250 = CZ)",
    ),
    "hint_soil_product": Text(
        "a SoilGrids layer is chosen by --property, --depth and --stat; list: "
        "kartograf soil list-layers",
        "warstwę SoilGrids wybierają --property, --depth i --stat; lista: kartograf "
        "soil list-layers",
    ),
    "hint_hsg_stats": Text(
        "since 0.8.0 the HSG statistics are printed by --summary",
        "od 0.8.0 statystyki HSG wypisuje --summary",
    ),
    "hint_hydro_sheet": Text(
        "a CZ area: --bbox (for example with --bbox-crs EPSG:5514) or --geometry",
        "obszar CZ: --bbox (np. z --bbox-crs EPSG:5514) albo --geometry",
    ),
    "hint_json": Text(
        "give it after the command, for example kartograf elevation list-sources "
        "--json",
        "podaj ją za komendą, np. kartograf elevation list-sources --json",
    ),
    "hint_owners": Text("these have it: {owners}", "mają ją: {owners}"),
    "unknown_argument": Text(
        "unknown argument {argument}. Options: {prog} --help",
        "nieznany argument {argument}. Opcje: {prog} --help",
    ),
    "unknown_option": Text(
        "unknown option {flag}. Options: {prog} --help",
        "nieznana opcja {flag}. Opcje: {prog} --help",
    ),
    "unknown_option_hint": Text(
        "unknown option {flag} ({hint}). Options: {prog} --help",
        "nieznana opcja {flag} ({hint}). Opcje: {prog} --help",
    ),
    "repeated_option": Text(
        "{flag} is given more than once, but it takes one value",
        "{flag} podano więcej niż raz, a przyjmuje jedną wartość",
    ),
    "repeated_option_hint": Text(
        "Give {flag} once, and run the command once for each value",
        "Podaj {flag} raz i uruchom komendę raz dla każdej wartości",
    ),
    "crs_needs_bbox": Text(
        "{flag} needs {area} (the CRS of the rectangle is given together with it)",
        "{flag} wymaga {area} (układ współrzędnych prostokąta podaje się razem z nim)",
    ),
    "no_command": Text(
        "no command given: give the name of a command of the catalog or its "
        "operation_id",
        "nie podano komendy: podaj nazwę komendy z katalogu albo jej operation_id",
    ),
    "unknown_command": Text(
        "unknown command {command!r}: give the name of a command of the catalog or "
        "its operation_id",
        "nieznana komenda {command!r}: podaj nazwę komendy z katalogu albo jej "
        "operation_id",
    ),
    "commands_list_hint": Text(
        "List of commands: kartograf commands list",
        "Lista komend: kartograf commands list",
    ),
    # ``catalog.tools``: the tool families of the MCP server.
    "unknown_tool_family": Text(
        "unknown tool family: {shown}", "nieznana rodzina narzędzi: {shown}"
    ),
    "no_tool_family": Text("none given", "nie podano żadnej"),
    "tool_families_hint": Text(
        "Tool families: {families}.", "Rodziny narzędzi: {families}."
    ),
    # ``guide``: the guides for agents.
    "unknown_guide_format": Text(
        "unknown guide format {format!r}", "nieznany rodzaj przewodnika {format!r}"
    ),
}
