#!/usr/bin/env python
"""E2E offline (Zad. 17): wycinek PL z API biblioteki na REALNYCH arkuszach 5 m.

Zrodlo arkuszy: cache Hydrografu (TYLKO DO ODCZYTU). Provider testowy KOPIUJE
``<godlo>.asc`` (i dla wskazanych arkuszy ``<godlo>.prj``) do sciezki, ktora
podaje DownloadManager; arkusz nieobecny w cache -> ``NoCoverageError``.
Poza providerem NIC nie jest podmieniane (bez patchy Kartografa). Siec
Pythona zablokowana straznikiem na ``socket.connect`` (dowod, ze przebieg jest
offline). Wynik: JSON z liczbami na stdout + pliki w katalogu roboczym
podanym jako argv[1] (poza repo).

Scenariusze:
  a) cel EPSG:2180, bbox przez szew N-34-139-A-c-4-3 / -4-4 (calkowity
     i ulamkowy): faza siatki, rozszerzenie < 1 px, wartosci == arkusz
     zawierajacy srodek piksela, nodata tylko tam, gdzie zaden arkusz nie ma
     danych; mieszany cache (.prj tylko przy -4-3) == cache bez .prj (bit w bit)
  b) cel EPSG:5514, ten sam bbox: porownanie z niezaleznym warpem GDAL kazdego
     arkusza (rasterio.warp.reproject, ta sama operacja przypieta, ta sama
     siatka) na pikselach waznych w obu
  c) szew N-34-139-A-d-4-3 (w cache) / -4-4 (BRAK w cache): NoCoverageError
     -> missing_sheets, sidecar extra.missing_sheets, nodata w miejscu arkusza
  d) ponowne uzycie arkuszy z cache (force=False po usunieciu wyniku): zero
     wywolan providera, wynik bit w bit
  e) porazka pobrania (DownloadError) z force=True: poprzedni wynik nietkniety
  f) kompresja pliku posredniego mozaiki (dst_kwds jak w build_pl_cutout)
"""

import hashlib
import json
import logging
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject

HYDRO = Path("/home/claude-agent/workspace/Hydrograf/cache/nmt/nmt_5m")
OUT = Path(sys.argv[1]).resolve()
NODATA = -9999.0

# --- straznik sieci (Python): kazde polaczenie poza loopbackiem = blad -------
_orig_connect = socket.socket.connect
NET_ATTEMPTS: list = []


def _guard(self, address):
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith(
        "/"
    ):
        NET_ATTEMPTS.append(host)
        raise OSError(f"E2E offline: zablokowane polaczenie do {address}")
    return _orig_connect(self, address)


socket.socket.connect = _guard  # type: ignore[method-assign]

from kartograf import (  # noqa: E402
    BBox,
    DownloadError,
    NoCoverageError,
    prepare_pl_cutout,
    run_pl_cutout,
    select_pl_cutout_sheets,
)
from kartograf.download.cutout import estimate_pl_cutout_bytes  # noqa: E402
from kartograf.transport.mosaic import mosaic_and_crop  # noqa: E402

# logi biblioteki (INFO: brak danych dla arkuszy; WARNING: No data for ...)
LOG_RECORDS: list[logging.LogRecord] = []
ALL_RECORDS: list[logging.LogRecord] = []


class _Collect(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append(record)
        ALL_RECORDS.append(record)


_h = _Collect(level=logging.DEBUG)
logging.getLogger("kartograf").addHandler(_h)
logging.getLogger("kartograf").setLevel(logging.DEBUG)

INDEX = {p.stem: p for p in HYDRO.rglob("*.asc")}


class CacheCopyProvider:
    """Provider testowy: kopia arkusza z cache Hydrografu albo NoCoverageError."""

    name = "hydrograf-cache-copy"
    default_extension = ".asc"
    vertical_crs = "EVRF2007"
    resolution = "5m"
    descriptor_key = "pl.gugik.nmt_5m"

    def __init__(self, prj_for=(), fail_with=None):
        self.prj_for = set(prj_for)
        self.fail_with = fail_with
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def download(self, godlo, output_path, timeout=30):
        with self._lock:
            self.calls.append(godlo)
        if self.fail_with is not None:
            raise self.fail_with(f"E2E: symulowana awaria pobrania {godlo}", godlo=godlo)
        src = INDEX.get(godlo)
        if src is None:
            raise NoCoverageError(
                f"E2E: arkusza {godlo} nie ma w cache Hydrografu", godlo=godlo
            )
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, output_path)
        if godlo in self.prj_for:
            shutil.copyfile(src.with_suffix(".prj"), output_path.with_suffix(".prj"))
        return output_path


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(label, bbox, target, *, prj_for=(), out_dir=None, workers=4, force=False):
    out_dir = out_dir or OUT / label
    cutout = prepare_pl_cutout(
        bbox, target, output_dir=out_dir, resolution="5m", vertical_crs="EVRF2007"
    )
    sheets = select_pl_cutout_sheets(cutout)
    est_before = estimate_pl_cutout_bytes(cutout, sheets)
    provider = CacheCopyProvider(prj_for=prj_for)
    t0 = time.perf_counter()
    result = run_pl_cutout(
        cutout,
        sheets,
        provider=provider,
        max_workers=workers,
        force=force,
        parent_request={"bbox": list(bbox[:4]), "bbox_crs": bbox.crs, "e2e": label},
    )
    dt = time.perf_counter() - t0
    return cutout, sheets, provider, result, est_before, dt


