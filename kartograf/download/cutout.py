"""
Merged NMT/NMPT PL cutout in a requested CRS (ADR-027, ADR-035) — library layer.

WCS path (CLI ``--target-crs`` and ``download_pl_cutout``, ADR-035):
``prepare_pl_cutout`` -> ``run_pl_wcs_cutout``. One GetCoverage area from GUGiK
WCS on the 1 m sheet grid (chunks, ADR-034), the PL land mask from PRG (nodata
-9999 outside ``A00 - W02 - W03``), then for EPSG:2180 the file as is, for
another CRS a local warp with a FORCED pinned operation (ADR-024/027). The
result is ONE GeoTIFF ``<output_dir>/<segment>/bbox/<coords>_<YYYYMMDD>.tif``
+ sidecar; every run downloads (the server composition may change).

The CLI (``kartograf download --bbox/--geometry --target-crs``) is a thin
layer over this module: it prints messages and translates exceptions into
exit codes. There is no ``print`` or argparse here.

Example::

    from kartograf import BBox, download_pl_cutout

    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        "EPSG:5514",
        output_dir="./data",
    )
    print(result.path)
"""

import logging
import os
import shutil
import threading
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from kartograf.core.bbox import BBox, is_czech_crs, transform_bbox
from kartograf.download.storage import bbox_cutout_path, prune_empty_dirs
from kartograf.exceptions import ValidationError
from kartograf.transform.crs import CONTENT_POLICY, WARP_MARGIN_PX, PinnedTransform

logger = logging.getLogger(__name__)

# nodata of GUGiK WCS elevation
PL_NODATA = -9999.0
# result grid pixel per NMT PL resolution
PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}
# target CRS with a pinned EPSG:2180 -> target operation (KNOWN_PATHS, ADR-027)
SUPPORTED_TARGET_CRS = ("EPSG:2180", "EPSG:5514", "EPSG:3045")
# CONTENT reprojection operation policy (CONTENT_POLICY) and source envelope
# margin (WARP_MARGIN_PX) — shared with the CZ flow, from transform/crs.py (D9).
_VERTICAL_CRS = ("EVRF2007", "KRON86")
# Products of a PL WCS cutout.
CUTOUT_PRODUCTS = ("nmt", "nmpt")
# Layers of the PL land mask (sidecar ``extra.mask.layers``, ADR-035).
LAND_MASK_LAYERS = (
    "A00_Granice_panstwa",
    "-W02_Morze_terytorialne_RP",
    "-W03_Morskie_wody_wewnetrzne",
)


@dataclass(frozen=True)
class PlCutout:
    """Prepared (fail-fast, no network) NMT/NMPT PL cutout."""

    target_crs: str
    resolution: str
    vertical_crs: str  # ACTUAL vertical CRS (after the 5m rule => EVRF2007)
    output_dir: Path
    bbox_2180: BBox  # exact request in EPSG:2180
    bbox_source_2180: BBox  # request + warp margin: WCS area
    bbox_target: BBox  # result grid (target CRS)
    pinned: PinnedTransform | None  # None for EPSG:2180 (crop only)
    target_path: Path  # without the download date (WCS adds it, run_pl_wcs_cutout)
    product: str = "nmt"  # "nmt" or "nmpt"

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
class PlCutoutResult:
    """Result of ``run_pl_wcs_cutout`` / ``download_pl_cutout``.

    ``path`` carries the download date, ``skipped`` is always ``False``,
    and ``masked_pixels``/``zero_pixels`` describe the land mask.
    """

    path: Path
    skipped: bool = False
    all_nodata: bool = False
    masked_pixels: int = 0
    zero_pixels: int = 0


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
    product: str = "nmt",
) -> PlCutout:
    """Fail-fast cutout preparation: operation, bboxes and result path.

    Zero network. ``TransformError`` when the EPSG:2180 -> ``target_crs``
    pair has no pinned operation (ADR-024/027); ``ValidationError`` on bad
    parameters. ``vertical_crs`` is the ACTUAL vertical CRS: with 5m only
    EVRF2007 (``require_nmt_vertical_crs``; 5m with KRON86 =
    ``ValidationError``). ``product``: ``"nmt"`` or ``"nmpt"`` (1m only; NMPT
    cutouts exist only on the WCS path, ``run_pl_wcs_cutout``).

    The cutout is always a GeoTIFF (``.tif``) — the descriptor's
    ``default_extension`` (``.asc``) concerns sheets, not the cutout.
    ``target_path`` has no date; the WCS path adds the download date.
    """
    if product not in CUTOUT_PRODUCTS:
        raise ValidationError(
            f"Produkt wycinka PL: {' albo '.join(CUTOUT_PRODUCTS)} (podano {product})"
        )
    if target_crs not in SUPPORTED_TARGET_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka PL: {target_crs} "
            f"(dostepne: {', '.join(SUPPORTED_TARGET_CRS)})"
        )
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if product == "nmpt" and resolution != "1m":
        raise ValidationError(f"NMPT PL jest tylko 1m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    from kartograf.providers.pl import require_nmt_vertical_crs

    require_nmt_vertical_crs(resolution, vertical_crs)

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

    if product == "nmpt":
        key = "pl.gugik.nmpt"
    else:
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
        product=product,
    )


