"""
Top-level parser of the Kartograf CLI (ADR-039).

``kartograf parse`` and ``kartograf cache`` are defined here; the data
groups (``elevation``, ``imagery``, ``landcover``, ``soil``, ...) register
themselves from ``kartograf/cli/groups/`` - one module per group. Flags
shared by the groups live in ``kartograf/cli/_args.py``.
"""

import argparse
import sys
from collections.abc import Sequence
from typing import Any, NoReturn

from kartograf._version import build_version
from kartograf.cli.groups import register_groups


class _LazyVersionAction(argparse.Action):
    """``--version`` resolving the build identifier only when requested."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            option_strings, dest=dest, default=argparse.SUPPRESS, nargs=0, **kwargs
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        sys.stdout.write(f"{parser.prog} {build_version()}\n")
        parser.exit()


# Commands removed in 0.8.0 (ADR-039): an input error naming the new command,
# never a working alias.
_REMOVED_COMMANDS = {
    "download": "kartograf elevation download (--product nmt, nmpt, laz) "
    "albo kartograf imagery download (--product orto)",
    "soilgrids": "kartograf soil hsg (grupy HSG) albo kartograf soil download "
    "(wlasciwosci SoilGrids)",
}


def _source_value(argv: Sequence[str]) -> str | None:
    """The ``--source``/``-s`` value of a command line (``None`` if absent)."""
    for i, arg in enumerate(argv):
        if arg.startswith("--source="):
            return arg.partition("=")[2]
        if arg in ("--source", "-s") and i + 1 < len(argv):
            return argv[i + 1]
    return None


def removed_command_error(argv: Sequence[str]) -> str | None:
    """Error text for a command line of a command removed in 0.8.0.

    ``kartograf download``, ``kartograf soilgrids ...`` and ``kartograf
    landcover ... --source soilgrids`` name their replacement; ``None`` for
    every other command line (argparse handles it).
    """
    if not argv:
        return None
    command = argv[0]
    if command in _REMOVED_COMMANDS:
        return (
            f"komenda '{command}' usunieta w 0.8.0 - uzyj {_REMOVED_COMMANDS[command]}"
        )
    if command == "landcover" and _source_value(argv[1:]) == "soilgrids":
        return (
            "SoilGrids jest w grupie soil od 0.8.0 - uzyj kartograf soil download "
            "albo kartograf soil list-layers"
        )
    return None


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="kartograf",
        description=(
            "Pobieranie danych przestrzennych z GUGiK (PL), CUZK (CZ), Copernicus "
            "i ISRIC. Komendy danych sa w grupach wg typu danych: kazda grupa ma "
            "podkomendy download i list-sources."
        ),
        epilog=(
            "Przyklad: kartograf elevation download --product nmt --sheet "
            "N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./data. "
            "Opcje komendy: kartograf <grupa> <komenda> --help"
        ),
    )

    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        help="pokaz wersje programu i zakoncz",
    )

    subparsers = parser.add_subparsers(dest="command", help="Komendy")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Rozpoznaj godlo arkusza i pokaz jego wlasciwosci",
        description="Rozpoznaj godlo arkusza i pokaz jego wlasciwosci",
    )
    parse_parser.add_argument(
        "sheet",
        metavar="GODLO",
        type=str.strip,
        help="Godlo arkusza (np. N-34-130-D, N-34-130-D-d-2-4)",
    )
    parse_parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="Pokaz hierarchie od arkusza do skali 1:1000000",
    )
    parse_parser.add_argument(
        "--children",
        action="store_true",
        help="Pokaz bezposrednie arkusze potomne",
    )
    parse_parser.add_argument(
        "--descendants",
        metavar="SKALA",
        help="Pokaz wszystkie arkusze potomne do skali docelowej (np. 1:10000)",
    )

    register_groups(subparsers)

    # Cache command group
    cache_parser = subparsers.add_parser(
        "cache",
        help="Zarzadzaj cache metadanych",
        description=(
            "Lokalny cache metadanych SQLite (odpowiedzi WMS, TERYT, indeks "
            "arkuszy CUZK)"
        ),
    )
    cache_parser.set_defaults(_group_parser=cache_parser)
    cache_subparsers = cache_parser.add_subparsers(
        dest="cache_command",
        title="komendy",
        metavar="KOMENDA",
    )

    cache_subparsers.add_parser(
        "stats",
        help="Pokaz statystyki cache (liczby wpisow, rozmiar bazy)",
    )

    cache_subparsers.add_parser(
        "clear",
        help="Usun wszystkie wpisy cache",
    )

    cache_subparsers.add_parser(
        "path",
        help="Pokaz sciezke pliku bazy cache",
    )

    return parser
