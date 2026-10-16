"""Project CLI: parse task commands and render the public project API results."""

import argparse
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

from kartograf import (
    FileCheck,
    ProjectCheck,
    add_project_task,
    check_project,
    download_project,
    init_project,
    open_project,
    project_status,
    remove_project_task,
    verify_project,
)
from kartograf.cli._parser import (
    create_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.cli.download_cmd import _print_notice, create_progress_callback
from kartograf.download.fetch import UpdateMode
from kartograf.exceptions import ValidationError
from kartograf.project.commands import data_commands_text, project_command


def cmd_project_init(args: argparse.Namespace) -> int:
    """Create a manifest and its store with the public API."""
    project = init_project(args.project, output_dir=args.output)
    print(f"Utworzono projekt: {project.directory / 'kartograf-project.json'}")
    print(f"Magazyn: {project.output_dir}")
    print(
        "Dodaj zadanie: "
        f"{project_command(args.project, 'add', 'NAZWA <grupa> download ...')}"
    )
    return 0


def _workers_given(tokens: list[str]) -> bool:
    """``-w``/``--workers`` among the tokens of a data command (also ``-w8``,
    ``--workers=8``): argparse cannot tell an explicit default."""
    return any(
        token in ("-w", "--workers")
        or token.startswith("--workers=")
        or (token.startswith("-w") and token[2:].isdigit())
        for token in tokens
    )


def cmd_project_add(args: argparse.Namespace) -> int:
    """Parse the unchanged data-group grammar after the project task name."""
    command_args = args.arguments
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]
    if any(arg == "--project" or arg.startswith("--project=") for arg in command_args):
        raise ValidationError("--project podaj przed nazwa zadania (przed NAZWA)")
    parser = create_parser()
    if not command_args:
        parser.error("podaj komende danych po nazwie zadania")
    removed = removed_command_error(command_args)
    if removed is not None:
        parser.error(removed)
    # Reject non-data commands before they demand their own (irrelevant) flags.
    if command_args[0] in ("parse", "cache") or (
        len(command_args) > 1
        and command_args[1] in ("list-sources", "list-layers", "availability")
    ):
        raise ValidationError(
            f"do projektu mozna dodac komendy zapisujace dane: {data_commands_text()}"
        )
    parsed = parse_command_line(parser, command_args)
    task = getattr(parsed, "_task", None)
    if task is None:
        raise ValidationError(
            f"do projektu mozna dodac komendy zapisujace dane: {data_commands_text()}"
        )
    command = f"{parsed.command} {getattr(parsed, f'{parsed.command}_command')}"
    for flag, enabled in (
        ("--check-updates", getattr(parsed, "check_updates", False)),
        ("--upgrade", getattr(parsed, "upgrade", False)),
        ("--force", getattr(parsed, "force", False)),
        ("--plan", getattr(parsed, "plan", None) is not None),
    ):
        if enabled:
            raise ValidationError(
                f"{flag} nie jest czescia zadania; aktualizacja projektu: "
                f"{project_command(args.project, 'download', '--upgrade', args.name)}"
            )
    if _workers_given(command_args):
        raise ValidationError(
            "--workers nie jest czescia zadania (opcja uruchomienia); rownolegle "
            "pobieranie: "
            f"{project_command(args.project, 'download', '--workers', 'N', args.name)}"
        )
    if getattr(parsed, "summary", False):
        raise ValidationError(
            "--summary nie jest czescia zadania (tylko wypisuje statystyki HSG "
            "po obliczeniu); usun --summary"
        )
    output = getattr(parsed, "output", None)
    if output is not None:
        store = open_project(args.project).output_dir
        if Path(output).resolve() != store.resolve():
            raise ValidationError(
                f"zadanie pobiera do magazynu projektu ({store}), a --output "
                f"wskazuje {Path(output).resolve()}; usun --output"
            )
    add_project_task(
        args.project, name=args.name, command=command, options=task(parsed)
    )
    print(
        f"Dodano zadanie {args.name} ({command}); pobierz: "
        f"{project_command(args.project, 'download', args.name)}"
    )
    return 0


def cmd_project_remove(args: argparse.Namespace) -> int:
    """Remove one task, leaving its store versions untouched."""
    remove_project_task(args.project, name=args.name)
    print(f"Usunieto zadanie {args.name}; pliki zostaly w magazynie")
    return 0


def _selected_tasks(args: argparse.Namespace) -> list[str] | None:
    return args.tasks or None


def _error(task: str, text: str) -> None:
    prefix = "" if text.startswith(f"{task}: ") else f"{task}: "
    print(f"Error: {prefix}{text}", file=sys.stderr)


def _file_count(count: int) -> str:
    if count == 1:
        noun = "plik"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        noun = "pliki"
    else:
        noun = "plikow"
    return f"{count} {noun}"


