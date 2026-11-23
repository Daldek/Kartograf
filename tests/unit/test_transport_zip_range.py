"""Members of a ZIP on an HTTP server read by range requests (ADR-062).

``kartograf.transport.zip_range`` and the range requests of
``kartograf.transport.http`` (``fetch_range``, ``require_partial``, ``download_to``
with ``headers``) against ``tests.support.camels.ZenodoServer``: files in memory that
answer a ``Range`` with 206 as Zenodo does (recorded in ``tests/fixtures/pl/camels``),
or ignore it. The ZIPs are written by ``zipfile`` and read back by it as the oracle.
"""

import hashlib
import io
import random
import struct
import zipfile
import zlib
from dataclasses import replace
from unittest.mock import patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.messages import message
from kartograf.transport.http import (
    RANGE_UNSUPPORTED,
    download_to,
    fetch_range,
    require_partial,
)
from kartograf.transport.zip_range import (
    TAIL_BYTES,
    MemberDigest,
    ZipEntry,
    extract_member,
    fetch_member,
    local_directory,
    read_directory,
)
from tests.support.camels import (
    ANSWERS,
    ZIP_HEADERS,
    Asked,
    ZenodoServer,
    answer,
    member_ranges,
)

URL = "https://example.test/release.zip"
DATE = (2026, 10, 11, 12, 0, 0)
# A member that deflate packs well and one it cannot pack (fixed seed).
TEXT = b"".join(b"%09d;Wisla;%d\n" % (149180100 + i, i * 7) for i in range(4000))
NOISE = random.Random(2180).randbytes(5000)
_END_RECORD = struct.Struct("<4s4H2IH")
_END64_RECORD = struct.Struct("<4sQ2H2I4Q")


def _zip(*members: tuple[str, bytes, int]) -> bytes:
    """A ZIP of ``(name, body, method)`` members with a fixed date."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body, method in members:
            info = zipfile.ZipInfo(name, date_time=DATE)
            info.compress_type = method
            archive.writestr(info, body)
    return buffer.getvalue()


def _serve(data: bytes, **kwargs) -> tuple[ZenodoServer, requests.Session]:
    server = ZenodoServer({URL: (data, ZIP_HEADERS)}, **kwargs)
    return server, server.session()


def _expected(data: bytes) -> tuple[ZipEntry, ...]:
    """The central directory of ``data`` as ``zipfile`` reads it."""
    return tuple(
        ZipEntry(
            info.filename,
            info.compress_type,
            info.flag_bits,
            info.CRC,
            info.compress_size,
            info.file_size,
            info.header_offset,
        )
        for info in zipfile.ZipFile(io.BytesIO(data)).infolist()
    )


def _entry(data: bytes, name: str) -> ZipEntry:
    (entry,) = [entry for entry in _expected(data) if entry.name == name]
    return entry


def _digest(body: bytes) -> MemberDigest:
    return MemberDigest(len(body), zlib.crc32(body), hashlib.sha256(body).hexdigest())


def _first_byte(span: str) -> int:
    """The first byte of a ``Range`` ``bytes=<first>-<last>``."""
    return int(span.removeprefix("bytes=").split("-")[0])


# --- the central directory ----------------------------------------------------


def test_read_directory_of_a_small_zip_asks_its_last_mib_once():
    data = _zip(
        ("CAMELS_PL_2.1/", b"", zipfile.ZIP_STORED),
        ("CAMELS_PL_2.1/gauges.gpkg", NOISE, zipfile.ZIP_STORED),
        ("CAMELS_PL_2.1/attributes.csv", TEXT, zipfile.ZIP_DEFLATED),
    )
    server, session = _serve(data)

    entries, total = read_directory(session, URL, timeout=5)

    assert entries == _expected(data)
    assert total == len(data)
    assert server.asked == [Asked("GET", URL, f"bytes=-{TAIL_BYTES}")]
    assert server.headers[0]["Accept-Encoding"] == "identity"


def test_read_directory_that_starts_before_the_last_mib_asks_it_once_more():
    """6000 members with long names: a directory of 1.2 MB, larger than the tail."""
    data = _zip(
        *(
            (f"CAMELS_PL_2.1/timeseries/{'q' * 160}_{number:05d}.csv", b"", 0)
            for number in range(6000)
        )
    )
    *_, size, offset, _ = _END_RECORD.unpack_from(data, len(data) - _END_RECORD.size)
    server, session = _serve(data)

    entries, total = read_directory(session, URL, timeout=5)

    assert offset < len(data) - TAIL_BYTES
    assert entries == _expected(data) and len(entries) == 6000
    assert total == len(data)
    assert server.asked == [
        Asked("GET", URL, f"bytes=-{TAIL_BYTES}"),
        Asked("GET", URL, f"bytes={offset}-{offset + size - 1}"),
    ]


@pytest.fixture(scope="module")
def zip64() -> bytes:
    """65,536 members, more than the end record counts: ``zipfile`` writes the ZIP64
    end record and its locator and marks the counts of the end record 0xFFFF."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in range(65_536):
            archive.writestr(zipfile.ZipInfo(f"{number:05x}", date_time=DATE), b"")
    return buffer.getvalue()


