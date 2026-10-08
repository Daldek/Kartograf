# Pre-flight audit — plan `2026-09-28-fala-review-max-i-wycinek-biblioteczny.md`

- **Date:** 2026-09-28, repo `develop` @ `81e71cb` (clean tree, nothing tracked modified by this audit)
- **Auditor:** pre-flight agent (opus), single reader of the whole plan (3196 lines) + spec
  `docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md`
- **Method (evidence, not reading):**
  1. Every file:line / symbol / helper / fixture the plan names was checked against live code (see "Anchors verified" at the end).
  2. **Full simulation**: a scratch copy of `kartograf/` + `tests/` + `pyproject.toml`
     (`/tmp/claude-1001/-home-claude-agent-workspace-Kartograf/ab64b7b0-0e04-4f07-adec-4e0421a37ffb/scratchpad/sim`, own git history,
     one commit per task) had the plan's code blocks applied task by task (Zad. 2-16; code blocks of Zad. 8/9/10/11/12/13 extracted
     verbatim from the plan file by line range). For each task: RED run of the new tests on the previous state, GREEN run, full suite
     (`-m "not live"`), and **every listed mutation proof executed** (sed/python edit -> pytest -> `git checkout`).
  3. `mypy kartograf/` on the simulated end state, diffed (list, no line numbers) against `mypy-baseline.txt`.
  4. Targeted experiments (Hydrograf `.prj` CRS equality, fd usage under lowered RLIMIT, ramp error decomposition, 19°E selection).
- **Result in one line:** the plan is executable end to end, but as written **2 tasks halt** (Zad. 4, Zad. 9), **12 existing/new tests break
  or fail to defend** behaviour; with the corrections proposed below the simulated end state is green:
  **1835 passed, 8 deselected (live)**, mypy error list **identical to baseline (32)**.

Counts: **BLOCKING 2 · IMPORTANT 5 · MINOR 14**.

---

## (a) Cross-task consistency (every pair sharing a file or an interface)

