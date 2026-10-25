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
}
