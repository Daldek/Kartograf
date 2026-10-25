# SCOPE.md - Scope of the Kartograf project
**Tool for Downloading Spatial Data**

**Version:** 3.28
**Date:** 2026-10-17
**Status:** Release v0.8.0 (2026-10-17)

---

## 1. Project purpose

**Kartograf** is a tool for downloading spatial data from public services of GUGiK (Poland), CUZK (Czechia, since v0.7.0), Copernicus and ISRIC: elevation models and point clouds, orthophotos and images, land cover and soils, boundaries, cadastre and land registry, 3D models, water network, geographic names, topographic maps and geodetic control networks (section 2). Further countries (DE, SK) — section 3.1.

### 1.1 Problem

Downloading spatial data from various sources requires:
- Knowledge of identification systems (sheet codes (Polish godła), TERYT, bbox)
- Navigating various web interfaces and APIs
- Manual organisation of downloaded files
- Different authentication protocols (OAuth2, API keys)

### 1.2 Solution

Kartograf automates this process by offering:
- **Unified API** - a uniform interface for different data sources
- **Sheet code parser** - validation and parsing of topographic map sheet codes
- **Data providers** - an abstraction over various services (GUGiK, CUZK, Copernicus, ISRIC)
- **Area selection** - sheet code, bbox, geometry file (SHP/GPKG), unit code (TERYT, KU), whole country
- **Automatic download** - downloading many files with one command
- **File organisation** - automatic directory structure

### 1.3 Users

1. **Hydrograf/Hydrolog developers** - integration as a Python library
2. **GIS specialists** - CLI for downloading data
3. **Hydrologists** - soil data and HSG for the SCS-CN method

---

## 2. Scope - Version 0.8.0

### 2.1 NMT (digital terrain model) - IN SCOPE

```text
# Features:
- PL-1992 sheet code parser (SheetParser): scales 1:1M to 1:10k
- PL-2000 sheet code parser (Parser2000): scales 1:10k to 1:500, 4 zones (EPSG:2176-2179)
- Automatic system detection: SheetParser automatically recognises PL-1992 vs PL-2000
- Sheet hierarchy (get_parent, get_children, get_all_descendants)
- Sheet bounding box (EPSG:2180, EPSG:4326, EPSG:2176-2179)
- Reverse lookup: bbox → sheet codes (find_sheets_for_bbox, find_sheets_2000_for_bbox;
  bbox in EPSG:2180, EPSG:4326 or EPSG:2176-2179 for both systems)
- Reverse lookup: geometry file → sheet codes (find_sheets_for_geometry)
- Area selection: sheet code, bbox, geometry file (SHP/GPKG)
- Download by sheet code → ASC (OpenData); sheet record from the GUGiK WFS
  sheet index (since 0.8.0; yearly types from GetCapabilities, hard filter on sheet code,
  CRS, resolution and format — ADR-041)
- `provider.download_bbox` (outside the version store): NMT 1 m KRON86
  (TIFF float32), EVRF2007 and NMPT (multipart ASC -> single-band GeoTIFF
  float32 with heights), bbox aligned to the 1 m EPSG:2180 grid;
  `DownloadManager.download_bbox` removed in 0.8.0 (D27).
  CLI `--bbox` without `--cutout`: OpenData sheets.
- bbox cutout from GUGiK WCS: `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,
  EPSG:3045}` in `--bbox`/`--geometry` mode for NMT **and NMPT** 1 m
  (`download_pl_cutout`/`check_pl_cutout`; in the CLI via `download_data`);
  PRG land mask `A00 - W02 - W03` and nodata -9999 outside land,
  0.0 on land preserved; bbox aligned OUTWARDS to the 1 m sheet
  grid (`k + 0.5`), local pinned reprojection.
  WCS shows the server's flight composition, not necessarily the latest
  exactly 1 m sheet according to ADR-028; for 0.5 m flights the 1 m result
  is decimation. Since 0.8.0 `bbox/<coords>.tif` without a date is
  a hard link to a version; by default the local version without PRG/WCS queries,
  `--force` downloads again (same content = no changes).
  No campaign/year selection; a resolution other than 1m and archives
  (`--format`) with `--cutout` = `Error:` — they remain available as sheets
  without this flag.
- Resolutions (variant registry `kartograf.sources.variants`, ADR-041;
  list: `kartograf elevation list-sources`): EVRF2007 ASC grids 0.15m,
  0.5m, 0.6m, 1m, 5m, 10m; KRON86 0.5m, 1m. `--resolution` is required
  when the format and vertical CRS give more than one label
- GUGiK archives as 1:1 source files (`--format XYZ|ASCII-NMT|TBD|TIN|
  TTN|GRD|DXF|DGN`, among others TBD 1–50 m): without conversion, cutout or mosaic,
  versions in the store (segment with format token, e.g.
  `nmt/pl_1992_tbd_25m_kron86`); sheets (various scales) from the sheet index
- Vertical CRSs: KRON86, EVRF2007 (availability per variant from the registry)
- Availability report (`kartograf elevation availability` /
  `check_availability`, ADR-041): for a PL area, combinations of year × sheet
  system × resolution × vertical CRS × format with completeness of
  full sheets (YES) on PRG land, without downloading data (also NMPT
  and LAZ; since ADR-047 also `full_m2`, `sheet_records` and `campaign_coverage`;
  USAGE 1.7, ARCHITECTURE 4.9)
- PL-2000 1:10000 sheet code: in the CLI and `download_data` `--scale` is required
  (error before network access, list of scales); provider/`DownloadManager` called
  without a scale, when GUGiK has only child sheets, gives `NoCoverageError`
  with the hint `--scale 1:2000` (no silent PL-1992 fallback download)
- NMT 100 m (0.8.0, plan E1, ADR-043 D10): `--resolution 100m` -> voivodeship
  files for the area from the GUGiK ATOM feed (ZIP with XYZ 1:1,
  `nmt/pl_1992_100m/teryt/<woj>.zip`, 2019 release); vertical CRS
  unknown (GUGiK does not declare it: sidecar `vertical_crs: null`
  with annotation, `--vertical-crs` = error); without sheets, flights or cutout
- 8-part PL-1992 sheet codes (0.8.0, plan E1): quarters of a 7-part sheet
  (`N-34-50-A-c-3-2-3`, label `1:5000`; true orthophoto sheets)

# Source: GUGiK (Główny Urząd Geodezji i Kartografii)
# API: WFS (sheet index), WCS (1 m cutout), OpenData
```

**Scale labels (PL-1992).** Kartograf scale labels are one level
finer than the GUGiK nomenclature: a 7-part sheet code (N-34-130-D-d-2-4) has here the
label `1:10000`, while at GUGiK it is an archiving module of 1:5000; the 1-144 grid
(label `1:200000`) has the dimensions of the official 1:100000 sheet (20' x 30').
The labels remain for public API and CLI `--scale` compatibility; aliases
are planned in the next major version (see the `SheetParser` docstring).

**Edge convention.** `find_sheets_for_bbox` / `find_sheets_for_geometry`
require a positive intersection area — touching edges are NOT an
intersection. A bbox equal to a sheet in EPSG:4326 therefore returns only its own
sheets (`N-34-130-D` at scale 1:50000 → 4, not 9); in EPSG:2180 (the default
`--bbox-crs`) the sheet envelope passes through the wider WGS84 envelope
and includes fragments of neighbours (16 instead of 4). A bbox degenerated to a point →
exactly one sheet. An unknown `sheet_system=` value gives `ValidationError`.

### 2.2 NMT, NMPT and LAZ — Czechia (CUZK; NMT since v0.7.0, NMPT and LAZ since 0.8.0) - IN SCOPE

```text
# Features (DMR — Digitalni model reliefu, equivalent of NMT;
# DMP — Digitalni model povrchu, equivalent of NMPT; model from --resolution):
- DMR 5G (resolution 2m) — download by sheet code TM33 (2x2 km grid,
  EPSG:3045, computable) OR by bbox via exportImage (ArcGIS ImageServer)
- DMR 4G (resolution 5m) — download by sheet code SM5 (sheet index
  KladyMapovychListu, EPSG:5514; the sheet exists only in 5m, so the CLI without
  `--resolution` downloads 5m, and `--resolution 2m` with sheet code SM5 is an error)
  OR by sheet code TM33 OR by bbox via exportImage
- DMP OK (NMPT 0.5m) — like DMR 4G (sheet SM5 without `--resolution`, tile
  TM33, bbox); DMP 1G (NMPT 2m) — like DMR 5G (tile TM33, bbox)
- Ready-made openzu files: sheet SM5 (EPSG:5514, Bpv) and from 0.8.0 tile TM33
  DMR 4G/DMP OK in EVRF2007 (ETRS89 file, EPSG:3045, no transformation);
  the remaining TM33 tiles = exportImage + local warp onto the tile grid
- LAZ (`--product laz`): requires `--model dmr5g|dmr4g|dmp1g|dmpok`;
  .laz file 1:1 from the openzu ZIP, no point transformation — `--vertical-crs
  Bpv` = SM5 sheets (EPSG:5514), `EVRF2007` = TM33 tiles (EPSG:3045);
  sheet code or area (sheets from the index), no `--cutout`
- Area selection: sheet code (TM33/SM5), bbox, geometry file — `--country
  {pl,cz,auto}`; `auto` detects the country from the sheet code/bbox, splits a cross-border
  bbox/geometry into separate files per country (no merging — today the
  consumer merges, e.g. Hydrograf; merging PL+CZ into one surface (R6) has no
  assigned release — section 3.1). A raster area reaching CZ is always a cutout and requires
  `--cutout --horizontal-crs` (ADR-038); under `auto` the PL part is then
  a WCS cutout. LAZ under `auto`: PL tiles and CZ sheets in one task
- **Local** horizontal reprojection (rasterio.warp + pinned operation; the server
  receives requests only in native EPSG:5514 — ADR-024):
  `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,EPSG:3045}` (natively
  `EPSG:5514`) — only in `--bbox`/`--geometry` mode (with a sheet code = error)
  S-JTSK → ETRS89 datum step pinned to the Czech operations EPSG:1622/1623
  (declared accuracy 1.0 m; ADR-024 erratum 2)
- Native vertical CRS: Bpv (Baltic 1957, EPSG:8357), for ETRS89 files
  (TM33 tiles, LAZ TM33) EVRF2007 (EPSG:5621); optional
  raster transformation Bpv → EVRF2007 (pinned operation 0.1 m); KRON86
  unreachable (no public Bpv→KRON86 grids)
- Report `elevation availability --country cz|auto`: index sheets
  and one `HEAD` per file (publication date, size), without survey years
- `extra.parent_request` in bbox/geometry mode sidecars — grouping
  the files of one task on both sides of the PL/CZ border

# Source: CUZK (Český úřad zeměměřický a katastrální)
# API: ArcGIS REST (query, exportImage) + openzu files (ZIP with TIFF+TFW or .laz)
# Licence: CC BY 4.0
```

Contours CZ (0.8.0, plan E1): `elevation download --product contours
--country cz --format SHP|DGN` - ZABAGED CUZK contours, SM5 sheet ZIP
from openzu 1:1 (`contours/cz_zabaged_<format>/`; S-JTSK, Bpv heights;
signal `http`), SM5 sheet code or SM5 sheets of the area from the index
`KladyMapovychListu`; without cutout and without a REST channel (ADR-043).

**Out of scope (no assigned release):** administrative boundary polygon
(instead of the rectangular country envelope) — sections 3.1 and 3.2.
Other CZ data: orthophoto (2.4), CUZK vector data (2.14), Geonames
and ZTM (2.15), Bodove pole and QGZU-2013 (2.16).

### 2.3 NMPT (digital surface model) - IN SCOPE

```text
# Features:
- Digital Surface Model (DSM) — terrain + objects (trees, buildings)
- Download by sheet code → ASC (OpenData)
- Download by bbox from the library (`provider.download_bbox`) -> GeoTIFF
  float32 with WCS heights (ASC multipart);
  CLI `--bbox` without `--cutout` downloads OpenData sheets,
  with `--cutout --horizontal-crs` a WCS cutout with a land mask
- Resolutions (variant registry): ASC grids EVRF2007 0.5m, 0.6m, 1m;
  KRON86 0.5m, 1m; XYZ archives 0.5m and 1m (KRON86). `--resolution`
  required since 0.8.0 (BREAKING; previously only 1m); `--cutout` cutout
  only 1m
- Vertical CRS: KRON86, EVRF2007
- Inherits from GugikProvider (shared download logic)

# Source: GUGiK
# API: WFS (sheet index), WCS (1 m cutout), OpenData
```

### 2.4 Orthophoto - IN SCOPE

