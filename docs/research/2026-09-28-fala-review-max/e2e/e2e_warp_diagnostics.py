#!/usr/bin/env python
"""Diagnostyka scenariusza b) E2E (Zad. 17): skad roznice cutout vs niezalezny warp.

Wejscie: katalog roboczy e2e_pl_cutout.py (argv[1]) — arkusze i wynik b_5514.
Nic w Kartografie nie jest podmieniane; skrypt tylko czyta pliki i liczy.

1) Odtworzenie toru biblioteki krok po kroku: mosaic_and_crop z parametrami
   build_pl_cutout (snap, VRT EPSG:2180/Float32) + reproject jak warp_to_grid
   (Band zrodla, ustawienia domyslne) -> musi dac wynik bit w bit (dowod, ze
   wynik = mozaika na siatce arkuszy + warp, bez innych krokow).
2) Niezalezny warp per arkusz vs warp tej mozaiki (oba GDAL, ta sama operacja
   przypieta, ta sama siatka) w trzech wariantach ustawien GDAL:
   - domyslne (jak warp_to_grid),
   - tolerance=0 (dokladny transformer zamiast przyblizonego 0,125 px),
   - XSCALE=YSCALE=1 (GDAL NIE skaluje jadra resamplingu wg proporcji okna
     zrodla do okna celu; domyslnie proporcja zalezy od zasiegu zrodla —
     arkusz vs mozaika — wiec jadro bywa rozne).
   Statystyki wg odleglosci (Chebyshev, px wyniku) od szwu = granicy, na
   ktorej zmienia sie arkusz dajacy wazna wartosc: przy szwie warp jednego
   arkusza widzi tylko czesc sasiadow bilinear (GDAL pomija piksel docelowy,
   gdy piksel zrodla pod probka to nodata, a wagi pozostalych normalizuje).
"""

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject

OUT = Path(sys.argv[1]).resolve()
NODATA = -9999.0

from kartograf import BBox, prepare_pl_cutout  # noqa: E402
from kartograf.transport.mosaic import mosaic_and_crop  # noqa: E402


def main() -> None:
    b_int = BBox(642000, 480500, 644000, 481500, "EPSG:2180")
    cutout = prepare_pl_cutout(
        b_int, "EPSG:5514", output_dir=OUT / "b_5514", resolution="5m"
    )
    sheets = sorted((OUT / "b_5514").rglob("*.asc"))
    op = cutout.pinned.gdal_operation()
    with rasterio.open(cutout.target_path) as ds:
        cut = ds.read(1)
        t, h, w, dcrs = ds.transform, ds.height, ds.width, ds.crs
    rep: dict = {"sheets": [p.name for p in sheets], "grid_hw": [h, w]}

    # 1) odtworzenie toru biblioteki (parametry build_pl_cutout / warp_to_grid)
    mos = OUT / "diag_mosaic.tif"
    mosaic_and_crop(
        sheets,
        cutout.bbox_source_2180,
        mos,
        nodata=NODATA,
        dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
        snap_to_source_grid=True,
        assign_crs="EPSG:2180",
        dtype="float32",
    )

    def warp(arr, st, **kw):
        dst = np.full((h, w), NODATA, dtype=np.float32)
        reproject(
            source=arr,
            destination=dst,
            src_transform=st,
            src_crs=CRS.from_string("EPSG:2180"),
            src_nodata=NODATA,
            dst_transform=t,
            dst_crs=dcrs,
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
            COORDINATE_OPERATION=op,
            **kw,
        )
        return dst

    replay = np.full((h, w), NODATA, dtype=np.float32)
    with rasterio.open(mos) as src:
        reproject(  # jak warp_to_grid: Band zrodla, bez dodatkowych opcji
            source=rasterio.band(src, 1),
            destination=replay,
            src_crs=CRS.from_string("EPSG:2180"),
            src_nodata=NODATA,
            dst_transform=t,
            dst_crs=dcrs,
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
            COORDINATE_OPERATION=op,
        )
        M, mt = src.read(1), src.transform
    rep["replay_library_path_bit_identical"] = bool(np.array_equal(replay, cut))

    for label, kw in (
        ("default", {}),
        ("tolerance_0", {"tolerance": 0}),
        ("XSCALE_YSCALE_1", {"XSCALE": 1, "YSCALE": 1}),
    ):
        mw = warp(M, mt, **kw)
        per = []
        for sp in sheets:
            with rasterio.open(sp) as s:
                per.append(warp(s.read(1).astype(np.float32), s.transform, **kw))
        V = np.stack(per)
        valid = V != NODATA
        n = valid.sum(0)
        val = np.where(valid, V, 0).sum(0) / np.maximum(n, 1)
        idx = np.argmax(valid, axis=0)
        switch = np.zeros(idx.shape, dtype=bool)
        switch[:, 1:] |= idx[:, 1:] != idx[:, :-1]
        switch[1:, :] |= idx[1:, :] != idx[:-1, :]
        rr, cc = np.indices(idx.shape)
        dist = np.full(idx.shape, 10**6)
        for y, x in zip(*np.nonzero(switch), strict=True):
            np.minimum(dist, np.maximum(np.abs(rr - y), np.abs(cc - x)), out=dist)
        both = (n >= 1) & (mw != NODATA)
        d = np.abs(mw.astype(np.float64) - val)

        def stats(diff, mask):
            dd = diff[mask]
            return {
                "n": int(dd.size),
                "mean_abs_m": float(dd.mean()),
                "max_abs_m": float(dd.max()),
                "n_gt_1mm": int(np.count_nonzero(dd > 0.001)),
                "n_gt_1cm": int(np.count_nonzero(dd > 0.01)),
            }

        big = both & (d > 0.01)
        rep[label] = {
            "per_sheet_valid_count_hist": {
                str(k): int(np.count_nonzero(n == k)) for k in range(3)
            },
            "mosaic_warp_equals_cutout": bool(np.array_equal(mw, cut)),
            "all": stats(d, both),
            "within_1px_of_seam": stats(d, both & (dist <= 1)),
            "farther_than_1px_from_seam": stats(d, both & (dist > 1)),
            "gt_1cm_by_seam_distance_px": {
                str(int(k)): int(v)
                for k, v in zip(*np.unique(dist[big], return_counts=True), strict=True)
            },
        }
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
