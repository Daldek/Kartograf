"""GUGiK archives downloaded as source files (ADR-041, plan A decision 13).

Index formats other than the ASC grid (``--format XYZ``, ``ASCII-NMT``,
``TBD``, ``TIN``, ``TTN``, ``GRD``, ``DXF``, ``DGN``) are variants of the
registry downloaded 1:1: the original file with its sidecar, versions in the
store, no conversion, cutout, mosaic or coverage measurement. Archives lie
on sheets of several scales (1:25000 and 1:10000 frames, PL-2000 sheets), so
the sheets of a request are the variant's records of the WFS index that
overlap the request area (``GugikProvider.index_sheets``). File signatures
and archive names (B4) are tested in ``tests/unit/test_campaigns.py``.

WFS answers: the recorded NMT KRON86 index around the centres of 1:25000
sheets (``sheet_nmt_kron86_<sheet>.xml`` of
``tests/fixtures/gugik_wfs/real_2026_10_15/``; ``N-34-58-D-c-3``: TBD 25 m
2010, TBD 30 m, TIN and TTN 2000 of the sheet, XYZ and ASC 1 m of its
1:10000 sheets) and ``wfs_record`` answers on the frames of real sheets.
File bodies: a small ZIP and the real file heads of
``tests/fixtures/gugik_archives/``.
"""

import io
import json
import logging
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.core.bbox import BBox
from kartograf.core.coverage import Polygon, rectangle
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.data import DataReport, UnitFailure, check_data, download_data
from kartograf.download.manager import DownloadManager
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import SHEET_LIST, Notice
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.skorowidz_wfs import sheet_frame_2180
from kartograf.sources.variants import UNKNOWN_VERTICAL, variants
from tests.conftest import (
    render_wfs_body,
    wfs_fixture,
    wfs_record,
    wfs_requests,
    wfs_response,
)
from tests.support.parity import assert_same_store, run_both

SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"
OPENDATA = "https://opendata.geoportal.gov.pl/"
HEADS = Path(__file__).parent.parent / "fixtures" / "gugik_archives"

SHEET = "N-34-58-D-c-3"  # 1:25000 frame of the KRON86 archives
RECORDED = "sheet_nmt_kron86_N-34-58-D-c-3.xml"
# The TBD 25 m record of SHEET in the recorded answer (SkorowidzNMT2010)
TBD_URL = f"{OPENDATA}NumDaneWys/NMT/5143/5143_316733_N-34-58-D-c-3_asc.zip"
TBD_25M = {"format": "TBD", "resolution": "25m", "vertical_crs": "KRON86"}
TBD_25M_ARGV = ["--format", "TBD", "--resolution", "25m", "--vertical-crs", "KRON86"]
STANDARD = Path("nmt/pl_1992_tbd_25m_kron86/N-34/58/D/c/3/N-34-58-D-c-3.zip")
SHEET_LISTED = (
    "Sheets found in the GUGiK sheet index: 1 for {what} (format: TBD, "
    "resolution: 25m)\n  Sheets: N-34-58-D-c-3"
)
# 500 x 200 m across the east edge of SHEET (about 240 m on each side)
ACROSS_EAST_EDGE = BBox(747400, 727600, 747900, 727800, "EPSG:2180")

# URL endings of the GUGiK formats (full WFS inventory 2026-10-15)
_FILE_ENDING = {
    "ASCII TBD": "_asc.zip",
    "ESRI TIN": "_tin.zip",
    "Intergraph TTN": ".ttn",
    "ASCII XYZ GRID": ".xyz.zip",
    "ARC/INFO ASCII GRID": ".asc",
}


