"""
PL image cutouts from GUGiK WCS in the versioned store (ADR-042 D14, ADR-044).

``download_image_cutout`` / ``check_image_cutout`` (Z2 pair; ``download_data``
with ``product="orto"`` or ``"true-orto"`` and ``cutout=True``): one RGB
GeoTIFF of an area from the Standard or High WCS coverage of ``pl.gugik.orto``
(``coverage``) with the chosen pixel (``resolution``, label K2), in EPSG:2180
only - the image is never resampled locally (no warp; no land mask: pixels
without imagery stay 0,0,0 as the service sends them). A cutout without any
image pixel (every pixel 0,0,0: the true orthophotomap outside its cities,
``high`` outside the 10 cm flights, the sea or an area abroad) is
``NoCoverageError`` and never becomes a version - the service publishes no
cutout extent, so the image is checked after the download. The request is
aligned OUTWARD to multiples of the pixel and fetched by the image provider
(``SCALEFACTOR``, chunks within the channel budget counted in coverage
pixels, stitched without resampling). The true orthophotomap
(``product="true-orto"``, plan E1) has one WCS channel (0.05 m coverage,
``pl.gugik.true_orto``) and takes no ``coverage``.

The standard path ``<output>/orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif``
(coords of the aligned grid in EPSG:2180; true orthophotomap:
``true-orto/pl_1992_<res>``) links to an immutable version in
``versions/bbox/``. The channel has no freshness signal (``none``): a local
version is used without any request and ``update="force"`` downloads again
(the same bytes = ``unchanged``; a repeated request gives the same bytes).

Measured live 2026-10-16 (``tests/fixtures/pl/orto_wcs/README.md``): the
server resamples every request within its own extent, so a result stitched
from chunks is NOT bit-identical to one request of the whole area (it is for
NMT, ADR-034) - every chunk is an exact server answer copied 1:1. Chunks have
even sizes (``GugikWcsMixin.plan_wcs_chunks``): an odd number of 0.25 m
pixels is a fractional number of coverage pixels, which the server answers
with a wrong grid or HTTP 400.

Example::

    from kartograf import BBox, download_image_cutout

    result = download_image_cutout(
        product="orto", bbox=BBox(566000, 243000, 566200, 243200, "EPSG:2180"),
        horizontal_crs="EPSG:2180", root="./data",
        coverage="standard", resolution="0.25m",
    )
    print(result.file.path)
"""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import numpy as np
import rasterio
from rasterio.errors import RasterioError

from kartograf.cache.metadata import MetadataCache
from kartograf.config import resolve_root
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
    validate_update,
)
from kartograf.download.plan import (
    PlanItem,
    Track,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import bbox_slot, token_segment
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.notices import CUTOUT_SIZE, Notice, NoticeSink
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    GugikImageProvider,
    GugikOrtoProvider,
    OrtoCoverage,
    coverage_choices,
    cutout_choice_error,
    cutout_resolution_labels,
    image_source,
    wcs_cutout_channel,
    wcs_cutout_channels,
)
from kartograf.sources.descriptor import AccessChannel, WcsCutoutParams
from kartograf.sources.registry import PL_1992_CRS, get_source
from kartograf.sources.variants import parse_resolution
from kartograf.transport.chunks import GridSpec, align_bbox

# The only CRS of the cutout: the service grid, never resampled locally.
ORTO_CUTOUT_CRS = PL_1992_CRS
# ``--cutout`` with ``--product orto`` outside PL (validation text).
ORTO_CUTOUT_PL_ONLY = (
    "--cutout z --product orto dziala tylko dla PL (wycinek z WCS GUGiK) - "
    "dla obszaru PL uzyj --country pl, ortofotomapa CZ: bez --cutout"
)
_TRACK: Track = "pl_cutout"
# Bytes per pixel of the result: 3 bands uint8 (RGB).
_RGB_BYTES = 3
# Grid tolerance of the checked result, in pixels (server transforms deviate
# by ~1e-9 px from the requested grid).
_GRID_TOL_PX = 1e-6


