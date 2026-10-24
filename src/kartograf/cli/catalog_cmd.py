"""
``kartograf commands list`` and ``kartograf commands schema --command ID`` (spec 7.4).

The commands are queries: they read the catalog from the library (``list_commands``,
``command_schema``), need no network and write nothing. With ``--json`` they print the
envelope of the documents ``kartograf-command-list/1`` and ``kartograf-commands/1`` of
the library; without it, a text for a person (Polish until the message catalogue,
ADR-050): the groups with their products and commands, or the description of one
command with its parameters, rules, constraints and examples. The text is rendered from
the declarations, which have the Polish texts next to the English ones.
"""

import argparse
import sys
import textwrap

from kartograf.catalog import command_schema, list_commands
from kartograf.catalog.commands import declared, declared_commands
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import Command, Group, Param, resolve
from kartograf.cli._json import command_id, emit_result, wants_json

_WIDTH = 78
_LIST_FOOTER = (
    "Opis komendy z parametrami i przykladami: kartograf commands schema --command "
    '"<grupa> <komenda>". Dokument JSON: kartograf commands list --json.'
)


def _wrap(text: str, indent: str, first: str | None = None) -> list[str]:
    return textwrap.wrap(
        text,
        width=_WIDTH,
        initial_indent=indent if first is None else first,
        subsequent_indent=indent,
    )


def _command_lines(commands: list[Command], indent: str) -> list[str]:
    """One line per command: id, kind, summary."""
    id_width = max(len(c.id) for c in commands)
    kind_width = max(len(c.kind) for c in commands)
    return [
        f"{indent}{c.id.ljust(id_width)}  {c.kind.ljust(kind_width)}  {c.summary_pl}"
        for c in commands
    ]


def _group_view(group: Group, commands: list[Command]) -> list[str]:
    lines = [f"{group.name}: {group.summary_pl}"]
    lines += _wrap(group.description_pl, "  ")
    products = resolve(group.products)
    if products:
        lines.append("  Produkty:")
        for name, summary in products:
            lines += _wrap(f"{name} - {summary}", "      ", "    ")
    lines.append("  Komendy:")
    lines += _command_lines(commands, "    ")
    return lines


def format_list() -> str:
    """Return the text of ``kartograf commands list``.

    The groups in the order of ``kartograf --help`` with their products and one line
    per command (id, kind, summary), and where to read more.
    """
    declarations = declared()
    lines: list[str] = []
    for group in declarations.groups:
        commands = [c for c in declarations.commands if c.group == group.name]
        lines += [*_group_view(group, commands), ""]
    lines += _wrap(_LIST_FOOTER, "")
    return "\n".join(lines) + "\n"


def _flag(param: Param) -> str:
    if param.positional:
        return f"<{param.name}>"
    flag = param.cli_flag
    if flag is None:
        return "-"
    return flag if param.short is None else f"{flag}, {param.short}"


def _row(cells: tuple[str, ...], widths: list[int], indent: str) -> str:
    line = "  ".join(
        cell.ljust(width) for cell, width in zip(cells, widths, strict=True)
    )
    return f"{indent}{line}".rstrip()


def _param_lines(command: Command, indent: str) -> list[str]:
    """Return the parameters of a command.

    A table of flag, API argument, kind and whether it is required, each row followed by
    its allowed values and description.
    """
    params = command.params
    if not params:
        return []
    header = ("FLAGA", "ARGUMENT", "RODZAJ", "WYMAGANY")
    rows = [
        (_flag(p), p.api_argument or "-", p.kind, "tak" if p.required else "nie")
        for p in params
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    lines = ["Parametry:", _row(header, widths, indent)]
    for cells, param in zip(rows, params, strict=True):
        lines.append(_row(cells, widths, indent))
        allowed = resolve(param.allowed)
        if allowed:
            lines += _wrap("Dozwolone wartosci: " + ", ".join(allowed), indent + "    ")
        lines += _wrap(resolve(param.description_pl), indent + "    ")
    return lines


def _constraint_lines(command: Command) -> list[str]:
    if not command.constraints:
        return []
    return ["Ograniczenia:", *(f"  - {c.message_pl}" for c in command.constraints)]


def _rule_lines(command: Command) -> list[str]:
    if not command.rules_pl:
        return []
    return ["Zasady:", *(f"  - {rule}" for rule in command.rules_pl)]


def _example_lines(command: Command) -> list[str]:
    lines = ["Przyklady:"]
    for example in command.examples:
        lines.append(f"  {example.title_pl}:")
        lines.append(f"    {example_command_line(command, example)}")
    return lines


def format_command(command: Command) -> str:
    """Return the text of ``kartograf commands schema`` for one command.

    The summary and description, what the command is (kind, function, result, check,
    effects, the id of the operation), the parameters, the constraints and rules and
    the examples.
    """
    lines = [f"{command.id}: {command.summary_pl}", ""]
    lines += _wrap(resolve(command.description_pl), "")
    facts = [
        f"rodzaj: {command.kind}",
        f"funkcja: {command.function} -> {command.result_schema}",
    ]
    if command.check_function is not None:
        facts.append(
            f"sprawdzenie: {command.check_function} -> {command.check_result_schema}"
        )
    if command.effects:
        facts.append(f"skutki: {', '.join(command.effects)}")
    if command.project_task:
        facts.append("komenda danych projektu")
    facts.append(f"operation_id: {command.operation_id}")
    lines += ["", *_wrap("; ".join(facts), "")]
    for block in (
        _param_lines(command, "  "),
        _constraint_lines(command),
        _rule_lines(command),
    ):
        if block:
            lines += ["", *block]
    lines += ["", *_example_lines(command)]
    return "\n".join(lines) + "\n"


def cmd_commands_list(args: argparse.Namespace) -> int:
    """Print the list of the commands (``--json``: the library document)."""
    document = list_commands()
    if wants_json(args):
        return emit_result(command_id(args), document)
    sys.stdout.write(format_list())
    return 0


def cmd_commands_schema(args: argparse.Namespace) -> int:
    """Print one command (``--json``: the library document)."""
    document = command_schema(args.command)
    if wants_json(args):
        return emit_result(command_id(args), document)
    sys.stdout.write(format_command(declared_commands()[document.commands[0].name]))
    return 0
