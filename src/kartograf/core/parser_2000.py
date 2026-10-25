"""
Parser of topographic map sheet codes for the PL-2000 system.

This module provides the Parser2000 class for parsing Polish topographic
map sheet codes in PL-2000 coordinate system.
PL-2000 uses dot-separated numeric format: zone.row.column[.subdivisions]
(e.g., 6.179.12, 6.179.12.20).
"""

import json
import math
import re
from typing import Any

import numpy as np
import shapely

from kartograf.core import pl2000_zones
from kartograf.core.bbox import BBox, _transformer, transform_bbox, validate_bbox
from kartograf.core.sheet_parser import (
    _DEGENERATE_EPS_DEG,
    _EDGE_TOL,
    SheetOutline,
    _axis_overlaps,
    _expand_degenerate,
)
from kartograf.exceptions import ParseError, ValidationError
from kartograf.messages import message

# PL-2000 scale hierarchy (from coarsest to finest)
SCALE_HIERARCHY_2000 = ["1:10000", "1:5000", "1:2000", "1:1000", "1:500"]

# Sheet dimensions in metres (height N-S, width E-W)
SHEET_DIMENSIONS_2000 = {
    "1:10000": (5000, 8000),
    "1:5000": (2500, 4000),
    "1:2000": (1000, 1600),
    "1:1000": (500, 800),
    "1:500": (250, 400),
}

# Zone to EPSG mapping
ZONE_EPSG = {
    5: "EPSG:2176",
    6: "EPSG:2177",
    7: "EPSG:2178",
    8: "EPSG:2179",
}

# CRSs supported by get_bbox
_SUPPORTED_CRS = {
    "EPSG:2176",
    "EPSG:2177",
    "EPSG:2178",
    "EPSG:2179",
    "EPSG:2180",
    "EPSG:4326",
}


