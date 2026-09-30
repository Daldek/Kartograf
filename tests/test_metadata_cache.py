"""
Tests for the MetadataCache module and its provider integrations.

Tests cover:
- MetadataCache record caching (set, get, TTL expiry, overwrite, key parts)
- MetadataCache TERYT caching (set, get, TTL expiry)
- MetadataCache management (clear, stats, vacuum, close)
- Migration of a legacy database (url_cache table dropped)
- GugikProvider cache integration (hit, no-coverage hit, miss, K3-safe failure)
- GugikNmptProvider cache integration (product key "nmpt")
- Bdot10kProvider TERYT cache integration (cache hit, miss)
- SoilGridsProvider cache parameter acceptance
- CLI cache commands (stats, clear, path)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.cli.commands import create_parser, main
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from tests.conftest import gfi_record, render_gfi_body

GODLO = "N-34-130-D-d-2-4"

# Payload `source` o kluczach z SkorowidzRecord.to_source (kontrakt cache).
SOURCE = {
    "url": (
        f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{GODLO}.asc"
    ),
    "skorowidz": (
        "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WMS/"
        "SkorowidzeUkladEVRF2007"
    ),
    "layer": "SkorowidzeNMT2024",
    "godlo": GODLO,
    "aktualnosc": "2024-09-03",
    "aktualnosc_rok": "2024",
    "dt_pzgik": "2024-09-03",
    "resolution_m": 1.0,
    "uklad": "PL-1992",
    "full_sheet": True,
    "numer_zgloszenia": None,
    "zrodlo_danych": None,
}


def _gfi_response(body: str) -> Mock:
    """Atrapa odpowiedzi GetFeatureInfo z szablonem skorowidza GUGiK."""
    resp = Mock(spec=requests.Response)
    resp.status_code = 200
    resp.text = body
    resp.raise_for_status = Mock()
    return resp


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def cache_path(tmp_path):
    """Return a temporary cache database path."""
    return tmp_path / "test_cache.db"


@pytest.fixture
def cache(cache_path):
    """Create and return a MetadataCache instance with a temp db."""
    c = MetadataCache(db_path=cache_path)
    yield c
    c.close()


@pytest.fixture
def short_ttl_cache(cache_path):
    """Create a MetadataCache with very short TTL (1 second)."""
    c = MetadataCache(db_path=cache_path, ttl_seconds=1)
    yield c
    c.close()


# =========================================================================
# TestMetadataCacheRecord
# =========================================================================


class TestMetadataCacheRecord:
    """Tabela record_cache: payload JSON pod kluczem (product, res, vcrs, godlo)."""

    def test_set_and_get_round_trip(self, cache):
        """Zagniezdzony payload wraca 1:1 (JSON round-trip, takze None/float)."""
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) == {"source": SOURCE}

    def test_no_coverage_payload_round_trip(self, cache):
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"no_coverage": True})
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) == {"no_coverage": True}

    def test_get_returns_none_when_missing(self, cache):
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) is None

    def test_ttl_expiry(self, short_ttl_cache):
        """Wpis wygasa po ttl_seconds i jest usuwany oportunistycznie."""
        short_ttl_cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})
        assert short_ttl_cache.get_record("nmt", "1m", "EVRF2007", GODLO) is not None

        time.sleep(1.1)

        assert short_ttl_cache.get_record("nmt", "1m", "EVRF2007", GODLO) is None
        count = short_ttl_cache._conn.execute(
            "SELECT COUNT(*) FROM record_cache"
        ).fetchone()[0]
        assert count == 0

    def test_overwrite_same_key(self, cache):
        """Ten sam klucz: nowy payload zastepuje stary (np. no_coverage -> source)."""
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"no_coverage": True})
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) == {"source": SOURCE}
        assert cache.stats()["record_count"] == 1

    @pytest.mark.parametrize(
        "other_key",
        [
            ("nmpt", "1m", "EVRF2007", GODLO),
            ("nmt", "5m", "EVRF2007", GODLO),
            ("nmt", "1m", "KRON86", GODLO),
            ("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-3"),
        ],
        ids=["product", "resolution", "vertical_crs", "godlo"],
    )
    def test_each_key_part_separates_entries(self, cache, other_key):
        """Kazde z 4 pol klucza rozdziela wpisy — brak przeciekow miedzy nimi."""
        other_payload = {"source": {**SOURCE, "url": "https://other/file.asc"}}
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})
        assert cache.get_record(*other_key) is None
        cache.set_record(*other_key, other_payload)
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) == {"source": SOURCE}
        assert cache.get_record(*other_key) == other_payload


# =========================================================================
# TestMetadataCacheTERYT
# =========================================================================


class TestMetadataCacheTERYT:
    """Tests for TERYT caching operations."""

    def test_set_and_get(self, cache):
        """Test that set_teryt followed by get_teryt returns the code."""
        cache.set_teryt(500000.0, 400000.0, "1465")
        result = cache.get_teryt(500000.0, 400000.0)
        assert result == "1465"

    def test_get_returns_none_when_missing(self, cache):
        """Test that get_teryt returns None for uncached entries."""
        result = cache.get_teryt(500000.0, 400000.0)
        assert result is None

    def test_ttl_expiry(self, short_ttl_cache):
        """Test that TERYT entries expire after TTL."""
        short_ttl_cache.set_teryt(500000.0, 400000.0, "1465")
        assert short_ttl_cache.get_teryt(500000.0, 400000.0) is not None

        time.sleep(1.1)

        assert short_ttl_cache.get_teryt(500000.0, 400000.0) is None

    def test_different_points_are_separate(self, cache):
        """Test that different coordinates have separate entries."""
        cache.set_teryt(500000.0, 400000.0, "1465")
        cache.set_teryt(600000.0, 500000.0, "2465")
        assert cache.get_teryt(500000.0, 400000.0) == "1465"
        assert cache.get_teryt(600000.0, 500000.0) == "2465"

    def test_overwrite(self, cache):
        """Test that setting the same point overwrites the TERYT."""
        cache.set_teryt(500000.0, 400000.0, "1465")
        cache.set_teryt(500000.0, 400000.0, "1466")
        assert cache.get_teryt(500000.0, 400000.0) == "1466"


# =========================================================================
# TestMetadataCacheSheet
# =========================================================================


class TestMetadataCacheSheet:
    """Tabela sheet_cache (indeks arkuszy CZ) — TTL wg SHEET_TTL_SECONDS."""

    _PAYLOAD = {
        "godlo": "CTES96",
        "name": "Cesky Tesin 8-6",
        "bbox": [-450000.0, -1105000.0, -447500.0, -1103000.0],
        "bbox_crs": "EPSG:5514",
        "podil": 0.507,
        "in_cz": None,
    }

    def test_set_and_get(self, cache):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        assert cache.get_sheet("cz_sm5", "CTES96") == self._PAYLOAD

    def test_get_returns_none_when_missing(self, cache):
        assert cache.get_sheet("cz_sm5", "XXXX99") is None

    def test_systems_are_separate(self, cache):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        assert cache.get_sheet("cz_tm33", "CTES96") is None

    def test_sheet_ttl_expiry(self, cache, monkeypatch):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        monkeypatch.setattr("kartograf.cache.metadata.SHEET_TTL_SECONDS", 0)
        assert cache.get_sheet("cz_sm5", "CTES96") is None
        # wpis usuniety oportunistycznie
        row = cache._conn.execute("SELECT COUNT(*) FROM sheet_cache").fetchone()
        assert row[0] == 0

    def test_sheet_ttl_independent_from_record_ttl(self, cache_path):
        """ttl_seconds=1 (record/teryt) nie dotyczy sheet_cache (TTL 30 dni)."""
        c = MetadataCache(db_path=cache_path, ttl_seconds=1)
        c.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        time.sleep(1.1)
        assert c.get_sheet("cz_sm5", "CTES96") == self._PAYLOAD
        c.close()

    def test_prune_expired_covers_sheet_cache(self, cache, monkeypatch):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        monkeypatch.setattr("kartograf.cache.metadata.SHEET_TTL_SECONDS", 0)
        assert cache.prune_expired() == 1

    def test_old_database_gains_sheet_table(self, cache_path):
        """Stara baza (bez sheet_cache) doposaza sie przy otwarciu."""
        c = MetadataCache(db_path=cache_path)
        c._conn.execute("DROP TABLE sheet_cache")
        c._conn.commit()
        c._conn.close()
        c._conn = None
        c2 = MetadataCache(db_path=cache_path)
        assert c2.stats()["sheet_count"] == 0
        c2.close()


# =========================================================================
# TestMetadataCacheMigration
# =========================================================================


class TestMetadataCacheMigration:
    """Stary plik cache (0.6.x, tabela url_cache) migruje przy otwarciu."""

    def test_legacy_url_cache_table_is_dropped(self, cache_path):
        conn = sqlite3.connect(str(cache_path))
        conn.execute(
            """
            CREATE TABLE url_cache (
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
        conn.execute(
            "INSERT INTO url_cache VALUES (?, ?, ?, ?, ?, ?)",
            (GODLO, "1m", "EVRF2007", "nmt", "https://old/file.asc", time.time()),
        )
        conn.commit()
        conn.close()

        c = MetadataCache(db_path=cache_path)
        try:
            tables = {
                row[0]
                for row in c._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "url_cache" not in tables
            assert "record_cache" in tables
            assert c.get_record("nmt", "1m", "EVRF2007", GODLO) is None
            assert c.stats()["record_count"] == 0
        finally:
            c.close()


# =========================================================================
# TestMetadataCacheManagement
# =========================================================================


class TestMetadataCacheManagement:
    """Tests for cache management operations."""

    def test_clear(self, cache):
        """Test that clear removes all entries."""
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"no_coverage": True})
        cache.set_teryt(1.0, 2.0, "1234")
        cache.set_sheet("cz_sm5", "CTES96", {"podil": 0.5})
        cache.clear()
        assert cache.get_record("nmt", "1m", "EVRF2007", "A") is None
        assert cache.get_teryt(1.0, 2.0) is None
        assert cache.get_sheet("cz_sm5", "CTES96") is None

    def test_stats(self, cache):
        """Test that stats returns correct counts."""
        st = cache.stats()
        assert st["record_count"] == 0
        assert st["teryt_count"] == 0
        assert st["sheet_count"] == 0

        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        cache.set_record("nmt", "1m", "EVRF2007", "B", {"no_coverage": True})
        cache.set_teryt(1.0, 2.0, "1234")
        cache.set_sheet("cz_sm5", "CTES96", {"podil": 0.5})

        st = cache.stats()
        assert st["record_count"] == 2
        assert st["teryt_count"] == 1
        assert st["sheet_count"] == 1
        assert st["db_size_bytes"] > 0
        assert "db_path" in st

    def test_vacuum(self, cache):
        """Test that vacuum runs without error."""
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        cache.clear()
        cache.vacuum()  # Should not raise

    def test_close(self, cache_path):
        """Test that close properly closes the connection."""
        c = MetadataCache(db_path=cache_path)
        c.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        c.close()
        # After close, the internal conn should be None
        assert c._conn is None

    def test_repr(self, cache):
        """Test repr output."""
        r = repr(cache)
        assert "MetadataCache" in r
        assert "ttl_seconds" in r

    def test_default_db_path(self, tmp_path, monkeypatch):
        """Test that default db path is in CWD."""
        monkeypatch.chdir(tmp_path)
        c = MetadataCache()
        try:
            assert str(tmp_path / ".kartograf_cache.db") == c.stats()["db_path"]
        finally:
            c.close()


