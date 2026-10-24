"""``download`` of the collection groups.

The groups are ``boundaries``, ``cadastre``, ``models3d``, ``hydro``, ``names``,
``maps`` and ``geodesy``: flags ->
``download_collection``/``check_collection`` (ADR-037, ADR-042 D9).

The CLI only translates: ``library_arguments`` turns the flags of a group into
library arguments (the same conversion for every data command, from the
declaration of the command in the catalog), ``cmd_collection_download`` runs the
plan file cycle and prints one status line per file (its path below
``--output``), the failures and the data notices. Every data decision is in
``kartograf.download.collections``.
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._args import library_arguments
from kartograf.cli.download_cmd import (
    _end_progress,
    _plan_context,
    _present,
    _print_version_summary,
    _report_plan,
    _report_stale,
    _status_line,
    _unit_of,
    _update_mode,
    notice_printer,
    progress_printer,
    run_with_plan_file,
)
from kartograf.download.collections import (
    CollectionReport,
    check_collection,
    download_collection,
    require_collection_product,
)
from kartograf.download.fetch import UpdateMode
from kartograf.envelope import exit_code_of


def cmd_collection_download(args: argparse.Namespace, group: str) -> int:
    """Run ``<group> download``.

    The group's ``--product`` (a missing one names only the group's products), then the
    plan file cycle around one ``download_collection``/``check_collection`` call.
    """
    require_collection_product(args.product, group)
    return run_with_plan_file(args, _collection_download)


def _collection_download(args: argparse.Namespace) -> int:
    arguments = {**library_arguments(args), "output_dir": args.output}
    on_notice = notice_printer(args)
    if args.check_updates:
        return _report_plan(args, check_collection(**arguments, on_notice=on_notice))
    update = _update_mode(args)
    # a group whose request is always one file (hydro) has no --workers
    workers = getattr(args, "workers", 1)
    on_progress = progress_printer(args, workers)
    report = download_collection(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        workers=workers,
        on_progress=on_progress,
        on_notice=on_notice,
    )
    return _present(
        args, report, lambda: _print_collection(args, report, on_progress, update)
    )


def _print_collection(
    args: argparse.Namespace,
    report: CollectionReport,
    on_progress: object,
    update: UpdateMode | None,
) -> int:
    """Print status lines, summary, failures and stale positions of a report.

    It returns the exit code.
    """
    _end_progress(on_progress)
    output = Path(args.output)
    if not args.quiet:
        for item in report.files:
            print(_status_line(_unit_of(item.file.path, output), item.file, update))
        if len(report.files) + len(report.failed) > 1:
            _print_version_summary(
                [item.file.status for item in report.files],
                len(report.failed),
                output,
            )
    for failure in report.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(report.stale)
    return exit_code_of(report)
