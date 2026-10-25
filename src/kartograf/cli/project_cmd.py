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
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.cli._parser import create_parser
from kartograf.cli.download_cmd import notice_printer, progress_printer
from kartograf.commands import CommandCall, parse_command
from kartograf.download.fetch import UpdateMode
from kartograf.envelope import exit_code_of
from kartograf.exceptions import ValidationError
from kartograf.messages import message
from kartograf.project.commands import project_command, task_command


def cmd_project_init(args: argparse.Namespace) -> int:
    """Create a manifest and its store with the public API."""
    project = init_project(args.project, root=args.root)
    if wants_json(args):
        return emit_result(command_id(args), project)
    print(
        message(
            "cli.project_created",
            lang=language(),
            path=project.directory / "kartograf-project.json",
        )
    )
    print(message("cli.project_store", lang=language(), root=project.root))
    print(
        message(
            "cli.project_add_task_hint",
            lang=language(),
            project_command=project_command(
                args.project, "add", message("cli.project_add_usage", lang=language())
            ),
        )
    )
    return 0


def _reject_run_options(args: argparse.Namespace, call: CommandCall) -> None:
    """Parse a task, the options of a data command.

    The flags of a run (``--upgrade``, ``--workers``...) and of the output
    (``--summary``, ``--quiet``, ``--json``, ``--root`` of another store) are an
    error, not a silently dropped value.
    """
    for flag, name in (
        ("--check", "check"),
        ("--upgrade", "upgrade"),
        ("--force", "force"),
        ("--plan", "plan"),
    ):
        if name in call.run:
            raise ValidationError(
                message(
                    "cli.run_option_upgrade",
                    flag=flag,
                    project_command=project_command(
                        args.project, "download", "--upgrade", args.name
                    ),
                ),
                option=name,
            )
    if "workers" in call.run:
        raise ValidationError(
            message(
                "cli.run_option_workers",
                project_command=project_command(
                    args.project, "download", "--workers", "N", args.name
                ),
            ),
            option="workers",
        )
    if "quiet" in call.run:
        raise ValidationError(
            message("cli.run_option_quiet"),
            option="quiet",
        )
    if "summary" in call.run:
        raise ValidationError(
            message("cli.run_option_summary"),
            option="summary",
        )
    if "json" in call.run:
        raise ValidationError(
            message(
                "cli.run_option_json",
                project_command=project_command(
                    args.project, "add", "--json", args.name, "..."
                ),
            ),
            option="json",
        )
    output = call.run.get("root")
    if output is not None:
        store = open_project(args.project).root
        if Path(str(output)).resolve() != store.resolve():
            raise ValidationError(
                message(
                    "cli.run_option_root",
                    store=store,
                    resolved_path=Path(str(output)).resolve(),
                ),
                option="root",
            )


def cmd_project_add(args: argparse.Namespace) -> int:
    """Read the data command after the task name and add it as a task.

    The command is read with ``parse_command``.
    """
    command_args = args.arguments
    if command_args and command_args[0] == "--":
        command_args = command_args[1:]
    if any(arg == "--project" or arg.startswith("--project=") for arg in command_args):
        raise ValidationError(message("cli.project_option_position"))
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
        return emit_result(command_id(args), project)
    print(
        message(
            "cli.project_task_added",
            lang=language(),
            name=args.name,
            command=call.command,
            project_command=project_command(args.project, "download", args.name),
        )
    )
    return 0


def cmd_project_remove(args: argparse.Namespace) -> int:
    """Remove one task, leaving its store versions untouched."""
    project = remove_project_task(args.project, name=args.name)
    if wants_json(args):
        return emit_result(command_id(args), project)
    print(message("cli.project_task_removed", lang=language(), name=args.name))
    return 0


def _selected_tasks(args: argparse.Namespace) -> list[str] | None:
    return args.tasks or None


def _error(task: str, text: str) -> None:
    prefix = "" if text.startswith(f"{task}: ") else f"{task}: "
    print(f"Error: {prefix}{text}", file=sys.stderr)


def _file_count(count: int) -> str:
    return message("cli.file_count", lang=language(), count=count)


