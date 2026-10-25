"""Messages of the user environment (``kartograf.config``): the root of the store."""

from kartograf.messages import Text

MESSAGES = {
    # ``config``.
    "empty_root": Text(
        "root is empty: give the store directory or leave it out for the default store",
        "root jest pusty: podaj katalog magazynu albo pomin go, aby uzyc "
        "domyslnego magazynu",
    ),
}
