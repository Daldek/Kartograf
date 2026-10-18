"""
Custom exceptions for Kartograf.

This module defines the core custom exceptions of the Kartograf package
(coordinate transformation errors live in ``kartograf.transform.crs``:
``TransformError``, ``TransformUnavailableError``). All of them inherit from
KartografError for easy catching of package-specific errors.

Every class carries machine-readable facts next to its message (spec 6.1):
a stable ``code`` (defined in the ``__dict__`` of EVERY class, never inherited
silently), the ``exit_code`` of the CLI, an optional ``hint`` set where the
error is raised and the ``details`` of the attributes listed in
``DETAIL_FIELDS``. ``kartograf.error_report.error_report`` turns an exception
into the ``kartograf-error/1`` document.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

from kartograf.serialization import encode


class KartografError(Exception):
    """
    Base exception for all Kartograf errors.

    All custom exceptions in this package inherit from this class,
    allowing users to catch all Kartograf-specific errors with a single except clause.

    Attributes
    ----------
    code : str
        Stable error code (``snake_case``); class attribute, defined by every
        class itself.
    exit_code : int
        Exit code of the CLI for this error (1 failure, 2 invalid input).
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

    code: ClassVar[str] = "kartograf_error"
    exit_code: ClassVar[int] = 1
    DETAIL_FIELDS: ClassVar[tuple[str, ...]] = ()
    DEFAULT_HINT: ClassVar[str | None] = None

    def __init__(self, *args: object, hint: str | None = None) -> None:
        super().__init__(*args)
        self.hint = hint

    def details(self) -> dict[str, object]:
        """The attributes of ``DETAIL_FIELDS`` as JSON-ready values.

        Empty values (``None``, empty text or collection) are left out;
        the others go through the encoder of ``kartograf.serialization``
        (tuples to lists, paths to absolute strings).
        """
        details: dict[str, object] = {}
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
    """A sequence of names as a tuple (a bare string is a mistake, not a name)."""
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

    code = "invalid_input"
    exit_code = 2
    DETAIL_FIELDS = ("option", "options", "allowed")

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
    """
    Wrong use of a command: an unknown command or flag, a missing positional
    argument, a value outside the allowed choices.

    Raised by the parser of the command catalog (``parse_command``, the CLI in
    the ``--json`` mode). A subclass of ``ValidationError``: wrong use is
    invalid input, so ``except ValidationError`` catches it too.
    """

    code = "usage_error"
    DEFAULT_HINT = "Parametry komendy: kartograf catalog <grupa> <komenda> --params"


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

    code = "invalid_sheet_code"
    DEFAULT_HINT = (
        "Formaty godel: PL-1992 N-34-130-D-d-2-4, PL-2000 6.179.12.20, "
        "SM5 CTES96, TM33 302_5550; wiecej: kartograf parse --help"
    )


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

    code = "download_failed"
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

    code = "no_coverage"
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

    code = "year_out_of_range"
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

    code = "cache_error"
    DEFAULT_HINT = "Wyczysc cache: kartograf cache clear"


class InvalidSidecarError(KartografError):
    """
    A ``kartograf-meta/1`` sidecar that cannot be read (``read_sidecar``,
    ADR-045): missing, not a JSON object, or another schema.

    ``iter_store`` never raises it: the store scan reports such a file as an
    entry with ``problem`` ``missing_sidecar``/``invalid_sidecar``.

    Attributes
    ----------
    path : Path
        The sidecar path (``<file>.meta.json``).
    """

    code = "invalid_sidecar"
    DETAIL_FIELDS = ("path",)
    DEFAULT_HINT = (
        "Podaj sciezke pliku danych magazynu albo jego sidecara "
        "<plik>.meta.json (kartograf-meta/1)"
    )

    def __init__(self, message: str, *, path: Path, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.path = path
