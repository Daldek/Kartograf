"""
The ``kartograf-error/1`` document: an exception as data (AGI-4.3, ERR-4).

``error_report(exc)`` turns any exception into an :class:`ErrorReport`: the
registry ``code`` with its English ``title``, the ``message``, a one-line
``hint``, the ``details`` (``reason`` first), the exit code of the registry and
the command. Four cases belong to no class of the package hierarchy and are
built here: ``OSError`` (``io_error``: a missing or unavailable directory or
file), ``KeyboardInterrupt`` (``cancelled``: Ctrl-C),
``kartograf.interrupt.Terminated`` (``terminated``: SIGTERM) and any other
exception (``internal_error``: a program error).

``ERROR_CODES`` and ``EXIT_CODES`` are the single source of the two tables of
``docs/USAGE.md`` and of the command catalog (``errors``, ``exit_codes``).
"""

import errno
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from kartograf._errors import BY_CODE, OUTCOME_MEANINGS, OUTCOMES
from kartograf.exceptions import (
    KartografError,
    NoCoverageError,
    UsageError,
    ValidationError,
    YearRangeError,
    registry_exit_code,
)
from kartograf.interrupt import Terminated
from kartograf.messages import DEFAULT_LANG, Lang, Message, localize, message
from kartograf.serialization import Document
from kartograf.transform.crs import TransformUnavailableError

HINT_MAX_CHARS = 400
ALLOWED_HINT_MAX_VALUES = 40


