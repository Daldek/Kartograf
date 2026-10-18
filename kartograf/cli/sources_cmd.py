"""
``<group> list-sources``: the registered sources of a group as a table.

The table is rendered from the library document ``list_sources`` (spec 5.4.6):
no network and no second catalogue. WYBOR is the options that choose a source in
``<group> download`` written as flags (``--product nmt --country pl --resolution
1m --vertical-crs EVRF2007|KRON86``), KATALOG the segment of the files below
``--output``, KLUCZ the ``dataset`` field of their sidecar.
"""

import argparse
import textwrap
from collections.abc import Sequence

from kartograf.catalog.commands import declared
from kartograf.source_info import SelectValue, list_sources

_HEADER = ("WYBOR", "KRAJ", "DOSTAWCA", "KATALOG", "KLUCZ", "NAZWA")
_NOTE = (
    "WYBOR: a|b = jedna z wartosci. KATALOG: pod --output; <uklad> i <uklad-wys> "
    "wynikaja z wyboru, wybory wariantu (skala, format, rocznik) dopisuja "
    "czlony _<wartosc>."
)


def _collapse(values: Sequence[str | int]) -> list[str]:
    """Consecutive ascending whole numbers as ``a-b`` (``2021, 2022, 2023`` ->
    ``2021-2023``); other values as they are."""
    runs: list[list[str | int]] = []
    for value in values:
        last = runs[-1][-1] if runs else None
        if isinstance(value, int) and isinstance(last, int) and value == last + 1:
            runs[-1].append(value)
        else:
            runs.append([value])
    return [f"{r[0]}-{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs]


def _metavars(group: str) -> dict[str, str]:
    """The placeholders of the flags of ``<group> download`` (``--property
    WLASCIWOSC``): what ``list-sources`` writes for a value the caller chooses."""
    for command in declared().commands:
        if command.id == f"{group} download":
            return {p.name: p.metavar for p in command.params if p.metavar}
    return {}


def _choice(select: dict[str, SelectValue], metavars: dict[str, str]) -> str:
    """The options of ``select`` as the flags that choose the source."""
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
    """Print the sources of ``group`` (``--json`` is the document of
    ``list_sources``)."""
    metavars = _metavars(group)
    rows = [
        (
            _choice(source.select, metavars),
            source.country,
            source.provider,
            source.directory,
            source.key,
            source.name,
        )
        for source in list_sources(group=group).sources
    ]
    widths = [max(len(row[i]) for row in (_HEADER, *rows)) for i in range(len(_HEADER))]
    print(f"Zrodla grupy {group}:")
    for row in (_HEADER, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        print("  " + "  ".join(cells).rstrip())
    print()
    print(textwrap.fill(_NOTE, width=78))
    print(f"Opcje pobrania: kartograf {group} download --help")
    return 0
