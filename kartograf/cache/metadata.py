"""
Metadata cache using SQLite for Kartograf.

This module provides the MetadataCache class that caches:
- OpenData URL lookups (godlo -> URL) for NMT/NMPT/Ortofoto providers
- TERYT code lookups (point -> TERYT) for BDOT10k provider

The cache uses SQLite with WAL mode for concurrent access support
and supports time-based TTL for cache expiration.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Default TTL: 7 days in seconds
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

# Default database filename
DEFAULT_DB_NAME = ".kartograf_cache.db"


class MetadataCache:
    """
    SQLite-based metadata cache for Kartograf.

    Caches WMS lookup results (OpenData URLs and TERYT codes) to avoid
    repeated network requests for the same data.

    Parameters
    ----------
    db_path : str or Path, optional
        Path to the SQLite database file. Defaults to
        `.kartograf_cache.db` in the current working directory.
    ttl_seconds : int, optional
        Time-to-live for cache entries in seconds. Default is 7 days
        (604800 seconds). Entries older than TTL are considered stale.

    Examples
    --------
    >>> cache = MetadataCache()
    >>> cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
    ...              "https://opendata.../file.asc")
    >>> url = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
    >>> cache.close()
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS url_cache (
                    godlo TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    vertical_crs TEXT NOT NULL,
                    product TEXT NOT NULL,
                    url TEXT NOT NULL,
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
            self._conn.commit()

    # =========================================================================
    # URL cache (for GugikProvider, GugikNmptProvider, GugikOrtoProvider)
    # =========================================================================

    def get_url(
        self,
        godlo: str,
        resolution: str,
        vertical_crs: str,
        product: str,
    ) -> str | None:
        """
        Get cached OpenData URL for a map sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        resolution : str
            Grid resolution (e.g., "1m", "5m")
        vertical_crs : str
            Vertical CRS (e.g., "EVRF2007", "KRON86")
        product : str
            Product type (e.g., "nmt", "nmpt", "orto")

        Returns
        -------
        str or None
            Cached URL if found and not expired, None otherwise
        """
        cursor = self._conn.execute(
            """
            SELECT url, cached_at FROM url_cache
            WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
            """,
            (godlo, resolution, vertical_crs, product),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        url, cached_at = row
        if time.time() - cached_at >= self._ttl_seconds:
            logger.debug(f"URL cache expired for {godlo} ({product})")
            # Opportunistically delete the expired entry
            with self._write_lock:
                self._conn.execute(
                    """
                    DELETE FROM url_cache
                    WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?
                    """,
                    (godlo, resolution, vertical_crs, product),
                )
                self._conn.commit()
            return None

        logger.debug(f"URL cache hit for {godlo} ({product})")
        return url

    def set_url(
        self,
        godlo: str,
        resolution: str,
        vertical_crs: str,
        product: str,
        url: str,
    ) -> None:
        """
        Cache an OpenData URL for a map sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        resolution : str
            Grid resolution
        vertical_crs : str
            Vertical CRS
        product : str
            Product type
        url : str
            OpenData URL to cache
        """
        with self._write_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO url_cache
                (godlo, resolution, vertical_crs, product, url, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (godlo, resolution, vertical_crs, product, url, time.time()),
            )
            self._conn.commit()
        logger.debug(f"Cached URL for {godlo} ({product})")

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
        """
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
            # Opportunistically delete the expired entry
            with self._write_lock:
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
    # Management methods
    # =========================================================================

    def clear(self) -> None:
        """Delete all cached entries from both tables."""
        with self._write_lock:
            self._conn.execute("DELETE FROM url_cache")
            self._conn.execute("DELETE FROM teryt_cache")
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
            - url_count: number of cached URL entries
            - teryt_count: number of cached TERYT entries
            - db_size_bytes: size of the database file in bytes
            - db_path: path to the database file
        """
        url_count = self._conn.execute("SELECT COUNT(*) FROM url_cache").fetchone()[0]
        teryt_count = self._conn.execute("SELECT COUNT(*) FROM teryt_cache").fetchone()[
            0
        ]

        db_size = 0
        if self._db_path.exists():
            db_size = self._db_path.stat().st_size

        return {
            "url_count": url_count,
            "teryt_count": teryt_count,
            "db_size_bytes": db_size,
            "db_path": str(self._db_path),
        }

    def prune_expired(self) -> int:
        """
        Delete all expired cache entries from both tables.

        Returns
        -------
        int
            Total number of entries deleted.
        """
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._write_lock:
            self._conn.execute("DELETE FROM url_cache WHERE cached_at < ?", (cutoff,))
            url_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            self._conn.execute("DELETE FROM teryt_cache WHERE cached_at < ?", (cutoff,))
            teryt_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
            self._conn.commit()
        total = url_deleted + teryt_deleted
        if total > 0:
            logger.debug(
                f"Pruned {total} expired entries "
                f"({url_deleted} URL, {teryt_deleted} TERYT)"
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