def _archive_bytes() -> bytes:
    """A small complete ZIP shaped like a GUGiK TBD archive (text members)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{SHEET}_GR.txt", "727700.00 745610.00 98.40\r\n" * 20)
        archive.writestr(f"{SHEET}_C.txt", "")
    return buffer.getvalue()


ARCHIVE = _archive_bytes()


def _head(name: str) -> bytes:
    """Real first 512 B of the GUGiK file ``name`` (``gugik_archives``)."""
    stem, ext = name.rsplit(".", 1)
    return (HEADS / f"{stem}.head.{ext}").read_bytes()


def _record(
    sheet: str,
    *,
    akt_data: str = "2010-10-09",
    resolution: str | None = "25.0 m",
    fmt: str = "ASCII TBD",
    system: str = "PL-1992",
    **fields: str,
) -> dict:
    """KRON86 index record on the frame of ``sheet`` (TBD 25 m by default);
    ``fields`` override record keys (``layer``, ``czy_ark_wypelniony``)."""
    record = wfs_record(
        sheet,
        resolution=resolution,
        system=system,
        akt_data=akt_data,
        url=f"{OPENDATA}NumDaneWys/NMT/5143/5143_1_{sheet}{_FILE_ENDING[fmt]}",
        footprint=list(sheet_frame_2180(sheet)),
        format=fmt,
        uklad_h="PL-KRON86-NH",
    )
    record.update(fields)
    return record


def _centre_box(sheet: str, half: float) -> BBox:
    """EPSG:2180 square of side ``2 * half`` at the centre of the sheet frame
    (``half=10``: the query area of the recorded ``sheet_*`` answers)."""
    frame = SheetParser(sheet).get_bbox(crs="EPSG:2180")
    x, y = (frame.min_x + frame.max_x) / 2, (frame.min_y + frame.max_y) / 2
    return BBox(x - half, y - half, x + half, y + half, "EPSG:2180")


def _area(box: BBox) -> Polygon:
    return rectangle(box.min_x, box.min_y, box.max_x, box.max_y)


def _index_session(records: list[dict]) -> Mock:
    """Session whose every WFS GetFeature answers ``records``."""
    session = Mock(spec=requests.Session)
    session.get = Mock(return_value=wfs_response(render_wfs_body(records)))
    return session


def _gugik_session(index: str, files: dict[str, bytes] | None = None) -> Mock:
    """GUGiK stand-in: WFS GetFeature -> ``index``; an OpenData URL of
    ``files`` -> its bytes; any other request -> HTTP 404."""
    known = files or {}

    def get(url, **kwargs):
        if url in known:
            response = Mock(spec=requests.Response)
            response.status_code = 200
            response.raise_for_status = Mock()
            response.headers = {}
            response.iter_content = Mock(return_value=[known[url]])
            return response
        query = parse_qs(urlparse(url).query)
        if query.get("REQUEST") == ["GetFeature"]:
            return wfs_response(index)
        return wfs_response("", status=404)

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    return session


def _downloads(session: Mock) -> list[str]:
    """OpenData files the session was asked for, in call order."""
    return [
        call.args[0]
        for call in session.get.call_args_list
        if call.args[0].startswith(OPENDATA)
    ]


def _sidecar(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text("utf-8"))


def _tbd_25m(session: Mock) -> GugikProvider:
    return GugikProvider(session, vertical_crs="KRON86", resolution="25m", format="TBD")


# =============================================================================
# Sheets of an area from the index (GugikProvider.index_sheets)
# =============================================================================


class TestIndexSheets:
    def test_records_of_the_variant_only(self):
        """Format, resolution and horizontal system are hard filters: the
        answer of the area holds every record of every format."""
        session = _index_session(
            [
                _record(SHEET),
                _record(SHEET, akt_data="2000-01-01", resolution="30.0 m"),
                _record(SHEET, akt_data="2000-01-01", resolution=None, fmt="ESRI TIN"),
                _record(
                    SHEET, akt_data="2000-01-01", resolution=None, fmt="Intergraph TTN"
                ),
                _record(
                    f"{SHEET}-1",
                    akt_data="2014-04-26",
                    resolution="1.00 m",
                    fmt="ASCII XYZ GRID",
                ),
                _record(
                    f"{SHEET}-1",
                    akt_data="2014-04-26",
                    resolution="1.00 m",
                    fmt="ARC/INFO ASCII GRID",
                ),
                # PL-2000 sheet overlapping the frame
                _record("8.221.11", system="PL-2000:S8"),
            ]
        )
        provider = _tbd_25m(session)
        frame = sheet_frame_2180(SHEET)

        assert provider.index_sheets([frame], system="1992") == [SHEET]
        assert provider.index_sheets([frame], system="2000") == ["8.221.11"]

    def test_neighbour_sharing_an_edge_is_excluded(self):
        """The sheet frame as the area: its edge neighbours in the index touch
        it (GUGiK frames meet within a fraction of a metre) and are not its
        sheets; an area reaching across the edge takes the neighbour too."""
        east, north = "N-34-58-D-c-4", "N-34-58-D-c-1"
        provider = _tbd_25m(_index_session([_record(s) for s in (SHEET, east, north)]))
        frame = sheet_frame_2180(SHEET)

        assert provider.index_sheets([frame], system="1992") == [SHEET]
        across = provider.index_sheets([_area(ACROSS_EAST_EDGE)], system="1992")
        assert across == [SHEET, east]

    def test_sheet_frame_takes_index_sheets_of_any_scale(self):
        """EVRF2007 TBD 25 m lies on 1:10000 sheets: a 1:25000 frame takes the
        four sheets inside it, not the 1:10000 neighbour across its edge."""
        inside = [f"{SHEET}-{quarter}" for quarter in (1, 2, 3, 4)]
        records = [
            _record(sheet, akt_data="2018-04-22", uklad_h="PL-EVRF2007-NH")
            for sheet in (*inside, "N-34-58-D-c-1-3")
        ]
        provider = GugikProvider(
            _index_session(records),
            vertical_crs="EVRF2007",
            resolution="25m",
            format="TBD",
        )

        assert provider.index_sheets([sheet_frame_2180(SHEET)], system="1992") == inside

    def test_sheets_overlap_an_area_not_the_envelope(self):
        """Two distant areas (features of a geometry) cost one query for their
        envelope; the sheet between them overlaps no area."""
        far = "N-34-58-D-d-3"
        session = _index_session([_record(s) for s in (SHEET, "N-34-58-D-c-4", far)])
        boxes = [_centre_box(SHEET, 50), _centre_box(far, 50)]

        sheets = _tbd_25m(session).index_sheets(
            [_area(box) for box in boxes], system="1992"
        )

        assert sheets == [SHEET, far]
        (query,) = wfs_requests(session)
        min_n, min_e, max_n, max_e = map(float, query["BBOX"].split(",")[:4])
        assert (min_e, min_n, max_e, max_n) == pytest.approx(
            (boxes[0].min_x, boxes[0].min_y, boxes[1].max_x, boxes[1].max_y)
        )

    def test_year_bounds_limit_types_and_records(self):
        """Only the yearly types within the bounds are queried; a record of
        such a type dated outside them is not a sheet of the request."""
        session = _index_session(
            [
                _record(SHEET),  # 2010
                _record(
                    "N-34-58-D-c-4", akt_data="2009-06-30", layer="SkorowidzNMT2010"
                ),
            ]
        )

        sheets = _tbd_25m(session).index_sheets(
            [_area(ACROSS_EAST_EDGE)], system="1992", min_year=2010, max_year=2015
        )

        assert sheets == [SHEET]
        (query,) = wfs_requests(session)
        assert query["TYPENAMES"] == ",".join(
            f"gugik:SkorowidzNMT{year}" for year in range(2015, 2009, -1)
        )

    def test_no_record_is_an_empty_list(self):
        session = _index_session([])
        frame = sheet_frame_2180(SHEET)
        assert _tbd_25m(session).index_sheets([frame], system="1992") == []

    def test_years_without_index_types_send_no_query(self):
        """KRON86 types start in 2000: earlier years have no record at all."""
        session = _index_session([_record(SHEET)])
        frame = sheet_frame_2180(SHEET)
        sheets = _tbd_25m(session).index_sheets([frame], system="1992", max_year=1999)
        assert sheets == []
        assert wfs_requests(session) == []

    def test_failed_query_is_download_error(self):
        """A failed index query is never an empty result (the recorded HTTP
        400 ExceptionReport)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=wfs_response(wfs_fixture("exception_report.xml"), status=400)
        )
        with pytest.raises(DownloadError, match="the result would be incomplete"):
            _tbd_25m(session).index_sheets([sheet_frame_2180(SHEET)], system="1992")


