"""
Command-line interface for Kartograf.

This module provides CLI commands for parsing map sheet identifiers,
displaying hierarchy information, and downloading NMT and land cover data.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.landcover.manager import LandCoverManager


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="kartograf",
        description="Tool for parsing and downloading Polish topographic map sheets",
        epilog="Example: kartograf parse N-34-130-D --hierarchy",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.3.0-dev",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse and display information about a map sheet",
        description="Parse a map sheet identifier (godlo) and display its properties",
    )
    parse_parser.add_argument(
        "godlo",
        help="Map sheet identifier (e.g., N-34-130-D, N-34-130-D-d-2-4)",
    )
    parse_parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="Display the full hierarchy from this sheet up to 1:1000000",
    )
    parse_parser.add_argument(
        "--children",
        action="store_true",
        help="Display direct children of this sheet",
    )
    parse_parser.add_argument(
        "--descendants",
        metavar="SCALE",
        help="Display all descendants to target scale (e.g., 1:10000)",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Download NMT data for a map sheet",
        description=(
            "Download NMT (Digital Terrain Model) data from GUGiK OpenData as ASC files"
        ),
    )
    download_parser.add_argument(
        "godlo",
        help="Map sheet identifier (e.g., N-34-130-D-d-2-4)",
    )
    download_parser.add_argument(
        "--scale",
        metavar="SCALE",
        help="Download all descendants to target scale (e.g., 1:10000)",
    )
    download_parser.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default="./data",
        help="Output directory (default: ./data)",
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    download_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )

    # Landcover command group
    landcover_parser = subparsers.add_parser(
        "landcover",
        help="Download land cover data (BDOT10k, CORINE)",
        description="Download land cover data from BDOT10k or CORINE",
    )
    landcover_subparsers = landcover_parser.add_subparsers(
        dest="landcover_command",
        help="Land cover commands",
    )

    # Landcover download command
    lc_download = landcover_subparsers.add_parser(
        "download",
        help="Download land cover data",
        description="Download land cover data from selected source",
    )
    lc_download.add_argument(
        "--source",
        "-s",
        choices=["bdot10k", "corine"],
        default="bdot10k",
        help="Data source (default: bdot10k)",
    )
    lc_download.add_argument(
        "--teryt",
        metavar="CODE",
        help="TERYT code (4-digit powiat code, e.g., 1465)",
    )
    lc_download.add_argument(
        "--bbox",
        metavar="BBOX",
        help="Bounding box: min_x,min_y,max_x,max_y in EPSG:2180",
    )
    lc_download.add_argument(
        "--godlo",
        metavar="GODLO",
        help="Map sheet identifier (e.g., N-34-130-D)",
    )
    lc_download.add_argument(
        "--year",
        type=int,
        default=2018,
        help="Reference year for CORINE (default: 2018)",
    )
    lc_download.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default="./data/landcover",
        help="Output directory (default: ./data/landcover)",
    )
    lc_download.add_argument(
        "--format",
        "-f",
        choices=["GPKG", "SHP", "GML"],
        default="GPKG",
        help="Output format for BDOT10k (default: GPKG)",
    )

    # Landcover list-sources command
    landcover_subparsers.add_parser(
        "list-sources",
        help="List available data sources",
    )

    # Landcover list-layers command
    lc_layers = landcover_subparsers.add_parser(
        "list-layers",
        help="List available layers for a source",
    )
    lc_layers.add_argument(
        "--source",
        "-s",
        choices=["bdot10k", "corine"],
        default="bdot10k",
        help="Data source (default: bdot10k)",
    )

    return parser


def format_sheet_info(parser: SheetParser) -> str:
    """
    Format sheet information for display.

    Parameters
    ----------
    parser : SheetParser
        Parsed sheet

    Returns
    -------
    str
        Formatted information string
    """
    lines = [
        f"Sheet:     {parser.godlo}",
        f"Scale:     {parser.scale}",
        f"Layout:    {parser.uklad}",
        "Components:",
    ]

    for name, value in parser.components.items():
        lines.append(f"  {name}: {value}")

    return "\n".join(lines)


def format_hierarchy(parser: SheetParser) -> str:
    """
    Format hierarchy information for display.

    Parameters
    ----------
    parser : SheetParser
        Starting sheet

    Returns
    -------
    str
        Formatted hierarchy string
    """
    hierarchy = parser.get_hierarchy_up()
    lines = ["Hierarchy (from current to 1:1000000):", ""]

    for i, sheet in enumerate(hierarchy):
        indent = "  " * i
        arrow = "└─ " if i > 0 else ""
        lines.append(f"{indent}{arrow}{sheet.godlo} ({sheet.scale})")

    return "\n".join(lines)


def format_children(parser: SheetParser) -> str:
    """
    Format children information for display.

    Parameters
    ----------
    parser : SheetParser
        Parent sheet

    Returns
    -------
    str
        Formatted children string
    """
    children = parser.get_children()

    if not children:
        return f"Sheet {parser.godlo} has no children (already at finest scale 1:10000)"

    lines = [
        f"Children of {parser.godlo} ({len(children)} sheets):",
        "",
    ]

    for child in children:
        lines.append(f"  {child.godlo} ({child.scale})")

    return "\n".join(lines)


def format_descendants(parser: SheetParser, target_scale: str) -> str:
    """
    Format descendants information for display.

    Parameters
    ----------
    parser : SheetParser
        Starting sheet
    target_scale : str
        Target scale

    Returns
    -------
    str
        Formatted descendants string
    """
    descendants = parser.get_all_descendants(target_scale)

    lines = [
        f"Descendants of {parser.godlo} to {target_scale} ({len(descendants)} sheets):",
        "",
    ]

    # Group by intermediate scales if there are many
    if len(descendants) <= 20:
        for desc in descendants:
            lines.append(f"  {desc.godlo}")
    else:
        # Just show count and first/last few
        lines.append(f"  {descendants[0].godlo}")
        lines.append(f"  {descendants[1].godlo}")
        lines.append("  ...")
        lines.append(f"  {descendants[-2].godlo}")
        lines.append(f"  {descendants[-1].godlo}")

    return "\n".join(lines)


def cmd_parse(args: argparse.Namespace) -> int:
    """
    Execute the parse command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    try:
        parser = SheetParser(args.godlo)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Always show basic info
    print(format_sheet_info(parser))

    # Show hierarchy if requested
    if args.hierarchy:
        print()
        print(format_hierarchy(parser))

    # Show children if requested
    if args.children:
        print()
        print(format_children(parser))

    # Show descendants if requested
    if args.descendants:
        try:
            print()
            print(format_descendants(parser, args.descendants))
        except ValidationError as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1

    return 0


