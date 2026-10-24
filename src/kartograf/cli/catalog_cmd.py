"""
``kartograf commands list [GRUPA [KOMENDA]] [--params] [--json]`` (spec 7.4).

The command is a query: it reads the catalog of the commands from the library
(``get_catalog``), needs no network and writes nothing. With ``--json`` it prints
the document ``kartograf-catalog/1`` of the library; without it, a text for a
person: the groups with their products and commands (one line per command), the
commands of one group, or the description of one command with its parameters,
constraints and examples.
"""

import argparse
import sys
import textwrap

from kartograf.catalog import get_catalog
from kartograf.catalog.model import Catalog, CommandInfo, GroupInfo, ParamInfo
from kartograf.cli._json import emit_document
from kartograf.exceptions import ValidationError

_WIDTH = 78
_FOOTER = (
    "Opis komendy z parametrami i przykladami: kartograf commands list <grupa> "
    "<komenda>. Przeglad jako dokument JSON: kartograf commands list --json. Caly "
    "katalog z parametrami, kodami wyjscia i bledow oraz schematami wyniku: "
    "kartograf commands list --params --json"
)


def _selection(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Return the ``(group, command)`` arguments of ``get_catalog`` for the line.

    ``GRUPA`` is a group; with ``KOMENDA`` (the name of a command inside the group,
    ``download``) the line names one command, whether the command has a CLI or only
    the API (``store overview``).
    """
    group, name = args.group, args.command
    if group is None:
        if name is not None:
            raise ValidationError("KOMENDA wymaga GRUPY", option="group")
        return None, None
    overview = get_catalog()
    groups = tuple(g.name for g in overview.groups)
    if name is not None:
        command = f"{group} {name}"
        if command in {c.id for c in overview.commands}:
            return None, command
        if group in groups:
            return group, command  # get_catalog names the commands of the group
    elif group in groups:
        return group, None
    raise ValidationError(
        f"Nieznana grupa {group!r} - grupy: {', '.join(groups)}",
        option="group",
        allowed=groups,
    )


def _wrap(text: str, indent: str, first: str | None = None) -> list[str]:
    return textwrap.wrap(
        text,
        width=_WIDTH,
        initial_indent=indent if first is None else first,
        subsequent_indent=indent,
    )


def _command_lines(commands: tuple[CommandInfo, ...], indent: str) -> list[str]:
    """One line per command: id, kind, summary."""
    id_width = max(len(c.id) for c in commands)
    kind_width = max(len(c.kind) for c in commands)
    return [
        f"{indent}{c.id.ljust(id_width)}  {c.kind.ljust(kind_width)}  {c.summary}"
        + ("" if c.cli is not None else " [tylko API]")
        for c in commands
    ]


def _flag(param: ParamInfo) -> str:
    if param.positional:
        return f"<{param.name}>"
    if param.flag is None:
        return "-"
    return param.flag if param.short is None else f"{param.flag}, {param.short}"


def _row(cells: tuple[str, ...], widths: list[int], indent: str) -> str:
    line = "  ".join(
        cell.ljust(width) for cell, width in zip(cells, widths, strict=True)
    )
    return f"{indent}{line}".rstrip()


def _param_lines(command: CommandInfo, indent: str) -> list[str]:
    """Return the parameters of a command.

    A table of flag, API argument, kind and whether it is required, each row followed by
    its allowed values and description.
    """
    params = command.params or ()
    if not params:
        return []
    header = ("FLAGA", "ARGUMENT", "RODZAJ", "WYMAGANY")
    rows = [
        (_flag(p), p.argument or "-", p.kind, "tak" if p.required else "nie")
        for p in params
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    lines = ["Parametry:", _row(header, widths, indent)]
    for cells, param in zip(rows, params, strict=True):
        lines.append(_row(cells, widths, indent))
        if param.allowed:
            allowed = "Dozwolone wartosci: " + ", ".join(param.allowed)
            lines += _wrap(allowed, indent + "    ")
        lines += _wrap(param.description, indent + "    ")
    return lines


def _constraint_lines(command: CommandInfo) -> list[str]:
    if not command.constraints:
        return []
    return ["Ograniczenia:", *(f"  - {c.message}" for c in command.constraints)]


def _example_lines(command: CommandInfo) -> list[str]:
    if not command.examples:
        return []
    lines = ["Przyklady:"]
    for example in command.examples:
        if example.title:
            lines.append(f"  {example.title}:")
            lines.append(f"    {example.command_line}")
        else:
            lines.append(f"  {example.command_line}")
    return lines


def _command_view(command: CommandInfo) -> list[str]:
    """Return the description of one command."""
    lines = [f"{command.id}: {command.summary}", ""]
    lines += _wrap(command.description, "")
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
    if command.cli is None:
        facts.append("tylko API")
    if command.tool:
        facts.append(f"narzedzie MCP: {command.tool}")
    lines += ["", *_wrap("; ".join(facts), "")]
    for block in (_param_lines(command, "  "), _constraint_lines(command)):
        if block:
            lines += ["", *block]
    examples = _example_lines(command)
    if examples:
        lines += ["", *examples]
    return lines


def _group_view(group: GroupInfo, by_id: dict[str, CommandInfo]) -> list[str]:
    lines = [f"{group.name}: {group.summary}"]
    lines += _wrap(group.description, "  ")
    if group.products:
        lines.append("  Produkty:")
        for product in group.products:
            countries = ", ".join(product.countries)
            lines += _wrap(
                f"{product.name} - {product.summary} [{countries}]", "      ", "    "
            )
    lines.append("  Komendy:")
    lines += _command_lines(tuple(by_id[i] for i in group.commands), "    ")
    return lines


def format_catalog(catalog: Catalog, *, command: str | None = None) -> str:
    """Return the text of a catalog view.

    The description of ``command`` when one was asked for, else the groups (and the
    commands only the API has) with one line per command, followed by the description
    of every command when the view has parameters.
    """
    by_id = {c.id: c for c in catalog.commands}
    if command is not None:
        return "\n".join(_command_view(by_id[command])) + "\n"
    lines: list[str] = []
    for group in catalog.groups:
        lines += [*_group_view(group, by_id), ""]
    alone = tuple(c for c in catalog.commands if c.cli is None)
    if alone:
        lines += ["Komendy tylko API:", *_command_lines(alone, "  "), ""]
    for entry in catalog.commands:
        if entry.params is not None:
            lines += ["", *_command_view(entry), ""]
    lines += _wrap(_FOOTER, "")
    return "\n".join(lines) + "\n"


def cmd_catalog(args: argparse.Namespace) -> int:
    """Print the catalog (``--json``: the library document, byte for byte)."""
    group, command = _selection(args)
    catalog = get_catalog(
        group=group, command=command, params=True if args.params else None
    )
    if args.json:
        return emit_document(catalog)
    sys.stdout.write(format_catalog(catalog, command=command))
    return 0
