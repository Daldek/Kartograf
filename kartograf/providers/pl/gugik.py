"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) services.

Two download methods based on input type:
- Sheet code (godlo) → OpenData (ASC format)
- BBox (bounding box) → WCS (GeoTIFF/PNG/JPEG formats; 1m and KRON86 only —
  the EVRF2007 WCS endpoint was withdrawn by GUGiK, see ``download_bbox``)

Supported resolutions:
- 1m (GRID1) - available for EVRF2007 and KRON86
- 5m (GRID5) - available only for EVRF2007
"""

import logging
import re
from pathlib import Path

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import (
    NoCoverageError,
    ValidationError,
)
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzLayersMixin,
    SkorowidzQuery,
    SkorowidzRecord,
    coverage_hints,
    no_coverage_error,
)
from kartograf.providers.pl.wcs import GugikWcsMixin
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
)

logger = logging.getLogger(__name__)


class GugikProvider(SkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Provider for downloading NMT data from GUGiK.

    Supports two download modes:
    - By sheet code (godlo): downloads from OpenData as ASC
    - By bbox (bounding box): downloads from WCS as GeoTIFF/PNG/JPEG
      (1m and KRON86 only, see ``download_bbox``)

    Supports two vertical coordinate systems:
    - EVRF2007 (PL-EVRF2007-NH) - default, European Vertical Reference Frame 2007
    - KRON86 (PL-KRON86-NH) - legacy Kronsztadt 86

    Supports two resolutions:
    - 1m (default) - high resolution, available for both EVRF2007 and KRON86
    - 5m - lower resolution, available only for EVRF2007

    Examples
    --------
    >>> provider = GugikProvider()
    >>> # Download by sheet code (godlo) → ASC from OpenData
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))
    >>>
    >>> # Download by bbox → GeoTIFF from WCS (KRON86 only, see download_bbox)
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> GugikProvider(vertical_crs="KRON86").download_bbox(bbox, Path("./area.tif"))
    >>>
    >>> # Download in legacy KRON86 vertical CRS
    >>> provider = GugikProvider(vertical_crs="KRON86")
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet_kron.asc"))
    >>>
    >>> # Download 5m resolution (only EVRF2007)
    >>> provider = GugikProvider(resolution="5m")
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet_5m.asc"))
    """

    # Base URL for GUGiK services
    BASE_URL = "https://mapy.geoportal.gov.pl"

    # Supported resolutions
    SUPPORTED_RESOLUTIONS = ["1m", "5m"]

    # WCS endpoints for NMT data (by vertical CRS) - only 1m resolution
    # Note: 5m resolution is NOT available via WCS
    WCS_ENDPOINTS = {
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
        "DigitalTerrainModelFormatTIFF",
        # Known service outage: HTTP 404 since 2026-08 (docs/PROGRESS.md);
        # kept for when GUGiK restores it
        "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
        "DigitalTerrainModelFormatTIFFEVRF2007",
    }

    # WMS endpoints for the indexes (skorowidze) - used to find OpenData URLs
    # Structure: {resolution: {vertical_crs: endpoint}}
    WMS_SKOROWIDZE_ENDPOINTS = {
        "1m": {
            "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladKRON86",
            "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladEVRF2007",
        },
        "5m": {
            # 5m is only available in EVRF2007
            "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/WMS/SheetsGrid5mEVRF2007",
        },
    }

    # Index layer names of this product: group 1 = year, group 2 = aggregate
    LAYER_PATTERN = re.compile(r"^SkorowidzeNMT(\d{4})(iStarsze)?$")
    # Product name family: a family name outside LAYER_PATTERN gives a warning
    LAYER_FAMILY = re.compile(r"^SkorowidzeNMT(?!P)")

    # Vertical CRS whose WCS endpoint GUGiK withdrew (HTTP 404 since 2026-08,
    # docs/PROGRESS.md). Applies to the NMT GRID1 endpoints declared above;
    # subclasses serving their own endpoints (NMPT) override this.
    WITHDRAWN_WCS_VERTICAL_CRS: tuple[str, ...] = ("EVRF2007",)

    # Coverage IDs for WCS (by vertical CRS) - only 1m resolution
    COVERAGE_IDS = {
        "KRON86": "DTM_PL-KRON86-NH_TIFF",
        "EVRF2007": "DTM_PL-EVRF2007-NH_TIFF",
    }

    # Supported vertical CRS by resolution
    SUPPORTED_VERTICAL_CRS = ["KRON86", "EVRF2007"]
    SUPPORTED_VERTICAL_CRS_5M = ["EVRF2007"]  # 5m only supports EVRF2007

    # Default settings
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = MAX_RETRIES

    # Product identifier for cache key
    _CACHE_PRODUCT = "nmt"

    def __init__(
        self,
        session: requests.Session | None = None,
        vertical_crs: str = "EVRF2007",
        resolution: str = "1m",
        cache=None,
    ):
        """
        Initialize GUGiK provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        vertical_crs : str, optional
            Vertical coordinate reference system: "KRON86" or "EVRF2007".
            Default is "EVRF2007" (European Vertical Reference Frame 2007).
        resolution : str, optional
            Grid resolution: "1m" or "5m". Default is "1m".
            Note: 5m resolution is only available for EVRF2007.
        cache : MetadataCache, optional
            Metadata cache instance for caching WMS lookup results.
            If None, no caching is performed (default behavior).
        """
        if resolution not in self.SUPPORTED_RESOLUTIONS:
            raise ValueError(
                f"Unsupported resolution: '{resolution}'. "
                f"Supported: {self.SUPPORTED_RESOLUTIONS}"
            )

        # 5m resolution only supports EVRF2007
        if resolution == "5m":
            if vertical_crs not in self.SUPPORTED_VERTICAL_CRS_5M:
                raise ValueError(
                    f"Resolution 5m is only available for EVRF2007, "
                    f"got vertical_crs='{vertical_crs}'. "
                    f"Use vertical_crs='EVRF2007' for 5m resolution."
                )
        else:
            if vertical_crs not in self.SUPPORTED_VERTICAL_CRS:
                raise ValueError(
                    f"Unsupported vertical CRS: '{vertical_crs}'. "
                    f"Supported: {self.SUPPORTED_VERTICAL_CRS}"
                )

        super().__init__()
        self._sessions = SessionPerThread(session)
        self._vertical_crs = vertical_crs
        self._resolution = resolution
        self._cache = cache
        self.descriptor_key = f"pl.gugik.nmt_{resolution}"

    @property
    def vertical_crs(self) -> str:
        """Return current vertical CRS."""
        return self._vertical_crs

    @property
    def resolution(self) -> str:
        """Return current resolution."""
        return self._resolution

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK"

    @property
    def default_extension(self) -> str:
        """Return default file extension for NMT data."""
        return ".asc"

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    # =========================================================================
    # Download by sheet code → OpenData (ASC)
    # =========================================================================

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for a map sheet (godlo) from OpenData.

        Always downloads ASC format - this is the native format for
        sheet-code-based downloads from GUGiK OpenData.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Path where the ASC file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 30)

        Returns
        -------
        Path
            Path to the downloaded ASC file

        Raises
        ------
        NoCoverageError
            Subclass of ``DownloadError``: every index (skorowidz) layer answered and
            none of them has the sheet, i.e. the source has no data for this
            godlo (sea, the Czech side of a border bbox, gaps in 1m coverage).
            An OGC exception report in a response is not an answer (see
            ``_resolve_sheet``). ``DownloadManager`` records such sheets in
            ``DownloadResult.no_coverage`` and the PL cutout fills them with
            nodata (ADR-027).
        DownloadError
            If any index layer query fails after retries, its answer is
            invalid, or the ASC download fails after retries. An older campaign
            is never substituted after a failed query. Also when the record
            declares another vertical datum than ``vertical_crs``
            (``verify_record_vertical_crs``; nothing is downloaded).

        Examples
        --------
        >>> provider = GugikProvider()
        >>> path = provider.download("N-34-130-D-d-2-4", Path("./data/sheet.asc"))
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import verify_record_vertical_crs

        record = self._resolve_sheet(godlo, timeout)
        verify_record_vertical_crs(record, self._vertical_crs, godlo)
        return self.download_record(record, Path(output_path), timeout)

    def _get_opendata_url(self, godlo: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the URL of the strictly matching, newest index record."""
        return self._resolve_sheet(godlo, timeout).url

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key, endpoint (resolution + vertical CRS) and resolution filter.

        Reads attributes through ``self`` — NMPT overrides ``_CACHE_PRODUCT``
        and ``WMS_SKOROWIDZE_ENDPOINTS``.
        """
        return SkorowidzQuery(
            cache_key=(
                self._CACHE_PRODUCT,
                self._resolution,
                self._vertical_crs,
                parser.godlo,
            ),
            endpoint=self.WMS_SKOROWIDZE_ENDPOINTS.get(self._resolution, {}).get(
                self._vertical_crs
            ),
            resolution_m=float(self._resolution[:-1]),
            no_coverage=self._no_coverage,
        )

    def _no_coverage(
        self, parser: SheetParser, records: list[SkorowidzRecord]
    ) -> NoCoverageError:
        hints = set()
        wanted_resolution = float(self._resolution[:-1])
        matching = []
        for record in records:
            if record.resolution_m != wanted_resolution:
                if record.godlo == parser.godlo and record.resolution_m is not None:
                    hints.add(
                        f"GUGiK ma ten arkusz w {record.resolution_m:g} m — "
                        f"Kartograf pobiera dokladnie {wanted_resolution:g} m"
                    )
                continue
            matching.append(record)
        hints |= coverage_hints(parser, matching)
        return no_coverage_error(
            parser,
            f"Brak danych {self._CACHE_PRODUCT.upper()} {self._resolution} dla "
            f"{parser.godlo} (uklad PL-{parser.uklad}, {self._vertical_crs})",
            hints,
        )

    # =========================================================================
    # Download by bbox → WCS (GeoTIFF/PNG/JPEG)
    # =========================================================================

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for a bounding box from WCS.

        Use this method when you need data for an arbitrary area
        (not aligned to standard map sheets).

        Note: WCS is only available for 1m resolution. For 5m resolution,
        use download() with a sheet code instead.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")
        timeout : int, optional
            Request timeout in seconds (default: 30)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails
        ValueError
            If format is not supported, bbox CRS is not EPSG:2180,
            or resolution is 5m (WCS not available for 5m)
        ValidationError
            If vertical_crs is EVRF2007 (WCS endpoint withdrawn by GUGiK)

        Notes
        -----
        Known service outage: the EVRF2007 WCS endpoint
        (DigitalTerrainModelFormatTIFFEVRF2007) has returned HTTP 404 since
        2026-08 (docs/PROGRESS.md), so bbox downloads work only with
        ``vertical_crs="KRON86"``. Use ``download()`` with a sheet code to get
        EVRF2007 heights.

        Examples
        --------
        >>> provider = GugikProvider(vertical_crs="KRON86")
        >>> bbox = BBox(
        ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        ... )
        >>> path = provider.download_bbox(bbox, Path("./area.tif"))
        """
        # WCS is only available for 1m resolution
        if self._resolution == "5m":
            raise ValueError(
                "WCS download (download_bbox) is not available for 5m resolution. "
                "Use download() with a godło instead, or use resolution='1m'."
            )

        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        if format not in self.WCS_FORMATS:
            raise ValueError(
                f"Unsupported WCS format: '{format}'. "
                f"Supported formats: {list(self.WCS_FORMATS.keys())}"
            )

        # GUGiK withdrew the EVRF2007 WCS endpoint (HTTP 404 since 2026-08):
        # fail with a readable message instead of three retried 404s
        if self._vertical_crs in self.WITHDRAWN_WCS_VERTICAL_CRS:
            raise ValidationError(
                "WCS NMT 1m for EVRF2007 is not available (GUGiK removed the "
                "endpoint, HTTP 404). Use GugikProvider(vertical_crs='KRON86') "
                "or download sheets by godlo."
            )

        output_path = Path(output_path)

        url = self._construct_wcs_url(bbox, format)

        return download_to(
            self._sessions.get(),
            url,
            output_path,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=(
                f"bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def _wcs_target(self) -> tuple[str, str]:
        """WCS endpoint and coverage for the provider's vertical CRS."""
        return (
            self.WCS_ENDPOINTS[self._vertical_crs],
            self.COVERAGE_IDS[self._vertical_crs],
        )

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_supported_resolutions(self) -> list[str]:
        """Return list of supported resolutions."""
        return list(self.SUPPORTED_RESOLUTIONS)

    def get_supported_vertical_crs_for_resolution(
        self, resolution: str | None = None
    ) -> list[str]:
        """
        Return list of supported vertical CRS for given resolution.

        Parameters
        ----------
        resolution : str, optional
            Resolution to check. If None, uses current resolution.

        Returns
        -------
        list[str]
            Supported vertical CRS for the resolution.
        """
        res = resolution or self._resolution
        if res == "5m":
            return list(self.SUPPORTED_VERTICAL_CRS_5M)
        return list(self.SUPPORTED_VERTICAL_CRS)

    def is_wcs_available(self) -> bool:
        """
        Check if WCS download is available for current configuration.

        WCS is only available for 1m resolution and only for vertical CRS
        whose endpoint is still served: the NMT EVRF2007 endpoint has
        returned HTTP 404 since 2026-08 (docs/PROGRESS.md), so for NMT this
        means KRON86 only.

        Returns
        -------
        bool
            True if WCS is available, False otherwise.
        """
        return (
            self._resolution == "1m"
            and self._vertical_crs not in self.WITHDRAWN_WCS_VERTICAL_CRS
        )
