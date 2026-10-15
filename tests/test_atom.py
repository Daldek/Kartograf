"""Engine ``atom_files`` (ADR-042 D12) on real CUZK ATOM feeds.

Fixtures ``tests/fixtures/cz/atom`` (recorded 2026-10-15, README there): the
ORTOFOTO service feed trimmed to three real entries (BENE09 2025, AS91
2025, CTES96 2024), the dataset feeds of CTES96 and AS91, the ZABAGED-GPKG
service feed (one dataset, CRS categories 3045 and 5514) and its dataset
feed (one file per CRS), the HTML page of the ATOM host and its 404 page.
"""

import io
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.sources.descriptor import AtomFilesParams
from kartograf.transport.atom import (
    atom_index,
    atom_segment_tokens,
    fetch_atom_file,
    resolve_atom_file,
    unpack_members,
)
from tests.conftest import recorded_response

FIXTURES = Path(__file__).parent / "fixtures" / "cz" / "atom"

ORTO_SERVICE = "https://atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml"
ORTO_FEEDS = "https://atom.cuzk.gov.cz/ORTOFOTO/datasetFeeds/CZ-00025712-CUZK_ORTOFOTO"
CTES96_FEED = f"{ORTO_FEEDS}_WRTO24.2024.CTES96.xml"
AS91_FEED = f"{ORTO_FEEDS}_WRTO24.2025.AS91.xml"
ORTO = AtomFilesParams(
    service_feed=ORTO_SERVICE,
    entry_pattern=r"ORTOFOTO_WRTO24\.(?P<year>[0-9]{4})\.(?P<sheet>[A-Z]{2,4}[0-9]{2})\.xml$",
    members=(
        (".jpg", ".jpg"),
        (".jgw", ".jgw"),
        (".TM33N.jgw", ".TM33N.jgw"),
        (".TM34N.jgw", ".TM34N.jgw"),
    ),
)
ZABAGED_SERVICE = "https://atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml"
ZABAGED_FEED = "https://atom.cuzk.gov.cz/ZABAGED-GPKG/datasetFeeds/CZ-00025712-CUZK_ZABAGED-GPKG_1.xml"
ZABAGED = AtomFilesParams(
    service_feed=ZABAGED_SERVICE,
    entry_pattern=r"ZABAGED-GPKG_1\.xml$",
    crs=("EPSG:5514", "EPSG:3045"),
    segment_tokens=("gpkg",),
)
ROUTES: dict[str, Any] = {
    ORTO_SERVICE: "ortofoto_service.xml",
    CTES96_FEED: "ortofoto_ctes96.xml",
    AS91_FEED: "ortofoto_as91.xml",
    ZABAGED_SERVICE: "zabaged_service.xml",
    ZABAGED_FEED: "zabaged_dataset.xml",
}


def answer(name: str, *, body: bytes | None = None):
    return recorded_response(FIXTURES / name, body=body)


def not_modified():
    response = Mock()
    response.status_code = 304
    response.headers = {"ETag": '"64a6104edbc8dc1:0"'}
    response.content = b""
    return response


class FakeService:
    """``requests.Session`` stand-in: ``routes`` = URL -> fixture name or a
    response factory; ``calls`` = ``(url, If-None-Match)`` of every GET."""

    def __init__(self, routes: dict | None = None) -> None:
        self.routes: dict[str, Any] = dict(ROUTES if routes is None else routes)
        self.calls: list[tuple[str, str | None]] = []

    def get(self, url, timeout=None, headers=None, **kwargs):
        self.calls.append((url, (headers or {}).get("If-None-Match")))
        reply = self.routes[url]
        return answer(reply) if isinstance(reply, str) else reply()

    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


@pytest.fixture
def cache(tmp_path):
    cache = MetadataCache(db_path=tmp_path / "cache.db")
    yield cache
    cache.close()