class Parser2000:
    """
    Parser of topographic map sheet codes for the PL-2000 system.

    Supported scales: 1:10000 to 1:500

    Attributes
    ----------
    sheet : str
        Normalized sheet code (e.g. "6.179.12")
    scale : str
        Map scale (e.g. "1:10000")
    system : str
        Coordinate system (always "2000")
    components : dict[str, str]
        Sheet code components (strefa, pas, slup, and optionally
        ark_5k/ark_2k/ark_1k/ark_500)
    zone : int
        Zone number (5-8)
    native_crs : str
        Native CRS of the zone (e.g. "EPSG:2177")

    Examples
    --------
    >>> parser = Parser2000("6.179.12")
    >>> parser.scale
    '1:10000'
    >>> parser.zone
    6
    >>> parser.native_crs
    'EPSG:2177'
    """

    # Sheet code patterns for each scale ([0-9]: ASCII digits only, not \d)
    PATTERNS_2000 = {
        "1:10000": r"^([5-8])\.([0-9]{1,3})\.([0-9]{1,2})$",
        "1:5000": r"^([5-8])\.([0-9]{1,3})\.([0-9]{1,2})\.([1-4])$",
        "1:2000": r"^([5-8])\.([0-9]{1,3})\.([0-9]{1,2})\.([0-9]{2})$",
        "1:1000": r"^([5-8])\.([0-9]{1,3})\.([0-9]{1,2})\.([0-9]{2})\.([1-4])$",
        "1:500": r"^([5-8])\.([0-9]{1,3})\.([0-9]{1,2})\.([0-9]{2})\.([1-4])\.([1-4])$",
    }

    # Component names per scale (order = regex groups)
    _COMPONENT_NAMES = {
        "1:10000": ("strefa", "pas", "slup"),
        "1:5000": ("strefa", "pas", "slup", "ark_5k"),
        "1:2000": ("strefa", "pas", "slup", "ark_2k"),
        "1:1000": ("strefa", "pas", "slup", "ark_2k", "ark_1k"),
        "1:500": ("strefa", "pas", "slup", "ark_2k", "ark_1k", "ark_500"),
    }

    # Positions of 2x2 quadrants: {quadrant: (row, col)}
    _QUADRANT_POSITIONS = {
        1: (0, 0),  # NW
        2: (0, 1),  # NE
        3: (1, 0),  # SW
        4: (1, 1),  # SE
    }

    def __init__(self, sheet: str):
        """
        Initialize the parser for the given PL-2000 sheet code.

        Parameters
        ----------
        sheet : str
            Map sheet code (e.g. "6.179.12", "6.179.12.15")

        Raises
        ------
        ParseError
            If the sheet code is invalid or matches no pattern.
        ValidationError
            If ark_2k is outside the range 01-25.
        """
        if not isinstance(sheet, str):
            raise ParseError(
                message("core.sheet_code_must_be_string", sheet_type=type(sheet))
            )

        sheet = sheet.strip()
        if not sheet:
            raise ParseError(message("core.sheet_code_must_not_be_empty"))

        # Reject the PL-1992 format (dashes)
        if "-" in sheet:
            raise ParseError(message("core.pl2000_code_is_pl1992", sheet=sheet))

        self._sheet = sheet
        self._scale = self._determine_scale()
        self._components = self._parse_components()
        self._validate_components()

    def _determine_scale(self) -> str:
        """
        Determine the scale from the structure of the sheet code.

        Returns
        -------
        str
            Map scale (e.g. "1:10000")

        Raises
        ------
        ParseError
            If the sheet code matches no pattern
        """
        for scale, pattern in self.PATTERNS_2000.items():
            if re.match(pattern, self._sheet):
                return scale

        raise ParseError(message("core.pl2000_code_format", sheet=self._sheet))

    def _parse_components(self) -> dict[str, str]:
        """
        Parse the sheet code components.

        Returns
        -------
        dict[str, str]
            Dictionary of sheet code components
        """
        pattern = self.PATTERNS_2000[self._scale]
        match = re.match(pattern, self._sheet)

        if not match:
            raise ParseError(
                message("core.sheet_code_parsing_error", sheet=self._sheet)
            )

        names = self._COMPONENT_NAMES[self._scale]
        return dict(zip(names, match.groups(), strict=True))

    def _validate_components(self) -> None:
        """
        Validate the sheet code components.

        Raises
        ------
        ValidationError
            If ark_2k is outside the range 01-25
        """
        if "ark_2k" in self._components:
            ark_2k = int(self._components["ark_2k"])
            if ark_2k < 1 or ark_2k > 25:
                ark_val = self._components["ark_2k"]
                raise ValidationError(
                    message("core.invalid_1_2000_sheet_number", ark_val=ark_val)
                )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def sheet(self) -> str:
        """Return the sheet code."""
        return self._sheet

    @property
    def scale(self) -> str:
        """Return the map scale."""
        return self._scale

    @property
    def system(self) -> str:
        """Return the coordinate system (always '2000')."""
        return "2000"

    @property
    def components(self) -> dict[str, str]:
        """Return a dictionary of sheet code components (a copy)."""
        return self._components.copy()

    @property
    def zone(self) -> int:
        """Return the zone number (5-8)."""
        return int(self._components["strefa"])

    @property
    def native_crs(self) -> str:
        """Return the native CRS of the zone (e.g. 'EPSG:2177')."""
        return ZONE_EPSG[self.zone]

    # =========================================================================
    # Equality and hashing
    # =========================================================================

    def __eq__(self, other: object) -> bool:
        """Compare two parsers by sheet code."""
        if not isinstance(other, Parser2000):
            return NotImplemented
        return self._sheet == other._sheet

    def __hash__(self) -> int:
        """Return the object hash."""
        return hash(self._sheet)

    def __repr__(self) -> str:
        """Return a debugging representation of the object."""
        return (
            f"Parser2000(sheet='{self._sheet}', scale='{self._scale}', system='2000')"
        )

    def __str__(self) -> str:
        """Return a readable representation of the sheet."""
        return message("core.scale_system_2000", sheet=self._sheet, scale=self._scale)

    # =========================================================================
    # BBox
    # =========================================================================

    def get_bbox(self, crs: str | None = None) -> BBox:
        """
        Compute the bounding box of the sheet in the given coordinate system.

        Parameters
        ----------
        crs : str, optional
            Target coordinate system (default: native CRS of the zone).
            Supported: EPSG:2176-2179, EPSG:2180, EPSG:4326.

        Returns
        -------
        BBox
            NamedTuple with fields: min_x, min_y, max_x, max_y, crs

        Raises
        ------
        ValidationError
            If the CRS is not supported.

        Examples
        --------
        >>> parser = Parser2000("6.179.12")
        >>> bbox = parser.get_bbox()
        >>> bbox.crs
        'EPSG:2177'
        """
        if crs is None:
            crs = self.native_crs

        if crs not in _SUPPORTED_CRS:
            raise ValidationError(
                message(
                    "core.unsupported_coordinate_system",
                    crs=crs,
                    supported_crs=", ".join(sorted(_SUPPORTED_CRS)),
                )
            )

        # Compute the bbox in the native CRS of the zone
        south, north, west, east = self._calculate_native_bbox()
        native_crs = self.native_crs

        if crs == native_crs:
            return BBox(min_x=west, min_y=south, max_x=east, max_y=north, crs=crs)

        # Transform to the target CRS (densified envelope, core.bbox)
        return transform_bbox(
            BBox(min_x=west, min_y=south, max_x=east, max_y=north, crs=native_crs),
            crs,
        )

    def _calculate_native_bbox(self) -> tuple[float, float, float, float]:
        """
        Compute the bounding box in the native CRS of the PL-2000 zone.

        Returns
        -------
        tuple[float, float, float, float]
            (south, north, west, east) in metres
        """
        strefa = int(self._components["strefa"])
        pas = int(self._components["pas"])
        slup = int(self._components["slup"])

        # Base 1:10000 coordinates
        south = pas * 5000 + 4_920_000
        north = south + 5000
        west = strefa * 1_000_000 + slup * 8000 + 332_000
        east = west + 8000

        if self._scale == "1:10000":
            return (south, north, west, east)

        # 1:5000 subdivision (2x2 in 10k)
        if self._scale == "1:5000":
            q = int(self._components["ark_5k"])
            return self._apply_quadrant(south, north, west, east, q, 2500, 4000)

        # 1:2000 subdivision (5x5 in 10k)
        ark_2k = int(self._components["ark_2k"])
        row, col = divmod(ark_2k - 1, 5)
        # Rows are counted from the top (row=0 is north)
        south_2k = north - (row + 1) * 1000
        north_2k = north - row * 1000
        west_2k = west + col * 1600
        east_2k = west_2k + 1600

        if self._scale == "1:2000":
            return (south_2k, north_2k, west_2k, east_2k)

        # 1:1000 subdivision (2x2 in 2k)
        q_1k = int(self._components["ark_1k"])
        south_1k, north_1k, west_1k, east_1k = self._apply_quadrant(
            south_2k, north_2k, west_2k, east_2k, q_1k, 500, 800
        )

        if self._scale == "1:1000":
            return (south_1k, north_1k, west_1k, east_1k)

        # 1:500 subdivision (2x2 in 1k)
        q_500 = int(self._components["ark_500"])
        return self._apply_quadrant(
            south_1k, north_1k, west_1k, east_1k, q_500, 250, 400
        )

    def _apply_quadrant(
        self,
        south: float,
        north: float,
        west: float,
        east: float,
        quadrant: int,
        height: float,
        width: float,
    ) -> tuple[float, float, float, float]:
        """
        Compute the bbox of a quadrant in a 2x2 grid.

        Parameters
        ----------
        south, north, west, east : float
            Parent bbox
        quadrant : int
            Quadrant number (1-4)
        height : float
            Quadrant height in metres
        width : float
            Quadrant width in metres

        Returns
        -------
        tuple[float, float, float, float]
            (south, north, west, east)
        """
        row, col = self._QUADRANT_POSITIONS[quadrant]
        new_north = north - row * height
        new_south = new_north - height
        new_west = west + col * width
        new_east = new_west + width
        return (new_south, new_north, new_west, new_east)

    # =========================================================================
    # Hierarchy
    # =========================================================================

    def get_parent(self) -> "Parser2000 | None":
        """
        Return the parent of the sheet (coarser scale).

        Returns
        -------
        Parser2000 | None
            Parent, or None for 1:10000 (the coarsest scale).

        Examples
        --------
        >>> Parser2000("6.179.12.15.2").get_parent().sheet
        '6.179.12.15'
        """
        if self._scale == "1:10000":
            return None

        # 1:5000 -> 1:10000 (drop ark_5k - the last segment)
        # 1:2000 -> 1:10000 (drop ark_2k - the last segment)
        # 1:1000 -> 1:2000 (drop ark_1k - the last segment)
        # 1:500  -> 1:1000 (drop ark_500 - the last segment)
        parent_sheet = self._sheet.rsplit(".", 1)[0]
        return Parser2000(parent_sheet)

    def get_children(self, scale: str | None = None) -> list["Parser2000"]:
        """
        Return the children of the sheet (finer scale).

        Parameters
        ----------
        scale : str, optional
            Scale of the children. Relevant only for 1:10000, which has two paths:
            - "1:5000" -> 4 children (2x2 grid)
            - "1:2000" -> 25 children (5x5 grid) - the default

        Returns
        -------
        list[Parser2000]
            List of children sorted by sheet code.

        Examples
        --------
        >>> [c.sheet for c in Parser2000("6.179.12").get_children(scale="1:5000")]
        ['6.179.12.1', '6.179.12.2', '6.179.12.3', '6.179.12.4']
        """
        if self._scale == "1:10000":
            if scale is None:
                scale = "1:2000"
            if scale == "1:5000":
                # 2x2: quadrants 1-4
                return [Parser2000(f"{self._sheet}.{q}") for q in range(1, 5)]
            if scale == "1:2000":
                # 5x5: sheets 01-25
                return [Parser2000(f"{self._sheet}.{i:02d}") for i in range(1, 26)]
            return []

        if self._scale == "1:2000":
            # 2x2: quadrants 1-4
            return [Parser2000(f"{self._sheet}.{q}") for q in range(1, 5)]

        if self._scale == "1:1000":
            # 2x2: quadrants 1-4
            return [Parser2000(f"{self._sheet}.{q}") for q in range(1, 5)]

        # 1:5000 and 1:500 are leaves - no children
        return []

    def get_all_descendants(self, target_scale: str) -> list["Parser2000"]:
        """
        Return all descendants at the target scale.

        Parameters
        ----------
        target_scale : str
            Target scale (e.g. "1:1000").

        Returns
        -------
        list[Parser2000]
            List of descendants sorted by sheet code.

        Raises
        ------
        ValidationError
            If target_scale is coarser than the current scale or if there is
            no path to target_scale (e.g. 1:5000 -> 1:2000).

        Examples
        --------
        >>> len(Parser2000("6.179.12").get_all_descendants("1:1000"))
        100
        """
        if target_scale == self._scale:
            return [self]

        # Check whether target_scale is finer
        if target_scale not in SCALE_HIERARCHY_2000:
            raise ValidationError(
                message(
                    "core.unknown_scale_allowed",
                    target_scale=target_scale,
                    scale_hierarchy_2000=", ".join(SCALE_HIERARCHY_2000),
                )
            )

        # Find the indices in the hierarchy
        current_idx = SCALE_HIERARCHY_2000.index(self._scale)
        target_idx = SCALE_HIERARCHY_2000.index(target_scale)

        if target_idx < current_idx:
            raise ValidationError(
                message(
                    "core.target_scale_coarser_current_scale",
                    target_scale=target_scale,
                    scale=self._scale,
                )
            )

        # Special case: from 1:10000 to 1:5000 - the 5k branch
        if self._scale == "1:10000" and target_scale == "1:5000":
            return self.get_children(scale="1:5000")

        # Special case: nothing below 1:5000 (leaves)
        if self._scale == "1:5000" and target_scale != "1:5000":
            raise ValidationError(
                message(
                    "core.sheet_1_5000_has_no_descendants", target_scale=target_scale
                )
            )

        # Recursively: expand the children down to target_scale
        children = self.get_children()
        if not children:
            raise ValidationError(
                message(
                    "core.sheet_has_no_descendants_scale",
                    sheet=self._sheet,
                    scale=self._scale,
                    target_scale=target_scale,
                )
            )

        if children[0].scale == target_scale:
            return sorted(children, key=lambda p: p.sheet)

        # Recursion
        result = []
        for child in children:
            result.extend(child.get_all_descendants(target_scale))
        return sorted(result, key=lambda p: p.sheet)

    def get_hierarchy_up(self) -> list["Parser2000"]:
        """
        Return the chain from the current sheet up to 1:10000.

        Returns
        -------
        list[Parser2000]
            List from self (first) to 1:10000 (last).

        Examples
        --------
        >>> [p.scale for p in Parser2000("6.179.12.15.2").get_hierarchy_up()]
        ['1:1000', '1:2000', '1:10000']
        """
        chain = [self]
        current = self
        while True:
            parent = current.get_parent()
            if parent is None:
                break
            chain.append(parent)
            current = parent
        return chain


