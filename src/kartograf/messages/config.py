"""Messages of the user environment (``kartograf.config``): the root, the settings."""

from kartograf.messages import Text

MESSAGES = {
    # ``config``.
    "empty_root": Text(
        "root is empty: give the store directory or leave it out for the default store",
        "root jest pusty: podaj katalog magazynu albo pomin go, aby uzyc "
        "domyslnego magazynu",
    ),
    # ``config``: a settings file or a setting that cannot be used.
    "file_missing": Text("the file does not exist", "plik nie istnieje"),
    "file_not_utf8": Text("the file is not UTF-8 text", "plik nie jest tekstem UTF-8"),
    "file_unreadable": Text(
        "the file cannot be read: {error}", "nie mozna odczytac pliku: {error}"
    ),
    "file_invalid_toml": Text(
        "the file is not valid TOML: {error}",
        "plik nie jest poprawnym TOML: {error}",
    ),
    "section_not_table": Text("[{name}] is not a table", "[{name}] nie jest tabela"),
    "directory_not_text": Text(
        "a directory must be a text", "katalog musi byc tekstem"
    ),
    "lang_not_allowed": Text(
        "the language must be one of {languages}",
        "jezyk musi byc jednym z: {languages}",
    ),
    "debug_not_flag": Text(
        "debug must be a flag: true, false, 1 or 0",
        "debug musi byc flaga: true, false, 1 albo 0",
    ),
    "not_positive": Text(
        "the value must be a whole number of at least 1",
        "wartosc musi byc liczba calkowita nie mniejsza niz 1",
    ),
    "not_addresses": Text(
        "the value must be IP addresses or networks (127.0.0.1, 10.0.0.0/8), a TOML "
        "list or joined by commas",
        "wartosc musi byc adresami albo sieciami IP (127.0.0.1, 10.0.0.0/8), lista "
        "TOML albo oddzielone przecinkami",
    ),
    "setting_error": Text("{name} {key}: {error}", "{name} {key}: {error}"),
    "file_unusable": Text(
        "The settings file {path} cannot be used: {error}",
        "Nie mozna uzyc pliku ustawien {path}: {error}",
    ),
    "setting_invalid": Text(
        "The setting is not valid: {error}", "Ustawienie jest nieprawidlowe: {error}"
    ),
}
