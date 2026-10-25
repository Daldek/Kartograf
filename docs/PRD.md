# PRD.md - Product Requirements Document
**Kartograf - Tool for Downloading Spatial Data**

**Version:** 4.8
**Date:** 2026-10-18
**Product Owner:** Piotr
**Status:** Release v0.8.0 (2026-10-17)

> The document describes the product requirements as implemented in the code
> of release v0.8.0, including the versioned store ADR-036 and CLI/API consistency ADR-037.
> Details of behaviour (messages, exit codes, edge cases) —
> `docs/SCOPE.md` and `docs/ARCHITECTURE.md`; rationale for decisions —
> `docs/DECISIONS.md`; change history — `docs/CHANGELOG.md`. Full list of
> CLI options: `kartograf <group> <command> --help`. Target requirements of version
> 1.0.0 — section 8 (roadmap and order of subprojects: `docs/SCOPE.md` 3.3).

---

## 1. Executive Summary

### 1.1 Problem Statement

Downloading spatial data from various sources (GUGiK, CUZK, Copernicus, ISRIC) is:
- **Time-consuming** - different web interfaces and API protocols
- **Complicated** - knowledge of identification systems is required (sheet codes (Polish godła), TERYT, bbox)
- **Inefficient** - files are downloaded one by one
- **Inconsistent** - different formats, CRSs and authentication for each source
- **Ambiguous** - the same GUGiK sheets occur in many survey campaigns, and the files carry no information about their origin

### 1.2 Solution

Kartograf is a CLI tool + Python library offering:
1. **Unified API** - a uniform interface (CLI = library, ADR-037) for elevation models, orthophotos and imagery, LAZ, land cover, soils, boundaries, cadastre, 3D models, names, maps and control networks
2. **Multiple Providers** - GUGiK (Poland), CUZK (Czechia), Copernicus CLMS (CORINE), ISRIC (SoilGrids); products and CLI groups: `docs/SCOPE.md` 2
3. **Intelligent Selection** - sheet code (PL-1992/PL-2000, CZ TM33/SM5), TERYT, KU (CZ), bbox, geometry file, whole country; country selection `--country {pl,cz,auto}`
4. **Automatic Processing** - merging of BDOT10k layers, HSG calculation, digital terrain model (NMT)/digital surface model (NMPT) cutout from GUGiK WCS with the PRG land mask and local reprojection (`--cutout --horizontal-crs`)
5. **Provenance** - canonical `data/` directory layout, `<file>.meta.json` metadata for downloads to the store, explicit choice of the GUGiK campaign scope
6. **Secure Auth** - Auth Proxy for isolating CLMS credentials
7. **Agent-ready** - `--json` in every command and `kartograf-*/1` documents from the library, command catalog (`kartograf commands list`), MCP server (`kartograf[mcp]`), `AGENTS.md` and `llms.txt` (ADR-046, ADR-052; section 3.27)

### 1.3 Target Users

| Persona | Needs | Usage |
|---------|----------|--------|
| **Hydrograf/Hydrolog developer** | NMT data, soil, HSG for calculations | Python API |
| **GIS specialist** | Topographic data, land cover | CLI |
| **Hydrologist** | HSG for the SCS-CN method | CLI + Python API |

The following are added in the target state (v1.0.0, section 8):

| Persona | Needs | Usage |
|---------|----------|--------|
| **QGIS user** | GUGiK data for an area from the map or a layer, ready for analysis | QGIS plugin |
| **Project team / company** | Shared data store, reuse in subsequent projects, record of the data versions used in a project | Web GUI + CLI |

---

## 2. Goals & Metrics

### 2.1 Technical Goals

| Goal | Target | Status |
|-----|--------|--------|
| Test coverage (core) | >= 80% | Gate threshold `fail_under = 80` in `pyproject.toml`; measurement: `pytest -m "not live" --cov=kartograf` |
| Offline tests | Tests without network (`conftest.py` blocks non-loopback sockets) | Network tests have the `live` marker |
| Reliability | >= 95% success rate | No automatic measurement of success rate in the code |
| Performance | Download < 60s | No guarantee: timeout and task time depend on the source and the number of files (section 7) |
| Code quality | ruff (check + format), mypy without new debt | The gate: `scripts/gate.sh` (`CLAUDE.md`) |

### 2.2 Integration Goals

| Goal | Status |
|-----|--------|
| Integration with Hydrograf | Ready |
| Integration with Hydrolog | Ready |
| Public API exports | Complete (`src/kartograf/__init__.py` `__all__`, section 5) |
| Common PL/CZ file grouping key (`extra.parent_request`) | Ready (PL+CZ merging on the consumer side) |

---

## 3. Core Features

### 3.1 Feature: NMT (digital terrain model)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Downloading NMT elevation data from GUGiK in all resolutions of the
ASC grids published by GUGiK — variant registry (ADR-041,
`kartograf.sources.variants`): EVRF2007 0.15m, 0.5m, 0.6m, 1m, 5m, 10m;
KRON86 0.5m, 1m — and GUGiK archives as source files, in the
vertical CRSs EVRF2007 and KRON86 (the choice is required since 0.8.0, with no
default value). Before downloading, the availability report states which combinations the
area has.

#### Requirements
- Sheet code PL-1992 (`SheetParser`, scales 1:1M–1:10k and 8-part sheet codes) and PL-2000 (`Parser2000`,
  zones EPSG:2176–2179); a PL-1992 sheet code coarser than 1:10000 is expanded
  to 1:10000 sheets without additional flags. For PL-2000 `--scale` is
  required with an area and a 1:10000 sheet code; it indicates the scale of the published sheets
  (usually 1:2000; USAGE 1.6).
- `--bbox` / `--geometry` (SHP/GPKG) without `--cutout` expands the area into a
  list of OpenData sheets (`--sheet-system {1992,2000}`); edges that merely touch
  are not an intersection.
- Selection of the sheet file from the GUGiK WFS sheet index (Polish skorowidz) (ADR-028, ADR-041): annual
  types exclusively from GetCapabilities, hard filter (whole sheet code, CRS,
  resolution, format consistent with the file URL), latest `aktualnosc`; no
  matching record = `NoCoverageError` with a hint of another variant
  from the registry, with no silent fallback to a different CRS, resolution or
  format. An incomplete WFS page = `DownloadError`, never an empty result.
  Records and lack of coverage are cached in `MetadataCache` (TTL 7 days,
  `--force` bypasses the read).
- Variants (resolution, vertical CRS, format) exclusively from the registry:
  CLI/API validation, `--help`, `kartograf elevation list-sources`, the store
  segment (`nmt/pl_1992_0.5m_evrf2007/`) and the record filter read one
  definition; a combination outside the registry = `ValidationError` before the network
  with a list of available labels.
- GUGiK archives (`--format XYZ|ASCII-NMT|TBD|TIN|TTN|GRD|DXF|DGN`): source
  file 1:1 with a sidecar as a version in the store (segment with the format
  token, e.g. `nmt/pl_1992_tbd_25m_kron86/`), without conversion, cutout
  and mosaic; sheets (different scales) are determined by the sheet index; `--scale`
  and `--cutout` with an archive = error. 8-part sheet codes (ASCII NMT 10 m, part of
  ASC 1 m) are downloaded with `--sheet <8-part sheet code>` (since 0.8.0, ADR-043 D10).
- NMT 100 m (voivodeship (Polish województwo) files from the ATOM feed, vertical CRS unknown) —
  section 3.19.
- Availability report (`kartograf elevation availability` =
  `check_availability`): for a PL area (sheet code, bbox, geometry) and a range of
  years, combinations of year × sheet system × resolution × vertical CRS ×
  format (also NMPT and LAZ tiles) with the number of full/incomplete sheets
  and completeness on PRG land (1 m grid), a download command hint
  (without `--root`, also for `project add`), `--details`,
  `--json` (`kartograf-availability/1`; fields `full_m2`, `sheet_records`
  and `campaign_coverage`, ADR-047); without downloading data, metadata
  cache (`--force`). USAGE 1.7.
- The sheet list tolerates missing coverage (R5): a sheet without data = `Warning:`
  and status `no_coverage`, exit code 0 with at least one file; a hard
  download failure = status `partial` (exit code 10) or `failed` (11) with the full list of failures.
- Parallel download of sheets (`--workers` = `download_data(workers=4)`;
  lower level `DownloadManager(workers=1)`); local versions are reused,
  a newer campaign is by default only reported (`--upgrade` downloads it).
- GUGiK campaigns (`--all-campaigns`, `--year`/`--min-year`/`--max-year`) — section 3.11.

#### Capabilities
```python
from pathlib import Path
from kartograf import BBox, DownloadManager, GugikProvider, SheetParser

# Sheet code parser
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)       # "1:10000"
print(parser.get_bbox())  # BBox(min_x=..., max_x=..., ...)

# Sheet hierarchy
hierarchy = parser.get_hierarchy_up()
descendants = parser.get_all_descendants("1:10000")

# Reverse lookup: bbox → sheet codes
from kartograf import find_sheets_for_bbox
bbox = BBox(771000, 509000, 772000, 510000, "EPSG:2180")
sheets = find_sheets_for_bbox(bbox, "1:10000", "1992")

# Reverse lookup: geometry file → sheet codes
from kartograf import find_sheets_for_geometry
sheets = find_sheets_for_geometry(Path("area.shp"), "1:10000", sheet_system="1992")

# Download by sheet code (ASC) — file in data/nmt/pl_1992_1m_evrf2007/...
# = kartograf elevation download --product nmt --sheet ... (ADR-037)
from kartograf import download_data
report = download_data(product="nmt", root="./data", sheet="N-34-130-D-d-2-4",
                       resolution="1m", vertical_crs="EVRF2007")
file = report.files[0].file  # VersionedFile: path, status, label, newer, unverified
# lower level: DownloadManager(...).download_sheet(...) -> DownloadResult
manager = DownloadManager(GugikProvider(vertical_crs="EVRF2007", resolution="1m"), root="./data")
result = manager.download_sheet("N-34-130-D-d-2-4")

# Raw WCS NMT 1m outside the versioned store: KRON86 from TIFF, EVRF2007 from ASC
# multipart; both paths yield a float32 GeoTIFF with heights (NMPT too).
# Cutout in the store (PRG mask, versions): download_pl_cutout (section 3.10).
kron = GugikProvider(vertical_crs="KRON86", resolution="1m")
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
path = kron.download_bbox(bbox, Path("area.tif"))

# Other resolutions from the registry (e.g. 0.5m; 5m, 0.15m, 0.6m, 10m EVRF2007 only)
manager_05 = DownloadManager(GugikProvider(vertical_crs="EVRF2007", resolution="0.5m"), root="./data")
result_05 = manager_05.download_sheet("N-33-58-A-c-1-3")  # DownloadResult

# GUGiK archive as a source file (format=; segment nmt/pl_<crs>_tbd_25m_kron86)
tbd = GugikProvider(vertical_crs="KRON86", resolution="25m", format="TBD")

# Availability report (without downloading) = kartograf elevation availability
from kartograf import check_availability
availability = check_availability(product="nmt", country="pl",
                                  bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"))
complete = [c for c in availability.combinations if c.complete]
print(complete[0].download_hint if complete else availability.to_json())
```

