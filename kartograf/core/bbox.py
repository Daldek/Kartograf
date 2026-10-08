"""
Bounding box and its envelope in another coordinate system.

A leaf module of the ``core`` layer (dependencies: ``pyproj``, ``numpy``,
``kartograf.exceptions``): the single place that decides "how to convert a
bbox between CRSs". The envelope is ALWAYS computed from densified edges: the
image of a rectangle in another CRS is a quadrilateral with curved sides, and
four corners miss the strip near the central meridian of the target CRS (19E
for EPSG:2180, 15/18/21/24E for PL-2000 zones; up to ~480 m for a 2 x 0.2 deg
bbox).

A pinned operation (ADR-024, ``kartograf.transform.crs.PinnedTransform``)
comes in through duck typing (``transformer=``): ``core`` does not import
``transform`` and does not choose the operation; it receives it from the
caller.
"""

import functools
import math
from typing import Any, NamedTuple

import numpy as np
from pyproj import CRS, Transformer

from kartograf.exceptions import ValidationError

# Number of points per edge (as in corine/soilgrids `transform_bounds`).
_DENSIFY = 21

# wkids of the CRSs in which CUZK publishes data (S-JTSK/Krovak, ETRS89/TM33);
# a request given in them leaves Krovak only via the pinned operation (ADR-024)
_CZ_WKIDS = frozenset({"5514", "3045"})
_CZ_AUTHORITIES = frozenset({"", "EPSG", "ESRI"})


class BBox(NamedTuple):
    """Bounding box with coordinates and a coordinate reference system."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str


def _norm_label(crs: str) -> str:
    return crs.strip().upper()


@functools.lru_cache(maxsize=64)
def _transformer(src: str, dst: str) -> Transformer:
    """Transformer for a CRS pair, once per process (thread-safe since pyproj 3.1)."""
    return Transformer.from_crs(src, dst, always_xy=True)


@functools.lru_cache(maxsize=64)
def _same_crs(src: str, dst: str) -> bool:
    """Whether two labels (or WKT strings) describe the same CRS."""
    if _norm_label(src) == _norm_label(dst):
        return True
    return bool(CRS.from_user_input(src) == CRS.from_user_input(dst))


def validate_bbox(bbox: BBox, *, crs: str | None = None) -> None:
    """
    Validate a bbox.

    A degenerate bbox (point/line, ``min == max``) is ALLOWED - this is the
    documented behaviour of ``find_sheets_for_bbox`` (exactly one sheet).

    Parameters
    ----------
    bbox : BBox
        Bbox to validate
    crs : str, optional
        Expected CRS of the bbox (labels are compared case-insensitively and
        ignoring whitespace)

    Raises
    ------
    ValidationError
        Infinite/NaN coordinate, ``min > max`` on either axis, or a CRS
        different from the expected one.
    """
    coords = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if not all(math.isfinite(v) for v in coords):
        raise ValidationError(
            f"wspolrzedne bboxa musza byc skonczone, otrzymano {coords}"
        )
    if bbox.min_x > bbox.max_x or bbox.min_y > bbox.max_y:
        raise ValidationError(
            f"bbox odwrocony (min > max): {coords}; "
            "oczekiwano min_x <= max_x i min_y <= max_y"
        )
    if crs is not None and _norm_label(bbox.crs) != _norm_label(crs):
        raise ValidationError(f"bbox w ukladzie {bbox.crs!r}, oczekiwano {crs!r}")


def transform_bbox(bbox: BBox, target_crs: str, *, transformer: Any = None) -> BBox:
    """
    Envelope of a bbox in the target CRS, always from densified edges.

    Parameters
    ----------
    bbox : BBox
        Source bbox; ``bbox.crs`` is a label (``"EPSG:2180"``) or WKT
    target_crs : str
        Target CRS; it goes into the ``crs`` field of the result unchanged
    transformer : object, optional
        ``None`` -> cached pyproj transformer, ``transform_bounds`` with
        ``densify_pts=21``. An object with a ``.transform(xs, ys)`` method
        (e.g. ``PinnedTransform``) -> 21 samples per edge (84 points),
        min/max envelope; the object, not the labels, determines source/target.

    Returns
    -------
    BBox
        Envelope in ``target_crs``. Same CRS (e.g. ``"epsg:2180"`` ->
        ``"EPSG:2180"``) -> the same coordinates with the target label.
    """
    if transformer is None:
        if _same_crs(bbox.crs, target_crs):
            return bbox._replace(crs=target_crs)
        pyproj_transformer = _transformer(bbox.crs, target_crs)
        min_x, min_y, max_x, max_y = pyproj_transformer.transform_bounds(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, densify_pts=_DENSIFY
        )
        return BBox(min_x, min_y, max_x, max_y, target_crs)

    xs = np.linspace(bbox.min_x, bbox.max_x, _DENSIFY)
    ys = np.linspace(bbox.min_y, bbox.max_y, _DENSIFY)
    west = np.full(_DENSIFY, bbox.min_x)
    east = np.full(_DENSIFY, bbox.max_x)
    south = np.full(_DENSIFY, bbox.min_y)
    north = np.full(_DENSIFY, bbox.max_y)
    out_x, out_y = transformer.transform(
        np.concatenate([xs, xs, west, east]),
        np.concatenate([south, north, ys, ys]),
    )
    return BBox(
        float(np.min(out_x)),
        float(np.min(out_y)),
        float(np.max(out_x)),
        float(np.max(out_y)),
        target_crs,
    )


def is_czech_crs(label: str) -> bool:
    """
    Whether the CRS is a Czech CUZK data CRS (EPSG:5514 / EPSG:3045).

    Compared by wkid: ``" epsg:5514 "``, ``"5514"`` and ``"ESRI:5514"``
    (ArcGIS uses the same wkids) give True.
    """
    norm = _norm_label(label)
    authority, _, code = norm.rpartition(":")
    return authority in _CZ_AUTHORITIES and code in _CZ_WKIDS
