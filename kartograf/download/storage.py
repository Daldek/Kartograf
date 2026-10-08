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
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.campaigns import CAMPAIGNS_DIR, CampaignRef
from kartograf.exceptions import ValidationError
from kartograf.sources.registry import get_source


class FileStorage:
    """
    Manages file storage for downloaded NMT data.

    Files are organized in a hierarchical directory structure based on
    resolution and sheet code components, making it easy to navigate and find
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
        variant: str | None = None,
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
            Explicit segment template driven by the source descriptor
            (e.g. "nmt/cz_dmr5g_{vcrs}"). Takes precedence over product
            and resolution.
        vertical_crs : str, optional
            Vertical CRS filling the ``{vcrs}`` placeholder of the segment
            template (lowercased; default "EVRF2007"). ``None`` leaves the
            placeholder unresolved — path methods then raise
            ``ValidationError`` for templates that require it.
        variant : str, optional
            Product variant appended to the END of the segment as
            ``_<variant>`` (E12: orto CIR -> ``orto/pl_<uklad>_cir``). Only
            orto uses it today; its template has no ``{vcrs}``, so the ADR-026
            order ``<kraj>_<uklad>[_<wariant>][_<vcrs>]`` holds. ``None``
            (default) = no suffix — the default variant (RGB) keeps its
            pre-E12 path. Take it from ``provider.storage_variant``.
        """
        if variant is not None and not re.fullmatch(r"[a-z0-9]+", variant):
            raise ValidationError(
                f"Nieprawidlowy wariant segmentu storage: '{variant}' "
                "(oczekiwano [a-z0-9]+)"
            )
        self._variant = variant
        self._subdir_override = subdir
        if product:
            self._product: str | None = product
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
        if self._variant:
            template = f"{template}_{self._variant}"
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
                # pl1992 is the registry fallback (never None)
                system = parser_registry.detect_system(identifier)
                uklad = "2000" if system.id == "pl2000" else "1992"
            subdir = subdir.replace("{uklad}", uklad)
        return self._ensure_resolved(subdir)

    def get_path(self, godlo: str, ext: str = ".asc") -> Path:
        """
        Generate file path for given sheet code and extension.

        The path follows a hierarchical structure based on resolution
        and sheet code components:
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
        # Normalize sheet code case via SheetParser (leading zeros are NOT stripped:
        # 'M-33-036-...' and 'M-33-36-...' map to different paths)
        parser = SheetParser(godlo)
        normalized_godlo = parser.godlo

        # Build directory path from sheet code components
        dir_parts = self._get_directory_parts(normalized_godlo)

        # Construct full path with resolved segment (product or resolution)
        dir_path = self._output_dir / self._resolved_subdir(normalized_godlo)
        for part in dir_parts:
            dir_path = dir_path / part

        filename = f"{normalized_godlo}{ext}"
        return dir_path / filename

    def get_campaign_path(
        self, godlo: str, campaign: CampaignRef, ext: str = ".asc"
    ) -> Path:
        """
        Path of a campaign file (ADR-030):
        ``<output>/<segment>/kampanie/<date>_<id>/<hierarchy>/<godlo><ext>``.
        """
        normalized = SheetParser(godlo).godlo
        dir_path = (
            self._output_dir
            / self._resolved_subdir(normalized)
            / CAMPAIGNS_DIR
            / campaign.dirname
        )
        for part in self._get_directory_parts(normalized):
            dir_path = dir_path / part
        return dir_path / f"{normalized}{ext}"

    def get_raw_path(
        self, identifier: str, filename: str, *, uklad: str | None = None
    ) -> Path:
        """
        Generate a file path for an opaque identifier WITHOUT parsing it.

        Unlike :meth:`get_path`, this does not run the identifier through
        ``SheetParser`` — it only splits it into a directory hierarchy. This is
        required for LAZ point-cloud tiles, whose sheet codes are finer than 1:10000
        and would otherwise raise ``ParseError``.

        Parameters
        ----------
        identifier : str
            Opaque sheet code used purely for the directory hierarchy
            (e.g. ``"N-33-131-B-a-1-1-4"`` or ``"6.162.34.02.3"``).
        filename : str
            File name to use as-is (e.g. the original OpenData ``.laz`` name).
        uklad : str, optional
            Explicit horizontal system (``"1992"`` or ``"2000"``) filling the
            ``{uklad}`` segment placeholder. For LAZ tiles pass ``tile.uklad``
            — the tile's ``uklad_xy`` decides, not the godlo format (a
            ``"PL-2000:*"`` tile can still carry a dash-form sheet code). ``None``
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
        Extract directory parts from sheet code.

        Supports both PL-1992 (dash-separated) and PL-2000 (dot-separated)
        formats:
        - PL-1992: "N-34-130-D-d-2-4" → ["N-34", "130", "D", "d", "2", "4"]
        - PL-2000: "6.179.12.20" → ["6", "179", "12", "20"]

        Parameters
        ----------
        godlo : str
            Normalized sheet code string

        Returns
        -------
        list[str]
            List of directory parts
        """
        return parser_registry.path_parts(godlo)

    def ensure_directory(self, godlo: str) -> Path:
        """
        Ensure directory exists for given sheet code.

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
        Check if file for given sheet code exists.

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

        Writes to the STANDARD path: ``temp.rename(target)`` replaces the
        campaign link (ADR-030) with a regular file; without a sidecar
        carrying ``extra.link`` it is an "unknown" file for the campaign
        flow, which the next ``newest`` replaces with a link.

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
        Delete file for given sheet code.

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
        # The campaign standard path is a hardlink or a copy (ADR-030):
        # unlink() removes the path itself, the file in kampanie/ stays.
        if path.exists():
            path.unlink()
            # The metadata sidecar must not outlive the data file.
            path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
            return True
        return False

    def list_files(
        self, pattern: str = "**/*.asc", *, campaigns: bool = False
    ) -> list[Path]:
        """
        List all files matching pattern in storage directory.

        Searches within the segment (ADR-026). A segment template carrying
        `{uklad}` spans BOTH systems, so PL-1992 and PL-2000 files are listed
        together even though they live in separate directories.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern for matching files (default: "**/*.asc")
        campaigns : bool, optional
            False (default): standard paths — without ``kampanie/``.
            True: only files in ``kampanie/`` (ADR-030).

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
                for p in root.glob(pattern):
                    in_campaigns = p.relative_to(root).parts[:1] == (CAMPAIGNS_DIR,)
                    if in_campaigns != campaigns:
                        continue
                    files.append(p)
        return files

    def get_size(self, godlo: str, ext: str = ".asc") -> int | None:
        """
        Get file size for given sheet code.

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