@dataclass(frozen=True)
class ErrorCodeSpec:
    """A row of the error table: an exception class and what it reports.

    ``code`` is the registry code, ``reason`` its refinement in
    ``details.reason`` (``None``: none) and ``exit_code`` the exit code the
    registry gives ``code``.
    """

    exception: str
    code: str
    reason: str | None
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
        "KartografError",
        "internal_error",
        None,
        1,
        "package error without a more precise class",
    ),
    ErrorCodeSpec(
        "ValidationError",
        "validation_error",
        "invalid_input",
        2,
        "wrong value or combination of arguments, a missing required argument, "
        "an invalid input file (plan, geometry); reasons that refine it: "
        "exclusive_options (output_dir with root) and store_only_option (an option "
        "that needs the store, with output_dir)",
    ),
    ErrorCodeSpec(
        "UsageError",
        "validation_error",
        "usage",
        2,
        "wrong use of a command: unknown command or flag, a missing positional "
        "argument, a value outside the allowed choices",
    ),
    ErrorCodeSpec(
        "ParseError",
        "validation_error",
        "invalid_sheet_code",
        2,
        "the sheet code is not a PL or CZ code or lies outside the nomenclature",
    ),
    ErrorCodeSpec(
        "ConfigError",
        "validation_error",
        "invalid_config",
        2,
        "the user settings cannot be used: nogat.toml is unreadable, not UTF-8 "
        "text, not valid TOML or has a section that is not a table, or a setting "
        "has a value that is not valid",
    ),
    ErrorCodeSpec(
        "DownloadError",
        "source_unavailable",
        None,
        5,
        "network, HTTP, timeout or the response of the source",
    ),
    ErrorCodeSpec(
        "NoCoverageError",
        "no_data",
        "no_coverage",
        14,
        "the source has no data for the sheet (a state of the data, retrying "
        "does not help)",
    ),
    ErrorCodeSpec(
        "YearRangeError",
        "no_data",
        "year_out_of_range",
        14,
        "data exists but not in the requested year range (found before any download)",
    ),
    ErrorCodeSpec(
        "CacheError",
        "store_unavailable",
        "cache",
        8,
        "the metadata cache is unavailable, locked or unreadable",
    ),
    ErrorCodeSpec(
        "StoreUnavailableError",
        "store_unavailable",
        None,
        8,
        "the store root has the layout of a store but no kartograf-store.json "
        "(reason no_marker: kartograf store init verifies the layout and writes it)",
    ),
    ErrorCodeSpec(
        "InvalidSidecarError",
        "data_error",
        "invalid_sidecar",
        7,
        "the kartograf-meta/1 sidecar is missing, unreadable or of another schema, "
        "or a field command_for_file reads has a value of a wrong form",
    ),
    ErrorCodeSpec(
        "InvalidLayoutError",
        "data_error",
        "invalid_layout",
        7,
        "a root without a marker is not the layout of a Kartograf store, or the "
        "marker is not a kartograf-store/1 document (details.problems lists what "
        "is wrong)",
    ),
    ErrorCodeSpec(
        "ConflictError",
        "conflict",
        None,
        4,
        "the target forbids the write (reasons: output_exists, "
        "duplicate_output_name, output_in_store, nested_store, not_empty): an "
        "output file that exists, two targets of one name, a plain directory in a "
        "store, a store in another store or a store root that is not empty",
    ),
    ErrorCodeSpec(
        "MissingDependencyError",
        "missing_dependency",
        None,
        6,
        "an optional extra is not installed (kartograf[mcp] for the MCP server); "
        'the hint names the install command (uv add "kartograf[mcp]")',
    ),
    ErrorCodeSpec(
        "ForbiddenError",
        "forbidden",
        None,
        12,
        "the MCP server refuses the call: a path outside its allowed directories "
        "(--allow-dir), or a write on a server that does not write (--allow-writes)",
    ),
    ErrorCodeSpec(
        "TransformError",
        "calculation_error",
        "transform_failed",
        13,
        "coordinate transformation failed (for example an infinite result)",
    ),
    ErrorCodeSpec(
        "TransformUnavailableError",
        "unsupported",
        "transform_unavailable",
        15,
        "no safe operation for the pair of coordinate systems",
    ),
    ErrorCodeSpec(
        "CommandNotRebuildableError",
        "unsupported",
        "command_not_rebuildable",
        15,
        "command_for_file: no command selects the stored file again (details.family; "
        "details.field names a missing sidecar field): a land cover, soil or "
        "collection file chosen by an area, soil hsg, a reprojected PL cutout",
    ),
    ErrorCodeSpec(
        "OSError",
        "io_error",
        None,
        9,
        "directory or file unavailable: missing, permissions, no space, "
        "disconnected share",
    ),
    ErrorCodeSpec(
        "KeyboardInterrupt",
        "cancelled",
        None,
        130,
        "cancelled by the user (Ctrl-C); versions are committed atomically, so "
        "units unfinished at the interrupt (also those queued with --workers > 1) "
        "do not exist and no half-written file is left",
    ),
    ErrorCodeSpec(
        "Terminated",
        "terminated",
        None,
        143,
        "terminated by SIGTERM (timeout, docker stop, kill): cleanup as after Ctrl-C",
    ),
    ErrorCodeSpec(
        "Exception",
        "internal_error",
        None,
        1,
        "program error: any other exception except OSError",
    ),
)


def _exit_codes() -> tuple[ExitCodeSpec, ...]:
    """Return the exit codes of the outcomes and of ``ERROR_CODES``, by number.

    The outcomes ``ok``, ``partial`` and ``failed`` (0, 10, 11) are named by their
    status, every other code by the registry code that owns it; the meaning is the
    one of the registry. The outcome ``cancelled`` is the error ``cancelled`` (130).
    """
    rows = {
        code: ExitCodeSpec(code, status, OUTCOME_MEANINGS[status])
        for status, code in OUTCOMES.items()
        if status != "cancelled"
    }
    for row in ERROR_CODES:
        rows.setdefault(
            row.exit_code,
            ExitCodeSpec(row.exit_code, row.code, BY_CODE[row.code].meaning),
        )
    return tuple(rows[number] for number in sorted(rows))


EXIT_CODES: tuple[ExitCodeSpec, ...] = _exit_codes()


