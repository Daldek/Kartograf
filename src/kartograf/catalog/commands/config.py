"""``kartograf config``: the settings in force (DEV-18.6, ADR-050)."""

from kartograf.catalog import shared
from kartograf.catalog.spec import Command, Example, Group
from kartograf.messages import message

COMMANDS = (
    Command(
        "config show",
        message("catalog_config.config_show_summary"),
        "query",
        "get_config",
        "kartograf-config/1",
        (shared.JSON,),
        description=message("catalog_config.config_show_description"),
        examples=(
            Example(
                {},
                title=message("catalog_config.example_settings_json_document"),
                run={"json": True},
            ),
        ),
        rules=(),
        errors=(),
    ),
)

GROUPS = (
    Group(
        "config",
        message("catalog_config.config_group_summary"),
        message("catalog_config.config_group_description"),
        position=2,
    ),
)
