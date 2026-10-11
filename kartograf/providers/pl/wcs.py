"""GUGiK WCS 2.0.1 GetCoverage — shared by NMT/NMPT 1 m and orthophotomaps (D13).

Area requests go through ``transport/chunks.py`` (ADR-034) when the provider
declares its source grid (``WCS_GRID``): the bbox is aligned OUTWARD to that grid
and split into chunks above ``WCS_CHUNK_LIMITS``. Measurements:
``docs/research/2026-10-10-wcs-limits/raport.md``.
"""

from pathlib import Path
from urllib.parse import urlencode

from kartograf.core.sheet_parser import BBox
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


class GugikWcsMixin:
    """Format -> GetCoverage URL; the derived class supplies endpoint and coverage.

    NMT/NMPT choose the endpoint and coverage by vertical CRS, orto has a
    single fixed one — the rest of the request (version, SUBSET in
    EPSG:2180, formats, chunking) is shared.
    """

    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    # Source pixel grid of the coverage. The server resamples to the REQUESTED grid
    # (nearest neighbour), so a bbox off the source grid silently shifts content by
    # a fraction of a pixel against its georeference (report point 4). None = one
    # request with the bbox as given (grid not measured, or the GeoTIFF of the
    # coverage is not usable data - NMPT, report point 6).
    WCS_GRID: GridSpec | None = None

    # A reliability budget, not a server limit: no limit up to 100 Mpx and 40000 px
    # per side was measured, at ~3 s/Mpx and 4 MB/Mpx; the host drops connections,
    # so a 16 Mpx chunk (~50 s, 64 MB) keeps a retry cheap (report point 2).
    WCS_CHUNK_LIMITS = ChunkLimits(
        max_width=40_000, max_height=40_000, max_pixels=16_000_000
    )

    # Provided by the concrete providers.
    _sessions: SessionPerThread
    MAX_RETRIES: int

    def _wcs_target(self) -> tuple[str, str]:
        """(WCS endpoint, COVERAGEID) for the provider's current configuration."""
        raise NotImplementedError

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """GetCoverage URL for a bbox in EPSG:2180 and a ``WCS_FORMATS`` format."""
        endpoint, coverage_id = self._wcs_target()
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": self.WCS_FORMATS[format],
        }
        base_url = f"{endpoint}?{urlencode(params)}"
        subset_x = f"SUBSET=x({bbox.min_x:.2f},{bbox.max_x:.2f})"
        subset_y = f"SUBSET=y({bbox.min_y:.2f},{bbox.max_y:.2f})"
        return f"{base_url}&{subset_x}&{subset_y}"

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
        source grid (< 1 px per side) and requested in chunks of at most
        ``WCS_CHUNK_LIMITS``, fetched one at a time and stitched 1:1 (ADR-034);
        each chunk is retried on its own. Otherwise one request with the bbox as
        given. An OGC exception report (XML/HTML) is never saved as the result.
        """
        session = self._sessions.get()
        validate = reject_error_document("WCS")
        output_path = Path(output_path)
        grid = self.WCS_GRID

        def fetch_one(area: BBox, path: Path, label: str) -> None:
            download_to(
                session,
                self._construct_wcs_url(area, format),
                path,
                timeout=timeout,
                retries=self.MAX_RETRIES,
                validate=validate,
                description=label,
            )

        if format != "GTiff" or grid is None:
            fetch_one(bbox, output_path, description)
            return output_path

        aligned, width, height = align_bbox(bbox, grid.step, grid)
        chunks = plan_chunks(aligned, width, height, grid.step, self.WCS_CHUNK_LIMITS)
        count = len(chunks)

        def fetch(chunk: Chunk, path: Path) -> None:
            index = chunks.index(chunk) + 1
            label = description if count == 1 else f"{description} [{index}/{count}]"
            fetch_one(chunk.bbox, path, label)

        # WCS declares no nodata (report point 3); chunks cover the bbox exactly.
        return fetch_chunks(chunks, aligned, output_path, fetch, nodata=None)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported WCS formats."""
        return list(self.WCS_FORMATS.keys())
