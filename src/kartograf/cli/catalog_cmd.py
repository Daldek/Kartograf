"""
``kartograf commands list``, ``commands schema --command ID`` and ``commands guide``.

The commands are queries: they read the catalog from the library (``list_commands``,
``command_schema``), need no network and write nothing. With ``--json`` they print the
envelope of the documents ``kartograf-command-list/1`` and ``kartograf-commands/1`` of
the library; without it, a text for a person (Polish until the message catalogue,
ADR-050): the groups with their products and commands, or the description of one
command with its parameters, rules, constraints and examples. The text is rendered from
the declarations, which have the Polish texts next to the English ones.

``commands guide`` prints the guide for agents of the library (``agent_guide``: English,
AGI-9.2) and, with ``--inject FILE``, puts its compact block into that file instead.
"""

import argparse
import contextlib
import os
import sys
import tempfile
import textwrap
from pathlib import Path

from kartograf.catalog import command_schema, list_commands
from kartograf.catalog.commands import declared, declared_commands
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import Command, Group, Param, resolve
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized, yes_no
from kartograf.exceptions import ValidationError
from kartograf.guide import agent_guide, inject_block
from kartograf.messages import message

_WIDTH = 78
_LIST_FOOTER = message("cli.list_footer")


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
        lines.append(message("cli.group_products_header", lang=language()))
        for name, summary in products:
            lines += _wrap(f"{name} - {summary}", "      ", "    ")
    lines.append(message("cli.group_commands_header", lang=language()))
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
    lines += _wrap(localized(_LIST_FOOTER), "")
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
    header = (
        message("cli.param_header_flag", lang=language()),
        "ARGUMENT",
        message("cli.param_header_kind", lang=language()),
        message("cli.param_header_required", lang=language()),
    )
    rows = [
        (
            _flag(p),
            p.api_argument or "-",
            p.kind,
            yes_no(p.required),
        )
        for p in params
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    lines: list[str] = [
        message("cli.parameters_header", lang=language()),
        _row(header, widths, indent),
    ]
    for cells, param in zip(rows, params, strict=True):
        lines.append(_row(cells, widths, indent))
        allowed = resolve(param.allowed)
        if allowed:
            lines += _wrap(
                message(
                    "cli.allowed_values", lang=language(), allowed=", ".join(allowed)
                ),
                indent + "    ",
            )
        lines += _wrap(resolve(param.description_pl), indent + "    ")
    return lines


def _constraint_lines(command: Command) -> list[str]:
    if not command.constraints:
        return []
    return [
        message("cli.constraints_header", lang=language()),
        *(f"  - {c.message_pl}" for c in command.constraints),
    ]


def _rule_lines(command: Command) -> list[str]:
    if not command.rules_pl:
        return []
    return [
        message("cli.rules_header", lang=language()),
        *(f"  - {rule}" for rule in command.rules_pl),
    ]


def _example_lines(command: Command) -> list[str]:
    lines: list[str] = [message("cli.examples_header", lang=language())]
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
    facts: list[str] = [
        message("cli.fact_kind", lang=language(), kind=command.kind),
        message(
            "cli.fact_function",
            lang=language(),
            function=command.function,
            result_schema=command.result_schema,
        ),
    ]
    if command.check_function is not None:
        facts.append(
            message(
                "cli.fact_check",
                lang=language(),
                check_function=command.check_function,
                check_result_schema=command.check_result_schema,
            )
        )
    if command.effects:
        facts.append(
            message(
                "cli.fact_effects", lang=language(), effects=", ".join(command.effects)
            )
        )
    if command.project_task:
        facts.append(message("cli.fact_project_task", lang=language()))
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


def _write_replacing(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` in one step: a temporary file, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)
        raise


def cmd_commands_guide(args: argparse.Namespace) -> int:
    """Print the guide for agents, or inject its block into a file (``--inject``)."""
    document = agent_guide(format=args.format)
    if args.inject is not None:
        if document.format != "agents-md-block":
            raise ValidationError(
                "--inject puts the block into a file: it needs the format "
                "agents-md-block",
                option="inject",
                options=("format", "inject"),
                hint="Run: kartograf commands guide --format agents-md-block "
                "--inject AGENTS.md",
            )
        path = Path(args.inject)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        _write_replacing(path, inject_block(existing, document.text))
    if wants_json(args):
        return emit_result(command_id(args), document)
    if args.inject is None:
        sys.stdout.write(document.text)
    return 0
