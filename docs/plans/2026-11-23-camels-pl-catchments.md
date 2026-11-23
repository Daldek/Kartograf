# Plan: CAMELS-PL catchments and gauging stations in Kartograf (`hydro download --product camels`)

Approved: 2026-11-22 (the author approved the Nogat plan `docs/plans/2026-11-22-camels-pl.md`, whose step 2 this plan
carries out: the design of that plan and the author's decisions 1, 3 and 6; the names of the files in the store by the
decision of the coordinator of that plan; reviewed by the author before the merge, DEV-3.3)

Requirements: DEV-17.4, HUB-5.2 (producers first: Obserwator's step 3 of the Nogat plan reads the files of this
product), DEV-19.5, DEV §20 (DEV-20.4, DEV-20.5, DEV-20.12; Nogat 1.2 in preparation, ECO-086), DEV-10.1, DEV-10.5,
DEV-10.6, DEV-13.2, ERR-1. Decision record: [ADR-062](../decisions/0062-camels-pl-catchments-and-gauging-stations.md).
PROGRESS item 35.

## Goal

`kartograf hydro download --product camels --country pl --whole-country [--version 2.0.0|2.1.0]` stores the catchment
boundaries and the gauging stations of a release of CAMELS-PL (Zenodo, concept DOI 10.5281/zenodo.20133182): two
GeoPackages in EPSG:2180 read out of the ZIP of the release by HTTP range requests and kept as published,

- in the store (`--root`): one version per content, labelled by the date of the first release with these bytes, its
  sidecar naming the release read, every release with these bytes and the provider lines S, P and L;
- in plain mode (`-o DIR`): the two files under their store names and `ATTRIBUTION.txt` with the lines;

with `--check`, the newest supported release when `--version` is not given, and the error codes of the registry.
Obserwator's step 3 of the Nogat plan reads the two files from the store.

## Where it starts (2026-11-23)

| Fact | Consequence |
|---|---|
| `hydro` has `network` (HY-NET, CZ; ADR-042 D16) and `pgw` (PL; ADR-059), and neither `--sheet` nor `--teryt` | `camels` is the second PL product of the group, with `--whole-country` only |
| Three releases: 1.0.0 (record 20133183, 2026-05-29: 354 catchments in another file under the root `CAMELS-PL/`, other names, CC BY-NC 4.0 on the record), 2.0.0 (record 23102156, 2026-10-07) and 2.1.0 (record 23275336, 2026-10-11) | 1.0.0 is known and refused; 2.0.0 and 2.1.0 are read; 2.1.0 is the default |
| 2.0.0 and 2.1.0 hold the same two GeoPackages, `CAMELS_PL_catchments.gpkg` (95,703,040 B) and `CAMELS_PL_gauging_stations.gpkg` (196,608 B), with the same CRC and SHA-256, below the roots `CAMELS_PL_2.0/` and `CAMELS_PL_2.1/` of ZIPs of 1,654,474,228 and 1,670,805,350 B | the members are found by a path pattern whatever the root; both releases make one store version |
| Zenodo answers a `Range` request of the ZIP with `206` and `Content-Range`, without a redirect; the central directory of 2.1.0 has 417 KB | the directory in one request of the last 1 MiB, then the two members, deflated to 55,507,931 B |
| The record of the concept DOI answers `302` to the newest record and then its JSON (`id`, `doi`, `metadata.version`, `metadata.publication_date`) | a notice of a newer release, never the release read |
| Nogat DEV §20 has the lines L and LP of CAMELS-PL, and DEV-20.12 says that the catchments carry S and P as well (ECO-086); no file of Kartograf carried a line (`CLAUDE.md`, Deviations, DEV-20) | the lines S, P and L in the sidecar and in `ATTRIBUTION.txt` of a plain write |
| The collection engines (ADR-042), the national file of PGW labelled by its edition (ADR-059), the versioned store (ADR-036), plain mode (ADR-054) and the fixtures of `kartograf.testing` (DEV-10.6) exist | reused, see Modules |

## Options

