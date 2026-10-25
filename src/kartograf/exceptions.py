"""
Custom exceptions for Kartograf.

This module defines the core custom exceptions of the Kartograf package
(coordinate transformation errors live in ``kartograf.transform.crs``:
``TransformError``, ``TransformUnavailableError``). All of them inherit from
KartografError for easy catching of package-specific errors.

Every class carries machine-readable facts next to its message (ERR §3, AGI-4.3):
a ``code`` from the shared Nogat error registry (defined in the ``__dict__`` of
EVERY class, never inherited silently), the project-specific ``reason`` that
refines it (``details.reason``, snake_case English), the ``exit_code`` the registry
gives the code, an optional ``hint`` set where the error is raised and the
``details`` of the attributes listed in ``DETAIL_FIELDS``.
``kartograf.error_report.error_report`` turns an exception into the
``kartograf-error/1`` document.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar

from kartograf._errors import BY_CODE
from kartograf.messages import Lang, localize, message
from kartograf.serialization import encode


def registry_exit_code(code: str) -> int:
    """Return the exit code the Nogat error registry gives ``code``.

    Raises
    ------
    ValueError
        The code is not in the registry or has no exit code (REST-only codes).
    """
    entry = BY_CODE.get(code)
    if entry is None or entry.exit_code is None:
        raise ValueError(f"{code!r} is not a registry code with an exit code")
    return entry.exit_code


class KartografError(Exception):
    """
    Base exception for all Kartograf errors.

    All custom exceptions in this package inherit from this class,
    allowing users to catch all Kartograf-specific errors with a single except clause.

    Attributes
    ----------
    code : str
        Registry code (``validation_error``, ``no_data``, ...); class attribute,
        defined by every class itself.
    reason : str, optional
        Project-specific refinement of ``code`` (``invalid_sheet_code``,
        ``no_coverage``), reported as ``details.reason``: a class attribute of a
        class that has one reason, the ``reason`` argument of a class that has
        several (``ConflictError``).
    exit_code : int
        Exit code of the CLI for this error: the registry's exit code of ``code``
        (set when the class is created).
    DETAIL_FIELDS : tuple[str, ...]
        Names of the instance attributes reported by ``details()``.
    DEFAULT_HINT : str, optional
        Hint of the class when the instance has none.
    hint : str, optional
        Hint set where the error is raised (ASCII, one line).

    Examples
    --------
    >>> try:
    ...     # some kartograf operation
    ...     pass
    ... except KartografError as e:
    ...     print(f"Kartograf error: {e}")
    """

    code: ClassVar[str] = "internal_error"
    reason: str | None = None
    exit_code: ClassVar[int] = registry_exit_code("internal_error")
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ()
    DEFAULT_HINT: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give the class the exit code of its registry ``code``."""
        super().__init_subclass__(**kwargs)
        cls.exit_code = registry_exit_code(cls.code)

    def __init__(
        self,
        *args: object,
        hint: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.hint = hint
        if reason is not None:
            self.reason = reason

    def localized(self, lang: Lang) -> str:
        """Return the text of the exception in ``lang``.

        Parameters
        ----------
        lang : {"en", "pl"}
            The language of the person who reads it (``--lang`` of the CLI).

        Returns
        -------
        str
            The message of the catalog (``kartograf.messages``) the exception was
            raised with, rendered in ``lang``; any other text as it is.
        """
        first = self.args[0] if len(self.args) == 1 else None
        return localize(first, lang) if isinstance(first, str) else str(self)

    def details(self) -> dict[str, object]:
        """Return ``reason`` and the attributes of ``DETAIL_FIELDS`` as JSON values.

        Empty values (``None``, empty text or collection) are left out;
        the others go through the encoder of ``kartograf.serialization``
        (tuples to lists, paths to absolute strings). ``reason`` comes first.
        """
        details: dict[str, object] = {}
        if self.reason is not None:
            details["reason"] = self.reason
        for name in self.DETAIL_FIELDS:
            value = getattr(self, name, None)
            empty = value is None or (
                isinstance(value, str | tuple | list | dict | frozenset | set)
                and not value
            )
            if not empty:
                details[name] = encode(value)
        return details


def _names(value: Sequence[str] | None, argument: str) -> tuple[str, ...] | None:
    """Return a sequence of names as a tuple (a bare string is a mistake)."""
    if value is None:
        return None
    if isinstance(value, str):
        raise TypeError(f"{argument} must be a sequence of names, not a str")
    return tuple(value)


class ValidationError(KartografError):
    """
    Error validating input data.

    Raised when input data fails validation checks,
    such as invalid coordinate system or unsupported scale.

    Attributes
    ----------
    option : str, optional
        Name of the API argument the error is about (``vertical_crs``; the
        argument name, not the CLI flag).
    options : tuple[str, ...], optional
        Arguments in conflict or from which one is required
        (``("sheet", "bbox")``).
    allowed : tuple[str, ...], optional
        Allowed values of ``option``.
    reason : str
        ``invalid_input`` unless the raising code names another one for the
        instance (``exclusive_options``, ``store_only_option``; ADR-054).

    Examples
    --------
    >>> raise ValidationError("Invalid sheet system: '1965'. Must be '1992' or '2000'")
    >>> raise ValidationError(
    ...     "wrong sheet system", option="sheet_system", allowed=("1992", "2000")
    ... )
    """

    code = "validation_error"
    reason = "invalid_input"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("option", "options", "allowed")

    def __init__(
        self,
        message: str,
        *,
        option: str | None = None,
        options: Sequence[str] | None = None,
        allowed: Sequence[str] | None = None,
        hint: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, reason=reason)
        self.option = option
        self.options = _names(options, "options")
        self.allowed = _names(allowed, "allowed")


class UsageError(ValidationError):
    """Wrong use of a command.

    An unknown command or flag, a missing positional argument, a value outside the
    allowed choices.

    Raised by the parser of the command catalog (``parse_command``, the CLI in
    the ``--json`` mode). A subclass of ``ValidationError``: wrong use is
    invalid input, so ``except ValidationError`` catches it too.

    Attributes
    ----------
    command : str, optional
        Catalog id of the command whose line was wrong (``elevation download``),
        when the line named one that the parser knows: ``error_report`` takes
        the example of the hint from it.
    """

    code = "validation_error"
    reason = "usage"
    DEFAULT_HINT = message("errors.usage_default_hint")

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        option: str | None = None,
        options: Sequence[str] | None = None,
        allowed: Sequence[str] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message, option=option, options=options, allowed=allowed, hint=hint
        )
        self.command = command


