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
        ("Depth interval below the surface (required); `0-30cm` only for `ocs`."),
        short="-d",
        metavar="GLEBOKOSC",
        allowed=(lambda: list(SoilGridsProvider.DEPTHS))
        if standard_only
        else _values("depth"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
        description_pl=_hsg_depth_help if standard_only else _depth_help,
    )


def _update(plan: str) -> tuple[Param, ...]:
    return shared.update_params(
        check=(
            "Compares the local versions with the SoilGrids release.",
            "Porownaj lokalne wersje z wydaniem SoilGrids bez pobierania",
        ),
        upgrade="Pobierz nowsze wydanie SoilGrids (domyslnie tylko "
        "informacja); z --plan wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik; ta sama tresc = bez zmian, inna "
        "= nowa wersja",
        plan=plan,
    )


_PLAN = (
    "Z --check: zapisz plan aktualizacji (kartograf-plan/1); "
    "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)"
)

_DOWNLOAD_PARAMS = (
    Param(
        "property",
        "str",
        (
            "SoilGrids property (required). Values stay in the SoilGrids "
            "units of the file; the meaning of each property gives its unit"
            " and conversion."
        ),
        short="-p",
        metavar="WLASCIWOSC",
        allowed=_values("property"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
        description_pl=_property_help,
    ),
    _depth(),
    Param(
        "stat",
        "str",
        "Statistic of the prediction (required).",
        metavar="STATYSTYKA",
        allowed=_values("stat"),
        required=True,
        task=True,
        section=SELECTION_TITLE,
        description_pl=_stat_help,
    ),
    *shared.area(
        sheet=(
            "Sheet code (for example N-34-130-D): the area is the extent of"
            " that sheet, as bbox with its corners.",
            SHEET_AREA_HELP,
        ),
        accepts=PL_SHEETS,
    ),
    *shared.target(lambda: store_files(["soil"])),
    *_update(
        "Z --check: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)"
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_HSG_PARAMS = (
    _depth(standard_only=True),
    *shared.area(
        sheet=(
            "Sheet code (for example N-34-130-D): the area is the extent of"
            " that sheet, as bbox with its corners.",
            SHEET_AREA_HELP,
        ),
        accepts=PL_SHEETS,
    ),
    *shared.target(lambda: HSG_OUTPUT_FILES),
    *shared.update_params(
        check=(
            "Compares the clay, sand and silt inputs with the SoilGrids "
            "release and the HSG with its inputs; nothing is computed.",
            (
                "Porownaj wejscia clay/sand/silt z wydaniem SoilGrids i HSG z "
                "wejsciami bez pobierania i bez liczenia"
            ),
        ),
        upgrade="Pobierz nowsze wydanie wejsc (domyslnie tylko informacja); "
        "HSG liczony tylko dla nowego zestawu wejsc; z --plan wykonaj plan",
        force="Pobierz ponownie wejscia; HSG liczony tylko, gdy tresc "
        "wejsc sie zmienila (inaczej uzyta ponownie)",
        plan=_PLAN,
    ),
    Param(
        "summary",
        "flag",
        (
            "Add the HSG summary after the calculation: the share and area "
            "of the groups A-D and of the cells without data."
        ),
        default=False,
        section=OUTPUT_TITLE,
        description_pl=(
            "Wypisz podsumowanie HSG po obliczeniu: udzial i powierzchnia "
            "grup A-D oraz brak danych"
        ),
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

COMMANDS = (
    Command(
        "soil download",
        ("Download one SoilGrids layer (property, depth, statistic) for an area"),
        "data",
        "download_soil",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Fetches one SoilGrids layer (ISRIC, 250 m) for an area given "
            "by `sheet`, `bbox` or `geometry`; values keep the SoilGrids "
            "units. For hydrologic soil groups use `soil hsg`. Never "
            f"overwrites: new content is a new version. {shared.PLAIN_NOTE}"
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_soil",
        check_result_schema="kartograf-plan/1",
        constraints=(_AREA_RULE, *shared.target_constraints()),
        examples=(
            Example(
                {
                    "property": "clay",
                    "depth": "0-5cm",
                    "stat": "mean",
                    "bbox": [626000, 480000, 628000, 482000],
                    "bbox_crs": "EPSG:2180",
                },
                title="Clay content at 0-5 cm for a rectangle",
                title_pl="Zawartosc ilu 0-5 cm dla prostokata",
            ),
            Example(
                {
                    "property": "soc",
                    "depth": "15-30cm",
                    "stat": "Q0.5",
                    "sheet": "N-34-130-D",
                },
                title="Organic carbon at 15-30 cm (median) for a sheet",
                title_pl="Wegiel organiczny 15-30 cm (mediana) dla arkusza",
            ),
        ),
        summary_pl="Pobierz warstwe SoilGrids (wlasciwosc, glebokosc, statystyka)",
        description_pl=(
            "Pobierz jedna warstwe SoilGrids (--property, --depth, --stat; "
            "lista: kartograf soil list-layers) dla jednego obszaru: "
            f"--sheet, --bbox albo --geometry. {shared.PLAIN_NOTE_PL}"
        ),
        rules=("Take `property`, `depth` and `stat` from `soil list-layers`.",),
        rules_pl=("Wez `property`, `depth` i `stat` z `soil list-layers`.",),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    Command(
        "soil hsg",
        ("Compute hydrologic soil groups (HSG) from SoilGrids texture for an area"),
        "data",
        "calculate_hsg",
        "kartograf-download/1",
        _HSG_PARAMS,
        description=(
            "Fetches the clay, sand and silt layers (statistic `mean`) of "
            "one depth for an area and computes the groups A-D for the "
            "SCS-CN method. Inputs and the HSG raster are stored as "
            "versions; the HSG is recomputed only when the inputs change. "
            "With `output_dir` only the HSG raster is written, as a plain file. "
            "For one SoilGrids layer use `soil download`."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_hsg",
        check_result_schema="kartograf-plan/1",
        constraints=(_AREA_RULE, *shared.target_constraints()),
        examples=(
            Example(
                {
                    "depth": "0-5cm",
                    "bbox": [626000, 480000, 628000, 482000],
                    "bbox_crs": "EPSG:2180",
                },
                title="HSG for a rectangle with the summary",
                run={"summary": True},
                title_pl="HSG dla prostokata z podsumowaniem",
            ),
        ),
        summary_pl="Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
        description_pl=(
            "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids dla "
            "wybranej glebokosci; uzyj statystyki mean (srednia) i oblicz "
            "grupy hydrologiczne HSG dla metody SCS-CN. Z --output-dir zapisuje "
            "tylko raster HSG, jako zwykly plik."
        ),
        rules=(("Give `depth`; add `summary` for the share and area of each group."),),
        rules_pl=(
            ("Podaj `depth`; `summary` dodaje udzial i powierzchnie kazdej grupy."),
        ),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("soil", lambda: ("soil",)),
    Command(
        "soil list-layers",
        "List the SoilGrids properties, depths and statistics (offline)",
        "query",
        "list_layers",
        "kartograf-layers/1",
        (
            Param(
                "group",
                "str",
                flag=None,
                required=True,
                description_pl=(
                    "Grupa komend (tu: soil); list_layers obsluguje landcover i soil"
                ),
                fixed="soil",
            ),
            shared.JSON,
        ),
        description=(
            "Lists the values of `property`, `depth` and `stat` of `soil "
            "download` with the units of each property. Use it to choose a "
            "layer."
        ),
        summary_pl="Wypisz wlasciwosci, glebokosci i statystyki SoilGrids",
        description_pl=(
            "Wypisz wlasciwosci, glebokosci i statystyki SoilGrids "
            "(wartosci --property, --depth, --stat; bez sieci)"
        ),
        rules=(),
        rules_pl=(),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {},
                title="The SoilGrids properties, depths and statistics",
                title_pl="Wlasciwosci, glebokosci i statystyki SoilGrids",
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "soil",
        "Soil: SoilGrids and hydrologic soil groups (HSG)",
        (
            "Soil in the versioned store: the SoilGrids property layers "
            "(ISRIC, 250 m) and the hydrologic soil groups (HSG) computed "
            "from the texture."
        ),
        products=_products,
        summary_pl="Gleby: SoilGrids i grupy hydrologiczne HSG",
        description_pl=(
            "Gleby: warstwy wlasciwosci SoilGrids (ISRIC, 250 m) i grupy "
            "hydrologiczne HSG obliczone z uziarnienia, w magazynie wersji."
        ),
    ),
)