```text
# Features:
- Standard Resolution aerial imagery (resolution per campaign, e.g. 25 cm, 10 cm)
- Download by sheet code → TIF (OpenData)
- Download by bbox → GeoTIFF (WCS) — from the library (`provider.download_bbox`, outside the store);
  CLI `--bbox` downloads OpenData sheets
- No vertical CRS (2D RGB); latest compatible record of the `color` variant
  (`RGB`/`CIR`/`B/W`, required in the API; CLI downloads RGB) from
  GetCapabilities/GetFeatureInfo; `GugikOrtoProvider(color="CIR")` selects the
  infrared variant
- Supported WCS formats: GTiff, PNG, JPEG
- Cutout in the store (0.8.0, ADR-042 D14): `imagery download --product orto
  --country pl --bbox|--geometry --cutout --horizontal-crs EPSG:2180
  --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` -> one GeoTIFF
  RGB `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif` (WCS Standard/High,
  0.1 m grid, 200 x 200 m chunks, no resampling or land mask;
  `download_image_cutout`/`check_image_cutout` with `product="orto"`)
- CZ orthophoto (0.8.0, ADR-042 D13): `--country cz` (sheet SM5 or area)
  -> JPEG + `.jgw`/`.TM33N.jgw`/`.TM34N.jgw` from ATOM CUZK 1:1 in
  `orto/cz_sjtsk/`, current vintage only (`download_cz_orto_sheet`)
- GUGiK imagery of plan E1 (0.8.0, ADR-043): `imagery download --product
  intensity` (LIDAR intensity images, 1 band 0.25 m, PL-1992
  and PL-2000 sheets), `--product true-orto` (true orthophoto of selected
  cities, 8-part sheet codes PL-1992; WCS cutout `True_Orthoimagery`
  `--resolution 0.05m`-`1m`) and `--product oblique-orto` (oblique
  orthophoto, PL-2000 sheets, sheet = 4 direction files, `--direction`);
  orthophoto sheet track (campaigns, `--year`, `index` signal), file
  over 100 MiB announced by its size from `HEAD`

# Source: GUGiK (PL), CUZK (CZ)
# API: WCS, WMS GetFeatureInfo, OpenData; ATOM CUZK
```

### 2.5 LAZ (LIDAR point clouds) - IN SCOPE

```text
# Features:
- ALS point clouds (LIDAR survey data), .laz format
- Area-based discovery via sheet code (≤1:10000) / bbox / geometry → WFS
  GetFeature, bbox and envelope in EPSG axis order (N,E), intersection filter;
  an error for a single yearly release aborts discovery (`DownloadError`)
- Tiles finer than 1:10000 (one 1:10000 sheet code → many .laz tiles)
- url_do_pobrania taken directly from the WFS attribute (tile sheet code not parsed)
- By default the newest tile per area (ADR-029); flags --year/--min-year/--max-year
  (year range, ADR-032), --vertical-crs, --min-density, --all-campaigns (section 2.12)
- Two vertical CRSs (selection required since 0.8.0): EVRF2007 (2018+), KRON86 (legacy, 2010-2019)
- Parallel download (--workers); tiles as versions in the store
  (ADR-036 D26): a tile with a local version is not downloaded again,
  a newer flight (different files) is downloaded by default; --check-updates,
  --upgrade, --force, --plan
- Library: download_data(product="laz", ...) (= CLI) or
  download_laz_area (bbox in any CRS; selection + download + sidecars,
  result LazDownloadResult: files/failed/superseded/stale/notices) and
  check_laz_area (plan without downloading)
- Failure of even one tile = Error: with the full list, code 1 (downloaded ones are kept)
- CZ (plan B, section 2.2): download_cz_laz/check_cz_laz (model=, sheet code
  or bbox; CzLazResult: sheets/files/failed/stale/notices); a file
  failure = Error: for the sheet, code 1 (the rest are kept)

# Source: GUGiK (CZ: CUZK, section 2.2)
# API: WFS (GetCapabilities + GetFeature), OpenData (CZ: KladyMapovychListu + openzu)
```

### 2.6 Land cover - IN SCOPE

```text
# BDOT10k (GUGiK):
- 15 layers (12 land cover PT* + 3 hydrographic SW*)
- Download of the whole county package; for GPKG an optional layer filter
  (`--layers`/`layers=`, e.g. SWRS,PTWP) and the original ZIP (`--keep-raw`)
- Download by TERYT (county)
- Download by sheet code, bbox (any supported CRS, `--bbox-crs`)
  or geometry — the package of EVERY county in the area (`--workers` in parallel)
- Format: GeoPackage (default) or Shapefile (.zip archive, not unpacked)
- Automatic layer merging preserving the rtree spatial index; the GPKG is
  assembled in a local temporary directory and moved to the store
  (SQLite does not write on a network share — works on CIFS/SMB without byte-range
  locks)
- Version store (0.8.0): landcover/pl_bdot10k_gpkg[_<layers>]/teryt/<T>,
  signal: none (local version unchecked, --force downloads); keep_raw =
  separate ZIP version; area = every county (`LandCoverReport`), error per county
- Annual archive (0.8.0, ADR-042 D11): `--year 2014..2025` (state
  at the beginning of the year) with the required `--format GML|SHP` — the original county
  ZIP package 1:1 in landcover/pl_bdot10k_<format>_<year>/teryt/<T>.zip
  (e.g. `pl_bdot10k_shp_2024/teryt/1261.zip`); area = packages of every
  county (PRG); version label = year, signal: none; GPKG, `--layers`,
  `--keep-raw` with `--year` = error, `--format GML` without `--year` = error
  with a hint; identical year (the same SHA-256 in another county
  release) without a duplicate — hard link, status `relabeled` (D7);
  no county package (404) = NoCoverageError for that county

# BDOO (GUGiK, 1:250 000) — `--product bdoo` (pl.gugik.bdoo, 0.8.0, ADR-043):
- voivodeship GML package per year (`--year` required: 2015, 2021-2026),
  ZIP 1:1 -> landcover/pl_bdoo_<year>/teryt/<voivodeship>.zip; `--teryt` 2 digits
  (county code = error with a hint), area (--bbox/--sheet/--geometry)
  = voivodeship packages of its counties according to PRG
- `--layers` = ZIP of files of the selected classes of the year (list: landcover
  list-layers --product bdoo) -> landcover/pl_bdoo_<year>_<classes>/; a class
  without a file in the package = Info (classes_absent), a class outside the year = error
- version label = year, signal: none

# CORINE Land Cover (Copernicus):
- 44 land cover classes
- Years: 1990, 2000, 2006, 2012, 2018
- Download by sheet code, bbox or geometry (no TERYT)
- Format: GeoTIFF (CLMS API) or PNG (WMS fallback: EEA Discomap, for 1990
  DLR; sidecar extra.fallback = "wms_png")
- OAuth2 RSA authentication (optional; CLMS_CREDENTIALS on every system,
  Keychain only on macOS)
- Auth Proxy for credentials isolation
- Version store (0.8.0): CLMS in landcover/eu_corine_<year>/ with the release
  label from the CLMS catalogue (metadata signal), WMS preview separately
  in landcover/eu_corine_<year>_preview/ (label = download date)

# ZABAGED, Data50 and Data250 (CZ) in `landcover download --product`: section 2.14
# All land cover sources: version sidecar <file>.meta.json (section 2.11)
```

### 2.7 SoilGrids (soil data) - IN SCOPE

```text
# ISRIC SoilGrids:
- 11 soil parameters (clay, sand, silt, soc, pH, etc.)
- 6 depths (0-5cm to 100-200cm)
- 5 statistics (mean, Q0.05, Q0.5, Q0.95, uncertainty)
- Resolution: 250m (global)
- Download by sheet code, bbox or geometry (WITHOUT TERYT — see 3.2)
- Format: GeoTIFF
- Version store (0.8.0): soil/global_soilgrids_<property>_<depth>_<stat>/,
  label = SoilGrids release from GetCapabilities (metadata signal)

# Source: ISRIC (International Soil Reference and Information Centre)
# API: WCS
```

### 2.8 HSG (Hydrologic Soil Groups) - IN SCOPE

```text
# HSG calculation for the SCS-CN method:
- Texture classification by the USDA triangle (12 classes)
- Texture → HSG mapping (A, B, C, D)
- Inputs clay/sand/silt = SoilGrids versions in the same store
  (missing ones are downloaded); the same inputs = HSG version reused
- Coverage statistics for each group
- Output format: GeoTIFF (values 1-4, 0 = nodata) in
  hsg/global_soilgrids_<depth>_<stat>/
- Selection: --sheet, --bbox, --geometry
- Version sidecar <file>.meta.json (extra.derived = "hsg", source layers,
  depth, statistic, class codes, source_files with sha256 of the inputs)

# Module: kartograf.hydrology.hsg
```

### 2.9 CLI interface - IN SCOPE

```bash
# Commands:
kartograf sheet parse <sheet_code>                    # info about the sheet code (PL-1992 or PL-2000)
kartograf sheet parse 6.179.12.20               # PL-2000 auto-detection
kartograf elevation download --sheet <sheet_code> --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # download NMT
kartograf elevation download --sheet <sheet_code> --product nmpt --resolution 1m --vertical-crs EVRF2007 --root ./data # download NMPT (--resolution required since 0.8.0)
kartograf imagery download --sheet <sheet_code> --product orto --root ./data # download orthophoto
kartograf elevation download --sheet <sheet_code> --product laz --vertical-crs EVRF2007 --root ./data # download LAZ point clouds (many tiles)
kartograf elevation download --bbox ... --product laz --year 2024 --min-density 12 --country pl --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox min_x,min_y,max_x,max_y --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data # NMT for a bbox
kartograf elevation download --bbox ... --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --root ./data # NMT in the PL-2000 system (1:2000 sheets)
kartograf imagery download --bbox ... --product orto --country pl --sheet-system 1992 --root ./data # orthophoto for a bbox
kartograf imagery download --bbox ... --product orto --country pl --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m --root ./data # WCS cutout
kartograf imagery download --sheet CTES96 --product orto --root ./data # CZ orthophoto (sheet SM5: JPEG + 3 JGW)
kartograf landcover download --product zabaged --bbox=... --bbox-crs EPSG:5514 --root ./data # ZABAGED (22 layers, EPSG:5514); --whole-country --horizontal-crs EPSG:5514|EPSG:3045
kartograf boundaries download --product admin --country cz --level obec --bbox=... --bbox-crs EPSG:5514 --root ./data # RUIAN; auto: --level pl=gmina,cz=obec
kartograf hydro download --product network --country cz --bbox=... --bbox-crs EPSG:5514 --root ./data # HY-NET; --whole-country (EPSG:3045)
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data # NMT from a geometry file
kartograf elevation download --geometry area.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --sheet <sheet_code> --resolution 5m --product nmt --vertical-crs EVRF2007 --root ./data # NMT 5m
kartograf elevation download --sheet <sheet_code> --resolution 0.5m --product nmt --vertical-crs EVRF2007 --root ./data # NMT 0.5m (labels from the variant registry; elevation list-sources)
kartograf elevation download --bbox ... --country pl --sheet-system 1992 --product nmt --format TBD --resolution 25m --vertical-crs KRON86 --root ./data # GUGiK archive as a source file (ADR-041)
kartograf elevation list-sources                   # NMT/NMPT/LAZ variants from the registry (ready-made flags), no network
kartograf elevation availability --product nmt --country pl --bbox ... # availability report: set of full sheets per year/system/resolution/format, without downloading
kartograf elevation availability --product nmpt --sheet <sheet_code> --details # codes of incomplete sheets and download commands; --json = check_availability
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv --root ./data # DMR 5G (CZ), sheet code TM33
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv --root ./data # DMR 4G (CZ, 5m), sheet code SM5, country from the sheet code
kartograf elevation download --sheet CTES96 --product nmpt --resolution 0.5m --vertical-crs Bpv --root ./data # DMP OK CZ, sheet SM5
kartograf elevation download --sheet 760_5518 --country cz --product nmpt --resolution 0.5m --vertical-crs EVRF2007 --root ./data # DMP OK native tile TM33
kartograf elevation download --sheet CTES96 --country cz --product laz --model dmr5g --vertical-crs Bpv --root ./data # CZ LAZ from ZIP, no transformation
kartograf elevation availability --product laz --country cz --sheet CTES96 # CZ report without downloading files
kartograf elevation download --bbox ... --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv --root ./data # cross-border bbox -> cutout per country
kartograf elevation download --bbox ... --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv --root ./data # local reprojection (pinned)
kartograf elevation download --bbox ... --country pl --cutout --horizontal-crs EPSG:2180 --product nmt --vertical-crs EVRF2007 --root ./data # NMT/NMPT 1 m WCS cutout + PRG mask (ADR-035)
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m --root ./data # Bpv -> EVRF2007 (EPSG:5621)
kartograf elevation download --sheet <sheet_code> --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # all GUGiK campaigns of the sheet (ADR-030)
kartograf elevation download --sheet <sheet_code> --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # latest flight of the year (ADR-032)
kartograf elevation download --sheet <sheet_code> --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # all flights of the year
kartograf elevation download --sheet <sheet_code> --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # latest flight, not older than the year
kartograf elevation download --bbox ... --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data # latest flight up to the year (hard link never backwards)
kartograf elevation download --bbox ... --product laz --all-campaigns --country pl --vertical-crs EVRF2007 --root ./data # LAZ without coverage deduplication
kartograf landcover download --product bdot10k --teryt <code> --root ./data  # area: --bbox [--bbox-crs] / --sheet / --geometry; --layers, --keep-raw, --workers, -q
kartograf landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP --root ./data # BDOT10k yearly archives (2014-2025, GML|SHP, ZIP 1:1)
kartograf landcover download --product corine --sheet <sheet> --root ./data --year 2018
kartograf soil download --property <param> --root ./data --depth 0-5cm --stat mean # --sheet/--bbox (without --teryt)
kartograf landcover list-sources
kartograf landcover list-layers --product <produkt>
kartograf soil hsg --sheet <sheet> --root ./data --depth 0-5cm # compute HSG from a SoilGrids version
kartograf boundaries download --product admin --country pl --level gmina --bbox ... --root ./data # PRG boundaries of the area (GPKG from WFS); --teryt 12 / --whole-country --country pl
kartograf boundaries list-sources
kartograf cadastre download --product map --teryt 1261 --root ./data # EGiB of the county (GPKG); area: --country pl --bbox/--sheet/--geometry
kartograf cadastre list-sources
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 --root ./data # CityGML 3D models; --lod 2 (2017) without --year
kartograf models3d list-sources
kartograf elevation download --product contours --country cz --format SHP --sheet CTES96 --root ./data # ZABAGED contours CZ (ZIP of sheet SM5; SHP|DGN)
kartograf elevation download --product nmt --resolution 100m --country pl --bbox ... --root ./data # NMT 100 m: voivodeship XYZ files from the ATOM feed
kartograf imagery download --product intensity --sheet <sheet_code> --root ./data # LIDAR intensity images; also --product true-orto, oblique-orto (--direction)
kartograf landcover download --product bdoo --teryt 12 --year 2023 --root ./data # BDOO: voivodeship GML package; --layers selected classes
kartograf landcover download --product data50 --bbox=... --bbox-crs EPSG:5514 --root ./data # Data50/Data250 CZ; --whole-country --horizontal-crs EPSG:5514|EPSG:3045
kartograf boundaries download --product addresses --country pl --bbox ... --root ./data # PRG address points and streets; --teryt <4 digits>; --whole-country --format SHP|GML
kartograf boundaries download --product special --country pl --bbox ... --root ./data # 44 kinds of PRG special boundaries (OGC API); --whole-country --format SHP|GML
kartograf boundaries download --product geomorphology --country cz --level celek --bbox=... --bbox-crs EPSG:5514 --root ./data # CZ geomorphological units
kartograf cadastre download --product prices --teryt 1261 --root ./data # RCN: export for a county (4 digits) or voivodeship (2 digits)
kartograf cadastre download --product map --ku 623164 --format SHP --root ./data # CZ cadastral map (SHP|DXF|DGN|VFK); area: KU by RUIAN
kartograf models3d download --product mesh --country pl --bbox ... --root ./data # city mesh (OBJ tiles); --product trees --teryt <code> (CityGML trees)
kartograf names download --product geographic --country pl --bbox ... --root ./data # PRNG (CZ: Geonames); --product world; --whole-country --format
kartograf names list-sources
kartograf maps download --product topographic --country pl --sheet <sheet_code> --scale 1:10000 --format TIFF --root ./data # BDOT10k visualisations (CZ: ZTM)
kartograf maps list-sources
kartograf geodesy download --product control --country pl --network vertical --bbox ... --root ./data # control points; --teryt (county package), sheet archives
kartograf geodesy download --product geoid --country pl --whole-country --root ./data # PL-geoid2021 (CZ: QGZU-2013)
kartograf geodesy list-sources
kartograf project init --root ~/dane/kartograf # project manifest with a shared store
kartograf project add teren elevation download --product nmt --sheet <sheet_code> --resolution 1m --vertical-crs EVRF2007
kartograf project download                 # pin task versions; --check-updates/--upgrade/--force
kartograf project status                   # existence and size, without reading data
kartograf project verify                   # SHA-256 of files and sidecars
kartograf cache stats|clear|path           # metadata cache (SQLite)
kartograf commands list --json                   # command catalog (groups, commands, ...); `commands schema --command "<group> <command>"`: options, allowed values, examples (ADR-052)
kartograf elevation availability --product nmt --sheet <sheet_code> --json # --json in every command: one kartograf-result/1 envelope, error kartograf-error/1 on stderr, exit codes of the Nogat registry (USAGE 9.3)
kartograf-mcp                              # MCP server (stdio; extra `kartograf[mcp]`): 39 tools 1:1 with commands, read only and plans by default; `--allow-writes --allow-dir DIR` allows writing (USAGE 9.6)
# Full list of options: kartograf <group> <command> --help
```

