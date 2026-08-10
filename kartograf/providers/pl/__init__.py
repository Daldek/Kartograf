"""Providery polskich zrodel danych (GUGiK)."""

import logging

import requests

from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

logger = logging.getLogger(__name__)

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
    vertical_crs: str = "EVRF2007",
    resolution: str = "1m",
    session: requests.Session | None = None,
    cache=None,
) -> GugikProvider:
    """Fabryka domyslnego providera NMT — jedno miejsce polskich domyslow.

    Egzekwuje regule "5m => EVRF2007" (identycznie jak DownloadManager).
    """
    if resolution == "5m" and vertical_crs != "EVRF2007":
        logger.warning(
            f"Resolution 5m only supports EVRF2007, changing "
            f"vertical_crs from '{vertical_crs}' to 'EVRF2007'"
        )
        vertical_crs = "EVRF2007"
    return GugikProvider(
        session=session,
        vertical_crs=vertical_crs,
        resolution=resolution,
        cache=cache,
    )
