"""
Regression tests of record selection and data handling on RAW GUGiK responses.

NMT/NMPT: WFS sheet index answers recorded 2026-10-15
(``tests/fixtures/gugik_wfs/real_2026_10_15/``, cases in its README). A
sheet lookup sends ONE GetFeature - every yearly type of the service, the
20 m square around the sheet centre - and ``recorded_wfs`` answers it with
the unedited recording of exactly that query; a case the round did not
record builds its answer with ``wfs_record``/``render_wfs_body`` from the
values of the live round of 2026-10-06. Orthophoto fixtures in
``tests/fixtures/gugik_skorowidz/real_2026_10_06/orto`` are unedited WMS
bodies from the live E2E round of 2026-10-06
(``docs/research/2026-10-06-e2e-brzegowe-i-review/``, requirement E18), each
index layer returned from a file of its name (layer order: newest -> oldest);
``tests/fixtures/gugik_laz/real_2026_10_10/`` (LAZ WFS) holds unedited bodies
recorded 2026-10-10 for exactly ``W2_BBOX`` and ``WRO_BBOX``.
"""

import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.laz import download_laz_area
from kartograf.exceptions import DownloadError, NoCoverageError, YearRangeError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzRecord,
    parse_skorowidz_records,
    select_campaign_records,
    select_sheet_record,
)
from kartograf.providers.pl.skorowidz_wfs import GUGIK_NS, parse_index_feature
from kartograf.sources.variants import source_format, variants
from tests.conftest import (
    WFS_FIXTURES,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_record,
    wfs_requests,
    wfs_response,
    wfs_types,
)

REAL = Path(__file__).parent.parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06"
REAL_LAZ = Path(__file__).parent.parent / "fixtures" / "gugik_laz" / "real_2026_10_10"

EMPTY = (
    Path(__file__).parent.parent / "fixtures" / "gugik_skorowidz" / "empty.body"
).read_text(encoding="utf-8")


def _response(body: str) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


def routed_session(path_for_layer) -> Mock:
    """A session that returns the raw body of a given layer on GetFeatureInfo.

    ``path_for_layer(layer)`` returns the file path or None (empty response).
    """
    session = Mock(spec=requests.Session)

    def get(url, **kwargs):
        path = path_for_layer(_layer_of(url))
        body = path.read_text(encoding="utf-8") if path else EMPTY
        return _response(body)

    session.get = Mock(side_effect=get)
    return session


def orto_session(sheet: str) -> Mock:
    def path_for_layer(layer):
        path = REAL / "orto" / f"{sheet}_{layer}.html"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def layer_records(path: Path, layer: str):
    return parse_skorowidz_records(path.read_text(encoding="utf-8"), layer)


def file_id(url: str) -> str:
    """``78954_1462161`` from ``.../78954/78954_1462161_M-33-57-C-b-4-2.asc``."""
    return "_".join(url.rsplit("/", 1)[-1].split("_")[:2])


# =============================================================================
# WFS sheet index of NMT/NMPT: answers recorded 2026-10-15
# =============================================================================

NMT_EVRF2007 = wfs_endpoint("nmt_evrf2007")
NMT_KRON86 = wfs_endpoint("nmt_kron86")
NMT_FILES = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT"
# A valid empty answer: the service has no record at the point
EMPTY_WFS = render_wfs_body([])
WFS_TAGS = ("nmt_evrf2007", "nmt_kron86", "nmpt_evrf2007", "nmpt_kron86")
_URN_2180 = "urn:ogc:def:crs:EPSG::2180"


def recorded_sheets(tag: str) -> dict[str, str]:
    """Sheet code -> file of the recorded answers ``sheet_<tag>_<sheet>.xml``."""
    prefix = f"sheet_{tag}_"
    return {
        path.name[len(prefix) : -len(".xml")]: path.name
        for path in WFS_FIXTURES.glob(f"{prefix}*.xml")
    }


def _centre_square(sheet: str) -> tuple[float, float, float, float]:
    """Recorded query square of a sheet (N, E axes): frame centre +- 10 m."""
    frame = SheetParser(sheet).get_bbox(crs="EPSG:2180")
    east = (frame.min_x + frame.max_x) / 2
    north = (frame.min_y + frame.max_y) / 2
    return (north - 10, east - 10, north + 10, east + 10)


def recorded_wfs(
    answers: dict[tuple[str, str], str] | None = None,
    *,
    fail: tuple[str, ...] = (),
) -> Mock:
    """Session replaying the NMT/NMPT WFS answers recorded 2026-10-15.

    A GetFeature equal to the recorded query - every yearly type of the
    service, ``SRSNAME`` and ``COUNT`` of the README, ``BBOX`` = the square
    around a sheet centre - is answered with ``sheet_<tag>_<sheet>.xml``.
    ``answers`` maps ``(tag, sheet)`` to the body of a query the round did
    not record (or to an edited recording); the services of the tags in
    ``fail`` answer HTTP 503. An OpenData file answers ``b"DATA"``; any other
    request fails the test.
    """
    replies = dict(answers or {})
    tags = {wfs_endpoint(tag): tag for tag in WFS_TAGS}
    session = Mock(spec=requests.Session)

    def get(url, **kwargs):
        if url.startswith("https://opendata.geoportal.gov.pl/"):
            response = wfs_response("")
            response.iter_content = Mock(return_value=[b"DATA"])
            return response
        endpoint, _, query = url.partition("?")
        tag = tags[endpoint]
        params = {key: values[0] for key, values in parse_qs(query).items()}
        assert params["REQUEST"] == "GetFeature", url
        if tag in fail:
            return wfs_response("<html>Service Unavailable</html>", status=503)
        assert params["TYPENAMES"] == ",".join(wfs_types(tag)), url
        assert (params["SRSNAME"], params["COUNT"]) == (_URN_2180, "1000"), url
        *corners, crs = params["BBOX"].split(",")
        assert crs == _URN_2180, url
        recorded = recorded_sheets(tag)
        for sheet in {*recorded, *(code for key, code in replies if key == tag)}:
            square = _centre_square(sheet)
            if all(
                abs(float(a) - b) < 1e-6 for a, b in zip(corners, square, strict=True)
            ):
                if (tag, sheet) in replies:
                    return wfs_response(replies[tag, sheet])
                return wfs_response(wfs_fixture(recorded[sheet]))
        raise AssertionError(f"WFS query without a recorded answer: {url}")

    session.get = Mock(side_effect=get)
    return session


