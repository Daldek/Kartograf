"""``kartograf project``: manage tasks and pinned store versions (ADR-040)."""

import argparse

from kartograf.cli._args import add_quiet, add_update_flags, examples
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

    init = commands.add_parser(
        "init",
        help="Utworz manifest projektu i magazyn",
        description="Utworz manifest projektu (kartograf-project.json "
        "w katalogu --project) wskazujacy magazyn --output; tworzy katalogi, "
        "ktorych nie ma. Jeden projekt = jeden magazyn; wiele projektow moze "
        "dzielic magazyn.",
        epilog=examples("kartograf project init --output ~/dane/kartograf"),
    )
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
        "--project podaj przed NAZWA; opcje po NAZWA naleza do komendy danych "
        "(bez --output i trybow aktualizacji). Wybory sprawdzane bez sieci, "
        "nic nie jest pobierane.",
        epilog=examples(
            "kartograf project add teren elevation download --product nmt "
            "--sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007",
            "kartograf project add gleby soil hsg --sheet N-34-130-D --depth 0-5cm",
        ),
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

    remove = commands.add_parser(
        "remove",
        help="Usun zadanie (nie pliki magazynu)",
        description="Usun zadanie i jego przypiecia z manifestu; pliki "
        "w magazynie zostaja.",
    )
    _project_flag(remove)
    remove.add_argument("name", metavar="NAZWA", help="Nazwa zadania")
    remove.set_defaults(_handler=cmd_project_remove)

    download = commands.add_parser(
        "download",
        help="Pobierz, odtworz lub zaktualizuj zadania projektu",
        description="Pobierz zadania projektu do magazynu i przypnij ich pliki "
        "(SHA-256). Zadanie z obecnymi przypietymi plikami zostaje bez zmian i "
        "bez zapytan do zrodla; brakujace pliki sa odtwarzane tylko przy "
        "zgodnej SHA-256. Zmiana przypiec: --upgrade albo --force.",
        epilog=examples(
            "kartograf project download",
            "kartograf project download --check-updates",
            "kartograf project download --upgrade teren",
        ),
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
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=None,
        help="Rownolegle pobieranie plikow w kazdym zadaniu (domyslnie jak "
        "w komendzie danych: elevation i imagery 4, pozostale 1; soil hsg bez "
        "rownoleglosci)",
    )
    download.add_argument(
        "tasks",
        nargs="*",
        metavar="NAZWA",
        help="Wybrane zadania (domyslnie wszystkie)",
    )
    download.set_defaults(_handler=cmd_project_download)

    for name, handler, help_text, description in (
        (
            "status",
            cmd_project_status,
            "Sprawdz obecnosc i rozmiar przypietych plikow",
            "Sprawdz bez sieci, czy przypiete pliki zadan sa w magazynie i maja "
            "przypiety rozmiar (szybko, bez czytania tresci); manifest bez "
            "zmian. Kod 1, gdy ktores zadanie nie jest pobrane albo brakuje "
            "przypietego pliku.",
        ),
        (
            "verify",
            cmd_project_verify,
            "Sprawdz SHA-256 i sidecary przypietych plikow",
            "Sprawdz bez sieci tresc przypietych plikow: czyta cale pliki "
            "i porownuje SHA-256 oraz sidecary wersji; manifest bez zmian. "
            "Kod 1 przy niezgodnosci.",
        ),
    ):
        command = commands.add_parser(name, help=help_text, description=description)
        _project_flag(command)
        add_quiet(command)
        command.add_argument(
            "tasks",
            nargs="*",
            metavar="NAZWA",
            help="Wybrane zadania (domyslnie wszystkie)",
        )
        command.set_defaults(_handler=handler)
