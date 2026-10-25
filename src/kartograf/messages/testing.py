"""Messages of the fixture builders of ``kartograf.testing``."""

from kartograf.messages import Text

MESSAGES = {
    # ``testing``.
    "unknown_variant": Text(
        "Unknown variant {variant!r} of the test store (allowed: {variants})",
        "Nieznany wariant {variant!r} magazynu testowego (dozwolone: {variants})",
    ),
    "empty_directory_needed": Text(
        "The test store needs a directory that does not exist or is empty: {base}",
        "Magazyn testowy wymaga nieistniejacego albo pustego katalogu: {base}",
    ),
    "unknown_pin": Text(
        "Unknown value pin={pin!r} (allowed: 'newest', 'oldest')",
        "Nieznana wartosc pin={pin!r} (dozwolone: 'newest', 'oldest')",
    ),
    "project_exists": Text(
        "the project already exists: {path}",
        "projekt juz istnieje: {path}",
    ),
    "task_changed": Text(
        "the task {name} was changed in the meantime",
        "zadanie {name} zmienione w tym czasie",
    ),
}