def sheet_records(tag: str, sheet: str) -> list[SkorowidzRecord]:
    """Parsed records of the recorded answer at the centre of ``sheet``
    (every sheet code, format and resolution the service has there)."""
    root = ET.fromstring(wfs_fixture(f"sheet_{tag}_{sheet}.xml"))
    return [
        record
        for elem in root.iter()
        if isinstance(elem.tag, str)
        and elem.tag.startswith(f"{{{GUGIK_NS}}}Skorowidz")
        and (record := parse_index_feature(elem)) is not None
    ]


def in_format(token: str) -> Callable[[SkorowidzRecord], bool]:
    """Hard filter of a variant's format: the record ``format`` AND its URL."""
    return lambda record: source_format(record.file_format, record.url) == token


# =============================================================================
# NMT/NMPT: the record of exactly the variant (plan A, ADR-041)
# =============================================================================


class TestVariantRecordOnRealWfs:
    """One answer holds every resolution, format and sheet code of the point;
    the provider takes the newest record of exactly its variant."""

    def test_select_0_5m_2025(self):
        sheet = "N-33-58-A-c-1-4"
        session = recorded_wfs()
        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="0.5m"
        )
        record = provider._resolve_sheet(sheet)
        assert file_id(record.url) == "84020_1844081"
        assert record.url.endswith(f"_{sheet}.asc")
        assert (record.layer, record.aktualnosc, record.full_sheet) == (
            "SkorowidzNMT2025",
            "2025-01-30",
            False,
        )
        source = provider.source_info(sheet)
        assert (source["index_url"], source["layer"]) == (
            NMT_EVRF2007,
            "SkorowidzNMT2025",
        )
        # one GetFeature with every yearly type of the service, no layer walk
        [query] = wfs_requests(session)
        assert query["TYPENAMES"] == ",".join(wfs_types("nmt_evrf2007"))

    def test_nmpt_0_5m(self):
        sheet = "N-33-58-A-d-1-2"
        session = recorded_wfs()
        records = {
            label: GugikNmptProvider(
                session=session, vertical_crs="EVRF2007", resolution=label
            )._resolve_sheet(sheet)
            for label in ("0.5m", "1m")
        }
        assert {label: (file_id(r.url), r.layer) for label, r in records.items()} == {
            "0.5m": ("84018_1843926", "SkorowidzNMPT2025"),
            "1m": ("76027_1185054", "SkorowidzNMPT2022"),
        }
        assert {c.args[0].split("?")[0] for c in session.get.call_args_list} == {
            wfs_endpoint("nmpt_evrf2007")
        }

    def test_kron86_0_5m_pl2000(self):
        """6.130.26.07.1.2 (PL-2000:S6, 1:500): the 0.5 m KRON86 grid of 2018."""
        sheet = "6.130.26.07.1.2"
        record = GugikProvider(
            session=recorded_wfs(), vertical_crs="KRON86", resolution="0.5m"
        )._resolve_sheet(sheet)
        assert file_id(record.url) == "70042_814868"
        assert record.url.endswith(f"_{sheet}.asc")
        assert (record.sheet, record.system, record.zone) == (sheet, "2000", 6)
        assert record.raw["ukladWspolrzednychPionowych"] == "PL-KRON86-NH"

    def test_0_15m_and_10m_pl2000(self):
        session = recorded_wfs()

        def newest(label, sheet):
            return GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution=label
            )._resolve_sheet(sheet)

        fine = newest("0.15m", "7.159.25.12.2")
        assert file_id(fine.url) == "80085_1530441"
        assert (fine.layer, fine.resolution_m, fine.system, fine.zone) == (
            "SkorowidzNMT2023",
            0.15,
            "2000",
            7,
        )
        # 6.125.25: the 5 m and 10 m grids of one delivery (2021, partial sheet)
        coarse = {label: newest(label, "6.125.25") for label in ("5m", "10m")}
        assert {label: file_id(r.url) for label, r in coarse.items()} == {
            "5m": "73929_1056345",
            "10m": "73928_1056333",
        }
        assert {(r.system, r.zone, r.full_sheet) for r in coarse.values()} == {
            ("2000", 6, False)
        }

    def test_format_filter_rejects_archives(self):
        """Review Focus 2: an archive of the same delivery never takes the
        grid's place; a grid published under a ``.xyz`` name stays a grid."""
        sheet = "M-34-64-D-d-2-1"
        records = {file_id(r.url): r for r in sheet_records("nmt_evrf2007", sheet)}
        grid, archive = records["73122_944493"], records["73123_940315"]
        # the ASCII NMT archive has the date, dt_pzgik and resolution of the 5 m
        # grid and a later URL: only the format keeps it from winning
        assert archive.file_format == "ASCII NMT"
        assert (archive.aktualnosc, archive.dt_pzgik, archive.resolution_m) == (
            grid.aktualnosc,
            grid.dt_pzgik,
            grid.resolution_m,
        )
        assert archive.url > grid.url
        session = recorded_wfs()
        found = {
            token: GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="5m", format=token
            ).resolve_campaigns(sheet, all_campaigns=True)
            for token in ("ASC", "XYZ", "ASCII-NMT")
        }
        assert {t: [file_id(r.url) for r in recs] for t, recs in found.items()} == {
            "ASC": ["73122_944493"],
            "XYZ": ["70950_853179"],
            "ASCII-NMT": ["73123_940315"],
        }
        # N-33-69-A-d-1-3: the only 1 m grid of 2019 (campaign 72675) is an
        # AAIGrid published under a `.xyz` name
        sheet = "N-33-69-A-d-1-3"
        (old,) = GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(sheet, max_year=2019)
        assert (file_id(old.url), old.url[-4:], old.aktualnosc) == (
            "72675_858106",
            ".xyz",
            "2019-04-29",
        )

    def test_campaigns_and_year_range_from_wfs(self):
        """KRON86 M-34-64-D-d-2-1: 1 m grids of 2012 and 2017, each beside an
        XYZ archive of the delivery; XYZ 1 m 2015 and TBD/TIN/TTN 2009 of the
        1:25000 sheet M-34-64-D-d-2 in the same answer."""
        sheet = "M-34-64-D-d-2-1"
        provider = GugikProvider(
            session=recorded_wfs(), vertical_crs="KRON86", resolution="1m"
        )
        every = provider.resolve_campaigns(sheet, all_campaigns=True)
        assert [(file_id(r.url), r.aktualnosc) for r in every] == [
            ("67253_783211", "2017-11-05"),
            ("4262_281430", "2012-07-06"),
        ]
        [older] = provider.resolve_campaigns(sheet, max_year=2016)
        assert file_id(older.url) == "4262_281430"
        assert provider.available_years(sheet) == (2012, 2017)


