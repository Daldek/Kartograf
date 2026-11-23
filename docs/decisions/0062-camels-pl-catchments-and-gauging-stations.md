# ADR-062: CAMELS-PL catchments and gauging stations: `hydro download --product camels`, the files of a release read from its ZIP

**Date:** 2026-11-23
**Status:** Accepted (the Nogat plan `docs/plans/2026-11-22-camels-pl.md`, approved by the author on 2026-11-22, step
2; the store names by the decision of the coordinator of the plan; the author reviews it at the merge, DEV-3.3);
amends ADR-042 (D1: the engine `release_files`; D2: `--whole-country` of a data set published in releases, chosen by
`--version`; D6: the signal of the bytes the registry pins and the label of the first release with a file's bytes)
and ADR-054 (decisions 3 and 6: `ATTRIBUTION.txt` in a plain write of CAMELS-PL and its plan position)
**Standard:** Nogat 1.2 (in preparation on Nogat `develop`; ECO-086): DEV-17.4, DEV-19.5, DEV §20 (DEV-20.4,
DEV-20.5, DEV-20.12), DEV-10.1, DEV-10.5, DEV-10.6, DEV-13.2, ERR-1; plan
[`docs/plans/2026-11-23-camels-pl-catchments.md`](../plans/2026-11-23-camels-pl-catchments.md); Nogat plan
`docs/plans/2026-11-22-camels-pl.md`, step 2

**Context:** On 2026-11-22 the author approved the Nogat plan for CAMELS-PL (Brzezińska et al.; Zenodo, concept DOI
10.5281/zenodo.20133182). The catchment boundaries of CAMELS-PL, made to the order of IMGW-PIB, are the boundaries of
the gauges (decision 1); Kartograf, not Obserwator, fetches the geometry, the catchments and the points of the gauges,
as a product of its group `hydro`, and Obserwator reads them from Kartograf's store (decision 6, ECO-086); a
catchment carries the line of CAMELS-PL and S and P of IMGW-PIB (decision 3, DEV-20.12). The design of the plan:
each tool knows the releases it supports (record, version, DOI, checksums of the members it reads), takes the newest
of them by default and another by `--version`; the concept DOI only tells that a newer release exists and is never
adopted unchecked; a new release enters by a patch release after its layout is checked; members are found by their
path pattern, not by the root folder, and a layout that differs more is refused with the version named and nothing
written; Kartograf reads the two GeoPackages from the ZIP by HTTP range requests (the whole ZIP as the fallback),
keeps them as published, makes a new store version only when their bytes change (2.0.0 -> 2.1.0 makes none), and
the sidecar names every release with these bytes and the lines. Checked on 2026-11-23:

- **Releases** (the central directories of the ZIPs, read by range requests):

  | Version | Record | Published | ZIP | Bytes | Root |
  |---|---|---|---|---|---|
  | 1.0.0 | 20133183 | 2026-05-29 | `CAMELS-PL.zip` | 780,566,205 | `CAMELS-PL/` |
  | 2.0.0 | 23102156 | 2026-10-07 | `CAMELS_PL_2.0.zip` | 1,654,474,228 | `CAMELS_PL_2.0/` |
  | 2.1.0 | 23275336 | 2026-10-11 | `CAMELS_PL_2.1.zip` | 1,670,805,350 | `CAMELS_PL_2.1/` |

  1.0.0 holds 354 catchments in another file under its root, names other files otherwise, and its record licenses it
  under CC BY-NC 4.0, which the line L (CC BY 4.0) cannot name. 2.0.0 and 2.1.0 hold the same two members below their
  root: `CAMELS_PL_catchment_boundaries/catchments/CAMELS_PL_catchments.gpkg` (95,703,040 B, CRC `2ff1251b`, SHA-256
  `dadc37e02febc0f188683c0df18b2380767a4396e7948213b73617ff4746d6b9`, deflated to 55,463,024 B) and
  `CAMELS_PL_catchment_boundaries/gauging_stations/CAMELS_PL_gauging_stations.gpkg` (196,608 B, CRC `6addfeba`, SHA-256
  `a0616fc6eef89b1a3e84de3688e35a87c54ffb2517dc1a54ddcc3af4579d8c14`, deflated to 44,907 B).
- **Content** of the two GeoPackages (EPSG:2180): the layer `CAMELS_PL_catchments` (GEOMETRY: 845 Polygon and 24
  MultiPolygon features, 3 of them invalid geometries) and the layer `CAMELS_PL_gauging_stations` (POINT), 869
  features each, with the fields `gauge_id` (INTEGER, the nine-digit code of IMGW-PIB), `gauge_name` and
  `water_body_name`; the catchments are nested.
- **Zenodo.** `GET https://zenodo.org/api/records/23275336/files/CAMELS_PL_2.1.zip/content` with `Range: bytes=-22`
  and `Accept-Encoding: identity` answers `206` without a redirect, with `content-range: bytes
  1670805328-1670805349/1670805350` and `accept-ranges: bytes`; the central directory of 2.1.0 has 417 KB. The
  record of the concept DOI, `https://zenodo.org/api/records/20133182`, answers `302` with `Location:
  /api/records/23275336` and then the JSON of that record (`id`, `doi`, `metadata.version`,
  `metadata.publication_date`). The answers are recorded in `tests/fixtures/pl/camels/`.

What exists: the collection engines of ADR-042 (descriptors with typed channel parameters, no provider), the national
file of PGW stored 1:1 under the label of its edition (ADR-059), the versioned store (ADR-036), plain mode (ADR-054)
and the consumer fixtures of `kartograf.testing` (DEV-10.6). No file of Kartograf carried a provider line of DEV §20
(`CLAUDE.md`, Deviations, DEV-20). The group `hydro` has the products `network` (HY-NET, CZ) and `pgw` (PL).

**Options:**
- A) Who fetches the geometry.
  - A1) Obserwator, with the rest of CAMELS-PL: rejected by the author (decision 6; ECO-086, Rejected).
  - A2) Kartograf, a product of `hydro` (chosen).
