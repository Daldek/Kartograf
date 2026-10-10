"""
Parser of topographic map sheet codes for the PL-2000 system.

This module provides the Parser2000 class for parsing Polish topographic
map sheet codes (godla) in PL-2000 coordinate system.
PL-2000 uses dot-separated numeric format: zone.row.column[.subdivisions]
(e.g., 6.179.12, 6.179.12.20).
"""

import math
import re

from kartograf.core.bbox import transform_bbox, validate_bbox
from kartograf.core.sheet_parser import (
    _DEGENERATE_EPS_DEG,
    BBox,
    _axis_overlaps,
    _expand_degenerate,
)
from kartograf.exceptions import ParseError, ValidationError

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
    godlo : str
        Normalized sheet code (e.g. "6.179.12")
    scale : str
        Map scale (e.g. "1:10000")
    uklad : str
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

    def __init__(self, godlo: str):
        """
        Initialize the parser for the given PL-2000 sheet code.

        Parameters
        ----------
        godlo : str
            Map sheet code (e.g. "6.179.12", "6.179.12.15")

        Raises
        ------
        ParseError
            If the sheet code is invalid or matches no pattern.
        ValidationError
            If ark_2k is outside the range 01-25.
        """
        if not isinstance(godlo, str):
            raise ParseError(f"Godlo musi byc stringiem, otrzymano: {type(godlo)}")

        godlo = godlo.strip()
        if not godlo:
            raise ParseError("Godlo nie moze byc puste")

        # Reject the PL-1992 format (dashes)
        if "-" in godlo:
            raise ParseError(
                f"Nieprawidlowe godlo PL-2000: '{godlo}'. "
                f"Format PL-1992 (z myslnikami) nie jest obslugiwany przez Parser2000."
            )

        self._godlo = godlo
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
            if re.match(pattern, self._godlo):
                return scale

        raise ParseError(
            f"Nieprawidlowe godlo PL-2000: '{self._godlo}'. "
            f"Godlo musi byc w formacie: strefa.pas.slup[.subdivisions]"
        )

    def _parse_components(self) -> dict[str, str]:
        """
        Parse the sheet code components.

        Returns
        -------
        dict[str, str]
            Dictionary of sheet code components
        """
        pattern = self.PATTERNS_2000[self._scale]
        match = re.match(pattern, self._godlo)

        if not match:
            raise ParseError(f"Blad parsowania godla: {self._godlo}")

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
                    f"Nieprawidlowy numer arkusza 1:2000: {ark_val}. "
                    f"Dozwolone wartosci: 01-25."
                )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def godlo(self) -> str:
        """Return the sheet code."""
        return self._godlo

    @property
    def scale(self) -> str:
        """Return the map scale."""
        return self._scale

    @property
    def uklad(self) -> str:
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
        return self._godlo == other._godlo

    def __hash__(self) -> int:
        """Return the object hash."""
        return hash(self._godlo)

    def __repr__(self) -> str:
        """Return a debugging representation of the object."""
        return f"Parser2000(godlo='{self._godlo}', scale='{self._scale}', uklad='2000')"

    def __str__(self) -> str:
        """Return a readable representation of the sheet."""
        return f"{self._godlo} (skala {self._scale}, uklad 2000)"

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
                f"Nieobslugiwany uklad wspolrzednych: {crs}. "
                f"Obslugiwane: {', '.join(sorted(_SUPPORTED_CRS))}"
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
        >>> Parser2000("6.179.12.15.2").get_parent().godlo
        '6.179.12.15'
        """
        if self._scale == "1:10000":
            return None

        # 1:5000 -> 1:10000 (drop ark_5k - the last segment)
        # 1:2000 -> 1:10000 (drop ark_2k - the last segment)
        # 1:1000 -> 1:2000 (drop ark_1k - the last segment)
        # 1:500  -> 1:1000 (drop ark_500 - the last segment)
        parent_godlo = self._godlo.rsplit(".", 1)[0]
        return Parser2000(parent_godlo)

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
        >>> [c.godlo for c in Parser2000("6.179.12").get_children(scale="1:5000")]
        ['6.179.12.1', '6.179.12.2', '6.179.12.3', '6.179.12.4']
        """
        if self._scale == "1:10000":
            if scale is None:
                scale = "1:2000"
            if scale == "1:5000":
                # 2x2: quadrants 1-4
                return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]
            if scale == "1:2000":
                # 5x5: sheets 01-25
                return [Parser2000(f"{self._godlo}.{i:02d}") for i in range(1, 26)]
            return []

        if self._scale == "1:2000":
            # 2x2: quadrants 1-4
            return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]

        if self._scale == "1:1000":
            # 2x2: quadrants 1-4
            return [Parser2000(f"{self._godlo}.{q}") for q in range(1, 5)]

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
                f"Nieznana skala: {target_scale}. "
                f"Dozwolone: {', '.join(SCALE_HIERARCHY_2000)}"
            )

        # Find the indices in the hierarchy
        current_idx = SCALE_HIERARCHY_2000.index(self._scale)
        target_idx = SCALE_HIERARCHY_2000.index(target_scale)

        if target_idx < current_idx:
            raise ValidationError(
                f"Skala docelowa {target_scale} jest grubsza niz "
                f"biezaca skala {self._scale}."
            )

        # Special case: from 1:10000 to 1:5000 - the 5k branch
        if self._scale == "1:10000" and target_scale == "1:5000":
            return self.get_children(scale="1:5000")

        # Special case: nothing below 1:5000 (leaves)
        if self._scale == "1:5000" and target_scale != "1:5000":
            raise ValidationError(
                f"Arkusz 1:5000 nie ma potomkow w skali {target_scale}. "
                f"Galaz 1:5000 jest niezalezna i nie ma drobniejszych podzialkow."
            )

        # Recursively: expand the children down to target_scale
        children = self.get_children()
        if not children:
            raise ValidationError(
                f"Arkusz {self._godlo} ({self._scale}) nie ma potomkow "
                f"w skali {target_scale}."
            )

        if children[0].scale == target_scale:
            return sorted(children, key=lambda p: p.godlo)

        # Recursion
        result = []
        for child in children:
            result.extend(child.get_all_descendants(target_scale))
        return sorted(result, key=lambda p: p.godlo)

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

