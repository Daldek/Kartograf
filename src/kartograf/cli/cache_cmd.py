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
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language
from kartograf.messages import message


def _print_stats(info: CacheInfo) -> None:
    """Print the statistics of the cache.

    A database that does not exist yet has none.
    """
    entries = info.entries or CacheEntries(0, 0, 0, 0, 0, 0)
    print(message("cli.stats_header", lang=language()))
    print(message("cli.stats_records", lang=language(), records=entries.records))
    print(message("cli.stats_campaigns", lang=language(), campaigns=entries.campaigns))
    print(message("cli.stats_teryt", lang=language(), teryt=entries.teryt))
    print(message("cli.stats_sheets", lang=language(), sheets=entries.sheets))
    print(
        message(
            "cli.stats_index_areas", lang=language(), index_areas=entries.index_areas
        )
    )
    print(
        message("cli.stats_atom_feeds", lang=language(), atom_feeds=entries.atom_feeds)
    )
    db_size_kb = (info.size_bytes or 0) / 1024
    if not info.exists:
        print(message("cli.stats_size_no_file", lang=language()))
    elif db_size_kb < 1024:
        print(message("cli.stats_size_kb", lang=language(), db_size_kb=db_size_kb))
    else:
        print(message("cli.stats_size_mb", lang=language(), size_mb=db_size_kb / 1024))
    print(message("cli.stats_db_path", lang=language(), path=info.path))


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
            return emit_result(command_id(args), info)
        print(info.path)
        return 0
    info = clear_cache() if action == "clear" else get_cache_info()
    if wants_json(args):
        return emit_result(command_id(args), info)
    if action == "clear":
        if info.removed_unreadable:
            print(
                message("cli.clear_removed_unreadable", lang=language(), path=info.path)
            )
        elif not info.exists:
            print(message("cli.clear_cache_empty", lang=language(), path=info.path))
        else:
            print(message("cli.clear_done", lang=language()))
    else:
        _print_stats(info)
    return 0
