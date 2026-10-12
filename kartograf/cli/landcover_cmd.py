"""
``kartograf landcover`` command group (download, list-sources, list-layers).
"""

import argparse
import sys
from pathlib import Path

from kartograf.cli._parser import parse_bbox_arg
from kartograf.cli.download_cmd import (
    _plan_context,
    _print_notice,
    _print_version_summary,
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    run_with_plan_file,
)
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
    """List available layers for a selected source."""
    if args.source is None:
        print(
            "Error: --source wymagane: bdot10k (wektorowa baza topograficzna "
            "GUGiK), corine (pokrycie terenu Copernicus), soilgrids (gleby ISRIC)",
            file=sys.stderr,
        )
        return 1

    if args.source == "bdot10k":
        from kartograf.providers.pl.bdot10k import Bdot10kProvider

        bdot = Bdot10kProvider()
        provider_name = bdot.name
    elif args.source == "corine":
        from kartograf.providers.corine import CorineProvider

        corine = CorineProvider()
        provider_name = corine.name
    else:
        from kartograf.providers.soilgrids import SoilGridsProvider

        soilgrids = SoilGridsProvider()
        provider_name = soilgrids.name
    print(f"Available layers for {provider_name}:")
    print()

    if args.source == "bdot10k":
        for layer in bdot.get_available_layers():
            desc = bdot.get_layer_description(layer)
            print(f"    {layer}  - {desc}")
    elif args.source == "corine":
        print("  CORINE provides unified land cover classification.")
        print("  Available years:")
        for year in corine.get_available_years():
            print(f"    {year}")
        print()
        print("  Use --year option to select reference year.")
    elif args.source == "soilgrids":
        print("  Available soil properties:")
        for prop in soilgrids.get_available_properties():
            desc = soilgrids.get_property_description(prop)
            print(f"    {prop:10} - {desc}")
        print()
        print("  Available depths:")
        for depth in soilgrids.get_available_depths():
            print(f"    {depth}")
        print()
        print("  Available statistics:")
        for stat in soilgrids.get_available_stats():
            print(f"    {stat}")
        print()
        print("  Use --property, --depth, --stat options to configure download.")

    return 0


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """Execute landcover download command."""
    missing = []
    if args.source is None:
        missing.append(
            "--source wymagane: bdot10k (wektorowa baza topograficzna GUGiK), "
            "corine (pokrycie terenu Copernicus), soilgrids (gleby ISRIC)"
        )
    if args.output is None:
        missing.append(
            "--output wymagane: katalog magazynu (pliki w <DIR>/landcover/... "
            "i <DIR>/soil/...)"
        )
    if args.source == "corine" and args.year is None:
        missing.append(
            "--year wymagane dla corine: 2018, 2012, 2006, 2000 "
            "(edycje pokrycia terenu CLMS/WMS), 1990 (tylko podglad WMS)"
        )
    if args.source == "soilgrids":
        if args.property is None:
            missing.append(
                "--property wymagane dla soilgrids: bdod (gestosc objetosciowa), "
                "cec (pojemnosc sorpcyjna), cfvo (frakcja szkieletowa), clay (il), "
                "nitrogen (azot), ocd (gestosc wegla organicznego), "
                "ocs (zasob wegla organicznego), phh2o (pH), sand (piasek), "
                "silt (pyl), soc (wegiel organiczny)"
            )
        if args.depth is None:
            missing.append(
                "--depth wymagane dla soilgrids: 0-5cm, 5-15cm, 15-30cm, "
                "30-60cm, 60-100cm, 100-200cm "
                "(przedzial glebokosci ponizej powierzchni)"
            )
        if args.stat is None:
            missing.append(
                "--stat wymagane dla soilgrids: mean (srednia), "
                "Q0.05 (5. percentyl), Q0.5 (mediana), "
                "Q0.95 (95. percentyl), uncertainty (niepewnosc predykcji)"
            )
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # Check that exactly one selection method is provided
    has_geometry = getattr(args, "geometry", None) is not None
    methods = [args.teryt, args.bbox, args.sheet]
    provided = [m for m in methods if m is not None]
    if has_geometry:
        provided.append(args.geometry)

    if len(provided) == 0:
        print(
            "Error: Must provide one of: --teryt, --bbox, --sheet, or --geometry",
            file=sys.stderr,
        )
        return 1

    if len(provided) > 1:
        print(
            "Error: Provide only one of: --teryt, --bbox, --sheet, or --geometry",
            file=sys.stderr,
        )
        return 1

    # Parse bbox if provided (zly bbox -> ValidationError -> Error: w main)
    bbox = parse_bbox_arg(args.bbox, "EPSG:2180") if args.bbox else None
    selection: dict = {
        "teryt": args.teryt,
        "sheet": args.sheet,
        "bbox": bbox,
        "geometry": Path(args.geometry) if has_geometry else None,
        "layer": getattr(args, "layer", None),
    }
    options: dict = {}
    if args.source == "corine":
        options["year"] = args.year
    if args.source == "bdot10k":
        options["format"] = args.format
    if args.source == "soilgrids":
        options["property"] = args.property
        options["depth"] = args.depth
        options["stat"] = args.stat

    manager = LandCoverManager(output_dir=Path(args.output), provider=args.source)
    try:
        return run_with_plan_file(
            args, lambda a: _landcover_task(a, manager, selection, options)
        )
    except (DownloadError, ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _landcover_task(
    args: argparse.Namespace,
    manager: LandCoverManager,
    selection: dict,
    options: dict,
) -> int:
    """One ``landcover download`` request: a plan (``--check-updates``) or
    the files with one status line each (spec 4.5)."""
    if args.check_updates:
        return _report_plan(
            args, manager.check(**selection, on_notice=_print_notice, **options)
        )
    update = _update_mode(args)
    result = manager.download(
        **selection,
        update=update,
        plan=_plan_context(args).loaded,
        on_notice=_print_notice,
        **options,
    )
    out = manager.output_dir
    statuses = []
    for item in result.files:
        for file in (item.file, item.raw):
            if file is not None:
                _report_file(args, _unit_of(file.path, out), file, update)
                statuses.append(file.status)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    # several files (BDOT10k area): one summary line, as for sheet lists
    if args.source == "bdot10k" and args.teryt is None and not args.quiet:
        _print_version_summary(statuses, len(result.failed), out)
    return 0 if result.ok else 1