### 2.10 Python API - IN SCOPE

```python
# Public API — source of truth: src/kartograf/__init__.py (__all__); the list below
# is consistent with it and updated together with it.
from kartograf import (
    # Cache
    MetadataCache,
    # Notices
    Notice,
    # Core
    SheetParser, Parser2000, ParserTM33, BBox, find_sheets_for_bbox,
    find_sheets_2000_for_bbox, find_sheets_for_geometry, get_overall_bbox,
    transform_bbox, parent_request_for,
    # Download (command level: `kartograf elevation download` / `imagery download`, spec 4.1)
    download_data, check_data, DataReport, UnitFile, UnitFailure,
    # Download (collections: `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`, ADR-042)
    download_collection, check_collection, CollectionReport,
    # Download (orthophoto: CZ SM5 sheet; PL image cutout, ADR-042 D13-D14, ADR-044)
    download_cz_orto_sheet, check_cz_orto_sheet, CzOrtoResult,
    download_image_cutout, check_image_cutout, ImageCutoutResult,
    # Availability report (`kartograf elevation availability`, ADR-041)
    check_availability, AvailabilityReport, AvailabilityCombination,
    AvailabilityRecord, AvailabilityCampaign, AvailabilityArea,
    # Download (NMT)
    DownloadManager, DownloadProgress, DownloadResult, CampaignRef, FileStorage,
    # Download (versioned store, update plan)
    UpdateMode, VersionedFile, VersionRef, PlanItem, UpdatePlan,
    # Download (PL cutout: WCS ADR-035)
    PlCutoutResult, check_pl_cutout, download_pl_cutout,
    # Download (CZ cutout, countries)
    CountryPart, countries_for_bbox, split_bbox_by_country, CzCutoutResult,
    check_cz_cutout, download_cz_cutout,
    # Download (CZ sheet: SM5 sheet / TM33 tile, R4)
    CzSheetResult, check_cz_sheet, download_cz_sheet,
    # Download (LAZ CZ: models, SM5/TM33, HTTP, plan)
    CzLazResult, CzLazFailure, check_cz_laz, download_cz_laz,
    # Download (LAZ PL: WFS, campaigns)
    LazDownloadResult, LazTileFailure, check_laz_area, download_laz_area,
    # Land cover and soil (command level, ADR-044)
    download_landcover, check_landcover, LandCoverReport,
    download_soil, check_soil, SoilReport, Edition,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikLazProvider, LazTile, LazTileSelection, SupersededLazTile,
    LandCoverProvider, Bdot10kProvider, Bdot10kPackage, CorineProvider,
    SoilGridsProvider, CuzkRasterProvider, create_cz_raster_provider,
    CuzkLazProvider,
    # TERYT (PRG)
    discover_teryts_for_bbox, teryt_for_point,
    # Hydrology
    calculate_hsg, check_hsg, HsgReport, hsg_statistics, hsg_from_rasters,
    # Project manifest (kartograf-project/1, ADR-040)
    init_project, open_project, add_project_task, remove_project_task,
    download_project, check_project, get_project_status, verify_project,
    Project, ProjectTask, PinnedFile, ProjectReport, TaskResult,
    ProjectCheck, FileCheck,
    # Transport and mosaic (stable since 0.7.1)
    get_with_retry, make_gugik_session, mosaic_and_crop, check_source_grid,
    # Store reading without writing (Archiwista, ADR-045, ARCHITECTURE 3.3.1)
    list_segments, list_partitions, iter_store, StoreEntry, read_sidecar, Sidecar,
    describe_segment, SegmentInfo, file_footprint, Footprint, link_target,
    pinned_transform, PinnedTransform,
    # Command catalog, command layer and JSON documents (agent interface, ADR-046, USAGE 9)
    list_commands, command_schema, CommandList, CommandCatalog,
    parse_command, validate_command, format_command, run_command, check_command,
    CommandCall, describe_sheet, SheetInfo, find_sheets, SheetList,
    list_sources, SourceList, list_layers, LayerList,
    get_cache_info, get_cache_path, clear_cache, CacheInfo,
    describe_store, StoreOverview, list_store_entries, StoreEntries,
    read_store_sidecar, StoreSidecar, ErrorReport, error_report,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError, NoCoverageError,
    YearRangeError, CacheError, InvalidSidecarError, UsageError, ForbiddenError,
    MissingDependencyError,
    # Version
    __version__,
)
# Registry of NMT/NMPT/LAZ variants (ADR-041) — data module outside __all__:
# from kartograf.sources.variants import variants, ProductVariant, IndexRef
```

### 2.11 Data layout on disk - IN SCOPE

- `data/<produkt>/<country>_<crs>[_<variant>][_<vcrs>]/...` (ADR-026);
  canonical segment table and the 0.6.x→0.7.0 migration:
  `docs/ARCHITECTURE.md` section 3
- CZ cutouts and PL digital terrain model (NMT)/digital surface model (NMPT) 1 m cutouts (only with `--cutout`; without
  this flag PL stores sheets in the sheet code hierarchy) in
  `<segment>/bbox/<coords>.tif` — a link to the version in
  `<segment>/versions/bbox/` (D15)
- `<crs>` in the segment (`pl_1992` vs `pl_2000`) is decided by the sheet code format
  of each file separately — one old directory (e.g. `orto/`) splits
  into two segments during migration; exception: LAZ tiles — the CRS comes from `uklad_xy`
  of the tile (`LazTile.system`), and only secondarily from the sheet code format
- Versioned store (ADR-036, since 0.8.0; every product: PL NMT/NMPT/orthophoto sheets,
  LAZ tiles, CZ sheets and cutouts, PL cutouts, land cover, HSG and collections): real files in
  `<segment>/versions/<hierarchy>/<date>_<id>_<sha8>/...`, immutable
  (version sidecar written once, exclusive write), standard path =
  hard link to the latest local version (no copies and no symlinks; a file
  system with hard links is required); `kampanie/` from 0.7.x without migration;
  modes `--check-updates`/`--upgrade`/`--force`, plan `kartograf-plan/1`
  for every track `elevation download`, `imagery download`, `landcover download`, `soil download` and `soil hsg`
  and `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`
  (track `collection`) (freshness signal per channel: sheet index (Polish skorowidz) or index
  record, `ETag`/`Last-Modified` of CUZK files, release from the ATOM feed,
  SoilGrids and CORINE CLMS; none for WCS/`exportImage`, BDOT10k and most
  GUGiK collections)
- A second link `<segment>/full_sheet/<hierarchy>/<sheet_code>.<ext>` to the
  latest local full flight (ADR-033); `list_files()` skips it,
  `delete()` removes both links
- Land cover and HSG in segments `landcover/`, `soil/`, `hsg/` (spec 3.4,
  ARCHITECTURE 3.3 rule 8); `--root` = store root
- Collections (ADR-042 D8, extension of rule 8):
  `<group>/<country>_<source>[_<tokens>]/{teryt/<T>|bbox/<coords>|country/<code>|ku/<code>|<sheet code hierarchy>|<zone>/<file>}<ext>`,
  versions in `<segment>/versions/<same hierarchy>/`. Tokens (`[a-z0-9.-]`)
  = content variant (level, LoD, vintage, network, scale, format); the area result (always GPKG
  in the native CRS of the service, `coords` in that CRS) has no format token,
  the package and the country file have the source format token, when the product has several
  formats or also an area result. Examples:
  `boundaries/pl_prg_gmina/bbox/<coords>.gpkg`, `boundaries/pl_prg_gml/teryt/12.zip`,
  `boundaries/pl_prg_shp/country/pl.zip`, `cadastre/pl_egib_gpkg/teryt/1261.gpkg`,
  `cadastre/pl_egib/bbox/<coords>.gpkg`, `cadastre/cz_cadastral-map_shp/ku/623164.zip`,
  `models3d/pl_buildings_lod1_2024/teryt/1261.zip`,
  `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip`,
  `names/pl_prng_shp/country/pl_miejscowosci.zip`,
  `maps/pl_bdot10k_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif`,
  `geodesy/pl_control_vertical/bbox/<coords>.gpkg`,
  `landcover/pl_bdot10k_shp_2024/teryt/1261.zip`; different content never
  shares a slot (full tree: ARCHITECTURE 3.3)
- Every successful download (CLI, DownloadManager, download_landcover,
  download_soil, calculate_hsg, download_pl_cutout, download_laz_area,
  download_collection) has a sidecar `<file>.meta.json` (schema
  `kartograf-meta/1`, best-effort); the version
  sidecar is mandatory (write failure = no version)

### 2.12 GUGiK campaigns (ADR-030) - IN SCOPE