# =========================================================================
# TestGugikProviderCacheIntegration
# =========================================================================


class TestGugikProviderCacheIntegration:
    """GugikProvider._resolve_sheet: cache -> warstwy skorowidza -> cache."""

    def test_cache_hit_source_skips_network(self, cache):
        """Trafienie `source` = zero sieci; URL i source_info z payloadu."""
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})

        mock_session = Mock(spec=requests.Session)
        provider = GugikProvider(session=mock_session, cache=cache)

        assert provider._get_opendata_url(GODLO) == SOURCE["url"]
        mock_session.get.assert_not_called()
        assert provider.source_info(GODLO) == SOURCE

    def test_cache_hit_no_coverage_raises_without_network(self, cache):
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"no_coverage": True})

        mock_session = Mock(spec=requests.Session)
        provider = GugikProvider(session=mock_session, cache=cache)

        with pytest.raises(NoCoverageError, match=GODLO):
            provider._get_opendata_url(GODLO)
        mock_session.get.assert_not_called()

    def test_cache_miss_queries_wms_and_stores_source(self, cache):
        """Miss: pierwsza warstwa z rekordem konczy petle, cache dostaje `source`."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = _gfi_response(
            render_gfi_body([gfi_record(GODLO)])
        )

        provider = GugikProvider(session=mock_session, cache=cache)
        result = provider._get_opendata_url(GODLO)

        expected_url = gfi_record(GODLO)["url"]
        assert result == expected_url
        assert mock_session.get.call_count == 1
        cached = cache.get_record("nmt", "1m", "EVRF2007", GODLO)
        assert cached["source"]["url"] == expected_url
        assert cached["source"]["layer"] == "SkorowidzeNMT2026"
        assert provider.source_info(GODLO) == cached["source"]

    def test_cache_miss_all_layers_empty_stores_no_coverage(self, cache):
        """Puste odpowiedzi WSZYSTKICH warstw = pewny brak pokrycia w cache."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = _gfi_response(render_gfi_body([]))

        provider = GugikProvider(session=mock_session, cache=cache)
        with pytest.raises(NoCoverageError, match=GODLO):
            provider._get_opendata_url(GODLO)

        assert mock_session.get.call_count == 4
        cached = cache.get_record("nmt", "1m", "EVRF2007", GODLO)
        assert cached is not None and cached["no_coverage"] is True
        assert "Brak danych" in cached["message"]

    def test_query_failure_is_not_cached_as_no_coverage(self, cache):
        """K3-safe: awaria sieci = DownloadError, cache zostaje pusty."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.side_effect = [requests.ConnectionError("boom")] * 3

        provider = GugikProvider(session=mock_session, cache=cache)
        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as excinfo:
            provider._get_opendata_url(GODLO)

        assert not isinstance(excinfo.value, NoCoverageError)
        assert "SkorowidzeNMT2026" in str(excinfo.value)
        assert mock_session.get.call_count == 3
        assert sleep.call_count == 2
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) is None

    def test_no_cache_backward_compat(self):
        """cache=None: to samo rozstrzygniecie, bez zapisu."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = _gfi_response(
            render_gfi_body([gfi_record(GODLO)])
        )

        provider = GugikProvider(session=mock_session)
        assert provider._get_opendata_url(GODLO) == gfi_record(GODLO)["url"]

    def test_5m_resolution_with_cache(self, cache):
        """Klucz 5m: trafienie bez sieci, miss zapisuje pod ("nmt","5m",...)."""
        cache.set_record(
            "nmt", "5m", "EVRF2007", GODLO, {"source": {**SOURCE, "resolution_m": 5.0}}
        )
        mock_session = Mock(spec=requests.Session)
        provider = GugikProvider(session=mock_session, resolution="5m", cache=cache)
        assert provider._get_opendata_url(GODLO) == SOURCE["url"]
        mock_session.get.assert_not_called()

        cache.clear()
        url_5m = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/5m/x.asc"
        mock_session.get.return_value = _gfi_response(
            render_gfi_body([gfi_record(GODLO, resolution="5.00 m", url=url_5m)])
        )
        assert provider._get_opendata_url(GODLO) == url_5m
        cached = cache.get_record("nmt", "5m", "EVRF2007", GODLO)
        assert cached["source"]["url"] == url_5m
        assert cached["source"]["resolution_m"] == 5.0
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) is None


