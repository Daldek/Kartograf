"""``kartograf soil``: SoilGrids layers (ISRIC) and hydrologic soil groups (ADR-039)."""

import argparse

from kartograf.cli._args import (
    OUTPUT_TITLE,
    SHEET_AREA_HELP,
    add_area_flags,
    add_quiet,
    add_update_flags,
)
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.cli.soil_cmd import cmd_soil_download, cmd_soil_hsg, cmd_soil_list_layers

_DEPTHS = (
    "0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm (przedzial glebokosci "
    "ponizej powierzchni)"
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """``soil download``, ``hsg``, ``list-sources`` and ``list-layers``."""
    commands = add_group(
        subparsers,
        "soil",
        help="Gleby: SoilGrids i grupy hydrologiczne HSG",
        description="Gleby: warstwy wlasciwosci SoilGrids (ISRIC, 250 m) i grupy "
        "hydrologiczne HSG obliczone z uziarnienia, w magazynie wersji.",
    )

    download = commands.add_parser(
        "download",
        help="Pobierz warstwe SoilGrids (wlasciwosc, glebokosc, statystyka)",
        description="Pobierz jedna warstwe SoilGrids (--property, --depth, "
        "--stat) dla jednego obszaru: --sheet, --bbox albo --geometry.",
    )
    add_area_flags(download.add_argument_group("Obszar"), sheet_help=SHEET_AREA_HELP)
    layer = download.add_argument_group("Warstwa SoilGrids (lista: soil list-layers)")
    layer.add_argument(
        "--property",
        "-p",
        metavar="WLASCIWOSC",
        default=None,
        help="Wymagane: bdod (gestosc objetosciowa), cec (pojemnosc sorpcyjna), "
        "cfvo (frakcja szkieletowa), clay (il), nitrogen (azot), ocd (gestosc "
        "wegla organicznego), ocs (zasob wegla organicznego), phh2o (pH), sand "
        "(piasek), silt (pyl), soc (wegiel organiczny)",
    )
    layer.add_argument(
        "--depth", "-d", metavar="GLEBOKOSC", default=None, help=f"Wymagane: {_DEPTHS}"
    )
    layer.add_argument(
        "--stat",
        metavar="STATYSTYKA",
        default=None,
        help="Wymagane: mean (srednia), Q0.05 (5. percentyl), Q0.5 (mediana), "
        "Q0.95 (95. percentyl), uncertainty (niepewnosc predykcji)",
    )
    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; pliki trafiaja do <KATALOG>/soil/... "
        "(wersje w versions/)",
    )
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje z wydaniem SoilGrids bez pobierania",
        upgrade_help="Pobierz nowsze wydanie SoilGrids (domyslnie tylko "
        "informacja); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik; ta sama tresc = bez zmian, inna "
        "= nowa wersja",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    add_quiet(output)
    download.set_defaults(_handler=cmd_soil_download)

    hsg = commands.add_parser(
        "hsg",
        help="Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
        description=(
            "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids "
            "dla wybranej glebokosci; uzyj statystyki mean (srednia) "
            "i oblicz grupy hydrologiczne HSG dla metody SCS-CN."
        ),
    )
    add_area_flags(hsg.add_argument_group("Obszar"), sheet_help=SHEET_AREA_HELP)
    params = hsg.add_argument_group("Parametry HSG")
    params.add_argument(
        "--depth", "-d", metavar="GLEBOKOSC", default=None, help=f"Wymagane: {_DEPTHS}"
    )
    params.add_argument(
        "--stats",
        action="store_true",
        help="Wypisz statystyki HSG po obliczeniu",
    )
    output = hsg.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; wejscia w <KATALOG>/soil/..., HSG w "
        "<KATALOG>/hsg/... (plik poza magazynem: hsg_from_rasters)",
    )
    add_update_flags(
        output,
        check_help="Porownaj wejscia clay/sand/silt z wydaniem SoilGrids i HSG "
        "z wejsciami bez pobierania i bez liczenia",
        upgrade_help="Pobierz nowsze wydanie wejsc (domyslnie tylko informacja); "
        "HSG liczony tylko dla nowego zestawu wejsc; z --plan wykonaj plan",
        force_help="Pobierz ponownie wejscia; HSG liczony tylko, gdy tresc "
        "wejsc sie zmienila (inaczej uzyta ponownie)",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    add_quiet(output)
    hsg.set_defaults(_handler=cmd_soil_hsg)

    add_list_sources(commands, "soil", ("soil",))

    commands.add_parser(
        "list-layers",
        help="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids",
        description="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids "
        "(wartosci --property, --depth, --stat; bez sieci)",
    ).set_defaults(_handler=cmd_soil_list_layers)
