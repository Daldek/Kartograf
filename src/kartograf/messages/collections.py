"""Messages of the collections (``kartograf.download.collections``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.collections``.
    "unit_powiat": Text("county packages", "paczek powiatow"),
    "unit_woj": Text("voivodeship packages", "paczek wojewodztw"),
    "unit_country": Text("country file", "pliku krajowego"),
    "unit_ku": Text("cadastral area packages", "paczek katastralnich uzemi"),
    "product_required": Text(
        "--product required: {collection_product_choices}",
        "--product wymagane: {collection_product_choices}",
    ),
    "product_unknown_value": Text(
        "--product {product!r}: unknown value - available: "
        "{collection_product_choices}",
        "--product {product!r}: nieznana wartosc - dostepne: "
        "{collection_product_choices}",
    ),
    "unknown_product": Text(
        "Unknown product '{product}'. Available: {collection_product_choices}",
        "Nieznany produkt '{product}'. Dostepne: {collection_product_choices}",
    ),
    "area_sheet": Text("sheets of the area", "arkusze obszaru"),
    "area_tile": Text("tiles of the area", "kafle obszaru"),
    "area_ku": Text("cadastral areas of the area", "katastralni uzemi obszaru"),
    "selection": Text("{flags} ({what})", "{flags} ({what})"),
    "selection_with": Text(
        "{flags} with {chosen} ({what})", "{flags} z {chosen} ({what})"
    ),
    "flags_ku": Text("--ku <6 digits>", "--ku <6 cyfr>"),
    "what_area_features": Text("area features", "obiekty obszaru"),
    "what_country_file": Text("country file", "plik krajowy"),
    "what_ku_package": Text("cadastral area package", "paczka katastralniho uzemi"),
    "what_powiat_package": Text("county package", "paczka powiatu"),
    "what_woj_package": Text("voivodeship package", "paczka wojewodztwa"),
    "where_selection": Text(
        "{selection} {product} ({country})", "{selection} {product} ({country})"
    ),
    "country_available": Text("{country}: {available}", "{country}: {available}"),
    "units_counties": Text("counties", "powiatow"),
    "units_voivodeships": Text("voivodeships", "wojewodztw"),
    "what_area_packages": Text(
        "packages of the {units} in the area", "paczki {units} obszaru"
    ),
    "choose_one_single": Text(
        "Give exactly one choice for {subject_flag} ({country}): {available}",
        "Podaj dokladnie jeden wybor dla {subject_flag} ({country}): {available}",
    ),
    "choose_one_multi": Text(
        "Give exactly one choice for {subject_flag} - {per_country:join(; )}",
        "Podaj dokladnie jeden wybor dla {subject_flag} - {per_country:join(; )}",
    ),
    "selection_text_area": Text("area", "obszaru"),
    "teryt_no_unit": Text(
        "--teryt {teryt}: {product} has no {unit_text}",
        "--teryt {teryt}: {product} nie ma {unit_text}",
    ),
    "teryt_per_voivodeship": Text(
        "--teryt {teryt}: {product} is published per voivodeship - give --teryt "
        "{voivodeship_code}",
        "--teryt {teryt}: {product} jest publikowane per wojewodztwo - podaj --teryt "
        "{voivodeship_code}",
    ),
    "no_ku_units": Text(
        "--ku: {product} ({country}) has no {unit_text_ku}",
        "--ku: {product} ({country}) nie ma {unit_text_ku}",
    ),
    "no_country_file": Text(
        "--whole-country: {product} ({country}) has no national file",
        "--whole-country: {product} ({country}) nie ma pliku krajowego",
    ),
    "no_area_data": Text(
        "{product} ({country}) has no data for an area",
        "{product} ({country}) nie ma danych dla obszaru",
    ),
    "other_selection_here": Text(
        "; for {selection_text}: {values}",
        "; dla {selection_text}: {values}",
    ),
    "option_only_elsewhere": Text(
        "{cli_flag} {value}: {product} ({country}) - available only for "
        "{elsewhere}{here}",
        "{cli_flag} {value}: {product} ({country}) - dostepne tylko dla "
        "{elsewhere}{here}",
    ),
    "option_country_mismatch": Text(
        "{cli_flag} applies only to {subject_flag} ({country}: {allowed}) - for "
        "{descriptor_country} omit {cli_flag}",
        "{cli_flag} dotyczy tylko {subject_flag} ({country}: {allowed}) - dla "
        "{descriptor_country} pomin {cli_flag}",
    ),
    "selection_missing_available": Text(
        "{missing}; available: {available}",
        "{missing}; dostepne: {available}",
    ),
    "option_value_unavailable": Text(
        "{cli_flag} {value}: not available for {where}; available: "
        "{values}{option_hint}",
        "{cli_flag} {value}: niedostepne dla {where}; dostepne: {values}{option_hint}",
    ),
    "options_unavailable_together": Text(
        "{chosen}: not available together for {where}",
        "{chosen}: niedostepne razem dla {where}",
    ),
    "option_required_for": Text(
        "{cli_flag} required for {where}: {values}{option_hint}",
        "{cli_flag} wymagane dla {where}: {values}{option_hint}",
    ),
    "hint_value_per_country": Text(
        "a value per country, e.g. {cli_flag} {example}",
        "wartosc per kraj, np. {cli_flag} {example}",
    ),
    "hint_single_value": Text(
        "one value for both countries",
        "jedna wartosc dla obu krajow",
    ),
    "hint_pl_cz_task": Text(
        " (PL+CZ task: {how} - {others}; common: {common})",
        " (zadanie PL+CZ: {how} - {others}; wspolne: {common})",
    ),
    "level_example_item": Text("{code}=<level>", "{code}=<poziom>"),
    "level_hint_multi_country": Text(
        " (PL+CZ task: level per country, e.g. --level {example:join(,)})",
        " (zadanie PL+CZ: poziom per kraj, np. --level {example:join(,)})",
    ),
    "level_not_for_packages": Text(
        "--level applies to area features (--bbox/--sheet/--geometry), not to "
        "{product} packages",
        "--level dotyczy obiektow obszaru (--bbox/--sheet/--geometry), nie paczek "
        "{product}",
    ),
    "flag_not_for_national_file": Text(
        "{cli_flag} does not apply to the national file {product} ({country}: current "
        "release from the ATOM feed)",
        "{cli_flag} nie dotyczy pliku krajowego {product} ({country}: biezace wydanie "
        "z feedu ATOM)",
    ),
    "national_file_subject": Text(
        "the national file {product} ({code})",
        "pliku krajowego {product} ({code})",
    ),
    "hcrs_area_service_crs": Text(
        "--horizontal-crs {horizontal_crs}: area features of {product} ({country}) "
        "are always in the service CRS {crs}",
        "--horizontal-crs {horizontal_crs}: obiekty obszaru {product} ({country}) sa "
        "zawsze w ukladzie uslugi {crs}",
    ),
    "hcrs_file_only_crs": Text(
        "--horizontal-crs {horizontal_crs}: {product} ({country}) publishes this file "
        "only in {crs}",
        "--horizontal-crs {horizontal_crs}: {product} ({country}) publikuje ten plik "
        "tylko w {crs}",
    ),
    "layers_not_applicable": Text(
        "--layers does not apply to {product} (content is stored in full)",
        "--layers nie dotyczy {product} (zawartosc zapisywana w calosci)",
    ),
    "layers_unknown_classes": Text(
        "--layers {unknown}: no such classes in {product} {where}",
        "--layers {unknown}: brak takich klas w {product} {where}",
    ),
    "layers_need_one_class": Text(
        "--layers: give at least one class of {product} {where}",
        "--layers: podaj co najmniej jedna klase {product} {where}",
    ),
    "layers_problem_available": Text(
        "{problem}; available: {published}",
        "{problem}; dostepne: {published}",
    ),
    "selection_not_available": Text(
        "{cli_flag} {value}: not available for {where}; available: {available}",
        "{cli_flag} {value}: niedostepne dla {where}; dostepne: {available}",
    ),
    "area_product_subject": Text(
        "area of {product} ({country})",
        "obszaru {product} ({country})",
    ),
    "flag_not_for_area_state": Text(
        "{cli_flag} does not apply to area features of product {product} ({country}: "
        "current service state)",
        "{cli_flag} nie dotyczy obiektow obszaru produktu {product} ({country}: "
        "biezacy stan uslugi)",
    ),
    "flag_not_for_area_features": Text(
        "{cli_flag} does not apply to area features of product {product} ({country})",
        "{cli_flag} nie dotyczy obiektow obszaru produktu {product} ({country})",
    ),
    "teryt_is_pl_code": Text(
        "--teryt is a TERYT code (PL); remove --country {country}",
        "--teryt to kod TERYT (PL); usun --country {country}",
    ),
    "ku_is_cz_code": Text(
        "--ku is a cadastral area code (CZ); remove --country {country}",
        "--ku to kod katastralniho uzemi (CZ); usun --country {country}",
    ),
    "source_label": Text("{name}, {country}", "{name}, {country}"),
    "product_sources": Text("{sources:join(; )}", "{sources:join(; )}"),
    "layers_count": Text(
        "{count} {count:plural(layer|layers)}",
        "{count} {count:plural(warstwa|warstwy|warstw)}",
    ),
    "level_not_for_fixed_content": Text(
        "--level does not apply to {subject_flag} (fixed content: {content})",
        "--level nie dotyczy {subject_flag} (stala zawartosc: {content})",
    ),
    "unknown_level": Text(
        "unknown level of {product} ({country})",
        "nieznany poziom {product} ({country})",
    ),
    "level_not_applicable": Text(
        "--level does not apply to product {product} (choose --{selector} {codes})",
        "--level nie dotyczy produktu {product} (wybor: --{selector} {codes})",
    ),
    "unavailable_for_where": Text(
        "not available for {where}",
        "niedostepne dla {where}",
    ),
    "selector_required": Text(
        "{cli_flag} required for {where}: {codes}{hint}",
        "{cli_flag} wymagane dla {where}: {codes}{hint}",
    ),
    "selector_value_unknown": Text(
        "{cli_flag} {value}: {unknown}; available: {codes}{hint}",
        "{cli_flag} {value}: {unknown}; dostepne: {codes}{hint}",
    ),
    "unknown_country": Text(
        "Unknown country --country {country!r}: {country_choices}",
        "Nieznany kraj --country {country!r}: {country_choices}",
    ),
    "product_limited_availability": Text(
        "--product {product} is available only for {descriptors}",
        "--product {product} jest dostepny tylko dla {descriptors}",
    ),
    "invalid_teryt_code": Text(
        "Invalid TERYT code {teryt!r}: voivodeship (2 digits, e.g. 12) or county (4 "
        "digits, e.g. 1261)",
        "Nieprawidlowy kod TERYT {teryt!r}: wojewodztwo (2 cyfry, np. 12) albo powiat "
        "(4 cyfry, np. 1261)",
    ),
    "county_code_prefix": Text(
        " (first two digits of the county code)",
        " (dwie pierwsze cyfry kodu powiatu)",
    ),
    "teryt_unknown_voivodeship": Text(
        "--teryt {teryt}: no voivodeship with code {voivodeship_code}{of_powiat}; "
        "available: {known}",
        "--teryt {teryt}: nie ma wojewodztwa o kodzie {voivodeship_code}{of_powiat}; "
        "dostepne: {known}",
    ),
    "invalid_ku_code": Text(
        "Invalid cadastral area code {ku!r}: 6 digits, e.g. 623164",
        "Nieprawidlowy kod katastralniho uzemi {ku!r}: 6 cyfr, np. 623164",
    ),
    "national_file_one_country": Text(
        "a national file of one country",
        "plik krajowy jednego kraju",
    ),
    "national_file": Text("national file", "plik krajowy"),
    "whole_country_requires": Text(
        "--whole-country requires {choices:join( or )} ({what})",
        "--whole-country wymaga {choices:join( albo )} ({what})",
    ),
    "country_required_area": Text(
        "--country required with --bbox/--geometry: {country_choices}",
        "--country wymagane z --bbox/--geometry: {country_choices}",
    ),
    "sheet_system_mismatch": Text(
        "--sheet {sheet} belongs to sheet system {inferred}, but --sheet-system "
        "{selected} was given",
        "--sheet {sheet} nalezy do ukladu {inferred}, a podano --sheet-system "
        "{selected}",
    ),
    "cz_no_sheets_variant": Text(
        "--sheet {sheet}: {product} (CZ) in the selected variant has no CUZK sheets - "
        "give --bbox",
        "--sheet {sheet}: {product} (CZ) w wybranym wariancie nie ma arkuszy CUZK - "
        "podaj --bbox",
    ),
    "invalid_cuzk_sheet_code": Text(
        "Invalid CUZK sheet code {sheet!r} (letters, digits and '-' allowed)",
        "Nieprawidlowe godlo arkusza CUZK {sheet!r} (dozwolone litery, cyfry i '-')",
    ),
    "cz_sheet_no_area": Text(
        "{subject_flag} (CZ): sheet code {sheet} does not define a CZ area - give "
        "--bbox (e.g. in EPSG:5514) or --geometry",
        "{subject_flag} (CZ): godlo {sheet} nie wyznacza obszaru CZ - podaj --bbox "
        "(np. w EPSG:5514) albo --geometry",
    ),
    "sheet_country_mismatch": Text(
        "Sheet code '{sheet}' belongs to system {name} (country {country}), but "
        "--country {country_2} was given",
        "Godlo '{sheet}' nalezy do systemu {name} (kraj {country}), a podano "
        "--country {country_2}",
    ),
    "sheet_needs_pl": Text(
        "--sheet {sheet} ({name}): the collection area is determined by a PL sheet "
        "code; for CZ give --bbox (e.g. in EPSG:5514) or --geometry",
        "--sheet {sheet} ({name}): obszar kolekcji wyznacza godlo PL; dla CZ podaj "
        "--bbox (np. w EPSG:5514) albo --geometry",
    ),
    "area_no_country": Text(
        "the area does not intersect the extent of any known country (PL, CZ)",
        "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
    ),
    "product_country_mismatch": Text(
        "--product {product} is available only for {descriptors}, but the area lies "
        "in {found}",
        "--product {product} jest dostepny tylko dla {descriptors}, a obszar lezy w "
        "{found}",
    ),
    "country_auto_product": Text(
        "--country auto -> {cs} (--product {product} only for {descriptors})",
        "--country auto -> {cs} (--product {product} tylko dla {descriptors})",
    ),
    "area_no_voivodeship": Text(
        "{what}: the area does not intersect any voivodeship (PRG)",
        "{what}: obszar nie przecina zadnego wojewodztwa (PRG)",
    ),
    "area_voivodeships_list": Text(
        "{what}: voivodeships of the area according to PRG ({codes_count}): {named}",
        "{what}: wojewodztwa obszaru wg PRG ({codes_count}): {named}",
    ),
    "area_no_sheet": Text(
        "{product}: the area does not intersect any sheet",
        "{product}: obszar nie przecina zadnego arkusza",
    ),
    "sheets_list": Text(
        "{product}: sheets ({sheets_count}): {names_text}",
        "{product}: arkusze ({sheets_count}): {names_text}",
    ),
    "sheets_list_missing": Text(
        "{product}: sheets ({sheets_count}): {names_text}; without an index record "
        "({missing_count}): {missing_names}",
        "{product}: arkusze ({sheets_count}): {names_text}; bez rekordu w indeksie "
        "({missing_count}): {missing_names}",
    ),
    "from_year": Text(" from year {year_filter}", " z roku {year_filter}"),
    "index_no_records": Text(
        "{product}: the index has no records{year} for the sheets of the area "
        "({names_text})",
        "{product}: indeks nie ma rekordow{year} dla arkuszy obszaru ({names_text})",
    ),
    "no_tiles_in_area": Text(
        "{product}: no tiles in the area (index {endpoint})",
        "{product}: brak kafli w obszarze (indeks {endpoint})",
    ),
    "no_tiles_for_year": Text(
        "{product}: no tiles from year {year} in the area (years in the index: {map})",
        "{product}: brak kafli z roku {year} w obszarze (lata w indeksie: {map})",
    ),
    "area_tiles_list": Text(
        "{product}: tiles of the area ({chosen_count}): {names_text}",
        "{product}: kafle obszaru ({chosen_count}): {names_text}",
    ),
    "no_cadastral_territory": Text(
        "{product}: the area does not intersect any cadastral territory (RUIAN)",
        "{product}: obszar nie przecina zadnego katastralniho uzemi (RUIAN)",
    ),
    "ruian_territories_list": Text(
        "{product}: cadastral territories of the area per RUIAN ({codes_count}): "
        "{names_text}",
        "{product}: katastralni uzemi obszaru wg RUIAN ({codes_count}): {names_text}",
    ),
    "no_county_in_area": Text(
        "{product}: the area does not intersect any county (PRG)",
        "{product}: obszar nie przecina zadnego powiatu (PRG)",
    ),
    "prg_counties_list": Text(
        "{product}: counties of the area per PRG ({units_count}): {names_text}",
        "{product}: powiaty obszaru wg PRG ({units_count}): {names_text}",
    ),
    "nationwide_file_size": Text(
        "{what} {country}: nationwide file {url} - {size_text}",
        "{what} {country}: plik krajowy {url} - {size_text}",
    ),
    "large_file_size": Text(
        "{what} {country} {unit}: large file {url} - {size_text}",
        "{what} {country} {unit}: duzy plik {url} - {size_text}",
    ),
    "package_classes_absent": Text(
        "{product} {country} {unit}: the package has no files for classes {absent} "
        "(no such objects); saved classes {classes}",
        "{product} {country} {unit}: paczka nie ma plikow klas {absent} (brak takich "
        "obiektow); zapisano klasy {classes}",
    ),
    "no_coverage_task_area": Text(
        "{error} (task area: {requested})",
        "{error} (obszar zadania: {requested})",
    ),
    "local_version_removed": Text(
        "{unit}: local version removed during download - retry the download",
        "{unit}: lokalna wersja usunieta w trakcie pobierania - ponow pobranie",
    ),
    "unit_choice_powiat": Text("--teryt <4 digits>", "--teryt <4 cyfry>"),
    "unit_choice_voivodeship": Text("--teryt <2 digits>", "--teryt <2 cyfry>"),
    "unit_choice_ku": Text("--ku", "--ku"),
    "size_estimated": Text(
        "an estimated {bytes_text} (average size over {known} of {count} "
        "{count:plural(file|files)} by HEAD; indicative only - file sizes vary "
        "widely, and the refusal is decided by the file count alone)",
        "szacunkowo {bytes_text} (sredni rozmiar {known} z {count} "
        "{count:plural(pliku|plikow|plikow)} wg HEAD; tylko orientacyjnie - rozmiary "
        "plikow sa bardzo rozne, a o odmowie decyduje juz sama liczba plikow)",
    ),
    "size_at_least": Text(
        "at least {bytes_text} (size known for {known} of {count} "
        "{count:plural(file|files)})",
        "co najmniej {bytes_text} (rozmiar znany dla {known} z {count} "
        "{count:plural(pliku|plikow|plikow)})",
    ),
    "size_total_head": Text(
        "{bytes_text} in total by HEAD",
        "razem {bytes_text} wg HEAD",
    ),
    "choose_unit_hint": Text(
        ", choose a unit ({units:join})",
        ", wybierz jednostke ({units:join})",
    ),
    "volume_limit_exceeded": Text(
        "{product}: the area yields {count} {count:plural(file|files)} to download, "
        "{size} - the limit of one task is {max_files} files and {max_gb} GB. Narrow "
        "the area (--bbox, --sheet, --geometry){unit} or run the plan with part of "
        "the items (--check --plan FILE, then --upgrade --plan FILE)",
        "{product}: obszar daje {count} {count:plural(plik|pliki|plikow)} do "
        "pobrania, {size} - limit jednego zadania to {max_files} plikow i {max_gb} "
        "GB. Zawez obszar (--bbox, --sheet, --geometry){unit} albo wykonaj plan z "
        "czescia pozycji (--check --plan PLIK, potem --upgrade --plan PLIK)",
    ),
}
