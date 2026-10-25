# Kartograf: official spatial data of Poland and Czechia for GIS and hydrology

Kartograf downloads spatial data: digital elevation models (DEM, Polish NMT), surface models (NMPT), orthophotos and LAZ point clouds from GUGiK (Poland) and CUZK (Czechia), BDOT10k and CORINE land cover, SoilGrids soils with hydrologic soil groups (HSG), boundaries, cadastre and 3D models. Every file is saved as an immutable version with metadata. CLI, Python library and MCP server.

## When to use

- Get the data of an area (a sheet code, a bounding box, a vector file, a TERYT county code or a whole country) from the official source, with its CRS, licence and origin recorded next to every file.
- Keep a reproducible data set: versions are never overwritten, and a project manifest pins them by SHA-256.
- Let an AI agent discover and call the same operations through MCP, the CLI or Python, with one result format and stable error codes.

## When not to use

- Hydrological computation (concentration time, SCS-CN, hydrographs, statistics): [Hydrolog](https://github.com/Daldek/Hydrolog). Kartograf only classifies HSG.
- IMGW-PIB and CHMU measurement series, PMAXTP: [IMGWTools](https://github.com/Daldek/IMGWTools).
- Watershed delineation and design hydrographs in a web application: [Hydrograf](https://github.com/Daldek/Hydrograf), which takes its elevation and land cover data from Kartograf.
- Browsing and managing a store in a browser: [Archiwista](https://github.com/Daldek/Archiwista).
- Areas outside Poland and Czechia: use the provider of that country. The only global source is SoilGrids.

## Install

Kartograf is not on PyPI yet; install it from Git (Python 3.12 or newer):

```bash
uv tool install "kartograf @ git+https://github.com/Daldek/Kartograf.git"
uv add "kartograf @ git+https://github.com/Daldek/Kartograf.git"
uvx --from "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git" kartograf-mcp
```

The lines install the CLI, add the library to a project and start the MCP server once.

| Extra | Adds |
|---|---|
| `mcp` | the MCP server `kartograf-mcp` (SDK `mcp>=2.3.0,<3`, protocol revision 2026-07-28) |

Development setup: `git clone https://github.com/Daldek/Kartograf.git && cd Kartograf && uv sync --locked --all-extras`.

## Quick start

Every command takes `--json`: stdout is then exactly one `kartograf-result/1` document, logs go to stderr. Without it the output is for people, in the language of `--lang` (`pl` or `en`).

### CLI

```bash
kartograf sheet parse N-34-139-C-a-3-1 --json
```

Offline. The envelope names the command and holds the document of the command:

```json
{
  "schema": "kartograf-result/1",
  "tool": "kartograf",
  "command": "sheet parse",
  "check": false,
  "status": "ok",
  "result": {
    "schema": "kartograf-sheet/1",
    "sheet": "N-34-139-C-a-3-1",
    "system": "pl1992",
    "country": "PL",
    "scale": "1:10000",
    "crs": "EPSG:2180"
  },
  "items": [],
  "notices": []
}
```

Plan a download, then run it (network). `--check` writes nothing:

```bash
kartograf elevation download --product nmt --sheet N-34-139-C-a-3-1 --resolution 1m --vertical-crs EVRF2007 --root ~/kartograf-data --check --json
kartograf elevation download --product nmt --sheet N-34-139-C-a-3-1 --resolution 1m --vertical-crs EVRF2007 --root ~/kartograf-data --json
```

The plan is `"check": true` with `result.schema` `kartograf-plan/1` and one item per file (`status` `missing`, `newer`, `current`, `unverifiable` or `check_failed`). The run has `result.schema` `kartograf-download/1`:

```json
{
  "schema": "kartograf-result/1",
  "command": "elevation download",
  "check": false,
  "status": "ok",
  "result": {
    "schema": "kartograf-download/1",
    "files": [{"unit": "N-34-139-C-a-3-1", "country": "PL", "status": "new"}],
    "failed": [],
    "ok": true
  }
}
```

`result.files[].path` is the file below the store, listed with its `size_bytes` and `sha256`. An area, a country or another product is another option set: `kartograf commands schema --command "elevation download"`.

### Python

```python
from kartograf import describe_sheet

info = describe_sheet("N-34-139-C-a-3-1")
print(info.scale, info.crs)  # 1:10000 EPSG:2180
```

Offline. Documents have `to_dict()` and `to_json()`; the dictionary is the `result` of the CLI envelope. A download is one call with the same options as keyword arguments (network):

```python
from pathlib import Path

from kartograf import check_data, download_data

choice = {
    "product": "nmt",
    "sheet": "N-34-139-C-a-3-1",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
    "root": Path.home() / "kartograf-data",
}
plan = check_data(**choice)  # reads the source, writes nothing
report = download_data(**choice)
print(report.ok, [item.file.path for item in report.files])
```

Failures raise `KartografError` subclasses with `code`, `exit_code`, `hint` and `details`.

### MCP

The server lists the tools of the catalog. A tool is called with the options as arguments and answers with the same envelope as `--json`, as `structuredContent` and as text:

```json
{"name": "kartograf_sheet_parse", "arguments": {"sheet": "N-34-139-C-a-3-1"}}
```

## Capabilities

The CLI group is `kartograf <group> download` and `product` selects the data; `kartograf <group> list-sources` lists the sources and values of a group offline. The MCP tool is `kartograf_<group>_download`. Every row reads from the source named in the last column and writes a store version with its licence.

| Task | CLI group (`--product`) | Python function | Data source and licence |
|---|---|---|---|
| DEM (NMT), surface model (NMPT), LAZ point clouds, ZABAGED contours | `elevation` (`nmt`, `nmpt`, `laz`, `contours`) | `download_data` | GUGiK (PL): free reuse with attribution; CUZK (CZ): CC BY 4.0 |
| Availability of years, grids and formats of an area, without downloading | `elevation availability` | `check_availability` | GUGiK, CUZK |
| Orthophoto, LIDAR intensity, true and oblique orthophoto | `imagery` (`orto`, `intensity`, `true-orto`, `oblique-orto`) | `download_data` | GUGiK, CUZK |
| Land cover: BDOT10k (also yearly archives), BDOO, CORINE, ZABAGED, Data50, Data250 | `landcover` | `download_landcover` | GUGiK, CUZK; CORINE: Copernicus CLMS data policy, attribution required |
| SoilGrids layers and hydrologic soil groups (HSG, SCS-CN) | `soil` (`download`, `hsg`) | `download_soil`, `calculate_hsg` | ISRIC SoilGrids: CC BY 4.0 |
| Boundaries (PRG, RUIAN), addresses, geomorphology | `boundaries` | `download_collection` | GUGiK, CUZK |
| Cadastral map (EGiB, RCN prices; CZ cadastral map) | `cadastre` | `download_collection` | GUGiK, CUZK |
| 3D building and tree models, city meshes (PL) | `models3d` | `download_collection` | GUGiK |
| Water network HY-NET (CZ) | `hydro` | `download_collection` | CUZK |
| Geographic names (PRNG, Geonames, world) | `names` | `download_collection` | GUGiK, CUZK |
| Topographic maps (BDOT10k visualisations, ZTM) | `maps` | `download_collection` | GUGiK, CUZK |
| Geodetic control networks, quasi-geoid models | `geodesy` | `download_collection` | GUGiK, CUZK |
| Pinned versions: manifest, status, verification | `project` (`init`, `add`, `download`, `status`, `verify`) | `init_project`, `download_project`, `verify_project` | the sources of its tasks |
| Sheet codes: parse one, find the sheets of an area | `sheet parse`, `sheet find` | `describe_sheet`, `find_sheets` | none (offline) |
| Read a store without writing | `store overview`, `store entries`, `store sidecar` | `describe_store`, `list_store_entries`, `read_store_sidecar` | none (offline) |

The full list is `kartograf commands list --json`. Python names are keyword-only functions of the top-level package (`kartograf.__all__`).

## For AI agents

- [llms.txt](https://raw.githubusercontent.com/Daldek/Kartograf/main/llms.txt) and [AGENTS.md](https://raw.githubusercontent.com/Daldek/Kartograf/main/AGENTS.md) are generated from the command catalog; `kartograf commands guide --format agents|llms|agents-md-block` prints them and `--inject PATH` puts the block into the AGENTS.md of another repository.
- Discover the commands with `kartograf commands list --json` and one command with `kartograf commands schema --command "elevation download" --json` (options, allowed values with meanings, rules, examples, errors). In Python: `list_commands()`, `command_schema()`, `validate_command()`, `check_command()`, `run_command()`; in MCP: `kartograf_commands_list` and `kartograf_commands_schema`.
- Every command answers with `kartograf-result/1` (`status` `ok`, `partial` or `failed`, `result`, `items`, `notices`); an error is `kartograf-error/1` on the last line of stderr.
- Read-only operations come first: `--check` plans without fetching or writing, a version is never overwritten, and the MCP server only plans until it is started with `--allow-writes`.

## MCP server

`kartograf-mcp` serves 40 tools named `kartograf_<group>_<verb>` over stdio. Each client below starts it as in the Install section:

```bash
claude mcp add kartograf -- uvx --from "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git" kartograf-mcp
codex mcp add kartograf -- uvx --from "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git" kartograf-mcp
```

Cursor reads `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "kartograf": {
      "command": "uvx",
      "args": ["--from", "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git", "kartograf-mcp"]
    }
  }
}
```

VS Code reads `.vscode/mcp.json`, whose key is `servers`:

```json
{
  "servers": {
    "kartograf": {
      "command": "uvx",
      "args": ["--from", "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git", "kartograf-mcp"]
    }
  }
}
```

| Option | Meaning |
|---|---|
| `--tools FAMILIES` | `discovery`, `availability`, `data`, `project`, `store`; `core` is the ten tools of the main tasks |
| `--allow-dir DIR` | absolute directory (repeatable) that every path argument and the store must lie in; another path is `forbidden` |
| `--allow-writes` | data tools write (needs `--allow-dir`); without it they only plan (`check`) |

Tool descriptions and instructions are English; the server plans until `--allow-writes` and never writes outside `--allow-dir`.

## Related tools

- [Hydrolog](https://github.com/Daldek/Hydrolog) reads the SoilGrids rasters that `soil download` writes and computes HSG, curve numbers and hydrographs.
- [Hydrograf](https://github.com/Daldek/Hydrograf) is a web application that downloads its DEM, land cover and HSG through the Kartograf library.
- [IMGWTools](https://github.com/Daldek/IMGWTools) provides the hydro-meteorological observations and PMAXTP that Kartograf does not; its store follows the same design.
- [Archiwista](https://github.com/Daldek/Archiwista) browses Kartograf and IMGWTools stores through `iter_store` and `read_sidecar`.
- [Retman](https://github.com/Daldek/Retman) is a Polish natural-language layer over the catalogs of the tools.
- External: the Geoportal of GUGiK (https://www.geoportal.gov.pl) for one-off manual downloads and ordering; OpenTopography for global DEMs outside Poland and Czechia.

## Errors and exit codes

An error is a `kartograf-error/1` document with `code`, `title`, `message`, `hint`, `details` and `exit_code`; the codes come from the [shared registry](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md). The outcomes `partial` (10) and `failed` (11) are results, not errors: read `items` and retry the failed units. The most common errors:

| Code | Exit | What to do |
|---|---|---|
| `validation_error` | 2 | an option is wrong or missing: fix `details.option` as `hint` says |
| `source_unavailable` | 5 | network, HTTP or timeout: retry the same call later |
| `no_data` | 14 | the source has no data there (`details.reason`): change the area or the year |
| `io_error` | 9 | a directory or file is unavailable: check `details.path` and the permissions |
| `forbidden` | 12 | MCP only: a path outside `--allow-dir`, or a write without `--allow-writes` |

Ctrl-C ends with 130 and SIGTERM with 143; nothing half written stays in the store.

## Data and licensing

Sources, as in the [Nogat registry](https://github.com/Daldek/Nogat/blob/main/ecosystem.yaml):

| Source | Data | Licence |
|---|---|---|
| GUGiK (Poland) | NMT, NMPT, orthophoto, LAZ, BDOT10k, PRG, EGiB, 3D models, geodesy | free reuse with attribution (Prawo geodezyjne i kartograficzne) |
| CUZK (Czechia) | DMR, DMP, orthophoto, LAZ, ZABAGED, RUIAN, HY-NET | CC BY 4.0 |
| Copernicus CLMS | CORINE Land Cover | Copernicus data policy, attribution required |
| ISRIC SoilGrids | soil properties, input of HSG | CC BY 4.0 |

Every file has a sidecar `<file>.meta.json` (`kartograf-meta/1`) with the CRS, the source, the request, the SHA-256 and the licence with a ready-made attribution text; pass it on when you publish results.

Files go to the directory of `--root` (`root`), one directory per product: `<root>/<product>/<country>_<system>[_<variant>]/...`. A version is a file in `versions/<label>_<sha8>/`; the standard path and `full_sheet/` are hard links to the newest local version ([ARCHITECTURE.md](https://github.com/Daldek/Kartograf/blob/main/docs/ARCHITECTURE.md), section 3).

### Settings, directories and backup

Settings come from the first of: the command-line option, the variable `KARTOGRAF_<KEY>`, the shared variable `NOGAT_<KEY>` (only `data_dir`, `cache_dir` and `lang`), the table `[kartograf]` and then `[nogat]` of `nogat.toml`, and the default (Nogat DEV-18). `nogat.toml` is in the user configuration directory (`~/.config/nogat/nogat.toml` on Linux) or at the path in `NOGAT_CONFIG`; Kartograf works without it, and refuses to run with a file it cannot read (`validation_error`, reason `invalid_config`). `kartograf config show [--json]` lists every setting with its value and source. [.env.example](https://github.com/Daldek/Kartograf/blob/main/.env.example) has every variable; Kartograf does not read a `.env` file.

| Variable | Key in `nogat.toml` | Meaning | Default |
|---|---|---|---|
| `KARTOGRAF_ROOT` | `[kartograf] root` | root of the store (reported by `config show`; the commands still take the store from `--root`) | `<data_dir>/kartograf` |
| `KARTOGRAF_DATA_DIR`, `NOGAT_DATA_DIR` | `data_dir` | parent of the stores | user data directory of `nogat` (`~/.local/share/nogat`) |
| `KARTOGRAF_CACHE_DIR`, `NOGAT_CACHE_DIR` | `cache_dir` | parent of the caches; the metadata cache is `<cache_dir>/kartograf/metadata.db` | user cache directory of `nogat` (`~/.cache/nogat`) |
| `KARTOGRAF_LANG`, `NOGAT_LANG` | `lang` | language of human-readable output, `pl` or `en`; `--lang` overrides it; the `--json` output and the error line are English (the library texts move into the message catalog area by area) | `pl` |
| `KARTOGRAF_DEBUG` | `[kartograf] debug` | print tracebacks and every library log record | off |
| `NOGAT_CONFIG` | - | path of `nogat.toml` | user configuration directory |
| `CLMS_CREDENTIALS` | never in the file | CLMS API credentials for CORINE as GeoTIFF ([USAGE.md](https://github.com/Daldek/Kartograf/blob/main/docs/USAGE.md), section 6); `config show` says present or missing | - |

Kartograf never writes a cache or state into the current directory. Without `CLMS_CREDENTIALS` CORINE is a PNG preview.

**Backup.** A store keeps hard links: the standard path and `full_sheet/` are hard links to a file in `versions/`. Back it up with a copy that preserves them (`rsync -aH SOURCE/ TARGET/`); on Windows use a tool that keeps hard links, not Explorer or `robocopy`, or the copy is two to three times larger. A source serves its current state, so a version that the source has since replaced or withdrawn (a campaign GUGiK no longer lists, a national file replaced in place) cannot be downloaded again: the store holds the only copy, and that part is the one to protect first. The metadata cache is not data and needs no backup.

## Documentation

| File | Content |
|---|---|
| [USAGE.md](https://github.com/Daldek/Kartograf/blob/main/docs/USAGE.md) | task-oriented guide to the CLI, the library and the MCP server |
| [ARCHITECTURE.md](https://github.com/Daldek/Kartograf/blob/main/docs/ARCHITECTURE.md) | modules, contracts, store layout, flows per product |
| [DECISIONS.md](https://github.com/Daldek/Kartograf/blob/main/docs/DECISIONS.md) | architecture decision records |
| [SCOPE.md](https://github.com/Daldek/Kartograf/blob/main/docs/SCOPE.md) and [PRD.md](https://github.com/Daldek/Kartograf/blob/main/docs/PRD.md) | scope, limits and product requirements |
| [CHANGELOG.md](https://github.com/Daldek/Kartograf/blob/main/docs/CHANGELOG.md) | changes per release, including breaking ones |

## Development

Read [CLAUDE.md](https://github.com/Daldek/Kartograf/blob/main/CLAUDE.md) first: rules, code map and documentation map. `scripts/gate.sh` runs the whole gate (ruff, mypy, offline tests with coverage, commit checks); it must pass before a commit.

## Status, licence, author

Pre-release (development status alpha): the version is `kartograf --version`, and the changes that are not released yet are in the CHANGELOG. Licence: MIT ([LICENSE](https://github.com/Daldek/Kartograf/blob/main/LICENSE)). Author: [Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/).
