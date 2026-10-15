"""Providers of Polish data sources (GUGiK)."""

import requests

from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

__all__ = [
    "Bdot10kProvider",
    "GugikProvider",
    "GugikLazProvider",
    "GugikNmptProvider",
    "GugikOrtoProvider",
    "LazTile",
    "create_nmt_provider",
]


def create_nmt_provider(
    vertical_crs: str,
    resolution: str | None,
    session: requests.Session | None = None,
    cache=None,
    format: str = "ASC",
) -> GugikProvider:
    """Build an NMT provider for an explicitly selected PL variant.

    ``vertical_crs``: "EVRF2007" (current heights) or "KRON86" (legacy);
    ``resolution``: a label of the variant registry (``0.5m``, ``1m``, ...);
    ``format``: "ASC" (grid) or an archive token. A combination outside the
    registry (``kartograf.sources.variants.variants()``) raises
    ``ValidationError`` naming the available values. ``session=None`` uses a
    managed HTTP session; ``cache=None`` disables metadata caching.
    """
    return GugikProvider(
        session=session,
        vertical_crs=vertical_crs,
        resolution=resolution,
        format=format,
        cache=cache,
    )
