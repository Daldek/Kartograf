"""Mesh 3D and 3D trees of GUGiK (plan E, E5) on recorded answers.

Mesh 3D: the WFS index ``ModeleSiatkowe3D`` (two pages of the E0 fixture,
one page of 122 records of Krakow) - a tile is the file of its record (the
field ``modul`` names tiles of several works). Trees: the powiat packages of
the 2023 release (``HEAD`` of 0.3-25 GB, 404 of a powiat without a
package, the PRG answer of an area of two powiats). Package bodies are built
from the recorded member names (``tests/fixtures/pl/{mesh_3d,trees_3d}``).
"""

import functools
import gzip
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    VOLUME_FILES,
    VOLUME_SAMPLE,
    check_collection,
    download_collection,
)
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.notices import DOWNLOAD_SIZE, UNIT_LIST
from tests.fake_packages import zip_bytes
from tests.test_collections_units import (
    INDEX,
    MESH_AREA,
    MESH_WFS,
    Response,
    Router,
    _key,
    _meta,
    recorded,
)

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent / "fixtures" / "pl"
MESH = FIXTURES / "mesh_3d" / "real_2026_10_16"
TREES = FIXTURES / "trees_3d" / "real_2026_10_16"
MESH_FILES: dict = json.loads((MESH / "files.json").read_text(encoding="utf-8"))
TREES_FILES: dict = json.loads((TREES / "files.json").read_text(encoding="utf-8"))
# The four tiles of the E0 pages (two records each) and the 122 of Krakow.
TILES = ("74228_55480", "74228_55482", "74230_55480", "74230_55482")
KRAKOW_122 = BBox(566000, 244000, 568000, 246000, "EPSG:2180")
# Area of the powiats 0202 (a package of 3.5 GB) and 0224 (no package: 404).
TREES_AREA = BBox(334000, 310000, 337000, 313000, "EPSG:2180")
LABEL = "2021-10-03_DFT.7201.043.2023"


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _zip_answer(body: bytes, headers: dict | None = None) -> Response:
    sent = {"Content-Type": "application/octet-stream", **(headers or {})}
    return Response(200, {**sent, "Content-Length": str(len(body))}, body)


def _tile_members(tile: str) -> list[str]:
    """The recorded members of one tile ZIP, named after ``tile`` (the
    other tiles of the page have the same shape)."""
    recorded_members = MESH_FILES["tile_74230_55482"]["members"]
    return [name.replace("74230_55482", tile) for name in recorded_members]


def _serve_pages(router: Router, monkeypatch, second: bytes | None = None) -> None:
    """The two WFS pages of ``MESH_AREA`` (``COUNT=2``, ``next``); ``second``
    replaces the body of the second page."""
    monkeypatch.setattr("kartograf.providers.pl.skorowidz_wfs.PAGE_SIZE", 2)
    first = (INDEX / "mesh_p1.xml").read_bytes()
    router.add(
        MESH_WFS,
        lambda: recorded(INDEX / "mesh_p1.xml"),
        {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": "gugik:SkorowidzModeleSiatkowe3D",
            "SRSNAME": "urn:ogc:def:crs:EPSG::2180",
            "BBOX": "244500.0,566100.0,244700.0,566300.0,urn:ogc:def:crs:EPSG::2180",
            "COUNT": "2",
        },
    )
    following = (
        first.split(b'next="', 1)[1].split(b'"', 1)[0].decode().replace("&amp;", "&")
    )
    router.add(following, lambda: recorded(INDEX / "mesh_p2.xml", second))


def _serve_tiles(router: Router) -> dict[str, bytes]:
    """The ZIP of each tile of the E0 pages (``GET``) and its recorded size
    (``HEAD``); file name stem -> served body."""
    bodies: dict[str, bytes] = {}
    for tile in TILES:
        entry = MESH_FILES[f"tile_{tile}"]
        body = zip_bytes(_tile_members(tile))
        router.add(entry["url"], functools.partial(_zip_answer, body))
        router.heads[_key(entry["url"])] = entry["headers"]
        bodies[entry["url"].rsplit("/", 1)[1].removesuffix(".zip")] = body
    return bodies