- B) How the two files are read.
  - B1) The whole ZIP (1.67 GB) for 96 MB of GeoPackages, on every read.
  - B2) The shapefile that the release also holds (Nogat plan: `CAMELS_PL_catchments.gpkg` and `.shp`): several
    members for the same features, where the GeoPackage is one file with its CRS and layer.
  - B3) The two GeoPackages by HTTP range requests of the ZIP (its central directory, then the two members: 55.5 MB
    of transfer), the whole ZIP only when the server does not answer a range request with the range (chosen).
- C) Which release is read.
  - C1) The one the concept DOI resolves to, unchecked: a new layout, new bytes or another licence would reach the
    store unnoticed.
  - C2) A table of the releases Kartograf checked, each pinned by the length of its ZIP and the size, CRC and
    SHA-256 of each member (chosen).
- D) A call without `--version`.
  - D1) An error that names the versions: the rule of no default that chooses data (`CLAUDE.md`, rules for code;
    ADR-044).
  - D2) The newest release Kartograf supports, as the Nogat plan designs it and ECO-086 states ("takes the newest it
    knows and cites the exact one") (chosen). The sidecar `request` names the release read, so the rebuilt command
    pins it.
- E) The names of the files in the store.
  - E1) The published names (`CAMELS_PL_catchments.gpkg`, `CAMELS_PL_gauging_stations.gpkg`): not the unit names of
    rule 10 of ARCHITECTURE 3.3 (lower case, `-` between the words of a token).
  - E2) Kartograf's unit names in the national slot, `country/pl_catchments.gpkg` and
    `country/pl_gauging-stations.gpkg`, the bytes as published and the published member path in the sidecar
    (chosen; the coordinator's decision).
- F) The version label.
  - F1) The version of the release read (`2.1.0`) or F2) its date: reading 2.0.0 and then 2.1.0 would give the
    same bytes two labels.
  - F3) The download date (`downloaded`): it says nothing of the source.
  - F4) The date of the first supported release with these bytes, `label_source="edition"` (chosen): one label per
    content, a date as the edition labels of ADR-059.
- G) The freshness signal.
  - G1) `none`, as PGW (ADR-059 D4): `--check` would say `unverifiable`, although the registry knows the bytes.
  - G2) `metadata` (chosen): `--check` judges the local versions by the SHA-256 the registry pins for the release,
    without a transfer, and asks the record of the concept DOI for a newer release.
- H) The attribution of the files.
  - H1) Kartograf's own text in `license.attribution` and no `ATTRIBUTION.txt`, as for its other products (the
    deviation from DEV-20 in `CLAUDE.md`).
  - H2) The provider lines S, P and L of the release (DEV-20.12, the author's decision 3) in the sidecar and in
    `ATTRIBUTION.txt` of a plain write (DEV-20.5) (chosen).
- I) A ZIP that differs from what the registry pins.
  - I1) Store what the path patterns find.
  - I2) `ReleaseLayoutError` naming the version before anything is written (chosen).

