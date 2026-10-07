"""
Metadata cache using SQLite for Kartograf.

This module provides the MetadataCache class that caches:
- Skorowidz records (product/resolution/vertical CRS/godlo -> metadata or no coverage)
- TERYT code lookups (point -> TERYT) for BDOT10k provider
- Sheet index lookups (system + godlo -> payload) for CUZK sheet providers
  (sheet_cache, fixed TTL of 30 days)

The cache uses SQLite with WAL mode for concurrent access support and
supports time-based TTL for cache expiration. All reads and writes on the
shared Connection are serialized through a single threading.Lock: WAL mode
buys concurrency across separate processes/connections, not across threads
sharing one Connection (CPython caches prepared statements per Connection,
so unlocked concurrent reads on the same SQL text can return another key's
row - see the comment in MetadataCache.get_record()).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Default TTL: 7 days in seconds
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

# TTL dla sheet_cache (indeks arkuszy CZ jest praktycznie staly): 30 dni.
SHEET_TTL_SECONDS = 30 * 24 * 3600

# Default database filename
DEFAULT_DB_NAME = ".kartograf_cache.db"


class MetadataCache:
    """
    SQLite-based metadata cache for Kartograf.

    Caches WMS lookup results (skorowidz records and TERYT codes, TTL 7 days)
    and CZ sheet index entries (``sheet_cache``, SM5, TTL 30 days) to avoid
    repeated network requests for the same data. ``refresh=True`` turns
    every read into a miss while writes still happen (CLI ``--force``).

    Parameters
    ----------
    db_path : str or Path, optional
        Path to the SQLite database file. Defaults to
        `.kartograf_cache.db` in the current working directory.
    ttl_seconds : int, optional
        Time-to-live for cache entries in seconds. Default is 7 days
        (604800 seconds). Entries older than TTL are considered stale.
        Does not apply to sheet_cache, which uses a separate fixed TTL of
        30 days (SHEET_TTL_SECONDS).
    refresh : bool, optional
        Tryb odswiezania (E14, CLI ``--force``): kazdy odczyt
        (``get_record``/``get_teryt``/``get_sheet``) jest chybieniem, a zapisy
        dzialaja normalnie — swiezo pobrany rekord (albo potwierdzony brak
        pokrycia) zastepuje stary wpis, wiec kolejny przebieg BEZ ``--force``
        dostaje nowy rekord. Default ``False``.

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
    ):
        self._refresh = refresh
        if db_path is None:
            db_path = Path(os.getcwd()) / DEFAULT_DB_NAME
        self._db_path = Path(db_path)
        self._ttl_seconds = ttl_seconds
        self._write_lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        # Enable WAL mode for better concurrent read/write performance
        result = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
        if result is None or result[0].lower() != "wal":
            actual = result[0] if result else "unknown"
            logger.warning(f"Failed to enable WAL journal mode, got: {actual}")
        self._create_tables()
        logger.debug(f"MetadataCache opened at {self._db_path}")

    def _create_tables(self) -> None:
        """Create cache tables if they don't exist."""
        with self._write_lock:
            self._conn.execute("DROP TABLE IF EXISTS url_cache")
            self._conn.execute(
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
            self._conn.execute(
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
            self._conn.execute(
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
            self._conn.execute(
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
            self._conn.commit()

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
        """Zwroc rekord skorowidza albo None (brak/wygasly/tryb refresh), TTL 7 dni."""
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
        with self._write_lock:
            cursor = self._conn.execute(
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
                self._conn.execute(
                    """
                    DELETE FROM record_cache
                    WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                    """,
                    (godlo, resolution, vertical_crs, product),
                )
                self._conn.commit()
                return None

            logger.debug(f"Record cache hit for {godlo} ({product})")
            return json.loads(payload)

    def set_record(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
        payload: dict,
    ) -> None:
        """Zapisz wybrany rekord lub pewny brak pokrycia po udanych zapytaniach."""
        with self._write_lock:
            self._conn.execute(
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
            self._conn.commit()
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
        """Zwroc kampanie arkusza albo None (brak/wygasla/tryb refresh), TTL 7 dni.

        Klucz jak w record_cache; `--min-year` NIE wchodzi do klucza.
        """
        if self._refresh:
            return None
        # Lock obejmuje tez odczyt - patrz komentarz w get_record().
        with self._write_lock:
            row = self._conn.execute(
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
                self._conn.execute(
                    """
                    DELETE FROM campaigns_cache
                    WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                    """,
                    (godlo, resolution, vertical_crs, product),
                )
                self._conn.commit()
                return None

            logger.debug(f"Campaigns cache hit for {godlo} ({product})")
            return json.loads(payload)

    def set_campaigns(
        self,
        product: str,
        resolution: str,
        vertical_crs: str,
        godlo: str,
        payload: dict,
    ) -> None:
        """Zapisz kampanie arkusza (od najnowszej) lub pewny brak pokrycia."""
        with self._write_lock:
            self._conn.execute(
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
            self._conn.commit()
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
        with self._write_lock:
            cursor = self._conn.execute(
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
                self._conn.execute(
                    "DELETE FROM teryt_cache WHERE x=? AND y=?",
                    (x, y),
                )
                self._conn.commit()
                return None

            logger.debug(f"TERYT cache hit for ({x}, {y}): {teryt}")
            return teryt

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
        with self._write_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO teryt_cache (x, y, teryt, cached_at)
                VALUES (?, ?, ?, ?)
                """,
                (x, y, teryt, time.time()),
            )
            self._conn.commit()
        logger.debug(f"Cached TERYT {teryt} for ({x}, {y})")

    # =========================================================================
    # Sheet cache (indeks arkuszy CZ: KladyMapovychListu)
    # =========================================================================

    def get_sheet(self, system: str, godlo: str) -> dict | None:
        """Zwroc zdekodowany payload arkusza albo None (brak/wygasly).

        Lock guards the read too - see comment in get_record(). Tryb
        ``refresh``: zawsze None.
        """
        if self._refresh:
            return None
        with self._write_lock:
            cursor = self._conn.execute(
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
                self._conn.execute(
                    "DELETE FROM sheet_cache WHERE system=? AND godlo=?",
                    (system, godlo),
                )
                self._conn.commit()
                return None
            logger.debug(f"Sheet cache hit for {system}/{godlo}")
            return json.loads(payload)

    def set_sheet(self, system: str, godlo: str, payload: dict) -> None:
        """Zapisz payload arkusza (JSON) pod kluczem (system, godlo)."""
        with self._write_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sheet_cache
                (system, godlo, payload, cached_at) VALUES (?, ?, ?, ?)
                """,
                (system, godlo, json.dumps(payload, ensure_ascii=False), time.time()),
            )
            self._conn.commit()
        logger.debug(f"Cached sheet {system}/{godlo}")

    # =========================================================================
    # Management methods
    # =========================================================================

    def clear(self) -> None:
        """Delete all cached entries from all tables."""
        with self._write_lock:
            self._conn.execute("DELETE FROM record_cache")
            self._conn.execute("DELETE FROM campaigns_cache")
            self._conn.execute("DELETE FROM teryt_cache")
            self._conn.execute("DELETE FROM sheet_cache")
            self._conn.commit()
        logger.info("Cache cleared")

    def vacuum(self) -> None:
        """Reclaim unused space in the database file."""
        with self._write_lock:
            self._conn.execute("VACUUM")
        logger.debug("Cache vacuumed")

    def stats(self) -> dict:
        """
        Return cache statistics.

        Returns
        -------
        dict
            Dictionary with keys:
            - record_count: number of cached skorowidz entries
            - campaign_count: number of cached campaign lists
            - teryt_count: number of cached TERYT entries
            - sheet_count: number of cached sheet entries
            - db_size_bytes: size of the database file in bytes
            - db_path: path to the database file
        """
        # Lock guards these reads too - see comment in get_record().
        with self._write_lock:
            record_count = self._conn.execute(
                "SELECT COUNT(*) FROM record_cache"
            ).fetchone()[0]
            campaign_count = self._conn.execute(
                "SELECT COUNT(*) FROM campaigns_cache"
            ).fetchone()[0]
            teryt_count = self._conn.execute(
                "SELECT COUNT(*) FROM teryt_cache"
            ).fetchone()[0]
            sheet_count = self._conn.execute(
                "SELECT COUNT(*) FROM sheet_cache"
            ).fetchone()[0]

        db_size = 0
        if self._db_path.exists():
            db_size = self._db_path.stat().st_size

        return {
            "record_count": record_count,
            "campaign_count": campaign_count,
            "teryt_count": teryt_count,
            "sheet_count": sheet_count,
            "db_size_bytes": db_size,
            "db_path": str(self._db_path),
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
        with self._write_lock:
            self._conn.execute(
                "DELETE FROM record_cache WHERE cached_at < ?", (cutoff,)
            )
            record_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            self._conn.execute(
                "DELETE FROM campaigns_cache WHERE cached_at < ?", (cutoff,)
            )
            campaign_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            self._conn.execute("DELETE FROM teryt_cache WHERE cached_at < ?", (cutoff,))
            teryt_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            sheet_cutoff = now - SHEET_TTL_SECONDS
            self._conn.execute(
                "DELETE FROM sheet_cache WHERE cached_at < ?", (sheet_cutoff,)
            )
            sheet_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            self._conn.commit()
        total = record_deleted + campaign_deleted + teryt_deleted + sheet_deleted
        if total > 0:
            logger.debug(
                f"Pruned {total} expired entries ({record_deleted} Record, "
                f"{campaign_deleted} Campaigns, {teryt_deleted} TERYT, "
                f"{sheet_deleted} Sheet)"
            )
        return total

    def close(self) -> None:
        """Close the database connection, pruning expired entries first."""
        if self._conn:
            self.prune_expired()
            self._conn.close()
            self._conn = None
            logger.debug("MetadataCache closed")

    def __del__(self):
        """Ensure database connection is closed on garbage collection."""
        import contextlib

        if hasattr(self, "_conn") and self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()

    def __repr__(self) -> str:
        return (
            f"MetadataCache(db_path={self._db_path!r}, ttl_seconds={self._ttl_seconds})"
        )
