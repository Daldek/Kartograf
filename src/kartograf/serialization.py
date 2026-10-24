"""
JSON documents of the library: one encoder for every result type.

Result types of the command-level API (reports, plans, project state, store
documents, errors) are frozen dataclasses mixing in :class:`Document`. The
mixin gives them ``to_dict()`` and ``to_json()`` with the document ``schema``
(``kartograf-<kind>/<n>``) as the first key. The CLI ``--json`` mode prints
``to_json()`` and the MCP tools return ``to_dict()``: no other module turns a
result into JSON (spec 5, rule A1).

Encoder rules (:func:`encode`), checked in this order:

=====================================  =========================================
Python value                           JSON
=====================================  =========================================
``Enum``                               its ``value``
``None``, ``bool``, ``int``, ``str``   unchanged
``float``                              the number; ``NaN``/``Infinity`` raise
                                       ``ValueError``
type with ``__json__(self, ctx)``      its result, encoded further
``Path``                               ``Path.absolute().as_posix()`` (the file
                                       system and symlinks are not touched)
``Decimal``                            a string (finite values only)
``datetime``                           ISO 8601 in UTC (``+00:00``), to seconds;
                                       a naive value raises ``ValueError``
dataclass                              an object, fields in declaration order
                                       (``metadata={"json": False}`` and the
                                       ``ctx.omit`` pairs are skipped)
``Mapping``                            an object (keys must be ``str``)
``tuple``, ``list``                    an array
``frozenset``, ``set``                 a sorted array
anything else                          ``TypeError`` (never ``str(obj)``)
=====================================  =========================================

The module imports nothing from the rest of the package: result types import
it, never the other way round (the CLI, the catalog and the MCP server sit
above it).
"""

import dataclasses
import inspect
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, cast

SCHEMA_PATTERN = r"kartograf-[a-z][a-z0-9-]*/[1-9][0-9]*"


@dataclass
class EncodeContext:
    """State of one encoding run, set by :meth:`Document.prepare_context`.

    A nested document gets its own copy: what it sets applies to its subtree
    only.

    Attributes
    ----------
    store : Path, optional
        Store directory the relative paths of project pins are joined to
        (``PinnedFile.__json__``, ``FileCheck.__json__``).
    omit : frozenset of (str, str)
        ``(class name, field name)`` pairs left out of the encoded dataclasses
        (``StoreEntries`` leaves out ``("Sidecar", "raw")``).
    """

    store: Path | None = None
    omit: frozenset[tuple[str, str]] = frozenset()


# schema name -> every Document class producing it (filled by __init_subclass__)
SCHEMAS: dict[str, tuple[type["Document"], ...]] = {}