# =========================================================================
# Standalone functions: bbox -> sheet code lookup (PL-2000)
# =========================================================================

# metres: a sheet edge drawn in WGS84 is split into equal parts of at most this
# length. A straight edge of a zone grid is a curve in longitude and latitude
# (1.6 m off the chord of an 8 km edge); 1 km keeps it within 3 cm. Neighbour
# sheets share their split points, so the drawn sheets of a zone leave no gap.
_EDGE_STEP_M = 1000.0
# A sheet counts when its part inside its zone and the bbox is larger than this
# share of its part inside the bbox: a positive area without the numerical
# slivers of a zone boundary.
_MIN_SHARE = 1e-9
# degrees (~1 km) around the sheets when the zone area is cut out
_ZONE_MARGIN_DEG = 0.01

# What a map draws of a sheet: its GeoJSON outline (EPSG:4326) and the WGS84
# envelope of the whole sheet.
type _Drawn = tuple[dict[str, Any], BBox]


# metres (~1 mm) - PL-2000 zones are metric, not degrees
_DEGENERATE_EPS_M = 1e-3


def _bboxes_intersect_2000(a: BBox, b: BBox) -> bool:
    """
    Positive-area intersection (same convention as PL-1992).

    Touching at an edge or corner does NOT count as an intersection
    (audit 0.7.0, A1-7). The helpers (`_axis_overlaps`, `_expand_degenerate`)
    are shared with `sheet_parser.py`; only the threshold for expanding a
    degenerate bbox in metres (`_DEGENERATE_EPS_M`) is separate - P-12.

    Parameters
    ----------
    a, b : BBox
        Bounding boxes to check (should be in the same CRS).
        `a` is the query bbox - its degenerate axis (a point) is resolved
        by containment in the half-open interval of `b`.

    Returns
    -------
    bool
        True if the intersection area is positive
    """
    return _axis_overlaps(a.min_x, a.max_x, b.min_x, b.max_x) and _axis_overlaps(
        a.min_y, a.max_y, b.min_y, b.max_y
    )


