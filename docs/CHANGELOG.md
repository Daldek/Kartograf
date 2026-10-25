# Changelog

All significant changes to the project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Everything below ships in 0.8.0: the release pull request renames this heading to
`[0.8.0] - <date>` (REL-2.1).

### Nogat standard 2.1 adoption (so far)

**Breaking**

- The `message` and the `hint` of the error document `kartograf-error/1` are English for the
  classes that already moved into the message catalog: the hints of an invalid argument
  (`Allowed values of --product: a, b. Example: kartograf ...`, `Options: --sheet, --bbox.`), of
  a wrong command line (`The options of the command: ...`), of a sheet code (`Sheet code
  formats: ...`), of the cache, of a sidecar and of an I/O or internal error, and the messages
  `interrupted (Ctrl-C)` and `terminated (SIGTERM)`. The text mode of the CLI prints them in
  Polish by default (`--lang pl`); the last line of stderr is always English. The other
  library texts follow area by area (ADR-053, PROGRESS Next 25); a client that matched the
  Polish `hint` matches the English one or the `code` and `details`.
- The library texts of the areas that moved into the message catalog are English by default and
  Polish with `--lang pl` (ADR-053), area by area: the sheet code parsers and geometry readers
  (`core`), `sheet_info`, the argument conversion (`catalog/kinds.py`) and the bbox check
  (`Invalid bbox: <reason>. Expected: ...` is one catalog message), the CRS transformations and
  the GeoPackage writer (`transform`), the transport engines, the metadata cache and the CLMS Auth
  Proxy (`transport`, `cache`, `auth`), the providers (`providers`: GUGiK, CUZK, CORINE and
  SoilGrids), the source registry, the hydrologic soil groups and the land cover orchestration
  (`sources`, `hydrology`, `landcover`) and the text the CLI prints for a person (`cli`: tables,
  status lines and notes; `--lang en` prints English, the default stays Polish), the command
  catalog (the declarations of `catalog/commands/*`, the section titles and placeholders of
  `--help`, the text of `commands list` and `commands schema` and the usage errors of the parser:
  `<group> <command> --help --lang en` prints English; the message of a usage error and of the
  unknown command of `command_schema` is English in the error document), the command
  layer, the store read API with the names of its segments, the cache, source and layer documents,
  the fixture builders (the root modules; the `directory` of a source is `<crs>` and
  `<vertical-crs>`; `kartograf-mcp` says English only and has no `--lang`), the downloads
  (`download/*`: the registry texts that the help lists are catalog messages too, so the Polish
  help is Polish where English leaked; `notices.size_text` and `names_text` return catalog
  messages and `notices.count_text` with its noun tables is gone; the error of a failed unit is
  English in the report and Polish at the terminal) and the projects (`project/*`: the checks of
  the manifest, the lock, the operations and the data commands of the tasks; the problems and
  the details of a task are English in the result and Polish at the terminal). A client that
  matched the Polish text matches the English one or the `code` and `details`.
- The package lives in `src/kartograf/` (ECO-011). Import paths do not change;
  repeat an editable install made before (`uv sync --locked --all-extras`).
- `kartograf.__version__` is `0.8.0.dev0` on `develop` (REL-1.1); the release
  pull request sets `0.8.0`. A requirement `kartograf>=0.8.0` does not accept the
  development version: pin the commit until the tag exists.
- The `dev` extra is the `dev` dependency group; environments are installed with
  `uv sync --locked --all-extras` from the committed `uv.lock` (DEV-6.2, DEV-6.3).
- `docs/DECISIONS.md` has LF line endings (DEV-14.1).
- Error codes and exit codes follow the Nogat registry (ERR §4, ADR-049). `code` of
  `ValidationError`, `UsageError` and `ParseError` is `validation_error` (exit 2) with
  `details.reason` `invalid_input`, `usage` and `invalid_sheet_code`; `NoCoverageError`
  and `YearRangeError` are `no_data` (exit 14, reasons `no_coverage` and
  `year_out_of_range`); `DownloadError` is `source_unavailable` (5); `CacheError` is
  `store_unavailable` (reason `cache`, 8); `InvalidSidecarError` is `data_error` (reason
  `invalid_sidecar`, 7); `TransformError` is `calculation_error` (reason
  `transform_failed`, 13); `TransformUnavailableError` is `unsupported` (reason
  `transform_unavailable`, 15); `OSError` is `io_error` (9); Ctrl-C is `cancelled` (130);
  `KartografError` itself is `internal_error` (1). The codes `invalid_input`,
  `usage_error`, `invalid_sheet_code`, `download_failed`, `no_coverage`,
  `year_out_of_range`, `cache_error`, `invalid_sidecar`, `transform_failed`,
  `transform_unavailable`, `kartograf_error` and `interrupted` no longer exist, and
  every CLI error exits with the registry exit code of its code instead of 1. Consumers
  that compared `err.code` (Retman: `no_coverage`) read `err.code` and `err.reason`, or
  catch the class.
- The document `kartograf-error/1` follows AGI-4.3: keys `code`, `title`, `message`,
  `hint`, `details`, `exit_code`, `command`. The `exception` key is removed, `hint` and
  `command` are left out when there is none, and `details` always exists with `reason`
  first (`ErrorReport.exception` is gone, `ErrorReport.title` is new).
- The default metadata cache is `<cache_dir>/kartograf/metadata.db` (by default
  `~/.cache/nogat/kartograf/metadata.db`) for the CLI, the library and the MCP server
  (ADR-050, DEV-18.2). Nothing is written to the current directory any more:
  `<cwd>/.kartograf_cache.db` and the former cache file of the MCP server
  (`~/.cache/kartograf/metadata.db`) are not read; delete them (the cache holds lookups and
  is rebuilt on demand). `kartograf cache path` (`get_cache_path`) says where the file is;
  `kartograf.cache.defaults.DEFAULT_CACHE_FILENAME` is `CACHE_FILENAME` (`metadata.db`).
- Every CLI command except `config show`, and the start of `kartograf-mcp`, stop with a
  `ConfigError` (`validation_error`, exit code 2, `details.reason` `invalid_config`) when
  `nogat.toml` cannot be used (unreadable, not UTF-8 text, invalid TOML, a section that is
  not a table, or missing when `NOGAT_CONFIG` names it) or `lang` is not `pl` or `en`.
  `KARTOGRAF_DEBUG=0` (and `false`, `no`, `off`) is now off; any other non-empty value is on.
- `platformdirs>=4` is a dependency.
- Every command id is `<group> <verb>` (AGI-2.2, the `command` of the result envelope):
  `kartograf parse` is `kartograf sheet parse`, `kartograf catalog` is
  `kartograf commands list`, `sheet find` is the former `find_sheets` and `store overview`,
  `store entries` and `store sidecar` are the former `store_overview`, `store_entries` and
  `store_sidecar` (commands that only the API had: they have a CLI now, see Added). The CLI words, the catalog ids
  (`get_catalog(command=...)`), the `command` of `kartograf-error/1` and the hints that
  name a command change; the library functions are unchanged (the MCP tools are renamed, see
  below).
- A notice is `{level, code, message}` in every document and in `kartograf.notices.Notice`
  (the AGI-4.2 notice): the key and the attribute `text` are now `message` (the same word
  as in `kartograf-error/1`); the text itself is unchanged (Polish ASCII until the message
  catalogue). `kartograf-plan/1` documents saved before this change (`--plan FILE`) have
  `text` in their notices and are rejected: write the plan again with `--check-updates`.
- `kartograf-availability/1` has the new key `failed` (before `notices`): the countries a
  `--country auto` check could not examine, as `UnitFailure` (`unit`, `country`, `error`,
  `kind`); it is `[]` when `ok` is true.
- Every `--json` output and every MCP result is the result envelope `kartograf-result/1`
  (AGI-4.2, ADR-051): `tool`, `version`, `command`, `check`, `status`, `result` (the document
  that was printed before, with its own `schema`), `items` (one entry per unit of a batch) and
  `notices`. Consumers read the old document from `result` (Retman, Archiwista).
- A result with `ok: false` exits with 10 (`partial`: a unit succeeded) or 11 (`failed`: none
  did) instead of 1; exit code 1 is only `internal_error`. The MCP server returns such a
  result without `isError`; only an error document is an error (AGI-5.7).
- The error document `kartograf-error/1` is the last line of stderr in both modes (AGI-3.3,
  compact and ASCII); with `--json` it is no longer on stdout, which stays empty. A syntax
  error of argparse in text mode ends with it too.
- `run_command` and `check_command` return `CommandResult` (the envelope); the report is
  `.result`, and `run_command(plan=)` takes `check_command(...).result`.
- The command catalog is the documents `kartograf-command-list/1` and `kartograf-commands/1`
  (AGI-2.4, ADR-052). `kartograf commands list` takes no argument and prints the list: the groups
  with their products and every command with its `operation_id`, summary, MCP families,
  `read_only` and `check`. `kartograf commands schema --command "<group> <verb>"` prints one
  command (Nogat `commands-1`): its options with allowed values and their meanings, result,
  effects, rules, examples with a result excerpt, errors and the Polish texts in `i18n.pl`.
  `get_catalog`, `data_commands`, `Catalog`, `CommandInfo`, `ParamInfo`, the document
  `kartograf-catalog/1` (its views, `--params`, `group`, `params` and `tables`, the tables of exit
  codes, error codes and schemas) are removed: migrate to `list_commands()` and
  `command_schema(command)`; the twelve data commands are the values of `project add --command`
  (`project_task` in the declarations). The hint of a usage error says
  `kartograf commands schema --command "<id>"`.
- The MCP server refuses a path outside `--allow-dir` with the registry code `forbidden`
  (exit code 12 in the error document) instead of `validation_error`, and `kartograf-mcp`
  without the `mcp` package ends with `missing_dependency` (exit code 6, the error document as
  the last line of stderr, hint `uv add "kartograf[mcp]"`) instead of a text line and exit code
  1; `create_server` raises `MissingDependencyError`, not `ImportError`, and
  `kartograf.mcp_server.INSTALL_HINT` is gone.
- The MCP server is rebuilt on the catalog (ADR-052, AGI section 5). The 29 tools with the old
  names are gone without aliases; there is one tool per command of the catalog that has a family,
  39 of them, named by the `operation_id` `kartograf_<group>_<verb>`: `elevation_download` is
  `kartograf_elevation_download`, `parse_sheet` is `kartograf_sheet_parse`, `find_sheets` is
  `kartograf_sheet_find`, `commands_list` is `kartograf_commands_list`, `commands_schema` is
  `kartograf_commands_schema`, `store_overview` is `kartograf_store_overview`, `project_status` is
  `kartograf_project_status`, and so on; `list_sources` and `list_layers` with a `group` argument are
  one tool per group (`kartograf_<group>_list_sources`, `kartograf_landcover_list_layers`,
  `kartograf_soil_list_layers`). The tools `check_updates` and `project_check_updates` and the family
  `check` are gone: the check is the argument `check_updates` of each tool that writes and has a plan.
  `--tools` takes `discovery`, `availability`, `data`, `project`, `store` and `core` (the ten tools of
  the main tasks).
- The MCP server is read only by default (AGI-1.3). Without `--allow-writes` a tool that writes and
  has a plan (the twelve data commands and `project download`) is offered as its plan-only variant:
  no `update`, `plan`, `workers` or `summary`, `check_updates` fixed to `true`, `readOnlyHint: true`,
  and a call is the plan; `project init`, `project add` and `project remove` are not offered and
  answer `forbidden` (12), as does an option of a run. Before, every data tool downloaded. Start
  `kartograf-mcp --allow-writes --allow-dir DIR` to download inside `DIR`; `--allow-writes` needs
  `--allow-dir` (usage error, exit code 2).
- Every MCP tool has an `outputSchema` (the result envelope `kartograf-result/1`, self-contained) and
  the annotations `title`, `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint`,
  all set; `kartograf_commands_list` and `kartograf_commands_schema` carry
  `_meta["anthropic/alwaysLoad"]`. The descriptions, the descriptions of the properties (the texts of
  the catalog) and the server instructions are English, within 600 and 4,096 characters. `tools/list`
  is about 207,000 characters, not 30,000 (ADR-052, decision 9): a client that loads every
  definition should start the server with `--tools core` (64,000). `kartograf.catalog.tools` has
  `tool_specs(families, *, allow_writes)` and `hidden_tools`; `Command.tool` and
  `check_arguments_schema` are removed; `kartograf.mcp_server` has `build_instructions`, and
  `create_server(allow_writes=)` raises `ValidationError` (not `ValueError`) for an unknown or empty
  family, a relative `allow_dirs` entry and `cache=True`.

**Added**

- The message catalog `kartograf.messages` (ADR-053): `message(key, lang="en", **values)`
  renders a `Text(en, pl)` entry of `kartograf.messages.<area>` as a `Message`, a `str` that
  remembers its key and values (`Message.localized(lang)`, `localize`, `reason`), with counted
  nouns written `{n:plural(file|files)}` and lists written `{items:join}`. `KartografError.localized(lang)`,
  `Notice.localized(lang)`, `error_report(exc, lang=)`, `config.human_language` and the
  CLI-only option `--lang pl|en` of every command (after it `KARTOGRAF_LANG`, `NOGAT_LANG`,
  `nogat.toml`, then `pl`) follow it. `tests/unit/test_messages.py` checks every entry,
  every `message(...)` call and the Polish literals that remain outside the catalog
  (`_PENDING`, shrinking area by area).
- `kartograf commands guide --format agents|llms|agents-md-block` (library: `agent_guide`,
  the document `AgentGuide` = `kartograf-guide/1` with `format` and `text`) renders the guide
  for AI agents of AGI section 8 from the command catalog, the error registry and the
  templates `src/kartograf/_data/agents/*.md` (packaged); it is offline, English and the same
  in every interface (AGI-3.8, AGI-8.1, AGI-9.2). `--inject FILE` (CLI only) puts the compact
  block of `agents-md-block` (at most 60 lines, between `<!-- BEGIN kartograf -->` and
  `<!-- END kartograf -->`) into the `AGENTS.md` of a repository that uses Kartograf, the same
  way every time (AGI-8.2); `kartograf.guide.inject_block` is the text part of it. The
  command has no MCP tool, and `kartograf mcp` (AGI-3.8) is not added: `kartograf-mcp` stays
  the entry point of the server (ADR-052, decision 10).
- `list_commands()`, `command_schema(command)` and the documents `CommandList` and
  `CommandCatalog` (AGI-2.1, AGI-2.4): `command_schema` takes the name of a command or its
  `operation_id` (`kartograf_<group>_<verb>`). `validate_command`, `check_command` and
  `run_command` keep `(command, options, *, output_dir)` and the twelve data commands (ADR-052).
- `kartograf sheet find`, `kartograf store overview`, `kartograf store entries` and
  `kartograf store sidecar`: the CLI of the four commands that only the API had
  (`find_sheets`, `describe_store`, `list_store_entries`, `read_store_sidecar`), so that every
  command of the catalog has a CLI form and an example call (AGI-1.2, AGI-2.2). The store reads
  take the store with `-o`/`--output` like the data commands (the data-output change renames it).
- `<group> list-sources --product PRODUCT` (the `product` argument of `list_sources` had no flag).
- The command declarations of the catalog (`kartograf.catalog.commands`) carry what AGI-2.2 and
  AGI-2.3 ask of a command and its options: English `summary`, `description`, `rules`, option
  descriptions and example titles, the Polish ones next to them in the fields ending in `_pl`
  (`--help` and the text of the CLI are unchanged), the registry `errors` a command can raise,
  its MCP `family` and `core` mark, `cardinality`, and per option `unit`, bounds, `path_role` and
  `examples`; `kartograf.catalog.meanings` gives every allowed value its English meaning and
  `kartograf.catalog.excerpts` the excerpt of each result document for the examples. Every command
  has a CLI form (`Command.cli` is gone). The catalog documents that publish them follow in the
  next step.
- `kartograf config show [--json]` (library: `get_config`, `Config`) reports the settings in
  force: `nogat.toml`, every key (`root`, `data_dir`, `cache_dir`, `lang`, `debug`) with its
  value and source, `CLMS_CREDENTIALS` as present or missing, and the store root with its size
  (hard links counted once); the document is `kartograf-config/1` (ADR-050, DEV-18.6).
- Settings from `nogat.toml` (`[kartograf]`, then the shared `[nogat]`) and the variables
  `KARTOGRAF_ROOT`, `KARTOGRAF_DATA_DIR`, `KARTOGRAF_CACHE_DIR`, `KARTOGRAF_LANG`,
  `KARTOGRAF_DEBUG`, `NOGAT_DATA_DIR`, `NOGAT_CACHE_DIR`, `NOGAT_LANG` and `NOGAT_CONFIG`
  (DEV-18.1); `root` is only reported until the data-output change, and `lang` takes effect
  with the message catalogue. `.env.example` and the README list every variable and give the
  backup notes for a store (DEV-18.3, DEV-18.5).
- `ConfigError` (a `ValidationError`, reason `invalid_config`).
- `ForbiddenError` (`forbidden`, exit code 12: details `option`, `path`, `allowed`) and
  `MissingDependencyError` (`missing_dependency`, exit code 6: details `extra`, hint `uv add
  "kartograf[<extra>]"`), exported from `kartograf` and listed in the error table of USAGE 9.3
  (ERR §2, DEV-6.5). Only the MCP server raises them.
- `kartograf-mcp --allow-writes` (the server says everything in English, AGI-9.2, so it has no
  `--lang`); `scripts/generate_output_schema.py` and the generated module
  `kartograf._output_schema`; the gate test of AGI-5.13 (the server over stdio with the SDK
  client: names, annotations, schemas, budgets, cold start under 5 seconds, a read-only call, a
  validation error with the code and the hint).
- `UnitFailure.code` and `UnitFailure.reason` (the registry code and `details.reason` a
  failed unit stands for: `no_coverage` and `year_out_of_range` are `no_data`, `download`
  and `country` are `source_unavailable`; `kartograf.download.data.FAILURE_CODES`),
  `PlanItem.store_path` (the path of a position below the store, the subject of a plan
  line) and the public `kartograf.download.data.failure_kind`.
- `kartograf.envelope` (`CommandResult`, `ResultItem`, `wrap`, `outcome_of`, `exit_code_of`):
  the status and the units of each document with a verdict; `TaskResult.code` and `.reason`
  (the registry code of a failed task of `download_project`) and `kartograf._errors.OUTCOMES`
  with `OUTCOME_MEANINGS` (the exit codes 10 and 11 are in the table of USAGE 9.3).

- `kartograf.testing`: `build_fixture_store`, `build_project` and `make_sidecar`
  build offline fixtures of the store, the project manifest and the
  `kartograf-meta/1` sidecar with the real writers (DEV-10.6).
- The Nogat gate (`scripts/gate.sh`, `scripts/check-commits.sh`), CI, live-test
  and Dependabot workflows (DEV-7.6, DEV-7.7, DEV-13.6).
- `schemas/nogat/` (copies of the Nogat error registry and agent schemas) and
  the generated module `kartograf._errors` (ERR-3).
- `KartografError.reason` (class attribute, reported as `details.reason`) and
  `ErrorCodeInfo.reason` in the catalog tables.
- `scripts/generate_docs.py` writes the exit code and error code tables, the table of the MCP
  tools and the instructions of the server in `docs/USAGE.md` 9.3 and 9.6 from the code
  (DOC-9.4); a contract test checks them.

**Changed**

- `pyproject.toml` has the discovery metadata of AGI-10.1: `[project.urls]` with `Homepage`,
  `Source` (was `Repository`), `Documentation`, `Changelog` and `Issues`, and the classifier
  `Topic :: Scientific/Engineering :: Hydrology`; `twine check` passes on the built distribution.
- Docstrings follow the numpy convention (ruff `D`) and `mypy --strict` passes
  over `src` and `tests` (DEV-7.2, DEV-7.3); coverage floor 80 (DEV-7.5).
- `tests/` is split into `unit`, `integration`, `contract` and `support`.
- The living documents `docs/DECISIONS.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `USAGE.md`,
  `SCOPE.md` and `PRD.md` are written in English (ECO-005, DEV-2.1): the same sections and
  numbering, the identifiers, flags, schema names, error codes and the Polish text that the
  tool prints are unchanged, and a Polish name that has no English one (sheet code, voivodeship,
  county, municipality, sheet index, NMT, NMPT) is glossed at its first use. Headings are
  English, so every link of the form `file.md#anchor` to a heading of these documents has
  the English anchor (`USAGE.md#96-mcp-server`, `ARCHITECTURE.md#36-json-documents-kartograf-1`);
  the tests that look up a section by its title use the English title. The records of past
  investigations (`docs/research`, `docs/superpowers`) are still Polish.
- `llms.txt` is generated (`kartograf commands guide --format llms`) and English: the layout
  of llmstxt.org (a summary, then link lists with raw links, at most 8,000 characters before
  the first list; DOC-5.1, DOC-5.2). `AGENTS.md` is new (at most 200 lines and 16 KiB;
  DOC-4.2). Both are derived files: `tests/contract/test_agent_guide.py` (in place of
  `tests/contract/test_llms_txt.py`) compares them with the generator byte for byte, keeps
  them within the budgets of DOC-1.7 and checks that the parser of the CLI reads every
  command line of them. Regenerate them after a change of the catalog, the error registry
  or the templates (USAGE 9.7).
- The rule of `CLAUDE.md` for the agents of other repositories no longer says "do not create
  `AGENTS.md`": the generated `AGENTS.md` and `llms.txt` are the interface of an agent that
  uses Kartograf.
- `README.md` is English and follows the 14 sections of DOC-2.1 (at most 400 lines, a summary of
  at most 400 characters, absolute links, an Install line per interface from Git, a Quick
  start with the shape of every output, a Capabilities table, MCP configuration for Claude
  Code, Cursor, Codex and VS Code, Related tools, the five most common errors and the table
  of variables with the backup notes). `tests/contract/test_readme.py` checks the order, the
  budgets, the links, the names in the table, and runs every example: the command lines as
  written, the Python blocks and the MCP call, against the fake index of the download tests.
- `CLAUDE.md` is English within 200 lines and follows DOC-3.1: critical rules, rules for
  code, environment and commands, the rules for agents of other repositories, a code map, a
  documentation map, the session workflow, the link to the entry of Kartograf in the Nogat
  `ecosystem.yaml`, and a `Deviations` section (DEV-1.2). Its section for other repositories is
  "Rules for agents of other repositories" (it was "Agenci z innych repozytoriow").
- `docs/DEVELOPMENT_STANDARDS.md` is deleted (DEV-1.3: a project holds no copy of the Nogat
  standard). Its project rules are in `CLAUDE.md`, and its recipes for a new command, a land
  cover provider, a PL sheet parser and a collection product are in `docs/ARCHITECTURE.md`
  4.11 and 5. Entries of this changelog and of `docs/DECISIONS.md` that cite
  `DEVELOPMENT_STANDARDS` or `STANDARDS x.y` cite the deleted document (ADR-009 is
  superseded by ADR-048).
- `llms.txt` no longer calls the README Polish.

**Fixed**

- A CRS label with surrounding spaces (`" EPSG:5514 "`) no longer fails in the
  pinned transform with PROJ 9.8.

### Data output (ADR-054)

The Nogat convention ECO-051 / DEV §19 gives every writing command two modes: plain files with
`--output-dir` (`-o`) and the versioned store with `--root`, and the default store when it
names neither. The entries below are the steps of the branch `feature/data-output`, one commit
each; "Migration guide: data output" at the end of this section lists what a caller changes.

**Breaking**

- A parameter that names a store root is `root` (ADR-054 decision 1): the download and check
  functions of every track, `DownloadManager`, `LandCoverManager`, `HSGCalculator`,
  `run_command`, `check_command`, `validate_command`, `init_project`, the read API
  (`list_segments`, `list_partitions`, `iter_store`, `describe_store`, `list_store_entries`),
  `Project.root`, the `root` key of `kartograf-project/1`, `StoreOverview.root` and
  `StoreEntries.root`. The CLI flag of the store is `--root`; `-o` and `--output` as a store
  root are gone, without an alias (`output_dir` and `-o` are reserved for the plain directory
  of the next steps). The layout, the sidecars and every result are unchanged. Consumers:
  Archiwista (`Project.root`, the read API names, the manifest key), Retman (`root=` in
  `validate_command`, `run_command`, `check_command` and `DownloadManager(output_dir=...)`),
  Hydrograf (`DownloadManager(output_dir=...)` in `backend/scripts/download_dem.py`).
- `DownloadManager(provider, *, root=None, ...)`, `LandCoverManager(provider, *, root=None,
  cache=True)` and `HSGCalculator(provider=None, *, root=None, cache=True)` take the provider
  first and the store as the keyword `root` (ADR-054 decision 1, DEV-19.1: the target options are
  keyword-only): `DownloadManager(tmp, provider)` is now `DownloadManager(provider, root=tmp)`.
- A call without a store works on the default store (ADR-054 decision 2, DEV-19.2): `root` is
  optional in every function, command, `kartograf-project/1` (`project init`) and tool, and `--root`
  in every command. The default is `KARTOGRAF_ROOT`, `[kartograf] root` of `nogat.toml`, else
  `<data_dir>/kartograf` (`kartograf.config.resolve_root`); a command that used to fail with
  "`--root` required" now writes there. `project init` writes the default root, as an absolute
  path, into the manifest. The MCP server accepts a call without `root` only when the default
  store lies inside `--allow-dir` (`forbidden` otherwise). An empty `root` is a
  `validation_error` (`option` `root`), not the default.

- The store has a marker, `kartograf-store.json` (ADR-054 decision 8, DEV-19.12 to DEV-19.14;
  schema `kartograf-store/1` with `schema`, `tool`, `created_at`, `producer_version`). The
  first publication of a version into a new root, or one without a file, writes it
  (`kartograf.marker.prepare_store`); a download that fails leaves none behind. The checks run
  before the first byte of a write and of a plan (`--check-updates` creates nothing): a root
  that has the layout of a store (files in `nmt/`, `laz/`, `hsg/`..., of this version or of
  0.7.x) and no marker is `store_unavailable` (`details.reason` `no_marker`, hint `kartograf
  store init --root DIR`); a root that holds other files is `conflict` (`not_empty`); a store
  never nests in another store of any tool (`nested_store`: markers of the ancestors, of the
  root and below it, found by file name alone). `kartograf.testing` builds its stores with the
  marker. The first write into an existing 0.8.0-dev store, or into a directory that holds
  other files (a project folder, a cache), now fails: run `kartograf store init --root DIR` on
  the store, or give a new or empty directory.
- `kartograf store init [--root DIR]` (`init_store`, MCP `kartograf_store_init`, document
  `kartograf-store-init/1`) writes the marker of a store; a root that has the layout and no
  marker is verified first (the top level holds product directories of Kartograf only and every
  sidecar is `kartograf-meta/1`: `data_error`, `invalid_layout` with `details.problems`) and its
  files are not touched. It is a command that writes: a server that does not write
  (`--allow-writes`) does not offer the tool.
- Errors: `ConflictError` (registry `conflict`, exit code 4; `details.reason` is set per
  instance: `nested_store`, `not_empty`), `StoreUnavailableError` (`store_unavailable`, reason
  `no_marker`) and `InvalidLayoutError` (`data_error`, `invalid_layout`); `KartografError`
  takes `reason=` for the classes that have several.
- `kartograf-meta/1` gains the optional `producer` (`kartograf`) and `producer_version`
  (ADR-054 decision 9, DEV-19.16) beside `kartograf_version`, which stays; nothing is renamed.
  Every sidecar the writers produce has them, the bare sidecar of a provider without a
  descriptor too. The typed `Sidecar` of the read API has both fields; a sidecar written
  earlier has neither key, and the view reports `kartograf` and the value of
  `kartograf_version` (`raw` stays as it is).
- `--check` replaces `--check-updates` (ADR-054 decision 6, DEV-19.10, AGI-3.4): the CLI flag of
  every command that plans, the library and catalog option (`check` instead of `check_updates`
  in `parse_command`, `format_command`, `run` of the pinned command lines), the argument of the
  MCP tools (`check: true` plans without writing) and the project commands. The plan is the
  same document (`kartograf-plan/1`), and no alias is kept. Consumers that pass `check_updates`
  to an MCP tool or `--check-updates` to the CLI change the name.
- The engine of plain output, `kartograf.output` (ADR-054 decision 3, DEV-19.4 to DEV-19.11; the
  library only, no command uses it yet): `resolve_target(output_dir=, root=)` (both given is
  `validation_error`, `details.reason` `exclusive_options`; neither is the default store),
  `plan_plain` and `refuse` (the target list is checked as a whole before the first byte:
  `duplicate_output_name`, `output_in_store`, `output_exists`, every offending path in
  `details.paths`), `Staging` (`<dir>/.kartograf-incoming/<host>_<pid>_<token>/`, one chunked read
  for size and SHA-256, `os.replace`, removed on success, error, SIGINT and SIGTERM, leftovers
  over 24 hours removed by the next run) and `FileResult`. `ValidationError` takes an instance
  `reason`.
- The reports of `kartograf-download/1` list `files[]` as DEV-19.19 says (ADR-054 decision 10):
  `{unit, country, path, size_bytes, sha256, status}`, in the store with `label` and
  `version_path` (`path` stays the standard path) and with `newer`, `unverified`, `same_as` when
  set, instead of `files[].file.{path, status, label, ...}`; the same for `raw[]` and `inputs[]`.
  The status in the document is `new`, `unchanged` or `relabeled`: the file statuses `local` and
  `reused` are `unchanged` there, and the Python attribute `VersionedFile.status` keeps both
  words. `VersionedFile.size_bytes` is new (and `local_file`, `committed_file` build the
  outcomes of the tracks). The reports also have `mode`, `root`, `output_dir` and `skipped[]`
  (`{id, reason, message}`, filled by the plain mode of the next steps); `kartograf-plan/1` has
  `mode`, `root`, `output_dir` (its key `store` is `root`: a plan file of 0.8.0-dev is not read,
  make a new one) and its items `action`, `path`, `reason` (plain plans). The Python attributes
  `item.file.path`, `.status`, `.label` are unchanged. Consumers: Hydrolog and Hydraulik read
  `files[].path`, Archiwista and Retman the report of a download.
- Plain mode at the seam of the tracks (ADR-054 decision 3, DEV-19.4 to DEV-19.9): the download
  and check functions of `laz`, `cz_laz`, `cz_sheets`, `cz_contours`, `cz_cutout`, `cutout` (PL
  WCS), `orto_cutout` and `cz_orto` take the keyword `output_dir` beside `root` and write ordinary
  files, named as in the store, into that directory: no sidecar, no version, no link, no
  `versions/`. The targets are checked as a whole before the first byte (`conflict`:
  `duplicate_output_name`, `output_in_store`, `output_exists`, every path in `details.paths`);
  `update="force"` replaces existing files, each with `os.replace`; `update="upgrade"`, `plan`
  and `all_campaigns` are `validation_error` `store_only_option` (hint `--root`). The files go
  through `<output_dir>/.kartograf-incoming/<host>_<pid>_<token>/`, which is created at the first
  transfer and removed on success, error, SIGINT and SIGTERM. `download_data(output_dir=)` and
  `check_data(output_dir=, force=)` run the check of the whole request first, so a request over
  two countries is judged as one list; the reports have `mode` `plain`, `output_dir` and the
  file statuses `written` and `replaced`, and a check lists `action`, `path` and `reason` of each
  target (a conflict is a result).
- PL sheets in plain mode (ADR-054 decision 5, DEV-19.4; adopted from D12 and D13 of the
  template branch): `DownloadManager(provider, output_dir=...)` and `download_data(output_dir=)`
  write one file per sheet, `<sheet>.<ext>`, taken from the newest flight DECLARED FULL
  (`full_sheet is True`) within the year bounds, not the newest flight: a file in a plain
  directory has no sidecar that says it is partial. A sheet that has flights in the range and
  none of them full is left out: a `warning` notice `skipped_incomplete` names the sheets (the
  first ten) and the hint `--root`, `skipped[]` lists `{id, reason, message}` for each, and
  `DownloadResult.incomplete` maps the sheet to its newest partial flight; the other sheets are
  written. When every sheet is left out the command fails with `no_data`, `details.reason`
  `skipped_incomplete` (a failed unit per sheet, exit 11; `check` raises the same
  `NoCoverageError(reason="skipped_incomplete")`). The year options filter the flights as in the
  store, with the same `YearRangeError`; `--full-sheet` is an `info` notice
  `full_sheet_redundant` and has no effect; `all_campaigns` is `store_only_option`. The rule
  applies to plain mode only. `DownloadResult` has `written`, `replaced` and `incomplete`,
  `YearRangeCheck` and `SheetInspection` an `incomplete` entry, and `NoCoverageError` takes an
  instance `reason`.
- Plain mode of the collections, land cover, soil and HSG (ADR-054 decisions 3, 11 and 12):
  `download_collection`, `download_landcover`, `download_soil`, `calculate_hsg` and their
  `check_*` twins take `output_dir` beside `root`; the `check_*` functions also take `force`, so
  that a plan lists `replace` for an existing file (in the store `force` of a check has no
  effect). `LandCoverManager(provider, *, root=None, output_dir=None, cache=True)` and
  `HSGCalculator(provider=None, *, root=None, output_dir=None, cache=True)` take it too. A unit
  is one file, `<unit><ext>`, in one flat directory (`0208.zip`, `1465.gpkg`,
  `<coordinates>.tif`); the request is judged as a whole before the first byte, as for the
  other tracks. BDOT10k with `keep_raw` writes the GPKG and the original package, `<teryt>.gpkg`
  and `<teryt>.zip` (`raw[]` lists the ZIP; no sidecar says which package a GPKG came from).
  SoilGrids and CORINE files have no edition label in plain mode, and no edition is asked.
  `calculate_hsg(output_dir=)` fetches the clay, sand and silt inputs into private directories
  of the staging directory (`Staging.scratch`) and writes only the HSG raster, named as in the
  store: `inputs[]` is empty, nothing is reused, and its plan has the one target without
  asking the source. `kartograf.output.writes` (the decorator the managers share),
  `report_target` and `unit_of` are new.
- The two targets in every interface (ADR-054 decisions 1, 11, 13 and 14): `output_dir` (`-o`,
  `--output-dir`, path role `output`) and `root` (`--root`, path role `root`) are one optional
  `one_of` group `target` of the catalog entry of each of the twelve data commands
  (`elevation`, `imagery`, `landcover`, `soil` and `soil hsg`, and `boundaries`, `cadastre`,
  `models3d`, `hydro`, `names`, `maps`, `geodesy` `download`); neither writes the default store.
  The CLI, `run_command`, `check_command` (which also takes `force`), `validate_command`, the
  project task functions and the MCP tools pass them to the library, which checks the pair:
  both is `validation_error` (`exclusive_options`, `details.option` `root`, `details.options`
  `["output_dir", "root"]`; the parser does not exclude them, so every interface answers with
  the same document). With `output_dir`, `--upgrade`, `--plan` and `--all-campaigns` are
  `store_only_option` naming `--root`; `--check --force` is a valid plan that lists `replace`,
  `--check` and `--upgrade` still exclude each other in the parser and `--upgrade --force` is
  one error line (exit 2). `project *` and `store init` are store-only and say so in their
  catalog entry (rule `Store only: ...`); a project task takes no `output_dir`. The CLI prints
  the status words `zapisano` and `zastapiono` (`written`, `replaced` with `--lang en`) and the
  summary `Zapisane: N, zastapione: M, bledy: K (DIR)` (`Written: N, replaced: M, errors: K
  (DIR)`) for a plain write, and the plan lines `do zapisania`, `do zastapienia (--force)` and
  `konflikt: ...` (`to write`, `to replace (--force)`, `conflict: ...`); they are catalog
  messages (ADR-053). The catalog texts, `AGENTS.md`, `llms.txt`, the MCP instructions and
  `docs/USAGE.md` describe both modes.
- MCP (ADR-054 decision 13, DEV-19.3): `output_dir` is checked like every path (absolute, inside
  `--allow-dir`: `forbidden`, `details.reason` `outside_allowed_dirs`); the default store is
  checked only when the call names neither target; `check` with `update=force` plans the
  replacement on a server that writes, and a server that does not write answers `forbidden`
  (`details.reason` `writes_disabled`) to any option of a run, as before.
- A real command that is interrupted (tests drive `kartograf elevation download --output-dir` in
  a process of its own): SIGINT ends it with exit 130 (`cancelled`) and SIGTERM with 143
  (`terminated`), the staging directory is gone and a target that existed with `--force` is
  whole; a plain write needs no hard link and no symlink.
- The command layer drives every command of the catalog (AGI-2.1; ADR-052 erratum 1, which closes
  the gap that decision 6 of ADR-052 and decision 14 of ADR-054 kept open): `parse_command`,
  `validate_command`, `format_command`, `run_command` and `check_command` take any command of
  `kartograf commands list`, by its name or its `operation_id`, not the twelve data commands
  only. Nothing there knows a command by name: the function, its arguments, the required options,
  the allowed values, the bounds of an integer, the rules among the options (`one_of`, `requires`,
  `excludes`) and the `check_*` twin come from the declaration (`Command.call_options`,
  `kartograf.catalog.arguments.check_call`); the twelve data commands keep the validation of
  their own function. The options of a call are the keys of `kartograf commands schema`; `root`,
  `output_dir`, `update`, `plan`, `workers` and `summary` are given by name beside them, and a
  command that has no such option refuses it (`validation_error`, `details.option`; `output_dir`
  for a command that works on a store only is `store_only_option`). A read-only command returns
  its document in the envelope `kartograf-result/1` (the one the CLI `--json` prints, compared in
  `tests/integration/test_commands_catalog.py` for every command that runs offline), `store init`
  writes the marker, `project init`, `project add` and `project remove` change the manifest, and
  `project download` takes the metadata cache like the data commands. `check_command` of a
  command that has no check is `validation_error` (`details.reason` `no_check`, `details.option`
  `check`), as in Hydrolog and Retman; it returns `CommandResult[UpdatePlan | ProjectCheck]`. An
  unknown command is `validation_error` with `details.allowed` the 45 names. `project add` is one
  call with the options `command` and `options` (what `command_schema` says): `parse_command`
  reads the words after the task name into them, `format_command` writes them back, and a flag
  of a run in that line is `validation_error`. A line that leaves a required option to the
  default of its flag (`--project` of a project command) parses to it (`project_dir` `.`), so
  every parsed line validates.
- `store init --check` (`check_store`, `kartograf-plan/1`, MCP `check`; DEV-19.10): the plan of the
  marker without writing it, one position of the track `store`: `missing` with the action `write`
  where `init_store` would write it, `current` where the root has it. A root that `init_store`
  refuses as a `conflict` (`nested_store`, `not_empty`) is the one conflict position and the plan
  is `ok` (exit 0, as for a data command); every other refusal is raised (`data_error` for a
  layout that fails the verification or a marker that is not `kartograf-store/1`). The tool
  `kartograf_store_init` is offered as a plan on a server that does not write (37 tools instead
  of 36).

