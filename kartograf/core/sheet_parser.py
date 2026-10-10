"""
Parser of topographic map sheet codes for the 1992 and 2000 systems.

This module provides the SheetParser class for parsing Polish topographic
map sheet codes (godlo) and extracting information about scale,
coordinate system, and sheet components.
"""

import math
import re

from kartograf.core import parser_registry
from kartograf.core.bbox import BBox, transform_bbox, validate_bbox
from kartograf.exceptions import ParseError, ValidationError


def _is_pl2000_format(godlo: str) -> bool:
    """Check if godlo uses PL-2000 dot-separated numeric format (via registry)."""
    return parser_registry.detect_system(godlo).id == "pl2000"


_PL2000_ZONES = ("5", "6", "7", "8")


def _zone_number_error(godlo: str) -> ParseError:
    """Build the error for a bare PL-2000 zone number used as a sheet code."""
    return ParseError(
        f"Nieprawidłowe godło: '{godlo}'. "
        f"To numer strefy PL-2000, a nie godło arkusza. "
        f"Najgrubsze godło PL-2000 ma format strefa.pas.slup "
        f"(1:10000), np. 6.179.12."
    )


class SheetParser:
    """
    Parser of topographic map sheet codes for the 1992 and 2000 systems.

    Supported scales: 1:1000000 to 1:10000

    Attributes
    ----------
    godlo : str
        Normalized sheet code (e.g. "N-34-130-D-d-2-4")
    scale : str
        Map scale (e.g. "1:10000")
    uklad : str
        Coordinate system ("1992" or "2000")
    components : Dict[str, str]
        Sheet code components (pas, slup, and optional subdivisions)

    Examples
    --------
    >>> parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
    >>> parser.scale
    '1:10000'
    >>> parser.components
    {'pas': 'N', 'slup': '34', 'arkusz_200k': '130', 'arkusz_100k': 'D',
     'arkusz_50k': 'd', 'arkusz_25k': '2', 'arkusz_10k': '4'}

    Notes
    -----
    Scale labels in Kartograf are one level finer than GUGiK nomenclature: a
    7-part godlo (e.g. N-34-130-D-d-2-4) is labelled '1:10000' here, while
    GUGiK calls the same sheet the 1:5000 archiving module; the 1-144 grid is
    labelled '1:200000' but has the dimensions of the official 1:100000 sheet
    (20' x 30'). Labels are kept for backward compatibility of the public API
    and CLI `--scale`; aliases are planned for the next major release.
    """

    # Scale hierarchy (from largest to smallest)
    SCALE_HIERARCHY = [
        "1:1000000",
        "1:500000",
        "1:200000",
        "1:100000",
        "1:50000",
        "1:25000",
        "1:10000",
    ]

    # Sheet code patterns for each scale ([0-9]: ASCII digits only, not \d)
    PATTERNS = {
        "1:1000000": r"^([A-Z])-([0-9]{1,2})$",
        "1:500000": r"^([A-Z])-([0-9]{1,2})-([A-D])$",
        "1:200000": r"^([A-Z])-([0-9]{1,2})-([0-9]{1,3})$",
        "1:100000": r"^([A-Z])-([0-9]{1,2})-([0-9]{1,3})-([A-D])$",
        "1:50000": r"^([A-Z])-([0-9]{1,2})-([0-9]{1,3})-([A-D])-([a-d])$",
        "1:25000": r"^([A-Z])-([0-9]{1,2})-([0-9]{1,3})-([A-D])-([a-d])-([1-4])$",
        "1:10000": (
            r"^([A-Z])-([0-9]{1,2})-([0-9]{1,3})-([A-D])-([a-d])-([1-4])-([1-4])$"
        ),
    }

    # Component names for each regex group
    COMPONENT_NAMES = [
        "pas",
        "slup",
        "arkusz_200k",
        "arkusz_100k",
        "arkusz_50k",
        "arkusz_25k",
        "arkusz_10k",
    ]

    # Allowed coordinate systems
    VALID_UKLADY = ("1992", "2000")

    # PL-1992 nomenclature range (A7): the 1:1M sheets covering Poland
    VALID_BANDS = ("M", "N")
    VALID_COLUMNS = range(33, 36)
    VALID_SHEET_NUMBERS = range(1, 145)

    def __init__(self, godlo: str, uklad: str | None = None):
        """
        Initialize the parser for the given sheet code.

        Parameters
        ----------
        godlo : str
            Map sheet code (e.g. "N-34-130-D-d-2-4")
        uklad : str, optional
            Coordinate system ("1992" or "2000").
            If None, it defaults to "1992".

        Raises
        ------
        ParseError
            If the sheet code is invalid or matches no pattern.
        ValidationError
            If the coordinate system is invalid.

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D", uklad="1992")
        >>> parser.scale
        '1:100000'
        """
        if not isinstance(godlo, str):
            raise ParseError(f"Godło musi być stringiem, otrzymano: {type(godlo)}")

        cleaned = godlo.strip()
        if not cleaned:
            raise ParseError("Godło nie może być puste")

        # Auto-detect PL-2000 format (dots + digits only, starts with 5-8)
        if _is_pl2000_format(cleaned):
            from kartograf.core.parser_2000 import Parser2000

            if uklad is not None and uklad != "2000":
                raise ValidationError(
                    f"Godło '{cleaned}' ma format PL-2000, ale podano uklad='{uklad}'"
                )
            self._pl2000: Parser2000 | None = Parser2000(cleaned)
            self._original_godlo = cleaned
            self._godlo = self._pl2000.godlo
            self._uklad = "2000"
            self._scale = self._pl2000.scale
            self._components = self._pl2000.components
        else:
            if cleaned in _PL2000_ZONES:
                raise _zone_number_error(cleaned)
            if uklad is not None and uklad == "2000":
                raise ValidationError(
                    f"Godło '{cleaned}' ma format PL-1992, ale podano uklad='2000'"
                )
            self._pl2000 = None
            self._original_godlo = cleaned

            # Normalize the sheet code (lowercase letters for 50k sheets and smaller)
            self._godlo = self._normalize_godlo(self._original_godlo)

            # Validate and set the coordinate system
            self._uklad = self._validate_uklad(uklad)

            # Determine the scale and validate the format
            self._scale = self._determine_scale()

            # Parse the components
            self._components = self._parse_components()

            # Reject codes outside the nomenclature range (A7)
            self._validate_range()

    def _normalize_godlo(self, godlo: str) -> str:
        """
        Normalize the sheet code to the standard format.

        The band letter (first) and the 100k sheet letters are uppercase.
        The 50k sheet letters and smaller are lowercase.

        Parameters
        ----------
        godlo : str
            Original sheet code

        Returns
        -------
        str
            Normalized sheet code
        """
        parts = godlo.split("-")
        if len(parts) < 2:
            return godlo  # Return unchanged, validation will report the error

        normalized = []

        for i, part in enumerate(parts):
            if i == 0:
                # Letter band - always uppercase
                normalized.append(part.upper())
            elif i == 3:
                # 100k sheet (A-D) - uppercase
                normalized.append(part.upper())
            elif i == 4 and len(part) == 1 and part.upper() in "ABCD":
                # 50k sheet (a-d) - lowercase
                normalized.append(part.lower())
            elif part.isascii() and part.isdigit():
                # Numbers without leading zeros - the GUGiK index form
                # (e.g. 'M-33-8-A-a-3-1'); '036' and '36' are one sheet (A7)
                normalized.append(part.lstrip("0") or "0")
            else:
                # Remaining parts unchanged
                normalized.append(part)

        return "-".join(normalized)

    def _validate_uklad(self, uklad: str | None) -> str:
        """
        Validate the coordinate system.

        Parameters
        ----------
        uklad : str or None
            System to validate, or None for the default

        Returns
        -------
        str
            Coordinate system ("1992" or "2000")

        Raises
        ------
        ValidationError
            If the coordinate system is invalid
        """
        if uklad is None:
            return "1992"  # Default system

        if uklad not in self.VALID_UKLADY:
            raise ValidationError(
                f"Nieprawidłowy układ: '{uklad}'. "
                f"Dozwolone wartości: {', '.join(self.VALID_UKLADY)}"
            )

        return uklad

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
        for scale, pattern in self.PATTERNS.items():
            if re.match(pattern, self._godlo):
                return scale

        if self._original_godlo in _PL2000_ZONES:
            raise _zone_number_error(self._original_godlo)

        raise ParseError(
            f"Nieprawidłowe godło: '{self._original_godlo}'. "
            f"Oczekiwano godła PL-1992 (np. N-34-130-D-d-2-4) "
            f"albo PL-2000 (np. 6.179.12)."
        )

    def _parse_components(self) -> dict[str, str]:
        """
        Parse the sheet code components.

        Returns
        -------
        Dict[str, str]
            Dictionary of sheet code components
        """
        pattern = self.PATTERNS[self._scale]
        match = re.match(pattern, self._godlo)

        if not match:
            raise ParseError(f"Błąd parsowania godła: {self._godlo}")

        groups = match.groups()
        components = {}

        for i, value in enumerate(groups):
            components[self.COMPONENT_NAMES[i]] = value

        return components

    def _validate_range(self) -> None:
        """Reject codes outside the PL-1992 nomenclature range (before any network).

        Raises
        ------
        ParseError
            Band outside M/N, column outside 33-35 or 1:200k sheet number
            outside 1-144.
        """
        problems = []
        pas = self._components["pas"]
        slup = int(self._components["slup"])
        if pas not in self.VALID_BANDS:
            problems.append(f"pas {pas} (dozwolone: M, N)")
        if slup not in self.VALID_COLUMNS:
            problems.append(f"slup {slup} (dozwolone: 33-35)")
        sheet = self._components.get("arkusz_200k", "")
        if sheet.isdigit() and int(sheet) not in self.VALID_SHEET_NUMBERS:
            problems.append(f"arkusz {sheet} (dozwolone: 1-144)")
        if problems:
            raise ParseError(
                f"Nieprawidlowe godlo: '{self._original_godlo}' — poza zakresem "
                f"nomenklatury PL-1992: {', '.join(problems)}"
            )

    @property
    def godlo(self) -> str:
        """Return the normalized sheet code."""
        return self._godlo

    @property
    def scale(self) -> str:
        """Return the map scale."""
        return self._scale

    @property
    def uklad(self) -> str:
        """Return the coordinate system."""
        return self._uklad

    @property
    def components(self) -> dict[str, str]:
        """Return a dictionary of sheet code components."""
        return self._components.copy()

    def __repr__(self) -> str:
        """Return a debugging representation of the object."""
        return (
            f"SheetParser(godlo='{self._godlo}', "
            f"scale='{self._scale}', uklad='{self._uklad}')"
        )

    def __str__(self) -> str:
        """Return a readable representation of the sheet."""
        return f"{self._godlo} (skala {self._scale}, układ {self._uklad})"

    def __eq__(self, other: object) -> bool:
        """Compare two parsers by sheet code and coordinate system."""
        if not isinstance(other, SheetParser):
            return NotImplemented
        return self._godlo == other._godlo and self._uklad == other._uklad

    def __hash__(self) -> int:
        """Return the object hash."""
        return hash((self._godlo, self._uklad))

    # =========================================================================
    # Hierarchy methods
    # =========================================================================

    # Mapping of scales to suffixes for children
    _CHILD_SUFFIXES = {
        "1:1000000": ["A", "B", "C", "D"],  # 1:1M → 1:500k (4 parts)
        "1:500000": None,  # 1:500k → 1:200k (36 parts, needs special logic)
        "1:200000": ["A", "B", "C", "D"],  # 1:200k → 1:100k (4 parts)
        "1:100000": ["a", "b", "c", "d"],  # 1:100k → 1:50k (4 parts)
        "1:50000": ["1", "2", "3", "4"],  # 1:50k → 1:25k (4 parts)
        "1:25000": ["1", "2", "3", "4"],  # 1:25k → 1:10k (4 parts)
    }

    def get_parent(self) -> "SheetParser | None":
        """
        Return the parent sheet (of a smaller scale).

        Returns
        -------
        SheetParser or None
            Parser of the parent sheet, or None if this is the top level (1:1M)

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> parent = parser.get_parent()
        >>> parent.godlo
        'N-34-130-D-d-2'
        >>> parent.scale
        '1:25000'
        """
        if self._pl2000 is not None:
            p = self._pl2000.get_parent()
            return SheetParser(p.godlo) if p is not None else None

        current_scale_idx = self.SCALE_HIERARCHY.index(self._scale)

        if current_scale_idx == 0:
            return None  # Already the top level (1:1M)

        # Special logic for 1:200k → 1:500k
        if self._scale == "1:200000":
            return self._get_parent_from_200k()

        # For the remaining scales: drop the last component
        parts = self._godlo.split("-")
        if len(parts) <= 2:
            return None

        parent_godlo = "-".join(parts[:-1])
        return SheetParser(parent_godlo, self._uklad)

    def _get_parent_from_200k(self) -> "SheetParser":
        """
        Return the parent 1:500k sheet for a 1:200k sheet.

        1:200k sheets are numbered 1-144 in a 12×12 grid within 1:1M
        (row by row, W->E, N->S - see `_apply_200k_subdivision`).
        Each 1:500k sheet (A, B, C, D) is a 6×6 block of that grid:

        A: rows 0-5, columns 0-5 (e.g. 1-6, 13-18, ..., 61-66)
        B: rows 0-5, columns 6-11 (e.g. 7-12, 19-24, ..., 67-72)
        C: rows 6-11, columns 0-5 (e.g. 73-78, 85-90, ..., 133-138)
        D: rows 6-11, columns 6-11 (e.g. 79-84, 91-96, ..., 139-144)

        Returns
        -------
        SheetParser
            Parser of the 1:500k sheet
        """
        arkusz_num = int(self._components["arkusz_200k"])
        # Quadrant = block of 6 rows x 6 columns of the 12x12 grid, NOT a band
        # of 36 consecutive numbers - that was the bug: (nr-1)//36 = 3 full-width rows.
        row, col = divmod(arkusz_num - 1, 12)
        section_letter = "ABCD"[(row >= 6) * 2 + (col >= 6)]

        parent_godlo = (
            f"{self._components['pas']}-{self._components['slup']}-{section_letter}"
        )
        return SheetParser(parent_godlo, self._uklad)

    def get_children(self) -> "list[SheetParser]":
        """
        Return all child sheets (of a larger scale).

        Returns
        -------
        List[SheetParser]
            List of child sheet parsers.
            Empty list if this is the lowest level (1:10k).

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2")
        >>> children = parser.get_children()
        >>> len(children)
        4
        >>> children[0].godlo
        'N-34-130-D-d-2-1'
        """
        if self._pl2000 is not None:
            return [SheetParser(c.godlo) for c in self._pl2000.get_children()]

        current_scale_idx = self.SCALE_HIERARCHY.index(self._scale)

        if current_scale_idx == len(self.SCALE_HIERARCHY) - 1:
            return []  # Already the lowest level (1:10k)

        # Special logic for 1:500k → 1:200k (36 sheets)
        if self._scale == "1:500000":
            return self._get_children_from_500k()

        # For the remaining scales: append suffixes
        # 1:500k (the only None entry) is handled above
        suffixes = self._CHILD_SUFFIXES.get(self._scale) or []
        children = []

        for suffix in suffixes:
            child_godlo = f"{self._godlo}-{suffix}"
            children.append(SheetParser(child_godlo, self._uklad))

        return children

    def _get_children_from_500k(self) -> "list[SheetParser]":
        """
        Return the 36 1:200k sheets for a 1:500k sheet.

        1:200k sheets are numbered in a 12x12 grid (row by row, W->E, N->S).
        A 1:500k section is a 6x6 block of that grid:

        A: rows 0-5, columns 0-5 (e.g. 1-6, 13-18, ..., 61-66)
        B: rows 0-5, columns 6-11 (e.g. 7-12, 19-24, ..., 67-72)
        C: rows 6-11, columns 0-5 (e.g. 73-78, 85-90, ..., 133-138)
        D: rows 6-11, columns 6-11 (e.g. 79-84, 91-96, ..., 139-144)

        Order of children: row by row (N->S), W->E within a row.

        Returns
        -------
        List[SheetParser]
            List of 36 parsers of 1:200k sheets
        """
        section_letter = self._components["arkusz_200k"]  # A, B, C, or D
        section_idx = "ABCD".index(section_letter)
        row_start = 6 if section_idx >= 2 else 0
        col_start = 6 if section_idx % 2 == 1 else 0

        children = []
        pas = self._components["pas"]
        slup = self._components["slup"]
        for row in range(row_start, row_start + 6):
            for col in range(col_start, col_start + 6):
                num = row * 12 + col + 1
                child_godlo = f"{pas}-{slup}-{num}"
                children.append(SheetParser(child_godlo, self._uklad))

        return children

    def get_hierarchy_up(self) -> "list[SheetParser]":
        """
        Return the full hierarchy upwards (up to 1:1000000).

        Returns
        -------
        List[SheetParser]
            List of parsers from the current one to the top level (inclusive).
            The first element is the current sheet, the last is the 1:1M sheet.

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> hierarchy = parser.get_hierarchy_up()
        >>> len(hierarchy)
        7
        >>> hierarchy[0].scale, hierarchy[-1].scale
        ('1:10000', '1:1000000')
        """
        if self._pl2000 is not None:
            h = self._pl2000.get_hierarchy_up()
            return [SheetParser(x.godlo) for x in h]

        hierarchy = [self]
        current = self

        while True:
            parent = current.get_parent()
            if parent is None:
                break
            hierarchy.append(parent)
            current = parent

        return hierarchy

    def get_all_descendants(self, target_scale: str) -> "list[SheetParser]":
        """
        Return all descendant sheets down to the given scale.

        Parameters
        ----------
        target_scale : str
            Target scale (e.g. "1:10000")

        Returns
        -------
        List[SheetParser]
            List of all descendant sheets at the target scale

        Raises
        ------
        ValidationError
            If target_scale is not a valid scale
        ValueError
            If target_scale is smaller than or equal to the current scale

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d")
        >>> descendants = parser.get_all_descendants("1:10000")
        >>> len(descendants)  # 4 * 4 = 16 sheets
        16
        >>> all(d.scale == "1:10000" for d in descendants)
        True
        """
        if self._pl2000 is not None:
            desc = self._pl2000.get_all_descendants(target_scale)
            return [SheetParser(d.godlo) for d in desc]

        if target_scale not in self.SCALE_HIERARCHY:
            raise ValidationError(
                f"Nieprawidłowa skala: '{target_scale}'. "
                f"Dozwolone: {', '.join(self.SCALE_HIERARCHY)}"
            )

        current_idx = self.SCALE_HIERARCHY.index(self._scale)
        target_idx = self.SCALE_HIERARCHY.index(target_scale)

        if target_idx <= current_idx:
            raise ValueError(
                f"Skala docelowa {target_scale} musi być większa "
                f"(bardziej szczegółowa) niż bieżąca {self._scale}"
            )

        # Collect the descendants recursively
        def collect_descendants(parser: SheetParser) -> list[SheetParser]:
            if parser.scale == target_scale:
                return [parser]

            all_descendants = []
            for child in parser.get_children():
                all_descendants.extend(collect_descendants(child))

            return all_descendants

        return collect_descendants(self)

    # =========================================================================
    # Bounding box computation methods
    # =========================================================================

    # Sheet dimensions in arc minutes (latitude, longitude)
    # Computed from the subdivision hierarchy
    _SHEET_DIMENSIONS = {
        "1:1000000": (240.0, 360.0),  # 4° × 6°
        "1:500000": (120.0, 180.0),  # 2° × 3°
        "1:200000": (20.0, 30.0),  # 20' × 30' (36 per 1:500k)
        "1:100000": (10.0, 15.0),  # 10' × 15' (4 per 1:200k)
        "1:50000": (5.0, 7.5),  # 5' × 7.5' (4 per 1:100k)
        "1:25000": (2.5, 3.75),  # 2.5' × 3.75' (4 per 1:50k)
        "1:10000": (1.25, 1.875),  # 1.25' × 1.875' (4 per 1:25k)
    }

    # Mapping of letters to positions in the 2×2 grid (row, col) - 0-indexed
    # A/a/1 = NW (top-left), B/b/2 = NE (top-right)
    # C/c/3 = SW (bottom-left), D/d/4 = SE (bottom-right)
    _QUADRANT_POSITIONS = {
        "A": (0, 0),
        "B": (0, 1),
        "C": (1, 0),
        "D": (1, 1),
        "a": (0, 0),
        "b": (0, 1),
        "c": (1, 0),
        "d": (1, 1),
        "1": (0, 0),
        "2": (0, 1),
        "3": (1, 0),
        "4": (1, 1),
    }

    def get_bbox(self, crs: str | None = None) -> BBox:
        """
        Compute the bounding box of the sheet in the given coordinate system.

        Parameters
        ----------
        crs : str, optional
            Target coordinate system.
            Default: "EPSG:2180" for PL-1992, the native zone CRS for PL-2000.
            Supported: "EPSG:2180", "EPSG:4326", "EPSG:2176"-"EPSG:2179"

        Returns
        -------
        BBox
            NamedTuple with fields: min_x, min_y, max_x, max_y, crs

        Examples
        --------
        >>> parser = SheetParser("N-34-130-D-d-2-4")
        >>> bbox = parser.get_bbox("EPSG:4326")
        >>> print(f"SW: ({bbox.min_x}, {bbox.min_y})")
        """
        if self._pl2000 is not None:
            return self._pl2000.get_bbox(crs=crs)

        # Default CRS for PL-1992
        if crs is None:
            crs = "EPSG:2180"

        # Compute the bbox in WGS84 (degrees)
        south, north, west, east = self._calculate_wgs84_bbox()

        if crs == "EPSG:4326":
            return BBox(
                min_x=west, min_y=south, max_x=east, max_y=north, crs="EPSG:4326"
            )

        if crs == "EPSG:2180":
            # Densified envelope (core.bbox): for sheets crossing 19E,
            # 4 corners raised the lower edge (N-34: ~468 m)
            return transform_bbox(
                BBox(min_x=west, min_y=south, max_x=east, max_y=north, crs="EPSG:4326"),
                "EPSG:2180",
            )

        raise ValidationError(
            f"Nieobsługiwany układ współrzędnych: {crs}. "
            "Obsługiwane: EPSG:2180, EPSG:4326"
        )

    def _calculate_wgs84_bbox(self) -> tuple:
        """
        Compute the bounding box in WGS84 (degrees).

        Returns
        -------
        tuple
            (south_lat, north_lat, west_lon, east_lon) in degrees
        """
        # Base coordinates of the 1:1M sheet
        pas = self._components["pas"]
        slup = int(self._components["slup"])

        # Band: A=0, B=1, ..., N=13
        row_1m = ord(pas) - ord("A")

        # 1:1M coordinates
        south_1m = row_1m * 4.0  # 4° per band
        north_1m = south_1m + 4.0
        west_1m = (slup - 31) * 6.0  # Column 31 = 0°E
        east_1m = west_1m + 6.0

        if self._scale == "1:1000000":
            return (south_1m, north_1m, west_1m, east_1m)

        # 1:500k - 2×2 subdivision of 1:1M
        if self._scale in (
            "1:500000",
            "1:200000",
            "1:100000",
            "1:50000",
            "1:25000",
            "1:10000",
        ):
            south, north, west, east = self._apply_500k_subdivision(
                south_1m, north_1m, west_1m, east_1m
            )
        else:
            south, north, west, east = south_1m, north_1m, west_1m, east_1m

        return (south, north, west, east)

    def _apply_500k_subdivision(
        self, south: float, north: float, west: float, east: float
    ) -> tuple:
        """Apply the subdivision for 1:500k and smaller scales."""

        # 1:500k - arkusz_200k holds a letter A-D (misleading name in COMPONENT_NAMES)
        if "arkusz_200k" in self._components:
            letter = self._components["arkusz_200k"]

            # If it is a letter A-D, this is the 1:500k subdivision
            if letter in "ABCD":
                row, col = self._QUADRANT_POSITIONS[letter]
                height = (north - south) / 2.0
                width = (east - west) / 2.0
                north = north - row * height
                south = north - height
                west = west + col * width
                east = west + width

                if self._scale == "1:500000":
                    return (south, north, west, east)

            # If it is a number, it is the 1:200k sheet number (1-144)
            elif letter.isdigit() or (len(self._components.get("arkusz_200k", "")) > 1):
                arkusz_num = int(self._components["arkusz_200k"])
                return self._apply_200k_subdivision(
                    south_1m=south,
                    north_1m=north,
                    west_1m=west,
                    east_1m=east,
                    arkusz_num=arkusz_num,
                )

        return (south, north, west, east)

    def _apply_200k_subdivision(
        self,
        south_1m: float,
        north_1m: float,
        west_1m: float,
        east_1m: float,
        arkusz_num: int,
    ) -> tuple:
        """
        Compute the bbox for a 1:200k sheet and smaller.

        1:200k sheets are numbered 1-144 in a 12×12 grid within 1:1M.
        """
        # Position in the 12×12 grid (numbered from top-left, row by row)
        row = (arkusz_num - 1) // 12  # 0-11
        col = (arkusz_num - 1) % 12  # 0-11

        # Dimensions of a single 1:200k sheet in degrees
        height = (north_1m - south_1m) / 12.0  # 4°/12 = 20'
        width = (east_1m - west_1m) / 12.0  # 6°/12 = 30'

        # Compute the bbox (sheets are numbered from the top, so row=0 is north)
        north = north_1m - row * height
        south = north - height
        west = west_1m + col * width
        east = west + width

        if self._scale == "1:200000":
            return (south, north, west, east)

        # 1:100k - 1:200k sheet split into 4 parts (A-D)
        if "arkusz_100k" in self._components:
            letter = self._components["arkusz_100k"]
            row_q, col_q = self._QUADRANT_POSITIONS[letter]
            q_height = height / 2.0
            q_width = width / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:100000":
                return (south, north, west, east)

        # 1:50k - 1:100k sheet split into 4 parts (a-d)
        if "arkusz_50k" in self._components:
            letter = self._components["arkusz_50k"]
            row_q, col_q = self._QUADRANT_POSITIONS[letter]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:50000":
                return (south, north, west, east)

        # 1:25k - 1:50k sheet split into 4 parts (1-4)
        if "arkusz_25k" in self._components:
            num = self._components["arkusz_25k"]
            row_q, col_q = self._QUADRANT_POSITIONS[num]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

            if self._scale == "1:25000":
                return (south, north, west, east)

        # 1:10k - 1:25k sheet split into 4 parts (1-4)
        if "arkusz_10k" in self._components:
            num = self._components["arkusz_10k"]
            row_q, col_q = self._QUADRANT_POSITIONS[num]
            q_height = (north - south) / 2.0
            q_width = (east - west) / 2.0
            north = north - row_q * q_height
            south = north - q_height
            west = west + col_q * q_width
            east = west + q_width

        return (south, north, west, east)


