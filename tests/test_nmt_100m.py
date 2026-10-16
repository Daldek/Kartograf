"""NMT 100 m: the voivodeship files of the GUGiK ATOM feed (plan E, E1).

Fixtures ``tests/fixtures/pl/nmt_100m`` (recorded 2026-10-16, README there):
the service feed (16 voivodeships, ``http://`` links), the dataset feeds of
voivodeships 12 and 24, the PRG powiats of three areas and the head of the
XYZ member of the file of voivodeship 12. The file bodies are small ZIPs
built with the recorded member name (the real file is 7.6 MB).
"""

import dataclasses
import io
import json
import zipfile
from pathlib import Path

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.data import check_data, download_data
from kartograf.exceptions import ValidationError
from kartograf.notices import DOWNLOAD_SIZE, UNIT_LIST, WHOLE_COUNTRY_SIZE
from kartograf.providers.pl.prg import PRG_WFS_ENDPOINT
from kartograf.sources.descriptor import AtomFilesParams
from kartograf.sources.registry import get_source
from kartograf.transport.atom import resolve_atom_file
from tests.conftest import recorded_response
from tests.fake_packages import FakeResponse

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "nmt_100m"
RECORDED = json.loads((FIXTURES / "files.json").read_text(encoding="utf-8"))[
    "nmt100_12"
]
HOST = "mapy.geoportal.gov.pl/wss/service/ATOM/httpauth"
SERVICE = f"https://{HOST}/atom/GUGIK_NMT100"
DATASET = (
    f"https://{HOST}/atom/GUGIK_NMT100?spatial_dataset_identifier_code=NMT100_{{woj}}"
    "&spatial_dataset_identifier_namespace=PL.PZGiK.205"
)
FILES = {
    "12": RECORDED["url"],
    "24": (
        f"https://{HOST}/download/?fileId=e2affa3627951eb6299337e1cd011c3f"
        "&name=slaskie_grid100.zip"
    ),
}
# EPSG:2180 areas of the recorded PRG answers (README): the centre of Krakow
# (powiat 1261), the 12/24 border at Jaworzno (1203, 2468) and the extent of
# sheet M-34-63-B-b (1212, 2401, 2465).
KRAKOW = BBox(564000, 241000, 570000, 247000, "EPSG:2180")
BORDER = BBox(523000, 253000, 528000, 258000, "EPSG:2180")
SHEET = "M-34-63-B-b"
PRG = {
    "241000,564000,247000,570000": "prg_krakow.xml",
    "253000,523000,258000,528000": "prg_border_12_24.xml",
    "264824.098,526680.833,274139.407,535636.597": "prg_sheet_M-34-63-B-b.xml",
}
CHOICE = {"product": "nmt", "resolution": "100m", "cache": False}


def _zip_12() -> bytes:
    """The file of voivodeship 12: its one XYZ member (recorded name, head)."""
    ((name, _size),) = RECORDED["members"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, RECORDED["member_head"].encode("utf-8"))
    return buffer.getvalue()


