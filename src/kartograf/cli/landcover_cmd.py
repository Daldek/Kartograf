"""``landcover download`` (ADR-037, ADR-044).

``landcover list-layers`` is in ``layers_cmd``.

The CLI translates flags to ``download_landcover`` / ``check_landcover``.
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
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    notice_printer,
    progress_printer,
    run_with_plan_file,
)
from kartograf.download.fetch import UpdateMode
from kartograf.download.options import output_required
from kartograf.envelope import exit_code_of
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import (
    LandCoverReport,
    check_landcover,
    download_landcover,
    require_landcover_product,
)

# Sources whose area is several TERYT unit packages (summary line).
_UNIT_SOURCES = ("bdot10k", "bdoo")


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """``landcover download``: flags -> ``download_landcover``/``check_landcover``."""
    require_landcover_product(args.product)
    if args.root is None:
        raise ValidationError(output_required("landcover"), option="root")
    return run_with_plan_file(args, _landcover_task)


def _landcover_task(args: argparse.Namespace) -> int:
    """Plan or download: the report as text or, with ``--json``, as a document."""
    arguments = {**library_arguments(args), "root": Path(args.root)}
    on_notice = notice_printer(args)
    if args.check_updates:
        return _report_plan(args, check_landcover(**arguments, on_notice=on_notice))
    update = _update_mode(args)
    on_progress = progress_printer(args, args.workers)
    result = download_landcover(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        workers=args.workers,
        on_notice=on_notice,
        on_progress=on_progress,
    )
    return _present(
        args, result, lambda: _print_landcover(args, result, on_progress, update)
    )


def _print_landcover(
    args: argparse.Namespace,
    result: LandCoverReport,
    on_progress: object,
    update: UpdateMode | None,
) -> int:
    """Print a status line per file, the errors per unit and the summary.

    It is for a land cover report and returns the exit code.
    """
    _end_progress(on_progress)
    out = Path(args.root)
    statuses = []
    for item in (*result.files, *result.raw):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
        statuses.append(item.file.status)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    if args.product in _UNIT_SOURCES and args.teryt is None and not args.quiet:
        _print_version_summary(statuses, len(result.failed), out)
    return exit_code_of(result)
