"""
Members of a ZIP on an HTTP server, read by range requests (ADR-062).

A ZIP keeps its table of contents at its end, the central directory, which its
end record locates (ZIP64 included). ``read_directory`` asks the last MiB of the
file and, when the directory begins before it, the directory itself: one request,
two at most, three with a ZIP64 record before them. ``fetch_member`` asks the local
header of one member (its name and extra field may differ from the directory's),
then the member's compressed bytes - a range written to a file by ``download_to`` -
and unpacks them, counting their size, CRC-32 and SHA-256; a member whose size or
CRC differs from its directory entry was damaged on the way (``DownloadError``).

A server that does not answer a range request with that range raises
``DownloadError`` with the reason ``RANGE_UNSUPPORTED`` (``require_partial``): the
caller downloads the whole ZIP instead and reads the same entries with
``local_directory`` and ``extract_member``. Stored (0) and deflated (8) members are
read (``READ_METHODS``); which entries are wanted, and whether their method can be
read, is the caller's judgement.
"""

import hashlib
import logging
import struct
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError
from kartograf.interrupt import check_stop
from kartograf.messages import message, reason
from kartograf.transport.http import download_to, fetch_range, require_partial

logger = logging.getLogger(__name__)

# The last bytes of a ZIP asked first: its end record (22 bytes and a comment of up
# to 65535), a ZIP64 locator and record before it, and - in one request - the
# directory of a ZIP of a few thousand members (CAMELS-PL 2.1: 417 KB).
TAIL_BYTES = 1 << 20
# Compression methods ``fetch_member`` and ``extract_member`` unpack: stored, deflated.
READ_METHODS = (0, 8)
_CHUNK = 1 << 20
_END = b"PK\x05\x06"
_END64 = b"PK\x06\x06"
_LOCATOR = b"PK\x06\x07"
_CENTRAL = b"PK\x01\x02"
_LOCAL = b"PK\x03\x04"
_END_RECORD = struct.Struct("<4s4H2IH")  # 22 bytes
_LOCATOR_RECORD = struct.Struct("<4sIQI")  # 20 bytes
_END64_RECORD = struct.Struct("<4sQ2H2I4Q")  # 56 bytes
_CENTRAL_HEADER = struct.Struct("<4s6H3I5H2I")  # 46 bytes
_LOCAL_HEADER = struct.Struct("<4s5H3I2H")  # 30 bytes
_ZIP64_EXTRA = 0x0001
_UTF8_FLAG = 0x0800
_ENCRYPTED_FLAG = 0x0001
_MAX16 = 0xFFFF
_MAX32 = 0xFFFFFFFF


@dataclass(frozen=True)
class ZipEntry:
    """One member of a ZIP as its central directory describes it.

    ``crc32`` is the CRC of the unpacked bytes, ``size`` their number and
    ``compressed_size`` that of the stored bytes; ``header_offset`` is the offset
    of the member's local header in the file.
    """

    name: str
    method: int
    flags: int
    crc32: int
    compressed_size: int
    size: int
    header_offset: int


@dataclass(frozen=True)
class MemberDigest:
    """The unpacked bytes of a member: their number, CRC-32 and SHA-256."""

    size: int
    crc32: int
    sha256: str


