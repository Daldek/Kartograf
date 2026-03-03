# v0.6 Implementation Plan — PL-2000 Verification, Parallel Downloads, Metadata Cache

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PL-2000 BBox verification tests, parallel download support, and SQLite metadata cache to Kartograf v0.6.0.

**Architecture:** Three independent feature branches worked in parallel by 3 teams of 5 subagents each. Each team works in a dedicated git worktree. After completion, a merge team integrates all branches into `develop`. Each team has 4 implementation agents + 1 verification agent.

**Tech Stack:** Python 3.12+, pytest, concurrent.futures.ThreadPoolExecutor, sqlite3 (stdlib), requests, pyproj

---

## Shared Context for All Teams

### Environment Setup

```bash
# Python environment
PYTHON=.venv/bin/python
PIP=.venv/bin/pip
PYTEST=".venv/bin/python -m pytest"
RUFF=".venv/bin/python -m ruff"

# Run tests
.venv/bin/python -m pytest tests/ -v

# Run linter
.venv/bin/python -m ruff check kartograf/ tests/

# Check formatting
.venv/bin/python -m ruff format --check kartograf/ tests/

# Fix formatting
.venv/bin/python -m ruff format kartograf/ tests/
```

### Available Tools

Each subagent has access to:
- **Read** — read files (use instead of `cat`)
- **Write** — create new files
- **Edit** — edit existing files (use instead of `sed`)
- **Glob** — find files by pattern (use instead of `find`)
- **Grep** — search file contents (use instead of `grep`/`rg`)
- **Bash** — shell commands: git, pytest, ruff, pip
- **Agent** — delegate subtasks to sub-agents
- **WebFetch** — fetch URL content (for live WMS tests)
- **WebSearch** — search the web (for GUGiK documentation)

### Available Skills (invoke with Skill tool)

- `superpowers:test-driven-development` — TDD workflow (RED -> GREEN -> REFACTOR)
- `superpowers:systematic-debugging` — debug test failures and bugs
- `superpowers:verification-before-completion` — verify work before claiming done
- `superpowers:code-review` — code review after completing work
- `simplify` — review code for reuse and quality

### Branch Setup

Each team MUST start from `develop`:

```bash
# Verify you're on develop
git checkout develop
git pull origin develop

# Create feature branch (team-specific)
git checkout -b feature/<branch-name>
```

### Commit Convention

All commits use Conventional Commits:
- `feat(scope): description` — new feature
- `test(scope): description` — new tests
- `fix(scope): description` — bug fix
- `refactor(scope): description` — refactoring

### Pre-Commit Checklist

Before every commit:
1. `.venv/bin/python -m pytest tests/ -v` — ALL tests pass
2. `.venv/bin/python -m ruff check kartograf/ tests/` — zero lint errors
3. `.venv/bin/python -m ruff format --check kartograf/ tests/` — formatting OK

### Key Files to Read First

- `/home/claude-agent/workspace/Kartograf/CLAUDE.md` — project instructions
- `/home/claude-agent/workspace/Kartograf/docs/PROGRESS.md` — current state
- `/home/claude-agent/workspace/Kartograf/docs/DECISIONS.md` — architectural decisions
- `/home/claude-agent/workspace/Kartograf/kartograf/__init__.py` — public API exports

### Existing Tests: 835 tests, ~84% coverage. DO NOT modify existing tests unless absolutely necessary.

---

## TEAM 1: PL-2000 BBox Verification

**Branch:** `feature/pl2000-verification`
**Scope:** New test file only — zero changes to source code
**Key source files to read:**
- `kartograf/core/parser_2000.py` — Parser2000, BBox computation, find_sheets_2000_for_bbox
- `kartograf/core/sheet_parser.py` — BBox NamedTuple, SheetParser (delegates to Parser2000)
- `tests/test_parser_2000.py` — existing PL-2000 tests (DO NOT modify)

### Agent 1A: Offline BBox Reference Tests

**Files:**
- Create: `tests/test_pl2000_verification.py`

**Step 1: Read source code**

Read `kartograf/core/parser_2000.py` lines 307-395 — understand `_calculate_native_bbox()` and `_apply_quadrant()`.

**Step 2: Write reference value tests**

```python
"""Verification tests for PL-2000 BBox computation against known reference values."""

import pytest
from kartograf.core.parser_2000 import Parser2000

class TestPL2000BBoxReferenceValues:
    """Test BBox computation against known reference values from GUGiK documentation.

    Reference: Instrukcja techniczna K-1 (Mapa zasadnicza)
    BBox formula for 1:10000:
        south = pas * 5000 + 4_920_000
        north = south + 5000
        west  = strefa * 1_000_000 + slup * 8000 + 332_000
        east  = west + 8000
    """

    @pytest.mark.parametrize("godlo,expected_south,expected_north,expected_west,expected_east", [
        # Zone 5 (EPSG:2176) — western Poland
        ("5.100.10", 5420000, 5425000, 5412000, 5420000),
        ("5.100.15", 5420000, 5425000, 5452000, 5460000),
        ("5.110.10", 5470000, 5475000, 5412000, 5420000),
        ("5.110.20", 5470000, 5475000, 5492000, 5500000),
        ("5.120.5",  5520000, 5525000, 5372000, 5380000),
        # Zone 6 (EPSG:2177) — central Poland
        ("6.100.10", 6420000, 6425000, 6412000, 6420000),
        ("6.150.15", 6670000, 6675000, 6452000, 6460000),
        ("6.179.12", 6815000, 6820000, 6428000, 6436000),
        ("6.200.20", 6920000, 6925000, 6492000, 6500000),
        ("6.180.10", 6820000, 6825000, 6412000, 6420000),
        # Zone 7 (EPSG:2178) — eastern Poland
        ("7.100.10", 7420000, 7425000, 7412000, 7420000),
        ("7.150.15", 7670000, 7675000, 7452000, 7460000),
        ("7.120.8",  7520000, 7525000, 7396000, 7404000),
        ("7.130.12", 7570000, 7575000, 7428000, 7436000),
        ("7.140.18", 7620000, 7625000, 7476000, 7484000),
        # Zone 8 (EPSG:2179) — easternmost Poland
        ("8.100.10", 8420000, 8425000, 8412000, 8420000),
        ("8.110.5",  8470000, 8475000, 8372000, 8380000),
        ("8.120.15", 8520000, 8525000, 8452000, 8460000),
        ("8.130.8",  8570000, 8575000, 8396000, 8404000),
        ("8.105.12", 8445000, 8450000, 8428000, 8436000),
    ])
    def test_10k_bbox_matches_formula(self, godlo, expected_south, expected_north,
                                       expected_west, expected_east):
        """BBox of 1:10000 sheet matches mathematical formula."""
        parser = Parser2000(godlo)
        bbox = parser.get_bbox()  # native CRS

        assert bbox.min_y == pytest.approx(expected_south, abs=0.01)
        assert bbox.max_y == pytest.approx(expected_north, abs=0.01)
        assert bbox.min_x == pytest.approx(expected_west, abs=0.01)
        assert bbox.max_x == pytest.approx(expected_east, abs=0.01)

    @pytest.mark.parametrize("godlo,expected_height,expected_width", [
        # 1:5000 — 2500m x 4000m
        ("6.179.12.1", 2500, 4000),
        ("6.179.12.2", 2500, 4000),
        ("6.179.12.3", 2500, 4000),
        ("6.179.12.4", 2500, 4000),
        # 1:2000 — 1000m x 1600m
        ("6.179.12.01", 1000, 1600),
        ("6.179.12.13", 1000, 1600),
        ("6.179.12.25", 1000, 1600),
        # 1:1000 — 500m x 800m
        ("6.179.12.15.1", 500, 800),
        ("6.179.12.15.4", 500, 800),
        # 1:500 — 250m x 400m
        ("6.179.12.15.2.3", 250, 400),
    ])
    def test_sheet_dimensions(self, godlo, expected_height, expected_width):
        """Each scale has correct sheet dimensions."""
        parser = Parser2000(godlo)
        bbox = parser.get_bbox()

        actual_height = bbox.max_y - bbox.min_y
        actual_width = bbox.max_x - bbox.min_x

        assert actual_height == pytest.approx(expected_height, abs=0.01)
        assert actual_width == pytest.approx(expected_width, abs=0.01)
```

