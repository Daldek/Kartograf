"""
The problem documents of ``kartograf server`` (RFC 9457, AGI-6.3, AGI-6.4).

Every error is ``application/problem+json``: ``type`` (the entry of its code on the
page of the Nogat error registry), ``title`` (the registry's title), ``status`` (the
registry's HTTP status), ``detail``, ``instance`` (the path of the request),
``code``, ``hint`` when a fix is known and ``details`` (``reason`` first), as
``kartograf.error_report`` describes the error; a ``validation_error`` that names
its options adds ``errors``, one ``{pointer, type, message}`` per option (``pointer``
a JSON Pointer to the option in the query or the body). The texts (``title``,
``detail``, ``hint``) are in the language of the request's ``Accept-Language``,
English without it (AGI-9.2); the machine fields are the same in both. An error
outside the package hierarchy is ``internal_error`` with a fixed text: the cause is
in the server's log, never in the answer.
"""

from collections.abc import Mapping
from typing import Final, Literal

from kartograf._errors import BY_CODE
from kartograf.error_report import error_report
from kartograf.exceptions import KartografError, ValidationError
from kartograf.messages import Lang, message

__all__ = [
    "PROBLEM_MEDIA_TYPE",
    "REGISTRY_PAGE",
    "Location",
    "http_status",
    "language_of",
    "problem",
]

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
REGISTRY_PAGE: Final = (
    "https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md"
)
"""The page of the Nogat error registry; ``#<code>`` is the entry of a code (ERR-4)."""

Location = Literal["query", "body"]
"""Where the options of a request are: the query of a ``GET``, the body of a POST."""


def language_of(header: str | None) -> Lang:
    """Return ``pl`` when ``Accept-Language`` prefers Polish, else ``en`` (AGI-6.4).

    The tag of the highest quality wins, the first of equals; any other language, no
    header and a malformed one are English (AGI-9.2).
    """
    best: tuple[float, str] | None = None
    for item in (header or "").split(","):
        tag, _, rest = item.strip().partition(";")
        weight = 1.0
        key, _, number = rest.strip().partition("=")
        if key.strip() == "q":
            try:
                weight = float(number)
            except ValueError:
                weight = 0.0
        if tag and weight > 0 and (best is None or weight > best[0]):
            best = (weight, tag.strip().lower())
    return "pl" if best is not None and best[1].split("-")[0] == "pl" else "en"


def http_status(code: str) -> int:
    """Return the HTTP status the registry gives ``code`` (500 when it gives none)."""
    return BY_CODE[code].http_status or 500


def _pointer(location: Location, name: str) -> str:
    """Return the JSON Pointer (RFC 6901) of an option in the query or the body."""
    escaped = name.replace("~", "~0").replace("/", "~1")
    return f"/{location}/{escaped}"


def problem(
    error: BaseException,
    *,
    instance: str,
    lang: Lang,
    command: str | None = None,
    given: Mapping[str, object] | None = None,
    location: Location = "body",
) -> dict[str, object]:
    """Return the problem document of an error.

    Parameters
    ----------
    error : BaseException
        A ``KartografError`` is described as ``error_report`` describes it; any other
        exception is ``internal_error`` with the server's fixed text.
    instance : str
        The path of the request.
    lang : {"en", "pl"}
        The language of the texts (``language_of`` the request).
    command : str, optional
        The catalog id of the command of the route, for the hint of an invalid option.
    given : Mapping, optional
        The options of the request, for the example of that hint.
    location : {"query", "body"}
        Where the options are, for the pointers of ``errors``.

    Returns
    -------
    dict
        ``type``, ``title``, ``status``, ``detail``, ``instance``, ``code``, ``hint``
        when known, ``details`` when not empty and ``errors`` for an invalid option.
    """
    if isinstance(error, KartografError):
        report = error_report(error, command=command, given=given, lang=lang)
        code, title, detail = report.code, report.title, report.message
        hint, details = report.hint, report.details
    else:
        entry = BY_CODE["internal_error"]
        code = entry.code
        title = entry.title_pl if lang == "pl" else entry.title
        detail = str(message("server.internal_error", lang))
        hint, details = None, {}
    body: dict[str, object] = {
        "type": f"{REGISTRY_PAGE}#{code}",
        "title": title,
        "status": http_status(code),
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    if hint:
        body["hint"] = hint
    if details:
        body["details"] = details
    if isinstance(error, ValidationError):
        names = (error.option,) if error.option else error.options or ()
        if names:
            body["errors"] = [
                {
                    "pointer": _pointer(location, name),
                    "type": error.reason or "invalid_input",
                    "message": detail,
                }
                for name in names
            ]
    return body
