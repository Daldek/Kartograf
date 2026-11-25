"""
The provider lines of the Nogat standard (DEV §20), kept in one place (DEV-20.4).

The table of provider lines and the terms lines are copied byte for byte from the
standard into ``_data/provider_lines.json``, and the products that G and Z name into
``_data/line_products.json`` (the lines and the names are Polish and Czech with their
diacritics, which the code of the package never holds as literals): every surface
takes them from here. ``provider_lines`` gives the lines of codes in the order of
DEV-20.4, each text before its processed text, the terms lines after them, each line
once; ``split_terms`` parts them into the attribution lines and the terms lines
(``attribution`` and ``terms_notice`` of a JSON document, DEV-20.6, DEV-20.7);
``merge_lines`` merges the lines of several products in that order, and the lines of
one row whose values are products, years and days (G, Z, W) into one line that names
them all: the products each once, the years and the days first to last.

``source_line`` gives the line of the data of a source (G of GUGiK, SG of ISRIC
SoilGrids, Z of ČÚZK; DEV-20.9 to DEV-20.11, ADR-064) with the years their data were
created and the days they were downloaded; ``file_lines`` the lines of a file from its
sidecar: the line of its source filled from its metadata, else the
``license.attribution`` it carries (the lines of a CAMELS-PL release, ADR-062; the
text of a source the table holds no row for). A plain write (DEV-20.5) merges the
lines of every file it places into ``ATTRIBUTION.txt`` of its directory at once
(``add_lines``), none removed; ``plan_attribution`` is its position in the plan of the
write and ``attribution_refusal`` the conflict of a path there that is no readable
UTF-8 file.
"""

import functools
import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC
from email.utils import parsedate_to_datetime
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from kartograf.output import FileResult, PlanEntry, Staging, refuse
from kartograf.sources.descriptor import SourceDescriptor

if TYPE_CHECKING:
    from kartograf.store import Sidecar

__all__ = [
    "ATTRIBUTION_FILE",
    "UNKNOWN",
    "add_lines",
    "attribution_refusal",
    "created_years",
    "date_parts",
    "date_text",
    "file_lines",
    "merge_lines",
    "period_text",
    "plan_attribution",
    "provider_lines",
    "source_line",
    "split_terms",
    "write_attribution",
]

ATTRIBUTION_FILE: Final = "ATTRIBUTION.txt"
"""The file of the lines in the root of a plain write (DEV-20.5)."""

# A value of G, Z or W that no metadata gives, the abbreviation of "no data" that
# Hydrograf writes in G (its ADR-085).
UNKNOWN: Final = "b.d."

_DATA = "provider_lines.json"
_PRODUCTS = "line_products.json"
_PLACEHOLDER = re.compile(r"\{([a-z]+)\}")
_TERMS = 2  # the first item of the rank of a terms line (``_Line``)
# The values a merge joins (G, Z, W): the products each once, the years and the days
# first to last; a row with any other value (L) keeps each of its lines.
_JOINED: Final = frozenset({"products", "period", "date"})
_PRODUCTS_JOIN = ", "
_YEARS_JOIN = "\u2013"  # an en dash: 2020-2025
_DAYS_JOIN = " \u2013 "  # a spaced en dash: 2026-03-24 - 2026-10-29
_YEAR = re.compile(r"\d{4}")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class _Line:
    """One line of the standard: its code, its text (a template) and its place.

    ``rank`` orders the lines: ``(0, order, 0)`` a text, ``(0, order, 1)`` its
    processed text, ``(2, position, 0)`` a terms line.
    """

    code: str
    text: str
    rank: tuple[int, int, int]

    @functools.cached_property
    def pattern(self) -> re.Pattern[str]:
        """The lines this one stands for, a group for each value of a placeholder."""
        parts = _PLACEHOLDER.split(self.text)
        return re.compile(
            "".join(
                re.escape(part) if i % 2 == 0 else f"(?P<{part}>.+?)"
                for i, part in enumerate(parts)
            )
        )

    @functools.cached_property
    def joined(self) -> bool:
        """Whether lines of this row merge into one: its values are those of G."""
        names = set(_PLACEHOLDER.findall(self.text))
        return bool(names) and names <= _JOINED

    def fill(self, params: Mapping[str, str]) -> str:
        """Return the line with its placeholders filled from ``params``.

        Raises
        ------
        KeyError
            A placeholder of the line without its value.
        """
        return _PLACEHOLDER.sub(lambda found: params[found[1]], self.text)


