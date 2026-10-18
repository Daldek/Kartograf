"""
The metadata cache as a document (``kartograf-cache/1``, spec 5.4.9).

The default cache of the library and the CLI is the SQLite database
``<cwd>/.kartograf_cache.db`` (the index records, campaign lists, TERYT codes,
sheet indexes, index areas and ATOM feed indexes it keeps are lookups that save
network requests, never downloaded data). ``get_cache_info`` reports it,
``clear_cache`` empties it. Neither creates a missing database.

An unreadable database is a ``CacheError`` for ``get_cache_info``; ``clear_cache``
repairs it by deleting the file with its ``-wal`` and ``-shm`` companions. A
database locked by another process is a ``CacheError`` for both and is never
deleted: the file is fine, it only has to wait.

Examples
--------
>>> from kartograf.cache_info import get_cache_info
>>> info = get_cache_info()
>>> info.action, info.path.name
('info', '.kartograf_cache.db')
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import is_lock_error
from kartograf.exceptions import CacheError
from kartograf.notices import Notice
from kartograf.serialization import Document

# Hints where the default hint of ``CacheError`` (clear the cache) would be the
# command that cannot help: a locked file is fine and only has to wait, and an
# unreadable file that cannot be deleted is what ``clear`` just failed at.
_LOCKED_HINT = "Poczekaj, az inny proces zwolni baze cache, i powtorz komende"
_UNDELETABLE_HINT = "Usun plik cache recznie albo sprawdz uprawnienia jego katalogu"


@dataclass(frozen=True)
class CacheEntries:
    """The number of entries of every table of the cache."""

    records: int
    campaigns: int
    teryt: int
    sheets: int
    index_areas: int
    atom_feeds: int


@dataclass(frozen=True)
class CacheInfo(Document):
    """The state of the cache (``kartograf-cache/1``).

    Attributes
    ----------
    action : str
        ``info`` (``get_cache_info``) or ``clear`` (``clear_cache``).
    path : Path
        The database file (``<cwd>/.kartograf_cache.db``), absolute.
    exists : bool
        Whether the file exists (the first write creates it).
    size_bytes : int, optional
        Size of the file; ``None`` without it.
    entries : CacheEntries, optional
        The numbers of entries; ``None`` after ``clear`` and without the file.
    cleared : bool, optional
        ``True`` after ``clear``, ``None`` for ``info``.
    removed_unreadable : bool, optional
        ``clear``: whether an unreadable file was deleted; ``None`` for ``info``.
    """

    SCHEMA = "kartograf-cache/1"

    action: Literal["info", "clear"]
    path: Path
    exists: bool
    size_bytes: int | None
    entries: CacheEntries | None
    cleared: bool | None = None
    removed_unreadable: bool | None = None


def get_cache_info() -> CacheInfo:
    """Report the metadata cache of the current directory.

    The database is opened only when its file exists: a missing file is reported
    (``exists`` false, no ``entries``), never created. As with every use of the
    cache, closing it drops the entries that have expired.

    Returns
    -------
    CacheInfo
        The document ``kartograf-cache/1`` with ``action="info"``.

    Raises
    ------
    CacheError
        The database is unreadable (``clear_cache`` deletes it) or locked by
        another process.

    Examples
    --------
    >>> from kartograf.cache_info import get_cache_info
    >>> get_cache_info().action
    'info'
    """
    # these calls report the state of the cache themselves: no disabled-cache notice
    with open_cache(True, force=False, on_notice=_ignore) as cache:
        assert cache is not None
        stats = cache.stats()
        error = cache.error
        path = cache.db_path
    if error is not None:
        raise _unusable(path, error)
    if not stats["db_exists"]:
        return CacheInfo("info", path, False, None, None)
    entries = CacheEntries(
        records=stats["record_count"],
        campaigns=stats["campaign_count"],
        teryt=stats["teryt_count"],
        sheets=stats["sheet_count"],
        index_areas=stats["index_area_count"],
        atom_feeds=stats["atom_feed_count"],
    )
    return CacheInfo("info", path, True, stats["db_size_bytes"], entries)


def clear_cache() -> CacheInfo:
    """Empty the metadata cache of the current directory and reclaim its space.

    A missing database is not created. An unreadable one is deleted together
    with its ``-wal`` and ``-shm`` files (``removed_unreadable`` is then true):
    the next use creates a fresh cache.

    Returns
    -------
    CacheInfo
        The document ``kartograf-cache/1`` with ``action="clear"``; ``exists``
        and ``size_bytes`` describe the file after the operation.

    Raises
    ------
    CacheError
        The database is locked by another process (it is never deleted), or an
        unreadable file cannot be deleted.

    Examples
    --------
    >>> from kartograf.cache_info import clear_cache
    >>> clear_cache().cleared
    True
    """
    removed = False
    with open_cache(True, force=False, on_notice=_ignore) as cache:
        assert cache is not None
        path = cache.db_path
        cache.clear()
        cache.vacuum()
        error = cache.error
        if error is not None:
            if is_lock_error(error):
                # The file is fine, another process holds it: never delete it.
                raise _unusable(path, error)
            cache.close()
            _remove_unreadable(path)
            removed = True
    try:
        size: int | None = path.stat().st_size
    except FileNotFoundError:
        size = None
    return CacheInfo("clear", path, size is not None, size, None, True, removed)


def _ignore(_notice: Notice) -> None:
    """Drop the disabled-cache notice (the caller raises ``CacheError``)."""


def _unusable(path: Path, error: Exception) -> CacheError:
    """The error of a cache that cannot be used: locked, or unreadable."""
    if is_lock_error(error):
        return CacheError(
            f"cache zablokowany przez inny proces: {path} ({error}) - "
            "sprobuj ponownie po jego zakonczeniu",
            hint=_LOCKED_HINT,
        )
    return CacheError(
        f"cache nieczytelny: {path} ({error}) - uzyj `kartograf cache clear`"
    )


def _remove_unreadable(path: Path) -> None:
    """Delete an unreadable cache file with its ``-wal``/``-shm`` companions."""
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
        except OSError as e:
            raise CacheError(
                f"nie mozna usunac nieczytelnego pliku cache {candidate}: {e}",
                hint=_UNDELETABLE_HINT,
            ) from e
