"""Testy mozaikowania (kartograf.transport.mosaic) na syntetycznych rastrach."""

import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.merge import merge as rasterio_merge
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.transport.mosaic import mosaic_and_crop


def _write_tile(
    path: Path,
    origin_x: float,
    origin_y: float,
    value: float,
    size: int = 10,
    res: float = 1.0,
    crs: str = "EPSG:2180",
    nodata: float | None = None,
) -> Path:
    data = np.full((size, size), value, dtype="float32")
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": from_origin(origin_x, origin_y, res, res),
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


def _write_asc(path, xll, yll, ncols=4, nrows=4, cellsize=1.0, value=1.0):
    """Syntetyczny Arc/Info ASCII Grid (bez CRS — jak arkusze GUGiK)."""
    header = (
        f"ncols {ncols}\nnrows {nrows}\nxllcorner {xll}\nyllcorner {yll}\n"
        f"cellsize {cellsize}\nNODATA_value -9999\n"
    )
    rows = "\n".join(" ".join(str(value) for _ in range(ncols)) for _ in range(nrows))
    path.write_text(header + rows + "\n", encoding="ascii")
    return path


def _write_lattice_tile(path, col0, row0, cols, rows, *, x0=0.5, y_top=100.5, res=1.0):
    """Kafel na siatce z narozami w x0 + k*res — jak arkusze GUGiK, ktorych
    narozniki leza pol piksela od liczb calkowitych (fakt 1 planu).
    Wartosc = 1000 * globalny_wiersz + globalna_kolumna: jednoznaczna, wiec
    kazde przesuniecie tresci widac jako rozbieznosc wartosci."""
    transform = rasterio.transform.from_origin(
        x0 + col0 * res, y_top - row0 * res, res, res
    )
    r, c = np.meshgrid(np.arange(rows) + row0, np.arange(cols) + col0, indexing="ij")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype="float32",
        crs="EPSG:2180",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write((1000.0 * r + c).astype("float32"), 1)
    return path


@pytest.fixture
def four_tiles(tmp_path):
    # Kafle 2x2 (kazdy 10x10 m, res 1 m): wspolny naroznik w (10, 10).
    return [
        _write_tile(tmp_path / "a.tif", 0, 20, 1.0),  # NW
        _write_tile(tmp_path / "b.tif", 10, 20, 2.0),  # NE
        _write_tile(tmp_path / "c.tif", 0, 10, 3.0),  # SW
        _write_tile(tmp_path / "d.tif", 10, 10, 4.0),  # SE
    ]


class TestMosaicAndCrop:
    def test_merge_and_crop_to_bbox(self, four_tiles, tmp_path):
        out = mosaic_and_crop(
            four_tiles,
            BBox(5.0, 5.0, 15.0, 15.0, "EPSG:2180"),
            tmp_path / "out.tif",
        )
        with rasterio.open(out) as src:
            assert src.width == 10 and src.height == 10
            assert src.bounds == pytest.approx((5.0, 5.0, 15.0, 15.0))
            data = src.read(1)
        # Cwiartki wyniku pochodza z 4 roznych kafli.
        assert data[0, 0] == 1.0 and data[0, -1] == 2.0
        assert data[-1, 0] == 3.0 and data[-1, -1] == 4.0

    def test_nodata_propagated_never_zeroed(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, nodata=-9999.0),
        ]
        out = mosaic_and_crop(
            tiles,
            BBox(0.0, 0.0, 20.0, 10.0, "EPSG:2180"),
            tmp_path / "out.tif",
            nodata=-9999.0,
        )
        with rasterio.open(out) as src:
            assert src.nodata == -9999.0
            data = src.read(1)
        # Obszar bez pokrycia (x 10..20) = nodata, NIE 0.
        assert data[0, -1] == -9999.0

    def test_mosaic_passes_dst_path_to_merge(self, four_tiles, tmp_path):
        """merge ma pisac wynik sam (kawalkami wg mem_limit).

        Bez dst_path rasterio trzyma caly wynik w jednej tablicy — szczyt
        RAM 2,63x rozmiaru danych, czyli ~2,4 GB dla zlewni 30x30 km przy
        DMR 5G (A3-4).
        """
        out_path = tmp_path / "out.tif"
        with patch(
            "kartograf.transport.mosaic.merge", wraps=rasterio_merge
        ) as merge_spy:
            mosaic_and_crop(
                four_tiles, BBox(5.0, 5.0, 15.0, 15.0, "EPSG:2180"), out_path
            )
        assert merge_spy.call_args.kwargs["dst_path"] == str(out_path)

    def test_empty_inputs_raise(self, tmp_path):
        with pytest.raises(ValidationError):
            mosaic_and_crop([], BBox(0, 0, 1, 1, "EPSG:2180"), tmp_path / "out.tif")

    def test_crs_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, crs="EPSG:2180"),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, crs="EPSG:2177"),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )

    def test_resolution_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, res=1.0),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, res=2.0),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )


