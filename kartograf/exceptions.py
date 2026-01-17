"""
Custom exceptions for Kartograf.

This module defines all custom exceptions used throughout the Kartograf package.
All exceptions inherit from KartografError for easy catching of package-specific errors.
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
    Error parsing godło string.

    Raised when a godło string cannot be parsed due to invalid format,
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
        The godło that was being downloaded when the error occurred.
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
