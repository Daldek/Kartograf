"""
Base provider class for data download services.

This module defines the abstract base class for all data providers
in Kartograf. Providers are responsible for downloading NMT data
from specific services.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from kartograf.core.sheet_parser import BBox


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    All data providers must inherit from this class and implement
    the required abstract methods.

    Providers support two download modes:
    - By godło (map sheet ID): returns data in provider's native format
    - By bbox (bounding box): returns data in specified format (optional)

    Attributes
    ----------
    name : str
        Human-readable name of the provider
    base_url : str
        Base URL for the provider's API/service

    Examples
    --------
    >>> class MyProvider(BaseProvider):
    ...     @property
    ...     def name(self) -> str:
    ...         return "My Provider"
    ...
    ...     @property
    ...     def base_url(self) -> str:
    ...         return "https://example.com/api"
    ...
    ...     def download(self, godlo: str, output_path: Path) -> Path:
    ...         # Implementation
    ...         pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return human-readable name of the provider.

        Returns
        -------
        str
            Provider name (e.g., "GUGiK", "OpenTopography")
        """
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """
        Return base URL for the provider's service.

        Returns
        -------
        str
            Base URL (e.g., "https://mapy.geoportal.gov.pl")
        """
        pass

    @abstractmethod
    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = 30,
    ) -> Path:
        """
        Download data for given map sheet (godło).

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Path where the file should be saved
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
        """
        pass

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = 30,
    ) -> Path:
        """
        Download data for a bounding box.

        Optional method - not all providers support bbox downloads.

        Parameters
        ----------
        bbox : BBox
            Bounding box defining the area to download
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
        NotImplementedError
            If the provider doesn't support bbox downloads
        DownloadError
            If the download fails
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support bbox downloads"
        )

    def get_supported_formats(self) -> list[str]:
        """
        Return list of supported output formats for bbox downloads.

        Returns
        -------
        list[str]
            List of format identifiers (e.g., ["GTiff", "PNG", "JPEG"])
        """
        return ["GTiff"]

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
        """
        extensions = {
            "GTiff": ".tif",
            "PNG": ".png",
            "JPEG": ".jpg",
            "ASC": ".asc",
        }
        if format not in extensions:
            raise ValueError(f"Unknown format: {format}")
        return extensions[format]

    def validate_godlo(self, godlo: str) -> bool:
        """
        Validate that godło is in correct format for this provider.

        Parameters
        ----------
        godlo : str
            Map sheet identifier to validate

        Returns
        -------
        bool
            True if godło is valid, False otherwise
        """
        return True

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}(base_url='{self.base_url}')"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.name} ({self.base_url})"