### Migration guide: data output (ADR-054, DEV §19)

What a caller of Kartograf (Python, `kartograf`, MCP) or a reader of its files has to change. The
entries above give the reasons and every detail; this is the list to follow. The names are those
of the unreleased 0.8.0, so no earlier release has to keep working, no data is migrated and no
alias exists.

**The two targets and the default store (DEV-19.1, DEV-19.2).** `output_dir` (`--output-dir`,
`-o`) writes plain files named as in the store, `root` (`--root`) writes the versioned store;
`--force` replaces existing plain files; the two exclude each other (`validation_error`,
`exclusive_options`). A command that names neither writes the store at the first of `--root`,
`KARTOGRAF_ROOT`, `[kartograf] root` of `nogat.toml` and `<data_dir>/kartograf`
(`kartograf config show --json` names it and its source), never into the working directory. The
MCP server writes only inside `--allow-dir` and with `--allow-writes`, so a default root outside
the allowed directories is `forbidden`.

| Old (0.8.0-dev) | New |
|---|---|
| `-o`, `--output DIR` as the store root of a command | `--root DIR` (store); `-o`, `--output-dir DIR` writes plain files |
| `output_dir=` as the store of `download_data`, `download_collection`, `download_landcover`, `download_soil`, `calculate_hsg`, the track functions, their `check_*` and `validate_*` twins, `run_command`, `check_command`, `validate_command`, `init_project` | `root=`; `output_dir=` is the plain directory |
| `DownloadManager(output_dir, provider)`, `LandCoverManager(output_dir, provider)`, `HSGCalculator(output_dir, provider)` | `DownloadManager(provider, *, root=None, output_dir=None, ...)` and the same for the others: the provider first, the targets keyword-only |
| `Project.output_dir`, the key `output_dir` of `kartograf-project/1`, `StoreOverview.output_dir`, `StoreEntries.output_dir` | `root` (an old manifest is not read: `project init` again) |
| `list_segments(output_dir)`, `list_partitions`, `iter_store`, `describe_store`, `list_store_entries` with `output_dir` | the same functions with `root` (optional: the default store) |
| a command without `--output` fails ("required") | it writes the default store |
| `--check-updates`, `check_updates` (CLI, `parse_command`, `format_command`, MCP argument) | `--check`, `check` (the plan `kartograf-plan/1` is the same document) |
| `kartograf-plan/1` with `store`, items with `status` only | `mode`, `root`, `output_dir` (a plan file of 0.8.0-dev is not read); plain items have `action` (`write`, `replace`, `conflict`), `path`, `reason` |
| `files[].file.{path, status, label, ...}` and `raw[]`, `inputs[]` likewise | `files[]` = `{unit, country, path, size_bytes, sha256, status}` (+ `label`, `version_path`, `newer`, `unverified`, `same_as` in the store) |
| file statuses `local`, `reused` in documents | `unchanged` (the Python attribute `VersionedFile.status` keeps both words); plain: `written`, `replaced` |
| reports without `mode` | `mode` (`plain` or `store`), `root` or `output_dir`, `skipped[]` (`{id, reason, message}`) |
| a store without a marker | `kartograf-store.json` (`kartograf-store/1`: `schema`, `tool`, `created_at`, `producer_version`), written by the first write; `kartograf store init --root DIR` marks an existing 0.8.0-dev store |
| sidecar `kartograf-meta/1` with `kartograf_version` | also `producer` and `producer_version` (optional; `kartograf_version` stays) |
| a work file `.part` beside a target (plain mode did not exist) | staging `<dir>/.kartograf-incoming/<host>_<pid>_<token>/`, removed after every run (success, error, SIGINT, SIGTERM); older leftovers (24 h) are removed by the next run |

**Plain mode (DEV-19.4 to DEV-19.11).** One file per unit named as in the store, in a flat
directory (`N-34-130-D-d-2-4.asc`, `0208.zip`, `<coordinates>.tif`, `CTES96.laz`), no sidecar, no
`versions/`, no standard path, no `full_sheet/`, no hard link: it works on FAT, exFAT and SMB. The
whole list of targets is checked before the first byte: a name two files share is `conflict`
(`duplicate_output_name`), a store of Kartograf or IMGWTools as the directory is `conflict`
(`output_in_store`), an existing file without `--force` is `conflict` (`output_exists`); the error
lists every path in `details.paths`. `--force` replaces each existing target with `os.replace` and
deletes nothing else. The year options filter the flights as in the store. **PL sheets (NMT,
NMPT, orthophotomaps) take the newest FULL flight, not the newest flight:** a file without a
sidecar cannot say it is partial; a sheet without a full flight is skipped (warning
`skipped_incomplete`, `skipped[]`), all skipped is `no_data` (`skipped_incomplete`, exit 11);
`--full-sheet` is an `info` notice and `--all-campaigns` is store-only. BDOT10k `keep_raw` writes
`<teryt>.gpkg` and `<teryt>.zip`; `soil hsg` fetches the SoilGrids inputs into the staging
directory and writes only the HSG raster (`inputs[]` is empty).

**Results (DEV-19.19).** Every writing command lists `files[]` with `size_bytes` and `sha256`
(computed while the file is written) and the status `written` or `replaced` (plain) and `new`,
`unchanged` or `relabeled` (store). `--check` plans each plain target as `write`, `replace` (with
`--force`) or `conflict`; a plan with conflicts is `ok` (exit 0), only the run fails.

**Errors** (codes of the registry; `details.reason` is the precision):

| Code (CLI exit) | `details.reason` | When |
|---|---|---|
| `conflict` (4) | `output_exists` | a plain target exists and there is no `--force`; `details.paths` lists every such file |
| `conflict` (4) | `duplicate_output_name` | two targets of one request have one name; `details.paths` |
| `conflict` (4) | `output_in_store` | the directory is, lies in or would enter a store of Kartograf or IMGWTools (hint `--root`) |
| `conflict` (4) | `nested_store` | the root lies in, holds or nests a store of any tool |
| `conflict` (4) | `not_empty` | a new store in a directory with other files and no layout |
| `store_unavailable` (8) | `no_marker` | a root that has the layout and no marker; hint `kartograf store init --root DIR` |
| `data_error` (7) | `invalid_layout` | `store init` found a foreign file or an invalid sidecar (`details.problems`) |
| `validation_error` (2) | `exclusive_options` | `output_dir` with `root` (`details.option` `root`, `details.options` both) |
| `validation_error` (2) | `store_only_option` | `--upgrade`, `--plan`, `--all-campaigns` or a project task with `output_dir` (hint `--root`) |
| `no_data` (14, units 11) | `skipped_incomplete` | every PL sheet of a plain request lacks a full flight |
| `forbidden` (12) | `writes_disabled`, `outside_allowed_dirs` | an MCP run on a server that does not write, or a path (or the default root) outside `--allow-dir` |

**Unchanged.** The store layout (`versions/`, the hard-linked standard path and `full_sheet/`), the
sidecar `kartograf-meta/1` apart from the two optional fields, the read API apart from the name
`root`, `kartograf-result/1`, the exit codes and the error registry, the project manifest apart
from the key `root`, and the MCP tool names.

**Per consumer** (checkouts of 2026-10-25; each changes with its pin):

- **Archiwista** (`src/archiwista/adapter/kartograf/adapter.py`): `project.output_dir` (line 645)
  is `project.root`, and the manifest key `output_dir` is `root`; the read API calls (`list_segments`
  at 120 and 317, `iter_store` at 424) take `root` (a positional store keeps working, a keyword
  changes); `probe` follows DEV-19.12 and DEV-19.13 (a root with the layout and no marker is
  `store_unavailable`, `no_marker`; the read API itself does not require the marker); read the
  marker fields and `producer`, `producer_version` of the sidecar; the statuses are `new`,
  `unchanged`, `relabeled`. `docs/PLAN_v0.1.md` (lines 45-50, 826) quotes the old names.
- **Retman** (`src/retman/tools/kartograf/`): `client.py:188`, `:195`, `:258` and `:273` pass
  `output_dir=` (and the flag `--output-dir`) for the store: pass `root=` (`--root`); `store_dir`
  need not stay required, since a default store exists; `handlers.py:84` and `:137` build
  `DownloadManager(output_dir=...)`: `DownloadManager(provider, root=...)`; a step that writes into
  its result folder can pass `output_dir` (plain files; `--force` where it may repeat) and read
  `files[].path`; `check_updates` becomes `check`.
- **Hydrolog:** no package dependency; `docs/INTEGRATION.md` (lines 410-452) calls
  `download_soil(output_dir=...)` for plain files and `HSGCalculator()`: both are real now
  (`output_dir` plain, `root` the store, neither the default store), and `AGENTS.md:143`
  (`kartograf soil download ... --output-dir`) is a valid call. Read `files[].path` of `--json`;
  with `--force` where the file may exist.
- **Hydraulik** (worktree `poc-poznan-screening`, `docs/poc/2026-10-15-poc-design.md:101`): the
  Kartograf calls of the proof of concept are the 0.7.x CLI: `kartograf elevation download ...
  --output-dir DIR` writes plain files and `--root DIR` the store; read `files[].path` of `--json`.
- **Hydrograf** (`backend`): `scripts/download_dem.py:130` builds `DownloadManager(output_dir=...)`,
  `scripts/download_landcover.py:118` and `core/cn_calculator.py:242` build
  `LandCoverManager(output_dir=..., ...)`: these name the store, so pass `root=` (the same
  layout) with the provider first (`DownloadManager(provider, root=...)`,
  `LandCoverManager(provider, root=...)`), or keep a directory as `output_dir=` for flat plain
  files (another layout: `<sheet>.asc` without `versions/`); `HSGCalculator()` (`core/
  cn_calculator.py:137`, `scripts/bootstrap.py:710`) now writes the default store unless it is
  given `root=` or `output_dir=`. The other `output_dir=` of `bootstrap.py` (lines 560, 593, 644,
  996) are Hydrograf's own functions and need no change.

### Breaking changes

- The default mode (without `--check-updates`/`--upgrade`) does not ask the source
  about the file with the local version (live test 2026-10-16, erratum 3 of ADR-036):
  the `http` signal (SM5 sheets, TM33 DMR 4G tiles, LAZ CZ, contours CZ,
  ZTM, KU packages, national RUIAN/HY-NET files) without `HEAD`, the `metadata`
  signal (SoilGrids, CORINE CLMS, orthophoto CZ, files from ATOM feeds)
  without checking the release, BDOT10k map sheets without GetFeatureInfo.
  The line `lokalna wersja ... (bez sprawdzania; --check-updates)`, in the API
  `VersionedFile.unverified == "unchecked"` and `newer = None`. Previously every
  run asked the source (offline 3 attempts and `Warning:`, up to 19 s; maps
  offline code 1) and appended `dostepna nowsza`. PL sheets and LAZ PL tiles
  ask the sheet index (Polish skorowidz) as before (file selection). What to do: check freshness
  with `--check-updates` (`check_*`), download newer content with
  `--upgrade`; code reading `VersionedFile.newer` in the default mode of these
  tracks gets `None`.
- Download status lines and `--check-updates` lines have one subject:
  the file path under `--output` in every track (previously the sheet code (Polish godło), the file name
  of a unit with several files, `82707_..._N-34-...laz` in the LAZ download, but
  the sheet code in the check, the bbox coordinates in the collection check); the same applies to the line
  `Error: ... zrodlo zmienilo sie od planu`. Project lines: `task:
  unit (file): state` (previously `orto_cz: CTES96: ok` four times). What to
  do: adjust scripts reading these lines to the path under `--output`
  (library unchanged: `VersionedFile.path`, `PlanItem.segment`/
  `hierarchy`/`name`).
- `hsg_statistics()` computes areas and percentages for the task area
  (`request` of the HSG sidecar: bbox in EPSG:2180 - with `--geometry` its
  envelope - or the sheet frame), not for the whole raster: a SoilGrids cell
  on the edge counts by its share in the area, the sum of areas = the area
  (live test 2026-10-17: a 2 x 2 km bbox gave 420.91 ha). Besides the groups
  `A`-`D` there is the key `nodata` (`percent` = share in the area); the `percent` of groups
  is the share of the area with data, `count` = cells touching
  the area; group descriptions (`description`, `HSG_DESCRIPTIONS`) in Polish.
  A file without a sidecar with the area - the whole raster. What to do: code iterating over the
  result skips the key `nodata` or iterates over `HSG_VALUES`; the percentage computed
  previously from raster pixels is no longer returned.
- The sidecar field `product` in land cover and HSG is the `--product` value as
  in the other groups (live test 2026-10-17): `bdot10k`, `bdoo`,
  `corine`, `zabaged`, `data50`, `data250` (previously `landcover`), raster
  `soil hsg` - `hsg` (previously `soil`; the command and directory name `hsg/`).
  `soil download` (without `--product`) stays `soil`. The field `product` of
  land cover descriptors = this value (the group is determined by the directory
  `landcover/`). What to do: code recognising a file by `product ==
  "landcover"` checks `dataset` or the new value.
- `UnitFile.unit` of a cutout (`download_data(..., cutout=True)`, PL and CZ) is the
  grid coordinates (`<coords>`, like the area units of a collection), not a
  path under `output_dir`; the project line `task: unit (file)`
  of a cutout has the same subject as other tasks (previously `trueorto:
  true-orto/pl_1992_0.05m/bbox/...tif (...tif): ok`). CLI download lines
  unchanged (path under `--output`). What to do: read the cutout path
  from `UnitFile.file.path`.
- UX consistency review 0.8.0 (input errors before the network, CLI = API):
  - `--layer` without `--geometry` is an error in every data command
    and in `project add` (previously the value was silently ignored and saved
    in the manifest). What to do: remove `--layer` (BDOT10k/BDOO data layers
    are selected with `--layers`).
  - LAZ PL rejects `--resolution`, `--sheet-system` and `--scale` (like LAZ
    CZ; previously ignored). What to do: remove these flags from LAZ downloads.
  - An area of explicit `--country pl|cz` (`--bbox`, envelope of `--geometry`)
    lying outside the country envelope ends with `ValidationError` with the
    area in EPSG:4326 and a hint about `--bbox-crs`/axis order (previously
    "brak obiektow"/"Brak arkuszy" after querying the source). What to do: fix
    `--bbox-crs` or the coordinates (`names --product world` unchanged).
  - The notice "skorowidz GUGiK niedostepny - uzyto lokalnej wersji"
    (`DownloadManager`) has the code `CHECK_FAILED` instead of `UNVERIFIED_LOCAL`;
    `UNVERIFIED_LOCAL` only means "local version of a source without a cheap
    signal" (`info`). What to do: code checking `Notice.code` for a sheet index
    failure - `CHECK_FAILED`.
  - The CLI does not expand abbreviations of long flags (`--out` does not mean `--output`,
    `--lay` is not an abbreviation of `--layer`/`--layers`); `--plan` without
    `--check-updates`/`--upgrade` is an `Error:` with code 2 (`ValidationError`,
    `option: plan`; previously a parser error, also code 2). What to do: write full
    flag names.
  - `--sheet` with a PL sheet code and `--sheet-system` other than the sheet code's system
    (`elevation`/`imagery download`, e.g. a PL-1992 sheet code with `--sheet-system
    2000`) is an `Error:`/`ValidationError` before the network (previously the flag was
    silently ignored); a matching value may still be given. What to do: remove
    `--sheet-system` (the sheet system follows from the sheet code).
  - `project init` without `--output`: `Error:` as in the data commands (code 2,
    as before; previously a parser error); `init_project(output_dir=None)` is a
    `ValidationError`. What to do: nothing (exit code unchanged).
  - `landcover download` and `landcover list-layers` select data through
    `--product` like every data group (ADR-044; previously `--source`/`-s`).
    `--source` and `-s` end with a parser error (code 2) with a hint about
    `--product`; `--product soilgrids` (like the former `--source soilgrids`)
    points to the `soil` group. Error messages name `--product <x>`
    (e.g. `--teryt dziala tylko z --product bdot10k ...`), the CHOICE column of
    `landcover list-sources` - `--product bdot10k`. The task option key of the project
    `landcover download` is `product` (previously `source`). What to
    do: in scripts replace `--source X`/`-s X` with `--product X`;
    in a hand-written `kartograf-project.json` the key `source` with `product`
    (`project add` writes the new key).
  - `soil hsg --summary` prints HSG statistics (share and area of
    groups A-D, no data) instead of `--stats` (ADR-044; next to `soil download
    --stat` the name was confusing); `--stats` ends with a parser error (code 2)
    with a hint about `--summary`, and `project add ... soil hsg --summary` is an
    `Error:` (a printing option, not a task option). What to do: in scripts
    replace `soil hsg ... --stats` with `--summary`.
  - The PL image cutout has one pair of functions for orthophoto and true orthophoto
    (ADR-044 D3): `download_image_cutout`/`check_image_cutout` (result
    `ImageCutoutResult`) are in `kartograf.__all__`, all arguments
    named (`bbox=` as in `download_data`), `coverage` optional (`None`
    for true orthophoto; orthophoto requires it as before); the 0.8.0-dev wrappers
    `download_orto_cutout`/`check_orto_cutout` and the name `OrtoCutoutResult`
    removed without aliases. What to do: `download_orto_cutout(bbox, ...)` ->
    `download_image_cutout(product="orto", bbox=bbox, ...)` (the same for
    `check_*`), `OrtoCutoutResult` -> `ImageCutoutResult`.
  - The download and check functions from `kartograf.__all__` accept
    only named arguments, like `download_data` (live test
    2026-10-17): `bbox=` in `download_pl_cutout`/`check_pl_cutout`,
    `download_cz_cutout`/`check_cz_cutout` and `download_laz_area`/
    `check_laz_area`, `sheet=` in `download_cz_sheet`/`check_cz_sheet`
    and `download_cz_orto_sheet`/`check_cz_orto_sheet` (previously the first
    argument was positional); a positional argument is a `TypeError`. Project
    functions (`download_project`, `check_project` and the rest of the family) have
    only the project directory positional. What to do: `download_pl_cutout(bbox,
    ...)` -> `download_pl_cutout(bbox=bbox, ...)`, `download_laz_area(bbox,
    ...)` -> `download_laz_area(bbox=bbox, ...)`,
    `download_cz_sheet("CTES96", ...)` -> `download_cz_sheet(sheet="CTES96",
    ...)`; the same for the remaining functions and their `check_*`.
  - Project state in the API: `get_project_status` instead of `project_status`
    (ADR-044 D4; a verb like `init_project`, `verify_project`), without an
    alias; `kartograf project status` unchanged. What to do: replace
    `project_status(...)` with `get_project_status(...)`.
- The public API of land cover, SoilGrids and HSG downloads is command-level
  functions (ADR-044 D5), without aliases: `download_landcover(product=...,
  output_dir=..., teryt=|sheet=|bbox=|geometry=, layer=, update=, plan=,
  workers=, on_notice=, ...)` and `check_landcover` with a selection consistent
  with `landcover download`; `download_soil(output_dir=..., sheet=|bbox=|
  geometry=, property=, depth=, stat=, ...)` and `check_soil` corresponding to
  `soil download`; `calculate_hsg(output_dir=..., sheet=|bbox=|geometry=,
  depth=...)` and `check_hsg` with the same selection (HSG computes only
  SoilGrids `stat="mean"`) and `hsg_statistics(path)`. The results
  `LandCoverReport`, `SoilReport` and `HsgReport` have `files:
  tuple[UnitFile, ...]`, `failed: tuple[UnitFailure, ...]` (errors of
  individual files and units, then `ok=False`), `stale`, `notices`
  and `ok` (complete data); `LandCoverReport.raw` is the separate versions of the
  original ZIP (`keep_raw`), `HsgReport.files[0].file` - the HSG raster,
  `HsgReport.inputs` - the downloaded clay/sand/silt. BDOT10k from an area downloads
  every county (Polish powiat). Input errors (incorrect options) still end with
  `ValidationError`. `LandCoverManager`, `HSGCalculator`,
  `LandCoverResult`, `LandCoverAreaResult`, `LandCoverFailure`
  and `HsgResult` are not exported from `kartograf.__all__`. There is no
  `timeout` parameter of the command functions or `collections.run_request` (the limit
  of the provider/channel). What to do: replace the former methods with functions
  from `kartograf.__all__` - `LandCoverManager(out,
  "bdot10k").download(teryt=t)` -> `download_landcover(product="bdot10k",
  output_dir=out, teryt=t)` (`product=` only in land cover; `check` ->
  `check_landcover`), `LandCoverManager(out, "soilgrids").check(...)` ->
  `check_soil(output_dir=out, ...)`, `HSGCalculator(out).calculate_hsg(...)`
  -> `calculate_hsg(output_dir=out, ...)` without `stat=` (analogously
  `check_hsg`), `calc.get_hsg_statistics(path)` -> `hsg_statistics(path)`;
  `result.file` -> `report.files[0].file`, `result.files` ->
  `report.files` (field `.file`), original ZIP versions from `report.raw`,
  HSG inputs from `report.inputs`; read a missing unit coverage and other failures
  from `report.failed` and `report.ok`, not from a file handling exception;
  remove passing `timeout=`.
- Orthophoto under `--country auto` (plan D, ADR-042 D13): an area at the
  border yields PL sheets and SM5 CZ sheets (CUZK) instead of narrowing to PL
  (the `Notice` `auto_narrowed_to_pl` for `--product orto` alone disappears; CZ
  files in `orto/cz_sjtsk/`, shared `extra.parent_request`). `--resolution`
  with `--product orto` without `--cutout` is an error for PL and CZ (sheets
  have the source pixel). What to do: PL sheets only - `--country pl`
  (`country="pl"`); remove `--resolution` from orthophoto sheet downloads
  (cutout pixel: `--cutout --coverage ... --resolution ...`).
- The CLI in command groups by data type (ADR-039, without aliases): each group
  has its own flags and `--help`, and `list-sources` prints its sources from the registry
  (without network). The old commands end with a parser error (code 2) with the name of the new one.

  | Until now | Now |
  |---|---|
  | `kartograf download --product nmt\|nmpt\|laz ...` | `kartograf elevation download --product nmt\|nmpt\|laz ...` |
  | `kartograf download --product orto ...` | `kartograf imagery download --product orto ...` (without `--vertical-crs` and `--min-density`; `--resolution` only with `--cutout`; `--country pl\|cz\|auto`) |
  | `kartograf landcover download --source bdot10k\|corine ...` | `kartograf landcover download --product bdot10k\|corine ...` (ADR-044) |
  | `kartograf landcover download --source soilgrids ...` | `kartograf soil download ...` (without `--source`) |
  | `kartograf landcover list-layers --source soilgrids` | `kartograf soil list-layers` |
  | `kartograf soilgrids hsg ...` | `kartograf soil hsg ...` |
  | `kartograf parse`, `kartograf cache` | unchanged |

  New: `kartograf <group> list-sources` in every data group; a missing `--product`
  gives a message with the products of that group only; `--sheet` and `--year` have
  a single definition in every data group (ADR-039 D4, D5). The library, sidecar
  and `data/` layout are unchanged. Python: `kartograf.cli.commands` has no
  `cmd_landcover` or `cmd_soilgrids`, `parse_bbox_arg` is in
  `kartograf.cli._args`. What to do: in scripts replace the commands according to the table
  (`--product orto` -> `imagery download`, other products ->
  `elevation download`, SoilGrids -> `soil`); Python code using
  library functions needs no changes.
- digital terrain model (NMT) and digital surface model (NMPT) PL from the variant registry (ADR-041, plan A): resolutions,
  vertical CRSs and formats are known to a single registry `kartograf.sources.variants`
  (CLI and API validation, `--help`, `list-sources`, store segment, selection of the
  sheet index record); NMPT has 0.5m, 0.6m and 1m grids.
  - `elevation download --product nmpt` requires `--resolution`;
    `GugikNmptProvider(session=None, *, vertical_crs, resolution,
    format="ASC", cache=None)` - `resolution` has no default value. What to
    do: add `--resolution 1m` / `resolution="1m"`; existing NMPT 1 m data
    stays in the segment `nmpt/pl_<crs>_1m_<vcrs>` (key
    `pl.gugik.nmpt`).
  - Removed without aliases: `kartograf.providers.pl.nmt_vertical_crs`,
    `require_nmt_vertical_crs`, `NMT_5M_VERTICAL_CRS`,
    `GugikProvider.SUPPORTED_RESOLUTIONS`, `SUPPORTED_VERTICAL_CRS`,
    `SUPPORTED_VERTICAL_CRS_5M`, `get_supported_resolutions()`,
    `get_supported_vertical_crs_for_resolution()`,
    `GugikNmptProvider.SUPPORTED_RESOLUTIONS`,
    `FileStorage.SUPPORTED_RESOLUTIONS`, `GugikLazProvider.WFS_ENDPOINTS`
    and `WMS_SKOROWIDZE_ENDPOINTS` (`GugikProvider`, `GugikNmptProvider`).
    What to do: variants from `kartograf.sources.variants.variants(product=,
    country=, vertical_crs=, resolution=, system=, format=)` (fields `label`,
    `vertical_crs`, `format`, `source`, `index_ref.endpoint`);
    `GugikProvider.is_wcs_available()` stays.
  - The NMT/NMPT sheet index is read from the GUGiK WFS (the same index as the availability
    report and LAZ) instead of WMS GetFeatureInfo; the record must have the format
    of the variant in the `format` field and in the URL ending. Sidecar of new sheets:
    `extra.source.index_url` = WFS service address, `extra.source.layer` = WFS
    type (`SkorowidzNMT2025` instead of the WMS layer `SkorowidzeNMT2025`); files,
    segments and the freshness signal (`index`) of existing data are unchanged.
    What to do: nothing; scripts comparing `extra.source.layer` with the WMS
    layer name - the new name.
- The cutout mode is explicit, and CRS names describe their roles (ADR-038,
  without aliases). CLI: `--target-crs X` -> `--cutout --horizontal-crs X`
  (`--cutout` enables a single cutout instead of sheets, `--horizontal-crs` is
  required with it, without `--cutout` it is an `Error:`), `--system` -> `--sheet-system`.
  A CZ area (`--bbox`/`--geometry`, also the CZ part under `--country auto`)
  requires `--cutout --horizontal-crs`, natively `--horizontal-crs EPSG:5514`
  (until now a CZ cutout was produced without the flag). Under `auto` a PL+CZ area no longer
  gives PL sheets next to a CZ cutout: with `--cutout` the PL part is a WCS cutout
  (1 m only, no campaigns), PL sheets are given by `--country pl`; the `Notice`
  `campaign_opts_pl_only` is removed (campaign options under `auto` with CZ are
  now an `Error:`). Library: `download_data`/`check_data(...,
  sheet_system=, cutout=False, horizontal_crs=None)` instead of `system=`,
  `target_crs=`; `download_pl_cutout`/`check_pl_cutout`/`download_cz_cutout`/
  `check_cz_cutout(..., horizontal_crs=)`, `create_cz_raster_provider`/
  `CuzkRasterProvider(horizontal_crs=)`; `SheetParser(sheet, sheet_system=)`
  and `SheetParser.sheet_system`, `find_sheets_for_bbox(...,
  sheet_system)`, `find_sheets_for_geometry(..., sheet_system=)`;
  `SUPPORTED_TARGET_CRS` -> `CUTOUT_CRS`. The no-coverage hint says
  `--sheet-system`; a cache entry with the `--system` hint is
  refreshed. Sidecar unchanged. What to do: in scripts replace the flags,
  add `--cutout --horizontal-crs EPSG:5514` to CZ area downloads; in
  code replace the argument names and add `cutout=True` to
  `download_data(horizontal_crs=...)`.
- `DownloadManager.download_sheet`, `download_hierarchy` and
  `download_sheets` now return `DownloadResult` instead of a path or a list of
  paths. `result.files[godlo]` contains a tuple of `VersionedFile` (among others `path`,
  `version_path`, `label`, `status`), and `result.stale` and `result.notices`
  pass on outdated plan items and data notices.
  `check_updates(manager, sheets)` -> `manager.check_sheets(sheets)`;
  `upgrade(manager, plan)` -> `manager.download_sheets(sheets, update="upgrade",
  plan=plan)`. Removed `last_result`, `last_sheet`, `UpgradeReport` and the
  `SheetFetch` export; the manager's `max_workers=` -> `workers=`, added
  `year=` and `on_notice=`. What to do: use the returned value,
  update method calls and file reads from `result.files`, and print notices
  from `on_notice` without reprocessing `result.notices`.
- Metadata cache (Z6, ADR-037): public functions (`download_data`,
  `check_data`, the `download_*`/`check_*` paths, `download_landcover`/
  `check_landcover`, `download_soil`/`check_soil`, `calculate_hsg`/
  `check_hsg`) accept `cache: MetadataCache | bool = True` -
  by default the same file as the CLI (`<cwd>/.kartograf_cache.db`); until now the
  library worked without a cache. `update="force"` skips cache reads
  (like `--force`). What to do: a process in a directory without write permission or
  stateless tests - `cache=False`; a custom file - `cache=MetadataCache(...)`.
- PL cutout: `download_pl_cutout(*, bbox, horizontal_crs, ...)` and
  `check_pl_cutout(*, bbox, horizontal_crs, ...)` accept the same
  selection arguments (all keyword-only), `download_pl_cutout` gets
  `plan=`, `cache=` (`True` = default cache in cwd) and `on_notice=`;
  `PlCutoutResult.notices` carries notices about the cutout size
  (`cutout_size`, before the first WCS request) and a cutout without data
  (`all_nodata`). `prepare_pl_cutout` and `run_pl_wcs_cutout` were removed,
  `PlCutout` is an internal step (outside `__all__`).
  What to do: pass `bbox=` and `horizontal_crs=` by name;
  `check_pl_cutout(cutout)` -> `check_pl_cutout(bbox=bbox,
  horizontal_crs=..., output_dir=..., vertical_crs=..., product=...)`; execute
  the plan through `download_pl_cutout(..., plan=plan)`.
- CZ: a CZ sheet has the public API `download_cz_sheet(*, sheet, output_dir,
  product, vertical_crs, resolution=None, update, plan, cache, on_notice)`
  and `check_cz_sheet` with the same arguments (`CzSheetResult`; SM5 sheet
  NMT `5m` only / NMPT `0.5m`, TM33 tile requires a label; erratum to decision
  9 of plan 2/3, `product` - plan B).
  `check_cz_cutout(*, bbox, output_dir, product, horizontal_crs,
  vertical_crs, resolution)` accepts the arguments of `download_cz_cutout` (without provider
  and `image_crs`); `download_cz_cutout` gets `plan=`, `on_notice=`,
  `cache=True` (default cache in cwd). CZ results have `notices`
  (`all_nodata` instead of a log warning). `run_cz_cutout` is outside the API.
  What to do: `run_cz_cutout(provider, bbox, ...)` ->
  `download_cz_cutout(bbox=bbox, product="nmt", ...)`;
  `check_cz_cutout(provider, bbox, output_dir=, image_crs=)` ->
  `check_cz_cutout(bbox=bbox, output_dir=, product="nmt", horizontal_crs=,
  vertical_crs=, resolution=)`.
- CZ from the variant registry (ADR-041, plan B): `CuzkDmrProvider`
  and `create_dmr_provider` removed without aliases - in their place
  `CuzkRasterProvider(product, resolution, session=None, cache=None,
  horizontal_crs=None, *, vertical_crs)` and `create_cz_raster_provider` with the same
  signature (`product` = `"nmt"`|`"nmpt"`, model from the registry:
  NMT `2m` DMR 5G / `5m` DMR 4G, NMPT `0.5m` DMP OK / `2m` DMP 1G);
  `sm5_signal(sheet)` -> `file_signal(sheet)` (SM5 file and TM33 tile).
  `download_cz_sheet`/`check_cz_sheet`/`download_cz_cutout`/
  `check_cz_cutout` require `product=`. `GugikLazProvider.download(url,
  ...)` -> `download_tile(url, ...)` (A5-7: the provider's `download` takes
  a sheet code). A TM33 DMR 4G tile with `--vertical-crs EVRF2007` is a ready CUZK
  ETRS89 file (EPSG:3045, no warp and no vertical operation, signal `http`);
  a version from a warp stored in the store before this change stays local
  with `Info:` (unchecked; a 0.7.x file in the standard path is
  replaced on the first download). `--country auto` with `--product nmpt`
  no longer narrows to PL (CZ has NMPT): a PL+CZ area with `--resolution
  0.5m` (DMP OK) requires `--cutout`, and the PL cutout has 1 m only. What to do:
  `CuzkDmrProvider(res, ...)`/`create_dmr_provider(res, ...)` ->
  `CuzkRasterProvider("nmt", res, ...)`/`create_cz_raster_provider("nmt",
  res, ...)`, `sm5_signal` -> `file_signal`; add `product="nmt"` in the CZ
  paths; `GugikLazProvider.download` -> `download_tile`; refresh TM33 DMR 4G
  EVRF2007 tiles from a store predating this change with `--force`; download NMPT PL
  0.5m sheets at the border with `--country pl`.
- LAZ: `download_laz_area` accepts `bbox` in any supported CRS
  (CZ systems only through the pinned operation), `plan=`, `cache=True`,
  `on_notice=` (`laz_superseded` instead of printing by the CLI) and
  `workers=` instead of `max_workers=`; a new twin `check_laz_area` with the
  same arguments. `on_progress` gets `(0, total)` before the first
  tile. `run_laz_download` and `check_laz_updates` are outside the API. What to do:
  `max_workers=` -> `workers=`; `check_laz_updates(selection, ...)` ->
  `check_laz_area(bbox=bbox, output_dir=..., vertical_crs=..., ...)`; execute
  the plan through `download_laz_area(..., update="upgrade", plan=plan)`.
- The CLI `elevation download` and `imagery download` only translate flags into
  `download_data`/`check_data` (description in Added): input errors are
  `ValidationError` with text as in the CLI, data notices
  (`Info:`/`Warning:`) are produced in the library as `Notice` (among others
  `auto` clipping, no coverage, links out of range); degrees
  in clipping notices as `st.N`/`st.E` (ASCII). In the summary
  `bledy:` counts failed parts of the task (sheets without GUGiK data are
  a `Warning:`, not an error). What to do: scripts matching CLI output -
  new texts; scripts calling the CLI through `subprocess` can switch to
  `download_data` with the same values (`resolution={"pl": "1m",
  "cz": "2m"}` instead of `pl=1m,cz=2m`).
- `kartograf landcover download` and `kartograf soil hsg`: a missing or multiple
  area selection is a library error `Podaj dokladnie jeden wybor: ...`
  (land cover/HSG) or `Podaj wybor obszaru: ...` /
  `Podaj dokladnie jeden wybor obszaru: ...` (`download_data`) instead of
  English messages; new flags of these commands - Added. What to do:
  see Language (Z5) below.
- Sidecar: coordinates `request.bbox` and `extra.parent_request.bbox` always
  as floating-point numbers (`770000.0`), also for a `BBox` made of
  integers - the same file from the CLI and from the library. What to do: nothing
  (comparison of numeric values unchanged); textual comparisons of sidecars
  must accept the `.0` notation.
- Language (Z5): the help of all commands, CLI messages, `Notice` texts
  and `KartografError` errors in Polish and in ASCII only. Changed among others:
  `Invalid bbox format` -> `Nieprawidlowy bbox`, `Must provide one of` /
  `Specify only one of` -> `Podaj wybor obszaru` /
  `Podaj dokladnie jeden wybor obszaru` (`download_data`),
  `File not found` -> `Brak pliku`, `Unsupported ...`/`Invalid ...` ->
  `Nieobslugiwany ...`/`Nieprawidlowy ...`, `Found N sheets ...` ->
  `Znaleziono arkuszy w skali ...`, `Downloading ...` -> `Pobieranie ...`;
  the labels of these lines `(resolution: 1m)`, `(CZ, resolution: 5m)`,
  `(product: orto)`, `(format: TTN, resolution: -)` -> `(rozdzielczosc:
  1m)`, `(CZ, rozdzielczosc: 5m)`, `(produkt: orto)`, `(format: TTN,
  rozdzielczosc: -)`, hierarchy `Pobieranie 25 arkuszy z 7.171.21 to
  1:2000` -> `... z 7.171.21 w skali 1:2000`, `Pobieranie CZ bbox (2m,
  EPSG:5514)` -> `Pobieranie wycinka CZ (rozdzielczosc: 2m, EPSG:5514)`
  (live tests 2026-10-16/17);
  the `parse` output (`Godlo:`, `Skala:`, `Uklad:`, `Czlony:`, `Hierarchia`,
  `Arkusze potomne`), `cache stats` (`Wpisy rekordow:` ...), `sheet_parser`
  messages without Polish characters (`Nieprawidlowe godlo`), BDOT10k layer
  descriptions (`Tereny lesne`), `metavar` (`GODLO`, `KATALOG`, `PLIK`, `ROK`,
  `NAZWA`, `KOD`, `SKALA`); ASCII progress bar icons: `>` download,
  `+` downloaded, `o` skipped, `x` error, `0` no data (was `↓ ✓ ○ ✗ ∅`).
  What to do: scripts matching CLI texts or `str(exception)` - the new
  wording; better the exception type (`ValidationError`) and the exit code.

- Library: invalid input values for providers, the store, the LAZ cutout
  and the target sheet scale raise `ValidationError` (a subclass of
  `KartografError`), not `ValueError`; the CLI no longer catches
  `ValueError` as a user error. What to do: change
  `except ValueError` to `except ValidationError` for argument errors;
  do not use it to cover internal program invariant errors.
- Removed the sheet-based PL cutout track: `PlCutoutSheets`,
  `select_pl_cutout_sheets`, `run_pl_cutout`, `build_pl_cutout`,
  `build_cutout_from_sheets` and the related functions for space estimation,
  sidecar writing and restoring skipped cutouts. `PlCutoutResult`
  no longer contains sheet fields (`sheet_paths`, `missing_sheets`,
  `off_grid_sheets`, `partial_sheets`, `unverified`). What to do:
  for a 1 m NMT/NMPT cutout use `download_pl_cutout`; for a sheet mosaic,
  download the sheets separately and merge them yourself with `mosaic_and_crop`.
- `download_pl_cutout` no longer accepts the ignored parameters
  `geometry`, `layer`, `scale`, `max_workers`, `force`, `on_progress`;
  `cache` has been restored as a parameter of the shared metadata cache.
  What to do: pass the geometry envelope as `bbox`; do the selection of
  sheets, campaigns and 5 m by downloading sheets without
  `--cutout`.
- `mosaic_and_crop` no longer accepts `snap_to_source_grid` or
  `assign_crs`; `dtype=` and wrapping sources in VRT remain. What to do:
  check the grid with `check_source_grid` and, if needed,
  align the area and resample the rasters in your own code; prepare the source
  CRS before merging, without assigning it through the mosaic.
- `GridMismatchError` removed from `kartograf` and `kartograf.exceptions` —
  it was raised only by the removed sheet track (EPSG:2180 from sheets with a different
  grid phase). What to do: remove handling of this exception; the grid phase
  of your own sources is checked by `check_source_grid(...).off_grid`.