def test_index_maps_sheet_to_dataset_feed():
    """The ``sheet`` group keys the index (also the 2-letter As sheet);
    ``year`` and ``updated`` come from the entry; a dataset feed id outside
    ``entry_pattern`` is not part of the channel."""
    index = atom_index(FakeService(), ORTO, cache=None)

    assert sorted(index) == ["AS91", "BENE09", "CTES96"]
    ctes = index["CTES96"]
    assert ctes.dataset_feed == CTES96_FEED
    assert dict(ctes.groups) == {"year": "2024", "sheet": "CTES96"}
    assert ctes.updated == "2025-02-06T14:00:09+02:00"
    assert ctes.crs == ("EPSG:5514",)
    assert index["AS91"].groups["year"] == "2025"
    only_2025 = AtomFilesParams(
        service_feed=ORTO_SERVICE,
        entry_pattern=r"WRTO24\.2025\.(?P<sheet>[A-Z]{2,4}[0-9]{2})\.xml$",
    )
    assert sorted(atom_index(FakeService(), only_2025, cache=None)) == [
        "AS91",
        "BENE09",
    ]


def test_dataset_feed_link_and_length():
    service = FakeService()
    file = resolve_atom_file(service, ORTO, key="CTES96", crs=None, cache=None)

    # the dataset feed of 2025-02 still names the old host openzu.cuzk.cz
    assert file.url == "https://openzu.cuzk.cz/opendata/ORTOFOTO/WRTO24.2024.CTES96.zip"
    assert file.length == 63870664
    assert file.dataset_feed == CTES96_FEED
    assert file.crs == "EPSG:5514"
    assert service.urls() == [ORTO_SERVICE, CTES96_FEED]


@pytest.mark.parametrize(
    "edit, message",
    [
        (lambda xml: xml.replace(b'rel="alternate"', b'rel="related"'), "0 linkow"),
        (
            lambda xml: xml.replace(
                b"<category",
                b'<link href="https://x/y.zip" rel="alternate" /><category',
            ),
            "2 linkow",
        ),
    ],
)
def test_entry_without_one_file_link_is_download_error(edit, message):
    body = edit((FIXTURES / "ortofoto_ctes96.xml").read_bytes())
    service = FakeService(
        {**ROUTES, CTES96_FEED: lambda: answer("ortofoto_ctes96.xml", body=body)}
    )
    with pytest.raises(DownloadError, match=message):
        resolve_atom_file(service, ORTO, key="CTES96", crs=None, cache=None)


def test_crs_category_selects_file():
    """ZABAGED: one dataset, a file per CRS category; the choice is required
    and checked before any request."""
    files = {
        crs: resolve_atom_file(FakeService(), ZABAGED, key="", crs=crs, cache=None)
        for crs in ("EPSG:5514", "EPSG:3045")
    }
    assert files["EPSG:5514"].url.endswith("/epsg-5514/ZABAGED-5514-gpkg-20261004.zip")
    assert files["EPSG:5514"].length == 5805826649
    assert files["EPSG:3045"].url.endswith("/epsg-3045/ZABAGED-3045-gpkg-20261004.zip")
    assert files["EPSG:3045"].length == 6742892709
    assert atom_segment_tokens(ZABAGED, "EPSG:5514") == ("gpkg", "5514")
    assert atom_segment_tokens(ORTO, None) == ()

    service = FakeService()
    with pytest.raises(ValidationError, match="EPSG:5514, EPSG:3045"):
        resolve_atom_file(service, ZABAGED, key="", crs=None, cache=None)
    with pytest.raises(ValidationError, match="dostepne: EPSG:5514, EPSG:3045"):
        resolve_atom_file(service, ZABAGED, key="", crs="EPSG:2180", cache=None)
    with pytest.raises(ValidationError, match="jeden plik"):
        resolve_atom_file(service, ORTO, key="CTES96", crs="EPSG:5514", cache=None)
    assert service.calls == []


def test_crs_missing_from_dataset_feed_is_download_error():
    """The channel declares 3045, the feed (source changed) has no such file."""
    body = (FIXTURES / "zabaged_dataset.xml").read_bytes()
    body = body.replace(b"/0/3045", b"/0/32633")
    service = FakeService(
        {**ROUTES, ZABAGED_FEED: lambda: answer("zabaged_dataset.xml", body=body)}
    )
    with pytest.raises(DownloadError, match="EPSG:32633, EPSG:5514"):
        resolve_atom_file(service, ZABAGED, key="", crs="EPSG:3045", cache=None)


