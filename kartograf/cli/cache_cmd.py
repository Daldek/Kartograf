"""
``kartograf cache`` command group (stats, clear, path).

The commands are the library functions ``get_cache_info`` and ``clear_cache``:
the text is rendered from their document (``kartograf-cache/1``) and with
``--json`` the CLI prints that document. A cache that cannot be used is the
``CacheError`` of the library (``main`` reports it, exit code 1).
"""

import argparse

from kartograf.cache.defaults import default_cache_path
from kartograf.cache_info import CacheEntries, CacheInfo, clear_cache, get_cache_info
from kartograf.cli._json import emit_document, wants_json


def _print_stats(info: CacheInfo) -> None:
    """The statistics of the cache; a database that does not exist yet has none."""
    entries = info.entries or CacheEntries(0, 0, 0, 0, 0, 0)
    print("Statystyki cache metadanych:")
    print(f"  Wpisy rekordow: {entries.records}")
    print(f"  Wpisy kampanii: {entries.campaigns}")
    print(f"  Wpisy TERYT: {entries.teryt}")
    print(f"  Wpisy arkuszy: {entries.sheets}")
    print(f"  Wpisy obszarow skorowidza: {entries.index_areas}")
    print(f"  Indeksy feedow ATOM: {entries.atom_feeds}")
    db_size_kb = (info.size_bytes or 0) / 1024
    if not info.exists:
        print("  Rozmiar bazy: - (plik jeszcze nie utworzony)")
    elif db_size_kb < 1024:
        print(f"  Rozmiar bazy: {db_size_kb:.1f} KB")
    else:
        print(f"  Rozmiar bazy: {db_size_kb / 1024:.1f} MB")
    print(f"  Sciezka bazy: {info.path}")


def cmd_cache(args: argparse.Namespace, action: str) -> int:
    """
    Execute a cache management command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments
    action : {"stats", "clear", "path"}
        The command; ``stats`` and ``path`` are ``get_cache_info``, ``clear``
        is ``clear_cache``.

    Returns
    -------
    int
        Exit code (0 for success; an unusable cache is the ``CacheError`` that
        ``main`` reports).
    """
    if action == "path" and not wants_json(args):
        # only the path: it is known (and printed) when the database is unreadable
        print(default_cache_path())
        return 0
    info = clear_cache() if action == "clear" else get_cache_info()
    if wants_json(args):
        return emit_document(info)
    if action == "clear":
        print(
            f"Usunieto nieczytelny plik cache: {info.path}"
            if info.removed_unreadable
            else "Cache wyczyszczony."
        )
    else:
        _print_stats(info)
    return 0
