"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) services.

Two download methods based on input type:
- Godło (map sheet ID) → OpenData (ASC format)
- BBox (bounding box) → WCS (GeoTIFF/PNG/JPEG formats)
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
    """

    # Base URL for GUGiK services
    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WCS endpoint for NMT data
    WCS_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
    )

    # WMS endpoint for skorowidze (index maps) - used to find OpenData URLs
    WMS_SKOROWIDZE_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladKRON86"
    )

    # Layers to query for ASC files (ordered from newest to oldest)
    WMS_LAYERS = [
        "SkorowidzeNMT2019",
        "SkorowidzeNMT2018",
        "SkorowidzeNMT2017iStarsze",
    ]

    # Coverage ID for WCS - single coverage for all of Poland
    COVERAGE_ID = "DTM_PL-KRON86-NH_TIFF"

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

    def __init__(self, session: requests.Session | None = None):
        """
        Initialize GUGiK provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        """
        self._session = session

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

        # Try each layer from newest to oldest
        for layer in self.WMS_LAYERS:
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
                url = f"{self.WMS_SKOROWIDZE_ENDPOINT}?{urlencode(params)}"
                logger.debug(f"Querying WMS for {godlo} on layer {layer}")

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
            f"No ASC file found for {godlo} in any WMS layer",
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
            If format is not supported or bbox CRS is not EPSG:2180

        Examples
        --------
        >>> provider = GugikProvider()
        >>> bbox = BBox(
        ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        ... )
        >>> path = provider.download_bbox(bbox, Path("./area.tif"))
        """
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
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": self.COVERAGE_ID,
            "FORMAT": self.WCS_FORMATS[format],
        }

        base_url = f"{self.WCS_ENDPOINT}?{urlencode(params)}"
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
