"""
SheetIndex — KladyMapovychListu sheet index (ArcGIS REST /query) with a cache.

Layer 24: SM5 (MAPNOM, MAPNAME, PODIL) in EPSG:5514.
Layer 26: TM33 2x2 km grid (MAPNOM, IN_CZ) in EPSG:3045.
Note: host `arcgis`, not `arcgis2`. Zero IO at import and construction.

OVER-SELECTION FILTER (reconnaissance Task 1, step 3b) —
`esriSpatialRelIntersects` selects more than the envelope asks for:
1. sheets touching the envelope only with an edge/corner (the envelope from
   the fixture `klady_sm5_bbox.json`: 13 returned, 7 actually intersecting),
2. with an `inSR` other than the native Krovak — sheets as far as ~2 km away,
   because the server reprojects the envelope and uses its axis-parallel
   bounding box in Krovak (rotation ~7 degrees); an envelope the size of one
   TM33 tile returned 9 tiles.
Therefore every bbox method filters the result ON THE CLIENT SIDE: only
sheets whose extent intersects the envelope with its INTERIOR remain (an edge
touch does not count — the convention of `find_tiles_tm33_for_bbox` /
`find_sheets_for_bbox`). The comparison is always in one CRS: the envelope
must be in the layer's native CRS, in which the service returns geometry
(otherwise `ValidationError`).

IN_CZ (layer 26) has only one value — "CZ" for all 20,308 tiles — so it is
NOT a border discriminator; the indicator of "how much of the sheet lies in
CZ" is PODIL of layer 24.
"""

import logging
from dataclasses import dataclass
from typing import Any

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import CZ_SM5_PATTERN
from kartograf.core.parser_tm33 import TM33_CRS
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient

logger = logging.getLogger(__name__)

KLADY_ENDPOINT = (
    "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"
)
SM5_LAYER = 24
TM33_LAYER = 26
SM5_CRS = "EPSG:5514"
SM5_SYSTEM = "cz_sm5"  # `system` key in sheet_cache

_SM5_FIELDS = "MAPNOM,MAPNAME,PODIL"
_TM33_FIELDS = "MAPNOM,IN_CZ"

_SM5_HINT = "oczekiwano 4 wielkich liter + 2 cyfr, np. CTES96"

# ArcGIS coordinates carry gridding noise of the order of 1e-3 m (e.g.
# -449999.999308 instead of -450000), so an edge touch must be detected with a
# tolerance. 1 cm is an order of magnitude above the noise and orders of
# magnitude below the size of a sheet (2500 x 2000 m) or a tile (2000 x 2000 m).
_OVERLAP_TOLERANCE_M = 0.01


@dataclass(frozen=True)
class SheetInfo:
    """One sheet/tile from the KladyMapovychListu index."""

    godlo: str  # MAPNOM ("CTES96" / "744_5534")
    name: str | None  # MAPNAME ("Český Těšín 9-6"); None for TM33
    bbox: BBox  # EPSG:5514 (layer 24) / EPSG:3045 (layer 26)
    podil: float | None  # share of the sheet in CZ territory; None for TM33
    in_cz: bool | None  # layer 26; None for SM5


class SheetIndex:
    """Sheet index with MAPNOM/bbox queries and the sheet_cache cache."""

    def __init__(
        self,
        session: Any = None,
        cache: MetadataCache | None = None,
        endpoint: str = KLADY_ENDPOINT,
    ):
        self._client = CuzkClient(session=session)
        self._cache = cache
        self._endpoint = endpoint

    def sm5_sheet(self, mapnom: str) -> SheetInfo:
        """SM5 sheet by MAPNOM; ValidationError when unknown (before download)."""
        if not isinstance(mapnom, str) or not CZ_SM5_PATTERN.match(mapnom.strip()):
            raise ValidationError(f"Niepoprawne godlo SM5: '{mapnom}' ({_SM5_HINT})")
        mapnom = mapnom.strip()  # consistent with detect_system (system registry)
        if self._cache is not None:
            cached = self._cache.get_sheet(SM5_SYSTEM, mapnom)
            if cached is not None:
                info = _info_from_payload(cached)
                if info is not None:
                    return info
        # mapnom passed CZ_SM5_PATTERN (only [A-Z] and digits) — no injection
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            where=f"MAPNOM='{mapnom}'",
            out_fields=_SM5_FIELDS,
            out_sr=SM5_CRS,
        )
        if not features:
            raise ValidationError(
                f"Arkusz SM5 '{mapnom}' nie istnieje w indeksie "
                f"KladyMapovychListu (warstwa {SM5_LAYER})"
            )
        info = _sm5_info(features[0])
        if self._cache is not None:
            self._cache.set_sheet(SM5_SYSTEM, mapnom, _payload_from_info(info))
        return info

    def sm5_sheets_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """SM5 sheets intersecting the bbox (foundation of stage 2: LAZ/Orto)."""
        _validate_request_bbox(bbox, SM5_CRS, "sm5_sheets_for_bbox")
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            bbox=bbox,
            out_fields=_SM5_FIELDS,
            out_sr=SM5_CRS,
        )
        return _intersecting(bbox, [_sm5_info(f) for f in features])

    def tm33_tiles_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """TM33 tiles intersecting the bbox (with the IN_CZ attribute)."""
        _validate_request_bbox(bbox, TM33_CRS, "tm33_tiles_for_bbox")
        features = self._client.query(
            self._endpoint,
            TM33_LAYER,
            bbox=bbox,
            out_fields=_TM33_FIELDS,
            out_sr=TM33_CRS,
        )
        return _intersecting(bbox, [_tm33_info(f) for f in features])


