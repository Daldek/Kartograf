"""CuzkRasterProvider - CUZK rasters: NMT and NMPT.

NMT: DMR 5G 2 m, DMR 4G 5 m; NMPT: DMP 1G 2 m, DMP OK 0.5 m.

The route of a request is a row of the variant registry (ADR-041 supplement,
plan B decision 2): an SM5 sheet = the S-JTSK file (openzu, EPSG:5514, Bpv),
a TM33 tile in EVRF2007 of a model with files = the ETRS89 file (EPSG:3045,
EVRF2007 natively), every other TM33 tile = the ImageServer warped onto the
tile grid (ADR-024), a bbox = the ImageServer. Heights outside the native
system of the channel go through the pinned Bpv->EVRF2007 operation.

Nativeness rule: the exportImage result is a server derivative (GeoTIFF); the
openzu files are CUZK bytes 1:1 — only the CRS tag is modified, in a GeoTIFF
without a CRS (metadata repair, the CRS of the channel). Vertical
transformation only when the requested heights are not native to the channel.

Endpoints come ONLY from descriptors (``channel_for``) — the provider knows no
URL. Sidecars are written by the download tracks (``download/cz_sheets.py``,
``download/cz_cutout.py``) from ``CzRasterRoute``.
"""

import dataclasses
import logging
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.transform import xy as _pixel_xy
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, transform_bbox
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.messages import message, reason
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, wkid
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.sources.descriptor import AccessChannel, TransportKind
from kartograf.sources.registry import (
    CZ_SYSTEM_CRS,
    channel_for,
    resolve_vertical_crs,
)
from kartograf.sources.variants import (
    CZ_MODELS,
    cz_sheet_system,
    cz_variant_error,
    find_cz_variant,
    variants,
)
from kartograf.transform.crs import (
    CONTENT_POLICY,
    REMEDIES,
    WARP_MARGIN_PX,
    PinnedTransform,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)
from kartograf.transform.raster import warp_to_grid
from kartograf.transport.http import head_signal

logger = logging.getLogger(__name__)

CUZK_NODATA = -9999.0

# The CRS in which CUZK STORES the raster data. The server receives requests
# only in it: imageSR=2180 loses the datum transformation (135 m error,
# ADR-024). The former 1.25 m for 3045 came from the difference between the
# Czech EPSG:1622 and the Slovak EPSG:4829 operations in the local reference,
# not from a server error (errata).
NATIVE_CRS = "EPSG:5514"

_DEFAULT_TIMEOUT = 60

# Control point for HORIZONTAL operations whose source is the native CRS
# — roughly the centre of Czechia (15.5E / 49.8N) in Krovak. A grid that does
# not cover it (e.g. sk_gku, Slovakia) returns inf there and is rejected
# before it can spoil a download (0.7.0 audit, A1-2).
CZ_PROBE_NATIVE: tuple[float, float] = (-670165.0, -1084718.0)

# The vertical Bpv->EVRF2007 operation has 0.1 m accuracy (reconnaissance
# Task 1, step 7). Without a probe: the pair is purely vertical, so
# transformer.transform(x, y) makes no sense here as a coverage test.
_VERTICAL_POLICY = TransformPolicy(min_accuracy_m=0.2)
# Auxiliary horizontal conversions do NOT touch the data values, so the limit
# is looser than for the operation reprojecting content:
#  - lon/lat for the vertical operation: the offset changes by 0.014 m per
#    degree of latitude, so a 2 m error is ~3e-7 m of height;
#  - envelope of the native request: it only has to COVER the target area, and
#    a possible divergence from the pinned operation (<= 2 m) fits in the
#    WARP_MARGIN_PX margin (4 px = 8 m at 2 m) — when reducing this margin,
#    tighten this policy or compute the envelope with the same operation as
#    the warp.
# CDN grids are not needed here (they cost ~2 s per CRS pair), hence
# allow_network_grids=False.
_LONLAT_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
_ENVELOPE_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
# Operation reprojecting the raster CONTENT: CONTENT_POLICY, envelope margin:
# WARP_MARGIN_PX — both from transform/crs.py, shared with the PL cutout (D9).

# The transformation runs in strips of a fixed number of PIXELS (not rows): for a
# wide raster a row strip would generate huge index and lon/lat arrays.
_CHUNK_PIXELS = 4_000_000


