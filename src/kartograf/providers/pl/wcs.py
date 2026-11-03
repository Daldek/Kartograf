"""GUGiK WCS 2.0.1 GetCoverage — shared by NMT/NMPT 1 m and orthophotomaps (D13).

Area requests go through ``transport/chunks.py`` (ADR-034) when the provider
declares its result grid (``WCS_GRID``): the bbox is aligned OUTWARD to that grid
and split into chunks above the chunk limits of the request format. Heights the
server sends only as ``image/x-aaigrid`` (NMT EVRF2007, NMPT) are converted to
float32 GeoTIFF per chunk (``transport/aaigrid.py``). Measurements:
``docs/research/2026-10-10-wcs-limits/raport.md``,
``docs/research/2026-10-11-wcs-cutouts/raport.md``.
"""

from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode

from kartograf.core.bbox import BBox
from kartograf.transport.aaigrid import ASC_MEDIA_TYPE, save_multipart_asc
from kartograf.transport.chunks import (
    Chunk,
    ChunkLimits,
    GridSpec,
    align_bbox,
    fetch_chunks,
    plan_chunks,
)
from kartograf.transport.http import (
    SessionPerThread,
    download_to,
    reject_error_document,
)

# Heights as float32 GeoTIFF straight from the server, or as ASC converted locally.
HEIGHT_GTIFF = "GTiff"
HEIGHT_AAIGRID = "AAIGrid"


