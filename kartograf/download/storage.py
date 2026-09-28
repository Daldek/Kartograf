"""
File storage management for downloaded NMT data.

This module provides the FileStorage class for managing file paths
and storage operations for downloaded data.
"""

import os
import re
import threading
from pathlib import Path
from typing import BinaryIO

from kartograf.core import parser_registry
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import ValidationError
from kartograf.sources.registry import get_source


class FileStorage:
    """
    Manages file storage for downloaded NMT data.

    Files are organized in a hierarchical directory structure based on
    resolution and godło components, making it easy to navigate and find
    specific sheets while keeping different resolutions separate.

    Directory structure example (PL-1992):
        data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmt/pl_1992_5m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmpt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/orto/pl_1992/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

    Directory structure example (PL-2000, own segment since 0.7.0/ADR-026 —
    the ADR-017 deferral is closed):
        data/nmt/pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc

    Attributes
    ----------
    output_dir : Path
        Base directory for storing downloaded files
    resolution : str
        Resolution dimension of the segment template ("1m" or "5m"); empty
        only when the segment comes from `product` (an explicit `subdir`
        alone leaves the constructor's `resolution` value untouched)

    Examples
    --------
    >>> storage = FileStorage("./data", resolution="1m")
    >>> path = storage.get_path("N-34-130-D-d-2-4", ".asc")
    >>> print(path)
    data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

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
        vertical_crs: str | None = "EVRF2007",
    ):
        """
        Initialize file storage.

        Parameters
        ----------
        output_dir : str or Path
            Base directory for storing downloaded files.
            Will be created if it doesn't exist.
        resolution : str, optional
            Resolution picking the NMT segment template: "1m" or "5m"
            (default: "1m"). Files land in
            `output_dir/nmt/pl_<uklad>_<resolution>_<vcrs>/...`.
            Ignored when product is set.
        product : str, optional
            Product name picking the segment template (e.g. "nmpt", "orto",
            "laz"). When set, the product template replaces the resolution one
            (`output_dir/nmpt/pl_<uklad>_1m_<vcrs>/...`).
        subdir : str, optional
            Explicit segment template sterowany deskryptorem zrodla
            (np. "nmt/cz_dmr5g_{vcrs}"). Ma pierwszenstwo przed product
            i resolution.
        vertical_crs : str, optional
            Vertical CRS filling the ``{vcrs}`` placeholder of the segment
            template (lowercased; default "EVRF2007"). ``None`` leaves the
            placeholder unresolved — path methods then raise
            ``ValidationError`` for templates that require it.
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
        self._vertical_crs = vertical_crs

    # Segment templates come from the source descriptors (ADR-026: a new
    # source is a new descriptor entry, no path code) — resolution/product
    # map to the descriptor KEY, not to a copy of its template.
    _RESOLUTION_SOURCES = {"1m": "pl.gugik.nmt_1m", "5m": "pl.gugik.nmt_5m"}
    _PRODUCT_SOURCES = {
        "nmpt": "pl.gugik.nmpt",
        "orto": "pl.gugik.orto",
        "laz": "pl.gugik.laz",
    }

    @staticmethod
    def _descriptor_template(key: str) -> str:
        """Segment template of a registered source."""
        template = get_source(key).storage_subdir
        if template is None:
            raise ValueError(f"Source '{key}' has no storage_subdir")
        return template

    @property
    def output_dir(self) -> Path:
        """Return the base output directory."""
        return self._output_dir

    @property
    def resolution(self) -> str:
        """Return the resolution dimension of the segment.

        "" only when the segment comes from `product` — an explicit `subdir`
        alone leaves the constructor's `resolution` value untouched.
        """
        return self._resolution

    @property
    def _subdir(self) -> str:
        """Return the segment template (override, product or resolution).

        ``{vcrs}`` is already filled from ``vertical_crs``; ``{uklad}`` may
        remain — path methods resolve it per identifier.
        """
        if self._subdir_override:
            template = self._subdir_override
        elif self._product:
            key = self._PRODUCT_SOURCES.get(self._product)
            template = self._descriptor_template(key) if key else self._product
        else:
            key = self._RESOLUTION_SOURCES.get(self._resolution)
            template = self._descriptor_template(key) if key else self._resolution
        # Falsy, not `is not None`: an empty string carries no dimension, so it
        # must leave `{vcrs}` unresolved for `_ensure_resolved` to report —
        # substituting it produced the silent segment `nmt/pl_1992_1m_`.
        if self._vertical_crs:
            template = template.replace("{vcrs}", self._vertical_crs.lower())
        return template

    @staticmethod
    def _ensure_resolved(subdir: str) -> str:
        """Reject a segment that still contains an unresolved placeholder."""
        if "{" in subdir:
            missing = ", ".join(re.findall(r"\{(\w+)\}", subdir))
            raise ValidationError(
                f"Nierozwiazany wymiar segmentu storage: {missing} (subdir '{subdir}')"
            )
        return subdir

    def _resolved_subdir(self, identifier: str, uklad: str | None = None) -> str:
        """Segment for the identifier: {uklad} given explicitly or from the
        sheet system.

        Same rule as ``parser_registry.path_parts`` when ``uklad`` is not
        given explicitly: dots (system ``pl2000``) -> "2000", anything else
        (incl. the pl1992 fallback) -> "1992". An explicit ``uklad`` overrides
        this detection — required for LAZ tiles, whose true horizontal system
        comes from ``uklad_xy`` (``LazTile.uklad``), not necessarily from the
        godlo format.
        """
        subdir = self._subdir
        if "{uklad}" in subdir:
            if uklad is None:
                system = parser_registry.detect_system(identifier)
                # None tylko gdyby rejestr byl pusty (nie zdarza sie w
                # praktyce — pl1992 jest fallbackiem z detect=lambda godlo:
                # True); warunek zostaje, zeby mypy nie zglosil union-attr.
                uklad = (
                    "2000" if system is not None and system.id == "pl2000" else "1992"
                )
            subdir = subdir.replace("{uklad}", uklad)
        return self._ensure_resolved(subdir)

    def get_path(self, godlo: str, ext: str = ".asc") -> Path:
        """
        Generate file path for given godło and extension.

        The path follows a hierarchical structure based on resolution
        and godło components:
        - 1:1M (N-34) → nmt/pl_1992_1m_evrf2007/N-34/N-34.asc
        - 1:10k (N-34-130-D-d-2-4) →
          nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

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
        PosixPath('data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc')
        """
        # Normalize godło using SheetParser
        parser = SheetParser(godlo)
        normalized_godlo = parser.godlo

        # Build directory path from godło components
        dir_parts = self._get_directory_parts(normalized_godlo)

        # Construct full path with resolved segment (product or resolution)
        dir_path = self._output_dir / self._resolved_subdir(normalized_godlo)
        for part in dir_parts:
            dir_path = dir_path / part

        filename = f"{normalized_godlo}{ext}"
        return dir_path / filename

    def get_raw_path(
        self, identifier: str, filename: str, *, uklad: str | None = None
    ) -> Path:
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
        uklad : str, optional
            Explicit horizontal system (``"1992"`` or ``"2000"``) filling the
            ``{uklad}`` segment placeholder. For LAZ tiles pass ``tile.uklad``
            — the tile's ``uklad_xy`` decides, not the godlo format (a
            ``"PL-2000:*"`` tile can still carry a dash-form godło). ``None``
            (default) keeps the previous behaviour: detect the system from
            ``identifier``'s format.

        Returns
        -------
        Path
            ``output_dir / <subdir> / <hierarchy from identifier> / filename``

        Raises
        ------
        ValidationError
            If ``uklad`` is given but is neither ``"1992"`` nor ``"2000"``.

        Examples
        --------
        >>> storage = FileStorage("./data", product="laz")
        >>> storage.get_raw_path("N-33-131-B-a-1-1-4", "81121_x.laz")
        PosixPath('data/laz/pl_1992_evrf2007/N-33/131/B/a/1/1/4/81121_x.laz')

        For LAZ tiles, prefer the explicit ``uklad`` (the tile's ``uklad_xy``
        decides, not the godlo format)::

            storage.get_raw_path(tile.godlo, tile.filename, uklad=tile.uklad)
        """
        if uklad is not None and uklad not in ("1992", "2000"):
            raise ValidationError(
                f"Nieznany uklad '{uklad}' (oczekiwano '1992' albo '2000')"
            )
        dir_parts = self._get_directory_parts(identifier)
        dir_path = self._output_dir / self._resolved_subdir(identifier, uklad)
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

        Searches within the segment (ADR-026). A segment template carrying
        `{uklad}` spans BOTH systems, so PL-1992 and PL-2000 files are listed
        together even though they live in separate directories.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern for matching files (default: "**/*.asc")

        Returns
        -------
        list[Path]
            List of matching file paths
        """
        template = self._subdir
        if "{uklad}" in template:
            subdirs = [template.replace("{uklad}", u) for u in ("1992", "2000")]
        else:
            subdirs = [template]
        files: list[Path] = []
        for name in subdirs:
            root = self._output_dir / self._ensure_resolved(name)
            if root.exists():
                files.extend(root.glob(pattern))
        return files

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


def prune_empty_dirs(start: Path, stop: Path) -> None:
    """
    Remove ``start`` and its parents while they are empty — never ``stop``.

    Used after a failed download/build: the target directory is created before
    writing, and a failure must not leave empty ``<segment>/bbox/`` trees behind
    (review max 2026-08-30, finding 10). Directories outside ``stop`` are never
    touched.
    """
    stop = Path(stop).resolve()
    current = Path(start).resolve()
    while current != stop and stop in current.parents:
        try:
            current.rmdir()  # succeeds only when empty
        except OSError:
            return
        current = current.parent
