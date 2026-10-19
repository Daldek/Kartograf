"""
The store readers as JSON documents (ADR-045, spec 5.4.10).

``describe_store`` (``kartograf-store-overview/1``), ``list_store_entries``
(``kartograf-store-entries/1``) and ``read_store_sidecar``
(``kartograf-store-sidecar/1``) wrap the streaming readers of
``kartograf.store`` (``list_segments``, ``iter_store``, ``read_sidecar``,
unchanged) in documents for callers that need one JSON answer, e.g. an agent
over MCP. Nothing is written and no data file is opened.

The listing of entries is bounded: ``segment`` and ``limit`` are required, and
the document says whether more entries followed (``truncated``). A full scan of
a store with tens of thousands of versions is an answer for a program (use
``iter_store``), not for a model.

Raises
------
ValidationError
    A wrong argument (``option``: ``segment``, ``units``, ``limit``).
OSError
    ``output_dir`` is missing or cannot be listed (a missing store is not an
    empty one).
InvalidSidecarError
    ``read_store_sidecar``: the sidecar is missing, unreadable or of another
    schema (``path`` attribute).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from kartograf.download.arguments import require_int
from kartograf.exceptions import ValidationError
from kartograf.serialization import Document, EncodeContext
from kartograf.store import (
    SegmentInfo,
    Sidecar,
    StoreEntry,
    describe_segment,
    iter_store,
    list_segments,
    read_sidecar,
)


@dataclass(frozen=True)
class StoreOverview(Document):
    """The segments of a store (``kartograf-store-overview/1``).

    Attributes
    ----------
    output_dir : Path
        The ``data/`` directory that was listed (absolute in JSON).
    segments : tuple of SegmentInfo
        Every ``<product>/<variant>`` directory, sorted, with the registered
        source and a human name (``known=False`` for a directory no
        descriptor produces).
    """

    SCHEMA = "kartograf-store-overview/1"

    output_dir: Path
    segments: tuple[SegmentInfo, ...]


@dataclass(frozen=True)
class StoreEntries(Document):
    """The first ``limit`` entries of one segment (``kartograf-store-entries/1``).

    Attributes
    ----------
    output_dir : Path
        The ``data/`` directory that was read (absolute in JSON).
    segment : str
        The ``<product>/<variant>`` segment.
    units : tuple of str, optional
        The units asked for (``iter_store(units=...)``); ``None`` = the whole
        segment.
    limit : int
        The most entries returned.
    truncated : bool
        ``True`` when the segment (or the units) had entries beyond ``limit``.
    entries : tuple of StoreEntry
        Files and problems in the order of ``iter_store``; their ``sidecar``
        has no ``raw`` in JSON (``read_store_sidecar`` returns the whole
        sidecar of one file).
    """

    SCHEMA = "kartograf-store-entries/1"

    output_dir: Path
    segment: str
    units: tuple[str, ...] | None
    limit: int
    truncated: bool
    entries: tuple[StoreEntry, ...]

    def prepare_context(self, ctx: EncodeContext) -> None:
        ctx.omit = ctx.omit | {("Sidecar", "raw")}


@dataclass(frozen=True)
class StoreSidecar(Document):
    """The metadata of one store file (``kartograf-store-sidecar/1``).

    Attributes
    ----------
    path : Path
        The path that was read, as given (absolute in JSON).
    sidecar : Sidecar
        All fields, with ``raw``; ``sidecar.schema`` is always
        ``kartograf-meta/1``.
    """

    SCHEMA = "kartograf-store-sidecar/1"

    path: Path
    sidecar: Sidecar


def describe_store(output_dir: str | Path) -> StoreOverview:
    """List the segments of the store with their registered sources.

    Parameters
    ----------
    output_dir : str or Path
        The ``data/`` directory (not its parent).

    Returns
    -------
    StoreOverview
        One ``SegmentInfo`` per segment; an empty store has no segments.

    Raises
    ------
    OSError
        ``output_dir`` cannot be listed.
    """
    segments = tuple(describe_segment(name) for name in list_segments(output_dir))
    return StoreOverview(Path(output_dir), segments)


def list_store_entries(
    output_dir: str | Path,
    *,
    segment: str,
    units: Iterable[str] | None = None,
    limit: int,
) -> StoreEntries:
    """Read the first ``limit`` entries of one segment of the store.

    Parameters
    ----------
    output_dir : str or Path
        The ``data/`` directory (not its parent).
    segment : str
        ``<product>/<variant>`` (``describe_store`` lists them); required.
    units : iterable of str, optional
        Only these units of ``segment``: exact names as in
        ``iter_store(units=...)`` (a sheet code, ``teryt/<code>``,
        ``country/<code>``, the ``sidecar.unit`` of an entry...), not prefixes.
    limit : int
        The most entries to return, at least 1; required.

    Returns
    -------
    StoreEntries
        At most ``limit`` entries; ``truncated`` tells whether more followed
        (one more entry is read to know, nothing beyond it).

    Raises
    ------
    ValidationError
        ``segment`` not a ``<product>/<variant>`` string, ``units`` a string, a
        malformed or reserved unit, ``limit`` not an integer >= 1.
    OSError
        ``output_dir`` cannot be listed.
    """
    require_int(limit, "limit")
    if limit < 1:
        raise ValidationError(f"limit musi byc >= 1, podano {limit}", option="limit")
    if not isinstance(segment, str):
        raise ValidationError(
            f"segment jest wymagany: <produkt>/<wariant> (otrzymano {segment!r}); "
            "segmenty magazynu: describe_store",
            option="segment",
        )
    # A string is passed through unchanged: iter_store rejects it by name.
    scoped = units if units is None or isinstance(units, str) else tuple(units)
    found = tuple(
        islice(iter_store(output_dir, segment=segment, units=scoped), limit + 1)
    )
    return StoreEntries(
        Path(output_dir),
        segment,
        None if scoped is None else tuple(scoped),
        limit,
        len(found) > limit,
        found[:limit],
    )


def read_store_sidecar(path: str | Path) -> StoreSidecar:
    """Read the sidecar of one store file (all fields, with the raw JSON).

    Parameters
    ----------
    path : str or Path
        A data file (its ``<name>.meta.json`` is read) or the sidecar itself.

    Returns
    -------
    StoreSidecar
        The typed ``Sidecar`` as ``kartograf.read_sidecar`` returns it.

    Raises
    ------
    InvalidSidecarError
        The sidecar is missing, unreadable or of another schema (``path``).
    """
    return StoreSidecar(Path(path), read_sidecar(path))
