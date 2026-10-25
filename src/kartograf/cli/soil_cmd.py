"""``soil download`` and ``soil hsg`` (ADR-044).

``soil list-layers`` is in ``layers_cmd``.

The CLI translates flags to the corresponding command-level API functions.
"""

import argparse
import sys
from typing import Any

from kartograf.cli._args import library_arguments, store_dir
from kartograf.cli._language import language, localized
from kartograf.cli.download_cmd import (
    _plan_context,
    _present,
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    notice_printer,
    run_with_plan_file,
)
from kartograf.download.fetch import UpdateMode
from kartograf.envelope import exit_code_of
from kartograf.hydrology import calculate_hsg, check_hsg
from kartograf.hydrology.hsg import HsgReport
from kartograf.landcover.manager import SoilReport, check_soil, download_soil
from kartograf.messages import message


def cmd_soil_download(args: argparse.Namespace) -> int:
    """``soil download``: one SoilGrids layer (property, depth, stat) of an area."""
    return run_with_plan_file(args, _soil_download)


def _soil_download(args: argparse.Namespace) -> int:
    arguments = {**library_arguments(args), "root": store_dir(args)}
    on_notice = notice_printer(args)
    if args.check_updates:
        return _report_plan(args, check_soil(**arguments, on_notice=on_notice))
    update = _update_mode(args)
    report = download_soil(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        on_notice=on_notice,
    )
    return _present(args, report, lambda: _print_soil(args, report, update))


def _print_soil(
    args: argparse.Namespace, report: SoilReport, update: UpdateMode | None
) -> int:
    """Print a status line per file and the errors per unit of a SoilGrids report.

    It returns the exit code.
    """
    out = store_dir(args)
    for item in report.files:
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
    for failure in report.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(report.stale)
    return exit_code_of(report)


def cmd_soil_hsg(args: argparse.Namespace) -> int:
    """
    ``soil hsg``: hydrologic soil groups from SoilGrids clay, sand and silt.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    selection = library_arguments(args)
    return run_with_plan_file(args, lambda a: _hsg_task(a, selection))


def _hsg_task(args: argparse.Namespace, selection: dict[str, Any]) -> int:
    """One ``soil hsg`` request: plan or inputs plus the derived raster."""
    arguments = {**selection, "root": store_dir(args)}
    on_notice = notice_printer(args)
    if args.check_updates:
        return _report_plan(args, check_hsg(**arguments, on_notice=on_notice))
    update = _update_mode(args)
    result = calculate_hsg(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        summary=args.summary,
        on_notice=on_notice,
    )
    return _present(args, result, lambda: _print_hsg(args, result, update))


def _print_hsg(
    args: argparse.Namespace, result: HsgReport, update: UpdateMode | None
) -> int:
    """Print a status line per file, the errors per unit, the statistics and the legend.

    The statistics of the raster (``--summary``) and the legend are for an HSG report;
    the exit code is returned.
    """
    out = store_dir(args)
    for item in (*result.inputs, *result.files):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    if result.summary is not None:
        _print_summary(result.summary)
    if result.files and not args.quiet:
        print()
        print(message("cli.hsg_legend_first", lang=language()))
        print(message("cli.hsg_legend_second", lang=language()))
        print(message("cli.hsg_scs_cn_method", lang=language()))
    return exit_code_of(result)


def _print_summary(summary: dict[str, Any]) -> None:
    """Print the statistics of the HSG raster (``report.summary``) as text."""
    print()
    print(message("cli.hsg_statistics_header", lang=language()))
    groups = dict(summary)
    nodata = groups.pop("nodata")
    for group, data in groups.items():
        pct = data["percent"]
        area = data["area_ha"]
        print(
            message(
                "cli.hsg_group_line",
                lang=language(),
                group=group,
                percent=pct,
                area_ha=area,
            )
        )
        print(f"           {localized(data['description'])}")
    print(
        message(
            "cli.hsg_nodata_area",
            lang=language(),
            nodata_percent=nodata["percent"],
            nodata_area_ha=nodata["area_ha"],
        )
    )
    total = nodata["area_ha"] + sum(data["area_ha"] for data in groups.values())
    print(message("cli.hsg_task_area_total", lang=language(), total=total))