@dataclass(frozen=True)
class ErrorReport(Document):
    """The failure of a command as a document (``kartograf-error/1``, AGI-4.3).

    ``code`` is a registry code and ``title`` its English title; ``message`` is
    what the CLI prints after ``Error: ``; ``hint`` is one ASCII line of at most
    400 characters or ``None`` (then the key is left out of the document);
    ``exit_code`` is the exit code of the registry; ``command`` is the catalog id
    of the failed command (known to the CLI and the MCP server, ``None`` for a
    plain library call, or the command a ``UsageError`` names; left out of the
    document when ``None``); ``details`` is ``exc.details()`` (``reason`` first;
    for ``OSError``: ``errno`` as a symbolic name and ``path``), ``{}`` when
    there is nothing to tell.
    """

    SCHEMA = "kartograf-error/1"
    JSON_KEYS = (
        "code",
        "title",
        "message",
        "hint",
        "details",
        "exit_code",
        "command",
    )

    code: str
    title: str
    message: str
    hint: str | None
    exit_code: int
    command: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return the document; ``hint`` and ``command`` are left out when ``None``."""
        document = super().to_dict()
        for key in ("hint", "command"):
            if document[key] is None:
                del document[key]
        return document


def error_line(report: ErrorReport) -> str:
    """Return the error document as the one line the CLI ends stderr with (AGI-3.3).

    Compact JSON and ASCII: a non-ASCII character is a JSON escape (``u`` and four
    hex digits), which every JSON reader resolves, because stderr has whatever
    encoding the terminal or the pipe has and an error must never fail to be
    reported.
    """
    return json.dumps(
        report.to_dict(), ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )


def allowed_values_hint(
    flag: str, allowed: Sequence[str], lang: Lang = DEFAULT_LANG
) -> Message:
    """Return ``Allowed values of <flag>: a, b, c.`` (up to 40, then ``...``)."""
    shown = ", ".join(allowed[:ALLOWED_HINT_MAX_VALUES])
    if len(allowed) > ALLOWED_HINT_MAX_VALUES:
        return message("errors.allowed_values_cut", lang, flag=flag, values=shown)
    return message("errors.allowed_values", lang, flag=flag, values=shown)


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
    option: str,
    allowed: Sequence[str] | None,
    command: str | None,
    given: Mapping[str, object] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> str | None:
    """Return the hint of a ``ValidationError`` that names an argument.

    Spec 6.3, step 3: the allowed values with the CLI flag of the argument and an
    example command line of the catalog that uses it (of the product of the call,
    ``given``).

    The flag and the example need the command (``command``); without it the flag
    is the name of the argument and there is no example. The example is left
    out when the hint would pass ``HINT_MAX_CHARS`` with it.
    """
    from kartograf.catalog.hints import example_for  # loads the declarations

    flag, line = example_for(command, option, given)
    text = allowed_values_hint(flag or option, allowed, lang) if allowed else ""
    if line:
        example = message("errors.example", lang, line=line)
        candidate = f"{text} {example}".strip()
        if len(candidate) <= HINT_MAX_CHARS:
            return candidate
    return text or None


def _options_hint(
    options: Sequence[str],
    command: str | None,
    given: Mapping[str, object] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> str:
    """Return the hint of a ``ValidationError`` that names several arguments.

    The area is missing (``sheet``, ``bbox``, ``geometry``) or two arguments
    exclude each other: their CLI flags and an example command line of the catalog
    that uses the first of them (of the product of the call, ``given``).

    Without the command (or for an argument it does not have) the name of the
    argument stands for the flag and there is no example; the example is left
    out when the hint would pass ``HINT_MAX_CHARS`` with it.
    """
    from kartograf.catalog.hints import example_for  # loads the declarations

    flags = [example_for(command, name)[0] or name for name in options]
    text = str(message("errors.options", lang, flags=", ".join(flags)))
    _, line = example_for(command, options[0], given)
    if line:
        candidate = f"{text} {message('errors.example', lang, line=line)}"
        if len(candidate) <= HINT_MAX_CHARS:
            return candidate
    return text


def _usage_hint(command: str | None, lang: Lang = DEFAULT_LANG) -> str | None:
    """Return the hint of a ``UsageError`` about a command of the catalog.

    Where its parameters are and an example line (``None`` for an unknown command).
    """
    from kartograf.catalog.hints import usage_hint  # loads the declarations

    return usage_hint(command, max_chars=HINT_MAX_CHARS, lang=lang)


def _library_hint(
    exc: KartografError,
    command: str | None,
    given: Mapping[str, object] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> str | None:
    """Return the hint of an exception of the package hierarchy (spec 6.3, 1-3)."""
    if exc.hint:
        return localize(exc.hint, lang)
    if isinstance(exc, NoCoverageError | YearRangeError) and exc.hints:
        return "; ".join(localize(hint, lang) for hint in exc.hints)
    if isinstance(exc, TransformUnavailableError) and exc.remedy:
        return localize(exc.remedy, lang)
    if isinstance(exc, UsageError):
        # the command whose line was wrong, else the command that was run
        usage = _usage_hint(exc.command or command, lang)
        if usage:
            return usage
    if exc.DEFAULT_HINT:
        return localize(exc.DEFAULT_HINT, lang)
    if isinstance(exc, ValidationError):
        if exc.option:
            return _option_hint(exc.option, exc.allowed, command, given, lang)
        if exc.options:
            return _options_hint(exc.options, command, given, lang)
    return None


def _io_path(exc: OSError) -> str | None:
    """Return the file name of an ``OSError`` as text (``None``: it has none)."""
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


def _report(
    code: str,
    text: str,
    *,
    hint: str | None = None,
    command: str | None = None,
    details: dict[str, object] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> ErrorReport:
    """Return the report of a registry ``code`` (its title and exit code)."""
    entry = BY_CODE[code]
    return ErrorReport(
        code=code,
        title=entry.title_pl if lang == "pl" else entry.title,
        message=text,
        hint=hint,
        exit_code=registry_exit_code(code),
        command=command,
        details={} if details is None else details,
    )


def error_report(
    exc: BaseException,
    *,
    command: str | None = None,
    given: Mapping[str, object] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> ErrorReport:
    """Describe an exception as an :class:`ErrorReport`.

    Parameters
    ----------
    exc : BaseException
        Any exception: a ``KartografError`` keeps its ``code``, ``exit_code``,
        ``hint`` and ``details`` (``reason`` first); ``KeyboardInterrupt`` is
        ``cancelled`` (130), ``Terminated`` (SIGTERM) is ``terminated`` (143),
        ``OSError`` is ``io_error`` (9) and every other exception is
        ``internal_error`` (a program error, 1).
    command : str, optional
        Catalog id of the command that failed (``elevation download``); without
        it the command a ``UsageError`` names. The hint of a ``UsageError`` is
        about the command whose line was wrong (``exc.command``), else about this
        one.
    given : mapping, optional
        The arguments of the failed call by their names (what the CLI parsed or
        an MCP tool was given). The example of the hint of an invalid argument
        is then the one of the ``product`` of the call, of its ``country`` and
        of the way it chose the area (``kartograf.catalog.hints.example_for``);
        without it the example is the first one that shows the argument.
    lang : {"en", "pl"}, optional
        Language of the ``title``, the ``message`` and the ``hint``: English, as
        every machine surface has it (AGI-9.2), unless a person asked for Polish.
    """
    if isinstance(exc, KartografError):
        named = exc.command if isinstance(exc, UsageError) else None
        return _report(
            exc.code,
            exc.localized(lang) or type(exc).__name__,
            hint=_hint_or_none(_library_hint(exc, command, given, lang)),
            command=command if command is not None else named,
            details=exc.details(),
            lang=lang,
        )
    if isinstance(exc, Terminated):
        return _report(
            "terminated",
            message("errors.terminated", lang),
            command=command,
            lang=lang,
        )
    if isinstance(exc, KeyboardInterrupt):
        return _report(
            "cancelled",
            message("errors.interrupted", lang),
            command=command,
            lang=lang,
        )
    text = _ascii(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, OSError):
        path = _io_path(exc)
        hint = (
            message("errors.io_error_hint", lang, path=path)
            if path
            else message("errors.io_error_hint_no_path", lang)
        )
        return _report(
            "io_error",
            text,
            hint=_one_line(hint),
            command=command,
            details=_io_details(exc),
            lang=lang,
        )
    return _report(
        "internal_error",
        text,
        hint=str(message("errors.internal_error_hint", lang)),
        command=command,
        lang=lang,
    )


def _hint_or_none(text: str | None) -> str | None:
    return None if text is None else _one_line(text)
