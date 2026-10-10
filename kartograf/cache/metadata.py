"""
Metadata cache using SQLite for Kartograf.

This module provides the MetadataCache class that caches:
- Index (skorowidz) records (product/resolution/vertical CRS/sheet code -> metadata or
no coverage)
- TERYT code lookups (point -> TERYT, ``teryt_cache``) for BDOT10k provider
- Powiat TERYT codes of an EPSG:2180 area (``teryt_bbox_cache``, PRG WFS
  discovery; also an empty list = sea/abroad)
- Sheet index lookups (system + sheet code -> payload) for CUZK sheet providers
  (sheet_cache, fixed TTL of 30 days)

The cache uses SQLite with WAL mode for concurrent access support and
supports time-based TTL for cache expiration. All reads and writes on the
shared Connection are serialized through a single threading.Lock: WAL mode
buys concurrency across separate processes/connections, not across threads
sharing one Connection (CPython caches prepared statements per Connection,
so unlocked concurrent reads on the same SQL text can return another key's
row - see the comment in MetadataCache.get_record()).

The database is opened lazily: constructing a MetadataCache, reading from
or querying stats of a missing database, clear() and close() never create
the file - only the first write (``set_*``) does.

The cache is only an accelerator, so its failure never blocks a download:
any ``sqlite3.Error`` while opening, reading or writing (a corrupted or
truncated file, no read permission, a lock held too long by another
process) switches the instance into a disabled state for the rest of its
life - reads are misses, writes are no-ops - and reports it exactly once
(``logger.warning`` or the ``on_disabled`` callback). With
``MetadataCache(strict=True)`` the same state raises ``CacheError`` instead
(on the failing call and on every later one).
"""

import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from kartograf.exceptions import CacheError

if TYPE_CHECKING:
    from kartograf.core.bbox import BBox

logger = logging.getLogger(__name__)

# Default TTL: 7 days in seconds
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

# TTL for sheet_cache (the CZ sheet index is practically constant): 30 days.
SHEET_TTL_SECONDS = 30 * 24 * 3600

# Default database filename
DEFAULT_DB_NAME = ".kartograf_cache.db"


def is_lock_error(error: BaseException) -> bool:
    """True when ``error`` is SQLite's "database is locked" (busy) error.

    A lock is not damage: the file is fine, another process holds it longer
    than the connection timeout. The cache is disabled the same way, but the
    message does not suggest deleting the file.
    """
    return isinstance(error, sqlite3.OperationalError) and "locked" in str(error)


