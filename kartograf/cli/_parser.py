"""
Top-level parser of the Kartograf CLI (ADR-039).

``kartograf parse`` and ``kartograf cache`` are defined here; the data
groups (``elevation``, ``imagery``, ``landcover``, ``soil``, ...) register
themselves from ``kartograf/cli/groups/`` - one module per group. Flags
shared by the groups live in ``kartograf/cli/_args.py``.
"""

import argparse
import re
import sys
from collections.abc import Sequence
from typing import Any, NoReturn

from kartograf._version import build_version
from kartograf.cli.groups import register_groups


class _Parser(argparse.ArgumentParser):
    """``ArgumentParser`` without prefix abbreviations of long flags: a command
    line keeps its meaning when a group gains a flag (``--stat`` is never read
    as ``--stats``, ``--lay`` is no ambiguous prefix). Every subparser of the
    CLI is of this class (``add_subparsers`` uses the class of its parser)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


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


# ``--bbox -447000,...``: argparse takes a value starting with "-" after a
# space for a flag; four comma-separated numbers are always a --bbox value.
_BBOX_VALUE = re.compile(r"-?[0-9]+(\.[0-9]+)?(,-?[0-9]+(\.[0-9]+)?){3}")
# Usual mix-ups of a command with a flag of another group: the hint replaces
# the list of the commands having the flag.
_UNKNOWN_HINTS = {
    ("kartograf landcover download", "--product"): "landcover wybiera zrodlo "
    "flaga --source, np. --source bdot10k; lista: kartograf landcover list-sources",
    ("kartograf landcover download", "--country"): "kraj wynika z --source "
    "(np. zabaged, data50, data250 = CZ)",
    ("kartograf soil download", "--product"): "warstwe SoilGrids wybieraja "
    "--property, --depth i --stat; lista: kartograf soil list-layers",
    ("kartograf hydro download", "--sheet"): "obszar CZ: --bbox (np. z --bbox-crs "
    "EPSG:5514) albo --geometry",
}


def _join_bbox_values(argv: Sequence[str]) -> list[str]:
    """``--bbox -447000,...`` -> ``--bbox=-447000,...`` (negative coordinates,
    e.g. S-JTSK, after a space)."""
    joined: list[str] = []
    i = 0
    while i < len(argv):
        if (
            argv[i] == "--bbox"
            and i + 1 < len(argv)
            and _BBOX_VALUE.fullmatch(argv[i + 1])
        ):
            joined.append(f"--bbox={argv[i + 1]}")
            i += 2
            continue
        joined.append(argv[i])
        i += 1
    return joined


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    return next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )


def _command_parser(
    root: argparse.ArgumentParser, parsed: argparse.Namespace
) -> argparse.ArgumentParser:
    """The parser of the command of a parsed line (``kartograf elevation
    download``); the group or the root parser of a line without one."""
    current = root
    group = getattr(parsed, "command", None)
    names = (group, getattr(parsed, f"{group}_command", None) if group else None)
    for name in names:
        action = _subparsers(current)
        if name is None or action is None or name not in action.choices:
            break
        current = action.choices[name]
    return current


def _flag_owners(root: argparse.ArgumentParser, flag: str) -> str:
    """The commands having ``flag``: ``boundaries, cadastre download; soil hsg``."""
    by_command: dict[str, list[str]] = {}
    top = _subparsers(root)
    assert top is not None
    for group, group_parser in top.choices.items():
        commands = _subparsers(group_parser)
        parsers = (
            commands.choices.items() if commands is not None else [("", group_parser)]
        )
        for command, command_parser in parsers:
            if flag in command_parser._option_string_actions:
                by_command.setdefault(command, []).append(group)
    return "; ".join(
        f"{', '.join(groups)} {command}".strip()
        for command, groups in by_command.items()
    )


def _unknown_text(
    root: argparse.ArgumentParser, command: argparse.ArgumentParser, extras: list[str]
) -> str:
    """The input error of arguments a command does not have."""
    options = f"Opcje: {command.prog} --help"
    first = extras[0]
    flag = first.partition("=")[0]
    if not flag.startswith("-"):
        return f"nieznany argument {first}. {options}"
    hint = _UNKNOWN_HINTS.get((command.prog, flag))
    if hint is None:
        owners = _flag_owners(root, flag)
        hint = f"maja ja: {owners}" if owners else None
    return f"nieznana opcja {flag}" + (f" ({hint})" if hint else "") + f". {options}"


def parse_command_line(
    parser: argparse.ArgumentParser, argv: Sequence[str]
) -> argparse.Namespace:
    """``parser.parse_args(argv)`` with readable input errors (exit code 2).

    ``--bbox`` with negative coordinates after a space is joined with its
    value; an unknown flag is reported by the parser of the command (its
    usage) with the commands that have it, or a hint for the usual mix-ups
    (``landcover download --product``, ``soil download --product``, ...).
    ``kartograf`` and ``project add`` parse data command lines with it.
    """
    parsed, extras = parser.parse_known_args(_join_bbox_values(argv))
    if extras:
        command = _command_parser(parser, parsed)
        command.error(_unknown_text(parser, command, extras))
    return parsed


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    parser = _Parser(
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
