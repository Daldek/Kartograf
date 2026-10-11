"""
WCS ``image/x-aaigrid`` responses: multipart body -> ASC part -> float32 GeoTIFF.

GUGiK WCS serves NMT EVRF2007 and NMPT heights only as ``image/x-aaigrid``
wrapped in ``multipart/related`` (``result.asc``, ``result.asc.aux.xml``,
``result.prj``); the ``image/tiff`` of those coverages is RGB uint8
(``docs/research/2026-10-11-wcs-cutouts/raport.md``, point 1). The module
knows no services or URLs: the caller supplies the expected chunk geometry.

The response lands on disk first (an ASC is ~20.5 B/px, a single
``download_bbox`` request may be hundreds of MB), so the body is scanned in a
fixed-size buffer, never read whole.
"""

import os
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import rasterio
import requests
from rasterio.errors import RasterioError
from rasterio.io import DatasetReader

from kartograf.exceptions import DownloadError
from kartograf.transport.chunks import Chunk
from kartograf.transport.mosaic import _GRID_TOL_PX

ASC_MEDIA_TYPE = "image/x-aaigrid"

_BUF = 1_048_576
# A part header is a few short lines; more than this is not a MIME header.
_MAX_PART_HEADER = 65_536
_BOUNDARY = re.compile(r'boundary\s*=\s*(?:"([^"]+)"|([^;\s]+))', re.IGNORECASE)
_PART_TYPE = re.compile(
    rb"^content-type\s*:\s*([^;\r\n]+)", re.IGNORECASE | re.MULTILINE
)


def _boundary(content_type: str) -> bytes:
    match = _BOUNDARY.search(content_type)
    if not match or "multipart/" not in content_type.lower():
        raise DownloadError(
            f"WCS: odpowiedz nie jest multipart (Content-Type: {content_type!r})"
        )
    return (match.group(1) or match.group(2)).encode("ascii")


class _Scanner:
    """Forward-only search in a file through a bounded buffer."""

    def __init__(self, f: BinaryIO):
        self._f = f
        self._buf = b""
        self._eof = False

    def _fill(self) -> bool:
        data = self._f.read(_BUF)
        if not data:
            self._eof = True
            return False
        self._buf += data
        return True

    def skip_past(
        self, pattern: bytes, sink: Callable[[bytes], object] | None = None
    ) -> bool:
        """Consume up to and including ``pattern``; bytes before it go to ``sink``.

        False (everything consumed) when the file ends without ``pattern``.
        """
        keep = len(pattern) - 1
        while True:
            i = self._buf.find(pattern)
            if i >= 0:
                if sink is not None:
                    sink(self._buf[:i])
                self._buf = self._buf[i + len(pattern) :]
                return True
            if len(self._buf) > keep:
                if sink is not None:
                    sink(self._buf[: len(self._buf) - keep])
                self._buf = self._buf[len(self._buf) - keep :]
            if not self._fill():
                if sink is not None:
                    sink(self._buf)
                self._buf = b""
                return False

    def peek(self, n: int) -> bytes:
        while len(self._buf) < n and not self._eof and self._fill():
            pass
        return self._buf[:n]

    def part_header(self) -> bytes | None:
        """Header lines of the current part (up to an empty line, CRLF or LF)."""
        while True:
            ends = [
                (i, len(sep))
                for sep in (b"\r\n\r\n", b"\n\n")
                if (i := self._buf.find(sep)) >= 0
            ]
            if ends:
                i, size = min(ends)
                header = self._buf[:i]
                self._buf = self._buf[i + size :]
                return header
            if len(self._buf) > _MAX_PART_HEADER or not self._fill():
                return None


class _BodyWriter:
    """Writes a part body; the line break before the next delimiter is dropped.

    The delimiter is searched as ``\\n--boundary``, so a CRLF break leaves a
    trailing ``\\r`` - the last byte is held back until the end of the part.
    """

    def __init__(self, f: BinaryIO):
        self._f = f
        self._held = b""

    def __call__(self, data: bytes) -> None:
        data = self._held + data
        self._f.write(data[:-1])
        self._held = data[-1:]

    def close(self) -> None:
        if self._held != b"\r":
            self._f.write(self._held)


def _head(path: Path, size: int = 300) -> str:
    with open(path, "rb") as f:
        return f.read(size).decode("utf-8", errors="replace")


