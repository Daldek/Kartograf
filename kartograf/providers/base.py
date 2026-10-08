"""
Base provider classes for data download services.

DataSourceProvider — common root of all providers (name, URL,
binding to the source registry via descriptor_key).
BaseProvider — rasters/sheets (NMT/NMPT/Orto/LAZ), as before.
LandCoverProvider — land cover (BDOT10k/CORINE/SoilGrids); moved
from landcover_base.py (removed without a shim, stage 0 spec 6.7).
"""

from abc import ABC, abstractmethod
from pathlib import Path

from kartograf.core.sheet_parser import BBox


class DataSourceProvider(ABC):
    """Common root of data source providers."""

    #: Descriptor key in kartograf.sources.registry (None = unbound).
    descriptor_key: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable name of the provider."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return base URL for the provider's service."""


class BaseProvider(DataSourceProvider):
    """
    Abstract base class for data providers.

    All data providers must inherit from this class and implement
    the required abstract methods.

    Providers support two download modes:
    - By sheet code (godlo): returns data in provider's native format
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
    def default_extension(self) -> str:
        """Default file extension for this provider (e.g. '.asc', '.tif')."""
        return ".asc"

    @property
    def storage_variant(self) -> str | None:
        """Product variant in the storage segment.

        Segment form: ``<country>_<crs>_<variant>``. ``None`` = default
        variant, no suffix (ADR-026). A provider that can deliver a
        different file under the same sheet code (CIR/B-W orto) returns the
        variant name here — otherwise a skip would silently return a file of
        another variant (E12).
        """
        return None

    def source_info(self, godlo: str) -> dict | None:
        """Origin of the downloaded sheet, if the provider exposes it."""
        return None

    @abstractmethod
    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = 30,
    ) -> Path:
        """
        Download data for given map sheet (godlo).

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
        Validate that godlo is in correct format for this provider.

        Parameters
        ----------
        godlo : str
            Map sheet identifier to validate

        Returns
        -------
        bool
            True if godlo is valid, False otherwise
        """
        return True

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}(base_url='{self.base_url}')"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.name} ({self.base_url})"


class LandCoverProvider(DataSourceProvider):
    """
    Abstract base class for land cover data providers.

    All land cover providers must inherit from this class and implement
    the required abstract methods. Providers support three download modes:
    - By TERYT code (administrative unit)
    - By bbox (bounding box)
    - By godlo (map sheet ID)
    Attributes
    ----------
    name : str
        Human-readable name of the provider
    base_url : str
        URL of the data source for reference

    Examples
    --------
    >>> class MyLandCoverProvider(LandCoverProvider):
    ...     @property
    ...     def name(self) -> str:
    ...         return "My Land Cover Provider"
    ...
    ...     @property
    ...     def base_url(self) -> str:
    ...         return "https://example.com/landcover"
    ...
    ...     def download_by_bbox(self, bbox, output_path):
    ...         # Implementation
    ...         pass
    """

    @property
    def source_url(self) -> str:
        """Deprecated alias for base_url (kept for backward compatibility)."""
        return self.base_url

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

    def download_by_admin_unit(
        self,
        code: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """Download data for an administrative unit (canonical name).

        For PL the unit code is TERYT. Unsupported by default.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support TERYT downloads"
        )

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """Deprecated alias for download_by_admin_unit."""
        return self.download_by_admin_unit(
            teryt, output_path, timeout=timeout, **kwargs
        )

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = 60,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a map sheet (godlo).

        Converts godlo to bbox and calls download_by_bbox.

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
            If godlo format is invalid
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
            List of format identifiers (e.g., ["GPKG", "SHP"])
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
            "GEOJSON": ".geojson",
            "GTiff": ".tif",
        }
        if format not in extensions:
            raise ValueError(f"Unknown format: {format}")
        return extensions[format]

    def validate_admin_unit(self, code: str) -> bool:
        """Validate administrative-unit code (canonical name).

        PL: TERYT — 4 digits (powiat) or 7 digits (gmina).
        """
        if not code or not code.isdigit():
            return False
        # Powiat: 4 digits, Gmina: 7 digits
        return len(code) in (4, 7)

    def validate_teryt(self, teryt: str) -> bool:
        """Deprecated alias for validate_admin_unit."""
        return self.validate_admin_unit(teryt)

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}()"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self.name} ({self.source_url})"
