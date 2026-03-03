"""
Download manager for coordinating NMT data downloads.

This module provides the DownloadManager class for downloading
single sheets and entire hierarchies of map sheets.

Supports parallel downloads via ThreadPoolExecutor when max_workers > 1.
"""

import concurrent.futures
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass
class DownloadResult:
    """
    Result of a batch/hierarchy download operation.

    Attributes
    ----------
    succeeded : list[Path]
        Paths to successfully downloaded files
    failed : list[str]
        Godlo identifiers that failed to download
    skipped : list[str]
        Godlo identifiers that were skipped (already existed)
    """

    succeeded: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Return total number of sheets processed."""
        return len(self.succeeded) + len(self.failed) + len(self.skipped)

    @property
    def all_paths(self) -> list[Path]:
        """Return paths of successfully downloaded files."""
        return list(self.succeeded)


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
        provider: BaseProvider | None = None,
        storage: FileStorage | None = None,
        vertical_crs: str = "EVRF2007",
        resolution: str = "1m",
        max_workers: int = 1,
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
        max_workers : int, optional
            Maximum number of parallel download threads (default: 1).
            When 1, downloads are sequential (backward compatible).
            When > 1, uses ThreadPoolExecutor for parallel downloads.
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
        self._default_ext = self._provider.default_extension
        self._max_workers = max(1, max_workers)

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
        on_progress: ProgressCallback | None = None,
    ) -> Path | list[Path]:
        """
        Download a map sheet as ASC.

        For sheets at scale 1:10000, downloads a single file.
        For coarser scales (e.g. 1:25000, 1:50000), automatically expands
        to all descendant 1:10000 sheets via download_hierarchy().

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        skip_existing : bool, optional
            Skip download if file exists (default: True)
        on_progress : callable, optional
            Callback function for progress updates (used when expanding hierarchy).

        Returns
        -------
        Path or list[Path]
            Path to the downloaded ASC file (for 1:10000),
            or list of paths (for coarser scales expanded to 1:10000)

        Raises
        ------
        DownloadError
            If download fails
        ParseError
            If godlo is invalid
        """
        parser = SheetParser(godlo)

        # PL-2000 godła are always downloaded directly (individual files on GUGiK)
        # PL-1992 coarser than 1:10000 must be expanded to 1:10000 descendants
        if parser.uklad != "2000" and parser.scale != "1:10000":
            return self.download_hierarchy(
                godlo, "1:10000", skip_existing=skip_existing, on_progress=on_progress
            )

        # Get target path
        target_path = self._storage.get_path(godlo, self._default_ext)

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
        on_progress: ProgressCallback | None = None,
        max_workers: int | None = None,
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
        max_workers : int, optional
            Maximum parallel download threads. If None, uses instance default.
            When <= 1, downloads sequentially (backward compatible).

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
        workers = max_workers if max_workers is not None else self._max_workers

        logger.info(
            f"Starting hierarchy download: {godlo} → {target_scale} "
            f"({total} sheets, workers={workers})"
        )

        if workers <= 1:
            # Sequential download (backward compatible)
            return self._download_hierarchy_sequential(
                descendants, total, skip_existing, on_progress
            )
        else:
            # Parallel download with ThreadPoolExecutor
            return self._download_hierarchy_parallel(
                descendants, total, skip_existing, on_progress, workers
            )

    def _download_single_sheet_task(
        self,
        descendant_godlo: str,
        skip_existing: bool,
    ) -> tuple[str, Path | None, str, str]:
        """
        Download a single sheet — used as a task for both sequential and parallel modes.

        Parameters
        ----------
        descendant_godlo : str
            Godlo identifier of the sheet to download
        skip_existing : bool
            Whether to skip if file already exists

        Returns
        -------
        tuple[str, Path | None, str, str]
            (godlo, path_or_none, status, message)
            status is one of: "skipped", "completed", "failed"
        """
        try:
            target_path = self._storage.get_path(descendant_godlo, self._default_ext)

            if skip_existing and target_path.exists():
                return (descendant_godlo, target_path, "skipped", "Already exists")

            path = self._provider.download(descendant_godlo, target_path)
            return (descendant_godlo, path, "completed", "")

        except DownloadError as e:
            logger.error(f"Failed to download {descendant_godlo}: {e}")
            return (descendant_godlo, None, "failed", str(e))

    def _download_hierarchy_sequential(
        self,
        descendants: list,
        total: int,
        skip_existing: bool,
        on_progress: ProgressCallback | None,
    ) -> list[Path]:
        """Execute sequential download of all descendants."""
        downloaded_paths = []
        failed_count = 0

        for i, descendant in enumerate(descendants, 1):
            current_godlo = descendant.godlo

            try:
                target_path = self._storage.get_path(current_godlo, self._default_ext)

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

    def _download_hierarchy_parallel(
        self,
        descendants: list,
        total: int,
        skip_existing: bool,
        on_progress: ProgressCallback | None,
        max_workers: int,
    ) -> list[Path]:
        """Execute parallel download of all descendants using ThreadPoolExecutor."""
        downloaded_paths: list[Path] = []
        failed_count = 0
        lock = threading.Lock()
        counter = [0]  # mutable counter for progress tracking

        def _submit_and_handle(descendant):
            """Download a single descendant and return the result."""
            return self._download_single_sheet_task(descendant.godlo, skip_existing)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_godlo = {
                executor.submit(_submit_and_handle, desc): desc.godlo
                for desc in descendants
            }

            for future in concurrent.futures.as_completed(future_to_godlo):
                godlo_id = future_to_godlo[future]
                try:
                    current_godlo, path, status, message = future.result()
                except Exception as e:
                    # Unexpected exception from the future
                    logger.error(f"Unexpected error downloading {godlo_id}: {e}")
                    with lock:
                        failed_count += 1
                        counter[0] += 1
                        current_count = counter[0]
                    if on_progress:
                        on_progress(
                            DownloadProgress(
                                current=current_count,
                                total=total,
                                godlo=godlo_id,
                                status="failed",
                                message=str(e),
                            )
                        )
                    continue

                with lock:
                    counter[0] += 1
                    current_count = counter[0]

                    if status in ("completed", "skipped") and path is not None:
                        downloaded_paths.append(path)
                    elif status == "failed":
                        failed_count += 1

                if on_progress:
                    if status == "skipped":
                        on_progress(
                            DownloadProgress(
                                current=current_count,
                                total=total,
                                godlo=current_godlo,
                                status="skipped",
                                message=message,
                            )
                        )
                    elif status == "completed":
                        on_progress(
                            DownloadProgress(
                                current=current_count,
                                total=total,
                                godlo=current_godlo,
                                status="completed",
                            )
                        )
                    elif status == "failed":
                        on_progress(
                            DownloadProgress(
                                current=current_count,
                                total=total,
                                godlo=current_godlo,
                                status="failed",
                                message=message,
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
            if not self._storage.exists(descendant.godlo, self._default_ext):
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
            f"resolution='{self._resolution}', "
            f"max_workers={self._max_workers})"
        )
