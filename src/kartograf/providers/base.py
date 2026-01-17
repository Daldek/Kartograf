"""
Base provider class for data download services.

This module defines the abstract base class for all data providers
in Kartograf. Providers are responsible for constructing URLs and
downloading data from specific services.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    All data providers must inherit from this class and implement
    the required abstract methods.

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
    ...     def construct_url(self, godlo: str, format: str) -> str:
    ...         return f"{self.base_url}/data/{godlo}.{format}"
    ...
    ...     def download(self, godlo: str, output_path: Path, format: str) -> Path:
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
    def construct_url(
        self,
        godlo: str,
        format: str = "GTiff",
    ) -> str:
        """
        Construct download URL for given sheet and format.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        format : str, optional
            Output format (default: "GTiff").
            Supported formats depend on the provider.

        Returns
        -------
        str
            Full URL for downloading the data

        Raises
        ------
        ValueError
            If the format is not supported by this provider
        """
        pass

    @abstractmethod
    def download(
        self,
        godlo: str,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = 30,
    ) -> Path:
        """
        Download data for given sheet to specified path.

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
        """
        pass

    def get_supported_formats(self) -> list[str]:
        """
        Return list of supported output formats.

        Returns
        -------
        list[str]
            List of format identifiers (e.g., ["GTiff", "AAIGrid", "XYZ"])

        Notes
        -----
        Subclasses should override this method to return their
        actual supported formats.
        """
        return ["GTiff"]

    def validate_godlo(self, godlo: str) -> bool:
        """
        Validate that godlo is in correct format for this provider.

        Parameters
        ----------
        godlo : str
            Map sheet identifier to validate

        Returns
        -------
        bool
            True if godlo is valid, False otherwise

        Notes
        -----
        Default implementation returns True. Subclasses can override
        to add provider-specific validation.
        """
        return True

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}(base_url='{self.base_url}')"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.name} ({self.base_url})"
