"""``kartograf config``: the settings in force (DEV-18.6, ADR-050)."""

from kartograf.catalog import shared
from kartograf.catalog.spec import Command, Example, Group

COMMANDS = (
    Command(
        "config show",
        "Show the settings in force: the value and source of every key",
        "query",
        "get_config",
        "kartograf-config/1",
        (shared.JSON,),
        description=(
            "Offline, read only: `nogat.toml` (path, whether it exists, why"
            " it cannot be used), each key (`root`, `data_dir`, "
            "`cache_dir`, `lang`, `debug`) with its value and source, the "
            "credentials as set or missing (never the values) and the store"
            " directory with its size. Works with a broken `nogat.toml`."
        ),
        examples=(
            Example(
                {},
                title="The settings as a JSON document",
                run={"json": True},
                title_pl="Ustawienia jako dokument JSON",
            ),
        ),
        summary_pl="Pokaz ustawienia uzytkownika: wartosc i zrodlo kazdego klucza",
        description_pl=(
            "Pokaz ustawienia w mocy (bez sieci i bez zapisu): plik "
            "nogat.toml (sciezka, czy istnieje, dlaczego nie da sie go "
            "uzyc), kazdy klucz (root, data_dir, cache_dir, lang, debug) z "
            "wartoscia i zrodlem (domyslnie, zmienna, plik), dane "
            "uwierzytelniajace (CLMS_CREDENTIALS: ustawione albo brak, bez "
            "wartosci) oraz katalog magazynu z rozmiarem (plik z wieloma "
            "dowiazaniami twardymi liczony raz). Dziala tez, gdy nogat.toml"
            " jest uszkodzony: inne komendy go odrzucaja."
        ),
        rules=(),
        rules_pl=(),
        errors=(),
    ),
)

GROUPS = (
    Group(
        "config",
        "User settings: nogat.toml and environment variables",
        (
            "The settings shared with the other Nogat tools (the file "
            "nogat.toml, the variables NOGAT_*) and those of Kartograf "
            "(KARTOGRAF_*): data directory, cache directory, store, "
            "language; credentials only from environment variables."
        ),
        position=2,
        summary_pl="Ustawienia uzytkownika: nogat.toml i zmienne srodowiskowe",
        description_pl=(
            "Ustawienia wspolne z innymi narzedziami Nogat (plik "
            "nogat.toml, zmienne NOGAT_*) i wlasne Kartografa (zmienne "
            "KARTOGRAF_*): katalog danych, katalog cache, magazyn, jezyk; "
            "dane uwierzytelniajace tylko ze zmiennych srodowiskowych."
        ),
    ),
)