class ParseError(ValidationError):
    """
    Error parsing sheet code string.

    Raised when a sheet code string cannot be parsed due to invalid format,
    unknown scale, a value outside the nomenclature range, or other parsing
    issues. A subclass of ``ValidationError`` (0.7.1): a bad sheet code is
    invalid input, so ``except ValidationError`` catches it too.

    Examples
    --------
    >>> raise ParseError("Invalid sheet code format: 'ABC-123'")
    """

    code = "validation_error"
    reason = "invalid_sheet_code"
    DEFAULT_HINT = message("errors.parse_default_hint")


class ConfigError(ValidationError):
    """
    The user settings cannot be used (DEV-18.1).

    Raised by ``kartograf.config.check_config`` for a ``nogat.toml`` that is
    unreadable, not UTF-8 text, not valid TOML or has a section that is not a
    table (or that ``NOGAT_CONFIG`` names but is missing), and for a setting
    whose value is not valid (``lang`` other than ``pl`` or ``en``). A
    subclass of ``ValidationError``: settings that cannot be used are invalid
    input, so ``except ValidationError`` catches it too. ``kartograf config
    show`` reports the same problem without raising.

    Attributes
    ----------
    path : Path, optional
        The settings file that cannot be used.
    value : str, optional
        The value of ``option`` that is not valid.

    Examples
    --------
    >>> raise ConfigError("nogat.toml is not UTF-8 text", option="NOGAT_CONFIG")
    """

    code = "validation_error"
    reason = "invalid_config"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("option", "value", "allowed", "path")
    DEFAULT_HINT = message("errors.config_default_hint")

    def __init__(
        self,
        message: str,
        *,
        option: str | None = None,
        path: Path | None = None,
        value: str | None = None,
        allowed: Sequence[str] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, option=option, allowed=allowed, hint=hint)
        self.path = path
        self.value = value