def orto_cutout_error(
    *, key: str, coverage: object, resolution: object, horizontal_crs: object
) -> ValidationError | None:
    """Return the error of the cutout choice of image source ``key``.

    ``None`` = valid.

    Texts name the CLI flags (``download_data`` passes them 1:1); the coverages
    and pixels are listed from the registry; ``option`` and
    ``allowed`` name the argument and its values.
    """
    error = cutout_choice_error(key, coverage, resolution)
    if error is not None:
        return error
    product = get_source(key).product
    if horizontal_crs is None:
        return ValidationError(
            f"--horizontal-crs wymagane z --cutout --product {product}: tylko "
            f"{ORTO_CUTOUT_CRS} (bez przeprobkowania obrazu)",
            option="horizontal_crs",
            allowed=(ORTO_CUTOUT_CRS,),
        )
    if horizontal_crs != ORTO_CUTOUT_CRS:
        return ValidationError(
            f"--horizontal-crs {horizontal_crs} nie dziala z --product {product}: "
            f"wycinek ortofotomapy tylko {ORTO_CUTOUT_CRS} (bez przeprobkowania "
            "obrazu)",
            option="horizontal_crs",
            allowed=(ORTO_CUTOUT_CRS,),
        )
    return None


def orto_coverage_choices() -> str:
    """Return the ``--coverage`` values of the orthophotomap cutout.

    ``--help`` of the CLI, which imports no providers, Z1.
    """
    return coverage_choices(ORTO_KEY)


def cutout_resolution_choices(products: tuple[str, ...]) -> str:
    """Return the cutout pixels of every cutout channel of the image ``products``.

    Format ``orto standard: 0.1m, ...; true-orto: 0.05m, ...`` in registry order
    (``--resolution`` in ``--help``).
    """
    parts = []
    for product in products:
        source = image_source(product)
        channels = wcs_cutout_channels(source.key) if source is not None else ()
        for channel in channels:
            assert source is not None  # channels of a source
            params = channel.params
            assert isinstance(params, WcsCutoutParams)  # wcs_cutout_channels
            coverage = params.variant if len(channels) > 1 else None
            labels = cutout_resolution_labels(source.key, coverage)
            name = f"{product} {coverage}" if coverage is not None else product
            parts.append(f"{name}: {', '.join(labels)}")
    return "; ".join(parts)


@dataclass(frozen=True)
class ImageCutoutResult:
    """Versioned image cutout (orthophotomap, true orthophotomap) and its data notices.

    ``file`` is ``None`` only when a plan skips the cutout and nothing is
    available locally; otherwise it points to the standard bbox link.
    ``stale``: plan positions changed since the plan. ``notices``:
    ``CUTOUT_SIZE`` (several WCS requests or >= 1 GiB, before the first
    request).
    """

    file: VersionedFile | None
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class _OrtoCutout:
    """A prepared cutout: the source, the choice, the aligned result grid and its slot.

    ``coverage`` ``None``: the one channel of the source.
    """

    key: str
    coverage: str | None
    resolution: str
    channel: AccessChannel
    grid: BBox
    width: int
    height: int
    slot: FileSlot

    @property
    def estimated_bytes(self) -> int:
        """Size of the uncompressed RGB result (bytes)."""
        return self.width * self.height * _RGB_BYTES

    @property
    def variant(self) -> str:
        """Name of the WCS channel in messages (``standard``, ``true``)."""
        params = self.channel.params
        assert isinstance(params, WcsCutoutParams)  # wcs_cutout_channel
        return params.variant


def _prepare(
    bbox: BBox,
    *,
    key: str,
    horizontal_crs: str,
    root: str | Path,
    coverage: str | None,
    resolution: str,
) -> _OrtoCutout:
    """Validate the choice and fix the result grid, without network access.

    Raises ``ValidationError`` for an invalid bbox or choice and
    ``TransformError`` when a bbox in a Czech CRS has no safe pinned
    operation to EPSG:2180.
    """
    # local import: options imports this module
    from kartograf.download.options import validate_request_bbox

    bbox = validate_request_bbox(bbox)
    error = orto_cutout_error(
        key=key,
        coverage=coverage,
        resolution=resolution,
        horizontal_crs=horizontal_crs,
    )
    if error is not None:
        raise error
    step = parse_resolution(resolution)
    assert step is not None  # a label of the channel (orto_cutout_error)
    pixel = float(step)
    aligned, width, height = align_bbox(bbox_to_2180(bbox), pixel, GridSpec(pixel))
    # the exact multiples of the pixel (float steps add ~1e-11 m of noise)
    min_x, min_y, max_x, max_y = (
        float(round(Decimal(repr(v)) / step) * step)
        for v in (aligned.min_x, aligned.min_y, aligned.max_x, aligned.max_y)
    )
    grid = BBox(min_x, min_y, max_x, max_y, aligned.crs)
    # one channel: its segment names the product (true-orto/pl_1992_<res>)
    tokens = (resolution,) if coverage is None else (coverage, resolution)
    segment = token_segment(get_source(key).resolve_subdir(system="1992"), tokens)
    return _OrtoCutout(
        key=key,
        coverage=coverage,
        resolution=resolution,
        channel=wcs_cutout_channel(key, coverage),
        grid=grid,
        width=width,
        height=height,
        slot=bbox_slot(root, segment, grid, ".tif"),
    )


