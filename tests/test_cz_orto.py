"""CZ orthophoto (ADR-042 D13): SM5 sheets of the CUZK ATOM feed in the
versioned store - ``download_data``/``check_data`` with ``product="orto"``.

Fixtures (READMEs there): ``tests/fixtures/cz/ortofoto`` - the ORTOFOTO
service feed trimmed to AS91, CTES86 and CTES96, the dataset feed of CTES86,
sheet ZIPs with the real member names and world files (an 8 x 8 px JPEG
instead of the 16-64 MB image) and KladyMapovychListu answers;
``tests/fixtures/cz/atom`` - the dataset feeds of CTES96 and AS91 and the
404 page of a missing feed; ``tests/fixtures/cuzk`` - the index record of
CTES96. The ``length`` of a dataset feed is set to the size of the fixture
ZIP (the engine checks the transfer against it).
"""

import hashlib
import io
import json
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords, transform_bbox
from kartograf.core.sheet_parser import find_sheets_for_bbox
from kartograf.download import cz_orto
from kartograf.download.area import bbox_to_2180
from kartograf.download.data import check_data, download_data, validate_data_request
from kartograf.download.fetch import VersionedFile
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import AUTO_NARROWED_TO_PL, CHECK_FAILED, SHEET_LIST
from kartograf.providers.cuzk.raster import bbox_to_crs
from kartograf.providers.cuzk.sheets import KLADY_ENDPOINT, SM5_LAYER
from tests.conftest import recorded_response

FIXTURES = Path(__file__).parent / "fixtures"
ORTO = FIXTURES / "cz" / "ortofoto"
ATOM = FIXTURES / "cz" / "atom"

SERVICE = "https://atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml"
FEEDS = "https://atom.cuzk.gov.cz/ORTOFOTO/datasetFeeds/CZ-00025712-CUZK_ORTOFOTO_"
OPENZU = "https://openzu.cuzk.cz/opendata/ORTOFOTO/"
KLADY = f"{KLADY_ENDPOINT}/{SM5_LAYER}/query"
SERVICE_ETAG = '"64a6104edbc8dc1:0"'

# sheet -> (release year, dataset feed); the files of a sheet in commit order
RELEASES = {
    "CTES96": ("2024", ATOM / "ortofoto_ctes96.xml"),
    "CTES86": ("2024", ORTO / "ortofoto_ctes86.xml"),
    "AS91": ("2025", ATOM / "ortofoto_as91.xml"),
}
INDEX_RECORDS = {
    "CTES96": FIXTURES / "cuzk" / "klady_sm5_where_ctes96.json",
    "CTES86": ORTO / "klady_sm5_where_ctes86.json",
    "AS91": ORTO / "klady_sm5_where_as91.json",
}
SUFFIXES = (".jgw", ".TM33N.jgw", ".TM34N.jgw", ".jpg")
WORLD_FILES = {
    ".jgw": "EPSG:5514",
    ".TM33N.jgw": "EPSG:3045",
    ".TM34N.jgw": "EPSG:3046",
}
# Interior of CTES96 and CTES86 (the recorded index answer of this envelope)
AREA = BBox(-448500.0, -1113500.0, -446500.0, -1112500.0, "EPSG:5514")
# Interior of AS91 (west of the PL envelope: CZ only under country="auto")
AS91_AREA = BBox(-899500.0, -1003500.0, -898000.0, -1002500.0, "EPSG:5514")


def _archive(sheet: str) -> Path:
    return ORTO / f"WRTO24.{RELEASES[sheet][0]}.{sheet}.zip"


def _members(sheet: str) -> dict[str, bytes]:
    """Member bytes of the fixture ZIP of ``sheet`` by stored suffix."""
    name = f"WRTO24.{RELEASES[sheet][0]}.{sheet}"
    with zipfile.ZipFile(_archive(sheet)) as archive:
        return {suffix: archive.read(f"{name}{suffix}") for suffix in SUFFIXES}


