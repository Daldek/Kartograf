"""
``kartograf cache`` command group (stats, clear, path).
"""

import argparse
import sys
from pathlib import Path

from kartograf.cache.defaults import default_cache_path, open_cache


def _unreadable_message(path: Path, error: Exception) -> str:
    """``Error:`` line for ``stats``/``clear`` when the cache is unusable."""
    from kartograf.cache.metadata import is_lock_error

    if is_lock_error(error):
        return (
            f"Error: cache zablokowany przez inny proces: {path} ({error}) - "
            "sprobuj ponownie po jego zakonczeniu"
        )
    return f"Error: cache nieczytelny: {path} ({error}) - uzyj `kartograf cache clear`"


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
    from kartograf.cache.metadata import is_lock_error

    if args.cache_command is None:
        print("Uzycie: kartograf cache <komenda>")
        print("Komendy: stats, clear, path")
        print("Szczegoly: kartograf cache <komenda> --help")
        return 0

    # Reads and management calls never create a missing database. Ignore the
    # disabled-cache notice here: these commands report cache.error themselves.
    with open_cache(True, force=False, on_notice=lambda _notice: None) as cache:
        assert cache is not None
        if args.cache_command == "path":
            print(default_cache_path())
            return 0

        if args.cache_command == "stats":
            st = cache.stats()
            if cache.error is not None:
                print(_unreadable_message(cache.db_path, cache.error), file=sys.stderr)
                return 1
            print("Statystyki cache metadanych:")
            print(f"  Wpisy rekordow: {st['record_count']}")
            print(f"  Wpisy kampanii: {st['campaign_count']}")
            print(f"  Wpisy TERYT: {st['teryt_count']}")
            print(f"  Wpisy arkuszy: {st['sheet_count']}")
            db_size_kb = st["db_size_bytes"] / 1024
            if not st["db_exists"]:
                print("  Rozmiar bazy: - (plik jeszcze nie utworzony)")
            elif db_size_kb < 1024:
                print(f"  Rozmiar bazy: {db_size_kb:.1f} KB")
            else:
                print(f"  Rozmiar bazy: {db_size_kb / 1024:.1f} MB")
            print(f"  Sciezka bazy: {st['db_path']}")
            return 0

        if args.cache_command == "clear":
            cache.clear()
            cache.vacuum()
            if cache.error is None:
                print("Cache wyczyszczony.")
                return 0
            if is_lock_error(cache.error):
                # The file is fine, another process holds it: never delete it.
                print(_unreadable_message(cache.db_path, cache.error), file=sys.stderr)
                return 1
            cache.close()
            return _remove_unreadable(cache.db_path)

    return 0