```text
# Strategies (PL only; CZ is always the current mosaic):
- Without `--all-campaigns` (default): the newest sheet index record (ADR-028)
  within the year range, checked on every run after the cache expires (7 days)
- `--all-campaigns`: every campaign of the sheet (within the year range) after the hard filter of ADR-028
- Data year (ADR-032; NMT/NMPT/orto: aktualnosc, LAZ: akt_rok):
  --year YYYY = --min-year YYYY --max-year YYYY; the year flags only determine
  the permitted years, --all-campaigns the number of flights (model A; every combination allowed)
- First the full campaign list of each sheet is checked, then the download:
  a sheet with data only from other years = Error: with the years and a hint, nothing
  downloaded; a sheet without data = Warning: (skipped); sheet index failure = Error:
  (exception: local version, point below)
- Several flights in the range (all): coverage measurement when the newest is incomplete;
  Info: + extra.better_coverage, link unchanged (newest)
- Second link full_sheet/ (ADR-033): the newest local flight with
  calyArkuszWypelnionyTrescia = TAK (full = within the borders of Poland), alongside the
  standard path; --full-sheet fetches at most one flight per sheet,
  when the newest in range is not full (no effect with --all-campaigns); Warning: E13
  points to full_sheet/ or hints at --full-sheet
- LAZ: --all-campaigns (tiles whose frame intersects the area, without ADR-029 deduplication);
  year range with a reference tile coverage check (ADR-032 P8); --year
  is mutually exclusive with --min-year/--max-year (Error:)
- WCS cutout `--cutout`: server composition without a choice of year
  or campaign (--all-campaigns/--year/--min-year/--max-year/--full-sheet =
  Error:); LAZ with --full-sheet = Error:
- CZ has no campaigns or year choice: a task without a PL part with --all-campaigns,
  a year flag or --full-sheet = Error: before the network; a PL+CZ area under auto
  requires --cutout (ADR-038), which rejects these flags - PL sheets: --country pl
- Verification of the campaign file content (AAIGrid header / TIFF signature;
  ADR-041 archives: complete ZIP, TTN signature, Intergraph header,
  DXF), format from the record's `format` field; campaign sidecar mandatory
- GUGiK sheet index unavailable (transport error) in default mode (without
  --upgrade/--force): sheet from the local version + Warning:, code unchanged —
  without year flags for every strategy (also --all-campaigns), when the standard
  path points to a local version (erratum 5 ADR-030); with year flags,
  when EVERY sheet of the task has a local version within the year range (ADR-036 D14).
  No local version, --upgrade or --force = error
- API: DownloadManager(year=, all_campaigns: bool = False, min_year=, max_year=,
  full_sheet=), .check_year_range(), YearRangeError, available_years
  (GUGiK providers), DownloadResult (.unverified, .reused_campaign_files,
  .better_coverage, .full_links, .without_full), FileStorage.get_full_sheet_path,
  CampaignRef; download_data(year=, min_year=, max_year=, all_campaigns=,
  full_sheet=) = CLI flags
```

### 2.13 Boundaries, cadastre, prices and 3D models (GUGiK, ADR-042, ADR-043) - IN SCOPE

```text
# CLI groups (ADR-039, ADR-042 D9): boundaries, cadastre, models3d — each
# with download and list-sources; library: download_collection/check_collection
# (= CLI, ADR-037), `collection` plan track. A new collection product = a descriptor
# entry with channel parameters, no provider (ARCHITECTURE 5).
# CZ products of these groups (RUIAN, geomorphology, cadastral map): section 2.14.

# PRG boundaries — `boundaries download --product admin` (pl.gugik.prg):
- --teryt <2 digits>: voivodeship package (GML of all levels), ZIP 1:1
  -> boundaries/pl_prg_gml/teryt/12.zip
- --whole-country --country pl: national SHP file (approx. 377 MB; size
  in Warning: before transfer) -> boundaries/pl_prg_shp/country/pl.zip
- area (--bbox/--sheet/--geometry, --country pl) with required --level
  wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb: one GeoPackage
  from WFS, full geometries of units intersecting the area (no clipping),
  EPSG:2180 -> boundaries/pl_prg_gmina/bbox/<coords>.gpkg

# PRG address points and streets — `boundaries download --product addresses`
# (pl.gugik.prg_addresses, 0.8.0):
- area (--country pl) -> one GPKG EPSG:2180 with layers of address
  points and streets (WFS KIN GUGiK) -> boundaries/pl_prg_addresses/bbox/<coords>.gpkg
- --teryt <4 digits>: county SHP package 1:1 -> boundaries/pl_prg_addresses_shp/teryt/1261.zip
  (there are no voivodeship packages: --teryt <2 digits> = error with a list of choices)
- --whole-country --format SHP|GML: national file (approx. 564 / 804 MB)

# PRG special boundaries — `boundaries download --product special` (pl.gugik.prg_special, 0.8.0):
- area (--country pl) -> one GPKG OGC:CRS84 with 44 kinds of boundaries (courts,
  police, tax administration, forests, waters, maritime areas, ...), one layer
  per kind, from OGC API PRG (minutes: each collection separately)
  -> boundaries/pl_prg_special/bbox/<coords>.gpkg; census districts are excluded from
  the area result (the service responds in minutes) — Info (area_omitted)
  points to the national file
- --whole-country --format SHP|GML: national file (approx. 734 MB for SHP);
  --teryt = error

# EGiB (cadastral map) — `cadastre download --product map` (pl.gugik.egib):
- --teryt <4 digits>: county export (layers parcels, buildings, transactions;
  refreshed daily), GPKG extracted from ZIP
  -> cadastre/pl_egib_gpkg/teryt/1261.gpkg
- area (--country pl): parcels and buildings from the WFS aggregate service in one
  GPKG EPSG:2180 -> cadastre/pl_egib/bbox/<coords>.gpkg; counties without
  integration with the service = gaps, restricted attributes = `brak_uprawnien`;
  the DATA field is left out of the file, its values are in the sidecar
  (extra.source.dropped_fields)

# RCN (real estate price register) — `cadastre download --product prices`
# (pl.gugik.rcn, 0.8.0):
- --teryt <4 digits> (county) or <2 digits> (voivodeship), area = export of
  each county -> GPKG EPSG:2180 with layers transakcje_dzialki,
  transakcje_budynki, transakcje_lokale, extracted from ZIP locally
  with layer checks -> cadastre/pl_rcn/teryt/1261.gpkg; refreshed daily

# 3D building models (CityGML) — `models3d download --product buildings`
# (pl.gugik.buildings):
- --teryt <4 digits> or area (--country pl): packages of each county
  of the area according to PRG; county package ZIP 1:1
- release: --lod 1 --year 2019|2021|2022|2024 or --lod 2 (the only release
  2017, --year may be omitted) -> models3d/pl_buildings_lod1_2024/teryt/1261.zip
- vertical CRS from the data in the sidecar: LoD1 2019 and LoD2 2017 = EPSG:9650
  (PL-KRON86-NH), LoD1 2021/2022/2024 = EPSG:9651 (PL-EVRF2007-NH)
- LoD2 does not cover the country: missing county package = error for that county

# City 3D mesh — `models3d download --product mesh` (pl.gugik.mesh, 0.8.0):
- tiles of the GUGiK WFS index intersecting the area (--bbox/--sheet/--geometry),
  each as the original ZIP (OBJ, MTL, JPG textures, approx. 40-60 MB)
  -> models3d/pl_mesh/<crs>[/<zone>]/<record_file>.zip (directory = record
  CRS 1992 or 2000/<zone>; heights EPSG:9651); tile = file of one record
  (a module from several works = several files), --year filters records
- version label = date and work report number from the record, freshness signal index
  (--check-updates without download)

# 3D tree models — `models3d download --product trees` (pl.gugik.trees, 0.8.0):
- CityGML LoD1 2023 (EPSG:2180, no vertical CRS): county package
  (--teryt) or county packages of the area, 0.3-25 GB each (Warning
  with size) -> models3d/pl_trees_lod1_2023/teryt/3063.zip; --lod 1
  and --year 2023 may be omitted

# Common:
- exactly one selection (--teryt / area / --whole-country); variant
  (level, LoD, year, format) required when the source publishes more than
  one — no defaults affecting the data
- --country pl|cz|auto required with --bbox/--geometry, with --teryt only pl;
  models3d PL only
- --check-updates | --upgrade | --force, --plan, --workers (default 1), -q;
  project task entries (`kartograf project add <name> boundaries download ...`)
- freshness signal none (GUGiK provides no ETag/Last-Modified, the WFS result
  is a snapshot; exception: mesh — index): --check-updates reports „nie da się
  sprawdzić bez pobrania”, new content is obtained with --force (same content = no
  change, different = new version)
- version label: year of 3D models (e.g. 2024), mesh — date and work
  report; PRG, addresses, special boundaries, EGiB and RCN — download date
- area limit (ADR-043 erratum 3): an area that would download more than 100
  files or more than 10 GB (sum of HEAD or lengths from the ATOM feed;
  over 100 files — estimate from 5), ends with an error before download
  with the file count, size and a hint (narrow the area, choose a
  unit --teryt/--ku, run the plan with some of the entries); files
  without a local version are counted; a unit and --whole-country have no limit; applies to
  all collections (sections 2.13-2.16, BDOO, ZABAGED, Data50, Data250,
  NMT 100 m)
- Notice: messages unit_list (area units according to PRG/RUIAN),
  whole_country_size (national file size before transfer),
  download_size (unit file over 100 MiB), area_omitted

# Source: GUGiK (PRG, EGiB, RCN, 3D building and tree models, mesh)
# API: WFS 2.0 (area objects, mesh index), OGC API Features (special
# boundaries), OpenData (unit ZIP packages, national files)
```

### 2.14 CZ data: ZABAGED, Data50, Data250, RUIAN, geomorphology, cadastral map, HY-NET (CUZK, ADR-042 D15-D17, ADR-043) - IN SCOPE

```text
# Common: area (--bbox/--geometry, --country cz or auto) = one GPKG
# of features intersecting the area in EPSG:5514 (full geometries); country file
# only with --whole-country, CUZK ZIP 1:1, size in Warning before transfer;
# sheet code as area and --teryt PL only. File engine from the ATOM feed:
# transport/atom.py (atom_files, feed index in cache with ETag).

# ZABAGED — `landcover download --product zabaged` (cz.cuzk.zabaged):
- area -> landcover/cz_zabaged/bbox/<coords>.gpkg: 22 land cover
  and water layers (REST ZABAGED_POLOHOPIS; codes = ASCII names of service layers),
  without converting classes to BDOT10k codes; list: landcover list-layers --product zabaged
- --whole-country --horizontal-crs EPSG:5514|EPSG:3045 -> country GPKG file
  from the ATOM feed (5.8/6.7 GB) in landcover/cz_zabaged_gpkg_<epsg>/country/cz.zip;
  full database layers under CUZK names (different from the area result); metadata signal

# Data50 and Data250 — `landcover download --product data50|data250` (cz.cuzk.data50/data250, 0.8.0):
- area -> landcover/cz_data50/bbox/<coords>.gpkg: all feature
  layers of the REST service (Data50: 69, Data250: 116) in EPSG:5514
- --whole-country --horizontal-crs EPSG:5514|EPSG:3045 -> country SHP ZIP
  from the ATOM feed 1:1 -> landcover/cz_data50_shp_<epsg>/country/cz.zip; metadata signal

# RUIAN — `boundaries download --product admin --country cz|auto` (cz.cuzk.ruian):
- --level kraj|okres|obec|katastralni-uzemi -> boundaries/cz_ruian_<level>/bbox/;
  under auto the level per country (--level pl=gmina,cz=obec) -> PRG and RUIAN files
- --whole-country --country cz -> boundaries/cz_ruian_shp/country/cz.zip (SHP, http)

# Geomorphological units — `boundaries download --product geomorphology
# --country cz` (cz.cuzk.geomorphology, 0.8.0):
- area with required --level subprovincie|oblast|celek|podcelek|okrsek|podokrsek|cast
  -> boundaries/cz_geomorphology_<level>/bbox/<coords>.gpkg (REST, EPSG:5514);
  no country file

# Cadastral map — `cadastre download --product map --country cz`
# (cz.cuzk.cadastral_map, 0.8.0):
- --ku <6 digits> (katastralni uzemi) or area = KU of the area according to RUIAN (Info
  with the KU list); --format SHP|DXF|DGN|VFK required -> KU ZIP package 1:1
  -> cadastre/cz_cadastral-map_<format>/ku/623164.zip; http signal (ETag/Last-Modified)
- VKM format outside 0.8.0 (section 3.1)

# HY-NET — `hydro` group, `download --product network --country cz` (cz.cuzk.hynet):
- area -> hydro/cz_hynet/bbox/<coords>.gpkg: WatercourseLink and HydroNode
  (WatercourseSeparatedCrossing without geometry and with hits 0 - country file only)
- --whole-country -> hydro/cz_hynet_gpkg/country/cz.zip (GPKG in EPSG:3045, http)