def find_sheets_2000_for_bbox(
    bbox: BBox,
    target_scale: str,
    zone: int | None = None,
) -> list[str]:
    """
    Find the PL-2000 sheet codes covering the given bounding box.

    A sheet belongs to the grid of its zone, and a zone is an area, not a
    longitude range (ADR-055): its nominal 3-degree strip with the powiat
    exceptions of § 22 of the regulation on the national spatial reference
    system (Dz.U. 2012 poz. 1247: a powiat that the meridian 16.5, 19.5 or
    22.5 E cuts belongs to the zone of its larger part;
    ``kartograf.core.pl2000_zones``). A sheet of zone N is returned when its
    part inside the area of zone N meets the bbox with a positive area, so a
    bbox across a zone boundary yields the sheets of each zone on its own
    side of the boundary, never the sheets of one zone over another zone.

    Parameters
    ----------
    bbox : BBox
        Bounding box in any supported CRS
        (EPSG:2176-2179, EPSG:2180, EPSG:4326)
    target_scale : str
        "1:10000" selects coarse PL-2000 sheets; "1:5000",
        "1:2000", "1:1000" or "1:500" selects successively finer sheets.
    zone : int | None
        If given, restricts the search to this zone (5-8).
        If None, every zone whose area meets the bbox.

    Returns
    -------
    list[str]
        Sorted list of PL-2000 sheet codes covering the bbox.
        Edge convention as in PL-1992: only a positive intersection area
        counts (touching at an edge is not enough), and a degenerate bbox
        (a point) yields exactly one sheet - the one east/north of the grid
        line, in the zone east/north of a zone boundary.

    Raises
    ------
    ValidationError
        If target_scale is invalid, the CRS is unsupported, or the bbox is
        inverted (min > max) or has a NaN/inf value
    """
    return [sheet for sheet, _zone, _outline in _find_2000(bbox, target_scale, zone)]


