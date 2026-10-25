"""Type checks of library call arguments (rules for code in CLAUDE.md, 0.8.0).

The CLI parses its flags into numbers, switches and lists before calling the
library, so these checks only ever fire for library callers. Values are
never converted: ``year="2018"`` or ``layers="SWRS,PTWP"`` are a
``ValidationError`` before anything else runs (no network, no file), instead
of a late ``TypeError``/``ValueError`` from a provider or a string iterated
character by character. Messages name the value as the called function does:
the CLI flag for command-level functions (``download_data``,
``download_landcover``: ``--year``), the parameter elsewhere
(``DownloadManager``, ``download_laz_area``). ``None`` (= "not given") is
handled by the callers. The error carries the API name of the argument as
``ValidationError.option`` (``--min-density`` -> ``min_density``).
"""

from kartograf.exceptions import ValidationError
from kartograf.messages import message


def option_name(name: str) -> str:
    """Return the API argument of a CLI flag or a parameter name.

    The API argument of a CLI flag or a parameter name:
    ``--vertical-crs`` -> ``vertical_crs``, ``workers`` -> ``workers``.
    """
    return name.removeprefix("--").replace("-", "_")


def option_error(text: str, *names: str) -> ValidationError:
    """Build the error text about one argument or several that do not go together.

    The error ``text`` about one argument (``option``) or about several
    that do not go together (``options``, in the order of the message).
    """
    if len(names) == 1:
        return ValidationError(text, option=names[0])
    return ValidationError(text, options=names)


def require_int(value: object, name: str) -> None:
    """``ValidationError`` unless ``value`` is an ``int`` (``bool`` is not)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            message("download.require_int", name=name, value=value),
            option=option_name(name),
        )


def require_workers(value: object, name: str = "--workers") -> None:
    """Raise ``ValidationError`` unless ``value`` is an ``int`` of at least 1.

    ``ValidationError`` unless ``value`` is an ``int`` of at least 1 (the
    number of parallel transfers: ``0`` and negative values are not "one").
    """
    require_int(value, name)
    assert isinstance(value, int)
    if value < 1:
        raise ValidationError(
            message("download.require_workers", name=name, value=value),
            option=option_name(name),
        )


def require_str(value: object, name: str) -> None:
    """Raise ``ValidationError`` unless ``value`` is a ``str``.

    ``ValidationError`` unless ``value`` is a ``str`` (a code is never a number:
    ``teryt=1261`` would lose leading zeros, e.g. ``0208``).
    """
    if not isinstance(value, str):
        raise ValidationError(
            message("download.require_str", name=name, value=value),
            option=option_name(name),
        )


def require_bool(value: object, name: str) -> None:
    """``ValidationError`` unless ``value`` is ``True`` or ``False``."""
    if not isinstance(value, bool):
        raise ValidationError(
            message("download.require_bool", name=name, value=value),
            option=option_name(name),
        )


def require_codes(value: object, name: str, example: str) -> None:
    """``ValidationError`` unless ``value`` is a list, tuple or set of strings.

    A single string is rejected even though it is iterable: ``"SWRS,PTWP"``
    would otherwise be read character by character (an iterator would be
    consumed by the check, so only these collections are accepted).
    """
    if not isinstance(value, list | tuple | set | frozenset):
        raise ValidationError(
            message("download.codes_not_list", name=name, example=example, value=value),
            option=option_name(name),
        )
    bad = [item for item in value if not isinstance(item, str)]
    if bad:
        raise ValidationError(
            message("download.codes_not_strings", name=name, example=example, bad=bad),
            option=option_name(name),
        )
