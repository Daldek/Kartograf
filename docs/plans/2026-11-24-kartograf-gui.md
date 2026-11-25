# Plan: Kartograf's GUI, plans and scripts for the user's own machine

Approved: 2026-11-24, the author (in session: „Ok, podoba mi się ten plan. Zapisz to.”; the answers to the open questions: „GUI Kartografa: wszystkie podkłady mapowe powinny być wspólne między projektami. Wciąż jest to pewna niejednolitość, którą trzeba załatwić. Jako wzór: Hydrograf. Reszta ok.”)

Status: approved on 2026-11-24, its open questions answered the same day (below); nothing started.

The author asked for a Kartograf GUI that „pozwalał na pobieranie danych przestrzennych wprost ze źródeł, generując
skrypt do basha/powershella lub dając ich treść. Wszystkie ewentualne klucze API byłyby po stronie użytkownika”; after
the design below and the clarification that the data bytes go between the user and the source, never through the
author's server, he approved it: „Ok, podoba mi się ten plan. Zapisz to. Myślę, że bezpośrednio u Kartografa, a
Latarnik powinien się do tego odnosić.” The plan therefore lives here; the Nogat plan of Latarnik
(`docs/plans/2026-11-24-latarnik.md`, branch `plan/latarnik`, approved 2026-11-24) refers to it. Details the design
did not fix were marked „[proposed]”; the author's answers of 2026-11-24 to the open questions decide them, and the
design below follows them (DEV-17.4). Branch `plan/kartograf-gui` from `develop` `332542f9`, not merged until the
author decides (DEV-3.3).

Requirements: DEV-17.4, HUB-5.2 (producers first), AGI-3.1, AGI-6.1 to AGI-6.6, DEV-13.1, DEV-18.4, DEV-15.1,
DEV-15.7 to DEV-15.11 (a public GUI), DEV-12.4 to DEV-12.9 (logs), DEV §20 (DEV-20.5, `ATTRIBUTION.txt`), DEV-3.3.
Decision record: ADR-063 [proposed number], written in step K1.

## Goal

A person without a command line habit picks data on a map and leaves with something to run on their own machine:

1. **Map and form.** An area drawn on the map or a sheet chosen, a product picked; the form is generated from the
   command catalog (`kartograf commands schema`), so a new option of a command appears without GUI work.
2. **The plan first.** Before anything is generated, the plan of the request (`--check`, `kartograf-plan/1`): its
   files, sizes, sources and licences as a table, and the footprints of its sheets on the map.
3. **Three outputs**, each to copy or to save as a file:
   - (a) by default, the `kartograf …` command line;
   - (b) a bash or PowerShell script that checks for Kartograf or installs it (`uv tool install …@tag`) and runs the
     command;
   - (c) a plain `curl` (bash) or `Invoke-WebRequest` (PowerShell) script built from the URLs of the plan, with
     checksums where they are known and an `ATTRIBUTION.txt` (DEV §20), which says plainly what it does not do: no
     retry policy of Kartograf, no sidecars, no store. A source that needs an OAuth key exchange (CLMS,
     `CLMS_CREDENTIALS`) is left out of (c) with the reason.
4. **Keys only on the user's side.** Scripts read environment variables (`$CLMS_CREDENTIALS`,
   `$env:CLMS_CREDENTIALS`); the GUI never asks for a key and never sends one; the plan of a keyed source is made
   without the key or marked incomplete.
5. **The GUI downloads and stores nothing.** A static page and a light read-only `kartograf server` that computes
   plans. The server queries the sheet indexes of the sources on the users' behalf, so it caches the indexes and
   limits plans per client; the data bytes never pass through it. Without the server a user runs `kartograf …
   --check` locally. Locally `kartograf gui serve` starts both.

## Where it starts (2026-11-24)