@dataclasses.dataclass(frozen=True)
class CzRasterRoute:
    """Describe how one CZ raster request is served: a row of the route table.

    A row of the route table (plan B, decision 2) with the operations it performs.

    ``channel``: the CUZK file of the sheet system (``DIRECT_FILES``) or the
    ImageServer (``ARCGIS_IMAGE``); ``horizontal_crs``: the CRS of the result
    file; ``horizontal``: the pinned operation of the local warp (``None``:
    the result is in the CRS of the channel); ``vertical``: the pinned
    Bpv->EVRF2007 operation when the requested heights are not native to the
    channel. The sidecar of the result describes exactly these operations.
    """

    channel: AccessChannel
    horizontal_crs: str
    horizontal: PinnedTransform | None
    vertical: PinnedTransform | None

    @property
    def files(self) -> bool:
        """The result is the CUZK file (signal ``http``), not an export."""
        return self.channel.transport == TransportKind.DIRECT_FILES

    @property
    def capability(self) -> str:
        """Capability of the channel in the sidecar (``build_metadata``)."""
        return "sheet_files" if self.files else "bbox_raster"


class CuzkRasterProvider(BaseProvider):
    """Provide a CZ raster of one product and resolution.

    ``nmt`` 2m (DMR 5G) / 5m (DMR 4G), ``nmpt`` 0.5m (DMP OK) / 2m (DMP 1G);
    Bpv or EVRF2007 heights.
    """

    def __init__(
        self,
        product: str,
        resolution: str,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
        horizontal_crs: str | None = None,
        *,
        vertical_crs: str,
    ):
        """Choose the CZ product, resolution and vertical reference explicitly.

        ``product``/``resolution`` select the CUZK model from the variant
        registry (``nmt``: ``2m`` DMR 5G, ``5m`` DMR 4G; ``nmpt``: ``0.5m``
        DMP OK, ``2m`` DMP 1G). ``vertical_crs`` is ``"Bpv"`` or
        ``"EVRF2007"`` (native for the ETRS89 files, otherwise the pinned
        Bpv->EVRF2007 operation); KRON86 has no available transformation.
        ``horizontal_crs`` is the CRS of a cutout (``None`` keeps the native
        EPSG:5514); ``session=None`` creates a session and ``cache=None``
        disables the sheet index cache.

        Raises
        ------
        TransformUnavailableError
            KRON86, or no safe operation to ``horizontal_crs``.
        ValidationError
            A product, resolution or height system outside the registry.
        """
        if vertical_crs == "KRON86":
            raise TransformUnavailableError(
                message("providers.no_kron86_transform"),
                remedy=REMEDIES["EPSG:9650"],
            )
        error = cz_variant_error(
            product=product, resolution=resolution, vertical_crs=vertical_crs
        )
        if error is not None:
            raise error
        variant = variants(product=product, country="CZ", resolution=resolution)[0]
        assert variant.resolution_m is not None  # a label of the registry
        self.descriptor_key = variant.source
        self._product = product
        self._model = CZ_MODELS[variant.model or ""][0]
        self._resolution = resolution
        self._pixel_size = float(variant.resolution_m)
        self._target_crs = horizontal_crs
        self._vertical_crs = vertical_crs
        self._session = session or requests.Session()
        self._client = CuzkClient(session=self._session, timeout=_DEFAULT_TIMEOUT)
        self._client_timeout = _DEFAULT_TIMEOUT
        self._sheet_index = SheetIndex(session=self._session, cache=cache)
        self._transforms: dict[tuple[str, str], PinnedTransform] = {}
        self._image = channel_for(self.descriptor_key, TransportKind.ARCGIS_IMAGE)
        # Fail-fast: when the user requested a CRS other than native, the lack
        # of a safe operation must abort before the transfer.
        if horizontal_crs is not None:
            self.horizontal_transform(horizontal_crs)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return f"CUZK {self._model} ({self._resolution})"

    @property
    def base_url(self) -> str:
        """Return the endpoint of the ImageServer."""
        return self._image.endpoint

    @property
    def default_extension(self) -> str:
        """Return the default extension of the downloaded files."""
        return ".tif"

    @property
    def product(self) -> str:
        """``nmt`` or ``nmpt``."""
        return self._product

    @property
    def resolution(self) -> str:
        """Return the resolution of the product."""
        return self._resolution

    @property
    def vertical_crs(self) -> str:
        """CLI name of the result's vertical CRS ("Bpv" or "EVRF2007")."""
        return self._vertical_crs

    @property
    def sheet_index(self) -> SheetIndex:
        """Shared sheet index (SM5 validation, PODIL for the sidecar)."""
        return self._sheet_index

    def horizontal_transform(self, target_crs: str) -> PinnedTransform | None:
        """Return the pinned ``EPSG:5514 -> target_crs`` operation of the raster.

        It reprojects the raster CONTENT; ``None`` when the result stays in the
        native CRS.

        The same instance as used during download (``_transforms`` cache), so
        the description and accuracy in the sidecar describe the operation
        actually performed.
        """
        if wkid(target_crs) == wkid(NATIVE_CRS):
            return None
        return self._pinned(
            NATIVE_CRS, target_crs, CONTENT_POLICY, probe=CZ_PROBE_NATIVE
        )

    def route(self, sheet: str | None = None) -> CzRasterRoute:
        """Return the route of a sheet code (``None``: a bbox cutout).

        Decision 2 of plan B: the channel, the CRS of the result and its pinned
        operations.

        A sheet is validated (CZ system, the variant of the product and
        resolution, the TM33 grid) and every operation of the route is built
        here - a missing safe operation raises before any request (the user
        does not pay for a transfer, nor gets a Bpv file under the name
        ordered as EVRF2007).

        Raises
        ------
        ValidationError
            A code outside CZ or a sheet without a variant (SM5 for 2m).
        ParseError
            A malformed TM33 code.
        TransformError
            No safe pinned operation of the route.
        """
        if sheet is None:
            target = self._target_crs or NATIVE_CRS
            return CzRasterRoute(
                self._image,
                target,
                self.horizontal_transform(target),
                self._vertical_for(self._image),
            )
        sheet = sheet.strip()
        system = cz_sheet_system(sheet)
        if system == "tm33":
            # full validation of the grid (even kilometres), not only the regex
            ParserTM33(sheet)
        variant = find_cz_variant(
            product=self._product,
            resolution=self._resolution,
            vertical_crs=self._vertical_crs,
            system=system,
        )
        if variant.channel == TransportKind.DIRECT_FILES:
            channel = channel_for(
                variant.source, TransportKind.DIRECT_FILES, CZ_SYSTEM_CRS[system]
            )
            return CzRasterRoute(
                channel, channel.horizontal_crs, None, self._vertical_for(channel)
            )
        tile_crs = CZ_SYSTEM_CRS["tm33"]
        return CzRasterRoute(
            self._image,
            tile_crs,
            self.horizontal_transform(tile_crs),
            self._vertical_for(self._image),
        )

    def _vertical_for(self, channel: AccessChannel) -> PinnedTransform | None:
        """Return the pinned operation from the native heights to the requested ones.

        For ``channel``; ``None`` when the channel serves them natively.
        """
        options = channel.vertical_crs_options
        requested = resolve_vertical_crs(self._vertical_crs, options)
        if requested in options:
            return None
        return self._pinned(options[0], requested, _VERTICAL_POLICY)

    def download(
        self,
        sheet: str,
        output_path: Path,
        timeout: int = _DEFAULT_TIMEOUT,
        *,
        on_download: Callable[[], None] | None = None,
        on_response: Callable[[requests.Response], None] | None = None,
    ) -> Path:
        """Download an SM5 sheet or a TM33 tile along its route (:meth:`route`).

        A CUZK file (SM5 in EPSG:5514, TM33 ETRS89 in EPSG:3045) arrives 1:1
        with the CRS of its channel written into the GeoTIFF; a TM33 tile
        without a file of the variant is an ``exportImage`` request in the
        native EPSG:5514 warped locally onto the tile grid (ADR-024).
        `horizontal_crs` applies only to bbox mode — the sheet code defines
        the extent in a specific CRS. ``on_response`` receives the HTTP
        response of a file (its signal); an export has none.

        ``on_download`` is called exactly once, after every validation
        (route, sheet-index lookup of SM5, TM33 grid parse) and right before
        the data transfer starts; it is never called when the request is
        rejected (same contract as ``DownloadManager.download_sheet(
        on_download=)`` in the PL flow).
        """
        output_path = Path(output_path)
        # like the system registry: whitespace is not part of the sheet code
        # (openzu URL, SM5 index and ParserTM33 get the same stripped code)
        sheet = sheet.strip()
        route = self.route(sheet)
        if route.files:
            self._download_file(
                sheet, route.channel, output_path, timeout, on_download, on_response
            )
        else:
            bbox = ParserTM33(sheet).get_bbox()
            self._export_raster(bbox, output_path, timeout, on_download)
        if route.vertical is not None:
            self._apply_vertical_shift(output_path, route.vertical)
        return output_path

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = _DEFAULT_TIMEOUT,
        *,
        on_download: Callable[[], None] | None = None,
    ) -> Path:
        """Produce a single cutout for any bbox.

        Another CRS than EPSG:5514 => local warp.

        ``on_download``: called once right before the first ``exportImage``
        request, after format and CRS validation (see :meth:`download`).
        """
        if format != "GTiff":
            raise ValidationError(message("providers.bbox_gtiff_only", format=format))
        output_path = Path(output_path)
        route = self.route()
        if wkid(bbox.crs) != wkid(route.horizontal_crs):
            bbox = self._bbox_to_crs(bbox, route.horizontal_crs)
        self._export_raster(bbox, output_path, timeout, on_download)
        if route.vertical is not None:
            self._apply_vertical_shift(output_path, route.vertical)
        return output_path

    def _export_raster(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int,
        on_download: Callable[[], None] | None = None,
    ) -> None:
        """Raster covering ``bbox`` in the CRS ``bbox.crs``.

        The server receives the request ONLY in the native CRS
        (``NATIVE_CRS``); when the target is different, the content is
        reprojected locally with a pinned operation with the Czech datum step
        EPSG:1622 (1.0 m). ``exportImage&imageSR=2180`` loses the S-JTSK->ETRS89
        datum transformation (content shifted by 135 m; ADR-024). The former
        1.25 m for 3045 is the EPSG:1622/4829 difference in the local
        reference, not a server error (ADR-024 errata). A local warp makes it
        possible to enforce and record the operation independently of the
        server.

        Tiling (``exportImage`` limits) and mosaicking happen on the native
        CRS side, i.e. BEFORE the warp — so the tile seam cannot be fixed in
        by interpolation.

        The warp is the shared ``transform/raster.warp_to_grid`` (the same as in
        the PL path): written through a temporary file and ``os.replace``, so
        a failed rebuild (``--force``) leaves the previous result file
        untouched.
        """
        client = self._client_for(timeout)
        # None == the target is the native CRS: the server serves the data directly
        pinned = self.horizontal_transform(bbox.crs)
        if pinned is None:
            if on_download is not None:
                on_download()
            client.export_image(
                self._image.endpoint,
                bbox,
                pixel_size=self._pixel_size,
                image_sr=NATIVE_CRS,
                no_data=CUZK_NODATA,
                output_path=output_path,
            )
            return

        native_bbox = self._native_request_bbox(bbox)
        native_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.native.tif"
        )
        if on_download is not None:
            on_download()
        try:
            client.export_image(
                self._image.endpoint,
                native_bbox,
                pixel_size=self._pixel_size,
                image_sr=NATIVE_CRS,
                no_data=CUZK_NODATA,
                output_path=native_path,
            )
            # Warp shared by the PL and CZ paths (D8): written through a temp file and
            # os.replace — a failure does NOT delete the previous result (N7).
            warp_to_grid(
                native_path,
                output_path,
                bbox,
                self._pixel_size,
                pinned,
                src_crs=NATIVE_CRS,
                nodata=CUZK_NODATA,
            )
        finally:
            native_path.unlink(missing_ok=True)

    def _native_request_bbox(self, bbox: BBox) -> BBox:
        """Native request envelope: the target converted to 5514 plus a margin."""
        native = self._bbox_to_crs(bbox, NATIVE_CRS)
        margin = WARP_MARGIN_PX * self._pixel_size
        return BBox(
            native.min_x - margin,
            native.min_y - margin,
            native.max_x + margin,
            native.max_y + margin,
            NATIVE_CRS,
        )

    def file_url(self, sheet: str) -> str:
        """Openzu URL of the CUZK file of a sheet (its route is a file).

        Raises
        ------
        ValidationError
            The route of the sheet is an ImageServer export (no file of the
            variant: TM33 in Bpv, DMR 5G, DMP 1G) or no route at all.
        """
        sheet = sheet.strip()
        route = self.route(sheet)
        if not route.files:
            raise ValidationError(
                message(
                    "providers.no_cuzk_file",
                    sheet=sheet,
                    model=self._model,
                    vertical_crs=self._vertical_crs,
                )
            )
        return route.channel.endpoint.format(sheet=sheet)

    def file_signal(
        self, sheet: str, timeout: int = _DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """Return the current HTTP signal of the CUZK file of a sheet (``HEAD``).

        The file is not downloaded.
        """
        return head_signal(self._session, self.file_url(sheet), timeout=timeout)

    def _download_file(
        self,
        sheet: str,
        channel: AccessChannel,
        output_path: Path,
        timeout: int,
        on_download: Callable[[], None] | None = None,
        on_response: Callable[[requests.Response], None] | None = None,
    ) -> None:
        """Fetch a CUZK sheet file from openzu (ZIP: ``.tif`` + ``.tfw``).

        The CRS of its channel is written into the GeoTIFF (metadata repair).
        """
        url = channel.endpoint.format(sheet=sheet)
        if channel.horizontal_crs == CZ_SYSTEM_CRS["sm5"]:
            self._sheet_index.sm5_sheet(sheet)  # validation before download
        if on_download is not None:
            on_download()
        try:
            self._client_for(timeout).fetch_file(
                url, output_path, unzip_single=".tif", on_response=on_response
            )
        except DownloadError as e:
            # A missing openzu file (404) is a sheet the index knows but CUZK does
            # not publish for the model (spec section 7): hint to verify the sheet
            # code.
            raise DownloadError(
                message("providers.openzu_file_unavailable", error=reason(e)),
                sheet=sheet,
                status_code=e.status_code,
            ) from e
        _assign_crs(output_path, channel.horizontal_crs)

    def _client_for(self, timeout: int) -> CuzkClient:
        """Client for the given timeout (the HTTP session is always shared)."""
        if timeout == self._client_timeout:
            return self._client
        return CuzkClient(session=self._session, timeout=timeout)

    def _pinned(
        self,
        src_crs: str,
        dst_crs: str,
        policy: TransformPolicy,
        *,
        probe: tuple[float, float] | None = None,
    ) -> PinnedTransform:
        """Pinned transformation (one per CRS pair over the provider's lifetime).

        `probe` (in the SOURCE CRS) adds a control point to the policy:
        a candidate that returns inf/NaN there is dropped — this is how a
        foreign country's grid is rejected, formally more accurate but not
        covering our data. The cache key remains the CRS pair alone: probe
        only REJECTS candidates (does not change the ranking), so the first
        query for a pair fixes the operation for the provider's whole
        lifetime.
        """
        key = (src_crs, dst_crs)
        if key not in self._transforms:
            if probe is not None:
                policy = dataclasses.replace(policy, probe_point=probe)
            self._transforms[key] = build_pinned_transform(src_crs, dst_crs, policy)
        return self._transforms[key]

    def _bbox_to_crs(self, bbox: BBox, target_crs: str) -> BBox:
        """Bbox envelope in the target CRS (transform cached by the provider)."""
        return bbox_to_crs(
            bbox,
            target_crs,
            self._pinned(
                bbox.crs,
                target_crs,
                _ENVELOPE_POLICY,
                probe=_center_of(bbox),
            ),
        )

    def _apply_vertical_shift(self, path: Path, pinned: PinnedTransform) -> None:
        """Convert raster values with the pinned 8357->5621 operation (per pixel).

        The vertical operation requires horizontal coordinates in the order
        (lon, lat, h) — always_xy=True, confirmed in reconnaissance (Task 1
        step 7a; swapping the arguments gives a silent ~0.44 m error). Nodata
        pixels (and any NaN/inf) are NOT transformed — otherwise the value
        -9999 would be shifted by the offset and stop being recognized.

        The conversion runs in strips, so it works on a temporary COPY and
        replaces the file (`os.replace`) only after full success — otherwise a
        failure at strip k would leave under the target name a raster with
        mixed vertical CRSs (strips 0..k-1 in EVRF2007, the rest in Bpv), and
        `skip_existing` in DownloadManager would make such corruption
        permanent. On error both the copy and the source file (with the
        accompanying `.tfw`) disappear.
        """
        temp_path = path.with_name(
            f"{path.name}.{os.getpid()}_{threading.get_ident()}.vshift.tif"
        )
        try:
            shutil.copy2(path, temp_path)
            self._shift_in_place(temp_path, pinned, path.name)
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            path.with_suffix(".tfw").unlink(missing_ok=True)
            raise

    def _shift_in_place(self, path: Path, pinned: PinnedTransform, label: str) -> None:
        """Convert heights in strips in the given file (see _apply_vertical_shift).

        `label` is the name of the TARGET file — messages must not point to
        the name of a temporary copy the user will never see.
        """
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                raise ValidationError(message("providers.raster_no_crs", label=label))
            if ds.transform.is_identity or not ds.transform.is_rectilinear:
                raise ValidationError(
                    message("providers.raster_no_geotransform", label=label)
                )
            bounds = ds.bounds
            horizontal = self._pinned(
                str(ds.crs),
                "EPSG:4326",
                _LONLAT_POLICY,
                probe=(
                    (bounds.left + bounds.right) / 2,
                    (bounds.bottom + bounds.top) / 2,
                ),
            )
            nodata = ds.nodata if ds.nodata is not None else CUZK_NODATA
            logger.debug(
                f"Vertical transformation {label}: {pinned.description} "
                f"(accuracy {pinned.accuracy_m} m), nodata {nodata}"
            )
            chunk_rows = max(1, _CHUNK_PIXELS // ds.width)
            for row_start in range(0, ds.height, chunk_rows):
                rows = min(chunk_rows, ds.height - row_start)
                window = Window(0, row_start, ds.width, rows)
                data = ds.read(1, window=window)
                mask = np.isfinite(data) & (data != nodata)
                if not mask.any():
                    continue
                row_idx, col_idx = np.nonzero(mask)
                xs, ys = _pixel_xy(
                    ds.window_transform(window), row_idx, col_idx, offset="center"
                )
                lon, lat = horizontal.transform(
                    np.asarray(xs, dtype="float64"),
                    np.asarray(ys, dtype="float64"),
                )
                _, _, shifted = pinned.transform(lon, lat, data[mask].astype("float64"))
                data[mask] = np.asarray(shifted, dtype=data.dtype)
                ds.write(data, 1, window=window)


def bbox_to_crs(
    bbox: BBox, target_crs: str, pinned: PinnedTransform | None = None
) -> BBox:
    """Envelope of a bbox in the target CRS through a PINNED operation (ADR-024).

    The only entry for requests leaving the Czech CRS (and for normalizing
    exportImage requests): picks the envelope operation (``_ENVELOPE_POLICY``
    with a control point in the middle of the bbox) when the caller does not
    supply one. Envelopes from densified edges are computed by
    ``core.bbox.transform_bbox`` (21 samples per edge) — the image of a
    rectangle in another CRS is a quadrilateral with curved sides.

    A module-level function (not just a method), because the CLI layer
    normalizes the bbox BEFORE building the file name — the name must carry
    the coordinates of the cutout actually requested. A repeated
    normalization in `download_bbox` is then a guarded no-op.
    """
    if pinned is None:
        pinned = build_pinned_transform(
            bbox.crs,
            target_crs,
            dataclasses.replace(_ENVELOPE_POLICY, probe_point=_center_of(bbox)),
        )
    return transform_bbox(bbox, target_crs, transformer=pinned)


def _center_of(bbox: BBox) -> tuple[float, float]:
    """Centre of the bbox — control point of the envelope operation (source CRS)."""
    return ((bbox.min_x + bbox.max_x) / 2, (bbox.min_y + bbox.max_y) / 2)


def _assign_crs(path: Path, crs: str) -> None:
    """Repair the metadata of a CUZK TIFF file.

    Write the CRS of its channel
    (georeferencing is in .tfw; SM5 EPSG:5514, ETRS89 tiles EPSG:3045).

    Mirror of `_overwrite_crs` in client.py: the whole body in try/except,
    because a corrupt TIFF from a correctly extracted ZIP can make rasterio
    raise an unmapped exception (e.g. TypeError) instead of
    (DownloadError, ValidationError) — without catching it such an exception
    would escape `_cz_download_sheet`/`_run_cz` as a traceback. On error both
    the target file and the accompanying .tfw are removed, so that
    `skip_existing` on the next run does not make the corruption permanent.
    """
    try:
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                logger.debug(f"{path.name}: no CRS in GeoTIFF - writing {crs}")
                ds.crs = CRS.from_string(crs)
    except Exception as e:
        path.unlink(missing_ok=True)
        path.with_suffix(".tfw").unlink(missing_ok=True)
        raise DownloadError(
            message("providers.crs_write_failed", crs=crs, path=path, error=reason(e))
        ) from e
