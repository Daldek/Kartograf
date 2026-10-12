"""
``kartograf soilgrids`` command group (HSG calculation).
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._parser import parse_bbox_arg
from kartograf.cli.download_cmd import _announce_geometry_layer
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
    missing = []
    if args.output is None:
        missing.append(
            "--output wymagane: dowolna sciezka pliku GeoTIFF .tif lub katalogu wyniku"
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

    # Canonical sheet code (A7): 'M-33-036-A' and 'M-33-36-A' give one file
    sheet = None
    if args.sheet:
        try:
            sheet = SheetParser(args.sheet).sheet
        except (ParseError, ValidationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Parse bbox if provided (or compute from geometry)
    bbox = None
    if has_geometry:
        from kartograf.core.geometry import get_overall_bbox

        filepath = Path(args.geometry)
        if not _announce_geometry_layer(args):
            return 1
        try:
            bbox = get_overall_bbox(filepath, layer=args.layer)
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.bbox:
        # zly bbox -> ValidationError -> Error: w main (stderr, kod 1)
        bbox = parse_bbox_arg(args.bbox, "EPSG:2180")

    # Create calculator
    calc = HSGCalculator(Path(args.output))

    print("Calculating Hydrologic Soil Groups (HSG)...")
    if sheet:
        print(f"  Godło: {sheet}")
    if has_geometry:
        print(f"  Geometry: {Path(args.geometry).name}")
    if bbox:
        print(f"  BBox: ({bbox.min_x}, {bbox.min_y}) - ({bbox.max_x}, {bbox.max_y})")
    print(f"  Depth: {args.depth}")
    print()

    try:
        if sheet:
            result = calc.calculate_hsg_by_sheet(
                sheet,
                depth=args.depth,
                stat="mean",  # HSG uses the mean texture estimate
            )
        else:
            assert bbox is not None
            result = calc.calculate_hsg_by_bbox(
                bbox,
                depth=args.depth,
                stat="mean",  # HSG uses the mean texture estimate
            )
        assert result.file is not None  # no plan: always a file
        result_path = result.file.path

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
