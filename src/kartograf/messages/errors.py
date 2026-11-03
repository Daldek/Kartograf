"""Messages of the error document: its hints, the cancellations, class hints."""

from kartograf.messages import Text

MESSAGES = {
    # ``error_report``: the errors the hierarchy has no class for.
    "interrupted": Text("interrupted (Ctrl-C)", "przerwano (Ctrl-C)"),
    "terminated": Text("terminated (SIGTERM)", "przerwano (SIGTERM)"),
    "internal_error_hint": Text(
        "Report the error with the command and the version; KARTOGRAF_DEBUG=1 shows "
        "the traceback",
        "Zglos blad z komenda i wersja; KARTOGRAF_DEBUG=1 pokazuje traceback",
    ),
    "io_error_hint": Text(
        "Check the path and the permissions: {path}",
        "Sprawdz sciezke i uprawnienia: {path}",
    ),
    "io_error_hint_no_path": Text(
        "Check the paths and the permissions of the directories in the arguments",
        "Sprawdz sciezki i uprawnienia katalogow z argumentow",
    ),
    # The parts of the hint of an invalid argument or a wrong command line.
    "allowed_values": Text(
        "Allowed values of {flag}: {values}.",
        "Dozwolone wartosci {flag}: {values}.",
    ),
    "allowed_values_cut": Text(
        "Allowed values of {flag}: {values}, ...",
        "Dozwolone wartosci {flag}: {values}, ...",
    ),
    "example": Text("Example: {line}", "Przyklad: {line}"),
    "options": Text("Options: {flags}.", "Opcje: {flags}."),
    "usage_hint": Text(
        'The options of the command: kartograf commands schema --command "{command}".',
        'Parametry komendy: kartograf commands schema --command "{command}".',
    ),
    # ``DEFAULT_HINT`` of the exception classes.
    "usage_default_hint": Text(
        'The options of a command: kartograf commands schema --command "<group> '
        '<command>"',
        'Parametry komendy: kartograf commands schema --command "<grupa> <komenda>"',
    ),
    "parse_default_hint": Text(
        "Sheet code formats: PL-1992 N-34-130-D-d-2-4, PL-2000 6.179.12.20, SM5 "
        "CTES96, TM33 302_5550; more: kartograf sheet parse --help",
        "Formaty godel: PL-1992 N-34-130-D-d-2-4, PL-2000 6.179.12.20, SM5 CTES96, "
        "TM33 302_5550; wiecej: kartograf sheet parse --help",
    ),
    "config_default_hint": Text(
        "Fix or remove the settings file, or point NOGAT_CONFIG at another one; "
        "kartograf config show reports the problem",
        "Popraw albo usun plik ustawien, albo wskaz inny w NOGAT_CONFIG; kartograf "
        "config show pokazuje problem",
    ),
    "cache_default_hint": Text(
        "Clear the cache: kartograf cache clear",
        "Wyczysc cache: kartograf cache clear",
    ),
    "sidecar_default_hint": Text(
        "Give the path of a data file of the store or of its sidecar "
        "<file>.meta.json (kartograf-meta/1)",
        "Podaj sciezke pliku danych magazynu albo jego sidecara "
        "<plik>.meta.json (kartograf-meta/1)",
    ),
    "command_not_rebuildable_hint": Text(
        "Pin the file as it is: without its command it cannot be checked for updates "
        "or restored (ADR-057, KB-6)",
        "Przypnij plik taki, jaki jest: bez jego komendy nie da sie sprawdzic "
        "aktualizacji ani go odtworzyc (ADR-057, KB-6)",
    ),
}
