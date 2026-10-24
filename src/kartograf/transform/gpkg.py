"""
Deterministic GeoPackage of a ``feature_bbox`` answer (ADR-042 D5).

``write_gpkg`` reads the pages saved by ``transport.feature_bbox`` with GDAL
(``pyogrio``), removes duplicates, sorts the features by the layer id field,
moves the response-time fields (``drop_fields``) out of the file and writes
one GPKG layer per source layer in the native CRS of the service.

Reading. WFS GML pages: open options ``XSD=<DescribeFeatureType>`` (the same
field types on every page, no guessing from the data), ``WRITE_GFS=NO`` (no
``.gfs`` files next to the pages) and ``DOWNLOAD_SCHEMA=NO``: the MapServer
XSDs of PRG and EGiB only import GML, which GDAL does not read, so reading
needs no network. An XSD that declares no type itself (GeoServer HY-NET: one
``xsd:include`` of the remote INSPIRE schema) is not given to GDAL: GDAL
would fetch the remote schema for every page and still learn the fields
from the document (measured 2026-10-15: the same fields, 0.3-0.4 s per
page). GDAL swaps
``urn:ogc:def:crs:EPSG::2180`` (N,E) coordinates to x = easting. Config
``GML_FETCH_ALL_GEOMETRIES=YES``: MapServer writes a
multi-part EGiB parcel or building as repeated ``<ms:geom>`` elements and
GDAL keeps only the LAST part without it (live 2026-10-15: building
``budynki.146510_8.0309.18_BUD`` = 2 polygons). ArcGIS GeoJSON pages:
geometries from GDAL, attributes from the JSON typed by the layer ``fields``
(``esriFieldTypeDate`` = epoch ms -> UTC ``DATETIME``). OGC API Features
GeoJSON pages: geometries from GDAL, attributes from the JSON with ONE type
per field over every page of the layer, so the page split never changes the
result: int -> int64, int+float -> float64, bool -> bool; strings, objects
and arrays, integers outside int64, mixed kinds and fields without any value
-> text (strings as they are, anything else as JSON text:
``json.dumps(ensure_ascii=False, sort_keys=True)``). The id column comes
first (``id_field="id"``: the GeoJSON ``id`` as the column ``id``; a property
``id`` must hold the same value), the other fields in first-seen order; an
empty layer has the id column only (``Unknown`` geometry). ``pyogrio``
returns linear geometries, so curves would be linearized the same way on
every page (none occurred in the PRG, EGiB and RUIAN answers of 2026-10-15:
the EGiB "Curve Polygon" of earlier probes is not in the data).

Deduplication by ``FeatureLayer.id_field``: an identical duplicate (every
field except ``drop_fields``, and the geometry bytes) is skipped, the same id
with other content is a ``DownloadError``; a number of unique features other
than ``matched`` (N) is a ``DownloadError``.

Writing: ``pyogrio.raw.write`` (driver GPKG, ``promote_to_multi=True``, CRS
``native_crs`` - OGC API: ``OGC:CRS84`` - layer ``FeatureLayer.name`` with
``DESCRIPTION`` = the WFS type name, the ArcGIS layer name with its id, e.g.
``Vodni tok (93)`` in the service's spelling, or the OGC API collection id),
features in id order, the layer geometry type from the geometries (one
family -> its Multi type, else ``Unknown``) or, for an empty layer, from the
schema; ``OGR_CURRENT_DATE`` is fixed while writing, so the same pages give
the same bytes (per GDAL version). GDAL config options are process-wide: one
lock serialises the configured GDAL work of this module (parallel jobs).
"""

import json
import math
import struct
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pyogrio
import pyogrio.raw
from pyogrio.errors import DataLayerError, DataSourceError

from kartograf.exceptions import DownloadError

if TYPE_CHECKING:
    from kartograf.sources.descriptor import FeatureBBoxParams
    from kartograf.transport.feature_bbox import FeaturePages, LayerPages

# gpkg_contents.last_change of every written layer (instead of "now").
_FIXED_DATE = "2000-01-01T00:00:00.000Z"

_GDAL_LOCK = threading.Lock()
_GML_OPEN_OPTIONS = {"WRITE_GFS": "NO", "DOWNLOAD_SCHEMA": "NO"}
_GDAL_TZ_UTC = 100  # GDAL TZFlag of UTC (pyogrio ``gdal_tz_offsets``)

