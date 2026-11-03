"""Default metadata cache shared by the CLI and library entry points."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from kartograf import config
from kartograf.cache.metadata import MetadataCache
from kartograf.notices import CACHE_DISABLED, Notice

CACHE_FILENAME = "metadata.db"


def default_cache_path() -> Path:
    """Return the default metadata database: ``<cache_dir>/kartograf/metadata.db``.

    ``cache_dir`` is the user cache directory of ``nogat`` unless the settings
    say otherwise (``KARTOGRAF_CACHE_DIR``, ``NOGAT_CACHE_DIR``, ``nogat.toml``;
    DEV-18.2). The path never depends on the current directory.
    """
    return config.cache_dir() / config.TOOL / CACHE_FILENAME


@contextmanager
def open_cache(
    cache: MetadataCache | bool,
    *,
    force: bool,
    on_notice: Callable[[Notice], None] | None = None,
) -> Iterator[MetadataCache | None]:
    """Use a cache for one request, closing only connections opened here.

    Forced requests use a separate connection to the same database rather than
    changing the refresh mode of a cache shared with other requests; it reads
    the entries younger than the given cache's ``refresh_ttl_seconds``.
    """
    if cache is False:
        yield None
        return
    if isinstance(cache, MetadataCache) and not force:
        yield cache
        return

    def on_disabled(message: str) -> None:
        if on_notice is not None:
            text = message.replace(" - ", " - ")
            if not text.isascii():
                text = text.encode("ascii", "backslashreplace").decode("ascii")
            on_notice(Notice("warning", CACHE_DISABLED, text))

    callback = on_disabled if on_notice is not None else None
    if isinstance(cache, MetadataCache):
        owned = MetadataCache(
            cache.db_path,
            ttl_seconds=cache._ttl_seconds,
            refresh=True,
            on_disabled=callback,
            strict=cache._strict,
            refresh_ttl_seconds=cache._refresh_ttl_seconds,
        )
    else:
        owned = MetadataCache(default_cache_path(), refresh=force, on_disabled=callback)
    try:
        yield owned
    finally:
        owned.close()
