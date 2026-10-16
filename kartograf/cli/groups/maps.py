"""``kartograf maps``: BDOT10k visualizations (PL) and ZTM sheets (CZ)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_choice_values


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    for flag, label in (
        ("scale", "Skala mapy (wymagana)"),
        ("format", "Format pliku (wymagany)"),
        ("sheet_system", "Uklad arkuszy CZ (bez --sheet wymagany)"),
    ):
        choices = "; ".join(
            f"{product} {country}: {', '.join(values)}"
            for product in products
            for country, values in collection_choice_values(product, flag).items()
        )
        content.add_argument(
            f"--{flag.replace('_', '-')}",
            metavar=flag.upper(),
            help=f"{label}: {choices}",
        )


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the maps download and list-sources commands."""
    commands = add_group(
        subparsers,
        "maps",
        help="Mapy topograficzne: BDOT10k (PL), ZTM (CZ)",
        description="Arkusze map topograficznych BDOT10k i ZTM jako oryginalne "
        "pliki ze zrodla (GeoTIFF, PDF, DGN lub SHP).",
    )
    add_collection_commands(
        commands,
        "maps",
        help="Pobierz arkusze mapy topograficznej",
        description="--product topographic: wizualizacje BDOT10k (--country pl) "
        "albo ZTM (--country cz). --scale i --format sa wymagane. "
        "Arkusz ZTM rozpoznaje --sheet-system sjtsk/etrs89 z godla; "
        "dla --bbox/--geometry wybierz --sheet-system. ZTM TIFF, DGN i SHP "
        "sa ZIP-ami, PDF jest plikiem .pdf; BDOT10k TIFF i PDF sa "
        "oryginalnymi plikami z indeksu map.",
        area_result="arkusze map przecinajace obszar (pliki oryginalne)",
        content=_content,
        sheet_help="Godlo mapy: PL-1992 (--country pl) albo ZTM w S-JTSK/ETRS89 "
        "(--country cz; uklad arkuszy wynika z godla, mozna podac --sheet-system)",
        check_help="Porownaj etykiete wydania z indeksem map BDOT10k (PL) albo "
        "ETag/Last-Modified arkusza ZTM (CZ) bez pobierania danych",
    )