class Document:
    """Mixin of the ``@dataclass(frozen=True)`` result types with a JSON form.

    Subclasses set ``SCHEMA``; ``JSON_KEYS`` lists the keys after ``schema``
    (``None``: the dataclass fields in declaration order). The value of a key
    is the dataclass field of that name; a class without such a field gives a
    property of that name (e.g. ``UpdatePlan.ok``); a class without both gives
    ``JSON_FILL[key]`` (the fixed key set of a schema family shared by several
    classes); otherwise ``ValueError`` (a program error).

    A dataclass field called ``schema`` is rejected: ``schema`` is the
    property reading ``SCHEMA``. A document nested in another one is encoded
    as an object without the ``schema`` key.
    """

    SCHEMA: ClassVar[str]
    JSON_KEYS: ClassVar[tuple[str, ...] | None] = None
    JSON_FILL: ClassVar[Mapping[str, object]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the ``SCHEMA`` declaration of a document subclass."""
        super().__init_subclass__(**kwargs)
        schema = getattr(cls, "SCHEMA", None)
        if not isinstance(schema, str) or not re.fullmatch(SCHEMA_PATTERN, schema):
            raise ValueError(
                f"{cls.__name__}.SCHEMA {schema!r} does not match {SCHEMA_PATTERN!r}"
            )
        # runs BEFORE the @dataclass decorator: read the declared names directly
        if "schema" in inspect.get_annotations(cls):
            raise ValueError(
                f"{cls.__name__}: a dataclass field called 'schema' is not allowed "
                "(Document.schema reads SCHEMA)"
            )
        if cls.JSON_KEYS is not None and "schema" in cls.JSON_KEYS:
            raise ValueError(f"{cls.__name__}.JSON_KEYS must not list 'schema'")
        SCHEMAS[schema] = (*SCHEMAS.get(schema, ()), cls)

    @property
    def schema(self) -> str:
        """The schema of the document (``kartograf-<kind>/<n>``)."""
        return self.SCHEMA

    def prepare_context(self, ctx: EncodeContext) -> None:
        """Set what the nested values need (hook; default: nothing)."""

    def to_dict(self) -> dict[str, object]:
        """Return the document as a JSON object; ``schema`` is the first key."""
        ctx = EncodeContext()
        self.prepare_context(ctx)
        return {"schema": self.SCHEMA, **_document_body(self, ctx)}

    def to_json(self, *, indent: int | None = 2) -> str:
        """Return the document as JSON text.

        ``indent=2`` (default): indented, ``ensure_ascii=False``, a newline at
        the end (what the CLI prints). ``indent=None``: compact separators and
        no newline (the form of MCP tool results).
        """
        data = self.to_dict()
        if indent is None:
            return json.dumps(
                data, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
        return (
            json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False) + "\n"
        )


def encode(value: object, ctx: EncodeContext | None = None) -> object:
    """Encode a value into JSON-native objects (rules in the module docstring).

    A :class:`Document` encoded here is nested: no ``schema`` key (use
    ``Document.to_dict`` for the document of the top level).

    Raises
    ------
    ValueError
        A non-finite number, a naive ``datetime``, a path of a store document
        outside its document, a key without a source.
    TypeError
        A type the encoder does not know, a non-``str`` mapping key.
    """
    return _encode(value, ctx if ctx is not None else EncodeContext())


def _fields(obj: object) -> tuple[dataclasses.Field[Any], ...]:
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"{type(obj).__name__} is not a dataclass instance")
    return dataclasses.fields(cast(Any, obj))


def _encode(value: object, ctx: EncodeContext) -> object:
    if isinstance(value, Enum):
        return _encode(value.value, ctx)
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{value!r} is not a JSON number")
        return float(value)
    if isinstance(value, type):
        raise TypeError(f"the class {value.__name__} is not encodable")
    hook = getattr(value, "__json__", None)
    if hook is not None:
        return _encode(hook(ctx), ctx)
    if isinstance(value, Path):
        return value.absolute().as_posix()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{value!r} is not a JSON number")
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"naive datetime {value!r}: the time zone is not guessed")
        return value.astimezone(UTC).isoformat(timespec="seconds")
    if isinstance(value, Document):
        child = dataclasses.replace(ctx)
        value.prepare_context(child)
        return _document_body(value, child)
    if dataclasses.is_dataclass(value):
        return _dataclass_body(value, ctx)
    if isinstance(value, Mapping):
        encoded: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object keys must be str, got {key!r}")
            encoded[key] = _encode(item, ctx)
        return encoded
    if isinstance(value, tuple | list):
        return [_encode(item, ctx) for item in value]
    if isinstance(value, frozenset | set):
        items: list[Any] = [_encode(item, ctx) for item in value]
        try:
            return sorted(items)
        except TypeError as e:
            raise TypeError(
                f"the elements of a {type(value).__name__} are not orderable"
            ) from e
    raise TypeError(f"{type(value).__name__} is not encodable to JSON")


def _dataclass_body(obj: object, ctx: EncodeContext) -> dict[str, object]:
    class_name = type(obj).__name__
    return {
        f.name: _encode(getattr(obj, f.name), ctx)
        for f in _fields(obj)
        if f.metadata.get("json", True) and (class_name, f.name) not in ctx.omit
    }


def _document_body(doc: Document, ctx: EncodeContext) -> dict[str, object]:
    """Return the keys of a document after ``schema``, in ``JSON_KEYS`` order."""
    by_name = {f.name: f for f in _fields(doc)}
    keys = doc.JSON_KEYS
    if keys is None:
        keys = tuple(
            name for name, f in by_name.items() if f.metadata.get("json", True)
        )
    class_name = type(doc).__name__
    return {
        key: _encode(_document_value(doc, key, by_name), ctx)
        for key in keys
        if (class_name, key) not in ctx.omit
    }


def _document_value(doc: Document, key: str, by_name: Mapping[str, Any]) -> object:
    if key in by_name:
        return getattr(doc, key)
    if isinstance(getattr(type(doc), key, None), property):
        return getattr(doc, key)
    if key in doc.JSON_FILL:
        return doc.JSON_FILL[key]
    raise ValueError(
        f"{type(doc).__name__}: no field, property or JSON_FILL entry for key {key!r}"
    )
