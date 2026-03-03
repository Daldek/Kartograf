"""
Tests for the MetadataCache module and its provider integrations.

Tests cover:
- MetadataCache URL caching (set, get, TTL expiry, overwrite)
- MetadataCache TERYT caching (set, get, TTL expiry)
- MetadataCache management (clear, stats, vacuum, close)
- GugikProvider cache integration (cache hit, miss, backward compat)
- GugikNmptProvider cache integration (product key "nmpt")
- GugikOrtoProvider cache integration (cache hit, miss)
- Bdot10kProvider TERYT cache integration (cache hit, miss)
- SoilGridsProvider cache parameter acceptance
- CLI cache commands (stats, clear, path)
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.cli.commands import create_parser, main
from kartograf.providers.bdot10k import Bdot10kProvider
from kartograf.providers.gugik import GugikProvider
from kartograf.providers.gugik_nmpt import GugikNmptProvider
from kartograf.providers.gugik_orto import GugikOrtoProvider
from kartograf.providers.soilgrids import SoilGridsProvider


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
# TestMetadataCacheURL
# =========================================================================


class TestMetadataCacheURL:
    """Tests for URL caching operations."""

    def test_set_and_get(self, cache):
        """Test that set_url followed by get_url returns the same URL."""
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://opendata.example.com/file.asc")
        result = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert result == "https://opendata.example.com/file.asc"

    def test_get_returns_none_when_missing(self, cache):
        """Test that get_url returns None for uncached entries."""
        result = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert result is None

    def test_ttl_expiry(self, short_ttl_cache):
        """Test that entries expire after TTL."""
        short_ttl_cache.set_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
            "https://opendata.example.com/file.asc",
        )
        # Immediately should return the URL
        assert short_ttl_cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt"
        ) is not None

        # Wait for TTL to expire
        time.sleep(1.1)

        result = short_ttl_cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt"
        )
        assert result is None

    def test_overwrite(self, cache):
        """Test that setting the same key overwrites the value."""
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://old-url.com/file.asc")
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://new-url.com/file.asc")
        result = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert result == "https://new-url.com/file.asc"

    def test_different_products_are_separate(self, cache):
        """Test that different products have separate cache entries."""
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://nmt.example.com/file.asc")
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmpt",
                       "https://nmpt.example.com/file.asc")
        assert cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt"
        ) == "https://nmt.example.com/file.asc"
        assert cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmpt"
        ) == "https://nmpt.example.com/file.asc"

    def test_different_resolutions_are_separate(self, cache):
        """Test that different resolutions have separate cache entries."""
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://1m.example.com/file.asc")
        cache.set_url("N-34-130-D-d-2-4", "5m", "EVRF2007", "nmt",
                       "https://5m.example.com/file.asc")
        assert cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt"
        ) == "https://1m.example.com/file.asc"
        assert cache.get_url(
            "N-34-130-D-d-2-4", "5m", "EVRF2007", "nmt"
        ) == "https://5m.example.com/file.asc"

    def test_different_vertical_crs_are_separate(self, cache):
        """Test that different vertical CRS have separate cache entries."""
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://evrf.example.com/file.asc")
        cache.set_url("N-34-130-D-d-2-4", "1m", "KRON86", "nmt",
                       "https://kron.example.com/file.asc")
        assert cache.get_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt"
        ) == "https://evrf.example.com/file.asc"
        assert cache.get_url(
            "N-34-130-D-d-2-4", "1m", "KRON86", "nmt"
        ) == "https://kron.example.com/file.asc"


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
# TestMetadataCacheManagement
# =========================================================================


class TestMetadataCacheManagement:
    """Tests for cache management operations."""

    def test_clear(self, cache):
        """Test that clear removes all entries."""
        cache.set_url("A", "1m", "EVRF2007", "nmt", "https://a.com")
        cache.set_teryt(1.0, 2.0, "1234")
        cache.clear()
        assert cache.get_url("A", "1m", "EVRF2007", "nmt") is None
        assert cache.get_teryt(1.0, 2.0) is None

    def test_stats(self, cache):
        """Test that stats returns correct counts."""
        st = cache.stats()
        assert st["url_count"] == 0
        assert st["teryt_count"] == 0

        cache.set_url("A", "1m", "EVRF2007", "nmt", "https://a.com")
        cache.set_url("B", "1m", "EVRF2007", "nmt", "https://b.com")
        cache.set_teryt(1.0, 2.0, "1234")

        st = cache.stats()
        assert st["url_count"] == 2
        assert st["teryt_count"] == 1
        assert st["db_size_bytes"] > 0
        assert "db_path" in st

    def test_vacuum(self, cache):
        """Test that vacuum runs without error."""
        cache.set_url("A", "1m", "EVRF2007", "nmt", "https://a.com")
        cache.clear()
        cache.vacuum()  # Should not raise

    def test_close(self, cache_path):
        """Test that close properly closes the connection."""
        c = MetadataCache(db_path=cache_path)
        c.set_url("A", "1m", "EVRF2007", "nmt", "https://a.com")
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
    """Tests for GugikProvider cache integration."""

    def _make_wms_response(self, url="https://opendata.example.com/N-34-130-D-d-2-4.asc"):
        """Create a mock WMS response containing an OpenData URL."""
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = f'<html>url:"{url}"</html>'
        mock_resp.raise_for_status = Mock()
        return mock_resp

    def test_cache_hit_skips_wms(self, cache):
        """Test that a cache hit skips the WMS GetFeatureInfo query."""
        # Pre-populate cache
        cache.set_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
            "https://opendata.cached.com/file.asc",
        )

        mock_session = Mock(spec=requests.Session)
        provider = GugikProvider(session=mock_session, cache=cache)

        result = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert result == "https://opendata.cached.com/file.asc"
        # WMS should NOT have been called
        mock_session.get.assert_not_called()

    def test_cache_miss_queries_wms_and_stores(self, cache):
        """Test that a cache miss queries WMS and stores the result."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = self._make_wms_response()

        provider = GugikProvider(session=mock_session, cache=cache)
        result = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert result == "https://opendata.example.com/N-34-130-D-d-2-4.asc"
        # Should have been stored in cache
        cached = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert cached == "https://opendata.example.com/N-34-130-D-d-2-4.asc"
        # WMS was called
        assert mock_session.get.call_count >= 1

    def test_no_cache_backward_compat(self):
        """Test that cache=None preserves default behavior."""
        mock_session = Mock(spec=requests.Session)
        mock_session.get.return_value = self._make_wms_response()

        provider = GugikProvider(session=mock_session)
        # Should not raise any errors about cache
        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert result == "https://opendata.example.com/N-34-130-D-d-2-4.asc"

    def test_cache_product_key_is_nmt(self):
        """Test that GugikProvider uses 'nmt' as cache product key."""
        assert GugikProvider._CACHE_PRODUCT == "nmt"

    def test_5m_resolution_with_cache(self, cache):
        """Test cache integration with 5m resolution."""
        cache.set_url(
            "N-34-130-D-d-2-4", "5m", "EVRF2007", "nmt",
            "https://opendata.cached.com/5m.asc",
        )

        mock_session = Mock(spec=requests.Session)
        provider = GugikProvider(
            session=mock_session, resolution="5m", cache=cache
        )

        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert result == "https://opendata.cached.com/5m.asc"
        mock_session.get.assert_not_called()


