# Kartograf - guide for agents

> Generated from the command catalog: `kartograf commands guide --format agents`. Do not edit it by hand.

## Purpose and scope

Kartograf downloads official spatial data of Poland (GUGiK) and Czechia (CUZK), with Copernicus (CORINE land cover) and ISRIC (SoilGrids soils): digital elevation models (DEM, Polish NMT) and surface models (NMPT), LAZ point clouds, orthophotos, land cover (BDOT10k, CORINE), soils and hydrologic soil groups (HSG), administrative boundaries, cadastre, 3D models and more. Every file is saved as an immutable version in a store, next to a `kartograf-meta/1` sidecar with its CRS, source and licence. Interfaces: a Python library, a CLI and an MCP server, all from one command catalog.

Use it to get the data of an area (a sheet code, a bbox, a geometry file, a TERYT code or a whole country) and to read what it has already downloaded. Command groups: `boundaries`, `cadastre`, `elevation`, `geodesy`, `hydro`, `imagery`, `landcover`, `maps`, `models3d`, `names`, `project`, `sheet`, `soil`, `store`, `cache`, `commands`, `config`.

Not for:

- hydrological computation (curve numbers, hydrographs, flow statistics): use Hydrolog; Kartograf only classifies HSG;
- IMGW and CHMU measurement series: use IMGWTools;
- watershed delineation and analysis: use Hydrograf, which takes its elevation and land cover data from Kartograf.

## Install

Python 3.12 or newer: `pip install "kartograf @ git+https://github.com/Daldek/Kartograf.git"`. The extra `mcp` adds the MCP server: `pip install "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"`. Without the console script: `python -m kartograf ...`.

## Interfaces

- Python: `kartograf.download_data(product="nmt", sheet="N-34-130-D-d-2-4", resolution="1m", vertical_crs="EVRF2007", root="/data/kartograf")` (keyword arguments are the options). Also `kartograf.list_commands`, `kartograf.command_schema`, `kartograf.validate_command`, `kartograf.check_command` and `kartograf.run_command`. Results are documents with `to_dict()` and `to_json()`; errors raise `KartografError` subclasses (`code`, `exit_code`, `hint`, `details`).
- CLI: `kartograf <group> <command> --option value --json`, e.g. `kartograf sheet parse N-34-130-D-d-2-4 --json`. A flag is `--` and the option name with `-` for `_`. `--json` prints the result envelope as one document on stdout; logs and progress go to stderr. `--root DIR` is the store of a data command.
- MCP: `kartograf-mcp [--allow-writes] [--allow-dir DIR] [--tools FAMILIES]` (extra `mcp`). A tool is named like the `operation_id` (`kartograf_elevation_download`) and its arguments are the options. The server reads and plans by default: a data tool only plans (`check_updates` is true) until `--allow-writes` is given, and that needs `--allow-dir`. `--tools core` keeps the ten tools of the main tasks.
- Settings: `kartograf config show` prints the effective settings (`root`, `data_dir`, `cache_dir`, `lang`, `debug`) and their sources.

## Workflow rules

Discover, check, run, read: find the command with `kartograf commands list` and read its options with `kartograf commands schema --command "<name>"`; run a data command with `--check-updates` first (the plan fetches and writes nothing); run it; read `status`, `result`, `items` and `notices` of the envelope.

Rules:

1. **Discover, do not guess:** `kartograf commands list` lists the commands and `kartograf commands schema` (option `command`) gives the options of one, with allowed values and their meanings, rules, examples and errors; in MCP use `kartograf_commands_list` and `kartograf_commands_schema`.
2. **Select the data explicitly:** `product`, `resolution`, `vertical_crs` and the area: `sheet`, `bbox` with `bbox_crs`, or `geometry`, exactly one; `country` goes with a bbox or a geometry. Nothing is guessed: a missing argument is an error with a hint.
3. **Absolute paths, outside the repository and /tmp:** `root` (CLI `--root`) is the store; a version is never overwritten, so a rerun is safe.
4. **Check, then run:** `--check-updates` (MCP: `check_updates`) plans without fetching; `--upgrade` fetches newer content, `--force` fetches again, and `--plan` runs a saved plan.
5. **Decide by codes:** `status` of the envelope (`ok`, `partial`, `failed`), `code`, `details.option` and `details.reason`, or the exit code; `partial` and `failed` (exit 10 and 11) are results: read `items` and retry only the failed units.
6. **Read `notices`:** non-fatal warnings (a skipped sheet, a mixed campaign); pass them on with the result.
7. **MCP reads and plans by default:** without `--allow-writes` a tool that writes only plans; `--allow-writes` needs `--allow-dir`, and a path outside it is `forbidden`.

## Result envelope

Every command answers with `kartograf-result/1`: `schema`, `tool`, `version`, `command`, `check` (true for a plan), `status`, `result`, `items` and `notices`.

