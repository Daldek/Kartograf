"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) services.

Two download methods based on input type:
- Godło (map sheet ID) → OpenData (ASC format)
- BBox (bounding box) → WCS (GeoTIFF/PNG/JPEG formats)

Supported resolutions:
- 1m (GRID1) - available for EVRF2007 and KRON86
- 5m (GRID5) - available only for EVRF2007
"""

import logging
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GugikProvider(BaseProvider):
    """
    Provider for downloading NMT data from GUGiK.

    Supports two download modes:
    - By godło (map sheet ID): downloads from OpenData as ASC
    - By bbox (bounding box): downloads from WCS as GeoTIFF/PNG/JPEG

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
    >>> # Download by bbox → GeoTIFF from WCS
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

    # WCS endpoints for NMT data (by vertical CRS) - only 1m resolution
    # Note: 5m resolution is NOT available via WCS
    WCS_ENDPOINTS = {
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
        "DigitalTerrainModelFormatTIFF",
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
                "SkorowidzeNMT2025",
                "SkorowidzeNMT2024",
                "SkorowidzeNMT2023",
                "SkorowidzeNMT2022iStarsze",
            ],
        },
        "5m": {
            # 5m layers (only EVRF2007)
            "EVRF2007": [
                "SkorowidzeNMT2024",
                "SkorowidzeNMT2023",
                "SkorowidzeNMT2022",
                "SkorowidzeNMT2021iStarsze",
            ],
        },
    }

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

    def __init__(
        self,
        session: requests.Session | None = None,
        vertical_crs: str = "EVRF2007",
        resolution: str = "1m",
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
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

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
        DownloadError
            If the download fails or no ASC file is found

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
        DownloadError
            If no ASC file is found
        """
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

        resolution_layers = self.WMS_LAYERS.get(self._resolution, {})
        wms_layers = resolution_layers.get(self._vertical_crs, [])

        if not wms_layers:
            raise DownloadError(
                f"No WMS layers configured for resolution={self._resolution}, "
                f"vertical_crs={self._vertical_crs}.",
                godlo=godlo,
            )

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

                # Parse HTML for OpenData URL pattern
                urls = re.findall(
                    r'url:"(https://opendata[^"]+\.asc)"',
                    response.text,
                )

                if urls:
                    # Prefer URL containing our godło
                    for found_url in urls:
                        if godlo in found_url:
                            logger.debug(f"Found OpenData URL: {found_url}")
                            return found_url

                    # Fallback to first found URL
                    logger.debug(f"Found OpenData URL (no exact match): {urls[0]}")
                    return urls[0]

            except requests.RequestException as e:
                logger.warning(f"WMS query failed for layer {layer}: {e}")
                continue

        raise DownloadError(
            f"No ASC file found for {godlo} in any WMS layer "
            f"(resolution={self._resolution}, vertical_crs={self._vertical_crs})",
            godlo=godlo,
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

        Examples
        --------
        >>> provider = GugikProvider()
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
        """Make HTTP GET request."""
        session = self._session or requests.Session()
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """Save HTTP response to file atomically."""
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

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

        WCS is only available for 1m resolution.

        Returns
        -------
        bool
            True if WCS is available, False otherwise.
        """
        return self._resolution == "1m"
