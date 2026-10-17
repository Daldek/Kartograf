"""``soil download``, ``soil list-layers`` and ``soil hsg`` (ADR-044).

The CLI translates flags to the corresponding command-level API functions.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from kartograf.cli.download_cmd import (
    _plan_context,
    _print_notice,
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    run_with_plan_file,
)
from kartograf.cli.landcover_cmd import area_task_arguments
from kartograf.download.options import output_required
from kartograf.hydrology import calculate_hsg, check_hsg, hsg_statistics
from kartograf.hydrology.hsg import HSG_OUTPUT_FILES
from kartograf.landcover.manager import (
    LandCoverManager,
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
        print(f"Error: {output_required('soil')}", file=sys.stderr)
        return 1
    return run_with_plan_file(args, _soil_download)


def _soil_download(args: argparse.Namespace) -> int:
    arguments = {**soil_download_task_arguments(args), "output_dir": Path(args.output)}
    if args.check_updates:
        return _report_plan(args, check_soil(**arguments, on_notice=_print_notice))
    update = _update_mode(args)
    report = download_soil(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        on_notice=_print_notice,
    )
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
        print(
            f"Error: --output wymagane: katalog magazynu ({HSG_OUTPUT_FILES})",
            file=sys.stderr,
        )
        return 1

    selection = soil_hsg_task_arguments(args)
    return run_with_plan_file(args, lambda a: _hsg_task(a, selection))


def _hsg_task(args: argparse.Namespace, selection: dict) -> int:
    """One ``soil hsg`` request: plan or inputs plus the derived raster."""
    arguments = {**selection, "output_dir": Path(args.output)}
    if args.check_updates:
        plan = check_hsg(**arguments, on_notice=_print_notice)
        return _report_plan(args, plan)
    update = _update_mode(args)
    result = calculate_hsg(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        on_notice=_print_notice,
    )
    out = Path(args.output)
    for item in (*result.inputs, *result.files):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    rc = 0 if result.ok else 1

    if args.summary and result.files:
        print()
        print("Statystyki HSG (procent grupy: z pikseli z danymi):")
        stats = hsg_statistics(result.files[0].file.path)
        nodata = stats.pop("nodata")
        for group, data in stats.items():
            pct = data["percent"]
            area = data["area_ha"]
            print(f"  Grupa {group}: {pct:.1f}% ({area:.2f} ha)")
            print(f"           {data['description']}")
        print(
            f"  Brak danych: {nodata['percent']:.1f}% calego obszaru "
            f"({nodata['area_ha']:.2f} ha)"
        )

    if result.files and not args.quiet:
        print()
        print("Legenda: 1=A (duza infiltracja), 2=B (umiarkowana),")
        print("         3=C (mala), 4=D (bardzo mala)")
        print("Metoda SCS-CN: HSG + uzytkowanie terenu -> Curve Number")
    return rc
