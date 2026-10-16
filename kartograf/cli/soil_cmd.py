"""
``soil download``, ``soil list-layers`` and ``soil hsg`` (Z1).

SoilGrids layers go through ``LandCoverManager`` (``run_land_cover``), the
HSG through ``HSGCalculator``; the CLI translates flags and prints results.
"""

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
from kartograf.cli.landcover_cmd import area_task_arguments, run_land_cover
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.landcover.manager import LandCoverManager

if TYPE_CHECKING:
    from kartograf.hydrology import HSGCalculator


def _soil_download_options(args: argparse.Namespace) -> dict:
    options: dict = {}
    for name in ("property", "depth", "stat"):
        value = getattr(args, name)
        if value is not None:
            options[name] = value
    return options


def soil_download_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``soil download`` and a project task."""
    return {**area_task_arguments(args), **_soil_download_options(args)}


def soil_hsg_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``soil hsg`` and a project task."""
    return {**area_task_arguments(args), "depth": args.depth}


def cmd_soil_download(args: argparse.Namespace) -> int:
    """``soil download``: one SoilGrids layer (property, depth, stat) of an area."""
    if args.output is None:
        print(
            "Error: --output wymagane: katalog magazynu (pliki w <KATALOG>/soil/...)",
            file=sys.stderr,
        )
        return 1
    options = _soil_download_options(args)
    return run_land_cover(args, "soilgrids", options)


def cmd_soil_list_layers(args: argparse.Namespace) -> int:
    """``soil list-layers``: properties, depths and statistics of SoilGrids."""
    # the catalogue of the source (no network, nothing written)
    provider: Any = LandCoverManager(".", "soilgrids", cache=False).provider
    print(f"Warstwy zrodla {provider.name}:")
    print()
    print("  Wlasciwosci gleb:")
    for prop in provider.get_available_properties():
        print(f"    {prop:10} - {provider.get_property_description(prop)}")
    print()
    print("  Glebokosci:")
    for depth in provider.get_available_depths():
        print(f"    {depth}")
    print()
    print("  Statystyki:")
    for stat in provider.get_available_stats():
        print(f"    {stat}")
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
            "Error: --output wymagane: katalog magazynu (wejscia w <KATALOG>/soil/..., "
            "HSG w <KATALOG>/hsg/...)",
            file=sys.stderr,
        )
        return 1

    from kartograf.hydrology import HSGCalculator

    selection = soil_hsg_task_arguments(args)
    calc = HSGCalculator(Path(args.output))

    try:
        return run_with_plan_file(args, lambda a: _hsg_task(a, calc, selection))
    except (DownloadError, ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _hsg_task(args: argparse.Namespace, calc: "HSGCalculator", selection: dict) -> int:
    """One ``soil hsg`` request: a plan (``--check-updates``) or the inputs
    and the HSG with one status line each (spec 4.5)."""
    if args.check_updates:
        plan = calc.check_hsg(**selection, on_notice=_print_notice)
        return _report_plan(args, plan)
    update = _update_mode(args)
    result = calc.calculate_hsg(
        **selection,
        update=update,
        plan=_plan_context(args).loaded,
        on_notice=_print_notice,
    )
    out = Path(args.output)
    for item in result.inputs:
        if item.file is not None:
            _report_file(args, _unit_of(item.file.path, out), item.file, update)
    if result.file is not None:
        _report_file(args, _unit_of(result.file.path, out), result.file, update)
    _report_stale(result.stale)
    rc = 0 if result.ok else 1

    if args.summary and result.file is not None:
        print()
        print("Statystyki HSG (procent grupy: z pikseli z danymi):")
        stats = calc.get_hsg_statistics(result.file.path)
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

    if not args.quiet:
        print()
        print("Legenda: 1=A (duza infiltracja), 2=B (umiarkowana),")
        print("         3=C (mala), 4=D (bardzo mala)")
        print("Metoda SCS-CN: HSG + uzytkowanie terenu -> Curve Number")
    return rc