# =========================================================================
# Standalone functions: bbox → sheet code lookup
# =========================================================================


# Edge tolerance - the intersection must have a positive area (audit 0.7.0, A1-7).
_EDGE_TOL = 1e-9
# degrees (~1 cm) - expands a point/line bbox on its max side (PL-1992, sheet_parser.py)
_DEGENERATE_EPS_DEG = 1e-7


def _axis_overlaps(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    """
    Positive-length overlap of two ranges on a single axis.

    A degenerate range ``a`` (a point/line, ``a_max - a_min <= _EDGE_TOL``) is
    resolved by containment in the half-open interval ``[b_min, b_max)`` - a
    point sitting on the MAX edge belongs to the next range, never to both.
    """
    if a_max - a_min <= _EDGE_TOL:  # degenerate axis: containment, half-open at max
        return b_min - _EDGE_TOL <= a_min < b_max - _EDGE_TOL
    return min(a_max, b_max) - max(a_min, b_min) > _EDGE_TOL


def _expand_degenerate(bbox: BBox, eps: float) -> BBox:
    """
    Expand a degenerate bbox axis (point/hairline) by ``eps`` on the MAX side.

    This way a point lying exactly on a grid line yields exactly one sheet -
    the one east/north of the line (audit 0.7.0, A1-7/A1-13).

    An axis is considered degenerate when its span is ``<= 2 * _EDGE_TOL``: such
    a bbox straddling a grid line cannot produce an overlap larger than
    ``_EDGE_TOL`` on either side, so without normalization it would return
    an empty list of sheets (review 0.7.0, round 1).

    Parameters
    ----------
    bbox : BBox
        Bbox to normalize
    eps : float
        Expansion in the units of the bbox CRS

    Returns
    -------
    BBox
        Bbox with a span allowing a positive intersection area
    """
    hairline = 2 * _EDGE_TOL
    max_x = bbox.max_x if bbox.max_x - bbox.min_x > hairline else bbox.min_x + eps
    max_y = bbox.max_y if bbox.max_y - bbox.min_y > hairline else bbox.min_y + eps
    return BBox(bbox.min_x, bbox.min_y, max_x, max_y, bbox.crs)


def _bboxes_intersect(a: BBox, b: BBox) -> bool:
    """
    Positive-area intersection; shared edges/corners do NOT count
    (audit 0.7.0, A1-7).

    Parameters
    ----------
    a, b : BBox
        Bounding boxes to check (should be in the same CRS).
        ``a`` is the query bbox - its degenerate axis (a point) is resolved
        by containment in the half-open interval of ``b``.

    Returns
    -------
    bool
        True if the intersection area is positive (> _EDGE_TOL on both axes)
    """
    return _axis_overlaps(a.min_x, a.max_x, b.min_x, b.max_x) and _axis_overlaps(
        a.min_y, a.max_y, b.min_y, b.max_y
    )


def find_sheets_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    system: str = "1992",
) -> list[str]:
    """
    Find the sheet codes of the sheets covering the given bounding box.

    Algorithm: hierarchical pruning - mathematically computes the 1:1M and
    1:200k sheets, then recursively narrows down to the target scale.

    Edge convention: only sheets with a positive intersection area with the
    bbox are returned - touching edges/corners is not enough (audit 0.7.0,
    A1-7). A bbox exactly equal to a sheet IN EPSG:4326 yields only that sheet
    and its descendants; a bbox in EPSG:2180 is first converted to a WGS84
    envelope (wider), so the selection may include neighbouring sheets (the
    EPSG:2180 envelope of sheet N-34-130-D-d-2-4 yields 9 sheet codes). A
    degenerate bbox (a point) yields exactly one sheet - the one east/north of
    the grid line.

    Parameters
    ----------
    bbox : BBox
        Bounding box in EPSG:2180 or EPSG:4326
    target_scale : str
        Target scale (default: "1:10000")
    system : str
        Coordinate system: "1992" (PL-1992) or "2000" (PL-2000).
        Default: "1992" - full backward compatibility.

    Returns
    -------
    list[str]
        Sorted list of sheet codes of the sheets covering the bbox

    Raises
    ------
    ValidationError
        If the system, target_scale or CRS is unsupported, and also for an
        inverted bbox (min > max) or one with a NaN/inf value
    """
    if system not in ("1992", "2000"):
        raise ValidationError(
            f"Nieobsługiwany system godeł: {system!r}. Dozwolone: '1992', '2000'"
        )

    validate_bbox(bbox)

    if system == "2000":
        from kartograf.core.parser_2000 import find_sheets_2000_for_bbox

        return find_sheets_2000_for_bbox(bbox, target_scale)

    if target_scale not in SheetParser.SCALE_HIERARCHY:
        raise ValidationError(
            f"Nieprawidłowa skala: '{target_scale}'. "
            f"Dozwolone: {', '.join(SheetParser.SCALE_HIERARCHY)}"
        )

    if bbox.crs not in ("EPSG:2180", "EPSG:4326"):
        raise ValidationError(
            f"Nieobsługiwany CRS: '{bbox.crs}'. Obsługiwane: EPSG:2180, EPSG:4326"
        )

    # Normalize to WGS84. Densified envelope (core.bbox): in PUWG 1992 a line of
    # constant y has its maximum latitude on the central meridian (x = 500 000 m, 19E),
    # so 4 corners missed the strip at the upper edge (2026-09-28).
    wgs_bbox = transform_bbox(bbox, "EPSG:4326")
    # Point/hairline: expand by eps on the MAX side to give exactly one sheet
    wgs_bbox = _expand_degenerate(wgs_bbox, _DEGENERATE_EPS_DEG)

    target_idx = SheetParser.SCALE_HIERARCHY.index(target_scale)

    # --- Step 1: Find the 1:1M sheets ---
    sheets_1m = _find_1m_sheets(wgs_bbox)

    if target_idx == 0:  # 1:1000000
        return sorted(sheets_1m)

    # --- Step 2: Find the 1:500k sheets ---
    if target_idx == 1:  # 1:500000
        result = []
        for godlo_1m in sheets_1m:
            result.extend(_find_children_intersecting(godlo_1m, wgs_bbox))
        return sorted(result)

    # --- Step 3: Find the 1:200k sheets (optimized) ---
    sheets_200k = []
    for godlo_1m in sheets_1m:
        sheets_200k.extend(_find_200k_sheets(godlo_1m, wgs_bbox))

    if target_idx == 2:  # 1:200000
        return sorted(sheets_200k)

    # --- Step 4: Drill down recursively to the target scale ---
    current_sheets = sheets_200k
    current_scale_idx = 2  # 1:200000

    while current_scale_idx < target_idx:
        next_sheets = []
        for godlo in current_sheets:
            next_sheets.extend(_find_children_intersecting(godlo, wgs_bbox))
        current_sheets = next_sheets
        current_scale_idx += 1

    return sorted(current_sheets)


