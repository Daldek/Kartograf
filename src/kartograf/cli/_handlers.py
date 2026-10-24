"""
The handler of every command of the CLI, by the id of the command (spec 8.2).

The parser of the catalog marks each parsed command line with the id of its
command (``_command_id``); ``HANDLERS`` maps that id to the function that
translates the line to the library. A group that shares a handler binds its own
arguments with ``functools.partial`` (``cmd_download(products=...)``,
``cmd_collection_download(group=...)``).
"""

import argparse
from collections.abc import Callable
from functools import partial

from kartograf.cli.availability_cmd import cmd_availability
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.catalog_cmd import (
    cmd_commands_guide,
    cmd_commands_list,
    cmd_commands_schema,
)
from kartograf.cli.collection_cmd import cmd_collection_download
from kartograf.cli.config_cmd import cmd_config_show
from kartograf.cli.download_cmd import cmd_download
from kartograf.cli.landcover_cmd import cmd_landcover_download
from kartograf.cli.layers_cmd import cmd_list_layers
from kartograf.cli.parse_cmd import cmd_find_sheets, cmd_parse
from kartograf.cli.project_cmd import (
    cmd_project_add,
    cmd_project_download,
    cmd_project_init,
    cmd_project_remove,
    cmd_project_status,
    cmd_project_verify,
)
from kartograf.cli.soil_cmd import cmd_soil_download, cmd_soil_hsg
from kartograf.cli.sources_cmd import cmd_list_sources
from kartograf.cli.store_cmd import (
    cmd_store_entries,
    cmd_store_overview,
    cmd_store_sidecar,
)
from kartograf.download.options import ELEVATION_PRODUCTS, IMAGERY_PRODUCTS
from kartograf.source_info import SOURCE_GROUPS

Handler = Callable[[argparse.Namespace], int]

# The groups whose ``download`` is ``download_collection`` (ADR-042).
COLLECTION_GROUPS = (
    "boundaries",
    "cadastre",
    "models3d",
    "hydro",
    "names",
    "maps",
    "geodesy",
)

HANDLERS: dict[str, Handler] = {
    "sheet parse": cmd_parse,
    "sheet find": cmd_find_sheets,
    "commands list": cmd_commands_list,
    "commands schema": cmd_commands_schema,
    "commands guide": cmd_commands_guide,
    "elevation download": partial(cmd_download, products=ELEVATION_PRODUCTS),
    "elevation availability": cmd_availability,
    "imagery download": partial(cmd_download, products=IMAGERY_PRODUCTS),
    "landcover download": cmd_landcover_download,
    "landcover list-layers": partial(cmd_list_layers, group="landcover"),
    "soil download": cmd_soil_download,
    "soil hsg": cmd_soil_hsg,
    "soil list-layers": partial(cmd_list_layers, group="soil"),
    **{
        f"{group} list-sources": partial(cmd_list_sources, group=group)
        for group in SOURCE_GROUPS
    },
    **{
        f"{group} download": partial(cmd_collection_download, group=group)
        for group in COLLECTION_GROUPS
    },
    "project init": cmd_project_init,
    "project add": cmd_project_add,
    "project remove": cmd_project_remove,
    "project download": cmd_project_download,
    "project status": cmd_project_status,
    "project verify": cmd_project_verify,
    "store overview": cmd_store_overview,
    "store entries": cmd_store_entries,
    "store sidecar": cmd_store_sidecar,
    "cache stats": partial(cmd_cache, action="stats"),
    "cache clear": partial(cmd_cache, action="clear"),
    "cache path": partial(cmd_cache, action="path"),
    "config show": cmd_config_show,
}