def sheet_values_at(xs, ys, sheet_paths):
    """Wartosc arkusza zawierajacego srodek piksela (tylko wazne), liczba waznych."""
    expected = np.full(xs.shape, np.float32(NODATA), dtype=np.float32)
    nvalid = np.zeros(xs.shape, dtype=np.int32)
    conflicts = 0
    for sp in sorted(sheet_paths):
        with rasterio.open(sp) as s:
            a = s.read(1)
            st = s.transform
            snd = s.nodata
            cols = np.floor((xs - st.c) / st.a).astype(np.int64)
            rows = np.floor((ys - st.f) / st.e).astype(np.int64)
            inside = (cols >= 0) & (cols < s.width) & (rows >= 0) & (rows < s.height)
            vals = np.full(xs.shape, np.nan, dtype=np.float32)
            vals[inside] = a[rows[inside], cols[inside]]
            valid = inside & (vals != snd)
            conflicts += int(np.count_nonzero(valid & (nvalid > 0) & (expected != vals)))
            first = valid & (nvalid == 0)
            expected[first] = vals[first]
            nvalid += valid
    return expected, nvalid, conflicts


def check_2180(result_path, sheet_paths, req: BBox):
    with rasterio.open(result_path) as ds:
        arr = ds.read(1)
        t = ds.transform
        b = ds.bounds
        nd = ds.nodata
        crs = ds.crs.to_string() if ds.crs else None
        shape = (ds.height, ds.width)
        dtype = ds.dtypes[0]
    rows, cols = np.indices(arr.shape)
    xs = t.c + (cols + 0.5) * t.a
    ys = t.f + (rows + 0.5) * t.e
    expected, nvalid, conflicts = sheet_values_at(xs, ys, sheet_paths)
    mism = int(np.count_nonzero(arr != expected))
    return {
        "crs": crs,
        "dtype": dtype,
        "shape_hw": shape,
        "origin": [t.c, t.f],
        "phase_x_mod5": t.c % 5,
        "phase_y_mod5": t.f % 5,
        "pixel": [t.a, -t.e],
        "extension_beyond_request_m": {
            "west": req.min_x - b.left,
            "south": req.min_y - b.bottom,
            "east": b.right - req.max_x,
            "north": b.top - req.max_y,
        },
        "pixels": int(arr.size),
        "value_mismatches": mism,
        "both_sheets_valid_conflicts": conflicts,
        "pixels_with_2plus_valid_sheets": int(np.count_nonzero(nvalid >= 2)),
        "nodata_in_result": int(np.count_nonzero(arr == nd)),
        "expected_nodata_no_sheet_has_data": int(np.count_nonzero(nvalid == 0)),
        "nodata_where_some_sheet_has_data": int(
            np.count_nonzero((arr == nd) & (nvalid > 0))
        ),
    }


