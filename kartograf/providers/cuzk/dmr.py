"""
CuzkDmrProvider — DMR 5G (2 m, exportImage) and DMR 4G (5 m, openzu + exportImage).

Nativeness rule: the exportImage result is a server derivative (GeoTIFF); the
openzu files are CUZK bytes 1:1 — only the CRS tag is modified, in a GeoTIFF
without a CRS (metadata repair). Vertical transformation only on an explicit
request (vertical_crs="EVRF2007").

Endpoints come ONLY from descriptors (`get_source(...).channels[..].endpoint`)
— the provider knows no URL. Sidecars are written by the CLI/manager layer.
"""

import dataclasses
import logging
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.transform import xy as _pixel_xy
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, transform_bbox
from kartograf.core.parser_registry import detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, wkid
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.sources.descriptor import AccessChannel, TransportKind
from kartograf.sources.registry import get_source
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

logger = logging.getLogger(__name__)

CUZK_NODATA = -9999.0

# The CRS in which CUZK STORES the raster data. The server receives requests
# only in it: imageSR=2180 loses the datum transformation (135 m error,
# ADR-024). The former 1.25 m for 3045 came from the difference between the
# Czech EPSG:1622 and the Slovak EPSG:4829 operations in the local reference,
# not from a server error (errata).
NATIVE_CRS = "EPSG:5514"

_RESOLUTION_KEYS = {"2m": "cz.cuzk.dmr5g", "5m": "cz.cuzk.dmr4g"}
_PIXEL_SIZES = {"2m": 2.0, "5m": 5.0}
_SUPPORTED_VERTICAL = ("Bpv", "EVRF2007")
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


