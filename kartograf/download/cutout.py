"""
Merged NMT PL cutout in a requested CRS (ADR-027) — library layer.

GUGiK sheets are downloaded normally into their own segments (acting as a
cache), the mosaic is cropped to the request area expanded outward to the
sheet pixel grid (< 1 px; with reprojection — with a margin), and for a CRS
other than EPSG:2180 the content lands on the result grid via a local warp
with a FORCED pinned operation (ADR-024/027). The result is ONE GeoTIFF
``<output_dir>/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`` + sidecar.

The CLI (``kartograf download --bbox/--geometry --target-crs``) is a thin
layer over this module: it prints messages and translates exceptions into
exit codes. There is no ``print`` or argparse here.

Example::

    from kartograf import BBox, download_pl_cutout

    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        "EPSG:5514",
        output_dir="./data",
        max_workers=4,
    )
    print(result.path)
"""

import json
import logging
import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from kartograf.core.bbox import BBox, is_czech_crs, transform_bbox
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, ProgressCallback
from kartograf.download.storage import (
    FileStorage,
    bbox_cutout_path,
    prune_empty_dirs,
    storage_for_provider,
)
from kartograf.exceptions import DownloadError, GridMismatchError, ValidationError
from kartograf.transform.crs import CONTENT_POLICY, WARP_MARGIN_PX, PinnedTransform

logger = logging.getLogger(__name__)

# nodata of GUGiK ASC sheets
PL_NODATA = -9999.0
# result grid pixel per NMT PL resolution
PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}
# target CRS with a pinned EPSG:2180 -> target operation (KNOWN_PATHS, ADR-027)
SUPPORTED_TARGET_CRS = ("EPSG:2180", "EPSG:5514", "EPSG:3045")
# CONTENT reprojection operation policy (CONTENT_POLICY) and source envelope
# margin (WARP_MARGIN_PX) — shared with the CZ flow, from transform/crs.py (D9).
_VERTICAL_CRS = ("EVRF2007", "KRON86")
# Lower bound of an ASC sheet's size on disk: 5.74-7.95 B per value in real
# GUGiK 5 m files (fact 9 of the 2026-09-28 plan) — we take less, so the check
# does not reject requests that will fit.
_ASC_BYTES_PER_VALUE = 5.5


@dataclass(frozen=True)
class PlCutout:
    """Prepared (fail-fast, no network) NMT PL cutout."""

    target_crs: str
    resolution: str
    vertical_crs: str  # ACTUAL vertical CRS (after the 5m rule => EVRF2007)
    output_dir: Path
    bbox_2180: BBox  # exact request in EPSG:2180
    bbox_source_2180: BBox  # request + warp margin: sheet selection and mosaic crop
    bbox_target: BBox  # result grid (target CRS)
    pinned: PinnedTransform | None  # None for EPSG:2180 (crop only)
    target_path: Path

    @property
    def pixel_size(self) -> float:
        """Result grid pixel size (m)."""
        return PIXEL_SIZES[self.resolution]

    @property
    def grid_shape(self) -> tuple[int, int]:
        """(height, width) of the result grid in pixels — as in ``warp_to_grid``."""
        b, px = self.bbox_target, self.pixel_size
        return (
            max(1, round((b.max_y - b.min_y) / px)),
            max(1, round((b.max_x - b.min_x) / px)),
        )

    @property
    def estimated_bytes(self) -> int:
        """Size of the uncompressed float32 result (bytes)."""
        height, width = self.grid_shape
        return height * width * 4


@dataclass(frozen=True)
class PlCutoutSheets:
    """Sheets to download for a cutout (godla at the selection scale)."""

    godla: tuple[str, ...]


@dataclass(frozen=True)
class PlCutoutResult:
    """Result of ``run_pl_cutout`` / ``download_pl_cutout``.

    With ``skipped=True`` (file existed, ``force=False``) ``missing_sheets``,
    ``off_grid_sheets``, ``partial_sheets``, ``unverified`` and ``all_nodata``
    come from the sidecar of the existing cutout (``skipped_pl_cutout``; the
    raster is not read again), and ``sheet_paths`` is empty — nobody touched
    the sheets.
    """

    path: Path
    skipped: bool = False  # file already existed (force=False) — no network
    sheet_paths: tuple[Path, ...] = ()  # sheets used for the mosaic
    missing_sheets: tuple[str, ...] = ()  # sheets without GUGiK data (R5) -> nodata
    # sheets with a different grid phase than the rest, reprojected separately (W1, S5)
    off_grid_sheets: tuple[str, ...] = ()
    # cutout without a single valid pixel (N2): the downloaded sheets lie in the
    # selection margin or are nodata themselves — the file was created, exit 0 in CLI
    all_nodata: bool = False
    # sheets from an incomplete newest campaign (index record
    # ``full_sheet=False``, E13) — chosen per ADR-028, but may contribute nodata
    partial_sheets: tuple[str, ...] = ()
    # godlo -> error: sheets from a local campaign because the index was
    # unavailable (transport error, I-1); a newer campaign was not checked. With
    # ``skipped=True`` restored from the sidecar (``extra.unverified_sheets``).
    unverified: dict[str, str] = field(default_factory=dict)


