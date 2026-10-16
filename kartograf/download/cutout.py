"""
Merged NMT/NMPT PL cutout in a requested CRS (ADR-027, ADR-035) — library layer.

WCS path (CLI ``--cutout`` and ``download_pl_cutout``, ADR-035/038):
``_prepare_pl_cutout`` -> ``_run_pl_wcs_cutout``. One GetCoverage area from GUGiK
WCS on the 1 m sheet grid (chunks, ADR-034), the PL land mask from PRG (nodata
-9999 outside ``A00 - W02 - W03``), then for EPSG:2180 the file as is, for
another CRS a local warp with a FORCED pinned operation (ADR-024/027). The
standard path ``<output_dir>/<segment>/bbox/<coords>.tif`` links to a version
in ``<segment>/versions/bbox/``. A local version needs no PRG or WCS request.

Public pair (Z2): ``download_pl_cutout`` / ``check_pl_cutout`` with the same
selection arguments. Data messages (cutout size, all-nodata) are
``Notice``s in the result and go to ``on_notice`` when emitted. There is no
``print`` or argparse here.

Example::

    from kartograf import BBox, download_pl_cutout

    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        horizontal_crs="EPSG:5514",
        output_dir="./data", vertical_crs="EVRF2007", product="nmt",
    )
    print(result.file.path)
"""

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords
from kartograf.download.area import bbox_to_2180
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    link_version,
    local_version,
    refreshes_cache,
    validate_update,
)
from kartograf.download.plan import (
    PlanItem,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import bbox_cutout_path, bbox_slot
from kartograf.download.versions import ContentDigest, VersionRef, read_version
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.notices import ALL_NODATA, CUTOUT_SIZE, Notice, NoticeSink
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import channel_signal, get_source
from kartograf.sources.variants import ProductVariant, variants
from kartograf.transform.crs import CONTENT_POLICY, WARP_MARGIN_PX, PinnedTransform

logger = logging.getLogger(__name__)

# nodata of GUGiK WCS elevation
PL_NODATA = -9999.0
# PL WCS cutouts have exactly one admissible resolution: 1 m.
PIXEL_SIZE = 1.0
# target CRS with a pinned EPSG:2180 -> target operation (KNOWN_PATHS, ADR-027)
CUTOUT_CRS = ("EPSG:2180", "EPSG:5514", "EPSG:3045")
# CONTENT reprojection operation policy (CONTENT_POLICY) and source envelope
# margin (WARP_MARGIN_PX) — shared with the CZ flow, from transform/crs.py (D9).
# Products of a PL WCS cutout.
CUTOUT_PRODUCTS = ("nmt", "nmpt")
# Seconds of one GUGiK WCS request of a cutout chunk (ASC grid, ~1 Mpx),
# retries included - measured live: NMT 3 x 4 km, 16 requests in 410-667 s
# (2026-10-16); NMT and NMPT 2 x 2 km, 6 requests each, 391 s both
# (2026-10-17). The ``CUTOUT_SIZE`` notice estimates a series with it.
WCS_REQUEST_SECONDS = (25, 40)


def wcs_time_text(requests: int) -> str:
    """Estimated time of ``requests`` WCS requests one after another:
    ``ok. 50-80 s`` below 2 minutes, else ``ok. 7-11 min``."""
    low, high = (requests * seconds for seconds in WCS_REQUEST_SECONDS)
    if high < 120:
        return f"ok. {low}-{high} s"
    low_min = max(1, round(low / 60))
    return f"ok. {low_min}-{max(low_min, round(high / 60))} min"


# Layers of the PL land mask (sidecar ``extra.mask.layers``, ADR-035).
LAND_MASK_LAYERS = (
    "A00_Granice_panstwa",
    "-W02_Morze_terytorialne_RP",
    "-W03_Morskie_wody_wewnetrzne",
)


@dataclass(frozen=True)
class PlCutout:
    """A prepared NMT/NMPT PL WCS cutout, always on the 1m grid (internal step).

    ``horizontal_crs`` is EPSG:2180 (native PL), EPSG:5514 or EPSG:3045
    (reprojected). ``vertical_crs`` is EVRF2007 (current heights) or KRON86
    (legacy heights). ``output_dir`` is the explicit output base directory;
    ``product`` is "nmt" (terrain heights) or "nmpt" (surface heights).
    Remaining fields contain the prepared extent, transform and result path.
    """

    horizontal_crs: str
    vertical_crs: str
    output_dir: Path
    bbox_2180: BBox
    bbox_source_2180: BBox
    bbox_target: BBox
    pinned: PinnedTransform | None
    target_path: Path
    product: str

    @property
    def pixel_size(self) -> float:
        """Result grid pixel size (m)."""
        return PIXEL_SIZE

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
    """Versioned cutout file, its PRG mask counts and data notices.

    ``file`` is ``None`` only when a plan skips this cutout and nothing is
    available locally. Otherwise the file points to the standard bbox link.
    ``notices`` holds the cutout size and all-nodata messages (Z3).
    """

    file: VersionedFile | None
    all_nodata: bool = False
    masked_pixels: int = 0
    zero_pixels: int = 0
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def _prepare_pl_cutout(
    bbox: BBox,
    horizontal_crs: str,
    *,
    output_dir: str | Path,
    vertical_crs: str,
    product: str,
) -> PlCutout:
    """Prepare a PL WCS cutout without network access.

    ``bbox`` is the requested extent in a supported CRS. ``horizontal_crs`` is
    "EPSG:2180" (native), "EPSG:5514" or "EPSG:3045" (pinned reprojection).
    ``output_dir`` selects the result directory. ``vertical_crs`` is
    "EVRF2007" (current heights) or "KRON86" (legacy heights).
    ``product`` is "nmt" (terrain model) or "nmpt" (surface model);
    both are available only at 1m for WCS cutouts.

    Raises ``ValidationError`` for invalid choices and ``TransformError``
    when no safe pinned reprojection is available. The GeoTIFF
    ``target_path`` is the undated standard link to the versioned result.
    """
    from kartograf.download.options import validate_request_bbox

    validate_request_bbox(bbox)
    if product not in CUTOUT_PRODUCTS:
        raise ValidationError(
            f"Produkt wycinka PL: {' albo '.join(CUTOUT_PRODUCTS)} (podano {product})"
        )
    if horizontal_crs not in CUTOUT_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka PL: {horizontal_crs} "
            f"(dostepne: {', '.join(CUTOUT_CRS)})"
        )
    if wcs_variant(product, vertical_crs) is None:
        systems = sorted(
            {
                v.vertical_crs
                for v in variants(product=product, country="PL")
                if v.vertical_crs is not None
            }
        )
        raise ValidationError(
            f"Uklad wysokosci {product.upper()} PL: {' albo '.join(systems)} "
            f"(podano {vertical_crs})"
        )

    from kartograf.providers.cuzk.raster import bbox_to_crs
    from kartograf.sources.registry import get_source

    # local import: tests replace the operation in the transform.crs module
    from kartograf.transform.crs import build_pinned_transform

    bbox_2180 = bbox_to_2180(bbox)
    pinned = None
    bbox_target = bbox_2180
    bbox_source_2180 = bbox_2180
    if horizontal_crs != "EPSG:2180":
        center = (
            (bbox_2180.min_x + bbox_2180.max_x) / 2,
            (bbox_2180.min_y + bbox_2180.max_y) / 2,
        )
        # content policy as in the CZ flow + probe at the request center
        pinned = build_pinned_transform(
            "EPSG:2180", horizontal_crs, replace(CONTENT_POLICY, probe_point=center)
        )
        bbox_target = bbox_to_crs(bbox_2180, horizontal_crs, pinned)
        # The source must cover the WHOLE result grid: the target envelope maps
        # back to 2180 larger than the request (CRS rotation), and the
        # interpolator needs a halo. Mirror of the CZ flow's _native_request_bbox.
        # Without `pinned` — the pinned operation is DIRECTIONAL (2180 -> target),
        # CZ does the same.
        back = bbox_to_crs(bbox_target, "EPSG:2180")
        margin = WARP_MARGIN_PX * PIXEL_SIZE
        bbox_source_2180 = BBox(
            back.min_x - margin,
            back.min_y - margin,
            back.max_x + margin,
            back.max_y + margin,
            "EPSG:2180",
        )

    key = _cutout_descriptor_key(product, vertical_crs)
    subdir = get_source(key).resolve_subdir(system="1992", vertical_crs=vertical_crs)
    return PlCutout(
        horizontal_crs=horizontal_crs,
        vertical_crs=vertical_crs,
        output_dir=Path(output_dir),
        bbox_2180=bbox_2180,
        bbox_source_2180=bbox_source_2180,
        bbox_target=bbox_target,
        pinned=pinned,
        target_path=bbox_cutout_path(output_dir, subdir, bbox_target, ".tif"),
        product=product,
    )


