"""
``kartograf cache`` command group (stats, clear, path).
"""

import argparse


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

    cache = MetadataCache()

    try:
        if args.cache_command == "path":
            print(cache.stats()["db_path"])
            return 0

        if args.cache_command == "stats":
            st = cache.stats()
            print("Metadata cache statistics:")
            print(f"  Record entries: {st['record_count']}")
            print(f"  TERYT entries: {st['teryt_count']}")
            print(f"  Sheet entries: {st['sheet_count']}")
            db_size_kb = st["db_size_bytes"] / 1024
            if db_size_kb < 1024:
                print(f"  Database size: {db_size_kb:.1f} KB")
            else:
                print(f"  Database size: {db_size_kb / 1024:.1f} MB")
            print(f"  Database path: {st['db_path']}")
            return 0

        if args.cache_command == "clear":
            cache.clear()
            cache.vacuum()
            print("Cache cleared.")
            return 0

    finally:
        cache.close()

    return 0