@functools.cache
def _table() -> Mapping[str, _Line]:
    """Return the lines of the standard by code, in their order."""
    data = json.loads(
        resources.files("kartograf")
        .joinpath("_data", _DATA)
        .read_text(encoding="utf-8")
    )
    lines: dict[str, _Line] = {}
    for row in data["lines"]:
        order = int(row["order"])
        lines[row["code"]] = _Line(row["code"], row["text"], (0, order, 0))
        if "processed_code" in row:
            code = row["processed_code"]
            lines[code] = _Line(code, row["processed"], (0, order, 1))
    for position, row in enumerate(data["terms"]):
        lines[row["code"]] = _Line(row["code"], row["text"], (_TERMS, position, 0))
    return lines


@functools.cache
def _products() -> Mapping[str, str]:
    """Return the ``<products>`` of G and Z by the registry key of the source."""
    data = json.loads(
        resources.files("kartograf")
        .joinpath("_data", _PRODUCTS)
        .read_text(encoding="utf-8")
    )
    return MappingProxyType(dict(data["products"]))


def provider_lines(codes: Iterable[str], **params: str) -> tuple[str, ...]:
    """Return the lines of ``codes`` in the order of the standard, each once.

    Parameters
    ----------
    codes : iterable of str
        Codes of the table of provider lines (``S``, ``P``, ``L``, ``LP``) or of the
        terms lines (``RD``, ``RE``), in any order.
    **params : str
        The values of the placeholders of a line: ``version``, ``year`` and ``doi``
        of ``L``; ``products``, ``period`` and ``date`` of ``G`` and ``Z``.

    Returns
    -------
    tuple of str
        The attribution lines in the order of DEV-20.4 (each text before its
        processed text), then the terms lines in the order of DEV-20.7.

    Raises
    ------
    KeyError
        A code the standard does not have, or a placeholder of a chosen line
        without its value.
    """
    table = _table()
    chosen = sorted({table[code] for code in codes}, key=lambda line: line.rank)
    return tuple(line.fill(params) for line in chosen)


def period_text(years: Iterable[int]) -> str:
    """Return ``<period>`` of G or W: a year, or the first and the last.

    ``"2021"``, ``"2020–2025"`` joined by an en dash, ``UNKNOWN`` without a year.
    """
    found = sorted(set(years))
    if not found:
        return UNKNOWN
    first, last = found[0], found[-1]
    return str(first) if first == last else f"{first}{_YEARS_JOIN}{last}"


def date_text(days: Iterable[str]) -> str:
    """Return ``<date>`` of G, Z or W: a day, or the first and the last.

    ``"2026-11-25"`` (``YYYY-MM-DD``), ``"2026-03-24 – 2026-10-29"`` joined by a
    spaced en dash, ``UNKNOWN`` without a day.
    """
    found = sorted(set(days))
    if not found:
        return UNKNOWN
    first, last = found[0], found[-1]
    return first if first == last else f"{first}{_DAYS_JOIN}{last}"


def _years(text: str) -> set[int]:
    """Return the years of ``<period>``: one, or the first and the last; none else."""
    parts = text.split(_YEARS_JOIN)
    if len(parts) > 2 or not all(_YEAR.fullmatch(part) for part in parts):
        return set()
    return {int(part) for part in parts}