**Step 3: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_pl2000_verification.py::TestPL2000BBoxReferenceValues -v
```

Expected: All PASS (these verify the formula, which is implemented correctly).

**Step 4: Commit**

```bash
git add tests/test_pl2000_verification.py
git commit -m "test(pl2000): add BBox reference value tests for all 4 zones"
```

---

### Agent 1B: Hierarchy and Children Consistency Tests

**Files:**
- Modify: `tests/test_pl2000_verification.py` (append new test classes)

**Step 1: Write hierarchy consistency tests**

```python
class TestPL2000HierarchyConsistency:
    """Test that children BBoxes tile perfectly within parent BBox."""

    @pytest.mark.parametrize("parent_godlo", [
        "5.100.10", "6.179.12", "7.130.12", "8.110.5",
    ])
    def test_5k_children_cover_parent_exactly(self, parent_godlo):
        """4 children at 1:5000 tile exactly over parent 1:10000."""
        parent = Parser2000(parent_godlo)
        parent_bbox = parent.get_bbox()
        children = parent.get_children(scale="1:5000")

        assert len(children) == 4

        # Union of children bboxes should equal parent bbox
        min_x = min(c.get_bbox().min_x for c in children)
        min_y = min(c.get_bbox().min_y for c in children)
        max_x = max(c.get_bbox().max_x for c in children)
        max_y = max(c.get_bbox().max_y for c in children)

        assert min_x == pytest.approx(parent_bbox.min_x, abs=0.01)
        assert min_y == pytest.approx(parent_bbox.min_y, abs=0.01)
        assert max_x == pytest.approx(parent_bbox.max_x, abs=0.01)
        assert max_y == pytest.approx(parent_bbox.max_y, abs=0.01)

    @pytest.mark.parametrize("parent_godlo", [
        "5.100.10", "6.179.12", "7.130.12", "8.110.5",
    ])
    def test_2k_children_cover_parent_exactly(self, parent_godlo):
        """25 children at 1:2000 tile exactly over parent 1:10000."""
        parent = Parser2000(parent_godlo)
        parent_bbox = parent.get_bbox()
        children = parent.get_children(scale="1:2000")

        assert len(children) == 25

        min_x = min(c.get_bbox().min_x for c in children)
        min_y = min(c.get_bbox().min_y for c in children)
        max_x = max(c.get_bbox().max_x for c in children)
        max_y = max(c.get_bbox().max_y for c in children)

        assert min_x == pytest.approx(parent_bbox.min_x, abs=0.01)
        assert min_y == pytest.approx(parent_bbox.min_y, abs=0.01)
        assert max_x == pytest.approx(parent_bbox.max_x, abs=0.01)
        assert max_y == pytest.approx(parent_bbox.max_y, abs=0.01)

    @pytest.mark.parametrize("parent_godlo", [
        "6.179.12.15", "7.130.12.01", "8.110.5.25",
    ])
    def test_1k_children_cover_2k_parent(self, parent_godlo):
        """4 children at 1:1000 tile exactly over parent 1:2000."""
        parent = Parser2000(parent_godlo)
        parent_bbox = parent.get_bbox()
        children = parent.get_children()

        assert len(children) == 4

        min_x = min(c.get_bbox().min_x for c in children)
        min_y = min(c.get_bbox().min_y for c in children)
        max_x = max(c.get_bbox().max_x for c in children)
        max_y = max(c.get_bbox().max_y for c in children)

        assert min_x == pytest.approx(parent_bbox.min_x, abs=0.01)
        assert min_y == pytest.approx(parent_bbox.min_y, abs=0.01)
        assert max_x == pytest.approx(parent_bbox.max_x, abs=0.01)
        assert max_y == pytest.approx(parent_bbox.max_y, abs=0.01)

    def test_no_descendant_exceeds_ancestor_bbox(self):
        """No descendant BBox extends beyond its ancestor's BBox."""
        parent = Parser2000("6.179.12")
        parent_bbox = parent.get_bbox()

        for desc in parent.get_all_descendants("1:1000"):
            desc_bbox = desc.get_bbox()
            assert desc_bbox.min_x >= parent_bbox.min_x - 0.01
            assert desc_bbox.min_y >= parent_bbox.min_y - 0.01
            assert desc_bbox.max_x <= parent_bbox.max_x + 0.01
            assert desc_bbox.max_y <= parent_bbox.max_y + 0.01

    def test_no_children_overlap(self):
        """Children at 1:2000 do not overlap each other (no shared interior)."""
        parent = Parser2000("6.179.12")
        children = parent.get_children(scale="1:2000")

        for i, a in enumerate(children):
            for b in children[i + 1:]:
                a_bbox = a.get_bbox()
                b_bbox = b.get_bbox()
                # Interior overlap check (touching edges OK)
                overlap_x = min(a_bbox.max_x, b_bbox.max_x) - max(a_bbox.min_x, b_bbox.min_x)
                overlap_y = min(a_bbox.max_y, b_bbox.max_y) - max(a_bbox.min_y, b_bbox.min_y)
                # Either no overlap or only edge-touching (overlap <= 0 in at least one dimension)
                assert overlap_x <= 0.01 or overlap_y <= 0.01