def test_read_directory_of_a_zip64_archive_reads_its_record_by_the_locator(zip64):
    _, _, _, here, count, *_ = _END_RECORD.unpack_from(zip64, len(zip64) - 22)
    record = _END64_RECORD.unpack_from(zip64, zip64.rfind(b"PK\x06\x06"))
    *_, size, offset = record
    server, session = _serve(zip64)

    entries, total = read_directory(session, URL, timeout=5)

    assert (here, count) == (0xFFFF, 0xFFFF)
    assert len(entries) == 65_536 and entries == _expected(zip64)
    assert total == len(zip64)
    assert server.asked == [
        Asked("GET", URL, f"bytes=-{TAIL_BYTES}"),
        Asked("GET", URL, f"bytes={offset}-{offset + size - 1}"),
    ]


def test_zip64_extra_fields_give_the_sizes_and_offsets_of_members(
    tmp_path, monkeypatch
):
    """``zipfile`` writes ZIP64 extra fields for what passes ``ZIP64_LIMIT`` (2 GiB);
    with the limit lowered to 1 KiB for the write a small ZIP has them: the directory
    marks sizes and offsets 0xFFFFFFFF and the extra fields hold them."""
    with monkeypatch.context() as lowered:
        lowered.setattr(zipfile, "ZIP64_LIMIT", 1024)
        data = _zip(
            ("small.prj", b"PROJCS", zipfile.ZIP_STORED),
            ("gauges.gpkg", NOISE, zipfile.ZIP_STORED),
            ("attributes.csv", TEXT, zipfile.ZIP_DEFLATED),
        )
    _, session = _serve(data)

    entries, _ = read_directory(session, URL, timeout=5)
    digest = fetch_member(
        session, URL, _entry(data, "gauges.gpkg"), tmp_path / "gauges.gpkg", timeout=5
    )

    *_, offset, _ = _END_RECORD.unpack_from(data, len(data) - _END_RECORD.size)
    assert b"\xff\xff\xff\xff" in data[offset:]
    assert entries == _expected(data)
    assert digest == _digest(NOISE)
    assert (tmp_path / "gauges.gpkg").read_bytes() == NOISE


def test_read_directory_of_a_file_that_is_no_zip_is_download_error():
    server, session = _serve(b"%PDF-1.7\n" + bytes(2000))

    with pytest.raises(DownloadError) as raised:
        read_directory(session, URL, timeout=5)

    assert str(raised.value) == message("transport.zip_no_end", context=URL)
    assert raised.value.reason is None
    assert len(server.asked) == 1


# --- one member -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "body", "method"),
    [
        ("gauges.gpkg", NOISE, zipfile.ZIP_STORED),
        ("attributes.csv", TEXT, zipfile.ZIP_DEFLATED),
        ("empty.txt", b"", zipfile.ZIP_STORED),
    ],
    ids=["stored", "deflated", "empty"],
)
def test_fetch_member_unpacks_it_with_its_size_crc_and_sha256(
    tmp_path, name, body, method
):
    """The local header, then the stored bytes (none for an empty member), each by
    its range; the packed bytes are removed."""
    data = _zip(("first.prj", b"PROJCS", zipfile.ZIP_DEFLATED), (name, body, method))
    server, session = _serve(data)
    entry = _entry(data, name)
    target = tmp_path / name

    digest = fetch_member(session, URL, entry, target, timeout=5)

    assert digest == _digest(body)
    assert target.read_bytes() == body
    header, stored = member_ranges(data, name)
    asked = [header, stored] if entry.compressed_size else [header]
    assert server.asked == [Asked("GET", URL, span) for span in asked]
    assert list(tmp_path.iterdir()) == [target]


