"""
File storage management for downloaded NMT data.

This module provides the FileStorage class for managing file paths
and storage operations for downloaded data.
"""

from pathlib import Path
from typing import BinaryIO

from kartograf.core.sheet_parser import SheetParser


class FileStorage:
    """
    Manages file storage for downloaded NMT data.

    Files are organized in a hierarchical directory structure based on
    the godło components, making it easy to navigate and find specific sheets.

    Directory structure example:
        data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

    Attributes
    ----------
    output_dir : Path
        Base directory for storing downloaded files

    Examples
    --------
    >>> storage = FileStorage("./data")
    >>> path = storage.get_path("N-34-130-D-d-2-4", ".tif")
    >>> print(path)
    data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

    Notes
    -----
    All write operations use atomic writes (temp file → rename) to prevent
    partial files in case of errors.
    """

    def __init__(self, output_dir: str | Path = "./data"):
        """
        Initialize file storage.

        Parameters
        ----------
        output_dir : str or Path
            Base directory for storing downloaded files.
            Will be created if it doesn't exist.
        """
        self._output_dir = Path(output_dir)

    @property
    def output_dir(self) -> Path:
        """Return the base output directory."""
        return self._output_dir

    def get_path(self, godlo: str, ext: str = ".tif") -> Path:
        """
        Generate file path for given godło and extension.

        The path follows a hierarchical structure based on godło components:
        - 1:1M (N-34) → N-34/N-34.tif
        - 1:500k (N-34-A) → N-34/A/N-34-A.tif
        - 1:200k (N-34-130) → N-34/130/N-34-130.tif
        - 1:100k (N-34-130-D) → N-34/130/D/N-34-130-D.tif
        - 1:50k (N-34-130-D-d) → N-34/130/D/d/N-34-130-D-d.tif
        - 1:25k (N-34-130-D-d-2) → N-34/130/D/d/2/N-34-130-D-d-2.tif
        - 1:10k (N-34-130-D-d-2-4) → N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        ext : str, optional
            File extension including dot (default: ".tif")

        Returns
        -------
        Path
            Full path to the file

        Examples
        --------
        >>> storage = FileStorage("./data")
        >>> storage.get_path("N-34-130-D-d-2-4", ".tif")
        PosixPath('data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif')
        """
        # Normalize godło using SheetParser
        parser = SheetParser(godlo)
        normalized_godlo = parser.godlo

        # Build directory path from godło components
        dir_parts = self._get_directory_parts(normalized_godlo)

        # Construct full path
        dir_path = self._output_dir
        for part in dir_parts:
            dir_path = dir_path / part

        filename = f"{normalized_godlo}{ext}"
        return dir_path / filename

    def _get_directory_parts(self, godlo: str) -> list[str]:
        """
        Extract directory parts from godło.

        Parameters
        ----------
        godlo : str
            Normalized godło string

        Returns
        -------
        list[str]
            List of directory parts
        """
        parts = godlo.split("-")

        # First two parts form the base: N-34
        dir_parts = [f"{parts[0]}-{parts[1]}"]

        # Add remaining parts as subdirectories
        for part in parts[2:]:
            dir_parts.append(part)

        return dir_parts

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

    def exists(self, godlo: str, ext: str = ".tif") -> bool:
        """
        Check if file for given godło exists.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".tif")

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
        ext: str = ".tif",
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
            File extension including dot (default: ".tif")

        Returns
        -------
        Path
            Path to the written file

        Examples
        --------
        >>> storage = FileStorage("./data")
        >>> path = storage.write_atomic("N-34-130-D", b"data", ".tif")
        """
        target_path = self.get_path(godlo, ext)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")

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

    def delete(self, godlo: str, ext: str = ".tif") -> bool:
        """
        Delete file for given godło.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".tif")

        Returns
        -------
        bool
            True if file was deleted, False if it didn't exist
        """
        path = self.get_path(godlo, ext)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_files(self, pattern: str = "**/*.tif") -> list[Path]:
        """
        List all files matching pattern in storage directory.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern for matching files (default: "**/*.tif")

        Returns
        -------
        list[Path]
            List of matching file paths
        """
        if not self._output_dir.exists():
            return []
        return list(self._output_dir.glob(pattern))

    def get_size(self, godlo: str, ext: str = ".tif") -> int | None:
        """
        Get file size for given godło.

        Parameters
        ----------
        godlo : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".tif")

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
        return f"FileStorage(output_dir='{self._output_dir}')"