| Fact | Consequence |
|---|---|
| `kartograf commands schema --command "<group> <verb>"` returns `kartograf-commands/1` (Nogat `commands-1`) with the options, their type, bounds, allowed values with meanings, path role, rules, examples, errors and the Polish texts in `i18n.pl` (`src/kartograf/catalog/build.py:357-371`, `catalog/commands/misc.py:273-277`, `catalog/model.py:5-9`) | the form is generated from it, as the design wants |
| The options carry a `section` and a `path_role` (`input` for `--geometry`, `output` for `-o`, `root` for `--root`: `src/kartograf/catalog/shared.py:64-123`) | the form groups fields by section; the server refuses every path option a client sends |
| `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command` serve any catalog command (`src/kartograf/commands.py:157`, `:262`, `:329`, `:412`, `:519`); `check_command` returns `kartograf-result/1` with `kartograf-plan/1` (`commands.py:562-565`) | the line of output (a) is `format_command`; the plan is `check_command` |
| An area is `--bbox` with `--bbox-crs`, EPSG:4326 among the accepted CRSs (`catalog/shared.py:76-93`, `download/options.py:311-313`), or `--geometry FILE`, an input path (`catalog/shared.py:94-101`) | a rectangle drawn on the map is a `--bbox … --bbox-crs EPSG:4326`; a polygon needs a file, so it comes later (question 6) |
| `sheet parse` gives a sheet's `bounds` in its native CRS, `None` for SM5 and ZTM sheets, whose frame is in the ČÚZK index (`src/kartograf/sheet_info.py:91-93`); `sheet find` gives the sheets of an area (`sheet_info.py:138-160`) | PL footprints need no network; CZ SM5/ZTM footprints need the server |
| A plan item has `track`, `segment`, `hierarchy`, `name`, `unit`, the local version, `available_label`, `available_signal`, `status` (`src/kartograf/download/plan.py:80-93`) | the table of the plan |
| `available_signal` differs per track: `{url, date, pzgik_date}` of a PL sheet (`download/updates.py:22-24`), `{url, year, date}` of a LAZ tile (`download/laz.py:248-251`), `{url, …record}` of a collection file of an index (`download/collections.py:3271-3273`), the HTTP headers `etag`, `last_modified`, `content_length` of a probe (`plan.py:58-60`), `{version, record, sha256}` of a CAMELS-PL member (`download/releases.py:802-806`), `None` for HSG, cutouts and others; a plain plan has no signal at all (`download/fetch.py:659-673`) | no plan names the URL, size, source and licence of every file: the plan grows additive fields (step K2; schemas `/1` only grow, `CLAUDE.md:27`) |
| The sources publish no checksums; Kartograf computes SHA-256 when it writes (`docs/SCOPE.md:992-997`); the only pinned SHA-256 are the members of a release (`src/kartograf/sources/descriptor.py:389-396`), read out of a ZIP by range requests | (c) checks a size where the plan knows one and a checksum only where the registry pins one |
| `<group> list-sources` returns `kartograf-sources/1` with the licence and `auth` of each source (`catalog/shared.py:401-413`, `src/kartograf/source_info.py:131-132`, `:383-386`); CORINE has `auth="clms_oauth"` (`sources/registry.py:3074`) | the licence column and the keyed sources come from the registry, not from GUI code |
| `CLMS_CREDENTIALS` comes from the environment only (`src/kartograf/config.py:79`; DEV-18.4, Nogat `standards/DEVELOPMENT_STANDARDS.md:822-824`) and only the Auth Proxy reads it (`CLAUDE.md:15`, `auth/client.py:268`); without it CORINE 2018 to 2000 is the WMS preview (`landcover/manager.py:2155-2157`) | the server runs without the variable; a CORINE plan there is the preview's plan, marked incomplete |
| Kartograf retries a request up to `MAX_RETRIES = 3` times with backoff, only network errors, 429 and 5xx (`src/kartograf/transport/http.py:5-7`, `:39`), and checks the format of what it got (`docs/SCOPE.md:993-997`) | what (c) does not do is named in its header |
| The metadata cache keeps index records 7 days and the ČÚZK sheet index 30 days (`src/kartograf/cache/metadata.py:58-62`); a check revalidates an ATOM feed (`download/collections.py:3268`) | the server's index cache is this cache, with a server setting of how fresh a plan must be |
| `kartograf-mcp` starts read only: a writing command only plans, its run options are `forbidden` (`src/kartograf/mcp_server.py:12-15`, `exceptions.py:587-589`) | the server takes the same policy without a switch to writes |
| No Kartograf command answers HTTP (`CLAUDE.md:125`, Deviations DEV-12.4 to DEV-12.9); SCOPE puts a REST server in 1.0+ and the web GUI in Archiwista (`docs/SCOPE.md:984-986`, `:1224`); the registry has `rest: null` (Nogat `ecosystem.yaml:76`) | the server, its logs, SCOPE and the registry change (steps N1, K4, K6) |
| Install line: `uv tool install "kartograf @ git+https://github.com/Daldek/Kartograf.git@v0.8.0"` (`README.md:24`); `develop` is `0.9.0.dev0` (`CLAUDE.md:9`) | (b) pins a released tag, never a dev version |
| `ATTRIBUTION.txt`: DEV-20.5 (Nogat `standards/DEVELOPMENT_STANDARDS.md:1146-1147`, `:1154-1156`), `kartograf.attribution` (`provider_lines`, `write_attribution`: `src/kartograf/attribution.py:98`, `:188`); provider lines exist for CAMELS-PL only, GUGiK, ISRIC and ČÚZK carry the registry's `license.attribution` (`CLAUDE.md:126`) | (c) writes the lines Kartograf has, else the registry's text of the source |
| Precedents: `obserwator server` and `obserwator gui serve` (Obserwator `README.md:119`, `:136`); `hydrolog gui serve` with the extra `gui` (Starlette, uvicorn: Hydrolog `pyproject.toml:70-77`); Hydrolog's catalog form `src/hydrolog/gui/web/src/forms/command-form.js:1-4` and its routes `api/commands` (`src/hydrolog/gui/_app.py:783-792`) | names, extra and form start from them |
| Archiwista plans and runs Kartograf commands in its store (`src/archiwista/adapter/kartograf/adapter.py:533`, `:557`) and has an editor's server side (`src/archiwista/api/commands.py:3-7`), but only „Wklej polecenie producenta” in its UI (Nogat `docs/plans/2026-11-01-nogat-gui-platform.md:174-178`) | the command builder is the shared part |
| The GUI platform plan wants „a graphical editor of such commands” (`2026-11-01-nogat-gui-platform.md:37-38`), as a kit component for Archiwista and the hub (option E2, `:255-256`), `<nogat-command-form>` reading commands-1 entries (item 8, `:401-408`); the kit (`nogat-kit` 1.2.0) has no such component (Nogat `design/kit/nogat-kit.json:3-16`) | step N1 adds it |
| `nogat-server/1` at `GET /api/v1/server` (`services` with `tool`, `version`, `api`, `capabilities`; `base` and `api` merged into one map `api`, e.g. `{"1": "/kartograf/v1"}`, as the Latarnik and Goniec plans agreed on 2026-11-24) is proposed by the Goniec plan, not approved (Nogat branch `plan/qgis-plugin`, `docs/plans/2026-11-24-qgis-plugin.md:93`) | Kartograf's server answers it once Nogat has the schema |

