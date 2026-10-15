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
needs no network (an ``xsd:include`` of a remote schema - GeoServer HY-NET,
INSPIRE - is still fetched by GDAL when online). GDAL swaps
``urn:ogc:def:crs:EPSG::2180`` (N,E) coordinates to x = easting. Config
``GML_FETCH_ALL_GEOMETRIES=YES``: MapServer writes a
multi-part EGiB parcel or building as repeated ``<ms:geom>`` elements and
GDAL keeps only the LAST part without it (live 2026-10-15: building
``budynki.146510_8.0309.18_BUD`` = 2 polygons). ArcGIS GeoJSON pages:
geometries from GDAL, attributes from the JSON typed by the layer ``fields``
(``esriFieldTypeDate`` = epoch ms -> UTC ``DATETIME``). ``pyogrio`` returns
linear geometries, so curves would be linearized the same way on every page
(none occurred in the PRG, EGiB and RUIAN answers of 2026-10-15: the EGiB
"Curve Polygon" of earlier probes is not in the data).

Deduplication by ``FeatureLayer.id_field``: an identical duplicate (every
field except ``drop_fields``, and the geometry bytes) is skipped, the same id
with other content is a ``DownloadError``; a number of unique features other
than ``matched`` (N) is a ``DownloadError``.

Writing: ``pyogrio.raw.write`` (driver GPKG, ``promote_to_multi=True``, CRS
``native_crs``, layer ``FeatureLayer.name`` with ``DESCRIPTION`` = source),
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
    """Unique features of one layer and the schema they are written with:
    ``key`` = index of the id field, ``compared`` = indices of the fields
    that make two features identical (all but ``drop_fields``), ``utc`` =
    datetime fields holding UTC values, ``declared`` = schema geometry type."""

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
        A page GDAL cannot read, pages with different schemas, a feature
        without an id, the same id with other content, or unique features
        != ``matched`` (incomplete answer).
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


def _read_page(page: Path, context: str, **kwargs: Any) -> tuple:
    try:
        return pyogrio.raw.read(page, **kwargs)
    except (DataSourceError, DataLayerError) as e:
        raise DownloadError(
            f"{context}: GDAL nie odczytal strony {page.name}: {e}"
        ) from e


def _read_wfs(
    layer_pages: "LayerPages", params: "FeatureBBoxParams", dropped: dict[str, set[str]]
) -> _Table:
    """Unique features of the GML pages read with the layer XSD."""
    layer = layer_pages.layer
    context = f"WFS {layer.source}"
    if layer_pages.schema is None or not layer_pages.pages:
        raise ValueError(f"Warstwa WFS {layer.source} wymaga schematu i stron")
    options = {
        "layer": layer.source.rsplit(":", 1)[-1],
        "XSD": str(layer_pages.schema),
        **_GML_OPEN_OPTIONS,
    }
    table: _Table | None = None
    with _gdal_config({"GML_FETCH_ALL_GEOMETRIES": "YES"}):
        for page in layer_pages.pages:
            meta, _, geometries, values = _read_page(page, context, **options)
            names = [str(name) for name in meta["fields"]]
            if table is None:
                table = _new_table(
                    names,
                    [np.dtype(dtype) for dtype in meta["dtypes"]],
                    set(),
                    str(meta["geometry_type"]),
                    layer.id_field,
                    params,
                    context,
                )
            elif names != table.names:
                raise DownloadError(
                    f"{context}: strona {page.name} ma inne pola niz pierwsza strona"
                )
            if geometries is not None:
                count = len(geometries)
            else:
                count = len(values[0]) if values else 0
            for index in range(count):
                row = tuple(column[index] for column in values)
                wkb = geometries[index] if geometries is not None else None
                _add(table, row, wkb, dropped, context)
    assert table is not None
    _check_complete(table, layer_pages, context)
    return table


def _read_arcgis(
    layer_pages: "LayerPages", params: "FeatureBBoxParams", dropped: dict[str, set[str]]
) -> _Table:
    """Unique features of the GeoJSON pages typed by the layer ``fields``."""
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
    """Comparable, hashable form of a value (null and NaN/NaT -> ``None``)."""
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
    """Add one feature: identical duplicates skipped, conflicting ones rejected
    (``drop_fields`` do not count: their value is the moment of the answer)."""
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
    """Layer type after ``promote_to_multi``: one family -> its Multi type,
    mixed families -> ``Unknown``; no geometries -> the declared type."""
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
            layer_options={"DESCRIPTION": layer.source},
            gdal_tz_offsets=tz_offsets or None,
        )


def _remove(path: Path) -> None:
    """Delete a partial GeoPackage and its SQLite side files."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
