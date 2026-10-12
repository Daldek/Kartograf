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
from kartograf.download.campaigns import FULL_SHEET_DIR
from kartograf.download.versions import INCOMING_DIR, VERSIONS_DIR
from kartograf.exceptions import ValidationError
from kartograf.sources.registry import get_source

# 0.7.x campaign directory, unused since the versioned store (spec 9).
_LEGACY_CAMPAIGNS_DIR = "kampanie"


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
    >>> storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
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
        output_dir: str | Path,
        *,
        resolution: str | None,
        vertical_crs: str | None,
        product: str | None = None,
        subdir: str | None = None,
        variant: str | None = None,
    ):
        """
        Initialize file storage.

        Parameters
        ----------
        output_dir : str or Path
            Base directory for storing downloaded files.
            Will be created if it doesn't exist.
        resolution : str or None
            "1m" for high-resolution NMT/NMPT or "5m" for NMT 5m.
            Set None only if the selected product/descriptor segment has no
            resolution dimension (e.g. orthophotos or LAZ). Without a product
            or descriptor, a resolution is required to choose the NMT segment.
        vertical_crs : str or None
            "EVRF2007" (modern PL heights), "KRON86" (legacy PL heights) or
            "Bpv" (native CZ heights). Set None only when the selected
            product/descriptor segment has no vertical dimension (orthophoto).
            A segment needing ``{vcrs}`` rejects None on path resolution.
        product : str or None, optional
            "nmpt" (surface model, 1m), "orto" (orthophoto) or "laz"
            (point cloud); None (default) selects NMT from ``resolution``.
        subdir : str or None, optional
            Explicit descriptor segment template, e.g. "nmt/cz_dmr5g_{vcrs}";
            None (default) selects by product or resolution.
        variant : str or None, optional
            Product variant appended as ``_<variant>``. "cir" and "bw"
            distinguish orthophoto from its RGB segment; None (default)
            leaves the segment unsuffixed. Take it from
            ``provider.storage_variant``.
        """
        if variant is not None and not re.fullmatch(r"[a-z0-9]+", variant):
            raise ValidationError(
                f"Nieprawidlowy wariant segmentu storage: '{variant}' "
                "(oczekiwano [a-z0-9]+)"
            )
        self._variant = variant
        self._subdir_override = subdir
        if product is not None or subdir is not None:
            self._product = product
            self._resolution = resolution or ""
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

        ``{vcrs}`` is already filled from ``vertical_crs``; ``{system}`` may
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

    def _resolved_subdir(self, identifier: str, system: str | None = None) -> str:
        """Segment for the identifier: {system} given explicitly or from the
        sheet system.

        Same rule as ``parser_registry.path_parts`` when ``system`` is not
        given explicitly: dots (system ``pl2000``) -> "2000", anything else
        (incl. the pl1992 fallback) -> "1992". An explicit ``system`` overrides
        this detection — required for LAZ tiles, whose true horizontal system
        comes from ``uklad_xy`` (``LazTile.system``), not necessarily from the
        sheet format.
        """
        subdir = self._subdir
        if "{system}" in subdir:
            if system is None:
                # pl1992 is the registry fallback (never None)
                detected = parser_registry.detect_system(identifier)
                system = "2000" if detected.id == "pl2000" else "1992"
            subdir = subdir.replace("{system}", system)
        return self._ensure_resolved(subdir)

    def get_path(self, sheet: str, ext: str) -> Path:
        """
        Generate file path for given sheet code and extension.

        The path follows a hierarchical structure based on resolution
        and sheet code components:
        - 1:1M (N-34) → nmt/pl_1992_1m_evrf2007/N-34/N-34.asc
        - 1:10k (N-34-130-D-d-2-4) →
          nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

        Parameters
        ----------
        sheet : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        ext : str
            Explicit file extension including dot: ".asc" for NMT/NMPT
            sheets or ".tif" for orthophotos.

        Returns
        -------
        Path
            Full path to the file

        Examples
        --------
        >>> storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        >>> storage.get_path("N-34-130-D-d-2-4", ".asc")
        PosixPath('data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc')
        """
        normalized = SheetParser(sheet).sheet
        return self._sheet_path(normalized, ext)

    def _sheet_path(self, normalized: str, ext: str, *subtree: str) -> Path:
        """``<output>/<segment>/<subtree...>/<hierarchy>/<sheet><ext>``.

        ``normalized`` is the canonical sheet code (``SheetParser(...).sheet``,
        A7: ``'M-33-036-...'`` and ``'M-33-36-...'`` map to one path).
        """
        dir_path = self._output_dir / self._resolved_subdir(normalized)
        for part in (*subtree, *self._get_directory_parts(normalized)):
            dir_path = dir_path / part
        return dir_path / f"{normalized}{ext}"

    def get_versions_base(self, sheet: str) -> Path:
        """``<output>/<segment>/versions`` of the sheet's segment (spec 3).

        Holds the staging directory ``.incoming/`` (same file system as the
        versions, D19).
        """
        normalized = SheetParser(sheet).sheet
        return self._output_dir / self._resolved_subdir(normalized) / VERSIONS_DIR

    def get_versions_root(self, sheet: str) -> Path:
        """``<output>/<segment>/versions/<hierarchy>/`` — every version of the
        sheet's files lives in ``<label>_<sha8>/`` directories here (D17)."""
        normalized = SheetParser(sheet).sheet
        path = self.get_versions_base(normalized)
        for part in self._get_directory_parts(normalized):
            path = path / part
        return path

    def has_legacy_campaigns(self) -> bool:
        """Whether the segment holds a 0.7.x ``kampanie/`` directory (unused
        since the versioned store; files are downloaded again)."""
        return any(
            (root / _LEGACY_CAMPAIGNS_DIR).is_dir() for root in self._segment_roots()
        )

    def get_full_sheet_path(self, sheet: str, ext: str) -> Path:
        """
        Path of the second link to the newest declared-full flight (ADR-033):
        ``<output>/<segment>/full_sheet/<hierarchy>/<sheet><ext>`` — the same
        hierarchy as :meth:`get_path`.
        ``ext`` is the explicit file extension including dot (".asc" or ".tif").
        """
        normalized = SheetParser(sheet).sheet
        return self._sheet_path(normalized, ext, FULL_SHEET_DIR)

    def get_raw_path(
        self, identifier: str, filename: str, *, system: str | None = None
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
        system : str, optional
            Explicit horizontal system (``"1992"`` or ``"2000"``) filling the
            ``{system}`` segment placeholder. For LAZ tiles pass ``tile.system``
            — the tile's ``uklad_xy`` decides, not the sheet format (a
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
            If ``system`` is given but is neither ``"1992"`` nor ``"2000"``.

        Examples
        --------
        >>> storage = FileStorage(
        ...     "./data", resolution=None, vertical_crs="EVRF2007", product="laz"
        ... )
        >>> storage.get_raw_path("N-33-131-B-a-1-1-4", "81121_x.laz")
        PosixPath('data/laz/pl_1992_evrf2007/N-33/131/B/a/1/1/4/81121_x.laz')

        For LAZ tiles, prefer the explicit ``system`` (the tile's ``uklad_xy``
        decides, not the sheet format)::

            storage.get_raw_path(tile.sheet, tile.filename, system=tile.system)
        """
        if system is not None and system not in ("1992", "2000"):
            raise ValidationError(
                f"Nieznany uklad '{system}' (oczekiwano '1992' albo '2000')"
            )
        dir_parts = self._get_directory_parts(identifier)
        dir_path = self._output_dir / self._resolved_subdir(identifier, system)
        for part in dir_parts:
            dir_path = dir_path / part
        return dir_path / filename

    def _get_directory_parts(self, sheet: str) -> list[str]:
        """
        Extract directory parts from sheet code.

        Supports both PL-1992 (dash-separated) and PL-2000 (dot-separated)
        formats:
        - PL-1992: "N-34-130-D-d-2-4" → ["N-34", "130", "D", "d", "2", "4"]
        - PL-2000: "6.179.12.20" → ["6", "179", "12", "20"]

        Parameters
        ----------
        sheet : str
            Normalized sheet code string

        Returns
        -------
        list[str]
            List of directory parts
        """
        return parser_registry.path_parts(sheet)

    def ensure_directory(self, sheet: str, ext: str) -> Path:
        """
        Ensure directory exists for given sheet code.

        Parameters
        ----------
        sheet : str
            Map sheet identifier
        ext : str
            Explicit file extension including dot (".asc" or ".tif").

        Returns
        -------
        Path
            Path to the directory (created if needed)
        """
        path = self.get_path(sheet, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.parent

    def exists(self, sheet: str, ext: str) -> bool:
        """
        Check if file for given sheet code exists.

        Parameters
        ----------
        sheet : str
            Map sheet identifier
        ext : str
            Explicit file extension including dot (".asc" or ".tif").

        Returns
        -------
        bool
            True if file exists
        """
        return self.get_path(sheet, ext).exists()

    def write_atomic(
        self,
        sheet: str,
        content: bytes | BinaryIO,
        ext: str,
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
        sheet : str
            Map sheet identifier
        content : bytes or BinaryIO
            Content to write (bytes or file-like object)
        ext : str
            Explicit file extension including dot (".asc" or ".tif").

        Returns
        -------
        Path
            Path to the written file

        Examples
        --------
        >>> storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        >>> path = storage.write_atomic("N-34-130-D", b"data", ".asc")
        """
        target_path = self.get_path(sheet, ext)
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

    def delete(self, sheet: str, ext: str) -> bool:
        """
        Delete the links of a sheet: the standard path and ``full_sheet/``.

        Each one goes together with its companion `<file>.meta.json` sidecar.
        Versions in ``versions/`` stay (spec D9).

        Parameters
        ----------
        sheet : str
            Map sheet identifier
        ext : str
            Explicit file extension including dot (".asc" or ".tif").

        Returns
        -------
        bool
            True if any file was deleted, False if none existed
        """
        deleted = False
        for path in (self.get_path(sheet, ext), self.get_full_sheet_path(sheet, ext)):
            # Both paths are hardlinks of a version file (spec 3.2): unlink()
            # removes the path itself, the version in versions/ stays.
            if path.exists():
                path.unlink()
                # The metadata sidecar must not outlive the data file.
                path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
                deleted = True
        return deleted

    def list_files(self, pattern: str, *, versions: bool = False) -> list[Path]:
        """
        List all files matching pattern in storage directory.

        Searches within the segment (ADR-026). A segment template carrying
        `{system}` spans BOTH systems, so PL-1992 and PL-2000 files are listed
        together even though they live in separate directories.

        Parameters
        ----------
        pattern : str
            Explicit glob pattern, e.g. "**/*.asc" for NMT/NMPT sheets or
            "**/*.tif" for orthophotos.
        versions : bool, optional
            False (default): standard paths — without ``versions/``,
            ``full_sheet/`` and a 0.7.x ``kampanie/``. True: only version
            files in ``versions/`` (without the ``.incoming/`` staging area).

        Returns
        -------
        list[Path]
            List of matching file paths
        """
        files: list[Path] = []
        for root in self._segment_roots():
            if not root.exists():
                continue
            for p in root.glob(pattern):
                parts = p.relative_to(root).parts
                if versions:
                    if parts[:1] != (VERSIONS_DIR,) or INCOMING_DIR in parts:
                        continue
                elif parts[:1] in (
                    (VERSIONS_DIR,),
                    (FULL_SHEET_DIR,),
                    (_LEGACY_CAMPAIGNS_DIR,),
                ):
                    continue
                files.append(p)
        return files

    def _segment_roots(self) -> list[Path]:
        """Segment directories; a ``{system}`` template spans both PL systems."""
        template = self._subdir
        if "{system}" in template:
            names = [template.replace("{system}", u) for u in ("1992", "2000")]
        else:
            names = [template]
        return [self._output_dir / self._ensure_resolved(name) for name in names]

    def get_size(self, sheet: str, ext: str) -> int | None:
        """
        Get file size for given sheet code.

        Parameters
        ----------
        sheet : str
            Map sheet identifier
        ext : str, optional
            File extension including dot (default: ".asc")

        Returns
        -------
        int or None
            File size in bytes, or None if file doesn't exist
        """
        path = self.get_path(sheet, ext)
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
    provider,
    *,
    resolution: str | None,
    vertical_crs: str | None,
) -> FileStorage:
    """
    ``FileStorage`` of the segment where the provider's files land — the
    single place it is built (D18: CLI, ``DownloadManager``, PL cutout, CZ
    flow).

    The provider's source descriptor determines the segment, or
    ``resolution`` picks the PL NMT template when there is no descriptor.
    ``resolution`` is "1m" or "5m" for raster NMT, or None only where the
    segment has no resolution dimension (e.g. LAZ/orthophoto).
    ``vertical_crs`` is "EVRF2007", "KRON86", "Bpv", or None only where the
    segment has no vertical dimension (orthophoto). The provider's actual
    height system wins over an injected value. The optional variant
    (``storage_variant``: ortho CIR/B-W) is appended to the segment.
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
