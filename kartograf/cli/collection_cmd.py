"""
``download`` of the collection groups (``boundaries``, ``cadastre``,
``models3d``, ``hydro``, ``names``, ``maps``, ``geodesy``): flags ->
``download_collection``/``check_collection`` (ADR-037, ADR-042 D9).

The CLI only translates: ``collection_task`` turns the flags of a group
into library arguments (the same translation for the handler and for
``project add``), ``cmd_collection_download`` runs the plan file cycle and
prints one status line per file (its path below ``--output``), the
failures and the data notices. Every data decision is in
``kartograf.download.collections``.
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._args import parse_bbox_arg, parse_per_country
from kartograf.cli.download_cmd import (
    _plan_context,
    _print_notice,
    _print_version_summary,
    _report_plan,
    _report_stale,
    _status_line,
    _unit_of,
    _update_mode,
    run_with_plan_file,
)
from kartograf.download.collections import (
    check_collection,
    download_collection,
    require_collection_product,
)


def collection_task(args: argparse.Namespace) -> dict:
    """Data options of a collection download: the library arguments of the
    handler and of a project task (flags a group does not have stay unset)."""
    return {
        "product": args.product,
        "country": args.country,
        "teryt": getattr(args, "teryt", None),
        "ku": getattr(args, "ku", None),
        "sheet": getattr(args, "sheet", None),
        "bbox": parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        "geometry": Path(args.geometry) if args.geometry is not None else None,
        "layer": args.layer,
        "whole_country": getattr(args, "whole_country", False),
        "level": parse_per_country(getattr(args, "level", None), "--level"),
        "lod": getattr(args, "lod", None),
        "year": getattr(args, "year", None),
        "format": getattr(args, "format", None),
        "scale": getattr(args, "scale", None),
        "sheet_system": getattr(args, "sheet_system", None),
        "network": parse_per_country(getattr(args, "network", None), "--network"),
        "horizontal_crs": getattr(args, "horizontal_crs", None),
    }


def cmd_collection_download(args: argparse.Namespace, group: str) -> int:
    """``<group> download``: the group's ``--product`` (a missing one names
    only the group's products), then the plan file cycle around one
    ``download_collection``/``check_collection`` call."""
    require_collection_product(args.product, group)
    return run_with_plan_file(args, _collection_download)


def _collection_download(args: argparse.Namespace) -> int:
    arguments = {**collection_task(args), "output_dir": args.output}
    if args.check_updates:
        return _report_plan(
            args, check_collection(**arguments, on_notice=_print_notice)
        )
    update = _update_mode(args)
    report = download_collection(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        workers=args.workers,
        on_notice=_print_notice,
    )
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
    return 0 if report.ok else 1