def _meta(file: VersionedFile) -> dict:
    sidecar = file.version_path.with_name(f"{file.version_path.name}.meta.json")
    return json.loads(sidecar.read_text(encoding="utf-8"))


def _json_response(path: Path) -> Mock:
    response = Mock()
    response.status_code = 200
    response.json.return_value = json.loads(path.read_text(encoding="utf-8"))
    return response


def _file_response(headers_of: Path, body: bytes, **headers: str) -> Mock:
    response = recorded_response(headers_of, body=body)
    response.headers.update(headers)
    return response


def _not_modified(etag: str) -> Mock:
    response = Mock()
    response.status_code = 304
    response.headers = {"ETag": etag}
    response.content = b""
    return response


def _rezip(archive: bytes, old: str, new: str, image: bytes) -> bytes:
    """The ZIP of a new release: members renamed, the same world files, a new image."""
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(archive)) as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            data = image if info.filename.endswith(".jpg") else source.read(info)
            target.writestr(info.filename.replace(old, new), data)
    return buffer.getvalue()


class FakeCuzk:
    """``requests.Session`` stand-in for CUZK: the ORTOFOTO service feed (with
    ``If-None-Match``), dataset feeds, sheet ZIPs and the SM5 index layer.

    ``calls`` = every requested URL, ``envelopes`` = the areas asked from
    the index (EPSG:5514).
    """

    def __init__(self) -> None:
        self.service = (ORTO / "ortofoto_service.xml").read_bytes()
        self.etag = SERVICE_ETAG
        self.routes: dict[str, Callable[[], Any]] = {}
        self.feeds: dict[str, bytes] = {}
        self.archives: dict[str, bytes] = {}
        self.years: dict[str, str] = {}
        self.calls: list[str] = []
        self.envelopes: list[tuple[float, ...]] = []
        for sheet, (year, feed) in RELEASES.items():
            self._publish(sheet, year, feed.read_bytes(), _archive(sheet).read_bytes())

    def _publish(
        self, sheet: str, year: str, feed: bytes, archive: bytes, etag: str = ""
    ) -> None:
        """Routes of a release: its dataset feed and the ZIP the feed links
        (``etag`` of a new ZIP; else the recorded one)."""
        feed = re.sub(rb'length="[0-9]+"', b'length="%d"' % len(archive), feed)
        self.years[sheet], self.feeds[sheet], self.archives[sheet] = year, feed, archive
        headers = {
            "Content-Length": str(len(archive)),
            **({"ETag": etag} if etag else {}),
        }
        link = re.search(rb'<link href="([^"]+\.zip)"', feed)
        assert link is not None
        self.routes[f"{FEEDS}WRTO24.{year}.{sheet}.xml"] = lambda: recorded_response(
            ATOM / "ortofoto_ctes96.xml", body=feed
        )
        self.routes[link.group(1).decode()] = lambda: _file_response(
            _archive(sheet), archive, **headers
        )

    def release(self, sheet: str, year: str, updated: str, image: bytes) -> None:
        """CUZK publishes a new release of ``sheet``: the service entry and
        the dataset feed name the new year, the file entry the new date, the
        old dataset feed is gone (404) and the ZIP has a new image."""
        old = f"WRTO24.{self.years[sheet]}.{sheet}"
        new = f"WRTO24.{year}.{sheet}"
        self.service = self.service.replace(old.encode(), new.encode())
        self.etag = '"nowe-wydanie"'
        self.routes[f"{FEEDS}{old}.xml"] = lambda: recorded_response(
            ATOM / "missing_feed.html"
        )
        feed = self.feeds[sheet].replace(old.encode(), new.encode())
        feed = re.sub(
            rb"<updated>[^<]*</updated>", f"<updated>{updated}</updated>".encode(), feed
        )
        image_zip = _rezip(self.archives[sheet], old, new, image)
        self._publish(sheet, year, feed, image_zip, etag='"nowy-zip"')

    def get(self, url, timeout=None, headers=None, params=None, stream=False, **kw):
        self.calls.append(url)
        if url == SERVICE:
            if (headers or {}).get("If-None-Match") == self.etag:
                return _not_modified(self.etag)
            return _file_response(
                ORTO / "ortofoto_service.xml", self.service, ETag=self.etag
            )
        if url == KLADY:
            query: dict[str, str] = params or {}
            if "where" in query:
                sheet = query["where"].removeprefix("MAPNOM='").removesuffix("'")
                return _json_response(INDEX_RECORDS[sheet])
            assert (query["inSR"], query["outSR"]) == ("5514", "5514")
            self.envelopes.append(tuple(float(v) for v in query["geometry"].split(",")))
            return _json_response(ORTO / "klady_sm5_bbox_ctes96_ctes86.json")
        return self.routes[url]()

    def zip_requests(self) -> list[str]:
        return [url for url in self.calls if url.endswith(".zip")]


