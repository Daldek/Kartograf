"""Messages of the metadata cache."""

from kartograf.messages import Text

MESSAGES = {
    # ``cache.metadata``.
    "cache_locked": Text(
        "metadata cache locked by another process ({db_path}): {error} - working "
        "without cache until the end of the task",
        "cache metadanych zablokowany przez inny proces ({db_path}): {error} - praca "
        "bez cache do konca zadania",
    ),
    "cache_unavailable": Text(
        "metadata cache cannot be opened or written ({db_path}): {error} - working "
        "without cache; check directory and file permissions",
        "cache metadanych niedostepny do otwarcia lub zapisu ({db_path}): {error} - "
        "praca bez cache; sprawdz uprawnienia katalogu i pliku",
    ),
    "cache_unreadable": Text(
        "metadata cache unreadable ({db_path}): {error} - working without cache; use "
        "`kartograf cache clear` or delete the file",
        "cache metadanych nieczytelny ({db_path}): {error} - praca bez cache; uzyj "
        "`kartograf cache clear` albo usun plik",
    ),
    # ``cache_info``.
    "hint_locked": Text(
        "Wait until the other process releases the cache database, then repeat the "
        "command",
        "Poczekaj, az inny proces zwolni baze cache, i powtorz komende",
    ),
    "hint_undeletable": Text(
        "Delete the cache file by hand or check the permissions of its directory",
        "Usun plik cache recznie albo sprawdz uprawnienia jego katalogu",
    ),
    "hint_unwritable": Text(
        "Check the permissions of the cache directory and file (it is not corrupt)",
        "Sprawdz uprawnienia katalogu i pliku cache (nie jest uszkodzony)",
    ),
    "error_locked": Text(
        "cache locked by another process: {path} ({error}) - try again when it has "
        "finished",
        "cache zablokowany przez inny proces: {path} ({error}) - sprobuj ponownie po "
        "jego zakonczeniu",
    ),
    "error_unwritable": Text(
        "cache cannot be opened or written: {path} ({error})",
        "cache niedostepny do otwarcia lub zapisu: {path} ({error})",
    ),
    "error_unreadable": Text(
        "cache unreadable: {path} ({error}) - use `kartograf cache clear`",
        "cache nieczytelny: {path} ({error}) - uzyj `kartograf cache clear`",
    ),
    "error_undeletable": Text(
        "cannot delete the unreadable cache file {candidate}: {error}",
        "nie mozna usunac nieczytelnego pliku cache {candidate}: {error}",
    ),
}
