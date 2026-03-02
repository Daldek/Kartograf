# PL-2000 Sheet Naming System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add full PL-2000 godlo support (parsing, BBox, hierarchy, download, CLI) with auto-detection alongside existing PL-1992.

**Architecture:** Composition pattern — SheetParser remains the public facade API. PL-2000 logic lives in a new `_Parser2000` class (`parser_2000.py`). SheetParser auto-detects format (dots=PL-2000, dashes=PL-1992) and delegates to `_Parser2000` when needed, keeping PL-1992 logic in place internally. This avoids risky extraction of working PL-1992 code while achieving clean separation.

**Tech Stack:** Python 3.12+, pyproj (CRS transforms), pytest (TDD)

**Design doc:** `docs/plans/2026-02-24-pl2000-support-design.md`

**Delegation model:** Tasks 1-6 are delegated to subagents. Main agent supervises, reviews, and approves.

---

## Key Reference: PL-2000 System

**Godlo format:** `zone.row.column[.subdivisions]` (dot-separated numbers)

**Coordinate formulas (1:10k base):**
```python
X_nw = row * 5000 + 4_920_000       # Northing (m)
Y_nw = column * 8000 + 332_000      # Easting within zone (m)
Y_full = zone * 1_000_000 + Y_nw    # Full Easting with zone prefix
```

**Zone → EPSG:** `{5: "EPSG:2176", 6: "EPSG:2177", 7: "EPSG:2178", 8: "EPSG:2179"}`

**Scales & dimensions (NS × EW in meters):**
- 1:10000 = 5000 × 8000 (base: `z.rrr.cc`)
- 1:5000 = 2500 × 4000 (2×2: `z.rrr.cc.n`, n=1-4)
- 1:2000 = 1000 × 1600 (5×5: `z.rrr.cc.nn`, nn=01-25)
- 1:1000 = 500 × 800 (2×2: `z.rrr.cc.nn.n`)
- 1:500 = 250 × 400 (2×2: `z.rrr.cc.nn.n.n`)

**Subdivision numbering (2×2):** 1=NW, 2=NE, 3=SW, 4=SE
**Subdivision numbering (5×5):** 01-25, row-major from NW

---

## Task 1: _Parser2000 — Parsing, Validation & BBox

**Files:**
- Create: `kartograf/core/parser_2000.py`
- Create: `tests/test_parser_2000.py`
- Reference: `kartograf/exceptions.py` (ParseError, ValidationError)
- Reference: `kartograf/core/sheet_parser.py:18-25` (BBox class)

**Depends on:** Nothing (fully independent)

### Step 1: Write failing tests for parsing & validation

Create `tests/test_parser_2000.py` with tests covering:

```python
"""Tests for PL-2000 sheet parser."""

import pytest

from kartograf.core.parser_2000 import Parser2000
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError


class TestParser2000Basic:
    """Basic parsing across all scales."""

    def test_parse_10k(self):
        p = Parser2000("6.179.12")
        assert p.godlo == "6.179.12"
        assert p.scale == "1:10000"
        assert p.uklad == "2000"
        assert p.components == {"strefa": "6", "pas": "179", "slup": "12"}

    def test_parse_5k(self):
        p = Parser2000("6.179.12.3")
        assert p.godlo == "6.179.12.3"
        assert p.scale == "1:5000"
        assert p.components["ark_5k"] == "3"

    def test_parse_2k(self):
        p = Parser2000("6.179.12.20")
        assert p.godlo == "6.179.12.20"
        assert p.scale == "1:2000"
        assert p.components["ark_2k"] == "20"

    def test_parse_2k_leading_zero(self):
        p = Parser2000("6.179.12.01")
        assert p.godlo == "6.179.12.01"
        assert p.scale == "1:2000"
        assert p.components["ark_2k"] == "01"

    def test_parse_1k(self):
        p = Parser2000("6.179.12.20.2")
        assert p.godlo == "6.179.12.20.2"
        assert p.scale == "1:1000"

    def test_parse_500(self):
        p = Parser2000("6.179.12.20.2.1")
        assert p.godlo == "6.179.12.20.2.1"
        assert p.scale == "1:500"

    def test_all_zones(self):
        for zone in [5, 6, 7, 8]:
            p = Parser2000(f"{zone}.100.10")
            assert p.components["strefa"] == str(zone)


class TestParser2000Validation:
    """Validation and error handling."""

    def test_invalid_zone(self):
        with pytest.raises(ParseError):
            Parser2000("3.179.12")

    def test_invalid_zone_9(self):
        with pytest.raises(ParseError):
            Parser2000("9.179.12")

    def test_invalid_ark_2k_zero(self):
        with pytest.raises(ValidationError):
            Parser2000("6.179.12.00")

    def test_invalid_ark_2k_26(self):
        with pytest.raises(ValidationError):
            Parser2000("6.179.12.26")

    def test_invalid_quadrant_zero(self):
        with pytest.raises(ParseError):
            Parser2000("6.179.12.0")

    def test_invalid_quadrant_5(self):
        with pytest.raises(ParseError):
            Parser2000("6.179.12.5")

    def test_empty_string(self):
        with pytest.raises(ParseError):
            Parser2000("")

    def test_not_string(self):
        with pytest.raises(ParseError):
            Parser2000(123)

    def test_pl1992_format_rejected(self):
        with pytest.raises(ParseError):
            Parser2000("N-34-130-D")


class TestParser2000Normalization:
    """Whitespace and format normalization."""

    def test_strip_whitespace(self):
        p = Parser2000("  6.179.12  ")
        assert p.godlo == "6.179.12"

    def test_single_digit_pas(self):
        p = Parser2000("6.1.1")
        assert p.components["pas"] == "1"

    def test_single_digit_slup(self):
        p = Parser2000("6.179.1")
        assert p.components["slup"] == "1"


class TestParser2000Equality:
    """Equality and hashing."""

    def test_equal(self):
        a = Parser2000("6.179.12")
        b = Parser2000("6.179.12")
        assert a == b

    def test_not_equal(self):
        a = Parser2000("6.179.12")
        b = Parser2000("6.179.13")
        assert a != b

    def test_hash_equal(self):
        a = Parser2000("6.179.12")
        b = Parser2000("6.179.12")
        assert hash(a) == hash(b)

    def test_repr(self):
        p = Parser2000("6.179.12")
        assert "6.179.12" in repr(p)
        assert "1:10000" in repr(p)
```