**Decision:** A2, B3, C2, D2, E2, F4, G2, H2 and I2.

1. **Product.** `hydro download --product camels --country pl --whole-country [--version X.Y.Z]`
   (`download_collection(product="camels", country="pl", whole_country=True, version=None)`, `check_collection` with
   the same arguments): the descriptor `pl.camels.camels` (`country` PL, `product` `camels`, `provider_name`
   `CAMELS-PL`, `storage_subdir` `hydro/pl_camels`, `default_extension` `.gpkg`, licence `CC-BY-4.0`). Its key follows
   ADR-044 D7: `<country>.<provider>.<name>`, the name a token of the `data/` path `hydro/pl_camels`. One channel:
   `DIRECT_FILES`, capability `country_files`, EPSG:2180, `update_signal="metadata"`, endpoint
   `https://zenodo.org/api/records/`, parameters `ReleaseFilesParams`. The only selection is `--whole-country`
   (another one is a `validation_error` that names it); `--year`, `--format`, `--level`, `--lod` and the other content
   options, `--layers` and a `--horizontal-crs` other than EPSG:2180 are a `validation_error`, and so is `--version`
   with another product (`collections.version_not_applicable`).
2. **Engine `release_files`.** New channel parameters in `sources/descriptor.py` (members of `ChannelParams`):
   `ReleaseFile(theme, pattern)` (a file of every release: `theme` names it in the store, `pattern` is a regular
   expression searched in the path of every ZIP member), `ReleaseMember(theme, path, size, crc32, sha256)` (what a
   release holds for a file, as checked when the release was added), `DatasetRelease(version, record, doi, published,
   url, size, members, refusal)` and `ReleaseFilesParams(dataset, files, releases, concept, concept_doi, lines)`.
   `download/releases.py` (`choose_release`, `release_lines`, `holders`, `release_jobs`, `run_release`,
   `plan_release`, `newer_release`) reads them; `download/collections.py` calls it from `run_request` and
   `plan_request` instead of the unit jobs. The transport: `transport/zip_range.py` (`read_directory`, `fetch_member`,
   `local_directory`, `extract_member`) on `transport/http.py` (`fetch_range`, `require_partial`, the reason
   `RANGE_UNSUPPORTED`, `download_to(headers=)`), with the retries of every request (DEV-13.2) and read timeouts of
   60 s (the central directory), 30 s (the record of the concept DOI) and 120 s (a member, its local header
   included, or the whole ZIP).
3. **Releases.** The registry knows 1.0.0, 2.0.0 and 2.1.0 (Context). 1.0.0 carries its `refusal` and `--version
   1.0.0` is a `ValidationError` (`option="version"`, `allowed` 2.0.0 and 2.1.0) whose text names the release and why,
   before any request; a version the registry does not know is the same error, which says that a newer release is
   read by the Kartograf release that adds it. Without `--version` the newest supported release is read, 2.1.0. The
   files are found by the patterns `(?:^|/)CAMELS_PL_catchment_boundaries/catchments/CAMELS_PL_catchments\.gpkg$` and
   `(?:^|/)CAMELS_PL_catchment_boundaries/gauging_stations/CAMELS_PL_gauging_stations\.gpkg$`, whatever the root. The
   concept record only tells of a newer release: when the record it resolves to is none the registry knows, the
   `info` notice `newer_release` names its version, record, DOI and date. A new release enters by a Kartograf patch
   release that adds its row after checking its layout: the length of the ZIP and the size, CRC and SHA-256 of each
   member.
4. **Reading.** `read_directory` asks the last 1 MiB of the ZIP (`TAIL_BYTES`) and, for a directory that begins
   before it, the directory itself (a ZIP64 end record through its locator). Checked in this order, before anything
   is published: the length of the ZIP equals the registry's; each file is found by its pattern exactly once; its
   entry has the size and CRC the registry pins and a method Kartograf unpacks (stored 0 or deflated 8,
   `READ_METHODS`; not encrypted); then each member is fetched (its local header, then its compressed bytes by
   `download_to` with a `Range` header and `require_partial` as `validate`), unpacked, checked against the size and
   CRC of its entry and its SHA-256 compared with the registry's. Only then are both files published. Before the
   transfer the `warning` notice `whole_country_size` gives the size of the files, the bytes to transfer and the size
   of the ZIP. A server that answers a range request without that range (`200`, no or another `Content-Range`) raises
   `DownloadError` with the reason `RANGE_UNSUPPORTED`, which the engine catches: the `warning` notice
   `whole_archive`, the whole ZIP downloaded into the staging directory (`Accept-Encoding: identity`), its length
   checked, the members read with `zipfile` under the same checks, the ZIP removed.
