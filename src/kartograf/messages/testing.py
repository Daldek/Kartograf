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
}