def _find_1m_sheets(wgs_bbox: BBox) -> list[str]:
    """
    Find the 1:1M sheets intersecting the bbox (WGS84).

    Parameters
    ----------
    wgs_bbox : BBox
        Bbox in EPSG:4326 (min_x=west, min_y=south, max_x=east, max_y=north)

    Returns
    -------
    list[str]
        1:1M sheet codes within the PL-1992 nomenclature range (bands M/N,
        columns 33-35)
    """
    south, north = wgs_bbox.min_y, wgs_bbox.max_y
    west, east = wgs_bbox.min_x, wgs_bbox.max_x

    # Band: row = floor(lat / 4), letter = chr(ord('A') + row)
    min_row = max(0, math.floor(south / 4.0))
    max_row = max(0, math.floor((north - 1e-10) / 4.0))
    # If north is exactly on a boundary (e.g. 56.0), it belongs to the band below
    if north == math.floor(north / 4.0) * 4.0 and north > south:
        max_row = max(0, int(north / 4.0) - 1)

    # Column: slup = floor(lon / 6) + 31
    min_slup = math.floor(west / 6.0) + 31
    max_slup = math.floor((east - 1e-10) / 6.0) + 31
    if east == math.floor(east / 6.0) * 6.0 and east > west:
        max_slup = int(east / 6.0) + 31 - 1

    result = []
    for row in range(min_row, max_row + 1):
        pas = chr(ord("A") + row)
        if pas not in SheetParser.VALID_BANDS:
            continue  # A7: outside the PL-1992 nomenclature - no sheets there
        for slup in range(min_slup, max_slup + 1):
            if slup in SheetParser.VALID_COLUMNS:
                result.append(f"{pas}-{slup}")

    return result


