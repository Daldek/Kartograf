"""``soil download``, ``soil list-layers`` and ``soil hsg`` (ADR-044).

The CLI translates flags to the corresponding command-level API functions.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

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
from kartograf.cli.landcover_cmd import area_task_arguments
from kartograf.download.fetch import UpdateMode
from kartograf.download.options import output_required
from kartograf.exceptions import ValidationError
from kartograf.hydrology import calculate_hsg, check_hsg
from kartograf.hydrology.hsg import HSG_OUTPUT_FILES, HsgReport
from kartograf.landcover.manager import (
    LandCoverManager,
    SoilReport,
    check_soil,
    download_soil,
    soil_choices,
)


def soil_download_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``soil download`` and a project task."""
    return {
        **area_task_arguments(args),
        "property": args.property,
        "depth": args.depth,
        "stat": args.stat,
    }


def soil_hsg_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``soil hsg`` and a project task."""
    return {**area_task_arguments(args), "depth": args.depth}


def cmd_soil_download(args: argparse.Namespace) -> int:
    """``soil download``: one SoilGrids layer (property, depth, stat) of an area."""
    if args.output is None:
        raise ValidationError(output_required("soil"), option="output_dir")
    return run_with_plan_file(args, _soil_download)


def _soil_download(args: argparse.Namespace) -> int:
    arguments = {**soil_download_task_arguments(args), "output_dir": Path(args.output)}
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
    """A status line per file and the errors per unit of a SoilGrids report; the
    exit code."""
    out = Path(args.output)
    for item in report.files:
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
    for failure in report.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(report.stale)
    return 0 if report.ok else 1


def cmd_soil_list_layers(args: argparse.Namespace) -> int:
    """``soil list-layers``: properties, depths and statistics of SoilGrids."""
    # the catalogue of the source (no network, nothing written)
    provider: Any = LandCoverManager(".", "soilgrids", cache=False).provider
    print(f"Warstwy zrodla {provider.name}:")
    print()
    print("  Wlasciwosci gleb:")
    for prop in provider.get_available_properties():
        print(f"    {prop:11} - {provider.get_property_description(prop)}")
    print()
    depths = soil_choices()["depth"]
    print(f"  Glebokosci ({', '.join(dict.fromkeys(depths.values()))}):")
    for depth in depths:
        print(f"    {depth}")
    print()
    print("  Statystyki:")
    for stat, text in soil_choices()["stat"].items():
        print(f"    {stat:11} - {text}")
    print()
    print("  Wybor pobrania: --property, --depth, --stat.")
    return 0


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
    if args.output is None:
        raise ValidationError(
            f"--output wymagane: katalog magazynu ({HSG_OUTPUT_FILES})",
            option="output_dir",
        )

    selection = soil_hsg_task_arguments(args)
    return run_with_plan_file(args, lambda a: _hsg_task(a, selection))


def _hsg_task(args: argparse.Namespace, selection: dict) -> int:
    """One ``soil hsg`` request: plan or inputs plus the derived raster."""
    arguments = {**selection, "output_dir": Path(args.output)}
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
    """A status line per file, the errors per unit, the statistics of the raster
    (``--summary``) and the legend of an HSG report; the exit code."""
    out = Path(args.output)
    for item in (*result.inputs, *result.files):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    if result.summary is not None:
        _print_summary(result.summary)
    if result.files and not args.quiet:
        print()
        print("Legenda: 1=A (duza infiltracja), 2=B (umiarkowana),")
        print("         3=C (mala), 4=D (bardzo mala)")
        print("Metoda SCS-CN: HSG + uzytkowanie terenu -> Curve Number")
    return 0 if result.ok else 1


def _print_summary(summary: dict) -> None:
    """The statistics of the HSG raster (``report.summary``) as text."""
    print()
    print("Statystyki HSG obszaru zadania (grupy: % powierzchni z danymi):")
    groups = dict(summary)
    nodata = groups.pop("nodata")
    for group, data in groups.items():
        pct = data["percent"]
        area = data["area_ha"]
        print(f"  Grupa {group}: {pct:.1f}% ({area:.2f} ha)")
        print(f"           {data['description']}")
    print(
        f"  Brak danych: {nodata['percent']:.1f}% obszaru zadania "
        f"({nodata['area_ha']:.2f} ha)"
    )
    total = nodata["area_ha"] + sum(data["area_ha"] for data in groups.values())
    print(f"  Obszar zadania: {total:.2f} ha")
