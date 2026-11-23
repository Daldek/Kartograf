"""
The provider lines of the Nogat standard (DEV §20), kept in one place (DEV-20.4).

The table of provider lines and the terms lines are copied byte for byte from the
standard into ``_data/provider_lines.json`` (the lines are Polish with diacritics,
which the code of the package never holds as literals): every surface takes them
from here. ``provider_lines`` gives the lines of a product in the order of
DEV-20.4, each text before its processed text, the terms lines after them, each
line once; ``merge_lines`` merges the lines of two products in that order, for
``ATTRIBUTION.txt`` of a plain write (DEV-20.5), which ``plan_attribution`` and
``write_attribution`` keep: a later write into the same directory merges its lines
in, none is removed.

Kartograf carries the lines of CAMELS-PL (``L`` with ``S`` and ``P``, DEV-20.12) in
the sidecars of its files and in ``ATTRIBUTION.txt``; the products of GUGiK, ISRIC
and ČÚZK keep their own attribution text (``CLAUDE.md``, Deviations).
"""

import functools
import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Final

from kartograf.output import FileResult, PlanEntry, Staging, refuse

__all__ = [
    "ATTRIBUTION_FILE",
    "merge_lines",
    "plan_attribution",
    "provider_lines",
    "write_attribution",
]

ATTRIBUTION_FILE: Final = "ATTRIBUTION.txt"
"""The file of the lines in the root of a plain write (DEV-20.5)."""

_DATA = "provider_lines.json"
_PLACEHOLDER = re.compile(r"\{([a-z]+)\}")


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
        """The lines this one stands for, whatever fills its placeholders."""
        parts = _PLACEHOLDER.split(self.text)
        return re.compile(
            "".join(re.escape(p) if i % 2 == 0 else ".+?" for i, p in enumerate(parts))
        )

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
        lines[row["code"]] = _Line(row["code"], row["text"], (2, position, 0))
    return lines


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


def _rank(line: str, position: int) -> tuple[int, int, int]:
    """Place a line of a merged list: its line of the standard, else after them."""
    for known in _table().values():
        if known.pattern.fullmatch(line):
            return known.rank
    return (1, position, 0)


def merge_lines(*groups: Sequence[str]) -> tuple[str, ...]:
    """Merge lines, each once, in the order of the standard (DEV-20.4, DEV-20.5).

    The lines of the table come in its order, a line of a provider the table does
    not hold after them in the order it came, the terms lines last; two lines of one
    row (``L`` of two releases) keep the order they came in.
    """
    found = list(dict.fromkeys(line for group in groups for line in group))
    ranked = [(_rank(line, number), number, line) for number, line in enumerate(found)]
    return tuple(line for _, _, line in sorted(ranked))


def _content(path: Path, lines: Sequence[str]) -> bytes | None:
    """Return the file with ``lines`` merged in; ``None`` when it holds them all.

    Raises
    ------
    OSError, UnicodeDecodeError
        An existing path that is no readable UTF-8 file.
    """
    try:
        existing: bytes | None = path.read_bytes()
    except FileNotFoundError:
        existing = None
    old = existing.decode("utf-8").splitlines() if existing is not None else []
    content = "".join(f"{line}\n" for line in merge_lines(old, lines)).encode("utf-8")
    return None if content == existing else content


def plan_attribution(write: Staging, lines: Sequence[str]) -> PlanEntry | None:
    """Return the position of ``ATTRIBUTION.txt`` in a plain write (DEV-20.5).

    ``write`` for a missing file, ``replace`` for one without some of ``lines``
    (they are merged in and none is removed, so ``--force`` does not matter),
    ``conflict`` (``output_exists``) for a path that is no readable UTF-8 file -
    with ``force`` it is ``replace``: the lines alone replace it, as ``force``
    replaces any existing target; ``None`` without lines or when the file holds
    them all.
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
    if content is None:
        return None
    return PlanEntry(path, "replace" if path.exists() else "write")


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
