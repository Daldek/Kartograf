"""
GUGiK provider for downloading Orthophotomap data.

This module provides the GugikOrtoProvider class for downloading
orthophoto (aerial imagery) data from the Polish GUGiK services.

Standard Resolution orthophotos (25cm) are available as GeoTIFF
via WMS skorowidze → OpenData and WCS.

Unlike NMT/NMPT, orthophotos:
- Have no vertical CRS (2D RGB imagery)
- Use a single WMS endpoint (no KRON86/EVRF2007 split)
- Download as TIF (not ASC)
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


class GugikOrtoProvider(BaseProvider):
    """
    Provider for downloading Orthophotomap data from GUGiK.

    Supports two download modes:
    - By godło (map sheet ID): downloads from OpenData as TIF
    - By bbox (bounding box): downloads from WCS as GeoTIFF

    Examples
    --------
    >>> provider = GugikOrtoProvider()
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))
    >>>
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_bbox(bbox, Path("./area.tif"))
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    WCS_ENDPOINT = f"{BASE_URL}/wss/service/PZGIK/ORTO/WCS/StandardResolution"
    COVERAGE_ID = "Orthoimagery_StandardResolution"

    WMS_SKOROWIDZE_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/ORTO/WMS/SkorowidzeWgAktualnosci"
    )

    WMS_LAYERS = [
        "SkorowidzeOrtofotomapy2025",
        "SkorowidzeOrtofotomapy2024",
        "SkorowidzeOrtofotomapy2023",
        "SkorowidzeOrtofotomapy2022",
        "SkorowidzeOrtofotomapy2021",
        "SkorowidzeOrtofotomapy2020",
        "SkorowidzeOrtofotomapy2019",
        "SkorowidzeOrtofotomapy2018",
        "SkorowidzeOrtofotomapyStarsze",
    ]

    # OpenData URL pattern in WMS GetFeatureInfo response
    OPENDATA_URL_PATTERN = re.compile(r'url:"(https://[^"]+)"')

    # WCS formats
    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    # Settings
    DEFAULT_TIMEOUT = 60  # Ortofoto files are larger
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2

    def __init__(self, session: requests.Session | None = None):
        """
        Initialize GUGiK Ortofotomapa provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        """
        self._session = session

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK Ortofotomapa"

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    @property
    def default_extension(self) -> str:
        """Return default file extension for orthophoto data."""
        return ".tif"

    # =========================================================================
    # Download by godło → OpenData (TIF)
    # =========================================================================

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a map sheet (godło) from OpenData.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Path where the TIF file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails or no file is found
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        opendata_url = self._get_opendata_url(godlo, timeout)

        return self._download_with_retry(
            url=opendata_url,
            output_path=output_path,
            timeout=timeout,
            description=f"{godlo} (Ortofoto OpenData)",
        )

    def _get_opendata_url(
        self,
        godlo: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """
        Get OpenData URL for orthophoto file using WMS GetFeatureInfo.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        timeout : int, optional
            Request timeout in seconds

        Returns
        -------
        str
            OpenData URL for the file

        Raises
        ------
        DownloadError
            If no file is found
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")

        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2

        buffer = 10
        query_bbox = (
            f"{center_y - buffer},{center_x - buffer},"
            f"{center_y + buffer},{center_x + buffer}"
        )

        session = self._session or requests.Session()

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
                logger.debug(f"Querying WMS for ortofoto {godlo} on layer {layer}")

                response = session.get(url, timeout=timeout)
                response.raise_for_status()

                urls = self.OPENDATA_URL_PATTERN.findall(response.text)

                if urls:
                    for found_url in urls:
                        if godlo in found_url:
                            logger.debug(f"Found OpenData URL: {found_url}")
                            return found_url

                    logger.debug(f"Found OpenData URL (no exact match): {urls[0]}")
                    return urls[0]

            except requests.RequestException as e:
                logger.warning(f"WMS query failed for layer {layer}: {e}")
                continue

        raise DownloadError(
            f"No orthophoto data available for {godlo}. "
            f"This area may not have orthophoto coverage in GUGiK. "
            f"Check https://mapy.geoportal.gov.pl for data availability.",
            godlo=godlo,
        )

    # =========================================================================
    # Download by bbox → WCS (GeoTIFF)
    # =========================================================================

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a bounding box from WCS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")
        timeout : int, optional
            Request timeout in seconds (default: 60)

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
                f"ortofoto bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """Construct WCS GetCoverage URL."""
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
        """Download file with automatic retry on failure."""
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
            f"Failed to download {description} after "
            f"{self.MAX_RETRIES} attempts: {last_error}",
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

    def validate_godlo(self, godlo: str) -> bool:
        """Validate godło format."""
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.exceptions import ParseError

        try:
            SheetParser(godlo)
            return True
        except ParseError:
            return False