def read_directory(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    description: str = "",
) -> tuple[tuple[ZipEntry, ...], int]:
    """Read the central directory of the ZIP at ``url`` by range requests.

    Returns
    -------
    tuple of (tuple of ZipEntry, int)
        The entries in the order of the directory and the length of the file (from
        the ``Content-Range`` of the first answer).

    Raises
    ------
    DownloadError
        ``reason`` ``RANGE_UNSUPPORTED``: the server does not answer a range request
        with the range; otherwise a failed request, or a file that is not a readable
        ZIP of one disk.
    """
    context = description or url
    tail, first, total = fetch_range(
        session, url, None, TAIL_BYTES, timeout=timeout, description=context
    )
    assert total is not None  # a suffix range is checked with the length of the file

    def part(offset: int, length: int) -> bytes:
        """``length`` bytes from ``offset``: from the tail, else one more request."""
        if offset >= first and offset + length <= first + len(tail):
            return tail[offset - first : offset - first + length]
        body, _, _ = fetch_range(
            session, url, offset, length, timeout=timeout, description=context
        )
        return body

    count, offset, size, end = _end_record(tail, context)
    if count is None:
        count, offset, size = _end64_record(tail, end, part, context)
    if offset + size > total:
        raise DownloadError(message("transport.zip_damaged", context=context))
    return _entries(part(offset, size) if size else b"", count, context), total


def fetch_member(
    session: requests.Session,
    url: str,
    entry: ZipEntry,
    target: Path,
    *,
    timeout: float,
    description: str = "",
) -> MemberDigest:
    """Read one member of the ZIP at ``url`` into ``target`` by range requests.

    The local header of the member first (30 bytes and its name and extra field),
    then its compressed bytes into ``<target>.packed`` (``download_to``: the retry
    policy and atomic write of every download), unpacked into ``target`` and removed.

    Returns
    -------
    MemberDigest
        Size, CRC-32 and SHA-256 of the unpacked bytes: the size and CRC are those of
        ``entry``.

    Raises
    ------
    DownloadError
        ``reason`` ``RANGE_UNSUPPORTED`` as ``read_directory``; a failed request, no
        local header at the offset of ``entry``, a method outside ``READ_METHODS``, or
        bytes that do not unpack to the size and CRC of ``entry``.
    """
    context = description or url
    _check_method(entry, context)
    header, _, _ = fetch_range(
        session,
        url,
        entry.header_offset,
        _LOCAL_HEADER.size,
        timeout=timeout,
        description=context,
    )
    signature, *_, name_length, extra_length = _LOCAL_HEADER.unpack(header)
    if signature != _LOCAL:
        raise DownloadError(
            message(
                "transport.zip_no_local_header",
                context=context,
                member=entry.name,
                offset=entry.header_offset,
            )
        )
    start = entry.header_offset + _LOCAL_HEADER.size + name_length + extra_length
    packed = target.with_name(f"{target.name}.packed")
    length = entry.compressed_size
    try:
        if length:

            def validate(response: requests.Response) -> None:
                require_partial(response, start, length, context)

            download_to(
                session,
                url,
                packed,
                timeout=timeout,
                description=context,
                validate=validate,
                headers={
                    "Range": f"bytes={start}-{start + length - 1}",
                    "Accept-Encoding": "identity",
                },
            )
        else:
            packed.write_bytes(b"")
        digest = _unpack(packed, target, entry.method, entry.name, context)
    finally:
        packed.unlink(missing_ok=True)
    _check_digest(entry, digest, context)
    return digest


def local_directory(path: Path) -> tuple[ZipEntry, ...]:
    """Return the entries of the central directory of a local ZIP.

    Raises
    ------
    DownloadError
        ``path`` is not a readable ZIP.
    """
    try:
        with zipfile.ZipFile(path) as archive:
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
                for info in archive.infolist()
            )
    except (zipfile.BadZipFile, ValueError) as e:
        raise DownloadError(
            message("transport.zip_unreadable", context=path.name, error=reason(e))
        ) from e


