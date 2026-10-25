# Kartograf: instructions for Claude Code

Kartograf downloads official spatial data of Poland (GUGiK) and Czechia (CUZK), with Copernicus CORINE and ISRIC SoilGrids (NMT/NMPT, orthophoto, LAZ, BDOT10k, SoilGrids, HSG and more), and saves every file as a version in a store with a metadata sidecar. One command catalog drives the CLI `kartograf`, the Python library and the MCP server `kartograf-mcp`.

Profile: `tool` (DEV §1). What it is for: `README.md`; scope: `docs/SCOPE.md`. Requirements are cited by ID (DEV, DOC, AGI, ERR, REL) from the [Nogat standard 2.1](https://github.com/Daldek/Nogat/tree/main/standards); this repository holds no copy of it (DEV-1.3).

## Critical rules

- Python only from the project environment: `uv sync --locked --all-extras`, then `uv run ...` or `.venv/bin/python` (DEV-6.2, DEV-6.3).
- `scripts/gate.sh` (ruff format, ruff check, mypy, offline tests with coverage, commit checks; also works from a worktree) is green before every commit (DEV-7.6). Tests are offline (`-m "not live"`, no network: `tests/conftest.py` fails a test that opens a socket); `live` tests only on purpose (DEV-10.1 to DEV-10.3).
- Downloaded data goes outside the repository and outside `/tmp`, always with an explicit `--root`. The metadata cache is in the user cache directory (`<cache_dir>/kartograf/metadata.db`), never in the current directory; `kartograf config show` reports every setting. If the data directory is unavailable, stop and ask. Tests write only in `tmp_path`.
- Git (DEV-3, DEV-4): work on `develop` or a topic branch `<type>/<topic>` from it; English Conventional Commits, author `Daldek <git@debever.pl>`, no `Co-Authored-By` trailer or other AI attribution. Without the author's approval in the session: no merge into `develop` or `main`, no tag, no force-push of a shared branch, no release entry (DEV-3.3).
- English for code, docstrings, comments, log messages, documentation, commits and ADRs (DEV-2.1). A text for a person lives in `kartograf.messages` (`message("<area>.<name>", name=value)`: English default, Polish ASCII variant, ADR-053); an f-string or a Polish literal outside it is a defect.
- Secrets only from environment variables. CLMS credentials (`CLMS_CREDENTIALS`) are read only by the Auth Proxy subprocess (`kartograf.auth.proxy`), never by the main process (DEV-13.1).
- Every HTTP request has a timeout and goes through `transport/http.py` (`download_to`, `get_with_retry`, `head_signal`: retries, backoff, atomic writes); providers have no retry loops of their own (DEV-13.2).
- UTF-8, LF, final newline (DEV-14.1). `docs/DECISIONS.md` is LF too.
- Generated files are never edited by hand: `AGENTS.md` and `llms.txt` (`kartograf commands guide --format agents|llms`), `src/kartograf/_errors.py` (`scripts/generate_errors.py`), `src/kartograf/_output_schema.py` (`scripts/generate_output_schema.py`) and the tables of `docs/USAGE.md` 9.3 and 9.6 (`scripts/generate_docs.py`). After a change of the catalog, the error registry or a template in `src/kartograf/_data/agents/`, regenerate them; contract tests compare them byte for byte.
- A decision with alternatives is an ADR (`docs/decisions/NNNN-slug.md`, indexed in `docs/DECISIONS.md`). The change goes into `docs/CHANGELOG.md` in the same commit (DOC-7.2); `docs/PROGRESS.md` is updated before the last commit of a session (DEV-17.3).

## Rules for code

- The CLI only translates: a handler in `src/kartograf/cli/` turns flags into the arguments of one library function and prints its result. No data logic there: no validation of values, no choice of countries, sheets or campaigns, no `parent_request`, no reading of sidecars to decide (ADR-037; `tests/contract/test_cli_translation.py`).
- A command is a declaration in `src/kartograf/catalog/commands/<group>.py`. The CLI parser, the options of project tasks and the MCP tools are built from it, and the library and `catalog` never import `kartograf.cli` or `mcp` (ADR-046).
- Command-level functions take keyword-only arguments, check their types before any network or write (`download/arguments.py`) and have no default that changes which data is chosen (product, variant, resolution, vertical CRS, area, output): a missing value is an error that names the option and its allowed values (ADR-044).
- Every exception is a `KartografError` subclass with its own registry `code` and a `reason` (ADR-049). Invalid input is `ValidationError` (a sheet code `ParseError`), never `ValueError`; validators set `option`, `options` and `allowed` (the API argument, not the flag); keep the chain with `raise ... from err`; carry facts as attributes, not in the text.
- Data messages are `Notice(level, code, text)` in the `notices` of the result (`notices.py`); the library does not print. Results are `@dataclass(frozen=True)` with the `Document` mixin (`serialization.py`): a new document is a class, a row in `tests/contract/test_json_contract.py` and a row in ARCHITECTURE 3.6; schemas `/1` only grow (ADR-046).
- Logging: `logging.getLogger(__name__)`, `%`-style arguments, never an f-string; the library does not call `print` or configure handlers (DEV-12).
- Tests: `test_<unit>_<scenario>[_<expected>]`, arrange-act-assert, recorded server answers in `tests/fixtures/`, a flag or a track needs a CLI = API scenario in `tests/contract/test_parity*.py` (DEV-10.5, ADR-037).

## Environment and commands

```bash
uv sync --locked --all-extras             # .venv, Python 3.12 or newer
scripts/gate.sh                           # the whole gate, about 9 minutes
uv run pytest tests -m "not live" -q      # offline tests; scope them with a path or -k
uv run pytest tests -m live               # network tests, on purpose only
uv run ruff format . && uv run ruff check . && uv run mypy src tests
uv run kartograf commands list --json     # run the CLI (python -m kartograf works too)
```

Settings and variables (`KARTOGRAF_*`, `NOGAT_*`, `NOGAT_CONFIG`, `CLMS_CREDENTIALS`): README, "Settings, directories and backup", and `.env.example`. `KARTOGRAF_DEBUG=1` prints the traceback of an unexpected error. Timeouts are constants of the providers (`grep -rn "_TIMEOUT =" src/kartograf/providers`).

## Rules for agents of other repositories

For agents of Hydrograf, Archiwista, Retman, IMGWTools and others that edit Kartograf:

- change it only on a branch from `develop` (`feat/<topic>`, `fix/<topic>`), never on `develop` or `main`; no merge into them, no push to them, no tag;
- no release entry (a new `## [x.y.z] - date` heading in `docs/CHANGELOG.md`, a new `__version__`, a tag) without the author's approval; describe the change under `## [Unreleased]` and in the commit;
- before a tag the review is mandatory: `git log develop..<branch>`, the author reads the diff and `scripts/gate.sh` is green; the tag comes only after the author agrees;
- the machine interface of Kartograf: `AGENTS.md` and `llms.txt` (the guide for agents), `kartograf commands list --json` (commands, options, allowed values, examples), `--json` on every command (documents `kartograf-*/1`, errors `kartograf-error/1`, exit codes of the Nogat error registry) and the MCP server `kartograf-mcp` (`kartograf[mcp]`); described in `docs/USAGE.md` 9;
- `AGENTS.md` and `llms.txt` are generated (`kartograf commands guide --format agents`, `--format llms`): do not edit them by hand; the rules for work on the code are in this file.

## Code map (`src/kartograf/`)

```
__init__.py        public API (__all__): the only supported import surface (AGI-7.1)
cli/               argparse front end; handlers translate flags to library calls
catalog/           command declarations (commands/<group>.py), parser, documents, MCP tools
commands.py        parse_command, validate_command, format_command, run_command, check_command of ANY
                   catalog command (the call is read from its declaration: catalog/arguments.py)
download/          data.py (download_data/check_data), collections.py, manager.py (sheets,
                   campaigns, versions), availability.py, laz.py, cutouts, cz_*.py, storage.py
sources/           registry.py (source descriptors, channels, licences), variants.py
providers/         pl/ (GUGiK), cuzk/, corine.py, soilgrids.py: talk to one source
transport/         engines shared by products: http.py, unit_package, feature_bbox, atom, chunks
transform/         pinned CRS transforms (crs.py), GeoPackage writer, raster warp
core/              sheet parsers (PL-1992, PL-2000, CZ), bbox, geometry
landcover/         BDOT10k, CORINE and SoilGrids orchestration
hydrology/         hsg.py: hydrologic soil groups from SoilGrids
project/           project manifest kartograf-project.json: model, operations, commands
store.py           read API of the store (iter_store, read_sidecar, ...); store_*.py documents
cache/  auth/      metadata cache (SQLite WAL); CLMS Auth Proxy
mcp_server.py      MCP server on the catalog (extra mcp); guide.py generates AGENTS.md, llms.txt
exceptions.py  error_report.py  envelope.py  notices.py  serialization.py  config.py
_errors.py  _output_schema.py   generated; _data/agents/ holds the guide templates
testing.py         producer fixtures for consumers (DEV-10.6)
```

Layers and dependencies: `docs/ARCHITECTURE.md` 2. Tests: `tests/unit`, `tests/integration`, `tests/contract` (interfaces, generated files, registry), `tests/support`, `tests/fixtures`.

## Documentation map

| You need | Read |
|---|---|
| State, backlog, last session | `docs/PROGRESS.md` |
| Scope, limits, roadmap to 1.0, dependencies | `docs/SCOPE.md` 2, 3, 4 |
| Product requirements (BDOT10k layers, SoilGrids parameters, CORINE years) | `docs/PRD.md` |
| Modules and layers; source descriptors and sidecar `kartograf-meta/1` | `docs/ARCHITECTURE.md` 2, 3.1, 3.2, 3.4 |
| Store layout, `versions/`, hard links, `full_sheet/`; read API for Archiwista | ARCHITECTURE 3.3, 3.3.1; ADR-036, ADR-045 |
| JSON documents `kartograf-*/1` | ARCHITECTURE 3.6; `docs/USAGE.md` 9 |
| Flows: sheets and campaigns, WCS cutout, CZ, LAZ, land cover, collections | ARCHITECTURE 4.1 to 4.10 |
| Command catalog, errors, MCP server; adding a command | ARCHITECTURE 4.11; ADR-046, ADR-049, ADR-052 |
| Adding a source, a country, a provider or a collection product | ARCHITECTURE 5 |
| Examples, results, campaigns, CLMS, known problems | `docs/USAGE.md` 1 to 7 |
| Environment, variables, `nogat.toml`, MCP configuration | README; `.env.example`; USAGE 9.6, 10 |
| Decisions and their errata (index at the top) | `docs/DECISIONS.md`, `docs/decisions/` |
| Changes per release | `docs/CHANGELOG.md` |
| The full list of options; the public API | `kartograf <group> <command> --help`, `kartograf commands list --json`; `kartograf.__all__` |
| The agent interface and the Nogat standard | `AGENTS.md`, `llms.txt`; https://github.com/Daldek/Nogat/tree/main/standards |

## Session workflow

1. Start: read this file and `docs/PROGRESS.md`; `git status` and `git log --oneline -10`; confirm the branch; find the sections of SCOPE, ARCHITECTURE and PRD that the task touches; ask when something is unclear (DEV-17.1).
2. A change of a public interface, or across several modules, starts with a plan in `docs/plans/YYYY-MM-DD-slug.md` that the author approves (DEV-17.4).
3. Write the test first for a defect (offline, a recorded answer as the fixture), then fix it; run the offline suite, because nothing else may break. A download defect: find the provider, then the shared transport (`transport/http.py`), not a retry in the provider.
4. Commit in small steps, each with its documentation, after `scripts/gate.sh` is green; the CHANGELOG entry goes under `## [Unreleased]`.
5. End: update `docs/PROGRESS.md` (state, what is in progress with file and context, the next steps) and commit it (DEV-17.3).
6. A need in another project is a GitHub issue there, labelled `request`; change only this repository (DEV-17.5).

## Cross-project context

The place of Kartograf in the ecosystem, its dependencies and consumers: https://github.com/Daldek/Nogat/blob/main/ecosystem.yaml (entry `Kartograf`). Hydrograf uses its library, Archiwista reads its store, Retman reads its catalog, Hydraulik calls its CLI, Hydrolog reads its files, and IMGWTools shares the store design without importing it.

## Deviations

- DEV-7.3: mypy checks `tests/` with an override that allows unannotated test functions (`[[tool.mypy.overrides]]` for `tests.*` in `pyproject.toml`).
- AGI-3.8, AGI-5.1: no `kartograf mcp`; the console script `kartograf-mcp` starts the server (ADR-052, decision 10; PROGRESS, Next 2).
- AGI-4.1: the domain JSON Schemas are not published in `src/kartograf/schemas` (PROGRESS, Next 2).
- DEV-2.1, ECO-005: `docs/research` and `docs/superpowers` are Polish records (PROGRESS, Next 26).
- DEV-13.7, DEV-16.2, DEV-3.6, DEV-4.2: `SECURITY.md`, `CONTRIBUTING.md`, `docs/CLA.md`, `CONTRIBUTORS.md`, the GitHub rulesets and the single author identity of the history are the author's steps (PROGRESS, Next 3).
- REL: the distribution is `kartograf`, not `nogat-kartograf`; no `server.json` yet (PROGRESS, Next 5).
