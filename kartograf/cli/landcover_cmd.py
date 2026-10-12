"""
``kartograf landcover`` command group (download, list-sources, list-layers).
"""

import argparse
import sys
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cli._parser import parse_bbox_arg
from kartograf.cli.download_cmd import (
    _announce_geometry_layer,
    _plan_context,
    _print_version_summary,
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    _warn_cache_disabled,
    run_with_plan_file,
)
from kartograf.core.sheet_parser import BBox
from kartograf.download.fetch import UpdateMode
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.corine import CorineProvider


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

    # BDOT10k uses the same cwd cache as PL/CZ downloads for PRG answers.
    output_dir = Path(args.output)
    is_bdot = args.source == "bdot10k"
    update = _update_mode(args)
    with open_cache(
        is_bdot, force=update == "force", on_notice=_warn_cache_disabled
    ) as cache:
        manager = LandCoverManager(
            output_dir=output_dir, provider=args.source, cache=cache
        )

        kwargs: dict = {}
        if args.source == "corine":
            kwargs["year"] = args.year
        if is_bdot:
            kwargs["format"] = args.format
        if args.source == "soilgrids":
            kwargs["property"] = args.property
            kwargs["depth"] = args.depth
            kwargs["stat"] = args.stat

        try:
            if has_geometry:
                from kartograf.core.geometry import get_overall_bbox

                if not _announce_geometry_layer(args):
                    return 1
                bbox = get_overall_bbox(Path(args.geometry), layer=args.layer)
            return run_with_plan_file(
                args, lambda a: _landcover_task(a, manager, bbox, kwargs, update)
            )
        except NotImplementedError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except DownloadError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except (ParseError, ValidationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def _landcover_task(
    args: argparse.Namespace,
    manager: LandCoverManager,
    bbox: BBox | None,
    kwargs: dict,
    update: UpdateMode | None,
) -> int:
    """One ``landcover download`` request: a plan (``--check-updates``) or
    the files with one status line each (spec 4.5)."""
    teryt, sheet = args.teryt, args.sheet
    plan = _plan_context(args).loaded
    is_bdot = args.source == "bdot10k"
    if (
        isinstance(manager.provider, CorineProvider)
        and not manager.provider.uses_clms(args.year)
        and not args.check_updates
    ):
        print(
            f"Info: CORINE {args.year}: podglad WMS (stylizowany PNG, nie dane; "
            "dane CLMS wymagaja CLMS_CREDENTIALS)",
            file=sys.stderr,
        )
    out = manager.output_dir
    if teryt is None and is_bdot:
        # Every powiat of the area, one package each (A2); a failed powiat is
        # reported, the others still run (exit code 1, ARCHITECTURE 4.2).
        area = {"bbox": bbox} if bbox is not None else {"sheet": sheet}
        if args.check_updates:
            return _report_plan(args, manager.check_all_counties(**area, **kwargs))
        result = manager.download_all_counties(
            **area, update=update, plan=plan, **kwargs
        )
        statuses = []
        for item in result.files:
            for file in (item.file, item.raw):
                if file is not None:
                    _report_file(args, _unit_of(file.path, out), file, update)
                    statuses.append(file.status)
        for failure in result.failed:
            print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
        rc = _report_stale(result.stale)
        if not args.quiet:
            _print_version_summary(statuses, len(result.failed), manager.output_dir)
        return 1 if rc or result.failed else 0

    where = (
        {"teryt": teryt}
        if teryt is not None
        else {"bbox": bbox}
        if bbox is not None
        else {"sheet": sheet}
    )
    if args.check_updates:
        return _report_plan(args, manager.check(**where, **kwargs))
    single = manager.download(**where, update=update, plan=plan, **kwargs)
    for file in (single.file, single.raw):
        if file is not None:
            _report_file(args, _unit_of(file.path, out), file, update)
    return _report_stale(single.stale)