# ArcGIS field type -> numpy dtype of the GPKG column (unknown types: text).
_ESRI_DTYPES = {
    "esriFieldTypeOID": "int64",
    "esriFieldTypeBigInteger": "int64",
    "esriFieldTypeInteger": "int32",
    "esriFieldTypeSmallInteger": "int16",
    "esriFieldTypeDouble": "float64",
    "esriFieldTypeSingle": "float32",
    "esriFieldTypeDate": "datetime64[ms]",
}
_ESRI_SKIPPED = {"esriFieldTypeGeometry", "esriFieldTypeBlob", "esriFieldTypeRaster"}
_ESRI_GEOMETRY = {
    "esriGeometryPoint": "MultiPoint",
    "esriGeometryMultipoint": "MultiPoint",
    "esriGeometryPolyline": "MultiLineString",
    "esriGeometryPolygon": "MultiPolygon",
    "esriGeometryEnvelope": "MultiPolygon",
}
# WKB base type -> geometry family (single and multi of one family).
_FAMILIES = {
    1: "Point",
    2: "LineString",
    3: "Polygon",
    4: "Point",
    5: "LineString",
    6: "Polygon",
}
_MULTI = {"MultiPoint", "MultiLineString", "MultiPolygon"}
# OGC API: the id field that means the GeoJSON ``id`` member; the int64 range
# of JSON integers written as numbers.
_GEOJSON_ID = "id"
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1

# One feature: field values (schema order) and the WKB geometry.
_Row = tuple[tuple[Any, ...], bytes | None]


@dataclass(frozen=True)
class GpkgSummary:
    """Result of ``write_gpkg``.

    ``features``: GPKG layer name -> features written (unique; every layer,
    also 0). ``dropped``: drop field -> sorted unique non-null values read
    from the pages (e.g. ``{"DATA": ("2026-10-14",)}``); a field without any
    value (absent from the layers or always null) has no key.
    """

    features: dict[str, int]
    dropped: dict[str, tuple[str, ...]]


@dataclass
class _Table:
    """Unique features of one layer and the schema they are written with.

    Unique features of one layer and the schema they are written with: ``key`` = index
    of the id field, ``compared`` = indices of the fields that make two features
    identical (all but ``drop_fields``), ``utc`` = datetime fields holding UTC values,
    ``declared`` = schema geometry type.
    """

    names: list[str]
    dtypes: list[np.dtype]
    utc: set[str]
    declared: str
    key: int
    compared: list[int]
    rows: dict[Any, _Row]


def write_gpkg(
    path: Path, pages: "FeaturePages", *, params: "FeatureBBoxParams"
) -> GpkgSummary:
    """Write the pages of every layer as one deterministic GeoPackage ``path``.

    ``path`` must not exist (local disk: SQLite needs working file locks).
    On any failure no file is left behind.

    Raises
    ------
    DownloadError
        A page GDAL cannot read, one field with two types on different pages
        (WFS), a feature without an id, the same id with other content, or
        unique features != ``matched`` (incomplete answer).
    ValueError
        ``path`` exists, no layers, or a WFS layer without schema/pages
        (programmer error).
    """
    path = Path(path)
    if path.exists():
        raise ValueError(f"Plik {path} juz istnieje")
    if not pages.layers:
        raise ValueError("Brak warstw do zapisu")
    dropped: dict[str, set[str]] = {name: set() for name in params.drop_fields}
    features: dict[str, int] = {}
    try:
        for layer_pages in pages.layers:
            if params.protocol == "wfs":
                table = _read_wfs(layer_pages, params, dropped)
            elif params.protocol == "ogcapi":
                table = _read_ogcapi(layer_pages, params, dropped)
            else:
                table = _read_arcgis(layer_pages, params, dropped)
            _write_layer(path, table, layer_pages, params)
            features[layer_pages.layer.name] = len(table.rows)
    except BaseException:
        _remove(path)
        raise
    return GpkgSummary(
        features=features,
        dropped={
            name: tuple(sorted(values)) for name, values in dropped.items() if values
        },
    )


@contextmanager
def _gdal_config(options: dict[str, str]) -> Iterator[None]:
    """GDAL config options for the block, then the previous values again."""
    with _GDAL_LOCK:
        previous = {key: pyogrio.get_gdal_config_option(key) for key in options}
        pyogrio.set_gdal_config_options(options)
        try:
            yield
        finally:
            pyogrio.set_gdal_config_options(previous)


