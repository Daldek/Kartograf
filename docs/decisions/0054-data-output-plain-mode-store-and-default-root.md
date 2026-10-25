# ADR-054: Data output: plain mode, the store and the default root

**Date:** 2026-10-25
**Status:** Accepted (the author approved the Nogat convention on 2026-10-24; this ADR applies it to
Kartograf); supersedes ADR-048 of the branch `claude/vigilant-faraday-finqvd` (documents only, never merged;
its decisions D12 and D13 are adopted, see decision 15); amends ADR-028, ADR-032, ADR-033, ADR-036, ADR-040,
ADR-045, ADR-050, ADR-051 and ADR-052
**Standard:** Nogat 2.1: DEV-19.1 to DEV-19.20, DEV-18.2, AGI-3.4, AGI-5.8, ERR-1, ECO-051; plan
`docs/plans/2026-10-24-data-output.md` of Nogat (item 2)

**Context:** Since 0.8.0 every command that writes data writes the versioned store (ADR-036), and `-o` /
`--output` is the root of that store. A user cannot fetch one file into an ordinary directory, and on a file
system without hard links (FAT, exFAT, the macOS SMB client) nothing can be fetched at all, while the library
users (Hydrolog: `download_soil`, `calculate_hsg`) want plain files. The branch
`claude/vigilant-faraday-finqvd` drafted an answer on 2026-10-23 (ADR-048: `-o` is a plain directory, `--store`
the store, one of them required, no flag to replace a file, Kartograf alone). On 2026-10-24 the author approved
the Nogat convention ECO-051 / DEV §19, which gives every tool with a store the same two modes with the same
names, defaults, errors and results (AGI-1.2), and rejected that variant (it gives `--output` to a directory
and `--store` to the store against AGI-3.4, makes "neither" an error although the store has a default place,
has no `--force`, and leaves IMGWTools with its own names). Kartograf 0.8.0 is untagged, so the breaking
changes land before the first release and no data is migrated (ECO-020).

**Options considered:**
- (a) The variant of the branch (ADR-048): rejected by ECO-051 for the reasons above.
- (b) One convention for every writing command, as DEV §19 says (chosen): `--output-dir` (`-o`), `--root`,
  the default store, `--force`, the markers, `files[]`.
- (c) A store library shared with IMGWTools: rejected in the Nogat plan (a dependency between the projects; the
  layouts differ, and a marker file name needs no import).
- (d) Leave the store as the only target and add `--output-dir` to the library only: the same call would still
  mean different things in the two store tools.

**Decision:**
1. **Names (DEV-19.1).** `output_dir` (`-o`, `--output-dir`, `path_role` output) writes plain files, `root`
   (`--root`, `path_role` root) writes the store. Neither is required. They are one exclusion group in the
   catalog (`one_of` `target`): giving both is `validation_error` with `details.reason` `exclusive_options`,
   `details.option` `root` (the second of the pair) and `details.options` `["output_dir", "root"]`, in the
   library, the CLI and MCP alike (the CLI parser does not exclude them itself, so the answer is the same
   document). `--output` (one file) is not declared: Kartograf has no command that writes exactly one file.
   Removed without an alias: `-o` / `--output` as a store root and `output_dir` as the name of a store root in
   every function (`download_data`, `download_collection`, `download_landcover`, `download_soil`,
   `calculate_hsg`, the track functions `download_laz_area`, `download_pl_cutout`, `download_image_cutout`,
   `download_cz_*`, their `check_*` twins and `validate_*`, `run_command`, `check_command`, `validate_command`,
   `init_project`), in `DownloadManager`, `LandCoverManager` and `HSGCalculator`, in the read API
   (`list_segments`, `list_partitions`, `iter_store`, `describe_store`, `list_store_entries` and the `root` of
   `StoreOverview` and `StoreEntries`), in `Project.output_dir` and in the `output_dir` key
   of `kartograf-project/1`. All of them are `root` now. `DownloadManager(provider, *, root=None,
   output_dir=None, ...)` takes the provider first, as the target options are keyword-only.
2. **Default root (DEV-19.2, DEV-18.2).** A command given neither writes the store at the first of `--root`,
   `KARTOGRAF_ROOT`, `[kartograf] root` of `nogat.toml` and `<data_dir>/kartograf` (`kartograf.store_root()`,
   the read-only accessor that returns the root, its source and whether its marker exists without
   reading the store; IMGWTools has the same; `kartograf config show --json` names the root, its source, whether
   it exists and its size). The store commands that only read (`store overview` and `store entries`) use it
   too. A project has the root of its manifest: `project init` without `--root` writes
   the resolved default root, as an absolute path, into the manifest, and every other project command reads
   it from there. The metadata cache stays in `<cache_dir>/kartograf` (ADR-050): no command writes into the
   current directory.
