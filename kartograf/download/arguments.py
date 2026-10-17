"""Type checks of library call arguments (STANDARDS 11.2, 0.8.0).

The CLI parses its flags into numbers, switches and lists before calling the
library, so these checks only ever fire for library callers. Values are
never converted: ``year="2018"`` or ``layers="SWRS,PTWP"`` are a
``ValidationError`` before anything else runs (no network, no file), instead
of a late ``TypeError``/``ValueError`` from a provider or a string iterated
character by character. Messages name the value as the called function does:
the CLI flag for command-level functions (``download_data``,
``download_landcover``: ``--year``), the parameter elsewhere
(``DownloadManager``, ``download_laz_area``). ``None`` (= "not given") is
handled by the callers.
"""

from kartograf.exceptions import ValidationError


def require_int(value: object, name: str) -> None:
    """``ValidationError`` unless ``value`` is an ``int`` (``bool`` is not)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            f"{name} musi byc liczba calkowita (int), otrzymano {value!r}"
        )


def require_str(value: object, name: str) -> None:
    """``ValidationError`` unless ``value`` is a ``str`` (a code is never a number:
    ``teryt=1261`` would lose leading zeros, e.g. ``0208``)."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} musi byc napisem (str), otrzymano {value!r}")


def require_bool(value: object, name: str) -> None:
    """``ValidationError`` unless ``value`` is ``True`` or ``False``."""
    if not isinstance(value, bool):
        raise ValidationError(
            f"{name} musi byc przelacznikiem (True albo False), otrzymano {value!r}"
        )


def require_codes(value: object, name: str, example: str) -> None:
    """``ValidationError`` unless ``value`` is a list, tuple or set of strings.

    A single string is rejected even though it is iterable: ``"SWRS,PTWP"``
    would otherwise be read character by character (an iterator would be
    consumed by the check, so only these collections are accepted).
    """
    if not isinstance(value, list | tuple | set | frozenset):
        raise ValidationError(
            f"{name}: podaj liste kodow, np. {example}, otrzymano {value!r}"
        )
    bad = [item for item in value if not isinstance(item, str)]
    if bad:
        raise ValidationError(
            f"{name}: kody musza byc napisami, np. {example}, otrzymano {bad!r}"
        )