def extract_member(path: Path, entry: ZipEntry, target: Path) -> MemberDigest:
    """Unpack the member ``entry`` of the local ZIP ``path`` into ``target``.

    Returns
    -------
    MemberDigest
        Size, CRC-32 and SHA-256 of the unpacked bytes (those of ``entry``).

    Raises
    ------
    DownloadError
        A method outside ``READ_METHODS``, a damaged member or a ZIP without it.
    """
    context = path.name
    _check_method(entry, context)
    digest = _Digest()
    try:
        with zipfile.ZipFile(path) as archive:
            info = next(
                (
                    i
                    for i in archive.infolist()
                    if i.header_offset == entry.header_offset
                ),
                None,
            )
            if info is None or info.filename != entry.name:
                raise DownloadError(
                    message(
                        "transport.zip_no_local_header",
                        context=context,
                        member=entry.name,
                        offset=entry.header_offset,
                    )
                )
            with archive.open(info) as source, open(target, "wb") as sink:
                while chunk := source.read(_CHUNK):
                    check_stop()
                    sink.write(chunk)
                    digest.add(chunk)
    except (zipfile.BadZipFile, zlib.error, EOFError) as e:
        raise DownloadError(
            message(
                "transport.zip_member_unreadable",
                context=context,
                member=entry.name,
                error=reason(e),
            )
        ) from e
    found = digest.result()
    _check_digest(entry, found, context)
    return found


# --- parsing -------------------------------------------------------------------


def _end_record(tail: bytes, context: str) -> tuple[int | None, int, int, int]:
    """Read the end record of the central directory in the last bytes of a ZIP.

    The last signature of the record that has its 22 bytes in ``tail`` is taken, as
    ``zipfile`` takes it. Returns ``(entries, directory offset, directory size,
    position of the record in tail)``; ``entries`` is ``None`` when a field holds its
    ZIP64 marker (the ZIP64 record has the values).
    """
    position = tail.rfind(_END, 0, max(len(tail) - _END_RECORD.size + len(_END), 0))
    if position < 0:
        raise DownloadError(message("transport.zip_no_end", context=context))
    _, disk, start_disk, here, count, size, offset, _ = _END_RECORD.unpack_from(
        tail, position
    )
    if _MAX16 in (disk, start_disk, here, count) or _MAX32 in (size, offset):
        return None, offset, size, position
    if disk or start_disk or here != count:
        raise DownloadError(message("transport.zip_disks", context=context))
    return count, offset, size, position


def _end64_record(
    tail: bytes,
    end: int,
    part: Callable[[int, int], bytes],
    context: str,
) -> tuple[int, int, int]:
    """Read the ZIP64 end record through the locator before the end record.

    Returns ``(entries, directory offset, directory size)``.
    """
    locator = end - _LOCATOR_RECORD.size
    if locator < 0:
        raise DownloadError(message("transport.zip_no_end", context=context))
    signature, _, record, disks = _LOCATOR_RECORD.unpack_from(tail, locator)
    if signature != _LOCATOR:
        raise DownloadError(message("transport.zip_no_end", context=context))
    fields = _END64_RECORD.unpack(part(record, _END64_RECORD.size))
    signature, _, _, _, disk, start_disk, here, count, size, offset = fields
    if signature != _END64:
        raise DownloadError(message("transport.zip_no_end", context=context))
    if disks != 1 or disk or start_disk or here != count:
        raise DownloadError(message("transport.zip_disks", context=context))
    return count, offset, size


def _entries(directory: bytes, count: int, context: str) -> tuple[ZipEntry, ...]:
    """Parse ``count`` entries of a central directory."""
    entries: list[ZipEntry] = []
    position = 0
    for _ in range(count):
        if position + _CENTRAL_HEADER.size > len(directory):
            raise DownloadError(message("transport.zip_damaged", context=context))
        (
            signature,
            _made,
            _needed,
            flags,
            method,
            _time,
            _date,
            crc,
            compressed,
            size,
            name_length,
            extra_length,
            comment_length,
            _disk,
            _internal,
            _external,
            offset,
        ) = _CENTRAL_HEADER.unpack_from(directory, position)
        if signature != _CENTRAL:
            raise DownloadError(message("transport.zip_damaged", context=context))
        start = position + _CENTRAL_HEADER.size
        name_end = start + name_length
        extra_end = name_end + extra_length
        if extra_end + comment_length > len(directory):
            raise DownloadError(message("transport.zip_damaged", context=context))
        raw = directory[start:name_end]
        name = raw.decode("utf-8" if flags & _UTF8_FLAG else "cp437")
        size, compressed, offset = _zip64_values(
            directory[name_end:extra_end], size, compressed, offset, context
        )
        entries.append(ZipEntry(name, method, flags, crc, compressed, size, offset))
        position = extra_end + comment_length
    return tuple(entries)