#### CLI Commands
```bash
kartograf sheet parse N-34-130-D-d-2-4
kartograf sheet parse N-34-130-D --hierarchy
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-130-D --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # coarser sheet code -> 1:10000 sheets (without --scale)
kartograf elevation download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # PL-2000: GUGiK sheet scale (USAGE 1.6)
kartograf elevation download --bbox 771000,509000,772000,510000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --bbox 19.93,50.05,19.95,50.07 --bbox-crs EPSG:4326 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --sheet N-34-130-D --resolution 5m --product nmt --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-33-58-A-c-1-3 --product nmt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010 --root ./data
kartograf elevation list-sources
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmpt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 --root ./data
kartograf imagery download --bbox 771000,509000,772000,510000 --product orto --country pl --sheet-system 1992 --root ./data
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --geometry area.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --root ./data
```

---

### 3.2 Feature: NMPT (digital surface model)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Downloading NMPT data (Digital Surface Model) from GUGiK — terrain + surface objects (trees, buildings).
Resolutions from the variant registry: ASC grids EVRF2007 0.5m, 0.6m, 1m,
KRON86 0.5m, 1m; XYZ archives 0.5m and 1m (KRON86). `--resolution` is required
since 0.8.0 (BREAKING: up to 0.7.x only 1m without the flag; `GugikNmptProvider(...,
resolution=)` is required); the `--cutout` cutout and WCS only 1m. Availability
report: `--product nmpt` (section 3.1). Selection of the sheet index record
and campaigns as for NMT (sections 3.1, 3.11). CLI `--bbox` without
`--cutout` downloads OpenData sheets; with `--cutout` a WCS cutout
(section 3.10). `GugikNmptProvider.download_bbox` returns float32 elevations
from WCS, not a colour TIFF.

#### Capabilities
```python
from pathlib import Path
from kartograf import BBox, GugikNmptProvider

# NMPT provider (resolution required from 0.8.0; WCS/download_bbox only 1m)
provider = GugikNmptProvider(vertical_crs="EVRF2007", resolution="1m")
provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))

# Via bbox (WCS)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"))
```

#### CLI Commands
```bash
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmpt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet M-34-64-D-d-2-1 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 771000,509000,772000,510000 --product nmpt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation availability --product nmpt --sheet M-34-64-D-d-2-1
```

---

### 3.3 Feature: Orthophoto (Standard Resolution)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Downloading orthophotos (aerial imagery) from GUGiK at the resolution given by the campaign (e.g. 25 cm, 10 cm).
The colour variant is required in the API (`GugikOrtoProvider(color="RGB")`; the CLI downloads RGB); `GugikOrtoProvider(color="CIR")`
selects infrared (a separate segment `orto/pl_<crs>_cir/`). Campaigns as for
NMT (section 3.11).

#### Capabilities
```python
from pathlib import Path
from kartograf import BBox, GugikOrtoProvider

# Orthophoto provider (no vertical CRS — 2D RGB; color="CIR" — infrared)
provider = GugikOrtoProvider(color="RGB")
provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))

# Via bbox (WCS, formats: GTiff, PNG, JPEG)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"), format="GTiff")
```

#### CLI Commands
```bash
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto --root ./data
kartograf imagery download --bbox 771000,509000,772000,510000 --product orto --country pl --sheet-system 1992 --root ./data
# WCS cutout in the store (0.8.0, ADR-042 D14): variant and pixel explicit, EPSG:2180 only
kartograf imagery download --bbox 566000,243000,566500,243500 --product orto --country pl --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m --root ./data
# CZ orthophoto (0.8.0, ADR-042 D13): SM5 sheet = JPEG + 3 JGW files, current vintage
kartograf imagery download --sheet CTES96 --product orto --root ./data
```

---

### 3.4 Feature: LAZ (LIDAR Point Clouds)

**Priority:** P1 (High)
**Status:** Production

#### Description
Downloading LIDAR point clouds (ALS survey data, `.laz` files) from GUGiK. Discovery is **area-based** via WFS: one 1:10000 sheet (or `--bbox` / `--geometry`) returns many LAZ tiles (with sheet codes finer than 1:10000), each with its own OpenData URL. The tile sheet code is not parseable and is treated as a label.

#### Capabilities
```python
from kartograf import BBox, GugikLazProvider, download_laz_area

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")

# Selecting and downloading tiles with sidecars (ADR-029) — a single call
result = download_laz_area(bbox=bbox, root="./data", vertical_crs="EVRF2007", min_density=12)
result.files                        # VersionedFile per tile (status new/local/...), hard links in data/laz/pl_<crs>_<vcrs>/
result.superseded                   # SupersededLazTile — older tiles covered by newer ones
result.failed                       # LazTileFailure — failures of individual tiles

# Tile selection only (without downloading)
provider = GugikLazProvider(vertical_crs="EVRF2007")
selection = provider.select_tiles(bbox, year=2024)  # LazTileSelection(tiles, superseded)
```

#### CLI Commands
```bash
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12 --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86 --country pl --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --all-campaigns --country pl --vertical-crs EVRF2007 --root ./data
kartograf elevation download --geometry area.shp --product laz --country pl --vertical-crs EVRF2007 --root ./data
```

#### Notes
- WFS EPSG:2180 accepts a bbox and returns the envelope in axis order (N,E);
  discovery rejects a tile set in which none intersects the area.