| A | B | Shared file / interface | A produces vs B consumes | Finding |
|---|---|---|---|---|
| 1 | 8 | `CLAUDE.md` | 1: `--force` sentence L297-298; 8: module tree L90-92 (`cutout.py` line) | OK, disjoint hunks |
| 1 | 9 | `CLAUDE.md` `--target-crs` PL bullet | 1: L297-298; 9: "`EPSG:2180` = sam crop" L294 | OK |
| 1 | 10 | `CLAUDE.md`, `docs/DECISIONS.md` | 1: L297-298 + ADR-027 L1036-1038/L1046-1048; 10: "failed arkusz = kod 1" L294 + new paragraph appended after ADR-027 Konsekwencje | OK (10 appends after the text 1 rewrote) |
| 1 | 15 | `CLAUDE.md` | 15: L112-115 (data layout) | OK |
| 1 | 17 | `CLAUDE.md`, `DECISIONS.md` | 17 greps for strings 1 removes (`odswiez albo nic` ...) | OK — today the grep hits exactly the 4 lines 1 rewrites (verified) |
| 9 | 10 | `CLAUDE.md` L294 (same sentence) | both rewrite substrings of one sentence | OK if applied on current text (both give substrings, not whole lines) |
| 8 | 9, 10, 15, 17 | `CLAUDE.md` | tree / bullet / layout / review | OK — but "Mapa plikow" says CLAUDE.md only in 1, 17 → **P-13** |
| 10 | 17 | `DECISIONS.md` ADR-027 | 10 addendum R5; 17 second addendum | OK |
| 2 | 3 | `transport/mosaic.py`, `tests/test_transport_mosaic.py` | 2: sequential metadata loop + `merge(paths)`; 3 adds `transforms` + `snap_to_source_grid`; test imports `os, sys` (2) + `logging` (3) | OK (simulated RED/GREEN) |
| 3 | 4 | `mosaic.py` metadata loop | 3's `_snap_outward(bounds, paths, transforms)` consumes `transforms`; 4 rewrites the loop to `metas` without saying to keep/derive `transforms` | **P-20** (MINOR) |
| 2 | 4 | fd tests | 2: headroom 64; 4: headroom 160 | 160 masks mutation 4 → **P-05** |
| 2,3,4 | CZ (`providers/cuzk/client.py:182`) | `mosaic_and_crop(tile_paths, bbox, out, nodata=)` | defaults `snap=False, assign_crs=None, dtype=None` | OK — `test_cuzk_client.py`/`test_cuzk_dmr.py` green after each of 2/3/4 |
| 3 | 9 | `snap_to_source_grid=True` | consumed in `build_pl_cutout` | OK (verified exact values) |
| 4 | 9 | `assign_crs="EPSG:2180"`, `dtype="float32"` | consumed in `build_pl_cutout` | 4's CRS check rejects every WKT1 EPSG:2180 → 9's `test_mixed_prj_cache_builds` fails → **P-01** |
| 4 | 11 | `dst_kwds` overlay on VRT-first profile | 11 adds `compress/predictor/tiled/512/bigtiff` | OK; measured: without explicit 512 blocks `RasterBlockError` still occurs after 9 → **P-19** |
| 3,4,9 | 17 | E2E (grid `mod 5 == 2.5`, independent warp) | consistent | E2E copies only `.asc` → real Hydrograf `.prj` never exercised → **P-21** |
| 5 | 9 | `find_sheets_for_bbox` used by `select_pl_cutout_sheets` | independent | OK |
| 5 | 17 | backlog "4-corner envelope in corine/soilgrids" | `parser_2000._transform_bbox_to_wgs84` (same 4-corner pattern, used by `--system 2000`) not mentioned | **P-15** |
| 6 | 7 | `DownloadResult.no_coverage`, status `"no_coverage"` in `_download_single_sheet_task` + both hierarchy helpers | `download_sheets` reuses the helpers | OK |
| 6 | 8 | `kartograf/__init__.py` | 6: `NoCoverageError` in exceptions import + `__all__`; 8: new cutout import block + `__all__` section | OK, disjoint; isort order OK (ruff I001 clean in sim) |
| 6 | 10 | `summary.no_coverage` → `missing_sheets` | consumed in `run_pl_cutout` | OK |
| 6 | 17 | E2E (c) provider raises `NoCoverageError` | consistent | OK |
| 7 | 8 | `download_sheets(godla, skip_existing=, on_progress=)` + `last_result` | `run_pl_cutout` calls with keywords; harness mocks `download_sheets.return_value` + `last_result=DownloadResult(...)` | OK |
| 7 | 11 | `DownloadManager.expand_sheets` (staticmethod) | `estimate_pl_cutout_bytes`; in CLI harness the class is a MagicMock → empty iteration (as the plan notes) | OK (verified) |
| 8 | 9 | `build_pl_cutout` (mosaic call), `select_pl_cutout_sheets` (selection); `_run`, `_CUT` | 9 edits both, uses `_run` for CLI test | OK |
| 8 | 10 | `PlCutoutResult`, `write_pl_cutout_sidecar`, `run_pl_cutout`, `_download_pl_cutout`, `_run` | 10 adds `missing_sheets`, replaces the failed-block, adds `Warning:`, harness `no_coverage=()` | OK; `run_pl_cutout` docstring from 8 becomes false → **P-14** |
| 8 | 11 | `PlCutout`, `run_pl_cutout`, `build_pl_cutout`, `_download_pl_cutout`, `_run` | 11 adds props, disk check before `DownloadManager`, `dst_kwds` variable, `Info:`; `TestDownloadPlBboxCutout()._run(...)` callable from another class | OK (verified) |
| 8 | 12 | `_download_pl_geometry(args, filepath, parent_request, bbox)` | 12's fake has the same signature | OK; but 12 breaks 8's re-pointed `test_cli_geometry_target_crs_reaches_worker` → **P-03** |
| 8 | 13 | `run_pl_cutout` build call | 13 wraps it in `try/except BaseException: prune; raise` | OK |
| 8 | (existing) | harness `_run` replaces `_DL` patches | `test_without_target_crs_behaviour_unchanged` still runs the non-cutout path that needs `_DL` patches | **P-04** |
| 9 | 10 | `test_pl_cutout.py` classes | `TestSheetGrid` (`_write_grid_sheet`) vs `TestMissingSheets` (`_write_sheet_asc`, `TestLibraryApi._SHEETS`) | OK |
| 9 | 11 | mosaic call `dst_kwds={...}` literal → variable | 11's spy reads `kwargs["dst_kwds"]` | OK |
| 9 | 13 | `_reject_pl2000_sheets` before `mkdir` | prune after it is a no-op (rmdir of missing dir → OSError → return) | OK |
| 10 | 11 | `_download_pl_cutout` | 11 `Info:` before `run_pl_cutout`, 10 `Warning:` after it | OK |
| 10 | 13 | `TestMissingSheets._cutout/_provider` | reused by 13's test (13 after 10) | OK; 13's test has no class named → **P-18** |
| 11 | 13 | disk check in `run_pl_cutout` | runs for real in 13's test | OK |
| 12 | 13, 15 | `cli/download_cmd.py` | different functions (`_cmd_download_geometry`, `_cz_download_bbox`, `_cmd_download_laz`) | OK |
| 13 | 15 | `download/storage.py` | module fn `prune_empty_dirs` vs `_resolved_subdir`/`get_raw_path` | OK, disjoint |
| 13 | 16 | `download/storage.py` | module fn vs maps/`_subdir`/top-level `get_source` import | OK; no import cycle (verified `import kartograf`) |
| 15 | 16 | `FileStorage._subdir` / `_resolved_subdir` | 15 reads `self._subdir`, 16 changes where the template comes from (`laz` → registry, same string) | OK |
| 14 | 7, 8 | `SourceDescriptor.resolve_subdir` | manager passes provider vcrs; `prepare_pl_cutout` validates vcrs first | OK |
| 14 | 15, 16 | `resolve_subdir` | 15 removes the CLI LAZ call; 16 does not call it | OK |
| all | all | `docs/CHANGELOG.md` 0.7.0 `### Added/Changed/Fixed/Tests` | sections exist (L154/L298/L423/L542) | OK |