def bbox_to_2180(bbox: BBox) -> BBox:
    """Request in EPSG:2180: Czech CRSs via the pinned operation, the rest as before.

    PL/WGS84 CRSs — deliberately the default transformer, as in the whole PL
    flow, envelope from densified edges (``core.bbox.transform_bbox``; four
    corners lost a strip at 19E — up to ~480 m in the S for a 2 x 0.2 deg
    bbox). The CLI passes a bbox here already after ``_country_bbox``, which
    leaves Czech CRSs via the pinned operation; the Czech branch therefore
    concerns library calls. The CRS label is compared case- and
    whitespace-insensitively (``is_czech_crs``): a literal comparison let
    ``"epsg:5514"`` through the default transformer (beside ADR-024, final
    wave review, m-2).
    """
    if is_czech_crs(bbox.crs):
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        return bbox_to_crs(bbox, "EPSG:2180")
    return transform_bbox(bbox, "EPSG:2180")


def prepare_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
) -> PlCutout:
    """Fail-fast cutout preparation: operation, bboxes and result path.

    Zero network. ``TransformError`` when the EPSG:2180 -> ``target_crs``
    pair has no pinned operation (ADR-024/027); ``ValidationError`` on bad
    parameters. ``vertical_crs`` is the ACTUAL vertical CRS: with 5m only
    EVRF2007 (``download_pl_cutout`` applies the provider factory rule
    itself).

    The cutout is always a GeoTIFF (``.tif``) — the descriptor's
    ``default_extension`` (``.asc``) concerns sheets, not the cutout.
    """
    if target_crs not in SUPPORTED_TARGET_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka PL: {target_crs} "
            f"(dostepne: {', '.join(SUPPORTED_TARGET_CRS)})"
        )
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    from kartograf.providers.pl import nmt_vertical_crs

    if nmt_vertical_crs(resolution, vertical_crs, log=False) != vertical_crs:
        raise ValidationError("NMT 5m jest dostepny wylacznie w EVRF2007")

    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_source

    # local import: tests replace the operation in the transform.crs module
    from kartograf.transform.crs import build_pinned_transform

    bbox_2180 = bbox_to_2180(bbox)
    pinned = None
    bbox_target = bbox_2180
    bbox_source_2180 = bbox_2180
    if target_crs != "EPSG:2180":
        center = (
            (bbox_2180.min_x + bbox_2180.max_x) / 2,
            (bbox_2180.min_y + bbox_2180.max_y) / 2,
        )
        # content policy as in the CZ flow + probe at the request center
        pinned = build_pinned_transform(
            "EPSG:2180", target_crs, replace(CONTENT_POLICY, probe_point=center)
        )
        bbox_target = bbox_to_crs(bbox_2180, target_crs, pinned)
        # The source must cover the WHOLE result grid: the target envelope maps
        # back to 2180 larger than the request (CRS rotation), and the
        # interpolator needs a halo. Mirror of the CZ flow's _native_request_bbox.
        # Without `pinned` — the pinned operation is DIRECTIONAL (2180 -> target),
        # CZ does the same.
        back = bbox_to_crs(bbox_target, "EPSG:2180")
        margin = WARP_MARGIN_PX * PIXEL_SIZES[resolution]
        bbox_source_2180 = BBox(
            back.min_x - margin,
            back.min_y - margin,
            back.max_x + margin,
            back.max_y + margin,
            "EPSG:2180",
        )

    key = "pl.gugik.nmt_5m" if resolution == "5m" else "pl.gugik.nmt_1m"
    subdir = get_source(key).resolve_subdir(uklad="1992", vertical_crs=vertical_crs)
    return PlCutout(
        target_crs=target_crs,
        resolution=resolution,
        vertical_crs=vertical_crs,
        output_dir=Path(output_dir),
        bbox_2180=bbox_2180,
        bbox_source_2180=bbox_source_2180,
        bbox_target=bbox_target,
        pinned=pinned,
        target_path=bbox_cutout_path(output_dir, subdir, bbox_target, ".tif"),
    )