# Source: CUZK (CC BY 4.0)
# API: ArcGIS REST (ZABAGED, Data50, Data250, RUIAN, geomorphology), WFS 2.0
# GeoServer (HY-NET), ATOM, openzu, services.cuzk.gov.cz (cadastral map)
```

### 2.15 Geographic names and topographic maps (GUGiK, CUZK, ADR-043) - IN SCOPE

```text
# `names` and `maps` CLI groups (download, list-sources; download_collection,
# project tasks); segments data/names/ and data/maps/.

# Names — `names download --product geographic|world`:
- geographic --country pl (pl.gugik.prng, PRNG RP): area -> GPKG OGC:CRS84
  (OGC API Features; page up to 180 s) -> names/pl_prng/bbox/<coords>.gpkg;
  --whole-country --format GML|SHP|XLSX -> two national ZIP files 1:1
  (names/pl_prng_<format>/country/pl_miejscowosci.zip, pl_obiekty-fizjograficzne.zip)
- world --country pl (pl.gugik.prng_world): Polish geographic names
  of the world — area also outside Poland, a single national file (pl_swiat.zip)
- geographic --country cz (cz.cuzk.geonames, Geonames): area -> GPKG
  EPSG:5514 (25 layers, REST) -> names/cz_geonames/bbox/<coords>.gpkg;
  --whole-country --format GPKG|FGDB --horizontal-crs EPSG:5514|EPSG:3045
  -> ZIP from the ATOM feed 1:1 (names/cz_geonames_<format>_<epsg>/country/cz.zip;
  release = label, metadata signal)
- area results without a cheap signal (none; new content: --force)

# Maps — `maps download --product topographic` (ready-made sheets, not a vector database):
- --country pl (pl.gugik.bdot10k_maps): BDOT10k visualisations, --scale
  1:10000|1:25000|1:50000|1:100000 and --format TIFF|PDF required, a sheet
  (--sheet) or the area's sheets -> maps/pl_bdot10k_<scale>_<format>/<hierarchy>/<sheet_code>.<ext>;
  the "Stan bazy" date from the index (WMS GetFeatureInfo) = label and index signal
- --country cz (cz.cuzk.ztm): ZTM at scales 1:5000-1:250000, sheet system
  S-JTSK or ETRS89 from the sheet code (area: --sheet-system sjtsk|etrs89), formats
  S-JTSK: TIFF, PDF, DGN, SHP, ETRS89: TIFF, PDF; ZIP 1:1 (PDF as .pdf)
  -> maps/cz_ztm_<scale>_<system>_<format>/<sheet code hierarchy>/<sheet_code>.zip; http signal

# Source: GUGiK (PRNG, BDOT10k visualisations), CUZK (Geonames, ZTM)
# API: OGC API Features, WMS GetFeatureInfo (map index), ArcGIS REST, ATOM, OpenData, openzu
```

### 2.16 Geodetic control networks and quasi-geoids (GUGiK, CUZK, ADR-043) - IN SCOPE

```text
# `geodesy` CLI group (download, list-sources; download_collection, project
# tasks with the network option).

# Control networks — `geodesy download --product control --network <network>` (--network required):
- PL (pl.gugik.control): horizontal|vertical|gravity|magnetic — area
  (--bbox/--sheet/--geometry) -> GPKG of network points from WFS (layers
  fundamentalna_* and bazowa_*, EPSG:2180) -> geodesy/pl_control_<network>/bbox/<coords>.gpkg;
  --teryt <4 digits> with horizontal|vertical -> county package (XLS listings,
  JPG descriptions) 1:1 -> geodesy/pl_control_<network>_xls/teryt/<T>.zip;
  archive-1942|archive-kronsztadt60 -> scans of 1:100 000 sheets (PDF, TIFF;
  --sheet of any scale or the sheets of the area)
  -> geodesy/pl_control_archive-1942/N-33/58/N-33-58.zip
- CZ (cz.cuzk.control, Bodove pole): gnss|horizontal|densification|
  horizontal-detailed|vertical|vertical-detailed|gravity, area only
  -> GPKG of network layers in EPSG:5514 (network = sum of its layers)
  -> geodesy/cz_control_<network>/bbox/<coords>.gpkg
- --country auto: one --network value for both countries (common:
  horizontal, vertical, gravity); signal none (new content: --force)

# Quasi-geoids — `geodesy download --product geoid --whole-country` (area = error):
- PL (pl.gugik.geoid2021): PL-geoid2021 for PL-EVRF2007-NH (TXT 1:1, 42 MB)
  -> geodesy/pl_geoid2021_evrf2007/country/pl.txt; signal none
- CZ (cz.cuzk.qgzu2013): QGZU-2013 (ZIP of 17 TXT grids for Bpv, 58 MB) from the
  ATOM feed -> geodesy/cz_qgzu2013_bpv/country/cz.zip; release = label, signal metadata
- models are data: Kartograf does not apply them to other data

# Source: GUGiK (primary control networks, PL-geoid2021), CUZK (Bodove pole, QGZU-2013)
# API: WFS (PL networks), ArcGIS REST (Bodove pole), ATOM, OpenData
```

### 2.17 Interface for AI agents - IN SCOPE

```text
# The same result in three ways (ADR-046; guide: USAGE 9):
# - CLI: `--json` in every command (44 leaf commands) — stdout is a single `kartograf-result/1`
#   envelope around a `kartograf-<kind>/1` document (20 documents), an error is `kartograf-error/1`
#   on the last line of stderr with a stable `code`, `hint` and the exit code of the Nogat
#   registry (0; 10 and 11 for a partial or failed batch; input error = 2);
# - library: `to_dict()`/`to_json()` of every report, exceptions with a stable `code`,
#   `exit_code` and `hint` (`ValidationError.option`/`allowed`), `error_report`;
# - MCP server `kartograf-mcp` (stdio; optional extra `kartograf[mcp]`, `mcp>=2.3.0,<3`):
#   39 tools 1:1 with the commands (`kartograf_<group>_<command>`), result = the `kartograf-result/1` envelope
#   with `outputSchema`, `is_error` only for an error, progress via MCP notifications, absolute paths,
#   `--tools`, `--allow-dir`, `--allow-writes` (without it only plans), no default values
#   affecting the data.
# Command catalog: `kartograf commands list|schema [--json]` (`list_commands()`, `command_schema()`) —
# the single source of truth
# about commands (CLI parser, project options, MCP tool schemas); command layer
# `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command`
# (KB-1..KB-5 of Archiwista). Files for agents: the generated `AGENTS.md` and `llms.txt`, `kartograf/py.typed`,
# `scripts/gate.sh`, `python -m kartograf`; rules for agents from other repositories:
# CLAUDE.md. New command = a declaration in `src/kartograf/catalog/commands/` (ARCHITECTURE 4.11).
```

---

## 3. Out of scope - Version 0.8.0

### 3.1 Planned functionality - FUTURE

```text
# Catalogue plans A-E (GUGiK and ČÚZK products) are in scope for 0.8.0 (section 2).
# Further CZ tasks (no assigned release):
- CZ administrative boundary polygon instead of a rectangular envelope
  (CountryProfile.extent_wgs84) — removes false queries to CUZK for
  bboxes lying entirely within Poland (see 3.2)
- Unification of extra.parent_request.bbox_crs between explicit/auto modes
- Merging PL+CZ cutouts into one continuous border surface
  (common grid, EVRF2007 on both sides, overlap rule) — R6; input
  data measured live on 2026-09-29: GUGiK provides data ~200 m into CZ,
  CUZK ~118 m into PL, shared strip ~310-350 m without a gap (apart from GUGiK
  coverage holes), PL−CZ height differences in the strip −0.19..+0.14 m (medians
  dependent on the dataset), PL and CZ grids not shared

# Campaigns — out of scope (ADR-030):
- --campaign <id> (selecting a single campaign), coverage and mosaic strategies
- Tool for assembling campaigns into one surface — no assigned
  release (did not make it into 0.7.1; ADR-030 erratum 6)
- Campaigns for CZ (CUZK does not publish history) — no assigned release

# CZ data out of scope for 0.8.0:
- Archive CUZK orthophoto (paid) — only the current vintage of the sheet
- Orthophoto cutout in a CRS other than EPSG:2180 (without resampling)
- CZ cadastral map in VKM format: CUZK pilot (10 KU), KU outside the pilot
  (e.g. 623164) returns 404 — fifth format `cadastre download --product map
  --country cz --format VKM`, once CUZK extends publication (PROGRESS backlog)

# GUGiK collections (ADR-042) — out of scope:
- EGiB voivodeship package (approx. 1.4 GB): `cadastre --teryt <2 digits>` = error
  with hint `--teryt <4 digits>`
- National 3D building model files (3.5-4.1 GB): `models3d --whole-country` = error
- Mapping ZABAGED classes to BDOT10k codes

# Interface for AI agents (ADR-046) — out of scope for 0.8.0:
- HTTP transport of the MCP server (stdio only)
- Cancelling downloads (KC) and a uniform `on_progress` for all functions (KC-2); MCP
  tools without progress: `kartograf_soil_download`, `kartograf_soil_hsg` and plans (`check_updates`)
- Download size estimate (KH), `command_for_file` (KB-6), `find_admin_units` (KB-7)

# Later — other countries:
- Germany (DE) — federation of 17 federal state models (BKG/basemap.de)
- Slovakia (SK) — DMR 5.0, ZBGIS (note: WCS returns ellipsoidal heights)

# Version 1.0+:
- GUI: QGIS plugin and web GUI — roadmap in section 3.3
- PostGIS integration
- REST API server
```

### 3.2 Technical limitations

```
- Sources do not publish checksums: Kartograf computes SHA-256 when writing
  a version (sidecar, ADR-036), and `kartograf project verify` checks them; the content
  of a download is checked only for format (verify_file_format: AAIGrid
  header / TIFF signature, ADR-030; GUGiK archives: ZIP/TTN/Intergraph/DXF,
  ADR-041; collection packages: ZIP directory and required members, ADR-042)
- Default timeouts: 30 s for NMT/NMPT (GUGiK) and for WFS discovery in LAZ,
  60 s for Orthophoto, LAZ tile downloads, CORINE (bbox/sheet code), CUZK and
  SoilGrids by sheet code, 120 s for BDOT10k (all modes) and SoilGrids
  by bbox and HSG (CORINE/SoilGrids by TERYT: NotImplementedError);
  the GUGiK sheet index GetCapabilities inherits the provider timeout (30 s
  NMT/NMPT, 60 s ortho); availability report: 30 s per sheet index query
  to WFS and PRG. Source of truth — constants in the code:
  GugikProvider.DEFAULT_TIMEOUT (NMT; NMPT inherits),
  GugikOrtoProvider.DEFAULT_TIMEOUT, GugikLazProvider.DEFAULT_TIMEOUT (tiles)
  and .WFS_TIMEOUT (discovery), CorineProvider.DEFAULT_TIMEOUT,
  SoilGridsProvider.DEFAULT_TIMEOUT (bbox; sheet code: default 60 s
  from LandCoverProvider.download_by_sheet), Bdot10kProvider.DEFAULT_TIMEOUT
  (TERYT query in PRG, teryts_for_area: 30 s), _DEFAULT_TIMEOUT
  in providers/cuzk/raster.py, the HSG limit follows from SoilGrids limits
  (no `timeout` parameter of the command function or `collections.run_request`;
  a collection channel may declare `FeatureBBoxParams.timeout`, ADR-044 D6).
- Max 3 retry attempts (not configurable); only network errors,
  HTTP 429 and 5xx are retried — other 4xx (e.g. 404) end immediately with DownloadError.status_code;
  pause 2 s, then 4 s, Retry-After extends it to a max of 60 s; a single
  place for all providers: transport/http.py (download_to,
  get_with_retry; constants and details: the module itself)
- Synchronous download within a single file (parallelism only
  between files, via ThreadPoolExecutor/--workers; default 4 workers
  in the CLI and download_data(workers=4), 1 in DownloadManager(workers=1))
- NMT/NMPT PL variants (resolution × vertical CRS × format) only
  from the variant registry (ADR-041), among others NMT 0.15m, 0.6m, 5m and 10m only
  EVRF2007; any other combination = Error: before the network with a list of available ones
- WCS (`provider.download_bbox`) NMT and NMPT gives 1 m float32 heights
  in both vertical CRSs; other resolutions and archives
  only from OpenData (sheets)
- PL WCS cutouts `--cutout` only 1 m (ASC grid; `--resolution` other
  than 1m or `--format` = Error:), without campaign/year selection;
  the server decides on the flight, which may differ from the sheet's flight
- Sheet index records that Kartograf does not download (sheet code outside the
  PL-1992/PL-2000 systems, format or variant outside the registry, missing https address
  or CRS), the availability report lists in a single Info: (index_unsupported);
  8-part PL-1992 sheet codes are downloaded since 0.8.0 (section 2.1)
- GUGiK archives (`--format`) are source files without conversion, cutout,
  mosaic and coverage measurement; `--scale` and `--cutout` with an archive = Error:
- PL availability report (`elevation availability`) trusts the declaration
  `calyArkuszWypelnionyTrescia` (it does not measure sheet content NOT);
  land mask rasterised on a 1 m grid in 4 Mpx strips — slow for
  large areas (16 km2: 5–7 s with network, 0.6–1.5 s
  with metadata cache, measured 2026-10-15). The CZ report checks
  only the HTTP headers of files, not their content or the flight year.