def test_fetch_member_whose_stored_bytes_changed_is_download_error(tmp_path):
    """A member that unpacks to another CRC than its directory entry was damaged on
    the way; the packed bytes are removed."""
    data = bytearray(_zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED)))
    entry = _entry(bytes(data), "gauges.gpkg")
    _, stored = member_ranges(bytes(data), "gauges.gpkg")
    data[_first_byte(stored) + 100] ^= 0xFF
    damaged = bytearray(NOISE)
    damaged[100] ^= 0xFF
    _, session = _serve(bytes(data))

    with pytest.raises(DownloadError) as raised:
        fetch_member(session, URL, entry, tmp_path / "gauges.gpkg", timeout=5)

    assert str(raised.value) == message(
        "transport.zip_member_damaged",
        context=URL,
        member="gauges.gpkg",
        size=len(NOISE),
        crc32=f"{zlib.crc32(damaged):08x}",
        expected_size=entry.size,
        expected_crc32=f"{entry.crc32:08x}",
    )
    assert not (tmp_path / "gauges.gpkg.packed").exists()


def test_fetch_member_whose_deflated_bytes_changed_is_download_error(tmp_path):
    data = bytearray(_zip(("attributes.csv", TEXT, zipfile.ZIP_DEFLATED)))
    entry = _entry(bytes(data), "attributes.csv")
    _, stored = member_ranges(bytes(data), "attributes.csv")
    data[_first_byte(stored) + entry.compressed_size // 2] ^= 0xFF
    _, session = _serve(bytes(data))

    with pytest.raises(DownloadError):
        fetch_member(session, URL, entry, tmp_path / "attributes.csv", timeout=5)

    assert not (tmp_path / "attributes.csv.packed").exists()


def test_fetch_member_of_another_method_is_refused_before_any_request(tmp_path):
    data = _zip(("attributes.csv", TEXT, zipfile.ZIP_BZIP2))
    server, session = _serve(data)

    with pytest.raises(DownloadError) as raised:
        fetch_member(
            session,
            URL,
            _entry(data, "attributes.csv"),
            tmp_path / "attributes.csv",
            timeout=5,
        )

    assert str(raised.value) == message(
        "transport.zip_method",
        context=URL,
        member="attributes.csv",
        method=zipfile.ZIP_BZIP2,
    )
    assert server.asked == []


def test_fetch_member_without_its_local_header_at_the_offset_is_download_error(
    tmp_path,
):
    data = _zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED))
    entry = replace(_entry(data, "gauges.gpkg"), header_offset=40)
    _, session = _serve(data)

    with pytest.raises(DownloadError) as raised:
        fetch_member(session, URL, entry, tmp_path / "gauges.gpkg", timeout=5)

    assert str(raised.value) == message(
        "transport.zip_no_local_header", context=URL, member="gauges.gpkg", offset=40
    )


# --- a server that ignores ranges -------------------------------------------------


def test_read_directory_of_a_server_that_ignores_ranges_reads_no_body():
    """200 with the whole file: ``RANGE_UNSUPPORTED`` at once, no retry, and the
    answer is closed with nothing of its body read."""
    data = _zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED))
    server, session = _serve(data, ranges=False)

    with pytest.raises(DownloadError) as raised:
        read_directory(session, URL, timeout=5)

    assert (raised.value.reason, raised.value.status_code) == (RANGE_UNSUPPORTED, 200)
    assert server.asked == [Asked("GET", URL, f"bytes=-{TAIL_BYTES}")]
    (body,) = server.bodies
    assert body.taken == 0 and body.closed


