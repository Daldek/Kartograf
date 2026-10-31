"""Messages of the area ``kinds``."""

from kartograf.messages import Text

MESSAGES = {
    # ``catalog.kinds``.
    "invalid_value_give_one_value_every": Text(
        "{flag}: invalid value {raw!r} - give one value for every country of the task "
        "or country=value pairs separated by commas (countries: pl, cz), e.g. {flag} "
        "pl=...,cz=...",
        "{flag}: nieprawidlowa wartosc {raw!r} - podaj jedna wartosc dla kazdego kraju "
        "zadania albo pary kraj=wartosc rozdzielone przecinkami (kraje: pl, cz), np. "
        "{flag} pl=...,cz=...",
    ),
    "expected_4_comma_separated_values": Text(
        "expected 4 comma-separated values, got {parts_count}",
        "oczekiwano 4 wartosci rozdzielonych przecinkami, podano {parts_count}",
    ),
    "invalid_bbox": Text(
        "Invalid bbox: {reason}. {bbox_expected}",
        "Nieprawidlowy bbox: {reason}. {bbox_expected}",
    ),
    "not_number": Text("{part!r} is not a number", "{part!r} nie jest liczba"),
    "string": Text("string", "napis"),
    "integer": Text("integer", "liczba calkowita"),
    "list_4_numbers_min_x": Text(
        "list of 4 numbers [min_x, min_y, max_x, max_y] with bbox_crs",
        "lista 4 liczb [min_x, min_y, max_x, max_y] z bbox_crs",
    ),
    "string_bbox_crs_together_bbox": Text(
        "string (the bbox CRS) together with bbox",
        "napis (uklad bbox) razem z bbox",
    ),
    "non_empty_path": Text("non-empty path (string)", "niepusta sciezka (napis)"),
    "string_object": Text(
        'string or object {{"pl": string, "cz": string}}',
        'napis albo obiekt {{"pl": napis, "cz": napis}}',
    ),
    "list_strings": Text("list of strings", "lista napisow"),
    "document_kartograf_plan_1": Text(
        "document kartograf-plan/1 (object)",
        "dokument kartograf-plan/1 (obiekt)",
    ),
    "option_expected_got": Text(
        "option {name}: expected {kind_text}, got {value!r}",
        "opcja {name}: oczekiwano {kind_text}, podano {value!r}",
    ),
    "unknown_option_options": Text(
        "unknown option {name!r} (options: {kinds})",
        "nieznana opcja {name!r} (opcje: {kinds})",
    ),
    "option_bbox_needs_bbox_crs": Text(
        "option bbox needs bbox_crs (the coordinate system of the bbox)",
        "opcja bbox wymaga bbox_crs (uklad wspolrzednych bbox)",
    ),
    "option_bbox_crs_needs_bbox": Text(
        "option bbox_crs needs bbox",
        "opcja bbox_crs wymaga bbox",
    ),
}