## Design

**D1. Map and form.** The page shows a map and, beside it, the form of one data command (`elevation download`,
`imagery download`, `landcover download`, `soil download`, `soil hsg` and the collection groups). The first version
offers `elevation download` (NMT, NMPT, LAZ) and `imagery download` (orthophoto); `landcover download` (BDOT10k,
CORINE) and the collection groups follow (question 3). The map's base layers are the ecosystem's shared set: every
base map is shared between the projects, modelled on Hydrograf (question 2; Nogat plan
`docs/plans/2026-11-24-shared-base-maps.md`, branch `plan/shared-base-maps`, being written), and the GUI defines none
of its own. The area is a rectangle drawn on the map (`--bbox … --bbox-crs EPSG:4326`), a sheet chosen on the map or
typed (`--sheet`, the sheets of the view from `sheet find`) or a TERYT where the command takes one; a drawn polygon,
which the script would write as a GeoJSON file for `--geometry`, comes in a later version (question 6). The fields
come from `commands schema`: type, allowed values with their meanings in Polish (`i18n.pl`), sections, rules that
enable a field; a pasted line is read by `parse_command`, the line of the form is written by `format_command`, errors
stand under their field from `validate_command`'s `details.option`. The target directory (`-o` or `--root`) is a text
field the GUI never resolves: it goes into the line and the scripts as typed. The form is the kit's command builder
(D6), so a new option of a command appears without GUI work.