### Step 2: Run tests — verify they fail

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py -v
```
Expected: ImportError (module doesn't exist yet)

### Step 3: Implement Parser2000 — parsing, validation, normalization

Create `kartograf/core/parser_2000.py`:

```python
"""
Parser godel map w ukladzie PL-2000.

Format godla: zone.row.column[.subdivisions]
Przyklad: 6.179.12, 6.179.12.20, 6.179.12.20.2.1

Strefy merydianowe:
    5 (EPSG:2176, 15E), 6 (EPSG:2177, 18E),
    7 (EPSG:2178, 21E), 8 (EPSG:2179, 24E)
"""

import re

from pyproj import Transformer

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError

# Zone -> EPSG mapping
ZONE_EPSG = {
    5: "EPSG:2176",
    6: "EPSG:2177",
    7: "EPSG:2178",
    8: "EPSG:2179",
}

# Regex patterns per scale
PATTERNS_2000 = {
    "1:10000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})$",
    "1:5000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.([1-4])$",
    "1:2000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})$",
    "1:1000": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])$",
    "1:500": r"^([5-8])\.(\d{1,3})\.(\d{1,2})\.(\d{2})\.([1-4])\.([1-4])$",
}

SCALE_HIERARCHY_2000 = [
    "1:10000",
    "1:5000",
    "1:2000",
    "1:1000",
    "1:500",
]

COMPONENT_NAMES_2000 = [
    "strefa",
    "pas",
    "slup",
    "ark_5k",  # or ark_2k depending on scale
    "ark_1k",
    "ark_500",
]

# Sheet dimensions in meters (NS x EW)
SHEET_DIMENSIONS_2000 = {
    "1:10000": (5000, 8000),
    "1:5000": (2500, 4000),
    "1:2000": (1000, 1600),
    "1:1000": (500, 800),
    "1:500": (250, 400),
}

# Quadrant positions for 2x2 grids (1=NW, 2=NE, 3=SW, 4=SE)
_QUADRANT_2X2 = {
    "1": (0, 0),
    "2": (0, 1),
    "3": (1, 0),
    "4": (1, 1),
}


class Parser2000:
    """Parser godel map w ukladzie PL-2000."""

    def __init__(self, godlo: str):
        if not isinstance(godlo, str):
            raise ParseError(
                f"Godlo musi byc stringiem, otrzymano: {type(godlo)}"
            )

        self._original = godlo.strip()
        if not self._original:
            raise ParseError("Godlo nie moze byc puste")

        self._godlo = self._original
        self._scale = self._determine_scale()
        self._components = self._parse_components()
        self._validate_components()

    def _determine_scale(self) -> str:
        for scale, pattern in PATTERNS_2000.items():
            if re.match(pattern, self._godlo):
                return scale
        raise ParseError(
            f"Nieprawidlowe godlo PL-2000: '{self._original}'. "
            f"Oczekiwany format: strefa.pas.slup[.podzialy] (np. 6.179.12)"
        )

    def _parse_components(self) -> dict[str, str]:
        pattern = PATTERNS_2000[self._scale]
        match = re.match(pattern, self._godlo)
        if not match:
            raise ParseError(f"Blad parsowania godla: {self._godlo}")

        groups = match.groups()
        components = {
            "strefa": groups[0],
            "pas": groups[1],
            "slup": groups[2],
        }

        if self._scale == "1:5000":
            components["ark_5k"] = groups[3]
        elif self._scale == "1:2000":
            components["ark_2k"] = groups[3]
        elif self._scale == "1:1000":
            components["ark_2k"] = groups[3]
            components["ark_1k"] = groups[4]
        elif self._scale == "1:500":
            components["ark_2k"] = groups[3]
            components["ark_1k"] = groups[4]
            components["ark_500"] = groups[5]

        return components

    def _validate_components(self) -> None:
        if "ark_2k" in self._components:
            val = int(self._components["ark_2k"])
            if val < 1 or val > 25:
                raise ValidationError(
                    f"Numer arkusza 1:2000 poza zakresem 01-25: "
                    f"'{self._components['ark_2k']}'"
                )

    @property
    def godlo(self) -> str:
        return self._godlo

    @property
    def scale(self) -> str:
        return self._scale

    @property
    def uklad(self) -> str:
        return "2000"

    @property
    def components(self) -> dict[str, str]:
        return dict(self._components)

    @property
    def zone(self) -> int:
        return int(self._components["strefa"])

    @property
    def native_crs(self) -> str:
        return ZONE_EPSG[self.zone]

    def __repr__(self) -> str:
        return f"Parser2000(godlo='{self._godlo}', scale='{self._scale}')"

    def __str__(self) -> str:
        return f"{self._godlo} ({self._scale}, uklad 2000, strefa {self.zone})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Parser2000):
            return NotImplemented
        return self._godlo == other._godlo

    def __hash__(self) -> int:
        return hash(("2000", self._godlo))
```

### Step 4: Run parsing tests — verify they pass

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py -v
```
Expected: All tests PASS

### Step 5: Write failing BBox tests

Add to `tests/test_parser_2000.py`:

