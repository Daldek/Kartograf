"""GUGiK PRG WFS: powiat TERYT codes (A1, 0.7.1) and the PL land mask (0.7.2).

Powiats: the one place that asks which powiats an area or a point lies in.
The filter is the powiat GEOMETRY (MapServer WFS 2.0, verified live
2026-10-08), not its envelope. A service or response failure is a
``DownloadError``; an empty list only comes from a valid response
without features (sea, abroad).

Land mask (WCS cutouts, ADR-035): ``A00_Granice_panstwa`` minus
``W02_Morze_terytorialne_RP`` and ``W03_Morskie_wody_wewnetrzne``. ``BBOX``
does not clip geometries (A00 is always the whole country, ~2 MB); W02/W03
return no features away from the coast
(``docs/research/2026-10-11-wcs-cutouts/raport.md``, point 6).
"""

import logging
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError
from kartograf.messages import message, reason
from kartograf.transport.http import SessionPerThread, get_with_retry

logger = logging.getLogger(__name__)

PRG_WFS_ENDPOINT = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
)
POWIAT_LAYER = "ms:A02_Granice_powiatow"
_MS = "{http://mapserver.gis.umn.edu/mapserver}"
_WFS_COLLECTION = "{http://www.opengis.net/wfs/2.0}FeatureCollection"
_WFS_MEMBER = "{http://www.opengis.net/wfs/2.0}member"
_GML = "{http://www.opengis.net/gml/3.2}"
_LAND_LAYER = "ms:A00_Granice_panstwa"
_WATER_LAYERS = (
    "ms:W02_Morze_terytorialne_RP",
    "ms:W03_Morskie_wody_wewnetrzne",
)
_TERYT = re.compile(r"\d{4}")
# Upper bound of features per request; Poland has ~380 powiats.
_COUNT = 1000
# Half-size (m) of the query square around a point.
_POINT_HALF = 0.5
# Pixels per row strip of LandMask.apply (~4 Mpx: tens of MB of working arrays,
# a few hundred rasterize calls of the ~73k-vertex A00 polygon for 1000 km2).
_MASK_STRIP_PX = 4_000_000

_sessions = SessionPerThread(None)


def _to_2180(bbox: BBox) -> BBox:
    """Area in EPSG:2180 - the shared rule (Czech CRSs via the pinned operation)."""
    # providers -> download must stay lazy (download imports providers)
    from kartograf.download.area import bbox_to_2180

    return bbox_to_2180(bbox)


def _mm(value: float, rounding: Callable[[float], int]) -> str:
    """Coordinate rounded to whole millimetres by ``math.floor``/``math.ceil``.

    Outward rounding never shrinks the area; millimetres (not metres) keep
    the 1 m point square of ``teryt_for_point`` a 1 m square. Trailing
    zeros are dropped (``290000.000`` -> ``290000``).
    """
    text = f"{rounding(round(value * 1000, 6)) / 1000:.3f}"
    return text.rstrip("0").rstrip(".")


def _query(bbox: BBox, session: requests.Session, timeout: float) -> list[str]:
    """Sorted unique powiat codes of one GetFeature request (``bbox`` in 2180)."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": POWIAT_LAYER,
        "PROPERTYNAME": "JPT_KOD_JE",
        "COUNT": str(_COUNT),
        # WFS 2.0 + urn CRS: (N, E) axis order; widened outward (rounding to
        # the nearest metre could drop a 0.5 m edge strip of the area)
        "BBOX": (
            f"{_mm(bbox.min_y, math.floor)},{_mm(bbox.min_x, math.floor)},"
            f"{_mm(bbox.max_y, math.ceil)},{_mm(bbox.max_x, math.ceil)},"
            "urn:ogc:def:crs:EPSG::2180"
        ),
    }
    response = get_with_retry(
        session,
        PRG_WFS_ENDPOINT,
        timeout=timeout,
        description=message("providers.prg_query_counties"),
        params=params,
    )
    root = _feature_collection(response.content)

    codes = []
    for element in root.iter(f"{_MS}JPT_KOD_JE"):
        code = (element.text or "").strip()
        if not _TERYT.fullmatch(code):
            raise DownloadError(message("providers.invalid_county_teryt", code=code))
        codes.append(code)
    _check_complete(root, len(codes))
    return sorted(set(codes))


def _feature_collection(content: bytes) -> ET.Element:
    """Reject malformed XML and WFS error reports (including HTTP 200 errors)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise DownloadError(
            message("providers.response_not_xml", error=reason(e))
        ) from e
    if root.tag != _WFS_COLLECTION:
        text = " ".join(t.strip() for t in root.itertext() if t.strip())[:300]
        raise DownloadError(message("providers.service_error", tag=root.tag, text=text))
    return root