# =========================================================================
# TestGugikNmptProviderCacheIntegration
# =========================================================================


class TestGugikNmptProviderCacheIntegration:
    """GugikNmptProvider uzywa klucza product="nmpt" (nie "nmt")."""

    def test_cache_hit_source_skips_network(self, cache):
        nmpt_source = {**SOURCE, "url": "https://opendata.cached.com/nmpt.asc"}
        cache.set_record("nmpt", "1m", "EVRF2007", GODLO, {"source": nmpt_source})

        mock_session = Mock(spec=requests.Session)
        provider = GugikNmptProvider(session=mock_session, cache=cache)

        assert provider._get_opendata_url(GODLO) == nmpt_source["url"]
        mock_session.get.assert_not_called()

    def test_nmt_entry_does_not_serve_nmpt(self, cache):
        """Wpis "nmt" nie jest trafieniem dla NMPT — miss idzie w siec pod "nmpt"."""
        cache.set_record("nmt", "1m", "EVRF2007", GODLO, {"source": SOURCE})
        nmpt_url = "https://opendata.geoportal.gov.pl/NumDaneWys/NMPT/1/x.asc"
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = _gfi_response(
            render_gfi_body([gfi_record(GODLO, url=nmpt_url)])
        )

        provider = GugikNmptProvider(session=mock_session, cache=cache)
        assert provider._get_opendata_url(GODLO) == nmpt_url

        assert mock_session.get.call_count == 1
        cached = cache.get_record("nmpt", "1m", "EVRF2007", GODLO)
        assert cached["source"]["url"] == nmpt_url
        assert cached["source"]["layer"] == "SkorowidzeNMPT2026"
        assert cache.get_record("nmt", "1m", "EVRF2007", GODLO) == {"source": SOURCE}