3. **Plain mode (DEV-19.4 to DEV-19.9).** One engine, `kartograf.output`, written once and used by every
   track at the seam `fetch_version` (a `FileSlot` of a plain target answers to the same call as a store
   slot), by the three tracks that have their own write (`DownloadManager._download_version`, the CZ
   orthophoto `cz_orto._download`, the BDOT10k files of `LandCoverManager`) and by `calculate_hsg`.
   *Names:* a file has the name it has in the store (`FileSlot.name`, known before the transfer; the
   extension of a PL sheet comes from its index record, which is asked before the first byte). The directory
   is flat: within one request the unit names are distinct by construction, so Kartograf declares no sub-path;
   a collision would be caught by the preflight. *Preflight:* the full target list is built and checked before
   the first byte of the request, in the order duplicate names (`conflict`, `duplicate_output_name`), a store
   (`output_in_store`), existing targets without `--force` (`output_exists`); the error lists every path of
   all reasons in `details.paths`. The list is the plain plan of decision 6, so `--check` and the run agree;
   a request over two countries (`--country auto`) is checked as one list. *Writing:* each file goes to
   `<output_dir>/.kartograf-incoming/<host>_<pid>_<token>/`, is verified there (the format checks of the
   track), hashed in one chunked pass (size and SHA-256 without reading the file into memory) and moved
   with `os.replace`; the staging directory is removed on success, on error, on SIGINT and on SIGTERM
   (`kartograf.interrupt.sigterm_interrupts`), leftovers older than 24 hours are removed by the next run, and
   a target that appeared after the preflight is not replaced without `--force`. The output directory is
   created if missing. There is no sidecar, no hard link, no `versions/`, no standard path and no
   `full_sheet/`: plain mode works on FAT, exFAT and SMB. `--force` replaces the existing targets (each by
   `os.replace`) and deletes nothing else; in the store `--force` keeps its meaning (fetch again: a new version
   or `unchanged`, nothing is overwritten). The API spelling of `--force` stays `update="force"` in both modes.
4. **Selection (DEV-19.4).** In plain mode a command selects what it selects in the store, with one declared
   exception, the PL sheets (NMT, NMPT, orthophotomaps): decision 5. The year options `--year`,
   `--min-year` and `--max-year` filter the admissible flights exactly as in the store (ADR-032), including the
   error of a sheet whose data lie only outside the range. LAZ, CZ sheets and tiles, cutouts, collections,
   land cover, soil and HSG select as in the store.
5. **PL sheets in plain mode (adopted from ADR-048 D12 and D13).** One file per sheet, the newest FULL flight
   (`full_sheet is True` of the index record, ADR-033; a record that does not declare it is not full) within
   the year bounds, not the newest flight: a file in a plain directory has no sidecar that says it is partial.
   A sheet without a full flight in the range is skipped: a warning notice `skipped_incomplete` names the sheet
   and its newest partial flight and the hint `--root` (the store takes the newest flight, partial or not),
   and `skipped[]` of the domain result lists `{id, reason, message}` with `id` the sheet and `reason`
   `skipped_incomplete`. The skip does not stop the task: the other sheets are written. When every sheet is
   skipped the request fails: each sheet is a failed unit with the code `no_data` and the reason
   `skipped_incomplete` (the status `failed`, exit 11, as for a request with no coverage). The rule applies
   only to plain mode and is written in USAGE, ARCHITECTURE 4.1, the `--help` and the catalog description of
   `--output-dir`, and the docstrings of the library functions. `--full-sheet` is accepted with `--output-dir`
   and has no effect (plain mode takes the full flight anyway): one `info` notice `full_sheet_redundant`.
   `--all-campaigns` (several flights of one sheet would be several files of one name) is store-only
   (decision 11).
6. **Plan (DEV-19.10, AGI-3.4).** `--check` replaces `--check-updates` (the API option and the MCP argument
   are `check`); it is the only plan, in both modes, and `check_command` returns the same plan as the CLI.
   In the store it is the plan of ADR-036 (`current`, `newer`, `missing`, `unverifiable`, `check_failed`).
   In plain mode each target is an item with `action` (`write`, `replace` with `--force`, `conflict`), `path`
   and, for a conflict, `reason` (`duplicate_output_name`, `output_exists`, `output_in_store`); the `status` is
   `missing` for `write` and `unverifiable` for the others, as in IMGWTools. A plan that lists conflicts is a
   successful result (`ok`, exit 0); only the run fails with `conflict`. `kartograf-plan/1` gains `mode`
   (`store` or `plain`) and `output_dir`, and its `store` key is renamed `root` (a plan file of 0.8.0-dev is not
   read: make a new one).