def find_sheet_outlines_2000(
    bbox: BBox,
    target_scale: str,
    zone: int | None = None,
) -> list[SheetOutline]:
    """
    Find the PL-2000 sheets of a bbox with their zone and WGS84 outline.

    The sheets and their order are those of ``find_sheets_2000_for_bbox``.
    The outline of a sheet is its rectangle in EPSG:4326, edges split into
    parts of at most 1 km; a sheet that a zone boundary cuts is drawn as its
    part inside its zone, so the outlines of two zones never overlap and
    together cover the bbox. A download still takes the whole sheet
    (``Parser2000(sheet).get_bbox()``).

    Parameters
    ----------
    bbox : BBox
        Bounding box in any supported CRS
        (EPSG:2176-2179, EPSG:2180, EPSG:4326)
    target_scale : str
        "1:10000", "1:5000", "1:2000", "1:1000" or "1:500".
    zone : int | None
        If given, restricts the search to this zone (5-8).

    Returns
    -------
    list[SheetOutline]
        Sorted by sheet code; ``zone`` is the first part of the code.

    Raises
    ------
    ValidationError
        As ``find_sheets_2000_for_bbox``.
    """
    return [
        SheetOutline(sheet=sheet, zone=found_zone, outline=drawn[0], bbox=drawn[1])
        for sheet, found_zone, drawn in _find_2000(
            bbox, target_scale, zone, outline=True
        )
        if drawn is not None
    ]


