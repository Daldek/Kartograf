"""Messages of the command catalog: the declarations of ``config``."""

from kartograf.messages import Text

MESSAGES = {
    "config_show_summary": Text(
        "Show the settings in force: the value and source of every key",
        "Pokaz ustawienia uzytkownika: wartosc i zrodlo kazdego klucza",
    ),
    "config_show_description": Text(
        "Offline, read only: `nogat.toml` (path, whether it exists, why it cannot be "
        "used), each key (`root`, `data_dir`, `cache_dir`, `lang`, `debug`) with its "
        "value and source, the credentials as set or missing (never the values) and "
        "the store directory with its size. Works with a broken `nogat.toml`.",
        "Pokaz ustawienia w mocy (bez sieci i bez zapisu): plik nogat.toml (sciezka, "
        "czy istnieje, dlaczego nie da sie go uzyc), kazdy klucz (root, data_dir, "
        "cache_dir, lang, debug) z wartoscia i zrodlem (domyslnie, zmienna, plik), "
        "dane uwierzytelniajace (CLMS_CREDENTIALS: ustawione albo brak, bez wartosci) "
        "oraz katalog magazynu z rozmiarem (plik z wieloma dowiazaniami twardymi "
        "liczony raz). Dziala tez, gdy nogat.toml jest uszkodzony: inne komendy go "
        "odrzucaja.",
    ),
    "example_settings_json_document": Text(
        "The settings as a JSON document",
        "Ustawienia jako dokument JSON",
    ),
    "config_group_summary": Text(
        "User settings: nogat.toml and environment variables",
        "Ustawienia uzytkownika: nogat.toml i zmienne srodowiskowe",
    ),
    "config_group_description": Text(
        "The settings shared with the other Nogat tools (the file nogat.toml, the "
        "variables NOGAT_*) and those of Kartograf (KARTOGRAF_*): data directory, "
        "cache directory, store, language; credentials only from environment "
        "variables.",
        "Ustawienia wspolne z innymi narzedziami Nogat (plik nogat.toml, zmienne "
        "NOGAT_*) i wlasne Kartografa (zmienne KARTOGRAF_*): katalog danych, katalog "
        "cache, magazyn, jezyk; dane uwierzytelniajace tylko ze zmiennych "
        "srodowiskowych.",
    ),
}
