"""Messages of the command catalog: the declarations of ``misc``."""

from kartograf.messages import Text

MESSAGES = {
    "sheet_description": Text(
        "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 (`6.179.12.20`), SM5 "
        "(`CTES96`), TM33 tile (`302_5550`) or ZTM (`0510-D-11`, `NM-34-07-1-D-15`).",
        "Godło arkusza: PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. 6.179.12.20), "
        "SM5 (np. CTES96), kafel TM33 (np. 302_5550) albo ZTM (np. 0510-D-11, "
        "NM-34-07-1-D-15)",
    ),
    "hierarchy_description": Text(
        "Add the hierarchy from the sheet up to the scale 1:1000000 (PL codes only).",
        "Pokaż hierarchię od arkusza do skali 1:1000000 (tylko godła PL)",
    ),
    "children_description": Text(
        "Add the direct child sheets (PL codes only).",
        "Pokaż bezpośrednie arkusze potomne (tylko godła PL)",
    ),
    "descendants_description": Text(
        "Add every descendant sheet down to this scale, for example `1:10000` (PL "
        "codes only).",
        "Pokaż wszystkie arkusze potomne do skali docelowej (np. 1:10000; tylko godła "
        "PL)",
    ),
    "command_description": Text(
        "Command to describe (required): its name, such as `elevation download`, or "
        "its `operation_id`, such as `kartograf_elevation_download`.",
        "Komenda do opisania (wymagana): nazwa z katalogu (np. elevation download) "
        "albo jej operation_id (np. kartograf_elevation_download); lista: kartograf "
        "commands list",
    ),
    "form_description": Text(
        "Also give each option its section and its Polish texts (`section`, "
        "`i18n.pl`: the description, the section and the meaning of each allowed "
        "value), what a form of the command reads; a longer page.",
        "Dodaj do każdej opcji jej sekcję i polskie teksty (section, i18n.pl: opis, "
        "sekcja i znaczenie każdej dozwolonej wartości), które czyta formularz "
        "komendy; dłuższa strona",
    ),
    "format_description": Text(
        "Guide to render: `agents` is AGENTS.md, `llms` is llms.txt and "
        "`agents-md-block` is the compact block for the AGENTS.md of a repository "
        "that uses Kartograf.",
        "Rodzaj przewodnika: agents (AGENTS.md), llms (llms.txt) albo agents-md-block "
        "(blok dla AGENTS.md projektu, który używa Kartografa); domyślnie agents",
    ),
    "inject_description": Text(
        "File to put the block in (CLI only).",
        "Wstaw blok agents-md-block do pliku AGENTS.md projektu (zastępuje blok "
        "między <!-- BEGIN kartograf --> a <!-- END kartograf -->, a bez bloku "
        "dopisuje go na końcu; wymaga --format agents-md-block)",
    ),
    "bbox_description": Text(
        "Area rectangle [min_x, min_y, max_x, max_y] in the CRS of `bbox_crs`; "
        "exactly one of `bbox` and `geometry`.",
        "Prostokąt obszaru: min_x,min_y,max_x,max_y w układzie --bbox-crs (domyślnie "
        "EPSG:2180); dokładnie jeden z --bbox i --geometry",
    ),
    "bbox_crs_description": Text(
        "CRS of `bbox`, required with it (the CLI defaults to "
        "EPSG:2180).{pl_bbox_crs:skip}",
        "Układ współrzędnych bbox (wymagany z bbox): {pl_bbox_crs}",
    ),
    "geometry_description": Text(
        "Vector file (SHP, GPKG or GeoJSON): the sheets that intersect its features; "
        "exactly one of `bbox` and `geometry`.",
        "Plik geometrii (SHP, GPKG albo GeoJSON): godła przecinające obiekty pliku; "
        "dokładnie jeden z --bbox i --geometry",
    ),
    "layer_description": Text(
        "GPKG layer of `geometry` (default: the first one).",
        "Warstwa GPKG pliku --geometry (domyślnie pierwsza)",
    ),
    "scale_description": Text(
        "Scale of the sheets (required): PL-1992 1:1000000 to 1:5000, PL-2000 1:10000 "
        "to 1:500.{scale_hierarchy:skip}{scale_hierarchy_2000:skip}",
        "Skala arkuszy (wymagana): PL-1992 {scale_hierarchy}; PL-2000 "
        "{scale_hierarchy_2000}",
    ),
    "sheet_system_description": Text(
        "Sheet system (required): `1992` or `2000`.",
        "Układ godeł (wymagany): 1992 (PL-1992) albo 2000 (PL-2000)",
    ),
    "root_description": Text(
        "Store directory: the one that holds the product segments. Default: the store "
        "of the user data directory (`KARTOGRAF_ROOT`, `[kartograf] root` of "
        "`nogat.toml`, else `<data_dir>/kartograf`).",
        "Katalog magazynu: katalog z segmentami produktów (domyślnie magazyn w "
        "katalogu danych użytkownika)",
    ),
    "init_root_root_description": Text(
        "Store directory: a new or empty one, or the layout of a store without its "
        "marker. Default: the store of the user data directory (`KARTOGRAF_ROOT`, "
        "`[kartograf] root` of `nogat.toml`, else `<data_dir>/kartograf`).",
        "Katalog magazynu: nowy albo pusty, albo układ magazynu bez znacznika "
        "(domyślnie magazyn w katalogu danych użytkownika)",
    ),
    "segment_description": Text(
        "Segment of the store (required): the product directory, for example "
        "`nmt/pl_1992_1m_evrf2007`; `store overview` lists them.",
        "Segment magazynu (wymagany): katalog produktu, np. nmt/pl_1992_1m_evrf2007; "
        "lista: kartograf store overview",
    ),
    "units_description": Text(
        "Only these units of the segment: names as in `sidecar.unit` of an entry (not "
        "prefixes); the reserved names (`versions`, `full_sheet`, `kampanie`) are "
        "errors; default all.",
        "Tylko te jednostki segmentu po przecinku: nazwy jak w sidecar.unit wpisu "
        "(nie prefiksy); nazwy zarezerwowane (versions, full_sheet, kampanie) to "
        "błąd; domyślnie wszystkie",
    ),
    "limit_description": Text(
        "Most entries to return (at least 1, required); `truncated` in the result "
        "says whether more followed.",
        "Najwyżej tyle wpisów (liczba >= 1, wymagana); truncated w wyniku mówi, czy "
        "były dalsze",
    ),
    "path_description": Text(
        "Data file of the store or its sidecar `<file>.meta.json` (required).",
        "Plik danych magazynu albo jego sidecar <plik>.meta.json (wymagany)",
    ),
    "sheet_parse_summary": Text(
        "Recognise a PL or CZ sheet code and show its properties",
        "Rozpoznaj godło arkusza (PL albo CZ) i pokaż jego właściwości",
    ),
    "sheet_parse_description": Text(
        "Offline. PL-1992 and PL-2000 codes: scale, parts, CRS and hierarchy; CZ "
        "codes (SM5, TM33, ZTM): system, CRS and the commands that accept the code. "
        "To go from an area to sheet codes use `sheet find`.",
        "Rozpoznaj godło arkusza i pokaż jego właściwości (bez sieci): PL-1992 i "
        "PL-2000 - skala, człony, układ i hierarchia arkuszy; CZ - system (SM5, kafel "
        "TM33, ZTM), układ współrzędnych i komendy, które przyjmują godło w --sheet.",
    ),
    "example_pl_1992_sheet_code": Text("A PL-1992 sheet code", "Godło PL-1992"),
    "example_descendant_sheets_down_1_10000": Text(
        "Descendant sheets down to 1:10000",
        "Arkusze potomne do skali 1:10000",
    ),
    "example_pl_2000_sheet_code": Text("A PL-2000 sheet code", "Godło PL-2000"),
    "example_cz_code_sm5_sheet": Text("A CZ code (SM5 sheet)", "Godło CZ (arkusz SM5)"),
    "commands_list_summary": Text(
        "List the commands with their groups, products and MCP families",
        "Wypisz komendy z grupami, produktami i rodzinami narzędzi MCP",
    ),
    "commands_list_description": Text(
        "Offline, read only: every group with its products and every command with its "
        "`operation_id`, summary, MCP families, whether it only reads and whether "
        "`check` plans it. Start here; for the options of one command use `commands "
        "schema`.",
        "Przegląd katalogu komend (bez sieci i bez zapisu): grupy z produktami i "
        "komendy (nazwa, operation_id, podsumowanie, rodziny narzędzi MCP, czy tylko "
        "czyta i czy ma plan). --json: dokument kartograf-command-list/1. Opcje "
        'jednej komendy: kartograf commands schema --command "<grupa> <komenda>".',
    ),
    "example_groups_products_commands": Text(
        "The groups, products and commands",
        "Grupy, produkty i komendy",
    ),
    "example_same_json_document": Text(
        "The same as a JSON document",
        "To samo jako dokument JSON",
    ),
    "commands_schema_summary": Text(
        "Describe one command: its options, result, effects, rules and examples",
        "Opisz jedną komendę: opcje, wynik, skutki, zasady i przykłady",
    ),
    "commands_schema_description": Text(
        "Offline, read only: the schema of one command (`kartograf-commands/1`): each "
        "option with its type, bounds, allowed values and meanings, path role and the "
        "options it requires or excludes, the result document, effects, server route, "
        "rules, examples with a result excerpt, error codes and the Polish texts. One "
        "command per call; the names are in `commands list`.",
        "Schemat jednej komendy z katalogu (bez sieci i bez zapisu): opcje (rodzaj, "
        "zakresy, dozwolone wartości ze znaczeniami, rola ścieżki, zależności między "
        "opcjami), dokument wyniku, skutki, trasa serwera, zasady, przykłady z "
        "fragmentem wyniku i kody błędów. --json: dokument kartograf-commands/1 (opisy "
        "po angielsku, polskie teksty komendy w i18n.pl; z --form także sekcje i "
        "polskie teksty opcji).",
    ),
    "example_schema_data_command": Text(
        "The schema of a data command",
        "Schemat komendy danych",
    ),
    "example_schema_form_json": Text(
        "The page of a form: also the sections and the Polish texts of the options, "
        "as JSON",
        "Strona formularza: także sekcje i polskie teksty opcji, jako JSON",
    ),
    "example_schema_command_operation_id_json": Text(
        "The schema of a command by its operation id, as JSON",
        "Schemat komendy wg operation_id, jako JSON",
    ),
    "commands_parse_summary": Text(
        "Read a command line of any command into its call and canonical line",
        "Odczytaj linię polecenia dowolnej komendy: wywołanie i linia kanoniczna",
    ),
    "commands_parse_description": Text(
        "Offline, read only: what a pasted `kartograf ...` line calls "
        "(`kartograf-command-line/1`): the command, the options of the call, the "
        "targets and run options as `commands schema` names them, and the canonical "
        "line. The parser of the CLI decides; `--json` and `--quiet` are no part of a "
        "call. Not a check of the values: use the command with `check` for that.",
        "Bez sieci i bez zapisu: co wywołuje wklejona linia `kartograf ...` (dokument "
        "kartograf-command-line/1): komenda, opcje wywołania, cele zapisu i opcje "
        "uruchomienia (nazwy jak w commands schema) oraz linia kanoniczna. Decyduje "
        "parser CLI; --json i --quiet nie są częścią wywołania. To nie sprawdzenie "
        "wartości: do tego komenda z --check.",
    ),
    "line_description": Text(
        "The command line to read, with or without the leading `kartograf`, quoted "
        "as in a shell.",
        "Linia polecenia do odczytania, z początkowym `kartograf` albo bez, w "
        "cudzysłowach jak w powłoce",
    ),
    "metavar_line": Text("LINE", "LINIA"),
    "example_parse_line": Text(
        "The call of a pasted line",
        "Wywołanie wklejonej linii",
    ),
    "commands_format_summary": Text(
        "Write the canonical command line of a call of any command",
        "Zapisz kanoniczną linię polecenia wywołania dowolnej komendy",
    ),
    "commands_format_description": Text(
        "Offline, read only: the `kartograf ...` line of a call "
        "(`kartograf-command-line/1`), as a command form shows it; `commands parse` "
        "reads it back. The options are those `commands schema` lists, the targets "
        "and run options among them; a path is text, never resolved. Not a check of "
        "the values: use the command with `check` for that.",
        "Bez sieci i bez zapisu: linia `kartograf ...` wywołania (dokument "
        "kartograf-command-line/1), jak pokazuje ją formularz komendy; commands "
        "parse odczytuje ją z powrotem. Opcje jak w commands schema, z celami zapisu "
        "i opcjami uruchomienia; ścieżka to tekst, nigdy nie rozwijany. To nie "
        "sprawdzenie wartości: do tego komenda z --check.",
    ),
    "format_command_description": Text(
        "The command of the call (required): its name, such as `elevation "
        "download`, or its `operation_id`.",
        "Komenda wywołania (wymagana): nazwa z katalogu (np. elevation download) "
        "albo jej operation_id",
    ),
    "format_options_description": Text(
        "The options of the call as a JSON object, by the names of `commands "
        "schema`: the options of the command, `output_dir` or `root`, `check`, "
        "`update` (`upgrade` or `force`), `plan` (a file), `workers`, `summary`.",
        "Opcje wywołania jako obiekt JSON, nazwy jak w commands schema: opcje "
        "komendy, output_dir albo root, check, update (upgrade albo force), plan "
        "(plik), workers, summary",
    ),
    "example_format_call": Text(
        "The line of the plan of a call in a store",
        "Linia planu wywołania w magazynie",
    ),
    "commands_guide_summary": Text(
        "Render the guide for AI agents (AGENTS.md, llms.txt or its block)",
        "Wygeneruj przewodnik dla agentów AI (AGENTS.md, llms.txt, blok)",
    ),
    "commands_guide_description": Text(
        "Offline, read only: the English guide for AI agents generated from the "
        "catalog: `agents` is AGENTS.md, `llms` is llms.txt and `agents-md-block` is "
        "the compact block that `--inject FILE` puts into the AGENTS.md of a "
        "repository that uses Kartograf (CLI only). A large text: fetch it once per "
        "session.",
        "Przewodnik dla agentów AI wygenerowany z katalogu (bez sieci i bez zapisu, "
        "po angielsku): agents to AGENTS.md, llms to llms.txt, agents-md-block to "
        "zwięzły blok, który --inject PLIK wstawia do AGENTS.md projektu "
        "korzystającego z Kartografa. --json: dokument kartograf-guide/1.",
    ),
    "commands_guide_rule": Text(
        "Fetch the guide once per session; `agents` is large.",
        "Pobierz przewodnik raz na sesję; agents jest duży.",
    ),
    "example_llms_txt_kartograf": Text(
        "The llms.txt of Kartograf",
        "Plik llms.txt Kartografa",
    ),
    "example_compact_block_json": Text(
        "The compact block, as JSON",
        "Zwarty blok, jako JSON",
    ),
    "cache_stats_summary": Text(
        "Show the statistics of the metadata cache",
        "Pokaż statystyki cache (liczby wpisów, rozmiar bazy)",
    ),
    "cache_stats_description": Text(
        "Offline, read only: the number of entries of the metadata cache by kind "
        "(records, campaigns, TERYT, sheets, ATOM feeds), the size and the path of "
        "the database.",
        "Wypisz liczby wpisów cache metadanych wg rodzaju (rekordy, kampanie, TERYT, "
        "arkusze, feedy ATOM), rozmiar i ścieżkę bazy",
    ),
    "example_statistics_metadata_cache": Text(
        "The statistics of the metadata cache",
        "Statystyki cache metadanych",
    ),
    "cache_clear_summary": Text(
        "Delete every entry of the metadata cache",
        "Usuń wszystkie wpisy cache",
    ),
    "cache_clear_description": Text(
        "Deletes every entry of the metadata cache (the next commands query the "
        "sources again); an unreadable database file is removed. The data files of "
        "the store stay.",
        "Usuń wszystkie wpisy cache metadanych (następne komendy odpytają źródła "
        "ponownie); nieczytelny plik bazy jest usuwany. Pliki magazynu danych zostają",
    ),
    "example_delete_every_cache_entry": Text(
        "Delete every cache entry",
        "Usuń wszystkie wpisy cache",
    ),
    "cache_path_summary": Text(
        "Show the path of the metadata cache file",
        "Pokaż ścieżkę pliku bazy cache",
    ),
    "cache_path_description": Text(
        "Offline, read only: the path of the metadata cache file, without opening the "
        "database, so it works when the database is unreadable.",
        "Wypisz ścieżkę pliku bazy cache metadanych (w bieżącym katalogu) bez "
        "otwierania bazy: działa też, gdy baza jest nieczytelna",
    ),
    "example_path_cache_file": Text(
        "The path of the cache file",
        "Ścieżka pliku cache",
    ),
    "sheet_find_summary": Text(
        "List the PL sheet codes that cover an area",
        "Wypisz godła arkuszy pokrywające obszar (bbox albo geometria)",
    ),
    "sheet_find_description": Text(
        "Offline: the PL-1992 or PL-2000 sheet codes of the chosen scale that cover a "
        "`bbox` or intersect the features of a `geometry` file; the list is not "
        "truncated. To describe one code use `sheet parse`.",
        "Godła arkuszy PL-1992 albo PL-2000 w wybranej skali, które pokrywają obszar: "
        "bbox (z bbox_crs) albo plik geometrii (arkusze przecinające obiekty); skala "
        "i układ godeł są wymagane. Bez sieci; wynik: lista godeł w kolejności "
        "biblioteki, bez ucinania.",
    ),
    "sheet_find_rule": Text(
        "`scale` and `sheet_system` are required: nothing is guessed.",
        "`scale` i `sheet_system` są wymagane: nic nie jest zgadywane.",
    ),
    "rule_give_exactly_one_area_bbox_geometry": Text(
        "Give exactly one area: bbox or geometry",
        "Podaj dokładnie jeden obszar: bbox albo geometry",
    ),
    "rule_layer_applies_only_geometry_layer_gpkg_file": Text(
        "layer applies only to geometry (the layer of the GPKG file with the area)",
        "layer dotyczy tylko geometry (warstwa pliku GPKG z obszarem)",
    ),
    "example_pl_1992_1_10000_sheets_rectangle": Text(
        "PL-1992 1:10000 sheets for a rectangle",
        "Arkusze PL-1992 1:10000 dla prostokąta",
    ),
    "example_pl_2000_1_2000_sheets_geometry": Text(
        "PL-2000 1:2000 sheets for a geometry",
        "Arkusze PL-2000 1:2000 dla geometrii",
    ),
    "store_overview_summary": Text(
        "List the segments of a store",
        "Wypisz segmenty magazynu danych (przegląd)",
    ),
    "store_overview_description": Text(
        "Read only, offline: the segments (product directories) of the store with "
        "product, country, `dataset` key, name and whether a registered source "
        "produces them. For the files of one segment use `store entries`.",
        "Przegląd magazynu (tylko odczyt, bez sieci): segmenty (katalogi produktów) z "
        "produktem, krajem, kluczem zbioru, nazwą i znacznikiem, czy segment jest w "
        "rejestrze źródeł.",
    ),
    "example_segments_store_data": Text(
        "The segments of the store in ./data",
        "Segmenty magazynu w ./data",
    ),
    "store_entries_summary": Text(
        "List the entries of one store segment: version files with their sidecars",
        "Wypisz wpisy segmentu magazynu: pliki wersji z sidecarami",
    ),
    "store_entries_description": Text(
        "Read only, offline: the first `limit` entries of a segment (version files "
        "and links, their sidecars without `raw`). `segment` and `limit` are "
        "required: a full scan is not an answer for a model. `truncated` says whether "
        "more entries followed.",
        "Pierwsze limit wpisów segmentu magazynu (tylko odczyt, bez sieci): pliki "
        "wersji z sidecarami bez pola raw; segment i limit są wymagane, bo pełny skan "
        "magazynu nie jest odpowiedzią. truncated: były dalsze wpisy; sidecar.unit "
        "wpisu jest wartością units tego samego segmentu.",
    ),
    "store_entries_rule": Text(
        "Take `segment` from `store overview` and `units` from `sidecar.unit`.",
        "Weź `segment` z `store overview`, a `units` z `sidecar.unit`.",
    ),
    "example_first_20_entries_segment": Text(
        "The first 20 entries of a segment",
        "Pierwsze 20 wpisów segmentu",
    ),
    "example_entries_one_sheet": Text(
        "The entries of one sheet",
        "Wpisy jednego arkusza",
    ),
    "store_sidecar_summary": Text(
        "Read the sidecar of one store file (kartograf-meta/1)",
        "Odczytaj sidecar jednego pliku magazynu (kartograf-meta/1)",
    ),
    "store_sidecar_description": Text(
        "Read only, offline: the sidecar of a store data file or of a "
        "`<file>.meta.json`, with the `raw` field. A missing or unreadable sidecar is "
        "the error `data_error` (reason `invalid_sidecar`).",
        "Sidecar pliku danych magazynu albo pliku <plik>.meta.json (tylko odczyt, bez "
        "sieci), wraz z polem raw; brak albo nieczytelny sidecar to błąd "
        "invalid_sidecar.",
    ),
    "example_sidecar_store_file": Text(
        "The sidecar of a store file",
        "Sidecar pliku z magazynu",
    ),
    "store_init_summary": Text(
        "Write the marker of a store (kartograf-store.json)",
        "Zapisz znacznik magazynu (kartograf-store.json)",
    ),
    "store_init_description": Text(
        "Writes `kartograf-store.json` into the store `root` (a new or empty "
        "directory, or one that has the layout of a store and no marker: the layout "
        "is verified first, no file is touched). A store with its marker is left as "
        "it is. Every download writes the marker into a new root by itself; this is "
        "for a store of 0.8.0-dev.",
        "Zapisz kartograf-store.json w magazynie --root (nowy albo pusty katalog, "
        "albo katalog z układem magazynu bez znacznika: układ jest najpierw "
        "sprawdzany, żadnego pliku nie zmienia). Magazyn ze znacznikiem zostaje bez "
        "zmian. Każde pobranie samo zapisuje znacznik w nowym katalogu; ta komenda "
        "jest dla magazynu 0.8.0-dev.",
    ),
    "store_init_rule_1": Text(
        "Run it once on a store that fails with `no_marker`; `check` plans it.",
        "Uruchom raz na magazynie, który kończy się błędem no_marker; --check "
        "planuje zapis.",
    ),
    "store_init_rule_2": Text(
        "Store only: only a store has a marker, so there is no `output_dir`.",
        "Tylko magazyn: znacznik ma tylko magazyn, więc bez --output-dir.",
    ),
    "example_mark_store_data": Text(
        "Mark the store in ./data",
        "Oznacz magazyn w ./data",
    ),
    "store_init_check_description": Text(
        "Plan without effects: say whether the marker would be written, the store has "
        "it already, or the root is a conflict (inside another store, or holding other "
        "files); nothing is written.",
        "Sprawdź bez zapisu: czy znacznik zostałby zapisany, czy magazyn ma go już, "
        "czy katalog jest konfliktem (w innym magazynie albo z innymi plikami)",
    ),
    "example_check_marker_store_data": Text(
        "Plan the marker of the store in ./data without writing it",
        "Sprawdź znacznik magazynu w ./data bez zapisu",
    ),
    "cache_group_summary": Text(
        "Manage the metadata cache",
        "Zarządzaj cache metadanych",
    ),
    "cache_group_description": Text(
        "The local SQLite cache of metadata (WMS answers, TERYT, the index of CUZK "
        "sheets); the data of the store are not part of it.",
        "Lokalny cache metadanych SQLite (odpowiedzi WMS, TERYT, indeks arkuszy CUZK) "
        "w pliku w bieżącym katalogu; dane w magazynie (--root) nie są częścią cache",
    ),
    "commands_group_summary": Text("Catalog of commands", "Katalog komend"),
    "commands_group_description": Text(
        "The description of the commands of Kartograf for agents and scripts "
        "(offline, read only): the list of commands and the schema of one command.",
        "Opis komend Kartografa dla agentów i skryptów (bez sieci i bez zapisu): "
        "lista komend i schemat jednej komendy z opcjami, wynikiem, zasadami i "
        "przykładami.",
    ),
    "sheet_group_summary": Text("Sheet codes", "Godła arkuszy"),
    "sheet_group_description": Text(
        "A PL-1992, PL-2000 or CZ (SM5, TM33, ZTM) sheet code and its properties, and "
        "the sheets that cover an area (offline).",
        "Godło arkusza PL-1992, PL-2000 albo CZ (SM5, TM33, ZTM) i jego właściwości, "
        "bez sieci.",
    ),
    "store_group_summary": Text(
        "Read the store and mark it",
        "Odczyt magazynu i jego znacznik",
    ),
    "store_group_description": Text(
        "Read access to the versioned store (read only, offline): its segments, the "
        "entries with their sidecars and the sidecar of one file; `store init` writes "
        "the marker of a store root.",
        "Odczyt magazynu wersji (tylko odczyt, bez sieci): segmenty, wpisy z "
        "sidecarami i sidecar jednego pliku; store init zapisuje znacznik magazynu.",
    ),
}