def test_edition_label():
    """The release of a file: the ``year`` group and the date of the file
    entry (ORTOFOTO) or the date alone (ZABAGED, both CRSs on one day)."""
    ctes = resolve_atom_file(FakeService(), ORTO, key="CTES96", crs=None, cache=None)
    as91 = resolve_atom_file(FakeService(), ORTO, key="AS91", crs=None, cache=None)
    zabaged = resolve_atom_file(
        FakeService(), ZABAGED, key="", crs="EPSG:3045", cache=None
    )

    assert ctes.edition == "2024_2025-02-06"
    assert as91.edition == "2025_2026-02-24"
    assert zabaged.edition == "2026-10-04"
    assert zabaged.updated == "2026-10-04T21:33:41+02:00"


def test_entry_without_date_is_download_error():
    # the file entry's <updated> (the last one; the feed has its own first)
    head, _, tail = (
        (FIXTURES / "ortofoto_ctes96.xml")
        .read_bytes()
        .rpartition(b"<updated>2025-02-06T14:00:09+02:00</updated>")
    )
    body = head + b"<updated>wczoraj</updated>" + tail
    service = FakeService(
        {**ROUTES, CTES96_FEED: lambda: answer("ortofoto_ctes96.xml", body=body)}
    )
    with pytest.raises(DownloadError, match="<updated>"):
        resolve_atom_file(service, ORTO, key="CTES96", crs=None, cache=None)


def test_index_cached_and_revalidated(cache):
    """Within the TTL the index needs no request; ``refresh`` and an expired
    index send ``If-None-Match``: 304 keeps the index, 200 replaces it."""
    service = FakeService()
    first = atom_index(service, ORTO, cache=cache)
    assert atom_index(service, ORTO, cache=cache) == first
    assert service.calls == [(ORTO_SERVICE, None)]

    service.routes[ORTO_SERVICE] = not_modified
    assert atom_index(service, ORTO, cache=cache, refresh=True) == first
    assert service.calls[-1] == (ORTO_SERVICE, '"64a6104edbc8dc1:0"')

    # a new release of BENE09 replaces the index (200 with a new ETag)
    body = (FIXTURES / "ortofoto_service.xml").read_bytes()
    body = body.replace(b"WRTO24.2025.BENE09", b"WRTO24.2026.BENE09")

    def changed():
        response = answer("ortofoto_service.xml", body=body)
        response.headers["ETag"] = '"nowy"'
        return response

    service.routes[ORTO_SERVICE] = changed
    renewed = atom_index(service, ORTO, cache=cache, refresh=True)
    assert renewed["BENE09"].groups["year"] == "2026"
    assert service.calls[-1] == (ORTO_SERVICE, '"64a6104edbc8dc1:0"')

    # the same store past its TTL: the stored ETag revalidates the index
    expired = MetadataCache(db_path=cache.db_path, ttl_seconds=0)
    service.routes[ORTO_SERVICE] = not_modified
    assert atom_index(service, ORTO, cache=expired) == renewed
    expired.close()
    assert service.calls[-1] == (ORTO_SERVICE, '"nowy"')
    assert len(service.calls) == 4


def test_stale_index_refreshed_when_dataset_feed_gone(cache):
    """A cached index points to the 2024 dataset feed, the source published
    2025 and removed it (404): the index is revalidated once and the new
    dataset feed is read - a stale cache never hides a release."""
    service = FakeService()
    atom_index(service, ORTO, cache=cache)
    body = (FIXTURES / "ortofoto_service.xml").read_bytes()
    body = body.replace(b"WRTO24.2024.CTES96", b"WRTO24.2025.CTES96")
    new_feed = f"{ORTO_FEEDS}_WRTO24.2025.CTES96.xml"
    feed = (FIXTURES / "ortofoto_ctes96.xml").read_bytes()
    feed = feed.replace(b"WRTO24.2024.CTES96", b"WRTO24.2025.CTES96")
    service.routes.update(
        {
            ORTO_SERVICE: lambda: answer("ortofoto_service.xml", body=body),
            CTES96_FEED: "missing_feed.html",
            new_feed: lambda: answer("ortofoto_ctes96.xml", body=feed),
        }
    )

    file = resolve_atom_file(service, ORTO, key="CTES96", crs=None, cache=cache)

    assert file.edition == "2025_2025-02-06"
    assert service.urls()[1:] == [CTES96_FEED, ORTO_SERVICE, new_feed]