---

## (b) Per-task self-consistency

| Zad. | Verdict | Notes (simulated) |
|---|---|---|
| 0 | done (HEAD `81e71cb`) | Expected line "`1787 passed` (+ deselected `live`)" is inaccurate: default `pytest tests/ -q` does **not** deselect `live` (no `addopts -m`), 1787 includes 8 network tests; offline = 1779 → **P-16** |
| 1 | OK | Old texts match CLAUDE.md L297-298 and DECISIONS.md L1036-1038 / L1046-1048 byte-for-byte; new texts true vs code (CZ deletes: `dmr.py:557-558`, `client.py:186`); Step 5 grep today returns exactly those 4 lines |
| 2 | OK | RED = `Too many open files` (t065.tif), GREEN; ExitStack mutation FAILs; CZ tests green |
| 3 | OK (ruff) | RED `TypeError`, GREEN; mutations 1-4 all FAIL as claimed; code has 3 × `zip()` without `strict=` (B905 enabled) → **P-11** |
| 4 | **Broken** | Specified CRS check makes its own `test_assign_crs_merges_sources_with_and_without_prj` FAIL → **P-01**; mutation 4 survives at headroom 160 → **P-05**; mutation 5 fails at write, not at the `driver` assertion → **P-17**; `metas` vs `transforms` → **P-20** |
| 5 | OK (claims) | RED (6 missing) / GREEN; sanity condition holds for all 6 (310-427 points each); mutation FAILs; no existing test breaks (full run with the change: 1779 pass). Fix adds 10 sheets of which 4 do **not** intersect the bbox → Step 4 rule and CHANGELOG wording → **P-08**, **P-15** |
| 6 | OK (claim) | RED/GREEN; full suite green; mutation (1) claims "test managera FAIL" — false → **P-10** |
| 7 | **Mutation dead** | RED/GREEN; mutation (1) FAILs 3 tests; (2) (lazy/generator) FAILs 5; **(3) survives** (all 9 tests pass) → **P-06** |
| 8 | **1 broken test** | cutout.py extracted verbatim imports and works; full suite: 1 failure `test_without_target_crs_behaviour_unchanged` → **P-04**; after fixing it, 33/33 cutout tests green; all 4 mutations FAIL as claimed; mypy: no new errors; re-pointing instructions imprecise → **P-12** |
| 9 | **Halts (Step 1a)** | Ramp test fails AFTER the fix (0.0257/0.0525 m vs thresholds 0.02/0.05; plan expected < 0.001) → **P-02**; `test_integer_first_sheet_keeps_decimals` passes BEFORE the fix → **P-07**; `test_mixed_prj_cache_builds` depends on P-01; other RED/GREEN OK; mutations (1)-(5) each FAIL their target test |
| 10 | OK | RED (4 tests) / GREEN; mutations 1,2,3,5 FAIL as claimed (4 trivially); `test_transport_failure_stays_fatal` is a guard (green before) though Step 2 says all "musza padac"; `run_pl_cutout` docstring stale → **P-14** |
| 11 | OK | RED/GREEN; mutations 1-3 FAIL; measured: dropping the 512 blocks still raises `RasterBlockError` after Zad. 9 → **P-19** |
| 12 | **10 broken tests** | New test RED/GREEN (default vs pinned envelope: dx -0.04/-0.06 m, dy -1.14/-1.16 m); mutation FAILs; but `read_source_crs` on stub files breaks 9 tests in `test_cli.py` + 1 in `test_pl_cutout.py` → **P-03**; commit list lacks `tests/test_pl_cutout.py` |
| 13 | OK | RED (5) / GREEN; mutations verified/analysed; test class unspecified, nested `with` = ruff SIM117 → **P-18**, **P-11** |
| 14 | OK | RED (4) / GREEN; mutation FAILs; no cycle (`descriptor` → `exceptions`) |
| 15 | OK (claim) | GREEN; six `TestLazTileUklad` cases pass; mutation (1) is caught by the pre-existing `"pl_2000_..." in str(...)` asserts, not by the new consistency assertion (tautological under that mutation) → **P-09** |
| 16 | OK | RED (`AttributeError ... get_source`) / GREEN; `TestDescriptorProviderConsistency` untouched (compares `storage._subdir`) |
| 17 | OK | Docs/E2E; E2E does not exercise a real Hydrograf `.prj` → **P-21** |

---

## (c) Findings

### P-01 — BLOCKING — Zad. 4 (and 9, 17): the "wymuszany" CRS check rejects every WKT1 flavour of EPSG:2180, incl. Hydrograf's real `.prj`