def _ring(element: ET.Element) -> list[list[float]]:
    """Decode GML (northing, easting) pairs as GeoJSON (easting, northing)."""
    pos = element.find(f"{_GML}LinearRing/{_GML}posList")
    if pos is None or pos.get("srsDimension", "2") != "2":
        raise DownloadError(message("providers.no_2d_point_list"))
    try:
        values = np.fromstring(pos.text or "", sep=" ")
    except ValueError as e:
        raise DownloadError(message("providers.invalid_point_list")) from e
    if values.size < 8 or values.size % 2 or not np.isfinite(values).all():
        raise DownloadError(message("providers.invalid_point_list"))
    pairs: list[list[float]] = values.reshape(-1, 2)[:, ::-1].tolist()
    return pairs


def _polygon(element: ET.Element) -> list[list[list[float]]]:
    exterior = element.find(f"{_GML}exterior")
    if exterior is None:
        raise DownloadError(message("providers.polygon_no_exterior"))
    return [_ring(exterior)] + [
        _ring(interior) for interior in element.findall(f"{_GML}interior")
    ]


def _land_geometries(root: ET.Element, layer: str) -> tuple[dict[str, Any], ...]:
    """Decode all returned features, rejecting partial or unsupported answers."""
    members = root.findall(_WFS_MEMBER)
    returned = root.get("numberReturned", "")
    if not returned.isdigit() or int(returned) != len(members) or root.get("next"):
        raise DownloadError(
            message("providers.incomplete_returned", layer=layer, returned=returned)
        )
    matched = root.get("numberMatched", "")
    if matched.isdigit() and int(matched) > len(members):
        raise DownloadError(
            message("providers.incomplete_matched", layer=layer, matched=matched)
        )
    geometries: list[dict[str, Any]] = []
    for member in members:
        feature = member.find(layer.replace("ms:", _MS))
        geom = feature.find(f"{_MS}msGeometry") if feature is not None else None
        if geom is None or len(geom) != 1:
            raise DownloadError(message("providers.no_layer_geometry", layer=layer))
        shape = geom[0]
        if shape.tag == f"{_GML}Polygon":
            geometries.append({"type": "Polygon", "coordinates": _polygon(shape)})
        elif shape.tag == f"{_GML}MultiSurface":
            surfaces = shape.findall(f"{_GML}surfaceMember/{_GML}Polygon")
            if not surfaces:
                raise DownloadError(
                    message("providers.empty_multisurface", layer=layer)
                )
            geometries.append(
                {"type": "MultiPolygon", "coordinates": [_polygon(p) for p in surfaces]}
            )
        else:
            raise DownloadError(
                message("providers.unknown_geometry", layer=layer, tag=shape.tag)
            )
    return tuple(geometries)


# Classes of ``LandMask.burn``: abroad, land, Polish sea water (W02/W03).
ABROAD, LAND, SEA = 0, 1, 2


