"""
``<group> list-sources``: the registered sources of a group as a table.

The table is rendered from the library document ``list_sources`` (spec 5.4.6):
no network and no second catalogue; with ``--json`` the CLI prints that
document (``kartograf-sources/1``). CHOICE is the options that choose a source in
``<group> download`` written as flags (``--product nmt --country pl --resolution
1m --vertical-crs EVRF2007|KRON86``), DIRECTORY the segment of the files below
``--output``, KEY the ``dataset`` field of their sidecar.
"""

import argparse
import textwrap
from collections.abc import Sequence

from kartograf.catalog.commands import declared
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.messages import message
from kartograf.source_info import SelectValue, list_sources

_HEADER = (
    message("cli.header_choice"),
    message("cli.header_country"),
    message("cli.header_provider"),
    message("cli.header_directory"),
    message("cli.header_key"),
    message("cli.header_name"),
)
_NOTE = message("cli.list_sources_note")


def _collapse(values: Sequence[str | int]) -> list[str]:
    """Collapse consecutive ascending whole numbers into ``a-b``.

    ``2021, 2022, 2023`` becomes ``2021-2023``; other values stay as they are.
    """
    runs: list[list[str | int]] = []
    for value in values:
        last = runs[-1][-1] if runs else None
        if isinstance(value, int) and isinstance(last, int) and value == last + 1:
            runs[-1].append(value)
        else:
            runs.append([value])
    return [f"{r[0]}-{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs]


def _metavars(group: str) -> dict[str, str]:
    """Return the placeholders of the flags of ``<group> download``.

    A placeholder is like ``--property WLASCIWOSC``: what ``list-sources`` writes for a
    value the caller chooses.
    """
    for command in declared().commands:
        if command.id == f"{group} download":
            return {p.name: p.metavar for p in command.params if p.metavar}
    return {}


def _choice(select: dict[str, SelectValue], metavars: dict[str, str]) -> str:
    """Return the options of ``select`` as the flags that choose the source."""
    parts = []
    for option, value in select.items():
        if value is None:
            text = metavars.get(option, option.upper())
        elif isinstance(value, tuple):
            text = "|".join(_collapse(value))
        else:
            text = str(value)
        parts.append(f"--{option.replace('_', '-')} {text}")
    return " ".join(parts)


def cmd_list_sources(args: argparse.Namespace, group: str) -> int:
    """Print the sources of ``group`` (``--json``: the document of ``list_sources``)."""
    sources = list_sources(group=group, product=args.product)
    if wants_json(args):
        return emit_result(command_id(args), sources)
    metavars = _metavars(group)
    header = tuple(localized(cell) for cell in _HEADER)
    rows = [
        (
            _choice(source.select, metavars),
            source.country,
            source.provider,
            source.directory,
            source.key,
            localized(source.name),
        )
        for source in sources.sources
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    print(message("cli.sources_of_group", lang=language(), group=group))
    for row in (header, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        print("  " + "  ".join(cells).rstrip())
    print()
    print(textwrap.fill(localized(_NOTE), width=78))
    print(message("cli.download_options_hint", lang=language(), group=group))
    return 0
