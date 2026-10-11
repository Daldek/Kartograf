"""PRG WFS: TERYT discovery (2026-10-08) and the PL land mask (2026-10-11)."""

import gzip
import re
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.transform import from_origin

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.pl import prg
from kartograf.providers.pl.prg import (
    LandMask,
    discover_teryts_for_bbox,
    fetch_land_mask,
    teryt_for_point,
)

FIX = Path(__file__).parent / "fixtures" / "gugik_prg" / "real_2026_10_08"
BARDO = BBox(340000, 290000, 350000, 300000, "EPSG:2180")
LAND_FIX = Path(__file__).parent / "fixtures" / "gugik_prg" / "land_mask_2026_10_11"
COAST = BBox(465000, 735000, 490000, 765000, "EPSG:2180")


def _land_session(*, inland=False, a00=None, error_layer=None, error_status=200):
    filenames = {
        "ms:W02_Morze_terytorialne_RP": (
            f"W02_Morze_terytorialne_RP_bbox_{'inland' if inland else 'coast'}.xml"
        ),
        "ms:W03_Morskie_wody_wewnetrzne": (
            f"W03_Morskie_wody_wewnetrzne_bbox_{'inland' if inland else 'coast'}.xml"
        ),
    }
    with gzip.open(LAND_FIX / "A00_Granice_panstwa.xml.gz", "rb") as file:
        country = file.read()

    def respond(*_args, **kwargs):
        layer = kwargs["params"]["TYPENAMES"]
        if layer == error_layer:
            body = (LAND_FIX / "exception_report.xml").read_bytes()
        elif layer == "ms:A00_Granice_panstwa":
            body = a00 if a00 is not None else country
        else:
            body = (LAND_FIX / filenames[layer]).read_bytes()
        response = Mock()
        response.content = body
        response.status_code = error_status if layer == error_layer else 200
        if response.status_code >= 400:
            error = requests.HTTPError(str(response.status_code))
            error.response = response
            response.raise_for_status = Mock(side_effect=error)
        else:
            response.raise_for_status = Mock()
        return response

    session = Mock()
    session.get.side_effect = respond
    return session


def _session(body: str | None = None, status: int = 200) -> Mock:
    response = Mock()
    response.status_code = status
    response.text = body or ""
    response.content = (body or "").encode()
    if status >= 400:
        error = requests.HTTPError(f"{status}")
        error.response = response
        response.raise_for_status = Mock(side_effect=error)
    else:
        response.raise_for_status = Mock()
    session = Mock()
    session.get.return_value = response
    return session


def test_two_counties():
    session = _session((FIX / "two_counties.xml").read_text(encoding="utf-8"))
    assert discover_teryts_for_bbox(BARDO, session=session) == ["0208", "0224"]
    params = session.get.call_args.kwargs["params"]
    # WFS 2.0 with the urn CRS uses the (N, E) axis order
    assert params["BBOX"] == "290000,340000,300000,350000,urn:ogc:def:crs:EPSG::2180"
    assert params["TYPENAMES"] == "ms:A02_Granice_powiatow"


def test_bbox_param_widened_outward():
    """P3: rounding to the nearest metre shrank the area by up to 0.5 m."""
    session = _session((FIX / "two_counties.xml").read_text(encoding="utf-8"))
    area = BBox(340000.6004, 290000.3996, 349999.4004, 299999.6004, "EPSG:2180")
    discover_teryts_for_bbox(area, session=session)
    params = session.get.call_args.kwargs["params"]
    assert params["BBOX"] == (
        "290000.399,340000.6,299999.601,349999.401,urn:ogc:def:crs:EPSG::2180"
    )


