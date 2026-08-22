"""
CLI commands for Kartograf — fasada zgodnosci.

Implementacje zyja w modulach _parser/parse_cmd/download_cmd/landcover_cmd/
soilgrids_cmd/cache_cmd; ten modul re-eksportuje publiczne nazwy i helpery
uzywane przez testy oraz utrzymuje entry point `main`
(pyproject: kartograf = "kartograf.cli.commands:main").
"""

import argparse
import os
import sys

from kartograf.cli._parser import create_parser
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.download_cmd import (
    _cmd_download_bbox,
    _cmd_download_geometry,
    _cmd_download_laz,
    _create_provider_and_storage,
    _download_godlo_list,
    _resolve_laz_bbox,
    _write_laz_sidecar,
    cmd_download,
    create_progress_callback,
)
from kartograf.cli.landcover_cmd import (
    cmd_landcover,
    cmd_landcover_download,
    cmd_landcover_list_layers,
    cmd_landcover_list_sources,
)
from kartograf.cli.parse_cmd import (
    cmd_parse,
    format_children,
    format_descendants,
    format_hierarchy,
    format_sheet_info,
)
from kartograf.cli.soilgrids_cmd import cmd_soilgrids, cmd_soilgrids_hsg
from kartograf.exceptions import KartografError

__all__ = [
    "create_parser",
    "main",
    "cmd_parse",
    "cmd_download",
    "cmd_landcover",
    "cmd_landcover_download",
    "cmd_landcover_list_layers",
    "cmd_landcover_list_sources",
    "cmd_soilgrids",
    "cmd_soilgrids_hsg",
    "cmd_cache",
    "create_progress_callback",
    "format_sheet_info",
    "format_hierarchy",
    "format_children",
    "format_descendants",
    "_create_provider_and_storage",
    "_download_godlo_list",
    "_cmd_download_bbox",
    "_cmd_download_laz",
    "_cmd_download_geometry",
    "_resolve_laz_bbox",
    "_write_laz_sidecar",
]


def _dispatch(parser: argparse.ArgumentParser, parsed_args: argparse.Namespace) -> int:
    """Rozeslij sparsowane argumenty do wlasciwej komendy."""
    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "parse":
        return cmd_parse(parsed_args)

    if parsed_args.command == "download":
        return cmd_download(parsed_args)

    if parsed_args.command == "landcover":
        return cmd_landcover(parsed_args)

    if parsed_args.command == "soilgrids":
        return cmd_soilgrids(parsed_args)

    if parsed_args.command == "cache":
        return cmd_cache(parsed_args)

    # Unknown command (shouldn't happen with argparse)
    print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
    return 1


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the CLI.

    Parameters
    ----------
    args : list[str], optional
        Command-line arguments (defaults to sys.argv[1:])

    Returns
    -------
    int
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    # argparse rzuca SystemExit dla --help/--version - ma przejsc bez zmian
    parsed_args = parser.parse_args(args)

    try:
        return _dispatch(parser, parsed_args)
    except KartografError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - last-resort barrier for the CLI user
        if os.environ.get("KARTOGRAF_DEBUG"):
            raise
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        print("Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
