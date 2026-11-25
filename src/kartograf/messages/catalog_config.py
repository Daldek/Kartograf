"""Messages of the command catalog: the declarations of ``config``."""

from kartograf.messages import Text

MESSAGES = {
    "config_show_summary": Text(
        "Show the settings in force: the value and source of every key",
        "Pokaż ustawienia użytkownika: wartość i źródło każdego klucza",
    ),
    "config_show_description": Text(
        "Offline, read only: `nogat.toml` (path, whether it exists, why it cannot be "
        "used), each key (`root`, `data_dir`, `cache_dir`, `lang`, `debug`) with its "
        "value and source, the credentials as set or missing (never the values) and "
        "the store directory with its size. Works with a broken `nogat.toml`.",
        "Pokaż ustawienia w mocy (bez sieci i bez zapisu): plik nogat.toml (ścieżka, "
        "czy istnieje, dlaczego nie da się go użyć), każdy klucz (root, data_dir, "
        "cache_dir, lang, debug) z wartością i źródłem (domyślnie, zmienna, plik), "
        "dane uwierzytelniające (CLMS_CREDENTIALS: ustawione albo brak, bez wartości) "
        "oraz katalog magazynu z rozmiarem (plik z wieloma dowiązaniami twardymi "
        "liczony raz). Działa też, gdy nogat.toml jest uszkodzony: inne komendy go "
        "odrzucają.",
    ),
    "example_settings_json_document": Text(
        "The settings as a JSON document",
        "Ustawienia jako dokument JSON",
    ),
    "config_group_summary": Text(
        "User settings: nogat.toml and environment variables",
        "Ustawienia użytkownika: nogat.toml i zmienne środowiskowe",
    ),
    "config_group_description": Text(
        "The settings shared with the other Nogat tools (the file nogat.toml, the "
        "variables NOGAT_*) and those of Kartograf (KARTOGRAF_*): data directory, "
        "cache directory, store, language; credentials only from environment "
        "variables.",
        "Ustawienia wspólne z innymi narzędziami Nogat (plik nogat.toml, zmienne "
        "NOGAT_*) i własne Kartografa (zmienne KARTOGRAF_*): katalog danych, katalog "
        "cache, magazyn, język; dane uwierzytelniające tylko ze zmiennych "
        "środowiskowych.",
    ),
}
