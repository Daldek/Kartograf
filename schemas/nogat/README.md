# Copies of the Nogat standard

Verbatim copies (ERR-3, AGI-4.1) of the files below, from the
[Nogat](https://github.com/Daldek/Nogat) repository at the commit named with each
(the tag `std-1.0` does not exist yet; replace the copies by the tag when it does):

- `error_registry.json` (Nogat `standards/error_registry.json`, commit `4bb6659`):
  error codes, exit codes and HTTP statuses. `src/kartograf/_errors.py` is generated
  from it with `uv run scripts/generate_errors.py`.
- `result-1.schema.json`, `error-1.schema.json` (Nogat `schemas/agent/`, commit
  `4bb6659`): the schemas of the result envelope and the error document.
- `commands-1.schema.json`, `command-list-1.schema.json` (Nogat `schemas/agent/`,
  commit `f5f6e67`, `develop`): the schemas of the command catalog and of its list,
  with the fields of a command form and the route `rest` (ADR-063).
- `server-1.schema.json` (Nogat `schemas/exchange/`, commit `f5f6e67`, `develop`):
  `nogat-server/1`, what a server answers at `GET /api/v1/server` (ADR-063).

`tests/contract/` validates Kartograf's documents against them. Do not edit these
files; copy them again when the standard changes.
