# fix-stderr (branch fix/e2e-stderr)

Contract: USAGE 9.2 - with `--json` stderr is empty except HTTP retry lines and `KARTOGRAF_DEBUG`; text mode has no bare Python lines.

## Findings

### e2e-A P2-2 / e2e-D P3-2 / e2e-B P3-3 / e2e-E P3-2(b) - pyproj `UserWarning: Best transformation is not available` - FIXED
- Root cause: `TransformerGroup(...)` in `transform/crs.py::build_pinned_transform` is the ONLY construction that emits it (checked: `Transformer.from_crs` in `core/bbox.py`, `transform/bbox.py`, `hydrology/hsg.py`, `providers/pl/skorowidz_wfs.py` do NOT warn - D's attribution to `core/bbox.py` was wrong; all CZ paths - availability, `--bbox-crs EPSG:3045`, TM33 warp, cutout - go through `build_pinned_transform` via `providers/cuzk/raster.py::bbox_to_crs`). The warning needs PROJ >= 9.6 data (CUZK grid `cz_cuzk_table_-y-x_3_v1710.tif` is "best" there); the dev venv (pyproj 3.7.2, PROJ 9.5.1) never shows it, the clean e2e venv (pyproj 3.8.0, PROJ 9.8.1) always does.
- Change: new `crs.py::_transformer_group()` = `warnings.catch_warnings()` + `filterwarnings("ignore", message="Best transformation is not available", category=UserWarning)` around the single `TransformerGroup` construction; `build_pinned_transform` uses it. No global filter.
- Test: `tests/test_transform_crs.py::TestBuildPinnedTransform::test_missing_grid_warning_of_pyproj_is_not_raised` (fails before: UserWarning escapes under `simplefilter("error")`; other warnings still pass through). The warning cannot be produced offline in the dev env (PROJ 9.5), hence the fake group that warns.
- Live (clean venv `.../kartograf-e2e-0.8.0/venv`, PYTHONPATH=worktree), before -> after stderr bytes: `elevation availability --product nmt --sheet CTES96 --json` (rc 0): warning -> 0 B; `availability --country auto --bbox ... --bbox-crs EPSG:4326 --json`: 0 B; `boundaries download --product admin --country cz --level obec --bbox 760856.41,5514903.04,763521.11,5519488.62 --bbox-crs EPSG:3045 --json` and text: warning -> 0 B; `geodesy download --product control --country cz --network vertical ... --bbox-crs EPSG:3045 --check-updates --json`: 0 B; `imagery download --product orto --country cz --bbox-crs EPSG:3045 --check-updates --json`: 0 B; TM33 `elevation download --product nmt --country cz --sheet 760_5518 --vertical-crs Bpv --resolution 5m --json` (warp): rc 0, 0 B.

### Unprefixed logger lines - FIXED (decision: prefix in text, drop in `--json`, not Notice)
Affected: `Pominieto wersje o niezgodnym sha256` (e2e-E P3-2a), `Pominieto wersje bez czytelnego sidecara` (e2e-A P3-19, B P3-12, C P3-11, D P3-9), and in general EVERY library `logger.warning/error` outside `kartograf.transport.http` (sidecar write failures, links, index_records...). Root cause: only the HTTP logger had a handler, so Python's `logging.lastResort` printed every other record as a bare message, also with `--json`.
- Why not `Notice`: `versions.read_version`/`list_versions` are low-level read paths (also store readers: `iter_store`, `project verify/status`) with no `NoticeSink`/result in reach; plumbing a sink through every caller would change many signatures for diagnostics that are either transient (parallel write races: "repaired by the next write of the same content", final state correct) or already reported by the command result (`project verify` reports "sidecar wersji niezgodny z nazwa wersji"). A generic log->notice bridge would need to inject into ~36 typed result documents.
- Change: `cli/commands.py`: `_StderrLines` handler is now installed on the `kartograf` logger (was `kartograf.transport.http`) by `_stderr_lines(as_json)` in `main`. Text mode: all WARNING/ERROR records become `Warning:`/`Error:` lines. `--json`: only `kartograf.transport.http` records pass (retry lines, as before); `KARTOGRAF_DEBUG` lets everything through. No notice codes added (USAGE 2 table / catalog unchanged).
- Tests: `tests/test_cli_errors.py` `test_library_warnings_are_not_on_stderr_in_json_mode`, `..._are_prefixed_in_text_mode`, `..._pass_with_debug_in_json_mode` (real `list_versions` skipped-version path; the first two fail before; use `propagate=False` to expose `lastResort` like the existing cz test). Existing `test_http_retry_lines_stay_on_stderr` unchanged.
- Live: tampered sidecar sha256 in the fix-stderr store, `boundaries download ... --check-updates`: `--json` rc 0, stderr 0 B (before: bare line); text: `Warning: Pominieto wersje o niezgodnym sha256: <dir>` (before: bare).

### e2e-C P3-08 - `Proxy request failed: {...}` on stderr in `--json` - FIXED
- Root cause: `auth/client.py::proxy_request` `logger.error(...)`; reason never reached the exception (`providers/corine.py` raised the constant "Zadanie przez proxy nie powiodlo sie").
- Change: `AuthProxyClient.last_error` (set in `proxy_request` failure paths and `_fail_proxy`, reset at the start of each request); the failure is logged at DEBUG; `corine.py::_download_via_clms_proxy` puts it into the `DownloadError` (`...nie powiodlo sie: Proxy request failed: {...}`), so it lands in `error`/`kartograf-error/1` and the text `Error:` line, not on stderr in `--json`. Note: `last_error` is on the process-wide singleton; with `workers>1` the reason of concurrent failures may be mixed (message only).
- Tests: `tests/test_auth_client.py` (`last_error` set / cleared), `tests/test_landcover.py::test_proxy_failure_reason_in_error`.
- Not live-reproduced after (needs a fake CLMS key + real proxy start); covered offline.

## Not changed / notes
- e2e-C's two remaining ASCII-text concerns (wording of the CLMS `Info:` on a malformed `CLMS_CREDENTIALS`) belong to another slice.
- Other `logger.error` calls in `auth/client.py` (download_file, truncated body, startup) now go through the same bridge: `Error:` line in text, dropped in `--json` (their failures also return False -> DownloadError).

## Docs changed
`docs/USAGE.md` 9.2 point 2 (what passes/doesn't on stderr, pyproj warning); `docs/ARCHITECTURE.md` (transform/crs section: warning suppression; 4.11 errors paragraph: `_StderrLines` policy).

## Proposed CHANGELOG (Polish, ASCII) - "Naprawiono"
- Stderr zgodny z kontraktem `--json` (USAGE 9.2) w czystej instalacji: ostrzezenie pyproj `Best transformation is not available` (brak siatki PROJ CUZK; availability CZ/auto, `--bbox-crs EPSG:3045`, warp TM33, wycinek CZ) nie jest drukowane - przypieta polityka wybiera operacje sama (`transform/crs.py`).
- Rekordy loggera biblioteki (np. `Pominieto wersje o niezgodnym sha256`, `Pominieto wersje bez czytelnego sidecara`) nie sa juz drukowane jako surowe linie: w trybie tekstowym maja prefiks `Warning:`/`Error:`, z `--json` stderr zostaje pusty (poza ponowieniami HTTP i `KARTOGRAF_DEBUG`).
- Blad zadania CLMS przez proxy niesie przyczyne w komunikacie bledu (`Zadanie przez proxy nie powiodlo sie: ...`) zamiast linii `Proxy request failed` na stderr w `--json`.

ADR errata: none needed (ADR-046 stderr contract unchanged; implementation now matches it).

## Additional change: duplicate sidecar warning
`sources/sidecar.py::pl_sheet_horizontal_crs` logged at WARNING the same fact that `download_data` reports as the `SHEET_CRS_MISMATCH` notice (Z3: the library does not log what a notice carries). Before: a bare duplicate line (also in `--json`); with the new handler it would be a doubled `Warning:` (caught by `tests/test_cli.py::TestSheetCrsMismatchWarning`). Now `logger.debug`; the mismatch stays visible as the notice and in the sidecar (`horizontal_crs`, `extra.source.declared_crs`). Tests in `tests/test_sidecar.py` no longer pin the log (kept the CRS assertions). Side effect: direct `DownloadManager` users no longer get the log warning (sidecar still describes it).

## Gate / commits
`scripts/gate.sh` GATE OK (7166 passed, 18 deselected). Commit on fix/e2e-stderr: 882db221 `fix(cli): stderr zgodny z kontraktem --json (...)`.
