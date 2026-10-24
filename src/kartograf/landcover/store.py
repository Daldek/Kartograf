"""
Land cover and HSG in the ``data/`` layout (versioned store spec 3.4).

A segment carries the content parameters (layers, format, year, soil
property, depth, statistic) as lowercase tokens after the descriptor's
``storage_subdir`` prefix (``download.storage.content_segment``); below it
the selection: ``teryt/<TERYT>``, ``bbox/<coords>`` (as cutouts) or the
sheet hierarchy (as NMT) - ``download.storage.unit_slot``. HSG is a derived
product without a descriptor: its prefix lives here.
"""

from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.storage import bbox_cutout_path, token_segment
from kartograf.exceptions import ValidationError

# Derived product: no descriptor of its own (D33).
HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"


def hsg_segment(depth: str, stat: str) -> str:
    """``hsg/global_soilgrids_<depth>_<stat>`` (lowercase)."""
    return token_segment(HSG_SEGMENT_PREFIX, (depth, stat))


def selection_unit(
    *, teryt: str | None = None, bbox: BBox | None = None, sheet: str | None = None
) -> str:
    """Plan unit of a selection: TERYT, bbox coordinates or the canonical sheet."""
    if sum(x is not None for x in (teryt, bbox, sheet)) != 1:
        raise ValidationError("Podaj dokladnie jeden wybor: teryt, bbox albo sheet")
    if teryt is not None:
        return teryt
    if bbox is not None:
        return bbox_cutout_path(".", "", bbox, "").name
    assert sheet is not None
    return SheetParser(sheet).sheet
