"""Testy warp_to_grid — lokalna reprojekcja przypieta operacja (wzorzec ADR-024)."""

import dataclasses
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import (
    TransformError,
    TransformPolicy,
    build_pinned_transform,
)
from kartograf.transform.raster import warp_to_grid

_NODATA = -9999.0
# EPSG:2180, srodkowa Polska — realny teren, operacja 2180->5514 ma tu 0,5 m
_APEX_2180 = (530050.0, 382050.0)


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX_2180, allow_network_grids=False
        ),
    )


def _write_cone_tif(path, apex, size=300, pixel=1.0, *, hole=None, declare_nodata=True):
    """Stozek wokol apex w EPSG:2180 (wzorzec _server_emulator z test_cuzk_dmr).

    ``hole`` to zakres (start, stop) wierszy i kolumn wypelniony wartoscia
    nodata; ``declare_nodata=False`` daje raster, ktory dziury NIE deklaruje
    w profilu — tylko taki obnaza brak ``src_nodata``/``dst_nodata`` w warpie
    (przy zadeklarowanym nodata rasterio domysla sie go z pasma i test bylby
    atrapa).
    """
    west = apex[0] - size / 2 * pixel
    north = apex[1] + size / 2 * pixel
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = north - (rows + 0.5) * pixel
    data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    if hole is not None:
        start, stop = hole
        data[start:stop, start:stop] = _NODATA
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": size,
        "height": size,
        "crs": CRS.from_string("EPSG:2180"),
        "transform": from_origin(west, north, pixel, pixel),
        "nodata": _NODATA if declare_nodata else None,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


def _apex_of(path):
    with rasterio.open(path) as ds:
        data = ds.read(1, masked=True)
        row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
        return ds.xy(int(row), int(col))


