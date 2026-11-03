"""Value kinds of the catalog parameters.

The parsers of the CLI texts and the conversion between the JSON form of the options and
the library arguments.

``--bbox`` is four numbers with the CRS of ``--bbox-crs``, a per-country value
is a text for every country or ``pl=..,cz=..`` pairs, ``--layers`` and
``--direction`` are comma-separated codes. The parsers raise the library's
``ValidationError`` with the messages of the CLI (Polish), so a command line and
a call of the API read a value the same way.

Options exist in two forms: library arguments (``BBox``, ``Path``, per-country
mappings, sequences) and the JSON form (``CommandCall.options``, the arguments of an
MCP tool). ``convert_arguments`` is the one conversion of the JSON form to library
arguments; its ``kinds`` is the mapping of an option name to the ``kind`` of the
parameter of a catalog command.
"""

import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath
from typing import Any, cast

from kartograf.catalog.spec import Kind
from kartograf.core.bbox import BBox
from kartograf.download.options import (
    BBOX_EXPECTED,
    COUNTRY_KEYS,
    validate_request_bbox,
)
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import ValidationError
from kartograf.messages import message, reason


def layer_codes(text: str) -> tuple[str, ...]:
    """Parse ``SWRS,PTWP`` into ``("SWRS", "PTWP")`` (also ``--direction n,e``).

    The codes are checked by the library.
    """
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
                message("kinds.invalid_value_give_one_value_every", flag=flag, raw=raw)
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
        reason = message(
            "kinds.expected_4_comma_separated_values", parts_count=len(parts)
        )
        raise ValidationError(
            message("kinds.invalid_bbox", reason=reason, bbox_expected=BBOX_EXPECTED)
        )
    values = []
    for part in parts:
        try:
            values.append(float(part.strip()))
        except ValueError:
            reason = message("kinds.not_number", part=part.strip())
            raise ValidationError(
                message(
                    "kinds.invalid_bbox", reason=reason, bbox_expected=BBOX_EXPECTED
                )
            ) from None
    return validate_request_bbox(BBox(values[0], values[1], values[2], values[3], crs))


# =============================================================================
# Options: library arguments <-> JSON form
# =============================================================================

_KIND_TEXT: dict[Kind, str] = {
    "str": message("kinds.string"),
    "int": message("kinds.integer"),
    "flag": "true",
    "bbox": message("kinds.list_4_numbers_min_x"),
    "bbox_crs": message("kinds.string_bbox_crs_together_bbox"),
    "path": message("kinds.non_empty_path"),
    "per_country": message("kinds.string_object"),
    "str_list": message("kinds.list_strings"),
    "plan": message("kinds.document_kartograf_plan_1"),
}


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _json_value(kind: Kind, value: object) -> object | None:
    """Return the JSON form of one library argument; ``None`` = wrong type."""
    if kind == "str":
        return value if isinstance(value, str) else None
    if kind == "int":
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if kind == "flag":
        return True if value is True else None
    if kind == "path":
        if isinstance(value, str | os.PathLike) and os.fspath(value):
            return PurePath(os.fspath(value)).as_posix()
        return None
    if kind == "per_country":
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            return dict(value)
        return None
    if kind == "str_list":
        if isinstance(value, Sequence) and not isinstance(value, str):
            items = list(value)
            return items if all(isinstance(item, str) for item in items) else None
        return None
    return None


def _valid_json(kind: Kind, value: object, data: Mapping[str, object]) -> bool:
    """Convert ``value``, the JSON form of ``kind``, to the library argument.

    ``data`` holds every given option, for the pair ``bbox`` and ``bbox_crs``.
    """
    if kind == "bbox":
        return (
            isinstance(value, list | tuple)
            and len(value) == 4
            and all(_is_number(v) and math.isfinite(v) for v in value)
            and "bbox_crs" in data
        )
    if kind == "bbox_crs":
        return isinstance(value, str) and "bbox" in data
    if kind == "path":
        return isinstance(value, str) and bool(value)
    if kind == "plan":
        return isinstance(value, Mapping | UpdatePlan)
    return value is not False and _json_value(kind, value) is not None


def convert_arguments(
    kinds: Mapping[str, Kind], data: Mapping[str, object]
) -> dict[str, Any]:
    """Return the JSON form of options or tool arguments -> library arguments.

    The one conversion of the JSON form (``CommandCall``, MCP tool arguments):
    ``bbox`` with ``bbox_crs`` becomes one ``BBox``, a ``path`` a ``Path``, a
    ``str_list`` a tuple, a per-country value a text or a ``{"pl": ..., "cz": ...}``
    dict, a ``flag`` ``True``, a ``plan`` an ``UpdatePlan``. ``None`` and a ``false``
    flag count as not given (are left out). The keys keep the order of ``data``
    (``bbox_crs`` is part of ``bbox``).

    Parameters
    ----------
    kinds : Mapping
        Option name -> kind (the parameters of a catalog command).
    data : Mapping
        The JSON form.

    Raises
    ------
    ValidationError
        A key that is not in ``kinds`` or a value of a wrong form
        (``option`` names the key; ``bbox`` without ``bbox_crs`` and the reverse
        name ``bbox_crs``).
    """
    for name in data:
        if name not in kinds:
            raise ValidationError(
                message(
                    "kinds.unknown_option_options", name=name, kinds=", ".join(kinds)
                ),
                option=name,
            )
    given = {
        name: value
        for name, value in data.items()
        if value is not None and not (kinds[name] == "flag" and value is False)
    }
    arguments: dict[str, Any] = {}
    for name, value in given.items():
        kind = kinds[name]
        if kind == "path" and isinstance(value, os.PathLike):
            value = os.fspath(value)
        if kind == "bbox" and "bbox_crs" not in given:
            raise ValidationError(
                message("kinds.option_bbox_needs_bbox_crs"),
                option="bbox_crs",
                options=("bbox", "bbox_crs"),
            )
        if kind == "bbox_crs" and "bbox" not in given:
            raise ValidationError(
                message("kinds.option_bbox_crs_needs_bbox"),
                option="bbox_crs",
                options=("bbox", "bbox_crs"),
            )
        if not _valid_json(kind, value, given):
            raise ValidationError(
                message(
                    "kinds.option_expected_got",
                    name=name,
                    kind_text=_KIND_TEXT[kind],
                    value=value,
                ),
                option=name,
            )
        if kind == "bbox":
            x0, y0, x1, y1 = cast(Sequence[float], value)
            arguments["bbox"] = BBox(x0, y0, x1, y1, str(given["bbox_crs"]))
        elif kind == "bbox_crs":
            continue
        elif kind == "path":
            arguments[name] = Path(str(value))
        elif kind == "str_list":
            arguments[name] = tuple(cast(Sequence[str], value))
        elif kind == "per_country" and isinstance(value, Mapping):
            arguments[name] = dict(value)
        elif kind == "plan":
            arguments[name] = _plan(name, value)
        else:
            arguments[name] = value
    return arguments


def _plan(name: str, value: object) -> UpdatePlan:
    """Return an ``UpdatePlan`` of a plan document.

    An ``UpdatePlan`` stays as it is.
    """
    if isinstance(value, UpdatePlan):
        return value
    try:
        return UpdatePlan.from_dict(value)
    except ValidationError as error:
        raise ValidationError(reason(error), option=name) from error
