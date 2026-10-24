# Kartograf

> Downloader of official spatial data for Poland and Czechia: elevation models and LAZ point clouds, orthophotos, land cover, soils and HSG, boundaries, cadastre and 3D models, saved as versions with metadata in a store. Python library, CLI and MCP server.

Kartograf is for getting the data of an area (a sheet code, a bbox, a geometry file, a TERYT code) from GUGiK (PL), CUZK (CZ), Copernicus and ISRIC, and for reading what was downloaded. It is not for hydrological computation (use Hydrolog) or for IMGW and CHMU measurement series (use IMGWTools).

Interfaces: Python (<!-- kartograf:python_example -->), the CLI (`kartograf <group> <command> --option value --json`) and the MCP server (`kartograf-mcp`, read only unless started with `--allow-writes --allow-dir DIR`; a tool is an `operation_id`). Install with `pip install "kartograf @ git+https://github.com/Daldek/Kartograf.git"`; the extra `mcp` adds the server.

Work in four steps: discover (`kartograf commands list`, `kartograf commands schema --command NAME`), check (`--check-updates`), run, read (`status`, `result`, `items`, `notices`). A result is a `kartograf-result/1` envelope; an error is a `kartograf-error/1` document whose `code` is one of: <!-- kartograf:error_codes -->.

Command groups: <!-- kartograf:group_names -->.

## Documentation

- [AGENTS.md](https://raw.githubusercontent.com/Daldek/Kartograf/main/AGENTS.md): the full guide for agents: interfaces, envelope, error codes, command index, typical flows
- [README.md](https://raw.githubusercontent.com/Daldek/Kartograf/main/README.md): what Kartograf is for, installation and quick start (Polish)
- [Usage](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/USAGE.md): task-oriented guide to the CLI, the library and the MCP server
- [Architecture](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/ARCHITECTURE.md): modules, store layout, sidecar, command catalog
- [Scope](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/SCOPE.md): what is in and out of scope
- [Changelog](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/CHANGELOG.md): changes per release

## Optional

- [Decisions](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/DECISIONS.md): architecture decision records
- [PRD](https://raw.githubusercontent.com/Daldek/Kartograf/main/docs/PRD.md): product requirements
