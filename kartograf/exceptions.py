"""
Custom exceptions for Kartograf.

This module defines the core custom exceptions of the Kartograf package
(coordinate transformation errors live in ``kartograf.transform.crs``:
``TransformError``, ``TransformUnavailableError``). All of them inherit from
KartografError for easy catching of package-specific errors.
"""

from collections.abc import Mapping


class KartografError(Exception):
    """
    Base exception for all Kartograf errors.

    All custom exceptions in this package inherit from this class,
    allowing users to catch all Kartograf-specific errors with a single except clause.

    Examples
    --------
    >>> try:
    ...     # some kartograf operation
    ...     pass
    ... except KartografError as e:
    ...     print(f"Kartograf error: {e}")
    """

    pass


class ValidationError(KartografError):
    """
    Error validating input data.

    Raised when input data fails validation checks,
    such as invalid coordinate system or unsupported scale.

    Examples
    --------
    >>> raise ValidationError("Invalid układ: '1965'. Must be '1992' or '2000'")
    """

    pass


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

    pass


class DownloadError(KartografError):
    """
    Error downloading data from provider.

    Raised when data cannot be downloaded from the provider service,
    including network errors, HTTP errors, and timeout errors.

    Attributes
    ----------
    godlo : str, optional
        The sheet code that was being downloaded when the error occurred.
    status_code : int, optional
        HTTP status code if applicable.

    Examples
    --------
    >>> raise DownloadError("Failed to download N-34-130-D: Connection timeout")
    """

    def __init__(
        self,
        message: str,
        godlo: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.godlo = godlo
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

    def __init__(
        self,
        message: str,
        godlo: str | None = None,
        status_code: int | None = None,
        hints: tuple[str, ...] = (),
    ):
        super().__init__(message, godlo=godlo, status_code=status_code)
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

    def __init__(
        self,
        message: str,
        *,
        sheets: Mapping[str, tuple[int, ...]],
        min_year: int | None,
        max_year: int | None,
        hints: tuple[str, ...] = (),
    ):
        super().__init__(message)
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
