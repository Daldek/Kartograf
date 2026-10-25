"""Messages of the downloads (``kartograf.download``): the update plan."""

from kartograf.messages import Text

MESSAGES = {
    # ``download``: a plan file from before the store key became ``root`` (0.8.0-dev).
    "old_plan_store_key": Text(
        "The plan has the key store of 0.8.0-dev, which is now root: make a new plan "
        "with --check",
        "Plan ma klucz store z 0.8.0-dev, ktory nazywa sie teraz root: zrob nowy plan "
        "z --check",
    ),
    # ``download.area``.
    "geometry_file_missing": Text(
        "File not found: {filepath}",
        "Brak pliku: {filepath}",
    ),
    "geometry_layer_default": Text(
        "{name}: {available_count} layers, used the first '{choice_name}' (others: "
        "{other_layers}); for another layer: --layer NAME",
        "{name}: liczba warstw {available_count}, uzyto pierwszej '{choice_name}' "
        "(pozostale: {other_layers}); inna warstwa: --layer NAZWA",
    ),
    "clip_sheets_sidecar": Text(
        "sheets were derived from the clipped bbox, the sidecar has request.sheet; "
        "original in extra.parent_request.bbox",
        "arkusze wyznaczono z przycietego bboxa, sidecar ma request.sheet; oryginal w "
        "extra.parent_request.bbox",
    ),
    "clip_sheets_tiles": Text(
        "sheets/tiles were derived from the clipped bbox; original in "
        "extra.parent_request.bbox",
        "arkusze/kafle wyznaczono z przycietego bboxa; oryginal w "
        "extra.parent_request.bbox",
    ),
    "clip_file_bbox": Text(
        "the file and request.bbox carry the clipped extent, original in "
        "extra.parent_request.bbox",
        "plik i request.bbox niosa zasieg przyciety, oryginal w "
        "extra.parent_request.bbox",
    ),
    "auto_part_clipped": Text(
        "--country auto: part {code} clipped to the country envelope ({edges:join}); "
        "{result}",
        "--country auto: czesc {code} przycieta do obwiedni kraju ({edges:join}); "
        "{result}",
    ),
    "clip_edge": Text("{edge}: {degrees}", "{edge}: {degrees}"),
    "degrees": Text(
        "{value:.2f} deg {hemisphere}", "{value:comma(.2f)} st.{hemisphere}"
    ),
    "auto_area_outside": Text(
        "--country auto: area {min_x}-{max_x} x {min_y}-{max_y} (~{percent:.0f} % of "
        "the task area) lies outside the PL/CZ range and was skipped; the explicit "
        "--country {explicit} downloads the whole bbox (beyond the border: sheets "
        "without data / nodata)",
        "--country auto: obszar {min_x}-{max_x} x {min_y}-{max_y} (~{percent:.0f} % "
        "powierzchni zadania) lezy poza zasiegiem PL/CZ i zostal pominiety; caly bbox "
        "pobiera jawne --country {explicit} (za granica: arkusze bez danych / nodata)",
    ),
    "partial_check_failed": Text(
        "part {failed} of the task could not be checked - checked {succeeded}; code 0 "
        "(rectangular country envelopes, ADR-023 items 4-5)",
        "czesc {failed} zadania nie mogla zostac sprawdzona - sprawdzono {succeeded}; "
        "kod 0 (prostokatne obwiednie krajow, ADR-023 pkt 4-5)",
    ),
    "partial_download_failed": Text(
        "part {failed} of the task ended with an error (see Error) - downloaded "
        "{succeeded}; code 0 (rectangular country envelopes, ADR-023 items 4-5)",
        "czesc {failed} zadania zakonczyla sie bledem (patrz Error) - pobrano "
        "{succeeded}; kod 0 (prostokatne obwiednie krajow, ADR-023 pkt 4-5)",
    ),
    # ``download.arguments``.
    "require_int": Text(
        "{name} must be an integer (int), got {value!r}",
        "{name} musi byc liczba calkowita (int), otrzymano {value!r}",
    ),
    "require_workers": Text(
        "{name} must be >= 1, got {value}",
        "{name} musi byc >= 1, podano {value}",
    ),
    "require_str": Text(
        "{name} must be a string (str), got {value!r}",
        "{name} musi byc napisem (str), otrzymano {value!r}",
    ),
    "require_bool": Text(
        "{name} must be a switch (True or False), got {value!r}",
        "{name} musi byc przelacznikiem (True albo False), otrzymano {value!r}",
    ),
    "codes_not_list": Text(
        "{name}: provide a list of codes, e.g. {example}, got {value!r}",
        "{name}: podaj liste kodow, np. {example}, otrzymano {value!r}",
    ),
    "codes_not_strings": Text(
        "{name}: codes must be strings, e.g. {example}, got {bad!r}",
        "{name}: kody musza byc napisami, np. {example}, otrzymano {bad!r}",
    ),
    # ``download.data``.
    "error_remedy": Text("{text} Remedy: {remedy}", "{text} Remedium: {remedy}"),
    "prefixed": Text("{prefix}{text}", "{prefix}{text}"),
    "sheet_failure": Text("{sheet}: {failure}", "{sheet}: {failure}"),
    "flight_description": Text("{name} ({details:join})", "{name} ({details:join})"),
    "better_coverage_row": Text("  {sheet}: {detail}", "  {sheet}: {detail}"),
    "no_plan_items": Text("no plan items", "brak pozycji planu"),
    "sheet_country_mismatch": Text(
        "Sheet code '{sheet}' belongs to system {name} (country {country}), but "
        "--country {country_2} was given",
        "Godlo '{sheet}' nalezy do systemu {name} (kraj {country}), a podano "
        "--country {country_2}",
    ),
    "sheet_wrong_country": Text(
        "--product {product} has no data for {country} - sheet code '{sheet}' belongs "
        "to the {name} system (country {country}); give a sheet code of the product's "
        "country",
        "--product {product} nie ma danych {country} - godlo '{sheet}' nalezy do "
        "systemu {name} (kraj {country}); podaj godlo kraju produktu",
    ),
    "model_only_cz_laz": Text(
        "--model applies only to --product laz in CZ - omit --model for PL",
        "--model dotyczy tylko --product laz w CZ - pomin --model dla PL",
    ),
    "what_sheet": Text("sheet {sheet}", "arkusza {sheet}"),
    "cz_no_campaigns": Text(
        "CZ (CUZK) has no campaigns - "
        "--all-campaigns/--min-year/--max-year/--year/--full-sheet apply only to PL",
        "CZ (CUZK) nie ma kampanii - "
        "--all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza tylko PL",
    ),
    "area_need_cutout": Text("cutout (--cutout)", "wycinek (--cutout)"),
    "area_need_laz_tiles": Text("LAZ tile selection", "wybor kafli LAZ"),
    "area_no_country": Text(
        "the area does not intersect the extent of any known country (PL, CZ)",
        "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
    ),
    "product_country_mismatch": Text(
        "--product {product} is available only for {product_countries}, but the area "
        "lies in {countries}",
        "--product {product} jest dostepny tylko dla {product_countries}, a obszar "
        "lezy w {countries}",
    ),
    "auto_narrowed_product": Text(
        "--country auto -> {own} (--product {product} only for {own_2})",
        "--country auto -> {own} (--product {product} tylko dla {own_2})",
    ),
    "auto_narrowed_pl_only": Text(
        "--country auto -> pl ({pl_only} applies only to PL)",
        "--country auto -> pl ({pl_only} dotyczy tylko PL)",
    ),
    "explicit_country_hint": Text(
        "; use --country pl or --country cz explicitly",
        "; uzyj jawnie --country pl albo --country cz",
    ),
    "product_country_only": Text(
        "--product {product} is available only for {product_countries}{hint}",
        "--product {product} jest dostepny tylko dla {product_countries}{hint}",
    ),
    "area_reaches_cz_model": Text(
        "area extends into CZ: give --model {cz_model_text} or --country pl",
        "obszar siega CZ: podaj --model {cz_model_text} albo --country pl",
    ),
    "label_product": Text("product: {product}", "produkt: {product}"),
    "label_format_resolution": Text(
        "format: {fmt}, resolution: {resolution}",
        "format: {fmt}, rozdzielczosc: {resolution}",
    ),
    "label_resolution": Text("resolution: {resolution}", "rozdzielczosc: {resolution}"),
    "unsupported_sheet_product": Text(
        "Unsupported PL sheet product: {product}",
        "Nieobslugiwany produkt arkuszy PL: {product}",
    ),
    "legacy_campaigns_dir": Text(
        "the kampanie/ directory from version 0.7.x is not used; data will be "
        "downloaded again to versions/",
        "katalog kampanie/ z wersji 0.7.x nie jest uzywany; dane zostana pobrane "
        "ponownie do versions/",
    ),
    "direction_prefix": Text("direction {direction}: ", "kierunek {direction}: "),
    "checked_count": Text("checked {kept}", "sprawdzono {kept}"),
    "sheet_at_scale": Text("{sheet} at scale {scale}", "{sheet} w skali {scale}"),
    "no_sheets_bbox": Text(
        "No sheets for the given bbox",
        "Brak arkuszy dla podanego bbox",
    ),
    "no_sheets_geometry": Text(
        "No sheets for the given geometry",
        "Brak arkuszy dla podanej geometrii",
    ),
    "at_scale": Text("at scale {target_scale}", "w skali {target_scale}"),
    "sheet_list_found": Text(
        "Sheets found {where}: {sheets_count} for {what} ({product_label})\n"
        "  Sheets: {sample}",
        "Znaleziono arkuszy {where}: {sheets_count} dla {what} ({product_label})\n"
        "  Arkusze: {sample}",
    ),
    "no_files_in_index": Text(
        "The GUGiK sheet index has no {describe} files {vertical_crs} "
        "(PL-{sheet_system}){years} for {what} - area data available: kartograf "
        "elevation availability",
        "Skorowidz GUGiK nie ma plikow {describe} {vertical_crs} "
        "(PL-{sheet_system}){years} dla {what} - dostepne dane obszaru: kartograf "
        "elevation availability",
    ),
    "in_gugik_index": Text("in the GUGiK sheet index", "w skorowidzu GUGiK"),
    "downloaded_count": Text("downloaded {paths_count}", "pobrano {paths_count}"),
    "sheets_download_failed": Text(
        "{prefix}{hard_count} of {total} {total:plural(sheet|sheets)} not downloaded "
        "(download error, not missing data): {causes:join(; )} - retry the download",
        "{prefix}{hard_count} z {total} {total:plural(arkusza|arkuszy|arkuszy)} nie "
        "pobrano (blad pobrania, nie brak danych): {causes:join(; )} - ponow pobranie",
    ),
    "no_coverage_some": Text(
        "{prefix}GUGiK has no data for {missing_count} of {total} "
        "{total:plural(sheet|sheets)} ({shown}) - skipped (the GUGiK sheet index does "
        "not have these sheets for the selected product and resolution, e.g. sea, "
        "area abroad, no NMT 5 m in part of the country); {outcome}",
        "{prefix}GUGiK nie ma danych dla {missing_count} z {total} "
        "{total:plural(arkusza|arkuszy|arkuszy)} ({shown}) - pominiete (skorowidz "
        "GUGiK nie ma tych arkuszy dla wybranego produktu i rozdzielczosci, np. "
        "morze, obszar za granica, brak NMT 5 m w czesci kraju); {outcome}",
    ),
    "no_coverage_more_hints": Text(
        "... and {rest} more hints (full list: DownloadResult.no_coverage_hints)",
        "... i {rest} innych podpowiedzi (pelna lista: "
        "DownloadResult.no_coverage_hints)",
    ),
    "full_flight_linked": Text(
        "full flight in <segment>/full_sheet/: {sheets_text}",
        "pelny lot w <segment>/full_sheet/: {sheets_text}",
    ),
    "task_year_scope": Text(" within the task year range", " w zakresie lat zadania"),
    "no_full_flight_index": Text(
        "no full flight in the sheet index{scope}: {sheets_text}",
        "brak pelnego lotu w skorowidzu{scope}: {sheets_text}",
    ),
    "full_sheet_hint": Text(" - use --full-sheet", " - uzyj --full-sheet"),
    "full_flight_not_downloaded": Text(
        "full flight not downloaded: {sheets_text}{hint}",
        "pelny lot nie pobrany: {sheets_text}{hint}",
    ),
    "incomplete_campaign": Text(
        "the latest GUGiK campaign is incomplete for {partial_count} sheets - the "
        "sheet index declares a sheet not entirely filled with content; the file in "
        "the standard path may contain a lot of nodata/black (extra.source.full_sheet "
        "in the sidecar); {groups:join(; )}",
        "najnowsza kampania GUGiK jest niepelna dla {partial_count} arkuszy - "
        "skorowidz deklaruje arkusz nie w calosci wypelniony trescia; plik w sciezce "
        "standardowej moze miec duzo nodata/czerni (extra.source.full_sheet w "
        "sidecarze); {groups:join(; )}",
    ),
    "crs_mismatch_item": Text(
        "{sheet} (sheet code: {expected}, file: {actual})",
        "{sheet} (godlo: {expected}, plik: {actual})",
    ),
    "sheet_crs_mismatch": Text(
        "{found_count} GUGiK {found_count:plural(sheet was|sheets were)} published in "
        "a different CRS than the sheet code indicates: {shown:join}{more} - the "
        "sidecar describes the CRS of the file (horizontal_crs); the record's "
        "declaration is in extra.source.declared_crs",
        "{found_count} {found_count:plural(arkusz|arkusze|arkuszy)} GUGiK "
        "opublikowano w innym ukladzie niz wskazuje godlo: {shown:join}{more} - "
        "sidecar opisuje uklad pliku (horizontal_crs); deklaracja rekordu w "
        "extra.source.declared_crs",
    ),
    "flight_full": Text("full", "pelny"),
    "flight_not_full": Text("not full", "niepelny"),
    "flight_coverage": Text("coverage {percent:g} %", "pokrycie {percent:comma(g)} %"),
    "better_coverage_older": Text(
        "for {better_count} {better_count:plural(sheet|sheets)} an older flight in "
        "the range has greater coverage than the latest (the link points to the "
        "latest):",
        "dla {better_count} {better_count:plural(arkusza|arkuszy|arkuszy)} starszy "
        "lot z przedzialu ma wieksze pokrycie niz najnowszy (dowiazanie wskazuje "
        "najnowszy):",
    ),
    "better_coverage_detail": Text(
        "link {flight_description}; greater coverage: {flight_description_2}",
        "dowiazanie {flight_description}; wieksze pokrycie: {flight_description_2}",
    ),
    "better_coverage_no_details": Text(
        "greater coverage: flight {better_id} (no details in the sidecar)",
        "wieksze pokrycie: lot {better_id} (brak szczegolow w sidecarze)",
    ),
    "sheets_more_count": Text(
        "  ... and {remaining} more",
        "  ... i {remaining} innych",
    ),
    "standard_path": Text("standard path", "sciezka standardowa"),
    "link_outside_range": Text(
        "{rows_count} links point to a local flight outside this task (a link never "
        "moves back to an older flight); downloaded flights are in "
        "<segment>/versions/:",
        "{rows_count} dowiazan wskazuje lokalny lot spoza tego zadania (dowiazanie "
        "nigdy nie cofa sie na starszy lot); pobrane loty sa w <segment>/versions/:",
    ),
    "link_outside_row": Text(
        "  {sheet}: {tree} -> link {campaign_dirname}",
        "  {sheet}: {tree} -> dowiazanie {campaign_dirname}",
    ),
    "cz_resolution_label": Text(
        "CZ, resolution: {label}",
        "CZ, rozdzielczosc: {label}",
    ),
    "cz_cutout": Text("CZ cutout", "wycinka CZ"),
    "cz_cutout_resolution": Text(
        "resolution: {resolution}, {target}",
        "rozdzielczosc: {resolution}, {target}",
    ),
    "cz_orto_no_sheets": Text(
        "CUZK SM5 sheet index has no sheets for the area (area outside CZ?)",
        "indeks arkuszy SM5 CUZK nie ma arkuszy obszaru (obszar poza CZ?)",
    ),
    "cz_orto_announce": Text("CZ, SM5 orthophoto", "CZ, ortofoto SM5"),
    "cz_contours_announce": Text("CZ, contours {format}", "CZ, warstwice {format}"),
    "laz_tiles_failed": Text(
        "{failed_count} of {tiles_count} LAZ {tiles_count:plural(tile|tiles)} not "
        "downloaded (download error): {names} - retry the download{details}",
        "{failed_count} z {tiles_count} {tiles_count:plural(kafla|kafli|kafli)} LAZ "
        "nie pobrano (blad pobrania): {names} - ponow pobranie{details}",
    ),
    # ``download.fetch``.
    "check_function_hint": Text("{check}()", "{check}()"),
    "generic_check_hint": Text("the relevant check_*()", "check_*() danego toru"),
    "update_check_downloads_nothing": Text(
        "update='check' downloads nothing - use {hint} (update plan, kartograf-plan/1)",
        "update='check' niczego nie pobiera - uzyj {hint} (plan aktualizacji, "
        "kartograf-plan/1)",
    ),
    "unknown_update_mode": Text(
        "Unknown update mode update={update!r} (allowed: None, 'upgrade', 'force')",
        "Nieznany tryb update={update!r} (dozwolone: None, 'upgrade', 'force')",
    ),
    "link_version_failed": Text("link {std}: {error}", "dowiazanie {std}: {error}"),
    "metadata_signal_edition_label": Text(
        "signal metadata: versions are labelled by the edition (edition=, without "
        "version=)",
        "sygnal metadata: wersje etykietuje wydanie (edition=, bez version=)",
    ),
    "index_signal_label": Text(
        "signal index: version= or edition= (label of the index record)",
        "sygnal index: version= albo edition= (etykieta rekordu indeksu)",
    ),
    "signal_label_required": Text(
        "signal {signal}: version= required, edition= only for metadata and index",
        "sygnal {signal}: wymagane version=, edition= tylko dla metadata i index",
    ),
    "source_check_failed": Text(
        "{unit}: could not check the source ({error}) - used local version "
        "{file_label}",
        "{unit}: nie udalo sie sprawdzic zrodla ({error}) - uzyto lokalnej wersji "
        "{file_label}",
    ),
    "local_version_unverified": Text(
        "{unit}: local version {file_label} not verified - source has no cheap "
        "signal; download again: --force",
        "{unit}: lokalna wersja {file_label} niesprawdzona - zrodlo bez taniego "
        "sygnalu; pobierz ponownie: --force",
    ),
    "version_no_sidecar": Text(
        "{path}: version without a readable sidecar",
        "{path}: wersja bez czytelnego sidecara",
    ),
    "metadata_signal_needs_edition": Text(
        "signal metadata: edition= required",
        "sygnal metadata: wymagane edition=",
    ),
    # ``download.links``.
    "hardlink_fs_required": Text(
        "{link}: the version store requires a file system with hard links (D22): "
        "{error}",
        "{link}: magazyn wersji wymaga systemu plikow z hardlinkami (D22): {error}",
    ),
    "version_sidecar_unreadable": Text(
        "Version sidecar {target} unreadable - no sidecar {sidecar}",
        "Sidecar wersji {target} nieczytelny - brak sidecara {sidecar}",
    ),
    "sidecar_write_failed": Text(
        "Could not write sidecar {sidecar}: {error} - old sidecar removed (the next "
        "run will recreate the link)",
        "Nie udalo sie zapisac sidecara {sidecar}: {error} - stary sidecar usuniety "
        "(nastepne uruchomienie odtworzy dowiazanie)",
    ),
    "sidecar_append_failed": Text(
        "Could not append data to sidecar {sidecar}: {error}",
        "Nie udalo sie dopisac danych do sidecara {sidecar}: {error}",
    ),
    # ``download.plan``.
    "plan_not_json": Text(
        "Update plan is not JSON: {error}",
        "Plan aktualizacji nie jest JSON: {error}",
    ),
    "plan_unknown_schema": Text(
        "Unknown update plan schema {schema!r} (expected {plan_schema!r})",
        "Nieznany schemat planu aktualizacji {schema!r} (oczekiwano {plan_schema!r})",
    ),
    "plan_incomplete": Text(
        "Incomplete update plan: {error}",
        "Niekompletny plan aktualizacji: {error}",
    ),
    "plan_merge_stores_differ": Text(
        "Cannot merge plans of different stores ({target}, {other_target})",
        "Nie mozna polaczyc planow roznych magazynow ({target}, {other_target})",
    ),
    "plan_unknown_item_status": Text(
        "Unknown plan item status {status!r}",
        "Nieznany status pozycji planu {status!r}",
    ),
    "plan_unknown_item_track": Text(
        "Unknown plan item track {track!r}",
        "Nieznany tor pozycji planu {track!r}",
    ),
    "plan_unknown_notice_level": Text(
        "Unknown plan notice level {level!r}",
        "Nieznany poziom komunikatu planu {level!r}",
    ),
    "plan_other_store": Text(
        "Plan is for a different store ({target}), not {store}",
        "Plan dotyczy innego magazynu ({target}), nie {store}",
    ),
    # ``download.storage``.
    "invalid_segment_variant": Text(
        "Invalid storage segment variant: '{variant}' (expected [a-z0-9]+)",
        "Nieprawidlowy wariant segmentu storage: '{variant}' (oczekiwano [a-z0-9]+)",
    ),
    "invalid_file_suffix": Text(
        "Invalid storage file name suffix: '{suffix}' (expected _[a-z0-9]+)",
        "Nieprawidlowy przyrostek nazwy pliku storage: '{suffix}' (oczekiwano "
        "_[a-z0-9]+)",
    ),
    "unsupported_resolution": Text(
        "Unsupported resolution: '{resolution}'. Supported ({name} {fmt}): {labels}",
        "Nieobslugiwana rozdzielczosc: '{resolution}'. Obslugiwane ({name} {fmt}): "
        "{labels}",
    ),
    "unresolved_segment_dimension": Text(
        "Unresolved storage segment dimension: {missing} (subdir '{subdir}')",
        "Nierozwiazany wymiar segmentu storage: {missing} (subdir '{subdir}')",
    ),
    "unknown_crs_system": Text(
        "Unknown CRS '{system}' (expected '1992' or '2000')",
        "Nieznany uklad '{system}' (oczekiwano '1992' albo '2000')",
    ),
    "invalid_segment_token": Text(
        "Disallowed segment element {token!r} (only lowercase letters and digits "
        "allowed, '-' and '.' only between them)",
        "Niedozwolony element segmentu {token!r} (dozwolone male litery i cyfry, '-' "
        "i '.' tylko miedzy nimi)",
    ),
    "exactly_one_selection": Text(
        "Give exactly one selection: teryt, bbox, sheet, country, ku, tile or mapnom "
        "(zone only with tile)",
        "Podaj dokladnie jeden wybor: teryt, bbox, sheet, country, ku, tile albo "
        "mapnom (zone tylko z tile)",
    ),
    "invalid_teryt_code": Text(
        "Invalid TERYT code: {teryt!r}",
        "Nieprawidlowy kod TERYT: {teryt!r}",
    ),
    "invalid_country_code": Text(
        "Invalid country code: {country!r}",
        "Nieprawidlowy kod kraju: {country!r}",
    ),
    "invalid_ku_code": Text(
        "Invalid cadastral area code: {ku!r}",
        "Nieprawidlowy kod katastralniho uzemi: {ku!r}",
    ),
    "invalid_tile_id": Text(
        "Invalid tile identifier: {tile!r}",
        "Nieprawidlowy identyfikator kafla: {tile!r}",
    ),
    "invalid_tile_crs_dir": Text(
        "Invalid tile CRS directory: {zone!r}",
        "Nieprawidlowy katalog ukladu kafla: {zone!r}",
    ),
    "invalid_cuzk_sheet_code": Text(
        "Invalid CUZK sheet code: {mapnom!r}",
        "Nieprawidlowe godlo arkusza CUZK: {mapnom!r}",
    ),
    # ``download.versions``.
    "coverage_not_measured": Text(
        "No coverage measurement for {name}: {error}",
        "Brak pomiaru pokrycia {name}: {error}",
    ),
    "skipped_version_no_sidecar": Text(
        "Skipped version without a readable sidecar: {directory} (the next write of "
        "the same content will repair it)",
        "Pominieto wersje bez czytelnego sidecara: {directory} (naprawi ja nastepny "
        "zapis tej samej tresci)",
    ),
    "skipped_version_sha256_mismatch": Text(
        "Skipped version with a mismatched sha256: {directory}",
        "Pominieto wersje o niezgodnym sha256: {directory}",
    ),
    "version_sha256_mismatch": Text(
        "{target}: version file has a different sha256 ({existing_prefix}) than the "
        "downloaded one ({downloaded_prefix}) - collision or corrupted file",
        "{target}: plik wersji ma inne sha256 ({existing_prefix}) niz pobrany "
        "({downloaded_prefix}) - kolizja albo uszkodzony plik",
    ),
    "store_needs_hardlinks": Text(
        "{target}: the version store requires a file system with hard links (D22): "
        "{error}",
        "{target}: magazyn wersji wymaga systemu plikow z hardlinkami (D22): {error}",
    ),
    "version_save_failed": Text(
        "{target}: failed to save the version: {error}",
        "{target}: nie udalo sie zapisac wersji: {error}",
    ),
    "sidecar_save_failed": Text(
        "{target}: failed to save the version sidecar: {error}",
        "{target}: nie udalo sie zapisac sidecara wersji: {error}",
    ),
}