5. **Store.** The segment `hydro/pl_camels`, the national slot `country/` and one unit per file,
   `<country>_<theme>`: `hydro/pl_camels/country/pl_catchments.gpkg` and
   `hydro/pl_camels/country/pl_gauging-stations.gpkg` (standard paths, hard links), the versions
   `hydro/pl_camels/versions/country/<label>_<sha8>/pl_catchments.gpkg` (and `pl_gauging-stations.gpkg`). The names
   are unit names Kartograf declares before the transfer, the same in a plain write (DEV-19.5). The bytes are those
   of the members as published: no layer, field, geometry or CRS is changed, and the 3 invalid geometries stay as
   published. The published member path is `extra.source.member` of the sidecar.
6. **Versions and signal.** The label is `published` of the first supported release whose member has these bytes,
   `label_source="edition"`: `2026-10-07` for both files of 2.0.0 and 2.1.0, so reading 2.0.0 and then 2.1.0 makes no
   new version. In the store a file whose pinned SHA-256 is already a version of its slot is that version, without a
   request (status `local`); `update="force"` reads it again (the same bytes: `unchanged`); `update="upgrade"` also asks
   the concept record. `--check` (`plan_release`) transfers nothing: `current` when a version has the pinned bytes,
   `newer` when the slot holds other bytes only, `missing` without a version; `available_label` is the label of the
   release's bytes and `available_signal` `{version, record, sha256}`. A plan asks the concept record (a failed request
   is the `warning` notice `check_failed`); a run asks it when it reads the ZIP or with `update="upgrade"`, and a failed
   request is only a log record.
7. **Sidecar** (`kartograf-meta/1`, both files): `dataset` `pl.camels.camels`, `provider` `CAMELS-PL`,
   `horizontal_crs` EPSG:2180, `request` `{"whole_country": true, "version": "2.1.0"}` (the release read; with
   `horizontal_crs` when given), `license` `{"id": "CC-BY-4.0", "attribution": "<S>\n<P>\n<L>", "url":
   "https://creativecommons.org/licenses/by/4.0/"}`, `extra.source` `{url, member, crc32, read}` (`read` is `range`, or
   `archive` after the fallback), `extra.release` `{version, record, doi, published}` of the release read,
   `extra.releases` (every supported release with these bytes, oldest first, each as `extra.release`),
   `extra.attribution` (the lines as a list) and `extra.version` `{label, label_source}`; no `extra.http`.
8. **Provider lines.** S, P and L come from `_data/provider_lines.json`, the table of provider lines and the terms
   lines of DEV §20 copied byte for byte, through `kartograf.attribution` (`provider_lines`, `merge_lines`,
   `plan_attribution`, `write_attribution`, `ATTRIBUTION_FILE`), in the order of DEV-20.4: S, P, L. L names the
   release read: its version, the year of its `published` and its DOI, never the concept DOI. The lines are data of
   the standard, not texts of the message catalog (ADR-053): Polish with diacritics in every language, never literals
   in the code. The descriptor's own `license.attribution` (`messages/legal.py`) is the text of `list-sources`; the
   sidecar of a file carries the lines instead. The other products keep the deviation from DEV-20 of `CLAUDE.md`, and
   no JSON document carries `attribution` or `terms_notice`.
9. **Plain mode.** `--whole-country -o DIR` reads the ZIP on every run (no store to reuse) and writes
   `DIR/pl_catchments.gpkg`, `DIR/pl_gauging-stations.gpkg` and `DIR/ATTRIBUTION.txt` (DEV-20.5): the lines one per
   line, UTF-8, merged into an existing file in the order of DEV-20.4, none removed, so `--force` does not matter for
   it; it is listed in `files[]`. An existing `ATTRIBUTION.txt` that is no readable UTF-8 file is `conflict`
   (`output_exists`) before any request, and with `--force` the lines alone replace it. The plan (`--check -o DIR`)
   lists it as `write`, `replace` (it lacks a line, or it is unreadable and `--force` is given) or `conflict`, and
   not at all when it holds every line; besides the record of the concept DOI, a plain plan asks nothing.
