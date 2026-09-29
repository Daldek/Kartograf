"""Testy mozaikowania (kartograf.transport.mosaic) na syntetycznych rastrach."""

import math
import os
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from pyproj import CRS
from rasterio.merge import merge as rasterio_merge
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import GridMismatchError, ValidationError
from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop


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


def test_snap_rejects_off_grid_source(tmp_path):
    """S5 (D3): zrodlo poza siatka wiekszosci = GridMismatchError z lista
    przesuniec, nie ostrzezenie — ``merge`` przepisywalby je "przez okno"
    (nie zawsze z najblizszego piksela, kolumna nodata na szwie); siatka
    odniesienia to wiekszosc, nie 'pierwsze na liscie'. Bez pliku wyniku."""
    odd = _write_lattice_tile(tmp_path / "odd.tif", 20, 0, 4, 10, x0=0.75)
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10)
    expected = r"1 z 3 zrodel .*0\.250 px.*odd\.tif"
    with pytest.raises(GridMismatchError, match=expected) as e:
        mosaic_and_crop(
            [odd, a, b],
            BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
            tmp_path / "o.tif",
            snap_to_source_grid=True,
        )
    assert isinstance(e.value, ValidationError)
    (source,) = e.value.off_grid
    assert source.path == odd
    assert (source.dx_px, source.dy_px) == pytest.approx((0.25, 0.0))
    assert not (tmp_path / "o.tif").exists()


def test_snap_tolerates_float_noise(tmp_path):
    """Dwa kafle rozniace sie o 1e-9 px to JEDNA siatka: porownanie faz
    z tolerancja, nie rownosc kubelkow (szumy po dwu stronach granicy kubelka
    nie moga dac falszywego bledu twardego)."""
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10, x0=0.0)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10, x0=1e-9)
    assert check_source_grid([a, b]).off_grid == ()
    out = mosaic_and_crop(
        [a, b],
        BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
        tmp_path / "o.tif",
        snap_to_source_grid=True,
    )
    with rasterio.open(out) as src:
        assert src.transform.c == pytest.approx(3.0, abs=1e-9)


def test_check_source_grid_wraps_phase_through_one(tmp_path):
    """Faza 0,9999999 i faza 0 to ta sama siatka (owiniecie przez 1) —
    takze wtedy, gdy zrodlo odniesienia ma faze 0."""
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10, x0=0.0)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10, x0=-1e-8)
    c = _write_lattice_tile(tmp_path / "c.tif", 20, 0, 12, 10, x0=0.0)
    grid = check_source_grid([a, b, c])
    assert grid.off_grid == ()
    assert grid.reference.c == 0.0


def test_check_source_grid_reports_shift_of_every_off_grid_source(tmp_path):
    """Przesuniecia w [-0,5; 0,5) wzgledem siatki WIEKSZOSCI, w obu osiach."""
    on1 = _write_lattice_tile(tmp_path / "on1.tif", 0, 0, 12, 10)
    on2 = _write_lattice_tile(tmp_path / "on2.tif", 10, 0, 12, 10)
    west = _write_lattice_tile(tmp_path / "west.tif", 20, 0, 4, 10, x0=0.5 - 0.3)
    south = _write_lattice_tile(tmp_path / "south.tif", 0, 10, 4, 4, y_top=100.5 + 0.4)
    grid = check_source_grid([west, on1, south, on2])
    assert grid.reference.c == 0.5
    shifts = {s.path.name: (s.dx_px, s.dy_px) for s in grid.off_grid}
    assert shifts.keys() == {"west.tif", "south.tif"}
    assert shifts["west.tif"] == pytest.approx((-0.3, 0.0))
    assert shifts["south.tif"] == pytest.approx((0.0, 0.4))
    assert math.isclose(max(max(abs(dx), abs(dy)) for dx, dy in shifts.values()), 0.4)


def test_check_source_grid_rejects_mixed_resolution(tmp_path):
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 0, 0, 12, 10, res=0.5)
    with pytest.raises(ValidationError, match="rozdzielczosci"):
        check_source_grid([a, b])


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


