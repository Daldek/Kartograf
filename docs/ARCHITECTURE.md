# Kartograf architecture

**Described version:** the code of the branch that contains this file — not the state on
a specific day. Package version: `src/kartograf/__init__.py` (`__version__`);
changes per release: `docs/CHANGELOG.md`; current state of work: `docs/PROGRESS.md`;
user guide (CLI and library examples): `docs/USAGE.md`;
rules for work on the code: `CLAUDE.md`.
Measurements and verifications on live services, which the sections
below refer to, are dated in the text, and their reports are in `docs/research/`
(names with the date `RRRR-MM-DD-<topic>`).

Canonical document: README/CLAUDE.md/SCOPE/USAGE refer here; in case of conflict
ARCHITECTURE.md + DECISIONS.md decide.

Every statement about system behaviour describes the CODE in this repo, not a plan
or a spec. Where the code deviates from the spec, the document describes the code and says so explicitly.

---

## 1. Overview and design principles

**Descriptors as data.** Every dataset (digital terrain model (NMT) 1 m from GUGiK, DMR 5G from CUZK,
CORINE, SoilGrids...) is described by one `SourceDescriptor` in
`src/kartograf/sources/registry.py`: access channels, horizontal and vertical CRSs,
licence, tile scheme, directory template, default file extension. The `sources/`
module does no IO on import — it is pure data and a few lookup
functions. The registry is the source of truth for the storage subdirectory
(`storage_subdir`), the extension (`default_extension`), the licence in the sidecar
and the channel capabilities — the vocabulary of names is `sheet_files`, `bbox_raster`,
`area_files`, `admin_unit_files`, `archive_unit_files`, `country_files`,
`bbox_vector` (which of them a given dataset declares is stated by its entry
in `registry.py`). Execution logic stays in the providers —
the descriptor says WHAT the source can do and where the result should land, not HOW to download it.
The exception is the collection channels (ADR-042): typed channel parameters
(`AccessChannel.params`) configure the generic engines for unit packages,
area objects and CUZK ATOM feed files, so such a product has no
provider (section 4.10); the CZ orthophoto uses the ATOM engine in its own track
(section 4.4), and the WCS channels of the PL orthophoto cutout (`WcsCutoutParams`)
configure `GugikOrtoProvider` (section 4.3).

**A sidecar for every successful download.** Next to every data file a
`<full_file_name>.meta.json` is created with schema `kartograf-meta/1`: horizontal and vertical
CRS, `nodata`, the original task, licence, package version, a description of the
transformations performed. Sidecars are written by the **managing layers** —
`DownloadManager`, `LandCoverManager`, the PL cutout in the library
(`download/cutout.py::write_pl_wcs_cutout_sidecar`), PL LAZ tiles in the library
(`download/laz.py::write_laz_sidecar`, ADR-029), CZ LAZ files
(`download/cz_laz.py`), the HSG result
(`HSGCalculator._reuse_or_compute`, section 4.8), CZ rasters (below),
CZ orthophoto (`download/cz_orto.py`, section 4.4), the PL orthophoto cutout
(`download/orto_cutout.py`, section 4.3) and collection files
(`download/collections.py::run_job`, section 4.10)
— never the providers; a provider returns a `Path`, and the metadata is assembled one level up,
where the task context is known. It follows that a direct call of a
provider from the library (e.g. `GugikProvider.download`,
`CuzkRasterProvider.download`/`download_bbox`, `CuzkLazProvider.download`)
writes only the data file, without a sidecar — in particular the CZ raster sidecar
is written by `download/cz_cutout.py::write_cz_sidecar` for a bbox cutout
(`download_cz_cutout`, section 4.5), and for a CZ sheet code (Polish godło) by `download_cz_sheet`
(`download/cz_sheets.py`), because the CZ tracks bypass `DownloadManager` (ADR-023).
A new sidecar is always created through
`sources/sidecar.py::emit_sidecar` — the only place of the write policy
(apart from it: the copy of the version sidecar in the standard path,
`download/links.py::write_link_sidecar`, and the completion of flight information
by `update_sidecar_extra` in the link sidecar). Writing outside the versioned
store is best-effort: an error in building the metadata or in writing ends with
a warning (`logger.warning`) without interrupting the download; `emit_sidecar`
returns `None` on a build error, whereas on an ordinary write error
`write_sidecar` returns the path even though the file is missing. A provider without
`descriptor_key` (`descriptor_key` that is not a `str`) yields `None` without
a warning. The VERSION sidecar in the store (ADR-036, section 3.3) is
mandatory and written exclusively (`exclusive=True`: tmp + `fsync` +
`os.link`); without a descriptor a trimmed sidecar is created (`request`, `extra`,
`sha256`, `size_bytes`, `downloaded_at`, `kartograf_version`), and every
other error is a `DownloadError` and no version. A version sidecar never
changes (`extra.parent_requests` removed in 0.8.0; `parent_request`
describes the task that created the version).

**Transformation policy (ADR-024).** Transformations that shift the CONTENT
of a raster or leave the Czech CRSs (EPSG:5514/3045) go through
`src/kartograf/transform/crs.py` — except for the WGS84 envelope used for country recognition
and clipping under `auto` (`bbox_to_wgs84` in `download/countries.py`, also for a
bbox given in a Czech CRS) and the envelope of the geometry file in the LAZ track
(`download/area.py::geometry_envelope_2180`: `get_overall_bbox(..., target_crs="EPSG:2180")`).
Envelope conversions between PL CRSs and WGS84 (sheet selection
in `core/sheet_parser.py` and `core/geometry.py`, `bbox_to_2180` of the cutout
and TERYT discovery for non-Czech CRSs, country dispatch in the CLI,
the EPSG:2180 bbox envelope in the CORINE/SoilGrids service CRS — `transform/bbox.py::envelope_from_2180`)
deliberately use the default pyproj transformer — migration is backlog A5-6.
`transform/crs.py` has four hard rules: (1) a transformer is built only through
`TransformerGroup(..., always_xy=True, allow_ballpark=False)` — `Transformer.
from_crs` can silently return identity; (2) an empty list of operations is
`TransformUnavailableError`, never a fallback; (3) operations
of unknown accuracy (`accuracy < 0`) and above `policy.min_accuracy_m` are rejected,
and the remaining ones go through a probe at a control point (inf/NaN = rejection, this is the
case of a foreign country's grid); (4) every result passes `isfinite`.
Building the group suppresses only the pyproj warning `Best transformation is not
available` (no PROJ grid, e.g. CUZK on a clean installation): the policy chooses
by itself from the available operations, and a raw `UserWarning` would break the contract
of empty stderr in `--json` (USAGE 9.2).
The chosen operation is **pinned** (`PinnedTransform`) and, when reprojecting
a raster, FORCED on GDAL through `COORDINATE_OPERATION` — without that GDAL
chooses the operation itself, outside the policy. The axis trap is real here, not
theoretical: the pipeline comes from an `always_xy=True` transformer, while GDAL supplies
coordinates in the authoritative axis order, so `proj=axisswap order=2,1`
is added INDEPENDENTLY for the source (at the head of the pipeline) and for the target (at the
end) — every time the given CRS is northing-first (EPSG:2180,
EPSG:3045; EPSG:5514 is not). Without the correction the raster is entirely nodata,
also on the source side: measured for the PL 2180 -> 5514 track without the leading
`axisswap` — **0 of 46225 valid pixels**. The correction is computed
from `axis_info`, not assumed. After the accuracy filters the most accurate
operation is chosen, but for the datum step S-JTSK -> ETRS89/WGS 84
an additional pin EPSG:1622/1623 applies (`DATUM_STEP_PINS`), excluding
EPSG:4829 for Slovakia even when its nominal 0.5 m looks better.
The nominal accuracy of the Czech operation is 1.0 m (ADR-024, erratum 2).

**No cross-country merging (state 0.8.0).** An area task crossing
more than one country yields **separate files and separate sidecars per country**,
linked by a shared `extra.parent_request`. Kartograf does not build a
cross-border mosaic and does not harmonise the vertical datum between countries — PL and CZ files are
merged by the consumer (Hydrograf). Merging PL+CZ into one continuous
border surface (shared grid, EVRF2007 on both sides; R6, 2026-09-28,
previously recorded as a Hydrograf task) is a task with no assigned
release (`docs/SCOPE.md` 3.1; border data measured live 2026-09-29 —
section 4.6). Kartograf provides everything
such a merge requires: explicit CRS codes for both axes, `nodata`, a description of the operation used
with its accuracy, and a shared grouping key.

---

## 2. Layers and module dependencies

A graph of import edges between top-level packages of `kartograf/`.
`(l)` = an EXCLUSIVELY lazy edge (import only inside a function); without the mark =
at least one module-level import (also under `if TYPE_CHECKING:`).
`kartograf` = the main package (`src/kartograf/__init__.py`):

```
kartograf ──> core, download, providers, landcover, hydrology, cache,
        sources, transport, notices, project, store, store_geometry,
        transform, catalog, commands, error_report, sheet_info,
        source_info, cache_info, store_documents    # re-export of the public API
__main__ ──> cli
cli ──> catalog, commands, error_report, sheet_info, source_info,
        cache_info, download, landcover, hydrology, notices, project,
        sources, interrupt, kartograf
mcp_server ──> catalog, commands, error_report, download, cache, kartograf
        # SDK `mcp`, `anyio`, `jsonschema`: lazily only, in create_server
commands ──> catalog, project, download, cache, notices
catalog ──> sources, download, landcover, hydrology, providers, core,
        error_report, _version, kartograf (l)
error_report ──> transform, interrupt, catalog (l)
sheet_info ──> catalog, core
source_info ──> download, landcover, providers, sources
cache_info ──> cache, notices
store_documents ──> download, store
project ──> download, landcover, hydrology, sources, cache, catalog,
        notices, _version, kartograf (_clock)
download ──> providers, sources, transform, core, cache, notices,
        _version, kartograf (_clock), transport, interrupt
landcover ──> providers, download, core, cache, sources, notices, transport,
        interrupt
hydrology ──> core, download, landcover, cache (TYPE_CHECKING), notices,
        providers (l), sources (l), transform (l)
providers ──> sources, transform, transport, core, cache, notices,
        auth (l), download (l), interrupt
sources ──> core, kartograf (_clock), _version
transport ──> transform, core, sources, cache, notices, providers,
        interrupt, kartograf (l, __version__)
transform ──> core, sources (TYPE_CHECKING), transport (TYPE_CHECKING)
cache ──> core (TYPE_CHECKING), notices
_version ──> kartograf (l, __version__)
store ──> core, download, sources, providers (l)
store_geometry ──> core, transform, store (types under TYPE_CHECKING; at runtime
        also a lazy import of `read_sidecar`), providers (l),
        transport (l)
_clock, notices, auth, interrupt ──> (nothing internal)
core ──> (nothing except exceptions and serialization)
exceptions ──> serialization (encoder for `details()`; edges TO it
        omitted above — it is imported by kartograf, cli, core, sources,
        transform, transport, providers, download, landcover, hydrology,
        cache, project, store, store_geometry, error_report, catalog)
serialization ──> (leaf, nothing internal; edges TO it omitted, as
        for exceptions — it is imported by the result types: Document, EncodeContext)
```

**How to reconstruct the graph.** The code uses only absolute internal
imports, so the full set of edges is given by:

```bash
grep -rnE '^\s*(from|import) kartograf' kartograf/ --include=*.py
```

An edge is the package of the source file (the second component of the path
`kartograf/<package>/...`) -> the package of the target module (`kartograf.<package>`);
imports within the same package are skipped. An indented line is usually
a lazy import, but imports under `if TYPE_CHECKING:`/`try:`
at module level are indented too — the position of the statement in the AST decides (an
`Import`/`ImportFrom` node in a function body = lazy). The graph must be corrected for
every new edge between packages.

Notes that are easy to overlook:

- `store` and `store_geometry` (store read access, section 3.3.1) only read:
  they use the write rules of `download` (`links.linked_version`, the constants
  `versions`) and the `sources` registry, without `DownloadManager`; no download
  module imports `store`.
- `core` imports nothing outside `core` and `exceptions` — also lazily.
  The direction is the opposite: `providers.cuzk.sheets`
  and `core.parser_tm33` import the CZ sheet system patterns from `core.parser_registry`.
  The pinned operation (ADR-024) enters `core.bbox.transform_bbox`
  through duck typing (`transformer=`), without importing `transform`.
- `download` reaches for `transform` in `download/cutout.py` (PL cutout,
  section 4.3) and lazily in `download/collections.py` (writing the GPKG of the area
  result, section 4.10). It reaches for `transport` lazily in
  `download/cutout.py` and `download/cz_cutout.py` and at module level
  in `download/cz_sheets.py` and `download/cz_laz.py` (`response_signal`).
  `cutout.py` imports at
  module level `transform.crs` (`PinnedTransform`, `CONTENT_POLICY`,
  `WARP_MARGIN_PX`), lazily `build_pinned_transform`, `transform.raster`
  (WCS cutout warp), `transport.aaigrid`, `transport.chunks` and
  `transport.mosaic.has_valid_pixels`; `cz_cutout.py` imports lazily
  the last function (the `all_nodata` check).
  `manager.py` and `storage.py` import none of them —
  `DownloadManager` remains the sheet coordination layer.
  `download/cz_orto.py` (CZ orthophoto, section 4.4) imports at module
  level `transport.atom` (ATOM feeds, ZIP members) and `transport.http`
  (`SessionPerThread`), and lazily `providers.cuzk` (`SheetIndex`,
  `bbox_to_crs`, `wkid`); `download/orto_cutout.py` (orthophoto cutout,
  section 4.3) - at module level `transport.chunks` (`align_bbox`,
  `GridSpec`) and `providers.pl.gugik_orto` (the WCS cutout channel,
  `GugikOrtoProvider`).
- `download/collections.py` (collections, ADR-042, section 4.10) imports at
  module level `transport.http` (`SessionPerThread`, `head_signal`),
  `transport.unit_package` (unit packages) and `transport.atom` (the
  country file from the ATOM feed), and lazily - only for the
  area result - `transport.feature_bbox.fetch_features`
  and `transform.gpkg.write_gpkg`: vector GDAL (`pyogrio`) is loaded
  only when the task downloads service features. From `providers` it takes
  `providers.pl.prg.discover_teryts_for_bbox` (counties (Polish powiaty) of the area)
  and `WOJEWODZTWO_NAMES`, and lazily `providers.cuzk.raster.bbox_to_crs`.
- `cli` only translates flags into command-level function arguments
  and prints the result (Z1, Z8; ADR-037, ADR-046): it builds the parser from the catalog
  declaration (`catalog.cliparser`; `cli/_parser.py::create_parser` is a facade),
  selects the command handler by its id (`cli/_handlers.py::HANDLERS`), converts flags
  into function arguments through `catalog.kinds.convert_arguments`
  (`cli/_args.py::library_arguments`) and calls the command-level function:
  `download.data` (`download_data`/`check_data`), `download.availability`
  (`check_availability`, ADR-041), `download.collections`
  (`download_collection`/`check_collection`), `landcover.manager`
  and `hydrology`; `sheet`, `list-sources`, `list-layers`, `cache`, `store` and `commands`
  go through `sheet_info`, `source_info`, `cache_info`, `store_documents` and `catalog.build` (`list_commands`,
  `command_schema`),
  and `project add` through `commands.parse_command`. It prints the result: the `--json` mode
  (`cli/_json.py`) is the `kartograf-result/1` envelope around `Document.to_json()`, the text mode renders the same
  documents (tables, status lines, a progress bar from
  `download.manager.DownloadProgress`), and `main` turns exceptions into
  `error_report` and the exit codes of the registry (ADR-049, ADR-051). From `download` it also takes
  `download.plan`/`fetch` (plan file, `UpdateMode`, `VersionedFile`) and
  `download.options` (`output_required`, `require_product`), from `sources.variants`
  the variant tables, from `notices` the messages, from `project.commands` `task_command`.
  It does not import `providers`, `transport`, `transform`, `core` or the sheet
  selection (`tests/contract/test_cli_translation.py::test_cli_imports_no_data_logic`
  allows only `catalog` and `serialization` beyond that).
- The variant registry `sources/variants.py` (ADR-041) is pure data:
  it imports only `exceptions`, `sources.descriptor` and
  `core.parser_registry.detect_system` (CZ sheet system: `sm5`/`tm33`),
  and `sources.registry` lazily (the registry builds descriptors from the types of this
  module). It is read by `download/options.py` (validation), `download/area.py`
  (`pl_only_flags`), `download/storage.py`, `download/cutout.py` (variant
  with a WCS channel), `download/data.py`, `download/cz_sheets.py`,
  `download/cz_laz.py`, `download/availability.py`, the PL providers
  (variant, `IndexRef`) and CZ (`find_cz_variant`, `find_cz_laz_variant`)
  and `cli`.
- `download/availability.py` (report, section 4.9) imports at module
  level `providers.pl.skorowidz_wfs` (the same client and record parser
  as the sheet download), `providers.pl.prg` (land mask),
  `providers.pl.gugik_laz.laz_tile` (LAZ tile parser),
  `providers.cuzk.sheets.SheetIndex` and `providers.cuzk.raster.bbox_to_crs`
  (CZ sheets, plan B) and `transport.http` (`SessionPerThread`,
  `head_signal`); it does not import `DownloadManager` or the store.
- `project` (`model`, `commands`, `manifest`, `operations`) maps data commands
  to the `download`/`landcover`/`hydrology` library functions; it does not implement
  per-product logic. The names and kinds of data command options (`TaskCommand.options`)
  come from the catalog (`Command.task_options`; JSON <-> arguments conversion:
  `catalog.kinds`), hence the edge `project ──> catalog`. `cli/project_cmd.py` only
  translates arguments and prints the results of the project API (ADR-037, ADR-040).
- `serialization` (section 3.6) is a leaf like `exceptions`: result types inherit
  from the `Document` mixin, and `exceptions` uses the encoder in `KartografError.details()`;
  `core.bbox` imports only `EncodeContext` (the `BBox.__json__` hook).
- `catalog` (section 4.11) describes the commands: declarations in `catalog/commands/*` read the
  source registry and validator constants (`sources`, `providers`, `download`, `landcover`,
  `hydrology`) and `core` (sheet codes, bbox), and `catalog.build` takes the code tables from
  `error_report` (`ERROR_CODES`, `EXIT_CODES`). The only back edge is the lazy import of
  `catalog.hints` in `error_report` (a command example in the error hint). The library,
  including `catalog`, does not import `cli` or `mcp` (a test in a clean process).
- `commands` (KB-2..KB-5) joins `catalog` (declarations, `convert_arguments`,
  `parsed_options`), `project.commands` (validation and execution of a data task:
  `task_command`) and `download` (`UpdateMode`, `UpdatePlan`, `DownloadProgress`).
- `sheet_info`, `source_info`, `cache_info` and `store_documents` are reports with logic
  moved from the CLI (Z1): `describe_sheet`/`find_sheets` (`core`, `catalog`:
  `SheetInfo.commands` with `Param.accepts`), `list_sources`/`list_layers`
  (`sources`, `providers`, `landcover`, `download`), `get_cache_info`/
  `get_cache_path`/`clear_cache` (`cache`, `notices`), `describe_store`/
  `list_store_entries`/`read_store_sidecar` (`store`, `download`); none imports `cli`.
- `mcp_server` is the only module that touches the `mcp` SDK (and `anyio` and
  `jsonschema`), always lazily in `create_server`: `import kartograf` and `import
  kartograf.mcp_server` work without `mcp`. Tools as data are provided by
  `catalog.tools` (without `mcp`), execution by `commands`, errors by `error_report`.
- `transport ──> transform`: `transport/mosaic.py` wraps the mosaic sources
  in a VRT through `transform.raster` (`vrt_xml`, `VRT_TYPES`; module-level
  import). `transform` reaches for `transport` and `sources` only under
  `if TYPE_CHECKING:` (the annotations `FeaturePages`/`LayerPages`
  and `FeatureBBoxParams` in `transform/gpkg.py`) — there is no cycle
  at runtime.
- `transport ──> sources`: the collection engines (`transport/unit_package.py`,
  `transport/feature_bbox.py`, `transport/atom.py`) read the typed channel
  parameters (`UnitPackageParams`, `PackageVariant`,
  `FeatureBBoxParams`, `FeatureLayer`, `AtomFilesParams` from
  `sources/descriptor.py` — data without IO), and `transport/atom.py` also
  `sources.edition.edition_label` (release label); `sources` does not
  import `transport`.
- `transport ──> cache`: `transport/atom.py` keeps the index of the ATOM service
  feed in `MetadataCache` (the `atom_cache` table with the feed `ETag`, ADR-042
  D12); `cache` does not import `transport`.
- `transport ──> notices`: the collection engines (`transport/unit_package.py`,
  `transport/atom.py`) compose error messages from `notices` (`count_text`,
  `FILES`, `cli_flag`); `notices` imports nothing internal.
- `transport ──> providers`: the only edge is `transport/index_records.py`
  (file index records, ADR-043), which imports at module level
  `providers.pl.skorowidz_wfs` (`WfsIndex` and the WFS query constants). The
  reverse edge `providers ──> transport` goes to `transport.http`, and
  `transport.index_records` imports only `download.collections`, so there is
  no module cycle.
- `providers ──> download` is lazy and MUST stay that way (the `download`
  package imports `providers` at import time): validation of years and campaign selection
  from `download.campaigns` in
  `SkorowidzLayersMixin.resolve_campaigns` (`providers/pl/skorowidz.py`)
  and in `GugikLazProvider.select_tiles` (`providers/pl/gugik_laz.py`) and
  the conversion of the area to EPSG:2180 `download.area.bbox_to_2180`
  in `providers/pl/prg.py` (one rule for the PL cutout and TERYT discovery).
- `cache ──> core` exists only under `if TYPE_CHECKING:` (the `BBox`
  annotation in `MetadataCache.get_teryts_for_bbox`/`set_teryts_for_bbox`);
  at runtime `cache.defaults` imports `notices`, not `core`.
- `landcover ──> cache`: `LandCoverManager(cache=MetadataCache | bool)`
  (`True` = shared cache in cwd, `cache/defaults.py::open_cache`) imports
  `MetadataCache` at module level (annotation) and passes it to the
  providers created by name (`Bdot10kProvider(cache=)` — PRG
  responses, `SoilGridsProvider(cache=)`); CORINE has no cache.
- `landcover ──> download`: `LandCoverManager` uses the shared version
  policy (`download.fetch.use_local`/`store_file`/`inspect_version`,
  `download.plan`, `download.storage.content_segment`/`unit_slot`,
  `download.versions`), and downloads the BDOT10k yearly archive with the unit
  tasks of the collection orchestrator (`download.collections.package_job`/
  `run_job`/`inspect_job`, section 4.10); `download` does not import
  `landcover` (there is no cycle).
- `landcover ──> transport`: `LandCoverManager` selects the BDOT10k archive
  variant (`--year`, `--format`) through
  `transport.unit_package.select_variant` — without network, the same rule as
  the package engine.
- `hydrology ──> core, download, landcover, cache` exists at module level
  only under `if TYPE_CHECKING:` (annotations `BBox`, `VersionedFile`,
  `PlanItem`, `MetadataCache`...; by the graph rule this is a module-level
  import); `notices` is imported normally.
  At runtime the rest is lazy: `landcover.manager` (clay/sand/silt
  inputs as versions), `download.fetch`/`plan`/`versions`
  (HSG version), `providers.soilgrids`, `core.sheet_parser`, `core.bbox`
  (`transform_bbox`), `transform` (pinned reprojection of the `hsg_from_rasters`
  inputs) and `sources.sidecar` (`emit_sidecar`, `file_digest`).
- `sources/sidecar.py` and `download/versions.py` import `_clock` through the
  main package at module import, and `sources/sidecar.py` and
  `download/plan.py` import `_version.build_version`. Only
  `build_version()` reaches lazily for `kartograf.__version__`;
  `transport/http.py` does so lazily for the `User-Agent` header.
- The edge `download ──> providers` also reaches the CZ track:
  `download/cutout.py` and `download/area.py` lazily import the generic
  `bbox_to_crs` from `providers/cuzk/raster.py` (ADR-024); moving it to
  `transform/` stays in the backlog (plan B only renamed `dmr.py`
  to `raster.py`).

### Modules

The tree lists every `.py` module of the package (`auth/` and `cli/` collectively,
the `__init__.py` of subpackages only when they carry their own logic). Source of truth:
the `.py` files under `kartograf/`; Public API: `src/kartograf/__init__.py` (`__all__`).

Stable transport and mosaic API (since 0.7.1): `get_with_retry` (any service
URL, retry policy network/429/5xx/`Retry-After`, GET only),
`make_gugik_session`, `mosaic_and_crop`, `check_source_grid` — exported
from `kartograf`; a signature change = a breaking change in the CHANGELOG.

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providers, ...)
├── _version.py         # build_version() — dev version identifier (git, lazy)
├── __main__.py          # `python -m kartograf` = the `kartograf` script (cli.commands.main)
├── py.typed             # PEP 561 marker: the consumer's mypy sees the library's types
├── serialization.py     # Document (dataclass mixin: to_dict/to_json, `schema` as the first
│                        # key), encode/EncodeContext (encoder: Path, Decimal, BBox, Notice,
│                        # __json__ hook), SCHEMAS (registry of kartograf-*/1 schemas); leaf
├── exceptions.py        # KartografError(.code, .exit_code, .hint, DETAIL_FIELDS, .details());
│                        # ValidationError(.option, .options, .allowed) -> UsageError(.command),
│                        # ParseError (code 2); DownloadError(.sheet, .status_code)
│                        # -> NoCoverageError(DownloadError; .hints) — the source has no data for
│                        # the sheet, .hints = hints (e.g. --scale 1:2000), YearRangeError;
│                        # CacheError; InvalidSidecarError(.path) — unreadable sidecar (read_sidecar);
│                        # ForbiddenError(.option, .path, .allowed) and MissingDependencyError(.extra) -
│                        # only the MCP server (a path outside --allow-dir; no extra `mcp`);
│                        # error codes and exit codes: USAGE 9.3
├── error_report.py      # ErrorReport (kartograf-error/1), error_report(exc, command=):
│                        # exception as data (io_error, cancelled, terminated, internal_error
│                        # are built here), ERROR_CODES/EXIT_CODES - the only source of the USAGE 9.3 tables and the catalog
├── interrupt.py         # Interruption: run_parallel (pool with queue cancellation and a stop flag for
│                        # running units), check_stop, Stopped/Terminated, sigterm_interrupts
├── core/                # Base logic, no network IO
│   ├── bbox.py             # BBox, validate_bbox, transform_bbox (dense envelope: _DENSIFY
│   │                       # points per edge, transformer cache, operation pinned
│   │                       # via duck typing `transformer=`), is_czech_crs
│   ├── sheet_parser.py     # SheetParser (PL-1992), find_sheets_for_bbox (BBox from core/bbox.py)
│   ├── parser_2000.py      # Parser2000 (PL-2000), find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — computable grid of CZ 2x2 km tiles (EPSG:3045)
│   ├── parser_registry.py  # Registry of sheet systems (SYSTEMS: pl2000, cz_tm33, cz_sm5,
│   │                       # pl1992), detect_system/path_parts with strip(), CZ patterns
│   │                       # (SM5: 2 or 4 letters + 2 digits, e.g. CTES96, AS91)
│   ├── geometry.py         # Reading SHP/GPKG, resolve_layer (layer choice),
│   │                       # find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py         # Convex polygons: intersection, difference, buffer (LAZ tile selection)
├── sources/             # Source descriptors as data (zero IO on import)
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir, variants), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile;
│   │                    # collection channel parameters (AccessChannel.params, ADR-042):
│   │                    # UnitPackageParams/PackageVariant, FeatureBBoxParams/FeatureLayer,
│   │                    # AtomFilesParams (CUZK ATOM feed), WcsCutoutParams (orthophoto cutout)
│   ├── registry.py      # PL/CZ/EU/GLOBAL registry: get_source, sources_for, get_country,
│   │                    # all_countries, vertical_crs_code, resolve_vertical_crs (family ->
│   │                    # realisation), parse_pl_system, horizontal_crs_for_sheet/_for_system;
│   │                    # channel_for/channel_signal (channel by transport and layout, CZ_SYSTEM_CRS);
│   │                    # NMT/NMPT descriptors per (product, format, resolution) with variants
│   ├── variants.py      # Variant registry (ADR-041): IndexRef, FileFormat/FORMATS, ProductVariant,
│   │                    # variants(), resolution_label/parse_resolution (K2 labels),
│   │                    # source_format (hard format filter), variant_error/find_variant;
│   │                    # CZ (plan B): CZ_MODELS, cz_sheet_system, find_cz_variant/
│   │                    # cz_variant_error (raster route), find_cz_laz_variant/cz_laz_error
│   ├── edition.py       # Edition (source release, metadata signal D29), edition_label
│   └── sidecar.py       # ResultMetadata, build_metadata, write_sidecar, emit_sidecar
│                        # (the only write policy), pl_sheet_horizontal_crs, read_asc_nodata
├── transform/           # Coordinate and raster transformations; GPKG writing
│   ├── bbox.py          # envelope_from_2180 — envelope of an EPSG:2180 bbox in another CRS
│   │                    # (CORINE, SoilGrids; default pyproj transformer, section 1)
│   ├── crs.py           # TransformPolicy, PinnedTransform, build_pinned_transform, KNOWN_PATHS;
│   │                    # TransformError -> TransformUnavailableError (no safe operation)
│   ├── raster.py        # warp_to_grid — local warp onto a grid, FORCED operation (PL
│   │                    # and CZ routes); vrt_xml/VRT_TYPES for transport/mosaic.py
│   └── gpkg.py          # write_gpkg — deterministic GPKG of the feature_bbox result (pyogrio:
│                        # dedupe and sort by id, drop_fields to the sidecar; ADR-042 D5), GpkgSummary
├── transport/           # Shared transport
│   ├── http.py          # download_to (files of ALL providers; atomic write os.replace)
│   │                    # and get_with_retry (queries: WMS/WFS sheet index, WFS LAZ, WFS PRG,
│   │                    # CuzkClient.query) — the only place for retry (network, 429, 5xx;
│   │                    # Retry-After): is_retryable, retry_wait, backoff_delay;
│   │                    # make_gugik_session, SessionPerThread (session per thread)
│   ├── chunks.py        # GridSpec, ChunkLimits, Chunk; align_bbox, plan_chunks,
│   │                    # fetch_chunks — shared chunks for CUZK and GUGiK WCS
│   ├── aaigrid.py       # multipart WCS -> ASC (streaming), grid validation and atomic float32 GeoTIFF
│   ├── mosaic.py        # mosaic_and_crop — merge rasters + clipping, nodata propagation;
│   │                    # without dtype= mixed band types -> ValidationError;
│   │                    # optionally (dtype=) wrapping sources in VRT;
│   │                    # check_source_grid (grid phases, SourceGrid.off_grid), has_valid_pixels
│   ├── unit_package.py  # Unit package engine (ADR-042 D1-D2): select_variant (no network),
│   │                    # package_url ({teryt}, {woj}, {sheet}, {ku}, {theme}), fetch_package (Content-Length, ZIP
│   │                    # directory, required members, extraction of one member; 404 = NoCoverageError)
│   ├── feature_bbox.py  # Area feature engine (ADR-042 D3/D4): WFS 2.0 and ArcGIS REST —
│   │                    # fresh metadata, feature count, pages by position, completeness;
│   │                    # count_features, fetch_features -> FeaturePages (pages on disk)
│   ├── atom.py          # atom_files engine (ADR-042 D12): atom_index (service feed index
│   │                    # in cache with ETag), resolve_atom_file (dataset feed -> file, release
│   │                    # from updated), check_atom_crs, atom_segment_tokens, fetch_atom_file
│   │                    # (size = feed length), unpack_members (ZIP members 1:1)
│   └── index_records.py # File index records (ADR-043): IndexRecord, gfi_records/
│                        # records_from_gfi (WMS GetFeatureInfo link table), wfs_records/
│                        # records_from_wfs (WFS records, e.g. mesh tiles)
├── providers/           # Data providers
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT; one registry variant per provider, P10,
│   │                    # index_sheets — archive sheets from the sheet index), gugik_nmpt.py,
│   │                    # gugik_orto.py (GugikImageProvider: image sheets from the WMS
│   │                    # sheet index described by SheetIndexParams - orthophoto (GugikOrtoProvider,
│   │                    # colour), intensity, true orthophoto, oblique orthophoto (provider per
│   │                    # direction, storage_suffix); WCS cutout from registry channels:
│   │                    # coverage_choices, cutout_resolution_labels, wcs_cutout_channels),
│   │                    # gugik_laz.py (select_tiles, select_all_intersecting;
│   │                    # WfsIndex transport), bdot10k.py,
│   │                    # skorowidz.py (SkorowidzRecord, ADR-028 selection,
│   │                    # SkorowidzLayersMixin: WMS GetCapabilities/GetFeatureInfo layers
│   │                    # for orthophoto, resolve_campaigns/download_record/
│   │                    # record_source/available_years; select_campaign_records,
│   │                    # coverage_hints/no_coverage_error),
│   │                    # skorowidz_wfs.py (WfsIndex — GetCapabilities/GetFeature of the
│   │                    # WFS NMT/NMPT/LAZ sheet indexes, parse_index_feature, feature_footprint,
│   │                    # overlaps_area, sheet_frame_2180, WfsSkorowidzLayersMixin),
│   │                    # wcs.py (GugikWcsMixin — GetCoverage chunks NMT/NMPT 1 m, orthophoto),
│   │                    # prg.py (WFS PRG: land mask A00 - W02 - W03 for the cutout and availability
│   │                    # report, LandMask.burn, discover_teryts_for_bbox,
│   │                    # teryt_for_point), __init__.py (create_nmt_provider)
│   ├── cuzk/            # CUZK: client.py (CuzkClient — descriptor-driven engine: ArcGIS
│   │                    # REST query/export_image + openzu files), sheets.py (SheetIndex/
│   │                    # SheetInfo — SM5/TM33 index from KladyMapovychListu, filters out
│   │                    # redundant service choice; file_sheets — CUZK file sheets of the area),
│   │                    # raster.py (CuzkRasterProvider — NMT DMR 5G/4G and NMPT DMP OK/1G,
│   │                    # route(): openzu file or ImageServer, optionally Bpv -> EVRF2007),
│   │                    # laz.py (CuzkLazProvider — LAZ DMR 5G/4G, DMP 1G/OK without transformation),
│   │                    # ruian.py (cadastral_areas_for_bbox — KU of the area from RUIAN, CZ cadastral map),
│   │                    # __init__.py (create_cz_raster_provider — the only place for Czech
│   │                    # defaults)
│   ├── corine.py        # CORINE from Copernicus CLMS (+ WMS PNG fallback)
│   └── soilgrids.py     # SoilGrids from ISRIC (WCS)
├── _clock.py            # now() — single source of result time (sidecar, version labels,
│                        # plan); compatibility tests freeze it (frozen_clock)
├── notices.py           # Notice(level, code, message), NoticeSink, notice codes (Z3, ADR-037)
├── sheet_info.py        # describe_sheet -> SheetInfo, find_sheets -> SheetList
│                        # (kartograf-sheet/1, -sheets/1; `parse` logic moved from the CLI)
├── source_info.py       # list_sources -> SourceList, list_layers -> LayerList
│                        # (kartograf-sources/1, -layers/1; source registry, no network)
├── cache_info.py        # get_cache_info/get_cache_path/clear_cache -> CacheInfo (kartograf-cache/1)
├── config.py            # user settings (DEV-18, ADR-050): nogat.toml, KARTOGRAF_*/NOGAT_*,
│                        # get_config -> Config (kartograf-config/1), check_config -> ConfigError
├── store_documents.py   # describe_store -> StoreOverview, list_store_entries -> StoreEntries,
│                        # read_store_sidecar -> StoreSidecar (reading the store as documents, ADR-045)
├── commands.py          # command layer (KB-2..KB-5): parse_command, validate_command,
│                        # format_command, run_command, check_command, CommandCall
├── mcp_server.py        # MCP server (stdio; extra `mcp`, script kartograf-mcp): create_server,
│                        # main, build_instructions, INSTRUCTIONS; the only module touching the SDK
├── guide.py             # guide for agents from the catalog (AGI 8): agent_guide -> AgentGuide
│                        # (kartograf-guide/1), inject_block; templates in _data/agents/*.md
├── catalog/             # Command catalog - the single source of truth (section 4.11), no cli/mcp import
│   ├── spec.py          # Command, Param, Constraint, Example, Group (data; value providers from the registry)
│   ├── model.py         # documents kartograf-command-list/1 and kartograf-commands/1: CommandList, GroupRow,
│   │                    # CommandRow, CommandCatalog, CommandEntry, OptionEntry, EnumValue, ResultEntry,
│   │                    # EffectsEntry, ExampleEntry, I18nEntry, PolishTexts
│   ├── build.py         # list_commands(), command_schema(command), is_option, effects; entries built once
│   ├── shared.py        # shared command parameters (area, output, update modes, --json...)
│   ├── kinds.py         # value kinds: flag text parsers, convert_arguments (JSON options ->
│   │                    # library arguments), options_from_json/options_to_json
│   ├── cliparser.py     # argparse parser from declarations: build_parser, parse_command_line, parsed_options
│   ├── formatting.py    # canonical command line (format_command_line)
│   ├── hints.py         # example_for, usage_hint (example in the error hint)
│   ├── tools.py         # MCP tools as data: tool_specs, hidden_tools, task_paths, parse_families, FAMILIES
│   └── commands/        # declarations, one module = one group (elevation, imagery, landcover, soil, boundaries,
│                        # cadastre, models3d, hydro, names, maps, geodesy, project, misc: parse, catalog,
│                        # cache and API-only commands); _collection.py = shape of the collection groups
├── store.py             # Read-only store access (ADR-045, 3.3.1): list_segments,
│                        # list_partitions, iter_store -> StoreEntry (units, partition,
│                        # skip_versions), read_sidecar -> Sidecar, describe_segment
│                        # -> SegmentInfo, link_target
├── store_geometry.py    # file_footprint -> Footprint (task bbox, sheet code, header,
│                        # unit index), pinned_transform (envelope policy, per thread)
├── cache/metadata.py    # MetadataCache — SQLite WAL, thread-safe; tables record_cache,
│                        # campaigns_cache, teryt_cache, teryt_bbox_cache, index_area_cache
│                        # (availability report; area records of the WFS tile index),
│                        # atom_cache (ATOM feed indexes with ETag;
│                        # TTL 7 d, DEFAULT_TTL_SECONDS)
│                        # and sheet_cache (30 d, SHEET_TTL_SECONDS); the database file is
│                        # opened lazily, created on first write
├── cache/defaults.py    # open_cache(cache: MetadataCache | bool, force) — shared cache of the
│                        # CLI and library in <cache_dir>/kartograf/metadata.db (DEV-18.2)
├── download/            # Download: the download command (data.py) and routes
│   ├── data.py          # download_data/check_data — commands `kartograf elevation download` / `imagery download` in the library
│   │                    # (ADR-037): country and `auto`, PL area expansion, route choice,
│   │                    # parent_request, DataReport/UnitFile/UnitFailure, Notice
│   ├── options.py       # validate_request / validate_request_bbox (also bbox CRS),
│   │                    # validation of choices: product, country, format, resolution and CRS
│   │                    # (from the variant registry), system, scale, years, LAZ options,
│   │                    # CZ orthophoto (cz_orto_option_error) and orthophoto cutout; texts as in --help
│   ├── arguments.py     # Type checking of library arguments (rules for code in CLAUDE.md): require_int,
│   │                    # require_str, require_bool, require_codes
│   ├── availability.py  # Availability report (ADR-041, section 4.9): check_availability (PL, CZ, auto),
│   │                    # AvailabilityReport (kartograf-availability/1)/AvailabilityCombination/AvailabilityArea
│   ├── area.py          # Task area: bbox_to_2180, geometry envelopes,
│   │                    # parent_request_for, `auto` clipping (Notice)
│   ├── campaigns.py     # GUGiK campaigns (ADR-030): CampaignRef, format from the record,
│   │                    # verify_file_format, verify_record_url/verify_sheet_extent (B4),
│   │                    # verify_record_vertical_crs (vertical CRS of the record)
│   ├── countries.py     # Splitting an area by country: countries_for_bbox, split_bbox_by_country
│   ├── links.py         # Linking the standard path to a version (hard link only, never backwards)
│   ├── fetch.py         # Policy for files without a campaign: fetch_version, VersionedFile;
│   │                    # FileSlot.related_roots (D23 between releases, ADR-042 D7)
│   ├── plan.py          # Update plan: UpdatePlan = kartograf-plan/1 document (PlanItem.track/unit,
│   │                    # notices, ok, from_dict)
│   ├── cutout.py        # PL WCS cutout (ADR-035): download_pl_cutout/check_pl_cutout,
│   │                    # land mask, sidecar (internal steps private)
│   ├── orto_cutout.py   # PL WCS image cutout (ADR-042 D14, plan E1, ADR-044): download_image_cutout/
│   │                    # check_image_cutout (orthophoto and true orthophoto by descriptor key),
│   │                    # ImageCutoutResult, orto_cutout_error
│   ├── cz_cutout.py     # CZ cutout: download_cz_cutout/check_cz_cutout, write_cz_sidecar
│   ├── cz_sheets.py     # CZ TM33/SM5 sheet: download_cz_sheet/check_cz_sheet, CzSheetResult,
│   │                    # cz_sheet_variant (CZ raster route row, plan B)
│   ├── cz_laz.py        # CZ LAZ (plan B): download_cz_laz/check_cz_laz, CzLazResult/
│   │                    # CzLazFailure — sheet or area, thread pool, cz_laz plan route
│   ├── cz_orto.py       # CZ orthophoto (ADR-042 D13): download_cz_orto_sheet/check_cz_orto_sheet,
│   │                    # CzOrtoResult, cz_orto_sheet, cz_orto_area_sheets (SM5 index)
│   ├── cz_contours.py   # ZABAGED CZ contours (plan E1): download_cz_contours_sheet/
│   │                    # check_cz_contours_sheet, CzContoursResult, cz_contours_area_sheets;
│   │                    # SM5 sheet ZIP 1:1, http signal, cz_sheet plan route
│   ├── laz.py           # PL LAZ tiles (ADR-029): download_laz_area/check_laz_area — bbox
│   │                    # in any CRS, thread pool, tile sidecar, failures in the result
│   ├── manager.py       # DownloadManager — PL sheets (ThreadPoolExecutor), sidecars;
│   │                    # campaigns (year=, all_campaigns=, min_year=, max_year=),
│   │                    # update/plan, check_sheets, DownloadResult (return value)
│   ├── storage.py       # FileStorage — segments from registry templates (ADR-026), versions/;
│   │                    # prune_empty_dirs — cleaning up empty bbox/ after a failure;
│   │                    # content_segment (prefix + content tokens), unit_slot (teryt/bbox/
│   │                    # sheet code/country, related slots D7 — ADR-042 D8)
│   ├── collections.py   # Collections (ADR-042): download_collection/check_collection =
│   │                    # boundaries/cadastre/models3d/hydro/names/maps/
│   │                    # geodesy download commands, validate_collection_request (no network),
│   │                    # CollectionReport, unit tasks (package_job/run_job/
│   │                    # inspect_job; collection plan route), area limit (100 files,
│   │                    # 10 GB), landcover_request/run_request/plan_request (ZABAGED,
│   │                    # BDOO, Data50, Data250)
│   ├── updates.py       # Internal PL plan items (kartograf-plan/1, ADR-036)
│   └── versions.py      # Versioned store (ADR-036): exclusive write, labels,
│                        # version list, cleaning up .incoming/
├── landcover/manager.py # Public download_landcover/check_landcover (LandCoverReport),
│                        # download_soil/check_soil (SoilReport); internal
│                        # LandCoverManager, BDOT10k of an area = every county;
│                        # BDOT10k annual editions and ZABAGED, BDOO, Data50 and Data250
│                        # (COLLECTION_SOURCES) via the collection engines
├── landcover/store.py   # hsg_segment, HSG_SEGMENT_PREFIX, selection_unit (spec 3.4)
├── hydrology/hsg.py     # Public calculate_hsg/check_hsg (HsgReport),
│                        # hsg_statistics; internal HSGCalculator from the versions
│                        # clay/sand/silt (D33, reused), USDA classification -> HSG,
│                        # hsg_from_rasters
├── project/             # Project manifest (ADR-040):
│   ├── model.py         # Project, ProjectTask, PinnedFile, ProjectReport,
│   │                    # ProjectCheck and task and file results
│   ├── commands.py      # COMMANDS: JSON options (TaskCommand.options from the catalog), validation without network,
│   │                    # download (TaskDownload: plan, summary), check_* and pins per data command
│   │                    # (no per-product logic)
│   ├── manifest.py      # kartograf-project/1: validation, mkdir lock, atomic
│   │                    # write and merging of changes per task
│   └── operations.py    # Public API: init, add, remove, download,
│                        # check, status, verify and open_project
├── auth/                # proxy.py (subprocess isolating CLMS credentials), client.py
│                        # (AuthProxyClient — singleton, starts the proxy itself)
└── cli/                 # Only flag translation and result printing (Z1, Z8; ADR-037, ADR-046):
                         # _parser.py (create_parser: facade over catalog.cliparser - parser from the catalog
                         # declarations, ADR-039), _handlers.py (HANDLERS: command id -> handler),
                         # _args.py (library_arguments: flags -> function arguments via the catalog),
                         # _json.py (--json mode: json_mode, emit_document, UTF-8),
                         # download_cmd.py (download_data/check_data),
                         # availability_cmd.py (check_availability: PL and CZ tables, --details, --json),
                         # collection_cmd.py (download_collection/check_collection),
                         # landcover_cmd.py, soil_cmd.py (SoilGrids + HSG), layers_cmd.py (list-layers),
                         # sources_cmd.py (list-sources), parse_cmd.py (describe_sheet),
                         # cache_cmd.py (cache_info), catalog_cmd.py (list_commands, command_schema),
                         # project_cmd.py (project API; project add via parse_command),
                         # commands.py (main entry point: exceptions -> error_report, the exit codes of the registry)