def select_pl_cutout_sheets(
    cutout: PlCutout,
    *,
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
) -> PlCutoutSheets:
    """Cutout sheets (zero network).

    Bbox mode: sheets of the source envelope (request + margin) enlarged by 1
    pixel — the mosaic crop is snapped OUTWARD to the sheet grid (< 1 px,
    ``build_pl_cutout``). Geometry mode: sheets per feature, and with a warp
    the UNION with the sheets of the same enlarged source envelope (R-01: the
    result covers the WHOLE envelope, without masking to features — without
    the union a nodata frame would remain at the edges; ARCHITECTURE 4.3). The
    cost is deliberate: for a sparse multi-feature geometry the union covers
    sheets of the whole envelope, also where there is no feature at all.
    """
    px = cutout.pixel_size
    src = cutout.bbox_source_2180
    # The crop is snapped OUTWARD to the sheet grid (< 1 px): selection with a
    # 1 px margin, so an edge pixel does not fall into a sheet outside the list.
    selection = BBox(
        src.min_x - px, src.min_y - px, src.max_x + px, src.max_y + px, "EPSG:2180"
    )
    if geometry is None:
        godla = find_sheets_for_bbox(selection, scale, system="1992")
        what = "bbox"
    else:
        from kartograf.core.geometry import find_sheets_for_geometry

        godla = find_sheets_for_geometry(
            Path(geometry), target_scale=scale, layer=layer, system="1992"
        )
        if cutout.pinned is not None:
            godla = sorted(
                set(godla) | set(find_sheets_for_bbox(selection, scale, system="1992"))
            )
        what = "geometry"
    if not godla:
        raise ValidationError(f"No sheets found for the given {what}")
    return PlCutoutSheets(godla=tuple(godla))


# x >= 1 000 000 m are PL-2000 zone coordinates (zone = the millions digit,
# EPSG:2176-2179 for zones 5-8); PUWG 1992 fits below.
_PL2000_MIN_X = 1_000_000.0


