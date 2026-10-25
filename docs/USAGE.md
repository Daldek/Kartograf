# User guide — Kartograf

How to use Kartograf from the command line and as a Python library. The document
describes user-visible behaviour; technical details and
contracts are in the canonical documents that the sections refer to:
scope and limitations — [SCOPE.md](SCOPE.md), architecture, `data/` layout
and sidecar schema — [ARCHITECTURE.md](ARCHITECTURE.md), rationale —
[DECISIONS.md](DECISIONS.md). Full list of CLI options: `kartograf <group> <command> --help`
or, machine-readable, `kartograf commands list --json` and `kartograf commands schema --command ... --json` (section 9.4);
list of the public API: `src/kartograf/__init__.py` (`__all__`).

## Table of contents

1. [CLI](#1-cli)
   - [1.1 NMT, NMPT, orthophoto, LAZ (Poland)](#11-nmt-nmpt-orthophoto-laz-poland)
   - [1.2 Area selection and country choice (`--country`)](#12-area-selection-and-country-choice---country)
   - [1.3 A single cutout (`--cutout`)](#13-a-single-cutout---cutout)
   - [1.4 Czechia (CUZK)](#14-czechia-cuzk)
   - [1.5 Land cover, soils, HSG, cache](#15-land-cover-soils-hsg-cache)
   - [1.6 When `--scale` is required](#16-when---scale-is-required)
   - [1.7 Availability report (`elevation availability`)](#17-availability-report-elevation-availability)
   - [1.8 Boundaries, cadastre, 3D building models and the BDOT10k archive](#18-boundaries-cadastre-3d-building-models-and-the-bdot10k-archive)
   - [1.9 CZ data: ZABAGED, Data50, Data250, RUIAN and HY-NET](#19-cz-data-zabaged-data50-data250-ruian-and-hy-net)
   - [1.10 Geographic names and topographic maps](#110-geographic-names-and-topographic-maps)
   - [1.11 3D mesh, trees, geodetic control networks and quasi-geoids](#111-3d-mesh-trees-geodetic-control-networks-and-quasi-geoids)
   - [1.12 Plain files or the store (`--output-dir`, `--root`)](#112-plain-files-or-the-store---output-dir---root)
2. [Python library](#2-python-library)
3. [Download result](#3-download-result)
4. [GUGiK campaigns](#4-gugik-campaigns)
   - [4.1 Choosing the data year (`--year`, `--min-year`, `--max-year`)](#41-choosing-the-data-year---year---min-year---max-year)
   - [4.2 Latest full flight (`full_sheet/`, `--full-sheet`)](#42-latest-full-flight-full_sheet---full-sheet)
   - [4.3 Versions, modes and update plan (`--check`, `--upgrade`, `--force`)](#43-versions-modes-and-update-plan---check---upgrade---force)
5. [Soils and HSG](#5-soils-and-hsg)
6. [CLMS API configuration (CORINE GeoTIFF)](#6-clms-api-configuration-corine-geotiff)
7. [Known issues and limitations](#7-known-issues-and-limitations)
8. [Project](#8-project)
   - [8.1 First download and check](#81-first-download-and-check)
   - [8.2 Freshness and data variant](#82-freshness-and-data-variant)
   - [8.3 Moving the project and store](#83-moving-the-project-and-store)
   - [8.4 Python library](#84-python-library)
9. [Interface for agents](#9-interface-for-agents)
   - [9.1 JSON documents and commands](#91-json-documents-and-commands)
   - [9.2 The `--json` contract](#92-the---json-contract)
   - [9.3 Exit codes and error codes](#93-exit-codes-and-error-codes)
   - [9.4 Command catalog](#94-command-catalog)
   - [9.5 Command layer](#95-command-layer)
   - [9.6 MCP server](#96-mcp-server)
   - [9.7 Files for agents](#97-files-for-agents)
10. [Settings and directories](#10-settings-and-directories)

Commands are grouped by data type (`kartograf <group> <command>`, ADR-039):

| Group | Commands | Data |
|---|---|---|
| `elevation` | `download`, `list-sources`, `availability` | NMT (`nmt`), NMPT (`nmpt`) and LAZ point clouds (`laz`) — PL, CZ; ZABAGED contours (`contours`, CZ); availability report for PL, CZ and `auto` |
| `imagery` | `download`, `list-sources` | orthophoto (`orto`): PL (GUGiK) and CZ (CUZK, SM5) sheets, PL WCS cutout (`--cutout`); PL: LIDAR intensity images (`intensity`), true orthophoto (`true-orto`) and oblique orthophoto (`oblique-orto`) of selected cities |
| `landcover` | `download`, `list-sources`, `list-layers` | BDOT10k (also the archive of yearly editions `--year`), BDOO (PL), CORINE, ZABAGED, Data50 and Data250 (CZ) (`--product`) |
| `soil` | `download`, `hsg`, `list-sources`, `list-layers` | SoilGrids, HSG |
| `boundaries` | `download`, `list-sources` | unit boundaries (`admin`): PRG (PL), RUIAN (CZ); address points and streets (`addresses`) and special boundaries (`special`) from PRG (PL); geomorphological units (`geomorphology`, CZ) |
| `cadastre` | `download`, `list-sources` | cadastral map (`map`): EGiB — parcels and buildings (PL), cadastral map (CZ, `--ku`); RCN real estate prices (`prices`, PL) |
| `models3d` | `download`, `list-sources` | 3D models (PL): CityGML LoD1/LoD2 buildings (`buildings`), CityGML trees (`trees`), OBJ city 3D mesh (`mesh`) |
| `hydro` | `download`, `list-sources` | HY-NET water network (`network`, CZ) |
| `names` | `download`, `list-sources` | geographic names (`geographic`): PRNG RP (PL), Geonames (CZ); Polish names of the world (`world`, PL) |
| `maps` | `download`, `list-sources` | topographic maps (`topographic`): BDOT10k visualisations (PL), ZTM (CZ) |
| `geodesy` | `download`, `list-sources` | geodetic control networks (`control`): PL (GUGiK) and CZ (Bodove pole); quasi-geoids (`geoid`): PL-geoid2021 and QGZU-2013 |
| `project` | `init`, `add`, `remove`, `download`, `status`, `verify` | project manifest and pinned versions from the store |
| `store` | `overview`, `entries`, `sidecar` | store reads (no network, no writes): segments, entries with sidecars, the sidecar of one file |

Outside the data groups there are `kartograf sheet parse` and `kartograf sheet find` (group `sheet`), `kartograf cache`, `kartograf config` (settings, section 10)
and `kartograf commands list`, `kartograf commands schema` and `kartograf commands guide` (group `commands`: the command catalog and the guide for agents, sections 9.4 and 9.7). `kartograf <group>
--help` prints the group's commands, `<group> <command> --help` — options and command
examples, `list-sources` — the group's sources from the registry (no network): `WYBOR` (the complete
set of required source-selection flags; `a|b` = one of the values), `KRAJ`, `DOSTAWCA`,
`KATALOG` (the directory of files under `--root`, e.g. `boundaries/pl_prg`) and `KLUCZ`
(the `dataset` field of the sidecar). The former `kartograf download`, `kartograf soilgrids` and
`landcover --source soilgrids` do not work: they end with an error (code 2)
naming the new command (table: CHANGELOG 0.8.0). `landcover` selects data
through `--product`, like every group; the former `--source`/`-s` ends with an error
with a hint pointing to `--product`.

Since 0.8.0 the CLI has no default values that affect the data: `--product`,
`--country` (with `--bbox`/`--geometry`),
`--vertical-crs` (digital terrain model (NMT), digital surface model (NMPT), LAZ), `--model` (LAZ CZ), `--resolution` (NMT
and NMPT, where there is a choice; orthophoto cutout pixel), `--sheet-system` (PL
`--bbox`/`--geometry` without `--cutout`; ZTM CZ area in `maps`),
`--horizontal-crs` (with `--cutout`; national files ZABAGED, Data50, Data250
and Geonames), `--coverage` (orthophoto cutout), `--scale` (PL-2000,
`maps`), `--level` (`boundaries` area; under `auto` per country), `--lod`
and `--year` (`models3d`, when there are several releases; BDOO and CORINE year),
`--network` (`geodesy --product control`), `--property`, `--depth`
and `--stat` (`soil download`; `soil hsg` — `--depth`) and `--format`
(CZ contours, `maps`, national `names` files, PRG address points and special
boundaries, CZ cadastral map, BDOT10k archive with `--year`) are given
explicitly. A missing value gives an `Error:` with the list of permitted values
(code 2, before the network; exit codes: section 9.3); the lists and meanings of values are also given by `kartograf
<group> <command> --help`. Only the format of NMT and NMPT
(ASC grid; the GUGiK archive selects `--format`) and of current BDOT10k
(GPKG), the `--bbox-crs EPSG:2180` CRS, switches and technical parameters
(`--workers`) remain default.

**The store without `--root`.** `--root` names the store (`<root>/<product>/<variant>/versions/...`);
a command given none works on the default store, the first of `KARTOGRAF_ROOT`, `[kartograf] root`
of `nogat.toml` and `<data_dir>/kartograf` (`data_dir`: `KARTOGRAF_DATA_DIR`, `NOGAT_DATA_DIR`,
`[kartograf] data_dir`, `[nogat] data_dir`, else the user data directory of `nogat`;
`kartograf config show` names the root and where it comes from). The same holds for the library
(`root=None`), for `store overview` and `store entries`, and for `project init`, which writes the
default root, as an absolute path, into the manifest. The MCP server accepts a call without `root`
only when the default store lies inside `--allow-dir` (`forbidden` otherwise). Nothing is written
into the current directory.

---

## 1. CLI

### 1.1 NMT, NMPT, orthophoto, LAZ (Poland)

```bash
# Sheet information (auto-detection of PL-1992 / PL-2000); --hierarchy shows the hierarchy
kartograf sheet parse N-34-130-D-d-2-4
kartograf sheet parse N-34-130-D --hierarchy

# NMT: single sheet or hierarchy; a PL-1992 sheet code coarser
# than 1:10000 expands to 1:10000 sheets on its own — without --scale (section 1.6)
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-130-D --resolution 5m --workers 8 --root ./data --product nmt --vertical-crs EVRF2007
kartograf elevation download --sheet N-33-58-A-c-1-3 --product nmt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
# Resolutions and vertical CRSs come from the variant registry (below);
# a combination outside the registry, e.g. --resolution 5m with --vertical-crs KRON86,
# ends with Error: (code 2, before any network access) with a list of available values

# NMPT (DSM) — --resolution required (since 0.8.0)
kartograf elevation download --sheet M-34-64-D-d-2-1 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmpt --resolution 1m --vertical-crs EVRF2007 --root ./data

# GUGiK archive as a source file (--format; no conversion): NMT TBD 25 m KRON86
kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010 --root ./data

# Other GUGiK products: orthophoto, LAZ point clouds
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 637400,487000,637450,487050 --product laz --min-density 12 --vertical-crs EVRF2007 --country pl --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86 --country pl --root ./data

# PL-2000: sheet code or bbox in the zone CRS; a coarser sheet code and bbox require --scale
# matching the GUGiK sheets (section 1.6)
kartograf sheet parse 6.179.12.20
kartograf elevation download --sheet 6.179.12.20 --product nmt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --root ./data

# GUGiK campaigns (section 4): the latest by default; `--all-campaigns`
# downloads all campaigns of the sheet
kartograf elevation download --sheet N-34-130-D-d-2-4 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # + latest full flight in full_sheet/ (section 4.2)
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --all-campaigns --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --all-campaigns --country pl --vertical-crs EVRF2007 --root ./data

# Choosing the data year (NMT, NMPT, orto, LAZ; section 4.1)
kartograf elevation download --sheet N-34-130-D-d-2-4 --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # latest flight from 2025
kartograf elevation download --sheet N-34-130-D-d-2-4 --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # all flights from 2025
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto --year 2024 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --min-year 2022 --max-year 2024 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # latest, not older than 2024
kartograf elevation download --bbox 530000,382000,533000,386000 --all-campaigns --min-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
```

Full list of commands and options: `kartograf --help`, `kartograf <group> <command> --help`.
Which years, resolutions and formats an area has: `kartograf elevation
availability` (section 1.7).

**NMT and NMPT variants (registry, since 0.8.0).** The resolution, vertical
CRS and format of a PL sheet are selected by a single variant registry — the same
one for CLI and library validation, `--help`, `kartograf elevation
list-sources` (the `WYBOR` column gives ready-made flags for each variant),
the store segment and the choice of the sheet index (Polish skorowidz) record
([ADR-041](DECISIONS.md); library: `kartograf.sources.variants.variants()`).
ASC grids (without `--format`; the product format):

| Product | EVRF2007 | KRON86 |
|---|---|---|
| NMT | `0.15m`, `0.5m`, `0.6m`, `1m`, `5m`, `10m` | `0.5m`, `1m` |
| NMPT | `0.5m`, `0.6m`, `1m` | `0.5m`, `1m` |

- `--resolution` accepts only the exact labels from the registry: `0,5m`
  or `50cm` gives `Error: PL nie ma rozdzielczosci 0,5m dla NMT - dostepne:
  EVRF2007: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; KRON86: 0.5m, 1m; uklad
  wysokosci nieznany: 100m`. The label is a segment component:
  `nmt/pl_1992_0.5m_evrf2007/`.
- `--product nmpt` requires `--resolution` (up to 0.7.x NMPT was only
  1 m): without the flag `Error: --resolution wymagane dla NMPT PL: EVRF2007:
  0.5m, 0.6m, 1m; KRON86: 0.5m, 1m` (code 2, before the network) — update existing
  invocations by adding `--resolution 1m`. Exception: the `--cutout` cutout
  (1 m only, section 1.3) accepts a missing `--resolution`.
- The GUGiK sheet index also publishes the same sheet as an archive (e.g.
  `.asc` and `.xyz.zip` of the same report); without `--format` Kartograf
  takes only the ASC grid record (record format and URL ending
  `.asc`; exception: 42 NMT 2019 grids of campaign 72675 are named `.xyz`,
  with AAIGrid inside — saved as `.asc`), never the archive.

**GUGiK archives (`--format`).** The remaining formats of the NMT/NMPT sheet index
(published until 2020) are register variants downloaded as **source
files 1:1**: `XYZ` (ASCII XYZ GRID, ZIP), `ASCII-NMT` (X Y Z points,
ZIP), `TBD` (structure points and lines, ZIP), `TIN` (ESRI TIN, ZIP),
`TTN` (Intergraph TTN), `GRD` (Intergraph GRD), `DXF` and `DGN`
(contours); NMPT has `XYZ` archives at 0.5m and 1m in KRON86. Resolutions
and vertical CRSs of the archives (e.g. TBD 1–25 m in both systems, 30–50 m
KRON86 only): `kartograf elevation list-sources`. 8-part PL-1992 sheet codes (Polish godła)
(quarters of a 7-part sheet, e.g. `N-34-50-A-c-3-2-3`, scale label
`1:5000`; among others `ASCII-NMT` 10 m sheets and some ASC 1 m sheets) are passed
in `--sheet` like any sheet code (since 0.8.0, ADR-043 D10).

- The file goes to the store like a grid sheet (versions in `versions/`,
  sidecar, campaigns, `full_sheet/`), without conversion, cutout or mosaic;
  the segment carries the format token: `nmt/pl_1992_tbd_25m_kron86/`. Kartograf does not
  open the file — that is the task of the program that handles the format
  (section 7).
- Archive sheets have different scales (among others 1:25000 and 1:10000, PL-2000),
  so they are determined by the sheet index: variant records from the year range whose
  frame intersects the task area (`--sheet` = sheet frame, `--bbox`,
  envelopes of `--geometry` features); a sheet touching the area
  only along an edge does not count. No such records gives `Error:
  Skorowidz GUGiK nie ma plikow ... - dostepne dane obszaru: kartograf
  elevation availability`.
- `--scale` and `--cutout` with an archive end with `Error:` before the network;
  `--sheet-system` is required as for grids. A variant with a single
  value does not require `--resolution` (`TIN`, `TTN` — no resolution;
  `GRD` — only `5m`).
- The content is checked only for format (complete ZIP, TTN
  signature, Intergraph header, DXF sections); archive coverage is not measured.

**NMT 100 m (since 0.8.0).** `--resolution 100m` means voivodeship (Polish województwo) files from the
GUGiK ATOM feed (ZIP with a single XYZ file, 2019 release), not sheets:

```bash
# Kraków: voivodeship 12 file (ZIP 7.6 MB); an area on a voivodeship border yields two files
kartograf elevation download --product nmt --resolution 100m --country pl --bbox 564000,241000,570000,247000 --bbox-crs EPSG:2180 --root ./data
#   Info: nmt: wojewodztwa obszaru wg PRG (1): 12 (malopolskie)
#   -> nmt/pl_1992_100m/teryt/12.zip (ZIP 1:1, wersja 2019-05-14 = data wpisu feedu)
```

- The vertical CRS is **unknown** (GUGiK does not declare it): the sidecar has
  `vertical_crs: null` and `extra.vertical_crs_note`; `--vertical-crs` gives
  `Error:`. `--format XYZ` can be omitted.
- Without sheets, flights and cutout: `--sheet-system`, `--scale`, year flags,
  `--all-campaigns`, `--full-sheet`, `--cutout`, `--horizontal-crs`,
  `--min-density` and `--country cz` give `Error: ... NMT 100 m to pliki
  wojewodztw z ATOM - bez arkuszy, lotow i wycinka`. `--check`
  reads only the feeds.

**Intensity images, true orthophoto and oblique orthophoto (since 0.8.0).** GUGiK
sheets like the orthophoto (campaigns, `--year`, `--all-campaigns`, sheet index
signal), GeoTIFF 1:1. A file over 100 MiB is announced before
download (`Warning: ... duzy plik <URL> - 296853152 B (ok. 297 MB)`).

```bash
# LIDAR intensity images: 1 band, 0.25 m pixel; PL-1992 and PL-2000 sheets
kartograf imagery download --product intensity --sheet M-34-64-D-d-1-4 --root ./data
#   -> intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif
# true orthophoto of selected cities (e.g. Gdańsk): 8-part PL-1992 sheet codes, RGB 0.05 m (approx. 300 MB)
kartograf imagery download --product true-orto --sheet N-34-50-A-c-3-2-3 --root ./data
#   -> true-orto/pl_1992/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif
# true orthophoto cutout from WCS: pixel 0.05m-1m, EPSG:2180 only, without --coverage
kartograf imagery download --product true-orto --country pl --bbox 470100,740100,470200,740200 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m --root ./data
#   -> true-orto/pl_1992_0.05m/bbox/470100_740100_470200_740200.tif
# oblique orthophoto (Kraków, Gdańsk): sheet = 4 direction files; --direction selects one part
kartograf imagery download --product oblique-orto --sheet 7.125.11.08 --direction n --root ./data
#   -> oblique-orto/pl_2000/7/125/11/08/7.125.11.08_n.tif (bez flagi także _e, _s, _w)
```

- A product with a single sheet system (true orthophoto: 1992, oblique orthophoto: 2000)
  may omit `--sheet-system`; the oblique orthophoto has 1:2000 and 1:1000 sheets,
  so an area requires `--scale`. `--full-sheet` only for the oblique orthophoto
  (intensity and true orthophoto records do not declare a full sheet).
- The true orthophoto covers only selected cities (e.g. Gdańsk; a sheet without a record,
  e.g. Kraków, gives `Error:` with a hint). A cutout outside them: WCS returns
  an entirely 0,0,0 image, so Kartograf ends with `Error: wycinek true orto:
  WCS GUGiK nie ma w tym obszarze prawdziwej ortofotomapy ...` (exit code 11) without a
  version in the store; the service does not publish the cutout extent, so the image is
  downloaded and checked before saving.
- Result lines and `--check` of a unit with several files give the file
  name (`7.125.11.08_e.tif: do pobrania ...`).
- Under `--country auto` a single-country product narrows the area to that country
  (`Info: --country auto -> pl (--product intensity tylko dla PL)`).

LAZ: by default the newest tile is downloaded for each part of the area;
older tiles covered by newer ones are skipped with an `Info:` notice
([ADR-029](DECISIONS.md), details: SCOPE 2.5 and ARCHITECTURE 4.7 "Wybór
kafli"); `--year`/`--min-year`/`--max-year` narrow the selection to a range of years
(section 4.1; a year outside the service = an error with a list of available ones). GUGiK WFS
in EPSG:2180 uses the axis order (N,E). The `--sheet` area is the sheet frame
(in EPSG:2180 a rotated quadrilateral), not its envelope: a tile must reach
into the area deeper than 1 m, so a neighbouring sheet touching the frame
along an edge or a corner is not downloaded (`--sheet N-34-130-D-d-2-4`
= 4 tiles 1:5000). The same for `--bbox`: a tile reaching into it by millimetres
(rounding of GUGiK frames to 1 cm) is skipped.
`--min-density` and `extra.nominal_density` are the **nominal** density from the GUGiK
WFS — the actual one can be higher.
When `--min-density` rejects all tiles of the area, the error points to them (exit code 14):
`Error: Brak kafli LAZ dla podanego obszaru: --min-density 12 odrzucilo 13 kafli
obszaru (najwyzsza gestosc nominalna 4 pkt/m2) - obniz albo pomin --min-density`
(tiles of sheet `N-34-130-D-d-2-4` have 4 pts/m2; with 12 pts/m2 this is, among others, the
Warsaw area from the example above).

`--min-density` works **only with `--product laz`**. With `nmt`, `nmpt` and `orto`
it ends with `Error:` and code 2 before any
network request (until 0.7.0 it was silently ignored). `--year`, `--min-year`
and `--max-year` work for NMT, NMPT, orthophoto and LAZ (since 0.7.2; earlier
`--year` outside LAZ ended with `Error:`) — PL only, without `--cutout`
(section 4.1).

### 1.2 Area selection and country choice (`--country`)

```bash
kartograf imagery download --bbox 771000,509000,772000,510000 --product orto --country pl --sheet-system 1992 --root ./data
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --geometry zlewnia.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
```

- The default `--bbox-crs` is `EPSG:2180`; the geometry file is SHP or GPKG.
  `--layer` selects a GPKG layer. Without this flag a GPKG with several layers
  uses the first; the library emits one `Notice`
  `geometry_layer_default` with the selected layer, the list of the others
  and the hint `--layer NAZWA` (CLI: `Info:`, also with `-q`).
  This also applies to `landcover download`, `soil download` and `soil hsg`
  (`download_landcover`, `download_soil`, `calculate_hsg`).
  The low-level `kartograf.core.geometry` functions
  (e.g. `find_sheets_for_geometry`) called without `layer=` log
  a warning (`logger.warning`) — pass `layer=` to specify the layer explicitly.
- PL without `--cutout` saves a **list of sheets** in the sheet code hierarchy;
  a sheet without GUGiK data is skipped with `Warning:` (code 0 when at least
  one sheet was downloaded).
- **Point or line in `--geometry` (since 0.8.0):** an envelope with zero
  area (a point, a line parallel to an axis) selects the sheets, units
  and pixels in which it lies — NMT/orthophoto sheets, `boundaries`, `soil
  download`, `landcover` BDOT10k accept it (`--bbox x,y,x,y` does not, see
  below). Cutout (`--cutout`, PL and CZ), LAZ tiles, `soil hsg`
  and `elevation availability` work on an area and end with `Error:
  --geometry: obwiednia obiektow ma zerowa powierzchnie ...` (code 2,
  `details.option=geometry`) before the network, also in `project add`; pass
  a polygon or a `--bbox` with positive area.
- `--country` is required with `--bbox`/`--geometry` (`pl`, `cz` or
  `auto`; with `--sheet` the country follows from the sheet code). Under `auto` countries
  are recognised by **rectangular** envelopes, not by the border: an area
  crossing the CZ envelope (west of 18.86°E and south of
  51.06°N) also goes to CUZK, and the PL rectangle (14.07–24.20°E,
  49.00–54.90°N) covers most of Czechia. For pure Poland use
  `--country pl`.
- Values with no Czech equivalent (`--vertical-crs KRON86`,
  a resolution that CUZK does not have, e.g.
  `--resolution 1m` or `0.5m` for NMT (NMPT `0.5m` has an equivalent
  DMP OK), `--format` — in the plain, not per-country form — and
  `--coverage` and `--resolution` of an orthophoto cutout) on an area covered by
  the envelopes of both countries switch `auto` to PL by themselves (an
  `Info:` notice); for LAZ also `--year`, `--min-year`, `--max-year`,
  `--all-campaigns` and `--min-density`. In Prague or Brno
  such a flag therefore directs the task to GUGiK, which has no data there (a download
  error); an error before the network is given only to an area outside the PL rectangle.
  LAZ on an area reaching CZ without these flags downloads the files of both countries
  and requires `--model` (section 1.4); without it, `Error:` with the hint
  `--country pl`. `--sheet-system`
  is required for the PL part of the task (without `--cutout`), so it does not choose
  the country. The orthophoto has a CZ source since 0.8.0, so `--product orto`
  alone no longer switches `auto` to PL (section 1.4).
- An NMT/NMPT raster from an area reaching CZ (`--country cz` or `auto`
  with a CZ part) requires `--cutout --horizontal-crs <crs>`: CUZK has no
  raster sheet mode for an area ([ADR-038](DECISIONS.md)). Under `auto`
  the PL part is then also a WCS cutout (1 m only, NMT/NMPT, no campaign
  choice); PL sheets from such an area are downloaded with `--country pl`. Without
  `--cutout` — `Error:` before the network with this hint. CZ LAZ has no
  cutout: the area selects sheets from the CUZK index (section 1.4).
  The orthophoto of a CZ area is SM5 sheets (without `--cutout`, section 1.4),
  and boundaries and the water network — one area file per country (section 1.9).
- Under `auto` clipping to the country envelope is reported as `Info:`;
  the original bbox is kept in `extra.parent_request`, the whole bbox is downloaded by
  `--country pl`.
- Full rules (clipping, exit codes, partial success): SCOPE 3.2,
  ARCHITECTURE 4.6, ADR-023.

### 1.3 A single cutout (`--cutout`)

`--cutout` switches `--bbox`/`--geometry` from a list of sheets to **one**
GeoTIFF of the area; the result CRS is given by the required `--horizontal-crs`
(`EPSG:2180`, `EPSG:5514`, `EPSG:3045`; orthophoto — only `EPSG:2180`,
below). `--horizontal-crs` without
`--cutout` and `--cutout` with `--sheet` give `Error:` before the network.

```bash
# NMT 1 m, WCS cutout in the source CRS or after local reprojection
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:2180 --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:5514 --vertical-crs EVRF2007 --root ./data
# NMPT 1 m, both vertical CRSs (here KRON86); --resolution can be omitted (the cutout is 1 m only)
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmpt --vertical-crs KRON86 --cutout --horizontal-crs EPSG:2180 --root ./data
# border area: separate PL + CZ cutouts, same CRS and parent_request
# (the PL cutout is 1 m only, the CZ part requires 2m or 5m — values per country)
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:2180 --product nmt --resolution pl=1m,cz=2m --vertical-crs EVRF2007 --root ./data
# NMT 5 m (and any resolution other than 1 m): OpenData sheets, without --cutout
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 5m --vertical-crs EVRF2007 --sheet-system 1992 --root ./data
```

- PL: WCS GUGiK provides NMT/NMPT 1 m heights in a single GeoTIFF
  `<segment>/bbox/<coords>.tif`. Before the WCS request,
  the PRG land mask (`A00 - W02 - W03`) is downloaded: sea
  and the area outside Poland are nodata `-9999`, **0.0 on land remains
  data**. A result that is entirely nodata gives `Warning:` and code 0. On the
  coast (measurement 2026-10-11: Gdynia, Hel, Mierzeja Wiślana) water with a WCS height of approx. 0–0.3 m remains outside the
  mask; the PRG line does not cut off
  land higher than 5 m, but a narrow strip of shore and quays (up to approx. 2 m)
  may end up as nodata, while a low beach on the land side remains.
- The range is expanded outwards to the 1 m sheet grid
  EPSG:2180 (edges `k + 0.5` m), then for other CRS
  locally reprojected with a pinned operation. WCS shows
  the server composition (the latest flight of the area without filling in with
  older ones); a cutout may show a different flight than the downloaded
  sheets of exactly 1 m. Over a 0.5 m flight the 1 m result is
  decimation, not averaging.
- The result is a hard link `<segment>/bbox/<coords>.tif` (without a date) to a
  version in `<segment>/versions/bbox/<YYYY-MM-DD>_<sha8>/`. By default
  and with `--upgrade` the existing version is used without PRG and WCS requests
  (line `... lokalna wersja ... (bez sprawdzania; --check)`);
  `--force` downloads again — the same content is "unchanged" (cutouts are
  byte-reproducible, measurement 2026-10-12), a different one is a new version next to the
  old one. A failed download does not touch the previous version or the hard link.
  Files `<coords>_<YYYYMMDD>.tif` from 0.7.x are not recognised (delete
  them manually). `--workers` and `--scale` do not change the WCS cutout.
  `Info:` gives the number of requests and the estimated time for more than one
  piece or a result >= 1 GiB (only when the cutout will be downloaded):
  WCS GUGiK returns a piece of approx. 1 Mpx in 25–40 s (measurement 2026-10-16/17,
  with retries), e.g. 16 requests = approx. 7–11 min.
- An area entirely outside PL land (PRG mask: sea, abroad) ends with
  `Error: wycinek NMT: obszar w calosci poza ladem PL ...` (exit code 11) before the
  first WCS request, with no version in the store — like the sheet mode
  (`GUGiK nie ma danych ...`). A file of pure nodata (`Warning: wycinek
  w calosci nodata ...`) remains only when WCS returns no data
  for an area on land.
- An NMT/NMPT cutout is **1 m only** from the ASC grid: `--resolution 1m` or without
  `--resolution`. Another resolution ends before any network access (code 2)
  with the message `Error: wycinki PL (--cutout) sa tylko 1 m (WCS GUGiK);
  arkusze 0.5m: pomin --cutout (arkusze bez --cutout); wycinek:
  --resolution 1m albo pomin --resolution`, and the archive (`--format`, section
  1.1) — `Error: --cutout dziala tylko z siatka ASC 1m (wycinek z WCS
  GUGiK); --format TBD to pliki zrodlowe arkuszy - pomin --cutout`.
- The choice of year (`--year`, `--min-year`, `--max-year`),
  `--all-campaigns` and `--full-sheet` with `--cutout` are
  rejected (`Error:`). Likewise `--cutout` for LAZ (the orthophoto has its
  own cutout — below); download sheets of other resolutions without
  `--cutout`. Details:
  [ADR-035](DECISIONS.md), [ADR-038](DECISIONS.md), ARCHITECTURE 4.3.

**Orthophoto cutout (`imagery download --cutout`, since 0.8.0).** A single
RGB GeoTIFF of a PL area from WCS GUGiK. Three choices are required, with no default
values: `--horizontal-crs EPSG:2180` (the image is not
resampled locally, there is no other CRS), `--coverage` (the service
variant) and `--resolution` (result pixel: `0.1m`, `0.25m`, `0.5m`, `1m`).

```bash
# Standard, 0.25 m pixel: 500 x 500 m = 2000 x 2000 px, 9 WCS requests
kartograf imagery download --product orto --country pl --bbox 566000,243000,566500,243500 --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m --root ./data
#   Info: wycinek 2000 x 2000 px RGB uint8 (~11 MiB), 9 zapytan WCS GUGiK (standard 0.25m) pobieranych po kolei
#   -> orto/pl_1992_standard_0.25m/bbox/566000_243000_566500_243500.tif
# High (10 cm pixel and smaller), 0.1 m pixel: 200 x 200 m = a single request
kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m --root ./data
#   -> orto/pl_1992_high_0.1m/bbox/566000_243000_566200_243200.tif
# Again: local version without requests; --force downloads (same content = no change)
kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m --root ./data --force
```

- **`standard` or `high`.** `standard` (`Orthoimagery_StandardResolution`)
  is the latest available orthophoto of the area — a server composition of flights
  with different pixel sizes (e.g. 25 cm and 10 cm); `high`
  (`Orthoimagery_High_Resolution`) contains only orthophotos with a pixel of
  10 cm or smaller. Outside the 10 cm flight areas `high` responds with an entirely
  black image (0,0,0, HTTP 200): Kartograf ends with `Error: wycinek
  ortofotomapy high: WCS GUGiK nie ma w tym obszarze ortofotomapy o pikselu
  10 cm i mniejszym, a obraz obszaru jest w calosci 0,0,0; wersja nie
  powstala, zmien --bbox albo uzyj --coverage standard` (exit code 11, `NoCoverageError` in the API)
  with no version in the store — use `standard` there. A `standard` cutout that is entirely black
  ends the same way, as does true orthophoto outside the cities of the
  service: the service does not publish the extent of the cutout, so the image is downloaded
  and checked before the version is saved. In samples (Kraków, 2026-10-15/16) both
  variants gave the same bytes over the same area.
  There is no choice of year or flight (`--year`, `--min-year`, `--max-year`,
  `--all-campaigns`, `--full-sheet` with `--cutout` = `Error:`); there is no PRG land mask
  either — pixels without imagery in a cutout that has an image remain 0,0,0.
- **Pixel and grid.** Both services have a national 0.1 m grid; a different result
  pixel is computed by the server from `SCALEFACTOR` (e.g. 0.4 for 0.25 m). The area is
  expanded outwards to a multiple of the pixel, and the file name carries
  this grid (EPSG:2180). The result is checked (size, pixel, NW
  corner, 3 uint8 bands, EPSG:2180): a response on a different grid is an `Error:` with no
  new version.
- **Time.** The orthophoto WCS is slow: a single request covers
  at most 200 x 200 m of terrain (4 Mpx of 0.1 m pixels) regardless of the result
  pixel, so a 1 x 1 km area is 25 requests even with `1m`.
  Measurement 2026-10-15: 200 x 200 m at 0.1 m (Standard) — 64 s, 100 x 100 m
  — 17 s (High 29 s); a 1 x 1 km area is therefore on the order of half an hour.
  Kartograf waits up to 300 s for each piece, downloads pieces one after another
  and before the first request prints `Info:` with the number of requests; it also checks
  free disk space (2 x the result size). The Standard service is sometimes
  temporarily unavailable (measurement 2026-10-15 morning: timeouts).
- **Assembling pieces.** A cutout made of several requests is NOT bit-for-bit equal to
  a single request for the whole area: the server resamples each request
  within its own extent (measurement 2026-10-16: 75–93 % of pixels differ, on average
  by 4 DN, max 89–120). The same task repeated gives the same bytes
  (`--force` = `bez zmian`), but two different areas may have pixels in their common
  part that differ by a few DN. NMT is assembled bit for bit
  ([ADR-034](DECISIONS.md), erratum 1).
- **Country.** PL only: `--country cz` (or an `auto` area entirely in CZ)
  with `--cutout` gives `Error: --cutout z --product orto dziala tylko dla PL
  ...`; under `auto` an area near the border is narrowed to PL (`Info: --country
  auto -> pl (--resolution 0.25m, --coverage standard dotyczy tylko PL)`).
  `--coverage` and `--resolution` without `--cutout` give `Error:` (orthophoto
  sheets have the source pixel). A cutout is in the version store
  (`orto/pl_1992_<coverage>_<res>/bbox/`); `--check` reports
  `nie da sie sprawdzic bez pobrania`, newer content is obtained with `--force`.
  Details: ARCHITECTURE 4.3, [ADR-042](DECISIONS.md) D14 (erratum 5).

### 1.4 Czechia (CUZK)

CZ has NMT rasters, and since 0.8.0 also NMPT and LAZ point clouds. The raster
model is chosen by `--product` and `--resolution`, the LAZ model by
`--model`; the route (a ready `openzu` file or the ImageServer service) is determined by the
variant and the sheet code ([ADR-041](DECISIONS.md); variants with ready-made flags:
`kartograf elevation list-sources`, column `WYBOR`):

| Product | Model (flags) | SM5 sheet (e.g. `CTES96`) | TM33 tile (e.g. `760_5518`) | Area (`--bbox`/`--geometry`) |
|---|---|---|---|---|
| `nmt` | DMR 4G (`--resolution 5m`) | TIFF file EPSG:5514, Bpv; EVRF2007 with a pinned transformation | EVRF2007: TIFF file EPSG:3045 (native); Bpv: `exportImage` + local warp | `exportImage` cutout (`--cutout`) |
| `nmt` | DMR 5G (`--resolution 2m`) | none (`Error:`) | `exportImage` + local warp | `exportImage` cutout (`--cutout`) |
| `nmpt` | DMP OK (`--resolution 0.5m`) | as DMR 4G | as DMR 4G | `exportImage` cutout (`--cutout`) |
| `nmpt` | DMP 1G (`--resolution 2m`) | none (`Error:`) | `exportImage` + local warp | `exportImage` cutout (`--cutout`) |
| `laz` | `--model dmr5g`, `dmr4g`, `dmp1g`, `dmpok` | `.laz` EPSG:5514, only `--vertical-crs Bpv` | `.laz` EPSG:3045, only `--vertical-crs EVRF2007` | sheets from the CUZK index (Bpv: SM5, EVRF2007: TM33), without `--cutout` |

```bash
# DMR 5G (2 m), sheet code TM33 (this tile lies mostly in Germany — mainly nodata)
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv --root ./data
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv --root ./data # DMR 4G (5 m), sheet SM5, country from the sheet code
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m --root ./data # Bpv -> EVRF2007 (EPSG:5621)
# DMR 4G, tile TM33 in EVRF2007: ready-made ETRS89 file (EPSG:3045), no transformation
kartograf elevation download --sheet 760_5518 --product nmt --resolution 5m --vertical-crs EVRF2007 --root ./data
# NMPT DMP OK (0.5 m): sheet SM5 (Bpv) and tile TM33 (EVRF2007) from CUZK files
kartograf elevation download --sheet CTES96 --product nmpt --resolution 0.5m --vertical-crs Bpv --root ./data
kartograf elevation download --sheet 760_5518 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 --root ./data
# NMPT DMP 1G (2 m): tile TM33 from the service (warp)
kartograf elevation download --sheet 760_5518 --product nmpt --resolution 2m --vertical-crs Bpv --root ./data
# CZ area = one cutout (--cutout); reprojection (only --bbox/--geometry,
# not the sheet code) via a locally pinned operation
kartograf elevation download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv --root ./data
# border area under auto: separate PL (WCS 1 m) and CZ cutouts, shared
# extra.parent_request; different values per country as pl=...,cz=...
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv --root ./data
# bboxes in EPSG:5514 are negative on CZ territory — since 0.8.0 --bbox -447000,... and --bbox=-447000,... both work;
kartograf elevation download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 5m --product nmt --vertical-crs Bpv --root ./data
kartograf elevation download "--bbox=-447000,-1114000,-446600,-1113600" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 2m --product nmpt --vertical-crs Bpv --root ./data # DMP 1G cutout
# LAZ CZ: --model selects the model, --vertical-crs the files (Bpv = SM5 sheets, EVRF2007 = TM33 tiles)
kartograf elevation download --sheet CTES96 --product laz --model dmr5g --vertical-crs Bpv --root ./data
kartograf elevation download --sheet 760_5518 --product laz --model dmpok --vertical-crs EVRF2007 --root ./data
kartograf elevation download "--bbox=-447000,-1114000,-444000,-1113000" --bbox-crs EPSG:5514 --country cz --product laz --model dmr4g --vertical-crs Bpv --root ./data
# border area under auto: PL LAZ tiles (WFS GUGiK) and CZ sheets, shared extra.parent_request
kartograf elevation download --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326 --country auto --product laz --model dmr4g --vertical-crs pl=EVRF2007,cz=Bpv --root ./data
```

`kartograf sheet parse` recognises PL sheet codes (PL-1992/PL-2000: scale, segments,
hierarchy) and CZ ones without network access: SM5 sheet (`CTES96`), TM33 tile (`302_5550`,
with extent in EPSG:3045) and ZTM sheet (`0510-D-11`, `NM-34-07-1-D-15`) — the system,
CRS and commands that accept a sheet code in `--sheet`; `--hierarchy`,
`--children` and `--descendants` apply only to PL sheet codes. CZ sheet codes (TM33, SM5)
are accepted by `kartograf elevation download` and (SM5) `kartograf imagery
download`, ZTM sheet codes by `kartograf maps download --country cz`. Since 0.8.0
two-letter SM5 sheet codes also work
(99 As sheets, `AS22`…`AS94`, e.g. `AS91`) — previously they ended with
a PL sheet code error, also for DMR.

`kartograf sheet find` does the reverse: it lists the PL sheet codes that cover an area
(`--bbox` with `--bbox-crs`, or a `--geometry` file with `--layer`), in the scale `--scale` and the sheet system
`--sheet-system` (both options are required, there are no defaults), without network access and without truncating the list:

```bash
kartograf sheet find --bbox 565000,242000,566000,243000 --scale 1:10000 --sheet-system 1992
kartograf sheet find --geometry zlewnia.gpkg --scale 1:2000 --sheet-system 2000 --json
```

`kartograf store overview --root ./data` lists the segments of a store (product, country, dataset key),
`kartograf store entries --root ./data --segment nmt/pl_1992_1m_evrf2007 --limit 20 [--units N-34-130-D-d-2-4]`
— the first entries of a segment (version files with their sidecars; `truncated` in `--json` says whether there were more),
and `kartograf store sidecar --path ./data/nmt/.../file.asc` — the sidecar of one file with the `raw` field.
Both reads leave the data alone (nothing is written or downloaded); in the library they are
`describe_store`, `list_store_entries` and `read_store_sidecar`.

**Per-country values.** `--resolution` and `--vertical-crs` accept a single
value for every country of the task (`--resolution 5m`) or `country=value`
pairs (`--resolution pl=1m,cz=2m`, `--vertical-crs
pl=EVRF2007,cz=Bpv`). A single value must be available in every country
of the task (common: NMT `5m`, NMPT `0.5m`, `EVRF2007`; the PL cutout has
only 1 m, so PL+CZ cutouts usually need the per-country form);
otherwise `Error:` before any network access
with a hint about the per-country form. A country key outside the task is not
an error. A plain `--resolution 1m` or `--vertical-crs KRON86` under `auto`
points to PL (`Info: --country auto -> pl`), because CZ does not have them.
Rectangular country envelopes may trigger CZ also for an area
in Poland (the CZ part is then sometimes entirely nodata).

- CZ resolution: an SM5 sheet (e.g. `CTES96`) is a ready-made DMR 4G file
  (NMT, 5 m only) or DMP OK (NMPT, 0.5 m only) — `--resolution` can be
  omitted, and any other value is an error (`Error:`, code 2, no network). A TM33
  tile and `--bbox`/`--geometry` (cutout, `--cutout`) require
  `--resolution`: NMT `2m` (DMR 5G) or `5m` (DMR 4G), NMPT `0.5m`
  (DMP OK) or `2m` (DMP 1G). A TM33 DMR 4G and DMP OK tile
  with `--vertical-crs EVRF2007` is a ready-made ETRS89 (EPSG:3045) file from CUZK;
  the other tiles and cutouts are cut from the ImageServer service.
- A CZ NMT/NMPT area (`--bbox`/`--geometry`) is always a single cutout
  and requires `--cutout --horizontal-crs` (natively `EPSG:5514`); without
  `--cutout` it is an `Error:` before any network access. PL without `--cutout` gives a list of sheets,
  CZ orthophoto of an area — SM5 sheets (below).
- CZ LAZ (`--product laz`): `--model` selects the model — `dmr5g` (terrain,
  DMR 5G), `dmr4g` (terrain, 5 m grid), `dmp1g` (surface, DMP 1G),
  `dmpok` (surface, image correlation) — and is required when the
  task includes CZ; with a PL-only task or with a raster it is an `Error:`.
  The `.laz` file goes to the store byte for byte as in the CUZK ZIP, without
  point transformation, so `--vertical-crs` selects files: `Bpv` =
  SM5 sheets (S-JTSK, EPSG:5514), `EVRF2007` = TM33 tiles (ETRS89,
  EPSG:3045); a sheet code of the other system is an `Error:` before any network access. The area
  expands to sheets of the CUZK index of that system (SM5 sheets with a part
  in CZ, TM33 tiles); `--cutout`, `--resolution`, year, campaigns
  and `--min-density` apply only to PL LAZ (`Error:`). A file that could not
  be downloaded does not interrupt the others (`Error:` for the sheet,
  exit code 10 or 11).
- Failure of one country under `auto` (no data or source outage) when the
  other succeeds ends with code 0: on stderr a `Warning:` about partial
  success and an `Error:` with the cause of the failure; exit code 10 or 11 when no country gave
  a result or `--country` was explicit.
- Natively S-JTSK/Bpv (EPSG:5514: SM5 sheets, ImageServer service)
  and ETRS89/EVRF2007 (EPSG:3045/5621: TM33 tile files DMR 4G and DMP OK,
  LAZ TM33); `KRON86` is unreachable for CZ.
  Details: SCOPE 2.2 and 3.2, ARCHITECTURE 4.4–4.7.
- Version store (0.8.0): a CZ sheet, a CZ LAZ file and a CZ cutout are kept
  as versions in `<segment>/versions/`, the sheet path and `bbox/<coords>.tif`
  are hard links (segments `nmt/cz_dmr5g_<vcrs>`, `nmt/cz_dmr4g_<vcrs>`,
  `nmpt/cz_dmpok_<vcrs>`, `nmpt/cz_dmp1g_<vcrs>`, `laz/cz_<model>_<vcrs>`).
  `openzu` files — SM5 sheet, TM33 tile DMR 4G/DMP OK in EVRF2007
  and CZ LAZ — have a cheap signal (`ETag`/`Last-Modified` of the file, stored
  in the version sidecar `extra.http`): by default one
  `HEAD` per file with a local version — newer content gives the suffix `; dostepna
  nowsza ... (--upgrade)`, and `--upgrade` downloads it; a failed `HEAD` is a
  `Warning:` and the local version (with `--upgrade` — an error). A TM33 tile
  from ImageServer and a CZ cutout (`exportImage`) have no cheap signal:
  local version without network, re-download only with `--force`.
- A TM33 DMR 4G tile in EVRF2007 stored in the version store before this
  change (warp from ImageServer, without `extra.http`) remains the local version
  with an `Info:` (unchecked); `--force` downloads the CUZK file as a new version
  and repoints the link. A plain 0.7.x file at the standard path is
  replaced on first download.

**CZ orthophoto (`imagery download --country cz`, since 0.8.0).** An SM5 sheet
from the CUZK ATOM service is four files stored 1:1, without pixel conversion:
a JPEG image and three georeferencing files (world file JGW) in the
S-JTSK, ETRS89 / UTM 33N and ETRS89 / UTM 34N systems.

```bash
# sheet SM5 (country from the sheet code); sheet code As has 2 letters
kartograf imagery download --product orto --sheet CTES96 --root ./data
#   -> orto/cz_sjtsk/CTES/96/: CTES96.jgw, CTES96.TM33N.jgw, CTES96.TM34N.jgw, CTES96.jpg
#      (wersja <year>_<release>, np. 2024_2025-02-06_<sha8>; ZIP CUZK 16-64 MB)
kartograf imagery download --product orto --country cz --sheet AS91 --root ./data
# area = SM5 sheets from the CUZK index (here CTES86 and CTES96), without --cutout
kartograf imagery download --product orto --country cz "--bbox=-448500,-1113500,-446500,-1112500" --bbox-crs EPSG:5514 --root ./data
# border area under auto: PL sheets (--sheet-system for the PL part) and CZ SM5 sheets
kartograf imagery download --product orto --country auto --bbox 18.60,49.74,18.64,49.76 --bbox-crs EPSG:4326 --sheet-system 1992 --root ./data
# newer vintage without downloading images (release from the ATOM feed)
kartograf imagery download --product orto --sheet CTES96 --check --root ./data
kartograf imagery list-sources   # --product orto (PL: pl.gugik.orto, CZ: cz.cuzk.orto)
```

- **CRS in GIS.** A JGW file does not carry a CRS. GIS reads the JPEG
  georeferencing from the file with the same name (`CTES96.jpg` +
  `CTES96.jgw`) — assign the layer the CRS **EPSG:5514** (S-JTSK /
  Krovak East North). `CTES96.TM33N.jgw` georeferences the same image
  in EPSG:3045 (ETRS89 / UTM 33N), and `CTES96.TM34N.jgw` in EPSG:3046
  (ETRS89 / UTM 34N); to use them, copy the JPEG outside the store and give
  the copy of the TM file the name `<copy>.jgw` (do not change files in the store —
  they are hard links to the version). The CRS of each file is given by its
  sidecar (`horizontal_crs`), and the JPEG sidecar also has the map
  `extra.world_files` (`.jgw` EPSG:5514, `.TM33N.jgw` EPSG:3045,
  `.TM34N.jgw` EPSG:3046; measured 2026-10-16: agreement to 3 cm). Pixel
  of the sheets in the samples: 0.125 m.
- **Current year only.** CUZK publishes free of charge one, current
  release of a sheet (archival CUZK orthophotos are paid): `--year`,
  `--min-year`, `--max-year`, `--all-campaigns`, `--full-sheet`,
  `--sheet-system`, `--scale`, `--format` and `--resolution` with `--country cz`
  give an `Error:` (e.g. `--year dotyczy tylko PL - CUZK publikuje tylko
  aktualny rocznik arkusza ortofoto CZ (archiwalne ortofoto CUZK sa
  platne, poza zakresem)`); under `auto` the year and sheet flags apply to the PL
  part. A TM33 tile as `--sheet` is an `Error: ortofoto CZ ma arkusze SM5 (np.
  CTES96, AS91); kafle TM33 sa tylko dla NMT ...`; `--cutout` with CZ — `Error:`.
- **Freshness.** The version label is the year and release date from the ATOM feed
  (`2024_2025-02-06`). By default local files are used without queries
  (suffix `(bez sprawdzania; --check)`; immediately when offline),
  `--check` checks the release without downloading images, `--upgrade`
  downloads the new year (old versions stay in `versions/`), `--force`
  downloads again (the same content = `bez zmian`). One sheet is one
  ZIP download and one release check; a failed check
  (`--check`) gives one line `nie udalo sie sprawdzic` per file.
  JGW files are written before the JPEG, so
  an image version always has georeferencing files.
- **Border area.** Under `--country auto` an area at the border gives PL sheets
  and CZ SM5 sheets (until now `auto` narrowed the orthophoto to PL);
  the files of both countries share `extra.parent_request`. Details:
  ARCHITECTURE 4.4, [ADR-042](DECISIONS.md) D13 (erratum 4).

**CZ contours (`elevation download --product contours`, since 0.8.0).**
ZABAGED CUZK contours: an SM5 sheet ZIP from openzu stored 1:1 (without
unpacking), S-JTSK (EPSG:5514), Bpv heights.

```bash
kartograf elevation download --product contours --format SHP --sheet CTES96 --root ./data
#   -> contours/cz_zabaged_shp/CTES/96/CTES96.zip (8 plików SHP)
kartograf elevation download --product contours --format DGN --sheet CTES96 --root ./data
#   -> contours/cz_zabaged_dgn/CTES/96/CTES96.zip (3 pliki)
# area = SM5 sheets from the CUZK index (here CTES86 and CTES96)
kartograf elevation download --product contours --format SHP --country cz "--bbox=-448500,-1113500,-446500,-1112500" --bbox-crs EPSG:5514 --root ./data
```

- `--format SHP|DGN` is required; `--vertical-crs` can be omitted (only
  `Bpv`). `--resolution`, `--cutout`, `--horizontal-crs`, PL sheet flags
  and flight flags give `Error: ... warstwice to arkusze SM5 (wektor) - bez
  rozdzielczosci, lotow i wycinka`; a TM33 tile and `--country pl` - `Error:`.
- Freshness: HTTP signal (`ETag`) - local version after one `HEAD`,
  `--check` without downloading. The sidecar has a list of ZIP files
  (`extra.members`), `mapname` and `cz_share` from the index.

### 1.5 Land cover, soils, HSG, cache

```bash
kartograf landcover download --product bdot10k --teryt 1465 --root ./data
#   landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: nowa wersja 2026-10-12_f3550257
kartograf landcover download --product bdot10k --teryt 1465 --format SHP --root ./data
#   landcover/pl_bdot10k_shp/teryt/1465.zip: nowa wersja ...  (archiwum .zip)
# Area spanning two counties (TERYT from PRG WFS): package of EACH county, separate file
kartograf landcover download --product bdot10k --bbox 626000,480000,628000,482000 --root ./data
#   landcover/pl_bdot10k_gpkg/teryt/1421.gpkg: nowa wersja 2026-10-12_38da4056
#   landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja 2026-10-12 (bez sprawdzania; --check)
#   Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 1, bledy: 0 (./data)
#   (ścieżka zawsze teryt/<TERYT> — pakiet to cały powiat; obszar żądania
#    w sidecarze extra.parent_request; to samo dla --sheet i --geometry)
kartograf landcover download --product corine --year 2018 --sheet N-34-130-D --root ./data
#   z CLMS_CREDENTIALS: landcover/eu_corine_2018/N-34/130/D/N-34-130-D.tif: nowa wersja V2020_20u1_<sha8>
#   bez: Info: CORINE 2018: podglad WMS ...
#        landcover/eu_corine_2018_preview/N-34/130/D/N-34-130-D.png: nowa wersja 2026-10-12_<sha8>
# The WMS preview works for 2018, 2012, 2006, 2000 (EEA; Kartograf reads the year's raster layer
# from the GetCapabilities of that year's service) and 1990 (DLR). A fully transparent image (the service
# has no CLC data for that year for the area: 1990 for Poland, an area outside Europe) is an
# Error: (exit code 11, `no_coverage`) and no version in the store.
kartograf soil download --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean --root ./data
#   soil/global_soilgrids_clay_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_717f0989
# The segment carries every content parameter (lowercase), so --property sand
# for the same area is a separate file; the parameters are also in the sidecar
# (request.property/depth/stat, request.year, request.format).
# Values in the file are integers in ISRIC units (clay g/kg, phh2o pH x 10, bdod
# cg/cm3, soc dg/kg, nitrogen cg/kg, cec mmol(c)/kg, cfvo cm3/dm3, ocd hg/m3, ocs t/ha);
# conventional unit = value / divisor: `soil list-layers`, sidecar `extra.units`
# ({"mapped": "g/kg", "conventional": "%", "divisor": 10}). `ocs` only --depth 0-30cm.

# Only selected BDOT10k layers (GPKG) + original ZIP, bbox in WGS84,
# 4 counties in parallel, without status lines (Info:/Warning:/Error: remain)
kartograf landcover download --product bdot10k --bbox 16.70,50.45,16.80,50.55 \
    --bbox-crs EPSG:4326 --layers SWRS,PTWP --keep-raw --workers 4 -q --root ./data
#   -> landcover/pl_bdot10k_gpkg_ptwp-swrs/teryt/<T>.gpkg
#      i landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip

# BDOO (general geographic database of GUGiK, 1:250 000): voivodeship GML package
# per annual edition (--year required: 2015, 2021-2026); --teryt = voivodeship code
kartograf landcover download --product bdoo --teryt 12 --year 2023 --root ./data
#   landcover/pl_bdoo_2023/teryt/12.zip: nowa wersja 2023_bd431599   (ZIP 1:1, 11,5 MB)
# area = packages of the voivodeships of its counties (PRG); --layers = ZIP of files of the selected classes
kartograf landcover download --product bdoo --bbox 523000,253000,528000,258000 \
    --year 2023 --layers KUIK,PTWP --root ./data
#   Info: bdoo: wojewodztwa obszaru wg PRG (2): 12 (malopolskie), 24 (slaskie)
#   Info: bdoo PL 24: paczka nie ma plikow klas KUIK (brak takich obiektow); zapisano klasy PTWP
#   landcover/pl_bdoo_2023_kuik-ptwp/teryt/12.zip: nowa wersja 2023_830c40f8
#   landcover/pl_bdoo_2023_kuik-ptwp/teryt/24.zip: nowa wersja 2023_79659873
#   Nowe: 2, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0 (./data)

# Hydrologic Soil Groups for the SCS-CN method (clay/sand/silt inputs in the same store)
kartograf soil hsg --bbox 626000,480000,628000,482000 --depth 0-5cm --summary --root ./data
#   soil/global_soilgrids_{clay,sand,silt}_0-5cm_mean/bbox/...: nowa wersja 2.0_<sha8>
#   hsg/global_soilgrids_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_470ef3d9
# Again (also with --force, when the content of the inputs has not changed): ... uzyta ponownie 2.0

# Overview of sources/layers and the metadata cache
kartograf landcover list-sources
kartograf landcover list-layers --product zabaged   # 22 ZABAGED layers (section 1.9)
kartograf landcover list-layers --product bdoo      # BDOO classes of each annual edition (--year)
kartograf soil list-layers
kartograf cache stats
kartograf cache clear
kartograf cache path
```

`--root` is the store directory (versions in `versions/`, standard path
= hard link; ARCHITECTURE 3.3 rule 8); `soil hsg --root plik.tif` is an
`Error:` (file outside the store: `hsg_from_rasters`). `--teryt` applies to
BDOT10k (county (Polish powiat), 4 digits) and BDOO (voivodeship, 2 digits); CORINE and SoilGrids
select the area through `--sheet`, `--bbox` or `--geometry`. BDOT10k
with `--bbox`/`--sheet`/`--geometry` downloads all counties of the area (the list
comes from the PRG WFS, responses in the metadata cache — `cache stats` counts them
in `Wpisy TERYT`); an error for one county is `Error: <TERYT>: ...`, the rest
are downloaded, exit code 10; an area without a county (sea) is an `Error:`. A BDOT10k area
(current packages and the `--year` archive) is subject to the limit from section 1.8 (100 files
or 10 GB according to `HEAD`, `Error:` code 2 before the download) and prints the list of counties
in `Info:` (`unit_list`). `--layers`: a BDOT10k class code from `landcover list-layers
--product bdot10k` (58 classes, also `BUBD`); an unknown code is an `Error:` code 2 before
the network, a class without objects in the county (absent from the package, e.g. `SWKN` in Sopot)
is an `Info:` `classes_absent` — the remaining classes are saved, and the absence of all of them is an
error for the county (as with BDOO). Modes
`--check`/`--upgrade`/`--force`/`--plan`: section 4.3. CORINE without
CLMS credentials downloads a PNG preview (section 6). BDOT10k layers,
SoilGrids parameters and CORINE years: PRD 3.5–3.7. ZABAGED, Data50 and Data250
(`--product zabaged|data50|data250`, CZ: an area or a national file): section 1.9.

**BDOO.** `--product bdoo` downloads the GUGiK general geographic objects database
(1:250 000) as GUGiK publishes it: a voivodeship GML package per
vintage (`--year` required; vintages 2014 and 2016–2020 do not exist — `Error:`
with a list, before the network). There is no national file. A county code (`--teryt 1261`)
ends with an `Error:` with the hint `--teryt 12`; an area (`--bbox`,
`--sheet`, `--geometry`) yields the packages of all voivodeships it intersects
(list in `Info:`; an error for one voivodeship does not stop the others,
`--workers` downloads in parallel, a summary line at the end). `--layers`
(class codes, e.g. `PTWP,SWRS`; list: `landcover list-layers --product bdoo`)
saves a ZIP of `__OT_<CODE>_<type>` files of the selected classes in a separate segment
(`pl_bdoo_2023_ptwp-swrs`): the files are byte for byte as in the package, while composite
objects (`__OT_Ciek` etc.), XSD and metadata remain only in the full package.
Packages up to 2023 have no file for a class whose objects are absent
in the voivodeship: the absence of some selected classes is an `Info:`, the absence of all — an
error for that voivodeship. A class outside the vintage (e.g. `KUIK` from 2024) is an
`Error:` with the list of classes of the vintage. The version has a vintage label; GUGiK does not
provide a change signal, so `--check` reports "nie da się sprawdzić
bez pobrania", and `--force` downloads again (the same content = `bez zmian`).

### 1.6 When `--scale` is required

`--scale` is the **target** scale of the PL-2000 sheets that Kartograf orders
from GUGiK (NMT, NMPT, orthophoto). It must match the scale of the sheets in which
GUGiK publishes the given product — Kartograf downloads the sheet file with exactly
that sheet code (the whole token), so a sheet in a different scale will not be matched.
Values: `1:5000`, `1:2000`, `1:1000`, `1:500`. Since 0.8.0 there is no
default value.

**When:**

- `--bbox`/`--geometry` with `--sheet-system 2000` (without `--cutout`): required —
  the area is split into sheets in this scale;
- `--sheet` with a PL-2000 1:10000 sheet code (e.g. `7.171.21`): required — the sheet code
  is expanded to descendants in this scale (`kartograf sheet parse <sheet_code>
  --descendants <scale>` shows the list before the download);
- a finer PL-2000 sheet code (e.g. `7.171.21.23`): optional — without the flag
  that sheet is downloaded, with the flag its descendants in this scale;
- does not apply to LAZ (tiles selected from WFS), CZ (TM33/SM5 sheet code or
  a cutout from the service) or the `--cutout` cutout.

**PL-1992 — flag not allowed.** GUGiK publishes PL-1992 sheets only
with a 7-part sheet code (e.g. `N-34-130-D-d-2-4`), designated in Kartograf
as `1:10000`; a coarser sheet code (e.g. `N-34-130-D`) and `--bbox`/`--geometry`
with `--sheet-system 1992` always yield these sheets, and `--scale` with a PL-1992 task
ends with an `Error:` (code 2, before the network). A note on naming: the Kartograf
scale labels are one level finer than the GUGiK nomenclature — the
same 7-part sheet is described by the GUGiK sheet index as an archiving module
1:5000 (`modulArchiwizacji`).

**PL-2000 — publication scale.** Kartograf starts the PL-2000 division from
the 1:10000 sheet (`zone.belt.column`, e.g. `7.171.21`), while GUGiK publishes
PL-2000 sheets in finer modules. In the saved responses of the
NMT 1 m and orthophoto sheet index, on which the Kartograf tests are based, PL-2000 sheets
most often have a 1:2000 module (e.g.
`7.171.21.23`, `5.167.25.13`), and 1:1000 and 1:5000 sheets also occur alongside them;
there was no PL-2000 1:10000 sheet in them at all. So usually
`--scale 1:2000`:

```bash
kartograf elevation download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --root ./data
```

**PL-2000 — zones.** A PL-2000 zone is the area of its powiats, not a longitude strip:
§ 22 of the regulation on the national spatial reference system (Dz.U. 2012 poz. 1247)
puts the zone boundaries on powiat boundaries, and a powiat that 16.5, 19.5 or 22.5 E
cuts belongs to the zone of its larger part (ADR-055; e.g. the whole of Łódź is zone 6).
A `--bbox`/`--geometry` across a zone boundary downloads each zone's sheets only on its own
side, each sheet once; outside Poland the nominal 3-degree strips hold. `kartograf sheet
find --bbox ... --sheet-system 2000` lists the same sheets, and the library function
`find_sheet_outlines` adds the zone of each sheet and the outline a map draws.

**What happens on a mismatch.** The absence of a sheet with the ordered sheet code is
a lack of coverage (`NoCoverageError`), never a silent fallback download (e.g.
of a PL-1992 sheet). The sheet index does, however, return sheets from the queried location
(e.g. a descendant of the ordered sheet code), so Kartograf hints at the scale in which
the data are there:

- a single sheet code: `Error:` (exit code 11), and in the error text e.g.
  `Dostepny potomek 5.167.25.13 - uzyj --scale 1:2000`;
- a list of sheets (`--bbox`/`--geometry`, expanded sheet code): sheets without
  data have the status `no_coverage` (icon `0` on the progress bar), on stderr `Warning: GUGiK nie ma
  danych dla N z M arkuszy ...` (code 0, when at least one sheet was downloaded)
  or — when no sheet has data — `Error: GUGiK nie ma danych dla
  zadnego z M arkuszy obszaru` (exit code 11); in both cases below it
  the hints `Info: Dostepny potomek <sheet_code> - uzyj --scale <scale>`;
- when the sheet index has this area in the other system, the hint points to its
  sheet code or `--sheet-system <crs> --scale <scale>`;
- NMT and NMPT (since 0.7.2; since 0.8.0 from the WFS sheet index): when the sheet is not
  in the selected variant, and the GUGiK sheet index has it in another variant
  from the registry (section 1.1), the hint is e.g. `Skorowidz GUGiK ma ten
  arkusz w NMT 1m EVRF2007 - uzyj --resolution 1m` (or `--vertical-crs
  KRON86`, `--format XYZ`) — for a single sheet code in the `Error:` text
  (exit code 11), for a list of sheets as `Info:`. Other variants of the same format
  (e.g. a different grid resolution) are hinted first, other formats (archives)
  only when there are none. GUGiK has large EVRF2007
  coverage gaps, also for NMT 5 m (e.g.
  `N-34-130-D-d --resolution 5m`: 6 of 16 sheets only in 1 m).
  Other resolutions and formats of a sheet arrive in the same WFS response
  (without additional requests); the second vertical CRS costs one WFS
  request to its service (a service with an error is skipped until the end of the
  task); the hints go into the metadata cache together with the lack of
  coverage. A full picture of the variants of an area is given by `kartograf elevation
  availability` (section 1.7).

**How to determine the right scale.** The simplest way is from the CLI hint: the scale
in `uzyj --scale ...` is the scale of the sheet that GUGiK actually published
(it may be 1:2000, but also e.g. 1:1000). The scale of a sheet code and its descendants
is shown by `kartograf sheet parse` (`--descendants <scale>`). If different places
of the area have sheets in different scales, a single call with one `--scale`
downloads only part — fetch the remaining sheets with another call
with the hinted scale.

### 1.7 Availability report (`elevation availability`)

`kartograf elevation availability` answers **before the download** for
which years, sheet systems, resolutions, vertical CRSs and formats the
area has a complete set of full NMT/NMPT sheets (LAZ: tiles) according to the GUGiK
sheet index, and in Czechia (since 0.8.0) — which SM5 sheets and TM33 tiles of the area
have CUZK files. It reads only the WFS sheet index (the same one from which
`elevation download` downloads) and the PRG land mask, and for CZ the sheet index
`KladyMapovychListu` and the headers of `openzu` files (`HEAD`); it downloads no
data file. The area is selected as in `elevation download`:
`--sheet` (PL-1992, PL-2000 or CZ SM5/TM33 sheet code; country from the sheet code),
`--bbox` (`--bbox-crs`) or `--geometry` (`--layer`) — the last two
with `--country pl`, `cz` or `auto` (without the flag `Error: --country wymagane
z --bbox/--geometry: pl (GUGiK), cz (CUZK), auto (...)`).
`--year`/`--min-year`/`--max-year` narrow the vintages of the sheet index — PL
only: with `--country cz` or a CZ sheet code this is an `Error:`, under `auto` a PL+CZ area
is narrowed to PL (`Info:`), and an area only in CZ is an `Error:`.

```bash
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
kartograf elevation availability --product nmpt --sheet M-34-64-D-d-2-1
kartograf elevation availability --product laz --country pl --geometry zlewnia.gpkg --layer catchments --min-year 2020
kartograf elevation availability --product nmt --country pl --bbox 339000,744800,343000,747000 --details
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000 --json > krakow.json
# Czechia and border area (since 0.8.0)
kartograf elevation availability --product nmpt --sheet CTES96
kartograf elevation availability --product nmpt --country cz "--bbox=-447000,-1114000,-446600,-1113600" --bbox-crs EPSG:5514
kartograf elevation availability --product laz --country cz "--bbox=-450000,-1114000,-444000,-1113000" --bbox-crs EPSG:5514 --details
kartograf elevation availability --product nmpt --country auto --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326 --json
```

Kraków (NMT, bbox 4 x 4 km; live printout 2026-10-15):

```
Dostepnosc NMT PL wg skorowidza GUGiK: obszar 16,00 km2, w tym lad 16,00 km2

  ROK   NALOT                   UKLAD    ROZDZ.  WYSOKOSCI  FORMAT     ARKUSZE TAK/NIE  KOMPLET
  2025  2025-04-28              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2024  2024-06-21..2024-07-30  PL-1992  1m      EVRF2007   ASC        6/0              tak
  2023  2023-09-08              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2023  2023-03-17              PL-2000  1m      EVRF2007   ASC        15/0             tak
  2022  2022-06-03              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2021  2021-10-04..2021-10-05  PL-2000  1m      EVRF2007   ASC        15/0             tak
  2019  2019-10-17              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2019  2019-08-26              PL-1992  5m      EVRF2007   ASC        6/0              tak
  2019  2019-08-26              PL-1992  5m      EVRF2007   ASCII-NMT  6/0              tak
  2018  2018-04-21              PL-1992  1m      EVRF2007   XYZ        4/0              nie: brak arkuszy dla 6,66 km2
  2018  2018-04-22              PL-1992  5m      EVRF2007   XYZ        2/0              nie: brak arkuszy dla 9,34 km2
  2018  2018-04-22              PL-1992  25m     EVRF2007   TBD        2/0              nie: brak arkuszy dla 9,34 km2
  2017  2017-10-21..2017-11-05  PL-1992  1m      KRON86     ASC        6/0              tak
  2017  2017-10-21..2017-11-05  PL-1992  1m      KRON86     XYZ        6/0              tak
  2015  2015-05-29              PL-1992  1m      KRON86     XYZ        4/0              tak
  2012  2012-07-06..2012-07-07  PL-1992  1m      KRON86     ASC        6/0              tak
  2012  2012-07-06..2012-07-07  PL-1992  1m      KRON86     XYZ        6/0              tak
  2009  2009-01-01              PL-1992  15m     KRON86     TBD        4/0              tak
  2009  2009-01-01              PL-1992  -       KRON86     TIN        4/0              tak
  2009  2009-01-01              PL-1992  -       KRON86     TTN        4/0              tak

Najnowsza kompletna kombinacja: 2025 PL-1992 1m EVRF2007 ASC
  Pobranie (dodaj --root KATALOG): kartograf elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025
  W projekcie: kartograf project add NAZWA elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025
```

Pomerania (NMT, bbox 4 x 2.2 km on the coast — most of the area is sea):

```
Dostepnosc NMT PL wg skorowidza GUGiK: obszar 8,80 km2, w tym lad 86,38 ha

  ROK   NALOT                   UKLAD    ROZDZ.  WYSOKOSCI  FORMAT  ARKUSZE TAK/NIE  KOMPLET
  2025  2025-01-30              PL-1992  0.5m    EVRF2007   ASC     0/4              nie: 4 niepelne
  2025  2025-04-21              PL-1992  5m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2023  2023-04-06..2023-09-06  PL-1992  5m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2022  2022-09-04              PL-1992  0.5m    EVRF2007   ASC     1/3              nie: 3 niepelne
  2022  2022-06-17              PL-1992  1m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2021  2021-10-09              PL-1992  0.5m    EVRF2007   ASC     1/3              nie: 3 niepelne
  2020  2020-06-01              PL-1992  5m      EVRF2007   XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2017  2017-05-27              PL-1992  1m      KRON86     XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2011  2011-04-27              PL-1992  1m      KRON86     ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2011  2011-04-27              PL-1992  1m      KRON86     XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2010  2010-07-04              PL-1992  25m     KRON86     TBD     3/0              tak
  2005  2005-01-01              PL-1992  25m     KRON86     TBD     3/0              tak
  2005  2005-01-01              PL-1992  25m     KRON86     DXF     3/0              tak
  2005  2005-01-01              PL-1992  -       KRON86     TIN     3/0              tak
  2005  2005-01-01              PL-1992  -       KRON86     TTN     3/0              tak

Najnowsza kompletna kombinacja: 2010 PL-1992 25m KRON86 TBD
  Pobranie (dodaj --root KATALOG): kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010
  W projekcie: kartograf project add NAZWA elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010
```

How to read the table:

- **Combination** = year of the sheet index annual layer, sheet system
  (PL-1992/PL-2000), resolution, vertical CRS and variant format
  from the registry (section 1.1); archives (`XYZ`, `TBD`, `TIN`...) are
  combinations to download just like ASC grids. `NALOT` is the range of record
  acquisition dates, `-` in `ROZDZ.` — a format without resolution
  (TIN, TTN). LAZ: combination = year, CRS and vertical CRS of the tiles,
  `ROZDZ.` = nominal density from WFS (e.g. `5 pkt/m2`), `FORMAT` = `LAZ`.
- **TAK/NIE** is the sheet index declaration `calyArkuszWypelnionyTrescia`
  (LAZ: `czy_ark_wypelniony`): `6/0` = 6 sheets with a full record of the
  combination, 0 sheets with incomplete records only. NIE does not say only
  that the sheet is not entirely filled — the gap can range from 1% to
  99%; the report **does not measure the content** of the files (sheet coverage is measured
  only by the download, section 4.1).
- **KOMPLET** `tak` = all land of the area lies within full (TAK)
  sheets of the combination. Land is the PRG state boundary (`A00`) without the
  territorial sea and marine internal waters (`W02`, `W03`) — in
  Pomerania 86.38 ha out of 8.80 km2; the sea needs no sheets. Measured on a
  1 m grid (pixel centres), with no tolerance threshold. `nie: N niepelne`
  = N sheets of the area have only NIE records in this combination; `nie: brak
  arkuszy dla X` = X of land does not lie in any sheet of the combination (e.g.
  2018 in Kraków: XYZ/TBD archives only for part of the area).
- The area is the same one that the download covers: `--sheet` = the sheet code frame
  (the measurement skips the 1 m strip at the frame — the frame computed from the sheet code differs from
  the GUGiK frame by centimetres), `--bbox` and `--geometry` (envelopes of features,
  like the sheets of `elevation download`) are measured exactly; LAZ — the sheet
  frame or the envelope of the whole geometry, as when downloading tiles. A sheet
  touching the area only along an edge does not belong to the combination.
- Order: year descending, then sheet system, resolution, vertical
  CRS and format.

**Download hint.** The footer gives the latest complete combination
and the command to download it — **without `--root`**: paste the `Pobranie` line after
appending `--root KATALOG`, the `W projekcie` line after the task name
(manifest, section 8; the store comes from the project). The command repeats the
task area, appends `--sheet-system`, the variant (`--format` for
archives, `--resolution`, `--vertical-crs`) and `--year`; for PL-2000 —
one command per sheet scale of the combination (`--scale`), and when
in some sheet the latest record of the year is NIE and a full record of that
year exists — `--full-sheet`. The command for the area (or sheet code) appears
only when its download plans solely sheets with a record
of the combination. When the area grid also has a sheet without such a record (abroad,
at sea, without data from that year or at that resolution), the
hint is one `--sheet` command for each sheet with a record —
no hint command ends with `Brak danych` (exit code 11); with
more than 5 commands the footer gives 5 and the number remaining
(all: `--details` or `--json`).
Archives (`--format`) and LAZ always have a command for the task area or sheet code.
Without a complete combination the footer says
`Zadna kombinacja nie pokrywa calego ladu obszaru pelnymi arkuszami
(arkusze niepelne i brakujace: --details)`.

`--details` appends for each combination the sheet codes of incomplete sheets, land
without sheets, in PL the share of land within full sheets (only for an
incomplete combination; rounded down to a whole percent, non-zero below 1% is `<1%`,
so an incomplete one never has 100%), each campaign separately (`komplet`
when its full sheets alone cover the land, otherwise its share), the campaigns of the
records that the hint command will download (number of records per
campaign; with `--full-sheet` a sheet has two records), and the download commands
(excerpt, Pomerania — the area grid has sea sheets without records, so
rasters get `--sheet` commands):

```
Szczegoly kombinacji:
  2025 PL-1992 0.5m EVRF2007 ASC: nie: 4 niepelne
    arkusze niepelne (4): N-33-58-A-c-1-3, N-33-58-A-c-1-4, N-33-58-A-c-2-3, N-33-58-A-c-3-1
    lad w ramach pelnych arkuszy: 0% (0,00 ha)
    kampanie: DFT.7201.024.2024 (0%)
    pobierane rekordy: 4 ark., kampanie: DFT.7201.024.2024 (4)
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-3 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-4 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-2-3 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-3-1 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
  2023 PL-1992 5m EVRF2007 ASC: nie: brak arkuszy dla 0,88 ha
    lad bez zadnego arkusza kombinacji: 0,88 ha
    lad w ramach pelnych arkuszy: 98% (85,50 ha)
    kampanie: DFT.7201.002.2023 (98%), DFT.7201.028.2023 (0%)
    pobierane rekordy: 3 ark., kampanie: DFT.7201.002.2023 (3), DFT.7201.028.2023 (2)
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-4 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
    kartograf elevation download --product nmt --sheet N-33-58-A-c-2-3 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
    kartograf elevation download --product nmt --sheet N-33-58-A-c-3-1 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
  2005 PL-1992 KRON86 TIN: tak
    kampanie: N-33-020/04 (komplet)
    pobierane rekordy: 3 ark., kampanie: N-33-020/04 (3)
    kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TIN --vertical-crs KRON86 --year 2005
```

`--json` prints the report as JSON (schema `kartograf-availability/1`) —
exactly the text that `check_availability(...).to_json()` returns
in the library (section 2); stdout is a single document, and notices
(`Info:`/`Warning:` of text mode) are only in the `notices` field, without
duplication on stderr (contract of `--json` mode: section 9.2). Fields (after
`schema`, the first key): `request`, `checked_at`, `areas`
(`area_m2`, `land_m2`), `combinations` (among others `source` = descriptor
key, `year`, `acquisition_dates`, `published`, `campaigns`,
`horizontal`, `resolution`, `vertical_crs`, `format`, `densities`,
`complete`, `sheets_full`, `sheets_partial`, `uncovered_m2`,
`download_hint` — commands without the `kartograf ` prefix, `full_m2`,
`sheet_records`, `campaign_coverage`), `failed` (a country that was not checked: `unit`, `country`, `error`, `kind`;
with `--country auto`), `notices` and `ok`. `full_m2` is
the land within full sheets (the lower bound of what certainly has data;
in PL `complete` if and only if `full_m2 == land_m2`), and
`land_m2 - uncovered_m2` — the upper bound. `sheet_records` are the records
that the `download_hint` command will download (`sheet`, `campaign`,
`acquisition_date`, `published`, `full_sheet`, `url`; by sheet, from the
latest; NMT/NMPT the latest record of the sheet and — with `--full-sheet` —
the latest full one, LAZ tiles selected by coverage from among the tiles of this
combination), `campaign_coverage` — each campaign separately (`campaign`,
`complete`, `full_m2`). **LAZ limitation:** the LAZ download command has
no sheet system, so it selects the latest tiles of both systems at once. When
a year has tiles in PL-1992 and in PL-2000, the `sheet_records` of a combination may
differ from what its command writes to the store (Kraków 2023:
the PL-2000 combination command downloads PL-1992 tiles); for NMT/NMPT
`sheet_records` is exactly the download plan. The fields `sheets_missing`
and `size_bytes` are filled only by the CZ part (in PL `[]`/`null`); in CZ
`full_m2` is the part of the area within sheets with a file — a complete
combination (every sheet of the index has a file) may have `full_m2 < land_m2`
when the area extends beyond the index sheets — and
`sheet_records`/`campaign_coverage` are empty. Beginning (Kraków):

```json
{
  "schema": "kartograf-availability/1",
  "request": {
    "product": "nmt",
    "country": "pl",
    "bbox": [565000.0, 242000.0, 569000.0, 246000.0],
    "bbox_crs": "EPSG:2180",
    "min_year": null,
    "max_year": null
  },
  "checked_at": "2026-10-15T20:50:50+00:00",
  "areas": [
    {"country": "PL", "crs": "EPSG:2180", "bounds": [565000.0, 242000.0, 569000.0, 246000.0],
     "area_m2": 16000000.0, "land_m2": 16000000.0}
  ],
  "combinations": [
    {
      "country": "PL", "product": "nmt", "source": "pl.gugik.nmt_1m", "year": 2025,
      "acquisition_dates": ["2025-04-28", "2025-04-28"],
      "horizontal": "PL-1992", "resolution": "1m", "vertical_crs": "EVRF2007", "format": "ASC",
      "complete": true,
      "sheets_full": ["M-34-64-D-d-1-2", "M-34-64-D-d-1-4", "M-34-64-D-d-2-1", "..."],
      "sheets_partial": [], "uncovered": false, "uncovered_m2": 0.0,
      "download_hint": ["elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025"],
      "full_m2": 16000000.0,
      "sheet_records": [
        {"sheet": "M-34-64-D-d-1-2", "campaign": "GK-FOTO.6201.5.2025", "acquisition_date": "2025-04-28",
         "published": "2025-11-07", "full_sheet": true,
         "url": "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83137/83137_1729552_M-34-64-D-d-1-2.asc"},
        "..."
      ],
      "campaign_coverage": [{"campaign": "GK-FOTO.6201.5.2025", "complete": true, "full_m2": 16000000.0}]
    }
  ]
}
```

(Excerpt shortened by hand; the real output is indented by 2 spaces,
has each list value on a separate line and contains all fields.)

- **No data is a response, not an error:** an area without sheets in the sheet index
  gives `Brak arkuszy NMT dla obszaru w skorowidzu GUGiK` (LAZ: `kafli`;
  CZ: `Brak arkuszy NMPT dla obszaru w indeksie CUZK`)
  and code 0. A failure of the sheet index or PRG (network, inconsistent WFS page,
  OGC report) is `Error:` and exit code 5 (`source_unavailable`) — never an empty report; likewise a failure of the
  CUZK index or a file `HEAD` other than `404`. A range of years with
  no annual layer of the service: `Error: --year 2030: skorowidz GUGiK NMT nie
  ma rocznika ... - dostepne roczniki: ...`.
- **The area of a single country must reach its envelope (since 0.8.0):** `--country pl`
  with `--bbox`/`--geometry` outside the PL envelope (or `--country cz` outside CZ) is
  `Error: --bbox (EPSG:2180) lezy poza CZ ... Sprawdz --bbox-crs ...` and code 2
  before any network access — the same check as in `elevation download`; it covers numbers
  in a CRS other than `--bbox-crs` and swapped axes. A `--bbox` with zero
  area (`min == max`) or with coordinates outside the EPSG:4326 range
  (longitude ±180, latitude ±90) is `Error: Nieprawidlowy bbox: ...` (code 2);
  a `--geometry` with zero area (a single point) is `Error: --geometry: ...`
  with `details.option=geometry` (section 1.2).
- **Area without land:** `area_m2` is the part of the area within the PL boundaries (with the territorial
  sea; the part outside the boundary has `0,00 ha`), `land_m2` — its land (PRG
  `A00` without `W02`/`W03`). An area entirely at sea (`land_m2 = 0`) has no land
  to cover, so every combination has `complete: true` (`full_m2 = land_m2 = 0`,
  in the table `KOMPLET` = `brak ladu`), and the report says so in `Info:` (code `no_land`
  in `notices`); the footer gives no download command. The invariant `complete`
  if and only if `full_m2 == land_m2` holds.
- **`Info:`** (code `index_unsupported` in the library) lists the records
  of the area that Kartograf does not download: record format inconsistent
  with the file, a format or variant outside the registry, a sheet code outside the
  PL-1992/PL-2000 systems, or a missing `https` address or CRS.
  Archives from the registry do not end up in `Info:` — they are combinations.
- **Cache:** WFS layer types, area records with sheet outlines and the PRG land
  mask, and for CZ index sheets and file `HEAD` results go to the
  metadata cache (`<cache_dir>/kartograf/metadata.db`, TTL
  7 days; `kartograf cache stats`: `Wpisy obszarow skorowidza`), so a
  repeated report for the same area does not query the network (measured
  2026-10-15: 0.6–1.5 s instead of approx. 5–7 s for 16 km2). `--force`
  skips reading the cache, queries the sheet index, PRG and CUZK again and overwrites
  the entries.
- **Time:** the land mask is rasterised on a 1 m grid in strips of
  4 Mpx, so the report for a large area (e.g. an entire catchment) takes
  correspondingly longer (section 7).
- **Project:** `availability` is not a project data command
  (`kartograf project add NAZWA elevation availability ...` = `Error:`);
  add the command from the `W projekcie` line to the manifest (section 8).

**Czechia (CUZK).** CUZK does not publish flight years, so a CZ combination is a
model and sheet system with files in the native vertical CRS: NMT —
DMR 4G (`S-JTSK` Bpv and `ETRS89-TM33` EVRF2007), NMPT — DMP OK (the same
two systems), LAZ — eight combinations (four models × two systems). DMR 5G
and DMP 1G have no sheet files: the report does not cover them and says so
in `Info:` (they are available as a `--cutout` cutout, a TM33 tile from the service
and LAZ `--model`) — provided the CZ part has at least one index sheet (it has none,
e.g. for the `auto` part deep in Poland inside the CZ rectangle). The sheets are
the index sheets in the CZ part of the area (SM5 with a part in CZ, TM33 tiles) —
the same ones that LAZ downloads for the area; each file is checked by one `HEAD`:
`200` = file (`PUBLIKACJA` from `Last-Modified`, `ROZMIAR` — the sum of
`Content-Length`; `-` when no sheet of the combination has a file), `404`
= sheet without a file (`ARKUSZE SA/BRAK` = with a file/without a file,
`sheets_missing`, incomplete combination, `uncovered_m2` — the part of the
area rectangle within such sheets, never more than `area_m2`),
any other response (`503`, network) is `Error:`, never no data. The field
`area_m2` of the CZ part is the rectangle of that part in EPSG:5514 (sheet code: its
frame) — CZ has no land mask, so near the border it also includes PL
territory. Under `--country auto` the report has separate tables and `areas` for PL and CZ;
a part that could not be checked, with the other one checked, gives
`Warning:`, `ok: false` in JSON and code 10 (the report of the other part is
printed). The CZ footer gives the commands of complete combinations: raster —
one per sheet (`--sheet`, `--resolution`, native
`--vertical-crs`), LAZ — one area command with `--country cz`
and `--model` (for a sheet code — one per sheet); with more than
5 combination commands the footer gives 5 and the number remaining
(all: `--details` or `--json`). Append `--root
KATALOG` to the command (in a project: `kartograf project add NAZWA` instead of
`kartograf`).

Czechia (NMPT, 400 x 400 m bbox at Český Těšín; live output
2026-10-16, approx. 1.3 s, 0.6 s from cache; E2E report:
`docs/research/2026-10-16-plan-b-e2e/raport.md`):

```
Dostepnosc NMPT CZ wg indeksu arkuszy i plikow CUZK: obszar 16,00 ha
CUZK nie publikuje lat nalotu; daty = publikacja pliku

  MODEL   UKLAD        ROZDZ.  WYSOKOSCI  FORMAT  ARKUSZE SA/BRAK  PUBLIKACJA  ROZMIAR  KOMPLET
  DMP OK  S-JTSK       0.5m    Bpv        TIFF    1/0              2025-10-10  16,7 MB  tak
  DMP OK  ETRS89-TM33  0.5m    EVRF2007   TIFF    1/0              2026-08-20  29,6 MB  tak

Kompletne kombinacje CZ (pobranie: dodaj --root KATALOG; w projekcie: kartograf project add NAZWA zamiast kartograf):
  DMP OK S-JTSK 0.5m Bpv TIFF
    kartograf elevation download --product nmpt --sheet CTES86 --resolution 0.5m --vertical-crs Bpv
  DMP OK ETRS89-TM33 0.5m EVRF2007 TIFF
    kartograf elevation download --product nmpt --sheet 760_5516 --resolution 0.5m --vertical-crs EVRF2007
```

On stderr: `Info: DMP 1G (2m) nie ma plikow arkuszy CUZK (raport ich nie
obejmuje) - jest dla calego CZ jako wycinek (--cutout), kafel TM33
z uslugi ImageServer (--sheet, np. 302_5550) i LAZ (--product laz --model
dmp1g)`.

### 1.8 Boundaries, cadastre, 3D building models and the BDOT10k archive

The groups `boundaries` (PRG boundaries, `--product admin`; address points
`addresses`; special boundaries `special`), `cadastre` (EGiB and the CZ cadastral
map, `--product map`; RCN prices, `--product prices`)
and `models3d` (3D building models, `--product buildings`)
share a common shape (ADR-042): exactly one choice — `--teryt` (unit
package), an `--bbox`/`--sheet`/`--geometry` area (with `--country`) or
`--whole-country` (national file; `boundaries` only) — and the modes
`--check`/`--upgrade`/`--force`/`--plan`, `--workers` and `-q` as
in the other groups. Each group has only its own content flags (`--level`
and `--format` in `boundaries`, `--format` and `--ku` in `cadastre`,
`--lod`/`--year` in `models3d`; a foreign flag is a parser error, code 2).
`models3d` is for Poland only (`--country pl`); `boundaries` also has
CZ boundaries (RUIAN) and CZ geomorphological units, `cadastre` — the CZ
cadastral map, and the CZ water network — the `hydro` group (section 1.9; the CZ examples
of this chapter are also there). The archive of BDOT10k annual editions is in the group
`landcover` (`--year`). 3D mesh and tree models (`models3d`) and control networks
and quasi-geoids (group `geodesy`) are described in section 1.11.

```bash
# BDOT10k yearly archives: original county package ZIP (GML or SHP)
kartograf landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP --root ./data
#   landcover/pl_bdot10k_shp_2024/teryt/1261.zip: nowa wersja 2024_5dbd678a
kartograf landcover download --product bdot10k --teryt 1261 --year 2022 --format SHP --root ./data
#   landcover/pl_bdot10k_shp_2022/teryt/1261.zip: nowa wersja 2022_6c64b1d3
kartograf landcover download --product bdot10k --teryt 1261 --year 2023 --format SHP --root ./data
#   landcover/pl_bdot10k_shp_2023/teryt/1261.zip: nowa etykieta 2023 (plik identyczny z 2022)
# Area = package of each county (PRG); --workers downloads counties in parallel
kartograf landcover download --product bdot10k --year 2018 --format GML --bbox 557000,244000,559000,246000 --workers 2 --root ./data
#   landcover/pl_bdot10k_gml_2018/teryt/1206.zip: nowa wersja 2018_b8b23714
#   landcover/pl_bdot10k_gml_2018/teryt/1261.zip: nowa wersja 2018_f8f5ead1
#   Nowe: 2, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0 (./data)

# 3D building models (CityGML): the release is selected by --lod and --year
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 --root ./data
#   models3d/pl_buildings_lod1_2024/teryt/1261.zip: nowa wersja 2024_dff392bb
kartograf models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500 --root ./data
#   Info: buildings: powiaty obszaru wg PRG (1): 1261
#   models3d/pl_buildings_lod2_2017/teryt/1261.zip: nowa wersja 2017_de14ed18

# PRG boundaries: units of the --level that intersect the area (one GPKG),
# voivodeship package (GML of all levels) or national file (SHP)
kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 --root ./data
#   boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg: nowa wersja 2026-10-15_d8fd43e6
kartograf boundaries download --product admin --teryt 12 --root ./data
#   boundaries/pl_prg_gml/teryt/12.zip: nowa wersja 2026-10-15_919fce9d
kartograf boundaries download --product admin --country pl --whole-country --root ./data
#   Warning: admin PL: plik krajowy https://opendata.geoportal.gov.pl/prg/granice/00_jednostki_administracyjne.zip - 377419459 B (ok. 377 MB)
#   boundaries/pl_prg_shp/country/pl.zip: nowa wersja 2026-10-15_40b93870

# EGiB: county export or parcels and buildings of the area from the aggregate WFS service
kartograf cadastre download --product map --teryt 1261 --root ./data
#   cadastre/pl_egib_gpkg/teryt/1261.gpkg: nowa wersja 2026-10-15_fd23bd6e
kartograf cadastre download --product map --country pl --bbox 565000,243000,567000,245000 --root ./data
#   cadastre/pl_egib/bbox/565000_243000_567000_245000.gpkg: nowa wersja 2026-10-15_14c95c95

# Again: local version without queries; --check: no cheap signal
kartograf boundaries download --product admin --teryt 12 --root ./data
#   boundaries/pl_prg_gml/teryt/12.zip: lokalna wersja 2026-10-15 (bez sprawdzania; --check)
kartograf boundaries download --product admin --teryt 12 --check --root ./data
#   boundaries/pl_prg_gml/teryt/12.zip: nie da sie sprawdzic bez pobrania (2026-10-15)

# PRG address points and streets (since 0.8.0): area, county package, national file
kartograf boundaries download --product addresses --country pl --bbox 566000,243500,566500,244000 --root ./data
#   boundaries/pl_prg_addresses/bbox/566000_243500_566500_244000.gpkg: nowa wersja 2026-10-16_f8981d39
kartograf boundaries download --product addresses --teryt 1261 --root ./data
#   boundaries/pl_prg_addresses_shp/teryt/1261.zip: nowa wersja 2026-10-16_ad2e3b66
kartograf boundaries download --product addresses --country pl --whole-country --format SHP --root ~/kartograf-data
#   Warning: addresses PL: plik krajowy https://opendata.geoportal.gov.pl/prg/adresy/PunktyAdresowe/POLSKA.zip - 563815148 B (ok. 564 MB)
#   boundaries/pl_prg_addresses_shp/country/pl.zip: nowa wersja 2026-10-16_957a5138

# PRG special boundaries: area (44 kinds, GPKG in OGC:CRS84) or national file
kartograf boundaries download --product special --country pl --bbox 21.0,52.22,21.01,52.23 --bbox-crs EPSG:4326 --root ./data
#   Info: special: wynik obszaru bez obwodow spisowych (kolekcja GranicaObwoduSpisowego: usluga odpowiada minutami) - sa w pliku krajowym: --whole-country --format SHP|GML
#   boundaries/pl_prg_special/bbox/21_52.22_21.01_52.23.gpkg: nowa wersja 2026-10-16_07b97606
kartograf boundaries download --product special --country pl --whole-country --format SHP --root ~/kartograf-data
#   Warning: special PL: plik krajowy https://opendata.geoportal.gov.pl/prg/granice/00_granice_specjalne_shp.zip - 734171465 B (ok. 734 MB)

# RCN (real estate prices): county export (4 digits) or voivodeship export (2 digits)
kartograf cadastre download --product prices --teryt 1201 --root ./data
#   cadastre/pl_rcn/teryt/1201.gpkg: nowa wersja 2026-10-16_a612f064
kartograf cadastre download --product prices --teryt 1261 --root ~/kartograf-data
#   Warning: prices PL 1261: duzy plik https://opendata.geoportal.gov.pl/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/1261_transakcje_ceny.gpkg.zip - 301623607 B (ok. 302 MB)
#   cadastre/pl_rcn/teryt/1261.gpkg: nowa wersja 2026-10-16_ed4cc8bb

# Group sources (from the registry, no network)
kartograf boundaries list-sources
kartograf cadastre list-sources
kartograf models3d list-sources
```

**BDOT10k archive.** `--year R` (2014–2025) is the GUGiK archive edition —
the state of the database at the beginning of year R — and not the year the objects were last updated. The county
package is stored 1:1 (without merging into GPKG, so without `--layers`
and `--keep-raw`) and requires `--format GML` or `SHP` (the archive has no GPKG).
Without `--year`, `landcover download` downloads the current packages as before;
`--format GML` without `--year` is an `Error:` with a hint. TERYT codes
change over time (counties are split and merged): a county without a package
in a given edition gives `Error: <TERYT>: Zrodlo nie publikuje paczki ...
(HTTP 404)`, and the remaining counties of the area are downloaded. Consecutive editions
are sometimes identical (GUGiK did not change the county data): the second gets the status
`nowa etykieta <year> (plik identyczny z <year>)` and takes no space —
it is a hard link to the same data.

**3D models.** `--lod 1` has the releases 2019, 2021, 2022 and 2024 (`--year`
required), `--lod 2` a single release 2017 (`--year` may be omitted, another year
is an `Error:`); the releases are listed by `--help` and the error message. The CityGML
package (ZIP) is stored 1:1, and the vertical CRS from the data goes to the
sidecar (`vertical_crs`): LoD1 2019 and LoD2 2017 — EPSG:9650 (KRON86),
LoD1 2021, 2022, 2024 — EPSG:9651 (EVRF2007). LoD2 does not cover the whole
country (e.g. Szczecin and the neighbouring counties): a missing county package gives
`Error: <TERYT>: ... (HTTP 404)` and exit code 10, the remaining counties are downloaded.
National model files (3.5–4.1 GB) are not supported.

**PRG boundaries.** An area requires `--level` (`wojewodztwo`, `powiat`,
`gmina`, `jednostka-ewidencyjna`, `obreb`): the result is one GeoPackage
with the full geometries of the units of that level that intersect the area (without
clipping), in EPSG:2180, with a PRG layer (e.g. `A03_Granice_gmin`) and its
fields (among others `JPT_KOD_JE`). `--teryt` accepts only a voivodeship
(2 digits: a GML package of levels A01, A02, A03, A05, A06); download county boundaries
by area (`--bbox`/`--geometry`). `--whole-country --country pl`
is a national SHP file (approx. 377 MB) — its size appears as a
`Warning:` before the transfer.

**EGiB.** `--teryt` (4 digits) is a GUGiK county export: a GeoPackage
with the layers `dzialki`, `budynki` and `transakcje` (the property price
register), refreshed daily — `--force` on the next day usually gives
a new version. The voivodeship package (approx. 1.4 GB) is not supported. An area
gives parcels and buildings from the GUGiK WFS aggregate service in one GPKG
(EPSG:2180, layers `dzialki` and `budynki`): counties that have not
integrated their service are gaps, and restricted attributes have
the value `brak_uprawnien`. The `DATA` field (the county data state date) does not
go into the file — its values are in the sidecar
(`extra.source.dropped_fields`), so the same content downloaded on another day
is the same version.

**PRG addresses.** `--product addresses` (PL only) has three choices:
an area (`--bbox`/`--sheet`/`--geometry` with `--country pl`) gives one
GeoPackage in EPSG:2180 with layers of address points and streets of the area
(GUGiK KIN WFS service); `--teryt` accepts only a county (4 digits) and gives
an SHP package 1:1 — `--teryt 12` is an `Error:` with a list of choices (there are
no voivodeship packages); `--whole-country --format SHP|GML` is a national file
(approx. 564 MB or approx. 804 MB), whose size appears as a `Warning:`
before the transfer. `--format` is required only with the national file.

**PRG special boundaries.** `--product special` (PL only) requires an area
or `--whole-country --format SHP|GML` (approx. 734 MB for SHP); `--teryt` is an
`Error:`. The area result is one GeoPackage in OGC:CRS84 with 44 kinds
of boundaries (courts, police, tax offices, forests, waters, maritime areas, ...),
one layer per kind with objects intersecting the area. An area
takes minutes (the PRG OGC API service is queried for each collection separately;
measured: Kraków 243 s, Warszawa 109 s), and a timeout
(120 s) is retried. Census districts (`GranicaObwoduSpisowego`) are not
part of the area result — the service responds to them in 158 to over 400 s —
so every area gets an `Info:` pointing to the national file in which they are.

**RCN.** `--product prices` (PL only): `--teryt` with 4 digits is a county
export, with 2 digits — a voivodeship, and an area is the export of each county
of the area. The file is a GeoPackage in EPSG:2180 with the layers
`transakcje_dzialki`, `transakcje_budynki` and `transakcje_lokale`,
refreshed daily (the file is replaced without a signal; new content only
with `--force`). The package is unpacked into one GPKG, and a missing one
of the three layers is an `Error:` and no version. **Disk space:** unpacking
and checking the layers happen in the system's local temporary directory (on the author's machine
`/tmp` is RAM): county 1261 (302 MB in ZIP) unpacks to
approx. 1.1 GB, so for a voivodeship export (on the order of 1.8 GB) make sure there is space
in the temporary directory (`TMPDIR`). Above 100 MiB a `Warning:`
with the size appears before the download.

**Freshness and versions.** GUGiK packages and service objects have no cheap
change signal: the next run uses the local version without queries,
`--check` reports `nie da sie sprawdzic bez pobrania`, and new
content is obtained with `--force` (the same content = `bez zmian`, different = a new version next to the
old one). The version label is the archive edition or the 3D model year, and for PRG
and EGiB — the download date. The version sidecar carries the choice (`request`), the source
(`extra.source`: package URL or the service and the object count of each
layer) and the task area (`extra.parent_request`) — ARCHITECTURE 3.2
and 4.10.

**Area limit (since 0.8.0).** An area (`--bbox`, `--sheet`, `--geometry`)
that would download more than **100 files** or more than **10 GB** ends
with an `Error:` (code 2) before the download: the message gives the number of
files, their size (the sum from `HEAD` or from the ATOM feed; above 100 files —
an estimate from 5 files) and what to do — narrow the area, choose a unit
(`--teryt`, `--ku`) or run a plan with part of the items (`--check
--plan PLIK`, edit the file, then `--upgrade --plan PLIK`). Only
files to be downloaded count: versions already local do not (with `--force` — all).
Choosing a unit (`--teryt`, `--ku`) and `--whole-country` have no limit —
the size of a large file appears as a `Warning:` before the transfer. The limit
applies to all collections, also ZABAGED, BDOO, Data50 and Data250
in `landcover`, the BDOT10k area (county packages, current and from the archive) and
NMT 100 m (voivodeship files of the area).

```bash
kartograf models3d download --product trees --country pl --bbox 560000,240000,575000,250000 --root ~/kartograf-data
#   Info: trees: powiaty obszaru wg PRG (2): 1206, 1261
#   Error: trees: obszar daje 2 pliki do pobrania, razem ok. 13,7 GB wg HEAD - limit jednego zadania to 100 plikow i 10 GB. Zawez obszar (--bbox, --sheet, --geometry), wybierz jednostke (--teryt <4 digits>) albo wykonaj plan z czescia pozycji (--check --plan PLIK, potem --upgrade --plan PLIK)
```

### 1.9 CZ data: ZABAGED, Data50, Data250, RUIAN and HY-NET

CUZK vector data (since 0.8.0, ADR-042 D15–D17) has the shape of the collections
from section 1.8: an `--bbox`/`--geometry` area yields one GeoPackage of features
intersecting the area, with full geometries (no clipping), always
in the service CRS **EPSG:5514** (S-JTSK); `--whole-country` writes the
CUZK national file 1:1, and its size appears as a `Warning:` before the
transfer. A sheet code as the area and `--teryt` apply to PL only — give a CZ area
as a rectangle or a geometry file. EPSG:5514 coordinates are
negative in Czechia: `--bbox -460000,...` and `--bbox=-460000,...` work the same.

```bash
# ZABAGED (landcover): 22 land cover and water layers of the area, EPSG:5514
kartograf landcover download --product zabaged "--bbox=-460000,-1120000,-450000,-1110000" --bbox-crs EPSG:5514 --root ./data
#   Info: zabaged: wynik obszaru ma 22 warstwy pokrycia terenu i wod; pelna baza ZABAGED jest w pliku krajowym: --whole-country --horizontal-crs EPSG:5514|EPSG:3045
#   -> landcover/cz_zabaged/bbox/-460000_-1120000_-450000_-1110000.gpkg
kartograf landcover list-layers --product zabaged
# ZABAGED national file (5.8 GB in EPSG:5514 or 6.7 GB in EPSG:3045) — only deliberately
kartograf landcover download --product zabaged --whole-country --horizontal-crs EPSG:5514 --root ~/kartograf-data
#   Warning: zabaged CZ: plik krajowy https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-5514/ZABAGED-5514-gpkg-20261004.zip - 5805826649 B (ok. 5806 MB)
#   -> landcover/cz_zabaged_gpkg_5514/country/cz.zip (wersja 2026-10-04_<sha8>)

# Data50 and Data250 (landcover): all feature layers of the area model
# (69 / 116 layers), EPSG:5514; bbox in EPSG:4326 -> its envelope in EPSG:5514
kartograf landcover download --product data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326 --root ./data
#   landcover/cz_data50/bbox/-450998.7179_-1112011.026_-450531.4728_-1111532.273.gpkg: nowa wersja 2026-10-16_7000764f
kartograf landcover list-layers --product data250
# SHP national file (Data50: 516 MB in EPSG:5514 or 757 MB in EPSG:3045; Data250: 230/320 MB)
kartograf landcover download --product data250 --whole-country --horizontal-crs EPSG:5514 --root ./data
#   Warning: data250 CZ: plik krajowy https://openzu.cuzk.gov.cz/opendata/Data250/epsg-5514/data250.zip - 230485722 B (ok. 230 MB)
#   landcover/cz_data250_shp_5514/country/cz.zip: nowa wersja 2026-05-12_ae501843
kartograf landcover download --product data250 --whole-country --horizontal-crs EPSG:5514 --check --root ./data
#   landcover/cz_data250_shp_5514/country/cz.zip: aktualne (2026-05-12)

# RUIAN (boundaries --country cz): units of the --level level intersecting the area
kartograf boundaries download --product admin --country cz --level obec "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 --root ./data
#   -> boundaries/cz_ruian_obec/bbox/-470000_-1130000_-440000_-1100000.gpkg (warstwa Obec)
# border area: separate PRG (EPSG:2180) and RUIAN (EPSG:5514) files, level per country
kartograf boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox 18.5,49.6,18.8,49.9 --bbox-crs EPSG:4326 --root ./data
#   -> boundaries/pl_prg_gmina/bbox/<coords EPSG:2180>.gpkg i boundaries/cz_ruian_obec/bbox/<coords EPSG:5514>.gpkg
kartograf boundaries download --product admin --country cz --whole-country --root ./data
#   -> boundaries/cz_ruian_shp/country/cz.zip (SHP, ok. 251 MB)

# HY-NET (hydro): watercourse segments and nodes of the area, EPSG:5514
kartograf hydro download --product network --country cz "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 --root ./data
#   Info: network: wynik obszaru bez skrzyzowan bezkolizyjnych (typ WatercourseSeparatedCrossing: relacje odcinkow bez geometrii, usluga nie liczy ich w obszarze) - sa w pliku krajowym: --whole-country --country cz
#   -> hydro/cz_hynet/bbox/-470000_-1130000_-440000_-1100000.gpkg (warstwy WatercourseLink, HydroNode)
kartograf hydro download --product network --country cz --whole-country --root ./data
#   -> hydro/cz_hynet_gpkg/country/cz.zip (HY-NET.gpkg w EPSG:3045, ok. 194 MB)
kartograf hydro download --product network --country cz --whole-country --check --root ./data

# Geomorphological units of CZ: the --level level is required for an area
kartograf boundaries download --product geomorphology --country cz --level celek "--bbox=-452000,-1112000,-450000,-1110000" --bbox-crs EPSG:5514 --root ./data
#   boundaries/cz_geomorphology_celek/bbox/-452000_-1112000_-450000_-1110000.gpkg: nowa wersja 2026-10-16_c7facb92

# Cadastral map of CZ: cadastral area package (--ku, 6 digits) or the KU of the area
kartograf cadastre download --product map --ku 623164 --format SHP --root ./data
#   cadastre/cz_cadastral-map_shp/ku/623164.zip: nowa wersja 2026-10-16_aaee5b70
kartograf cadastre download --product map --country cz --format SHP "--bbox=-452000,-1112000,-450000,-1110500" --bbox-crs EPSG:5514 --root ./data
#   Info: map: katastralni uzemi obszaru wg RUIAN (3): 652954, 696137, 753521
#   cadastre/cz_cadastral-map_shp/ku/652954.zip: nowa wersja 2026-10-16_223d7ce9 (i dwa kolejne KU)
kartograf cadastre download --product map --country cz --format SHP "--bbox=-452000,-1112000,-450000,-1110500" --bbox-crs EPSG:5514 --check --root ./data
#   cadastre/cz_cadastral-map_shp/ku/652954.zip: aktualne (2026-10-16)   (tak samo 696137 i 753521)
kartograf hydro list-sources
```

**ZABAGED.** `--product zabaged` yields 22 layers of land cover
and hydrography of the `ZABAGED_POLOHOPIS` REST service (list: `landcover
list-layers --product zabaged`), among others `vodni_tok` and `brehova_cara`
(lines), `vodni_plocha`, `orna_puda_a_ostatni_dale_nespecifikovane_plochy`,
`trvaly_travni_porost`, `lesni_puda_se_stromy`,
`budova_jednotliva_nebo_blok_budov_plocha` (polygons). The GPKG layer name
is the service layer name without diacritics, in lower case; the layer description
(`gpkg_contents.description`) is the service name with the id, e.g. `Vodní tok (93)`.
Kartograf **does not convert ZABAGED classes to BDOT10k codes** (PT*, SW*):
the consumer determines the equivalents (the table of equivalents from the reconnaissance of
2026-08-10 contains errors). `--whole-country` requires `--horizontal-crs
EPSG:5514` or `EPSG:3045` (the file is published in two CRSs)
and writes the CUZK national ZIP 1:1 (inside `ZABAGED_RESULTS.gpkg`;
Kartograf does not unpack it). The layers of the national file are the full database under
CUZK names (e.g. `VodniPlocha_c`, `TrvalyTravniPorost_c`) — **different from the
layer names of the area result**; every area download reminds you of this
with an `Info:` line (`Notice` `area_omitted`). The area result is always in EPSG:5514
(`--horizontal-crs` with an area = `Error:`); `--teryt`, `--sheet`,
`--format`, `--layers`, `--keep-raw` and `--year` with `--product zabaged` are
`Error:`. The national file has a release from the ATOM feed (label e.g.
`2026-10-04`): `--check` compares it without downloading, `--upgrade`
downloads the new release.

**Data50 and Data250.** `--product data50` and `--product data250` are the CUZK digital
geographic models at scales 1:50,000 and 1:250,000. An area yields one
GeoPackage with **all feature layers** of the REST service
`DATA50`/`DATA250` (69 and 116 layers; list: `landcover list-layers
--product data50`; the Data250 relief rasters are not area data), layer names
as in ZABAGED (CUZK name without diacritics, e.g. `vodni_tok`, `les`,
`louka_pastvina`), without conversion to BDOT10k codes; an empty layer stays
with its schema. `--whole-country` with `--horizontal-crs EPSG:5514` or
`EPSG:3045` writes the national ZIP with Shapefile files 1:1 (Data50: directory
`shp/`, Data250: `DATA250_<year>_SHP/`; the layer names of the national file are
different from the layers of the area result, e.g. `Akvadukt.shp`, `AirfldA.shp`), with a
release from the ATOM feed (`--check` without downloading). The remaining rules
are as for ZABAGED: the area result is always in EPSG:5514, `--teryt`, `--sheet`,
`--year`, `--layers`, `--format` and `--keep-raw` are `Error:`.

**RUIAN.** `boundaries download --product admin --country cz` requires `--level`
for an area: `kraj`, `okres`, `obec` or `katastralni-uzemi`
(GPKG layers `VyssiUzemneSamospravnyCelek`, `Okres`, `Obec`,
`KatastralniUzemi`; among others the fields `kod` and `nazev`). Under `--country auto`
an area at the border yields two files (PRG and RUIAN) with a shared
`extra.parent_request`; the levels of the countries differ, so give them per
country (`--level pl=gmina,cz=obec`; library: `{"pl": "gmina", "cz":
"obec"}`) — a single value unavailable in one of the countries is an `Error:`
with the hint `--level pl=<level>,cz=<level>`. `--whole-country
--country cz` is the national SHP (approx. 251 MB) with an `ETag`: by default the local
version is used without a request (section 4.3), `HEAD` is done only by
`--check` (`aktualne` or `nowsza`) and `--upgrade`.

**`--country auto` in collections.** Country envelopes are rectangles, so
an area deep inside one country (e.g. Cieszyn on the Polish side) also falls
into the other, where the source has no data for it (no cadastral area
in RUIAN, map sheet, features). Such a part is an error of that country — an entry
in `failed` (`kind` `no_coverage` or `download`; `unit` = country code when
the units could not be determined) and an `Error:` line — but the other country is
downloaded, and the task ends with code 0 with a `Warning:`
`auto_partial_success` (the same rule as in `elevation` and `imagery`;
`--check`: `Warning:` `check_failed` and `auto_partial_success`).
Code 1 is kept for an explicit `--country` and for the failure of all countries
(no units in either = `no_coverage`). A project task with a partial
success is not pinned.

**HY-NET.** The `hydro` group (`--product network`; CZ only — `--country pl`
is an `Error:`, and `auto` narrows to CZ with an `Info:`) downloads the INSPIRE hydrographic
network from the CUZK WFS. The area result has **2 layers**:
`WatercourseLink` (watercourse links) and `HydroNode` (network nodes). The type
`WatercourseSeparatedCrossing` (watercourse crossings) is not covered by the area:
there is no geometry in the GML (it is a relation of two links), and the service
for a BBOX query reports 0 features although it returns them (30 x 30 km:
0 versus 4) — completeness cannot be verified; the crossings are in the national
file, as reminded by the `Info:` line of every area download
(`Notice` `area_omitted`, like the census circuits of the PRG special boundaries).
The layer fields come from the response content (the service schema is only
a reference to the remote INSPIRE schema), so the same type can
have different fields in another area (a page with a single node has no
`hydroNodeCategory`); a layer without features has only the `gml_id` field. The national
file (`--whole-country --country cz`, approx. 194 MB) is a ZIP with
`HY-NET.gpkg` in **EPSG:3045** (ETRS89 / UTM 33N) — in a different CRS than the
area result (EPSG:5514); the sidecar gives the actual CRS, and there is no other
CRS of the file (`--horizontal-crs` is unnecessary). The file has an `ETag`:
`--check` reports `aktualne` or `nowsza`. The service redirects the
default `User-Agent` of `curl` to a PDF with the terms of use —
Kartograf sends its own (`kartograf/<version>`).

**Geomorphological units.** `boundaries download --product
geomorphology --country cz` requires `--level` for an area: `subprovincie`,
`oblast`, `celek`, `podcelek`, `okrsek`, `podokrsek` or `cast` (without
`--level` an `Error:` with the list). The result is one GeoPackage in EPSG:5514
with the units of that level intersecting the area (full geometries);
measurement: a 2 x 2 km area gave 1 feature of level `celek`, and a 20 x 20 km area
9 features of level `okrsek`.
The product has no national file or `--teryt`.

**CZ cadastral map.** `cadastre download --product map --country cz`
downloads a CUZK cadastral area (KU) package in the `--format` format
(`SHP`, `DXF`, `DGN` or `VFK`; ZIP written 1:1, format = a separate segment
of the store `cadastre/cz_cadastral-map_<format>/ku/`). `--ku` (6 digits) selects one KU
(with `--country pl` it is an `Error:`); an `--bbox`/`--geometry` area yields the package of
every KU of the area according to RUIAN (with an `Info:` list of KUs). A missing `--format` is an
`Error:` with the list of formats. A KU without a package (e.g. 999999) ends with
`Error: ... (HTTP 404)`, and the remaining KUs of the task are saved. The packages have an
HTTP signal: the next run uses the local version without a request
(`HEAD` is done only by `--check` and `--upgrade`: `aktualne` or
`nowsza`). The KUs of an area from RUIAN are kept in the metadata cache (TTL 7 days; `--force`,
`--upgrade` and `--check` query the service), so repeating the area
works without a network.
The VKM format (cadastral exchange) is not supported: its address
returns 404 for KU 623164 (state 2026-10-16).

**Freshness and size.** Area features (ZABAGED, RUIAN, HY-NET) have
no cheap change signal: local version without requests, `--check`
= `nie da sie sprawdzic bez pobrania`, new content — `--force`. The area result
is assembled in memory (the whole layer at once): a 30 x 30 km area
is thousands of features per ZABAGED layer (reconnaissance of 2026-10-15: 4979
watercourse links), for a whole country use the national file. Details:
ARCHITECTURE 4.8 and 4.10, [ADR-042](DECISIONS.md) erratum 2–3.

### 1.10 Geographic names and topographic maps

`names download` downloads `--product geographic`: PRNG RP for `--country pl`
or Geonames for `--country cz`; `--product world --country pl` means
**Polish geographic names of the world**, not clipping the area to Poland.
An area (`--bbox`, `--sheet` or `--geometry`) yields a GPKG with the full geometries
of features intersecting the area: PRNG in OGC:CRS84 (longitude, latitude), Geonames
in EPSG:5514 (25 layers). A PRNG query takes approx. 80–95 s per page of features
(measured 2026-10-16) — it is preceded by `Info: geographic: zapytanie OGC API
PRNG - usluga odpowiada ...` (only `geographic`; `world` responds in a few
seconds); for the complete dataset use `--whole-country`.
Area results have no cheap update signal; use `--force`
to refresh them.

```bash
kartograf names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326 --root ~/kartograf-data
kartograf names download --product world --country pl --bbox=-74.02,40.69,-73.92,40.79 --bbox-crs EPSG:4326 --root ~/kartograf-data
kartograf names download --product geographic --country cz --bbox=-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514 --root ~/kartograf-data
kartograf names download --product geographic --country pl --whole-country --format SHP --root ~/kartograf-data
kartograf names download --product world --country pl --whole-country --format GML --root ~/kartograf-data
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 --root ~/kartograf-data
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 --check --root ~/kartograf-data
```

PRNG RP has **two** country files (`miejscowosci`, `obiekty-fizjograficzne`:
`country/pl_miejscowosci.zip`, `country/pl_obiekty-fizjograficzne.zip`);
the Polish names of the world have one (`pl_swiat.zip`). GUGiK formats: `GML`, `SHP`,
`XLSX` (original ZIP archives). Geonames: `GPKG` or `FGDB` in
`EPSG:5514`/`EPSG:3045`, with an explicit `--horizontal-crs` required; the country file is
the original ZIP from the CUZK ATOM feed, and the release date is the version label and the
`--check` signal. A warning about their size appears before
country files are downloaded.

`maps download --product topographic` downloads BDOT10k visualisation sheets
(`--country pl`, scales `1:10000`, `1:25000`, `1:50000`, `1:100000`, formats
`TIFF` and `PDF`) or ZTM CUZK (`--country cz`, scales from `1:5000` to
`1:250000`). Both `--scale` and `--format` are required. The BDOT10k sheets
are ready-made TIFF/PDF files, not the BDOT10k vector database; the `Stan bazy` date from
the index is the version label and the update signal. For ZTM, `TIFF`, `DGN`
and `SHP` remain original ZIPs, and `PDF` has the `.pdf` extension.
`S-JTSK` allows `TIFF`, `PDF`, `DGN`, `SHP`; `ETRS89` — only `TIFF` and
`PDF`. The `sjtsk`/`etrs89` sheet system follows from the sheet code; `--sheet-system`
is required with ZTM `--bbox`/`--geometry` and applies to CZ only (BDOT10k
maps have PL-1992 sheets — with `--country pl` the flag gives `Error:`, under
`--country auto` it applies to the CZ part). ZTM checks `ETag`/`Last-Modified`
from `HEAD` without downloading data. A sheet lies in the sheet code hierarchy like any
sheet in the store: `maps/cz_ztm_10000_sjtsk_tiff/0510/D/11/0510-D-11.zip`,
`maps/cz_ztm_10000_etrs89_pdf/NM-34/07/1/D/15/NM-34-07-1-D-15.pdf`.

```bash
kartograf maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF --root ~/kartograf-data
kartograf maps download --product topographic --country pl --sheet M-34-064 --scale 1:100000 --format PDF --root ~/kartograf-data
kartograf maps download --product topographic --country cz --sheet 0510-D-11 --scale 1:10000 --format TIFF --root ~/kartograf-data
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF --root ~/kartograf-data
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF --check --root ~/kartograf-data
kartograf maps list-sources
kartograf names list-sources
```

The CLI and API have the same validation, `Notice`, statuses and store layout
`data/names/` and `data/maps/`. The commands are also suitable for a manifest
(`kartograf project add <name> names download ...` /
`kartograf project add <name> maps download ...`); the data directory
then comes from the project.

### 1.11 3D mesh, trees, geodetic control networks and quasi-geoids

`models3d download` has, besides buildings (section 1.8), two GUGiK products
(PL only). `--product mesh` is city mesh models: GUGiK index tiles
intersecting the area (`--bbox`/`--sheet`/`--geometry`), each as an
original ZIP (OBJ, MTL and JPG textures, approx. 40–60 MB). A tile is the file
of a single index record — the same module may appear in several works (e.g. mesh
from photos and from scanning), so you get both versions as separate files;
`--year R` keeps tiles from year R data. The file lies in the record's layout directory
(`1992` or `2000/<zone>`, e.g. `2000/7` = PL-2000 zone 7, like the
first component of the PL-2000 sheet code): the OBJ has the coordinates of that
zone (E with the zone prefix) and PL-EVRF2007-NH heights (sidecar
`horizontal_crs`, `vertical_crs` EPSG:9651). The version label is the date
and the work report number from the record, so `--check` compares a tile
with the index without downloading. The area of a large city is hundreds of tiles — above
100 tiles the task ends with `Error:` with the count and estimated size
(area limit, section 1.8). `--product trees` is CityGML LoD1 tree models
(2023 release, GML files of 1:500 sheets in EPSG:2180 without a vertical
CRS): a county package (`--teryt`) or the county packages of the area,
0.3–25 GB each; `--lod 1` and `--year 2023` can be omitted (any other value is
`Error:`), not every county has a package (`Error: <TERYT>: ... (HTTP 404)`).

```bash
kartograf models3d download --product mesh --country pl --bbox 566200,244650,566250,244700 --root ~/kartograf-data
#   Info: mesh: kafle obszaru (1): 2000/7/78944_6777_74230_55482
#   models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip: nowa wersja 2021-10-03_DFT.7201.043.2023_7950f585
kartograf models3d download --product mesh --country pl --bbox 566200,244650,566250,244700 --check --root ~/kartograf-data
#   models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip: aktualne (2021-10-03_DFT.7201.043.2023)
kartograf models3d download --product trees --teryt 3063 --root ~/kartograf-data
#   Warning: trees PL 3063: duzy plik https://opendata.geoportal.gov.pl/InneDane/Drzewa3D/LOD1/2023/30/3063.zip - 324674789 B (ok. 325 MB)
#   models3d/pl_trees_lod1_2023/teryt/3063.zip: nowa wersja 2023_25a77518
```

`geodesy download --product control` downloads geodetic control points.
`--network` is required: PL `horizontal`, `vertical`, `gravity`,
`magnetic` (GUGiK horizontal, vertical, gravimetric and magnetic
networks; magnetic also isogonic zones), `archive-1942`,
`archive-kronsztadt60` (archival point catalogues); CZ `gnss` (CZEPOS
stations), `horizontal`, `densification` (ZhB), `horizontal-detailed`,
`vertical`, `vertical-detailed`, `gravity` (CUZK Bodove pole). An area yields
one GeoPackage of network points (PL: layers `fundamentalna_*`
and `bazowa_*` in EPSG:2180; CZ: network layers, e.g. `bod_zvbp`, in EPSG:5514 —
a CZ network is the sum of its layers, including points determined in ETRS89).
`--teryt` (county) yields a package of the `horizontal` or `vertical` network: coordinate
lists (XLS) and topographic descriptions (JPG). The archives are scans (PDF,
TIFF) of 1:100 000 sheets: `--sheet` of any scale or an area selects
the 1:100 000 sheets of its extent (the 1942 archive can exceed 1 GB — the size
is in a `Warning:` before the transfer). A network without county packages with `--teryt` gives
`Error:` pointing to the area. Under `--country auto` a single `--network`
value applies to both countries (common: `horizontal`, `vertical`,
`gravity`), and different networks are given per country like `--level`:
`--network pl=horizontal,cz=gnss` (library: `network={"pl":
"horizontal", "cz": "gnss"}`); the error lists the values of each country.

`geodesy download --product geoid` is a quasi-geoid model as a single
country file, only with `--whole-country`: `--country pl` — PL-geoid2021 for
PL-EVRF2007-NH (TXT: latitude, longitude, zeta in ETRF2000-PL, grid
0.01°, 42 MB), `--country cz` — QGZU-2013 (ZIP of 17 TXT grids for Bpv
heights, 58 MB; the release date from the ATOM feed is the label and the
`--check` signal). An area gives `Error:`. Kartograf downloads the models
as data and does not apply them to other data.

```bash
kartograf geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000 --root ~/kartograf-data
#   geodesy/pl_control_vertical/bbox/560000_240000_575000_250000.gpkg: nowa wersja 2026-10-16_1272d195
kartograf geodesy download --product control --network horizontal --teryt 1201 --root ~/kartograf-data
#   geodesy/pl_control_horizontal_xls/teryt/1201.zip: nowa wersja 2026-10-16_fa3dc40c
kartograf geodesy download --product control --network gravity --teryt 1201 --root ~/kartograf-data
#   Error: --network gravity: control (PL) - dostepne tylko dla --bbox/--sheet/--geometry (obiekty obszaru); dla --teryt: horizontal, vertical
kartograf geodesy download --product control --network archive-kronsztadt60 --sheet M-34-064-D --root ~/kartograf-data
#   Info: control: arkusze (1): M-34-64
#   geodesy/pl_control_archive-kronsztadt60/M-34/64/M-34-64.zip: nowa wersja 2026-10-16_8211a8dc
kartograf geodesy download --product control --country cz --network vertical "--bbox=-452000,-1113000,-449000,-1110000" --bbox-crs EPSG:5514 --root ~/kartograf-data
#   geodesy/cz_control_vertical/bbox/-452000_-1113000_-449000_-1110000.gpkg: nowa wersja 2026-10-16_b921641a
kartograf geodesy download --product control --country auto --network vertical --bbox 18.55,49.70,18.70,49.78 --bbox-crs EPSG:4326 --root ~/kartograf-data
#   -> geodesy/cz_control_vertical/bbox/<coords>.gpkg i geodesy/pl_control_vertical/bbox/<coords>.gpkg (obszar w EPSG:5514 i EPSG:2180)
kartograf geodesy download --product geoid --country pl --whole-country --root ~/kartograf-data
#   Warning: geoid PL: plik krajowy https://opendata.geoportal.gov.pl/InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt - 42328086 B (ok. 42 MB)
#   geodesy/pl_geoid2021_evrf2007/country/pl.txt: nowa wersja 2026-10-16_d695cf81
kartograf geodesy download --product geoid --country cz --whole-country --root ~/kartograf-data
#   geodesy/cz_qgzu2013_bpv/country/cz.zip: nowa wersja 2021-02-22_aacfba6b
kartograf geodesy list-sources
```

Control points, packages, archives and PL-geoid2021 have no cheap freshness
signal (`--check`: `nie da sie sprawdzic bez pobrania`; new
content with `--force`). The `models3d download` and `geodesy download` commands
are suitable for a manifest (`kartograf project add <name> geodesy download
--product control --network horizontal --teryt 1201`).

### 1.12 Plain files or the store (`--output-dir`, `--root`)

Every data command (`elevation`, `imagery`, `landcover`, `soil`, `soil hsg`, `boundaries`,
`cadastre`, `models3d`, `hydro`, `names`, `maps`, `geodesy` `download`) writes in one of two
ways (ADR-054, Nogat DEV §19):

| Flag | Library | Writes |
|---|---|---|
| `-o`, `--output-dir DIR` | `output_dir=` | plain files named as in the store, flat, in `DIR` (created when missing) |
| `--root DIR` | `root=` | the versioned store: `versions/`, sidecars, the hard-linked standard path |
| neither | neither | the store at the first of `KARTOGRAF_ROOT`, `[kartograf] root` of `nogat.toml` and `<data_dir>/kartograf` (section 10) |

`--output-dir` and `--root` exclude each other (`validation_error`, `details.reason`
`exclusive_options`). The commands whose input is the store, every `project` command and
`store init`, take `--root` only.

```bash
# plain files: one NMT sheet as ./dem/N-34-130-D-d-2-4.asc and nothing else
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./dem
# the same call again is a conflict (exit 4) before anything is fetched; --force replaces the file
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./dem --force
# the plan: write, replace (with --force) or conflict for each target; exit 0 even with conflicts
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./dem --check
# the versioned store of a place of your choice, and of the default place
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --root ./data
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007
```

**Plain mode.**

- *Names.* A file has the name it has in the store: `<sheet>.<ext>` (`N-34-130-D-d-2-4.asc`),
  `<unit><ext>` for a package (`0208.zip`, `1465.gpkg`), `<coordinates>.tif` for a SoilGrids layer
  and the HSG raster, `<sheet>.laz` for a CZ point cloud. There is no sidecar, no `versions/`, no
  standard path, no `full_sheet/` and no hard link, so a plain write works on FAT, exFAT and SMB.
  `landcover download --keep-raw` writes `<teryt>.gpkg` and the original `<teryt>.zip`.
- *Before the first request* the directory is looked at: one that is, or lies in, a store of
  Kartograf or IMGWTools is `conflict` (`output_in_store`, `details.paths` the directory, the hint
  names `--root`), and nothing is asked of the source.
- *Before the first byte* the whole list of targets is checked, and a failure writes nothing:
  a name two files share is `conflict` (`duplicate_output_name`), a subdirectory that a unit
  would enter and that holds a store marker is `conflict` (`output_in_store`), an existing file
  without `--force` is `conflict` (`output_exists`). The error lists every path in
  `details.paths`. A request over two countries (`--country auto`) is checked as one list.
- *Writing.* Each file goes to `DIR/.kartograf-incoming/<host>_<pid>_<token>/`, is verified
  there and moves into place with `os.replace`; the staging directory is removed after success,
  error, Ctrl-C (exit 130) and SIGTERM (exit 143), and leftovers older than 24 hours are removed
  by the next run. `--force` replaces each existing target atomically and deletes nothing else.
- *Plan.* `--check` lists each target as `do zapisania` (write), `do zastapienia (--force)`
  (replace, only with `--force`) or `konflikt: ...` (conflict); `--lang en` prints `to write`,
  `to replace (--force)` and `conflict: ...`. `--check --force` is a valid pair.
  A plain plan fetches no data and asks no freshness signal; with `--root` the `--force` of a
  plan has no effect. A file whose source cannot be asked (an unreachable sheet index) is
  `nie udalo sie sprawdzic: ...` (`could not check: ...`), status `check_failed` with no action,
  as in the store: the plan is not `ok` and exits 11 (10 beside files that are fine), as the run.
- *Options that need a store.* `--upgrade`, `--plan` and `--all-campaigns` with `--output-dir`
  are `validation_error` (`store_only_option`) and name `--root`; `--full-sheet` is an `info`
  notice (it has no effect). The year options filter the flights as in the store.
- *PL sheets (NMT, NMPT, orthophotomaps) take the newest FULL flight, not the newest flight.* A
  file without a sidecar cannot say it is partial, so a plain sheet comes from the newest flight
  declared full within the year range. A sheet that has flights and none of them full is
  skipped: the warning `skipped_incomplete` names it (with the hint `--root`, which takes the
  newest flight, partial or not) and `skipped[]` of the result lists `{id, reason, message}`;
  the other sheets are written. When every sheet is skipped the command fails with `no_data`
  (`skipped_incomplete`, exit 11 as a result, 14 as an error of the plan).
- *HSG.* `soil hsg --output-dir` fetches the clay, sand and silt inputs into the staging
  directory and writes only the HSG raster; `inputs[]` is empty and nothing is reused.
- *Result.* `files[]` = `{unit, country, path, size_bytes, sha256, status}` with the status
  `written` or `replaced`; the report has `mode` `plain`, `root` `null` and `output_dir`. The
  summary line is `Zapisane: N, zastapione: M, bledy: K (DIR)` (`Written: N, replaced: M,
  errors: K (DIR)` with `--lang en`). Per-unit outcomes stay in `items[]` of the envelope.
- *MCP.* `output_dir` is a path of the call like `root`: absolute and inside `--allow-dir`
  (`forbidden`, `outside_allowed_dirs`). A call that names neither target needs the default
  store inside `--allow-dir`. `check` with `update=force` plans the replacement on a server that
  writes; a server that does not write answers `forbidden` (`writes_disabled`) to every option
  of a run.

**A store root that cannot be written** is the error of the command, before any request, in
every data command and in `project download`, and not a failed unit of each sheet or file: a
root that has the layout of a store and no `kartograf-store.json` is `store_unavailable`
(`no_marker`, exit 8, the hint is `kartograf store init --root DIR`), a root that holds other
files is `conflict` (`not_empty`, exit 4), and a root that lies in, holds or has below it a
store of Kartograf or IMGWTools is `conflict` (`nested_store`, exit 4). `--check` lists a root
that is a `conflict` as the one position of the track `store` (`action` `conflict`, `reason`,
the root as `path`): the plan is `ok`, exits 0 and asks nothing; the plan of a root without its
marker fails as the run does (exit 8). An `output_dir` that is, or lies in, a store is refused
the same way (`output_in_store`).

The reasons of the errors above are listed in 9.3 and in the migration guide of the CHANGELOG.

---

## 2. Python library

Every CLI command has one library function with the same choices
(parameter names = flag names in `snake_case`) and the same result
(ADR-037): `kartograf elevation download` and `kartograf imagery download` =
`download_data`/`check_data`, `landcover download` =
`download_landcover`/`check_landcover`, `soil download` =
`download_soil`/`check_soil`, `soil hsg` = `calculate_hsg`/`check_hsg`,
`elevation availability` = `check_availability`,
`boundaries download`, `cadastre download`, `models3d download`, `hydro
download`, `names download`, `maps download` and `geodesy download` =
`download_collection`/`check_collection`. An input error
is a `ValidationError` with the text as after `Error:` in the CLI; messages about data
(CLI: `Info:`/`Warning:`) are a `Notice` in the result's `notices` field and via
`on_notice`.

```python
from kartograf import BBox, check_data, download_data

# = kartograf elevation download --product nmt --bbox 18.60,49.73,18.66,49.76
#   --bbox-crs EPSG:4326 --country auto --resolution pl=1m,cz=2m
#   --vertical-crs pl=EVRF2007,cz=Bpv --cutout --horizontal-crs EPSG:3045 --root ./data
selection = dict(
    product="nmt",
    root="./data",
    bbox=BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326"),
    country="auto",
    resolution={"pl": "1m", "cz": "2m"},     # single value: resolution="1m"
    vertical_crs={"pl": "EVRF2007", "cz": "Bpv"},
    cutout=True,                             # one cutout per country
    horizontal_crs="EPSG:3045",
)
report = download_data(**selection, on_notice=lambda n: print(n.level, n.message))
for item in report.files:                    # UnitFile(unit, country, file)
    print(item.country, item.unit, item.file.path, item.file.status)
for failure in report.failed:                # UnitFailure(unit, country, error, kind)
    print(failure.country, failure.error)
print(report.ok)  # CLI exit code: True = 0 (also auto partial success)

plan = check_data(**selection)               # = --check, without downloading
report = download_data(**selection, update="upgrade", plan=plan)  # = --upgrade --plan
```

Availability report (section 1.7) — sheet index and PRG mask, without downloading
data; result `AvailabilityReport` (`request`, `checked_at`, `areas`:
`AvailabilityArea`, `combinations`: `AvailabilityCombination`, `failed`:
`UnitFailure` of a country that was not checked, `notices`, `ok`), `to_json()` =
the `--json` output:

```python
from kartograf import BBox, check_availability, download_data

# = kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
report = check_availability(
    product="nmt",                                   # "nmt" | "nmpt" | "laz"
    country="pl",                                    # required with bbox=/geometry=
    bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
    min_year=2020,                                   # optional; also year=, max_year=
)                                                    # cache=True, force=False, on_notice=
land = report.areas[0].land_m2
for c in report.combinations:                        # year, descending
    print(c.year, c.horizontal, c.resolution, c.vertical_crs, c.format,
          c.complete, len(c.sheets_full), len(c.sheets_partial), c.uncovered_m2)
    print(f"  pełne arkusze: {int(c.full_m2 * 100 // land)}% lądu")  # KD-2, rounded down
    one = [k.campaign for k in c.campaign_coverage if k.complete]  # KD-1
    taken = {r.campaign for r in c.sheet_records if r.full_sheet and r.campaign}
    print("  sama kampania:", one, "kampanie pobrania:", sorted(taken))
newest = next((c for c in report.combinations if c.complete), None)
if newest is not None:
    print(newest.source, newest.download_hint)     # e.g. "pl.gugik.nmt_1m", ("elevation download ...",)
    # combination as download_data arguments (PL-2000: also scale=,
    # the scales are given by download_hint)
    download_data(product="nmt", root="./data", country="pl",
                  bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
                  sheet_system=newest.horizontal.removeprefix("PL-"),
                  format=newest.format, resolution=newest.resolution,
                  vertical_crs=newest.vertical_crs, year=newest.year)
text = report.to_json()                              # kartograf-availability/1
```

The registry of NMT/NMPT/LAZ variants (ADR-041; data without IO) replaces the provider constants removed
in 0.8.0 (`SUPPORTED_RESOLUTIONS`, `WFS_ENDPOINTS`,
`nmt_vertical_crs()`, etc.):

```python
from kartograf.sources.variants import variants

for v in variants(product="nmpt", country="PL"):
    print(v.source, v.label, v.vertical_crs, v.format, v.source_file)
# pl.gugik.nmpt_0_5m 0.5m EVRF2007 ASC False ... pl.gugik.nmpt_xyz_1m 1m KRON86 XYZ True
print([v.label for v in variants(product="nmt", vertical_crs="KRON86", format="ASC")])
# ['0.5m', '1m']
```

Collections (`boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`,
`geodesy`; sections 1.8–1.11) — result `CollectionReport(files, failed, stale,
notices, ok)`, the elements of `files` and `failed` as in `DataReport`:

```python
from kartograf import BBox, check_collection, download_collection, download_landcover

out = "./data"
show = lambda notice: print(notice.level, notice.message)  # = Info:/Warning: in the CLI
# = boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000
gminy = download_collection(
    product="admin", root=out, country="pl", level="gmina",
    bbox=BBox(550000, 220000, 590000, 270000, "EPSG:2180"),
)
print(gminy.files[0].file.path)  # data/boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg
download_collection(product="admin", root=out, teryt="12")  # voivodeship package
download_collection(product="admin", root=out, country="pl", whole_country=True,
                    on_notice=show)  # Notice whole_country_size before the transfer
# = cadastre download --product map --teryt 1261 / --country pl --bbox ...
download_collection(product="map", root=out, teryt="1261")
download_collection(product="map", root=out, country="pl",
                    bbox=BBox(565000, 243000, 567000, 245000, "EPSG:2180"))
# = models3d download --product buildings --lod 1 --year 2024 --teryt 1261
download_collection(product="buildings", root=out, teryt="1261", lod=1, year=2024)
lod2 = download_collection(product="buildings", root=out, lod=2, country="pl",
                           bbox=BBox(566000, 243000, 566500, 243500, "EPSG:2180"),
                           on_notice=show,  # Notice unit_list: counties of the area
                           on_progress=lambda p: print(p.current, p.total, p.sheet, p.status))
# progress as for a sheet list (task with multiple units; CLI: progress bar, -q for no bar)
for failure in lod2.failed:  # kind "no_coverage" = no county package (HTTP 404)
    print(failure.unit, failure.kind, failure.error)
plan = check_collection(product="buildings", root=out, teryt="1261", lod=1, year=2024)
print([(i.track, i.unit, i.status) for i in plan.items])  # [("collection", "1261", "unverifiable")]
# = landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP
download_landcover(product="bdot10k", root=out,
                   teryt="1261", year=2024, format="SHP")
# = landcover download --product bdoo --teryt 12 --year 2023 --layers PTWP,SWRS
bdoo = download_landcover(
    product="bdoo", root=out, teryt="12", year=2023,
    layers=["PTWP", "SWRS"], on_notice=show
)  # data/landcover/pl_bdoo_2023_ptwp-swrs/teryt/12.zip; Notice classes_absent,
#    gdy paczka nie ma pliku którejś klasy
# = names download --product world --country pl --bbox=-74.02,40.69,-73.92,40.79
world = download_collection(
    product="world", country="pl", root=out,
    bbox=BBox(-74.02, 40.69, -73.92, 40.79, "EPSG:4326"),
)
# = maps download --product topographic --country cz --sheet 0510-D-11
map_sheet = download_collection(
    product="topographic", country="cz", root=out,
    sheet="0510-D-11", scale="1:10000", format="TIFF",
)
map_status = check_collection(
    product="topographic", country="cz", root=out,
    sheet="0510-D-11", scale="1:10000", format="TIFF",
)
# = models3d download --product mesh --country pl --bbox 566200,244650,566250,244700
mesh = download_collection(
    product="mesh", country="pl", root=out,
    bbox=BBox(566200, 244650, 566250, 244700, "EPSG:2180"),
)  # data/models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip; year= filters tiles
# = geodesy download --product control --network horizontal --teryt 1201
download_collection(product="control", root=out, teryt="1201",
                    network="horizontal")
# = geodesy download --product control --country cz --network vertical --bbox=...
download_collection(product="control", root=out, country="cz", network="vertical",
                    bbox=BBox(-452000, -1113000, -449000, -1110000, "EPSG:5514"))
# = geodesy download --product geoid --country cz --whole-country
download_collection(product="geoid", root=out, country="cz",
                    whole_country=True, on_notice=show)  # QGZU, release from the ATOM feed
# area over 100 files or 10 GB: ValidationError before the download
# (file count, size and hint; section 1.8)
```

Validation without the network (e.g. before saving a task):
`kartograf.download.collections.validate_collection_request(...)` with the same
choices (without `update`, `plan`, `workers`, `cache`, `on_notice`).

CZ orthophoto, PL orthophoto cutout and CZ data (sections 1.3, 1.4 and 1.9):

```python
from kartograf import (
    BBox, check_cz_orto_sheet, download_collection, download_cz_orto_sheet,
    download_data, download_image_cutout, download_landcover,
)

out = "./data"
show = lambda notice: print(notice.level, notice.message)
# = imagery download --product orto --country cz --sheet CTES96
report = download_data(product="orto", country="cz", sheet="CTES96", root=out)
for item in report.files:  # four sheet files: .jgw, .TM33N.jgw, .TM34N.jgw, .jpg
    print(item.unit, item.file.path.name, item.file.label)  # CTES96 CTES96.jpg 2024_2025-02-06
# = imagery download --product orto --country cz --bbox=-448500,-1113500,-446500,-1112500 --bbox-crs EPSG:5514
download_data(product="orto", country="cz", root=out,
              bbox=BBox(-448500, -1113500, -446500, -1112500, "EPSG:5514"))
# sheet track (CzOrtoResult: files, stale, notices) and a plan without downloading images
sheet = download_cz_orto_sheet(sheet="AS91", root=out)
plan = check_cz_orto_sheet(sheet="AS91", root=out)  # "cz_orto" track, four entries
# = imagery download --product orto --country pl --bbox 566000,243000,566500,243500
#   --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m
cut = download_data(product="orto", country="pl", root=out,
                    bbox=BBox(566000, 243000, 566500, 243500, "EPSG:2180"),
                    cutout=True, horizontal_crs="EPSG:2180",
                    coverage="standard", resolution="0.25m", on_notice=show)
# cutout track (ImageCutoutResult: file, stale, notices); plan: check_image_cutout
high = download_image_cutout(product="orto",
                             bbox=BBox(566000, 243000, 566200, 243200, "EPSG:2180"),
                             horizontal_crs="EPSG:2180", root=out,
                             coverage="high", resolution="0.1m")
# true orto: without coverage (single service); outside cities NoCoverageError
print(high.file.path)  # data/orto/pl_1992_high_0.1m/bbox/566000_243000_566200_243200.tif

# = landcover download --product zabaged --bbox=-460000,-1120000,-450000,-1110000 --bbox-crs EPSG:5514
area = download_landcover(product="zabaged", root=out,
                          bbox=BBox(-460000, -1120000, -450000, -1110000, "EPSG:5514"))
print(area.files[0].file.path)  # data/landcover/cz_zabaged/bbox/-460000_-1120000_-450000_-1110000.gpkg
# Available layers: kartograf landcover list-layers --product zabaged
# national file (5.8 GB): Notice whole_country_size before the transfer
download_landcover(product="zabaged", root=out,
                   whole_country=True, horizontal_crs="EPSG:5514", on_notice=show)
# = landcover download --product data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326
download_landcover(product="data50", root=out,
                   bbox=BBox(18.566, 49.757, 18.572, 49.761, "EPSG:4326"))  # 69 layers, EPSG:5514
download_landcover(product="data50", root=out,
                   whole_country=True, horizontal_crs="EPSG:5514", on_notice=show)  # SHP, 516 MB
# = boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox ...
download_collection(product="admin", root=out, country="auto",
                    level={"pl": "gmina", "cz": "obec"},
                    bbox=BBox(18.5, 49.6, 18.8, 49.9, "EPSG:4326"), on_notice=show)
# = hydro download --product network --country cz --bbox=... / --whole-country
download_collection(product="network", root=out, country="cz",
                    bbox=BBox(-470000, -1130000, -440000, -1100000, "EPSG:5514"))
download_collection(product="network", root=out, country="cz",
                    whole_country=True, on_notice=show)  # HY-NET.gpkg in EPSG:3045
```

Lower level (tracks) — the same files and sidecars as `download_data`:

```python
from pathlib import Path
from kartograf import SheetParser, DownloadManager, BBox, GugikProvider

# Parsing the sheet code and the sheet bounding box
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)                      # "1:10000"
bbox = parser.get_bbox(crs="EPSG:2180")  # or "EPSG:4326"

# Since 0.8.0 every data choice is explicit: directory, provider (product),
# vertical CRS and resolution (TypeError if missing)
# Download by sheet code -> ASC (OpenData); hierarchy: download_hierarchy()
provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager(provider, root="./data")
result = manager.download_sheet("N-34-130-D-d-2-4")
path = result.files["N-34-130-D-d-2-4"][0].version_path
# Variants from the registry (kartograf.sources.variants.variants()); a combination
# outside the registry, e.g. GugikProvider(resolution="5m", vertical_crs="KRON86"),
# -> ValidationError with a list of available labels. Archive: format="TBD" (section 1.1)

# Raw WCS outside the store (e.g. NMT KRON86 as TIFF or orthophoto;
# NMT/NMPT only the 1 m variant — provider.is_wcs_available()):
# provider.download_bbox(bbox, path) — NMT/NMPT: single-band float32 GeoTIFF
# on a 1 m EPSG:2180 grid, orthophoto: RGB from a single Standard request;
# without PRG mask and without versions. NMT/NMPT cutout in the versioned store:
# download_pl_cutout (below), orthophoto: download_image_cutout (above).
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
kron = GugikProvider(vertical_crs="KRON86", resolution="1m")
path = kron.download_bbox(area, Path("my_area.tif"))

# Land Cover: BDOT10k / CORINE and SoilGrids to the store (root = --root)
from kartograf import (
    calculate_hsg, check_hsg, check_soil, download_landcover, download_soil,
    hsg_statistics,
)
result = download_landcover(product="bdot10k", root="./data", teryt="1465")
file = result.files[0].file
print(file.path, file.status)  # data/landcover/pl_bdot10k_gpkg/teryt/1465.gpkg new
# BDOT10k for EVERY county in the area (bbox in any CRS, sheet= or
# geometry=), counties in parallel (workers=), only selected layers ->
# landcover/pl_bdot10k_gpkg_ptwp-swkn-swrm-swrs/teryt/<T>.gpkg;
# keep_raw=True: original GUGiK ZIP as a separate version in report.raw
area = download_landcover(
    product="bdot10k", root="./data",
    bbox=BBox(340000, 290000, 350000, 300000, "EPSG:2180"),
    layers=["SWRS", "SWKN", "SWRM", "PTWP"], keep_raw=True, workers=4,
)
paths = [r.file.path for r in area.files]
raw_paths = [r.file.path for r in area.raw]
print(area.ok, area.failed, area.notices)  # failed: errors of individual counties
download_landcover(product="corine", root="./data",
                   sheet="N-34-130-D", year=2018)  # CLMS or _preview
soil = dict(root="./data", sheet="N-34-130-D",
            property="clay", depth="0-5cm", stat="mean")
plan = check_soil(**soil)
download_soil(**soil, update="upgrade", plan=plan)  # only plan items

# Hydrologic Soil Groups (inputs = SoilGrids "mean" versions in the same store);
# selection: sheet=, bbox= (any CRS) or geometry= (file envelope)
hsg = calculate_hsg(root="./data", sheet="N-34-130-D", depth="0-5cm")
if hsg.files:
    print(hsg.files[0].file.status, hsg.files[0].file.label)
    stats = hsg_statistics(hsg.files[0].file.path)
print(hsg.inputs, hsg.failed, hsg.ok)
plan = check_hsg(root="./data", sheet="N-34-130-D", depth="0-5cm")

# HSG from ready-made clay/sand/silt rasters (g/kg) on an explicit grid - without downloading
from kartograf import BBox, hsg_from_rasters
hsg_from_rasters(
    Path("clay.tif"), Path("sand.tif"), Path("silt.tif"),
    bbox=BBox(501000, 596000, 503000, 598000, "EPSG:2180"),
    crs="EPSG:2180", pixel_m=100.0, output_path=Path("./hsg_100m.tif"),
)

# Merged WCS cutout of NMT or NMPT PL (GeoTIFF + sidecar)
from kartograf import check_pl_cutout, download_pl_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
selection = dict(horizontal_crs="EPSG:5514", root="./data",
                 vertical_crs="EVRF2007", product="nmpt")
result = download_pl_cutout(bbox=bbox, **selection)
print(result.file.path, result.file.status, result.masked_pixels, result.all_nodata)
for notice in result.notices:               # cutout size, cutout without data
    print(notice.level, notice.message)
# by default an existing version without PRG/WCS requests; update="force" downloads again
plan = check_pl_cutout(bbox=bbox, **selection)   # same arguments, without downloading
result = download_pl_cutout(bbox=bbox, **selection, update="upgrade", plan=plan)

# Cross-border PL/CZ catchment: splitting the area by country and a CZ cutout
# in the PL CRS (EPSG:2180 + EVRF2007); the CZ grid starts from the given area
from kartograf import download_cz_cutout, split_bbox_by_country

area = BBox(16.19, 50.42, 16.25, 50.45, "EPSG:4326")  # Kudowa-Zdrój / Náchod
parts = split_bbox_by_country(area, cz_crs="EPSG:2180")  # {"CZ": ..., "PL": ...}
cz = download_cz_cutout(
    bbox=parts["CZ"].bbox,
    product="nmt",
    root="./data",
    horizontal_crs="EPSG:2180",
    vertical_crs="EVRF2007",
    resolution="2m",          # "2m" DMR 5G / "5m" DMR 4G
)
print(cz.file.path)           # data/nmt/cz_dmr5g_evrf2007/bbox/<coords>.tif
# all_nodata=True: the CZ part has not a single valid pixel (the CZ envelope
# rectangle reaches deep into Poland) — the file is created, the flag is also in the sidecar
print(cz.all_nodata)
# Download the PL part (parts["PL"].bbox) via download_pl_cutout (above).

# CZ sheet: SM5 (ready DMR 4G 5m file or DMP OK 0.5m - resolution can be
# omitted) or TM33 tile (resolution required: NMT "2m"/"5m", NMPT "0.5m"/"2m");
# product required: "nmt" or "nmpt"
from kartograf import check_cz_sheet, download_cz_sheet

sm5 = download_cz_sheet(sheet="CTES96", root="./data", product="nmt", vertical_crs="Bpv")
tm33 = download_cz_sheet(
    sheet="302_5550", root="./data", product="nmt", vertical_crs="EVRF2007",
    resolution="2m",
)
# DMP OK, TM33 tile in EVRF2007: ready ETRS89 file (EPSG:3045) without transformation
dmp = download_cz_sheet(
    sheet="760_5518", root="./data", product="nmpt", vertical_crs="EVRF2007",
    resolution="0.5m",
)

# Check without downloading (plan kartograf-plan/1): the check_* twin with the same
# arguments as the download; the plan runs the download with update="upgrade"
plan = check_cz_sheet(
    sheet="CTES96", root="./data", product="nmt", vertical_crs="Bpv"
)
print([(i.track, i.unit, i.status) for i in plan.items])
sm5 = download_cz_sheet(
    sheet="CTES96", root="./data", product="nmt", vertical_crs="Bpv",
    update="upgrade", plan=plan,
)

# CZ LAZ: model and vertical CRS (Bpv = SM5 sheets, EVRF2007 = TM33 tiles);
# sheet code (sheet=) or area (bbox= in any supported CRS)
from kartograf import check_cz_laz, download_cz_laz

selection_cz = dict(model="dmr5g", vertical_crs="Bpv", root="./data",
                    bbox=BBox(-447000, -1114000, -444000, -1113000, "EPSG:5514"))
clouds = download_cz_laz(**selection_cz)
for file in clouds.files:                  # VersionedFile per sheet (.laz 1:1 from ZIP)
    print(file.path, file.status)
for failure in clouds.failed:              # a file failure does not stop the others
    print(failure.sheet, failure.error)
plan = check_cz_laz(**selection_cz)        # cz_laz track items, one HEAD per file
clouds = download_cz_laz(**selection_cz, update="upgrade", plan=plan)
```

**Metadata cache in the library.** Command-level and track-level functions
(`download_data`, `check_data`, `download_pl_cutout`, `download_cz_*`,
`download_laz_area`, `download_landcover`/`check_landcover`,
`download_soil`/`check_soil`, `calculate_hsg`/`check_hsg`) accept
`cache: MetadataCache | bool = True`: by default the same file as the CLI
(`<cache_dir>/kartograf/metadata.db`, TTL 7 days), `False` = no cache, a custom
`MetadataCache` = that one. `update="force"` skips cache reads in this
call (like `--force`), and the check functions (`check_data`, `check_*`)
always skip them (like `--check`). Read-only directory:
cache disabled with a `Notice` `cache_disabled`, the download continues.
A provider created manually (below) without a `MetadataCache` queries the GUGiK sheet index
on EVERY `download_sheet`; pass it a cache, and sheet queries
are limited to once per TTL:

```python
from kartograf import DownloadManager, MetadataCache, download_landcover
from kartograf.providers.pl import create_nmt_provider

manager = DownloadManager(
    create_nmt_provider(
        vertical_crs="EVRF2007", resolution="1m", cache=MetadataCache("metadata.db")
    ),  # or GugikProvider(..., cache=...)
    root="./data",
)
# Land cover: cache for a provider created by name (BDOT10k: PRG responses)
report = download_landcover(product="bdot10k", root="./data",
                            teryt="1465", cache=MetadataCache("metadata.db"))
```

**`update="force"` and the provider cache.** `force` skips reads only
from the cache that the function itself opens (the `cache` parameter
of a command-level function, also `download_landcover`): the record
is downloaded again and stored. A provider passed as a ready instance
in the lower-level API (`DownloadManager(provider, root="./data")`, the
internal `LandCoverManager(Bdot10kProvider(cache=...), root="./data")`,
`download_laz_area(..., provider=...)`) keeps ITS cache: `update="force"`
downloads the files again, but it may take sheet index records or PRG
responses from that cache (until the TTL ends). Full refresh: create the
provider with `MetadataCache("metadata.db", refresh=True)` or call
`download_data(..., update="force")`, which creates the provider itself.

The remaining elements of the public API (among others `GugikNmptProvider` —
since 0.8.0 with a required `resolution=`, e.g. `GugikNmptProvider(vertical_crs="EVRF2007",
resolution="0.5m")`, `GugikOrtoProvider`, `GugikLazProvider`/`download_laz_area`
for PL LAZ, `CuzkRasterProvider`/`create_cz_raster_provider` for CZ rasters,
`CuzkLazProvider`/`download_cz_laz` for CZ LAZ, `Parser2000`,
`ParserTM33`, `FileStorage`) — exports in `src/kartograf/__init__.py`, described
in SCOPE 2.10 and PRD 5.

**Store reading (since 0.8.0, ADR-045).** The library functions index files
without modifying them, also from an SMB share mounted read-only. `list_segments`
returns `<product>/<variant>` segments (also those unknown to the registry),
`iter_store` — an iterator of `version`, `link`, `full_sheet` and `problem`
entries (missing or bad sidecar, unknown segment, leftovers). The scan reads
only sidecars (one read per file), does not open data files and does not
`stat` every file. `list_partitions` splits a segment into disjoint parts
(sum of parts = segment scan), which can be scanned in parallel in threads
— so even the largest segment does not wait for a single thread. Already
known version directories can be skipped (`skip_versions`: their files come
back with `skipped=True` and `sidecar=None`; a set of directories — from the
version directory listing, a mapping directory → file names — even without
a listing, in which case the caller vouches for the directory contents):

```python
from concurrent.futures import ThreadPoolExecutor

from kartograf import iter_store, list_partitions, list_segments

store = "<data-dir>"
# version directories from the previous scan, relative to store, e.g.
# "nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e"
known: set[str] = set()


def scan(job: tuple[str, str]) -> list:
    segment, part = job
    return list(iter_store(store, segment=segment, partition=part, skip_versions=known))


jobs = [(s, p) for s in list_segments(store) for p in list_partitions(store, s)]
with ThreadPoolExecutor(max_workers=8) as pool:
    entries = [entry for part in pool.map(scan, jobs) for entry in part]
print(len(entries))
```

A unit scan does not list the whole segment — only the slots of the given sheet codes,
`teryt/<code>`, `bbox/<coords>`, `country/<code>`, `ku/<code>`:

```python
from kartograf import file_footprint, iter_store, link_target, read_sidecar

entries = iter_store(
    "<data-dir>",
    segment="nmt/pl_1992_1m_evrf2007",
    units=["N-34-130-D-d-2-4"],
)
for entry in entries:
    if entry.kind == "problem":
        print(entry.problem, entry.path)
    elif entry.kind == "version":
        meta = entry.sidecar or read_sidecar(entry.path)  # None when skipped
        outline = file_footprint(entry)  # no network; None = no reliable outline
        print(entry.path, meta.data_year, outline.wgs84 if outline else None)
    else:  # link, full_sheet
        print(entry.path, entry.version_path, link_target(entry.path))
```

`read_sidecar` reads a data file or a `.meta.json` path, keeps the
raw `dataset` and returns the `dataset_key` recognised in the registry
(or `None`); `data_year` is not derived from `downloaded_at`, and an
unreadable sidecar is an `InvalidSidecarError`. `describe_segment`
gives the name with variants, `known=False` for an unknown segment. The
`version_path` of a link comes from its sidecar (without reading the
data); `link_target` confirms the content — on some SMB shares it forces
a read of the whole file, so call it for the links of interest, not 50
thousand slots at once. `file_footprint` returns `native`, `wgs84`,
`source` (`request`, `sheet`, `header`, `unit`); it does not accept an
invented country outline. A file that is that area (cutout, `bbox/`) has
an outline from the task bbox (`request`); a LAZ tile selected for an
area or sheet (its `request.bbox` is the task area) has an outline from
the LAS header (`header`), and its `Sidecar.unit` is the tile's sheet
code (`extra.tile_sheet`), so `iter_store(units=[unit])` finds it. Unit
outlines from the PRG/RUIAN/SM5 indexes require `network=True` or a
previously filled `cache` (zero network queries in the default call). The
conversion to WGS84 is the pinned operation `pinned_transform`, not the
default pyproj. Cost, threads and layout variants: ARCHITECTURE 3.3.1.

**Notice codes (`Notice.code`).** The code does not depend on the notice text
(constants in `src/kartograf/notices.py`); the CLI prints `info` as `Info:`,
`warning` as `Warning:` on stderr, also with `-q` (exception: `sheet_list`).

| Code | Level | When | Commands |
|---|---|---|---|
| `sheet_list` | info | area expanded to a list of sheets before download; CLI: header on stdout, hidden by `-q` | `elevation`, `imagery download` |
| `unit_list` | info | units of a collection area before download: counties or voivodeships (PRG), sheets (maps, geodetic control archives; also sheets without a record in the index), mesh tiles, katastrální území | collections, `landcover --product bdoo` |
| `geometry_layer_default` | info | GPKG with several layers without `--layer`: the first one used | commands with `--geometry` |
| `auto_narrowed_to_pl`, `auto_narrowed_to_cz` | info | `--country auto` narrowed to one country (the product or the choice allows only that country) | `elevation`, `imagery`, collections, `elevation availability` |
| `auto_clipped`, `auto_area_outside` | info | `--country auto`: part of the area clipped to the country envelope or lying outside PL and CZ | commands with an area and `--country auto` |
| `auto_partial_success` | warning | `--country auto`: one country ended with an error, the other downloaded (exit code 0) | `elevation`, `imagery download`, collection groups with an area |
| `legacy_campaigns_dir` | info | the store contains a `kampanie/` directory from 0.7.x | `elevation`, `imagery download` |
| `newer_available` | info | the source has a newer flight, the local version used (without `--upgrade`) | PL sheets `elevation`, `imagery` |
| `check_failed` | warning | the source could not be checked (e.g. GUGiK sheet index unavailable), the local version used | data commands, `elevation availability` |
| `unverified_local` | info | `--upgrade`: local version of a source without a cheap change signal (new content: `--force`) | data commands |
| `no_coverage_some`, `no_coverage_hint` | warning, info | some sheets without GUGiK data (at least 1 file downloaded) and provider hints | `elevation`, `imagery download` |
| `better_coverage`, `link_outside_range` | info | an older flight from the year range has larger coverage; the link stayed on a flight outside the range | `elevation`, `imagery download` |
| `sheet_crs_mismatch`, `incomplete_campaign` | warning | sheet file in a different CRS than the sheet code; the latest campaign declares an incomplete sheet | `elevation`, `imagery download` |
| `cutout_size` | info | PL cutout: many WCS requests or at least 1 GiB, with an estimated time (25–40 s per request) | `--cutout` (PL) |
| `all_nodata` | warning | NMT/NMPT cutout or CZ sheet or cutout without data (nodata only; a PL cutout entirely outside land and an image cutout entirely 0,0,0 are an `Error:`) | `elevation download` |
| `slow_source` | info | slow service: measured response time before the area query (OGC API PRNG) | `names download` |
| `laz_superseded` | info | LAZ tiles skipped as covered by newer ones | `elevation download --product laz` |
| `download_size`, `whole_country_size` | warning | unit file over 100 MiB or a country file: size before transfer | collections, `landcover --whole-country`, true orthophoto and oblique orthophoto sheets |
| `area_omitted` | info | the area result deliberately omits source layers that are in the country file (PRG special boundaries, HY-NET, ZABAGED) | `boundaries`, `hydro`, `landcover download` |
| `classes_absent` | info | the package has no file for one of the `--layers` classes (no such objects) | `landcover --product bdoo` |
| `corine_preview` | info | CORINE without CLMS credentials: WMS preview instead of data | `landcover --product corine` |
| `cache_disabled` | warning | metadata cache not usable (e.g. read-only directory); the download continues | all |
| `project_geometry_changed` | warning | the task geometry file has changed since pinning | `project download --check` |
| `index_unsupported`, `cz_service_only` | info | index records that Kartograf does not download; CZ models without sheet files (DMR 5G, DMP 1G) | `elevation availability` |

The area unit list has two codes because of the printout: `sheet_list`
(`download_data`) is printed by the CLI as the sheet list header on stdout,
and `unit_list` (collections, also map sheets and geodetic control archives) as `Info:`
on stderr.

---

## 3. Download result

**Return value.** `download_sheet`, `download_hierarchy` and
`download_sheets` return `DownloadResult`. A PL-1992 sheet code coarser than
1:10000 expands into 1:10000 sheets (`expand_sheets`); failures of
individual sheets of a list and hierarchy do not interrupt the others.
`result.files[godlo]` contains a tuple of `VersionedFile`: `path` is the standard
path, `version_path` is the version file, `label` and `status` describe the
selected version.

**Summary:** `succeeded`, `failed`, `skipped`, `no_coverage` (sheets
for which GUGiK has no data; a subset of `failed`), `campaign_files`,
`reused_campaign_files`, the statuses `new`/`relabeled`/`unchanged`/`local`,
`newer`, `unverified` and `no_coverage_hints`. `stale` contains outdated
update plan items, `notices` data notices also passed through
`on_notice`. The fields `better_coverage`, `link_outside_range`,
`full_links`, `full_link_outside_range` and `without_full` remain (sections 4.1 and 4.2).

- `PlCutoutResult` (WCS cutout): `file` (`VersionedFile`),
  `masked_pixels`, `zero_pixels`, `all_nodata`, `stale`, `notices`.
- `CzCutoutResult` (CZ cutout, `download_cz_cutout`) and `CzSheetResult`
  (CZ sheet, `download_cz_sheet`): `file`, `all_nodata`, `stale`, `notices`.
- `CzLazResult` (`download_cz_laz`): `sheets`, `files` (a version per
  sheet), `failed` (`CzLazFailure(sheet, error)`), `stale`, `notices`, `ok`.
- `LazDownloadResult` (`download_laz_area`): `tiles` (selected tiles),
  `files` (`VersionedFile` per tile), `failed`, `superseded` (tiles
  skipped as covered by newer ones), `stale`, `notices`.
- `DataReport` (`download_data`, commands `kartograf elevation download` and `kartograf imagery download`): `files`
  (`UnitFile(unit, country, file)`), `failed` (`UnitFailure(unit, country,
  error, kind)`), `stale`, `superseded`, `notices`, `ok` (CLI exit code:
  `True` = 0).
- `LandCoverReport` (`download_landcover`): `files`
  (`UnitFile(unit, country, file)`), `raw` (the original BDOT10k ZIP with
  `keep_raw`, also as `UnitFile`), `failed` (`UnitFailure` indicating
  the unit, country, text and kind of error), `stale`, `notices`, `ok`.
  `SoilReport` (`download_soil`) has the same contract without `raw`.
  `HsgReport` (`calculate_hsg`) adds `inputs` (clay/sand/silt inputs),
  and puts the result raster in `files`; input failures in `failed`, `ok=False`.
- `VersionedFile`: `path` (standard path = hard link), `status`
  (`new`/`unchanged`/`relabeled`/`local`, for HSG also `reused`), `label`, `sha256`,
  `version_path`, `newer` (the source has newer content, default mode),
  `unverified` (`"unchecked"` — the default mode did not ask the source about the local version,
  `"none"` — no cheap signal, `"check_failed: ..."`).
  `file` of single-file results is `None` only with `plan=`, when the plan
  does not execute that file and there is no local version.

**Sidecar.** Every successful download through the CLI or the management layer
of the library (below) writes two files: the data (`.asc`, `.tif`,
`.laz`, `.gpkg`, ...) and `<file>.meta.json` (schema `kartograf-meta/1`): the horizontal
and vertical CRS of the file, nodata, the request, licence, transformations used,
provenance (`extra.source`), and for area tasks `extra.parent_request`
linking the files of one task. Full table of fields: ARCHITECTURE 3.2,
`parent_request`: ARCHITECTURE 3.4. Sidecars are written by the management layer
(`DownloadManager`, `LandCoverManager`, PL and CZ cutouts, and LAZ tiles
(PL and CZ) and CZ sheets in the library), and `FileStorage.delete()` removes the sidecar together with the data file.
A direct call to a provider (e.g. `CuzkRasterProvider` from the library) writes
only the data file, without a sidecar.

**Where the files are.** `data/<dir>/<segment>/<unit>`: the directory is the
value of `--product` in `elevation` and `imagery` (`nmt/`, `true-orto/`,
`oblique-orto/`), and in the other groups the group name (`landcover/`,
`geodesy/`). The segment is `<country>_<tokens>` in lower case: `_` separates
tokens, `-` joins the words of one token (`cz_cadastral-map_shp`,
`pl_control_archive-1942`), tokens are the values of choices (`--format SHP` ->
`shp`, `--year 2024`); the PL CRS is always `1992`/`2000`, the PL-2000 zone is the
directory of its number (`nmt/pl_2000_1m_evrf2007/6/...`,
`models3d/pl_mesh/2000/7/...`), a sheet lies in the sheet code hierarchy. The sidecar
field `dataset` is the source key `<country>.<provider>.<name>` (e.g.
`pl.gugik.true_orto`; the `KLUCZ` column in `list-sources`), the `product` field
is the value of `--product` (`true-orto`, `bdot10k`; `soil download` - `soil`,
`soil hsg` - `hsg`). The canonical
table, rules (naming convention: rule 10), examples and migration from 0.6.x:
ARCHITECTURE 3.3.

**Files from 0.7.x.** A plain file at the standard path (without a sidecar
linking to a version) is not a store version: the first run of 0.8.0
downloads the data into `versions/` and replaces the file with a link (ADR-036 D24);
PL cutout files with a date in the name (`<coords>_<YYYYMMDD>.tif`) are not
recognised (section 1.3).

---

## 4. GUGiK campaigns

GUGiK publishes the same sheet in several campaigns (different acquisition years).
By default (also with year flags) the latest campaign is downloaded;
`--all-campaigns` — every one. Choosing the year (`--year`, `--min-year`,
`--max-year`) is described in section 4.1. Campaigns and year apply only to PL — for CZ
the options give `Error: CZ (CUZK) nie ma kampanii - ...` (a Czech-only task)
or `Info:` (a PL+CZ area under `auto`, CZ in the current version).

The actual NMT/NMPT/orthophoto files lie as **versions** in
`data/<produkt>/<segment>/versions/<sheet code hierarchy>/<date>_<id>_<sha8>/<sheet_code>.<ext>`
(`<date>` = acquisition date, `<id>` = campaign number from the GUGiK file name,
`<sha8>` = the beginning of the SHA-256 sum of the content), and the standard path
`data/<produkt>/<segment>/<sheet code hierarchy>/<sheet_code>.<ext>` is a
hard link to the newest local version
([ADR-036](DECISIONS.md)). Nothing overwrites a version: downloading the same
content again is "unchanged", different content is a new version next to the old one.
Details of the modes: section 4.3.

- **Sheet index unavailable:** when the GUGiK sheet index does not respond (network, HTTP
  429/5xx) and the sheet already has a local version, the default mode uses it (every
  strategy) and prints a warning about the local version without checking for a newer one
  (code unchanged, also with `-q`). With a year flag: when EVERY sheet of the task
  has a local version within the year range — the local versions are used with a warning,
  otherwise the whole task ends with an error without downloads. Without a local version,
  with `--upgrade` or `--force` the error ends the download as a failure. Library:
  `DownloadResult.unverified` (the transport error text) and `notices` with the code
  `CHECK_FAILED`.
- **Hard links required:** the standard path is a hard link to the version
  file (the same file on disk, no additional space); Kartograf does not
  create symlinks or copies. A file system without hard links (exFAT/FAT,
  sshfs/FUSE) ends the sheet download with an error. On an SMB share mounted
  without `serverino` (unstable inode numbers) the link is
  confirmed by content: the size and SHA-256 sum of the file match
  the sidecar of the version that the link sidecar points to (one read of the
  file at each run; cost: section 7). The link count does not
  play a part here: the cifs client reports `st_nlink = 1` for a path
  that has just been opened (also for reading, by Kartograf or another
  program), for several seconds, sometimes longer. Therefore the link never
  moves back to an older flight, even right after the file is read. A file with the content of
  a version is that version even as an independent copy; downloading the sheet
  turns such a copy back into a link to the same version, when none
  of the paths reports a second name (e.g. after `rsync -a` without `-H`).
- **Copying `data/`:** use `rsync -aH` or `cp -a` — without preserving
  hard links the standard path becomes a separate copy (duplicated data).
  The version content is uncompressed (SHA-256 sum over the bytes) — for large
  datasets it is worth enabling file system compression.
  On an SMB/cifs share the client may temporarily report a wrong link
  count, so even `rsync -aH` will copy them as separate files
  (after such copying, downloading the sheet restores the link, see above).
  `project verify` confirms the content of the copy, but not the space saving:
  check its disk usage; if needed, copy on the server side or
  from a host with local access to the file system.
- **Windows:** a hard link works without additional privileges (NTFS), and data
  shared over SMB is seen by the Windows client as ordinary files.
- **Migration from 0.7.x:** none; the `kampanie/` directory is not read (the CLI
  prints once `Info: katalog kampanie/ z wersji 0.7.x nie jest uzywany ...`),
  and the needed campaigns are downloaded again into `versions/`; a plain file or
  copy at the standard path is replaced with a link.
- **Record vertical CRS:** an NMT/NMPT sheet index record must declare the
  requested CRS (`ukladWspolrzednychPionowych`: `PL-KRON86-NH` for KRON86,
  `PL-EVRF2007-NH` for EVRF2007); a different value ends the campaign with an error before
  downloading the file (sheet: `Error:`/failure according to the list, in `all` the remaining
  campaigns are downloaded). A record without this field is accepted.
- **Cutout `--cutout`** comes from the GUGiK WCS with the server's composition
  of flights (not from sheet campaigns, section 1.3) and does not accept
  `--all-campaigns`, year flags or `--full-sheet`.
- **LAZ:** `--all-campaigns` downloads all tiles whose frame intersects the
  area (without ADR-029 deduplication). LAZ tiles are versions with a standard-path
  link, without `full_sheet/`.
  `--min-density` is only for LAZ (with other products: `Error:`,
  section 1.1).
- Combining several campaigns into one surface is not part of
  Kartograf (plans: SCOPE 3.1).

Detailed rules: SCOPE 2.12, ARCHITECTURE 3.3 (rules 6 and 7), ADR-030,
ADR-033.

### 4.1 Choosing the data year (`--year`, `--min-year`, `--max-year`)

The data year is the acquisition year: `aktualnosc` of the sheet index record (NMT, NMPT,
orthophoto) or `akt_rok` of the LAZ tile — not the date of acceptance into PZGiK. The bounds are
closed; `--year RRRR` is shorthand for `--min-year RRRR --max-year RRRR`
([ADR-032](DECISIONS.md)).

- **Year flags determine only the permitted years, `--all-campaigns` the number
  of flights per sheet.** By default one, the newest flight in the range
  is downloaded; `--all-campaigns` downloads all flights
  in the range into `versions/`. The same rule for every year flag and every
  product. Example (a sheet with flights 2019, 2023, 2025-04, 2025-10):
  `--year 2025` = flight 2025-10; `--year 2025 --all-campaigns` = both flights
  of 2025; `--max-year 2024` = flight 2023; `--min-year 2024` = flight 2025-10.
- **The standard path** points to the newest local flight and never moves back
  to an older one. When a newer flight was downloaded earlier and the range now excludes it
  (e.g. `--max-year 2022`), the selected flight goes into `versions/`, the link
  stays with the newer one, and the CLI prints `Info: N dowiazan wskazuje lokalny lot
  spoza tego zadania ...` with a line `<sheet_code>: sciezka standardowa -> dowiazanie
  <date>_<id>` (the same for `full_sheet/`, section 4.2).
- **Check first, then download.** When some sheet has data only
  from other years, the task ends with `Error:` and exit code 14 before downloading
  anything (also from the other sheets):

  ```
  Error: brak danych z roku 2024 dla 2 z 4 arkuszy - nic nie pobrano:
    N-34-139-C-a-3-1: dostepne roczniki 2019, 2023, 2025
    N-34-139-C-a-3-3: dostepne roczniki 2019, 2025
  Podpowiedz: --min-year 2024 (rok 2024 i nowsze) albo --max-year 2024 (rok 2024 i starsze)
  ```

  A sheet without any data (sea, an area abroad) is skipped
  with a `Warning:` as before. A sheet index failure during the check aborts the whole
  task (`Error: nie udalo sie sprawdzic roku danych ...`) — repeat the download.
- **Several flights in the range (`--all-campaigns`):** every incomplete flight has
  in the version sidecar the coverage measured at write time (share of valid pixels,
  `extra.coverage`); when the newest flight is incomplete and an older one has greater
  coverage (a full flight counts as fully covered), Kartograf prints
  `Info:` (stderr, also with `-q`) and writes `extra.flights`
  and `extra.better_coverage` in the sidecar of the standard path. The link
  still points to the newest flight; the older one lies in `versions/`.
- **Sidecar:** `request.min_year`/`max_year` (when given), `request.year`
  (when equal), `request.campaigns` (the strategy actually used),
  `extra.available_years` (all years of the sheet in the sheet index).
- **LAZ:** the ADR-029 selection within the range. A tile that without year flags
  would be selected and has a year outside the range must be covered by tiles
  from the range; otherwise `Error: brak kafli LAZ z roku ... dla N z M kafli
  obszaru - nic nie pobrano:` with years per tile. WFS queries go to
  all years of the service. The tile sidecar has `extra.acquisition_date`
  and `extra.full_sheet`.
- **Does not work:** with `--cutout` (`Error: --year nie dziala z
  --cutout ...`) or for CZ (a CZ-only task = `Error:`; a PL+CZ area
  under `auto` requires `--cutout`, so also `Error:` — PL sheets with year flags
  are downloaded with `--country pl`).

### 4.2 Latest full flight (`full_sheet/`, `--full-sheet`)

The latest flight is sometimes incomplete: the sheet index declares
`calyArkuszWypelnionyTrescia = NIE` and the file may have from 1% to 99% of the data.
The standard path still points to the newest flight, and next to it Kartograf
maintains a second link to the newest **local** flight that the sheet index
declares as full ([ADR-033](DECISIONS.md)):

```
data/nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc             # latest flight
data/nmt/pl_1992_1m_evrf2007/full_sheet/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc  # latest full
```

```bash
# sheet with an incomplete latest flight: downloads the latest and the latest full flight
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
#   -> N-34-139-C-a-3-1: nowa wersja 2025-10-21_84183_<sha8> (i druga: najnowszy pełny lot)
kartograf imagery download --sheet M-34-90-C-b-4-4 --product orto --full-sheet --root ./data
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --max-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data # full flight within the year range
```

- **Without the flag** `full_sheet/` is created only from flights that the task
  has locally anyway: by default, when the latest flight is full (both links are
  the same file, no additional space), and with `--all-campaigns` — the latest
  full one among the downloaded flights. The first run after an update creates
  `full_sheet/` also for data already downloaded.
- **`--full-sheet`** downloads at most one additional flight per sheet and only
  when the latest flight in the year range is not full; with `--all-campaigns`
  it adds nothing. The sidecar of such a campaign has `request.full_sheet: true`.
- **No full flight:** there is no file in `full_sheet/`. A `Warning:` about an incomplete
  latest campaign divides the sheets into: `pelny lot w <segment>/full_sheet/`,
  `brak pelnego lotu w skorowidzu` (with year flags: `... w zakresie lat
  zadania`) and `pelny lot nie pobrany: ... - uzyj --full-sheet`.
- **Full = within the borders of Poland.** A border sheet marked as full has
  nodata on the foreign side of the frame — this is normal. `full_sheet/` trusts the
  sheet index declaration and does not measure coverage.
- **Never backwards:** like the standard path; when with year flags
  the link stays with a full flight outside the range, the CLI prints `Info:`
  with a line `<sheet_code>: full_sheet/ -> dowiazanie <date>_<id>`.
- **`list_files()` / `delete()`:** `FileStorage.list_files()` skips
  `full_sheet/` and `versions/`, `delete(godło)` removes both links (the versions
  stay).
- **Does not work:** with `--product laz` and `--cutout` (`Error:` before the network);
  for CZ like the other campaign options.
- **Library:** `DownloadManager(full_sheet=True)`;
  `DownloadResult.full_links` (sheet code -> `full_sheet/`
  path), `DownloadResult.without_full`,
  `DownloadResult.full_link_outside_range`.


### 4.3 Versions, modes and update plan (`--check`, `--upgrade`, `--force`)

Applies to every track of `kartograf elevation download` and `kartograf imagery download`: PL NMT/NMPT/orthophoto sheets,
LAZ tiles (PL and CZ), CZ sheets (TM33, SM5; CZ orthophoto), CZ cutouts and PL cutouts
`--cutout` (including orthophotos), as well as `landcover download`, `soil download`, `soil hsg`
and `boundaries download`, `cadastre download`, `models3d download`,
`hydro download`, `names download`, `maps download` and `geodesy download`. The flags
are mutually exclusive. The table below describes PL sheets (signal:
sheet index); the other tracks differ in the signal. Without `--check`
and `--upgrade` a file with a local version is used **without querying
the signal** (`HEAD`, release, ATOM feed, map sheet index record):
the line `lokalna wersja ... (bez sprawdzania; --check)`, with no network
at once and no `Warning:`. The signal is compared by `--check` (`nowsza:
...`) and `--upgrade` (downloads the newer content). PL sheets and PL LAZ tiles
query the sheet index for the file selection (sheet index records from the cache):

| Track | Freshness signal | Notes |
|---|---|---|
| PL sheets | GUGiK sheet index (`index`) | table below |
| PL LAZ tiles | WFS record (`index`) | a newer flight means new files — downloaded by default; a tile with a local version only with `--force` (D26) |
| CZ: SM5 sheets, TM33 DMR 4G/DMP OK tiles in EVRF2007, LAZ files (plan track `cz_laz`) | `ETag`/`Last-Modified` (`http`) | `--check`/`--upgrade`: one `HEAD` per file; a different `ETag` = `nowsza`, `--upgrade` downloads |
| other TM33 tiles (warp from ImageServer), CZ and PL cutouts (including orthophotos) | none (`none`) | by default `lokalna wersja ... (bez sprawdzania; --check)`; `--check` = `nie da sie sprawdzic bez pobrania`; `--upgrade` = local + `Info:` about `--force` |
| CZ orthophoto (SM5 sheet; plan track `cz_orto`) | release from the CUZK ATOM feed (`metadata`) | label = `<year>_<release>` (`2024_2025-02-06`); one release check per sheet (four files); a newer vintage = `nowsza: ...` in `--check`, `--upgrade` downloads |
| SoilGrids, CORINE CLMS | source release (`metadata`: GetCapabilities / CLMS catalogue) | version label = release (`2.0`, `V2020_20u1`); a newer release = `nowsza: ...` in `--check`, `--upgrade` downloads; release unavailable: without a local version `Error:`, with a local one the local version by default without a query (with `--upgrade` `Error:`) |
| BDOT10k, CORINE preview | none (`none`) | like cutouts; `--force` for BDOT10k also refreshes the PRG cache |
| collections (`boundaries`, `cadastre`, `models3d`, `hydro`; plan track `collection`), area ZABAGED and the BDOT10k archive (`--year`) | none (`none`) | like cutouts; label = vintage/release year or download date (sections 1.8, 1.9) |
| national RUIAN and HY-NET files | `ETag`/`Last-Modified` (`http`) | like SM5 sheets |
| national ZABAGED file | release from the ATOM feed (`metadata`) | label = release date (`2026-10-04`); like CZ orthophoto |
| PRNG/Geonames areas, PRNG country | none (`none`) | `--force` to check for new content; PRNG RP has two national packages |
| Geonames country | ATOM feed release (`metadata`) | `--check` compares the release date without downloading the ZIP |
| BDOT10k maps | `Stan bazy` date of the sheet index (`index`) | date separate per scale, without downloading TIFF/PDF; a sheet with a local version by default without GetFeatureInfo |
| CZ ZTM | `ETag`/`Last-Modified` (`http`) | `--check`/`--upgrade`: one `HEAD` per sheet |
| HSG (`soil hsg`) | sha256 of inputs | the same input content = `uzyta ponownie` (no computation); in the plan an `hsg` item next to three `landcover` items |

Under `--country auto` `--check --plan FILE` writes ONE plan
with PL and CZ items (field `track`), and `--upgrade --plan FILE` executes
the items of each track.

| Situation | default | `--check` | `--upgrade` | `--force` |
|---|---|---|---|---|
| local version up to date | local version | `aktualne` | local version | downloads again |
| a newer campaign in the sheet index | local version + `Info:` | `nowsza: <label> (lokalna <label>)` | downloads the newer one | downloads |
| no local version | downloads | `do pobrania` | downloads | downloads |

`--check` downloads nothing; with `--plan FILE` it writes a JSON plan
(`kartograf-plan/1`), which `--upgrade --plan FILE` executes later —
an item whose source has changed since the plan ends with `Error:` without
a download, and items removed from the file are not executed. A `--plan`
pointing to a directory or to a directory that does not exist is a `validation_error` (reason `invalid_input`)
before the network; an `--upgrade --plan` that executed no item (all
up to date or already executed) says so with an `Info:` line (not in `--json`).
`--force` downloads
again and refreshes the metadata cache, but does not overwrite: the same content =
`bez zmian`, different = a new version (in a project `--force` also repairs
damaged pinned versions, section 8.1).

`--check` behaves like a download of the same area with regard to data
(since 0.8.0): a sheet without data in the sheet index (sea, area abroad, no
resolution in the region) **is not a plan item** and is not a check
error — when the rest of the area has data, `--check` ends with code 0
with the same `Warning: GUGiK nie ma danych dla N z M arkuszy ...` as the download
(in JSON: `notices`, `ok: true`); when no sheet has data, it is an
`Error:` with exit code 14 and error code `no_data` (reason `no_coverage`). Sheets with data only outside the
year range give ONE `no_data` error (reason `year_out_of_range`) for all of them (`dla N z M
arkuszy`), as in the download; the `check_failed` item remains for a sheet index
failure (network, 5xx).

`--check` and `--upgrade` always query the source: reading the metadata
cache (sheet index records, PRG responses, indexes; TTL 7 days) is
skipped, and the entries are refreshed — a new flight published after the last
query is visible at once (also without an earlier
`--check`), and without a network the check ends with `Error:`.
The default download uses the cache as before.

```bash
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data
#   nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc: nowa wersja 2025-10-21_84183_4de1eac7
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data --check --plan plan.json
#   nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc: aktualne (2025-10-21_84183)
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 --root ./data --upgrade --plan plan.json
```

Result: one line per file — its subject is always the file path under
`--root` (the same in the download and in `--check`, each file separately,
e.g. the four directions of oblique orthophoto and the JPEG/JGW files of CZ orthophoto), then
`nowa wersja <label>_<sha8>`, `nowa
etykieta <label> (plik identyczny z <label>)` (GUGiK published under
a new record a file byte-identical to the newest existing version; the new
version directory is a hard link, with no additional disk space;
in the library `VersionedFile.same_as`), `bez zmian <label>`,
`lokalna wersja <label>`
(with the suffix `; dostepna nowsza <label> (--upgrade)` from the sheet index
record or `(bez sprawdzania; --check)`), after the list
the summary `Nowe: N, nowa etykieta: N, bez zmian: N, lokalne: N, bledy: N`
(also for PL and CZ LAZ tiles). A CZ sheet, a CZ LAZ file and a cutout give one
status line.

Library:

```python
from kartograf import DownloadManager, GugikProvider, UpdatePlan

godlo = "N-34-139-C-a-3-1"
manager = DownloadManager(
    GugikProvider(vertical_crs="EVRF2007", resolution="1m"), root="./data"
)
result = manager.download_sheet(godlo)
print(result.files[godlo][0].status, result.files[godlo][0].label)
plan = manager.check_sheets([godlo])  # downloads nothing
report = manager.download_sheets(
    [godlo], update="upgrade", plan=UpdatePlan.from_json(plan.to_json())
)
print(report.stale, report.files.get(godlo, ()))
# LAZ: download_laz_area(..., update=, plan=) + check_laz_area (same arguments);
# LAZ CZ: download_cz_laz(..., update=, plan=) + check_cz_laz (same choice);
# cutouts and CZ sheets: download_pl_cutout / download_image_cutout /
# download_cz_cutout / download_cz_sheet / download_cz_orto_sheet(..., update=,
# plan=) + check_pl_cutout / check_image_cutout / check_cz_cutout /
# check_cz_sheet / check_cz_orto_sheet (same arguments); land cover:
# download_landcover(..., update=, plan=) + check_landcover; SoilGrids:
# download_soil(..., update=, plan=) + check_soil; HSG:
# calculate_hsg(..., update=, plan=) + check_hsg; collections:
# download_collection(..., update=, plan=) + check_collection; plan
# items: item.track, item.unit
```

---

## 5. Soils and HSG

- SoilGrids (ISRIC): 11 properties (`ocs` only for the depth 0-30cm, the rest
  6 depths), 5 statistics, resolution 250 m. The file holds integers
  in ISRIC units; conventional unit = value / divisor (`soil
  list-layers`, sidecar `extra.units`): clay, sand, silt g/kg (% = / 10), phh2o
  pH x 10 (/ 10), bdod cg/cm3 (kg/dm3 = / 100), nitrogen cg/kg (g/kg = / 100),
  soc dg/kg (g/kg = / 10), cec mmol(c)/kg (cmol(c)/kg = / 10), cfvo cm3/dm3
  (cm3/100cm3 = / 10), ocd hg/m3 (kg/m3 = / 10), ocs t/ha (kg/m2 = / 10);
  the `uncertainty` statistic is the quotient 10 x (Q0.95 - Q0.05) / Q0.5 (/ 10 = quotient).
  A window smaller than a pixel (250 m) is expanded to one pixel.
  The release (`extra.edition`) comes from the GetCapabilities of the property map; the
  `ocd` map does not give the release in its title, so its release is the release of the `clay` map
  and the `ocd` sidecar says so in machine-readable form: `extra.edition.source_property` =
  `"clay"` (`id` = release, `title` and `url` are those of the `clay` map); in the sidecars
  of the other properties this field is absent (own map).
- HSG (`kartograf soil hsg`, `calculate_hsg(root=...)`) takes
  `clay`/`sand`/`silt` as SoilGrids versions from the same store
  (downloads the missing ones), classifies the texture by the USDA triangle (12 classes)
  and maps it to groups A–D; the result is a GeoTIFF version 1–4 (0 = nodata)
  in `hsg/global_soilgrids_<depth>_mean/` with a sidecar
  (`extra.source_files`: version paths and sha256 of the inputs; PRD 3.8). The same
  inputs = version reused, without computation.
- `hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`
  does the same from ready rasters (g/kg) on a grid with the given CRS
  and pixel, with no default values. Input nodata only from its tag,
  and pixels outside the input extent get `0`; the sidecar contains the SHA-256
  hashes of the input files (`extra.source_files`: `name`, `file`,
  `sha256`; `extra.source_layers` is, as in HSG, a list of layer names).
- The classification uses the **canonical thresholds of the USDA triangle** (oblique boundaries
  `silt + 1.5*clay`, `silt + 2*clay`), shared by the scalar
  and array versions. The texture → HSG mapping is deliberately more lenient than the
  TR-55 table: `sandy_loam` = **B** (not A), `clay_loam`
  and `silty_clay_loam` = **C** (not D) — these are transitional classes whose group
  also depends on the soil structure ([ADR-025](DECISIONS.md)).
- `--summary` computes the **task area** (bbox; with `--geometry` its
  envelope in EPSG:2180; with `--sheet` the sheet frame), not the whole raster:
  the SoilGrids grid (250 m, EPSG:4326) extends beyond the area, so a cell at the
  edge counts by its share in the area, and the sum of areas is the area
  (line `Obszar zadania: <ha> ha`; a 2 x 2 km bbox = approx. 400 ha). The cell
  area is computed geodetically on the ellipsoid, not in square
  degrees. The group percentage is the share **in the area with data**; the line
  `Brak danych: <percent>% obszaru zadania (<ha> ha)` gives the part of the area
  without data (class 0: all inputs 0 or nodata). In the library
  `hsg_statistics(path)` reads the area from the sidecar `request` (a file without
  it: the whole raster) and returns the missing data under the key `nodata` (percentage
  of the area); the group descriptions are in Polish. Where SoilGrids zeros come from: section 7.

---

## 6. CLMS API configuration (CORINE GeoTIFF)

To download CORINE as a **GeoTIFF with class codes** (instead of a PNG preview),
you need an account in the Copernicus Land Monitoring Service:

1. Register at https://land.copernicus.eu
2. Generate API credentials (JSON with the fields `client_id`, `private_key`,
   `token_uri`, optionally `key_id` and `user_id`)
3. Set them in the environment variable `CLMS_CREDENTIALS` — works on every
   system:

```bash
export CLMS_CREDENTIALS='{
  "client_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "token_uri": "https://land.copernicus.eu/@@oauth2-token",
  "key_id": "...",
  "user_id": "..."
}'
```

On macOS an alternative (a fallback when the variable is absent) is Keychain:

```bash
security add-generic-password -a "$USER" -s "clms-token" -w '{ ... ten sam JSON ... }'
```

**Security:** the credentials are read only by the Auth Proxy subprocess
(`python -m kartograf.auth.proxy`), which inherits the environment variables
of its parent. The main application never sees private keys or the token —
the proxy downloads the data itself, and the token goes only to the hosts `*.copernicus.eu`
and `*.eea.europa.eu` (a presigned download link on another `https` host
is forwarded without the token, an `http` address is rejected). Details: PRD 3.6,
CLAUDE.md (critical rules).

**Without configuration:** CORINE automatically downloads a PNG preview via WMS
(the sidecar then gets `extra.fallback = "wms_png"`).

**From the library** you can also pass the credentials directly:
`CorineProvider(clms_credentials={...})` (direct mode, bypassing the
proxy).

---

## 7. Known issues and limitations

- Kartograf does not merge PL and CZ rasters into a single border-area surface
  (R6); the results are separate, linked by `extra.parent_request`.
- Land cover and HSG (since 0.8.0): a data correction within the same
  SoilGrids/CORINE release (without a change of the release label) is detected only by
  `--force`; BDOT10k and the CORINE preview have no cheap freshness signal.
  The CORINE download from CLMS (with `CLMS_CREDENTIALS`) was not verified
  live in 0.8.0 (reading the release from the CLMS catalogue — yes). Land cover
  and HSG files from 0.7.x (`bdot10k_teryt_*.gpkg`, `soilgrids_*.tif`,
  `hsg_*.tif`) are not recognised — download them again into the store.
- The PL-2000 1:10000 sheet code requires an explicit `--scale` in the CLI and `download_data`
  (section 1.6); a provider/`DownloadManager` called without a scale, when the
  sheet index has only child sheets, returns `NoCoverageError`
  with the hint `--scale 1:2000`. A PL-1992 sheet is never downloaded
  as a substitute.
- Country recognition uses rectangular envelopes (ADR-023), not the boundary
  polygon; `--country auto` may query CUZK outside Czechia and GUGiK
  in Czechia (section 1.2).
- The PL `--cutout` of NMT/NMPT is 1 m only: download NMT/NMPT in other
  resolutions (e.g. 0.5m, 5m) and archives as sheets without
  this flag (section 1.3); the CZ cutout has a model step (0.5 m, 2 m or 5 m,
  section 1.4). An orthophoto cutout has a selectable pixel
  (`0.1m`–`1m`), but only in EPSG:2180 and only for PL.
- A store on an SMB/cifs share without `serverino` (section 4): every
  run reads the whole file for each hard link (standard path
  and `full_sheet/`), also with `lokalna wersja` (measurement 2026-10-16: PL orthophoto
  300 MB = approx. 5 s; a store of hundreds of sheets = minutes); the same applies to every
  `link_target` call. Mount the share with `serverino` or keep the store
  on a local disk. Kartograf does not shorten this check: a shortcut without a checksum
  (link count, size, modification time) could treat a link to
  an older version of the same size as current, and the link count
  changes transiently after every file read, including after reading
  for the check itself.
- SoilGrids returns **0** in masked areas, not `-32768` as described
  by ISRIC: WCS with `OUTPUTCRS=EPSG:4326` returns a GeoTIFF without a NoData tag
  (measurement 2026-10-16: Piastów/Ursus, 85 of 104 pixels = 0). Kartograf
  writes the file unchanged (sidecar `nodata` as in the file), and HSG treats
  a clay/sand/silt triple of zeros as no data (`Brak danych` in `--summary`);
  in your own analyses treat 0 g/kg in a masked area as a missing
  value. A raster of only zeros (sea, water, built-up area) gives `Warning:`
  `all_nodata` and `extra.all_nodata` in the sidecar (except `cfvo`, where 0 can be
  a value); HSG without any class gets the same warning.
- The orthophoto WCS is slow (measurement 2026-10-15: approx. 1 min per chunk
  of 200 x 200 m; an area of 1 x 1 km = 25 chunks regardless of the pixel),
  and Standard is sometimes temporarily unavailable. A cutout assembled from chunks is not
  bit-for-bit equal to a single request (differences of a few DN at
  the seams of the server's resampling); `high` outside the 10 cm flight areas
  returns a black image: Kartograf reports `Error:` (without a version in the store)
  only after the download, because the service does not publish its extent (section 1.3).
- CZ orthophoto: only the current vintage of a sheet (archival CUZK images
  are paid); JGW files do not carry a CRS — in GIS assign EPSG:5514 to
  `<sheet_code>.jpg` with `<sheet_code>.jgw` (section 1.4).
- Oblique orthophoto (`--product oblique-orto`) of the Kraków 2021 campaign
  (e.g. sheet `7.125.11.08`, campaign 78945): the GeoTIFF has its own CRS description
  („Transverse Mercator, WGS84”) with PL-2000 zone 7 parameters, without an
  EPSG code. GDAL and rasterio do not report a code (`to_epsg()` = `None`), and with a
  lowered confidence threshold they wrongly match EPSG:32634 (UTM 34N — the image
  would land approx. 6900 km away). The file's CRS is EPSG:2178 (PL-2000
  zone 7), like `horizontal_crs` in the sidecar. In QGIS set the layer CRS
  to EPSG:2178; for a tool that requires a code, provide it without changing the file:
  `gdal_translate -of VRT -a_srs EPSG:2178 plik.tif plik.vrt`. Do not use
  `gdal_edit.py` on a file in the store — changing bytes breaks the SHA-256 checksum
  of the version and of project pins. Campaigns with an EPSG code in the file (e.g. Gdańsk
  2024, EPSG:2177) do not require this.
- ZABAGED: classes are not converted to BDOT10k codes, and the layers of the
  national file have different names than the area result; HY-NET: the area result has no
  stream crossings (only in the national file, EPSG:3045), layer fields
  depend on the content of the area (section 1.9).
- GUGiK archives (`--format XYZ|ASCII-NMT|TBD|TIN|TTN|GRD|DXF|DGN`) are
  downloaded as source files without conversion (ZIP, `.ttn`, `.grd`,
  `.dxf`, `.dgn`): Kartograf does not unpack them, resample them to a
  grid, cut them out or measure coverage — you open the file with a program
  that supports the given format (section 1.1).
- The `elevation availability` report trusts the sheet index declaration
  `calyArkuszWypelnionyTrescia`: a sheet may NOT have from 1% to 99% of
  data, and the report does not measure file contents (section 1.7). In CZ it checks
  only that files exist (`HEAD`), does not know survey years, and `area_m2` of the CZ part
  is a rectangle, not land.
- The availability report rasterises the land of the area on a 1 m grid (strips of
  4 Mpx): for large areas it takes long to compute, and a repeated report of the
  same area uses the metadata cache (section 1.7).
- `provider.download_bbox` (WCS: NMT KRON86 TIFF, NMT EVRF2007
  and NMPT ASC multipart) gives float32 heights at a resolution of
  1 m outside the version store, without the PRG land mask and without a sidecar;
  the mask and version are provided by the `--cutout` cutout /
  `download_pl_cutout`. The server's composition may differ
  from the sheet's campaign choice.
- Cutouts (PL, CZ) and TM33 tiles from ImageServer have no cheap freshness
  signal: a change of content at the source or of the PRG mask is invisible without
  `--force` (openzu files — sheet SM5, TM33 tile DMR 4G/DMP OK
  in EVRF2007, CZ LAZ — have an HTTP signal, section 4.3).
- PRG boundaries, EGiB, 3D building and tree models, the BDOT10k archive, control networks
  and CZ area objects (ZABAGED, RUIAN, HY-NET, Bodove pole; sections 1.8,
  1.9 and 1.11) have no cheap freshness signal: newer content is brought
  only by `--force` (3D mesh tiles compare the index record label).
- 3D tree models: a county package is up to 25 GB, and the GUGiK server answers
  the `HEAD` size request after several to several dozen seconds (approx. 3.5 s per
  GB), so an area of several counties means about a minute of measurement and almost always
  the 10 GB limit `Error:` — download a county (`--teryt`). The 3D mesh of a city
  area is hundreds of tiles: above 100 narrow the area (sections 1.8 and 1.11).
- GUGiK WFS pages (PRG and EGiB area objects) arrive in several
  seconds per page of 1000 objects (live 2026-10-15: 2–4 s; limit of a single
  request 60 s), so a large EGiB area takes minutes. The area result is
  assembled in memory (the whole layer at once) — for a whole county it is more convenient to
  download the export (`cadastre download --teryt`), and for voivodeship boundaries —
  the package (`boundaries download --teryt <2 digits>`); for the whole of Czechia —
  the national file (`--whole-country`).
- The GeoPackage of an area result has the same bytes for the same content only
  within a single GDAL version (`pyogrio`): after a GDAL update `--force`
  may write a new version of the same content.
- Area EGiB comes from the aggregate service of county WFS: a county without
  integration is a gap in the result (no error), restricted attributes have
  the value `brak_uprawnien`. LoD2 of 3D models does not cover the whole country.
- A damaged or unreadable metadata cache (`<cache_dir>/kartograf/metadata.db`)
  does not interrupt the download: the CLI prints one
  `Warning: cache metadanych nieczytelny (<file>): ...` and works without the cache.
  Fix: `kartograf cache clear` (removes the unreadable file together
  with `-wal`/`-shm`) or remove the file manually.

The full list of technical limitations (timeouts, retries, CZ, `auto`):
SCOPE 3.2; plans: SCOPE 3.1.

---

## 8. Project

A project stores in `kartograf-project.json` **tasks** (data commands
with options) and **pinned file versions** (full SHA-256 checksums). One
project points to one `--root` store; many projects can use
the same store, without copying data into project directories.
The standard path in the store may point to a newer version, but
the pin stays on specific bytes. The manifest file can be
kept together with the project scripts in a version control system.

### 8.1 First download and check

```bash
mkdir -p ~/projekty/wisla
cd ~/projekty/wisla
kartograf project init --root ~/dane/kartograf
kartograf project add teren elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --year 2022
kartograf project add pokrycie landcover download --product bdot10k --teryt 1465
kartograf project add gleby soil hsg --depth 0-5cm --sheet N-34-130-D
kartograf project download
kartograf project status
kartograf project verify
```

`init` requires an explicit `--root`; it creates the manifest and the store directory
if they do not exist. `add` takes, by task name, the same commands
and data selection flags as the ordinary `kartograf elevation download`,
`imagery download` (also CZ orthophoto and the `--cutout` cutout), `landcover
download` (also ZABAGED), `soil download`, `soil hsg`,
`boundaries download`, `cadastre download`, `models3d download`,
`hydro download`, `names download`, `maps download` and `geodesy download`;
a CZ orthophoto sheet pins four files (JPEG and three JGW);
it checks the selections without network and without downloading. A task does not store
`--root` or the `--upgrade`/`--force` modes: the store comes from the project,
and the mode is chosen at `project download`. Run options are not
part of a task: `add` with `--workers` or `soil hsg --summary` ends with
`Error:` (parallel download: `project download --workers N`; default
as in the data command). `remove NAME` removes
the task and its pins from the manifest, it **does not remove files** from the store.
Task names can be given positionally in `download`, `status` and `verify`;
without names the command covers all tasks. `--project DIR`
allows working without `cd` (by default the project is in the current directory;
command hints in messages then have `--project DIR`):

```bash
kartograf project verify --project ~/projekty/wisla
```

The first `download` pins the complete set of task files only after full
success; the HSG result also pins the three SoilGrids input files.
A repeated `download` **does not change pins** and does not query the source
when the pinned files are present. When they are missing, it tries to recreate the
task: it accepts only the same SHA-256 checksums and writes the bytes under the
pinned version (`version`, `label`) - the manifest does not change, even
when the source gives a different label (e.g. a download date of a different day). Different content
at the source means an error, never a silent replacement; recover a copy of the store or
explicitly choose `--upgrade`. `status` without network quickly checks the existence
of versions and sizes; `verify` without network reads whole files and compares
SHA-256 and version sidecars. Neither changes the manifest. File
lines have the form `task: unit (file): state`, e.g. `orto_cz:
CTES96 (CTES96.jpg): ok` - files of one unit (JPEG and three JGW) are
distinguishable. A task not yet downloaded is the line `teren: nie pobrane
(pobierz: kartograf project download teren)` and exit code 11 (with `-q` the code only:
`kartograf project status -q || kartograf project download`).

A damaged pinned version (`status`: different size; `verify`: different SHA-256
checksum or sidecar) returns from a copy of the store or after `kartograf project
download --force NAME`: `--force` sets aside the files of the damaged version
(data and sidecar) into a hidden directory `.<label>_<sha8>.corrupt-<time>`
next to it - nothing is removed, and the store scan skips hidden directories -
and downloads the task again. The same bytes return under the pinned version
(`odtworzono`, manifest unchanged); different content at the source re-pins the task
like any `--force`. Without network the version stays set aside (`status`: missing
pinned file), and an ordinary `download NAME` will recreate it from the same
bytes. Without `--force`, manual repair: remove the version directory and run
`download`.

### 8.2 Freshness and data variant

```bash
kartograf project download --check
kartograf project download --upgrade teren
kartograf project download --force pokrycie
```

`--check` queries the source without downloading and compares the state
**with the pin**, not with the newest local version in the store; it does not change the
manifest. `--upgrade` explicitly re-pins the whole task to a newer version,
if there is a change signal, also when the new version is already in the store.
`--force` repeats the download even without a cheap signal; re-pinning
happens after full success of the task, and it repairs damaged pinned versions
(8.1). Other projects keep their
pins, old versions are still in the store.

**Recommendation for reproducibility:** choose an explicit variant in the task
(e.g. `--year`, the appropriate `--resolution` and `--vertical-crs`) when the
product allows it. Without `--year` you choose the latest flight at the time of
download from the source - but when the store already has an older flight of that sheet,
the first `download` pins that local flight (default mode, section 4.3:
without asking the source; `Info:` mentions a newer one), and only `--upgrade` pins the newer one;
after a new flight is published, recreating on an empty
store may return a different checksum and end with an error. Even
an explicit year does not replace a copy of the store if the source withdraws or
replaces the file. There is no `project availability`: before `project add`
use `kartograf elevation availability ...` to learn the available
complete variants of the area (years, CRSs, resolutions, formats), and provide the
chosen task flags — the report prints a ready line `W projekcie:
kartograf project add NAME elevation download ...` without `--root`
(section 1.7; an archive with `--format`, in the manifest the option `format`).
`availability` answers the question *which
variants are available*, and `project download --check` — *whether the
pinned files are current for the chosen variant*. The `--year`
choice remains current for a given year even after a
newer vintage is released.

### 8.3 Moving the project and store

Relative `root` and `options.geometry` paths are saved
relative to the project directory (not the current read directory). A path
from the command line (`--root` in `project init`, `--geometry` in `project
add`) is, however, first READ relative to the current directory, also
with `--project KATALOG` from another location; only then is it saved
relative to the project (outside the project tree this is a `../..` chain in the manifest,
and the store is created where the current directory points): give absolute paths
or run the command from the project directory. The geometry is
a `.gpkg` or `.shp`. Paths given as absolute remain absolute.
Pinned `path` and `version` are always relative to the store.

| Situation | What to do |
|---|---|
| You move the project together with the store, keeping their relative position (relative `root`) | Nothing; `kartograf project verify` will confirm the state. |
| You move only the project, the store stays under the same absolute path | Nothing. |
| You move only the project, and `root` is relative | Change `root` in `kartograf-project.json`. |
| You move or copy the store | Copy together with sidecars and hard links (`rsync -aH`), fix `root`, run `kartograf project verify`. |
| You open a project with an empty store | Create the store directory (or point `root` to an existing one), run `kartograf project download`, then `kartograf project verify`; restoring requires a matching SHA-256. |

On an SMB/cifs share `rsync -aH` may not preserve all hard
links (section 4); `verify` does not detect redundant copies.

It is worth keeping the area geometry file next to the manifest and giving it as a relative path:
it moves with the project. Changing its bytes since pinning
usually blocks restoring missing files; `status`, `verify` and `download`
do not see it when the files are present (`--check` warns), and an explicit
`--upgrade`/`--force` may accept the changed area. The other commands
require an existing store directory (a missing mounted share will not
cause a download into an empty directory).

### 8.4 Python library

```python
from pathlib import Path
from kartograf import (
    add_project_task, check_project, download_project, init_project,
    get_project_status, verify_project,
)

project_dir = Path.home() / "projekty" / "wisla"
init_project(project_dir, root=Path.home() / "dane" / "kartograf")
add_project_task(
    project_dir,
    name="teren",
    command="elevation download",
    options={
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "year": 2022,
    },
)
report = download_project(project_dir)
print(report.ok, [(task.name, task.outcome) for task in report.tasks])
print(get_project_status(project_dir).ok, verify_project(project_dir).ok)
check = check_project(project_dir)  # source probe; no download and no write
print([(item.task, item.status) for item in check.files])
download_project(project_dir, tasks=["teren"], update="upgrade", workers=8)
```

`init_project` and `add_project_task` return `Project`,
`download_project` returns `ProjectReport` (`tasks`, `notices`, `ok`;
`workers` = parallel file downloads of each task, `None` = command
defaults),
and `check_project`, `get_project_status` and `verify_project` return
`ProjectCheck` (`files`, `not_downloaded`, `notices`, `ok`).
`open_project(project_dir)` reads and validates the manifest; the API also provides
`remove_project_task`. Project operations by default work without the
SQLite cache (`cache=False`); `cache=True` creates the cache in the current
directory, so use it only locally. Format and write contract:
[ARCHITECTURE.md, section 3.5](ARCHITECTURE.md#35-project-manifest-kartograf-project1).

## 9. Interface for agents

An AI agent (Claude Code, the Archiwista assistant, a script, another server) uses Kartograf
in three equivalent ways: the CLI with `--json`, the Python library (`to_dict()`,
`to_json()`) and the MCP server `kartograf-mcp`. The same task yields on each of them
the same document `kartograf-<kind>/1`: the same keys, values and key order
(only fields dependent on execution time differ - `checked_at`,
the version label - and store paths). On each path the agent can:
(1) **discover** what Kartograf can do and which values are allowed
(`kartograf commands list` i `commands schema`, 9.4), without reading code and without parsing `--help`;
(2) **call** a command with explicit parameters and get a machine-readable result
(`--json`, 9.2); (3) after an error **know what to fix**, without parsing
text (`kartograf-error/1` with `code`, `hint` and `details.option`, 9.3).
Contract and rationale: [ADR-046](DECISIONS.md#adr-046-interface-for-ai-agents-json-documents-error-codes-command-catalog-and-mcp-server)
and the specification `docs/superpowers/specs/2026-10-18-agent-interface-design.md`;
modules and dependencies: [ARCHITECTURE.md, sections 3.6 and 4.11](ARCHITECTURE.md#36-json-documents-kartograf-1).
A short index for agents, read outside the repository, is `llms.txt` (9.7).

### 9.1 JSON documents and commands

Every command answers with one **result envelope** `kartograf-result/1` (AGI-4.2). The
document of the command (a row of the table below) is its `result`. The CLI prints the
envelope with `--json`, every MCP tool returns it, and `run_command` and `check_command`
of the library return it as `CommandResult` (`to_dict()` is the same document).

| Key | Meaning |
|---|---|
| `schema`, `tool`, `version` | `kartograf-result/1`, `kartograf` and the package version |
| `command` | the catalog id of the command (`elevation download`) |
| `check` | `true` when the run was a plan without effects (`--check`) |
| `status` | `ok`, `partial` or `failed` (a cancelled command is the error `cancelled`) |
| `result` | the domain document of the table below |
| `items` | one entry per unit of a batch, `{id, status, code?, reason?, message?}`: `status` is `ok` or `failed`, a failed unit has the registry `code` of its failure (`reason` where the code is not precise enough); `[]` for a command with no batch |
| `notices` | `{level, code, message}` of the run (the notices of `result`) |

`status` follows the verdict `ok` of the domain document: `ok` when it is true (or the
document has no verdict), `partial` when it is false and a unit succeeded, `failed` when
it is false and no unit did. The exit code of the CLI follows it: 0, 10, 11 (9.3). They
are outcomes, not errors: the envelope is printed all the same and nothing is written to
the error line. In MCP only an error is `isError`. The units, by document:

| Document (`kartograf` prefix left out) | A unit is | A failed unit |
|---|---|---|
| `-download/1` | a unit with a file | a failed unit (`no_data` with the reason `no_coverage` or `year_out_of_range`, else `source_unavailable`), or a planned position the source changed since the plan (`conflict`, reason `stale_plan`); a failed part of a successful report (`--country auto` with one country down) stays a notice |
| `-plan/1` | a position, named by its path below the store | a position the source could not be asked about (`source_unavailable`, reason `check_failed`) |
| `-availability/1` | a country | a country that could not be checked |
| `-project-report/1` | a task | a failed task, with the `code` and `reason` of `TaskResult` |
| `-project-check/1` | a task | `status` and `verify`: a task with no pins (`not_found`, reason `not_downloaded`), a missing file (`not_found`, `missing_file`), a corrupt one (`data_error`, `corrupt_file`); a check: only `check_failed` |

A document with no verdict (a sheet, sources, layers, the cache, the settings, the store,
the catalog, a project that was changed) is `ok` with no items. The documents:

| Document (`schema`) | CLI command (MCP tool) | Library function | Status `partial` or `failed` when |
|---|---|---|---|
| `kartograf-result/1` | every command with `--json` (MCP: every tool), around the document of its own row | `run_command`, `check_command` (`CommandResult`) | never: `status` is the verdict |
| `kartograf-download/1` | `elevation download`, `imagery download`, `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`, `landcover download`, `soil download`, `soil hsg` (MCP: `kartograf_<group>_download`, `kartograf_soil_hsg`) | `download_data`, `download_collection`, `download_landcover`, `download_soil`, `calculate_hsg` | `ok: false` |
| `kartograf-plan/1` | each of the above with `--check` (MCP: the same tool with `check: true`) | `check_data`, `check_collection`, `check_landcover`, `check_soil`, `check_hsg` | item `check_failed` (`ok: false`) |
| `kartograf-availability/1` | `elevation availability` (MCP: `kartograf_elevation_availability`) | `check_availability` | `ok: false` |
| `kartograf-sheet/1` | `sheet parse` (MCP: `kartograf_sheet_parse`) | `describe_sheet` | - |
| `kartograf-sheets/1` | `sheet find` (MCP: `kartograf_sheet_find`) | `find_sheets` | - |
| `kartograf-sources/1` | `<group> list-sources` (11 groups; MCP: `kartograf_<group>_list_sources`) | `list_sources` | - |
| `kartograf-layers/1` | `landcover list-layers`, `soil list-layers` (MCP: `kartograf_landcover_list_layers`, `kartograf_soil_list_layers`) | `list_layers` | - |
| `kartograf-project-state/1` | `project init`, `project add`, `project remove` | `init_project`, `add_project_task`, `remove_project_task` | - |
| `kartograf-project-report/1` | `project download` | `download_project` | `ok: false` |
| `kartograf-project-check/1` | `project status`, `project verify`, `project download --check` (MCP: `kartograf_project_download` with `check: true`) | `get_project_status`, `verify_project`, `check_project` | `ok: false` |
| `kartograf-cache/1` | `cache stats`, `cache path`, `cache clear` | `get_cache_info`, `get_cache_path`, `clear_cache` | - |
| `kartograf-config/1` | `config show` | `get_config` | - |
| `kartograf-command-list/1` | `commands list` (MCP: `kartograf_commands_list`) | `list_commands` | - |
| `kartograf-commands/1` | `commands schema --command` (MCP: `kartograf_commands_schema`) | `command_schema` | - |
| `kartograf-guide/1` | `commands guide` (no MCP tool) | `agent_guide` | - |
| `kartograf-store-overview/1` | `store overview` (MCP: `kartograf_store_overview`) | `describe_store` | - |
| `kartograf-store-entries/1` | `store entries` (MCP: `kartograf_store_entries`) | `list_store_entries` | - |
| `kartograf-store-sidecar/1` | `store sidecar` (MCP: `kartograf_store_sidecar`) | `read_store_sidecar` | - |
| `kartograf-store-init/1` | `store init` (MCP: `kartograf_store_init`) | `init_store` | - |
| `kartograf-error/1` | each command on error: the last line of stderr (9.3) | `error_report` | - |

Common rules of the documents:

- the first key is `schema`, then keys in a fixed order; a key is
  always present (no value is `null`, no elements `[]`);
- paths are absolute strings with `/`; time is ISO 8601 UTC
  (`2026-10-18T12:00:00+00:00`), data dates `YYYY-MM-DD`; `bbox` is
  `[min_x, min_y, max_x, max_y]` next to a key with the CRS (`bbox_crs`, `crs`);
- notices (`Info:` and `Warning:` of the text mode) are in the `notices` array as
  `{level, code, message}` (the text key is `message`, as in an error), in the document of the command
  and in the envelope;
- `ok` is present in the documents `-download/1`, `-plan/1`, `-availability/1`,
  `-project-report/1` and `-project-check/1`. `ok: false` is a **result** (units in
  `failed`, stale positions in `stale`, a `check_failed` position), not an error: the
  status of the envelope is `partial` or `failed` and the CLI exits with 10 or 11. An error
  is `kartograf-error/1`, on the last line of stderr, never an envelope;
- `ok` in `kartograf-project-check/1` depends on the command: `project status` and
  `project verify` give `ok: false` when a task is not downloaded
  (`not_downloaded`) or a file does not have status `ok`; `project download
  --check` assesses only source freshness (`ok: false` = item
  `check_failed`), so a project without pins has `ok: true` there and status `ok`, and
  `not_downloaded` lists all tasks. Completeness and the whole
  project content are assessed by `status`/`verify` (idiom `project status -q ||
  project download`);
- within `/1` changes are only additive (new keys, new enumeration values):
  read by keys and ignore unknown ones; removing a key or changing a type means `/2`;
- library: each document has `to_dict()` and `to_json(indent=2)`; `to_json()` is
  byte-reproducible with the same clock, `to_json(indent=None)` is the compact form of the
  MCP server. Files - the sidecar `kartograf-meta/1` and the manifest `kartograf-project/1` -
  are not result documents. List of keys of each document:
  [ARCHITECTURE.md 3.6](ARCHITECTURE.md#36-json-documents-kartograf-1).

### 9.2 The `--json` contract

The `--json` flag (no short form) is in every leaf command of the CLI (44 commands),
after the command: `kartograf elevation availability --json ...`; `kartograf --json ...` does not
exist. In `project add` give it before the task name (`kartograf project add --json
teren elevation download ...`): after the task name it is a run option and ends with
a `validation_error` with `details.option` equal to `json`.

1. **stdout** is exactly one JSON document, the envelope `kartograf-result/1` (UTF-8
   whatever the locale, indent of 2 spaces, `\n` at the end), and nothing else; an error writes
   nothing to it: no progress bar, no status lines, no
   sheet list header.
2. **stderr** is empty, with two exceptions outside the contract (and the error document, 4): HTTP transport retry lines
   (`Warning:`) and a traceback with `KARTOGRAF_DEBUG=1` (the exception is then raised also
   in JSON mode; with this variable the library diagnostic warnings also pass through). Other
   library diagnostic warnings (e.g. `Pominieto wersje o niezgodnym sha256`,
   `Pominieto wersje bez czytelnego sidecara` with parallel writes) are not printed
   here, and without `--json` have the prefix `Warning:`; the store state is then described by the result
   of the command (e.g. `project verify`). The pyproj warning about a missing PROJ grid
   (`Best transformation is not available`) is not printed in any mode:
   transformations are chosen by the pinned operations policy (ARCHITECTURE 2).
3. `Info:`/`Warning:` notices are in the `notices` field of the document; `-q` is allowed and has no
   effect. `--plan PLIK` works as before, and the plan file is the same document as
   stdout (saved before printing; the line `Info: zapisano plan` is not printed).
   `soil hsg --json --summary` returns statistics in the `summary` field.
4. **Exit code** (9.3): 0 for the status `ok`, 10 for `partial` and 11 for `failed` (the
   envelope is printed all the same: they are outcomes, ERR §1), the registry exit code of the
   error otherwise (2 for an input error, 5 for a source failure, ...), 130 after Ctrl-C, 143
   after SIGTERM. An error is the compact `kartograf-error/1` document on the **last line of
   stderr**, in both modes (AGI-3.3; ASCII: a character outside ASCII is a JSON escape), also
   a syntax error (`reason` `usage`); stdout stays empty. In text mode the `Error:` line, and
   the usage of argparse for a syntax error, come first.
5. Without `--json` the behaviour is unchanged (text), with exceptions: exit code 2 for input
   errors, the `list-sources` and `list-layers` tables and `sheet parse` are rendered from library
   documents (the same text), and `cache path` prints the path alone.

Sheet code (offline):

```bash
kartograf sheet parse N-34-130-D-d-2-4 --json
```

```json
{
  "schema": "kartograf-result/1",
  "tool": "kartograf",
  "version": "0.8.0",
  "command": "sheet parse",
  "check": false,
  "status": "ok",
  "result":
  {
    "schema": "kartograf-sheet/1",
    "sheet": "N-34-130-D-d-2-4",
    "system": "pl1992",
    "country": "PL",
    "sheet_system": "1992",
    "scale": "1:10000",
    "components": {
      "pas": "N",
      "slup": "34",
      "arkusz_200k": "130",
      "arkusz_100k": "D",
      "arkusz_50k": "d",
      "arkusz_25k": "2",
      "arkusz_10k": "4"
    },
    "zone": null,
    "crs": "EPSG:2180",
    "bounds": {
      "bbox": [769911.0902514459, 508419.16283969115, 772163.7346478042, 510851.5730979936],
      "crs": "EPSG:2180"
    },
    "commands": ["elevation download", "elevation availability", "imagery download", "..."],
    "hierarchy": null,
    "children": null,
    "descendants": null
  },
  "items": [],
  "notices": []
}
```

(`result` is the document of the command; `bounds.bbox` and `commands` are written on one line and shortened; the real output has
an indent of 2 spaces and each list value on a separate line; `commands` are the commands that
accept this sheet code in `--sheet`.) Sources from the registry, without network: `kartograf elevation
list-sources --json` (`kartograf-sources/1`: `group`, `products`, `sources` with a key,
a directory in the store, a flag choice in `select`, the licence and freshness signals).

An input error (missing `--vertical-crs`) is a `kartograf-error/1` document on the last line of
stderr and exit code 2, stdout is empty:

```bash
kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --root /dane/kartograf --json
```

```json
{
  "schema": "kartograf-error/1",
  "code": "validation_error",
  "title": "Invalid input",
  "message": "--vertical-crs wymagane dla --product nmt (PL): EVRF2007 (PL-EVRF2007-NH, uklad obowiazujacy), KRON86 (PL-KRON86-NH, uklad historyczny)",
  "hint": "Allowed values of --vertical-crs: EVRF2007, KRON86. Example: kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --root ./data",
  "details": {
    "reason": "invalid_input",
    "option": "vertical_crs",
    "allowed": ["EVRF2007", "KRON86"]
  },
  "exit_code": 2,
  "command": "elevation download"
}
```

(The document is one compact line on stderr; `allowed` is written on one line here.)

### 9.3 Exit codes and error codes

Every error has a `code` of the shared Nogat
[error registry](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md), and
the CLI exits with the exit code the registry gives that code, in every Nogat tool.
The finer distinction of Kartograf is `details.reason` (snake_case English). `code`,
`reason` and the keys never change with the language. Both tables are generated from the
code by `scripts/generate_docs.py` and a contract test checks them. The exit codes 10
(`partial`) and 11 (`failed`) are outcomes, not errors (ERR §1): a batch that finished with
failed units; the result lists them (`items`) and no error document is written.

<!-- generated: exit-codes from kartograf.error_report by scripts/generate_docs.py; do not edit -->
| Exit | Name | Meaning |
|---|---|---|
| 0 | `ok` | Operation completed for every unit. |
| 1 | `internal_error` | Defect in the tool or an unexpected exception. |
| 2 | `validation_error` | Unknown command or option, wrong type, value out of range or not allowed, missing required option, violated exclusion rule. |
| 4 | `conflict` | Operation conflicts with current state: version collision, lock held, identifier taken. |
| 5 | `source_unavailable` | Remote service failed: timeout, connection error, HTTP error, download failure. |
| 6 | `missing_dependency` | Feature needs an extra or an external program that is not installed; hint names the install command. |
| 7 | `data_error` | Data read by the tool (input file, archive, sidecar, stored series) is malformed or violates its format. |
| 8 | `store_unavailable` | Data store or cache cannot be used: missing marker, locked, unreadable, network share disconnected. |
| 9 | `io_error` | Reading or writing files failed: permissions, no space, path missing. |
| 10 | `partial` | Batch operation completed for some units; per-unit status in items[]. |
| 11 | `failed` | Batch operation ran but no unit succeeded; per-unit codes in items[]. |
| 12 | `forbidden` | Path outside allowed directories, write attempted in read-only mode, insufficient role. |
| 13 | `calculation_error` | Input is valid but no result can be computed: no convergence, series too short, numerical failure, transformation failed. |
| 14 | `no_data` | Request is valid but the source has no data for the area, period or product requested. |
| 15 | `unsupported` | Request is valid but this combination is not supported: no safe CRS transformation, product not offered for the country, operation outside the tool's scope. |
| 130 | `cancelled` | Cancelled by the user or by SIGINT. |
| 143 | `terminated` | Terminated by SIGTERM (container stop, timeout). |
<!-- end generated -->

<!-- generated: error-codes from kartograf.error_report by scripts/generate_docs.py; do not edit -->
| Code | `details.reason` | Exception | Exit | When |
|---|---|---|---|---|
| `internal_error` | - | `KartografError` | 1 | package error without a more precise class |
| `validation_error` | `invalid_input` | `ValidationError` | 2 | wrong value or combination of arguments, a missing required argument, an invalid input file (plan, manifest, geometry); reasons that refine it: exclusive_options (output_dir with root) and store_only_option (an option that needs the store, with output_dir) |
| `validation_error` | `usage` | `UsageError` | 2 | wrong use of a command: unknown command or flag, a missing positional argument, a value outside the allowed choices |
| `validation_error` | `invalid_sheet_code` | `ParseError` | 2 | the sheet code is not a PL or CZ code or lies outside the nomenclature |
| `validation_error` | `invalid_config` | `ConfigError` | 2 | the user settings cannot be used: nogat.toml is unreadable, not UTF-8 text, not valid TOML or has a section that is not a table, or a setting has a value that is not valid |
| `source_unavailable` | - | `DownloadError` | 5 | network, HTTP, timeout or the response of the source |
| `no_data` | `no_coverage` | `NoCoverageError` | 14 | the source has no data for the sheet (a state of the data, retrying does not help) |
| `no_data` | `year_out_of_range` | `YearRangeError` | 14 | data exists but not in the requested year range (found before any download) |
| `store_unavailable` | `cache` | `CacheError` | 8 | the metadata cache is unavailable, locked or unreadable |
| `store_unavailable` | - | `StoreUnavailableError` | 8 | the store root has the layout of a store but no kartograf-store.json (reason no_marker: kartograf store init verifies the layout and writes it) |
| `data_error` | `invalid_sidecar` | `InvalidSidecarError` | 7 | the kartograf-meta/1 sidecar is missing, unreadable or of another schema |
| `data_error` | `invalid_layout` | `InvalidLayoutError` | 7 | a root without a marker is not the layout of a Kartograf store, or the marker is not a kartograf-store/1 document (details.problems lists what is wrong) |
| `conflict` | - | `ConflictError` | 4 | the target forbids the write (reasons: output_exists, duplicate_output_name, output_in_store, nested_store, not_empty): an output file that exists, two targets of one name, a plain directory in a store, a store in another store or a store root that is not empty |
| `missing_dependency` | - | `MissingDependencyError` | 6 | an optional extra is not installed (kartograf[mcp] for the MCP server); the hint names the install command (uv add "kartograf[mcp]") |
| `forbidden` | - | `ForbiddenError` | 12 | the MCP server refuses the call: a path outside its allowed directories (--allow-dir), or a write on a server that does not write (--allow-writes) |
| `calculation_error` | `transform_failed` | `TransformError` | 13 | coordinate transformation failed (for example an infinite result) |
| `unsupported` | `transform_unavailable` | `TransformUnavailableError` | 15 | no safe operation for the pair of coordinate systems |
| `io_error` | - | `OSError` | 9 | directory or file unavailable: missing, permissions, no space, disconnected share |
| `cancelled` | - | `KeyboardInterrupt` | 130 | cancelled by the user (Ctrl-C); versions are committed atomically, so units unfinished at the interrupt (also those queued with --workers > 1) do not exist and no half-written file is left |
| `terminated` | - | `Terminated` | 143 | terminated by SIGTERM (timeout, docker stop, kill): cleanup as after Ctrl-C |
| `internal_error` | - | `Exception` | 1 | program error: any other exception except OSError |
<!-- end generated -->

`io_error`, `cancelled`, `terminated` and the second `internal_error` row have no class in
the `KartografError` hierarchy: `error_report` builds them (`io_error` from `OSError`,
`cancelled` from `KeyboardInterrupt`, `terminated` from `kartograf.interrupt.Terminated`, a
subclass of `KeyboardInterrupt`, and `internal_error` from every other exception). With
`--json` an error is the `kartograf-error/1` document on the last line of stderr and stdout
stays empty.

`forbidden` and `missing_dependency` belong to the MCP server: `ForbiddenError` is a path
outside the directories of `--allow-dir` (`details.option`, `details.path` and
`details.allowed` name it) and `MissingDependencyError` is a missing `mcp` package
(`details.extra` is `mcp`, the hint is `uv add "kartograf[mcp]"`; `kartograf-mcp` ends with
exit code 6 and the document as the last line of stderr). The library functions and the CLI
never raise them.

**Cancellation in the CLI (Ctrl-C, SIGTERM).** Both signals act the same way: the command
stops the transfer, removes the working directory of its write
(`versions/.incoming/<host>_<pid>_<token>/`), prints `Error: przerwano (Ctrl-C)` or
`Error: przerwano (SIGTERM)` (with `--json`: a `kartograf-error/1` document with code
`cancelled` or `terminated`) and exits with 130 or 143. With `--workers >= 2` the queue is
cancelled: units (sheets, counties, tiles, packages) that did not finish before the
interrupt are neither downloaded nor committed; running transfers stop after the current
chunk (usually within a fraction of a second, at the latest with the response timeout of
the server) and only then does the command end. Versions committed before the interrupt
stay (each is created atomically). After SIGKILL and after a second SIGTERM (the first
restores the default action) there is no cleanup: the working directory stays and a write
to the same segment removes it after 24 hours. The MCP server (`kartograf-mcp`) does not
intercept SIGTERM: the signal ends the process at once, without cleanup (closing stdin ends
it after the current calls).

`failed[].kind` in `kartograf-download/1` uses the names of the data reasons: `no_coverage`
(the source has no data: sheet, tiles, cutout), `year_out_of_range` (data exists but outside
the year range), `download` (network, server) and `country` (part of `--country auto` failed
for another reason). The same state of the data that the library reports as an exception
(`NoCoverageError`, `YearRangeError`, for example in `check_data` or LAZ `--sheet`) is the
`kind` of the unit in the download report.

The document `kartograf-error/1` has the keys `code`, `title`, `message`, `hint`, `details`,
`exit_code` and `command` (AGI-4.3):

- `code` is a registry code and `title` its English title;
- `message` is exactly the text the CLI prints after `Error: ` (Polish ASCII, as the
  library raises it);
- `hint` is one line (at most 400 characters) and is left out when there is none: the hint
  the exception carries, else the one of its class; for a `ValidationError` with `option`
  the parts `Allowed values of <flag>: ...` (from `allowed`, at most 40 values) and
  `Example: <command line>` from the catalog, and with `options` (for example a missing
  area) `Options: <flags>.` and `Example: <command line>` from the catalog; the hint and
  the title are English, and so is the `message` of every class that moved into the message
  catalog (ADR-053; the others are Polish ASCII until their area moves);
- `details` is always present: `reason` first (when the class has one), then the attributes
  of the exception: `option` (the name of the **API** argument, for example `vertical_crs`,
  not the flag), `options` (the arguments in conflict, for example `["sheet", "bbox",
  "geometry"]`), `allowed` (the allowed values), for sources `sheet`, `status_code` and
  `hints`, for `OSError` `errno` (symbolic name) and `path`; `{}` when there is nothing to
  tell;
- `exit_code` is the exit code of the registry for `code`;
- `command` is the catalog id of the command (`elevation download`) where the error
  occurred; the CLI and the MCP server know it, a library call without context has none,
  and the key is then left out.

The exception contract of the library (DEV-11.1) is unchanged in shape: `except
KartografError` still catches everything, and `code`, `reason`, `exit_code`, `hint`,
`details()`, `ValidationError.option`/`options`/`allowed` and `UsageError.command` are
attributes of the exceptions. `error_report(exc, command=None)` turns any exception into an
`ErrorReport` (the document above): the CLI and the MCP server use it, and a library script
can write an error to its log with it. Without `--json` an error is `Error: <message>` on
stderr, then the document as the last line, with the same exit code (the CLI prints `Remedium:` below a transform error for every
command).

### 9.4 Command catalog

The commands are described by the catalog (`kartograf.catalog`): the CLI parser, the documents
`kartograf-command-list/1` and `kartograf-commands/1` and the MCP tools are built from the same declarations. Two steps:
first the list of commands, then the schema of one command.

```bash
kartograf commands list                                         # groups with products and commands (text)
kartograf commands list --json                                  # the list: kartograf-command-list/1
kartograf commands schema --command "elevation download"        # description of a command: parameters, rules, examples (text)
kartograf commands schema --command kartograf_soil_hsg --json   # kartograf-commands/1 with one command
```

```python
from kartograf import command_schema, list_commands

listing = list_commands()                       # = commands list --json (the `result` of the envelope)
schema = command_schema("elevation download")   # = commands schema --command ... --json
print(schema.to_json())                         # to_dict() / to_json(): like every document
```

`--command` takes the name of a command (`elevation download`) or its `operation_id`
(`kartograf_elevation_download`); an unknown or missing command is a `validation_error` with
`details.option` `command` and `details.allowed` (the command names).

**The list** (`kartograf-command-list/1`, about 11 thousand characters of compact JSON): `tool`, `version`,
`groups` (`name`, `summary`, `products`: the product names) and `commands` (`name` =
`<group> <command>`, `operation_id` = `kartograf_<group>_<command>`, `summary`, `families`,
`read_only`, `check`: the command that plans this command without effects, that is, itself with the option
`check`, or `null`).

**The schema** (`kartograf-commands/1`, the Nogat schema `schemas/nogat/commands-1.schema.json`; up to
about 16 thousand characters of compact JSON, the CLI prints it indented) carries one command: `name`,
`operation_id`, `function` (the library function), `summary`, `description` (when to use, when not,
the main limitation), `options`, `result` (`schema` and `cardinality`: `single`, `bounded`,
`unbounded`), `effects` (`read_only`, `writes`: `none`, `add`, `replace`, `delete`;
`idempotent`, `network`, `destructive`), `check`, `families` (the MCP tool families; `core` is the
main tasks), `rules`, `examples` (`call` = the full CLI command, `result` = an excerpt of the result,
`title`), `errors` (codes of the error registry, 9.3) and `i18n.pl` (the Polish `summary`, `description`,
`rules`; the document does not carry the Polish option descriptions, they are in `--help`).

An option (`options[]`) is a parameter with an argument of the library function, or `check` of a command with a
plan; the flags only the CLI has (`--json`, `--quiet`, `--upgrade`, `--force`) are not options
(`--upgrade` and `--force` write the option `update`). It has a `name` (the function argument, the key of the MCP
call and the `--flag`), `type` (`string`, `integer`, `boolean`, `array`, `object`), `required`,
`description` (in English) and, when it has the value: `items`, `unit`, `default`, `enum` (`value`
and a one-line `meaning`), `min`, `max`, `examples`, `one_of` (a group of mutually exclusive options:
`area`, the choice of the area, exactly one of them) and `path_role` (`input`, `output`, `root`:
a path that the MCP server checks). A value per country (`resolution`, `vertical_crs`) is a string
or an object with the keys `pl` and `cz`.

The exit codes and error codes are not in the catalog any more: the tables are in 9.3, and the codes of a command in its `errors`.
The command descriptions are in English (AGI-9.1); the CLI text and `--help` are Polish until the message
catalogue.

### 9.5 Command layer

The command layer is five functions from `kartograf.__all__` (`command` and `options` are passed
positionally, the remaining arguments are keyword-only); they are called by the CLI (`project add`) and the MCP
server, and the Archiwista assistant can use them to build, validate and run tasks without
knowing the per-product functions:

| Function | Role |
|---|---|
| `parse_command(argv, tasks=False)` | command line of any command (a list of words or a string, also with a leading `kartograf`, as `format_command` writes it) -> `CommandCall(command, options, run)`: `options` is the JSON form of the options of the call (the keys of `commands schema`; as `tasks[].options` for a data command, `bbox` always with `bbox_crs`, a required option the line leaves to the default of its flag, `project_dir` `.`, included), `run` is the remaining flags of the line under the parameter names (`root`, `output_dir`, `upgrade`, `force`, `check`, `plan`, `workers`, `quiet`, `json`, `summary`; there is no `update` key); `project add` has its data command as the options `command` and `options`; a syntax error is a `UsageError`; with `tasks=True` the line must be a data command (`ValidationError(option="command")`) |
| `validate_command(command, options, root=None, output_dir=None)` | validation without network and without writing: a data command gets the checks of its function, any other command is checked against its declaration (names, forms, required options, allowed values, bounds, rules among the options): `ValidationError` with `option`/`allowed` |
| `format_command(command, options, run=None)` | canonical line `kartograf <group> <command> --flag ...` (the inverse of `parse_command`) |
| `run_command(command, options, root=, output_dir=, update=, plan=, workers=, summary=, cache=, on_progress=, on_notice=)` | calls the function of the command (`download_data`, `describe_sheet`, `init_store`, ...) and returns its envelope `CommandResult` (9.1; `result` is the document of the command, `kartograf-download/1` for a download); the mode is `update="upgrade"` or `"force"` (the caller makes it of `run`: `upgrade`/`force` -> `update`, `check` -> `check_command`), `plan` is `check_command(...).result`; an option the command does not have is refused |
| `check_command(command, options, root=, output_dir=, force=, cache=, on_notice=)` | the `check_*` of a command that has a check, without downloading or writing (a data command, `project download`, `store init`): the envelope with `check: true`, `result` is `kartograf-plan/1` (`kartograf-project-check/1` for a project); any other command is `validation_error`, `details.reason` `no_check` |

```python
from kartograf import (
    check_command, error_report, format_command,
    parse_command, run_command, validate_command,
)
from kartograf.exceptions import ValidationError

call = parse_command(
    "elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m "
    "--vertical-crs EVRF2007 --root /dane/kartograf --json"
)
# CommandCall(command='elevation download',
#             options={'product': 'nmt', 'sheet': 'N-34-130-D-d-2-4',
#                      'resolution': '1m', 'vertical_crs': 'EVRF2007'},
#             run={'root': '/dane/kartograf', 'json': True})
validate_command(call.command, call.options, root=call.run["root"])
print(format_command(call.command, call.options, run=call.run))
plan = check_command(call.command, call.options, root="/dane/kartograf")  # network
report = run_command(call.command, call.options, root="/dane/kartograf",
                     update="upgrade", plan=plan.result)                       # network
print(report.status, report.exit_code, [item.id for item in report.items])
try:
    validate_command("elevation download", {"product": "nmt", "sheet": "N-34-130-D-d-2-4",
                                             "resolution": "1m"})
except ValidationError as exc:
    print(exc.option, exc.allowed)                 # vertical_crs ('EVRF2007', 'KRON86')
    print(error_report(exc, command="elevation download").hint)
```

### 9.6 MCP server

The Model Context Protocol server runs over **stdio** (the only transport in 0.8.0): the
script `kartograf-mcp` (or `python -m kartograf.mcp_server`) offers one tool per command of
the catalog, each calling one function of the library (AGI section 5). The name of a tool is
the `operation_id` of its command (`kartograf_elevation_download`); its description, input
schema and hints come from the catalog; its answer is the result envelope
`kartograf-result/1`, the document of `--json` (9.1), and its `outputSchema` says so. The
server is thin: it has no data logic, validation or formatting of its own, and everything it
says (instructions, descriptions, its own messages) is English (AGI-9.2).

**Installation.** The SDK `mcp` is an optional extra (`mcp>=2.3.0,<3`; it brings `pydantic`,
`starlette`, `uvicorn` and `jsonschema`, among others); the core of Kartograf gains no
dependency:

```bash
pip install "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"
```

(after the release: the tag `v0.8.0`; a development checkout: `uv sync --locked --all-extras`
includes `mcp`). `import kartograf` and the CLI work without `mcp`; the script `kartograf-mcp`
is always installed, and without the SDK it ends with the exit code 6 (`missing_dependency`):
the last line of stderr is the `kartograf-error/1` document with the hint
`uv add "kartograf[mcp]"`, stdout stays empty.

**Client configuration.** Claude Code:

```bash
claude mcp add kartograf -- kartograf-mcp                  # reads and plans only
claude mcp add kartograf -- kartograf-mcp --allow-writes --allow-dir /data/kartograf
```

Other clients (a file with the key `mcpServers`; the options of the server are `args`):

```json
{
  "mcpServers": {
    "kartograf": {
      "command": "kartograf-mcp",
      "args": ["--allow-writes", "--allow-dir", "/data/kartograf", "--tools", "core"]
    }
  }
}
```

Where the scripts directory is not on `PATH` (a worktree, `uvx`) use `"command": "python"` and
`"args": ["-m", "kartograf.mcp_server", ...]`. The server prints one line on stderr when it
starts (`kartograf-mcp 0.8.0: stdio, writes off, allow-dir none, tools all`); a
failure to start prints `Error: ...` and the `kartograf-error/1` document as the last line.

**Server options:**

| Option | Meaning |
|---|---|
| `--tools FAMILIES` | tool families, comma separated: `discovery`, `availability`, `data`, `project`, `store` and `core` (default: every tool). `core` is the ten tools of the main tasks (AGI-5.12) for clients that limit the number of tools or have no tool search; an unknown family stops the start (exit code 2) |
| `--allow-dir DIR` | repeatable; an absolute directory (or with `~`; a relative one stops the start with a usage error, exit code 2: it would depend on the working directory the client chose). When given, every path argument (`root`, `geometry`, `project_dir`, `path`, and the paths among the options of `project add`) must lie, after `Path.resolve()`, inside one of the directories, else the call is `forbidden` (exit code 12) with `details.option`, `details.path`, `details.allowed` and a `hint`. Without it a call may read any absolute path. The store that a project manifest names is not checked, the project directory is |
| `--allow-writes` | the tools that write do write, inside `--allow-dir` (required with it: without a directory the start fails with a usage error, exit code 2). Without it the server reads and plans (see below) |
| `--cache-file FILE` | file of the metadata cache; default `<cache_dir>/kartograf/metadata.db`, the same file as the CLI and the library (section 10); it does not depend on the working directory the client chose |
| `--no-cache` | no metadata cache (exclusive with `--cache-file`) |
| `--version` | the version |

**Read only by default (AGI-1.3).** Without `--allow-writes` the 23 tools that only read work
as usual, and each of the 13 tools that write and have a plan (the twelve data commands and
`project download`) is offered as its **plan-only variant**: its input schema has no `update`,
`plan`, `workers` or `summary`, `check` is fixed to `true` (the call may leave it
out), its hints say `readOnlyHint: true`, and every call is the plan (`check: true` in the
envelope, the document `kartograf-plan/1`; for `project download` `kartograf-project-check/1`).
An argument of a run, or `check: false`, answers `forbidden` (12) with `details.option`
and the hint to start the server with `--allow-writes`. The three tools that write and have no
plan (`project init`, `project add`, `project remove`) are not offered at all; a call of one (a
client may still have the old list) answers `forbidden` (12). With `--allow-writes` all 39
tools are offered as declared, and `check: true` still plans.

#### MCP server tools

The hints are the MCP annotations (AGI-5.4); every tool has all five, the `title` (the summary
of the command) and the four booleans: `RO` is `readOnlyHint`, `D` `destructiveHint`, `I`
`idempotentHint`, `OW` `openWorldHint`. A hint that is not listed is `false`: a tool that
writes a store says it is not destructive, because a store never overwrites a version. The
table is the declaration of a server that writes; the last column says what a server that does
not write does with the tool.

<!-- generated: mcp-tools from kartograf.catalog.tools by scripts/generate_docs.py; do not edit -->
| Tool | Catalog command | Library function | Families | Document | Hints | Without `--allow-writes` |
|---|---|---|---|---|---|---|
| `kartograf_elevation_download` | `elevation download` | `download_data` | `data`, `core` | `kartograf-download/1` | I, OW | plan |
| `kartograf_elevation_list_sources` | `elevation list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_elevation_availability` | `elevation availability` | `check_availability` | `availability`, `core` | `kartograf-availability/1` | RO, I, OW | same |
| `kartograf_imagery_download` | `imagery download` | `download_data` | `data`, `core` | `kartograf-download/1` | I, OW | plan |
| `kartograf_imagery_list_sources` | `imagery list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_landcover_download` | `landcover download` | `download_landcover` | `data`, `core` | `kartograf-download/1` | I, OW | plan |
| `kartograf_landcover_list_sources` | `landcover list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_landcover_list_layers` | `landcover list-layers` | `list_layers` | `discovery` | `kartograf-layers/1` | RO, I | same |
| `kartograf_soil_download` | `soil download` | `download_soil` | `data`, `core` | `kartograf-download/1` | I, OW | plan |
| `kartograf_soil_hsg` | `soil hsg` | `calculate_hsg` | `data`, `core` | `kartograf-download/1` | I, OW | plan |
| `kartograf_soil_list_sources` | `soil list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_soil_list_layers` | `soil list-layers` | `list_layers` | `discovery` | `kartograf-layers/1` | RO, I | same |
| `kartograf_boundaries_download` | `boundaries download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_boundaries_list_sources` | `boundaries list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_cadastre_download` | `cadastre download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_cadastre_list_sources` | `cadastre list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_models3d_download` | `models3d download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_models3d_list_sources` | `models3d list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_hydro_download` | `hydro download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_hydro_list_sources` | `hydro list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_names_download` | `names download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_names_list_sources` | `names list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_maps_download` | `maps download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_maps_list_sources` | `maps list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_geodesy_download` | `geodesy download` | `download_collection` | `data` | `kartograf-download/1` | I, OW | plan |
| `kartograf_geodesy_list_sources` | `geodesy list-sources` | `list_sources` | `discovery` | `kartograf-sources/1` | RO, I | same |
| `kartograf_project_init` | `project init` | `init_project` | `project` | `kartograf-project-state/1` | I | not offered |
| `kartograf_project_add` | `project add` | `add_project_task` | `project` | `kartograf-project-state/1` |  | not offered |
| `kartograf_project_remove` | `project remove` | `remove_project_task` | `project` | `kartograf-project-state/1` | D | not offered |
| `kartograf_project_download` | `project download` | `download_project` | `project` | `kartograf-project-report/1` | I, OW | plan |
| `kartograf_project_status` | `project status` | `get_project_status` | `project` | `kartograf-project-check/1` | RO, I | same |
| `kartograf_project_verify` | `project verify` | `verify_project` | `project` | `kartograf-project-check/1` | RO, I | same |
| `kartograf_sheet_parse` | `sheet parse` | `describe_sheet` | `discovery` | `kartograf-sheet/1` | RO, I | same |
| `kartograf_commands_list` | `commands list` | `list_commands` | `discovery`, `core` | `kartograf-command-list/1` | RO, I | same |
| `kartograf_commands_schema` | `commands schema` | `command_schema` | `discovery`, `core` | `kartograf-commands/1` | RO, I | same |
| `kartograf_sheet_find` | `sheet find` | `find_sheets` | `discovery`, `core` | `kartograf-sheets/1` | RO, I | same |
| `kartograf_store_overview` | `store overview` | `describe_store` | `store`, `core` | `kartograf-store-overview/1` | RO, I | same |
| `kartograf_store_entries` | `store entries` | `list_store_entries` | `store` | `kartograf-store-entries/1` | RO, I | same |
| `kartograf_store_sidecar` | `store sidecar` | `read_store_sidecar` | `store` | `kartograf-store-sidecar/1` | RO, I | same |
| `kartograf_store_init` | `store init` | `init_store` | `store` | `kartograf-store-init/1` | I | plan |
<!-- end generated -->

`cache *` and `config show` have no tool (the cache of the server is its own business, and
`update="force"` refreshes entries; the settings are the business of the host), and neither
has `open_project` (the state of a project is returned by the project tools). Tool names are
as stable as error codes. `kartograf_commands_list` and `kartograf_commands_schema` carry
`_meta["anthropic/alwaysLoad"]`, so Claude Code loads their definitions up front. Every tool
has an `outputSchema`: the envelope `kartograf-result/1` as one self-contained JSON Schema,
generated from the vendored `schemas/nogat/result-1.schema.json` by
`scripts/generate_output_schema.py` (a contract test keeps the module equal to the generator).

A tool takes the arguments of the library function, named like the `options` of the
catalog (not the CLI flags); `kartograf_commands_schema(command="elevation download")` lists
them with the meaning of every allowed value. The same task, run and then planned (the
`arguments` of the second call add `check`; the plan is what `update="upgrade"` and
`plan` run later):

```json
{
  "name": "kartograf_elevation_download",
  "arguments": {
    "product": "nmt",
    "sheet": "N-34-130-D-d-2-4",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
    "root": "/data/kartograf"
  }
}
```

```json
{
  "name": "kartograf_elevation_download",
  "arguments": {
    "product": "nmt",
    "sheet": "N-34-130-D-d-2-4",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
    "root": "/data/kartograf",
    "check": true
  }
}
```

**Result and errors.**

- A result, also with the status `partial` or `failed`: `CallToolResult` with
  `structured_content` = `to_dict()` of the envelope `kartograf-result/1` (9.1) and
  `content` = the same document as compact JSON (`to_json(indent=None)`); `is_error` is
  false. The outcomes 10 and 11 of the CLI are results here too (also
  `kartograf_project_status` with a task that is not downloaded): the agent reads `status` and
  `items`. The SDK client checks every such result against the `outputSchema`.
- An error: `kartograf-error/1` (`structured_content` and `content`, `is_error: true`) with
  `command` = the command of the tool. `OSError` is `io_error`, any other exception outside
  the hierarchy is `internal_error` (the full traceback only in the stderr log of the
  server). `forbidden` (12) is a path outside `--allow-dir`, an argument of a run (or
  `check: false`) on a server that does not write, or a tool that is not offered. The
  only protocol error is an unknown tool name (`INVALID_PARAMS`, naming the close tool names).
- The order of the checks of a call: a write that a plan-only tool refuses (`forbidden`); the
  arguments against the input schema of the tool (the first violation is `validation_error`
  with `details.option` = the property: a missing argument, then an unknown one, then a
  missing companion such as `bbox_crs`, then a wrong value); the rule of paths (absolute;
  `--allow-dir`); the options of a run next to `check` (`validation_error`: a plan
  fetches nothing); `validate_command` (the rules of the library, with `option`); then the
  execution in a worker thread. The server adds no default that changes data: a `root`
  that is given is absolute (a relative one is `validation_error` with `option: root` and a
  `hint`), one that is left out is the default store, which must lie inside `--allow-dir`
  (`forbidden` otherwise), and a `bbox` always comes with `bbox_crs`.
- Progress: a tool whose library function has `on_progress` (`kartograf_elevation_download`,
  `kartograf_imagery_download`, `kartograf_landcover_download`, the seven collection download
  tools and `kartograf_project_download`) sends MCP `progress` notifications when it runs (a
  counter of events that grows strictly, no total, the text `<status> <unit>
  (<current>/<total>): <message>`); a plan and the other tools send none.
- Concurrency: calls may run in parallel, but at most 4 tools that use the network
  (`openWorldHint`) at once; the rest wait (GUGiK and CUZK are not flooded). A call that the
  client cancels does not stop a running download (versions are committed atomically, the
  result is dropped); closing stdio ends the server process.
- Cost for the context of the agent: `tools/list` is long, because every property has its
  catalog description and every tool the 3,000-character `outputSchema`: about 212,000
  characters of compact JSON for the 40 tools of a server that writes (89,000 without the
  `outputSchema`), 194,000 (80,000) for the 37 tools of a server that does not, and 66,000
  (35,000) for `--tools core`; the answer of `kartograf_commands_list` is about 11,000
  characters, and `structuredContent` repeats `content`. Claude Code defers the definitions
  and loads only the names and the `alwaysLoad` tools; for a client that loads all of them,
  start with `--tools core` or fewer families. The limit of 30,000 characters of ADR-046 (D22)
  does not hold any more (ADR-052, decision 9).

#### Server instructions (`instructions`)

The server sends the client the text `instructions` (at most 4,096 characters, where Claude
Code cuts it; it loads the text at the start of every session): what the tools have in common
is said there once, and not in the description of each tool, and the last paragraphs say the
state of this server (writes, directories, families). The block below is the text of a server
in the default state (`kartograf.mcp_server.INSTRUCTIONS`); a test compares it:

<!-- generated: mcp-instructions from kartograf.mcp_server by scripts/generate_docs.py; do not edit -->
```text
Kartograf downloads spatial data of Poland and Czechia (GUGiK, CUZK, Copernicus, ISRIC) into a versioned store (root: one directory per product, versions never overwritten) or, with output_dir, as plain files named as in the store. Order: discover, check, run, read. Discover with kartograf_commands_list (groups, products and commands) and kartograf_commands_schema(command="elevation download") (the options of one command, its allowed values with their meanings, rules, examples and errors). What years, grids and CRSs an area has: kartograf_elevation_availability. Read the store: kartograf_store_overview, kartograf_store_entries, kartograf_store_sidecar; the sidecar of a file has its CRS, source and licence.
Shared arguments. Target of a write: output_dir (plain files), root (the store) or neither (the default store), never both. Paths (root, output_dir, project_dir, geometry, path) are absolute. Area: sheet (a sheet code, for example N-34-130-D-d-2-4), bbox ([min_x, min_y, max_x, max_y] in bbox_crs, which is required: there is no default) or geometry (a SHP or GPKG file; layer is its GPKG layer), exactly one; some commands also take teryt, ku or whole_country. country is pl, cz or auto: required with bbox and geometry, implied by a sheet code. Select data explicitly (product, resolution, vertical_crs, ...): nothing is guessed. A value per country is a string or {"pl": ..., "cz": ...}.
Updates. update omitted fetches what is missing, update=upgrade fetches newer content when the source signals it (store only), update=force fetches again: a store never overwrites a version, plain files are replaced and an existing one is otherwise a conflict. check=true plans without fetching (with output_dir each target is write, replace or conflict): a store plan (the result of the envelope, kartograf-plan/1) runs later with update=upgrade and plan.
This server does not write: a command that writes only plans (check is true; update, plan, workers and summary are forbidden), and kartograf_project_init, kartograf_project_add and kartograf_project_remove are unavailable. Start kartograf-mcp with --allow-writes and --allow-dir DIR to download.
Results. A result is the envelope kartograf-result/1: status (ok, partial, failed), result (the document of the command), items (one per unit; a failed one has code and reason) and notices. partial and failed are results (isError false): read items. An error (isError true) is kartograf-error/1 with code, message, hint and details; details.option names the argument to fix. forbidden is a path outside --allow-dir or a write on a server that only plans.
```
<!-- end generated -->

### 9.7 Files for agents

- **`AGENTS.md` and `llms.txt`** in the repository root are the guide for agents (AGI section 8,
  DOC 4 and 5): English and **generated** from the command catalog, the error registry and the
  templates in `src/kartograf/_data/agents/` (`kartograf commands guide --format agents` or
  `--format llms`). `tests/contract/test_agent_guide.py` compares the files with the output of
  the generator byte for byte and keeps the budgets: `AGENTS.md` at most 200 lines and 16 KiB,
  `llms.txt` at most 8,000 characters before the first link list. The generator reads every
  command line of the guide with the real CLI parser, so an outdated example stops it. After a
  change of the catalog, the error registry or a template, regenerate both files:
  `kartograf commands guide --format agents > AGENTS.md` and
  `kartograf commands guide --format llms > llms.txt`. An agent outside the repository starts
  with `llms.txt`, then `kartograf commands list --json`.
- **A block for the `AGENTS.md` of another repository**:
  `kartograf commands guide --format agents-md-block --inject AGENTS.md` puts the compact block
  (at most 60 lines) between `<!-- BEGIN kartograf -->` and `<!-- END kartograf -->` into the
  file of a repository that uses Kartograf; running it again changes nothing. `--inject` is an
  option of the CLI only: the library function `kartograf.guide.inject_block(existing, block)`
  returns the new text and is not part of `__all__`.
- **`python -m kartograf`** works like `kartograf` (an environment without the scripts directory on
  `PATH`: worktree, `uvx`); `python -m kartograf.cli.commands` too.
- **`kartograf/py.typed`** (PEP 561): the consumer's `mypy` sees the library's types instead of
  `import-untyped`.
- **`scripts/gate.sh`**: a single gate command before reporting readiness (ruff, ruff format,
  mypy, offline pytest; also works from a worktree; DEV-7.6).
- Rules for agents from other repositories working on the Kartograf code (a branch from `develop`, no
  merge, push or tags without consent, review before a tag): `CLAUDE.md`, section "Rules for agents of
  other repositories".

---

## 10. Settings and directories

Kartograf keeps its settings where every Nogat tool does (Nogat DEV-18, ADR-050): one file,
`nogat.toml`, and variables with a fixed prefix. A setting comes from the first of:

1. the command-line option (none of the keys below has one yet);
2. the variable `KARTOGRAF_<KEY>`;
3. the shared variable `NOGAT_<KEY>`, for the shared keys `data_dir`, `cache_dir` and `lang`
   only;
4. the table `[kartograf]` of `nogat.toml`;
5. the table `[nogat]` of `nogat.toml`, for the shared keys only;
6. the built-in default.

An empty variable counts as unset. `nogat.toml` is read with `tomllib` from the user
configuration directory (`platformdirs.user_config_path("nogat")`, on Linux
`~/.config/nogat/nogat.toml`) or from the path in `NOGAT_CONFIG`; Kartograf works without it,
and does not read a `.env` file ([.env.example](../.env.example) lists every variable).

| Key | Variable | Default | Meaning |
|---|---|---|---|
| `root` | `KARTOGRAF_ROOT` | `<data_dir>/kartograf` | root of the store of a command that names neither `--root` nor `--output-dir` (DEV-19.2); `config show` reports it and its source |
| `data_dir` | `KARTOGRAF_DATA_DIR`, `NOGAT_DATA_DIR` | user data directory of `nogat` | parent of the stores |
| `cache_dir` | `KARTOGRAF_CACHE_DIR`, `NOGAT_CACHE_DIR` | user cache directory of `nogat` | parent of the caches: the metadata cache is `<cache_dir>/kartograf/metadata.db` |
| `lang` | `KARTOGRAF_LANG`, `NOGAT_LANG` | `pl` | `pl` or `en`, and `--lang` on every command: the language of the text for people (the `Error:` line, the status lines); the `--json` document, the error line on stderr and the MCP server are English; the library texts move into the message catalog area by area (ADR-053, Next item 25) |
| `debug` | `KARTOGRAF_DEBUG` | off | tracebacks of unexpected errors and every library log record in the `--json` mode |

The credential `CLMS_CREDENTIALS` (section 6) is read from the environment only, never from
`nogat.toml`, and is never printed. A directory may start with `~`. Kartograf writes no cache
and no state into the current directory.

```toml
# ~/.config/nogat/nogat.toml
[nogat]
data_dir = "/srv/nogat"          # shared with the other tools: <data_dir>/kartograf is the store

[kartograf]
cache_dir = "/var/cache/kartograf"
```

`kartograf config show` (the library function `get_config`) prints every setting with its
value and source, each credential as present or missing, and the store root with its size
(a hard-linked file counted once). `--json` prints the document `kartograf-config/1`:

```json
{
  "schema": "kartograf-config/1",
  "tool": "kartograf",
  "version": "0.8.0.dev0",
  "config_file": {"path": "/home/ola/.config/nogat/nogat.toml", "source": "default",
                  "exists": true, "error": null, "ignored": []},
  "keys": {
    "root": {"value": "/srv/nogat/kartograf", "source": "default", "name": null, "error": null},
    "cache_dir": {"value": "/var/cache/kartograf", "source": "file", "name": "[kartograf]", "error": null}
  },
  "credentials": {"CLMS_CREDENTIALS": "missing"},
  "store": {"root": "/srv/nogat/kartograf", "source": "default", "name": null,
            "exists": true, "size_bytes": 1835008}
}
```

(`keys` is shortened here: the real document has all five keys. `source` is `default`, `env`
or `file`; `name` is the variable or the table.) `config_file.ignored` lists the keys of
`[kartograf]` that nothing reads: an unknown key, or a credential (`clms_credentials`).

**The default root without the size.** `kartograf.store_root()` returns `StoreRoot(root, source,
name, marker_exists)`: the root of the default store by the same order, the layer that gave it and
whether `kartograf-store.json` is a file in it. It lists and measures nothing, so a caller that only
needs the place (a wizard, a consumer) uses it instead of `get_config()`; IMGWTools has the same
function.

**A file or a value that cannot be used.** An unreadable file, a file that is not UTF-8 text,
invalid TOML, a section that is not a table, a missing file named by `NOGAT_CONFIG` and a
`lang` other than `pl` or `en` are a `ConfigError` (`validation_error`, exit code 2,
`details.reason` `invalid_config`, with `details.option`, `details.path` and, for a value,
`details.value` and `details.allowed`). Every CLI command except `config show` and the MCP
server stop with it, instead of ignoring the file; library functions do not read the file
for validation and use the defaults, and `config show` (and `get_config`) report the problem
in `config_file.error` and `keys.<key>.error`.