def _cutout_provider(cutout: _OrtoCutout) -> GugikImageProvider:
    """Return the provider of the cutout's WCS channel and pixel.

    The orthophotomap: the RGB composition.
    """
    if cutout.key == ORTO_KEY:
        return GugikOrtoProvider(
            color=GugikOrtoProvider.DEFAULT_COLOR,
            coverage=cast(OrtoCoverage, cutout.coverage),
            resolution=cutout.resolution,
        )
    return GugikImageProvider(
        cutout.key, coverage=cutout.coverage, resolution=cutout.resolution
    )


def _check_disk_space(cutout: _OrtoCutout, staged: Path) -> None:
    """``ValidationError`` when the store lacks room for the chunks and the result."""
    need = 2 * cutout.estimated_bytes
    probe = staged.parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        raise ValidationError(
            f"Za malo miejsca na dysku dla wycinka: potrzeba co najmniej "
            f"~{need / 2**30:.1f} GiB (siatka {cutout.width} x {cutout.height} px "
            f"RGB i kawalki WCS), wolne ~{free / 2**30:.1f} GiB w {probe}"
        )


def _check_result(path: Path, cutout: _OrtoCutout) -> None:
    """``DownloadError`` unless ``path`` is an RGB uint8 raster on the cutout grid.

    The service answers a request it cannot honour exactly with another grid
    (``standard_0.25m_odd_3x3.tif`` in the fixtures); such a file never
    becomes a version.
    """
    grid = cutout.grid
    step = (grid.max_x - grid.min_x) / cutout.width
    tol = _GRID_TOL_PX * step
    try:
        with rasterio.open(path) as src:
            t = src.transform
            size = (src.width, src.height)
            bands = (src.count, set(src.dtypes))
            epsg = src.crs.to_epsg() if src.crs is not None else None
    except RasterioError as e:
        raise DownloadError(
            f"WCS ortofotomapy: nieczytelny GeoTIFF wycinka: {e}"
        ) from e
    problems = []
    if size != (cutout.width, cutout.height):
        problems.append(
            f"{size[0]} x {size[1]} px zamiast {cutout.width} x {cutout.height}"
        )
    if (
        abs(t.a - step) > tol
        or abs(-t.e - step) > tol
        or abs(t.b) > tol
        or abs(t.d) > tol
    ):
        problems.append(f"piksel {t.a:g} x {-t.e:g} m zamiast {step:g} m")
    if abs(t.c - grid.min_x) > tol or abs(t.f - grid.max_y) > tol:
        problems.append(
            f"naroznik NW {t.c:.3f}/{t.f:.3f} zamiast {grid.min_x:.3f}/{grid.max_y:.3f}"
        )
    if bands != (3, {"uint8"}):
        problems.append(
            f"{bands[0]} pasm {'/'.join(sorted(bands[1]))} zamiast 3 pasm uint8 (RGB)"
        )
    if epsg != 2180:
        problems.append(f"uklad EPSG:{epsg} zamiast {ORTO_CUTOUT_CRS}")
    if problems:
        raise DownloadError(
            "WCS ortofotomapy zwrocil inna siatke niz zapytanie: " + "; ".join(problems)
        )


def _has_image(path: Path) -> bool:
    """Whether any pixel of the raster is not 0,0,0 (early exit)."""
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            if np.any(src.read(window=window)):
                return True
    return False


def _no_image_error(cutout: _OrtoCutout) -> NoCoverageError:
    """Build the ``NoCoverageError`` of a cutout whose every pixel is 0,0,0.

    The error carries the reason and the remedy of its WCS channel.
    """
    if cutout.key != ORTO_KEY:
        what = (
            "wycinek true orto: WCS GUGiK nie ma w tym obszarze prawdziwej "
            "ortofotomapy - obejmuje tylko wybrane miasta, np. Gdansk"
        )
        remedy = "zmien --bbox"
    elif cutout.coverage == "high":
        what = (
            "wycinek ortofotomapy high: WCS GUGiK nie ma w tym obszarze "
            "ortofotomapy o pikselu 10 cm i mniejszym"
        )
        remedy = "zmien --bbox albo uzyj --coverage standard"
    else:
        what = (
            f"wycinek ortofotomapy {cutout.coverage}: WCS GUGiK nie ma w tym "
            "obszarze ortofotomapy (np. morze albo obszar za granica)"
        )
        remedy = "zmien --bbox"
    return NoCoverageError(
        f"{what}, a obraz obszaru jest w calosci 0,0,0; wersja nie powstala, {remedy}"
    )