def _reject_pl2000_sheets(sheet_paths: list[Path]) -> None:
    """A loud error instead of a silent hole (fact 7 of the 2026-09-28 plan).

    Until 0.7.0 the GUGiK index could return, for a PL-1992 godlo, a sheet of
    a newer campaign in PL-2000 (a silent URL fallback without the godlo,
    removed together with K4 — ``select_sheet_record`` rejects a record of
    another CRS). The guard stays for cached sheets downloaded by an earlier
    version: the mosaic forces EPSG:2180, so such a sheet would land outside
    the area and ``merge`` would skip it without a word. Reprojecting such
    sheets is stage 2.
    """
    import rasterio

    foreign: list[tuple[Path, int]] = []
    for path in sheet_paths:
        with rasterio.open(path) as src:
            if src.bounds.left >= _PL2000_MIN_X:
                foreign.append((Path(path), int(src.bounds.left // 1_000_000)))
    if foreign:
        listing = ", ".join(
            f"{p.name} (strefa {zone}, EPSG:{2171 + zone})" for p, zone in foreign[:5]
        )
        paths = ", ".join(str(p) for p, _ in foreign)
        raise ValidationError(
            f"{len(foreign)} arkusz(y) ma wspolrzedne PL-2000 zamiast PL-1992: "
            f"{listing}{' ...' if len(foreign) > 5 else ''} — plik pochodzi "
            "z wczesniejszej wersji Kartografa (cichy fallback skorowidza, "
            "usuniety w 0.7.0) i wycinek pominalby go po cichu (dziura nodata). "
            f"Usun go i ponow pobranie: {paths}"
        )


def build_pl_cutout(
    sheet_paths: list[Path],
    crop_bbox_2180: BBox,
    bbox_target: BBox,
    pixel_size: float,
    pinned: PinnedTransform | None,
    target_path: Path,
) -> tuple[str, ...]:
    """Stitch sheets, crop to ``crop_bbox_2180``; optional local warp.

    ``crop_bbox_2180`` is the SOURCE envelope (with a warp: request + margin),
    not the exact request. ``pinned is None`` = EPSG:2180 target: crop only
    (atomic ``os.replace``). Both write paths are atomic (the second is closed
    by the internal ``os.replace`` in ``warp_to_grid``), so an interrupted
    build does NOT leave a half-written file under ``target_path`` — and does
    not delete the previous result. Returns the godla of sheets reprojected
    separately (W1, below) — an empty tuple on the mosaic path.

    Sheet grid (R1): the crop is expanded OUTWARD to whole pixels of the
    sheet grid (of most sheets; < 1 px per side), so with an EPSG:2180 target
    values pass 1:1, without resampling, and the warp receives content
    without a sub-pixel shift. Grid phases are checked by
    ``check_source_grid`` BEFORE the mosaic (S5: 5 m sheets of the 2022
    campaign near Krakow each have a different phase; 1 m — one phase),
    because ``merge`` rewrites an off-grid sheet "through a window" — not
    always from the nearest pixel and with a nodata column/row at the seam:

    - EPSG:2180 target (``pinned is None``) and an off-grid sheet ->
      ``GridMismatchError`` (D3): 1:1 values are impossible, while a cutout
      with a warp or the sheets alone are available without network (the
      sheets stay in the cache);
    - warp (``pinned``) and an off-grid sheet -> **W1** (D8): ``warp_to_grid``
      receives a LIST of sheets and reprojects each ONCE, from its own grid
      onto the result grid (no intermediate mosaic); seams are independent
      warps (the interpolator does not see the neighbor across the seam), in
      the overlap the first in sort order wins — as in ``merge``;
    - one phase -> 1:1 mosaic (+ warp) as before (verified live bit for bit;
      ARCHITECTURE 4.3).

    On the mosaic path each sheet is wrapped in a VRT with an explicit
    EPSG:2180 and a Float32 band: a sheet with a ``.prj`` (e.g. added by
    Hydrograf) merges with a sheet without it (previously an ``incompatible
    input CRS`` error), and a sheet with only integers (GDAL reads it as
    Int32) does not truncate the heights of the others. Inputs are sorted:
    ``merge`` takes the result profile from the first source, and the first
    source wins in the overlap, so the result does not depend on the list
    order (parallel download returns sheets in completion order). The mosaic
    result is a GTiff with EPSG:2180.

    A sheet in PL-2000 coordinates (``x >= 1 000 000``) ends with
    ``ValidationError`` BEFORE the mosaic (``_reject_pl2000_sheets``) —
    otherwise ``merge`` would skip it silently and a nodata hole would
    remain in the result.

    The INTERMEDIATE mosaic file (``tmp``) is compressed (deflate, predictor
    3, 512 px tiles, BIGTIFF=IF_SAFER) ONLY when ``pinned is not None``: the
    warp then reads it once and deletes it, so compression pays in disk space
    without a readability cost. With an EPSG:2180 target the same file IS the
    result (``os.replace`` onto ``target_path``), so it stays uncompressed —
    as before (finding 9 of the max review wave).
    """
    _reject_pl2000_sheets(sheet_paths)
    from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

    paths = sorted(Path(p) for p in sheet_paths)
    grid = check_source_grid(paths)
    if grid.off_grid:
        if pinned is None:
            raise GridMismatchError(
                grid.describe_off_grid(len(paths), "arkuszy")
                + " — wycinek EPSG:2180 wymaga wspolnej siatki (wartosci 1:1). "
                "Zadaj wycinek w ukladzie z pelnym warpem (--target-crs "
                "EPSG:5514 albo EPSG:3045) albo pobierz obszar jako arkusze "
                "(bez --target-crs). Arkusze zostaja w cache.",
                grid.off_grid,
            )
        from kartograf.transform.raster import warp_to_grid

        # W1: each sheet from its own grid straight onto the result grid.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        warp_to_grid(
            paths,
            target_path,
            bbox_target,
            pixel_size,
            pinned,
            src_crs="EPSG:2180",
            nodata=PL_NODATA,
        )
        return tuple(sorted(s.path.stem for s in grid.off_grid))

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(
        f"{target_path.name}.{os.getpid()}_{threading.get_ident()}.mosaic.tif"
    )
    dst_kwds: dict = {"driver": "GTiff", "crs": "EPSG:2180"}
    if pinned is not None:
        # INTERMEDIATE file (the warp reads it once and deletes it): deflate +
        # floating-point predictor gives 2-3x less for NMT. 512 px tiles — the
        # AAIGrid profile has blockysize=1, and tiled without sizes ends with
        # RasterBlockError; BIGTIFF=IF_SAFER, because with compression GDAL does
        # not know the size up front (fact 10 of the 2026-09-28 plan).
        dst_kwds.update(
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=512,
            blockysize=512,
            bigtiff="IF_SAFER",
        )
    try:
        mosaic_and_crop(
            paths,
            crop_bbox_2180,
            tmp,
            nodata=PL_NODATA,
            dst_kwds=dst_kwds,
            # sheet grid (R1), sheets in VRT: EPSG:2180 + Float32 — facts 1-2, 5-6
            snap_to_source_grid=True,
            assign_crs="EPSG:2180",
            dtype="float32",
        )
        if pinned is None:
            os.replace(tmp, target_path)
        else:
            from kartograf.transform.raster import warp_to_grid

            warp_to_grid(
                tmp,
                target_path,
                bbox_target,
                pixel_size,
                pinned,
                src_crs="EPSG:2180",
                nodata=PL_NODATA,
            )
    finally:
        tmp.unlink(missing_ok=True)
    return ()


def _sheet_source(sheet_path: Path) -> dict:
    """Origin of a sheet from its sidecar (``extra.source``), best-effort."""
    entry: dict = {
        "sheet": sheet_path.stem,
        "url": None,
        "layer": None,
        "acquisition_date": None,
        "full_sheet": None,
    }
    sidecar = sheet_path.parent / f"{sheet_path.name}.meta.json"
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        source = meta["extra"]["source"]
    except (OSError, ValueError, KeyError, TypeError):
        return entry  # sheet without a sidecar (pre-0.7.0 cache) or without source
    if not isinstance(source, dict):
        return entry
    request = meta.get("request")
    request_sheet = request.get("sheet") if isinstance(request, dict) else None
    if isinstance(request_sheet, str):
        entry["sheet"] = request_sheet
    # a pre-ADR-031 sheet sidecar (Polish keys) yields null fields, not an error
    for key in ("url", "layer", "acquisition_date", "full_sheet"):
        entry[key] = source.get(key)
    return entry


def _partial_sheets(sources: list) -> tuple[str, ...]:
    """Godla of ``sheet_sources`` entries with ``full_sheet is False`` (E13).

    ``None`` (a sheet without a sidecar or a record without the flag) is not
    incomplete — we warn only about what the index explicitly declares.
    """
    # entries without a ``sheet`` string (pre-ADR-031 cutout sidecar with
    # Polish keys) carry no usable sheet name and are skipped
    return tuple(
        sorted(
            entry["sheet"]
            for entry in sources
            if isinstance(entry, dict)
            and entry.get("full_sheet") is False
            and isinstance(entry.get("sheet"), str)
        )
    )


def write_pl_cutout_sidecar(
    cutout: PlCutout,
    *,
    parent_request: dict | None = None,
    missing_sheets: tuple[str, ...] = (),
    sheet_paths: tuple[Path, ...] = (),
    off_grid_sheets: tuple[str, ...] = (),
    all_nodata: bool = False,
    unverified: dict[str, str] | None = None,
) -> None:
    """Best-effort cutout sidecar (an error does not abort the download).

    ``capability="sheet_files"``: the data come from OpenData sheets — the
    ``bbox_raster`` channel does not exist for 5m, and for 1m it declares only
    KRON86 (ADR-027, a departure from the letter of spec 6.1 item 5).
    ``missing_sheets`` (non-empty) -> ``extra.missing_sheets``: sheets without
    GUGiK data (R5). ``sheet_paths`` (non-empty) -> ``extra.sheet_sources``:
    the origin of each mosaic sheet ``{sheet, url, layer, acquisition_date,
    full_sheet}`` (``full_sheet`` = the full-sheet flag from the index record,
    E13) read from the sheet sidecars (``extra.source``, D5); a sheet without
    a sidecar or without ``source`` (cache from before 0.7.0) has ``null`` in
    the fields other than ``sheet``. ``off_grid_sheets`` (non-empty) ->
    ``extra.off_grid_sheets``: sheets with a different grid phase than the
    rest, reprojected separately (W1, S5) — the consumer sees that the cutout
    seams come from independent warps. ``all_nodata=True`` ->
    ``extra.all_nodata: true`` (E15): a cutout without a single valid pixel;
    skipping an existing cutout restores the flag from the sidecar instead of
    reading the raster. ``unverified`` (non-empty) ->
    ``extra.unverified_sheets`` ``{godlo: error}``: sheets from a local
    campaign without checking for a newer one (index unavailable, I-1).
    """
    from kartograf.sources.sidecar import emit_sidecar

    b = cutout.bbox_target
    extra: dict = {}
    if parent_request:
        extra["parent_request"] = parent_request
    if missing_sheets:
        # R5: sheets GUGiK has no data for — the cutout has nodata there
        extra["missing_sheets"] = list(missing_sheets)
    if sheet_paths:
        extra["sheet_sources"] = [_sheet_source(Path(p)) for p in sheet_paths]
    if off_grid_sheets:
        extra["off_grid_sheets"] = list(off_grid_sheets)
    if all_nodata:
        extra["all_nodata"] = True
    if unverified:
        extra["unverified_sheets"] = dict(unverified)
    emit_sidecar(
        "pl.gugik.nmt_5m" if cutout.resolution == "5m" else "pl.gugik.nmt_1m",
        cutout.target_path,
        request={
            "bbox": [b.min_x, b.min_y, b.max_x, b.max_y],
            "bbox_crs": cutout.target_crs,
        },
        vertical_crs=cutout.vertical_crs,
        horizontal_crs=cutout.target_crs,
        pinned_transforms={"horizontal": cutout.pinned},
        capability="sheet_files",
        nodata=PL_NODATA,
        extra=extra or None,
    )


def _require_matching_provider(cutout: PlCutout, provider) -> None:
    """An injected provider must supply the cutout's vertical CRS and resolution.

    The sheet segment (shared cache) and the cutout sidecar take the vertical
    CRS and resolution from ``cutout``, and the data from the provider — a
    mismatch would write e.g. KRON86 heights into the ``..._evrf2007``
    segment (or 5 m sheets into the 1 m segment), and later runs with
    ``skip_existing`` would use them without a warning. ``isinstance(str)``
    as in ``DownloadManager``: an absent attribute or a non-string one (e.g.
    a Mock) is not compared.
    """
    for attr in ("vertical_crs", "resolution"):
        actual = getattr(provider, attr, None)
        expected = getattr(cutout, attr)
        if isinstance(actual, str) and actual != expected:
            raise ValidationError(
                f"Provider niezgodny z wycinkiem: {attr} providera {actual}, "
                f"wycinka {expected} — przygotuj wycinek (prepare_pl_cutout) "
                "z pionem i rozdzielczoscia providera"
            )


def estimate_pl_cutout_bytes(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> tuple[int, int]:
    """(bytes, number of sheets to download) — a LOWER bound of disk needs.

    The uncompressed float32 result + sheets not yet downloaded at 5.5 B per
    value. The intermediate (compressed) mosaic file and filesystem overhead
    are NOT counted: this is a "surely not enough" check, not a guarantee.
    Cheap (``get_bbox`` uses the ``core.bbox`` cached transformer, N9), so a
    caller computing it themselves before ``run_pl_cutout`` does not pay
    twice.

    A sheet is counted when the standard path does not exist. Under
    ``newest`` a sheet with a newer campaign or with a removed target
    campaign (a hardlink survives removal of ``kampanie/``) will be
    downloaded despite the existing path, so the estimate stays a lower
    bound.
    """
    storage = storage or storage_for_provider(
        cutout.output_dir,
        resolution=cutout.resolution,
        vertical_crs=cutout.vertical_crs,
    )
    px = cutout.pixel_size
    need = cutout.estimated_bytes
    pending = 0
    for leaf in DownloadManager.expand_sheets(list(sheets.godla)):
        if storage.get_path(leaf, ".asc").exists():
            continue
        pending += 1
        frame = SheetParser(leaf).get_bbox("EPSG:2180")
        need += int(
            (frame.max_x - frame.min_x)
            * (frame.max_y - frame.min_y)
            / (px * px)
            * _ASC_BYTES_PER_VALUE
        )
    return need, pending


def check_pl_cutout_disk_space(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> None:
    """``ValidationError`` when the disk SURELY runs out of space (before network)."""
    import shutil

    need, pending = estimate_pl_cutout_bytes(cutout, sheets, storage=storage)
    probe = cutout.target_path.parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        height, width = cutout.grid_shape
        raise ValidationError(
            f"Za malo miejsca na dysku dla wycinka: potrzeba co najmniej "
            f"~{need / 2**30:.1f} GiB (siatka {width} x {height} px float32 + "
            f"{pending} arkuszy do pobrania), wolne ~{free / 2**30:.1f} GiB w {probe}"
        )


def _sidecar_sheet_list(extra: dict, key: str) -> tuple[str, ...]:
    """List of godla from the sidecar ``extra[key]`` — empty when the field is
    absent or has another shape (a hand-made sidecar or one from before the field)."""
    value = extra.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str))


def _sidecar_unverified(extra: dict) -> dict[str, str]:
    """``extra.unverified_sheets`` {godlo: error} — empty when absent/wrong shape."""
    value = extra.get("unverified_sheets")
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def skipped_pl_cutout(cutout: PlCutout) -> PlCutoutResult:
    """Result for a cutout that ALREADY exists (``force=False``): zero network.

    The nodata holes are what the file build wrote, so ``missing_sheets``
    (sheets without GUGiK data, R5) and ``off_grid_sheets`` (W1) come back
    from the sidecar of the existing cutout (``extra.missing_sheets``,
    ``extra.off_grid_sheets``), not as empty tuples — the consumer sees the
    same as at build time. Without a sidecar, with an unreadable one or
    without these fields (a cutout from before 0.7.0, without holes): empty.
    ``sheet_paths`` is empty — nobody touches the sheets here.
    ``partial_sheets`` (E13) comes back from ``extra.sheet_sources`` (entries
    with ``full_sheet: false``), and ``all_nodata`` (E15) from
    ``extra.all_nodata`` — the raster is not read.
    """
    sidecar = cutout.target_path.with_name(f"{cutout.target_path.name}.meta.json")
    try:
        extra = json.loads(sidecar.read_text(encoding="utf-8")).get("extra") or {}
    except (OSError, ValueError, AttributeError):
        extra = {}
    if not isinstance(extra, dict):
        extra = {}
    sources = extra.get("sheet_sources")
    return PlCutoutResult(
        path=cutout.target_path,
        skipped=True,
        missing_sheets=_sidecar_sheet_list(extra, "missing_sheets"),
        off_grid_sheets=_sidecar_sheet_list(extra, "off_grid_sheets"),
        all_nodata=extra.get("all_nodata") is True,
        partial_sheets=_partial_sheets(sources if isinstance(sources, list) else []),
        unverified=_sidecar_unverified(extra),
    )


def run_pl_cutout(
    cutout: PlCutout,
    sheets: PlCutoutSheets,
    *,
    provider=None,
    storage: FileStorage | None = None,
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
) -> PlCutoutResult:
    """Download the sheets, build the cutout, write the sidecar.

    ``force=False`` + an existing result file -> ``skipped=True`` without
    network (``missing_sheets``/``off_grid_sheets`` from the existing cutout's
    sidecar, ``skipped_pl_cutout``). Cached sheets are reused
    (``skip_existing = not force``).
    No data at the source (``NoCoverageError``) -> nodata + ``missing_sheets``;
    every other sheet download failure (``DownloadError``) ->
    ``DownloadError``; when NO sheet has data -> ``ValidationError``. Both
    errors are raised before anything is built. A cutout from sheets that
    contribute not a single valid pixel (N2: selection margin, a fully nodata
    sheet) IS CREATED and has ``all_nodata=True`` (+ ``logger.warning``) — it
    is a correct "no data" result, not an error.
    Another sheet exception (e.g. a write ``OSError``) propagates from here
    unchanged with ``max_workers=1``, and in a thread pool counts as a
    download failure (``DownloadError``). ``provider`` and ``storage`` default
    to the NMT factory and the ``FileStorage`` of the sheet segment (the CLI
    injects its own). An injected ``provider`` must supply the cutout's
    vertical CRS and resolution — otherwise ``ValidationError`` before any
    download. The disk space check (``check_pl_cutout_disk_space``) runs
    BEFORE ``DownloadManager`` — a lower bound, not a guarantee (finding 9 of
    the max review wave).
    """
    if provider is not None:
        _require_matching_provider(cutout, provider)
    if not force and cutout.target_path.exists():
        return skipped_pl_cutout(cutout)
    if provider is None:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=cutout.vertical_crs, resolution=cutout.resolution
        )
    if storage is None:
        storage = storage_for_provider(
            cutout.output_dir,
            provider,
            resolution=cutout.resolution,
            vertical_crs=cutout.vertical_crs,
        )
    check_pl_cutout_disk_space(cutout, sheets, storage=storage)
    manager = DownloadManager(
        output_dir=cutout.output_dir,
        provider=provider,
        storage=storage,
        vertical_crs=cutout.vertical_crs,
        resolution=cutout.resolution,
        max_workers=max_workers,
        sidecar_extra={"parent_request": parent_request} if parent_request else None,
    )
    sheet_paths = manager.download_sheets(
        list(sheets.godla), skip_existing=not force, on_progress=on_progress
    )
    summary = manager.last_result
    failed = list(summary.failed) if summary is not None else []
    no_data = set(summary.no_coverage) if summary is not None else set()
    fatal = [g for g in failed if g not in no_data]
    missing = tuple(sorted(g for g in failed if g in no_data))
    unverified = dict(summary.unverified) if summary is not None else {}
    if fatal:
        # R5: only a lack of data at the source can become nodata. Every other
        # failure (network, server, incomplete index response) ends the task — a
        # transient error must not leave a permanent hole in a file that is
        # later skipped as existing.
        total = summary.total if summary is not None else len(failed)
        raise DownloadError(
            f"{len(fatal)} z {total} arkuszy nie pobrano (blad pobrania, nie brak "
            f"danych): {', '.join(fatal)} — wycinek nie powstal; ponow pobranie"
        )
    if not sheet_paths:
        raise ValidationError(
            f"GUGiK nie ma danych dla zadnego z {len(missing)} arkuszy obszaru "
            "— wycinek nie powstal"
        )
    if missing:
        # info, not warning: the CLI prints the user-facing message, and the data
        # is carried by the result (missing_sheets) and the sidecar
        logger.info(
            f"Brak danych GUGiK dla {len(missing)} arkuszy wycinka: "
            f"{', '.join(missing)}"
        )
    try:
        off_grid = build_pl_cutout(
            list(sheet_paths),
            cutout.bbox_source_2180,
            cutout.bbox_target,
            cutout.pixel_size,
            cutout.pinned,
            cutout.target_path,
        )
    except BaseException:
        # finding 10: a failed build does not leave an empty <segment>/bbox/ tree
        # (a directory with a previous result is not empty — it stays)
        prune_empty_dirs(cutout.target_path.parent, cutout.output_dir)
        raise
    # N2: sheets from the selection margin (1 px / warp margin) may contribute
    # no pixel to the request area, and a border sheet may be entirely nodata —
    # the file is then a correct "no data" result, but the consumer should
    # know about it (CLI: Warning, exit code 0).
    from kartograf.transport.mosaic import has_valid_pixels

    all_nodata = not has_valid_pixels(cutout.target_path, PL_NODATA)
    if all_nodata:
        logger.warning(
            f"Wycinek {cutout.target_path} jest w calosci nodata — pobrane "
            f"arkusze ({len(sheet_paths)}) nie wnosza zadnego piksela w obszarze "
            "zadania (brak danych GUGiK / obszar poza pokryciem)"
        )
    write_pl_cutout_sidecar(
        cutout,
        parent_request=parent_request,
        missing_sheets=missing,
        sheet_paths=tuple(sheet_paths),
        off_grid_sheets=off_grid,
        all_nodata=all_nodata,
        unverified=unverified,
    )
    return PlCutoutResult(
        path=cutout.target_path,
        sheet_paths=tuple(sheet_paths),
        missing_sheets=missing,
        off_grid_sheets=off_grid,
        all_nodata=all_nodata,
        partial_sheets=_partial_sheets([_sheet_source(Path(p)) for p in sheet_paths]),
        unverified=unverified,
    )


def download_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
    cache=None,
) -> PlCutoutResult:
    """One merged NMT PL GeoTIFF in ``target_crs`` for a bbox or a geometry.

    Geometry mode: ``bbox`` is the geometry envelope (e.g.
    ``get_overall_bbox(path, target_crs="EPSG:2180")``), ``geometry`` — the file.
    NMT factory rule: 5m => EVRF2007 (with a log warning). The provider and
    session come from the factory; ``cache`` (``MetadataCache`` or ``None``)
    goes to the provider — index records are read and written only through
    the cache. ``force=True`` does NOT bypass the record cache by itself: to
    refresh records (skip the read, save the new choice), pass
    ``MetadataCache(refresh=True)`` — which is what the CLI does with
    ``--force`` (E14). Own provider/session: steps ``prepare_pl_cutout`` ->
    ``select_pl_cutout_sheets`` -> ``run_pl_cutout(provider=...)``.

    Returns
    -------
    PlCutoutResult
        ``path`` — the result file; ``skipped=True`` (no network) when the file
        already existed and ``force=False`` (``missing_sheets``/
        ``off_grid_sheets`` then from the sidecar of the existing cutout);
        ``missing_sheets`` — sheets without GUGiK data (nodata in their
        place); ``off_grid_sheets`` — sheets with a different grid phase,
        reprojected separately (W1; only with a warp); ``sheet_paths`` —
        sheets used for the mosaic (download completion order).

    Raises
    ------
    ValidationError
        Bad parameters, no sheets for the area, no sheet has GUGiK data, too
        little disk space or a sheet in PL-2000 coordinates.
    GridMismatchError
        (a ``ValidationError`` subclass) ``target_crs="EPSG:2180"`` while the
        sheets lie on different pixel grids (S5): 1:1 values are impossible —
        ``.off_grid`` lists the shifted sheets; the sheets stay in the cache,
        a cutout with a warp (5514/3045) can be built from them.
    TransformError
        No safe pinned EPSG:2180 -> ``target_crs`` operation (before any
        network).
    DownloadError
        Sheet download failure (network, server; a broken index layer query —
        up to 3 attempts on a network error, 429 and 5xx, other 4xx without
        retries — not a lack of data); the cutout is not created.
    OSError
        Sheet write error with ``max_workers=1`` (in a thread pool it counts
        as a download failure).

    ``parent_request`` goes to the cutout sidecar and the sidecars of sheets
    downloaded in this call only when it was given.
    """
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    from kartograf.providers.pl import create_nmt_provider

    provider = create_nmt_provider(
        vertical_crs=vertical_crs, resolution=resolution, cache=cache
    )
    cutout = prepare_pl_cutout(
        bbox,
        target_crs,
        output_dir=output_dir,
        resolution=resolution,
        vertical_crs=provider.vertical_crs,
    )
    if not force and cutout.target_path.exists():
        return skipped_pl_cutout(cutout)
    sheets = select_pl_cutout_sheets(
        cutout, geometry=geometry, layer=layer, scale=scale
    )
    return run_pl_cutout(
        cutout,
        sheets,
        provider=provider,
        max_workers=max_workers,
        force=force,
        on_progress=on_progress,
        parent_request=parent_request,
    )


