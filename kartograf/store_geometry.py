"""Read-only extents of store files and pinned CRS operations (ADR-045).

``file_footprint`` takes the first trustworthy source of an extent - the
request bbox, a computable sheet code, the file header, a unit index (PRG,
RUIAN, SM5) - and never invents one (a national file has none). Envelopes
are reprojected with densified edges through ``pinned_transform``: an
operation chosen once by Kartograf's policy (no ballpark, no network
grids), never pyproj's default.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import struct
import threading
from collections.abc import MutableMapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from pyproj import CRS
from pyproj.exceptions import CRSError

from kartograf.core.bbox import BBox, transform_bbox, validate_bbox
from kartograf.core.parser_registry import CZ_SM5_PATTERN, detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import InvalidSidecarError, ValidationError
from kartograf.transform.crs import (
    PinnedTransform,
    TransformPolicy,
    build_pinned_transform,
)

if TYPE_CHECKING:
    from kartograf.store import Sidecar, StoreEntry

_WGS84 = "EPSG:4326"
_ENVELOPE_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)
_FES = "http://www.opengis.net/fes/2.0"
_GML = "{http://www.opengis.net/gml/3.2}"
_MS = "{http://mapserver.gis.umn.edu/mapserver}"
_WFS_MEMBER = "{http://www.opengis.net/wfs/2.0}member"
_TERYT = re.compile(r"(?:[0-9]{2}|[0-9]{4})")
_KU = re.compile(r"[0-9]{6}")
_ASC_KEYS = frozenset(
    {
        "ncols",
        "nrows",
        "xllcorner",
        "yllcorner",
        "xllcenter",
        "yllcenter",
        "cellsize",
        "dx",
        "dy",
        "nodata_value",
    }
)

# One build at a time: it switches PROJ's process-wide network flag.
_BUILD_LOCK = threading.Lock()
# Operations from a pyproj TransformerGroup are not thread-safe: one per thread.
_LOCAL = threading.local()


@dataclass(frozen=True)
class Footprint:
    """Extent of a file: the same envelope natively and in WGS84.

    Attributes
    ----------
    native : BBox
        Envelope in the file's CRS (sheet, header) or the CRS of the source
        that gave it (request bbox, unit index).
    wgs84 : BBox
        Envelope in ``EPSG:4326`` (longitude, latitude).
    source : str
        ``request`` (bbox of the request), ``sheet`` (computable sheet code
        PL-1992/PL-2000/TM33), ``header`` (GeoTIFF, ASC, JPEG + world file,
        GPKG, LAS/LAZ) or ``unit`` (PRG, RUIAN or SM5 index).
    """

    native: BBox
    wgs84: BBox
    source: str


def pinned_transform(src_crs: str, dst_crs: str) -> PinnedTransform:
    """The pinned operation Kartograf uses for envelopes of this CRS pair.

    Chosen once per thread by ``transform.crs.build_pinned_transform``: an
    operation with a known accuracy of at most 1 m, without ballpark and
    without network grids, the Czech datum step for S-JTSK (ADR-024). No
    approximate fallback: S-JTSK with ballpark is about 100 m off.

    Thread-safe: may be called concurrently from any number of threads
    (e.g. a thread pool); each thread gets its own object, built one
    thread at a time. Do not pass the returned object to another thread.

    Parameters
    ----------
    src_crs, dst_crs : str
        CRS definitions accepted by pyproj, e.g. ``"EPSG:5514"``.

    Returns
    -------
    PinnedTransform
        ``transform(xs, ys)`` (always_xy order; scalars or numpy arrays;
        inf/NaN = ``TransformError``), ``description``, ``accuracy_m``,
        ``src_crs``, ``dst_crs``. The object is cached for the calling
        thread; call the function in every thread rather than sharing it.

    Raises
    ------
    TransformUnavailableError
        No operation satisfies the policy (with the rejected candidates).
    """
    cache: dict[tuple[str, str], PinnedTransform] | None = getattr(
        _LOCAL, "pinned", None
    )
    if cache is None:
        cache = _LOCAL.pinned = {}
    pinned = cache.get((src_crs, dst_crs))
    if pinned is None:
        with _BUILD_LOCK:
            pinned = build_pinned_transform(src_crs, dst_crs, _ENVELOPE_POLICY)
        cache[(src_crs, dst_crs)] = pinned
    return pinned


def _same_crs(first: str, second: str) -> bool:
    return first.strip().upper() == second.strip().upper() or (
        CRS.from_user_input(first) == CRS.from_user_input(second)
    )


def _reproject(bbox: BBox, target: str) -> BBox:
    if _same_crs(bbox.crs, target):
        return bbox._replace(crs=target)
    return transform_bbox(bbox, target, transformer=pinned_transform(bbox.crs, target))


def _footprint(bbox: BBox, source: str) -> Footprint:
    return Footprint(bbox, _reproject(bbox, _WGS84), source)


def _valid_bbox(coords: Any, crs: Any) -> BBox | None:
    if not isinstance(crs, str) or not crs.strip():
        return None
    if not isinstance(coords, (tuple, list)) or len(coords) != 4:
        return None
    try:
        if any(isinstance(value, bool) for value in coords):
            return None
        min_x, min_y, max_x, max_y = (float(value) for value in coords)
        bbox = BBox(min_x, min_y, max_x, max_y, crs)
        validate_bbox(bbox)
        crs_info = CRS.from_user_input(crs)
        if crs_info.is_geographic and (
            bbox.min_x < -180 or bbox.max_x > 180 or bbox.min_y < -90 or bbox.max_y > 90
        ):
            return None
    except (TypeError, ValueError, ValidationError, CRSError):
        return None
    return bbox


def _stem(entry: StoreEntry) -> str:
    return entry.name.split(".", 1)[0]


def _sheet_footprint(entry: StoreEntry, meta: Sidecar | None) -> Footprint | None:
    """Extent computed from a PL-1992, PL-2000 or TM33 sheet code (offline)."""
    request = meta.request if meta is not None else None
    sheet = request.get("sheet") if request is not None else None
    if not isinstance(sheet, str):
        sheet = entry.name.rsplit(".", 1)[0]
    sheet = sheet.strip()
    system = detect_system(sheet).id
    geographic: BBox | None = None
    try:
        if system == "cz_tm33":
            native = ParserTM33(sheet).get_bbox()
        elif system in ("pl1992", "pl2000"):
            if meta is not None and meta.country not in (None, "PL", "pl"):
                return None
            parser = SheetParser(sheet)
            if system == "pl1992":
                # A PL-1992 sheet is a longitude/latitude rectangle: exact in
                # WGS84, projected with the pinned operation (not the
                # parser's default transformer).
                geographic = parser.get_bbox(_WGS84)
                native = _reproject(geographic, "EPSG:2180")
            else:
                native = parser.get_bbox()
        else:
            return None  # SM5 is an indexed sheet, not a computable grid
    except ValidationError:  # incl. ParseError
        return None
    crs = meta.horizontal_crs if meta is not None else None
    try:
        if crs and not _same_crs(native.crs, crs):
            # E17: the file is published in another CRS than its code says.
            native = _reproject(native, crs)
            geographic = None
    except CRSError:
        return None
    if geographic is not None:
        return Footprint(native, geographic, "sheet")
    return _footprint(native, "sheet")


def _asc_bbox(path: Path, crs: str) -> BBox | None:
    header: dict[str, float] = {}
    try:
        with path.open("rb") as stream:
            for _ in range(12):
                line = stream.readline(256)
                if not line or len(line) >= 256:
                    break
                parts = line.decode("ascii").split()
                if len(parts) != 2 or parts[0].lower() not in _ASC_KEYS:
                    break
                header[parts[0].lower()] = float(parts[1])
        width, height = header["ncols"], header["nrows"]
        dx = header.get("dx", header.get("cellsize"))
        dy = header.get("dy", header.get("cellsize"))
        if dx is None or dy is None or min(width, height, dx, dy) <= 0:
            return None
        x0 = header.get("xllcorner", header.get("xllcenter", math.nan) - dx / 2)
        y0 = header.get("yllcorner", header.get("yllcenter", math.nan) - dy / 2)
        return _valid_bbox((x0, y0, x0 + width * dx, y0 + height * dy), crs)
    except (OSError, UnicodeError, ValueError, KeyError):
        return None


def _world_bbox(world: Path, width: int, height: int, crs: str) -> BBox | None:
    try:
        with world.open(encoding="ascii") as stream:
            values = [float(stream.readline()) for _ in range(6)]
            if stream.readline().strip():
                return None
        a, d, b, e, c, f = values
        # The world-file origin is the centre of the top-left pixel.
        points = [
            (c + a * (x - 0.5) + b * (y - 0.5), f + d * (x - 0.5) + e * (y - 0.5))
            for x, y in ((0, 0), (width, 0), (0, height), (width, height))
        ]
        return _valid_bbox(
            (
                min(x for x, _ in points),
                min(y for _, y in points),
                max(x for x, _ in points),
                max(y for _, y in points),
            ),
            crs,
        )
    except (OSError, UnicodeError, ValueError):
        return None


def _raster_bbox(path: Path, crs: str | None, world: Path | None = None) -> BBox | None:
    import rasterio

    try:
        # Sibling files are probed by name, never by listing the directory
        # (a bbox/ slot of a share may hold thousands of files).
        with (
            rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="TRUE"),
            rasterio.open(path, "r") as raster,
        ):
            if raster.width < 1 or raster.height < 1:
                return None
            if path.suffix.lower() in {".jpg", ".jpeg"}:
                world = world or path.with_suffix(".jgw")
                return (
                    _world_bbox(world, raster.width, raster.height, crs)
                    if crs
                    else None
                )
            file_crs = raster.crs.to_string() if raster.crs is not None else crs
            if file_crs is None or raster.transform.is_identity:
                return None
            b = raster.bounds
            return _valid_bbox((b.left, b.bottom, b.right, b.top), file_crs)
    except (OSError, rasterio.errors.RasterioError):
        return None


def _gpkg_bbox(path: Path) -> BBox | None:
    # SQLite's immutable URI neither creates a journal on a network share nor
    # writes -shm/-wal files. Do not open GPKGs in read/write mode.
    uri = f"file:{quote(os.fspath(path.absolute()), safe='/')}?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            rows = conn.execute(
                "SELECT c.min_x,c.min_y,c.max_x,c.max_y,s.organization,"
                "s.organization_coordsys_id,s.definition FROM gpkg_contents AS c "
                "JOIN gpkg_spatial_ref_sys AS s ON s.srs_id=c.srs_id "
                "WHERE c.data_type='features'"
            ).fetchall()
    except sqlite3.Error:
        return None
    if not rows:
        return None
    extents = []
    for min_x, min_y, max_x, max_y, authority, code, wkt in rows:
        crs = f"{authority}:{code}" if authority == "EPSG" else wkt
        box = _valid_bbox((min_x, min_y, max_x, max_y), crs)
        if box is None:
            return None  # a partial union would hide a layer of the file
        extents.append(box)
    target = extents[0].crs
    aligned = [_reproject(extent, target) for extent in extents]
    return BBox(
        min(b.min_x for b in aligned),
        min(b.min_y for b in aligned),
        max(b.max_x for b in aligned),
        max(b.max_y for b in aligned),
        target,
    )


def _las_bbox(path: Path, crs: str | None) -> BBox | None:
    if not crs:
        return None
    try:
        with path.open("rb") as stream:
            header = stream.read(255)
        if (
            len(header) < 227
            or header[:4] != b"LASF"
            or header[24] != 1
            or header[25] > 4
        ):
            return None
        size = struct.unpack_from("<H", header, 94)[0]
        if size < 227:
            return None
        # LAS 1.4 may store the point count in the extended 64-bit field.
        if struct.unpack_from("<I", header, 107)[0] == 0 and (
            header[25] != 4
            or size < 375
            or len(header) < 255
            or struct.unpack_from("<Q", header, 247)[0] == 0
        ):
            return None
        max_x, min_x, max_y, min_y = struct.unpack_from("<4d", header, 179)
        return _valid_bbox((min_x, min_y, max_x, max_y), crs)
    except (OSError, struct.error):
        return None


def _companion(entry: StoreEntry, name: str) -> Path | None:
    """``name`` next to the file; for a version, the single version of the
    same label that holds it (CZ orthophoto members are committed one by
    one: same edition, different content hashes and directories)."""
    local = entry.path.with_name(name)
    if local.is_file():
        return local
    if entry.kind != "version" or not entry.label:
        return None
    # Never substitute the mutable current link for an older JPEG/world file.
    label_dir = entry.path.parent
    prefix = f"{entry.label}_"
    if not label_dir.name.startswith(prefix) or not re.fullmatch(
        r"[0-9a-f]{8}", label_dir.name[len(prefix) :]
    ):
        return None
    matches = []
    try:
        for sibling in label_dir.parent.iterdir():
            if sibling.name.startswith(prefix) and re.fullmatch(
                r"[0-9a-f]{8}", sibling.name[len(prefix) :]
            ):
                candidate = sibling / name
                if candidate.is_file():
                    matches.append(candidate)
    except OSError:
        return None
    return matches[0] if len(matches) == 1 else None


def _header_bbox(entry: StoreEntry, meta: Sidecar | None) -> BBox | None:
    crs = meta.horizontal_crs if meta is not None else None
    suffix = entry.path.suffix.lower()
    if suffix == ".asc" and crs:
        return _asc_bbox(entry.path, crs)
    if suffix in {".tif", ".tiff"}:
        return _raster_bbox(entry.path, crs)
    if suffix in {".jpg", ".jpeg"}:
        return _raster_bbox(
            entry.path, crs, _companion(entry, entry.path.with_suffix(".jgw").name)
        )
    if suffix == ".jgw" and crs:
        image = _companion(entry, _stem(entry) + ".jpg")
        return _raster_bbox(image, crs, entry.path) if image is not None else None
    if suffix == ".gpkg":
        return _gpkg_bbox(entry.path)
    if suffix in {".las", ".laz"}:
        return _las_bbox(entry.path, crs)
    return None


def _teryt_bbox(code: str) -> BBox | None:
    from kartograf.providers.pl.prg import (
        POWIAT_LAYER,
        PRG_WFS_ENDPOINT,
        _feature_collection,
    )
    from kartograf.transport.http import get_with_retry, make_gugik_session

    layer = POWIAT_LAYER if len(code) == 4 else "ms:A01_Granice_wojewodztw"
    filter_xml = (
        f'<fes:Filter xmlns:fes="{_FES}"><fes:PropertyIsEqualTo>'
        f"<fes:ValueReference>JPT_KOD_JE</fes:ValueReference>"
        f"<fes:Literal>{code}</fes:Literal></fes:PropertyIsEqualTo></fes:Filter>"
    )
    with make_gugik_session() as session:
        response = get_with_retry(
            session,
            PRG_WFS_ENDPOINT,
            timeout=30,
            description="PRG unit extent",
            params={
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAMES": layer,
                "SRSNAME": "urn:ogc:def:crs:EPSG::2180",
                "FILTER": filter_xml,
                "COUNT": "2",
            },
        )
    root = _feature_collection(response.content)
    members = root.findall(_WFS_MEMBER)
    if (
        len(members) != 1
        or root.get("numberReturned") != "1"
        or root.get("numberMatched") not in ("1", "unknown")
    ):
        return None
    feature = members[0].find(f"{_MS}{layer.split(':', 1)[1]}")
    if feature is None or feature.findtext(f"{_MS}JPT_KOD_JE") != code:
        return None
    envelope = feature.find(f"{_GML}boundedBy/{_GML}Envelope")
    if envelope is None or envelope.get("srsName") != "urn:ogc:def:crs:EPSG::2180":
        return None
    lower = (envelope.findtext(f"{_GML}lowerCorner") or "").split()
    upper = (envelope.findtext(f"{_GML}upperCorner") or "").split()
    if len(lower) != 2 or len(upper) != 2:
        return None
    # WFS 2.0 EPSG:2180 axis order is northing, easting.
    return _valid_bbox((lower[1], lower[0], upper[1], upper[0]), "EPSG:2180")


def _ku_bbox(code: str) -> BBox | None:
    from kartograf.providers.cuzk.client import CuzkClient
    from kartograf.providers.cuzk.sheets import _rings_envelope

    features = CuzkClient().query(
        "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer",
        7,
        where=f"kod={int(code)}",
        out_fields="kod",
        out_sr="EPSG:5514",
    )
    actual = (
        features[0].get("attributes", {}).get("kod") if len(features) == 1 else None
    )
    if isinstance(actual, bool) or not isinstance(actual, (int, str)):
        return None
    if not str(actual).isdigit() or int(actual) != int(code):
        return None
    return _rings_envelope(features[0], "EPSG:5514")


def _sm5_bbox(code: str) -> BBox | None:
    from kartograf.providers.cuzk.sheets import SheetIndex

    try:
        return SheetIndex().sm5_sheet(code).bbox
    except ValidationError:  # not in the index (like an unknown TERYT or KU)
        return None


def _unit_key(entry: StoreEntry, meta: Sidecar | None) -> tuple[str, str] | None:
    """``(kind, code)`` of the unit index entry for the file, if any."""
    request = (meta.request if meta is not None else None) or {}
    slot = entry.hierarchy.split("/", 1)[0]
    if slot == "teryt":
        code = str(request.get("teryt") or _stem(entry))
        return ("teryt", code) if _TERYT.fullmatch(code) else None
    if slot == "ku":
        code = str(request.get("ku") or _stem(entry))
        return ("ku", code) if _KU.fullmatch(code) else None
    if meta is not None and meta.country == "CZ":
        sheet = request.get("sheet")
        code = sheet if isinstance(sheet, str) else entry.name.rsplit(".", 1)[0]
        if CZ_SM5_PATTERN.fullmatch(code):
            return "sm5", code
    return None


def _unit_bbox(
    entry: StoreEntry,
    meta: Sidecar | None,
    cache: MutableMapping[tuple[str, str], BBox] | None,
    network: bool,
) -> BBox | None:
    key = _unit_key(entry, meta)
    if key is None:
        return None
    if cache is not None and key in cache:
        return cache[key]
    if not network:
        return None
    kind, code = key
    load = _ku_bbox if kind == "ku" else _sm5_bbox if kind == "sm5" else _teryt_bbox
    bbox = load(code)
    if bbox is not None and cache is not None:
        cache[key] = bbox
    return bbox


def _sidecar_of(entry: StoreEntry) -> Sidecar | None:
    if entry.sidecar is not None or entry.kind == "problem":
        return entry.sidecar
    from kartograf.store import read_sidecar

    try:
        return read_sidecar(entry.path)  # e.g. a skipped version
    except InvalidSidecarError:
        return None


def file_footprint(
    entry: StoreEntry,
    *,
    network: bool = False,
    cache: MutableMapping[tuple[str, str], BBox] | None = None,
) -> Footprint | None:
    """Extent of a store file from the first trustworthy source.

    Order: the request bbox (``request.bbox`` + ``bbox_crs``), a computable
    sheet code (PL-1992, PL-2000, TM33), the file header (GeoTIFF, ASC,
    JPEG + world file, GPKG, LAS/LAZ), the unit (TERYT from PRG, KU from
    RUIAN, SM5 sheet from the CUZK index). A malformed source is skipped;
    a file without any (a national package) has no footprint.

    Parameters
    ----------
    entry : StoreEntry
        An entry of ``iter_store``; without ``sidecar`` (``skipped``) the
        sidecar is read first (one small file).
    network : bool, default False
        Allow queries of the unit indexes (PRG WFS, RUIAN, CUZK SM5 index);
        without it no request leaves the process.
    cache : MutableMapping, optional
        The caller's memory of unit envelopes, ``(kind, code) -> BBox``
        (kind ``teryt``, ``ku``, ``sm5``; native CRS). Read also without
        ``network``; filled by network queries.

    Returns
    -------
    Footprint or None
        Native and WGS84 envelopes with their ``source``; ``None`` when no
        source gives a trustworthy extent.

    Raises
    ------
    TransformUnavailableError
        No safe operation from the file's CRS to WGS84 (never approximated).
    DownloadError
        A unit index failed (only with ``network=True``).
    ParseError
        A unit index feature without usable geometry (only with
        ``network=True``).
    TransformError
        A source envelope lies outside the area of the pinned operation.

    Notes
    -----
    Thread-safe: may be called concurrently from any number of threads
    (e.g. a thread pool over ``iter_store`` entries). The only state shared
    between calls is ``cache``: one plain ``dict`` may serve all threads;
    two threads missing the same unit may both query its index.
    """
    meta = _sidecar_of(entry)
    request = meta.request if meta is not None else None
    if request is not None:
        bbox = _valid_bbox(request.get("bbox"), request.get("bbox_crs"))
        if bbox is not None:
            return _footprint(bbox, "request")
    footprint = _sheet_footprint(entry, meta)
    if footprint is not None:
        return footprint
    bbox = _header_bbox(entry, meta)
    if bbox is not None:
        return _footprint(bbox, "header")
    bbox = _unit_bbox(entry, meta, cache, network)
    if bbox is not None:
        return _footprint(bbox, "unit")
    return None
