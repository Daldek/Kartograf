"""
Hydrology module for Kartograf.

This module provides hydrological analysis tools including:
- Hydrologic Soil Group (HSG) of an area in the version store
  (``calculate_hsg``/``check_hsg``, ``soil hsg``) and its statistics
  (``hsg_statistics``)
- USDA soil texture triangle classification
"""

from kartograf.hydrology.hsg import (
    HSG_DESCRIPTIONS,
    TEXTURE_CLASSES,
    HsgReport,
    calculate_hsg,
    check_hsg,
    classify_usda_texture,
    hsg_statistics,
    texture_to_hsg,
)

__all__ = [
    "calculate_hsg",
    "check_hsg",
    "HsgReport",
    "hsg_statistics",
    "classify_usda_texture",
    "texture_to_hsg",
    "HSG_DESCRIPTIONS",
    "TEXTURE_CLASSES",
]