ADR-062 records each option with its reason: who fetches the geometry (Obserwator; Kartograf), how the files are
read (the whole ZIP; the shapefile; range requests of the GeoPackages), which release is read (the one of the concept
DOI; a table of the releases Kartograf checked), a call without `--version` (an error; the newest supported release),
the names in the store (the published names; Kartograf's unit names), the version label (the version or the date of
the release read; the download date; the date of the first release with these bytes), the freshness signal (`none`;
the bytes the registry pins), the attribution (Kartograf's own text; the lines S, P and L) and a ZIP that differs from
the registry (store what is found; `ReleaseLayoutError`).

## Decision

ADR-062, in short:

1. `pl.camels.camels` in the source registry (the key by ADR-044 D7), product `camels` of the group `hydro`,
   `provider` `CAMELS-PL`, one `DIRECT_FILES` channel (`country_files`, EPSG:2180, signal `metadata`) with the new
   parameters `ReleaseFilesParams`: the two files, the three releases and the concept record.
2. `--whole-country` only; `--version` chooses a release, the newest supported one without it; 1.0.0 and an unknown
   version are a `validation_error` naming the versions read.
3. The ZIP is read by range requests: its directory, its length, each file found by its pattern exactly once, the
   size, CRC and method of its entry, then the member, its SHA-256; any difference is a `ReleaseLayoutError` and
   nothing is written. A server that ignores ranges gets the whole ZIP downloaded (`whole_archive`).
4. Store: `hydro/pl_camels/country/pl_catchments.gpkg` and `pl_gauging-stations.gpkg`, the bytes as published, the
   label `2026-10-07` (`label_source="edition"`); a stored version with the pinned bytes is used without a request.
5. Sidecar: `extra.source` (with the published `member`), `extra.release`, `extra.releases`, `extra.attribution` and
   the lines in `license.attribution`.
6. Plain mode: the two files and `ATTRIBUTION.txt`, merged into an existing one.
7. `--check`: `current`, `newer` or `missing` without a transfer; the concept record tells of a newer release
   (`newer_release`).
8. `parse_command` takes `--version` as the program's flag only before the group; `hydro download` declares
   `data_error`.
9. `command_for_file` rebuilds the command with `--version`; `kartograf.testing` gets `build_camels_archive` and
   `build_camels_store`.

### Where this plan reads the Nogat plan differently

- The files are named by Kartograf's unit names, `pl_catchments.gpkg` and `pl_gauging-stations.gpkg`, not by the
  published names; the published member path is `extra.source.member` (the coordinator's decision).
- The lines are in the order of DEV-20.4: S, P, then L (the plan names "the lines CAMELS-PL, S and P").
- The release read is also chosen by `--version` in the library (`version`), and a version Kartograf does not know is
  refused like 1.0.0, with the versions it reads in `allowed`.

## Interface changes

1. CLI `hydro download`: `--product camels` (`--country pl`, `--whole-country`) and the new `--version VERSION`
   (`camels` only), its texts, rule and two examples.
2. Library: `download_collection`, `check_collection` and `validate_collection_request` take `version` (keyword-only,
   `str | None`); `ReleaseLayoutError` in `kartograf.__all__`.
3. Source registry: `ReleaseFile`, `ReleaseMember`, `DatasetRelease` and `ReleaseFilesParams` in
   `kartograf.sources.descriptor` (`ChannelParams`); the descriptor `pl.camels.camels`.
4. Store: the segment `hydro/pl_camels` (`country/pl_catchments.gpkg`, `country/pl_gauging-stations.gpkg`).
5. Sidecar `kartograf-meta/1`: the keys `extra.release`, `extra.releases` and `extra.attribution`, and
   `extra.source` `{url, member, crc32, read}`; `license.attribution` holds the lines of the release.
6. Documents: no new schema; a plain write lists `ATTRIBUTION.txt` in `files[]` and in the plan.
7. Notices: `whole_archive` (warning) and `newer_release` (info); error: `data_error` with the reason
   `release_layout` (exit 7).
8. MCP: the tool `kartograf_hydro_download` gets `version` from the catalog.
9. Command layer: `parse_command` reads `hydro download ... --version 2.0.0` as a call.
10. `kartograf.testing`: `build_camels_archive`, `build_camels_store`, `CamelsFixture`, `CAMELS_DATASET`,
    `CAMELS_SEGMENT`.

## Interface for Obserwator

- **Store paths.** `<root>/hydro/pl_camels/country/pl_catchments.gpkg` and
  `<root>/hydro/pl_camels/country/pl_gauging-stations.gpkg` (the standard paths, hard links to the newest version);
  the versions `<root>/hydro/pl_camels/versions/country/2026-10-07_<sha8>/pl_catchments.gpkg` and
  `.../2026-10-07_<sha8>/pl_gauging-stations.gpkg`, where `<sha8>` is the start of the SHA-256 the registry pins:
  `2026-10-07_dadc37e0` and `2026-10-07_a0616fc6` for the bytes of 2.0.0 and 2.1.0.
- **Content** as published: EPSG:2180; the layer `CAMELS_PL_catchments` (GEOMETRY: 845 Polygon and 24 MultiPolygon
  features, 3 of them invalid geometries) and the layer `CAMELS_PL_gauging_stations` (POINT), 869 features each,
  with the fields `gauge_id` (INTEGER, the nine-digit code of IMGW-PIB), `gauge_name` and `water_body_name`.
- **Sidecar** `kartograf-meta/1`: `dataset` `pl.camels.camels`, `provider` `CAMELS-PL`, `request` `{"whole_country":
  true, "version": "2.1.0"}` (the release read), `license` `{"id": "CC-BY-4.0", "attribution": "<S>\n<P>\n<L>",
  "url": "https://creativecommons.org/licenses/by/4.0/"}`, `extra.source` `{url, member, crc32, read}` (`member` the
  published member path, `read` `range` or `archive`), `extra.release` `{version, record, doi, published}`,
  `extra.releases` (every supported release with these bytes, oldest first), `extra.attribution` `[S, P, L]` and
  `extra.version` `{"label": "2026-10-07", "label_source": "edition"}`.
- **Lines** (`_data/provider_lines.json`, byte for byte from the table of DEV §20): S, P and L in this order (DEV-20.4),
  one per line in `license.attribution`, a list in `extra.attribution`, the lines of `ATTRIBUTION.txt` of a plain
  write. L names the release read: its version, the year of its `published` and its DOI. For 2.1.0:

  ```text
  Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy
  Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone
  Źródło danych: CAMELS-PL 2.1.0 (Brzezińska i in., 2026), https://doi.org/10.5281/zenodo.23275336, licencja CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
  ```

- **Python API.** `download_collection(product="camels", country="pl", whole_country=True, version=None, root=...)`
  and `check_collection(...)` with the same arguments; the read API: `describe_segment("hydro/pl_camels")` (a known
  segment), `iter_store(root, segment="hydro/pl_camels")` and `read_sidecar(path)` (`Sidecar.unit` `pl_catchments`
  or `pl_gauging-stations`, `Sidecar.edition` the label); `command_for_file(read_sidecar(path))` gives `kartograf
  hydro download --product camels --country pl --whole-country --version 2.1.0` for a file read from 2.1.0.
- **Testing fixture** (`kartograf.testing`, DEV-10.6): `build_camels_archive(path, *, version=None) -> Path`, a tiny
  ZIP in the published layout of 2.0.0 or 2.1.0 (the root, the two members the registry names, each after its `.prj`,
  the directory entries, deflated, fixed dates) whose GeoPackages hold six gauges of 2.1.0 with their published
  codes, names and points (149180100 Skoczów, 149180110 Ustroń-Obłaziec, 149180120 Górki Wielkie, 149180140 Wisła,
  150210070 Wampierzów as a MultiPolygon of two parts, 151230030 Okuninka with a ring self-intersection) and
  fictional rectangle catchments nested as the published ones (149180140 in 149180110 in 149180100; 149180120 in
  149180100); `build_camels_store(root, *, version=None) -> CamelsFixture(root, release, catchments,
  gauging_stations)`, a store written by the real `run_release` against a registry copy that pins the fixture bytes
  (`FixtureFile`s with one version labelled `2026-10-07`); `CAMELS_DATASET = "pl.camels.camels"`, `CAMELS_SEGMENT =
  "hydro/pl_camels"`.

## Modules

| Module | Reused as it is | Changed |
|---|---|---|
| `sources/descriptor.py` | `SourceDescriptor`, `AccessChannel`, `LicenseInfo` | `ReleaseFile`, `ReleaseMember`, `DatasetRelease`, `ReleaseFilesParams`, `ChannelParams` |
| `sources/registry.py` | the PL registry, `_COUNTRIES` built from the keys | `_PL_CAMELS`, its licence and the releases |
| `transport/http.py` | `download_to`, `get_with_retry`, the shared retries | `fetch_range`, `require_partial`, `RANGE_UNSUPPORTED`, `download_to(headers=)` |
| `transport/zip_range.py` | – | new: `read_directory`, `fetch_member`, `local_directory`, `extract_member` |
| `download/releases.py` | – | new: `choose_release`, `release_lines`, `holders`, `release_jobs`, `run_release`, `plan_release`, `newer_release` |
| `download/collections.py` | `_resolve`, `_candidates`, `CollectionPart`, `CollectionReport`, the notices | `_release_content`, `_release_part`, the branches of `run_request` and `plan_request`, `version` |
| `download/fetch.py`, `download/versions.py`, `download/plan.py`, `download/storage.py` | `store_file`, `local_file`, `local_only`, `link_version`, `list_versions`, `newest_version`, `new_plan`, `select_planned`, `unit_slot` | – |
| `attribution.py`, `_data/provider_lines.json` | – | new: `provider_lines`, `merge_lines`, `plan_attribution`, `write_attribution`, `ATTRIBUTION_FILE` |
| `sources/sidecar.py` | `emit_sidecar` | `attribution=` (the `license.attribution` of a file) |
| `exceptions.py`, `error_report.py`, `notices.py` | – | `ReleaseLayoutError` and its registry row; `WHOLE_ARCHIVE`, `NEWER_RELEASE` |
| `output.py` | plain mode, `Staging`, `preflight`, `refuse` | – |
| `catalog/commands/hydro.py`, `catalog/commands/_collection.py`, `catalog/meanings.py` | `collection_commands`, `choice_values` | `version`, its `applies_to` rule, two examples, `errors=`; the meanings of `camels` and of a version |
| `commands.py` | `parse_command` | `--version` as the program's flag only before the group |
| `store.py`, `stored_command.py` | `iter_store`, `read_sidecar`, `command_for_file` | the segment of `ReleaseFilesParams` |
| `testing.py`, `_data/camels_fixture.json` | `FixtureFile`, `FixtureVersion`, the fixed clock | the CAMELS-PL fixtures |
| `messages/` | the areas `collections`, `sources`, `legal`, `transport`, `catalog`, `catalog_hydro` | the new area `releases` and the texts of the product |

## Steps

| # | Step | Main files |
|---|---|---|
| 1 | Open 0.9.0 at `0.9.0.dev0` on `feat/camels-pl-catchments` from `develop` `228a2870` | commit `115b8d03` |
| 2 | Check the releases from the central directories of their ZIPs by range requests (2026-11-23); record the answers of Zenodo | `tests/fixtures/pl/camels/` |
| 3 | Registry: the engine parameters, `pl.camels.camels` and its releases, the source texts | `sources/descriptor.py`, `sources/registry.py`, `messages/sources.py`, `messages/legal.py` |
| 4 | Transport: ranges of a file, the members of a ZIP by range requests and from a local ZIP | `transport/http.py`, `transport/zip_range.py`, `messages/transport.py` |
| 5 | Engine: the run and the plan of a release, the provider lines, `ReleaseLayoutError`, the notices, the sidecar, the read API | `download/releases.py`, `download/collections.py`, `attribution.py`, `_data/provider_lines.json`, `sources/sidecar.py`, `exceptions.py`, `error_report.py`, `notices.py`, `store.py`, `messages/releases.py`, `messages/collections.py`, `pyproject.toml` (package data) |
| 6 | Catalog and command layer: `--version`, its rule and examples, `data_error`, `parse_command` | `catalog/commands/hydro.py`, `catalog/commands/_collection.py`, `catalog/meanings.py`, `commands.py`, `messages/catalog.py`, `messages/catalog_hydro.py` |
| 7 | Consumer fixtures | `testing.py`, `_data/camels_fixture.json` |
| 8 | Offline tests of steps 3 to 7 on the recorded answers and the fixture archive served from memory, with a CLI = API scenario of `--version` (DEV-10.5) | `tests/` |
| 9 | Documentation: this plan, ADR-062, CHANGELOG `[Unreleased]`, PROGRESS (Status, Open questions, item 35), USAGE (1.14, the notices), ARCHITECTURE, SCOPE, PRD, README, `CLAUDE.md`; regenerate the USAGE 8.3 and 8.6 tables, `AGENTS.md` and `llms.txt` | `docs/`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `llms.txt` |
| 10 | A live read of 2.1.0 from Zenodo into a store outside `/tmp`, `scripts/gate.sh`, the author's review of `git log develop..feat/camels-pl-catchments` and his approval of the merge into `develop` (DEV-3.3) | – |

## Not in scope

- Everything else of CAMELS-PL (Nogat plan decision 7): the attributes, the signatures, the forcing (E-OBS, G2DC-PL+)
  and the simulations are Obserwator's provider `CAMELS` (step 3) and Hydrolog's reference cases (step 5).
- The repair of the 3 invalid geometries, the upstream gauges and the simplified outlines (Obserwator, Nogat plan).
- The shapefiles of the release and release 1.0.0 (ADR-062 options B2 and C).
- The fields `attribution` and `terms_notice` of the JSON documents (DEV-20.6) and the lines G, SG and Z of the
  other products (`CLAUDE.md`, Deviations; PROGRESS, Open questions).

## Risks

- Zenodo stops answering range requests: the whole ZIP of 1.67 GB is downloaded and read (`whole_archive`), under
  the same checks.
- A new release (the Nogat plan names one announced for December 2026): until a Kartograf patch release adds its row
  after checking its layout, `newer_release` tells of it and `--version` refuses it; a release whose files have other
  bytes becomes a new version labelled by its date.
- The ZIP of a known release changes or moves: another length or member is a `ReleaseLayoutError`, a failed request a
  `DownloadError`; nothing is written either way.
- The concept record does not answer: `check_failed` in `--check`, a log record in a run; the files are read anyway.
- The GeoPackages are stored as published, with their 3 invalid geometries: a consumer that needs valid ones repairs
  them.

## Results

(filled in per step)

- Step 1: commit `115b8d03`.
- Step 2: the releases table of ADR-062 (Context), checked on 2026-11-23; `concept_20133182_302.html` (the body of
  the `302` of the concept record) and `record_23275336.json` (the record of 2.1.0) in `tests/fixtures/pl/camels/`.
- Steps 3 to 7: the code of ADR-062; `build_camels_store` writes the store through the real `run_release`.
- Step 9: this plan, ADR-062 (indexed in `docs/DECISIONS.md`, with the amendments of ADR-042 and ADR-054 recorded on
  both sides) and the documents above; the generated tables of USAGE 8.3 and 8.6, `AGENTS.md` and `llms.txt` are the
  output of their generators.
- Live check (2026-11-23): `hydro download --product camels` of 2.1.0 against Zenodo into a throwaway root, 7 HTTP
  responses in 30.8 s (the concept record's `302` and record 23275336, the last 1 MiB as `206`, then per member its
  30 B local header and its body: 55,463,024 B of catchments, 44,907 B of gauges; 55.5 MB transferred instead of
  the ZIP's 1.67 GB); both files byte-equal to the members of the 2.1.0 ZIP on the NAS.
- Gate: `scripts/gate.sh` green, 8800 passed, 18 deselected.