class CuzkDmrProvider(BaseProvider):
    """NMT provider for Czechia (CUZK): DMR 5G / DMR 4G."""

    def __init__(
        self,
        resolution: str = "2m",
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
        target_crs: str | None = None,
        vertical_crs: str = "Bpv",
    ):
        if resolution not in _RESOLUTION_KEYS:
            raise ValidationError(
                f"Nieobslugiwana rozdzielczosc CZ: '{resolution}' (dostepne: 2m, 5m)"
            )
        if vertical_crs == "KRON86":
            raise TransformUnavailableError(
                "Brak transformacji Bpv (EPSG:8357) -> KRON86 (EPSG:9650) "
                "— siatki GUGiK nie sa publiczne",
                remedy=REMEDIES["EPSG:9650"],
            )
        if vertical_crs not in _SUPPORTED_VERTICAL:
            raise ValidationError(
                f"Nieobslugiwany uklad pionowy dla CZ: '{vertical_crs}' "
                f"(dostepne: {', '.join(_SUPPORTED_VERTICAL)})"
            )
        self.descriptor_key = _RESOLUTION_KEYS[resolution]
        self._resolution = resolution
        self._pixel_size = _PIXEL_SIZES[resolution]
        self._target_crs = target_crs
        self._vertical_crs = vertical_crs
        self._session = session or requests.Session()
        self._client = CuzkClient(session=self._session, timeout=_DEFAULT_TIMEOUT)
        self._client_timeout = _DEFAULT_TIMEOUT
        self._sheet_index = SheetIndex(session=self._session, cache=cache)
        self._transforms: dict[tuple[str, str], PinnedTransform] = {}
        # Fail-fast as with KRON86: the lack of a safe 8357->5621 operation must
        # abort BEFORE any download, so the user does not pay for the transfer
        # and does not get a Bpv file under the name ordered as EVRF2007.
        self._vertical_transform: PinnedTransform | None = (
            self._pinned("EPSG:8357", "EPSG:5621", _VERTICAL_POLICY)
            if vertical_crs == "EVRF2007"
            else None
        )
        # The same rule for the horizontal part: when the user requested a CRS other
        # than native, the lack of a safe operation must abort before the transfer.
        if target_crs is not None:
            self.horizontal_transform(target_crs)

        descriptor = get_source(self.descriptor_key)
        image_endpoint = _endpoint_for(descriptor.channels, TransportKind.ARCGIS_IMAGE)
        if image_endpoint is None:
            raise ValidationError(
                f"Deskryptor '{self.descriptor_key}' nie ma kanalu "
                f"{TransportKind.ARCGIS_IMAGE.name} z endpointem — "
                f"pobieranie rastrow CUZK niemozliwe"
            )
        self._image_endpoint: str = image_endpoint
        # The file channel exists only for DMR 4G (SM5 sheets from openzu);
        # None is a valid state here, not a configuration error.
        self._files_endpoint: str | None = _endpoint_for(
            descriptor.channels, TransportKind.DIRECT_FILES
        )

    @property
    def name(self) -> str:
        return f"CUZK DMR ({self._resolution})"

    @property
    def base_url(self) -> str:
        return self._image_endpoint

    @property
    def default_extension(self) -> str:
        return ".tif"

    @property
    def resolution(self) -> str:
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
        """Pinned ``EPSG:5514 -> target_crs`` operation used to reproject the
        raster CONTENT; ``None`` when the result stays in the native CRS.

        The same instance as used during download (``_transforms`` cache), so
        the description and accuracy in the sidecar describe the operation
        actually performed.
        """
        if wkid(target_crs) == wkid(NATIVE_CRS):
            return None
        return self._pinned(
            NATIVE_CRS, target_crs, CONTENT_POLICY, probe=CZ_PROBE_NATIVE
        )

    @property
    def vertical_transform(self) -> PinnedTransform | None:
        """Pinned 8357->5621 operation (None for a native Bpv download).

        Built in the constructor — see the fail-fast note there.
        """
        return self._vertical_transform

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = _DEFAULT_TIMEOUT,
        *,
        on_download: Callable[[], None] | None = None,
    ) -> Path:
        """Download a TM33 tile (grid in 3045) or an SM5 sheet (openzu, 5514).

        `target_crs` applies only to bbox mode — the sheet code defines the
        extent in a specific CRS, so reprojection would diverge it from the
        grid. The TM33 tile lies in EPSG:3045 and the CUZK data in EPSG:5514:
        `exportImage` gets a native request, and a local warp carries it onto
        the tile grid (ADR-024). The SM5 sheet arrives as a file already in
        5514 — no warp.

        ``on_download`` is called exactly once, after every validation
        (CZ system, SM5 resolution and sheet-index lookup, TM33 grid parse)
        and right before the data transfer starts; it is never called when
        the request is rejected (same contract as
        ``DownloadManager.download_sheet(on_download=)`` in the PL flow).
        """
        output_path = Path(output_path)
        # like the system registry: whitespace is not part of the sheet code
        # (openzu URL, SM5 index and ParserTM33 get the same stripped code)
        godlo = godlo.strip()
        system = detect_system(godlo)
        if system.country != "CZ":
            raise ValidationError(
                f"Godlo '{godlo}' nie nalezy do zadnego systemu CZ "
                f"(TM33: 302_5550, SM5: CTES96)"
            )
        if system.id == "cz_sm5":
            self._download_sm5(godlo, output_path, timeout, on_download)
        else:  # cz_tm33
            # Parsing through ParserTM33 (full validation: even kilometres),
            # not through the system registry regex alone.
            bbox = ParserTM33(godlo).get_bbox()
            self._export_raster(bbox, output_path, timeout, on_download)
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
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
        """A single cutout for any bbox (`--target-crs` => local warp).

        ``on_download``: called once right before the first ``exportImage``
        request, after format and CRS validation (see :meth:`download`).
        """
        if format != "GTiff":
            raise ValidationError(
                f"CuzkDmrProvider.download_bbox obsluguje tylko GTiff "
                f"(zadano: {format})"
            )
        output_path = Path(output_path)
        image_sr = self._target_crs or NATIVE_CRS
        if wkid(bbox.crs) != wkid(image_sr):
            bbox = self._bbox_to_crs(bbox, image_sr)
        self._export_raster(bbox, output_path, timeout, on_download)
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
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
                self._image_endpoint,
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
                self._image_endpoint,
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

    def _download_sm5(
        self,
        godlo: str,
        output_path: Path,
        timeout: int,
        on_download: Callable[[], None] | None = None,
    ) -> None:
        """SM5 sheet (DMR 4G) from openzu + CRS metadata repair."""
        if self._resolution != "5m":
            raise ValidationError(
                f"Arkusze SM5 sa dostepne tylko dla --resolution 5m "
                f"(DMR 4G); dla 2m uzyj godla TM33 albo --bbox "
                f"[godlo: {godlo}]"
            )
        if self._files_endpoint is None:
            raise ValidationError(
                f"Deskryptor '{self.descriptor_key}' nie ma kanalu "
                f"{TransportKind.DIRECT_FILES.name} z endpointem — "
                f"pobieranie arkuszy SM5 niemozliwe"
            )
        self._sheet_index.sm5_sheet(godlo)  # validation before download
        url = self._files_endpoint.format(sheet=godlo)
        if on_download is not None:
            on_download()
        try:
            self._client_for(timeout).fetch_file(url, output_path, unzip_single=".tif")
        except DownloadError as e:
            # spec section 7: 404 from openzu -> hint to verify the sheet code
            raise DownloadError(
                f"{e} — zweryfikuj godlo w indeksie KladyMapovychListu "
                f"(arkusz moze byc znany indeksowi, ale plik openzu "
                f"niedostepny)"
            ) from e
        _assign_crs(output_path, "EPSG:5514")

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

    def _apply_vertical_shift(self, path: Path) -> None:
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
        pinned = self._vertical_transform
        if pinned is None:  # pragma: no cover — called only for EVRF2007
            return
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
                raise ValidationError(
                    f"Raster {label} nie ma CRS — nie da sie wyznaczyc "
                    f"(lon, lat) wymaganych przez operacje pionowa"
                )
            if ds.transform.is_identity or not ds.transform.is_rectilinear:
                raise ValidationError(
                    f"Raster {label} nie ma uzytecznej geotransformacji "
                    f"(jednostkowa/nieprostokatna) — nie da sie wyznaczyc "
                    f"(lon, lat) dla operacji pionowej"
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
                f"Transformacja pionowa {label}: {pinned.description} "
                f"(dokladnosc {pinned.accuracy_m} m), nodata {nodata}"
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


def _endpoint_for(
    channels: tuple[AccessChannel, ...], transport: TransportKind
) -> str | None:
    """Endpoint of the first channel of the given transport (None if none)."""
    return next(
        (ch.endpoint for ch in channels if ch.transport == transport and ch.endpoint),
        None,
    )


def _assign_crs(path: Path, crs: str) -> None:
    """Repair DMR4G-TIFF metadata: write the CRS (georeferencing is in .tfw).

    Mirror of `_overwrite_crs` in client.py: the whole body in try/except,
    because a corrupt TIFF from a correctly extracted ZIP can make rasterio
    raise an unmapped exception (e.g. TypeError) instead of
    (DownloadError, ValidationError) — without catching it such an exception
    would escape `_cz_download_godlo`/`_run_cz` as a traceback. On error both
    the target file and the accompanying .tfw are removed, so that
    `skip_existing` on the next run does not make the corruption permanent.
    """
    try:
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                logger.debug(f"{path.name}: brak CRS w GeoTIFF — wpisuje {crs}")
                ds.crs = CRS.from_string(crs)
    except Exception as e:
        path.unlink(missing_ok=True)
        path.with_suffix(".tfw").unlink(missing_ok=True)
        raise DownloadError(f"nie udalo sie wpisac CRS {crs} w {path}: {e}") from e
