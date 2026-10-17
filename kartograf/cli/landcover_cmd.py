"""``landcover download`` and ``landcover list-layers`` (ADR-037, ADR-044).

The CLI translates flags to ``download_landcover`` / ``check_landcover``.
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
from kartograf.download.options import output_required
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_PRODUCT_CHOICES,
    LandCoverManager,
    check_landcover,
    download_landcover,
    require_landcover_product,
)

# Sources whose area is several TERYT unit packages (summary line).
_UNIT_SOURCES = ("bdot10k", "bdoo")


def cmd_landcover_list_layers(args: argparse.Namespace) -> int:
    """``landcover list-layers``: BDOT10k, ZABAGED, Data50 or Data250 layers,
    BDOO classes per release, CORINE years."""
    if args.product is None:
        print(
            f"Error: --product wymagane: {LANDCOVER_PRODUCT_CHOICES}", file=sys.stderr
        )
        return 1
    # the catalogue of the product (no network, nothing written)
    manager = LandCoverManager(".", args.product, cache=False)
    print(f"Warstwy zrodla {manager.provider_name}:")
    print()
    if args.product in COLLECTION_SOURCES:
        key = COLLECTION_SOURCES[args.product]
        classes = collection_classes(key)
        if classes:
            _print_classes(classes)
            return 0
        for layer in collection_layers(key):
            print(f"    {layer.name}")
        print()
        print(
            textwrap.fill(
                "Nazwy = warstwy GeoPackage obszaru (--bbox/--geometry); wynik "
                "obszaru ma zawsze wszystkie te warstwy (--layers dziala tylko "
                "z --product bdot10k albo bdoo). Plik krajowy (--whole-country) "
                "ma warstwy pelnej bazy pod nazwami CUZK.",
                width=78,
                initial_indent="  ",
                subsequent_indent="  ",
            )
        )
        return 0
    provider: Any = manager.provider
    if args.product == "bdot10k":
        for layer in provider.get_available_layers():
            desc = provider.get_layer_description(layer)
            print(f"    {layer}  - {desc}")
    else:
        print("  CORINE: jedna klasyfikacja pokrycia terenu.")
        print("  Dostepne lata (--year, rok referencyjny):")
        for year in provider.get_available_years():
            kind = (
                "dane CLMS z CLMS_CREDENTIALS, bez nich podglad WMS"
                if year in provider.CLMS_YEARS
                else "tylko podglad WMS"
            )
            print(f"    {year}  ({kind})")
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


def landcover_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by ``landcover download`` and ``project add``."""
    return {
        "product": args.product,
        "teryt": args.teryt,
        **area_task_arguments(args),
        "year": args.year,
        "format": args.format,
        "layers": args.layers,
        "keep_raw": args.keep_raw,
        "whole_country": args.whole_country,
        "horizontal_crs": args.horizontal_crs,
    }


def cmd_landcover_download(args: argparse.Namespace) -> int:
    """``landcover download``: flags -> ``download_landcover``/``check_landcover``."""
    missing = []
    if args.product is None:
        missing.append(f"--product wymagane: {LANDCOVER_PRODUCT_CHOICES}")
    if args.output is None:
        missing.append(output_required("landcover"))
    if missing:
        for error in missing:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    require_landcover_product(args.product)
    return run_with_plan_file(args, _landcover_task)


def _landcover_task(args: argparse.Namespace) -> int:
    """Plan or download with a status line per file and errors per unit."""
    arguments = {**landcover_task_arguments(args), "output_dir": Path(args.output)}
    if args.check_updates:
        return _report_plan(args, check_landcover(**arguments, on_notice=_print_notice))
    update = _update_mode(args)
    on_progress = create_progress_callback(args.quiet, args.workers)
    result = download_landcover(
        **arguments,
        update=update,
        plan=_plan_context(args).loaded,
        workers=args.workers,
        on_notice=_print_notice,
        on_progress=on_progress,
    )
    _end_progress(on_progress)
    out = Path(args.output)
    statuses = []
    for item in (*result.files, *result.raw):
        _report_file(args, _unit_of(item.file.path, out), item.file, update)
        statuses.append(item.file.status)
    for failure in result.failed:
        print(f"Error: {failure.unit}: {failure.error}", file=sys.stderr)
    _report_stale(result.stale)
    if args.product in _UNIT_SOURCES and args.teryt is None and not args.quiet:
        _print_version_summary(statuses, len(result.failed), out)
    return 0 if result.ok else 1