def wcs_variant(product: str, vertical_crs: str) -> ProductVariant | None:
    """The product's variant with a WCS channel (the 1 m grid, registry)."""
    for variant in variants(product=product, country="PL", vertical_crs=vertical_crs):
        channels = get_source(variant.source).channels
        if any(channel.transport == TransportKind.WCS for channel in channels):
            return variant
    return None


def _cutout_descriptor_key(product: str, vertical_crs: str) -> str:
    """Source descriptor of the cutout (the WCS variant: 1 m grid)."""
    variant = wcs_variant(product, vertical_crs)
    if variant is None:  # pragma: no cover - guarded by _prepare_pl_cutout
        raise ValidationError(f"{product.upper()} PL nie ma wycinka WCS")
    return variant.source


def _require_matching_provider(cutout: PlCutout, provider) -> None:
    """Reject a provider with a different product, vertical CRS or resolution.

    The cutout path and sidecar describe ``cutout``; a mismatched provider
    would silently write data for a different product or vertical datum.
    """
    checks = (
        ("vertical_crs", cutout.vertical_crs),
        ("resolution", "1m"),
        ("descriptor_key", _cutout_descriptor_key(cutout.product, cutout.vertical_crs)),
    )
    for attr, expected in checks:
        actual = getattr(provider, attr, None)
        if isinstance(actual, str) and actual != expected:
            raise ValidationError(
                f"Provider niezgodny z wycinkiem: {attr} providera {actual}, "
                f"wycinka {expected} - podaj provider z produktem, pionem "
                "i rozdzielczoscia wycinka"
            )