def _cutout_descriptor_key(cutout: PlCutout) -> str:
    """Source descriptor of the cutout's product and resolution."""
    if cutout.product == "nmpt":
        return "pl.gugik.nmpt"
    return "pl.gugik.nmt_5m" if cutout.resolution == "5m" else "pl.gugik.nmt_1m"


def _require_matching_provider(cutout: PlCutout, provider) -> None:
    """Reject a provider with a different product, vertical CRS or resolution.

    The cutout path and sidecar describe ``cutout``; a mismatched provider
    would silently write data for a different product or vertical datum.
    """
    checks = (
        ("vertical_crs", cutout.vertical_crs),
        ("resolution", cutout.resolution),
        ("descriptor_key", _cutout_descriptor_key(cutout)),
    )
    for attr, expected in checks:
        actual = getattr(provider, attr, None)
        if isinstance(actual, str) and actual != expected:
            raise ValidationError(
                f"Provider niezgodny z wycinkiem: {attr} providera {actual}, "
                f"wycinka {expected} — przygotuj wycinek (prepare_pl_cutout) "
                "z produktem, pionem i rozdzielczoscia providera"
            )


def _wcs_1m_only(resolution: str) -> ValidationError:
    return ValidationError(
        f"Wycinek PL z WCS GUGiK jest tylko 1m (podano {resolution}); "
        "NMT 5 m pobieraj jako arkusze bez --target-crs"
    )


def dated_cutout_path(cutout: PlCutout, day: date) -> Path:
    """WCS cutout path: ``<coords>_<YYYYMMDD>.tif`` next to ``cutout.target_path``."""
    path = cutout.target_path
    return path.with_name(f"{path.stem}_{day:%Y%m%d}{path.suffix}")


def _wcs_cutout_provider(cutout: PlCutout):
    """Default provider of the cutout's product and vertical CRS (1 m)."""
    if cutout.product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        return GugikNmptProvider(vertical_crs=cutout.vertical_crs)
    from kartograf.providers.pl import create_nmt_provider

    return create_nmt_provider(vertical_crs=cutout.vertical_crs, resolution="1m")


def _check_wcs_disk_space(cutout: PlCutout, path: Path) -> None:
    """``ValidationError`` when the disk SURELY runs out (result + 2180 work file)."""
    need = 2 * cutout.estimated_bytes
    probe = path.parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        height, width = cutout.grid_shape
        raise ValidationError(
            f"Za malo miejsca na dysku dla wycinka: potrzeba co najmniej "
            f"~{need / 2**30:.1f} GiB (siatka {width} x {height} px float32 i plik "
            f"roboczy EPSG:2180), wolne ~{free / 2**30:.1f} GiB w {probe}"
        )


