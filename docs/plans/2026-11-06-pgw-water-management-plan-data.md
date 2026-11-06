# Plan: PGW water management plan data in Kartograf (`hydro download --product pgw`)

Approved: 2026-11-06 (delegated approval: on 2026-11-06 the author delegated the architecture of the Nogat plan
`docs/plans/2026-11-06-hydroni-instance.md` (branch `plan/hydroni-instance`, `1fd0317`: „masz wolną rękę”); this
plan is that plan's step 1 and carries out its decision D1; design details by delegated authority, reviewed by the
author before the merge, DEV-3.3)

Requirements: DEV-17.4, HUB-5.2 (the producer first: Hydrograf's step 3 reads the GeoPackage of this product),
DEV §19 through ADR-054 (plain mode and the store), DEV-10.1, DEV-10.5, DEV-10.6, DEV-13.2, ERR-4. Decision record:
[ADR-059](../decisions/0059-pgw-water-management-plan-data.md). PROGRESS item 27.

## Goal

`kartograf hydro download --product pgw --country pl` downloads the spatial geodatabase of the second update of the
river basin management plans (IIaPGW, 2022-2027) that PGW Wody Polskie KZGW publishes on
<https://apgw.gov.pl/pl/III-cykl-materialy-do-pobrania>:

- `--whole-country`: the archive as published, a version of the store;
- an area (`--bbox`, `--geometry`): one GeoPackage in EPSG:2180 with the whole features of the spatial layers that
  intersect the area, the layers chosen by `--layers` (the feature datasets `PGW_WP`, `JCWPd`, `SIG`), read from
  the stored archive, which is downloaded once.

Both in plain mode (`-o`) and in the store (`--root`), with `--check`, sidecars that name the source and the
portal's reservation, and the error codes of the registry. Hydrograf's processing by PGW units (Nogat plan D3)
reads the GeoPackage; the Hydroni store gets both files in Nogat's step 6.

## Where it starts (2026-11-06)

| Fact | Consequence |
|---|---|
| `hydro` has one product, `network` (HY-NET, CZ; ADR-042 D16), and neither `--sheet` nor `--teryt` | `pgw` is the first PL product of the group |
| The materials page links one spatial file, `wody.isok.gov.pl/api/repo-mdd/publ/download/file/bccfebcf31ac47799fe1de6294b73c29/geobaza-2apgw-ver-20230915-gdb-zip`: `HEAD` 200 without authentication, `application/zip`, 142,048,450 B, no `ETag`, no `Last-Modified` | a national file without a cheap freshness signal; the URL names the edition |
| The ZIP holds one File Geodatabase, `Geobaza_2aPGW_ver_20230915.gdb/`: 25 spatial layers in `PGW_WP` (16), `JCWPd` (1) and `SIG` (8), and 34 attribute tables | the area GeoPackage takes the spatial layers; the tables stay in the archive |
| Every layer carries an ESRI definition of the CS92 grid (ESRI:102173); pyproj 3.8 (PROJ 9.8.1) does not equate it with EPSG:2180, whose datum is ETRF2000-PL in the current EPSG dataset | EPSG:2180 is written after a check of the projection; nothing is reprojected |
| GDAL reads the geodatabase inside the ZIP: the 25 layers of the Hydroni envelope (70 x 78 km) in 11.2 s from the NAS; its 14 non-empty layers make a 14.7 MB GeoPackage | an area is read from the stored archive in seconds |
| `pyogrio` (GDAL 3.12.4 in the environment) writes a File Geodatabase with feature datasets offline | test fixtures and the consumer fixture are built without the network |
| The collection engines (ADR-042, ADR-043), the derived versions of `soil hsg`, plain mode (ADR-054) and `extra.parent_request` exist | reused, see Modules |

## Options

ADR-059 records each option with its reason: the area result (fetch the archive per request; a provider class; the
stored archive and a GeoPackage derived from it), the area of `--geometry` (its features; its envelope), `--layers`
not given (`PGW_WP`; required; every layer), the freshness signal (`http`; `metadata` from the page; `metadata`
from the registry; `none` with the edition as label), the CRS (reproject; write EPSG:2180 after a check) and the
GeoPackage layer names (the source names; ASCII names).

## Decision

ADR-059, in short:

1. `pl.pgw.pgw` in the source registry, product `pgw` of the group `hydro`, `provider` `PGW Wody Polskie`.
2. One edition, the file of 2023-09-15: version label `2023-09-15` (`label_source="edition"`), a ZIP member ending
   in `_ver_20230915.gdb/gdb` required, signal `none` (`--check`: `unverifiable`; a new edition is a registry change
   and `--force`).
3. `--whole-country`: the ZIP 1:1 through the `unit_package` channel, `hydro/pl_pgw_gdb/country/pl.zip`.
4. An area: a second channel with the new parameters `ArchiveLayersParams`; the archive is the local version of
   its slot or one download into it, and the GeoPackage
   `hydro/pl_pgw[_<layers>]/bbox/<coords>.gpkg` is written from it (or reused when a version written from the same
   archive `sha256` exists): the features that intersect the envelope of the area, unclipped, in the order of
   their identifier, every chosen layer (an empty one with its schema), lowercase ASCII layer names, EPSG:2180; the
   `Info` `AREA_OMITTED` names the attribute tables left out; no feature at all is `no_data`.
5. `--layers PGW_WP,JCWPd,SIG` (any of them, without letter case; not given: all), a segment token like BDOT10k's.
6. Sidecars: the source, the portal's reservation (`license` id `PL-APGW`), `extra.source_files` naming the
   archive version a GeoPackage comes from, `extra.parent_request` by the rules of collections.
7. `CollectionReport.inputs` lists the archive of an area request; `check_collection` gives the archive and the
   GeoPackage items.
8. Plain mode: `pl.zip`, or `<coords>.gpkg` with the archive fetched into the staging directory and removed.
9. Errors: `validation_error`, `no_data`, `source_unavailable`; no new code.
10. `command_for_file` rebuilds the archive's command and refuses the area file; `kartograf.testing` gets a fixture
    of the product.

### Where this plan reads the Nogat plan differently

- `--layers` not given is every spatial layer, not `PGW_WP` alone: a default that chooses data is against
  Kartograf's rules for code, and `landcover download --layers` already means "all" when omitted. Hydrograf asks
  `--layers PGW_WP` (Nogat steps 3 and 6).
- The version label is the publication date `2023-09-15`; the plan's edition `2apgw-20230915` is the name of the
  file of that edition.
- For `--geometry`, "the features that intersect the area" means its envelope, as for every collection area
  (ADR-058 decision 4); Hydrograf intersects the units with its own polygon.
- In plain mode every area request downloads the archive: only the store keeps it for reuse.

## Interface changes

1. CLI `hydro download`: `--product pgw`, `--country pl` (the group offers `pl|cz|auto`), the new `--layers CODES`
   (`pgw` with an area), its texts, rules and examples.
2. Library: `download_collection`, `check_collection` and `validate_collection_request` take `layers` (keyword-only,
   `Sequence[str] | None`); `CollectionReport` gets `inputs`.
3. Source registry: `ArchiveLayersParams` in `kartograf.sources.descriptor` (`ChannelParams`); the descriptor
   `pl.pgw.pgw`.
4. Store: the segments `hydro/pl_pgw_gdb` (`country/pl.zip`) and `hydro/pl_pgw[_<layers>]` (`bbox/<coords>.gpkg`).
5. Sidecar `kartograf-meta/1`: no new key (`extra.source_files` is HSG's key, `extra.source.layers` that of the area
   results).
6. Documents: no new schema; `inputs` of `kartograf-download/1` is filled for a `pgw` area.
7. MCP: the tool `kartograf_hydro_download` gets `layers` from the catalog.
8. `kartograf.testing`: one new public fixture function.

## Modules

| Module | Reused as it is | Changed |
|---|---|---|
| `sources/descriptor.py` | `UnitPackageParams`, `PackageVariant` (`edition`, `members`), `FeatureLayer`, `LicenseInfo`, `AccessChannel` | `ArchiveLayersParams`, `ChannelParams` |
| `sources/registry.py` | the two-channel pattern of `_CZ_HYNET`, `_COUNTRIES` built from the keys | `_PL_PGW` and its licence |
| `transport/unit_package.py`, `transport/http.py` | `fetch_package` (atomic download, HTML, size, ZIP and member checks), `download_to`, `head_signal`, the shared retries | – |
| `transform/gpkg.py` | `_gdal_config` (the GDAL lock), `_FIXED_DATE`, `_geometry_type`, `_remove`, `GpkgSummary`, `pyogrio.raw.write` | a writer of the archive layers of an area beside `write_gpkg` |
| `download/collections.py` | `_resolve`, `_candidates`, `_content`, `package_job`, `run_job`, `inspect_job`, `UnitJob`, the volume check, the notices, `CollectionReport` | the archive channel among the area channels, `layers`, the parent and derived jobs, `inputs` |
| `download/fetch.py`, `download/versions.py`, `download/plan.py`, `download/storage.py` | `fetch_version`, `use_local`, `store_file`, `local_file(status="reused")`, `inspect_version`, `VersionRef`, `new_plan`, `select_planned`, `content_segment`, `unit_slot` | – |
| `hydrology/hsg.py` | the pattern of `_reuse_or_compute`, `_matching_version`, `_hsg_item` and `_calculate_plain` | – |
| `download/area.py`, `output.py` | `parent_request_for`, the geometry envelope; plain mode, `Staging.scratch`, `preflight` | – |
| `catalog/commands/hydro.py`, `catalog/commands/_collection.py` | `collection_commands(content=, constraints=)` | `layers`, its `applies_to` rule, examples; the docstring on `--sheet`/`--teryt` |
| `messages/` | the areas `catalog_hydro`, `collections`, `sources`, `legal` | the texts of the product, the option, the errors and the attribution |
| `stored_command.py` | `command_for_file` (families `unit`, `area`) | – (tests only) |
| `testing.py` | the pattern of `build_fixture_store` (real writers, fixed clock) | the PGW fixture |

## Steps

Each step is one or a few commits on `feature/pgw`; during a step only the tests of the changed parts run, the gate
runs once before the merge.

| # | Step | Main files | Proof |
|---|---|---|---|
| 1 | This plan, ADR-059, PROGRESS item 27 | `docs/plans/`, `docs/decisions/0059-*.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md` | – |
| 2 | Descriptor: `ArchiveLayersParams`, `pl.pgw.pgw` with its two channels, licence and attribution, source texts | `sources/descriptor.py`, `sources/registry.py`, `messages/legal.py`, `messages/sources.py` | registry tests: naming convention, signal inventory, one national channel per archive channel, unique layer names |
| 3 | The national archive (`--whole-country`) in the store and in plain mode, `--check`; fixtures `tests/fixtures/pl/pgw/` (the `HEAD` answer of 2026-11-06; a cut of the real archive written by GDAL with the published datasets, names, fields and CRS definition; `README.md` with the recipe) | the fixtures and `tests/integration/`; no engine change expected (`run_job` labels a package by its `PackageVariant.edition`) | stored 1:1, edition marker missing = error, HTML on 200, 404 |
| 4 | The writer of the archive layers of an area | `transform/gpkg.py` | unit tests on the cut: rectangle selection with the boundary, empty layer with schema, identifier order and field, ASCII names and `DESCRIPTION`, CRS check, missing layer, no geodatabase, equal bytes twice |
| 5 | The area: archive channel, parent and derived jobs, reuse by the archive `sha256`, `inputs`, `AREA_OMITTED`, `no_data`, `layers` in the API and the segment, plain mode, `check_collection` items | `download/collections.py` | integration tests of each, offline |
| 6 | Catalog and CLI: `layers`, rule, examples, the `hydro` texts; regenerate `AGENTS.md`, `llms.txt`, the USAGE 8.3/8.6 tables and `_output_schema.py` where they change | `catalog/commands/hydro.py`, `_collection.py`, `messages/catalog_hydro.py` | parity scenarios in `tests/contract/test_parity_collections.py` (area with `--layers`, `--whole-country`, `--check`), JSON contract with `inputs` |
| 7 | `kartograf.testing` fixture; `command_for_file` of both files | `testing.py`, `tests/` | fixture tests, rebuilt and refused commands |
| 8 | Documentation: ARCHITECTURE 3.1, 3.2, 3.3 (rule 9), 4.10 and 5; USAGE 1 (a PGW section), 2 and 7; SCOPE 2, 5 and 7; PRD (a feature section); README and `CLAUDE.md` (the sources); CHANGELOG `[Unreleased]`; PROGRESS item 27 closed | `docs/`, `README.md`, `CLAUDE.md` | the documentation tests |
| 9 | Smoke on the real archive into a store outside `/tmp` (`/mnt/magazyn/agent-tmp/pgw-rozpoznanie/store`): `--whole-country`; the Hydroni area `--geometry /mnt/magazyn/agent-tmp/Hydroni/Obszar_h_07_dissolved.gpkg --layers PGW_WP` twice (download, then `local` and `reused`); `--check`; plain mode; one `live` test of the published `HEAD` | – | the outputs, recorded in Results |

After step 9: `scripts/gate.sh`, the author's review of `git log develop..feature/pgw` and his approval of the merge
into `develop` (DEV-3.3).

## Not in scope

- The plans in editable formats (`iiapgw-na-strone-20230727-zip`), the table of contents of the files in Dziennik
  Ustaw (`spis-tresci-iiapgw-xlsx`), the set of measures (`eiv-p21-ostateczny-zestaw-dzialan-wraz-z-zalacznikami-zip`)
  and the water-body cards (`karty.apgw.gov.pl:4200`): Nogat plan D1.
- The 34 attribute tables in the area GeoPackage: they stay in the archive (`AREA_OMITTED` says so).
- Selecting by the features of a geometry instead of its envelope, and a freshness signal for a new edition
  (ADR-059 options B1 and D).
- `--sheet` and `--teryt` in `hydro`, and the archival materials of earlier cycles.

## Risks

- The file moves or is replaced: a 404 is a `no_coverage` failure (`no_data`: the source no longer publishes the
  file); another edition behind the URL is refused by the edition marker; a correction under the same name is new
  bytes under the same label, fetched only by `--force`.
- No licence is named: whether the data may be redistributed is an open question for the author.
- The bytes of a GeoPackage are deterministic for one GDAL version only, as for `write_gpkg`.
- GDAL warns that two spatial index files of the archive have a suspicious depth and scans those layers; the exact
  test keeps the selection the same, and the writer logs the warnings instead of passing them on.
- A very large area through the area path writes every feature it meets; `--whole-country` is the cheaper way to
  the whole country.

## Results

(filled in per step)

- Step 1: this plan, ADR-059 and PROGRESS item 27.