@pytest.fixture
def cuzk(monkeypatch) -> FakeCuzk:
    fake = FakeCuzk()
    monkeypatch.setattr(cz_orto, "_session", lambda: fake)
    return fake


@pytest.fixture
def cache(tmp_path):
    cache = MetadataCache(db_path=tmp_path / "cache.db")
    yield cache
    cache.close()


def test_cz_orto_sheet_files_and_sidecars(tmp_path, cuzk):
    """Four ZIP members 1:1 (no pixel conversion) as ``<sheet><suffix>`` in
    ``orto/cz_sjtsk/CTES/96``, world files committed before the image; every
    sidecar names its CRS, the release and the ZIP member."""
    report = download_data(
        product="orto", country="cz", sheet="CTES96", output_dir=tmp_path, cache=False
    )

    assert report.ok and report.failed == ()
    assert [(f.unit, f.country, f.file.status) for f in report.files] == [
        ("CTES96", "CZ", "new")
    ] * 4
    folder = tmp_path / "orto" / "cz_sjtsk" / "CTES" / "96"
    assert [f.file.path for f in report.files] == [
        folder / f"CTES96{suffix}" for suffix in SUFFIXES
    ]
    members = _members("CTES96")
    for suffix, unit_file in zip(SUFFIXES, report.files, strict=True):
        assert unit_file.file.path.read_bytes() == members[suffix]
        assert unit_file.file.version_path.parent.parent == (
            tmp_path / "orto" / "cz_sjtsk" / "versions" / "CTES" / "96"
        )
        assert unit_file.file.label == "2024_2025-02-06"
    source = {
        "url": f"{OPENZU}WRTO24.2024.CTES96.zip",
        "dataset_feed": f"{FEEDS}WRTO24.2024.CTES96.xml",
        "edition": "2024_2025-02-06",
        "year": 2024,
        "updated": "2025-02-06T14:00:09+02:00",
    }
    for suffix, unit_file in zip(SUFFIXES, report.files, strict=True):
        meta = _meta(unit_file.file)
        assert meta["dataset"] == "cz.cuzk.ortofoto"
        assert (meta["country"], meta["product"]) == ("CZ", "orto")
        assert meta["request"] == {"sheet": "CTES96"}
        assert meta["vertical_crs"] is None
        assert meta["horizontal_crs"] == WORLD_FILES.get(suffix, "EPSG:5514")
        assert meta["sha256"] == hashlib.sha256(members[suffix]).hexdigest()
        assert meta["extra"]["source"] == {
            **source,
            "member": f"WRTO24.2024.CTES96{suffix}",
        }
        assert meta["extra"]["version"] == {
            "label": "2024_2025-02-06",
            "label_source": "edition",
        }
        assert meta["extra"]["http"]["etag"] == '"ff7efbc9778db1:0"'
        assert meta["extra"]["mapname"] == "Český Těšín 9-6"
        assert meta["extra"]["cz_share"] == pytest.approx(0.99)
        assert "parent_request" not in meta["extra"]
    jpeg = _meta(report.files[3].file)
    assert jpeg["extra"]["world_files"] == WORLD_FILES
    assert "world_files" not in _meta(report.files[0].file)["extra"]