def test_unknown_sheet_is_no_coverage(cache):
    """A sheet missing from a fresh index has no orthophoto; a cached index
    is revalidated once before saying so."""
    service = FakeService()
    with pytest.raises(NoCoverageError, match="XXXX99"):
        resolve_atom_file(service, ORTO, key="XXXX99", crs=None, cache=cache)
    assert service.urls() == [ORTO_SERVICE]

    service.routes[ORTO_SERVICE] = not_modified
    with pytest.raises(NoCoverageError, match="XXXX99"):
        resolve_atom_file(service, ORTO, key="XXXX99", crs=None, cache=cache)
    assert service.calls[-1] == (ORTO_SERVICE, '"64a6104edbc8dc1:0"')


@pytest.mark.parametrize("feed", [ORTO_SERVICE, CTES96_FEED])
def test_html_feed_is_download_error(feed, cache):
    """The ATOM host answers its HTML page with HTTP 200: never an index or
    a file (and nothing is cached)."""
    service = FakeService({**ROUTES, feed: "atom_root.html"})
    with pytest.raises(DownloadError, match="nie jest feedem ATOM"):
        resolve_atom_file(service, ORTO, key="CTES96", crs=None, cache=cache)
    if feed == ORTO_SERVICE:
        assert cache.get_atom_entries(f"{ORTO_SERVICE}|{ORTO.entry_pattern}") is None


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


# Member names of WRTO24.2024.CTES96.zip (central directory, 2026-10-15).
CTES96_MEMBERS = {
    "WRTO24.2024.CTES96.jpg": b"\xff\xd8\xff\xe0 jpeg \xff\xd9",
    "WRTO24.2024.CTES96.jgw": b"0.25\n0\n0\n-0.25\n-449999.875\n-1112000.125\n",
    "WRTO24.2024.CTES96.TM33N.jgw": b"0.25\n0.003\n0.003\n-0.25\n1.0\n2.0\n",
    "WRTO24.2024.CTES96.TM34N.jgw": b"0.25\n-0.02\n-0.02\n-0.25\n3.0\n4.0\n",
}


def test_unpack_members_longest_suffix_first(tmp_path):
    archive = tmp_path / "ctes96.zip"
    archive.write_bytes(_zip(CTES96_MEMBERS))

    paths = unpack_members(archive, ORTO, tmp_path, "CTES96", url="u")

    assert {s: p.name for s, p in paths.items()} == {
        ".jpg": "CTES96.jpg",
        ".jgw": "CTES96.jgw",
        ".TM33N.jgw": "CTES96.TM33N.jgw",
        ".TM34N.jgw": "CTES96.TM34N.jgw",
    }
    for suffix, path in paths.items():
        assert path.read_bytes() == CTES96_MEMBERS[f"WRTO24.2024.CTES96{suffix}"]


def test_unpack_members_missing_member_is_download_error(tmp_path):
    members = {k: v for k, v in CTES96_MEMBERS.items() if not k.endswith(".TM34N.jgw")}
    archive = tmp_path / "ctes96.zip"
    archive.write_bytes(_zip(members))

    with pytest.raises(DownloadError, match=r"\.TM34N\.jgw \(0\)"):
        unpack_members(archive, ORTO, tmp_path, "CTES96", url="u")
    assert not list(tmp_path.glob("CTES96*"))


def _file_response(body: bytes, length: int | None = None):
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/x-zip-compressed"}
    if length is not None:
        response.headers["Content-Length"] = str(length)
    response.iter_content = lambda chunk_size=1: iter([body])
    return response


def test_fetch_atom_file_checks_feed_length(tmp_path):
    """A transfer shorter than the feed ``length`` leaves no file."""
    body = _zip(CTES96_MEMBERS)
    service = Mock()
    service.get.return_value = _file_response(body)
    file = resolve_atom_file(FakeService(), ORTO, key="CTES96", crs=None, cache=None)
    target = tmp_path / "CTES96.zip"

    with pytest.raises(DownloadError, match="przerwany transfer"):
        fetch_atom_file(service, file, target, timeout=5)
    assert not target.exists()

    exact = type(file)(**{**file.__dict__, "length": len(body)})
    service.get.return_value = _file_response(body, len(body))
    signal = fetch_atom_file(service, exact, target, timeout=5)
    assert target.read_bytes() == body
    assert signal["content_length"] == len(body)
