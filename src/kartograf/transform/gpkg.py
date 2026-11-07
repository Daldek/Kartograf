"""
Deterministic GeoPackages of area results (ADR-042 D5, ADR-059).

``write_gpkg`` reads the pages saved by ``transport.feature_bbox`` with GDAL
(``pyogrio``), removes duplicates, sorts the features by the layer id field,
moves the response-time fields (``drop_fields``) out of the file and writes
one GPKG layer per source layer in the native CRS of the service.

``write_archive_gpkg`` reads the one File Geodatabase of a ZIP through
``/vsizip/``: every declared layer must be in it, with its identifier column
and the projection of the native CRS (the layers of PGW carry an ESRI
definition of the CS92 grid that pyproj does not equate with EPSG:2180, so the
projection method, its parameters and the ellipsoid are compared; nothing is
reprojected). The envelope of the area is GDAL's spatial filter, and a
feature stays when shapely finds that its geometry intersects the area
rectangle, the boundary included (the ``BBOX`` filter of a WFS). The features
are written whole, in the order of the identifier, which is the first field;
an integer field read with nulls (as floats by pyogrio) is written as its
declared type with the nulls; every chosen layer is written, an empty one with
its schema, under its lowercase ASCII name with ``DESCRIPTION`` =
``<dataset>/<source layer>``. Two warnings of the read are ignored
(``_ARCHIVE_WARNINGS``: measured types read in 2D, a spatial index GDAL does
not use). No feature in any layer is ``NoCoverageError``.

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
lock (``gdal_config``) serialises the configured GDAL work of this module
(parallel jobs) and of the fixtures ``kartograf.testing`` writes with GDAL.
"""

import json
import math
import struct
import threading
import warnings
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pyogrio
import pyogrio.raw
import shapely
from pyogrio.errors import DataLayerError, DataSourceError
from pyproj import CRS
from pyproj.exceptions import CRSError

from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.messages import message, reason

if TYPE_CHECKING:
    from kartograf.core.bbox import BBox
    from kartograf.sources.descriptor import (
        ArchiveLayersParams,
        FeatureBBoxParams,
        FeatureLayer,
    )
    from kartograf.transport.feature_bbox import FeaturePages, LayerPages

# gpkg_contents.last_change of every written layer (instead of "now").
_FIXED_DATE = "2000-01-01T00:00:00.000Z"

_GDAL_LOCK = threading.Lock()
_GML_OPEN_OPTIONS = {"WRITE_GFS": "NO", "DOWNLOAD_SCHEMA": "NO"}
_GDAL_TZ_UTC = 100  # GDAL TZFlag of UTC (pyogrio ``gdal_tz_offsets``)
# Warnings of reading the geodatabase of PGW (2023-09-15) about the reading, not
# the data: its measured layers hold no M values and are read in 2D, and GDAL
# reads a layer whose spatial index has a doubtful depth without the index.
_ARCHIVE_WARNINGS = (
    (UserWarning, r"Measured \(M\) geometry types are not supported"),
    (RuntimeWarning, r"Cannot use .* as the index depth"),
)

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
    """Result of ``write_gpkg`` and ``write_archive_gpkg``.

    ``features``: GPKG layer name -> features written (unique; every layer,
    also 0). ``dropped``: drop field -> sorted unique non-null values read
    from the pages (e.g. ``{"DATA": ("2026-10-14",)}``); a field without any
    value (absent from the layers or always null) has no key. ``member``: the
    geodatabase directory of the archive the layers were read from.
    """

    features: dict[str, int]
    dropped: dict[str, tuple[str, ...]]
    member: str | None = None


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
        raise ValueError(f"File {path} already exists")
    if not pages.layers:
        raise ValueError("No layers to write")
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


def archive_geodatabase(archive: Path) -> str:
    """Return the name of the one ``*.gdb`` directory of a ZIP archive.

    Raises
    ------
    DownloadError
        Not a readable ZIP, or no or several geodatabases in it.
    """
    try:
        with zipfile.ZipFile(archive) as opened:
            tops = {name.split("/", 1)[0] for name in opened.namelist() if "/" in name}
    except (OSError, zipfile.BadZipFile) as e:
        raise DownloadError(
            message(
                "transform.archive_unreadable", context=archive.name, error=reason(e)
            )
        ) from e
    found = sorted(top for top in tops if top.lower().endswith(".gdb"))
    if len(found) != 1:
        raise DownloadError(
            message(
                "transform.archive_geodatabases", archive=archive.name, count=len(found)
            )
        )
    return found[0]