class MetadataCache:
    """
    SQLite-based metadata cache for Kartograf.

    Caches lookup results to avoid repeated network requests for the same
    data. Tables: ``record_cache`` (skorowidz records), ``campaigns_cache``
    (campaign lists), ``teryt_cache`` (point -> powiat TERYT),
    ``teryt_bbox_cache`` (EPSG:2180 area -> powiat TERYT codes, PRG WFS) -
    all with the TTL (default 7 days) - and ``sheet_cache`` (CZ sheet index,
    SM5, fixed TTL of 30 days). ``refresh=True`` turns
    every read into a miss while writes still happen (CLI ``--force``).

    Parameters
    ----------
    db_path : str or Path, optional
        Path to the SQLite database file. Defaults to
        `.kartograf_cache.db` in the current working directory. The file
        is created by the first write, not by the constructor.
    ttl_seconds : int, optional
        Time-to-live for cache entries in seconds. Default is 7 days
        (604800 seconds). Entries older than TTL are considered stale.
        Does not apply to sheet_cache, which uses a separate fixed TTL of
        30 days (SHEET_TTL_SECONDS).
    refresh : bool, optional
        Refresh mode (E14, CLI ``--force``): every read
        (``get_record``/``get_campaigns``/``get_teryt``/
        ``get_teryts_for_bbox``/``get_sheet``) is a miss, while writes
        work normally - a freshly fetched record (or a confirmed lack of
        coverage) replaces the old entry, so the next run WITHOUT ``--force``
        gets the new record. Default ``False``.
    on_disabled : callable, optional
        Called once with a user-facing message when the cache gets disabled
        by an SQLite error (see the module docstring). Default ``None`` =
        the message goes to ``logger.warning`` instead.
    strict : bool, optional
        Strict mode (A9): an SQLite error raises ``CacheError`` on the
        failing call and on every later call, instead of disabling the cache
        silently. ``on_disabled`` is still called once. Default ``False``.
        The management methods (``stats``, ``clear``, ``vacuum``,
        ``prune_expired``, ``close`` - it prunes first) raise too; the
        ``error`` property reports the state without raising.
        ``DownloadManager`` lets the ``CacheError`` through when downloading
        sequentially and records it as a failed sheet in the parallel pool.

    Examples
    --------
    >>> cache = MetadataCache()
    >>> cache.set_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4",
    ...                  {"no_coverage": True})
    >>> record = cache.get_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4")
    >>> cache.close()
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        refresh: bool = False,
        on_disabled: Callable[[str], None] | None = None,
        strict: bool = False,
    ):
        self._refresh = refresh
        self._on_disabled = on_disabled
        self._strict = strict
        # Message of the error that disabled the cache (for strict mode).
        self._error_message: str = ""
        # First SQLite error; once set, the cache is disabled (guarded by
        # _write_lock, so concurrent threads report it only once).
        self._error: sqlite3.Error | None = None
        if db_path is None:
            db_path = Path(os.getcwd()) / DEFAULT_DB_NAME
        self._db_path = Path(db_path)
        self._ttl_seconds = ttl_seconds
        self._write_lock = threading.Lock()
        # Opened lazily under _write_lock (see _connection()): constructing
        # the cache, reading a missing database, stats/clear/close never
        # create the file - only the first write does.
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file (it may not exist yet)."""
        return self._db_path

    @property
    def error(self) -> sqlite3.Error | None:
        """SQLite error that disabled the cache, or None while it works."""
        return self._error

    @contextmanager
    def _db_errors(self) -> Iterator[None]:
        """Turn an ``sqlite3.Error`` into the disabled state.

        Used inside ``_write_lock``; without ``strict`` the caller falls
        through to its "miss" return value after a suppressed error, in
        strict mode ``CacheError`` is raised.
        """
        try:
            yield
        except sqlite3.Error as e:
            message = self._disable(e)
            if self._strict:
                raise CacheError(message) from e

    def _disable(self, error: sqlite3.Error) -> str:
        """Disable the cache and report it once (caller holds ``_write_lock``).

        Returns the message describing why the cache is disabled.
        """
        if self._error is not None:
            return self._error_message
        self._error = error
        if self._conn is not None:
            with suppress(sqlite3.Error):
                self._conn.close()
            self._conn = None
        if is_lock_error(error):
            message = (
                f"cache metadanych zablokowany przez inny proces "
                f"({self._db_path}): {error} — praca bez cache do konca zadania"
            )
        else:
            message = (
                f"cache metadanych nieczytelny ({self._db_path}): {error} — "
                f"praca bez cache; uzyj `kartograf cache clear` albo usun plik"
            )
        self._error_message = message
        if self._on_disabled is not None:
            self._on_disabled(message)
        else:
            logger.warning(message)
        return message

    def _existing_connection(self) -> sqlite3.Connection | None:
        """Return the connection only if the database file already exists.

        Read and management paths (``get_*``, ``stats``, ``clear``,
        ``vacuum``, ``prune_expired``) use this: a missing file is not
        created and None is returned (a miss / an empty cache). The check is
        repeated on every call, so a file created later by another instance
        or process is picked up. Caller must hold ``_write_lock``.
        """
        if self._error is not None:
            if self._strict:
                raise CacheError(self._error_message)
            return None
        if self._conn is None and not self._db_path.exists():
            return None
        return self._connection()

    def _connection(self) -> sqlite3.Connection | None:
        """Return the shared connection, opening (and creating) it on first use.

        None when the cache is disabled; an open failure raises
        ``sqlite3.Error`` (turned into the disabled state by ``_db_errors``).

        Caller must hold ``_write_lock`` - this makes the check-and-open
        atomic, so two threads never open two connections. Opening sets WAL
        mode and creates missing tables (also migrating an older database).
        """
        if self._error is not None:
            if self._strict:
                raise CacheError(self._error_message)
            return None
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        try:
            # Enable WAL mode for better concurrent read/write performance
            result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            if result is None or result[0].lower() != "wal":
                actual = result[0] if result else "unknown"
                logger.warning(f"Failed to enable WAL journal mode, got: {actual}")
            self._create_tables(conn)
        except BaseException:
            conn.close()
            raise
        self._conn = conn
        logger.debug(f"MetadataCache opened at {self._db_path}")
        return conn

    @staticmethod
    def _create_tables(conn: sqlite3.Connection) -> None:
        """Create cache tables if they don't exist (caller holds the lock)."""
        conn.execute("DROP TABLE IF EXISTS url_cache")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS record_cache (
                godlo TEXT NOT NULL,
                resolution TEXT NOT NULL,
                vertical_crs TEXT NOT NULL,
                product TEXT NOT NULL,
                payload TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (godlo, resolution, vertical_crs, product)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campaigns_cache (
                godlo TEXT NOT NULL,
                resolution TEXT NOT NULL,
                vertical_crs TEXT NOT NULL,
                product TEXT NOT NULL,
                payload TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (godlo, resolution, vertical_crs, product)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teryt_cache (
                x REAL NOT NULL,
                y REAL NOT NULL,
                teryt TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (x, y)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teryt_bbox_cache (
                min_x REAL NOT NULL,
                min_y REAL NOT NULL,
                max_x REAL NOT NULL,
                max_y REAL NOT NULL,
                teryts TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (min_x, min_y, max_x, max_y)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sheet_cache (
                system    TEXT NOT NULL,
                godlo     TEXT NOT NULL,
                payload   TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (system, godlo)
            )
            """
        )
        conn.commit()

    # =========================================================================
    # Record cache (for GugikProvider, GugikNmptProvider, GugikOrtoProvider)
    # =========================================================================

    def get_record(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
    ) -> dict | None:
        """Return the index record or None (missing/expired/refresh mode), 7-day TTL."""
        if self._refresh:
            return None
        # The lock also guards this read (not just writes): CPython caches a
        # prepared statement per Connection, keyed by SQL text, and reuses it
        # across threads. Two threads executing the same SQL text on this
        # shared `check_same_thread=False` connection concurrently can step
        # the same `sqlite3_stmt` and overwrite each other's bindings, which
        # returns another key's row (or raises). WAL mode only buys
        # concurrency across separate connections/processes, not across
        # threads sharing one connection. So execute+fetchone (and the
        # opportunistic DELETE below) must happen as a single critical
        # section, not just the writes.
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                """
                SELECT payload, cached_at FROM record_cache
                WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                """,
                (godlo, resolution, vertical_crs, product),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            payload, cached_at = row
            if time.time() - cached_at >= self._ttl_seconds:
                logger.debug(f"Record cache expired for {godlo} ({product})")
                # Opportunistically delete the expired entry (same critical
                # section - threading.Lock is not reentrant).
                conn.execute(
                    """
                    DELETE FROM record_cache
                    WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                    """,
                    (godlo, resolution, vertical_crs, product),
                )
                conn.commit()
                return None

            logger.debug(f"Record cache hit for {godlo} ({product})")
            return json.loads(payload)
        return None  # disabled by an SQLite error (_db_errors)

    def set_record(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
        payload: dict,
    ) -> None:
        """Store the chosen record or confirmed no coverage after successful queries."""
        with self._write_lock, self._db_errors():
            conn = self._connection()
            if conn is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO record_cache
                (godlo, resolution, vertical_crs, product, payload, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    godlo,
                    resolution,
                    vertical_crs,
                    product,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )
            conn.commit()
        logger.debug(f"Cached record for {godlo} ({product})")

    # =========================================================================
    # Campaigns cache (--campaigns all, ADR-030 h)
    # =========================================================================

    def get_campaigns(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
    ) -> dict | None:
        """Return the sheet's campaigns or None (missing/expired/refresh mode), 7-day
        TTL.

        Key as in record_cache; `--min-year` is NOT part of the key.
        """
        if self._refresh:
            return None
        # The lock covers the read too - see the comment in get_record().
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return None
            row = conn.execute(
                """
                SELECT payload, cached_at FROM campaigns_cache
                WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                """,
                (godlo, resolution, vertical_crs, product),
            ).fetchone()
            if row is None:
                return None

            payload, cached_at = row
            if time.time() - cached_at >= self._ttl_seconds:
                logger.debug(f"Campaigns cache expired for {godlo} ({product})")
                conn.execute(
                    """
                    DELETE FROM campaigns_cache
                    WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                    """,
                    (godlo, resolution, vertical_crs, product),
                )
                conn.commit()
                return None

            logger.debug(f"Campaigns cache hit for {godlo} ({product})")
            return json.loads(payload)
        return None  # disabled by an SQLite error (_db_errors)

    def set_campaigns(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
        payload: dict,
    ) -> None:
        """Store the sheet's campaigns (newest first) or a confirmed no coverage."""
        with self._write_lock, self._db_errors():
            conn = self._connection()
            if conn is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO campaigns_cache
                (godlo, resolution, vertical_crs, product, payload, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    godlo,
                    resolution,
                    vertical_crs,
                    product,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )
            conn.commit()
        logger.debug(f"Cached campaigns for {godlo} ({product})")

    # =========================================================================
    # TERYT cache (for Bdot10kProvider)
    # =========================================================================

    def get_teryt(self, x: float, y: float) -> str | None:
        """
        Get cached TERYT code for a point.

        Parameters
        ----------
        x : float
            X coordinate in EPSG:2180
        y : float
            Y coordinate in EPSG:2180

        Returns
        -------
        str or None
            Cached TERYT code if found and not expired, None otherwise
            (always None in ``refresh`` mode)
        """
        if self._refresh:
            return None
        # Lock guards the read too - see comment in get_record().
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                "SELECT teryt, cached_at FROM teryt_cache WHERE x=? AND y=?",
                (x, y),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            teryt, cached_at = row
            if time.time() - cached_at >= self._ttl_seconds:
                logger.debug(f"TERYT cache expired for ({x}, {y})")
                # Opportunistically delete the expired entry (same critical
                # section - threading.Lock is not reentrant).
                conn.execute(
                    "DELETE FROM teryt_cache WHERE x=? AND y=?",
                    (x, y),
                )
                conn.commit()
                return None

            logger.debug(f"TERYT cache hit for ({x}, {y}): {teryt}")
            return teryt
        return None  # disabled by an SQLite error (_db_errors)

    def set_teryt(self, x: float, y: float, teryt: str) -> None:
        """
        Cache a TERYT code for a point.

        Parameters
        ----------
        x : float
            X coordinate in EPSG:2180
        y : float
            Y coordinate in EPSG:2180
        teryt : str
            TERYT code to cache
        """
        with self._write_lock, self._db_errors():
            conn = self._connection()
            if conn is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO teryt_cache (x, y, teryt, cached_at)
                VALUES (?, ?, ?, ?)
                """,
                (x, y, teryt, time.time()),
            )
            conn.commit()
        logger.debug(f"Cached TERYT {teryt} for ({x}, {y})")

    def get_teryts_for_bbox(self, bbox: "BBox") -> list[str] | None:
        """Cached powiat TERYT codes of an EPSG:2180 area (None = miss/expired).

        An empty list is a valid cached answer (no powiat: sea, abroad).
        Always None in ``refresh`` mode. Lock guards the read too - see the
        comment in get_record().
        """
        if self._refresh:
            return None
        key = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT teryts, cached_at FROM teryt_bbox_cache "
                "WHERE min_x=? AND min_y=? AND max_x=? AND max_y=?",
                key,
            ).fetchone()
            if row is None:
                return None
            teryts, cached_at = row
            if time.time() - cached_at >= self._ttl_seconds:
                logger.debug(f"TERYT area cache expired for {key}")
                # Same critical section - threading.Lock is not reentrant.
                conn.execute(
                    "DELETE FROM teryt_bbox_cache "
                    "WHERE min_x=? AND min_y=? AND max_x=? AND max_y=?",
                    key,
                )
                conn.commit()
                return None
            logger.debug(f"TERYT area cache hit for {key}: {teryts}")
            return list(json.loads(teryts))
        return None  # disabled by an SQLite error (_db_errors)

    def set_teryts_for_bbox(self, bbox: "BBox", teryts: list[str]) -> None:
        """Cache the powiat TERYT codes of an EPSG:2180 area (also an empty list)."""
        with self._write_lock, self._db_errors():
            conn = self._connection()
            if conn is None:
                return
            conn.execute(
                "INSERT OR REPLACE INTO teryt_bbox_cache "
                "(min_x, min_y, max_x, max_y, teryts, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    bbox.min_x,
                    bbox.min_y,
                    bbox.max_x,
                    bbox.max_y,
                    json.dumps(list(teryts)),
                    time.time(),
                ),
            )
            conn.commit()
        logger.debug(f"Cached TERYT codes {teryts} for area {bbox}")

    # =========================================================================
    # Sheet cache (CZ sheet index: KladyMapovychListu)
    # =========================================================================

    def get_sheet(self, system: str, godlo: str) -> dict | None:
        """Return the decoded sheet payload or None (missing/expired).

        Lock guards the read too - see comment in get_record(). In
        ``refresh`` mode: always None.
        """
        if self._refresh:
            return None
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                "SELECT payload, cached_at FROM sheet_cache WHERE system=? AND godlo=?",
                (system, godlo),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            payload, cached_at = row
            if time.time() - cached_at >= SHEET_TTL_SECONDS:
                logger.debug(f"Sheet cache expired for {system}/{godlo}")
                # Same critical section - threading.Lock is not reentrant.
                conn.execute(
                    "DELETE FROM sheet_cache WHERE system=? AND godlo=?",
                    (system, godlo),
                )
                conn.commit()
                return None
            logger.debug(f"Sheet cache hit for {system}/{godlo}")
            return json.loads(payload)
        return None  # disabled by an SQLite error (_db_errors)

    def set_sheet(self, system: str, godlo: str, payload: dict) -> None:
        """Store the sheet payload (JSON) under the key (system, godlo)."""
        with self._write_lock, self._db_errors():
            conn = self._connection()
            if conn is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO sheet_cache
                (system, godlo, payload, cached_at) VALUES (?, ?, ?, ?)
                """,
                (system, godlo, json.dumps(payload, ensure_ascii=False), time.time()),
            )
            conn.commit()
        logger.debug(f"Cached sheet {system}/{godlo}")

    # =========================================================================
    # Management methods
    # =========================================================================

    def clear(self) -> None:
        """Delete all cached entries from all tables."""
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM record_cache")
            conn.execute("DELETE FROM campaigns_cache")
            conn.execute("DELETE FROM teryt_cache")
            conn.execute("DELETE FROM teryt_bbox_cache")
            conn.execute("DELETE FROM sheet_cache")
            conn.commit()
            logger.info("Cache cleared")

    def vacuum(self) -> None:
        """Reclaim unused space in the database file."""
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return
            conn.execute("VACUUM")
            logger.debug("Cache vacuumed")

    def stats(self) -> dict:
        """
        Return cache statistics.

        Returns
        -------
        dict
            Dictionary with keys:
            - record_count: number of cached index entries
            - campaign_count: number of cached campaign lists
            - teryt_count: number of cached TERYT entries: points
              (``teryt_cache``) and areas (``teryt_bbox_cache``)
            - sheet_count: number of cached sheet entries
            - db_size_bytes: size of the database file in bytes
            - db_path: path to the database file
            - db_exists: whether the database file exists (it is created
              by the first write; until then all counts are 0)
            - error: ``str`` of the SQLite error that disabled the cache
              (counts are then 0), ``None`` while it works; without
              ``strict`` only - in strict mode the call raises
              ``CacheError`` instead
        """
        counts: tuple[int, ...] = (0, 0, 0, 0, 0)
        # Lock guards these reads too - see comment in get_record().
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                # Nothing cached yet - report zeros without creating the file.
                counts = (0, 0, 0, 0, 0)
            else:
                counts = tuple(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "record_cache",
                        "campaigns_cache",
                        "teryt_cache",
                        "teryt_bbox_cache",
                        "sheet_cache",
                    )
                )
        record_count, campaign_count, teryt_points, teryt_areas, sheet_count = counts
        teryt_count = teryt_points + teryt_areas

        db_exists = self._db_path.exists()
        db_size = self._db_path.stat().st_size if db_exists else 0

        return {
            "record_count": record_count,
            "campaign_count": campaign_count,
            "teryt_count": teryt_count,
            "sheet_count": sheet_count,
            "db_size_bytes": db_size,
            "db_path": str(self._db_path),
            "db_exists": db_exists,
            "error": None if self._error is None else str(self._error),
        }

    def prune_expired(self) -> int:
        """
        Delete all expired cache entries from all tables.

        Returns
        -------
        int
            Total number of entries deleted.
        """
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._write_lock, self._db_errors():
            conn = self._existing_connection()
            if conn is None:
                return 0
            conn.execute("DELETE FROM record_cache WHERE cached_at < ?", (cutoff,))
            record_deleted = conn.execute("SELECT changes()").fetchone()[0]
            conn.execute("DELETE FROM campaigns_cache WHERE cached_at < ?", (cutoff,))
            campaign_deleted = conn.execute("SELECT changes()").fetchone()[0]
            conn.execute("DELETE FROM teryt_cache WHERE cached_at < ?", (cutoff,))
            teryt_deleted = conn.execute("SELECT changes()").fetchone()[0]
            conn.execute("DELETE FROM teryt_bbox_cache WHERE cached_at < ?", (cutoff,))
            teryt_deleted += conn.execute("SELECT changes()").fetchone()[0]
            sheet_cutoff = now - SHEET_TTL_SECONDS
            conn.execute("DELETE FROM sheet_cache WHERE cached_at < ?", (sheet_cutoff,))
            sheet_deleted = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            total = record_deleted + campaign_deleted + teryt_deleted + sheet_deleted
            if total > 0:
                logger.debug(
                    f"Pruned {total} expired entries ({record_deleted} Record, "
                    f"{campaign_deleted} Campaigns, {teryt_deleted} TERYT, "
                    f"{sheet_deleted} Sheet)"
                )
            return total
        return 0  # disabled by an SQLite error (_db_errors)

    def close(self) -> None:
        """Close the database connection, pruning expired entries first."""
        if self._conn:
            self.prune_expired()
        # prune_expired() may have disabled the cache (connection closed).
        with self._write_lock:
            if self._conn is not None:
                with suppress(sqlite3.Error):
                    self._conn.close()
                self._conn = None
                logger.debug("MetadataCache closed")

    def __del__(self):
        """Ensure database connection is closed on garbage collection."""
        # No imports and no exceptions: at interpreter shutdown
        # sys.meta_path can be None (an import in __del__ raised ImportError).
        try:
            conn = getattr(self, "_conn", None)
            if conn is not None:
                conn.close()
        except Exception:  # noqa: BLE001, S110 - a finalizer must not raise
            pass

    def __repr__(self) -> str:
        return (
            f"MetadataCache(db_path={self._db_path!r}, ttl_seconds={self._ttl_seconds})"
        )
