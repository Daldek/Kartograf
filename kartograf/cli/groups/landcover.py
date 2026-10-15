"""``kartograf landcover``: BDOT10k (GUGiK) and CORINE Land Cover (ADR-039)."""

import argparse

from kartograf.cli._args import (
    OUTPUT_TITLE,
    SHEET_AREA_HELP,
    add_area_flags,
    add_quiet,
    add_update_flags,
    layer_codes,
)
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.cli.landcover_cmd import (
    SOURCE_CHOICES,
    cmd_landcover_download,
    cmd_landcover_list_layers,
)
from kartograf.sources.descriptor import SourceDescriptor

SOURCES = ("bdot10k", "corine")


def _source_flag(source: SourceDescriptor) -> str:
    """``--source`` of a descriptor: the last part of its key (``pl.gugik.bdot10k``)."""
    return f"--source {source.key.rsplit('.', 1)[-1]}"


def register(subparsers: argparse._SubParsersAction) -> None:
    """``landcover download``, ``list-sources`` and ``list-layers``."""
    commands = add_group(
        subparsers,
        "landcover",
        help="Pokrycie terenu: BDOT10k, CORINE Land Cover",
        description="Pokrycie terenu: wektorowa baza BDOT10k (GUGiK, PL) i CORINE "
        "Land Cover (Copernicus, UE) w magazynie wersji.",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz dane wybranego zrodla (--source)",
        description="Pobierz dane wybranego zrodla (--source) dla jednego "
        "obszaru: --teryt, --sheet, --bbox albo --geometry. BDOT10k obszaru "
        "= paczki kazdego powiatu, ktory obszar przecina (PRG).",
    )

    selection = download.add_argument_group("Zrodlo i obszar")
    selection.add_argument(
        "--source",
        "-s",
        choices=SOURCES,
        default=None,
        help=f"Zrodlo (wymagane): {SOURCE_CHOICES}",
    )
    selection.add_argument(
        "--teryt",
        metavar="KOD",
        help="Kod TERYT powiatu (4 cyfry, np. 1465; tylko BDOT10k)",
    )
    add_area_flags(
        selection,
        sheet_help=f"{SHEET_AREA_HELP}; BDOT10k: powiaty przecinajace arkusz",
    )

    options = download.add_argument_group("Parametry zrodla")
    options.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        default=None,
        help="Rok danych = wydanie (rok referencyjny) CORINE, wymagane dla "
        "corine: 2018, 2012, 2006, 2000 (edycje pokrycia terenu CLMS/WMS), 1990 "
        "(tylko podglad WMS)",
    )
    options.add_argument(
        "--format",
        "-f",
        choices=["GPKG", "SHP"],
        default=None,
        help="Tylko BDOT10k: GPKG (GeoPackage, domyslnie) lub SHP "
        "(archiwum ZIP z plikami Shapefile)",
    )
    options.add_argument(
        "--layers",
        metavar="KODY",
        type=layer_codes,
        default=None,
        help="Tylko BDOT10k GPKG: zostaw wybrane warstwy, kody po przecinku "
        "(np. SWRS,PTWP; lista: landcover list-layers); domyslnie wszystkie",
    )
    options.add_argument(
        "--keep-raw",
        action="store_true",
        help="Tylko BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok pliku "
        "(wersja surowa w magazynie)",
    )

    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; pliki trafiaja do "
        "<KATALOG>/landcover/... (wersje w versions/)",
    )
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: CORINE "
        "(CLMS) - wydanie zrodla; BDOT10k i podglad CORINE - brak taniego "
        "sygnalu (nie da sie sprawdzic bez pobrania)",
        upgrade_help="Pobierz nowsze wydanie CORINE (domyslnie tylko "
        "informacja); BDOT10k i podglad CORINE zostaja lokalne (pobranie: "
        "--force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik (BDOT10k: takze odswiez powiaty "
        "z PRG); ta sama tresc = bez zmian, inna = nowa wersja",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=1,
        help="Tylko BDOT10k obszaru (wiele powiatow): liczba rownoleglych "
        "pobran (domyslnie 1)",
    )
    add_quiet(output)
    download.set_defaults(_handler=cmd_landcover_download)

    add_list_sources(commands, "landcover", ("landcover",), _source_flag)

    layers = commands.add_parser(
        "list-layers",
        help="Wypisz warstwy wybranego zrodla",
        description="Wypisz warstwy BDOT10k albo lata CORINE (bez sieci)",
    )
    layers.add_argument(
        "--source",
        "-s",
        choices=SOURCES,
        default=None,
        help=f"Zrodlo (wymagane): {SOURCE_CHOICES}",
    )
    layers.set_defaults(_handler=cmd_landcover_list_layers)