# =========================================================================
# TestBdot10kCacheIntegration
# =========================================================================


class TestBdot10kCacheIntegration:
    """Tests for Bdot10kProvider TERYT cache integration."""

    def test_cache_hit_skips_wms(self, cache):
        """Test that a TERYT cache hit skips WMS GetFeatureInfo."""
        cache.set_teryt(500000.0, 400000.0, "1465")

        mock_session = Mock(spec=requests.Session)
        provider = Bdot10kProvider(session=mock_session, cache=cache)

        result = provider._get_teryt_for_point(500000.0, 400000.0)
        assert result == "1465"
        mock_session.get.assert_not_called()

    def test_cache_miss_queries_wms_and_stores(self, cache):
        """Test that a TERYT cache miss queries WMS and stores."""
        mock_session = Mock(spec=requests.Session)
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = (
            '<html>href="/bdot10k/schemat2021/GPKG/14/1465_GPKG.zip"</html>'
        )
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp

        provider = Bdot10kProvider(session=mock_session, cache=cache)
        result = provider._get_teryt_for_point(500000.0, 400000.0)

        assert result == "1465"
        # Should be in cache now
        cached = cache.get_teryt(500000.0, 400000.0)
        assert cached == "1465"

    def test_no_cache_backward_compat(self):
        """Test Bdot10kProvider works without cache."""
        mock_session = Mock(spec=requests.Session)
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = (
            '<html>href="/bdot10k/schemat2021/GPKG/14/1465_GPKG.zip"</html>'
        )
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp

        provider = Bdot10kProvider(session=mock_session)
        result = provider._get_teryt_for_point(500000.0, 400000.0)
        assert result == "1465"

    def test_cache_hit_via_shp_pattern(self, cache):
        """Test TERYT cache hit avoids SHP URL pattern extraction too."""
        cache.set_teryt(600000.0, 500000.0, "2465")

        mock_session = Mock(spec=requests.Session)
        provider = Bdot10kProvider(session=mock_session, cache=cache)

        result = provider._get_teryt_for_point(600000.0, 500000.0)
        assert result == "2465"


