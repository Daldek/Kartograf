"""Providery polskich zrodel danych (GUGiK)."""

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
]
