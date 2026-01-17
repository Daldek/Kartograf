"""
GUGiK provider for downloading NMT data.

This module provides the GugikProvider class for downloading
Digital Terrain Model (NMT) data from the Polish GUGiK
(Główny Urząd Geodezji i Kartografii) WCS service.
"""

from pathlib import Path

from kartograf.providers.base import BaseProvider


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
    >>> print(url)
    https://mapy.geoportal.gov.pl/wss/service/...

    Notes
    -----
    The GUGiK WCS service requires specific parameters for accessing
    NMT data. This provider handles the URL construction automatically.
    """

    # Base URL for GUGiK WCS service
    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WCS endpoint for NMT GeoTIFF data
    WCS_GEOTIFF = (
        f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
    )

    # Supported output formats
    SUPPORTED_FORMATS = {
        "GTiff": "image/tiff",
        "AAIGrid": "application/x-ogc-aaigrid",
        "XYZ": "text/plain",
    }

    # Default settings
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3

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

        Notes
        -----
        The actual URL construction will be implemented in Stage 6.
        This is a placeholder implementation.
        """
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: '{format}'. "
                f"Supported formats: {list(self.SUPPORTED_FORMATS.keys())}"
            )

        # TODO: Implement actual URL construction in Stage 6
        # This requires understanding the WCS parameters for GUGiK
        raise NotImplementedError("URL construction will be implemented in Stage 6")

    def download(
        self,
        godlo: str,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download NMT data for given sheet.

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

        Notes
        -----
        The download implementation with retry logic will be added in Stage 6.
        This is a placeholder implementation.
        """
        # TODO: Implement download with retry in Stage 6
        raise NotImplementedError(
            "Download functionality will be implemented in Stage 6"
        )

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return list(self.SUPPORTED_FORMATS.keys())

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
        # Use SheetParser for validation
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.exceptions import ParseError

        try:
            SheetParser(godlo)
            return True
        except ParseError:
            return False
