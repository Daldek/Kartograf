"""
Value kinds of the catalog parameters: the parsers of the CLI texts.

``--bbox`` is four numbers with the CRS of ``--bbox-crs``, a per-country value
is a text for every country or ``pl=..,cz=..`` pairs, ``--layers`` and
``--direction`` are comma-separated codes. The parsers raise the library's
``ValidationError`` with the messages of the CLI (Polish), so a command line and
a project task read a value the same way.
"""

from kartograf.core.bbox import BBox
from kartograf.download.options import (
    BBOX_EXPECTED,
    COUNTRY_KEYS,
    validate_request_bbox,
)
from kartograf.exceptions import ValidationError


def layer_codes(text: str) -> tuple[str, ...]:
    """``SWRS,PTWP`` -> ``("SWRS", "PTWP")`` (also ``--direction n,e``); the codes
    are checked by the library."""
    return tuple(code.strip() for code in text.split(","))


def parse_per_country(raw: str | None, flag: str) -> str | dict[str, str] | None:
    """``5m`` (every country) or ``pl=1m,cz=2m`` (per country) as library value.

    Raises
    ------
    ValidationError
        An item without ``=``, a country other than PL/CZ, an empty value or
        a country given twice (the text of the library's per-country check).
    """
    if raw is None or "=" not in raw:
        return raw
    values: dict[str, str] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        key = key.strip().lower()
        if not sep or key not in COUNTRY_KEYS or not value.strip() or key in values:
            raise ValidationError(
                f"{flag}: nieprawidlowa wartosc {raw!r} - podaj jedna wartosc dla "
                f"kazdego kraju zadania albo pary kraj=wartosc rozdzielone "
                f"przecinkami (kraje: pl, cz), np. {flag} pl=...,cz=..."
            )
        values[key] = value.strip()
    return values


def parse_bbox_arg(text: str, crs: str) -> BBox:
    """
    Parse the ``--bbox`` value (``"min_x,min_y,max_x,max_y"``) into a ``BBox``.

    One message for every input defect, so callers do not catch the exception.

    Parameters
    ----------
    text : str
        Argument value; whitespace around numbers is allowed
    crs : str
        CRS in which the coordinates were given

    Raises
    ------
    ValidationError
        ``Nieprawidlowy bbox: <reason>. Oczekiwano: ...`` for a number of values
        other than 4, a non-numeric value, NaN/inf or ``min > max``
        (``core.bbox.validate_bbox``; a point bbox is allowed).
    """
    parts = text.split(",")
    if len(parts) != 4:
        reason = f"oczekiwano 4 wartosci rozdzielonych przecinkami, podano {len(parts)}"
        raise ValidationError(f"Nieprawidlowy bbox: {reason}. {BBOX_EXPECTED}")
    values = []
    for part in parts:
        try:
            values.append(float(part.strip()))
        except ValueError:
            reason = f"{part.strip()!r} nie jest liczba"
            raise ValidationError(
                f"Nieprawidlowy bbox: {reason}. {BBOX_EXPECTED}"
            ) from None
    return validate_request_bbox(BBox(values[0], values[1], values[2], values[3], crs))