def test_cz_orto_world_files_committed_before_jpeg(tmp_path, cuzk, monkeypatch):
    """A failed commit of the image fails the sheet without a partial
    version; the world files stay and the next run adds the image."""
    real = cz_orto.emit_sidecar

    def full_disk(key, data, **kwargs):
        if data.name.endswith(".jpg"):
            raise DownloadError("brak miejsca na dysku")
        return real(key, data, **kwargs)

    monkeypatch.setattr(cz_orto, "emit_sidecar", full_disk)
    selection = {
        "product": "orto",
        "country": "cz",
        "sheet": "CTES96",
        "output_dir": tmp_path,
        "cache": False,
    }
    failed = download_data(**selection)

    assert not failed.ok and failed.files == ()
    assert [(f.unit, f.country, f.kind) for f in failed.failed] == [
        ("CTES96", "CZ", "download")
    ]
    assert "brak miejsca na dysku" in failed.failed[0].error
    folder = tmp_path / "orto" / "cz_sjtsk" / "CTES" / "96"
    assert sorted(p.name for p in folder.glob("CTES96*") if p.suffix != ".json") == [
        "CTES96.TM33N.jgw",
        "CTES96.TM34N.jgw",
        "CTES96.jgw",
    ]
    versions = tmp_path / "orto" / "cz_sjtsk" / "versions"
    assert not list(versions.rglob("CTES96.jpg"))
    assert not list(versions.glob(".incoming/*"))

    monkeypatch.setattr(cz_orto, "emit_sidecar", real)
    repaired = download_data(**selection)

    assert repaired.ok
    assert [f.file.status for f in repaired.files] == [
        "unchanged",
        "unchanged",
        "unchanged",
        "new",
    ]
    assert (folder / "CTES96.jpg").read_bytes() == _members("CTES96")[".jpg"]
    assert len(cuzk.zip_requests()) == 2


def test_cz_orto_metadata_signal(tmp_path, cuzk, cache):
    """The edition (release year + date of the feed entry) is compared without
    downloading the image; ``--upgrade`` stores the new release next to the
    old one."""
    selection = {
        "product": "orto",
        "country": "cz",
        "sheet": "CTES96",
        "output_dir": tmp_path / "dane",
        "cache": cache,
    }
    first = download_data(**selection)
    assert [f.file.status for f in first.files] == ["new"] * 4

    plan = check_data(**selection)
    assert [(i.track, i.unit, i.name, i.status) for i in plan.items] == [
        ("cz_orto", "CTES96", f"CTES96{suffix}", "current") for suffix in SUFFIXES
    ]
    again = download_data(**selection)
    assert [(f.file.status, f.file.newer) for f in again.files] == [("local", None)] * 4

    image = _members("CTES86")[".jpg"]
    cuzk.release("CTES96", "2025", "2026-03-02T08:00:00+02:00", image)
    plan = check_data(**selection)
    assert [
        (i.name, i.status, i.local_label, i.available_label) for i in plan.items
    ] == [
        (f"CTES96{suffix}", "newer", "2024_2025-02-06", "2025_2026-03-02")
        for suffix in SUFFIXES
    ]
    assert len(cuzk.zip_requests()) == 1  # checks read only the feeds

    default = download_data(**selection)
    assert [(f.file.status, f.file.newer) for f in default.files] == [
        ("local", "2025_2026-03-02")
    ] * 4
    assert len(cuzk.zip_requests()) == 1

    upgraded = download_data(**selection, update="upgrade", plan=plan)
    assert upgraded.ok and upgraded.stale == ()
    assert [(f.file.status, f.file.label) for f in upgraded.files] == [
        ("relabeled", "2025_2026-03-02"),
        ("relabeled", "2025_2026-03-02"),
        ("relabeled", "2025_2026-03-02"),
        ("new", "2025_2026-03-02"),
    ]
    assert upgraded.files[3].file.path.read_bytes() == image
    old_jpeg = first.files[3].file.version_path
    assert old_jpeg.read_bytes() == _members("CTES96")[".jpg"]
    assert _meta(upgraded.files[3].file)["extra"]["source"]["year"] == 2025
    assert len(cuzk.zip_requests()) == 2


