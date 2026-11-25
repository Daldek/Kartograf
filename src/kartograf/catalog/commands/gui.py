"""``kartograf gui``: the page of plans and scripts on this computer (ADR-063).

``gui serve`` serves the page with the read-only ``/api/v1`` of ``kartograf server`` in
one process until Ctrl+C or ``SIGTERM``. A person starts it, so it is no MCP tool, and
``kartograf server`` does not serve it (``rest`` is ``null``: a local group). Its plans
use the network and the metadata cache; it never writes data.
"""

from kartograf.catalog import shared
from kartograf.catalog.spec import Command, Example, Group, Param
from kartograf.messages import message
from kartograf.server.serving import DEFAULT_HOST, DEFAULT_PORT

_MAX_PORT = 65535
_EXAMPLE_PORT = 8066

COMMANDS = (
    Command(
        "gui serve",
        message("catalog_gui.serve_summary"),
        "query",
        "serve_gui",
        "kartograf-gui/1",
        (
            Param(
                "host",
                "str",
                message("catalog_gui.host_description"),
                default=DEFAULT_HOST,
                metavar=message("catalog_gui.metavar_host"),
            ),
            Param(
                "port",
                "int",
                message("catalog_gui.port_description"),
                default=DEFAULT_PORT,
                minimum=0,
                maximum=_MAX_PORT,
            ),
            Param(
                "no_browser",
                "flag",
                message("catalog_gui.no_browser_description"),
                default=False,
            ),
            shared.JSON,
        ),
        description=message("catalog_gui.serve_description"),
        effects=("network",),
        examples=(
            Example(
                {"port": _EXAMPLE_PORT, "no_browser": True},
                title=message("catalog_gui.example_serve_without_browser"),
                result={
                    "schema": "kartograf-gui/1",
                    "url": f"http://{DEFAULT_HOST}:{_EXAMPLE_PORT}/",
                    "started_at": "2026-11-25T10:00:00+00:00",
                    "stopped_at": "2026-11-25T12:00:00+00:00",
                },
            ),
        ),
        rules=(message("catalog_gui.serve_rule"),),
        errors=("validation_error", "missing_dependency", "conflict"),
    ),
)

GROUPS = (
    Group(
        "gui",
        message("catalog_gui.group_summary"),
        message("catalog_gui.group_description"),
        position=2,
    ),
)
