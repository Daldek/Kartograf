"""Project CLI: the commands of ``kartograf project`` on the public project API.

Every command is one library call (``init_project``, ``add_project_task``,
``remove_project_task``, ``download_project``, ``check_project``,
``get_project_status``, ``verify_project``); the CLI prints its result as text or,
with ``--json``, as the document of the library (``kartograf-project-state/1``,
``-report/1``, ``-check/1``). ``project add`` reads the data command after the
task name with ``parse_command`` (the parser of the command catalog).
"""

import argparse
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

from kartograf import (
    FileCheck,
    ProjectCheck,
    ProjectReport,
    add_project_task,
    check_project,
    download_project,
    get_project_status,
    init_project,
    open_project,
    remove_project_task,
    verify_project,
)
from kartograf.catalog.kinds import convert_arguments
from kartograf.cli._json import emit_document, wants_json
from kartograf.cli._parser import create_parser
from kartograf.cli.download_cmd import notice_printer, progress_printer
from kartograf.commands import CommandCall, parse_command
from kartograf.download.fetch import UpdateMode
from kartograf.exceptions import ValidationError
from kartograf.project.commands import project_command, task_command


def cmd_project_init(args: argparse.Namespace) -> int:
    """Create a manifest and its store with the public API."""
    project = init_project(args.project, output_dir=args.output)
    if wants_json(args):
        return emit_document(project)
    print(f"Utworzono projekt: {project.directory / 'kartograf-project.json'}")
    print(f"Magazyn: {project.output_dir}")
    print(
        "Dodaj zadanie: "
        f"{project_command(args.project, 'add', 'NAZWA <grupa> download ...')}"
    )
    return 0


def _reject_run_options(args: argparse.Namespace, call: CommandCall) -> None:
    """A task is the options of a data command: the flags of a run (``--upgrade``,
    ``--workers``...) and of the output (``--summary``, ``--json``, ``--output``
    of another store) are an error, not a silently dropped value."""
    for flag, name in (
        ("--check-updates", "check_updates"),
        ("--upgrade", "upgrade"),
        ("--force", "force"),
        ("--plan", "plan"),
    ):
        if name in call.run:
            raise ValidationError(
                f"{flag} nie jest czescia zadania; aktualizacja projektu: "
                f"{project_command(args.project, 'download', '--upgrade', args.name)}",
                option=name,
            )
    if "workers" in call.run:
        raise ValidationError(
            "--workers nie jest czescia zadania (opcja uruchomienia); rownolegle "
            "pobieranie: "
            f"{project_command(args.project, 'download', '--workers', 'N', args.name)}",
            option="workers",
        )
    if "summary" in call.run:
        raise ValidationError(
            "--summary nie jest czescia zadania (tylko wypisuje statystyki HSG "
            "po obliczeniu); usun --summary",
            option="summary",
        )
    if "json" in call.run:
        raise ValidationError(
            "--json nie jest czescia zadania (to tryb wyniku komendy project add); "
            "podaj go przed nazwa zadania: "
            f"{project_command(args.project, 'add', '--json', args.name, '...')}",
            option="json",
        )
    output = call.run.get("output_dir")
    if output is not None:
        store = open_project(args.project).output_dir
        if Path(str(output)).resolve() != store.resolve():
            raise ValidationError(
                f"zadanie pobiera do magazynu projektu ({store}), a --output "
                f"wskazuje {Path(str(output)).resolve()}; usun --output",
                option="output_dir",
            )


def cmd_project_add(args: argparse.Namespace) -> int:
    """Read the data command after the task name (``parse_command``) and add it
    as a task."""
    command_args = args.arguments
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]
    if any(arg == "--project" or arg.startswith("--project=") for arg in command_args):
        raise ValidationError("--project podaj przed nazwa zadania (przed NAZWA)")
    if any(arg in ("-h", "--help") for arg in command_args):
        # the help of the data command itself: argparse prints it and exits
        create_parser().parse_args(command_args)
    call = parse_command(command_args)
    _reject_run_options(args, call)
    project = add_project_task(
        args.project,
        name=args.name,
        command=call.command,
        options=convert_arguments(task_command(call.command).options, call.options),
    )
    if wants_json(args):
        return emit_document(project)
    print(
        f"Dodano zadanie {args.name} ({call.command}); pobierz: "
        f"{project_command(args.project, 'download', args.name)}"
    )
    return 0


def cmd_project_remove(args: argparse.Namespace) -> int:
    """Remove one task, leaving its store versions untouched."""
    project = remove_project_task(args.project, name=args.name)
    if wants_json(args):
        return emit_document(project)
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


def _print_download(args: argparse.Namespace, report: ProjectReport, progress) -> int:
    """The text of ``download_project``: a line per task and its pins, the
    errors, the totals; the exit code."""
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


def cmd_project_download(args: argparse.Namespace) -> int:
    """Use ``check_project`` in check mode; otherwise ``download_project``."""
    on_notice = notice_printer(args)
    if args.check_updates:
        checked = check_project(
            args.project, tasks=_selected_tasks(args), on_notice=on_notice
        )
        if wants_json(args):
            return emit_document(checked)
        return _render_check(checked, quiet=args.quiet, checking_updates=True)
    mode: UpdateMode | None = (
        "upgrade" if args.upgrade else "force" if args.force else None
    )
    workers = args.workers if args.workers is not None else 4
    progress = progress_printer(args, workers)
    report = download_project(
        args.project,
        tasks=_selected_tasks(args),
        update=mode,
        workers=args.workers,
        on_progress=progress,
        on_notice=on_notice,
    )
    if wants_json(args):
        return emit_document(report)
    return _print_download(args, report, progress)


def _check(args: argparse.Namespace, report: ProjectCheck) -> int:
    """The result of ``status``/``verify``: the text or the document."""
    if wants_json(args):
        return emit_document(report)
    return _render_check(report, quiet=args.quiet, checking_updates=False)


def cmd_project_status(args: argparse.Namespace) -> int:
    """Fast local file presence and size check through the public API."""
    return _check(args, get_project_status(args.project, tasks=_selected_tasks(args)))


def cmd_project_verify(args: argparse.Namespace) -> int:
    """Verify pinned bytes and sidecars through the public API."""
    return _check(args, verify_project(args.project, tasks=_selected_tasks(args)))