**D2. The plan before anything.** „Sprawdź” calls the plan; nothing is generated before it. The table lists per file
the unit, the name, the size where known, the source (registry key and provider), the licence and its status; the
map draws the footprints of the plan's units (PL sheets from `sheet parse`, LAZ tiles from their sheet code, cutouts
from their bbox, ČÚZK SM5/ZTM frames from the server's plan). The plan's notices stand above the table. A plan that
is not `ok`, or that holds a keyed source without its key, is marked incomplete and says why.

**D3. Three outputs.** Each with „Kopiuj” and „Zapisz” (`kartograf.sh`, `kartograf.ps1`):

- (a) **The command line**, the default: `format_command` of the form, with the target the user typed.
- (b) **A Kartograf script** (bash or PowerShell): it stops with the address of uv's installation guide when `uv` is
  missing (it installs nothing but Kartograf); it installs
  `kartograf @ git+https://github.com/Daldek/Kartograf.git@v<version>` with `uv tool install` when `kartograf` is
  missing; when another version is installed it runs this one command with
  `uvx --from "kartograf @ …@v<version>" kartograf …` and leaves the user's install alone (question 5); it checks that
  the variables of a keyed source are set (D4) and stops naming them otherwise; then it runs the command line of (a).
  Kartograf's retries, checks, sidecars, store and plain-mode `ATTRIBUTION.txt` all apply.
- (c) **A direct script** (`--direct`: `curl` in bash, `Invoke-WebRequest` in PowerShell): one download per file of
  the plan from its URL, into the target under the plan's plain name; a size check where the plan knows the size and
  a SHA-256 check
  where the registry pins one; then an `ATTRIBUTION.txt` with the lines of the sources of the files (DEV-20.5; the
  provider lines where Kartograf has them, else the registry's `license.attribution`). Its header says what it does not
  do: no retries and backoff of Kartograf, no format checks, no sidecars `kartograf-meta/1`, no store or versions, no
  cutout, merge or reprojection. Two kinds of file are left out of (c), each listed in the header with its reason:
  - a file of a source that needs a key exchange (CLMS: OAuth with `CLMS_CREDENTIALS`; reason `credentials`): the
    exchange belongs to Kartograf's Auth Proxy, use (b);
  - a file Kartograf builds rather than fetches (a WCS cutout, a merged or reprojected raster, HSG, a member read out
    of a ZIP by range requests; reason `built`): no URL serves it, use (b).
  A plan whose every file is left out gets no (c), with the reasons.

**D4. Keys only on the user's side.** The GUI has no field for a key, stores none and sends none; the server runs
without `CLMS_CREDENTIALS` in its environment. A keyed source is known from `auth` of `kartograf-sources/1`; its plan
is what Kartograf plans without the key (CORINE: the WMS preview) and the GUI marks it incomplete: „the CLMS data need
your key in `CLMS_CREDENTIALS`; run (a) or (b) on your machine”. Scripts read the variable from the environment only
(`$CLMS_CREDENTIALS`, `$env:CLMS_CREDENTIALS`) and never write it into a file.

**D5. The GUI downloads and stores nothing.** The page is static files. `kartograf server` is read only: it answers
the catalog (`commands list`, `commands schema`), the queries without paths (`sheet parse`, `sheet find`,
`<group> list-sources`, `<group> list-layers`, `elevation availability`), the plans (`?check=true` of the data
commands) and `script generate` (D7); a run, a path option from a client, `store *`, `cache *` and `config show`
answer `forbidden`. It writes only its metadata cache and its logs, never data. It computes a plan against a target
it owns and never shows (how: ADR-063, verified in step K2), so every file of the plan is to be written and the plan
says nothing about the server's disk. Because it queries the sources' sheet indexes on the users' behalf:

- the indexes are cached server-side (the metadata cache, `<cache_dir>/kartograf/metadata.db`) and a plan reuses an
  index younger than a server setting `index_max_age` (1 day) instead of revalidating it per plan; the plan
  shows `checked_at` and the age of the indexes it read;
- plans are limited per client beside DEV-15.9's request limit: `plan_limit` per `plan_window` (20 per 600 s) and
  `plan_max_units` units per plan (500); over a limit, `429` with `Retry-After` and the error document of
  `rate_limited` (AGI-6.5); the three values are revisited after the first days of public traffic (question 7);
- the data bytes never pass through it: a URL of the plan is the source's, never a proxy of the server.

Without the server the page still builds (a) and (b) from the catalog it ships, and tells the user to run
`kartograf … --check` locally; (c) is then `kartograf script generate --shell bash --direct …` run locally.
`kartograf gui serve` starts the page and the server on 127.0.0.1 in one process.

**D6. Roles.** Archiwista runs downloads on a server into a managed store; Kartograf's GUI only plans and generates
for the user's own machine. The shared part is the command builder, a Nogat kit component (the GUI platform plan's
„graphical editor of producer commands”, `<nogat-command-form>`), generated from a command catalog and used by
Archiwista („Kreator polecenia”), Kartograf's GUI and later others. It starts from Hydrolog's catalog form, which
already renders commands-1 entries.