- Source: GUGiK WFS (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`)
- By default the newest tile per area (ADR-029): tiles are selected greedily
  starting from the newest `akt_rok`; an older tile is skipped when its intersection
  with the area is already covered by the selected ones (frames in EPSG:2180, tolerance
  `COVERAGE_TOLERANCE_M`); skipped tiles = `Info:` on stderr.
- `--year` — only that annual edition (checked against GetCapabilities);
  `--min-year`/`--max-year` — closed range of `akt_rok`;
  `--all-campaigns` — all tiles whose frame intersects the area,
  without coverage deduplication (section 3.11).
  `--year` is mutually exclusive with `--min-year`/`--max-year`.
- Failure of even one tile = `Error:` with the full list and status `partial` (exit code 10;
  `failed`, 11, when no tile came) (downloaded tiles
  are kept); tile sidecar, in `--bbox`/`--geometry` mode with `extra.parent_request`.
- PL only: for an area reaching into CZ an explicit `--country pl` is required.
- Parallel download (`--workers`), skipping existing files

---

### 3.5 Feature: BDOT10k (Land Cover - GUGiK)

**Priority:** P1
**Status:** Production

#### Description
Downloading land cover data from the Polish BDOT10k database (county (Polish powiat) TERYT code,
sheet code, bbox or geometry) into the version store (`landcover/pl_bdot10k_<format>[_<layers>]/teryt/<T>`,
ADR-036). GPKG format (default — layers merged into a single `.gpkg` file,
assembled in a local temporary directory and moved to the store, so it
also works on network shares) or SHP (`.zip` archive).

#### Capabilities
```python
from kartograf import download_landcover

# Download by TERYT -> landcover/pl_bdot10k_gpkg/teryt/1465.gpkg
report = download_landcover(product="bdot10k", root="./data", teryt="1465")
for item in report.files:
    print(item.unit, item.file.path, item.file.status)
print(report.ok, report.failed)  # failures of individual counties in failed

# Every county in the area (sheet=, bbox= in any CRS, geometry=)
download_landcover(product="bdot10k", root="./data", sheet="N-34-130-D",
                   layers=["PTWP", "SWRS"], workers=4)
```

#### Layers (58 BDOT10k classes; optional `--layers` filter in the resulting GPKG)

`--layers` accepts the code of each of the 58 classes of the BDOT10k classification (regulation of 2021,
Dz.U. 2021 poz. 1412; list: `kartograf landcover list-layers --product bdot10k`),
e.g. `BUBD`. A county package has tables only for the classes whose objects are in the county
(47–70 tables): absence of some of the selected classes is an `Info:` (`classes_absent`), absence of all —
a county error; an unknown code is a `ValidationError` before any network access. Below are the land
cover and hydrography classes:

**Land cover (PT* — 12 layers):**
| Layer | Description |
|---------|------|
| PTGN | Wasteland |
| PTKM | Transport areas |
| PTLZ | Forest areas |
| PTNZ | Undeveloped areas |
| PTPL | Squares |
| PTRK | Shrub vegetation |
| PTSO | Storage sites |
| PTTR | Agricultural areas |
| PTUT | Permanent crops |
| PTWP | Surface waters |
| PTWZ | Wetlands |
| PTZB | Built-up areas |

**Hydrography (SW* — 3 layers):**
| Layer | Description |
|---------|------|
| SWRS | Rivers and streams |
| SWKN | Canals |
| SWRM | Drainage ditches |

#### CLI Commands
```bash
kartograf landcover download --product bdot10k --teryt 1465 --root ./data
kartograf landcover download --product bdot10k --sheet N-34-130-D --root ./data
kartograf landcover list-layers --product bdot10k
```

---

### 3.6 Feature: CORINE Land Cover (Copernicus)

**Priority:** P1
**Status:** Production

#### Description
Downloading the European CORINE land cover classification (44 classes).

#### Capabilities
```python
from kartograf import download_landcover

# CLMS (CLMS_CREDENTIALS) -> landcover/eu_corine_2018/.../N-34-130-D.tif,
# version with a release label (e.g. V2020_20u1); without credentials a preview
# landcover/eu_corine_2018_preview/.../N-34-130-D.png (label = date)
report = download_landcover(product="corine", root="./data",
                            sheet="N-34-130-D", year=2018)
```

#### Available years
- 1990, 2000, 2006, 2012, 2018 (WMS preview of each year: Kartograf reads the raster layer of the year
  from GetCapabilities; a fully transparent image = `no_coverage`, no version)

#### Data sources (priority)
1. **CLMS API** - GeoTIFF with class codes (requires OAuth2)
2. **EEA Discomap WMS** - PNG preview (fallback)
3. **DLR WMS** - fallback for 1990

#### Auth Proxy (security)
```
CorineProvider → localhost HTTP → AuthProxy subprocess → CLMS API
                                  (credentials: CLMS_CREDENTIALS,
                                   fallback on macOS only: Keychain "clms-token")
```
Credentials are read exclusively by the Auth Proxy subprocess (`python -m
kartograf.auth.proxy`): the `CLMS_CREDENTIALS` variable (JSON: `client_id`,
`private_key`, `token_uri`) works on every system, Keychain (service
`clms-token`) is a fallback on macOS only. The main process sees neither keys
nor token. Without credentials — a PNG preview via WMS (sidecar
`extra.fallback = "wms_png"`). Direct mode from the library:
`CorineProvider(clms_credentials={...})`.

#### CLI Commands
```bash
kartograf landcover download --product corine --year 2018 --sheet N-34-130-D --root ./data
kartograf landcover list-layers --product corine
```

---

### 3.7 Feature: SoilGrids (Soil Data)

**Priority:** P1
**Status:** Production

#### Description
Downloading global soil data from ISRIC SoilGrids (250m resolution).

#### Capabilities
```python
from kartograf import download_soil

# Downloading organic carbon (sheet code or bbox; TERYT = ValidationError)
# -> soil/global_soilgrids_soc_0-5cm_mean/N-34/130/D/N-34-130-D.tif,
#    wersja z etykieta wydania SoilGrids (np. 2.0)
report = download_soil(
    root="./data", sheet="N-34-130-D",
    property="soc", depth="0-5cm", stat="mean",
)
print(report.files[0].file.path, report.failed, report.ok)

# Downloading clay content
download_soil(
    root="./data", sheet="N-34-130-D",
    property="clay", depth="15-30cm", stat="mean",
)
```

#### Available parameters (11)
The SoilGrids file contains integers in ISRIC units (the "In file" column);
conventional unit = value / divisor (the same in the sidecar: `extra.units`;
source: <https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html>).
| Parameter | Description | In file | Conventional (divisor) |
|----------|------|---------|---------------------------|
| bdod | Bulk density | cg/cm³ | kg/dm³ (100) |
| cec | Cation exchange capacity | mmol(c)/kg | cmol(c)/kg (10) |
| cfvo | Coarse fragments | cm³/dm³ | cm³/100 cm³ = % vol. (10) |
| clay | Clay content | g/kg | % (10) |
| nitrogen | Total nitrogen | cg/kg | g/kg (100) |
| ocd | Organic carbon density | hg/m³ | kg/m³ (10) |
| ocs | Organic carbon stock (0-30cm only) | t/ha | kg/m² (10) |
| phh2o | pH in H2O | pH x 10 | pH (10) |
| sand | Sand content | g/kg | % (10) |
| silt | Silt content | g/kg | % (10) |
| soc | Organic carbon | dg/kg | g/kg (10) |

The `uncertainty` statistic is the ratio 10 x (Q0.95 − Q0.05) / Q0.5 (unitless, / 10 = ratio).

#### Depths (6; `ocs`: 0-30cm only)
0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm

#### Statistics (5)
mean, Q0.05, Q0.5, Q0.95, uncertainty

#### CLI Commands
```bash
kartograf soil download --sheet N-34-130-D --property soc --root ./data --depth 0-5cm --stat mean
kartograf soil download --sheet N-34-130-D --property clay --depth 15-30cm --root ./data --stat mean
kartograf soil list-layers
```

---

### 3.8 Feature: HSG (Hydrologic Soil Groups)

**Priority:** P1
**Status:** Production

#### Description
Calculation of hydrologic soil groups (HSG) for the SCS-CN method based on SoilGrids
texture data — the clay/sand/silt inputs are SoilGrids versions in the same
store, the result is a version in `hsg/global_soilgrids_<depth>_<stat>/`
(the same inputs = version reused, ADR-036 D33).

#### Capabilities
```python
from kartograf import calculate_hsg, hsg_statistics

# Calculate HSG for a sheet code from stored or downloaded SoilGrids versions
report = calculate_hsg(root="./data", sheet="N-34-130-D", depth="0-5cm")
if report.ok and report.files:
    stats = hsg_statistics(report.files[0].file.path)
    for group, data in stats.items():
        print(f"Grupa {group}: {data['percent']:.1f}%")
else:
    print(report.failed)
```

#### Hydrologic groups
| Group | Infiltration | Textures | Runoff potential |
|-------|-------------|----------|-------------------|
| A | High | sand, loamy sand | Low |
| B | Moderate | sandy loam, loam | Moderate |
| C | Slow | clay loam | High |
| D | Very slow | clay | Very high |

#### Output format
GeoTIFF raster with values:
- 1 = Group A
- 2 = Group B
- 3 = Group C
- 4 = Group D
- 0 = NoData

The result gets a `.meta.json` version sidecar (`extra.derived = "hsg"`, source
layers, depth, statistic, class codes, `extra.source_files` with version
paths and sha256 of the inputs).

#### CLI Commands
```bash
kartograf soil hsg --sheet N-34-130-D --root ./data --depth 0-5cm
kartograf soil hsg --sheet N-34-130-D --summary --root ./data --depth 0-5cm
kartograf soil hsg --bbox 450000,550000,460000,560000 --root ./data --depth 0-5cm
kartograf soil hsg --geometry area.gpkg --layer catchments --root ./data --depth 0-5cm
kartograf soil hsg --sheet N-34-130-D --root ./data --depth 0-5cm --check --plan plan.json
```

---

### 3.9 Feature: NMT, NMPT and LAZ for Czechia (CUZK; DMR 5G/4G, DMP OK/1G, LAZ)

**Priority:** P1 (High)
**Status:** Production (NMT since v0.7.0; NMPT and LAZ since v0.8.0, plan B)

#### Description
Download of Czech models from CUZK: NMT DMR 5G (2 m, TM33 sheet code — a computable
grid of 2x2 km tiles in EPSG:3045) and DMR 4G (5 m, SM5 sheet code from the sheet index
`KladyMapovychListu`, EPSG:5514, or a TM33 tile), NMPT DMP OK (0.5 m, like
DMR 4G) and DMP 1G (2 m, like DMR 5G), as well as a bbox/geometry cutout via
`exportImage` (ArcGIS ImageServer) and LAZ point clouds of four models
(DMR 5G, DMR 4G, DMP 1G, DMP OK) — plan B. Other CZ data: orthophoto
(3.17), contours (3.19), vector data (3.21), cadastral map (3.23),
Geonames and ZTM (3.25), Bodove pole and QGZU-2013 (3.26).

#### Requirements
- `--country {pl,cz,auto}` (required with `--bbox`/`--geometry` since 0.8.0; with `--sheet` the country comes from the sheet code): country from the sheet code format or
  from the rectangular country envelopes (ADR-023); a border-area bbox/geometry under
  `auto` yields separate PL and CZ files with a shared `extra.parent_request` (no
  PL+CZ merging — R6, no assigned release). Code 0 = success of at least one country;
  if the other fails, a `Warning:`.
- Options without a Czech counterpart (`--vertical-crs KRON86`, a resolution
  that CUZK does not have, e.g. `--resolution 1m` or `0.5m` for NMT — NMPT
  `0.5m` is DMP OK, `--format`, `--coverage` and `--resolution` of the orthophoto
  cutout; for LAZ also `--year`, `--min-year`, `--max-year`,
  `--all-campaigns`, `--min-density`) resolve the disputed area to PL
  with `Info:`.
- The raster model follows from `--product` and `--resolution` (NMT `2m` DMR 5G /
  `5m` DMR 4G, NMPT `0.5m` DMP OK / `2m` DMP 1G); the SM5 sheet exists only
  for DMR 4G and DMP OK (`--resolution` may be omitted), a TM33 tile requires
  `--resolution`. Ready-made open-data files: SM5 sheet (EPSG:5514, Bpv) and TM33 tile
  of DMR 4G/DMP OK in EVRF2007 (EPSG:3045, no transformation); other
  TM33 tiles = `exportImage` + local warp.
- Requests to CUZK only in native EPSG:5514; a CZ raster area is always
  a single cutout and requires `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,
  EPSG:3045}` (ADR-038; `--bbox`/`--geometry` only); horizontal reprojection
  with a locally pinned operation — S-JTSK → ETRS89 step via
  EPSG:1622/1623 (ADR-024). `--cutout` with a sheet code = error. Under `auto` a PL+CZ
  raster area also requires `--cutout` (the PL part = WCS cutout).
- Native vertical CRS Bpv (ETRS89 files: EVRF2007); optionally
  `--vertical-crs EVRF2007` (EPSG:5621, pinned operation). KRON86
  is unavailable for CZ.
- LAZ CZ: `--model dmr5g|dmr4g|dmp1g|dmpok` required (with PL or a raster =
  `Error:`); the `.laz` file 1:1 from the ZIP, no transformation — `--vertical-crs Bpv`
  = SM5 sheets (EPSG:5514), `EVRF2007` = TM33 tiles (EPSG:3045); sheet code
  or area (index sheets), without `--cutout`; an error in one file does not
  stop the others. Under `auto` LAZ downloads PL tiles and CZ sheets.
- `exportImage` is tiled on the client side (budget of 4 Mpx per request),
  pixel exactly 0.5 m / 2 m / 5 m (model step).
- The SM5 sheet index is cached in `MetadataCache` (`sheet_cache`, TTL 30 days;
  `--force` queries again).
- CZ has no campaigns: `--all-campaigns`/`--min-year` without a PL part = `Error:`
  before the network (section 3.11).
- Report `elevation availability --country cz|auto` / `check_availability`:
  index sheets and one `HEAD` per file (publication date, size), without
  flight years and without downloading files; `404` = sheet without a file, any other failure
  = error; an unchecked `auto` part = `ok=False` (code 1).

#### Capabilities
```python
from pathlib import Path

