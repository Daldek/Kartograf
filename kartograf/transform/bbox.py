"""Obwiednia bboxa EPSG:2180 w innym ukladzie (CORINE, SoilGrids; D19)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kartograf.core.sheet_parser import BBox


def envelope_from_2180(
    bbox: BBox, target_crs: str
) -> tuple[float, float, float, float]:
    """Obwiednia prostokata EPSG:2180 w ``target_crs`` (osie x/y = lon/lat).

    Obwiednia calego prostokata (krawedzie zageszczone, ``densify_pts=21``),
    nie tylko dwoch naroznikow: siatka EPSG:2180 jest obrocona wzgledem
    poludnikow, wiec para SW/NE ucina pasy polnocny i poludniowy.

    Returns
    -------
    tuple
        (min_x, min_y, max_x, max_y) w ``target_crs``; dla EPSG:4326
        (min_lon, min_lat, max_lon, max_lat).
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:2180", target_crs, always_xy=True)
    return transformer.transform_bounds(
        bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, densify_pts=21
    )
