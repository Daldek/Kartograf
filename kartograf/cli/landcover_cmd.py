"""``landcover download`` (ADR-037, ADR-044); ``landcover list-layers`` is in
``layers_cmd``.

The CLI translates flags to ``download_landcover`` / ``check_landcover``.
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._args import parse_bbox_arg
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
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import (
    LandCoverReport,
    check_landcover,
    download_landcover,
    require_landcover_product,
)

# Sources whose area is several TERYT unit packages (summary line).
_UNIT_SOURCES = ("bdot10k", "bdoo")


def area_task_arguments(args: argparse.Namespace) -> dict:
    """Shared area selection for land cover, SoilGrids and HSG tasks."""
    return {
        "sheet": args.sheet,
        "bbox": parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        "geometry": Path(args.geometry) if args.geometry is not None else None,
        "layer": args.layer,
    }


def landcover_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``landcover download`` and ``project add``."""
    return {
        "product": args.product,
        "teryt": args.teryt,
        **area_task_arguments(args),
        "year": args.year,
        "format": args.format,
        "layers": args.layers,
        "keep_raw": args.keep_raw,
        "whole_country": args.whole_country,
        "horizontal_crs": args.horizontal_crs,
    }


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """``landcover download``: flags -> ``download_landcover``/``check_landcover``."""
    require_landcover_product(args.product)
    if args.output is None:
        raise ValidationError(output_required("landcover"), option="output_dir")
    return run_with_plan_file(args, _landcover_task)


def _landcover_task(args: argparse.Namespace) -> int:
    """Plan or download: the report as text or, with ``--json``, as a document."""
    arguments = {**landcover_task_arguments(args), "output_dir": Path(args.output)}
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
    on_progress,
    update: UpdateMode | None,
) -> int:
    """A status line per file, the errors per unit and the summary of a land cover
    report; the exit code."""
    _end_progress(on_progress)
    out = Path(args.output)
    statuses = []
    for item in (*result.files, *result.raw):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
        statuses.append(item.file.status)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    if args.product in _UNIT_SOURCES and args.teryt is None and not args.quiet:
        _print_version_summary(statuses, len(result.failed), out)
    return 0 if result.ok else 1