def _find_2000(
    bbox: BBox,
    target_scale: str,
    zone: int | None,
    *,
    outline: bool = False,
) -> list[tuple[str, int, _Drawn | None]]:
    """Sheets of the zones that meet a bbox: ``(sheet, zone, drawn)``."""
    if target_scale not in SCALE_HIERARCHY_2000:
        raise ValidationError(
            message(
                "core.invalid_scale_allowed",
                target_scale=target_scale,
                scale_hierarchy_2000=", ".join(SCALE_HIERARCHY_2000),
            )
        )

    validate_bbox(bbox)
    bbox_wgs84 = transform_bbox(bbox, "EPSG:4326")

    # The zones whose area meets the bbox. A point or a hairline is widened
    # on its max side for this only (review 0.7.0, round 1); the exact bbox
    # goes on to the zone CRS, so that the metric eps decides the sheet.
    detect = _expand_degenerate(bbox_wgs84, _DEGENERATE_EPS_DEG)
    window = (detect.min_x, detect.min_y, detect.max_x, detect.max_y)
    zones = [zone] if zone is not None else pl2000_zones.zones_in(window)

    found: dict[int, tuple[list[tuple[str, _Drawn | None]], float]] = {}
    for z in zones:
        zone_crs = ZONE_EPSG[z]
        if bbox.crs == zone_crs:
            zone_bbox = bbox
        else:
            # Densified envelope: a parallel has its minimum y on the central
            # meridian of the zone (15/18/21/24E) - 4 corners raised the lower
            # edge and lost a whole row of sheets (parser assessment
            # 2026-10-07, K3)
            zone_bbox = transform_bbox(bbox_wgs84, zone_crs)
        # Point/hairline: expand by eps on the MAX side (exactly one sheet)
        zone_bbox = _expand_degenerate(zone_bbox, _DEGENERATE_EPS_M)
        candidates = _grid_candidates(z, zone_bbox, target_scale)
        if candidates:
            kept, share = _in_zone(z, zone_bbox, candidates, outline)
            if kept:
                found[z] = (kept, share)

    point = (
        bbox_wgs84.max_x - bbox_wgs84.min_x <= 2 * _EDGE_TOL
        and bbox_wgs84.max_y - bbox_wgs84.min_y <= 2 * _EDGE_TOL
    )
    if point and len(found) > 1:
        # A point on a zone boundary: the zone with the larger share of the
        # eps square east/north of it (east on a meridian outside Poland).
        best = max(found, key=lambda z: (found[z][1], z))
        found = {best: found[best]}

    result = [
        (sheet, z, drawn)
        for z, (kept, _share) in found.items()
        for sheet, drawn in kept
    ]
    return sorted(result, key=lambda item: item[0])