def storage_for_provider(
    output_dir: str | Path,
    provider=None,
    *,
    resolution: str = "1m",
    vertical_crs: str | None = "EVRF2007",
) -> FileStorage:
    """
    ``FileStorage`` of the segment where the provider's files land — the
    single place it is built (D18: CLI, ``DownloadManager``, PL cutout, CZ
    flow).

    The segment comes from the provider's source descriptor
    (``resolve_subdir(vertical_crs=...)``, ``{uklad}`` resolved per godlo),
    and without ``descriptor_key`` from ``resolution`` (PL NMT template).
    Vertical CRS: the provider's ACTUAL vertical CRS when it knows it
    (``str``), otherwise ``vertical_crs`` — the segment carries the fact,
    not the caller's wish. The provider variant (``storage_variant``, orto
    CIR/B-W) goes at the end of the segment (E12). ``isinstance(str)``, not
    ``is not None``: for ``Mock(spec=Provider)`` class attributes yield a
    ``Mock``.
    """
    provider_vertical_crs = getattr(provider, "vertical_crs", None)
    if isinstance(provider_vertical_crs, str):
        vertical_crs = provider_vertical_crs
    key = getattr(provider, "descriptor_key", None)
    subdir = (
        get_source(key).resolve_subdir(vertical_crs=vertical_crs)
        if isinstance(key, str)
        else None
    )
    variant = getattr(provider, "storage_variant", None)
    return FileStorage(
        output_dir,
        resolution=resolution,
        subdir=subdir,
        vertical_crs=vertical_crs,
        variant=variant if isinstance(variant, str) else None,
    )


def bbox_cutout_path(
    output_dir: str | Path, subdir: str, bbox: BBox, extension: str
) -> Path:
    """
    Path of a bbox cutout: ``<output>/<segment>/bbox/<coords><ext>`` (ADR-026).

    ``<coords>`` = ``min_x_min_y_max_x_max_y`` with ``format(v, ".10g")`` —
    the result grid coordinates in its own CRS. One name for the PL cutout
    (``--target-crs``) and the CZ cutout (D7).
    """
    coords = "_".join(
        format(v, ".10g") for v in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    )
    return Path(output_dir) / subdir / "bbox" / f"{coords}{extension}"
