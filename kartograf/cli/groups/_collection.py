"""
``download`` and ``list-sources`` of a collection group (``boundaries``,
``cadastre``, ``models3d``, ``hydro``; ADR-042 D9).

Every collection group has the same command shape: ``--product`` and
``--country`` like ``elevation``/``imagery``, one selection (``--teryt``,
``--sheet``/``--bbox``/``--geometry``, in some groups ``--whole-country``),
the content flags of the group only (``--level``, ``--lod``/``--year``),
the store flags and ``--workers`` (default 1). ``--teryt`` and ``--sheet``
select PL units and sheet codes: a group without PL sources (``hydro``) has
neither. The choices in ``--help`` come from the source registry through
the library.
"""

import argparse
from collections.abc import Callable
from functools import partial

from kartograf.cli._args import (
    BBOX_HELP,
    GEOMETRY_HELP,
    OUTPUT_TITLE,
    SHEET_AREA_HELP,
    add_area_flags,
    add_quiet,
    add_update_flags,
)
from kartograf.cli.collection_cmd import cmd_collection_download, collection_task
from kartograf.cli.groups import add_list_sources
from kartograf.download.collections import (
    collection_product_choices,
    collection_products,
)
from kartograf.download.options import COUNTRIES, COUNTRY_CHOICES
from kartograf.sources.descriptor import SourceDescriptor


def _source_choice(source: SourceDescriptor) -> str:
    """Flags selecting ``source`` in a collection ``download``."""
    return f"--product {source.product} --country {source.country.lower()}"


def add_collection_commands(
    commands: argparse._SubParsersAction,
    group: str,
    *,
    help: str,
    description: str,
    area_result: str,
    teryt_help: str | None = None,
    sheet: bool = True,
    whole_country_help: str | None = None,
    content: Callable[[argparse._ArgumentGroup, tuple[str, ...]], None] | None = None,
) -> None:
    """``<group> download`` and ``<group> list-sources``.

    ``area_result``: what an area gives (help of the area flags);
    ``teryt_help``: the group has ``--teryt``; ``sheet``: the group has
    ``--sheet`` (``False``: no PL source - the area of a sheet code is PL
    only); ``whole_country_help``: the group has ``--whole-country``;
    ``content`` adds the content flags of the group (it gets the group's
    products).
    """
    products = collection_products(group)
    download = commands.add_parser("download", help=help, description=description)

    selection = download.add_argument_group("Produkt i wybor")
    selection.add_argument(
        "--product",
        choices=products,
        default=None,
        help=f"Produkt (wymagany): {collection_product_choices(products)}",
    )
    pl_selections = [
        text
        for text, given in (
            ("Z --teryt tylko pl", teryt_help is not None),
            ("Z --sheet kraj wynika z godla", sheet),
        )
        if given
    ]
    selection.add_argument(
        "--country",
        choices=COUNTRIES,
        default=None,
        help="Kraj zrodla - wymagany z --bbox/--geometry"
        + (" i --whole-country (bez auto)" if whole_country_help else "")
        + f": {COUNTRY_CHOICES}"
        + "".join(f". {text}" for text in pl_selections),
    )
    if teryt_help is not None:
        selection.add_argument("--teryt", metavar="KOD", help=teryt_help)
    add_area_flags(
        selection,
        sheet_help=f"{SHEET_AREA_HELP}; {area_result}" if sheet else None,
        bbox_help=f"{BBOX_HELP}; {area_result}",
        geometry_help=f"{GEOMETRY_HELP}; {area_result}",
    )
    if whole_country_help is not None:
        selection.add_argument(
            "--whole-country", action="store_true", help=whole_country_help
        )
    if content is not None:
        content(download.add_argument_group("Zawartosc"), products)

    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help=f"Wymagane: katalog magazynu; pliki trafiaja do <KATALOG>/{group}/... "
        "(wersje w versions/)",
    )
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: plik "
        "z sygnalem zrodla (naglowki HTTP plikow krajowych CUZK) - porownanie "
        "bez pobrania; paczki GUGiK i obiekty obszaru nie maja taniego sygnalu "
        "(nie da sie sprawdzic bez pobrania), brakujace pliki = do pobrania",
        upgrade_help="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje; pliki "
        "bez taniego sygnalu zostaja lokalne (pobranie: --force); z --plan "
        "wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik zadania; ta sama tresc = bez "
        "zmian, inna = nowa wersja; nic nie jest nadpisywane",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=1,
        help="Liczba rownoleglych pobran jednostek (wiele paczek obszaru; domyslnie 1)",
    )
    add_quiet(output)
    download.set_defaults(
        _handler=partial(cmd_collection_download, group=group), _task=collection_task
    )

    add_list_sources(commands, group, products, _source_choice)
