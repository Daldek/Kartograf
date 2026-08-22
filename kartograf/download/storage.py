"""
File storage management for downloaded NMT data.

This module provides the FileStorage class for managing file paths
and storage operations for downloaded data.
"""

import os
import threading
from pathlib import Path
from typing import BinaryIO

from kartograf.core import parser_registry
from kartograf.core.sheet_parser import SheetParser


class FileStorage:
    """
    Manages file storage for downloaded NMT data.

    Files are organized in a hierarchical directory structure based on
    resolution and godło components, making it easy to navigate and find
    specific sheets while keeping different resolutions separate.

    Directory structure example (PL-1992):
        data/nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmt_5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmpt/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/orto/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

    Directory structure example (PL-2000):
        data/nmt_1m/6/179/12/6.179.12.asc
        data/nmt_1m/6/179/12/20/6.179.12.20.asc
        (PL-2000 sheets share the resolution subdirectory with PL-1992;
        the separate nmt_2000_<res> layout promised in ADR-017 is deferred.
        File names do not collide: PL-2000 uses dots, PL-1992 dashes.)

    Attributes
    ----------
    output_dir : Path
        Base directory for storing downloaded files
    resolution : str
        Resolution subdirectory ("1m" or "5m")

    Examples
    --------
    >>> storage = FileStorage("./data", resolution="1m")
    >>> path = storage.get_path("N-34-130-D-d-2-4", ".asc")
    >>> print(path)
    data/nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

    Notes
    -----
    All write operations use atomic writes (temp file → rename) to prevent
    partial files in case of errors.
    """

    SUPPORTED_RESOLUTIONS = ["1m", "5m"]

    def __init__(
        self,
        output_dir: str | Path = "./data",
        resolution: str = "1m",
        product: str | None = None,
        subdir: str | None = None,
    ):
        """
        Initialize file storage.

        Parameters
        ----------
        output_dir : str or Path
            Base directory for storing downloaded files.
            Will be created if it doesn't exist.
        resolution : str, optional
            Resolution for subdirectory: "1m" or "5m" (default: "1m").
            Files will be stored in output_dir/resolution/...
            Ignored when product is set.
        product : str, optional
            Product name for subdirectory (e.g. "nmpt", "orto").
            When set, uses product instead of resolution as subdirectory.
        subdir : str, optional
            Explicit subdirectory name sterowany deskryptorem zrodla
            (np. "cz_dmr5g"). Ma pierwszenstwo przed product i resolution.
        """
        self._subdir_override = subdir
        if product:
            self._product = product
            self._resolution = ""
        else:
            if resolution not in self.SUPPORTED_RESOLUTIONS:
                raise ValueError(
                    f"Unsupported resolution: '{resolution}'. "
                    f"Supported: {self.SUPPORTED_RESOLUTIONS}"
                )
            self._product = None
            self._resolution = resolution
        self._output_dir = Path(output_dir)

    # Mapping from resolution to subdirectory name
    _RESOLUTION_SUBDIRS = {
        "1m": "nmt_1m",
        "5m": "nmt_5m",
    }

    @property
    def output_dir(self) -> Path:
        """Return the base output directory."""
        return self._output_dir

    @property
    def resolution(self) -> str:
        """Return the resolution subdirectory."""
        return self._resolution

    @property
    def _subdir(self) -> str:
        """Return subdirectory name (override, product or nmt_<resolution>)."""
        if self._subdir_override:
            return self._subdir_override
        if self._product:
            return self._product
        return self._RESOLUTION_SUBDIRS.get(self._resolution, self._resolution)

    def get_path(self, godlo: str, ext: str = ".asc") -> Path:
        """
        Generate file path for given godło and extension.

        The path follows a hierarchical structure based on resolution
        and godło components:
        - 1:1M (N-34) → nmt_1m/N-34/N-34.asc
        - 1:10k (N-34-130-D-d-2-4) → nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        Path
            Full path to the file

        Examples
        --------
        >>> storage = FileStorage("./data", resolution="1m")
        >>> storage.get_path("N-34-130-D-d-2-4", ".asc")
        PosixPath('data/nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc')
        """
        # Normalize godło using SheetParser
        parser = SheetParser(godlo)
        normalized_godlo = parser.godlo

        # Build directory path from godło components
        dir_parts = self._get_directory_parts(normalized_godlo)

        # Construct full path with subdirectory (product or resolution)
        dir_path = self._output_dir / self._subdir
        for part in dir_parts:
            dir_path = dir_path / part

        filename = f"{normalized_godlo}{ext}"
        return dir_path / filename

    def get_raw_path(self, identifier: str, filename: str) -> Path:
        """
        Generate a file path for an opaque identifier WITHOUT parsing it.

        Unlike :meth:`get_path`, this does not run the identifier through
        ``SheetParser`` — it only splits it into a directory hierarchy. This is
        required for LAZ point-cloud tiles, whose godła are finer than 1:10000
        and would otherwise raise ``ParseError``.

        Parameters
        ----------
        identifier : str
            Opaque godło used purely for the directory hierarchy
            (e.g. ``"N-33-131-B-a-1-1-4"`` or ``"6.162.34.02.3"``).
        filename : str
            File name to use as-is (e.g. the original OpenData ``.laz`` name).

        Returns
        -------
        Path
            ``output_dir / <subdir> / <hierarchy from identifier> / filename``

        Examples
        --------
        >>> storage = FileStorage("./data", product="laz")
        >>> storage.get_raw_path("N-33-131-B-a-1-1-4", "81121_x_N-33-131-B-a-1-1-4.laz")
        PosixPath('data/laz/N-33/131/B/a/1/1/4/81121_x_N-33-131-B-a-1-1-4.laz')
        """
        dir_parts = self._get_directory_parts(identifier)
        dir_path = self._output_dir / self._subdir
        for part in dir_parts:
            dir_path = dir_path / part
        return dir_path / filename

    def _get_directory_parts(self, godlo: str) -> list[str]:
        """
        Extract directory parts from godło.

        Supports both PL-1992 (dash-separated) and PL-2000 (dot-separated)
        formats:
        - PL-1992: "N-34-130-D-d-2-4" → ["N-34", "130", "D", "d", "2", "4"]
        - PL-2000: "6.179.12.20" → ["6", "179", "12", "20"]

        Parameters
        ----------
        godlo : str
            Normalized godło string

        Returns
        -------
        list[str]
            List of directory parts
        """
        return parser_registry.path_parts(godlo)

    def ensure_directory(self, godlo: str) -> Path:
        """
        Ensure directory exists for given godło.

        Parameters
        ----------
        godlo : str
            Map sheet identifier

        Returns
        -------
        Path
            Path to the directory (created if needed)
        """
        path = self.get_path(godlo)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.parent

    def exists(self, godlo: str, ext: str = ".asc") -> bool:
        """
        Check if file for given godło exists.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        bool
            True if file exists
        """
        return self.get_path(godlo, ext).exists()

    def write_atomic(
        self,
        godlo: str,
        content: bytes | BinaryIO,
        ext: str = ".asc",
    ) -> Path:
        """
        Write content to file atomically.

        Uses a temporary file and atomic rename to prevent partial files.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        content : bytes or BinaryIO
            Content to write (bytes or file-like object)
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        Path
            Path to the written file

        Examples
        --------
        >>> storage = FileStorage("./data")
        >>> path = storage.write_atomic("N-34-130-D", b"data", ".asc")
        """
        target_path = self.get_path(godlo, ext)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Use unique temp filename per process/thread to prevent collisions
        # when multiple threads write concurrently
        thread_id = threading.current_thread().ident
        temp_suffix = f"{target_path.suffix}.{os.getpid()}_{thread_id}.tmp"
        temp_path = target_path.with_suffix(temp_suffix)

        try:
            with open(temp_path, "wb") as f:
                if isinstance(content, bytes):
                    f.write(content)
                else:
                    # File-like object
                    for chunk in iter(lambda: content.read(8192), b""):
                        f.write(chunk)

            # Atomic rename
            temp_path.rename(target_path)
            return target_path

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    def delete(self, godlo: str, ext: str = ".asc") -> bool:
        """
        Delete file for given godło.

        Also deletes the companion `<file>.meta.json` sidecar, if present.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        bool
            True if file was deleted, False if it didn't exist
        """
        path = self.get_path(godlo, ext)
        if path.exists():
            path.unlink()
            # Sidecar metadanych nie moze przezyc pliku danych.
            path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
            return True
        return False

    def list_files(self, pattern: str = "**/*.asc") -> list[Path]:
        """
        List all files matching pattern in storage directory.

        Searches within the resolution subdirectory.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern for matching files (default: "**/*.asc")

        Returns
        -------
        list[Path]
            List of matching file paths
        """
        subdir = self._output_dir / self._subdir
        if not subdir.exists():
            return []
        return list(subdir.glob(pattern))

    def get_size(self, godlo: str, ext: str = ".asc") -> int | None:
        """
        Get file size for given godło.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        int or None
            File size in bytes, or None if file doesn't exist
        """
        path = self.get_path(godlo, ext)
        if path.exists():
            return path.stat().st_size
        return None

    def __repr__(self) -> str:
        """Return string representation."""
        if self._subdir_override:
            return (
                f"FileStorage(output_dir='{self._output_dir}', "
                f"subdir='{self._subdir_override}')"
            )
        if self._product:
            return (
                f"FileStorage(output_dir='{self._output_dir}', "
                f"product='{self._product}')"
            )
        return (
            f"FileStorage(output_dir='{self._output_dir}', "
            f"resolution='{self._resolution}')"
        )