def test_dst_kwds_forces_gtiff_and_crs(tmp_path):
    """Wejscia ASC (AAIGrid, brak CRS) -> wynik GTiff z wpisanym CRS."""
    a = _write_asc(tmp_path / "a.asc", 0, 0)
    b = _write_asc(tmp_path / "b.asc", 4, 0)
    out = tmp_path / "out.tif"

    mosaic_and_crop(
        [a, b],
        BBox(1, 1, 7, 3, "EPSG:2180"),
        out,
        nodata=-9999.0,
        dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
    )

    with rasterio.open(out) as ds:
        assert ds.driver == "GTiff"
        assert ds.crs is not None and ds.crs.to_epsg() == 2180
        assert ds.nodata == -9999.0
        assert ds.bounds == (1.0, 1.0, 7.0, 3.0)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc/self/fd")
def test_many_inputs_do_not_exhaust_file_descriptors(tmp_path):
    """Zn. 3 review max: wycinek 75 x 75 km to >1200 arkuszy, a limit
    deskryptorow to 1024 (Linux) / 256 (macOS). Mozaika nie moze trzymac
    otwartych wszystkich zrodel naraz."""
    import resource

    n = 300
    paths = [
        _write_tile(tmp_path / f"t{i:03d}.tif", 2 * i, 2, float(i), size=2)
        for i in range(n)
    ]
    # rozgrzewka: pierwsze otwarcie rastra otwiera na stale proj.db (+1 fd)
    with rasterio.open(paths[0]) as src:
        _ = src.crs
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    in_use = len(os.listdir("/proc/self/fd"))
    resource.setrlimit(resource.RLIMIT_NOFILE, (in_use + 64, hard))
    try:
        out = mosaic_and_crop(
            paths, BBox(0, 0, 2 * n, 2, "EPSG:2180"), tmp_path / "out.tif"
        )
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))

    with rasterio.open(out) as src:
        data = src.read(1)
    assert data.shape == (2, 2 * n)
    assert data[0, 0] == 0.0
    assert data[0, 2 * n - 1] == float(n - 1)


@pytest.mark.parametrize(
    "bbox",
    [
        BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
        BBox(3.0, 92.0, 17.0, 98.0, "EPSG:2180"),  # calkowity = remis 0,5 px
    ],
    ids=["ulamkowy", "calkowity"],
)
def test_snap_copies_source_pixels_exactly(tmp_path, bbox):
    """Zn. 1: piksele wyniku = piksele zrodel (bez przesuniecia i bez
    mieszania kolumn przy remisie); zasieg = zadanie + < 1 px na strone."""
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10)  # zakladka 2 px
    out = mosaic_and_crop(
        [a, b], bbox, tmp_path / "out.tif", nodata=-9999.0, snap_to_source_grid=True
    )
    with rasterio.open(out) as src:
        t, data = src.transform, src.read(1)
        left, bottom, right, top = src.bounds

    col0, row0 = t.c - 0.5, 100.5 - t.f
    assert col0 == pytest.approx(round(col0), abs=1e-9)
    assert row0 == pytest.approx(round(row0), abs=1e-9)
    assert left <= bbox.min_x < left + 1.0 and right - 1.0 < bbox.max_x <= right
    assert bottom <= bbox.min_y < bottom + 1.0 and top - 1.0 < bbox.max_y <= top
    r, c = np.meshgrid(
        np.arange(data.shape[0]) + round(row0),
        np.arange(data.shape[1]) + round(col0),
        indexing="ij",
    )
    np.testing.assert_array_equal(data, (1000.0 * r + c).astype("float32"))


def test_snap_uses_majority_grid_and_warns(tmp_path, caplog):
    """Zrodlo poza siatka nie wetuje mozaiki (arkusze sa w cache — blad
    bylby trwaly); siatka = wiekszosc, nie 'pierwsze na liscie'."""
    odd = _write_lattice_tile(tmp_path / "odd.tif", 20, 0, 4, 10, x0=0.75)
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10)
    with caplog.at_level(logging.WARNING, logger="kartograf.transport.mosaic"):
        out = mosaic_and_crop(
            [odd, a, b],
            BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
            tmp_path / "o.tif",
            snap_to_source_grid=True,
        )
    with rasterio.open(out) as src:
        phase = src.transform.c - 0.5
        assert phase == pytest.approx(round(phase), abs=1e-9)
    assert "odd.tif" in caplog.text and "0.250" in caplog.text


def test_snap_keeps_bbox_already_on_grid(tmp_path):
    """3 * 0.1 == 0.30000000000000004: iloraz 3.0000000000000004 nie moze
    dolozyc czwartej kolumny (tolerancja bledu zmiennoprzecinkowego)."""
    a = _write_lattice_tile(
        tmp_path / "a.tif", 0, 0, 10, 10, x0=0.0, y_top=1.0, res=0.1
    )
    out = mosaic_and_crop(
        [a],
        BBox(0.0, 0.5, 3 * 0.1, 1.0, "EPSG:2180"),
        tmp_path / "o.tif",
        snap_to_source_grid=True,
    )
    with rasterio.open(out) as src:
        assert (src.width, src.height) == (3, 5)


def test_snap_rejects_rotated_source(tmp_path):
    from affine import Affine

    path = tmp_path / "rot.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="float32",
        crs="EPSG:2180",
        transform=Affine(1.0, 0.1, 0.0, 0.1, -1.0, 4.0),
    ) as dst:
        dst.write(np.ones((4, 4), dtype="float32"), 1)
    with pytest.raises(ValidationError, match="obrocona"):
        mosaic_and_crop(
            [path],
            BBox(0, 0, 4, 4, "EPSG:2180"),
            tmp_path / "o.tif",
            snap_to_source_grid=True,
        )
