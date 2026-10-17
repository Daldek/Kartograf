"""``kartograf maps``: BDOT10k visualizations (PL) and ZTM sheets (CZ)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_choice_values


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    for flag, metavar, label in (
        ("scale", "SKALA", "Skala mapy (wymagana)"),
        ("format", "FORMAT", "Format pliku (wymagany)"),
        (
            "sheet_system",
            "UKLAD",
            "Tylko ZTM (CZ): uklad arkuszy - wymagany z --bbox/--geometry, "
            "z --sheet wynika z godla; mapy BDOT10k (PL) maja arkusze PL-1992 "
            "(pomin --sheet-system)",
        ),
    ):
        choices = "; ".join(
            f"{product} {country}: {', '.join(values)}"
            for product in products
            for country, values in collection_choice_values(product, flag).items()
        )
        content.add_argument(
            f"--{flag.replace('_', '-')}",
            metavar=metavar,
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
        description="--product topographic: wizualizacje BDOT10k (--country pl; "
        "arkusze PL-1992, bez --sheet-system) albo ZTM (--country cz). --scale "
        "i --format sa wymagane. ZTM (CZ): uklad arkuszy --sheet-system "
        "sjtsk|etrs89 wynika z godla, dla --bbox/--geometry jest wymagany. ZTM "
        "TIFF, DGN i SHP sa ZIP-ami, PDF jest plikiem .pdf; BDOT10k TIFF i PDF "
        "sa oryginalnymi plikami z indeksu map.",
        area_result="arkusze map przecinajace obszar (pliki oryginalne)",
        examples_of=(
            "kartograf maps download --product topographic --country pl --sheet "
            "M-34-064-D-d-1 --scale 1:10000 --format TIFF -o ./data",
            "kartograf maps download --product topographic --country cz --sheet "
            "0510-D-11 --scale 1:10000 --format TIFF -o ./data",
            "kartograf maps download --product topographic --country cz --bbox "
            "-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514 --scale 1:10000 "
            "--sheet-system sjtsk --format PDF -o ./data",
        ),
        content=_content,
        sheet_help="Godlo mapy: PL-1992 (--country pl) albo ZTM w S-JTSK/ETRS89 "
        "(--country cz; uklad arkuszy wynika z godla)",
        check_help="Porownaj etykiete wydania z indeksem map BDOT10k (PL) albo "
        "ETag/Last-Modified arkusza ZTM (CZ) bez pobierania danych",
    )