def _wcs_cutout_provider(cutout: PlCutout, cache: MetadataCache | None = None):
    """Default provider of the cutout's product and vertical CRS (1 m)."""
    if cutout.product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        return GugikNmptProvider(
            vertical_crs=cutout.vertical_crs, resolution="1m", cache=cache
        )
    from kartograf.providers.pl import create_nmt_provider

    return create_nmt_provider(
        vertical_crs=cutout.vertical_crs, resolution="1m", cache=cache
    )


def _check_wcs_disk_space(cutout: PlCutout, staged: Path) -> None:
    """``ValidationError`` if work directory lacks result + source space."""
    need = 2 * cutout.estimated_bytes
    probe = staged.parent
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
    version: VersionRef,
    digest: ContentDigest,
    http: dict | None,
    parent_request: dict | None = None,
    masked_pixels: int = 0,
    zero_pixels: int = 0,
    all_nodata: bool = False,
) -> None:
    """Write the mandatory, exclusive sidecar of a WCS cutout version.

    ``extra.source`` names the WCS request and its server flight composition.
    ``extra.mask`` describes the PRG mask and ``masked_pixels``;
    ``extra.zero_pixels`` counts 0.0 pixels kept on land (when positive);
    ``extra.all_nodata`` is set when no pixel is valid. The version, digest
    and HTTP signal are stored by the same sidecar contract as other tracks.
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
    if http is not None:
        extra["http"] = http
    b = cutout.bbox_target
    emit_sidecar(
        _cutout_descriptor_key(cutout.product, cutout.vertical_crs),
        path,
        request={
            "bbox": bbox_coords(b),
            "bbox_crs": cutout.horizontal_crs,
        },
        vertical_crs=cutout.vertical_crs,
        horizontal_crs=cutout.horizontal_crs,
        pinned_transforms={"horizontal": cutout.pinned},
        capability="bbox_raster",
        nodata=PL_NODATA,
        extra=extra,
        digest=(digest.sha256, digest.size_bytes),
        version=version.to_extra(),
        exclusive=True,
    )


def _pl_cutout_slot(cutout: PlCutout) -> FileSlot:
    """Version slot for the undated bbox link of this prepared cutout."""
    from kartograf.sources.registry import get_source

    subdir = get_source(
        _cutout_descriptor_key(cutout.product, cutout.vertical_crs)
    ).resolve_subdir(system="1992", vertical_crs=cutout.vertical_crs)
    return bbox_slot(cutout.output_dir, subdir, cutout.bbox_target, ".tif")


def _check_prepared(cutout: PlCutout) -> UpdatePlan:
    """Plan of a prepared cutout from the local store only (signal ``none``)."""
    slot = _pl_cutout_slot(cutout)
    item = inspect_version(
        slot,
        track="pl_cutout",
        unit=slot.std.stem,
        signal=channel_signal(
            _cutout_descriptor_key(cutout.product, cutout.vertical_crs),
            TransportKind.WCS,
        ),
    )
    return new_plan(store_id(cutout.output_dir), (item,))


def check_pl_cutout(
    bbox: BBox,
    *,
    horizontal_crs: str,
    output_dir: str | Path,
    vertical_crs: str,
    product: str,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_pl_cutout`` with the same arguments, no download.

    The WCS channel has no remote version signal, so the plan reads only the
    local store: no PRG, WCS or metadata cache request is made. ``cache`` and
    ``on_notice`` are accepted for symmetry with ``download_pl_cutout``.

    Raises ``ValidationError`` for invalid choices and ``TransformError``
    when no safe pinned reprojection exists, exactly as the download does.
    """
    del cache, on_notice  # same signature as the download (Z2); unused here
    cutout = _prepare_pl_cutout(
        bbox,
        horizontal_crs,
        output_dir=output_dir,
        vertical_crs=vertical_crs,
        product=product,
    )
    return _check_prepared(cutout)


