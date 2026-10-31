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
from kartograf.messages import message
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.registry import sources_for

_AREA_RULE = Constraint(
    "one_of",
    ("sheet", "bbox", "geometry"),
    message("catalog_soil.rule_give_exactly_one_area_sheet_bbox_geometry"),
)


def _products() -> list[tuple[str, str]]:
    return [("soil", sources_for(product="soil")[0].name)]


def _described(kind: str) -> list[str]:
    """Return the values of ``kind`` with their texts.

    The items are like ``bdod: gestosc objetosciowa (kg/dm3)``, each one a message of
    its own so that the text of the value follows the language of the help.
    """
    return [
        message("catalog_soil.described_item", value=value, text=text)
        for value, text in soil_choices()[kind].items()
    ]


def _depths(standard_only: bool = False) -> str:
    """Return the depth values of ``--depth`` with their explanation.

    All of them for ``soil download`` (``0-30cm`` only for ocs), the standard ones for
    HSG (clay, sand and silt are published at those only).
    """
    depths = soil_choices()["depth"]
    names = SoilGridsProvider.DEPTHS if standard_only else list(depths)
    return message(
        "catalog_soil.depths_text",
        names=list(names),
        explanations=list(dict.fromkeys(depths.values())),
        note="" if standard_only else message("catalog_soil.depths_ocs_note"),
    )


def _property_help() -> str:
    return message(
        "catalog_soil.property_description", described=_described("property")
    )


def _depth_help() -> str:
    return message("catalog_soil.depth_description", depths=_depths())


def _hsg_depth_help() -> str:
    return message("catalog_soil.depth_description", depths=_depths(standard_only=True))


def _stat_help() -> str:
    return message("catalog_soil.stat_description", described=_described("stat"))


def _values(kind: str) -> Callable[[], list[str]]:
    return lambda: list(soil_choices()[kind])


def _depth(standard_only: bool = False) -> Param:
    return Param(
        "depth",
        "str",
        _hsg_depth_help if standard_only else _depth_help,
        short="-d",
        metavar=message("catalog.metavar_depth"),
        allowed=(lambda: list(SoilGridsProvider.DEPTHS))
        if standard_only
        else _values("depth"),
        required=True,
        section=SELECTION_TITLE,
    )


_PLAN = message("catalog_soil.plan_description", common=shared.PLAN_HELP)


def _update() -> tuple[Param, ...]:
    return shared.update_params(
        check=message("catalog_soil.check_description"),
        upgrade=message("catalog_soil.download_upgrade_description"),
        force=message("catalog_soil.download_force_description"),
        plan=_PLAN,
    )


_DOWNLOAD_PARAMS = (
    Param(
        "property",
        "str",
        _property_help,
        short="-p",
        metavar=message("catalog.metavar_property"),
        allowed=_values("property"),
        required=True,
        section=SELECTION_TITLE,
    ),
    _depth(),
    Param(
        "stat",
        "str",
        _stat_help,
        metavar=message("catalog.metavar_stat"),
        allowed=_values("stat"),
        required=True,
        section=SELECTION_TITLE,
    ),
    *shared.area(sheet=SHEET_AREA_HELP, accepts=PL_SHEETS),
    *shared.target(lambda: store_files(["soil"])),
    *_update(),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_HSG_PARAMS = (
    _depth(standard_only=True),
    *shared.area(sheet=SHEET_AREA_HELP, accepts=PL_SHEETS),
    *shared.target(lambda: HSG_OUTPUT_FILES),
    *shared.update_params(
        check=message("catalog_soil.check_description_2"),
        upgrade=message("catalog_soil.hsg_upgrade_description"),
        force=message("catalog_soil.hsg_force_description"),
        plan=_PLAN,
    ),
    Param(
        "summary",
        "flag",
        message("catalog_soil.summary_description"),
        default=False,
        section=OUTPUT_TITLE,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

COMMANDS = (
    Command(
        "soil download",
        message("catalog_soil.soil_download_summary"),
        "data",
        "download_soil",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=message(
            "catalog_soil.soil_download_description", note=shared.PLAIN_NOTE
        ),
        effects=("network", "store_write"),
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
                title=message("catalog_soil.example_clay_content_0_5_cm_rectangle"),
            ),
            Example(
                {
                    "property": "soc",
                    "depth": "15-30cm",
                    "stat": "Q0.5",
                    "sheet": "N-34-130-D",
                },
                title=message(
                    "catalog_soil.example_organic_carbon_15_30_cm_median_sheet"
                ),
            ),
        ),
        rules=(message("catalog_soil.soil_download_rule"),),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    Command(
        "soil hsg",
        message("catalog_soil.soil_hsg_summary"),
        "data",
        "calculate_hsg",
        "kartograf-download/1",
        _HSG_PARAMS,
        description=message("catalog_soil.soil_hsg_description"),
        effects=("network", "store_write"),
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
                title=message("catalog_soil.example_hsg_rectangle_summary"),
                run={"summary": True},
            ),
        ),
        rules=(message("catalog_soil.soil_hsg_rule"),),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("soil", lambda: ("soil",)),
    Command(
        "soil list-layers",
        message("catalog_soil.soil_list_layers_summary"),
        "query",
        "list_layers",
        "kartograf-layers/1",
        (
            Param(
                "group",
                "str",
                flag=None,
                required=True,
                description=message("catalog_soil.group_description"),
                fixed="soil",
            ),
            shared.JSON,
        ),
        description=message("catalog_soil.soil_list_layers_description"),
        rules=(),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {},
                title=message(
                    "catalog_soil.example_soilgrids_properties_depths_statistics"
                ),
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "soil",
        message("catalog_soil.soil_group_summary"),
        message("catalog_soil.soil_group_description"),
        products=_products,
    ),
)
