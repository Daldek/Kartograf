"""
``kartograf soilgrids`` command group (HSG calculation).
"""

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from kartograf.cli._parser import parse_bbox_arg
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
from kartograf.download.plan import PlanItem
from kartograf.exceptions import DownloadError, ParseError, ValidationError

if TYPE_CHECKING:
    from kartograf.hydrology import HSGCalculator


def cmd_soilgrids(args: argparse.Namespace) -> int:
    """
    Execute soilgrids commands.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    if args.soilgrids_command is None:
        print("Usage: kartograf soilgrids <command>")
        print("Commands: hsg")
        print("Run 'kartograf soilgrids <command> --help' for details")
        return 0

    if args.soilgrids_command == "hsg":
        return cmd_soilgrids_hsg(args)

    return 0


def cmd_soilgrids_hsg(args: argparse.Namespace) -> int:
    """
    Execute soilgrids HSG calculation command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    missing = []
    if args.output is None:
        missing.append(
            "--output wymagane: katalog magazynu (wejscia w <DIR>/soil/..., "
            "HSG w <DIR>/hsg/...)"
        )
    if args.depth is None:
        missing.append(
            "--depth wymagane: 0-5cm, 5-15cm, 15-30cm, 30-60cm, "
            "60-100cm, 100-200cm (przedzial glebokosci ponizej powierzchni)"
        )
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    if Path(args.output).suffix.lower() in (".tif", ".tiff"):
        print(
            "Error: --output to katalog magazynu (od 0.8.0); plik poza "
            "magazynem: hsg_from_rasters",
            file=sys.stderr,
        )
        return 1

    from kartograf.hydrology import HSGCalculator

    # Check that exactly one selection method is provided
    has_geometry = getattr(args, "geometry", None) is not None
    methods = [args.bbox, args.sheet]
    provided = [m for m in methods if m is not None]
    if has_geometry:
        provided.append(args.geometry)

    if len(provided) == 0:
        print(
            "Error: Must provide one of: --bbox, --sheet, or --geometry",
            file=sys.stderr,
        )
        return 1

    if len(provided) > 1:
        print(
            "Error: Provide only one of: --bbox, --sheet, or --geometry",
            file=sys.stderr,
        )
        return 1

    # zly bbox -> ValidationError -> Error: w main (stderr, kod 1)
    bbox = parse_bbox_arg(args.bbox, "EPSG:2180") if args.bbox else None
    selection: dict = {
        "sheet": args.sheet,
        "bbox": bbox,
        "geometry": Path(args.geometry) if has_geometry else None,
        "layer": getattr(args, "layer", None),
    }
    calc = HSGCalculator(Path(args.output))

    print("Calculating Hydrologic Soil Groups (HSG)...")
    if args.sheet:
        print(f"  Godło: {args.sheet}")
    if has_geometry:
        print(f"  Geometry: {Path(args.geometry).name}")
    if bbox:
        print(f"  BBox: ({bbox.min_x}, {bbox.min_y}) - ({bbox.max_x}, {bbox.max_y})")
    print(f"  Depth: {args.depth}")
    print()

    try:
        return run_with_plan_file(args, lambda a: _hsg_task(a, calc, selection))
    except (DownloadError, ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _plan_label(item: PlanItem) -> str:
    """``clay <unit>`` / ``hsg <unit>``: the layer of a position in its line."""
    if item.track == "hsg":
        return f"hsg {item.unit}"
    # soil/global_soilgrids_<property>_<depth>_<stat>
    return f"{item.segment.rsplit('/', 1)[-1].split('_')[2]} {item.unit}"


def _hsg_task(args: argparse.Namespace, calc: "HSGCalculator", selection: dict) -> int:
    """One ``soilgrids hsg`` request: a plan (``--check-updates``) or the
    inputs and the HSG with one status line each (spec 4.5)."""
    if args.check_updates:
        plan = calc.check_hsg(**selection, depth=args.depth, on_notice=_print_notice)
        return _report_plan(args, plan, _plan_label)
    update = _update_mode(args)
    result = calc.calculate_hsg(
        **selection,
        depth=args.depth,
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

    if args.stats and result.file is not None:
        print()
        print("HSG Statistics:")
        stats = calc.get_hsg_statistics(result.file.path)
        for group, data in stats.items():
            pct = data["percent"]
            area = data["area_ha"]
            print(f"  Group {group}: {pct:.1f}% ({area:.2f} ha)")
            print(f"           {data['description']}")

    print()
    print("Legend: 1=A (high infiltration), 2=B (moderate),")
    print("        3=C (slow), 4=D (very slow)")
    print("Use with SCS-CN method: HSG + Land Use -> Curve Number")
    return rc
