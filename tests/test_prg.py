"""A1: TERYT discovery from the PRG WFS (raw responses of 2026-10-08)."""

import re
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.pl import prg
from kartograf.providers.pl.prg import discover_teryts_for_bbox, teryt_for_point

FIX = Path(__file__).parent / "fixtures" / "gugik_prg" / "real_2026_10_08"
BARDO = BBox(340000, 290000, 350000, 300000, "EPSG:2180")


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
