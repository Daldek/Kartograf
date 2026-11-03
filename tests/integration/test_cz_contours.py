"""CZ contour lines (ZABAGED, CUZK) through ``download_data`` (plan E1, step 5).

The openzu answers replay the recorded ``HEAD`` headers and ZIP member lists
of ``tests/fixtures/cz/contours/files.json`` (member bytes are stand-ins);
the SM5 index answers are the recorded ``KladyMapovychListu`` fixtures.
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from kartograf.core.bbox import BBox
from kartograf.download import cz_contours
from kartograf.download.data import check_data, download_data
from kartograf.exceptions import ValidationError
from kartograf.notices import AUTO_NARROWED_TO_CZ, SHEET_LIST
from kartograf.providers.cuzk.sheets import KLADY_ENDPOINT, SM5_LAYER

FIXTURES = Path(__file__).parent.parent / "fixtures"
FILES = json.loads((FIXTURES / "cz" / "contours" / "files.json").read_text())
ORTO = FIXTURES / "cz" / "ortofoto"
KLADY = f"{KLADY_ENDPOINT}/{SM5_LAYER}/query"
INDEX_RECORDS = {
    "CTES96": FIXTURES / "cuzk" / "klady_sm5_where_ctes96.json",
    "CTES86": ORTO / "klady_sm5_where_ctes86.json",
}
# Interior of CTES96 and CTES86 (the recorded index answer of this envelope);
# Cesky Tesin lies inside the WGS84 envelopes of both PL and CZ.
AREA = BBox(-448500.0, -1113500.0, -446500.0, -1112500.0, "EPSG:5514")
# A WGS84 area across the PL-CZ border near Nachod (both country envelopes).
BORDER = BBox(16.10, 50.38, 16.20, 50.45, "EPSG:4326")
OPENZU = "https://openzu.cuzk.gov.cz/opendata"
DIRECTORIES = {"SHP": "ZABAGED-vyskopis", "DGN": "ZABAGED-vyskopis-DGN"}


def _url(fmt: str, sheet: str) -> str:
    return f"{OPENZU}/{DIRECTORIES[fmt]}/epsg-5514/{sheet}.zip"


def _archive(fmt: str, sheet: str, edition: str = "2026") -> bytes:
    """A ZIP with the recorded member names of CTES96 renamed to ``sheet``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, _size in FILES[f"contours_{fmt.lower()}_CTES96"]["members"]:
            archive.writestr(name.replace("CTES96", sheet), f"{sheet} {name} {edition}")
    return buffer.getvalue()


def _response(status: int, body: bytes, headers: dict[str, str]) -> Mock:
    response = Mock()
    response.status_code = status
    response.headers = dict(headers)
    response.content = body
    response.iter_content = lambda chunk_size=1: (
        body[i : i + 1000] for i in range(0, len(body), 1000)
    )
    if status >= 400:
        error = requests.HTTPError(f"{status} Error", response=response)
        response.raise_for_status.side_effect = error
    return response


def _json_response(path: Path) -> Mock:
    response = Mock()
    response.status_code = 200
    response.json.return_value = json.loads(path.read_text(encoding="utf-8"))
    return response


