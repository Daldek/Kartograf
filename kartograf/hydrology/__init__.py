"""
Hydrology module for Kartograf.

This module provides hydrological analysis tools including:
- Hydrologic Soil Group (HSG) classification from soil texture
- USDA soil texture triangle classification
"""

from kartograf.hydrology.hsg import (
    HSG_DESCRIPTIONS,
    TEXTURE_CLASSES,
    HSGCalculator,
    classify_usda_texture,
    texture_to_hsg,
)

__all__ = [
    "HSGCalculator",
    "classify_usda_texture",
    "texture_to_hsg",
    "HSG_DESCRIPTIONS",
    "TEXTURE_CLASSES",
]
