"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) services.

Two download methods based on input type:
- Godło (map sheet ID) → OpenData (ASC format)
- BBox (bounding box) → WCS (GeoTIFF/PNG/JPEG formats; 1m and KRON86 only —
  the EVRF2007 WCS endpoint was withdrawn by GUGiK, see ``download_bbox``)

Supported resolutions:
- 1m (GRID1) - available for EVRF2007 and KRON86
- 5m (GRID5) - available only for EVRF2007
"""

import logging
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Znaczniki raportu wyjatku OGC: WMS (<ServiceExceptionReport>) i OWS
# (<ows:ExceptionReport>) — wielkosc liter jak w schematach OGC.
_OGC_EXCEPTION_MARKERS = ("ServiceException", "ExceptionReport")
# Tresc pierwszego elementu z komunikatem: <ServiceException code="..."> (WMS)
# albo <ows:ExceptionText> (OWS); \b odrzuca korzen <ServiceExceptionReport>.
_OGC_EXCEPTION_TEXT = re.compile(
    r"<(?:\w+:)?(?:ServiceException|ExceptionText)\b[^>]*>(.*?)</", re.DOTALL
)


def _ogc_exception_excerpt(text: str, limit: int = 200) -> str:
    """Krotki, jednoliniowy wyciag raportu wyjatku OGC do komunikatu bledu.

    Komunikat elementu wyjatku, a nie poczatek dokumentu: pierwsze ~200 znakow
    raportu MapServera to sama deklaracja XML i przestrzenie nazw.
    """
    match = _OGC_EXCEPTION_TEXT.search(text)
    excerpt = match.group(1) if match and match.group(1).strip() else text
    return " ".join(excerpt.split())[:limit]


class GugikProvider(BaseProvider):
    """
    Provider for downloading NMT data from GUGiK.

    Supports two download modes:
    - By godło (map sheet ID): downloads from OpenData as ASC
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
    >>> # Download by godło → ASC from OpenData
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

    # WMS endpoints for skorowidze (index maps) - used to find OpenData URLs
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

    # Layers to query for ASC files (by resolution and vertical CRS)
    # Ordered from newest to oldest
    WMS_LAYERS = {
        "1m": {
            "KRON86": [
                "SkorowidzeNMT2019",
                "SkorowidzeNMT2018",
                "SkorowidzeNMT2017iStarsze",
            ],
            "EVRF2007": [
                "SkorowidzeNMT2026",
                "SkorowidzeNMT2025",
                "SkorowidzeNMT2024",
                "SkorowidzeNMT2023iStarsze",
            ],
        },
        "5m": {
            # 5m layers (only EVRF2007)
            # Note: the 5m skorowidze endpoint (SheetsGrid5mEVRF2007) still
            # serves the older roczniki — it has NOT been rolled forward to
            # 2026 like the 1m EVRF2007 endpoint. Verified via GetCapabilities.
            "EVRF2007": [
                "SkorowidzeNMT2025",
                "SkorowidzeNMT2024",
                "SkorowidzeNMT2023",
                "SkorowidzeNMT2022iStarsze",
            ],
        },
    }

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

    # WCS formats (for bbox downloads)
    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    # File extensions
    FORMAT_EXTENSIONS = {
        "GTiff": ".tif",
        "PNG": ".png",
        "JPEG": ".jpg",
        "ASC": ".asc",
    }

    # Default settings
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2

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

        self._session = session
        self._vertical_crs = vertical_crs
        self._resolution = resolution
        self._cache = cache
        self._validated_layers: dict[tuple[str, str], list[str]] = {}
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
    # WMS layer validation
    # =========================================================================

    def _fetch_wms_layers(self, wms_endpoint: str, timeout: int = 10) -> list[str]:
        """
        Fetch available Skorowidze layers from WMS GetCapabilities.

        Parameters
        ----------
        wms_endpoint : str
            WMS endpoint URL
        timeout : int, optional
            Request timeout in seconds (default: 10)

        Returns
        -------
        list[str]
            Sorted list of Skorowidze layer names (newest first,
            iStarsze layers last)

        Raises
        ------
        ValueError
            If no Skorowidze layers found in response
        requests.RequestException
            On network errors
        """
        # Use a dedicated session to avoid interfering with the main
        # session's mock side_effects in tests or download state
        session = requests.Session()
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetCapabilities",
        }
        response = session.get(wms_endpoint, params=params, timeout=timeout)
        response.raise_for_status()

        root = ET.fromstring(response.text)

        # Try WMS 1.3.0 namespace first, fall back to namespace-less
        wms_ns = "{http://www.opengis.net/wms}"
        names = [elem.text for elem in root.iter(f"{wms_ns}Name") if elem.text]
        if not names:
            names = [elem.text for elem in root.iter("Name") if elem.text]

        # Filter to Skorowidze layers
        skorowidze = [n for n in names if n.startswith("Skorowidze")]

        if not skorowidze:
            raise ValueError("No Skorowidze layers found in GetCapabilities response")

        # Sort: regular entries by year descending first,
        # then iStarsze by year descending, then entries without year
        def sort_key(name: str) -> tuple[int, int]:
            year_match = re.search(r"(\d{4})", name)
            if not year_match:
                return (2, 0)
            year = int(year_match.group(1))
            if "iStarsze" in name:
                return (1, -year)
            return (0, -year)

        skorowidze.sort(key=sort_key)

        return skorowidze

    def _get_validated_layers(
        self, resolution: str, vertical_crs: str, timeout: int = 10
    ) -> list[str]:
        """
        Get validated WMS layers, checking GetCapabilities against hardcoded.

        Results are cached per (resolution, vertical_crs) pair for the
        lifetime of this provider instance.

        Parameters
        ----------
        resolution : str
            Grid resolution ("1m" or "5m")
        vertical_crs : str
            Vertical CRS ("KRON86" or "EVRF2007")
        timeout : int, optional
            Request timeout for GetCapabilities (default: 10)

        Returns
        -------
        list[str]
            List of WMS layer names to query
        """
        cached = self._validated_layers.get((resolution, vertical_crs))
        if cached is not None:
            return cached

        hardcoded = self.WMS_LAYERS.get(resolution, {}).get(vertical_crs, [])

        resolution_endpoints = self.WMS_SKOROWIDZE_ENDPOINTS.get(resolution, {})
        wms_endpoint = resolution_endpoints.get(vertical_crs)

        if not wms_endpoint:
            self._validated_layers[(resolution, vertical_crs)] = hardcoded
            return hardcoded

        try:
            discovered = self._fetch_wms_layers(wms_endpoint, timeout)

            if set(discovered) != set(hardcoded):
                logger.warning(
                    f"WMS GetCapabilities returned different layers than hardcoded for "
                    f"resolution={resolution}, vertical_crs={vertical_crs}. "
                    f"Hardcoded: {hardcoded}. Discovered: {discovered}. "
                    f"Using discovered layers. Consider updating WMS_LAYERS in code."
                )
                self._validated_layers[(resolution, vertical_crs)] = discovered
                return discovered

            self._validated_layers[(resolution, vertical_crs)] = hardcoded
            return hardcoded

        except (requests.RequestException, ValueError, ET.ParseError) as e:
            logger.warning(
                f"Failed to fetch WMS GetCapabilities from {wms_endpoint}: {e}. "
                f"Using hardcoded WMS_LAYERS as fallback."
            )
            self._validated_layers[(resolution, vertical_crs)] = hardcoded
            return hardcoded

    # =========================================================================
    # Download by godło → OpenData (ASC)
    # =========================================================================

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for a map sheet (godło) from OpenData.

        Always downloads ASC format - this is the native format for
        godło-based downloads from GUGiK OpenData.

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
            Subclass of ``DownloadError``: every skorowidz layer answered and
            none of them has the sheet, i.e. the source has no data for this
            godlo (sea, the Czech side of a border bbox, gaps in 1m coverage).
            An OGC exception report in a response is not an answer (see
            ``_get_opendata_url``). ``DownloadManager`` records such sheets in
            ``DownloadResult.no_coverage`` and the PL cutout fills them with
            nodata (ADR-027).
        DownloadError
            If the skorowidz lookup fails (every layer query failed: service
            unavailable; or some failed and the rest have no sheet: coverage
            uncertain, not absent) or the ASC download still fails after all
            retries

        Notes
        -----
        Which file lands under ``godlo`` is decided by ``_get_opendata_url`` —
        see its Notes for the known bugs of that choice (K3, K4, S1).

        Examples
        --------
        >>> provider = GugikProvider()
        >>> path = provider.download("N-34-130-D-d-2-4", Path("./data/sheet.asc"))
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get OpenData URL via WMS GetFeatureInfo
        opendata_url = self._get_opendata_url(godlo, timeout)

        return self._download_with_retry(
            url=opendata_url,
            output_path=output_path,
            timeout=timeout,
            description=f"{godlo} (OpenData)",
        )

    def _get_opendata_url(
        self,
        godlo: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """
        Get OpenData URL for ASC file using WMS GetFeatureInfo.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        timeout : int, optional
            Request timeout in seconds

        Returns
        -------
        str
            OpenData URL for the ASC file

        Raises
        ------
        NoCoverageError
            If every skorowidz layer answered and none of them has the sheet
            (the source has no data for this godlo). A response without an
            OpenData URL whose body carries an OGC exception report
            (``ServiceException``/``ExceptionReport``) is not an answer: it
            counts as a failed query of that layer, like a transport error.
        DownloadError
            If every skorowidz layer query failed (transport error or OGC
            exception report: service unavailable), or if only some layers
            answered and the rest have no data for the sheet (coverage is
            then uncertain, not absent)

        Notes
        -----
        Layers are queried newest first, one request per layer, without
        retries and — unless a ``session`` was injected — on a fresh
        ``requests.Session`` per call. Known bugs (live tests 2026-09-29,
        docs/PROGRESS.md "Znane bledy"; not intended behaviour):

        - K3: if a newer layer query fails and an older layer has the sheet,
          the older edition's URL is returned (only a log warning);
        - K4: the first URL containing ``godlo`` as a substring wins,
          regardless of resolution (0.5 m files sit in the 1 m index),
          campaign date or coverage, and a URL without ``godlo`` is accepted
          as a fallback (e.g. a PL-2000 sheet under a PL-1992 godlo);
        - S1: no per-layer retry and no shared session.
        """
        # Check cache first
        if self._cache is not None:
            cached_url = self._cache.get_url(
                godlo, self._resolution, self._vertical_crs, self._CACHE_PRODUCT
            )
            if cached_url is not None:
                logger.debug(f"Using cached URL for {godlo}")
                return cached_url

        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")

        # Query point at center of the sheet
        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2

        # Small bbox around center (WMS 1.3.0 with EPSG:2180 uses y,x order)
        buffer = 10
        query_bbox = (
            f"{center_y - buffer},{center_x - buffer},"
            f"{center_y + buffer},{center_x + buffer}"
        )

        session = self._session or requests.Session()

        # Get WMS endpoint and layers for current resolution and vertical CRS
        resolution_endpoints = self.WMS_SKOROWIDZE_ENDPOINTS.get(self._resolution, {})
        wms_endpoint = resolution_endpoints.get(self._vertical_crs)

        if not wms_endpoint:
            raise DownloadError(
                f"No WMS endpoint available for resolution={self._resolution}, "
                f"vertical_crs={self._vertical_crs}. "
                f"5m resolution is only available for EVRF2007.",
                godlo=godlo,
            )

        wms_layers = self._get_validated_layers(self._resolution, self._vertical_crs)

        if not wms_layers:
            raise DownloadError(
                f"No WMS layers configured for resolution={self._resolution}, "
                f"vertical_crs={self._vertical_crs}.",
                godlo=godlo,
            )

        # Transport failures are counted separately from "layer answered but
        # has no data": all-failed means the service is down, not that the
        # sheet has no coverage
        transport_errors = 0
        last_error: Exception | None = None

        # Try each layer from newest to oldest
        for layer in wms_layers:
            params = {
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetFeatureInfo",
                "LAYERS": layer,
                "QUERY_LAYERS": layer,
                "INFO_FORMAT": "text/html",
                "CRS": "EPSG:2180",
                "BBOX": query_bbox,
                "WIDTH": 100,
                "HEIGHT": 100,
                "I": 50,
                "J": 50,
            }

            try:
                url = f"{wms_endpoint}?{urlencode(params)}"
                logger.debug(
                    f"Querying WMS for {godlo} on layer {layer} "
                    f"(resolution={self._resolution})"
                )

                response = session.get(url, timeout=timeout)
                response.raise_for_status()
                text = response.text

                # Parse HTML for OpenData URL pattern
                urls = re.findall(
                    r'url:"(https://opendata[^"]+\.asc)"',
                    text,
                )

                if urls:
                    # Prefer URL containing our godło
                    for found_url in urls:
                        if godlo in found_url:
                            logger.debug(f"Found OpenData URL: {found_url}")
                            self._cache_url(godlo, found_url)
                            return found_url

                    # Fallback: URL bez tego godla. Dla nowszych kampanii bywa to
                    # arkusz PL-2000 (inny zasieg i uklad), zapisywany pod godlem
                    # PL-1992 — wycinek --target-crs odrzuca taki arkusz glosno
                    # (plan 2026-09-28, fakt 7), lista arkuszy przyjmuje go bez zmian
                    # (znany blad K4, testy na zywo 2026-09-29).
                    logger.warning(
                        f"{godlo}: skorowidz zwrocil URL innego arkusza ({urls[0]}) "
                        "— plik moze byc innym arkuszem, np. w ukladzie PL-2000"
                    )
                    self._cache_url(godlo, urls[0])
                    return urls[0]

                # Brak URL + raport wyjatku OGC (MapServer odpowiada nim z HTTP
                # 200, np. LayerNotDefined dla nieaktualnej nazwy warstwy, gdy
                # GetCapabilities sie nie udal) to porazka zapytania tej warstwy,
                # nie "warstwa odpowiedziala i nie ma arkusza": pod R5 chwilowy
                # blad albo zla nazwa warstwy zostawilyby trwala dziure nodata.
                # Straz tylko negatywna — strona bledu z 200 BEZ znacznikow OGC
                # liczy sie dalej jako brak arkusza. Na zywo (2026-09-29):
                # pusta odpowiedz = szablon HTML MapServera (200, text/html) bez
                # znacznikow OGC, zla warstwa = 200 text/xml z LayerNotDefined.
                if any(marker in text for marker in _OGC_EXCEPTION_MARKERS):
                    transport_errors += 1
                    last_error = DownloadError(
                        f"warstwa {layer}: raport wyjatku OGC w odpowiedzi "
                        f"HTTP {response.status_code}: {_ogc_exception_excerpt(text)}",
                        godlo=godlo,
                    )
                    logger.warning(f"WMS query failed for layer {layer}: {last_error}")
                    continue

            except requests.RequestException as e:
                transport_errors += 1
                last_error = e
                logger.warning(f"WMS query failed for layer {layer}: {e}")
                continue

        if transport_errors == len(wms_layers):
            raise DownloadError(  # bez zmian: cala usluga niedostepna
                f"GUGiK WMS skorowidz unavailable for {godlo}: "
                f"all {transport_errors} layer queries failed "
                f"(last error: {last_error})",
                godlo=godlo,
            )

        if transport_errors:
            # Czesc warstw nie odpowiedziala — arkusz moze lezec wlasnie w nich.
            # To NIE jest brak pokrycia: wycinek potraktowalby go jako nodata
            # i chwilowa awaria zostawilaby trwala dziure (R5).
            raise DownloadError(
                f"GUGiK WMS skorowidz: {transport_errors} z {len(wms_layers)} "
                f"warstw nie odpowiedzialo dla {godlo}, pozostale nie maja "
                f"arkusza — brak pokrycia niepewny (ostatni blad: {last_error})",
                godlo=godlo,
            )

        raise NoCoverageError(
            f"No NMT {self._resolution} data available for {godlo} "
            f"(vertical_crs={self._vertical_crs}). "
            f"This area may not have {self._resolution} coverage in GUGiK. "
            f"Check https://mapy.geoportal.gov.pl for data availability.",
            godlo=godlo,
        )

    def _cache_url(self, godlo: str, url: str) -> None:
        """Store URL in cache if cache is available."""
        if self._cache is not None:
            self._cache.set_url(
                godlo,
                self._resolution,
                self._vertical_crs,
                self._CACHE_PRODUCT,
                url,
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
        use download() with a godło instead.

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
        ``vertical_crs="KRON86"``. Use ``download()`` with a godło to get
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
        output_path.parent.mkdir(parents=True, exist_ok=True)

        url = self._construct_wcs_url(bbox, format)

        return self._download_with_retry(
            url=url,
            output_path=output_path,
            timeout=timeout,
            description=(
                f"bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """
        Construct WCS GetCoverage URL for bounding box.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        format : str
            Output format (GTiff, PNG, JPEG)

        Returns
        -------
        str
            Full WCS URL
        """
        wcs_endpoint = self.WCS_ENDPOINTS[self._vertical_crs]
        coverage_id = self.COVERAGE_IDS[self._vertical_crs]

        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": self.WCS_FORMATS[format],
        }

        base_url = f"{wcs_endpoint}?{urlencode(params)}"
        subset_x = f"SUBSET=x({bbox.min_x:.2f},{bbox.max_x:.2f})"
        subset_y = f"SUBSET=y({bbox.min_y:.2f},{bbox.max_y:.2f})"

        return f"{base_url}&{subset_x}&{subset_y}"

    # =========================================================================
    # Common utilities
    # =========================================================================

    def _download_with_retry(
        self,
        url: str,
        output_path: Path,
        timeout: int,
        description: str,
    ) -> Path:
        """
        Download file with automatic retry on failure.

        Parameters
        ----------
        url : str
            URL to download
        output_path : Path
            Target path
        timeout : int
            Request timeout
        description : str
            Description for logging

        Returns
        -------
        Path
            Path to downloaded file

        Raises
        ------
        DownloadError
            If download fails after all retries
        """
        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {description} (attempt {attempt}/{self.MAX_RETRIES})"
                )

                response = self._make_request(url, timeout)
                self._save_response(response, output_path)

                logger.info(f"Successfully downloaded {description} to {output_path}")
                return output_path

            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"Download failed for {description} (attempt {attempt}): {e}"
                )

                if attempt < self.MAX_RETRIES:
                    wait_time = self.RETRY_BACKOFF_BASE**attempt
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        raise DownloadError(
            f"Failed to download {description} after {self.MAX_RETRIES} attempts: "
            f"{last_error}",
        )

    def _make_request(self, url: str, timeout: int) -> requests.Response:
        """
        Make HTTP GET request.

        Thread-safety: When self._session is None (default), a new
        requests.Session is created per call, making this method safe
        for concurrent use from multiple threads. If a shared session
        is provided via constructor, callers must ensure thread-safety
        of that session externally.
        """
        session = self._session or requests.Session()
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """
        Save HTTP response to file atomically.

        Uses a unique temp filename per process/thread to prevent
        collisions when multiple threads download concurrently.
        """
        thread_id = threading.current_thread().ident
        temp_suffix = f"{output_path.suffix}.{os.getpid()}_{thread_id}.tmp"
        temp_path = output_path.with_suffix(temp_suffix)

        try:
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            temp_path.rename(output_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_supported_formats(self) -> list[str]:
        """Return list of supported WCS formats."""
        return list(self.WCS_FORMATS.keys())

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

    def get_file_extension(self, format: str) -> str:
        """Get file extension for given format."""
        if format not in self.FORMAT_EXTENSIONS:
            raise ValueError(f"Unknown format: {format}")
        return self.FORMAT_EXTENSIONS[format]

    def validate_godlo(self, godlo: str) -> bool:
        """Validate godło format."""
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.exceptions import ParseError

        try:
            SheetParser(godlo)
            return True
        except ParseError:
            return False

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