# =============================================================================
# NMT: record selection (C1b, C3, C6, C9)
# =============================================================================


class TestNmtRecordSelectionOnRealWfs:
    def test_c1b_c6_newest_campaign_wins_pl2000_records_ignored(self):
        """M-34-64-D-d-2-1: 1 m campaigns 2019 and 2022-2025 of the sheet and
        two of 7.125.11.04 (PL-2000:S7, 2021, 2023) in one answer."""
        sheet = "M-34-64-D-d-2-1"
        record = GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        )._resolve_sheet(sheet)
        assert file_id(record.url) == "83137_1729555"
        assert (record.sheet, record.system, record.aktualnosc) == (
            sheet,
            "1992",
            "2025-04-28",
        )

    def test_c3_newest_record_of_another_resolution_never_wins(self):
        """N-33-58-A-c-1-4: the newest records are 0.5 m (2025-01-30) and 5 m
        (2025-04-21); the 1 m grid has only 2022."""
        sheet = "N-33-58-A-c-1-4"
        session = recorded_wfs()
        found = {
            label: GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution=label
            )._resolve_sheet(sheet)
            for label in ("1m", "5m")
        }
        assert {
            label: (file_id(r.url), r.resolution_m) for label, r in found.items()
        } == {"1m": ("76036_1189924", 1.0), "5m": ("83830_1796314", 5.0)}

    def test_campaign_date_beats_dt_pzgik(self):
        """N-33-69-A-d-1-3 (2024): 2024-09-23 (81025) before 2024-07-21 (81616),
        although the latter has a later ``dt_pzgik`` (2025-06-20)."""
        sheet = "N-33-69-A-d-1-3"
        by_id = {file_id(r.url): r for r in sheet_records("nmt_evrf2007", sheet)}
        assert by_id["81616_1669592"].dt_pzgik > by_id["81025_1562189"].dt_pzgik
        record = GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        )._resolve_sheet(sheet)
        assert file_id(record.url) == "81025_1562189"

    def test_c9_uppercase_asc_record_is_available_but_loses_to_newer(self):
        """5 m N-33-115-C-d-2-2 (records of 2026-10-06): the ``.ASC`` grid of
        2022 is an ASC record on its own, but 2025-03-20 (``.asc``) wins."""
        sheet = "N-33-115-C-d-2-2"
        old = wfs_record(
            sheet,
            resolution="5.00 m",
            akt_data="2022-07-24",
            dt_pzgik="2023-04-04",
            czy_ark_wypelniony="NIE",
            url=f"{NMT_FILES}/76969/76969_1297751_{sheet}.ASC",
        )
        newer = [
            wfs_record(
                sheet,
                resolution="5.00 m",
                akt_data=date,
                dt_pzgik=pzgik,
                url=f"{NMT_FILES}/{url}_{sheet}.asc",
            )
            for date, pzgik, url in (
                ("2023-05-09", "2024-02-15", "78939/78939_1445968"),
                ("2025-03-20", "2026-03-20", "83841/83841_1816160"),
            )
        ]

        def newest(records):
            answer = {("nmt_evrf2007", sheet): render_wfs_body(records)}
            return GugikProvider(
                session=recorded_wfs(answer), vertical_crs="EVRF2007", resolution="5m"
            )._resolve_sheet(sheet)

        alone = newest([old])
        assert file_id(alone.url) == "76969_1297751"
        assert alone.url.endswith(".ASC")
        assert file_id(newest([old, *newer]).url) == "83841_1816160"

    def test_c9a_lowercase_sheet_in_record_is_normalised(self):
        """KRON86 N-33-59-C-a-1-3: ``godlo`` ``N-33-59-c-a-1-3`` (lower-case c,
        the record of 2026-10-06)."""
        sheet = "N-33-59-C-a-1-3"
        body = render_wfs_body(
            [
                wfs_record(
                    "N-33-59-c-a-1-3",
                    akt_data="2018-04-21",
                    dt_pzgik="2018-07-25",
                    uklad_h="PL-KRON86-NH",
                    url=f"{NMT_FILES}/67106/67106_778610_{sheet}.asc",
                )
            ]
        )
        assert "<gugik:godlo>N-33-59-c-a-1-3</gugik:godlo>" in body
        provider = GugikProvider(
            session=recorded_wfs({("nmt_kron86", sheet): body}),
            vertical_crs="KRON86",
            resolution="1m",
        )
        record = provider._resolve_sheet(sheet)
        assert file_id(record.url) == "67106_778610"
        assert record.sheet == sheet
        assert provider.source_info(sheet)["sheet"] == sheet


# =============================================================================
# NoCoverageError: hints (C6f, C6g, C10g, P10)
# =============================================================================


