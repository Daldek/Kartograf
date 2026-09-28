"""
Unit tests for the GugikLazProvider (LAZ point-cloud download via WFS).

All tests run offline: WFS GetCapabilities / GetFeature responses are provided
as GML/XML fixtures through mocked sessions. Network is never touched.
"""

import logging
import math
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile

# Patch target for the dedicated session created in _fetch_available_years
_LAZ_SESSION_PATCH = "kartograf.providers.pl.gugik_laz.requests.Session"


# ---------------------------------------------------------------------------
# Fixtures (XML/GML strings)
# ---------------------------------------------------------------------------

CAPABILITIES_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" version="2.0.0">
  <wfs:FeatureTypeList>
    <wfs:FeatureType>
      <wfs:Name>gugik:SkorowidzDanychPomiarowychLIDAR2024</wfs:Name>
    </wfs:FeatureType>
    <wfs:FeatureType>
      <wfs:Name>gugik:SkorowidzDanychPomiarowychLIDAR2025</wfs:Name>
    </wfs:FeatureType>
    <wfs:FeatureType>
      <wfs:Name>gugik:SkorowidzDanychPomiarowychLIDAR2018</wfs:Name>
    </wfs:FeatureType>
    <wfs:FeatureType>
      <wfs:Name>gugik:SomethingElse</wfs:Name>
    </wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>
"""

CAPABILITIES_NO_LIDAR = """\
<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" version="2.0.0">
  <wfs:FeatureTypeList>
    <wfs:FeatureType><wfs:Name>gugik:Other</wfs:Name></wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>
"""

EXCEPTION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1" version="2.0.0">
  <ows:Exception exceptionCode="InvalidParameterValue">
    <ows:ExceptionText>Unknown type name</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>
"""


def _feature(
    godlo, year, lower, upper, density="25 p/m2", seq="100", dens_code="81121"
):
    """Build one WFS member element string."""
    url = (
        "https://opendata.geoportal.gov.pl/NumDaneWys/DanePomiaroweLAZ/"
        f"{dens_code}/{dens_code}_{seq}_{godlo}.laz"
    )
    return f"""\
  <wfs:member>
    <gugik:SkorowidzDanychPomiarowychLIDAR{year} gml:id="f.{seq}">
      <gml:boundedBy>
        <gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180">
          <gml:lowerCorner>{lower[0]} {lower[1]}</gml:lowerCorner>
          <gml:upperCorner>{upper[0]} {upper[1]}</gml:upperCorner>
        </gml:Envelope>
      </gml:boundedBy>
      <gugik:godlo>{godlo}</gugik:godlo>
      <gugik:akt_rok>{year}</gugik:akt_rok>
      <gugik:format>LAZ</gugik:format>
      <gugik:char_przestrz>{density}</gugik:char_przestrz>
      <gugik:uklad_xy>PL-2000:S6</gugik:uklad_xy>
      <gugik:url_do_pobrania>{url}</gugik:url_do_pobrania>
    </gugik:SkorowidzDanychPomiarowychLIDAR{year}>
  </wfs:member>"""


def _collection(members, number_returned=None):
    n = len(members) if number_returned is None else number_returned
    return f"""\
<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection
   xmlns:gugik="http://www.gugik.gov.pl"
   xmlns:gml="http://www.opengis.net/gml/3.2"
   xmlns:wfs="http://www.opengis.net/wfs/2.0"
   numberMatched="{n}" numberReturned="{n}">
{chr(10).join(members)}
</wfs:FeatureCollection>"""


# Three tiles: two inside the query bbox, one far outside (for the
# intersection post-filter), all in the 2024 layer.
_TILE_A = _feature(
    "N-33-131-B-a-1-1-4", 2024, (530500, 382500), (531000, 383000), seq="1573132"
)
_TILE_B = _feature(
    "N-33-131-B-a-1-2-3",
    2024,
    (531000, 383000),
    (531500, 383500),
    seq="1601845",
    dens_code="81279",
)
_TILE_OUTSIDE = _feature(
    "Z-99-999-A-a-9-9-9", 2024, (600000, 500000), (600500, 500500), seq="9999"
)