def independent_warp(result_path, sheet_paths, pinned):
    with rasterio.open(result_path) as ds:
        arr = ds.read(1)
        t = ds.transform
        h, w = ds.height, ds.width
        dst_crs = ds.crs
        b = ds.bounds
    op = pinned.gdal_operation()
    vals, weights = [], []
    for sp in sorted(sheet_paths):
        with rasterio.open(sp) as s:
            a = s.read(1).astype(np.float32)
            st = s.transform
        dst = np.full((h, w), NODATA, dtype=np.float32)
        reproject(
            source=a,
            destination=dst,
            src_transform=st,
            src_crs=CRS.from_user_input("EPSG:2180"),
            src_nodata=NODATA,
            dst_transform=t,
            dst_crs=dst_crs,
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
            COORDINATE_OPERATION=op,
        )
        vals.append(dst)
        # suma wag bilinear pikseli waznych (maska 1/0 bez nodata) — do
        # rekonstrukcji wartosci na szwie: (wA*vA + wB*vB) / (wA + wB)
        mask = (a != NODATA).astype(np.float32)
        wdst = np.zeros((h, w), dtype=np.float32)
        reproject(
            source=mask,
            destination=wdst,
            src_transform=st,
            src_crs=CRS.from_user_input("EPSG:2180"),
            dst_transform=t,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
            COORDINATE_OPERATION=op,
            init_dest_nodata=False,
        )
        weights.append(wdst)
    V = np.stack(vals).astype(np.float64)
    W = np.stack(weights).astype(np.float64)
    valid = V != NODATA
    nvalid = valid.sum(0)
    single = nvalid == 1
    seam = nvalid >= 2
    ind = np.where(single, np.where(valid, V, 0).sum(0), np.nan)
    ws = np.where(valid, W, 0.0)
    recon = np.where(
        seam, (np.where(valid, V * W, 0).sum(0)) / np.maximum(ws.sum(0), 1e-12), np.nan
    )
    mean_seam = np.where(seam, np.where(valid, V, 0).sum(0) / np.maximum(nvalid, 1), np.nan)
    cut_valid = arr != NODATA
    a64 = arr.astype(np.float64)

    def stats(mask, ref):
        d = np.abs(a64[mask] - ref[mask])
        if d.size == 0:
            return {"n": 0}
        return {
            "n": int(d.size),
            "mean_abs_m": float(d.mean()),
            "max_abs_m": float(d.max()),
            "n_diff_gt_0": int(np.count_nonzero(d > 0)),
            "n_diff_gt_1mm": int(np.count_nonzero(d > 0.001)),
            "n_diff_gt_1cm": int(np.count_nonzero(d > 0.01)),
        }

    combined = np.where(single, ind, np.where(seam, mean_seam, np.nan))
    both = cut_valid & (nvalid >= 1)
    return {
        "grid_hw": [h, w],
        "bounds": [b.left, b.bottom, b.right, b.top],
        "cutout_nodata": int(np.count_nonzero(~cut_valid)),
        "independent_nodata": int(np.count_nonzero(nvalid == 0)),
        "valid_in_cutout_only": int(np.count_nonzero(cut_valid & (nvalid == 0))),
        "valid_in_independent_only": int(np.count_nonzero(~cut_valid & (nvalid >= 1))),
        "all_valid_in_both_(seam=mean_of_sheets)": stats(both, combined),
        "single_sheet_pixels": stats(cut_valid & single, ind),
        "seam_pixels_vs_mean_of_sheet_warps": stats(cut_valid & seam, mean_seam),
        "seam_pixels_vs_weight_reconstruction": stats(cut_valid & seam, recon),
    }


