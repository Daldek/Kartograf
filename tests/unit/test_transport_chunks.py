"""Tests for transport/chunks.py: alignment, chunk plan, fetch and stitch."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.transport.chunks import (
    Chunk,
    ChunkLimits,
    GridSpec,
    align_bbox,
    fetch_chunks,
    plan_chunks,
)

GUGIK_1M = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)


def _global_values(bbox: BBox, origin: BBox, res: float) -> np.ndarray:
    """Pixel values 1000 * global_row + global_column for ``bbox`` inside ``origin``."""
    col0 = round((bbox.min_x - origin.min_x) / res)
    row0 = round((origin.max_y - bbox.max_y) / res)
    width = round((bbox.max_x - bbox.min_x) / res)
    height = round((bbox.max_y - bbox.min_y) / res)
    rows = np.arange(row0, row0 + height)[:, None]
    cols = np.arange(col0, col0 + width)[None, :]
    return (1000 * rows + cols).astype("float32")


def _writer(origin: BBox, res: float, calls: list[Path]):
    def fetch(chunk: Chunk, path: Path) -> None:
        calls.append(path)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=chunk.width,
            height=chunk.height,
            count=1,
            dtype="float32",
            crs="EPSG:2180",
            transform=from_origin(chunk.bbox.min_x, chunk.bbox.max_y, res, res),
        ) as dst:
            dst.write(_global_values(chunk.bbox, origin, res), 1)

    return fetch


class TestAlignBbox:
    def test_align_snaps_outward_to_grid(self):
        aligned, w, h = align_bbox(
            BBox(450000, 550000, 460000, 560000, "EPSG:2180"), 1.0, GUGIK_1M
        )
        assert (aligned.min_x, aligned.min_y, aligned.max_x, aligned.max_y) == (
            449999.5,
            549999.5,
            460000.5,
            560000.5,
        )
        assert (w, h) == (10001, 10001)
        assert aligned.crs == "EPSG:2180"

        frac, w, h = align_bbox(
            BBox(450000.7, 550000.2, 450010.2, 550003.9, "EPSG:2180"), 1.0, GUGIK_1M
        )
        assert (frac.min_x, frac.max_x) == (450000.5, 450010.5)
        assert (frac.min_y, frac.max_y) == (549999.5, 550004.5)
        assert (w, h) == (10, 5)

    @pytest.mark.parametrize("noise", [1e-9, -1e-9])
    def test_align_on_grid_within_tolerance_adds_nothing(self, noise):
        aligned, w, h = align_bbox(
            BBox(100.5 + noise, 200.5 - noise, 110.5 - noise, 205.5 + noise, "X"),
            1.0,
            GUGIK_1M,
        )
        assert (w, h) == (10, 5)
        assert aligned.min_x == pytest.approx(100.5, abs=1e-12)
        assert aligned.max_y == pytest.approx(205.5, abs=1e-12)

    def test_align_without_grid_keeps_nw_anchor_rule(self):
        """CZ exportImage rule: NW corner kept, whole pixel count by round."""
        aligned, w, h = align_bbox(BBox(0.0, 0.0, 1000.7, 181.4, "EPSG:5514"), 2.0)
        assert (w, h) == (500, 91)
        assert aligned.min_x == 0.0 and aligned.max_y == 181.4
        assert aligned.max_x == 1000.0
        assert aligned.min_y == pytest.approx(181.4 - 91 * 2.0)

    def test_align_rejects_pixel_size_other_than_grid_step(self):
        with pytest.raises(ValidationError, match="source grid step"):
            align_bbox(BBox(0, 0, 10, 10, "X"), 0.5, GUGIK_1M)


class TestPlanChunks:
    @pytest.mark.parametrize(
        ("width", "height"), [(5000, 5000), (1800, 12300), (50000, 50), (8, 8)]
    )
    def test_plan_chunks_respects_budget_and_covers_request(self, width, height):
        bbox = BBox(0.3, 100.7 - height * 2, 0.3 + width * 2, 100.7, "EPSG:5514")
        limits = ChunkLimits(15000, 4100, 4_000_000)
        chunks = plan_chunks(bbox, width, height, 2.0, limits)
        assert sum(c.width * c.height for c in chunks) == width * height
        assert chunks[0].bbox.min_x == bbox.min_x
        assert chunks[0].bbox.max_y == bbox.max_y
        for index, chunk in enumerate(chunks):
            tile = chunk.bbox
            assert 0 < chunk.width <= 15000 and 0 < chunk.height <= 4100
            assert chunk.width * chunk.height <= 4_000_000
            assert tile.max_x - tile.min_x == pytest.approx(chunk.width * 2)
            assert tile.max_y - tile.min_y == pytest.approx(chunk.height * 2)
            assert bbox.min_x <= tile.min_x < tile.max_x <= bbox.max_x
            assert bbox.min_y <= tile.min_y < tile.max_y <= bbox.max_y
            for other in chunks[index + 1 :]:
                o = other.bbox
                assert (
                    tile.max_x <= o.min_x
                    or o.max_x <= tile.min_x
                    or tile.max_y <= o.min_y
                    or o.max_y <= tile.min_y
                )

    def test_plan_chunks_single_chunk_within_limits(self):
        bbox = BBox(0, 0, 20, 10, "X")
        assert plan_chunks(bbox, 20, 10, 1.0, ChunkLimits(20, 10, 200)) == [
            Chunk(bbox, 20, 10)
        ]

    def test_plan_chunks_multiple_keeps_every_chunk_even(self):
        """``multiple=2``: every chunk even-sized (budget 1 Mpx, isqrt = 1000)."""
        bbox = BBox(0.5, 0.5, 0.5 + 2502, 0.5 + 1202, "EPSG:2180")
        chunks = plan_chunks(
            bbox, 2502, 1202, 1.0, ChunkLimits(40_000, 40_000, 1_000_000), multiple=2
        )
        assert all(c.width % 2 == 0 and c.height % 2 == 0 for c in chunks)
        assert all(c.width * c.height <= 1_000_000 for c in chunks)
        assert sum(c.width for c in chunks if c.bbox.max_y == bbox.max_y) == 2502
        assert sum(c.height for c in chunks if c.bbox.min_x == bbox.min_x) == 1202
        with pytest.raises(ValidationError, match="is not a multiple of"):
            plan_chunks(bbox, 2501, 1202, 1.0, ChunkLimits(10, 10, 100), multiple=2)


class TestFetchChunks:
    def test_fetch_chunks_single_writes_rootectly(self, tmp_path):
        bbox = BBox(0, 0, 8, 6, "EPSG:2180")
        calls: list[Path] = []
        out = tmp_path / "one.tif"
        fetch_chunks([Chunk(bbox, 8, 6)], bbox, out, _writer(bbox, 1.0, calls))
        assert calls == [out]
        assert list(tmp_path.glob("*.part*")) == []

    def test_fetch_chunks_mosaics_bit_exact(self, tmp_path, caplog):
        """Striped chunks (like GUGiK WCS GeoTIFF) -> bit-exact, tiled result,
        without GDAL's BLOCKXSIZE-without-TILED warning."""
        bbox = BBox(0.5, 0.5, 8.5, 6.5, "EPSG:2180")
        chunks = plan_chunks(bbox, 8, 6, 1.0, ChunkLimits(4, 3, 1000))
        assert len(chunks) == 4
        calls: list[Path] = []
        with caplog.at_level("WARNING"):
            out = fetch_chunks(
                chunks, bbox, tmp_path / "m.tif", _writer(bbox, 1.0, calls)
            )
        assert len(calls) == 4 and out not in calls
        with rasterio.open(out) as src:
            np.testing.assert_array_equal(src.read(1), _global_values(bbox, bbox, 1.0))
            assert src.transform == from_origin(0.5, 6.5, 1.0, 1.0)
            assert src.shape == (6, 8)
            assert src.profile["tiled"] is True
        assert not [r for r in caplog.records if "BLOCKXSIZE" in r.getMessage()]
        assert list(tmp_path.glob("*.part*")) == []

    def test_fetch_chunks_cleans_parts_on_fetch_error(self, tmp_path):
        bbox = BBox(0, 0, 8, 6, "EPSG:2180")
        chunks = plan_chunks(bbox, 8, 6, 1.0, ChunkLimits(4, 3, 1000))
        calls: list[Path] = []
        write = _writer(bbox, 1.0, calls)

        def fetch(chunk: Chunk, path: Path) -> None:
            if calls:
                path.write_bytes(b"partial")
                raise DownloadError("zerwane polaczenie")
            write(chunk, path)

        out = tmp_path / "m.tif"
        with pytest.raises(DownloadError, match="zerwane"):
            fetch_chunks(chunks, bbox, out, fetch)
        assert not out.exists()
        assert list(tmp_path.glob("*.part*")) == []

    def test_fetch_chunks_stitch_failure_is_download_error(self, tmp_path):
        bbox = BBox(0, 0, 8, 6, "EPSG:2180")
        chunks = plan_chunks(bbox, 8, 6, 1.0, ChunkLimits(4, 3, 1000))

        def fetch(chunk: Chunk, path: Path) -> None:
            path.write_bytes(b"II*\x00" + b"\x00" * 64)

        out = tmp_path / "m.tif"
        with pytest.raises(DownloadError, match="failed to stitch"):
            fetch_chunks(chunks, bbox, out, fetch)
        assert not out.exists()
        assert list(tmp_path.glob("*.part*")) == []