def _cutout_result(
    file: VersionedFile | None, *, stale: tuple[PlanItem, ...] = ()
) -> PlCutoutResult:
    """Read mask counts from the immutable version sidecar, never from the raster."""
    if file is None:
        return PlCutoutResult(None, stale=stale)
    version = read_version(file.version_path.parent, file.version_path.name)
    if version is None:
        raise DownloadError(f"{file.version_path}: wersja bez czytelnego sidecara")
    extra = version.meta.get("extra") or {}
    return PlCutoutResult(
        file=file,
        all_nodata=bool(extra.get("all_nodata", False)),
        masked_pixels=int((extra.get("mask") or {}).get("masked_pixels", 0)),
        zero_pixels=int(extra.get("zero_pixels", 0)),
        stale=stale,
    )


def _run_pl_wcs_cutout(
    cutout: PlCutout,
    *,
    provider=None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict | None = None,
    now: datetime | None = None,
    sink: NoticeSink | None = None,
) -> PlCutoutResult:
    """Use the local cutout or download a new immutable GUGiK WCS version.

    On a download (ADR-035), check disk space, get the PRG land mask before
    WCS, request the source on its 1 m sheet grid, mask pixels outside
    ``A00 - W02 - W03`` to -9999 (on-land zeroes stay data), then move the
    result or warp it with the pinned operation onto ``bbox_target``. All
    work happens inside the private ``versions/.incoming/`` directory.
    ``now`` supplies the UTC ``downloaded`` version label.

    A local version has no PRG/WCS request and its mask counts come from its
    immutable sidecar. A plan executes only matching missing positions; stale
    or removed positions are skipped. Without a local version, a skipped
    position has ``file=None``. ``sink`` receives the ``CUTOUT_SIZE`` notice
    right before the first request of a download that needs several WCS
    chunks or at least 1 GiB.
    """
    validate_update(update)
    if provider is not None:
        _require_matching_provider(cutout, provider)
    slot = _pl_cutout_slot(cutout)
    signal = channel_signal(
        _cutout_descriptor_key(cutout.product, cutout.vertical_crs), TransportKind.WCS
    )
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(cutout.output_dir))
        current = inspect_version(
            slot, track="pl_cutout", unit=slot.std.stem, signal=signal
        )
        todo, excluded = select_planned(plan, [current], "pl_cutout")
        stale = tuple(excluded)
        if not todo:
            local = local_version(slot)
            if local is None:
                return _cutout_result(None, stale=stale)
            link_version(slot.std, local, refresh=False)
            return _cutout_result(
                VersionedFile(slot.std, "local", local.label, local.sha256, local.path),
                stale=stale,
            )

    from kartograf.providers.pl.prg import fetch_land_mask
    from kartograf.transport.chunks import align_bbox
    from kartograf.transport.mosaic import has_valid_pixels

    selected_provider = provider
    masked_pixels = zero_pixels = 0
    all_nodata = False

    def fetch(staged: Path) -> None:
        nonlocal selected_provider, masked_pixels, zero_pixels, all_nodata
        if selected_provider is None:
            selected_provider = _wcs_cutout_provider(cutout)
        chunks = len(selected_provider.plan_wcs_chunks(cutout.bbox_source_2180))
        _check_wcs_disk_space(cutout, staged)
        timeout = selected_provider.DEFAULT_TIMEOUT
        b = cutout.bbox_source_2180
        # PRG covers the source aligned OUTWARD to the sheet grid, including
        # any edge pixel centre. A PRG failure must precede all WCS requests.
        grid = selected_provider.WCS_GRID
        mask_area = align_bbox(b, grid.step, grid)[0] if grid is not None else b
        mask = fetch_land_mask(mask_area, timeout=timeout)
        if not mask.has_land(b, cutout.pixel_size):
            # the sheet mode has no record there either: no version, no WCS
            raise NoCoverageError(
                f"wycinek {cutout.product.upper()}: obszar w calosci poza ladem PL "
                "(maska PRG: granica panstwa bez morza terytorialnego i wod "
                "wewnetrznych) - GUGiK nie ma tu danych; zmien --bbox"
            )
        if sink is not None and (chunks > 1 or cutout.estimated_bytes >= 2**30):
            height, width = cutout.grid_shape
            sink.emit(
                "info",
                CUTOUT_SIZE,
                f"wycinek {width} x {height} px float32 "
                f"(~{cutout.estimated_bytes / 2**20:.0f} MiB), {chunks} zapytan "
                f"WCS GUGiK pobieranych po kolei - {wcs_time_text(chunks)} "
                f"({WCS_REQUEST_SECONDS[0]}-{WCS_REQUEST_SECONDS[1]} s na "
                "zapytanie wg pomiaru)",
            )
        description = (
            f"wycinek {cutout.product.upper()} {cutout.vertical_crs} "
            f"({b.min_x:.0f},{b.min_y:.0f})-({b.max_x:.0f},{b.max_y:.0f})"
        )
        work = staged.parent / f"{staged.stem}.wcs.tif"
        try:
            selected_provider._download_wcs(b, work, "GTiff", timeout, description)
            masked_pixels, zero_pixels = mask.apply(work, PL_NODATA)
            if cutout.pinned is None:
                os.replace(work, staged)
            else:
                from kartograf.transform.raster import warp_to_grid

                warp_to_grid(
                    work,
                    staged,
                    cutout.bbox_target,
                    cutout.pixel_size,
                    cutout.pinned,
                    src_crs="EPSG:2180",
                    nodata=PL_NODATA,
                )
        finally:
            work.unlink(missing_ok=True)

        all_nodata = not has_valid_pixels(staged, PL_NODATA)
        return None

    def write_sidecar(
        path: Path, version: VersionRef, digest: ContentDigest, http: dict | None
    ) -> None:
        assert selected_provider is not None
        write_pl_wcs_cutout_sidecar(
            cutout,
            path,
            selected_provider,
            version=version,
            digest=digest,
            http=http,
            parent_request=parent_request,
            masked_pixels=masked_pixels,
            zero_pixels=zero_pixels,
            all_nodata=all_nodata,
        )

    file = fetch_version(
        slot,
        update,
        signal=signal,
        fetch=fetch,
        version=VersionRef.downloaded(now),
        write_sidecar=write_sidecar,
    )
    return _cutout_result(file, stale=stale)


