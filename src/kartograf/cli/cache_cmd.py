"""
``kartograf cache`` command group (stats, clear, path).

The commands are the library functions ``get_cache_info``, ``clear_cache`` and
``get_cache_path``: the text is rendered from their document
(``kartograf-cache/1``) and with ``--json`` the CLI prints that document. A cache
that cannot be used is the ``CacheError`` of the library (``main`` reports it,
exit code 1); ``path`` does not open the database, so it works then, too.
"""

import argparse

from kartograf.cache_info import (
    CacheEntries,
    CacheInfo,
    clear_cache,
    get_cache_info,
    get_cache_path,
)
from kartograf.cli._json import emit_document, wants_json


def _print_stats(info: CacheInfo) -> None:
    """Print the statistics of the cache.

    A database that does not exist yet has none.
    """
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
        The command: ``get_cache_info``, ``clear_cache`` or ``get_cache_path``.

    Returns
    -------
    int
        Exit code (0 for success; an unusable cache is the ``CacheError`` that
        ``main`` reports, except for ``path``, which never opens the database).
    """
    if action == "path":
        info = get_cache_path()
        if wants_json(args):
            return emit_document(info)
        print(info.path)
        return 0
    info = clear_cache() if action == "clear" else get_cache_info()
    if wants_json(args):
        return emit_document(info)
    if action == "clear":
        if info.removed_unreadable:
            print(f"Usunieto nieczytelny plik cache: {info.path}")
        elif not info.exists:
            print(f"Cache jest pusty: nie ma pliku cache ({info.path})")
        else:
            print("Cache wyczyszczony.")
    else:
        _print_stats(info)
    return 0