from kartograf import BBox, create_cz_raster_provider, download_cz_laz

provider = create_cz_raster_provider("nmt", "2m", vertical_crs="Bpv")  # DMR 5G
provider.download("302_5550", Path("./302_5550.tif"))      # TM33 tile

provider_evrf = create_cz_raster_provider("nmt", "5m", vertical_crs="EVRF2007")
bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
provider_evrf.download_bbox(bbox, Path("./area.tif"))      # exportImage cutout

dmp = create_cz_raster_provider("nmpt", "0.5m", vertical_crs="EVRF2007")  # DMP OK
dmp.download("760_5518", Path("./760_5518.tif"))           # ETRS89 file 1:1

clouds = download_cz_laz(model="dmr5g", vertical_crs="Bpv", root="./data",
                         sheet="CTES96")                   # CZ LAZ in the store
```

#### CLI Commands
```bash
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv --root ./data # DMR 5G (TM33), 2m, Bpv
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv --root ./data # DMR 4G (SM5, 5m only), country from sheet code
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m --root ./data
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv --root ./data
kartograf elevation download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv --root ./data
kartograf elevation download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 5m --product nmt --vertical-crs Bpv --root ./data
kartograf elevation download --sheet CTES96 --product nmpt --vertical-crs Bpv --root ./data # DMP OK (SM5, 0.5m only)
kartograf elevation download --sheet 760_5518 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 --root ./data # DMP OK, ETRS89 file
kartograf elevation download --sheet CTES96 --product laz --model dmr5g --vertical-crs Bpv --root ./data # LAZ CZ
kartograf elevation availability --product nmpt --country cz "--bbox=-447000,-1114000,-446600,-1113600" --bbox-crs EPSG:5514
```

---

### 3.10 Feature: PL NMT/NMPT cutout (`--cutout`, ADR-035, ADR-038)

**Priority:** P1 (High)
**Status:** Production (since v0.7.2; version store since 0.8.0)

#### Description
A single 1 m NMT or NMPT GeoTIFF from the GUGiK WCS for `--bbox` or the
envelope of `--geometry` + `--cutout --horizontal-crs`. The PRG land mask sets
nodata outside Poland; the local warp uses a pinned operation.
Result: `<segment>/bbox/<coords>.tif` (a link to a version in
`versions/bbox/`, ADR-036 D15) with a sidecar;
under `auto` PL and CZ are two files with a shared `extra.parent_request`.

#### Requirements
- 1 m only (another resolution from the registry or an archive `--format`
  with `--cutout` = `Error:` before the network), both vertical CRSs. WCS NMT KRON86 returns
  float32 TIFF, EVRF2007 and NMPT — multipart ASC converted
  to float32 GeoTIFF. The request is aligned outwards to the 1 m sheet
  grid (`k + 0,5`), requests of even sizes (live
  measurement 2026-10-11), ASC split into chunks of up to 1 Mpx coverage pixels
  in NMT and 4 Mpx in NMPT (1 Mpx of the 1 m result).
- PRG mask `A00 - W02 - W03` before WCS: pixels outside land
  `-9999`, 0.0 inside the mask remains data.
  An all-nodata result = `Warning:`, code 0.
- WCS gives a server composition, not a choice of the newest sheet
  of exactly 1 m according to ADR-028; on a 0.5 m flight 1 m is decimation.
  No choice of year and campaign: `--all-campaigns`, year flags
  and `--full-sheet` with `--cutout` = `Error:`.
- By default the local cutout version is used without PRG/WCS queries
  (no cheap update signal); `--force` downloads again.
  New content becomes an immutable version, and the link changes
  only after success; with identical content no version is added.
  `--workers`, `--scale` have no effect on the WCS path. 5 m: sheets without `--cutout`.

#### Capabilities
```python
from kartograf import BBox, check_pl_cutout, download_pl_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
selection = dict(horizontal_crs="EPSG:5514", root="./data",
                 vertical_crs="EVRF2007", product="nmpt")
result = download_pl_cutout(bbox=bbox, **selection)
result.file.path, result.masked_pixels, result.zero_pixels, result.all_nodata
plan = check_pl_cutout(bbox=bbox, **selection)   # without downloading
```

#### CLI Commands
```bash
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:5514 --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmpt --cutout --horizontal-crs EPSG:2180 --vertical-crs EVRF2007 --root ./data
```

---

### 3.11 Feature: GUGiK campaigns (ADR-030)

**Priority:** P1 (High)
**Status:** Production (since v0.7.0; version store since 0.8.0)

#### Description
A PL NMT/NMPT/orthophoto sheet is sometimes published by GUGiK in many survey
campaigns. Kartograf stores each downloaded campaign separately and explicitly
marks which one is "current".

#### Requirements
- By default: the newest campaign of a sheet according to the ADR-028 rule within the year
  range, resolved on every run (network, when the 7-day cache
  has expired); an existing local version remains current, and a newer
  campaign is reported as available to download via `--upgrade`.
- `--all-campaigns`: every campaign of a sheet (within the year range) after the hard
  ADR-028 filter, with no limit on the count.
- Data year (ADR-032): `--year YYYY` = `--min-year YYYY --max-year YYYY`,
  closed bounds 1900..2100; year flags determine only the permitted
  years, `--all-campaigns` the number of flights. First the full list of
  campaigns of each sheet is checked: data only from other years = `YearRangeError`
  (`Error:` with the years and a hint) and nothing is downloaded.
- Campaign files as versions (ADR-036) in
  `<segment>/versions/<sheet_code hierarchy>/<date>_<id>_<sha8>/` with a MANDATORY,
  immutable sidecar (`extra.campaign`, `extra.version`); file format
  from the record's `format` field and content verification after download (AAIGrid
  header / TIFF signature); exclusive write (nothing is overwritten).
- The standard path `<segment>/<hierarchy>/<sheet code>.<ext>` is a HARD link
  to the newest local version; no copies and no symlinks (a file system
  without hard links = error). The link is moved only to a newer version,
  never backwards; the target is recorded in the sidecar (`extra.link`, `extra.link_target`).
  By default a newer campaign is not downloaded automatically (`Info:`,
  `--upgrade`); `--check` reports without downloading.
- A second link `<segment>/full_sheet/<hierarchy>/<sheet code>.<ext>`
  (ADR-033) to the newest local flight marked in the sheet index as
  full (`calyArkuszWypelnionyTrescia = TAK`, full = within the borders of Poland);
  `--full-sheet` / `DownloadManager(full_sheet=True)` fetches at most
  one such flight per sheet when the newest in the year range is not full.
- GUGiK sheet index unavailable (transport error) with the default selection without
  year flags and `--force` and an existing local campaign: the sheet is taken
  from the local campaign with a `Warning:` (erratum 5 of ADR-030); library:
  `DownloadResult.unverified` / `VersionedFile.unverified`.
- PL only: a task without a PL part with `--all-campaigns`, a year flag or
  `--full-sheet` = `Error:` before the network; a PL+CZ area under `auto` requires
  `--cutout` (ADR-038), and a `--cutout` cutout does not accept
  `--all-campaigns`, year flags or `--full-sheet` (PL sheets: `--country pl`).
- LAZ: `--all-campaigns` = tiles without coverage deduplication, year flags
  = `akt_rok` bounds; LAZ without links and without `--full-sheet`.

#### Capabilities
```python
from kartograf import DownloadManager, GugikProvider

provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager(provider, root="./data", min_year=2022, full_sheet=True)
result = manager.download_sheet("N-34-139-C-a-3-1")  # DownloadResult
result.campaign_files              # sheet code -> campaign files (downloaded and used)
result.full_links                  # sheet code -> full_sheet/ path
result.without_full                # sheets without a full flight in scope
# CampaignRef — campaign description (id, date, dt_pzgik, url, ...)
```

#### CLI Commands
```bash
kartograf elevation download --sheet N-34-130-D-d-2-4 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --all-campaigns --min-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
```

---

### 3.12 Feature: `data/` layout and download metadata (ADR-026, sidecars)

**Priority:** P0 (Critical)
**Status:** Production (version store since 0.8.0)

#### Requirements
- Canonical layout `data/<product>/<country>_<crs>[_<variant>][_<vcrs>]/...`
  (e.g. `nmt/pl_1992_1m_evrf2007/`, `orto/pl_1992_cir/`,
  `laz/pl_2000_evrf2007/`, `nmt/cz_dmr5g_bpv/`); segment templates
  in the source descriptors (`src/kartograf/sources/registry.py`). The
  `pl_1992`/`pl_2000` CRS comes from the sheet code format of each file (LAZ tiles — from the tile
  CRS). Cutouts in `<segment>/bbox/`. Segment table and migration:
  `docs/ARCHITECTURE.md` section 3; additional segments `landcover/`, `soil/`, `hsg/`
  and collections `<group>/<country>_<source>[_<tokens>]/{teryt|bbox|country|ku|...}`
  (ARCHITECTURE 3.3, rule 9).
- Every successful download through the CLI or the library's management layer
  (`download_data`, `DownloadManager`, `download_landcover`, `download_soil`,
  `download_pl_cutout`, `download_laz_area`, `download_collection`, CZ paths
  and `calculate_hsg`) gets a sidecar `<file>.meta.json` (schema
  `kartograf-meta/1`): dataset, country, product, horizontal and vertical CRS,
  resolution, nodata, request, licence, Kartograf version, `extra`
  (record origin `extra.source`, `extra.parent_request`, etc.).
  The sidecar of each version is mandatory; the sidecar of a link is best-effort.
- The sidecar records the actual CRS of the FILE; a PL-2000 sheet published by
  GUGiK in a different CRS than the sheet code indicates gives a `Warning:` (E17).

---

### 3.13 Feature: PRG administrative boundaries (`boundaries`, ADR-042)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
Boundaries of administrative and cadastral units from the national Register of
Boundaries (PRG) of GUGiK (source `pl.gugik.prg`) in the version store: a
voivodeship package, a national file, or units of one level intersecting the
task area as a single GeoPackage from WFS.

#### Requirements
- `--teryt <2 digits>`: voivodeship package (GML of all levels), ZIP 1:1
  in `boundaries/pl_prg_gml/teryt/<woj>.zip`; `--teryt <4 digits>` = error
  (county area: `--bbox`/`--geometry`).
- `--whole-country --country pl`: national SHP file (approx. 377 MB), size
  in `Warning:` before the transfer (`Notice` `whole_country_size`),
  `boundaries/pl_prg_shp/country/pl.zip`.
- Area (`--bbox`/`--sheet`/`--geometry` + `--country pl`) with the required
  `--level wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`: full
  geometries of units intersecting the area (no clipping), EPSG:2180,
  `boundaries/pl_prg_<level>/bbox/<coords>.gpkg`; completeness from the service's feature
  count, GPKG bytes reproducible within one GDAL version.
- Freshness signal `none`: `--check` reports "cannot be checked
  without downloading", new content only through `--force` (same
  content = unchanged, different = new version); version label = download date.

#### Capabilities
```python
from kartograf import BBox, download_collection

