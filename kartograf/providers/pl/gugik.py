"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) services.

Two download methods based on input type:
- Sheet code → OpenData (ASC format)
- BBox (bounding box) → WCS (GeoTIFF/PNG/JPEG formats; 1m only; EVRF2007
  heights requested as image/x-aaigrid and written as GeoTIFF float32)

Supported resolutions:
- 1m (GRID1) - available for EVRF2007 and KRON86
- 5m (GRID5) - available only for EVRF2007
"""

import logging
import re
import threading
from pathlib import Path

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import (
    DownloadError,
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
    query_skorowidz_layer,
    select_sheet_record,
)
from kartograf.providers.pl.wcs import HEIGHT_AAIGRID, HEIGHT_GTIFF, GugikWcsMixin
from kartograf.transport.chunks import GridSpec
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
)

logger = logging.getLogger(__name__)


class GugikProvider(SkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Provider for downloading NMT data from GUGiK.

    Supports two download modes:
    - By sheet code: downloads from OpenData as ASC
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
    >>> # Download by sheet code → ASC from OpenData
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))
    >>>
    >>> # Download by bbox → GeoTIFF float32 from WCS (1m, both vertical CRS)
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_bbox(bbox, Path("./area.tif"))
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

    # WCS endpoints for NMT data (by vertical CRS) - only 1m resolution.
    # KRON86 heights come as float32 GeoTIFF from the TIFF endpoint; EVRF2007
    # heights only as image/x-aaigrid from DigitalTerrainModel (its image/tiff is
    # RGB) - docs/research/2026-10-11-wcs-cutouts/raport.md, point 1.
    # Note: 5m resolution is NOT available via WCS
    WCS_ENDPOINTS = {
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
        "DigitalTerrainModelFormatTIFF",
        "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModel",
    }

    # WMS endpoints for the indexes (skorowidze) - used to find OpenData URLs
    # Structure: {resolution: {vertical_crs: endpoint}}
    WMS_INDEX_ENDPOINTS = {
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

    # Vertical CRS whose WCS endpoint GUGiK withdrew: download_bbox fails before
    # the network. None today (the EVRF2007 entry pointed at a non-existent
    # endpoint until 0.7.2); kept as the mechanism for future withdrawals.
    WITHDRAWN_WCS_VERTICAL_CRS: tuple[str, ...] = ()

    # Coverage IDs for WCS (by vertical CRS) - only 1m resolution
    COVERAGE_IDS = {
        "KRON86": "DTM_PL-KRON86-NH_TIFF",
        "EVRF2007": "DTM_PL-EVRF2007-NH",
    }

    # How heights of each vertical CRS are requested (GugikWcsMixin.HEIGHT_*).
    WCS_HEIGHT_FORMAT = {"KRON86": HEIGHT_GTIFF, "EVRF2007": HEIGHT_AAIGRID}

    # NMT 1 m sheet grid: step 1 m, pixel edges at k + 0.5 m - measured in 9
    # regions of Poland and identical to the OpenData sheets
    # (docs/research/2026-10-10-wcs-limits/raport.md, points 4 and 7).
    WCS_GRID: GridSpec | None = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)
    WCS_NATIVE_STEP: float | None = 1.0

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
        # Variant index endpoints that failed (P10): skipped from then on
        self._failed_variants: set[str] = set()
        self._failed_variants_lock = threading.Lock()
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
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for a map sheet from OpenData.

        Always downloads ASC format - this is the native format for
        sheet-code-based downloads from GUGiK OpenData.

        Parameters
        ----------
        sheet : str
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
            sheet (sea, the Czech side of a border bbox, gaps in 1m coverage).
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

        record = self._resolve_sheet(sheet, timeout)
        verify_record_vertical_crs(record, self._vertical_crs, sheet)
        return self.download_record(record, Path(output_path), timeout)

    def _get_opendata_url(self, sheet: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the URL of the strictly matching, newest index record."""
        return self._resolve_sheet(sheet, timeout).url

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key, endpoint (resolution + vertical CRS) and resolution filter.

        Reads attributes through ``self`` — NMPT overrides ``_CACHE_PRODUCT``
        and ``WMS_INDEX_ENDPOINTS``.
        """
        return SkorowidzQuery(
            cache_key=(
                self._CACHE_PRODUCT,
                self._resolution,
                self._vertical_crs,
                parser.sheet,
            ),
            endpoint=self.WMS_INDEX_ENDPOINTS.get(self._resolution, {}).get(
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
                if record.sheet == parser.sheet and record.resolution_m is not None:
                    hints.add(
                        f"GUGiK ma ten arkusz w {record.resolution_m:g} m — "
                        f"Kartograf pobiera dokladnie {wanted_resolution:g} m"
                    )
                continue
            matching.append(record)
        hints |= coverage_hints(parser, matching)
        hints |= self._variant_hints(parser)
        return no_coverage_error(
            parser,
            f"Brak danych {self._CACHE_PRODUCT.upper()} {self._resolution} dla "
            f"{parser.sheet} (uklad PL-{parser.system}, {self._vertical_crs})",
            hints,
        )

    def _variant_hints(self, parser: SheetParser) -> set[str]:
        """Hints naming the other variants of the product (resolution,
        vertical CRS from ``WMS_INDEX_ENDPOINTS``) whose index has the
        sheet (P10, 0.7.2).

        One GetFeatureInfo per variant with all its layers at the sheet's
        query point; a record passes the same hard filter as a download
        (sheet code, horizontal CRS, zone, resolution of the variant).
        Advisory: a failed variant query is logged and gives no hint - it
        never turns the no-coverage result into an error. One attempt per
        query (no retries) and a failed variant endpoint is skipped for the
        rest of the provider's life, so an outage of an index the user did
        not ask for costs one timeout, not one per sheet. The hint text has
        no sheet code, so the CLI shows one line for many sheets. Timeout:
        ``DEFAULT_TIMEOUT`` (``no_coverage`` does not receive the call's one).
        """
        hints: set[str] = set()
        query_bbox = self._query_bbox(parser)
        zone = int(parser.sheet.split(".")[0]) if parser.system == "2000" else None
        for resolution, by_crs in self.WMS_INDEX_ENDPOINTS.items():
            for vertical_crs, endpoint in by_crs.items():
                if (resolution, vertical_crs) == (self._resolution, self._vertical_crs):
                    continue
                variant = f"{resolution} {vertical_crs}"
                with self._failed_variants_lock:
                    if endpoint in self._failed_variants:
                        continue
                try:
                    records = query_skorowidz_layer(
                        self._sessions.get(),
                        endpoint,
                        ",".join(self._layers(endpoint, self.DEFAULT_TIMEOUT)),
                        query_bbox=query_bbox,
                        sheet=parser.sheet,
                        timeout=self.DEFAULT_TIMEOUT,
                        retries=1,
                        # no trailing digits: "EVRF2007" at the end of the
                        # label would read as a layer year in the parser
                        label=f"wariant {variant} (wszystkie warstwy)",
                    )
                except DownloadError as e:
                    with self._failed_variants_lock:
                        self._failed_variants.add(endpoint)
                    logger.warning(
                        "%s: nie sprawdzono wariantu %s (podpowiedz pominieta, "
                        "wariant pomijany do konca zadania): %s",
                        parser.sheet,
                        variant,
                        e,
                    )
                    continue
                found = select_sheet_record(
                    records,
                    sheet=parser.sheet,
                    system=parser.system,
                    zone=zone,
                    resolution_m=float(resolution[:-1]),
                )
                if found is not None:
                    flags = []
                    if resolution != self._resolution:
                        flags.append(f"--resolution {resolution}")
                    if vertical_crs != self._vertical_crs:
                        flags.append(f"--vertical-crs {vertical_crs}")
                    hints.add(
                        f"Skorowidz GUGiK ma ten arkusz w "
                        f"{self._CACHE_PRODUCT.upper()} {variant} — uzyj "
                        + " ".join(flags)
                    )
        return hints

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
            If the vertical CRS is in ``WITHDRAWN_WCS_VERTICAL_CRS`` (none today)

        Notes
        -----
        GeoTIFF: the file extent is the bbox expanded OUTWARD to the 1 m sheet
        grid (``WCS_GRID``: pixel edges at k + 0.5 m, < 1 px per side), because
        the server resamples to the requested grid and an off-grid bbox would
        shift the content by a fraction of a pixel; on that grid the content
        equals the OpenData 1 m sheets of the flight the server shows. The area
        is fetched in chunks (``plan_wcs_chunks``) and stitched without
        resampling (ADR-034). Heights are float32 with no nodata: KRON86 as
        GeoTIFF (16 Mpx chunks), EVRF2007 as ``image/x-aaigrid`` converted to
        GeoTIFF in EPSG:2180 (1 Mpx chunks, ~20 s/Mpx). PNG/JPEG: one request
        with the bbox as given (preview). An OGC exception report is raised as
        ``DownloadError``, never saved.

        Examples
        --------
        >>> provider = GugikProvider(vertical_crs="EVRF2007")
        >>> bbox = BBox(
        ...     min_x=450000, min_y=550000, max_x=451000, max_y=551000, crs="EPSG:2180"
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

        if self._vertical_crs in self.WITHDRAWN_WCS_VERTICAL_CRS:
            raise ValidationError(
                f"WCS {self._CACHE_PRODUCT.upper()} 1m for {self._vertical_crs} is "
                "not available (endpoint withdrawn by GUGiK). Download sheets by "
                "sheet code instead."
            )

        return self._download_wcs(
            bbox,
            Path(output_path),
            format,
            timeout,
            f"bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
            f"({bbox.max_x:.0f},{bbox.max_y:.0f})",
        )

    def _wcs_target(self) -> tuple[str, str]:
        """WCS endpoint and coverage for the provider's vertical CRS."""
        return (
            self.WCS_ENDPOINTS[self._vertical_crs],
            self.COVERAGE_IDS[self._vertical_crs],
        )

    def _wcs_height_format(self) -> str:
        """``HEIGHT_GTIFF`` or ``HEIGHT_AAIGRID`` for the provider's vertical CRS."""
        return self.WCS_HEIGHT_FORMAT[self._vertical_crs]

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

        WCS is only available for 1m resolution (both vertical CRS) and not for
        a vertical CRS listed in ``WITHDRAWN_WCS_VERTICAL_CRS`` (none today).

        Returns
        -------
        bool
            True if WCS is available, False otherwise.
        """
        return (
            self._resolution == "1m"
            and self._vertical_crs not in self.WITHDRAWN_WCS_VERTICAL_CRS
        )