class TestWarpToGrid:
    def test_content_lands_where_pyproj_says(self, tmp_path):
        """Regresja TRESCI: wierzcholek < 1 px od wzorca pyproj (2180->5514)."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 100, ay - 100, ax + 100, ay + 100, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        gx, gy = _apex_of(dst)
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"

    def test_grid_matches_bbox_and_profile(self, tmp_path):
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 40, ax + 50, ay + 40, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 2.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            assert (ds.width, ds.height) == (50, 40)
            assert ds.crs.to_epsg() == 5514
            assert ds.nodata == _NODATA
        # zapis atomowy: brak plikow tymczasowych
        assert list(tmp_path.glob("*.warp.tif")) == []

    def test_operation_is_forced(self, tmp_path):
        """COORDINATE_OPERATION musi byc podane GDAL-owi jawnie (ADR-024)."""
        from rasterio.warp import reproject as real_reproject

        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")

        with patch(
            "kartograf.transform.raster.reproject", wraps=real_reproject
        ) as warp:
            warp_to_grid(
                src,
                tmp_path / "dst.tif",
                bbox,
                1.0,
                pinned,
                src_crs="EPSG:2180",
                nodata=_NODATA,
            )

        warp.assert_called_once()
        assert warp.call_args.kwargs["COORDINATE_OPERATION"] == pinned.gdal_operation()
        # bilinear, nie nearest: NMT jest polem ciaglym, a `nearest` cofnalby
        # tez sens testu o nodata (bez interpolacji nie ma czego zatruc)
        assert warp.call_args.kwargs["resampling"] == Resampling.bilinear

    def test_nodata_does_not_bleed_into_interpolation(self, tmp_path):
        """Zrodlo BEZ zadeklarowanego nodata: maskowanie robia src/dst_nodata.

        Fixtura deklarujaca nodata NIE strzeglaby tego — rasterio domysla sie
        wtedy `src_nodata` z pasma i wynik jest ten sam z argumentami i bez.
        Taki raster jest osiagalny na torze PL: `transport/mosaic.py` wpisuje
        `nodata` do profilu tylko wtedy, gdy wolajacy poda wartosc.
        """
        src = _write_cone_tif(
            tmp_path / "src.tif", _APEX_2180, hole=(100, 140), declare_nodata=False
        )
        with rasterio.open(src) as ds:
            assert ds.nodata is None, "fixtura deklaruje nodata — test bylby atrapa"
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 100, ay - 100, ax + 100, ay + 100, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            valid = ds.read(1, masked=True).compressed()
        assert valid.size > 0, "caly wynik zamaskowany — warp nie przeniosl tresci"
        assert valid.min() > 0.0, f"nodata weszlo do interpolacji: min {valid.min()}"

    def test_failed_warp_writes_only_to_temp_file(self, tmp_path):
        """Zapis jest atomowy: sciezka docelowa nie powstaje w trakcie warpu.

        Sam brak `*.warp.tif` po udanym przebiegu tego nie dowodzi (bez pliku
        tymczasowego tez go nie ma). Dowodem jest STAN W CHWILI AWARII: cel
        jeszcze nie istnieje, a plik tymczasowy juz tak.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"
        seen = {}

        def boom(*args, **kwargs):
            seen["dst_exists"] = dst.exists()
            seen["tmp"] = [p.name for p in tmp_path.glob("*.warp.tif")]
            raise RuntimeError("warp przerwany")

        with (
            patch("kartograf.transform.raster.reproject", side_effect=boom),
            pytest.raises(RuntimeError, match="warp przerwany"),
        ):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert seen["dst_exists"] is False, "polzapisany raster pod finalna sciezka"
        assert seen["tmp"], "warp nie uzyl pliku tymczasowego"
        assert not dst.exists()
        assert list(tmp_path.glob("*.warp.tif")) == []  # sprzatanie po awarii

    def test_failed_warp_removes_stale_destination(self, tmp_path):
        """Semantyka toru CZ: nieudany warp nie zostawia STAREGO wyniku."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"
        dst.write_bytes(b"II*\x00stary wynik")

        with (
            patch(
                "kartograf.transform.raster.reproject",
                side_effect=RuntimeError("warp przerwany"),
            ),
            pytest.raises(RuntimeError),
        ):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert not dst.exists()

    def test_lowercase_crs_is_the_same_pair(self, tmp_path):
        """`epsg:2180` to ten sam uklad co `EPSG:2180` — porownanie semantyczne.

        Guard pary ukladow porownuje CRS-y, nie stringi; samo `a == b`
        odrzucaloby zdrowe wywolanie z inaczej zapisanym kodem.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "epsg:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="epsg:2180", nodata=_NODATA)

        assert dst.exists()

    def test_pinned_pair_must_match_src_crs(self, tmp_path):
        """Niespojna para zrodlowa = blad, nie cichy zly wynik.

        Przy wymuszonym `COORDINATE_OPERATION` GDAL ignoruje zadeklarowany
        `src_crs` (zmierzone: 2180/4326/3857/32633/5514 daja ten sam wynik),
        wiec bez tego guardu parametr bylby martwy i dawal falszywa asekuracje.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        with pytest.raises(TransformError, match="Niespojna para ukladow"):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:4326", nodata=_NODATA
            )

        assert not dst.exists()

    def test_pinned_pair_must_match_bbox_crs(self, tmp_path):
        """Niespojna para docelowa (bbox.crs != pinned.dst_crs) = blad."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        bbox = BBox(
            _APEX_2180[0] - 50,
            _APEX_2180[1] - 50,
            _APEX_2180[0] + 50,
            _APEX_2180[1] + 50,
            "EPSG:2180",
        )
        dst = tmp_path / "dst.tif"

        with pytest.raises(TransformError, match="Niespojna para ukladow"):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert not dst.exists()

    def test_guard_skips_unknown_pinned_pair(self, tmp_path):
        """Pola `src_crs`/`dst_crs` sa opcjonalne — guard nie moze na nich padac.

        Gdy `pinned` nie zna swojej pary, o braku decyduje `gdal_operation()`
        (jego wlasny komunikat), a nie guard — nawet jesli podany `src_crs`
        rozni sie od faktycznego zrodla operacji.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = dataclasses.replace(
            _pinned_2180_to("EPSG:5514"), src_crs=None, dst_crs=None
        )
        bbox = BBox(0.0, 0.0, 100.0, 100.0, "EPSG:5514")

        with pytest.raises(TransformError, match="wymaga znanej pary ukladow"):
            warp_to_grid(
                src,
                tmp_path / "dst.tif",
                bbox,
                1.0,
                pinned,
                src_crs="EPSG:4326",
                nodata=_NODATA,
            )
