# Round 3 fixes (E2E 0.8.0) - branch integrate/e2e-fixes

Worktree `<worktree>`, base 114c03b3, 6 commits:
8270e78e (store, N-P2-1), ed6179ff (geometry, N-P3-4), 1515ea4c (year hint, N-P3-3), 7ec8990e (catalog, N-P3-2),
17184bed (ocd edition + volume wording, N-P3-7/6), 42ec581b (docs; DECISIONS.md CRLF checked: 4388/4388 lines).
Gate (`scripts/gate.sh`, once, before the commits): ruff check, ruff format --check, mypy, pytest offline: **GATE OK**,
7419 passed, 18 deselected. Live data only in `<katalog-danych>/R3/` (explicit `--output`), ~350 MB, no repo path written.
"Before" = `git archive 114c03b3` copy in scratch; "after" = worktree (`python -m kartograf` with cwd = worktree).

## 1. N-P2-1 file_footprint / OGC:CRS84 (P2) - DONE
- Cause: PROJ 9.8.1 gives the OGC:CRS84 -> EPSG:4326 axis swap accuracy -1 ("unknown"), the policy rejects it, `_same_crs`
  treated the pair as different; the first source's TransformUnavailableError aborted `file_footprint`. On the local PROJ 9.5.1
  the accuracy is 0.0, so the bug does NOT reproduce there; reproduced with the R2 venv python (PROJ 9.8.1) + worktree/baseline code.
- Change: `store_geometry._same_crs` = equal up to the axis order of a geographic CRS (`CRS.equals(ignore_axis_order=True)`) -> identity,
  no operation; `transform.crs.build_pinned_transform` accepts a pair equal up to axis order as exact (accuracy 0) whatever PROJ
  reports (public `pinned_transform("OGC:CRS84","EPSG:4326")` works too); `file_footprint` iterates the sources
  (request, sheet, header, unit) and skips one whose envelope raises `TransformError` (debug log), `None` when none is left; only
  DownloadError/ParseError of the network unit index still propagate. ETRS89 (EPSG:4258) is NOT treated as identity.
- Tests (offline, PROJ-independent, all fail on baseline): `test_crs84_request_is_the_wgs84_envelope_without_an_operation`,
  `test_a_source_without_a_safe_operation_falls_through_to_the_next[2 error classes]`, `TestBuildPinnedTransform::
  test_axis_swap_of_one_wgs84_is_exact_whatever_proj_reports`; `test_crs84_geopackage_header_is_the_wgs84_envelope` (real GDAL CRS84 GPKG;
  passes on baseline under PROJ 9.5.1, fails under 9.8.1).
- Live: store with 15 families / 60 entries (nmt sheet/cutout/bbox, CZ SM5/TM33, LAZ PL+CZ, orto cutout/CZ JPG, soil clay+hsg, admin,
  special, cadastre, hydro CZ, geodesy, names PL geographic/world + CZ, BDOT10k, models3d, maps CZ). PROJ 9.8.1, baseline:
  **6 entries RAISE TransformUnavailableError** (boundaries/pl_prg_special, names/pl_prng, names/pl_prng_world, link+version);
  worktree: 0 raising, all `request`. Header route (request bbox damaged): baseline raises for names, worktree
  `('header', WGS84 19.9323,50.0557,19.9445,50.0646)`. PROJ 9.5.1 worktree: 60 entries, 0 raising. `maps/cz_ztm` and `models3d`
  (teryt unit, needs `network=True`) give `None` - expected, unchanged.
- Docs: ARCHITECTURE 3.3.1, DECISIONS ADR-045 errata 3 (3) + index row, CHANGELOG (BREAKING bullet + Naprawione).

## 2. N-P3-4 point via --geometry - DONE
- Decision: a point / axis-parallel line (zero-area envelope) picks sheets, units, pixels -> accepted where that is the question
  (NMT/orto sheets, `boundaries`, `soil download`, `landcover` BDOT10k: verified live with `--check-updates`, rc 0, one unit each);
  cutout (PL+CZ), LAZ tiles (selection works on overlap area, a point selects nothing), `soil hsg`, and `elevation availability`
  (it printed `obszar 0,00 ha`, `brak ladu` for land) work on an AREA -> `ValidationError` `option="geometry"`,
  message "--geometry: obwiednia obiektow ma zerowa powierzchnie ...; <track> wymaga obszaru - podaj wielobok albo --bbox ...".
- Change: `options.geometry_area_error`/`require_geometry_area`; called in `data._dispatch_area` (cutout/LAZ, PL/CZ/auto),
  `_download_geometry` (explicit CZ cutout), `hsg._selection`, `availability` (`_area_polygons`, CZ and auto envelope).
  `validate_data_request`/`project add` now reject too (dry run used to pass).
- Tests (11 fail on baseline, 1 acceptance guard): `tests/test_validate_request.py` (6 download/validate parity rows, HSG, 4 availability).
- Live after (rc 2, option=geometry): NMT PL cutout point + hline, orto PL cutout, NMT CZ cutout, LAZ PL, LAZ CZ, HSG point + hline,
  availability NMT PL/LAZ PL/NMT CZ/auto. Before: same commands rc 2 with `option=bbox` (cutout/LAZ/HSG), availability rc 0 with 0,00 ha.
