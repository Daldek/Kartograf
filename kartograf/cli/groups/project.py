"""``kartograf project``: manage tasks and pinned store versions (ADR-040)."""

import argparse

from kartograf.cli._args import add_quiet, add_update_flags
from kartograf.cli.groups import add_group
from kartograf.cli.project_cmd import (
    cmd_project_add,
    cmd_project_download,
    cmd_project_init,
    cmd_project_remove,
    cmd_project_status,
    cmd_project_verify,
)


def _project_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        metavar="KATALOG",
        default=".",
        help="Katalog projektu (domyslnie biezacy katalog)",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the project subcommands with the top-level CLI."""
    commands = add_group(
        subparsers,
        "project",
        help="Projekt: zadania i przypiete wersje plikow w magazynie",
        description="Manifest projektu: zadania pobrania i przypiete wersje danych "
        "w jednym magazynie.",
    )

    init = commands.add_parser("init", help="Utworz manifest projektu i magazyn")
    _project_flag(init)
    init.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Katalog magazynu projektu (wymagany; bez domyslnej sciezki)",
    )
    init.set_defaults(_handler=cmd_project_init)

    add = commands.add_parser(
        "add",
        help="Dodaj zadanie z komendy danych (bez pobierania)",
        description="Dodaj zadanie: NAZWA <grupa> <komenda> [opcje komendy]. "
        "--project podaj przed NAZWA; opcje po NAZWA naleza do komendy danych.",
    )
    _project_flag(add)
    add.add_argument("name", metavar="NAZWA", help="Unikalna nazwa zadania")
    add.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        metavar="<grupa> <komenda> [opcje]",
        help="Komenda danych i jej opcje, np. elevation download --product nmt ...",
    )
    add.set_defaults(_handler=cmd_project_add)

    remove = commands.add_parser("remove", help="Usun zadanie (nie pliki magazynu)")
    _project_flag(remove)
    remove.add_argument("name", metavar="NAZWA", help="Nazwa zadania")
    remove.set_defaults(_handler=cmd_project_remove)

    download = commands.add_parser(
        "download", help="Pobierz, odtworz lub zaktualizuj zadania projektu"
    )
    _project_flag(download)
    add_update_flags(
        download,
        check_help="Sprawdz zrodla bez pobierania i bez zmiany przypiec",
        upgrade_help="Pobierz nowsze wersje i przepnij cale zadania",
        force_help="Pobierz ponownie i przepnij cale zadania",
    )
    add_quiet(download)
    download.add_argument(
        "tasks",
        nargs="*",
        metavar="NAZWA",
        help="Wybrane zadania (domyslnie wszystkie)",
    )
    download.set_defaults(_handler=cmd_project_download)

    for name, handler, help_text in (
        ("status", cmd_project_status, "Sprawdz obecnosc i rozmiar przypietych plikow"),
        ("verify", cmd_project_verify, "Sprawdz SHA-256 i sidecary przypietych plikow"),
    ):
        command = commands.add_parser(name, help=help_text)
        _project_flag(command)
        add_quiet(command)
        command.add_argument(
            "tasks",
            nargs="*",
            metavar="NAZWA",
            help="Wybrane zadania (domyslnie wszystkie)",
        )
        command.set_defaults(_handler=handler)