# = kartograf boundaries download ... (ADR-037)
report = download_collection(
    product="admin",
    root="./data",
    country="pl",
    bbox=BBox(550000, 220000, 590000, 270000, "EPSG:2180"),
    level="gmina",
)  # CollectionReport: files (UnitFile), failed (UnitFailure), stale, notices, ok
download_collection(product="admin", root="./data", teryt="12")
```

#### CLI Commands
```bash
kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 --root ./data
kartograf boundaries download --product admin --teryt 12 --root ./data
kartograf boundaries download --product admin --country pl --whole-country --root ./data
kartograf boundaries list-sources
```

---

### 3.14 Feature: EGiB — cadastral map (`cadastre`, ADR-042)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
Parcels and buildings from the Land and Building Register (EGiB) (source `pl.gugik.egib`)
in the version store: a county export or area objects from the GUGiK aggregate
WFS service.

#### Requirements
- `--teryt <4 digits>`: county export (GeoPackage with layers `dzialki`,
  `budynki`, `transakcje`; refreshed daily), GPKG extracted from the ZIP to
  `cadastre/pl_egib_gpkg/teryt/<T>.gpkg`; `--teryt <2 digits>` (voivodeship package
  approx. 1.4 GB) = error with the hint `--teryt <4 digits>`.
- Area (`--bbox`/`--sheet`/`--geometry` + `--country pl`): parcels
  and buildings intersecting the area in one EPSG:2180 GPKG,
  `cadastre/pl_egib/bbox/<coords>.gpkg`; counties not integrated with the aggregate
  service = gaps, restricted attributes = `brak_uprawnien`; the `DATA` field
  is left out of the file, values in the sidecar `extra.source.dropped_fields`.
- Freshness signal `none`, version label = download date (as in 3.13).

#### Capabilities
```python
from kartograf import check_collection, download_collection

report = download_collection(product="map", root="./data", teryt="1261")
print([item.file.path for item in report.files], report.ok)
plan = check_collection(product="map", root="./data", teryt="1261")  # UpdatePlan
```

#### CLI Commands
```bash
kartograf cadastre download --product map --teryt 1261 --root ./data
kartograf cadastre download --product map --country pl --bbox 566000,244000,566400,244400 --root ./data
kartograf cadastre list-sources
```

---

### 3.15 Feature: 3D building models (`models3d`, ADR-042)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
GUGiK CityGML 3D building models (source `pl.gugik.buildings`): a county
ZIP package stored 1:1 in the version store, release chosen explicitly
(LoD and year).

#### Requirements
- Selection: `--teryt <4 digits>` or an area (+ `--country pl`; packages of each
  county of the area according to PRG, `Notice` `unit_list`); `--whole-country` = error
  (national files 3.5-4.1 GB out of scope).
- Release: `--lod 1 --year 2019|2021|2022|2024` or `--lod 2` (the only
  release 2017, `--year` may be omitted); no default values.
- File `models3d/pl_buildings_lod<N>_<year>/teryt/<T>.zip`; version label
  = release year; signal `none`.
- Vertical CRS in the sidecar from the data: LoD1 2019 and LoD2 2017 = EPSG:9650
  (PL-KRON86-NH), LoD1 2021/2022/2024 = EPSG:9651 (PL-EVRF2007-NH).
- LoD2 does not cover the country: a missing county package = error for that county.

#### Capabilities
```python
from kartograf import download_collection

download_collection(product="buildings", root="./data", teryt="1261", lod=1, year=2024)
download_collection(product="buildings", root="./data", teryt="1261", lod=2)
```

#### CLI Commands
```bash
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 --root ./data
kartograf models3d download --product buildings --lod 2 --country pl --bbox 566000,244000,566400,244400 --root ./data
kartograf models3d list-sources
```

---

### 3.16 Feature: BDOT10k annual archive (ADR-042 D11)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
BDOT10k annual editions 2014-2025 (state at the beginning of the year) from the GUGiK archive: the original
county ZIP package stored 1:1 in the version store, alongside the current
packages from section 3.5.

#### Requirements
- `--year 2014..2025` requires `--format GML` or `SHP`; GPKG, `--layers`
  and `--keep-raw` with `--year` = error; `--format GML` without `--year` = error
  with a hint; without `--year` the current packages as before (GPKG/SHP).
- File `landcover/pl_bdot10k_<format>_<year>/teryt/<T>.zip`; area =
  packages of each county (PRG); version label = annual edition, signal `none`.
- An identical annual edition (the same SHA-256 in another release of the same county)
  does not take up space a second time: hard link, status `relabeled`.
- A missing county package (404) = `NoCoverageError` for that county.

#### Capabilities
```python
from kartograf import download_landcover

report = download_landcover(product="bdot10k", root="./data",
                            teryt="1261", year=2024, format="SHP")
# -> landcover/pl_bdot10k_shp_2024/teryt/1261.zip
```

#### CLI Commands
```bash
kartograf landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP --root ./data
kartograf landcover download --product bdot10k --sheet N-34-130-D --year 2018 --format GML --root ./data
```

---

### 3.17 Feature: CZ orthophoto and PL orthophoto cutout (`imagery`, ADR-042 D13-D14)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
CUZK orthophoto for SM5 sheets and one GUGiK orthophoto cutout
from WCS for a PL area, both in the version store.

#### Requirements
- CZ (`--country cz`, `cz.cuzk.orto`): an SM5 sheet or the SM5 sheets
  of an area from the CUZK index; four CUZK ZIP files 1:1 in `orto/cz_sjtsk/`
  (`<sheet_code>.jpg`, `.jgw` EPSG:5514, `.TM33N.jgw`, `.TM34N.jgw`); only the
  current annual edition (archived CUZK orthophotos are paid); the release from the ATOM
  feed is the version label and the `--check` signal.
- PL cutout (`--cutout --horizontal-crs EPSG:2180`): `--coverage
  standard|high` and `--resolution 0.1m|0.25m|0.5m|1m` required; RGB from WCS
  without resampling, grid aligned to the pixel, chunks up to 200 x 200 m
  -> `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`; signal `none`.
- Orthophoto sheets without `--cutout` do not accept `--resolution`
  (source pixel); under `--country auto` an area near the border yields PL
  and CZ sheets with a shared `extra.parent_request`.

#### Capabilities
```python
from kartograf import BBox, download_cz_orto_sheet, download_image_cutout

