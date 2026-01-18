"""
Land Cover download manager.

This module provides the LandCoverManager class for coordinating
downloads of land cover data from multiple providers.
"""

import logging
from pathlib import Path
from typing import Optional, Union

from kartograf.core.sheet_parser import BBox
from kartograf.download.storage import FileStorage
from kartograf.providers.bdot10k import Bdot10kProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.landcover_base import LandCoverProvider

logger = logging.getLogger(__name__)


# Registry of available providers
PROVIDERS = {
    "bdot10k": Bdot10kProvider,
    "corine": CorineProvider,
}


class LandCoverManager:
    """
    Manager for downloading land cover data.

    Coordinates downloads from multiple land cover providers,
    handles file storage, and provides a unified interface
    for downloading by TERYT, bbox, or godło.

    Parameters
    ----------
    output_dir : str or Path, optional
        Directory for downloaded files (default: "./data/landcover")
    provider : LandCoverProvider or str, optional
        Provider instance or name ("bdot10k", "corine").
        Default: Bdot10kProvider

    Examples
    --------
    >>> manager = LandCoverManager()
    >>>
    >>> # Download by TERYT (BDOT10k)
    >>> manager.download(teryt="1465")
    >>>
    >>> # Download by godło
    >>> manager.download(godlo="N-34-130-D")
    >>>
    >>> # Download CORINE data
    >>> manager.set_provider("corine")
    >>> manager.download(godlo="N-34-130-D", year=2018)
    >>>
    >>> # Download by bbox
    >>> from kartograf import BBox
    >>> bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
    >>> manager.download(bbox=bbox)
    """

    def __init__(
        self,
        output_dir: Union[str, Path] = "./data/landcover",
        provider: Optional[Union[LandCoverProvider, str]] = None,
    ):
        """
        Initialize LandCoverManager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Directory for downloaded files
        provider : LandCoverProvider or str, optional
            Provider instance or name
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._storage = FileStorage(output_dir)

        # Initialize provider
        if provider is None:
            self._provider = Bdot10kProvider()
        elif isinstance(provider, str):
            self._provider = self._get_provider_by_name(provider)
        else:
            self._provider = provider

    def _get_provider_by_name(self, name: str) -> LandCoverProvider:
        """
        Get provider instance by name.

        Parameters
        ----------
        name : str
            Provider name ("bdot10k", "corine")

        Returns
        -------
        LandCoverProvider
            Provider instance

        Raises
        ------
        ValueError
            If provider name is unknown
        """
        name_lower = name.lower()
        if name_lower not in PROVIDERS:
            raise ValueError(
                f"Unknown provider: {name}. "
                f"Available providers: {list(PROVIDERS.keys())}"
            )
        return PROVIDERS[name_lower]()

    @property
    def provider(self) -> LandCoverProvider:
        """Return current provider."""
        return self._provider

    @property
    def provider_name(self) -> str:
        """Return current provider name."""
        return self._provider.name

    def set_provider(self, provider: Union[LandCoverProvider, str]) -> None:
        """
        Set the active provider.

        Parameters
        ----------
        provider : LandCoverProvider or str
            Provider instance or name ("bdot10k", "corine")
        """
        if isinstance(provider, str):
            self._provider = self._get_provider_by_name(provider)
        else:
            self._provider = provider
        logger.info(f"Provider set to: {self._provider.name}")

    def download(
        self,
        teryt: Optional[str] = None,
        bbox: Optional[BBox] = None,
        godlo: Optional[str] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data.

        Exactly one of teryt, bbox, or godlo must be provided.

        Parameters
        ----------
        teryt : str, optional
            TERYT code (4-digit for powiat)
        bbox : BBox, optional
            Bounding box in EPSG:2180
        godlo : str, optional
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path, optional
            Custom output path. If not provided, auto-generated.
        **kwargs
            Additional provider-specific options (e.g., year, layers)

        Returns
        -------
        Path
            Path to downloaded file

        Raises
        ------
        ValueError
            If none or multiple selection methods provided
        """
        # Validate exactly one selection method
        methods = [teryt, bbox, godlo]
        provided = [m for m in methods if m is not None]

        if len(provided) == 0:
            raise ValueError("Must provide one of: teryt, bbox, or godlo")
        if len(provided) > 1:
            raise ValueError("Provide only one of: teryt, bbox, or godlo")

        # Generate output path if not provided
        if output_path is None:
            output_path = self._generate_output_path(teryt, bbox, godlo)

        # Dispatch to appropriate download method
        if teryt is not None:
            return self._provider.download_by_teryt(teryt, output_path, **kwargs)
        elif bbox is not None:
            return self._provider.download_by_bbox(bbox, output_path, **kwargs)
        else:
            return self._provider.download_by_godlo(godlo, output_path, **kwargs)

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a TERYT code.

        Parameters
        ----------
        teryt : str
            TERYT code (4-digit for powiat)
        output_path : Path, optional
            Custom output path
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            output_path = self._output_dir / f"{self._provider.name}_{teryt}.gpkg"
        return self._provider.download_by_teryt(teryt, output_path, **kwargs)

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a bounding box.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        output_path : Path, optional
            Custom output path
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            bbox_str = (
                f"{bbox.min_x:.0f}_{bbox.min_y:.0f}_{bbox.max_x:.0f}_{bbox.max_y:.0f}"
            )
            output_path = (
                self._output_dir / f"{self._provider.name}_bbox_{bbox_str}.gpkg"
            )
        return self._provider.download_by_bbox(bbox, output_path, **kwargs)

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a map sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path, optional
            Custom output path
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            output_path = self._output_dir / f"{self._provider.name}_{godlo}.gpkg"
        return self._provider.download_by_godlo(godlo, output_path, **kwargs)

    def _generate_output_path(
        self,
        teryt: Optional[str],
        bbox: Optional[BBox],
        godlo: Optional[str],
    ) -> Path:
        """Generate output path based on selection method."""
        provider_prefix = self._provider.name.lower().replace(" ", "_")

        if teryt:
            filename = f"{provider_prefix}_teryt_{teryt}.gpkg"
        elif bbox:
            bbox_str = (
                f"{bbox.min_x:.0f}_{bbox.min_y:.0f}_{bbox.max_x:.0f}_{bbox.max_y:.0f}"
            )
            filename = f"{provider_prefix}_bbox_{bbox_str}.gpkg"
        else:
            filename = f"{provider_prefix}_godlo_{godlo}.gpkg"

        return self._output_dir / filename

    # =========================================================================
    # Info methods
    # =========================================================================

    @staticmethod
    def get_available_providers() -> list[str]:
        """Return list of available provider names."""
        return list(PROVIDERS.keys())

    def get_available_layers(self) -> list[str]:
        """Return available layers from current provider."""
        return self._provider.get_available_layers()

    def get_supported_formats(self) -> list[str]:
        """Return supported formats from current provider."""
        return self._provider.get_supported_formats()

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"LandCoverManager("
            f"provider={self._provider.name!r}, "
            f"output_dir={self._output_dir!r})"
        )