def create_progress_callback(quiet: bool = False):
    """
    Create a progress callback for download operations.

    Parameters
    ----------
    quiet : bool
        If True, suppress output

    Returns
    -------
    callable
        Progress callback function
    """
    if quiet:
        return None

    def on_progress(progress: DownloadProgress) -> None:
        """Print progress bar and status."""
        bar_width = 30
        filled = int(bar_width * progress.current / max(progress.total, 1))
        bar = "=" * filled + "-" * (bar_width - filled)

        status_icon = {
            "downloading": "↓",
            "completed": "✓",
            "skipped": "○",
            "failed": "✗",
        }.get(progress.status, " ")

        line = (
            f"\r[{bar}] {progress.current}/{progress.total} "
            f"{status_icon} {progress.godlo}"
        )

        # Pad to overwrite previous longer lines
        line = line.ljust(80)

        if progress.status in ("completed", "failed"):
            print(line, flush=True)
        else:
            print(line, end="", flush=True)

    return on_progress


def cmd_download(args: argparse.Namespace) -> int:
    """
    Execute the download command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    try:
        # Validate godlo first
        SheetParser(args.godlo)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create download manager
    output_dir = Path(args.output)
    manager = DownloadManager(output_dir=output_dir)

    skip_existing = not args.force
    on_progress = create_progress_callback(args.quiet)

    try:
        if args.scale:
            # Download hierarchy
            if not args.quiet:
                count = manager.count_sheets(args.godlo, args.scale)
                print(f"Downloading {count} sheets from {args.godlo} to {args.scale}")
                print()

            paths = manager.download_hierarchy(
                args.godlo,
                args.scale,
                skip_existing=skip_existing,
                on_progress=on_progress,
            )

            if not args.quiet:
                print()
                print(f"Downloaded {len(paths)} files to {output_dir}")
        else:
            # Download single sheet
            if not args.quiet:
                print(f"Downloading {args.godlo}...")

            path = manager.download_sheet(
                args.godlo,
                skip_existing=skip_existing,
            )

            if not args.quiet:
                print(f"Downloaded to {path}")

    except DownloadError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_landcover(args: argparse.Namespace) -> int:
    """
    Execute landcover commands.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    if args.landcover_command is None:
        print("Usage: kartograf landcover <command>")
        print("Commands: download, list-sources, list-layers")
        print("Run 'kartograf landcover <command> --help' for details")
        return 0

    if args.landcover_command == "list-sources":
        return cmd_landcover_list_sources(args)

    if args.landcover_command == "list-layers":
        return cmd_landcover_list_layers(args)

    if args.landcover_command == "download":
        return cmd_landcover_download(args)

    return 0