cz = download_cz_orto_sheet(sheet="CTES96", root="./data")  # CzOrtoResult
cut = download_image_cutout(
    product="orto", bbox=BBox(566000, 243000, 566500, 243500, "EPSG:2180"),
    horizontal_crs="EPSG:2180", root="./data",
    coverage="standard", resolution="0.25m",
)  # ImageCutoutResult
```

#### CLI Commands
```bash
kartograf imagery download --sheet CTES96 --product orto --root ./data
kartograf imagery download --bbox 566000,243000,566500,243500 --product orto --country pl --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m --root ./data
```

---

### 3.18 Feature: GUGiK imagery — intensity, true orthophoto, oblique orthophoto (`imagery`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
Three GUGiK imagery products on the orthophoto sheet path (campaigns,
versions, `--year`/`--all-campaigns`, signal `index`).

#### Requirements
- `--product intensity` (`pl.gugik.intensity`): LIDAR intensity images,
  1 band 0.25 m, PL-1992 and PL-2000 sheets -> `intensity/pl_<crs>/`.
- `--product true-orto` (`pl.gugik.true_orto`): true orthophoto
  of selected cities, 8-part PL-1992 sheets -> `true-orto/pl_1992/`;
  cutout from WCS `True_Orthoimagery` (`--cutout --horizontal-crs EPSG:2180
  --resolution 0.05m`..`1m`, without `--coverage`) -> `true-orto/pl_1992_<pixel>/bbox/`.
- `--product oblique-orto` (`pl.gugik.oblique_orto`): oblique orthophoto,
  PL-2000 sheets, a sheet = four direction files `<sheet_code>_n|e|s|w.tif`
  in `oblique-orto/pl_2000/`; `--direction` selects a part.
- A product with a single sheet system may omit `--sheet-system`; a sheet
  over 100 MiB announces a `Notice` `download_size` (size from `HEAD`).

#### CLI Commands
```bash
kartograf imagery download --product intensity --sheet M-34-64-D-d-1-4 --root ./data
kartograf imagery download --product true-orto --sheet N-34-50-A-c-3-2-3 --root ./data
kartograf imagery download --product true-orto --country pl --bbox 470100,740100,470200,740200 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m --root ./data
kartograf imagery download --product oblique-orto --sheet 7.125.11.08 --direction n --root ./data
```

---

### 3.19 Feature: NMT 100 m (PL) and ZABAGED contours (CZ) (`elevation`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
Two file products of the `elevation` group without a cutout: GUGiK NMT 100 m
(voivodeship files) and CUZK ZABAGED contours (SM5 sheets).

#### Requirements
- NMT 100 m (`--product nmt --resolution 100m --country pl`,
  `pl.gugik.nmt_100m`, ADR-043 D10): XYZ files of the voivodeships of the area (according to PRG)
  from the GUGiK ATOM feed, ZIP 1:1 in `nmt/pl_1992_100m/teryt/<woj>.zip`,
  release from the feed (signal `metadata`). Vertical CRS unknown: sidecar
  `vertical_crs: null` with a source annotation; `--vertical-crs`, sheet,
  flight and cutout flags, and `--country cz` = error before any network access.
- Contours (`--product contours --country cz --format SHP|DGN`,
  `cz.cuzk.zabaged_contours_shp|dgn`): SM5 sheet ZIP from openzu 1:1
  (members and CRC checked before the version is written) in
  `contours/cz_zabaged_<format>/`; SM5 sheet code or the SM5 sheets of an area
  from the index; S-JTSK, Bpv heights; signal `http`.

#### CLI Commands
```bash
kartograf elevation download --product nmt --resolution 100m --country pl --bbox 564000,241000,570000,247000 --root ./data
kartograf elevation download --product contours --format SHP --sheet CTES96 --root ./data
```

---

### 3.20 Feature: BDOO (`landcover`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
The GUGiK General Geographic Objects Database (1:250 000): a voivodeship GML package
per annual edition, stored 1:1 in the version store.

#### Requirements
- `--product bdoo` with the required `--year` (2015, 2021-2026); `--teryt`
  2 digits (a county code (powiat) = error with a hint), the area = voivodeship packages
  of its counties according to PRG -> `landcover/pl_bdoo_<year>/teryt/<woj>.zip`.
- `--layers` (classes of the annual edition: `landcover list-layers --product bdoo`)
  writes a ZIP of the files of the selected classes (`pl_bdoo_<year>_<classes>`); a class with no
  file in the package = `Info:` (`classes_absent`), a class outside the annual edition = error.
- Version label = annual edition, signal `none`.

#### CLI Commands
```bash
kartograf landcover download --product bdoo --teryt 12 --year 2023 --root ./data
kartograf landcover download --product bdoo --bbox 523000,253000,528000,258000 --year 2023 --layers KUIK,PTWP --root ./data
```

---

### 3.21 Feature: CUZK vector data — ZABAGED, Data50, Data250, RUIAN, HY-NET, geomorphology (ADR-042 D15-D17, ADR-043)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
CUZK vector data in the collection shape: an area yields one GeoPackage
of features intersecting the area (full geometries, EPSG:5514), and
`--whole-country` yields the CUZK national file 1:1 with its size in a `Warning:` before
the transfer.

#### Requirements
- ZABAGED (`landcover --product zabaged`): 22 land cover and water layers
  (without converting classes to BDOT10k codes); national GPKG file
  in EPSG:5514 or EPSG:3045 (`--horizontal-crs` required) from the ATOM feed.
- Data50 and Data250 (`landcover --product data50|data250`): all
  feature layers of the REST service (69 / 116); national SHP file as for ZABAGED.
- RUIAN (`boundaries --product admin --country cz|auto`): `--level
  kraj|okres|obec|katastralni-uzemi`, under `auto` the level is per country
  (`--level pl=gmina,cz=obec`); national SHP file.
- HY-NET (group `hydro`, `--product network --country cz`):
  `WatercourseLink` and `HydroNode`; national GPKG file (EPSG:3045).
- Geomorphology (`boundaries --product geomorphology --country cz`):
  required `--level subprovincie`..`cast`, no national file.
- A PL sheet code as the area and `--teryt` apply to PL only; EPSG:5514 coordinates
  are negative (`--bbox=...`).

#### CLI Commands
```bash
kartograf landcover download --product zabaged "--bbox=-460000,-1120000,-450000,-1110000" --bbox-crs EPSG:5514 --root ./data
kartograf landcover download --product data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326 --root ./data
kartograf boundaries download --product admin --country cz --level obec "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 --root ./data
kartograf boundaries download --product geomorphology --country cz --level celek "--bbox=-452000,-1112000,-450000,-1110000" --bbox-crs EPSG:5514 --root ./data
kartograf hydro download --product network --country cz --whole-country --root ./data
```

---

### 3.22 Feature: PRG addresses, PRG special boundaries and RCN (`boundaries`, `cadastre`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
Three GUGiK collection products: address points and streets, 44 kinds of special
boundaries, and the real estate price register.

#### Requirements
- Addresses (`boundaries --product addresses`, `pl.gugik.prg_addresses`):
  area = one EPSG:2180 GPKG with address points and streets (WFS KIN);
  `--teryt <4 digits>` = county SHP package 1:1; `--whole-country --format
  SHP|GML` = national file.
- Special boundaries (`boundaries --product special`, `pl.gugik.prg_special`):
  area = one OGC:CRS84 GPKG with a layer per boundary kind (OGC API PRG,
  minutes); census districts only in the national file — `Info:` (`area_omitted`);
  `--whole-country --format SHP|GML`; `--teryt` = error.
- RCN (`cadastre --product prices`, `pl.gugik.rcn`): `--teryt` 4 digits
  (county) or 2 digits (voivodeship), the area = export of each county;
  GPKG with layers `transakcje_dzialki`, `transakcje_budynki`,
  `transakcje_lokale`, unpacked and checked locally
  (`cadastre/pl_rcn/teryt/<T>.gpkg`); refreshed daily.
- Version label = download date, signal `none`.

#### CLI Commands
```bash
kartograf boundaries download --product addresses --country pl --bbox 566000,243500,566500,244000 --root ./data
kartograf boundaries download --product addresses --teryt 1261 --root ./data
kartograf boundaries download --product special --country pl --bbox 21.0,52.22,21.01,52.23 --bbox-crs EPSG:4326 --root ./data
kartograf cadastre download --product prices --teryt 1201 --root ./data
```

---

### 3.23 Feature: CZ cadastral map (`cadastre`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
CUZK katastrální území packages (the equivalent of EGiB) written 1:1
to the version store.

#### Requirements
- `--product map --country cz` with the required `--format SHP|DXF|DGN|VFK`:
  `--ku <6 digits>` or the KU of the area according to RUIAN (`Info:` with the list of KU) ->
  `cadastre/cz_cadastral-map_<format>/ku/<KU>.zip`; signal `http`
  (`ETag`/`Last-Modified`); a KU without a package = an error for that KU.
- The VKM format is outside 0.8.0 (CUZK pilot, `docs/SCOPE.md` 3.1).

#### CLI Commands
```bash
kartograf cadastre download --product map --ku 623164 --format SHP --root ./data
kartograf cadastre download --product map --country cz --format SHP "--bbox=-452000,-1112000,-450000,-1110500" --bbox-crs EPSG:5514 --root ./data
```

---

### 3.24 Feature: 3D city mesh and tree models (`models3d`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
GUGiK city mesh models (OBJ with textures) and 3D tree models (CityGML LoD1),
PL only.

#### Requirements
- Mesh (`--product mesh`, `pl.gugik.mesh`): WFS index tiles
  intersecting the area, each as the original ZIP (OBJ, MTL, JPG)
  in `models3d/pl_mesh/<crs>[/<zone>]/<file of the record>.zip` (`1992` or
  `2000/<zone>`, EPSG:9651 heights); tile = the file of one record, `--year`
  filters records; label = date and work report number, signal `index`.
- Trees (`--product trees`, `pl.gugik.trees`): the 2023 release, a county package
  or the county packages of the area (0.3-25 GB, size in a `Warning:`),
  `models3d/pl_trees_lod1_2023/teryt/<T>.zip`.
- Area limit (all collections): an area that would download more than
  100 files or more than 10 GB ends with `ValidationError`/`Error:`
  before the download, with the file count, the size and a hint (narrow the
  area, choose a unit, run a plan with part of the items); no
  bypass flag.

#### CLI Commands
```bash
kartograf models3d download --product mesh --country pl --bbox 566200,244650,566250,244700 --root ./data
kartograf models3d download --product trees --teryt 3063 --root ./data
```

---

### 3.25 Feature: Geographic names and topographic maps (`names`, `maps`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
GUGiK geographic names (PRNG RP and Polish names of the world) and CUZK
(Geonames), and ready-made map sheets: BDOT10k visualisations (PL) and ZTM (CZ).

#### Requirements
- `names --product geographic --country pl`: area = OGC:CRS84 GPKG
  (OGC API Features), `--whole-country --format GML|SHP|XLSX` = two national
  files (`miejscowosci`, `obiekty-fizjograficzne`); `--product world` —
  Polish names of the world, also outside Poland.
- `names --product geographic --country cz` (Geonames): area = EPSG:5514
  GPKG (25 layers), `--whole-country --format GPKG|FGDB
  --horizontal-crs EPSG:5514|EPSG:3045` = ZIP from the ATOM feed (signal `metadata`).
- `maps --product topographic`: `--scale` and `--format` required; PL —
  sheets 1:10000-1:100000, TIFF or PDF, the `Stan bazy` date from the index as
  the label and signal `index`; CZ — ZTM 1:5000-1:250000, S-JTSK or
  ETRS89 system from the sheet code (area: `--sheet-system`), TIFF/PDF (S-JTSK also
  DGN/SHP), signal `http`.

#### CLI Commands
```bash
kartograf names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326 --root ./data
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 --root ./data
kartograf maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF --root ./data
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF --root ./data
```

---

### 3.26 Feature: Geodetic control networks and quasi-geoids (`geodesy`, ADR-043)

**Priority:** P2 (Medium)
**Status:** Production (0.8.0)

#### Description
Geodetic control points from GUGiK (with county packages and sheet archives)
and CUZK (Bodove pole) and the PL-geoid2021 and QGZU-2013 quasi-geoid models.

#### Requirements
- `--product control --network <network>` (required): PL `horizontal`,
  `vertical`, `gravity`, `magnetic` — area = GPKG of network points
  (EPSG:2180); `--teryt` with `horizontal|vertical` = county package (XLS,
  JPG); `archive-1942`, `archive-kronsztadt60` = scans of 1:100 000 sheets;
  CZ `gnss`, `horizontal`, `densification`, `horizontal-detailed`,
  `vertical`, `vertical-detailed`, `gravity` — area = GPKG of network layers
  (EPSG:5514). A value available only in another choice names that choice.
- `--product geoid --whole-country`: PL-geoid2021 (TXT 1:1) or
  QGZU-2013 (ZIP from the ATOM feed, release = label); area = error.
  Kartograf does not apply the models to other data.

#### CLI Commands
```bash
kartograf geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000 --root ./data
kartograf geodesy download --product control --network horizontal --teryt 1201 --root ./data
kartograf geodesy download --product geoid --country pl --whole-country --root ./data
kartograf geodesy list-sources
```

### 3.27 Feature: Interface for AI agents (ADR-046)

**Priority:** P1 (High)
**Status:** Production (0.8.0)

#### Description
AI agents (Claude Code, the Archiwista assistant, scripts, other servers) use
Kartograf through the CLI, the library and the MCP server and get the same task as the
same JSON document; they can discover commands and allowed values without reading the code and
fix an error without parsing text.

#### Requirements
- `--json` in every CLI command: stdout is one `kartograf-result/1` envelope (`status`, `result`
  with the `kartograf-<kind>/1` document of the command, `items`, `notices`; first key `schema`;
  20 documents of the library), with no progress bar and no status lines
  (notices go in `notices`); an error is `kartograf-error/1` (`code`, `title`, `message`, `hint`,
  `details`, `exit_code`, `command`) on the last line of stderr, with nothing on stdout. The
  documents are returned by the library (`to_dict()`/`to_json()`), and the CLI and MCP only print them.
- Stable error codes (`code`) and exit codes from the Nogat registry (ADR-049, ADR-051): 0 (ok),
  10 (`partial`) and 11 (`failed`) for a batch with failed units, 2 (`validation_error`), 5
  (`source_unavailable`), 14 (`no_data`), the other codes of the registry, 130 (Ctrl-C), 143
  (SIGTERM); `ValidationError` carries `option` and `allowed`, and the hint (`hint`) carries the
  allowed values and an example command. One code table: `docs/USAGE.md` 9.3.
- Command catalog (`kartograf commands list`, `kartograf commands schema`, `list_commands()`,
  `command_schema()`, `kartograf-command-list/1`, `kartograf-commands/1`):
  groups, products, commands, parameters (flag, API argument, kind, required, allowed
  values), constraints and examples; the single source of truth: the CLI parser,
  project options and MCP tool schemas are generated from the declarations. Command layer:
  `parse_command`, `validate_command`, `format_command`, `run_command`,
  `check_command` (KB-1..KB-5 of the Archiwista).
- MCP server `kartograf-mcp` (extra `kartograf[mcp]`, stdio): 39 tools 1:1
  with the commands (`kartograf_<group>_<command>`), result = the `kartograf-result/1` envelope (`outputSchema`),
  `is_error` only for an error, with no default values affecting data (a given `root`
  absolute, one left out the default store inside `--allow-dir`, `bbox` with `bbox_crs`),
  progress through MCP notifications,
  `--tools`, `--allow-dir` and `--allow-writes` (without it the server only reads and plans).
- `kartograf/py.typed` (PEP 561), the generated `AGENTS.md` and `llms.txt` (`kartograf commands
  guide`), `scripts/gate.sh`, `python -m kartograf`; a rule for agents from other repositories
  in `CLAUDE.md`.
- Outside the scope of 0.8.0: the HTTP transport of the MCP server, cancelling downloads (KC),
  download size estimate (KH).

#### CLI Commands
```bash
kartograf commands list --json
kartograf elevation availability --product nmt --sheet N-34-130-D-d-2-4 --json
claude mcp add kartograf -- kartograf-mcp
```

---

## 4. Architecture

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Interface                                │
├──────────────────────────────┬──────────────────────────────────────────┤
│  CLI (--country pl|cz|auto)  │              Python API                  │
└──────────────┬───────────────┴───────────────────┬──────────────────────┘
               │                                   │
               v                                   v
┌─────────────────────────────────────────────────────────────────────────┐
│                        Command functions / API                         │
├────────────────────────────────────┬────────────────────────────────────┤
│ download_data (NMT, NMPT, imagery) │ download_landcover / download_soil │
│ DownloadManager (PL sheets,        │ calculate_hsg / check_hsg          │
│   campaigns ADR-030)               │ download_collection (collections:  │
│ download_pl_cutout (ADR-035)       │   boundaries, cadastre, 3D models, │
│ download_laz_area (ADR-029)        │   names, maps, control networks; ADR-042)    │
│ CZ paths: sheet, cutout, LAZ       │                                    │
└──────────────┬─────────────────────┴───────────────────┬────────────────┘
               │                                         │
               v                                         v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                   Providers                                      │
├────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────┬─────────┤
│ Gugik  │ GugikNmpt│ GugikImg │ GugikLaz │ Cuzk*    │ Bdot10k  │ Corine │SoilGrids│
│ (NMT)  │ (NMPT)   │ (imagery)│ (LAZ)    │ (CZ)     │          │        │         │
└───┬────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴───┬────┴────┬────┘
    v         v          v          v          v          v         v         v
┌───────────────────────┐ ┌─────────┐ ┌────────────┐ ┌────────┐ ┌───────────┐ ┌─────┐
│ GUGiK WCS / OpenData  │ │GUGiK WFS│ │ CUZK       │ │ GUGiK  │ │ CLMS API  │ │ISRIC│
│ + sheet index WFS/WMS │ │+OpenData│ │ ArcGIS REST│ │OpenData│ │(AuthProxy)│ │ WCS │
│ (NMT, NMPT, Orthophoto)│ │ (LAZ)   │ │ + openzu   │ │(BDOT10k│ │ + WMS PNG │ │     │
└───────────────────────┘ └─────────┘ └────────────┘ └────────┘ └───────────┘ └─────┘

Shared layers: sources/ (descriptors, variant registry, sidecars), transport/ (HTTP, mosaic),
transform/ (pinned CRS transformations), cache/ (MetadataCache, SQLite).
Sheet index: WFS for NMT/NMPT and LAZ (ADR-041), WMS GetFeatureInfo for imagery;
the availability report (check_availability) reads the same WFS and the PRG mask.
GugikImg = GugikImageProvider (orthophoto: GugikOrtoProvider, intensity, true orthophoto,
oblique orthophoto); Cuzk* = CuzkRasterProvider (NMT/NMPT) and CuzkLazProvider. Collections have no
providers: download_collection and the transport/ engines (unit_package, feature_bbox, atom_files)
read channel parameters from the descriptors (ADR-042, ADR-043).
```