def _read_page(page: Path, context: str, **kwargs: Any) -> tuple[Any, ...]:
    try:
        result: tuple[Any, ...] = pyogrio.raw.read(page, **kwargs)
        return result
    except (DataSourceError, DataLayerError) as e:
        raise DownloadError(
            f"{context}: GDAL nie odczytal strony {page.name}: {e}"
        ) from e


def _read_wfs(
    layer_pages: "LayerPages", params: "FeatureBBoxParams", dropped: dict[str, set[str]]
) -> _Table:
    """Return the unique features of the GML pages read with the layer XSD.

    GDAL types every page on its own. With a full XSD (MapServer PRG, EGiB)
    all pages have one schema; an XSD that only includes a remote schema
    (GeoServer HY-NET: ``xsd:include`` of INSPIRE) leaves GDAL to learn the
    fields from each document, so a page may lack an optional field other
    pages have (HY-NET ``hydroNodeCategory``): the layer gets the union of
    the page fields in first-seen order, a missing value is null, one field
    with two types is a ``DownloadError``. An empty layer whose type GDAL
    cannot build at all (no XSD schema, no feature to learn from) is written
    with the id field only (``Unknown`` geometry).
    """
    layer = layer_pages.layer
    context = f"WFS {layer.source}"
    if layer_pages.schema is None or not layer_pages.pages:
        raise ValueError(f"Warstwa WFS {layer.source} wymaga schematu i stron")
    options = {"layer": layer.source.rsplit(":", 1)[-1], **_GML_OPEN_OPTIONS}
    if _declares_types(layer_pages.schema):
        options["XSD"] = str(layer_pages.schema)
    table: _Table | None = None
    with _gdal_config({"GML_FETCH_ALL_GEOMETRIES": "YES"}):
        for page in layer_pages.pages:
            try:
                meta, _, geometries, values = pyogrio.raw.read(page, **options)
            except DataLayerError as e:
                if layer_pages.matched:
                    raise DownloadError(
                        f"{context}: GDAL nie odczytal strony {page.name}: {e}"
                    ) from e
                return _new_table(
                    [layer.id_field],
                    [np.dtype(object)],
                    set(),
                    "Unknown",
                    layer.id_field,
                    params,
                    context,
                )
            except DataSourceError as e:
                raise DownloadError(
                    f"{context}: GDAL nie odczytal strony {page.name}: {e}"
                ) from e
            names = [str(name) for name in meta["fields"]]
            dtypes = [np.dtype(dtype) for dtype in meta["dtypes"]]
            if table is None:
                table = _new_table(
                    names,
                    dtypes,
                    set(),
                    str(meta["geometry_type"]),
                    layer.id_field,
                    params,
                    context,
                )
            positions = _merge_fields(table, names, dtypes, params, page, context)
            if geometries is not None:
                count = len(geometries)
            else:
                count = len(values[0]) if values else 0
            for index in range(count):
                row = tuple(
                    None if position is None else values[position][index]
                    for position in positions
                )
                wkb = geometries[index] if geometries is not None else None
                _add(table, row, wkb, dropped, context)
    assert table is not None
    _check_complete(table, layer_pages, context)
    return table


_XSD = "{http://www.w3.org/2001/XMLSchema}"


def _declares_types(schema: Path) -> bool:
    """Check whether a ``DescribeFeatureType`` XSD declares the types itself.

    Whether a ``DescribeFeatureType`` XSD declares the types itself (MapServer) rather
    than only including a remote schema (GeoServer INSPIRE, module docstring).
    """
    try:
        root = ET.parse(schema).getroot()
    except ET.ParseError:
        return False
    return any(child.tag in (f"{_XSD}element", f"{_XSD}complexType") for child in root)


def _merge_fields(
    table: _Table,
    names: list[str],
    dtypes: list[np.dtype],
    params: "FeatureBBoxParams",
    page: Path,
    context: str,
) -> list[int | None]:
    """Merge the fields of a page into the layer schema.

    Fields of a page into the layer schema: new fields appended (null in the rows read
    so far); the page column of every layer field (``None``: the page has no such
    field).
    """
    for name, dtype in zip(names, dtypes, strict=True):
        if name in table.names:
            known = table.dtypes[table.names.index(name)]
            if known != dtype:
                raise DownloadError(
                    f"{context}: pole {name} ma na stronie {page.name} typ {dtype}, "
                    f"a na wczesniejszych {known}"
                )
            continue
        table.names.append(name)
        table.dtypes.append(dtype)
        if name not in params.drop_fields:
            table.compared.append(len(table.names) - 1)
        table.rows = {
            key: ((*row, None), wkb) for key, (row, wkb) in table.rows.items()
        }
    return [names.index(name) if name in names else None for name in table.names]