def _write_sidecar(
    cutout: _OrtoCutout,
    path: Path,
    provider: GugikImageProvider,
    *,
    version: VersionRef,
    digest: ContentDigest,
    http: dict[str, Any] | None,
    parent_request: dict[str, Any] | None,
) -> None:
    """Write the mandatory, exclusive sidecar of a cutout version.

    ``request`` = the aligned grid and the choice (``coverage`` only where
    the source has several channels); ``extra.source`` = the WCS request
    (endpoint, coverage id, format, ``scalefactor`` when the pixel is not the
    coverage step) and the server composition of flights.
    """
    from kartograf.sources.sidecar import emit_sidecar

    endpoint, coverage_id = provider._wcs_target()
    source: dict[str, Any] = {
        "service": "WCS",
        "endpoint": endpoint,
        "coverage": coverage_id,
        "format": provider.WCS_FORMATS["GTiff"],
    }
    scale = provider._wcs_scale()
    if scale is not None:
        source["scalefactor"] = float(f"{scale:g}")  # the value of the URL
    source["composition"] = "server"
    extra: dict[str, Any] = {}
    if parent_request:
        extra["parent_request"] = parent_request
    extra["source"] = source
    if http is not None:
        extra["http"] = http
    request: dict[str, Any] = {
        "bbox": bbox_coords(cutout.grid),
        "bbox_crs": ORTO_CUTOUT_CRS,
    }
    if cutout.coverage is not None:
        request["coverage"] = cutout.coverage
    request["resolution"] = cutout.resolution
    emit_sidecar(
        cutout.key,
        path,
        request=request,
        horizontal_crs=ORTO_CUTOUT_CRS,
        capability="bbox_raster",
        extra=extra,
        digest=(digest.sha256, digest.size_bytes),
        version=version.to_extra(),
        exclusive=True,
    )


def _run(
    cutout: _OrtoCutout,
    *,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    parent_request: dict[str, Any] | None,
    sink: NoticeSink,
    now: datetime | None = None,
) -> ImageCutoutResult:
    """Use the local cutout or download a new immutable version.

    A plan executes only its matching missing position (changed ones land in
    ``stale``). A download checks disk space, announces a cutout of several
    requests (or >= 1 GiB) with ``CUTOUT_SIZE`` before the first one, fetches
    into the private staging directory and checks the grid of the result; a
    cutout without any image pixel raises ``NoCoverageError`` before the
    version is stored (``_no_image_error``).
    """
    slot = cutout.slot
    signal = cutout.channel.update_signal
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(slot.root))
        current = inspect_version(slot, track=_TRACK, unit=slot.std.stem, signal=signal)
        todo, excluded = select_planned(plan, [current], _TRACK)
        stale = tuple(excluded)
        if not todo:
            local = local_version(slot)
            if local is None:
                return ImageCutoutResult(None, stale=stale)
            link_version(slot.std, local, refresh=False)
            return ImageCutoutResult(
                VersionedFile(slot.std, "local", local.label, local.sha256, local.path),
                stale=stale,
            )

    provider: GugikImageProvider | None = None

    def fetch(staged: Path) -> None:
        nonlocal provider
        provider = _cutout_provider(cutout)
        chunks = len(provider.plan_wcs_chunks(cutout.grid))
        if chunks > 1 or cutout.estimated_bytes >= 2**30:
            sink.emit(
                "info",
                CUTOUT_SIZE,
                f"wycinek {cutout.width} x {cutout.height} px RGB uint8 "
                f"(~{cutout.estimated_bytes / 2**20:.0f} MiB), {chunks} zapytan "
                f"WCS GUGiK ({cutout.variant} {cutout.resolution}) pobieranych "
                "po kolei",
            )
        _check_disk_space(cutout, staged)
        grid = cutout.grid
        provider._download_wcs(
            grid,
            staged,
            "GTiff",
            provider.WCS_CUTOUT_READ_TIMEOUT,
            f"wycinek ortofotomapy {cutout.variant} {cutout.resolution} "
            f"({grid.min_x:.0f},{grid.min_y:.0f})-({grid.max_x:.0f},{grid.max_y:.0f})",
        )
        _check_result(staged, cutout)
        if not _has_image(staged):
            raise _no_image_error(cutout)

    def write_sidecar(
        path: Path,
        version: VersionRef,
        digest: ContentDigest,
        http: dict[str, Any] | None,
    ) -> None:
        assert provider is not None  # fetch ran first
        _write_sidecar(
            cutout,
            path,
            provider,
            version=version,
            digest=digest,
            http=http,
            parent_request=parent_request,
        )

    file = fetch_version(
        slot,
        update,
        signal=signal,
        fetch=fetch,
        version=VersionRef.downloaded(now),
        write_sidecar=write_sidecar,
    )
    return ImageCutoutResult(file, stale=stale)