def write_pl_wcs_cutout_sidecar(
    cutout: PlCutout,
    path: Path,
    provider,
    *,
    parent_request: dict | None = None,
    masked_pixels: int = 0,
    zero_pixels: int = 0,
    all_nodata: bool = False,
) -> None:
    """Best-effort sidecar of a WCS cutout (an error does not abort the download).

    ``capability="bbox_raster"`` of the cutout's descriptor. ``extra.source``
    names the WCS request (``service``, ``endpoint``, ``coverage``, ``format``)
    and ``composition: "server"`` — the flight shown by the server, not chosen
    by Kartograf (no campaign or year, ADR-035). ``extra.mask`` describes the
    PRG land mask and ``masked_pixels``; ``extra.zero_pixels`` (> 0 only) counts
    0.0 pixels kept on land; ``extra.all_nodata`` when no pixel is valid.
    """
    from kartograf.providers.pl.wcs import HEIGHT_AAIGRID
    from kartograf.sources.sidecar import emit_sidecar
    from kartograf.transport.aaigrid import ASC_MEDIA_TYPE

    endpoint, coverage = provider._wcs_target()
    asc = provider._wcs_height_format() == HEIGHT_AAIGRID
    extra: dict = {}
    if parent_request:
        extra["parent_request"] = parent_request
    extra["source"] = {
        "service": "WCS",
        "endpoint": endpoint,
        "coverage": coverage,
        "format": ASC_MEDIA_TYPE if asc else provider.WCS_FORMATS["GTiff"],
        "composition": "server",
    }
    extra["mask"] = {
        "source": "PRG",
        "layers": list(LAND_MASK_LAYERS),
        "masked_pixels": masked_pixels,
    }
    if zero_pixels:
        extra["zero_pixels"] = zero_pixels
    if all_nodata:
        extra["all_nodata"] = True
    b = cutout.bbox_target
    emit_sidecar(
        _cutout_descriptor_key(cutout),
        path,
        request={
            "bbox": [b.min_x, b.min_y, b.max_x, b.max_y],
            "bbox_crs": cutout.target_crs,
        },
        vertical_crs=cutout.vertical_crs,
        horizontal_crs=cutout.target_crs,
        pinned_transforms={"horizontal": cutout.pinned},
        capability="bbox_raster",
        nodata=PL_NODATA,
        extra=extra,
    )


