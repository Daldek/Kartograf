"""Providery czeskich zrodel danych (CUZK)."""

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk.client import CuzkClient
from kartograf.providers.cuzk.dmr import CuzkDmrProvider
from kartograf.providers.cuzk.sheets import SheetIndex, SheetInfo, Sm5Sheet

__all__ = [
    "CuzkClient",
    "CuzkDmrProvider",
    "SheetIndex",
    "SheetInfo",
    "Sm5Sheet",
    "create_dmr_provider",
]


def create_dmr_provider(
    resolution: str = "2m",
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    target_crs: str | None = None,
    vertical_crs: str = "Bpv",
) -> CuzkDmrProvider:
    """Fabryka providera DMR — jedno miejsce czeskich domyslow (wzor: pl)."""
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