7. **Output in a store (DEV-19.11).** An `output_dir` that is, lies in, or would enter (through a unit
   sub-path) a directory that holds `kartograf-store.json` or `imgw-store.json` is `conflict`,
   `details.reason` `output_in_store`, and the hint names `--root`. The check reads marker file names only;
   nothing is imported from IMGWTools. A directory with a store somewhere below it is a fine output (the
   default store `<data_dir>/kartograf` lies below `<data_dir>`). The directory itself is judged before any
   request (`kartograf.output.directory_refusal`, `details.paths` the directory, so no list of targets and
   no index request is needed); a subdirectory that a unit would enter is judged with the list of targets.
8. **Store marker (DEV-19.12 to DEV-19.14).** `kartograf-store.json`, schema `kartograf-store/1`, with
   `schema`, `tool` (`kartograf`), `created_at` (UTC, ISO 8601 with offset) and `producer_version`. The first
   write into a missing or empty root creates it (`kartograf.marker.prepare_store`, called by every store
   write); `kartograf store init [--root DIR]` (new command, store group, store-only) writes it, and
   verifies first the layout of a root that has one and no marker: the top level holds registered product
   directories only and every sidecar is `kartograf-meta/1` (`data_error`, `invalid_layout` with the problems
   listed). A root with the layout of the store (a `versions/` directory under `<product>/<variant>/`, or the
   0.7.x `kampanie/`) and no marker is `store_unavailable`, `details.reason` `no_marker`, and the hint
   `kartograf store init --root <path>`; a root that is not empty and has neither is `conflict`,
   `not_empty`. A store never nests (DEV-19.14): before a write the command looks for `kartograf-store.json` and
   `imgw-store.json` in the ancestors of the root, at the root (the marker of the other tool) and below it
   (the product trees of this store are not entered), and a nested store is `conflict`, `nested_store`.
   The refusal comes before any request or unit of work (erratum 2026-10-25: the first unit of a list
   of sheets used to meet it, after the index had been asked, and a worker thread reported it as a
   failed unit of the code `source_unavailable`, so the registry code and reason were lost): the
   command looks at the root (`kartograf.output.guard_store`) and, for a plain write, at the
   directory (`directory_refusal`, `output_in_store`, `details.paths` the directory), and the
   refusal is its error, with its own code, reason and exit code, in every track and in
   `project download`. The plan (`--check`) creates nothing and asks nothing: a root that is a
   `conflict` (`nested_store`, `not_empty`) is listed as the one position of the track `store`
   (`action` `conflict`, `reason`, the root as `path`, `status` `unverifiable`) and the plan is `ok`
   (DEV-19.10; IMGWTools lists `nested_store` the same way), and `check_project` lists a `conflict`
   entry of every selected task; a root with the layout and no marker (`store_unavailable`) or with an
   unreadable marker (`data_error`) fails the plan with the same error as the run it plans would.
   The read commands and the read API (`list_segments`, `iter_store`, ...) do not
   require the marker: the consumer decides what to do with an unmarked store (Archiwista's probe follows
   DEV-19.12 and DEV-19.13).
   `kartograf.testing` builds its stores with the marker.
9. **Sidecar (DEV-19.16).** `kartograf-meta/1` gains the optional fields `producer` (`kartograf`) and
   `producer_version` beside `kartograf_version`, which stays; nothing is renamed. The typed `Sidecar` of the
   read API has both. The thirteen fields of DEV-19.16 exist in the sidecar, with `dataset_key` derived on
   read.
10. **Results (DEV-19.19).** Every download report of `kartograf-download/1` lists `files[]` as `{path,
    size_bytes, sha256, status}` instead of `files[].file.path` and the other fields of the file, plus the
    `unit` and the `country` of the request that the project pins and the envelope `items[]` need; in the
    store the entry keeps `label` and `version_path` (the immutable version file; `path` is the standard
    path, as before). The status is `written` or `replaced` in plain mode and `new`, `unchanged` or
    `relabeled` in the store: the file statuses `local` (the local version was used, no transfer) and `reused`
    (a derived file whose inputs match a version) are `unchanged` in the document, and the Python attribute
    `VersionedFile.status` keeps both words for flow control. `size_bytes` and `sha256` come from the single
    chunked read of the staged file (store: `read_content`, as before; plain: the engine). The report also
    has `mode` (`plain` or `store`), `root` or `output_dir` and `skipped[]` (decision 5). Per-unit outcomes
    stay in `items[]`.