```python
class TestParser2000BBox:
    """BBox calculation tests."""

    def test_bbox_10k_native_crs(self):
        """6.179.12 -> zone 6, EPSG:2177."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        # X_nw = 179*5000 + 4920000 = 5815000 (Northing / south boundary)
        # Y_nw = 6*1000000 + 12*8000 + 332000 = 6428000 (Easting / west boundary)
        assert bbox.crs == "EPSG:2177"
        assert bbox.min_x == pytest.approx(6428000)    # west (Easting)
        assert bbox.max_x == pytest.approx(6436000)    # east
        assert bbox.min_y == pytest.approx(5815000)    # south (Northing)
        assert bbox.max_y == pytest.approx(5820000)    # north

    def test_bbox_10k_zone_5(self):
        p = Parser2000("5.100.10")
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2176"
        assert bbox.min_x == pytest.approx(5412000)    # 5*1e6 + 10*8000 + 332000
        assert bbox.min_y == pytest.approx(5420000)    # 100*5000 + 4920000

    def test_bbox_5k_subdivision(self):
        """1:5k quad 1 (NW) of 6.179.12."""
        p = Parser2000("6.179.12.1")
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2177"
        # NW quadrant: same west/north as parent, half dimensions
        assert bbox.min_x == pytest.approx(6428000)
        assert bbox.max_x == pytest.approx(6432000)    # +4000
        assert bbox.min_y == pytest.approx(5817500)    # north - 2500
        assert bbox.max_y == pytest.approx(5820000)

    def test_bbox_5k_quad_4_se(self):
        """1:5k quad 4 (SE) of 6.179.12."""
        p = Parser2000("6.179.12.4")
        bbox = p.get_bbox()
        assert bbox.min_x == pytest.approx(6432000)
        assert bbox.max_x == pytest.approx(6436000)
        assert bbox.min_y == pytest.approx(5815000)
        assert bbox.max_y == pytest.approx(5817500)

    def test_bbox_2k_subdivision(self):
        """1:2k sheet 01 (top-left) of 6.179.12."""
        p = Parser2000("6.179.12.01")
        bbox = p.get_bbox()
        # 5x5 grid: row=0, col=0 => NW corner
        assert bbox.min_x == pytest.approx(6428000)
        assert bbox.max_x == pytest.approx(6429600)    # +1600
        assert bbox.min_y == pytest.approx(5819000)    # north - 1000
        assert bbox.max_y == pytest.approx(5820000)

    def test_bbox_2k_sheet_25(self):
        """1:2k sheet 25 (bottom-right) of 6.179.12."""
        p = Parser2000("6.179.12.25")
        bbox = p.get_bbox()
        # row=4, col=4 => SE corner
        assert bbox.min_x == pytest.approx(6434400)    # west + 4*1600
        assert bbox.max_x == pytest.approx(6436000)
        assert bbox.min_y == pytest.approx(5815000)
        assert bbox.max_y == pytest.approx(5816000)

    def test_bbox_1k(self):
        """1:1k quad 1 (NW) of sheet 6.179.12.01."""
        p = Parser2000("6.179.12.01.1")
        bbox = p.get_bbox()
        assert bbox.max_x - bbox.min_x == pytest.approx(800)
        assert bbox.max_y - bbox.min_y == pytest.approx(500)

    def test_bbox_500(self):
        """1:500 quad 1 (NW) of 6.179.12.01.1."""
        p = Parser2000("6.179.12.01.1.1")
        bbox = p.get_bbox()
        assert bbox.max_x - bbox.min_x == pytest.approx(400)
        assert bbox.max_y - bbox.min_y == pytest.approx(250)

    def test_bbox_wgs84(self):
        """Transform to WGS84."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:4326")
        assert bbox.crs == "EPSG:4326"
        # Poland is roughly 49-55N, 14-24E
        assert 49 < bbox.min_y < 55
        assert 14 < bbox.min_x < 24

    def test_bbox_epsg2180(self):
        """Transform to PL-1992."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:2180")
        assert bbox.crs == "EPSG:2180"
        # EPSG:2180 coords for Poland: X ~140000-900000, Y ~100000-800000
        assert 100000 < bbox.min_x < 900000

    def test_bbox_invalid_crs(self):
        p = Parser2000("6.179.12")
        with pytest.raises(ValidationError):
            p.get_bbox(crs="EPSG:9999")

    def test_child_bbox_inside_parent(self):
        """All child bboxes must be inside parent."""
        parent = Parser2000("6.179.12")
        pb = parent.get_bbox()
        for i in range(1, 5):
            child = Parser2000(f"6.179.12.{i}")
            cb = child.get_bbox()
            assert cb.min_x >= pb.min_x - 0.01
            assert cb.max_x <= pb.max_x + 0.01
            assert cb.min_y >= pb.min_y - 0.01
            assert cb.max_y <= pb.max_y + 0.01
```

### Step 6: Run BBox tests — verify they fail

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py::TestParser2000BBox -v
```
Expected: AttributeError (get_bbox not implemented)

### Step 7: Implement get_bbox in Parser2000

Add to `kartograf/core/parser_2000.py`, in the `Parser2000` class:

```python
    def get_bbox(self, crs: str | None = None) -> BBox:
        """
        Oblicza bounding box arkusza.

        Parameters
        ----------
        crs : str, optional
            Uklad CRS wyniku. Domyslnie natywny CRS strefy (EPSG:2176-2179).
            Obslugiwane: EPSG:2176-2179, EPSG:2180, EPSG:4326.
        """
        if crs is None:
            crs = self.native_crs

        valid_crs = {"EPSG:2176", "EPSG:2177", "EPSG:2178", "EPSG:2179",
                     "EPSG:2180", "EPSG:4326"}
        if crs not in valid_crs:
            raise ValidationError(
                f"Nieobslugiwany CRS: '{crs}'. "
                f"Dozwolone: {', '.join(sorted(valid_crs))}"
            )

        zone = self.zone
        pas = int(self._components["pas"])
        slup = int(self._components["slup"])

        # Base 1:10k bbox (Northing = Y-axis, Easting = X-axis)
        south = pas * 5000 + 4_920_000
        north = south + 5000
        west = zone * 1_000_000 + slup * 8000 + 332_000
        east = west + 8000

        # Apply subdivisions
        if "ark_5k" in self._components:
            row, col = _QUADRANT_2X2[self._components["ark_5k"]]
            north = north - row * 2500
            south = north - 2500
            west = west + col * 4000
            east = west + 4000
        elif "ark_2k" in self._components:
            ark_idx = int(self._components["ark_2k"]) - 1
            row_5, col_5 = divmod(ark_idx, 5)
            north = north - row_5 * 1000
            south = north - 1000
            west = west + col_5 * 1600
            east = west + 1600

            if "ark_1k" in self._components:
                row, col = _QUADRANT_2X2[self._components["ark_1k"]]
                north = north - row * 500
                south = north - 500
                west = west + col * 800
                east = west + 800

                if "ark_500" in self._components:
                    row, col = _QUADRANT_2X2[self._components["ark_500"]]
                    north = north - row * 250
                    south = north - 250
                    west = west + col * 400
                    east = west + 400

        native_bbox = BBox(
            min_x=west, min_y=south, max_x=east, max_y=north,
            crs=self.native_crs
        )

        if crs == self.native_crs:
            return native_bbox

        return self._transform_bbox(native_bbox, crs)

    @staticmethod
    def _transform_bbox(bbox: BBox, target_crs: str) -> BBox:
        """Transform BBox to target CRS."""
        transformer = Transformer.from_crs(
            bbox.crs, target_crs, always_xy=True
        )
        # Transform all 4 corners for accuracy
        xs = [bbox.min_x, bbox.max_x, bbox.min_x, bbox.max_x]
        ys = [bbox.min_y, bbox.min_y, bbox.max_y, bbox.max_y]
        tx, ty = transformer.transform(xs, ys)
        return BBox(
            min_x=min(tx), min_y=min(ty),
            max_x=max(tx), max_y=max(ty),
            crs=target_crs
        )
