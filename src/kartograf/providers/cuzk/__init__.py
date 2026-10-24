"""Providers of Czech data sources (CUZK)."""

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.providers.cuzk.client import CuzkClient
from kartograf.providers.cuzk.laz import CuzkLazProvider
from kartograf.providers.cuzk.raster import CuzkRasterProvider, CzRasterRoute
from kartograf.providers.cuzk.sheets import SheetIndex, SheetInfo

__all__ = [
    "CuzkClient",
    "CuzkLazProvider",
    "CuzkRasterProvider",
    "CzRasterRoute",
    "SheetIndex",
    "SheetInfo",
    "create_cz_raster_provider",
]


def create_cz_raster_provider(
    product: str,
    resolution: str,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    horizontal_crs: str | None = None,
    *,
    vertical_crs: str,
) -> CuzkRasterProvider:
    """Build the CZ raster of a product and resolution (variant registry).

    ``nmt`` ``2m`` DMR 5G / ``5m`` DMR 4G, ``nmpt`` ``0.5m`` DMP OK / ``2m`` DMP 1G.

    ``vertical_crs`` is "Bpv" (native Baltic heights) or "EVRF2007" (native
    for the ETRS89 files, otherwise the pinned operation). ``horizontal_crs``
    is the CRS of a cutout (``None`` keeps native EPSG:5514); ``session=None``
    creates a session and ``cache=None`` disables metadata caching.
    """
    return CuzkRasterProvider(
        product,
        resolution,
        session=session,
        cache=cache,
        horizontal_crs=horizontal_crs,
        vertical_crs=vertical_crs,
    )