- `status`: `ok`; `partial` (some units failed, exit code 10); `failed` (no unit succeeded, exit code 11). They are outcomes, not errors: the envelope is printed all the same.
- `result`: the document of the command, with its own `schema` (`kartograf-download/1`, `kartograf-plan/1`, `kartograf-availability/1`, `kartograf-sheet/1`, ...); `ok: false` in it is `partial` or `failed` above.
- `items`: one `{id, status, code?, reason?, message?}` per unit; a failed unit has the registry `code`.
- `notices`: non-fatal `{level, code, message}` entries.

## Error codes

An error is a `kartograf-error/1` document (`code`, `title`, `message`, `hint`, `details`, `exit_code`, `command`): the last line of stderr in the CLI (stdout stays empty), an `isError` result in MCP, `error_report(exc)` in Python. The code is the same everywhere. Registry: https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md

| Code | Exit | What to do |
|---|---|---|
| `internal_error` | 1 | bug in Kartograf: report the command, options and version |
| `validation_error` | 2 | wrong or missing option: fix `details.option` as `hint` says |
| `source_unavailable` | 5 | network, HTTP or timeout: wait and retry the same call |
| `no_data` | 14 | the source has no data there (`details.reason`): change area or year |
| `store_unavailable` | 8 | the metadata cache is locked or unreadable: retry or `--no-cache` |
| `data_error` | 7 | a sidecar is unreadable or of another schema: see `details.path` |
| `missing_dependency` | 6 | an extra is missing: install it as `hint` says |
| `forbidden` | 12 | MCP refused: a path outside `--allow-dir` or a write without `--allow-writes` |
| `calculation_error` | 13 | a coordinate transformation failed: change the CRS or area |
| `unsupported` | 15 | no safe transformation for these coordinate systems: use another |
| `io_error` | 9 | a directory or file is unavailable: check `details.path` |
| `cancelled` | 130 | interrupted (Ctrl+C): nothing half written, run again |
| `terminated` | 143 | ended by SIGTERM: nothing half written, run again |

## Command index

One line per command: name, `operation_id`, summary. Options, allowed values, units and examples: `kartograf commands schema --command "<name>"` (MCP: `kartograf_commands_schema`).

- `elevation download` (`kartograf_elevation_download`): Download NMT, NMPT, LAZ or contours as sheets, tiles or one WCS cutout
- `elevation list-sources` (`kartograf_elevation_list_sources`): List the registered data sources of the elevation group (offline)
- `elevation availability` (`kartograf_elevation_availability`): Report the years, grids, CRSs and formats of NMT, NMPT or LAZ for an area
- `imagery download` (`kartograf_imagery_download`): Download orthophotos and other images as sheets or one WCS cutout
- `imagery list-sources` (`kartograf_imagery_list_sources`): List the registered data sources of the imagery group (offline)
- `landcover download` (`kartograf_landcover_download`): Download land cover: BDOT10k, BDOO, CORINE, ZABAGED, Data50 or Data250
- `landcover list-sources` (`kartograf_landcover_list_sources`): List the registered data sources of the landcover group (offline)
- `landcover list-layers` (`kartograf_landcover_list_layers`): List the layers, classes or years of a land-cover product (offline)
- `soil download` (`kartograf_soil_download`): Download one SoilGrids layer (property, depth, statistic) for an area
- `soil hsg` (`kartograf_soil_hsg`): Compute hydrologic soil groups (HSG) from SoilGrids texture for an area
- `soil list-sources` (`kartograf_soil_list_sources`): List the registered data sources of the soil group (offline)
- `soil list-layers` (`kartograf_soil_list_layers`): List the SoilGrids properties, depths and statistics (offline)
- `boundaries download` (`kartograf_boundaries_download`): Download boundaries or addresses: a unit package, a national file or area objects
- `boundaries list-sources` (`kartograf_boundaries_list_sources`): List the registered data sources of the boundaries group (offline)
- `cadastre download` (`kartograf_cadastre_download`): Download cadastral data: an EGiB or RCN export, or the data of an area
- `cadastre list-sources` (`kartograf_cadastre_list_sources`): List the registered data sources of the cadastre group (offline)
- `models3d download` (`kartograf_models3d_download`): Download 3D models: building and tree county packages or city mesh tiles (PL)
- `models3d list-sources` (`kartograf_models3d_list_sources`): List the registered data sources of the models3d group (offline)
- `hydro download` (`kartograf_hydro_download`): Download the CZ water network (HY-NET) for an area or the national file
- `hydro list-sources` (`kartograf_hydro_list_sources`): List the registered data sources of the hydro group (offline)
- `names download` (`kartograf_names_download`): Download geographic names of an area or the national files (PL, CZ, world)
- `names list-sources` (`kartograf_names_list_sources`): List the registered data sources of the names group (offline)
- `maps download` (`kartograf_maps_download`): Download topographic map sheets: BDOT10k visualisations (PL), ZTM (CZ)
- `maps list-sources` (`kartograf_maps_list_sources`): List the registered data sources of the maps group (offline)
- `geodesy download` (`kartograf_geodesy_download`): Download control points, county packages, sheet archives or a quasi-geoid
- `geodesy list-sources` (`kartograf_geodesy_list_sources`): List the registered data sources of the geodesy group (offline)
- `project init` (`kartograf_project_init`): Create a project manifest and its store
- `project add` (`kartograf_project_add`): Add a task for a data command to the project without downloading
- `project remove` (`kartograf_project_remove`): Remove a task and its pins from the manifest, keeping the files
- `project download` (`kartograf_project_download`): Fetch, restore or update the tasks of a project and pin their files
- `project status` (`kartograf_project_status`): Check offline that the pinned files of the tasks exist with the pinned size
- `project verify` (`kartograf_project_verify`): Verify the SHA-256 and the sidecars of the pinned files of the tasks
- `sheet parse` (`kartograf_sheet_parse`): Recognise a PL or CZ sheet code and show its properties
- `commands list` (`kartograf_commands_list`): List the commands with their groups, products and MCP families
- `commands schema` (`kartograf_commands_schema`): Describe one command: its options, result, effects, rules and examples
- `commands guide` (no MCP tool): Render the guide for AI agents (AGENTS.md, llms.txt or its block)
- `cache stats` (no MCP tool): Show the statistics of the metadata cache
- `cache clear` (no MCP tool): Delete every entry of the metadata cache
- `cache path` (no MCP tool): Show the path of the metadata cache file
- `sheet find` (`kartograf_sheet_find`): List the PL sheet codes that cover an area
- `store overview` (`kartograf_store_overview`): List the segments of a store
- `store entries` (`kartograf_store_entries`): List the entries of one store segment: version files with their sidecars
- `store sidecar` (`kartograf_store_sidecar`): Read the sidecar of one store file (kartograf-meta/1)
- `config show` (no MCP tool): Show the settings in force: the value and source of every key