def extract_multipart_asc(src: Path, content_type: str, dst: Path) -> Path:
    """Copy the ``image/x-aaigrid`` part of a multipart body file to ``dst``.

    Streams through ``src`` in a fixed buffer. The boundary comes from
    ``content_type`` (quoted or not). No ASC part = ``DownloadError`` with the
    beginning of the body; ``dst`` is not left behind.
    """
    src, dst = Path(src), Path(dst)
    boundary = _boundary(content_type)
    delimiter = b"--" + boundary
    found = False
    try:
        with open(src, "rb") as f:
            scanner = _Scanner(f)
            if scanner.skip_past(delimiter):
                while scanner.peek(2) != b"--":
                    header = scanner.part_header()
                    if header is None:
                        break
                    media = _PART_TYPE.search(header)
                    if (
                        media
                        and media.group(1).strip().lower() == ASC_MEDIA_TYPE.encode()
                    ):
                        with open(dst, "wb") as out:
                            writer = _BodyWriter(out)
                            closed = scanner.skip_past(b"\n" + delimiter, writer)
                            writer.close()
                        if not closed:
                            raise DownloadError(
                                f"WCS: odpowiedz multipart urwana w czesci "
                                f"{ASC_MEDIA_TYPE} ({src.name})"
                            )
                        found = True
                        break
                    if not scanner.skip_past(delimiter):
                        break
    except BaseException:
        dst.unlink(missing_ok=True)
        raise
    if not found:
        raise DownloadError(
            f"WCS: brak czesci {ASC_MEDIA_TYPE} w odpowiedzi multipart; "
            f"poczatek tresci: {_head(src)!r}"
        )
    return dst


def _check_geometry(src: DatasetReader, expect: Chunk) -> None:
    """``DownloadError`` when the ASC header does not describe ``expect``."""
    if (src.width, src.height) != (expect.width, expect.height):
        raise DownloadError(
            f"WCS: ASC ma ncols x nrows {src.width} x {src.height}, "
            f"oczekiwano {expect.width} x {expect.height}"
        )
    step_x = (expect.bbox.max_x - expect.bbox.min_x) / expect.width
    step_y = (expect.bbox.max_y - expect.bbox.min_y) / expect.height
    t = src.transform
    tol = _GRID_TOL_PX * max(step_x, step_y)
    if abs(t.a - step_x) > tol or abs(-t.e - step_y) > tol:
        raise DownloadError(
            f"WCS: ASC ma cellsize {t.a} x {-t.e}, oczekiwano {step_x} x {step_y}"
        )
    xll, yll = t.c, t.f + t.e * src.height
    if abs(xll - expect.bbox.min_x) > tol or abs(yll - expect.bbox.min_y) > tol:
        raise DownloadError(
            f"WCS: ASC ma xllcorner/yllcorner {xll}/{yll}, oczekiwano "
            f"{expect.bbox.min_x}/{expect.bbox.min_y}"
        )


def asc_to_gtiff(
    asc: Path, tif: Path, *, expect: Chunk, crs: str = "EPSG:2180"
) -> Path:
    """ASC -> float32 GeoTIFF with a forced CRS; size and corner checked first.

    ``ncols``/``nrows``, ``cellsize`` and ``xllcorner``/``yllcorner`` must match
    ``expect`` (within ``_GRID_TOL_PX`` of a pixel) - otherwise ``DownloadError``
    and no ``tif``. The CRS is ``crs`` (a ``.prj`` of the response is ESRI WKT
    and is ignored, like ``assign_crs`` of sheets); no nodata is declared (the
    service declares none). The raster is read whole - callers bound its size
    by chunk limits. Written atomically (temporary file + ``os.replace``).
    """
    asc, tif = Path(asc), Path(tif)
    tmp = tif.with_name(f"{tif.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    try:
        with rasterio.open(asc, driver="AAIGrid") as src:
            _check_geometry(src, expect)
            data = src.read(1).astype("float32", copy=False)
            profile = {
                "driver": "GTiff",
                "width": src.width,
                "height": src.height,
                "count": 1,
                "dtype": "float32",
                "crs": crs,
                "transform": src.transform,
                "nodata": None,
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
            }
        with rasterio.open(tmp, "w", **profile) as dst:
            dst.write(data, 1)
        os.replace(tmp, tif)
    except RasterioError as e:
        raise DownloadError(f"WCS: nieczytelny plik ASC {asc.name}: {e}") from e
    finally:
        tmp.unlink(missing_ok=True)
        Path(f"{asc}.aux.xml").unlink(missing_ok=True)
    return tif


def save_multipart_asc(
    expect: Chunk, *, crs: str = "EPSG:2180", chunk_size: int = _BUF
) -> Callable[[requests.Response, Path], Path]:
    """``download_to(save=...)`` hook for a multipart ``image/x-aaigrid`` response.

    Streams the body to ``<out>.<pid>_<tid>.mime``, extracts the ASC part,
    converts it to a float32 GeoTIFF at ``<out>`` and removes the intermediate
    files in any case. A content error is ``DownloadError`` (not retried by
    ``download_to``); an interrupted stream stays a ``RequestException``.
    """

    def save(response: requests.Response, output_path: Path) -> Path:
        output_path = Path(output_path)
        stem = f"{output_path.name}.{os.getpid()}_{threading.get_ident()}"
        mime = output_path.with_name(f"{stem}.mime")
        asc = output_path.with_name(f"{stem}.asc")
        try:
            with open(mime, "wb") as f:
                for block in response.iter_content(chunk_size):
                    if block:
                        f.write(block)
            extract_multipart_asc(mime, response.headers.get("Content-Type", ""), asc)
            return asc_to_gtiff(asc, output_path, expect=expect, crs=crs)
        finally:
            mime.unlink(missing_ok=True)
            asc.unlink(missing_ok=True)

    return save
