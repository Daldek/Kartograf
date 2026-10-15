"""Route of a CZ raster provider fake (``CuzkRasterProvider.route``).

Tests replace ``CuzkRasterProvider`` with fakes that must not build pinned
operations (PROJ grids, network). ``route_of`` gives the route a real
provider would: the channel and the result CRS of the row of the variant
registry (plan B, decision 2), with the operations supplied by the fake.
"""

from collections.abc import Callable
from typing import Any

from kartograf.providers.cuzk.raster import NATIVE_CRS, CzRasterRoute
from kartograf.sources.descriptor import AccessChannel, TransportKind
from kartograf.sources.registry import (
    CZ_SYSTEM_CRS,
    channel_for,
    get_source,
    resolve_vertical_crs,
)
from kartograf.sources.variants import cz_sheet_system, find_cz_variant


def _vertical(channel: AccessChannel, vertical_crs: str, pinned: Any) -> Any:
    """``pinned`` when the requested heights are not native to ``channel``."""
    options = channel.vertical_crs_options
    return None if resolve_vertical_crs(vertical_crs, options) in options else pinned


def route_of(
    descriptor_key: str,
    vertical_crs: str,
    sheet: str | None = None,
    *,
    target_crs: str | None = None,
    horizontal: Callable[[str], Any] | None = None,
    vertical: Any = None,
) -> CzRasterRoute:
    """Route of a sheet (``None``: a cutout in ``target_crs``) of the raster
    descriptor ``descriptor_key``; ``horizontal(crs)`` gives the horizontal
    operation of a warp, ``vertical`` the Bpv->EVRF2007 operation."""
    source = get_source(descriptor_key)
    image = channel_for(descriptor_key, TransportKind.ARCGIS_IMAGE)

    def warp(crs: str) -> Any:
        return horizontal(crs) if horizontal is not None else None

    if sheet is None:
        target = target_crs or NATIVE_CRS
        return CzRasterRoute(
            image, target, warp(target), _vertical(image, vertical_crs, vertical)
        )
    system = cz_sheet_system(sheet)
    variant = find_cz_variant(
        product=source.product,
        resolution=source.resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    if variant.channel == TransportKind.DIRECT_FILES:
        files = channel_for(
            descriptor_key, TransportKind.DIRECT_FILES, CZ_SYSTEM_CRS[system]
        )
        return CzRasterRoute(
            files, files.horizontal_crs, None, _vertical(files, vertical_crs, vertical)
        )
    tile = CZ_SYSTEM_CRS["tm33"]
    return CzRasterRoute(
        image, tile, warp(tile), _vertical(image, vertical_crs, vertical)
    )


def cz_factory(provider: Any) -> Callable[..., Any]:
    """``side_effect`` of a patched ``create_cz_raster_provider``: returns
    ``provider`` with ``target_crs`` = the cutout CRS of the call (``None``:
    native), as a real provider of that call would route its cutout."""

    def create(**kwargs: Any) -> Any:
        provider.target_crs = kwargs.get("horizontal_crs")
        return provider

    return create