def test_fetch_member_of_a_server_that_ignores_ranges_is_range_unsupported(tmp_path):
    data = _zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED))
    server, session = _serve(data, ranges=False)

    with pytest.raises(DownloadError) as raised:
        fetch_member(
            session,
            URL,
            _entry(data, "gauges.gpkg"),
            tmp_path / "gauges.gpkg",
            timeout=5,
        )

    assert raised.value.reason == RANGE_UNSUPPORTED
    assert len(server.asked) == 1 and server.bodies[0].taken == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("ranges", [True, False], ids=["range", "whole-file"])
def test_download_to_with_a_range_writes_it_or_refuses_the_whole_file(tmp_path, ranges):
    """``require_partial`` as ``validate``: the range is written; the whole file of
    a server that ignores ``Range`` is refused unread and nothing is written."""
    data = bytes(range(256)) * 8
    server, session = _serve(data, ranges=ranges)
    target = tmp_path / "part.bin"

    def validate(response: requests.Response) -> None:
        require_partial(response, 1000, 500, "part")

    def run() -> None:
        download_to(
            session,
            URL,
            target,
            timeout=5,
            validate=validate,
            headers={"Range": "bytes=1000-1499", "Accept-Encoding": "identity"},
        )

    if ranges:
        run()
        assert target.read_bytes() == data[1000:1500]
    else:
        with pytest.raises(DownloadError) as raised:
            run()
        assert raised.value.reason == RANGE_UNSUPPORTED
        assert server.bodies[0].taken == 0
        assert list(tmp_path.iterdir()) == []
    assert server.asked == [Asked("GET", URL, "bytes=1000-1499")]


# --- fetch_range and require_partial -----------------------------------------------


def test_fetch_range_retries_a_range_that_ends_early():
    """A body shorter than its range is retried like a broken connection; the next
    full answer is taken."""
    data = bytes(range(256)) * 4
    server, session = _serve(data, short=1)

    with patch("kartograf.transport.http.time.sleep") as sleep:
        found = fetch_range(session, URL, 10, 20, timeout=5)

    assert found == (data[10:30], 10, len(data))
    assert server.asked == [Asked("GET", URL, "bytes=10-29")] * 2
    sleep.assert_called_once_with(2)


def test_fetch_range_short_at_every_attempt_fails_after_the_retries():
    """Not a server that ignores ranges: the retry policy runs out (three attempts)."""
    data = bytes(range(256)) * 4
    server, session = _serve(data, short=3)

    with (
        patch("kartograf.transport.http.time.sleep") as sleep,
        pytest.raises(DownloadError) as raised,
    ):
        fetch_range(session, URL, 10, 20, timeout=5)

    assert raised.value.reason is None
    assert server.asked == [Asked("GET", URL, "bytes=10-29")] * 3
    assert [call.args for call in sleep.call_args_list] == [(2,), (4,)]


def test_fetch_range_of_the_last_bytes_of_a_file_shorter_than_them():
    """A suffix range longer than the file: the whole file, from byte 0."""
    data = b"PK" + bytes(100)
    server, session = _serve(data)

    found = fetch_range(session, URL, None, TAIL_BYTES, timeout=5)

    assert found == (data, 0, len(data))
    assert server.asked == [Asked("GET", URL, f"bytes=-{TAIL_BYTES}")]


def test_require_partial_reads_the_recorded_answer_of_a_suffix_range():
    """The answer of Zenodo to ``Range: bytes=-22`` of the ZIP of CAMELS-PL 2.1
    (recorded 2026-11-23): its first byte and the length of the file."""
    recorded = ANSWERS["range"]
    request = requests.Request(
        "GET", recorded["url"], headers=recorded["request_headers"]
    ).prepare()
    response = answer(request, recorded["status"], recorded["headers"], b"")

    found = require_partial(response, None, 22, "CAMELS_PL_2.1.zip")

    assert found == (1_670_805_328, 1_670_805_350)


def _partial(status: int, content_range: str | None) -> requests.Response:
    request = requests.Request("GET", URL).prepare()
    headers = {} if content_range is None else {"Content-Range": content_range}
    return answer(request, status, headers, b"0123456789")


