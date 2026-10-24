"""``kartograf config``: the settings in force (DEV-18.6, ADR-050)."""

from kartograf.catalog import shared
from kartograf.catalog.spec import Command, Example, Group

COMMANDS = (
    Command(
        "config show",
        "Pokaz ustawienia uzytkownika: wartosc i zrodlo kazdego klucza",
        "query",
        "get_config",
        "kartograf-config/1",
        (shared.JSON,),
        description="Pokaz ustawienia w mocy (bez sieci i bez zapisu): plik "
        "nogat.toml (sciezka, czy istnieje, dlaczego nie da sie go uzyc), kazdy "
        "klucz (root, data_dir, cache_dir, lang, debug) z wartoscia i zrodlem "
        "(domyslnie, zmienna, plik), dane uwierzytelniajace (CLMS_CREDENTIALS: "
        "ustawione albo brak, bez wartosci) oraz katalog magazynu z rozmiarem "
        "(plik z wieloma dowiazaniami twardymi liczony raz). Dziala tez, gdy "
        "nogat.toml jest uszkodzony: inne komendy go odrzucaja.",
        examples=(
            Example({}, title="Ustawienia jako dokument JSON", run={"json": True}),
        ),
    ),
)

GROUPS = (
    Group(
        "config",
        "Ustawienia uzytkownika: nogat.toml i zmienne srodowiskowe",
        "Ustawienia wspolne z innymi narzedziami Nogat (plik nogat.toml, zmienne "
        "NOGAT_*) i wlasne Kartografa (zmienne KARTOGRAF_*): katalog danych, "
        "katalog cache, magazyn, jezyk; dane uwierzytelniajace tylko ze zmiennych "
        "srodowiskowych.",
        position=2,
    ),
)
