# Kartograf - guide for agents

> Generated from the command catalog: `kartograf commands guide --format agents`. Do not edit it by hand.

## Purpose and scope

Kartograf downloads official spatial data of Poland (GUGiK) and Czechia (CUZK), with Copernicus (CORINE land cover) and ISRIC (SoilGrids soils): digital elevation models (DEM, Polish NMT) and surface models (NMPT), LAZ point clouds, orthophotos, land cover (BDOT10k, CORINE), soils and hydrologic soil groups (HSG), administrative boundaries, cadastre, 3D models and more. Every file is saved as an immutable version in a store, next to a `kartograf-meta/1` sidecar with its CRS, source and licence. Interfaces: a Python library, a CLI and an MCP server, all from one command catalog.

Use it to get the data of an area (a sheet code, a bbox, a geometry file, a TERYT code or a whole country) and to read what it has already downloaded. Command groups: <!-- kartograf:group_names -->.

Not for:

- hydrological computation (curve numbers, hydrographs, flow statistics): use Hydrolog; Kartograf only classifies HSG;
- IMGW and CHMU measurement series: use IMGWTools;
- watershed delineation and analysis: use Hydrograf, which takes its elevation and land cover data from Kartograf.

## Install

Python 3.12 or newer: `pip install "kartograf @ git+https://github.com/Daldek/Kartograf.git"`. The extra `mcp` adds the MCP server: `pip install "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"`. Without the console script: `python -m kartograf ...`.

## Interfaces

- Python: <!-- kartograf:python_example --> (keyword arguments are the options). Also `kartograf.list_commands`, `kartograf.command_schema`, `kartograf.validate_command`, `kartograf.check_command` and `kartograf.run_command`. Results are documents with `to_dict()` and `to_json()`; errors raise `KartografError` subclasses (`code`, `exit_code`, `hint`, `details`).
- CLI: `kartograf <group> <command> --option value --json`, e.g. <!-- kartograf:cli_example -->. A flag is `--` and the option name with `-` for `_`. `--json` prints the result envelope as one document on stdout; logs and progress go to stderr. `--root DIR` is the store of a data command.
- MCP: `kartograf-mcp [--allow-writes] [--allow-dir DIR] [--tools FAMILIES]` (extra `mcp`). A tool is named like the `operation_id` (`kartograf_elevation_download`) and its arguments are the options. The server reads and plans by default: a data tool only plans (`check_updates` is true) until `--allow-writes` is given, and that needs `--allow-dir`. `--tools core` keeps the ten tools of the main tasks.
- Settings: `kartograf config show` prints the effective settings (`root`, `data_dir`, `cache_dir`, `lang`, `debug`) and their sources.

## Workflow rules

Discover, check, run, read: find the command with `kartograf commands list` and read its options with `kartograf commands schema --command "<name>"`; run a data command with `--check-updates` first (the plan fetches and writes nothing); run it; read `status`, `result`, `items` and `notices` of the envelope.

Rules:

<!-- kartograf:rules -->

## Result envelope

Every command answers with `kartograf-result/1`: `schema`, `tool`, `version`, `command`, `check` (true for a plan), `status`, `result`, `items` and `notices`.

- `status`: `ok`; `partial` (some units failed, exit code 10); `failed` (no unit succeeded, exit code 11). They are outcomes, not errors: the envelope is printed all the same.
- `result`: the document of the command, with its own `schema` (`kartograf-download/1`, `kartograf-plan/1`, `kartograf-availability/1`, `kartograf-sheet/1`, ...); `ok: false` in it is `partial` or `failed` above.
- `items`: one `{id, status, code?, reason?, message?}` per unit; a failed unit has the registry `code`.
- `notices`: non-fatal `{level, code, message}` entries.

## Error codes

An error is a `kartograf-error/1` document (`code`, `title`, `message`, `hint`, `details`, `exit_code`, `command`): the last line of stderr in the CLI (stdout stays empty), an `isError` result in MCP, `error_report(exc)` in Python. The code is the same everywhere. Registry: https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md

<!-- kartograf:errors -->

## Command index

One line per command: name, `operation_id`, summary. Options, allowed values, units and examples: `kartograf commands schema --command "<name>"` (MCP: `kartograf_commands_schema`).

<!-- kartograf:index -->

## Typical flows

CLI lines; in MCP call the tool of the `operation_id` with the same options as arguments (`check_updates: true` for `--check-updates`). Paths under `/data/` are examples: give your own, absolute.

<!-- kartograf:flows -->

## Things not to do

- Do not leave out `product`, `resolution` or `vertical_crs` hoping for a default: Kartograf asks, it does not guess.
- Do not point `--root` at the repository or at `/tmp`, and do not delete versions by hand (a store is hard-linked): to refresh, run with `--upgrade` or `--force`.
- Do not parse `message` or `hint`: decide by `code`, `details.option`, `details.reason` or the exit code.
- Do not repeat a call unchanged after `validation_error`, and do not treat `partial` as a failure of the whole run.
- Do not use it for hydrological computation or for measurement series (see the scope above).

Developing this repository? Read CLAUDE.md.
