"""``kartograf soil``: SoilGrids layers (ISRIC) and hydrologic soil groups (ADR-039)."""

import argparse

from kartograf.cli._args import (
    OUTPUT_TITLE,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
    add_area_flags,
    add_output,
    add_quiet,
    add_update_flags,
    examples,
)
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.cli.soil_cmd import (
    cmd_soil_download,
    cmd_soil_hsg,
    cmd_soil_list_layers,
    soil_download_task_arguments,
    soil_hsg_task_arguments,
)
from kartograf.download.options import store_files
from kartograf.hydrology.hsg import HSG_OUTPUT_FILES
from kartograf.landcover.manager import soil_choices

_CHOICES = soil_choices()
_DEPTHS = (
    f"{', '.join(_CHOICES['depth'])} "
    f"({', '.join(dict.fromkeys(_CHOICES['depth'].values()))})"
)


def _described(descriptions: dict[str, str]) -> str:
    """``bdod: gestosc objetosciowa (kg/dm3); ...``: values with their texts
    (``%`` escaped for argparse help)."""
    text = "; ".join(f"{value}: {text}" for value, text in descriptions.items())
    return text.replace("%", "%%")


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
        "--stat; lista: kartograf soil list-layers) dla jednego obszaru: "
        "--sheet, --bbox albo --geometry.",
        epilog=examples(
            "kartograf soil download --property clay --depth 0-5cm --stat mean "
            "--bbox 626000,480000,628000,482000 -o ./data",
            "kartograf soil download --property soc --depth 15-30cm --stat Q0.5 "
            "--sheet N-34-130-D -o ./data",
        ),
    )
    layer = download.add_argument_group(SELECTION_TITLE)
    layer.add_argument(
        "--property",
        "-p",
        metavar="WLASCIWOSC",
        default=None,
        help=f"Wymagane: {_described(_CHOICES['property'])}",
    )
    layer.add_argument(
        "--depth", "-d", metavar="GLEBOKOSC", default=None, help=f"Wymagane: {_DEPTHS}"
    )
    layer.add_argument(
        "--stat",
        metavar="STATYSTYKA",
        default=None,
        help=f"Wymagane: {_described(_CHOICES['stat'])}",
    )
    add_area_flags(layer, sheet_help=SHEET_AREA_HELP)
    output = download.add_argument_group(OUTPUT_TITLE)
    add_output(output, store_files(["soil"]))
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
    download.set_defaults(
        _handler=cmd_soil_download, _task=soil_download_task_arguments
    )

    hsg = commands.add_parser(
        "hsg",
        help="Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
        description=(
            "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids "
            "dla wybranej glebokosci; uzyj statystyki mean (srednia) "
            "i oblicz grupy hydrologiczne HSG dla metody SCS-CN."
        ),
        epilog=examples(
            "kartograf soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 "
            "--summary -o ./data",
        ),
    )
    params = hsg.add_argument_group(SELECTION_TITLE)
    params.add_argument(
        "--depth", "-d", metavar="GLEBOKOSC", default=None, help=f"Wymagane: {_DEPTHS}"
    )
    add_area_flags(params, sheet_help=SHEET_AREA_HELP)
    output = hsg.add_argument_group(OUTPUT_TITLE)
    add_output(output, HSG_OUTPUT_FILES)
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
    output.add_argument(
        "--summary",
        action="store_true",
        help="Wypisz podsumowanie HSG po obliczeniu: udzial i powierzchnia "
        "grup A-D oraz brak danych",
    )
    add_quiet(output)
    hsg.set_defaults(_handler=cmd_soil_hsg, _task=soil_hsg_task_arguments)

    add_list_sources(
        commands,
        "soil",
        ("soil",),
        lambda _source: "--property WLASCIWOSC --depth GLEBOKOSC --stat STATYSTYKA",
    )

    commands.add_parser(
        "list-layers",
        help="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids",
        description="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids "
        "(wartosci --property, --depth, --stat; bez sieci)",
    ).set_defaults(_handler=cmd_soil_list_layers)