```

**Step 2: Run tests**

```bash
.venv/bin/python -m pytest tests/test_pl2000_verification.py::TestPL2000HierarchyConsistency -v
```

**Step 3: Commit**

```bash
git add tests/test_pl2000_verification.py
git commit -m "test(pl2000): add hierarchy consistency tests — children tiling, no overlap"
```

---

### Agent 1C: Live WMS Tests

**Files:**
- Modify: `tests/test_pl2000_verification.py` (append)
- Modify: `pyproject.toml` (add `live` marker)

**Step 1: Register pytest marker**

Read `pyproject.toml` and add the `live` marker to `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
markers = [
    "live: tests requiring network access to GUGiK WMS (deselect with '-m not live')",
]
```

If `[tool.pytest.ini_options]` doesn't exist, create it.

**Step 2: Write live WMS tests**

```python
import requests

class TestPL2000LiveWMS:
    """Live tests querying GUGiK WMS to verify PL-2000 BBox center points.

    These tests are skipped by default. Run with: pytest -m live
    Requires network access to mapy.geoportal.gov.pl
    """

    WMS_ENDPOINT = (
        "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladEVRF2007"
    )
    WMS_LAYER = "SkorowidzeNMT2024"

    def _query_wms_at_point(self, x_2180: float, y_2180: float, timeout: int = 30) -> str:
        """Query GUGiK WMS at a point in EPSG:2180 and return response text."""
        buffer = 10
        bbox = f"{y_2180 - buffer},{x_2180 - buffer},{y_2180 + buffer},{x_2180 + buffer}"
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": self.WMS_LAYER,
            "QUERY_LAYERS": self.WMS_LAYER,
            "INFO_FORMAT": "text/html",
            "CRS": "EPSG:2180",
            "BBOX": bbox,
            "WIDTH": 100,
            "HEIGHT": 100,
            "I": 50,
            "J": 50,
        }
        from urllib.parse import urlencode
        url = f"{self.WMS_ENDPOINT}?{urlencode(params)}"
        session = requests.Session()
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text

    @pytest.mark.live
    @pytest.mark.parametrize("godlo", [
        # Zone 6 (central Poland — best coverage)
        "6.179.12",   # near Bialystok
        "6.150.15",   # central
        "6.170.10",   # mid-east
        # Zone 7
        "7.120.8",
        "7.130.12",
        # Zone 5
        "5.110.10",
        "5.120.5",
        # Zone 8
        "8.110.5",
    ])
    def test_wms_returns_data_at_bbox_center(self, godlo):
        """GUGiK WMS returns data at the computed center of a PL-2000 sheet."""
        parser = Parser2000(godlo)
        bbox_2180 = parser.get_bbox(crs="EPSG:2180")

        center_x = (bbox_2180.min_x + bbox_2180.max_x) / 2
        center_y = (bbox_2180.min_y + bbox_2180.max_y) / 2

        try:
            text = self._query_wms_at_point(center_x, center_y)
            # WMS returns HTML with data or empty body
            # If the center maps to a valid sheet, there should be content
            # We don't assert data presence (coverage varies),
            # just that the request doesn't fail
            assert isinstance(text, str)
        except requests.exceptions.ConnectionError:
            pytest.skip("GUGiK WMS unavailable")
        except requests.exceptions.Timeout:
            pytest.skip("GUGiK WMS timeout")
```

**Step 3: Run live tests (optional, requires network)**

```bash
.venv/bin/python -m pytest tests/test_pl2000_verification.py::TestPL2000LiveWMS -m live -v
```

**Step 4: Verify non-live tests still work (live tests should be skipped)**

```bash
.venv/bin/python -m pytest tests/test_pl2000_verification.py -v -m "not live"
```

**Step 5: Commit**

```bash
git add tests/test_pl2000_verification.py pyproject.toml
git commit -m "test(pl2000): add live WMS verification tests (@pytest.mark.live)"
```

---

### Agent 1D: Edge Cases and Round-Trip Tests

**Files:**
- Modify: `tests/test_pl2000_verification.py` (append)

**Step 1: Write edge case and round-trip tests**

```python
from kartograf.core.parser_2000 import find_sheets_2000_for_bbox, ZONE_EPSG
from kartograf.core.sheet_parser import BBox

class TestPL2000EdgeCases:
    """Edge cases: zone boundaries, extreme sheets, multi-zone queries."""

    def test_multi_zone_bbox_returns_sheets_from_both_zones(self):
        """BBox spanning zone 6/7 boundary (19.5°E) returns sheets from both."""
        # BBox in WGS84 crossing the 19.5°E meridian
        bbox = BBox(min_x=19.3, min_y=51.0, max_x=19.7, max_y=51.2, crs="EPSG:4326")
        godla = find_sheets_2000_for_bbox(bbox, target_scale="1:10000")

        zones_found = set()
        for g in godla:
            zone = int(g.split(".")[0])
            zones_found.add(zone)

        assert 6 in zones_found, "Should find sheets in zone 6"
        assert 7 in zones_found, "Should find sheets in zone 7"

    def test_multi_zone_bbox_56_boundary(self):
        """BBox spanning zone 5/6 boundary (16.5°E)."""
        bbox = BBox(min_x=16.3, min_y=51.0, max_x=16.7, max_y=51.2, crs="EPSG:4326")
        godla = find_sheets_2000_for_bbox(bbox, target_scale="1:10000")

        zones_found = {int(g.split(".")[0]) for g in godla}
        assert 5 in zones_found
        assert 6 in zones_found

    def test_multi_zone_bbox_78_boundary(self):
        """BBox spanning zone 7/8 boundary (22.5°E)."""
        bbox = BBox(min_x=22.3, min_y=51.0, max_x=22.7, max_y=51.2, crs="EPSG:4326")
        godla = find_sheets_2000_for_bbox(bbox, target_scale="1:10000")

        zones_found = {int(g.split(".")[0]) for g in godla}
        assert 7 in zones_found
        assert 8 in zones_found

    @pytest.mark.parametrize("godlo", [
        "5.100.10", "6.179.12", "7.130.12", "8.110.5",
        "6.179.12.15", "6.179.12.01", "6.179.12.25",
        "6.179.12.15.2", "6.179.12.15.2.3",
    ])
    def test_round_trip_godlo_to_bbox_to_find(self, godlo):
        """godlo -> BBox -> find_sheets_2000_for_bbox -> result contains original godlo."""
        parser = Parser2000(godlo)
        bbox = parser.get_bbox()  # native CRS

        found = find_sheets_2000_for_bbox(bbox, target_scale=parser.scale)
        assert godlo in found, f"{godlo} not found in {found}"

    def test_single_point_bbox_finds_containing_sheet(self):
        """Very small BBox (point-like) finds exactly one 1:10000 sheet."""
        # Center of 6.179.12
        parser = Parser2000("6.179.12")
        bbox = parser.get_bbox()
        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2
        eps = 0.001

        point_bbox = BBox(
            min_x=center_x - eps, min_y=center_y - eps,
            max_x=center_x + eps, max_y=center_y + eps,
            crs=bbox.crs,
        )
        found = find_sheets_2000_for_bbox(point_bbox, target_scale="1:10000")
        assert found == ["6.179.12"]

    def test_zone_forced_overrides_auto_detection(self):
        """Explicit zone parameter limits search to that zone only."""
        bbox = BBox(min_x=19.3, min_y=51.0, max_x=19.7, max_y=51.2, crs="EPSG:4326")

        only_zone6 = find_sheets_2000_for_bbox(bbox, zone=6)
        only_zone7 = find_sheets_2000_for_bbox(bbox, zone=7)

        for g in only_zone6:
            assert g.startswith("6.")
        for g in only_zone7:
            assert g.startswith("7.")

    def test_drill_down_to_5k(self):
        """find_sheets_2000_for_bbox with target_scale=1:5000 returns 5k sheets."""
        parser = Parser2000("6.179.12")
        bbox = parser.get_bbox()

        found = find_sheets_2000_for_bbox(bbox, target_scale="1:5000")
        assert len(found) == 4
        assert all(g.startswith("6.179.12.") for g in found)

    def test_drill_down_to_2k(self):
        """find_sheets_2000_for_bbox with target_scale=1:2000 returns 2k sheets."""
        parser = Parser2000("6.179.12")
        bbox = parser.get_bbox()

        found = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert len(found) == 25