def _days(text: str) -> set[str]:
    """Return the days of ``<date>``: one, or the first and the last; none else."""
    parts = text.split(_DAYS_JOIN)
    if len(parts) > 2 or not all(_DAY.fullmatch(part) for part in parts):
        return set()
    return set(parts)


def _known(line: str) -> _Line | None:
    """Return the line of the standard that ``line`` is, whatever its values."""
    for known in _table().values():
        if known.pattern.fullmatch(line):
            return known
    return None


def _rank(line: str, position: int) -> tuple[int, int, int]:
    """Place a line of a merged list: its line of the standard, else after them."""
    known = _known(line)
    return known.rank if known is not None else (1, position, 0)


def _joined(row: _Line, lines: Sequence[str]) -> str:
    """Return one line of ``row`` naming the products, years and days of ``lines``.

    A value that names no year or day (``UNKNOWN``) adds none; ``UNKNOWN`` stays
    when no line names one.
    """
    products: dict[str, None] = {}
    years: set[int] = set()
    days: set[str] = set()
    for line in lines:
        match = row.pattern.fullmatch(line)
        assert match is not None  # the lines of the row
        values = match.groupdict()
        products.update(dict.fromkeys(values.get("products", "").split(", ")))
        years |= _years(values.get("period", ""))
        days |= _days(values.get("date", ""))
    return row.fill(
        {
            "products": _PRODUCTS_JOIN.join(name for name in products if name),
            "period": period_text(years),
            "date": date_text(days),
        }
    )


def merge_lines(*groups: Sequence[str]) -> tuple[str, ...]:
    """Merge lines, each once, in the order of the standard (DEV-20.4, DEV-20.5).

    The lines of the table come in its order, a line of a provider the table does
    not hold after them in the order it came, the terms lines last. The lines of one
    row whose values are products, years and days (G, Z, W) become one line in the
    place of the first of them, which names the products of all of them each once
    in the order they came and their years and days first to last (DEV §20); two
    lines of another row (``L`` of two releases) keep the order they came in.
    """
    found = list(dict.fromkeys(line for group in groups for line in group))
    rows: dict[str, list[str]] = {}
    for line in found:
        known = _known(line)
        if known is not None and known.joined:
            rows.setdefault(known.code, []).append(line)
    table = _table()
    merged = {code: _joined(table[code], lines) for code, lines in rows.items()}
    kept: list[str] = []
    for line in found:
        known = _known(line)
        if known is not None and known.joined:
            if line != rows[known.code][0]:
                continue  # merged into the line of the first of its row
            line = merged[known.code]
        kept.append(line)
    ranked = [
        (_rank(line, number), number, line)
        for number, line in enumerate(dict.fromkeys(kept))
    ]
    return tuple(line for _, _, line in sorted(ranked))


