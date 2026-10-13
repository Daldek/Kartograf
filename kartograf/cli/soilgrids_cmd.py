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
        print("Uzycie: kartograf soilgrids <komenda>")
        print("Komendy: hsg")
        print("Szczegoly: kartograf soilgrids <komenda> --help")
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
            "--output wymagane: katalog magazynu (wejscia w <KATALOG>/soil/..., "
            "HSG w <KATALOG>/hsg/...)"
        )
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    from kartograf.hydrology import HSGCalculator

    # one area choice: checked by the library (ValidationError -> Error:)
    bbox = parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None
    geometry = Path(args.geometry) if args.geometry is not None else None
    selection: dict = {
        "sheet": args.sheet,
        "bbox": bbox,
        "geometry": geometry,
        "layer": args.layer,
    }
    calc = HSGCalculator(Path(args.output))

    try:
        return run_with_plan_file(args, lambda a: _hsg_task(a, calc, selection))
    except (DownloadError, ParseError, ValidationError) as e:
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
        print("Statystyki HSG:")
        stats = calc.get_hsg_statistics(result.file.path)
        for group, data in stats.items():
            pct = data["percent"]
            area = data["area_ha"]
            print(f"  Grupa {group}: {pct:.1f}% ({area:.2f} ha)")
            print(f"           {data['description']}")

    if not args.quiet:
        print()
        print("Legenda: 1=A (duza infiltracja), 2=B (umiarkowana),")
        print("         3=C (mala), 4=D (bardzo mala)")
        print("Metoda SCS-CN: HSG + uzytkowanie terenu -> Curve Number")
    return rc