def _check_line(file: FileCheck, checking: bool) -> str:
    """Return the status of a file relative to the pin, never to the latest alias."""
    status: str
    if checking:
        if file.status == "newer":
            status = message(
                "cli.status_newer",
                lang=language(),
                available_label=file.available_label
                or message("cli.status_unknown", lang=language()),
            )
            if file.pinned_label:
                status += message(
                    "cli.status_pinned", lang=language(), pinned_label=file.pinned_label
                )
        else:
            status = {
                "current": message("cli.status_current", lang=language()),
                "added": message("cli.status_added", lang=language()),
                "removed": message("cli.status_removed", lang=language()),
                "unverifiable": message("cli.status_unverifiable", lang=language()),
                "missing": message("cli.status_missing", lang=language()),
                "check_failed": message("cli.status_check_failed", lang=language()),
            }.get(file.status, file.status)
    else:
        status = {
            "ok": "ok",
            "missing": message("cli.status_missing", lang=language()),
            "corrupt": message("cli.status_corrupt", lang=language()),
        }.get(file.status, file.status)
    if file.detail and file.detail != status:
        status += f": {localized(file.detail)}"
    return f"{file.task}: {_unit_file(file.unit, file.path)}: {status}"


def _unit_file(unit: str, path: str) -> str:
    """Return the subject of a project line.

    The unit and its file name, ``CTES96 (CTES96.jpg)`` - the files of one unit stay
    distinguishable.
    """
    return f"{unit} ({PurePosixPath(path).name})"


def _render_check(report: ProjectCheck, *, quiet: bool, checking: bool) -> int:
    """Render API file statuses and report failures; notices stay on stderr."""
    if not quiet and not checking:
        print(
            message(
                "cli.project_directory",
                lang=language(),
                directory=report.project.directory,
            )
        )
        print(
            message(
                "cli.project_store",
                lang=language(),
                root=report.project.root,
            )
        )
        selected = {file.task for file in report.files} | set(report.not_downloaded)
        for task in report.project.tasks:
            if task.name in selected and task.files:
                print(
                    message(
                        "cli.task_pinned_line",
                        lang=language(),
                        name=task.name,
                        command=task.command,
                        file_count=_file_count(len(task.files)),
                        pinned_at=task.pinned_at,
                    )
                )
    for name in report.not_downloaded:
        # a state, not an error: the exit code 1 says it (status -q || download)
        if not quiet:
            hint = project_command(report.project.directory, "download", name)
            print(
                message(
                    "cli.task_not_downloaded", lang=language(), name=name, hint=hint
                )
            )
    for file in report.files:
        line = _check_line(file, checking)
        if file.status in ("check_failed", "missing", "corrupt"):
            print(f"Error: {line}", file=sys.stderr)
        elif not quiet:
            print(line)
    return exit_code_of(report, check=checking)


def _print_download(
    args: argparse.Namespace, report: ProjectReport, progress: object
) -> int:
    """Print the text of ``download_project``.

    A line per task and its pins, the errors, the totals; the exit code.
    """
    if getattr(progress, "pending", False):
        print()
    for result in report.tasks:
        for error in result.errors:
            _error(result.name, localized(error))
        if not args.quiet:
            outcome = {
                "pinned": message("cli.outcome_pinned", lang=language()),
                "restored": message("cli.outcome_restored", lang=language()),
                "updated": message("cli.outcome_updated", lang=language()),
                "unchanged": message("cli.status_unchanged", lang=language()),
                "failed": message("cli.outcome_failed", lang=language()),
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
                    message(
                        "cli.unit_file_pinned",
                        lang=language(),
                        name=result.name,
                        unit_file=_unit_file(pin.unit, pin.path),
                        label=pin.label,
                    )
                )
    if not args.quiet:
        counts = Counter(task.outcome for task in report.tasks)
        print(
            message(
                "cli.download_summary",
                lang=language(),
                counts_pinned=counts["pinned"],
                counts_restored=counts["restored"],
                counts_updated=counts["updated"],
                counts_unchanged=counts["unchanged"],
                counts_failed=counts["failed"],
            )
        )
    return exit_code_of(report)


def cmd_project_download(args: argparse.Namespace) -> int:
    """Use ``check_project`` in check mode; otherwise ``download_project``."""
    on_notice = notice_printer(args)
    if args.check:
        checked = check_project(
            args.project, tasks=_selected_tasks(args), on_notice=on_notice
        )
        if wants_json(args):
            return emit_result(command_id(args), checked, check=True)
        return _render_check(checked, quiet=args.quiet, checking=True)
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
        return emit_result(command_id(args), report)
    return _print_download(args, report, progress)


def _check(args: argparse.Namespace, report: ProjectCheck) -> int:
    """Return the result of ``status``/``verify``: the text or the document."""
    if wants_json(args):
        return emit_result(command_id(args), report)
    return _render_check(report, quiet=args.quiet, checking=False)


def cmd_project_status(args: argparse.Namespace) -> int:
    """Fast local file presence and size check through the public API."""
    return _check(args, get_project_status(args.project, tasks=_selected_tasks(args)))


def cmd_project_verify(args: argparse.Namespace) -> int:
    """Verify pinned bytes and sidecars through the public API."""
    return _check(args, verify_project(args.project, tasks=_selected_tasks(args)))