## Typical flows

CLI lines; in MCP call the tool of the `operation_id` with the same options as arguments (`check_updates: true` for `--check-updates`). Paths under `/data/` are examples: give your own, absolute.

### 1. The elevation model (NMT) of a sheet

A sheet code (PL-1992 or PL-2000, CZ SM5, TM33 or ZTM) is the shortest way to name an area.

1. `kartograf sheet parse N-34-130-D-d-2-4 --json` - properties of the sheet, no network.
2. `kartograf elevation availability --product nmt --sheet N-34-130-D-d-2-4 --json` - what the area has (years, grids, vertical CRSs); nothing is fetched.
3. `kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --root /data/kartograf --check-updates --json` - the plan (`kartograf-plan/1`): what a run would fetch; nothing is written.
4. `kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --root /data/kartograf --json` - the run: `kartograf-download/1`, `files[].path` of the versions written below the store.

### 2. An area given as a bounding box, and the point cloud

A bbox needs its CRS (`--bbox-crs`, default EPSG:2180) and a country; an area gets one request per sheet.

1. `kartograf elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --root /data/kartograf --json` - the elevation model of the sheets that cover the area.
2. `kartograf elevation download --product laz --country pl --bbox 530000,382000,533000,386000 --vertical-crs KRON86 --root /data/kartograf --json` - LAZ point clouds of the area.

### 3. Land cover, soils and hydrologic soil groups (HSG)

Sources and layers (offline): `kartograf landcover list-layers --product bdot10k`, `kartograf soil list-sources`.

1. `kartograf landcover download --product bdot10k --teryt 1465 --root /data/kartograf --json` - BDOT10k of a county (TERYT code).
2. `kartograf soil download --property clay --depth 0-5cm --stat mean --bbox 626000,480000,628000,482000 --root /data/kartograf --json` - a SoilGrids layer for an area.
3. `kartograf soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 --root /data/kartograf --summary --json` - the HSG raster from the texture layers, with the share of each group in `result.summary`.

### 4. A project: tasks with pinned versions

Run the lines in the directory of the project; `--json` goes before the name of the task.

1. `kartograf project init --root /data/kartograf --json` - the project and its store.
2. `kartograf project add --json area elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007` - a task: a data command with its options.
3. `kartograf project download --json` - fetch and pin the versions.
4. `kartograf project status --json` - is everything there? `status` reads sizes, `verify` the checksums.

## Things not to do

- Do not leave out `product`, `resolution` or `vertical_crs` hoping for a default: Kartograf asks, it does not guess.
- Do not point `--root` at the repository or at `/tmp`, and do not delete versions by hand (a store is hard-linked): to refresh, run with `--upgrade` or `--force`.
- Do not parse `message` or `hint`: decide by `code`, `details.option`, `details.reason` or the exit code.
- Do not repeat a call unchanged after `validation_error`, and do not treat `partial` as a failure of the whole run.
- Do not use it for hydrological computation or for measurement series (see the scope above).

Developing this repository? Read CLAUDE.md.