def write_archive_gpkg(
    path: Path,
    archive: Path,
    *,
    params: "ArchiveLayersParams",
    layers: Sequence["FeatureLayer"],
    area: "BBox",
) -> GpkgSummary:
    """Write the features of ``layers`` that intersect ``area`` as one GeoPackage.

    ``archive``: a ZIP holding one File Geodatabase; ``area``: a rectangle in
    ``params.native_crs``. ``path`` must not exist (local disk: SQLite needs
    working file locks). On any failure no file is left behind; the rules are in
    the module docstring.

    Raises
    ------
    DownloadError
        No or several geodatabases, a missing layer, a layer with another
        identifier column or another projection, a layer or geometry GDAL or
        GEOS cannot read.
    NoCoverageError
        No feature of any of ``layers`` intersects ``area``.
    ValueError
        ``path`` exists or no layers (programmer error).
    """
    path = Path(path)
    if path.exists():
        raise ValueError(f"File {path} already exists")
    if not layers:
        raise ValueError("No layers to write")
    member = archive_geodatabase(archive)
    source = f"/vsizip/{archive}/{member}"
    context = f"{archive.name}/{member}"
    with _archive_reading():
        try:
            present = {str(name) for name, _ in pyogrio.list_layers(source)}
        except (DataSourceError, DataLayerError) as e:
            raise DownloadError(
                message(
                    "transform.archive_unreadable", context=context, error=reason(e)
                )
            ) from e
    missing = [layer.source for layer in layers if layer.source not in present]
    if missing:
        raise DownloadError(
            message(
                "transform.archive_missing_layers",
                context=context,
                missing=", ".join(missing),
            )
        )
    features: dict[str, int] = {}
    try:
        for layer in layers:
            features[layer.name] = _write_archive_layer(
                path, source, f"{context}/{layer.source}", layer, params, area
            )
    except BaseException:
        _remove(path)
        raise
    if not any(features.values()):
        _remove(path)
        raise NoCoverageError(
            message(
                "transform.archive_no_features",
                context=context,
                codes=", ".join(dict.fromkeys(layer.code for layer in layers)),
                bbox=",".join(f"{value:.10g}" for value in area[:4]),
                crs=params.native_crs,
            )
        )
    return GpkgSummary(features=features, dropped={}, member=member)


def _write_archive_layer(
    path: Path,
    source: str,
    context: str,
    layer: "FeatureLayer",
    params: "ArchiveLayersParams",
    area: "BBox",
) -> int:
    """Append the features of one archive layer that intersect ``area``; their count."""
    with _archive_reading():
        try:
            info = pyogrio.read_info(source, layer=layer.source)
            meta, fids, geometries, values = pyogrio.raw.read(
                source,
                layer=layer.source,
                bbox=(area.min_x, area.min_y, area.max_x, area.max_y),
                return_fids=True,
            )
        except (DataSourceError, DataLayerError) as e:
            raise DownloadError(
                message(
                    "transform.archive_unreadable", context=context, error=reason(e)
                )
            ) from e
    if info["fid_column"] != layer.id_field:
        raise DownloadError(
            message(
                "transform.archive_layer_identifier",
                context=context,
                found=info["fid_column"] or "-",
                expected=layer.id_field,
            )
        )
    if not _same_grid(meta["crs"], params.native_crs):
        raise DownloadError(
            message(
                "transform.archive_layer_grid",
                context=context,
                found=_crs_name(meta["crs"]),
                crs=params.native_crs,
            )
        )
    box = shapely.box(area.min_x, area.min_y, area.max_x, area.max_y)
    try:
        meets = shapely.intersects(shapely.from_wkb(geometries), box)
    except shapely.errors.GEOSException as e:
        raise DownloadError(
            message("transform.archive_geometry", context=context, error=reason(e))
        ) from e
    order = [int(i) for i in np.argsort(fids, kind="stable") if meets[i]]
    columns: list[tuple[np.ndarray, np.ndarray | None]] = [
        (np.asarray(fids[order], dtype=np.int64), None)
    ]
    for column, declared in zip(values, meta["dtypes"], strict=True):
        columns.append(_declared_column(column[order], np.dtype(declared)))
    geometry = np.empty(len(order), dtype=object)
    for position, index in enumerate(order):
        geometry[position] = geometries[index]
    with gdal_config({"OGR_CURRENT_DATE": _FIXED_DATE}):
        pyogrio.raw.write(
            path,
            geometry,
            [data for data, _ in columns],
            [layer.id_field, *(str(name) for name in meta["fields"])],
            field_mask=[mask for _, mask in columns],
            layer=layer.name,
            driver="GPKG",
            geometry_type=_geometry_type(list(geometry), str(meta["geometry_type"])),
            crs=params.native_crs,
            promote_to_multi=True,
            layer_options={"DESCRIPTION": f"{layer.code}/{layer.source}"},
        )
    return len(order)


@contextmanager
def _archive_reading() -> Iterator[None]:
    """Read an archive through GDAL: no EPSG matching, the known warnings ignored.

    ``USE_OSR_FIND_MATCHES=NO``: GDAL would otherwise look for an EPSG
    equivalent of every layer CRS each time it opens the geodatabase (0.1 s for
    the 25 layers of PGW, finding none: ``_same_grid`` compares the projection).
    The warnings of ``_ARCHIVE_WARNINGS`` concern the reading, not the data.
    """
    with gdal_config({"USE_OSR_FIND_MATCHES": "NO"}), warnings.catch_warnings():
        for category, text in _ARCHIVE_WARNINGS:
            warnings.filterwarnings("ignore", message=text, category=category)
        yield


