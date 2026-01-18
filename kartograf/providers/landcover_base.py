"""
Base provider class for land cover data download services.

This module defines the abstract base class for land cover providers
in Kartograf. Providers download land cover data from sources like
BDOT10k (GUGiK) or CORINE Land Cover (Copernicus).
"""

from abc import ABC, abstractmethod
from pathlib import Path

from kartograf.core.sheet_parser import BBox


class LandCoverProvider(ABC):
    """
    Abstract base class for land cover data providers.

    All land cover providers must inherit from this class and implement
    the required abstract methods. Providers support three download modes:
    - By TERYT code (administrative unit)
    - By bbox (bounding box)
    - By godło (map sheet ID)

    Attributes
    ----------
    name : str
        Human-readable name of the provider
    source_url : str
        URL of the data source for reference

    Examples
    --------
    >>> class MyLandCoverProvider(LandCoverProvider):
    ...     @property
    ...     def name(self) -> str:
    ...         return "My Land Cover Provider"
    ...
    ...     @property
    ...     def source_url(self) -> str:
    ...         return "https://example.com/landcover"
    ...
    ...     def download_by_bbox(self, bbox, output_path):
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
            Provider name (e.g., "BDOT10k", "CORINE Land Cover")
        """
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        """
        Return URL of the data source for reference.

        Returns
        -------
        str
            Source URL (e.g., "https://www.geoportal.gov.pl")
        """
        pass

    @abstractmethod
    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = 60,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a bounding box.

        Parameters
        ----------
        bbox : BBox
            Bounding box defining the area to download.
            Must be in EPSG:2180 (PL-1992) for Polish providers.
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        **kwargs
            Provider-specific options (e.g., layers, year)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails after all retry attempts
        ValidationError
            If bbox or parameters are invalid
        """
        pass

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for an administrative unit (TERYT code).

        TERYT is Polish territorial unit identifier system.
        Typically 4-digit code for powiat (county) or 7-digit for gmina (municipality).

        Parameters
        ----------
        teryt : str
            TERYT code (e.g., "1465" for powiat warszawski zachodni)
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120, larger due to file size)
        **kwargs
            Provider-specific options (e.g., format, layers)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        NotImplementedError
            If the provider doesn't support TERYT downloads
        DownloadError
            If the download fails
        ValidationError
            If TERYT code is invalid
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support TERYT downloads"
        )

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = 60,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a map sheet (godło).

        Converts godło to bbox and calls download_by_bbox.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ParseError
            If godło format is invalid
        DownloadError
            If the download fails
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")
        return self.download_by_bbox(bbox, output_path, timeout, **kwargs)

    def get_available_layers(self) -> list[str]:
        """
        Return list of available land cover layers/classes.

        Returns
        -------
        list[str]
            List of layer identifiers (e.g., ["PTLZ", "PTWP"] for BDOT10k)
        """
        return []

    def get_supported_formats(self) -> list[str]:
        """
        Return list of supported output formats.

        Returns
        -------
        list[str]
            List of format identifiers (e.g., ["GPKG", "SHP", "GML"])
        """
        return ["GPKG"]

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
            File extension including dot (e.g., ".gpkg")
        """
        extensions = {
            "GPKG": ".gpkg",
            "SHP": ".shp",
            "GML": ".gml",
            "GEOJSON": ".geojson",
            "GTiff": ".tif",
        }
        if format not in extensions:
            raise ValueError(f"Unknown format: {format}")
        return extensions[format]

    def validate_teryt(self, teryt: str) -> bool:
        """
        Validate TERYT code format.

        Parameters
        ----------
        teryt : str
            TERYT code to validate

        Returns
        -------
        bool
            True if TERYT is valid format, False otherwise
        """
        if not teryt or not teryt.isdigit():
            return False
        # Powiat: 4 digits, Gmina: 7 digits
        return len(teryt) in (4, 7)

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}()"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.name} ({self.source_url})"