def sidecar(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"cache_sheets_indexed": len(INDEX)}

    # ---------------- a) EPSG:2180, szew -4-3/-4-4 -------------------------
    seam_prj = ("N-34-139-A-c-4-3",)
    for label, bbox in (
        ("a_int", BBox(642000, 480500, 644000, 481500, "EPSG:2180")),
        ("a_frac", BBox(642001.3, 480502.7, 643998.9, 481497.1, "EPSG:2180")),
    ):
        cutout, sheets, prov, res, est, dt = run(label, bbox, "EPSG:2180", prj_for=seam_prj)
        prj_files = sorted(p.name for p in (OUT / label).rglob("*.prj"))
        chk = check_2180(res.path, res.sheet_paths, bbox)
        meta = sidecar(res.path)
        actual_bytes = sum(p.stat().st_size for p in res.sheet_paths) + res.path.stat().st_size
        report[label] = {
            "bbox": list(bbox[:4]),
            "sheets_selected": list(sheets.godla),
            "provider_calls": sorted(prov.calls),
            "prj_copied_next_to": prj_files,
            "missing_sheets": list(res.missing_sheets),
            "result": str(res.path.relative_to(OUT)),
            "file_name_equals_request": res.path.stem
            == "_".join(format(v, ".10g") for v in bbox[:4]),
            "sidecar": {
                "horizontal_crs": meta["horizontal_crs"],
                "transform": meta["transform"],
                "request": meta["request"],
                "nodata": meta["nodata"],
                "extra_keys": sorted((meta.get("extra") or {}).keys()),
            },
            "estimate_before_run": {"bytes": est[0], "pending_sheets": est[1]},
            "actual_bytes_sheets_plus_result": actual_bytes,
            "estimate_is_lower_bound": est[0] <= actual_bytes,
            "seconds": round(dt, 3),
            "check": chk,
        }
    # mieszany cache (.prj przy -4-3) vs cache bez .prj: identyczny wynik
    b_int = BBox(642000, 480500, 644000, 481500, "EPSG:2180")
    _, _, _, res_noprj, _, _ = run("a_int_noprj", b_int, "EPSG:2180", prj_for=())
    res_mixed_path = OUT / report["a_int"]["result"]
    report["a_int_mixed_prj_vs_no_prj_bit_identical_pixels"] = bool(
        np.array_equal(
            rasterio.open(res_mixed_path).read(1), rasterio.open(res_noprj.path).read(1)
        )
    )

    # ---------------- b) EPSG:5514, ten sam bbox ----------------------------
    cutout, sheets, prov, res, est, dt = run("b_5514", b_int, "EPSG:5514", prj_for=seam_prj)
    meta = sidecar(res.path)
    with rasterio.open(res.path) as ds:
        bounds_eq_target = all(
            abs(u - v) < 1e-6
            for u, v in zip(
                ds.bounds,
                (
                    cutout.bbox_target.min_x,
                    cutout.bbox_target.min_y,
                    cutout.bbox_target.max_x,
                    cutout.bbox_target.max_y,
                ),
                strict=True,
            )
        )
        res_profile = {
            "crs": ds.crs.to_string(),
            "dtype": ds.dtypes[0],
            "compress": ds.compression.value if ds.compression else None,
            "shape_hw": [ds.height, ds.width],
        }
    report["b_5514"] = {
        "bbox_request_2180": list(b_int[:4]),
        "bbox_target_5514": list(cutout.bbox_target[:4]),
        "bbox_source_2180": list(cutout.bbox_source_2180[:4]),
        "sheets_selected": list(sheets.godla),
        "provider_calls": sorted(prov.calls),
        "missing_sheets": list(res.missing_sheets),
        "result": str(res.path.relative_to(OUT)),
        "result_profile": res_profile,
        "bounds_equal_bbox_target": bounds_eq_target,
        "sidecar": {
            "horizontal_crs": meta["horizontal_crs"],
            "transform": meta["transform"],
            "extra_keys": sorted((meta.get("extra") or {}).keys()),
        },
        "pinned": f"{cutout.pinned.description} ({cutout.pinned.accuracy_m} m)",
        "estimate_before_run": {"bytes": est[0], "pending_sheets": est[1]},
        "seconds": round(dt, 3),
        "independent_warp": independent_warp(res.path, res.sheet_paths, cutout.pinned),
    }

    # ---------------- c) arkusz BRAK w cache -> NoCoverageError --------------
    b_c = BBox(650500, 480800, 652500, 481800, "EPSG:2180")
    LOG_RECORDS.clear()
    cutout, sheets, prov, res, est, dt = run("c_missing", b_c, "EPSG:2180")
    chk = check_2180(res.path, res.sheet_paths, b_c)
    meta = sidecar(res.path)
    # nodata na wschod od danych A-d-4-3 (w miejscu A-d-4-4)?
    with rasterio.open(res.path) as ds:
        arr = ds.read(1)
        t = ds.transform
    rows, cols = np.indices(arr.shape)
    xs = t.c + (cols + 0.5) * t.a
    nod = arr == NODATA
    valid_x_max = float(xs[~nod].max()) if (~nod).any() else None
    nodata_x_min = float(xs[nod].min()) if nod.any() else None
    lib_logs = [
        (r.levelname, r.name, r.getMessage()[:160])
        for r in LOG_RECORDS
        if "Brak danych GUGiK" in r.getMessage() or "No data for" in r.getMessage()
    ]
    report["c_missing"] = {
        "bbox": list(b_c[:4]),
        "sheets_selected": list(sheets.godla),
        "sheets_in_cache": [g for g in sheets.godla if g in INDEX],
        "provider_calls": sorted(prov.calls),
        "missing_sheets_result": list(res.missing_sheets),
        "sidecar_extra_missing_sheets": (meta.get("extra") or {}).get("missing_sheets"),
        "sidecar_extra_parent_request": (meta.get("extra") or {}).get("parent_request"),
        "check": chk,
        "nodata_fraction": round(float(nod.mean()), 4),
        "max_x_of_valid_pixel_centre": valid_x_max,
        "min_x_of_nodata_pixel_centre": nodata_x_min,
        "library_log_lines": lib_logs,
    }

    # ---------------- d) ponowne uzycie arkuszy z cache -----------------------
    a_path = OUT / report["a_int"]["result"]
    ref_sha = sha(a_path)
    with rasterio.open(a_path) as ds:
        ref_pixels = ds.read(1)
    a_path.unlink()
    Path(f"{a_path}.meta.json").unlink()
    cutout = prepare_pl_cutout(
        b_int, "EPSG:2180", output_dir=OUT / "a_int", resolution="5m"
    )
    sheets = select_pl_cutout_sheets(cutout)
    guard = CacheCopyProvider(fail_with=DownloadError)
    res = run_pl_cutout(cutout, sheets, provider=guard, max_workers=4)
    with rasterio.open(res.path) as ds:
        rebuilt_pixels = ds.read(1)
    report["d_cache_reuse"] = {
        "provider_calls": list(guard.calls),  # kopia: e) dopisuje do tej listy
        "rebuilt_bit_identical_file": sha(res.path) == ref_sha,
        "rebuilt_identical_pixels": bool(np.array_equal(ref_pixels, rebuilt_pixels)),
        "skipped_second_call_without_force": run_pl_cutout(
            cutout, sheets, provider=guard, max_workers=4
        ).skipped,
    }

    # ---------------- e) awaria pobrania z force=True -------------------------
    before = sha(res.path)
    err = None
    try:
        run_pl_cutout(cutout, sheets, provider=guard, max_workers=4, force=True)
    except DownloadError as e:
        err = str(e)[:200]
    leftovers = sorted(
        p.name for p in res.path.parent.iterdir() if ".mosaic." in p.name or ".warp." in p.name
    )
    report["e_failed_force_keeps_previous"] = {
        "raised_DownloadError": err,
        "previous_result_unchanged": sha(res.path) == before,
        "tmp_leftovers": leftovers,
    }

    # ---------------- f) kompresja pliku posredniego -------------------------
    b5514 = report["b_5514"]
    src_bbox = BBox(*b5514["bbox_source_2180"], "EPSG:2180")
    sheet_paths = sorted(
        (OUT / "b_5514").rglob("*.asc"),
    )
    plain = OUT / "f_mosaic_plain.tif"
    comp = OUT / "f_mosaic_compressed.tif"
    common = dict(
        nodata=NODATA,
        snap_to_source_grid=True,
        assign_crs="EPSG:2180",
        dtype="float32",
    )
    mosaic_and_crop(
        sheet_paths, src_bbox, plain, dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"}, **common
    )
    mosaic_and_crop(
        sheet_paths,
        src_bbox,
        comp,
        dst_kwds={
            "driver": "GTiff",
            "crs": "EPSG:2180",
            "compress": "deflate",
            "predictor": 3,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "bigtiff": "IF_SAFER",
        },
        **common,
    )
    with rasterio.open(plain) as p1, rasterio.open(comp) as p2:
        same = bool(np.array_equal(p1.read(1), p2.read(1)))
        hw = [p1.height, p1.width]
    asc_bytes = sum(p.stat().st_size for p in sheet_paths)
    asc_values = 0
    for p in sheet_paths:
        with rasterio.open(p) as s:
            asc_values += s.width * s.height
    report["f_intermediate_compression"] = {
        "mosaic_hw": hw,
        "plain_bytes": plain.stat().st_size,
        "compressed_bytes": comp.stat().st_size,
        "ratio": round(plain.stat().st_size / comp.stat().st_size, 2),
        "pixels_identical": same,
        "asc_sheets": len(sheet_paths),
        "asc_bytes_per_value": round(asc_bytes / asc_values, 3),
    }

    report["network_attempts_blocked"] = NET_ATTEMPTS
    report["kartograf_warning_or_worse_log_messages"] = sorted(
        {
            f"{r.levelname} {r.name}: {r.getMessage()[:200]}"
            for r in ALL_RECORDS
            if r.levelno >= logging.WARNING
        }
    )
    print(json.dumps(report, indent=2, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