# =============================================================================
# download_data / check_data / CLI with an archive format
# =============================================================================


class TestDownloadArchive:
    @pytest.mark.parametrize("sheet", [SHEET, f"{SHEET}-1"])
    def test_sheet_gives_the_archive_of_the_index(self, tmp_path, sheet):
        """A sheet code inside the 1:25000 archive frame (that frame or one of
        its 1:10000 sheets): the index sheet, the original file, the sidecar
        of the archive variant."""
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        with patch(SESSION_FACTORY, return_value=session):
            report = download_data(
                product="nmt", root=tmp_path, sheet=sheet, cache=False, **TBD_25M
            )

        assert report.ok
        assert report.notices == (
            Notice("info", SHEET_LIST, SHEET_LISTED.format(what=f"sheet {sheet}")),
        )
        (unit,) = report.files
        assert unit.unit == SHEET
        assert unit.file.path == tmp_path / STANDARD
        assert unit.file.path.read_bytes() == ARCHIVE
        assert _downloads(session) == [TBD_URL]
        meta = _sidecar(unit.file.path)
        assert meta["dataset"] == "pl.gugik.nmt_tbd_25m"
        assert meta["resolution"] == "25m"
        assert meta["extra"]["source"]["format"] == "ASCII TBD"
        assert meta["extra"]["source"]["url"] == TBD_URL
        assert meta["extra"]["source"]["layer"] == "SkorowidzNMT2010"

    @pytest.mark.parametrize(
        ("fmt", "resolution", "sheet", "name", "record_format", "stored", "dataset"),
        [
            (
                "TTN",
                None,
                SHEET,
                "4543_360776_N-34-58-D-c-3.ttn",
                "Intergraph TTN",
                "nmt/pl_1992_ttn_kron86/N-34/58/D/c/3/N-34-58-D-c-3.ttn",
                "pl.gugik.nmt_ttn",
            ),
            (
                "TIN",
                None,
                SHEET,
                "4542_360777_N-34-58-D-c-3_tin.zip",
                "ESRI TIN",
                "nmt/pl_1992_tin_kron86/N-34/58/D/c/3/N-34-58-D-c-3.zip",
                "pl.gugik.nmt_tin",
            ),
            (
                "GRD",
                "5m",
                "M-34-10-B-a-1",
                "4641_410597_M-34-10-B-a-1.grd",
                "Intergraph GRD",
                "nmt/pl_1992_grd_5m_kron86/M-34/10/B/a/1/M-34-10-B-a-1.grd",
                "pl.gugik.nmt_grd_5m",
            ),
            (
                "DXF",
                "25m",
                "M-33-24-B-b-1",
                "4506_363954_M-33-24-B-b-1.dxf",
                "Warstwice DXF",
                "nmt/pl_1992_dxf_25m_kron86/M-33/24/B/b/1/M-33-24-B-b-1.dxf",
                "pl.gugik.nmt_dxf_25m",
            ),
            (
                "DGN",
                "25m",
                "N-33-103-B-b-4",
                "4512_376571_N-33-103-B-b-4.dgn",
                "Warstwice DGN",
                "nmt/pl_1992_dgn_25m_kron86/N-33/103/B/b/4/N-33-103-B-b-4.dgn",
                "pl.gugik.nmt_dgn_25m",
            ),
        ],
        ids=["TTN", "TIN", "GRD", "DXF", "DGN"],
    )
    def test_each_archive_format_of_the_recorded_index(
        self, tmp_path, fmt, resolution, sheet, name, record_format, stored, dataset
    ):
        """The recorded index of a sheet holds several archives of one
        delivery: the requested format's file is downloaded, checked by its
        signature and stored in the segment of its variant."""
        url = f"{OPENDATA}NumDaneWys/NMT/{name.split('_', 1)[0]}/{name}"
        body = ARCHIVE if name.endswith(".zip") else _head(name)
        session = _gugik_session(
            wfs_fixture(f"sheet_nmt_kron86_{sheet}.xml"), {url: body}
        )
        with patch(SESSION_FACTORY, return_value=session):
            report = download_data(
                product="nmt",
                root=tmp_path,
                sheet=sheet,
                format=fmt,
                resolution=resolution,
                vertical_crs="KRON86",
                cache=False,
            )

        assert report.ok
        assert [(f.unit, f.file.path) for f in report.files] == [
            (sheet, tmp_path / stored)
        ]
        assert (tmp_path / stored).read_bytes() == body
        assert _downloads(session) == [url]
        meta = _sidecar(tmp_path / stored)
        assert (meta["dataset"], meta["extra"]["source"]["format"]) == (
            dataset,
            record_format,
        )

    def test_bbox_sheets_come_from_the_index(self, tmp_path):
        """The recorded query area (20 m at the centre of the 1:25000 frame):
        the archive's 1:25000 sheet, not the 1:10000 sheets of the grid."""
        bbox = _centre_box(SHEET, 10)
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        with patch(SESSION_FACTORY, return_value=session):
            report = download_data(
                product="nmt",
                root=tmp_path,
                bbox=bbox,
                country="pl",
                sheet_system="1992",
                cache=False,
                **TBD_25M,
            )

        assert report.ok
        assert report.notices == (
            Notice("info", SHEET_LIST, SHEET_LISTED.format(what="bbox")),
        )
        assert [(f.unit, f.file.path) for f in report.files] == [
            (SHEET, tmp_path / STANDARD)
        ]
        assert _downloads(session) == [TBD_URL]
        meta = _sidecar(tmp_path / STANDARD)
        assert meta["dataset"] == "pl.gugik.nmt_tbd_25m"
        assert meta["extra"]["parent_request"] == {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": "EPSG:2180",
            "countries": ["PL"],
        }

    def test_partial_archive_is_stored_without_coverage(self, tmp_path, caplog):
        """An archive of a sheet not declared full is kept as published: no
        valid-pixel share is measured (no ``extra.coverage``, no warning)."""
        record = _record(SHEET, czy_ark_wypelniony="NIE")
        url = record["url_do_pobrania"]
        session = _gugik_session(render_wfs_body([record]), {url: ARCHIVE})
        with (
            caplog.at_level(logging.WARNING),
            patch(SESSION_FACTORY, return_value=session),
        ):
            report = download_data(
                product="nmt", root=tmp_path, sheet=SHEET, cache=False, **TBD_25M
            )

        assert report.ok
        (unit,) = report.files
        meta = _sidecar(unit.file.path)
        assert meta["extra"]["campaign"]["full_sheet"] is False
        assert "coverage" not in meta["extra"]
        assert [r.getMessage() for r in caplog.records] == []

    @pytest.mark.parametrize(
        ("resolution", "years", "label"),
        [("15m", {}, ""), ("25m", {"max_year": 2009}, " up to 2009")],
        ids=["no-15m-record", "25m-only-in-2010"],
    )
    def test_no_record_of_the_variant_is_no_coverage(
        self, tmp_path, resolution, years, label
    ):
        """The index has archives of the sheet but none of the variant in the
        year bounds: no download, a no_coverage failure naming the variant."""
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        with patch(SESSION_FACTORY, return_value=session):
            report = download_data(
                product="nmt",
                root=tmp_path,
                sheet=SHEET,
                format="TBD",
                resolution=resolution,
                vertical_crs="KRON86",
                cache=False,
                **years,
            )

        assert report.ok is False
        assert report.files == ()
        assert report.failed == (
            UnitFailure(
                "PL",
                "PL",
                f"The GUGiK sheet index has no NMT TBD {resolution} files KRON86 "
                f"(PL-1992){label} for sheet {SHEET} - area data available: "
                "kartograf elevation availability",
                "no_coverage",
            ),
        )
        assert _downloads(session) == []

    def test_check_data_plans_the_index_sheet(self, tmp_path):
        """``--check`` of an archive plans the 1:25000 sheet of the
        index (one item, not its 1:10000 sheets) without downloading."""
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        with patch(SESSION_FACTORY, return_value=session):
            plan = check_data(
                product="nmt", root=tmp_path, sheet=SHEET, cache=False, **TBD_25M
            )

        (item,) = plan.items
        assert (item.segment, item.hierarchy, item.name, item.unit) == (
            "nmt/pl_1992_tbd_25m_kron86",
            "N-34/58/D/c/3",
            "N-34-58-D-c-3.zip",
            SHEET,
        )
        assert (item.status, item.available_label) == ("missing", "2010-10-09_5143")
        assert _downloads(session) == []

    def test_manager_downloads_archive_sheet_as_given(self, tmp_path):
        """``DownloadManager.download_sheet`` with an archive provider keeps
        the 1:25000 code (a grid variant expands it to 1:10000)."""
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        manager = DownloadManager(_tbd_25m(session), root=tmp_path)

        result = manager.download_sheet(SHEET)

        (file,) = result.files[SHEET]
        assert file.path == tmp_path / STANDARD
        assert _downloads(session) == [TBD_URL]

    def test_cli_equals_api(self, tmp_path, frozen_clock):
        """``elevation download --format TBD`` = ``download_data(format="TBD")``:
        the same store bytes (link, version, sidecars)."""
        session = _gugik_session(wfs_fixture(RECORDED), {TBD_URL: ARCHIVE})
        with patch(SESSION_FACTORY, return_value=session):
            run = run_both(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "--sheet",
                    SHEET,
                    *TBD_25M_ARGV,
                    "-q",
                ],
                lambda out: download_data(
                    product="nmt", root=out, sheet=SHEET, **TBD_25M
                ),
                tmp_path,
            )

        assert run.cli_code == 0
        assert isinstance(run.api_result, DataReport) and run.api_result.ok
        assert (run.cli_store / STANDARD).read_bytes() == ARCHIVE
        assert_same_store(run.cli_store, run.api_store)


