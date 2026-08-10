"""
Providers module for Kartograf.

This module contains provider implementations for downloading data
from various sources. Currently supported providers:

- GugikProvider: Downloads NMT data from GUGiK (Polish geodesy service)
- GugikLazProvider: Downloads LAZ point-cloud data from GUGiK (via WFS)
- LandCoverProvider: Abstract base for land cover data providers
- Bdot10kProvider: Downloads land cover data from BDOT10k (GUGiK)
- CorineProvider: Downloads CORINE Land Cover data (Copernicus/GIOŚ)
- SoilGridsProvider: Downloads soil property data from ISRIC SoilGrids

Polish providers (Gugik*, Bdot10kProvider) live in ``kartograf.providers.pl``;
re-exported here for backward-compatible top-level access.
"""

from kartograf.providers.base import BaseProvider, LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.soilgrids import SoilGridsProvider

__all__ = [
    "BaseProvider",
    "GugikProvider",
    "GugikLazProvider",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
]