def test_cz_orto_check_failure_reported_once_per_sheet(tmp_path, cuzk):
    """One edition lookup per sheet: a dataset feed that cannot be read is
    asked once and reported once, the four local files stay in use."""
    selection = {
        "product": "orto",
        "country": "cz",
        "sheet": "CTES96",
        "output_dir": tmp_path,
        "cache": False,
    }
    download_data(**selection)
    feed = f"{FEEDS}WRTO24.2024.CTES96.xml"
    cuzk.routes[feed] = lambda: recorded_response(ATOM / "missing_feed.html")
    cuzk.calls.clear()

    report = download_data(**selection)

    assert report.ok
    assert [f.file.status for f in report.files] == ["local"] * 4
    assert all(
        (f.file.unverified or "").startswith("check_failed: ") for f in report.files
    )
    assert [n.code for n in report.notices].count(CHECK_FAILED) == 1
    assert cuzk.calls == [SERVICE, feed]


@pytest.mark.parametrize(
    "area",
    [AREA, transform_bbox(AREA, "EPSG:4326")],
    ids=["epsg5514", "wgs84"],
)
def test_cz_orto_area_uses_sm5_index(tmp_path, cuzk, area):
    """An area is the SM5 sheets of the index, asked in EPSG:5514 (a bbox in
    another CRS through the pinned operation); four files per sheet."""
    report = download_data(
        product="orto", country="cz", bbox=area, output_dir=tmp_path, cache=False
    )

    assert report.ok
    assert [(f.unit, f.file.path.name) for f in report.files] == [
        (sheet, f"{sheet}{suffix}")
        for sheet in ("CTES86", "CTES96")
        for suffix in SUFFIXES
    ]
    (envelope,) = cuzk.envelopes
    expected = area if area.crs == "EPSG:5514" else bbox_to_crs(area, "EPSG:5514")
    assert envelope == pytest.approx(bbox_coords(expected))
    (listing,) = [n for n in report.notices if n.code == SHEET_LIST]
    assert "CTES86, CTES96" in listing.text
    for unit_file in report.files:
        assert _meta(unit_file.file)["extra"]["parent_request"] == {
            "bbox": bbox_coords(area),
            "bbox_crs": area.crs,
            "countries": ["CZ"],
        }
    assert _members("CTES86")[".jpg"] == report.files[3].file.path.read_bytes()


def test_cz_orto_area_plan_downloads_planned_sheets(tmp_path, cuzk):
    """A plan of an area executes its missing sheet only."""
    selection = {
        "product": "orto",
        "country": "cz",
        "bbox": AREA,
        "output_dir": tmp_path,
        "cache": False,
    }
    download_data(**{**selection, "bbox": None, "sheet": "CTES96", "country": None})
    plan = check_data(**selection)
    assert [(i.unit, i.status) for i in plan.items] == [("CTES86", "missing")] * 4 + [
        ("CTES96", "current")
    ] * 4

    report = download_data(**selection, update="upgrade", plan=plan)

    assert report.ok and report.stale == ()
    assert [(f.unit, f.file.status) for f in report.files] == [
        ("CTES86", "new")
    ] * 4 + [("CTES96", "local")] * 4
    assert cuzk.zip_requests() == [
        f"{OPENZU}WRTO24.2024.CTES96.zip",
        f"{OPENZU}WRTO24.2024.CTES86.zip",
    ]