class TestNoCoverageHintsOnRealWfs:
    @pytest.mark.parametrize(
        ("sheet", "vertical_crs", "records", "hints"),
        [
            pytest.param(
                "6.129.30",
                "EVRF2007",
                [
                    wfs_record(
                        "M-34-63-A-c-2-1",
                        akt_data="2025-04-03",
                        dt_pzgik="2026-03-24",
                        url=f"{NMT_FILES}/83884/83884_1833346_M-34-63-A-c-2-1.asc",
                    ),
                    wfs_record(
                        "6.129.30.13.4",
                        system="PL-2000:S6",
                        akt_data="2020-05-08",
                        dt_pzgik="2020-10-28",
                        url=f"{NMT_FILES}/73736/73736_1019437_6.129.30.13.4.asc",
                    ),
                    wfs_record(
                        "6.129.30.13.4",
                        resolution="0.50 m",
                        system="PL-2000:S6",
                        akt_data="2023-07-05",
                        dt_pzgik="2024-06-07",
                        url=f"{NMT_FILES}/79108/79108_1494890_6.129.30.13.4.asc",
                    ),
                ],
                (
                    "Available descendant 6.129.30.13.4 - use --scale 1:1000",
                    (
                        "The sheet index has this area in PL-1992: M-34-63-A-c-2-1 "
                        "(1:10000) - use this sheet code or --sheet-system 1992"
                    ),
                ),
                id="c6f-1_10000",
            ),
            pytest.param(
                "5.167.25",
                "KRON86",
                [
                    wfs_record(
                        "M-33-8-A-a-3-1",
                        akt_data="2011-07-26",
                        dt_pzgik="2012-07-30",
                        uklad_h="PL-KRON86-NH",
                        url=f"{NMT_FILES}/4148/4148_105823_M-33-8-A-a-3-1.asc",
                    ),
                    wfs_record(
                        "5.167.25.13",
                        system="PL-2000:S5",
                        akt_data="2019-06-03",
                        dt_pzgik="2019-11-14",
                        uklad_h="PL-KRON86-NH",
                        url=f"{NMT_FILES}/72980/72980_898837_5.167.25.13.asc",
                    ),
                ],
                (
                    "Available descendant 5.167.25.13 - use --scale 1:2000",
                    (
                        "The sheet index has this area in PL-1992: M-33-8-A-a-3-1 "
                        "(1:10000) - use this sheet code or --sheet-system 1992"
                    ),
                ),
                id="c6g-kron86",
            ),
        ],
    )
    def test_c6f_c6g_pl2000_hints_descendant_scale_and_pl1992_sheet(
        self, sheet, vertical_crs, records, hints
    ):
        """Records of 2026-10-06 at the centre of a PL-2000 1:10000 sheet: a
        descendant sheet and the PL-1992 sheet, none of the sheet itself."""
        own, other = (
            ("nmt_evrf2007", "nmt_kron86")
            if vertical_crs == "EVRF2007"
            else ("nmt_kron86", "nmt_evrf2007")
        )
        session = recorded_wfs(
            {(own, sheet): render_wfs_body(records), (other, sheet): EMPTY_WFS}
        )
        with pytest.raises(NoCoverageError) as exc:
            GugikProvider(
                session=session, vertical_crs=vertical_crs, resolution="1m"
            )._resolve_sheet(sheet)
        assert exc.value.hints == hints
        assert exc.value.sheet == sheet
        # every year of the height system in one query
        assert len(wfs_requests(session, wfs_endpoint(own))) == 1

    def test_no_coverage_hints_other_resolution_without_network(self):
        """N-33-58-A-c-1-3 has only 0.5 m grids (2021, 2022, 2025)."""
        sheet = "N-33-58-A-c-1-3"
        session = recorded_wfs({("nmt_kron86", sheet): EMPTY_WFS})
        with pytest.raises(NoCoverageError) as exc:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._resolve_sheet(sheet)
        assert str(exc.value) == (
            "No NMT 1m data for N-33-58-A-c-1-3 (PL-1992 system, EVRF2007). The "
            "GUGiK sheet index has this sheet in NMT 0.5m EVRF2007 - use "
            "--resolution 0.5m"
        )
        # the hint comes from the answer itself, not from a second query
        assert len(wfs_requests(session, NMT_EVRF2007)) == 1

    def test_c10g_nmpt_hints_its_resolutions_from_nmpt_services_only(self):
        """NMPT N-33-77-B-c-3-3: 0.5 m (2022, 2024) and 0.6 m (2024), no 1 m."""
        sheet = "N-33-77-B-c-3-3"
        session = recorded_wfs({("nmpt_kron86", sheet): EMPTY_WFS})
        with pytest.raises(NoCoverageError) as exc:
            GugikNmptProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._resolve_sheet(sheet)
        assert exc.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMPT 0.5m EVRF2007 - use "
                "--resolution 0.5m"
            ),
            (
                "The GUGiK sheet index has this sheet in NMPT 0.6m EVRF2007 - use "
                "--resolution 0.6m"
            ),
        )
        # its own service and, for P10, the other height system - never NMT
        assert [c.args[0].split("?")[0] for c in session.get.call_args_list] == [
            wfs_endpoint("nmpt_evrf2007"),
            wfs_endpoint("nmpt_kron86"),
        ]

    def test_archive_only_sheet_hint(self):
        """KRON86 N-34-58-D-c-3 (1:25000): its only 1 m record is the XYZ
        archive of 2016; TBD/TIN/TTN archives of 2000 and 2010 beside it."""
        sheet = "N-34-58-D-c-3"
        session = recorded_wfs({("nmt_evrf2007", sheet): EMPTY_WFS})
        with pytest.raises(NoCoverageError) as exc:
            GugikProvider(
                session=session, vertical_crs="KRON86", resolution="1m"
            )._resolve_sheet(sheet)
        assert exc.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMT TBD 25m KRON86 - use "
                "--format TBD --resolution 25m"
            ),
            (
                "The GUGiK sheet index has this sheet in NMT TBD 30m KRON86 - use "
                "--format TBD --resolution 30m"
            ),
            "The GUGiK sheet index has this sheet in NMT TIN KRON86 - use --format TIN",
            "The GUGiK sheet index has this sheet in NMT TTN KRON86 - use --format TTN",
            (
                "The GUGiK sheet index has this sheet in NMT XYZ 1m KRON86 - use "
                "--format XYZ"
            ),
        )
        assert all(sheet not in hint for hint in exc.value.hints)