# =============================================================================
# Choices rejected before the network
# =============================================================================

_BBOX_ARGV = ["--bbox", "743470,725300,743480,725310", "--bbox-crs", "EPSG:2180"]
_BBOX = BBox(743470, 725300, 743480, 725310, "EPSG:2180")
_SCALE_ERROR = (
    "--scale does not apply to --format TBD: archive sheets (various scales) come "
    "from the GUGiK sheet index - omit --scale"
)


@pytest.mark.parametrize(
    ("argv", "selection", "message"),
    [
        (
            ["--product", "nmt", "--sheet", SHEET, "--scale", "1:10000", *TBD_25M_ARGV],
            {"product": "nmt", "sheet": SHEET, "scale": "1:10000", **TBD_25M},
            _SCALE_ERROR,
        ),
        (
            ["--product", "nmt", *_BBOX_ARGV, "--country", "pl"]
            + ["--sheet-system", "2000", "--scale", "1:5000", *TBD_25M_ARGV],
            {
                "product": "nmt",
                "bbox": _BBOX,
                "country": "pl",
                "sheet_system": "2000",
                "scale": "1:5000",
                **TBD_25M,
            },
            _SCALE_ERROR,
        ),
        (
            ["--product", "nmt", *_BBOX_ARGV, "--country", "pl", "--cutout"]
            + ["--horizontal-crs", "EPSG:2180", *TBD_25M_ARGV],
            {
                "product": "nmt",
                "bbox": _BBOX,
                "country": "pl",
                "cutout": True,
                "horizontal_crs": "EPSG:2180",
                **TBD_25M,
            },
            (
                "--cutout works only with the ASC 1m grid (a cutout from GUGiK WCS); "
                "--format TBD means source sheet files - omit --cutout"
            ),
        ),
        (
            ["--product", "nmt", "--sheet", SHEET, "--format", "XYZ"]
            + ["--resolution", "0.5m", "--vertical-crs", "KRON86"],
            {
                "product": "nmt",
                "sheet": SHEET,
                "format": "XYZ",
                "resolution": "0.5m",
                "vertical_crs": "KRON86",
            },
            (
                "PL has no resolution 0.5m for NMT XYZ - available: EVRF2007: 1m, 5m; "
                "KRON86: 1m; vertical CRS unknown: 100m"
            ),
        ),
        (
            ["--product", "laz", "--sheet", f"{SHEET}-1", "--format", "TBD"]
            + ["--vertical-crs", "KRON86"],
            {
                "product": "laz",
                "sheet": f"{SHEET}-1",
                "format": "TBD",
                "vertical_crs": "KRON86",
            },
            (
                "--format applies only to --product nmt and nmpt (PL) and contours "
                "(CZ), got --product laz - omit --format"
            ),
        ),
    ],
    ids=["scale-sheet", "scale-bbox", "cutout", "xyz-resolution", "laz"],
)
def test_rejected_before_network_cli_equals_api(tmp_path, argv, selection, message):
    session = Mock(spec=requests.Session)
    with patch(SESSION_FACTORY, return_value=session):
        run = run_both(
            ["elevation", "download", *argv],
            lambda out: download_data(root=out, cache=False, **selection),
            tmp_path,
        )

    assert run.cli_code == 2
    assert isinstance(run.api_error, ValidationError)
    assert f"Error: {run.api_error.localized('pl')}" in run.cli_stderr.splitlines()
    assert str(run.api_error) == message
    session.get.assert_not_called()
    assert not run.cli_store.exists() and not run.api_store.exists()


