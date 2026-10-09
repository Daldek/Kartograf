"""Split of an area task between countries (A6, 0.7.1).

Country recognition and clipping to a country's envelope, shared by the CLI
(``--country auto`` and an explicit ``--country``) and library callers.
"""

from dataclasses import dataclass

from kartograf.core.bbox import BBox


def bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Bbox in WGS84 - the common CRS for country recognition and clipping.

    The default pyproj transformer (``core.bbox.transform_bbox``, an envelope
    from densified edges): it serves to RECOGNIZE the country and clip to its
    envelope, not to request a download. The pinned operation (``country_bbox``
    -> ``bbox_to_crs``) applies when LEAVING Czech CRSs
    (Krovak/UTM33N) - for a clipped PL bbox the WGS84->EPSG:2180 jump goes
    deliberately through the default (unpinned) pyproj transformer, see
    ``country_bbox``.
    """
    from kartograf.core.bbox import transform_bbox

    return transform_bbox(bbox, "EPSG:4326")


def countries_for_bbox(bbox: BBox) -> tuple[str, ...]:
    """
    Codes of countries whose ``extent_wgs84`` intersects the bbox (sorted).

    Country envelopes are rectangles, so a border strip of one country
    can lie inside the neighbor's rectangle (e.g. Opole Silesia inside the
    CZ envelope) - auto-split then queries both sources instead of guessing the border.
    """
    from kartograf.sources.registry import all_countries

    wgs = bbox_to_wgs84(bbox)
    hits = [
        profile.code
        for profile in all_countries()
        if (
            wgs.min_x < profile.extent_wgs84.max_x
            and wgs.max_x > profile.extent_wgs84.min_x
            and wgs.min_y < profile.extent_wgs84.max_y
            and wgs.max_y > profile.extent_wgs84.min_y
        )
    ]
    return tuple(sorted(hits))


@dataclass(frozen=True)
class CountryPart:
    """Part of an area task for one country (``country_bbox``).

    ``clipped`` lists the WGS84 edges actually clipped to the country's
    envelope (``"W"``, ``"S"``, ``"E"``, ``"N"``; empty = bbox unchanged) -
    the CLI turns this into an ``Info:`` (S3).
    """

    bbox: BBox
    clipped: tuple[str, ...] = ()


# edge -> (BBox field, whether clipping raises the minimum, unit)
EDGES = (
    ("W", "min_x", True, "E"),
    ("S", "min_y", True, "N"),
    ("E", "max_x", False, "E"),
    ("N", "max_y", False, "N"),
)


def country_bbox(
    bbox: BBox, code: str, *, auto: bool, cz_crs: str = "EPSG:5514"
) -> CountryPart:
    """
    Part of the bbox for a country in the CRS of its task.

    ``auto`` mode clips the bbox to the country's envelope (in WGS84) and returns the
    result in the working CRS: CZ - ``cz_crs`` (Krovak or the requested target CRS),
    PL - the task CRS unchanged (keeps the PL-2000 zone and zero drift). Without
    ``auto`` (an explicit country) NOTHING is clipped (the caller knows the extent
    of their task). Clipped edges come back in ``CountryPart.clipped``.

    When clipping changes nothing, the ORIGINAL bbox is transformed -
    one jump from the task CRS instead of two (via WGS84).

    PL after clipping (S3): only the edges in ``clipped`` take their value
    from the transformation of the clipped rectangle (the envelope of the country's
    curved edge - conservative outward), the rest keep the
    original value 1:1. The envelope of the WHOLE clipped rectangle widened
    the untouched edges by tens of meters (Rozewie: W 110 / S 38 / E 82 m),
    because the task meridian is not a straight line in EPSG:2180. The CZ part is
    by definition in a different CRS (``bbox_to_crs`` with edge sampling),
    so widening there is unavoidable and honest - unchanged.

    A task given in a Czech CRS but directed to PL (a bbox in EPSG:5514 with
    country PL or with auto-split) leaves Krovak
    IMMEDIATELY and only through the pinned operation: later steps (clipping, sheet
    selection) already work in EPSG:2180, so GUGiK sheet selection never
    results from an unpinned Krovak transformation.
    """
    from kartograf.core.bbox import is_czech_crs, transform_bbox
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_country

    if code != "CZ" and is_czech_crs(bbox.crs):
        bbox = bbox_to_crs(bbox, "EPSG:2180")

    if not auto:
        return CountryPart(bbox)

    wgs = bbox_to_wgs84(bbox)
    extent = get_country(code).extent_wgs84
    clipped = tuple(
        edge
        for edge, attr, is_min, _unit in EDGES
        if (
            getattr(wgs, attr) < getattr(extent, attr)
            if is_min
            else getattr(wgs, attr) > getattr(extent, attr)
        )
    )
    if not clipped:
        source = bbox  # clipping was a no-op
    else:
        source = BBox(
            max(wgs.min_x, extent.min_x),
            max(wgs.min_y, extent.min_y),
            min(wgs.max_x, extent.max_x),
            min(wgs.max_y, extent.max_y),
            "EPSG:4326",
        )

    target = cz_crs if code == "CZ" else bbox.crs
    if wkid(source.crs) == wkid(target):
        return CountryPart(source, clipped)
    if code == "CZ":
        # into a Czech CRS only the pinned operation with edge sampling
        # (the image of a rectangle in Krovak has curved sides)
        return CountryPart(bbox_to_crs(source, target), clipped)
    transformed = transform_bbox(source, target)
    if not clipped:
        return CountryPart(transformed)
    # PL: untouched edges 1:1 from the original, clipped ones from the transformation
    values = {
        attr: getattr(transformed if edge in clipped else bbox, attr)
        for edge, attr, _is_min, _unit in EDGES
    }
    return CountryPart(BBox(**values, crs=target), clipped)


def split_bbox_by_country(bbox: BBox, *, cz_crs: str) -> dict[str, CountryPart]:
    """Per-country parts of an area, as ``--country auto`` builds them (A6).

    Countries whose envelope intersects ``bbox``; each part is clipped to the
    country envelope. The CZ part is in ``cz_crs`` (EPSG:5514, EPSG:3045 or
    EPSG:2180 — via the pinned operation), the PL part in the CRS of ``bbox``.
    """
    return {
        code: country_bbox(bbox, code, auto=True, cz_crs=cz_crs)
        for code in countries_for_bbox(bbox)
    }