def _write_asc_text(path, xll, yll, rows, *, cellsize=1.0, nodata_header="-9999"):
    """ASC jak u GUGiK: naglowek z `nodata_value -9999` BEZ kropki (fakt 5)."""
    header = (
        f"ncols {len(rows[0])}\nnrows {len(rows)}\nxllcorner {xll}\n"
        f"yllcorner {yll}\ncellsize {cellsize}\nnodata_value {nodata_header}\n"
    )
    path.write_text(header + "\n".join(" ".join(r) for r in rows) + "\n")
    return path


def _write_prj(asc_path, wkt_text):
    asc_path.with_suffix(".prj").write_text(wkt_text)


_HYDROGRAF_2180_WKT = (  # tresc .prj z cache Hydrografu (gdalsrsinfo -o wkt_simple)
    'PROJCS["ETRF2000-PL / CS92",GEOGCS["ETRF2000-PL",DATUM["ETRF2000_Poland",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",19],'
    'PARAMETER["scale_factor",0.9993],PARAMETER["false_easting",500000],'
    'PARAMETER["false_northing",-5300000],UNIT["metre",1]]'
)

# P-01: kazdy z tych trzech WKT1 opisuje EPSG:2180, ale samo CRS.equals(...,
# ignore_axis_order=True) zwraca dla wszystkich False (pyproj 3.7.2 / PROJ 9.5.1,
# zmierzone 2026-09-28) — stad _same_projection w Step 3.
_2180_WKT_VARIANTS = [
    CRS.from_epsg(2180).to_wkt("WKT1_GDAL"),
    CRS.from_epsg(2180).to_wkt("WKT1_ESRI"),
    _HYDROGRAF_2180_WKT,
]


@pytest.mark.parametrize(
    "prj_text", _2180_WKT_VARIANTS, ids=["wkt1_gdal", "wkt1_esri", "hydrograf"]
)
def test_assign_crs_merges_sources_with_and_without_prj(tmp_path, prj_text):
    """Fakt 6: Hydrograf dopisuje .prj do czesci arkuszy; merge rzucal
    'CRS mismatch'. Z assign_crs zrodla dostaja jawny SRS przez VRT.
    Wszystkie trzy warianty WKT1 EPSG:2180 (pyproj GDAL/ESRI, .prj Hydrografu)
    musza zostac uznane za "ten sam" uklad (P-01)."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * 4] * 4)
    b = _write_asc_text(tmp_path / "b.asc", 4.5, 0.5, [["2.5"] * 4] * 4)
    _write_prj(a, prj_text)
    with rasterio.open(a) as sa, rasterio.open(b) as sb:
        assert sa.crs is not None and sb.crs is None  # warunek sensownosci testu
    bbox = BBox(0.5, 0.5, 8.5, 4.5, "EPSG:2180")
    with pytest.raises(ValidationError, match="niezgodne CRS"):
        mosaic_and_crop([a, b], bbox, tmp_path / "x.tif")
    out = mosaic_and_crop([a, b], bbox, tmp_path / "o.tif", assign_crs="EPSG:2180")
    with rasterio.open(out) as src:
        data = src.read(1)
        assert src.crs.to_epsg() == 2180
        assert src.driver == "GTiff"  # profil z pierwszego zrodla to VRT
    assert data[0, 0] == 1.5 and data[0, -1] == 2.5


def test_assign_crs_rejects_source_with_other_crs(tmp_path):
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * 4] * 4)
    _write_prj(a, CRS.from_epsg(2177).to_wkt("WKT1_GDAL"))
    with pytest.raises(ValidationError, match="wymuszany"):
        mosaic_and_crop(
            [a],
            BBox(0.5, 0.5, 4.5, 4.5, "EPSG:2180"),
            tmp_path / "o.tif",
            assign_crs="EPSG:2180",
        )


def test_dtype_float32_keeps_decimals_when_first_source_is_integer(tmp_path):
    """Fakt 5: ASC z samymi liczbami calkowitymi GDAL czyta jako Int32,
    a merge bierze dtype z PIERWSZEGO zrodla — wysokosci innych arkuszy
    bylyby obciete."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["100"] * 4] * 4)
    b = _write_asc_text(tmp_path / "b.asc", 4.5, 0.5, [["100.25"] * 4] * 4)
    with rasterio.open(a) as sa:
        assert sa.dtypes[0] == "int32"  # warunek sensownosci testu
    out = mosaic_and_crop(
        [a, b],
        BBox(0.5, 0.5, 8.5, 4.5, "EPSG:2180"),
        tmp_path / "o.tif",
        assign_crs="EPSG:2180",
        dtype="float32",
    )
    with rasterio.open(out) as src:
        data = src.read(1)
        assert src.dtypes[0] == "float32"
    assert data[0, -1] == pytest.approx(100.25)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc/self/fd")