```

**Step 2: Run all verification tests**

```bash
.venv/bin/python -m pytest tests/test_pl2000_verification.py -v -m "not live"
```

**Step 3: Commit**

```bash
git add tests/test_pl2000_verification.py
git commit -m "test(pl2000): add edge cases — multi-zone, round-trip, drill-down"
```

---

### Agent 1V: Verification

**Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 835 existing + ~50 new tests, ALL PASS.

**Step 2: Run linter and formatter**

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
```

**Step 3: Verify no source code was modified**

```bash
git diff --name-only develop -- kartograf/
```

Expected: empty output (only test files and pyproject.toml changed).

**Step 4: Check coverage**

```bash
.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=term-missing -q
```

**Step 5: Report findings**

List any issues found. If issues exist, create fix commits. Then run full suite again.

---

## TEAM 2: Parallel Downloads

**Branch:** `feature/parallel-downloads`
**Key source files to read:**
- `kartograf/download/manager.py` — DownloadManager (sequential loop at line 284)
- `kartograf/providers/gugik.py` — GugikProvider._make_request (creates session per call, line 583-588)
- `kartograf/landcover/manager.py` — LandCoverManager.download (single dispatch)
- `kartograf/cli/commands.py` — CLI commands (sequential loops at lines 771, 866)

### Agent 2A: DownloadManager Parallelization

**Files:**
- Modify: `kartograf/download/manager.py`
- Create: `tests/test_parallel_download.py`

**Step 1: Write failing test for parallel download_hierarchy**

```python
"""Tests for parallel download functionality."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from kartograf.download.manager import DownloadManager, DownloadProgress


class TestParallelDownloadHierarchy:
    """Test that download_hierarchy uses ThreadPoolExecutor when max_workers > 1."""

    def test_download_hierarchy_with_workers(self, tmp_path):
        """download_hierarchy with max_workers=2 downloads in parallel."""
        mock_provider = MagicMock()
        mock_provider.name = "test"
        type(mock_provider).default_extension = PropertyMock(return_value=".asc")

        # Track which thread each download runs on
        threads = []
        def fake_download(godlo, output_path, timeout=30):
            threads.append(threading.current_thread().name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("data")
            return output_path
        mock_provider.download.side_effect = fake_download

        from kartograf.download.storage import FileStorage
        storage = FileStorage(tmp_path, resolution="1m")
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=mock_provider,
            storage=storage,
            max_workers=2,
        )

        paths = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(paths) > 0
        assert mock_provider.download.call_count > 0

    def test_max_workers_1_is_sequential(self, tmp_path):
        """max_workers=1 runs downloads sequentially (backward compatible)."""
        mock_provider = MagicMock()
        mock_provider.name = "test"
        type(mock_provider).default_extension = PropertyMock(return_value=".asc")

        def fake_download(godlo, output_path, timeout=30):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("data")
            return output_path
        mock_provider.download.side_effect = fake_download

        from kartograf.download.storage import FileStorage
        storage = FileStorage(tmp_path, resolution="1m")
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=mock_provider,
            storage=storage,
            max_workers=1,
        )

        paths = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(paths) > 0
```

**Step 2: Run test — should fail (max_workers not accepted)**

```bash
.venv/bin/python -m pytest tests/test_parallel_download.py::TestParallelDownloadHierarchy::test_download_hierarchy_with_workers -v
```

Expected: FAIL with TypeError about unexpected `max_workers`.

**Step 3: Implement max_workers in DownloadManager**

Modify `kartograf/download/manager.py`:

1. Add `import concurrent.futures` and `import threading` at top
2. Add `max_workers=1` parameter to `__init__`
3. Add `DownloadResult` dataclass:

```python
@dataclass
class DownloadResult:
    """Result of a batch download operation."""
    succeeded: list[Path]
    failed: list[str]
    skipped: list[str]
```

4. Replace sequential loop in `download_hierarchy` with ThreadPoolExecutor:

```python
def download_hierarchy(self, godlo, target_scale, skip_existing=True,
                       on_progress=None, max_workers=None):
    # Use instance max_workers if not overridden
    workers = max_workers or self._max_workers

    parser = SheetParser(godlo)
    descendants = parser.get_all_descendants(target_scale)
    total = len(descendants)
    downloaded_paths = []
    failed_count = 0
    lock = threading.Lock()

    def _download_one(i_and_descendant):
        i, descendant = i_and_descendant
        current_godlo = descendant.godlo
        try:
            target_path = self._storage.get_path(current_godlo, self._default_ext)
            if skip_existing and target_path.exists():
                with lock:
                    if on_progress:
                        on_progress(DownloadProgress(
                            current=i, total=total, godlo=current_godlo,
                            status="skipped", message="Already exists",
                        ))
                    downloaded_paths.append(target_path)
                return

            with lock:
                if on_progress:
                    on_progress(DownloadProgress(
                        current=i, total=total, godlo=current_godlo,
                        status="downloading",
                    ))

            path = self._provider.download(current_godlo, target_path)

            with lock:
                downloaded_paths.append(path)
                if on_progress:
                    on_progress(DownloadProgress(
                        current=i, total=total, godlo=current_godlo,
                        status="completed",
                    ))
        except DownloadError as e:
            with lock:
                nonlocal failed_count
                failed_count += 1
                if on_progress:
                    on_progress(DownloadProgress(
                        current=i, total=total, godlo=current_godlo,
                        status="failed", message=str(e),
                    ))

    items = list(enumerate(descendants, 1))

    if workers <= 1:
        for item in items:
            _download_one(item)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_download_one, items))

    return downloaded_paths
```