### 4.2 Hydrology Module

```
┌─────────────────────────────────────────────────────────────┐
│              calculate_hsg / check_hsg                      │
├─────────────────────────────────────────────────────────────┤
│  HsgReport(files, inputs, failed, stale, notices, ok)        │
│  hsg_statistics(path)                                        │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│              SoilGridsProvider                              │
│  (downloads clay, sand, silt)                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│  USDA Texture Triangle  →  HSG Mapping                      │
│  (12 texture classes)      (4 hydrologic groups)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Public API

The source of truth is `src/kartograf/__init__.py` (`__all__`); the list below
is consistent with it and must be updated together with it.

```python
from kartograf import (
    # Cache
    MetadataCache,

    # Notices
    Notice,

    # Core
    SheetParser,
    Parser2000,
    ParserTM33,
    BBox,
    find_sheets_for_bbox,
    find_sheets_2000_for_bbox,
    find_sheets_for_geometry,
    get_overall_bbox,
    transform_bbox,
    parent_request_for,

    # Download (command level: `kartograf elevation download` / `imagery download`, spec 4.1)
    download_data,
    check_data,
    DataReport,
    UnitFile,
    UnitFailure,

    # Download (collections: `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`, ADR-042)
    download_collection,
    check_collection,
    CollectionReport,

    # Download (orthophoto: CZ SM5 sheet; PL image cutout, ADR-042 D13-D14, ADR-044)
    download_cz_orto_sheet,
    check_cz_orto_sheet,
    CzOrtoResult,
    download_image_cutout,
    check_image_cutout,
    ImageCutoutResult,

    # Availability report (`kartograf elevation availability`, ADR-041)
    check_availability,
    AvailabilityReport,
    AvailabilityCombination,
    AvailabilityRecord,
    AvailabilityCampaign,
    AvailabilityArea,

    # Download (NMT)
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    CampaignRef,
    FileStorage,

    # Download (versioned store, update plan)
    UpdateMode,
    VersionedFile,
    VersionRef,
    PlanItem,
    UpdatePlan,

    # Download (PL cutout: WCS ADR-035)
    PlCutoutResult,
    check_pl_cutout,
    download_pl_cutout,

    # Download (CZ cutout, countries)
    CountryPart,
    countries_for_bbox,
    split_bbox_by_country,
    CzCutoutResult,
    check_cz_cutout,
    download_cz_cutout,

    # Download (CZ sheet: SM5 sheet / TM33 tile, R4)
    CzSheetResult,
    check_cz_sheet,
    download_cz_sheet,

    # Download (LAZ CZ: model, sheet/area)
    CzLazResult,
    CzLazFailure,
    check_cz_laz,
    download_cz_laz,

    # Download (LAZ tiles, D17)
    LazDownloadResult,
    LazTileFailure,
    check_laz_area,
    download_laz_area,

    # Land cover and soil (command level, ADR-044)
    download_landcover,
    check_landcover,
    LandCoverReport,
    download_soil,
    check_soil,
    SoilReport,
    Edition,
    # Providers
    BaseProvider,
    GugikProvider,
    GugikNmptProvider,
    GugikOrtoProvider,
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
    LandCoverProvider,
    Bdot10kProvider,
    Bdot10kPackage,
    CorineProvider,
    SoilGridsProvider,
    CuzkRasterProvider,
    create_cz_raster_provider,
    CuzkLazProvider,

    # TERYT (PRG)
    discover_teryts_for_bbox,
    teryt_for_point,

    # Hydrology
    calculate_hsg,
    check_hsg,
    HsgReport,
    hsg_statistics,
    hsg_from_rasters,

    # Project manifest (kartograf-project/1, ADR-040)
    init_project,
    open_project,
    add_project_task,
    remove_project_task,
    download_project,
    check_project,
    get_project_status,
    verify_project,
    Project,
    ProjectTask,
    PinnedFile,
    ProjectReport,
    TaskResult,
    ProjectCheck,
    FileCheck,

    # Transport and mosaic (stable since 0.7.1)
    get_with_retry,
    make_gugik_session,
    mosaic_and_crop,
    check_source_grid,

    # Store reading without writing (Archiwista, ADR-045, ARCHITECTURE 3.3.1)
    list_segments,
    list_partitions,
    iter_store,
    StoreEntry,
    read_sidecar,
    Sidecar,
    describe_segment,
    SegmentInfo,
    file_footprint,
    Footprint,
    link_target,
    pinned_transform,
    PinnedTransform,

    # Command catalog, command layer and JSON documents (agent interface, ADR-046)
    list_commands,
    command_schema,
    CommandList,
    CommandCatalog,
    parse_command,
    validate_command,
    format_command,
    run_command,
    check_command,
    CommandCall,
    describe_sheet,
    SheetInfo,
    find_sheets,
    SheetList,
    list_sources,
    SourceList,
    list_layers,
    LayerList,
    get_cache_info,
    get_cache_path,
    clear_cache,
    CacheInfo,
    describe_store,
    StoreOverview,
    list_store_entries,
    StoreEntries,
    read_store_sidecar,
    StoreSidecar,
    ErrorReport,
    error_report,

    # Exceptions
    KartografError,
    ParseError,
    ValidationError,
    DownloadError,
    NoCoverageError,
    YearRangeError,
    CacheError,
    InvalidSidecarError,
    UsageError,

    # Version
    __version__,            # "0.8.0"
)
```

The registry of NMT/NMPT/LAZ variants (ADR-041) is a data module outside
`__all__`: `from kartograf.sources.variants import variants` (also
`ProductVariant`, `IndexRef`, `resolution_label`, `parse_resolution`).
It replaces the symbols removed in 0.8.0 (BREAKING, no aliases):
`kartograf.providers.pl.nmt_vertical_crs`, `require_nmt_vertical_crs`,
`NMT_5M_VERTICAL_CRS`, `GugikProvider.SUPPORTED_RESOLUTIONS`,
`SUPPORTED_VERTICAL_CRS`, `SUPPORTED_VERTICAL_CRS_5M`, `WMS_SKOROWIDZE_ENDPOINTS`,
`get_supported_resolutions()`, `get_supported_vertical_crs_for_resolution()`,
`GugikNmptProvider.SUPPORTED_RESOLUTIONS`, `FileStorage.SUPPORTED_RESOLUTIONS`
and `GugikLazProvider.WFS_ENDPOINTS` — what to do: `variants(product=...,
vertical_crs=..., format=...)` (labels: `v.label`, sheet index services:
`v.index_ref`). `GugikNmptProvider(session=None, *, vertical_crs,
resolution, format="ASC", cache=None)` requires `resolution`;
`GugikProvider(..., resolution=, format=)` accepts labels and formats
from the registry; `GugikProvider.is_wcs_available()` remains (WCS channel
from the registry, 1 m only).

---

## 6. Dependencies

### 6.1 Runtime Dependencies

```
Python >= 3.12
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing
numpy >= 1.24.0        # Array operations
pyshp >= 2.3.0         # Shapefile reading
pyogrio >= 0.10        # GDAL vector: GPKG of collection area results (ADR-042)
mcp >= 2.3.0, < 3      # optional extra `kartograf[mcp]`: MCP server (ADR-046)
```

### 6.2 Development Dependencies

```
pytest >= 8.0          # Testing
pytest-cov >= 5.0      # Coverage
ruff >= 0.8            # Linting + Formatting
mypy >= 1.13           # Type checking
mcp >= 2.3.0, < 3      # MCP server tests (in the `dev` extra)
```

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Requirement | Target |
|-------------|--------|
| Parse time | < 0.1s |
| NMT download | < 30s |
| Land Cover download | < 60s |
| HSG calculation | < 120s |

### 7.2 Reliability

- Success rate >= 95%
- Retry logic: `MAX_RETRIES = 3` (not configurable), backoff 2 s, then 4 s
  (`transport/http.py::backoff_delay`); only network errors, HTTP 429
  and 5xx are retried, `Retry-After` extends the pause (max `MAX_RETRY_AFTER` = 60 s); other 4xx
  end immediately (`DownloadError.status_code`)
- Timeouts per source as provider constants (e.g. `DEFAULT_TIMEOUT`); summary
  in `docs/SCOPE.md` 3.2
- Atomic writes (tmp → `os.replace`); a failed cutout rebuild leaves the
  previous file
- Skip-existing applies to sheets and other downloads; the PL WCS cutout
  never skips an existing file, it downloads on every call.
  With the default selection, sheets check for the availability of a newer campaign
- Content integrity: a GUGiK campaign file is verified by content format
  (AAIGrid header / TIFF signature); no checksums

### 7.3 Security

- Auth Proxy isolates CLMS credentials (subprocess; the main process does not see
  keys or the token)
- Credentials: the `CLMS_CREDENTIALS` variable (JSON, every system); fallback
  on macOS only: Keychain (service `clms-token`)
- No hardcoded secrets in code

---

## 8. Future Enhancements

### Done up to 0.8.0
- [x] Parallel downloads (multi-threading) (implemented in v0.6.0)
- [x] Metadata cache (SQLite) (implemented in v0.6.0)
- [x] Area cutouts from GUGiK WCS: NMT/NMPT 1 m (`download_pl_cutout`,
      0.7.2), orthophoto and true orthophoto (0.8.0); the sheet-based path from 0.7.0
      removed in 0.8.0
- [x] Czechia: DMR 5G/4G from CUZK, `--country` (0.7.0); DMP OK and DMP 1G
      (NMPT), LAZ of four models and the CZ/auto availability report (plan B,
      0.8.0); orthophoto, contours, ZABAGED, Data50, Data250, RUIAN, HY-NET,
      geomorphology, cadastral map, Geonames, ZTM, Bodove pole and
      QGZU-2013 (plans D and E, 0.8.0)
- [x] GUGiK campaigns (0.7.0; in 0.8.0 `--all-campaigns` and
      `--year`/`--min-year`/`--max-year`)
- [x] Interface for AI agents: `--json` in every command, `kartograf-*/1`
      documents, error and exit codes, command catalog, MCP server,
      `AGENTS.md`, `llms.txt`, `py.typed`, `scripts/gate.sh` (ADR-046, ADR-052, 0.8.0)

### Further tasks (no assigned release) — details in `docs/SCOPE.md` 3.1
- [ ] Country boundary polygon instead of a rectangular envelope (`--country auto`)
- [ ] Merging PL+CZ cutouts into a single cross-border surface (R6)
- [ ] Assembling campaigns into a single surface
- [ ] CZ cadastral map in VKM format (when CUZK extends the pilot)
- [ ] MCP server HTTP transport, download cancellation (KC), download size estimate (KH)

### Version 1.0.0 — roadmap (order and rules: `docs/SCOPE.md` 3.3)

Each item is a separate subproject with its own spec and ADR; the requirements below
describe the result, not the solution.

- [x] **Versioned store:** no product silently overwrites
      previously downloaded data; every version of a file remains available
      under an immutable path, and the standard path points to the latest
      local version (0.8.0, ADR-036; all products).
- [x] **Project manifest:** a project records which specific files
      and versions it used (with checksums); from the CLI one can download data
      into the project, check its integrity and find out whether the source
      has newer data. Data already present in the store is not downloaded again
      (0.8.0, ADR-040).
- [x] **Complete public GUGiK data:** all products available
      publicly and without login, as far as the services allow
      (inventory in the subproject spec). Done in 0.8.0: plans A-E
      of the GUGiK and ČÚZK catalogue (ADR-041, ADR-042, ADR-043); excluded: CZ cadastral
      map in VKM format and archival CUZK orthophoto (paid).
- [ ] **Ready-to-use data:** for each product a result fitted to the area
      of the task (cutout, mosaic, reprojection where they make sense)
      with a provenance sidecar. State in 0.8.0: NMT/NMPT 1 m cutouts,
      orthophotos and true orthophotos, collection area objects (GPKG);
      the remaining products as 1:1 source files.
- [ ] **QGIS plugin:** downloading from within QGIS through the library's
      public API, without its own download logic.
- [ ] **Web GUI:** a local data manager — a browser of the store
      and of project manifests with information about newer data; publication
      after local testing.
- [x] **English-only identifiers** in the API, CLI and sidecar (ADR-031;
      API/CLI in 0.8.0, erratum 1).

### Later (beyond v1.0.0)
- [ ] PostGIS integration
- [ ] REST API server

---

## 9. Cross-Project Integration

### 9.1 Dependency Map

```
HYDROGRAF (main application)
    ├── IMGWTools (IMGW data)
    ├── Kartograf (GIS data) ← THIS PROJECT
    └── Hydrolog (hydrological calculations)
            ├── IMGWTools (required)
            └── Kartograf (optional)
```

### 9.2 Integration Points

| Project | Uses from Kartograf |
|---------|-------------------|
| Hydrograf | DownloadManager, download_landcover |
| Hydrolog | calculate_hsg, download_soil, SoilGridsProvider |

---

**Document version:** 4.8
**Last update date:** 2026-10-18
**Status:** Release v0.8.0 (2026-10-17)
