"""
The ``kartograf-error/1`` document: an exception as data (spec 6).

``error_report(exc)`` turns any exception into an :class:`ErrorReport` with a
stable ``code``, the exit code of the CLI, a one-line ``hint`` and the
``details`` of the exception. Three codes belong to no class of the package
hierarchy and are built here: ``io_error`` (``OSError``: a missing or
unavailable directory or file), ``interrupted`` (``KeyboardInterrupt``) and
``internal_error`` (any other exception: a program error).

``ERROR_CODES`` and ``EXIT_CODES`` are the single source of the two tables of
``docs/USAGE.md`` and of the command catalog (``errors``, ``exit_codes``).
"""

import errno
import os
from collections.abc import Sequence
from dataclasses import dataclass, field

from kartograf.exceptions import (
    KartografError,
    NoCoverageError,
    ValidationError,
    YearRangeError,
)
from kartograf.serialization import Document
from kartograf.transform.crs import TransformUnavailableError

HINT_MAX_CHARS = 400
ALLOWED_HINT_MAX_VALUES = 40


@dataclass(frozen=True)
class ErrorCodeSpec:
    """A row of the error code table: the exception class and its meaning."""

    code: str
    exception: str
    exit_code: int
    meaning: str


@dataclass(frozen=True)
class ExitCodeSpec:
    """A row of the exit code table of the CLI."""

    code: int
    name: str
    meaning: str


ERROR_CODES: tuple[ErrorCodeSpec, ...] = (
    ErrorCodeSpec(
        "kartograf_error",
        "KartografError",
        1,
        "blad pakietu bez dokladniejszej klasy",
    ),
    ErrorCodeSpec(
        "invalid_input",
        "ValidationError",
        2,
        "bledna wartosc albo kombinacja argumentow, brak wymaganego argumentu, "
        "bledny plik wejsciowy (plan, manifest, geometria)",
    ),
    ErrorCodeSpec(
        "usage_error",
        "UsageError",
        2,
        "bledne uzycie komendy: nieznana komenda albo flaga, brak argumentu "
        "pozycyjnego, wartosc spoza dozwolonych",
    ),
    ErrorCodeSpec(
        "invalid_sheet_code",
        "ParseError",
        2,
        "godlo nie jest godlem PL ani CZ albo lezy poza nomenklatura",
    ),
    ErrorCodeSpec(
        "download_failed",
        "DownloadError",
        1,
        "siec, HTTP, timeout albo odpowiedz zrodla",
    ),
    ErrorCodeSpec(
        "no_coverage",
        "NoCoverageError",
        1,
        "zrodlo nie ma danych dla arkusza (stan danych, ponowienie nie pomoze)",
    ),
    ErrorCodeSpec(
        "year_out_of_range",
        "YearRangeError",
        1,
        "dane sa, ale poza przedzialem lat (wykryte przed pobraniem)",
    ),
    ErrorCodeSpec(
        "cache_error",
        "CacheError",
        1,
        "cache metadanych niedostepny, zablokowany albo nieczytelny",
    ),
    ErrorCodeSpec(
        "invalid_sidecar",
        "InvalidSidecarError",
        1,
        "sidecar kartograf-meta/1 nie istnieje, jest nieczytelny albo ma inny schemat",
    ),
    ErrorCodeSpec(
        "transform_failed",
        "TransformError",
        1,
        "blad przeliczenia wspolrzednych (np. wynik nieskonczony)",
    ),
    ErrorCodeSpec(
        "transform_unavailable",
        "TransformUnavailableError",
        1,
        "brak bezpiecznej operacji dla pary ukladow",
    ),
    ErrorCodeSpec(
        "io_error",
        "OSError",
        1,
        "katalog albo plik niedostepny: brak, uprawnienia, brak miejsca, "
        "odlaczony udzial",
    ),
    ErrorCodeSpec(
        "interrupted",
        "KeyboardInterrupt",
        130,
        "przerwane przez uzytkownika (Ctrl-C)",
    ),
    ErrorCodeSpec(
        "internal_error",
        "Exception",
        1,
        "blad programu: kazdy inny wyjatek poza OSError",
    ),
)

EXIT_CODES: tuple[ExitCodeSpec, ...] = (
    ExitCodeSpec(
        0,
        "ok",
        "komenda wykonana; dokument wyniku z ok: true albo dokument bez pola ok",
    ),
    ExitCodeSpec(
        1,
        "failed",
        "brak kompletnego wyniku: blad zrodla, sieci, cache, magazynu, blad "
        "programu, albo ok: false",
    ),
    ExitCodeSpec(
        2,
        "usage",
        "bledne uzycie albo bledne dane wejsciowe: argparse, ValidationError, "
        "ParseError, UsageError",
    ),
    ExitCodeSpec(
        130,
        "interrupted",
        "przerwane przez uzytkownika (128 + SIGINT); wersje sa zatwierdzane "
        "atomowo, brak polowicznych plikow",
    ),
)

INTERRUPTED_MESSAGE = "przerwano (Ctrl-C)"
INTERNAL_ERROR_HINT = (
    "Zglos blad z komenda i wersja; KARTOGRAF_DEBUG=1 pokazuje traceback"
)
IO_ERROR_HINT = "Sprawdz sciezke i uprawnienia: {path}"
IO_ERROR_HINT_NO_PATH = "Sprawdz sciezki i uprawnienia katalogow z argumentow"