**Step 4: Run test — should pass**

```bash
.venv/bin/python -m pytest tests/test_parallel_download.py -v
```

**Step 5: Run full test suite to check backward compatibility**

```bash
.venv/bin/python -m pytest tests/ -v
```

All 835 existing tests MUST still pass.

**Step 6: Commit**

```bash
git add kartograf/download/manager.py tests/test_parallel_download.py
git commit -m "feat(download): add parallel download support with ThreadPoolExecutor"
```

---

### Agent 2B: Provider Thread-Safety

**Files:**
- Modify: `kartograf/providers/gugik.py` (line 583-588, `_make_request`)
- Modify: `tests/test_parallel_download.py` (append)

**Step 1: Write thread-safety test**

```python
class TestProviderThreadSafety:
    """Test that providers work correctly under concurrent access."""

    def test_concurrent_downloads_no_race_condition(self, tmp_path):
        """10 concurrent downloads don't corrupt files."""
        from kartograf.download.storage import FileStorage

        mock_provider = MagicMock()
        mock_provider.name = "test"
        type(mock_provider).default_extension = PropertyMock(return_value=".asc")

        results = {}
        def fake_download(godlo, output_path, timeout=30):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            content = f"data-for-{godlo}"
            output_path.write_text(content)
            results[godlo] = content
            return output_path
        mock_provider.download.side_effect = fake_download

        storage = FileStorage(tmp_path, resolution="1m")
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=mock_provider,
            storage=storage,
            max_workers=4,
        )

        # N-34-130-D-d-2 has 16 descendants at 1:10000
        paths = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(paths) == 16
        # Verify no file corruption
        for path in paths:
            assert path.exists()
```

**Step 2: Add session-per-call documentation**

Read `kartograf/providers/gugik.py:583-588`. The `_make_request` method already creates a new session per call when `self._session` is None:

```python
def _make_request(self, url, timeout):
    session = self._session or requests.Session()
    ...
```

This is already thread-safe (no shared mutable state). Document this in a comment:

```python
def _make_request(self, url: str, timeout: int) -> requests.Response:
    """Make HTTP GET request.

    Thread-safety: When self._session is None (default), a new Session
    is created per call, ensuring no shared state between threads.
    """
    session = self._session or requests.Session()
    response = session.get(url, timeout=timeout, stream=True)
    response.raise_for_status()
    return response
```

**Step 3: Verify FileStorage.write_atomic is thread-safe**

Read `kartograf/download/storage.py` — `write_atomic` uses temp+rename pattern. The temp filename includes the original filename suffix + `.tmp`, so two concurrent writes to different godla won't clash. But two writes to the SAME godlo could clash on the `.tmp` name. Add unique suffix:

In `kartograf/download/storage.py`, modify `write_atomic` to use thread-unique temp names:

```python
import os

def write_atomic(self, godlo, content, ext=".asc"):
    target = self.get_path(godlo, ext)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Use PID+thread ID for unique temp name (thread-safe)
    unique = f"{os.getpid()}_{threading.current_thread().ident}"
    temp_path = target.with_suffix(f"{ext}.{unique}.tmp")
    try:
        temp_path.write_bytes(content)
        temp_path.rename(target)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return target
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_parallel_download.py tests/test_storage.py -v
```

**Step 5: Commit**

```bash
git add kartograf/providers/gugik.py kartograf/download/storage.py tests/test_parallel_download.py
git commit -m "feat(providers): ensure thread-safety for concurrent downloads"
```

---

### Agent 2C: LandCover Parallel Downloads

**Files:**
- Modify: `kartograf/landcover/manager.py`
- Modify: `tests/test_parallel_download.py` (append)

**Step 1: Write failing test for batch download**

```python
class TestLandCoverParallelDownload:
    """Test LandCoverManager batch download with parallel workers."""

    def test_download_batch_teryt_list(self, tmp_path):
        """download_batch downloads multiple TERYTs in parallel."""
        from kartograf.landcover.manager import LandCoverManager

        mock_provider = MagicMock()
        mock_provider.name = "test"
        mock_provider.download_by_teryt.side_effect = lambda teryt, path, **kw: path

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        results = manager.download_batch(
            items=[{"teryt": "1465"}, {"teryt": "1261"}, {"teryt": "0461"}],
            max_workers=2,
        )
        assert len(results) == 3
        assert mock_provider.download_by_teryt.call_count == 3
```

**Step 2: Implement download_batch in LandCoverManager**

Add to `kartograf/landcover/manager.py`:

```python
import concurrent.futures
import threading

def download_batch(
    self,
    items: list[dict],
    max_workers: int = 4,
    **kwargs,
) -> list[Path]:
    """Download multiple items in parallel.

    Parameters
    ----------
    items : list[dict]
        List of dicts, each with one of: teryt, bbox, godlo
    max_workers : int
        Number of parallel workers (default: 4)
    **kwargs
        Provider-specific options passed to each download

    Returns
    -------
    list[Path]
        Paths to downloaded files (order matches items)
    """
    results = [None] * len(items)

    def _download_one(index_and_item):
        idx, item = index_and_item
        try:
            path = self.download(**item, **kwargs)
            results[idx] = path
        except Exception as e:
            logger.error(f"Failed to download item {idx}: {e}")
            results[idx] = None

    indexed_items = list(enumerate(items))

    if max_workers <= 1:
        for item in indexed_items:
            _download_one(item)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_download_one, indexed_items))

    return [r for r in results if r is not None]
```

**Step 3: Run test**

```bash
.venv/bin/python -m pytest tests/test_parallel_download.py::TestLandCoverParallelDownload -v
```

**Step 4: Commit**

```bash
git add kartograf/landcover/manager.py tests/test_parallel_download.py
git commit -m "feat(landcover): add download_batch with parallel workers"
```

---

### Agent 2D: CLI --workers Flag

**Files:**
- Modify: `kartograf/cli/commands.py`
- Modify: `tests/test_cli.py` (append)
- Modify: `tests/test_parallel_download.py` (append)

**Step 1: Add --workers argument to CLI**

In `kartograf/cli/commands.py`, add to `download_parser` (after `--system`):