- CLI: the sheet code is given with the `--sheet` flag (ADR-031 errata 1, no aliases):
  `kartograf download N-34-130-D-d-2-4` (0.7.x) -> `kartograf elevation
  download --sheet N-34-130-D-d-2-4 ...` (orthophoto: `imagery
  download`; also PL-2000 and CZ sheet codes, e.g. `--sheet 302_5550`);
  `landcover download --godlo` -> `--sheet`, `soilgrids hsg --godlo` ->
  `soil hsg --sheet`. `kartograf parse` takes the sheet code positionally as
  before (in the help: `GODLO`). What to do: add `--sheet` before the sheet code
  (command names: the group table above), replace `--godlo` with `--sheet`.
- Library: Polish public API identifiers replaced by
  English ones, without aliases (ADR-031 erratum 1). `godlo` -> `sheet`,
  `godla` -> `sheets` in all parameters and attributes (among others
  `SheetParser.sheet`, `DownloadProgress.sheet`,
  `LazTile.sheet`, `DownloadError.sheet`/`NoCoverageError.sheet`,
  `DownloadManager.download_sheet(sheet)`, `check_year_range(sheets)`,
  `MetadataCache.get_record(..., sheet)`, `LandCoverManager.download(sheet=)`,
  `download_all_counties(sheet=)`); methods `download_by_godlo` ->
  `download_by_sheet` (`LandCoverManager`, `LandCoverProvider`,
  `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`),
  `HSGCalculator.calculate_hsg_by_godlo` -> `calculate_hsg_by_sheet`,
  `BaseProvider.validate_godlo` -> `validate_sheet`,
  `horizontal_crs_for_godlo` -> `horizontal_crs_for_sheet`. `uklad` ->
  `system` (`Parser2000.system`, `ParserTM33.system`, `LazTile.system`,
  `FileStorage.get_raw_path(..., system=)`,
  `SourceDescriptor.resolve_subdir(system=)`, segment template `{system}`
  instead of `{uklad}`), in `SheetParser` `sheet_system` (`SheetParser(sheet,
  sheet_system=)`, `.sheet_system`, ADR-038), `SheetParser.VALID_UKLADY` ->
  `VALID_SYSTEMS`, `CampaignRef.zgloszenie` -> `survey_work_id`,
  `GugikOrtoProvider.WMS_SKOROWIDZE_ENDPOINT` -> `WMS_INDEX_ENDPOINT`
  (`WMS_SKOROWIDZE_ENDPOINTS` for NMT and NMPT removed - see the entry on the variant
  registry above). What to do: replace the names in calls and attribute
  reads.
  Sidecar keys and values (sheet codes) are unchanged.
- CLI and library: `--campaigns {newest,all}` and the parameter
  `campaigns="newest"|"all"` replaced by the `--all-campaigns` switch
  and the parameter `all_campaigns: bool = False` (PL sheets and LAZ).
  By default the newest flight is downloaded; the switch selects all
  flights in the year range. Model A and the text values of `request.campaigns`
  in the sidecar (`"newest"`/`"all"`) remain unchanged (parameter
  `FileStorage.list_files(campaigns=)` — see the versioned store below).
  What to do: replace `--campaigns all` with `--all-campaigns`,
  remove `--campaigns newest`; replace `campaigns="all"` with
  `all_campaigns=True`, and remove `campaigns="newest"` or replace it with
  `all_campaigns=False`; property `DownloadManager.campaigns` ->
  `DownloadManager.all_campaigns` (bool).
- No default values affecting data (CLI and API; DEVELOPMENT_STANDARDS
  11.2, ADR-004 erratum 1, ADR-023 erratum 2). Missing value: CLI `Error:`
  with a list of permitted values (code 2, before the network); API:
  `TypeError` for required signature arguments, `ValidationError`
  for missing conditional options (among others CORINE `year`, HSG `depth`).
  - CLI `elevation download` and `imagery download`: required `--product`
    (elevation: nmt|nmpt|laz|contours; imagery: orto|intensity|true-orto|
    oblique-orto), `--output`,
    `--country` with `--bbox`/`--geometry` (pl|cz|auto; with `--sheet` the country
    comes from the sheet code), `--vertical-crs` for nmt/nmpt/laz (PL EVRF2007|KRON86, CZ
    Bpv|EVRF2007), `--resolution` for NMT and NMPT where there is a choice (PL:
    variant registry labels, e.g. 0.5m|1m|5m - see the entry on the registry above;
    CZ TM33 and area: NMT 2m|5m, NMPT 0.5m|2m; the `--cutout` cutout and the SM5 sheet have
    a single value and may omit it), `--sheet-system` for PL
    `--bbox`/`--geometry` without `--cutout` (1992|2000), `--horizontal-crs`
    with `--cutout`. `--resolution` and `--vertical-crs`
    accept a single value or per-country pairs (`pl=1m,cz=2m`,
    `pl=EVRF2007,cz=Bpv`); a single value must fit every country
    of the task. `--scale`: PL-1992 is always 1:10000 — `--scale` with a PL-1992
    task is an `Error:`; PL-2000 requires `--scale` (1:5000|1:2000|1:1000|1:500)
    with `--bbox`/`--geometry --sheet-system 2000` and with a 1:10000 sheet code. The
    `Info:` about different default vertical CRSs for the PL and CZ parts is gone;
    `--sheet-system` no longer
    switches `--country auto` to PL. The no-coverage hint for
    PL-1992 does not give `--scale`.
  - CLI `landcover download`: required `--product` (in 0.7.x `--source`),
    `--output`, `--year` (corine); `landcover list-layers --product`;
    `soil download`: `--property`/`--depth`/`--stat`; `soil hsg`:
    `--output` and `--depth`.
    For BDOT10k `--format` defaults to `GPKG` (without `--year`); for
    other sources it is an error.
  - API: `DownloadManager(output_dir, provider, *, ...)` — both required,
    the parameters `vertical_crs` and `resolution` removed (the provider decides);
    `FileStorage(output_dir, *, resolution, vertical_crs, ...)`, methods
    `get_path/exists/delete/get_full_sheet_path/get_campaign_path/get_size/
    write_atomic` with required `ext`, `list_files(pattern, *, versions=False)`;
    `MetadataCache(db_path, ...)`; `GugikProvider(*, vertical_crs, resolution)`,
    `GugikNmptProvider(*, vertical_crs, resolution)`, `GugikLazProvider(*, vertical_crs)`,
    `GugikOrtoProvider(*, color)`, `create_nmt_provider(vertical_crs,
    resolution)`, `CuzkRasterProvider(product, resolution, ...,
    *, vertical_crs)`, `create_cz_raster_provider(product, resolution,
    ..., *, vertical_crs)`;
    `download_pl_cutout(*, bbox, horizontal_crs, output_dir,
    vertical_crs, product)` — the `resolution` parameter removed (cutout only
    1 m), and `prepare_pl_cutout` removed; `download_laz_area(*, bbox,
    output_dir, vertical_crs, ...)`; internal `run_laz_download` removed;
    `find_sheets_for_bbox(bbox, target_scale, sheet_system)`,
    `find_sheets_2000_for_bbox(bbox, target_scale)`,
    `find_sheets_for_geometry(filepath, target_scale, ..., *, sheet_system)`;
    `download_landcover(product=..., output_dir=...)`,
    `download_soil(output_dir=..., property=..., depth=..., stat=...)`;
    `CorineProvider.download_by_bbox/download_by_sheet(..., *, year)`;
    `SoilGridsProvider.download_by_bbox(..., *, property, depth, stat)`;
    `calculate_hsg(output_dir=..., depth=..., ...)`.
  What to do: give explicitly the values that used to be defaults (CLI: `--product
  nmt -o ./data --resolution 1m --vertical-crs EVRF2007`, with an area
  `--country pl --sheet-system 1992`; CZ `--resolution 2m --vertical-crs Bpv`;
  border areas `--resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv`;
  remove `--scale` from PL-1992 tasks). Library: pass the provider
  and the directory to `DownloadManager`, `product` and `output_dir` to
  `download_landcover`, the path to `MetadataCache` (the CLI uses
  `.kartograf_cache.db` in the current directory).
- Versioned store for PL NMT/NMPT/orthophoto sheets (ADR-036;
  spec `docs/superpowers/specs/2026-10-08-versioned-store-design.md`):
  - Layout: `<segment>/kampanie/<date>_<id>/...` -> `<segment>/versions/<hierarchy>/<date>_<id>_<sha8>/<sheet_code>.<ext>`
    (immutable version, sidecar written once). No migration: `kampanie/`
    is not read (the CLI prints `Info:` once). What to do: download the data
    again (e.g. with the same command); the old `kampanie/` directory can be
    removed manually.
  - The default mode no longer automatically downloads a newer campaign with
    `newest`: the local version stays, and the CLI appends `; dostepna nowsza
    <label> (--upgrade)` and `Info:` (`DownloadResult.newer`). What to do:
    `--upgrade` / `update="upgrade"` when you want the newer campaign.
  - `--force` downloads again and refreshes the metadata cache, but overwrites
    nothing: the same content = `bez zmian`, different = a new version next to the
    old one. `--force`, `--upgrade` and `--check-updates` are mutually exclusive.
    What to do: do not combine `--force`, `--upgrade` and `--check-updates`.
  - Library: `download_sheet/download_hierarchy/download_sheets(...,
    skip_existing=)` -> `update: None | "upgrade" | "force"`. What to do:
    replace `skip_existing=False` with `update="force"`, remove
    `skip_existing=True`.
  - Hard links required: the standard path and `full_sheet/` are exclusively
    hard links to versions; a copy instead of a hard link is gone (a file
    system without hard links = sheet error). `SheetFetch.link`,
    `DownloadResult.copied` and the CLI `Warning: hardlink niedostepny ...`
    removed. What to do: keep data on ext4/NTFS/SMB; copy the store
    with `rsync -aH`.
  - `extra.parent_requests` removed (the version sidecar is immutable;
    `parent_request` = the task that created the version). `extra.coverage`
    is computed on write for every incomplete flight, never appended; a full
    flight has no measurement. What to do: group the task's files by
    `parent_request`.
  - `FileStorage.get_campaign_path` removed, `list_files(campaigns=)` ->
    `list_files(versions=)` (True = version files). What to do: read the versions of a
    sheet from `FileStorage.get_versions_root(sheet)` or
    `list_files(..., versions=True)`.
  - Provider without campaigns (mocks, foreign providers): the file is also a version
    (label = UTC download date); its sidecar is mandatory (without a
    descriptor: a trimmed sidecar), a write failure = sheet error. What to
    do: nothing.
  - CLI (`elevation download`, `imagery download`): instead of `Downloaded to`,
    `Skipped ... already exists` and `Downloaded
    N files ...` one line per file (`<sheet_code>: nowa wersja
    <label>_<sha8>` / `nowa etykieta ... (plik identyczny z
    <label>)` / `bez zmian
    ...` / `lokalna wersja ...`) and the summary `Nowe: N, nowa etykieta:
    N, bez zmian: N, lokalne: N, bledy: N`. What to do: switch scripts parsing
    the output to the new lines or to the library.
  - Failure of the sheet index without a year bound: local version for every
    strategy (previously only `newest`); with a year bound when EVERY sheet has a
    local version in the range — local versions with a warning (previously always a
    task error). Default mode only. What to do: nothing.
- Versioned store for LAZ, CZ sheets and cutouts, and PL cutouts
  from WCS (ADR-036):
  - LAZ: tile = version in `laz/<segment>/versions/<hierarchy>/<date>_<report>_<sha8>/<file>.laz`,
    standard path = hard link, version sidecar mandatory. A tile
    with a local version is not downloaded again; a newer survey (different
    files) is downloaded by default (D26). `run_laz_download`/
    `download_laz_area(force=)` -> `update=None|"upgrade"|"force"`,
    `LazDownloadResult.downloaded`/`.skipped` -> `.files`
    (`VersionedFile`, status `new`/`unchanged`/`relabeled`/`local`) and
    `.stale`. What to do: replace `force=True` with `update="force"`, count
    from `result.files` by `status`.
  - CZ sheets (TM33, SM5) and the CZ cutout: versions in `<segment>/versions/`,
    `bbox/<coords>.tif` and the sheet path are hard links. SM5 stores
    `ETag`/`Last-Modified` in `extra.http` and by default makes one `HEAD`
    per file with a local version (newer content only reported, `--upgrade`
    downloads). `run_cz_cutout`/`download_cz_cutout(force=)` -> `update=`,
    `CzCutoutResult.path`/`.skipped` -> `.file` (`VersionedFile`) and
    `.stale`. What to do: `force=True` -> `update="force"`, read the path
    from `result.file.path`, skipping from `result.file.status == "local"`.
  - PL cutout from WCS: `bbox/<coords>.tif` without a date in the name is a hard link
    to a version in `versions/bbox/<YYYY-MM-DD>_<sha8>/`; by default and with
    `--upgrade` a local version without PRG and WCS queries (previously every
    call downloaded), `--force` downloads again (the same content =
    unchanged). Files `<coords>_<YYYYMMDD>.tif` from 0.7.x are not recognised.
    `PlCutoutResult.path`/`.skipped` -> `.file` and `.stale`;
    `run_pl_wcs_cutout(today=)` -> `now=` (+ `update=`, `plan=`),
    `download_pl_cutout(..., update=)`; `dated_cutout_path` removed. What to
    do: read the path from `result.file.path`; download again only
    via `update="force"`/`--force`; remove old dated files manually.
  - An old plain 0.7.x file at a LAZ/CZ/cutout path is replaced by
    a hard link to the new version on the first download (D24). What to do:
    nothing (copies outside the store are not touched).
  - `download_cz_cutout`, `download_cz_sheet`, `download_pl_cutout`: the result's
    `file` field is `None` only with `plan=`, when the plan does not execute that
    file and there is no local version. What to do: when executing a plan
    check `result.file is None`.
  - `PlanItem.sheet` -> `PlanItem.unit`, new field `track` (`pl_sheet`,
    `laz_tile`, `cz_sheet`, `pl_cutout`, `cz_cutout`); `PlanItem`/
    `UpdatePlan` in `kartograf.download.plan` (export from `kartograf` unchanged),
    `UpdateMode` in `kartograf.download.fetch`. The plan schema
    stays `kartograf-plan/1`. What to do: `item.sheet` -> `item.unit`;
    switch imports from `kartograf.download.updates`/`manager` to
    `kartograf`.
  - `DownloadManager.download_bbox` removed (D27, erratum 2 of ADR-003). What to
    do: for an NMT/NMPT cutout in the store — `download_pl_cutout(bbox=bbox,
    horizontal_crs="EPSG:2180", ...)`; for raw WCS (e.g. orthophoto)
    outside the store — `provider.download_bbox(bbox, path)`.
  - CLI `elevation download` (LAZ, CZ and cutouts): instead of `Downloaded to ...`/`Skipped ...`
    one status line per file (`<sheet|cutout path|LAZ file>:
    nowa wersja ...` / `lokalna wersja ...`), for LAZ a summary of
    counters; a file without a cheap signal (TM33, cutouts) gets
    `(bez sprawdzania; --check-updates)`. What to do: switch scripts parsing
    the output to the new lines.
  - Sidecar: `downloaded_at` with microseconds (ordering of two downloads
    in the same second). What to do: ISO 8601 parsers unchanged.
- Versioned store for land cover and HSG (ADR-036 D29-D33):
  - Layout: files `bdot10k_..._teryt_<T>.gpkg`, `corine_<year>_sheet_<sheet_code>.png`,
    `soilgrids_<wl>_<gl>_<stat>_bbox_<coords>.tif`, `hsg_<sheet_code>_<depth>.tif`
    -> spec 3.4 segments with versions: `landcover/pl_bdot10k_gpkg[_<layers>]/teryt/<T>.gpkg`
    (`keep_raw`: `landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip`, SHP:
    `landcover/pl_bdot10k_shp/teryt/<T>.zip`), `landcover/eu_corine_<year>/...tif`
    (CLMS), `landcover/eu_corine_<year>_preview/...png` (WMS preview without
    credentials), `soil/global_soilgrids_<wl>_<gl>_<stat>/...tif`,
    `hsg/global_soilgrids_<gl>_<stat>/...tif`; under the segment `teryt/<T>`,
    `bbox/<coords>` (EPSG:2180, like cutouts) or the sheet code hierarchy. No
    migration. What to do: download again into the store directory (`--output`)
    and read the path from the status line / `report.files[0].file.path`; delete the old
    files manually.
  - Land cover, SoilGrids and HSG write to the store only:
    `output_path` removed, `output_dir` required, `keep_intermediate`
    removed (the clay/sand/silt inputs are SoilGrids versions in the store).
    The result is a `LandCoverReport`, `SoilReport` or `HsgReport` report
    (the former internal `LandCoverResult`/`LandCoverAreaResult`/`HsgResult`
    are not public). What to do: `download_landcover(product=...,
    output_dir=<store root>, teryt=|sheet=|bbox=|geometry=)` without
    `output_path`, files from `report.files`, raw ZIP in `report.raw`;
    `calculate_hsg(output_dir=<store root>, bbox=bbox, depth=...)`
    returns the raster in `report.files[0].file`, the inputs in `report.inputs`.
    File outside the store: `provider.download_by_*(..., output_path)`
    or `hsg_from_rasters`.
  - Land cover and SoilGrids do not download an existing file again:
    the default mode takes the local version without querying for a release; a signal
    without a cheap check gives `(bez sprawdzania; --check-updates)`.
    `--check-updates`/`--upgrade` check the SoilGrids and CORINE CLMS release,
    `--upgrade` downloads newer content. New versions are labelled with the release
    (`2.0`, `V2020_20u1`); without a release none are created. What to do: to
    download again — `--force` / `update="force"`, for a newer release — `--upgrade`.
  - `download_landcover` does not stop at the first county error:
    `LandCoverReport.failed` contains its `UnitFailure`; the CLI prints
    `Error: <TERYT>: ...` for each error and exits with code 1. What to do:
    check `report.failed` and `report.ok` instead of catching a file exception.
  - `extra.source.raw_file` (BDOT10k `keep_raw`) replaced by
    `extra.source_files` (`name`, `file` = path of the ZIP version relative to
    `--output`, `sha256`). HSG sidecar: `extra.source_files` with `file`,
    `sha256`, `label` of the inputs; `request` = selection (without `bbox` for a sheet).
    What to do: read `extra.source_files[].file` (path relative to
    `--output`) and `sha256` instead of `extra.source.raw_file`.
  - CLI `landcover download` and `soil hsg`: instead of `Downloaded to:` /
    `HSG raster saved to:` a status line per file (path relative to
    `--output`); `soil hsg --output` only a store directory (`.tif` =
    `Error:`), `--keep-intermediate` removed. What to do: switch scripts parsing
    the output to the status lines.
  - `SourceDescriptor.storage_subdir` is always a `str` (land cover:
    segment prefix); `CorineProvider.CLMS_DATASET_UIDS`/
    `CLMS_RASTER_DOWNLOAD_IDS` 2012/2006/2000 changed to identifiers
    from the CLMS catalogue. What to do: nothing.
- Library argument types are checked on input, without conversion
  (STANDARDS 11.2, `kartograf/download/arguments.py`): `download_data`/
  `check_data`, `download_landcover`/`check_landcover` (also the BDOT10k archive
  `year`), `calculate_hsg`/`check_hsg`,
  `download_collection`/`check_collection`, `check_availability`,
  `DownloadManager` and `download_laz_area`/`check_laz_area` raise
  `ValidationError` before the network for a number given as a string
  (`year="2018"`, `timeout="120"`, `workers="4"`, `min_density="10"`,
  `lod="1"`), a non-integer number or `bool` where an `int` was expected
  (`year=2018.0`), a switch other than `True`/`False` (`cutout`,
  `all_campaigns`, `full_sheet`, `keep_raw`, `whole_country`, `force`),
  `timeout <= 0` and `layers` given as a string (`"SWRS,PTWP"` was read
  character by character); `download_collection`/`check_collection`/
  `validate_collection_request` accept `teryt`, `sheet`, `ku`, `format`,
  `scale`, `sheet_system` and `network` only as `str` (ADR-043 D5: a code
  given as a number loses leading zeros, e.g. `0208`). Until now some of them worked
  by accident, some ended with a late `ValueError` from `urllib3` or
  `TypeError`. CLI flags unchanged. What to do: pass `int` (`timeout`
  also `float`), `True`/`False`, codes as `str` (`teryt="1261"`)
  and a list/tuple of codes (`layers=["SWRS", "PTWP"]`).
- 0.8.0 UX review, CLI help: `hydro download` has no `--workers`/`-w`
  (an area is one GeoPackage, a national file is one file; the flag changed nothing);
  the `--country` of a collection offers only the countries of the group's products
  and `auto` (`hydro`: `cz`, `auto`; `models3d`: `pl`, `auto`) - `hydro
  --country pl` and `models3d --country cz` are a parser error (code 2) instead of a
  library error. `list-sources` has a `KATALOG` column (directory of files under
  `--output`), and `WYBOR` - the complete set of required flags of the source (`--country`
  also for PL in `elevation`/`imagery`, `--vertical-crs EVRF2007|KRON86`,
  `landcover --year` BDOO and CORINE; `soil`: `--property --depth --stat`).
  What to do: remove `-w`/`--workers` from `hydro download` commands (in a project:
  `project download --workers` works as before); scripts reading
  `list-sources` by columns - take `KATALOG` and the new `WYBOR` flags into account.
- Input errors end the CLI with code 2, not 1 (interface for AI agents, ADR-046;
  added to the prepared 0.8.0 release before tagging):
  `ValidationError`, `ParseError`, `UsageError` and a parser syntax error (argparse
  already ended with 2 before). Exit codes: 0 = ok, 1 = source, network
  or disk failure or `ok: false`, 2 = incorrect input data and usage, 130 = Ctrl-C.
  Handlers do not print their own `Error:` nor return 1 for a missing `--output`,
  `--product` and the like: they raise `ValidationError` with `option`, and `main` translates
  it. Error text unchanged apart from three details: `Remedium:` under the
  CRS conversion error is printed by `main` for every command (until now only
  `elevation`/`imagery download`), an unreadable `--plan` file is an input error
  (`option: plan`, code 2), and a plan write error is `Error: <Type>: <text>` (code 1).
  What to do: scripts checking `== 1` should test `!= 0`; 2 means "fix the input
  data", 1 - failures or `ok: false` (code table: USAGE 9.3).
- `AvailabilityReport.to_json()` and `UpdatePlan.to_json()` (the `--plan` file,
  `--check-updates --json`) have `schema` as the first key (until now the last);
  the dataclass field `schema` of both types was replaced by a class constant (`AvailabilityReport(
  schema=...)` and `dataclasses.replace(plan, schema=...)` do not work);
  `UpdatePlan` gained the fields `notices` (notices emitted during the check)
  and `ok` (two new keys of `kartograf-plan/1`), and `UpdatePlan.from_dict` rejects
  an unknown schema. Plans saved by 0.8.0-dev still load. What to
  do: read the JSON files by key, not by position; do not build these
  reports with `schema=`.
- `--json` silences `Info:` and `Warning:` on stderr: the notices are in the
  `notices` field of the document, and `elevation availability --json` stops duplicating them
  (stderr is empty apart from HTTP retry lines). What to do: agents and scripts
  reading stderr read `notices` from the document.
- The CLI parser is built from the command catalog (`kartograf/catalog/commands/`): the
  modules `kartograf/cli/groups/*.py`, the flags in `cli/_args.py` and the functions
  `download_task_arguments`, `_download_arguments`, `collection_task`,
  `area_task_arguments`, `landcover_task_arguments`,
  `soil_download_task_arguments` and `soil_hsg_task_arguments` disappear;
  `kartograf.cli.commands` does not export `format_sheet_info`,
  `format_hierarchy`, `format_children` or `format_descendants` (there is
  `format_sheet(describe_sheet(...))`), `cmd_cache` takes `action`, and
  `cmd_landcover_list_layers` and `cmd_soil_list_layers` replaced
  `cmd_list_layers`. `create_parser`, `main`, `parse_command_line`,
  `removed_command_error` and `_subparsers` (facade) remain. What to do: code and tests
  importing CLI internals use `parse_command(...).options` or
  `create_parser()`; a handler's hand-built `argparse.Namespace` must carry
  `_command_id`; a new command is a declaration in the catalog (STANDARDS 17.2).
- E2E test 2026-10-19 (clean install, all command groups; errata
  ADR-018, 036, 040-042, 043-047): behaviour changes of existing commands and
  API.
  - `--bbox` in every command with an area (elevation, imagery, collections,
    landcover, soil, hsg, availability, cutouts, LAZ): coordinates outside the
    EPSG:4326 range (longitude +-180, latitude +-90; e.g. metres with
    `--bbox-crs EPSG:4326`) and a bbox with zero area (`min == max`)
    are a `ValidationError` (code 2, `details.option=bbox`, hint
    about `--bbox-crs` and axis order) before the network; until now `OverflowError`,
    `ValueError`, a query with `inf` or a 1 x 1 px file. `--bbox x,y,x,y`
    (a point) is not accepted. A point (or a line parallel to an axis) in
    `--geometry` selects the sheets, units and pixels it lies in
    (NMT/orthophoto sheets, `boundaries`, `soil download`, `landcover` BDOT10k),
    but the cutout (`--cutout`, PL and CZ), LAZ tiles, `soil hsg` and `elevation
    availability` work on an area: `Error: --geometry: obwiednia
    obiektow ma zerowa powierzchnie ...` (code 2, `details.option=geometry`;
    until now a notice about `bbox`, and `validate_data_request`/`project add` did not
    catch it). What to do: for these commands pass a polygon or
    `--bbox` with a positive area.
  - `--workers 0` and negative values in every command with `--workers` (CLI
    and library: `download_data`, `download_landcover`, collections, LAZ PL
    and CZ, `DownloadManager`, `download_project`) are a `ValidationError` (code
    2, `option=workers`, `... musi byc >= 1, podano N`); until now
    `elevation`/`imagery`/`landcover` and `DownloadManager` silently
    accepted 1. What to do: pass `--workers >= 1`.
  - `--check-updates` and the plan (`check_data`, `project download
    --check-updates`) treat a sheet without data in the sheet index like a
    download: it is a data state, not a plan item (until now `check_failed`
    and code 1). An area with coverage gaps gives code 0 and `Warning: GUGiK nie
    ma danych dla N z M arkuszy ...` (`no_coverage_some`); no data
    in any sheet is a `NoCoverageError` (`no_coverage`, code 1);
    sheets with data only outside the year range give one `year_out_of_range`
    for all sheets (until now `check_failed` per sheet); `check_failed`
    remains for sheet index failures. `DownloadManager.check_sheets(sheets, *,
    on_no_coverage=None)`. What to do: code reading `check_failed` from the plan
    as no data checks the `Notice` `no_coverage_some` and the error codes.
  - `failed[].kind` in `kartograf-download/1` (`UnitFailure.kind`):
    a single `--sheet` without a record is `no_coverage` (until now `download`),
    the new value `year_out_of_range` (code `YearRangeError`) for a year
    conflict also in LAZ and `--country auto` (until now `download`/`country`).
    What to do: code comparing `kind` with `download` handles the new values.
  - `--country auto` in collections (`boundaries`, `cadastre`, `names`,
    `maps`, `geodesy`): partial success (a country with errors alongside a country without
    errors) ends with code 0 and a `Warning:` `auto_partial_success` (the same
    rule as `elevation` and `imagery`; until now code 1), the entries remain
    in `failed`, and the CLI prints `Error:` as before; code 1 remains for an explicit
    `--country`, a single country and failure of all countries. A country without
    area units or with a failed units query does not abort the
    task (until now `Error:` without downloading the second country). What to do:
    scripts checking code 1 for partial success read `failed`
    and `notices`.
  - Exit code 143 and error code `terminated`: SIGTERM in the CLI acts like
    Ctrl-C (until now the process died without a message); 130 remains for SIGINT.
    What to do: a script handling codes 0/1/2/130 adds 143.
  - Store reading: `Sidecar.unit` of a LAZ tile is its sheet code
    (`extra.tile_sheet`), not the task area `<coords>` from `request.bbox`
    (until now `iter_store(units=[unit])` did not find the tile), and the tile's
    `file_footprint` takes the outline from the LAS header (without a readable
    header: `None`, not the task area); in a segment of sheets only
    (ZTM) the bare number (`0510`) is a sheet, not a TERYT. Sidecar format
    unchanged. What to do: code grouping tiles by `Sidecar.unit` gets the tile
    sheet codes instead of a common area.
  - `link_target(sciezka)` and `linked_version` for a file with the content of a version
    that is not a link (an independent copy, e.g. after `rsync -a` without
    `-H`) return that version (until now `None`); a download turns such a copy
    back into a link to the same version, never another. What to do:
    code computing "space saving" from `link_target` checks the link count
    (`os.stat`) separately.
  - `file_footprint` no longer raises `TransformUnavailableError`/
    `TransformError`: a source whose envelope cannot be safely
    converted to WGS84 is skipped and the next one decides (task
    bbox, sheet code, header, unit), and when none remains - the
    result is `None`. Until now the first error aborted the call
    (`names` entries `geographic`/`world` and `boundaries` `special`
    with `request.bbox_crs` = `OGC:CRS84`, PROJ 9.8.1). What to do:
    code wrapping `file_footprint` in `try/except TransformError`
    can remove it; `None` means "no reliable outline".

### Added

- Sheet and campaign details in the availability report (KD-1, KD-2; ADR-047;
  added to the prepared 0.8.0 release before tagging): new fields of
  `AvailabilityCombination` - `full_m2` (land within full sheets, lower
  bound; in PL `complete` if and only if `full_m2 == land_m2`; CZ:
  area within sheets with a file - a complete combination may have
  `full_m2 < land_m2` when the area extends beyond the index sheets),
  `sheet_records` (records that `download_hint` downloads: `sheet`,
  `campaign`, `acquisition_date`, `published`, `full_sheet`, `url` - NMT/NMPT
  the latest sheet record and, with `--full-sheet`, the latest full one; LAZ tiles
  of the coverage selection from among the combination's tiles; LAZ limitation: the command does
  not have a sheet system and selects from PL-1992 and PL-2000 tiles at once, so for a year
  with both systems the downloaded tiles may differ from `sheet_records`)
  and `campaign_coverage` (each campaign separately: `complete`, `full_m2`); new
  types `AvailabilityRecord`, `AvailabilityCampaign` in `kartograf.__all__`;
  schema `kartograf-availability/1` additively.
  `kartograf elevation availability --details` adds in PL the share of land
  in full sheets (rounded down, `<1%`), campaigns separately and the campaigns of records to
  download.

- Interface for AI agents, JSON documents (ADR-046, USAGE 9; added to the
  prepared 0.8.0 release before tagging): `--json` in every CLI command
  (36 leaf commands and `catalog`) - stdout is exactly one document
  `kartograf-<kind>/1` (16 schemas, first key `schema`), without a progress bar
  and status line; an error is `kartograf-error/1` on stdout (also a syntax
  error), stderr empty. The documents are produced by the library: every report
  has `to_dict()` and `to_json()` (the `Document` mixin in `kartograf.serialization`, outside
  `__all__`), and the CLI and the MCP server only print them; within `/1` changes
  are additive. New in `kartograf.__all__` (the logic of `parse`, `list-sources`,
  `list-layers` and `cache` moved from the CLI to the library):
  `describe_sheet`/`SheetInfo`, `find_sheets`/`SheetList`, `list_sources`/`SourceList`,
  `list_layers`/`LayerList`, `get_cache_info`, `get_cache_path` (does not open the
  database), `clear_cache`/`CacheInfo`, `describe_store`/`StoreOverview`,
  `list_store_entries`/`StoreEntries`, `read_store_sidecar`/`StoreSidecar`,
  `ErrorReport`/`error_report`.

- Stable error codes with a hint (ADR-046): every `KartografError` has
  `code` (snake_case, unique), `exit_code`, `hint` and `DETAIL_FIELDS`/
  `details()`; `ValidationError` carries `option`, `options` and `allowed` (the name of the
  API argument, not a flag); the new class `UsageError` (subclass of `ValidationError`,
  attribute `command`) is incorrect use of a command; `OSError` (missing, permissions,
  detached share) has the new code `io_error`, and `KeyboardInterrupt` and other exceptions
  `interrupted` and `internal_error` (built by `error_report`). `hint` contains the
  allowed values and a command example from the catalog, and for an error with `options` (e.g. missing
  area) the flags of those options and an example; a plan of another store is a `ValidationError` with
  `option="plan"`. One table of exit codes
  and errors: USAGE 9.3 (`tests/test_docs_tables.py` checks that it is equal to the
  catalog). The attributes are additive: `except ValidationError` also catches
  `UsageError`, constructors accept new arguments as keyword-only.

- Command catalog (ADR-046): `kartograf catalog [GROUP [COMMAND]] [--params]
  [--json]` and `get_catalog(group=, command=, params=, tables=)`
  (`kartograf-catalog/1`): groups, products, commands, parameters (flag, API
  argument, kind, requirement, allowed values, dependencies), constraints and
  examples; by default a concise overview (approx. 7.6 thousand characters), the rest on
  request (group, command, `--params`, `tables=True`). `data_commands()` returns
  12 data commands; types `Catalog`, `CommandInfo`, `ParamInfo`; `CommandInfo.check_tool`
  (`full` view) indicates the MCP tool that checks the command (`check_updates` or
  `project_check_updates`). The catalog is
  the single source of truth: the declarations in `kartograf/catalog/commands/` produce
  the CLI parser, the project data command options and the MCP tool schemas, and the contract
  tests check the consistency of flags, signatures, `COMMANDS` and examples.

- Command layer for Archiwista (KB-2..KB-5, ADR-046): `parse_command`,
  `validate_command`, `format_command`, `run_command`, `check_command` and
  `CommandCall` - a data command as data (options in the form of JSON of project task
  options), validation without network and writes, execution by the command function and a freshness
  check. `parse_command` also accepts a line with a leading `kartograf ` (as
  `format_command` writes it).

- MCP server `kartograf-mcp` (ADR-046, USAGE 9.6): optional extra
  `kartograf[mcp]` (`mcp>=2.3.0,<3`, stdio, also `python -m kartograf.mcp_server`),
  29 tools 1:1 with the catalog commands and one `check_updates` for 12 data commands;
  the tool result is a `--json` document, `is_error` = CLI exit code != 0, input
  schemas from the catalog, absolute paths, no defaults affecting
  data (`output_dir` explicit, `bbox` with `bbox_crs`), progress via MCP notifications,
  options `--tools`, `--allow-dir` (absolute directory; a relative one ends startup with a usage error,
  code 2), `--cache-file`, `--no-cache` (a cache directory that cannot be
  created gives a warning and work without cache, as in the CLI); `tools/list` is
  approx. 28.6 thousand characters. `import kartograf` and the CLI do not require `mcp`; `dev` includes
  `mcp`.

- Files for agents (ADR-046): `kartograf/py.typed` (PEP 561, `Typing :: Typed`;
  the consumer's `mypy` sees the library types; the whole public API (`kartograf.__all__`)
  has full, precise annotations - `PinnedTransform.transform` has overloads
  (scalars and numpy arrays), `cache` is `MetadataCache | None`, dictionaries are
  `dict[str, Any]`, and `CampaignRef.from_record` accepts the protocol
  `IndexRecord`; this is checked by `tests/test_typing_consumer.py`: `mypy --strict`
  on a consumer module and an `inspect` review), `llms.txt` (index for agents, llmstxt.org
  format), `scripts/gate.sh` (one gate command: ruff check, ruff format
  --check, mypy, offline pytest; also works from a worktree), `python -m kartograf`
  and a rule for agents from other repositories in `CLAUDE.md` (branch from `develop`,
  no merges, tags or release entries without consent, review before the tag).

- Public store read API for Archiwista (KA-1..KA-6, ADR-045;
  added to the prepared 0.8.0 release before tagging, ARCHITECTURE
  3.3.1): `list_segments` (`<product>/<variant>` segments, also
  unknown ones), `iter_store` (streaming scan of versions, both kinds of links
  and problems; `segment`, `units` - only the slots of the given units, without
  listing the segment - and `skip_versions` - known version directories without
  reading their sidecars, for an incremental scan; one sidecar read per
  file, no `stat` and without opening data files; parallel calls
  in threads), `read_sidecar` (tolerant read of older metadata
  and 0.8.0-dev keys, the data year never from the download date; error:
  `InvalidSidecarError`; a sidecar without the `schema` field written by
  `emit_sidecar` for a provider without a descriptor is accepted as in
  `read_version`; `Sidecar.unit` of a national file with a theme is
  `<country>_<theme>`, e.g. `pl_miejscowosci`, i.e. the name accepted by
  `iter_store(units=...)`), `describe_segment` (human name and source
  of the segment from the registry, `known=False` without guessing), `file_footprint`
  (native and WGS84 outline from the task bbox, sheet code, header or unit;
  network only with an explicit `network=True`; an SM5 sheet unknown to the index has no
  outline, like an unknown TERYT and KU), `link_target` (confirmation of the target
  also on SMB without stable inodes) and `pinned_transform` (an operation without
  approximations, per thread). Types `StoreEntry`, `Sidecar`, `SegmentInfo`,
  `Footprint`, `PinnedTransform` and the exception `InvalidSidecarError` are
  in `kartograf.__all__`; `StoreEntry` and `Sidecar` are unhashable. The functions do not write to the store; the consumer's cache and index
  belong to its local directory. The schema `kartograf-meta/1`
  and the layout of existing files do not change.
- Store read: parallel parts of one segment and a faster scan
  (ADR-045, ARCHITECTURE 3.3.1; Archiwista v0.1 measurement - the largest segment
  read by a single thread). `list_partitions(output_dir, segment, *,
  target=32)` splits a segment into disjoint parts: `"."` (segment level:
  its problems and files directly in it and in `full_sheet/`),
  `"<dir>[/<dir>...]"` (a slot and all slots under it - in the standard path,
  `full_sheet/` and `versions/`) and `"<dir>/."` (only the slot of a directory
  split further); `iter_store(..., segment=..., partition=...)`
  reads one part, and the sum of the parts is exactly the segment scan (without
  repetitions; parts in separate threads). `skip_versions` also accepts a
  mapping `version directory -> data file names`: such a directory is not
  even listed, the caller vouches for its contents (a set works as
  before). A scan without `pathlib` in the loop and with cheaper sidecar typing -
  Archiwista test store (50 thousand slots, SSD): incremental scan 12.4
  -> 6.3 s (with the mapping 5.2 s), full 20.3 -> 10.1 s, result unchanged
  with one intended exception: a `units` scan skips hidden version directories
  (`.<label>_<sha8>`) like the full scan (previously it read them).