def _mesh(tmp_path, **choice):
    return {
        "product": "mesh",
        "country": "pl",
        "bbox": MESH_AREA,
        "output_dir": tmp_path,
        "cache": False,
        **choice,
    }


def test_mesh_tiles_from_bbox(tmp_path, router, monkeypatch):
    """The tiles of an area are the files of the index records (two pages):
    each ZIP (OBJ, MTL, JPG) stored 1:1 in the directory of the record's
    CRS, labelled by the record; a check compares the records and asks for
    no file."""
    _serve_pages(router, monkeypatch)
    bodies = _serve_tiles(router)
    notices = []
    report = download_collection(**_mesh(tmp_path), on_notice=notices.append)
    assert report.ok, report.failed
    assert sorted(item.unit for item in report.files) == [
        f"2000/7/{name}" for name in sorted(bodies)
    ]
    units = [n.text for n in notices if n.code == UNIT_LIST]
    assert len(units) == 1 and "kafle obszaru (4)" in units[0]
    item = next(f for f in report.files if f.unit == "2000/7/78944_6777_74230_55482")
    path = item.file.path
    assert path == tmp_path / "models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip"
    assert path.read_bytes() == bodies["78944_6777_74230_55482"]
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == _tile_members("74230_55482")
    meta = _meta(item.file.version_path)
    assert meta["dataset"] == "pl.gugik.mesh"
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:2178", "EPSG:9651")
    assert meta["request"] == {"tile": "2000/7/78944_6777_74230_55482"}
    assert meta["extra"]["version"]["label"] == LABEL
    assert meta["extra"]["source"]["record"]["modul"] == "74230_55482"

    gets = router.gets("https://opendata.geoportal.gov.pl/")
    plan = check_collection(**_mesh(tmp_path))
    assert {(i.status, i.available_label) for i in plan.items} == {("current", LABEL)}
    assert router.gets("https://opendata.geoportal.gov.pl/") == gets


def test_mesh_area_again_without_network_uses_cached_index(tmp_path, monkeypatch):
    """The index records of an area are kept in the metadata cache: the same
    area again with local tiles asks no service (offline run); the check
    asks the index again."""
    from kartograf.cache.metadata import MetadataCache

    online = Router()
    monkeypatch.setattr(col, "_session", lambda: online)
    _serve_pages(online, monkeypatch)
    _serve_tiles(online)
    cache = MetadataCache(tmp_path / "cache.db")
    choice = {**_mesh(tmp_path / "out"), "cache": cache}
    assert download_collection(**choice).ok

    offline = Router()  # every request is an AssertionError
    monkeypatch.setattr(col, "_session", lambda: offline)
    again = download_collection(**choice)
    assert again.ok and offline.calls == []
    assert {item.file.status for item in again.files} == {"local"}
    with pytest.raises(AssertionError, match="Nieoczekiwane zapytanie"):
        check_collection(**choice)


def _second_work(page: bytes) -> bytes:
    """The second page with its first record moved to another work of a
    later year over the tile ``74230_55482`` of page one (the index names
    tiles of several works with one ``modul``, measured 2026-10-16)."""
    first = page.split(b"<wfs:member>", 1)[1].split(b"</wfs:member>", 1)[0]
    changed = (
        first.replace(
            b"78944/78944_6953_74230_55480.zip", b"80412/80412_15_74230_55482.zip"
        )
        .replace(b"<gugik:modul>74230_55480<", b"<gugik:modul>74230_55482<")
        .replace(b"<gugik:akt_rok>2021<", b"<gugik:akt_rok>2023<")
        .replace(b"<gugik:Aktualnosc>2021-10-03<", b"<gugik:Aktualnosc>2023-05-14<")
    )
    assert changed != first
    return page.replace(first, changed, 1)