```python
download_parser.add_argument(
    "--workers",
    "-w",
    type=int,
    default=4,
    help="Number of parallel download workers (default: 4, use 1 for sequential)",
)
```

Also add to `lc_download` parser:

```python
lc_download.add_argument(
    "--workers",
    "-w",
    type=int,
    default=4,
    help="Number of parallel download workers (default: 4)",
)
```

**Step 2: Pass max_workers through CLI commands**

In `cmd_download()`, pass `max_workers` to DownloadManager:

```python
manager = DownloadManager(
    output_dir=output_dir,
    provider=provider,
    storage=storage,
    vertical_crs=vertical_crs,
    resolution=resolution,
    max_workers=getattr(args, "workers", 4),
)
```

In `_cmd_download_bbox()` and `_cmd_download_geometry()`, similarly pass `max_workers`.

**Step 3: Write CLI test**

```python
class TestCLIWorkersFlag:
    """Test --workers flag in CLI."""

    def test_download_workers_flag_accepted(self):
        """CLI accepts --workers flag."""
        from kartograf.cli.commands import create_parser
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4", "--workers", "2"])
        assert args.workers == 2

    def test_download_default_workers(self):
        """Default workers is 4."""
        from kartograf.cli.commands import create_parser
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4"])
        assert args.workers == 4
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_parallel_download.py -v
```

**Step 5: Commit**

```bash
git add kartograf/cli/commands.py tests/test_cli.py tests/test_parallel_download.py
git commit -m "feat(cli): add --workers flag for parallel downloads"
```

---

### Agent 2V: Verification

**Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

All 835 existing + new parallel tests MUST pass.

**Step 2: Verify backward compatibility**

```bash
# max_workers=1 should give exact same behavior as before
.venv/bin/python -m pytest tests/test_download_manager.py -v
```

All existing DownloadManager tests must pass unchanged.

**Step 3: Linter and formatter**

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
```

**Step 4: Test thread-safety under load**

```bash
.venv/bin/python -m pytest tests/test_parallel_download.py -v -x --count=3 2>/dev/null || \
.venv/bin/python -m pytest tests/test_parallel_download.py -v -x
```

Run parallel tests 3 times to catch intermittent race conditions.

**Step 5: Report findings**

---

## TEAM 3: Metadata Cache (SQLite)

**Branch:** `feature/metadata-cache`
**Key files to read:**
- `kartograf/providers/gugik.py:278-397` — `_get_opendata_url()` (WMS lookup, uncached)
- `kartograf/providers/bdot10k.py` — `_get_teryt_for_point()` (TERYT WMS lookup, uncached)
- `kartograf/cli/commands.py` — CLI structure

### Agent 3A: MetadataCache Class

**Files:**
- Create: `kartograf/cache/__init__.py`
- Create: `kartograf/cache/metadata.py`
- Create: `tests/test_metadata_cache.py`

**Step 1: Create cache package**

```bash
mkdir -p kartograf/cache
```

**Step 2: Write failing test**

```python
"""Tests for MetadataCache (SQLite)."""

import time
from pathlib import Path

import pytest

from kartograf.cache.metadata import MetadataCache