- Docs: CHANGELOG (E2E bbox bullet rewritten), DECISIONS (ADR errata 5 text), USAGE 1.2 + availability bullet.

## 3. N-P3-6 BDOT10k volume - PREMISE CORRECTED, wording fixed
- Finding: `within_volume` (shared by collections and `LandCoverManager._bdot_volume`) already HEADs EVERY package up to 100 files
  (sample of 5 only above 100, where the count refuses anyway) - so the 69-powiat area passed legitimately: measured live, all 69
  HEADs = **2,87 GB** (<10 GB). Only the message estimate above the limit misleads (378 powiats: "ok. 6,4 GB" vs 18 GB real).
- Change: estimate text marked "tylko orientacyjnie - rozmiary plikow sa bardzo rozne, a o odmowie decyduje juz sama liczba plikow";
  docstring of `within_volume`. No algorithm change (nothing to fix there).
- Tests: `test_bdot10k_area_within_the_file_limit_is_measured_package_by_package` (69 powiats, sample 1 MB, exact sum 19 GB -> refused,
  every URL HEADed; passes on baseline = guard of the premise); `test_collections_volume` assertion relaxed to the facts.
- Live: baseline vs worktree CLI, `--bbox 100000,100000,800000,800000` (378 files): refused before any download, new wording; script
  with `VOLUME_BYTES` patched to 1 GB and `download_package` raising on the 69-powiat area: "razem ok. 2,9 GB wg HEAD", 69 HEADs of 69, 0 files written.
- Docs: ARCHITECTURE (limit paragraph), DECISIONS (ADR-043 errata 4), CHANGELOG.

## 4. N-P3-3 year hint - DONE
- Cause: for a range the "older/newer" branches kept the other flag (`--max-year 2024` repeated the user's flag).
- Change: `year_range_hints` moves the blocking bound to the nearest year every conflicting sheet has (`--min-year 2022 (z lat 2022-2024)`);
  `--year Y` (equal bounds) and a single bound keep the spec U4 one-sided hints.
- Tests: semantic test over a generated grid (hint changes the call AND the changed range has data for every sheet), report case,
  spec case T9 updated.
- Live (`--check-updates`, bbox 530000,382000,533000,386000, --min-year 2023 --max-year 2024): before `Podpowiedz: --max-year 2024
  (rok 2024 i starsze)`, after `Podpowiedz: --min-year 2022 (z lat 2022-2024)`.
- Docs: ARCHITECTURE (YearRangeError sentence), CHANGELOG.

## 5. N-P3-2 catalog examples - DONE
- Change: examples `elevation download` PL NMT bbox as sheets (1992) and as cutout, CZ LAZ with `--model`; `imagery download` PL orto
  bbox sheets, CZ orto bbox; `example_for` ranks the mode of the call (`cutout` in `given`) after the country, so a PL sheet-list
  call no longer gets the cutout example (not enough to just add the examples).
- Tests: `test_example_for_elevation_and_imagery_is_of_the_country_and_mode_of_the_call` (fails on baseline); example-validation
  contract tests pass for the new examples.
- Live (offline `--json` hints, before -> after): nmt PL inverted bbox / zero line / missing `--country` CZ cutout -> PL
  `--country pl --bbox ... --sheet-system 1992`; laz CZ (`--model`, `--min-density`, `--year`) PL LAZ -> CZ with `--model dmr5g`;
  orto CZ bbox PL cutout -> CZ bbox; orto PL sheet-list PL cutout -> PL `--sheet-system 1992` example.
- Not added (technical): a `--geometry` example for `*download` (the example validation reads the file); NMPT/contours examples.

## 6. N-P3-7 ocd edition - DONE
- Change: `Edition.source_property` (new optional field, in `extra.edition` only when set); `SoilGridsProvider.edition("ocd")` sets `"clay"`;
  other properties unchanged. Test: extended `test_ocd_edition_comes_from_the_clay_map_its_title_has_none` (fails on baseline).
- Docs: USAGE 5, ARCHITECTURE edition table, DECISIONS ADR-044 errata 2, CHANGELOG.

## 7. N-P3-1 workers - VERIFIED
- `landcover download --product bdot10k --teryt 2264 --workers 0` and `--product corine --year 2018 --sheet N-34-130-D-d-2-4 --workers 0`:
  rc 2, "--workers musi byc >= 1, podano 0", 1 s (before any network).

## Notes
- PROGRESS.md not touched (session end, Main). No version/tag/merge/push. No `git stash`, no subagents.
- Incident: two early `edit` calls used relative paths and landed in the MAIN checkout (`develop`, campaigns.py + test_campaigns.py,
  ~25 s). Reverted at once with `git apply -R` (main `git status` clean) and re-applied in the worktree; all later edits used absolute paths.
- Interpreters outside the rule (read-only, for PROJ 9.8.1 evidence only): `<scratch>/venv/bin/python`
  with `PYTHONPATH=<worktree>`; nothing installed or written there.