def test_vrt_wrapping_does_not_exhaust_file_descriptors(tmp_path):
    """Owijanie w VRT tez nie moze trzymac otwartych wszystkich zrodel."""
    import resource

    n = 300
    paths = [
        _write_tile(tmp_path / f"t{i:03d}.tif", 2 * i, 2, float(i), size=2)
        for i in range(n)
    ]
    with rasterio.open(paths[0]) as src:
        _ = src.crs
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    in_use = len(os.listdir("/proc/self/fd"))
    # poprawny kod potrzebuje < 6 deskryptorow; pula GDAL (GDAL_MAX_DATASET_POOL_SIZE,
    # domyslnie 100) maskowalaby "wszystkie VRT naraz" przy zapasie > ~110 (P-05,
    # zmierzone w pre-flight 2026-09-28: mutacja przechodzi przy 160, pada przy 64)
    resource.setrlimit(resource.RLIMIT_NOFILE, (in_use + 64, hard))
    try:
        out = mosaic_and_crop(
            paths,
            BBox(0, 0, 2 * n, 2, "EPSG:2180"),
            tmp_path / "out.tif",
            assign_crs="EPSG:2180",
            dtype="float32",
        )
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    with rasterio.open(out) as src:
        assert src.read(1)[0, 2 * n - 1] == float(n - 1)


def test_wrapping_rejects_multiband_source(tmp_path):
    """VRT owija tylko pasmo 1 — zrodlo wielopasmowe to blad, nie cicha
    utrata pozostalych pasm."""
    path = tmp_path / "rgb.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=2,
        dtype="float32",
        crs="EPSG:2180",
        transform=from_origin(0, 4, 1, 1),
    ) as dst:
        dst.write(np.ones((2, 4, 4), dtype="float32"))
    with pytest.raises(ValidationError, match="pasm"):
        mosaic_and_crop(
            [path], BBox(0, 0, 4, 4, "EPSG:2180"), tmp_path / "o.tif", dtype="float32"
        )


@pytest.mark.parametrize(
    ("source_dtype", "dtype"),
    [("float32", "float16"), ("int8", None)],
    ids=["zadany_typ", "typ_zrodla"],
)
def test_wrapping_rejects_type_without_vrt_name(tmp_path, source_dtype, dtype):
    """Typ spoza mapy typow VRT: ValidationError, nie KeyError."""
    path = tmp_path / "t.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype=source_dtype,
        crs="EPSG:2180",
        transform=from_origin(0, 4, 1, 1),
    ) as dst:
        dst.write(np.ones((1, 4, 4), dtype=source_dtype))
    with rasterio.open(path) as src:
        assert src.dtypes[0] == source_dtype  # warunek sensownosci testu
    with pytest.raises(ValidationError, match="typ pasma"):
        mosaic_and_crop(
            [path],
            BBox(0, 0, 4, 4, "EPSG:2180"),
            tmp_path / "o.tif",
            assign_crs="EPSG:2180",
            dtype=dtype,
        )