def _grid_candidates(zone: int, zone_bbox: BBox, target_scale: str) -> list[Parser2000]:
    """Sheets of a zone grid whose rectangle meets the bbox (in the zone CRS)."""
    # Compute the row/col range for 1:10k
    min_row = math.floor((zone_bbox.min_y - 4_920_000) / 5000) - 1
    max_row = math.floor((zone_bbox.max_y - 4_920_000) / 5000) + 1
    min_col = math.floor((zone_bbox.min_x - zone * 1_000_000 - 332_000) / 8000) - 1
    max_col = math.floor((zone_bbox.max_x - zone * 1_000_000 - 332_000) / 8000) + 1

    # Clamp to sane values (pas >= 0, slup >= 0)
    min_row = max(0, min_row)
    min_col = max(0, min_col)

    found: dict[str, Parser2000] = {}
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            # Try to create a Parser2000 - skip if the sheet code is invalid
            try:
                p = Parser2000(f"{zone}.{row}.{col}")
            except (ParseError, ValidationError):
                continue

            if _bboxes_intersect_2000(zone_bbox, p.get_bbox()):
                if target_scale == "1:10000":
                    found[p.sheet] = p
                else:
                    # Drill down to target_scale
                    _drill_down(p, zone_bbox, target_scale, found)
    return list(found.values())


def _drill_down(
    parent: Parser2000,
    zone_bbox: BBox,
    target_scale: str,
    result: dict[str, Parser2000],
) -> None:
    """
    Recursively drill down the hierarchy, checking the intersection with the bbox.

    Parameters
    ----------
    parent : Parser2000
        Parent to drill down from
    zone_bbox : BBox
        Bbox in the native CRS of the zone
    target_scale : str
        Target scale
    result : dict[str, Parser2000]
        Sheets found at the target scale by sheet code (modified in place)
    """
    # Special case: from 1:10000 to 1:5000 - the 5k branch
    if parent.scale == "1:10000" and target_scale == "1:5000":
        children = parent.get_children(scale="1:5000")
    else:
        children = parent.get_children()

    for child in children:
        child_bbox = child.get_bbox()

        if not _bboxes_intersect_2000(zone_bbox, child_bbox):
            continue

        if child.scale == target_scale:
            result[child.sheet] = child
        else:
            _drill_down(child, zone_bbox, target_scale, result)


def _in_zone(
    zone: int,
    zone_bbox: BBox,
    candidates: list[Parser2000],
    outline: bool,
) -> tuple[list[tuple[str, _Drawn | None]], float]:
    """
    Keep the candidates whose part inside the zone area meets the bbox.

    The test runs in WGS84, where the zone area is defined: the bbox (its
    envelope in the zone CRS, as for the candidates) and each sheet become
    polygons with edges densified to ``_EDGE_STEP_M``.

    Returns
    -------
    tuple
        The kept ``(sheet, drawn)`` pairs (``drawn`` only when asked for) and
        the share of the bbox inside the zone.
    """
    zone_crs = ZONE_EPSG[zone]
    boxes = np.array(
        [
            [b.min_x, b.min_y, b.max_x, b.max_y]
            for b in (c.get_bbox() for c in candidates)
        ]
    )
    around = transform_bbox(
        BBox(
            min(float(boxes[:, 0].min()), zone_bbox.min_x),
            min(float(boxes[:, 1].min()), zone_bbox.min_y),
            max(float(boxes[:, 2].max()), zone_bbox.max_x),
            max(float(boxes[:, 3].max()), zone_bbox.max_y),
            zone_crs,
        ),
        "EPSG:4326",
    )
    area = pl2000_zones.zone_area(
        zone,
        (
            around.min_x - _ZONE_MARGIN_DEG,
            around.min_y - _ZONE_MARGIN_DEG,
            around.max_x + _ZONE_MARGIN_DEG,
            around.max_y + _ZONE_MARGIN_DEG,
        ),
    )
    view = _wgs84_rectangles(
        zone_crs,
        np.array(
            [[zone_bbox.min_x, zone_bbox.min_y, zone_bbox.max_x, zone_bbox.max_y]]
        ),
    )[0]
    view_area = float(shapely.area(view))
    if area.is_empty or view_area <= 0.0:
        return [], 0.0

    sheets = None
    if shapely.covers(area, view):
        keep = np.ones(len(candidates), dtype=bool)
        share = 1.0
    else:
        part = shapely.intersection(area, view)
        share = float(shapely.area(part)) / view_area
        sheets = _wgs84_rectangles(zone_crs, boxes)
        inside = shapely.area(shapely.intersection(sheets, part))
        base = shapely.area(shapely.intersection(sheets, view))
        keep = inside > _MIN_SHARE * base

    kept = [c for c, k in zip(candidates, keep, strict=True) if k]
    if not outline:
        return [(c.sheet, None) for c in kept], share
    if sheets is None:
        sheets = _wgs84_rectangles(zone_crs, boxes)
    drawn = _outlines(sheets[keep], area)
    return [(c.sheet, d) for c, d in zip(kept, drawn, strict=True)], share