class GugikWcsMixin:
    """Format -> GetCoverage URL; the derived class supplies endpoint and coverage.

    NMT/NMPT choose the endpoint and coverage by vertical CRS, orto by its
    WCS cutout channel (Standard or High; the raw ``download_bbox`` without
    one: Standard) - the rest of the request (version, SUBSET in EPSG:2180,
    formats, chunking) is shared.
    """

    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    # Pixel grid of the RESULT (the OpenData sheet grid). The server resamples to
    # the REQUESTED grid (nearest neighbour), so a bbox off the source grid silently
    # shifts content by a fraction of a pixel against its georeference (2026-10-10
    # report point 4); on the sheet grid the result is the sheet content bit for bit
    # (2026-10-11 report point 3). None = one request with the bbox as given.
    WCS_GRID: GridSpec | None = None

    # Step of the coverage itself; a result step (``WCS_GRID.step``) different from
    # it is requested with SCALEFACTOR = native / result (NMPT: 0.5 m coverage,
    # 1 m result). None = the result step.
    WCS_NATIVE_STEP: float | None = None

    # A reliability budget, not a server limit: no limit up to 100 Mpx and 40000 px
    # per side was measured, at ~3 s/Mpx and 4 MB/Mpx; the host drops connections,
    # so a 16 Mpx chunk (~50 s, 64 MB) keeps a retry cheap (report point 2). Like
    # the ASC budget below it counts COVERAGE pixels (equal steps for NMT; the
    # orthophotomap cutout sets its own from ``WcsCutoutParams``).
    WCS_CHUNK_LIMITS = ChunkLimits(
        max_width=40_000, max_height=40_000, max_pixels=16_000_000
    )

    # image/x-aaigrid: ~20.5 B/px and ~20 s/Mpx, and the server stays silent before
    # the first byte longer for larger requests (1 Mpx: ~7 s, 4 Mpx: ~25 s) while
    # DEFAULT_TIMEOUT (30 s) is a read timeout - 1 Mpx keeps the first byte well
    # within it (docs/research/2026-10-11-wcs-cutouts/raport.md, point 5). The
    # budget counts COVERAGE pixels: a result step coarser than the coverage
    # (NMPT 1 m from 0.5 m) reads (step / native)^2 coverage pixels per result
    # pixel. NMPT overrides the budget (GugikNmptProvider).
    WCS_CHUNK_LIMITS_AAIGRID = ChunkLimits(
        max_width=40_000, max_height=40_000, max_pixels=1_000_000
    )

    # image/x-aaigrid sends no byte before the whole chunk is computed. Live
    # 2026-10-11 the first byte of NMPT (SCALEFACTOR, 1 Mpx of coverage) came after
    # 19-106 s and NMT 1 Mpx went past 30 s under load, while hangs without a byte
    # last 600-1200 s - an ASC chunk waits at least this long (s) for data, which
    # still cuts a hang (report docs/research/2026-10-11-wcs-cutouts-live).
    WCS_ASC_READ_TIMEOUT = 120

    # Provided by the concrete providers.
    _sessions: SessionPerThread
    MAX_RETRIES: int

    def _wcs_target(self) -> tuple[str, str]:
        """(WCS endpoint, COVERAGEID) for the provider's current configuration."""
        raise NotImplementedError

    def _wcs_height_format(self) -> str:
        """Height request format of ``format="GTiff"``: ``HEIGHT_GTIFF`` or ASC."""
        return HEIGHT_GTIFF

    def _wcs_scale(self) -> float | None:
        """SCALEFACTOR of a ``WCS_GRID`` request; None when the steps are equal."""
        if self.WCS_GRID is None or self.WCS_NATIVE_STEP is None:
            return None
        scale = self.WCS_NATIVE_STEP / self.WCS_GRID.step
        return None if scale == 1 else scale

    def _construct_wcs_url(
        self, bbox: BBox, format: str, scale: float | None = None
    ) -> str:
        """GetCoverage URL for a bbox in EPSG:2180.

        ``format``: a ``WCS_FORMATS`` key or ``HEIGHT_AAIGRID``
        (``image/x-aaigrid``); ``scale`` other than None/1 adds ``SCALEFACTOR``.
        """
        endpoint, coverage_id = self._wcs_target()
        media = ASC_MEDIA_TYPE if format == HEIGHT_AAIGRID else self.WCS_FORMATS[format]
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": media,
        }
        if scale is not None and scale != 1:
            params["SCALEFACTOR"] = f"{scale:g}"
        base_url = f"{endpoint}?{urlencode(params)}"
        subset_x = f"SUBSET=x({bbox.min_x:.2f},{bbox.max_x:.2f})"
        subset_y = f"SUBSET=y({bbox.min_y:.2f},{bbox.max_y:.2f})"
        return f"{base_url}&{subset_x}&{subset_y}"

    def plan_wcs_chunks(self, bbox: BBox) -> list[Chunk]:
        """Chunks of a ``format="GTiff"`` request of ``bbox`` (EPSG:2180).

        The bbox aligned OUTWARD to ``WCS_GRID``, widened by at most 1 px east
        and south to an even size and cut into even-sized chunks within the
        limits of the height format (ASC: ``WCS_CHUNK_LIMITS_AAIGRID``), counted
        in coverage pixels: when the server resamples (NMPT ``SCALEFACTOR``,
        NMT 1 m over a 0.5 m flight), an odd-sized request takes its middle row
        and column from the neighbouring source pixel (live 2026-10-11,
        ``docs/research/2026-10-11-wcs-cutouts-live``); even sizes give the
        sheet content bit for bit. The orthophotomap at 0.25 m needs them too:
        an even number of 0.25 m pixels is a whole number of 0.1 m coverage
        pixels, and a fractional one gives a wrong grid or HTTP 400 (live
        2026-10-16, ``tests/fixtures/pl/orto_wcs/README.md``). The extra pixels
        are cropped after stitching (``fetch_chunks``).
        """
        grid = self.WCS_GRID
        if grid is None:
            raise ValueError("plan_wcs_chunks: the provider declares no WCS_GRID")
        aligned, width, height = align_bbox(bbox, grid.step, grid)
        even_w, even_h = width + width % 2, height + height % 2
        request = BBox(
            aligned.min_x,
            aligned.max_y - even_h * grid.step,
            aligned.min_x + even_w * grid.step,
            aligned.max_y,
            aligned.crs,
        )
        if self._wcs_height_format() == HEIGHT_AAIGRID:
            limits = self.WCS_CHUNK_LIMITS_AAIGRID
        else:
            limits = self.WCS_CHUNK_LIMITS
        native = self.WCS_NATIVE_STEP or grid.step
        # the budget counts coverage pixels (NMPT: 4 per 1 m result pixel,
        # orthophotomap 0.25 m: 6.25 per result pixel of the 0.1 m coverage)
        per_pixel = max(1.0, (grid.step / native) ** 2)
        limits = replace(limits, max_pixels=int(limits.max_pixels / per_pixel))
        return plan_chunks(request, even_w, even_h, grid.step, limits, multiple=2)

    def _download_wcs(
        self,
        bbox: BBox,
        output_path: Path,
        format: str,
        timeout: float,
        description: str,
    ) -> Path:
        """GetCoverage of ``bbox`` into ``output_path``; chunked on ``WCS_GRID``.

        GeoTIFF with a declared ``WCS_GRID``: the bbox is expanded outward to the
        result grid (< 1 px per side) and requested in even-sized chunks
        (``plan_wcs_chunks``), fetched one at a time, stitched 1:1 and cropped to
        the aligned bbox (ADR-034); each chunk is retried on its own. Heights
        served only as ASC (``_wcs_height_format``) are requested as
        ``image/x-aaigrid`` (with ``SCALEFACTOR`` when the coverage step differs
        from the grid) and each chunk becomes a float32 GeoTIFF in EPSG:2180
        after its size and corner are checked. Otherwise one request with the
        bbox as given. An OGC exception report (XML/HTML) is never saved as the
        result.
        """
        session = self._sessions.get()
        validate = reject_error_document("WCS")
        output_path = Path(output_path)
        grid = self.WCS_GRID

        if format != "GTiff" or grid is None:
            download_to(
                session,
                self._construct_wcs_url(bbox, format),
                output_path,
                timeout=timeout,
                retries=self.MAX_RETRIES,
                validate=validate,
                description=description,
            )
            return output_path

        asc = self._wcs_height_format() == HEIGHT_AAIGRID
        request_format = HEIGHT_AAIGRID if asc else format
        scale = self._wcs_scale()
        aligned, _, _ = align_bbox(bbox, grid.step, grid)
        chunks = self.plan_wcs_chunks(bbox)
        count = len(chunks)

        def fetch(chunk: Chunk, path: Path) -> None:
            index = chunks.index(chunk) + 1
            label = description if count == 1 else f"{description} [{index}/{count}]"
            download_to(
                session,
                self._construct_wcs_url(chunk.bbox, request_format, scale),
                path,
                timeout=max(timeout, self.WCS_ASC_READ_TIMEOUT) if asc else timeout,
                retries=self.MAX_RETRIES,
                validate=validate,
                save=save_multipart_asc(chunk) if asc else None,
                description=label,
            )

        # WCS declares no nodata (report point 3); the chunks cover the aligned
        # bbox plus at most 1 px east/south, cropped when stitching.
        return fetch_chunks(chunks, aligned, output_path, fetch, nodata=None)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported WCS formats."""
        return list(self.WCS_FORMATS.keys())
