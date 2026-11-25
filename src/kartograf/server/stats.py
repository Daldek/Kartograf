"""
The daily totals of ``kartograf server`` and its GUI (DEV-15.11, ADR-063 decision 8).

Each UTC day is one JSON object per line of ``<data_dir>/kartograf/stats.jsonl``, in
date order, with the keys of DEV-15.11: ``date``; ``visitors``, the distinct visitors
of the day, a visitor being the HMAC-SHA-256 of the client address and the
``User-Agent`` under a 32-byte random salt drawn at start and at each 00:00 UTC (salt
and hashes stay in memory and are never written); ``page_views``, the HTML pages of
the GUI served; ``stations_opened``, always 0 (Kartograf has no stations);
``analyses_run``, the plans answered and the scripts generated; ``downloads``, always
0 (the server downloads nothing for anyone, the data go between the user and the
source). The server rewrites the day's line at most ``FLUSH_S`` after a change and at
shutdown, and after a restart adds to the day's line (with a new salt). The pattern
is Hydrolog's public GUI (``hydrolog.gui._public.DailyStats``).
"""

import contextlib
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from kartograf.messages import message

__all__ = ["FLUSH_S", "STATS_FILE", "STATS_KEYS", "DailyStats", "read_days"]

logger = logging.getLogger(__name__)

STATS_FILE: Final = "stats.jsonl"
STATS_KEYS: Final = (
    "visitors",
    "page_views",
    "stations_opened",
    "analyses_run",
    "downloads",
)
FLUSH_S: Final = 300.0
"""The day's line is rewritten at most this many seconds after a change (DEV-15.11)."""


def _today(now: datetime) -> str:
    return now.astimezone(UTC).date().isoformat()


def read_days(path: Path) -> list[dict[str, Any]]:
    """Return the lines of ``stats.jsonl`` as objects; unusable lines are skipped.

    A missing or unreadable file has no lines.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    entries = []
    for line in text.splitlines():
        with contextlib.suppress(ValueError):
            entry = json.loads(line)
            if isinstance(entry, dict) and isinstance(entry.get("date"), str):
                entries.append(entry)
    return entries


class DailyStats:
    """The day's totals and their file (DEV-15.11).

    Parameters
    ----------
    path : Path
        ``<data_dir>/kartograf/stats.jsonl``, created with its directory by the first
        write.
    clock : callable, optional
        The current time (aware); tests pass their own.
    """

    def __init__(
        self, path: Path, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.path = path
        self._clock = clock
        self._lock = threading.Lock()
        self._day = _today(clock())
        self._salt = secrets.token_bytes(32)
        self._seen: set[bytes] = set()
        self._stored = self._stored_totals(self._day)
        self._counts = dict.fromkeys(STATS_KEYS[1:], 0)
        self._pending: list[dict[str, Any]] = []
        self._dirty = False

    def _stored_totals(self, day: str) -> dict[str, int]:
        """Return the totals the file holds for ``day`` (a restart adds to them)."""
        for entry in read_days(self.path):
            if entry.get("date") == day:
                return {
                    key: value
                    for key in STATS_KEYS
                    if isinstance(value := entry.get(key), int)
                    and not isinstance(value, bool)
                }
        return {}

    def _roll(self) -> None:
        """Start a new day at 00:00 UTC: the old one's line is final, a new salt."""
        day = _today(self._clock())
        if day == self._day:
            return
        self._pending.append(self._line())
        self._day = day
        self._salt = secrets.token_bytes(32)
        self._seen = set()
        self._stored = {}
        self._counts = dict.fromkeys(STATS_KEYS[1:], 0)
        self._dirty = True

    def _line(self) -> dict[str, Any]:
        """Return the day's line: the stored totals plus this run's."""
        line: dict[str, Any] = {"date": self._day}
        line["visitors"] = self._stored.get("visitors", 0) + len(self._seen)
        for key in STATS_KEYS[1:]:
            line[key] = self._stored.get(key, 0) + self._counts[key]
        return line

    def visit(self, address: str, user_agent: str) -> None:
        """Count the visitor of a counted request, in memory only."""
        text = f"{address}\n{user_agent}".encode("utf-8", "replace")
        with self._lock:
            self._roll()
            digest = hmac.new(self._salt, text, hashlib.sha256).digest()
            if digest not in self._seen:
                self._seen.add(digest)
                self._dirty = True

    def count(self, key: str) -> None:
        """Add one to a total other than ``visitors``.

        Raises
        ------
        KeyError
            ``key`` is not such a total.
        """
        if key not in self._counts:
            raise KeyError(key)
        with self._lock:
            self._roll()
            self._counts[key] += 1
            self._dirty = True

    def snapshot(self) -> dict[str, Any]:
        """Return the day's line as it would be written now."""
        with self._lock:
            self._roll()
            return self._line()

    def flush(self) -> None:
        """Rewrite the lines of the days that changed (atomically), in date order.

        A failure is logged and the totals stay for the next try.
        """
        with self._lock:
            self._roll()
            if not self._dirty:
                return
            lines = [*self._pending, self._line()]
            try:
                self._write(lines)
            except OSError:
                logger.exception(message("server.stats_not_written"))
                return
            self._pending = []
            self._dirty = False

    def _write(self, lines: list[dict[str, Any]]) -> None:
        entries = {entry["date"]: entry for entry in read_days(self.path)}
        for line in lines:
            entries[line["date"]] = line
        text = "".join(
            json.dumps(entries[day], ensure_ascii=False) + "\n"
            for day in sorted(entries)
        )
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(4)}")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
