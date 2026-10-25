"""Declare the commands outside the data groups.

``sheet parse`` and ``sheet find``, ``commands list``, ``commands schema`` and
``commands guide``, the ``cache`` group and the read access to the store
(``store overview``, ``store entries``, ``store sidecar``).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Group,
    Param,
)
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000
from kartograf.core.sheet_parser import PL_BBOX_CRS, SheetParser
from kartograf.messages import message


def _command_ids() -> list[str]:
    return [command.id for command in declared().commands]


def _guide_formats() -> tuple[str, ...]:
    from kartograf.guide import GUIDE_FORMATS  # it imports the catalog

    return GUIDE_FORMATS


def _scales() -> list[str]:
    """Return the scales of the sheets of either PL sheet system, coarsest first."""
    return list(dict.fromkeys([*SheetParser.SCALE_HIERARCHY, *SCALE_HIERARCHY_2000]))


def _scale_help() -> str:
    return message(
        "catalog_misc.scale_description",
        scale_hierarchy=", ".join(SheetParser.SCALE_HIERARCHY),
        scale_hierarchy_2000=", ".join(SCALE_HIERARCHY_2000),
    )


def _bbox_crs_help() -> str:
    return message(
        "catalog_misc.bbox_crs_description", pl_bbox_crs=", ".join(PL_BBOX_CRS)
    )


_PARSE_PARAMS = (
    Param(
        "sheet",
        "str",
        message("catalog_misc.sheet_description"),
        positional=True,
        required=True,
        metavar=message("catalog.metavar_sheet"),
        normalize="strip",
        examples=("N-34-130-D-d-2-4",),
    ),
    Param(
        "hierarchy",
        "flag",
        message("catalog_misc.hierarchy_description"),
        default=False,
    ),
    Param(
        "children",
        "flag",
        message("catalog_misc.children_description"),
        default=False,
    ),
    Param(
        "descendants",
        "str",
        message("catalog_misc.descendants_description"),
        metavar=message("catalog.metavar_scale"),
    ),
    shared.JSON,
)

_SCHEMA_PARAMS = (
    Param(
        "command",
        "str",
        message("catalog_misc.command_description"),
        required=True,
        metavar=message("catalog.metavar_command"),
        allowed=_command_ids,
        examples=("elevation download",),
    ),
    shared.JSON,
)

_GUIDE_PARAMS = (
    Param(
        "format",
        "str",
        message("catalog_misc.format_description"),
        default="agents",
        allowed=_guide_formats,
        choices=True,
        metavar=message("catalog.metavar_kind"),
    ),
    Param(
        "inject",
        "path",
        message("catalog_misc.inject_description"),
        argument=None,
        path_role="output",
        metavar=message("catalog.metavar_file"),
    ),
    shared.JSON,
)

_FIND_SHEETS_PARAMS = (
    Param(
        "bbox",
        "bbox",
        message("catalog_misc.bbox_description"),
        metavar="BBOX",
    ),
    Param(
        "bbox_crs",
        "bbox_crs",
        _bbox_crs_help,
        allowed=lambda: PL_BBOX_CRS,
        choices=True,
        normalize="upper",
        cli_default="EPSG:2180",
    ),
    Param(
        "geometry",
        "path",
        message("catalog_misc.geometry_description"),
        metavar=message("catalog.metavar_file"),
        path_role="input",
    ),
    Param(
        "layer",
        "str",
        message("catalog_misc.layer_description"),
        metavar=message("catalog.metavar_name"),
    ),
    Param(
        "scale",
        "str",
        _scale_help,
        required=True,
        allowed=_scales,
        metavar=message("catalog.metavar_scale"),
    ),
    Param(
        "sheet_system",
        "str",
        message("catalog_misc.sheet_system_description"),
        required=True,
        allowed=lambda: SheetParser.VALID_SYSTEMS,
        choices=True,
    ),
    shared.JSON,
)

_ROOT = replace(
    shared.ROOT,
    description=message("catalog_misc.root_description"),
    section=None,
)

_INIT_ROOT = replace(
    _ROOT,
    description=message("catalog_misc.init_root_root_description"),
)

_STORE_ENTRIES_PARAMS = (
    _ROOT,
    Param(
        "segment",
        "str",
        message("catalog_misc.segment_description"),
        required=True,
        metavar="SEGMENT",
    ),
    Param(
        "units",
        "str_list",
        message("catalog_misc.units_description"),
        metavar=message("catalog.metavar_units"),
    ),
    Param(
        "limit",
        "int",
        message("catalog_misc.limit_description"),
        required=True,
        metavar="N",
        minimum=1,
    ),
    shared.JSON,
)

_STORE_SIDECAR_PARAMS = (
    Param(
        "path",
        "path",
        message("catalog_misc.path_description"),
        required=True,
        metavar=message("catalog.metavar_file"),
        path_role="input",
    ),
    shared.JSON,
)

COMMANDS = (
    Command(
        "sheet parse",
        message("catalog_misc.sheet_parse_summary"),
        "query",
        "describe_sheet",
        "kartograf-sheet/1",
        _PARSE_PARAMS,
        description=message("catalog_misc.sheet_parse_description"),
        examples=(
            Example(
                {"sheet": "N-34-130-D-d-2-4"},
                title=message("catalog_misc.example_pl_1992_sheet_code"),
            ),
            Example(
                {"sheet": "N-34-130-D", "descendants": "1:10000"},
                title=message("catalog_misc.example_descendant_sheets_down_1_10000"),
            ),
            Example(
                {"sheet": "6.179.12.20"},
                title=message("catalog_misc.example_pl_2000_sheet_code"),
            ),
            Example(
                {"sheet": "CTES96"},
                title=message("catalog_misc.example_cz_code_sm5_sheet"),
            ),
        ),
        rules=(),
        errors=("validation_error",),
        family="discovery",
    ),
    Command(
        "commands list",
        message("catalog_misc.commands_list_summary"),
        "query",
        "list_commands",
        "kartograf-command-list/1",
        (shared.JSON,),
        description=message("catalog_misc.commands_list_description"),
        examples=(
            Example(
                {},
                title=message("catalog_misc.example_groups_products_commands"),
            ),
            Example(
                {},
                title=message("catalog_misc.example_same_json_document"),
                run={"json": True},
            ),
        ),
        rules=(),
        errors=(),
        family="discovery",
        core=True,
        cardinality="bounded",
    ),
    Command(
        "commands schema",
        message("catalog_misc.commands_schema_summary"),
        "query",
        "command_schema",
        "kartograf-commands/1",
        _SCHEMA_PARAMS,
        description=message("catalog_misc.commands_schema_description"),
        examples=(
            Example(
                {"command": "elevation download"},
                title=message("catalog_misc.example_schema_data_command"),
            ),
            Example(
                {"command": "kartograf_soil_hsg"},
                title=message("catalog_misc.example_schema_command_operation_id_json"),
                run={"json": True},
            ),
        ),
        rules=(),
        errors=("validation_error",),
        family="discovery",
        core=True,
        cardinality="single",
    ),
    Command(
        "commands guide",
        message("catalog_misc.commands_guide_summary"),
        "query",
        "agent_guide",
        "kartograf-guide/1",
        _GUIDE_PARAMS,
        description=message("catalog_misc.commands_guide_description"),
        examples=(
            Example(
                {"format": "llms"},
                title=message("catalog_misc.example_llms_txt_kartograf"),
            ),
            Example(
                {"format": "agents-md-block"},
                title=message("catalog_misc.example_compact_block_json"),
                run={"json": True},
            ),
        ),
        rules=(message("catalog_misc.commands_guide_rule"),),
        errors=("validation_error",),
        cardinality="single",
    ),
    Command(
        "cache stats",
        message("catalog_misc.cache_stats_summary"),
        "query",
        "get_cache_info",
        "kartograf-cache/1",
        (shared.JSON,),
        description=message("catalog_misc.cache_stats_description"),
        rules=(),
        errors=(
            "validation_error",
            "store_unavailable",
            "io_error",
        ),
        examples=(
            Example(
                {},
                title=message("catalog_misc.example_statistics_metadata_cache"),
            ),
        ),
    ),
    Command(
        "cache clear",
        message("catalog_misc.cache_clear_summary"),
        "manage",
        "clear_cache",
        "kartograf-cache/1",
        (shared.JSON,),
        description=message("catalog_misc.cache_clear_description"),
        effects=("cache_delete",),
        destructive=True,
        rules=(),
        errors=(
            "validation_error",
            "store_unavailable",
            "io_error",
        ),
        examples=(
            Example(
                {},
                title=message("catalog_misc.example_delete_every_cache_entry"),
            ),
        ),
    ),
    Command(
        "cache path",
        message("catalog_misc.cache_path_summary"),
        "query",
        "get_cache_path",
        "kartograf-cache/1",
        (shared.JSON,),
        description=message("catalog_misc.cache_path_description"),
        rules=(),
        errors=(
            "validation_error",
            "io_error",
        ),
        examples=(Example({}, title=message("catalog_misc.example_path_cache_file")),),
    ),
    Command(
        "sheet find",
        message("catalog_misc.sheet_find_summary"),
        "query",
        "find_sheets",
        "kartograf-sheets/1",
        _FIND_SHEETS_PARAMS,
        description=message("catalog_misc.sheet_find_description"),
        constraints=(
            Constraint(
                "one_of",
                ("bbox", "geometry"),
                message("catalog_misc.rule_give_exactly_one_area_bbox_geometry"),
            ),
            Constraint(
                "requires",
                ("geometry",),
                message(
                    "catalog_misc.rule_layer_applies_only_geometry_layer_gpkg_file"
                ),
                "layer",
            ),
        ),
        examples=(
            Example(
                {
                    "bbox": [565000, 242000, 566000, 243000],
                    "bbox_crs": "EPSG:2180",
                    "scale": "1:10000",
                    "sheet_system": "1992",
                },
                title=message("catalog_misc.example_pl_1992_1_10000_sheets_rectangle"),
            ),
            Example(
                {
                    "geometry": "zlewnia.gpkg",
                    "scale": "1:2000",
                    "sheet_system": "2000",
                },
                title=message("catalog_misc.example_pl_2000_1_2000_sheets_geometry"),
            ),
        ),
        rules=(message("catalog_misc.sheet_find_rule"),),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="discovery",
        core=True,
        cardinality="unbounded",
    ),
    Command(
        "store overview",
        message("catalog_misc.store_overview_summary"),
        "query",
        "describe_store",
        "kartograf-store-overview/1",
        (_ROOT, shared.JSON),
        description=message("catalog_misc.store_overview_description"),
        examples=(
            Example(
                {},
                title=message("catalog_misc.example_segments_store_data"),
            ),
        ),
        rules=(),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="store",
        core=True,
        cardinality="bounded",
    ),
    Command(
        "store entries",
        message("catalog_misc.store_entries_summary"),
        "query",
        "list_store_entries",
        "kartograf-store-entries/1",
        _STORE_ENTRIES_PARAMS,
        description=message("catalog_misc.store_entries_description"),
        examples=(
            Example(
                {"segment": "nmt/pl_1992_1m_evrf2007", "limit": 20},
                title=message("catalog_misc.example_first_20_entries_segment"),
            ),
            Example(
                {
                    "segment": "nmt/pl_1992_1m_evrf2007",
                    "limit": 5,
                    "units": ["N-34-130-D-d-2-4"],
                },
                title=message("catalog_misc.example_entries_one_sheet"),
            ),
        ),
        rules=(message("catalog_misc.store_entries_rule"),),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="store",
        cardinality="bounded",
    ),
    Command(
        "store sidecar",
        message("catalog_misc.store_sidecar_summary"),
        "query",
        "read_store_sidecar",
        "kartograf-store-sidecar/1",
        _STORE_SIDECAR_PARAMS,
        description=message("catalog_misc.store_sidecar_description"),
        examples=(
            Example(
                {"path": "./data/nmt/pl_1992_1m_evrf2007/N-34-130-D-d-2-4.asc"},
                title=message("catalog_misc.example_sidecar_store_file"),
            ),
        ),
        rules=(),
        errors=(
            "validation_error",
            "data_error",
            "io_error",
            "forbidden",
        ),
        family="store",
    ),
    Command(
        "store init",
        message("catalog_misc.store_init_summary"),
        "manage",
        "init_store",
        "kartograf-store-init/1",
        (_INIT_ROOT, shared.JSON),
        description=message("catalog_misc.store_init_description"),
        effects=("store_write",),
        examples=(
            Example(
                {},
                title=message("catalog_misc.example_mark_store_data"),
            ),
        ),
        rules=(
            message("catalog_misc.store_init_rule_1"),
            message("catalog_misc.store_init_rule_2"),
        ),
        errors=(
            "validation_error",
            "conflict",
            "data_error",
            "io_error",
            "forbidden",
        ),
        family="store",
    ),
)

GROUPS = (
    Group(
        "cache",
        message("catalog_misc.cache_group_summary"),
        message("catalog_misc.cache_group_description"),
        position=2,
    ),
    Group(
        "commands",
        message("catalog_misc.commands_group_summary"),
        message("catalog_misc.commands_group_description"),
        position=2,
    ),
    Group(
        "sheet",
        message("catalog_misc.sheet_group_summary"),
        message("catalog_misc.sheet_group_description"),
    ),
    Group(
        "store",
        message("catalog_misc.store_group_summary"),
        message("catalog_misc.store_group_description"),
    ),
)