```

### Step 8: Run all tests — verify they pass

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py -v
```
Expected: All PASS

### Step 9: Verify existing tests still pass

```bash
.venv/bin/python -m pytest tests/test_sheet_parser.py -v
```
Expected: All 107 PASS (no regressions)

### Step 10: Commit

```bash
git add kartograf/core/parser_2000.py tests/test_parser_2000.py
git commit -m "feat(parser): add Parser2000 — parsing, validation, BBox for PL-2000"
```

---

## Task 2: _Parser2000 — Hierarchy Methods

**Files:**
- Modify: `kartograf/core/parser_2000.py`
- Modify: `tests/test_parser_2000.py`

**Depends on:** Task 1

### Step 1: Write failing hierarchy tests

Add to `tests/test_parser_2000.py`:

```python
class TestParser2000Hierarchy:
    """Hierarchy: parent, children, descendants."""

    # --- get_parent ---

    def test_parent_of_500(self):
        p = Parser2000("6.179.12.01.1.1")
        parent = p.get_parent()
        assert parent.godlo == "6.179.12.01.1"
        assert parent.scale == "1:1000"

    def test_parent_of_1k(self):
        p = Parser2000("6.179.12.01.1")
        parent = p.get_parent()
        assert parent.godlo == "6.179.12.01"
        assert parent.scale == "1:2000"

    def test_parent_of_2k(self):
        p = Parser2000("6.179.12.01")
        parent = p.get_parent()
        assert parent.godlo == "6.179.12"
        assert parent.scale == "1:10000"

    def test_parent_of_5k(self):
        p = Parser2000("6.179.12.3")
        parent = p.get_parent()
        assert parent.godlo == "6.179.12"
        assert parent.scale == "1:10000"

    def test_parent_of_10k_is_none(self):
        p = Parser2000("6.179.12")
        assert p.get_parent() is None

    # --- get_children ---

    def test_children_of_10k_5k(self):
        """10k -> 4 children at 5k (2x2)."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:5000")
        assert len(children) == 4
        assert children[0].godlo == "6.179.12.1"
        assert children[3].godlo == "6.179.12.4"

    def test_children_of_10k_2k(self):
        """10k -> 25 children at 2k (5x5)."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:2000")
        assert len(children) == 25
        assert children[0].godlo == "6.179.12.01"
        assert children[24].godlo == "6.179.12.25"

    def test_children_of_2k(self):
        """2k -> 4 children at 1k."""
        p = Parser2000("6.179.12.01")
        children = p.get_children()
        assert len(children) == 4

    def test_children_of_1k(self):
        """1k -> 4 children at 500."""
        p = Parser2000("6.179.12.01.1")
        children = p.get_children()
        assert len(children) == 4

    def test_children_of_500_empty(self):
        """500 has no children."""
        p = Parser2000("6.179.12.01.1.1")
        assert p.get_children() == []

    def test_children_of_5k_empty(self):
        """5k has no children (leaf in 5k branch)."""
        p = Parser2000("6.179.12.3")
        assert p.get_children() == []

    # --- get_all_descendants ---

    def test_descendants_10k_to_2k(self):
        p = Parser2000("6.179.12")
        desc = p.get_all_descendants("1:2000")
        assert len(desc) == 25

    def test_descendants_2k_to_500(self):
        p = Parser2000("6.179.12.01")
        desc = p.get_all_descendants("1:500")
        # 4 * 4 = 16
        assert len(desc) == 16

    def test_descendants_10k_to_500(self):
        p = Parser2000("6.179.12")
        desc = p.get_all_descendants("1:500")
        # 25 * 4 * 4 = 400
        assert len(desc) == 400

    def test_descendants_same_scale_returns_self(self):
        p = Parser2000("6.179.12")
        desc = p.get_all_descendants("1:10000")
        assert len(desc) == 1
        assert desc[0].godlo == "6.179.12"

    def test_descendants_coarser_scale_raises(self):
        p = Parser2000("6.179.12.01")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:10000")

    # --- get_hierarchy_up ---

    def test_hierarchy_up_from_500(self):
        p = Parser2000("6.179.12.01.1.1")
        hierarchy = p.get_hierarchy_up()
        assert len(hierarchy) == 4
        assert hierarchy[0].godlo == "6.179.12.01.1.1"
        assert hierarchy[1].godlo == "6.179.12.01.1"
        assert hierarchy[2].godlo == "6.179.12.01"
        assert hierarchy[3].godlo == "6.179.12"

    def test_hierarchy_up_from_10k(self):
        p = Parser2000("6.179.12")
        hierarchy = p.get_hierarchy_up()
        assert len(hierarchy) == 1
        assert hierarchy[0].godlo == "6.179.12"
```

### Step 2: Run hierarchy tests — verify they fail

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py::TestParser2000Hierarchy -v
```
Expected: AttributeError

### Step 3: Implement hierarchy methods

Add to `Parser2000` class in `kartograf/core/parser_2000.py`:

```python
    def get_parent(self) -> "Parser2000 | None":
        """Return parent sheet at coarser scale, or None for 1:10000."""
        if self._scale == "1:10000":
            return None

        parts = self._godlo.split(".")
        # Remove last component to get parent
        if self._scale in ("1:5000", "1:2000"):
            parent_godlo = ".".join(parts[:3])  # z.rrr.cc
        elif self._scale == "1:1000":
            parent_godlo = ".".join(parts[:4])  # z.rrr.cc.nn
        elif self._scale == "1:500":
            parent_godlo = ".".join(parts[:5])  # z.rrr.cc.nn.n

        return Parser2000(parent_godlo)

    def get_children(self, scale: str | None = None) -> list["Parser2000"]:
        """
        Return child sheets at next finer scale.

        For 1:10000, 'scale' must be specified: "1:5000" or "1:2000".
        For other scales, next finer scale is used automatically.
        """
        if self._scale == "1:500":
            return []
        if self._scale == "1:5000":
            return []  # 5k is leaf in its branch

        if self._scale == "1:10000":
            if scale is None:
                scale = "1:2000"  # default subdivision
            if scale == "1:5000":
                return [
                    Parser2000(f"{self._godlo}.{i}") for i in range(1, 5)
                ]
            elif scale == "1:2000":
                return [
                    Parser2000(f"{self._godlo}.{i:02d}")
                    for i in range(1, 26)
                ]
            else:
                raise ValidationError(
                    f"Nieprawidlowa skala potomna dla 1:10000: '{scale}'. "
                    f"Dozwolone: 1:5000, 1:2000"
                )

        # 1:2000 -> 1:1000, 1:1000 -> 1:500
        return [Parser2000(f"{self._godlo}.{i}") for i in range(1, 5)]

    def get_all_descendants(self, target_scale: str) -> list["Parser2000"]:
        """Return all descendants at target scale."""
        scale_order = {s: i for i, s in enumerate(SCALE_HIERARCHY_2000)}

        if target_scale not in scale_order:
            raise ValidationError(
                f"Nieobslugiwana skala: '{target_scale}'. "
                f"Dozwolone: {', '.join(SCALE_HIERARCHY_2000)}"
            )

        current_idx = scale_order.get(self._scale)
        target_idx = scale_order.get(target_scale)

        if current_idx is None:
            raise ValidationError(f"Nieznana skala: '{self._scale}'")

        if target_idx < current_idx:
            raise ValidationError(
                f"Skala docelowa '{target_scale}' jest grubsza niz "
                f"biezaca '{self._scale}'"
            )

        if target_idx == current_idx:
            return [Parser2000(self._godlo)]

        # For 1:10k, decide 5k vs 2k branch based on target
        if self._scale == "1:10000" and target_scale == "1:5000":
            return self.get_children(scale="1:5000")

        # For 2k branch: 10k -> 2k -> 1k -> 500
        results = [self]
        while results and results[0].scale != target_scale:
            next_level = []
            for sheet in results:
                if sheet.scale == "1:10000":
                    next_level.extend(sheet.get_children(scale="1:2000"))
                else:
                    next_level.extend(sheet.get_children())
            results = next_level

        return sorted(results, key=lambda p: p.godlo)

    def get_hierarchy_up(self) -> list["Parser2000"]:
        """Return chain from current sheet up to 1:10000."""
        hierarchy = [self]
        current = self
        while True:
            parent = current.get_parent()
            if parent is None:
                break
            hierarchy.append(parent)
            current = parent
        return hierarchy