def _read_arcgis(
    layer_pages: "LayerPages", params: "FeatureBBoxParams", dropped: dict[str, set[str]]
) -> _Table:
    """Return the unique features of the GeoJSON pages typed by ``fields``."""
    layer = layer_pages.layer
    context = f"ArcGIS {layer.source}"
    columns = [
        (name, esri) for name, esri in layer_pages.fields if esri not in _ESRI_SKIPPED
    ]
    table = _new_table(
        [name for name, _ in columns],
        [np.dtype(_ESRI_DTYPES.get(esri, "object")) for _, esri in columns],
        {name for name, esri in columns if esri == "esriFieldTypeDate"},
        _arcgis_geometry(layer_pages.schema),
        layer.id_field,
        params,
        context,
    )
    for page in layer_pages.pages:
        features = json.loads(page.read_bytes())["features"]
        _, _, geometries, _ = _read_page(page, context, columns=[])
        if geometries is None or len(geometries) != len(features):
            raise DownloadError(f"{context}: GDAL odczytal inna liczbe obiektow strony")
        for feature, wkb in zip(features, geometries, strict=True):
            properties = feature.get("properties") or {}
            row = tuple(
                _esri_value(properties.get(name), esri, name, context)
                for name, esri in columns
            )
            _add(table, row, wkb, dropped, context)
    _check_complete(table, layer_pages, context)
    return table


def _read_ogcapi(
    layer_pages: "LayerPages", params: "FeatureBBoxParams", dropped: dict[str, set[str]]
) -> _Table:
    """Return the unique features of the OGC API GeoJSON pages.

    Unique features of the OGC API GeoJSON pages: one pass over every page types the
    fields (module docstring), a second one reads the rows.
    """
    layer = layer_pages.layer
    context = f"OGC API {layer.source}"
    kinds: dict[str, set[str]] = {layer.id_field: set()}
    for page in layer_pages.pages:
        for values in _ogcapi_values(page, layer.id_field, context):
            for name, value in values.items():
                found = kinds.setdefault(name, set())
                if value is not None:
                    found.add(_json_kind(value))
    names = list(kinds)
    dtypes = [_json_dtype(kinds[name]) for name in names]
    table = _new_table(names, dtypes, set(), "Unknown", layer.id_field, params, context)
    for page in layer_pages.pages:
        rows = _ogcapi_values(page, layer.id_field, context)
        if not rows:
            continue
        _, _, geometries, _ = _read_page(page, context, columns=[])
        if geometries is None or len(geometries) != len(rows):
            raise DownloadError(
                f"{context}: GDAL odczytal inna liczbe obiektow strony {page.name}"
            )
        for values, wkb in zip(rows, geometries, strict=True):
            row = tuple(
                _json_value(values.get(name), dtype)
                for name, dtype in zip(names, dtypes, strict=True)
            )
            _add(table, row, wkb, dropped, context)
    _check_complete(table, layer_pages, context)
    return table


def _ogcapi_values(page: Path, id_field: str, context: str) -> list[dict[str, Any]]:
    """Return the attributes of every feature of a saved page.

    Attributes of every feature of a saved page; with ``id_field="id"`` the GeoJSON
    ``id`` is the attribute ``id`` (a property ``id`` must equal it).
    """
    rows = []
    for feature in json.loads(page.read_bytes())["features"]:
        properties = feature.get("properties")
        if properties is not None and not isinstance(properties, dict):
            raise DownloadError(
                f"{context}: strona {page.name} ma obiekt z properties innym niz "
                "slownik"
            )
        values = dict(properties or {})
        if id_field == _GEOJSON_ID:
            ident = feature.get("id")
            if values.get(_GEOJSON_ID, ident) != ident:
                raise DownloadError(
                    f"{context}: wlasciwosc id={values[_GEOJSON_ID]!r} rozna od "
                    f"identyfikatora obiektu {ident!r}"
                )
            values[_GEOJSON_ID] = ident
        rows.append(values)
    return rows


