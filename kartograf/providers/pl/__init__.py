"""Providers of Polish data sources (GUGiK)."""

import logging

import requests

from kartograf.exceptions import ValidationError
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
    "require_nmt_vertical_crs",
]

# GUGiK NMT 5 m exists only in EVRF2007 (index SheetsGrid5mEVRF2007).
NMT_5M_VERTICAL_CRS = "EVRF2007"


def nmt_vertical_crs(resolution: str, vertical_crs: str, *, log: bool = True) -> str:
    """ACTUAL vertical CRS of PL NMT — the one place of the "5m => EVRF2007" rule (D11).

    Returns the corrected vertical CRS (logged as a warning with
    ``log=True``). Library entry points and the CLI reject the mismatch
    through ``require_nmt_vertical_crs`` (0.7.1: no swap anywhere in
    Kartograf); this function stays the pure rule behind it.
    """
    actual = NMT_5M_VERTICAL_CRS if resolution == "5m" else vertical_crs
    if log and actual != vertical_crs:
        logger.warning(
            f"Resolution 5m only supports EVRF2007, changing "
            f"vertical_crs from '{vertical_crs}' to '{actual}'"
        )
    return actual


def require_nmt_vertical_crs(resolution: str, vertical_crs: str) -> str:
    """Return ``vertical_crs`` when GUGiK has PL NMT ``resolution`` in it.

    Library counterpart of ``nmt_vertical_crs`` (0.7.1: no silent swap). Never
    logs.

    Raises
    ------
    ValidationError
        ``resolution="5m"`` with a vertical CRS other than EVRF2007 (5 m
        exists only in EVRF2007) - the message names the remedy.
    """
    actual = nmt_vertical_crs(resolution, vertical_crs, log=False)
    if actual != vertical_crs:
        raise ValidationError(
            f"NMT {resolution} (PL) jest dostepny tylko w {actual} — podano "
            f"vertical_crs={vertical_crs!r}; uzyj vertical_crs={actual!r} "
            f"albo resolution='1m'"
        )
    return vertical_crs


def create_nmt_provider(
    vertical_crs: str = "EVRF2007",
    resolution: str = "1m",
    session: requests.Session | None = None,
    cache=None,
) -> GugikProvider:
    """Factory of the default NMT provider — the one place for Polish defaults.

    Rule "5m => EVRF2007": ``require_nmt_vertical_crs`` - 5 m with KRON86
    raises ``ValidationError`` (0.7.1; earlier a silent swap with a warning).
    """
    return GugikProvider(
        session=session,
        vertical_crs=require_nmt_vertical_crs(resolution, vertical_crs),
        resolution=resolution,
        cache=cache,
    )