class TestVariantHintOnRealWfs:
    """P10: no record of the variant -> hints naming the variants of the
    sheet: other resolutions from the same answer without network, the other
    height system by one query to its service (both recorded here)."""

    SHEET = "N-33-58-A-c-1-4"
    EVRF2007_HINTS = (
        (
            "The GUGiK sheet index has this sheet in NMT 0.5m EVRF2007 - use "
            "--resolution 0.5m"
        ),
        "The GUGiK sheet index has this sheet in NMT 1m EVRF2007 - use --resolution 1m",
        "The GUGiK sheet index has this sheet in NMT 5m EVRF2007 - use --resolution 5m",
    )
    KRON86_HINT = (
        "The GUGiK sheet index has this sheet in NMT 1m KRON86 - use --resolution 1m "
        "--vertical-crs KRON86"
    )

    def provider(self, session, **kwargs):
        return GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="0.6m", **kwargs
        )

    def test_variant_hints_for_0_6m_gap(self):
        session = recorded_wfs()
        with pytest.raises(NoCoverageError) as exc:
            self.provider(session)._resolve_sheet(self.SHEET)
        assert set(exc.value.hints) == {*self.EVRF2007_HINTS, self.KRON86_HINT}
        # one query per service: its own and the other height system
        assert len(wfs_requests(session, NMT_EVRF2007)) == 1
        assert len(wfs_requests(session, NMT_KRON86)) == 1

    def test_variant_with_other_sheet_gives_no_hint(self):
        """The KRON86 records at the point belong to another sheet code."""
        body = wfs_fixture(f"sheet_nmt_kron86_{self.SHEET}.xml")
        other = body.replace(self.SHEET, "N-33-58-A-c-1-2")
        assert other != body
        session = recorded_wfs({("nmt_kron86", self.SHEET): other})
        with pytest.raises(NoCoverageError) as exc:
            self.provider(session)._resolve_sheet(self.SHEET)
        assert exc.value.hints == self.EVRF2007_HINTS

    def test_no_coverage_hint_other_vertical_crs_one_query(self, caplog):
        """Review: an outage of the other service costs ONE attempt per
        provider (no retries, not one per sheet) and leaves no coverage."""
        session = recorded_wfs(fail=("nmt_kron86",))
        provider = self.provider(session)
        caught = []
        for sheet in (self.SHEET, "N-33-58-A-c-1-3"):
            with pytest.raises(NoCoverageError) as exc:
                provider._resolve_sheet(sheet)
            caught.append(exc.value.hints)
        assert caught == [
            self.EVRF2007_HINTS,
            (
                (
                    "The GUGiK sheet index has this sheet in NMT 0.5m EVRF2007 - use "
                    "--resolution 0.5m"
                ),
            ),
        ]
        assert len(wfs_requests(session, NMT_KRON86)) == 1
        assert len(wfs_requests(session, NMT_EVRF2007)) == 2
        assert any(
            r.levelname == "WARNING"
            and "vertical CRS KRON86 was not checked" in r.getMessage()
            for r in caplog.records
        )

    def test_variant_hint_cached_with_no_coverage(self, tmp_path):
        cache = MetadataCache(tmp_path / "c.db")
        with pytest.raises(NoCoverageError) as first:
            self.provider(recorded_wfs(), cache=cache)._resolve_sheet(self.SHEET)
        again = Mock(spec=requests.Session)
        with pytest.raises(NoCoverageError) as second:
            self.provider(again, cache=cache)._resolve_sheet(self.SHEET)
        again.get.assert_not_called()
        assert second.value.hints == first.value.hints
        assert self.KRON86_HINT in second.value.hints


# =============================================================================
# Ortho: RGB/CIR, sheet code token, partial sheet (C12)
# =============================================================================


class TestOrtoRecordSelectionOnRealBodies:
    SHEET = "N-34-139-A-c-1-1"

    def test_c12_cir_comes_from_2024_when_newer_layer_has_only_rgb(self):
        provider = GugikOrtoProvider(session=orto_session(self.SHEET), color="CIR")
        record = provider._resolve_sheet(self.SHEET)
        assert file_id(record.url) == "81434_1416956"
        assert record.layer == "SkorowidzeOrtofotomapy2024"
        assert record.resolution_m == 0.25
        assert provider.source_info(self.SHEET)["color"] == "CIR"

    def test_c12_rgb_comes_from_2025_at_5_cm(self):
        provider = GugikOrtoProvider(session=orto_session(self.SHEET), color="RGB")
        record = provider._resolve_sheet(self.SHEET)
        assert file_id(record.url) == "83235_1485417"
        assert record.layer == "SkorowidzeOrtofotomapy2025"
        assert record.resolution_m == 0.05
        assert provider.source_info(self.SHEET)["color"] == "RGB"

    def test_c12_token_parent_request_never_takes_child_records(self):
        """M-34-90-C-b-4 (parent sheet) -> its own 0.75 m record from 1997,
        not the newer records of the child M-34-90-C-b-4-4."""
        records = layer_records(
            REAL / "orto" / "M-34-90-C-b-4-4_SkorowidzeOrtofotomapyStarsze.html",
            "SkorowidzeOrtofotomapyStarsze",
        )
        parent = select_sheet_record(
            records,
            sheet="M-34-90-C-b-4",
            system="1992",
            predicate=lambda r: r.raw.get("kolor") == "RGB",
        )
        assert file_id(parent.url) == "77300_1184641"
        assert parent.sheet == "M-34-90-C-b-4"

    def test_c12_token_child_request_never_takes_parent_record(self):
        """From the records of the parent M-34-90-C-b-4 alone, the request
        M-34-90-C-b-4-4 selects nothing (the sheet code is a whole token, not a
        prefix)."""
        records = layer_records(
            REAL / "orto" / "M-34-90-C-b-4-4_SkorowidzeOrtofotomapyStarsze.html",
            "SkorowidzeOrtofotomapyStarsze",
        )
        parents = [r for r in records if r.sheet == "M-34-90-C-b-4"]
        assert parents  # the parent is in the raw body
        assert (
            select_sheet_record(parents, sheet="M-34-90-C-b-4-4", system="1992") is None
        )
        # and the sheet's own real record beats the newest: 2022-06-26 RGB (76530)
        child = select_sheet_record(
            records,
            sheet="M-34-90-C-b-4-4",
            system="1992",
            predicate=lambda r: r.raw.get("kolor") == "RGB",
        )
        assert file_id(child.url) == "76530_1090199"
        assert child.sheet == "M-34-90-C-b-4-4"

    def test_c12_record_with_full_sheet_false_wins_adr_028(self):
        """M-34-90-C-b-4-4: 2026 (partial sheet) before the full 2024 - no
        preference for the ``calyArkuszWypelnionyTrescia`` flag."""
        sheet = "M-34-90-C-b-4-4"
        provider = GugikOrtoProvider(session=orto_session(sheet), color="RGB")
        record = provider._resolve_sheet(sheet)
        assert file_id(record.url) == "84466_1602825"
        assert record.full_sheet is False
        assert record.layer == "SkorowidzeOrtofotomapy2026"
        assert provider.source_info(sheet)["full_sheet"] is False

    def test_c12_pl2000_sheet_takes_own_record_not_descendants(self):
        """7.173.21.01: record 2021-04-28 (75063), descendants 7.173.21.01.x
        from 2022 are ignored (the sheet code is a whole token)."""
        sheet = "7.173.21.01"
        provider = GugikOrtoProvider(session=orto_session(sheet), color="RGB")
        record = provider._resolve_sheet(sheet)
        assert file_id(record.url) == "75063_1038529"
        assert record.sheet == sheet
        assert (record.system, record.zone) == ("2000", 7)


# =============================================================================
# Cutout: sheets from different campaigns (C14)
# =============================================================================