```

### Step 4: Run all tests — verify they pass

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py -v
```
Expected: All PASS

### Step 5: Run full test suite

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: All 636+ tests PASS

### Step 6: Commit

```bash
git add kartograf/core/parser_2000.py tests/test_parser_2000.py
git commit -m "feat(parser): add Parser2000 hierarchy — parent, children, descendants"
```

---

## Task 3: find_sheets_2000_for_bbox

**Files:**
- Modify: `kartograf/core/parser_2000.py`
- Modify: `tests/test_parser_2000.py`

**Depends on:** Task 2

### Step 1: Write failing tests

Add to `tests/test_parser_2000.py`:

```python
from kartograf.core.parser_2000 import Parser2000, find_sheets_2000_for_bbox


class TestFindSheets2000ForBBox:
    """BBox -> PL-2000 godla lookup."""

    def test_single_10k_sheet(self):
        """BBox inside one 1:10k sheet."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        # Shrink slightly to be strictly inside
        inner = BBox(
            bbox.min_x + 100, bbox.min_y + 100,
            bbox.max_x - 100, bbox.max_y - 100,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(inner, target_scale="1:10000")
        assert result == ["6.179.12"]

    def test_multiple_10k_sheets(self):
        """BBox spanning 2 sheets horizontally."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        wide = BBox(
            bbox.min_x - 100, bbox.min_y + 100,
            bbox.max_x + 100, bbox.max_y - 100,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(wide, target_scale="1:10000")
        assert len(result) >= 2
        assert "6.179.12" in result

    def test_target_2k(self):
        """Drill down to 1:2000."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        inner = BBox(
            bbox.min_x + 100, bbox.min_y + 100,
            bbox.max_x - 100, bbox.max_y - 100,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(inner, target_scale="1:2000")
        assert len(result) == 25  # full sheet

    def test_small_bbox_fewer_2k_sheets(self):
        """Small BBox should hit fewer 1:2k sheets."""
        p = Parser2000("6.179.12.01")
        bbox = p.get_bbox()
        inner = BBox(
            bbox.min_x + 10, bbox.min_y + 10,
            bbox.max_x - 10, bbox.max_y - 10,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(inner, target_scale="1:2000")
        assert "6.179.12.01" in result
        assert len(result) <= 4  # at most a few neighbors

    def test_wgs84_bbox(self):
        """Accept WGS84 bbox, auto-detect zone."""
        bbox = BBox(17.0, 52.0, 17.1, 52.1, "EPSG:4326")
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:10000")
        assert len(result) > 0
        # Zone 6 (meridian 18E covers ~16.5-19.5E)
        assert all(g.startswith("6.") for g in result)

    def test_epsg2180_bbox(self):
        """Accept PL-1992 bbox."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:10000")
        assert len(result) > 0

    def test_roundtrip_10k(self):
        """get_bbox -> find_sheets -> should find original sheet."""
        p = Parser2000("7.181.15")
        bbox = p.get_bbox()
        inner = BBox(
            bbox.min_x + 1, bbox.min_y + 1,
            bbox.max_x - 1, bbox.max_y - 1,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(inner, target_scale="1:10000")
        assert "7.181.15" in result

    def test_zone_parameter(self):
        """Explicit zone limits results."""
        bbox = BBox(17.0, 52.0, 17.1, 52.1, "EPSG:4326")
        result = find_sheets_2000_for_bbox(
            bbox, target_scale="1:10000", zone=6
        )
        assert all(g.startswith("6.") for g in result)

    def test_sorted_output(self):
        """Results must be sorted."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        wide = BBox(
            bbox.min_x - 5000, bbox.min_y - 5000,
            bbox.max_x + 5000, bbox.max_y + 5000,
            bbox.crs
        )
        result = find_sheets_2000_for_bbox(wide, target_scale="1:10000")
        assert result == sorted(result)
```

### Step 2: Verify tests fail

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py::TestFindSheets2000ForBBox -v
```

### Step 3: Implement find_sheets_2000_for_bbox

Add to `kartograf/core/parser_2000.py` (module-level function):

```python
def _determine_zones_for_bbox(bbox_wgs84: BBox) -> list[int]:
    """Determine which PL-2000 zones a WGS84 bbox intersects."""
    # Zone boundaries (approximate longitude ranges)
    zone_bounds = {
        5: (13.5, 16.5),
        6: (16.5, 19.5),
        7: (19.5, 22.5),
        8: (22.5, 25.5),
    }
    zones = []
    for z, (w, e) in zone_bounds.items():
        if bbox_wgs84.min_x < e and bbox_wgs84.max_x > w:
            zones.append(z)
    return zones