def split_terms(lines: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Part ``lines`` into the attribution lines and the terms lines (DEV-20.7).

    A JSON document carries the first as ``attribution`` (DEV-20.6) and the
    second as ``terms_notice``; each part keeps the order ``lines`` came in.
    """
    ranks = [_rank(line, number)[0] for number, line in enumerate(lines)]
    return (
        tuple(line for line, rank in zip(lines, ranks, strict=True) if rank != _TERMS),
        tuple(line for line, rank in zip(lines, ranks, strict=True) if rank == _TERMS),
    )


def date_parts(line: str) -> tuple[str, str] | None:
    """Return the text of ``line`` before and after its ``<date>``, or ``None``.

    A line of a row that names the day of the download (G, Z, W) is split around
    that value, so a writer that knows the day only when it runs (the direct script
    of ``kartograf script generate``) puts it between the two parts; ``None`` for a
    line of another row or of a provider the table does not hold.
    """
    known = _known(line)
    if known is None or "date" not in known.pattern.groupindex:
        return None
    match = known.pattern.fullmatch(line)
    assert match is not None  # `_known` matched it
    start, end = match.span("date")
    return line[:start], line[end:]


# --- the lines of a source and of a file ----------------------------------------------


def source_line(
    source: SourceDescriptor,
    *,
    years: Iterable[int] = (),
    days: Iterable[str] = (),
) -> str | None:
    """Return the line of DEV §20 that the data of ``source`` carry, filled.

    G of GUGiK and Z of ČÚZK name the product of the source (``<products>``, the
    names of ``_data/line_products.json``), G the years the data were created
    (``<period>``, `period_text`) and both the days they were downloaded
    (``<date>``, `date_text`); SG of ISRIC SoilGrids has no value (ADR-064).

    Returns
    -------
    str or None
        The line; ``None`` for a source whose licence names no line
        (``LicenseInfo.line``).

    Raises
    ------
    KeyError
        A source of G or Z whose product ``_data/line_products.json`` does not name.
    """
    code = source.license.line
    if code is None:
        return None
    row = _table()[code]
    params = {"period": period_text(years), "date": date_text(days)}
    if "{products}" in row.text:
        params["products"] = _products()[source.key]
    return row.fill(params)


def created_years(sidecar: "Sidecar") -> frozenset[int]:
    """Return the years the data of a file were created, from its metadata (DEV §20).

    The year of its data that ``kartograf.store`` reads (``Sidecar.data_year``: the
    flight or the date of its index record, the edition, the year of the request),
    else the year of the ``Last-Modified`` of the file served (``extra.http``), the
    day its provider published it; none when the metadata gives neither (an answer a
    service builds at the request: a WCS, WFS or OGC API area, an ImageServer
    cutout).
    """
    if sidecar.data_year is not None:
        return frozenset({sidecar.data_year})
    http = (sidecar.extra or {}).get("http")
    modified = http.get("last_modified") if isinstance(http, dict) else None
    if not isinstance(modified, str):
        return frozenset()
    try:
        moment = parsedate_to_datetime(modified)
    except (TypeError, ValueError, IndexError):
        return frozenset()
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    return frozenset({moment.year})


def file_lines(meta: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the lines of a file from its sidecar (``kartograf-meta/1``).

    The line of its source (`source_line`) with the years its data were created
    (`created_years`) and the UTC day of ``downloaded_at``, so a version written before
    the sources had their lines gets them too; for a source without one, the lines of
    its ``license.attribution`` as written (the lines of a CAMELS-PL release, the text
    of a source the table holds no row for); none without either.

    Parameters
    ----------
    meta : mapping
        The sidecar as JSON (``ResultMetadata`` as a dict, ``LocalVersion.meta``).
    """
    from kartograf.sources.registry import get_source
    from kartograf.store import _typed  # the store imports the download layer

    sidecar = _typed(dict(meta), None)
    if sidecar.dataset_key is not None:
        day = (sidecar.downloaded_at or "")[:10]
        line = source_line(
            get_source(sidecar.dataset_key),
            years=created_years(sidecar),
            days=(day,) if _DAY.fullmatch(day) else (),
        )
        if line is not None:
            return (line,)
    text = (sidecar.license or {}).get("attribution")
    if not isinstance(text, str):
        return ()
    return tuple(row for row in text.splitlines() if row.strip())


# --- ATTRIBUTION.txt of a plain write -------------------------------------------------


def _content(path: Path, lines: Sequence[str]) -> bytes | None:
    """Return the file with ``lines`` merged in; ``None`` when it holds them all.

    The file is compared line by line, so its line endings (``CRLF`` of a file
    written on Windows, a missing final newline) do not make it differ; a file
    it returns is UTF-8 with ``LF`` (DEV-14.1).

    Raises
    ------
    OSError, UnicodeDecodeError
        An existing path that is no readable UTF-8 file.
    """
    try:
        existing: bytes | None = path.read_bytes()
    except FileNotFoundError:
        existing = None
    old = tuple(existing.decode("utf-8").splitlines()) if existing is not None else ()
    merged = merge_lines(old, lines)
    if existing is not None and merged == old:
        return None
    return "".join(f"{line}\n" for line in merged).encode("utf-8")


def plan_attribution(write: Staging, lines: Sequence[str]) -> PlanEntry | None:
    """Return the position of ``ATTRIBUTION.txt`` in a plain write (DEV-20.5).

    ``write`` for a missing file, ``replace`` for one without some of ``lines``
    (they are merged in and none is removed, so ``--force`` does not matter) and for
    any existing one when a line names years or days (G, Z: the values of the files
    are known after their download, `merge_lines`), ``conflict`` (``output_exists``)
    for a path that is no readable UTF-8 file - with ``force`` it is ``replace``: the
    lines alone replace it, as ``force`` replaces any existing target; ``None``
    without lines or when the file holds them all.
    """
    if not lines:
        return None
    path = write.target(ATTRIBUTION_FILE)
    try:
        content = _content(path, lines)
    except (OSError, UnicodeDecodeError):
        if write.force:
            return PlanEntry(path, "replace")
        return PlanEntry(path, "conflict", "output_exists")
    if content is None and not any(
        known is not None and known.joined for known in map(_known, lines)
    ):
        return None
    return PlanEntry(path, "replace" if path.exists() else "write")


def attribution_refusal(write: Staging) -> PlanEntry | None:
    """Return the conflict of ``ATTRIBUTION.txt`` of a plain write, or ``None``.

    A path there that is no readable UTF-8 file is ``conflict`` (``output_exists``)
    without ``force``: the preflight of the write lists it before the first byte
    (`kartograf.output.preflight`), as the lines of its files would be merged into it.
    """
    if write.force:
        return None
    path = write.target(ATTRIBUTION_FILE)
    try:
        _content(path, ())
    except (OSError, UnicodeDecodeError):
        return PlanEntry(path, "conflict", "output_exists")
    return None


def write_attribution(write: Staging, lines: Sequence[str]) -> FileResult | None:
    """Merge ``lines`` into the ``ATTRIBUTION.txt`` of a plain write (DEV-20.5).

    The file is staged and moved into place with ``os.replace`` like every plain
    file.

    Returns
    -------
    FileResult or None
        The file (``written`` or ``replaced``), or ``None`` when it held every line.

    Raises
    ------
    ConflictError
        ``output_exists``: the path is no readable UTF-8 file and the write is not
        forced; nothing is written.
    """
    entry = plan_attribution(write, lines)
    if entry is None:
        return None
    refuse([entry])
    try:
        content = _content(entry.path, lines)
    except (OSError, UnicodeDecodeError):  # forced (plan_attribution): lines alone
        content = "".join(f"{line}\n" for line in merge_lines(lines)).encode("utf-8")
    if content is None:
        return None
    staged = write.stage_path(ATTRIBUTION_FILE)
    try:
        staged.write_bytes(content)
        replaced = entry.path.exists()
        os.replace(staged, entry.path)
    finally:
        write.discard(staged)
    return FileResult(
        entry.path,
        len(content),
        hashlib.sha256(content).hexdigest(),
        "replaced" if replaced else "written",
    )


def add_lines(write: Staging, lines: Sequence[str]) -> None:
    """Merge the lines of a file a plain write placed into its ``ATTRIBUTION.txt``.

    Called for each file once it is in place (``kartograf.download.fetch``), so the
    directory never holds a file without its lines; threads of one write merge one
    after another. ``write.attribution`` is then the file as it stands: ``written``
    when this write made it, else ``replaced``; ``None`` while the write changed
    nothing of it (the five download reports list it in ``files[]``). A write whose
    files are not kept (``Staging.attributed`` false) gets none.

    Raises
    ------
    ConflictError
        ``output_exists``: a path that is no readable UTF-8 file appeared after the
        preflight and the write is not forced.
    """
    if not lines or not write.attributed:
        return
    with write.attribution_lock:
        written = write_attribution(write, lines)
        if written is None:
            return
        first = write.attribution
        write.attribution = (
            written if first is None else replace(written, status=first.status)
        )
