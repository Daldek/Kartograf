"""
Unit tests for the GugikLazProvider (LAZ point-cloud download via WFS).

All tests run offline: WFS GetCapabilities / GetFeature responses are provided
as GML/XML fixtures through mocked sessions. Network is never touched.
"""

import math
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile

# Patch the shared GUGiK session factory at provider construction.
_LAZ_SESSION_PATCH = "kartograf.providers.pl.gugik_laz.make_gugik_session"


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
    """Build a member with (E, N) inputs serialized in URN axis order (N, E)."""
    url = (
        "https://opendata.geoportal.gov.pl/NumDaneWys/DanePomiaroweLAZ/"
        f"{dens_code}/{dens_code}_{seq}_{godlo}.laz"
    )
    return f"""\
  <wfs:member>
    <gugik:SkorowidzDanychPomiarowychLIDAR{year} gml:id="f.{seq}">
      <gml:boundedBy>
        <gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180">
          <gml:lowerCorner>{lower[1]} {lower[0]}</gml:lowerCorner>
          <gml:upperCorner>{upper[1]} {upper[0]}</gml:upperCorner>
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

# Envelopes and attributes recorded in the live L1 B3_wfs_axis_test.log
# (2026-09-29). Keep these server coordinates literal, independent of _feature.
SPYTKOWICE_BBOX = BBox(536400, 235100, 536600, 235300, "EPSG:2180")
SPYTKOWICE_MEMBER = """\
<wfs:member>
  <gugik:SkorowidzDanychPomiarowychLIDAR2023>
    <gml:boundedBy>
      <gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180">
        <gml:lowerCorner>234772 535830</gml:lowerCorner>
        <gml:upperCorner>235938 536958</gml:upperCorner>
      </gml:Envelope>
    </gml:boundedBy>
    <gugik:godlo>M-34-76-A-a-1-1-3</gugik:godlo>
    <gugik:akt_rok>2023</gugik:akt_rok>
    <gugik:char_przestrz>4 p/m2</gugik:char_przestrz>
    <gugik:uklad_xy>PL-1992</gugik:uklad_xy>
    <gugik:url_do_pobrania>https://opendata.geoportal.gov.pl/NumDaneWys/DanePomiaroweLAZ/77518/77518_1352498_M-34-76-A-a-1-1-3.laz</gugik:url_do_pobrania>
  </gugik:SkorowidzDanychPomiarowychLIDAR2023>
</wfs:member>"""
LUBUSKIE_MEMBER = """\
<wfs:member>
  <gugik:SkorowidzDanychPomiarowychLIDAR2024>
    <gml:boundedBy>
      <gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180">
        <gml:lowerCorner>535970.420000 234660.930000</gml:lowerCorner>
        <gml:upperCorner>537185.430000 235780.440000</gml:upperCorner>
      </gml:Envelope>
    </gml:boundedBy>
    <gugik:godlo>N-33-127-A-a-2-3-4</gugik:godlo>
    <gugik:akt_rok>2024</gugik:akt_rok>
    <gugik:uklad_xy>PL-1992</gugik:uklad_xy>
    <gugik:url_do_pobrania>https://opendata.geoportal.gov.pl/test_N-33-127-A-a-2-3-4.laz</gugik:url_do_pobrania>
  </gugik:SkorowidzDanychPomiarowychLIDAR2024>
</wfs:member>"""


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
    provider._available_years["EVRF2007"] = [2024, 2023]
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
    """Uklad kafla LAZ z uklad_xy (``parse_pl_uklad``, D3); nieznany = blad.

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

    @pytest.mark.parametrize(
        ("godlo", "crs"),
        [
            ("6.162.34.02.3", None),
            ("N-33-131-B-a-1-1-4", None),
            ("N-33-131-B-a-1-1-4", "EPSG:2180"),
            ("6.162.34.02.3", "PL-2000"),
            ("XYZ99", None),
        ],
    )
    def test_unrecognized_crs_is_an_error_not_a_guess(self, godlo, crs):
        """D3: bez rozpoznanego uklad_xy nie zgadujemy z godla (dawniej:
        kaskada godlo -> 2000, segment pl_2000 przy sidecarze EPSG:2180)."""
        with pytest.raises(ValidationError, match="uklad_xy"):
            self._tile(godlo=godlo, crs=crs).uklad  # noqa: B018


