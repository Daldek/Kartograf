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
from kartograf.providers.pl import create_nmt_provider

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

    Notes
    -----
    Populated by `download_hierarchy` and exposed as `DownloadManager.last_result`.
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

    Attributes
    ----------
    last_result : DownloadResult or None
        Per-sheet outcome of the most recent hierarchy download. Reset to None
        at the start of each `download_sheet` / `download_hierarchy` call; set
        only by `download_hierarchy` (a single 1:10000 sheet downloaded via
        `download_sheet` leaves it None).

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
        sidecar_extra: dict | None = None,
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
            Storage manager (default: FileStorage whose subdirectory comes
            from the provider's source descriptor
            (`resolve_subdir(vertical_crs=...)`, `{uklad}` resolved per godlo),
            falling back to `resolution` when the provider has no
            `descriptor_key`)
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
        sidecar_extra : dict, optional
            Dodatkowe pola scalane do `extra` kazdego sidecara (etap 1:
            `parent_request` w trybie bbox/geometry).
        """
        # If resolution is 5m, force EVRF2007
        if resolution == "5m" and vertical_crs != "EVRF2007":
            logger.warning(
                f"Resolution 5m only supports EVRF2007, changing "
                f"vertical_crs from '{vertical_crs}' to 'EVRF2007'"
            )
            vertical_crs = "EVRF2007"

        self._provider = provider or create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution
        )
        if storage is None:
            subdir = None
            key = getattr(self._provider, "descriptor_key", None)
            # isinstance(str), nie `is not None`: dla Mock(spec=Provider)
            # descriptor_key (atrybut klasy BaseProvider) zwraca Mock, nie None.
            if isinstance(key, str):
                from kartograf.sources.registry import get_source

                subdir = get_source(key).resolve_subdir(vertical_crs=vertical_crs)
            storage = FileStorage(
                output_dir,
                resolution=resolution,
                subdir=subdir,
                vertical_crs=vertical_crs,
            )
        self._storage = storage
        self._vertical_crs = vertical_crs
        self._resolution = resolution
        self._default_ext = self._provider.default_extension
        self._max_workers = max(1, max_workers)
        self._sidecar_extra = sidecar_extra
        self.last_result: DownloadResult | None = None

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

        Notes
        -----
        `self.last_result` is reset to None at the start of each
        `download_sheet` / `download_hierarchy` call and set only by
        `download_hierarchy`, so a single 1:10000 sheet downloaded here leaves
        it None and never exposes the previous run's result.
        """
        # Wynik poprzedniego przebiegu nie moze przeciec do tego wywolania.
        # Reset jest idempotentny — rozwiniecie do hierarchii zeruje go ponownie.
        self.last_result = None

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
        self._write_sidecar(target_path, {"godlo": godlo})

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
        ValidationError
            If target_scale is invalid
        ParseError
            If godlo is invalid

        Notes
        -----
        Per-sheet download failures do not raise; they are collected in
        `self.last_result.failed` (see `DownloadResult`). The returned list
        contains downloaded AND skipped (pre-existing) files.
        `self.last_result` is reset to None at the start of each
        `download_sheet` / `download_hierarchy` call and set only by
        `download_hierarchy`, so a call that raises never leaves the previous
        run's result behind.

        Examples
        --------
        >>> manager = DownloadManager()
        >>> paths = manager.download_hierarchy("N-34-130-D-d", "1:10000")
        >>> len(paths)  # 4 * 4 = 16 sheets
        16
        """
        # Wynik poprzedniego przebiegu nie moze przeciec do tego wywolania —
        # kasujemy go, zanim cokolwiek moze rzucic (ParseError/ValidationError).
        self.last_result = None

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
            self._write_sidecar(path, {"godlo": descendant_godlo})
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
        result = DownloadResult()

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
                    result.skipped.append(current_godlo)
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
                self._write_sidecar(path, {"godlo": current_godlo})
                result.succeeded.append(path)
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
                result.failed.append(current_godlo)
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

        self.last_result = result
        logger.info(
            f"Hierarchy download complete: {len(result.succeeded)} downloaded, "
            f"{len(result.skipped)} skipped, {len(result.failed)} failed (of {total})"
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
        result = DownloadResult()
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
                        result.failed.append(godlo_id)
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
                        if status == "skipped":
                            result.skipped.append(current_godlo)
                        else:
                            result.succeeded.append(path)
                        downloaded_paths.append(path)
                    elif status == "failed":
                        result.failed.append(current_godlo)

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

        self.last_result = result
        logger.info(
            f"Hierarchy download complete: {len(result.succeeded)} downloaded, "
            f"{len(result.skipped)} skipped, {len(result.failed)} failed (of {total})"
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
        ValidationError
            If the provider refuses the request before going out to the
            network - today: EVRF2007 heights, whose WCS endpoint GUGiK
            withdrew (see ``GugikProvider.download_bbox``)

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
        result = self._provider.download_bbox(bbox, output_path, format=format)
        self._write_sidecar(
            result,
            {
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
        )
        return result

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

    def _write_sidecar(self, data_path: Path, request: dict) -> None:
        """Best-effort zapis sidecara .meta.json (blad nie przerywa pobrania)."""
        try:
            from kartograf.sources.registry import get_source
            from kartograf.sources.sidecar import build_metadata, write_sidecar

            key = getattr(self._provider, "descriptor_key", None)
            if not isinstance(key, str):
                return
            meta = build_metadata(
                get_source(key),
                request=request,
                vertical_crs=getattr(self._provider, "vertical_crs", None),
                data_path=data_path,
                extra=dict(self._sidecar_extra) if self._sidecar_extra else None,
            )
            write_sidecar(data_path, meta)
        except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
            logger.warning(f"Nie udalo sie zapisac sidecara dla {data_path}: {e}")

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"DownloadManager(provider={self._provider.name}, "
            f"output_dir='{self._storage.output_dir}', "
            f"resolution='{self._resolution}', "
            f"max_workers={self._max_workers})"
        )
