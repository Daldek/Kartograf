"""
Download manager for coordinating NMT data downloads.

This module provides the DownloadManager class for downloading
single sheets and entire hierarchies of map sheets.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from kartograf.core.sheet_parser import SheetParser
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

    Attributes
    ----------
    provider : BaseProvider
        Data provider for downloading sheets
    storage : FileStorage
        Storage manager for saving files

    Examples
    --------
    >>> manager = DownloadManager(output_dir="./data")
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    PosixPath('data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif')

    >>> def on_progress(p):
    ...     print(f"{p.current}/{p.total}: {p.godlo} - {p.status}")
    >>> manager.download_hierarchy("N-34-130-D", "1:10000", on_progress=on_progress)
    """

    def __init__(
        self,
        output_dir: str | Path = "./data",
        provider: Optional[BaseProvider] = None,
        storage: Optional[FileStorage] = None,
        format: str = "GTiff",
    ):
        """
        Initialize download manager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Base directory for downloads (default: "./data")
        provider : BaseProvider, optional
            Data provider (default: GugikProvider)
        storage : FileStorage, optional
            Storage manager (default: FileStorage with output_dir)
        format : str, optional
            Default output format (default: "GTiff")
        """
        self._provider = provider or GugikProvider()
        self._storage = storage or FileStorage(output_dir)
        self._format = format

    @property
    def provider(self) -> BaseProvider:
        """Return the data provider."""
        return self._provider

    @property
    def storage(self) -> FileStorage:
        """Return the storage manager."""
        return self._storage

    @property
    def format(self) -> str:
        """Return the default format."""
        return self._format

    def download_sheet(
        self,
        godlo: str,
        format: Optional[str] = None,
        skip_existing: bool = True,
    ) -> Path:
        """
        Download a single map sheet.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        format : str, optional
            Output format (default: instance default)
        skip_existing : bool, optional
            Skip download if file exists (default: True)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If download fails
        ParseError
            If godlo is invalid
        """
        format = format or self._format
        ext = self._provider.get_file_extension(format)

        # Get target path
        target_path = self._storage.get_path(godlo, ext)

        # Check if already exists
        if skip_existing and target_path.exists():
            logger.info(f"Skipping {godlo} - already exists at {target_path}")
            return target_path

        # Download
        logger.info(f"Downloading {godlo}...")
        self._provider.download(godlo, target_path, format=format)

        return target_path

    def download_hierarchy(
        self,
        godlo: str,
        target_scale: str,
        format: Optional[str] = None,
        skip_existing: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> list[Path]:
        """
        Download all descendant sheets to target scale.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier (e.g., "N-34-130-D")
        target_scale : str
            Target scale to download (e.g., "1:10000")
        format : str, optional
            Output format (default: instance default)
        skip_existing : bool, optional
            Skip download if file exists (default: True)
        on_progress : callable, optional
            Callback function for progress updates.
            Called with DownloadProgress object for each sheet.

        Returns
        -------
        list[Path]
            List of paths to downloaded files

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
        format = format or self._format

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
                # Check if exists
                ext = self._provider.get_file_extension(format)
                target_path = self._storage.get_path(current_godlo, ext)

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

                path = self._provider.download(
                    current_godlo, target_path, format=format
                )
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

    def get_missing_sheets(
        self,
        godlo: str,
        target_scale: str,
        format: Optional[str] = None,
    ) -> list[str]:
        """
        Get list of sheets that haven't been downloaded yet.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier
        target_scale : str
            Target scale to check
        format : str, optional
            Output format (default: instance default)

        Returns
        -------
        list[str]
            List of godło identifiers for missing sheets
        """
        format = format or self._format
        ext = self._provider.get_file_extension(format)

        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)

        missing = []
        for descendant in descendants:
            if not self._storage.exists(descendant.godlo, ext):
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
            f"output_dir='{self._storage.output_dir}')"
        )