def _bbox_to_zone_coords(bbox: BBox, zone: int) -> BBox:
    """Transform bbox to zone-specific PL-2000 CRS."""
    target_crs = ZONE_EPSG[zone]
    if bbox.crs == target_crs:
        return bbox
    transformer = Transformer.from_crs(bbox.crs, target_crs, always_xy=True)
    xs = [bbox.min_x, bbox.max_x, bbox.min_x, bbox.max_x]
    ys = [bbox.min_y, bbox.min_y, bbox.max_y, bbox.max_y]
    tx, ty = transformer.transform(xs, ys)
    return BBox(min(tx), min(ty), max(tx), max(ty), target_crs)


def _bboxes_intersect(a: BBox, b: BBox) -> bool:
    """Check if two bboxes intersect (shared edge = intersect)."""
    return not (
        a.max_x < b.min_x or a.min_x > b.max_x
        or a.max_y < b.min_y or a.min_y > b.max_y
    )


def find_sheets_2000_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    zone: int | None = None,
) -> list[str]:
    """
    Find PL-2000 sheet godla covering a bounding box.

    Parameters
    ----------
    bbox : BBox
        Bounding box in any supported CRS.
    target_scale : str
        Target scale (1:10000, 1:2000, etc.)
    zone : int, optional
        Limit to specific zone (5-8). Auto-detected if None.
    """
    # Transform to WGS84 for zone detection
    if bbox.crs != "EPSG:4326":
        transformer = Transformer.from_crs(
            bbox.crs, "EPSG:4326", always_xy=True
        )
        xs = [bbox.min_x, bbox.max_x, bbox.min_x, bbox.max_x]
        ys = [bbox.min_y, bbox.min_y, bbox.max_y, bbox.max_y]
        tx, ty = transformer.transform(xs, ys)
        bbox_wgs84 = BBox(min(tx), min(ty), max(tx), max(ty), "EPSG:4326")
    else:
        bbox_wgs84 = bbox

    zones = [zone] if zone else _determine_zones_for_bbox(bbox_wgs84)
    all_godla: set[str] = set()

    for z in zones:
        zone_bbox = _bbox_to_zone_coords(bbox, z)
        zone_crs = ZONE_EPSG[z]

        # Calculate row/column range for 1:10k sheets
        min_row = int((zone_bbox.min_y - 4_920_000) / 5000)
        max_row = int((zone_bbox.max_y - 4_920_000) / 5000)
        y_offset = z * 1_000_000 + 332_000
        min_col = int((zone_bbox.min_x - y_offset) / 8000)
        max_col = int((zone_bbox.max_x - y_offset) / 8000)

        # Safety margins
        min_row = max(0, min_row - 1)
        max_row = max_row + 1
        min_col = max(0, min_col - 1)
        max_col = max_col + 1

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                godlo_10k = f"{z}.{row}.{col}"
                try:
                    p = Parser2000(godlo_10k)
                except (ParseError, ValidationError):
                    continue
                sheet_bbox = p.get_bbox()
                if _bboxes_intersect(zone_bbox, sheet_bbox):
                    if target_scale == "1:10000":
                        all_godla.add(godlo_10k)
                    else:
                        descendants = p.get_all_descendants(target_scale)
                        for d in descendants:
                            d_bbox = d.get_bbox()
                            if _bboxes_intersect(zone_bbox, d_bbox):
                                all_godla.add(d.godlo)

    return sorted(all_godla)
```

### Step 4: Run tests — verify they pass

```bash
.venv/bin/python -m pytest tests/test_parser_2000.py -v
```

### Step 5: Run full test suite

```bash
.venv/bin/python -m pytest tests/ -v
```

### Step 6: Commit

```bash
git add kartograf/core/parser_2000.py tests/test_parser_2000.py
git commit -m "feat(parser): add find_sheets_2000_for_bbox — BBox to PL-2000 lookup"
```

---

## Task 4: SheetParser Facade — Auto-Detection & Delegation

**Files:**
- Modify: `kartograf/core/sheet_parser.py` (lines 89-133, 174-225)
- Modify: `tests/test_sheet_parser.py`

**Depends on:** Tasks 1-3

### Step 1: Write failing auto-detection tests

Add to `tests/test_sheet_parser.py`:

```python
class TestSheetParserAutoDetection:
    """Auto-detection of PL-1992 vs PL-2000 format."""

    def test_pl1992_detected(self):
        p = SheetParser("N-34-130-D")
        assert p.uklad == "1992"

    def test_pl2000_detected(self):
        p = SheetParser("6.179.12")
        assert p.uklad == "2000"
        assert p.scale == "1:10000"

    def test_pl2000_2k(self):
        p = SheetParser("6.179.12.20")
        assert p.uklad == "2000"
        assert p.scale == "1:2000"

    def test_pl2000_5k(self):
        p = SheetParser("6.179.12.3")
        assert p.uklad == "2000"
        assert p.scale == "1:5000"

    def test_pl2000_500(self):
        p = SheetParser("6.179.12.01.1.1")
        assert p.uklad == "2000"
        assert p.scale == "1:500"

    def test_pl2000_bbox(self):
        p = SheetParser("6.179.12")
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2177"
        assert bbox.min_y == pytest.approx(5815000)

    def test_pl2000_parent(self):
        p = SheetParser("6.179.12.01")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12"
        assert isinstance(parent, SheetParser)

    def test_pl2000_children(self):
        p = SheetParser("6.179.12")
        children = p.get_children()
        assert len(children) == 25
        assert all(isinstance(c, SheetParser) for c in children)

    def test_pl2000_hierarchy_up(self):
        p = SheetParser("6.179.12.01.1")
        h = p.get_hierarchy_up()
        assert len(h) == 3
        assert all(isinstance(x, SheetParser) for x in h)

    def test_pl2000_descendants(self):
        p = SheetParser("6.179.12")
        desc = p.get_all_descendants("1:2000")
        assert len(desc) == 25
        assert all(isinstance(d, SheetParser) for d in desc)

    def test_explicit_uklad_2000_match(self):
        p = SheetParser("6.179.12", uklad="2000")
        assert p.uklad == "2000"

    def test_explicit_uklad_1992_conflict(self):
        with pytest.raises(ValidationError):
            SheetParser("6.179.12", uklad="1992")

    def test_explicit_uklad_2000_conflict(self):
        with pytest.raises(ValidationError):
            SheetParser("N-34-130-D", uklad="2000")

    def test_pl2000_components(self):
        p = SheetParser("6.179.12")
        c = p.components
        assert c["strefa"] == "6"
        assert c["pas"] == "179"
        assert c["slup"] == "12"

    def test_pl2000_equality(self):
        a = SheetParser("6.179.12")
        b = SheetParser("6.179.12")
        assert a == b
        assert hash(a) == hash(b)

    def test_pl2000_repr(self):
        p = SheetParser("6.179.12")
        assert "6.179.12" in repr(p)

    def test_pl2000_str(self):
        p = SheetParser("6.179.12")
        assert "2000" in str(p)
