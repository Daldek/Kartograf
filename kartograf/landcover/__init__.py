"""
Land Cover module for Kartograf.

Downloads BDOT10k, CORINE Land Cover and SoilGrids into the version store
(``data/`` layout, spec 3.4).
"""

from kartograf.landcover.manager import (
    LandCoverAreaResult,
    LandCoverFailure,
    LandCoverManager,
    LandCoverResult,
)

__all__ = [
    "LandCoverManager",
    "LandCoverResult",
    "LandCoverAreaResult",
    "LandCoverFailure",
]