COLLECTION_2024 = _collection([_TILE_A, _TILE_B, _TILE_OUTSIDE])

QUERY_BBOX = BBox(530000.0, 382000.0, 533000.0, 386000.0, "EPSG:2180")


def _make_response(text):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _provider_with_getfeature(text):
    """Provider whose download session returns `text` for every GetFeature."""
    session = MagicMock()
    session.get.return_value = _make_response(text)
    provider = GugikLazProvider(session=session)
    return provider, session


# ===========================================================================
# Init / properties
# ===========================================================================


class TestInitAndProperties:
    def test_defaults(self):
        p = GugikLazProvider()
        assert p.name == "GUGiK LAZ (chmura punktów)"
        assert p.base_url == "https://mapy.geoportal.gov.pl"
        assert p.default_extension == ".laz"
        assert p.vertical_crs == "EVRF2007"

    def test_kron86(self):
        p = GugikLazProvider(vertical_crs="KRON86")
        assert p.vertical_crs == "KRON86"

    def test_invalid_vertical_crs(self):
        with pytest.raises(ValueError, match="Unsupported vertical_crs"):
            GugikLazProvider(vertical_crs="NONSENSE")

    def test_endpoints_present(self):
        p = GugikLazProvider()
        assert "EVRF2007" in p.WFS_ENDPOINTS
        assert "KRON86" in p.WFS_ENDPOINTS
        assert "DanePomiaroweLidarEVRF2007" in p.WFS_ENDPOINTS["EVRF2007"]


class TestLazTile:
    def test_filename_from_url(self):
        tile = LazTile(
            godlo="N-33-131-B-a-1-1-4",
            url="https://opendata.geoportal.gov.pl/x/81121/81121_1573132_N-33-131-B-a-1-1-4.laz",
            year=2024,
            density=25,
            crs="PL-2000:S6",
            min_x=0,
            min_y=0,
            max_x=1,
            max_y=1,
        )
        assert tile.filename == "81121_1573132_N-33-131-B-a-1-1-4.laz"


class TestLazTileUklad:
    """Kaskada ukladu kafla LAZ: uklad_xy -> format godla -> 2000.

    Przeniesione z tests/test_cli.py::TestLazUklad (zn. 8, review max
    2026-08-30) — ``LazTile.uklad`` jest teraz jedynym zrodlem prawdy, uzywanym
    zarowno przez CLI, jak i przez biblioteke (``FileStorage.get_raw_path``).
    """

    def _tile(self, godlo="N-33-131-B-a-1-1-4", crs="PL-2000:S6"):
        return LazTile(
            godlo=godlo,
            url="u/f.laz",
            year=2024,
            density=25,
            crs=crs,
            min_x=0.0,
            min_y=0.0,
            max_x=1.0,
            max_y=1.0,
        )

    def test_crs_pl2000_wins_over_dash_godlo(self):
        # godlo myslnikowe, ale uklad_xy mowi PL-2000 — crs wygrywa
        assert self._tile().uklad == "2000"

    def test_crs_pl1992(self):
        assert self._tile(crs="PL-1992").uklad == "1992"

    def test_none_crs_falls_back_to_dot_godlo(self):
        assert self._tile(godlo="6.162.34.02.3", crs=None).uklad == "2000"

    def test_none_crs_falls_back_to_dash_godlo(self):
        assert self._tile(crs=None).uklad == "1992"

    def test_unrecognized_crs_falls_back_to_godlo(self):
        assert self._tile(crs="EPSG:2180").uklad == "1992"

    def test_everything_fails_defaults_2000_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            assert self._tile(godlo="XYZ99", crs=None).uklad == "2000"
        assert "XYZ99" in caplog.text


# ===========================================================================
# Year discovery (GetCapabilities)
# ===========================================================================


