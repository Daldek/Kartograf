"""
Custom exceptions for Kartograf.

This module defines the core custom exceptions of the Kartograf package
(coordinate transformation errors live in ``kartograf.transform.crs``:
``TransformError``, ``TransformUnavailableError``). All of them inherit from
KartografError for easy catching of package-specific errors.
"""


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


class ParseError(KartografError):
    """
    Error parsing sheet code string.

    Raised when a sheet code string cannot be parsed due to invalid format,
    unknown scale, or other parsing issues.

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


class GridMismatchError(ValidationError):
    """
    Mosaic sources lie on different pixel grids (S5).

    Raised by ``transport.mosaic.mosaic_and_crop(snap_to_source_grid=True)``
    and by the PL cutout for ``EPSG:2180`` when at least one source raster
    is shifted by a fraction of a pixel against the reference grid: copying
    pixels 1:1 (R1) is impossible without resampling. Sources on the same
    grid within float noise (1e-6 px) are not a mismatch.

    Attributes
    ----------
    off_grid : tuple[OffGridSource, ...]
        Every off-grid source with its shift in pixels
        (``transport.mosaic.OffGridSource``: ``path``, ``dx_px``, ``dy_px``).
    """

    def __init__(self, message: str, off_grid: tuple = ()):
        super().__init__(message)
        self.off_grid = off_grid