def cmd_landcover_list_sources(args: argparse.Namespace) -> int:
    """List available land cover data sources."""
    print("Available land cover data sources:")
    print()
    print("  bdot10k  - BDOT10k (GUGiK)")
    print("             Polish topographic database, land cover classes (PT)")
    print("             High resolution (1:10000), vector data")
    print("             Formats: GPKG, SHP, GML")
    print()
    print("  corine   - CORINE Land Cover (Copernicus/GIOŚ)")
    print("             European land cover classification (44 classes)")
    print("             Resolution: 100m, raster data")
    print("             Years: 1990, 2000, 2006, 2012, 2018")
    print()
    return 0


def cmd_landcover_list_layers(args: argparse.Namespace) -> int:
    """List available layers for a source."""
    manager = LandCoverManager(provider=args.source)

    print(f"Available layers for {manager.provider_name}:")
    print()

    if args.source == "bdot10k":
        from kartograf.providers.bdot10k import Bdot10kProvider

        provider = Bdot10kProvider()
        for layer in provider.get_available_layers():
            desc = provider.get_layer_description(layer)
            print(f"  {layer}  - {desc}")
    else:
        from kartograf.providers.corine import CorineProvider

        provider = CorineProvider()
        print("  CORINE provides unified land cover classification.")
        print("  Available years:")
        for year in provider.get_available_years():
            print(f"    {year}")
        print()
        print("  Use --year option to select reference year.")

    return 0


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """Execute landcover download command."""
    # Check that exactly one selection method is provided
    methods = [args.teryt, args.bbox, args.godlo]
    provided = [m for m in methods if m is not None]

    if len(provided) == 0:
        print(
            "Error: Must provide one of: --teryt, --bbox, or --godlo", file=sys.stderr
        )
        return 1

    if len(provided) > 1:
        print(
            "Error: Provide only one of: --teryt, --bbox, or --godlo", file=sys.stderr
        )
        return 1

    # Parse bbox if provided
    bbox = None
    if args.bbox:
        try:
            parts = [float(x.strip()) for x in args.bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("BBOX must have 4 values")
            bbox = BBox(parts[0], parts[1], parts[2], parts[3], "EPSG:2180")
        except ValueError as e:
            print(f"Error: Invalid bbox format: {e}", file=sys.stderr)
            print(
                "Expected: min_x,min_y,max_x,max_y (e.g., 450000,550000,460000,560000)"
            )
            return 1

    # Create manager with selected provider
    output_dir = Path(args.output)
    manager = LandCoverManager(output_dir=output_dir, provider=args.source)

    print(f"Downloading land cover data from {manager.provider_name}...")

    try:
        # Build kwargs for provider-specific options
        kwargs = {}
        if args.source == "corine":
            kwargs["year"] = args.year
        if args.source == "bdot10k":
            kwargs["format"] = args.format

        # Download
        if args.teryt:
            print(f"  TERYT: {args.teryt}")
            path = manager.download(teryt=args.teryt, **kwargs)
        elif bbox:
            print(
                f"  BBox: ({bbox.min_x}, {bbox.min_y}) - ({bbox.max_x}, {bbox.max_y})"
            )
            path = manager.download(bbox=bbox, **kwargs)
        else:
            print(f"  Godło: {args.godlo}")
            path = manager.download(godlo=args.godlo, **kwargs)

        print(f"Downloaded to: {path}")
        return 0

    except NotImplementedError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except DownloadError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main(args: Optional[list[str]] = None) -> int:
    """
    Main entry point for the CLI.

    Parameters
    ----------
    args : list[str], optional
        Command-line arguments (defaults to sys.argv[1:])

    Returns
    -------
    int
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "parse":
        return cmd_parse(parsed_args)

    if parsed_args.command == "download":
        return cmd_download(parsed_args)

    if parsed_args.command == "landcover":
        return cmd_landcover(parsed_args)

    # Unknown command (shouldn't happen with argparse)
    print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
