"""``kartograf soil``: SoilGrids layers (ISRIC) and hydrologic soil groups (ADR-039)."""

from collections.abc import Callable
from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    OUTPUT_TITLE,
    PL_SHEETS,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.options import store_files
from kartograf.hydrology.hsg import HSG_OUTPUT_FILES
from kartograf.landcover.manager import soil_choices
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.registry import sources_for

_AREA_RULE = Constraint(
    "one_of",
    ("sheet", "bbox", "geometry"),
    "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
)


def _products() -> list[tuple[str, str]]:
    return [("soil", sources_for(product="soil")[0].name)]


def _described(kind: str) -> str:
    """Return the values of ``kind`` with their texts.

    The text is like ``bdod: gestosc objetosciowa (kg/dm3); ...``.
    """
    return "; ".join(f"{value}: {text}" for value, text in soil_choices()[kind].items())


def _depths(standard_only: bool = False) -> str:
    """Return the depth values of ``--depth`` with their explanation.

    All of them for ``soil download`` (``0-30cm`` only for ocs), the standard ones for
    HSG (clay, sand and silt are published at those only).
    """
    depths = soil_choices()["depth"]
    names = SoilGridsProvider.DEPTHS if standard_only else list(depths)
    note = "" if standard_only else "; 0-30cm tylko dla ocs"
    return f"{', '.join(names)} ({', '.join(dict.fromkeys(depths.values()))}{note})"


def _property_help() -> str:
    return f"Wymagane: {_described('property')}"


def _depth_help() -> str:
    return f"Wymagane: {_depths()}"


def _hsg_depth_help() -> str:
    return f"Wymagane: {_depths(standard_only=True)}"


def _stat_help() -> str:
    return f"Wymagane: {_described('stat')}"


def _values(kind: str) -> Callable[[], list[str]]:
    return lambda: list(soil_choices()[kind])


def _depth(standard_only: bool = False) -> Param:
    return Param(
        "depth",
        "str",
        _hsg_depth_help if standard_only else _depth_help,
        short="-d",
        metavar="GLEBOKOSC",
        allowed=(lambda: list(SoilGridsProvider.DEPTHS))
        if standard_only
        else _values("depth"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
    )


def _update(plan: str) -> tuple[Param, ...]:
    return shared.update_params(
        check="Porownaj lokalne wersje z wydaniem SoilGrids bez pobierania",
        upgrade="Pobierz nowsze wydanie SoilGrids (domyslnie tylko "
        "informacja); z --plan wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik; ta sama tresc = bez zmian, inna "
        "= nowa wersja",
        plan=plan,
    )


_PLAN = (
    "Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
    "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)"
)

_DOWNLOAD_PARAMS = (
    Param(
        "property",
        "str",
        _property_help,
        short="-p",
        metavar="WLASCIWOSC",
        allowed=_values("property"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
    ),
    _depth(),
    Param(
        "stat",
        "str",
        _stat_help,
        metavar="STATYSTYKA",
        allowed=_values("stat"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
    ),
    *shared.area(sheet=SHEET_AREA_HELP, accepts=PL_SHEETS),
    shared.output_dir(lambda: store_files(["soil"])),
    *_update(
        "Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)"
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_HSG_PARAMS = (
    _depth(standard_only=True),
    *shared.area(sheet=SHEET_AREA_HELP, accepts=PL_SHEETS),
    shared.output_dir(lambda: HSG_OUTPUT_FILES),
    *shared.update_params(
        check="Porownaj wejscia clay/sand/silt z wydaniem SoilGrids i HSG "
        "z wejsciami bez pobierania i bez liczenia",
        upgrade="Pobierz nowsze wydanie wejsc (domyslnie tylko informacja); "
        "HSG liczony tylko dla nowego zestawu wejsc; z --plan wykonaj plan",
        force="Pobierz ponownie wejscia; HSG liczony tylko, gdy tresc "
        "wejsc sie zmienila (inaczej uzyta ponownie)",
        plan=_PLAN,
    ),
    Param(
        "summary",
        "flag",
        "Wypisz podsumowanie HSG po obliczeniu: udzial i powierzchnia "
        "grup A-D oraz brak danych",
        default=False,
        section=OUTPUT_TITLE,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

COMMANDS = (
    Command(
        "soil download",
        "Pobierz warstwe SoilGrids (wlasciwosc, glebokosc, statystyka)",
        "data",
        "download_soil",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description="Pobierz jedna warstwe SoilGrids (--property, --depth, "
        "--stat; lista: kartograf soil list-layers) dla jednego obszaru: "
        "--sheet, --bbox albo --geometry.",
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_soil",
        check_result_schema="kartograf-plan/1",
        tool="soil_download",
        constraints=(_AREA_RULE,),
        examples=(
            Example(
                {
                    "property": "clay",
                    "depth": "0-5cm",
                    "stat": "mean",
                    "bbox": [626000, 480000, 628000, 482000],
                    "bbox_crs": "EPSG:2180",
                },
                title="Zawartosc ilu 0-5 cm dla prostokata",
            ),
            Example(
                {
                    "property": "soc",
                    "depth": "15-30cm",
                    "stat": "Q0.5",
                    "sheet": "N-34-130-D",
                },
                title="Wegiel organiczny 15-30 cm (mediana) dla arkusza",
            ),
        ),
    ),
    Command(
        "soil hsg",
        "Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
        "data",
        "calculate_hsg",
        "kartograf-download/1",
        _HSG_PARAMS,
        description="Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids "
        "dla wybranej glebokosci; uzyj statystyki mean (srednia) "
        "i oblicz grupy hydrologiczne HSG dla metody SCS-CN.",
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_hsg",
        check_result_schema="kartograf-plan/1",
        tool="soil_hsg",
        constraints=(_AREA_RULE,),
        examples=(
            Example(
                {
                    "depth": "0-5cm",
                    "bbox": [626000, 480000, 628000, 482000],
                    "bbox_crs": "EPSG:2180",
                },
                title="HSG dla prostokata z podsumowaniem",
                run={"summary": True},
            ),
        ),
    ),
    shared.list_sources_command("soil", lambda: ("soil",)),
    Command(
        "soil list-layers",
        "Wypisz wlasciwosci, glebokosci i statystyki SoilGrids",
        "query",
        "list_layers",
        "kartograf-layers/1",
        (
            Param(
                "group",
                "str",
                "Grupa komend (tu: soil); list_layers obsluguje landcover i soil",
                flag=None,
                required=True,
                allowed=("soil",),
            ),
            shared.JSON,
        ),
        description="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids "
        "(wartosci --property, --depth, --stat; bez sieci)",
        tool="list_layers",
    ),
)

GROUPS = (
    Group(
        "soil",
        "Gleby: SoilGrids i grupy hydrologiczne HSG",
        "Gleby: warstwy wlasciwosci SoilGrids (ISRIC, 250 m) i grupy "
        "hydrologiczne HSG obliczone z uziarnienia, w magazynie wersji.",
        products=_products,
    ),
)