class TestAvailableYears:
    def test_fetch_years_descending(self):
        session = MagicMock()
        session.get.return_value = _make_response(CAPABILITIES_XML)
        p = GugikLazProvider()
        with patch(_LAZ_SESSION_PATCH, return_value=session):
            years = p._fetch_available_years("EVRF2007")
        assert years == [2025, 2024, 2018]

    def test_fetch_years_no_lidar_raises(self):
        session = MagicMock()
        session.get.return_value = _make_response(CAPABILITIES_NO_LIDAR)
        p = GugikLazProvider()
        with patch(_LAZ_SESSION_PATCH, return_value=session), pytest.raises(ValueError):
            p._fetch_available_years("EVRF2007")

    def test_get_years_caches(self):
        p = GugikLazProvider()
        with patch.object(
            p, "_fetch_available_years", return_value=[2025, 2024]
        ) as mock_fetch:
            p._get_available_years("EVRF2007")
            p._get_available_years("EVRF2007")
        mock_fetch.assert_called_once()

    def test_get_years_fallback_on_error(self):
        p = GugikLazProvider()
        with patch.object(
            p, "_fetch_available_years", side_effect=requests.ConnectionError("x")
        ):
            years = p._get_available_years("EVRF2007")
        assert years == GugikLazProvider.FALLBACK_YEARS["EVRF2007"]

    def test_fallback_years_distinct_per_crs(self):
        assert (
            GugikLazProvider.FALLBACK_YEARS["KRON86"]
            != GugikLazProvider.FALLBACK_YEARS["EVRF2007"]
        )
        assert 2010 in GugikLazProvider.FALLBACK_YEARS["KRON86"]


# ===========================================================================
# discover_tiles
# ===========================================================================