class DownloadError(KartografError):
    """
    Error downloading data from provider.

    Raised when data cannot be downloaded from the provider service,
    including network errors, HTTP errors, and timeout errors.

    Attributes
    ----------
    sheet : str, optional
        The sheet code that was being downloaded when the error occurred.
    status_code : int, optional
        HTTP status code if applicable.

    Examples
    --------
    >>> raise DownloadError("Failed to download N-34-130-D: Connection timeout")
    """

    code = "source_unavailable"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("sheet", "status_code")

    def __init__(
        self,
        message: str,
        sheet: str | None = None,
        status_code: int | None = None,
        *,
        hint: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(message, hint=hint, reason=reason)
        self.sheet = sheet
        self.status_code = status_code


class NoCoverageError(DownloadError):
    """
    The source has no data for the requested sheet.

    Raised when every index (skorowidz) layer answered and none of them
    contains the sheet — a state of the data, not a transport failure:
    retrying will not help. Raster builders (PL cutout, ADR-027 errata 1,
    2026-09-28) treat it as nodata; every other DownloadError stays fatal.

    Attributes
    ----------
    hints : tuple[str, ...]
        User-facing hints (e.g. ``use --scale 1:2000``), the same texts the
        message contains after the period; empty when there are none.
    reason : str
        ``no_coverage``; ``skipped_incomplete`` when the sheets of a plain write
        (``output_dir``) all lack a full flight in the year range (ADR-054 decision 5).
    """

    code = "no_data"
    reason = "no_coverage"
    DETAIL_FIELDS = ("sheet", "status_code", "hints")

    def __init__(
        self,
        message: str,
        sheet: str | None = None,
        status_code: int | None = None,
        hints: tuple[str, ...] = (),
        *,
        hint: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(
            message, sheet=sheet, status_code=status_code, hint=hint, reason=reason
        )
        self.hints = tuple(hints)


class YearRangeError(DownloadError):
    """
    Data exists, but not in the requested year range — raised before any download.

    Attributes
    ----------
    sheets : dict[str, tuple[int, ...]]
        Sheet code (LAZ: tile sheet code) -> every year the source has for it
        (ascending); only the conflicting sheets.
    min_year, max_year : int or None
        The requested range (closed; ``None`` = open side).
    hints : tuple[str, ...]
        Flag suggestions, the same texts as the message's ``Podpowiedz:`` line;
        empty when none applies.
    """

    code = "no_data"
    reason = "year_out_of_range"
    DETAIL_FIELDS = ("sheets", "min_year", "max_year", "hints")

    def __init__(
        self,
        message: str,
        *,
        sheets: Mapping[str, tuple[int, ...]],
        min_year: int | None,
        max_year: int | None,
        hints: tuple[str, ...] = (),
        hint: str | None = None,
    ):
        super().__init__(message, hint=hint)
        self.sheets = dict(sheets)
        self.min_year = min_year
        self.max_year = max_year
        self.hints = tuple(hints)


class CacheError(KartografError):
    """
    The metadata cache cannot be used (``MetadataCache(strict=True)``).

    Without ``strict`` an SQLite error disables the cache and the work goes
    on without it (``on_disabled``); in strict mode the same state raises
    this exception on the failing call and on every later one.
    """

    code = "store_unavailable"
    reason = "cache"
    DEFAULT_HINT = message("errors.cache_default_hint")


class InvalidSidecarError(KartografError):
    """A ``kartograf-meta/1`` sidecar that cannot be read (``read_sidecar``, ADR-045).

    Missing, not a JSON object, or another schema.

    ``iter_store`` never raises it: the store scan reports such a file as an
    entry with ``problem`` ``missing_sidecar``/``invalid_sidecar``.

    Attributes
    ----------
    path : Path
        The sidecar path (``<file>.meta.json``).
    """

    code = "data_error"
    reason = "invalid_sidecar"
    DETAIL_FIELDS = ("path",)
    DEFAULT_HINT = message("errors.sidecar_default_hint")

    def __init__(self, message: str, *, path: Path, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.path = path


class ForbiddenError(KartografError):
    """
    A call the server refuses (AGI-5.8, ERR registry ``forbidden``).

    Raised by the MCP server before anything is read or written: a path outside the
    directories the server allows (``--allow-dir``), or a write on a server that does
    not write (``--allow-writes``). The library functions never raise it.

    Attributes
    ----------
    option : str, optional
        Name of the argument that was refused (``root``, ``update``).
    path : Path, optional
        The resolved path that lies outside the allowed directories.
    allowed : tuple[str, ...], optional
        The directories the server allows.

    Examples
    --------
    >>> raise ForbiddenError(
    ...     "root lies outside the allowed directories",
    ...     option="root",
    ...     path=Path("/tmp/x"),
    ...     allowed=["/data"],
    ... )
    """

    code = "forbidden"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("option", "path", "allowed")

    def __init__(
        self,
        message: str,
        *,
        option: str | None = None,
        path: Path | None = None,
        allowed: Sequence[str] | None = None,
        hint: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, reason=reason)
        self.option = option
        self.path = path
        self.allowed = _names(allowed, "allowed")


class MissingDependencyError(KartografError):
    """
    An optional extra is not installed (DEV-6.5).

    Raised where a feature needs a package that only an extra brings (the MCP server
    needs ``kartograf[mcp]``). The hint names the command that installs the extra.

    Attributes
    ----------
    extra : str, optional
        Name of the extra (``mcp``); without a ``hint`` the hint is ``uv add
        "kartograf[<extra>]"``.

    Examples
    --------
    >>> raise MissingDependencyError("the MCP server needs mcp", extra="mcp")
    """

    code = "missing_dependency"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("extra",)

    def __init__(
        self, message: str, *, extra: str | None = None, hint: str | None = None
    ) -> None:
        if hint is None and extra is not None:
            hint = f'uv add "kartograf[{extra}]"'
        super().__init__(message, hint=hint)
        self.extra = extra


class ConflictError(KartografError):
    """
    The state of the target forbids the write (ERR registry ``conflict``, ADR-054).

    Raised before the first byte of a write: an output file that exists (``--force``
    replaces it), two targets of one name, a plain directory that is or lies in a
    store, a store inside another store, a store root that is not empty. A plan
    (``--check``) does not raise it: it lists the conflict.

    Attributes
    ----------
    reason : str
        ``output_exists``, ``duplicate_output_name``, ``output_in_store``,
        ``nested_store`` or ``not_empty`` (``details.reason``).
    path : Path, optional
        The directory or root the error is about.
    paths : tuple[str, ...], optional
        Every target that is in conflict, not only the first.

    Examples
    --------
    >>> raise ConflictError(
    ...     "2 targets exist",
    ...     reason="output_exists",
    ...     paths=["out/a.asc", "out/b.asc"],
    ... )
    """

    code = "conflict"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("path", "paths")

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        path: Path | None = None,
        paths: Sequence[str] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, reason=reason)
        self.path = path
        self.paths = _names(paths, "paths")


class StoreUnavailableError(KartografError):
    """
    A store root that cannot be written as it is (ERR registry ``store_unavailable``).

    Raised for a root that has the layout of a store but no marker
    (``kartograf-store.json``): ``kartograf store init`` verifies the layout and
    writes the marker.

    Attributes
    ----------
    reason : str
        ``no_marker`` (``details.reason``).
    path : Path, optional
        The store root.

    Examples
    --------
    >>> raise StoreUnavailableError(
    ...     "data has the layout of a store but no kartograf-store.json",
    ...     reason="no_marker",
    ...     path=Path("data"),
    ... )
    """

    code = "store_unavailable"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("path",)

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        path: Path | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint, reason=reason)
        self.path = path


class InvalidLayoutError(KartografError):
    """
    A root that is not the layout of a Kartograf store (``kartograf store init``).

    Raised when a root without a marker is verified before one is written, and when a
    marker is not a ``kartograf-store/1`` document.

    Attributes
    ----------
    path : Path
        The store root.
    problems : tuple[str, ...]
        What is wrong, at most 20 entries.

    Examples
    --------
    >>> raise InvalidLayoutError(
    ...     "data is not a Kartograf store: 1 problem",
    ...     path=Path("data"),
    ...     problems=["unexpected entry 'notes.txt' at the top level"],
    ... )
    """

    code = "data_error"
    reason = "invalid_layout"
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ("path", "problems")

    def __init__(
        self,
        message: str,
        *,
        path: Path,
        problems: Sequence[str],
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint)
        self.path = path
        self.problems = _names(problems, "problems")