11. **Command classes (DEV-19.17, DEV-19.18).** Store-only: `store init` and every `project` command (their
    input or result is the store), and the options `--upgrade`, `--plan` and `--all-campaigns`: with
    `output_dir` each is `validation_error`, `details.reason` `store_only_option`, `details.option` the
    option, and the hint names `--root`. A project task carries no `output_dir` either (the same error). Both
    modes: every `<group> download` (`elevation`, `imagery`, `landcover`, `soil`, `boundaries`, `cadastre`,
    `models3d`, `hydro`, `names`, `maps`, `geodesy`) and `soil hsg`. `--force` is valid in both modes (decision
    3). The catalog says which command is store-only in its description and rules.
12. **HSG (DEV-19.18).** `calculate_hsg` supports both modes: in the store the SoilGrids inputs are versions
    as before; in plain mode they are fetched into the staging directory (nothing of them is kept) and only
    the HSG GeoTIFF is written to `output_dir` under its slot name. ADR-048 D11 (HSG outside plain mode) is
    not adopted.
13. **MCP (DEV-19.3, AGI-5.8).** The server writes only inside its `--allow-dir` directories and only with
    `--allow-writes` (ADR-052). The default root is a path of every writing call: when the call names neither
    `output_dir` nor `root`, the root of decision 2 must lie inside an allowed directory, otherwise
    `forbidden` with `details.reason` `outside_allowed_dirs`. `output_dir` has `path_role` output and `root`
    `path_role` root, and both are checked like every path option. Kartograf has no REST server.
14. **Calling convention.** `validate_command`, `check_command` and `run_command` keep `(command, options, *,
    ...)` of ADR-052 (decision 6 there, the gap to AGI-2.1 stays open) and take `output_dir` and `root`
    keyword-only (neither: the default root); `check_command` and `run_command` return the envelope as before.
15. **What was adopted from ADR-048 of the branch.** D1 (two exclusive targets; names differ: DEV-19.1) and
    D2 (a directory, never a file name; adopted for `output_dir`) in part; D3 (the full list first, then the
    check, then the transfer; refusal before the first byte naming every colliding name) adopted, with the
    staging directory instead of `<name>.part` (the plan itself noted that the work files of mosaics and
    warps lie beside the target) and with `--force` added; D4 (no metadata outside the store) adopted;
    D5 (only Kartograf) not adopted; D6 (`--check-updates`, `--upgrade`, `--force`, `--plan` only in the store)
    changed: `--force` and `--check` are valid in both modes; D7 (projects store-only) adopted; D8 (the
    directory is created) adopted; D9 (the name of the store, known before the transfer) adopted; D10
    (an interrupted run keeps the finished files, a rerun refuses) adopted, and `--force` makes the rerun
    possible; D11 (HSG outside) not adopted; **D12 and D13 (the newest full flight, a sheet without one is
    skipped) adopted** (decision 5); D14 (`--all-campaigns` an error, `--full-sheet` a warning, years as
    filters) adopted with `--full-sheet` an `info`; D15 (no explicit campaign) unchanged.
16. **Known limits.** The names are known before the first byte, with two steps that come first: the index
    records of the PL sheets and the tile selection of the LAZ and collection tracks ask the source for the
    list of files, which is the same query the store makes and is served from the metadata cache; no data
    file is requested before the preflight. A transfer of the plain write is not resumed.

**Consequences:** A caller writes without a flag (the default store), writes plain files with `-o`, and gets
the same names, errors, plan and `files[]` as in IMGWTools. A call that gave a store as `output_dir` or `-o`
now fails with a hint naming `--root` (a plain directory that is a store is `output_in_store`). The consumers
change with the pin: Archiwista (`Project.root`, the read API names, `probe` and the marker, the manifest key),
Retman (`root=` in the three commands and `DownloadManager`), Hydrolog (documents: `output_dir`, `files[].path`),
Hydrograf (`DownloadManager(root=...)`) and Hydraulik (`--output-dir`, `files[].path`); the list is in the
migration guide of the CHANGELOG and in PROGRESS. The first write into an existing 0.8.0-dev store fails with
`no_marker` until `kartograf store init` is run on it.

**Erratum 1 (2026-10-25, ADR-052 erratum 1):** the gap to AGI-2.1 that decision 14 keeps open is closed in part:
`validate_command`, `check_command` and `run_command` take every command of the catalog, and `store init` has a
`--check` (`check_store`).

**Open questions:**
- Whether a plain `--force` should compare the source signal before it replaces a file (it replaces on
  `--force` only, as DEV-19.9 says).
- Whether the project of a plain tree should exist (DEV-19.18 makes commands whose input is the store
  store-only).