def test_format_for_orto_is_validation_error(tmp_path):
    """``imagery download`` has no ``--format``; the API rejects it."""
    with pytest.raises(ValidationError) as caught:
        download_data(
            product="orto",
            root=tmp_path,
            sheet=f"{SHEET}-1",
            format="TBD",
            cache=False,
        )
    assert str(caught.value) == (
        "--format applies only to --product nmt and nmpt (PL) and contours (CZ), "
        "got --product orto - omit --format"
    )


def test_xyz_resolution_error_lists_the_registry(tmp_path):
    """The labels offered for ``--format XYZ`` are those of the registry
    (with the voivodeship files NMT 100 m, whose height system is unknown)."""
    prefix = "PL has no resolution 0.5m for NMT XYZ - available: "
    with pytest.raises(ValidationError) as caught:
        download_data(
            product="nmt",
            root=tmp_path,
            sheet=SHEET,
            format="XYZ",
            resolution="0.5m",
            vertical_crs="KRON86",
            cache=False,
        )
    text = str(caught.value)
    assert text.startswith(prefix)
    listed = {
        vertical_crs: set(labels.split(", "))
        for vertical_crs, labels in (
            part.split(": ") for part in text.removeprefix(prefix).split("; ")
        )
    }
    found = variants(product="nmt", country="PL", format="XYZ")
    registry = {
        vertical_crs or UNKNOWN_VERTICAL: {
            v.label for v in found if v.vertical_crs == vertical_crs
        }
        for vertical_crs in {v.vertical_crs for v in found}
    }
    assert listed == registry