class TestCutoutSheetsFromDifferentCampaigns:
    """One provider (a cutout over several sheets) gives every sheet the
    newest 1 m record of its own: campaigns differ from sheet to sheet."""

    EXPECTED = {
        "N-33-77-B-c-3-3": ("80196_1534047", "SkorowidzNMT2024"),
        "N-33-77-D-a-1-2": ("80196_1534063", "SkorowidzNMT2024"),
        "M-34-29-A-b-4-2": ("83852_1826359", "SkorowidzNMT2025"),
        "N-34-121-C-b-3-3": ("81136_1575486", "SkorowidzNMT2024"),
    }

    def test_c14_each_sheet_gets_its_own_newest_campaign(self):
        provider = GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        )
        records = {sheet: provider._resolve_sheet(sheet) for sheet in self.EXPECTED}
        assert {
            sheet: (file_id(r.url), r.layer) for sheet, r in records.items()
        } == self.EXPECTED
        assert {sheet: provider.source_info(sheet)["url"] for sheet in records} == {
            sheet: r.url for sheet, r in records.items()
        }


# =============================================================================
# LAZ: WFS on raw XML (C13)
# =============================================================================

W2_BBOX = BBox(637200, 486900, 637500, 487100, "EPSG:2180")
# 50 x 50 m at the centre of 6.150.13.16.4 (Wroclaw, two NIE deliveries in 2025)
WRO_BBOX = BBox(367331, 369020, 367381, 369070, "EPSG:2180")
# 300 x 300 m on two PL-1992 sheets: one with 2023/2025, the other only 2019
W3_BBOX = BBox(627706, 479258, 628006, 479558, "EPSG:2180")
# query window (axes N,E) each recorded area answers
_LAZ_WINDOWS = {
    "w2": "486900,637200,487100,637500,",
    "wro": "369020,367331,369070,367381,",
    "w3": "479258,627706,479558,628006,",
}


def laz_session(area: str = "w2") -> MagicMock:
    """WFS: GetCapabilities and GetFeature from raw XML recorded for ``area``."""
    session = MagicMock()

    def get(url, **kwargs):
        query = parse_qs(urlparse(url).query)
        vcrs = "KRON86" if "LidarKRON86" in url else "EVRF2007"
        if query["REQUEST"][0] == "GetCapabilities":
            path = REAL_LAZ / f"caps_{vcrs}.xml"
        else:
            assert query["BBOX"][0].startswith(_LAZ_WINDOWS[area])
            year = query["TYPENAMES"][0][-4:]
            path = REAL_LAZ / f"{area}_{vcrs}_{year}.xml"
        response = MagicMock()
        response.text = path.read_text(encoding="utf-8")
        response.raise_for_status = MagicMock()
        return response

    session.get = MagicMock(side_effect=get)
    return session


def feature_years(session: MagicMock) -> list[str]:
    return [
        parse_qs(urlparse(call.args[0]).query)["TYPENAMES"][0][-4:]
        for call in session.get.call_args_list
        if "GetFeature" in call.args[0]
    ]