def _find_200k_sheets(godlo_1m: str, wgs_bbox: BBox) -> list[str]:
    """
    Find the 1:200k sheets within a 1:1M sheet that intersect the bbox.

    Optimization: mathematically computes the row/column range in the 12x12 grid.

    Parameters
    ----------
    godlo_1m : str
        Sheet code of the 1:1M sheet (e.g. "N-34")
    wgs_bbox : BBox
        Bbox in EPSG:4326

    Returns
    -------
    list[str]
        List of 1:200k sheet codes
    """
    parser_1m = SheetParser(godlo_1m)
    bbox_1m = parser_1m.get_bbox(crs="EPSG:4326")

    north_1m = bbox_1m.max_y
    south_1m = bbox_1m.min_y
    west_1m = bbox_1m.min_x
    east_1m = bbox_1m.max_x

    height_200k = (north_1m - south_1m) / 12.0
    width_200k = (east_1m - west_1m) / 12.0

    # Compute the row range (from the top)
    min_row = max(0, math.floor((north_1m - wgs_bbox.max_y) / height_200k))
    max_row = min(11, math.floor((north_1m - wgs_bbox.min_y - 1e-10) / height_200k))

    # Compute the column range (from the left)
    min_col = max(0, math.floor((wgs_bbox.min_x - west_1m) / width_200k))
    max_col = min(11, math.floor((wgs_bbox.max_x - west_1m - 1e-10) / width_200k))

    # Clamp ranges
    min_row = max(0, min(11, min_row))
    max_row = max(0, min(11, max_row))
    min_col = max(0, min(11, min_col))
    max_col = max(0, min(11, max_col))

    pas = godlo_1m.split("-")[0]
    slup = godlo_1m.split("-")[1]

    result = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            arkusz_num = row * 12 + col + 1
            godlo = f"{pas}-{slup}-{arkusz_num}"
            # Verify the intersection (in case of edge cases)
            sp = SheetParser(godlo)
            sb = sp.get_bbox(crs="EPSG:4326")
            if _bboxes_intersect(wgs_bbox, sb):
                result.append(godlo)

    return result


def _find_children_intersecting(godlo: str, wgs_bbox: BBox) -> list[str]:
    """
    Find the children of a sheet that intersect the bbox.

    Parameters
    ----------
    godlo : str
        Sheet code of the parent sheet
    wgs_bbox : BBox
        Bbox in EPSG:4326

    Returns
    -------
    list[str]
        List of sheet codes of children intersecting the bbox
    """
    parser = SheetParser(godlo)
    children = parser.get_children()

    result = []
    for child in children:
        child_bbox = child.get_bbox(crs="EPSG:4326")
        if _bboxes_intersect(wgs_bbox, child_bbox):
            result.append(child.godlo)

    return result
