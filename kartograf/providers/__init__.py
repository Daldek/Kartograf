"""
Providers module for Kartograf.

This module contains provider implementations for downloading data
from various sources. Currently supported providers:

- GugikProvider: Downloads NMT data from GUGiK (Polish geodesy service)
- LandCoverProvider: Abstract base for land cover data providers
- Bdot10kProvider: Downloads land cover data from BDOT10k (GUGiK)
- CorineProvider: Downloads CORINE Land Cover data (Copernicus/GIOŚ)
- SoilGridsProvider: Downloads soil property data from ISRIC SoilGrids
"""

from kartograf.providers.base import BaseProvider
from kartograf.providers.bdot10k import Bdot10kProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.gugik import GugikProvider
from kartograf.providers.landcover_base import LandCoverProvider
from kartograf.providers.soilgrids import SoilGridsProvider

__all__ = [
    "BaseProvider",
    "GugikProvider",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
]