# =========================================================================
# TestGugikNmptProviderCacheIntegration
# =========================================================================


class TestGugikNmptProviderCacheIntegration:
    """Tests for GugikNmptProvider cache integration."""

    def test_cache_product_key_is_nmpt(self):
        """Test that GugikNmptProvider uses 'nmpt' as cache product key."""
        assert GugikNmptProvider._CACHE_PRODUCT == "nmpt"

    def test_cache_hit(self, cache):
        """Test that NMPT provider uses cache correctly."""
        cache.set_url(
            "N-34-130-D-d-2-4", "1m", "EVRF2007", "nmpt",
            "https://opendata.cached.com/nmpt.asc",
        )

        mock_session = Mock(spec=requests.Session)
        provider = GugikNmptProvider(session=mock_session, cache=cache)

        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert result == "https://opendata.cached.com/nmpt.asc"
        mock_session.get.assert_not_called()

    def test_no_cache_backward_compat(self):
        """Test that GugikNmptProvider works without cache."""
        mock_session = Mock(spec=requests.Session)
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = 'url:"https://opendata.example.com/nmpt.asc"'
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp

        provider = GugikNmptProvider(session=mock_session)
        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert "nmpt.asc" in result


# =========================================================================
# TestGugikOrtoProviderCacheIntegration
# =========================================================================


class TestGugikOrtoProviderCacheIntegration:
    """Tests for GugikOrtoProvider cache integration."""

    def test_cache_hit_skips_wms(self, cache):
        """Test that a cache hit skips the WMS query for ortofoto."""
        cache.set_url(
            "N-34-130-D-d-2-4", "orto", "none", "orto",
            "https://opendata.cached.com/orto.tif",
        )

        mock_session = Mock(spec=requests.Session)
        provider = GugikOrtoProvider(session=mock_session, cache=cache)

        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert result == "https://opendata.cached.com/orto.tif"
        mock_session.get.assert_not_called()

    def test_cache_miss_stores_result(self, cache):
        """Test that a cache miss stores the WMS result."""
        mock_session = Mock(spec=requests.Session)
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = 'url:"https://opendata.example.com/N-34-130-D-d-2-4.tif"'
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp

        provider = GugikOrtoProvider(session=mock_session, cache=cache)
        result = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "N-34-130-D-d-2-4.tif" in result
        cached = cache.get_url("N-34-130-D-d-2-4", "orto", "none", "orto")
        assert cached is not None

    def test_no_cache_backward_compat(self):
        """Test that GugikOrtoProvider works without cache."""
        mock_session = Mock(spec=requests.Session)
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = 'url:"https://opendata.example.com/orto.tif"'
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp

        provider = GugikOrtoProvider(session=mock_session)
        result = provider._get_opendata_url("N-34-130-D-d-2-4")
        assert "orto.tif" in result


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
        result = main(["cache", "stats"])
        assert result == 0
        captured = capsys.readouterr()
        assert "URL entries" in captured.out
        assert "TERYT entries" in captured.out

    def test_cmd_cache_clear(self, tmp_path, monkeypatch, capsys):
        """Test that 'cache clear' clears and vacuums."""
        monkeypatch.chdir(tmp_path)
        # First populate some data
        c = MetadataCache(db_path=tmp_path / ".kartograf_cache.db")
        c.set_url("A", "1m", "EVRF2007", "nmt", "https://a.com")
        c.close()

        result = main(["cache", "clear"])
        assert result == 0
        captured = capsys.readouterr()
        assert "cleared" in captured.out.lower()

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
