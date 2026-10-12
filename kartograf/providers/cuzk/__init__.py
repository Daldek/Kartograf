"""Providers of Czech data sources (CUZK)."""

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk.client import CuzkClient
from kartograf.providers.cuzk.dmr import CuzkDmrProvider
from kartograf.providers.cuzk.sheets import SheetIndex, SheetInfo

__all__ = [
    "CuzkClient",
    "CuzkDmrProvider",
    "SheetIndex",
    "SheetInfo",
    "create_dmr_provider",
]


def create_dmr_provider(
    resolution: str,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    target_crs: str | None = None,
    *,
    vertical_crs: str,
) -> CuzkDmrProvider:
    """Build CZ DMR: 2m DMR 5G or 5m DMR 4G (SM5 sheets).

    ``vertical_crs`` is "Bpv" (native Baltic heights) or "EVRF2007"
    (reprojected European heights). ``target_crs=None`` keeps native
    EPSG:5514; ``session=None`` creates a session and ``cache=None``
    disables metadata caching.
    """
    if resolution not in {"2m", "5m"}:
        raise ValidationError(
            f"Nieobslugiwana rozdzielczosc CZ: '{resolution}' (dostepne: 2m, 5m)"
        )
    return CuzkDmrProvider(
        resolution=resolution,
        session=session,
        cache=cache,
        target_crs=target_crs,
        vertical_crs=vertical_crs,
    )