def run_pl_wcs_cutout(
    cutout: PlCutout,
    *,
    provider=None,
    parent_request: dict | None = None,
    today: date | None = None,
) -> PlCutoutResult:
    """Download the cutout from GUGiK WCS, mask it to PL land, write the sidecar.

    Steps (ADR-035): the PL land mask for ``bbox_source_2180`` from PRG
    (``fetch_land_mask``; a failure = ``DownloadError`` before any WCS
    request), one GetCoverage area on the 1 m sheet grid
    (``bbox_source_2180`` aligned OUTWARD, chunks per ``plan_wcs_chunks``),
    pixels outside ``A00 - W02 - W03`` -> -9999 (0.0 on land stays data), then
    EPSG:2180: that file is the result; another CRS: ``warp_to_grid`` with the
    pinned operation onto ``bbox_target``.

    The result is ``<coords>_<YYYYMMDD>.tif`` (``today``, default: local
    date). Every run downloads; on the same day the new file replaces the
    previous one atomically only after a successful build — a failed run
    leaves the previous file and its sidecar untouched and no empty
    ``bbox/`` tree. The content is the server's flight composition, not the
    newest flight per ADR-028 (individual sheet downloads).

    ``provider`` (default: NMT or NMPT provider of the cutout's vertical CRS)
    must match the cutout's product, vertical CRS and resolution.

    Raises
    ------
    ValidationError
        ``cutout.resolution`` other than ``"1m"``, provider mismatch or
        too little disk space — before any network.
    DownloadError
        PRG or WCS failure (after retries), or a WCS response whose ASC size or
        corner differs from the request; no result is written.
    """
    if cutout.resolution != "1m":
        raise _wcs_1m_only(cutout.resolution)
    if provider is not None:
        _require_matching_provider(cutout, provider)
    else:
        provider = _wcs_cutout_provider(cutout)
    path = dated_cutout_path(cutout, today or date.today())
    _check_wcs_disk_space(cutout, path)

    from kartograf.providers.pl.prg import fetch_land_mask
    from kartograf.transport.chunks import align_bbox
    from kartograf.transport.mosaic import has_valid_pixels

    timeout = provider.DEFAULT_TIMEOUT
    b = cutout.bbox_source_2180
    # before WCS: a PRG failure must not waste a long download. The mask covers
    # the raster actually written (aligned OUTWARD to the sheet grid): a W02/W03
    # polygon touching only an edge pixel centre must be returned by the BBOX.
    grid = provider.WCS_GRID
    mask_area = align_bbox(b, grid.step, grid)[0] if grid is not None else b
    mask = fetch_land_mask(mask_area, timeout=timeout)
    description = (
        f"wycinek {cutout.product.upper()} {cutout.vertical_crs} "
        f"({b.min_x:.0f},{b.min_y:.0f})-({b.max_x:.0f},{b.max_y:.0f})"
    )
    work = path.with_name(f"{path.name}.{os.getpid()}_{threading.get_ident()}.wcs.tif")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        provider._download_wcs(b, work, "GTiff", timeout, description)
        masked, zeros = mask.apply(work, PL_NODATA)
        if cutout.pinned is None:
            os.replace(work, path)
        else:
            from kartograf.transform.raster import warp_to_grid

            warp_to_grid(
                work,
                path,
                cutout.bbox_target,
                cutout.pixel_size,
                cutout.pinned,
                src_crs="EPSG:2180",
                nodata=PL_NODATA,
            )
    except BaseException:
        work.unlink(missing_ok=True)
        # a failed run leaves no empty <segment>/bbox/ tree (a directory with a
        # previous result is not empty — it stays)
        prune_empty_dirs(path.parent, cutout.output_dir)
        raise
    work.unlink(missing_ok=True)

    all_nodata = not has_valid_pixels(path, PL_NODATA)
    if all_nodata:
        logger.warning(
            "Cutout %s is entirely nodata: the area lies outside PL land (PRG mask)",
            path,
        )
    write_pl_wcs_cutout_sidecar(
        cutout,
        path,
        provider,
        parent_request=parent_request,
        masked_pixels=masked,
        zero_pixels=zeros,
        all_nodata=all_nodata,
    )
    return PlCutoutResult(
        path=path, all_nodata=all_nodata, masked_pixels=masked, zero_pixels=zeros
    )


def download_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
    parent_request: dict | None = None,
    product: str = "nmt",
) -> PlCutoutResult:
    """One NMT/NMPT PL GeoTIFF in ``target_crs`` for a bbox, from GUGiK WCS.

    ``prepare_pl_cutout(product=)`` -> ``run_pl_wcs_cutout`` (ADR-035): 1 m on
    the sheet grid, the server's flight composition (not the newest flight per
    ADR-028), nodata -9999 outside PL land (PRG mask; 0.0 on land stays data),
    the download date in the file name, every call downloads. For a geometry
    request, pass its envelope as ``bbox`` (e.g. via
    ``get_overall_bbox(path, target_crs="EPSG:2180")``).

    Own provider/session: ``run_pl_wcs_cutout(provider=...)``.

    Returns
    -------
    PlCutoutResult
        ``path`` — the dated result file; ``masked_pixels``/``zero_pixels`` —
        land mask counts; ``all_nodata`` — the area is outside PL land.

    Raises
    ------
    ValidationError
        Bad parameters (also ``resolution="5m"``), too little disk space.
    TransformError
        No safe pinned EPSG:2180 -> ``target_crs`` operation (before any
        network).
    DownloadError
        PRG or WCS failure; the cutout is not created.

    ``parent_request`` goes to the cutout sidecar only when it was given.
    """
    if resolution != "1m":
        if resolution not in PIXEL_SIZES:
            raise ValidationError(f"Rozdzielczosc NMT PL: 1m (podano {resolution})")
        raise _wcs_1m_only(resolution)
    cutout = prepare_pl_cutout(
        bbox,
        target_crs,
        output_dir=output_dir,
        resolution=resolution,
        vertical_crs=vertical_crs,
        product=product,
    )
    return run_pl_wcs_cutout(cutout, parent_request=parent_request)
