"""
``kartograf store``: the read access to the store as text or documents.

The commands are the library functions ``describe_store``, ``list_store_entries`` and
``read_store_sidecar`` (ADR-045): nothing is written, no network is used and no data
file is opened. The text is rendered from their documents
(``kartograf-store-overview/1``, ``kartograf-store-entries/1``,
``kartograf-store-sidecar/1``); with ``--json`` the CLI prints the document. A store
directory that cannot be listed is the ``OSError`` of the library and a sidecar that
cannot be read its ``InvalidSidecarError``; ``main`` reports them.
"""

import argparse
import json

from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.exceptions import ValidationError
from kartograf.messages import message
from kartograf.store_documents import (
    StoreEntries,
    StoreOverview,
    StoreSidecar,
    describe_store,
    list_store_entries,
    read_store_sidecar,
)

_NONE = "-"
_OVERVIEW_HEADER = (
    "SEGMENT",
    message("cli.header_product"),
    message("cli.header_country"),
    message("cli.header_key"),
    message("cli.header_name"),
)


def _output(args: argparse.Namespace) -> str:
    """Return the store directory of ``--root``; the library has no default for it."""
    if not args.root:
        raise ValidationError(message("cli.root_required"), option="root")
    output: str = args.root
    return output


def format_overview(overview: StoreOverview) -> str:
    """Return the text of ``kartograf store overview`` from the document.

    A line per segment (the segment, its product, country, ``dataset`` key and name; a
    segment no source produces is marked), or the note that the store is empty.
    """
    if not overview.segments:
        return message("cli.store_empty", lang=language(), root=overview.root)
    header = tuple(localized(cell) for cell in _OVERVIEW_HEADER)
    rows = [
        (
            info.segment,
            info.product or _NONE,
            info.country or _NONE,
            info.dataset_key or _NONE,
            localized(info.name)
            if info.known
            else message(
                "cli.segment_unknown_registry",
                lang=language(),
                name=localized(info.name),
            ),
        )
        for info in overview.segments
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    lines = [
        message(
            "cli.store_segments_header",
            lang=language(),
            root=overview.root,
            rows_count=len(rows),
        ),
        "",
    ]
    for row in (header, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        lines.append("  " + "  ".join(cells).rstrip())
    return "\n".join(lines)


def format_entries(listed: StoreEntries) -> str:
    """Return the text of ``kartograf store entries`` from the document.

    A header (the segment, the number of entries and whether more followed) and a line
    per entry: its kind, label, the first digits of its SHA-256 and its path; a problem
    names what is wrong with the file.
    """
    more = (
        message("cli.more_entries_suffix", lang=language()) if listed.truncated else ""
    )
    lines = [
        message(
            "cli.segment_entries_header",
            lang=language(),
            segment=listed.segment,
            entries_count=len(listed.entries),
            limit=listed.limit,
            more=more,
        ),
        "",
    ]
    for entry in listed.entries:
        problem = f"  problem: {localized(entry.problem)}" if entry.problem else ""
        lines.append(
            f"  {entry.kind:<10} {entry.label or _NONE:<24} "
            f"{entry.sha8 or _NONE:<8}  {entry.path}{problem}"
        )
    return "\n".join(lines)


def format_sidecar(document: StoreSidecar) -> str:
    """Return the text of ``kartograf store sidecar`` from the document.

    The path that was read and the sidecar as it is stored (``raw``, indented).
    """
    raw = json.dumps(document.sidecar.raw, indent=2, ensure_ascii=False)
    return f"Sidecar: {document.path}\n{raw}"


def cmd_store_overview(args: argparse.Namespace) -> int:
    """Print the segments of the store of ``--root`` (``--json``: the document)."""
    overview = describe_store(_output(args))
    if wants_json(args):
        return emit_result(command_id(args), overview)
    print(format_overview(overview))
    return 0


def cmd_store_entries(args: argparse.Namespace) -> int:
    """Print the first ``--limit`` entries of a segment (``--json``: the document)."""
    listed = list_store_entries(
        _output(args), segment=args.segment, units=args.units, limit=args.limit
    )
    if wants_json(args):
        return emit_result(command_id(args), listed)
    print(format_entries(listed))
    return 0


def cmd_store_sidecar(args: argparse.Namespace) -> int:
    """Print the sidecar of ``--path`` (``--json``: the document)."""
    if not args.path:
        raise ValidationError(message("cli.path_required"), option="path")
    document = read_store_sidecar(args.path)
    if wants_json(args):
        return emit_result(command_id(args), document)
    print(format_sidecar(document))
    return 0