class TestLazDiscoveryOnRealWfs:
    def test_c13_evrf2007_newest_tile_covers_both_systems(self):
        """L1: two CRS in the area, but 2025/PL-1992 covers it entirely.

        Until 2026-10-06 the result also had the 2022 PL-2000:S7 tiles (dedup by
        sheet code only) - a duplicated area (C13 NOTE 1).
        """
        selection = GugikLazProvider(
            session=laz_session(), vertical_crs="EVRF2007"
        ).select_tiles(W2_BBOX)
        tiles = selection.tiles
        assert [(t.sheet, t.year, t.crs) for t in tiles] == [
            ("N-34-139-A-c-1-1-3-4", 2025, "PL-1992"),
        ]
        assert [t.system for t in tiles] == ["1992"]
        assert [t.density for t in tiles] == [12]
        assert tiles[0].url.endswith("83230_1743191_N-34-139-A-c-1-1-3-4.laz")
        assert sorted(
            (s.tile.sheet, s.tile.year, s.tile.crs) for s in selection.superseded
        ) == [
            ("7.173.21.06.1", 2022, "PL-2000:S7"),
            ("7.173.21.06.2", 2022, "PL-2000:S7"),
            ("N-34-139-A-c-1-1-3-4", 2023, "PL-1992"),
        ]
        # the second horizontal CRS is still recognised (pl_2000 segment)
        assert [s.tile.system for s in selection.superseded if s.tile.year == 2022] == [
            "2000",
            "2000",
        ]

    def test_laz_year_2023_w2_covers_reference(self):
        session = laz_session()
        tiles = GugikLazProvider(
            session=session, vertical_crs="EVRF2007"
        ).discover_tiles(W2_BBOX, year=2023)
        assert [(t.sheet, t.year) for t in tiles] == [("N-34-139-A-c-1-1-3-4", 2023)]
        assert file_id(tiles[0].url) == "78044_1403296"
        assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]

    def test_laz_year_2022_two_tiles_together_cover_w2_reference(self):
        """P8: no single 2022 tile covers W2_BBOX, their union does - no conflict."""
        session = laz_session()
        selection = GugikLazProvider(
            session=session, vertical_crs="EVRF2007"
        ).select_tiles(W2_BBOX, year=2022)
        assert [(t.sheet, t.year, t.crs) for t in selection.tiles] == [
            ("7.173.21.06.1", 2022, "PL-2000:S7"),
            ("7.173.21.06.2", 2022, "PL-2000:S7"),
        ]
        assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]

    def test_laz_year_2024_w2_conflict_lists_years(self, tmp_path):
        session = laz_session()
        provider = GugikLazProvider(session=session, vertical_crs="EVRF2007")
        provider.download_tile = MagicMock()  # type: ignore[method-assign]
        with pytest.raises(YearRangeError) as caught:
            download_laz_area(
                bbox=W2_BBOX,
                root=tmp_path,
                provider=provider,
                year=2024,
                vertical_crs="EVRF2007",
            )
        err = caught.value
        assert err.sheets == {"N-34-139-A-c-1-1-3-4": (2022, 2023, 2025)}
        assert "brak LAZ tiles z roku 2024 dla 1 z 1 area tiles" in str(err)
        assert "N-34-139-A-c-1-1-3-4 (2025, PL-1992)" in str(err)
        assert "--min-year 2024" in str(err)
        assert "--max-year 2024" in str(err)
        assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]
        provider.download_tile.assert_not_called()
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        ("bounds", "message"),
        [
            ({"min_year": 2010, "max_year": 2017}, "range 2010-2017 has no vintage"),
            ({"year": 2017}, "vintage 2017 does not exist"),
            ({"min_year": 2017, "max_year": 2017}, "vintage 2017 does not exist"),
        ],
    )
    def test_laz_range_without_service_year(self, bounds, message):
        session = laz_session()
        with pytest.raises(DownloadError, match=f"{message} in service EVRF2007"):
            GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
                W2_BBOX, **bounds
            )
        assert feature_years(session) == []

    def test_c13_min_density_13_drops_the_12_p_m2_tile(self):
        tiles = GugikLazProvider(
            session=laz_session(), vertical_crs="EVRF2007"
        ).discover_tiles(W2_BBOX, min_density=13)
        assert [(t.sheet, t.crs) for t in tiles] == [
            ("7.173.21.06.1", "PL-2000:S7"),
            ("7.173.21.06.2", "PL-2000:S7"),
        ]

    def test_c13_kron86_returns_2018_tile_not_2012(self):
        session = laz_session()
        provider = GugikLazProvider(session=session, vertical_crs="KRON86")
        tiles = provider.discover_tiles(W2_BBOX)
        assert [(t.sheet, t.year) for t in tiles] == [("N-34-139-A-c-1-1-3-4", 2018)]
        assert file_id(tiles[0].url) == "70707_846000"
        # vintage 2012 was in the service and was queried
        assert "2012" in feature_years(session)

    def test_c13_las_format_in_wfs_still_yields_dot_laz_filename(self):
        raw = (REAL_LAZ / "w2_KRON86_2018.xml").read_text(encoding="utf-8")
        assert "<gugik:format>LAS</gugik:format>" in raw  # raw body
        tile = GugikLazProvider(
            session=laz_session(), vertical_crs="KRON86"
        ).discover_tiles(W2_BBOX)[0]
        assert tile.filename == "70707_846000_N-34-139-A-c-1-1-3-4.laz"
        assert tile.filename.endswith(".laz")

    @pytest.mark.parametrize("bounds", [{}, {"max_year": 2025}])
    def test_wroclaw_two_nie_deliveries_of_one_sheet_both_kept(self, bounds):
        """T25 / ADR-029: a NIE frame covers nothing, so both 2025 deliveries stay.

        The PL-1992 2024 tile stays too: no full-sheet tile covers its area.
        """
        selection = GugikLazProvider(
            session=laz_session("wro"), vertical_crs="EVRF2007"
        ).select_tiles(WRO_BBOX, **bounds)
        assert [
            (t.sheet, t.year, t.full_sheet, file_id(t.url)) for t in selection.tiles
        ] == [
            ("6.150.13.16.4", 2025, False, "84048_1847378"),
            ("6.150.13.16.4", 2025, False, "84169_1850670"),
            ("M-33-35-A-c-4-4-3-2", 2024, True, "79805_1509323"),
        ]

    def test_wroclaw_year_2025_conflict_on_one_of_three_reference_tiles(self):
        """P8: 2025 has only NIE tiles here, so the 2024 reference stays uncovered."""
        session = laz_session("wro")
        with pytest.raises(YearRangeError) as caught:
            GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
                WRO_BBOX, year=2025
            )
        err = caught.value
        assert err.sheets == {"M-33-35-A-c-4-4-3-2": (2019, 2022, 2024, 2025)}
        assert (
            "M-33-35-A-c-4-4-3-2 (2024, PL-1992): dostepne roczniki "
            "2019, 2022, 2024, 2025 (tylko arkusze niepelne)"
        ) in str(err)
        assert "area tiles" in str(err)
        assert "--max-year 2025" in str(err)
        assert "--min-year" not in str(err)
        assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]

    @pytest.mark.parametrize(
        ("year", "sheet", "years", "hint", "no_hint"),
        [
            (
                2019,
                "N-34-138-B-c-4-4-4-4",
                (2023, 2025),
                "--min-year 2019",
                "--max-year",
            ),
            (2025, "N-34-138-D-a-2-2-2", (2019,), "--max-year 2025", "--min-year"),
        ],
    )
    def test_w3_year_conflict_on_one_of_two_reference_tiles(
        self, year, sheet, years, hint, no_hint
    ):
        """T22 on two reference tiles: only the tile without ``year`` is listed."""
        session = laz_session("w3")
        with pytest.raises(YearRangeError) as caught:
            GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
                W3_BBOX, year=year
            )
        err = caught.value
        assert err.sheets == {sheet: years}
        assert f"z roku {year} dla 1 z 2 area tiles" in str(err)
        assert hint in str(err)
        assert no_hint not in str(err)
        assert "niepelne" not in str(err)  # every tile here is a full sheet

    def test_discover_tiles_forwards_min_year(self):
        """``discover_tiles(min_year=)`` = ``select_tiles(min_year=).tiles``."""
        with pytest.raises(YearRangeError) as caught:
            GugikLazProvider(
                session=laz_session("w3"), vertical_crs="EVRF2007"
            ).discover_tiles(W3_BBOX, min_year=2023)
        assert caught.value.sheets == {"N-34-138-D-a-2-2-2": (2019,)}
        tiles = GugikLazProvider(
            session=laz_session("w3"), vertical_crs="EVRF2007"
        ).discover_tiles(W3_BBOX, min_year=2019, max_year=2023)
        assert [(t.sheet, t.year) for t in tiles] == [
            ("N-34-138-B-c-4-4-4-4", 2023),
            ("N-34-138-D-a-2-2-2", 2019),
        ]

    def test_w3_older_tile_adding_uncovered_area_is_kept(self):
        """ADR-029: no newer tile covers the 2019 sheet, so 2019 stays beside 2025."""
        selection = GugikLazProvider(
            session=laz_session("w3"), vertical_crs="EVRF2007"
        ).select_tiles(W3_BBOX)
        assert [(t.sheet, t.year) for t in selection.tiles] == [
            ("N-34-138-B-c-4-4-4-4", 2025),
            ("N-34-138-D-a-2-2-2", 2019),
        ]
        assert [
            (s.tile.sheet, s.tile.year, s.reason) for s in selection.superseded
        ] == [("N-34-138-B-c-4-4-4-4", 2023, "covered")]


# =============================================================================
# ADR-030: campaign list (select_campaign_records) on real answers
# =============================================================================


def _orto_records(sheet):
    return [
        r
        for f in sorted((REAL / "orto").glob(f"{sheet}_*.html"))
        for r in layer_records(f, f.stem.split("_", 1)[1])
    ]


def _is_rgb(record):
    return record.raw.get("kolor") == "RGB"


def _is_cir(record):
    return record.raw.get("kolor") == "CIR"


def _sheet_args(sheet):
    parser = SheetParser(sheet)
    zone = int(sheet.split(".")[0]) if parser.sheet_system == "2000" else None
    return {"sheet": sheet, "system": parser.sheet_system, "zone": zone}