def _cutout_key(product: str) -> str:
    """Descriptor key of the WCS cutout of an image ``product``."""
    source = image_source(product)
    if source is None or not wcs_cutout_channels(source.key):
        raise ValidationError(
            f"--product {product!r}: brak wycinka WCS obrazu - wycinek maja "
            "--product orto i true-orto"
        )
    return source.key


def check_image_cutout(
    *,
    product: str,
    bbox: BBox,
    horizontal_crs: str,
    root: str | Path | None = None,
    resolution: str,
    coverage: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Build the update plan of ``download_image_cutout``.

    It takes the same arguments as the download and downloads nothing.

    The WCS channel has no remote version signal, so the plan (track
    ``pl_cutout``) reads only the local store: no request is made. ``cache``
    and ``on_notice`` are accepted for symmetry with the download.

    Raises ``ValidationError`` for an invalid choice and ``TransformError``
    when a Czech CRS has no safe pinned operation, exactly as the download.
    """
    root = resolve_root(root)
    del cache, on_notice  # same signature as the download (Z2); unused here
    cutout = _prepare(
        bbox,
        key=_cutout_key(product),
        horizontal_crs=horizontal_crs,
        root=root,
        coverage=coverage,
        resolution=resolution,
    )
    slot = cutout.slot
    item = inspect_version(
        slot, track=_TRACK, unit=slot.std.stem, signal=cutout.channel.update_signal
    )
    return new_plan(store_id(slot.root), (item,))


def download_image_cutout(
    *,
    product: str,
    bbox: BBox,
    horizontal_crs: str,
    root: str | Path | None = None,
    resolution: str,
    coverage: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict[str, Any] | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> ImageCutoutResult:
    """Download a versioned RGB GeoTIFF of an area from the WCS of a GUGiK image.

    ``product``: ``"orto"`` - the orthophotomap, ``coverage`` ``"standard"``
    (newest orthophotomaps) or ``"high"`` (pixel 10 cm and finer; 0,0,0
    elsewhere), ``resolution`` a label K2 of the channel (``"0.1m"``,
    ``"0.25m"``, ``"0.5m"``, ``"1m"``); ``"true-orto"`` - the true
    orthophotomap, one channel (0.05 m coverage of selected cities:
    ``coverage`` left out; pixels ``"0.05m"``, ``"0.1m"``, ``"0.25m"``,
    ``"0.5m"``, ``"1m"``). ``horizontal_crs``:
    ``"EPSG:2180"`` only (the image is not resampled). ``bbox`` may be in any
    supported CRS (for a geometry pass its envelope); the result grid is
    ``bbox`` in EPSG:2180 aligned OUTWARD to multiples of the pixel. The
    server composes the flights itself (no year choice). Default and
    ``update="upgrade"`` use a local version without a request;
    ``update="force"`` downloads again. ``plan`` (from
    ``check_image_cutout``) downloads only its missing position; a changed
    position lands in ``stale``. ``parent_request`` goes to the sidecar only
    when given. ``cache`` is accepted for symmetry with the other tracks (the
    cutout reads no metadata); ``on_notice`` receives each data notice when
    it is emitted.

    Returns
    -------
    ImageCutoutResult
        ``file`` - standard link and version status; ``notices`` -
        ``CUTOUT_SIZE`` (before the first WCS request).

    Raises
    ------
    ValidationError
        A product without a WCS cutout, an invalid bbox, choice or update
        mode (before any request), or too little disk space on download.
    TransformError
        No safe pinned operation from a Czech CRS of ``bbox`` to EPSG:2180.
    NoCoverageError
        The area has no image pixel (every pixel 0,0,0: the true
        orthophotomap outside the cities of the service, ``high`` outside
        the 10 cm flights, the sea or an area abroad); no version is stored.
    DownloadError
        WCS failure, an error document or a raster off the requested grid;
        no version is committed.
    """
    root = resolve_root(root)
    validate_update(update, check="check_image_cutout")
    cutout = _prepare(
        bbox,
        key=_cutout_key(product),
        horizontal_crs=horizontal_crs,
        root=root,
        coverage=coverage,
        resolution=resolution,
    )
    del cache  # the WCS cutout reads no metadata (symmetry, Z2)
    sink = NoticeSink(on_notice)
    result = _run(
        cutout, update=update, plan=plan, parent_request=parent_request, sink=sink
    )
    return replace(result, notices=sink.notices)