def _wgs84_rectangles(
    crs: str, boxes: np.ndarray, step: float = _EDGE_STEP_M
) -> np.ndarray:
    """
    Polygons in EPSG:4326 of rectangles of a zone CRS.

    ``boxes`` is an ``(n, 4)`` array ``(min_x, min_y, max_x, max_y)``; every
    edge is split into equal parts of at most ``step`` metres, at points
    computed from the corners alone, so neighbour sheets share them exactly.
    Rings start at the south-west corner and run counter-clockwise, like a
    GeoJSON exterior ring.
    """
    west, south, east, north = (boxes[:, i : i + 1] for i in range(4))
    nx = max(1, math.ceil(float(np.max(east - west)) / step))
    ny = max(1, math.ceil(float(np.max(north - south)) / step))
    xs = west + (east - west) * np.linspace(0.0, 1.0, nx + 1)
    ys = south + (north - south) * np.linspace(0.0, 1.0, ny + 1)
    xs[:, -1:] = east
    ys[:, -1:] = north
    ring_x = np.hstack(
        [
            xs[:, :-1],
            np.repeat(east, ny, axis=1),
            xs[:, :0:-1],
            np.repeat(west, ny + 1, axis=1),
        ]
    )
    ring_y = np.hstack(
        [
            np.repeat(south, nx, axis=1),
            ys[:, :-1],
            np.repeat(north, nx, axis=1),
            ys[:, ::-1],
        ]
    )
    lon, lat = _transformer(crs, "EPSG:4326").transform(ring_x.ravel(), ring_y.ravel())
    coords = np.stack(
        [np.reshape(lon, ring_x.shape), np.reshape(lat, ring_y.shape)], axis=-1
    )
    polygons: np.ndarray = shapely.polygons(coords)
    return polygons


def _outlines(sheets: np.ndarray, area: Any) -> list[_Drawn]:
    """Outlines and envelopes: the sheet inside its zone, else its part inside it."""
    whole = shapely.covers(area, sheets)
    drawn: list[_Drawn] = []
    for sheet, inside, bounds in zip(
        sheets, whole, shapely.bounds(sheets).tolist(), strict=True
    ):
        min_x, min_y, max_x, max_y = bounds
        envelope = BBox(min_x, min_y, max_x, max_y, "EPSG:4326")
        if inside:
            ring = shapely.get_coordinates(sheet).tolist()
            drawn.append(({"type": "Polygon", "coordinates": [ring]}, envelope))
            continue
        parts = [
            p
            for p in shapely.get_parts(shapely.intersection(sheet, area))
            if p.geom_type == "Polygon" and not p.is_empty
        ]
        clipped = parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)
        outline = json.loads(shapely.to_geojson(shapely.orient_polygons(clipped)))
        drawn.append((outline, envelope))
    return drawn