def test_mesh_tile_of_two_works_and_year(tmp_path, router, monkeypatch):
    """Two works over one ``modul`` are two files (a tile = the file of its
    record, no 'newest record' between works); ``year`` keeps the records
    of that year; a year without records names the years of the index."""
    page = (INDEX / "mesh_p2.xml").read_bytes()
    _serve_pages(router, monkeypatch, _second_work(page))
    plan = check_collection(**_mesh(tmp_path))
    assert sorted(i.unit for i in plan.items) == [
        "2000/7/78944_6776_74228_55482",
        "2000/7/78944_6777_74230_55482",
        "2000/7/78944_6952_74228_55480",
        "2000/7/80412_15_74230_55482",
    ]
    (later,) = check_collection(**_mesh(tmp_path, year=2023)).items
    assert (later.unit, later.available_label) == (
        "2000/7/80412_15_74230_55482",
        "2023-05-14_DFT.7201.043.2023",
    )
    with pytest.raises(NoCoverageError) as missing:
        check_collection(**_mesh(tmp_path, year=2020))
    assert "lata w indeksie: 2021, 2023" in str(missing.value)


def _serve_krakow(router: Router) -> list[str]:
    """The recorded page of 122 records (``COUNT=1000``) and the ``HEAD`` of
    every tile; the tile URLs in the order of the page."""
    area = MESH_FILES["area_122"]
    meta = json.loads((MESH / "wfs_122_p0.xml.headers.json").read_text())
    body = gzip.decompress((MESH / area["wfs"]).read_bytes())
    headers = {"Content-Type": meta["Content-Type"]}
    router.add(meta["url"], lambda: Response(200, headers, body))
    for url, length in area["content_length"].items():
        router.heads[_key(url)] = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(length),
        }
    return re.findall(r"<gugik:URL_do_pobrania>([^<]+)<", body.decode())


def test_mesh_city_area_over_the_file_limit(tmp_path, router):
    """122 tiles of Krakow (5.7 GB) exceed the file limit of one request: a
    ``ValidationError`` with the number and the size estimated from
    ``VOLUME_SAMPLE`` real ``HEAD`` answers, before any tile transfer; the
    check of the same area lists every tile."""
    urls = _serve_krakow(router)
    assert len(urls) == 122 > VOLUME_FILES
    with pytest.raises(ValidationError) as refused:
        download_collection(**_mesh(tmp_path, bbox=KRAKOW_122))
    text = str(refused.value)
    assert "122 pliki do pobrania" in text and "limit" in text
    heads = [url for method, url in router.calls if method == "HEAD"]
    assert len(heads) == VOLUME_SAMPLE
    sizes = MESH_FILES["area_122"]["content_length"]
    estimate = sum(sizes[url] for url in heads) * 122 // VOLUME_SAMPLE
    whole, tenth = divmod(round(estimate / 10**8), 10)
    assert f"szacunkowo ok. {whole},{tenth} GB" in text
    assert router.gets("https://opendata.geoportal.gov.pl/") == 0
    assert not list(tmp_path.rglob("*.zip"))

    plan = check_collection(**_mesh(tmp_path, bbox=KRAKOW_122))
    assert len(plan.items) == 122
    assert {i.status for i in plan.items} == {"missing"}


# --- trees ------------------------------------------------------------------------


class _Streamed:
    """A transfer whose body exists only as a stream of chunks: reading it
    whole (``content``) fails the test."""

    status_code = 200

    def __init__(self, headers: dict, body: bytes) -> None:
        self.headers = {**headers, "Content-Length": str(len(body))}
        self._body = body
        self.chunks = 0

    @property
    def content(self) -> bytes:
        raise AssertionError("cialo pobrania odczytane w calosci zamiast strumienia")

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1):
        for start in range(0, len(self._body), chunk_size):
            self.chunks += 1
            yield self._body[start : start + chunk_size]