- SoilGrids: WGS84 bbox only (automatic transformation)
- SoilGrids: no selection by TERYT — `--teryt` applies to BDOT10k, BDOO and collections,
  and `SoilGridsProvider.download_by_teryt` raises NotImplementedError (previously
  it silently returned a 60x60 km square around the voivodeship centre); use --bbox/--sheet
- find_sheets_for_bbox/find_sheets_for_geometry: touching edges are NOT
  an intersection (positive area required) — a bbox equal to a sheet in EPSG:4326
  returns only its sheets (in EPSG:2180 also fragments of neighbours), and a bbox
  degenerate to a point → exactly one sheet
- GUGiK sheet index: retry (up to 3 attempts: network, 429, 5xx), session per thread; a layer /
  template failure aborts with DownloadError, without campaign degradation. NMT/NMPT:
  WFS sheet index (since 0.8.0); the server ignores FILTER, paging only by
  `next`, a multi-type response with `next` is rejected and queried per type
  (the server pages several types inconsistently); an inconsistent page = DownloadError
  („wynik bylby niepelny”), never an empty result. Ortho: WMS GetFeatureInfo.
  A record must have the whole sheet code, a matching CRS, resolution and (NMT/NMPT)
  format matching the URL; the newest date wins. No record gives
  NoCoverageError; extra.source preserves provenance.
  The PL cache stores a full record or no coverage (TTL 7 days); --force skips
  the read and writes a fresh entry (in CZ the same for the SM5 sheet index)

# CZ (CUZK; NMT since v0.7.0, other products since 0.8.0) — additional limitations:
- CZ products: nmt (DMR 5G/4G), nmpt (DMP OK/1G), laz (four models,
  --model), contours (ZABAGED contours), orto (SM5 sheets, current
  vintage only), ZABAGED, Data50, Data250, RUIAN, geomorphology, cadastral
  map (SHP/DXF/DGN/VFK), HY-NET, Geonames, ZTM, Bodove pole, QGZU-2013
- exportImage: service ceilings 15000x4100 px, practical limit ~8 Mpx;
  the client tiles according to a 4 Mpx budget per request, NW snap gives a pixel
  of exactly 0.5 m/2 m/5 m (model step), and the E/S edge may differ by <= 1/2 px
- KRON86 unreachable for CZ (no public Bpv→KRON86 grids) — the only
  vertical transformation is Bpv→EVRF2007 (EPSG:5621)
- --cutout works only with --bbox/--geometry; with a CZ sheet code = ValidationError;
  CZ raster area without --cutout = ValidationError (ADR-038); LAZ with --cutout = error
- `--cutout` for PL: NMT/NMPT 1 m from WCS, PL-1992 segment
  (`--sheet-system 2000` = error); ortho/LAZ, NMT/NMPT other than 1 m and archives with `--cutout`
  = error. Area outside the PRG land mask `A00 - W02 - W03` = nodata
  -9999; height 0.0 on land remains. Entire cutout nodata =
  Warning: and code 0. WCS chooses the flight on the server, different from the
  newest sheet of exactly 1 m according to ADR-028 (section 2.1)
- WCS cutout (since 0.8.0): by default the local version without PRG queries
  and WCS (no cheap freshness signal), `--force` downloads again;
  the new version is created next to the old one, the previous version and hard link
  remain on failure; `--workers`, `--scale` have no effect.
  `Info:` gives the number of WCS tasks for many pieces or a result
  >= 1 GiB (when the cutout is downloaded), without a hard size limit
- PL sheet list (--bbox/--geometry without --cutout and sheet code
  hierarchy) tries all sheets regardless of --workers. R5:
  NoCoverageError -> skip, Warning: and status no_coverage;
  >= 1 file, no hard failure = code 0; all sheets without data
  or any failure other than no coverage = code 1 (list of all
  failures). A single sheet without data = code 1
- Raster --bbox mode is explicit (ADR-038): PL without --cutout returns a list of sheets
  (many files), with --cutout one file; the CZ raster has only a cutout (exportImage,
  downloaded natively in 5514 and reprojected locally when another
  CRS is requested), so a CZ raster area requires --cutout. Under auto a PL+CZ area does not give
  PL sheets next to the CZ cutout (PL sheets: --country pl). CZ LAZ (since 0.8.0)
  has no cutout: the area is sheets from the CUZK index, without --cutout
- CountryProfile.extent_wgs84 for CZ is a RECTANGLE (envelope), not a polygon
  of the border — --country auto in the strip west of 18.86°E and south of
  51.06°N (among others Opole, Wałbrzych, Rybnik, southern outskirts of Wrocław;
  Kraków, Rzeszów and central Wrocław are already outside the rectangle) sends
  a query to CUZK also for bboxes lying entirely in Poland, and also
  in Saxony below 51.06°N and in the Bogatynia strip (an additional raster
  entirely nodata = Warning: on stderr and code 0). Symmetrically the PL rectangle
  (14.07..24.20°E, 49.00..54.90°N) covers
  most of Czechia, so auto in Prague, Brno or Ostrava also queries
  GUGiK — the fix (border polygon) has no assigned release (section 3.1, ADR-023)
- --country (required with --bbox/--geometry since 0.8.0; previously default
  auto): under auto on a disputed area, values with no Czech equivalent
  (--vertical-crs KRON86, a resolution with no CZ equivalent, e.g.
  --resolution 1m or 0.5m for NMT — NMPT 0.5m is DMP OK, --format
  in its plain form, --coverage and --resolution of an orthophoto cutout)
  DECIDE the country as pl with an Info: message on
  stderr, instead of failing the task; for --product laz also --year,
  --min-year, --max-year, --all-campaigns and --min-density. Without them LAZ
  on an area reaching CZ downloads PL tiles and CZ sheets (requires --model;
  without it an error with the hint --country pl)
- --country auto clips each country's part of the task to the rectangle,
  prints `Info:` about the clipping and about the area omitted outside both
  envelopes. The file name and request.bbox carry the clipped part,
  extra.parent_request the original task; untouched PL edges keep
  the original coordinates (no widening on those edges).
  Explicit --country pl does not clip, --geometry without --cutout determines
  PL sheets from the geometry; a bbox entirely outside the countries = error before the network.
  On the DE/SK/UA/BY/LT/RU borders auto queries PL with clipping;
  inside the CZ rectangle CUZK is added (no border polygon required)
- Partial success in auto mode (one country downloaded, the other failed — no
  data or source failure) is exit code 0 + Warning: on stderr; a failure for
  explicit --country and for failure of all countries stays a failure (the outcome
  `failed` or an error, with its registry exit code; ADR-023 points
  4-5). Code 0 therefore does not guarantee a file from each country. Info:/Warning: go
  to stderr, so -q does NOT suppress them
- extra.parent_request.bbox_crs depends on the mode when the geometry file is not
  in the CZ request CRS: explicit --country cz carries the CZ request CRS
  (--horizontal-crs), auto/pl — EPSG:2180, and for a file in EPSG:5514/3045
  — the file's CRS (since 2026-09-28: the envelope leaves Krovak via the pinned
  operation); a file in EPSG:5514 with --horizontal-crs EPSG:5514 thus gives the same bbox_crs in
  all modes — a known limitation of the grouping key, to be unified
  (section 3.1, no assigned release)