class FakeOpenzu:
    """``requests.Session`` stand-in: the SM5 index layer and the openzu ZIPs
    (``HEAD`` and ``GET``) of the recorded headers; ``publish`` replaces a
    ZIP with a new ``ETag``."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, dict[str, str]]] = {}
        self.calls: list[tuple[str, str]] = []
        for fmt in DIRECTORIES:
            recorded = FILES[f"contours_{fmt.lower()}_CTES96"]["headers"]
            for sheet in INDEX_RECORDS:
                body = _archive(fmt, sheet)
                headers = {**recorded, "Content-Length": str(len(body))}
                self.files[_url(fmt, sheet)] = (body, headers)

    def publish(self, url: str, body: bytes, etag: str) -> None:
        self.files[url] = (
            body,
            {**self.files[url][1], "ETag": etag, "Content-Length": str(len(body))},
        )

    def _file(self, url: str, body: bool) -> Mock:
        if url not in self.files:
            return _response(404, b"<html>404</html>", {"Content-Type": "text/html"})
        content, headers = self.files[url]
        return _response(200, content if body else b"", headers)

    def head(self, url: str, timeout: Any = None, **kwargs: Any) -> Mock:
        self.calls.append(("HEAD", url))
        return self._file(url, body=False)

    def get(self, url: str, timeout: Any = None, params: Any = None, **kwargs: Any):
        self.calls.append(("GET", url))
        if url == KLADY:
            query: dict[str, str] = params or {}
            if "where" in query:
                sheet = query["where"].removeprefix("MAPNOM='").removesuffix("'")
                return _json_response(INDEX_RECORDS[sheet])
            return _json_response(ORTO / "klady_sm5_bbox_ctes96_ctes86.json")
        return self._file(url, body=True)

    def zip_gets(self) -> list[str]:
        return [url for method, url in self.calls if method == "GET" and url != KLADY]


@pytest.fixture
def openzu(monkeypatch) -> FakeOpenzu:
    fake = FakeOpenzu()
    monkeypatch.setattr(cz_contours, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text())


def test_contours_sheet_zip_kept(tmp_path, openzu):
    """``--sheet CTES96 --format SHP``: the openzu ZIP 1:1 (8 files, not
    unpacked) in the SM5 hierarchy; DGN lands in its own segment."""
    report = download_data(
        product="contours",
        format="SHP",
        sheet="CTES96",
        root=tmp_path,
        cache=False,
    )

    assert report.ok
    (unit,) = report.files
    path = tmp_path / "contours" / "cz_zabaged_shp" / "CTES" / "96" / "CTES96.zip"
    assert unit.file.path == path
    assert path.read_bytes() == openzu.files[_url("SHP", "CTES96")][0]
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 8
    meta = _meta(unit.file.version_path)
    assert meta["dataset"] == "cz.cuzk.zabaged_contours_shp"
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["extra"]["http"]["etag"] == '"0ec953fb18dd1:0"'
    assert meta["extra"]["mapname"]
    assert len(meta["extra"]["members"]) == 8
    assert not list(tmp_path.rglob("*.shp"))  # nothing unpacked

    dgn = download_data(
        product="contours",
        format="DGN",
        sheet="CTES96",
        root=tmp_path,
        cache=False,
    )
    (unit,) = dgn.files
    assert unit.file.path == (
        tmp_path / "contours" / "cz_zabaged_dgn" / "CTES" / "96" / "CTES96.zip"
    )
    assert _meta(unit.file.version_path)["dataset"] == "cz.cuzk.zabaged_contours_dgn"


def test_contours_area_expands_to_sm5(tmp_path, openzu):
    """An EPSG:5514 area gives the SM5 sheets of the CUZK index, one ZIP each."""
    notices = []
    report = download_data(
        product="contours",
        format="SHP",
        country="cz",
        bbox=AREA,
        root=tmp_path,
        cache=False,
        on_notice=notices.append,
    )

    assert report.ok
    assert sorted(unit.unit for unit in report.files) == ["CTES86", "CTES96"]
    assert sorted(openzu.zip_gets()) == [_url("SHP", "CTES86"), _url("SHP", "CTES96")]
    (listing,) = [n for n in notices if n.code == SHEET_LIST]
    assert "CTES86" in listing.message and "CTES96" in listing.message
    for unit in report.files:
        assert _meta(unit.file.version_path)["extra"]["parent_request"][
            "countries"
        ] == ["CZ"]


@pytest.mark.parametrize(
    "choice",
    [
        {"cutout": True, "horizontal_crs": "EPSG:5514"},
        {"resolution": "5m"},
        {"year": 2020},
        {"sheet_system": "1992"},
    ],
)
def test_contours_reject_grid_choices(tmp_path, openzu, choice):
    with pytest.raises(ValidationError, match="contours are SM5 sheets \\(vector\\)"):
        download_data(
            product="contours",
            format="SHP",
            country="cz",
            bbox=AREA,
            root=tmp_path,
            cache=False,
            **choice,
        )
    assert openzu.calls == []


def test_contours_format_and_height_system(tmp_path, openzu):
    """``--format`` is required (SHP, DGN); ``--vertical-crs`` may be omitted
    and takes only Bpv."""
    with pytest.raises(ValidationError, match="--format required .*: SHP, DGN"):
        download_data(product="contours", sheet="CTES96", root=tmp_path)
    with pytest.raises(ValidationError, match="available: SHP, DGN"):
        download_data(product="contours", format="GPKG", sheet="CTES96", root=tmp_path)
    with pytest.raises(ValidationError, match="have heights Bpv"):
        download_data(
            product="contours",
            format="SHP",
            vertical_crs="EVRF2007",
            sheet="CTES96",
            root=tmp_path,
        )
    assert openzu.calls == []

    report = download_data(
        product="contours",
        format="SHP",
        vertical_crs="Bpv",
        sheet="CTES96",
        root=tmp_path,
        cache=False,
    )
    assert report.ok


def test_contours_sheet_systems(tmp_path, openzu):
    """A TM33 tile and a PL sheet code are not contour sheets."""
    with pytest.raises(ValidationError, match="are SM5 sheets"):
        download_data(product="contours", format="SHP", sheet="302_5550", root=tmp_path)
    with pytest.raises(ValidationError, match="has no data for PL"):
        download_data(
            product="contours",
            format="SHP",
            sheet="M-33-58-B-c-3-1",
            root=tmp_path,
        )
    assert openzu.calls == []


def test_contours_country_rules(tmp_path, openzu):
    """``--country pl`` is an error; ``auto`` across the border keeps CZ."""
    with pytest.raises(ValidationError, match="is available only for CZ"):
        download_data(
            product="contours",
            format="SHP",
            country="pl",
            bbox=BORDER,
            root=tmp_path,
        )

    notices = []
    check_data(
        product="contours",
        format="SHP",
        country="auto",
        bbox=AREA,
        root=tmp_path,
        cache=False,
        on_notice=notices.append,
    )
    (narrowed,) = [n for n in notices if n.code == AUTO_NARROWED_TO_CZ]
    assert narrowed.message == "--country auto -> cz (--product contours only for CZ)"


def test_contours_http_signal(tmp_path, openzu):
    """A second run uses the local version without a request (ADR-036 erratum
    3); a new ZIP is seen by the check (``HEAD``), then ``upgrade`` downloads
    it as a new version."""
    selection = {
        "product": "contours",
        "format": "SHP",
        "sheet": "CTES96",
        "root": tmp_path,
        "cache": False,
    }
    first = download_data(**selection).files[0].file
    url = _url("SHP", "CTES96")

    openzu.calls.clear()
    again = download_data(**selection).files[0].file
    assert again.status == "local" and again.unverified == "unchecked"
    assert openzu.calls == []
    assert check_data(**selection).items[0].status == "current"

    new_zip = _archive("SHP", "CTES96", edition="2027")
    openzu.publish(url, new_zip, '"nowe-wydanie"')
    reported = download_data(**selection).files[0].file
    assert reported.status == "local" and reported.newer is None
    assert check_data(**selection).items[0].status == "newer"

    upgraded = download_data(**selection, update="upgrade").files[0].file
    assert upgraded.status == "new"
    assert upgraded.label != first.label or upgraded.sha256 != first.sha256
    assert upgraded.path.read_bytes() == new_zip
    assert first.version_path.exists()


def test_contours_bad_package_commits_no_version(tmp_path, openzu):
    """An HTML page instead of the ZIP and a missing sheet (404) fail the
    sheet; no version is committed."""
    url = _url("SHP", "CTES96")
    openzu.files[url] = (b"<html>maintenance</html>", openzu.files[url][1])
    report = download_data(
        product="contours",
        format="SHP",
        sheet="CTES96",
        root=tmp_path,
        cache=False,
    )
    assert not report.ok and not report.files
    assert "ZIP" in report.failed[0].error
    del openzu.files[url]
    report = download_data(
        product="contours",
        format="SHP",
        sheet="CTES96",
        root=tmp_path,
        cache=False,
    )
    assert "KladyMapovychListu" in report.failed[0].error
    assert not list((tmp_path / "contours").rglob("*.zip"))