def _grid(crs: CRS) -> tuple[Any, ...] | None:
    """Return the map projection of a projected CRS: method, parameters, ellipsoid."""
    operation = crs.coordinate_operation
    if not crs.is_projected or operation is None:
        return None
    parameters = tuple(
        (
            parameter.code or parameter.name,
            parameter.value
            if isinstance(parameter.value, str)
            else round(parameter.value * parameter.unit_conversion_factor, 9),
        )
        for parameter in operation.params
    )
    ellipsoid = crs.ellipsoid
    return (
        operation.method_code or operation.method_name,
        parameters,
        round(ellipsoid.semi_major_metre, 3) if ellipsoid is not None else None,
        round(ellipsoid.inverse_flattening, 9) if ellipsoid is not None else None,
        tuple(axis.unit_conversion_factor for axis in crs.axis_info),
    )


def _same_grid(found: str | None, native: str) -> bool:
    """Whether a layer CRS has the map projection of ``native`` (no reprojection)."""
    if not found:
        return False
    try:
        grid = _grid(CRS.from_user_input(found))
        return grid is not None and grid == _grid(CRS.from_user_input(native))
    except CRSError:
        return False


def _crs_name(found: str | None) -> str:
    """Return the name of a layer CRS for a message (``-``: none)."""
    if not found:
        return "-"
    try:
        return str(CRS.from_user_input(found).name)
    except CRSError:
        return found[:60]


def _declared_column(
    column: np.ndarray, declared: np.dtype
) -> tuple[np.ndarray, np.ndarray | None]:
    """Return a column read by pyogrio as its declared type, with its null mask.

    pyogrio reads an integer or boolean field holding nulls as floats with NaN:
    written back as its declared type, the nulls stay nulls.
    """
    if declared.kind in "iub" and column.dtype.kind == "f":
        nulls = np.isnan(column)
        return np.where(nulls, 0, column).astype(declared), (
            nulls if nulls.any() else None
        )
    return column, None


@contextmanager
def gdal_config(options: dict[str, str]) -> Iterator[None]:
    """Set GDAL config options for the block, then the previous values again.

    The options are process-wide, so one lock serialises every configured GDAL
    work of Kartograf.
    """
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
            message(
                "transform.gdal_did_not_read_page",
                context=context,
                name=page.name,
                error=reason(e),
            )
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
        raise ValueError(f"WFS layer {layer.source} needs a schema and pages")
    options = {"layer": layer.source.rsplit(":", 1)[-1], **_GML_OPEN_OPTIONS}
    if _declares_types(layer_pages.schema):
        options["XSD"] = str(layer_pages.schema)
    table: _Table | None = None
    with gdal_config({"GML_FETCH_ALL_GEOMETRIES": "YES"}):
        for page in layer_pages.pages:
            try:
                meta, _, geometries, values = pyogrio.raw.read(page, **options)
            except DataLayerError as e:
                if layer_pages.matched:
                    raise DownloadError(
                        message(
                            "transform.gdal_did_not_read_page",
                            context=context,
                            name=page.name,
                            error=reason(e),
                        )
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
                    message(
                        "transform.gdal_did_not_read_page",
                        context=context,
                        name=page.name,
                        error=reason(e),
                    )
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
                    message(
                        "transform.field_has_type_page_earlier_ones",
                        context=context,
                        name=name,
                        page_name=page.name,
                        dtype=dtype,
                        known=known,
                    )
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
            raise DownloadError(
                message(
                    "transform.gdal_read_different_number_features_page",
                    context=context,
                )
            )
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
                message(
                    "transform.gdal_read_different_number_features_page_2",
                    context=context,
                    name=page.name,
                )
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
                message(
                    "transform.page_has_feature_whose_properties_not",
                    context=context,
                    name=page.name,
                )
            )
        values = dict(properties or {})
        if id_field == _GEOJSON_ID:
            ident = feature.get("id")
            if values.get(_GEOJSON_ID, ident) != ident:
                raise DownloadError(
                    message(
                        "transform.property_id_differs_feature_identifier",
                        context=context,
                        id_value=values[_GEOJSON_ID],
                        ident=ident,
                    )
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
        raise DownloadError(
            message(
                "transform.layer_schema_has_no_field",
                context=context,
                id_field=id_field,
            )
        )
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
        message(
            "transform.value_field_not_type",
            context=context,
            value=value,
            name=name,
            esri=esri,
        )
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
            message(
                "transform.feature_without_identifier",
                context=context,
                id_field=table.names[table.key],
            )
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
            message(
                "transform.feature_occurs_twice_different_content",
                context=context,
                id_field=table.names[table.key],
                ident=ident,
            )
        )


def _check_complete(table: _Table, layer_pages: "LayerPages", context: str) -> None:
    if len(table.rows) != layer_pages.matched:
        raise DownloadError(
            message(
                "transform.pages_give_different_features",
                context=context,
                rows_count=len(table.rows),
                matched=layer_pages.matched,
            )
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
            message(
                "transform.identifiers_not_comparable",
                source=layer.source,
                id_field=layer.id_field,
            )
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
    with gdal_config({"OGR_CURRENT_DATE": _FIXED_DATE}):
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