```

---

## 3. Data contracts

### 3.1 `SourceDescriptor` and `storage_subdir` templates

`SourceDescriptor` (`src/kartograf/sources/descriptor.py`) carries: `key`,
`country`, `product`, `name`, `provider_name`, a tuple of `channels`
(`AccessChannel`), `tile_scheme`, `storage_subdir`, `default_extension`,
`license`, `resolution`, `auth` and (since 0.8.0, ADR-041) a tuple of `variants`
(`ProductVariant`, the variant registry — below). `product` = the value of
`--product` selecting the source (`nmt`, `admin`, `bdot10k`, `zabaged`;
SoilGrids without `--product` - `soil`) and the `product` field of the sidecar; the CLI group
of the source is determined by the first segment of `storage_subdir` (e.g. the products of
`landcover download` = descriptors under `landcover/`).

Since 0.7.0 (ADR-026) `storage_subdir` is a **template** with the placeholders
`{system}` and `{vcrs}`, not a literal directory name. An external consumer
reading this field directly gets the template — a deliberate trade-off; the correct way
is `resolve_subdir()`. The key and `storage_subdir` of every descriptor
are subject to the naming convention (section 3.3, rule 10; ADR-044 D7).

| Descriptor key | `storage_subdir` | `default_extension` |
|---|---|---|
| `pl.gugik.nmt_0_15m`, `pl.gugik.nmt_0_5m`, `pl.gugik.nmt_0_6m`, `pl.gugik.nmt_1m`, `pl.gugik.nmt_5m`, `pl.gugik.nmt_10m` | `nmt/pl_{system}_<label>_{vcrs}`, e.g. `nmt/pl_{system}_0.5m_{vcrs}` | `.asc` |
| `pl.gugik.nmpt_0_5m`, `pl.gugik.nmpt_0_6m`, `pl.gugik.nmpt` (1 m) | `nmpt/pl_{system}_<label>_{vcrs}`, e.g. `nmpt/pl_{system}_1m_{vcrs}` | `.asc` |
| archives `pl.gugik.<product>_<format>[_<label>]`, e.g. `pl.gugik.nmt_tbd_25m`, `pl.gugik.nmt_ascii_nmt_1m`, `pl.gugik.nmt_tin`, `pl.gugik.nmpt_xyz_0_5m` | `<product>/pl_{system}_<format>[_<label>]_{vcrs}`, e.g. `nmt/pl_{system}_tbd_25m_{vcrs}`, `nmt/pl_{system}_ascii-nmt_1m_{vcrs}`, `nmt/pl_{system}_tin_{vcrs}` | by format: `.zip` (XYZ, ASCII-NMT, TBD, TIN), `.ttn`, `.grd`, `.dxf`, `.dgn` |
| `pl.gugik.orto` | `orto/pl_{system}` (+ `_<variant>` for CIR/B-W, rule 5); WCS cutout `orto/pl_1992_<coverage>_<res>` (tokens, rule 5) | `.tif` |
| `cz.cuzk.orto` | `orto/cz_sjtsk` (SM5 hierarchy) | `.jpg` (+ `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`) |
| `pl.gugik.nmt_100m` | `nmt/pl_1992_100m` (without `{vcrs}`: vertical CRS unknown, P1); slot `teryt/<woj>` | `.zip` |
| `pl.gugik.intensity` | `intensity/pl_{system}` | `.tif` |
| `pl.gugik.true_orto` | `true-orto/pl_{system}`; WCS cutout `true-orto/pl_1992_<res>` | `.tif` |
| `pl.gugik.oblique_orto` | `oblique-orto/pl_{system}`; file `<sheet_code>_<direction>` (`FileStorage(suffix=)`) | `.tif` |
| `cz.cuzk.zabaged_contours_shp`, `cz.cuzk.zabaged_contours_dgn` | `contours/cz_zabaged_shp`, `contours/cz_zabaged_dgn` (SM5 hierarchy) | `.zip` |
| `pl.gugik.laz` | `laz/pl_{system}_{vcrs}` | `.laz` |
| `cz.cuzk.dmr5g` | `nmt/cz_dmr5g_{vcrs}` | `.tif` |
| `cz.cuzk.dmr4g` | `nmt/cz_dmr4g_{vcrs}` | `.tif` |
| `cz.cuzk.dmpok`, `cz.cuzk.dmp1g` | `nmpt/cz_dmpok_{vcrs}`, `nmpt/cz_dmp1g_{vcrs}` | `.tif` |
| `cz.cuzk.<model>_laz` (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`) | `laz/cz_<model>_{vcrs}` | `.laz` |
| `pl.gugik.bdot10k` | `landcover/pl_bdot10k` (prefix + tokens, rule 8) | `.gpkg` |
| `eu.clms.corine` | `landcover/eu_corine` (prefix + tokens) | `.tif` |
| `global.isric.soilgrids` | `soil/global_soilgrids` (prefix + tokens) | `.tif` |
| `pl.gugik.prg` | `boundaries/pl_prg` (prefix + tokens, rule 9) | `.gpkg` |
| `pl.gugik.egib` | `cadastre/pl_egib` (prefix + tokens, rule 9) | `.gpkg` |
| `pl.gugik.buildings` | `models3d/pl_buildings` (prefix + tokens, rule 9) | `.zip` |
| `cz.cuzk.zabaged` | `landcover/cz_zabaged` (prefix + tokens, rule 9) | `.gpkg` |
| `cz.cuzk.ruian` | `boundaries/cz_ruian` (prefix + tokens, rule 9) | `.gpkg` |
| `cz.cuzk.hynet` | `hydro/cz_hynet` (prefix + tokens, rule 9) | `.gpkg` |
| `pl.gugik.bdoo` | `landcover/pl_bdoo` (prefix + tokens: vintage and `--layers` classes, rule 9); slot `teryt/<woj>` | `.zip` |
| `cz.cuzk.data50`, `cz.cuzk.data250` | `landcover/cz_data50`, `landcover/cz_data250` (prefix + tokens, rule 9) | `.gpkg` (nationwide file `.zip`) |
| `pl.gugik.mesh` | `models3d/pl_mesh` (prefix, rule 9); slot `<crs>[/<zone>]/<file of the tile>` | `.zip` |
| `pl.gugik.trees` | `models3d/pl_trees` (prefix + tokens `lod1`, `2023`, rule 9) | `.zip` |
| `pl.gugik.control` | `geodesy/pl_control` (prefix + tokens: network, `xls` of the county package, rule 9) | `.gpkg` (package and archive `.zip`) |
| `pl.gugik.geoid2021` | `geodesy/pl_geoid2021` (prefix + token `evrf2007`) | `.txt` |
| `cz.cuzk.control` | `geodesy/cz_control` (prefix + network token) | `.gpkg` |
| `cz.cuzk.qgzu2013` | `geodesy/cz_qgzu2013` (prefix + token `bpv`) | `.zip` |
| `cz.cuzk.cadastral_map` | `cadastre/cz_cadastral-map` (prefix + format token, rule 9); slot `ku/<code>` | `.zip` |

The sheet channel of every PL NMT/NMPT descriptor is `WFS` (`sheet_files`,
signal `index`; the GUGiK WFS sheet index (Polish skorowidz), since 0.8.0 instead of `WMS_SHEET_INDEX`,
which remains only for orthophoto). The WCS `bbox_raster` channel for both vertical
CRSs (`EPSG:9650` KRON86, `EPSG:9651` EVRF2007) is held exclusively by
`pl.gugik.nmt_1m` and `pl.gugik.nmpt` (1 m); the other resolutions
and archives do not have it (hence the NMT/NMPT cutout is 1 m only, section 4.3).
`pl.gugik.orto` has, alongside `WMS_SHEET_INDEX` (`sheet_files`, `index`), two
`WCS` `bbox_raster` channels for the orthophoto cutout (plan D, ADR-042 D14):
`.../PZGIK/ORTO/WCS/StandardResolution` (`Orthoimagery_StandardResolution`)
and `.../HighResolution` (`Orthoimagery_High_Resolution`), signal `none`,
parameters `WcsCutoutParams` (below; section 4.3).

The CZ descriptors (plan B) have open-data file channels `DIRECT_FILES`
(`sheet_files`, signal `http`) per horizontal CRS: S-JTSK `EPSG:5514`
with Bpv heights (`EPSG:8357`) and ETRS89/TM33N `EPSG:3045` with EVRF2007
(`EPSG:5621`); the NMT/NMPT rasters also have an `ARCGIS_IMAGE` channel
(`bbox_raster`, signal `none`, `EPSG:5514`/Bpv; DMP OK: service
`dmp_obrazova_korelace`), and the raster `cz.cuzk.dmr5g` and `cz.cuzk.dmp1g`
have only this channel (the files of these models are LAZ only). A single channel
is selected by `registry.channel_for(key, transport, horizontal_crs)`
(`ValidationError` when there is none or it is ambiguous);
`channel_signal(key, transport, horizontal_crs)` returns its signal.

**Variant registry (ADR-041, `sources/variants.py`).** One PL
descriptor per (product, format, resolution), built in
`registry.py::_pl_sheet_source` from the `_PL_SHEET_SOURCES` list; the key,
segment template, extension and name are determined by the format and label.
Existing keys remain (`pl.gugik.nmpt` = digital surface model (NMPT) 1 m, `pl.gugik.nmt_1m`,
`pl.gugik.nmt_5m`). `SourceDescriptor.variants` has one
`ProductVariant` per vertical CRS: `source` (= descriptor key =
`dataset` of the sidecar), `product`, `country`, `resolution_m` (`Decimal`;
`None` for LAZ, TIN and TTN), `vertical_crs` (CLI name: `EVRF2007`/`KRON86`),
`format` (`FileFormat` token: `ASC`, `XYZ`, `ASCII-NMT`, `TBD`, `TIN`,
`TTN`, `GRD`, `DXF`, `DGN`; LAZ: `LAZ`), `systems` (`("1992", "2000")`
— the CRS in which a sheet exists is a fact of the sheet index, not of the
registry), `channel` and `index_ref` (`IndexRef(endpoint, layer_prefix)`:
the WFS service of the sheet index and the prefix of the yearly types, e.g.
`.../NumerycznyModelTerenuEVRF2007/WFS/Skorowidze` + `SkorowidzNMT`;
NMPT: `NumerycznyModelPokryciaTerenu{EVRF2007,KRON86}` + `SkorowidzNMPT`;
LAZ: `DanePomiaroweLidar{EVRF2007,KRON86}` +
`SkorowidzDanychPomiarowychLIDAR`) and `model` (CZ: `dmr5g`, `dmr4g`,
`dmp1g`, `dmpok`; PL `None`). Properties: `label` (label K2)
and `source_file` (archive = source file without conversion, cutout
and mosaic). `FORMATS` (`FileFormat`: token, name of the `format` field
in the sheet index, extension, accepted URL path endings, description,
`source_file`) describes the sheet index formats; the extension follows from the
`format` field of the record, never from the URL.

The CZ variants (plan B, `cz.cuzk.*` descriptors) are rows of the route table
(section 4.4): one per (product, label or `model`, vertical CRS
`Bpv`/`EVRF2007`, sheet system `systems=("sm5",)` or
`("tm33",)`), `format` `TIFF`/`LAZ`, `index_ref=None`; `channel` is
`DIRECT_FILES` (open-data file) or `ARCGIS_IMAGE` (ImageServer with a warp to the
TM33 tile grid). The CZ cutout is not a registry row, but the
`ARCGIS_IMAGE` channel of the descriptor.

Functions (no IO): `variants(*, product, country, vertical_crs,
resolution, system, format)` — variants in registry order;
`resolution_label(Decimal)` -> `0.15m`/`0.5m`/`10m` (`format(value.normalize(),
"f") + "m"`) and the inverse `parse_resolution(label)` (exact label
only; `0,5m`, `50cm`, `0.50m` = `None`); `source_format(format, url)`
— the token when the `format` field of the record and the URL ending indicate the same
format, otherwise `None` (hard filter, section 4.1); `variant_error`/
`find_variant` — the selection error text (list of labels per vertical CRS)
and the single selected variant (`resolution=None` selects the only label:
`GRD` 5m, TIN/TTN without resolution); `labels_by_vertical_crs`,
`format_tokens`; for CZ `cz_sheet_system` (sheet code system `sm5`/`tm33`),
`cz_variant_error`/`find_cz_variant` (raster route row; SM5 may
omit the label when the product has one label with SM5 files) and
`cz_laz_error`/`find_cz_laz_variant` (model and vertical CRS of CZ LAZ,
consistency with the sheet code system). The registry is read by: CLI/API validation
(`download/options.py`), the `--help` and `list-sources` texts,
`download/area.py::pl_only_flags`, `FileStorage` (variant descriptor),
the cutout (`download/cutout.py::wcs_variant` — variant with a WCS channel),
the PL providers (variant, sheet index services) and CZ (route, model), the CZ paths
(`download/cz_sheets.py`, `download/cz_laz.py`) and the availability report
(4.9). No other module holds a list of resolutions, vertical
CRSs or formats. The remaining descriptors (orthophoto, land cover)
have an empty `variants` tuple.

`storage_subdir` is always a string (since 0.8.0). Land cover and collection sources
have a prefix without placeholders, which `download/storage.py::content_segment`
completes with content tokens (section 3.3 rules 8 and 9, sections 4.8 and 4.10).
CORINE has two channels: `CLMS_API` (data, signal `metadata`) and `WMS`
(PNG preview, `none`, `EPSG:3857`).

**Collection channel parameters (ADR-042 D1).** `AccessChannel.params`
(default `None` = channel handled by the provider) carries a typed,
immutable engine configuration - data without IO:

| Type | Fields | Engine |
|---|---|---|
| `UnitPackageParams` | `unit` (`powiat`/`woj`/`country`), `variants` (`PackageVariant`), `unpack` (suffix of ONE member saved instead of the ZIP; `None` = ZIP 1:1), `class_pattern` (plan E4: expression searched for in the file name of each ZIP member, group `code` = class of the member; a package without a class file is not data, and a selection of `layers` classes writes a new ZIP of the files of those classes - each member byte for byte, with the name, date and compression of the source, in source order) | `transport/unit_package.py` |
| `PackageVariant` | `choice` (API/CLI options selecting the variant, e.g. `(("format", "SHP"), ("year", "2024"))`; `()` = the only variant), `url_template` (tokens only `{teryt}`, `{woj}` = first 2 digits of TERYT), `edition` (version label), `segment_tokens`, `members` (required suffixes of ZIP members), `vertical_crs` (vertical CRS declared in the 3D data), `classes` (plan E4: class codes of the release for selection by `layers`; `()` = no class selection) | as above |
| `FeatureBBoxParams` | `protocol` (`wfs`/`arcgis`, consistent with the `transport` of the `WFS`/`ARCGIS_QUERY` channel), `native_crs`, `axis_order` (`yx` = northing first in BBOX), `page_size`, `layers` (`FeatureLayer`), `selection` (`level` = one layer by `--level`, `all` = every one), `order_field` (ArcGIS `orderByFields`), `drop_fields` | `transport/feature_bbox.py` + `transform/gpkg.py` |
| `FeatureLayer` | `code` (value of `--level` or a fixed code), `source` (WFS type `ms:A03_Granice_gmin` or ArcGIS layer id), `name` (GPKG layer), `id_field` (stable feature identifier: dedupe and ordering) | as above |
| `AtomFilesParams` (plan D) | `service_feed` (ATOM service feed), `entry_pattern` (expression on the dataset feed id; group `sheet` = index key, `year` = release year in the file name; without `sheet` the feed has one dataset), `crs` (EPSG codes of the CRS category of the dataset files; `()` = one file), `members` (pairs of ZIP member suffix -> save suffix; `()` = ZIP 1:1), `segment_tokens` (+ EPSG code, when `crs` has several CRSs) | `transport/atom.py` |
| `WcsCutoutParams` (plan D) | `variant` (`--coverage`: `standard`/`high`), `coverage_id`, `native_step` (coverage step, 0.1 m), `resolutions` (result pixels: 0.1, 0.25, 0.5, 1; labels K2), `max_native_pixels` (request budget in coverage pixels, 4 Mpx) | `GugikOrtoProvider` + `download/orto_cutout.py` |

The registry tests (`tests/unit/test_sources_registry.py`) enforce: template tokens,
the same `choice` keys in the variants of a channel, keys, directories
and `edition`/`segment_tokens` per the naming convention (section 3.3, rule 10),
protocol consistent with the transport, `page_size > 0` and a collection channel capability
unique within a descriptor (`archive_unit_files`, `country_files`,
`bbox_vector`, `admin_unit_files`) - after which `build_metadata(capability=)`
selects the sidecar channel. PL collection channels:

| Descriptor (`--product`) | Channel, capability | Parameters |
|---|---|---|
| `pl.gugik.bdot10k` (`landcover --product bdot10k --year`) | `DIRECT_FILES`, `archive_unit_files` | county; 24 variants `(format, year)`: 2014-2025 x `GML` (member `.xml`) / `SHP` (`.shp`), `.../Archiwum/bdot10k/<R>/<F>/{woj}/{teryt}_<F>_<R>.zip`, `edition` = year |
| `pl.gugik.prg` (`admin`) | `WFS` `AdministrativeBoundaries`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, page 1000, `selection="level"`: `wojewodztwo`=A01, `powiat`=A02, `gmina`=A03, `jednostka-ewidencyjna`=A05, `obreb`=A06, id `IIP_IDENTY` |
| as above | `DIRECT_FILES`, `admin_unit_files` | voivodeship; `prg/granice/{woj}_GraniceAdministracyjne.zip`, member `.gml`, token `gml` |
| as above | `DIRECT_FILES`, `country_files` | country; `prg/granice/00_jednostki_administracyjne.zip` (approx. 377 MB), member `.shp`, token `shp` |
| `pl.gugik.egib` (`map`) | `DIRECT_FILES`, `admin_unit_files` | county; `InneDane/latest_exports/eziudp_wfs/GPKG/{teryt}.gpkg.zip`, `unpack=".gpkg"`, token `gpkg` |
| as above | `WFS` `UslugaZbiorcza`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, page 1000, `selection="all"`: `dzialki`, `budynki`, id `gml_id`, `drop_fields=("DATA",)` |
| `pl.gugik.buildings` (`buildings`) | `DIRECT_FILES`, `admin_unit_files` | county; variants `(lod, year)`: LoD1 2019 (`.../LOD1/2019/{woj}/{teryt}_gml.zip`, EPSG:9650), LoD1 2021/2022/2024 (`.../LOD1/<R>/{woj}/{teryt}.zip`, EPSG:9651), LoD2 2017 (`.../LOD2/{teryt}_gml.zip`, EPSG:9650); member `.gml`, `edition` = year |
| `pl.gugik.bdoo` (`landcover --product bdoo`, plan E4) | `DIRECT_FILES`, `admin_unit_files` | voivodeship; 7 `year` variants (2015, 2021-2026): `opendata/bdoo/<R>/PL.PZGiK.201.{woj}.zip`, member `.xml` (up to 2023) or `.gml` (from 2024), `edition` = year; `classes` = sum of the classes of the 16 packages of a vintage (2015: 44, 2021-2023: 37, 2024-2026: 26), `class_pattern` `__OT_(?P<code>[A-Z]{4})_[A-Z]\.`; EPSG:2180; no country-wide file |
| `pl.gugik.mesh` (`models3d --product mesh`, plan E5) | `DIRECT_FILES`, `area_files` | area tiles from WFS records `NMT/WFS/ModeleSiatkowe3D` (type `gugik:SkorowidzModeleSiatkowe3D`, `next` pages); `IndexSource(unit_field=None)`: tile = record file (`URL_do_pobrania`; the `modul` field repeats across several works and cities), label `Aktualnosc_Numer_zgloszenia_pracy`, year `akt_rok` (`--year` filter), zone `uklad_xy` (slot directory `1992` or `2000/<zone>` and the sidecar CRS); member `.obj`, `vertical_crs` EPSG:9651; `index` |
| `pl.gugik.trees` (`models3d --product trees`, plan E5) | `DIRECT_FILES`, `admin_unit_files` | county; one variant `(lod, year)` = (1, 2023): `InneDane/Drzewa3D/LOD1/2023/{woj}/{teryt}.zip` (0.3-25 GB; not every county has a package), member `.gml`, `edition` 2023, no vertical CRS (GML `srsName="EPSG:2180"`) |
| `pl.gugik.control` (`geodesy --product control --country pl`, plan E5) | 4 x `WFS`, `bbox_vector` (shared capability, ADR-043 D6) | `wfs`, EPSG:2180, `yx`, page 1000, `selection="all"`, `choice` `network`: `horizontal` (`PodstawowaOsnowaGeodezyjnaPozioma`: `Fundamentalna_pozioma`, `Bazowa_pozioma`), `vertical` (`PodstawowaOsnowaGeodezyjnaWysokosciowa`), `gravity` (`OsnowaGrawimetryczna`), `magnetic` (`OsnowaMagnetyczna`: points and `izogony`, without `izogony_etykiety`); address `.../PZGIK/<service>/WFS`; features without `gml:id`: id `nr_punktu` (isogons `zakres_wartosci_deklinacji`); GPKG layer = source name in lowercase |
| as above | `DIRECT_FILES`, `admin_unit_files` | county; `network` variants `horizontal`/`vertical`: `bdpog/Pozioma/{teryt}_PodstawowaOsnowaPozioma.zip` (`Wysokosciowa`), member `.xls` (coordinate lists; JPG descriptions), tokens `<network>`, `xls` |
| as above | `DIRECT_FILES`, `sheet_files` | 1:100 000 sheet (`SheetGrid(system="1992", parts=3)`); `network` variants `archive-1942`, `archive-kronsztadt60`: `bdpog/MaterialyArchiwalne/Katalogi_<Kartoteki1942\|Kronsztadt60>/{sheet}.zip` (sheet code without the leading zero), member `.pdf` (catalogue scans; the CRS in the sidecar = the sheet grid CRS) |
| `pl.gugik.geoid2021` (`geodesy --product geoid --country pl`, plan E5) | `DIRECT_FILES`, `country_files` | country; `InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt` (42 MB, grid 0.01 deg.), `file_kind="txt"`, token `evrf2007`, EPSG:9702 (ETRF2000-PL), no `vertical_crs` (the model is not heights) |

Each of these channels apart from the 3D mesh tiles (`index`: index
record label) has the signal `none` (GUGiK provides neither `ETag` nor `Last-Modified`;
the WFS result is a snapshot). CZ channels (plan D, ADR-042 D13-D17; the CZ area
is always in EPSG:5514 = the DefaultCRS of the services):

