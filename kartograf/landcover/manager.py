"""
Land Cover download manager.

This module provides the LandCoverManager class for coordinating
downloads of land cover data from multiple providers.

Supports parallel batch downloads via ThreadPoolExecutor.
"""

import concurrent.futures
import logging
from pathlib import Path

from kartograf.core.sheet_parser import BBox
from kartograf.download.storage import FileStorage
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider

logger = logging.getLogger(__name__)


# Registry of available providers
PROVIDERS = {
    "bdot10k": Bdot10kProvider,
    "corine": CorineProvider,
    "soilgrids": SoilGridsProvider,
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
        Provider instance or name ("bdot10k", "corine", "soilgrids").
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
        output_dir: str | Path = "./data/landcover",
        provider: LandCoverProvider | str | None = None,
    ):
        """
        Initialize LandCoverManager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Directory for downloaded files. It is not created here: the
            directory appears only when a download writes its first file.
        provider : LandCoverProvider or str, optional
            Provider instance or name
        """
        self._output_dir = Path(output_dir)
        self._storage = FileStorage(output_dir)

        # Initialize provider
        self._provider: LandCoverProvider
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
            Provider name ("bdot10k", "corine", "soilgrids")

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

    def set_provider(self, provider: LandCoverProvider | str) -> None:
        """
        Set the active provider.

        Parameters
        ----------
        provider : LandCoverProvider or str
            Provider instance or name ("bdot10k", "corine", "soilgrids")
        """
        if isinstance(provider, str):
            self._provider = self._get_provider_by_name(provider)
        else:
            self._provider = provider
        logger.info(f"Provider set to: {self._provider.name}")

    def download(
        self,
        teryt: str | None = None,
        bbox: BBox | None = None,
        godlo: str | None = None,
        output_path: Path | None = None,
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
            path = self._provider.download_by_teryt(teryt, output_path, **kwargs)
            self._write_sidecar(path, {"teryt": teryt}, kwargs)
            return path
        elif bbox is not None:
            path = self._provider.download_by_bbox(bbox, output_path, **kwargs)
            self._write_sidecar(
                path,
                {
                    "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                    "bbox_crs": bbox.crs,
                },
                kwargs,
            )
            return path
        elif godlo is not None:
            path = self._provider.download_by_godlo(godlo, output_path, **kwargs)
            self._write_sidecar(path, {"sheet": godlo}, kwargs)
            return path
        # Unreachable after the validation above; keeps godlo narrowed to str.
        raise ValueError("Must provide one of: teryt, bbox, or godlo")

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a TERYT code.

        Parameters
        ----------
        teryt : str
            TERYT code (4-digit for powiat)
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            output_path = self._generate_output_path(teryt, None, None)
        path = self._provider.download_by_teryt(teryt, output_path, **kwargs)
        self._write_sidecar(path, {"teryt": teryt}, kwargs)
        return path

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a bounding box.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            output_path = self._generate_output_path(None, bbox, None)
        path = self._provider.download_by_bbox(bbox, output_path, **kwargs)
        self._write_sidecar(
            path,
            {
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
            kwargs,
        )
        return path

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a map sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        if output_path is None:
            output_path = self._generate_output_path(None, None, godlo)
        path = self._provider.download_by_godlo(godlo, output_path, **kwargs)
        self._write_sidecar(path, {"sheet": godlo}, kwargs)
        return path

    def download_batch(
        self,
        items: list[dict],
        max_workers: int = 4,
        **kwargs,
    ) -> list[Path]:
        """
        Download land cover data for multiple items in parallel.

        Each item dict should contain exactly one of: teryt, bbox, godlo.

        Parameters
        ----------
        items : list[dict]
            List of download items, each with one of:
            - {"teryt": "1465"}
            - {"bbox": BBox(...)}
            - {"godlo": "N-34-130-D"}
        max_workers : int, optional
            Maximum number of parallel download threads (default: 4).
            When <= 1, downloads sequentially.
        **kwargs
            Additional provider-specific options passed to each download.

        Returns
        -------
        list[Path]
            List of paths to successfully downloaded files.
            Failed items are logged but do not stop the batch.

        Examples
        --------
        >>> manager = LandCoverManager()
        >>> items = [
        ...     {"teryt": "1465"},
        ...     {"teryt": "1261"},
        ...     {"godlo": "N-34-130-D"},
        ... ]
        >>> paths = manager.download_batch(items, max_workers=2)
        """
        if not items:
            return []

        def _download_single(item: dict) -> Path | None:
            """Download a single item, returning path or None on failure."""
            try:
                return self.download(**item, **kwargs)
            except Exception as e:
                item_desc = str(item)
                logger.error(f"Batch download failed for {item_desc}: {e}")
                return None

        results: list[Path] = []

        if max_workers <= 1:
            # Sequential
            for item in items:
                path = _download_single(item)
                if path is not None:
                    results.append(path)
        else:
            # Parallel
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = {
                    executor.submit(_download_single, item): item for item in items
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        path = future.result()
                        if path is not None:
                            results.append(path)
                    except Exception as e:
                        item_desc = str(futures[future])
                        logger.error(
                            f"Unexpected error in batch download for {item_desc}: {e}"
                        )

        logger.info(f"Batch download complete: {len(results)}/{len(items)} successful")
        return results

    def _generate_output_path(
        self,
        teryt: str | None,
        bbox: BBox | None,
        godlo: str | None,
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

    def _write_sidecar(
        self, data_path: Path, request: dict, kwargs: dict | None = None
    ) -> None:
        """Best-effort zapis sidecara .meta.json (``emit_sidecar``, D7)."""
        from kartograf.sources.sidecar import emit_sidecar

        horizontal_crs = None
        extra = None
        # CORINE bez credentials CLMS spada na podglad PNG z WMS — inny CRS
        # niz deklarowany dla kanalu CLMS GeoTIFF (EPSG:3035).
        is_png = data_path.suffix.lower() == ".png"
        key = getattr(self._provider, "descriptor_key", None)
        if is_png and key == "eu.clms.corine":
            year = (kwargs or {}).get("year", 2018)
            # 1990 to jedyny rocznik DLR (WMS DLR, EPSG:4326); pozostale
            # ida przez EEA Discomap (EPSG:3857) - patrz CorineProvider.EEA_YEARS.
            horizontal_crs = (
                "EPSG:4326" if year not in CorineProvider.EEA_YEARS else "EPSG:3857"
            )
            extra = {"fallback": "wms_png", "note": "podglad WMS, nie dane"}
        emit_sidecar(
            key,
            data_path,
            request=request,
            vertical_crs=getattr(self._provider, "vertical_crs", None),
            horizontal_crs=horizontal_crs,
            extra=extra,
        )

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
