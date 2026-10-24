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
from kartograf.exceptions import ValidationError
from kartograf.store_documents import (
    StoreEntries,
    StoreOverview,
    StoreSidecar,
    describe_store,
    list_store_entries,
    read_store_sidecar,
)

_NONE = "-"
_OVERVIEW_HEADER = ("SEGMENT", "PRODUKT", "KRAJ", "KLUCZ", "NAZWA")


def _output(args: argparse.Namespace) -> str:
    """Return the store directory of ``--output``; the library has no default for it."""
    if not args.output:
        raise ValidationError(
            "-o/--output jest wymagane (katalog magazynu)", option="output_dir"
        )
    output: str = args.output
    return output


def format_overview(overview: StoreOverview) -> str:
    """Return the text of ``kartograf store overview`` from the document.

    A line per segment (the segment, its product, country, ``dataset`` key and name; a
    segment no source produces is marked), or the note that the store is empty.
    """
    if not overview.segments:
        return f"Magazyn {overview.output_dir} jest pusty (brak segmentow)"
    rows = [
        (
            info.segment,
            info.product or _NONE,
            info.country or _NONE,
            info.dataset_key or _NONE,
            info.name if info.known else f"{info.name} [nieznany w rejestrze]",
        )
        for info in overview.segments
    ]
    widths = [
        max(len(row[i]) for row in (_OVERVIEW_HEADER, *rows))
        for i in range(len(_OVERVIEW_HEADER))
    ]
    lines = [f"Magazyn {overview.output_dir} ({len(rows)} segmentow):", ""]
    for row in (_OVERVIEW_HEADER, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        lines.append("  " + "  ".join(cells).rstrip())
    return "\n".join(lines)


def format_entries(listed: StoreEntries) -> str:
    """Return the text of ``kartograf store entries`` from the document.

    A header (the segment, the number of entries and whether more followed) and a line
    per entry: its kind, label, the first digits of its SHA-256 and its path; a problem
    names what is wrong with the file.
    """
    more = ", sa dalsze" if listed.truncated else ""
    lines = [
        f"Segment {listed.segment}: {len(listed.entries)} wpisow "
        f"(limit {listed.limit}{more})",
        "",
    ]
    for entry in listed.entries:
        problem = f"  problem: {entry.problem}" if entry.problem else ""
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
    """Print the segments of the store of ``--output`` (``--json``: the document)."""
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
        raise ValidationError("--path jest wymagane (plik magazynu)", option="path")
    document = read_store_sidecar(args.path)
    if wants_json(args):
        return emit_result(command_id(args), document)
    print(format_sidecar(document))
    return 0
