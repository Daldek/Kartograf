"""Catalog of the Kartograf commands (spec 8).

The declarations of every command, the documents ``kartograf-command-list/1`` and
``kartograf-commands/1`` built from them (``list_commands``, ``command_schema``) and
the CLI parser built from them.

The package imports nothing from ``kartograf.cli`` and nothing of the MCP
server: the library describes its commands, the CLI and the server only
translate them.
"""

from kartograf.catalog.build import command_schema, list_commands

__all__ = ["command_schema", "list_commands"]
