"""Providers of Polish data sources (GUGiK)."""

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
    "nmt_vertical_crs",
]

# GUGiK NMT 5 m exists only in EVRF2007 (index SheetsGrid5mEVRF2007).
NMT_5M_VERTICAL_CRS = "EVRF2007"


def nmt_vertical_crs(resolution: str, vertical_crs: str, *, log: bool = True) -> str:
    """ACTUAL vertical CRS of PL NMT — the one place of the "5m => EVRF2007" rule (D11).

    The rule has a single effect: correction to EVRF2007. The provider
    factory and ``DownloadManager`` log it as a warning (``log=True``), the
    CLI prints ``Info:`` to stderr (``log=False`` + its own message), and
    steps that already take the ACTUAL vertical CRS (``prepare_pl_cutout``)
    reject a mismatch with ``ValidationError`` (``log=False``).
    """
    actual = NMT_5M_VERTICAL_CRS if resolution == "5m" else vertical_crs
    if log and actual != vertical_crs:
        logger.warning(
            f"Resolution 5m only supports EVRF2007, changing "
            f"vertical_crs from '{vertical_crs}' to '{actual}'"
        )
    return actual


def create_nmt_provider(
    vertical_crs: str = "EVRF2007",
    resolution: str = "1m",
    session: requests.Session | None = None,
    cache=None,
) -> GugikProvider:
    """Factory of the default NMT provider — the one place for Polish defaults.

    Rule "5m => EVRF2007": ``nmt_vertical_crs`` (correction with a warning).
    """
    return GugikProvider(
        session=session,
        vertical_crs=nmt_vertical_crs(resolution, vertical_crs),
        resolution=resolution,
        cache=cache,
    )
