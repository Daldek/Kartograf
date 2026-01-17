"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) WCS service.
"""

import logging
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.exceptions import DownloadError
from kartograf.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GugikProvider(BaseProvider):
    """
    Provider for downloading NMT data from GUGiK.

    This provider connects to the GUGiK WCS (Web Coverage Service)
    to download Digital Terrain Model data for Polish topographic
    map sheets.

    Attributes
    ----------
    SUPPORTED_FORMATS : dict
        Mapping of format names to WCS format identifiers

    Examples
    --------
    >>> provider = GugikProvider()
    >>> url = provider.construct_url("N-34-130-D-d-2-4", format="GTiff")
    >>> provider.download("N-34-130-D-d-2-4", Path("./data/sheet.tif"))

    Notes
    -----
    The GUGiK WCS service requires specific parameters for accessing
    NMT data. This provider handles the URL construction automatically.
    """

    # Base URL for GUGiK WCS service
    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WCS endpoint for NMT GeoTIFF data
    WCS_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
    )

    # Supported output formats with their MIME types
    SUPPORTED_FORMATS = {
        "GTiff": "image/tiff",
        "AAIGrid": "application/x-ogc-aaigrid",
        "XYZ": "text/plain",
    }

    # File extensions for formats
    FORMAT_EXTENSIONS = {
        "GTiff": ".tif",
        "AAIGrid": ".asc",
        "XYZ": ".xyz",
    }

    # Default settings
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2  # Exponential backoff base (2, 4, 8 seconds)

    def __init__(self, session: requests.Session | None = None):
        """
        Initialize GUGiK provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests. If None, a new session
            will be created for each download.
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

    def construct_url(
        self,
        godlo: str,
        format: str = "GTiff",
    ) -> str:
        """
        Construct WCS download URL for given sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        format : str, optional
            Output format: "GTiff", "AAIGrid", or "XYZ" (default: "GTiff")

        Returns
        -------
        str
            Full WCS URL for downloading the data

        Raises
        ------
        ValueError
            If the format is not supported

        Examples
        --------
        >>> provider = GugikProvider()
        >>> url = provider.construct_url("N-34-130-D-d-2-4")
        >>> "N-34-130-D-d-2-4" in url
        True
        """
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: '{format}'. "
                f"Supported formats: {list(self.SUPPORTED_FORMATS.keys())}"
            )

        # Normalize godło using SheetParser
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        normalized_godlo = parser.godlo

        # Build WCS GetCoverage request parameters
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": normalized_godlo,
            "FORMAT": self.SUPPORTED_FORMATS[format],
        }

        return f"{self.WCS_ENDPOINT}?{urlencode(params)}"

    def download(
        self,
        godlo: str,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for given sheet.

        Downloads data with automatic retry on failure using exponential backoff.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format (default: "GTiff")
        timeout : int, optional
            Request timeout in seconds (default: 30)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails after all retry attempts
        ValueError
            If the format is not supported

        Examples
        --------
        >>> provider = GugikProvider()
        >>> path = provider.download("N-34-130-D-d-2-4", Path("./data/sheet.tif"))
        """
        url = self.construct_url(godlo, format)

        # Ensure parent directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {godlo} (attempt {attempt}/{self.MAX_RETRIES})"
                )

                response = self._make_request(url, timeout)
                self._save_response(response, output_path)

                logger.info(f"Successfully downloaded {godlo} to {output_path}")
                return output_path

            except requests.RequestException as e:
                last_error = e
                logger.warning(f"Download failed for {godlo} (attempt {attempt}): {e}")

                if attempt < self.MAX_RETRIES:
                    wait_time = self.RETRY_BACKOFF_BASE**attempt
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        # All retries exhausted
        raise DownloadError(
            f"Failed to download {godlo} after {self.MAX_RETRIES} attempts: "
            f"{last_error}",
            godlo=godlo,
        )

    def _make_request(
        self,
        url: str,
        timeout: int,
    ) -> requests.Response:
        """
        Make HTTP GET request with error handling.

        Parameters
        ----------
        url : str
            URL to request
        timeout : int
            Request timeout in seconds

        Returns
        -------
        requests.Response
            HTTP response object

        Raises
        ------
        requests.RequestException
            If the request fails
        """
        session = self._session or requests.Session()

        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        return response

    def _save_response(
        self,
        response: requests.Response,
        output_path: Path,
    ) -> None:
        """
        Save HTTP response content to file atomically.

        Uses a temporary file and atomic rename to prevent partial downloads.

        Parameters
        ----------
        response : requests.Response
            HTTP response with content to save
        output_path : Path
            Target path for the file
        """
        # Write to temporary file first
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        try:
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Atomic rename
            temp_path.rename(output_path)

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return list(self.SUPPORTED_FORMATS.keys())

    def get_file_extension(self, format: str) -> str:
        """
        Get file extension for given format.

        Parameters
        ----------
        format : str
            Output format name

        Returns
        -------
        str
            File extension including dot (e.g., ".tif")

        Raises
        ------
        ValueError
            If format is not supported
        """
        if format not in self.FORMAT_EXTENSIONS:
            raise ValueError(f"Unknown format: {format}")
        return self.FORMAT_EXTENSIONS[format]

    def validate_godlo(self, godlo: str) -> bool:
        """
        Validate godlo format for GUGiK service.

        Parameters
        ----------
        godlo : str
            Map sheet identifier to validate

        Returns
        -------
        bool
            True if godlo is valid for GUGiK service
        """
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.exceptions import ParseError

        try:
            SheetParser(godlo)
            return True
        except ParseError:
            return False