**Plan:** L603 and L734 — reject a source when
`not CRS.from_user_input(meta["crs"].to_wkt()).equals(target, ignore_axis_order=True)`.

**Evidence (pyproj 3.7.2 / PROJ 9.5.1, rasterio 1.5.0 / GDAL 3.12.1):**

| `.prj` content (read by rasterio) | plan check | `to_epsg(min_confidence=20)` | proj-dict == EPSG:2180 |
|---|---|---|---|
| `CRS.from_epsg(2180).to_wkt("WKT1_GDAL")` (the plan's own test fixture `_write_prj`) | **False** | 2180 | True |
| `to_wkt("WKT1_ESRI")` | **False** | 2180 | True |
| **real Hydrograf file** `Hydrograf/cache/nmt/nmt_5m/N-34/139/A/c/4/4/N-34-139-A-c-4-4.prj` (`gdalsrsinfo -o wkt_simple`, see `raster_utils.py:67-99`) | **False** | 2180 | True |
| old "ETRS89 / Poland CS92" WKT1 | **False** | 2180 | True |
| WKT2 of EPSG:2180 | True | 2180 | True |
| EPSG:2177 / 2176 WKT1_GDAL | False | 2177 / 2176 | **False** |

Simulated Zad. 4 exactly as specified: `test_assign_crs_merges_sources_with_and_without_prj` FAILS with
`ValidationError: ... ma CRS PROJCS["ETRF2000-PL / CS92" ... AUTHORITY["EPSG","2180"]], a wymuszany jest EPSG:2180`
(Zad. 9 `test_mixed_prj_cache_builds` fails the same way). rasterio `CRS.__eq__` is also False for these pairs.
In production the fix for fact 6 would turn "CRS mismatch" into a permanent "wymuszany" error for every cutout over a
Hydrograf-touched cache — the exact case fact 6 targets. `rasterio.crs.CRS.to_epsg()` is not a way out either
(returns None for the WKT1_GDAL variant).

**Correction (verified: all 2180 variants merge, 2177 rejected, suite green):** in Zad. 4 Step 3 replace the bullet at L734 by
"`... i not _same_projection(meta["crs"], target)` -> `ValidationError(...)`" and add (plus `import warnings`):

```python
def _same_projection(src_crs, target: CRS) -> bool:
    """Czy CRS zrodla to uklad wymuszany?

    Samo ``CRS.equals(..., ignore_axis_order=True)`` NIE wystarcza: kazdy WKT1
    EPSG:2180 (WKT1_GDAL z pyproj, ESRI, ``gdalsrsinfo -o wkt_simple`` z .prj
    Hydrografu) daje False (zmierzone 2026-09-28, pyproj 3.7.2 / PROJ 9.5.1),
    wiec porownujemy takze parametry odwzorowania (slownik PROJ.4).
    """
    candidate = CRS.from_user_input(src_crs.to_wkt())
    if candidate.equals(target, ignore_axis_order=True):
        return True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # to_dict() ostrzega o PROJ.4
        return candidate.to_dict() == target.to_dict()
```

and parametrize `test_assign_crs_merges_sources_with_and_without_prj` over three `.prj` texts: `WKT1_GDAL`, `WKT1_ESRI`
and the verbatim Hydrograf string

```python
_HYDROGRAF_2180_WKT = (  # tresc .prj z cache Hydrografu (gdalsrsinfo -o wkt_simple)
    'PROJCS["ETRF2000-PL / CS92",GEOGCS["ETRF2000-PL",DATUM["ETRF2000_Poland",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",19],'
    'PARAMETER["scale_factor",0.9993],PARAMETER["false_easting",500000],'
    'PARAMETER["false_northing",-5300000],UNIT["metre",1]]'
)
```

New mutation proof: "replace `_same_projection` by plain `.equals(...)` → the Hydrograf/ESRI/WKT1 variants FAIL".
Also fix the Interfaces sentence at L603 ("porownanie `pyproj.CRS.equals(...)`") accordingly.

### P-02 — BLOCKING — Zad. 9: the ramp test cannot pass after the fix; Step 1a orders STOP

**Plan:** L2046-2071 thresholds `err.mean() < 0.02 and err.max() < 0.05`; L2073 "po < 0,001 m ... jesli po naprawie blad > prog — STOP".

**Evidence (full Zad. 2-9 simulated):**
- before the fix (snap off): mean 0.347 m, max 0.616 m (plan's range OK);
- **after the fix: mean 0.0257 m, max 0.0525 m → FAIL** (both thresholds exceeded).
- Decomposition: the snapped mosaic equals the ramp to 6.1e-6 m; manual bilinear on the mosaic at pyproj inverse coordinates:
  1.2e-6 m; `rasterio.warp.reproject(..., tolerance=0.0)` gives the same 0.0257/0.0525 (not the approx transformer).
  Warping pure coordinate rasters shows GDAL's dst→src mapping differs from `pinned._transformer` INVERSE by up to
  0.075 m in northing (column-periodic). So the residual is inherent to the frozen warp stage (`transform/raster.py`), not
  to the mosaic being fixed — the plan's "< 0.001 m" expectation is false.

**Correction (verified: bit-identical after the fix; before the fix mean 0.350 / max 0.639 m, 100 % pixels differ):**
replace the pyproj-based assertion by a comparison with `warp_to_grid` of an ideal single-raster source on the sheet grid —
this isolates exactly what Zad. 9 fixes (the mosaic stage):

```python
    def test_target_5514_warp_has_no_subpixel_shift(self, tmp_path):
        """Rampa liniowa: wycinek z arkuszy == warp idealnego rastra na siatce
        arkuszy (ta sama operacja przypieta, ta sama siatka wyniku). Kazde
        przesuniecie tresci w mozaice wychodzi jako rozbieznosc (bez naprawy:
        srednio 0,35 m, maks. 0,64 m; po naprawie: 0)."""
        from rasterio.transform import from_origin

        from kartograf.download.cutout import build_pl_cutout, prepare_pl_cutout
        from kartograf.transform.raster import warp_to_grid

        def ramp(gx, gy):
            return 0.3 * (gx - 529950.0) + 0.7 * (gy - 381950.0)

        sheets = self._sheets(tmp_path, ramp)
        cut = prepare_pl_cutout(
            BBox(530010.37, 382010.61, 530150.29, 382085.43, "EPSG:2180"),
            "EPSG:5514", output_dir=tmp_path, resolution="1m", vertical_crs="EVRF2007",
        )
        build_pl_cutout(sheets, cut.bbox_source_2180, cut.bbox_target, 1.0,
                        cut.pinned, cut.target_path)
        cols, rows = np.meshgrid(np.arange(310), np.arange(200))  # suma obu arkuszy
        ideal = tmp_path / "ideal.tif"
        with rasterio.open(ideal, "w", driver="GTiff", width=310, height=200, count=1,
                           dtype="float32", crs="EPSG:2180", nodata=_NODATA,
                           transform=from_origin(529950.5, 382150.5, 1.0, 1.0)) as dst:
            dst.write(ramp(529950.5 + cols + 0.5, 382150.5 - rows - 0.5).astype("float32"), 1)
        ref = tmp_path / "ref.tif"
        warp_to_grid(ideal, ref, cut.bbox_target, 1.0, cut.pinned,
                     src_crs="EPSG:2180", nodata=_NODATA)
        with rasterio.open(cut.target_path) as got, rasterio.open(ref) as exp:
            assert got.transform == exp.transform
            np.testing.assert_array_equal(got.read(1), exp.read(1))
```

Drop Step 1a (or rewrite it as "measured: after 0 / before 0.35 m mean"). If the pyproj-based variant is kept instead,
the thresholds must be recalibrated from measurement (e.g. mean < 0.05, max < 0.1: before-fix is 6.9x / 6.2x above) and
the "< 0,001 m" sentence removed. Zad. 17 E2E (b) should expect the same ~cm-level GDAL-vs-pyproj residual.

### P-03 — IMPORTANT — Zad. 12: `_geometry_envelope` breaks 10 existing tests (unmentioned)

**Plan:** L2746-2754 calls `read_source_crs(filepath, layer=layer)` before `get_overall_bbox`; L2758 only anticipates
`parent_request` tests.

**Evidence:** simulated Zad. 12 → 10 failures, all tests that patch `kartograf.core.geometry.get_overall_bbox` but pass a
stub geometry file (`touch()` / `b"stub"`): `read_source_crs` raises `ValidationError: Missing .prj ...` (stub `.shp`) or
`sqlite3.DatabaseError` (stub `.gpkg`):
`tests/test_cli.py::TestAreaModeHierarchyExitCode::test_geometry_coarse_scale_failure_returns_exit_1`,
`TestCmdDownloadGeometry::test_download_geometry_basic`, `::test_download_geometry_with_layer`,
`::test_geometry_workers_1_sequential_collects_all_paths`,
`TestDownloadGeometrySystem::test_download_geometry_system_2000`, `::test_download_geometry_default_system_1992`,
`TestAutoSplitGeometry::test_geometry_border_splits`, `::test_geometry_pl_only_skips_cz`,
`::test_geometry_outside_known_countries`, and
`tests/test_pl_cutout.py::TestGeometryCutout::test_cli_geometry_target_crs_reaches_worker`.

**Correction (either verified green):**
- (A, preferred — tests stay honest) add to each of these 10 tests
  `patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))` (per test, NOT a class-level
  autouse: `TestAutoSplitGeometry` also hosts tests that need the real reader, incl. possibly the new Zad. 12 test);
  add `tests/test_pl_cutout.py` to the Zad. 12 commit list and to its Files list.
- (B) make the envelope tolerant — behaviour-preserving because `get_overall_bbox` re-reads the CRS and reports the same
  error for a genuinely bad file:
  ```python
      import sqlite3
      try:
          source_crs = read_source_crs(filepath, layer=layer)
      except (ValidationError, ValueError, sqlite3.Error):
          source_crs = None  # get_overall_bbox zglosi blad pliku sam, czytelnie
      epsg = source_crs.to_epsg() if source_crs is not None else None
      if epsg is not None and str(epsg) in _CZ_CRS_WKIDS:
          ...
  ```
Either way Step 4 must name these tests.

### P-04 — IMPORTANT — Zad. 8: the new `_run` harness breaks `test_without_target_crs_behaviour_unchanged`

**Plan:** L1816-1834 replaces the `_DL` patches (`find_sheets_for_bbox`, `DownloadManager`, `_download_godlo_list`) by
`_CUT` patches in `TestDownloadPlBboxCutout._run`.

**Evidence:** that test (`tests/test_pl_cutout.py:458-467`) runs `_download_pl_bbox` with `target_crs=None`, i.e. the
non-cutout path, which still uses `_DL.find_sheets_for_bbox/DownloadManager/_download_godlo_list`. Simulated:
`AttributeError: 'types.SimpleNamespace' object has no attribute 'default_extension'` (real `DownloadManager`), and
its assertion `find.call_args.args[0] is _BBOX_2180` would target the `_CUT` mock that is never called.

**Correction:** add to Zad. 8 Step 3: "`test_without_target_crs_behaviour_unchanged` keeps its own `_DL` patches
(it exercises the non-cutout path)":

```python
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        with (
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-1"]) as find,
            patch(f"{_DL}._create_provider_and_storage",
                  return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock())),
            patch(f"{_DL}.DownloadManager"),
            patch(f"{_DL}._download_godlo_list", return_value=(sheets, [])),
        ):
            rc = _download_pl_bbox(_pl_args(tmp_path, target_crs=None), _BBOX_2180, _PARENT)
```
(assertions unchanged; verified green).

### P-05 — IMPORTANT — Zad. 4: fd-test headroom 160 lets mutation 4 ("open all VRTs at once") survive

**Plan:** L685-687 (`in_use + 160`, justified by the GDAL dataset pool), mutation 4 at L768.

**Evidence:** the correct Zad. 4 code passes with headroom **6**; the mutation (all 300 VRTs opened in an `ExitStack`,
passed as datasets to `merge`) **passes at 160** and **fails at 64** (`Too many open files` on `t064.tif`) — GDAL's VRT
source pool caps real fds at ~100, so any headroom above ~110 hides the regression the test exists for.

**Correction:** use `in_use + 64` (same as the Zad. 2 test) and replace the comment by the measurement:
`# poprawny kod potrzebuje < 6 deskryptorow; pula GDAL (100) maskowalaby "wszystkie VRT naraz" przy zapasie > ~110`.
Drop the Step 4 "STOP if > 100" (measured non-issue) or keep it as a report item.

### P-06 — IMPORTANT — Zad. 7: mutation proof (3) does not fail

**Plan:** L1267 "(3) `_download_single_sheet_task`: `except DownloadError` -> `raise` — `test_failures_collected_not_raised[4]` FAIL".

**Evidence:** executed — all 9 targeted tests PASS: `_download_hierarchy_parallel` catches the re-raised exception in its
generic `except Exception` (manager.py:554-571) and still appends to `failed`.

**Correction:** replace with "(3) `_download_hierarchy_sequential`: `except DownloadError as e:` body -> `raise` —
`test_failures_collected_not_raised[1]` FAIL" (executed: FAILs).

### P-07 — IMPORTANT — Zad. 9: `test_integer_first_sheet_keeps_decimals` is green before the change

**Plan:** L2089-2102 calls `build_pl_cutout([b, a], ...)`; Step 2 (L2142) lists "Int32" among expected RED failures.

**Evidence:** on the Zad. 8 state the test PASSES (executed): unsorted input puts the float sheet `b` first, so `merge`
takes float32 from it. The test only bites through mutation (3) `dtype=None` because the NEW code sorts `a` first.

**Correction:** call `build_pl_cutout([a, b], ...)` (RED holds: Int32 first → 100.0), or parametrize both orders
`[[a, b], [b, a]]` with the docstring "niezaleznie od kolejnosci wejscia".

### P-08 — MINOR — Zad. 5: the fix also over-selects; Step 4's rule is false

**Evidence:** for the plan's bbox the fix adds **10** sheets: the 6 expected plus `N-34-134-B-c-4-2`, `N-34-134-B-d-3-1`,
`N-34-135-A-c-4-2`, `N-34-135-A-d-3-1`, which do **not** intersect the bbox (dense-grid check, 2001 x 1001 points):
the WGS84 envelope now reaches the CM latitude over its full longitude range. No existing test changes (full suite with
the change: 1779 pass), so L873 ("nowy arkusz musi faktycznie przecinac bbox") never triggers — but if it did, it would
fail for legitimate envelope over-selection. In the cutout flow, over-selected sheets are downloaded and, near the coast,
can appear in `missing_sheets`/`Warning:` although they lie outside the user's area.

**Correction:** L873: "nowy arkusz musi przecinac obwiednie WGS84 bboxa; arkusze poza bboxem w 2180 to znana nadmiarowa
selekcja obwiedni (zmierzone: +4 dla bboxa z testu)"; mention over-selection in the CHANGELOG entry (L880-886).

### P-09 — MINOR — Zad. 15: mutation (1) attribution

**Plan:** L3049 "(1) `get_raw_path` ignoruje `uklad` — ... i asercja spojnosci CLI FAIL".
**Evidence:** the consistency assertion computes its expectation with the same (mutated) `get_raw_path`, so it stays green;
the CLI tests fail only via the pre-existing `"pl_2000_evrf2007" in str(sidecar.parent)` / `"pl_2000_kron86"` asserts
(executed). **Correction:** make the consistency assertion also check the literal segment
(`assert ("laz", "pl_2000_evrf2007") == target.parts[-10:-8]` style) or attribute the FAIL to the existing asserts.
Also refresh the docstring of `test_laz_segment_carries_vertical_crs_from_flag` (test_cli.py:2717 names `_storage_for`).

### P-10 — MINOR — Zad. 6: mutation (1) claims the manager test fails

**Plan:** L1098. The manager test's mock provider raises `NoCoverageError` itself; changing gugik.py's final raise
cannot affect it. Only test (a) fails. **Correction:** "(1) ... — test (a) FAIL".

### P-11 — MINOR — plan code is not ruff-clean after `ruff format`

**Evidence (ruff check after `ruff format` on the simulated end state):** B905 `zip()` without `strict=` at plan L528, L542
(Zad. 3) and in Zad. 4's two validation loops + wrapping loop (L744); SIM117 nested `with` in Zad. 13's
`test_failed_build_leaves_no_empty_bbox_dir` (L2823-2825); several E501 in long f-strings/comments `ruff format` cannot
wrap (cutout.py, download_cmd.py, test lines). **Correction:** `zip(..., strict=True)` everywhere (project already uses
it: `cuzk/client.py:283`, `parser_2000.py:186`); combine the two `with` in Zad. 13's test; wrap long strings.

### P-12 — MINOR — Zad. 8 Step 3 re-pointing is imprecise

- L1814 formula hardcodes `vertical_crs="EVRF2007"`; `test_vertical_kron86_lands_in_kron86_segment` must pass `"KRON86"`
  (the third positional arg), and `output_dir=str(tmp_path)` for the `_args` helper tests.
- `TestGeometryCutout`/`TestBorderTwoCutouts` have no `_run`; their inline patches must become
  `patch(f"{_CUT}.DownloadManager", return_value=<manager mock>)`, and
  `test_geometry_target_5514_covers_whole_envelope` needs
  `manager.download_sheets.side_effect = lambda godla, **kw: [sheets[g] for g in godla]`
  (it maps godla → sheets today via `_download_godlo_list` side_effect). Spell this out (verified working).
- Docstring of `test_cli_geometry_target_crs_reaches_worker` mentions the "guard R-12" that Zad. 8 removes.

### P-13 — MINOR — "Mapa plikow" is incomplete

L82 lists `CLAUDE.md`/`DECISIONS.md` for tasks 1, 17 only; CLAUDE.md is also edited by 8, 9, 10, 15 and DECISIONS.md by 10.
L94 says "reszta w 17", but README.md is edited in 8 and ARCHITECTURE.md in 15. Update the map.

### P-14 — MINOR — Zad. 10 leaves Zad. 8's `run_pl_cutout` docstring false

L1636-1637 ("Kazdy nieudany arkusz -> DownloadError z lista") contradicts R5 after Zad. 10; add to Zad. 10 Step 3
"docstring `run_pl_cutout`: brak danych -> nodata + `missing_sheets`; inne porazki -> `DownloadError`; zaden arkusz z
danymi -> `ValidationError`". Also note in Step 2 that `test_transport_failure_stays_fatal` is a guard (green before).

### P-15 — MINOR — Zad. 5 CHANGELOG/docstring overstate the scope

L884-885 "wszystkich trybow `--bbox`/`--geometry`": `--system 2000` goes through `find_sheets_2000_for_bbox`, which uses its
own 4-corner `parser_2000._transform_bbox_to_wgs84` (L690-707; for a 2180 bbox the zone bbox is derived from that
envelope) — not fixed (for the plan's bbox no PL-2000 sheet is missed, checked by dense sampling, but the pattern is the
same); EPSG:4326 bboxes are unaffected. Also the docstring (L834-836) says the CM point gives the extrema "na obu
krawedziach poziomych" — the bottom-edge minimum lies at the corners (the extra point is harmless). **Correction:**
restrict the CHANGELOG wording to PL-1992 selection from EPSG:2180 and add `parser_2000` to the backlog list in
"Zakonczenie" pt 2.

### P-16 — MINOR — the default test command is not offline

`pyproject.toml` has no `-m "not live"`; `pytest tests/ -q` runs the 8 `live` tests (network; they passed here, so the
count is 1787). Global Constraints call the suite "OFFLINE". **Correction:** use
`.venv/bin/python -m pytest tests/ -q -m "not live"` in gates (offline baseline **1779**), or state that 1787 includes 8
network tests.

### P-17 — MINOR — Zad. 4 mutation 5 wording

L769: removing `kwds.setdefault("driver", "GTiff")` fails at write (`RasterioIOError: Write failed` — VRT driver), before the
`src.driver == "GTiff"` assertion is reached (executed; 3 tests FAIL). Say "FAIL (zapis przez sterownik VRT)".

### P-18 — MINOR — Zad. 13: the pl_cutout test has no class

L2818 defines `test_failed_build_leaves_no_empty_bbox_dir(self, tmp_path)` without naming its class; put it in
`TestMissingSheets` (it reuses its `_cutout/_provider`) and flatten the nested `with` (SIM117).

### P-19 — MINOR — Zad. 11: "RasterBlockError may not appear after Zad. 9" — measured: it still appears

Removing `blockxsize/blockysize` with `tiled=True` on the VRT-first profile raises
`RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16` (executed). Replace the L2670
parenthetical with this fact (the 512 blocks are required, not just explicit).

### P-20 — MINOR — Zad. 4 must keep `transforms` for Zad. 3's `_snap_outward`

L732 introduces `metas` but `_snap_outward(bounds, paths, transforms)` (Zad. 3) still consumes `transforms`. Add
"`transforms = [m["transform"] for m in metas]`" to Step 3(b).

### P-21 — MINOR — Zad. 17 E2E never exercises a real Hydrograf `.prj`

Step 4 copies only `<godlo>.asc`. Copy the `.prj` for at least one sheet (all 1977 cached sheets have one) so fact 6 is
checked on the real WKT (this would have exposed P-01).

---

## Verified OK (anchors and claims the plan relies on)

- File:line anchors: `CLAUDE.md:294,297-298,112-115`; `DECISIONS.md:1036-1038,1046-1048`; `download_cmd.py` cutout block
  929-1185, `_download_pl_bbox` 1188, R-01 union 1980-1993, `_laz_uklad` 1391-1412, `_cz_download_bbox` mkdir 1722-1728;
  `gugik.py` fallback 549-553 / final raises 561-575; `manager.py` `_download_single_sheet_task` 409-442,
  `_download_hierarchy_parallel` except-Exception 554-571; `storage.py:110-150`, `_resolved_subdir` 162, `get_raw_path` 221;
  `descriptor.py:83-101`; `sheet_parser.py:927-959`; `_parser.py:112-121`; `cuzk/client.py:182,186`; `cuzk/dmr.py:557-558`;
  `transform/raster.py:133-137`; `README.md:83`; tests `test_cli.py:2461-2513` (`TestLazUklad`), `:3325`
  (`test_bbox_download_error_returns_1`), `:3406` (`_write_krovak_shp`, envelope -447000/-1114000/-446000/-1113000 in
  EPSG:5514 with WKT2 `.prj`), `:3206` (godlo no-dir mirror); `test_pl_cutout.py` helpers `_write_sheet_asc(path, west,
  south, size=100, pixel=1.0, apex=None)`, `_pl_args`, `_PARENT`, `_BBOX_2180`, `_APEX`, `_pinned_2180_to`, `_DL` (L271);
  `test_transport_mosaic.py::_write_tile(path, origin_x, origin_y, value, size=10, res=1.0, crs, nodata)`.
- APIs: `DownloadResult(succeeded, failed, skipped)` + `total`; `DownloadError(message, godlo=, status_code=)`; `BBox`
  NamedTuple positional; `SheetParser.get_bbox("EPSG:4326"/"EPSG:2180")`; `get_all_descendants` → `list[SheetParser]`
  (order -1..-4); `find_sheets_for_geometry(filepath, target_scale=, layer=, system=)`; `write_sidecar` →
  `<file>.meta.json`; `build_metadata(descriptor, *, request, vertical_crs, data_path, transform, extra, capability, nodata)`;
  `PinnedTransform._transformer` is a pyproj `Transformer` (INVERSE call works); `affine.Affine`, `pyproj.enums.TransformDirection`,
  `rasterio.io.MemoryFile(..., ext=".vrt")`, `merge(list_of_str_paths)` lazy per chunk (merge.py:459-460).
- Facts re-measured: fact 5 (`"100"` + `nodata_value -9999` → int32), fact 6 (VRT with forced SRS merges once the CRS check
  is fixed), fact 8 (exactly the 6 named sheets missed; 0 for 10 km; sanity condition 310-427 points per sheet), fact 10
  (tiled without blocks → `RasterBlockError`), `Counter.most_common(1)` tie → first encountered.
- Zad. 2/3/8/10/11/13/14/16 mutation proofs execute and FAIL as claimed; mypy end state = baseline list (32, no new).