# =========================================================================
# TestSoilGridsCacheIntegration
# =========================================================================


class TestSoilGridsCacheIntegration:
    """Tests for SoilGridsProvider cache parameter."""

    def test_accepts_cache_parameter(self, cache):
        """Test that SoilGridsProvider accepts cache parameter."""
        provider = SoilGridsProvider(cache=cache)
        assert provider._cache is cache

    def test_no_cache_backward_compat(self):
        """Test SoilGridsProvider works without cache."""
        provider = SoilGridsProvider()
        assert provider._cache is None


# =========================================================================
# TestCLICacheCommands
# =========================================================================


class TestCLICacheCommands:
    """Tests for CLI cache subcommands."""

    def test_parser_accepts_cache_stats(self):
        """Test that parser accepts 'cache stats'."""
        parser = create_parser()
        args = parser.parse_args(["cache", "stats"])
        assert args.command == "cache"
        assert args.cache_command == "stats"

    def test_parser_accepts_cache_clear(self):
        """Test that parser accepts 'cache clear'."""
        parser = create_parser()
        args = parser.parse_args(["cache", "clear"])
        assert args.command == "cache"
        assert args.cache_command == "clear"

    def test_parser_accepts_cache_path(self):
        """Test that parser accepts 'cache path'."""
        parser = create_parser()
        args = parser.parse_args(["cache", "path"])
        assert args.command == "cache"
        assert args.cache_command == "path"

    def test_cmd_cache_stats(self, tmp_path, monkeypatch, capsys):
        """Test that 'cache stats' prints statistics."""
        monkeypatch.chdir(tmp_path)
        c = MetadataCache(db_path=tmp_path / ".kartograf_cache.db")
        c.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        c.close()

        result = main(["cache", "stats"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Record entries: 1" in captured.out
        assert "TERYT entries" in captured.out
        assert "Sheet entries:" in captured.out

    def test_cmd_cache_clear(self, tmp_path, monkeypatch, capsys):
        """Test that 'cache clear' clears and vacuums."""
        monkeypatch.chdir(tmp_path)
        # First populate some data
        c = MetadataCache(db_path=tmp_path / ".kartograf_cache.db")
        c.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        c.close()

        result = main(["cache", "clear"])
        assert result == 0
        captured = capsys.readouterr()
        assert "cleared" in captured.out.lower()

        c = MetadataCache(db_path=tmp_path / ".kartograf_cache.db")
        try:
            assert c.stats()["record_count"] == 0
        finally:
            c.close()

    def test_cmd_cache_path(self, tmp_path, monkeypatch, capsys):
        """Test that 'cache path' prints the database path."""
        monkeypatch.chdir(tmp_path)
        result = main(["cache", "path"])
        assert result == 0
        captured = capsys.readouterr()
        assert ".kartograf_cache.db" in captured.out

    def test_cmd_cache_no_subcommand(self, capsys):
        """Test that 'cache' without subcommand shows usage."""
        result = main(["cache"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Usage" in captured.out


# =========================================================================
# TestThreadSafety
# =========================================================================


class TestThreadSafety:
    """Tests for threading.Lock protecting write operations."""

    def test_has_write_lock(self, cache):
        """Test that MetadataCache has a threading.Lock for writes."""
        assert hasattr(cache, "_write_lock")
        assert isinstance(cache._write_lock, type(threading.Lock()))

    def test_concurrent_set_record_no_errors(self, cache_path):
        """Test that concurrent set_record calls don't raise errors."""
        cache = MetadataCache(db_path=cache_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    cache.set_record(
                        "nmt",
                        "1m",
                        "EVRF2007",
                        f"sheet-{thread_id}-{i}",
                        {"source": {**SOURCE, "url": f"https://e/{thread_id}/{i}"}},
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cache.stats()["record_count"] == 100
        cache.close()
        assert errors == [], f"Concurrent writes raised errors: {errors}"

    def test_concurrent_set_teryt_no_errors(self, cache_path):
        """Test that concurrent set_teryt calls don't raise errors."""
        cache = MetadataCache(db_path=cache_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    cache.set_teryt(
                        float(thread_id * 1000 + i),
                        float(thread_id * 1000 + i),
                        f"{thread_id:02d}{i:02d}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        cache.close()
        assert errors == [], f"Concurrent writes raised errors: {errors}"

    def test_concurrent_clear_no_errors(self, cache_path):
        """Test that concurrent clear+write calls don't raise errors."""
        cache = MetadataCache(db_path=cache_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    cache.set_record(
                        "nmt",
                        "1m",
                        "EVRF2007",
                        f"sheet-{thread_id}-{i}",
                        {"no_coverage": True},
                    )
            except Exception as e:
                errors.append(e)

        def clearer():
            try:
                for _ in range(5):
                    cache.clear()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(3)]
        threads.append(threading.Thread(target=clearer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        cache.close()
        assert errors == [], f"Concurrent operations raised errors: {errors}"

    def test_concurrent_get_record_returns_own_value(self, tmp_path):
        """Parallel readers on one connection must never see another key's row."""
        cache = MetadataCache(db_path=tmp_path / "c.db")
        for i in range(300):
            cache.set_record(
                "nmt", "1m", "EVRF2007", f"G{i}", {"source": {"url": f"u://G{i}"}}
            )
        errors: list[str] = []

        def worker(seed: int) -> None:
            for k in range(400):
                i = (seed * 37 + k) % 300
                try:
                    got = cache.get_record("nmt", "1m", "EVRF2007", f"G{i}")
                except Exception as e:  # noqa: BLE001 - any exception is a failure here
                    errors.append(f"{type(e).__name__}: {e}")
                    continue
                if got != {"source": {"url": f"u://G{i}"}}:
                    errors.append(f"G{i} -> {got!r}")

        threads = [threading.Thread(target=worker, args=(s,)) for s in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        cache.close()
        assert errors == []

    def test_concurrent_get_sheet_returns_own_payload(self, tmp_path):
        """Parallel readers of sheet_cache must never see another key's payload."""
        cache = MetadataCache(db_path=tmp_path / "c.db")
        for i in range(300):
            cache.set_sheet("cz_tm33", f"T{i}", {"i": i})
        errors: list[str] = []

        def worker(seed: int) -> None:
            for k in range(200):
                i = (seed * 37 + k) % 300
                try:
                    got = cache.get_sheet("cz_tm33", f"T{i}")
                except Exception as e:  # noqa: BLE001 - any exception is a failure here
                    errors.append(f"{type(e).__name__}: {e}")
                    continue
                if got != {"i": i}:
                    errors.append(f"T{i} -> {got!r}")

        threads = [threading.Thread(target=worker, args=(s,)) for s in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        cache.close()
        assert errors == []


# =========================================================================
# TestWALVerification
# =========================================================================


class TestWALVerification:
    """Tests for WAL journal mode verification."""

    def test_wal_mode_enabled_by_default(self, cache_path):
        """Test that WAL mode is successfully enabled."""
        cache = MetadataCache(db_path=cache_path)
        result = cache._conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        cache.close()

    def test_wal_failure_logs_warning(self, cache_path, caplog):
        """Test that a warning is logged when WAL mode fails."""
        real_conn = sqlite3.connect(str(cache_path), check_same_thread=False)

        call_count = 0

        class ConnWrapper:
            """Wraps a real connection, intercepting the first execute call."""

            def __init__(self, conn):
                self._conn = conn

            def execute(self, sql, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                result = self._conn.execute(sql, *args, **kwargs)
                # Intercept the PRAGMA journal_mode call
                if "journal_mode=WAL" in sql:
                    mock_cursor = Mock()
                    mock_cursor.fetchone.return_value = ("delete",)
                    return mock_cursor
                return result

            def commit(self):
                return self._conn.commit()

            def close(self):
                return self._conn.close()

        wrapper = ConnWrapper(real_conn)
        with (
            patch("kartograf.cache.metadata.sqlite3.connect", return_value=wrapper),
            caplog.at_level(logging.WARNING, logger="kartograf.cache.metadata"),
        ):
            cache = MetadataCache(db_path=cache_path)
            cache._conn = real_conn  # Restore real conn for cleanup

        assert any(
            "Failed to enable WAL journal mode" in record.message
            for record in caplog.records
        ), (
            f"Expected WAL warning not found in logs: "
            f"{[r.message for r in caplog.records]}"
        )
        real_conn.close()


# =========================================================================
# TestPruneExpired
# =========================================================================


class TestPruneExpired:
    """Tests for expired entry cleanup."""

    def test_prune_expired_removes_old_record_entries(self, cache_path):
        """Test that prune_expired deletes expired record entries."""
        cache = MetadataCache(db_path=cache_path, ttl_seconds=1)
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        cache.set_record("nmt", "1m", "EVRF2007", "B", {"no_coverage": True})

        # Wait for TTL to expire
        time.sleep(1.1)

        # Add a fresh entry that should NOT be pruned
        cache.set_record("nmt", "1m", "EVRF2007", "C", {"no_coverage": True})

        deleted = cache.prune_expired()
        assert deleted == 2

        # Verify: A and B gone, C still there
        count = cache._conn.execute("SELECT COUNT(*) FROM record_cache").fetchone()[0]
        assert count == 1
        assert cache.get_record("nmt", "1m", "EVRF2007", "C") == {"no_coverage": True}
        cache.close()

    def test_prune_expired_removes_old_teryt_entries(self, cache_path):
        """Test that prune_expired deletes expired TERYT entries."""
        cache = MetadataCache(db_path=cache_path, ttl_seconds=1)
        cache.set_teryt(1.0, 2.0, "1234")
        cache.set_teryt(3.0, 4.0, "5678")

        time.sleep(1.1)

        # Add a fresh entry
        cache.set_teryt(5.0, 6.0, "9999")

        deleted = cache.prune_expired()
        assert deleted == 2

        assert (
            cache._conn.execute("SELECT COUNT(*) FROM teryt_cache").fetchone()[0] == 1
        )
        assert cache.get_teryt(5.0, 6.0) == "9999"
        cache.close()

    def test_prune_expired_returns_zero_when_nothing_expired(self, cache):
        """Test that prune_expired returns 0 when no entries are expired."""
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        cache.set_teryt(1.0, 2.0, "1234")
        deleted = cache.prune_expired()
        assert deleted == 0

    def test_prune_expired_returns_zero_on_empty_cache(self, cache):
        """Test that prune_expired returns 0 on empty database."""
        deleted = cache.prune_expired()
        assert deleted == 0

    def test_close_prunes_expired(self, cache_path):
        """Test that close() calls prune_expired before closing."""
        cache = MetadataCache(db_path=cache_path, ttl_seconds=1)
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})
        cache.set_teryt(1.0, 2.0, "1234")

        time.sleep(1.1)

        # Close should prune expired entries
        cache.close()

        # Re-open and verify entries were pruned
        cache2 = MetadataCache(db_path=cache_path)
        assert cache2.stats()["record_count"] == 0
        assert cache2.stats()["teryt_count"] == 0
        cache2.close()

    def test_get_record_deletes_expired_entry(self, cache_path):
        """Test that get_record opportunistically deletes an expired entry."""
        cache = MetadataCache(db_path=cache_path, ttl_seconds=1)
        cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": SOURCE})

        time.sleep(1.1)

        # get_record returns None and deletes the entry
        result = cache.get_record("nmt", "1m", "EVRF2007", "A")
        assert result is None

        # Verify entry is actually deleted from the database
        count = cache._conn.execute("SELECT COUNT(*) FROM record_cache").fetchone()[0]
        assert count == 0
        cache.close()

    def test_get_teryt_deletes_expired_entry(self, cache_path):
        """Test that get_teryt opportunistically deletes an expired entry."""
        cache = MetadataCache(db_path=cache_path, ttl_seconds=1)
        cache.set_teryt(1.0, 2.0, "1234")

        time.sleep(1.1)

        # get_teryt returns None and deletes the entry
        result = cache.get_teryt(1.0, 2.0)
        assert result is None

        # Verify entry is actually deleted from the database
        count = cache._conn.execute("SELECT COUNT(*) FROM teryt_cache").fetchone()[0]
        assert count == 0
        cache.close()
