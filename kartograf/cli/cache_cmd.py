"""
``kartograf cache`` command group (stats, clear, path).
"""

import argparse
import sys
from pathlib import Path


def _unreadable_message(path: Path, error: Exception) -> str:
    """``Error:`` line for ``stats``/``clear`` when the cache is unusable."""
    from kartograf.cache.metadata import is_lock_error

    if is_lock_error(error):
        return (
            f"Error: cache zablokowany przez inny proces: {path} ({error}) — "
            "sprobuj ponownie po jego zakonczeniu"
        )
    return f"Error: cache nieczytelny: {path} ({error}) — uzyj `kartograf cache clear`"


def _remove_unreadable(path: Path) -> int:
    """Delete an unreadable cache file with its ``-wal``/``-shm`` companions."""
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
        except OSError as e:
            print(
                f"Error: nie mozna usunac nieczytelnego pliku cache {candidate}: {e}",
                file=sys.stderr,
            )
            return 1
    print(f"Usunieto nieczytelny plik cache: {path}")
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    """
    Execute cache management commands.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    from kartograf.cache import MetadataCache

    if args.cache_command is None:
        print("Usage: kartograf cache <command>")
        print("Commands: stats, clear, path")
        print("Run 'kartograf cache <command> --help' for details")
        return 0

    from kartograf.cache.metadata import is_lock_error

    # MetadataCache opens the database lazily: none of these subcommands
    # creates the file when it does not exist yet. An SQLite error disables
    # the cache silently here (no-op callback) - the subcommands report it
    # themselves via cache.error.
    cache = MetadataCache(on_disabled=lambda _message: None)

    try:
        if args.cache_command == "path":
            print(cache.db_path)
            return 0

        if args.cache_command == "stats":
            st = cache.stats()
            if cache.error is not None:
                print(_unreadable_message(cache.db_path, cache.error), file=sys.stderr)
                return 1
            print("Metadata cache statistics:")
            print(f"  Record entries: {st['record_count']}")
            print(f"  Campaign entries: {st['campaign_count']}")
            print(f"  TERYT entries: {st['teryt_count']}")
            print(f"  Sheet entries: {st['sheet_count']}")
            db_size_kb = st["db_size_bytes"] / 1024
            if not st["db_exists"]:
                print("  Database size: - (file not created yet)")
            elif db_size_kb < 1024:
                print(f"  Database size: {db_size_kb:.1f} KB")
            else:
                print(f"  Database size: {db_size_kb / 1024:.1f} MB")
            print(f"  Database path: {st['db_path']}")
            return 0

        if args.cache_command == "clear":
            cache.clear()
            cache.vacuum()
            if cache.error is None:
                print("Cache cleared.")
                return 0
            if is_lock_error(cache.error):
                # the file is fine, another process holds it: never delete it
                print(_unreadable_message(cache.db_path, cache.error), file=sys.stderr)
                return 1
            cache.close()
            return _remove_unreadable(cache.db_path)

    finally:
        cache.close()

    return 0