def _zip64_values(
    extra: bytes, size: int, compressed: int, offset: int, context: str
) -> tuple[int, int, int]:
    """Replace the 32-bit markers of an entry by its ZIP64 extra field values."""
    if _MAX32 not in (size, compressed, offset):
        return size, compressed, offset
    position = 0
    while position + 4 <= len(extra):
        tag, length = struct.unpack_from("<2H", extra, position)
        body = extra[position + 4 : position + 4 + length]
        position += 4 + length
        if tag != _ZIP64_EXTRA:
            continue
        values = list(struct.unpack_from(f"<{len(body) // 8}Q", body))
        try:
            if size == _MAX32:
                size = values.pop(0)
            if compressed == _MAX32:
                compressed = values.pop(0)
            if offset == _MAX32:
                offset = values.pop(0)
        except IndexError:
            break
        return size, compressed, offset
    raise DownloadError(message("transport.zip_damaged", context=context))


# --- members -------------------------------------------------------------------


class _Digest:
    """Size, CRC-32 and SHA-256 of bytes fed in chunks."""

    def __init__(self) -> None:
        self.size = 0
        self.crc32 = 0
        self.sha256 = hashlib.sha256()

    def add(self, chunk: bytes) -> None:
        self.size += len(chunk)
        self.crc32 = zlib.crc32(chunk, self.crc32)
        self.sha256.update(chunk)

    def result(self) -> MemberDigest:
        return MemberDigest(self.size, self.crc32, self.sha256.hexdigest())


def _check_method(entry: ZipEntry, context: str) -> None:
    if entry.method not in READ_METHODS or entry.flags & _ENCRYPTED_FLAG:
        raise DownloadError(
            message(
                "transport.zip_method",
                context=context,
                member=entry.name,
                method=entry.method,
            )
        )


def _unpack(
    packed: Path, target: Path, method: int, name: str, context: str
) -> MemberDigest:
    """Unpack the stored bytes of a member (method 0 or 8) into ``target``."""
    digest = _Digest()
    inflater = zlib.decompressobj(-zlib.MAX_WBITS) if method == 8 else None
    try:
        with open(packed, "rb") as source, open(target, "wb") as sink:
            while chunk := source.read(_CHUNK):
                check_stop()
                if inflater is None:
                    sink.write(chunk)
                    digest.add(chunk)
                    continue
                data = chunk
                while data:
                    out = inflater.decompress(data, _CHUNK)
                    sink.write(out)
                    digest.add(out)
                    data = inflater.unconsumed_tail
            if inflater is not None:
                out = inflater.flush()
                sink.write(out)
                digest.add(out)
                if not inflater.eof:
                    raise zlib.error("the deflate stream ends early")
    except zlib.error as e:
        raise DownloadError(
            message(
                "transport.zip_member_unreadable",
                context=context,
                member=name,
                error=reason(e),
            )
        ) from e
    return digest.result()


def _check_digest(entry: ZipEntry, digest: MemberDigest, context: str) -> None:
    """Check that a member unpacked to the size and CRC of its directory entry."""
    if (digest.size, digest.crc32) != (entry.size, entry.crc32):
        raise DownloadError(
            message(
                "transport.zip_member_damaged",
                context=context,
                member=entry.name,
                size=digest.size,
                crc32=f"{digest.crc32:08x}",
                expected_size=entry.size,
                expected_crc32=f"{entry.crc32:08x}",
            )
        )
