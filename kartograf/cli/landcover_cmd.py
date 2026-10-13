"""
``kartograf landcover`` command group (download, list-sources, list-layers).
"""

import argparse
import sys
from pathlib import Path
from typing import Any

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
        print("Uzycie: kartograf landcover <komenda>")
        print("Komendy: download, list-sources, list-layers")
        print("Szczegoly: kartograf landcover <komenda> --help")
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
    print("Dostepne zrodla pokrycia terenu i gleb:")
    print()
    print("  bdot10k   - BDOT10k (GUGiK)")
    print("              Baza danych obiektow topograficznych: warstwy pokrycia")
    print("              terenu i sieci wodnej (PT*, SW*)")
    print("              Dane wektorowe, szczegolowosc 1:10000")
    print("              Formaty: GPKG, SHP")
    print()
    print("  corine    - CORINE Land Cover (Copernicus/GIOS)")
    print("              Europejska klasyfikacja pokrycia terenu (44 klasy)")
    print("              Rozdzielczosc: 100 m, dane rastrowe")
    print("              Lata: 1990, 2000, 2006, 2012, 2018")
    print()
    print("  soilgrids - ISRIC SoilGrids")
    print("              Globalne predykcje wlasciwosci gleb")
    print("              Rozdzielczosc: 250 m, dane rastrowe (GeoTIFF)")
    print("              Wlasciwosci: clay, sand, silt, soc, phh2o, nitrogen i inne")
    print(
        "              Glebokosci: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm"
    )
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

    # the catalogue of the source (no network, nothing written)
    provider: Any = LandCoverManager(".", args.source, cache=False).provider
    bdot = corine = soilgrids = provider
    provider_name = provider.name
    print(f"Warstwy zrodla {provider_name}:")
    print()

    if args.source == "bdot10k":
        for layer in bdot.get_available_layers():
            desc = bdot.get_layer_description(layer)
            print(f"    {layer}  - {desc}")
    elif args.source == "corine":
        print("  CORINE: jedna klasyfikacja pokrycia terenu.")
        print("  Dostepne lata:")
        for year in corine.get_available_years():
            print(f"    {year}")
        print()
        print("  Rok referencyjny: --year.")
    elif args.source == "soilgrids":
        print("  Wlasciwosci gleb:")
        for prop in soilgrids.get_available_properties():
            desc = soilgrids.get_property_description(prop)
            print(f"    {prop:10} - {desc}")
        print()
        print("  Glebokosci:")
        for depth in soilgrids.get_available_depths():
            print(f"    {depth}")
        print()
        print("  Statystyki:")
        for stat in soilgrids.get_available_stats():
            print(f"    {stat}")
        print()
        print("  Wybor pobrania: --property, --depth, --stat.")

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
            "--output wymagane: katalog magazynu (pliki w <KATALOG>/landcover/... "
            "i <KATALOG>/soil/...)"
        )
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # one area choice: checked by the library (ValidationError -> Error:)
    bbox = parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None
    selection: dict = {
        "teryt": args.teryt,
        "sheet": args.sheet,
        "bbox": bbox,
        "geometry": Path(args.geometry) if args.geometry is not None else None,
        "layer": args.layer,
    }
    options: dict = {}
    if args.year is not None:
        options["year"] = args.year
    if args.format is not None:
        options["format"] = args.format
    if args.layers is not None:
        options["layers"] = args.layers
    if args.keep_raw:
        options["keep_raw"] = True
    if args.property is not None:
        options["property"] = args.property
    if args.depth is not None:
        options["depth"] = args.depth
    if args.stat is not None:
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
        workers=args.workers,
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