def build_cutout_from_sheets(
    sheet_paths: Sequence[Path],
    bbox: BBox,
    target_crs: str,
    output_path: Path,
    *,
    resolution: str,
    vertical_crs: str,
) -> PlCutoutResult:
    """NMT PL cutout from LOCAL sheet files - no network (A10).

    The result goes to ``output_path`` chosen by the caller (also outside
    the Kartograf ``data/`` tree), with its sidecar next to it
    (``extra.sheet_sources`` from the sheets' sidecars, when present). Grid
    and warp rules as in ``download_pl_cutout``; the file is always built
    (no skip of an existing result).

    Raises
    ------
    ValidationError
        Empty sheet list, bad parameters, PL-2000 sheets.
    GridMismatchError
        EPSG:2180 target and sheets with different grid phases.
    TransformError
        No safe pinned operation to ``target_crs``.
    """
    if not sheet_paths:
        raise ValidationError("build_cutout_from_sheets: brak arkuszy wejsciowych")
    output_path = Path(output_path)
    prepared = prepare_pl_cutout(
        bbox,
        target_crs,
        output_dir=output_path.parent,
        resolution=resolution,
        vertical_crs=vertical_crs,
    )
    cutout = replace(prepared, target_path=output_path)
    sheets = tuple(Path(p) for p in sheet_paths)
    off_grid = build_pl_cutout(
        list(sheets),
        cutout.bbox_source_2180,
        cutout.bbox_target,
        cutout.pixel_size,
        cutout.pinned,
        cutout.target_path,
    )
    from kartograf.transport.mosaic import has_valid_pixels

    all_nodata = not has_valid_pixels(output_path, PL_NODATA)
    if all_nodata:
        logger.warning(f"Wycinek {output_path} jest w calosci nodata")
    write_pl_cutout_sidecar(
        cutout, sheet_paths=sheets, off_grid_sheets=off_grid, all_nodata=all_nodata
    )
    return PlCutoutResult(
        path=output_path,
        sheet_paths=sheets,
        off_grid_sheets=off_grid,
        all_nodata=all_nodata,
        partial_sheets=_partial_sheets([_sheet_source(p) for p in sheets]),
    )