@dataclass(frozen=True)
class ErrorReport(Document):
    """The failure of a command as a document (``kartograf-error/1``).

    ``message`` is what the CLI prints after ``Error: ``; ``hint`` is one ASCII
    line of at most 400 characters or ``None``; ``exception`` is the class
    name; ``command`` is the catalog id of the failed command (known to the
    CLI and the MCP server, ``None`` for a plain library call); ``details`` is
    ``exc.details()`` (for ``OSError``: ``errno`` as a symbolic name and
    ``path``), ``{}`` when there is nothing to tell.
    """

    SCHEMA = "kartograf-error/1"
    JSON_KEYS = (
        "code",
        "message",
        "hint",
        "exception",
        "exit_code",
        "command",
        "details",
    )

    code: str
    message: str
    hint: str | None
    exception: str
    exit_code: int
    command: str | None = None
    details: dict[str, object] = field(default_factory=dict)


def allowed_values_hint(flag: str, allowed: Sequence[str]) -> str:
    """``Dozwolone wartosci <flag>: a, b, c.`` (at most 40 values, then ``...``)."""
    shown = ", ".join(allowed[:ALLOWED_HINT_MAX_VALUES])
    if len(allowed) > ALLOWED_HINT_MAX_VALUES:
        return f"Dozwolone wartosci {flag}: {shown}, ..."
    return f"Dozwolone wartosci {flag}: {shown}."


def _one_line(text: str) -> str:
    """ASCII, one line, at most ``HINT_MAX_CHARS`` characters (cut with ``...``)."""
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    text = " ".join(text.split())
    if len(text) > HINT_MAX_CHARS:
        text = text[: HINT_MAX_CHARS - 3] + "..."
    return text


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _option_hint(
    option: str, allowed: Sequence[str] | None, command: str | None
) -> str | None:
    """The hint of a ``ValidationError`` that names an argument (spec 6.3, step
    3): the allowed values with the CLI flag of the argument and an example
    command line of the catalog that uses it.

    The flag and the example need the command (``command``); without it the flag
    is the name of the argument and there is no example. The example is left
    out when the hint would pass ``HINT_MAX_CHARS`` with it.
    """
    from kartograf.catalog.hints import example_for  # loads the declarations

    flag, line = example_for(command, option)
    text = allowed_values_hint(flag or option, allowed) if allowed else ""
    if line:
        candidate = f"{text} Przyklad: {line}".strip()
        if len(candidate) <= HINT_MAX_CHARS:
            return candidate
    return text or None


def _library_hint(exc: KartografError, command: str | None) -> str | None:
    """The hint of an exception of the package hierarchy (spec 6.3, steps 1-3)."""
    if exc.hint:
        return exc.hint
    if isinstance(exc, NoCoverageError | YearRangeError) and exc.hints:
        return "; ".join(exc.hints)
    if isinstance(exc, TransformUnavailableError) and exc.remedy:
        return exc.remedy
    if exc.DEFAULT_HINT:
        return exc.DEFAULT_HINT
    if isinstance(exc, ValidationError) and exc.option:
        return _option_hint(exc.option, exc.allowed, command)
    return None


def _io_path(exc: OSError) -> str | None:
    """The file name of an ``OSError`` as text (``None``: it has none)."""
    filename = exc.filename
    if isinstance(filename, bytes):
        return os.fsdecode(filename)
    if isinstance(filename, str | os.PathLike):
        return os.fspath(filename)
    return None


def _io_details(exc: OSError) -> dict[str, object]:
    details: dict[str, object] = {}
    if exc.errno is not None:
        details["errno"] = errno.errorcode.get(exc.errno, str(exc.errno))
    path = _io_path(exc)
    if path:
        details["path"] = path
    return details


def error_report(exc: BaseException, *, command: str | None = None) -> ErrorReport:
    """Describe an exception as an :class:`ErrorReport`.

    Parameters
    ----------
    exc : BaseException
        Any exception: a ``KartografError`` keeps its ``code``, ``exit_code``,
        ``hint`` and ``details``; ``KeyboardInterrupt`` is ``interrupted``
        (130), ``OSError`` is ``io_error`` and every other exception is
        ``internal_error`` (a program error; both exit with 1).
    command : str, optional
        Catalog id of the command that failed (``elevation download``).
    """
    if isinstance(exc, KartografError):
        return ErrorReport(
            code=exc.code,
            message=str(exc),
            hint=_hint_or_none(_library_hint(exc, command)),
            exception=type(exc).__name__,
            exit_code=exc.exit_code,
            command=command,
            details=exc.details(),
        )
    if isinstance(exc, KeyboardInterrupt):
        return ErrorReport(
            code="interrupted",
            message=INTERRUPTED_MESSAGE,
            hint=None,
            exception=type(exc).__name__,
            exit_code=130,
            command=command,
        )
    message = _ascii(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, OSError):
        path = _io_path(exc)
        hint = IO_ERROR_HINT.format(path=path) if path else IO_ERROR_HINT_NO_PATH
        return ErrorReport(
            code="io_error",
            message=message,
            hint=_one_line(hint),
            exception=type(exc).__name__,
            exit_code=1,
            command=command,
            details=_io_details(exc),
        )
    return ErrorReport(
        code="internal_error",
        message=message,
        hint=INTERNAL_ERROR_HINT,
        exception=type(exc).__name__,
        exit_code=1,
        command=command,
    )


def _hint_or_none(text: str | None) -> str | None:
    return None if text is None else _one_line(text)