```

### Step 2: Verify tests fail

```bash
.venv/bin/python -m pytest tests/test_sheet_parser.py::TestSheetParserAutoDetection -v
```

### Step 3: Modify SheetParser for auto-detection

Modify `kartograf/core/sheet_parser.py`:

**At top of file (after existing imports, ~line 15), add:**
```python
from kartograf.core.parser_2000 import Parser2000
```

**Add detection function before SheetParser class (~line 17):**
```python
def _is_pl2000_format(godlo: str) -> bool:
    """Check if godlo uses PL-2000 dot-separated numeric format."""
    return bool(re.match(r"^[5-8]\.\d", godlo))
```

**Modify `SheetParser.__init__` (lines 91-133):**

Replace the current `__init__` body with:
```python
    def __init__(self, godlo: str, uklad: str | None = None):
        if not isinstance(godlo, str):
            raise ParseError(f"Godlo musi byc stringiem, otrzymano: {type(godlo)}")

        cleaned = godlo.strip()
        if not cleaned:
            raise ParseError("Godlo nie moze byc puste")

        # Auto-detect system
        if _is_pl2000_format(cleaned):
            if uklad is not None and uklad != "2000":
                raise ValidationError(
                    f"Godlo '{cleaned}' ma format PL-2000, "
                    f"ale podano uklad='{uklad}'"
                )
            self._pl2000 = Parser2000(cleaned)
            self._original_godlo = cleaned
            self._godlo = self._pl2000.godlo
            self._uklad = "2000"
            self._scale = self._pl2000.scale
            self._components = self._pl2000.components
        else:
            if uklad is not None and uklad == "2000":
                raise ValidationError(
                    f"Godlo '{cleaned}' ma format PL-1992, "
                    f"ale podano uklad='2000'"
                )
            self._pl2000 = None
            self._original_godlo = cleaned
            self._godlo = self._normalize_godlo(cleaned)
            self._uklad = self._validate_uklad(uklad)
            self._scale = self._determine_scale()
            self._components = self._parse_components()
```

**Modify `get_bbox` method (~line 549) to delegate for PL-2000:**

At the start of `get_bbox`, add:
```python
        if self._pl2000 is not None:
            return self._pl2000.get_bbox(crs=crs)
```

**Modify hierarchy methods to delegate for PL-2000:**

At start of `get_parent` (~line 305):
```python
        if self._pl2000 is not None:
            p = self._pl2000.get_parent()
            if p is None:
                return None
            return SheetParser(p.godlo)
```

At start of `get_children` (~line 364):
```python
        if self._pl2000 is not None:
            children = self._pl2000.get_children()
            return [SheetParser(c.godlo) for c in children]
```

At start of `get_hierarchy_up` (~line 426):
```python
        if self._pl2000 is not None:
            h = self._pl2000.get_hierarchy_up()
            return [SheetParser(x.godlo) for x in h]
```

At start of `get_all_descendants` (~line 457):
```python
        if self._pl2000 is not None:
            desc = self._pl2000.get_all_descendants(target_scale)
            return [SheetParser(d.godlo) for d in desc]
```

**Modify `__eq__` and `__hash__` to include system in comparison:**
```python
    def __eq__(self, other):
        if not isinstance(other, SheetParser):
            return NotImplemented
        return self._godlo == other._godlo and self._uklad == other._uklad

    def __hash__(self):
        return hash((self._godlo, self._uklad))