- Store read - guarantees written down for consumers (Archiwista's remarks):
  stability of the source key (KA-8: the `dataset` key unchanged after release,
  renaming only through the reader's alias table and `dataset_key`, the provider
  in the `provider` field; ARCHITECTURE 3.3, rule 10) and thread safety
  (`file_footprint` and `pinned_transform` from a thread pool, a shared `cache`
  as a plain `dict`; docstrings, ADR-045, a parallel-use test).

- `Info:` before slow services (live test 2026-10-16): a PL NMT/NMPT cutout
  from several WCS requests gives an estimated time (`CUTOUT_SIZE`:
  `... 16 zapytan WCS GUGiK pobieranych po kolei - ok. 7-11 min (25-40 s
  na zapytanie wg pomiaru)`, constant `WCS_REQUEST_SECONDS`), a PRNG
  area request (`names download --product geographic|world`) - the measured
  OGC API response time (`SLOW_SOURCE`, `FeatureBBoxParams.response_note`).
- UX review 0.8.0, input values: `--country`, `--format`,
  `--vertical-crs` and CRS codes (`--bbox-crs`, `--horizontal-crs`, `BBox`
  CRS) in any letter case (`--country PL`, `--format shp`,
  `--vertical-crs evrf2007`/`bpv`, `epsg:2180`) - the CLI and the library (data commands
  and functions with `bbox`) accept the registry spelling; an unknown value is
  given in the message as it was entered. `geodesy download --network`
  in per-country syntax like `--level` (`pl=horizontal,cz=gnss`; API `network=
  {"pl": ..., "cz": ...}`, manifest: a string or an object per country). A
  single-country source option (`maps --sheet-system sjtsk|etrs89`, ZTM CZ) applies
  under `--country auto` to the part of that country; for the other country alone it is
  an error naming the country that has it (previously "not applicable" also for an
  area near the border that could not be downloaded). What to do: nothing.
- Collection progress: `download_collection(on_progress=)` and a progress bar
  (like the sheet list: `>` before the transfer, `+` downloaded, `o` local, `x`
  error) in `boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`
  and `geodesy download`, in the `landcover` collection sources (ZABAGED, BDOO,
  Data50, Data250) and NMT 100 m files - for a task with many
  units (one unit: a status line and a `Warning` with the size of a
  large file); `-q` hides the bar. The project passes progress to collection
  tasks.
- Documentation: USAGE 2 - a table of all `Notice` codes (code, level,
  when, commands); `sheet_list` (`download_data`, header on stdout)
  and `unit_list` (collections, also map sheets and control network archives) described
  as two printouts of the same list of units.
- 3D mesh, trees, geodetic control networks and quasi-geoids (ADR-043): `models3d download
  --product mesh` (GUGiK city mesh models: tiles of the WFS index of the area,
  ZIP OBJ+MTL+JPG 1:1
  in `models3d/pl_mesh/<zone>/<record file>.zip`, CRS from the record,
  heights EPSG:9651, label = date and report number of the work, signal
  `index` in `--check-updates`; tile = record file, `--year` filters
  records) and `--product trees` (CityGML LoD1 2023 trees, county package
  0.3-25 GB, a `Warning` with the size before the transfer). New group `geodesy`
  (`download`, `list-sources`): `--product control --network ...` - PL control networks
  (WFS of the `horizontal`, `vertical`, `gravity`, `magnetic` networks to the GPKG of the
  area; county packages of the horizontal and vertical network `--teryt`;
  archives of 1:100 000 sheets `archive-1942`, `archive-kronsztadt60`) and CZ
  (Bodove pole: `gnss`, `horizontal`, `densification`,
  `horizontal-detailed`, `vertical`, `vertical-detailed`, `gravity`; a network
  = the sum of its layers), `--product geoid --whole-country` - PL-geoid2021 (TXT
  1:1) and QGZU-2013 (ZIP from the ATOM feed, release from the feed). Manifest entry
  of `geodesy download` (`network`, `whole_country`). An option value available
  only in another selection names that selection (`--teryt` with `--network gravity`),
  and a PL+CZ task without `--network` gives the values of both countries and the common ones.
  Examples and live results: USAGE 1.11, `docs/research/2026-10-16-plan-e5-e2e/raport.md`.
- Collection area limit (ADR-043 erratum 3): an area (`--bbox`/`--sheet`/
  `--geometry`) in `boundaries`, `cadastre`, `models3d`, `hydro`, `names`,
  `maps`, `geodesy`, in the `landcover` collection sources (ZABAGED, BDOO,
  Data50, Data250) and NMT 100 m that would download more than 100 files or
  more than 10 GB (sum of `HEAD`/lengths from the ATOM feed; above 100 files -
  an estimate from 5 files) ends with `Error:`/`ValidationError` before the
  first transfer, with the file count, the size and a hint: narrow the
  area, choose a unit (`--teryt`, `--ku` - no limit) or execute a
  plan with a part of the items (`--check-updates --plan PLIK`, then `--upgrade
  --plan PLIK`). Files without a local version are counted (`--force`:
  all, `--upgrade --plan`: the plan items); there is no bypass option.
- BDOO, Data50 and Data250 (ADR-043): three `landcover download
  --product` products.
  `bdoo` (BDOO GUGiK, 1:250 000): a voivodeship (Polish województwo) GML package per
  vintage (`--year` required: 2015, 2021-2026; `--teryt` 2 digits, a county code =
  `Error:` with the hint `--teryt <woj>`; an area `--bbox`/`--sheet`/
  `--geometry` = the voivodeship packages of its counties from PRG, `Info` with a list,
  a voivodeship without a package in `failed`, `--workers`, a summary line)
  saved 1:1 in `landcover/pl_bdoo_<year>/teryt/<woj>.zip` with a
  vintage label; `--layers` (classes of the vintage, `landcover list-layers --product
  bdoo`) saves a ZIP of `__OT_<CODE>_<type>` files of the selected classes (members
  byte for byte, `pl_bdoo_<year>_<classes>`), a class without a file in the package = `Info`
  `classes_absent` (new `Notice` code), all missing = a voivodeship error,
  a class outside the vintage = `Error:`. `data50` and `data250` (CUZK): an area =
  one GeoPackage of all feature layers of the REST service (69 and 116)
  in EPSG:5514, `--whole-country --horizontal-crs EPSG:5514|EPSG:3045` =
  a national SHP ZIP from the ATOM feed 1:1 (release from the feed, size in `Warning`
  before the transfer). Engines: `PackageVariant.classes`,
  `UnitPackageParams.class_pattern`; the area of a product with voivodeship packages only
  gives the voivodeship packages of the area. Examples and live results:
  USAGE 1.5 and 1.9, `docs/research/2026-10-16-plan-e4-e2e/raport.md`.
- PRG addresses and special boundaries, RCN, geomorphology and the CZ cadastral map
  (ADR-043): the `boundaries` and `cadastre` groups get
  the products `boundaries download --product addresses|special|geomorphology`
  and `cadastre download --product map --country cz|prices`, the flags
  `--format` (national files and cadastral map formats) and `--ku`
  (6 digits, CZ only). PRG addresses: points and streets of the area (GPKG EPSG:2180),
  a county SHP package (`--teryt` 4 digits) or a national file
  (`--whole-country --format SHP|GML`). PRG special boundaries: 44 kinds
  from OGC API PRG (GPKG OGC:CRS84) or a national SHP/GML file; census districts
  (`GranicaObwoduSpisowego`) are not in the area result - `Info`
  (`AREA_OMITTED`) points to the national file. CZ geomorphology: units
  of the `--level` level (`subprovincie`...`cast`). RCN: a county or
  voivodeship export (GPKG with three layers, unpacked from the ZIP locally,
  layer check). CZ cadastral map: a KU package in SHP, DXF, DGN or VFK
  (KU of the area from RUIAN; HTTP signal); VKM outside 0.8.0. Project manifest
  tasks for both groups accept `format` and `ku`. Examples and live results:
  USAGE 1.8 and 1.9, `docs/research/2026-10-16-plan-e3-e2e/raport.md`.
- Geographic names and topographic maps (ADR-043): the groups `kartograf
  names` and `kartograf maps` with
  `download`/`list-sources`, the shared library function
  `download_collection`/`check_collection` and project manifest tasks.
  `names --product geographic --country pl` downloads PRNG RP as an area
  GPKG OGC:CRS84 (OGC API Features; large pages, timeout 180 s) or two
  national GML/SHP/XLSX ZIPs; `--product world --country pl` allows downloading
  Polish names of the world also outside Poland (an area and one national file).
  CUZK Geonames (`geographic --country cz`) provides 25 area layers in
  EPSG:5514 or a national GPKG/FGDB ZIP in EPSG:5514/3045 from the ATOM feed
  (release from `updated`, `metadata` signal). Areas have no cheap signal.
  `maps --product topographic --country pl` downloads ready BDOT10k
  visualisation sheets at scales 1:10000/25000/50000/100000 as TIFF or
  PDF (the `Stan bazy` date from the index as a signal); `--country cz` downloads ZTM
  at six scales, in the S-JTSK or ETRS89 sheet system recognised
  from the sheet code, and in TIFF/PDF formats (S-JTSK also DGN/SHP; formats other than
  PDF are ZIPs). ZTM sheets have an HTTP signal; the sidecar has the variant CRS
  EPSG:5514 or EPSG:3045. Separate store segments `data/names/`,
  `data/maps/`; examples and live results: USAGE 1.10 and the E2E report.
- ZABAGED contours from CUZK (ADR-043) in `elevation
  download --product contours --country cz --format SHP|DGN` (`--sheet`
  of an SM5 sheet, `--bbox`/`--geometry` = the SM5 sheets of the area from the index
  `KladyMapovychListu`): the sheet ZIP from openzu saved 1:1 (without
  unpacking or conversion; members and CRC checked before the version is written)
  in `contours/cz_zabaged_shp|dgn/<hierarchy SM5>/<sheet_code>.zip`, a sidecar
  with the list of ZIP members, `mapname`/`cz_share` from the index and `extra.http`;
  `http` signal (local version after a single `HEAD`, `--check-updates` without
  download, `cz_sheet` plan track). Descriptors
  `cz.cuzk.zabaged_contours_shp` and `cz.cuzk.zabaged_contours_dgn` (one
  format = one descriptor, like the GUGiK archives); `--format` required,
  `--vertical-crs` only `Bpv` (can be omitted); `--resolution`, `--cutout`,
  `--horizontal-crs`, `--sheet-system`, `--scale`, year and flight flags =
  `Error:` ("warstwice to arkusze SM5 (wektor) ..."); tile TM33 = `Error:`.
  `--country auto` for a single-country product narrows the area to that country
  (`Info:` `auto_narrowed_to_cz`/`auto_narrowed_to_pl`, as in collections;
  this also applies to intensity, true orthophoto and oblique orthophoto, previously `Error:`),
  and `--country pl` with contours is an `Error:` "... dostepny tylko dla CZ".
  The `--format` error text with another product mentions `contours (CZ)`.
- GUGiK images (ADR-043): three products
  in `imagery download` on the orthophoto sheet track (campaigns, versions,
  `--year`/`--all-campaigns`, `index` signal): `--product intensity`
  (LIDAR intensity images, `pl.gugik.intensity`, PL-1992 and PL-2000 sheets,
  `intensity/pl_<crs>/...`), `--product true-orto` (true
  orthophoto of selected cities, `pl.gugik.true_orto`, 8-member PL-1992 sheets in
  `true-orto/pl_1992/...`; `--cutout --horizontal-crs EPSG:2180
  --resolution 0.05m|0.1m|0.25m|0.5m|1m` = a cutout from WCS `True_Orthoimagery`
  in `true-orto/pl_1992_<pixel>/bbox/`, without `--coverage`) and `--product
  oblique-orto` (oblique orthophoto, `pl.gugik.oblique_orto`, PL-2000
  sheets; a sheet is four direction files `<sheet_code>_n|e|s|w.tif`
  in `oblique-orto/pl_2000/...`, a new flag `--direction n,e,s,w` /
  `direction=` in `download_data`/`check_data`, without the flag all
  four). A product with a single sheet system (true orto, oblique orto) may
  omit `--sheet-system`; `--full-sheet` only for oblique orto (the intensity
  and true orto records do not declare a full sheet). Image sheet indexes
  are described by the new channel parameter `SheetIndexParams` (layers, sheet
  systems, directions, extent); one provider `GugikImageProvider`
  (`GugikOrtoProvider` = orthophoto with colour variants). Project manifest:
  the `direction` option of the `imagery download` task. Result lines
  and `--check-updates` of a unit with several files (oblique orto directions,
  CZ orthophoto files) give the file name (`7.125.11.08_n.tif: aktualne
  ...`, `CTES96.TM33N.jgw`); `elevation availability --product` accepts
  only `nmt`, `nmpt`, `laz` (contours and NMT 100 m are outside the report).
- GUGiK NMT 100 m (ADR-043 D10; `pl.gugik.nmt_100m`, a registry variant without
  vertical CRS):
  `elevation download --product nmt --resolution 100m --bbox ... --country pl`
  (also `--sheet`, `--geometry`) downloads the voivodeship files of the area (by PRG)
  from the GUGiK ATOM feed to `nmt/pl_1992_100m/teryt/<woj>.zip` - a ZIP with an
  XYZ file 1:1, version = the `updated` date of the feed entry (`metadata` signal:
  `--check-updates` reads only the feeds), a sidecar with `vertical_crs: null`,
  `extra.vertical_crs_note` ("GUGiK nie deklaruje ukladu wysokosci ...")
  and `extra.source` (service feed, dataset feed, voivodeship code, URL,
  `length`). `--format` can be omitted (`XYZ` - the only value);
  `--vertical-crs`, `--sheet-system`, `--scale`, year and flight flags,
  `--full-sheet`, `--cutout`, `--horizontal-crs`, `--min-density`
  and `--country cz` = `Error:` before the network. The `atom_files` engine gets
  the `woj` group in `AtomFilesParams.entry_pattern` (voivodeship units
  of the area) and `force_https` (`http://` links of GUGiK feeds downloaded over
  `https` of the same host).
- 8-member PL-1992 sheet codes (ADR-043 D10)
  in `SheetParser` (quarters of a 7-member sheet, numbering 1-4 as above:
  `N-34-50-A-c-3-2-3`; Kartograf label `1:5000`, GUGiK: module 1:2500);
  `find_sheets_for_bbox(..., "1:5000", "1992")` gives 8-member sheet codes,
  `get_children()` of a 7-member sheet - its four quarters, new
  `series_scale(liczba_czlonow)` (GUGiK series by member count, not by
  label). `DownloadManager` expands a sheet code coarser than the provider's sheet level
  (`BaseProvider.sheet_scale`, NMT/NMPT/orto: 7 members), and downloads an
  8-member sheet code as a sheet: NMT 1 m 2019 grids published per
  quarter (1678 sheet index records) can be downloaded by `--sheet
  <8-member sheet code>` (hint `elevation availability`). The archive
  registry gets `ASCII-NMT 10m` EVRF2007 (`pl.gugik.nmt_ascii_nmt_10m`,
  215 8-member sheets; the ZIP contains points every 0.5 m, the sheet index declares
  10 m). Closes the ADR-041 limitation (records with 8-member sheet codes are
  no longer `Info:` in the availability report).
- Collection engines (ADR-043 D1-D9): a shared collection contract for the new
  ADR-043 products (no new products in the registry). The library functions
  `download_collection`/`check_collection`/`validate_collection_request`
  get `ku` (CZ cadastral area, 6 digits; area = KU from RUIAN), `format`,
  `scale`, `sheet_system` and `network` (values from the descriptors:
  choice of channel, e.g. one WFS service per network or one ATOM feed
  per format: `FeatureBBoxParams.choice`, `AtomFilesParams.choice`; or
  of a package variant). New units of the engine `unit_package`: sheets
  (PL-1992 series by the member count of the sheet code or the CUZK
  index layer `KladyMapovychListu` in the sheet code hierarchy), tiles
  from WFS records (latest record, `year` as a filter, CRS directory
  `1992/` or `2000/<zone>/`), KU (`ku/<code>`) and national file topics
  (`country/pl_<topic>`); file address from a template (`{sheet}`,
  `{ku}`, `{theme}`) or from an index record (GetFeatureInfo of the link
  table, `transport/index_records.py`); non-ZIP files (`file_kind` TIFF,
  PDF, TXT) checked by content. The `index` signal compares the record
  label (e.g. the database state date) with the local version without
  downloading; exactly the channel with a record index has it. Channels
  of one kind (a service per network) may share a capability if they
  declare the same CRSs (sidecar). `feature_bbox` supports OGC API Features
  (CRS84, pages by `next`, check of `numberMatched`/`numberReturned`)
  with a separate channel time limit (`FeatureBBoxParams.timeout`; the
  GUGiK OGC API PRNG responds in 78-95 s per page). A file above 100
  MiB (a package or a collection unit file, an ATOM unit file, a GUGiK
  image sheet and orthophoto) gets the `Notice` `DOWNLOAD_SIZE` with
  the size (from `HEAD` or the ATOM feed) before its download (national
  file: `WHOLE_COUNTRY_SIZE`); therefore there is one `HEAD` request
  before every package download, including the products of plans C/D.
- The `hydro` group (plan D, ADR-042 D16): `kartograf hydro download --product
  network --country cz` - the CUZK HY-NET water network. An area (`--bbox`/
  `--geometry`) = one GeoPackage in EPSG:5514
  (`hydro/cz_hynet/bbox/<coords>.gpkg`) with 2 layers: `WatercourseLink`
  (watercourse segments) and `HydroNode` (nodes); `WatercourseSeparatedCrossing`
  is not an area layer (no geometry in GML, GeoServer returns `hits` 0 for BBOX
  despite objects), crossings are in the national file - an `Info` (`AREA_OMITTED`)
  of every area download reminds of this.
  `--whole-country --country cz` = `hydro/cz_hynet_gpkg/country/cz.zip`
  (GeoPackage in EPSG:3045, approx. 194 MB, `http` signal); `hydro
  list-sources`; library `download_collection(product="network", ...)`.
- ZABAGED in `landcover download --product zabaged` (ADR-042 D15): area =
  GeoPackage EPSG:5514 with 22 land cover and water layers
  (`landcover/cz_zabaged/bbox/<coords>.gpkg`; list: `landcover list-layers
  --product zabaged`), without converting classes to BDOT10k codes;
  `--whole-country --horizontal-crs EPSG:5514|EPSG:3045` = a national ZIP
  from the ATOM feed 1:1 (`landcover/cz_zabaged_gpkg_<epsg>/country/cz.zip`,
  5.8/6.7 GB, label = release date, `metadata` signal; layers under
  CUZK names, different from the area result - an `Info` `AREA_OMITTED` on
  every area download points to the national file). Library:
  `download_landcover(product="zabaged", output_dir=..., ...)`.
- RUIAN in `boundaries download --product admin --country cz|auto`
  (ADR-042 D17): `--level kraj|okres|obec|katastralni-uzemi` ->
  `boundaries/cz_ruian_<level>/bbox/<coords>.gpkg` (EPSG:5514);
  `--whole-country --country cz` -> `boundaries/cz_ruian_shp/country/cz.zip`
  (SHP, approx. 253 MB, `http`); under `auto` the level per country
  (`--level pl=gmina,cz=obec`, API `level={"pl": "gmina", "cz": "obec"}`)
  produces separate PRG and RUIAN files.
- Czechia orthophoto in `imagery download --product orto --country cz` (ADR-042
  D13): SM5 sheet (`--sheet CTES96`, `AS91`) or an area (SM5 sheets
  from the CUZK index) -> four CUZK ZIP files 1:1 in
  `orto/cz_sjtsk/<hierarchy SM5>/`: `<sheet_code>.jpg`, `.jgw` (EPSG:5514),
  `.TM33N.jgw` (EPSG:3045), `.TM34N.jgw` (EPSG:3046); JPEG sidecar with
  `extra.world_files`; current vintage only (archival CUZK orthophoto
  is paid); release from the ATOM feed (`metadata`, label
  `<year>_<updated>`, e.g. `2024_2025-02-06`). Library:
  `download_cz_orto_sheet`/`check_cz_orto_sheet` (`CzOrtoResult`), plan
  track `cz_orto`.
- PL orthophoto cutout in the store (ADR-042 D14): `imagery download
  --product orto --country pl --bbox|--geometry --cutout --horizontal-crs
  EPSG:2180 --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` ->
  `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif` (RGB from GUGiK WCS, without
  resampling, pixel-aligned and verified grid, chunks up to
  200 x 200 m, signal `none`; a cutout that is entirely 0,0,0, e.g. `high` outside
  the 10 cm areas, is an `Error:` without a version). Library:
  `download_image_cutout`/`check_image_cutout(..., product="orto",
  coverage=, resolution=)` (`ImageCutoutResult`; the same pair for true
  orto), `download_data(..., coverage=)`.
- Engine `atom_files` (ADR-042 D12, `kartograf/transport/atom.py`):
  files referenced by the CUZK ATOM feed (service feed -> dataset feed -> file),
  release from `updated`, feed index in the metadata cache (`atom_cache`
  with `ETag`, TTL 7 days, conditional GET on `--upgrade`/`--check-updates`,
  one refresh on a missing key or a 404 of the dataset feed).
- NMT/NMPT PL (ADR-041, plan A): NMT grids 0.15m, 0.5m, 0.6m and 10m and
  NMPT 0.5m and 0.6m (full list: `kartograf elevation list-sources`);
  GUGiK archives (`--format` XYZ, ASCII-NMT, TBD, TIN, TTN, GRD, DXF, DGN)
  downloaded 1:1 as source files with a sidecar and versions (without conversion,
  cutout or mosaic; the archive sheets for an area are determined by the sheet index).
  Availability report `kartograf elevation availability` /
  `check_availability` (`AvailabilityReport`, `AvailabilityCombination`,
  `AvailabilityArea`, JSON `kartograf-availability/1`): for which years,
  CRSs, resolutions, vertical CRSs and formats the area has a complete set
  of full NMT/NMPT sheets or LAZ tiles according to the WFS sheet index and the PRG land mask,
  without downloading data; download hint without `--output` (also
  after `kartograf project add NAME`). The hint does not plan a sheet without
  a combination record: when the area grid or the descendants of the sheet code have such
  a sheet (across the border - plan B E2E at Cieszyn, sea, missing year
  record), instead of an area command there is one `--sheet` per sheet
  with a record (previously `--check-updates` from the hint ended with `Brak
  danych` and exit code 1); the PL footer gives at most 5 commands and the count of
  the remaining ones, like CZ. Description: `docs/USAGE.md` 1.1 and 1.7.
  The project task `elevation download` stores the `format` option.
- Czechia in `elevation` (plan B, ADR-041): NMPT CZ - DMP OK 0.5m (SM5
  sheet and TM33 tile from CUZK files, cutout from ImageServer) and DMP 1G 2m (TM33
  tile and cutout from ImageServer); TM33 tiles DMR 4G/DMP OK in EVRF2007 as
  ready-made ETRS89 files (EPSG:3045, without transformation); CZ LAZ point clouds
  of four models: `--product laz --model dmr5g|dmr4g|dmp1g|dmpok` (API
  `model=`), `--vertical-crs Bpv` = SM5 sheets (EPSG:5514), `EVRF2007` =
  TM33 tiles (EPSG:3045), sheet code or area (sheets from the index
  `KladyMapovychListu`), `.laz` file 1:1 from the ZIP in
  `laz/cz_<model>_<vcrs>/`, signal `http`, plan track `cz_laz`.
  `--country auto` with LAZ downloads PL tiles and CZ sheets with a shared
  `extra.parent_request`; `--year`/`--min-year`/`--max-year`,
  `--all-campaigns` and `--min-density` then narrow the task to PL
  (`Info:`). Report `elevation availability --country cz|auto` /
  `check_availability(country="cz"|"auto")`: CZ combinations (model x
  `S-JTSK`/`ETRS89-TM33`) from the index sheets and one `HEAD` per file
  (publication date, size; without flight years and without downloading files),
  404 = sheet without a file, any other failure = error; `Notice` `cz_service_only`
  (DMR 5G, DMP 1G without sheet files), `AVAILABILITY_COUNTRIES` = `pl`,
  `cz`, `auto`, an unchecked `auto` part = `CHECK_FAILED` and `ok=False`
  (CLI exit code 1). Library: `CuzkRasterProvider`, `create_cz_raster_provider`,
  `CuzkLazProvider`, `download_cz_laz`/`check_cz_laz`, `CzLazResult`,
  `CzLazFailure` in `__all__`; `download_data`/`check_data(..., model=)`.
  Project: `--model` in the `elevation download` task. Description:
  `docs/USAGE.md` 1.4 and 1.7; E2E: `docs/research/2026-10-16-plan-b-e2e/raport.md`.
- GUGiK boundaries, cadastre and 3D building models (catalog plan C, ADR-042):
  CLI groups `boundaries` (`--product admin`, PRG: area objects from WFS
  with the required `--level wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`,
  voivodeship package `--teryt <2 digits>`, national file `--whole-country`),
  `cadastre` (`--product map`, EGiB: county export `--teryt <4 digits>`
  or parcels and buildings of an area from the WFS collective service) and `models3d`
  (`--product buildings`, CityGML: `--lod 1 --year 2019|2021|2022|2024`
  or `--lod 2`, county package or county packages of an area from PRG), each
  with `download` and `list-sources`, modes `--check-updates`/`--upgrade`/
  `--force`/`--plan`, `--workers` and `-q`. Files in the versioned store:
  `<group>/<country>_<source>[_<tokens>]/{teryt/<T>|bbox/<coords>|country/<code>}`
  (e.g. `boundaries/pl_prg_gmina/bbox/<coords>.gpkg`,
  `cadastre/pl_egib_gpkg/teryt/1261.gpkg`,
  `models3d/pl_buildings_lod1_2024/teryt/1261.zip`); the area result is one
  GeoPackage in the service CRS (EPSG:2180) with full geometries,
  completeness checked by the service object count; freshness signal `none`
  (new content: `--force`). Description: `docs/USAGE.md` 1.8, ARCHITECTURE 4.10.
- BDOT10k vintage archive: `landcover download --product bdot10k --year
  2014..2025 --format GML|SHP` (state as of the beginning of the year) stores the original
  county ZIP package 1:1 in `landcover/pl_bdot10k_<format>_<year>/teryt/<T>.zip`
  with label = year; identical vintages of the same county take up space
  once (status `relabeled`, hard link, ADR-042 D7).
- Library (ADR-042 D10): `download_collection`/`check_collection`
  and `CollectionReport(files, failed, stale, notices, ok)` in `__all__` (=
  `boundaries`/`cadastre`/`models3d download`, plan track `collection`),
  network-free validation `kartograf.download.collections.validate_collection_request`,
  `download_landcover`/`check_landcover(year=, format="GML"|"SHP")` for the BDOT10k
  archive; `Notice` codes `unit_list` (counties of an area according to PRG),
  `whole_country_size` (size of the national file before transfer)
  and `auto_narrowed_to_cz`; channel parameters `AccessChannel.params`
  (`UnitPackageParams`, `PackageVariant`, `FeatureBBoxParams`,
  `FeatureLayer` in `kartograf.sources.descriptor`) and the descriptors
  `pl.gugik.prg`, `pl.gugik.egib`, `pl.gugik.buildings` and the channel
  `archive_unit_files` in `pl.gugik.bdot10k`. Project (ADR-040): tasks
  `boundaries download`, `cadastre download` and `models3d download`.
  Live verification: `docs/research/2026-10-15-plan-c-live/raport.md`.
- Project (ADR-040): the `kartograf project` group (`init`, `add`, `remove`,
  `download`, `status`, `verify`) stores tasks and pinned versions
  in `kartograf-project.json` (`kartograf-project/1`). `download` restores
  missing versions only with a matching SHA-256 sum; `--check-updates`
  queries the source without downloading, `--upgrade`/`--force` explicitly re-pin
  tasks. Public API: `init_project`, `open_project`,
  `add_project_task`, `remove_project_task`, `download_project`,
  `check_project`, `get_project_status`, `verify_project` and the types
  `Project`, `ProjectTask`, `PinnedFile`, `ProjectReport`, `TaskResult`,
  `ProjectCheck`, `FileCheck`. Tasks cover every `download` command
  of the data groups and `soil hsg` with their options (among others `cutout`,
  `horizontal_crs`, `coverage`, `resolution` in `imagery download`;
  `whole_country`, `horizontal_crs` in `landcover download`).
  `project download --workers N` (API `download_project(workers=)`) downloads
  the files of each task in parallel (default as in the data command); in `project
  add` `--workers` and `soil hsg --summary` are an `Error:` (run options, not
  task options). `status`/`verify`: a task not downloaded is the line `NAZWA: nie
  pobrane (pobierz: kartograf project download NAZWA)` and exit code 1 (without
  `Error:`); hints of `kartograf project ...` commands have `--project
  KATALOG` when the project is not the current directory. Usage description:
  `docs/USAGE.md` section 8.
- Library (ADR-037): `download_data`/`check_data` (`kartograf.download.data`)
  = the commands `kartograf elevation download` and `kartograf imagery download`:
  the whole command logic (sheet code and country, `country="auto"` with narrowing to PL
  and partial success, validation of each country before download,
  expansion of a PL area into sheets, `parent_request`) is in the library,
  result `DataReport(files, failed, stale, superseded, notices, ok)`.
  The API also has `UnitFile`, `UnitFailure`, `download_cz_sheet`/`check_cz_sheet`,
  `check_laz_area`, `get_overall_bbox`, `transform_bbox`,
  `parent_request_for`; CLI = API parity tests (`tests/test_parity.py`,
  `tests/test_parity_landcover.py`). CLI: `landcover download` and `soil hsg`
  are one library call per command, with the new flags `--bbox-crs`
  (bbox in any CRS from the list) and `--quiet` (no status line on
  stdout; `Info:`/`Warning:` on stderr remain), and `landcover download`
  also has `--layers KODY` (BDOT10k GPKG layer filter, e.g. `SWRS,PTWP`),
  `--keep-raw` (original GUGiK ZIP in the store) and `--workers N`
  (BDOT10k counties of an area in parallel, default 1).
- Input validation in the library before the network, with the same text as the CLI
  (ADR-037): `download_data`/`check_data` check `product`, `country`,
  `sheet_system`, `horizontal_crs` (values as in `--help`) and bbox
  (inverted, infinite: `Nieprawidlowy bbox: ...`); bbox (coordinates
  and CRS from the `--bbox-crs` list, unknown CRS = `ValidationError`) also
  in `download_pl_cutout`/`check_pl_cutout`, `download_cz_cutout`/
  `check_cz_cutout`, `download_laz_area`/`check_laz_area`,
  `download_landcover`/`check_landcover` and `calculate_hsg`/`check_hsg`
  (a `.tif` directory is rejected as in the CLI); `resolution`/`vertical_crs`
  of a type other than text or dictionary = `ValidationError`; the TERYT code
  is also checked in `check`. Input errors
  within a part of a country are `ValidationError`, not a `failed` entry.
  The messages `nie udalo sie sprawdzic zrodla` and
  `lokalna wersja ... niesprawdzona` of land cover and HSG are library
  `Notice`s; a PL sheet used locally when the sheet index is unavailable gives
  one message; `--check-updates` under `auto` with a failure of one country
  reports an error with the country name.
- Library: `Notice(level, code, text)` in the public API and
  `kartograf.notices.NoticeSink` (collecting notices and passing them to a
  callback); notice text is limited to ASCII, the codes are stable.
- Library and CLI: `kartograf.cache.defaults.open_cache(cache, force=...)`
  shares the default metadata database `.kartograf_cache.db` in the current
  directory (`default_cache_path()`); `cache=False` skips the cache, and `force=True`
  for a passed instance uses a separate connection without changing its reads.
  Disabling the cache is reported by a `Notice` (`cache_disabled`).
- CLI `elevation download` and `imagery download`: `--check-updates
  [--plan FILE]` (report without downloading, JSON plan `kartograf-plan/1`),
  `--upgrade [--plan FILE]` (download of
  newer content; plan execution with a check that the source has not changed
  since the plan) — for every track: PL sheets, PL and CZ LAZ tiles (CZ:
  `ETag`/`Last-Modified` of the file), CZ sheets (SM5 and native TM33:
  `ETag`/`Last-Modified`), CZ and PL cutouts (without a cheap signal:
  "nie da sie sprawdzic bez pobrania"); with `--country auto` one plan
  for PL and CZ.
- CLI `landcover download`, `soil download` and `soil hsg`: `--check-updates`,
  `--upgrade`, `--force`, `--plan FILE` (plan tracks `landcover` and `hsg`);
  status `uzyta ponownie` (HSG from the same inputs, without computing).
- Library: `UpdatePlan`, `PlanItem`, `UpdateMode`, `VersionRef`,
  `VersionedFile`, `LandCoverReport`, `SoilReport`, `HsgReport` and `Edition`
  in `__all__` (internal class types without export);
  `DownloadManager.check_sheets`, `FileStorage.get_versions_root`,
  `get_versions_base`, `has_legacy_campaigns`, `UpdatePlan.merge`/`items_for`.
  `kartograf.download.fetch` provides `fetch_version`/`inspect_version`,
  `use_local`/`store_file` and the release signal `metadata`; status `reused`
  denotes HSG from the same inputs without recomputation.
- Library: `check_cz_cutout`/`check_pl_cutout` in `__all__`; channels
  `AccessChannel.update_signal`/`channel_signal`, transport
  `response_signal`, `head_signal`, `download_to(on_response=)`,
  `get_with_retry(headers=)`; sidecars `extra.version`, `extra.http`
  (SM5), `extra.edition` and status `relabeled` (the same content under a new
  label; `VersionedFile.same_as` = label of the latest identical
  version, in the CLI `(plik identyczny z <label>)`).
- E2E test 2026-10-19, library: module `kartograf.interrupt`
  (`run_parallel(work, items, *, workers, on_done=None)`, `check_stop`,
  `Stopped`, `Terminated`, `sigterm_interrupts`; `Stopped` and `Terminated`
  are subclasses of `KeyboardInterrupt`, so the same cleanup works as
  on Ctrl-C with `--workers 1`); all download pools
  (`DownloadManager`, collections, BDOT10k counties, PL and CZ LAZ tiles) go
  through `run_parallel`, and the stop-check points are the HTTP transport
  (before an attempt, between chunks, instead of the retry pause), the
  AAIGrid stream, the BDOT10k package and `commit_version`. Code `terminated` (143)
  in `ERROR_CODES` and `EXIT_CODES` (`kartograf catalog`, USAGE 9.3,
  `llms.txt`); an additive change, 130 remains for Ctrl-C.
  `AuthProxyClient.last_error`/`credentials_problem()`,
  `notices.names_text`/`LISTED_UNITS`, `notices.NO_LAND`
  and `download.arguments.require_workers`.

### Changed

- AI agent interface (ADR-046), changes to existing APIs and behaviours:
  `calculate_hsg(..., summary=False)` and `HsgReport.summary` (HSG statistics after
  the calculation); `--summary` calls the API instead of `hsg_statistics` in the CLI (text
  unchanged, `soil hsg --json --summary` returns `summary` in the document).
  `TaskDownload.__call__` (`project/commands.py`) receives `plan`, and
  `TaskCommand.options` comes from the catalog: in new manifests the option keys
  follow declaration order (e.g. `country` right after `product`), and saving a task
  rewrites an older manifest in that order as well. CLI handlers do not pass
  unset flags (`None`, `False`) to library functions (their
  default values apply); empty `--bbox ''` and `--geometry ''` are an input error (code 2),
  as in `parse_command` and `project add` (previously ignored); `parse` reports the error
  before printing the sheet code; `project add` reports task command syntax errors as
  `UsageError` (`Error: ...`, code 2, no `usage:` block); `cache path` in text
  mode prints only the path without opening the database, and `cache path --json` is
  `kartograf-cache/1` with `action: "path"`. The `list-sources` and `list-layers` tables
  and the `parse` output are rendered from library documents, with no text changes.
  What to do: tests that replace library functions and read their `kwargs`
  must account for the absence of unset flags; a new command is a declaration in the catalog
  (STANDARDS 17.2).

- One naming convention for source keys and `data/` directories (UX review
  UX-35..40, ADR-044 D7, ARCHITECTURE 3.3 rule 10; enforced by the registry test
  `TestNamingConvention`): key `<country>.<provider>.<name>`
  made of whole words, `data/` path, directory = `--product` in `elevation`
  and `imagery`, segment `<country>_<tokens>` (`_` between tokens, `-` within a
  multi-word token, `.` in a number), PL CRS `1992`/`2000` and the PL-2000 zone
  as a directory named after its number, sheet always in the sheet code hierarchy. Products new
  in 0.8.0 were named according to it before the release; segments and keys from releases
  <= 0.7.2 are unchanged. Changed relative to the development version of 0.8.0:
  keys `pl.gugik.true_orto` (was `orto_true`), `pl.gugik.oblique_orto`
  (`orto_oblique`), `pl.gugik.buildings` (`buildings_3d`), `pl.gugik.mesh`
  (`mesh_3d`), `pl.gugik.trees` (`trees_3d`), `pl.gugik.control`
  (`prpog`), `pl.gugik.geoid2021` (`quasigeoid`), `cz.cuzk.hynet`
  (`hy_net`), `cz.cuzk.orto` (`ortofoto`), `cz.cuzk.control`
  (`survey_control`), `cz.cuzk.qgzu2013` (`qgzu`); directories
  `true-orto/pl_<crs>/` (was `orto/pl_<crs>_true/`, cutout
  `true-orto/pl_1992_<pixel>/`), `oblique-orto/pl_2000/`
  (`orto/pl_2000_oblique/`), `cadastre/cz_cadastral-map_<format>/`
  (`cz_km_<format>`), `geodesy/pl_control_<network>_xls/` (`_package`),
  `geodesy/cz_qgzu2013_bpv/` (`cz_qgzu2013`); mesh tile
  `models3d/pl_mesh/2000/7/` (`s7/`) and `.../1992/` (`pl1992/`), ZTM sheet
  `maps/cz_ztm_<scale>_<crs>_<format>/0510/D/11/0510-D-11.zip` (was
  flat in the segment), topic of the country file `country/pl_miejscowosci.zip`
  (`pl-miejscowosci.zip`). `--output` in `imagery` describes the product directory.
  What to do: data downloaded by the development version under the old names is not
  migrated - the next download goes to the new directories (delete the old ones
  manually); code reading the sidecar `dataset` or registry keys uses the
  new keys.
- Plan D (ADR-042 D13-D17): `imagery download --country` accepts `cz`
  (CZ orthophoto), `boundaries download --country` - `cz` and `auto` (RUIAN),
  `--level` in per-country syntax (`pl=gmina,cz=obec`; one parser definition
  with `--resolution`/`--vertical-crs` in `cli/_args.py`). Name of the descriptor
  `pl.gugik.orto`: `Ortofotomapa (arkusze wg kampanii; wycinek WCS
  Standard i High)` (the `dataset` key is unchanged). `AccessChannel.params`
  has two new types: `AtomFilesParams` and `WcsCutoutParams`.
- The lists of `elevation`/`imagery` products and `landcover` sources
  were moved from the CLI parsers to the library (`download/options.py`,
  `landcover/manager.py`): CLI groups and the project manifest use
  the same choices (internal change).
- New runtime dependency `pyogrio>=0.10` (vector GDAL; a wheel with its own
  GDAL, approx. 100 MB next to the `rasterio` GDAL): writing the GeoPackage result of an area
  `boundaries`/`cadastre download` (ADR-042 D5). What to do: update the
  installation (`pip install -U kartograf` or `pip install -e .` in the repo) -
  `pyogrio` is installed together with the package; without it, downloading area features
  ends with an import error (packages and other commands work).
- `landcover download --format` also accepts `GML`, only with `--year`
  (BDOT10k yearly archive); `--year` with `--product bdot10k` means the archive
  year (previously only CORINE). Without `--year` it works as before
  (current GPKG/SHP packages); `--format GML` without `--year` is an `Error:`
  with a hint. What to do: nothing.
- Documentation of the `update="force"` contract with respect to the provider cache (USAGE 2,
  ARCHITECTURE, docstrings of `DownloadManager`/`LandCoverManager`):
  `force` refreshes the cache opened by the function itself; a provider passed in
  as a ready instance keeps its cache (full refresh:
  `MetadataCache(refresh=True)`). Behaviour unchanged. What to do: nothing.
- UX review 0.8.0, CLI help (UX-15, 23, 26-34, 44): every `download`,
  `soil hsg` and `elevation availability` has command examples in `--help`
  (checked by a test like `project add`); `project init/add/remove/download/
  status/verify` and `cache stats/clear/path` have descriptions. Uniform help
  sections (`Produkt i obszar`, `Parametry produktu`, `Wynik i aktualizacja`),
  `--country` right after `--product`, metavars in Polish (`ROZDZIELCZOSC`,
  `UKLAD`, `SKALA`), one `--output` text (`Katalog magazynu (wymagany):
  pliki w <DIR>/<dir>/...` with the directory from the registry; the same in the error
  for missing `--output`). `maps`: the description and `--sheet-system` state that the sheet system
  applies only to ZTM (CZ). `soil list-layers` and the `--property`/`--stat` help
  in Polish with units (one description map). `landcover list-layers` for
  ZABAGED/Data50/Data250: only layer names and a sentence that `--layers` applies
  only to BDOT10k and BDOO; CORINE years with the kind of data (1990 - WMS preview
  only). The main `kartograf --help` describes the groups without claiming that each
  has `download` and `list-sources`. Docstring of `kartograf/__init__.py`:
  all sources and collection groups. What to do: nothing.
- `kartograf parse` recognises CZ sheet codes without network (UX-25): SM5 sheet
  (`CTES96`), TM33 tile (`302_5550`, with extent in EPSG:3045) and ZTM sheet
  (`0510-D-11`, `NM-34-07-1-D-15`) - system, CRS and commands accepting a
  sheet code in `--sheet`; `--hierarchy`/`--children`/`--descendants` with a CZ sheet code
  is an `Error:`. ZTM patterns in `core.parser_registry.ztm_sheet_system` (one
  source for `parse` and `maps download --sheet`). What to do: nothing.
- E2E test 2026-10-19, `hint` in `kartograf-error/1` (CLI and MCP) takes
  `Przyklad:` from the product, country and area selection of the call
  (`error_report(exc, command=, given=)`, `catalog.hints.example_for(...,
  given)`; previously the first example of the command, e.g. `buildings` for
  `--product trees`); new catalog examples: `boundaries` (`admin
  --country auto --level pl=gmina,cz=obec`, `special`, `geomorphology`),
  `models3d` `trees`, `names` `world`. What to do: nothing.
- E2E test 2026-10-19, `soil list-layers --json`: `properties[]` has the fields
  `unit`, `conventional_unit`, `divisor` and `depths` (`PropertyInfo`;
  `depths` contains `0-30cm`), and `landcover list-layers --product bdot10k`
  lists all 58 BDOT10k classes (`--layers` values) instead of 15.
  Units in `--help`, `soil list-layers` and the sidecar (`extra.units`:
  `mapped`, `conventional`, `divisor`; an addition to `kartograf-meta/1`)
  are ISRIC "mapped units": clay g/kg, phh2o pH x 10, bdod cg/cm3, soc
  dg/kg, nitrogen cg/kg, cec mmol(c)/kg, cfvo cm3/dm3, ocd hg/m3, ocs
  t/ha (previously conventional descriptions). BDOT10k: `extra.source.classes`
  and `Bdot10kPackage.classes`/`absent` with `--layers`. `--property ocs`
  accepts only `--depth 0-30cm` (`ValidationError` with a list
  of available ones, code 2).
- E2E test 2026-10-19, behaviour changes with no effect on exit codes:
  a download pool unit exception other than `DownloadError` (e.g. a write
  error) in collections, land cover and LAZ stops the pool immediately (previously
  after the whole queue; `DownloadManager` still converts it to the unit status
  `failed`); `project add ... -q` is an `Error:` (code 2,
  `option=quiet`; previously `-q` was silently skipped); the WARNING log about a mismatched
  sheet system in the PL sidecar (`sources.sidecar.pl_sheet_horizontal_crs`)
  was lowered to DEBUG, because the same fact is carried by the `Notice` `SHEET_CRS_MISMATCH`
  (and the sidecar: `horizontal_crs`, `extra.source.declared_crs`); direct
  users of `DownloadManager` no longer get this logger line. What to
  do: nothing.

### Fixed

- A store root that a write refuses is the error of the command, not the failure of every unit
  (DEV-19.13, DEV-19.14, AGI-4.3, ADR-054 decision 8). A root with the layout of a store and no
  marker (`store_unavailable`, `no_marker`), a root that holds other files (`conflict`,
  `not_empty`) and a root that lies in, holds or has below it a store of any tool (`conflict`,
  `nested_store`) was met by the first unit of work, after the index of the sheets had been
  asked, and a list of sheets fetched in parallel reported it as one failed unit with the code
  `source_unavailable` (kind `download`, exit 11): the registry code, the reason, the hint and
  the exit code (8 or 4) were lost (found by Retman). Now every track looks at the root before
  any request: the sheets (one, a list, an area), the LAZ tiles, the PL and CZ cutouts, the CZ
  sheets, LAZ, orthophotos and contours, the collections, land cover, soil, the HSG and
  `project download` (`kartograf.output.guard_store`, called by `writing` and by the public
  methods of `DownloadManager`, `LandCoverManager` and `HSGCalculator`; `download_data` and
  `download_collection` judge the request first, so an invalid one is still a
  `validation_error`). The error document is the last line of stderr and the exit code is the
  registry's. An `output_dir` that is, or lies in, a store is refused the same way before the
  index is asked (`conflict`, `output_in_store`, `details.paths` the directory). `--check`
  (`check_*`, `check_command`, MCP `check`, `DownloadManager.check_sheets`,
  `LandCoverManager.check`, `HSGCalculator.check_hsg`) lists a root that is a `conflict`
  instead of raising, as IMGWTools does for `nested_store`: one position of the new track
  `store` with the action `conflict`, the `reason` (`nested_store`, `not_empty`), the root as
  `path`, `error` with the text and the status `unverifiable`; the plan is `ok` (exit 0) and
  asks nothing. The plan of a root without its marker still fails with `store_unavailable`, as
  the run does. `check_project` lists a `conflict` entry (`FileCheck.status`) of every selected
  task. `Track` has the value `store`, `PinStatus` the value `conflict`, and
  `kartograf.marker.store_refusal`, `kartograf.output.guard_store`,
  `kartograf.output.directory_refusal` and `kartograf.download.plan.refusal_plan` are new.
- UX review 0.8.0 messages: an unknown flag reported by a command
  (its `usage`) with the list of commands that have it and a hint about common
  mistakes (`landcover --source`/`-s` -> `--product`, `soil download
  --product` -> `--property`, `hydro --sheet`); `--bbox -447000,...` after a
  space works without `=`; a missing selection lists the product's choices in the task's country
  (HY-NET CZ without `--teryt`/`--ku`/`--sheet`, control networks with the values of
  `--network`, CORINE and SoilGrids `--sheet, --bbox albo --geometry`);
  flags instead of registry keys (`--sheet-system`, `--keep-raw`,
  `--teryt`) and the product name in "nie dotyczy"; CZ `landcover` sources
  with a PL sheet code and a 2-digit `--teryt` of BDOT10k with a hint; `--layers` case-insensitive;
  sheet systems as `PL-1992`/`SM5`; correct inflection of numerals
  ("2 pliki", "dla 1 arkusza", "Pobieranie kafli
  LAZ"); the "no features in the area" error gives the task area in the user's
  CRS.
- LAZ PL `--sheet`: tiles are selected from the sheet frame (a rotated
  quadrilateral in EPSG:2180), not from its envelope, and a tile must reach into the area deeper than
  1 m (`tolerance_m`): neighbours touching the frame at an edge or
  a corner (GUGiK frames rounded to 1 cm) and a tile reaching
  into `--bbox` by millimetres are not downloaded. The example from USAGE 1.1 (`--sheet
  N-34-130-D-d-2-4`) downloaded 13 tiles (1.83 GB) instead of 4 (575 MB), a 1:5000
  sheet - 6 tiles instead of 1 (live test 2026-10-16). The same in
  `elevation availability --product laz --sheet` (field and frame tiles).
  Library: `download_laz_area`/`check_laz_area(sheet=)` (exactly one
  of `bbox`/`sheet`, like `download_cz_laz`), `select_tiles(frame=)`,
  `select_newest_cover`/`select_all_intersecting` with the frame as an EPSG:2180
  polygon, `select_all_intersecting(tolerance_m=)`. The `Info:` about skipped
  tiles lists only tiles covered by newer ones; tiles outside the area
  stay in `superseded` with the reason `outside`.
- `--check-updates` (and `check_data`, `check_*`, `check_landcover`)
  always queries the source: the metadata cache is opened in refresh
  mode (read skipped, entries written anew) in every path.
  Previously PL sheets (NMT/NMPT/orto), archives, 100 m NMT files, collections,
  CZ LAZ, CZ sheets and land cover answered from the cache (TTL 7 days) - also
  offline `aktualne`, and a new flight published in the meantime was invisible
  (live test 2026-10-16). Without network the check now ends with
  `Error:`. `--upgrade` (`update="upgrade"`) queries the source in the same way (cache
  in refresh mode, `fetch.refreshes_cache`) - a new flight is visible
  without a prior `--check-updates`. The default download reads the cache as
  before.
- PL cutout `--cutout` entirely outside land (PRG mask: sea, abroad)
  ends with an `Error:` (code 1, `NoCoverageError`) before the first WCS
  request, with no version in the store - like the sheet mode. Previously 6 WCS requests
  (30 s), a 16.8 MB file of pure nodata and code 0 with a `Warning:` (live test
  2026-10-16). `Warning: wycinek w calosci nodata` remains for WCS with no
  data on land.
- HSG `--summary`: task area statistics - header `Statystyki HSG
  obszaru zadania (grupy: % powierzchni z danymi)`, group lines with a description
  in Polish, `Brak danych: <percent>% obszaru zadania (<ha> ha)` and `Obszar
  zadania: <ha> ha`; previously a 2 x 2 km bbox with 19 of 104 pixels with data
  gave just `Grupa B: 100.0%`, and then 420.91 ha of the "whole area" (the whole
  SoilGrids raster reaching beyond the bbox, live test 2026-10-17).
- PL image cutout entirely 0,0,0 (`imagery download --cutout`,
  `download_image_cutout`): true orto outside the service's cities, `high`
  orthophoto outside 10 cm areas and `standard` without an orthophoto ends with an
  `Error:` (code 1, `NoCoverageError`, in `download_data` the PL failure
  `no_coverage`) with no version in the store - like the PL cutout outside land;
  the message gives the cause and remedy (`zmien --bbox`, with `high` also
  `uzyj --coverage standard`). Previously a black file was a new version
  with `extra.all_nodata` and a `Warning:` (true orto with a nested bracket;
  live test 2026-10-17, Krakow, 19 s). The service does not publish the cutout
  extent, so the image is downloaded and checked before the version is saved;
  `ImageCutoutResult.notices` no longer contains `all_nodata`.
- 3D mesh `--bbox` (and every WFS index tile product) without `--check-updates`/
  `--upgrade` does not query the index a second time in the same area: the area
  records are in the metadata cache (TTL like the PL sheet indexes), so
  a run with local tiles works without network. Previously 3 WFS attempts
  `SkorowidzModeleSiatkowe3D` and code 1 offline (live test 2026-10-17).
  `--check-updates`, `--upgrade` and `--force` query the index as before.
- `update="check"` in the download function points to the plan function of that track
  (`uzyj check_landcover()`, `check_soil()`, `check_hsg()`,
  `check_image_cutout()`, `check_data()`, `check_collection()`, ...);
  previously always `check_sheets() albo check_*()`.
- `python -m kartograf.cli.commands` no longer prints the `RuntimeWarning` of the `runpy`
  module (the `kartograf.cli` package imports `main` only on use).
- A failure of the GUGiK WFS sheet index in the `--check-updates` line ends with the fact
  `- wynik bylby niepelny`, without `ponow pobranie` (the check downloads nothing;
  live tests 2026-10-16/17). The `ponow pobranie` remedy is added only by
  download summaries; previously a summary of several sheets had it
  twice, and the warning `skorowidz GUGiK niedostepny - uzyto lokalnej
  wersji` advised repeating the download even though the file was in place.
- Project: recreating a missing pinned version with a matching SHA-256
  writes the bytes under the pinned version (`version`, `label`; hard link
  and sidecar with the pinned label) - the manifest does not change. Previously
  recreating on another day changed `version`/`label` of tasks with a
  download-date label (a manifest change without a data change).
- Documentation: USAGE 7 - the cost of confirming hard links on an SMB share without
  `serverino` (full file read on every run; no shortcut
  in the code) and SoilGrids zeros in masked areas (GeoTIFF without a NoData
  tag; HSG treats them as no data).
- Documentation: USAGE 7 - the Krakow 2021 oblique orthophoto has its own CRS description
  without an EPSG code in the GeoTIFF (GDAL guesses EPSG:32634); the file CRS is EPSG:2178
  as in the sidecar, with a workaround that does not change the file.
- CLI (live test 2026-10-16): `kartograf` and `<group>` without a command
  print help to stderr with exit code 2 (previously 0 - a script with a mistake
  "passed"); Ctrl-C ends with `Error: przerwano (Ctrl-C)` and exit code 130
  instead of a traceback; `--check-updates --plan` to a non-existent directory
  = `Error:` before the network (previously after the whole source check); without files
  (LAZ WFS failure) there is no `Nowe: 0, ..., bledy: 0` summary contradicting the
  `Error:` line; HTTP request retries are `Warning:` lines with a short
  cause (`HTTP 503`, `przekroczony czas odpowiedzi`, `brak sieci albo
  DNS`, `zerwane albo odrzucone polaczenie`) instead of the raw urllib3
  exception (approx. 500 characters); the full exception is in the cause chain
  (`KARTOGRAF_DEBUG=1`).
- SM5 sheet codes with two letters (99 As sheets, `AS22`...`AS94`):
  `detect_system("AS91")` returned the PL-1992 system (fallback of the pattern
  `^[A-Z]{4}[0-9]{2}$`), so `--sheet AS91` (DMR 4G) ended with a PL
  sheet code error. Now `cz_sm5` (`^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$`, directory
  `AS/91`) - also for CZ DMR and orthophoto.
- CORINE CLMS 2012/2006/2000: dataset UIDs and the raster `@id` did not exist
  in the CLMS catalogue (`items_total: 0`); corrected according to the catalogue
  (`docs/research/2026-10-12-plan3-spec-check/raport.md`). The CLMS download
  with credentials has not been verified live.
- `soilgrids hsg --bbox ... -o <dir>` wrote `hsg_bbox_<depth>.tif`
  without coordinates — two areas overwrote one file. Now
  `hsg/global_soilgrids_<gl>_<stat>/bbox/<coords>.tif`.
- PL sheets downloaded in parallel (`workers > 1`): the result (`DownloadResult`
  list, `files`) and messages (e.g. the list of sheets without GUGiK data)
  are in order of submission, not completion - the same task always gives the
  same report (detected by the CLI = API consistency test).
- `--check-updates --plan FILE` with a FILE directory that does not exist:
  `Error: nie udalo sie zapisac planu <FILE>: ...` (code 1) instead of
  `Error: FileNotFoundError: ...` with the `KARTOGRAF_DEBUG` hint
  (live verification 2026-10-12).
- `landcover download --format` with a source other than bdot10k ends with an
  error (previously it was silently ignored); `download_landcover`/`download_soil`
  without a required source option (`year` CORINE, `property`/`depth`/`stat`
  SoilGrids) or
  with a BDOT10k-only option (`format`, `layers`, `keep_raw`) for another source
  gives `ValidationError` with the CLI text (previously `TypeError`). Without
  English and duplicate log lines on stderr (`No data for ...`,
  `Failed to download ...`, CORINE preview, `Zapytanie WFS GUGiK ...` LAZ,
  logs duplicating `Notice`, BDOT10k county failures): the cause of the failure
  is in the error text (`Error:`, the `failed` field of the result).
- A "no coverage" entry in the metadata cache written before 0.8.0 (a message
  or hint with Polish characters or the dash `—`) aborted the
  download with the error `Tekst komunikatu musi byc zapisany w ASCII` (e.g.
  `kartograf elevation download --sheet N-34-130-D --resolution 5m ...` with a cache
  from 0.7.x). Such an entry is now treated as a missing entry and the sheet index is
  queried again. What to do: nothing (optionally `kartograf cache clear`).
- `landcover download --check-updates --keep-raw` printed two
  identical plan lines (`0208: do pobrania`) for GPKG and the raw ZIP of the
  same TERYT. The plan lines of `landcover download`, `soil download` and `soil
  hsg` now label items with the path under `--output`, like the status lines
  (`landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: do pobrania`, `soil hsg`:
  instead of `clay <coords>` / `hsg <coords>`). What to do: scripts parsing the plan
  lines of these commands read the path (the JSON plan file is unchanged).
- `--bbox-crs EPSG:2176-2179` (PL-2000 zones) with `--sheet-system 1992`
  ended with `Error: Nieobslugiwany CRS: 'EPSG:2177'. Obslugiwane:
  EPSG:2180, EPSG:4326`, even though the CRS is on the `--bbox-crs` list.
  `find_sheets_for_bbox(..., sheet_system="1992")` now accepts the same
  Polish CRSs as PL-2000 (EPSG:2180, EPSG:4326, EPSG:2176-2179); CZ CRSs
  are converted earlier by `download_data` in the pinned operation.
- Sheet download progress with several campaigns (`--all-campaigns`,
  `--full-sheet`): previously the `nowa wersja`/`lokalna wersja` lines appeared
  only after the whole task. The library reports `DownloadProgress` events
  `campaigns` (list of the sheet's flights: `lokalna`/`do pobrania`) and `campaign`
  (before downloading each flight, `k/n`); the CLI prints `  Kampanie <sheet>
  (do pobrania k z n): ...` and `  Pobieranie <sheet> <label> (k/n)...`.
  `--upgrade --plan` for PL sheets reports progress like a regular download.
- Download progress of BDOT10k counties of an area (`landcover download --bbox/
  --sheet/--geometry`, also the `--year` archive): previously no progress at all
  until the end of the task. `download_landcover(on_progress=)`
  reports `DownloadProgress` per county like the sheet list (`sheet` = TERYT:
  `downloading` just before the transfer with `--workers 1`, then `completed`/
  `skipped`/`failed` in completion order); the CLI and `project download`
  draw the same bar as for sheets. A single `--teryt`, CORINE and SoilGrids
  unchanged (one file).
- The progress bar of the sheet list (and BDOT10k counties), whose last
  unit was `o` (local version), did not end the line: the first status
  line was appended to the bar (live verification 2026-10-15). The bar
  line is now closed before status lines and `Error:`.
- The hard link sidecar (`<file>.meta.json` of the standard path) after a write
  failure stayed stale and described the previous version (ADR-030 M-8). It is now
  removed (a warning in the log), and the next run recreates the
  hard link and sidecar (ADR-030 erratum 10).
- Orthophoto documentation (SCOPE, PRD, docstring of `gugik_orto.py`):
  resolution "according to campaign (e.g. 25 cm, 10 cm)" instead of a fixed 25 cm
  (README corrected earlier).
- E2E test 2026-10-19, interruption: Ctrl-C with `--workers >= 2` stops the
  download. The queue (PL sheets, collections, BDOT10k counties, PL and CZ LAZ
  tiles) is cancelled, running transfers stop after the current chunk
  (also the BDOT10k package), and units unfinished before the interruption are
  neither downloaded nor committed; previously the command waited for the whole queue
  and committed it (12 BDOT10k counties, 6 RCN counties, 3 orthophoto sheets
  after Ctrl-C). Exit code 130 and `kartograf-error/1` `interrupted` as with
  `--workers 1`; versions committed before the interruption remain.
  SIGTERM (`timeout`, `docker stop`) in the CLI acts like Ctrl-C: cleanup of the
  `versions/.incoming/` directory, `Error: przerwano (SIGTERM)` or
  `kartograf-error/1` with code `terminated`, exit code 143 (previously the process died
  without a message and left leftovers). The MCP server does not intercept SIGTERM
  (default termination; `.incoming` is cleaned after 24 h). Known limits:
  a request blocked on the network ends with a timeout, probe pools
  (`check_year_range`, HEAD of sizes, `availability`) wait for running
  requests.
- E2E test 2026-10-19, hard links on an SMB/cifs share without `serverino`
  (standard path and `full_sheet/`): the hard link does not fall back to an
  older flight when the file was read a moment earlier (another program,
  previous run). The cifs client then reports `st_nlink` = 1 for
  a few seconds, and confirmation required `st_nlink >= 2` of both files, so the
  path was taken as unknown and was repointed to the selected flight (e.g.
  `--max-year 2022` right after a download with `--full-sheet`, without Warning/Info).
  The same cause gave `link_target` = `None` alternating with the result
  and a needless write (hard link replacement, rewritten sidecar) on `lokalna
  wersja`. Confirmation without stable inodes is now based on
  content (size and SHA-256 from the version sidecar), without the hard link
  count (`links._hold`); local disk and shares with stable inodes are
  unchanged (see the `link_target` change of an independent copy in the BREAKING section).
- E2E test 2026-10-19, stderr consistent with the `--json` contract (USAGE 9.2)
  in a clean installation: the pyproj warning `Best transformation is not
  available` (CUZK PROJ grid; availability CZ/auto, `--bbox-crs
  EPSG:3045`, TM33 warp, CZ cutout) is not printed (filter only around
  `TransformerGroup` in `transform/crs.py`); library logger records
  (`Pominieto wersje o niezgodnym sha256`, `Pominieto wersje bez
  czytelnego sidecara`, sidecar write errors) are not raw lines -
  in the text they have the prefix `Warning:`/`Error:`, with `--json` stderr stays
  empty (except HTTP retries and `KARTOGRAF_DEBUG`); a CLMS task error
  via proxy carries the cause (`Zadanie przez proxy nie powiodlo sie:
  ...`) instead of the `Proxy request failed` line on stderr.
- E2E test 2026-10-19, CORINE: the WMS preview works for 2012, 2006 and 2000
  (the year's raster layer from the EEA service GetCapabilities; previously
  `LayerNotDefined`); a fully transparent image (1990 for Poland,
  an area outside Europe) is a `NoCoverageError` without writing a version (previously an empty
  version); a year error names the flag (`--year 2019: niedostepne dla
  --product corine; dostepne: ...`); `Warning` `corine_preview` with a reason
  when `CLMS_CREDENTIALS` is set but unusable (proxy `/health`
  returns `credentials_error`, without the variable value).
- E2E test 2026-10-19, SoilGrids and HSG: `--property ocd` works (release
  taken from the `clay` map: `ocd.map` has no release in its title); a window smaller than
  a pixel is expanded to one pixel (previously HTTP 400); an all-zero raster
  (except `cfvo`, where 0 is a value) is a `Warning` `all_nodata`
  and `extra.all_nodata`, HSG without any class likewise; the USDA triangle
  classification does not round (values on g/kg boundaries by rules
  in float64, not float32; removed dead `HSGCalculator.
  CONVERSION_FACTOR`).
- E2E test 2026-10-19, BDOT10k: an area (`--bbox`, `--geometry`)
  is subject to the 100 files / 10 GB limit like collections, also the `--year`
  archive (previously without a limit); `--layers` rejects an unknown or empty code
  before the network (code 2,
  `option=layers`, `allowed`; previously only after the download), a class
  absent from the county package is an `Info` `classes_absent` (like BDOO), the absence of
  all classes is a county `NoCoverageError` (previously a county
  `DownloadError`); the description of class `PTWZ` corrected ("Wyrobiska i zwalowiska").
- E2E test 2026-10-19, collections: `Info:` `unit_list` names at most
  10 units (`a, ..., j i 3874 inne`, `notices.names_text`); a 3D mesh
  with an area over the limit no longer prints a 120 KB line. The CZ cadastral map
  by area: KU by RUIAN (also an empty response) in the metadata cache
  (TTL 7 days; `--force`, `--upgrade` and `--check-updates` query the service),
  so a repeat works without the network (previously code 1 after 3 attempts).
- E2E test 2026-10-19, `elevation availability`: an area without PL land (territorial
  sea, outside the state border) has `complete: true` (the invariant
  `complete <=> full_m2 == land_m2` holds), but `Info:` `no_land`,
  the column KOMPLET `brak ladu` and a footer without a download hint (previously
  `tak` and `Pobranie ...` for 0,00 ha). An empty LAZ tile selection
  after `--min-density` names the flag, the number of rejected tiles and the highest
  nominal density (`LazTileSelection.below_density`).
- E2E test 2026-10-19, project and cache: `project download --force`
  repairs a corrupted pinned version (different size, SHA-256 or
  sidecar; previously `bez zmian` and `verify` still reported it corrupted): it sets it aside into
  a hidden directory `.<label>_<sha8>.corrupt-<time>` (nothing is
  deleted) and downloads again, the same bytes return under the pinned version
  (`odtworzono`, manifest unchanged), and `status` and `verify` give the same
  repair description. A manifest with an editor BOM is read; `--project`
  pointing to a file gives a readable error; `--check-updates --plan DIRECTORY` is
  `invalid_input` before the network; `--upgrade --plan` with no items to
  execute prints `Info:` (does not stay silent); the hint after `project init`
  `NAZWA <group> <command> ...`. `cache stats` and `cache_disabled` do not
  call the cache "unreadable" when it cannot be opened or written
  (read-only directory, full disk, a directory in place of the file) -
  the hint concerns permissions, not `cache clear`; `cache clear` without a database
  file says there is nothing to clear.
- E2E test 2026-10-19, availability and messages: `--country pl|cz` with `--bbox`
  or `--geometry` outside the country envelope is code 2 also in `elevation
  availability` (as in `elevation download`; previously `Brak arkuszy` or
  `obszar 0,00 ha`, code 0). Other message fixes: a non-existent
  voivodeship in `--teryt` says the code does not exist and gives the list;
  `--whole-country` without a country names the product's countries (hydro: only
  `--country cz`); `Info:` about 80-95 s only for `names --product
  geographic`; `boundaries` help: 44 kinds of special boundaries
  in the area result; correct `llms.txt` (`landcover list-layers --product
  bdoo --json`, `soil list-layers --json`, MCP tools of all collection
  groups).
- E2E test 2026-10-19, round 3 (after the second live verification):
  `file_footprint` returns the footprint of entries in `OGC:CRS84` (PRNG, special
  PRG boundaries): CRS84 and EPSG:4326 are the same WGS84 longitude/latitude,
  so the envelope is the same numbers without an operation, and `build_pinned_transform`
  accepts an axis swap of the same CRS as exact, also when PROJ 9.8.1
  reports its accuracy as unknown (-1). The year-range hint changes the
  boundary that blocks (`--min-year 2023 --max-year 2024` with data
  from 2022: `--min-year 2022`, previously `--max-year 2024`, the flag from the call);
  for `--year YYYY` the one-sided flags remain. The `Przyklad:` block in input
  errors matches the country and call mode (new catalog examples: PL
  NMT `--bbox` as sheets and as a cutout, CZ LAZ with `--model`, PL orthophoto
  `--bbox` as sheets, CZ orthophoto `--bbox`; the example chooses the mode by
  `--cutout`). The `ocd` sidecar has `extra.edition.source_property` = `clay`
  (the release comes from the `clay` map, its title and url in `extra.edition`).
  BDOT10k and collection area limit: up to 100 files the size of each
  is measured by `HEAD`, so the 10 GB limit is exact (an area of 69 counties is
  2.87 GB and rightly passes); above 100 files the refusal is decided by
  the count, and the size in the message is only indicative (average of 5 files,
  for 378 counties 6.4 GB against 18 GB actual).

## [0.7.2] - 2026-10-11

### Added

- CLI: `download --product nmpt --bbox/--geometry --target-crs ...`
  — NMPT 1 m cutout from GUGiK WCS (previously
  `Error:`), segment `nmpt/pl_1992_1m_<vcrs>/bbox/`.
- Library: `run_pl_wcs_cutout(cutout, *, provider=None, parent_request=None,
  today=None)` (in `__all__`) — PL cutout from GUGiK WCS: 1 m sheet grid,
  PL land mask from PRG (`A00_Granice_panstwa` minus
  `W02_Morze_terytorialne_RP` and `W03_Morskie_wody_wewnetrzne`, outside the mask
  -9999, 0.0 on land is kept), name `<coords>_<YYYYMMDD>.tif`, sidecar
  `capability="bbox_raster"` with `extra.source` (`composition: "server"`)
  and `extra.mask`. `prepare_pl_cutout(product=)` and
  `download_pl_cutout(product=)`: `"nmt"` or `"nmpt"` (NMPT 1 m cutout,
  segment `nmpt/pl_1992_1m_<vcrs>/bbox/`). `PlCutoutResult.masked_pixels`
  (pixels outside the mask) and `zero_pixels` (0.0 on land; also
  `extra.zero_pixels`, when > 0).
- NMT/NMPT: for a sheet without data in the selected resolution or vertical CRS,
  an `Info:` hint about the variant in which the GUGiK sheet index has that sheet,
  e.g. `Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 — uzyj --resolution 1m`
  (library: `NoCoverageError.hints`, `DownloadResult.no_coverage_hints`).
  Cost: one sheet index query per variant (NMT: 2, NMPT: 1) and
  missing sheet; an error in that query (one attempt) skips the hint,
  and a variant with an error is not queried again until the end of
  the task; the result is unchanged. No-coverage cache entries from
  before 0.7.2 do not have this hint until the end of the TTL (7
  days) — `--force` or `MetadataCache(refresh=True)` refreshes them.
- Library: `DownloadManager(max_year=)` and the public
  `check_year_range(godla)` check the full campaign list before
  the download; `YearRangeError` gives the sheets, available years and hints.
  `available_years(godlo)` of the NMT/NMPT/orthophoto providers returns the ascending years
  from the sheet's full campaign list.
  A campaign sidecar with a range contains `request.max_year`, `request.year`
  for a single year and `extra.available_years`.
- NMT/NMPT/orthophoto: after downloading several flights of a sheet from a year range,
  when the newest is not full, the share of valid pixels is measured
  (`extra.coverage` in the campaign sidecar). The standard-path sidecar
  receives the list `extra.flights` and `extra.better_coverage` (the ID of the flight
  with greater coverage, if one exists); the library returns this ID in
  `SheetFetch.better_coverage` and `DownloadResult.better_coverage`.
  The link still points to the newest flight, not the flight with the greatest coverage.
- LAZ library: `select_tiles(max_year=)`, `discover_tiles(min_year=,
  max_year=)` and `download_laz_area(max_year=)` select tiles from the closed
  range. In an `Error:` about a missing vintage, a year that in the uncovered part
  has only deliveries of incomplete sheets (`czy_ark_wypelniony=NIE`) has
  the note `(tylko arkusze niepelne)`.
  The LAZ sidecar records `request.max_year` (and `request.year`, when the bounds are
  equal), and for known values `extra.acquisition_date` and `extra.full_sheet`.
- CLI `download`: `--max-year YYYY` and `--year YYYY` work for NMT,
  NMPT, orthophoto and LAZ. The year flags only determine the permitted years,
  and `--campaigns` the number of flights per sheet: by default (`newest`) one,
  the newest flight in the range, `--campaigns all` all flights in the range.
  `--year` is a shorthand for both bounds set to the same year; a missing vintage for
  any sheet/tile stops the task before the download, gives the
  available years and a hint. With `--campaigns all`, when an older flight has
  greater measured coverage than the newest, the CLI gives an `Info:` also with `-q`
  (the link stays on the newest flight).
- CLI and library: when at a year bound the link still points to
  a flight outside the task (the link never moves back), the CLI gives
  `Info: N dowiazan wskazuje lokalny lot spoza tego zadania ...` with a line
  `<sheet_code>: sciezka standardowa|full_sheet/ -> dowiazanie <date>_<id>` per
  link; library: `SheetFetch.link_outside_range`,
  `DownloadResult.link_outside_range` (for `full_sheet/`: the fields
  `full_link_outside_range`).
- NMT/NMPT/orthophoto: a second link
  `<segment>/full_sheet/<hierarchy>/<sheet_code>.<ext>` to the newest
  local flight marked in the GUGiK sheet index as full
  (`calyArkuszWypelnionyTrescia = TAK`; full = within the borders of Poland). The same
  mechanism as the standard path: hard link with no space cost (a copy when a
  hard link is unavailable), never backwards, sidecar with `extra.link_target`. When the
  newest flight is full, both links point to the same file.
  `FileStorage.list_files()` skips `full_sheet/`, `FileStorage.delete()`
  removes both links (files in `kampanie/` remain); new
  `FileStorage.get_full_sheet_path()`. Library: `SheetFetch.full_link`,
  `SheetFetch.full_link_outside_range`, `DownloadResult.full_links`,
  `DownloadResult.full_link_outside_range`.
- Library: `DownloadManager(full_sheet=True)` (property
  `full_sheet`) — when the newest flight of a sheet in the year range is not
  full, it additionally downloads the newest full flight from that range
  (at most one additional flight per sheet) and links it in `full_sheet/`;
  the standard path still points to the newest flight. The campaign sidecar of such a
  task has `request.full_sheet: true`. Sheets without a full flight
  in the sheet index: `DownloadResult.without_full`. A provider without campaigns
  with `full_sheet=True` = `ValidationError`.
- CLI `download --full-sheet` (NMT/NMPT/orthophoto PL, also with year flags):
  when the newest flight of a sheet is not full, it additionally downloads the newest
  full flight from the range and links it in `<segment>/full_sheet/`. The summary
  counts campaign files (`Downloaded 2 campaign files for 1 sheets ...`).
  `--full-sheet` with `--product laz` or `--target-crs` = `Error:` before
  the network (code 1); for CZ like other campaign options (`Error:` without PL, `Info:`
  for PL+CZ under `--country auto`). With `--campaigns all` it has no effect.
- `--geometry` with a GPKG file with multiple layers without `--layer` (`download`,
  `landcover download`, `soilgrids hsg`): one `Info:` on stderr (also
  with `-q`) with the name of the first layer used, the list of the others and the hint
  `--layer`. The layer selection is unchanged.
- `--country auto` for a PL+CZ area without `--vertical-crs`: one `Info:` before
  the download, that the PL part is in EVRF2007 and the CZ part in Bpv (difference approx.
  0.11-0.15 m), with the hint `--vertical-crs EVRF2007` (one CRS for
  both). Default CRSs are unchanged. Country envelopes are rectangular, so the
  notice also appears for tasks in which the CZ part turns out to be empty.

### Changed

- CLI `download --bbox/--geometry --target-crs` (PL): cutout from GUGiK WCS
  instead of a sheet mosaic (ADR-035) — 1 m sheet grid, server flight composition,
  nodata -9999 outside PL land (PRG mask), name `<coords>_<YYYYMMDD>.tif`, every
  run downloads (no `Skipped`; `--force`, `--workers` and `--scale` have no
  effect). `--resolution 5m --target-crs` = `Error:` (code 1, before the network).
  Instead of the sheet list and notices about sheets (`Warning:` R5/E13/I-1,
  `Info:` W1) there is an `Info:` about the number of WCS queries (when > 1 or
  the result >= 1 GiB) and a `Warning:` when the area lies entirely outside PL
  land. Year flags, `--campaigns all` and `--full-sheet` with `--target-crs`
  remain `Error:` (new content). What to do: for a 5 m cutout or the newest
  sheet flight (ADR-028) — download sheets without `--target-crs` (or the
  sheet API); scripts looking for a file by name without a date — match the
  pattern `<coords>_*.tif`; older cutouts without a date are left untouched.
- `download_pl_cutout()` downloads the cutout from GUGiK WCS (`run_pl_wcs_cutout`):
  1 m sheet grid, server flight composition (not the newest flight of ADR-028),
  nodata -9999 outside PL land (PRG mask), name with the download date
  `<coords>_<YYYYMMDD>.tif`, every call downloads (no `skipped`),
  `resolution="5m"` = `ValidationError`. The sheet parameters `geometry`,
  `layer`, `scale`, `max_workers`, `force`, `on_progress`, `cache` have no
  effect; a non-default value gives a `DeprecationWarning` (removal
  in 0.8.0). The sheet API (`prepare_pl_cutout` -> `select_pl_cutout_sheets`
  -> `run_pl_cutout`, `build_cutout_from_sheets`) works unchanged and is
  deprecated (removal in 0.8.0); `run_pl_cutout` with
  `cutout.product="nmpt"` = `ValidationError`. What to do: for a cutout from sheets
  (newest flight ADR-028, 5 m) — `prepare_pl_cutout` ->
  `select_pl_cutout_sheets` -> `run_pl_cutout`; do not pass the sheet
  parameters of `download_pl_cutout`; code looking for a file by name without a date —
  use `PlCutoutResult.path`.
- The `Warning:` about an incomplete newest campaign (E13) splits sheets: "pelny
  lot w <segment>/full_sheet/", "brak pelnego lotu w skorowidzu" (with year
  flags: "... w zakresie lat zadania") and "pelny lot nie pobrany ... — uzyj
  --full-sheet". Notices about campaign options
  for CZ mention `--full-sheet`. Scripts matching the old text
  need to be fixed.
- The CLI notice about sheets without GUGiK data does not guess the cause
  "(morze, obszar za granica)": it says that the GUGiK sheet index does not have these
  sheets for the selected product and resolution, and gives the sea, borders and lack of
  NMT 5 m in part of the country as examples (checked live: e.g.
  `N-34-130-D-d --resolution 5m` — 6 of 16 sheets without 5 m, NMT 1 m exists).
  Scripts matching the old text need to be fixed.
- `--year` with `--product nmt|nmpt|orto` is no longer ignored: it downloads the
  given vintage or returns an `Error:` with the list of years. What to do: remove
  `--year` passed only "just in case" or choose an appropriate
  `--min-year`/`--max-year` range.
- `--year`/`--max-year` with `--target-crs` return an `Error:` (like `--min-year`
  before). What to do: do not pass year flags for a cutout (a cutout
  from WCS has the server flight composition, without year selection).
- `--campaigns all --min-year` always queries all layers of the sheet index,
  to be able to give the full list of vintages. `campaigns_cache` entries from a partial
  scan are queried again. What to do: nothing (the cost is 1-3 additional GetFeatureInfo
  queries per sheet once every 7 days).
- `DownloadManager(min_year=...)`: a sheet with data only outside the range
  stops the whole task (also the list/hierarchy) before the download, instead of
  being skipped. A failure of the sheet index check also stops the task;
  the local fallback without verification still works without year bounds.
  What to do: for lists with a deliberate omission of older sheets, download without
  the bound and filter by `extra.campaign.date`, or lower the bound.
- `validate_campaign_args(campaigns, min_year, max_year)` has a new
  mandatory argument (internal function, outside `__all__`). What to do: code
  calling it directly adds `max_year`.
- LAZ `--year`/`--min-year`: parts of the area available only in other
  vintages were downloaded partially without a notice; now the task
  stops before the download, gives the tile vintages and a hint.
  WFS queries all vintages of the service also with `--year`. What to do:
  if you deliberately want to download less data, apply the hint
  `--min-year`/`--max-year` or narrow `--bbox`.
- `mosaic_and_crop()` without `dtype=` for sources with different band types
  (e.g. ASC int32 alongside float32) ends with a `ValidationError` with a list of types;
  previously the result got the type of the first source (e.g. float heights truncated
  to integers without a trace). What to do: for mixed sources
  pass `dtype=` (e.g. `"float32"`).
- `download_bbox()` NMT 1 m KRON86 (GeoTIFF; also
  `DownloadManager.download_bbox`): the file extent is the bbox expanded
  outwards to the source grid (pixel edges `k + 0.5` m, < 1 px on each
  side), and an area above 16 Mpx is downloaded in pieces and stitched without
  resampling (ADR-034). Sidecar `request.bbox` = the task bbox. What to
  do: nothing; whoever relied on an extent equal to the bbox reads the extent from the file.
  Orthophoto and PNG/JPEG — one query as before (NMPT: below).
- `download_bbox()` NMT 1 m EVRF2007 works (previously `ValidationError`
  about a withdrawn endpoint): float32 heights from WCS `DigitalTerrainModel`
  (`image/x-aaigrid`, saved as GeoTIFF EPSG:2180) on the 1 m
  sheet grid; `is_wcs_available()` EVRF2007 = `True`, the WCS channel `pl.gugik.nmt_1m`
  in the registry has both vertical CRSs. What to do: nothing; whoever caught
  `ValidationError` for EVRF2007 can remove the workaround.
- `download_bbox()` NMPT: resolution 1 m (`SCALEFACTOR=0.5`; previously
  0.5 m) on the 1 m sheet grid, in pieces like NMT; the registry `pl.gugik.nmpt`
  has the WCS channel `bbox_raster`. What to do: nothing; the result matches NMPT 1 m
  sheets (over a 0.5 m flight — a 0.5 m pixel centred on a whole metre).
- `download_bbox()` NMT EVRF2007 and NMPT download `image/x-aaigrid` pieces
  (NMT up to 1 Mpx; NMPT up to 4 Mpx of 0.5 m coverage pixels = 1 Mpx of a 1 m result —
  host hangs hit pieces of every size, so fewer pieces
  means fewer retries; measurement `docs/research/2026-10-11-nmpt-asc-tuning/`;
  ASC approx. 20 s/Mpx and approx. 20 MB/Mpx; a longer task is silent before the first
  byte for longer than the 30 s read timeout). KRON86 NMT unchanged (GeoTIFF,
  16 Mpx). Every WCS query with a grid (NMT, NMPT, also KRON86) has an
  even width and height: the grid-aligned extent is
  widened by at most 1 px to the east/south and clipped after stitching
  (with an odd size the server takes the middle row and column
  from the neighbouring source pixel when it resamples — NMPT `SCALEFACTOR`,
  NMT 1 m over a 0.5 m flight; live measurement 2026-10-11). An
  `image/x-aaigrid` piece waits for the first byte for at least 120 s
  (`WCS_ASC_READ_TIMEOUT`; the caller's `timeout`, when larger): the server does not
  send anything before computing the whole piece (NMPT: 19-106 s live).
  What to do: nothing; large EVRF2007/NMPT areas take
  correspondingly longer than KRON86.
- Library: geometry functions (`get_overall_bbox`, `read_feature_bboxes`,
  `find_sheets_for_geometry`, `read_source_crs`) for a GPKG with multiple
  layers without `layer=` log the choice of the first layer as a `WARNING`
  (previously `INFO`, invisible by default). What to do: pass `layer=` if the
  message is a nuisance.

### Fixed

- The BDOT10k county query (WFS PRG) expands the area outwards
  with millimetre accuracy; previously rounding to whole metres
  could miss a county touching the area within a strip of up to 0.5 m,
  and `teryt_for_point` queried once for the point itself and once for a 2 m square.
- WFS PRG: a response in which `numberReturned` differs from the number of
  county codes read ends with `DownloadError` instead of a silently
  shorter list of counties (and a missing BDOT10k package).
- BDOT10k: the `timeout` option (`Bdot10kProvider.download_by_bbox/godlo`,
  `LandCoverManager.download_by_bbox/godlo/download_all_counties`)
  now also applies to the county query in WFS PRG; previously that query
  always used 30 s. Without `timeout`, the manager keeps 30 s.
- Sheet codes with non-ASCII digits (e.g. full-width `M-３３-８-A`,
  `6.１４５.２０`, CZ `７３０_５５５５`) are rejected (`ParseError`);
  previously PL-1992 and PL-2000 passed validation and ended up in paths
  and sidecars in a form different from the GUGiK sheet code. What to do: give the sheet code
  using the digits `0-9`.
- BDOT10k `keep_raw=True`: a failed write of the original ZIP on re-download
  leaves the previous GPKG and its sidecar unchanged (the merged GPKG
  replaces the previous one only after the ZIP is written). Previously the previous GPKG
  was overwritten and then deleted, leaving a sidecar without a data file.
- `download_bbox()` for NMT/NMPT/orthophoto no longer saves a WCS error report
  (`ows:ExceptionReport`, XML with HTTP 200) as a raster file — it is a
  `DownloadError`. NMT 1 m with a bbox outside the source grid gave content
  shifted by a fraction of a pixel relative to the georeferencing (the server resamples to
  the task grid; measurement `docs/research/2026-10-10-wcs-limits/raport.md`);
  now the task is aligned to the source grid.
- `download_bbox()` NMPT returned a 3-band RGB uint8 (colour preview)
  instead of heights; now 1 float32 band with heights (1 m on the sheet
  grid, bit for bit with the NMPT 1 m sheets). The WCS NMT EVRF2007 entry
  pointed to a non-existent endpoint (`DigitalTerrainModelFormatTIFFEVRF2007`,
  HTTP 404) — replaced with the working `DigitalTerrainModel`.

## [0.7.1] - 2026-10-09

### Added

- Roadmap to v1.0.0 in the documentation (`docs/SCOPE.md` 3.3, `docs/PRD.md`
  section 8): the complete set of public GUGiK data, ready-made data for each
  product, a data manager (versioned store, project manifest),
  a QGIS plugin and a web GUI.
- Stable public API: `get_with_retry`, `make_gugik_session`,
  `mosaic_and_crop`, `check_source_grid` exported from `kartograf`.
- `MetadataCache(strict=True)`: an SQLite error ends with `CacheError`
  (a new exception) instead of silently disabling the cache.
- Sidecar: `sha256` and `size_bytes` of the data file at the top level
  (all products). NMT/NMPT/orthophoto sheet sidecar: in `extra.source`
  `height_rmse_m`, `position_rmse_m`, `archive_module`,
  `declared_vertical_crs` from the sheet index record. Cache entries of records
  from before 0.7.1 are queried again.
- Verification of GUGiK sheets (B4): the sheet index record URL must contain
  the sheet code (NMT, NMPT, orthophoto), and the extent from the ASC header (NMT/NMPT) must lie
  within the sheet code frame (at least 50 % of the file area, frame in the file's CRS —
  PL-2000 sheets published in EPSG:2180 pass);
  a mismatch = sheet `DownloadError`, the file is not saved.
- `discover_teryts_for_bbox(bbox, *, session, cache)` and
  `teryt_for_point(x, y, crs, ...)`: TERYT county codes from the GUGiK WFS PRG
  (geometry filter); a service error or a list truncated by paging =
  `DownloadError`, an empty list only for a valid response without
  features. Responses go to the metadata cache (new table
  `teryt_bbox_cache`; `cache stats`: `TERYT entries` counts points and
  areas).
- BDOT10k from multiple counties: `LandCoverManager.download_all_counties(bbox=
  | godlo=, layers=)` downloads the package of EVERY county intersecting the area
  (TERYT from WFS PRG), optionally only selected layers (e.g. `PTWP`,
  `SWRS`); `Bdot10kProvider.download_package` returns `Bdot10kPackage`
  (`path`, `teryt`, `url`, `format`; exported from `kartograf`).
  `LandCoverManager(cache=)` passes the metadata cache to providers
  created by name (BDOT10k, SoilGrids).
- BDOT10k sidecar: `extra.source` (`url`, `teryt`, `format`) and `extra.http`
  (`etag`, `last_modified`, `content_length` from the response; the GUGiK package
  server currently provides only `Content-Length`). `keep_raw=True` keeps the
  original GUGiK ZIP next to the GPKG (full package: `bdot10k_teryt_<TERYT>_GPKG.zip`
  without a layer token, the same file regardless of the `layers=` filter, with its own
  sidecar; GPKG only). `Bdot10kPackage` has the fields `http` and `raw_path`.
- CZ cutout in the library: `download_cz_cutout(bbox, output_dir=,
  target_crs=, vertical_crs=, resolution=)` (e.g. EPSG:2180 + EVRF2007;
  grid from the requested area, as in the CLI) and `run_cz_cutout` with its own
  provider; the result `CzCutoutResult` with the flag `all_nodata` (also
  in the sidecar and in the log), the sidecar is written by the library. Splitting the area by
  country: `countries_for_bbox`, `split_bbox_by_country`. The CLI (`--bbox`/
  `--geometry` for CZ) uses the same implementation — messages
  and exit codes unchanged, the CZ cutout sidecar gets
  `extra.all_nodata` (`true`/`false`).
- `build_cutout_from_sheets(sheet_paths, bbox, target_crs, output_path, *,
  resolution, vertical_crs)`: an NMT PL cutout from local sheets without
  network requests, the result and sidecar under the path given by the
  caller (grid rules as in `download_pl_cutout`). A missing or
  unreadable sheet and an `output_path` equal to an input sheet =
  `ValidationError` before writing.
- `hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`:
  HSG from ready-made SoilGrids rasters (g/kg) on an explicitly given grid, without
  default values (input nodata only from the tag, as in
  `calculate_hsg_by_bbox`); a sidecar with the `sha256` of the input layers
  (`extra.source_files`: `name`, `file`, `sha256`; `extra.source_layers`
  as in `calculate_hsg_by_bbox` — a list of the names `clay`, `sand`, `silt`).
- Verification of the vertical CRS of the GUGiK sheet index record (NMT/NMPT): the field
  `ukladWspolrzednychPionowych` must match the requested CRS
  (`PL-KRON86-NH` for KRON86, `PL-EVRF2007-NH` for EVRF2007); any other value
  = campaign `DownloadError` before the file is downloaded (`newest` and `all`, also
  `GugikProvider.download`). A record without this field is accepted.
  New: `kartograf.download.campaigns.verify_record_vertical_crs`,
  `RECORD_VERTICAL_CRS`, `kartograf.providers.pl.require_nmt_vertical_crs`
  (`nmt_vertical_crs` unchanged).

### Changed

- `DownloadManager.download_sheet()` sets `last_result` also for a
  single sheet (a one-element `DownloadResult`); previously `None`.
  What to do: code that treated `last_result` after `download_sheet()`
  as `None` can now read the sheet result from it.
- Documented: with campaigns (`campaigns=`) the source of a sheet's origin
  is the sidecar, not `source_info()` (A12).
- PL-1992 sheet codes outside the nomenclature range (a zone other than M/N, a column outside
  33-35, a 1:200 000 sheet outside 1-144, e.g. `N-34-999-D`) end with
  `ParseError` before any network request; previously they reached
  services with a bbox of `inf` or outside Poland. What to do: nothing if the sheet codes
  are correct; code that expected `DownloadError` or an empty result for such sheet codes
  should catch `ParseError` (or `ValidationError`).
- `ParseError` inherits from `ValidationError` — `except ValidationError`
  also catches sheet code errors. What to do: if the code handles both exceptions separately,
  `except ParseError` must come before `except ValidationError`.
- Numbers in a PL-1992 sheet code are written without leading zeros, as in the GUGiK
  sheet index (`M-33-036-A` -> `M-33-36-A`) — in the path, sidecar and result,
  also in land cover file names (`..._godlo_M-33-36-A`) and in the default
  result name of `kartograf soilgrids hsg --godlo`
  (`hsg_M-33-36-A_<depth>.tif`). Files saved earlier under a sheet code
  with leading zeros are not recognised; download them again.
- `find_sheets_for_bbox` returns only sheet codes within the PL-1992 nomenclature range:
  an area extending beyond the M/N zones and columns 33-35 (e.g. a bbox across 12E)
  yields sheet codes only for its Polish part, an area entirely outside the range —
  an empty list (previously also sheet codes outside the range, which have no data).
  What to do: nothing — the removed sheet codes had no data anyway; code that
  treated an empty list as an error now gets it for an area entirely
  outside Poland.
- `kartograf landcover download --source bdot10k` with `--bbox`, `--godlo`
  or `--geometry` downloads all counties in the area (previously one, from the
  centre of the area — the rest of the area silently without data) and prints
  a `Downloaded to:` line for each file.
- The BDOT10k file is always named `bdot10k_teryt_<TERYT>.gpkg` (`.zip` for
  SHP), also with `--bbox`/`--godlo`/`--geometry` — it contains the whole county
  package. The previous `bdot10k_bbox_*`/`bdot10k_godlo_*` are not
  recognised; download the area again. A file with a layer filter carries their
  codes in the name (`bdot10k_PTWP-SWRS_teryt_<TERYT>.gpkg`).
- `LandCoverManager.download_by_bbox`/`download_by_godlo` for BDOT10k: an area
  from several counties ends with `ValidationError` with a list of codes (use
  `download_all_counties`), an area without a county — `NoCoverageError`; the sidecar
  of a single-county file has `extra.parent_request` (the task area).
- `Bdot10kProvider.download_by_bbox` (and `LandCoverManager` for BDOT10k)
  accepts an area in any supported CRS — previously a CRS other than
  EPSG:2180 ended with `ValueError`; the area is converted to EPSG:2180
  for the PRG query. The private `Bdot10kProvider._get_teryt_for_point`
  (WMS GetFeatureInfo) and `WMS_ENDPOINT` are removed without replacement — use
  `teryt_for_point`/`discover_teryts_for_bbox`.
- Library: `create_nmt_provider`, `DownloadManager` (without a provider or
  with a provider without its own `vertical_crs`) and `download_pl_cutout` with
  `resolution="5m"` and `vertical_crs="KRON86"` end with `ValidationError`
  (NMT 5 m exists only in EVRF2007); previously they silently switched the CRS to
  EVRF2007 with a warning in the log. What to do: give `vertical_crs="EVRF2007"`
  (or `resolution="1m"` when KRON86 is needed). CLI — see the entry
  below (also an error).
- CLI: `kartograf download ... --resolution 5m --vertical-crs KRON86`
  (NMT PL: sheet code, hierarchy, `--bbox`/`--geometry`, cutout `--target-crs`,
  also `--country auto`) ends with `Error: NMT 5m (PL) jest dostepny tylko
  w EVRF2007 ...` and exit code 1 before anything goes to the network; previously the CLI
  switched the CRS to EVRF2007 with an `Info:` message and downloaded (code 0).
  `--resolution 5m` without `--vertical-crs` works as before (EVRF2007). What to
  do: omit `--vertical-crs` or give `--vertical-crs EVRF2007`;
  for KRON86 use `--resolution 1m`.
- Downloading GUGiK NMT/NMPT/orthophoto sheets (CLI and `DownloadManager`, also
  cutout `--target-crs`) rejects records and files that passed in 0.7.0:
  a record URL without the sheet code, an ASC file outside the sheet code frame (B4) and an NMT/NMPT record
  declaring a vertical CRS other than the requested one — sheet (campaign)
  `DownloadError`, the file is not saved. The record checks run before
  skipping an already downloaded campaign, and `--force` (`skip_existing=False`) does not
  disable them. What to do: check the record in the GUGiK sheet index (geoportal) —
  the message gives the sheet code and the mismatch; this is a data error at the source that
  is worth reporting to GUGiK; for other sheets the download continues (list:
  sheet failure according to R5, `--campaigns all`: the remaining campaigns).
- The message `Error: --campaigns all nie dziala z --target-crs` no longer
  refers to "narzedzia 0.7.1" (campaign composition has no assigned release,
  ADR-030 erratum 6); exit code unchanged.
- `kartograf download --year RRRR` and `--min-density N` with `--product`
  nmt/nmpt/orto end with `Error:` and exit code 1 before the network (previously the options were
  silently ignored: code 0 and the newest data). Applies to all paths
  (sheet code, hierarchy, sheet list, `--bbox`, `--geometry`, `--target-crs`,
  `--country auto`, CZ); `--product laz` unchanged. Year selection for
  NMT/NMPT/orthophoto will arrive in 0.7.2. What to do: omit the option or — for the year —
  use `--min-year RRRR` (the newest campaign not older than the given year;
  PL only, without `--target-crs`; for CZ-only tasks — CUZK has no year
  selection, the message says to omit `--year`); scripts passing `--year`/
  `--min-density` to products other than LAZ must remove them.

### Fixed

- Merging a BDOT10k package no longer silently skips a table with a repeated
  name — it is a `DownloadError`.
- BDOT10k: package layers are extracted in a streaming manner (without loading
  the whole layer into memory), and `keep_raw` saves the ZIP without a second copy
  in memory. An I/O error during extraction, merging or ZIP writing
  (no space, out of memory) is a `DownloadError` (CLI: `Error:` with a description,
  exit code 1), not a bare `OSError`. A failed write of the original ZIP now removes the
  already saved GPKG — no data file is left without a sidecar.
- `cache stats`: `TERYT entries` counts PRG responses from `landcover download`
  (U5).

## [0.7.0] - 2026-10-08

Multi-country release. Main novelties relative to 0.6.1:

- **Czechia (CUZK, stage 1):** NMT DMR 5G (2 m, TM33 tiles) and DMR 4G (5 m,
  SM5 sheets) by sheet code or `--bbox`/`--geometry`; `--country
  {pl,cz,auto}` (default `auto`) splits a border area into separate
  files per country with a shared `extra.parent_request`.
- **New LAZ product:** LIDAR point clouds (ALS) from GUGiK via WFS
  (`--product laz`), the newest tile per area by default (ADR-029).
- **PL cutout `--target-crs`:** one merged NMT GeoTIFF for a bbox or
  geometry in EPSG:2180/5514/3045, local reprojection with a pinned operation
  (ADR-027); `download_pl_cutout` in the library.
- **GUGiK campaigns:** `--campaigns {newest,all}` and `--min-year`; files
  in `<segment>/kampanie/`, the standard path is a hard link to the
  newest campaign (ADR-030).
- **New `data/` layout and `.meta.json` sidecar:** segments
  `<product>/<country>_<crs>[_<variant>][_<vcrs>]` (ADR-026), next to each
  downloaded file CRS/licence/nodata/task metadata (keys per ADR-031).
- **Reliability:** a single HTTP transport (retries only for network/429/5xx),
  GUGiK sheet index layers solely from GetCapabilities, explicit
  `NoCoverageError` instead of silent substitutes, a metadata cache resistant
  to corruption.

### Breaking changes

#### `data/` layout and output files
- **New `data/` layout** (ADR-026): segments
  `<product>/<country>_<crs>[_<variant>][_<vcrs>]` explicitly encode the country, the horizontal
  CRS (PL: 1992/2000 — closing the deferred ADR-017) and the vertical one
  (kron86/evrf2007/bpv; orthophoto without a vertical one), e.g. `nmt/pl_1992_1m_evrf2007/`,
  `orto/pl_1992/`. `<crs>` follows from the sheet code format of EACH file separately
  (dots -> `2000`, hyphens -> `1992`; LAZ tiles — the tile's `uklad_xy`).
  Kartograf does not migrate `data/` automatically (table in "Migrating
  from 0.6.1"). The `landcover/` directory is unchanged (CORINE/SoilGrids file names
  — below). Canonical description: `docs/ARCHITECTURE.md`
  section 3.
- **Campaigns (ADR-030):** the real PL NMT/NMPT/orthophoto files reside solely
  in `<segment>/kampanie/<date>_<id>/<sheet code hierarchy>/<sheet code>.<ext>`;
  the standard path `<segment>/<hierarchy>/<sheet code>.<ext>` is
  a hard link (or a copy) to the newest local campaign
  (details in Added, "GUGiK campaigns"). A regular file at the standard
  path (e.g. moved over from 0.6.1) is unknown to Kartograf:
  the first run downloads it again into `kampanie/` and replaces it with
  a link. Copy `data/` only preserving hard links
  (`rsync -aH`/`cp -a`), otherwise a duplicate appears.
- **The default `newest` queries the sheet index on every run** when the
  record cache (7 days) has expired, and downloads the newer campaign if one has appeared;
  a re-run "without network" works only within the cache window.
- `FileStorage.list_files()` returns standard paths by default — without
  `kampanie/` and without dangling links (`list_files(campaigns=True)` = only
  `kampanie/`).
- **BDOT10k `--format SHP` / `format="SHP"`** writes a ZIP archive
  with shapefiles under the `.zip` extension (e.g. `bdot10k_teryt_1465.zip`,
  sidecar next to it) and returns that path (also via bbox/sheet code); in 0.6.1 the ZIP
  went to the given path, usually `.gpkg`, which pretended to be a GeoPackage.
  The CLI prints the actual path (review N1).
- **`LandCoverManager.download_by_teryt/download_by_bbox/download_by_godlo`
  without `output_path` name files the same way as `download()`** — it was
  `CORINE Land Cover_N-34-130-D.gpkg` (spaces, source label), it is
  `corine_2018_godlo_N-34-130-D.<ext>` (pattern below); the extension is set by the
  provider (CORINE `.tif`/`.png`, SoilGrids `.tif`). Scripts that build the
  result path from the source name need fixing (A5-2, N14).
- **`soilgrids hsg` names the default file with the depth:**
  `hsg_<sheet_code>_<depth>.tif` (e.g. `hsg_N-34-130-D_0-5cm.tif`) and
  `hsg_bbox_<depth>.tif`; it was `hsg_<sheet_code>.tif` / `hsg_bbox.tif`, so
  successive `--depth` values silently overwrote the result. The HSG sidecar with `--godlo`
  / `calculate_hsg_by_godlo` also writes `request.sheet` (next to the
  derived `bbox`/`bbox_crs`); `--bbox`/`--geometry` without `sheet`.
  Scripts that build the HSG result path need fixing. The statistic
  (`stat`) is not a CLI parameter (always `mean`); in the library the file name
  is chosen by the caller (`output_path`).
- **Land cover file names carry content parameters** (U3, silent data
  loss in 0.6.1): `soilgrids ... --property clay`, followed by `--property
  sand` for the same area wrote the same file
  `soilgrids_bbox_<coords>.tif` — the second result silently overwrote the first;
  the same for CORINE with a different `--year`. New pattern
  `<source>[_<parameter>...]_<mode>_<id>.<ext>`, `<source>` = the value of
  `--source` (`bdot10k`/`corine`/`soilgrids`), parameters including default
  values:
  `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif` (e.g.
  `soilgrids_clay_0-5cm_mean_bbox_770000_509000_772000_511000.tif`),
  `corine_<year>_godlo_N-34-130-D.tif` (`.png` from the WMS preview); it was
  `soilgrids_bbox_<coords>.tif` and `corine_land_cover_bbox_<coords>.<ext>`.
  BDOT10k unchanged (`bdot10k_teryt_1465.gpkg`/`.zip` — the format is distinguished by
  the extension). The same parameters = the same path (a repeated download
  overwrites as before). The sidecar records the parameters in `request`
  (`property`/`depth`/`stat`, `year`, `format`), and the GeoTIFF result's `nodata` is
  read from the file (`null` when the file does not declare it). Files from 0.6.1
  (old names) are not recognised — Kartograf neither changes nor
  reads them.
- **`DownloadManager` takes the segment from the provider:** without an explicit `storage=`
  the subdirectory comes from the provider descriptor (it was: always the NMT 1m segment,
  so `DownloadManager(provider=GugikNmptProvider())` wrote to the NMT directory
  and with `--force` overwrote its files; now `nmpt/pl_<crs>_1m_<vcrs>/`,
  A2-2), and the vertical CRS of the segment comes from the PROVIDER, not from the manager flag
  `vertical_crs=` (`DownloadManager(provider=GugikProvider(vertical_crs=
  "KRON86"))` wrote to `nmt/pl_1992_1m_evrf2007/` next to a sidecar with
  `EPSG:9650`; applies to the library, not the CLI).
- **Output directories are created only on write:** `LandCoverManager()`
  does not create `output_dir` (default `./data/landcover`) in the constructor,
  and `MetadataCache()` does not create the `.kartograf_cache.db` file on
  construction (details in Changed). Code that assumes `output_dir` exists
  right after `LandCoverManager(...)` must create it itself.

#### Sidecar `.meta.json`
- **The sidecar is new in 0.7.0** (next to each downloaded file, schema
  `kartograf-meta/1`, description in Added). The keys are English (ADR-031) —
  consumers reading sidecars from the 0.7.0-dev development versions must
  switch to the new names; the schema stays `kartograf-meta/1` (unreleased before 0.7.0),
  with no compatibility layer:

  | Was (0.7.0-dev) | Is |
  |---|---|
  | `request.godlo` (all tracks) | `request.sheet` |
  | `extra.source.godlo` | `extra.source.sheet` |
  | `extra.source.aktualnosc` / `aktualnosc_rok` | `extra.source.acquisition_date` / `acquisition_year` |
  | `extra.source.uklad` | `extra.source.declared_crs` |
  | `extra.source.zrodlo_danych` | `extra.source.data_source` |
  | `extra.source.numer_zgloszenia`, `extra.campaign.zgloszenie` | `survey_work_id` (in both) |
  | `extra.source.skorowidz` | `extra.source.index_url` |
  | `extra.source.dt_pzgik`, `extra.campaign.dt_pzgik` | `pzgik_date` (in both) |
  | `extra.source.kolor` (orthophoto) | `extra.source.color` |
  | `extra.godlo_kafla` / `rok` / `gestosc` (LAZ) | `extra.tile_sheet` / `year` / `nominal_density` |
  | `extra.uwaga` (CORINE PNG) | `extra.note` |
  | `extra.podil` (CZ SM5) | `extra.cz_share` |
  | `extra.sheet_sources[]`: `godlo`, `aktualnosc` | `sheet`, `acquisition_date` |

  `teryt` stays (the register's proper name). Canonical table:
  `docs/ARCHITECTURE.md` 3.2. Consequences for old local data —
  "Migrating from 0.6.1", data from 0.7.0-dev.

#### Library API
- **Deep provider import paths changed without shims**
  (`from kartograf.providers.bdot10k import Bdot10kProvider` ends in
  `ModuleNotFoundError`); the public `from kartograf import ...` UNCHANGED.
  Table in "Migrating from 0.6.1".
- **The `LandCoverProvider.download_by_teryt` wrapper narrows its positional arity**:
  positionally it accepts only `teryt`, `output_path`, `timeout`; a further
  positional argument (e.g. `format` in `Bdot10kProvider.download_by_admin_unit`
  as the 4th argument) ends in `TypeError` — pass it as a keyword
  (`format=...`).
- **`SoilGridsProvider.download_by_teryt()` raises `NotImplementedError`** —
  until now it returned, as a success, data for a fixed 60x60 km area around the centre of the
  VOIVODESHIP (2-digit TERYT prefix), identical for every municipality (Polish gmina).
  Use `download_by_bbox()` or `download_by_godlo()` (A4-3).
- **`GugikProvider.download_bbox(vertical_crs="EVRF2007")` ends in
  `ValidationError`** with a remedy, before going out to the network — GUGiK withdrew the
  WCS endpoint `DigitalTerrainModelFormatTIFFEVRF2007` (404 also for
  GetCapabilities), so WCS NMT 1m works only in KRON86; the WCS channel of the
  `pl.gugik.nmt_1m` descriptor declares only `EPSG:9650` (WCS NMPT is
  not affected). EVRF2007 heights from a bbox: `--bbox` (OpenData sheets)
  or the `--target-crs` cutout/`download_pl_cutout` (A1-4).
- **`find_sheets_for_bbox()`/`find_sheets_for_geometry()`: touching
  edges are not an intersection** — a positive intersection area counts, so
  a bbox equal to a sheet in its CRS (EPSG:4326 for PL-1992, zone
  2176-2179 for PL-2000) returns ONLY its sheets (a bbox in EPSG:2180
  passes through a wider WGS84 envelope and also returns neighbours — e.g.
  9 sheet codes for `N-34-130-D-d-2-4`). The same on a grid line and on the border of
  PL-2000 zones (A1-7, A9-1):

  | query | was | is |
  |---|---|---|
  | bbox of sheet `N-34-130-D`, `--scale 1:50000` | 9 sheet codes | 4 (`N-34-130-D-a..d`) |
  | bbox of sheet `N-34-130-D-d-2-4` (1:10000) | 4 sheet codes | 1 |
  | bbox of sheet `6.179.12.20` (PL-2000, `--scale 1:2000`) | 9 sheet codes | 1 |
  | point / degenerate bbox (<= ~2e-9 units) | `[]` (PL-1992) / 4 sheet codes (PL-2000) | 1 sheet (the one to the E/N of the grid line) |

- **`find_sheets_for_bbox`/`find_sheets_2000_for_bbox`: input validation**
  — an unknown `system=` value ends in `ValidationError` instead of a silent
  fallback to PL-1992; an inverted bbox (`min > max`) or one with NaN/inf —
  `ValidationError` (until now a garbage sheet, e.g. `BBox(10, 10, 5, 5)` ->
  `L-33-1-D-c-4-3`, or `ValueError`). A point bbox is still allowed.
- **`get_parent()`/`get_children()`/`get_all_descendants()` and `parse
  --hierarchy` for 1:1000000 <-> 1:500000: correct quadrant geometry** —
  the quadrant is computed from the position of the 1:200000 sheet in the 12x12 grid (6x6 blocks:
  A = NW, B = NE, C = SW, D = SE), rather than from bands of 36 consecutive numbers.
  72 of the 144 1:200000 sheets get a different parent than in 0.6.x,
  and `get_all_descendants()` of a 1:500000 sheet returns the proper quadrant
  instead of a horizontal band (A1-1).
- **Removed public attributes and methods of the classes exported in `kartograf`**
  (access ends in `AttributeError`):

  | Removed | Instead |
  |---|---|
  | `MetadataCache.get_url()` / `set_url()` | `get_record()` / `set_record()` (a sheet index record or a confirmed lack of coverage; the `url_cache` table is dropped on open) |
  | `WMS_LAYERS` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`) | no hardcoded list — layers from GetCapabilities (the provider's `LAYER_PATTERN`) |
  | `GugikProvider.FORMAT_EXTENSIONS` (also in `GugikNmptProvider`) | `get_file_extension()` (inherited from `BaseProvider`) |
  | `GugikOrtoProvider.OPENDATA_URL_PATTERN` | none — the sheet URL from the sheet index record |
  | `RETRY_BACKOFF_BASE` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`, `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`) | `kartograf.transport.http.RETRY_BACKOFF_BASE` (one backoff for all); the providers' `MAX_RETRIES` points to `transport.http.MAX_RETRIES` (3) |
  | `CorineProvider.DLR_YEARS` | none (dead code) |
  | `SoilGridsProvider.TERYT_WMS_ENDPOINT` | none — `download_by_teryt()` raises `NotImplementedError` |

- **Auth proxy: the `/token` endpoint and
  `AuthProxyClient.get_access_token()` removed** — they handed the raw token to the
  client process, which contradicts the proxy's role (credential isolation, ADR-002). The token
  goes solely to `*.copernicus.eu` and `*.eea.europa.eu` hosts: `/proxy`
  and `/download` accept only `https` (any other scheme = 403), `/proxy`
  rejects (403) every host outside the list (until now it downloaded from any URL
  of the client), and `/download` forwards the request to an `https` host outside the list
  WITHOUT the `Authorization` header (a CLMS presigned `DownloadURL` may be on a CDN)
  (A4-10).
- **The `kartograf.cli.commands` facade no longer re-exports the command
  implementations** — an import from the facade ends in `ImportError`; the canonical ones are the
  `cli/*_cmd.py` modules: the public `cmd_landcover_download`,
  `cmd_landcover_list_layers`, `cmd_landcover_list_sources`,
  `cmd_soilgrids_hsg` and the private `_cmd_download_bbox`,
  `_cmd_download_geometry`, `_download_godlo_list`,
  `_create_provider_and_storage` (from `kartograf.cli.download_cmd`). The facade
  keeps `main`, `create_parser`, the dispatchers `cmd_parse`, `cmd_download`,
  `cmd_landcover`, `cmd_soilgrids`, `cmd_cache`, `create_progress_callback`
  and the `format_*` formatting helpers (A5-1, K9).
- **`NoCoverageError` is a subclass of `DownloadError`** (`except DownloadError`
  catches both), and `GridMismatchError` is a subclass of `ValidationError`.
- **`import kartograf` eagerly loads `rasterio`** (GDAL/PROJ) — the CZ exports
  in `__init__.py` import `providers/cuzk/client.py`, which imports
  `rasterio` at module level; the cost is approx. +60 ms on import. A broken
  GDAL/PROJ (e.g. a missing native library) breaks `import kartograf` itself,
  not only the first raster call — relevant for Hydrograf/Hydrolog
  (ADR-023, "Additional findings" item 2).

#### CLI and behaviour
- **The default country is `--country auto`** — in 0.6.1 the `--country` option
  did not exist and every task went to GUGiK. For `--bbox`/`--geometry` without an explicit
  `--country`: an area crossing the envelopes of two countries is downloaded
  from EACH of them (separate files and sidecars, shared
  `extra.parent_request`); the CZ envelope is RECTANGULAR (it reaches 18.86 E
  and 51.06 N), so a task from southern Poland additionally gets a file
  and sidecar from CUZK (outside the actual border a same-nodata raster with `Warning:`,
  not an error) — workaround: explicit `--country pl`. Options without a Czech
  counterpart resolve the country to `pl` (details in Added, "Country selection")
  (A6-3, N6-2; ADR-023 points 4-5).
- **Downloading a hierarchy or a list of sheets with failures ends with code 1**
  and `Error: N z M arkuszy nie pobrano (blad pobrania, nie brak danych):
  <sheets> — ponow pobranie` with the full list — previously: code 0 despite
  missing sheets; applies to sheet code and `--bbox`/`--geometry` (A2-3).
  A mere lack of coverage for some sheets gives `Warning:` and code 0 (Added, "NMT PL").
- **Lack of source data is a `NoCoverageError`, not a silent substitute:** when
  selecting a GUGiK sheet, instead of a PL-1992 file under a PL-2000 sheet code, a file
  of 0.5 m for a 1 m task, or a child sheet; for PL-2000 1:10000
  with only children, the hint `--scale 1:2000`. A failure of the sheet index layer
  or GetCapabilities is a `DownloadError` instead of falling back to an older
  campaign or a hard-coded list of layers (K3, K4, S4).
- **The CLI rejects `--product nmpt --resolution 5m` and `--product orto
  --vertical-crs ...`** instead of silently ignoring them (V2-N1).
- **Removed the `GML` format** — `--format GML`, the entry in `landcover
  list-sources` and `get_supported_formats()`; it was never implemented
  (the task ended with a GPKG file) (A6-2).
- **Sheet selection from an EPSG:2180 bbox crossing the 19°E meridian returns
  more sheets** — the WGS84 envelope is computed from densified edges (description
  in Fixed); redundant sheets outside the bbox are possible.
- **HSG: canonical USDA triangle thresholds** (ADR-025) — the oblique boundaries of the standard
  (`silt + 1.5*clay`, `silt + 2*clay`) replaced the approximations by
  vertical/horizontal lines, the rules are in one place, so
  `classify_usda_texture()` (scalar) and `classify_usda_texture_array()`
  (array, used by `calculate_hsg_by_bbox`) give identical results
  (equivalence pinned by a test over the whole simplex at 1% steps). Effect on 5151
  simplex points, "was -> is":

  | HSG change | points | share of simplex | texture change |
  |---|---|---|---|
  | A -> B | 136 | 2.64% | `loamy_sand` -> `sandy_loam` |
  | C -> B | 85 | 1.65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
  | D -> C | 5 | 0.10% | `sandy_clay` -> `clay_loam` |
  | **total** | **226** | **4.39%** | (the texture class changes for 427 points = 8.29%) |

  Each change is by exactly one group. `TEXTURE_TO_HSG` is unchanged
  (a deliberate, documented deviation from TR-55: `sandy_loam`=B,
  `clay_loam`/`silty_clay_loam`=C) (A4-4, A4-8).
- **HSG: nodata pixels get 0 ("no data")**, not group B (details
  in Fixed).

### Migrating from 0.6.1
- **The existing `data/` cache is not reused** — NMT/NMPT/orthophoto sheets
  from 0.6.1 (`nmt_1m/`, `nmt_5m/`, `nmpt/`, `orto/`) are downloaded again,
  even after manually moving them to the new segments (a plain file in the standard path
  without a sidecar with `extra.link` is unknown, ADR-030). Manual
  migration does not save transfer: plan the space and time of the first
  download, remove the old directories after it. The `landcover/` directory is unchanged
  (file names — the point below). Table of
  directory correspondence (e.g. for your own scripts reading `data/`):

  | Old path | New path |
  |---|---|
  | `nmt_1m/` (1992 sheet codes) | `nmt/pl_1992_1m_<vcrs>/` |
  | `nmt_1m/` (2000 dotted sheet codes) | `nmt/pl_2000_1m_<vcrs>/` |
  | `nmt_5m/` | `nmt/pl_<crs>_5m_evrf2007/` |
  | `nmpt/` | `nmpt/pl_<crs>_1m_<vcrs>/` |
  | `orto/` | `orto/pl_<crs>/` (CIR: `orto/pl_<crs>_cir/`, B/W: `orto/pl_<crs>_bw/`) |
  | `laz/` (0.7.0-dev only) | `laz/pl_<crs>_<vcrs>/` |
  | `cz_dmr5g/` (0.7.0-dev only) | `nmt/cz_dmr5g_<vcrs>/` |
  | `cz_dmr4g/` (0.7.0-dev only) | `nmt/cz_dmr4g_<vcrs>/` |

  The old `nmt_5m/`, `nmpt/` and `orto/` held both sheet systems together, so
  one old directory corresponds to two segments.
- **CORINE/SoilGrids files in `landcover/`** have new names with parameters
  (`soilgrids_bbox_<coords>.tif` -> `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif`,
  `corine_land_cover_bbox_<coords>.tif` -> `corine_<year>_bbox_<coords>.tif`;
  likewise `godlo_<sheet_code>`). An old SoilGrids file does not say which
  parameter it concerns (the sidecar did not record it), so it is safer to download
  again than to rename; a CORINE file can be renamed manually
  if the vintage is known (in 0.6.1 the default is 2018). Scripts composing
  the result name should take the path returned by `LandCoverManager.download()`
  (CLI: `Downloaded to:`). BDOT10k is unchanged.
- **Imports** — provider modules have moved (no shims); the private
  `Bdot10kProvider._get_teryt_for_point()` still exists:

  | Old import | New import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |

  Simplest: `from kartograf import Bdot10kProvider` (and the other classes).
- **A single NMT raster for an area** — instead of assembling the mosaic yourself (or
  with `kartograf.transport.mosaic.mosaic_and_crop`, which is NOT
  exported in `kartograf` and is an internal step) use
  `kartograf.download_pl_cutout` (EVRF2007/KRON86, 1 m/5 m, target
  EPSG:2180/5514/3045; a sheet without data = nodata + `missing_sheets`);
  with your own provider, session or `MetadataCache` — the steps
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
  `run_pl_cutout(provider=...)`.
- **Other consumer-visible changes:** a sidecar `<file>.meta.json`
  next to every downloaded file (a consumer, e.g. Hydrograf, reads the English
  keys of ADR-031); `except DownloadError` also catches `NoCoverageError`;
  `import kartograf` requires a working `rasterio`; arguments of
  `download_by_teryt` after `timeout` are keyword-only; in the CLI, for tasks
  from southern Poland pass `--country pl` if the CUZK file is
  not needed.
- **Data from the 0.7.0-dev development versions** (does not concern 0.6.1 users):
  - `laz/`, `cz_dmr5g/`, `cz_dmr4g/` can be moved according to the table above —
    they are skipped solely on the existence of the file (no campaign); read `<vcrs>`
    from the sidecar (`vertical_crs`). The earlier flat layout of CZ cutouts
    (`cz_dmr5g_<coords>.tif` in the output root) was replaced by
    `<segment>/bbox/<coords>.tif`.
  - CZ rasters and PL cutouts -> EPSG:5514 with the sidecar `S-JTSK to ETRS89 (3)`
    were computed with the Slovak operation EPSG:4829 — they may be shifted by 1-5 m
    (e.g. 1.25 m to the south for TM33 tiles, 4.92 m in western Czechia).
    The CLI prints `Info:` when skipping them, but does not rebuild
    automatically: rerun with `--force`.
  - PL cutouts built before the crop was snapped to the sheet grid have
    content shifted by a fraction of a pixel and the same file names — rebuild
    with `--force` (also downloads the sheets again) or, more cheaply: delete only the cutout
    file and run without `--force` (cached sheets will be used).
  - Sidecars with Polish keys are not migrated: a campaign sidecar without
    `extra.campaign.pzgik_date` yields the link key from the directory name
    (a lower estimate), `sheet_sources` entries without `sheet` do not count
    as incomplete sheets when skipping a cutout, and a
    `record_cache`/`campaigns_cache` entry with Polish keys is a cache
    miss (the sheet index is queried again, the entry overwritten). Refreshing
    sidecars: `--force`.
  - Record cache entries from before the `NoCoverageError.hints` hints have no
    hints until the TTL expires (7 d).
  - A symlink in the standard path (from before erratum 4 of ADR-030) is an unknown
    path; the campaign file is local, so `newest` does not download it,
    it only replaces the symlink with a hard link.

### Added

#### Czechia (CUZK, stage 1)
- **`providers/cuzk/`:** `CuzkClient` — the first descriptor-driven
  engine (URLs solely from `AccessChannel.endpoint`): `query()`
  with pagination and a client-side filter for redundant selection,
  `export_image()` with tiling and CRS override, `fetch_file()` (ZIP
  openzu -> TIFF+TFW); `SheetIndex`/`SheetInfo` — SM5/TM33 sheet index
  from KladyMapovychListu (SM5 sheet by sheet code: `SheetIndex.sm5_sheet`);
  `CuzkDmrProvider` + the factory `create_dmr_provider` (one place for Czech
  defaults) — DMR 5G (2 m, TM33 sheet code) and DMR 4G (5 m, SM5 sheet code), bbox via
  `exportImage`; repair of CRS metadata in DMR4G-TIFF files and in `exportImage`
  results. `nmt` only; `nmpt`/`orto`/`laz` for CZ are stage 2.
- **`exportImage` natively in EPSG:5514:** the CUZK server receives tasks
  only in the native CRS (descriptors `server_reprojection=False`,
  A1-6). The service ceiling is 15000 x 4100 px, the real barrier ~8 Mpx — the client
  tiles with a budget of 4 Mpx per request, tiles anchored at the task's NW
  corner (the last mosaic row without `-9999`, seams bit for bit, no
  content shifts between tiles). The pixel is exactly 2 m/5 m (snap from the
  NW corner, also for a single cutout); the result bbox may differ
  from the task by <= half a pixel on the E/S edges. A damaged tile ends
  with a `DownloadError` with the output file cleaned up (A3-1, A3-3, K6, N3).
- **Local reprojection with a pinned operation (ADR-024):** `--target-crs`
  and the TM33 tile (warp to the EPSG:3045 grid; the SM5 sheet is 1:1) are computed by
  `rasterio.warp` with a forced operation pipeline (`COORDINATE_OPERATION`),
  shared with the PL path (`transform/raster.warp_to_grid`). The S-JTSK ->
  ETRS89 step is the Czech EPSG:1622/1623 (1.0 m), not the Slovak EPSG:4829.
  Tiling and mosaic on the native side (before the warp — seams are not
  baked in by interpolation), nodata does not enter interpolation, atomic
  write; a failed reprojection (also with `--force`) does not delete the previous
  cutout/tile. A lack of a safe horizontal operation aborts in the provider
  constructor, before any transfer; horizontal policies pass `probe_point`,
  so a foreign country's local grid (e.g. `sk_gku`) returning `inf` is
  rejected (K2, A1-2).
- **Vertical transformation Bpv -> EVRF2007** (optional, `--vertical-crs
  EVRF2007`): EPSG:8357 -> EPSG:5621, pinned operation 0.1 m, offset
  +0.11..+0.15 m increasing S->N, computed per pixel; a raster without a
  geotransform is rejected (A3-5). `KRON86` for CZ is
  unreachable (GUGiK grids are not public).
- **`core/parser_tm33.py` — `ParserTM33`:** a computable grid of 2x2 km TM33 tiles
  (EPSG:3045, sheet code `{E_km}_{N_km}` = SW corner; odd
  kilometres, e.g. `301_5550`, are invalid), modelled on `Parser2000`;
  in `parser_registry` as `cz_tm33`/`cz_sm5` (before the pl1992 fallback;
  patterns `CZ_TM33_PATTERN`/`CZ_SM5_PATTERN`).
- **Registry:** descriptors `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g`, `CountryProfile`
  for CZ (rectangular envelope in EPSG:4326, ADR-023), `all_countries()`;
  `AccessChannel.endpoint` — the only source of URLs for descriptor-driven
  engines (PL channels have `endpoint=""`, the source of truth is the provider
  constants).
- **An SM5 sheet code without `--resolution` downloads 5 m** (also under `--country
  auto`); an explicit `--resolution 2m` with an SM5 sheet code is an `Error:` (code 1) before
  the provider is created, without network. TM33 tile and CZ `--bbox`/`--geometry`:
  default 2 m (or 5 m). Library: `CuzkDmrProvider`/
  `create_dmr_provider` are bound to the resolution and for SM5 require
  `resolution="5m"`.
- **CZ `--bbox`/`--geometry` always gives a single cutout**
  `<segment>/bbox/<coords>.tif` (e.g.
  `nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif`); a failed
  cutout does not leave an empty `bbox/` directory.
- **`Downloading ...` in the CZ path only at the start of the transfer** (sheet code,
  `--bbox`/`--geometry`, also under `auto`): an unknown SM5 sheet, a failure of the
  index query or an invalid TM33 tile gives only `Error:`.
  Library: `CuzkDmrProvider.download`/`download_bbox` accept a
  keyword-only `on_download: Callable[[], None] | None`, called once, after
  validations, right before downloading the SM5 file / the first `exportImage`.
- **SM5 index in the cache:** table `sheet_cache` (TTL 30 days),
  `kartograf cache stats` prints `Sheet entries`; `--force` queries the index
  again and stores it (`MetadataCache(refresh=True)`, D16).
- **CZ sidecar:** `transform.horizontal = "pinned: <operation description>
  (<precision> m)"` symmetrically to `transform.vertical` — also for TM33
  tiles downloaded by sheet code (the 5514 -> 3045 reprojection is described); the SM5 path
  (openzu files in 5514) has no horizontal part; `extra.cz_share`.

#### Country selection (`--country`) and border areas
- **`--country {pl,cz,auto}`** (default `auto`): sheet code — country
  from the sheet code format; area — every country with an intersecting
  rectangular envelope (under `auto` clipped to it), separate files with
  a shared `extra.parent_request` (the original task bbox, its CRS and
  the **attempted** — not necessarily downloaded — countries), without
  merging PL+CZ (R6). Sheet-code mode does not get `parent_request`.
- **PL-only options resolve `auto` to `pl`:** `--product nmpt|orto`,
  `--system`, `--vertical-crs KRON86`, `--resolution 1m` on a disputed
  area give `Info: --country auto -> pl (...)` on stderr (also with
  `-q`) instead of code 1 (ADR-023 point 5, N6-2). Options that cannot
  be resolved for a country (`--resolution 2m`/`--vertical-crs Bpv`
  on an area reaching PL; `--product` other than `nmt`, `1m`,
  `KRON86`, `--system` for CZ) are rejected before the download with
  a hint to give an explicit `--country`; `--product laz` on an area
  reaching CZ — `Error:` with the hint `--country pl`. `--target-crs`
  works for both countries and does not decide the selection.
- **Clipping to the envelope** prints `Info:` only when it really limits
  the download (`--geometry` without `--target-crs` determines the PL sheets
  from the whole geometry — no Info for PL; part of CZ may be clipped);
  untouched PL edges remain original (no widening through a CRS round-trip).
  Cutouts carry the clipped extent in the file name and `request.bbox`, the
  `--bbox` list mode determines sheets from the clipped bbox (sidecars with
  `request.sheet`); explicit `--country pl` does not clip. A bbox entirely
  outside the envelopes = `Error:` code 1 without network access (S3).
- **Exit codes:** 0 when at least one country
  delivered a result; failure of the other gives
  `Warning: czesc <country> zadania zakonczyla sie bledem (patrz Error wyzej) — pobrano <country>; kod 0 (...)`
  (without guessing the cause: no coverage or a source failure);
  code 1 when all countries failed or `--country` was explicit (A3-2,
  ADR-023 point 4). A PL/CZ cutout entirely nodata gives `Warning:`
  and code 0 (N2). `Info:`/`Warning:` go to stderr despite `-q`.
- **`--bbox-crs`** also accepts `EPSG:5514` (S-JTSK) and `EPSG:3045`
  (ETRS89 / UTM 33N) alongside `EPSG:2180`, `EPSG:4326`, `EPSG:2176-2179`
  (give negative Krovak bboxes as `--bbox=...`). A bbox or geometry file
  in a Czech CRS leaves Krovak through a pinned operation, not the default
  transformer (for PL the grid and cutout name would otherwise be shifted
  by approx. 1.2 m); `parent_request.bbox_crs` then carries the file CRS.
- **`--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}`** in `--bbox`/`--geometry`
  mode for both countries (CZ: `exportImage` cutout, PL: merged
  cutout); sheet code + `--target-crs` = error. On the border,
  `--country auto --target-crs` produces two cutouts PL+CZ with a
  shared `parent_request`. `--vertical-crs {KRON86,EVRF2007,Bpv}`.
- **Default values per country:** `--resolution`/`--vertical-crs`/`--system`
  when not given are resolved only after the country is determined
  (PL: 1m/EVRF2007/1992; CZ: 2m/Bpv, `--system` does not apply).

#### LAZ — LIDAR point clouds (ADR-029)
- **`GugikLazProvider`** — `.laz` files (ALS measurement data) via
  **WFS** (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`),
  area discovery: sheet code (<= 1:10000) / `--bbox` / `--geometry` ->
  EPSG:2180 bbox -> `discover_tiles()` (WFS GetFeature). WFS BBOX and
  envelope in axis order (N,E), an intersection guard rejects tiles
  outside the area (K1). Tiles are finer than 1:10000; the tile sheet
  code is a label (not parsable), `url_do_pobrania` is taken directly
  from WFS. WFS metadata: `akt_rok`, `akt_data`, `char_przestrz`
  (density), `uklad_xy`, `czy_ark_wypelniony`, frame `msGeometry`.
- **Tile selection by area coverage** (default, without `--year`): tiles from
  the newest `akt_rok` (within a year the newer `akt_data`); an older tile is
  skipped when its common part with the area is covered by the already selected
  tiles (frames in EPSG:2180, each +1 m tolerance, `COVERAGE_TOLERANCE_M`), so
  PL-1992 and PL-2000 of the same place do not duplicate. A tile contributing
  an uncovered piece stays (whole); a tile with `czy_ark_wypelniony=NIE`
  does not displace older ones; a tile whose frame does not intersect the
  area (only the envelope) is skipped. `--year` = only that year, coverage
  dedup within the year. Skipped tiles: `Info:` on stderr (also with `-q`),
  in the library `superseded`. New module `core/coverage.py` (intersection,
  difference and buffer of convex polygons, without new dependencies).
- **Vintages:** the list of years exclusively from WFS GetCapabilities
  (`_fetch_available_years`/`_get_available_years`, in-memory cache of successful
  responses only; failure = `DownloadError`). An explicit `--year` is checked
  against the GetCapabilities of the given service before GetFeature: a
  non-existent year = `rocznik ... nie istnieje w usludze ... (dostepne: ...)`
  without a retry suggestion; a vintage discovery failure =
  `DownloadError` with the year and information about an incomplete result;
  `No LAZ tiles found` means a complete set of correct responses (N7).
- **CLI:** `kartograf download <sheet_code|--bbox|--geometry> --product laz`
  with flags `--year`, `--vertical-crs` (default EVRF2007),
  `--min-density` (NOMINAL density from WFS — the actual one is
  sometimes several times higher, E16), `--campaigns`, `--min-year`;
  parallel download (`--workers`), skipping existing files. Failure
  of even one tile = `Error: N z M kafli LAZ nie pobrano ...`
  with the FULL list, code 1 (downloaded tiles stay).
- **Layout:** `laz/pl_<crs>_<vcrs>/<hierarchy of sheet code>/<original name>.laz`,
  `<crs>` per tile from `uklad_xy` (`LazTile.uklad`); an unrecognised
  value = `ValidationError`, and discovery skips such a tile with a
  warning in the log (without guessing from the sheet code format).
  `FileStorage.get_raw_path(..., uklad=)` — path for a non-parsable sheet
  code without `SheetParser`; the same segment as the CLI is given by
  `uklad=tile.uklad`, without it the CRS follows from the sheet code format.
- **Library API:** `kartograf.download.laz` — `download_laz_area(bbox, ...)`,
  `run_laz_download(selection, ...)`, `LazDownloadResult`
  (`downloaded`/`skipped`/`failed`/`superseded`), `LazTileFailure`,
  `write_laz_sidecar`; `GugikLazProvider.select_tiles(...)` returns
  `LazTileSelection` (`tiles`, `superseded` = `SupersededLazTile`),
  and `discover_tiles` = `select_tiles(...).tiles`; `select_tiles`
  validates `min_year` like `DownloadManager`. `LazTile` with fields
  `footprint` (frame in EPSG:2180, axes E,N), `date`, `full_sheet`
  (with default values). Exports in `kartograf`: `GugikLazProvider`,
  `LazTile`, `LazTileSelection`, `SupersededLazTile`, `download_laz_area`,
  `run_laz_download`, `LazDownloadResult`, `LazTileFailure`. A tile failure
  is not an exception (`result.failed`). One HTTP session per thread
  (`SessionPerThread`), an injected session (`session=`) always wins.
- **Tile sidecar:** `request.year`/`request.min_density` (when given),
  `extra.tile_sheet`, `extra.year`, `extra.nominal_density`; in
  `--bbox`/`--geometry` mode `extra.parent_request` (bbox in the given
  CRS, `countries: ["PL"]`). A provider without `descriptor_key` gets
  `pl.gugik.laz`; a failed write logs `kartograf.sources.sidecar`.

#### PL cutout `--target-crs` (ADR-027)
- **CLI:** `--target-crs` with PL `--bbox`/`--geometry` gives one merged
  GeoTIFF `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif` (GUGiK sheet mosaic +
  crop + local warp with a pinned operation). Only `nmt` and PL-1992; readable
  errors for a sheet code, `--product nmpt|orto|laz`, `--system 2000`.
- **`EPSG:2180`** = crop on the sheet pixel grid (area extended outwards
  by < 1 px, values 1:1, `transform: null`, the file name carries the task
  coordinates). GUGiK sheet pixel corners lie halfway between multiples
  of the pixel (5 m: 5k + 2.5 m; 1 m: k + 0.5 m), some 5 m sheets of the
  2022 campaign have a different phase: sheets with different phases give
  `GridMismatchError(ValidationError)` with `.off_grid` and code 1 with a
  hint to use a different `--target-crs`. **Another target** — W1: warp of
  each sheet separately, phase deviations in `extra.off_grid_sheets` (S5).
- **Sheet selection** (`select_pl_cutout_sheets`) has a margin of 1 pixel (bbox mode and
  the R-01 sum); `--geometry` with `EPSG:2180` (without the R-01 sum) has no margin —
  the outermost column or row may be nodata (`docs/ARCHITECTURE.md` 4.3). `--geometry`
  covers the WHOLE envelope of the geometry without masking, and with reprojection
  the sheets are the sum of the sheet codes of the geometry and of the envelope with
  a margin (envelope filled with data; cost: with a sparse geometry the sheets of the
  whole envelope are downloaded). A sheet issued by the sheet index in the PL-2000
  system under a PL-1992 sheet code ends the build with an error with a description;
  an old PL-2000 sheet is not mixed into the PL-1992 cache — remove it and retry.
- **Data gaps:** a sheet without GUGiK data (`NoCoverageError`) = nodata +
  `Warning:` + `extra.missing_sheets` (`PlCutoutResult.missing_sheets`);
  another download failure = code 1; an area without data in
  any sheet = `ValidationError`. A result entirely empty despite
  downloaded sheets: `PlCutoutResult.all_nodata=True`, `Warning:`,
  `extra.all_nodata: true` (E15). Sheets of an incomplete campaign:
  `extra.sheet_sources[].full_sheet`, `PlCutoutResult.partial_sheets`,
  an empty cutout from them warns about an incomplete campaign, not about
  missing data (E13). A local campaign used on a sheet index failure:
  `PlCutoutResult.unverified`, `extra.unverified_sheets`, `Warning:` (I-1).
- **Skipping an existing result:** based on file existence alone;
  `PlCutoutResult(skipped=True)` restores `missing_sheets`, `off_grid_sheets`
  and `all_nodata` from the sidecar (without reading the raster), the CLI
  repeats the warnings. Reused sheets append `extra.parent_requests` without
  losing the original `parent_request`. `--force` rebuilds the cutout and
  downloads its sheets again; a cheaper rebuild: remove the cutout alone.
- **Campaigns:** a cutout is always `newest` and reads sheets
  through links; `--campaigns all` or `--min-year` with
  `--target-crs` = `Error:` code 1 before network access.
- **Library** (`kartograf.download.cutout`, export in `kartograf`):
  `download_pl_cutout(bbox, target_crs, ..., cache=)` and the steps
  `prepare_pl_cutout` (fail-fast, no network; non-factual vertical =
  `ValidationError`) -> `select_pl_cutout_sheets` -> `run_pl_cutout`
  (does not accept `campaigns`), types `PlCutout`, `PlCutoutSheets`,
  `PlCutoutResult`. The CLI is a wrapper over these functions.
  `run_pl_cutout` with an injected provider with a different vertical
  or resolution ends with `ValidationError` before the download. A bbox
  in a Czech CRS with a lower-case label or with spaces (`"epsg:5514"`)
  leaves Krovak through the pinned operation like `"EPSG:5514"` (m-2).
- **Mosaic and resources:** sheets wrapped in VRT with explicit EPSG:2180
  and Float32 (an ASC sheet with integers only does not turn the
  mosaic into Int32, sheets with and without `.prj` mix), source list
  sorted; sources opened lazily (a cutout from > 1024 sheets does not
  end with "Too many open files"; Linux descriptor limit 1024, macOS
  256); the intermediate mosaic file compressed (deflate, 512 px tiles,
  BigTIFF when needed). Before network access a free-space check — a
  LOWER estimate (result + sheets without a file in the standard path,
  pre-counted; under `newest` a sheet with a newer or removed campaign
  will be downloaded despite the link), `Info:` for cutouts >= 1 GiB,
  no hard limit. Both write paths are atomic: a failed build does
  not destroy the previous file and does not leave an empty `bbox/`.

#### GUGiK campaigns (ADR-030)
- **CLI `--campaigns {newest,all}`** (default `newest`) and **`--min-year YYYY`**
  (1900..2100, otherwise `Error:` without network access); PL only (GUGiK).
  `newest` = the ADR-028 rule, resolved on every run (network after the 7
  d cache expiry), downloads only missing campaigns. `all` = EVERY record
  after the hard ADR-028 filter from all layers, without a limit on the
  number of campaigns (`logger.info` with the count, once per sheet).
- **`--min-year`** = a bound on the year of `aktualnosc` (not `dt_pzgik`),
  for both strategies; a record without a determined year does not
  meet it (`all`: skipped; `newest`: `NoCoverageError` "starsza niz
  min_year" with the date of that campaign, list/hierarchy: status
  `no_coverage`). The year from the layer name serves only in `all` to
  skip a layer query (upper year < bound); `Starsze` is always queried.
- **Layout:** `<segment>/kampanie/<date>_<id>/<hierarchy of sheet code>/<sheet_code>.<ext>` +
  `.meta.json`; `<date>` = `aktualnosc` of the record, `<id>` = the first numeric
  segment of the file name in the URL, otherwise `u` + 8 hex characters of `sha1(URL)`.
- **Standard path link:** once per sheet after collecting
  campaigns, hardlink, and when unavailable — a copy with
  `Warning: hardlink niedostepny na tym systemie plikow — sciezka standardowa jest KOPIA najnowszej kampanii dla N arkuszy (...) (extra.link=copy)`
  (code unchanged). No symlinks (erratum 4: a symlink from Linux on
  an SMB share is unreadable for Windows clients, and shares limit
  the target length). The standard path sidecar is a regular file with
  `extra.link` (`hardlink`/`copy`) and `extra.link_target` (the only
  source of the target). The link is repointed only to a campaign with
  the key `(aktualnosc, dt_pzgik, url)` strictly greater than the key of
  the current target (from the sidecar, and when unreadable — from the
  directory name); otherwise unchanged (never backwards). Existence check:
  target from the sidecar (`samefile` for a hardlink); a removed campaign
  directory or a missing sidecar = missing file (re-download/re-link).
- **Format from the record's `format` field** (not from the URL extension); the file always
  has the canonical extension `.asc`/`.tif` (record 72675 with a `.xyz` URL is
  AAIGrid = an ordinary `.asc` campaign); no field (orthophoto, old cache entries) =
  the product's default format. After download the content is verified (AAIGrid
  header / TIFF signature); an unknown format or mismatched content =
  campaign failure (`DownloadError` with the format name, file removed), never
  a silent `.asc`. A campaign file without a sidecar (interrupted run) undergoes
  content verification before the sidecar is recreated.
- **The campaign file sidecar is mandatory** (`emit_sidecar(required=True)`,
  atomic write): a write failure = campaign failure (data file removed,
  link not moved); other sidecars are best-effort.
  `extra.campaign` = `{id, date, survey_work_id, source, full_sheet,
  pzgik_date}`, `request.campaigns` always, `request.min_year` only when
  given.
- **Failures:** partial failure of `all` on a sheet (e.g. an invalid
  `aktualnosc` of one campaign) = code 1 with the full list, the remaining campaigns
  downloaded, link to the newest valid one; a link failure (even of a
  copy) = sheet failure (code 1, the list continues also with
  `--workers 1`, downloaded campaigns remain). Race without locks: parallel
  calls on the same path may temporarily leave the link on an
  older campaign; the next `newest`/`all` repairs it (files
  in `kampanie/` untouched).
- **Sheet index outage with `newest` (I-1, erratum 5):** a TRANSPORT error
  of record resolution (network, HTTP 429/5xx; not lack of coverage, not other
  4xx or an OGC report) on a sheet with an existing local campaign is not
  a failure — the sheet is skipped using the local campaign (link unchanged),
  `Warning: <sheet_code>: skorowidz GUGiK niedostepny — uzyto lokalnej kampanii
  bez sprawdzenia nowszej (...)` on stderr also with `-q` (list: one
  `Warning:` with the sheet codes), code unchanged. `--campaigns all`, `--min-year`,
  `--force` and no local campaign — an error as before.
- **`all` summary** (without `-q`, also a single sheet code): `Downloaded
  <n> campaign files for <m> sheets to <dir> (<k> already existed)`
  (n = downloaded, k = already local).
- **CZ and LAZ:** a task without PL (a CZ sheet code also under `auto`, area/geometry
  with explicit `--country cz`, an entirely Czech area under `auto`) with campaign options
  = `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year
  dotycza tylko PL` (code 1, no network); an area under `auto` with PL and CZ = one
  `Info:`, CZ is downloaded as usual (current version of CUZK data). LAZ:
  `--campaigns all` = all tiles whose frame intersects the area, without
  ADR-029 deduplication (a tile intersected only by the envelope is skipped);
  `--min-year` = lower bound of `akt_rok`; `--min-year` and `--year`
  are mutually exclusive (`Error:`); LAZ without links.
- **Library:** `DownloadManager(campaigns=, min_year=)`,
  `DownloadManager.last_sheet` (`SheetFetch`: `godlo`, `path`, `skipped`,
  `downloaded`, `reused`, `link`, `unverified`), `DownloadResult.
  campaign_files`, `reused_campaign_files`, `copied`, `unverified` (sheet code ->
  error content); exports `kartograf.CampaignRef`, `kartograf.SheetFetch`;
  modules `download/campaigns.py` (`CampaignRef`, `validate_campaign_args`,
  `verify_file_format` — read `OSError` as `DownloadError`)
  and `download/links.py`; `FileStorage.get_campaign_path`,
  `FileStorage.list_files(campaigns=)`. PL providers: `resolve_campaigns`,
  `download_record`, `record_source`, `_resolve_record(parser, timeout,
  query)`; sheet index: `select_campaign_records`, `layer_upper_year`,
  `LAYER_FAMILY` (a layer from the product family outside `LAYER_PATTERN` =
  `logger.warning`, not queried). A library without `MetadataCache`
  queries the sheet index on every `download_sheet` (also for an already
  downloaded sheet) — pass the cache to the provider.
- **Cache:** table `campaigns_cache` (list of a sheet's campaigns, TTL 7 days,
  `--min-year` outside the key; after a partial scan it serves only bounds
  >= the scan bound, a lower one = rescan), `kartograf cache stats`
  prints `Campaign entries`.

#### NMT PL and the GUGiK sheet index
- **`NoCoverageError(DownloadError)`** — the source has no data for the sheet
  (all sheet index layers responded); `DownloadResult.no_coverage`
  (subset of `failed`), hints `NoCoverageError.hints` /
  `DownloadResult.no_coverage_hints`.
- **PL sheet list** (`--bbox`/`--geometry` without `--target-crs`, also
  sheet code hierarchy): missing data for one sheet does not interrupt the others
  (R5 tries all, regardless of `--workers`); `NoCoverageError` =
  `Warning:` and `DownloadProgress.status == "no_coverage"` (`∅` in the CLI);
  >= 1 file and only missing coverage -> code 0, all without data or
  a hard failure -> code 1 with the full list. A single sheet without data ->
  code 1. Hints (e.g. `uzyj --scale 1:2000` for PL-2000 1:10000) as
  `Info:` on stderr (no duplicates, max 5 lines + "i K innych"), without a
  `Downloaded 0 ...` summary (O-3/O-6/O-7, S2).
- **Record selection (ADR-028):** hard filter on sheet code (whole token), CRS,
  resolution 1 m/5 m, orthophoto RGB and date; in the first matching layer
  the newest `aktualnosc` wins, then `dt_pzgik`, URL, regardless of
  the full-sheet flag (K4). A record of a non-full sheet (`full_sheet:
  false`) wins when it is the newest, but the CLI prints `Warning:` (sheet code,
  list and cutout paths, also on skip), and `extra.source.full_sheet`
  records it (E13). A `NoCoverageError` hint about a sheet in another CRS
  has the form `<sheet_code> (<scale>) — uzyj tego godla lub --system X --scale Y`
  (also orthophoto; D14).
- **PL-2000 sheets published in EPSG:2180 coordinates** (observed
  in zone 7, e.g. `7.125.11.19`, `7.173.21.01`, with a non-integer `cellsize`
  0.99937 m): the sidecar records the file's actual CRS (`horizontal_crs:
  EPSG:2180`), the record's declaration in `extra.source.declared_crs`
  (`PL-2000:S7`), the file lies in the segment by sheet code; the CLI prints `Warning: N
  arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: <sheet_code>
  (godlo: EPSG:2178, plik: EPSG:2180)` on stderr (sheet code, list
  and hierarchy paths, also on skip and `-q`; the fact is read from the sidecar), code unchanged;
  the library logs the same via `kartograf.sources.sidecar` (E17).
  The remaining PL-2000 sheets have the zone EPSG 2176-2179 in the sidecar (N8).
- **Orthophoto: colour variant in the path** — RGB by default
  (`GugikOrtoProvider(color="RGB")`, newest RGB record, K5) in
  `orto/pl_<crs>/`, `color="CIR"` (infrared) in `orto/pl_<crs>_cir/`,
  B/W in `orto/pl_<crs>_bw/`; new `BaseProvider.storage_variant`,
  `FileStorage(variant=...)` (E12).
- **`DownloadManager`:** `download_sheets(godla, ...)`
  and `expand_sheets(godla)` (list of sheet codes, coarser PL-1992 expanded
  to 1:10000, duplicates once; failures collected in `last_result`); `last_result`
  (`DownloadResult`: succeeded/failed/skipped/no_coverage of the last
  `download_hierarchy()`/`download_sheets()`, cleared on entry to
  `download_sheet()`/`download_hierarchy()`/`download_sheets()`; the CLI
  derives the exit code from it, A2-5); `sidecar_extra=` (fields merged into
  `extra` of every sidecar, e.g. `parent_request`); `download_sheet(on_download=)`.
- **Factory `create_nmt_provider()`** (`providers/pl/__init__.py`) — a single
  place for Polish NMT defaults; the rule "NMT 5m only in EVRF2007" in one
  place (`kartograf.providers.pl.nmt_vertical_crs`), effect: correction to
  EVRF2007 — the CLI (`--resolution 5m --vertical-crs KRON86`) prints `Info:`
  on stderr (also with `-q`), the factory logs, `prepare_pl_cutout` rejects
  a non-factual vertical CRS with `ValidationError` (D11).
- **A single parser of the GUGiK CRS value** `sources.registry.parse_pl_uklad`
  (`PL-1992`, `PL-2000:S5..S8`, whitespace trimmed) for sheet index records,
  `horizontal_crs_for_uklad` (sidecar) and `LazTile.uklad`;
  an unusual value (e.g. `PL-2000` without a zone) is rejected consistently (record
  without a CRS, LAZ tile skipped with a warning, `ValidationError`)
  (E11, D3).

#### Sidecar `.meta.json` and `data/` layout
- **Sidecar `<file>.meta.json`** after every successful download (schema
  `kartograf-meta/1`: dataset, horizontal/vertical CRS, nodata, licence,
  `request`, `kartograf_version`, `transform`, `extra`) — a contract for
  Hydrograf. A write error does not interrupt the download (exception: campaign file).
  Fields of `extra` include: `source` (origin of the sheet), `sheet_sources`,
  `missing_sheets`, `off_grid_sheets`, `all_nodata`, `unverified_sheets`,
  `parent_request`, `parent_requests`, `campaign`, `link`/`link_target`,
  `fallback`, `derived`. Common wrapper `sources.sidecar.emit_sidecar`
  (operation format `pinned_label`); `build_metadata(capability=, nodata=)`
  — explicit channel choice by capability and explicit `nodata` (CUZK `exportImage`
  returns `noDataValue: null`). PL sidecars in `--bbox`/`--geometry` mode
  have `extra.parent_request` (a grouping key shared with CZ and LAZ).
- **`kartograf_version` in the sidecar and `kartograf --version`** for `dev`
  versions give `<version>+<short SHA>` (e.g. `0.7.0-dev+6db4408`), with
  uncommitted changes in `kartograf/` with the suffix `.dirty`
  (`kartograf/_version.py::build_version`, lazy, cached per process); without
  git or outside the repository — just `__version__`. Releases, `__version__`
  and `User-Agent` unchanged.
- **Vertical CRS -> codes** (`vertical_crs_code`): `KRON86` = `EPSG:9650`,
  `EVRF2007` = `EPSG:5621` (family, shared by PL and CZ), `EVRF2007-PL` =
  `EPSG:9651` (Polish realisation), `Bpv` = `EPSG:8357` (Baltic 1957, CUZK);
  PL sidecars declare the Polish realisation (`resolve_vertical_crs`).
- **Segments from descriptors:** `SourceDescriptor.storage_subdir` is a
  template with `{uklad}`/`{vcrs}`, the path is given by `resolve_subdir(uklad=,
  vertical_crs=)` (partial filling is legal, vcrs in lower case);
  `FileStorage(vertical_crs=)` (default `"EVRF2007"`),
  `FileStorage(subdir=...)`; `{uklad}` resolved per sheet code; an unresolved
  placeholder or an empty dimension (`vertical_crs=''`, also via
  `DownloadManager` with a provider with an empty vertical CRS) = `ValidationError`
  instead of a segment `nmt/pl_1992_1m_`. A single provider segment factory
  `download.storage.storage_for_provider` and cutout name
  `download.storage.bbox_cutout_path` (PL and CZ).

#### Land cover, HSG, CORINE
- **HSG has a sidecar** (`kartograf soilgrids hsg` /
  `HSGCalculator.calculate_hsg_by_bbox`): descriptor
  `global.isric.soilgrids`, `extra.derived = "hsg"`, source layers,
  depth, statistics.
- **CORINE without CLMS credentials:** the PNG preview (WMS) sidecar declares the
  actual CRS — `EPSG:3857` (EEA Discomap) or `EPSG:4326` (DLR, year
  1990) — instead of `EPSG:3035` (CLMS GeoTIFF only) and carries
  `extra.fallback = "wms_png"` with `extra.note` "podglad WMS, nie dane".
- **`LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`**
  (canonical) + `download_by_teryt`/`validate_teryt`/`source_url` as
  working compatibility aliases.

#### Metadata cache
- **`MetadataCache.get_record/set_record`** — a sheet index record
  (`{"source": ...}`) or a confirmed lack of coverage with the hint content
  (`{"no_coverage": true, "message": ..., "hints": ...}`), TTL 7 days;
  a negative hit reproduces the same `NoCoverageError`.
  `stats()["record_count"]`, `kartograf cache stats` prints `Record
  entries`. The CLI attaches the record cache in the PL paths (N6).
- **`MetadataCache(refresh=True)`** — reads = miss, writes normal;
  `--force` in the PL and CZ paths bypasses cache READ, but writes the fresh choice,
  so the next run without `--force` gets the new record (E14, D16).
- New: `MetadataCache.db_path`, `MetadataCache.error`, parameter
  `on_disabled=`, `stats()` keys `db_exists` and `error` (description
  in Changed).

#### Library and source architecture
- **`kartograf/sources/`** — source descriptors as data (zero IO on
  import): `SourceDescriptor`, `AccessChannel`, `TransportKind`,
  `LicenseInfo`, `CountryProfile` + registry (`get_source`, `sources_for`,
  `get_country`, `all_countries`, `vertical_crs_code`,
  `resolve_vertical_crs`).
- **`kartograf/transform/crs.py`** — a strict transformation policy:
  `TransformerGroup(allow_ballpark=False)`, accuracy filter, a probe
  rejecting grids of foreign countries (`inf`), `isfinite` check,
  `TransformError`/`TransformUnavailableError` with a remedy, `KNOWN_PATHS`;
  `PinnedTransform` carries a CRS pair (`src_crs`/`dst_crs`), accepts
  scalars or `numpy` arrays and exposes `gdal_operation()` (a PROJ pipeline
  for `COORDINATE_OPERATION` with axis order correction — a northing-first target
  without `axisswap` produced a raster entirely nodata); `build_pinned_transform`
  runs the probe inside the `network.set_network_enabled(...)` context;
  shared `CONTENT_POLICY` and `WARP_MARGIN_PX` for the PL and CZ paths (D9).
- **`kartograf.transform.raster.warp_to_grid`** — local raster reprojection
  (a single mosaic or a list of sheets, W1) with a forced pinned
  operation (ADR-024).
- **`kartograf/transport/`** — `download_to()` and `get_with_retry()` (described
  in Changed, "HTTP transport") and `mosaic_and_crop()` (rasterio.merge +
  clipping, nodata propagation; the result is written by
  `merge(dst_path=...)` — peak memory ~1.06x the raster size, A3-4;
  options `dst_kwds=`, `snap_to_source_grid=`, `assign_crs=`, `dtype=`,
  off by default — used by the PL cutout; a source off the majority
  grid = a warning in the log). `check_source_grid`, `has_valid_pixels`.
- **`kartograf.core.bbox`:** `BBox` (`kartograf.BBox`,
  `core.sheet_parser.BBox`, `core.geometry.BBox` are the same class),
  `validate_bbox`, `transform_bbox` (dense envelope: 21 points per
  edge, transformer cache, pinned operation via `transformer=` —
  duck typing), `is_czech_crs`; `transform/bbox.py::envelope_from_2180`
  for CORINE/SoilGrids (D19).
- **`kartograf/core/parser_registry.py`** — registry of sheet systems (literal
  `SYSTEMS`: pl2000, cz_tm33, cz_sm5, fallback pl1992; `detect_system`
  always returns `SheetSystem`); `SheetParser` and `FileStorage` delegate to
  the registry (identical results).
- **CLI split into modules** `cli/_parser.py`, `parse_cmd.py`,
  `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`, `cache_cmd.py`;
  `cli/commands.py` is a facade with the entry point `main` (unchanged).
- **`KARTOGRAF_DEBUG=1`** — full traceback instead of the shortened `Error: ...`
  for every exception reaching the `main` barrier (also
  `KartografError`; N1-1, N17).

### Changed

#### HTTP transport
- **One transport for all providers:** GUGiK files
  (NMT/NMPT/orto/LAZ/BDOT10k), CORINE, SoilGrids and CUZK are downloaded by
  `transport.http.download_to` with the hooks `validate=` (CORINE/SoilGrids:
  `reject_error_document` — a WMS/WCS XML/HTML report without retries) and `save=`
  (BDOT10k GPKG: ZIP extraction); queries (sheet index, WFS LAZ, TERYT
  BDOT10k, `CuzkClient.query`) use `get_with_retry` (optional `params=`).
  Replaces six copies of the download loop in the providers (D1).
- **Retry policy:** max 3 attempts (`MAX_RETRIES`, not configurable),
  only network errors, HTTP 429 and 5xx are retried; other 4xx (e.g. 404 for a
  wrong WCS coverage name) end immediately with the message `HTTP <code>
  (bez ponowien)`. The `Retry-After` header (seconds or HTTP date) extends
  the pause, max 60 s (`MAX_RETRY_AFTER`). A single backoff: 2 s, then 4 s
  (`backoff_delay`). `DownloadError.status_code` carries the HTTP code of the last
  attempt (previously `None`). Content errors (JSON, OGC report) are not retried.
  The TERYT BDOT10k query and the CUZK index are retried (previously a single attempt).
  New: `is_retryable`, `retry_wait`, `http_status`, `http_failure`
  (N5, N9).
- **Atomic write via `os.replace`** (also the BDOT10k GPKG merge) instead of
  `Path.rename` — on Windows `--force` over a downloaded sheet failed with
  `FileExistsError`. The target directory is created only after a successful HTTP
  response (a failed download does not leave an empty directory).
- **`DownloadError` messages in Polish** (`HTTP 404 (bez ponowien)`,
  `po 3 probach`); an NMT/NMPT/orthophoto file download error gives the file name
  from the URL, not the sheet code (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData): HTTP
  404`).
- **Sessions:** one HTTP session per thread (`transport.http.SessionPerThread`,
  `make_gugik_session`: keep-alive, `User-Agent: kartograf/<version>`) in
  all GUGiK providers, BDOT10k, CORINE (also CLMS queries
  in direct mode) and SoilGrids — instead of a new, never-closed
  `requests.Session()` on every call; providers keep
  `self._sessions` (D2). Sheet index GetCapabilities/GetFeatureInfo queries
  use a per-thread session and retries (S1).

#### NMT PL and the GUGiK sheet index
- **Sheet index layers (NMT/NMPT/orthophoto) exclusively from GetCapabilities** —
  shared `skorowidz._fetch_wms_layers` with the provider's `LAYER_PATTERN` (orthophoto:
  `SkorowidzeOrtofotomapy<year>`/`Starsze`, without `Zasiegi` variants),
  yearly layers in descending order, aggregate and `Starsze` layers at the end, in-memory cache
  of successful responses only. No hardcoded lists and no fallback: a GetCapabilities
  failure = `DownloadError`. GetCapabilities uses the provider timeout
  (30 s NMT/NMPT, 60 s orthophoto or `timeout=` from `download()`) instead of the
  hardcoded 10 s (N3, E10).
- **Diagnosis of sheet index failures:** a failure of all layers = service
  unavailability, not "no coverage for the sheet code" (A2-9); a partial failure with the sheet missing
  in the remaining ones = "coverage uncertain" (`DownloadError`, code 1).
  A response that is an OGC exception report (`ServiceExceptionReport`,
  `ows:ExceptionReport`, e.g. `LayerNotDefined` with HTTP 200) or a broken
  GetFeatureInfo template is a failed layer query, not a missing sheet
  (previously they gave a false `NoCoverageError`, and in a cutout nodata that
  subsequent runs skipped); a URL in the response still wins, an HTML page
  without OGC markers (an empty MapServer template) means a missing sheet (I-2, N1).
- **`DownloadManager.download_sheet` returns (and describes with a sidecar) the path
  returned by the provider** — like `download_hierarchy`/`download_sheets`;
  previously the manager's target path. Sequential and parallel modes share
  one "download sheet" body (`_fetch_sheet`) and one progress report
  (`downloading` only sequentially) (D10).
- **Sheet code lists expanded into hierarchies** (`--bbox`/`--geometry`)
  are downloaded sequentially, with parallelism inside each hierarchy — the
  multiplication of threads disappears (previously up to `--workers`^2 tasks to GUGiK) (A2-3).
- **`DownloadManager` with a provider that knows its vertical CRS** does not log the correction
  "5m only EVRF2007" (the vertical CRS comes from the provider); the CLI with `--resolution 5m
  --vertical-crs KRON86` creates a provider corrected by
  `create_nmt_provider` (D11).

#### Metadata cache
- **File opened lazily:** `MetadataCache()` does not create
  `.kartograf_cache.db` on construction — the file and schema are created on the
  first write (`set_*`); reads with no file are a miss,
  `stats()` returns zeros (key `db_exists`), `clear()`/`vacuum()`/`close()`
  create nothing. `kartograf cache path|stats|clear` in a directory without a database do not
  create it (`Database size: - (file not created yet)`). Opening (WAL,
  tables, migration of an old database — removal of `url_cache`) happens under the existing
  lock.
- **A corrupted cache does not block downloads:** an SQLite error on open,
  read or write (garbage instead of a database, truncated database, no permissions,
  `database is locked`) disables the cache for the rest of the instance's life — reads
  are a miss, writes are a no-op, `stats()` returns zeros and the key `error`
  (`MetadataCache.error`); one warning per instance (`logger.warning`
  or `on_disabled=`), no exception, thread-safe. The download CLI prints
  ``Warning: cache metadanych nieczytelny (<path>): <error> — praca bez
  cache; uzyj `kartograf cache clear` albo usun plik`` (stderr, also
  with `-q`; exit code according to the download result), and when another process holds the lock
  `Warning: cache metadanych zablokowany przez inny proces (...)` without advice to
  delete. `kartograf cache clear` removes the unreadable file with `-wal`/`-shm`
  (`Usunieto nieczytelny plik cache: <path>`, code 0; no permission or
  lock = `Error:`, code 1), `cache stats` prints ``Error: cache
  nieczytelny: <path> (<error>) — uzyj `kartograf cache clear` `` (code 1),
  `cache path` unchanged. Previously a sheet list ended with the failure of
  EVERY sheet (`file is not a database`, code 1).

#### Land cover, HSG, BDOT10k
- **The land cover output directory is created only when the file is written**
  (`download_to` after a successful response): `LandCoverManager()` and `kartograf
  landcover list-layers` leave no directories; BDOT10k, CORINE
  and SoilGrids do not create it before the query (a failed download, e.g.
  HTTP 404, does not leave an empty directory).
- **HSG: output directory only on write** — `kartograf soilgrids
  hsg` and `HSGCalculator.calculate_hsg_by_bbox`/`_by_godlo` create the directory
  right before writing the raster (a missing `--geometry` file or a SoilGrids error
  does not leave an empty `./data/hsg`).
- **`Bdot10kProvider.DEFAULT_TIMEOUT` = 120 s** as the default value of
  `download_by_admin_unit/godlo/bbox` (TERYT query 30 s) (N11).
- **BDOT10k GPKG assembled in a local temporary directory** and moved
  to the target by a copy alongside + `os.replace` (SMB/CIFS network shares without byte-range
  locks ended SQLite with `database is locked`); cleanup also on
  exception.
- **CORINE and SoilGrids:** bbox envelope from EPSG:2180 via
  `envelope_from_2180` (result unchanged, D19).

#### CLI
- **`Downloading <sheet_code> ...`** is printed only at the start of the download
  (`download_sheet(on_download=)`), not for `Skipped`/`Error:`;
  a single sheet code skipped as existing prints `Skipped <sheet_code> -
  already exists at ...` instead of `Downloaded to` (decided by
  `manager.last_sheet.skipped`); `Error:` is not preceded by an empty line when the progress
  bar did not start.
- **`--help` texts** describe CZ/CUZK, SW layers in BDOT10k, SoilGrids, LAZ,
  HSG, `sheet_cache`, campaigns; `--scale` in Polish with a reference to
  `docs/USAGE.md` 1.6, `--resolution` describes SM5 (5m only) vs TM33/bbox
  (2m default or 5m) (A6-13).
- Internally: one transformation error helper (`Error: ... Remedium:
  ...`, `_print_transform_error`, D6) and one sheet list header
  (`_print_sheet_list`, D15); message content unchanged.

#### Package and dependencies
- **`pyproject.toml`:** dynamic version from `kartograf.__version__`
  (the `0.6.1` vs `0.7.0-dev` mismatch removed; `dynamic = ["version"]`);
  `[tool.setuptools.packages.find] include = ["kartograf*"]` (`tests/` outside the
  distribution); description and keywords about CUZK/DMR/LAZ (A6-4, A6-5, A6-6).
- **Licence as an SPDX expression (PEP 639):** `license = "MIT"` +
  `license-files = ["LICENSE"]`, no licence classifier, real
  `authors`; build-system `setuptools>=77.0.3` (without `wheel`) — a build without
  isolation requires setuptools >= 77, distributions have `Metadata-Version:
  2.4` with `License-Expression: MIT` and LICENSE in `dist-info/licenses/`,
  upload to PyPI requires twine >= 6.x.
- **Source package (sdist) with complete tests:** `MANIFEST.in`
  (`graft tests`) adds `tests/conftest.py`, `tests/__init__.py`
  and `tests/fixtures/` — offline tests pass from an unpacked sdist
  (the wheel still has no `tests/`). Classifier `Programming Language :: Python
  :: 3.13`.

#### Code quality and gate
- **Gate:** offline tests (`pytest tests/ -m "not live"`), coverage threshold
  `fail_under` in `pyproject.toml`, `ruff check .` and `ruff format --check .`
  on the whole repo (also the `docs/research/` scripts), `mypy kartograf/ tests/`
  without errors. `.claude/` in `.gitignore` and outside ruff/mypy. `live` tests
  require a network and are not part of the gate (`pytest -m live`, only deliberately).
- **mypy without errors:** typing-only fixes, without `# type:
  ignore`/`cast`; visible effect: a missing `private_key` in the CLMS
  credentials ends with an explicit message (proxy: `None` + log, direct
  mode: `DownloadError`) instead of an error from PyJWT. `affine` in
  `ignore_missing_imports`. Removed `from __future__ import annotations`
  (Python 3.12; forward references in `core/sheet_parser.py` in quotes).
- **Offline tests:** `tests/conftest.py` fails every test that opens a
  non-loopback socket (exception: the `live` marker) and stubs the sheet index
  GetCapabilities; layer discovery tests disable the stub with the marker
  `real_wms_layers`. Fixtures from raw server responses
  (`tests/fixtures/gugik_skorowidz/`, `gugik_laz/`, `gugik_asc/`, `cuzk/`).
  Fixes have pinning tests (RED before the fix, GREEN after); `live`
  WMS PL-2000 tests check real records/CRS (N5).
- **PL cutout verified offline on real 5 m sheets:** target
  EPSG:2180 with no value discrepancies relative to the sheet containing the pixel
  centre; target EPSG:5514 consistent with an independent GDAL warp of each sheet
  (deviations at seams — `docs/ARCHITECTURE.md` 4.3).
- **Internal deduplication** (no behaviour change): `GugikWcsMixin`
  (`providers/pl/wcs.py`: `WCS_FORMATS`, `_construct_wcs_url`,
  `get_supported_formats` for NMT/NMPT and orthophoto), `validate_godlo`
  in `SkorowidzLayersMixin`, `skorowidz.coverage_hints`, shared
  `warp_to_grid` in the CZ path (D8, D13, D14). Removed the unreachable branch
  `--product laz` in area dispatch and the dead fallbacks
  `getattr(args, "vertical_crs", "KRON86")` (N5-1).

#### Documentation
- New `docs/ARCHITECTURE.md` (architecture, data contracts, `data/`
  layout) and `docs/USAGE.md` (guide: CLI and library examples, download
  result, campaigns, CLMS, known problems; 1.6 "Kiedy `--scale` jest
  niezbedne": target scale = GUGiK sheet scale, PL-1992 without the flag,
  PL-2000 usually `--scale 1:2000`). Examples without the unnecessary `--scale
  1:10000` for a PL-1992 sheet code, `kartograf download CTES96` without
  `--resolution`.
- `docs/DEVELOPMENT_STANDARDS.md` (15-17) is the main source of conventions
  (`IMPLEMENTATION_PROMPT.md` removed); `README.md` shortened to an
  introduction; `CLAUDE.md` limited to critical rules and pointers;
  ADR index solely in `docs/DECISIONS.md` (erratum 1 to ADR-009).
- Documentation consistent with behaviour: retries only for network/429/5xx,
  a sheet across the border in list mode = `Warning:` and code 0, list of timeouts,
  the `cli -> transport` edge in ARCHITECTURE 2, docstrings of
  `LandCoverManager`/`MetadataCache`/`download_pl_cutout` (N2, N4, N10,
  N13, N16). Live verification reports in `docs/research/` (CZ stage 1,
  border areas and the maritime strip, edge cases, ADR-030 campaigns).

### Removed

#### Library API, CLI and providers
- Dead CLMS/Keychain code in `providers/corine.py` (`KEYCHAIN_SERVICE`,
  `get_credentials_from_keychain`, `save_credentials_to_keychain`,
  `get_clms_credentials`) — credentials are read only by the auth
  proxy subprocess; `CorineProvider.DLR_YEARS` (A5-1).
- Hardcoded `WMS_LAYERS` and the fallback to them (also obsolete NMPT layers)
  — layers come from GetCapabilities; `GugikProvider.FORMAT_EXTENSIONS`
  and the override of `get_file_extension`, `GugikOrtoProvider.OPENDATA_URL_PATTERN`,
  the providers' `RETRY_BACKOFF_BASE` attributes, `SoilGridsProvider.TERYT_WMS_ENDPOINT`
  (table in BREAKING).
- `MetadataCache.get_url/set_url` and the `url_cache` table (removed when
  the database is opened).
- The `/token` endpoint of the auth proxy and `AuthProxyClient.get_access_token()`.
- The `GML` format (A6-2).
- Re-exports of command implementations from the `cli/commands.py` facade (BREAKING).
- The module `kartograf.providers.landcover_base` (classes in
  `kartograf.providers.base`) and old provider modules outside
  `providers/pl/`.
- Private `core.geometry._transform_bbox` (4 corners) — replaced by
  `core.bbox.transform_bbox` (K6).

#### Package and documentation
- `requirements.txt` and `requirements-dev.txt` — the only source of dependencies
  is `pyproject.toml`.
- `IMPLEMENTATION_PROMPT.md` (content in `docs/DEVELOPMENT_STANDARDS.md`).

### Fixed

#### Parsers and sheet selection
- **Sheet selection from an envelope across systems:** `SheetParser.get_bbox`,
  `Parser2000.get_bbox`, PL-1992/PL-2000 selection and the SHP/GPKG readers
  (`read_feature_bboxes`/`get_overall_bbox`/`find_sheets_for_geometry`)
  compute envelopes with one function, `core.bbox.transform_bbox` (21 points per
  edge) instead of 4 corners: an EPSG:2180 bbox across the 19°E meridian
  no longer loses the strip at the upper edge (for a 20 km bbox 6 sheets were omitted; at the
  cost of possible redundant sheets), coarse sheets across 19°E (e.g.
  `N-34`) have a correct lower edge (-468 m), an SHP/GPKG feature across 19°E
  no longer loses ~65 m in the north, `find_sheets_for_bbox(..., system="2000")`
  from a WGS84 bbox across the zone's central meridian (15/18/21/24°E) no longer loses a
  row of sheets (e.g. 16 instead of 8). 1:10000 sheets unchanged (1e-6 m).
  The same applies to the PL cutout and LAZ tile selection from a WGS84 bbox (the cutout's `min_y`
  lower by ~479 m) and to country detection under `auto`.
- **Performance:** `SheetParser.get_bbox("EPSG:2180")` builds the transformer once
  per process (200 calls: 1371 ms -> 8 ms); SHP/GPKG readers — one
  transformer per layer.
- **Whitespace around the sheet code:** `detect_system`, `path_parts`,
  `SheetIndex.sm5_sheet` and `CuzkDmrProvider.download` trim it consistently
  with the parsers; the CLI trims the positional sheet code of `download`/`parse` (`kartograf
  download " 302_5550"` no longer goes down the PL path with the misleading `Nieprawidlowe godlo
  PL-1992`).
- **`kartograf parse 6`:** a bare PL-2000 zone number (5-8) gives a notice that it
  is a zone, with the coarsest format `strefa.pas.slup` (e.g. `6.179.12`),
  also with an explicit `uklad=` in `SheetParser`; the generic sheet code error lists the formats
  of PL-1992 and PL-2000 with examples.
- **`--geometry`:** point SHP files give a degenerate bbox instead of
  `AttributeError`; GPKG without an envelope in the header reads the point from WKB (also
  Z/M and EWKB with the SRID flag), an empty geometry is skipped, an unsupported type =
  `ValidationError` instead of silently skipping the record (A1-3, A1-5).

#### CLI
- **bbox validation in the CLI:** `kartograf download --bbox` (PL, CZ, LAZ),
  `landcover download --bbox` and `soilgrids hsg --bbox` parse the bbox with a single
  `cli._parser.parse_bbox_arg` — a reversed bbox, NaN/inf or a wrong count
  of values = `Error: Invalid bbox format: <reason>. Expected: ...` on stderr
  and exit code 1 (previously a junk sheet, a download or `Error: ValueError`;
  the hint does not go to stdout) (K7b).
- **`kartograf landcover download`** with an invalid `--property`/`--depth`/
  `--stat` (SoilGrids) or `--year` (CORINE) ends with `Error: <content>`
  and exit code 1 before any network access, without `ValueError:` and the `KARTOGRAF_DEBUG` hint
  (N8).
- **`main()` has an exception barrier:** an error other than `KartografError` =
  `Error: <Type>: <message>` with the `KARTOGRAF_DEBUG=1` hint and exit code 1
  instead of a traceback (N1-1).

#### NMT PL and the GUGiK sheet index
- **The sheet index record parser** recognises `.ASC` URLs regardless of
  letter case (H1).
- **Outdated sheet index layer names** (NMT 1m/EVRF2007, orthophoto) — the hardcoded
  lists from 0.6.1 contained retired layers (e.g. `SkorowidzeNMT2023`; yearly
  orthophoto layers 2018..2023 merged into `SkorowidzeOrtofotomapyStarsze`), did not
  know the new vintages (2026), and the orthophoto got "Invalid layer(s) given
  in the LAYERS parameter"; the cause is removed (layers from GetCapabilities).

#### Cache and storage
- **`MetadataCache`:** reads under the same lock as writes (parallel
  reads could return a row of a different key, A2-1); `__del__` does not
  import and does not raise when the interpreter shuts down (`ImportError:
  sys.meta_path is None`).
- **`FileStorage.delete()`** also removes the `.meta.json` sidecar.

#### Land cover, HSG, CORINE, auth proxy
- **`Bdot10kProvider`** returns the path of the `.gpkg` file actually written
  (the sidecar no longer lands next to a non-existent file, A2-6).
- **`CLMS_CREDENTIALS` is read:** the variable is passed to the auth
  proxy subprocess (before Keychain), so CORINE GeoTIFF works also on Linux
  and Windows — previously the only source was the macOS Keychain (A4-1).
- **Auth proxy and client:** a truncated stream no longer appends a 502 response to
  the raster body (a download without `Content-Length` is framed as chunked),
  `download_file()` writes through a temporary file and checks
  `Content-Length` (was: `True` and a corrupted GeoTIFF, A4-2); proxy start
  and singleton under a lock, the subprocess handle and the stderr-draining thread as
  class state (two threads do not start two proxies, parallel CORINE does not
  mix GeoTIFF with PNG); after `kill()` the subprocess is reaped (`wait`, no
  zombie), the streamed `/download` response is closed; missing credentials
  do not start the subprocess (`AuthProxyClient.is_available()` = False outside
  macOS), port reading with a timeout, stderr drained (N4-1, A4-11, A4-13,
  A4-14).
- **SoilGrids and CORINE:** the bbox envelope via `transform_bounds()` instead of
  two corners (the requested area was ~10% too narrow); CORINE computes the
  WMS image aspect ratio from the metric envelope (the DLR 1990 branch lost 1.7x
  of vertical resolution) (A4-7).
- **HSG:** nodata pixels (`-32768`, `NaN`, the raster's nodata value) get
  0 ("brak danych"), not group B (A4-5); `soilgrids hsg --stats` computes
  area geodetically for EPSG:4326 rasters (was `0.00 ha`, A4-6).

## [0.6.1] - 2026-03-24

### Fixed
- **NMT 5m: fixed WMS layer names**
  - `WMS_LAYERS["5m"]["EVRF2007"]`: `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`
  - Removed the non-existent layer `SkorowidzeNMT2021iStarsze`
  - Added the missing layer `SkorowidzeNMT2025`
  - The wrong names caused no results when downloading NMT 5m despite the data being available

### Added
- **WMS layer validation via GetCapabilities**
  - `_fetch_wms_layers()` — fetches the list of available layers from WMS GetCapabilities
  - `_get_validated_layers()` — compares hardcoded layers with the live WMS, auto-updates on mismatch
  - Lazy validation: only on the first call of `_get_opendata_url()`
  - Graceful fallback: if GetCapabilities is unavailable, uses the hardcoded layers
  - Warning logged when a mismatch between hardcoded and live is detected
  - In-memory cache per provider instance (no lock, benign duplicate OK)
  - Separate 10s timeout for GetCapabilities
  - Works for GugikProvider (NMT) and GugikNmptProvider (NMPT) through inheritance
  - GugikOrtoProvider not supported (different inheritance hierarchy)

### Tests
- **1007 tests** (+17 new)
  - New `tests/test_wms_layer_validation.py` — 17 tests for WMS layer validation

---

## [0.6.0] - 2026-03-03

### Added
- **Parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — configurable thread pool for hierarchy downloads
  - `DownloadResult` dataclass — structured results with succeeded/failed/skipped tracking
  - `_download_hierarchy_parallel()` — concurrent sheet downloads with progress callbacks
  - `LandCoverManager.download_batch()` — parallel batch download for land cover data
  - CLI: `--workers`/`-w` flag on `kartograf download` (default: 4)
  - Thread-safe temp filenames in all providers (`pid_threadid.tmp` pattern)
- **SQLite metadata cache (MetadataCache)**
  - `kartograf/cache/metadata.py` — SQLite WAL mode, TTL 7 days, thread-safe writes
  - URL cache for GUGiK OpenData lookups (NMT, NMPT, Orto)
  - TERYT cache for BDOT10k point-to-TERYT resolution
  - `prune_expired()` — automatic cleanup of stale entries
  - Integrated with GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
  - CLI: `kartograf cache stats|clear|path`
- **PL-2000 BBox verification tests**
  - 67 new tests: reference values, hierarchy consistency, live WMS, edge cases
  - `@pytest.mark.live` marker for GUGiK WMS integration tests
- **Public API: export of MetadataCache and DownloadResult**
  - `from kartograf import MetadataCache, DownloadResult`

### Tests
- **990 tests** (+155 new)

---

## [0.5.0] - 2026-03-02

### Added
- **PL-2000 sheet naming system — full support**
  - `Parser2000` class for parsing PL-2000 sheet codes (format `zone.row.column[.subdivisions]`)
  - 5 scales: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
  - 4 meridian zones: 5 (EPSG:2176), 6 (EPSG:2177), 7 (EPSG:2178), 8 (EPSG:2179)
  - BBox calculation with CRS transformation (pyproj)
  - Hierarchy: get_parent(), get_children(), get_all_descendants(), get_hierarchy_up()
  - `find_sheets_2000_for_bbox()` — BBox to PL-2000 sheet code lookup
- **SheetParser auto-detection of PL-1992 vs PL-2000**
  - `SheetParser("6.179.12")` automatically recognises PL-2000
  - `SheetParser("N-34-130-D")` automatically recognises PL-1992
  - Validation of system/format consistency
- **find_sheets_for_bbox: parameter system="1992"|"2000"**
  - `find_sheets_for_bbox(bbox, system="2000")` returns PL-2000 sheet codes
  - `find_sheets_for_geometry()` also supports the system parameter
- **CLI: full PL-2000 support**
  - `kartograf parse 6.179.12.20` — auto-detection, displays the zone and CRS
  - `kartograf download --bbox ... --system 2000` — download with PL-2000 sheet codes
  - `--bbox-crs` extended to EPSG:2176-2179
- **FileStorage: support for PL-2000 paths**
  - Directory layout: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`
    (note 2026-08-22: the `nmt_2000_1m` subdirectory was not implemented —
    PL-2000 sheets landed in `nmt_<res>/` next to PL-1992, see ADR-017
    and the `FileStorage` docstring; separating the directories was postponed.
    **Completed in 0.7.0** — ADR-026 gave PL-2000 its own segments
    `nmt/pl_2000_<res>_<vcrs>/`; see Breaking Changes 0.7.0)
- **Public API: export of Parser2000 and find_sheets_2000_for_bbox**
  - `from kartograf import Parser2000, find_sheets_2000_for_bbox`

### Removed
- **BDOT10k: removed filtering by category (--category pt/hydro)**
  - The whole BDOT10k file is downloaded without splitting into categories
  - Removed the constants `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Removed the `category` parameter from `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - Removed the CLI argument `--category`
  - `_extract_gpkg_from_zip()` extracts and merges all GPKG layers from the ZIP
  - `get_available_layers()` returns all 15 layers (PT* + SW*)

### Fixed
- **download_sheet(): PL-2000 sub-10k sheet codes downloaded directly**
  - PL-2000 sheet codes at scales 1:5000, 1:2000, 1:1000, 1:500 are now downloaded
    as single files, without attempting to expand to 1:10000
- **CLI: dynamic scale labels**
  - `format_hierarchy()` — header "from current to X" instead of hardcoded "1:1000000"
  - `format_children()` — "finest scale X" instead of hardcoded "1:10000"

### Tests
- **835 tests** (+199 new; 849 during development — 14 `--category`
  tests were removed in the same version together with the flag, ADR-016)

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → sheet code lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`

### Tests
- **636 tests** (+62 new)
  - 31 tests in `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 CLI geometry tests: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 tests in `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (digital surface model)**
  - `GugikNmptProvider` — inherits from GugikProvider, overrides the NMPT endpoints
  - Only 1m resolution, vertical CRS: KRON86 or EVRF2007
  - Download: sheet code → OpenData ASC, bbox → WCS GeoTIFF
- **Orthophoto (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — a separate class, TIF format
  - No vertical CRS (2D RGB), 9 WMS layers (2018-2025+older)
  - Download: sheet code → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — product selection in the download command**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — downloads NMPT
  - `kartograf download --bbox ... --product orto` — downloads an orthophoto
  - Default: nmt (unchanged)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → sheet codes**
  - Hierarchical clipping algorithm (mathematical, no WFS)
  - Supports EPSG:2180 and EPSG:4326
  - Any target scale (1:1M to 1:10k)
  - Optimised 1:200k search (12x12 grid)
- **CLI `kartograf download --bbox` — downloading NMT for a bbox**
  - `--bbox min_x,min_y,max_x,max_y` — bbox coordinates
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — bbox CRS (default EPSG:2180)
  - `godlo` becomes optional (godlo XOR --bbox)
  - Automatic sheet detection and downloading in a loop
- **Automatic expansion of sheet codes to 1:10000 in `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatically downloads 4 sheets of 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → downloads 16 sheets of 1:10000
  - For 1:10000 sheet codes the behaviour is unchanged (a single file)
  - New parameter `on_progress` — progress callback when expanding the hierarchy
  - Return type: `Path` (1:10000) or `list[Path]` (coarser scales)
  - CLI adapted — displays the number of downloaded files when expanding

### Tests
- **574 tests, coverage 83.95% (target of 80% reached)**
  - New `tests/test_gugik_nmpt.py` — 21 tests for GugikNmptProvider
  - New `tests/test_gugik_orto.py` — 25 tests for GugikOrtoProvider
  - New `tests/test_auth_client.py` — 30 tests for AuthProxyClient
  - New `tests/test_auth_proxy.py` — 24 tests for CLMSCredentials, ProxyHandler
  - Extended `tests/test_cli.py` — +12 tests (product CLI), +11 tests (landcover/soilgrids CLI)
  - Extended `tests/test_storage.py` — +8 tests (product storage)
  - Extended `tests/test_download_manager.py` — +3 tests (default_ext)
  - Extended `tests/test_landcover.py` — +38 tests
  - Extended `tests/test_hsg.py` — +6 tests

### Fixed
- Improved the error message when there is no NMT 5m coverage — instead of the technical "No ASC file found in any WMS layer" it shows a readable notice that GUGiK has no coverage for the given area

### Changed
- **FileStorage: subdirectories `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - New `product` parameter in FileStorage (e.g. product="nmpt", product="orto")
  - Structure: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamic file extension**
  - `_default_ext` is taken from `provider.default_extension` instead of hardcoded `.asc`
- **BaseProvider: new property `default_extension`** (default `.asc`)
- Migration from black + flake8 to ruff (pyproject.toml)
- Removal of .flake8, addition of .editorconfig
- Standardisation of documentation according to shared/standards
- Rewrite of CLAUDE.md (7 sections, approx. 148 lines)
- Rewrite of PROGRESS.md (4 sections, condensed from 785 lines)
- Expansion of DEVELOPMENT_STANDARDS.md (722 lines, 15 sections according to shared/standards)
- Expansion of IMPLEMENTATION_PROMPT.md (284 lines, 11 sections, current v0.3.2 context)
- Update of README.md, PRD.md, SCOPE.md
- Automatic code fixes by `ruff check --fix` (63 fixes: imports, type annotations)

### Added
- ruff configuration (linter + formatter) in pyproject.toml
- File .editorconfig
- Section [project.optional-dependencies] dev in pyproject.toml
- docs/DECISIONS.md — register of 9 architectural decisions (ADR)

### Removed
- File .flake8 (configuration covered by ruff)
- Section [tool.black] from pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Default vertical CRS changed to EVRF2007**
  - `GugikProvider`: default `vertical_crs` changed from `"KRON86"` to `"EVRF2007"`
  - `DownloadManager`: default `vertical_crs` changed from `"KRON86"` to `"EVRF2007"`
  - CLI: `--vertical-crs` defaults to `EVRF2007`
  - Kronstadt 86 (KRON86) is obsolete and available as a legacy option

- **New directory layout with resolution**
  - `FileStorage`: new `resolution` parameter (default `"1m"`)
  - NMT files are now separated by resolution:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # for 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # for 5m
    ```
  - `DownloadManager` automatically passes `resolution` to `FileStorage`
  - Default file extension changed from `.tif` to `.asc`

### Breaking Changes

- **Directory layout** - NMT files are now saved in the `1m/` or `5m/` subdirectory
  - Old path: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - New path: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Default vertical_crs** - changed from `KRON86` to `EVRF2007`
  - To use the old CRS: `--vertical-crs KRON86`

**Usage examples:**
```bash
# Download NMT 1m (EVRF2007 by default)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Download NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Use the old Kronstadt (legacy) vertical CRS
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **NMT resolution selection** - Support for NMT data in two resolutions
  - `1m` (GRID1) - high resolution, default
  - `5m` (GRID5) - lower resolution, EVRF2007 only

- **GugikProvider** - New `resolution` parameter
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - New WMS endpoints for 5m: `SheetsGrid5mEVRF2007`
  - Automatic validation: 5m requires EVRF2007
  - New methods: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` raises ValueError for 5m (WCS unavailable)

- **DownloadManager** - New `resolution` parameter
  - `DownloadManager(resolution="5m")` - automatically forces EVRF2007

- **CLI** - New option `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Shortcut: `-r 5m`

**5m limitations:**
- Available only in the EVRF2007 vertical CRS
- No WCS support (download_bbox) - OpenData sheets only

**Usage examples:**
```bash
# Download NMT 1m (default)
kartograf download N-34-130-D-d-2-4

# Download NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Download the hierarchy at 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Tests** - 365 tests (18 new for resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Added missing exports in the main module
  - Added `SoilGridsProvider` to `kartograf/__init__.py`
  - Added `HSGCalculator` to `kartograf/__init__.py`
  - It is now possible to import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Version synchronisation** - Unified the version across all files
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: updated status and test count

- **Dependency synchronisation** - Added missing dependencies
  - `pyproject.toml`: added `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: added `PyJWT[crypto]>=2.8.0`

- **Tests** - Fixed the version test in `test_integration.py`

- **Documentation** - Added a QA Review section to `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids and Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider for ISRIC SoilGrids (soil data)
  - Global soil data at 250m resolution
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 soil parameters:**
    - `bdod` - Bulk density (kg/dm³)
    - `cec` - Cation exchange capacity (cmol/kg)
    - `cfvo` - Coarse fragments (%)
    - `clay` - Clay content (%)
    - `nitrogen` - Total nitrogen (g/kg)
    - `ocd` - Organic carbon density (kg/m³)
    - `ocs` - Organic carbon stock (t/ha)
    - `phh2o` - pH in H2O
    - `sand` - Sand content (%)
    - `silt` - Silt content (%)
    - `soc` - Organic carbon (g/kg)
  - **6 depths:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statistics:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - CRS transformation: EPSG:2180 → WGS84

- **HSGCalculator** - Hydrologic Soil Groups calculation for the SCS-CN method
  - `kartograf/hydrology/hsg.py` - hydrology module
  - Soil texture classification according to the USDA triangle (12 classes)
  - Mapping of texture to HSG (A, B, C, D)
  - **Hydrologic groups:**
    - A - high infiltration (sand, loamy sand)
    - B - moderate infiltration (sandy loam, loam)
    - C - slow infiltration (clay loam)
    - D - very slow infiltration (clay)
  - Automatic download of clay/sand/silt from SoilGrids
  - Coverage statistics for each HSG group

- **CLI soilgrids** - New CLI commands
  - `kartograf landcover download --source soilgrids --property <param> --depth <depth>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <sheet_code>` - HSG calculation
  - HSG options: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Usage examples:**
```bash
# Download organic carbon
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Download clay content
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Calculate HSG for the SCS-CN method
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover

- **LandCoverProvider** - New abstraction for land cover data providers
  - Methods: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Common interface for different data sources

- **Bdot10kProvider** - Provider for BDOT10k (GUGiK)
  - Downloading county packages by TERYT
  - Downloading via WMS GetFeatureInfo for the package URL
  - Downloading by sheet code (converted to bbox)
  - **12 land cover layers (PT*):**
    - PTGN - Unused land
    - PTKM - Transport areas
    - PTLZ - Forest areas
    - PTNZ - Undeveloped areas
    - PTPL - Squares
    - PTRK - Shrub vegetation
    - PTSO - Storage sites
    - PTTR - Agricultural areas
    - PTUT - Permanent crops
    - PTWP - Surface waters
    - PTWZ - Wetland areas
    - PTZB - Built-up areas
  - Automatic merging of PT* layers from ZIP into one GeoPackage
  - Output format: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider for CORINE Land Cover (Copernicus)
  - European land cover classification (44 classes)
  - Available years: 1990, 2000, 2006, 2012, 2018
  - **Three data sources (in priority order):**
    1. **CLMS API** - GeoTIFF with class codes (requires OAuth2)
    2. **EEA Discomap WMS** - PNG preview (years 2000-2018)
    3. **DLR WMS** - Fallback for 1990
  - OAuth2 RSA authentication for the CLMS API
  - Storing credentials in the macOS Keychain (service: `clms-token`)

- **LandCoverManager** - Management of land cover data downloads
  - Dispatch to the appropriate provider
  - Support for multiple area selection methods

- **CLI landcover** - New CLI commands
  - `kartograf landcover download --source bdot10k --teryt <code>`
  - `kartograf landcover download --source corine --year <year> --godlo <sheet_code>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider uses an **Auth Proxy** for secure CLMS API authentication:

**Security architecture:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (RSA private key) are isolated in a separate process
- The main application never sees the credentials
- Only API responses are passed to the application

**New modules:**
- `kartograf/auth/proxy.py` - HTTP server isolating credentials
- `kartograf/auth/client.py` - client that starts the proxy automatically

**Configuration:**
1. Register at https://land.copernicus.eu
2. Generate API credentials (JSON)
3. Save to the Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Operating modes:**
```python
# Default (safe) - uses proxy
provider = CorineProvider()

# Direct (for testing) - credentials visible
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Note:** If credentials are not configured, CorineProvider automatically uses WMS (PNG preview instead of GeoTIFF with class codes).

### Dependencies

- Added `PyJWT[crypto]>=2.8.0` - JWT generation for OAuth2
- Added `rasterio>=1.3.0` - GeoTIFF raster processing
- Added `numpy>=1.24.0` - array operations

### Technical Details

- 347 tests (42 for landcover, 28 for soilgrids, 34 for HSG)
- Formatting: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - New download architecture

**Simplified download logic:**
- **Sheet code → OpenData (ASC)** - downloading a sheet by sheet code always yields an ASC file
- **BBox → WCS (GeoTIFF)** - downloading by bounding box yields GeoTIFF/PNG/JPEG

**API changes:**
- `download_sheet(godlo)` - always downloads ASC (the `format` parameter was removed)
- `download_hierarchy(godlo, target_scale)` - downloads all sheets as ASC
- `download_bbox(bbox, filename, format)` - **new method** for downloading by bbox
- Removed `construct_url()` from the public API
- `DownloadManager` no longer accepts the `format` parameter in the constructor

### Added

- **ASC download via OpenData** - Automatic URL lookup by WMS GetFeatureInfo
  - Queries to layers: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Download from `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Calculating the sheet bounding box
  - Supported CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Coordinate transformation through `pyproj`

- **BBox** - New data type in the public API

- **GugikProvider.download_bbox()** - Downloading by bounding box from WCS

### Dependencies

- Added `pyproj>=3.6.0` to requirements

### Technical Details

- 245 tests

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <sheet_code>` - Display sheet information
  - `kartograf parse <sheet_code> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <sheet_code> --children` - Show direct children
  - `kartograf download <sheet_code>` - Download single sheet
  - `kartograf download <sheet_code> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[Unreleased]: https://github.com/Daldek/Kartograf/compare/v0.7.2...HEAD
[0.7.2]: https://github.com/Daldek/Kartograf/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/Daldek/Kartograf/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/Daldek/Kartograf/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Daldek/Kartograf/compare/4cec5d87b9aad1ffdb59693ec7163c7c97540983...v0.6.1
[0.6.0]: https://github.com/Daldek/Kartograf/compare/v0.5.0...4cec5d87b9aad1ffdb59693ec7163c7c97540983
[0.5.0]: https://github.com/Daldek/Kartograf/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/402d8091dc02dfacb77619950fc06504bea6d7ec...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/compare/v0.3.1...402d8091dc02dfacb77619950fc06504bea6d7ec
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