- extra.parent_request.countries = countries ATTEMPTED, not downloaded (when
  one country fails in auto mode the other's sidecars still carry both codes)

# Collections (boundaries, cadastre, models3d, hydro, names, maps, geodesy,
# BDOT10k archive, BDOO, ZABAGED, Data50, Data250; ADR-042, ADR-043):
- PRG `--teryt <4 digits>` = error (PRG publishes voivodeship packages; county
  area via --bbox/--geometry); EGiB and PRG addresses `--teryt <2 digits>`
  = error with the hint `--teryt <4 digits>`; special boundaries without
  `--teryt`; `models3d --whole-country` = error
- `models3d` PL only (`--country cz` = error); CZ: RUIAN and geomorphology
  (`boundaries`), cadastral map (`cadastre`), HY-NET (`hydro`) — section 2.14
- LoD2 (the only release, 2017) does not cover the country, 3D trees not every
  county: missing county package = error for that county
- Area limit: over 100 files or 10 GB = error before download (section
  2.13); no override flag — narrow the area, unit or plan
- PRG special boundaries of an area: minutes (OGC API queried per collection,
  120 s limit with retry); census districts only in the national file
- RCN: unpacking and layer checks in a local temporary directory
  (`TMPDIR`; voivodeship export of the order of 1.8 GB)
- GUGiK WFS pages: a few seconds per page of 1000 features (live
  2026-10-15: 2–4 s); completeness from the feature count (`RESULTTYPE=hits`),
  an incomplete series of pages = DownloadError; area result assembled in memory
  (whole layer at once)
- GPKG bytes of an area result are reproducible within one GDAL version
  (pyogrio); another GDAL version may give different bytes for the same content
- EGiB of an area: gaps in counties without integration with the aggregate service,
  restricted attributes = `brak_uprawnien`
- Freshness signal none (outside channels with an index, CUZK `ETag` and the ATOM
  feed): --check-updates does not detect newer data, only --force gives new content
- Timeouts: 60 s per WFS query, 120 s per package, 30 s for HEAD
  and PRG query (SERVICE_TIMEOUT, PACKAGE_TIMEOUT, PROBE_TIMEOUT
  in download/collections.py)
```

---

### 3.3 Roadmap to v1.0.0

Direction approved 2026-10-08. Each subproject has its own spec and plan;
subprojects 2 and 3 enter 0.8.0 together (user decision 2026-10-15);
the details are settled by their ADRs, not by this section.

**v1.0.0 goal:**

1. **A complete set of public GUGiK data** — all products that GUGiK
   makes available publicly and without login, as far as the services allow.
   The full catalogue is an entry condition, not a differentiator.
2. **Ready-to-use data as the differentiator** — for each product, a result fitted to
   the task area (cutout, merging, reprojection where they make sense)
   with a provenance sidecar, not just raw sheets and packages.
3. **Data manager** — a shared team store from which subsequent projects
   take data instead of downloading it again, with a record of which data versions
   each project used.
4. **QGIS plugin** and **web GUI** as overlays on the library.
5. **English-only identifiers** in the API, CLI and sidecar (ADR-031).

**Audience of the overlays:** first the user and their team (local
installation, web GUI run on `localhost`), after testing —
publication (QGIS plugin repository, public instance of the web GUI).

**Principles:**

- The overlays (QGIS, web) call only the public API of the library
  (`src/kartograf/__init__.py`); they have no download or processing logic of their own.
- The store never overwrites data silently: each product has immutable
  versions (ADR-036, since 0.8.0); the standard path points to the newest
  local version.
- The sidecar remains an immutable description of a file's provenance. The link between a
  project and data is recorded by the project manifest (project → data: specific
  files, versions and checksums); the information "which projects use this
  file" is an index built from the manifests, not an entry in the sidecar.
- The store may sit on a network share without byte-range locks, so the
  shared directory cannot be a SQLite database on the share; the source of truth is the
  sidecars and manifests, the index and metadata cache are local.
- The project manifest is a new format, so it uses English
  keys from the start (no ADR-031 migration).

**Subprojects and order:**

| # | Subproject | Scope | Depends on |
|---|------------|--------|-----------|
| 1 | Versioned store | done (0.8.0, ADR-036): immutable versions for all products (previously only PL NMT/NMPT/orthophoto campaigns); plans 1/3 (PL sheets), 2/3 (LAZ, CZ, cutouts) and 3/3 (land cover, HSG), products of plans C-E in the store from the start (live E2E: `docs/research/2026-10-12-store-e2e/raport.md`); CLMS with credentials not verified live | — |
| 2 | Project manifest | done (0.8.0): file `kartograf-project.json` (`kartograf-project/1`) in the project directory — tasks (data commands of the ADR-039 groups with options) and pinned versions of files from the store with SHA-256 checksums; CLI group `project`: `init`, `add`, `remove`, `download` (also `--check-updates`, `--upgrade`, `--force`), `status`, `verify`; restoring data on a new store only with identical checksums. E2E: `docs/research/2026-10-15-project-e2e/raport.md`. Spec: `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`; plan: `docs/superpowers/plans/2026-10-15-manifest-projektu.md`; ADR-040 | 1; CLI command groups (ADR-039) |
| 3 | GUGiK catalogue and ready-to-use data | done (0.8.0, plans A-E, user decision 2026-10-15): GUGiK and ČÚZK products from the catalogue, each versioned and with a sidecar, with a cutout where the service provides one (sections 2.1-2.16). A: `elevation` PL — variant registry, NMT/NMPT grids in all GUGiK resolutions, GUGiK archives as source files, WFS sheet index, availability report (ADR-041); B: `elevation` CZ — DMP OK/1G, TM33 ETRS89 tiles, ČÚZK LAZ, CZ report; C: BDOT10k archive, PRG, EGiB, 3D building models (ADR-042); D: CZ orthophoto, PL orthophoto cutout, ZABAGED, RUIAN, HY-NET (ADR-042 D12-D17); E: GUGiK images, CZ contours, NMT 100 m, names, maps, addresses and special PRG boundaries, RCN, BDOO, Data50/250, geomorphology, CZ cadastral map, 3D mesh, trees, control networks, quasi-geoids (ADR-043). Outside 0.8.0: VKM, archival CUZK orthophoto (section 3.1). Inventory: `docs/research/2026-10-13-katalog-produktow/raport.md`; spec: `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`; plans: `docs/superpowers/plans/2026-10-15-plan-{a,b,c,d,e}-*.md` | 1; CLI command groups (0.8.0) |
| 4 | QGIS plugin | download from within QGIS for an area from the map or a layer; repository: this one or a separate one, to be decided in the spec | 2, partly 3 |
| 5 | Web GUI | local data manager: browser for the store and project manifests, information about newer data | 2 |
| — | ADR-031 (English identifiers) | API and CLI in English in 0.8.0 without aliases (erratum 1) | done (0.8.0) |
| — | Publishing the overlays | after testing 4 and 5 locally | 4, 5 |

Live verification of plans B-E: `docs/research/2026-10-16-plan-b-e2e/`,
`2026-10-15-plan-d-e2e/` and `2026-10-16-plan-e1-e2e/` to `2026-10-16-plan-e5-e2e/`
(reports `raport.md`). Products outside plans A-E will go into subsequent releases
and may proceed in parallel with 4 and 5.

---

## 4. Architecture

### 4.1 Modules

The tree corresponds to the `kartograf/` directory (source of truth: the directory itself); detailed
description — `docs/ARCHITECTURE.md`.

```
kartograf/
├── __init__.py           # Public API exports
├── _clock.py             # now() — single time source for results (frozen in conformance tests)
├── _version.py           # build_version() — version identifier
├── __main__.py           # `python -m kartograf` = `kartograf` script
├── py.typed              # PEP 561 marker (types for the consumer's mypy)
├── serialization.py      # Document (to_dict/to_json, schema as first key), encoder, SCHEMAS registry (ADR-046)
├── error_report.py       # ErrorReport, error_report, ERROR_CODES/EXIT_CODES (kartograf-error/1)
├── commands.py           # command layer: parse_command, validate_command, format_command, run_command, check_command
├── sheet_info.py         # describe_sheet, find_sheets (kartograf-sheet/1, kartograf-sheets/1)
├── source_info.py        # list_sources, list_layers (kartograf-sources/1, kartograf-layers/1)
├── cache_info.py         # get_cache_info, get_cache_path, clear_cache (kartograf-cache/1)
├── store_documents.py    # describe_store, list_store_entries, read_store_sidecar (store read documents)
├── mcp_server.py         # kartograf-mcp MCP server (stdio; optional `mcp` extra)
├── catalog/              # Command catalog: declarations (commands/), list_commands, command_schema, CLI parser, MCP tools (tools.py)
├── notices.py            # Notice, NoticeSink, data notice codes (ADR-037)
├── exceptions.py         # KartografError (code, exit_code, hint), ValidationError (option, allowed) -> UsageError/ParseError, DownloadError -> NoCoverageError/YearRangeError, CacheError, InvalidSidecarError, ForbiddenError, MissingDependencyError (MCP server)
├── store.py              # Store read without writing (ADR-045): list_segments, list_partitions, iter_store, read_sidecar, describe_segment, link_target
├── store_geometry.py     # file_footprint (native and WGS84 outline), pinned_transform (pinned operation, per thread)
├── core/                 # Core logic
│   ├── bbox.py              # BBox, validate_bbox, transform_bbox, is_czech_crs
│   ├── sheet_parser.py      # SheetParser — topographic map sheet code parser
│   ├── parser_2000.py       # Parser2000 — PL-2000 sheet code parser
│   ├── parser_tm33.py       # ParserTM33 — computable CZ 2x2 km tile grid (EPSG:3045)
│   ├── parser_registry.py   # Sheet system registry (pl1992, pl2000, cz_tm33, cz_sm5)
│   ├── geometry.py          # SHP/GPKG reading, find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py          # Convex polygons (intersection/difference/buffer) — LAZ tile selection (ADR-029)
├── sources/               # Source descriptors as data (zero IO on import)
│   ├── descriptor.py        # SourceDescriptor (+variants), AccessChannel (+endpoint, +params: UnitPackageParams/FeatureBBoxParams, ADR-042), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py          # PL/CZ/EU/GLOBAL registry — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs; NMT/NMPT descriptors per (product, format, resolution)
│   ├── variants.py          # Variant registry (ADR-041): ProductVariant, IndexRef, FORMATS, variants(), K2 labels, source_format
│   ├── edition.py           # Edition — source release (metadata signal: SoilGrids, CORINE CLMS)
│   └── sidecar.py           # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<file>.meta.json)
├── transform/             # CRS and raster transformations, collection GPKG writing
│   ├── bbox.py               # envelope_from_2180 — envelope of an EPSG:2180 bbox in another CRS (CORINE, SoilGrids)
│   ├── gpkg.py               # write_gpkg — deterministic GPKG of a feature_bbox result (pyogrio, ADR-042 D5)
│   ├── crs.py                # TransformerGroup (allow_ballpark=False, probe under network policy); PinnedTransform.transform polymorphic
│   └── raster.py             # warp_to_grid — local warp to grid, FORCED operation (ADR-027)
├── transport/             # Shared download transport
│   ├── http.py               # download_to (atomic write + retry), get_with_retry, sessions, HTTP signals
│   ├── aaigrid.py            # reading WCS ASC (AAIGrid) responses
│   ├── chunks.py             # area query chunks on the source grid (ADR-034)
│   ├── feature_bbox.py       # feature_bbox engine: area features from WFS 2.0 / ArcGIS REST (feature count, pages, completeness; ADR-042 D3/D4)
│   ├── mosaic.py             # mosaic_and_crop — tile merge (rasterio) + clipping (optionally on the source grid, sources in VRT)
│   ├── unit_package.py       # unit_package engine: unit file from a URL template ({teryt}, {woj}, {sheet}, {ku}, {theme}) or from an index record (variants, required parts, unpack; ADR-042 D1, ADR-043)
│   ├── atom.py               # atom_files engine: files from an ATOM feed (CUZK, GUGiK), release from updated, feed index in cache with ETag (ADR-042 D12)
│   └── index_records.py      # file index records: WMS GetFeatureInfo link table, WFS records (ADR-043)
├── providers/             # Data providers
│   ├── base.py               # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider
│   ├── pl/                   # Polish providers
│   │   ├── gugik.py             # GugikProvider (NMT)
│   │   ├── gugik_nmpt.py        # GugikNmptProvider (NMPT/DSM)
│   │   ├── gugik_orto.py        # GugikImageProvider — image sheets (orthophoto: GugikOrtoProvider, intensity, true ortho, oblique ortho); WCS cutout from registry channels
│   │   ├── gugik_laz.py         # GugikLazProvider (LAZ point clouds, WFS via WfsIndex; select_tiles)
│   │   ├── skorowidz.py         # GUGiK sheet index: records, hard filter, campaign selection (ADR-028/030); WMS GetFeatureInfo for ortho
│   │   ├── skorowidz_wfs.py     # WFS sheet index NMT/NMPT/LAZ (ADR-041): WfsIndex, parse_index_feature, sheet outlines
│   │   ├── wcs.py               # GugikWcsMixin — shared WCS GetCoverage URL (NMT/NMPT 1m, ortho)
│   │   ├── bdot10k.py           # Bdot10kProvider
│   │   ├── prg.py               # WFS PRG: land mask (PL cutout, availability report), TERYT for area/point
│   │   └── __init__.py          # create_nmt_provider() — NMT provider factory (vertical_crs, resolution required)
│   ├── cuzk/                  # Czech providers (CUZK, plan B)
│   │   ├── client.py            # CuzkClient — ArcGIS REST + ZIP openzu
│   │   ├── sheets.py            # SheetIndex/SheetInfo — SM5/TM33 index
│   │   ├── raster.py            # CuzkRasterProvider — NMT DMR and NMPT DMP
│   │   ├── laz.py               # CuzkLazProvider — four LAZ models
│   │   ├── ruian.py             # area KU from RUIAN (cadastral_areas_for_bbox) — CZ cadastral map
│   │   └── __init__.py          # create_cz_raster_provider(product, resolution, ...)
│   ├── corine.py             # CorineProvider
│   └── soilgrids.py          # SoilGridsProvider
├── cache/                 # Metadata cache
│   ├── defaults.py           # open_cache — cache shared by CLI and library (<cache_dir>/kartograf/metadata.db)
│   └── metadata.py           # MetadataCache — SQLite WAL: record_cache, campaigns_cache, teryt_cache, teryt_bbox_cache, index_area_cache, atom_cache (TTL 7d), sheet_cache (TTL 30d)
├── download/              # Download: library download command (data.py) and tracks
│   ├── data.py               # download_data/check_data = `kartograf elevation download` / `imagery download` (ADR-037)
│   ├── options.py            # Task choice validation (texts as in --help; variants from the registry)
│   ├── arguments.py          # Library argument type checks (require_int/str/bool/codes, timeout; CLAUDE.md)
│   ├── availability.py       # Availability report: check_availability, AvailabilityReport (ADR-041)
│   ├── collections.py        # download_collection/check_collection = `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download` (ADR-042); area limit; landcover collections
│   ├── cz_orto.py            # CZ orthophoto: download_cz_orto_sheet/check_cz_orto_sheet (ADR-042 D13)
│   ├── cz_contours.py        # ZABAGED CZ contours: SM5 sheet ZIP 1:1 (download_cz_contours_sheet, ADR-043)
│   ├── orto_cutout.py        # PL WCS image cutout (orthophoto, true ortho): download_image_cutout/check_image_cutout (ADR-042 D14, ADR-044)
│   ├── area.py               # Area: bbox_to_2180, geometry, parent_request, automatic clipping
│   ├── campaigns.py          # GUGiK campaigns (ADR-030): CampaignRef, format from record, verify_file_format
│   ├── countries.py          # Splitting an area by country (countries_for_bbox, split_bbox_by_country)
│   ├── fetch.py              # Policy for files without a campaign: fetch_version, VersionedFile
│   ├── plan.py               # kartograf-plan/1 update plan (PlanItem, UpdatePlan as Document)
│   ├── links.py              # Linking the standard path to a version (hard link only, never backwards)
│   ├── cutout.py             # PL cutout --cutout (download_pl_cutout/check_pl_cutout)
│   ├── cz_cutout.py          # CZ cutout (download_cz_cutout/check_cz_cutout)
│   ├── cz_sheets.py          # CZ sheet TM33/SM5 (download_cz_sheet/check_cz_sheet)
│   ├── cz_laz.py            # CZ LAZ: download_cz_laz/check_cz_laz
│   ├── laz.py                # LAZ tiles (download_laz_area/check_laz_area; ADR-029)
│   ├── manager.py            # DownloadManager (all_campaigns=, min_year=, sidecar_extra=; download_sheets/expand_sheets)
│   ├── storage.py            # FileStorage(vertical_crs=) — segments from descriptor templates (ADR-026); content_segment/unit_slot (land cover, collections; ADR-042 D8)
│   ├── updates.py            # PL sheet update plan items
│   └── versions.py           # Versioned store (ADR-036): exclusive write, labels, version list
├── landcover/             # Land Cover in the version store
│   ├── manager.py            # download_landcover/check_landcover, download_soil/check_soil; internal LandCoverManager
│   └── store.py              # HSG segment and land cover unit selection (spec 3.4)
├── hydrology/             # Hydrological calculations
│   └── hsg.py                # calculate_hsg/check_hsg, hsg_statistics; internal HSGCalculator (input versions, reused)
├── project/               # kartograf-project/1 project manifest (ADR-040)
│   ├── model.py              # Project, ProjectTask, PinnedFile, ProjectReport, TaskResult, ProjectCheck, FileCheck
│   ├── commands.py           # COMMANDS: data commands in tasks (options from the catalog, validation without network, download, pins)
│   ├── manifest.py           # manifest reading, validation and atomic writing
│   └── operations.py         # API: init_project, open_project, add/remove_project_task, download_project, check_project, get_project_status, verify_project
├── auth/                  # Authentication (CLMS)
│   ├── proxy.py               # Auth Proxy server
│   └── client.py               # Auth Proxy client
└── cli/                   # CLI: only flag translation and result output (ADR-037, ADR-046)
    ├── _parser.py             # create_parser() — facade over the parser built from the command catalog (ADR-039, ADR-046)
    ├── _handlers.py           # HANDLERS: command id -> handler
    ├── _args.py               # library_arguments: flags -> library function arguments (via the catalog)
    ├── _json.py               # --json mode: document on stdout, exit codes
    ├── parse_cmd.py           # `kartograf sheet parse` -> describe_sheet
    ├── download_cmd.py        # `elevation download` / `imagery download` -> download_data/check_data
    ├── availability_cmd.py    # `elevation availability` -> check_availability (table, --details, --json)
    ├── landcover_cmd.py       # `landcover download` -> download_landcover/check_landcover
    ├── layers_cmd.py          # `landcover list-layers` / `soil list-layers` -> list_layers
    ├── sources_cmd.py         # `<group> list-sources` -> list_sources
    ├── collection_cmd.py      # `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download` -> download_collection/check_collection
    ├── soil_cmd.py            # `soil download` -> download_soil/check_soil; `soil hsg` -> calculate_hsg/check_hsg
    ├── project_cmd.py         # `kartograf project` -> project API (ADR-040); `project add` via parse_command
    ├── cache_cmd.py           # `kartograf cache` -> get_cache_info/get_cache_path/clear_cache
    ├── catalog_cmd.py         # `kartograf commands list|schema` -> list_commands, command_schema
    └── commands.py            # Compatibility facade — `main` entry point (errors -> error_report, codes 0/1/2/130/143)
```

### 4.2 Dependencies

```
Python 3.12+
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing (HSG, CZ exportImage/openzu)
numpy >= 1.24.0        # Array operations (HSG, CZ per-pixel vertical transformation)
pyshp >= 2.3.0         # Shapefile reading
pyogrio >= 0.10        # Vector GDAL: writing GPKG of collection area results (ADR-042)
```

---

## 5. Data sources

| Source | Data type | API | Authentication |
|--------|-----------|-----|--------------|
| GUGiK | NMT, NMPT, orthophoto, images (intensity, true ortho, oblique ortho), LAZ, BDOT10k (from the yearly archive), BDOO | WCS, WMS, WFS, ATOM, OpenData | None |
| GUGiK PRG | Unit boundaries, address points and streets, special boundaries | WFS 2.0, OGC API Features, OpenData (ZIP packages, national files) | None |
| GUGiK EGiB and RCN | Cadastral map (parcels, buildings), real estate price register | WFS 2.0 (aggregate service), OpenData (county/voivodeship export) | None |
| GUGiK 3D models | CityGML LoD1/LoD2 buildings, CityGML LoD1 trees, city 3D meshes (OBJ) | WFS (mesh index), OpenData (ZIP packages) | None |
| GUGiK PRNG and maps | Geographic names of Poland and the world, BDOT10k map visualisations | OGC API Features, WMS GetFeatureInfo (index), OpenData | None |
| GUGiK control networks | Horizontal, vertical, gravimetric, magnetic control networks (with archives), PL-geoid2021 | WFS, OpenData | None |
| CUZK | NMT, NMPT, LAZ, orthophoto, contours, ZABAGED, Data50, Data250, RUIAN, HY-NET, geomorphology, cadastral map, Geonames, ZTM, Bodove pole, QGZU-2013, CZ availability report | ArcGIS REST (query, exportImage), WFS 2.0 (HY-NET), ATOM, sheet index + openzu files and services.cuzk.gov.cz | None |
| Copernicus CLMS | CORINE | REST API | OAuth2 RSA |
| EEA Discomap | CORINE (preview) | WMS | None |
| DLR | CORINE 1990 (preview, fallback) | WMS | None |
| ISRIC SoilGrids | Soil | WCS | None |

---

## 6. Success criteria

### 6.1 Functional

```
- The parser correctly parses sheet codes 1:1M - 1:5k (PL-1992, with 8-part sheet codes), PL-2000, TM33/SM5 (CZ)
- NMT is downloaded in all GUGiK grid resolutions from the variant
  registry (PL: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; NMPT 0.5m, 0.6m, 1m)
  and as GUGiK archives (source files), 2m and 5m (CZ)
- The availability report (elevation availability / check_availability) gives,
  for a PL area, the combinations with a full set of complete sheets, without downloading data
- BDOT10k is downloaded by TERYT, sheet code, bbox and geometry (every county of the area)
- CORINE is downloaded by sheet code (GeoTIFF or PNG fallback)
- SoilGrids downloads soil data
- HSG computes hydrological groups from SoilGrids data
- CZ DMR and DMP are downloaded by TM33/SM5 sheet code or cutout
  (`--cutout`), with native 5514/Bpv or 3045/EVRF2007 files
  and a local pinned transformation for the remaining pairs
- CZ LAZ downloads `.laz` 1:1 from the source by sheet code/area; `--model`
  selects the variant, `--country auto` downloads independent PL and CZ tiles
  with a shared `extra.parent_request`, without mosaicking
- The CZ and `auto` availability report checks variants and files (`HEAD`),
  without downloading data; a missing file does not pretend success
- PL 1 m NMT/NMPT cutout (--cutout / download_pl_cutout): one GeoTIFF
  from GUGiK WCS on the sheet grid (EPSG:2180) or in EPSG:5514/3045; outside
  PL land (PRG mask) nodata -9999
- GUGiK campaigns: --all-campaigns, --year/--min-year/--max-year; versions
  in versions/, standard path as a hard link to the latest;
  --check-updates/--upgrade/--force and the update plan (ADR-036)
- LAZ: tile selection by area coverage (ADR-029), API download_laz_area
- PRG boundaries, EGiB and 3D building models are downloaded by TERYT
  and area (download_collection), the BDOT10k archive by TERYT and area
  (`--year`, `download_landcover`); versions in versions/ and a sidecar for each file
- Products of plans D and E (CZ orthophoto, PL orthophoto cutout, GUGiK
  images, CZ contours, NMT 100 m, BDOO, ZABAGED, Data50, Data250, RUIAN,
  HY-NET, geomorphology, CZ cadastral map, PRG addresses and special
  boundaries, RCN, mesh, trees, names, maps, control networks, quasi-geoids) are downloaded
  from the CLI and library with versions and a sidecar; a collection area of more than 100
  files or 10 GB ends with an error before download
- Integration with Hydrograf/Hydrolog works
```

### 6.2 Qualitative

```
- All offline tests pass (`pytest -m "not live"`); tests
  with the `live` marker require a network and are not part of the offline gate
- Coverage not lower than the `fail_under` threshold in `pyproject.toml`
- Code compliant with ruff (`ruff check .` and `ruff format --check .` clean),
  `mypy kartograf/ tests/` without errors
- Documentation consistent with the code; behaviour changes towards GUGiK/CUZK services
  verified live before release (reports in `docs/research/`)
```

---

## 7. Change history

| Date | Version | Change |
|------|--------|--------|
| 2026-01-15 | 1.0 | Initial MVP (NMT only) |
| 2026-01-18 | 1.1 | Added Land Cover, SoilGrids, HSG |
| 2026-01-21 | 2.0 | Updated to reflect v0.3.1 features |
| 2026-02-07 | 3.0 | Added NMPT, Ortofotomapa, updated storage structure |
| 2026-02-08 | 3.1 | BDOT10k hydro category, rtree fix |
| 2026-02-08 | 3.2 | Geometry file selection (--geometry SHP/GPKG) |
| 2026-03-02 | 3.3 | Removed BDOT10k category filtering (download full package) |
| 2026-03-02 | 3.4 | PL-2000 support, bump to v0.5.0 |
| 2026-03-24 | 3.5 | WMS layer validation, 5m bugfix, bump to v0.6.1 |
| 2026-08-11 | 3.6 | Stage 0 (sources/transform/transport/providers-pl, CLI split, LAZ) + stage 1 (CZ/CUZK: DMR 5G/4G, --country/--target-crs, ADR-023); module tree and sections refreshed |
| 2026-08-18 | 3.7 | Documentation consistency review: stage 1 merge status, section 2 heading (0.5.0→0.7.0), `cache` command in 2.9, missing exports in 2.10 |
| 2026-08-22 | 3.8 | Consistency corrections after the 0.7.0 pre-release audit: WCS NMT only 1m/KRON86, 4 orthophoto WMS layers, SoilGrids without TERYT, per-source timeouts, edge convention and scale labels, `--country auto` semantics (CZ/PL rectangle extent, Info/Warning, partial success) |
| 2026-08-28 | 3.9 | Per-product data layout (ADR-026), --target-crs for PL (ADR-027), section 2.11 |
| 2026-09-28 | 3.10 | Max review wave: PL cutout as a library API (download_pl_cutout), sheet grid, R5 (NoCoverageError -> nodata + extra.missing_sheets), exports in 2.10, module tree, stage 2: PL+CZ mosaicking and cutout from PL-2000 sheets |
| 2026-09-29 | 3.11 | Historical live tests and audit before the repair wave: diagnoses of LAZ, S-JTSK, sheet index, ortho, CUZK limit and country dispatch; evidence of behaviour at sea and in border areas and entry into R6 |
| 2026-09-30 | 3.12 | Update after the repair wave: GUGiK record filter and cache, R5 in list/hierarchy, W1/phase error in 2180, EPSG:1622/1623 pin, 4 Mpx budget, LAZ axes |
| 2026-10-07 | 3.13 | GUGiK campaigns (ADR-030): section 2.12, `kampanie/` layout with the link in 2.11, rejected strategies in 3.1 |
| 2026-10-08 | 3.14 | Documentation review: erratum 5 of ADR-030 (local campaign on sheet index failure), CZ and --min-year x --year in 2.12, sidecars (HSG, general rule), BDOT10k GPKG assembled locally, full list of exports in 2.10, module tree and cache tables in 4.1, DLR in 5, no volatile values in 6.2 and history |
| 2026-10-08 | 3.15 | Roadmap to v1.0.0 (section 3.3): complete public GUGiK data, ready-made data, data manager (versioned store, project manifest), QGIS plugin, web GUI |
| 2026-10-09 | 3.16 | Campaign assembly tool (3.1) without an assigned release — did not make it into 0.7.1 (ADR-030 erratum 6) |
| 2026-10-10 | 3.17 | Data year selection (ADR-032): --year/--min-year/--max-year for NMT/NMPT/ortho/LAZ in 2.12, CZ and cutouts without a year; model A (year = year filter, --campaigns = number of flights) |
| 2026-10-10 | 3.18 | Second hard link `full_sheet/` and `--full-sheet` (ADR-033) in 2.11 and 2.12 |
| 2026-10-11 | 3.19 | Release v0.7.2: PL NMT/NMPT cutouts from GUGiK WCS with the PRG land mask (ADR-035), area query chunks on the source grid (ADR-034), status |
| 2026-10-12 | 3.20 | Versioned store plan 2/3 (ADR-036): LAZ, CZ and `bbox/` cutouts without a date in versions, update modes for each track, `DownloadManager.download_bbox` removed |
| 2026-10-13 | 3.21 | Full verification against the 0.8.0-dev code (ADR-037): 0.8.0 status and headings, `--scale` for PL-2000, BDOT10k/CORINE/SoilGrids via geometry and layer filter, fallback when the sheet index is unavailable (D14), campaign API, module tree (missing modules, exceptions), criteria 6.1 |
| 2026-10-13 | 3.22 | Explicit cutout mode (ADR-038): `--cutout` + `--horizontal-crs` instead of `--target-crs`, `--sheet-system` instead of `--system`; CZ area requires `--cutout` |
| 2026-10-13 | 3.23 | Subproject 3: reference to the GUGiK/ČÚZK inventory and the accepted spec (order of plans A–E) |
| 2026-10-15 | 3.24 | Plan A (ADR-041): NMT/NMPT variant registry (0.15–10 m grids, NMPT with `--resolution`), GUGiK archives as source files (`--format`), WFS sheet index, availability report `elevation availability`/`check_availability` (2.1, 2.3, 2.9, 2.10, 3.2, 3.3, 4.1, 6.1) |
| 2026-10-15 | 3.25 | Plan C of subproject 3 (ADR-042): PRG boundaries, EGiB and 3D building models (groups `boundaries`, `cadastre`, `models3d`, section 2.13), BDOT10k yearly archive (2.6), `download_collection`/`check_collection`, collection segment layout (2.11), limitations (3.1, 3.2), modules and `pyogrio` (4), sources (5) |
| 2026-10-16 | 3.26 | Plan D (ADR-042 D12-D17): CZ orthophoto and PL orthophoto cutout (2.4), CZ data ZABAGED, RUIAN, HY-NET and the `hydro` group (2.14), CLI and API (2.9, 2.10), limitations (3.1, 3.2), modules (4.1) |
| 2026-10-16 | 3.27 | Plans B and E (ADR-041, ADR-043) and review before release 0.8.0: purpose (1), BDOO (2.6), PRG addresses and special boundaries, RCN, mesh, trees and area limit (2.13), CZ Data50/250, geomorphology and cadastral map (2.14), names and maps (2.15), control networks and quasi-geoids (2.16), CLI (2.9), collection layout (2.11), VKM and outdated tasks (3.1), checksums, 8-part sheet codes and collection limitations (3.2), roadmap (3.3), modules, sources and criteria (4-6); list blocks as `text` |
| 2026-10-17 | 3.28 | Release v0.8.0: versioned store (ADR-036), project manifest (ADR-040), GUGiK/ČÚZK catalogue — plans A–E (ADR-041–043), CLI groups and unified API (ADR-039, ADR-044), status |

---

**Document version:** 3.28
**Last updated:** 2026-10-17
**Status:** Release v0.8.0 (2026-10-17)
