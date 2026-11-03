"""
Land Cover module for Kartograf.

Downloads BDOT10k, BDOO, CORINE, ZABAGED, Data50 and Data250
(``download_landcover``, ``landcover download``) and SoilGrids
(``download_soil``, ``soil download``) into the version store (``data/``
layout, spec 3.4).
"""

from kartograf.landcover.manager import (
    LandCoverReport,
    SoilReport,
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
)

__all__ = [
    "download_landcover",
    "check_landcover",
    "LandCoverReport",
    "download_soil",
    "check_soil",
    "SoilReport",
]
