"""
``landcover download`` and ``landcover list-layers`` (``LandCoverManager``, Z1).

``run_land_cover`` is the store request of one land cover source with the
area flags of a command; ``soil download`` runs SoilGrids through it.
"""

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Any

from kartograf.cli._args import parse_bbox_arg
from kartograf.cli.download_cmd import (
    _end_progress,
    _plan_context,
    _print_notice,
    _print_version_summary,
    _report_file,
    _report_plan,
    _report_stale,
    _unit_of,
    _update_mode,
    create_progress_callback,
    run_with_plan_file,
)
from kartograf.download.collections import collection_classes, collection_layers
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_SOURCE_CHOICES,
    LandCoverManager,
)

# Sources whose area is several TERYT unit packages (summary line).
_UNIT_SOURCES = ("bdot10k", "bdoo")


def cmd_landcover_list_layers(args: argparse.Namespace) -> int:
    """``landcover list-layers``: BDOT10k, ZABAGED, Data50 or Data250 layers,
    BDOO classes per release, CORINE years."""
    if args.source is None:
        print(f"Error: --source wymagane: {LANDCOVER_SOURCE_CHOICES}", file=sys.stderr)
        return 1
    # the catalogue of the source (no network, nothing written)
    manager = LandCoverManager(".", args.source, cache=False)
    print(f"Warstwy zrodla {manager.provider_name}:")
    print()
    if args.source in COLLECTION_SOURCES:
        key = COLLECTION_SOURCES[args.source]
        classes = collection_classes(key)
        if classes:
            _print_classes(classes)
            return 0
        for layer in collection_layers(key):
            print(f"    {layer.name}  - warstwa uslugi {layer.source}")
        print()
        print(
            "  Nazwy = warstwy GeoPackage obszaru (--bbox/--geometry); plik "
            "krajowy (--whole-country) ma warstwy pelnej bazy pod nazwami CUZK."
        )
        return 0
    provider: Any = manager.provider
    if args.source == "bdot10k":
        for layer in provider.get_available_layers():
            desc = provider.get_layer_description(layer)
            print(f"    {layer}  - {desc}")
    else:
        print("  CORINE: jedna klasyfikacja pokrycia terenu.")
        print("  Dostepne lata:")
        for year in provider.get_available_years():
            print(f"    {year}")
        print()
        print("  Rok referencyjny: --year.")
    return 0


def _print_classes(classes: dict[str, tuple[str, ...]]) -> None:
    """Class codes of a source of packages (BDOO) per release (``--year``)."""
    print("  Klasy obiektow (--layers) wg rocznika; kod = OT_<KOD> w nazwach plikow")
    print("  paczki wojewodztwa.")
    for where, codes in classes.items():
        print()
        print(f"  {where} ({len(codes)}):")
        print(
            textwrap.fill(
                ", ".join(codes),
                width=78,
                initial_indent="    ",
                subsequent_indent="    ",
            )
        )
    print()
    print(
        textwrap.fill(
            "--layers zapisuje ZIP plikow wybranych klas. Paczka ma pliki tylko "
            "tych klas, ktorych obiekty sa w wojewodztwie (do 2023): brak czesci "
            "klas = Info, brak wszystkich = blad wojewodztwa.",
            width=78,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )


def area_task_arguments(args: argparse.Namespace) -> dict:
    """Shared area selection for land cover, SoilGrids and HSG tasks."""
    return {
        "sheet": args.sheet,
        "bbox": parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        "geometry": Path(args.geometry) if args.geometry is not None else None,
        "layer": args.layer,
    }


def _landcover_options(args: argparse.Namespace) -> dict:
    options: dict = {}
    if args.year is not None:
        options["year"] = args.year
    if args.format is not None:
        options["format"] = args.format
    if args.layers is not None:
        options["layers"] = args.layers
    if args.keep_raw:
        options["keep_raw"] = True
    if args.whole_country:
        options["whole_country"] = True
    if args.horizontal_crs is not None:
        options["horizontal_crs"] = args.horizontal_crs
    return options


def landcover_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``landcover download`` and ``project add``."""
    return {
        "source": args.source,
        "teryt": args.teryt,
        **area_task_arguments(args),
        **_landcover_options(args),
    }


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """``landcover download``: flags -> ``LandCoverManager.download``/``.check``."""
    missing = []
    if args.source is None:
        missing.append(f"--source wymagane: {LANDCOVER_SOURCE_CHOICES}")
    if args.output is None:
        missing.append(
            "--output wymagane: katalog magazynu (pliki w <KATALOG>/landcover/...)"
        )
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    options = _landcover_options(args)
    return run_land_cover(
        args, args.source, options, teryt=args.teryt, workers=args.workers
    )


def run_land_cover(
    args: argparse.Namespace,
    source: str,
    options: dict,
    *,
    teryt: str | None = None,
    workers: int = 1,
) -> int:
    """One store request of ``source`` for the area flags of ``args``."""
    selection = area_task_arguments(args)
    selection["teryt"] = teryt
    manager = LandCoverManager(output_dir=Path(args.output), provider=source)
    try:
        return run_with_plan_file(
            args,
            lambda a: _landcover_task(a, manager, source, selection, options, workers),
        )
    except (DownloadError, ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _landcover_task(
    args: argparse.Namespace,
    manager: LandCoverManager,
    source: str,
    selection: dict,
    options: dict,
    workers: int,
) -> int:
    """One request: a plan (``--check-updates``) or the files with one status
    line each (spec 4.5); BDOT10k by an area draws the powiat progress bar
    first."""
    if args.check_updates:
        plan = manager.check(**selection, on_notice=_print_notice, **options)
        return _report_plan(args, plan)
    update = _update_mode(args)
    on_progress = create_progress_callback(args.quiet, workers)
    result = manager.download(
        **selection,
        update=update,
        plan=_plan_context(args).loaded,
        workers=workers,
        on_notice=_print_notice,
        on_progress=on_progress,
        **options,
    )
    out = manager.output_dir
    _end_progress(on_progress)
    statuses = []
    for item in result.files:
        for file in (item.file, item.raw):
            if file is not None:
                _report_file(args, _unit_of(file.path, out), file, update)
                statuses.append(file.status)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    # several files (an area of BDOT10k powiats or BDOO voivodeships): one
    # summary line, as for sheet lists
    if source in _UNIT_SOURCES and selection["teryt"] is None and not args.quiet:
        _print_version_summary(statuses, len(result.failed), out)
    return 0 if result.ok else 1
