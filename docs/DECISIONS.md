# Decision register — Kartograf

Every architectural or project decision is documented below.
Format: number, date, context (why the topic arose), options considered, decision, consequences.

The content of a decision describes the state at the time it was made and is not modernised.
Later changes to facts and additional findings are appended at the end of the entry
as errata `**Erratum N (YYYY-MM-DD, source/reason):**`, numbered chronologically within the
ADR. Template for a new entry: [New ADR template](#new-adr-template).

**Status vocabulary** (the `**Status:**` line of each entry):
- `Accepted` — the decision applies in full;
- `Accepted — partly superseded by ADR-x (scope)` — the indicated part no longer applies;
- `Accepted — amended by ADR-x (scope)` — it applies, a later decision extends it;
- `Superseded by ADR-x` — it no longer applies;
- `Rejected` — considered and not accepted.

After the semicolon the status may give the reverse relations (`supersedes ...`, `amends ...`);
each relation is recorded on both sides.

## Index

| ADR | Title | Date | Status |
|---|---|---|---|
| [ADR-001](#adr-001-flat-layout-instead-of-src-layout) | Flat layout instead of src layout | 2026-01-17 | Accepted |
| [ADR-002](#adr-002-auth-proxy-for-isolating-clms-credentials) | Auth Proxy for isolating CLMS credentials | 2026-01-18 | Accepted |
| [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--separating-the-nmt-download-paths) | OpenData (ASC) vs WCS (GeoTIFF) — separating the NMT download paths | 2026-01-18 | Accepted — partly superseded by [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) (bbox = WCS GeoTIFF; erratum 1) and [ADR-036](#adr-036-versioned-store) (`DownloadManager.download_bbox` removed; erratum 2) |
| [ADR-004](#adr-004-evrf2007-as-the-default-vertical-crs) | EVRF2007 as the default vertical CRS | 2026-01-21 | Superseded in 0.8.0 — erratum 1 (vertical CRS required, no default value) |
| [ADR-005](#adr-005-nmt-directory-structure-split-by-resolution) | NMT directory structure split by resolution | 2026-01-21 | Accepted — partly superseded by [ADR-013](#adr-013-renaming-storage-subdirectories-from-1m5m-to-nmt_1mnmt_5m), and then [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) (implementation of the directory layout; erratum 1) |
| [ADR-006](#adr-006-landcoverprovider-as-a-separate-hierarchy-from-baseprovider) | LandCoverProvider as a separate hierarchy from BaseProvider | 2026-01-18 | Accepted |
| [ADR-007](#adr-007-migration-from-black--flake8-to-ruff) | Migration from black + flake8 to ruff | 2026-02-03 | Accepted |
| [ADR-008](#adr-008-condensing-progressmd-from-785-to-80-lines) | Condensing PROGRESS.md from 785 to ~80 lines | 2026-02-03 | Accepted |
| [ADR-009](#adr-009-expanding-development_standards-and-implementation_prompt) | Expanding DEVELOPMENT_STANDARDS and IMPLEMENTATION_PROMPT | 2026-02-03 | Superseded by [ADR-048](#adr-048-adoption-of-the-nogat-standard-21-layout-tooling-and-versions) |
| [ADR-010](#adr-010-the-find_sheets_for_bbox-algorithm--hierarchical-clipping-without-wfs) | The find_sheets_for_bbox algorithm — hierarchical clipping without WFS | 2026-02-07 | Accepted |
| [ADR-011](#adr-011-gugiknmptprovider-inherits-from-gugikprovider) | GugikNmptProvider inherits from GugikProvider | 2026-02-07 | Accepted |
| [ADR-012](#adr-012-gugikortoprovider-as-a-separate-class-does-not-inherit-from-gugikprovider) | GugikOrtoProvider as a separate class (does not inherit from GugikProvider) | 2026-02-07 | Accepted |
| [ADR-013](#adr-013-renaming-storage-subdirectories-from-1m5m-to-nmt_1mnmt_5m) | Renaming storage subdirectories from 1m/5m to nmt_1m/nmt_5m | 2026-02-07 | Superseded by [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors); partly supersedes [ADR-005](#adr-005-nmt-directory-structure-split-by-resolution) (directory names) |
| [ADR-014](#adr-014-bdot10k-category-based-extraction-pt-vs-hydro) | BDOT10k category-based extraction (pt vs hydro) | 2026-02-08 | Superseded by [ADR-016](#adr-016-bdot10k--removing-category-filtering-downloading-the-whole-file) |
| [ADR-015](#adr-015-pyshp--sqlite3-instead-of-fiona-for-reading-geometry) | pyshp + sqlite3 instead of fiona for reading geometry | 2026-02-08 | Accepted — amended by [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (GPKG writing via pyogrio; envelope reading unchanged) |
| [ADR-016](#adr-016-bdot10k--removing-category-filtering-downloading-the-whole-file) | BDOT10k — removing category filtering, downloading the whole file | 2026-03-02 | Accepted; supersedes [ADR-014](#adr-014-bdot10k-category-based-extraction-pt-vs-hydro) |
| [ADR-017](#adr-017-pl-2000-sheet-naming--composition-pattern-with-auto-detection) | PL-2000 sheet naming — composition pattern with auto-detection | 2026-02-24 | Accepted — amended by [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) (PL-2000's own segments; erratum 1) |
| [ADR-018](#adr-018-threadpoolexecutor-for-parallel-downloads) | ThreadPoolExecutor for parallel downloads | 2026-03-03 | Accepted; erratum 2: download pools via `kartograf.interrupt.run_parallel`: Ctrl-C cancels the queue and stops transfers (E2E test 0.8.0) |
| [ADR-019](#adr-019-sqlite-wal-as-metadata-cache) | SQLite WAL as metadata cache | 2026-03-03 | Accepted — amended by [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource) (`record_cache` instead of `url_cache`; erratum 1) and [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (`campaigns_cache`; erratum 2) |
| [ADR-020](#adr-020-validating-wms-layers-via-getcapabilities) | Validating WMS layers via GetCapabilities | 2026-03-24 | Accepted — partly superseded by [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource) (layers only from GetCapabilities, no hard-coded lists and no fallback; erratum 3) |
| [ADR-021](#adr-021-laz-lidar-point-clouds--discovery-via-wfs-area-based) | LAZ (LIDAR point clouds) — discovery via WFS, area-based | 2026-06-24 | Accepted — partly superseded by [ADR-029](#adr-029-choosing-laz-tiles-by-area-coverage-and-downloading-laz-in-the-library) (newest-per-tile rule) |
| [ADR-022](#adr-022-multi-country-source-architecture--descriptors-registries-sidecar-strict-transformation-policy-stage-0) | Multi-country source architecture — descriptors, registries, sidecar, strict transformation policy (stage 0) | 2026-08-10 | Accepted — amended by [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) (formal engine interface: `CuzkClient`, (a)) and [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100) (English sidecar key names) |
| [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) | CUZK engine, CZ CRS policy and EVRF2007→5621 (stage 1) | 2026-08-11 | Accepted — partly superseded by [ADR-024](#adr-024-reprojection-of-cz-content-only-locally-no-imagesr--native) (TM33 download mechanism in (c), Additional findings item 1) and [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) (`--target-crs` for CZ only; Additional findings item 6) and [ADR-038](#adr-038-explicit-cutout-mode-and-crs-names---cutout---horizontal-crs---sheet-system) (a CZ area is always a cutout; now `--cutout`); amended by [ADR-029](#adr-029-choosing-laz-tiles-by-area-coverage-and-downloading-laz-in-the-library) ((f).1 covers LAZ) and [ADR-034](#adr-034-common-mechanism-for-area-queries-chunks-on-the-source-grid) (CUZK chunking in `transport/chunks.py`); amends [ADR-022](#adr-022-multi-country-source-architecture--descriptors-registries-sidecar-strict-transformation-policy-stage-0); erratum 2: `--country` required with an area, values per country (0.8.0) |
| [ADR-024](#adr-024-reprojection-of-cz-content-only-locally-no-imagesr--native) | Reprojection of CZ content only locally (no `imageSR` != native) | 2026-08-11 | Accepted — amended by [ADR-034](#adr-034-common-mechanism-for-area-queries-chunks-on-the-source-grid) (common chunk planning with an NW anchor); supersedes part of [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) (TM33 download mechanism in (c), Additional findings item 1) |
| [ADR-025](#adr-025-texture---hsg-mapping-and-the-canonical-usda-triangle-070-audit) | Texture -> HSG mapping and the canonical USDA triangle (0.7.0 audit) | 2026-08-22 | Accepted |
| [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) | data/ layout per product — segments and templates in descriptors | 2026-08-28 | Accepted — amended by [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (files in `<segment>/kampanie/`, standard path = hard link or copy; erratum 2), [ADR-036](#adr-036-versioned-store) (`<segment>/versions/`; erratum 3) and [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D7: naming convention for `data/` keys and directories); supersedes [ADR-013](#adr-013-renaming-storage-subdirectories-from-1m5m-to-nmt_1mnmt_5m) and the implementation of the layout from [ADR-005](#adr-005-nmt-directory-structure-split-by-resolution), amends [ADR-017](#adr-017-pl-2000-sheet-naming--composition-pattern-with-auto-detection) (closes the deferral) |
| [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) | --target-crs for PL — merged bbox cutout (mosaic + pinned warp) | 2026-08-28 | Accepted — partly superseded by [ADR-035](#adr-035-pl-cutouts-from-gugik-wcs-with-a-prg-land-mask) (cutout source in the CLI and `download_pl_cutout`; sheet API removed in 0.8.0, erratum 2 of ADR-035) and [ADR-038](#adr-038-explicit-cutout-mode-and-crs-names---cutout---horizontal-crs---sheet-system) (the name `--target-crs`, enabling a cutout with a CRS flag); amended by [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (deprecated sheet path only); supersedes part of [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) (`--target-crs` for CZ only) and [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--separating-the-nmt-download-paths) (bbox = WCS GeoTIFF) |
| [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource) | Choosing the GUGiK sheet index record and `extra.source` | 2026-09-30 | Accepted — amended by [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (campaign strategies `newest`/`all`, `--min-year`; the `newest` selection rule unchanged; sheet index failure: erratum 2) and [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (plain mode takes the newest full flight); partly superseded by [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100) (`extra.source` key names); supersedes part of [ADR-020](#adr-020-validating-wms-layers-via-getcapabilities) (hard-coded layers and fallback), amends [ADR-019](#adr-019-sqlite-wal-as-metadata-cache) (`record_cache`) |
| [ADR-029](#adr-029-choosing-laz-tiles-by-area-coverage-and-downloading-laz-in-the-library) | Choosing LAZ tiles by area coverage and downloading LAZ in the library | 2026-10-07 | Accepted — amended by [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (`--campaigns all`/`--min-year` for LAZ; erratum 1) and [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict) (year range and reference coverage; erratum 2); supersedes part of [ADR-021](#adr-021-laz-lidar-point-clouds--discovery-via-wfs-area-based) (newest-per-tile rule), amends [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) ((f).1 covers LAZ) |
| [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) | Campaign strategies (`newest`/`all`), `--min-year` and the `kampanie/` layout with a hard link | 2026-10-07 | Accepted — partly superseded by [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100) (`extra.campaign` key names), [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict) (range, scan and conflict; erratum 7) and [ADR-036](#adr-036-versioned-store) (`kampanie/` layout, automatic `newest`, copy instead of hard link; erratum 9); amended by [ADR-033](#adr-033-second-hard-link-to-the-newest-full-flight-full_sheet---full-sheet) (second link `full_sheet/`; erratum 8); amends [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) (`kampanie/`), [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) (cutout only `newest`), [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource) (strategies; the `newest` selection rule unchanged), [ADR-029](#adr-029-choosing-laz-tiles-by-area-coverage-and-downloading-laz-in-the-library) (LAZ: `all`, `--min-year`) and [ADR-019](#adr-019-sqlite-wal-as-metadata-cache) (`campaigns_cache`); erratum 10: open minor review items closed (M-8: link sidecar removed after a write failure) |
| [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100) | Identifier language — English (sidecar from 0.7.0, API/CLI until v1.0.0) | 2026-10-08 | Accepted — amended by [ADR-037](#adr-037-cli-and-api-consistency) (language of user-facing texts, Z5); partly supersedes [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource) (names of `extra.source` keys) and [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (names of `extra.campaign` keys); amends [ADR-022](#adr-022-multi-country-source-architecture--descriptors-registries-sidecar-strict-transformation-policy-stage-0) (naming convention of `kartograf-meta/1` sidecar keys); erratum 1: API/CLI in English in 0.8.0 without aliases (points 2-3 outdated) |
| [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict) | Choosing the data year: year range, stopping on conflict | 2026-10-10 | Accepted — amended by [ADR-033](#adr-033-second-hard-link-to-the-newest-full-flight-full_sheet---full-sheet) (`--full-sheet` from point 4; erratum 1) and [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (the year options filter the flights of plain mode); partly superseded by [ADR-036](#adr-036-versioned-store) (point 2: D14, point 4: D13; erratum 3); erratum 2: `--all-campaigns`/`all_campaigns` from 0.8.0; amends [ADR-029](#adr-029-choosing-laz-tiles-by-area-coverage-and-downloading-laz-in-the-library) (LAZ) and [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (PL campaigns) |
| [ADR-033](#adr-033-second-hard-link-to-the-newest-full-flight-full_sheet---full-sheet) | Second hard link to the newest full flight (`full_sheet/`, `--full-sheet`) | 2026-10-10 | Accepted — partly superseded by [ADR-036](#adr-036-versioned-store) (F-U5: `kampanie/`; erratum 1); amended by [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (`--full-sheet` has no effect with `--output-dir`); amends [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) ((d): second hard link; erratum 8) and [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict) (point 4: `--full-sheet`; erratum 1) |
| [ADR-034](#adr-034-common-mechanism-for-area-queries-chunks-on-the-source-grid) | Common mechanism for area queries (chunks on the source grid) | 2026-10-10 | Accepted — amended by [ADR-035](#adr-035-pl-cutouts-from-gugik-wcs-with-a-prg-land-mask) (ASC 1 Mpx and NMPT) and [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (orthophoto cutout chunks; erratum 1: bit-for-bit stitching only for NMT); amends [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) (CUZK chunking) and [ADR-024](#adr-024-reprojection-of-cz-content-only-locally-no-imagesr--native) (NW anchor) |
| [ADR-035](#adr-035-pl-cutouts-from-gugik-wcs-with-a-prg-land-mask) | PL cutouts from GUGiK WCS with a PRG land mask | 2026-10-11 | Accepted; partly supersedes [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) (cutout source in the CLI and `download_pl_cutout`), amends [ADR-034](#adr-034-common-mechanism-for-area-queries-chunks-on-the-source-grid) (ASC 1 Mpx and NMPT); erratum 1: NMPT ASC chunk 4 Mpx coverage; erratum 2: sheet-based path removed in 0.8.0; erratum 3: W-U3/W-U8 superseded by [ADR-036](#adr-036-versioned-store) (D15, plan 2/3) |
| [ADR-036](#adr-036-versioned-store) | Versioned store | 2026-10-12 | Accepted — partly superseded by [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (D27: orthophoto cutout in the store; erratum 2) and [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D32: public land cover and HSG reports); amended by [ADR-037](#adr-037-cli-and-api-consistency) (CZ sheet in the public API; erratum 1), [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (D23 between releases, unit slots) and [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (store marker, `root`, plain mode as the second write target); partly supersedes [ADR-030](#adr-030-campaign-strategies-newestall---min-year-and-the-kampanie-layout-with-a-hard-link) (`kampanie/`, automatic `newest`, copy), [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict) (points 2 and 4), [ADR-033](#adr-033-second-hard-link-to-the-newest-full-flight-full_sheet---full-sheet) (F-U5), [ADR-035](#adr-035-pl-cutouts-from-gugik-wcs-with-a-prg-land-mask) (W-U3/W-U8) and [ADR-003](#adr-003-opendata-asc-vs-wcs-geotiff--separating-the-nmt-download-paths) (`DownloadManager.download_bbox`); amends [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) (`versions/`; land cover and HSG in the `data/` layout); erratum 3: default mode without signal queries when a local version exists, `--upgrade` queries the source (live test 0.8.0); erratum 4: hard link confirmation by content without a link count (SMB without `serverino`) and data states in `check_sheets` (E2E test 0.8.0) |
| [ADR-037](#adr-037-cli-and-api-consistency) | CLI and API consistency | 2026-10-12 | Accepted — amended by [ADR-038](#adr-038-explicit-cutout-mode-and-crs-names---cutout---horizontal-crs---sheet-system) (names of CRS flags and parameters), [ADR-039](#adr-039-cli-command-groups-by-data-type) (one command = one library function), [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D5-D6: land cover, soils and HSG functions, reports) and [ADR-046](#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server) (command result as a JSON document, `--json`, error and exit codes); amends [ADR-036](#adr-036-versioned-store) (CZ sheet in the public API; erratum 1 of ADR-036) and [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100) (language of user-facing texts) |
| [ADR-038](#adr-038-explicit-cutout-mode-and-crs-names---cutout---horizontal-crs---sheet-system) | Explicit cutout mode and CRS names (--cutout, --horizontal-crs, --sheet-system) | 2026-10-13 | Accepted — amended by [ADR-039](#adr-039-cli-command-groups-by-data-type) (flag names in groups); partly supersedes [ADR-027](#adr-027---target-crs-for-pl--merged-bbox-cutout-mosaic--pinned-warp) (enabling the PL cutout with a CRS flag, the name `--target-crs`) and [ADR-023](#adr-023-cuzk-engine-cz-crs-policy-and-evrf20075621-stage-1) (CZ area always as a cutout, no mode flag); amends [ADR-037](#adr-037-cli-and-api-consistency) (CLI names = API) |
| [ADR-039](#adr-039-cli-command-groups-by-data-type) | CLI command groups by data type | 2026-10-15 | Accepted — amended by [ADR-040](#adr-040-project-manifest-and-pinned-versions) (a data command sets `_task` for `project add`), [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (groups `boundaries`, `cadastre`, `models3d`, `hydro`), [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (groups `names`, `maps`, `geodesy`) and [ADR-046](#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server) (command declarations in the catalog, CLI parser built from the catalog); partly superseded by [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D1: `landcover --source`, D5: functions instead of methods); amends [ADR-037](#adr-037-cli-and-api-consistency) (the CLI only translates; one command = one library function) and [ADR-038](#adr-038-explicit-cutout-mode-and-crs-names---cutout---horizontal-crs---sheet-system) (flag names); no aliases for removed commands (same principle as the erratum of [ADR-031](#adr-031-identifier-language--english-sidecar-from-070-apicli-until-v100)) |
| [ADR-040](#adr-040-project-manifest-and-pinned-versions) | Project manifest and pinned versions | 2026-10-15 | Accepted — amended by [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (collection command entries), [ADR-046](#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server) (names and kinds of data command options from the catalog) and [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (`root` instead of `output_dir`, projects store-only); partly superseded by [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D2: the name `project_status`); amends [ADR-039](#adr-039-cli-command-groups-by-data-type) (a data command sets `_task` for `project add`); erratum 2: `project download --force` repairs a damaged pinned version (E2E test 0.8.0) |
| [ADR-041](#adr-041-product-variant-registry-wfs-sheet-index-for-nmtnmpt-and-availability-report) | Product variant registry, WFS sheet index for NMT/NMPT and availability report | 2026-10-15 | Accepted — amended by [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (NMT 100 m in the variant registry without a vertical CRS; 8-part PL-1992 sheet codes - closes Limitations, erratum 4) and [ADR-047](#adr-047-sheet-and-campaign-details-in-the-availability-report-kd-1-kd-2) (`full_m2`, `sheet_records`, `campaign_coverage`); errata 1-3: completion of plan A, CZ variants (plan B), completion of plan B; erratum 5: availability: country envelope, area without land (`no_land`), `--min-density` error (E2E test 0.8.0) |
| [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) | Channel engines (unit_package, feature_bbox, atom_files) and plan C/D data | 2026-10-15 | Accepted — partly superseded by [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (D1: collection channel capability unique in the descriptor) and [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D9: `landcover` stays with `--source`; erratum 5: orthophoto cutout API names; D6: explicit collection call timeout); amended by [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (sheet, tile and KU units, index record and `index` signal, OGC API Features, channel choice by option values); partly supersedes [ADR-036](#adr-036-versioned-store) (D27: orthophoto cutout in the store; erratum 2 of ADR-036); amends [ADR-015](#adr-015-pyshp--sqlite3-instead-of-fiona-for-reading-geometry) (GPKG writing via pyogrio; envelope reading unchanged), [ADR-034](#adr-034-common-mechanism-for-area-queries-chunks-on-the-source-grid) (orthophoto cutout chunks; erratum 1 of ADR-034), [ADR-036](#adr-036-versioned-store) (D23 between releases, unit slots), [ADR-039](#adr-039-cli-command-groups-by-data-type) (groups `boundaries`, `cadastre`, `models3d`, `hydro`) and [ADR-040](#adr-040-project-manifest-and-pinned-versions) (project command entries); errata 1-5: D5 and D12-D17 according to the plan D code (ATOM index, HY-NET area 2 layers, ZABAGED and RUIAN, CZ orthophoto, orthophoto cutout); erratum 6: an image cutout entirely 0,0,0 = `NoCoverageError` without a version (live test 0.8.0); erratum 7: `--country auto` in collections: partial success with code 0, a country without units does not abort the task, KU cache (E2E test 0.8.0) |
| [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) | Plan E: unit, sheet and national products on engines C/D | 2026-10-16 | Accepted; partly supersedes [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (D1: collection channel capability unique in the descriptor); amended by [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D6: channel limit instead of an explicit call timeout); partly superseded by [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) (D1 and erratum 3: slots for CUZK sheet, tile and national file topic - D7 of ADR-044); amends [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (sheet, tile and KU units, national file topics, index record and `index` signal, OGC API Features, channel choice by option values, `DOWNLOAD_SIZE`), [ADR-039](#adr-039-cli-command-groups-by-data-type) (groups `names`, `maps`, `geodesy`) and [ADR-041](#adr-041-product-variant-registry-wfs-sheet-index-for-nmtnmpt-and-availability-report) (NMT 100 m in the variant registry without a vertical CRS; 8-part PL-1992 sheet codes - D10); erratum 1: PRG census districts outside the special boundaries area (E3); erratum 2: BDOO package classes (`--layers`) and county packages of the area (E4); erratum 3: area limit (100 files, 10 GB), mesh tile = record file, Bodove pole = sum of network layers (E5); erratum 4: the area limit covers BDOT10k (E2E test 0.8.0) |
| [ADR-044](#adr-044-unifying-cli-and-api---product---summary-land-cover-soils-and-hsg-functions) | Unifying CLI and API: --product, --summary, land cover, soils and HSG functions | 2026-10-16 | Accepted; partly supersedes [ADR-039](#adr-039-cli-command-groups-by-data-type) (D1, D6: `landcover --source`, D5: class methods as API), [ADR-040](#adr-040-project-manifest-and-pinned-versions) (D2: the name `project_status`), [ADR-042](#adr-042-channel-engines-unit_package-feature_bbox-atom_files-and-plan-cd-data) (D9: `landcover` stays with `--source`; erratum 5: orthophoto cutout API names), [ADR-036](#adr-036-versioned-store) (D32: land cover and HSG results), [ADR-037](#adr-037-cli-and-api-consistency) (S3-S4: class methods) and [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (D1 and erratum 3: slots for CUZK sheet, tile and national file topic - D7); amends [ADR-043](#adr-043-plan-e-unit-sheet-and-national-products-on-engines-cd) (D7: call timeout) and [ADR-026](#adr-026-data-layout-per-product--segments-and-templates-in-descriptors) (D7: naming convention for `data/` keys and directories); erratum 1: keyword-only arguments of all download and check functions (live test 0.8.0); erratum 2: land cover and soils: SoilGrids units, BDOT10k classes, CORINE preview (E2E test 0.8.0) |
| [ADR-045](#adr-045-public-store-reading-api-for-archiwista) | Public store-reading API for Archiwista | 2026-10-18 | Accepted — amended by [ADR-046](#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server) (MCP tools for reading the store; erratum 1) and [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (the parameter `root`); erratum 2: segment parts (`list_partitions`, `partition`) and the `skip_versions` mapping without listing known version directories (relaxes visibility of changes in them); erratum 3: `Sidecar.unit` and the LAZ tile outline, ZTM sheet, `link_target` of an independent copy, `file_footprint` without an exception for a source without a CRS operation (E2E test 0.8.0) |
| [ADR-046](#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server) | Interface for AI agents: JSON documents, error codes, command catalog and MCP server | 2026-10-18 | Accepted; amends [ADR-037](#adr-037-cli-and-api-consistency) (command result as a JSON document, `--json`, error and exit codes), [ADR-039](#adr-039-cli-command-groups-by-data-type) (command declarations in the catalog), [ADR-040](#adr-040-project-manifest-and-pinned-versions) (data command options from the catalog) and [ADR-045](#adr-045-public-store-reading-api-for-archiwista) (MCP tools for reading the store); erratum 3: exit code 143 (`terminated`), `failed[].kind`, stderr in `--json`, `hint` from call arguments (E2E test 0.8.0) |
| [ADR-047](#adr-047-sheet-and-campaign-details-in-the-availability-report-kd-1-kd-2) | Sheet and campaign details in the availability report (KD-1, KD-2) | 2026-10-19 | Accepted; amends [ADR-041](#adr-041-product-variant-registry-wfs-sheet-index-for-nmtnmpt-and-availability-report) (`full_m2`, `sheet_records`, `campaign_coverage`); erratum 1: `AvailabilityRecord.full_sheet`, LAZ limitation and CZ exception in the field documentation; erratum 2: area without land: `complete` unchanged, `no_land` signal (E2E test 0.8.0) |
| [ADR-048](#adr-048-adoption-of-the-nogat-standard-21-layout-tooling-and-versions) | Adoption of the Nogat standard 2.1: layout, tooling and versions | 2026-10-24 | Accepted; supersedes [ADR-009](#adr-009-expanding-development_standards-and-implementation_prompt) |
| [ADR-049](decisions/0049-nogat-error-registry-mapping.md) | Error codes and exit codes follow the Nogat registry | 2026-10-24 | Accepted |
| [ADR-050](decisions/0050-nogat-user-environment.md) | User environment: nogat.toml, variables, user directories and `config show` | 2026-10-24 | Accepted — amended by [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (the default root is the target of a command without a target option) |
| [ADR-051](decisions/0051-result-envelope-and-outcome-exit-codes.md) | Result envelope kartograf-result/1, outcome exit codes 10 and 11, error document on stderr | 2026-10-24 | Accepted — amended by [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (`files[]` and `skipped[]` of the download reports) |
| [ADR-052](decisions/0052-command-catalog-documents-and-mcp-server.md) | Command catalog documents kartograf-command-list/1 and kartograf-commands/1, and the MCP server | 2026-10-24 | Accepted — amended by [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) (the options `output_dir` and `root`, `check` instead of `check_updates`, `store init`); erratum 1: the command layer drives every command (AGI-2.1) |
| [ADR-053](decisions/0053-message-catalog-and-english-machine-output.md) | Message catalog and English machine output | 2026-10-25 | Accepted; amends [ADR-037](#adr-037-cli-and-api-consistency) (Z5, S6: the language of messages); erratum 1: the migration is complete, `_PENDING` is gone |
| [ADR-054](decisions/0054-data-output-plain-mode-store-and-default-root.md) | Data output: plain mode, the store and the default root | 2026-10-25 | Accepted; supersedes ADR-048 of the branch `claude/vigilant-faraday-finqvd` (not merged; its D12 and D13 adopted); amends [ADR-028](#adr-028-choosing-the-gugik-sheet-index-record-and-extrasource), [ADR-032](#adr-032-choosing-the-data-year-year-range-stopping-on-conflict), [ADR-033](#adr-033-second-hard-link-to-the-newest-full-flight-full_sheet---full-sheet), [ADR-036](#adr-036-versioned-store), [ADR-040](#adr-040-project-manifest-and-pinned-versions), [ADR-045](#adr-045-public-store-reading-api-for-archiwista), [ADR-050](decisions/0050-nogat-user-environment.md), [ADR-051](decisions/0051-result-envelope-and-outcome-exit-codes.md) and [ADR-052](decisions/0052-command-catalog-documents-and-mcp-server.md) |

---

## ADR-001: Flat layout instead of src layout

**Date:** 2026-01-17
**Status:** Accepted

**Context:** At the start of the project, a directory structure had to be chosen. The standard options are `src/kartograf/` (src layout) or `kartograf/` (flat layout).

**Options:**
- A) `src/` layout — forces `pip install -e .` to run the tests, prevents accidental imports from the CWD
- B) Flat layout — simpler, less configuration, sufficient for projects of this scale

**Decision:** Flat layout (`kartograf/` in the root). The project is medium-sized, used in a closed ecosystem (Hydrograf/Hydrolog), and does not need the isolation of src/.

**Consequences:** Simpler imports, no additional directory layer. A potential problem with CWD imports — acceptable when working with a venv.

---

## ADR-002: Auth Proxy for isolating CLMS credentials

**Date:** 2026-01-18
**Status:** Accepted

**Context:** CORINE Land Cover from Copernicus CLMS requires OAuth2 RSA (client_id + private key). Credentials should not be visible in the main application process.

**Options:**
- A) Direct OAuth2 in CorineProvider — simpler, but credentials in the memory of the main process
- B) Auth Proxy — a separate HTTP process on localhost, credentials isolated
- C) External secret manager — overengineering for this project

**Decision:** Auth Proxy (option B). A separate process (`kartograf/auth/proxy.py`) launched as a subprocess. The main application communicates with the proxy over localhost HTTP. Credentials are retrieved from the macOS Keychain.

**Consequences:** Safer — credentials do not leave the proxy process. More complex code (2 modules: proxy.py, client.py). Fallback to WMS (PNG) when credentials are missing.

---

## ADR-003: OpenData (ASC) vs WCS (GeoTIFF) — separating the NMT download paths

**Date:** 2026-01-18
**Status:** Accepted — partly superseded by ADR-027 (bbox = WCS GeoTIFF; erratum 1) and ADR-036 (`DownloadManager.download_bbox` removed; erratum 2)

**Context:** GUGiK offers two ways of downloading digital terrain model (NMT): OpenData (ASC files by sheet code (Polish godło)) and WCS (GeoTIFF by bbox). Initially, an attempt was made to unify both in a single flow.

**Options:**
- A) One interface with a `method` parameter — unified API, but complicated internal logic
- B) Splitting into `download_sheet(godlo)` → ASC and `download_bbox(bbox)` → GeoTIFF

**Decision:** Splitting (option B). A sheet code always gives ASC via OpenData, a bbox always gives GeoTIFF via WCS. Different formats, different APIs, different limitations — there is no point in combining them.

**Consequences:** Clearer code. The user explicitly chooses the method. NMT 5m works only via OpenData (WCS unavailable).

**Erratum 1 (2026-09-29, documentation audit):** the part "a bbox always gives GeoTIFF
via WCS" no longer holds: the CLI expands a PL bbox into OpenData sheets,
and a single GeoTIFF for a bbox/geometry is built from the sheets as a cutout by `--target-crs` /
`download_pl_cutout` (ADR-027). WCS remained only in
`DownloadManager.download_bbox` / `GugikProvider.download_bbox` and only for
KRON86 — GUGiK withdrew the EVRF2007 endpoint (HTTP 404 since 2026-08), and
`download_bbox` with EVRF2007 ends with a `ValidationError` before touching the network.

**Erratum 2 (2026-10-12, ADR-036 D27, 0.8.0):** `DownloadManager.download_bbox`
removed — it wrote a file in the store root, always overwrote it and duplicated
`download_pl_cutout(EPSG:2180)` without the PRG mask. NMT/NMPT cutout in the store:
`download_pl_cutout`; raw WCS (e.g. orthophoto) outside the store:
`provider.download_bbox(bbox, path)` (the provider methods remain).

---

## ADR-004: EVRF2007 as the default vertical CRS

**Date:** 2026-01-21
**Status:** Superseded in 0.8.0 — erratum 1 (vertical CRS required, no default value)

**Context:** GUGiK offers NMT in two systems: KRON86 (Kronstadt, historical) and EVRF2007 (European Vertical Reference Frame, the current standard). Previously the default was KRON86.

**Options:**
- A) Keep KRON86 as the default — backward compatibility
- B) Change to EVRF2007 — the current standard, required by NMT 5m

**Decision:** EVRF2007 as the default (option B). It is the current geodetic standard in Poland. KRON86 is available as `--vertical-crs KRON86`.

**Consequences:** Breaking change in v0.3.2. Users of KRON86 must pass the flag explicitly. NMT 5m works out of the box.

**Erratum 1 (2026-10-12, 0.8.0, user decision):** there is no default value
for the vertical CRS. The CLI `--vertical-crs` is required for NMT, digital surface model (NMPT)
and LAZ (PL: EVRF2007 or KRON86; NMT 5 m only EVRF2007; CZ: Bpv or
EVRF2007), and in the API `vertical_crs` is required in the GUGiK/CUZK providers,
factories, `FileStorage`, the PL cutout and LAZ. Reason: the rule "no
default values affecting data" (DEVELOPMENT_STANDARDS 11.2) — the vertical
CRS selects the data, so the caller selects it. EVRF2007 remains the
recommended CRS (the current standard, the only one for NMT 5 m).

---

## ADR-005: NMT directory structure split by resolution

**Date:** 2026-01-21
**Status:** Accepted — partly superseded by ADR-013, and then ADR-026 (realisation of the directory layout; erratum 1)

**Context:** After adding NMT 5m support, the 1m and 5m files for the same sheet code had the same path. Risk of overwriting.

**Options:**
- A) Suffix in the file name (`N-34-130-D-d-2-4_5m.asc`) — simple, but inconsistent with the GUGiK convention
- B) Resolution subdirectory (`data/1m/...`, `data/5m/...`) — clean separation

**Decision:** Resolution subdirectory (option B). Structure: `data/1m/N-34/130/.../plik.asc` and `data/5m/N-34/130/.../plik.asc`.

**Consequences:** Breaking change — old paths without `1m/`/`5m/` are not compatible. Clean separation, easy to understand. FileStorage accepts a `resolution` parameter.

**Erratum 1 (2026-08-28, ADR-026):** the decision "resolution is a path dimension"
still holds, but its realisation changed twice: `1m`/`5m` ->
`nmt_1m`/`nmt_5m` (ADR-013) -> segments `nmt/pl_<crs>_<res>_<vcrs>`
(ADR-026). The `resolution` parameter in `FileStorage` remained, except that it maps
today to a segment TEMPLATE, not to a directory name.

---

## ADR-006: LandCoverProvider as a separate hierarchy from BaseProvider

**Date:** 2026-01-18
**Status:** Accepted

**Context:** When adding BDOT10k and CORINE, it had to be decided how to organise the providers. BaseProvider (NMT) and the new providers (Land Cover) have different interfaces — NMT downloads by sheet code/bbox, Land Cover additionally by TERYT.

**Options:**
- A) Extend BaseProvider with Land Cover methods — one hierarchy, but NMT does not need TERYT
- B) A separate base class LandCoverProvider — clean separation of responsibilities

**Decision:** A separate hierarchy (option B). `BaseProvider` for NMT, `LandCoverProvider` for land cover. Common interface: `download_by_godlo()`, `download_by_bbox()`. Additional in LC: `download_by_teryt()`.

**Consequences:** Two provider hierarchies. Possible unification in the future (v0.4+). LandCoverManager dispatches to the appropriate provider.

---

## ADR-007: Migration from black + flake8 to ruff

**Date:** 2026-02-03
**Status:** Accepted

**Context:** The workspace has unified standards (`shared/standards/DEVELOPMENT_STANDARDS.md`) that require ruff. Kartograf used black (formatter) + flake8 (linter) — two separate tools, separate configuration files.

**Options:**
- A) Keep black + flake8 — works, but not compliant with the workspace standard
- B) Migrate to ruff — one tool (linter + formatter), configuration in pyproject.toml

**Decision:** Migration to ruff (option B). Removed `[tool.black]` from pyproject.toml and `.flake8`. Added `[tool.ruff]` with the rules `E, F, I, UP, B, SIM`.

**Consequences:** One tool instead of two. Ruff detected 73 problems in the existing code (imports, legacy typing), 63 fixed automatically by `ruff check --fix`. About 10 B904 errors remain (`raise ... from err`).

---

## ADR-008: Condensing PROGRESS.md from 785 to ~80 lines

**Date:** 2026-02-03
**Status:** Accepted

**Context:** PROGRESS.md grew cumulatively over 21 stages. Most of the content was outdated (e.g. "next steps" from stage 5). The file did not fulfil the role of "where I am now".

**Options:**
- A) Keep it — full history, but hard to navigate
- B) Condense to 4 sections (status, checkpoints, last session, backlog) — a readable "here and now"
- C) As B, but add a separate DECISIONS.md for decisions — separating "what now" from "why"

**Decision:** Option C. PROGRESS.md = current state. DECISIONS.md = rationale for decisions. The history of the 21 stages remains in the git history. CHANGELOG.md covers changes per release.

**Consequences:** An AI agent reads PROGRESS.md and immediately knows what to do. Architectural decisions are in DECISIONS.md. Historical details are available via `git log` and `git show`.

---

## ADR-009: Expanding DEVELOPMENT_STANDARDS and IMPLEMENTATION_PROMPT

**Date:** 2026-02-03
**Status:** Superseded by ADR-048 (2026-10-25: `docs/DEVELOPMENT_STANDARDS.md` is deleted, DEV-1.3; see erratum 2)

**Context:** During the standardisation of the documentation, both files were initially deprecated (replaced by short notes). However, the full content is needed — the AI agent and developers need detailed instructions in the project context, not only references to shared/standards.

**Options:**
- A) Short notes referring to shared/standards — minimal, but requires reading two sources
- B) Expanded versions modelled on shared/standards, but with Kartograf examples — self-contained documents

**Decision:** Option B. DEVELOPMENT_STANDARDS.md (722 lines, 15 sections) and IMPLEMENTATION_PROMPT.md (284 lines, 11 sections) rewritten from scratch with current content (v0.3.2, ruff, all modules).

**Consequences:** The documents are self-contained — they do not require reading shared/standards. Cost: both sources must be kept up to date when the standard changes.

**Erratum 1 (2026-10-08, documentation review):** `IMPLEMENTATION_PROMPT.md`
was removed; its unique content (workflow, "What NOT to do", typical
tasks) moved to `docs/DEVELOPMENT_STANDARDS.md` (sections 15-17).
`DEVELOPMENT_STANDARDS.md` is henceforth the main source of the conventions and the process
of working on the project; `CLAUDE.md` was minimised to critical rules and
pointers (without the module tree, CLI examples and limitations), `README.md`
is an introduction to the project, and the usage details (CLI and library
examples, download result, campaigns, CLMS) are in `docs/USAGE.md`.
The self-containment principle of DEVELOPMENT_STANDARDS from the decision still holds;
the part concerning `IMPLEMENTATION_PROMPT.md` is outdated.

**Erratum 2 (2026-10-25, ADR-048):** `docs/DEVELOPMENT_STANDARDS.md` is deleted
(DEV-1.3: a project holds no copy of the Nogat standard). What was project-specific in it
moved: the critical rules, the rules for code (the CLI only translates, the catalog is the
source of commands, no default that chooses data, errors with registry codes), the session
workflow, the place of downloaded data and the commands are in `CLAUDE.md`; the recipes
for a new command, provider, PL parser and collection product are in `ARCHITECTURE.md` 4.11
and 5. The text of this decision, and every later entry that cites `DEVELOPMENT_STANDARDS`
or `STANDARDS x.y`, describes the document as it was and is not rewritten.

---

## ADR-010: The find_sheets_for_bbox algorithm — hierarchical clipping without WFS

**Date:** 2026-02-07
**Status:** Accepted

**Context:** A reverse lookup is needed: give a bbox, get a list of sheet codes. GUGiK does not offer a WFS for searching sheets by bbox. The topographic map grid is purely mathematical.

**Options:**
- A) WFS query to GUGiK — requires a network query, the service may be unavailable
- B) Brute force: generate all sheet codes, compute the bbox of each, check the intersection — O(n) where n = ALL sheets
- C) Hierarchical clipping: compute 1:1M and 1:200k mathematically, then drill down recursively with pruning — O(n) where n = FOUND sheets

**Decision:** Option C. Algorithm: (1) floor division for 1:1M (band/column), (2) a 12x12 grid for 1:200k with clamped row/col, (3) recursive get_children() + _bboxes_intersect() down to the target scale. Without any network query.

**Consequences:** Works offline. Fast (~1s for 1:10k). Depends on the correctness of _calculate_wgs84_bbox() — if the bbox logic changes, find_sheets_for_bbox will change too. CLI download sheet code becomes optional (nargs="?").

**Erratum 1 (2026-09-29, documentation audit; code state after the 0.7.0 audit
and the max review wave of 2026-09-28):** (a) since the 0.7.0 audit (A1-7) a positive
intersection area counts — touching edges are not an intersection;
(b) a bbox in EPSG:2180 is converted to a WGS84 envelope from 4 corners and 2
points on the central meridian 19°E (that is where the maximum width of the upper
edge lies — fact 8 of the max review wave); the envelope is wider than the bbox, so the
selection includes neighbouring sheets (the EPSG:2180 envelope of sheet
`N-34-130-D-d-2-4` gives 9 sheet codes, `N-34-130-D` at the 1:50000 scale — 16 instead of
4; in a large cutout up to ~3.7 km beyond the task); (c) `--system 2000` computes the
envelope from 4 corners (`core/parser_2000`, backlog).

**Erratum 2 (2026-10-07, parsers — `core/bbox.py`):** the envelopes from erratum 1
(b) and (c) are now computed by a single function `core/bbox.py::transform_bbox`
(`transform_bounds` with `densify_pts=21` per edge) — in `find_sheets_for_bbox`
and `find_sheets_2000_for_bbox`; item (c) from the backlog is closed. The rule
of positive area from (a) and the wider envelope of the EPSG:2180 bbox are unchanged.

---

## ADR-011: GugikNmptProvider inherits from GugikProvider

**Date:** 2026-02-07
**Status:** Accepted

**Context:** NMPT (digital surface model) uses the same mechanisms as NMT: WMS sheet indexes (Polish skorowidz) → OpenData ASC, WCS → GeoTIFF. It differs only in endpoints, layer names, coverage IDs and the lack of 5m.

**Options:**
- A) A separate class (copy the logic from GugikProvider) — duplication of ~200 lines of code
- B) Inheritance from GugikProvider — overriding only the class constants and __init__

**Decision:** Inheritance (option B). `GugikNmptProvider(GugikProvider)` overrides `WCS_ENDPOINTS`, `WMS_SKOROWIDZE_ENDPOINTS`, `WMS_LAYERS`, `COVERAGE_IDS`, `SUPPORTED_RESOLUTIONS` and `name`. Zero duplication of the download logic.

**Consequences:** ~100 lines instead of ~300. Every change in GugikProvider automatically propagates to NMPT. Risk: a change in GugikProvider may break NMPT — mitigated by tests.

---

## ADR-012: GugikOrtoProvider as a separate class (does not inherit from GugikProvider)

**Date:** 2026-02-07
**Status:** Accepted

**Context:** An orthophoto differs from NMT/NMPT in many ways: no vertical CRS, a different format (TIF, not ASC), a single WMS endpoint (not split into KRON86/EVRF2007), a different layer structure (a list instead of a dict-of-dicts).

**Options:**
- A) Inherit from GugikProvider — requires hacking vertical_crs=None, resolution=None, overriding many methods
- B) A separate class `GugikOrtoProvider(BaseProvider)` — its own implementation, ~250 lines

**Decision:** A separate class (option B). The differences are too large for inheritance to be clean. Duplicating ~50 lines (_download_with_retry, _make_request, _save_response) is acceptable.

**Consequences:** Readable code without hacks. The common methods may be extracted to a mixin/helper in the future. Evolution independent of NMT/NMPT.

---

## ADR-013: Renaming storage subdirectories from 1m/5m to nmt_1m/nmt_5m

**Date:** 2026-02-07
**Status:** Superseded by ADR-026; partly supersedes ADR-005 (directory names)

**Context:** After adding NMPT and Orthophoto, the `1m` and `5m` subdirectories in FileStorage became ambiguous — they could denote the resolution of any product. The new products use the `nmpt` and `orto` subdirectories.

**Options:**
- A) Keep `1m`/`5m` — simple, but inconsistent with `nmpt`/`orto`
- B) Change to `nmt_1m`/`nmt_5m` — unambiguous, consistent with the product/ convention

**Decision:** Option B. Structure: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`. FileStorage uses the `_RESOLUTION_SUBDIRS` mapping to translate the resolution into a subdirectory name.

**Consequences:** Breaking change — the old paths `data/1m/` and `data/5m/` are not compatible. Unambiguous structure. The `product` parameter in FileStorage allows new products to be added easily.

**Erratum 1 (2026-08-28, ADR-026):** the `nmt_1m`/`nmt_5m` layout was replaced by the segments
`nmt/pl_<crs>_<res>_<vcrs>` — see ADR-026.

---

## ADR-014: BDOT10k category-based extraction (pt vs hydro)

**Date:** 2026-02-08
**Status:** Superseded by ADR-016

**Context:** The BDOT10k ZIP from GUGiK contains ~60 GPKG files per county (Polish powiat), including land cover layers (PT*) and hydrography layers (SW*). Until now, extraction filtered only on `_PT` in the file name. There is a need to download hydrographic data (rivers, canals, ditches) without changing the existing API.

**Options:**
- A) A separate provider `Bdot10kHydroProvider` — duplicated download logic, a new dispatch in LandCoverManager
- B) A `category` parameter in the existing Bdot10kProvider — `CATEGORY_FILTERS` maps the category name to file filtering patterns in the ZIP
- C) A `layers` parameter with a list of layers — flexible, but requires the user to know the layer codes

**Decision:** Option B. Added `CATEGORY_FILTERS = {"pt": ["_PT"], "hydro": ["_SW", "_PTWP"]}`. The `category` parameter (default `"pt"`) is passed through `download_by_teryt()` → `_download_with_retry()` → `_extract_gpkg_from_zip()`. Backward compatible — the default behaviour does not change.

**Consequences:** Zero code duplication. New categories are easy to add in the future (e.g. `"transport"` for DR* layers). PTWP is shared by both categories (land cover and hydrography). CLI: `--category {pt,hydro}` — simple and discoverable.

---

## ADR-015: pyshp + sqlite3 instead of fiona for reading geometry

**Date:** 2026-02-08
**Status:** Accepted — amended by ADR-042 (GPKG writing via pyogrio; envelope reading unchanged)

**Context:** The user needs to download data for areas defined by SHP/GPKG files. A library is needed to read the geometry.

**Options:**
- A) fiona (OGR bindings) — full format support, but ~150MB surface area, shares GDAL with rasterio but adds a Python wrapper
- B) pyshp + sqlite3 — pyshp (~100KB, pure Python) for SHP, sqlite3 (stdlib) + struct.unpack for GPKG envelope parsing. Zero C dependencies.
- C) geopandas — the most convenient API, but huge dependencies (pandas, fiona/pyogrio, shapely)

**Decision:** Option B. Full OGR is not needed to extract per-feature bounding boxes. pyshp reads `.shp` natively (shape.bbox). GPKG is SQLite — the envelope is in the binary geometry header (GeoPackage Binary: magic + flags + SRS + 4×float64). The CRS comes from `.prj` (WKT) and `gpkg_spatial_ref_sys` (WKT). Transformation via pyproj (already a dependency).

**Consequences:** Minimal dependencies (+1 package ~100KB). No support for formats other than SHP/GPKG — acceptable, because these are the only formats used in the Polish GIS workflow. Envelope parsing is brittle (depends on the GeoPackage Binary specification) but stable and well documented.

---

## ADR-016: BDOT10k — removing category filtering, downloading the whole file

**Date:** 2026-03-02
**Status:** Accepted; supersedes ADR-014

**Context:** Category filtering (pt/hydro) in Bdot10kProvider added in ADR-014 turned out to be an unnecessary complication. The user downloads the whole ZIP from GUGiK anyway — client-side filtering caused data loss (e.g. SW* layers skipped by default). It is better to download everything and let the user filter in GIS.

**Options:**
- A) Keep category — backward compatible, but complicates the API and loses data by default
- B) Remove category, download everything — simpler API, no data loss

**Decision:** Option B. Removed `CATEGORY_FILTERS`, `PT_LAYERS`, `HYDRO_LAYERS`, the `category` parameter from methods, the CLI argument `--category`. `_extract_gpkg_from_zip()` extracts all GPKG files from the ZIP and merges them into one file. `get_available_layers()` returns all 15 layers.

**Consequences:** Breaking change — code using `category="hydro"` must be updated (the parameter is ignored by `**kwargs`). Simpler API. No data loss. 835 tests (down from 849 — 14 category tests removed).

---

## ADR-017: PL-2000 sheet naming — composition pattern with auto-detection

**Date:** 2026-02-24
**Status:** Accepted — amended by ADR-026 (own PL-2000 segments; erratum 1)

**Context:** PL-2000 is a different sheet system than PL-1992. PL-2000 uses the format `strefa.pas.slup[.podpodzialki]` (e.g. `6.179.12.20`), 4 meridian zones (EPSG:2176-2179) and scales from 1:10k to 1:500. It requires a separate parser with different BBox and hierarchy logic.

**Options:**
- A) Inheritance: Parser2000(SheetParser) — problematic because SheetParser is tightly bound to PL-1992 (letter-based belt/column, different scales)
- B) Composition: SheetParser delegates to Parser2000 — loose coupling, format auto-detection
- C) A separate class without integration — no unified API

**Decision:** Option B. Composition pattern: `SheetParser` detects the sheet code format via the regex `^[5-8]\.\d` and delegates to `Parser2000` (lazy import). Auto-detection is transparent — the user uses `SheetParser("6.179.12")` and does not need to know about Parser2000. BBox in the native zone CRS (EPSG:2176-2179), not EPSG:2180. `find_sheets_for_bbox(bbox, system="2000")` dispatches to `find_sheets_2000_for_bbox()`.

**Consequences:** Clean separation of PL-1992 and PL-2000 logic. Auto-detection in SheetParser keeps the unified API. New exports: `Parser2000`, `find_sheets_2000_for_bbox`. CLI: `--system {1992,2000}` allows forcing the system. FileStorage: subdirectory `nmt_2000_1m` for PL-2000 sheets.

**Erratum 1 (2026-08-28, ADR-026):** the `nmt_2000_1m` subdirectory announced here
never came into being (PL-2000 sheets landed in `nmt_<res>/` next to PL-1992 —
see the note in CHANGELOG 0.5.0). The deferral was closed in ADR-026: PL-2000 has
its own `pl_2000_*` segments.

---

## ADR-018: ThreadPoolExecutor for parallel downloads

**Date:** 2026-03-03
**Status:** Accepted; erratum 2: download pools via `kartograf.interrupt.run_parallel`: Ctrl-C cancels the queue and stops transfers (E2E test 0.8.0)

**Context:** Downloading a sheet hierarchy (e.g. N-34-130-D → 256 sheets at 1:10000) was sequential, which with a slow connection to GUGiK took a very long time. Parallelism is needed.

**Options:**
- A) asyncio + aiohttp — fully asynchronous, requires refactoring the whole I/O stack
- B) ThreadPoolExecutor — simple addition to existing code, requests is thread-safe
- C) multiprocessing — separate processes, greater overhead, harder state sharing

**Decision:** ThreadPoolExecutor (B). Requests is thread-safe, an I/O-bound task is ideal for threads, minimal refactoring. `max_workers=4` as the default, configurable via CLI `--workers`.

**Consequences:** Thread-safe temp filenames are required in all providers (pattern `pid_threadid.tmp`). DownloadResult instead of list[Path] for structured results. Backward compatible: `max_workers=1` gives sequential downloads.

**Erratum 1 (2026-09-29, documentation audit):** `max_workers=4` is the default
in the CLI (`--workers`), and in the library it is 1 (`DownloadManager`,
`download_pl_cutout`, `run_pl_cutout`). The methods return `list[Path]`,
and the structured result (`DownloadResult`: succeeded/failed/skipped/no_coverage)
goes to `DownloadManager.last_result`.

**Erratum 2 (2026-10-19, E2E test 0.8.0):** download pools
(`DownloadManager`, collections, BDOT10k counties, LAZ tiles for PL and CZ) go
through a single helper `kartograf.interrupt.run_parallel`. An exception
in the waiting thread (Ctrl-C, unit error) cancels the unstarted units
and sets a stop flag, which running units see in `check_stop()`
(HTTP transport: before an attempt, between chunks, instead of the retry pause;
`commit_version`); a unit ends with `Stopped` (a subclass of
`KeyboardInterrupt`), so the same clean-up runs as with
`--workers 1`, and nothing is committed after the interruption. The flag is per
pool (`threading.local`), with no global state. What remains: a query
blocked on the network and probe pools (`executor.map`) do not hear the stop.

---

## ADR-019: SQLite WAL as metadata cache

**Date:** 2026-03-03
**Status:** Accepted — amended by ADR-028 (`record_cache` instead of `url_cache`; erratum 1) and ADR-030 (`campaigns_cache`; erratum 2)

**Context:** Each sheet download requires a request to the GUGiK API for the OpenData URL. With repeated downloads the same URLs are queried many times. Likewise BDOT10k — the point→TERYT mapping.

**Options:**
- A) SQLite with WAL mode — local file, zero dependencies, concurrent reads, TTL
- B) Redis — fast, but requires a server, overengineering
- C) Pickle/JSON file — simple, but no concurrent access, no TTL

**Decision:** SQLite WAL (A). Zero additional dependencies (sqlite3 in stdlib), WAL mode enables concurrent reads from ThreadPoolExecutor, a TTL of 7 days prevents stale data, threading.Lock protects writes.

**Consequences:** New module `kartograf/cache/metadata.py`, `.kartograf_cache.db` in the working directory, CLI `kartograf cache` for management. `prune_expired()` cleans stale entries. Optional — providers work without the cache.

**Erratum 1 (2026-09-30, repair wave, ADR-028):** the PL CLI attaches `MetadataCache` to NMT/NMPT/orto
except with `--force` (this mode bypasses the cache). The cutout API has `cache=`.
The cache stores `record_cache` (the full `source` or a confirmed
`no_coverage`, TTL 7 days), not just URLs; `url_cache` is dropped
when the database is opened, `get_url/set_url` were replaced by `get_record/set_record`.
`stats()["record_count"]` and the CLI `Record entries` report the new entries.

**Erratum 2 (2026-10-07, review-2 E14 and D16; ADR-030):** `--force` no longer
bypasses the cache, only its READ: `MetadataCache(refresh=True)` writes the
freshly chosen record (ADR-028 erratum 1); likewise the SM5 sheet index of the CZ track
(`sheet_cache`, TTL 30 days). ADR-030 added the table `campaigns_cache` (the list
of campaigns of a sheet, TTL 7 days).

---

## ADR-020: Validating WMS layers via GetCapabilities

**Date:** 2026-03-24
**Status:** Accepted — partly superseded by ADR-028 (layers solely from GetCapabilities, no hardcoded lists and no fallback; erratum 3)

**Context:** The hardcoded WMS layer names in GugikProvider turned out to be wrong for NMT 5m — GUGiK changed the layer names (e.g. `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`, added `SkorowidzeNMT2025`). The error caused all NMT 5m downloads to fail. A mechanism is needed to detect discrepancies between hardcoded and live WMS.

**Options:**
- A) Validation on provider initialisation — a GetCapabilities query in `__init__()`, immediate detection
- B) Lazy validation — a query on the first `_get_opendata_url()`, no cost if the provider is not used
- C) Periodic validation — cron/timer every N hours
- D) No validation — relying on hardcoded values, manual update

**Decision:** Lazy validation (option B). New methods `_fetch_wms_layers()` (GetCapabilities XML → list of layers) and `_get_validated_layers()` (comparing hardcoded with live). Validation is performed once, the result is cached in memory per provider instance (without a lock — benign duplicate on concurrent access). A separate 10s timeout for GetCapabilities (shorter than the standard 30s). On a discrepancy: warning + auto-update to the live layers. On a GetCapabilities error: warning + fallback to the hardcoded layers.

**Consequences:** Automatic detection of WMS layer changes without manual code updates. Zero cost if the provider is not used (lazy). GugikNmptProvider inherits the validation from GugikProvider without additional code. GugikOrtoProvider is out of scope (a different inheritance hierarchy, a different layer format). 17 new tests in `tests/test_wms_layer_validation.py`.

**Erratum 1 (2026-06-24, orthophoto validation and 2026 vintages):** GugikOrtoProvider received its own validation (`_fetch_wms_layers`/`_get_validated_layers`, excludes the `Zasiegi` variants). The layer names for NMT 1m/EVRF2007 and Orto were refreshed (new 2026 vintages).

**Erratum 2 (2026-09-29, history before the repair wave):**
GetFeatureInfo could return HTTP 200 with an OGC report instead of a
valid empty response; such a report signals a layer failure,
not `NoCoverageError` (ADR-027). The old fallback to hardcoded layers
could request outdated names and lose newer records; the erratum below
replaced this policy.

**Erratum 3 (2026-09-30, repair wave):** the hardcoded `WMS_LAYERS` for
NMT/NMPT/orto were removed. Layers come only from GetCapabilities,
discovered lazily and cached per instance with a lock; a GetCapabilities
fetch error is not remembered nor replaced with the old list.
GetFeatureInfo expects a template of an empty or full response
(`var ... = [];`); an OGC report or a wrong template is a `DownloadError`
without silent degradation to an older campaign. Transport queries
have 3 attempts, and orto uses the same record parser.

**Erratum 4 (2026-10-06, review N3, E10):** the "separate 10s timeout for
GetCapabilities" no longer applies: the sheet index GetCapabilities inherits the
provider timeout (`DEFAULT_TIMEOUT`: 30 s `GugikProvider` — NMT and NMPT,
60 s `GugikOrtoProvider`) or the `timeout=` passed to the download — a GetCapabilities
failure ends the whole track, so the limit cannot be shorter than for
downloading a sheet. Only transport errors are retried (ADR-028 erratum 1).
Layer discovery lives in the shared `SkorowidzLayersMixin`
(`providers/pl/skorowidz.py`: `_fetch_wms_layers`, `_layers`);
`_get_validated_layers` does not exist.

---

## ADR-021: LAZ (LIDAR point clouds) — discovery via WFS, area-based

**Date:** 2026-06-24
**Status:** Accepted — partly superseded by ADR-029 (newest-per-tile rule)

**Context:** Adding download of LAZ files (ALS survey data) from GUGiK. Two problems: (1) LAZ tiles have sheet codes finer than 1:10000 (e.g. `M-34-27-B-b-2-1-1`, module 1:1000), while `SheetParser` parses at most down to 1:10000 — the tile sheet code cannot be parsed; (2) the LAZ sheet index **WMS** service (`DanePomNMT/WMS/...`) returns HTTP 401, so the WMS GetFeatureInfo mechanism (as in NMT/orthophoto) does not work.

**Options considered:**
- A) Extend `SheetParser` to 1:1000 (PL-1992 + PL-2000) and download by tile sheet code — a lot of work, and the sheet code is opaque in the URL anyway
- B) Discovery via **WFS** GetFeature by bbox — open service (HTTP 200), the feature contains `url_do_pobrania` directly; the tile sheet code as a label (no parsing)
- C) Constructing the URL from the pattern `.../{density}/{density}_{id}_{godło}.laz` — requires an unpredictable `id` → infeasible
- D) ATOM/CSW — more complex and less direct than WFS

**Decision:** Option B. `GugikLazProvider` with area-based discovery: sheet code (≤1:10000) / `--bbox` / `--geometry` → bbox EPSG:2180 → WFS GetFeature (`gugik:SkorowidzDanychPomiarowychLIDAR{rok}`) → tiles with `url_do_pobrania`. The tile sheet code is opaque, no changes to `SheetParser`; two WFS services by vertical CRS, newest-per-tile by default (from 2026-10-07: the newest tile per AREA — ADR-029) and the `--year`/`--min-density` filters. The historical implementation sent EPSG:2180 axes as (E,N), which was corrected in the erratum below.

**Consequences:** No changes in `SheetParser`: the tile sheet code remains opaque. LAZ has a separate flow `_cmd_download_laz` (area→WFS→tiles→parallel download; from 2026-10-07 download and sidecar are in the library `download/laz.py`, the CLI is a wrapper — ADR-029). WFS provides year/density/CRS; the vintages come from GetCapabilities (no hard-coded list fallback). Live results from before the axis fix confirmed the LASF format, not the correct tile position.

**Erratum 1 (2026-09-29, historical diagnosis):** the original
"verified live" checked incorrectly paired BBOX and envelope:
`urn:ogc:def:crs:EPSG::2180` requires (N,E), while the old client used
(E,N). Near Spytkowice the response with the wrong order directed
to Lubuskie instead of the correct tile `M-34-76-A-a-1-1-3`.
The fix below replaced these assumptions.

**Erratum 2 (2026-09-30, fix K1/N7):** for WFS `urn:ogc:def:crs:EPSG::2180`
`BBOX` and reading `gml:Envelope` use EPSG axes (N,E);
the guard checks that at least one returned tile intersects
the requested area (when all are outside it, `DownloadError`).
The vintages come from GetCapabilities (no `FALLBACK_YEARS`); an error
of any vintage after retries ends `discover_tiles` with
`DownloadError`, not a misleading empty result.

---

## ADR-022: Multi-country source architecture — descriptors, registries, sidecar, strict transformation policy (stage 0)

**Date:** 2026-08-10
**Status:** Accepted — amended by ADR-023 (formal engine interface: `CuzkClient`, (a)) and ADR-031 (English sidecar key names)

**Context:** Directional decision: extension to Czechia (full product parity), then Germany and Slovakia (cross-border analyses). Research on 3 countries (docs/research/2026-08-10-*) yielded 4 real cases for designing the abstraction boundaries and revealed pitfalls: DE = a federation of 17 models; SK WCS returns ellipsoidal heights (42.3 m deviation from Bpv); PROJ silently returns identity (ballpark) when there is no network; transformation grids of foreign countries return inf outside their area; CZ fills the area outside the border with zeros (without metadata 0 m passes for sea level). Spec: docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md.

**Options considered:**
- A) Add countries by extending the existing GUGiK-centric classes
- B) Stage 0: sources described declaratively (descriptors as data), a metadata sidecar, a strict transformation policy, a common transport; providers per country in providers/<cc>/
- C) Full extraction of transport engines (WMS sheet index/WCS) right now

**Decision:** Option B. `sources/` (SourceDescriptor/AccessChannel/registry; zero IO), `sources/sidecar.py` (ResultMetadata + `<file>.meta.json` after every successful download — a contract for Hydrograf, which merges cross-border data), `transform/crs.py` (TransformerGroup with allow_ballpark=False; rejecting operations of unknown accuracy — in pyproj accuracy=-1, 0.0 means an exact operation and IS accepted; a probe at a control point rejects foreign-country grids returning inf; isfinite on every result), `transport/http.py` + `transport/mosaic.py`, `core/parser_registry.py`, ABC unification (DataSourceProvider; download_by_admin_unit with teryt aliases), relocation of providers/pl/ WITHOUT shims (user decision: Hydrograf/Hydrolog will adapt their imports; the stable surface = `from kartograf import ...`). Option C rejected: the only consumer of WMS sheet indexes is GUGiK, extraction now is a risk for ~1060 tests with no gain; the formal engine interface will arise in stage 1 with CuzkClient.

**Consequences:** Identical behaviour (invariant of ~1060 tests with no assertion changes); the only observable change is the `.meta.json` sidecars. BREAKING for deep imports (table in CHANGELOG). Stage 1 (CZ DMR) builds on the pl/ provider factory, the descriptors and the transformation policy.

---

## ADR-023: CUZK engine, CZ CRS policy and EVRF2007→5621 (stage 1)

**Date:** 2026-08-11
**Status:** Accepted — partly superseded by ADR-024 (TM33 download mechanism in (c), Additional findings item 1) and ADR-027 (`--target-crs` for CZ only; Additional findings item 6) and ADR-038 (CZ area always as a cutout; now `--cutout`); amended by ADR-029 ((f).1 covers LAZ) and ADR-034 (CUZK chunking in `transport/chunks.py`); amends ADR-022; erratum 2: `--country` required with an area, values per country (0.8.0)

**Context:** Stage 1 adds the first foreign data source — CUZK (Czech
Office for Surveying, Mapping and Cadastre), DMR 5G (2 m, `exportImage`)
and DMR 4G (5 m, openzu files + `exportImage`). It is the first real consumer of the stage 0
architecture (descriptors, sidecar, `transform/crs.py`), so several stage 0
decisions marked "deferred to stage 1" (formal engine interface,
explicit channel selection, probe under the network policy) had to be closed.
Live reconnaissance (`docs/research/2026-08-11-etap1-rekonesans.md`) and E2E
(`docs/research/2026-08-11-etap1-e2e.md`) verified the spec's assumptions and
forced several corrections (among others the asymmetric `exportImage` limit 15000x4100 px,
the CRS from `exportImage`/openzu always requires overriding, the actual `PODIL`/`MAPNAME`
values of CTES96). The consultation with the user at the plan stage
(2026-08-11) settled three open questions of the spec (`parent_request`,
`--target-crs` + sheet code, polymorphism of `PinnedTransform.transform`).

**Decisions:**

(a) **`CuzkClient` (`kartograf/providers/cuzk/client.py`) as the first
descriptor-driven engine.** The methods `query()`, `export_image()`, `fetch_file()`
are generic, parametrised by the URL from `AccessChannel.endpoint` (a new descriptor
field) — the client knows no sheet codes, products or sidecars (cf. the module
docstring). This fulfils the announcement in ADR-022 ("the formal engine interface will arise
in stage 1 with CuzkClient"). Nevertheless `CuzkClient` **stays** in
`providers/cuzk/`, not in `transport/` — extraction of a common "ArcGIS
REST engine" (analogous to `transport/http.py`/`transport/mosaic.py`) is
deliberately deferred until the **second consumer** of the same pattern (DE/SK have
a similar REST/WCS API) — one consumer does not yet justify an abstraction
(in line with the rejection of option C in ADR-022).

(b) **The CZ flow bypasses `DownloadManager`** — the LAZ precedent (ADR-021).
`CuzkDmrProvider` and the CLI (`_cmd_download_cz`) do not call
`download_sheet()`/`download_bbox()`; they have their own flow, because the CZ data model
differs structurally from PL: a CZ sheet code (TM33 or SM5) **always** yields
exactly one file — there is no sheet hierarchy to expand as in PL-1992.
The `DownloadManager` API remains untouched; the only point of contact is the
additive parameter `sidecar_extra` (Task 13), used by the PL CLI in the
`--bbox`/`--geometry` mode (Task 17) to attach the common `parent_request`.

(c) **TM33 in sheet code mode downloaded in EPSG:3045; PL/CZ bbox mode
asymmetry.** The TM33 tile grid (2x2 km, `{E_km}_{N_km}`) is defined in
ETRS89/UTM33N (EPSG:3045, `ParserTM33` — mathematically computable, a formula like
`Parser2000`), even though the DMR 5G data lie natively in S-JTSK/Krovak (EPSG:5514,
`AccessChannel.horizontal_crs` of the `ARCGIS_IMAGE` channel). *(The download mechanism
described further in this item is SUPERSEDED by ADR-024: the `exportImage` request
goes in native 5514, and the reprojection of the tile to 3045 is done by a local warp
with a pinned operation; the definition of the tile grid in 3045 and the PL/CZ bbox
asymmetry remain valid.)* Download by sheet code
therefore requested `exportImage` with `bboxSR=imageSR=3045` — the server reprojected on the fly;
the "native" product of the CZ sheet code mode is 3045 (the tile grid definition), not
5514 (the CUZK data storage CRS). This creates an explicit asymmetry relative to PL: `--bbox` in PL
returns a **list of sheets** from OpenData (many files by sheet code, `find_sheets_for_bbox`
+ a download loop), `--bbox` in CZ returns **one file** — a direct server-side
cutout from `exportImage`, because CZ has no equivalent of "OpenData by arbitrary
bbox". The asymmetry is documented (research step 5, spec), not hidden.

(d) **EVRF2007 = EPSG:5621 globally + family→realisation map** (BREAKING
limited to `vertical_crs_code`). User decision 2026-08-11:
`vertical_crs_code("EVRF2007")` now returns the pan-European **EPSG:5621**
(not the Polish realisation EPSG:9651) — because `EVRF2007` is now the name of a FAMILY
of CRSs, common to PL and CZ (Bpv→EVRF2007 is an operation to 5621, not to
any national realisation). The new function `resolve_vertical_crs(name, options)`
maps the name to the family code, but if a channel declares in
`vertical_crs_options` a national realisation (PL: EPSG:9651) instead of the code
of the family, it returns the realisation. Effect: PL sidecars still carry the actual code
9651 (content unchanged), and BREAKING concerns **only** direct calls of
`vertical_crs_code("EVRF2007")` from outside Kartograf (Hydrograf/Hydrolog, if
they call the function directly). The old/new code map — see CHANGELOG.

(e) **`Bpv` = EPSG:8357 (Baltic 1957, not 1977); vertical 8357→5621 pinned
operation 0.1 m; KRON86 unreachable for CZ.** The native vertical CRS of
CUZK is Bpv (Baltický po vyrovnání) = EPSG:8357, the **Baltic 1957** realisation
(confirmed by the `vcsWkid` of the `ImageServer` services and the PROJ operation name
"Baltic 1957 height to EVRF2007 height (1)") — **not** Baltic 1977
(EPSG:5705, a different realisation, easy to confuse by name). The transformation
8357→5621 is a pinned EPSG operation with an accuracy of 0.1 m; the offset measured
live (E2E, 64722 pixels) is **+0.132366 m** (std 2.22e-05), within the expected
reconnaissance range +0.112..+0.148 m (gradient ~+0.014 m/degree of latitude,
increasing S→N). The transformation 8357→9650 (KRON86, the Polish realisation
Kronstadt 86) is **unreachable** — the only PROJ paths are ballpark
(the grids `pl86_2019`/`pl07_2019` are not public) and are strictly rejected
by `allow_ballpark=False` (ADR-022); the user gets
`TransformUnavailableError` with a remedy ("zainstaluj siatki recznie do
`PROJ_DATA` albo uzyj EVRF2007 (EPSG:5621)").

(f) **Resolutions from the 2026-08-11 consultation (binding):**
1. `extra.parent_request` is written **always** in the
   `--bbox`/`--geometry` mode (auto AND explicit `--country`), **never** in the sheet code
   mode. The grouping key is an identical `bbox`+`bbox_crs` — it enables the
   scenario of two-stage fetching of a second country for the same task
   (e.g. first `--country pl`, then `--country cz` for the same bbox:
   both sets of sidecars will have the same `parent_request` and can be
   grouped on the Hydrograf side).
2. `--target-crs` together with a CZ sheet code is a hard `ValidationError`
   (server-side reprojection makes sense only relative to a requested area
   `--bbox`/`--geometry`; a single tile downloaded by sheet code is by definition
   already a native 1:1 product — see also item 1 below).
3. `PinnedTransform.transform` is **polymorphic** (scalars or `numpy`
   arrays, `np.isfinite` instead of `math.isfinite`) instead of a separate method
   `transform_grid` — reconnaissance (Task 1, step 7d) showed that
   `math.isfinite` raises `TypeError` on `numpy.ndarray`, and per-pixel vertical
   transformation of the whole raster (Task 12) requires an array call.

(g) **`None` sentinels for `--resolution`/`--vertical-crs`/`--system`
resolved per country.** The CLI (`cli/_parser.py`) changed the defaults
of these three flags from hard-coded PL defaults to the sentinel
`None`, resolved only after the target country is determined (from the sheet code
or `--country`) — PL and CZ have disjoint defaults (PL: 1m/EVRF2007/1992 unchanged;
CZ: 2m/Bpv, `--system` not applicable). One `argparse.ArgumentParser`
serves both countries without duplicating flag definitions and without guessing the country
before it is determined.

**Additional findings (closing the commitments collected during
implementation — the controller ledger `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`
was not preserved: the directory is outside git, the file is lost; the only
surviving record of these commitments is the points below and PROGRESS.md):**

1. **Semantics of `transform.horizontal` in sidecars** — **SUPERSEDED by
   ADR-024 (2026-08-11)**. Originally: "reprojection ordered by the
   user (`--target-crs`)", NOT "server work" — a TM33 tile downloaded by
   sheet code had `transform: null` (despite the server-side 5514→3045 reprojection
   inside `exportImage`), and a bbox with `--target-crs` had
   `transform.horizontal = "server:EPSG:<code>"`. Measurements from 2026-08-11
   showed that "server work" is not an implementation detail that
   can be passed over in silence: server-side reprojection lost the datum transformation
   (error of 135 m). Since ADR-024 Kartograf does not use it at all, and the field carries
   the pinned local operation with its accuracy — for BOTH modes, including the sheet-code-based TM33.
   The implementation described below (`server_crs`
   in `_write_cz_sidecar()`) no longer exists. The distinction on the vertical side
   remains unchanged: the authoritative signal of the
   actual transformation is `transform.vertical` (e.g.
   `"pinned: Bpv->EVRF2007"`), NOT `vertical_source` — `vertical_source`
   describes only the **source channel** (`"native"` for CUZK), so it stays
   `"native"` also when `vertical_crs` in the sidecar is already after
   conversion (e.g. `EPSG:5621` after Bpv→EVRF2007, see point (e)); this is not
   an inconsistency, but two different fields describing two different things.
2. **Eager import of `rasterio` on `import kartograf`** (CZ exports in
   `__init__.py`, Task 18): `providers/cuzk/client.py` imports `rasterio`
   at module level (needed for `export_image`/`fetch_file`), and
   `CuzkDmrProvider` imports `client.py` at module level — as a result
   a plain `import kartograf` **for the first time** eagerly loads `rasterio`
   (GDAL/PROJ bindings), with a measured cost of **+55–65 ms** (from ~185 ms to ~244 ms,
   3x measurement with `time.perf_counter()`). This is a **failure-domain** change: a broken
   GDAL/PROJ (e.g. a missing native library in the Hydrograf/
   Hydrolog environment) now breaks `import kartograf` itself, not only the first
   call of a raster function. Decision: the simple variant was accepted (eager,
   plain top-level import, stylistically consistent with the rest of `__init__.py` —
   `GugikOrtoProvider`, `Bdot10kProvider` etc. are exported identically),
   lazy loading (`__getattr__`/PEP 562) was NOT introduced in `__init__.py` —
   `rasterio` is a hard, required dependency of the whole package
   (pyproject: `rasterio >= 1.3.0`), so this is a shift in time of the moment
   of loading, not a new dependency; and almost every real CLI operation on
   CZ data immediately needs `rasterio` anyway. **Future fix path**
   (outside the scope of stage 1): move `import rasterio`/
   `from rasterio.crs import CRS` in `providers/cuzk/client.py` and `dmr.py` to
   function/method level, analogously to the pattern already used in
   `hydrology/hsg.py` and `transport/mosaic.py` — they would restore lazy loading
   without changing the public API.
3. **`parent_request.countries` is the countries ATTEMPTED, not downloaded.** When
   one country fails in `--country auto` mode (e.g. CZ returns
   `DownloadError`), the sidecars of the other country (PL) still carry
   `countries: ["CZ", "PL"]` — the field describes the intent of the task (which countries
   the bbox crosses), not the fact of a successful download per country. In addition,
   `parent_request.bbox_crs` **differs per mode for the same geometry
   file**: explicit `--country cz` writes the CRS of the geometry file (e.g.
   EPSG:5514/3045), while `auto`/explicit `--country pl` writes EPSG:2180 —
   so the same `.shp` file used in two CLI invocations (once `--country cz`,
   once without the flag) will NOT produce an identical `parent_request` despite
   an identical user task. This is a known limitation of the grouping key
   (point f.1) — to be unified in stage 2 (see also
   `docs/SCOPE.md`, the limitations section).
4. **Rectangular country extents send CUZK queries also outside the actual
   CZ border.** `CountryProfile.extent_wgs84` for CZ is the rectangle
   `BBox(12.09, 48.55, 18.86, 51.06)` (an envelope, not a border polygon) —
   every `--country auto` task in southern Poland (lon < 18.86°E, lat <
   51.06°N — the strip west of 18.86E and south of 51.06N - among others Opole,
   Walbrzych, Rybnik, the southern outskirts of Wroclaw; Krakow, Rzeszow and the centre of
   Wroclaw (51.11N) lie outside the rectangle) sends a query to CUZK, even though the
   bbox actually lies entirely in Poland. The result is:
   an additional raster filled with `nodata` (`-9999`) + an additional CZ sidecar without
   useful data, not an error — but unnecessary network traffic and an unnecessary file.
   The proper fix (an administrative border polygon instead of a rectangle)
   is planned for stage 2 (see `docs/SCOPE.md`).
   **Symmetry (0.7.0 audit, finding A3-2):** the same happens in the other
   direction — the PL rectangle is `BBox(14.07, 49.00, 24.20, 54.90)`, so it covers
   almost all of Czechia east of Pilsen and `--country auto` in Prague, Brno
   or Ostrava also queries GUGiK. The result is however different from the CZ
   side: missing GUGiK data is a hard `DownloadError`, not an empty raster, so
   `max(exit_codes)` turned a correctly downloaded CZ raster into exit code 1 of the whole
   command. Since 0.7.0 the failure of ONE country when the other succeeds (only
   in `auto` mode and only with more than one country) ends with exit
   code **0** with a `Warning:` on stderr; `max(exit_codes)`
   stays for explicit `--country` (the user specified the scope) and for the
   case in which all countries failed. Information about incomplete coverage
   is not lost: the sidecars still carry `parent_request.countries` = the countries
   ATTEMPTED (point 3).
5. **Addendum 2026-08-22 (0.7.0 pre-release audit, finding N6-2): PL-only
   options resolve `--country auto` instead of failing the task.**
   A second effect of the rectangular envelopes (point 4) was that a task lying
   ENTIRELY in Poland but inside the CZ rectangle (the strip west of 18.86E and
   south of 51.06N - among others Opole, Walbrzych, Rybnik, the southern outskirts of
   Wroclaw; not the whole of southern Poland, see point 4 (Krakow and Rzeszow outside the
   rectangle)) ended with code 1 when the user gave an
   option with no Czech equivalent: `--product nmpt|orto`, `--system`,
   `--vertical-crs KRON86`, `--resolution 1m` (e.g. `kartograf download --bbox
   442802,248390,444802,250390 --system 2000` near Raciborz ->
   `Error: --system dotyczy tylko PL`). Relative to 0.6.1, where `--country`
   did not exist at all, this was a hard regression of commands documented since
   v0.4.0/v0.5.0. Since 0.7.0 such an option RESOLVES the country: the CLI prints
   `Info: --country auto -> pl (<options> dotyczy tylko PL)` to stderr and then
   behaves exactly like an explicit `--country pl` — without clipping the bbox
   to the country envelope, with `parent_request.countries == ["PL"]`. The resolution
   covers only ACTUALLY disputed areas (`auto` mode, more than one
   country, PL among them): an area lying entirely in Czechia still gets
   the stage 2 message, because choosing PL there would be nonsense rather than reading
   the intent. `--product laz` does NOT belong to this list despite being PL-specific — it has
   its own flow (`_cmd_download_laz`) with its own cross-border guard
   and never reaches the area dispatch. Cost: a border bbox
   with `--system 2000` will no longer get the Czech part (until now it got
   nothing — code 1, so the change is strictly better), and `-q` does not suppress the
   `Info:` message, because it goes to stderr (like `Error:`/`Warning:`).
6. **Addendum 2026-08-28 (ADR-027): `--target-crs` ceases to be a
   Czech-only flag.** In `--bbox`/`--geometry` mode it also works for PL
   (one merged cutout), and on the border `--country auto --target-crs`
   gives two cutouts in the same CRS with a shared
   `extra.parent_request`. `--target-crs` therefore is NOT added to the list of options
   resolving the country from point 5 (`_pl_only_flags`) — it works on both
   sides of the border, so it does not resolve in either direction. The asymmetry from point
   (c) applies from now on only without `--target-crs`: with this flag a PL bbox gives
   one merged cutout.

**Consequences:** Full DMR product parity between PL and CZ (sheet code,
bbox, optional horizontal/vertical transformation). 1381 tests green
(+244 relative to the state after stage 0), coverage ~89%, ruff/mypy with no new
debt relative to baseline, E2E 11/11 PASS on live CUZK+GUGiK data
(`docs/research/2026-08-11-etap1-e2e.md`). BREAKING limited to
`vertical_crs_code()` (a public function, but a niche one — most
consumers use sidecars, which carry the actual code with no change in content).
Stage 2 (DMP/Orto/LAZ CZ, border polygon, unification of `parent_request`)
builds on the same `CuzkClient`/descriptors — a further consumer may
justify extracting the engine to `transport/` (point a).

**Erratum 1 (2026-09-29, documentation audit and live tests;
`docs/research/2026-09-29-live-e2e-i-audyt-docs/`):**
- point (f).2: "a single tile downloaded by sheet code is by definition
  already a native 1:1 product" — no longer valid for TM33 since ADR-024: a TM33
  tile is a local warp from EPSG:5514 to the EPSG:3045 grid; the SM5 sheet
  and PL sheets give 1:1. The rejection of `--target-crs` with a sheet code stays (the sheet code
  determines the scope and CRS of the product);
- point 3 ("explicit `--country cz` writes the CRS of the geometry file, while `auto`/
  `--country pl` — EPSG:2180"): explicit `--country cz` writes the envelope
  in the CZ task CRS (EPSG:5514 or `--target-crs`), while `auto`/`pl` —
  in the file CRS when the file is in EPSG:5514/3045 (since 2026-09-28, review
  max point 4), otherwise in EPSG:2180. The keys match only when both
  CRSs coincide (e.g. a file in EPSG:5514 without `--target-crs`);
  the limitation to be unified in stage 2 is unchanged;
- point 4: missing GUGiK data is `NoCoverageError(DownloadError)`;
  a cutout with partially missing data writes nodata and `extra.missing_sheets`;
  list/hierarchy mode has R5 tolerance since 2026-09-30 (ADR-027 erratum 3);
  a fully nodata CZ result gives a `Warning:` and code 0, likewise PL when
  the downloaded sheets contribute no valid pixels;
- clipping under `auto` prints `Info:` to stderr about the trimmed
  edges and the lost part outside the countries. Untouched PL edges
  keep their original values (end of widening on WGS84 round-trip).
  The file name and `request.bbox` carry the clipping, the original is in
  `extra.parent_request`; an explicit country does not clip. With `--geometry`
  without `--target-crs` the PL sheets are determined by the geometry;
- the declared `exportImage` ceiling of 15000 x 4100 px remains,
  the real limit of ~8 Mpx leads to client-side tiling with a budget of
  4 Mpx per query (ADR-024 erratum 2).

**Erratum 2 (2026-10-12, 0.8.0, no default values):** `--country`
is required with `--bbox`/`--geometry` (with `--sheet` the country still follows
from the sheet code). Without the defaults PL 1m/EVRF2007 and CZ 2m/Bpv, a PL+CZ task gives
`--resolution`/`--vertical-crs` as one value available in both countries
(`5m`, `EVRF2007`) or per country (`pl=1m,cz=2m`, `pl=EVRF2007,cz=Bpv`;
user decision 2026-10-12); validation of each country happens before the network.
The `Info:` about differing default vertical CRSs of the PL and CZ parts disappeared.
Point 5 (PL-only flags resolve `auto` to `pl`) applies to
`--product nmpt|orto` and plain `--vertical-crs KRON86`
and `--resolution 1m`; `--system` (required for the PL part) and per-country
values do not select the country, and a PL+CZ task with `--system` is no longer
an error on the CZ side.

---

## ADR-024: Reprojection of CZ content only locally (no `imageSR` != native)

**Data:** 2026-08-11
**Status:** Accepted — amended by ADR-034 (common chunk planning with an NW anchor); partly supersedes ADR-023 (the TM33 download mechanism in (c), Additional findings point 1)

**Context:** An analysis of the PL/CZ seam on the Olza (Cieszyn / Cesky Tesin) found that
`kartograf download --country cz --target-crs EPSG:2180` returns a raster whose
content lies **135 m off** the truth (dE 119 m, dN 64.5 m). The source was not any
Kartograf transformation: the reprojection was performed by the CUZK ArcGIS server
(`exportImage&imageSR=2180`) and it did so **without a datum transformation**
S-JTSK→ETRS89, that is, exactly like the ballpark operation we forbid.
Architectural irony: `transform/crs.py` forbids ballpark and this ban
works — the task envelope computed locally agrees with pyproj to 0.07 m —
but the pixel CONTENT itself went through the server path, which introduced the same error
back. No sidecar signalled this (`transform.horizontal =
"server:EPSG:2180"`, no accuracy field).

Control measurements (2026-08-11, `exportImage` vs. native 5514 data
reprojected locally by pyproj/GDAL, matched by RMS minimum):

| path | RMS minimum | shift | ballpark per pyproj |
|---|---|---|---|
| `imageSR=2180` (`--target-crs`) | 0.041 m at (−119.0; −64.5) | **135 m** | dE 118.8 / dN 64.4 |
| `imageSR=3045` (sheet code TM33) | 0.034 m at (0; +1.25) | **1.25 m** | dE 115.3 / dN 70.7 |
| native 5514 vs native 5514 | 0.045 m at (0; 0) | 0 (control) | — |

That is: for 3045 the server **applies** the datum (the 135 m shift does not occur),
but leaves a systematic **1.25 m to the south** — repeated on two
independent tiles (`758_5514`, `760_5514`), with native exports
agreeing with each other to 0.045 m. The source of this 1.25 m remains unknown (on the server side).

**Correction of the figure (2026-08-11, after live verification of the fix):** 1.25 m comes
from a measurement on two diagnosis tiles near Cieszyn (`758_5514`, `760_5514`).
An independent measurement on the E2E file from before the fix (`302_5550`, western Czechia,
kept from the E2E session) gave a content shift of **4.92 m** relative to the file after the
fix (dE −4.50 m, dN −2.00 m; RMS minimum 0.042 m in a ±30 m scan) —
almost 4x more than near Cieszyn. Conclusion: the error of the server-side reprojection
5514→3045 was **spatially variable** (a different realisation of the datum transformation
on the CUZK server in different parts of the country), not a global
constant — a stronger argument for Option C (local reprojection also for
the TM33 sheet-code path) than the figure of 1.25 m alone would suggest. Source:
`seam/verify/verify-report.md`, section 2 ("Dodatkowo: bezposredni pomiar
skutku fixu na tym samym kaflu") — report recovered 2026-08-18 from the session
scratchpad: copy in `docs/research/2026-08-11-adr024-verify-report.md`, original
with full data in the unversioned `seam/` in the repo root.

**Options:**
- A) Fix only `--target-crs`, leave the TM33 sheet-code path on the server.
  Rejected: 1.25 m is 0.6 of a DMR 5G pixel, on a 20° slope it gives 0.45 m of height
  error — of the same order as the whole difference budget measured at the seam.
  It would also leave two different rules for two paths of the same product.
- B) Keep server-side reprojection + a control test of points (server vs
  `PinnedTransform`) with a hard error on divergence. Rejected: it detects the
  problem but does not solve it — the user gets an error instead of data,
  and the cost of the task has already been incurred.
- C) **Local reprojection** — chosen.

**Decisions:**

(a) **The CUZK server receives raster tasks ONLY in the native CRS**
(`NATIVE_CRS = "EPSG:5514"`). This applies to both paths: `--target-crs` and the default
TM33 sheet-code path (result in 3045). The task envelope is the target converted to 5514
with the existing `bbox_to_crs()` (edge sampling) plus a margin
`_WARP_MARGIN_PX = 4` pixels — it covers the uncertainty of the envelope operation
(≤ 2 m) and the interpolator halo at the edge.

(b) **Local reprojection of content via `rasterio.warp.reproject`, with the operation
FORCED.** Without forcing, GDAL chooses the operation itself, outside the policy of
`transform/crs.py` (measured difference relative to the pinned one: 0.08 m on average,
1.9 m at most). Mechanism: `PinnedTransform.gdal_operation()` returns the same
operation as a PROJ pipeline for GDAL's `COORDINATE_OPERATION`.

(c) **The axis-order correction in `gdal_operation()` is mandatory.**
`PinnedTransform` is created with `always_xy=True` (E-N order), while GDAL passes the
operation coordinates in the **authoritative** order of both CRSs. Both real
CZ→PL targets are northing-first (`EPSG:2180`: x=north, `EPSG:3045`: N-E), so
without `step proj=axisswap order=2,1` the warp yields a raster that is **entirely nodata** —
a silent failure, easy to overlook in the pipeline. The correction is computed from
`CRS.axis_info`, not assumed. Alternatives checked: `to_wkt()` of the operation
(GDAL applies its own axis handling — also entirely nodata) and looking up the
authoritative version of the operation in `TransformerGroup(always_xy=False)`
(it cannot be matched by description: normalisation appends "+ axis order change").

(d) **Tiling and mosaicking stay on the native side — before the
warp.** The `exportImage` limits split the task in 5514, `mosaic_and_crop` assembles
the tiles into one raster and only that raster is reprojected. The reverse order
(warp per tile) would entrench seams: interpolation at a tile edge has no
neighbours from the adjacent tile.

(e) **`transform.horizontal` in the sidecar carries the local operation
with its accuracy** — `"pinned: <description> (<acc> m)"`, symmetrically to
`transform.vertical`. It replaces `"server:EPSG:<code>"` (without accuracy) and
also appears for the TM33 tile, which so far had `transform: null`.
The sidecar consumer now has a signal that reprojection took place at all and with what
accuracy; previously `"server:EPSG:2180"` could mean "a 135 m error".

(f) **Fail-fast before the transfer.** The lack of a safe horizontal operation
aborts before the user pays for the download — but **in two different
places**, because the target CRS is known at two different moments:
- `--target-crs` (bbox/geometry mode): the target is known at construction, so the
  operation is built **in the provider constructor**, like the vertical
  Bpv→EVRF2007; the CLI translates the exception into a message with a remedy when creating the
  provider;
- **sheet code TM33**: `target_crs` is `None` (the sheet code delivers the native product for
  its grid), and the target — EPSG:3045 — follows only from the sheet code, so the
  operation is created in `_export_raster()`, **before** the first HTTP task.
  The exception is caught only by `_run_cz()` in the CLI (a common `TransformError` handler
  for the whole CZ flow) and prints the same message with the remedy. This
  safeguard lies far from the place where the exception is raised, so it is pinned by the test
  `test_godlo_without_safe_horizontal_operation_exits_cleanly`.

Policy: `_HORIZONTAL_POLICY` (`min_accuracy_m=1.0`, no grids from the CDN) —
stricter than the envelope one (2 m), because it is the only operation that **moves
pixels**; the known operations from Krovak to 2180/3045 have 0.5 m.

(g) **Forcing the operation must be guarded by a separate test.** The content test
alone does NOT defend it: after removing `COORDINATE_OPERATION` the warp still works
and still lands ~1.0 m from the pyproj reference, i.e. **within** the
1 px (2 m) tolerance of the content test — measured. `TestGdalOperation` in turn checks
only the form of the string, never its use. Therefore
`test_warp_forces_the_pinned_operation` (both paths: bbox and sheet code)
asserts directly that the operation from `gdal_operation()` was passed to GDAL.

**Consequences:** Every CZ download in a CRS other than 5514 costs one
local resampling (bilinear) and a slightly larger transfer (the envelope of a
rectangle rotated relative to the grid + margin). The number of resamplings does NOT
change — the server reprojected anyway, only worse and without a trace in the
metadata. Nodata (`-9999`) does not enter interpolation (GDAL mask,
verified by a test), writing remains atomic (tmp + `os.replace`), and the result
lies on the same grid as before: **the size in pixels is identical**,
and the extent — as before — is snapped to a multiple of `pixel_size` counted from the
south-western corner of the task (`round()` on the pixel count, exactly
as in `CuzkClient.export_image`), so it may differ from the requested one by **≤ ½
pixel** at the edge. BREAKING for sidecar consumers: a different
`transform.horizontal` value, non-empty `transform` for TM33 tiles.
The SM5 path (DMR 4G from openzu) is untouched — the files arrive in 5514.
The rule "do not trust server-side reprojection" is binding also for future
DE/SK sources driven by a server-side CRS parameter.

**Live verification of the fix (2026-08-11, CUZK+GUGiK data,
`seam/verify/verify-report.md` — copy:
`docs/research/2026-08-11-adr024-verify-report.md`):** the content check (matching to the
native 5514 reference by the RMS-minimum method in a shift scan of ±2 m/0.25 m)
confirms the fix on both paths, with the minimum exactly at (0,0) on both:
sheet code TM33 (`302_5550`, EPSG:3045) — RMS(0,0) = **0.016 m**; bbox
`--target-crs EPSG:2180` — RMS(0,0) = **0.031 m**. Comparison with the PL NMT
in the overlap strip (Olza seam) gives a CZ−PL median of **−0.086 m** with a
correlation of **0.998** (consistent with the diagnosis measurement above: −0.083 m).
Negative controls (the same test on the pre-fix files) reproduce the
original errors (median +1.368 m, correlation 0.499) — so the method is
sensitive to an error of this class, and the zero result on the post-fix files is not
an artefact of insensitivity.

Two known costs of the local warp, observed during this verification —
candidates for optimisation in stage 2 (they do not block the fix):
(a) **loss of the server's sparse (sparse/tiled) TIFF layout** — a tile
93% nodata: 527 KB (server tiled TIFF, empty tiles omitted) → 4.0 MB
(local striped/dense write); for tiles without nodata there is practically no
difference. Direction of the fix: `tiled=True` + compression in the warp write profile;
(b) **bilinear interpolator halo of ~1 pixel at the validity edge**
(~0.5% of the product's pixels have references already in nodata; the values remain
correct, GDAL renormalises the weights). Direction of the fix: masking before
interpolation at the edge, if the consumer computes the exact coverage
area.

**Erratum 1 (2026-09-29, historical measurements before the fix; report
`docs/research/2026-09-29-live-e2e-i-audyt-docs/L4-pogranicze-cz-report.md`):**
- **Diagnosis of the historical 1.25/4.92 m difference:** the local
  `build_pinned_transform` chose the Slovak EPSG:4829 (0.5 m)
  instead of the Czech EPSG:1622 (1.0 m). The server correctly computed
  `imageSR=3045`, the local reference was wrong. The server-side
  `imageSR=2180` still confused the datum by ~135 m, which is why the rule of
  local reprojection remains (erratum 2 below).
- **Grid anchor:** the NW of the task, the resulting dimension rounded
  to whole pixels (at least 1), the E/S edge may
  deviate by up to 1/2 px or more for a bbox < 1/2 px.

**Erratum 2 (2026-09-30, repair wave, D1: CZ track unfrozen):**
1. **S-JTSK operation (K2).** Measurement of the difference EPSG:1622 − EPSG:4829
   in EPSG:3045: Cieszyn (+0.03; −1.16) m and tile `302_5550`
   (+4.52; +2.03) m explains the historical measurements of 1.25 m and 4.92 m.
   The server computed `imageSR=3045` correctly; the local
   reference with the Slovak operation was wrong. The ban on `imageSR` != 5514 still
   applies (for 2180 the server is off by ~135 m). The S-JTSK -> ETRS89/WGS 84
   datum step is now explicitly pinned to the Czech
   EPSG:1622/1623 in `DATUM_STEP_PINS`, before the operation attempt;
   the PROJ AOI alone is not enough (the Slovakia rectangle covers Moravia,
   and for western CZ the 5514 -> 2180 list is sometimes empty).
   The nominal accuracy in `KNOWN_PATHS` 5514 <-> 2180 and in the sidecar
   is 1.0 m (instead of 0.5 m). The self-agreement of 0.016/0.031 m
   and the seam median of −0.086 m did not prove the position; an independent
   L4 measurement against the GUGiK NMT near the Karkonosze gave (−2.26; +0.61) m for the old
   operation and (+0.38; −0.03) m for EPSG:1622.
   Old files with the sidecar `S-JTSK to ETRS89 (3)` are skipped
   without a rebuild; the CLI signals `Info:`, refresh them with `--force`.
2. **Tiling (K6).** The real server limit is ~8 Mpx,
   regardless of the dimension ceilings of 15000 x 4100 px.
   `MAX_EXPORT_PIXELS = 4_000_000` splits the task into near-square
   tiles with an NW anchor, and `merge` assembles them without resampling.
3. **Grid (N3).** The bbox is snapped to a whole number of pixels from the
   NW for a single query, tiling and warp: exactly
   2 m/5 m per pixel. The file name and `request.bbox` keep the extent
   from before the snap (E/S differ by up to 1/2 px).
4. **Empty result (N2).** A raster that is entirely nodata remains a result
   with code 0, but the CLI displays `Warning:`; the PL cutout likewise
   (`PlCutoutResult.all_nodata`).
5. The previous statement "the CZ track verified live — we do not touch it"
   loses force. Offline tests are green; a repeated L4 on the live service
   remains a gate before the release, not a proof carried out in this wave.

**Erratum 3 (2026-10-07, review D9 deduplication):** the constants from points (a)
and (f) now live in `transform/crs.py`, shared by the CZ track and the PL cutout (ADR-027):
`_WARP_MARGIN_PX` -> `WARP_MARGIN_PX` (still 4 px), `_HORIZONTAL_POLICY` ->
`CONTENT_POLICY` (`min_accuracy_m=1.0`, no grids from the CDN).

---

## ADR-025: Texture -> HSG mapping and the canonical USDA triangle (0.7.0 audit)

**Data:** 2026-08-22
**Status:** Accepted

**Context:** The pre-release audit of 0.7.0 (findings A4-4, A4-8, A4-9) showed
two independent problems in `kartograf/hydrology/hsg.py`. (1) The texture classification
thresholds were an approximation of the USDA triangle, not the USDA triangle: the oblique
boundaries of the standard (`silt + 1.5*clay`, `silt + 2*clay`, `sand > 52`, `sand > 45`,
`silt < 28`) were replaced with vertical/horizontal lines (e.g. `clay <= 15 and
sand >= 70` instead of `silt + 2*clay < 30`), even though the docstring declared
"standard USDA soil texture triangle". The rules additionally existed in **two
copies** — an `if/else` chain in the scalar version and a reversed order of masks
in the array version — so they also diverged from each other: normalisation in
float32 gave a different class at the `clay = 15%` boundary in the scalar than in the array
(16 points of the simplex, all changing HSG A/B), and the scalar chain had an
unreachable branch (`clay >= 40 and silt >= 40` after the earlier block
`clay >= 40`). (2) The `TEXTURE_TO_HSG` table deviates from the classic TR-55
table, and the module docstring gave a list of groups consistent with TR-55 — i.e. contradicting
its own code. The deviation was deliberate (comments "Can be A/B depending on
structure", "Can be C/D"), but was documented nowhere. HSG is the declared
input of the SCS-CN method for the Hydrologist, so both matters change or explain the
result for the consumer.

**Options:**
- A) Keep the simplified thresholds and fix only the docstring. Rejected: the difference
  is not cosmetic (see the numbers in "Consequences"), and it concerns sandy
  soils, which dominate in Poland.
- B) Fix the thresholds separately in each of the two implementations. Rejected: it was the
  duplication of rules that produced the scalar-vs-vector divergence; two copies would
  drift apart again.
- C) One list of rules, the vector version as the source of truth, the scalar as a
  wrapper — chosen.
- D) While at it, bring `TEXTURE_TO_HSG` in line with the TR-55 table
  (`sandy_loam` = A, `clay_loam`/`silty_clay_loam` = D). Rejected in 0.7.0:
  it is a product change (different CN for the consumer), not a bug fix — see
  decision (b).

**Decision:**

(a) **The texture thresholds are the canonical USDA rules** (Soil Survey Manual), kept
in a single list `_USDA_RULES` as `(name, predicate)` pairs; the predicate receives
a float64 array of shares in percent (after normalisation to a sum of 100) and
returns a mask. Order matters — the first matching rule wins:

1. `sand`: `silt + 1.5*clay < 15`
2. `loamy_sand`: `silt + 1.5*clay >= 15 and silt + 2*clay < 30`
3. `sandy_loam`: `(7 <= clay <= 20 and sand > 52 and silt + 2*clay >= 30) or
   (clay < 7 and silt < 50 and silt + 2*clay >= 30)`
4. `silt`: `silt >= 80 and clay < 12`
5. `silt_loam`: `(silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12)`
6. `loam`: `7 <= clay <= 27 and 28 <= silt < 50 and sand <= 52`
7. `sandy_clay_loam`: `20 <= clay < 35 and silt < 28 and sand > 45`
8. `clay_loam`: `27 <= clay < 40 and 20 < sand <= 45`
9. `silty_clay_loam`: `27 <= clay < 40 and sand <= 20`
10. `sandy_clay`: `clay >= 35 and sand > 45`
11. `silty_clay`: `clay >= 40 and silt >= 40`
12. `clay`: `clay >= 40 and sand <= 45 and silt < 40`

The array version (`classify_usda_texture_array`, the one used by
`calculate_hsg_by_bbox`) is the source of truth: it computes the masks and picks the first
matching one via `np.select`. The scalar version (`classify_usda_texture`) is a
wrapper — the same rules on a one-element array and `TEXTURE_NAMES[code]`.
The equivalence of the two functions is pinned by a test on the **whole** simplex at 1% steps
(5151 points), which at the same time proves that the rules are a partition: every point
gets a class 1-12, and `default` in `np.select` is never used.
Normalisation is computed **in float64** (`_normalize_pct`) — this removes the float32
divergence at the `clay = 15%` boundary (A4-8); `np.divide(..., where=)` also removes
`RuntimeWarning: invalid value encountered in divide` for pixels without
data. Points with a sum of 0 get an **explicit guard** -> `loam`: after normalisation
`(0, 0, 0)` satisfies rule 1 (`silt + 1.5*clay = 0 < 15`), so without the guard
it would be `sand`. This is not fiction: nodata pixels of the raster pipeline are
masked separately, but the public function is meant to return `loam` by decision, not
by an accidental rule hit.

(b) **`TEXTURE_TO_HSG` stays unchanged** and is deliberately milder than the
TR-55 table: `sandy_loam` = B (not A), `clay_loam` and `silty_clay_loam` = C
(not D). Rationale: these are transitional classes whose actual group depends on
soil structure and drainage conditions, not on the particle-size composition alone;
choosing the middle group is conservative for SCS-CN (it does not understate runoff
where the soil is worse than the composition alone suggests, and does not overstate it for
sandy-loamy soils). Changing this table changes the CN for the consumer
(Hydrolog), so it is a **product decision, not a fix** — outside the scope of
0.7.0. The module docstring no longer repeats the list of groups according to TR-55 (it contradicted the
table), it only refers here.

**Consequences:** The texture classification changes for part of the area of the
triangle, so HSG (and therefore the CN for the consumer) changes for the same
input data. The effect computed on the simplex grid at 1% steps (5151 points,
the **array** version, the one used by `calculate_hsg_by_bbox`), in the format
"was -> is":

| HSG change | points | share of simplex | texture change |
|---|---|---|---|
| A -> B | 136 | 2.64% | `loamy_sand` -> `sandy_loam` |
| C -> B | 85 | 1.65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
| D -> C | 5 | 0.10% | `sandy_clay` -> `clay_loam` |
| **total** | **226** | **4.39%** | (the texture class changes for 427 points = 8.29%) |

Every change is by **exactly one group**, in both directions: 136 points
become stricter (A -> B, more runoff), 90 become milder (C -> B, D -> C,
less runoff). The largest single item is sandy soils, until now
promoted from B to A by the vertical boundary `clay <= 15 and sand >= 70`
set in place of the oblique `silt + 2*clay < 30`; these are soils dominant in
Poland, so this item weighs more in practice than its 2.64% of the area of the
triangle.

Consumers (Hydrolog: HSG -> CN; Hydrograf: HSG rasters) will get a different result for these
pixels than in 0.6.x — consistent with the standard. The "Changed" entry in
`docs/CHANGELOG.md` carries the same table.

Note: the audit verification report (A4-4) gives smaller numbers — "3.4%,
136 B->A, 35 B->C, 5 C->D", recorded in the other direction (reference -> code) and for
the scalar version. The difference of 226 vs 176 points does not result from the direction of the notation:
that reference was a separate implementation of the rules and closed the class boundaries
differently. Two ties on the boundary are resolved here by the order of rules from point (a):
`clay = 20%` with `sand > 45` and `silt < 28` goes to `sandy_loam`, not to
`sandy_clay_loam` (28 points), and `clay = 27%` with `20 < sand <= 45` goes to
`loam`, not to `clay_loam` (22 points). Binding for consumers are the numbers from the
table above — computed by a test directly on the implementation from point (a).

---

## ADR-026: data/ layout per product — segments and templates in descriptors

**Date:** 2026-08-28
**Status:** Accepted — amended by ADR-030 (files in `<segment>/kampanie/`, standard path = hard link or copy; erratum 2), ADR-036 (`<segment>/versions/`; erratum 3) and ADR-044 (D7: naming convention of `data/` keys and directories); supersedes ADR-013 and the realisation of the layout from ADR-005, amends ADR-017 (closes the deferral)

**Context:** The flat `data/` layout did not encode the country or the CRS (`nmt_1m/`
next to `cz_dmr5g/`; PL-2000 shared a directory with PL-1992; the same sheet in KRON86
and EVRF2007 had ONE path — the second download: skip or overwrite).
The German federation (a dozen or so DEM sources, research 2026-08-10) would blow up the
root of the directory.

**Options** (resolutions D1-D8 in section 2 of the spec
`docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`;
below only the variants named there):
- A) Keep the flat layout of ADR-013 (`nmt_1m/`, `nmpt/`, `orto/`,
  `cz_dmr5g/`) — the state before 0.7.0 described in Context
- B) **Variant A from D1**: `data/<product>/<segment>/...`, `landcover/` unchanged
  — adopted
- Within B three narrowings were rejected: the horizontal layout only for NMT (the scope
  of the deferral from ADR-017) — D2 extends it to ALL PL products; a horizontal
  suffix also for CZ — D4 rejects as redundancy (the dataset name
  determines the CRS 1:1); resolution in every segment — D5
  leaves it only where it is an API parameter (NMT/NMPT)

**Decision (D1-D8 approved by the user 2026-08-28):**
`data/<product>/<segment>/...`, segment = `<country>_<crs>[_<variant>][_<vcrs>]`
lowercase. The PL horizontal CRS always explicit (`pl_1992`/`pl_2000`); the vertical one
always explicit (`kron86`/`evrf2007`/`bpv`; the only product without a vertical one
is orto); CZ without a horizontal suffix (the dataset name determines the CRS 1:1,
natively 5514); resolution only where it is an API parameter
(NMT/NMPT). `SourceDescriptor.storage_subdir` becomes a TEMPLATE
with placeholders `{uklad}`/`{vcrs}`; `resolve_subdir()` fills them via
`str.replace` (partial filling is legal, vcrs lowercased), FileStorage
resolves `{uklad}` per sheet code (rule `path_parts`: dots=2000, otherwise
1992) and validates zero braces (`ValidationError` with the name of the dimension). `--bbox`
cutouts go to `<segment>/bbox/<coords><ext>` (convention ed939a0, shared
PL/CZ). `landcover/` unchanged.

**Consequences:** BREAKING on disk (migration table: CHANGELOG 0.7.0
and ARCHITECTURE.md section 3). A new source (e.g. DE) = a new descriptor entry,
zero changes in the path code. A consumer reading `storage_subdir` directly
gets a template — the field was de facto internal; use `resolve_subdir()`.
FileStorage: new parameter `vertical_crs` (default "EVRF2007"); an unknown
`product` is still passed through (e.g. test `nmt_2000_1m`).

**Erratum 1 (2026-09-29, documentation audit; code changes from the review wave max
2026-09-28, notes 7, 8, 11):** `resolve_subdir` rejects an empty/blank dimension
(`ValidationError`); for LAZ tiles `{uklad}` is determined by `LazTile.uklad`
(cascade `uklad_xy` -> sheet code format -> "2000"), passed explicitly
in `FileStorage.get_raw_path(..., uklad=)` — without `uklad=` the sheet code
format rule applies; `FileStorage(resolution=/product=)` maps to the descriptor
KEY instead of a copy of the template (single source of truth). Live
2026-09-29 all segments were created according to the table (NMT 1 m/5 m,
EVRF2007/KRON86, PL-1992/PL-2000, NMPT, orto, LAZ, CZ dmr5g/dmr4g bpv/evrf2007,
`bbox/`); the origin and consistency of the GUGiK record is governed by ADR-028.

**Erratum 2 (2026-10-07, ADR-030):** in PL products with campaigns (NMT, NMPT,
orto) the path `<segment>/<hierarchy>/<sheet_code>.<ext>` is no longer a plain
file: the real files lie in `<segment>/kampanie/<date>_<id>/<hierarchy>/`,
and the standard path is a hard link (or a copy) to the newest local
campaign (ADR-030 (c), (d), erratum 4). The segments from this decision are unchanged.

**Erratum 3 (2026-10-12, ADR-036):** in 0.8.0 the PL NMT/NMPT/orto sheets lie
as versions in `<segment>/versions/<hierarchy>/<label>_<sha8>/`;
the standard path and `full_sheet/` are solely hard links to the
version (no copies). The `kampanie/` directory from 0.7.x is not used. Land
cover and HSG lie in the `data/` layout (plan 3/3, ADR-036 D29-D33): segments
`landcover/pl_bdot10k_*`, `landcover/eu_corine_<year>[_preview]`,
`soil/global_soilgrids_<property>_<depth>_<stat>`,
`hsg/global_soilgrids_<depth>_<stat>` (prefixes in `storage_subdir` of the
descriptors, content tokens lowercase), below them `teryt/<T>`,
`bbox/<coords>` or the sheet code hierarchy.

---

## ADR-027: --target-crs for PL — merged bbox cutout (mosaic + pinned warp)

**Date:** 2026-08-28
**Status:** Accepted — partly superseded by ADR-035 (cutout source in the CLI and `download_pl_cutout`; sheet API removed in 0.8.0, erratum 2 of ADR-035) and ADR-038 (the name `--target-crs`, enabling the cutout with a CRS flag); amended by ADR-030 (only the deprecated sheet path); supersedes part of ADR-023 (`--target-crs` only for CZ) and ADR-003 (bbox = WCS GeoTIFF)

**Context:** `--target-crs` existed only for CZ; the scenario "area of
interest in one country + pulling in data from the other" required a
PL warp on the consumer side — an asymmetry for no reason other than the history of
the implementation.

**Options** (D6 of the spec and its section 6; below only the variants named there):
- A) Leave `--target-crs` as a Czech-only flag — the state before 0.7.0
  described in Context
- B) **D6: "YES, it is in scope; semantics »one cutout«"** (spec section
  6) — adopted
- Within B three variants were rejected: sharing the warp with the CZ path (refactoring
  `providers/cuzk/dmr.py::_warp_to_grid` instead of a separate
  `transform/raster.py`) — see Consequences; merging also WITHOUT
  `--target-crs` (spec 6.1: "Without `--target-crs` the PL bbox behaviour is
  unchanged — a list of sheets natively"); `capability="bbox_raster"` in the sidecar
  per the letter of spec 6.1 item 5 — replaced by `sheet_files`, because the channel
  `bbox_raster` does not describe the way this data arrived

**Decision:** `--bbox`/`--geometry` + `--country pl` + `--target-crs`
(product nmt) returns ONE file `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`:
the sheets are downloaded normally into their segments (they act as a cache,
skip-existing as standard), then `mosaic_and_crop` (GTiff+CRS forced —
ASC does not carry them) + a local warp `warp_to_grid` with the FORCED operation
`PinnedTransform.gdal_operation()` (the machinery and pitfalls of ADR-024, including
axisswap for northing-first targets). `EPSG:2180` = a crop only
(`transform: null`; since 2026-09-28 a crop on the sheet grid — erratum 2
below). Fail-fast of the operation before the network; every failed sheet =
an error for the whole (code 1; changed 2026-09-28 for a sheet without GUGiK data —
erratum 1 (R5) below). The file name carries coordinates in the RESULT CRS.
The sidecar is written by the CLI (since 2026-09-28 the library, `write_pl_cutout_sidecar` —
erratum 2 below): `horizontal_crs=target`, `transform.horizontal=
"pinned: ..."`, `nodata=-9999`, `extra.parent_request`; channel
`sheet_files` (fact: data from OpenData sheets — the `bbox_raster` channel does
not exist for 5m, and for 1m it declares only KRON86). Exclusions of 0.7.0:
sheet code (native product 1:1), `--product nmpt|orto` (stage 2), `laz` (point
cloud), `--system 2000` (cross-zone mosaic — stage 2). On a cross-border
area `--country auto --target-crs` gives TWO cutouts (PL+CZ)
in the same CRS, a shared `extra.parent_request`.

The source envelope gets a margin: the target envelope is converted back to EPSG:2180 and grows
by `WARP_MARGIN_PX = 4` pixels (`download/cutout.py`; until 2026-09-28 the
CLI constant `_PL_WARP_MARGIN_PX`) — the interpolator halo, rotation of the target system.
This enlarged bbox ALSO drives sheet selection in BOTH modes: `--bbox`
selects sheets directly from it, whereas `--geometry` with a warp takes the UNION of the sheet codes
of the geometry (per object) and of the sheet codes of the enlarged bbox (R-01; for the EPSG:2180 target
there is no margin, so the sheets are determined by the geometry alone). Since 2026-09-28 selection
in bbox mode and in the R-01 union has an additional 1-pixel margin (erratum 2
below). A cutout from `--geometry` covers the WHOLE envelope
of the geometry — there is no masking to objects, and `nodata` means only
a missing downloaded sheet.

**Consequences:** PL/CZ symmetry in bbox mode; the outstanding backlog item
"Mosaicking NMT PL sheets" is closed. The PL warp is a separate function
`transform/raster.warp_to_grid` — a parametrised copy of the CZ pattern, deliberately
not shared (the ADR-024 tests patch `providers.cuzk.dmr.reproject`,
the CZ path was verified live right before the release). A failed cutout build does NOT
delete the previous result file (atomic write via `os.replace`, also
with `--force`); the CZ path was an exception here and on failure deleted the target file.
(Correction 2026-10-06, review D8/N7: the CZ path now calls the same
`transform/raster.warp_to_grid` — the copy `dmr._warp_to_grid` that deleted the
file has been removed, the result of the TM33 tile and of the cutout is bit-for-bit identical; a failed
CZ warp leaves the previous file as in PL.)
(Correction 2026-09-28: the earlier wording of this paragraph and of the sentences on sheet selection
in `--geometry` described the opposite of the code's behaviour — review max
2026-08-30, findings 5-6.)

**Erratum 1 (2026-09-28, R5, review max finding 2):** a sheet for which GUGiK
has no data (`NoCoverageError` — all sheet index layers responded
and none has the sheet) does not veto the cutout: nodata is put in its place,
the CLI prints `Warning:`, and the sidecar carries `extra.missing_sheets` (library
API: `PlCutoutResult.missing_sheets`). Every other download failure
(network, server, partial sheet index failure — also a 2xx response with an OGC
exception report) still aborts the cutout before
the build, with code 1 — a transient error must not leave a permanent hole in a file
that is then skipped as existing. Code 1 also ends an area
for which NO sheet has data (`ValidationError`, the cutout is not
created). Under `--country auto` a failure of the PL path with CZ success is still
code 0 and `Warning:` (ADR-023 items 4-5). Supersedes "every failed sheet = error
of the whole" (Decision above, spec 6.1 item 1). Reason: sheet selection is pure
sheet-system grid arithmetic, so the task area (with margin) reaches sheets outside
GUGiK coverage — at sea, in holes in the 1 m coverage, on the Czech side of a
border bbox; one such sheet used to veto the whole cutout, so
`--country auto --target-crs` on the border then gave only the CZ cutout.

**Erratum 2 (2026-09-28, R1, R3, facts 5-8 of the review max wave plan):**
- **Sheet grid (R1, review max finding 1).** The mosaic crop is extended
  OUTWARDS to the sheet pixel grid (the grid of most sources, < 1 px per
  side). For `EPSG:2180` the cutout is therefore the task area extended
  by < 1 px, with values 1:1 from the sheets — `transform: null` remains
  true, and the file name carries the coordinates of the TASK. With a warp the same
  snap is applied to the mosaic crop (source envelope), so the warp does not inherit
  a shift by a fraction of a pixel. Reason: GUGiK 5 m sheets have pixel corners
  at `5k + 2,5 m` (measured on 1977 sheets), and a crop anchored
  at the task corner shifted the content — for a bbox on multiples of 5 m
  by 0.5 px, mixing neighbouring columns. Sheet selection (bbox mode
  and the R-01 union) gets a 1-pixel margin so that the snapped crop does not reach
  a sheet outside the list. E2E on real 5 m sheets: 0 of 80,601 pixels
  differing from the sheet containing the pixel centre. Cutouts built
  earlier have the same file names — rebuild with `--force` (CHANGELOG).
- **Normalisation in VRT (facts 5-6).** Each sheet goes into `merge` through a
  VRT with explicit EPSG:2180 and a Float32 band, and the inputs are sorted: a sheet
  with a `.prj` added by Hydrograf merges with a sheet without it (previously
  `niezgodne CRS wejsc`), and a sheet with integers only
  (GDAL: Int32) does not truncate the whole mosaic to integers.
- **PL-2000 sheets = loud error (fact 7).** A sheet in PL-2000 coordinates
  (GUGiK sheet index fallback under a PL-1992 sheet code) ends the cutout build with
  `ValidationError` instead of a silent nodata hole; reprojection of such sheets
  is stage 2.
- **Selection at the upper edge (fact 8).** `find_sheets_for_bbox`
  with an EPSG:2180 bbox takes into account the maximum width on the central meridian
  19°E — previously it lost the strip at the upper edge of the bbox (6 sheets for a bbox
  20 km wide).
- **Library API (R3, review max finding 12).** The path lives in
  `kartograf.download.cutout`: `download_pl_cutout` or the steps
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`,
  exported in `kartograf`. The CLI is a wrapper (messages, exit codes),
  and the sidecar is assembled by the library (`write_pl_cutout_sidecar`). `run_pl_cutout`
  rejects an injected provider with a different vertical CRS or resolution than the
  cutout — the sheet segment carries the ACTUAL vertical CRS (ADR-026).
- **No changes (R2):** R-01 stays — for a single object and for a bbox "the whole
  envelope" and "ring" (the margin strip alone) give the same set of sheets,
  and a sparse multi-object geometry does not occur in practice. **Stage 2
  (R6):** merging PL+CZ into one continuous border surface
  (common grid, EVRF2007 on both sides) — after a live check of how
  GUGiK and CUZK clip data at the border.
- Size (finding 9): no hard limit — the intermediate mosaic file in a warp
  is compressed, disk space is checked before the network (lower
  estimate), and the CLI prints `Info:` for cutouts >= 1 GiB.

**Erratum 3 (2026-09-30, R5-list, D3/D8, D4/D5/D9, N2/N4/N9):**
- **R5 in the list and hierarchy.** `NoCoverageError` for a sheet
  does not veto all the others: regardless of `--workers`
  all are attempted, with `DownloadProgress.status="no_coverage"`
  and `Warning:`. At least one file without hard failures = code 0;
  all without data or any hard failure = code 1
  (full list of failures); a single sheet without data = code 1.
  The cutout still fills the gap with nodata and `extra.missing_sheets`.
- **Grid phases (D3/D8).** For EPSG:2180 `check_source_grid`
  detects sheets with a phase other than the dominant one and reports
  `GridMismatchError(ValidationError)` with `.off_grid` and a hint
  to change the target (contract of 1:1 values without resampling). For
  EPSG:5514/3045 W1: `warp_to_grid(list[Path])` warps each
  sheet ONCE from its own grid to the result, without a tmp mosaic;
  `extra.off_grid_sheets` carries the list of deviations. A common phase
  keeps the mosaic + warp path. On skip, `missing_sheets` and `off_grid_sheets`
  are read from the sidecar.
- **Provenance and cache.** The cutout's `extra.sheet_sources` maps
  the sheet codes of downloaded sheets to the `extra.source` chosen according to ADR-028.
  `download_pl_cutout(cache=)` lets the library use the record
  cache (the CLI plugs it in, `--force` skips it).
  `PlCutoutResult.all_nodata` signals a completely empty result
  despite downloaded sheets (`Warning:`, code 0). The disk space check
  counts the missing sheets once and reuses the result.

Description of the current flow: `docs/ARCHITECTURE.md` section 4.3.

---

## ADR-028: Choosing the GUGiK sheet index record and `extra.source`

**Data:** 2026-09-30
**Status:** Accepted — amended by ADR-030 (campaign strategies `newest`/`all`, `--min-year`; the `newest` selection rule unchanged; sheet index failure: erratum 2) and ADR-054 (plain mode takes the newest full flight); partly superseded by ADR-031 (names of the `extra.source` keys); supersedes part of ADR-020 (hard-coded layers and fallback), amends ADR-019 (`record_cache`)

**Context:** GetFeatureInfo returns many records: different campaigns, RGB/CIR,
resolutions 0.5 m and 1 m, PL-1992/2000 sheets and child sheet codes.
Choosing the first URL containing a sheet code fragment swapped the product
or the scope. A failure of a newer layer could silently redirect to an older one;
URLs alone in the cache would perpetuate an unclear decision without provenance.

**Options:**
- A) First URL or silent fallback to a similar sheet code/CRS.
- B) Strict record filter and explicit distinction of missing coverage from failure.
- C) Merging incompatible records at the sheet level.

**Decision:** B (D4/D5/D9 and P2/P3/P7). `providers/pl/skorowidz.py`
parses the `var ... = [];` template, the full set of fields and HTTPS addresses from the
GetFeatureInfo response; an OGC report or a missing template is a `DownloadError`, not
missing coverage. Compatibility requires the sheet code as a whole token, horizontal
PL-1992/2000 (for PL-2000 also the zone), the requested resolution
exactly 1 m/5 m and RGB colour for orthophoto by default
(`GugikOrtoProvider(color="CIR")` on explicit request). A record without a CRS
or resolution is rejected with a warning. Layers come
from GetCapabilities and are queried from the newest; every attempted
layer must respond, the first matching vintage ends the search
(on a violation of the layer/year partition: warning). Among compatible
records of that layer the maximum `(aktualnosc, dt_pzgik, url)` wins,
without preferring `calyArkuszWypelnionyTrescia=TAK`.
After all valid empty/non-matching responses
the result is `NoCoverageError` with a hint (e.g. PL-2000 1:10000
with only children -> `--scale 1:2000`), and a failure of any
queried layer after 3 attempts = `DownloadError`. The cache stores
`{"source": {...}}` or `{"no_coverage": true}` for a TTL of 7 days;
`--force` bypasses the cache to check the current state of the sheet index.

**Consequences:** A sheet gets `extra.source` (URL, layer,
freshness, resolution and other fields), a PL cutout
`extra.sheet_sources` (a map of sheet codes to source). The `kartograf-meta/1` schema
stays without a version change (additive fields), but consumers will no longer
silently get 0.5 m instead of 1 m, a PL-1992 file instead of PL-2000,
or an older campaign after a sheet index failure: they will receive `NoCoverageError`
or `DownloadError`. `MetadataCache.get_url/set_url` were replaced by
`get_record/set_record`, the old `url_cache` table is removed on
initialisation (ADR-019). The PL-2000 sheet sidecar declares the actual
`horizontal_crs` of the zone EPSG:2176-2179.

**Erratum 1 (2026-10-06, review-2 N4, E14, E17, D16):**
- "after 3 attempts" (here and in erratum 3 of ADR-020 of 2026-09-30 "Transport requests
  have 3 attempts"): since ca4d004 only a network error, HTTP 429 and 5xx are retried
  (up to 3 attempts, `Retry-After` lengthens the pause); other 4xx (403/404) end
  at the first attempt with `DownloadError.status_code`
  (`transport/http.py::is_retryable`).
- "`--force` bypasses the cache": since E14 `--force` opens
  `MetadataCache(refresh=True)` — reading is a miss, but the freshly chosen
  record (or missing coverage) is WRITTEN; since D16 the same in the CZ path
  for the SM5 sheet index.
- "The PL-2000 sheet sidecar declares the actual `horizontal_crs` of the zone":
  the sidecar describes the CRS of the FILE — GUGiK publishes some PL-2000
  zone 7 sheets in EPSG:2180 coordinates; then `horizontal_crs` =
  EPSG:2180, the record's declaration stays in `extra.source.uklad`, and the CLI
  prints `Warning:` (E17).

**Erratum 2 (2026-10-07, ADR-030 erratum 5):** the sentence from Consequences
"consumers will no longer get [...] an older campaign after a sheet index failure" has
one explicit exception: `newest` on a sheet index TRANSPORT error (network,
429, 5xx) and an existing local campaign of the sheet uses that local
campaign — with `Warning:` and the `unverified` field in the result, never silently.
A failure other than transport, `all`, `--min-year`, `--force` or no
local campaign = `DownloadError` as before.

---

## ADR-029: Choosing LAZ tiles by area coverage and downloading LAZ in the library

**Data:** 2026-10-07
**Status:** Accepted — amended by ADR-030 (`--campaigns all`/`--min-year` for LAZ; erratum 1) and ADR-032 (year range and reference coverage; erratum 2); supersedes part of ADR-021 (newest-per-tile rule), amends ADR-023 ((f).1 covers LAZ)

**Context:** ADR-021 deduplicated tiles by sheet code (newest `akt_rok`
per sheet code). PL-1992 and PL-2000 tiles of the same place have different sheet codes,
so the E2E of 2026-10-06 (C13, area w2 in Warsaw, 50 x 50 m) got two
tiles: 2022/PL-2000:S7 (250 MB) and 2025/PL-1992 (50 MB) — a duplicated area,
and the "newest vintage" was not guaranteed per area. Moreover the thread pool loop,
the tile sidecar and tile failures lived only in the CLI (review-1 D17), and
the LAZ sidecar did not carry `extra.parent_request` (review-2 N15; the erratum of ADR-023
item 8 about this exception was removed along with this fix).

**Options:**
- A) Dedup by sheet code (state) — does not join CRSs or campaigns with a different cut.
- B) Dedup by the WFS envelope — the envelope of a rotated frame (EPSG:2180)
  protrudes beyond it by ~15 m at the corners: false "coverage".
- C) Greedy selection by tile frame (`msGeometry`) from the newest year,
  comparison in EPSG:2180 with an edge tolerance.
- D) Download everything and leave the choice to the user (`--year`).

**Decision:** C. `GugikLazProvider.select_tiles` (and `discover_tiles` =
`select_tiles(...).tiles`) queries the vintages as before, discards tiles
below `--min-density`, and then `select_newest_cover` goes through the tiles
starting from the newest `akt_rok` (within a year: newer `akt_data`, higher density,
sheet code, URL). A tile is skipped if its intersection with the task area
is covered by the union of the tiles already selected, each enlarged by
`COVERAGE_TOLERANCE_M` = 1 m; a tile contributing an uncovered piece stays.
With `--year` the rule works within that year. The tile frame is the
`msGeometry` polygon (N,E axes for URN, like the envelope), normalised to a
convex quadrilateral (`core/coverage.py`: vertices collinear to within
10 cm are removed — the parallel sides of PL-1992 sheets are gaps of ~3 cm).
Caution rules (doubt = download): only a tile with
`czy_ark_wypelniony` != `NIE` covers (the frame of an incomplete sheet is not the extent of
the data — Wroclaw 2025 has two NIE deliveries of the same sheet), and only
by its frame or by the same sheet code (never the envelope); a tile without
geometry stays; a tile whose frame does not intersect the area (only the
envelope does) is skipped as "outside". Skipped tiles are returned by
`LazTileSelection.superseded` (tile + covering tiles); the CLI prints
them as `Info:` on stderr (also with `-q`).

The 1 m tolerance: frames of tiles of different CRSs and campaigns do not lie edge
to edge, and a strip narrower than 1 m is 2-4 rows of points at 4-20 p/m2 with
a position error of 0.10-0.30 m (`blad_sr_syt`) — it does not justify downloading
a 50-250 MB tile; at the same time it is 2-3 orders of magnitude smaller than the
tile (~500-1100 m), so it will not hide a real gap in a newer campaign.

Downloading moves to the library: `kartograf.download.laz`
(`download_laz_area`, `run_laz_download`, `write_laz_sidecar`;
`LazDownloadResult` with `downloaded`/`skipped`/`failed`/`superseded`), modelled on
`download/cutout.py`. A tile failure is not an exception, it goes to
`failed`; the CLI translates it into `Error:` with the full list and exit code 1. The tile
sidecar carries `extra.parent_request` in `--bbox`/`--geometry` mode
(ADR-023 (f).1 now covers LAZ; `countries` = `["PL"]`).

**Consequences:** The w2 area downloads one tile (2025/PL-1992) instead of
two; older vintages only explicitly (`--year`). The result depends on the area:
an area extending beyond the newer campaign will also get the older tile
(whole — LAZ is not clipped). `LazTile` has new fields `footprint`,
`date`, `full_sheet` (additive, with default values). Incomplete
tiles (`NIE`) do not displace older complete ones — the area may then
get both. The library (Hydrograf) downloads LAZ without duplicating the CLI.

**Erratum 1 (2026-10-07, ADR-030 (j)):** "older vintages only explicitly
(`--year`)" — also via `--campaigns all`: all tiles whose frame
intersects the area, without coverage deduplication (a tile intersected only by the
envelope is still skipped). `--min-year` is the lower bound of `akt_rok`
(with `newest` the coverage-based choice works on the vintages from the bound) and is mutually exclusive
with `--year`.

**Erratum 2 (2026-10-10, ADR-032):** `--year Y` is the range `[Y, Y]`,
`--min-year`/`--max-year` are closed bounds of `akt_rok`; `--year` is not
combined with either bound. With a year flag WFS queries ALL vintages of the
service, after the `--min-density` and vertical filter. Reference selection R =
`select_newest_cover` without year bounds (the result the user would get without the
flag). Each tile of R outside the range must have its intersection
with the area covered by tiles from the range according to the same frame rule and 1 m
tolerance. Different sheet codes PL-1992/PL-2000 mean that the conflict is determined by
coverage, not by sheet code equality. Lack of coverage of part of R = `YearRangeError`
with the reference sheet code, its year/CRS and the years of the tiles intersecting the
uncovered fragment; zero downloads. W2 with `--year 2022` is covered jointly by two
PL-2000 tiles (neither alone), `--year 2023` the same sheet code; Wroclaw
(`6.150.13.16.4`) with `--year 2025` is a conflict (the year 2025 has only
`NIE` deliveries there, the 2024 PL-1992 reference stays uncovered). A year in which
the uncovered fragment is intersected only by `NIE` deliveries gets in the message
the note `(tylko arkusze niepelne)` (user decision 2026-10-10).
`discover_tiles` accepts `min_year` and `max_year` like `select_tiles`
(user decision 2026-10-10, symmetry). A fragment
without tiles in any year stays without a warning as before.
Within the range itself `newest` keeps the ADR-029 selection (also for an explicit
`--campaigns newest`); `all` keeps the absence of coverage deduplication.
A vintage absent from GetCapabilities still gives `DownloadError` before
GetFeature, not a conflict with a specific tile. The tile sidecar gets
`request.max_year`/`min_year` and `year` (when the bounds are equal) as well as
`extra.acquisition_date`/`full_sheet`, when known.

---

## ADR-030: Campaign strategies (`newest`/`all`), `--min-year` and the `kampanie/` layout with a hard link

**Date:** 2026-10-07 (user decisions)
**Status:** Accepted — partly superseded by ADR-031 (key names of `extra.campaign`), ADR-032 (range, scan and conflict; erratum 7) and ADR-036 (`kampanie/` layout, automatic `newest`, copy instead of hard link; erratum 9); amended by ADR-033 (second link `full_sheet/`; erratum 8); amends ADR-026 (`kampanie/`), ADR-027 (cutout only `newest`), ADR-028 (strategies; the `newest` selection rule unchanged), ADR-029 (LAZ: `all`, `--min-year`) and ADR-019 (`campaigns_cache`); erratum 10: open review nitpicks closed (M-8: link sidecar removed after a write failure)

**Context:** A GUGiK sheet often has several campaigns (different acquisition dates,
orders, sources: laser scanning or aerial photographs). Measurement of 2026-10-07
(`docs/research/2026-10-06-e2e-brzegowe-i-review/pokrycie-kampanii.md`):
the newest campaign is sometimes incomplete (N-34-139-C-a-3-1: 0.9 % of the data of the older
complete campaign; orthophoto M-34-90-C-b-4-4: 3.2 %), and the flag
`calyArkuszWypelnionyTrescia` does not measure the scale of the gap. Coverage cannot be
determined before downloading: the server `opendata.geoportal.gov.pl` does not support
HTTP Range, and the WFS geometry of the sheet indexes (`.../WFS/Skorowidze`, `msGeometry`)
is the sheet frame, not the extent of the data (erratum in
`docs/research/2026-10-07-pobieraczek.md`). Today Kartograf downloads only the
newest campaign (ADR-028), the file in the standard path does not carry the
campaign identity, and a rerun skips the existing file without
checking whether a newer campaign has appeared. The user wants to be able to download
all campaigns and combine them themselves (QGIS; a universal campaign-merging
tool planned in 0.7.1).

**Options (strategies):**
- `newest` — the newest campaign (state, ADR-028).
- `all` — all campaigns of the sheet meeting the hard filter of ADR-028.
- `coverage` — the newest with coverage >= a threshold. REJECTED: coverage known
  only after downloading (or an interrupted download) — unnecessary load on
  GUGiK infrastructure.
- `mosaic` — the newest + older only in gaps, one composite file.
  REJECTED: combining campaigns is up to the user/the 0.7.1 tool.
- Specifying a particular campaign (`--campaign <id>`). REJECTED: requires
  knowing GUGiK identifiers, nobody will use it.

**Options (file layout of multiple campaigns):** A) a suffix in the file name in
the sheet directory; B) campaign first, then the sheet hierarchy
(`kampanie/<campaign>/<hierarchy>/<sheet_code>.<ext>`); C) sheet first, then
campaign; D) always the original GUGiK file name. B chosen — one GUGiK delivery =
one directory, which in QGIS gives a coherent campaign mosaic (VRT),
while file names and the sheet code hierarchy stay unchanged.

**Decisions:**

(a) **Strategies.** CLI `--campaigns {newest,all}` (default `newest`);
library: parameter `campaigns="newest"|"all"` in `DownloadManager` (and in
the paths that use it). Applies to PL products with campaigns in the
sheet index: NMT (1 m, 5 m), NMPT, orthophoto — in all sheet modes:
sheet code, list `--bbox`/`--geometry`, sheet code hierarchy. The `newest` selection rule
= ADR-028 unchanged (newest `aktualnosc`, then `dt_pzgik`,
URL; no preference for a full sheet). `all` = every record that
passes the hard filter of ADR-028 (sheet code as a token, CRS, resolution,
vertical CRS, orthophoto colour variant), from every layer of the service.

(b) **`newest` checks whether there is a newer campaign.** Every run
resolves the current newest record (from `MetadataCache.record_cache`, TTL 7
days; after expiry or with `--force` — a query to the sheet index). If the file
of that campaign is local — only ensuring the link (d), no download.
If not — download into `kampanie/` and repointing the link. An existing
file in the standard path is no longer a reason to skip.

(c) **Campaign identity and layout.** Campaign directory `<date>_<id>`:
`<date>` = `aktualnosc` (the data ACQUISITION date, YYYY-MM-DD), `<id>` =
order identifier — the first numeric segment of the file name in the URL
(`.../NMT/83233/83233_1744736_<sheet_code>.asc` -> `83233`), in the absence of such
a segment `u<8 characters of sha1(URL)>`. Campaign file:
`<segment>/kampanie/<date>_<id>/<sheet code hierarchy>/<sheet_code>.<ext>` + sidecar
alongside, e.g. `nmt/pl_1992_1m_evrf2007/kampanie/2025-04-27_83233/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc`.
Segment (ADR-026) unchanged, also the orthophoto variant
(`orto/pl_1992_cir/kampanie/...`). Real files lie ONLY in
`kampanie/` — applies to both strategies.

(d) **Standard path = link to the newest campaign available locally.**
`<segment>/<hierarchy>/<sheet_code>.<ext>` (the path from ADR-026, the same for
consumers, among others Hydrograf) and its `.meta.json` sidecar point to the file
and sidecar of the newest campaign available locally — also an incomplete one (in line
with `newest`). Every download of a campaign newer than the link target (through
`newest` or `all`) repoints the link atomically (temporary link +
`os.replace`). The method is chosen automatically, in order:
1) RELATIVE symbolic link (Linux/macOS; Windows with developer
mode) — it shows which campaign it points to, `data/` can be moved;
2) hard link (ordinary Windows on NTFS, shares without symlinks; the same
volume); 3) copy + `Warning:` (FAT32/exFAT, a different volume). The method used:
`extra.link` in the sidecar (`symlink|hardlink|copy`). Verified
2026-10-07: symlink, hardlink and atomic replacement work on a local disk
and on a CIFS SMB 3.1.1 network share. A dangling link (deleted
campaign) = a missing file: the existence check checks the TARGET, not the link.

(e) **No migration.** Files from before this change (ordinary files in the standard path)
are treated as unknown: `newest` downloads the newest campaign
into `kampanie/` and REPLACES the old file (and its sidecar) with a link.
Kartograf does not move old files into `kampanie/` on the basis of sidecars
— risk of missing/incomplete metadata; downloading again is cheap.

(f) **`--min-year YYYY`** (both strategies): lower bound of the year from
`aktualnosc` (acquisition date, not `dt_pzgik` — the difference reaches a year:
2025-10-21 accepted into PZGiK 2026-07-10). `newest --min-year`: when the newest
campaign is older than the bound — no coverage (`NoCoverageError` with
a hint: the date of the newest campaign; in list mode status
`no_coverage`/`Warning:` like R5). `all --min-year`: campaigns from that year
inclusive. Verification 2026-10-07: 1381 sheet index records (NMT 1 m/5 m,
NMPT, orthophoto; KRON86/EVRF2007) — `aktualnosc` always a full date, `aktualnoscRok`
always consistent.

(g) **Resilience to layer name changes.** Layers come from GetCapabilities
(`LAYER_PATTERN`, no hard-coded lists — ADR-028/S4). For `--min-year`: the year
from the layer name serves ONLY to skip the query — a layer
is skipped only when the name gives an unambiguous UPPER year (`2019`,
`2017iStarsze`) smaller than the bound. A layer without a year (`Starsze`) or
with a name not matching the pattern is always queried. The result is decided
solely by the record's `aktualnosc`. A layer whose name does not match
`LAYER_PATTERN` gives a warning in the log (today it is silently skipped —
a change of the naming scheme must not lose data without a trace); whether it should be
queried instead of skipped — to be decided by the plan after the review of
`_fetch_wms_layers`.

(h) **Cache.** `record_cache` (newest record) with unchanged semantics;
`all` needs a list of sheet records — a new table (e.g.
`campaigns_cache`, key like `record_cache`, TTL 7 days, `--force` = refresh
like E14). The `--min-year` bound does NOT enter the key: the filter works on the
list/record after reading.

(i) **Sidecar.** Every campaign file: `extra.campaign` = {`id`, `date`
(`aktualnosc`), `zgloszenie` (`numerZgloszeniaPracy`), `source`
(`zrDanych`/`zrodloDanych`), `full_sheet`, `dt_pzgik`} alongside the existing
`extra.source`; `request` records `campaigns` and `min_year`; `extra.link`
in the sidecar of the standard path.

(j) **Out of scope / behaviour of other tracks.** PL cutout (`--target-crs`,
ADR-027) with `--campaigns all` = `ValidationError` before the network (merging
campaigns — a 0.7.1 tool); a cutout with `newest` takes sheets through
links as before. CZ (CUZK) has no campaigns: an explicit `--country cz`
with `all`/`--min-year` = `ValidationError`; under `--country auto` the options
apply only to the PL part (`Info:`). LAZ: `newest` = ADR-029 (selection by
area coverage); `all` = switching off the ADR-029 deduplication (all
vintages meeting the filters), `--min-year` = lower bound of `akt_rok`,
mutually exclusive with `--year`; the LAZ layout unchanged (file name =
original GUGiK name, unique per campaign), no links.

**Consequences:**
- The consumer (Hydrograf) sees the same paths; GDAL/rasterio follow the
  link. Tools that copy `data/` may copy the link instead of the
  data — describe in the README.
- The `data/` layout changes internally (ADR-026 + `kampanie/`): `FileStorage`
  must distinguish the standard path from the campaign path; `list_files`/`delete`
  must handle links (deleting the standard path = removing the link, not the
  campaign).
- `newest` queries the sheet index after the record cache expires
  (7 days) for each sheet — a conscious cost of data freshness.
- The first run after deployment downloads the sheets from the cache again
  (no migration, (e)).
- Tests: campaign identity from real URLs (NMT/NMPT/orthophoto), link
  methods with a fallback (simulating missing permissions), atomic replacement,
  dangling link, `--min-year` on raw bodies (single-year layers,
  aggregate layers, `Starsze`, unknown name), `all` + skip per campaign.


**Erratum 1 (2026-10-07, plan `docs/research/2026-10-07-plan-adr030.md`,
verification `docs/research/2026-10-07-weryfikacja-planu-adr030.md`;
accepted by the user):**
- (g) **[Q1]** A GetCapabilities layer whose name does not match
  `LAYER_PATTERN` is NOT queried (instead of "always queried"):
  real GetCapabilities responses contain `default`, `WMS` and (orthophoto)
  `SkorowidzeOrtofotomapyZasiegi*`, and a response outside the sheet index template
  fails the sheet (`DownloadError`). A name from the product family (e.g.
  `Skorowidz...NMT...`) that does not match the pattern produces a `logger.warning`
  — a change in the naming scheme does not go unnoticed. The `Starsze` layer (without a year)
  matches the pattern and is always queried.
- (g) **[Q5]** Skipping layers by the year in the name works ONLY in `all`.
  `newest --min-year` queries layers as before (from the newest), so that
  `record_cache` does not depend on the boundary and the missing-data message gives the date
  of the newest campaign.
- (d) **[Q7]** The sidecar of the standard path is a REGULAR
  file (a copy of the campaign sidecar + `extra.link`,
  `extra.link_target`), written atomically — not a link:
  writing through a symlink would overwrite the campaign sidecar
  (`write_sidecar`, `_note_reuse`). Only the data file is a link.
- (d) The link is NEVER moved to a campaign older than the
  current target: it is moved only to a key `(aktualnosc, dt_pzgik, url)`
  strictly greater than the target key (equal or smaller = no change). The target
  key comes from the campaign sidecar, and when that is unreadable — from the name of the
  directory `<date>_<id>` as `(data, "", "")`, a lower bound
  (`download/links.py::campaign_key_of`). [Corrected 2026-10-08:
  the earlier wording spoke of comparing the key `<date>_<id>`.]
- (j) **[Q2]** A PL cutout (`--target-crs`) with `--min-year` = `ValidationError`
  before the network, code 1 — the same as with `--campaigns all`.
- (j) **[Q9]** A CZ sheet code (unambiguously Czech) under `--country auto`
  with `--campaigns all`/`--min-year` = `Error:`, code 1 (consistent with
  `--product nmpt/orto` for CZ). `Info:` (the options apply only to the PL part)
  only for a `--bbox`/`--geometry` area.
- (c) **[Q3]** A campaign with a file format other than the product default (in practice
  `.xyz`, record 72675) is saved with the extension from the URL and does NOT get
  a link. When such a campaign is the newest under `newest`, the sheet ends
  in failure (`DownloadError`), and the file stays in `kampanie/`. (Today `.xyz` is
  saved as `.asc` — an error, fixed by this change.)
- (i) **[Q8]** `request.min_year` only when given; LAZ: `request.campaigns`
  only with `all`.
- **[Q4]** A PL cutout from `newest` is skipped when the result file exists
  (without checking for newer sheet campaigns) — refresh with `--force`.
- **[Q10]** A partial failure of `all` on a sheet (e.g. one campaign that cannot be
  downloaded) = hard failure of the sheet (code 1); downloaded campaigns stay,
  the link points to the newest downloaded one.
- **[Q6]** `all` for orthophoto may mean ~10 campaigns and GB of data per sheet —
  no limit, described in the documentation and `logger.info` with the number of campaigns.

**Erratum 2 (2026-10-07, user decisions on plan questions N-1..N-3):**
- **[N-1]** The sidecar of a file in `kampanie/` is MANDATORY: a failed write of the
  campaign sidecar = download failure of that campaign (data file removed,
  `DownloadError`). The sidecar carries the campaign identity. The other sidecars
  (among others the cutout one) remain best-effort. A missing campaign sidecar is henceforth
  solely the result of user intervention; in that case the campaign key comes from the name of the
  directory `<date>_<id>`. No scanning of `kampanie/` in 0.7.0 (risk R21).
- **[N-2] Supersedes point [Q3] of erratum 1.** The file format comes from the
  `format` field of the sheet index record, not from the URL extension. Verification
  2026-10-07: all 1217 NMT/NMPT records from the round have
  `format: "ARC/INFO ASCII GRID"` — including record 72675
  (`72675_858113_N-33-69-A-d-3-2.xyz`), whose file is an AAIGrid
  (header `ncols/nrows/xllcorner`, GDAL `AAIGrid`, 1 m, 92.5% valid
  pixels); the `.xyz` extension is a naming error on the GUGiK side. Orthophoto records
  have no `format` field (always `.tif`). Rule: the file is saved
  with the canonical extension of the format (`.asc` for ARC/INFO ASCII GRID),
  treated like any other campaign (link as usual), and after download the
  format is verified by content (AAIGrid header / TIFF signature).
  A record with an unsupported format (a `format` field other than the known ones) or
  a file whose content does not match the format = campaign failure
  (`DownloadError` with the format name), not a silent save under `.asc`.
- **[N-3]** An entirely Czech area under `--country auto` with
  `--campaigns all`/`--min-year` = `Error:`, code 1 (campaign options apply
  only to PL; CUZK does not publish campaigns in the services used by
  Kartograf — reconnaissance of the DMR 5G raster catalogue in progress). `Info:` only
  for an area with a PL part.

**Erratum 3 (2026-10-07, user decision after the CUZK reconnaissance,
`docs/research/2026-10-07-cuzk-kampanie.md`):** the campaign mechanism is
EXCLUSIVELY for PL (GUGiK) — no common, country-independent campaign
abstraction. CUZK does not provide archival data (ImageServer = one
current raster; `Metadata/MapServer/20` gives only the year of the last
update per area), so Czechia always downloads the newest data;
campaign options for CZ = `Error:` (I-3, N-3). Outside the scope of 0.7.0 (next
release): a mechanism for updating CZ data as a CLI flag — forcing a
completely new download of the whole set or a partial download with
a comparison of changes in metadata (e.g. `ROK` from Metadata/20, ATOM `<updated>`,
`Last-Modified` of openzu files).

**Erratum 4 (2026-10-07, user decision after live verification T12,
`docs/research/2026-10-07-adr030-live/raport.md`):** the standard path
is EXCLUSIVELY a hard link: methods `hardlink` -> `copy` (+ `Warning:`);
symlink REMOVED (supersedes the order symlink -> hardlink -> copy from point (d)).
Reasons: (1) a symlink created from Linux on an SMB share (`reparse=nfs` or
`mfsymlinks`) is unreadable for Windows clients, who will use
the data; (2) the tested SMB share accepted a symlink target of at most 77 characters, so
some sheets got a symlink (PL-2000, target 65-72 characters) and some a hardlink
(PL-1992, orthophoto, 79-81) — behaviour dependent on the length of the sheet code; (3) a hardlink
works without privileges on ext4/btrfs/APFS/NTFS and over SMB (the server shows
a regular file); the campaign always lies in the same segment as the standard
path (the same file system). The copy remains for systems without
hardlinks (exFAT/FAT, sshfs/FUSE). `extra.link` = `hardlink|copy`,
`extra.link_target` unchanged (a path relative to the campaign file — the only
source of the target, because a hardlink carries no pointer). An existing symlink (development
data from before the release) = unknown path: `newest` replaces it with
a hardlink, without compatibility code. Copying `data/`: `rsync -aH` / `cp -a`
(without preserving hardlinks a duplicate arises). The erratum also covers
Consequences: the risk "tools that copy may copy the link instead of the data"
becomes a duplicate risk (copying without `rsync -aH`/`cp -a`), and
the "dangling link" from point (d) does not exist — a removed campaign directory (or
a missing standard sidecar) means no target in `extra.link_target`, so the
file is treated as missing and downloaded anew; `FileStorage.delete`
of the standard path removes only that name (the file in `kampanie/` stays).

**Erratum 5 (2026-10-07, final review T11 (I-1) and FB fixes; user
decision, recorded 2026-10-08):** a sheet index outage under `newest` does not
fail a sheet that has a local campaign (amends (b)). Conditions:
strategy `newest`, without `--min-year`, without `--force` (library:
`skip_existing`), `resolve_campaigns` ends with a TRANSPORT error (network
or timeout, HTTP 429, 5xx — `_is_transport_failure` in
`download/manager.py`, policy `transport/http.py`; NOT `NoCoverageError`,
not other 4xx, not an OGC report or a wrong response template), and the standard path
points to an existing local campaign (`linked_campaign(std)`).
Then the sheet is skipped using the local campaign, the link stays unchanged,
and the result carries the error: `SheetFetch.unverified`,
`DownloadResult.unverified` (`{godlo: blad}`). The CLI prints `Warning: <sheet_code>:
skorowidz GUGiK niedostepny — uzyto lokalnej kampanii bez sprawdzenia nowszej
(<error>)` (list and hierarchy: a single `Warning:` with the number of sheets and the sheet codes),
exit code unchanged. `--target-crs` cutout (ADR-027):
`PlCutoutResult.unverified` and sidecar `extra.unverified_sheets`
(`{godlo: blad}`), restored from the sidecar when an existing cutout is skipped
(the CLI repeats the `Warning:` with the suffix `(z sidecara istniejacego wycinka)`).
`all`, `--min-year`, `--force`, no local campaign or an error other than
transport = error as before (ADR-028: no silent degradation; ADR-028
erratum 2). Reason: a temporary GUGiK outage should not fail a re-run
when the data is already local; the `Warning:` keeps it explicit.
A library without `MetadataCache` queries the sheet index on every sheet download —
attaching a cache is recommended (`docs/USAGE.md` section 2).

**Erratum 6 (2026-10-09, closing 0.7.1, documentation review):**
the announcement "a tool for combining campaigns into one surface — 0.7.1"
(Context, the `mosaic` option, decision, (j)) was not delivered: the scope of
0.7.1 was set by the Hydrograf requirements (`docs/PROGRESS.md`, backlog "Do 0.7.1
— wymagania Hydrografa"), and combining campaigns is not assigned to
any release. The decision is unchanged (`mosaic` rejected as a download
strategy; combining belongs to the user or a separate tool); state of the
plan: `docs/SCOPE.md` 3.1. The CLI message for `--target-crs` with `--campaigns
all` (j) ends from 0.7.1 on the reason, without referring to a tool.

**Erratum 7 (2026-10-10, ADR-032 — choosing the data year):**
- (f) **Bounds and conflict.** `--year Y` = `--min-year Y --max-year Y`,
  `--max-year U` selects years <= U (no lower bound), the pair `[L, U]`
  inclusive. The year comes from `aktualnoscRok`, otherwise from `aktualnosc[:4]`;
  `dt_pzgik` is not a data year. For EVERY range `newest`
  and `all` check all sheets BEFORE downloading. A sheet without
  any data = skipped with `Warning:` R5; with data, but
  without a year in the range = `YearRangeError(DownloadError)` and the end of
  the whole task with no downloads before the `Warning:`. The exception carries
  `sheets` (sheet code -> all available years), `min_year`, `max_year`
  and `hints`. The message gives up to 20 sheet codes, the list of years and a hint
  of a ONE-SIDED bound covering all conflicts, if one
  exists; otherwise no hint. This supersedes `NoCoverageError`
  and the `Warning:` for `--min-year` alone from the old (f).
- (g) **Full scan, supersedes [Q5] of erratum 1.** For every range the
  campaign list covers ALL GetCapabilities layers:
  skipping by the upper year from the layer name (`layer_upper_year`,
  `scanned_from`) removed. Only a full scan makes it possible to give all
  years on conflict, also for `all --min-year`; old `campaigns_cache`
  entries with `scanned_from` are a miss. [Q1] remains:
  layers outside `LAYER_PATTERN` are not queried.
- (h) **Cache with a range.** Without bounds `newest` still uses
  `record_cache`. Every range, including `--min-year` alone with `newest`,
  reads the FULL list from `campaigns_cache` (TTL 7 days); the bounds are not
  part of the key. `DownloadManager.check_year_range` queries the provider
  once per sheet without bounds (`campaigns="all"`), filters the list locally
  and keeps the years for the sidecar; sheet index/WFS errors abort the whole
  task before the download. The local campaign fallback I-1 from erratum 5
  works only WITHOUT any year bound.
- (a), (d) **Strategy and link (model A, ADR-032 point 3).** The year flags
  narrow the permitted years, `--campaigns` decides the number of
  flights: `newest` (default, also explicit with any bound) = one
  newest flight in the range, `all` = all flights in the range,
  also several in one year. The standard path points to the newest
  local flight by `(aktualnosc, dt_pzgik, url)`, also a partial one;
  the "never backwards" rule (d) is changed neither by coverage nor by the range —
  a link outside the range is reported by the CLI as `Info:`.
- (i) **Sidecar and measurement.** `request.min_year`/`max_year` only when
  provided; additionally `request.year` when both bounds are equal,
  `request.campaigns` is the resolved strategy. In the flow with a range
  `extra.available_years` contains all years of the sheet. With `all`
  the sidecar of the standard path gets `extra.flights` (flights from
  newest; `id`, `date`, `full_sheet`, optionally `coverage`).
  For > 1 flight in the range and a newest one that is not full (not YES)
  after download the share of valid pixels is measured (ASC: without NODATA,
  orthophoto: nodata or alpha), and the campaign's `extra.coverage` is written
  (0..1, 4 places). An orthophoto without nodata/alpha remains unmeasured.
  When another flight has greater coverage, the standard path has
  `extra.better_coverage` = its id, and the CLI prints `Info:` on stderr
  (also with `-q`); the hard link does not change its target. Newest full =
  no measurement and no message. On refresh `None` removes a stale
  `extra.better_coverage`, it does not write `null`. The `request` sidecar
  describes the first download of the file (reuse does not overwrite it), and
  `extra.parent_request(s)` does not carry year bounds.
- (j) **[Q2], CZ and cutout.** `--year`, `--min-year`, `--max-year`
  and `--campaigns all` with a PL cutout `--target-crs` = `Error:`
  before the network (cutout from the newest campaigns, name without a year).
  For a task without PL every year flag or `all` = `Error:` (CUZK
  does not publish history); on a PL+CZ area under `--country auto`
  the flags apply to PL only, CZ stays current and the CLI prints `Info:`
  once. Year flags do not automatically narrow the task to PL.
  LAZ: the rule and the coverage reference are in erratum 2 of ADR-029.

**Erratum 8 (2026-10-10, ADR-033 — second hard link):**
- (d) Next to the standard path there is a second hard link
  `<segment>/full_sheet/<hierarchy>/<sheet_code>.<ext>` to the newest
  local flight of the task with `full_sheet is True` (sheet index: YES). The same
  mechanics as the standard path (`download/links.py::ensure_link`,
  formerly `ensure_standard_link`; hardlink -> copy, never backwards among
  full flights, sidecar with `extra.link_target`). The rule of the standard
  path is unchanged.
- Consequences for `FileStorage`: `list_files()` skips `kampanie/`
  and `full_sheet/`, `delete(godlo)` removes both hard links with their sidecars,
  files in `kampanie/` remain.

**Erratum 9 (2026-10-12, ADR-036, 0.8.0):** (1) the `kampanie/<date>_<id>/` layout
replaced by versions `<segment>/versions/<hierarchy>/<date>_<id>_<sha8>/`
(the version label = the former campaign directory name); (2) the default mode does not
automatically download a newer campaign with `newest` any more — the
local version stays and a notice about the newer one is given (`--upgrade` / `update="upgrade"`);
(3) erratum 4: the copy instead of a hardlink disappears — a missing hardlink is a file
error (D22); (4) `--force` downloads again, but does not overwrite (the same
content = `unchanged`, different = a new version). The record selection rule and the "newest" key
are unchanged.

**Erratum 10 (2026-10-15, 0.8.0, closing "Open minor items" from the review
T11/FB):** (1) `--target-crs` cutout on the I-1 fallback without `Warning:` -
obsolete: the PL cutout comes from GUGiK WCS (ADR-035, `--cutout` since 0.8.0),
without the sheet index and without the I-1 fallback (`PlCutoutResult.unverified` removed
together with the sheet track, erratum 2 of ADR-035); (2) double I-1 line in the CLI -
fixed earlier (manager log at `debug`, a single `Warning:`); (3)
`MetadataCache.__del__` `ImportError` at interpreter shutdown -
fixed in FB (`__del__` without imports and exceptions); (4) M-7 double INFO
of the campaign count - fixed (a single INFO); (5) M-8 stale link sidecar
after a write failure - corrected: when writing `<link>.meta.json` fails
(`write_link_sidecar`), the old sidecar is removed (`Warning` in the
log), because it would describe the previous version. A link without a sidecar is an unknown
path: the next run recreates the link and the sidecar (self-healing
without an intermediate state that lies; test
`test_failed_sidecar_write_drops_stale_sidecar_and_heals`).

---

## ADR-031: Identifier language — English (sidecar from 0.7.0, API/CLI until v1.0.0)

**Data:** 2026-10-08 (user decision)
**Status:** Accepted — amended by ADR-037 (language of user-facing texts, Z5); partly supersedes ADR-028 (`extra.source` key names) and ADR-030 (`extra.campaign` key names); amends ADR-022 (naming convention of `kartograf-meta/1` sidecar keys); erratum 1: API/CLI in English in 0.8.0 without aliases (points 2-3 obsolete)

**Context:** The sidecar `<file>.meta.json` (`kartograf-meta/1`, ADR-022) is
a contract for consumers (Hydrograf), and its keys arose
incrementally: the main fields and most `extra` keys were English
(`horizontal_crs`, `parent_request`, `sheet_sources`, `full_sheet`), and some
Polish — copied from GUGiK record field names or domain terms:
`request.godlo`, `extra.source.{godlo, aktualnosc, aktualnosc_rok, uklad,
zrodlo_danych, numer_zgloszenia, skorowidz, dt_pzgik, kolor}`,
`extra.campaign.{zgloszenie, dt_pzgik}`, LAZ `extra.{godlo_kafla, rok,
gestosc}`, CORINE `extra.uwaga`, CZ `extra.podil`. In one dictionary
`full_sheet` and `aktualnosc` sat side by side, and the same fact had two names
(`extra.source.numer_zgloszenia` and `extra.campaign.zgloszenie`). The same
mixture affects the API (`godlo` in signatures, `CampaignRef.zgloszenie`)
and the CLI (`--godlo`). The `kartograf-meta/1` schema had not been released yet
(it arrives in 0.7.0), so changing the keys now breaks no release.
DEVELOPMENT_STANDARDS 9.4 had so far settled the language of docstrings,
comments, commits and documentation, but not of identifiers.

**Options considered:**
- A) Leave the mixture — zero cost, but the sidecar contract becomes fixed
  in release 0.7.0 and every later change requires a new schema version.
- B) English sidecar keys now, in the unreleased `kartograf-meta/1`;
  API/CLI gradually (aliases), English only from v1.0.0.
- C) Everything at once (sidecar, API, CLI) in 0.7.0 — one break, but
  Hydrograf/Hydrolog and user scripts would have to change their calls
  without a transition period.

**Decision:** B.
1. **0.7.0 — sidecar keys in English**, the schema stays
   `kartograf-meta/1`, without a compatibility layer (project rule: no shims,
   BREAKING in CHANGELOG): `request.godlo` -> `request.sheet` (all
   tracks); `extra.source`: `godlo` -> `sheet`, `aktualnosc` ->
   `acquisition_date`, `aktualnosc_rok` -> `acquisition_year`, `uklad` ->
   `declared_crs`, `zrodlo_danych` -> `data_source`, `numer_zgloszenia` ->
   `survey_work_id`, `skorowidz` -> `index_url`, `dt_pzgik` -> `pzgik_date`,
   `kolor` (orthophoto) -> `color`; `extra.campaign`: `zgloszenie` ->
   `survey_work_id`, `dt_pzgik` -> `pzgik_date`; LAZ: `godlo_kafla` ->
   `tile_sheet`, `rok` -> `year`, `gestosc` -> `nominal_density`; CORINE
   PNG: `uwaga` -> `note`; CZ SM5: `podil` -> `cz_share`;
   cutout `extra.sheet_sources[]`: `godlo` -> `sheet`, `aktualnosc` ->
   `acquisition_date`. `teryt` stays — a proper name of the TERYT register, not a
   Polish word to translate. Values (sheet codes, layer names, dates, the content
   of `note`) stay in their source form. The mapping of GUGiK record fields to
   sidecar keys is in one place (`SkorowidzRecord.to_source`).
2. **Subsequent 0.x releases — English names in the API and CLI in parallel**
   with the Polish ones (aliases next to the current names: parameters, dataclass
   attributes, CLI flags, e.g. `sheet` next to `godlo`). The Polish name gets a
   deprecation warning only once the English one is available.
3. **From v1.0.0 English identifiers only** (code, API, CLI,
   data keys); Polish aliases removed.

The scope of language beyond identifiers is unchanged: documentation (`docs/`,
`README.md`, `CLAUDE.md`) and commits in Polish, docstrings and comments in
English (STANDARDS 9.4); CLI messages for the user (`Error:`,
`Warning:`, `Info:`) stay in Polish — 9.4 does not regulate them, and this
decision concerns identifiers only. STANDARDS 9.4 refers here.

**Consequences:**
- BREAKING in 0.7.0: a sidecar consumer reads the new names (table in
  `docs/ARCHITECTURE.md` 3.2 and in CHANGELOG 0.7.0, Breaking Changes).
- Old local sidecars (from before this decision) are not migrated; code that reads
  them treats a missing new key as missing information: a campaign sidecar
  without `extra.campaign.pzgik_date` gives no hard link key
  (a lower estimate from the campaign directory name, as without a sidecar); `sheet_sources`
  entries without `sheet` do not count as incomplete sheets when
  skipping a cutout; warning E17 requires `request.sheet`. Refresh:
  `--force`.
- The `record_cache`/`campaigns_cache` payload is the same dictionary as
  `extra.source`; an entry with Polish keys is a cache miss
  (the sheet index is queried again, the entry overwritten) — without `KeyError`.
- The API/CLI stage (points 2-3) requires a separate plan: a list of identifiers
  (`godlo` in signatures and flags, `SheetFetch.godlo`,
  `CampaignRef.zgloszenie`, `LazTile.godlo` etc.), aliases with tests of both
  names, deprecation warnings and a CHANGELOG entry in every release.
  The field names of raw external responses (GUGiK record
  `aktualnoscRok`, CUZK `PODIL`) are not Kartograf identifiers
  and do not change.

**Erratum 1 (2026-10-12, 0.8.0, user decision):** points 2-3 of the decision
(aliases in subsequent 0.x, removal in v1.0.0) do not apply. The API and CLI
move to English identifiers in 0.8.0 in one go, without aliases
and without deprecation warnings (0.8.0 breaks the CLI anyway with the versioned
store). Scope: `godlo` -> `sheet` (`godla` -> `sheets`) in
all parameters, attributes and method names (`download_by_sheet`,
`calculate_hsg_by_sheet`, `validate_sheet`, `horizontal_crs_for_sheet`);
`uklad` -> `system` (`SheetParser.system`, `LazTile.system`,
`FileStorage.get_raw_path(system=)`, segment template `{system}`),
`VALID_UKLADY` -> `VALID_SYSTEMS`; `CampaignRef.zgloszenie` ->
`survey_work_id` (like the sidecar key); `WMS_SKOROWIDZE_ENDPOINT(S)` ->
`WMS_INDEX_ENDPOINT(S)`. CLI: `--godlo` -> `--sheet` (`landcover
download`, `soilgrids hsg`), positional argument of `download` -> `--sheet`,
`parse` stays positional (`SHEET`). Default land cover file name:
`..._godlo_<sheet>` -> `..._sheet_<sheet>`. Unchanged: `dt_pzgik` (a GUGiK
field name), Polish messages, field names of raw responses
(`godlo`, `uklad_xy`, `ukladWspolrzednych*`), columns of the internal SQLite
cache. Internal modules with Polish names (`providers/pl/skorowidz.py`)
are not public API and stay.

---

## ADR-032: Choosing the data year: year range, stopping on conflict

**Data:** 2026-10-10 (user decisions 2026-10-09 and 2026-10-10)
**Status:** Accepted — amended by ADR-033 (`--full-sheet` from point 4; erratum 1) and ADR-054 (the year options filter the flights of plain mode); partly superseded by ADR-036 (point 2: D14, point 4: D13; erratum 3); erratum 2: `--all-campaigns`/`all_campaigns` since 0.8.0; amends ADR-029 (LAZ) and ADR-030 (PL campaigns)

**Context:** `--year` worked only for LAZ, and `--min-year` in the sheet
list allowed skipping a sheet that had only older data.
The newest campaign may be incomplete and within one year there are often numerous
flights. The user needs the same year selection for NMT, NMPT, orthophoto
and LAZ, verification of the whole task before download and information
about the available vintages. CUZK does not publish data history.

**Options considered:**
- A) Only `--year` with stopping, without a symmetric upper bound:
  an inconsistent result of `--year Y` and the bound pairs `[Y, Y]`.
- B) A closed range with verification of all sheets/tiles before
  download and an explicit conflict; year flags determine the permitted
  years, `--campaigns` the number of flights; without changing the rule of the standard
  path.
- C) Partial download or a hard link to the fullest flight:
  does not guarantee the requested year for the whole task, changes the key of
  the ADR-030 (d) hard link and requires coverage known only after download.

**Decision:** B (U1-U16 of the spec, including the "model A" erratum of 2026-10-10;
details and exceptions in erratum 7 of ADR-030 and erratum 2 of ADR-029).
1. `--year Y` = closed `[Y, Y]`, `--min-year L` = `[L, +inf)`,
   `--max-year U` = `(-inf, U]`, a pair = `[L, U]`; each bound is an
   integer 1900..2100, `L <= U`. `--year` with another bound =
   error. The NMT/NMPT/orthophoto year from `aktualnoscRok`, if missing from
   `aktualnosc[:4]`; a missing year does not satisfy the range. LAZ uses
   `akt_rok`. Orthophoto variants and the remaining hard filters of ADR-028
   apply BEFORE the classification of vintages.
2. First the FULL list of data for every sheet (all
   sheet index layers, one checking phase), only then
   download. No data in any year gives a skip with
   `Warning:` like R5. Data only outside the range even
   for one sheet = `YearRangeError(DownloadError)`, `Error:`
   with all its years and a hint, zero files of the task.
   A one-directional hint is given only when it covers
   EVERY conflicting sheet; when both cover all,
   both are shown, separated by `albo`. No common
   hint = years only. A sheet index/WFS failure in this phase =
   an error of the whole task without downloads; I-1 (local campaign)
   remains only for a task without bounds.
3. The year flags are only a filter on permitted years, and `--campaigns`
   decides the number of flights per sheet (model A): `newest`
   (default) = one, the newest flight in the range (key ADR-028),
   `all` = all flights in the range into `kampanie/`, including several
   in one year. Every combination is allowed; the same rule
   for NMT, NMPT, orthophoto and LAZ. The standard path points to the
   newest local flight according to ADR-028 and never falls back to an
   older local campaign (ADR-030 (d)); when, with a range, it
   points to a flight outside the range, the CLI prints `Info:`, and the library
   returns this information in the result.
4. For > 1 flight in the range with explicit `all` and an incomplete newest one,
   coverage by valid pixels is measured after the download. When another
   flight has greater coverage, the CLI prints `Info:` on stderr,
   the sidecar points to that flight (`extra.better_coverage`), but the
   link stays with the newest one. A newest full flight (YES)
   or a single flight = no measurement. An undecided OPTION
   for the future: an explicit flag changing the link rule to
   the newest full flight (`--full-sheet`) or a flight with coverage above a
   threshold (`--min-coverage N`); they would require a different link
   key, sometimes additional downloads and resolving the collision
   with the "never backwards" principle. It is not implemented.
5. LAZ: the reference is the selection according to ADR-029 without year flags,
   after the density and vertical filters. Selection in the range preserves
   ADR-029 (`all`: no deduplication); every reference tile
   must have an intersection with the area covered by tiles
   from the range with a tolerance of 1 m. The conflict has the years of tiles
   crossing the missing fragment and the reference label,
   it does not require the same sheet code. An empty area with no tiles
   in ANY year = no data as before, without a warning.
6. The `--target-crs` cutout accepts no year flag:
   the cutout name carries no vintage and the cutout assembles
   the newest campaigns. A CZ-only task = an error with PL flags
   before the network, a PL+CZ area under `auto` = `Info:`
   and the current CUZK version for CZ.
7. Sidecars (schema `kartograf-meta/1`, additive fields):
   `request.min_year`/`max_year` when given and `year`
   when both bounds are equal, `request.campaigns` is the
   actual sheet strategy. `extra.available_years`
   contains all years of the sheet for a task with a range;
   campaigns with a measurement have `extra.coverage` 0..1, and the sidecar
   of the standard path with `all` has `extra.flights` and
   `extra.better_coverage` only when an older flight is better.
   LAZ: `extra.acquisition_date` and `extra.full_sheet` when
   known. `request` describes the original download, not the last
   use; `extra.parent_request(s)` carries no year bounds.

**Consequences:** Every range requires a full list of vintages
from the service, instead of a partial scan or only `record_cache`
(TTL `campaigns_cache` = 7 days). `YearRangeError.sheets`,
`.min_year`, `.max_year` and `.hints` are available in the library.
A differing vintage on one sheet stops the whole list;
`--campaigns all` with a range may download more data than
`newest`. Coverage informs, it does not change the link target.
In 0.8.0 `--campaigns {newest,all}` is to be replaced
by a switch without a value (e.g. `--all-campaigns`), because `newest`
is always the default (a CLI breaking change, backlog "Do 0.8.0").

**History:** the first version (2026-10-10, before merge) made the
strategy depend on the bounds: `--min-year` alone = `newest`, an upper bound =
`all`, explicit `newest` with an upper bound = error. An audit of the CLI flag logic
revealed an asymmetry (`--min-year 1900` = 4 files, `--max-year 2100` =
23 on C14), redundancy and a mismatch with LAZ; the user accepted model A
(2026-10-10).

**Erratum 1 (2026-10-10, ADR-033):** the option from item 4 (`--full-sheet`)
was implemented WITHOUT changing the link key: the standard path still points to the
newest flight, and the newest full flight gets a second link
`full_sheet/`. In model A `--campaigns` still means the number of flights
(`newest` = one), and `--full-sheet` adds at most one flight per sheet
— only when the newest in the range is not full; with `all` it has no
effect. The year range also filters the full flight. `--min-coverage N`
remains out of scope.

**Erratum 2 (2026-10-12, 0.8.0):** the CLI `--campaigns {newest,all}`
was replaced by the switch without a value `--all-campaigns`, and the library
parameter `campaigns="newest"|"all"` by `all_campaigns: bool = False`
(among others `DownloadManager` and the LAZ download). Without the switch / with
`all_campaigns=False` the newest flight is downloaded; with the switch /
with `all_campaigns=True` all flights in the permitted range.
Model A from item 3 remains unchanged: the year flags filter the permitted
years, the switch determines the number of flights. The sidecar field
`request.campaigns` remains the text strategy `"newest"` or `"all"`
(schema `kartograf-meta/1` unchanged).

**Erratum 3 (2026-10-12, ADR-036, 0.8.0):** item 2 — with an unavailable
sheet index and a year range the task no longer always ends with an error:
when EVERY sheet has a local version with a vintage in the range, the local
versions are used with a warning; otherwise an error of the whole task with no downloads
(D14; default mode only). Item 4 — the coverage of an incomplete flight is
measured when the version is written (`extra.coverage` in the version sidecar,
D13), not appended later; a flight declared as full is not
measured and in the comparison counts as fully covered.

---

## ADR-033: Second hard link to the newest full flight (`full_sheet/`, `--full-sheet`)

**Date:** 2026-10-10 (user decisions F-U1..F-U5)
**Status:** Accepted — partly superseded by ADR-036 (F-U5: `kampanie/`; erratum 1); amended by ADR-054 (`--full-sheet` has no effect with `--output-dir`); amends ADR-030 ((d): second link; erratum 8) and ADR-032 (item 4: `--full-sheet`; erratum 1)

**Context:** The standard path points to the newest local flight, including an
incomplete one (`calyArkuszWypelnionyTrescia = NIE`); E13 only warns about this.
Measurement of 2026-10-07 (577 groups of sheet code x product,
`docs/research/2026-10-06-e2e-brzegowe-i-review/pokrycie-kampanii.md`):
14 sheets with an incomplete newest record, in 8 an older full
flight exists; coverage of the incomplete one from 0.9 % (NMT N-34-139-C-a-3-1) to 98.9 %.
Measurement of the borders of 2026-10-10
(`docs/research/2026-10-10-full-sheet-link/granica-pelne-pokrycie.md`):
YES means "full coverage within the borders of Poland" — 13 files YES, 0 px
nodata on the PL side; nodata beyond the border (e.g. Slubice 75 %) is the foreign
part of the frame. NO says nothing about the scale of the gap.

**Options considered:**
- A) Changing the standard link key to the newest full flight:
  breaks ADR-028/ADR-030 (d) and the meaning of the standard path for
  consumers (Hydrograf).
- B) A mosaic of flights (new + supplement from an older one): out of scope
  (SCOPE 3.1).
- C) Selection by measured coverage (`--min-coverage N`): coverage is known
  only after the download.
- D) A second link next to the standard one to the newest local full
  flight + a flag fetching that flight.
- E) Like D, but fetching by default: changes the number of `newest` flights
  (model A of ADR-032).

**Decision:** D.
- F-U1: fetching only with `--full-sheet`
  (`DownloadManager(full_sheet=True)`): when the newest flight in the year
  range is not full, the task ADDITIONALLY downloads the newest full flight
  from the range (`resolve_campaigns(campaigns="all")`, first record
  `full_sheet is True`). Without the flag `full_sheet/` is created only from flights
  that the task has locally anyway. With `--campaigns all` the flag has no effect.
  The campaign sidecar of such a task: `request.full_sheet: true`.
- F-U2: a sheet without a full flight = no file in `full_sheet/` (no
  link to the "best" incomplete one); one `Warning:` with E13 divides
  sheets into: with `full_sheet/`, without a full flight in the sheet index
  (`DownloadResult.without_full`), full flight not downloaded (hint
  `--full-sheet`).
- F-U3: the full link never goes backwards; when it stays with a flight outside the
  range, `Info:` shared with U15
  (`DownloadResult.full_link_outside_range`).
- F-U4: the `--target-crs` cutout assembles standard paths unchanged;
  `--full-sheet` with `--target-crs` or LAZ = `Error:` before the network;
  CZ like the other campaign options (no PL `Error:`, PL+CZ under `auto` `Info:`).
- F-U5: one English concept `full_sheet` (directory `full_sheet/`,
  flag `--full-sheet`, parameter `full_sheet=`) — this is already the name of the
  GUGiK flag in records and sidecars; the working name `full_coverage/`
  rejected, because `coverage` in the code means measured coverage or no
  data. `kampanie/` stays (renaming is a separate, breaking decision).
- Candidates: only flights with `full_sheet is True` (NO and no flag =
  not full). I-1 (sheet index unavailable) and no candidates leave the
  existing full link unchanged; `--force` refreshes it like the
  standard one; a link failure = a sheet failure.

**Consequences:** When the newest flight is full, both links are
hard links of one file (no space cost; with a copy — two copies).
The first run after the update creates `full_sheet/` for local data,
because the campaign flow passes through every sheet also on
skip. `--full-sheet` downloads at most one additional flight per sheet,
and reads the full list of sheet index layers only for sheets with an incomplete
newest flight (`campaigns_cache`). `full_sheet/` trusts the declaration of the
sheet index; full = within the borders of Poland (border sheets have nodata
beyond the border). LAZ has no `full_sheet/`. Library: `SheetFetch.full_link`,
`.full_link_outside_range`, `.no_full_flight`; `DownloadResult.full_links`,
`.full_link_outside_range`, `.without_full`;
`FileStorage.get_full_sheet_path()`.

**Erratum 1 (2026-10-12, ADR-036, 0.8.0):** F-U5 — "`kampanie/` stays"
no longer applies: `full_sheet/` points to the newest local VERSION of a flight
declared as full in `versions/`. A missing newest full flight
from the scope is "no local version" (the default mode downloads it).

---

## ADR-034: Common mechanism for area queries (chunks on the source grid)

**Date:** 2026-10-10
**Status:** Accepted — amended by ADR-035 (ASC 1 Mpx and NMPT) and ADR-042 (orthophoto cutout chunks; erratum 1: bit-for-bit stitching only for NMT); amends ADR-023 (CUZK chunking) and ADR-024 (NW anchor)

**Context:** CUZK split large `exportImage` tasks via `_tile_grid`
in the client, while GUGiK WCS `download_bbox` made a single request without
alignment to the source grid. The KRON86 measurement of 2026-10-10
(`docs/research/2026-10-10-wcs-limits/raport.md`) showed no hard
WCS limit up to 100 Mpx, but the host dropped connections. The server samples onto
the grid of the request: a bbox off the source grid gives a silent geolocation error
(content shifted relative to the description by a fraction of a pixel). The NMT 1 m grid
has edges `k + 0,5` m in nine measured regions; chunks
from the same grid assemble bit for bit.

**Options considered:**
- A) Ultimately assemble PL cutouts from sheet files — rejected as the
  ultimate cutout path in favour of preparing WCS requests (D-U3);
  the existing cutout still assembles sheets until work on (a).
- B) Download chunks in parallel — rejected given the unstable GUGiK host
  and the cost of retrying a large request.
- C) Align CZ to the ImageServer service grid — deferred; CUZK
  measurement of 2026-09-29, out of scope of this change. The NW anchor was kept.
- D) A common area query plan, sequential download and assembly
  on the source grid where it is measured.

**Decision:** D. The internal module `kartograf/transport/chunks.py` provides
`GridSpec`, `ChunkLimits`, `Chunk`, `align_bbox`, `plan_chunks` and
`fetch_chunks` for CUZK and GUGiK WCS, without knowledge of URLs and products.
With a given grid `align_bbox` expands the bbox OUTWARDS to its lines;
without a grid (CZ) it keeps the NW anchor and an integer number of pixels via
`round`. `plan_chunks` keeps the NW, north-south and
west-east split. The CUZK budget is 4 Mpx per chunk under a practical limit of
approx. 8 Mpx (and ceilings of 15000 x 4100 px); GUGiK NMT 1 m KRON86 GTiff
is 16 Mpx and up to 40000 px per side — a reliability budget, NOT a server limit.
`fetch_chunks` downloads chunks sequentially, assembles them without resampling
and removes intermediate files; `download_to` retries each chunk separately.
WCS responses are subject to `reject_error_document("WCS")`, also with
a single request. NMPT and orthophoto have no measured grid: they stay with
a single request without alignment (orthophoto not measured). The NMPT GeoTIFF returns
RGB uint8 instead of heights — a fix with WCS cutouts in (a) (D-U6).
The WCS measurement concerns only KRON86, because the EVRF2007 endpoint is unavailable
(D-U5). `mosaic_and_crop` without `dtype=` rejects sources with mixed
band types via `ValidationError`, instead of silently adopting the type
of the first file.

**Consequences:** NMT KRON86 `download_bbox` GTiff may have an extent
larger than the task bbox by less than 1 px on each side, and tasks
above 16 Mpx are divided into chunks; the sidecar keeps the task bbox.
CUZK keeps its existing result and request parameters. PL cutouts
from WCS in (a) may use this mechanism (D-U3), but the current PL
cutout still assembles sheets; removing the sheet parameters of the public
`mosaic_and_crop` remains a candidate for 0.8.0.

**Erratum 1 (2026-10-16, ADR-042 D14, plan D):** "chunks from the same
grid assemble bit for bit" applies only to NMT (1 m sheet grid).
The PL orthophoto cutout in the store (`--cutout --coverage --resolution`,
`download/orto_cutout.py`) already has a measured grid (DescribeCoverage
2026-10-16: step 0.1 m for both coverages, Standard and High) and is divided into
chunks (budget 4 Mpx of coverage pixels = 200 x 200 m, even chunk sizes),
but the stitched chunks are NOT bit-for-bit equal to a single request
for the whole area: the server resamples each request in its own extent
(measurement 2026-10-16: 20 x 20 m at 0.1 m - 75-93 % of quadrant pixels
differ, on average 4 DN, max 89; 40 x 40 m at 0.25 m - 70 % of pixels,
on average 4.4 DN, max 120). Repeating the same request gives the same
bytes, and each chunk is a server response copied 1:1 (without
resampling), so the same area and pixel give a reproducible result; a different
split into chunks (a different area) may give different pixel values in the same place.
The orthophoto part of the sentence "NMPT and orthophoto have no measured
grid: they stay with a single request without alignment" now concerns
only the raw `GugikOrtoProvider.download_bbox` without `coverage` (file
outside the store). Measurements: `tests/fixtures/pl/orto_wcs/README.md`.

---

## ADR-035: PL cutouts from GUGiK WCS with a PRG land mask

**Data:** 2026-10-11
**Status:** Accepted; partly supersedes ADR-027 (cutout source in the CLI and `download_pl_cutout`), amends ADR-034 (ASC 1 Mpx and NMPT); erratum 1: NMPT ASC chunk 4 Mpx coverage; erratum 2: sheet track removed in 0.8.0; erratum 3: W-U3/W-U8 superseded by ADR-036 (D15, plan 2/3)

**Kontekst:** Cutting PL out of a mosaic of OpenData sheets (ADR-027) required
the sheet index, downloading whole sheets and handling their different grid phases.
WCS can answer directly for a bbox, but it does not declare nodata: outside
the coverage it returns 0.0, which is also a real height on land
(Żuławy). A query shifted off the sheet grid can silently
shift the geolocation. The report
`docs/research/2026-10-10-wcs-limits/raport.md` (items 2-8) showed
host instability, WCS agreement with the sheet on the 1 m grid, a flight
composition different from the ADR-028 choice and RGB uint8 instead of heights in the NMPT TIFF.
The report `docs/research/2026-10-11-wcs-cutouts/raport.md` (items 1-6)
confirmed a working WCS EVRF2007 via ASC multipart, 1 m and 0.5 m grids,
decimation, the ASC cost and point membership in PRG.

**Options considered:**
- A) Keep cutouts from sheets — certain provenance per campaign,
  but the cost of whole sheets and grid phase problems.
- B) WCS without a mask — fast area selection, but 0.0 over the sea
  and abroad pretends to be data.
- C) WCS with every 0.0 replaced by nodata — loses valid pixels
  with a height of 0 m on land, especially in Żuławy.
- D) WCS with a PRG land mask — rejects pixels outside the land,
  keeping 0.0 inside; accepted.

**Decision:** D, according to W-U1..W-U11 of the spec
`docs/superpowers/specs/2026-10-11-wcs-cutouts-design.md`:
- W-U1, W-U6: CLI `--bbox`/`--geometry --target-crs` and
  `download_pl_cutout` use WCS, not sheets. The former sheet API
  (`prepare_pl_cutout` + `select_pl_cutout_sheets` + `run_pl_cutout`,
  `build_cutout_from_sheets`, `PlCutoutSheets`) stays with unchanged
  behaviour, marked as deprecated for removal in 0.8.0;
  `prepare_pl_cutout` also prepares the new WCS track.
- W-U2, W-U7, W-U10: NMT and NMPT cutouts only at 1 m (KRON86 and
  EVRF2007); 5 m rejected. No campaign or year choice.
- W-U3, W-U8: name `<segment>/bbox/<coords>_<YYYYMMDD>.tif`;
  every run downloads again, does not skip an existing file.
  A successful write atomically replaces the file of the same day, a failed one
  leaves the previous file and sidecar.
- W-U4: EVRF2007 NMT and both NMPT verticals get heights from
  `image/x-aaigrid` (multipart ASC -> GeoTIFF float32);
  NMT KRON86 keeps `image/tiff` float32.
- W-U5, W-U11: before WCS the PRG mask is downloaded:
  `A00_Granice_panstwa - W02_Morze_terytorialne_RP -
  W03_Morskie_wody_wewnetrzne`, rasterised by pixel
  centre (`all_touched=False`); outside it nodata -9999.
  **0.0 on land remains data**, it is not globally
  replaced with nodata.
- W-U9: the source bbox is aligned OUTWARD to the 1 m sheet grid
  `GridSpec(1.0, 0.5, 0.5)` before downloading and splitting into chunks.
  NMPT with a native step of 0.5 m gives a 1 m result through
  `SCALEFACTOR=0.5`; over a 0.5 m flight this is decimation, not averaging.
  ASC chunks have a limit of 1 Mpx of coverage pixels (NMPT 1 m: 0.25 Mpx
  of result) and a read limit of at least 120 s, TIFF 16 Mpx (ADR-034).
  Every query has an even width and height (range widened
  by at most 1 px to the east/south, clipped after stitching): with an
  odd size the server, when resampling, takes the middle
  row and column from the neighbouring source pixel (live verification
  `docs/research/2026-10-11-wcs-cutouts-live/raport.md` items 3, 5).
  Reprojection to EPSG:5514/3045 stays local with a pinned operation.

**Consequences:** WCS presents the newest flight of the area without
attaching older ones; it does not select the newest sheet of exactly
1 m according to ADR-028. A cutout may therefore have a different flight than the downloaded
sheets (report 2026-10-10 item 8, 2026-10-11 item 4), and zeros
inside the mask are not filled in from an older flight. The sidecar describes
`bbox_raster`, WCS `extra.source` with `composition="server"`,
PRG `extra.mask`, `zero_pixels`, `all_nodata` and any
`parent_request`; there is no `sheet_sources` in the new track.
`download_bbox` for EVRF2007 and NMPT returns float32 with heights
on the 1-metre sheet grid, without the PRG mask and without nodata.
The sheet parameters of `download_pl_cutout` and `mosaic_and_crop`
(`snap_to_source_grid`, `assign_crs`) are dropped in 0.8.0.
The old decisions ADR-027 and ADR-034 keep their description of the state at the time
of the decision; this ADR defines the new track. Live verification (report
2026-10-11-wcs-cutouts-live): NMT/NMPT cutouts of both CRSs = the sheet
of the same flight in 100 %; on the coast (Gdynia, Hel, Mierzeja Wiślana)
outside the mask there is water with a WCS height of approx. 0-0.3 m (median), no
pixel > 5 m, > 2 m: 0-1048 px per 1 km2; on land 0-82 px of 0.0 remain.

**Erratum 1 (2026-10-11, tuning of NMPT ASC chunks,
`docs/research/2026-10-11-nmpt-asc-tuning/raport.md`):** the NMPT
ASC chunk limit is 4 Mpx of coverage pixels (1 Mpx of 1 m result), not 1 Mpx
coverage (0.25 Mpx of result) from W-U9; NMT EVRF2007 stays at 1 Mpx,
the 120 s read limit is unchanged. Host hangs (no byte for
300 s) hit chunks of every size, and a 4 Mpx coverage chunk
answered in 15-26 s like a 1 Mpx one; fewer chunks means fewer retries.
Live NMPT 2000 x 1000 px: 2 chunks, 246 s (previously 8 chunks,
1186 s), bit for bit identical to a single query.

**Erratum 2 (2026-10-11, 0.8.0, precondition of the versioned store
D16):** the deprecated sheet track removed without a transition period:
`select_pl_cutout_sheets`, `run_pl_cutout`, `build_cutout_from_sheets`,
`PlCutoutSheets`, the sheet fields of `PlCutoutResult`, the sheet parameters of
`download_pl_cutout`, `mosaic_and_crop(snap_to_source_grid=,
assign_crs=)` and the now unused `GridMismatchError`. A PL cutout
is produced exclusively from WCS; the sheet mosaic is assembled by the caller
(`mosaic_and_crop`, `check_source_grid`).

**Erratum 3 (2026-10-12, ADR-036):** W-U3/W-U8 (name with a date, download
on every run) superseded by decision D15 of the versioned store:
`bbox/<coords>.tif` as a hard link to the newest version, the date only
in the version label, by default the local version (no PRG and WCS queries),
`--force` downloads again. Implemented in 0.8.0 (plan 2/3 of the store);
`<coords>_<YYYYMMDD>.tif` files from 0.7.x are not recognised (D10).

---

## ADR-036: Versioned store

**Data:** 2026-10-12 (spec accepted 2026-10-11, decisions D1-D24; revisions 2026-10-12, D26-D28 and D29-D33)
**Status:** Accepted — partly superseded by ADR-042 (D27: orthophoto cutout in the store; erratum 2) and ADR-044 (D32: public land cover and HSG reports); amended by ADR-037 (CZ sheet in the public API; erratum 1), ADR-042 (D23 between releases, unit slots) and ADR-054 (store marker, `root`, plain mode as the second write target); partly supersedes ADR-030 (`kampanie/`, automatic `newest`, copy), ADR-032 (items 2 and 4), ADR-033 (F-U5), ADR-035 (W-U3/W-U8) and ADR-003 (`DownloadManager.download_bbox`); amends ADR-026 (`versions/`; land cover and HSG in the `data/` layout); erratum 3: default mode without signal queries when a local version exists, `--upgrade` queries the source (live test 0.8.0); erratum 4: content confirmation of a link without a link count (SMB without `serverino`) and data states in `check_sheets` (E2E test 0.8.0)

**Context:** Up to 0.7.x the store could silently overwrite data: `--force`
overwrote the campaign file, `newest` automatically switched the path to
a newer campaign, the campaign sidecar was appended to (`parent_requests`,
`coverage`), and without a hard link the standard path was a copy.
There was no way to check freshness without downloading.

**Options considered:**
- A) Keep `kampanie/` and add checksums.
- B) Versions identified by content (sha256) with an immutable sidecar,
  exclusive write, update modes and an update plan.

**Decision:** B, according to the spec
`docs/superpowers/specs/2026-10-08-versioned-store-design.md` (D1-D24):
- layout `<segment>/versions/<hierarchy>/<label>_<sha8>/<name>`
  (D17), label `<date>_<id>` of the campaign / edition / UTC download date;
- write: working directory `versions/.incoming/<host>_<pid>_<token>/`,
  a single read (sha256 + coverage, D20), `fsync`, exclusive `os.link`
  (D18, D21), cleanup of leftovers > 24 h (D19); the same content =
  `unchanged`, the same content with a new campaign label = `relabeled`
  (a new directory with a hard link, D23); the version sidecar is written once
  (`extra.version`, `extra.coverage`, D12, D13), published exclusively;
- the standard path and `full_sheet/` = exclusively hard links to versions
  (D22; no hard links = error), never backwards;
- `update` modes: default (local versions, missing ones downloaded, a newer
  campaign only reported — D5), `upgrade`, `force` (downloads, does not
  overwrite), `check` = `check_updates` (plan `kartograf-plan/1`,
  downloads nothing); `upgrade(plan)` checks the signal again;
- sheet index unavailable: without a year range the local version + a warning
  (every strategy), with a range D14.

**Consequences:** Plan 1/3 (2026-10-12) implements the store for PL sheets
NMT/NMPT/orthophoto (`DownloadManager`, CLI `--sheet`/`--bbox`/`--geometry`
without `--target-crs`): `versions.py`, `updates.py`, `--check-updates`,
`--upgrade`, `--plan`, version statuses in the CLI. `kampanie/` from 0.7.x is
not migrated (re-download, `Info:`). Plan 2/3 (2026-10-12)
covers the remaining `kartograf download` tracks: LAZ tiles, CZ sheets
(TM33/SM5, moved from the CLI to `download/cz_sheets.py`), CZ cutouts
and PL cutouts from WCS in `bbox/<coords>.tif` without a date (D15); the common
policy for files without a campaign `download/fetch.py`, a plan with an item track
(`download/plan.py`, `PlanItem.track`/`unit`), `--check-updates`/
`--upgrade`/`--plan` for every track (with `--country auto` one plan
for PL and CZ). Plan 3/3 (2026-10-12): land cover (BDOT10k, CORINE, SoilGrids)
and HSG in the `data/` layout (D29-D33 below). The store requires a file system with hard links; when the file system
does not provide stable inode numbers (SMB without `serverino`, `samefile`
false for a hard link), the link is confirmed by content: both paths have
more than 1 link, the same size, and the sha256 of the link = the sha256 from the version sidecar
(a full file read only on such shares). Store copy: `rsync -aH`.

Decisions of the 2026-10-12 revision (plan 2/3):
- D26: a LAZ file = a version per file (the name `<report>_<record>_<sheet_code>.laz`
  changes with the survey), label `<date>_<report>`; an exception to D5 —
  a newer survey means new files, downloaded by default, a tile with a local version
  is not downloaded again (only `--force`).
- D27: `DownloadManager.download_bbox` removed (erratum 2 of ADR-003).
- D28: `Content-Length` is not a freshness signal.
- Signal per access channel (`AccessChannel.update_signal`, inventory
  `docs/research/2026-10-12-signal-inventory/raport.md`):

| Channel | Signal | Label |
|---|---|---|
| PL sheets NMT/NMPT/orthophoto (sheet index) | `index` | campaign |
| LAZ (WFS record) | `index` | campaign (D26) |
| GUGiK WCS (PL cutouts) | `none` | download date |
| SM5 CUZK (`openzu`) | `http` (`ETag`, `Last-Modified` in `extra.http`) | download date |
| `exportImage` CUZK (TM33, CZ cutouts) | `none` (`ETag` depends on the query) | download date |
| BDOT10k (county package) | `none` | download date |
| SoilGrids (WCS) | `metadata` (release from GetCapabilities, D29) | release, e.g. `2.0` |
| CORINE CLMS | `metadata` (`characteristics_release_major_version` from the CLMS catalogue, D29) | release, e.g. `V2020_20u1` |
| CORINE WMS preview (EEA/DLR) | `none` (D31) | download date |
| HSG (derived) | set of input sha256 values (D33) | input release |

  The same content under a new `ETag` = `relabeled`, under the same one or without
  a signal = `unchanged` (D23 for `http`). Without a cheap signal: by default
  and with `--upgrade` the local version (unchecked, `--force` downloads). All
  measured objects were byte-for-byte reproducible, so `--force` with an
  unchanged source gives "no changes".

Decisions of the 2026-10-12 revision (plan 3/3, verification
`docs/research/2026-10-12-plan3-spec-check/raport.md`):
- D29: the `metadata` signal of SoilGrids and CORINE = the source release: the title
  of the GetCapabilities of the property map (`SoilGrids250m 2.0 - Clay content` ->
  `2.0`) and `characteristics_release_major_version` of the public CLMS
  catalogue (without credentials). The release is the version label (`label_source =
  "edition"`), described in `extra.edition`. CLMS UIDs for 2012/2006/2000 corrected
  according to the catalogue.
- D30: no SoilGrids/CORINE version is created without a release: a release
  unavailable without a local version = file error; with a local version by default
  `Warning:` (local unchecked), `--upgrade`/`--force` = error.
  Comparison: the local version label against the source release (a different release =
  by default information, `--upgrade` downloads); a version with a different label
  (not from a release) is not comparable. HTTP headers of a channel without a signal
  (`none`) do not distinguish versions (the same content on another day = `unchanged`).
- D31: the CORINE preview from WMS (without `CLMS_CREDENTIALS`, also 1990) is a separate
  product in the segment `eu_corine_<year>_preview` (WMS channel, `none`,
  date label) — never a version of a CLMS data file.
- D32: `LandCoverManager` and `HSGCalculator` write exclusively to the store
  (`output_dir` = the root of `--output`, without `output_path`); the historical results of the
  methods `LandCoverResult`/`LandCoverAreaResult`/`HsgResult` from
  `VersionedFile` replace the public reports from ADR-044 D5. A file outside
  the store: `provider.download_by_*` and `hsg_from_rasters`.
- D33: HSG calculated from versions of the clay/sand/silt inputs (table 4.2, without a
  temporary directory and without `keep_intermediate`); label = release of the inputs
  (different ones: sorted, joined with `+`), `extra.source_files[]` with `sha256`
  and the path of the input version; a version with the same set of input sha256 values is
  reused (`reused`, no calculation), `--force` applies to the inputs.
- Segments (spec 3.4, lowercase): `landcover/pl_bdot10k_gpkg[_<layers>]`,
  `landcover/pl_bdot10k_gpkg_zip` (`keep_raw`), `landcover/pl_bdot10k_shp`,
  `landcover/eu_corine_<year>[_preview]`,
  `soil/global_soilgrids_<property>_<depth>_<stat>`,
  `hsg/global_soilgrids_<depth>_<stat>`; under the segment `teryt/<T>`,
  `bbox/<coords>` or the sheet code hierarchy. Plan lanes `landcover` and `hsg`.
- Limitations: a data correction within the same release (without a label
  change) is detected only by `--force`; a CLMS download with credentials has not been
  verified live (2026-10-12). An HSG with the same content from other inputs
  remains the version with the first inputs in `source_files` (versions are
  immutable), so such inputs calculate HSG on every run.

**Erratum 1 (2026-10-12, ADR-037, decision 9 of plan 2/3):** the CZ sheet
(TM33/SM5) has a public API: `download_cz_sheet`/`check_cz_sheet`
(`kartograf/download/cz_sheets.py`, result `CzSheetResult`, exported
in `kartograf/__init__.py`); the earlier "no public API for the CZ sheet"
no longer applies. The lanes are called by `download_data`/`check_data`
(CLI and API consistency, ADR-037).

**Erratum 2 (2026-10-16, ADR-042 D14, plan D):** D27 (and the sentence of erratum 2
of ADR-003 "raw WCS (e.g. orthophoto) outside the store") partly no longer
applies: the PL orthophoto has a WCS cutout in the version store
(`imagery download --product orto --cutout --horizontal-crs EPSG:2180
--coverage standard|high --resolution 0.1m|0.25m|0.5m|1m`,
`download_orto_cutout`/`check_orto_cutout`, segment
`orto/pl_1992_<coverage>_<res>/bbox/`, signal `none`, plan lane
`pl_cutout`). The raw `GugikOrtoProvider.download_bbox` without `coverage`
remains a file outside the store; `DownloadManager.download_bbox` remains
removed.

**Erratum 3 (2026-10-17, live test 0.8.0, coordinator decisions):**
(1) the default mode does not query the source for a file with a local version: the signals `http`
(`HEAD`) and `metadata` (release from GetCapabilities, the CLMS catalogue or
an ATOM feed) are compared only by `--check-updates` and `--upgrade`; by default
the local version is used without a query (`VersionedFile.unverified =
"unchecked"`, CLI `(bez sprawdzania; --check-updates)`), and a BDOT10k map sheet
with a local version does not get GetFeatureInfo. The suffix `dostepna
nowsza` is given by default only for an index record that the lane queries anyway
when choosing files (PL sheets from the sheet index cache, LAZ tiles,
ADR-043 records) - D5 applies to these lanes unchanged. The sentence of D30 "with a local
version `Warning:` by default" no longer applies: without a query there is no
failure. Reason: without a network every re-run waited for 3 attempts
(up to 19 s) and ended with `Warning:` or an error (maps), although the local file
was ready. (2) `--upgrade` opens the metadata cache in refresh
mode like `--check-updates` and `--force` (`fetch.refreshes_cache`):
a new flight published within the TTL is visible without a prior check.

**Erratum 4 (2026-10-19, E2E test 0.8.0):** (1) Confirmation of the hard link
on a share without stable inode numbers (SMB without `serverino`) relies
solely on content: the same size and SHA-256 of the file = SHA-256
from the sidecar of the version to which the link sidecar points. The condition "both
paths have more than 1 link" is REMOVED: the cifs client reports
`st_nlink` = 1 for a path after it is opened (also after a confirming
read) for several seconds, so the condition reverted the link
to an older flight ("never backwards" violated) and gave an unstable `link_target`.
A path with the content of a version IS that version (`links._hold`); an independent copy
(neither path reports a second name) is turned by `ensure_link` into
a hardlink of THE SAME version, and "stays" writes nothing.
Without a usable link sidecar (M-8) the path is still unknown
and may be repointed to the chosen version (ADR-030 erratum 10). (2)
`DownloadManager.check_sheets` reproduces the data states of the download: a sheet without
data in the sheet index is not a plan item (`on_no_coverage`; >= 1 sheet
with data: `Warning` `no_coverage_some`, code 0; none: `NoCoverageError`),
a year conflict is a single `YearRangeError` for all sheets, and
`check_failed` remains for a sheet index failure.

---

## ADR-037: CLI and API consistency

**Data:** 2026-10-12 (spec `docs/superpowers/specs/2026-10-12-cli-api-consistency-design.md`, plan `docs/superpowers/plans/2026-10-12-cli-api-consistency.md`)
**Status:** Accepted — amended by ADR-038 (names of CRS flags and parameters), ADR-039 (one command = one library function), ADR-044 (D5-D6: land cover, soils and HSG functions, reports) and ADR-046 (command result as a JSON document, `--json`, error and exit codes); amends ADR-036 (CZ sheet in the public API; erratum 1 of ADR-036) and ADR-031 (language of user-facing texts)

**Context:** The 2026-10-12 audit showed that the same task from the CLI
and from the library gave different results: data logic only in the CLI (`--country
auto`, validation of `--system`/`--scale`, `parent_request`, `--geometry`
and `--bbox-crs` outside PL sheets, the CZ sheet, BDOT10k from many counties),
four shapes of result and plan, a different metadata cache (CLI in cwd,
library without), `ValueError` alongside `ValidationError` and mixed language
of messages. Hydrograf uses the library, so the result could not depend
on how it was run.

**Options:**
- A) The library as the only place for data decisions; the CLI only translates
  flags and prints the result; CLI = API parity tests.
- B) Leave the logic in the CLI and add its equivalents to the library (two
  sources of truth, the divergence returns with every change).
- C) The library calls the CLI (`main([...])`) - result only as text.

**Decision:** A. Rules (spec 3):
- Z1. The CLI only translates: in `kartograf/cli/` it is not allowed to validate data
  values, choose countries, sheets, scale, campaigns or counties, build
  `parent_request` or read sidecars in order to make decisions. It may parse
  flag text, read/write the plan file, format the result, derive the exit
  code from result fields and draw progress (`tests/test_cli_translation.py`
  `test_cli_imports_no_data_logic`).
- Z2. The `download`/`check` pair: every public download function has
  a `check_*` twin with the same arguments (without `update`, `plan`,
  `workers`, `on_progress`); every download function accepts `update=`
  and `plan=`.
- Z3. Data messages are created in the library as
  `Notice(level, code, text)` in the `notices` field of the result and through
  `on_notice`; the CLI prints `Info:`/`Warning:` to stderr (also with `-q`).
- Z4. Invalid input = `ValidationError` (`ParseError` for sheet codes),
  source = `DownloadError`, cache = `CacheError`; program errors remain
  built-in; `ValidationError` does not inherit from `ValueError`.
- Z5. Help, CLI messages and the texts of `KartografError` exceptions in Polish,
  ASCII only; `metavar` in Polish (`GODLO`, `KATALOG`, `PLIK`,
  `ROK`, `NAZWA`, `KOD`, `SKALA`).
- Z6. Shared metadata cache: `cache: MetadataCache | bool = True`
  (`True` = `<cwd>/.kartograf_cache.db`, `False` = none); `update="force"`
  without cache reads in this call.
- Z7. Parity tests (`tests/test_parity.py`,
  `tests/test_parity_landcover.py`): the same store byte for byte (files,
  sidecars, versions), statuses, plan, `notices`, error type and text, with
  a frozen clock (`kartograf/_clock.py`).

Decisions S1-S6 (spec 7): S1 `download_data`/`check_data` (the name `download`
collides with the subpackage); S2 internal steps (`prepare_pl_cutout`,
`run_*`, `check_laz_updates`, `check_updates`, `upgrade`) outside the API;
S3 public `download_landcover`/`check_landcover` with the `LandCoverReport` report
instead of the `LandCoverManager.download` method with
`LandCoverAreaResult` (ADR-044 D5; internal
`download_all_counties`/`download_by_*`/`download_batch` removed);
S4 public `calculate_hsg`/`check_hsg` with `sheet`/`bbox`/`geometry`,
without `stat` (ADR-044 D5); S5 `cache: MetadataCache | bool`; S6 exception
texts in Polish ASCII (they reach the CLI 1:1).

**Consequences:** Version 0.8.0 breaks the API (CHANGELOG [0.8.0] "Co
zrobic"): `DownloadResult` as a return value instead of `last_result`,
`check_sheets`/`download_sheets(plan=)`, `workers`, new signatures of
`check_*`, `LandCoverAreaResult`, HSG without `stat`, message texts.
A new library command `kartograf.download.data`: `download_data`/
`check_data` -> `DataReport(files, failed, stale, superseded, notices,
ok)`; `ok` is the CLI exit code rule (partial success of `auto` = `ok`
with a `Notice`). New R7 flags: `landcover download --layers --keep-raw
--bbox-crs --workers --quiet`, `soilgrids hsg --bbox-crs --quiet`.
The parity tests found and removed two discrepancies: the bbox in the sidecar
made of integers (library) vs floats (CLI) - now
always `float` (`core.bbox.bbox_coords`); the order of the result of parallel
sheets depending on threads - now the order of submission. Risk Z6:
a library process with a read-only cwd gets the cache disabled
with a `Notice`. A CLI change without a library equivalent is an error (the
CLI imports test and the parity tests).

**Erratum 1 (2026-10-13, code audit 0.8.0-dev):** clarification of the implementation
of Z1-Z3: `kartograf/cli/_parser.py:parse_bbox_arg` parses four numbers
and calls the library `validate_request_bbox`; `download_data`/`check_data`,
`LandCoverManager.download`/`.check` and `HSGCalculator.calculate_hsg`/
`.check_hsg` also validate the bbox and choices when called without the CLI. Z2
applies to command-level functions, not to low-level provider methods;
the `check_*` equivalents also accept `on_notice`. Z3: `SHEET_LIST`
is a `Notice` from the library, but the CLI displays the sheet list as a header
on stdout (instead of `Info:` on stderr); the other data `Notice`
messages go to stderr, also with `--quiet`. An additional CLI message
about saving the `--plan` file concerns an operation on the plan file, not data.

**Erratum 2 (2026-10-18, ADR-046):** the command result is a library document
(`Document`: `to_dict()`/`to_json()`), and the CLI in `--json` mode prints `to_json()`
instead of text (Z1 extended to JSON; rule Z8 in STANDARDS 7.3). Z3: in `--json`
mode the `Notice` messages are only in the `notices` field of the document (stderr empty), not
as `Info:`/`Warning:` on stderr, and saving the `--plan` file does not print an `Info:` line.
Input errors (`ValidationError`, `ParseError`, `UsageError`) end the CLI with code 2, not 1
(one table of exit and error codes: USAGE 9.3). The CLI imports test allows
`kartograf.catalog` and `kartograf.serialization`.

**Erratum (2026-10-25, ADR-053):** Z5 and S6 (Polish ASCII texts of the library, the
CLI and `KartografError`) are amended: the texts of the library, the notices and the
error document are English by default, and the Polish ASCII texts are the second language of
the message catalog (`kartograf.messages`), shown by `--lang pl`, the default of a person at
a terminal.

---

## ADR-038: Explicit cutout mode and CRS names (--cutout, --horizontal-crs, --sheet-system)

**Data:** 2026-10-13
**Status:** Accepted — amended by ADR-039 (flag names in groups); partly supersedes ADR-027 (enabling the PL cutout with a CRS flag, the name `--target-crs`) and ADR-023 (the CZ area always a cutout, no mode flag); amends ADR-037 (CLI names = API)

**Context:** The user asked whether `--horizontal-crs`/`--datum` would not
be clearer than `--target-crs`/`--system`. Code 0.8.0-dev:
`--target-crs` does two things at once - it gives the result CRS and, for PL
`--bbox`/`--geometry`, switches the sheet download to a single cutout from the GUGiK
WCS (ADR-027, ADR-035); for CZ an area always gives a cutout (`exportImage`,
without the flag natively EPSG:5514). `--system` selects the sheet system of PL
sheets (1992 -> EPSG:2180 files; 2000 -> files in the sheet zone EPSG:2176-2179),
not the datum (both systems have the ETRF2000-PL datum). 0.8.0 breaks the CLI/API anyway.

**Options:**
- A) No change of names; better help and an `Info:` about the mode.
- B) An explicit mode flag `--cutout`, cutout CRS `--horizontal-crs`
  (symmetry with `--vertical-crs`), sheet system `--sheet-system`.
- C) A single flag `--horizontal-crs` instead of `--system` (EPSG:2180 =
  1992 sheets, EPSG:2176-2179 = 2000 sheets of one zone) - a PL-2000 area
  in several zones would have no value, an EPSG:5514/3045 cutout
  has no sheet equivalent.

**Decision:** B (user decision 2026-10-13), without aliases of the old names:
- D1. `--cutout` / `cutout: bool` enables the single-cutout mode; only
  with `--bbox`/`--geometry` (with `--sheet` an error).
- D2. `--horizontal-crs` / `horizontal_crs=` = cutout CRS, required
  with `--cutout` (no default value, also native CZ:
  `--horizontal-crs EPSG:5514`); without `--cutout` an error.
- D3. A CZ area without `--cutout` = error (CUZK has no sheet mode
  for an area); `--country auto` with an area reaching CZ requires `--cutout`,
  and then the PL part is also a cutout (no combination of PL sheets +
  CZ cutout).
- D4. `--sheet-system` / `sheet_system=` instead of `--system` / `system=`
  in sheet selection: `download_data`/`check_data`, `find_sheets_for_bbox`,
  `find_sheets_for_geometry`, `SheetParser(sheet_system=)` and
  `SheetParser.sheet_system`. Unchanged are the low-level names
  describing the file or segment CRS (`LazTile.system`,
  `FileStorage.get_raw_path(system=)`, the `{system}` template, the cache key
  of the CZ sheet index).
- D5. `horizontal_crs=` instead of `target_crs=` in task functions
  (`download_data`/`check_data`, `download_pl_cutout`/`check_pl_cutout`,
  `download_cz_cutout`/`check_cz_cutout`) and in the CUZK provider
  (`create_dmr_provider`, `CuzkDmrProvider`); general transformation functions
  (`transform_bbox`, `get_overall_bbox`) remain with `target_crs` (the target
  of the transformation, not the task mode).
- D6. The `kartograf-meta/1` sidecar unchanged (the `horizontal_crs` key already
  describes the file CRS; `system` and `target_crs` are not sidecar keys).

**Consequences:** A breaking change to the CLI and API in 0.8.0 (CHANGELOG [0.8.0]
"Co zrobic"): old flags give an argparse error, old arguments `TypeError`.
A cutout requires three flags (`--cutout --horizontal-crs ...` + an area),
but the mode and the result CRS are visible in the command. Downloading a CZ area
requires `--cutout` also for the native CRS.

---

## ADR-039: CLI command groups by data type

**Date:** 2026-10-15
**Status:** Accepted — amended by ADR-040 (the data command sets `_task` for `project add`), ADR-042 (groups `boundaries`, `cadastre`, `models3d`, `hydro`), ADR-043 (groups `names`, `maps`, `geodesy`) and ADR-046 (command declarations in the catalog, CLI parser built from the catalog); partly superseded by ADR-044 (D1: `landcover --source`, D5: functions instead of methods); amends ADR-037 (the CLI only translates; one command = one library function) and ADR-038 (flag names); no aliases for removed commands (same rule as erratum ADR-031)

**Context:** CLI 0.8.0-dev had a single `download` command for NMT, NMPT,
orthophoto and LAZ (with flags that apply to only some products:
`--vertical-crs`, `--resolution`, `--cutout`, `--min-density`),
`landcover` with `--source` that also covered SoilGrids, and `soilgrids hsg`.
The `--help` of a single command mixed flags unrelated to the selected product,
and `--year` and `--sheet` meant different things in different commands. The roadmap
(subproject 3) adds further data types (boundaries, parcels, 3D models,
names, maps), which will not fit in a single command.

**Options:**
- A) A single `download` command with successive `--product` values; flags validated
  in the library (current state).
- B) Command groups by data type: `kartograf <group> <command>`; each
  group has its own flags and help; a new data type = a new group.
- C) A command per product (`kartograf nmt`, `kartograf orto`, ...).

**Decision:** B (user decision 2026-10-13, included in 0.8.0), without
aliases for the old names:
- D1. Groups in 0.8.0: `elevation` (`--product nmt|nmpt|laz`; NMT/NMPT PL,
  DMR CZ, LAZ), `imagery` (`--product orto`), `landcover` (`--source
  bdot10k|corine`), `soil` (SoilGrids, HSG). `parse` and `cache` stay
  outside the groups. Group commands: `download`, `list-sources` (every group),
  `list-layers` (`landcover`, `soil`), `hsg` (`soil`).
- D2. Each group is a single module `kartograf/cli/groups/<group>.py`
  with `register(subparsers)`; `register_groups` discovers modules via
  `pkgutil` (alphabetically, `_*` modules are helpers), so a new group is
  one new module with no changes in the common file. Common flags (area,
  update modes, `--quiet`, `parse_bbox_arg`) are in `cli/_args.py`;
  `cli/_parser.py` contains only the main parser, `parse`, `cache` and the error for
  removed commands.
- D3. A group has only its own flags: `imagery download` does not accept
  `--vertical-crs`, `--resolution`, `--cutout`, `--horizontal-crs`,
  `--min-density`; `--country` in `imagery` is `pl|auto` (no CZ orthophoto;
  `cz` will arrive with plan D). A flag from outside the group is an argparse error.
  The library rules (orto + CZ, orto + cutout) still apply at the
  `download_data` level (ADR-037).
- D4. `--sheet` has one definition in all groups: the area of the sheet
  with that sheet code. When the source publishes the product in these sheets (NMT, NMPT,
  orto PL; DMR CZ), the result is the sheet files 1:1; otherwise data from the extent of the
  sheet (LAZ: tiles, BDOT10k: counties, CORINE/SoilGrids/HSG: cutout).
  The flag name is unchanged.
- D5. `--year` has one definition: the year that the data describe. `elevation`
  and `imagery`: flight filter (the newest flight from the year, with `--min-year`/
  `--max-year`); `landcover`: release (CORINE 2018; later the BDOT10k
  annual edition from plan C).
- D6. A missing `--product` (or `--source` in `landcover`) gives a message
  listing only the choices of the group (`options.product_choices()`); the value
  is still validated by argparse and the library. `soil download` has no `--source`
  (one source). `imagery download` keeps the required `--product orto`
  despite a single product: the group will get further products in plan E (true
  orto, oblique orto, intensity images), so the flag will not change
  when they are added. `list-sources` prints a table from the descriptor registry
  (WYBOR, KRAJ, DOSTAWCA, KLUCZ = `dataset` of the sidecar, NAZWA) without network access.
- D7. Removed commands end with a parser error (code 2) with the name of the new
  command, without a working alias: `download`, `soilgrids`,
  `landcover ... --source soilgrids`. The library and the `kartograf-meta/1` sidecar
  are unchanged (the public API change is introduced
  only by ADR-044 D5); `data/` segments unchanged.
- D8. CLI commands still only translate into library functions (ADR-037):
  `elevation download` and `imagery download` -> `download_data`/
  `check_data`; `landcover download`, `soil download` and `soil hsg` ->
  module functions specified in ADR-044 D5 (not class methods).
  `kartograf.cli.commands` loses `cmd_landcover`/`cmd_soilgrids`;
  `parse_bbox_arg` is in `kartograf.cli._args`.

**Consequences:** A breaking CLI change in 0.8.0 (CHANGELOG [0.8.0] "What to
do": old -> new command table). The `--help` of a group contains only
relevant flags. New products add groups without changes to existing ones;
branches with new groups must use `cli/groups/<group>.py` and
`add_group`/`add_list_sources` from `kartograf.cli.groups` and flags from
`kartograf.cli._args`. Scripts calling the old commands (including
Hydrograf/Hydrolog) must be updated.

**Erratum 1 (2026-10-18, ADR-046 D4):** the modules `kartograf/cli/groups/*`, the functions
`add_group`/`add_list_sources` and the flags in `kartograf/cli/_args.py` were replaced by the declaration of
commands in `kartograf/catalog/commands/<group>.py` (parser: `catalog/cliparser.py`,
`cli/_parser.py::create_parser` is a facade; a new group = one new declaration module,
STANDARDS 17.2); `parse_bbox_arg` is in `kartograf.catalog.kinds`. The names of groups, commands and
flags and the content of `--help` are unchanged except for the new `--json` flag and the `catalog` command.

---

## ADR-040: Project manifest and pinned versions

**Date:** 2026-10-15
**Status:** Accepted — amended by ADR-042 (collection command entries), ADR-046 (names and kinds of options of data commands from the catalog) and ADR-054 (`root` instead of `output_dir`, projects store-only); partly superseded by ADR-044 (D2: the name `project_status`); amends ADR-039 (the data command sets `_task` for `project add`); erratum 2: `project download --force` repairs a corrupted pinned version (E2E test 0.8.0)

**Context:** The versioned store (ADR-036) is shared by many
projects, and the standard path points to the newest local version, so
after the next download a project loses the information about which bytes it used.
The `kartograf-meta/1` sidecar is an immutable description of a file's provenance,
not a list of the projects that used it (SCOPE 3.3). Subproject 2 of the roadmap
(project manifest) is included in 0.8.0; the user gave a free hand regarding
architecture (2026-10-15). The store and the project directory may lie
on a network share without byte-range locks - so an SQLite database is ruled out.

**Options:**
- A) A JSON file in the project directory: tasks (group command + data options)
  and pinned file versions with SHA-256; CLI group `project`.
- B) An SQLite database of projects and files in the store: locks on the share,
  a second source of truth next to the sidecars.
- C) A copy of the data in the project directory and a list of commands: duplicates, no
  proof of version identity.
- D) Project entries in the version sidecars: violates the immutability of the sidecar.

**Decision:** A. Details and rejected variants (M1-M12):
`docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`.
- D1. File `kartograf-project.json`, schema `kartograf-project/1`,
  English keys, strict validation: `output_dir` (one store
  from `init --output`; a relative path is stored relative to the project
  directory) and `tasks[]`: `name`, `command` (a data command of a group
  of ADR-039), `options` (library function arguments in JSON form),
  `pinned_at`, `kartograf_version`, `geometry_sha256`, `files[]`
  (`role`, `unit`, `path`, `version`, `label`, `sha256`, `size_bytes`).
- D2. CLI `kartograf project init|add|remove|download|status|verify`,
  `--project KATALOG` defaults to the current directory; `add NAZWA <group>
  <command> [opcje]` accepts a group command in its grammar; modes as
  in the groups: `download --check-updates|--upgrade|--force`. API:
  `init_project`, `open_project`, `add_project_task`,
  `remove_project_task`, `download_project`, `check_project`,
  `project_status`, `verify_project`.
- D3. A task is pinned as a whole, only after full success.
  `download` without a mode does not change pins: it downloads tasks not yet downloaded,
  and restores missing pinned files only with an identical SHA-256.
  Re-pinning only with `--upgrade`/`--force`, always of the whole task.
- D4. `check_project` compares the pin with the `check_*` plan of the command
  via `PlanItem.local_sha256`; source signals are interpreted solely by
  the logic of ADR-036.
- D5. `verify` = full SHA-256 and consistency with the version sidecar; `status`
  = existence and size, without network access.
- D6. No `project availability`: the availability report (plan A/B) serves
  to choose a variant before `project add`; the report is not a data file.
- D7. Atomic write (`os.replace`) under a short directory lock
  (`mkdir`), merging per task; no SQLite and no byte-range locks;
  project operations by default without the metadata cache.
- D8. One entry per data command in `kartograf/project/commands.py`
  and `_task` in the command parser (amending ADR-039): a new product
  in an existing command does not change the project, a new group (plans C-E)
  adds entries.

**Consequences:** One file per project is the source of the
project -> data link; an index of "which projects use a file" can be built
locally from the manifests, without changing the sidecars. Relocating a project
requires preserving the relative location of the store or correcting a single
`output_dir`. Restoring bytes that the source changed or withdrew
requires a copy of the store (with sidecars); a task without an explicit variant
(e.g. without `--year`) is restored without a copy only up to the publication of newer
data. The project file system must support atomic `mkdir`
and `rename`; the store still requires hard links (ADR-036). Every
new data command requires an entry in the project table and `_task` (a
consistency test). Implementation:
`docs/superpowers/plans/2026-10-15-manifest-projektu.md`.

**Erratum 1 (2026-10-18, ADR-046 D4):** `_task` in the command parser was replaced by the parameters
`task=True` of the command declaration in the catalog (`Command.task_options`); `TaskCommand.options`
comes from the catalog, and `project add` parses the command through `parse_command`. D8 still
applies (one `COMMANDS` entry per data command). The option keys of new manifests have
the declaration order (`country` right after `product`).

**Erratum 2 (2026-10-19, E2E test 0.8.0):** `project download --force`
repairs versions corrupted according to `verify` (different size, SHA-256, sidecar):
before downloading it sets aside the data and sidecar into a hidden directory
`.<label>_<sha8>.corrupt-<time>` next to the version (nothing is deleted;
the scan and `list_versions` skip hidden directories), after downloading the same
bytes return under the pinned version (`odtworzono`, manifest unchanged),
different content at the source re-pins the task like any `--force`. Direct
data commands (`elevation download --force` etc.) still do not overwrite
and do not repair (`commit_version` treats the same SHA from the sidecar as the
same content); repair at that level would require changing the
`kartograf-download/1` documents - a separate decision.

---

## ADR-041: Product variant registry, WFS sheet index for NMT/NMPT and availability report

**Date:** 2026-10-15
**Status:** Accepted — amended by ADR-043 (NMT 100 m in the variant registry without a vertical CRS; 8-part PL-1992 sheet codes - closes Limitations, erratum 4) and ADR-047 (`full_m2`, `sheet_records`, `campaign_coverage`); errata 1-3: completion of plan A, CZ variants (plan B), completion of plan B; erratum 5: availability: country envelope, area without land (`no_land`), `--min-density` error (E2E test 0.8.0)

**Context:** The GUGiK 2025 sheet indexes have NMT only in 0.5 m and 5 m,
and NMPT in 73% in 0.5 m; Kartograf knew only NMT 1 m and 5 m and NMPT 1 m,
so new flights were invisible (the 0.5 m gap, spec 1). Resolutions
and vertical CRSs were hard-coded in 7 places (constants `("1m", "5m")`
in `options.py`, the NMT/NMPT providers, `FileStorage`, the cutout, `area.py`
and the CLI; the rule "5m only EVRF2007" three times - backlog A5-4). A full
inventory of the WFS sheet indexes on 2026-10-15 showed `.asc` grids at 0.15;
0.5; 0.6; 1; 5 and 10 m and archives (XYZ, ASCII NMT, TBD, TIN, TTN, GRD,
DXF, DGN); the WMS sheet index has no 10 m, and WFS is a superset of WMS for
grids. The same sheet has files in two formats in WFS (18,003 layer-sheet
pairs of NMT EVRF2007, 87,100 NMT KRON86). The availability report
(spec 4, K3/K4) needs one index and one list of variants,
shared with downloading.

**Options:**
- A) A `ProductVariant` registry in the source descriptors as the only source
  of variants; NMT/NMPT sheet index from WFS for downloading and the report.
- B) Per-module lists of constants (the existing state) extended with the new
  resolutions.
- C) Downloading sheets via the WMS sheet index (as before), report from WFS.

**Decision:** A. Details: spec
`docs/superpowers/specs/2026-10-13-katalog-produktow-design.md` (K1-K4,
sections 3-4), measurements `docs/research/2026-10-15-plan-a-b/raport.md`, plan
`docs/superpowers/plans/2026-10-15-plan-a-elevation-pl.md` (implementation
decisions 1-13).
- R1. Registry `kartograf/sources/variants.py`: `ProductVariant` (source
  = descriptor key and `dataset` of the sidecar, product, country, resolution
  as `Decimal`, vertical CRS, format, horizontal CRSs, channel,
  `IndexRef` of the WFS service), variants in `SourceDescriptor.variants`, one
  descriptor per (product, format, resolution). The registry is the only
  source of resolutions, vertical CRSs and formats for CLI/API validation,
  `--help`, `list-sources`, the store segment and the sheet index record filter; no other
  module holds such a list. A new
  resolution or format = a registry entry.
- R2. K2 labels: `0.15m`, `0.5m`, `0.6m`, `1m`, `5m`, `10m` (archives
  also `15m`-`50m`) from a single `resolution_label` function; the flag accepts
  only the exact registry labels (`0,5m`, `50cm`, `0.50m` = error
  with the list of labels). The label is a segment component
  (`nmt/pl_{system}_0.5m_{vcrs}`); keys and segments of existing data
  (`pl.gugik.nmt_1m`, `pl.gugik.nmt_5m`, `pl.gugik.nmpt` = NMPT 1 m) are
  unchanged.
- R3. ASC grids in all resolutions of the WFS inventory: NMT
  EVRF2007 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; NMT KRON86 0.5m, 1m; NMPT
  EVRF2007 0.5m, 0.6m, 1m; NMPT KRON86 0.5m, 1m.
- R4. GUGiK archives (`--format` XYZ, ASCII-NMT, TBD, TIN, TTN, GRD, DXF,
  DGN) ARE registry variants and are downloaded as source files:
  original file + sidecar, versions in the store (ADR-036), without conversion,
  cutout or mosaic; the segment with a format token
  (`nmt/pl_{system}_tbd_25m_{vcrs}`), the extension from the `format` field
  of the record. `--format` selects the file format; without the flag = ASC grid - this is a
  product choice explicitly described in `--help` and the documentation, not a hidden
  data default. Archives lie on sheets of various scales, so the
  archive sheets for an area are determined by the sheet index (variant records
  intersecting the area, frame narrowed by 1 m, within the year range); `--scale`
  and `--cutout` with an archive = `Error:`.
- R5. NMT/NMPT sheet index from WFS
  (`kartograf/providers/pl/skorowidz_wfs.py`): the sheet channel
  `TransportKind.WFS` (`update_signal="index"`) instead of
  `WMS_SHEET_INDEX`; one `GetFeature` per sheet with `TYPENAMES`
  of all annual types of the service, further pages only via `next`,
  every failure = `DownloadError` ("wynik bylby niepelny"), never an empty
  result. Download and report read the same index with the same parser;
  LAZ uses the same transport; orthophoto stays on WMS.
- R6. Hard record filter (extension of ADR-028): the record format
  AND the URL path ending must indicate the variant format
  (`source_format`); an inconsistent record (e.g. grid format with URL `.xyz`,
  42 NMT 2019 records) is not downloaded.
- R7. WCS cutout (`--cutout`) only 1 m (`pl.gugik.nmt_1m`,
  `pl.gugik.nmpt`): GUGiK WCS gives a composition of flights, not a sheet by year
  (ADR-035); `--cutout` with another resolution = `Error:` before the network.
- R8. Availability report (`check_availability`, `kartograf elevation
  availability`): a combination = (year, horizontal CRS, label, vertical
  CRS, format) of a registry variant, LAZ = (year, horizontal CRS, vertical
  CRS); a combination is complete when the outlines of full sheets
  (`TAK`) according to the sheet index cover the area intersected with the PRG land (1 m
  grid); archives are combinations to download (format in the report,
  hint with `--format`); `Info:` only for records outside the registry
  (inconsistent, with an 8-component sheet code). The report does not download data.
- R9. Download hint in the report: a command to paste after
  `kartograf ` or after `kartograf project add NAME ` - without `--output`
  (ADR-040, manifest spec 4.10).

**Limitations:** 8-component sheet codes of the PL-1992 system (ASCII NMT 10 m - 215
sheets, 1678 ASC 1 m records) are outside `SheetParser`: they are not downloaded,
the report shows them as `Info:`; to be closed in plan E (E1 extends
`SheetParser`). The file signatures of the archives (ZIP, TTN, Intergraph GRD/DGN,
DXF) were checked on one sample per format.

**Consequences:** Breaking changes in 0.8.0 (plan decision 12, "What to do"
in the CHANGELOG): `--product nmpt` requires `--resolution`;
`GugikNmptProvider(..., resolution=)` without a default value;
`GugikProvider` and `GugikNmptProvider` accept labels and `format`
from the registry; removed without aliases: `kartograf.providers.pl.nmt_vertical_crs`,
`require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`,
`GugikProvider.SUPPORTED_RESOLUTIONS`/`SUPPORTED_VERTICAL_CRS`/
`SUPPORTED_VERTICAL_CRS_5M`/`WMS_INDEX_ENDPOINTS`/
`get_supported_resolutions`/`get_supported_vertical_crs_for_resolution`,
`GugikNmptProvider.SUPPORTED_RESOLUTIONS`/`WMS_INDEX_ENDPOINTS`,
`FileStorage.SUPPORTED_RESOLUTIONS`, `GugikLazProvider.WFS_ENDPOINTS`
(replacement: `kartograf.sources.variants.variants(...)`). Sidecars
of new NMT/NMPT sheets: `extra.source.index_url` = the WFS service address,
`extra.source.layer` = the WFS type (`SkorowidzNMT2025`); files and segments
of existing data unchanged, the sheet freshness signal is still `index`.
New report API: `check_availability`, `AvailabilityReport`,
`AvailabilityCombination`, `AvailabilityArea`. Plan B adds the CZ variants
(supplement to ADR-041).

**Rejected:**
- lists of constants per module (option B): every new resolution changes
  several modules, and the rules drift apart;
- labels `50cm` and `0_5m` (two units in one parameter; spec K2);
- archives outside downloading (plan recommendation before revision) - rejected
  by user decision 2026-10-15: archives are the only source of 15-50 m
  and of some vintages (e.g. Kraków 2018);
- WMS for downloading and WFS for the report (option C): two indexes may give
  different answers, and WMS has neither 10 m nor archives;
- a coverage threshold in the report: completeness is binary according to the outlines of `TAK`
  sheets, the report gives uncovered land in m2.

**Erratum 1 (2026-10-15, completion of plan A):**
- R5 clarified: the server paginates the response of several types
  inconsistently (repetitions and gaps, recording 2026-10-15), of one type consistently;
  a response of several types with the `next` attribute is rejected and each type is
  queried separately; an object repeated on a subsequent page = `DownloadError`.
- R6 corrected: 42 NMT EVRF2007 2019 records (campaign 72675, sheets
  N-33-69) have the grid format and file name `.xyz`, but AAIGrid inside
  (headers of all 42 files checked live 2026-10-15; 0.7.x
  downloaded them) - they are ASC grids: `FORMATS` accepts URL `.asc`
  and `.xyz` for ASC, the content after download is checked by `verify_file_format`. Inconsistent
  remain, among others, a grid format with an archive URL and an archive with a `.asc` URL.
- R8 clarified: the report's `Info:` has the code `index_unsupported` (records
  outside the registry: 8-component sheet codes, format inconsistent with the file); with `--sheet`
  the measurement skips the 1 m strip at the sheet frame (the frame from the sheet code differs
  from the GUGiK frame by centimetres), `--bbox`/`--geometry` are measured exactly;
  LAZ has an envelope like the LAZ download; `--country` is required only with `--bbox`/
  `--geometry`; the metadata cache holds the WFS types, area records
  with outlines and the land mask (a repeated report without network, `--force` skips the cache).
- Manifest (ADR-040): `elevation availability` does not set `_task`
  (`project add` rejects it); `COMMANDS["elevation download"]` has the option
  `format`; every report hint passes `project add` without network.
- Live E2E 2026-10-15 (`docs/research/2026-10-15-plan-a-e2e/raport.md`):
  grids 0.15m, 0.5m (NMT and NMPT, EVRF2007 and KRON86) and 0.6m downloaded
  with a pixel equal to the label; the Kraków and Pomerania reports consistent with the plan's
  measurements; CLI JSON = API; downloaded sheets = `sheets_full` of the combination; the LAZ
  report queries only WFS and PRG; the 1 m cutout byte-identical to the cutout from `develop`;
  the TBD 25 m archive downloaded, ZIP complete, rerun local.

**Erratum 2 (2026-10-15, plan B: CZ variants):**
- R1 for CZ: a registry row = a row of the plan B route table
  (`docs/superpowers/plans/2026-10-15-plan-b-elevation-cz.md`, decision 2):
  (product, resolution or model, vertical CRS, sheet system
  `sm5`/`tm33`) with the channel that serves it - a CUZK file
  (`DIRECT_FILES`, signal `http`) or an ImageServer with a local warp to
  the tile grid (`ARCGIS_IMAGE`, signal `none`). `ProductVariant.model`
  (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`; PL: `None`). Descriptors:
  `cz.cuzk.dmr5g` (NMT 2m), `cz.cuzk.dmr4g` (NMT 5m), `cz.cuzk.dmp1g`
  (NMPT 2m), `cz.cuzk.dmpok` (NMPT 0.5m) and `cz.cuzk.<model>_laz`; segments
  `nmt|nmpt/cz_<model>_<vcrs>`, `laz/cz_<model>_<vcrs>` (the model and vertical
  CRS determine the file - no horizontal CRS in the segment).
  A CZ cutout is not a row: it is the ImageServer channel of the descriptor.
- Routes: an SM5 sheet = an S-JTSK file (EPSG:5514, Bpv natively; EVRF2007 via
  the pinned Bpv->EVRF2007 operation); a TM33 tile in EVRF2007 = an ETRS89 file
  (EPSG:3045, EVRF2007 natively according to the CSW metadata of the datasets - without
  transformation, sidecar `vertical_crs = EPSG:5621` without a vertical operation);
  a TM33 tile in Bpv and every tile of a model without raster files (DMR 5G,
  DMP 1G: `*-TIFF` = 404) = ImageServer + warp (ADR-024). SM5 for 2m =
  `Error:` before the network. The channel is chosen by `channel_for(klucz, transport,
  uklad poziomy)`: the descriptor has one file channel per system.
- CZ LAZ: `--model` (API `model=`) is required for `--product laz` in CZ,
  with PL or another product = `Error:`. Files only in the pairs S-JTSK + Bpv
  (SM5 sheets) and ETRS89 + EVRF2007 (TM33 tiles): the vertical CRS selects
  the files of the area, a wrong pair with a sheet code = `Error:` before the network;
  the point cloud without transformation (file 1:1 from the ZIP).
- CZ report (`check_availability(country="cz"|"auto")`): sheets of the index
  `KladyMapovychListu` intersecting the area (SM5 `PODIL > 0`, TM33
  `IN_CZ`) and `HEAD` of each file: 200 = a sheet with a file, 404 = no
  file (`sheets_missing`), another error = `DownloadError`; `published` =
  `Last-Modified`, `size_bytes` = `Content-Length`; without flight years (CUZK
  does not publish them). Models without raster files = `Info:`
  `cz_service_only`.
- Rejected: the backup endpoint `dmp` (alias `dmp_obrazova_korelace`:
  the same description and catalogue); ATOM as a signal and report source (`<updated>`
  = `Last-Modified`, feed 24-31 MB); a new flag `--sheet-system` for CZ
  LAZ (the horizontal CRS follows from the vertical CRS of the files); transformation of point
  clouds (changes source data, no pinned 3D operation); a second track
  for choosing the raster model (`--model` for NMT/NMPT - rasters are selected by
  `--resolution`).

**Erratum 3 (2026-10-16, completion of plan B):**
- CZ raster route: `CuzkRasterProvider.route(sheet=None) -> CzRasterRoute`
  (channel, result CRS, pinned operations; `None` = cutout) - the sheet and
  cutout paths write the sidecar from the route, the vertical operation is created in `route()`
  before the network. The raster variant is chosen by `find_cz_variant`/`cz_variant_error`,
  LAZ by `find_cz_laz_variant`/`cz_laz_error` (`sources/variants.py`;
  `find_variant` stays for PL); the file signal is `file_signal(sheet)`.
- Area file sheets - one rule for LAZ download and the report
  (`SheetIndex.file_sheets(system, area)`): SM5 with `PODIL > 0`, TM33 - tiles
  of layer 26 (`IN_CZ` has a single value `CZ` in the index, the index has no tiles outside CZ);
  a sheet touching the area at an edge or overlapping it by less than 1 cm is dropped
  (ArcGIS coordinate noise approx. 1 mm).
- `--country auto` with LAZ: PL tiles from WFS and CZ sheets according to the vertical CRS,
  a common `extra.parent_request`; PL-only LAZ flags (`--year`,
  `--min-year`, `--max-year`, `--all-campaigns`, `--min-density`) narrow
  `auto` to PL (`Info:`); an area reaching CZ without `--model` = `Error:`
  with the list of models and `--country pl`.
- CZ report: `HEAD` in parallel (8 threads), cache `head|<url>`
  and `cz-sheets|...` like the sheet index records (`--force` skips reading);
  `uncovered_m2` is measured in the CRS of the reported area (the rectangle
  of the CZ part in EPSG:5514, a sheet code - its frame; the frame of a TM33 tile transferred
  by vertices with the pinned operation), so it does not exceed `area_m2`;
  `size_bytes = None` when no sheet has a file; `Info:`
  `cz_service_only` only for the CZ part with index sheets. `auto`:
  an unchecked part with the second one checked = `Warning:` `check_failed`,
  `ok=False` (CLI code 1), both = error; year flags: `cz` = error, `auto` =
  narrowing to PL. CZ hints: raster - a command per sheet, LAZ -
  one area command with `--model`; each passes
  `validate_data_request` and `project add` without network.
- Existing TM33 DMR 4G EVRF2007 tiles from a warp: the default mode keeps the
  local version (`Info:` - unchecked), `--force` downloads the CUZK file
  as a new version and repoints the hard link.
- Live E2E 2026-10-16 (`docs/research/2026-10-16-plan-b-e2e/raport.md`):
  DMP OK SM5 5000x4000 px 0.5 m; native TM33 tiles DMP OK and DMR 4G
  EVRF2007 with values 1:1 from the CUZK ZIP; DMR 4G TM33 natively versus
  the former warp on the same grid: median |difference| 0.06 m, p95 0.39 m,
  max. 1.66 m; the DMP 1G 2 m cutout geometrically consistent with the native DMP OK
  (below 1/4 pixel); CZ LAZ of a sheet and a tile byte-identical to the ZIP members;
  the choice of area sheets = the index after dropping the touching ones; the CZ report
  and `auto` without file `GET`, `--json` = API.

**Erratum 4 (2026-10-16, documentation review before the 0.8.0 release):** The limitation about 8-component PL-1992 sheet codes has been outdated since plan E (E1, ADR-043 D10): `SheetParser` accepts 8-component sheet codes (label `1:5000`), `--sheet` downloads ASCII NMT 10 m and ASC 1 m sheets with such codes, and the availability report gives them in the download hint instead of in `Info:` (`index_unsupported`).

**Erratum 5 (2026-10-19, E2E test of 0.8.0):** `elevation availability` with
`--country pl|cz` and `--bbox`/`--geometry` checks the country envelope as the
download does (`outside_country`, code 2, `option=bbox|geometry`); a PL sheet code and
`auto` unchanged. An area without PL land: `complete` unchanged, `Info`
`no_land` (ADR-047 erratum 2). An empty LAZ tile selection after `--min-density`
points to the flag, the number of rejected tiles and the highest nominal
density (`LazTileSelection.below_density`). `--bbox` outside the EPSG:4326 range or
with zero area is rejected by the common `validate_request_bbox` (code 2,
`option=bbox`). A point (or a line parallel to an axis) in `--geometry` selects
the sheets, units and pixels in which it lies; the cutout, LAZ tiles, `soil hsg`
and this report work on an area and reject it (`require_geometry_area`,
`option=geometry`; round 3 of the 0.8.0 E2E test).

---

## ADR-042: Channel engines (unit_package, feature_bbox, atom_files) and plan C/D data

**Data:** 2026-10-15
**Status:** Accepted — partly superseded by ADR-043 (D1: collection channel capability unique in the descriptor) and ADR-044 (D9: `landcover` keeps `--source`; erratum 5: orthophoto cutout API names; D6: explicit timeout of the collection call); amended by ADR-043 (sheet, tile and KU units, index record and the `index` signal, OGC API Features, channel choice by option values); partly supersedes ADR-036 (D27: orthophoto cutout in the store; erratum 2 of ADR-036); amends ADR-015 (GPKG writing via pyogrio; envelope reading unchanged), ADR-034 (orthophoto cutout chunks; erratum 1 of ADR-034), ADR-036 (D23 between releases, unit slots), ADR-039 (groups `boundaries`, `cadastre`, `models3d`, `hydro`) and ADR-040 (project command entries); errata 1-5: D5 and D12-D17 according to the plan D code (ATOM index, HY-NET area 2 layers, ZABAGED and RUIAN, CZ orthophoto, orthophoto cutout); erratum 6: an image cutout entirely 0,0,0 = `NoCoverageError` without a version (live test 0.8.0); erratum 7: `--country auto` in collections: partial success with code 0, a country without units does not abort the task, KU cache (E2E test 0.8.0)

**Context:** The catalog spec (K5-K7) requires that a product from the report be
a descriptor entry and a channel configuration, not a provider. Plans C and D
bring packages per administrative unit (BDOT10k archive, 3D models,
PRG, EGiB), features for an area from WFS and ArcGIS REST (PRG, EGiB, RUIAN,
HY-NET, ZABAGED) and files pointed to by the CUZK ATOM feed (orthophoto, ZABAGED
country). The reconnaissance of 2026-10-15 showed: wrong `next` links in both
WFS servers, a duplicate feature at the MapServer page boundary, axis order
consistent with EPSG at both providers, the time-varying EGiB field `DATA` (data
state date of the county), multipart EGiB features as repeated
geometries, URLs with a year/date in the name (only from the feed).
Curves (`CurvePolygon`) from the EGiB sample of 2026-10-13 did not occur in the data
(measurement of 2026-10-15: only linear polygons).

**Options considered:**
- A) Provider per product (the `providers/pl/*.py` pattern).
- B) Generic engines driven by typed channel parameters
  in the descriptor + one collection orchestrator on the version store.
- C) A single generic "download URL" without typed parameters.

**Decision:** B.
- D1. `AccessChannel.params: UnitPackageParams | FeatureBBoxParams |
  AtomFilesParams | WcsCutoutParams | None` (data without IO, immutable;
  the last two in plan D). The required ZIP members are a property of the variant
  (`PackageVariant.members`: the GML and SHP packages of one channel differ).
  Engines: `transport/unit_package.py`, `transport/feature_bbox.py`,
  `transport/atom.py` (plan D), GPKG writing `transform/gpkg.py`,
  orchestration `download/collections.py`. A new product = a descriptor
  with channel parameters (+ a choice in the CLI). A collection channel has a capability
  unique in its descriptor (sidecar channel choice).
- D2. The kind of selection determines the channel: `teryt` (2 digits = voivodeship (Polish województwo), 4 = county)
  -> `unit_package` of that unit; area (`bbox`/`sheet`/`geometry`) ->
  `feature_bbox`, and when the product does not have it - counties from PRG and a package
  per county; `whole_country` -> national file (`unit_package` of the unit
  `country` or `atom_files`) only explicitly, with the size from `HEAD`/
  the feed in a `Notice` before the transfer (K7). Exactly one selection; the variant
  (year, format, LoD, level, national file CRS) is required when the source
  publishes more than one (K8), and with a single one only a value equal to the
  published one is accepted. The file CRS is chosen by `--horizontal-crs` (ADR-038; API
  `horizontal_crs`): required when the channel has several CRSs (CUZK national
  files 5514/3045); the area result is always in the native CRS of the service.
- D3. Completeness of `feature_bbox` from the count, not from links: WFS
  `RESULTTYPE=hits`, ArcGIS `returnCountOnly` -> N; pages
  `STARTINDEX`/`resultOffset` (ArcGIS with `orderByFields`) from 0 every
  `page_size`; `next` ignored (MapServer drops it on middle
  pages, GeoServer gives it on the last one). Page loop: ends when
  there are N unique identifiers; beyond N planned positions only
  as long as the previous page was full and added new identifiers
  (MapServer repeats a feature at the page boundary, so the last unique
  feature may lie beyond position N-1: PRG A03, `hits` 39, `COUNT=13` -
  the 39th feature at `STARTINDEX=39`); a short page with fewer than N
  unique, a page beyond N without new identifiers or more than N
  unique = `DownloadError`. Dedupe by the channel's identifier field
  (an identical duplicate skipped, a differing one = `DownloadError`);
  `numberMatched="unknown"` in the `hits` response = `DownloadError`; HTML,
  `ExceptionReport`, JSON `error` with HTTP 200 = `DownloadError`. N = 0
  in all layers = `NoCoverageError` (no file); an empty layer
  next to non-empty ones = a layer with a schema without features. Service metadata
  (`GetCapabilities`, `DescribeFeatureType`, ArcGIS layer fields) are
  fetched fresh once per download, without a metadata cache: the type check
  and DefaultCRS concern the state of the service at the time of download, and using a local
  version sends no request.
- D4. The BBOX axis order is a channel parameter with a test on a real
  response: GUGiK `urn:...:EPSG::2180` = N,E, CUZK EPSG:5514 = X,Y
  (both consistent with EPSG); swapping gives an empty result without an error.
- D5. The `feature_bbox` result: one GPKG in the native CRS of the service
  (DefaultCRS), full geometries of the features intersecting the area (without
  clipping; a multipart feature - repeated `<ms:geom>` of EGiB -
  in full thanks to `GML_FETCH_ALL_GEOMETRIES=YES`), layer for layer
  of the source; bytes deterministic within one GDAL version (features by
  identifier, schema from service metadata - GML read with the `XSD=` of
  the `DescribeFeatureType` response, `WRITE_GFS=NO`, `DOWNLOAD_SCHEMA=NO`
  - and a fixed `OGR_CURRENT_DATE`). Fields that vary in time independently of
  the features (`drop_fields`; EGiB `DATA` = data state date of the county
  in the aggregate service, different between counties and refreshed even daily)
  are outside the GPKG - otherwise every download would be a new version - and their values
  go in the sidecar `extra.source.dropped_fields` (field -> values). The GPKG is
  assembled on a local disk (SQLite does not write on a network
  volume), then store staging. A new dependency `pyogrio` (vector
  GDAL).
- D6. Store and signals: every file through `FileSlot` and
  `use_local`/`store_file`/`fetch_version`/`inspect_version`; signal =
  `update_signal` of the channel: GUGiK packages and all WFS/REST results
  `none`, CUZK files `http`, files from the ATOM feed `metadata`. Label:
  products with a release in the segment (BDOT10k vintage, 3D model year) -
  the release (`label_source="edition"`), the others `downloaded`.
- D7. D23 between releases: `FileSlot.related_roots` - when the slot has
  no version with that sha256, it is searched for in related slots (other releases
  of this product, format and unit); a hit = a hard link to
  existing data, status `relabeled`, `same_as` = the label of the
  found version (spec 9.3: identical vintages without a duplicate).
- D8. The `data/` layout (extension of rule 8): `<group>/<country>_<source>
  [_<tokens>]/{teryt/<T>|bbox/<coords>|country/<code>}<ext>`; `coords`
  in the native CRS (`.10g`), tokens `[a-z0-9.-]`, national file
  `country/pl` or `country/cz`; versions in `<segment>/versions/<the same
  hierarchy>/`. Tokens = content variant (level, LoD, vintage): the area result
  (always GPKG in the native CRS) without a format token; a package
  and a national file with the source format token when the product has several formats
  or also an area result, and when the source publishes a file in several
  CRSs - also with the EPSG code (clarification of the spec 7 examples:
  `boundaries/pl_prg_<level>/bbox/`, `landcover/cz_zabaged/bbox/`,
  `landcover/cz_zabaged_gpkg_5514/country/cz.zip`,
  `models3d/pl_buildings_lod1_<year>/teryt/` without a format - one format,
  no area result). Different contents never share a slot.
- D9. CLI (amendment to ADR-039): groups `boundaries`, `cadastre`,
  `models3d` (plan C) and `hydro` (plan D), a module per group with `download`
  and `list-sources`; selection `--product` + `--country pl|cz|auto` (like
  `elevation`/`imagery`; `landcover` keeps `--source`); `--teryt`,
  `--whole-country`, `--level` (boundaries for an area; national names:
  PL `wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`, CZ
  `kraj|okres|obec|katastralni-uzemi`; with `--country auto` in the per-country
  syntax `pl=gmina,cz=obec` like `--resolution`), `--lod 1|2`, `--year`,
  `--horizontal-crs` (only where the national file has several CRSs; plan D:
  `landcover --source zabaged`). Products: `admin` (PRG, RUIAN), `map`
  (EGiB - cadastral map), `buildings` (3D models), `network`
  (HY-NET). New products without `--layers` (fixed content). The parser
  of every `download` command sets `_handler` and `_task` (ADR-040).
- D10. Library: `download_collection`/`check_collection`
  (`CollectionReport`: `files` with `UnitFile`, `failed` with `UnitFailure`,
  `stale`, `notices`, `ok`), validation without network
  `validate_collection_request`, plan track `collection`. `landcover
  download` stays `LandCoverManager` (ADR-039 D8) and delegates the BDOT10k
  archive and ZABAGED to the collection engines.
- D11. BDOT10k archive: `--year 2014..2025` with the required `--format
  GML|SHP` (no GPKG; with `--year`, `GPKG`, `--layers`,
  `--keep-raw` are rejected), ZIP 1:1, `landcover/pl_bdot10k_<format>_<year>/teryt/<T>.zip`,
  label = year, `none`, D7 for identical vintages; a 404 for a county
  (TERYT change, no package) = `NoCoverageError` of that county.
- D12 (plan D). `atom_files`: service ATOM feed -> dataset feed -> `alternate`
  link with `length`; the entry is selected by a regular expression on the dataset
  id (named groups) or the sole dataset + CRS category; release
  (`metadata`) from the entry's `<updated>`; the service feed index in MetadataCache
  refreshed by conditional GET (ETag).
- D13 (plan D). CZ orthophoto: `imagery download --product orto
  --country cz` (sheet or area -> SM5 sheets from the index), ZIP
  members without pixel conversion as `<sheet_code>.jpg`, `<sheet_code>.jgw` (S-JTSK),
  `<sheet_code>.TM33N.jgw`, `<sheet_code>.TM34N.jgw`, each file versioned
  in `orto/cz_sjtsk/<SM5 hierarchy>/`; label `<year>_<updated>`,
  signal `metadata`. The SM5 sheet code pattern accepts 2 letters (As).
- D14 (plan D). PL orthophoto cutout from WCS in the store (partly
  supersedes ADR-036 D27): `imagery download --product orto --cutout
  --horizontal-crs EPSG:2180 --coverage standard|high --resolution
  0.1m|0.25m|0.5m|1m`, `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`,
  `none`, without a land mask, chunks of up to 4 native Mpx, configuration
  in the `WcsCutoutParams` of the WCS channel; `GugikOrtoProvider.download_bbox`
  stays a raw API outside the store.
- D15 (plan D). ZABAGED: `landcover download --source zabaged`; area
  -> GPKG EPSG:5514 from 22 land-cover and hydrography REST layers (names =
  ASCII codes of the layer names), `--whole-country --horizontal-crs
  EPSG:5514|EPSG:3045` -> national `ZABAGED-<code>-gpkg-<date>.zip`
  from the feed (`metadata`); without mapping classes to BDOT10k codes.
- D16 (plan D). Group `hydro`, `--product network` (HY-NET): area ->
  GPKG EPSG:5514 (3 WFS types), `--whole-country` -> `HY-NET.zip`
  (EPSG:3045 according to the feed, `http`).
- D17 (plan D). RUIAN: `boundaries --product admin --country cz`; area
  -> REST layers 17/15/12/7, `--whole-country` -> `shp/stat/epsg-5514/1.zip`
  (`http`).

**Consequences:** Further plan E products enter as descriptors
with parameters (a new protocol, e.g. OGC API Features, extends
`FeatureBBoxParams.protocol` together with the first product). `pyogrio`
is added to the dependencies (approx. 100 MB of wheel with GDAL next to the GDAL of `rasterio`).
A WFS/REST result is a snapshot without a signal: `--check-updates` reports
`unverifiable`, new content comes only with `--force`. National files may
have a different CRS than the area result (HY-NET 3045 vs 5514) - the sidecar gives
the actual one. Details and measurements: `docs/research/2026-10-15-plan-c-d/raport.md`,
plans `docs/superpowers/plans/2026-10-15-plan-c-*.md`, `...-plan-d-*.md`.

**Erratum 1 (2026-10-16, plan D Task 2, D12):** the ATOM service feed index
lies in `MetadataCache` (table `atom_cache`, key = feed + `entry_pattern`)
together with the feed `ETag`: within the TTL (7 days) without a request; an older index and
`--upgrade` and `--check-updates` (`refresh`) send a conditional GET
(`If-None-Match`; 304 = index unchanged). A key missing from the cached
index or a 404 of the dataset feed = ONE index refresh (a stale
cache does not hide a new vintage). The dataset feed (approx. 1.4 KB) is always read fresh -
its entry carries the release. The version label = the `updated` date
of the FILE entry in the dataset feed, preceded by the `year` group of the pattern,
when it has one (`2024_2025-02-06` orthophoto, `2026-10-04` ZABAGED). The service feed
is read as a stream (ORTOFOTO: 23.7 MB, 16,301 entries), read limit
120 s, dataset feed 60 s. A key outside the feed = `NoCoverageError`;
HTML instead of a feed, an entry without exactly one `alternate` link, several
files without a resolution, a size different from the feed `length` or
`Content-Length` = `DownloadError`; a CRS outside the feed category =
`ValidationError` without network. ZIP members (`AtomFilesParams.members`) are
copied 1:1, longest suffix first (`.TM33N.jgw` before `.jgw`).

**Erratum 2 (2026-10-16, plan D Task 3 and live test, D3, D5, D16):**
the HY-NET area result has 2 layers, `WatercourseLink` and `HydroNode` (not
3 WFS types): `WatercourseSeparatedCrossing` has no geometry in GML (it is
a relation of two `net:element` segments), and GeoServer for a query with BBOX
returns `hits` 0, although the pages return objects (30 x 30 km: 0 versus 4,
100 x 100 km: 0 versus 24) - the completeness of D3 cannot be verified.
The crossings are in the national file (`--whole-country`). The GPKG layer codes and
names = WFS type names. The HY-NET `DescribeFeatureType` is only an
`xsd:include` of a remote INSPIRE schema: such an XSD does not reach GDAL
(D5 "schema from the service metadata" does not apply to this service) - fields are
read from the content of each page, the layer gets the union of the page fields
in order of first occurrence (missing field = null, one field with two
types = `DownloadError`), so the schema depends on the content: the same type may
have different fields in another area (a page with a single node has no
`hydroNodeCategory`). An empty layer without an XSD schema (0 objects of the type)
= a layer with only the `gml_id` field (geometry `Unknown`), not a schema without
objects from D3. The service redirects the default `User-Agent` of curl (302) to a
PDF with the terms; Kartograf sends `kartograf/<version>`. National file:
ZIP 1:1 with a required `.gpkg` member (`hydro/cz_hynet_gpkg/country/cz.zip`,
approx. 194 MB), only EPSG:3045 (other `horizontal_crs` = `ValidationError`).
CZ-only product: `--country pl` = error, `auto` narrows to CZ
(`auto_narrowed_to_cz`), `--level` = error (fixed content).

**Erratum 3 (2026-10-16, plan D Task 3, D10, D15, D17):** ZABAGED: 22
area layers (ids and codes in `registry.py::_ZABAGED_LAYERS`; lines 93
`vodni_tok` and 112 `brehova_cara`, the rest polygons), page 2000,
`orderByFields=OBJECTID`, id `fid_zbg`. The GPKG layer description
(`gpkg_contents.description`) = the ArcGIS layer name as spelled by the service
with the id (`Vodní tok (93)`, RUIAN `Obec (12)`). The national file = ZIP 1:1 (member
`ZABAGED_RESULTS.gpkg`) in `landcover/cz_zabaged_gpkg_<5514|3045>/country/cz.zip`
with full-database layers under CUZK names (e.g. `VodniPlocha_c`), different from the
codes of the area result; the size from the feed `length` in the `Notice`
`whole_country_size` before the transfer (release 2026-10-04: 5.8 GB
EPSG:5514, 6.7 GB EPSG:3045). `LandCoverManager(output_dir, "zabaged")`
(`COLLECTION_SOURCES`, no provider class): `teryt`, `format`, `layers`,
`keep_raw`, `year` = `ValidationError` with the source name (also
in `validate_request`), `sheet` = error (CZ area: `bbox`/`geometry`),
`horizontal_crs` with an area = error (the result is always EPSG:5514); a
download error is an exception, not a `failed` entry (one file per query,
like CORINE). RUIAN: `kraj`=17 `VyssiUzemneSamospravnyCelek`, `okres`=15
`Okres`, `obec`=12 `Obec`, `katastralni-uzemi`=7 `KatastralniUzemi`
(GPKG layer names), page 1000, `orderByFields=objectid`, id `kod`;
national file `boundaries/cz_ruian_shp/country/cz.zip` (ZIP 1:1, required
`.shp` member, approx. 253 MB, `http`). Under `auto` the level is per country
(`{"pl": "gmina", "cz": "obec"}`; a value unavailable in one
country = error with the hint `--level pl=<level>,cz=<level>`);
`--teryt` with `--country cz` and a CZ sheet code as the collection area = error.
The GPKG write (D5) keeps the whole layer in memory - a risk for very
large areas.

**Erratum 4 (2026-10-16, plan D Task 4, D13):** CZ orthophoto is only the
current vintage of a sheet (archival CUZK orthophotos are paid): with
`--country cz` the flags `--year`, `--min-year`, `--max-year`,
`--all-campaigns`, `--full-sheet`, `--sheet-system`, `--scale`,
`--vertical-crs` and `--format` = `ValidationError` (under `auto` the campaign
and sheet flags apply to the PL part); tile TM33 as `--sheet` =
error with a hint to SM5, `--cutout` with CZ = error. An area under `auto` yields
PL sheets and CZ SM5 sheets (previously `auto_narrowed_to_pl` - the orthophoto had
no CZ source); `--resolution` with orthophoto without `--cutout` = error for both
countries (the sheet pixel results from the source). JPEG sidecar: `horizontal_crs`
EPSG:5514 and `extra.world_files` = `{".jgw": "EPSG:5514", ".TM33N.jgw":
"EPSG:3045", ".TM34N.jgw": "EPSG:3046"}` (measurement 2026-10-16 on CTES96,
CTES86 and AS91: the origin of the TM files = the S-JTSK origin converted to
EPSG:3045/3046 with an accuracy of 0.03 m); the sidecar of each JGW has
the `horizontal_crs` of its CRS. A JGW does not carry a CRS - in GIS the user
assigns it (JPEG + `.jgw` = EPSG:5514). One release check per
sheet (one `resolve_atom_file`, failure remembered): the four files
share the result, `check_failed` once per sheet. Write order `.jgw`,
`.TM33N.jgw`, `.TM34N.jgw`, `.jpg`: a JPEG version always has JGW files, a file
with a failed write has no version (the next run adds it).
API: `download_cz_orto_sheet`/`check_cz_orto_sheet` (`CzOrtoResult`),
plan track `cz_orto`, unit = sheet code.

**Erratum 5 (2026-10-16, plan D Task 5, D14):** orthophoto cutout
only in EPSG:2180 (the image is not resampled locally;
`--horizontal-crs` required, any other value = error), `--coverage`
and `--resolution` required with no default values (choices from the WCS channels
of the registry), RGB composition only, no year selection (server
composition). The range is aligned OUTWARD to a multiple of the pixel, and the result
is checked (size, step, NW corner, 3 uint8 bands, EPSG:2180): a different
grid = `DownloadError` without a version. An odd number of 0.25 m pixels
is a fraction of the 0.1 m coverage pixels - the server responds with a wrong grid or
HTTP 400 - therefore chunks have even sizes. The GeoTIFF chunk budget
is counted in coverage pixels (like ASC): 4 Mpx = 200 x 200 m
regardless of the result pixel; the chunk read limit is 300 s (measurement
2026-10-15: 4 Mpx Standard 64 s, 2000 x 2000 px at `SCALEFACTOR=0.4`
176 s). Stitched chunks are NOT bit-for-bit equal to a single query
(erratum 1 of ADR-034). High outside the 10 cm pixel areas responds with HTTP 200
with a 0,0,0 image: the version is created with `extra.all_nodata: true` and a `Notice`
`all_nodata` (warning); there is no PRG land mask. The download checks
disk space (2 x the result size) and announces `cutout_size` for
more than one query or >= 1 GiB. Sidecar: `resolution`
(from the descriptor) = `null`, the pixel and variant in `request.resolution`
and `request.coverage`, `extra.source` = the actual endpoint, coverage id,
format, `scalefactor` (pixel other than 0.1 m) and `composition: server`;
the CRS fields from the first `bbox_raster` channel (Standard and High have
the same). The name `pl.gugik.orto`: `Ortofotomapa (arkusze wg kampanii; wycinek
WCS Standard i High)`. Under `auto`, `--coverage` and `--resolution` of orthophoto
narrow the task to PL (`auto_narrowed_to_pl`); an area only in CZ =
error. API: `download_orto_cutout`/`check_orto_cutout`
(`OrtoCutoutResult`), plan track `pl_cutout`.

**Erratum 6 (2026-10-17, live test of release 0.8.0, coordinator
decision):** the sentence of erratum 5 "High outside the 10 cm pixel areas
responds with HTTP 200 with a 0,0,0 image: the version is created with `extra.all_nodata:
true` and a `Notice` `all_nodata`" is no longer in force. An image cutout that is entirely 0,0,0
(High orthophoto outside the 10 cm flights, Standard without an orthophoto, true orthophoto
ADR-043 E1 outside the selected cities) ends with `NoCoverageError` BEFORE
the version is written - like an NMT/NMPT cutout outside land (PRG mask): staging
removed, in `download_data` a PL `no_coverage` failure, CLI `Error:` code 1,
content with the cause and the channel remedy (for High `--coverage standard`).
The service does not publish the extent of the cutout, so the image is downloaded
and checked before the version is written; the image cutout sidecar has no
`extra.all_nodata`, and `ImageCutoutResult.notices` has `all_nodata`. The API names
from erratum 5 were replaced by ADR-044 D3 (`download_image_cutout`/
`check_image_cutout`, `ImageCutoutResult`).

**Erratum 7 (2026-10-19, E2E test 0.8.0, collection cutout):** the
partial success rule of `--country auto` (code 0 + `Warning:`
`auto_partial_success`; code 1 for an explicit country and for failure of all
countries, ADR-023 points 4-5) also covers collections (`download_collection`,
the shared `download.area.emit_partial_success`). A country in which the area
has no units (RUIAN KU, PRG counties, sheets, tiles) or the query for them
failed is an error of that country (`UnitFailure` of the country, `kind` `no_coverage`
or `download`), not an abort of the task; a single country raises as before,
no units in all countries is a single `NoCoverageError`/
`DownloadError` with the texts of both. KU by RUIAN for an area (also an empty
response) is in `index_area_cache` (TTL 7 days; `--force`, `--upgrade`
and `--check-updates` query the service).

---

## ADR-043: Plan E: unit, sheet and national products on engines C/D

**Data:** 2026-10-16
**Status:** Accepted; partly supersedes ADR-042 (D1: the collection channel capability unique in the descriptor); amended by ADR-044 (D6: channel limit instead of an explicit call timeout); partly superseded by ADR-044 (D1 and erratum 3: CUZK sheet, tile and national-file theme slots - D7 ADR-044); amends ADR-042 (sheet, tile and KU units, national file themes, index record and the `index` signal, OGC API Features, channel choice by option values, `DOWNLOAD_SIZE`), ADR-039 (groups `names`, `maps`, `geodesy`) and ADR-041 (NMT 100 m in the variant registry without a vertical CRS; 8-member PL-1992 sheet codes - D10); erratum 1: PRG census districts outside the special boundaries area (E3); erratum 2: BDOO package classes (`--layers`) and voivodeship packages of the area (E4); erratum 3: area limit (100 files, 10 GB), mesh tile = record file, Bodove pole = sum of network layers (E5); erratum 4: the area limit covers BDOT10k (E2E test 0.8.0)

**Context:** Plan E (catalogue spec 6, 24 items) adds GUGiK products
and CUZK products whose file is neither a TERYT unit package nor a result
of an area from plans C/D: map sheets (BDOT10k visualisations: the file link only
in WMS GetFeatureInfo; CUZK ZTM: sheets of the index layer
`KladyMapovychListu`), tiles from WFS records (3D mesh: URL, date and report number
in the record), CZ cadastral territory packages (KU from RUIAN), national
files from several themes (PRNG), files without ZIP (TIFF, PDF, TXT
PL-geoid2021), OGC API Features services (PRNG, PRG special boundaries) and
products with a separate service per network or a feed per format. Measurements
2026-10-15/16 (`docs/research/2026-10-15-plan-e/raport.md`, fixtures
`tests/fixtures/pl/{e0,index_records,feature_bbox}/`,
`tests/fixtures/cuzk/real_2026_10_16/`): each PRNG OGC API `items` query
takes 78-95 s regardless of `limit` (`/collections` below 0.4 s;
OGC API PRG responds in 3.5 s); the mesh index publishes the namespace
`https://www.gugik.gov.pl` (NMT/NMPT/LAZ indexes `http://`), one record
per tile (Kraków: 3884 tiles of approx. 37 MB each); the BDOT10k visualisation GFI outside the
layer extent returns 0 B; the gravimetric control WFS responds under
`.../OsnowaGrawimetryczna/WFS` (not without `/WFS`), without `gml:id`; GUGiK
servers occasionally drop the connection (`RemoteDisconnected`), a retry
responds 200; GUGiK `opendata` sends neither `ETag` nor `Last-Modified`,
and the RCN `latest_exports` file is replaced (1261: 236,404,584 B
2026-10-15, 301,623,607 B 2026-10-16).

**Options considered:**
- A) A provider per product (maps, mesh, CZ cadastral map).
- B) Extending the engines and the plan orchestrator of C/D with units, an address
  from the index record and new channel parameters; product = descriptor.
- C) WMS as a data channel (a map image instead of a sheet file).

**Decision:** B (without a second engine and without a provider copying
the download). A duplicates the download, store and signals (the principle of plan C);
C gives a service image instead of a published file - WMS is only an
index (GFI). Code: Task E0 of plan E
(`docs/superpowers/plans/2026-10-15-plan-e-produkty.md`).
- D1. `unit_package` units: `UnitPackageParams.unit` += `sheet`
  (sheets of the area or the `--sheet` sheet), `tile` (WFS index records
  in the area), `ku` (CZ cadastral territories: `--ku` 6 digits or the KU of the area
  from the RUIAN layer `ku_layer`, field `kod`, `returnGeometry=false`);
  `themes`: a national file from several files, each theme a separate unit
  `country/<country>-<topic>` (lower case, `_` -> `-`). URL template tokens
  += `{sheet}`, `{ku}`, `{theme}`. Slots (extension of ADR-042 D8):
  PL sheet `<segment>/<hierarchy of the sheet code>/<sheet_code>`, CUZK sheet flat
  `<segment>/<MAPNOM>`, tile `<segment>/<zone>/<module>` (zone
  from the record CRS field: `PL-2000:S7` -> `s7`; without the field `tile/`), KU
  `<segment>/ku/<code>`, theme `<segment>/country/pl-<topic>`. `sheet=` of
  C/D products still means the sheet area (ADR-039 D4); a sheet unit
  arises only in the channel `unit="sheet"`.
- D2. The sheet grid is a property of the variant (`PackageVariant.sheet_grid`,
  a map scale has its own grid): `SheetGrid(system="1992", parts=N)` -
  a PL-1992 series with N sheet code members computed from the envelope
  (`find_sheets_for_bbox`; the `SheetParser` scale labels are one level
  finer than the GUGiK nomenclature, so the series is named by the number of
  members, never by a scale label; an area in a CRS other than PL-1992/PL-2000/
  WGS84 switches to EPSG:4326); `SheetGrid(system="cuzk", layer, crs)` -
  `MAPNOM` of the `KladyMapovychListu` layer queried in its CRS
  (`SheetIndex.sheets_for_bbox(layer, bbox)`, `SheetIndex.sheet(layer,
  mapnom, crs=)`; SM5 and TM33 unchanged); the existence of a CZ `--sheet`
  is checked in the layer after the query (`ValidationError`). There is no PL-2000
  grid: no collection product of plan E needs it.
- D3. Index record: `UnitPackageParams.index: IndexSource(kind, endpoint,
  parser, unit_field, url_field, label_fields, year_field, zone_field)`,
  layer in the variant (`PackageVariant.index_layer`). `url_template=None`
  = URL from the record: the only link or the format link from `choice`
  (`index_url`). `transport/index_records.py`: `gfi_records` (WMS 1.3.0
  GetFeatureInfo in the middle of the sheet frame, axes N,E; parser `map_links` -
  HTML table of the BDOT10k visualisation: sheet code, format link from the extension,
  date "Stan bazy"; 0 B = no record) and `wfs_records` (`WfsIndex`: pages
  only via `next`, fields by local name). An OGC exception on 200, HTML
  without a table, a table without a date or a link without HTTPS = `DownloadError`
  ("wynik bylby niepelny"); a single unusable WFS object
  is skipped with a warning. The unit gets the newest record (year, then
  label); `year` of a product without yearly variants is a record filter
  (ADR-028), not a variant choice. A sheet without a record is skipped
  and listed in `UNIT_LIST`; no sheet with a record = `NoCoverageError`.
- D4. The `index` signal in collections: the record label (`label_fields`
  joined with `_`, D29) is the version release (`label_source="edition"`),
  compared by `fetch_version`/`inspect_version`; `check_collection`
  queries only the index, never a file. A collection channel has the `index` signal if
  and only if it has an `IndexSource` (registry test). LAZ unchanged.
- D5. Choosing the channel and variant by option values: `download_collection`/
  `check_collection`/`validate_collection_request` receive `ku`, `format`,
  `scale`, `sheet_system` and `network` (`str | None`; `teryt`, `ku`,
  `sheet` and these options of a type other than `str` = `ValidationError`, because a code
  from a number loses leading zeros). The allowed values are in the descriptor
  (K1): `PackageVariant.choice`, `FeatureBBoxParams.choice` (one WFS
  service per network), `AtomFilesParams.choice` (one feed per format). Of several
  channels of the choice kind, the one whose values accept the given ones wins;
  no distinguishing value = `ValidationError` with a list; a single candidate
  is taken directly (its content check gives the allowed values).
  `FeatureBBoxParams.selection_key` names the layer selection option with
  `selection="level"` (`--level`; `network` for CZ control networks); a single `code`
  can name several layers.
- D6. The capability of a collection channel does not have to be unique (partly
  supersedes ADR-042 D1): channels of one kind (a service per network) share
  the capability. The sidecar reads the CRS from the first channel of that capability,
  so the channels that share it declare the same CRS (registry test).
- D7. OGC API Features in `feature_bbox` (`protocol="ogcapi"`,
  `TransportKind.OGC_API_FEATURES`): `/collections?f=json` once per
  download (no descriptor collection = `DownloadError`), first page
  `items?f=json&bbox=<CRS84 lon,lat>&limit=<page_size>`, subsequent ones only via
  `rel="next"` with the same scheme and host. N = `numberMatched`
  of the first page - without a separate count query, because each PRNG `items`
  takes 78-95 s. Each page: `numberReturned` equal to the number of
  objects and the same `numberMatched`; end at N unique `id`s;
  more than N, a page without new `id`s or no `next` before N =
  `DownloadError`. Result: GPKG in `OGC:CRS84` (the only output CRS of the
  GUGiK services). A slow service declares `FeatureBBoxParams.timeout`;
  precedence: channel, `SERVICE_TIMEOUT` (60 s); the explicit call `timeout`
  was removed (ADR-044 D6).
- D8. Non-ZIP files: `PackageVariant.file_kind` `zip|tiff|pdf|txt`
  (extension `.zip`, `.tif`, `.pdf`, `.txt`), checked by the first
  bytes: TIFF magic (classic and BigTIFF), `%PDF-`, text without NUL bytes
  with a first non-empty line that is not a marker (encoding
  irrelevant). An HTML/XML document instead of a file = `DownloadError`, without a
  version.
- D9. Size before transfer (K9): before the `GET` of each unit file
  a `HEAD`; a file over 100 MiB gets a `Notice` `DOWNLOAD_SIZE` (a warning
  with URL and size) at the moment of its download, also in C/D products
  (one more `HEAD` per package); a national file still gets
  `WHOLE_COUNTRY_SIZE` (K7). No sum of the sizes of all units before the
  first `GET`: the list of units is given by `UNIT_LIST`.
- D10. Product decisions of plan E (implemented in packages E1-E5): new groups
  `names`, `maps` and `geodesy` (ADR-039; `geodesy` = PL and CZ control networks and
  quasi-geoid models); product names unique across collections; oblique orthophoto
  `--direction` as a filter of the four sheet files; 8-part sheet codes
  of PL-1992 in `SheetParser` (E1). NMT 100 m (user decision
  2026-10-15): vertical CRS UNKNOWN - sidecar `vertical_crs: null`
  with a source annotation, segment without a CRS token, `--vertical-crs` for
  this variant = error. The CZ cadastral map in VKM format is outside 0.8.0
  (the pilot files of 2026-10-15 returned 404); SHP, DXF, DGN and VFK are included.

**Rejected:** provider per product (A); WMS as a data channel (C); a national
file for an area (an area always goes through the area channel or
through units, ADR-042 D2, K7); a height transformation tool
from a quasi-geoid - Kartograf downloads the PL and CZ models as data and does not apply
them to other data (PROJ has the official GUGiK grid); a REST channel
for CZ contours (SM5 sheets 1:1 with `http`); GeoParquet RCN; a national file
of BDOO; an OGC API feature count query before the pages (D7).

**Consequences:** Products E1-E5 are descriptors with parameters (registry
tests enforce: a variant without a URL template has an index, the `index` signal only
with an index, template tokens from the channel unit, a sheet grid and an index
layer in every variant, shared capability = the same CRS). Each
C/D package download sends one more `HEAD`. The area of a large city yields
thousands of mesh tiles (Kraków: approx. 3884 x 37 MB, approx. 143 GB) - `UNIT_LIST`
shows them before transfer; the limitation belongs to E5. Downloading OGC API
PRNG takes approx. 1.5 min per page - `page_size` and the channel `timeout` are set by
the descriptor (E2). CZ sheets lie flat in `<segment>/`, so thousands of
sheets give one large directory. The RCN file `latest_exports` is
replaced without a signal (`none`): new content comes only with `--force`.

**Erratum 1 (2026-10-16, E2E E3: `docs/research/2026-10-16-plan-e3-e2e/raport.md`):** The sentence "OGC API PRG responds in 3.5 s" applies to a single page of the `SadRejonowy` collection, not to the whole service: the `GranicaObwoduSpisowego` collection responds in 158 to over 400 s (measurement 2026-10-16: 157.9 s, and the area in Kraków exceeded the 60 s limit and ended with an error after exhausting retries), so the remaining collections have times of the order of seconds, and this one - minutes. Coordinator's decision: `GranicaObwoduSpisowego` is not an area result collection (the descriptor `pl.gugik.prg_special` has 44 collections instead of 45; the census districts are in the national SHP/GML file), and each area task gets an `Info` `AREA_OMITTED` (field `FeatureBBoxParams.area_omitted`); the channel timeout is 120 s. The special boundaries area takes 2-4 min (Kraków 243 s, Warsaw 109 s). The VKM fact is unchanged: VKM files respond 200 for KU 737950, 692450 and 619116, and 404 for KU 623164 (P2), so VKM remains outside 0.8.0.

**Erratum 2 (2026-10-16, E4: `docs/research/2026-10-16-plan-e4-e2e/raport.md`):** The BDOO `--layers` filter is not a GPKG layer filter (like the current BDOT10k), but a selection of package members: `UnitPackageParams.class_pattern` (an expression with a `code` group searched in the member file name; BDOO `__OT_<CODE>_<type>.`) and `PackageVariant.classes` (release classes = the sum over the 16 voivodeship packages of the year; a class outside the release = `ValidationError` before the network with a list of release classes). The class selection writes a new ZIP of the members of those classes - each byte for byte, with the name, date and compression of the source, in source order, so the same package gives the same bytes - in a segment with the class token (`pl_bdoo_2023_kuik-ptwp`); complex objects, XSD and metadata are only in the full package. A package without the file of some of the selected classes (until 2023 the package has no file for a class without objects in the voivodeship) = `Info` `CLASSES_ABSENT` (a new `Notice` code), with none of them = unit `NoCoverageError`; a package without any class file is not data (`DownloadError`). Classes only on the TERYT unit channel or the national file, without `unpack` (registry test). The area of a product that has only voivodeship packages (BDOO) yields the voivodeship packages of the area's counties from PRG (`UNIT_LIST`), like the NMT 100 m ATOM files; a county code for such a product = `ValidationError` with the hint `--teryt <woj>`. BDOO, Data50 and Data250 go through `LandCoverManager` along the `landcover_request` path (like ZABAGED, ADR-042 D15), not through BDOT10k archive tasks.

**Erratum 3 (2026-10-16, E5: `docs/research/2026-10-16-plan-e5-e2e/raport.md`):** (1) Area limit (decision 2026-10-15): a collection area task (`bbox`, `sheet`, `geometry`; also the sources of the `LandCoverManager` collection and NMT 100 m) that would transfer more than 100 files or more than 10 GB ends with `ValidationError` BEFORE the first transfer (`collections.run_request` -> `_within_volume`): the number of files, the size (sum of `HEAD`/`length` of the ATOM feed; over 100 files - an estimate from an average of 5 files spread evenly) and a hint (narrow the area, unit `--teryt`/`--ku`, a plan with part of the items). Files without a local version are counted (`force`: all, `--upgrade --plan`: plan items); unit selection and `whole_country` have no limit (the trees package 0208 = 24.7 GB would otherwise be unreachable); there is no bypass option. A size queried before transfer is not queried again (size `HEAD` with the `SIZE_TIMEOUT` limit = 120 s: the GUGiK opendata server responds in 0.2-90 s, approx. 3.5 s per GB). (2) 3D mesh: the `modul` field of the `ModeleSiatkowe3D` index does not identify the tile (26,633 values in several places of the country; 138 places with two meshes of one year), so `IndexSource.unit_field=None` = the unit is the file name of the record; the D5 rule "newest tile record" does not apply to mesh, `year` filters records. Segment `models3d/pl_mesh/<zone>/<file>.zip` instead of `.../<module>.zip`. (3) Control points: the point layers determined in ETRS89 (2-8, 22-28) are not subsets of 18/20 and 38/40 (zero common points in the country) - the network = the sum of 6 layers; abolished ones and labels omitted; a single `FeatureLayer.code` names several layers (the registry test allows a repeated code with `selection="level"`). (4) A collection product may have only an ATOM channel when the feed has one dataset (QGZU; `atom.single_dataset`); the sheet and voivodeship feeds stay in `download_data`. (5) An option value available only in another choice names that choice (`--teryt` + `--network gravity` -> area), and a PL+CZ task gives the values of the other country and the common ones. (6) Quasi-geoids: sidecar without `vertical_crs` (the model is not heights; the CRS in the name and segment `evrf2007`), control network archives: the sidecar CRS = the CRS of the sheet grid (EPSG:2180).

**Erratum 4 (2026-10-19, E2E test 0.8.0):** the area limit from erratum 3 (1)
covers BDOT10k (`LandCoverManager._bdot_volume`, current packages,
a county counted once despite `--keep-raw`, also the `--year` archive):
`HEAD` sizes through the provider session, the same message; for this purpose
`collections.within_volume` and `unit_choices` are public. The county list
of the area is `Info` `unit_list` (`notices.names_text`, at most 10
names). Up to 100 files the size of each file is measured by `HEAD` (the
10 GB limit is exact: 69 counties = 2.87 GB pass); above 100 files
the count decides on refusal, and the size (average of 5 files) is only
indicative (round 3 of the E2E test 0.8.0).

---

## ADR-044: Unifying CLI and API: --product, --summary, land cover, soils and HSG functions

**Data:** 2026-10-16
**Status:** Accepted; partly supersedes ADR-039 (D1, D6: `landcover --source`, D5: class methods in the API role), ADR-040 (D2: name `project_status`), ADR-042 (D9: `landcover` stays with `--source`; erratum 5: orthophoto cutout API names), ADR-036 (D32: land cover and HSG results), ADR-037 (S3-S4: class methods) and ADR-043 (D1 and erratum 3: slots of the CUZK sheet, tile and national file topic - D7); amends ADR-043 (D7: call timeout) and ADR-026 (D7: naming convention of keys and `data/` directories); erratum 1: keyword-only arguments of all download and check functions (live test 0.8.0); erratum 2: land cover and soils: SoilGrids units, BDOT10k classes, CORINE preview (E2E test 0.8.0)

**Kontekst:** Review of UX of release 0.8.0 (UX-08, UX-09, UX-21, UX-45):
`landcover` is the only one of the 11 data groups that selects data with the flag `--source`
(`-s`), the others use `--product`, and the mistake `landcover download --product`
ended with a parser error; the project task option key is `source`.
`soil hsg --stats` stands next to `soil download --stat`. The land
cover and soils library consists of classes (`LandCoverManager(output_dir, provider)
.download(**options)`, `HSGCalculator(...).calculate_hsg(..., timeout=120)`)
with their own results (`LandCoverAreaResult`, `LandCoverResult`,
`LandCoverFailure`, `HsgResult`), while the other commands are keyword-only
functions (`download_data`, `download_collection`) with reports
`UnitFile`/`UnitFailure`; next to `download_image_cutout` there is the wrapper
`download_orto_cutout`, and `project_status` is a noun among
verbs. User decisions 2026-10-16: `--product` in all
groups (no alias; `--source` = error with a hint), `soil hsg
--summary`, full API unification (functions in the style of `download_data`/
`download_collection`, consistent result types and names, no unnecessary
aliases), everything with "Co zrobic" in the CHANGELOG.
The same review (UX-35..40) showed the names of source keys and `data/`
directories of the products new in 0.8.0 without a single convention: key
`pl.gugik.orto_true` with `--product true-orto` and directory
`orto/pl_1992_true/`, `cz.cuzk.hy_net` with segment `cz_hynet`,
`cadastre/cz_km_<format>` (`km` reads like kilometres), token `package`
instead of a format token, `cz_qgzu2013` without a vertical CRS token (next to
`pl_geoid2021_evrf2007`), mesh zone directories `s7`/`pl1992` next to tokens
`1992`/`2000` and thousands of ZTM sheets flat in one directory. User decision
2026-10-16: one convention before the release, without migration
(products new in 0.8.0).

**Options:**
- A) Keep `--source` and the classes; only targeted notices for mistakes.
- B) One convention in every group: `--product`, module-level functions
  and reports shaped like `CollectionReport`; classes as an internal
  layer.

**Decision:** B (user decision 2026-10-16), without aliases:
- D1. `landcover download` and `landcover list-layers` select the product
  with the `--product` flag (no short form, values from the registry: `bdot10k`, `bdoo`,
  `corine`, `zabaged`, `data50`, `data250`), the CHOICE column of `landcover
  list-sources` - `--product <x>`. `--source` and `-s` = parser error
  (code 2) with a hint `--product`; `--product soilgrids` and the former
  `--source soilgrids` point to the `soil` group. Error messages name
  `--product <x>`. Task option key of the project `landcover download`:
  `product` (the manifest is new in 0.8.0 - no migration of the `source` key).
- D2. `soil hsg --summary` prints HSG statistics (share and area of
  groups) instead of `--stats` (the name is not confused with `soil download --stat`);
  `--stats` = parser error (code 2) with a hint `--summary`. `project
  add` rejects `--summary` like `--workers` (a printing option, not part of the
  task).
- D3. The PL image cutout has one pair of functions for orthophoto and true
  orto: `download_image_cutout`/`check_image_cutout` (`product="orto"`
  with `coverage`, `"true-orto"` without it) with the result `ImageCutoutResult`
  in `kartograf.__all__`. The wrappers `download_orto_cutout`/
  `check_orto_cutout` and the name `OrtoCutoutResult` (ADR-042 erratum 5)
  removed without aliases.
- D4. Project state: `get_project_status` (a verb like `init_project`,
  `download_project`, `verify_project`) instead of `project_status` (ADR-040
  D2), without an alias; the command `kartograf project status` unchanged.
- D5. Every land cover, soils and HSG data command has a counterpart in
  the public `kartograf.__all__`: `download_landcover`/`check_landcover`,
  `download_soil`/`check_soil`, `calculate_hsg`/`check_hsg` and
  `hsg_statistics`. The functions accept the command options as named arguments,
  `output_dir`, `cache`, `on_notice` and optionally `plan`/`update`;
  `download_landcover` requires `product`. The reports `LandCoverReport`,
  `SoilReport` and `HsgReport` provide `files` (`UnitFile`), `failed`
  (`UnitFailure`), `stale`, `notices` and `ok`; land cover additionally has
  `raw` (the original ZIP for `keep_raw`), HSG has `inputs` (three SoilGrids
  versions) and the result file in `files`. `LandCoverManager`,
  `HSGCalculator`, `LandCoverResult`, `LandCoverAreaResult`,
  `LandCoverFailure` and `HsgResult` remain an internal implementation,
  without exports and without public aliases. The CLI and project tasks
  call command-level functions, not methods of these classes.
- D6. Download/computation errors of a single file go to
  `report.failed`, `ok=False`; the remaining units are processed.
  Errors of choices and options before the work remain `ValidationError`.
  The public functions and `collections.run_request` have no `timeout`
  parameter: limits are set in providers or channel parameters
  (ADR-043 D7); `require_timeout` was removed, without a sham passing
  of the time from the command to the engine.
- D7. One naming convention for source keys and `data/` directories (rule 10
  of section 3.3 of `docs/ARCHITECTURE.md`; registry test
  `TestNamingConvention`), consistent with the segments of releases <= 0.7.2 and rule 8:
  key `<country>.<provider>.<name>` (words `[a-z0-9]` joined by `_`)
  from whole words of the `data/` path - the dataset name from the segment or the product
  directory, when the segment starts with a CRS, with fixed descriptor
  tokens; top-level directory = `--product` in `elevation`
  and `imagery`, the CLI group in the others; segment `<country>_<tokens>...`: `_`
  only between tokens, `-` between words of one token (like `0-5cm`,
  `ptwp-swrs`, `ascii-nmt`; never `_` in a token), `.` only in a number;
  variant tokens = values of the choices (`--format SHP` -> `shp`,
  `--horizontal-crs EPSG:3045` -> `3045`), content without a choice - the token of
  the file format, vertical CRS at the end; PL CRS `1992`/`2000`,
  PL-2000 zone = the directory of its number under `2000` (like the first part of the
  PL-2000 sheet code); sheet hierarchy = all parts of the sheet code; a suffix
  to the unit code in the file name after `_`. Changes (products new
  in 0.8.0, no migration): keys `pl.gugik.orto_true` ->
  `pl.gugik.true_orto`, `orto_oblique` -> `oblique_orto`, `buildings_3d`
  -> `buildings`, `mesh_3d` -> `mesh`, `trees_3d` -> `trees`, `prpog` ->
  `control`, `quasigeoid` -> `geoid2021`, `cz.cuzk.hy_net` ->
  `cz.cuzk.hynet`, `ortofoto` -> `orto`, `survey_control` -> `control`,
  `qgzu` -> `qgzu2013`; directories `orto/pl_<crs>_true` ->
  `true-orto/pl_<crs>` (cutout `true-orto/pl_1992_<res>`),
  `orto/pl_<crs>_oblique` -> `oblique-orto/pl_<crs>`,
  `cadastre/cz_km_<format>` -> `cadastre/cz_cadastral-map_<format>`,
  `geodesy/pl_control_<network>_package` -> `geodesy/pl_control_<network>_xls`
  (content format token like `pl_prg_shp`, `pl_prng_xlsx`; not `zip` -
  every package is a ZIP); `geodesy/cz_qgzu2013` ->
  `geodesy/cz_qgzu2013_bpv` (like `pl_geoid2021_evrf2007`); slots: mesh
  tile `s7/` -> `2000/7/`, `pl1992/` -> `1992/`, ZTM sheet flat ->
  sheet code hierarchy (`0510/D/11/0510-D-11.zip`, `NM-34/07/1/D/15/...`;
  `parser_registry.cuzk_map_path_parts`), national file topic
  `pl-<topic>` -> `pl_<topic>`. `token_segment` rejects a token outside the
  convention (`-` and `.` only between letters and digits). Unchanged:
  segments and keys of releases <= 0.7.2 (including `pl.gugik.nmpt` = NMPT 1 m without
  `_1m`, the `dataset` field of 0.7 sidecars).

**Consequences:** A breaking change of the CLI and API in 0.8.0 (CHANGELOG [0.8.0]
"What to do"): the same `product` choice in every group and in the API, one
`files`/`failed`/`stale` report per command type. The existing methods and
result types of the classes are not public API; when migrating, code reading
`result.file` chooses `report.files[0].file`. The sidecar schema
`kartograf-meta/1` and the segments of releases <= 0.7.2 unchanged; D7 changes keys
(the `dataset` field) and directories only for products new in 0.8.0 - files
downloaded by the development version under the former names are not migrated
(the next download goes to the new directories). A new descriptor passes the
convention test or does not enter the registry.

**Erratum 1 (2026-10-17, live test of release 0.8.0, coordinator
decision):** the API unification (D3, D5) covers all download
and check functions from `kartograf.__all__`: keyword-only arguments
(`*` at the start), like `download_data` - also `download_pl_cutout`/
`check_pl_cutout`, `download_cz_cutout`/`check_cz_cutout`,
`download_laz_area`/`check_laz_area` (`bbox=`), `download_cz_sheet`/
`check_cz_sheet` and `download_cz_orto_sheet`/`check_cz_orto_sheet`
(`sheet=`); until now the first argument was positional (live test:
`download_image_cutout(bbox, ...)` stood out from the rest of the API). The project
functions (ADR-040) have only the project directory positional - a handle
shared by the whole family (`init_project`, `open_project`,
`download_project`, `check_project`, `get_project_status`,
`verify_project`, ...). Rule: DEVELOPMENT_STANDARDS 7.3 (Z2), test
`tests/test_public_api.py`; a breaking change with "What to do" in the CHANGELOG
[0.8.0].

**Erratum 2 (2026-10-19, E2E test 0.8.0):** (1) The SoilGrids sidecar has
`extra.units` (`mapped`, `conventional`, `divisor`; an addition to
`kartograf-meta/1`): file values are ISRIC "mapped units" (clay g/kg,
phh2o pH x 10, bdod cg/cm3, soc dg/kg, nitrogen cg/kg, cec mmol(c)/kg,
cfvo cm3/dm3, ocd hg/m3, ocs t/ha), and `soil list-layers --json` carries
`unit`, `conventional_unit`, `divisor` and `depths` (`PropertyInfo`).
`ocs` exists only for 0-30 cm (`PROPERTY_DEPTHS`, a single place of
validation for the provider and `LandCoverManager`); the `ocd` edition comes
from the `clay` map (`ocd.map` has no edition in its title; the title and url in
`extra.edition` are those of the `clay` map, and `extra.edition.source_property` =
`clay` states this in machine-readable form). A raster of only zeros
(except `cfvo`) is a `Warning` `all_nodata` and `extra.all_nodata`, HSG without
a class likewise; a window smaller than a pixel is extended to one
pixel. (2) BDOT10k: `--layers` validated against the 58 classes from
the regulation (Dz.U. 2021 poz. 1412, annex 1; `BDOT10K_CLASSES`) before the
network, a class absent from the county package is an `Info` `classes_absent`
(`extra.source.classes`), absence of all classes - the county's `NoCoverageError`;
classes outside the list (the GUGiK typo `OT_BIUB_L`) are not selectable.
(3) CORINE: the WMS preview raster layer is derived from the GetCapabilities of the
year's service (2012, 2006, 2000), a fully transparent image is a `NoCoverageError`
before the version. (4) BDOT10k area limit: ADR-043 erratum 4.

---

## ADR-045: Public store-reading API for Archiwista

**Date:** 2026-10-18
**Status:** Accepted — amended by ADR-046 (MCP tools for reading the store; erratum 1) and ADR-054 (the parameter `root`); erratum 2: segment parts (`list_partitions`, `partition`) and the `skip_versions` mapping without listing known version directories (relaxes visibility of changes in them); erratum 3: `Sidecar.unit` and the LAZ tile outline, ZTM sheet, `link_target` of an independent copy (E2E test 0.8.0)

**Context:** Archiwista 0.1 indexes a large store (also on SMB) without
writing to it and without a private `data/` parser. It needs six
operations KA-1..KA-6 from its specification 12.1. The inode number on some
CIFS shares does not recognise a hard link, old sidecars and segments from the development
version do not exactly match the current registry.

**Options:**
- A) A structure reader in Archiwista and inode-number heuristics — faster
  start, two different store contracts and false hard-link targets on SMB.
- B) A streaming, read-only producer API; shared registries, parsers,
  link validation and pinned transformation operations — one policy.

**Decision:** B, in release 0.8.0. `list_segments(output_dir)` returns
`<product>/<variant>` segments (also those unknown to the registry), and
`iter_store(output_dir, *, segment=None, units=None, skip_versions=None)`
a generator of version entries, standard paths, `full_sheet/` and problems
(unknown segment, missing/corrupted sidecar, old `kampanie/`, stale
`.incoming/`). `segment` is the relative path `<product>/<variant>`;
`units` are the units of the segment whose slot directories are computed by the same
logic as writing; the scan restriction occurs BEFORE listing the segment
branch. `skip_versions` are version directories known to the caller: their files
are returned from the listing alone (`skipped=True`, `sidecar=None`) - versions are
immutable, so an incremental scan reads only the sidecars of links and new
versions. The scan does not read file contents and does not call `link_target`; it reads the sidecar
of a single file at most once, and the `version_path` of a link is taken
from `extra.link_target` after checking that it points to a version of its own slot.
Calls for different segments or parts of the `units` of one segment may
run in parallel in threads. Unknown segments are visible, they do not silently
end up in another product. `StoreEntry.sidecar` may be `None`; `problem`
is a code useful for indexing.

`read_sidecar(path)` accepts a data file or `.meta.json`, preserves
raw values and separately exposes the recognised descriptor key and
normalised dates, data year and unit. Missing data in an old sidecar
remains missing: the download date is not the data year; invalid JSON/unknown
schema is a read error, which the scan turns into a problem entry; a missing `schema`
field is accepted only in the shape of the `emit_sidecar` bare sidecar
(a provider without a descriptor), consistent with `read_version`. `Sidecar.unit` of a
national file with a theme is the slot file name (`pl_miejscowosci`), so it
can be passed to `iter_store(units=...)`. Normalisation of
historical keys (including from 0.8.0-dev) does not mutate the store.
`describe_segment(segment)` recognises registry patterns and content variants
by inverting `resolve_subdir`/`content_segment`, with a safe result
`known=False` for the rest. `file_footprint(entry, *, network=False, cache=None)`
has the order: task bbox, parseable PL/TM33 sheet code, file header,
unit from the network index (unknown to the index = no outline),
finally no outline; `Footprint` carries
`native` and `wgs84` as `BBox` and `source`. Network access to PRG/RUIAN/SM5
is opt-in, and the cache is the caller's local memory (read also without
network); national files do not get an invented outline. `link_target(path)`
uses the existing `linked_version`: link metadata and `samefile`,
and on CIFS from reading the file hash (without a stable inode).
`pinned_transform(src_crs, dst_crs)` builds a `PinnedTransform` without
network grids and without ballpark (an object per thread - pyproj operations are not
thread-safe); we do not expose a default pyproj transformation.
Thread guarantee: `list_segments`, `iter_store`, `read_sidecar`,
`describe_segment`, `file_footprint`, `link_target` and `pinned_transform`
can be called in parallel from many threads (the consumer's thread pool);
`pinned_transform` gives the thread its own object (do not pass it to another
thread), and `file_footprint` shares between threads only the caller's
`cache` (a plain `dict` suffices). This is guarded by the parallel-use
test.

**Consequences:** Store reading only (also for a store mounted read-only);
problem results instead of lost files. The cost of a full scan is directory
listing + one sidecar read per file, without `stat`/`open` of the content of each
version; a scan with `skip_versions` - listing + sidecars of links and new
versions; for `units` the number of listed branches is proportional to the number of
selected units and their versions. `file_footprint` reads the header only
when bbox/sheet code is missing; `link_target` may read the whole file on CIFS without
`serverino` — do not call it for every version in a full scan. The
`kartograf-meta/1` version on disk remains unchanged. Contract description: ARCH 3.3.1;
plan: ARCH 3.3.2. No part of KD/KB or downloading is in this cycle.

**Erratum 1 (2026-10-18, ADR-046):** store reading also takes the form of documents
(`describe_store`, `list_store_entries`, `read_store_sidecar`; `kartograf-store-overview/1`,
`-store-entries/1`, `-store-sidecar/1`) and MCP tools `store_overview`, `store_entries`,
`store_sidecar`; the streaming `list_segments`, `iter_store` and `read_sidecar` are unchanged.
A missing or unavailable `output_dir` is an `OSError` (error code `io_error`, exit code 1),
`InvalidSidecarError` is `invalid_sidecar`, invalid arguments are a `ValidationError` with
`option` (`segment`, `units`).

**Erratum 2 (2026-10-19, Archiwista v0.1 measurement `docs/raporty/v0.1-pomiary.md`,
coordinator decision; still 0.8.0):** an incremental scan of a store of 50 thousand
slots on an SMB share took 342 s (target 180 s): the largest segment
(`nmt/pl_1992_1m_evrf2007`, 43% of entries) was read by one thread, and refreshing the
view listed every known version directory of a flat slot (`bbox/`: 4850).
(1) Parallelism within a segment: `list_partitions(output_dir, segment, *,
target=32)` returns disjoint part keys - `"."` (segment level: its
problems and files directly in the segment directory and in `full_sheet/`),
`"<dir>[/<dir>...]"` (a slot and all slots under it, simultaneously
in the standard path, `full_sheet/` and `versions/`) and `"<dir>/."` (the slot
of a directory itself, split further). First-level directories are split
level by level into subdirectories while there are fewer parts than `target`.
`iter_store(..., segment=..., partition=...)` reads one part; the sum of the parts
is the segment scan (the same entries, none twice, segment problems once).
The key is a string: readable in logs and portable between threads and
processes. Rejected: a depth parameter (segment shapes differ - two
first-level directories in NMT PL-1992, 714 in the CZ orthophoto) and splitting
the files of a flat slot by name (each part would list the whole directory).
(2) `skip_versions` also accepts a mapping `version directory -> data
file names`: a directory from the mapping is not listed, and its entries (the same as
from a listing) are built from the given names. This RELAXES the guarantee of the decision: a file
removed from such a directory or added to it (Kartograf adds a file
to an existing `<label>_<sha8>` for the same label and the same
`sha8` of another file of the slot) is not visible until a scan without the mapping. The set of
directories works as before (listing, `missing_sidecar`). The caller maps
only directories whose files were all valid versions at the last read,
and periodically scans without the mapping (Archiwista:
daily and on request for a full scan, with the time of the last such scan
in the store view). Gain: approx. 80 thousand out of 201 thousand listings of an
incremental scan, one listing instead of 4850 when refreshing `bbox/`
units. (3) The scan loop operates on strings (`Path` only in `StoreEntry`),
and sidecar typing computes computed fields lazily: a store of 50 thousand slots,
SSD, incremental scan 12.4 -> 6.3 s (with the mapping 5.2 s), full 20.3 ->
10.1 s, result unchanged (hash of all entries). Contract and cost: ARCH
3.3.1. Invalid `partition`, `target` and mapping names are a `ValidationError`
with `option` (`partition`, `target`, `skip_versions`), as in erratum 1.

**Erratum 3 (2026-10-19, E2E test 0.8.0):** (1) `Sidecar.unit` of a LAZ tile is
its sheet code (`extra.tile_sheet`, also in 0.7.x and 0.8.0-dev sidecars
and the key `godlo_kafla`), not the task area `<coords>` from `request.bbox`;
`file_footprint` of a tile ignores `request.bbox` and takes the outline from the LAS header
(without a readable header: `None`, never the task area), so
`iter_store(units=[unit])` finds the tile. In a segment of sheets and tiles only
(ZTM) the number alone (`0510`) is a sheet, not TERYT. The `request` record
of a LAZ tile is unchanged (task area; versions are immutable, the reader must
know the old shape); switching to `request.tile` with `parent_request`
was considered and postponed. (2) `link_target`/`linked_version` of a file with the content of a
version that is not a link (an independent copy) returns that version
instead of `None`: the contract "confirmed on disk" is the same content, not the
same inode (ADR-036 erratum 4). (3) `file_footprint` skips a source whose
envelope cannot be safely converted to WGS84 (`TransformError`: no
operation in the policy or the envelope outside the operation area) and takes the next
source; with no source the result is `None`, the exception does not leave the function
(`DownloadError`/`ParseError` of indexes remain with `network=True`). Reason:
`names` and `boundaries` `special` entries have `request.bbox_crs` =
`OGC:CRS84`, and PROJ 9.8.1 reports an unknown accuracy for the CRS84 -> EPSG:4326
axis swap, so the policy rejected it and the first error aborted the call
(the GPKG header was not read). A pair of CRS equal up to the axis
order of a geographic CRS (CRS84, EPSG:4326) is an identity:
the envelope is the same numbers without an operation, and `build_pinned_transform` treats
such a pair as exact.

---

## ADR-046: Interface for AI agents: JSON documents, error codes, command catalog and MCP server

**Data:** 2026-10-18
**Status:** Accepted; amends ADR-037 (command result as a JSON document, `--json`, error and exit codes), ADR-039 (command declarations in the catalog), ADR-040 (data command options from the catalog) and ADR-045 (MCP tools for store reading); erratum 3: exit code 143 (`terminated`), `failed[].kind`, stderr in `--json`, `hint` from call arguments (E2E test 0.8.0)

**Context:** Kartograf is meant to be a tool that AI agents (Claude Code, Archiwista
assistant, scripts, other servers) choose and use without reading the code - through the CLI,
the Python library and an MCP server. State of 0.8.0-dev: `--json` exists only in `elevation
availability`; results of data commands, project, `parse`, `list-sources`, `list-layers` and
`cache` have no serialisation (part of the logic for choosing flags, layers and cache sits in the CLI);
exceptions have no stable codes or hints, and exit codes (0, 1, 2, 130) are not
written down anywhere; the names, kinds and allowed values of options are repeated by hand in argparse
(36 commands, 38 thousand characters of help), in the project's `COMMANDS` and in the
`*_task_arguments` functions; there is no command catalog (Archiwista KB requirement, SPEC 12.2); there is no
`py.typed`, `llms.txt` or a single gate command. The scope (8 items) was set by the coordinator
on 2026-10-18; design: `docs/superpowers/specs/2026-10-18-agent-interface-design.md`.

**Options considered:**
- A) Only documentation and `--help` for agents; CLI text parsed on the agent side.
- B) One machine contract: JSON documents from the library, stable error codes, command
  catalog as the source of truth (CLI parser, project options and MCP schemas from it), MCP server
  as a thin layer over library functions.
- C) Only an MCP server with its own tool descriptions (CLI and library unchanged).

**Decision:** B (details D1-D21 of the specification):
- D1. Serialisation in the library: the `Document` mixin (`kartograf/serialization.py`),
  `to_dict()`/`to_json()`, `schema` as the first key, absolute paths; CLI and MCP
  only print. Schemas `kartograf-<kind>/<n>`, within `/1` only additive changes.
  One schema `kartograf-download/1` for `DataReport`, `CollectionReport`,
  `LandCoverReport`, `SoilReport` and `HsgReport`. The notice field remains `text`
  (`Notice.text`), an error has `message`.
- D2. `--json` in every command: stdout = one document, stderr without `Info:`/`Warning:`
  (notices in `notices`), error = `kartograf-error/1` on stdout (also an argparse error).
- D3. Exceptions get `code`, `exit_code`, `hint` and `DETAIL_FIELDS`; `ValidationError` carries
  `option`/`options`/`allowed`; new `UsageError`; `OSError` (missing, permissions, detached
  share) has the code `io_error` (D21). Exit codes: 0, 1, 2 (invalid input and usage, like
  argparse), 130; one table of exit and error codes in USAGE.
- D4. Command catalog (`get_catalog()`, `kartograf catalog`, `data_commands()`): declarations
  of commands and parameters in `kartograf/catalog/`; the CLI parser is built from the declarations (stdlib
  argparse, the library does not import `kartograf.cli`), project `COMMANDS` options and MCP schemas
  from the same declarations, contract tests as a second barrier. Command layer
  `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command`
  (KB-2..KB-5 of Archiwista, without `cancel`).
- D5. MCP server: extra `kartograf[mcp]` (`mcp>=2.3.0,<3`), script `kartograf-mcp`, stdio,
  low-level `mcp.server.Server` with explicit schemas from the catalog; 29 tools (a catalog
  command + one `check_updates` tool with parameters `tool` and `arguments` instead of
  12 twins), result = the `--json` document, `is_error` = CLI exit code != 0, progress
  via `report_progress`, absolute paths, no default values affecting
  data, `--tools` and `--allow-dir`.
- D6. `py.typed` (PEP 561), `llms.txt`, `scripts/gate.sh`, `python -m kartograf` and a rule
  in `CLAUDE.md` for agents from other repositories (branch from `develop`, no merge, tags
  and release entries without consent, review before a tag).

**Consequences:** Breaking change in 0.8.0-dev (CHANGELOG [0.8.0], "Co zrobic"): an input error
ends the CLI with code 2 (not 1); `schema` is the first key of `kartograf-availability/1` and
`kartograf-plan/1`, the plan has `notices` and `ok`; the modules `kartograf/cli/groups/*` and the functions
`*_task_arguments` disappear (CLI = `create_parser()` from the catalog). The library gains
`describe_sheet`, `find_sheets`, `list_sources`, `list_layers`, `get_cache_info`,
`clear_cache`, `describe_store`, `list_store_entries`, `read_store_sidecar` (logic
moved from the CLI according to Z1). Hydrograf unchanged (library; exception attributes
additive); Archiwista gets KB-1..KB-5 and keeps `Notice(level, code, text)`.
Extension of DEVELOPMENT_STANDARDS rules: 7.3 (Z8-Z11), 6.3 (`scripts/gate.sh`), 11.1
(error codes), 17.2 (a new command via the catalog). Issues O1-O9 of the specification were settled by the
coordinator on 2026-10-18 (section 16 of the specification: among others one `check_updates` tool,
`CommandInfo.supports_check` instead of `check_tool`, exit code 2 for input errors).

**Erratum 1 (2026-10-18, implementation and integration):** discrepancies relative to the decision and measurements
established in the implementation (specification: 9.4, 16.2-16.4):
- D22. Agent context budget (coordinator decision during implementation): the first version of the
  tools gave `tools/list` 65,893 characters and `get_catalog()` 47,807 characters. Now
  `get_catalog()` returns an overview (`view: "overview"`: 7,315 characters, CLI `kartograf catalog
  --json` 7,629), and parameters, constraints and examples on request (`group=`, `command=`,
  `params=True`); the tables `exit_codes`, `errors` and `schemas` are `null` until
  requested (`tables=True`; the whole catalog with parameters has them); `view` is the second key of
  `kartograf-catalog/1`. Tool descriptions are written per call (a few words), shared
  argument meanings are once in the server's `instructions` (four paragraphs, 1,447 characters),
  tools have no `title` or `$ref`; `tools/list` has 28,607 characters (the 30,000 budget is
  guarded by tests).
- Modules: reports with logic moved from the CLI live outside `catalog/`: `source_info.py`
  (`list_sources`, `list_layers`), `cache_info.py`, `store_documents.py` and `sheet_info.py`
  (`describe_sheet`, `find_sheets`; `SheetInfo.commands` is computed from the catalog); shared parser
  code, `format_command` and hints are `catalog/kinds.py`, `formatting.py` and
  `hints.py`; `ErrorReport` and the code tables: `kartograf/error_report.py`; `Document`, the encoder and
  `SCHEMAS` (outside `__all__`): `kartograf/serialization.py`.
- `kartograf.mcp_server` imports without `mcp`: the SDK is loaded lazily in `create_server`, which
  without the package raises `ImportError` with an installation message; `main()` prints it to stderr and
  exits with code 1 (the `kartograf-mcp` script is always installed).
- MCP progress: the library's `on_progress` is sometimes called from worker threads (`workers > 1`), where
  `anyio.from_thread.run` does not work; the server uses `BlockingPortal`, and the event counter grows
  strictly under a lock (`total` is `None`).
- Integration wrap-up: `cache path` has its own function `get_cache_path` (the database is not
  opened, so an unreadable cache does not break the path indication; `cache path --json` is
  `kartograf-cache/1` with `action: "path"`); a `UsageError` of a known command carries its id
  (`command` in `kartograf-error/1`, hint `Parametry komendy: kartograf catalog <id>.
  Przyklad: ...`); `format_command(run=)` validates run flags, and `parse_command`
  rejects a lone `--bbox-crs`.
- Installing `mcp` in `.venv` (O7) raised `idna` 3.11 -> 3.20 (requirement of `httpx2`), so it was
  not purely additive: coordinator's approval; the remaining 20 packages were added without upgrades.

**Erratum 2 (2026-10-18, live verification T9):** report
`docs/research/2026-10-18-agent-interface-e2e/raport.md` (wheel and sdist with `py.typed`, `--json`
in 37 leaf commands, availability, download, MCP server over stdio, Claude Code):
- Result: code ready for release 0.8.0, no blockers; spec criteria 1-12 met
  (after the documentation merge the code table in USAGE, the rule in `CLAUDE.md` and the documentation entries
  landed on the branch). Agreement of the three paths (CLI `--json`, library `to_dict()`, MCP tool)
  confirmed apart from `checked_at`, the status label and the store path. Gate: 7070 passed,
  18 deselected; ruff and format clean, mypy without errors.
- One error, fixed (`a7ba1336`): `kartograf-mcp` ended with a traceback when the cache directory
  could not be created (read-only `HOME`, `--cache-file` under a regular file),
  while the CLI and the library warn and work without cache. `_open_cache` catches `OSError`,
  logs one warning and the server runs without cache; regression test in `tests/test_mcp_server.py`.
- Discrepancies of the plan relative to the services (code consistent with the spec): `elevation download` has 30 parameters
  (29 with a CLI flag and `update`), not 28; sheet `N-34-130-D-d-2-4` has no NMT 5 m; the status
  of a repeated run is `local`; a missing area is reported before a missing `output_dir`
  (`details.options`); `--help` differs from the reference by the examples from the catalog and exit
  code 2 for `parse` with an invalid sheet code (intended, decisions O2 and D7).
- Minor items O1-O5 from the report (coordinator's decision: fixed in 0.8.0, because it is ergonomics for
  agents): the `hint` of an error from `options` (e.g. missing area) is `Opcje: <flags>.` and `Przyklad:
  <command line>` from the catalog instead of `null`; `parse_command` accepts a line with a
  leading `kartograf ` (the round trip `parse_command(format_command(...))` works without
  trimming); `project_check_updates` is named in the catalog (`CommandInfo.check_tool`,
  `full` view; `check_updates` for data commands), while `supports_check` and `tool` remain
  unchanged; a plan of another store is a `ValidationError` with `option="plan"`; a relative `--allow-dir`
  ends startup with a usage error (code 2: call paths are absolute, a relative
  directory would depend on the working directory of the server chosen by the client).

**Erratum 3 (2026-10-19, E2E test 0.8.0):** (1) exit code 143
(128 + SIGTERM) and error code `terminated` (`kartograf.interrupt.Terminated`,
a subclass of `KeyboardInterrupt`): the CLI `main` intercepts SIGTERM
(`sigterm_interrupts`) and ends like Ctrl-C (cleaning up `.incoming`,
`Error: przerwano (SIGTERM)` or `kartograf-error/1`); the MCP server does not
intercept SIGTERM (default termination; cooperative stopping
would require `os._exit` with stdin open and a change in the semantics of `_execute` -
a separate decision). Rows 143/`terminated` in `ERROR_CODES` and `EXIT_CODES`,
the description of 130 clarified; additive change. (2) `UnitFailure.kind`
in `kartograf-download/1` has the values `no_coverage`, `year_out_of_range`,
`download` and `country`; data states (`NoCoverageError`, `YearRangeError`)
have in the report the same names as the `kartograf-error/1` error codes, and
`check_data` reports them as exceptions of these classes when the plan is empty (previously
`kind: download` and `check_failed`). (3) The stderr contract is unchanged, but
now actually implemented: the `_StderrLines` handler is on the `kartograf` logger
(previously only `kartograf.transport.http`; the other records went through
`logging.lastResort` as raw lines); in text, WARNING/ERROR records
are `Warning:`/`Error:` lines, with `--json` only HTTP retries pass through,
and `KARTOGRAF_DEBUG` lets everything through. No `Notice` codes were added:
the store readers (`list_versions`, `iter_store`) have no `NoticeSink`
outlet. The pyproj warning `Best transformation is not available`
is suppressed only around `TransformerGroup` (`transform/crs.py`).
(4) The `hint` of an error takes `Przyklad:` from the product, country and area selection
of the call (`error_report(..., given=)`, `catalog.hints.example_for`;
CLI and MCP pass the arguments).

---

## ADR-047: Sheet and campaign details in the availability report (KD-1, KD-2)

**Date:** 2026-10-19
**Status:** Accepted; amends ADR-041 (`full_m2`, `sheet_records`, `campaign_coverage`); erratum 1: `AvailabilityRecord.full_sheet`, LAZ limitation and CZ exception in the field documentation; erratum 2: area without land: `complete` unchanged, `no_land` signal (E2E test 0.8.0)

**Context:** Archiwista (SPEC 6.4, 12.4: KD-1, KD-2) computes the coverage labels
"full", "full · N campaigns" and "partial · 58%" from the `check_availability`
report. The report returned only `complete`, `uncovered_m2`
(upper bound) and `campaigns` (all records, including incomplete ones
and ones not selected by the download), so the share of full sheets, the records
that Kartograf will download, and the completeness of campaigns could not be computed without a
copy of Kartograf's rules. Spec:
`docs/superpowers/specs/2026-10-19-availability-sheet-details-design.md`.

**Options:**
- A) New fields in `AvailabilityCombination` computed from the same records
  and the same grid as `complete`; records chosen by the same rules as
  the download.
- B) A separate combination-details function (a second query or a second
  measurement pass).
- C) Only `full_m2`; the consumer computes records and campaigns from `campaigns`.

**Decision:** A. Additively in `kartograf-availability/1`:
- `full_m2` (KD-2): land within YES records; PL `land_px * (target_px -
  missing) // target_px` (for `bbox`/`geometry` exactly `land_m2 -
  missing`; the frame strip of the `sheet` task is neither covered nor missing),
  so in PL `complete <=> full_m2 == land_m2`, while the records alone do NOT give 0.
  CZ: the part of the area rectangle within sheets with a file (the same measure as
  `uncovered_m2`); a complete combination may have `full_m2 < land_m2` when the
  area extends beyond the index sheets.
- `sheet_records` (KD-1): `AvailabilityRecord(sheet, campaign,
  acquisition_date, published, full_sheet, url)` of the records that `download_hint`
  downloads: NMT/NMPT the newest sheet record (ADR-028) and the newest
  YES when the newest is not YES (`--full-sheet`, ADR-033); LAZ tiles
  `select_newest_cover` (ADR-029) from among the combination's tiles (one sheet
  system). CZ: empty.
- `campaign_coverage` (KD-1): `AvailabilityCampaign(campaign, complete,
  full_m2)` for each campaign from `campaigns`, in the same `_measure`
  pass. CZ: empty.
- CLI `elevation availability --details`: share of full sheets (rounded down,
  `<1%`), campaigns separately, campaigns of the records to download.

Rejected: B (a second pass over the same pixels and a second contract);
C (the consumer would have to repeat ADR-028/029/033); `land_px - missing`
(the frame of the `sheet` task would count as covered, the records alone NO > 0).

**Consequences:** Archiwista takes the labels straight from the report ("N
campaigns" = distinct `campaign` of the `full_sheet` records in `sheet_records`).
Cost: one `rasterize` per campaign in the measurement strip; queries and cache
unchanged. Contract test: `sheet_records` == the URLs of the `check_data` plan
from the hint (NMT with `--full-sheet`, LAZ of a year with one sheet system).
LAZ limitation: the hint has no sheet system, so a `--year` download
selects tiles of both systems at once, while the combination has one - for a year with tiles
of PL-1992 and PL-2000 `sheet_records` may differ from what the command
writes (Krakow 2023: the hint of the PL-2000 combination downloads PL-1992 tiles;
described in the field docstring, USAGE 1.7 and ARCHITECTURE 4.9); a LAZ year that
does not cover the area's tiles is rejected by the download (unchanged).

**Erratum 1 (2026-10-19, user review before merge):** the field
`AvailabilityRecord.full` is named `full_sheet`, as in `SkorowidzRecord`,
`LazTile`, the sidecar and the `--full-sheet` flag (in `/1` a rename after
release would require `/2`); the LAZ limitation (two sheet systems) is described
at the field and in USAGE, not only in the ADR; the CZ exception to `complete <=>
full_m2 == land_m2` is added in the class description and in the CHANGELOG.

**Erratum 2 (2026-10-19, E2E test 0.8.0):** a PL area without land (territorial
sea, area outside the state border) has `complete: true`:
the invariant `complete <=> full_m2 == land_m2` stays true (empty land
is entirely covered, `full_m2 == land_m2 == 0`). The signal is the `Info`
`no_land` (`notices.NO_LAND`), the COMPLETE column `brak ladu` and a footer
without a download hint; the rejected alternative `complete = false` for
`land_m2 == 0` would break the invariant. Details: ADR-041 erratum 5.

---

## ADR-048: Adoption of the Nogat standard 2.1: layout, tooling and versions

**Date:** 2026-10-24
**Status:** Accepted; supersedes ADR-009 (the deleted `docs/DEVELOPMENT_STANDARDS.md`)

**Context:** Kartograf follows the Nogat standard 2.1 before the data-output
work. The agent-doable items of phase 2 of the adoption plan (structure and
tooling) are done here; the interface items (phase 4) and the user environment
are listed in `docs/PROGRESS.md`.

**Options:** keep the flat layout and the local gate (no change); adopt the
templates of Nogat `standards/ci/` unchanged (chosen); write project-specific
variants of the gate and CI.

**Decision:**
- `src/kartograf/` layout, uv with a committed `uv.lock`, the gate and CI
  templates unchanged except the two settings at the top of `gate.sh`
  (ECO-011, ECO-012, DEV-7.6, DEV-7.7).
- `develop` carries `0.8.0.dev0` and the changelog has `[Unreleased]` (REL-1.1);
  the release pull request sets `0.8.0`.
- `tests/` is split by what a test needs: `unit` (one module, fakes),
  `integration` (flows across library, CLI and store), `contract` (interface
  parity, JSON contracts, generated files), `support` (shared fakes); the
  `live` marker is the only one in use.
- ruff `E,F,W,I,UP,B,SIM,C4,D` with the numpy convention and mypy strict; the
  tests keep one mypy override (their functions are unannotated), recorded as a
  deviation in `CLAUDE.md`.
- Verbatim copies of the Nogat registry and agent schemas live in
  `schemas/nogat/`; `src/kartograf/_errors.py` is generated from the registry
  by `scripts/generate_errors.py` and a contract test fails when it is stale.

**Consequences:** consumers repeat editable installs and pin the commit until
the tag `v0.8.0` exists (`kartograf>=0.8.0` rejects a development version).
Phases 3 and 4 of the adoption change codes, exit codes and JSON documents
(ERR §4, AGI-4.2) and are breaking changes of the unreleased 0.8.0 (ECO-020).

**Erratum 1 (2026-10-25, step e3 of the adoption):** `README.md` follows the order of DOC-2.1
in English and `CLAUDE.md` follows DOC-3.1 in English, with a `Deviations` section (DEV-1.2);
`tests/contract/test_readme.py` runs the examples of the README (DOC-2.6). The file
`docs/DEVELOPMENT_STANDARDS.md` is deleted because DEV-1.3 forbids a copy of the standard in a
project, and its project rules moved to `CLAUDE.md` and `ARCHITECTURE.md` 4.11 and 5, so
ADR-009 is superseded.

## New ADR template

Copy the block below when adding a decision: the next number, a status from the
vocabulary at the beginning of the file, a new row in the index and cross-references on both
sides of the relation. Add errata at the end of the entry.

```markdown
## ADR-XXX: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Accepted — partly superseded by ADR-YYY (scope) | Accepted — amended by ADR-YYY (scope) | Superseded by ADR-YYY | Rejected

**Context:** Why the topic arose.

**Options:**
- A) ...
- B) ...

**Decision:** Which option and why.

**Consequences:** What follows from it.

**Erratum 1 (YYYY-MM-DD, source/reason):** Added later.
```
