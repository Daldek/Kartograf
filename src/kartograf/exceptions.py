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
        ``no_coverage``); class attribute, reported as ``details.reason``.
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
    reason: ClassVar[str | None] = None
    exit_code: ClassVar[int] = registry_exit_code("internal_error")
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ()
    DEFAULT_HINT: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give the class the exit code of its registry ``code``."""
        super().__init_subclass__(**kwargs)
        cls.exit_code = registry_exit_code(cls.code)

    def __init__(self, *args: object, hint: str | None = None) -> None:
        super().__init__(*args)
        self.hint = hint

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

    Examples
    --------
    >>> raise ValidationError("Invalid układ: '1965'. Must be '1992' or '2000'")
    >>> raise ValidationError(
    ...     "zly uklad", option="sheet_system", allowed=("1992", "2000")
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
    ) -> None:
        super().__init__(message, hint=hint)
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
    DEFAULT_HINT = "Parametry komendy: kartograf catalog <grupa> <komenda> --params"

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
    >>> raise ParseError("Invalid godło format: 'ABC-123'")
    """

    code = "validation_error"
    reason = "invalid_sheet_code"
    DEFAULT_HINT = (
        "Formaty godel: PL-1992 N-34-130-D-d-2-4, PL-2000 6.179.12.20, "
        "SM5 CTES96, TM33 302_5550; wiecej: kartograf parse --help"
    )


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
    DEFAULT_HINT = (
        "Fix or remove the settings file, or point NOGAT_CONFIG at another one; "
        "kartograf config show reports the problem"
    )

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
    ):
        super().__init__(message, hint=hint)
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
    ):
        super().__init__(message, sheet=sheet, status_code=status_code, hint=hint)
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
    DEFAULT_HINT = "Wyczysc cache: kartograf cache clear"


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
    DEFAULT_HINT = (
        "Podaj sciezke pliku danych magazynu albo jego sidecara "
        "<plik>.meta.json (kartograf-meta/1)"
    )

    def __init__(self, message: str, *, path: Path, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.path = path
