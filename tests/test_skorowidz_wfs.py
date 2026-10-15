"""
Tests of the shared GUGiK WFS sheet index client (``skorowidz_wfs``).

Server answers are the recordings of 2026-10-15
(``tests/fixtures/gugik_wfs/real_2026_10_15/``, see its README) served by a
fake session that picks the file from the request parameters; synthetic
features come from ``wfs_record``/``render_wfs_body``. Offline only.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.coverage import polygon_area
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError
from kartograf.providers.pl.skorowidz_wfs import (
    GML_NS,
    URN_2180,
    WfsIndex,
    area_envelope,
    feature_footprint,
    index_feature_issue,
    overlaps_area,
    parse_index_feature,
    sheet_frame_2180,
    sheet_query_bbox,
)
from kartograf.sources.variants import IndexRef, variants
from tests.conftest import (
    render_wfs_body,
    wfs_fixture,
    wfs_record,
    wfs_requests,
    wfs_response,
    wfs_types,
)

# Pomorze area of the recorded area/page answers (README)
POMORZE = BBox(339000, 744800, 343000, 747000, "EPSG:2180")
SHEET = "N-33-58-A-c-1-4"


def _ref(product: str, vertical_crs: str) -> IndexRef:
    """WFS index of a product and height system from the variant registry."""
    ref = variants(product=product, country="PL", vertical_crs=vertical_crs)[
        0
    ].index_ref
    assert ref is not None
    return ref


def _session(answer: Callable[[dict[str, str]], str | Mock]) -> Mock:
    """Fake session: ``answer(query params)`` gives the body (or a response)."""
    session = Mock()

    def get(url: str, **kwargs: object) -> Mock:
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        result = answer(params)
        return result if isinstance(result, Mock) else wfs_response(result)

    session.get.side_effect = get
    return session


def _index(session: Mock, product: str = "nmt", vertical_crs: str = "EVRF2007"):
    ref = _ref(product, vertical_crs)
    return WfsIndex(lambda: session, ref.endpoint, ref.layer_prefix, timeout=5)


def _features(text: str) -> list[ET.Element]:
    root = ET.fromstring(text)
    return [
        elem
        for elem in root.iter()
        if isinstance(elem.tag, str) and "}Skorowidz" in elem.tag
    ]


def _recorded_feature(name: str, gml_id: str) -> ET.Element:
    (feature,) = [
        f for f in _features(wfs_fixture(name)) if f.get(f"{{{GML_NS}}}id") == gml_id
    ]
    return feature


def _feature_of(record: dict) -> ET.Element:
    (feature,) = _features(render_wfs_body([record]))
    return feature


def _bounds(bbox: BBox) -> tuple[float, float, float, float]:
    return bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y


def _ids(features: list[ET.Element]) -> list[str | None]:
    return [f.get(f"{{{GML_NS}}}id") for f in features]


def _recorded_page(year: int, page: int) -> str:
    return wfs_fixture(f"type_nmt_evrf2007_pomorze_count5_{year}_{page}.xml")


def _per_type_page(params: dict[str, str]) -> str:
    """Recorded COUNT=5 answer (Pomorze, NMT EVRF2007) of a GetFeature."""
    names = params["TYPENAMES"]
    start = int(params.get("STARTINDEX", "0"))
    if "," in names:
        assert start == 0, "the next page of several types is never requested"
        return "page_nmt_evrf2007_pomorze_count5_1.xml"
    return f"type_nmt_evrf2007_pomorze_count5_{names[-4:]}_{start // 5 + 1}.xml"


# ===========================================================================
# Feature types (GetCapabilities)
# ===========================================================================


@pytest.mark.real_wfs_types
class TestFeatureTypes:
    def test_feature_types_newest_first(self):
        session = _session(lambda params: wfs_fixture("caps_nmt_kron86.xml"))
        index = _index(session, vertical_crs="KRON86")

        types = index.feature_types()

        years = [*range(2019, 2003, -1), 2000]
        assert types == [f"gugik:SkorowidzNMT{year}" for year in years]
        # memoized: a second call does not ask the server again
        assert index.feature_types() == types
        assert session.get.call_count == 1
        url = session.get.call_args.args[0]
        assert url.startswith(f"{_ref('nmt', 'KRON86').endpoint}?")
        assert "REQUEST=GetCapabilities" in url

    def test_family_name_outside_pattern_is_logged_and_skipped(self, caplog):
        odd = "gugik:SkorowidzNMT2020_archiwum"
        caps = wfs_fixture("caps_nmt_kron86.xml").replace(
            "<FeatureTypeList>",
            f"<FeatureTypeList><FeatureType><Name>{odd}</Name></FeatureType>",
            1,
        )
        index = _index(_session(lambda params: caps), vertical_crs="KRON86")

        with caplog.at_level(logging.WARNING):
            types = index.feature_types()

        assert odd not in types
        assert len(types) == 17
        assert odd in caplog.text and "NIE odpytywany" in caplog.text

    def test_no_type_is_error(self):
        # the LAZ service has no SkorowidzNMT<year> type
        session = _session(lambda params: wfs_fixture("caps_laz_kron86.xml"))
        index = _index(session, vertical_crs="KRON86")

        with pytest.raises(DownloadError, match="brak typow obiektow SkorowidzNMT"):
            index.feature_types()
        with pytest.raises(DownloadError, match="wynik bylby niepelny"):
            index.feature_types()  # a failure is not memoized


# ===========================================================================
# GetFeature
# ===========================================================================


class TestFeatures:
    def test_one_request_for_all_types(self):
        sheet_answer = wfs_fixture(f"sheet_nmt_evrf2007_{SHEET}.xml")
        session = _session(lambda params: sheet_answer)
        types = wfs_types("nmt_evrf2007")
        bbox = sheet_query_bbox(SheetParser(SHEET))

        found = list(_index(session).features(bbox, types))

        assert len(found) == 8  # every feature of every yearly type
        (params,) = wfs_requests(session, _ref("nmt", "EVRF2007").endpoint)
        assert params["TYPENAMES"] == ",".join(types)
        assert len(types) == 9
        assert params["SRSNAME"] == URN_2180
        assert params["COUNT"] == "1000"
        # URN axis order: northing first
        assert params["BBOX"] == (
            f"{bbox.min_y},{bbox.min_x},{bbox.max_y},{bbox.max_x},{URN_2180}"
        )

    def test_paging_follows_next(self, monkeypatch):
        # one type, recorded with COUNT=5: 5 + 2 features, page 2 from `next`
        monkeypatch.setattr("kartograf.providers.pl.skorowidz_wfs.PAGE_SIZE", 5)
        session = _session(lambda params: wfs_fixture(_per_type_page(params)))

        found = list(_index(session).features(POMORZE, ["gugik:SkorowidzNMT2025"]))

        ids = _ids(found)
        assert len(ids) == len(set(ids)) == 7
        page1 = ET.fromstring(_recorded_page(2025, 1))
        requested = [call.args[0] for call in session.get.call_args_list]
        assert len(requested) == 2
        assert requested[1] == page1.get("next")
        assert parse_qs(urlparse(requested[0]).query)["COUNT"] == ["5"]

    def test_several_types_with_next_are_queried_per_type(self, monkeypatch):
        # The server pages an answer of several types inconsistently (the
        # recorded COUNT=10 pages repeat 2 features and miss 2); one type
        # pages consistently (README): a `next` on the answer of several types
        # drops it and queries every type on its own.
        monkeypatch.setattr("kartograf.providers.pl.skorowidz_wfs.PAGE_SIZE", 5)
        session = _session(lambda params: wfs_fixture(_per_type_page(params)))
        types = wfs_types("nmt_evrf2007")

        found = list(_index(session).features(POMORZE, types))

        ids = _ids(found)
        expected = _ids(_features(wfs_fixture("area_nmt_evrf2007_pomorze.xml.gz")))
        assert len(ids) == len(set(ids)) == 26
        assert set(ids) == set(expected)
        requested = wfs_requests(session)
        assert requested[0]["TYPENAMES"] == ",".join(types)
        first_types = [p["TYPENAMES"] for p in requested[1:] if "STARTINDEX" not in p]
        assert first_types == list(types)
        # never the `next` of the answer of several types
        assert all("," not in p["TYPENAMES"] for p in requested[1:])
        assert len(requested) == 1 + len(types) + 2  # 2025 and 2022 have 2 pages

    def test_repeated_feature_on_next_page_is_error(self):
        record = wfs_record(SHEET)
        endpoint = _ref("nmt", "EVRF2007").endpoint
        pages = {
            None: render_wfs_body([record], next_url=f"{endpoint}?STARTINDEX=1"),
            "1": render_wfs_body([record]),
        }
        session = _session(lambda params: pages[params.get("STARTINDEX")])

        with pytest.raises(
            DownloadError, match=r"strona 2.*powtorzony.*wynik bylby niepelny"
        ):
            list(_index(session).features(POMORZE, ["gugik:SkorowidzNMT2024"]))

    def test_next_outside_service_is_error(self):
        body = render_wfs_body(
            [wfs_record(SHEET)],
            next_url="https://example.com/wfs?REQUEST=GetFeature&STARTINDEX=1",
        )
        session = _session(lambda params: body)

        with pytest.raises(DownloadError, match="spoza uslugi.*wynik bylby niepelny"):
            list(_index(session).features(POMORZE, ["gugik:SkorowidzNMT2024"]))
        assert session.get.call_count == 1

    @pytest.mark.parametrize("declared", ["9", "7", ""])
    def test_number_returned_mismatch_is_error(self, declared):
        answer = wfs_fixture(f"sheet_nmt_evrf2007_{SHEET}.xml").replace(
            'numberMatched="8" numberReturned="8"',
            f'numberMatched="8" numberReturned="{declared}"',
            1,
        )
        session = _session(lambda params: answer)

        with pytest.raises(DownloadError, match="numberReturned.*wynik bylby niepelny"):
            list(_index(session).features(POMORZE, wfs_types("nmt_evrf2007")))

    @pytest.mark.parametrize("status", [400, 200])
    def test_exception_report_is_error(self, status):
        report = wfs_fixture("exception_report.xml")
        session = _session(lambda params: wfs_response(report, status=status))

        with pytest.raises(DownloadError, match="wynik bylby niepelny") as exc:
            list(_index(session).features(POMORZE, ["gugik:SkorowidzNMT1900"]))
        if status == 200:
            assert "TYPENAME 'SkorowidzNMT1900' doesn't exist" in str(exc.value)

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ("Service Unavailable", "nieczytelna"),
            ("<html><body>Blad</body></html>", "nie jest kolekcja obiektow"),
        ],
    )
    def test_non_gml_answer_is_error(self, body, message):
        session = _session(lambda params: body)

        with pytest.raises(DownloadError, match=f"{message}.*wynik bylby niepelny"):
            list(_index(session).features(POMORZE, wfs_types("nmt_evrf2007")))

    def test_empty_answer_is_empty(self):
        sea = "N-33-46-C-c-3-2"
        session = _session(lambda params: wfs_fixture(f"sheet_nmt_evrf2007_{sea}.xml"))
        bbox = sheet_query_bbox(SheetParser(sea))

        assert list(_index(session).features(bbox, wfs_types("nmt_evrf2007"))) == []
        assert session.get.call_count == 1


# ===========================================================================
# Records and footprints
# ===========================================================================


class TestParseIndexFeature:
    def test_parse_maps_fields_to_record(self):
        feature = _recorded_feature(
            f"sheet_nmt_evrf2007_{SHEET}.xml", "SkorowidzNMT2025.1844081"
        )

        record = parse_index_feature(feature)

        assert record is not None
        assert record.sheet == SHEET
        assert record.layer == "SkorowidzNMT2025"
        assert record.url == (
            "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/84020/"
            "84020_1844081_N-33-58-A-c-1-4.asc"
        )
        assert record.resolution_m == 0.5
        assert record.system == "1992"
        assert record.full_sheet is False
        assert record.aktualnosc == "2025-01-30"
        assert record.dt_pzgik == "2026-05-26"
        assert record.raw["format"] == "ARC/INFO ASCII GRID"
        endpoint = _ref("nmt", "EVRF2007").endpoint
        source = record.to_source(endpoint)
        assert source["survey_work_id"] == "DFT.7201.024.2024"
        assert source["index_url"] == endpoint
        assert source["layer"] == "SkorowidzNMT2025"
        assert source["acquisition_year"] == "2025"
        assert source["declared_crs"] == "PL-1992"
        assert source["declared_vertical_crs"] == "PL-EVRF2007-NH"
        assert source["data_source"] == "Skaning laserowy"
        assert source["height_rmse_m"] == 0.15
        assert source["position_rmse_m"] == 0.2
        assert source["archive_module"] == "1:5000"

    def test_pl2000_record(self):
        record = parse_index_feature(
            _feature_of(wfs_record("7.159.25.12.2", system="PL-2000:S7"))
        )

        assert record is not None
        assert (record.sheet, record.system, record.zone) == (
            "7.159.25.12.2",
            "2000",
            7,
        )

    @pytest.mark.parametrize(
        ("record", "issue"),
        [
            (wfs_record("N-33-58-A-c-1-4-1-1"), "sheet"),
            (wfs_record("XYZ"), "sheet"),
            (wfs_record(SHEET, url_do_pobrania=None), "url"),
            (wfs_record(SHEET, url="http://opendata.geoportal.gov.pl/a.asc"), "url"),
        ],
        ids=["8-part-code", "garbage-code", "no-url", "http-url"],
    )
    def test_unusable_feature_is_none(self, record, issue):
        feature = _feature_of(record)

        assert index_feature_issue(feature) == issue
        assert parse_index_feature(feature) is None

    def test_usable_feature_has_no_issue(self):
        assert index_feature_issue(_feature_of(wfs_record(SHEET))) is None


class TestFootprint:
    def test_footprint_in_east_north(self):
        feature = _recorded_feature(
            f"sheet_nmt_evrf2007_{SHEET}.xml", "SkorowidzNMT2025.1844081"
        )

        footprint = feature_footprint(feature)

        assert footprint is not None
        frame = SheetParser(SHEET).get_bbox(crs="EPSG:2180")
        for got, want in zip(
            _bounds(area_envelope([footprint])), _bounds(frame), strict=True
        ):
            assert got == pytest.approx(want, abs=1.0)

    def test_sheet_frame_matches_gugik_footprint(self):
        footprint = feature_footprint(
            _recorded_feature(
                f"sheet_nmt_evrf2007_{SHEET}.xml", "SkorowidzNMT2025.1844081"
            )
        )
        assert footprint is not None

        frame = sheet_frame_2180(SHEET)

        assert overlaps_area(frame, footprint)
        for got, want in zip(
            _bounds(area_envelope([frame])),
            _bounds(area_envelope([footprint])),
            strict=True,
        ):
            assert got == pytest.approx(want, abs=1.0)

    def test_pl2000_sheet_frame(self):
        sheet = "7.159.25.12.2"
        (feature,) = [
            f
            for f in _features(wfs_fixture(f"sheet_nmt_evrf2007_{sheet}.xml"))
            if (record := parse_index_feature(f)) is not None and record.sheet == sheet
        ][:1]
        footprint = feature_footprint(feature)
        assert footprint is not None

        frame = sheet_frame_2180(sheet)

        envelope = area_envelope([frame])
        for got, want in zip(
            _bounds(envelope), _bounds(area_envelope([footprint])), strict=True
        ):
            assert got == pytest.approx(want, abs=1.0)
        # a PL-2000 sheet is not a rectangle in EPSG:2180
        ox, oy = frame[0]
        local = tuple((x - ox, y - oy) for x, y in frame)
        width = envelope.max_x - envelope.min_x
        height = envelope.max_y - envelope.min_y
        assert abs(polygon_area(local)) < 0.99 * width * height


class TestOverlapsArea:
    def test_neighbour_sharing_edge_does_not_overlap(self):
        frame = sheet_frame_2180(SHEET)

        assert not overlaps_area(frame, sheet_frame_2180("N-33-58-A-c-1-3"))
        assert not overlaps_area(frame, sheet_frame_2180("N-33-58-A-c-1-2"))
        assert not overlaps_area(frame, sheet_frame_2180("N-33-58-A-c-1-1"))

    def test_real_overlap(self):
        frame = sheet_frame_2180(SHEET)

        assert overlaps_area(frame, frame)
        # the 1:25000 parent sheet contains it
        assert overlaps_area(frame, sheet_frame_2180("N-33-58-A-c-1"))
        assert overlaps_area(sheet_frame_2180("N-33-58-A-c-1"), frame)

    def test_far_area_does_not_overlap(self):
        assert not overlaps_area(
            sheet_frame_2180(SHEET), sheet_frame_2180("M-34-64-D-d-2-1")
        )


def test_area_envelope_spans_all_areas():
    left = sheet_frame_2180("N-33-58-A-c-1-3")
    right = sheet_frame_2180(SHEET)

    envelope = area_envelope([left, right])

    assert envelope.crs == "EPSG:2180"
    points = [*left, *right]
    assert envelope.min_x == min(x for x, _ in points)
    assert envelope.max_x == max(x for x, _ in points)
    assert envelope.min_y == min(y for _, y in points)
    assert envelope.max_y == max(y for _, y in points)
