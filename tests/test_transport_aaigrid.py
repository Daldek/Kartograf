"""Tests for transport/aaigrid.py on recorded GUGiK WCS multipart responses."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.transport.aaigrid import (
    asc_to_gtiff,
    extract_multipart_asc,
    save_multipart_asc,
)
from kartograf.transport.chunks import Chunk
from tests.conftest import WCS_FIXTURES, recorded_response

NMT = WCS_FIXTURES / "nmt_evrf2007_20x20.mime"
NMT_CHUNK = Chunk(BBox(567580.5, 243664.5, 567600.5, 243684.5, "EPSG:2180"), 20, 20)


def _content_type(path: Path) -> str:
    meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
    return meta["Content-Type"]


def _convert(tmp_path: Path, expect: Chunk = NMT_CHUNK) -> Path:
    asc = extract_multipart_asc(NMT, _content_type(NMT), tmp_path / "part.asc")
    return asc_to_gtiff(asc, tmp_path / "out.tif", expect=expect)


def test_extract_and_convert_recorded_nmt_evrf2007(tmp_path):
    tif = _convert(tmp_path)

    with rasterio.open(tif) as src:
        assert (src.width, src.height, src.count) == (20, 20, 1)
        assert src.dtypes == ("float32",)
        assert src.crs.to_epsg() == 2180
        assert src.nodata is None
        assert (src.transform.c, src.transform.f) == (567580.5, 243684.5)
        assert (src.transform.a, src.transform.e) == (1.0, -1.0)
        values = src.read(1)
    reference = np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
    assert np.array_equal(values, reference)


def test_multipart_without_asc_part_raises(tmp_path):
    # the recorded body with the ASC part relabelled: only octet-stream parts left
    body = NMT.read_bytes().replace(
        b"Content-Type: image/x-aaigrid", b"Content-Type: application/octet-stream"
    )
    src = tmp_path / "body.mime"
    src.write_bytes(body)
    dst = tmp_path / "part.asc"

    with pytest.raises(DownloadError, match="image/x-aaigrid") as exc:
        extract_multipart_asc(src, _content_type(NMT), dst)

    assert "--wcs" in str(exc.value)  # beginning of the body for diagnosis
    assert not dst.exists()


def test_asc_size_mismatch_raises(tmp_path):
    wider = Chunk(BBox(567580.5, 243664.5, 567601.5, 243684.5, "EPSG:2180"), 21, 20)

    with pytest.raises(DownloadError, match="ncols"):
        _convert(tmp_path, wider)

    assert not (tmp_path / "out.tif").exists()


def test_asc_corner_mismatch_raises(tmp_path):
    shifted = Chunk(BBox(567580.75, 243664.5, 567600.75, 243684.5, "EPSG:2180"), 20, 20)

    with pytest.raises(DownloadError, match="xllcorner"):
        _convert(tmp_path, shifted)

    assert not (tmp_path / "out.tif").exists()


def test_save_hook_cleans_intermediate_files(tmp_path):
    ok_dir, bad_dir = tmp_path / "ok", tmp_path / "bad"
    ok_dir.mkdir()
    bad_dir.mkdir()

    saved = save_multipart_asc(NMT_CHUNK)(recorded_response(NMT), ok_dir / "a.tif")
    assert saved == ok_dir / "a.tif"
    assert sorted(p.name for p in ok_dir.iterdir()) == ["a.tif"]

    shifted = Chunk(BBox(567581.5, 243664.5, 567601.5, 243684.5, "EPSG:2180"), 20, 20)
    with pytest.raises(DownloadError):
        save_multipart_asc(shifted)(recorded_response(NMT), bad_dir / "a.tif")
    assert list(bad_dir.iterdir()) == []


def test_boundary_from_quoted_content_type(tmp_path):
    quoted = _content_type(NMT).replace("boundary=wcs", 'boundary="wcs"')
    assert quoted != _content_type(NMT)

    asc = extract_multipart_asc(NMT, quoted, tmp_path / "part.asc")
    tif = asc_to_gtiff(asc, tmp_path / "out.tif", expect=NMT_CHUNK)

    with rasterio.open(tif) as src:
        values = src.read(1)
    reference = np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
    assert np.array_equal(values, reference)


def test_lf_only_multipart(tmp_path):
    """A body with LF line breaks (no CR) yields the same ASC."""
    src = tmp_path / "lf.mime"
    src.write_bytes(NMT.read_bytes().replace(b"\r\n", b"\n"))

    asc = extract_multipart_asc(src, _content_type(NMT), tmp_path / "part.asc")
    tif = asc_to_gtiff(asc, tmp_path / "out.tif", expect=NMT_CHUNK)

    with rasterio.open(tif) as out:
        values = out.read(1)
    assert np.array_equal(
        values, np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
    )


def test_truncated_asc_part_raises(tmp_path):
    """A body cut inside the ASC part (no closing delimiter) is a DownloadError,
    not a short raster; the partial ASC is not left behind."""
    body = NMT.read_bytes()
    src = tmp_path / "cut.mime"
    src.write_bytes(body[: body.index(b"result.asc.aux.xml") - 200])
    dst = tmp_path / "part.asc"

    with pytest.raises(DownloadError, match="urwana"):
        extract_multipart_asc(src, _content_type(NMT), dst)

    assert not dst.exists()


@pytest.mark.parametrize("buffer", [1, 3, 7, 64])
def test_small_buffer_splits_delimiters(tmp_path, monkeypatch, buffer):
    """Delimiters and part headers cut across buffer reads give the same ASC."""
    import kartograf.transport.aaigrid as aaigrid

    whole = extract_multipart_asc(NMT, _content_type(NMT), tmp_path / "whole.asc")
    monkeypatch.setattr(aaigrid, "_BUF", buffer)

    small = extract_multipart_asc(NMT, _content_type(NMT), tmp_path / "small.asc")

    assert small.read_bytes() == whole.read_bytes()
    assert small.read_bytes().startswith(b"ncols")
    assert small.read_bytes().endswith(b"203.6199951171875\n")