@pytest.mark.parametrize(
    ("start", "length", "content_range", "found"),
    [
        (100, 50, "bytes 100-149/1000", (100, 1000)),
        (100, 50, "bytes 100-149/*", (100, None)),
        (None, 22, "bytes 978-999/1000", (978, 1000)),
        (None, TAIL_BYTES, "bytes 0-9999/10000", (0, 10000)),
    ],
    ids=["range", "range-unknown-length", "suffix", "suffix-whole-file"],
)
def test_require_partial_returns_the_first_byte_and_the_length_of_the_file(
    start, length, content_range, found
):
    assert require_partial(_partial(206, content_range), start, length, "x") == found


@pytest.mark.parametrize(
    ("status", "start", "length", "content_range"),
    [
        (200, 100, 50, None),
        (200, 100, 50, "bytes 100-149/1000"),
        (206, 100, 50, None),
        (206, 100, 50, "bytes 0-49/1000"),
        (206, 100, 50, "bytes 100-148/1000"),
        (206, 100, 50, "items 100-149/1000"),
        (206, None, 22, "bytes 970-991/1000"),
        (206, None, 22, "bytes 970-999/1000"),
        (206, None, 22, "bytes 978-999/*"),
    ],
    ids=[
        "whole-file",
        "status-200",
        "no-content-range",
        "another-range",
        "shorter-range",
        "not-bytes",
        "suffix-not-at-the-end",
        "suffix-longer",
        "suffix-unknown-length",
    ],
)
def test_require_partial_refuses_an_answer_without_the_range_unread(
    status, start, length, content_range
):
    response = _partial(status, content_range)

    with pytest.raises(DownloadError) as raised:
        require_partial(response, start, length, "x")

    assert (raised.value.reason, raised.value.status_code) == (
        RANGE_UNSUPPORTED,
        status,
    )
    assert response.raw.closed


# --- a local ZIP (the whole-archive fallback) --------------------------------------


def test_local_directory_and_extract_member_read_what_the_ranges_read(tmp_path):
    """The entries of the local reader are those of the range reader, and a member
    unpacks to the same bytes and digest."""
    data = _zip(
        ("CAMELS_PL_2.1/", b"", zipfile.ZIP_STORED),
        ("CAMELS_PL_2.1/gauges.gpkg", NOISE, zipfile.ZIP_STORED),
        ("CAMELS_PL_2.1/attributes.csv", TEXT, zipfile.ZIP_DEFLATED),
    )
    path = tmp_path / "release.zip"
    path.write_bytes(data)
    _, session = _serve(data)
    ranged, _ = read_directory(session, URL, timeout=5)

    entries = local_directory(path)
    digests = [
        extract_member(path, entry, tmp_path / f"{number}.out")
        for number, entry in enumerate(entries[1:], start=1)
    ]

    assert entries == ranged
    assert digests == [_digest(NOISE), _digest(TEXT)]
    assert (tmp_path / "1.out").read_bytes() == NOISE
    assert (tmp_path / "2.out").read_bytes() == TEXT


def test_local_directory_of_a_file_that_is_no_zip_is_download_error(tmp_path):
    path = tmp_path / "release.zip"
    path.write_bytes(b"%PDF-1.7\n" + bytes(2000))

    with pytest.raises(DownloadError, match="release.zip"):
        local_directory(path)


def test_extract_member_of_an_entry_the_local_zip_lacks_is_download_error(tmp_path):
    data = _zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED))
    path = tmp_path / "release.zip"
    path.write_bytes(data)
    entry = replace(_entry(data, "gauges.gpkg"), name="other.gpkg")

    with pytest.raises(DownloadError) as raised:
        extract_member(path, entry, tmp_path / "other.gpkg")

    assert str(raised.value) == message(
        "transport.zip_no_local_header",
        context="release.zip",
        member="other.gpkg",
        offset=entry.header_offset,
    )


def test_extract_member_whose_bytes_changed_is_download_error(tmp_path):
    data = bytearray(_zip(("gauges.gpkg", NOISE, zipfile.ZIP_STORED)))
    entry = _entry(bytes(data), "gauges.gpkg")
    _, stored = member_ranges(bytes(data), "gauges.gpkg")
    data[_first_byte(stored) + 100] ^= 0xFF
    path = tmp_path / "release.zip"
    path.write_bytes(bytes(data))

    with pytest.raises(DownloadError):
        extract_member(path, entry, tmp_path / "gauges.gpkg")