| Descriptor (selection) | Channel, capability | Parameters |
|---|---|---|
| `cz.cuzk.zabaged` (`landcover --product zabaged`) | `ARCGIS_QUERY` `ZABAGED_POLOHOPIS/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, page 2000, `selection="all"`: 22 layers (`registry.py::_ZABAGED_LAYERS`, code = ASCII layer name), `order_field="OBJECTID"`, id `fid_zbg`; `none` |
| as above | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml` (one dataset), `crs` EPSG:5514 and EPSG:3045, ZIP 1:1, token `gpkg` + EPSG code; `metadata` |
| `cz.cuzk.ruian` (`admin`) | `ARCGIS_QUERY` `RUIAN/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, page 1000, `selection="level"`: `kraj`=17, `okres`=15, `obec`=12, `katastralni-uzemi`=7, `order_field="objectid"`, id `kod`; `none` |
| as above | `DIRECT_FILES` + `UnitPackageParams`, `country_files` | country; `services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` (approx. 253 MB), member `.shp`, token `shp`; `http` |
| `cz.cuzk.hynet` (`network`) | `WFS` `geoserver/hy-n/wfs`, `bbox_vector` | `wfs`, EPSG:5514, `xy`, page 1000, `selection="all"`: `hy-n:WatercourseLink`, `hy-n:HydroNode` (GPKG layers without prefix), id `gml_id`; `none` |
| as above | `DIRECT_FILES` + `UnitPackageParams`, `country_files` | country; `openzu.cuzk.gov.cz/opendata/HY-NET/HY-NET.zip` (approx. 194 MB, EPSG:3045), member `.gpkg`, token `gpkg`; `http` |
| `cz.cuzk.data50`, `cz.cuzk.data250` (`landcover --product data50\|data250`, plan E4) | `ARCGIS_QUERY` `DATA50/MapServer`, `DATA250/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, page 2000, `selection="all"`: 69 and 116 feature layers (`registry.py::_DATA50_LAYERS`, `_DATA250_LAYERS`, code = ASCII layer name as for ZABAGED; relief rasters 5 and 6 of DATA250 omitted), `order_field="OBJECTID"`, id `OBJECTID`; `none` |
| as above | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/Data50/Data50.xml` (`Data250/Data250.xml`; one dataset), `crs` EPSG:5514 and EPSG:3045, SHP ZIP 1:1 (Data50 516/757 MB, Data250 230/320 MB), token `shp` + EPSG code; `metadata` |
| `cz.cuzk.control` (`geodesy --product control --country cz`, plan E5) | `ARCGIS_QUERY` `BodovaPole/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, page 1000, `selection="level"`, `selection_key="network"`: `gnss`=0, `horizontal`=18, 20, 2, 4, 6, 8, `densification`=38, 40, 22, 24, 26, 28, `horizontal-detailed`=42, `vertical`=44, `vertical-detailed`=46, `gravity`=48 (network = sum of layers: points determined in ETRS89 are not a subset of the main layers; abolished 10-17, 30-37 and labels omitted), GPKG layer = ASCII CUZK name (`bod_zvbp`), id `OBJECTID`; `none` |
| `cz.cuzk.qgzu2013` (`geodesy --product geoid --country cz`, plan E5) | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/QGZU/QGZU.xml` (one dataset; dataset feed and file on hosts `atom.cuzk.cz`, `openzu.cuzk.cz`), EPSG:4258, ZIP of 17 TXT grids 1:1 (58 MB), token `bpv` (vertical CRS of the model); `metadata` |
| `cz.cuzk.orto` (`imagery --product orto --country cz`) | `DIRECT_FILES` + `AtomFilesParams`, `sheet_files` | feed `atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml`, entry by SM5 sheet code (groups `year`, `sheet`), members `.jpg`, `.jgw`, `.TM33N.jgw`, `.TM34N.jgw` 1:1; `metadata`; track `download/cz_orto.py` (not a collection) |

CUZK country-wide files with `ETag` have the signal `http`, files from the ATOM feed
(year or release date in the name) - `metadata` (release from `updated`).
The HY-NET type `WatercourseSeparatedCrossing` is not an area layer: it has
no geometry in GML (a relation of two segments), and for a query
with BBOX GeoServer returns `hits` 0 despite features on the pages (ADR-042 erratum 2);
the crossings are contained in the country-wide file.

Plan E1 channels (ADR-043; `download_data` products, not collections):

| Descriptor (selection) | Channel, capability | Parameters |
|---|---|---|
| `pl.gugik.nmt_100m` (`elevation --product nmt --resolution 100m`) | `DIRECT_FILES` + `AtomFilesParams`, `admin_unit_files` | feed `mapy.geoportal.gov.pl/.../ATOM/httpauth/atom/GUGIK_NMT100`, dataset entry by `NMT100_<woj>` (group `woj`), `force_https` (`http://` links of GUGiK feeds downloaded via `https`), ZIP with an XYZ file 1:1; `metadata`; registry variant without vertical CRS (`vertical_crs=None`, `vertical_note`, P1); `collection` track (`collections.atom_area_request`) |
| `pl.gugik.intensity` (`imagery --product intensity`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files` | `OI/WMS/SkorowidzeObrazowIntensywnosci`, layer `SkorowidzeOI`, PL-1992 sheets (7-part sheet codes) and PL-2000, without `calyArkuszWypelnionyTrescia` (`full_sheet=False`); `index` |
| `pl.gugik.true_orto` (`imagery --product true-orto`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files`; `WCS` + `WcsCutoutParams`, `bbox_raster` | index `ORTO/WMS/TrueOrtho` (`Skorowidze`, 8-part PL-1992 sheet codes, `extent` = selected cities); WCS `True_Orthoimagery` (grid 0.05 m, pixels `0.05m`-`1m`, one service = no `--coverage`); `index` / `none` |
| `pl.gugik.oblique_orto` (`imagery --product oblique-orto`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files` | `ORTO/WMS/SkorowidzeOrtofotomapyUkosnej`, a layer per direction (`directions`: `n`, `e`, `s`, `w`), PL-2000 sheets 1:2000 and 1:1000, `full_sheet=True`; file `<sheet_code>_<direction>.tif`; `index` |
| `cz.cuzk.zabaged_contours_shp`, `cz.cuzk.zabaged_contours_dgn` (`elevation --product contours --country cz --format SHP\|DGN`) | `DIRECT_FILES`, `sheet_files` | `openzu.cuzk.gov.cz/opendata/ZABAGED-vyskopis{,-DGN}/epsg-5514/{sheet}.zip` (one format = one descriptor, like the GUGiK archives), SM5 sheets, S-JTSK, Bpv, ZIP 1:1; `http`; track `download/cz_contours.py` |

`SheetIndexParams(layers, systems, sheet_parts, full_sheet, directions=(),
extent=None)` describes the WMS image index: record layers (fixed - without
`GetCapabilities`; the orthophoto has `layers=()` and layers from
`GetCapabilities`), sheet systems (with one, `--sheet-system` can be
omitted), the number of sheet code parts (`series_scale`: 7 = `1:10000`, 8 =
`1:5000`), whether records declare a full sheet (`--full-sheet`), view directions
(code, layer) and the extent for `NoCoverageError` hints.

**`SourceDescriptor.resolve_subdir(*, system=None, vertical_crs=None) -> str`**
fills the template through `str.replace`, not `str.format` — partial
filling is legal. `vertical_crs` is normalised to lowercase
(`"Bpv"` -> `"bpv"`). Passing a dimension that the template does not have is a no-op
(orthophoto ignores `vertical_crs`).
An empty string (or only whitespace) in `system`/`vertical_crs` is a
`ValidationError` — `None` means "fill in later", while an empty string gave a
silent segment `nmt/pl_1992_1m_` (review max note 7).

Who fills which placeholder:

| Placeholder | Filled by | When |
|---|---|---|
| `{vcrs}` | the `FileStorage(vertical_crs=)` constructor or an explicit `resolve_subdir(vertical_crs=)` | once, at the start of the task — the vertical CRS belongs to the task, not to the sheet |
| `{system}` | `FileStorage` per identifier (`get_path`/`get_raw_path`/`exists`/`delete`/`ensure_directory`), the same rule as `parser_registry.path_parts`: dots -> `2000`, the rest -> `1992` | when building each path |
| `{system}` (explicit) | LAZ track: `LazTile.system` (the tile's `uklad_xy` via `parse_pl_system`; unknown = tile skipped / `ValidationError`) via `FileStorage.get_raw_path(..., system=)` — a single source of truth for the CLI and the library (note 8, review max); PL WCS cutout (`download_pl_cutout`: `system="1992"` fixed — `--cutout` with `--sheet-system 2000` is rejected, section 4.3) and image cutout (`download_image_cutout`: `system="1992"`, EPSG:2180 only) | before creating the `FileStorage` / cutout path |

`FileStorage` validates the final result: a segment in which a `{`
brace remains after filling ends with a `ValidationError` naming the missing dimension
(`_ensure_resolved`). The silent directory `pl_{system}_1m_evrf2007` will never be created.

### 3.2 Sidecar schema `kartograf-meta/1`

Every successful download through the CLI or the library management layer
(`download_data`, `DownloadManager`, `download_landcover`, `download_soil`,
`download_pl_cutout`, `download_laz_area`, `download_cz_cutout`,
`download_cz_sheet`, `download_cz_laz`, `download_cz_orto_sheet`,
`download_image_cutout`, `download_collection`, `calculate_hsg`) writes the data
and `<file>.meta.json`: the version sidecar in the store is mandatory,
the standard path sidecar is best-effort (section 1). Outside the store
`hsg_from_rasters` writes a best-effort sidecar. A direct call to a
provider does not write a sidecar (section 1).

| Pole | Znaczenie |
|---|---|
| `dataset` | source descriptor key (e.g. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | country, product and provider name from the descriptor; `product` = the value of the file's `--product` (`nmt`, `true-orto`, `admin`, `bdot10k`, `zabaged`, ...), in a group without `--product` the name of the command and directory: `soil download` - `soil`, raster `soil hsg` - `hsg` (`build_metadata(product=)`, derived product) |
| `horizontal_crs` | actual horizontal CRS of the file: PL-1992 sheet `EPSG:2180`, PL-2000 sheet `EPSG:2176`–`EPSG:2179` according to the sheet code zone, CZ natively `EPSG:5514`, TM33 tile `EPSG:3045`; `--cutout` cutout in the `--horizontal-crs` CRS (PL orthophoto only `EPSG:2180`); CZ orthophoto: JPEG and `.jgw` `EPSG:5514`, `.TM33N.jgw` `EPSG:3045`, `.TM34N.jgw` `EPSG:3046` (each file its own CRS); collections: area result in the service CRS (PL `EPSG:2180`, CZ `EPSG:5514`), national file in the file CRS (HY-NET `EPSG:3045`, ZABAGED the selected `--horizontal-crs`). For a PL sheet the CRS from the sheet code is CHECKED against the file coordinates (`sources/sidecar.py::pl_sheet_horizontal_crs`): a file published by GUGiK in a CRS other than the one indicated by the sheet code (E17, e.g. PL-2000 zone 7 sheets such as `7.125.11.19` in EPSG:2180) gets the CRS of the FILE, the declaration of the sheet index record stays in `extra.source.declared_crs`, the `kartograf.sources.sidecar` logger warns, and the CLI prints `Warning: N arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: ...` (code unchanged; the directory segment still follows the sheet code, ADR-026) |
| `vertical_crs` | code of the vertical CRS realisation: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` when the product has no vertical component (orthophoto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (from `AccessChannel`) |
| `resolution` | resolution from the descriptor: registry K2 label (`0.15m`, `0.5m`, `1m`, `10m`, archives up to `50m`; CZ `0.5m`/`2m`/`5m`) or `null` (PL and CZ orthophoto - the pixel of an orthophoto cutout carries `request.resolution`; PL and CZ LAZ, TIN/TTN archives, collections) |
| `nodata` | empty pixel value: for `.asc` read automatically from the header (`read_asc_nodata`), in the CZ path from the GeoTIFF tag (`download/cz_cutout.py::read_tif_nodata`; in bbox mode with the `CUZK_NODATA` fallback), for the PL cutout the constant `-9999.0`, for the HSG result `0`, for CORINE/SoilGrids GeoTIFFs from `LandCoverManager` from the file tag (section 4.8); `null` when none of these paths applies (e.g. orthophoto) |
| `request` | the task that produced THIS file: `sheet` (sheet code), `bbox` + `bbox_crs` in the result CRS or `teryt`; for PL campaigns `campaigns` (resolved `newest`/`all`, always), `min_year`/`max_year` (when given) and `year` (when the bounds are equal); LAZ: `year`/`min_year`/`max_year`/`min_density` when given, `campaigns` only for `all`; land cover: content parameters with default values — SoilGrids `property`/`depth`/`stat`, CORINE `year`, BDOT10k `format` (4.8); orthophoto cutout: `bbox`/`bbox_crs` of the result grid, `coverage` and `resolution`; CZ orthophoto: `sheet`; collections: `teryt`, `bbox`/`bbox_crs` in the service CRS or `whole_country: true` and the given variants (`level`, `lod`, `year`, `horizontal_crs`). `request` describes the original DOWNLOAD of the file, not the latest use; `extra.parent_request(s)` does not carry year flags (3.4) |
| `license` | `{id, attribution, url}` from the descriptor |
| `downloaded_at`, `kartograf_version` | UTC timestamp (ISO 8601, since 0.8.0 with microseconds — ordering of two downloads within one second) and the package version from `src/kartograf/_version.py::build_version()`: release = `__version__` alone; development version (`dev`) = `<__version__>+<short SHA>` of the commit from which the package was imported, with the `.dirty` suffix when tracked files of the `kartograf/` directory have uncommitted changes (docs/tests do not count); when git is unavailable or the package does not come from the repository it lies in (`os.path.samefile`), `__version__` alone. The same value in `kartograf --version`; the HTTP `User-Agent` carries `__version__` alone |
| `transform` | dictionary of axes (`horizontal`/`vertical`) with a description of the operation used in the format `pinned: <description> (<accuracy> m)`; an axis without conversion has no key, and without any conversion the whole field is `null` |
| `extra` | `parent_request` (area; the task that created the file — `parent_requests` removed in 0.8.0); PL LAZ `tile_sheet`/`year`/`nominal_density`/`url`, additionally `acquisition_date`/`full_sheet` when known; PL NMT/NMPT/orthophoto sheets `source`, `campaign`, `version` (`label`, `label_source`; ADR-036), `coverage` (partial flight, when the version is stored) and the year/flight fields described below; CZ LAZ, sheets and cutouts, PL cutout: `version` (ADR-036, plan 2/3); CZ sheet `all_nodata`; SM5 (CZ rasters and LAZ) `mapname`/`cz_share`; openzu file (SM5, native TM33 tile, CZ LAZ — plan B) `http` (`etag`, `last_modified`, `content_length` of the `openzu` response; freshness signal); CZ bbox cutout `all_nodata` and `parent_request`; PL WCS cutout `source`, `mask`, `zero_pixels` (only when > 0), `all_nodata`, `parent_request` (section 3.2); orthophoto cutout `source`, `all_nodata` (only `true`), `http`, `parent_request`; CZ orthophoto `source`, `world_files` (JPEG sidecar), `mapname`/`cz_share`, `http`, `parent_request`; collections `source`, `http`, `parent_request` (below); CORINE WMS `fallback`/`note`; HSG `derived` and calculation parameters |
| `sha256`, `size_bytes` | since 0.7.1: SHA-256 digest (hex) and size in bytes of the data file, computed in `build_metadata` (`sources/sidecar.py::file_digest`) from the FINISHED file — one place for all products, including derived ones (cutout, merged BDOT10k GPKG, HSG); `null` when the sidecar is created without an existing data file. A version in the store (ADR-036) takes the digest from the single read at write time (`build_metadata(digest=)`, D20) — this is the identity of the version (`_<sha8>` in the directory name). The standard path sidecar (a copy of the version sidecar) carries the version digest |
| `schema` | constant `kartograf-meta/1` |

Key names are in English (ADR-031, since 0.7.0); the exception is `teryt` —
a proper name from the registry. Values (sheet codes, layer names, dates, messages)
stay in their source form. Sidecars written before ADR-031 (Polish
keys, e.g. `request.godlo`, `extra.source.aktualnosc`) are not
migrated: the code reading sidecars treats a missing new key as missing
information (section "Stare sidecary" below).

`extra.source` — origin of the PL sheet from the GUGiK sheet index record
(`SkorowidzRecord.to_source`; the same dictionary goes into `record_cache`
and `campaigns_cache`). NMT/NMPT records come since 0.8.0 from the WFS sheet index:
`parse_index_feature` (`providers/pl/skorowidz_wfs.py`) maps the WFS fields
(`url_do_pobrania`, `godlo`, `akt_data`, `akt_rok`, `dt_pzgik`,
`uklad_xy`, `uklad_h`, `char_przestrz`, `czy_ark_wypelniony`,
`nr_zglosz`, `zrodlo_danych`, `format`, `blad_sr_wys`, `blad_sr_syt`,
`modul_archiwizacji`) to the same raw record keys as the former
GetFeatureInfo, so the column below gives the names of the WMS record fields:

| Key | Content (GUGiK record field) |
|---|---|
| `url` | OpenData file URL (`url`) |
| `index_url` | address of the sheet index service the record comes from: NMT/NMPT (since 0.8.0) — the WFS service of the variant (`IndexRef.endpoint`, e.g. `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NumerycznyModelTerenuEVRF2007/WFS/Skorowidze`); orthophoto (and NMT/NMPT sidecars from before 0.8.0) — WMS endpoint |
| `layer` | NMT/NMPT: WFS feature type without the namespace prefix (e.g. `SkorowidzNMT2025`); orthophoto: WMS layer of the sheet index |
| `sheet` | sheet code after normalisation (`godlo`) |
| `acquisition_date` | data currency date `YYYY-MM-DD` (`aktualnosc`) |
| `acquisition_year` | currency year (`aktualnoscRok`, otherwise from `aktualnosc`) |
| `pzgik_date` | date of admission to PZGiK (`dt_pzgik`) or `null` |
| `resolution_m` | resolution in metres (`charakterystykaPrzestrzenna`/`wielkoscPiksela`; WFS: `char_przestrz`) |
| `declared_crs` | CRS declared in the record, e.g. `PL-2000:S7` (`ukladWspolrzednychPoziomych`) — may differ from the file's `horizontal_crs` (E17) |
| `full_sheet` | `true`/`false` = full/partial sheet (`calyArkuszWypelnionyTrescia`), `null` when missing |
| `survey_work_id` | survey work report number (`numerZgloszeniaPracy`) |
| `data_source` | data source (`zrDanych`/`zrodloDanych`) |
| `format` | file format from the record (`format`), e.g. `ARC/INFO ASCII GRID`, `ASCII TBD` |
| `height_rmse_m` | since 0.7.1: mean height error in metres (`bladSredniWysokosci`); `null` when missing or the value is non-numeric |
| `position_rmse_m` | since 0.7.1: mean position error in metres (`bladSredniPolozenia`); `null` as above |
| `archive_module` | since 0.7.1: archiving module, e.g. `1:5000` (`modulArchiwizacji`), or `null` |
| `declared_vertical_crs` | since 0.7.1: vertical CRS declared in the record, e.g. `PL-EVRF2007-NH` (`ukladWspolrzednychPionowych`), or `null` |
| `color` | orthophoto only: variant `RGB`/`CIR`/`B/W` |

**Old sidecars and cache entries (from before ADR-031).** A `record_cache`/
`campaigns_cache` entry without the new keys is a cache miss (the sheet index is
queried again, the entry overwritten); since 0.7.1 this also applies to entries
without the `archive_module` key (written before the accuracy keys were added).
A campaign sidecar without `extra.campaign.pzgik_date` does not provide a link
key from the sidecar — the lower estimate from the campaign directory name
is used (as when there is no sidecar). The E17 warning is not raised for a
sidecar without `request.sheet`. Refreshing a sheet: `--force`.

The channel from which `horizontal_crs`/`vertical_crs_options`/
`vertical_source` is taken is chosen by `build_metadata`: either explicitly by `capability=`,
or by default by the shape of the task (`bbox` in `request` -> channel with
`bbox_raster`/`bbox_vector`, otherwise the first matching one). The name of the vertical
CRS family is mapped to the national realisation if the channel declares
it (`resolve_vertical_crs`: `EPSG:5621` -> `EPSG:9651` for PL).

**PL WCS cutout (`--cutout`) in the sidecar.** The library
(`download/cutout.py::write_pl_wcs_cutout_sidecar`) builds a record with
`capability="bbox_raster"` of the NMT 1 m or NMPT descriptor, `nodata=-9999`,
`horizontal_crs` in the target CRS and `request` =
`{"bbox": <bbox_target>, "bbox_crs": <target CRS>}` (bbox after conversion
to the result CRS). For EPSG:2180 `transform=null`; for EPSG:5514/3045
`transform.horizontal` describes the pinned operation of the local warp.
`extra.source` contains `service="WCS"`, `endpoint`, `coverage`,
`format`, `composition="server"`: the server composition is NOT
the choice of the newest sheet according to ADR-028. `extra.mask` contains
`source="PRG"`, a list `layers` with three entries
`A00_Granice_panstwa`, `-W02_Morze_terytorialne_RP`,
`-W03_Morskie_wody_wewnetrzne` and `masked_pixels`;
`PlCutoutResult.masked_pixels` is counted
on the EPSG:2180 download grid, before any warp. `extra.zero_pixels`
is written only when the number of zero pixels on land is > 0 (zeros remain
data); `extra.all_nodata` and `PlCutoutResult.all_nodata` are true when
the whole result is nodata. `extra.parent_request` is created only when
`parent_request=` is passed (in the CLI: the original task, section 3.4).

**PL orthophoto cutout in the sidecar (ADR-042 D14).**
`download/orto_cutout.py` writes the `pl.gugik.orto` sidecar with
`capability="bbox_raster"` (CRS fields from the first WCS channel; Standard
and High have the same), `horizontal_crs` EPSG:2180, `transform=null`,
`resolution=null` and `request` = `{"bbox": <result grid>, "bbox_crs":
"EPSG:2180", "coverage": ..., "resolution": ...}` (bbox aligned
outwards to a multiple of the pixel, section 4.3). `extra.source` =
`service="WCS"`, the actual `endpoint` and `coverage` (the coverage id of the variant),
`format`, `scalefactor` (only when the pixel is other than 0.1 m, e.g. `0.4` for
0.25 m) and `composition="server"`. A result without any image pixel
does not become a version (section 4.3), so `extra.all_nodata` does not occur. There is no PRG mask
and no `zero_pixels`.

**CZ orthophoto in the sidecar (ADR-042 D13).** `download/cz_orto.py` writes the
`cz.cuzk.orto` sidecar (`capability="sheet_files"`, `request` =
`{"sheet": <sheet_code>}`) for each of the four sheet files:
`horizontal_crs` = file CRS (JPEG and `.jgw` EPSG:5514, `.TM33N.jgw`
EPSG:3045, `.TM34N.jgw` EPSG:3046), `extra.source` = `{url,
dataset_feed, edition, year, updated, member}` (`member` = ZIP member name,
e.g. `WRTO24.2024.CTES96.jpg`), `extra.http` of the ZIP response,
`extra.mapname`/`extra.cz_share` from the SM5 index (best effort)
and `extra.parent_request` (area). The JPEG sidecar additionally has
`extra.world_files` = `{".jgw": "EPSG:5514", ".TM33N.jgw": "EPSG:3045",
".TM34N.jgw": "EPSG:3046"}` - the JGW file itself carries no CRS. The version
label = edition `<year>_<updated>` (`label_source="edition"`).

**Collections (ADR-042) in the sidecar.** `download/collections.py::run_job`
selects the channel by its capability (unique in the descriptor) and writes:
`request` = the user's choice in this unit (`teryt`, `ku` (CZ cadastral map,
with `format`), `tile` (mesh tile: `<crs>/<module>`, e.g.
`2000/7/78944_6777_74230_55482`), `sheet`, `bbox` +
`bbox_crs` in the native CRS of the service or `whole_country: true`; `year`,
`format`, `lod`, `level`, `horizontal_crs` only when given - the only
LoD2 release without `year`), `horizontal_crs` =
file CRS (area result: `native_crs` of the channel; national file: CRS of the
channel or the selected ATOM feed file), `vertical_crs` =
`PackageVariant.vertical_crs` (3D models; 2D = `null`), `extra.source`:
package `{url, edition?, member?}` (`member` = unpacked member, EGiB),
file from the ATOM feed `{url, dataset_feed, edition, updated}` (ZABAGED
national), area result `{service, protocol, layers: [{code, source, name,
features}], dropped_fields?}` (`dropped_fields` = field -> sorted
unique values of the `drop_fields` fields removed from the GPKG, EGiB `{"DATA": [...]}`);
the file also has `extra.http` (response headers; GUGiK without a signal, CUZK files
with `ETag`/`Last-Modified` = `http` signal), and an area
split into counties or converted from a sheet/geometry/another CRS -
`extra.parent_request` (section 3.4). Version label: `edition` of the variant
(`label_source="edition"`: BDOT10k vintage, 3D model year), the release
from the ATOM feed (`updated` date, e.g. `2026-10-04`), otherwise the
download date.

**Versioned store (ADR-036).** The VERSION sidecar (`versions/.../<label>_<sha8>/<file>.meta.json`)
is MANDATORY and immutable in all paths (PL and CZ sheets,
PL and CZ cutouts, LAZ, land cover, HSG): `emit_sidecar(..., exclusive=True)`
writes it once (tmp + `fsync` + `os.link`, never overwrites); a write
failure raises `DownloadError` (the write removes the created data file, there is no
version). A sidecar outside the store remains best-effort.
The standard path sidecar (of the link) is a REGULAR file — a copy of the version
sidecar with `extra.link` (`hardlink`) and `extra.link_target` added
(written as `tmp` + `os.replace`, never "through" a sidecar symlink left
by the user; best-effort). This is the ONLY source of the link target
(a hardlink carries no pointer): a missing standard sidecar or
`extra.link = "copy"` from 0.7.x = unknown path. A failed write removes the
old link sidecar (it would describe the previous version), so the next
run recreates the link and the sidecar (ADR-030 erratum 10).

**Year range and coverage (ADR-032, ADR-036 D13).** For a task with a year
bound, the sidecar of each NMT/NMPT/orthophoto version and its copy in the standard path
contain `extra.available_years` (sorted, all years of the
sheet from the full sheet index); without bounds the field is absent. `extra.coverage` (0..1,
four decimal places) is held by the version sidecar of EVERY raster flight
(`.asc`/`.tif`; ADR-041 archives without measurement) without
`full_sheet=true` — computed from the same read as sha256 at write time
(ASC without `NODATA_value` = -9999, orthophoto by nodata/alpha; a measurement error = missing
field + warning), never added later. With a range and `all`
the standard sidecar gets `extra.flights` (descending per ADR-028; `id`,
`date`, `full_sheet`); when it has > 1 flight and the linked flight does not have
`full_sheet=true`, it also adds `coverage` from the version sidecars and compares
the coverage. For an older flight with GREATER coverage `extra.better_coverage` =
its `id` (a flight declared as full counts as fully covered) and
the CLI prints `Info:` to stderr (also with `-q`). The `better_coverage` field is removed
when a repeated task does not show a better flight. Coverage does NOT move
the link (newest flight first per ADR-028, the "never backwards" rule).
The LAZ sidecar additionally carries `extra.acquisition_date` (`akt_data`)
and `extra.full_sheet` (`czy_ark_wypelniony`), when known.

### 3.3 Canonical `data/` layout

```
data/
├── nmt/
│   ├── pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # HARD LINK (rule 6)
│   ├── pl_1992_1m_evrf2007/full_sheet/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # HARD LINK to the latest full flight (rule 7)
│   ├── pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e/N-34-130-D-d-2-4.asc   # version (real file)
│   ├── pl_1992_1m_evrf2007/versions/.incoming/<host>_<pid>_<token>/   # write in progress (cleaned up after 24 h)
│   ├── pl_1992_1m_kron86/...
│   ├── pl_1992_5m_evrf2007/...              # 5m, 0.15m, 0.6m, 10m EVRF2007 only (variant registry, 3.1)
│   ├── pl_1992_0.5m_evrf2007/...            # K2 label in the segment (0.15m, 0.5m, 0.6m, 1m, 5m, 10m)
│   ├── pl_1992_tbd_25m_kron86/<hier>/<sheet_code>.zip   # GUGiK archive: source file 1:1 (ADR-041), sheets of various scales
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif         # HARD LINK: PL WCS cutout (4.3)
│   ├── pl_1992_1m_evrf2007/versions/bbox/2026-10-12_<sha8>/<coords>.tif   # cutout version
│   ├── pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
│   ├── cz_dmr5g_bpv/302/5550/302_5550.tif   # HARD LINK (version in versions/302/5550/)
│   ├── cz_dmr5g_bpv/bbox/<coords>.tif       # HARD LINK: CZ bbox cutouts (versions in versions/bbox/)
│   ├── cz_dmr5g_evrf2007/...
│   ├── cz_dmr4g_bpv/CTES/96/CTES96.tif      # HARD LINK; version sidecar with extra.http (ETag)
│   ├── cz_dmr4g_evrf2007/760/5518/760_5518.tif   # native TM33 tile from the openzu file (plan B), extra.http
│   └── pl_1992_100m/teryt/12.zip            # NMT 100 m: voivodeship XYZ ZIP 1:1 (ATOM feed; vertical CRS unknown)
├── nmpt/
│   ├── pl_1992_1m_evrf2007/...              # (+ _kron86, + pl_2000_..., + 0.5m, 0.6m, xyz_0.5m/xyz_1m KRON86)
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif # HARD LINK: NMPT WCS cutout
│   ├── cz_dmpok_bpv/CTES/96/CTES96.tif      # DMP OK 0.5m, SM5 sheet from the openzu file (plan B)
│   ├── cz_dmpok_evrf2007/760/5518/760_5518.tif   # DMP OK, native TM33 tile from the openzu file
│   └── cz_dmp1g_bpv/bbox/<coords>.tif       # DMP 1G 2m: ImageServer cutout (TM33 tile: warp)
├── orto/
│   ├── pl_1992/...                          # sheets; no vertical CRS
│   ├── pl_1992_cir/...                      # CIR variant (B/W: pl_<crs>_bw), E12
│   ├── pl_1992_standard_0.25m/bbox/<coords>.tif   # HARD LINK: orthophoto WCS cutout (4.3, ADR-042 D14)
│   ├── pl_1992_high_0.1m/versions/bbox/2026-10-16_<sha8>/<coords>.tif   # High cutout version
│   ├── cz_sjtsk/CTES/96/CTES96.jpg          # HARD LINK: CZ orthophoto, JPEG from CUZK ZIP 1:1 (4.4, ADR-042 D13)
│   ├── cz_sjtsk/CTES/96/CTES96.jgw          # + CTES96.TM33N.jgw and CTES96.TM34N.jgw (georeferencing files)
│   └── cz_sjtsk/versions/AS/91/2025_2026-02-24_<sha8>/AS91.jpg   # version (label <year>_<updated>); sheet code As
├── true-orto/
│   ├── pl_1992/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif   # true orthophoto: 8-part sheet (plan E1)
│   └── pl_1992_0.05m/bbox/<coords>.tif      # HARD LINK: WCS True_Orthoimagery cutout
├── oblique-orto/pl_2000/7/125/11/08/7.125.11.08_n.tif   # oblique orthophoto: one file per direction (_n, _e, _s, _w)
├── laz/pl_2000_evrf2007/<hier>/<file>.laz   # HARD LINK; horizontal CRS per tile (uklad_xy), vertical from flag
├── laz/pl_2000_evrf2007/versions/<hier>/<date>_<report>_<sha8>/<file>.laz   # version (D26)
├── laz/cz_dmr5g_bpv/CTES/96/CTES96.laz      # HARD LINK: CZ LAZ (plan B) 1:1 from openzu ZIP; SM5 = EPSG:5514/Bpv
├── laz/cz_dmr5g_bpv/versions/CTES/96/<date>_<sha8>/CTES96.laz   # version
├── laz/cz_dmpok_evrf2007/760/5518/760_5518.laz   # TM33 tile = EPSG:3045/EVRF2007
├── intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif   # intensity image (1 band; + pl_2000/...)
├── contours/cz_zabaged_shp/CTES/96/CTES96.zip   # ZABAGED contours: SM5 sheet ZIP 1:1 (+ cz_zabaged_dgn)
├── landcover/
│   ├── pl_bdot10k_gpkg/teryt/1465.gpkg          # HARD LINK; versions in versions/teryt/<date>_<sha8>/
│   ├── pl_bdot10k_gpkg_ptwp-swrs/teryt/1465.gpkg # layer filter (codes sorted, lowercase)
│   ├── pl_bdot10k_gpkg_zip/teryt/1465.zip      # keep_raw: original package ZIP
│   ├── pl_bdot10k_shp/teryt/1465.zip           # SHP package
│   ├── pl_bdot10k_shp_2024/teryt/1261.zip      # annual archive (rule 9); versions 2024_<sha8>
│   ├── pl_bdot10k_shp_2023/versions/teryt/2023_<sha8>/1261.zip   # year identical to 2022: hard link (D7)
│   ├── eu_corine_2018/N-34/130/D/N-34-130-D.tif  # CLMS; versions <release>_<sha8> (e.g. V2020_20u1_...)
│   ├── eu_corine_2018_preview/bbox/<coords>.png  # WMS preview without credentials (D31)
│   ├── cz_zabaged/bbox/<coords>.gpkg           # ZABAGED of the area (REST, 22 layers), EPSG:5514
│   ├── cz_zabaged_gpkg_5514/country/cz.zip     # national file from the ATOM feed; versions 2026-10-04_<sha8> (release)
│   ├── pl_bdoo_2023/teryt/12.zip               # BDOO: voivodeship GML package 1:1; versions 2023_<sha8> (year)
│   ├── pl_bdoo_2023_kuik-ptwp/teryt/12.zip     # --layers: ZIP of files of selected classes (codes sorted)
│   ├── cz_data50/bbox/<coords>.gpkg            # Data50 of the area (REST, 69 layers), EPSG:5514; cz_data250: 116
│   └── cz_data50_shp_5514/country/cz.zip       # national SHP file from the ATOM feed; versions 2026-04-28_<sha8>
├── boundaries/
│   ├── pl_prg_gmina/bbox/<coords>.gpkg         # features of the area (WFS), EPSG:2180; versions <date>_<sha8>
│   ├── pl_prg_gml/teryt/12.zip                 # voivodeship package 1:1
│   ├── pl_prg_shp/country/pl.zip               # national file (--whole-country)
│   ├── pl_prg_addresses/bbox/<coords>.gpkg     # address points and streets of the area (WFS KIN), EPSG:2180
│   ├── pl_prg_addresses_shp/teryt/1261.zip     # county package 1:1; national file: _shp or _gml, country/pl.zip
│   ├── pl_prg_special/bbox/<coords>.gpkg       # special boundaries of the area (OGC API, one layer per kind), OGC:CRS84
│   ├── pl_prg_special_shp/country/pl.zip       # national file (+ pl_prg_special_gml)
│   ├── cz_ruian_obec/bbox/<coords>.gpkg        # RUIAN of the area (REST), EPSG:5514, e.g. -470000_-1130000_...
│   ├── cz_ruian_shp/country/cz.zip             # national SHP file (http signal)
│   └── cz_geomorphology_celek/bbox/<coords>.gpkg   # geomorphological units of the --level level (REST), EPSG:5514
├── cadastre/
│   ├── pl_egib/bbox/<coords>.gpkg              # parcels and buildings of the area (WFS), no token
│   ├── pl_egib_gpkg/teryt/1261.gpkg            # county export (GPKG unpacked from ZIP)
│   ├── pl_rcn/teryt/1261.gpkg                  # RCN: county export (teryt/12.gpkg - voivodeships), GPKG from ZIP
│   └── cz_cadastral-map_shp/ku/623164.zip      # CZ cadastral map: KU package 1:1 (+ _dxf, _dgn, _vfk; http signal)
├── models3d/
│   ├── pl_buildings_lod1_2024/teryt/1261.zip   # CityGML 1:1; versions 2024_<sha8> (release year)
│   ├── pl_trees_lod1_2023/teryt/3063.zip       # trees CityGML 1:1 (package 0.3-25 GB); versions 2023_<sha8>
│   └── pl_mesh/2000/7/78944_6777_74230_55482.zip   # mesh tile = index record file (OBJ+MTL+JPG 1:1),
│                                               # directory = record layout: 1992 or 2000/<zone>;
│                                               # versions <Freshness>_<report>_<sha8>
├── hydro/
│   ├── cz_hynet/bbox/<coords>.gpkg             # HY-NET of the area (WFS: WatercourseLink, HydroNode), EPSG:5514
│   └── cz_hynet_gpkg/country/cz.zip            # national file (GPKG in ZIP, EPSG:3045, http signal)
├── geodesy/
│   ├── pl_control_horizontal/bbox/<coords>.gpkg      # network points of the area (network WFS), EPSG:2180
│   ├── pl_control_horizontal_xls/teryt/1201.zip      # county package (XLS lists, JPG descriptions) 1:1
│   ├── pl_control_archive-1942/N-33/58/N-33-58.zip   # 1:100,000 sheet archive 1:1
│   ├── pl_geoid2021_evrf2007/country/pl.txt          # PL-geoid2021 quasi-geoid model 1:1 (TXT)
│   ├── cz_control_vertical/bbox/<coords>.gpkg        # Bodove pole: network layers, EPSG:5514
│   └── cz_qgzu2013_bpv/country/cz.zip                # QGZU-2013 from the ATOM feed; versions 2021-02-22_<sha8>
├── names/
│   ├── pl_prng/bbox/<coords>.gpkg              # PRNG of the area (OGC API), OGC:CRS84 (+ pl_prng_world/)
│   ├── pl_prng_shp/country/pl_miejscowosci.zip # national file 1:1 (+ pl_obiekty-fizjograficzne.zip; _gml, _xlsx)
│   ├── cz_geonames/bbox/<coords>.gpkg          # Geonames of the area (REST, 25 layers), EPSG:5514
│   └── cz_geonames_gpkg_5514/country/cz.zip    # national file from the ATOM feed (+ _fgdb, _3045); label = release
├── maps/
│   ├── pl_bdot10k_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif   # BDOT10k visualisation; label = database state date
│   └── cz_ztm_10000_sjtsk_tiff/0510/D/11/0510-D-11.zip   # ZTM: sheet code hierarchy (PDF: .pdf; http signal)
├── soil/global_soilgrids_clay_0-5cm_mean/bbox/<coords>.tif   # versions 2.0_<sha8> (release)
└── hsg/global_soilgrids_0-5cm_mean/bbox/<coords>.tif         # derived from clay/sand/silt versions (D33)
```

**Segment rules:**

1. A segment has the form `<country>_<crs>[_<variant>][_<vcrs>]`, all values
   lowercase. PL CRS: `1992` / `2000`. Vertical CRS: `kron86` /
   `evrf2007` / `bpv`. CZ does not carry a horizontal CRS: in its place stands the
   model (`dmr5g`, `dmr4g`, `dmpok`, `dmp1g`), and the CRS of the file follows from the sheet code
   — SM5 sheet EPSG:5514, TM33 tile EPSG:3045 (openzu file or warp
   from ImageServer; plan B); the `bbox/` cutout has the `--horizontal-crs` CRS
   (sidecar). In CZ LAZ the vertical CRS determines the files (Bpv = SM5 sheets,
   EVRF2007 = TM33 tiles), so `cz_<model>_<vcrs>` identifies them unambiguously.
   The CZ orthophoto (plan D) has the segment `orto/cz_sjtsk` (CRS of the JPEG and `.jgw`;
   `.TM33N.jgw` and `.TM34N.jgw` lie alongside in the same directory), the PL
   orthophoto cutout - `orto/pl_1992_<coverage>_<res>` (rule 5). The images of
   plan E1 have their own product directories (rule 10) with the segment
   `pl_<crs>`: `intensity/pl_1992`, `true-orto/pl_1992` (cutout
   `true-orto/pl_1992_<res>`), `oblique-orto/pl_2000`.
   The PL NMT/NMPT part between the CRS and `<vcrs>` comes from the descriptor
   template (`registry.py::_pl_sheet_source`, section 3.1; it is not the
   `<variant>` from rule 5): an ASC grid — the label alone
   (`pl_1992_0.5m_evrf2007`), an archive — the format token before the label
   (`pl_1992_tbd_25m_kron86`, `pl_1992_ascii-nmt_1m_evrf2007`), a format
   without resolution — the token alone (`pl_1992_tin_kron86`).
2. The hierarchy inside a segment is unchanged — `parser_registry.path_parts`:
   PL-1992 `N-34-130-D-d-2-4` -> `N-34/130/D/d/2/4`, PL-2000 `6.179.12.20` ->
   `6/179/12/20`, TM33 `302_5550` -> `302/5550`, SM5 `CTES96` -> `CTES/96`,
   and two-letter SM5 sheet codes (99 As sheets, `AS22`...`AS94`) `AS91` ->
   `AS/91` (`path_parts` = `[godlo[:-2], godlo[-2:]]`; since 0.8.0 - previously
   the SM5 pattern had 4 letters and `AS91` fell through to the PL-1992 fallback).
   CUZK map sheets (ZTM, `MAPNOM` of the `KladyMapovychListu` layer) have the same
   hierarchy (`parser_registry.cuzk_map_path_parts`, ADR-044 D7):
   S-JTSK `0510-D-11` -> `0510/D/11`, ETRS89 `NM-34-07-1-D-15` ->
   `NM-34/07/1/D/15` (1:1,000,000 sheet in a single directory like `N-34`).
3. The `bbox/` subdirectory inside a segment holds the links to PL WCS cutouts
   (`--cutout`; NMT/NMPT and orthophoto) and CZ ones: `<coords>.tif` without a date
   (D15); versions in `<segment>/versions/bbox/<YYYY-MM-DD>_<sha8>/<coords>.tif`.
   The coordinates are in the RESULT CRS (`--horizontal-crs`), formatted
   `%.10g` and joined with `_`. The name carries the TASK, not the exact extent
   of the raster: a PL cutout in EPSG:2180 extends up to < 1 px further after outward
   alignment to the 1 m grid, and the warp grid (`warp_to_grid` from
   `transform/raster.py`, shared by PL and CZ) has an integer number of
   pixels from NW, so E/S may deviate by up to 0.5 px (section 4.3).
   Exception: the orthophoto cutout carries the RESULT grid in its name (bbox
   aligned outward to a multiple of the pixel). PL without
   `--cutout` stores sheets in the sheet code hierarchy (section 4.2).
4. Resolution enters the segment only where it is an API parameter
   (NMT/NMPT): the K2 label from the registry (`0.15m`, `0.5m`, `0.6m`, `1m`, `5m`,
   `10m`; archives also `15m`..`50m`), the same as `--resolution`
   and the sidecar `resolution`. It is absent for CZ (the model determines it 1:1:
   `dmr5g` 2 m, `dmr4g` 5 m, `dmpok` 0.5 m, `dmp1g` 2 m) and for orthophoto
   sheets and LAZ (no such parameter); the orthophoto cutout has the pixel
   in the segment token (rule 5).
5. `<variant>` distinguishes files of the same sheet code and CRS that are not the
   same product (E12, 2026-10-06). Only orthophoto declares a variant
   (`storage_variant`; default `None` in `BaseProvider`): RGB
   without a suffix in `orto/pl_<crs>/` (no migration), CIR in
   `orto/pl_<crs>_cir/`, B/W in `orto/pl_<crs>_bw/`. The variant comes
   from `provider.storage_variant` (`GugikOrtoProvider(color=...)`) and is passed to
   `FileStorage(variant=...)`; without it, skip silently returned an RGB file for a
   CIR task. An orthophoto cutout (plan D, ADR-042 D14) has the tokens
   `<coverage>_<res>` appended to the PL-1992 segment (`token_segment`):
   `orto/pl_1992_standard_0.25m/`, `orto/pl_1992_high_0.1m/` - the WCS variant
   and the pixel are different contents; there is no colour in the segment (the cutout is only
   RGB). A true orthophoto cutout (a single WCS service) has only the pixel:
   `true-orto/pl_1992_0.05m/`.

6. **Versions (ADR-036; formerly `kampanie/`, ADR-030).** The actual
   NMT/NMPT/orthophoto PL files live ONLY in `<segment>/versions/<hierarchia
   godla>/<label>_<sha8>/<sheet_code>.<ext>` (+ the version's `.meta.json`);
   the standard path `<segment>/<hierarchy>/<sheet_code>.<ext>` is a
   hard link to the newest LOCAL version of the task. The campaign label =
   `<date>_<id>`: `<date>` = the `aktualnosc` of the record (YYYY-MM-DD), `<id>` =
   the first numeric segment of the file name in the URL (`83233_1744736_<sheet_code>.asc`
   -> `83233`), otherwise `u` + 8 hex characters of `sha1(URL)`; providers without
   campaigns: UTC download date. `<sha8>` = the beginning of the content sha256.
   Write (`download/versions.py::commit_version`): working directory
   `versions/.incoming/<host>_<pid>_<token>/` on the same file
   system, `fsync`, exclusive `os.link` (never overwrites; an existing
   file with a different sha256 = `DownloadError`), version sidecar written exclusively;
   the same content = `unchanged`, the same content with a new campaign label =
   `relabeled` (a new directory with a hard link). A version without a sidecar is
   invalid (the next write of the same content repairs it after checking
   sha256); leftovers older than 24 h are removed. Link: hard
   link only (no support = `DownloadError`, never a copy or symlink),
   atomic replacement (temporary file + `os.replace`), never backwards (ADR-028
   key from the version sidecar). Check: target from `extra.link_target` +
   `os.path.samefile`; when the file system has no stable inodes (SMB without
   `serverino`), confirmation by content: the same size and sha256 of the link =
   sha256 of the version sidecar (`links._same_content`). The link count does not
   take part in the confirmation: the cifs client reports `st_nlink` = 1 for a
   path that has just been opened (also by this read), for several seconds
   or longer, so the count would change the result between successive calls
   (e2e 0.8.0: the link rolled back to an older flight). A path with the content of a version
   IS that version (`links._hold`), also when it is an independent copy, and "never backwards"
   depends on its key; `ensure_link` turns such a copy
   back into a hard link of THE same version when none of the paths reports
   a second name (`_Held.lone`, e.g. after `rsync -a` without `-H`), and otherwise
   writes nothing. `FileStorage.get_versions_root(sheet)`/
   `get_versions_base`,
   `list_files()` skips `versions/`, `full_sheet/` and `kampanie/`
   (`versions=True` = version files only). The `kampanie/` directory from 0.7.x
   is not read (`has_legacy_campaigns()` -> `Info:` in the CLI). Since plan
   2/3 the same mechanism applies to LAZ tiles (label `<akt_data>_<report>`,
   D26; `FileStorage.get_raw_versions_root/base(sheet, system=)`), CZ sheets
   and, since plan B, CZ LAZ files (label = UTC download date), CZ orthophoto
   (plan D: each of the four sheet files has its own versions
   in `versions/<SM5 hierarchy>/`, label = release `<year>_<updated>`)
   and `bbox/` cutouts (hierarchy `bbox`,
   `storage.bbox_slot`); common policy for files without campaigns:
   `download/fetch.py::fetch_version`. An old plain 0.7.x file in the standard
   path (sidecar without `extra.link`) is replaced by a link
   (D24). Land cover and HSG (plan 3/3) — rule 8.
   Copying `data/`: `rsync -aH`/`cp -a` (without preserving hard links
   a duplicate is created).

7. **Second `full_sheet/` link (ADR-033).** Next to the standard path
   `<segment>/full_sheet/<hierarchy>/<sheet_code>.<ext>`
   (+ `.meta.json`) points to the newest LOCAL flight of the task marked
   in the sheet index as full (`full_sheet is True`; NO and a missing flag = not
   full). The same mechanism as rule 6 (`download/links.py::ensure_link`:
   hard link only, never backwards among full flights, sidecar with
   `extra.link_target`); when the newest flight is full, both links are
   the same file. No full flight = no file in `full_sheet/`
   (an existing link stays). `FileStorage.get_full_sheet_path`
   builds the path, `list_files()` skips `full_sheet/` (like
   `versions/`), `delete(sheet)` removes both links with the sidecars.
   A collision with the hierarchy is impossible: the first hierarchy component is a 1:1M sheet
   or a zone (`N-34`, `7`). LAZ, CZ, cutouts and land cover have no
   `full_sheet/`.

8. **Land cover and HSG (ADR-036 D29-D33, spec 3.4).** Segment = prefix of the descriptor's
   `storage_subdir` (`landcover/pl_bdot10k`,
   `landcover/eu_corine`, `soil/global_soilgrids`; HSG: constant
   `HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"`) + `_` + content tokens
   by rule 10 (`download/storage.py::content_segment`):
   BDOT10k `gpkg[_<layers>]`/`gpkg_zip`/`shp` (archive of annual editions -
   rule 9), CORINE `<year>[_preview]`, SoilGrids
   `<property>_<depth>_<stat>`, HSG `<depth>_<stat>`.
   Under the segment (`download/storage.py::unit_slot`): `teryt/<T><ext>`
   (BDOT10k, also when selected by bbox/sheet), `bbox/<coords><ext>`
   (EPSG:2180, `.10g`, like cutouts) or the sheet code hierarchy (`path_parts`,
   canonical sheet code). Versions as in rule 6 (`versions/<ta sama
   hierarchia>/`).

9. **Collections (ADR-042 D8; extension of rule 8).**
   `<group>/<country>_<source>[_<tokens>]/{teryt/<T>|bbox/<coords>|country/<code>|ku/<code>|<sheet code hierarchy>|<crs>[/<zone>]/<file>}<ext>`:
   segment = prefix of `storage_subdir` + content variant tokens
   (`content_segment`), under it `unit_slot`: `teryt/<T>` (package of a county
   or voivodeship (Polish województwo) - also when the area was split into counties from PRG; BDOO:
   the voivodeships of those counties), `bbox/<coords>` (area result; coordinates
   in the service's NATIVE CRS, `.10g`, `_`) or `country/<code>` (nationwide
   file, `pl`/`cz`); versions in `<segment>/versions/<ta sama
   hierarchia>/`. Tokens = content variant: level (`pl_prg_gmina`), LoD
   and year (`pl_buildings_lod1_2024`), format and archive annual edition
   (`pl_bdot10k_shp_2024`), annual edition and selected BDOO classes
   (`pl_bdoo_2023_kuik-ptwp`, codes sorted). An area result (always GPKG
   in the native CRS) has no format token; a package and a nationwide file have the
   source format token when the product has several formats or the area result as well
   (`pl_prg_gml`, `pl_prg_shp`, `pl_egib_gpkg` next to `pl_egib`),
   and when the source publishes a file in several CRSs - also the EPSG code (plan D).
   CZ segments (plan D): `landcover/cz_zabaged` (area result),
   `landcover/cz_zabaged_gpkg_5514` and `_3045` (nationwide file in two
   CRSs), `boundaries/cz_ruian_<level>` (e.g. `cz_ruian_obec`),
   `boundaries/cz_ruian_shp`, `hydro/cz_hynet`, `hydro/cz_hynet_gpkg`;
   plan E4: `landcover/cz_data50` and `landcover/cz_data50_shp_<5514|3045>`
   (likewise `cz_data250`); the CZ nationwide file is `country/cz`, and
   CZ `bbox/<coords>` has EPSG:5514 coordinates (negative, e.g.
   `-460000_-1120000_-450000_-1110000.gpkg`). Plan E: an index tile has the slot
   `<crs>[/<zone>]/<file>` (mesh: record CRS `1992` or `2000`
   and PL-2000 zone `5`-`8`, record file name, e.g.
   `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip`), sheet -
   sheet code hierarchies (`geodesy/pl_control_archive-1942/N-33/58/`, ZTM sheet
   `maps/cz_ztm_10000_sjtsk_tiff/0510/D/11/0510-D-11.zip`, BDOT10k
   visualisation sheet), and the E5 segments are `models3d/pl_trees_lod1_2023`,
   `geodesy/pl_control_<network>` (area), `geodesy/pl_control_<network>_xls`
   (county package: XLS lists and JPG descriptions), `geodesy/pl_geoid2021_evrf2007`,
   `geodesy/cz_control_<network>` and `geodesy/cz_qgzu2013_bpv` (QGZU-2013 is the
   Bpv height quasi-geoid, like PL-geoid2021 for EVRF2007).
   A CZ cadastral map KU has the slot `ku/<code>`
   (`cadastre/cz_cadastral-map_<format>/ku/623164.zip`), the topic of a nationwide
   file - `country/<country>_<topic>`
   (`names/pl_prng_shp/country/pl_miejscowosci.zip`). E2 and E3 segments:
   `names/pl_prng[_<format>]`, `names/pl_prng_world[_<format>]`,
   `names/cz_geonames[_<format>_<epsg>]`, `maps/pl_bdot10k_<scale>_<format>`,
   `maps/cz_ztm_<scale>_<crs>_<format>`, `boundaries/pl_prg_addresses[_<format>]`,
   `boundaries/pl_prg_special[_<format>]`, `boundaries/cz_geomorphology_<level>`,
   `cadastre/pl_rcn` and `cadastre/cz_cadastral-map_<format>`.
   Different contents never share a slot. Identical content of another release of the same
   unit, format and LoD (`FileSlot.related_roots`, D7) does not take
   space a second time: the new version is a hard link to the existing data
   (`relabeled`, `same_as` = label of the version found).

10. **Key and directory naming convention (ADR-044 D7).** One convention for
    source keys and names in `data/`. Segments from releases <= 0.7.2 comply with it
    (`nmt/pl_1992_1m_evrf2007`, `orto/pl_1992_cir`, `laz/pl_2000_kron86`,
    `nmt/cz_dmr5g_bpv`) and so does rule 8; products new in 0.8.0 were named by it
    before the release (no migration). It is enforced by the registry test
    `tests/unit/test_sources_registry.py::TestNamingConvention`.
    - **Source key** = `<country>.<provider>.<name>`: descriptor country (`pl`,
      `cz`, `eu`, `global`), provider (`gugik`, `cuzk`, `clms`, `isric`),
      `<name>` - words `[a-z0-9]` joined by `_` (no `-` or dot in the key:
      `0.5m` -> `0_5m`), composed of whole words of the `data/` path:
      the dataset name from the segment (`hynet`, `geoid2021`, `cadastral-map` ->
      `cadastral_map`) or the product directory when the segment starts with
      a CRS (`orto`, `true-orto` -> `true_orto`), with the descriptor's fixed
      tokens (`nmt_tbd_25m`, `zabaged_contours_shp`) and with the directory
      when the dataset has descriptors in several directories (`dmr5g_laz`,
      `bdot10k_maps`). The key is the `dataset` field of the sidecar; `pl.gugik.nmpt`
      (NMPT 1 m without `_1m`) stays from 0.7.
    - **Top-level directory** = the `--product` value in `elevation`
      and `imagery` (`nmt/`, `true-orto/`, `oblique-orto/`), the CLI group name
      in the other groups (`landcover/`, `geodesy/`); `soil hsg` -> `hsg/`.
    - **Segment** = `<country>_<token>[_<token>...]`, lower case; `_` only
      between tokens; a token is letters and digits, `-` between words of a single
      token (`ascii-nmt`, `cadastral-map`, `horizontal-detailed`,
      `archive-1942`, `0-5cm`, codes `ptwp-swrs`), `.` only in a number
      (`0.5m`). After the country comes the PL CRS (rule 1) or the dataset name: the
      provider's abbreviation without spaces and hyphens (`dmr5g` from DMR 5G, `hynet` from HY-NET,
      `qgzu2013` from QGZU-2013), and without an established abbreviation English words
      (`buildings`, `control`, `cadastral-map`). Variant tokens are the values of the
      options that select it, in lower case (`--level gmina`,
      `--network horizontal-detailed`, `--format SHP` -> `shp`, `--year 2024`,
      `--lod 1` -> `lod1`, `--scale 1:10000` -> `10000`, `--sheet-system
      sjtsk`, `--horizontal-crs EPSG:3045` -> `3045`, `--resolution 0.5m`,
      `--layers PTWP,SWRS` -> `ptwp-swrs`); content without a choice is named by the token of the
      file format (`gpkg`, `xls`; rule 9) and the vertical CRS of the data
      (`evrf2007`, `bpv`) - the latter always last (rule 1). The order of
      a product's tokens is set by its descriptor (`segment_tokens`).
    - **PL CRS** everywhere `1992`/`2000` (segment token or directory),
      PL-2000 zone - its number as a directory under `2000`, like the first
      component of a PL-2000 sheet code (`nmt/pl_2000_1m_evrf2007/6/179/...`,
      `models3d/pl_mesh/2000/7/<file>`, `models3d/pl_mesh/1992/<file>`);
      never `pl1992`, `s7` or `PL-2000:S7`.
    - **Sheet hierarchy** = all components of the sheet code as directories
      (rule 2), file = full sheet code; also ZTM sheets, never flat.
    - **File name** = unit code (TERYT, `pl`/`cz`, KU code, sheet code,
      `<coords>`, tile record file), suffix after `_`: topic of a nationwide file
      (`country/pl_miejscowosci.zip`, `pl_obiekty-fizjograficzne.zip`),
      direction of an oblique orthophoto (`7.125.11.08_n.tif`). ZIP members stored 1:1
      keep the source names (`CTES96.TM33N.jgw`).
    - **Key stability (contract with store consumers, KA-8
      of Archiwista).** A source key published in a release does not change:
      version sidecars are immutable (ADR-036), so every `dataset` ever written
      stays on disk. A key name is changed only through the reader's
      alias table (`_DEV_DATASETS` in `src/kartograf/store.py`):
      the raw `dataset` in the sidecar and in `Sidecar.dataset` stays unchanged,
      `Sidecar.dataset_key` gives the descriptor's current key, and a key
      unknown to the registry gives `dataset_key=None`, not an error (3.3.1).
      The provider is in the sidecar's `provider` field (`provider_name`
      of the descriptor: `GUGiK`, `CUZK`, `Copernicus CLMS`, `ISRIC`), the country in the
      `country` field; the middle part of the key is not a provider identifier,
      and the consumer compares the key as a whole and does not derive from it
      the product, variant, provider or country (it takes them from the sidecar
      and `describe_segment`). The first part of a supranational dataset key
      is the extent (`eu.clms.corine`, `global.isric.soilgrids`).

A new raster source requires a provider and a dispatch path (section 5), but
its `storage_subdir` (per rule 10, e.g. `nmt/de_bb_dgm1_dhhn2016/`) does not
require a special rule in the path code; a collection product (rule 9) is
simply a descriptor entry with the channel parameters.

**Top-level directories** (CLI group and product selection):

| Directory | CLI group | Selection |
|---|---|---|
| `nmt/` | `elevation` | `--product nmt` |
| `nmpt/` | `elevation` | `--product nmpt` |
| `laz/` | `elevation` | `--product laz` |
| `contours/` | `elevation` | `--product contours` (CZ) |
| `orto/` | `imagery` | `--product orto` |
| `true-orto/` | `imagery` | `--product true-orto` |
| `oblique-orto/` | `imagery` | `--product oblique-orto` |
| `intensity/` | `imagery` | `--product intensity` |
| `landcover/` | `landcover` | `--product bdot10k`, `bdoo`, `corine`, `zabaged`, `data50`, `data250` |
| `soil/` | `soil` | `soil download --property` |
| `hsg/` | `soil` | `soil hsg` |
| `boundaries/` | `boundaries` | `--product admin`, `addresses`, `special`, `geomorphology` |
| `cadastre/` | `cadastre` | `--product map`, `prices` |
| `models3d/` | `models3d` | `--product buildings`, `trees`, `mesh` |
| `hydro/` | `hydro` | `--product network` |
| `names/` | `names` | `--product geographic`, `world` |
| `maps/` | `maps` | `--product topographic` |
| `geodesy/` | `geodesy` | `--product control`, `geoid` |

**Migration 0.6.x -> 0.7.0 (BREAKING):**

| Old path | New path |
|---|---|
| `nmt_1m/` (1992 sheet codes) | `nmt/pl_1992_1m_<vcrs>/` |
| `nmt_1m/` (2000 dotted sheet codes) | `nmt/pl_2000_1m_<vcrs>/` |
| `nmt_5m/` | `nmt/pl_<crs>_5m_evrf2007/` |
| `nmpt/` | `nmpt/pl_<crs>_1m_<vcrs>/` |
| `orto/` | `orto/pl_<crs>/` |
| `laz/` | `laz/pl_<crs>_<vcrs>/` |
| `cz_dmr5g/` (0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
| `cz_dmr4g/` (0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

`<crs>` comes from the sheet code format of EACH file separately (dots -> `2000`,
hyphens -> `1992`, the `path_parts` rule from section 3.1) — the old `nmt_5m/`,
`nmpt/`, `orto/` and `laz/` held both systems together, so one old directory
splits into two segments during migration (`orto/` -> `orto/pl_1992/`
and `orto/pl_2000/`).

For a manual migration, read `<vcrs>` from the sidecar (the `vertical_crs` field:
`EPSG:9650` -> `kron86`, `EPSG:9651`/`EPSG:5621` -> `evrf2007`, `EPSG:8357`
-> `bpv`). Files from before the sidecar stage 0 have none — in that case the user's
own knowledge or a re-download remains. Kartograf does not migrate an existing
`data/` automatically: files in the old layout simply stop being
seen as downloaded (the next task downloads them again into the new
segment).

### 3.3.1 Public store read access (ADR-045, v0.8.0)

Reading `data/` without write access (also from an SMB share mounted read-only)
for Archiwista and other readers - a single `data/` contract
from 3.2-3.3, with no private parser on the consumer side. In
`kartograf.__all__`: `list_segments`, `list_partitions`, `iter_store`,
`read_sidecar`, `describe_segment`, `link_target` (module `src/kartograf/store.py`),
`file_footprint`, `pinned_transform` (`src/kartograf/store_geometry.py`), the types
below and `InvalidSidecarError` (attribute `path`). The functions do not create
directories, caches or files in the store; the index and cache are kept
locally by the caller. Public records:

| Record | Fields and semantics |
|---|---|
| `StoreEntry` | `kind`: `version`, `link` (standard path), `full_sheet`, `problem`; `segment` (`produkt/wariant`), `hierarchy` (the slot directory relative to the segment, and for a version and `full_sheet` - relative to `versions/` and `full_sheet/`; `""` for a segment problem), `name`, `path` (built from `root` in the given form), `version_path` (the version pointed to by the link's `extra.link_target`, checked lexically: it lies in the slot of this link; for a version its own path; `None` = unknown), `label` and `sha8` (from the directory name `<label>_<sha8>`; for a link without a known version - from the sidecar), `sidecar` (`Sidecar` or `None`), `problem` (`missing_sidecar`, `invalid_sidecar`, `unknown_segment`, `legacy_campaigns`, `stale_incoming`) and `skipped` (`True` = a version from `skip_versions`, sidecar not read). |
| `Sidecar` | Typed fields from 3.2 (`schema`, raw `dataset`, `dataset_key` from the registry or `None`, `country`, `product`, `provider`, `horizontal_crs`, `vertical_crs`, `vertical_source`, `resolution`, `nodata`, `request`, `license`, `downloaded_at`, `kartograf_version`, `transform`, `extra`, `sha256`, `size_bytes`) and the computed fields `data_year`, `data_date`, `campaign`, `survey_work_id`, `edition`, `full_sheet`, `coverage`, `unit`, `raw`. A missing value or a value of an unexpected type is `None`, and the original JSON (`raw`) remains unchanged. |
| `SegmentInfo` | `segment`, `product`, `country`, `dataset_key`, `name`, `known`. The name is human-readable: descriptor name + variant (CRS, vertical CRS, format, vintage, LoD, level); no match in the registry = `known=False`, never a presumed descriptor. |
| `Footprint` | `native: BBox`, `wgs84: BBox` (EPSG:4326, longitude/latitude), `source`: `request`, `sheet`, `header`, `unit`. No verified footprint = `None` (including country-wide packages). |

`list_segments(root)` returns the sorted `<product>/<variant>`
of all real second-level directories (excluding symbolic links
and names starting with `.`), including those unknown to the registry.
A missing `root` is an `OSError`, not an empty store (a detached share).

`iter_store(root, *, segment=None, units=None, skip_versions=None,
partition=None)` is a generator; without `segment` it walks the segments
from `list_segments` in turn; `partition` (requires `segment`, excludes
`units`) is one part from `list_partitions` (below).
Within a segment the order is: links, `full_sheet`, versions, leftovers;
an entry is yielded before the listing of the following directories is made. `units`
(requires `segment`) are unit names, not prefixes: a PL-1992/2000 sheet code,
TM33, SM5, a ZTM sheet or a LAZ tile (slot = the sheet code hierarchy directory with
ALL the sheet's files: LAZ file names from the URL, oblique orthophoto directions,
georeference files), `teryt/<code>`, `bbox/<coords>`, `country/<code>`,
`ku/<code>` or `<dir>/<file name without extension>` (a mesh tile
`2000/7/<file>`); a bare TERYT code, `<coords>` and country also work (6 digits =
KU in a segment whose package channel has the unit `ku`). A country-wide file
with a topic is `<country>_<topic>` (`pl_miejscowosci`) - exactly the name
returned by `Sidecar.unit` (derived from the slot file name, because the topic
is not in `request`), so the `unit` from the index closes the refresh loop
`iter_store(units=[unit])`. Likewise a LAZ tile: one selected for an area or
sheet has that area in `request.bbox` (0.7.x and 0.8.0 sidecars), but its
`unit` is the tile sheet code from `extra.tile_sheet` (also `godlo_kafla` from before
ADR-031); in a segment of sheets and tiles only (ZTM) the bare number (`0510`) is a
sheet, not a TERYT. Reserved names (`versions`, `full_sheet`,
`kampanie`, also as a unit on its own) and names longer than 255 bytes are a
`ValidationError`. Hierarchies are computed by
the same functions as writing (`SheetParser`, `path_parts`,
`cuzk_map_path_parts`); the scan does not list other segment directories and does not
report segment-level problems; it skips hidden version directories
(`.<label>_<sha8>`) just like the full scan. `skip_versions` are version
directories known to the caller, relative to `root`, with `/` (e.g.
`nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e`):
their files come back with `skipped=True` and `sidecar=None` without reading sidecars
(versions are immutable). Set of directories: files from the version directory listing,
a missing sidecar in the listing still gives `missing_sidecar`. Mapping `directory ->
data file names`: a directory present in the parent's listing is not listed,
and the entries (the same as from a listing, in name order, filtered by `units`)
are built from the given names - the caller vouches for the directory contents; a file
removed from it or added later (Kartograf adds a file to an
existing `<label>_<sha8>` with the same label and the same
`sha8` of another slot file) is not visible to a scan with a mapping.
The caller therefore maps only directories all of whose files were valid versions at the
last read, and periodically scans without a mapping.
Mapping keys are not validated (a key outside the scan matches nothing);
the scan validates names when it reaches the directory (a name containing a
path, hidden, or a sidecar is a `ValidationError` from the iterator).
Invalid arguments are a `ValidationError` immediately on the call (no
path goes outside the store; a segment that is a
symbolic link is rejected, and such directories in the tree are not
traversed). An I/O error midway (e.g. a detached share) is an `OSError` -
the caller keeps the old index; a file or directory that disappeared
during the scan is not an error. Inconsistent or unreadable metadata give
an entry problem, without displacing the other versions of the slot. A version is valid
by the same rule as `download.versions.read_version` (`sha256`
starts with the directory's `<sha8>`, `extra.version` has `label`
and `label_source`).

`list_partitions(root, segment, *, target=32)` splits one segment
into disjoint parts for parallel calls of `iter_store(..., segment=...,
partition=...)`; the union of the parts is exactly `iter_store(..., segment=...)` -
the same entries, none twice (property test on random stores).
Keys: `"."` (always first) - the segment level: `unknown_segment`,
`legacy_campaigns`, `stale_incoming` and files directly in the segment
directory and in `full_sheet/` (hierarchy `""`); `"<dir>[/<dir>...]"`
- the slot of this hierarchy directory and all slots below it, simultaneously
in the standard path, `full_sheet/` and `versions/`; `"<dir>/."` -
only the directory's own slot (its files and versions), when its subdirectories are
separate parts. Splitting: first-level directories (the union of the three
trees) are split by levels into subdirectories, as long as there are fewer parts than
`target` and there is something to split; a directory without subdirectories remains a whole part.
Archiwista test store (50 thousand slots): `nmt/pl_1992_1m_evrf2007` -
75 parts (`M-33/<7>`, `M-34/<66>`, `bbox`), `laz/pl_1992_evrf2007` - 77,
`orto/cz_sjtsk` - 715 (first-level directories), flat segments
(`teryt`, `bbox`) - 2. The key is validated by `iter_store` (components without a leading `.`,
without a separator and drive), and the part's path - by `lstat` of each
component (a symbolic link is not traversed). A nonexistent
segment gives `[]`. A directory added after the split goes into the next
split (like a directory added past the point of a full scan).

Cost per entry (the scan never calls `link_target`):

| Element | Disk/share operations |
|---|---|
| segments (`list_segments`) | 1 listing of `root` + 1 listing per product directory |
| directory (hierarchy, `full_sheet/`, `versions/`, version directory) | 1 listing (`scandir`; entry type from the listing - no file `stat` on ext4/XFS/NTFS/SMB) |
| `link`, `full_sheet` | 1 sidecar read (open, read, close); no `stat`, data file not opened |
| `version` | 1 sidecar read; version from `skip_versions`: 0 reads, only the listing of its directory |
| `missing_sidecar` | 0 (no `<file>.meta.json` in the listing) |
| `invalid_sidecar` | 1 read |
| `unknown_segment`, `legacy_campaigns` | 0 (from the segment listing) |
| `stale_incoming` | listing of `versions/.incoming` (only when it is in the listing) + `lstat` of the working directory tree |
| `iter_store(segment=...)` | `stat` of `root` + `lstat` of the product and segment directories |
| `list_partitions` | like `iter_store(segment=...)` + listing of the segment, `full_sheet/` and `versions/` + at most 3 listings (one in each tree) per directory checked during the split (on an SMB share approx. 2-5 ms per listing; `nmt/pl_1992_1m_evrf2007`: 11 listings) |
| `partition` | like `iter_store(segment=...)` + `lstat` of the key components in each of the three trees + listings of the part's subtree only; `"."`: listing of the segment, `full_sheet/` and `versions/` |
| `skip_versions` - mapping | known version directory: 0 listings and 0 reads (without mapping: 1 listing) |
| `units` | per unit: `lstat` of the slot path components (symbolic link guard, result shared across the units of the call) for the link, `full_sheet/` and `versions/` + listing of those directories and of version directories; a flat slot (`teryt/`, `bbox/`, `country/`, `ku/`, mesh zone) is shared by many units - its version directory and every version directory in it are listed once per call (a directory from the `skip_versions` mapping - not at all) |

Threads: any calls of `iter_store` may run in parallel in separate
threads - different segments, parts of `list_partitions` of one segment (this is how
Archiwista divides the work: the largest segment does not wait on one thread)
or parts of `units` of one segment (units shared by two parts
yield only repeated entries). The scan only reads and has no shared state
apart from the immutable registry and `functools.lru_cache`; one iterator belongs
to one thread, while a single `skip_versions` mapping can serve many
calls at once (the scan neither copies nor modifies it). The same applies to
`read_sidecar`, `describe_segment`, `file_footprint` and `link_target`;
`file_footprint` shares between threads only the caller's `cache` (one
plain `dict` can serve all threads - in the worst case two threads
query the index for the same unit). `pinned_transform` can also be called
from many threads at once (below). This guarantee is enforced by the parallel-use
test in `tests/unit/test_store_geometry.py`.

Cost of CPU (test store of 50k slots, SSD, single thread, 131,111
entries): incremental scan (`skip_versions` = all versions) 6.3 s,
with mapping 5.2 s, full 10.1 s (before optimisation 12.4 s and 20.3 s).
The scan loop works on strings (`Path` paths only in the resulting
`StoreEntry`), checks link versions with the same rule as
`link_target` without `pathlib`, rejects short names without a regular
expression, and the sidecar typing computes derived fields lazily.

`read_sidecar(path)` accepts a data file or a sidecar and does not open the data
file: it validates the schema (`InvalidSidecarError`: missing file, bad JSON, different
schema; a sidecar without a `schema` field is accepted only in the shape written
by `emit_sidecar` for a provider without `descriptor_key` - an object with
`sha256` and `extra`, as accepted by `download.versions.read_version`); old missing fields stay empty, keys from before ADR-031 and `dataset`
keys from 0.8.0-dev (ADR-044 D7) are recognised through an explicit mapping
in the reader, without changing `raw`. `data_date`/`data_year` come from the campaign,
the sheet index record, the LAZ tile or the release (the `updated` date of the CZ orthophoto ATOM feed
is the publication date, not the data year) - never from `downloaded_at` or
from the `downloaded` label. `describe_segment` reverses the write rules
(`resolve_subdir`, `content_segment`, orthophoto variants and cutouts, HSG);
every segment written by the paths of the current registry is recognised
(test `test_every_segment_the_writers_produce_is_known_with_its_source`),
segments from 0.8.0-dev (`orto/pl_1992_true`, `cadastre/cz_km_*`) are
`known=False`.

`file_footprint(entry, *, network=False, cache=None)` selects the first
RELIABLE source: the task bbox (with `bbox_crs`; only for a file that IS
that area - a LAZ tile with `extra.tile_sheet` has in `request.bbox` the area
from which it was selected, so its footprint is the LAS header), a computable sheet code
PL-1992/PL-2000/TM33 (PL-1992: WGS84 = exact rectangle of the sheet code), the footprint
from the GeoTIFF/ASC header, JPG/JGW (the georeference file of the same version),
GPKG (SQLite `immutable=1`, without `-wal`/`-shm` files), LAS/LAZ, the footprint of a
TERYT unit (PRG), KU (RUIAN) or SM5 sheet (CUZK index); it does not fake
a country footprint. A unit footprint from `cache` (`(kind, code) -> BBox`, memory of the
caller) is also used without network; a query to the index only with
`network=True`. An entry without `sidecar` (e.g. `skipped`) first reads the sidecar.
An SM5 sheet or a unit unknown to the index has no footprint (`None`, not an
error). A source whose envelope cannot be safely converted to WGS84
(`TransformError`: no operation in the policy or the envelope outside the area of the
operation) is skipped and the next one decides (the first RELIABLE source);
with none, the result is `None`. `OGC:CRS84` (PRNG, PRG special boundaries) and
EPSG:4326 are the same longitude/latitude: the envelope is the same numbers without
an operation. Exceptions: `DownloadError` (index unavailable) and `ParseError`
(KU feature without geometry) - only with `network=True`. The PRG query
presents itself like the other GUGiK queries (`make_gugik_session`).

`StoreEntry` and `Sidecar` are unhashable (dict fields; `__hash__ =
None`): the key is `StoreEntry.path` or `(kind, path)`.
A GDAL raster header is read without listing the directory
(`GDAL_DISABLE_READDIR_ON_OPEN=TRUE`). Envelopes are computed with densified
edges (`transform_bbox`) through `pinned_transform`, never through the
default `Transformer.from_crs`; the lack of a safe operation is
`TransformUnavailableError` from `pinned_transform` (for a pair equal up to
the axis order of the geographic CRS the operation is exact).

`link_target(path)` checks that `extra.link_target` points to the version
of the slot of this link (the same rule as `version_path` of the scan), and then
confirms it with the existing `download.links.linked_version`: the same file by
inode or - on a share without stable inodes (SMB without `serverino`) -
by content (the same size, SHA-256 of the link = SHA-256 of the version sidecar,
one full read of the file at each call; the link count is not
checked, because the cifs client reports `st_nlink` = 1 after a read and subsequent
calls would alternately return the version and `None`). A file with the content of a version
counts as that version also when it is an independent copy (a download
turns it into a hard link, rule 6 in 3.3). It returns a path in the same
form as `version_path`. Reading all targets during a full scan
could cost many gigabytes, so the scan assigns versions from the
sidecar path, and `link_target` is called on demand.
`pinned_transform(src_crs, dst_crs)` builds a `PinnedTransform` with the envelope
policy (accuracy <= 1 m, no ballpark and no network grids, CZ datum
step for S-JTSK); operations from pyproj `TransformerGroup` are not
thread-safe, so the object is cached per thread, and the build
(which toggles the global PROJ network flag) is performed by one thread at a time.

### 3.3.2 Read access implementation plan v0.8.0 (completed 2026-10-18)

1. Establish the types and the format of problems (ADR-045), use the patterns of descriptors
   and hierarchy parsers, traverse the trees with a generator; separately the scenario
   without a segment and the selection of `units` without scanning the whole branch.
2. Normalise sidecars of old and current releases without writing; combine
   links with the existing SMB verification and reverse the segment variants.
3. Determine the footprint by priority, read headers only for missing
   bboxes/sheet codes, connect the pinned transformation and the optional unit
   indexes.
4. Add offline tests on an artificial store, API `__all__`, documentation,
   CHANGELOG in the 0.8.0 section; run the offline gate pytest/ruff/mypy.
5. Update PROGRESS, make logical commits on the branch
   `feat/archiwista-store-api`; merge into `develop` only after the user's
   consent. No data downloads or CLI changes.

### 3.4 `extra.parent_request`

In `--bbox`/`--geometry` mode the task sidecars get `extra.parent_request`
— since 2026-10-07 also the LAZ tiles (`download_laz_area(parent_request=)`,
review-2 N15), since plan B also the CZ LAZ files (`download_cz_laz(parent_request=)`);
`countries` are the countries of the task, e.g. `["PL"]` for `--country pl`, `["CZ", "PL"]`
under `auto` with an area in both rectangles:

```json
{"bbox": [min_x, min_y, max_x, max_y], "bbox_crs": "EPSG:2180", "countries": ["CZ", "PL"]}
```

It carries the **original** user task — before clipping per country — its
CRS and the countries actually queried in this call (attempted, not downloaded).
In `--geometry` mode the "task" is the envelope of the geometry: for a file in a Czech
CRS (EPSG:5514/3045) in the CRS of the FILE (since 2026-09-28), for the others
in EPSG:2180; an explicit `--country cz` of a raster (cutout) writes the envelope
in the CRS of the CZ task (`--horizontal-crs`). The key is built by `download/area.py::parent_request_for`,
called by `download_data`; a direct call of the library path
writes it only when `parent_request=` is passed.
A version with a sidecar keeps the `parent_request` of the task that
CREATED it; subsequent tasks do not change the version sidecar (ADR-036; the
`extra.parent_requests` list removed in 0.8.0). This is the grouping key:
the consumer (Hydrograf, the future `find_downloaded`) uses it to assemble
the files of one task, including those lying on both sides of the border, which
Kartograf deliberately leaves separated (section 1). The dictionary is shared
by reference between the sidecars of the task and **must not be mutated** after
creation.

### 3.5 Project manifest `kartograf-project/1`

`kartograf project init --root KATALOG` creates in the project directory
`kartograf-project.json` (UTF-8, JSON with 2-space indentation). The manifest
holds `schema: "kartograf-project/1"`, `root` (one versioned
store) and `tasks` in the order of addition. A task has a unique `name`,
`command` (e.g. `elevation download`), data-selection `options`, `pinned_at`,
`kartograf_version` and `files`; for a pinned geometry also
`geometry_sha256`. `pinned_at` and `kartograf_version` are `null`, and `files`
empty before the first download. Each file entry gives `role` (`output`,
`raw`, `input`), `unit`, the standard path `path`, the path of the immutable
version `version`, `label`, the full `sha256` and `size_bytes`. The manifest selects
data versions; the `kartograf-meta/1` sidecar invariably describes the provenance
of the file. The update report `kartograf-plan/1` is not part of the manifest.

A relative `root` and a relative `options.geometry` are written and
resolved relative to the project directory, while absolute ones remain
absolute. `path` and `version` are always relative to the store, with the
separator `/`; `version` points to a file under `versions/`, never
`.incoming/`. Moving the project directory together with the store preserves
the bindings if their relative position stays the same.

`src/kartograf/project/manifest.py` strictly checks the structure and types on
every read (including command names and options, sums and paths; the UTF-8 BOM of an
editor is allowed, writing is always without BOM). It writes
a temporary file next to the manifest, synchronises it (`fsync`) and replaces it
atomically (`os.replace`); it also synchronises the directory when the file system
allows it. A short directory lock `.kartograf-project.lock`
(`mkdir`) covers only read-merge-write, not the download. With
concurrent operations, changes to different tasks are merged, a change to the same
task reports a conflict without overwriting other people's pins. The write
happens after each completed task; there is no SQLite or byte-range locks
on the share. Details of the format and modes:
[`USAGE.md`, section 8](USAGE.md#8-project) and the spec
`docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`.

### 3.6 JSON documents `kartograf-*/1`

A command result is a document: `@dataclass(frozen=True)` with the `Document` mixin
(`src/kartograf/serialization.py`), which provides `to_dict()` and `to_json()`. `schema`
(`kartograf-<kind>/<n>`, class constant `SCHEMA`, property `schema`) is always
the first key, followed by the `JSON_KEYS` keys in a fixed order (by default the dataclass
fields; a key without a field and without a property takes `JSON_FILL`). `to_json()` =
`json.dumps(to_dict(), ensure_ascii=False, indent=2, allow_nan=False)` and `\n` at the
end (`indent=None`: the compact form of the MCP server, without a newline). The CLI `--json` prints
`to_json()` in the envelope `kartograf-result/1` (`cli/_json.py::emit_result`, USAGE 9.1), the MCP server returns `to_dict()` and
`to_json(indent=None)`; no other module converts results to JSON (Z8).

The encoder (`encode`, checked in this order): `Enum` -> value; finite `float`
(`NaN`/`Infinity` is `ValueError`); a type with the hook `__json__(ctx)` (`BBox` ->
`{"bbox": [...], "crs"}`, project entries); `Path` -> `Path.absolute().as_posix()` (without
touching the file system); `Decimal` -> string; `datetime` -> ISO 8601 UTC to seconds;
dataclass -> object with fields in declaration order (`metadata={"json": False}` and `ctx.omit`
pairs skipped); `Mapping` -> object; `tuple`/`list` -> array; `set` -> sorted
array; any other type is `TypeError` (never `str(obj)`). `EncodeContext` carries `store`
(the store directory to which the version paths of project pins are relative) and `omit` (pairs
`(class, field)`: `StoreEntries` omits `Sidecar.raw`). The `SCHEMAS` registry
(`__init_subclass__`) collects classes per schema; a test checks the name pattern
(`^kartograf-[a-z][a-z0-9-]*/[1-9][0-9]*$`), the same set and order of keys of the classes of one
schema, and that every `result_schema` of the catalog is in the registry.

| Schema | Library type | Module | Keys after `schema` |
|---|---|---|---|
| `kartograf-download/1` | `DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`, `HsgReport` | `download.data`, `download.collections`, `landcover.manager`, `hydrology.hsg` | `files, raw, inputs, failed, stale, superseded, summary, notices, ok` |
| `kartograf-plan/1` | `UpdatePlan` | `download.plan` | `store, checked_at, kartograf_version, items, notices, ok` |
| `kartograf-result/1` | `CommandResult` | `envelope` | `tool, version, command, check, status, result, items, notices` |
| `kartograf-availability/1` | `AvailabilityReport` | `download.availability` | `request, checked_at, areas, combinations, failed, notices, ok` |
| `kartograf-sheet/1` | `SheetInfo` | `sheet_info` | `sheet, system, country, sheet_system, scale, components, zone, crs, bounds, commands, hierarchy, children, descendants` |
| `kartograf-sheets/1` | `SheetList` | `sheet_info` | `request, sheets, count` |
| `kartograf-sources/1` | `SourceList` | `source_info` | `group, products, sources` |
| `kartograf-layers/1` | `LayerList` | `source_info` | `group, product, source, layers, classes, years, properties, depths, statistics` |
| `kartograf-project-state/1` | `Project` | `project.model` | `directory, root, tasks` |
| `kartograf-project-report/1` | `ProjectReport` | `project.model` | `project, tasks, notices, ok` |
| `kartograf-project-check/1` | `ProjectCheck` | `project.model` | `project, files, not_downloaded, notices, ok` |
| `kartograf-cache/1` | `CacheInfo` | `cache_info` | `action, path, exists, size_bytes, entries, cleared, removed_unreadable` |
| `kartograf-config/1` | `Config` | `config` | `tool, version, config_file, keys, credentials, store` |
| `kartograf-command-list/1` | `CommandList` | `catalog.model` | `tool, version, groups, commands` |
| `kartograf-commands/1` | `CommandCatalog` | `catalog.model` | `tool, version, commands` |
| `kartograf-guide/1` | `AgentGuide` | `guide` | `format, text` |
| `kartograf-store-overview/1` | `StoreOverview` | `store_documents` | `root, segments` |
| `kartograf-store-entries/1` | `StoreEntries` | `store_documents` | `root, segment, units, limit, truncated, entries` |
| `kartograf-store-sidecar/1` | `StoreSidecar` | `store_documents` | `path, sidecar` |
| `kartograf-error/1` | `ErrorReport` | `error_report` | `code, title, message, hint, details, exit_code, command` |

Document rules (source: `docs/superpowers/specs/2026-10-18-agent-interface-design.md`,
section 5; usage: USAGE 9.1):

- one schema `kartograf-download/1` for five result types of the data commands with a fixed
  set of keys (`raw`, `inputs`, `superseded`, `summary` empty when the class does not have them:
  `JSON_FILL`), so the consumer cannot distinguish the type by the keys;
- `AvailabilityReport` and `UpdatePlan` have no `schema` field (the constant `SCHEMA`
  and the property `schema`): they are not built with `schema=`, and an unknown schema is rejected by
  `UpdatePlan.from_dict`; plans written by 0.8.0-dev still load;
- paths in documents are absolute (exceptions: `request.geometry` of the availability report
  and `tasks[].options` of the project in manifest form); `Project`, `ProjectReport` and
  `ProjectCheck` set `ctx.store`, so the pin paths (`PinnedFile`, `FileCheck`)
  are absolute;
- the key is always present (no value `null`, no elements `[]`), lists are not
  silently truncated (`kartograf-store-entries/1` carries `limit` and `truncated`);
- `ok` is present in result documents (`-download/1`, `-plan/1`, `-availability/1`,
  `-project-report/1`, `-project-check/1`): `envelope.py` reads them (`_READERS`, by type) and
  gives the envelope status `ok`, `partial` or `failed` (CLI exit code 0, 10, 11);
  `ok: false` is a result, not an error (an error is `kartograf-error/1`, the last line of stderr);
- within `/1` only additive changes (new keys, new enum values); removing a
  key or changing a type is `/2`. A new document = a class with `Document` in the result module,
  an entry in the table above and a row in `tests/contract/test_json_contract.py` (exact list of keys in
  order; a key change is a test error).

File schemas - the sidecar `kartograf-meta/1` (3.2) and the manifest `kartograf-project/1` (3.5) -
are not result documents and do not enter `SCHEMAS`; the project document is
`kartograf-project-state/1`.

---

## 4. Flows per product

**Migration 0.7.x -> 0.8.0 (ADR-036, BREAKING):**

| State | Behaviour |
|---|---|
| `<segment>/kampanie/` from 0.7.x | neither read nor migrated; the CLI prints `Info:` once, the required campaigns are downloaded again into `versions/` |
| link or regular file at the standard path | sidecar without `extra.link = "hardlink"` with a target in `versions/` = unknown path; REPLACED by a hard link after the version is downloaded |
| link to a version | subsequent tasks repoint it only to a version whose key `(aktualnosc, dt_pzgik, url)` is greater than the key of the current target; an equal key (new content of the same campaign) only when the version was created in this invocation |
| link whose `extra.link_target` does not exist (version directory removed) | no file — downloaded anew |

**The `download` command in the library (ADR-037, since 0.8.0).** `kartograf elevation download`
and `kartograf imagery download` (CLI groups, ADR-039) and `download_data(...)`/`check_data(...)` (`download/data.py`) are the same
path: the CLI converts flags to arguments (`--bbox` -> `BBox`,
`pl=..,cz=..` -> dictionary) and prints the result. `download_data` validates the whole
task before the network (`download/options.py`: area selection, product,
country, CRS and resolution per country, CZ LAZ model, system, scale, years,
LAZ options, CZ orthophoto and orthophoto cutout; `ValidationError` with text
as in `--help`), resolves the country (sheet code:
from the code; area: `--country`, `auto` with clipping, section 4.6), selects the track
(PL sheets 4.1/4.2, PL cutout - NMT/NMPT and orthophoto - 4.3, CZ 4.4/4.5
with CZ orthophoto in 4.4, PL and CZ LAZ 4.7), builds
`parent_request` (`download/area.py`) and collects the result
`DataReport(files, failed, stale, superseded, notices, ok)`: `files` =
`UnitFile(unit, country, file: VersionedFile)` (`unit` = sheet code, LAZ file
name or cutout grid coordinates `<coords>`, like the area units
of a collection; project line `task: unit (file)`), `failed` =
`UnitFailure(unit, country, error, kind)`, `ok` = exit code rule
(partial success of `auto` = `True`). Data notices are `Notice`
(`src/kartograf/notices.py`; the list of codes is in the docstring of `download/data.py`)
passed through `on_notice` when they arise and returned in `notices`;
the CLI prints them as `Info:`/`Warning:` on stderr (also with `-q`), the header of the
sheet list (`SHEET_LIST`) on stdout. `check_data` (the same arguments
without `update`, `plan`, `workers`, `on_progress`) returns one plan
`kartograf-plan/1` (under `auto` with PL and CZ items). The tracks are public
(`download_pl_cutout`, `download_image_cutout`, `download_cz_cutout`,
`download_cz_sheet`, `download_cz_orto_sheet`, `download_laz_area`,
`download_cz_laz`, `DownloadManager`) with `check_*` counterparts; their internal
steps are not.

**Collections (ADR-042, since 0.8.0).** `kartograf boundaries download`,
`cadastre download`, `models3d download`, `hydro download`, `names
download`, `maps download` and `geodesy download` (ADR-039 groups, ADR-042
D9) are `download_collection(...)`/`check_collection(...)`
(`download/collections.py`) - one orchestrator for unit packages,
area objects and national files (also from an ATOM feed), driven by the
channel parameters of the descriptor (section 4.10); ZABAGED (`landcover
download --product zabaged`) goes through the same engines with the public
`download_landcover` and the internal `LandCoverManager` (section 4.8).

### 4.1 PL sheet code (NMT/NMPT/orthophoto)

`SheetParser` validates the sheet code and normalises it to the canonical form:
letter case and PL-1992 numbers without leading zeros (since 0.7.1, A7:
`M-33-036-A` -> `M-33-36-A`, the same form in the path, sidecar and result);
digits only ASCII `0-9` in all sheet systems (PL-1992, PL-2000, CZ;
since 0.7.2 — full-width digits etc. are a `ParseError`); a PL-1992 sheet code
coarser than 1:10000 expands to 1:10000 sheets
(`download_hierarchy`), a PL-2000 sheet code is downloaded directly (archives
ADR-041: sheets from the sheet index, section 4.2).

**NMT/NMPT sheet index: WFS (since 0.8.0, ADR-041).** The NMT/NMPT provider
handles ONE registry variant (section 3.1: product, format,
resolution, vertical CRS) and reads records from the WFS sheet index of that
variant (`IndexRef`; `providers/pl/skorowidz_wfs.py`,
`WfsSkorowidzLayersMixin`): the annual types of the service from GetCapabilities
(`WfsIndex.feature_types`: pattern `^(?:gugik:)?<prefix><year>$`,
newest first, a family type outside the pattern = `logger.warning`, no
types = `DownloadError`) and ONE `GetFeature` with all types
(`TYPENAMES`), `SRSNAME` and `BBOX` in URN `EPSG::2180` with axes (N,E),
a 20 m square in the middle of the sheet (`sheet_query_bbox`), `COUNT=1000`.
The server ignores `FILTER`, so every filter is client-side;
further pages only through the `next` attribute (from the same service).
A multi-type response that has `next` (does not fit on a page) is
rejected and each type is queried separately — the server paginates several
types inconsistently (repetitions and omissions, measurement 2026-10-15), a single type
consistently. `numberReturned` different from the number of objects, an object repeated on
a subsequent page, `next` from outside the service, a page loop, `ExceptionReport` or
non-XML with HTTP 200 = `DownloadError` with the note `wynik bylby
niepelny` — never an empty result (an empty, valid collection = no records,
e.g. sea); a transport error preserves `status_code` (I-1 below).
`parse_index_feature` maps WFS fields to sheet index record keys
(section 3.2), `layer` = object type (`SkorowidzNMT2025`); an object without an `https`
URL or with a sheet code outside `SheetParser` is not a record. The orthophoto
stays on WMS (`SkorowidzLayersMixin`:
`GetFeatureInfo`, layers discovered lazily through `GetCapabilities` — ADR-020).

`providers/pl/skorowidz.py` filters records (hard filter ADR-028,
`SkorowidzQuery`): whole sheet code, matching CRS and resolution, for
NMT/NMPT also the **format** of the variant (`source_format`: the record `format` field
and the end of the URL path must indicate the same format — the same
sheet may be in the sheet index as an `.asc` grid and an `.xyz.zip` archive; grids of
campaign 72675 (NMT 2019, 42 records) have the name `.xyz` and are ASC grids), for orthophoto the colour
variant from `color`; it selects (strategy `newest`) the record with the newest date
in the first layer group with a match (NMT/NMPT: one group = all
annual types of the service); a tie is resolved by `dt_pzgik`, URL. The vertical CRS
is selected solely by the service (a separate sheet index per CRS); before download
`verify_record_vertical_crs` (`download/campaigns.py`; called in
`DownloadManager._fetch_campaigns` for `newest` and `all` and in
`GugikProvider.download`) compares the record field `ukladWspolrzednychPionowych`
with the requested CRS (`RECORD_VERTICAL_CRS`: KRON86 -> `PL-KRON86-NH`, EVRF2007
-> `PL-EVRF2007-NH`, values from raw GUGiK responses). A different value =
campaign `DownloadError` before download (in `all` the remaining campaigns are
downloaded, the sheet ends in failure); missing field = record accepted (`debug`
log); orthophoto has no vertical CRS — no check. The value from the record is
stored in `extra.source.declared_vertical_crs`, also in the record cache —
a mismatched record from the cache gives the same error, refresh: `--force`. No matching record
after correct layer responses = `NoCoverageError`, e.g. for PL-2000
1:10000 with only descendants the hint is `--scale 1:2000`. NMT/NMPT (P10
since 0.7.2, via WFS since 0.8.0; `GugikProvider._no_coverage`): records
of the sheet from other registry variants arrive in the same WFS response
(all formats and resolutions of the point) and give a hint without the
network, e.g. `Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 - uzyj
--resolution 1m` — first variants of the same format, other formats
(`--format XYZ`) only when there are none; records outside the registry give
one line `... tylko rekordy, ktorych Kartograf nie pobiera: ...`.
The second vertical CRS (`_variant_hints`): one `GetFeature` to the service of
the second CRS (all types, the same square and hard filter, one
attempt without retries, timeout `DEFAULT_TIMEOUT`). The hint text is
without the sheet code (one `Info:` line for many sheets). A query error
for the second CRS = no such hint, `logger.warning`
and skipping that service for the rest of the provider's life, never a change of result;
a hit in the no-coverage cache (with hints) does not query the network. A layer failure,
an OGC report or an unexpected template = `DownloadError`, not a silent fallback
to an older campaign. Queries and downloads have up to 3 attempts with backoff
(retried: network, 429, 5xx; other 4xx end at the first attempt)
and keep-alive sessions per thread. `MetadataCache` (SQLite WAL, TTL 7 days)
stores a record `{"source": ...}` or a confirmed `{"no_coverage": true}`;
the CLI and the library use the same cache (Z6, ADR-037): the parameter
`cache: MetadataCache | bool = True` of public functions (`True` =
`<cache_dir>/kartograf/metadata.db` via `cache/defaults.py::open_cache`, `False` =
no cache); `update="force"` (CLI `--force`) and every check
(`check_*`, `check_data`, CLI `--check-updates` - always queries the source)
open it in `MetadataCache(refresh=True)` mode — read skipped,
fresh record written (E14); `--upgrade` the same as `--check-updates`
(`fetch.refreshes_cache`: `upgrade` and `force`), the default download reads the
cache within the TTL. `kartograf cache stats` shows `Wpisy rekordow`. Rule:
`force`/`upgrade` refresh only the cache opened by the function (parameter
`cache`, provider created by it or by name); a provider passed
as an instance (`DownloadManager`, `LandCoverManager`,
`download_laz_area(provider=)`) keeps its own cache, which `force`
does not bypass — full refresh:
a provider with `MetadataCache(..., refresh=True)` (USAGE "Metadata cache
in the library").
The database is opened lazily: the `metadata.db` file (and its directory
`<cache_dir>/kartograf/`) is created only on the first write (`set_*`); construction, reads (`get_*` = miss),
`stats()` (zeros, `db_exists: false`), `clear()` and `close()` on a missing file
do not create it, so `kartograf cache path|stats|clear` without a database
write nothing (the cache never lies in the current directory: `cache_dir`
comes from the user settings, `kartograf/config.py`, ADR-050). The cache is only an accelerator: every
`sqlite3.Error` (corrupted/truncated file, no permissions, `database is
locked`) disables the instance for the rest of its life (read = miss, write =
no-op, `MetadataCache.error`, `stats()["error"]`) with one warning
(`Notice` `CACHE_DISABLED` via `on_notice`; CLI: one `Warning:` per command);
the download continues. `MetadataCache(strict=True)` (library, since 0.7.1):
the same state ends with `CacheError` on the call that failed, and on
every subsequent one (`on_disabled` still once). Repair: `kartograf cache clear`
removes the unreadable file together with `-wal`/`-shm`.
`DownloadManager` writes a sidecar after every successful sheet; a GUGiK ASC sheet
carries no CRS (rasterio: `crs=None`), so the only carrier of the CRS is the
sidecar. A rerun resolves the newest record of the sheet (cache 7 d;
after it expires, a query to the sheet index) and applies the `update` mode
(below, "Tryby i plan aktualizacji"). `--cutout` in sheet code mode is
**rejected** (`ValidationError`, code 2) — a PL sheet code delivers a native 1:1 sheet.

**Incomplete newest campaign (E13).** A record with `full_sheet: false`
(the sheet index declares the sheet not completely filled) still wins when
it is the newest (ADR-028 without a preference for the full sheet); the fact goes to
`extra.source.full_sheet`, and the CLI reads it from the result sidecars and prints
one `Warning: najnowsza kampania GUGiK jest niepelna dla N arkuszy ...`
on stderr in the sheet code, list and hierarchy tracks — also for sheets skipped
as existing (code unchanged). The warning divides sheets (ADR-033): "full
flight in <segment>/full_sheet/" (`DownloadResult.full_links`), "no full
flight in the sheet index" (`DownloadResult.without_full`; with `all` every sheet
without a full link; with a year boundary with the note "within the task year
range") and "full flight not downloaded — use --full-sheet".
Meaning of the flag: YES = full coverage within the borders of Poland (measurement
`docs/research/2026-10-10-full-sheet-link/granica-pelne-pokrycie.md`:
nodata beyond the border in border sheets is normal), NO does not say
anything about the scale of the gap (0.9-98.9 %). Cutout: section 4.3 (`partial_sheets`),
the mosaic still from standard paths.

**Second link and `--full-sheet` (ADR-033).** After the standard link,
`_fetch_campaigns` links `full_sheet/` to the newest
flight with `full_sheet is True` among the flights of THIS task (rule 7 in 3.3);
without a candidate the full link is left untouched. A failure of this
link = a sheet failure (`dowiazanie <path>: <error>`), `--force`
refreshes it, I-1 does not touch it. `DownloadManager(full_sheet=True)` (CLI
`--full-sheet`): with `newest`, when the selected record is not full, the manager
additionally calls `resolve_campaigns(all_campaigns=True, min_year=..., max_year=...)`
and takes the first full record (list from the newest, `campaigns_cache`)
as one more campaign of the sheet — at most one additional flight;
none = `DownloadResult.without_full`.
A failure of this query or of the full flight download = a sheet failure
(the standard path still points to the newest). The campaign sidecar of the task
with the flag: `request.full_sheet: true`. With `all` the flag has no effect; with
`--cutout` and LAZ `Error:` before the network. With a year range
a full link from outside the task: `full_link_outside_range` and the shared
`Info:` with U15.

**Campaigns and data year (ADR-030, ADR-032).** NMT/NMPT/orthophoto accept
`--year Y` (shorthand for `--min-year Y --max-year Y`), `--min-year L` and
`--max-year U` (inclusive bounds, 1900..2100); the year is `aktualnoscRok`,
otherwise `aktualnosc[:4]`, NOT `dt_pzgik`. The year flags are only a filter
of permitted years; `--all-campaigns` decides the number of flights (model A,
ADR-032 point 3): without the switch (default, allowed with any bound) = one
newest flight from the range, with the switch = all flights from the range, including
several in one year. The same rule applies to LAZ.
A task with any bound first checks ALL sheets
in `DownloadManager.check_year_range`: one full list of campaigns from each
GetCapabilities layer per sheet, year filter after the hard ADR-028 filter.
The `campaigns_cache` list (TTL 7 days, without `scanned_from`) also serves
`newest` with any bound; without bounds `newest` still takes
`record_cache`. `GugikProvider.available_years(sheet)` returns ascending
years from the full list. A sheet without GUGiK data = `NoCoverageError` and
skipping R5, and with data only outside the range = `YearRangeError`
(list of years for up to 20 sheets, the hint changes the bound that blocks: with a
range `--min-year` down or `--max-year` up to the nearest
year that every conflicting sheet has; `--year` gives one-sided flags),
zero downloads for the WHOLE task.
A sheet index failure in the checking phase aborts the task before download,
unless in default mode (D14) EVERY sheet of the task has a local version
with a year within the range (`extra.campaign.date[:4]`) — then sheets
with a sheet index error get that version with a warning (`unverified`).
Then the manager uses the ALREADY checked records, saves each selected
and missing flight as a version in `versions/`, updates the link once
per sheet (newest flight according to ADR-028, never backwards), sidecars and coverage
described in 3.2. `DownloadResult.better_coverage` indicates sheets with a
flight of better coverage (only `all`); `link_outside_range` and
`full_link_outside_range` — sheets whose standard link or
`full_sheet/` was left at a flight outside the task (never backwards), the CLI then prints
one `Info:` with the line `<sheet_code>: sciezka standardowa|full_sheet/ ->
dowiazanie <date>_<id>`. Further details: a single rule
`DownloadManager._select` (shared by download and `inspect_sheets`)
decides per record "local version or download"; the download
(`GugikProvider.download_record` into a working directory, `record_source`
-> `extra.source`) is finished by `commit_version` (ADR-036); after collecting campaigns the
manager moves the link ONCE per sheet (deduplication of sheet codes; never
backwards). `download_sheet`, `download_hierarchy` and `download_sheets`
return `DownloadResult`: `succeeded`, `failed`, `skipped`, `no_coverage`
(subset of `failed`: no data at the source), `no_coverage_hints` (sheet code ->
`NoCoverageError.hints`), `campaign_files`, `reused_campaign_files`
(versions already local per sheet), lists `new`/`relabeled`/`unchanged`/`local`,
`newer` (sheet code -> newer campaign not downloaded), `unverified`, `stale`
and `notices`. `files[godlo]` contains `VersionedFile` for each selected
flight, with status, label and version path. The result of a single sheet
has the same shape as a list result. Full list of fields: the docstring of
`DownloadResult` in `download/manager.py`. The origin of a sheet
with campaigns: `provider.source_info()` fills in the single-record flow
(`download`, `get_download_url`, `resolve_campaigns` in `newest` mode), and with
`all` it stays `None` — the source of origin is then the sidecar
(`extra.source`, `extra.campaign`); the sidecar of the standard path describes
the version the link points to, and it may be older than the newest
record (D5 or a failed download, A12). Before the network
`verify_record_url` (B4): the file name in the record URL must end with the sheet
code (`<id>_<number>_<sheet_code>.<ext>`, compared in canonical form;
ADR-041 archive names also with endings `.xyz.zip`, `.zip.zip`,
`_asc.zip`, `_tin.zip`, prefix `NMT-` and a sheet code without separators);
a URL without a sheet code or with a different sheet code = campaign `DownloadError` without downloading.
File: format from the record's `format` field (not from the URL; no field — the product's
default format), the extension is always canonical from the registry `FORMATS`
(`.asc`/`.tif`; archives `.zip`, `.ttn`, `.grd`, `.dxf`, `.dgn`); an
NMT/NMPT record whose URL does not match the `format` field (e.g. a grid with URL
`.zip`), does not pass the hard format filter and is not downloaded
(the `.xyz` name of campaign 72675 grids is accepted: AAIGrid checked
live and again after download). After download `verify_file_format`
(AAIGrid header / TIFF signature; archives: complete ZIP with a readable central
directory, TTN signature, Intergraph GRD/DGN header,
`SECTION` DXF), then `verify_sheet_extent` (B4,
only `.asc`): the extent from the ASC header (`xllcorner`/`xllcenter`,
`yllcorner`/`yllcenter`, `ncols`, `nrows`, `cellsize`; the `*center` variant
shifted by half a pixel) must lie at least 50 % of its area
(`MIN_FRAME_OVERLAP`) within the sheet frame computed in the FILE's CRS:
`x < 1e6` = EPSG:2180 (also a PL-2000 sheet published by GUGiK in
EPSG:2180, E17), otherwise the native PL-2000 zone of the sheet. A partial sheet
(`full_sheet=False`) lies within the frame and passes, a neighbouring sheet or one from
another place does not; an unreadable or incomplete header = error. An unknown
format or mismatched content = campaign `DownloadError` with the format name,
an extent outside the frame = `DownloadError` with the file extent and the sheet frame;
no version is created. The download error
gives the file name from the URL (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData):
HTTP 404`), which in `all` distinguishes campaigns. Failures: a campaign (including
an invalid `aktualnosc` of a record in `all`, missing sidecar, verification
failure, sha256 collision) = failure of that campaign — the others are downloaded,
the link goes to the newest valid one, but the sheet ends as a failure (a failed item, exit code 10 or 11);
failure of the link itself (also lack of hard links) = sheet failure (the list
continues also with `--workers 1`, saved versions remain). A race without
locks: parallel writes of the same content end up in one version
(exclusive `os.link`), and parallel link moves may temporarily
leave it on an older version; the next call repairs it.

**Modes and update plan (ADR-036, D5, D14).** `update` in
`download_sheet`/`download_hierarchy`/`download_sheets` (CLI: no flag,
`--upgrade`, `--force`; mutually exclusive with `--check-updates`):
by default a local version with the record label is used without download,
missing versions (`all`, `--full-sheet`, no local one) are downloaded,
and when the newest flight is not local, but there is another local version
from the range (the link target first), it stays and `DownloadResult.newer`
(CLI: suffix `; dostepna nowsza <label> (--upgrade)` and `Info:`).
`update="upgrade"` downloads that flight; `force` downloads all selected
flights again and refreshes `MetadataCache` (the same content = `unchanged`,
different = a new version of the same label), record verification works in
all modes; `update="check"` is a `ValidationError` (checking
is done by `manager.check_sheets(sheets)`). Providers without campaigns: without `force`
the newest local version (no cheap signal).
`DownloadManager.check_sheets(sheets)` (CLI `--check-updates [--plan PLIK]`)
downloads nothing and returns `UpdatePlan` (`kartograf-plan/1`: `store`,
`checked_at`, `kartograf_version`, items with segment, hierarchy, name,
local version and record signal; statuses `current`/`newer`/`missing`/
`unverifiable`/`check_failed`). `manager.download_sheets(sheets,
update="upgrade", plan=plan)` (CLI `--upgrade --plan PLIK`) rejects a different
store and an unknown schema before the network, reads the signal again and downloads
only `newer`/`missing` items with an unchanged signal; a changed
signal = item `result.stale` (error, no download). The plan types are in
`download/plan.py` (`PlanItem.track` = `pl_sheet`/`laz_tile`/`cz_sheet`/
`cz_laz`/`pl_cutout`/`cz_cutout`, `unit` = task unit; `UpdatePlan.merge`,
`select_planned`, `new_plan`); the remaining tracks get `plan=` in their
`run_*`.

**Data states in checking (0.8.0, E2E P2-3).** `check_sheets(sheets,
on_no_coverage=)` reproduces the download result, not only the items: a sheet without
data (`NoCoverageError`) is neither a plan item nor a checking failure —
`on_no_coverage(brakujace, liczba_arkuszy)` receives those sheets
(`download/data.py` turns them into `NO_COVERAGE_SOME` and `NO_COVERAGE_HINT`,
with the download text, `_no_coverage_warning`/`_coverage_hints`), and when no
sheet has data, it raises `NoCoverageError` (single sheet: its
own; list: `no_coverage_text`). Sheets with data only outside the year range are
ONE `YearRangeError` (`year_range_error`, like `_checked_range`), and
`check_failed` remains for sheet index failures. `check_data` then throws the error
of the first failure (`_Run.causes`): the exception class is the error (`NoCoverageError` and
`YearRangeError` are `no_data`, exit code 14, with the reasons `no_coverage` and
`year_out_of_range`), and in the download report the same name is `UnitFailure.kind`
(`_failure_kind`; `download` and `country` for the rest).

**Tracks without campaigns (plan 2/3; LAZ CZ: plan B).** LAZ (`download/laz.py`),
LAZ CZ (`download/cz_laz.py`), CZ sheets
(`download/cz_sheets.py`), CZ cutouts (`download/cz_cutout.py`) and PL
(`download/cutout.py`) as well as the track without campaigns of `DownloadManager` use
a single policy from `download/fetch.py`: `fetch_version(slot, update,
signal=, fetch=, version=, write_sidecar=, probe=)` — local version or
download into `.incoming/`, `commit_version(signal=)`, hard link — and
`inspect_version` (plan item without downloading; `check_laz_area`,
`check_cz_laz`, `check_cz_sheet`, `check_cz_cutout`, `check_pl_cutout`).
The signal by channel (`AccessChannel.update_signal`, `channel_signal`): LAZ
`index` (a tile with a local version = `local`, a newer survey means new files,
D26), openzu files — SM5 sheet, native TM33 tile (plan B) and LAZ CZ —
`http` (`probe` = the provider's `file_signal`, `HEAD` of the `openzu` file).
The default mode does not ask the source about the local version (erratum 3 of ADR-036):
`http` + `probe` and `metadata` + `edition` give a local version
`unverified="unchecked"` without a query (line `(bez sprawdzania;
--check-updates)`); `upgrade` does `HEAD` (equal `ETag` = local, different =
download, failed `HEAD` = error), `--check-updates` = `inspect_version`.
The label of an index record (`index` + `edition`) is known from the file selection,
so the comparison remains in every mode. A TM33 tile from ImageServer and
cutouts `none` (local, `unverified="none"`). Result: `VersionedFile(path, status, label, sha256,
version_path, newer, unverified)`; `LazDownloadResult.files`,
`CzLazResult.files`, `CzSheetResult`/`CzCutoutResult`/`PlCutoutResult.file`
(`None` only with `plan=`, when the plan does not perform the file and there is no local
version) and `stale`. The fields of a local version result (`all_nodata`, `masked_pixels`,
`zero_pixels`) come from the version sidecar, without reading the raster.

The CLI prints one line per file: `<sheet_code>: nowa wersja <label>_<sha8>`,
`nowa etykieta <label> (plik identyczny z <label>)` (the newest
existing version with the same sha256, `VersionedFile.same_as`),
`bez zmian <label>`,
`lokalna wersja <label>`, and after the list (without `-q`) `Nowe: N, nowa
etykieta: N, bez zmian: N, lokalne: N, bledy: N (<dir>)` (PL sheets
and LAZ tiles; PL LAZ unit = file name, LAZ CZ = sheet code, cutout = path under
`--root`). A file without a cheap signal: by default the suffix `(bez
sprawdzania; --check-updates)`, with `--upgrade` an `Info:` about `--force`;
a failed signal check: `Warning:`. The `--check-updates` report is
one line per item (`aktualne`, `nowsza: ...`, `do pobrania`, `nie da
sie sprawdzic bez pobrania`, `nie udalo sie sprawdzic: ...`); land cover,
soils and HSG mark items with the path under `--root` like the status line
(GPKG and raw ZIP `--keep-raw` of the same TERYT = two different lines), an unchecked item
makes the plan `ok: false` (exit code 10 or 11); with `--plan` the CLI writes ONE plan of all
tracks of the task (`--country auto`: PL and CZ, `UpdatePlan.merge`), and
`--upgrade --plan` reads it once before work. The `kampanie/` directory from 0.7.x:
a one-off `Info:`.

A sheet index failure without a year bound (I-1, erratum 5 of ADR-030; ADR-036: every
strategy, default mode only): when `resolve_campaigns` ends with a
TRANSPORT error (`DownloadError` with `status_code` 429/5xx or without a code,
but with the cause `requests.RequestException` — network/timeout; NOT
`NoCoverageError`, other 4xx or an OGC report/bad template), and the standard path
points to an existing local version (`linked_version`),
the manager does NOT report a failure: the sheet has status `local` with
`unverified=<error content>`, link unchanged. List/hierarchy: the sheet
in `skipped`, and `DownloadResult.unverified` (sheet code -> error content). CLI:
`Warning: <sheet_code>: skorowidz GUGiK niedostepny - uzyto lokalnej wersji bez
sprawdzenia nowszej (<error>)` (single sheet code) or `Warning: skorowidz
GUGiK niedostepny - dla N arkuszy uzyto lokalnych wersji bez sprawdzenia
nowszej (<up to 10 sheets>) (<first error>)` (list), stderr also with `-q`, code
unchanged. `upgrade`, `force` and no local version (also a link
with a removed target version) — error. With a year bound: D14 (above).
A library without `MetadataCache` queries the
sheet index at EVERY `download_sheet` (also for an already downloaded sheet);
passing the cache to the provider limits this to once per 7 days.

Result: `data/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/<date>_<id>_<sha8>/N-34-130-D-d-2-4.asc`
(+ `.meta.json`) and the link `data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`;
for NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, for other resolutions
and archives the variant segment (e.g. `data/nmt/pl_1992_0.5m_evrf2007/...`,
`data/nmt/pl_1992_tbd_25m_kron86/.../<sheet_code>.zip`), for orthophoto
`data/orto/pl_1992/...`.

### 4.2 PL bbox / geometry without `--cutout`

The bbox goes to `download_data` (`download/data.py`), which resolves the countries
(section 4.6), and the Polish part goes to the PL sheet track. `find_sheets_for_bbox` (pure grid
mathematics, no network queries — ADR-010) returns the list of 1:10000 sheet codes, which
`DownloadManager` downloads in parallel. In `--geometry` mode the sheets are determined by
the geometry of each object (`find_sheets_for_geometry`), not by its envelope.
When `--geometry` points to a GPKG with several layers and `--layer` is not given,
the library selects the first `gpkg_contents` layer and emits ONCE before
the work a `Notice` `GEOMETRY_LAYER_DEFAULT` with its name, the remaining layers
and the hint `--layer NAZWA` (CLI: `Info:`, also with `-q`). It also applies to
`download_landcover`, `download_soil` and `calculate_hsg`; SHP
and a single-layer GPKG give no message.

The sidecar of a downloaded sheet gets `extra.parent_request` and `extra.source`
(URL, layer, date, resolution). Reusing a version does not
change its sidecar (ADR-036). List mode (also a sheet code hierarchy) tries
ALL sheets regardless of `--workers` (ADR-027 erratum 3, R5-list).
`NoCoverageError` appends the missing sheet code and a `Warning:`, progress status
`no_coverage` (icon `0`, `DownloadProgress.status`), without vetoing the downloaded
files. The hints `NoCoverageError.hints` (e.g. `--scale 1:2000`) are
`Notice` `NO_COVERAGE_HINT` (CLI: `Info:` on stderr, also with `-q`), without
literal duplicates, at most `MAX_HINT_LINES` lines plus `... i N innych
podpowiedzi` (full list: `DownloadResult.no_coverage_hints`). Result
`DataReport.ok`: >= 1 file and zero hard failures = `True` (code 0). When
all sheets are missing or any other download failure occurs,
`DataReport.failed` has entries, `ok` = `False` (exit code 10 or 11, status `partial` or `failed`).
A single sheet without data is exit code 11; under `--country auto` the code also depends
on the success of the second country (section 4.6).

The campaign and year options (`--all-campaigns`, `--year`, `--min-year`, `--max-year`,
section 4.1) work here per sheet; the `all` summary counts campaign files,
not sheets. A sheet without data in any year has status `no_coverage`
(`Warning:` R5); a sheet with data only outside the range is
`YearRangeError` and aborts the WHOLE list before download, also with
`--min-year` alone. A failed sheet index check also aborts the list.
The same applies to `--check-updates`: sheets without data are `NO_COVERAGE_SOME` and code 0
(no sheet with data = `NoCoverageError`, `no_data` with the reason `no_coverage`, exit code 14),
a year conflict is a single `YearRangeError` (`no_data`, reason `year_out_of_range`) for all
sheets (section 4.1).

**GUGiK archives (`format` other than `ASC`, ADR-041).** Archive sheets
have different scales (6-part sheet codes 1:25000 and 7-part codes of a single variant,
PL-2000 sheets), so they are not determined by the sheet code grid but by the sheet index:
`download_data` -> `_download_pl_archive` (`download/data.py`) with the area
as convex polygons in EPSG:2180 (`--sheet` = sheet frame
`sheet_frame_2180`, `--bbox` = envelope `bbox_to_2180`, `--geometry` =
envelopes of the objects) calls `GugikProvider.index_sheets(areas, system=,
min_year=, max_year=)`: variant records (hard filter on format,
resolution and system) of the yearly types within the year range whose frame
(`msGeometry`, otherwise the sheet frame) intersects the area by more than an edge
strip (`overlaps_area`: frame narrowed by `EDGE_TOLERANCE_M` = 1 m — a neighbour
touching only at an edge does not count). Then the usual sheet track
(`DownloadManager.download_sheets`: campaigns, versions, sidecars,
`full_sheet/`), but sheet codes from the sheet index are not expanded to 1:10000
(`DownloadManager` recognises the `source_file` variant). An empty list =
`no_coverage` failure with the text `Skorowidz GUGiK nie ma plikow ... -
dostepne dane obszaru: kartograf elevation availability`. `--scale`
and `--cutout` with an archive = `ValidationError` before the network; `--sheet-system`
is required as for grids. Content verification: `verify_file_format`
(4.1), without `verify_sheet_extent` and coverage measurement.

**WCS (`provider.download_bbox`) in the library: NMT/NMPT 1 m and orthophoto.**
The PL CLI uses WCS only with `--cutout` (section 4.3); without this flag it
downloads OpenData sheets. `GugikProvider.download_bbox` for NMT 1 m and
`GugikNmptProvider.download_bbox` for NMPT 1 m return a single-band float32 GeoTIFF
with heights on a 1 m EPSG:2180 grid (without nodata, PRG mask,
sidecar and version — the file is outside the store). `DownloadManager.download_bbox`
was removed in 0.8.0 (D27, erratum 2 of ADR-003): a cutout in the store is
`download_pl_cutout`.
WCS has only the 1 m variant (channel `bbox_raster` in the registry,
`is_wcs_available()`); a provider of another resolution or an archive
gives `ValidationError`. NMT KRON86: endpoint
`DigitalTerrainModelFormatTIFF`, coverage `DTM_PL-KRON86-NH_TIFF`,
`image/tiff` float32; NMT EVRF2007: `DigitalTerrainModel`,
`DTM_PL-EVRF2007-NH`, `image/x-aaigrid`; NMPT KRON86/EVRF2007:
`DigitalSurfaceModel`, `DSM_PL-<v>-NH`, `image/x-aaigrid`.
The old EVRF2007 TIFF endpoint returned 404, but EVRF2007 ASC works
(report `docs/research/2026-10-11-wcs-cutouts/raport.md` item 1).
`WITHDRAWN_WCS_VERTICAL_CRS=()` preserves the mechanism for future withdrawals.

`GugikWcsMixin._download_wcs` aligns the bbox OUTWARDS to the grid
`GridSpec(1.0, 0.5, 0.5)`: pixel edges `k + 0,5` m, the result may
extend by < 1 px further on each side. `plan_wcs_chunks` widens the range
by at most 1 px to the east/south to an even width and height
and cuts it into even chunks (`plan_chunks(multiple=2)`); the excess
is clipped after stitching. Reason (live verification
`docs/research/2026-10-11-wcs-cutouts-live/raport.md` item 3): when the server
resamples (NMPT `SCALEFACTOR`, NMT 1 m over a 0.5 m flight), with an
odd size it takes the middle row and column from the neighbouring
source pixel. Limits: 16 Mpx and 40000 px per side for TIFF, for the
slower ASC (approx. 20 s/Mpx, response only after the whole chunk is computed)
1 Mpx of coverage pixels in NMT and 4 Mpx in NMPT (1 Mpx of a 1 m result;
host hangs do not depend on chunk size, and a 4 Mpx chunk
responds like 1 Mpx — `docs/research/2026-10-11-nmpt-asc-tuning/raport.md`).
An ASC chunk waits for data at least `WCS_ASC_READ_TIMEOUT` = 120 s
(first NMPT byte live up to 106 s). NMPT has a native coverage step of
0.5 m; `SCALEFACTOR=0.5` gives a 1 m result on the sheet grid. `fetch_chunks`
assembles sequential chunks without
resampling and retries each separately. `transport/aaigrid.py` extracts
ASC from the multipart response in streaming mode, checks the header and atomically writes
a GeoTIFF with EPSG:2180; invalid content = `DownloadError` without
retries. XML reports are rejected by `reject_error_document("WCS")`.
The orthophoto remains on its own `download_bbox` path.

Result: **many files** — a list of sheets in the segment as in 4.1 (links to
versions in `versions/`; with `all` additionally each campaign). This is an
asymmetry relative to CZ, where a bbox gives a single cutout.

**GUGiK images of plan E1 (ADR-043).** Intensity, true orthophoto and oblique
orthophoto go through the orthophoto sheet track (`DownloadManager`, campaigns, versions,
signal `index`): one provider `GugikImageProvider`
(`providers/pl/gugik_orto.py`) parametrised by the descriptor's `SheetIndexParams`
(section 3.1). The area expands to the sheet codes of the sheet index series
(`series_scale(sheet_parts)`: true orthophoto `1:5000`, 8-part sheet codes;
a single sheet system = `--sheet-system` can be omitted). Oblique orthophoto is
four managers — one per direction (`data._managers`, provider
with `direction`, `storage_suffix` `_n`/`_e`/`_s`/`_w`); `verify_record_url`
strips the direction suffix from the file name (`_N.tif`), and
`DownloadManager._download_planned` narrows the plan entries to the manager's segment
and file name. A `HEAD` precedes the `GET` of an image sheet; a file
over 100 MiB (`LARGE_FILE_BYTES`) gets a `Notice` `download_size`
with the size (K9). True orthophoto cutout: section 4.3 (`download_image_cutout`,
the descriptor's `WCS` channel, without a `coverage` token in the segment).

**NMT 100 m (ADR-043 D10).** `--resolution 100m` is a registry variant without
a sheet index (`pl_file_variant`): the area (`--bbox`, `--geometry`, `--sheet`
frame) yields voivodeships from PRG (`discover_teryts_for_bbox`, the first two
TERYT digits), and for each one a GUGiK ATOM feed file
(`collections.atom_area_request`, `collection` plan track, slot
`nmt/pl_1992_100m/teryt/<woj>.zip`, signal `metadata` with `updated` of the dataset
entry). Flags for sheets, flights, cutout and `--vertical-crs` = `ValidationError`
before the network.

### 4.3 PL bbox / geometry with `--cutout` (ADR-035, ADR-038, ADR-042 D14)

The CLI `elevation download --bbox`/`--geometry --cutout --horizontal-crs` and the
library `download_data(cutout=True, horizontal_crs=...)` and
`download_pl_cutout()` download NMT or NMPT 1 m from GUGiK WCS and do not
mosaic sheets (the orthophoto has its own cutout track — end of the section).
The mode is explicit: `--horizontal-crs` is required
with `--cutout`, without `--cutout` it is an `Error:`, `--cutout` with `--sheet` too.
Library: `download_pl_cutout(*, bbox, horizontal_crs,
root, vertical_crs, product="nmt"|"nmpt", update, plan,
parent_request, cache, on_notice)` -> `PlCutoutResult`;
`check_pl_cutout(...)` with the same selection returns a plan without downloading.
Preparation (validation without network) and execution are internal steps
(`_prepare_pl_cutout`, `_run_pl_wcs_cutout`), outside the API since 0.8.0.

1. The cutout has only the 1 m variant: `download_pl_cutout` has no resolution
   parameter (a variant with a WCS channel from the registry,
   `download/cutout.py::wcs_variant`: `pl.gugik.nmt_1m` / `pl.gugik.nmpt`),
   and `download_data(cutout=True)` rejects before the network any resolution
   other than `1m` and an archive `format` (`ValidationError`; CLI `Error:`, texts
   in USAGE 1.3; no `resolution` = `1m`). `download_pl_cutout` rejects
   an unsupported target vertical/CRS
   (`EPSG:2180`, `EPSG:5514`, `EPSG:3045`) and the lack of a safe
   pinned transformation operation. The target bbox determines the bbox of the
   EPSG:2180 source; for the warp it has a margin of 4 px for interpolation.
   `--geometry` gives the envelope of the whole geometry, without masking to its
   objects. `--sheet-system 2000`, `--cutout` with a sheet code or with LAZ
   are still rejected before download.
2. `download_pl_cutout` downloads and builds the PRG land mask **before**
   any WCS request: `A00_Granice_panstwa` minus
   `W02_Morze_terytorialne_RP` minus
   `W03_Morskie_wody_wewnetrzne`. `A00` is downloaded without BBOX
   (PRG does not clip its geometry); `W02`/`W03` with the BBOX of the area.
   Rasterisation takes the pixel centre (`all_touched=False`), including
   over border rivers, bays and lagoons. Outside the mask nodata
   `-9999`; on land the WCS values, **also 0.0**, remain data
   (Żuławy). The mask does not fill zeros inside land from sheets. An area with
   not a single pixel centre on land (`LandMask.has_land`: sea,
   abroad) ends with `NoCoverageError` before WCS, without a version (CLI:
   `Error:`, exit code 11 `failed`; like sheet mode).
3. The provider downloads through `_download_wcs(bbox_source_2180, work,
   "GTiff")` on the 1-metre sheet grid
   `GridSpec(1.0, 0.5, 0.5)`, with the bbox aligned OUTWARDS
   (ADR-034 chunks and per-format limits in 4.2). For EPSG:2180
   the masked result goes atomically through `os.replace` to the file;
   for EPSG:5514/3045 `warp_to_grid` with the pinned operation, nodata
   and target grid performs a local reprojection. `PlCutoutResult`
   gives `masked_pixels`, `zero_pixels` counted before the warp and
   `all_nodata`. `all_nodata` with a `Warning:` (code 0) remains only for WCS
   without data on land.
4. The result is in `nmt/pl_1992_1m_<vcrs>/bbox/` or
   `nmpt/pl_1992_1m_<vcrs>/bbox/` as a
   link `<coords>.tif` (without date, D15) to the version
   `versions/bbox/<YYYY-MM-DD>_<sha8>/<coords>.tif` (+ the version's `.meta.json`),
   where `<coords>` describe the task bbox IN THE RESULT CRS,
   not the aligned raster. Steps 2-3 (PRG mask, WCS, warp) run
   in the private `versions/.incoming/`, and the result is saved by
   `fetch_version` (signal `none`): by default and with `upgrade` the local
   version without PRG and WCS requests (result fields from the version sidecar, space
   check only when downloading), `force` downloads again (the same
   content = `unchanged`; cutouts are byte-reproducible, inventory
   2026-10-12). `--workers` and `--scale` do not change the WCS track. A failure
   leaves the previous version and link, without an empty tree.
   Files `<coords>_<YYYYMMDD>.tif` from 0.7.x are not recognised. A sidecar with
   `capability="bbox_raster"`, `extra.source` WCS and `extra.mask`
   PRG is described in section 3.2. The CLI prints `Info:` with the number of WCS
   requests and the estimated time (`WCS_REQUEST_SECONDS` = 25-40 s per request,
   measurement 2026-10-16/17) for > 1 chunk or a result >= 1 GiB (when the cutout
   will be downloaded, after the PRG mask).

WCS returns the server's composition (the newest flight of the area without appending
older ones), **not** the newest campaign of exactly 1 m selected for a sheet
by ADR-028. Over a 0.5 m flight the 1 m result is decimation (a 0.5 m pixel
centred on a whole metre), not a 2 x 2 average. When the flights are the same
and the grids match, the measured WCS and sheet are bit-for-bit identical
(`docs/research/2026-10-10-wcs-limits/raport.md` items 4, 8 and
`docs/research/2026-10-11-wcs-cutouts/raport.md` items 2-4).
`--year`, `--min-year`, `--max-year`, `--all-campaigns` and
`--full-sheet` with `--cutout` remain an `Error:` before the network;
the server does not offer a choice of flight.

The cutout sheet track (ADR-027: `select_pl_cutout_sheets`,
`run_pl_cutout`, `build_cutout_from_sheets`, `PlCutoutSheets`, the sheet
parameters of `download_pl_cutout` and `mosaic_and_crop(snap_to_source_grid=,
assign_crs=)`) was removed in 0.8.0 (ADR-035 erratum 2). Merging PL+CZ
into one surface remains stage 2; under `--country auto` two
files are produced with a shared `extra.parent_request`.

**PL orthophoto cutout (ADR-042 D14, since 0.8.0).** `imagery download
--product orto --country pl --bbox|--geometry --cutout --horizontal-crs
EPSG:2180 --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` =
`download_data(product="orto", cutout=True, horizontal_crs="EPSG:2180",
coverage=..., resolution=...)` -> `download/orto_cutout.py::
download_image_cutout(*, product, bbox, horizontal_crs, root,
resolution, coverage=None, update, plan, parent_request, cache, on_notice)` ->
`ImageCutoutResult(file, stale, notices)` (ADR-044 D3: one pair for
`product="orto"` and `"true-orto"`); `check_image_cutout(...)` with the
same selection gives the plan (track `pl_cutout`; local version =
`unverifiable`). Unlike NMT/NMPT:

1. Validation without network (`orto_cutout_error`, `cutout_choice_error`):
   `--coverage` (`standard` - the latest available orthophotos, `high` -
   orthophotos with a pixel of 10 cm or smaller) and `--resolution` (result
   pixel `0.1m`, `0.25m`, `0.5m`, `1m`; labels from
   `WcsCutoutParams.resolutions`) are required with no defaults,
   `--horizontal-crs` only `EPSG:2180` (no local resampling of the
   image), PL only (`--country cz` or an area only in CZ = error; under
   `auto` `--coverage`/`--resolution` narrow the task to PL), no
   `--sheet`, year or campaign; `--coverage` or `--resolution` for orto without
   `--cutout` = error. RGB composition only. There is no PRG land mask: pixels
   without an image in a cutout with an image stay 0,0,0 as from the server.
2. Grid: bbox (any supported CRS, geometry = envelope)
   converted to EPSG:2180 and aligned OUTWARDS to a multiple of the
   pixel; the file name carries this grid. `GugikOrtoProvider(color="RGB",
   coverage=, resolution=)` takes the endpoint and coverage from the registry channel;
   a pixel other than 0.1 m = `SCALEFACTOR` (0.1 m / pixel). Chunks have
   a budget of 4 Mpx of coverage pixels (200 x 200 m of terrain regardless of the
   result pixel - a 1 x 1 km area is 25 requests) and even sizes (an odd
   number of 0.25 m pixels is a fraction of a coverage pixel: wrong grid or
   HTTP 400); they are downloaded one by one and stitched without resampling, with a chunk
   read limit of 300 s (`WCS_CUTOUT_READ_TIMEOUT`; measurement 2026-10-15:
   4 Mpx Standard 64 s, 2000 x 2000 px at `SCALEFACTOR=0.4` 176 s).
3. Before the first request: `Notice` `cutout_size` (px, MiB, number of
   requests) for more than one chunk or >= 1 GiB, and a check of
   disk space (2 x result size, otherwise `ValidationError`).
   The result is checked (size, step, NW corner, 3 uint8 bands,
   EPSG:2180): a different grid = `DownloadError` with no version. A result with
   no image pixel at all (HTTP 200 with a 0,0,0 image: true orto outside
   the selected cities, High outside the areas of 10 cm pixels, Standard outside
   orthophotos) ends with `NoCoverageError` BEFORE the version is written
   (`_no_image_error`, content with the cause and the channel remedy, for High
   `--coverage standard`; the service does not publish the cutout extent, so the image
   is checked after download; staging removed; in `download_data`
   a `no_coverage` PL failure, CLI `Error:`, exit code 11) - like an NMT/NMPT cutout
   outside land.
4. Store: hard link `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`
   to the version `versions/bbox/<YYYY-MM-DD>_<sha8>/`, signal `none`:
   by default and with `--upgrade` the local version without requests, `--force` downloads
   again (the same area and pixel = the same bytes = `unchanged`).
   Sidecar: section 3.2.
5. Stitched chunks are NOT bit-for-bit equal to a single request for the whole
   area: the server resamples each request within its extent (measurement
   2026-10-16: 20 x 20 m at 0.1 m - 75-93 % of pixels differ, mean
   4 DN, max 89; 40 x 40 m at 0.25 m - 70 %, mean 4.4 DN, max 120);
   only NMT stitches bit for bit (ADR-034 erratum 1). WCS returns the
   server composition without a choice of year; in samples (Krakow, 2026-10-15/16)
   High and Standard gave the same bytes over the same area.

`GugikOrtoProvider.download_bbox` without `coverage` remains a raw
Standard request outside the store (one request without alignment).

### 4.4 CZ sheet code (NMT: DMR 5G / DMR 4G, NMPT: DMP OK / DMP 1G) and CZ orthophoto

A CZ raster selects `product` (`nmt`|`nmpt`), `resolution` and `vertical_crs`
from the registry variants (section 3.1; plan B, decision 2):
`CuzkRasterProvider.route(sheet=None) -> CzRasterRoute(channel,
horizontal_crs, horizontal, vertical)` selects the channel, the result CRS
and the pinned operations BEFORE the network (`sheet=None` = cutout, section 4.5):

| Model (`--product`, `--resolution`) | SM5 sheet (`CTES96`) | TM33 tile (`760_5518`) |
|---|---|---|
| DMR 4G (`nmt`, `5m`), DMP OK (`nmpt`, `0.5m`) | openzu file EPSG:5514 (Bpv); EVRF2007: file + vertical transformation | EVRF2007: openzu file EPSG:3045 natively; Bpv: `exportImage` + local warp |
| DMR 5G (`nmt`, `2m`), DMP 1G (`nmpt`, `2m`) | none (`ValidationError` before the network: SM5 only 5m / 0.5m) | `exportImage` + local warp (EVRF2007: + vertical transformation) |

A TM33 tile without a variant file is expanded by `ParserTM33` to a bbox in EPSG:3045; the CUZK
server receives an `exportImage` request **exclusively in the native CRS EPSG:5514**
(plus a margin of 4 px), and a local warp with a pinned operation moves it onto the tile grid
(ADR-024 — server-side reprojection lost the datum shift). Such a tile
is therefore not a 1:1 product: it is a warp from EPSG:5514 onto the EPSG:3045 grid,
with the pinned Czech S-JTSK -> ETRS89 operation (EPSG:1622/1623,
nominally 1.0 m; ADR-024 erratum 2).
`exportImage` responses are always a server derivative (bilinear; the grid of the
DMR 5G service has a phase of (0.4; 1.88) m mod 2), so only openzu files give 1:1:
the SM5 sheet DMR 4G/DMP OK (EPSG:5514) and, since plan B, the TM33 tile DMR 4G/DMP OK
in EVRF2007 (ETRS89 file, EPSG:3045), without a warp — the file is a TIFF without CRS
(georeferencing in `.tfw`), so after download only the CRS metadata
is overwritten (the channel CRS). `--vertical-crs EVRF2007` appends the pinned
vertical transformation Bpv -> EPSG:5621 (in-place shift) where the
channel gives Bpv (SM5 sheet, ImageServer); the TM33 file has EVRF2007 natively
(without `_apply_vertical_shift`, sidecar without a vertical operation). `KRON86` for
CZ is unreachable (no public grids). An SM5 sheet may omit
`resolution` (the product has one label with SM5 files: NMT 5m, NMPT 0.5m);
a TM33 tile requires it. The sidecar is written by the library (`download/cz_sheets.py`,
`download_cz_sheet`) from the route: result CRS, pinned operations,
`capability` (`sheet_files` for a file, `bbox_raster` for `exportImage`)
and the file's `extra.http`.

A TM33 DMR 4G EVRF2007 tile downloaded before plan B (warp, version without
`extra.http`) stays in default mode a local version
(`unverified="none"`, `Notice` `unverified_local`: unverified, CUZK
file via `--force`); `--force` downloads the CUZK file as a new version
and repoints the hard link (decision 12 of plan B).

Result: `data/nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (`horizontal_crs`
EPSG:3045) or `data/nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif`
(`horizontal_crs` EPSG:5514); NMPT e.g.
`data/nmpt/cz_dmpok_evrf2007/760/5518/760_5518.tif` (ETRS89 file,
`vertical_crs` EPSG:5621) or `data/nmpt/cz_dmp1g_bpv/760/5518/760_5518.tif`
(warp from `dmp1g`).

**SM5 sheet codes with two letters (since 0.8.0).** `CZ_SM5_PATTERN` =
`^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$`: 99 As sheets (`AS22`...`AS94`; the SM5
index has 16,299 sheets) are recognised as `cz_sm5` (`AS91` ->
`AS/91`), also for DMR 4G; previously `detect_system("AS91")` returned the
`pl1992` fallback, so the sheet ended with a PL sheet code error.

**CZ orthophoto (ADR-042 D13, since 0.8.0).** `imagery download --product
orto --country cz` (SM5 sheet code - the country also from the sheet code - or an area) =
`download_data(product="orto", ...)` -> track `download/cz_orto.py`: a sheet code
via `cz_orto_sheet` (TM33 tile = error with an SM5 hint), an area ->
SM5 sheets from the `KladyMapovychListu` index (`cz_orto_area_sheets`; bbox
converted to EPSG:5514 with the pinned operation; `Notice` `sheet_list`),
each sheet `download_cz_orto_sheet(*, sheet, root, update, plan,
parent_request, cache, on_notice, on_download)` -> `CzOrtoResult(files,
stale, notices)`; `check_cz_orto_sheet` gives four plan items of the track
`cz_orto` (unit = sheet code). The release comes from the ORTOFOTO ATOM feed
(engine `atom_files`, section 4.10): one `resolve_atom_file` per sheet
(result and failure remembered for the four files, `check_failed` once
per sheet), label `<year>_<updated>` (e.g. `2024_2025-02-06`), signal
`metadata`: by default local versions are compared with the release (a newer
vintage = a note `dostepna nowsza ... (--upgrade)`), `--upgrade` downloads
the new vintage (old versions stay in `versions/`), `--force` downloads
again. Download: one ZIP (16-64 MB; read limit 120 s; size =
feed `length` and `Content-Length`) to `versions/.incoming/`, members
`.jpg`, `.jgw`, `.TM33N.jgw`, `.TM34N.jgw` copied 1:1 (without pixel
conversion) and written in the order `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`,
`.jpg` as `orto/cz_sjtsk/<hierarchy SM5>/<sheet_code><suffix>` (the JPEG version
always has JGW files). Only the current vintage of a sheet (archival
CUZK orthophotos are paid): year and campaign flags, `--full-sheet`,
`--sheet-system`, `--scale`, `--vertical-crs`, `--format` and `--resolution`
with `--country cz` = error, `--cutout` with CZ = error. JGW does not carry a CRS -
the CRS of each file is given by its sidecar (JPEG: `extra.world_files`,
section 3.2). The sheet pixel follows from JGW (samples 2026-10-16: 0.125 m).

**CZ contours (plan E1, since 0.8.0).** `elevation download --product
contours --format SHP|DGN` -> track `download/cz_contours.py` (dispatch
`data._download_cz_contours`, like CZ orthophoto): an SM5 sheet code (TM33 tile =
error) or the SM5 sheets of an area with CUZK files
(`SheetIndex.file_sheets("sm5")`, bbox converted to EPSG:5514 with the pinned
operation). Each sheet: an openzu ZIP from the channel template of the format descriptor
(`cz.cuzk.zabaged_contours_<format>`) downloaded 1:1 to
`contours/cz_zabaged_<format>/<hierarchy SM5>/<sheet_code>.zip`; before the
version is written the ZIP members and their CRC are checked (an HTML page or a truncated ZIP
= `DownloadError`, no version), sidecar: list of members (`extra.members`),
`mapname`/`cz_share` from the index, `extra.http`, CRS EPSG:5514, heights
Bpv. Signal `http` (`HEAD` for a local version only with `--upgrade`), plan track
`cz_sheet` (unit = sheet code). `--resolution`, `--cutout`,
`--horizontal-crs`, PL sheet and flight flags = error before the network
(`options._contours_error`).

### 4.5 CZ bbox

A single `exportImage` cutout of the variant service (DMR 5G `dmr5g`, DMR 4G `dmr4g`,
DMP OK `dmp_obrazova_korelace`, DMP 1G `dmp1g`); a CZ raster area requires
`--cutout --horizontal-crs` (ADR-038; without `--cutout` `ValidationError`
before the network; CZ LAZ for an area means sheets from the index, section 4.7; CZ orthophoto
for an area means SM5 sheets, section 4.4). The bbox is
first normalised to the RESULT CRS (`--horizontal-crs`, natively
EPSG:5514), so that the file name carries the coordinates of
the cutout actually requested. The request to the server goes natively; with
`--horizontal-crs` other than 5514 the content is reprojected by a local warp
with the pinned Czech operation. The server declares ceilings of 15000 x 4100 px,
but in practice rejects requests above approx. 8 Mpx. `CuzkClient.export_image`
uses `transport/chunks.py`: `align_bbox` without a source grid keeps the
NW anchor and `round` to a whole number of pixels, `plan_chunks` splits
the request with a budget of `MAX_EXPORT_PIXELS = 4_000_000` (square chunks
respecting the dimensional ceilings), `fetch_chunks` downloads them one by one
and stitches through `mosaic_and_crop` without resampling before the warp. CUZK
behaviour is unchanged: the pixel is exactly the variant step (0.5 m DMP OK,
2 m DMR 5G and DMP 1G, 5 m DMR 4G), E/S may deviate
by <= 0.5 px (the file name and `request.bbox` carry the bbox from before the snap).
A cutout entirely of nodata gives `Warning:` and code 0, not apparent silence.

The CZ bbox track is in the library (`download/cz_cutout.py`):
`download_cz_cutout(*, bbox, root, product, horizontal_crs,
vertical_crs, resolution, update, plan, parent_request, cache, on_notice,
on_download)` builds the provider (`create_cz_raster_provider(product,
resolution, ...)`; route `route()` with operations before the network), normalises the
bbox, determines the version slot (`bbox_slot`), downloads (`fetch_version`, signal
`none`), checks nodata and writes the version sidecar; `check_cz_cutout(...)`
with the same selection gives the plan. The execution step (`_run_cz_cutout`) is internal. The result grid starts from the requested bbox
converted to the result CRS, exactly as in the CLI before 0.7.1;
there is no alignment to the PL grid (a separate spec together with R6). The result
`CzCutoutResult(file, all_nodata, stale)`: a raster without a single
valid pixel is created, has `all_nodata=True`, `extra.all_nodata: true`
in the sidecar (with data `false` — the key is always present) and `Notice`
`ALL_NODATA` (CLI: `Warning:`). The check is best-effort: an unreadable file gives
`all_nodata=False` (debug log), never an abort after a successful download.
A local version (default mode and `upgrade`) returns `file.status ==
"local"` with the `all_nodata` flag from the version sidecar, without network; `force`
downloads again (the same content = `unchanged`). A failed download does not
leave a version or an empty tree and passes the exception on.

Result: hard link `data/<nmt|nmpt>/cz_<model>_<vcrs>/bbox/<coords>.tif`
(e.g. `nmt/cz_dmr5g_bpv`, `nmpt/cz_dmp1g_bpv`) to the version
in `versions/bbox/<YYYY-MM-DD>_<sha8>/`. CZ sheets (TM33, SM5) have
a public API since 0.8.0 `download/cz_sheets.py` (`download_cz_sheet`/
`check_cz_sheet(*, sheet, root, product, vertical_crs,
resolution=None, ...)` -> `CzSheetResult`; ADR-037): the same sidecar content
as previously in the CLI (`mapname`, `cz_share`, `capability`,
`horizontal_crs`); openzu files (SM5, since plan B also the TM33 tile
DMR 4G/DMP OK in EVRF2007) with the `http` signal (`extra.http`), the TM33 tile
from ImageServer `none`.

### 4.6 Dispatch per country (`--country auto`)

The split by country is in the library (`download/countries.py`;
called by `download_data`, ADR-037): `countries_for_bbox` compares the bbox
(in WGS84) with `CountryProfile.extent_wgs84`
of each country in the registry. The envelopes are **rectangles**, not boundary
polygons, so an area deep inside one country routinely also falls into the other.
Consequences: (1) an area crossing both rectangles is downloaded from EACH
country — separate files and sidecars, a shared `parent_request`; for NMT/NMPT
rasters this requires `--cutout` (a CZ raster area is always a cutout,
ADR-038), so the PL part is then a WCS cutout; without `--cutout`
a `ValidationError` with the hint `--country pl` (PL sheets). LAZ (plan B)
has no cutout: the PL part is GUGiK WFS tiles (section 4.7), the CZ part —
CUZK index sheets of the system determined by the CZ vertical CRS (Bpv: SM5,
EVRF2007: TM33); it requires `--model`, without it a `ValidationError` (`obszar
siega CZ: podaj --model ... albo --country pl`). An orthophoto (plan D) without
`--cutout` gives PL sheets (`--sheet-system` for the PL part) and CZ SM5 sheets
(previously `auto_narrowed_to_pl`), and collections - an area file per country
(section 4.10). A single-country product (intensity, true ortho, oblique ortho:
PL; contours: CZ) narrows `auto` to that country with `Info:`
`auto_narrowed_to_pl`/`auto_narrowed_to_cz` (like collections); an area only
in the other country = `ValidationError`; (2) in the
disputed area a flag without a Czech counterpart (`--vertical-crs KRON86`,
a resolution outside the CZ registry, e.g.
`--resolution 1m` or `0.5m` for NMT — NMPT `0.5m` is DMP OK, any
`--format`, and `--coverage` and `--resolution` of an orthophoto cutout; for LAZ
also `--year`, `--min-year`, `--max-year`, `--all-campaigns`
and `--min-density`; `download/area.py::pl_only_flags`
reads the registries) RESOLVES the country to `pl` with an `Info:` message instead of
failing the task; (3) a failure of one country
when the other succeeds gives code 0 and a `Warning:` (also in collections, section
4.10) — an explicit `--country` and a failure of all countries stay a failure (exit code 10 or 11).
`Info:`/`Warning:` go to stderr,
so `-q` does not suppress them. `--cutout` does NOT resolve the country in either direction,
because since ADR-027 it works on both sides of the border.

The part of the task for each country is CLIPPED under `auto` to its
rectangle (`country_bbox`; the full set of parts for `auto` is given by
`split_bbox_by_country(bbox, cz_crs=)` — the CZ part in `cz_crs`, the PL part
in the bbox CRS). `country_bbox` changes only the clipped PL edges —
the others carry the original coordinates; CZ is still converted
through WGS84. Before the download, `download_data` emits a `Notice`
(`AUTO_CLIPPED`, `AUTO_AREA_OUTSIDE`; CLI: `Info:`) about the clipping and
about the area left outside both rectangles (also a corner one).
The file name and `request.bbox` carry the clipped bbox, the original only
in `extra.parent_request`. The PL list mode (`--bbox` without `--cutout`, area
only without CZ) determines sheets from the clipped bbox, and their sidecars have
`request.sheet` (original: `extra.parent_request.bbox`). With a geometry
without `--cutout`
the PL sheets are determined by the geometry itself (whole), so there is no notice
about PL clipping or about an area outside the rectangles; the CZ part is still
clipped and reported. An explicit
`--country pl` does not clip; a bbox entirely outside the rectangles =
`ValidationError` (CLI `Error:`, code 2) without network access. Outside the CZ envelope, at the borders with
DE/SK/UA/BY/LT/RU, `auto` queries only PL; inside the CZ rectangle
CUZK is added even over Poland/Saxony, because the envelope is not
a boundary polygon. An entirely nodata result (CZ or a PL cutout
with downloaded sheets) gives a `Warning:` and code 0. A partial success of
PL or CZ under `auto` gives `DataReport.ok = True` (code 0), the failure of the other
part in `failed` and a `Notice` `AUTO_PARTIAL_SUCCESS`; `--resolution 1m`
resolves to PL. The vertical CRS and resolution are required (0.8.0, no
defaults); one value applies to every country of the task and must be available for
it, different values: `pl=..,cz=..` (library: dictionary
`{"pl": ..., "cz": ...}`); each country is validated before the first
download. The CZ LAZ model is chosen by `--model` (`model=`, plan B); `--model`
with a raster or with a PL-only task (explicit `--country pl`, PL sheet code,
area only in PL or narrowed to PL) = `ValidationError`.

Campaign options and year flags (ADR-030/032; errata Q9, N-3) apply
only to PL sheets and PL LAZ tiles; `download_data` checks all inputs: a task without PL (CZ sheet code under `cz`/`auto`, explicit
`--country cz`, an area entirely in CZ under `auto`) with `--all-campaigns` or any
year flag = `ValidationError` (`CZ (CUZK) nie ma kampanii -
--all-campaigns/--min-year/--max-year/--year dotycza tylko PL`; CZ orthophoto:
`--year dotyczy tylko PL - CUZK publikuje tylko aktualny rocznik
arkusza ortofoto CZ ...`), code 2 without network access (CZ LAZ with `--min-density`:
`--min-density dotyczy tylko LAZ PL`). An NMT/NMPT raster area PL+CZ under
`auto` requires `--cutout`, and the cutout rejects these
flags (4.3) - PL sheets with campaigns are given only by `--country pl` (since
ADR-038; the `Notice` `campaign_opts_pl_only` removed). An orthophoto under
`auto` applies year and campaign flags to PL sheets, and the CZ part takes
the current vintage of SM5 sheets. For rasters the year flags do not
belong to `pl_only_flags` and do not narrow `auto` to PL; for LAZ (plan B)
`--year`/`--min-year`/`--max-year`, `--all-campaigns` and `--min-density`
narrow a PL+CZ area to PL (`Info:`, `AUTO_NARROWED_TO_PL`).

The PL/CZ junction measured live on 2026-09-29 (input data for R6; report:
`docs/research/2026-09-29-live-e2e-i-audyt-docs/L4-pogranicze-cz-report.md`; both cutouts
in EPSG:2180): GUGiK delivers data ~200 m deep into CZ, CUZK ~118 m deep into PL, a
shared strip of ~310-350 m (Cieszyn, Karkonosze, Beskid Slaski, the PL-CZ-DE tripoint),
with no gap where GUGiK has the product at the given resolution (Karkonosze
5 m: no GUGiK sheets — a 5.2 km² hole on the PL side). Height differences
PL - CZ (both "EVRF2007": PL `EPSG:9651`, CZ `EPSG:5621`) in the shared strip:
medians -0.19..+0.14 m depending on the dataset and slope (tripoint: 0.17 m),
the Olza riverbed ~ -0.55 m (water surface); the PL grids (5 m: 5k + 2.5; 1 m: k + 0.5)
and CZ (warp anchored in the NW corner of the task) are not shared.

### 4.7 LAZ (LIDAR point clouds, PL and CZ)

A flow outside `DownloadManager` — one area task gives many tiles.
The logic is in the library (`download/laz.py`, ADR-029; modelled on `cutout.py`):
`download_laz_area(bbox=..., ...)` accepts a bbox in any supported
CRS (conversion to EPSG:2180 in the library, `area.bbox_to_2180`)
or `sheet=` (sheet code PL-1992/PL-2000: WFS is asked for the frame envelope, tiles
selected for the frame `sheet_frame_2180`, `select_tiles(frame=)`),
`check_laz_area(...)` gives the plan. `--geometry` is reduced to a bbox by
`download_data`; the CLI only prints the result.
Discovery goes through
**WFS** `GetFeature` (the LAZ index WMS returns 401 — ADR-021) on the shared
`WfsIndex` transport (`providers/pl/skorowidz_wfs.py`, since 0.8.0 — the same
client as the NMT/NMPT sheet index and the availability report: paging by
`next`, `numberReturned` check, error = `DownloadError` "wynik bylby
niepelny", section 4.1); the services and type prefix (`DanePomiaroweLidar
{EVRF2007,KRON86}`, `SkorowidzDanychPomiarowychLIDAR`) come from the variant
registry (`variants(product="laz")` -> `IndexRef`;
`GugikLazProvider.WFS_ENDPOINTS` removed in 0.8.0), and the tiles are
downloaded in parallel. WFS `urn:ogc:def:crs:EPSG::2180` expects
the (N,E) axis order: the bbox is sent, and `gml:Envelope` and the `msGeometry` frame
are read in that order, then the tiles are filtered by the actual intersection.
GetCapabilities (`WfsIndex.feature_types`) determines the vintages (no hard-coded list); an explicit `--year`
absent from the vertical-CRS service = `DownloadError` with a list of
available vintages, before GetFeature;
a range with no service vintage also gives `DownloadError`. With a year
flag, WFS queries ALL vintages for the reference, before the download.
If any vintage fails after retries, `select_tiles`
raises `DownloadError` instead of guessing the absence of tiles. When all
respond and there are no tiles at all, `download_laz_area` raises
`NoCoverageError` (`Brak kafli LAZ dla podanego obszaru ...`).

**Shared year flags, `--min-density` LAZ only (ADR-032).**
`--year`/`--min-year`/`--max-year` for NMT/NMPT/orthophoto go to
`DownloadManager` (4.1), for LAZ to `download_laz_area`;
`--min-density` for other products = `Error:` before the network
(`download/options.py::validate_request`). `--year` with any year bound =
`Error: --year wyklucza sie z --min-year/--max-year` before the network,
also in LAZ. A CZ-only task with year flags = `Error: CZ (CUZK)
nie ma kampanii` (4.6). A `--cutout` cutout with a year flag = `Error:`
(4.3).

**Tile selection (ADR-029/032).** By default (without year bounds) tiles are selected
greedily from the newest `akt_rok` (within a year: the newer `akt_data`): an
older tile is skipped when its intersection with the task area is already covered
by the union of selected tiles — comparison of `msGeometry` frames in EPSG:2180,
each covering frame enlarged by 1 m (`COVERAGE_TOLERANCE_M`); a tile
contributing an uncovered piece is kept (whole — LAZ is not clipped).
Thanks to this PL-1992 and PL-2000 of the same place do not duplicate (in w2:
2025/PL-1992 instead of 2025 + 2022/PL-2000:S7). Within a year range this
rule operates on the selected tiles (explicit `newest` allowed).
Only a full tile covers (`czy_ark_wypelniony` !=
`NIE`) and only by frame or by the same sheet code, never by envelope. A tile whose
frame does not intersect the area (only the envelope does) is skipped.
A tile must reach into the area deeper than `tolerance_m` (1 m; the
index rule `overlaps_area`: the tile frame narrowed by the tolerance intersects the
area): a neighbouring sheet touching the sheet code frame with an edge or
a corner (GUGiK frames rounded to 1 cm) is `outside`; an area
narrower than 2 tolerances takes every intersecting tile.
Skipped tiles: `LazTileSelection.superseded` / `LazDownloadResult.superseded`
(tile + covering tiles; `outside` with an empty list), in the CLI `Info:` on
stderr also with `-q` - only tiles covered by newer ones (`outside` do not
belong to the area and are not printed).

With a year flag `select_tiles` checks the coverage of reference tiles,
selected across ALL years without bounds, by tiles from the range
(after the density and vertical filter). It compares frames, not sheet codes: PL-1992
and PL-2000 may divide the same area differently. An uncovered part of
a reference tile = `YearRangeError` before the download with the sheet code of the
reference, its year/system and the years of tiles intersecting the
uncovered fragment; tolerance 1 m as in normal selection.
In the w2 area `--year 2022` is covered by the references together by two PL-2000
tiles (neither alone), and `--year 2023` by the same sheet code. In Wroclaw
(`6.150.13.16.4`) `--year 2025` is a conflict: year 2025 has only
`NIE` deliveries there, which do not cover the 2024 reference (PL-1992); a year
in which the uncovered fragment is intersected only by `NIE` deliveries has in
the message a note `(tylko arkusze niepelne)`. A fragment
without tiles in ANY year remains without a warning.

A download failure of even one tile goes to `LazDownloadResult.failed`
(the library does not raise); the CLI then exits with code 10 or 11 with `Error:`
and the FULL list of failed tiles (like `_finish_pl_sheets`; successful tiles
stay on disk and are skipped on retry without `--force`).
The tile sheet code is finer than 1:10000 and is NOT
parsed — `FileStorage.get_raw_path(..., system=tile.system)` builds the directory
hierarchy from it itself. The horizontal system is determined **per tile**
by the `LazTile.system` property (a single source of truth for the CLI and library, note 8
of the max review) from the tile's `uklad_xy`, by the parser `sources.registry.parse_pl_system`
shared with the sheet index and sidecar (`horizontal_crs_for_system`; review-1 D3):
`PL-1992` -> `1992`, `PL-2000:S5..S8` -> `2000`. An unrecognised value (e.g.
`PL-2000` without a zone) — the tile is skipped in discovery with a warning in the log,
and `LazTile.system` of a manually built tile raises `ValidationError` (formerly
guessing from the sheet code format gave a `pl_2000` segment with an EPSG:2180 sidecar).
The vertical CRS comes from the CLI flag (library:
`FileStorage(vertical_crs=)`). One task can therefore write tiles to two
segments at once — `{system}` is resolved per `get_raw_path` call,
one `FileStorage` suffices for the whole PL task. For `--country auto`
the PL part uses this track, the CZ part `download/cz_laz.py`;
both parts share `extra.parent_request` (section 4.6).

**LAZ campaigns (ADR-030/032).** By default
(also with an upper bound) the greedy selection of ADR-029 within the range.
`--all-campaigns` = all tiles with a frame intersecting the area
(`select_all_intersecting`), without coverage deduplication; a tile
intersected only by the WFS envelope goes to `superseded` with the reason
"outside". `--year Y` = range `[Y, Y]`, `--min-year`/`--max-year`
are closed bounds of `akt_rok`; `--year` with any of them =
an error in the CLI (`ValidationError` in the library). `download_laz_area`
and `select_tiles` accept `year=`, `min_year=`, `max_year=`.
LAZ has no `kampanie/`; a tile is a version in `versions/`, and the standard
path is a hard link (ADR-036); `request.campaigns` in the sidecar only for `all`.

Result: `data/laz/pl_2000_evrf2007/6/162/34/02/3/<original_name>.laz`
(+ `.meta.json` with `extra.tile_sheet`/`year`/`nominal_density`/`url`,
`extra.acquisition_date`/`full_sheet`, when known, and
`extra.parent_request` in `--bbox`/`--geometry` mode; `request`
carries the bbox of the task AREA (an EPSG:2180 window - not of the tile: the outline and `unit`
of the tile are read from the LAS header and from `extra.tile_sheet`, section 3.3.1),
the given year bounds, `year` for a single year
and `min_density`, when given — E16).
`nominal_density` and the `--min-density` filter are the NOMINAL value from the GUGiK WFS
(`char_przestrz`); the actual density of a tile is sometimes several times higher
(E2E 2026-10-06: ~119 pts/m2 at a nominal 15).

**LAZ CZ (plan B, `download/cz_laz.py`).** `download_cz_laz(*, model,
vertical_crs, root, sheet=None, bbox=None, update=None, plan=None,
parent_request=None, workers=4, cache=True, on_notice=None,
on_progress=None) -> CzLazResult(sheets, files, failed, stale, notices)`
(`ok` = no `failed`) and `check_cz_laz(*, model, vertical_crs, root,
sheet=None, bbox=None, cache=True, on_notice=None) -> UpdatePlan` are the command-level
path; `download_data` calls it for a CZ sheet code and for the CZ part of an area.
One call = one model (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`, the variant
registry) and the vertical CRS, which determines the files: CUZK publishes LAZ
only in the pairs S-JTSK/Bpv (SM5 sheets, EPSG:5514) and ETRS89/EVRF2007
(TM33 tiles, EPSG:3045), and Kartograf does not transform point clouds. A wrong
pair (e.g. an SM5 sheet code with EVRF2007), a missing or unknown model, `--cutout`,
`--resolution` and `--min-density` = `ValidationError` before the network.
`CuzkLazProvider(model, session=None, cache=None, *, vertical_crs)`:
`sheets(area)` converts the area (any supported CRS) with the pinned
operation to the CRS of the system and takes `SheetIndex.file_sheets(system, area)`
— SM5 sheets with `PODIL > 0` (layer 24) or TM33 tiles (layer 26;
`IN_CZ` has a single value `CZ` in the index, so it does not distinguish border
tiles) — the same rule as the CZ report (4.9); an area without sheets =
`NoCoverageError`. An SM5 sheet code is checked in the index
(`SheetIndex.sm5_sheet`, `sheet_cache`), a TM33 tile by the grid parser.
`download(sheet, output_path, ...)` writes the `.laz` member of the openzu ZIP
byte for byte (`CuzkClient.fetch_file(..., unzip_single=".laz")`); 404 =
`DownloadError` for the sheet with an index hint. Files go in parallel
(`workers`); a file failure goes to `failed` (`CzLazFailure(sheet,
error)`), the others remain (CLI: `Error:` per sheet, exit code 10 or 11). Store:
`laz/cz_<model>_<vcrs>/<sheet code hierarchy>/<sheet_code>.laz` (`CTES/96`,
`760/5518`), versions like an SM5 sheet (label = download date, signal
`http`: `HEAD` of the ZIP with a local version with `--upgrade` via `file_signal`), plan
path `cz_laz` (`unit` = sheet code). Sidecar: `dataset` `cz.cuzk.<model>_laz`,
`request.sheet`, horizontal CRS of the file (EPSG:5514/3045), native vertical
(EPSG:8357/5621), `capability` `sheet_files`, `extra.http`, SM5
`extra.mapname`/`cz_share`, area `extra.parent_request`.

### 4.8 Land cover and soils (BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250, SoilGrids)

**Version store (ADR-036 D29-D33, ADR-044 D5-D6).** The public functions
`download_landcover(product=..., root=..., ...)` and
`download_soil(root=..., ...)` write exclusively to the store
`root` (= `--root`; without `output_path`, D32), in the segments of rule 8
of section 3.3. They return `LandCoverReport`/`SoilReport` with `UnitFile` in `files`,
unit failures in `failed`, `stale`, `notices` and `ok`; with `keep_raw`
the original BDOT10k archives are in `LandCoverReport.raw`. Internally they use
`LandCoverManager`. Errors in selections and options are `ValidationError` before the
network; failures of individual files are `failed` entries (`ok=False`).
The file policy is shared with the other paths (`download/fetch.py`):
`use_local` (a decision without
downloading data), download to `versions/.incoming/`, `store_file`
(sha256 in one read, `commit_version`, version sidecar, hard link).
Signal per channel (`AccessChannel.update_signal`):

| Source / channel | Signal | Version label | Segment |
|---|---|---|---|
| SoilGrids WCS | `metadata`: `SoilGridsProvider.edition(property)` — the first `ows:Title` of the GetCapabilities of the property map (`SoilGrids250m 2.0 - ...` -> `2.0`); the `ocd` map does not give the edition in its title (state 2026-10-19), so its edition is the edition of the `clay` map (`extra.edition.url`/`title` point to it, and `extra.edition.source_property` = `clay` states this in machine-readable form) | edition | `soil/global_soilgrids_<wl>_<gl>_<stat>` |
| CORINE CLMS (`uses_clms(year)`: token and year in `CLMS_YEARS`) | `metadata`: `CorineProvider.edition(year)` — `characteristics_release_major_version` from `@search?UID=<uid>&fullobjects=1` (without a token) | edition (`V2020_20u1`) | `landcover/eu_corine_<year>` |
| CORINE WMS preview (without credentials; 1990 always) | `none` | download date | `landcover/eu_corine_<year>_preview` (`.png`) |
| BDOT10k county package | `none` | download date | `landcover/pl_bdot10k_gpkg[_<layers>]`, `_shp`, `_gpkg_zip` |
| BDOT10k vintage archive (`year`, channel `archive_unit_files`) | `none` | vintage (`label_source="edition"`) | `landcover/pl_bdot10k_<gml\|shp>_<year>` |
| ZABAGED of an area (`bbox`/`geometry`, REST, plan D) | `none` | download date | `landcover/cz_zabaged` (`bbox/<coords>.gpkg`, EPSG:5514) |
| ZABAGED national file (`whole_country`, ATOM feed) | `metadata`: the `updated` date of the file entry in the dataset feed | edition (`2026-10-04`) | `landcover/cz_zabaged_gpkg_<5514\|3045>` (`country/cz.zip`) |
| BDOO voivodeship package (`year` required, plan E4) | `none` | vintage (`label_source="edition"`) | `landcover/pl_bdoo_<year>[_<classes>]` (`teryt/<woj>.zip`) |
| Data50, Data250 of an area (REST, plan E4) | `none` | download date | `landcover/cz_data50`, `landcover/cz_data250` (`bbox/<coords>.gpkg`, EPSG:5514) |
| Data50, Data250 national file (`whole_country`, ATOM feed) | `metadata`: the `updated` date of the file entry | edition (Data50 `2026-04-28`, Data250 `2026-05-12`) | `landcover/cz_data50_shp_<5514\|3045>`, `cz_data250_shp_...` (`country/cz.zip`) |

`metadata` (decision table 2 of plan 3/3): the edition is queried once per file
(`memoized_edition`) BEFORE the download — without an edition no version is created
(a file error, D30). A local version with an edition label: equal = local,
different = by default `newer=<edition>` (CLI: `dostepna nowsza ... (--upgrade)`),
`upgrade` downloads; edition unavailable = by default `unverified="check_failed:
..."` (CLI `Warning:`), `upgrade`/`force` = error. A version not from an edition is
not comparable (`unverified="none"`). The same content under a new edition
= `relabeled` (D23). `none`: the local version is not checked; HTTP headers
go to `extra.http`, but are not a signal (the same content on another day =
`unchanged`). `check_landcover(...)`/`check_soil(...)` build a plan
`kartograf-plan/1` (path `landcover`, `unit` = TERYT / bbox coordinates /
sheet code) without downloading data (allowed: GetCapabilities, the CLMS catalogue,
PRG); `download_landcover(..., update="upgrade", plan=)` or
`download_soil(..., update="upgrade", plan=)` executes only the entries of the
plan, those changed since the plan return in `stale`.

Content parameters (`_content_params`, U3) carry the segment and the `request`
of the sidecar (`property`/`depth`/`stat`, `year`, `format`, `layers`) next to the
selection (`teryt` / `bbox`+`bbox_crs` / canonical `sheet`); the GeoTIFF `nodata`
is read from the file (`null` when the tag is missing). The SoilGrids/CORINE CLMS version sidecar
has `extra.edition` (`id`, `url`, `title` / `dataset_uid`). The CORINE
preview: `horizontal_crs` of the WMS service (EPSG:3857, 1990 EPSG:4326),
`extra.fallback = "wms_png"`, `extra.note = "podglad WMS, nie dane"`. The raster
layer of the EEA service for the given year (`Corine Land Cover <year> raster`; the name is `12`
only in CLC2018, in other years `Corine_Land_Cover_<year>_raster<number>`)
is read by `CorineProvider._eea_raster_layer` from GetCapabilities once per provider;
a preview image that is entirely transparent (alpha 0: no CLC data for the year for the area)
is `NoCoverageError` AFTER the download and BEFORE the version is written (`kind: no_coverage`, like
true orthophoto). The SoilGrids sidecar has `extra.units` = `{mapped, conventional,
divisor}` (ISRIC units: value in the file / `divisor` = conventional unit;
`uncertainty` is the quotient `10 x (Q0.95 - Q0.05) / Q0.5`),
and a raster of only zeros (apart from `cfvo`) `extra.all_nodata` and a `Warning`
`all_nodata`; `ocs` exists only for `0-30cm` (`SoilGridsProvider.check_layer`),
a window smaller than a pixel is extended to one pixel (250 m).

**ZABAGED (CZ, ADR-042 D15, plan D).** `LandCoverManager(root,
"zabaged")` has no provider class (`COLLECTION_SOURCES`): the options are checked by
`_collection_request`, and the selection and download are done by the functions
of `download/collections.py` (`landcover_request`, `run_request`,
`plan_request`; the same unit tasks as the collections, section 4.10) on the
plan path `landcover`. An area (`bbox` in any supported CRS
or `geometry`; the only country is CZ, without `--country`) gives one GPKG
in EPSG:5514 with 22 land cover and hydrography layers (ASCII layer codes and names
from `registry.py::_ZABAGED_LAYERS`, the layer description = the service name
with id, e.g. `Vodní tok (93)`), full geometries of the objects
intersecting the area; classes are NOT converted to BDOT10k codes.
`whole_country=True` with `horizontal_crs` `EPSG:5514` or `EPSG:3045`
(required - the file is published in two CRSs) = the national ZIP from the ATOM
feed 1:1 (5.8/6.7 GB, member `ZABAGED_RESULTS.gpkg` with the layers of the full database
under CUZK names, e.g. `VodniPlocha_c`), the size from the feed in the `Notice`
`whole_country_size` before the transfer. `teryt`, `format`, `layers`,
`keep_raw`, `year` = `ValidationError` with the source name, `sheet` = error,
`horizontal_crs` with an area = error (the result is always EPSG:5514). One file
per request: a download error goes to `LandCoverReport.failed` (`ok=False`).
The internal `get_available_layers()` returns the 22 layer names of the area result,
`get_supported_formats()` - `["GPKG"]`.

**BDOO (PL, plan E4, ADR-043).** `LandCoverManager(root, "bdoo")`
follows the same path as ZABAGED (`COLLECTION_SOURCES`, `landcover_request`
with `teryt`, `year` and `layers`). GUGiK publishes BDOO only as a GML package
of a voivodeship per vintage (`opendata/bdoo/<R>/PL.PZGiK.201.<woj>.zip`; 2015,
2021-2026; no national file), so `year` is required (missing or a
vintage outside the registry = `ValidationError` with a list), `teryt` is the code of the
voivodeship (a county code = error with the hint `--teryt <woj>`), and an area
(`bbox`/`sheet`/`geometry`) gives the packages of the voivodeships of its counties from PRG
(the general orchestrator rule for a product without county packages, `Info`
`unit_list`; a voivodeship without a package goes to `failed`, `workers`
in parallel). The package is written 1:1 (`teryt/<woj>.zip`, label =
vintage). `layers` (class codes of the vintage, `PackageVariant.classes`; a class
outside the vintage = `ValidationError` with the list of classes of that vintage) writes
a ZIP of the files `__OT_<CODE>_<type>` of the selected classes (`class_pattern`) in a separate
segment `pl_bdoo_<year>_<classes>`: members byte for byte, with the name, date
and compression of the source, in the order of the source - the same package gives the same
bytes (`unchanged`); composite objects (`__OT_Ciek` etc.), XSD and metadata
remain only in the full package. Up to 2023 the package has no file for a class
without objects in the voivodeship (classes of the vintage = the sum over 16 packages): a lack of
some of the selected classes = `Info` `classes_absent`, a lack of all =
`NoCoverageError` of the voivodeship; `extra.source.classes` = the classes written.
`get_available_layers()` returns the classes of all vintages,
`get_supported_formats()` - `["ZIP"]`.

**Data50 and Data250 (CZ, plan E4).** Like ZABAGED: an area = one GPKG
of all feature layers of the service `DATA50/MapServer` (69) or
`DATA250/MapServer` (116; relief rasters 5 and 6 are not data) in EPSG:5514,
ASCII layer names from the CUZK names, without conversion to BDOT10k classes;
`whole_country=True` with `horizontal_crs` (`EPSG:5514` or `EPSG:3045`) =
the national SHP ZIP from the ATOM feed 1:1 (Data50 516/757 MB, Data250 230/320 MB;
the layers of the file under their own names, different from the area layers, e.g.
`shp/Akvadukt.shp`, `AirfldA.shp`), the edition from `updated` of the feed.

**BDOT10k from multiple counties (since 0.7.1, A2).** A BDOT10k package is always
a package of a WHOLE county, so the path and the `request` of the sidecar describe
the content: `landcover/pl_bdot10k_<format>[_<layers>]/teryt/<TERYT>.<ext>`,
`request = {teryt, format[, layers]}` — also when requested via
`--bbox`/`--sheet`/`--geometry`.
The task area goes to `extra.parent_request`: `{bbox, bbox_crs,
countries: ["PL"]}` or `{sheet, countries: ["PL"]}`.
`download_landcover(product="bdot10k", root=..., teryt=|sheet=|bbox=|
geometry=, layer=, update=, plan=, workers=, on_notice=, format=, layers=,
keep_raw=)` for an area queries PRG (`Bdot10kProvider.teryts_for_area` ->
`discover_teryts_for_bbox`, an area in any supported CRS) and
downloads the package of EVERY county intersecting the area, in code order.
`LandCoverReport.files` contains the successful files, `raw` the separate ZIP archives, and
`failed` the county failures (`UnitFailure`); the rest is downloaded
(spec 4.2); a PRG discovery failure is a task error, the PRG limit is
30 s. `workers` downloads counties in parallel. The CLI `landcover download`
(ADR-039) is a single call of `download_landcover` (flags `--layers`,
`--keep-raw`, `--bbox-crs`, `--workers`, `--quiet`), prints file statuses,
`Error: <TERYT>: ...` for failures and exits with code 10 or 11 for
`ok=False`. The low-level `Bdot10kProvider.download_by_bbox`/
`download_by_sheet` (file outside the store) download ONE county
(`_single_teryt`): an area of several counties is a `ValidationError` with a list of
codes and a hint to `download_landcover`. The provider applies its own download
and PRG query timeout, not the explicit `timeout` of the command. An area prints
`Info` `unit_list` (counties from PRG) and is subject to the collection limit
(`download.collections.within_volume`: > 100 packages to download or > 10 GB
according to `HEAD` = `ValidationError` before the first transfer; also the archive
`year`). `layers=` (class codes from `BDOT10K_CLASSES`: 58 classes of the 2021 regulation;
GPKG only) leaves in the merged GPKG only the `__OT_<code>_*` files of the package;
an unknown code and an empty code are `ValidationError` before the network, a class without a file
in the county package (no objects of it) is `Info` `classes_absent` (like BDOO;
`Bdot10kPackage.classes`/`absent`, `extra.source.classes`), and a lack of all
selected classes is `NoCoverageError` of the county; a file with a filter
carries the layers token in the segment, because it is no longer a full package. Merging
the package (`_merge_gpkg_files`) ends with `DownloadError` when a table name
repeats in two files of the package (until now the second copy was
silently skipped); in a real package (one table per class and geometry
type, `..._<TERYT>__OT_<CODE>_<A|L|P>.gpkg`) there are no duplicates.

BDOT10k GPKG: the ZIP archive from GUGiK is unpacked, and the layers are merged
into a single GeoPackage in a LOCAL temporary directory (`tempfile`); the finished file
goes into the store's `versions/.incoming/` (copy as `<name>.gpkg.<pid>_<tid>.tmp` + `os.replace`).
Reason: SQLite on CIFS/SMB shares without byte-range locks ended the
merge with the error `database is locked` (`Bdot10kProvider._merge_gpkg_files`).

**Provenance of the BDOT10k package in the sidecar (A4, decision 9 of plan 3/3).**
The sidecar of a BDOT10k file version has `extra.source = {url, teryt, format}` (the URL
of the OpenData package) and `extra.http = {etag, last_modified, content_length}` —
the GUGiK response headers as they arrived (the server does not provide `ETag` or
`Last-Modified`, only `Content-Length`; channel `none`). `keep_raw=True`
(GPKG only — with SHP `ValidationError`) saves the untouched GUGiK archive
as its OWN version in `landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip`
(full package: one file for each `layers=` filter, `request` without
`layers`); the package is downloaded when ANY of the files (GPKG, ZIP)
requires a download, both files go through `store_file` (the same content =
`unchanged`): first the ZIP, then the GPKG with `extra.source_files = [{name:
"package", file: <path of the ZIP version relative to --root>, sha256}]`.
The package files are created in the `.incoming/` of their own segments; an error in downloading,
unpacking or saving the archive leaves no version or working directory,
previous versions and links remain. `extra.parent_request`
(the task area) alongside `source` and `http`. Repeatability: a GPKG merged
from the same package has the same sha256 (live 2026-10-12: `--force` = `bez
zmian`).

**Archive of BDOT10k annual editions (ADR-042 D10-D11, since 0.8.0).**
`download_landcover(product="bdot10k", root=..., year=R,
format="GML"|"SHP", teryt=|sheet=|bbox=|geometry=)`
(CLI `landcover download --product bdot10k --year R --format GML|SHP`)
downloads the annual editions 2014-2025 (state as of the beginning of the year) from the channel
`archive_unit_files` of the descriptor `pl.gugik.bdot10k`: the county ZIP package
saved 1:1, without GPKG merging, in
`landcover/pl_bdot10k_<gml|shp>_<year>/teryt/<T>.zip`, label = year,
`request = {teryt, format, year}`, signal `none`. Validation without the network
in `_check_options` (the same place for `download`, `check`
and `validate_request`): the variant via `transport.unit_package.select_variant`
(no `format` or `GPKG` = `ValidationError` with the list `GML, SHP`, a year
outside the list = the list of years), `layers`/`keep_raw` with `year` = error, and `GML`
without `year` = error with a hint. The download runs as unit tasks of the
collection orchestrator (`package_job`/`run_job`/`inspect_job`, section
4.10) with an HTTP session and the BDOT10k provider limit
(`Bdot10kProvider.session()`), on the `landcover` plan track. Area =
counties from PRG as for the current packages (`extra.parent_request`, a county
error in `failed`); a `teryt` without a package in the annual edition (HTTP 404, e.g. after
a TERYT code change) = `NoCoverageError`. Identical annual editions of the same
county and format take up space once (D7: `relabeled`, hardlink; live
2026-10-15: SHP 2023 of county 1261 = 2022).

`calculate_hsg(root=..., sheet=|bbox=|geometry=, layer=, depth=,
update=, plan=, on_notice=)` and `check_hsg(...)` (`hydrology/hsg.py`,
ADR-044 D5; the statistic is always `mean`) compute soil groups from the
SoilGrids versions `clay`/`sand`/`silt` in the same store (internal
`HSGCalculator`; input errors are `ValidationError`, failures of individual
files go to `HsgReport.failed` and no HSG is produced) according to the canonical
USDA triangle (ADR-025). Result `HsgReport(files, inputs, failed, stale,
notices, ok)` in `hsg/global_soilgrids_<gl>_mean/` (`bbox/<coords>` or
the sheet code hierarchy). The HSG raster is in `files[0].file`, the downloaded clay/sand/silt versions
in `inputs`. An HSG version whose `extra.source_files` has the same
three input sha256 values (order clay, sand, silt) is reused
(`reused`, no computation, linked to it); otherwise classification into `.incoming/`
and `store_file` with label = sorted unique input labels joined with `+`
(`label_source = "edition"`). `--force` applies to the inputs. Version sidecar:
descriptor `global.isric.soilgrids`, `product: "hsg"` (`build_metadata(
product=)`; the inputs have `soil`), `capability="bbox_raster"`, `request`
= the selection (`bbox`+`bbox_crs` or `sheet`), `horizontal_crs` = the raster CRS,
`nodata: 0`, `extra` = `{derived: "hsg", depth, stat, classes, source_layers,
source_files: [{name, file (path of the input version), sha256, label}]}`.
`hsg_statistics(path)` (`soil hsg --summary`) computes the `request` area of the
sidecar (bbox or sheet frame; without it the whole raster): the outline of the area
converted to the raster CRS is rasterised on a grid 10 x denser, so a
SoilGrids cell at the edge counts by its share in the area (cell areas
geodesic for EPSG:4326); groups `A`-`D` and `nodata` sum to the
area, `percent` of the groups = share of the area with data, `nodata.percent` =
share of the area; group descriptions in Polish (`HSG_DESCRIPTIONS`).
`check_hsg(...)` = 3 `landcover` entries + an `hsg` entry
(`current` when an HSG version exists with the sha256 of the current local inputs and each
input is `current`; an input `check_failed` = `check_failed`; otherwise
`missing`; never `newer`). Limitation: an HSG with identical content from other
inputs is an existing version with the first inputs in `source_files` — such
inputs compute the HSG on every run (versions are immutable).

`hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`
(since 0.7.1, A8) computes HSG from ready rasters (g/kg, SoilGrids) without downloading
and without default values: each input is reprojected with a pinned
operation (`CONTENT_POLICY`, bilinear; `warp_to_grid`) onto the `crs`/`pixel_m` grid
anchored in `bbox` (converted to `crs`), and the classification (`_classify_hsg`)
and GeoTIFF writing (`_write_hsg_geotiff`) are shared with
`calculate_hsg`. The input nodata comes solely from
its tag (no tag = no nodata value, without a default `-32768`); pixels
outside the input extent and zero triples give `0`. Sidecar as above
(`extra.source_layers` = `["clay", "sand", "silt"]`, the same type), plus
`extra.source_files` = a list of `{name, file, sha256}` (digest of the input file,
`file_digest`), without `depth`/`stat` (they are not known), and `request` carries
the grid (`bbox` in `crs`).

**TERYT discovery (since 0.7.1).** `providers/pl/prg.py` is the only place
that asks which counties an area or a point lies in:
`discover_teryts_for_bbox(bbox, *, session, cache, timeout)` returns
sorted, unique 4-digit county codes, and `teryt_for_point(x, y,
crs, ...)` the county code of a point (`None` = no county: sea, abroad;
a point on the border of two counties = the lower code). Source: WFS PRG GUGiK
(WFS 2.0.0, MapServer), layer `ms:A02_Granice_powiatow`, attribute
`JPT_KOD_JE`. An area in any supported CRS is converted to
EPSG:2180 by the same rule as the PL cutout (`download.cutout.bbox_to_2180`),
and `BBOX` goes in axis order (N,E) with `urn:ogc:def:crs:EPSG::2180`,
expanded outwards to whole millimetres (since 0.7.2).
The filter works on the county GEOMETRY, not on its envelope (verified
live 2026-10-08; raw responses: `tests/fixtures/gugik_prg/`). An empty
list only from a valid response without objects; an HTTP error (after the shared
retry policy `get_with_retry`), `ows:ExceptionReport`, a non-XML response,
a code outside 4 digits and a list truncated by paging = `DownloadError`.
Truncation: `numberReturned < numberMatched`, or a non-numeric `numberMatched`
(MapServer: `unknown`) with a full page, or the collection attribute `next`
— this is what a real MapServer page looks like (`unknown` + `next`).
A response in which a numeric `numberReturned` differs from the number of
codes read (an object without `JPT_KOD_JE`) is also a `DownloadError` (since 0.7.2).
Responses go to `MetadataCache`: area (EPSG:2180) -> list of codes
in `teryt_bbox_cache` (TTL like the other tables, also an empty list), point
-> code in `teryt_cache`; `kartograf cache stats` counts both in `Wpisy TERYT`.

### 4.9 Availability report (`elevation availability`, ADR-041)

`check_availability(*, product, country=None, sheet=None, bbox=None,
geometry=None, layer=None, year=None, min_year=None, max_year=None,
cache=True, force=False, on_notice=None) -> AvailabilityReport`
(`download/availability.py`) answers for which years, sheet systems,
resolutions, vertical CRSs and formats an area has a complete set of FULL
NMT/NMPT sheets (LAZ: tiles) according to the GUGiK sheet index — without downloading
data; since plan B also CZ: which SM5 sheets and TM33 tiles of the area
(index `KladyMapovychListu`) have CUZK files, with the publication date
and size from `HEAD` (CUZK does not publish survey years), and `auto` (PL and CZ parts
in one report). The CLI `kartograf elevation availability`
(`cli/availability_cmd.py`) only translates flags (`--bbox` -> `BBox`,
`--force`) and prints the result: a PL table (combinations from the newest year)
and a CZ table (columns `MODEL`, `UKLAD`, `ROZDZ.`, `WYSOKOSCI`, `FORMAT`,
`ARKUSZE SA/BRAK`, `PUBLIKACJA`, `ROZMIAR`, `KOMPLET`; above it the line
`CUZK nie publikuje lat nalotu; daty = publikacja pliku`), `--details`
(sheet codes of incomplete sheets — CZ: without a file —, land without sheets, commands
for each combination), a footer with the newest complete PL combination and
with the complete CZ combinations (at most `MAX_HINT_LINES`
= 5 commands per combination and the count of the remaining ones), `--json` = exactly
`AvailabilityReport.to_json()` (messages only in the `notices` field, without
duplication on stderr). `ok=False` (a part of `auto` not checked)
= the report is printed and the exit code is 10 or 11. The report is not a project data command
(`project_task` of the catalog = `false`; `project add` rejects it). Live examples and printouts:
USAGE 1.7.

**Validation before the network** (texts as in `download_data`): a single choice of
area; `product` from `AVAILABILITY_PRODUCTS` (`nmt`, `nmpt`, `laz`);
`sheet` = a PL sheet code (PL-1992/PL-2000) or CZ (SM5, TM33; country from the sheet code;
a TM33 tile is checked by `ParserTM33`); `bbox`/`geometry`
require `country`; `country` from `AVAILABILITY_COUNTRIES` (`pl`, `cz`,
`auto`; the same report shape); year bounds
as in downloading (`year` = `min_year` = `max_year`) and only for PL: with `cz`
or a CZ sheet code = `ValidationError` (`CZ (CUZK) nie publikuje lat nalotu
...`), with `auto` an area in both rectangles narrows to PL (`Info:`,
`AUTO_NARROWED_TO_PL`), and an area only in CZ = `ValidationError`.

**PL algorithm:**

1. **Area** -> convex polygons (E, N) in EPSG:2180 — the same area
   that the download of this selection covers: NMT/NMPT `sheet` = sheet code frame
   (`sheet_frame_2180`: corners in the sheet system, densified edges;
   the PL-2000 frame is not a rectangle in EPSG:2180), `bbox` = envelope
   `bbox_to_2180`, `geometry` = envelopes of the layer's objects
   (`read_feature_bboxes`, like the `download_data` sheets); LAZ `sheet` = sheet code
   frame as for NMT, `geometry` = envelope of the whole layer (like
   `download_laz_area`).
2. **Services and types:** the WFS services of the product from the registry (`variants(product=)`
   -> `IndexRef`, one per vertical CRS), their annual types
   (`WfsIndex.feature_types`) and the selection of types from the year range; no type
   in the range = `ValidationError` with the years per CRS.
3. **Records:** one `WfsIndex.features(envelope, types)` per service
   (all pages; rules and errors as in 4.1) — the same client and the
   same parser (`parse_index_feature`; LAZ: `laz_tile`) as the download,
   plus the outline `msGeometry` (`feature_footprint`).
4. **Land:** the PRG mask of the envelope (`fetch_land_mask`: `A00` minus `W02`
   and `W03`, like the cutout 4.3).
5. **Combinations** (`_group`): a record belongs to the area when its frame
   intersects the area by more than the edge strip (`overlaps_area`, the rule of
   archive sheets from 4.2). The record variant = `source_format` (format and
   URL) + label `char_przestrz` + vertical CRS of the service ->
   registry `ProductVariant`; the NMT/NMPT combination key: (type year,
   PL-1992/PL-2000 CRS, variant descriptor = format and label, vertical
   CRS); LAZ: (year, CRS, vertical CRS). Archives from the registry are
   combinations like grids. Records without a variant (format inconsistent with the URL,
   format or variant outside the registry, sheet code outside `SheetParser`, no `https` URL
   or CRS) are not a combination: one `Notice("info",
   INDEX_UNSUPPORTED, ...)` (`index_unsupported`) with the format,
   resolution, vertical CRS, years, count of sheets and the reason.
6. **Measurement** (`_measure`): a 1 m grid aligned to whole metres of the
   envelope, pixel centres (`rasterize`, `all_touched=False`), strips
   of rows of 4 Mpx (`_STRIP_PX`, like `LandMask.apply`); in each strip the
   mask classes from `LandMask.burn`. `area_m2` = pixels of the area in the country,
   `land_m2` = land pixels (1 px = 1 m2). `target` = area & land; for
   `sheet` NMT/NMPT without the `EDGE_TOLERANCE_M` strip = 1 m at the frame
   (`_inner`: the frame computed from the sheet code differs from the GUGiK frame by centimetres),
   `bbox`/`geometry` measured exactly. Per combination: `target` pixels
   outside the sum of outlines of sheets with a record YES (`missing`), outside the
   outlines of all sheets of the combination (`uncovered`) and outside the outlines of
   YES records of each campaign separately (one `rasterize` per campaign
   in a strip). `complete` <=> `missing == 0`; `uncovered_m2` = `uncovered`;
   without a threshold. `full_m2` (KD-2) = `land_px * (target_px - missing) //
   target_px` (`land_px` when `missing == 0`): the share of the covered part of
   `target` moved onto land, rounded down — for `bbox`/`geometry` exactly
   `land_m2 - missing`, for `sheet` the frame strip is neither covered nor
   a gap; in PL `complete` <=> `full_m2 == land_m2`, records alone NO = 0.
7. **Result:** `AvailabilityCombination` with `source` (descriptor key),
   `year`, `acquisition_dates`/`published` (min/max `akt_data`/
   `dt_pzgik`), `campaigns` (`nr_zglosz`), `horizontal`, `resolution`
   (label or `None`), `vertical_crs`, `format`, `densities`
   (nominal LAZ densities), `complete`, `sheets_full` (a sheet with at
   least one YES record of the combination), `sheets_partial` (NO only),
   `uncovered`, `uncovered_m2`, `download_hint`, `full_m2`,
   `sheet_records` and `campaign_coverage` (KD-1, ADR-047; below);
   `sheets_missing` and `size_bytes` are CZ fields (plan B; empty/`None` for PL).
   Order: year
   descending, CRS, resolution, vertical CRS, format (order of
   `FORMATS`). `AvailabilityReport(request, checked_at, areas, combinations,
   notices, ok)` (`Document`: the schema `kartograf-availability/1` is a class constant,
   the first key of the document; no `schema` field); `areas` =
   `AvailabilityArea(country, crs, bounds, area_m2, land_m2)`;
   `checked_at` from `kartograf._clock`; `ok` = `False` only when parts of the
   task could not be checked (plan B, `auto`) — in PL always `True`.
   `to_json()` from the `Document` mixin (section 3.6): 2-space indentation, trailing `\n`.
8. **Records to download and campaigns (KD-1, ADR-047):** `sheet_records` =
   `AvailabilityRecord(sheet, campaign, acquisition_date, published, full_sheet,
   url)` records that the `download_hint` of the combination downloads, by sheet,
   within a sheet from the newest: NMT/NMPT the newest record of the sheet in the order of
   ADR-028 (`akt_data`, `dt_pzgik`, `url`) and — when it is not YES but the sheet
   has a YES record (hint with `--full-sheet`, ADR-033) — the newest YES
   (`_sheet_records`, shared with `_needs_full_sheet`); LAZ the tiles that
   `select_newest_cover` (ADR-029) leaves in the task area among the
   tiles of the combination (of one sheet system). LAZ limitation: the hint
   has no sheet system, so a `--year` download selects from the tiles of both
   systems at once; when a year has PL-1992 and PL-2000 tiles, `sheet_records` may
   differ from what the command writes (Krakow 2023: the PL-2000 hint
   downloads PL-1992 tiles). NMT/NMPT: `sheet_records` == download plan.
   `campaign_coverage` = `AvailabilityCampaign(campaign, complete,
   full_m2)` for each campaign from `campaigns` (same order): whether its
   YES records alone cover the land and how much land is within them (measure
   `full_m2`). Test: `sheet_records` == the URLs of the `check_data` plan
   from the hint (`test_sheet_records_are_what_the_hint_downloads`; LAZ
   on a year with one sheet system).

**CZ algorithm and `auto` (plan B, decisions 9-10):**

1. **Parts:** `cz` from `bbox` = that bbox, from `geometry` = the envelope of the layer
   (`geometry_envelope`); CZ sheet code = its frame (SM5 from the index by name,
   `SheetIndex.sm5_sheet` — sheet codes outside the index = `ValidationError`;
   TM33 from the sheet code). `auto` splits the area (geometry: its envelopes)
   by the rectangular envelopes of the countries like `download_data`
   (`split_bbox_by_country`): the PL part as in the PL algorithm (bbox clipped,
   geometry = its objects), the CZ part clipped to the CZ rectangle
   (`country_bbox(..., cz_crs=)`) separately in the CRS of each sheet
   system. `areas` in the order PL, CZ.
2. **Combinations:** CZ variants of the product with a file channel in the native
   vertical CRS of the files (`_cz_files`): NMT — DMR 4G, NMPT — DMP OK
   (each `S-JTSK` Bpv and `ETRS89-TM33` EVRF2007), LAZ — 4 models x 2
   systems = 8; registry order (model, then S-JTSK before
   ETRS89-TM33). A combination arises only when its system has >= 1 sheet.
3. **Sheets:** the CZ part converted to the CRS of the system (EPSG:5514 SM5,
   EPSG:3045 TM33; outside `auto` via `bbox_to_crs`, like the LAZ download
   of an area) and `SheetIndex.file_sheets(system, area)` — a rule shared
   with `CuzkLazProvider.sheets`: SM5 with `PODIL > 0`, TM33 tiles of the index
   (`IN_CZ` has one value `CZ`, it is not a discriminator); cache
   `cz-sheets|<system>|<area in mm>`. The CZ sheet code in its own system is
   the only sheet (SM5 with `PODIL` 0 — none), the sheets of the other system
   come from the envelope of its frame.
4. **Files:** one `HEAD` per file of the openzu (in parallel, `_HEAD_WORKERS` = 8,
   timeout 60 s, retries like `head_signal`), cache `head|<url>`;
   200 = file (`Last-Modified`, `Content-Length`), 404 = sheet without a file,
   any other failure (5xx, timeout, other 4xx) = `DownloadError`, never
   "no file". No `GET` of a data file
   (`test_cz_availability_never_gets_files`).
5. **CZ result:** `sheets_full` (200), `sheets_missing` (404),
   `complete` = no `sheets_missing`, `uncovered` = `bool(sheets_missing)`,
   `uncovered_m2` = the part of the report-area rectangle lying within the frames of sheets
   without a file, computed in the CRS of that rectangle (the frame of a TM33 tile
   moved corner by corner by a pinned operation, so never
   more than `area_m2`; `_frames_m2`), `full_m2` = the same measure for
   sheets with a file (KD-2; `complete` does not require `full_m2 == land_m2` when the
   area extends beyond the sheets of the index), `published` = min/max
   `Last-Modified`
   (YYYY-MM-DD), `size_bytes` = sum of `Content-Length` (`None` when some
   file does not provide it or no sheet has a file; CLI: `-`),
   `year`/`acquisition_dates` = `None`, `campaigns`/`densities`/
   `sheets_partial`/`sheet_records`/`campaign_coverage` empty,
   `horizontal` `S-JTSK`/`ETRS89-TM33`.
   `AvailabilityArea` CZ: `crs="EPSG:5514"`, `bounds` = the CZ part
   in EPSG:5514, `area_m2` = `land_m2` = report rectangle (area: the CZ
   part in EPSG:5514; sheet code: its frame) — CZ has no land mask.
6. **Models without files:** NMT (DMR 5G) and NMPT (DMP 1G) get one
   `Notice("info", CZ_SERVICE_ONLY, ...)` (`cz_service_only`): the model has no
   sheet files (the report does not cover it), but is available for the whole of CZ
   as a cutout (`--cutout`), a TM33 tile from ImageServer and LAZ (`--model`);
   only when the CZ part has at least one sheet of the index (the `auto` part in PL
   inside the CZ rectangle — without `Info:`). LAZ has files of all models.
7. **`auto`:** a country that could not be checked (`DownloadError`), with the
   other one checked = `Notice("warning", CHECK_FAILED, ...)` and `ok=False`
   (the report of the other country is kept; CLI exit code 10 or 11); failure of both = an exception
   (the first error), like a single-country task.

**Download hint** (`_download_hint`): a tuple of commands to paste after
`kartograf ` or after `kartograf project add NAME ` — without `--root`
(the store comes from the user's `--root` or from the project, ADR-040).
The area as in the task (`--country pl --bbox ... [--bbox-crs]` or
`--geometry FILE [--layer]` + `--sheet-system`; `--sheet` — the sheet code alone,
when the combination is in its system (PL-2000: the sheet code and its descendants),
otherwise one command per sheet),
for PL-2000 grids one command per sheet scale
(`--scale`), the variant (`--format` for archives, `--resolution` when the
variant has a label, `--vertical-crs`), `--year`, and `--full-sheet` when
in some sheet the newest record of the year is NO and a full record of that
year exists. The grid rule (coordinator decision 2026-10-16, E2E
of plan B at Cieszyn): an area or sheet code command only when the
sheets that the PL download of this scale would plan (`_selected_sheets`:
the grid of the whole bbox `--country pl` without clipping, the grid of the geometry or
the descendants of the sheet code; one selection per system and scale, `functools.cache`) are a
subset of the sheets of the combination; otherwise one `--sheet` command per sheet
with a record (`_grid_areas`, PL-2000 separately for each scale) — a grid
sheet without a record (beyond the border, sea, no record of the year or
resolution) would give `Brak danych` (`check_failed`, exit code 10 or 11). Archives
(`source_file`) and LAZ: always the area or sheet code of the task (the download
plans only records of the sheet index). LAZ: area + `--vertical-crs` +
`--year`. The command selects exactly the sheets of the combination (tests
`test_report_sheets_equal_download_selection`,
`test_border_hint_plans_only_sheets_with_records`). CZ (`_cz_hint`): raster —
one command per sheet with a file (`elevation download --product nmpt
--sheet CTES86 --resolution 0.5m --vertical-crs Bpv`, vertical CRS
native for the files of the system); LAZ — one command for the task area
(`--country cz`, `--bbox`/`--geometry`, `--model`, `--vertical-crs`),
for a sheet code one command per sheet. Every hint passes the validation of
`download_data` and `project add` without a network (`test_cz_hints`,
`test_cz_hints_accepted_by_project_add`).

**Cache:** table `index_area_cache` in `MetadataCache`
(`get_index_area`/`set_index_area`, JSON payload, TTL like records —
`DEFAULT_TTL_SECONDS`, 7 days): keys `wfs-types|<endpoint>` (yearly types
of the service), `wfs|<endpoint>|<types>|<envelope in mm>` (envelope records
with outlines), `prg|<envelope in mm>` (land mask) and CZ
`cz-sheets|<system>|<area in mm>` (index sheets) and `head|<url>`
(result of a file `HEAD`, also 404); WFS index tiles of a collection (3D mesh,
`transport/index_records.py::wfs_records(cache=)`) - key
`wfs-records|<endpoint>|<type>|<envelope in mm>` with area records, so
a repeated download of an area with local tiles does not query the index
(`--check-updates`/`--upgrade`/`--force` refresh the entry);
the SM5 sheet code goes to `sheet_cache` (TTL
30 days). The cache is opened by
`open_cache(cache, force=force)`; `force=True` (CLI `--force`) skips
reading and overwrites entries. A repeated report of the same area does not query
the network (measured 2026-10-15, 16 km2: approx. 5–7 s with network, 0.6–1.5 s
from cache; CZ 2026-10-16, 16 ha NMPT: 1.3 s with `--force`, 0.6 s from cache);
`kartograf cache stats` counts the entries in `Wpisy obszarow
skorowidza`.

**Errors:** a failure of the sheet index service, PRG or CUZK (index, `HEAD` other
than 404) = `DownloadError` (CLI
`Error:`, `source_unavailable`, exit code 5), never an empty report; an empty, valid response = a report
without combinations (CLI: `Brak arkuszy ... dla obszaru w skorowidzu GUGiK`,
CZ: `w indeksie CUZK`; code 0). Under `auto` a failure of one country with the
other checked = `CHECK_FAILED` and `ok=False` (point 7 above). The report
does not request any data file
(`test_availability_never_downloads`: the session stub rejects every URL
outside the sheet index and PRG; CZ: `test_cz_availability_never_gets_files`).
CLI = API consistency: `--json` gives the same text
as `check_availability(...).to_json()` with the same cache.

### 4.10 Collections: unit packages, area objects and ATOM feed files (ADR-042)

**Command in the library.** `kartograf
boundaries|cadastre|models3d|hydro|names|maps|geodesy download` =
`download_collection(...)`/`check_collection(...)`
(`download/collections.py`); the CLI only translates flags
(`cli/collection_cmd.py`: `library_arguments` from the catalog gives the function arguments,
the same for project items), and the shared shape of the groups is in
`catalog/commands/_collection.py` (`--help` texts from the library:
`collection_product_choices`, `collection_level_choices`,
`collection_variant_choices`). `validate_collection_request` checks the whole
selection WITHOUT a network and is the only place of the rules (both functions
and project items call it): bbox coordinates, exactly one selection (`teryt`,
`ku`, `sheet`, `bbox`, `geometry`, `whole_country`), product from the registry,
country (`pl`/`cz`/`auto` required with an area; `whole_country` only
`pl`/`cz`; with `sheet` from the sheet code), channel for the kind of selection, variant
(`lod`, `year`, `format`, `scale`, `sheet_system`, `network`) and level (`level`,
with `auto` per country), `horizontal_crs` equal to the CRS of the file. The error gives the CLI
flags and the selections that the product has (e.g. `--teryt 1261: admin nie ma paczek
powiatow; dostepne: ...`). An option value that no channel
of the given selection has, but a channel of another selection has, names that selection (`--network
gravity: control (PL) - dostepne tylko dla --bbox/--sheet/--geometry
(obiekty obszaru); dla --teryt: horizontal, vertical`); a PL+CZ task
(`auto`) without a selecting option or with a value of one country gets
the values of the other country and the common values (one value applies to both).
A collection product is a descriptor with a `unit_package` or
`feature_bbox` channel other than `landcover`, or with just the national file of an ATOM feed
of one dataset (QGZU; `atom.single_dataset`); sheet and voivodeship feeds
(CZ orthophoto, NMT 100 m) belong to `download_data`.

**The kind of selection determines the channel (D2).**

| Selection | Channel | Units | File (rule 9 of section 3.3) |
|---|---|---|---|
| `teryt` (2 digits = voivodeship, 4 = county; PL) | `unit_package` of that unit | `[teryt]` | `teryt/<T>` |
| `ku` (6 digits; CZ) | `unit_package` KU | `[ku]` | `ku/<code>` |
| `sheet` or sheets intersecting the area | `unit_package` of sheets with the PL or CUZK index | `[godlo]`/sheets of the area | sheet code hierarchy (`<MAPNOM>` CUZK: `cuzk_map_path_parts`) in the variant segment |
| area of a product with a `feature_bbox` channel | `feature_bbox` | one area in the native CRS of the service | `bbox/<coords>.gpkg` |
| area of a product with a tile channel (`unit="tile"`) | `unit_package` of tiles from WFS index records | area records (`next` pages), `year` = record filter (`Notice` `unit_list`) | `<crs>[/<zone>]/<tile>` |
| area of a product without `feature_bbox` (county) | `unit_package` of the county | counties from PRG (`discover_teryts_for_bbox`, metadata cache; `Notice` `unit_list`) | `teryt/<T>` of each county |
| `whole_country` | `unit_package` of the unit `country` or `atom_files` (file from the ATOM feed of CUZK; `horizontal_crs` required when the file has several CRSs) | `pl` or `cz` (PRNG: topics) | `country/<code>` (PRNG: `pl_<topic>`) |

Area: `bbox` in a CRS from the `--bbox-crs` list, `sheet` = extent of the PL
or CZ sheet code, `geometry` = envelope of the objects in the file (`--layer`).
Under `country="auto"` the area is split into countries as in `download_data`
(section 4.6) and narrowed to the countries where the product exists (`Notice`
`auto_narrowed_to_pl`/`auto_narrowed_to_cz`); `world --country pl` does not
clip the area to Poland. An area converted to the native CRS of the service
(`transform_bbox`; Czech CRSs - pinned operation) or originating
from a sheet/geometry/`auto` yields `extra.parent_request` (section 3.4);
the county packages of the area always have it. Country file:
first `HEAD` (ATOM feed file: feed `length`, no `HEAD`)
and `Notice` `whole_country_size` (`warning`: bytes or "unknown
size"), then the transfer (K7). A single-country product under `auto` is
narrowed to that country (`network` -> CZ: `auto_narrowed_to_cz`), and the
`admin` level with `auto` is given per country (`{"pl": "gmina", "cz": "obec"}`;
one value unavailable in one of the countries = error with the hint
`--level pl=<level>,cz=<level>`).

**Unit tasks.** Each file is a `UnitJob` (slot, sidecar `request`,
source): `package_job` (unit package or country file) or an area objects task.
`run_job` = `fetch_version` of the slot (policy
`use_local`/`store_file`, section 3.3 rule 6; `update` modes),
`inspect_job` = an item of the `kartograf-plan/1` plan without downloading data
(lane `collection`, `unit` = TERYT / coordinates `_` / `pl` / `cz`). A unit error
goes to `CollectionReport.failed` as `UnitFailure(unit, country, error,
kind)` (`no_coverage` for `NoCoverageError`, `download` for
`DownloadError`), the remaining units keep running (`workers` =
`ThreadPoolExecutor`, HTTP session per thread). Result: `CollectionReport(files,
failed, stale, notices, ok)`, `ok` = no errors and no stale plan
items, except `--country auto` in PL and CZ (rule of `download_data`,
section 4.6): a country with errors alongside a country without errors is a partial success -
`ok = True` (code 0), `Notice` `auto_partial_success`
(`download/area.py::emit_partial_success`, shared with `download_data`), the errors
remain in `failed`. A country in which the area has no units (no KU in RUIAN,
county, sheet, tile - the rectangular CZ envelope covers PL territory)
or in which the unit query failed is an error of that country
(`UnitFailure(<country>, <country>, ...)`, `_jobs`) and does not interrupt the other; no
units in ALL countries = `NoCoverageError`. `--check-updates`: such a
country is `Warning` `check_failed` + `auto_partial_success` (as in `check_data`).
The KUs of the area according to RUIAN (`cadastral_areas_for_bbox`, also an empty response) lie
in the metadata cache (`index_area_cache`, TTL 7 days, like PRG counties), so
repeating the area works without a network. `Notice` `unit_list` names at
most 10 units, the rest is counted (`notices.names_text`). Timeouts:
`SERVICE_TIMEOUT` 60 s (WFS/REST, a channel may have its own
`FeatureBBoxParams.timeout`, e.g. PRNG OGC API 180 s), `PACKAGE_TIMEOUT`
120 s (package), `PROBE_TIMEOUT` 30 s (`HEAD` of the signal, PRG query),
`SIZE_TIMEOUT` 120 s (`HEAD` of the size: the GUGiK opendata server responds
in 0.2-90 s, approx. 3.5 s per GB of 3D tree packages).
`LandCoverManager` uses the same `package_job`/`run_job`/
`inspect_job` for the BDOT10k archive and `landcover_request`/`run_request`/
`plan_request` for ZABAGED (lane `landcover`, section 4.8).

**Area limit (ADR-043 erratum 3).** An area task (`bbox`, `sheet`,
`geometry`) that would download more than `VOLUME_FILES` = 100 files or
more than `VOLUME_BYTES` = 10 GB ends with a `ValidationError` BEFORE the
first transfer (`run_request` -> `_within_volume`, a single place for
collections, `LandCoverManager` and NMT 100 m): the file count, the size (sum of
`HEAD`/`length` of the ATOM feed; up to 100 files each file is measured, so the
10 GB limit is exact, above 100 the refusal is decided by the count, and the size
is only an indicative average of `VOLUME_SAMPLE` = 5 files spread
evenly) and a hint (narrow the
area, choose a unit `--teryt`/`--ku`, run the plan with a part of the
items). The files counted are those the task would send: without a local
version, with `update="force"` all of them, with `--upgrade --plan` the plan items;
area objects (`feature_bbox`) are one file with no size. A size
queried before the transfer is not queried a second time (`Notice`
`download_size`, ATOM file). Unit selection (`teryt`, `ku`)
and `whole_country` name their files themselves - no limit, the size is still
in a `Notice` before the transfer; there is no bypass option (decision 2026-10-15).

**The `unit_package` engine (`transport/unit_package.py`).**
`select_variant(params, **choice)` selects a published variant without a network:
no value with several variants or an unpublished value =
`ValidationError` with the list of allowed values; a sole variant may be omitted,
and a given one must equal the published one (K8). `package_url` fills in
`{teryt}`/`{woj}`. `fetch_package` downloads atomically (`download_to`,
shared retry policy), rejects an HTML/XML document on HTTP 200,
compares the size with `Content-Length` (interrupted transfer = `DownloadError`),
reads the ZIP central directory, requires the `members` of the variant, and with
`unpack` unpacks in a streaming manner EXACTLY one member with that suffix
(CRC is checked by `zipfile`). HTTP 404 = `NoCoverageError` (the source
does not publish the unit package: LoD2 outside coverage, TERYT code changed),
any other error = `DownloadError`; the package never lies in memory, and an error
leaves no result file.

**The `atom_files` engine (`transport/atom.py`, D12, plan D).** The feed of the CUZK
ATOM service has one entry per dataset (ORTOFOTO: 16,301 SM5 sheets, 23.7 MB;
ZABAGED-GPKG: one dataset), the entry links the dataset feed, and its entries are
files (`rel="alternate"` with `length`, CRS category
`http://www.opengis.net/def/crs/EPSG/0/<code>`). File names carry the year
or release date (`WRTO24.<year>.<sheet>.zip`,
`ZABAGED-5514-gpkg-<date>.zip`), so the URL exists only in the feed.
`atom_index` reads the service feed in a streaming manner (`iterparse`, entries
removed from the tree) into `key -> AtomEntry`: `entry_pattern` is searched in the id
of the dataset feed, group `sheet` = key (without it the feed has one dataset,
key `""`). The index lies in `MetadataCache` (`atom_cache`) with the `ETag`
of the feed: within the TTL (7 days) without a query, older: conditional GET
`If-None-Match` (304 = unchanged); `--force`, `--upgrade`
and `--check-updates` (cache in refresh mode) read the feed anew.
`resolve_atom_file` always reads the dataset feed fresh (small, carries the
release) and selects the file by CRS category (`check_atom_crs` - without a
network); a key missing from the cached index or a 404 of the dataset feed = ONE
index refresh. Release = the `updated` date of the file entry, with the year
of the `year` group when present (`2024_2025-02-06`, `2026-10-04`) - the version
label and the `metadata` signal. `fetch_atom_file` downloads atomically and compares
the size with the feed `length` and `Content-Length`; `unpack_members` copies
ZIP members 1:1 (longest suffix first). A key outside the feed =
`NoCoverageError`; HTML instead of a feed, an entry without a single link, an ambiguous file,
an interrupted transfer = `DownloadError`. Read timeouts:
service feed 120 s, dataset feed 60 s.

**The `feature_bbox` engine (`transport/feature_bbox.py`, D3/D4).** Service
metadata is fetched fresh once per download, without the metadata cache: WFS
`GetCapabilities` (every layer exists, DefaultCRS has the EPSG code
`native_crs` - compared by code, not by URN/URL notation; `CountDefault`
not smaller than `page_size`) and `DescribeFeatureType` of the layer (XSD for
GDAL); ArcGIS `/<id>?f=json` (layer CRS, identifier and ordering
fields, `maxRecordCount`). A mismatch = `DownloadError`, without
substituting the CRS. Number of objects N: WFS `RESULTTYPE=hits`
(`numberMatched="unknown"` = `DownloadError`), ArcGIS `returnCountOnly`;
N = 0 in all layers = `NoCoverageError` (no file), an empty
layer next to non-empty ones = a layer with a schema and no objects (without an XSD
schema - HY-NET - a layer with only the identifier field). Pages are
downloaded by position (`STARTINDEX`/`COUNT`; ArcGIS `resultOffset`/
`resultRecordCount` with `orderByFields`) from 0 every `page_size`, and `next` links
are ignored (MapServer drops them on middle pages, GeoServer gives them
on the last one). The loop ends when there are N unique identifiers; beyond
the N planned positions it continues only if the previous page was
full and added new identifiers - MapServer repeats an object at the page
boundary (PRG A03, `hits` 39, `COUNT=13`: the 39th object only at
`STARTINDEX=39`). A short page with fewer than N unique, a page beyond N
without new identifiers or more than N unique = `DownloadError`;
so are HTML, `ows:ExceptionReport` or a JSON `error` on HTTP 200. WFS BBOX:
`<a>,<b>,<c>,<d>,urn:ogc:def:crs:EPSG::<code>` in the order of `axis_order`
(GUGiK EPSG:2180 `yx` = N,E; CUZK EPSG:5514 `xy` = X,Y - both consistent
with EPSG); swapping the axes gives an empty result WITHOUT an error, hence the order has a test
on a real service response. `SRSNAME` = the same URN; the ArcGIS envelope is
always x,y (`inSR`/`outSR` native). Coordinates are rounded OUTWARDS
to a millimetre. Pages go to disk
(`<pages_dir>/<layer>/<start>.gml|.json`) as they arrive - in memory
one page at a time.

**GPKG writing (`transform/gpkg.py`, D5).** `write_gpkg` reads pages through
GDAL (`pyogrio`): GML with `XSD=<DescribeFeatureType>` (the same field types on
every page), `WRITE_GFS=NO`, `DOWNLOAD_SCHEMA=NO`
and `GML_FETCH_ALL_GEOMETRIES=YES` (a multi-part EGiB object is a repeated
`<ms:geom>`; without this option GDAL keeps the last part), ArcGIS GeoJSON
with field types from the layer `fields`. An XSD that does not itself declare types
(HY-NET: only an `xsd:include` of a remote INSPIRE schema) does not go to
GDAL: fields are read from the content of each page, the layer gets the union of the fields of
the pages in order of first occurrence (missing field = null, one field
with two types = `DownloadError`), so the HY-NET schema depends on the content of
the area (ADR-042 erratum 2); an empty type without a schema = a layer with only
`gml_id` (geometry `Unknown`). Layer description (`DESCRIPTION`) = WFS type
or ArcGIS layer name with id (`Vodní tok (93)`, `Obec (12)`). An identical duplicate (fields except
`drop_fields` and geometry bytes) is skipped, the same identifier
with different content = `DownloadError`, a number of unique objects other than N =
`DownloadError`. Result: one GPKG layer per source layer (`FeatureLayer.name`),
objects in the order of `id_field`, full geometries of objects intersecting the
area (no clipping, `promote_to_multi`), CRS `native_crs`, `drop_fields` fields
outside the file (values in the sidecar
`extra.source.dropped_fields`, section 3.2). Constant `OGR_CURRENT_DATE` -
the same pages give the same bytes within one GDAL version (live
2026-10-15: `--force` of PRG municipalities (Polish gminy) = `bez zmian`). GDAL options are global for the
process, so one lock serialises the configured work of the module
(parallel tasks). The writer keeps the objects of one layer in memory (area of
a municipality, district - thousands of objects; very large areas - see USAGE 7).
The GPKG is created in a local temporary directory (SQLite does not write on a
network volume without locks), then goes to `versions/.incoming/`
of the store.

**Store, signals and labels (D6, D7).** Signal = `update_signal` of the channel.
Channels without an explicitly announced signal (`PRG`, `EGiB`, `PRNG`/`Geonames`
areas, `PRNG` country and other area objects) have `none`:
the local version is used without queries, `--check-updates` = `unverifiable`
(`nie da sie sprawdzic bez pobrania`), new content is brought only by
`--force` (the same
content = `unchanged`, different = a new version). CUZK country files with `ETag`
(RUIAN, HY-NET) have `http`: `--upgrade` compares the local version with one
`HEAD` (different `ETag` = download), `--check-updates` = `current`/`newer`,
by default the local version without a query. A file from the ATOM feed (ZABAGED,
Geonames country, QGZU) has `metadata`: the release from the feed before the download, a different
release = `newer`. BDOT10k maps have `index` (the `Stan bazy` date separately
per scale from GetFeatureInfo; a sheet with a local version by default without
GetFeatureInfo - `_sheet_jobs(skip_local)`, `UnitJob.unchecked`), 3D mesh
tiles too (label from the WFS record:
`Aktualnosc` and `Numer_zgloszenia_pracy`; the tiles of an area are chosen by the WFS index,
whose area records lie in the metadata cache - `index_area_cache`,
TTL 7 days - so a repeated run with local tiles does not query the network, like PL
sheet indexes; modes `--check-updates`/`--upgrade`/`--force` query the
index), ZTM sheets `http` (`HEAD`).
Label = `edition` of the variant (BDOT10k
vintage, year of the 3D models; `label_source="edition"`), the release from the ATOM feed
or the download date (PRG, EGiB, RUIAN, HY-NET). Releases of the same content - variants differing only in a value
equal to the release (`year`), with the same format and LoD - are related slots
(`FileSlot.related_roots`): an identical sha256 in another release of the same
unit = a hard link to the existing data, status `relabeled`
(`same_as` = label of the version found).

**Names and maps (E2).** `pl.gugik.prng` and `pl.gugik.prng_world` each have
one OGC API Features collection (natively CRS84; `numberMatched`, `next`
pages, a page of up to 10000 objects, a single request limit of 180 s).
`world` does not restrict the area to the PL extent; the national PRNG consists of ZIP files
of the original two RP topics or of a single `SWIAT`. CUZK Geonames is
25 ArcGIS REST layers in EPSG:5514 and two national ATOM feed channels
(`GPKG`/`FGDB`, choice of EPSG:5514/3045). BDOT10k maps are 4 scales x
2 formats from the `wms_gfi` records (`Mapy10k`...`Mapy100k`); the scale
determines the number of sheet code segments, the format is a separate store segment.
CUZK ZTM is 6 scales x 2 systems (S-JTSK/ETRS89), respectively
ZIP TIFF/DGN/SHP or PDF (ETRS89 only TIFF/PDF). The sheet system
follows from its sheet code, but a conflicting `sheet_system` is an error;
the variant's `sheet_grid.crs` gives the sidecar EPSG:5514 or EPSG:3045.

**Boundaries, cadastre and CZ (E3).** `pl.gugik.prg_addresses` has three
channels: WFS KIN (`A07_Punkty_adresowe` and `A08_Ulice` into one GPKG
EPSG:2180, axes N,E), county SHP packages (`unit="powiat"`) and two national
files (SHP, GML selected by `--format`). `pl.gugik.prg_special` is the OGC API
PRG in CRS84 (44 collections listed explicitly in the descriptor) with a channel timeout of
120 s (`FeatureBBoxParams.timeout`; an area takes minutes, because the service is queried
for each collection separately) and a national SHP/GML file. The collection
`GranicaObwoduSpisowego` is not part of the area result (the response takes
158 to over 400 s): `FeatureBBoxParams.area_omitted` carries the text, which the
collection engine turns into an `Info` `AREA_OMITTED` (`<product>: <text>`)
for every area task of the channel (the census districts are
in the national file). `cz.cuzk.hynet` has the same mechanism (the type
`WatercourseSeparatedCrossing` without geometry only in the national file)
and `cz.cuzk.zabaged` (22 area layers versus the full database of the national
file). `pl.gugik.rcn` has the channels
`unit="powiat"` and `unit="woj"`; the ZIP package is unpacked into a single
GPKG (`UnitPackageParams.unpack=".gpkg"`), and `unpack_layers` (only
with `unpack=".gpkg"`; a registry invariant) enforces the presence of the layers
`transakcje_dzialki`, `transakcje_budynki`, `transakcje_lokale`:
unpacking and the check run in a local working directory (SQLite does not
work on network volumes), a missing layer = `DownloadError` and no
version. `cz.cuzk.cadastral_map` is `unit="ku"` with four variants
(`--format SHP|DXF|DGN|VFK`, ZIP 1:1, signal `http`); the KU of an area according to the
RUIAN layer 7. `cz.cuzk.geomorphology` is ArcGIS REST
(`GeomorfologickeJednotky`, EPSG:5514), one layer per level
(`--level`, `selection="level"`). The cadastral map in the VKM format is
outside 0.8.0 (the VKM file address returns 404 for KU 623164).

**3D models, control networks and quasi-geoids (E5).** `pl.gugik.mesh` has a channel
`unit="tile"` with `IndexSource(kind="wfs", unit_field=None)`: the index
`ModeleSiatkowe3D` has one record per file, but the `modul` field (`74230_55482`)
names tiles of several projects and cities (26,633 values in several places of the country,
138 places with two meshes of the same year - from images and from scanning), so
the unit = the record's file name without `.zip` (`78944_6777_74230_55482`),
each area record is a separate file, and `year` filters the records (the rule
"newest tile record" does not apply to mesh). The slot directory (`1992` or
`2000/<zone>`, rule 10) and the sidecar layout are given by the record's `uklad_xy` (OBJ
in the coordinates of that zone), heights
`EPSG:9651` from the variant. `pl.gugik.trees` is county packages of a single
release (LoD1 2023; the `--lod`/`--year` flags may be omitted, any other value = an
error) - 0.3-25 GB, a `Notice` `download_size` before the transfer, a stream to
staging and a ZIP check on disk; an area almost always exceeds the
10 GB limit, `--teryt` has no limit. `pl.gugik.control` has four WFS channels
(one service per network, selection by `choice` `network`, shared capability
`bbox_vector`), county packages of the horizontal and vertical network
(`unit="powiat"`, tokens `<network>`, `xls`) and 1:100 000 sheet archives
(`unit="sheet"`, `SheetGrid(system="1992", parts=3)`; `--sheet` of any
scale gives the 1:100 000 sheets of its extent). The gravimetric and magnetic
networks and the archives have no county packages: `--teryt` with them = an error
with a hint to select an area. `cz.cuzk.control` is a single ArcGIS channel
with `selection_key="network"`, in which one network code names several
layers (horizontal: 18, 20 and the layers defined in ETRS89 2-8, which are not
a subset of 18/20 - zero common points in the country). Quasi-geoids are a single
national file: PL-geoid2021 TXT (`file_kind="txt"`, a file without ZIP checked
as text without NUL and markers) and QGZU ZIP from the ATOM feed (a collection product
with only the ATOM channel of one dataset); an area = an error with `--whole-country`.
Kartograf does not apply the models to other data (ADR-043, item 7 of plan E).

### 4.11 Interface for agents: command catalog, documents and MCP server (ADR-046)

**Principle.** The same task run through the CLI with `--json`, through the library (`to_dict()`) and
through the MCP server gives the same document (3.6); an error has a stable `code`, `exit_code` and `hint`
(`kartograf-error/1`). The CLI and MCP are thin: they translate and print (Z1, Z8), while the commands,
parameters and allowed values are described by a single catalog (Z9). Usage: USAGE, section 9;
rationale: ADR-046.

**Command catalog (`src/kartograf/catalog/`).** The declarations (`catalog/spec.py`: `Command`, `Param`,
`Constraint`, `Example`, `Group`) live in `catalog/commands/<module>.py`, one module per
CLI group (`MODULE_ORDER`: elevation, imagery, landcover, soil, boundaries, cadastre,
models3d, hydro, names, maps, geodesy, project, misc); `declared()` finds the modules by
name, so a new group is one new file. `Param` carries the name, kind (`str`, `int`,
`flag`, `bbox`, `bbox_crs`, `path`, `per_country`, `str_list`, `plan`, `options`), the CLI flag,
the API argument name (`argument`), whether it is required, `task` (a project task option), `allowed`
(a provider reading the source registry when the catalog is built, not at import), the description and fields
for the parser only (`dest`, `metavar`...). The declarations produce:

- `list_commands()` -> `CommandList` (`kartograf-command-list/1`) and `command_schema(command)` ->
  `CommandCatalog` (`kartograf-commands/1`, one command: the name or the `operation_id`;
  `catalog/build.py`, `model.py`): `build.command_entries()` builds the entries once from the declarations
  (an option = `is_option`, enums from `meanings.py`, examples from `excerpts.py`); the page budget of
  20,000 characters (DOC-1.7) and conformance with `schemas/nogat/commands-1.schema.json` are guarded by
  `tests/contract/test_commands_schema.py`. The exit code and error tables:
  `error_report.EXIT_CODES`, `ERROR_CODES` (USAGE 9.3); the 12 data commands: `project_task`
  in the declarations (`project.commands.COMMANDS`, KB-1);
- the CLI parser (`catalog/cliparser.py::build_parser`; `cli/_parser.py::create_parser` is a
  facade): `--help`, `choices`, flag exclusion and examples (`epilog` from the catalog
  examples); the `cli/groups/*` modules do not exist;
- project data command options (`project/commands.py::COMMANDS`: `TaskCommand.options` =
  `Command.task_options`) and the JSON <-> library arguments conversion
  (`catalog/kinds.py::convert_arguments`), shared by `project add`, `parse_command` and the MCP
  server;
- MCP tool specifications (`catalog/tools.py`) and error hints
  (`catalog/hints.py::example_for`: a command example in `hint`).

Consistency is enforced by contract tests (`tests/unit/test_catalog*.py` and `tests/contract/test_catalog_declarations.py`): parser flags == catalog in
both directions, `COMMANDS[...].options` == `task` parameters, `function`/`check_function` in
`kartograf.__all__` with matching signatures, `allowed` == registry, examples through
`validate_command` and the round trip `parse_command(format_command(...))`, constraints tested by
a violation derived from the example. The library does not import `kartograf.cli` (a test in a
clean process).

**Command layer (`src/kartograf/commands.py`, KB-2..KB-5 of Archiwista).** `parse_command` (line
-> `CommandCall(command, options, run)`; the catalog parser in "only the given flags" mode),
`validate_command` (task conversion and validation without network and writes), `format_command`
(`catalog/formatting.py`), `run_command`/`check_command` (conversion, validation, then the command
function: `download_data`, `download_collection`, ... or `check_*`). `options` is the JSON form of
project task options (ADR-040), `run` - the remaining flags of the line under the parameter
names (`root`, `upgrade`, `force`, `check_updates`, `plan`, `workers`,
`quiet`, `json`, `summary`; there is no `update` key: `run_command` takes the mode as
`update="upgrade"|"force"`, and `check_updates` is `check_command`, so the mapping is done by the
caller). The functions without network (`parse_command`, `validate_command`,
`format_command`) have a test with a transport stub rejecting every request.

**Errors.** Every `KartografError` class has its own `code` in `__dict__` (snake_case, unique;
`tests/integration/test_errors.py`), `exit_code`, `DETAIL_FIELDS` and an optional `hint`; the library validators
set `ValidationError.option`/`options`/`allowed` (the API argument name, not the flag).
`error_report(exc, command=)` turns any exception into an `ErrorReport` (the codes `io_error` for
`OSError`, `interrupted`, `terminated` and `internal_error` are built here, not by the hierarchy classes); `hint` is composed
deterministically from `exc.hint`, `DEFAULT_HINT`, `hints`/`remedy` or `Allowed values of ...` and
`Example: ...` from the catalog (English, `kartograf.messages.errors`; up to 400 characters). `main` (`cli/commands.py`) detects JSON mode before
parsing (`cli/_json.py::json_mode`), builds the parser with `usage_errors=True` (a syntax error
is a `UsageError`, with `command` when the line named a known command) and turns every exception into a
`kartograf-error/1` document on stdout (stderr empty) and the exit code `e.exit_code`
(0/1/2), 130 for Ctrl-C, 143 for SIGTERM; `KARTOGRAF_DEBUG=1` re-raises the exception. The records of the `kartograf` logger
(level WARNING and above) `main` turns into `Warning:`/`Error:` lines on stderr
(`_StderrLines`; without a handler Python prints them without a prefix); with `--json` only
`kartograf.transport.http` records (retries) pass through, and with `KARTOGRAF_DEBUG` all of them. The tables of exit codes
and errors are in USAGE 9.3 (`tests/contract/test_docs_tables.py` ensures they are equal to the catalog).

**Interruption and thread pools (`src/kartograf/interrupt.py`).** Ctrl-C is a `KeyboardInterrupt` only in the
main thread, so `--workers >= 2` (units in a `ThreadPoolExecutor`) waited for the whole queue
and committed it after the interruption (e2e 0.8.0: B P2-1, C P2-5, D P2-2). Every download pool
(`DownloadManager._download_many`, the collection `run_request`, BDOT10k counties in `LandCoverManager`,
PL LAZ tiles and CZ LAZ sheets) goes through a single helper `run_parallel(work, items,
workers=, on_done=)`: when the thread waiting for results gets an exception (Ctrl-C, a unit error,
an `on_done` exception), units that have not started are cancelled, and those in progress get a stop flag;
the call returns only after them, so nothing from the pool keeps running and nothing is committed after the
interruption (versions committed earlier remain). A unit sees the flag in `check_stop()` (before a
request and between body chunks in `transport/http.py::download_to`/`get_with_retry`/
`head_signal`, in `transport/aaigrid.py`, in the BDOT10k package loops and at the start of
`commit_version`) and instead of a retry pause, and ends with `Stopped` - a subclass of
`KeyboardInterrupt`: the same cleanup works as with `--workers 1` (`except BaseException`,
`finally`), and no `except Exception` of the package turns it into a unit failure. A request
blocked on the network ends at the latest with the timeout. Probe pools (`executor.map` with HEAD and
index requests) cancel the queue by themselves (`map`) and wait only for current requests.
SIGTERM: `sigterm_interrupts()` (CLI `main`) raises `Terminated` in the main thread (also a
`KeyboardInterrupt`; the first signal restores the default reaction), and `error_report` gives
`terminated`/143. Outside `main` (library, MCP server) the signal is not intercepted.

**MCP server (`src/kartograf/mcp_server.py`, `catalog/tools.py`, `_output_schema.py`).** One tool per
command of the catalog that has a family (39), named by the `operation_id` (`kartograf_<group>_<command>`, AGI-5.2).
`catalog/tools.py` builds them from the declarations and `command_entries()` (descriptions, `enum` values, bounds,
examples, `dependentRequired` `bbox` -> `bbox_crs`, JSON Schema 2020-12 with
`additionalProperties: false`; `anyOf` for a value per country) and from the mode of the server:
`tool_specs(allow_writes=)` gives, with writes, the commands as declared, and without writes the commands that have a
plan (the 12 data commands and `project download`) in a plan-only variant (without the run options `update`, `plan`,
`workers`, `summary`; `check_updates` fixed to `true`; `readOnlyHint: true`), while the commands that write without a
plan (`project init|add|remove`) vanish from the list (`hidden_tools`: a call is `forbidden`).
`_output_schema.py` is the `outputSchema` of all tools: the schema `result-1` from `schemas/nogat/`
made self-contained (`scripts/generate_output_schema.py`, a contract test: the module == the generator and the
same verdicts as the Nogat schema). Without `mcp` (the module does not import the SDK).

`mcp_server.py` exposes them through the low-level `mcp.server.Server` (stdio): the result is
`CallToolResult(content=<compact JSON>, structured_content=<to_dict() of the kartograf-result/1 envelope>,
is_error=<error>)`, errors as `kartograf-error/1` (`forbidden` for a path outside `--allow-dir`, for a
hidden tool and for a run option in the plan-only variant; `missing_dependency` without the SDK),
the order of the checks: refusal of a write, the input schema (`jsonschema`), the absolute paths rule
(`--allow-dir`, also paths nested in the options of `project add`), the run options next to `check_updates`,
`validate_command`; progress through `report_progress`, at most 4 concurrent network calls (those with
`openWorldHint`) and a server cache in the user cache directory. The `mcp` SDK is an optional dependency
(extra `mcp`), and only `mcp_server.py` touches it, lazily. The server instructions (in English, up to 4096
characters) are built by `build_instructions` from the tool names of the catalog and the state of the server. Context
budget: `tools/list` is about 207,000 characters (87,000 without `outputSchema`; `--tools core` 64,000 and 34,000), because
every property carries the description from the catalog and every tool an `outputSchema`; the budget of 30,000 characters
of ADR-046 (D22) no longer holds (ADR-052, decision 9); `list_commands()` and a result page <= 20,000 characters (DOC-1.7);
tests enforce this (`tests/contract/test_mcp_tools.py`, the AGI-5.13 gate test in
`tests/integration/test_mcp_server.py`). Usage and client configuration: USAGE 9.6.

**New command through the catalog.** Six steps:

1. **Declaration** in `catalog/commands/<group>.py`: `COMMANDS` (`Command`: `id`, `summary`,
   `kind`, `function` and `check_function` from `kartograf.__all__`, `result_schema`, `family`
   and `core` (the MCP family), `effects`, `project_task`, `params`, `constraints`, `examples`)
   and `GROUPS`. Modules are found by name (`declared()`); a collection group uses
   `collection_commands` and `collection_group` (`catalog/commands/_collection.py`). A `Param`
   has `name`, `kind`, `flag`, `argument` (the name of the function argument), `required`,
   `task=True` for the options that choose data (they go into the project manifest), `allowed`
   as a provider from the registry (not a copy of the list) and its description. The CLI
   parser, the `COMMANDS` of projects, the MCP schemas and `kartograf commands list` are built
   from it.
2. **Library function** at command level in `kartograf.__all__`: keyword-only arguments, a
   result `Document` with its own schema (the rules of `serialization.py`), a `check_*`
   counterpart, validation without network shared with the download, and `ValidationError`
   with `option` and `allowed`.
3. **CLI handler** in `cli/_handlers.py::HANDLERS` (a collection group: its name in
   `COLLECTION_GROUPS`): `library_arguments(args)` turns the flags into arguments, the handler
   calls the function and prints the result (`--json`: `to_json()`; text: the rendering of
   the document).
4. **Project:** a data command needs an entry in `project/commands.py::COMMANDS`: validation
   without network shared with the download, the calls of the download and of `check_*`, and
   an adapter from the whole result to the pins (`VersionedFile`, with the input and raw files
   where there are any). The task options are the `task=True` params. A new product of an
   existing command needs no new entry.
5. **MCP:** the tool arises from the declaration (`catalog/tools.py`): the description from
   `summary`, `description` and `rules` (at most 600 characters), the schema from the
   descriptions, values, bounds and examples of the options, the annotations from `effects`;
   nothing else is written, and a contract test guards the description.
6. **Tests:** the catalog contract tests (`tests/contract/test_catalog_declarations.py`:
   parser flags equal the catalog, the signature of the function, examples through
   `validate_command`, constraints), a project task test (pin the result, check against the
   pins, restore with the same SHA-256), a CLI = API scenario in `tests/contract/test_parity*.py`,
   the row of the document in `tests/contract/test_json_contract.py` and `--json` in
   `tests/contract/test_cli_json.py`.

---

## 5. How to add a new source or a new country

Checklist using DE (Brandenburg, DGM1) as an example:

1. **Descriptor** in `src/kartograf/sources/registry.py`: `key="de.lgb.dgm1"`,
   `country="DE"`, `product="nmt"`, `provider_name="LGB"`, channels
   (`AccessChannel` with transport, CRSs, `capabilities`, `endpoint`),
   licence, `storage_subdir="nmt/de_bb_dgm1_{vcrs}"`, `default_extension`;
   the key and directory follow the naming convention (section 3.3, rule 10; enforced by
   the registry test). This
   entry alone is enough for the files to land in the correct directory — **zero changes
   in the path code**. If the country introduces a new vertical CRS, add it to
   `_VERTICAL_CRS_CODES` (and, for a family/realisation, also to
   `_VERTICAL_FAMILY`).
2. **`CountryProfile`** in `_COUNTRIES`: code, name, `extent_wgs84`
   and `dataset_keys`. `countries_for_bbox` reads countries from the registry via
   `all_countries()`, so the `--country auto` dispatch starts to see the new
   country without CLI changes. Remember that the envelope is a rectangle (section 4.6).
3. **Sheet/tile parser** in `core/` (if the country has its own sheet system):
   a parser class + a `SheetSystem` entry (`detect`, `path_parts`) in the `SYSTEMS`
   literal in `core/parser_registry.py`; keep the sheet code pattern there as a
   public constant (like `CZ_TM33_PATTERN`/`CZ_SM5_PATTERN`) and import it
   in the parser/index — one pattern per system. Models: `ParserTM33`
   (computable grid) and `SheetIndex.sm5_sheet` (grid requiring an
   index). The `pl1992` fallback must remain last — its `detect` always
   returns `True`, so `detect_system` never returns `None`.
4. **Provider** in `providers/de/`, modelled on `providers/cuzk/`: a generic
   descriptor-driven engine (the equivalent of `CuzkClient` — it knows the URLs
   from `AccessChannel.endpoint`, it knows nothing about sheets or sidecars), a product
   provider on top of it and a `create_*_provider()` factory in `__init__.py` as
   the only place for country defaults. The provider sets `descriptor_key`.
5. **Library dispatch** (ADR-037): for a new country add a lane
   in `download/data.py` (`_dispatch_area` -> the country lane function) and extend the
   validation in `download/options.py` (`validate_request`, `check_per_country`)
   and `download/area.py::pl_only_flags` with the options that do not
   exist in that country; the CLI does not change apart from the flag choices in the catalog declaration
   (`catalog/commands/elevation.py` / `imagery.py`, constants from `download/options.py`). The country scenario goes in `tests/contract/test_parity.py`. Do reprojections locally, with a pinned operation — never via the
   server's CRS parameter (ADR-024).
6. **Tests**: fixtures from REAL server responses (model: `tests/fixtures/cuzk/`),
   a descriptor-provider consistency test, an entry in `KNOWN_PATHS` for every
   CRS pair used together with the expected accuracy, tests of the paths
   of the new segment and a content-after-warp test (vertex position relative to
   the pyproj reference). Tests are offline — `tests/conftest.py` fails every
   test that goes out to the network other than loopback; only tests with the `live`
   marker are exempt (default commands: `-m "not live"`).

When transforming content from/to EPSG:5514/3045, additionally test the
datum step pin (`DATUM_STEP_PINS` EPSG:1622/1623), not only the
nominal `KNOWN_PATHS` accuracy: the Slovak operation has a misleading
0.5 m and may pass the AOI filter in Czechia. The output grid itself
should preserve the exact pixel and the pinned operation in the sidecar.

**A new resolution or format of an existing PL product (NMT/NMPT)** is a
registry entry, not code: one line `_pl_sheet_source(produkt, etykieta,
uklady_wysokosci, format=...)` in `registry.py::_PL_SHEET_SOURCES` (ADR-041,
section 3.1). The descriptor key, segment, extension, validation of
`--resolution`/`--vertical-crs`/`--format`, the `--help` texts,
`list-sources`, the hard filter of the sheet index record, P10 hints
and the availability report combinations read the registry. A new archive format
additionally requires a `FileFormat` entry in `sources/variants.py::FORMATS`
(token, `format` field name, extension, URL endings) and content verification
in `download/campaigns.py::verify_file_format`. A new WCS channel
for an NMT/NMPT cutout is a separate decision — today only the 1 m variants; the
WCS channels of an orthophoto cutout are `WcsCutoutParams` entries (section 3.1, 4.3).

A new **command that writes data** (including `download` of a new group) is a declaration
in `src/kartograf/catalog/commands/<group>.py` (parameters `task=True` = manifest task
options; the CLI parser, project options and MCP schemas are built from it, section 4.11)
and an entry in `src/kartograf/project/commands.py::COMMANDS`: validation shared with the download
without network access, the download function and `check_*`, a result adapter to the full set of
pinned `VersionedFile`s. Add a project task test for this command
(pinning, checking and restoring); a new product of an existing command does not
require a new entry in the table (ADR-040, manifest spec section 5).

**A new land cover or soil provider.** A class in `providers/` (a national one in the
subpackage of its country, `providers/pl/`) derived from `LandCoverProvider`
(`providers/base.py`) that implements the abstract members (`name`, `base_url` and
`download_by_bbox`). `download_by_sheet` is inherited (sheet code, bbox in EPSG:2180,
`download_by_bbox`): override it only when the source has a sheet track of its own;
`download_by_admin_unit` (TERYT) is optional and raises `NotImplementedError` by default.
Then: the descriptor in `sources/registry.py` and `descriptor_key` in the provider (storage
directory and sidecar), the provider in `PROVIDERS` of `landcover/manager.py`, the export in
`kartograf/__init__.py` (`__all__`), offline tests with fixtures recorded from real answers,
and the product in the choices of `--product`: the declaration
`catalog/commands/landcover.py` (`download` and `list-layers`) reads them from the registry
(`LANDCOVER_PRODUCTS`) and `cli/landcover_cmd.py` maps the arguments.

An extension of the **PL sheet parsers** touches `core/sheet_parser.py` for PL-1992 (a
pattern in `PATTERNS`, the division of sheets in `get_children()`) or `core/parser_2000.py`
for PL-2000, and tests of the hierarchy (`get_parent`, `get_children`, `get_all_descendants`)
in `tests/unit/test_sheet_parser.py`, `test_parser_2000.py` and `test_parser_registry.py`.

**A new collection product (ADR-042).** A unit package (county,
voivodeship, national file), area objects from WFS 2.0 / ArcGIS REST or
a file from the CUZK ATOM feed is a descriptor entry with `AccessChannel.params`
(`UnitPackageParams`, `FeatureBBoxParams` or `AtomFilesParams`, section
3.1) - without a provider and without engine code:
segment = `storage_subdir` + variant tokens (section 3.3 rules 9 and 10), the channel
follows from the kind of selection (section 4.10), the sidecar, versions and plan are shared.
Confirm the BBOX axis order (`axis_order`) with a test against a real
service response (swapped axes give an empty result without an error), add the channel
to the inventory of registry test signals, record fixtures from real
responses. CLI: a new group = a module `catalog/commands/<group>.py` with `collection_commands`
and `collection_group` (`catalog/commands/_collection.py`), the group name in `COLLECTION_GROUPS`
(`cli/_handlers.py`) and a project entry (the paragraph above); a new
product of an existing group = only a new `--product` choice from the registry. A new
protocol (e.g. OGC API Features) extends `FeatureBBoxParams.protocol`
together with the first product.

Checklist: (1) the `SourceDescriptor` in `sources/registry.py` (key and `storage_subdir` by
the naming convention of section 3.3 rule 10, enforced by `TestNamingConvention`), or a new
channel of an existing descriptor (the BDOT10k archive). (2) The parameters of the channel:
`url_template` takes only the tokens `{teryt}`, `{woj}`, `{sheet}`, `{ku}` and `{theme}`
(`None`: the URL comes from the index record, `IndexSource`); all variants of a channel have
the same keys in `choice` (for example `("lod", "year")`) and different values; `file_kind`
(`zip`, `tiff`, `pdf`, `txt`) is checked by the first bytes; the protocol agrees with the
transport of the channel (WFS: `wfs`, ARCGIS_QUERY: `arcgis`, OGC_API_FEATURES: `ogcapi`,
DIRECT_FILES: `UnitPackageParams` or `AtomFilesParams`); `url_template` and `endpoint` start
with `https://`; `page_size` is not larger than the page limit of the service
(`CountDefault` or `maxRecordCount`, checked at the download). (3) The channels of one
capability may share a kind (for example a WFS per network) when they declare the same
CRSs: the sidecar reads the CRSs from the first channel of the capability (ADR-043 D6); the
channel and the variant select the values of the options in `choice` (ADR-043 D5); the
`update_signal` follows the signal of the source (`none` for GUGiK packages and WFS results,
`index` for a channel with an `IndexSource`). (4) The inventory of signals in
`tests/unit/test_sources_registry.py` (`CHANNEL_SIGNALS`). (5) Small fixtures from real
answers under `tests/fixtures/` (`feature_bbox/` with `*.headers.json`). (6) A group needs
its `catalog/commands` module, its name in `COLLECTION_GROUPS` and an entry of
`project/commands.py::COMMANDS`.

---

## 6. Decisions (ADR)

The index of decisions with titles, dates and statuses (the "superseded"
and "amended" relations) is maintained in `docs/DECISIONS.md` (section "Index") — this
document does not duplicate it. The sections above refer to ADR numbers and their
errata where they describe the code behaviour that follows from them.
