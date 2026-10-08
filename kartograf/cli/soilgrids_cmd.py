"""
``kartograf soilgrids`` command group (HSG calculation).
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._parser import parse_bbox_arg
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError, ParseError, ValidationError


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
    from kartograf.hydrology import HSGCalculator

    # Check that exactly one selection method is provided
    has_geometry = getattr(args, "geometry", None) is not None
    methods = [args.bbox, args.godlo]
    provided = [m for m in methods if m is not None]
    if has_geometry:
        provided.append(args.geometry)

    if len(provided) == 0:
        print(
            "Error: Must provide one of: --bbox, --godlo, or --geometry",
            file=sys.stderr,
        )
        return 1

    if len(provided) > 1:
        print(
            "Error: Provide only one of: --bbox, --godlo, or --geometry",
            file=sys.stderr,
        )
        return 1

    # Canonical sheet code (A7): 'M-33-036-A' and 'M-33-36-A' give one file
    godlo = None
    if args.godlo:
        try:
            godlo = SheetParser(args.godlo).godlo
        except (ParseError, ValidationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Determine output path
    output_path = Path(args.output)
    if godlo:
        if output_path.suffix.lower() != ".tif":
            # Output is a directory; the directory itself is created on write
            output_path = output_path / f"hsg_{godlo}_{args.depth}.tif"
    elif (args.bbox or has_geometry) and output_path.suffix.lower() != ".tif":
        output_path = output_path / f"hsg_bbox_{args.depth}.tif"

    # Parse bbox if provided (or compute from geometry)
    bbox = None
    if has_geometry:
        from kartograf.core.geometry import get_overall_bbox

        filepath = Path(args.geometry)
        if not filepath.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            return 1
        try:
            bbox = get_overall_bbox(filepath, layer=getattr(args, "layer", None))
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.bbox:
        # zly bbox -> ValidationError -> Error: w main (stderr, kod 1)
        bbox = parse_bbox_arg(args.bbox, "EPSG:2180")

    # Create calculator
    calc = HSGCalculator()

    print("Calculating Hydrologic Soil Groups (HSG)...")
    if godlo:
        print(f"  Godło: {godlo}")
    if has_geometry:
        print(f"  Geometry: {Path(args.geometry).name}")
    if bbox:
        print(f"  BBox: ({bbox.min_x}, {bbox.min_y}) - ({bbox.max_x}, {bbox.max_y})")
    print(f"  Depth: {args.depth}")
    print()

    try:
        if godlo:
            result_path = calc.calculate_hsg_by_godlo(
                godlo=godlo,
                output_path=output_path,
                depth=args.depth,
                keep_intermediate=args.keep_intermediate,
            )
        else:
            result_path = calc.calculate_hsg_by_bbox(
                bbox=bbox,
                output_path=output_path,
                depth=args.depth,
                keep_intermediate=args.keep_intermediate,
            )

        print(f"HSG raster saved to: {result_path}")

        # Print statistics if requested
        if args.stats:
            print()
            print("HSG Statistics:")
            stats = calc.get_hsg_statistics(result_path)
            for group, data in stats.items():
                pct = data["percent"]
                area = data["area_ha"]
                print(f"  Group {group}: {pct:.1f}% ({area:.2f} ha)")
                print(f"           {data['description']}")

        print()
        print("Legend: 1=A (high infiltration), 2=B (moderate),")
        print("        3=C (slow), 4=D (very slow)")
        print("Use with SCS-CN method: HSG + Land Use -> Curve Number")

        return 0

    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except DownloadError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
