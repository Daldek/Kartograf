"""Envelope of an EPSG:2180 bbox in another CRS (CORINE, SoilGrids; D19)."""

from kartograf.core.bbox import BBox


def envelope_from_2180(
    bbox: BBox, target_crs: str
) -> tuple[float, float, float, float]:
    """Envelope of an EPSG:2180 rectangle in ``target_crs`` (x/y axes = lon/lat).

    Envelope of the whole rectangle (edges densified, ``densify_pts=21``),
    not just two corners: the EPSG:2180 grid is rotated relative to the
    meridians, so an SW/NE pair cuts off the northern and southern strips.

    Returns
    -------
    tuple
        (min_x, min_y, max_x, max_y) in ``target_crs``; for EPSG:4326
        (min_lon, min_lat, max_lon, max_lat).
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:2180", target_crs, always_xy=True)
    return transformer.transform_bounds(
        bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, densify_pts=21
    )