class FakeGugik:
    """``requests.Session`` stand-in of PRG and the NMT 100 m feeds (https
    only: the ``http://`` links of the feeds must be followed over https);
    ``calls`` = every GET URL in order; an unknown URL fails the test."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.body = _zip_12()

    def _dataset(self, woj: str):
        feed = (FIXTURES / f"dataset_{woj}.xml").read_bytes()
        if woj == "12":  # the feed `length` of the small ZIP the test serves
            feed = feed.replace(
                b'length="7619580"', f'length="{len(self.body)}"'.encode()
            )
        return recorded_response(FIXTURES / f"dataset_{woj}.xml", body=feed)

    def get(self, url, params=None, timeout=None, headers=None, stream=False):
        self.calls.append(url)
        if url == PRG_WFS_ENDPOINT:
            bbox = params["BBOX"].removesuffix(",urn:ogc:def:crs:EPSG::2180")
            return recorded_response(FIXTURES / PRG[bbox])
        if url == SERVICE:
            return recorded_response(FIXTURES / "service_feed.xml")
        for woj in ("12", "24"):
            if url == DATASET.format(woj=woj):
                return self._dataset(woj)
        if url == FILES["12"]:
            headers = {"Content-Type": "application/zip"}
            return FakeResponse(
                200, {**headers, "Content-Length": str(len(self.body))}, self.body
            )
        raise AssertionError(f"Nieoczekiwane zapytanie: {url}")

    def head(self, url, **kwargs):
        raise AssertionError(f"HEAD niepotrzebny (rozmiar z feedu): {url}")

    def file_gets(self) -> int:
        return sum(1 for url in self.calls if url in FILES.values())


@pytest.fixture
def gugik(monkeypatch) -> FakeGugik:
    fake = FakeGugik()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("area", "units"),
    [
        ({"bbox": KRAKOW, "country": "pl"}, ["12"]),
        ({"bbox": BORDER, "country": "pl"}, ["12", "24"]),
        ({"sheet": SHEET}, ["12", "24"]),
    ],
)
def test_area_selects_voivodeships(tmp_path, gugik, area, units):
    """The files of an area are its voivodeships (the first two digits of
    its PRG powiats): Krakow lies in 12 only, the Jaworzno border and the
    sheet M-34-63-B-b reach 12 and 24; the plan reads no file."""
    notices = []
    plan = check_data(output_dir=tmp_path, on_notice=notices.append, **CHOICE, **area)

    assert [item.unit for item in plan.items] == units
    assert {item.status for item in plan.items} == {"missing"}
    assert {item.track for item in plan.items} == {"collection"}
    assert [n.code for n in notices] == [UNIT_LIST]
    assert notices[0].text.startswith(f"nmt: wojewodztwa obszaru wg PRG ({len(units)})")
    assert "12 (malopolskie)" in notices[0].text
    assert gugik.file_gets() == 0


def test_zip_kept_with_txt(tmp_path, gugik, frozen_clock):
    """The file of a voivodeship is stored as published (ZIP with one XYZ
    text); the sidecar has no height system and says why, the source feeds
    and the size of the feed, and the area of the request."""
    notices = []
    report = download_data(
        output_dir=tmp_path,
        bbox=KRAKOW,
        country="pl",
        on_notice=notices.append,
        **CHOICE,
    )

    assert report.ok
    (unit_file,) = report.files
    assert (unit_file.unit, unit_file.country) == ("12", "PL")
    path = unit_file.file.path
    assert path == tmp_path / "nmt/pl_1992_100m/teryt/12.zip"
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == [RECORDED["members"][0][0]]
    meta = _meta(unit_file.file.version_path)
    assert meta["dataset"] == "pl.gugik.nmt_100m"
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:2180", None)
    assert meta["resolution"] == "100m"
    assert meta["request"] == {"teryt": "12", "resolution": "100m"}
    assert "GUGiK nie deklaruje ukladu wysokosci" in meta["extra"]["vertical_crs_note"]
    assert meta["extra"]["source"] == {
        "url": FILES["12"],
        "service_feed": SERVICE,
        "dataset_feed": DATASET.format(woj="12"),
        "dataset": "12",
        "edition": "2019-05-14",
        "updated": "2019-05-14T00:00:00Z",
        "length": len(gugik.body),
    }
    assert meta["extra"]["parent_request"]["countries"] == ["PL"]
    # a 7.6 MB voivodeship file is neither a national file nor a large one
    assert not {WHOLE_COUNTRY_SIZE, DOWNLOAD_SIZE} & {n.code for n in notices}


def test_edition_label_from_entry(tmp_path, gugik, frozen_clock):
    """The version label is the ``updated`` of the file entry of the dataset
    feed; a second run and ``check_data`` read only the feeds."""
    first = download_data(output_dir=tmp_path, bbox=KRAKOW, country="pl", **CHOICE)
    (unit_file,) = first.files
    assert (unit_file.file.status, unit_file.file.label) == ("new", "2019-05-14")
    assert (
        _meta(unit_file.file.version_path)["extra"]["version"]["label_source"]
        == "edition"
    )

    again = download_data(output_dir=tmp_path, bbox=KRAKOW, country="pl", **CHOICE)
    assert [f.file.status for f in again.files] == ["local"]
    (item,) = check_data(output_dir=tmp_path, bbox=KRAKOW, country="pl", **CHOICE).items
    assert (item.status, item.local_label, item.available_label) == (
        "current",
        "2019-05-14",
        "2019-05-14",
    )
    assert gugik.file_gets() == 1


def test_https_for_gugik_atom(tmp_path, gugik, frozen_clock):
    """The feeds link the dataset feed and the file with ``http://``; the
    channel parameter ``force_https`` asks them over https of the same host,
    a channel without it follows the links as published."""
    assert RECORDED["feed_href"].startswith("http://")
    assert RECORDED["url"] == "https://" + RECORDED["feed_href"].removeprefix("http://")
    download_data(output_dir=tmp_path, bbox=KRAKOW, country="pl", **CHOICE)
    atom = [url for url in gugik.calls if url != PRG_WFS_ENDPOINT]
    assert atom == [SERVICE, DATASET.format(woj="12"), FILES["12"]]

    params = get_source("pl.gugik.nmt_100m").channels[0].params
    assert isinstance(params, AtomFilesParams)
    plain = dataclasses.replace(params, force_https=False)
    with pytest.raises(AssertionError, match="Nieoczekiwane zapytanie: http://"):
        resolve_atom_file(gugik, plain, key="12", crs=None, cache=None)


@pytest.mark.parametrize(
    ("flags", "flag"),
    [
        ({"sheet_system": "1992"}, "--sheet-system"),
        ({"scale": "1:10000"}, "--scale"),
        ({"year": 2019}, "--year"),
        ({"min_year": 2019}, "--min-year"),
        ({"max_year": 2019}, "--max-year"),
        ({"all_campaigns": True}, "--all-campaigns"),
        ({"full_sheet": True}, "--full-sheet"),
        ({"cutout": True, "horizontal_crs": "EPSG:2180"}, "--cutout"),
        ({"horizontal_crs": "EPSG:2180"}, "--horizontal-crs"),
        ({"min_density": 4}, "--min-density"),
        ({"country": "cz"}, "--country cz"),
    ],
)
def test_100m_rejects_sheet_flags(tmp_path, gugik, flags, flag):
    choice = {"bbox": KRAKOW, "country": "pl", **flags}
    with pytest.raises(ValidationError) as error:
        download_data(output_dir=tmp_path, **CHOICE, **choice)
    assert str(error.value).startswith(f"{flag} nie dotyczy --resolution 100m")
    assert str(error.value).endswith(
        "NMT 100 m to pliki wojewodztw z ATOM - bez arkuszy, lotow i wycinka"
    )
    assert gugik.calls == []


def test_100m_has_no_height_system(tmp_path, gugik):
    """Decision P1: GUGiK declares no height system - ``--vertical-crs`` is
    an error, ``--format XYZ`` (the only format of the files) may be given,
    another archive format is not the 100 m variant."""
    with pytest.raises(ValidationError, match="uklad wysokosci nieznany"):
        download_data(
            output_dir=tmp_path,
            bbox=KRAKOW,
            country="pl",
            vertical_crs="EVRF2007",
            **CHOICE,
        )
    with pytest.raises(ValidationError, match="nie ma rozdzielczosci 100m dla NMT TBD"):
        download_data(
            output_dir=tmp_path, bbox=KRAKOW, country="pl", format="TBD", **CHOICE
        )
    assert gugik.calls == []
    plan = check_data(
        output_dir=tmp_path, bbox=KRAKOW, country="pl", format="XYZ", **CHOICE
    )
    assert [item.unit for item in plan.items] == ["12"]
