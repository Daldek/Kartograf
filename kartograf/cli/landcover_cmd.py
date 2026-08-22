"""
``kartograf landcover`` command group (download, list-sources, list-layers).
"""

import argparse
import sys
from pathlib import Path

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.landcover.manager import LandCoverManager


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
    print("  bdot10k   - BDOT10k (GUGiK)")
    print("              Polish topographic database, land cover and hydrography")
    print("              layers (PT*, SW*)")
    print("              High resolution (1:10000), vector data")
    print("              Formats: GPKG, SHP")
    print()
    print("  corine    - CORINE Land Cover (Copernicus/GIOŚ)")
    print("              European land cover classification (44 classes)")
    print("              Resolution: 100m, raster data")
    print("              Years: 1990, 2000, 2006, 2012, 2018")
    print()
    print("  soilgrids - ISRIC SoilGrids")
    print("              Global soil property predictions")
    print("              Resolution: 250m, raster data (GeoTIFF)")
    print("              Properties: clay, sand, silt, soc, phh2o, nitrogen, etc.")
    print("              Depths: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm")
    print()
    return 0


def cmd_landcover_list_layers(args: argparse.Namespace) -> int:
    """List available layers for a source."""
    manager = LandCoverManager(provider=args.source)

    print(f"Available layers for {manager.provider_name}:")
    print()

    if args.source == "bdot10k":
        from kartograf.providers.pl.bdot10k import Bdot10kProvider

        provider = Bdot10kProvider()
        for layer in provider.get_available_layers():
            desc = provider.get_layer_description(layer)
            print(f"    {layer}  - {desc}")
    elif args.source == "corine":
        from kartograf.providers.corine import CorineProvider

        provider = CorineProvider()
        print("  CORINE provides unified land cover classification.")
        print("  Available years:")
        for year in provider.get_available_years():
            print(f"    {year}")
        print()
        print("  Use --year option to select reference year.")
    elif args.source == "soilgrids":
        from kartograf.providers.soilgrids import SoilGridsProvider

        provider = SoilGridsProvider()
        print("  Available soil properties:")
        for prop in provider.get_available_properties():
            desc = provider.get_property_description(prop)
            print(f"    {prop:10} - {desc}")
        print()
        print("  Available depths:")
        for depth in provider.get_available_depths():
            print(f"    {depth}")
        print()
        print("  Available statistics:")
        for stat in provider.get_available_stats():
            print(f"    {stat}")
        print()
        print("  Use --property, --depth, --stat options to configure download.")

    return 0


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """Execute landcover download command."""
    # Check that exactly one selection method is provided
    has_geometry = getattr(args, "geometry", None) is not None
    methods = [args.teryt, args.bbox, args.godlo]
    provided = [m for m in methods if m is not None]
    if has_geometry:
        provided.append(args.geometry)

    if len(provided) == 0:
        print(
            "Error: Must provide one of: --teryt, --bbox, --godlo, or --geometry",
            file=sys.stderr,
        )
        return 1

    if len(provided) > 1:
        print(
            "Error: Provide only one of: --teryt, --bbox, --godlo, or --geometry",
            file=sys.stderr,
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
        if args.source == "soilgrids":
            kwargs["property"] = args.property
            kwargs["depth"] = args.depth
            kwargs["stat"] = args.stat

        # Download
        if has_geometry:
            from kartograf.core.geometry import get_overall_bbox

            filepath = Path(args.geometry)
            if not filepath.exists():
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                return 1
            bbox = get_overall_bbox(filepath, layer=getattr(args, "layer", None))
            print(f"  Geometry: {filepath.name}")
            path = manager.download(bbox=bbox, **kwargs)
        elif args.teryt:
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