def download_pl_cutout(
    bbox: BBox,
    *,
    horizontal_crs: str,
    output_dir: str | Path,
    vertical_crs: str,
    product: str,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> PlCutoutResult:
    """One versioned NMT/NMPT PL GeoTIFF in ``horizontal_crs`` from GUGiK WCS.

    ADR-035: the source on the 1 m sheet grid, the server's flight
    composition (not the newest flight per ADR-028), nodata -9999 outside PL
    land (PRG mask; 0.0 on land stays data). The undated standard bbox path
    links to an immutable version. Default and ``update="upgrade"`` use a
    local version without PRG or WCS requests; ``update="force"`` downloads
    again. ``plan`` (from ``check_pl_cutout``) downloads only its missing
    position; a changed position lands in ``stale``. For a geometry request
    pass its envelope as ``bbox`` (e.g. via
    ``get_overall_bbox(path, target_crs="EPSG:2180")``).

    ``output_dir`` selects the base directory; ``horizontal_crs`` is
    "EPSG:2180", "EPSG:5514" or "EPSG:3045"; ``vertical_crs`` is
    "EVRF2007" (current heights) or "KRON86" (legacy heights), and
    ``product`` is "nmt" (terrain) or "nmpt" (surface). The only WCS cutout
    resolution is 1m. ``parent_request`` goes to the version sidecar only
    when given. ``cache``: ``True`` = default metadata cache in the current
    directory, a ``MetadataCache`` = that cache, ``False`` = none.
    ``on_notice`` receives each data notice when it is emitted.

    Returns
    -------
    PlCutoutResult
        ``file`` — standard link and version status; ``masked_pixels`` and
        ``zero_pixels`` — land mask counts; ``all_nodata`` — outside PL land;
        ``notices`` — ``CUTOUT_SIZE`` (before the first WCS request) and
        ``ALL_NODATA``.

    Raises
    ------
    ValidationError
        Bad product, CRS, vertical CRS or update mode, or too little disk
        space on download.
    TransformError
        No safe pinned EPSG:2180 -> ``horizontal_crs`` operation (before any
        network).
    DownloadError
        PRG or WCS failure; no new version is committed.
    """
    validate_update(update)
    cutout = _prepare_pl_cutout(
        bbox,
        horizontal_crs,
        output_dir=output_dir,
        vertical_crs=vertical_crs,
        product=product,
    )
    sink = NoticeSink(on_notice)
    with open_cache(
        cache, force=refreshes_cache(update), on_notice=sink.add
    ) as metadata:
        result = _run_pl_wcs_cutout(
            cutout,
            provider=_wcs_cutout_provider(cutout, metadata),
            update=update,
            plan=plan,
            parent_request=parent_request,
            sink=sink,
        )
    file = result.file
    if result.all_nodata and file is not None and file.status != "local":
        # an area off PL land fails before WCS (PRG mask); nodata on land is
        # an answer of the service
        sink.emit(
            "warning",
            ALL_NODATA,
            "wycinek w calosci nodata - WCS GUGiK nie zwrocil danych dla obszaru "
            "(na ladzie wg maski PRG)",
        )
    return replace(result, notices=sink.notices)