```

### Step 4: Run ALL tests

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: All existing 636 tests + new auto-detection tests PASS

### Step 5: Commit

```bash
git add kartograf/core/sheet_parser.py tests/test_sheet_parser.py
git commit -m "feat(parser): SheetParser auto-detection — PL-1992 vs PL-2000 facade"
```

---

## Task 5: Extend find_sheets_for_bbox & Update Geometry

**Files:**
- Modify: `kartograf/core/sheet_parser.py` (find_sheets_for_bbox, ~line 830)
- Modify: `kartograf/core/geometry.py` (~line 468)
- Modify: `tests/test_sheet_parser.py`

**Depends on:** Task 4

### Step 1: Write failing tests

Add to `tests/test_sheet_parser.py`:

```python
class TestFindSheetsForBBoxSystem:
    """find_sheets_for_bbox with system parameter."""

    def test_default_system_1992(self):
        """Default system=1992 returns PL-1992 godla."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result = find_sheets_for_bbox(bbox, target_scale="1:10000")
        # Should return PL-1992 format (dashes)
        assert all("-" in g for g in result)

    def test_system_2000(self):
        """system=2000 returns PL-2000 godla."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result = find_sheets_for_bbox(
            bbox, target_scale="1:10000", system="2000"
        )
        # Should return PL-2000 format (dots)
        assert all("." in g for g in result)
        assert len(result) > 0

    def test_backward_compatible(self):
        """Calling without system param works as before."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result_old = find_sheets_for_bbox(bbox, "1:10000")
        result_new = find_sheets_for_bbox(bbox, "1:10000", system="1992")
        assert result_old == result_new
```

### Step 2: Verify tests fail

### Step 3: Modify find_sheets_for_bbox

In `kartograf/core/sheet_parser.py`, modify `find_sheets_for_bbox` signature (~line 830):

```python
def find_sheets_for_bbox(
    bbox: BBox,
    target_scale: str = "1:10000",
    system: str = "1992",
) -> list[str]:
```

At the start of the function body, add dispatch:
```python
    if system == "2000":
        from kartograf.core.parser_2000 import find_sheets_2000_for_bbox
        return find_sheets_2000_for_bbox(bbox, target_scale)

    # ... existing PL-1992 logic unchanged ...
```

### Step 4: Update geometry.py

Modify `find_sheets_for_geometry` in `kartograf/core/geometry.py` to pass system parameter:

Add `system: str = "1992"` parameter to `find_sheets_for_geometry()` and pass it through to `find_sheets_for_bbox()`.

### Step 5: Run tests

```bash
.venv/bin/python -m pytest tests/ -v
```

### Step 6: Commit

```bash
git add kartograf/core/sheet_parser.py kartograf/core/geometry.py tests/test_sheet_parser.py
git commit -m "feat(parser): find_sheets_for_bbox system parameter — PL-1992/PL-2000 dispatch"
```

---

## Task 6: FileStorage & DownloadManager Updates

**Files:**
- Modify: `kartograf/download/storage.py` (lines 136-173)
- Modify: `kartograf/download/manager.py`
- Modify/Create: tests

**Depends on:** Task 4

### Step 1: Write failing FileStorage tests

```python
class TestFileStoragePL2000:
    """FileStorage with PL-2000 godla."""

    def test_get_path_pl2000(self, tmp_path):
        storage = FileStorage(str(tmp_path), subdir="nmt_2000_1m")
        path = storage.get_path("6.179.12.20")
        assert "nmt_2000_1m" in str(path)
        assert "6" in str(path)
        assert "179" in str(path)
        assert "6.179.12.20.asc" in str(path)

    def test_get_path_pl1992_unchanged(self, tmp_path):
        storage = FileStorage(str(tmp_path), subdir="nmt_1m")
        path = storage.get_path("N-34-130-D-d-2-4")
        assert "N-34" in str(path)
```

### Step 2: Modify _get_directory_parts

In `kartograf/download/storage.py`, modify `_get_directory_parts` (line 150):

```python
    def _get_directory_parts(self, godlo: str) -> list[str]:
        """Extract directory parts from godlo (PL-1992 or PL-2000)."""
        if "." in godlo:
            # PL-2000: split on dots
            parts = godlo.split(".")
            return parts[:-1] if len(parts) > 3 else parts
        else:
            # PL-1992: split on dashes
            parts = godlo.split("-")
            dir_parts = [f"{parts[0]}-{parts[1]}"]
            for part in parts[2:]:
                dir_parts.append(part)
            return dir_parts
```

### Step 3: DownloadManager — handle PL-2000 target scale

In `kartograf/download/manager.py`, the `download_sheet` method checks `parser.scale != "1:10000"` to decide expansion. For PL-2000, the target scale for NMT may differ. Verify that `SheetParser("6.179.12.20").scale` returns the correct scale and that hierarchy expansion works through the facade.

The key change: when scale is PL-2000 specific (1:2000, 1:1000, 1:500), the manager should handle it. Verify auto-detection works in DownloadManager context.

### Step 4: Run tests

```bash
.venv/bin/python -m pytest tests/ -v
```

### Step 5: Commit

```bash
git add kartograf/download/storage.py kartograf/download/manager.py tests/
git commit -m "feat(storage): PL-2000 directory structure support"
```

---

## Task 7: CLI Updates

**Files:**
- Modify: `kartograf/cli/commands.py`
- Modify: CLI-related tests

**Depends on:** Tasks 4-6

### Step 1: Update parse command

The `cmd_parse()` function (line 465) already uses `SheetParser(args.godlo)`. With auto-detection, this works automatically for PL-2000 godla.

**Enhance output for PL-2000** — add zone and native CRS info in `format_sheet_info()` (line 330):

```python
    if parser.uklad == "2000":
        lines.append(f"  Strefa: {parser.components.get('strefa', '?')}")
        # Show native CRS
        from kartograf.core.parser_2000 import ZONE_EPSG
        zone = int(parser.components["strefa"])
        lines.append(f"  Natywny CRS: {ZONE_EPSG[zone]}")
```

### Step 2: Update download command

Add `--system` parameter to download command arguments:

```python
download_parser.add_argument(
    "--system", choices=["1992", "2000"], default="1992",
    help="System godlowania (domyslnie 1992)"
)
```

Pass to `find_sheets_for_bbox` when using `--bbox` or `--geometry`.

### Step 3: Extend --bbox-crs choices

Add EPSG:2176-2179 to valid CRS choices for `--bbox-crs` argument.

### Step 4: Write CLI tests

```python
class TestCLIPL2000:
    def test_parse_pl2000(self, capsys):
        """kartograf parse 6.179.12"""
        # Test that parse command works with PL-2000 godlo

    def test_parse_pl2000_shows_zone(self, capsys):
        """Output includes zone info for PL-2000."""
```

### Step 5: Run tests

```bash
.venv/bin/python -m pytest tests/ -v
```

### Step 6: Commit

```bash
git add kartograf/cli/commands.py tests/
git commit -m "feat(cli): PL-2000 auto-detection in parse/download commands"
```

---

## Task 8: Technical Verification & Documentation

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/PROGRESS.md`
- Modify: `kartograf/__init__.py` (version bump)

**Depends on:** All previous tasks

### Step 1: Run full test suite with coverage

```bash
.venv/bin/python -m pytest tests/ -v --cov=kartograf --cov-report=term-missing
```
Expected: All tests pass, coverage >= 80%

### Step 2: Run linter

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
```

### Step 3: Run type checker

```bash
.venv/bin/python -m mypy kartograf/
```

### Step 4: Manual verification — parse PL-2000 godlo

```bash
kartograf parse 6.179.12
kartograf parse 6.179.12.20
kartograf parse 6.179.12.20.2.1
```

### Step 5: Update documentation

**CHANGELOG.md** — add v0.5.0 entry:
- feat(parser): PL-2000 sheet naming system support
- feat(parser): auto-detection PL-1992 vs PL-2000
- feat(parser): find_sheets_2000_for_bbox
- feat(cli): --system parameter for download/landcover
- feat(storage): PL-2000 directory structure

**PROGRESS.md** — update status table and "Ostatnia sesja"

### Step 6: Commit docs

```bash
git add docs/ kartograf/__init__.py
git commit -m "docs: PL-2000 support documentation, version bump"
```

---

## Execution Notes

### Risk Areas
1. **BBox formulas** — coordinate offsets (4920000, 332000) must be verified against real GUGiK data. Download the example file (`77247_1336074_6.179.12.20.asc`) and compare ASC header coordinates with calculated BBox.
2. **1:5k vs 1:2k branching** — unique hierarchy where 10k has TWO independent subdivision paths. Tests must cover both branches.
3. **Zone boundaries** — areas near zone borders may need sheets from adjacent zones. The `_determine_zones_for_bbox` function handles this.
4. **WMS GetFeatureInfo** — existing GugikProvider queries WMS to get download URLs. Must verify that WMS returns PL-2000 URLs for areas with PL-2000 data.

### What to verify with real data
- Download `6.179.12.20.asc` and check `xllcorner`/`yllcorner` values match calculated BBox
- Query WMS skorowidze for PL-2000 area and verify response format
- Test `kartograf download 6.179.12.20` end-to-end