class TestDiscoverTiles:
    def test_requires_epsg_2180(self):
        p = GugikLazProvider()
        with pytest.raises(ValueError, match="EPSG:2180"):
            p.discover_tiles(BBox(0, 0, 1, 1, "EPSG:4326"), year=2024)

    def test_parses_and_filters_outside_tiles(self):
        p, session = _provider_with_getfeature(COLLECTION_2024)
        tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        # Tile far outside the bbox is dropped by the intersection post-filter
        godla = [t.godlo for t in tiles]
        assert godla == ["N-33-131-B-a-1-1-4", "N-33-131-B-a-1-2-3"]
        # one query (single year, single page)
        assert session.get.call_count == 1

    def test_tile_attributes_parsed(self):
        p, _ = _provider_with_getfeature(COLLECTION_2024)
        tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        a = tiles[0]
        assert a.url.endswith("81121_1573132_N-33-131-B-a-1-1-4.laz")
        assert a.year == 2024
        assert a.density == 25
        assert a.crs == "PL-2000:S6"
        assert a.min_x == 530500 and a.max_y == 383000

    def test_bbox_param_uses_native_axis_order(self):
        p, session = _provider_with_getfeature(COLLECTION_2024)
        p.discover_tiles(QUERY_BBOX, year=2024)
        called_url = session.get.call_args[0][0]
        # min_x,min_y,max_x,max_y order with urn CRS appended
        assert "BBOX=530000.0%2C382000.0%2C533000.0%2C386000.0%2Curn" in called_url

    def test_min_density_filter(self):
        members = [
            _feature(
                "AAA",
                2024,
                (530500, 382500),
                (531000, 383000),
                density="4 p/m2",
                seq="1",
            ),
            _feature(
                "BBB",
                2024,
                (531000, 383000),
                (531500, 383500),
                density="12 p/m2",
                seq="2",
            ),
        ]
        p, _ = _provider_with_getfeature(_collection(members))
        tiles = p.discover_tiles(QUERY_BBOX, year=2024, min_density=12)
        assert [t.godlo for t in tiles] == ["BBB"]

    def test_newest_per_godlo_dedup(self):
        # Same godło present in 2024 and 2023 → keep 2024
        coll_2024 = _collection(
            [_feature("SAME", 2024, (530500, 382500), (531000, 383000), seq="new")]
        )
        coll_2023 = _collection(
            [_feature("SAME", 2023, (530500, 382500), (531000, 383000), seq="old")]
        )
        session = MagicMock()
        session.get.side_effect = [
            _make_response(coll_2024),
            _make_response(coll_2023),
        ]
        p = GugikLazProvider(session=session)
        p._available_years["EVRF2007"] = [2024, 2023]  # skip GetCapabilities
        tiles = p.discover_tiles(QUERY_BBOX)
        assert len(tiles) == 1
        assert tiles[0].year == 2024
        assert "new" in tiles[0].url

    def test_pagination_follows_pages(self):
        page1 = _collection(
            [
                _feature("P1", 2024, (530500, 382500), (531000, 383000), seq="1"),
                _feature("P2", 2024, (531000, 383000), (531500, 383500), seq="2"),
            ]
        )
        page2 = _collection(
            [_feature("P3", 2024, (531500, 383500), (532000, 384000), seq="3")]
        )
        session = MagicMock()
        session.get.side_effect = [_make_response(page1), _make_response(page2)]
        p = GugikLazProvider(session=session)
        with patch.object(GugikLazProvider, "PAGE_SIZE", 2):
            tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        assert {t.godlo for t in tiles} == {"P1", "P2", "P3"}
        assert session.get.call_count == 2

    def test_exception_report_skipped(self):
        p, _ = _provider_with_getfeature(EXCEPTION_XML)
        tiles = p.discover_tiles(QUERY_BBOX, year=2099)
        assert tiles == []

    def test_network_error_returns_empty(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("boom")
        p = GugikLazProvider(session=session)
        tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        assert tiles == []


# ===========================================================================
# _intersects
# ===========================================================================


class TestIntersects:
    def _tile(self, lx, ly, ux, uy):
        return LazTile("g", "u", 2024, 25, "c", lx, ly, ux, uy)

    def test_inside(self):
        assert GugikLazProvider._intersects(
            self._tile(530500, 382500, 531000, 383000), QUERY_BBOX
        )

    def test_outside(self):
        assert not GugikLazProvider._intersects(
            self._tile(600000, 500000, 600500, 500500), QUERY_BBOX
        )

    def test_edge_touch(self):
        assert GugikLazProvider._intersects(
            self._tile(533000, 386000, 534000, 387000), QUERY_BBOX
        )

    def test_nan_geometry_kept(self):
        nan = math.nan
        assert GugikLazProvider._intersects(self._tile(nan, nan, nan, nan), QUERY_BBOX)


# ===========================================================================
# download
# ===========================================================================


class TestDownload:
    def _stream_response(self, content=b"LASF-fake-laz-bytes"):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.iter_content = MagicMock(return_value=[content])
        return resp

    def test_download_success(self, tmp_path):
        session = MagicMock()
        session.get.return_value = self._stream_response()
        p = GugikLazProvider(session=session)
        out = tmp_path / "tile.laz"
        result = p.download("https://opendata.geoportal.gov.pl/x.laz", out)
        assert result == out
        assert out.read_bytes() == b"LASF-fake-laz-bytes"

    def test_download_creates_parent_dir(self, tmp_path):
        session = MagicMock()
        session.get.return_value = self._stream_response()
        p = GugikLazProvider(session=session)
        out = tmp_path / "laz" / "N-33" / "131" / "tile.laz"
        p.download("https://opendata.geoportal.gov.pl/x.laz", out)
        assert out.exists()

    def test_download_retries_then_fails(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("down")
        p = GugikLazProvider(session=session)
        with (
            patch("kartograf.providers.pl.gugik_laz.time.sleep"),
            pytest.raises(DownloadError),
        ):
            p.download("https://opendata.geoportal.gov.pl/x.laz", tmp_path / "t.laz")
        assert session.get.call_count == GugikLazProvider.MAX_RETRIES