def _gml_package(members: list[str], payload: int = 0) -> bytes:
    """A stored (not compressed) ZIP of ``members`` with ``payload`` bytes
    in the first one - larger than one transfer chunk."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for i, name in enumerate(members):
            archive.writestr(
                name, (b"<CityModel/>" * (payload // 12)) if i == 0 else b""
            )
    return buffer.getvalue()


def test_trees_size_notice_and_stream(tmp_path, router):
    """A powiat package over 100 MiB is announced with its ``HEAD`` size
    before its transfer, streamed in chunks to the staging file (never held
    whole), checked as a ZIP on disk and stored 1:1 in the segment of the
    only release; another LoD or year is an input error naming it."""
    entry = TREES_FILES["trees_3063"]
    body = _gml_package(entry["members"], payload=3 * 1_048_576)
    transfer = _Streamed(entry["headers"], body)
    router.add(entry["url"], lambda: transfer)
    router.heads[_key(entry["url"])] = entry["headers"]
    seen: list[tuple[str, int]] = []
    report = download_collection(
        product="trees",
        teryt="3063",
        output_dir=tmp_path,
        cache=False,
        on_notice=lambda n: seen.append((n.code, router.gets(entry["url"]))),
    )
    assert report.ok, report.failed
    assert seen == [(DOWNLOAD_SIZE, 0)]
    (size,) = [n.text for n in report.notices if n.code == DOWNLOAD_SIZE]
    assert "324674789 B" in size and entry["url"] in size
    assert transfer.chunks > 1
    (item,) = report.files
    assert item.file.path == tmp_path / "models3d/pl_trees_lod1_2023/teryt/3063.zip"
    assert item.file.path.read_bytes() == body
    meta = _meta(item.file.version_path)
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:2180", None)
    assert meta["request"] == {"teryt": "3063"}
    assert meta["extra"]["version"]["label"] == "2023"

    for choice, allowed in (({"lod": 2}, "dostepne: 1"), ({"year": 2024}, "2023")):
        with pytest.raises(ValidationError) as error:
            download_collection(
                product="trees",
                teryt="3063",
                output_dir=tmp_path,
                cache=False,
                **choice,
            )
        assert allowed in str(error.value)


def test_trees_package_without_gml_is_not_data(tmp_path, router):
    """A package without CityGML members is refused; no version is kept."""
    entry = TREES_FILES["trees_3063"]
    body = zip_bytes(["3063_opis.txt"])
    router.add(entry["url"], lambda: _zip_answer(body))
    report = download_collection(
        product="trees", teryt="3063", output_dir=tmp_path, cache=False
    )
    (failure,) = report.failed
    assert (failure.unit, failure.kind) == ("3063", "download")
    assert ".gml" in failure.error
    assert not list(tmp_path.rglob("*.zip"))


def test_trees_unit_failure_isolated(tmp_path, router):
    """An area of two powiats: 0224 has no package (404) - its failure does
    not stop 0202, and no version is kept for it."""
    router.add_recorded(TREES / "prg_powiaty_0202_0224.xml")
    found = TREES_FILES["trees_0202"]
    missing = TREES_FILES["trees_0224"]
    sheets = [name.split("_", 1)[1] for name in TREES_FILES["trees_3063"]["members"]]
    body = zip_bytes([f"0202_{sheet}" for sheet in sheets[:3]])
    router.add(found["url"], lambda: _zip_answer(body))
    router.heads[_key(found["url"])] = found["headers"]
    router.add(missing["url"], lambda: Response(404, missing["headers"], b"<html/>"))
    report = download_collection(
        product="trees", country="pl", bbox=TREES_AREA, output_dir=tmp_path, cache=False
    )
    assert not report.ok
    assert [item.unit for item in report.files] == ["0202"]
    (failure,) = report.failed
    assert (failure.unit, failure.kind) == ("0224", "no_coverage")
    assert [n.code for n in report.notices].count(DOWNLOAD_SIZE) == 1
    assert not list((tmp_path / "models3d").rglob("0224*"))


def test_trees_powiat_choice_has_no_volume_limit(tmp_path, router):
    """``--teryt`` names its file: the 24.7 GB package of 0208 is downloaded
    after its size notice (the volume limit is for areas only)."""
    entry = TREES_FILES["trees_0208"]
    body = zip_bytes(["0208_M-34-1-A-a-1-1-1.gml"])
    router.add(entry["url"], lambda: _zip_answer(body))
    router.heads[_key(entry["url"])] = entry["headers"]
    report = download_collection(
        product="trees", teryt="0208", output_dir=tmp_path, cache=False
    )
    assert report.ok, report.failed
    (size,) = [n.text for n in report.notices if n.code == DOWNLOAD_SIZE]
    assert "24707968358 B" in size
    assert report.files[0].file.path.name == "0208.zip"