def _check_line(file: FileCheck, checking_updates: bool) -> str:
    """Polish status relative to the pin, never to the latest store alias."""
    if checking_updates:
        if file.status == "newer":
            status = f"nowsza: {file.available_label or 'nieznana'}"
            if file.pinned_label:
                status += f" (przypieta {file.pinned_label})"
        else:
            status = {
                "current": "aktualne",
                "added": "nowy plik w wyniku zadania",
                "removed": "poza wynikiem zadania",
                "unverifiable": "nie da sie sprawdzic bez pobrania (--force)",
                "missing": "brak przypietego pliku w magazynie",
                "check_failed": "blad sprawdzenia",
            }.get(file.status, file.status)
    else:
        status = {
            "ok": "ok",
            "missing": "brak przypietego pliku w magazynie",
            "corrupt": "uszkodzony przypiety plik",
        }.get(file.status, file.status)
    if file.detail and file.detail != status:
        status += f": {file.detail}"
    return f"{file.task}: {_unit_file(file.unit, file.path)}: {status}"


def _unit_file(unit: str, path: str) -> str:
    """Subject of a project line: the unit and its file name, ``CTES96
    (CTES96.jpg)`` - the files of one unit stay distinguishable."""
    return f"{unit} ({PurePosixPath(path).name})"


def _render_check(report: ProjectCheck, *, quiet: bool, checking_updates: bool) -> int:
    """Render API file statuses and report failures; notices stay on stderr."""
    if not quiet and not checking_updates:
        print(f"Projekt: {report.project.directory}")
        print(f"Magazyn: {report.project.output_dir}")
        selected = {file.task for file in report.files} | set(report.not_downloaded)
        for task in report.project.tasks:
            if task.name in selected and task.files:
                print(
                    f"{task.name}  {task.command}  {_file_count(len(task.files))}  "
                    f"przypiete {task.pinned_at}"
                )
    for name in report.not_downloaded:
        # a state, not an error: the exit code 1 says it (status -q || download)
        if not quiet:
            hint = project_command(report.project.directory, "download", name)
            print(f"{name}: nie pobrane (pobierz: {hint})")
    for file in report.files:
        line = _check_line(file, checking_updates)
        if file.status in ("check_failed", "missing", "corrupt"):
            print(f"Error: {line}", file=sys.stderr)
        elif not quiet:
            print(line)
    return 0 if report.ok else 1


def cmd_project_download(args: argparse.Namespace) -> int:
    """Use ``check_project`` in check mode; otherwise ``download_project``."""
    if args.check_updates:
        checked = check_project(
            args.project, tasks=_selected_tasks(args), on_notice=_print_notice
        )
        return _render_check(checked, quiet=args.quiet, checking_updates=True)
    mode: UpdateMode | None = (
        "upgrade" if args.upgrade else "force" if args.force else None
    )
    workers = args.workers if args.workers is not None else 4
    progress = create_progress_callback(args.quiet, workers=workers)
    report = download_project(
        args.project,
        tasks=_selected_tasks(args),
        update=mode,
        workers=args.workers,
        on_progress=progress,
        on_notice=_print_notice,
    )
    if getattr(progress, "pending", False):
        print()
    for result in report.tasks:
        for message in result.errors:
            _error(result.name, message)
        if not args.quiet:
            outcome = {
                "pinned": "przypieto",
                "restored": "odtworzono",
                "updated": "zaktualizowano",
                "unchanged": "bez zmian",
                "failed": "blad",
            }[result.outcome]
            line = f"{result.name}: {outcome}"
            if result.outcome in ("pinned", "restored"):
                line += f" ({_file_count(len(result.pinned))})"
            elif result.outcome == "updated":
                current = next(
                    task for task in report.project.tasks if task.name == result.name
                )
                line += f" ({_file_count(len(current.files))})"
            print(line)
            for pin in result.pinned:
                print(
                    f"{result.name}: {_unit_file(pin.unit, pin.path)}: "
                    f"przypieto {pin.label}"
                )
    if not args.quiet:
        counts = Counter(task.outcome for task in report.tasks)
        print(
            f"Projekt: przypiete {counts['pinned']}, odtworzone {counts['restored']}, "
            f"zaktualizowane {counts['updated']}, bez zmian {counts['unchanged']}, "
            f"bledy {counts['failed']}"
        )
    return 0 if report.ok else 1


def cmd_project_status(args: argparse.Namespace) -> int:
    """Fast local file presence and size check through the public API."""
    return _render_check(
        project_status(args.project, tasks=_selected_tasks(args)),
        quiet=args.quiet,
        checking_updates=False,
    )


def cmd_project_verify(args: argparse.Namespace) -> int:
    """Verify pinned bytes and sidecars through the public API."""
    return _render_check(
        verify_project(args.project, tasks=_selected_tasks(args)),
        quiet=args.quiet,
        checking_updates=False,
    )