def _real_cases() -> list[tuple[str, list[SkorowidzRecord], dict]]:
    """(sheet code, records, filter) for every real answer: each recorded WFS
    sheet answer with every registered variant of its product and height
    system, each orthophoto body with RGB and CIR."""
    cases: list[tuple[str, list[SkorowidzRecord], dict]] = []
    for tag in WFS_TAGS:
        product, vertical_crs = tag.split("_")
        found = variants(
            product=product, country="PL", vertical_crs=vertical_crs.upper()
        )
        for sheet in sorted(recorded_sheets(tag)):
            records = sheet_records(tag, sheet)
            for variant in found:
                resolution = variant.resolution_m
                wanted = {
                    "resolution_m": None if resolution is None else float(resolution),
                    "predicate": in_format(variant.format),
                    "require_resolution": resolution is not None,
                }
                cases.append((sheet, records, wanted))
    for sheet in sorted(
        {f.name.rsplit("_Skorowidze", 1)[0] for f in (REAL / "orto").glob("*.html")}
    ):
        for pred in (_is_rgb, _is_cir):
            cases.append((sheet, _orto_records(sheet), {"predicate": pred}))
    return cases


class TestCampaignListsOnRealBodies:
    def test_campaign_list_of_each_sheet_code_in_one_answer(self):
        """M-34-64-D-d-2-1: the answer also holds 7.125.11.04 (PL-2000:S7,
        1 m 2021 and 2023) - each sheet code gets its own campaigns."""
        records = sheet_records("nmt_evrf2007", "M-34-64-D-d-2-1")
        grid = {"resolution_m": 1.0, "predicate": in_format("ASC")}
        pl1992 = select_campaign_records(
            records, sheet="M-34-64-D-d-2-1", system="1992", **grid
        )
        assert [file_id(r.url) for r in pl1992] == [
            "83137_1729555",
            "81428_1632968",
            "78992_1476934",
            "76531_1216448",
            "73228_990051",
        ]
        pl2000 = select_campaign_records(
            records, sheet="7.125.11.04", system="2000", zone=7, **grid
        )
        assert [file_id(r.url) for r in pl2000] == ["77912_1385041", "75172_1140019"]
        assert (
            select_campaign_records(
                records, sheet="7.125.11.04", system="2000", zone=6, **grid
            )
            == []
        )

    def test_select_sheet_record_equals_head_of_campaign_list_on_every_answer(self):
        selected = 0
        for sheet, records, wanted in _real_cases():
            args = {**_sheet_args(sheet), **wanted}
            single = select_sheet_record(records, **args)
            listed = select_campaign_records(records, **args)
            assert single == (listed or [None])[0], (sheet, wanted)
            selected += single is not None
        # most cases select a record: the comparison is not vacuous
        assert selected >= 50

    def test_orto_all_rgb_m34_90_c_b_4_4_excludes_cir_and_parent_sheet(self):
        sheet = "M-34-90-C-b-4-4"
        recs = select_campaign_records(
            _orto_records(sheet), predicate=_is_rgb, **_sheet_args(sheet)
        )
        assert [file_id(r.url).split("_")[0] for r in recs] == [
            "84466",
            "81437",
            "76530",
            "73121",
            "70500",
            "69792",
            "75",
        ]

    def test_duplicate_url_across_layers_listed_once(self):
        """A record repeated in the answers of two layers is one campaign."""
        sheet = "M-34-90-C-b-4-4"
        body = REAL / "orto" / f"{sheet}_SkorowidzeOrtofotomapy2026.html"
        twice = layer_records(body, "SkorowidzeOrtofotomapy2026") + layer_records(
            body, "SkorowidzeOrtofotomapy2025"
        )
        recs = select_campaign_records(twice, predicate=_is_rgb, **_sheet_args(sheet))
        assert [file_id(r.url) for r in recs] == ["84466_1602825"]

    def test_record_format_survives_cache_roundtrip(self):
        """The record ``format`` decides the variant of a cached record too:
        an XYZ archive stays XYZ, the ``.xyz`` name of a 72675 grid stays ASC."""
        sheet = "N-33-69-A-d-1-3"
        records = {file_id(r.url): r for r in sheet_records("nmt_evrf2007", sheet)}
        for key, token in (("73843_1035648", "XYZ"), ("72675_858106", "ASC")):
            back = SkorowidzRecord.from_source(records[key].to_source(NMT_EVRF2007))
            assert back.file_format == records[key].file_format
            assert source_format(back.file_format, back.url) == token

    def test_orto_record_has_no_format_and_roundtrip_keeps_none(self):
        recs = _orto_records("M-34-90-C-b-4-4")
        assert recs
        for r in recs:
            assert r.file_format is None
            back = SkorowidzRecord.from_source(r.to_source("https://wms"))
            assert back.file_format is None
            assert "format" not in back.raw


# =============================================================================
# Declared vertical datum of the record vs the queried index (0.7.1, E5)
# =============================================================================


class TestDeclaredVerticalCrsOnRealWfs:
    """``GugikProvider.download`` (path without the manager) checks the record."""

    SHEET = "N-33-58-A-c-1-4"  # KRON86 answer: records PL-KRON86-NH

    def test_kron86_record_from_evrf2007_index_is_not_downloaded(self, tmp_path):
        """E5: the EVRF2007 service answers with KRON86 records -> DownloadError."""
        kron86 = wfs_fixture(f"sheet_nmt_kron86_{self.SHEET}.xml")
        provider = GugikProvider(
            session=recorded_wfs({("nmt_evrf2007", self.SHEET): kron86}),
            vertical_crs="EVRF2007",
            resolution="1m",
        )
        provider.download_record = Mock()
        with pytest.raises(DownloadError) as exc:
            provider.download(self.SHEET, tmp_path / "a.asc")
        message = str(exc.value)
        assert "deklaruje uklad wysokosci PL-KRON86-NH" in message
        assert "zadano EVRF2007" in message
        assert self.SHEET in message
        provider.download_record.assert_not_called()

    def test_kron86_record_from_kron86_index_is_downloaded(self, tmp_path):
        provider = GugikProvider(
            session=recorded_wfs(), vertical_crs="KRON86", resolution="1m"
        )
        provider.download_record = Mock(return_value=tmp_path / "a.asc")
        provider.download(self.SHEET, tmp_path / "a.asc")
        record = provider.download_record.call_args.args[0]
        assert file_id(record.url) == "3646_66649"
        assert record.raw["ukladWspolrzednychPionowych"] == "PL-KRON86-NH"
