"""
Value kinds of the catalog parameters: the parsers of the CLI texts and the
conversion between the JSON form of the options and the library arguments.

``--bbox`` is four numbers with the CRS of ``--bbox-crs``, a per-country value
is a text for every country or ``pl=..,cz=..`` pairs, ``--layers`` and
``--direction`` are comma-separated codes. The parsers raise the library's
``ValidationError`` with the messages of the CLI (Polish), so a command line and
a project task read a value the same way.

Options exist in two forms: library arguments (``BBox``, ``Path``, per-country
mappings, sequences) and the JSON form (``tasks[].options`` of a project,
``CommandCall.options``, the arguments of an MCP tool). ``options_to_json`` /
``options_from_json`` convert between them for a project task,
``check_options_json`` validates the JSON form read from a manifest and
``convert_arguments`` is the one conversion of the JSON form to library
arguments (``options_from_json`` is its project form). ``kinds`` is the mapping
of an option name to its kind (``TaskCommand.options``, or the ``kind`` of the
parameters of a catalog command).
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


# =============================================================================
# Options: library arguments <-> JSON form
# =============================================================================

_KIND_TEXT: dict[Kind, str] = {
    "str": "napis",
    "int": "liczba calkowita",
    "flag": "true",
    "bbox": "lista 4 liczb [min_x, min_y, max_x, max_y] z bbox_crs",
    "bbox_crs": "napis (uklad bbox) razem z bbox",
    "path": "niepusta sciezka (napis)",
    "per_country": 'napis albo obiekt {"pl": napis, "cz": napis}',
    "str_list": "lista napisow",
    "plan": "dokument kartograf-plan/1 (obiekt)",
    "options": "obiekt opcji zadania",
}


def _argument_names(kinds: Mapping[str, Kind]) -> list[str]:
    """Library argument names (``bbox_crs`` is part of ``bbox``)."""
    return [name for name, kind in kinds.items() if kind != "bbox_crs"]


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _json_value(kind: Kind, value: object) -> object | None:
    """The JSON form of one library argument; ``None`` = wrong type."""
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


def options_to_json(
    kinds: Mapping[str, Kind],
    options: Mapping[str, object],
    *,
    command: str | None = None,
) -> dict:
    """Library arguments -> ``tasks[].options`` (spec 3.3).

    ``None`` and ``False`` are omitted (only chosen values are recorded);
    keys follow the order of ``kinds``; a ``BBox`` becomes ``bbox`` (4 numbers)
    and ``bbox_crs``, a path a string with ``/``.

    Parameters
    ----------
    kinds : Mapping
        Option name -> kind of the command (``TaskCommand.options``).
    options : Mapping
        Library arguments.
    command : str, optional
        Name of the command, for the messages.

    Raises
    ------
    ValidationError
        An option of another command or not a library argument (e.g.
        ``output_dir``, ``update``, ``timeout``), or a value of a wrong type.
    """
    given = {
        name: value
        for name, value in options.items()
        if value is not None and value is not False
    }
    names = _argument_names(kinds)
    for name in given:
        if name not in names:
            owner = f" komendy {command}" if command else ""
            raise ValidationError(
                f"opcja {name!r} nie nalezy do zadania{owner} "
                f"(opcje: {', '.join(names)})",
                option=name,
            )
    data: dict = {}
    for name in names:
        if name not in given:
            continue
        value = given[name]
        kind = kinds[name]
        if kind == "bbox":
            if not isinstance(value, BBox):
                raise ValidationError(
                    f"opcja bbox: oczekiwano BBox, podano {value!r}", option="bbox"
                )
            data["bbox"] = [value.min_x, value.min_y, value.max_x, value.max_y]
            data["bbox_crs"] = value.crs
            continue
        converted = _json_value(kind, value)
        if converted is None:
            raise ValidationError(
                f"opcja {name}: oczekiwano {_KIND_TEXT[kind]}, podano {value!r}",
                option=name,
            )
        data[name] = converted
    return data


def _valid_json(kind: Kind, value: object, data: Mapping[str, object]) -> bool:
    """``value`` is the JSON form of ``kind`` (``data``: every given option, for
    the pair ``bbox`` and ``bbox_crs``)."""
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
    if kind == "options":
        return isinstance(value, Mapping)
    return value is not False and _json_value(kind, value) is not None


def check_options_json(
    kinds: Mapping[str, Kind], data: object, *, command: str | None = None
) -> str | None:
    """Error text of ``tasks[].options`` read from a manifest (``None`` = valid).

    Keys of ``kinds`` only, values of their kind; ``null`` and ``false`` are not
    written by Kartograf (an omitted key means "not chosen"); ``bbox`` and
    ``bbox_crs`` come together.
    """
    if not isinstance(data, dict):
        return "options: oczekiwano obiektu"
    for name, value in data.items():
        kind = kinds.get(name)
        if kind is None:
            owner = f" komendy {command}" if command else ""
            return (
                f"options: opcja {name!r} nie nalezy do{owner or ' komendy'} "
                f"(opcje: {', '.join(kinds)})"
            )
        if not _valid_json(kind, value, data):
            return f"options.{name}: oczekiwano {_KIND_TEXT[kind]}"
    return None


def convert_arguments(
    kinds: Mapping[str, Kind],
    data: Mapping[str, object],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """The JSON form of options or tool arguments -> library arguments.

    The one conversion of the JSON form (``tasks[].options``, ``CommandCall``,
    MCP tool arguments): ``bbox`` with ``bbox_crs`` becomes one ``BBox``, a
    ``path`` a ``Path``, a ``str_list`` a tuple, a per-country value a text or a
    ``{"pl": ..., "cz": ...}`` dict, a ``flag`` ``True``, a ``plan`` an
    ``UpdatePlan``, ``options`` a dict. ``None`` and a ``false`` flag count as
    not given (are left out). The keys keep the order of ``data``
    (``bbox_crs`` is part of ``bbox``).

    Parameters
    ----------
    kinds : Mapping
        Option name -> kind (``TaskCommand.options``, or the parameters of a
        catalog command).
    data : Mapping
        The JSON form.
    base_dir : Path, optional
        A relative ``path`` is resolved against it; without it a relative path
        stays relative.

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
                f"nieznana opcja {name!r} (opcje: {', '.join(kinds)})", option=name
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
                "opcja bbox wymaga bbox_crs (uklad wspolrzednych bbox)",
                option="bbox_crs",
                options=("bbox", "bbox_crs"),
            )
        if kind == "bbox_crs" and "bbox" not in given:
            raise ValidationError(
                "opcja bbox_crs wymaga bbox",
                option="bbox_crs",
                options=("bbox", "bbox_crs"),
            )
        if not _valid_json(kind, value, given):
            raise ValidationError(
                f"opcja {name}: oczekiwano {_KIND_TEXT[kind]}, podano {value!r}",
                option=name,
            )
        if kind == "bbox":
            x0, y0, x1, y1 = cast(Sequence[float], value)
            arguments["bbox"] = BBox(x0, y0, x1, y1, str(given["bbox_crs"]))
        elif kind == "bbox_crs":
            continue
        elif kind == "path":
            path = Path(str(value))
            if base_dir is not None and not path.is_absolute():
                path = Path(os.path.abspath(base_dir / path))
            arguments[name] = path
        elif kind == "str_list":
            arguments[name] = tuple(cast(Sequence[str], value))
        elif kind == "per_country" and isinstance(value, Mapping):
            arguments[name] = dict(value)
        elif kind == "plan":
            arguments[name] = _plan(name, value)
        elif kind == "options":
            arguments[name] = dict(cast(Mapping[str, Any], value))
        else:
            arguments[name] = value
    return arguments


def _plan(name: str, value: object) -> UpdatePlan:
    """An ``UpdatePlan`` of a plan document (an ``UpdatePlan`` stays as it is)."""
    if isinstance(value, UpdatePlan):
        return value
    try:
        return UpdatePlan.from_dict(value)
    except ValidationError as error:
        raise ValidationError(str(error), option=name) from error


def options_from_json(
    kinds: Mapping[str, Kind], data: Mapping[str, Any], *, base_dir: Path
) -> dict[str, Any]:
    """``tasks[].options`` -> library arguments; a relative path is resolved
    against ``base_dir`` (the project directory). ``convert_arguments`` with a
    base directory."""
    return convert_arguments(kinds, data, base_dir=base_dir)