def test_wrapping_keeps_each_source_own_nodata(tmp_path):
    """VRT to widok 1:1 — NoDataValue = nodata ZRODLA, nie mozaiki.

    SimpleSource kopiuje piksele doslownie: przy nodata mozaiki innym niz
    nodata zrodla -9999 pierwszego arkusza przestaloby byc maskowane i w
    zakladce (sasiednie arkusze GUGiK zachodza na siebie, fakt 1) przykryloby
    wazne dane drugiego. Owijanie nie moze zmienic wyniku wzgledem mozaiki
    bez owijania.
    """
    a = _write_asc_text(
        tmp_path / "a.asc", 0.5, 0.5, [["1.5", "1.5", "-9999", "-9999"]] * 4
    )
    b = _write_asc_text(tmp_path / "b.asc", 2.5, 0.5, [["2.5"] * 4] * 4)
    bbox = BBox(0.5, 0.5, 6.5, 4.5, "EPSG:2180")
    kwargs = {"nodata": -32768.0, "dst_kwds": {"driver": "GTiff"}}
    plain = mosaic_and_crop([a, b], bbox, tmp_path / "p.tif", **kwargs)
    wrapped = mosaic_and_crop(
        [a, b], bbox, tmp_path / "w.tif", dtype="float32", **kwargs
    )
    with rasterio.open(plain) as p, rasterio.open(wrapped) as w:
        expected = p.read(1)
        data = w.read(1)
        assert w.nodata == -32768.0  # nodata WYNIKU nadal ustawia merge
    assert expected[0].tolist() == [1.5, 1.5, 2.5, 2.5, 2.5, 2.5]
    np.testing.assert_array_equal(data, expected)


@pytest.mark.parametrize(("cols", "rows"), [(200, 100), (460, 50)])
def test_wrapping_writes_short_wide_first_source(tmp_path, cols, rows):
    """Profil wyniku ``merge`` bierze z PIERWSZEGO zrodla, czyli z VRT: bloki
    min(128, szerokosc) x min(128, wysokosc), tiled dla zrodla szerszego niz
    128 px. Wysokosc < 128 niepodzielna przez 16 konczyla zapis GTiff
    ``RasterBlockError`` — np. arkusz przyciety na granicy albo wybrzezu
    (ksztaltow arkuszy 1 m i przygranicznych offline nie znamy)."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * cols] * rows)
    out = mosaic_and_crop(
        [a],
        BBox(0.5, 0.5, cols + 0.5, rows + 0.5, "EPSG:2180"),
        tmp_path / "o.tif",
        nodata=-9999.0,
        assign_crs="EPSG:2180",
        dtype="float32",
    )
    with rasterio.open(out) as src:
        assert src.shape == (rows, cols)
        assert (src.read(1) == 1.5).all()


def test_wrapping_keeps_explicit_tiling_from_dst_kwds(tmp_path):
    """Domyslny zapis bez kafli nie nadpisuje jawnych kafli wolajacego."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * 200] * 100)
    out = mosaic_and_crop(
        [a],
        BBox(0.5, 0.5, 200.5, 100.5, "EPSG:2180"),
        tmp_path / "o.tif",
        dst_kwds={"tiled": True, "blockxsize": 512, "blockysize": 512},
        assign_crs="EPSG:2180",
        dtype="float32",
    )
    with rasterio.open(out) as src:
        assert src.block_shapes == [(512, 512)]


@pytest.mark.parametrize(
    ("value", "nodata", "expected"),
    [
        (-9999.0, -9999.0, False),
        (np.nan, -9999.0, False),
        (np.nan, np.nan, False),
        (np.inf, None, False),
        (np.nan, None, False),
        (0.0, None, True),
        (-9999.0, None, True),
    ],
)
def test_has_valid_pixels_distinguishes_nodata_and_nonfinite(
    tmp_path, value, nodata, expected
):
    from kartograf.transport.mosaic import has_valid_pixels

    path = _write_tile(tmp_path / "data.tif", 0, 32, value, size=32, nodata=nodata)
    assert has_valid_pixels(path, nodata) is expected


def test_has_valid_pixels_finds_only_valid_pixel_in_last_block(tmp_path):
    from kartograf.transport.mosaic import has_valid_pixels

    path = tmp_path / "last-block.tif"
    data = np.full((32, 32), -9999.0, dtype="float32")
    data[0, 0] = np.nan
    data[-1, -1] = 0.0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        count=1,
        width=32,
        height=32,
        dtype="float32",
        crs="EPSG:2180",
        transform=from_origin(0, 32, 1, 1),
        nodata=-9999.0,
        tiled=True,
        blockxsize=16,
        blockysize=16,
    ) as dst:
        dst.write(data, 1)
    assert has_valid_pixels(path, -9999.0) is True