def test_number_returned_mismatch_raises():
    """P6: a feature without JPT_KOD_JE must not shorten the list silently."""
    body = (FIX / "two_counties.xml").read_text(encoding="utf-8")
    body = re.sub(r"<ms:JPT_KOD_JE>[^<]*</ms:JPT_KOD_JE>", "", body, count=1)
    with pytest.raises(DownloadError, match="numberReturned=2"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_sea_is_empty_list():
    session = _session((FIX / "no_counties.xml").read_text(encoding="utf-8"))
    assert discover_teryts_for_bbox(BARDO, session=session) == []


def test_service_error_raises():
    session = _session((FIX / "error_400.xml").read_text(encoding="utf-8"), 400)
    with pytest.raises(DownloadError):
        discover_teryts_for_bbox(BARDO, session=session)


def test_exception_report_with_200_raises():
    body = (FIX / "error_400.xml").read_text(encoding="utf-8")
    with pytest.raises(DownloadError, match="PRG"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_not_xml_raises():
    with pytest.raises(DownloadError, match="PRG"):
        discover_teryts_for_bbox(BARDO, session=_session("<html>oops"))


def _two_counties_with(matched: str) -> str:
    body = (FIX / "two_counties.xml").read_text(encoding="utf-8")
    return re.sub(r'numberMatched="[^"]*"', f'numberMatched="{matched}"', body)


def test_discover_truncated_result_raises():
    """Review Focus 1: numberReturned < numberMatched = paging cut the list."""
    body = _two_counties_with("400")
    with pytest.raises(DownloadError, match="niepelna"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_unknown_match_count_at_page_limit_raises(monkeypatch):
    """Review Focus 1: 'unknown' count and a full page = maybe cut -> error."""
    monkeypatch.setattr(prg, "_COUNT", 2)
    body = _two_counties_with("unknown")
    with pytest.raises(DownloadError, match="niepelna"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_unknown_match_count_below_page_limit_passes():
    body = _two_counties_with("unknown")
    assert discover_teryts_for_bbox(BARDO, session=_session(body)) == ["0208", "0224"]


def test_next_page_link_raises():
    """Review Focus 1: a 'next' link on the collection = more pages exist."""
    body = (FIX / "two_counties.xml").read_text(encoding="utf-8")
    body = re.sub(
        r"(<(?:\w+:)?FeatureCollection)", r'\1 next="https://x/page2"', body, count=1
    )
    with pytest.raises(DownloadError, match="niepelna"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_real_paged_response_raises():
    """Review Focus 1, real form: MapServer pages with 'unknown' + 'next'.

    Recorded with COUNT=1 for the two-county area: numberMatched="unknown",
    numberReturned="1" and a ``next`` link - below our page size, so only
    the ``next`` link reveals the cut.
    """
    body = (FIX / "truncated_count1.xml").read_text(encoding="utf-8")
    with pytest.raises(DownloadError, match="niepelna"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_bad_code_raises():
    body = (FIX / "two_counties.xml").read_text(encoding="utf-8")
    body = body.replace(">0224<", ">22A<")
    with pytest.raises(DownloadError, match="TERYT"):
        discover_teryts_for_bbox(BARDO, session=_session(body))


def test_discover_transforms_bbox_to_2180():
    """Review Focus 2: a bbox in EPSG:4326 is queried in EPSG:2180."""
    session = _session((FIX / "two_counties.xml").read_text(encoding="utf-8"))
    wgs = BBox(16.70, 50.45, 16.80, 50.55, "EPSG:4326")
    discover_teryts_for_bbox(wgs, session=session)
    bbox_param = session.get.call_args.kwargs["params"]["BBOX"]
    min_n, min_e = (float(v) for v in bbox_param.split(",")[:2])
    assert 250000 < min_n < 350000 and 300000 < min_e < 400000


def test_cache_hit_skips_network(tmp_path):
    from kartograf.cache.metadata import MetadataCache

    cache = MetadataCache(db_path=tmp_path / "c.db")
    session = _session((FIX / "two_counties.xml").read_text(encoding="utf-8"))
    assert discover_teryts_for_bbox(BARDO, session=session, cache=cache) == [
        "0208",
        "0224",
    ]
    other = _session("must not be used")
    assert discover_teryts_for_bbox(BARDO, session=other, cache=cache) == [
        "0208",
        "0224",
    ]
    other.get.assert_not_called()


def test_teryt_for_point():
    """Raw point answer (2026-10-08): E345000/N295000 lies in 0224 only.

    The query must be a point-sized square around the point: a wider square
    could reach the lower-coded neighbour 0208 across the border.
    """
    session = _session((FIX / "point_0224.xml").read_text(encoding="utf-8"))
    assert teryt_for_point(345000, 295000, "EPSG:2180", session=session) == "0224"
    params = session.get.call_args.kwargs["params"]
    # the 1 m square around the point, not widened to whole metres
    assert params["BBOX"] == (
        "294999.5,344999.5,295000.5,345000.5,urn:ogc:def:crs:EPSG::2180"
    )


def test_teryt_for_point_boundary_takes_lowest_code():
    """Synthetic boundary case: an answer with two powiats -> the lower code.

    The two-county AREA response stands in for a point exactly on a border;
    it is not the real answer for this point (see ``test_teryt_for_point``).
    """
    session = _session((FIX / "two_counties.xml").read_text(encoding="utf-8"))
    assert teryt_for_point(345000, 295000, "EPSG:2180", session=session) == "0208"


def test_teryt_for_point_sea_is_none():
    session = _session((FIX / "no_counties.xml").read_text(encoding="utf-8"))
    assert teryt_for_point(450000, 800000, "EPSG:2180", session=session) is None


def test_teryt_for_point_uses_point_cache(tmp_path):
    from kartograf.cache.metadata import MetadataCache

    cache = MetadataCache(db_path=tmp_path / "c.db")
    cache.set_teryt(345000.0, 295000.0, "0224")
    other = _session("unused")
    assert (
        teryt_for_point(345000, 295000, "EPSG:2180", session=other, cache=cache)
        == "0224"
    )
    other.get.assert_not_called()


def test_teryt_for_point_sea_answer_is_cached(tmp_path):
    """A point in the sea is not asked again (empty answer in the area cache)."""
    from kartograf.cache.metadata import MetadataCache

    cache = MetadataCache(db_path=tmp_path / "c.db")
    sea = _session((FIX / "no_counties.xml").read_text(encoding="utf-8"))
    assert (
        teryt_for_point(450000, 800000, "EPSG:2180", session=sea, cache=cache) is None
    )
    other = _session("must not be used")
    assert (
        teryt_for_point(450000, 800000, "EPSG:2180", session=other, cache=cache) is None
    )
    other.get.assert_not_called()


def _write_mask_raster(path, values, transform):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=len(values),
        height=1,
        count=1,
        dtype="float32",
        crs="EPSG:2180",
        transform=transform,
    ) as dst:
        dst.write(np.array([values], dtype=np.float32), 1)


def test_gml_axis_order_swapped():
    session = _land_session()
    mask = fetch_land_mask(COAST, session=session)
    assert len(mask.country) == 1
    assert len(mask.water) == 2
    with gzip.open(LAND_FIX / "A00_Granice_panstwa.xml.gz", "rb") as file:
        first_n, first_e = (
            float(value)
            for value in re.search(
                rb"<gml:posList[^>]*>([\s\S]*?)</gml:posList>", file.read()
            )
            .group(1)
            .split()[:2]
        )
    assert mask.country[0]["coordinates"][0][0] == [first_e, first_n]
    assert mask.water[0]["type"] == "Polygon"
    assert mask.water[1]["type"] == "MultiPolygon"
    assert len(mask.water[1]["coordinates"][0]) == 59  # exterior + 58 holes
    calls = [call.kwargs["params"] for call in session.get.call_args_list]
    assert [params["TYPENAMES"] for params in calls] == [
        "ms:A00_Granice_panstwa",
        "ms:W02_Morze_terytorialne_RP",
        "ms:W03_Morskie_wody_wewnetrzne",
    ]
    assert "BBOX" not in calls[0]
    assert all(
        params["BBOX"] == "735000,465000,765000,490000,urn:ogc:def:crs:EPSG::2180"
        for params in calls[1:]
    )


def test_mask_on_recorded_coast(tmp_path):
    mask = fetch_land_mask(COAST, session=_land_session())
    # Integer pixel centres nearest the report's projected control points.
    controls = [
        (470878, 739270, 0.0, True),  # Gdynia on land
        (470500, 739000, 5.0, True),  # Gdynia, inland from the reported point
        (471182, 739268, 5.0, False),  # Gdynia 300 m offshore
        (472961, 763008, 0.0, False),  # Zatoka Pucka near Kuznica
        (489088, 750152, 5.0, False),  # 2 km east of reported Hel point; open sea
        (480000, 800000, 5.0, False),  # Baltic outside A00
    ]
    masked = zeros = 0
    for index, (x, y, value, expected_land) in enumerate(controls):
        transform = from_origin(x - 0.5, y + 0.5, 1, 1)
        country = rasterize(
            [(geom, 1) for geom in mask.country],
            out_shape=(1, 1),
            transform=transform,
            dtype=np.uint8,
        )
        water = rasterize(
            [(geom, 1) for geom in mask.water],
            out_shape=(1, 1),
            transform=transform,
            dtype=np.uint8,
        )
        assert bool(country[0, 0] and not water[0, 0]) is expected_land, (x, y)
        tif = tmp_path / f"coast_{index}.tif"
        _write_mask_raster(tif, [value], transform)
        actual_masked, actual_zeros = mask.apply(tif, -9999.0)
        with rasterio.open(tif) as src:
            assert src.read(1)[0, 0] == (value if expected_land else -9999.0)
            assert src.nodata == -9999.0
        assert actual_masked == int(not expected_land)
        assert actual_zeros == int(expected_land and value == 0)
        masked += actual_masked
        zeros += actual_zeros
    assert (masked, zeros) == (4, 1)


def test_inland_area_skips_empty_water_layers():
    session = _land_session(inland=True)
    mask = fetch_land_mask(
        BBox(600000, 500000, 602000, 502000, "EPSG:2180"), session=session
    )
    assert len(mask.country) == 1
    assert mask.water == ()
    assert all(
        call.kwargs["params"]["BBOX"]
        == "500000,600000,502000,602000,urn:ogc:def:crs:EPSG::2180"
        for call in session.get.call_args_list[1:]
    )


def test_a00_missing_raises():
    empty = (LAND_FIX / "W02_Morze_terytorialne_RP_bbox_inland.xml").read_bytes()
    with pytest.raises(DownloadError):
        fetch_land_mask(COAST, session=_land_session(a00=empty))


def test_land_service_error_raises():
    with pytest.raises(DownloadError):
        fetch_land_mask(
            COAST, session=_land_session(error_layer="ms:W02_Morze_terytorialne_RP")
        )


def test_land_http_error_raises():
    with pytest.raises(DownloadError) as error:
        fetch_land_mask(
            COAST,
            session=_land_session(
                error_layer="ms:W02_Morze_terytorialne_RP", error_status=400
            ),
        )
    assert error.value.status_code == 400


def test_land_non_xml_raises():
    with pytest.raises(DownloadError):
        fetch_land_mask(COAST, session=_land_session(a00=b"<broken"))


def test_land_bbox_rounds_outward():
    session = _land_session(inland=True)
    area = BBox(600000.6004, 500000.3996, 602000.4004, 502000.6004, "EPSG:2180")
    fetch_land_mask(area, session=session)
    assert all(
        call.kwargs["params"]["BBOX"]
        == "500000.399,600000.6,502000.601,602000.401,urn:ogc:def:crs:EPSG::2180"
        for call in session.get.call_args_list[1:]
    )


def test_land_incomplete_answer_raises():
    empty = (LAND_FIX / "W02_Morze_terytorialne_RP_bbox_inland.xml").read_bytes()
    incomplete = empty.replace(b'numberReturned="0"', b'numberReturned="1"')
    with pytest.raises(DownloadError):
        fetch_land_mask(COAST, session=_land_session(a00=incomplete))
    next_page = empty.replace(
        b"numberReturned=", b'next="https://x/page2" numberReturned='
    )
    with pytest.raises(DownloadError):
        fetch_land_mask(COAST, session=_land_session(a00=next_page))


def test_pixel_center_rule(tmp_path):
    square = {
        "type": "Polygon",
        "coordinates": [[[0.2, 0.2], [1.8, 0.2], [1.8, 1.8], [0.2, 1.8], [0.2, 0.2]]],
    }
    tif = tmp_path / "centers.tif"
    _write_mask_raster(tif, [5.0, 0.0, 5.0], from_origin(-0.5, 1.5, 1, 1))
    assert LandMask((square,), ()).apply(tif, -9999.0) == (2, 1)
    with rasterio.open(tif) as src:
        np.testing.assert_array_equal(src.read(1), [[-9999.0, 0.0, -9999.0]])
        assert src.nodata == -9999.0


@pytest.mark.parametrize("strip_px", [6, 12, 4_000_000])
def test_mask_in_strips_equals_whole(tmp_path, monkeypatch, strip_px):
    """Row strips (1, 2 rows or the whole raster) give the same mask and counts:
    land = western half minus a water square in its NW corner."""
    monkeypatch.setattr(prg, "_MASK_STRIP_PX", strip_px)
    country = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [3, 0], [3, 5], [0, 5], [0, 0]]],
    }
    water = {
        "type": "Polygon",
        "coordinates": [[[0, 3], [1, 3], [1, 5], [0, 5], [0, 3]]],
    }
    values = np.zeros((5, 6), dtype=np.float32)
    values[:, 1] = 7.0
    tif = tmp_path / "strips.tif"
    with rasterio.open(
        tif,
        "w",
        driver="GTiff",
        width=6,
        height=5,
        count=1,
        dtype="float32",
        crs="EPSG:2180",
        transform=from_origin(0, 5, 1, 1),
    ) as dst:
        dst.write(values, 1)

    masked, zeros = LandMask((country,), (water,)).apply(tif, -9999.0)

    expected = values.copy()
    expected[:, 3:] = -9999.0  # east of the country
    expected[0:2, 0] = -9999.0  # water square (rows 0-1, column 0)
    with rasterio.open(tif) as src:
        np.testing.assert_array_equal(src.read(1), expected)
    assert (masked, zeros) == (17, 8)  # 15 + 2 masked; zeros: columns 0 and 2