@dataclass(frozen=True)
class LandMask:
    """Polish country polygon minus territorial and internal sea water."""

    country: tuple[dict[str, Any], ...]
    water: tuple[dict[str, Any], ...]

    def burn(
        self, transform: Affine, shape: tuple[int, int]
    ) -> np.ndarray[Any, np.dtype[Any]]:
        """Classes of a grid window: ``LAND``, ``SEA`` (W02/W03) or ``ABROAD``.

        Pixel membership is decided by its centre (``all_touched=False``): A00
        burns ``LAND``, W02/W03 burn ``SEA`` over it. ``transform`` is the
        affine transform of the window (EPSG:2180), ``shape`` its (rows,
        columns); the caller keeps windows small (row strips).
        """
        classes: np.ndarray[Any, np.dtype[Any]] = rasterize(
            [(geometry, LAND) for geometry in self.country],
            out_shape=shape,
            transform=transform,
            fill=ABROAD,
            all_touched=False,
            dtype=np.uint8,
        )
        if self.water:
            rasterize(
                [(geometry, SEA) for geometry in self.water],
                out=classes,
                transform=transform,
                all_touched=False,
            )
        return classes

    def has_land(self, area: BBox, pixel: float) -> bool:
        """Check whether a pixel centre of the ``pixel`` grid of ``area`` lies on land.

        ``area`` is in EPSG:2180 (``burn`` in row strips, stops at the first land
        pixel).
        ``False``: a cutout of the area would be nodata only (sea, abroad) -
        decided from the mask alone, before any WCS request.
        """
        if not self.country:
            return False
        width = max(1, round((area.max_x - area.min_x) / pixel))
        height = max(1, round((area.max_y - area.min_y) / pixel))
        rows = max(1, _MASK_STRIP_PX // width)
        for row in range(0, height, rows):
            strip = min(rows, height - row)
            transform = from_origin(area.min_x, area.max_y - row * pixel, pixel, pixel)
            if np.any(self.burn(transform, (strip, width)) == LAND):
                return True
        return False

    def apply(self, path: Path, nodata: float) -> tuple[int, int]:
        """Mask a float32 EPSG:2180 GeoTIFF in place: pixels outside land -> nodata.

        Land per pixel centre (``burn``). Processed in row strips of about
        ``_MASK_STRIP_PX`` pixels, so memory does not grow with the cutout.
        Returns ``(masked, zero_on_land)``: pixels set to ``nodata`` and pixels
        kept on land whose value is 0.0 (data, not nodata - ADR-035).
        """
        masked = zero_on_land = 0
        with rasterio.open(path, "r+") as dataset:
            rows = max(1, _MASK_STRIP_PX // dataset.width)
            for row in range(0, dataset.height, rows):
                window = Window(0, row, dataset.width, min(rows, dataset.height - row))
                classes = self.burn(
                    dataset.window_transform(window), (window.height, window.width)
                )
                data = dataset.read(1, window=window)
                off_land = classes != LAND
                masked += int(np.count_nonzero(off_land))
                zero_on_land += int(np.count_nonzero(~off_land & (data == 0.0)))
                data[off_land] = nodata
                dataset.write(data, 1, window=window)
            dataset.nodata = nodata
        logger.debug("PRG land mask: masked=%s zero_on_land=%s", masked, zero_on_land)
        return masked, zero_on_land

    def to_payload(self) -> dict[str, Any]:
        """JSON payload of the mask (metadata cache)."""
        return {"country": list(self.country), "water": list(self.water)}

    @classmethod
    def from_payload(cls, payload: object) -> "LandMask | None":
        """Mask of a cached payload; ``None`` for an unreadable one (a miss)."""
        if not isinstance(payload, dict):
            return None
        country, water = payload.get("country"), payload.get("water")
        if not isinstance(country, list) or not isinstance(water, list) or not country:
            return None
        return cls(country=tuple(country), water=tuple(water))


def fetch_land_mask(
    area: BBox, *, session: requests.Session | None = None, timeout: float = 30
) -> LandMask:
    """Fetch A00 country and W02/W03 sea polygons intersecting an EPSG:2180 area."""
    current_session = session or _sessions.get()
    common = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature"}
    bbox = (
        f"{_mm(area.min_y, math.floor)},{_mm(area.min_x, math.floor)},"
        f"{_mm(area.max_y, math.ceil)},{_mm(area.max_x, math.ceil)},"
        "urn:ogc:def:crs:EPSG::2180"
    )
    layers = (_LAND_LAYER, *_WATER_LAYERS)
    results = []
    for layer in layers:
        params = {**common, "TYPENAMES": layer}
        if layer != _LAND_LAYER:
            params["BBOX"] = bbox
        response = get_with_retry(
            current_session,
            PRG_WFS_ENDPOINT,
            timeout=timeout,
            description=message("providers.prg_query_layer", layer=layer),
            params=params,
        )
        geometries = _land_geometries(_feature_collection(response.content), layer)
        if layer == _LAND_LAYER and not geometries:
            raise DownloadError(message("providers.no_national_boundary"))
        results.append(geometries)
        logger.debug("PRG land mask: %s: %s features", layer, len(geometries))
    return LandMask(country=results[0], water=results[1] + results[2])


def _check_complete(root: ET.Element, found: int) -> None:
    """DownloadError when the list may be incomplete (Review Focus 1, P6).

    A numeric ``numberReturned`` different from the number of parsed codes
    (``found``) means features without ``JPT_KOD_JE``. Cut =
    ``numberReturned < numberMatched``; with a non-numeric
    ``numberMatched`` (MapServer ``unknown``: matches not counted) a full
    page (``>= _COUNT``) counts as cut; a ``next`` link always does. The
    real MapServer page (recorded 2026-10-08) carries ``unknown`` and a
    ``next`` link.
    """
    matched = root.get("numberMatched", "")
    returned_attr = root.get("numberReturned", "")
    if returned_attr.isdigit() and int(returned_attr) != found:
        raise DownloadError(
            message(
                "providers.inconsistent_response",
                returned_attr=returned_attr,
                found=found,
            )
        )
    returned = found
    # non-numeric numberMatched ('unknown'): a full page counts as cut
    cut = returned < int(matched) if matched.isdigit() else returned >= _COUNT
    if cut or root.get("next"):
        raise DownloadError(
            message(
                "providers.incomplete_county_list",
                returned=returned,
                matched=matched or message("providers.unknown_county_count"),
            )
        )


def discover_teryts_for_bbox(
    bbox: BBox,
    *,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    timeout: float = 30,
) -> list[str]:
    """TERYT codes (4 digits, sorted) of powiats whose geometry intersects ``bbox``.

    ``bbox`` in any supported CRS (converted to EPSG:2180). ``cache`` keeps
    the answer for its TTL (also an empty one); ``MetadataCache(refresh=True)``
    skips the read.

    Raises
    ------
    DownloadError
        Service failure (after the shared retry policy), a response that is
        not a WFS feature collection, a truncated list or a malformed code.
    """
    area = _to_2180(bbox)
    if cache is not None:
        cached = cache.get_teryts_for_bbox(area)
        if cached is not None:
            return cached
    codes = _query(area, session or _sessions.get(), timeout)
    if cache is not None:
        cache.set_teryts_for_bbox(area, codes)
    logger.debug("PRG: %s -> %s", area, codes)
    return codes


def teryt_for_point(
    x: float,
    y: float,
    crs: str,
    *,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    timeout: float = 30,
) -> str | None:
    """TERYT code of the powiat containing the point; None = no powiat there.

    A point exactly on a boundary of two powiats gives the lower code. A
    found code goes to the point cache (``teryt_cache``); the query square
    goes through ``discover_teryts_for_bbox``, so an empty answer (sea) is
    cached too (``teryt_bbox_cache``) and not asked again within the TTL.
    """
    point = _to_2180(BBox(x, y, x, y, crs))
    px, py = point.min_x, point.min_y
    if cache is not None:
        cached = cache.get_teryt(px, py)
        if cached is not None:
            return cached
    half = _POINT_HALF
    square = BBox(px - half, py - half, px + half, py + half, "EPSG:2180")
    codes = discover_teryts_for_bbox(
        square, session=session, cache=cache, timeout=timeout
    )
    if not codes:
        return None
    if cache is not None:
        cache.set_teryt(px, py, codes[0])
    return codes[0]