10. **Errors.** `ReleaseLayoutError` (`kartograf.exceptions`, exported from `kartograf`; a `DownloadError` with the
    registry code `data_error`, `details.reason` `release_layout`, exit 7; attributes and `details` `version`,
    `record`, `url`, `member`; the hint names the DOI of the release) for a ZIP of another length, a file found by its
    pattern not exactly once, a member of another size, CRC, method or SHA-256: nothing is written, and retrying does
    not help, a Kartograf release that checked the new layout does. A member damaged on the way (it unpacks to another
    size or CRC than its directory entry) and a failed request are a `DownloadError` (`source_unavailable`). Both
    end the request before anything is published: the members are read and checked in the staging directory first.
    A refused or unknown version is a `validation_error` before any request. The catalog of `hydro download` declares
    `data_error` (a new `errors` parameter of `collection_commands`).
11. **Catalog and command line.** `hydro download` gets `--version VERSION` (`version`, kind `str`; `allowed` from the
    registry, 2.0.0 and 2.1.0; no CLI `choices`, so the library explains a refused or unknown version), the rule
    `applies_to` `version` -> `product` `camels`, two examples (the newest release; `--version 2.0.0`) and the meanings
    of the value `camels` and of a version `X.Y.Z` (`catalog/meanings.py`). `kartograf.commands.parse_command` takes
    `--version` as the program's flag only before the group, so `hydro download ... --version 2.0.0` is a call, while
    `--version` before the group and `-h`/`--help` anywhere stay a `UsageError`.
12. **Rebuilt commands and the read API.** `command_for_file` rebuilds `kartograf hydro download --product camels
    --country pl --whole-country --version <request.version>`; `describe_segment("hydro/pl_camels")` knows the segment
    and `iter_store(root, segment="hydro/pl_camels")` lists its files (`store.py`).
13. **Consumers** (DEV-10.6). `kartograf.testing.build_camels_archive(path, *, version=None)` writes a tiny ZIP in the
    published layout of 2.0.0 or 2.1.0 (the root, the two members the registry names, each after its `.prj`, the
    directory entries, deflated, fixed dates) with GeoPackages built from `_data/camels_fixture.json`: six gauges of
    2.1.0 with their published codes, names and points (149180100 Skoczów, 149180110 Ustroń-Obłaziec, 149180120
    Górki Wielkie, 149180140 Wisła, 150210070 Wampierzów as a MultiPolygon of two parts, 151230030 Okuninka with a
    ring self-intersection) and fictional rectangle catchments nested as the published ones (149180140 in 149180110
    in 149180100; 149180120 in 149180100); both releases hold the same GeoPackage bytes.
    `build_camels_store(root, *, version=None)` runs the real `run_release` against a copy of the registry that pins
    the fixture bytes, its range requests answered from memory, and returns `CamelsFixture(root, release, catchments,
    gauging_stations)` (`FixtureFile`s with one version labelled `2026-10-07`); `CAMELS_DATASET` and `CAMELS_SEGMENT`
    name the dataset and the segment.

**Consequences:**
- `hydro` holds two PL products and one CZ product; the texts of the group, `--help`, `list-sources`, the MCP tool
  `kartograf_hydro_download` (`version`), `AGENTS.md`, `llms.txt` and the generated tables of `docs/USAGE.md` follow
  the catalog and the error registry.
- A read transfers about 55.5 MB of a 1.67 GB ZIP; only a server that ignores range requests costs the whole ZIP
  (`whole_archive`).
- Kartograf reads only the releases it checked. A new release that holds the same bytes is a registry row and no new
  version; one with other bytes is a new version under the date of that release; one with another layout is a
  `ReleaseLayoutError` until a Kartograf patch release checks it, and `newer_release` tells of it meanwhile (another
  release is announced for December 2026, Nogat plan).
- The CAMELS-PL files are the first of Kartograf with the lines of DEV §20; the GUGiK, ISRIC and ČÚZK products keep
  the deviation of `CLAUDE.md`, and a plain directory written for both kinds holds the lines of CAMELS-PL only.
- A version sidecar is never rewritten (ADR-036): its `extra.release` and `extra.releases` name the release read and
  the releases the registry knew when the version was written.
- Obserwator (Nogat plan step 3) reads the two files from the store and carries the lines on (DEV-20.6); the repair
  of the 3 invalid geometries, the upstream gauges and the rest of CAMELS-PL (provider `CAMELS`, decision 7) are
  Obserwator's.
- Out of scope: the shapefiles, the attributes, the signatures, the forcing and the simulations of CAMELS-PL, and
  release 1.0.0.