# Longitude ranges for PL-2000 zones
_ZONE_LON_RANGES = {
    5: (13.5, 16.5),
    6: (16.5, 19.5),
    7: (19.5, 22.5),
    8: (22.5, 25.5),
}


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


def _determine_zones_for_bbox(bbox_wgs84: BBox) -> list[int]:
    """
    Determine the PL-2000 zones intersected by a bbox in WGS84.

    Parameters
    ----------
    bbox_wgs84 : BBox
        Bbox in EPSG:4326 (min_x=west_lon, max_x=east_lon)

    Returns
    -------
    list[int]
        List of zone numbers (5-8) sorted ascending
    """
    west_lon = bbox_wgs84.min_x
    east_lon = bbox_wgs84.max_x

    zones = []
    for zone_num, (zone_west, zone_east) in _ZONE_LON_RANGES.items():
        # A zone intersects the bbox if the longitude ranges overlap
        if west_lon < zone_east and east_lon > zone_west:
            zones.append(zone_num)

    return sorted(zones)


def find_sheets_2000_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    zone: int | None = None,
) -> list[str]:
    """
    Find the PL-2000 sheet codes covering the given bounding box.

    Parameters
    ----------
    bbox : BBox
        Bounding box in any supported CRS
        (EPSG:2176-2179, EPSG:2180, EPSG:4326)
    target_scale : str
        Target scale (default: "1:10000").
        Supported: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
    zone : int | None
        If given, restricts the search to this zone (5-8).
        If None, the zone is detected automatically from the bbox.

    Returns
    -------
    list[str]
        Sorted list of PL-2000 sheet codes covering the bbox.
        Edge convention as in PL-1992: only a positive intersection area
        counts (touching at an edge is not enough), and a degenerate bbox
        (a point) yields exactly one sheet - the one east/north of the grid line.

    Raises
    ------
    ValidationError
        If target_scale is invalid, the CRS is unsupported, or the bbox is
        inverted (min > max) or has a NaN/inf value
    """
    if target_scale not in SCALE_HIERARCHY_2000:
        raise ValidationError(
            f"Nieprawidlowa skala: '{target_scale}'. "
            f"Dozwolone: {', '.join(SCALE_HIERARCHY_2000)}"
        )

    validate_bbox(bbox)

    # Step 1: Transform to WGS84 for zone detection
    bbox_wgs84 = transform_bbox(bbox, "EPSG:4326")

    # Step 2: Determine the zones. Detection compares longitude ranges with
    # strict inequalities, so a point on a zone-boundary meridian
    # (16.5/19.5/22.5E) would fall into no zone without the expansion
    # (review 0.7.0, round 1). The expansion is used ONLY for detection - we
    # keep transforming the exact bbox to the zone CRS, so that the metric
    # eps decides the sheet.
    detect_bbox = _expand_degenerate(bbox_wgs84, _DEGENERATE_EPS_DEG)
    zones = [zone] if zone is not None else _determine_zones_for_bbox(detect_bbox)

    if not zones:
        return []

    # Step 3: For each zone find the 1:10k sheets
    all_godla: set[str] = set()

    for z in zones:
        zone_crs = ZONE_EPSG[z]

        # Transform the bbox to the zone CRS
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

        # Compute the row/col range for 1:10k
        min_row = math.floor((zone_bbox.min_y - 4_920_000) / 5000) - 1
        max_row = math.floor((zone_bbox.max_y - 4_920_000) / 5000) + 1
        min_col = math.floor((zone_bbox.min_x - z * 1_000_000 - 332_000) / 8000) - 1
        max_col = math.floor((zone_bbox.max_x - z * 1_000_000 - 332_000) / 8000) + 1

        # Clamp to sane values (pas >= 0, slup >= 0)
        min_row = max(0, min_row)
        min_col = max(0, min_col)

        # Step 4: Check the intersection for every candidate
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                godlo_10k = f"{z}.{row}.{col}"

                # Try to create a Parser2000 - skip if the sheet code is invalid
                try:
                    p = Parser2000(godlo_10k)
                except (ParseError, ValidationError):
                    continue

                sheet_bbox = p.get_bbox()

                if _bboxes_intersect_2000(zone_bbox, sheet_bbox):
                    if target_scale == "1:10000":
                        all_godla.add(godlo_10k)
                    else:
                        # Drill down to target_scale
                        _drill_down(p, zone_bbox, target_scale, all_godla)

    return sorted(all_godla)


def _drill_down(
    parent: Parser2000,
    zone_bbox: BBox,
    target_scale: str,
    result: set[str],
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
    result : set[str]
        Result set of sheet codes (modified in place)
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
            result.add(child.godlo)
        else:
            _drill_down(child, zone_bbox, target_scale, result)