def _json_kind(value: Any) -> str:
    """Return the kind of a non-null JSON value.

    Kind of a non-null JSON value: ``bool``, ``int`` (int64 range), ``float`` or
    ``text`` (strings, objects, arrays, larger integers).
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int" if _INT64_MIN <= value <= _INT64_MAX else "text"
    if isinstance(value, float):
        return "float"
    return "text"


def _json_dtype(kinds: set[str]) -> np.dtype:
    """Return the column type for the kinds of every value of a field.

    Column type from the kinds of every value of a field: int -> int64, int+float ->
    float64, bool -> bool, anything else (also no value) -> text.
    """
    if kinds == {"bool"}:
        return np.dtype(bool)
    if kinds == {"int"}:
        return np.dtype(np.int64)
    if kinds and kinds <= {"int", "float"}:
        return np.dtype(np.float64)
    return np.dtype(object)


def _json_value(value: Any, dtype: np.dtype) -> Any:
    """Convert a JSON value to the column type (``None`` = null).

    JSON value as the column type (``None`` = null); a text column keeps strings and
    holds any other value as JSON text.
    """
    if value is None or dtype.kind in "bi":
        return value
    if dtype.kind == "f":
        return float(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _new_table(
    names: list[str],
    dtypes: list[np.dtype],
    utc: set[str],
    declared: str,
    id_field: str,
    params: "FeatureBBoxParams",
    context: str,
) -> _Table:
    """Empty table of a layer schema; the id field must be in the schema."""
    if id_field not in names:
        raise DownloadError(f"{context}: schemat warstwy nie ma pola {id_field}")
    return _Table(
        names=names,
        dtypes=dtypes,
        utc=utc,
        declared=declared,
        key=names.index(id_field),
        compared=[i for i, name in enumerate(names) if name not in params.drop_fields],
        rows={},
    )


def _arcgis_geometry(schema: Path | None) -> str:
    """GPKG geometry type of an empty ArcGIS layer from its saved layer JSON."""
    if schema is None:
        return "Unknown"
    info = json.loads(schema.read_bytes())
    return _ESRI_GEOMETRY.get(str(info.get("geometryType")), "Unknown")


def _esri_value(value: Any, esri: str, name: str, context: str) -> Any:
    """JSON value of an ArcGIS field as the column type (``None`` = null)."""
    if value is None:
        return None
    kind = np.dtype(_ESRI_DTYPES.get(esri, "object")).kind
    number = isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "M" and isinstance(value, int) and not isinstance(value, bool):
        return np.datetime64(value, "ms")
    if kind == "i" and number and float(value).is_integer():
        return int(value)
    if kind == "f" and number:
        return float(value)
    if kind == "O":
        return value if isinstance(value, str) else json.dumps(value)
    raise DownloadError(
        f"{context}: wartosc {value!r} pola {name} nie jest typu {esri}"
    )


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float | np.floating):
        return math.isnan(value)
    if isinstance(value, np.datetime64):
        return bool(np.isnat(value))
    return False


def _canonical(value: Any) -> Any:
    """Return a comparable, hashable form of a value (null and NaN/NaT -> ``None``)."""
    if _is_null(value):
        return None
    if isinstance(value, np.ndarray):
        return tuple(_canonical(item) for item in value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def _add(
    table: _Table,
    row: tuple[Any, ...],
    wkb: Any,
    dropped: dict[str, set[str]],
    context: str,
) -> None:
    """Add one feature: skip identical duplicates, reject conflicting ones.

    Add one feature: identical duplicates skipped, conflicting ones rejected
    (``drop_fields`` do not count: their value is the moment of the answer).
    """
    ident = _canonical(row[table.key])
    if ident is None or ident == "":
        raise DownloadError(
            f"{context}: obiekt bez identyfikatora {table.names[table.key]}"
        )
    for index, name in enumerate(table.names):
        if name in dropped and not _is_null(row[index]):
            value = _canonical(row[index])
            dropped[name].add(value if isinstance(value, str) else str(value))
    geometry = None if wkb is None else bytes(wkb)
    existing = table.rows.get(ident)
    if existing is None:
        table.rows[ident] = (row, geometry)
        return
    same = existing[1] == geometry and all(
        _canonical(existing[0][i]) == _canonical(row[i]) for i in table.compared
    )
    if not same:
        raise DownloadError(
            f"{context}: obiekt {table.names[table.key]}={ident!r} wystepuje "
            "dwa razy z inna trescia"
        )


def _check_complete(table: _Table, layer_pages: "LayerPages", context: str) -> None:
    if len(table.rows) != layer_pages.matched:
        raise DownloadError(
            f"{context}: strony daja {len(table.rows)} roznych obiektow, "
            f"oczekiwano {layer_pages.matched} (niepelna odpowiedz)"
        )


def _column(values: Sequence[Any], dtype: np.dtype) -> tuple[np.ndarray, Any]:
    """Column array of ``dtype`` and its null mask (``None``: no nulls)."""
    if dtype.kind in "iub":
        mask = np.array([_is_null(value) for value in values], dtype=bool)
        data = np.array(
            [0 if null else value for value, null in zip(values, mask, strict=True)],
            dtype=dtype,
        )
        return data, (mask if mask.any() else None)
    if dtype.kind == "f":
        return np.array(
            [np.nan if _is_null(value) else value for value in values], dtype=dtype
        ), None
    if dtype.kind == "M":
        return np.array(
            [np.datetime64("NaT") if _is_null(value) else value for value in values],
            dtype=dtype,
        ), None
    column = np.empty(len(values), dtype=object)
    for index, value in enumerate(values):
        column[index] = None if _is_null(value) else value
    return column, None


def _wkb_kind(wkb: bytes) -> tuple[int, bool, bool]:
    """WKB base type, Z and M flags (ISO and EWKB codes)."""
    (code,) = struct.unpack_from("<I" if wkb[0] == 1 else ">I", wkb, 1)
    iso = (code & 0x0FFFFFFF) // 1000
    return (
        (code & 0x0FFFFFFF) % 1000,
        bool(code & 0x80000000) or iso in (1, 3),
        bool(code & 0x40000000) or iso in (2, 3),
    )


def _geometry_type(geometries: Sequence[bytes | None], declared: str) -> str:
    """Return the layer type after ``promote_to_multi``.

    Layer type after ``promote_to_multi``: one family -> its Multi type, mixed families
    -> ``Unknown``; no geometries -> the declared type.
    """
    kinds = {_wkb_kind(wkb) for wkb in geometries if wkb}
    if not kinds:
        if declared in _MULTI:
            return declared
        return f"Multi{declared}" if f"Multi{declared}" in _MULTI else "Unknown"
    families = {_FAMILIES.get(base) for base, _, _ in kinds}
    family = families.pop() if len(families) == 1 else None
    if family is None:
        return "Unknown"
    has_z = any(z for _, z, _ in kinds)
    has_m = any(m for _, _, m in kinds)
    name = f"Multi{family}"
    if has_z and has_m:
        return f"Measured 3D {name}"
    if has_m:
        return f"Measured {name}"
    return f"{name} Z" if has_z else name


def _write_layer(
    path: Path, table: _Table, layer_pages: "LayerPages", params: "FeatureBBoxParams"
) -> None:
    """Append one layer to the GeoPackage: features in id order."""
    layer = layer_pages.layer
    try:
        ordered = [table.rows[key] for key in sorted(table.rows)]
    except TypeError as e:
        raise DownloadError(
            f"{layer.source}: identyfikatory {layer.id_field} nie sa porownywalne"
        ) from e
    kept = [i for i, name in enumerate(table.names) if name not in params.drop_fields]
    names = [table.names[i] for i in kept]
    columns = [_column([row[i] for row, _ in ordered], table.dtypes[i]) for i in kept]
    geometry = np.empty(len(ordered), dtype=object)
    for index, (_, wkb) in enumerate(ordered):
        geometry[index] = wkb
    tz_offsets = {
        name: np.full(len(ordered), _GDAL_TZ_UTC, dtype=np.int64)
        for name in names
        if name in table.utc
    }
    with _gdal_config({"OGR_CURRENT_DATE": _FIXED_DATE}):
        pyogrio.raw.write(
            path,
            geometry,
            [data for data, _ in columns],
            names,
            field_mask=[mask for _, mask in columns],
            layer=layer.name,
            driver="GPKG",
            geometry_type=_geometry_type(list(geometry), table.declared),
            crs=params.native_crs,
            promote_to_multi=True,
            layer_options={"DESCRIPTION": _description(layer_pages, params)},
            gdal_tz_offsets=tz_offsets or None,
        )


def _description(layer_pages: "LayerPages", params: "FeatureBBoxParams") -> str:
    """Return the ``gpkg_contents.description`` of a layer.

    ``gpkg_contents.description`` of a layer: the WFS type name, the ArcGIS layer name
    of the service with its id (``Vodni tok (93)``, the name as the service spells it)
    or the OGC API collection id.
    """
    layer = layer_pages.layer
    if params.protocol == "arcgis" and layer_pages.schema is not None:
        name = json.loads(layer_pages.schema.read_bytes()).get("name")
        if isinstance(name, str) and name.strip():
            return f"{name.strip()} ({layer.source})"
    return layer.source


def _remove(path: Path) -> None:
    """Delete a partial GeoPackage and its SQLite side files."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