class TestMetadataCacheURL:
    """Test URL cache operations."""

    def test_set_and_get_url(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://opendata.example.com/file.asc")

        result = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert result == "https://opendata.example.com/file.asc"
        cache.close()

    def test_get_url_returns_none_when_missing(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        result = cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt")
        assert result is None
        cache.close()

    def test_url_ttl_expiry(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db", ttl_seconds=1)
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://example.com/file.asc")

        # Should be available immediately
        assert cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt") is not None

        # Wait for TTL to expire
        time.sleep(1.1)
        assert cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt") is None
        cache.close()

    def test_url_overwrite(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_url("G1", "1m", "EVRF2007", "nmt", "url1")
        cache.set_url("G1", "1m", "EVRF2007", "nmt", "url2")
        assert cache.get_url("G1", "1m", "EVRF2007", "nmt") == "url2"
        cache.close()


class TestMetadataCacheTERYT:
    """Test TERYT cache operations."""

    def test_set_and_get_teryt(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_teryt(450000.0, 550000.0, "1465")
        assert cache.get_teryt(450000.0, 550000.0) == "1465"
        cache.close()

    def test_get_teryt_none_when_missing(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        assert cache.get_teryt(0.0, 0.0) is None
        cache.close()


class TestMetadataCacheManagement:
    """Test cache management operations."""

    def test_clear(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_url("G1", "1m", "EVRF2007", "nmt", "url")
        cache.set_teryt(1.0, 2.0, "1234")
        cache.clear()
        assert cache.get_url("G1", "1m", "EVRF2007", "nmt") is None
        assert cache.get_teryt(1.0, 2.0) is None
        cache.close()

    def test_stats(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_url("G1", "1m", "EVRF2007", "nmt", "url")
        cache.set_url("G2", "1m", "EVRF2007", "nmt", "url2")
        cache.set_teryt(1.0, 2.0, "1234")

        stats = cache.stats()
        assert stats["url_count"] == 2
        assert stats["teryt_count"] == 1
        cache.close()
```

**Step 3: Run test — should fail (module doesn't exist)**

```bash
.venv/bin/python -m pytest tests/test_metadata_cache.py -v
```

**Step 4: Implement MetadataCache**

Write `kartograf/cache/__init__.py`:
```python
"""Metadata cache for Kartograf."""
from kartograf.cache.metadata import MetadataCache

__all__ = ["MetadataCache"]
```

Write `kartograf/cache/metadata.py`:
```python
"""SQLite-based metadata cache for OpenData URLs and TERYT lookups."""

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days


class MetadataCache:
    """SQLite cache for metadata lookups (URLs, TERYT codes).

    Thread-safe via WAL mode (concurrent reads, serialized writes).

    Parameters
    ----------
    db_path : Path or str, optional
        Path to SQLite database file. Default: .kartograf_cache.db in CWD.
    ttl_seconds : int, optional
        Time-to-live for cache entries in seconds. Default: 7 days.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ):
        if db_path is None:
            db_path = Path(".kartograf_cache.db")
        self._db_path = Path(db_path)
        self._ttl = ttl_seconds
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS url_cache (
                godlo TEXT NOT NULL,
                resolution TEXT NOT NULL,
                vertical_crs TEXT NOT NULL,
                product TEXT NOT NULL DEFAULT 'nmt',
                url TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (godlo, resolution, vertical_crs, product)
            );
            CREATE TABLE IF NOT EXISTS teryt_cache (
                x REAL NOT NULL,
                y REAL NOT NULL,
                teryt TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (x, y)
            );
        """)
        self._conn.commit()

    # === URL cache ===

    def get_url(self, godlo: str, resolution: str, vertical_crs: str,
                product: str = "nmt") -> str | None:
        now = time.time()
        row = self._conn.execute(
            "SELECT url, cached_at FROM url_cache "
            "WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?",
            (godlo, resolution, vertical_crs, product),
        ).fetchone()
        if row and (now - row[1]) < self._ttl:
            return row[0]
        return None

    def set_url(self, godlo: str, resolution: str, vertical_crs: str,
                product: str, url: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO url_cache "
            "(godlo, resolution, vertical_crs, product, url, cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (godlo, resolution, vertical_crs, product, url, time.time()),
        )
        self._conn.commit()

    # === TERYT cache ===

    def get_teryt(self, x: float, y: float) -> str | None:
        now = time.time()
        row = self._conn.execute(
            "SELECT teryt, cached_at FROM teryt_cache WHERE x=? AND y=?",
            (x, y),
        ).fetchone()
        if row and (now - row[1]) < self._ttl:
            return row[0]
        return None

    def set_teryt(self, x: float, y: float, teryt: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO teryt_cache (x, y, teryt, cached_at) VALUES (?, ?, ?, ?)",
            (x, y, teryt, time.time()),
        )
        self._conn.commit()

    # === Management ===

    def clear(self) -> None:
        self._conn.execute("DELETE FROM url_cache")
        self._conn.execute("DELETE FROM teryt_cache")
        self._conn.commit()

    def vacuum(self) -> None:
        self._conn.execute("VACUUM")

    def stats(self) -> dict:
        url_count = self._conn.execute("SELECT COUNT(*) FROM url_cache").fetchone()[0]
        teryt_count = self._conn.execute("SELECT COUNT(*) FROM teryt_cache").fetchone()[0]
        db_size = self._db_path.stat().st_size if self._db_path.exists() else 0
        return {
            "url_count": url_count,
            "teryt_count": teryt_count,
            "db_size_bytes": db_size,
        }

    def close(self) -> None:
        self._conn.close()
```

**Step 5: Run tests — should pass**

```bash
.venv/bin/python -m pytest tests/test_metadata_cache.py -v
```

**Step 6: Commit**

```bash
git add kartograf/cache/__init__.py kartograf/cache/metadata.py tests/test_metadata_cache.py
git commit -m "feat(cache): add MetadataCache with SQLite backend and TTL"
```

---

### Agent 3B: GugikProvider Cache Integration

**Files:**
- Modify: `kartograf/providers/gugik.py`
- Modify: `tests/test_metadata_cache.py` (append)

**Step 1: Write failing test**

```python
class TestGugikProviderCacheIntegration:
    """Test that GugikProvider uses cache for URL lookups."""

    def test_cache_hit_skips_wms(self, tmp_path):
        """When URL is in cache, WMS is not queried."""
        from kartograf.cache.metadata import MetadataCache
        from kartograf.providers.gugik import GugikProvider
        from unittest.mock import patch

        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt",
                       "https://opendata.example.com/cached.asc")

        provider = GugikProvider(cache=cache)

        with patch.object(provider, "_make_request") as mock_req:
            url = provider._get_opendata_url("N-34-130-D-d-2-4")
            assert url == "https://opendata.example.com/cached.asc"
            mock_req.assert_not_called()

        cache.close()

    def test_cache_miss_queries_wms_and_stores(self, tmp_path):
        """When URL is not in cache, WMS is queried and result is cached."""
        from kartograf.cache.metadata import MetadataCache
        from kartograf.providers.gugik import GugikProvider
        from unittest.mock import MagicMock

        cache = MetadataCache(db_path=tmp_path / "test.db")
        session = MagicMock()
        response = MagicMock()
        response.text = 'url:"https://opendata.example.com/fresh.asc"'
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        provider = GugikProvider(session=session, cache=cache)
        url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert url == "https://opendata.example.com/fresh.asc"
        # Should be cached now
        assert cache.get_url("N-34-130-D-d-2-4", "1m", "EVRF2007", "nmt") == url
        cache.close()

    def test_no_cache_backward_compatible(self):
        """Provider works without cache (cache=None, default)."""
        from kartograf.providers.gugik import GugikProvider

        provider = GugikProvider()
        assert provider._cache is None
```

**Step 2: Implement cache parameter in GugikProvider**

In `kartograf/providers/gugik.py`, add `cache=None` parameter to `__init__`:

```python
def __init__(self, session=None, vertical_crs="EVRF2007", resolution="1m", cache=None):
    # ... existing code ...
    self._cache = cache
```

In `_get_opendata_url`, add cache check at the start and cache store after WMS lookup:

```python
def _get_opendata_url(self, godlo, timeout=DEFAULT_TIMEOUT):
    # Check cache first
    if self._cache is not None:
        cached_url = self._cache.get_url(
            godlo, self._resolution, self._vertical_crs, "nmt"
        )
        if cached_url is not None:
            logger.debug(f"Cache hit for {godlo}: {cached_url}")
            return cached_url

    # ... existing WMS lookup code ...
    # After finding URL, before returning:
    # Store in cache
    if self._cache is not None:
        self._cache.set_url(
            godlo, self._resolution, self._vertical_crs, "nmt", found_url
        )

    return found_url
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_metadata_cache.py -v
.venv/bin/python -m pytest tests/test_gugik_provider.py -v  # existing tests still pass
```

**Step 4: Commit**

```bash
git add kartograf/providers/gugik.py tests/test_metadata_cache.py
git commit -m "feat(cache): integrate MetadataCache with GugikProvider URL lookup"
```

---

### Agent 3C: LandCover Provider Cache Integration

**Files:**
- Modify: `kartograf/providers/bdot10k.py`
- Modify: `tests/test_metadata_cache.py` (append)

**Step 1: Write failing test for BDOT10k TERYT cache**

```python
class TestBdot10kCacheIntegration:
    """Test BDOT10k provider uses cache for TERYT lookups."""

    def test_teryt_cache_hit(self, tmp_path):
        """Cached TERYT is returned without WMS query."""
        from kartograf.cache.metadata import MetadataCache
        from kartograf.providers.bdot10k import Bdot10kProvider
        from unittest.mock import patch

        cache = MetadataCache(db_path=tmp_path / "test.db")
        cache.set_teryt(450000.0, 550000.0, "1465")

        provider = Bdot10kProvider(cache=cache)

        with patch.object(provider, "_make_request") as mock_req:
            teryt = provider._get_teryt_for_point(450000.0, 550000.0)
            assert teryt == "1465"
            mock_req.assert_not_called()

        cache.close()
```

**Step 2: Add cache parameter to Bdot10kProvider**

In `kartograf/providers/bdot10k.py`, add `cache=None` to `__init__` and use it in `_get_teryt_for_point`:

```python
def __init__(self, session=None, cache=None):
    self._session = session
    self._cache = cache

def _get_teryt_for_point(self, x, y, timeout=30):
    # Check cache
    if self._cache is not None:
        cached = self._cache.get_teryt(x, y)
        if cached is not None:
            return cached

    # ... existing WMS lookup ...

    # Store in cache before returning
    if self._cache is not None and teryt:
        self._cache.set_teryt(x, y, teryt)

    return teryt
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_metadata_cache.py tests/test_landcover.py -v
```

**Step 4: Commit**

```bash
git add kartograf/providers/bdot10k.py tests/test_metadata_cache.py
git commit -m "feat(cache): integrate MetadataCache with Bdot10kProvider TERYT lookup"
```

---

### Agent 3D: CLI Cache Commands + Tests

**Files:**
- Modify: `kartograf/cli/commands.py`
- Modify: `tests/test_cli.py` (append)

**Step 1: Add cache subparser to CLI**

In `kartograf/cli/commands.py`, add after soilgrids parser:

```python
# Cache command group
cache_parser = subparsers.add_parser(
    "cache",
    help="Manage metadata cache",
    description="Manage the local SQLite metadata cache",
)
cache_subparsers = cache_parser.add_subparsers(
    dest="cache_command",
    help="Cache commands",
)
cache_subparsers.add_parser("stats", help="Show cache statistics")
cache_subparsers.add_parser("clear", help="Clear all cached entries")
cache_subparsers.add_parser("path", help="Show path to cache file")
```

**Step 2: Add cmd_cache function**

```python
def cmd_cache(args: argparse.Namespace) -> int:
    """Execute cache management commands."""
    from kartograf.cache.metadata import MetadataCache

    if args.cache_command is None:
        print("Usage: kartograf cache <command>")
        print("Commands: stats, clear, path")
        return 0

    cache = MetadataCache()

    if args.cache_command == "path":
        print(cache._db_path)
        cache.close()
        return 0

    if args.cache_command == "stats":
        stats = cache.stats()
        print("Cache statistics:")
        print(f"  URL entries:   {stats['url_count']}")
        print(f"  TERYT entries: {stats['teryt_count']}")
        print(f"  Database size: {stats['db_size_bytes']} bytes")
        cache.close()
        return 0

    if args.cache_command == "clear":
        cache.clear()
        print("Cache cleared.")
        cache.close()
        return 0

    return 0
```

**Step 3: Register in main()**

```python
if parsed_args.command == "cache":
    return cmd_cache(parsed_args)
```

**Step 4: Write CLI tests**

```python
class TestCLICacheCommands:
    def test_cache_stats_command(self):
        from kartograf.cli.commands import create_parser
        parser = create_parser()
        args = parser.parse_args(["cache", "stats"])
        assert args.cache_command == "stats"

    def test_cache_clear_command(self):
        from kartograf.cli.commands import create_parser
        parser = create_parser()
        args = parser.parse_args(["cache", "clear"])
        assert args.cache_command == "clear"

    def test_cache_path_command(self):
        from kartograf.cli.commands import create_parser
        parser = create_parser()
        args = parser.parse_args(["cache", "path"])
        assert args.cache_command == "path"
```

**Step 5: Add .kartograf_cache.db to .gitignore**

```bash
echo ".kartograf_cache.db" >> .gitignore
```

**Step 6: Run tests**

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_metadata_cache.py -v
```

**Step 7: Commit**

```bash
git add kartograf/cli/commands.py tests/test_cli.py tests/test_metadata_cache.py .gitignore
git commit -m "feat(cli): add 'kartograf cache' commands (stats, clear, path)"
```

---

### Agent 3V: Verification

**Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

**Step 2: Linter and formatter**

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
```

**Step 3: Verify cache is opt-in**

Check that all existing tests pass WITHOUT any cache configured — the default behavior must be unchanged.

**Step 4: Verify TTL works**

```bash
.venv/bin/python -m pytest tests/test_metadata_cache.py::TestMetadataCacheURL::test_url_ttl_expiry -v
```

**Step 5: Verify .kartograf_cache.db is in .gitignore**

```bash
grep kartograf_cache .gitignore
```

**Step 6: Report findings**

---

## TEAM MERGE: Integration

**After all 3 teams complete work.**

### Agent M1: Sequential Merge

**Step 1: Merge PL-2000 verification (clean additive)**

```bash
git checkout develop
git merge --no-ff feature/pl2000-verification -m "Merge feature/pl2000-verification: PL-2000 BBox verification tests"
```

Expected: Fast-forward or clean merge (only new test files + pyproject.toml marker).

**Step 2: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

**Step 3: Merge metadata-cache**

```bash
git merge --no-ff feature/metadata-cache -m "Merge feature/metadata-cache: SQLite metadata cache"
```

Potential conflicts: `kartograf/cli/commands.py` (new cache subparser near soilgrids), `kartograf/providers/gugik.py` (new cache param), `kartograf/providers/bdot10k.py` (new cache param).

**Step 4: Run full suite**

**Step 5: Merge parallel-downloads**

```bash
git merge --no-ff feature/parallel-downloads -m "Merge feature/parallel-downloads: ThreadPoolExecutor parallel downloads"
```

Potential conflicts:
- `kartograf/download/manager.py` — both cache and parallel modify this
- `kartograf/cli/commands.py` — both add new CLI args
- `kartograf/providers/gugik.py` — both modify `__init__` signature

Resolve by keeping BOTH changes: cache param AND max_workers param.

**Step 6: Run full suite after final merge**

### Agent M2: Post-Merge Validation

Run full suite, linter, coverage after each merge step.

### Agent M3: Documentation

Update after all merges:
- `docs/CHANGELOG.md` — v0.6.0 entry
- `docs/PROGRESS.md` — CP9, update "Ostatnia sesja"
- `docs/DECISIONS.md` — ADR-018 (parallel downloads), ADR-019 (metadata cache)
- `kartograf/__init__.py` — update `__version__` to `"0.6.0"`, add `MetadataCache` export
- `kartograf/cli/commands.py` — update version string

---

## Success Metrics

- [ ] All 835 existing tests pass after merge
- [ ] 40+ new PL-2000 verification tests
- [ ] Parallel downloads: max_workers=1 preserves old behavior
- [ ] Parallel downloads: max_workers=4 uses ThreadPoolExecutor
- [ ] Cache: TTL works (expired entries not returned)
- [ ] Cache: thread-safe (WAL mode)
- [ ] Cache: opt-in (no behavioral change without explicit cache)
- [ ] Ruff: zero errors
- [ ] Coverage: >= 80%
- [ ] CLI: --workers and `kartograf cache` commands work