# ===========================================================================
# Year discovery (GetCapabilities)
# ===========================================================================


class TestAvailableYears:
    def test_fetch_years_descending(self):
        session = MagicMock()
        session.get.return_value = _make_response(CAPABILITIES_XML)
        with patch(_LAZ_SESSION_PATCH, return_value=session):
            p = GugikLazProvider()
        years = p._fetch_available_years("EVRF2007")
        assert years == [2025, 2024, 2018]

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            (CAPABILITIES_NO_LIDAR, "LIDAR"),
            ("<wfs:WFS_Capabilities", "nieczytelna"),
            (EXCEPTION_XML, "Unknown type name"),
        ],
    )
    def test_invalid_capabilities_abort_discovery(self, text, message):
        p = GugikLazProvider()
        with (
            patch("requests.Session.get", return_value=_make_response(text)),
            pytest.raises(DownloadError, match=message),
        ):
            p.discover_tiles(QUERY_BBOX)

    def test_get_years_caches(self):
        p = GugikLazProvider()
        with patch.object(
            p, "_fetch_available_years", return_value=[2025, 2024]
        ) as mock_fetch:
            p._get_available_years("EVRF2007")
            p._get_available_years("EVRF2007")
        mock_fetch.assert_called_once()

    def test_capabilities_network_failure_raises_without_caching(self):
        p = GugikLazProvider()
        with (
            patch(
                "requests.Session.get", side_effect=requests.ConnectionError("reset")
            ) as get,
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError, match="GetCapabilities.*EVRF2007"),
        ):
            p.discover_tiles(QUERY_BBOX)
        assert get.call_count == 3
        assert "EVRF2007" not in p._available_years

        with patch(
            "requests.Session.get", return_value=_make_response(CAPABILITIES_XML)
        ):
            assert p._get_available_years("EVRF2007") == [2025, 2024, 2018]

    def test_capabilities_recovers_after_connection_reset(self):
        session = MagicMock()
        session.get.side_effect = [
            requests.ConnectionError("reset"),
            _make_response(CAPABILITIES_XML),
        ]
        p = GugikLazProvider(session=session)
        with patch("kartograf.transport.http.time.sleep"):
            assert p._get_available_years("EVRF2007") == [2025, 2024, 2018]
        assert session.get.call_count == 2


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

    def test_bbox_param_epsg_axis_order_north_east(self):
        p, session = _provider_with_getfeature(COLLECTION_2024)
        p.discover_tiles(QUERY_BBOX, year=2024)
        called_url = session.get.call_args[0][0]
        assert "BBOX=382000.0%2C530000.0%2C386000.0%2C533000.0%2Curn" in called_url

    def test_spytkowice_tile_keeps_easting_northing(self):
        p, _ = _provider_with_getfeature(_collection([SPYTKOWICE_MEMBER]))
        tiles = p.discover_tiles(SPYTKOWICE_BBOX, year=2023)

        assert [tile.godlo for tile in tiles] == ["M-34-76-A-a-1-1-3"]
        tile = tiles[0]
        assert (tile.min_x, tile.min_y, tile.max_x, tile.max_y) == (
            535830,
            234772,
            536958,
            235938,
        )
        assert tile.filename == "77518_1352498_M-34-76-A-a-1-1-3.laz"
        assert tile.year == 2023
        assert tile.density == 4
        assert tile.crs == "PL-1992"

    def test_transposed_lubuskie_tile_is_filtered(self):
        p, _ = _provider_with_getfeature(
            _collection([SPYTKOWICE_MEMBER, LUBUSKIE_MEMBER])
        )
        tiles = p.discover_tiles(SPYTKOWICE_BBOX, year=2023)
        assert [tile.godlo for tile in tiles] == ["M-34-76-A-a-1-1-3"]

    def test_only_transposed_tiles_raise_axis_error(self):
        p, _ = _provider_with_getfeature(_collection([LUBUSKIE_MEMBER]))
        with pytest.raises(DownloadError, match="kolejnosci osi"):
            p.discover_tiles(SPYTKOWICE_BBOX, year=2024)

    @pytest.mark.parametrize(
        "srs_name",
        [
            "urn:ogc:def:crs:EPSG::2180",
            "http://www.opengis.net/def/crs/EPSG/0/2180",
            "https://www.opengis.net/def/crs/EPSG/0/2180",
            "EPSG:2180",
            None,
        ],
    )
    def test_envelope_axis_order_follows_srs_name(self, srs_name):
        member = SPYTKOWICE_MEMBER
        original = 'srsName="urn:ogc:def:crs:EPSG::2180"'
        replacement = f'srsName="{srs_name}"' if srs_name else ""
        member = member.replace(original, replacement)
        if srs_name == "EPSG:2180":
            member = member.replace("234772 535830", "535830 234772").replace(
                "235938 536958", "536958 235938"
            )
        p, _ = _provider_with_getfeature(_collection([member]))
        tiles = p.discover_tiles(SPYTKOWICE_BBOX, year=2023)
        assert [(t.godlo, t.min_x, t.min_y, t.max_x, t.max_y) for t in tiles] == [
            ("M-34-76-A-a-1-1-3", 535830, 234772, 536958, 235938)
        ]

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
        p._available_years["EVRF2007"] = [2024]
        with patch.object(GugikLazProvider, "PAGE_SIZE", 2):
            tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        assert {t.godlo for t in tiles} == {"P1", "P2", "P3"}
        assert session.get.call_count == 2

    def test_unknown_year_reports_available_years_without_retry(self):
        session = MagicMock()
        session.get.return_value = _make_response(CAPABILITIES_XML)
        provider = GugikLazProvider(session=session)

        with pytest.raises(DownloadError) as exc:
            provider.discover_tiles(QUERY_BBOX, year=2099)

        assert "rocznik 2099 nie istnieje w usludze EVRF2007" in str(exc.value)
        assert "2025, 2024, 2018" in str(exc.value)
        assert "ponow pobranie" not in str(exc.value)
        assert session.get.call_count == 1
        assert "REQUEST=GetCapabilities" in session.get.call_args.args[0]

    def test_exception_report_raises_with_server_text(self):
        p, _ = _provider_with_getfeature(EXCEPTION_XML)
        with pytest.raises(DownloadError, match="2024.*Unknown type name"):
            p.discover_tiles(QUERY_BBOX, year=2024)

    def test_unreadable_response_raises_download_error(self):
        p, _ = _provider_with_getfeature("<wfs:FeatureCollection")
        with pytest.raises(DownloadError, match="2024.*nieczytelna"):
            p.discover_tiles(QUERY_BBOX, year=2024)

    def test_network_error_raises_download_error(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("reset")
        p = GugikLazProvider(session=session)
        p._available_years["EVRF2007"] = [2024]
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError, match="2024.*reset.*wynik bylby niepelny"),
        ):
            p.discover_tiles(QUERY_BBOX, year=2024)
        assert session.get.call_count == 3

    def test_partial_year_failure_raises_instead_of_partial_result(self):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(COLLECTION_2024),
            *(requests.ConnectionError("reset") for _ in range(3)),
        ]
        p = GugikLazProvider(session=session)
        p._available_years["EVRF2007"] = [2024, 2023]
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError, match="2023.*wynik bylby niepelny"),
        ):
            p.discover_tiles(QUERY_BBOX)
        assert session.get.call_count == 4

    def test_page_failure_raises_instead_of_partial_result(self):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(_collection([_TILE_A])),
            *(requests.ConnectionError("reset") for _ in range(3)),
        ]
        p = GugikLazProvider(session=session)
        p._available_years["EVRF2007"] = [2024]
        with (
            patch.object(p, "PAGE_SIZE", 1),
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError, match="2024.*wynik bylby niepelny"),
        ):
            p.discover_tiles(QUERY_BBOX, year=2024)
        assert session.get.call_count == 4

    def test_page_retry_keeps_all_tiles(self):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(_collection([_TILE_A])),
            requests.ConnectionError("reset"),
            _make_response(_collection([_TILE_B])),
            _make_response(_collection([])),
        ]
        p = GugikLazProvider(session=session)
        p._available_years["EVRF2007"] = [2024]
        with (
            patch.object(p, "PAGE_SIZE", 1),
            patch("kartograf.transport.http.time.sleep"),
        ):
            tiles = p.discover_tiles(QUERY_BBOX, year=2024)
        assert [tile.godlo for tile in tiles] == [
            "N-33-131-B-a-1-1-4",
            "N-33-131-B-a-1-2-3",
        ]
        assert session.get.call_count == 4


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