**D7. Relation to Latarnik.** Latarnik (Nogat plan `docs/plans/2026-11-24-latarnik.md`, branch `plan/latarnik`)
hosts the page and routes `/kartograf/v1/…` to `kartograf server`'s `/api/v1/…`; its `nogat-server/1` lists the
service `kartograf` with `api` `{"1": "/kartograf/v1"}` (a tool alone: `{"1": "/api/v1"}`; the shape the Latarnik and
Goniec plans agreed on 2026-11-24, one `GET /api/v1/server` on every server). The page finds its API base as its own
tool's entry in `/api/v1/server` of its origin, one request, so the same files run under `kartograf gui serve` and
behind Latarnik. Kartograf's GUI also runs without Latarnik.

### Where this plan reads the design differently

- **Command names.** Catalog ids are `<group> <verb>` (AGI-3.1): the script command is `kartograf script generate
  --shell …`, not `kartograf script --shell …`. `kartograf server` follows `obserwator server` and, like
  `kartograf-mcp`, stays outside the catalog (it starts a process); `kartograf gui serve` is a catalog command like
  Hydrolog's.
- **The shells of (c).** The design names `--shell bash|powershell|curl`; (c) exists for both shells, so
  `--shell bash|powershell` chooses the shell and `--direct` makes (c) of it: plain `curl` or `Invoke-WebRequest`
  (question 4).
- **The plan grows.** The design takes the URLs, sizes, sources and licences from the plan; today no plan names them
  for every file (Where it starts), so step K2 adds them before the GUI.
- **Built files.** Besides the keyed sources, (c) leaves out the files Kartograf builds, with the reason `built`.

## Interface changes

1. `kartograf-plan/1`, additive: per item `source` (the registry key) and `fetch`, `{url, size_bytes,
   sha256}` (a field `null` when not known) when the file is the bytes at `url` unchanged, else `null` with
   `fetch_reason` `credentials` or `built`; at the top `sources`, `{key, provider, license: {id, attribution, url},
   auth}` per source of the items. Filled from what the check already reads, with no extra request for a size; the
   same in store and plain plans.
2. Catalog command `script generate` (CLI, library function `generate_script`, MCP tool, REST): the command line of a
   data command (`--command`, read by `parse_command`) or a saved plan (`--plan FILE`), `--shell bash|powershell`,
   `--direct` for (c), the target; result `kartograf-script/1` `{shell, kind, text, files, left_out: [{name, unit,
   reason}], notices}`. `kind` `kartograf` for (b), `direct` for (c). It queries the network only to make a plan when
   given no `--plan`.
