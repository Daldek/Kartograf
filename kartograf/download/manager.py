"""
Download manager for coordinating NMT data downloads.

This module provides the DownloadManager class for downloading
single sheets and entire hierarchies of map sheets.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError
from kartograf.providers.base import BaseProvider
from kartograf.providers.gugik import GugikProvider

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """
    Progress information for download operations.

    Attributes
    ----------
    current : int
        Number of sheets processed so far
    total : int
        Total number of sheets to process
    godlo : str
        Current sheet being processed
    status : str
        Status of current operation ("downloading", "skipped", "completed", "failed")
    message : str
        Optional message with additional details
    """

    current: int
    total: int
    godlo: str
    status: str
    message: str = ""

    @property
    def progress_percent(self) -> float:
        """Return progress as percentage (0-100)."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100


# Type alias for progress callback
ProgressCallback = Callable[[DownloadProgress], None]


class DownloadManager:
    """
    Manages downloading of NMT data sheets.

    Coordinates between the provider (data source), storage (file system),
    and sheet parser to download single sheets or entire hierarchies.

    Two download modes:
    - By godło: downloads ASC files from OpenData
    - By bbox: downloads GeoTIFF from WCS (only 1m resolution)

    Supports vertical CRS:
    - EVRF2007 (default) - European Vertical Reference Frame 2007
    - KRON86 - legacy Kronsztadt 86

    Supports resolutions:
    - 1m (default) - high resolution, available for both EVRF2007 and KRON86
    - 5m - lower resolution, available only for EVRF2007

    Examples
    --------
    >>> manager = DownloadManager(output_dir="./data")
    >>>
    >>> # Download single sheet (ASC)
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    PosixPath('data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc')
    >>>
    >>> # Download hierarchy (ASC)
    >>> manager.download_hierarchy("N-34-130-D", "1:10000")
    >>>
    >>> # Download by bounding box (GeoTIFF) - only 1m resolution
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> manager.download_bbox(bbox, "area.tif")
    >>>
    >>> # Download in legacy KRON86 vertical CRS
    >>> manager = DownloadManager(vertical_crs="KRON86")
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    >>>
    >>> # Download 5m resolution (only EVRF2007)
    >>> manager = DownloadManager(resolution="5m")
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    """

    def __init__(
        self,
        output_dir: str | Path = "./data",
        provider: Optional[BaseProvider] = None,
        storage: Optional[FileStorage] = None,
        vertical_crs: str = "EVRF2007",
        resolution: str = "1m",
    ):
        """
        Initialize download manager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Base directory for downloads (default: "./data")
        provider : BaseProvider, optional
            Data provider (default: GugikProvider with specified settings)
        storage : FileStorage, optional
            Storage manager (default: FileStorage with output_dir)
        vertical_crs : str, optional
            Vertical CRS: "EVRF2007" or "KRON86" (default: "EVRF2007").
            Note: 5m resolution only supports EVRF2007.
        resolution : str, optional
            Grid resolution: "1m" or "5m" (default: "1m").
            Note: 5m is only available for EVRF2007 and does not support
            bbox download (WCS).
        """
        # If resolution is 5m, force EVRF2007
        if resolution == "5m" and vertical_crs != "EVRF2007":
            logger.warning(
                f"Resolution 5m only supports EVRF2007, changing "
                f"vertical_crs from '{vertical_crs}' to 'EVRF2007'"
            )
            vertical_crs = "EVRF2007"

        self._provider = provider or GugikProvider(
            vertical_crs=vertical_crs, resolution=resolution
        )
        self._storage = storage or FileStorage(output_dir, resolution=resolution)
        self._vertical_crs = vertical_crs
        self._resolution = resolution

    @property
    def vertical_crs(self) -> str:
        """Return current vertical CRS."""
        return self._vertical_crs

    @property
    def resolution(self) -> str:
        """Return current resolution."""
        return self._resolution

    @property
    def provider(self) -> BaseProvider:
        """Return the data provider."""
        return self._provider

    @property
    def storage(self) -> FileStorage:
        """Return the storage manager."""
        return self._storage

    # =========================================================================
    # Download by godło → ASC
    # =========================================================================

    def download_sheet(
        self,
        godlo: str,
        skip_existing: bool = True,
    ) -> Path:
        """
        Download a single map sheet as ASC.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        skip_existing : bool, optional
            Skip download if file exists (default: True)

        Returns
        -------
        Path
            Path to the downloaded ASC file

        Raises
        ------
        DownloadError
            If download fails
        ParseError
            If godlo is invalid
        """
        # Get target path (always .asc for godło downloads)
        target_path = self._storage.get_path(godlo, ".asc")

        # Check if already exists
        if skip_existing and target_path.exists():
            logger.info(f"Skipping {godlo} - already exists at {target_path}")
            return target_path

        # Download
        logger.info(f"Downloading {godlo}...")
        self._provider.download(godlo, target_path)

        return target_path

    def download_hierarchy(
        self,
        godlo: str,
        target_scale: str,
        skip_existing: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> list[Path]:
        """
        Download all descendant sheets to target scale as ASC.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier (e.g., "N-34-130-D")
        target_scale : str
            Target scale to download (e.g., "1:10000")
        skip_existing : bool, optional
            Skip download if file exists (default: True)
        on_progress : callable, optional
            Callback function for progress updates.

        Returns
        -------
        list[Path]
            List of paths to downloaded ASC files

        Raises
        ------
        DownloadError
            If any download fails
        ValidationError
            If target_scale is invalid
        ParseError
            If godlo is invalid

        Examples
        --------
        >>> manager = DownloadManager()
        >>> paths = manager.download_hierarchy("N-34-130-D-d", "1:10000")
        >>> len(paths)  # 4 * 4 = 16 sheets
        16
        """
        # Parse starting sheet and get all descendants
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)

        total = len(descendants)
        downloaded_paths = []
        failed_count = 0

        logger.info(
            f"Starting hierarchy download: {godlo} → {target_scale} ({total} sheets)"
        )

        for i, descendant in enumerate(descendants, 1):
            current_godlo = descendant.godlo

            try:
                target_path = self._storage.get_path(current_godlo, ".asc")

                if skip_existing and target_path.exists():
                    # Skipped
                    if on_progress:
                        on_progress(
                            DownloadProgress(
                                current=i,
                                total=total,
                                godlo=current_godlo,
                                status="skipped",
                                message="Already exists",
                            )
                        )
                    downloaded_paths.append(target_path)
                    continue

                # Download
                if on_progress:
                    on_progress(
                        DownloadProgress(
                            current=i,
                            total=total,
                            godlo=current_godlo,
                            status="downloading",
                        )
                    )

                path = self._provider.download(current_godlo, target_path)
                downloaded_paths.append(path)

                if on_progress:
                    on_progress(
                        DownloadProgress(
                            current=i,
                            total=total,
                            godlo=current_godlo,
                            status="completed",
                        )
                    )

            except DownloadError as e:
                failed_count += 1
                logger.error(f"Failed to download {current_godlo}: {e}")

                if on_progress:
                    on_progress(
                        DownloadProgress(
                            current=i,
                            total=total,
                            godlo=current_godlo,
                            status="failed",
                            message=str(e),
                        )
                    )

        logger.info(
            f"Hierarchy download complete: {len(downloaded_paths)}/{total} successful, "
            f"{failed_count} failed"
        )

        return downloaded_paths

    # =========================================================================
    # Download by bbox → GeoTIFF
    # =========================================================================

    def download_bbox(
        self,
        bbox: BBox,
        filename: str,
        format: str = "GTiff",
    ) -> Path:
        """
        Download NMT data for a bounding box as GeoTIFF.

        Use this method when you need data for an arbitrary area
        (not aligned to standard map sheets).

        Note: WCS download is only available for 1m resolution.
        For 5m resolution, use download_sheet() with a godło instead.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        filename : str
            Output filename (will be placed in output_dir)
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If download fails
        ValueError
            If format is not supported, bbox CRS is wrong, or resolution is 5m

        Examples
        --------
        >>> manager = DownloadManager(output_dir="./data")
        >>> bbox = BBox(
        ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        ... )
        >>> path = manager.download_bbox(bbox, "my_area.tif")
        """
        output_path = self._storage.output_dir / filename

        logger.info(f"Downloading bbox to {output_path}...")
        return self._provider.download_bbox(bbox, output_path, format=format)

    # =========================================================================
    # Utility methods
    # =========================================================================

    def get_missing_sheets(
        self,
        godlo: str,
        target_scale: str,
    ) -> list[str]:
        """
        Get list of sheets that haven't been downloaded yet.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier
        target_scale : str
            Target scale to check

        Returns
        -------
        list[str]
            List of godło identifiers for missing sheets
        """
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)

        missing = []
        for descendant in descendants:
            if not self._storage.exists(descendant.godlo, ".asc"):
                missing.append(descendant.godlo)

        return missing

    def count_sheets(self, godlo: str, target_scale: str) -> int:
        """
        Count total number of sheets in hierarchy.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier
        target_scale : str
            Target scale to count

        Returns
        -------
        int
            Number of sheets
        """
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)
        return len(descendants)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"DownloadManager(provider={self._provider.name}, "
            f"output_dir='{self._storage.output_dir}', "
            f"resolution='{self._resolution}')"
        )