@pytest.mark.parametrize(
    "operation", [download_data, check_data, validate_data_request]
)
@pytest.mark.parametrize(
    ("choice", "message"),
    [
        ({"year": 2024}, "--year dotyczy tylko PL"),
        ({"min_year": 2020}, "--min-year dotyczy tylko PL"),
        ({"max_year": 2025}, "--max-year dotyczy tylko PL"),
        ({"all_campaigns": True}, "--all-campaigns dotyczy tylko PL"),
        ({"full_sheet": True}, "--full-sheet dotyczy tylko PL"),
        ({"sheet_system": "1992"}, "--sheet-system dotyczy tylko PL"),
        ({"scale": "1:5000"}, "--scale dotyczy tylko PL"),
        ({"vertical_crs": "Bpv"}, "--vertical-crs nie dotyczy --product orto"),
        ({"resolution": "5m"}, "--resolution z --product orto dotyczy tylko wycinka"),
        ({"format": "XYZ"}, "--format nie dotyczy ortofoto CZ"),
        ({"sheet": "302_5550"}, "ortofoto CZ ma arkusze SM5 (np. CTES96, AS91)"),
        (
            {"sheet": None, "bbox": AREA, "year": 2024},
            "--year dotyczy tylko PL",
        ),
        (
            {
                "sheet": None,
                "bbox": AS91_AREA,
                "country": "auto",
                "all_campaigns": True,
            },
            "--all-campaigns dotyczy tylko PL",
        ),
    ],
)
def test_cz_orto_pl_only_flags_rejected(tmp_path, cuzk, operation, choice, message):
    """CUZK has only the current release of a sheet (archival orthophotos are
    paid): PL-only choices fail before any request, naming the flag."""
    selection = {
        "product": "orto",
        "country": "cz",
        "sheet": "CTES96",
        "output_dir": tmp_path,
        **choice,
    }
    if operation is not validate_data_request:
        selection["cache"] = False
    with pytest.raises(ValidationError) as error:
        operation(**selection)
    assert str(error.value).startswith(message)
    assert cuzk.calls == []


def test_auto_orto_both_countries(tmp_path, cuzk):
    """A border area: PL sheets (with the PL-only choices) and CZ SM5 sheets
    under one ``parent_request`` - no narrowing to PL any more."""
    with patch(
        "kartograf.download.data._download_pl_sheet_list", return_value=0
    ) as pl_sheets:
        report = download_data(
            product="orto",
            country="auto",
            bbox=AREA,
            sheet_system="1992",
            all_campaigns=True,
            output_dir=tmp_path,
            cache=False,
        )

    assert report.ok
    assert AUTO_NARROWED_TO_PL not in [n.code for n in report.notices]
    pl_task, _run, pl_list, pl_parent = pl_sheets.call_args.args
    assert pl_list == find_sheets_for_bbox(
        bbox_to_2180(AREA), "1:10000", sheet_system="1992"
    )
    assert pl_list and pl_task.all_campaigns is True
    assert [(f.unit, f.country) for f in report.files] == [("CTES86", "CZ")] * 4 + [
        ("CTES96", "CZ")
    ] * 4
    parent = {
        "bbox": bbox_coords(AREA),
        "bbox_crs": "EPSG:5514",
        "countries": ["CZ", "PL"],
    }
    assert pl_parent == parent
    assert _meta(report.files[0].file)["extra"]["parent_request"] == parent


def test_two_letter_sm5_sheet(tmp_path, cuzk):
    """As sheets (2 letters): the code alone selects CZ, the hierarchy is AS/91."""
    report = download_data(
        product="orto", sheet="AS91", output_dir=tmp_path, cache=False
    )

    assert report.ok
    folder = tmp_path / "orto" / "cz_sjtsk" / "AS" / "91"
    assert [f.file.path for f in report.files] == [
        folder / f"AS91{suffix}" for suffix in SUFFIXES
    ]
    assert {f.file.label for f in report.files} == {"2025_2026-02-24"}
    assert (folder / "AS91.jpg").read_bytes() == _members("AS91")[".jpg"]
    assert _meta(report.files[3].file)["extra"]["mapname"] == "Aš 9-1"