def _validate_request_bbox(bbox: BBox, expected_crs: str, method: str) -> None:
    """The envelope must be in the layer CRS (the filter works in a single CRS)."""
    if bbox.crs.strip().upper() != expected_crs:
        raise ValidationError(
            f"{method} wymaga bbox w {expected_crs} (usluga zwraca geometrie "
            f"w tym ukladzie, a filtr przeciec wymaga wspolnego CRS), "
            f"otrzymano: {bbox.crs}"
        )
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            f"Niepoprawny bbox: ({bbox.min_x}, {bbox.min_y}, "
            f"{bbox.max_x}, {bbox.max_y})"
        )


def _overlaps_interior(sheet: BBox, request: BBox) -> bool:
    """Whether the extents share a part of positive area (edge touch => False)."""
    width = min(sheet.max_x, request.max_x) - max(sheet.min_x, request.min_x)
    height = min(sheet.max_y, request.max_y) - max(sheet.min_y, request.min_y)
    return width > _OVERLAP_TOLERANCE_M and height > _OVERLAP_TOLERANCE_M


def _intersecting(bbox: BBox, infos: list[SheetInfo]) -> list[SheetInfo]:
    """Drop the service's over-selection; result sorted by sheet code (determinism)."""
    kept = [i for i in infos if _overlaps_interior(i.bbox, bbox)]
    if len(kept) != len(infos):
        dropped = sorted({i.godlo for i in infos} - {i.godlo for i in kept})
        logger.debug(
            f"KladyMapovychListu: odrzucono {len(infos) - len(kept)} "
            f"nieprzecinajacych arkuszy: {', '.join(dropped)}"
        )
    return sorted(kept, key=lambda i: i.godlo)


def _rings_envelope(feature: dict, crs: str) -> BBox:
    """Envelope of ALL rings of the geometry.

    For a polygon with holes the inner rings lie within the outer one, so the
    envelope is exact. For a multipart polygon the envelope is a superset of
    the parts — the filter may then keep one sheet too many, but will NEVER
    lose a sheet that actually intersects the envelope (the safe direction
    of error). SM5 sheets and TM33 tiles are in practice rectangles with a
    single ring.
    """
    geometry = feature.get("geometry") or {}
    points = [pt for ring in geometry.get("rings") or [] for pt in ring]
    if not points:
        raise ParseError(
            f"Feature bez geometrii 'rings' w odpowiedzi KladyMapovychListu: "
            f"{feature.get('attributes')}"
        )
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return BBox(min(xs), min(ys), max(xs), max(ys), crs)


def _mapnom(feature: dict) -> str:
    mapnom = (feature.get("attributes") or {}).get("MAPNOM")
    if not mapnom:
        raise ParseError(
            f"Feature bez atrybutu MAPNOM w odpowiedzi KladyMapovychListu: {feature}"
        )
    return str(mapnom)


def _sm5_info(feature: dict) -> SheetInfo:
    attrs = feature.get("attributes") or {}
    podil = attrs.get("PODIL")
    return SheetInfo(
        godlo=_mapnom(feature),
        name=attrs.get("MAPNAME"),
        bbox=_rings_envelope(feature, SM5_CRS),
        podil=float(podil) if podil is not None else None,
        in_cz=None,
    )


def _tm33_info(feature: dict) -> SheetInfo:
    attrs = feature.get("attributes") or {}
    return SheetInfo(
        godlo=_mapnom(feature),
        name=None,
        bbox=_rings_envelope(feature, TM33_CRS),
        podil=None,
        in_cz=_parse_in_cz(attrs.get("IN_CZ")),
    )


def _parse_in_cz(value: Any) -> bool | None:
    """IN_CZ arrives as a string ("CZ"); in practice always the same value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().upper() == "CZ"
    return bool(value)


def _payload_from_info(info: SheetInfo) -> dict:
    return {
        "godlo": info.godlo,
        "name": info.name,
        "bbox": [info.bbox.min_x, info.bbox.min_y, info.bbox.max_x, info.bbox.max_y],
        "bbox_crs": info.bbox.crs,
        "podil": info.podil,
        "in_cz": info.in_cz,
    }


def _info_from_payload(payload: dict) -> SheetInfo | None:
    """Restore SheetInfo from the cache; None if the entry is incomplete or old."""
    try:
        min_x, min_y, max_x, max_y = payload["bbox"]
        return SheetInfo(
            godlo=payload["godlo"],
            name=payload.get("name"),
            bbox=BBox(min_x, min_y, max_x, max_y, payload["bbox_crs"]),
            podil=payload.get("podil"),
            in_cz=payload.get("in_cz"),
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Pomijam niezdatny wpis sheet_cache ({e}): {payload}")
        return None