3. `kartograf server` (extra `server`, Starlette and uvicorn as Hydrolog's `gui`): `/api/v1/<group>/<verb>`
   of the commands of D5 (AGI-6.1; `POST …/download?check=true` only), `/openapi.json` from the catalog (AGI-6.2,
   AGI-6.6), errors as `application/problem+json` (AGI-6.3), `Accept-Language` (AGI-6.4), `GET /api/v1/server`
   (`nogat-server/1`, capabilities `catalog`, `plan`, `script`), the limits of D5, logs `nogat-log/1`
   (DEV-12.4 to DEV-12.9, DEV-15.10), daily totals (DEV-15.11); settings `index_max_age`, `plan_limit`,
   `plan_window`, `plan_max_units`, `request_limit`, `request_window` (DEV-18.1).
4. `kartograf gui serve` (extra `gui`): the static page and the server on 127.0.0.1; the page under
   `src/kartograf/gui/web/`, ES modules (DEV-15.1), the kit files copied byte for byte (the command builder,
   `nogat-sources`, `nogat-app-menu`, the terms), MapLibre as Archiwista's, with the base layers of the shared set
   (D1).
5. Deviations: DEV-12.4 to DEV-12.9 (`CLAUDE.md:125`) narrows to the Auth Proxy; SCOPE's „REST API server” (1.0+)
   and „web GUI = Archiwista” lines change.

## Steps

Producers first (HUB-5.2): Nogat (N1 and the Nogat step of the shared base maps), then Kartograf, then Latarnik.
Kartograf's steps K1 to K7 ship in the minor after `0.9.0` (question 1), whose released tag (b) pins.

| # | Project | Step | Main files |
|---|---|---|---|
| N1 | Nogat | The command builder as a kit component (`<nogat-command-form>`, from Hydrolog's `forms/command-form.js` and the GUI platform plan's item 8), the optional commands-1/AGI-2.3 fields it reads; `nogat-server/1` (shared with the Goniec plan) with Kartograf's capabilities; Kartograf in the registry: `interfaces.rest`, its server and its route under Latarnik; an ECO decision | `design/kit/`, `schemas/`, `ecosystem.yaml`, `standards/` |
| K1 | Kartograf | ADR-063 (the plan fields, the target of a server plan, the script command, the server, the GUI, the limits, the author's answers of 2026-11-24); branch `feat/gui` from `develop` | `docs/decisions/`, `docs/DECISIONS.md` |
| K2 | Kartograf | The additive plan fields of every track, in store and plain plans; the target of a server plan | `download/plan.py`, `download/fetch.py`, `download/updates.py`, the tracks, `messages/` |
| K3 | Kartograf | `script generate` in the catalog, the library, the CLI and MCP; the three outputs, `ATTRIBUTION.txt` lines, the left-out files | `catalog/commands/`, a new `script.py`, `attribution.py`, `messages/` |
| K4 | Kartograf | `kartograf server` (extra `server`): routes from the catalog, the read-only policy, OpenAPI, problem documents, `nogat-server/1`, index cache, limits, logs, totals | a new `server/`, `pyproject.toml`, `config.py` |
| K5 | Kartograf | The GUI and `kartograf gui serve` (extra `gui`): map with the shared base layers, form (NMT, NMPT, LAZ and orthophoto first), plan table, footprints, outputs; kit files copied; the terms of a public GUI (DEV-15.7, DEV-15.8) | a new `gui/`, `pyproject.toml` |
| K6 | Kartograf | Documentation: this plan's results, ADR-063, CHANGELOG `[Unreleased]`, PROGRESS, README, USAGE, ARCHITECTURE, SCOPE, `CLAUDE.md`; regenerate `AGENTS.md`, `llms.txt`, `_output_schema.py`, the USAGE tables | `docs/`, `README.md`, `CLAUDE.md` |
| K7 | Kartograf | Offline tests (routes against recorded answers, the scripts' text, the limits, CLI = API = REST of `script generate`), a live plan and a run of (b) and (c) on the author's machine into a directory outside `/tmp`, `scripts/gate.sh`, the author's review | `tests/` |
| L1 | Latarnik | Hosting the page and routing `/kartograf/v1/…` to `kartograf server` (its own plan) | Latarnik |
| A1 | Archiwista | Its „Kreator polecenia” from the kit component (its own plan, later) | Archiwista |

## Not in scope

- Downloading or storing data in the GUI or on the server; a proxy of the data bytes.
- Taking, storing or forwarding a key of any source.
- Archiwista's managed store, projects and server-side runs (D6).
- A polygon area in the first version: rectangle and sheets first, a polygon later (question 6).
- Base maps of Kartograf's own: the GUI takes the ecosystem's shared set (question 2).

## Risks

- **Load on the sources.** Every plan queries the sources' indexes from the author's server: the index cache, the
  plan limits and `plan_max_units` bound it; a source that throttles the server fails the plans (`check_failed`), not
  the users' downloads.
- **Stale plans.** A plan from a cached index can name a file a source has replaced: the plan shows its age, and (b)
  plans again on the user's machine; (c) downloads what the URL serves at the time.
- **(c) is weaker than Kartograf.** No retries, no format checks, no sidecars: its header says so, and the GUI shows
  (a) first.
- **Version drift.** The server's Kartograf and the user's differ: (b) pins the server's released tag, the minor
  after `0.9.0` that brings the GUI (question 1); a dev server cannot generate (b).
- **Privacy.** The server sees the areas users plan; its logs hold no IP address (DEV-15.10) and its terms say what it
  sends to the sources and which providers of the shared base maps receive the visitor's IP address (DEV-15.7; Nogat
  `standards/DEVELOPMENT_STANDARDS.md:584-585`).

## Open questions (answered by the author on 2026-11-24)

1. **Release.** The GUI in 0.9.0 (opened with CAMELS-PL, `CLAUDE.md:9`) or a later minor? (b) pins a released tag, so
   a public server needs one.
   Answered 2026-11-24: the next minor after 0.9.0 (as the coordinator recommended; „Reszta ok”).
2. **Map base layer.** OpenStreetMap tiles, GUGiK's WMTS (orthophoto, topographic map) or both; the provider receives
   the visitor's IP address and the terms name it (Nogat `standards/DEVELOPMENT_STANDARDS.md:584-585`).
   Answered 2026-11-24: neither chosen here; „wszystkie podkłady mapowe powinny być wspólne między projektami”, „Jako
   wzór: Hydrograf”: the base maps come from the ecosystem's shared set, the Nogat plan
   `docs/plans/2026-11-24-shared-base-maps.md` (branch `plan/shared-base-maps`, being written), modelled on Hydrograf
   (D1, Interface changes 4, K5).
3. **Products first.** Which commands the first version offers: `elevation download` (NMT, NMPT, LAZ) and
   `imagery download`, then `landcover download` (BDOT10k, CORINE) and the collection groups.
   Answered 2026-11-24: as proposed and as the coordinator recommended; NMT, NMPT, LAZ and orthophoto first, then
   BDOT10k, CORINE and the collections.
4. **The shells of (c).** `--shell bash|powershell|curl|invoke-webrequest`, or `--shell bash|powershell` with
   `--direct`?
   Answered 2026-11-24: as the coordinator recommended; `--shell bash|powershell` plus `--direct` for plain `curl` or
   `Invoke-WebRequest`.
5. **(b) and another installed version.** Run the command through `uvx --from …@tag` and leave the user's install
   alone, or `uv tool install --force` the server's tag?
   Answered 2026-11-24: as proposed and as the coordinator recommended; `uvx --from …@tag`.
6. **Area.** A rectangle and sheets only in the first version, or a drawn polygon too (the script would write a
   GeoJSON file for `--geometry`)?
   Answered 2026-11-24: as the coordinator recommended; rectangle and sheets first, a polygon later.
7. **Limits.** `plan_limit` 20 per 600 s, `plan_max_units` 500 and `index_max_age` 1 day, or other values?
   Answered 2026-11-24: as the coordinator recommended; 20 plans per 600 s, 500 units, indexes 1 day, revisited after
   the first days of traffic.

## Results

(filled in per step)
