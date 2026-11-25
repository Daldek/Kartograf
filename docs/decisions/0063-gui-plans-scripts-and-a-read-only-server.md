# ADR-063: The GUI, plans and scripts for the user's own machine, and a read-only `kartograf server`

**Date:** 2026-11-25
**Status:** Accepted (the plan [`docs/plans/2026-11-24-kartograf-gui.md`](../plans/2026-11-24-kartograf-gui.md),
approved by the author on 2026-11-24 with his answers to its seven questions, step K1; the author reviews it at the
merge, DEV-3.3)
**Standard:** Nogat `develop` `f5f6e67` (kit 1.3.0, ECO-093 to ECO-095): DEV-17.4, HUB-5.2, AGI-2.1 to AGI-2.4,
AGI §6 (AGI-6.1 to AGI-6.10), DEV-12.4 to DEV-12.9, DEV-13.1, DEV §15 (DEV-15.1 to DEV-15.11, DEV-15.15,
DEV-15.17), DEV-18.1, DEV-18.2, DEV-18.4, DEV-19.21, DEV §20 (DEV-20.5), DEV-3.3

**Context:** The author asked for a GUI that „pozwalał na pobieranie danych przestrzennych wprost ze źródeł, generując
skrypt do basha/powershella lub dając ich treść. Wszystkie ewentualne klucze API byłyby po stronie użytkownika” and
approved the plan of 2026-11-24: a person draws an area or picks a sheet on a map, fills the form of a data command
generated from the catalog, sees the plan of the request first and leaves with (a) the `kartograf …` line, (b) a
bash or PowerShell script that installs Kartograf when needed and runs the line, or (c) a plain `curl` or
`Invoke-WebRequest` script of the plan's URLs; the GUI downloads and stores nothing, the data bytes go between the
user and the source, keys stay with the user, and a light read-only `kartograf server` computes the plans. His
answers: the GUI in the minor after 0.9.0, which (b) pins; the base maps of the ecosystem's shared set (Hydrograf as
the model); NMT, NMPT, LAZ and orthophoto first; `--shell bash|powershell` with `--direct`; `uvx --from …@tag` when
another version is installed; a rectangle and sheets before a polygon; 20 plans per 600 s, 500 units per plan,
indexes reused for a day, revisited after the first days of traffic.

Nogat's step N1 is on `develop` (`40bae70`, `f5f6e67`): the kit 1.3.0 has `<nogat-command-form>` (DEV-15.17,
ECO-093), generated from a command's commands-1 entry with the optional fields AGI-2.3 now names (`section`,
`requires`, `excludes`, `applies_to`, `required_when`, `i18n.pl` of an option, a command's `one_of`); commands-1 and
the command list take `rest` (`{method, path, key}`) and `long` (ECO-095); every server answers `GET /api/v1/server`
with `nogat-server/1` (ECO-094), Kartograf's capabilities being `catalog`, `plan` and `script`, and serves its
command list at `/api/v1/commands/list` (AGI-6.7); the catalog decides access and caching (AGI-6.8); the client's
address comes only from a trusted proxy (AGI-6.9); a path option is refused with `forbidden` (AGI-6.1). Latarnik
routes `/kartograf/v1/…` to `kartograf server`'s `/api/v1/…` by the `rest` of each entry of the command list.

What exists: the catalog declares sections, Polish texts and constraints (`Param.section`, catalog messages,
`Constraint`) but `kartograf-commands/1` writes none of them; `check_command` plans any data command
(`kartograf-plan/1`), but no plan names the URL, size, source and licence of every file and a plain plan has no
signal at all (the plan, Where it starts); `format_command` and `parse_command` are library functions without a
catalog command, so no client of a server can call them; no command answers HTTP (`CLAUDE.md`, Deviations
DEV-12.4 to DEV-12.9). Archiwista serves its producers' lines as catalog commands of its own (`commands parse`,
`commands format`, `POST /commands/parse`, `POST /commands/format`).

**Options:**
- A) What a plan says of each file.
  - A1) A document of its own beside the plan: a second description of the same files.
  - A2) Additive fields of `kartograf-plan/1` (schemas `/1` only grow) (chosen).
- B) The size of a file.
  - B1) A `HEAD` per file: one request per file on every plan, on the users' behalf.
  - B2) Only what the check already reads: the index record, the probe's `content_length`, the size the registry
    pins (chosen).
- C) The target of a plan made for another machine (the server's, and the plan of (c)).
  - C1) The server's default store: the plan would tell of the server's disk and say `current` for a file it holds.
  - C2) An empty store of the process: the store's selection keeps every campaign, (c) writes plain files, and the
    plan names a path of the server.
  - C3) A plain write into a directory that does not exist, answered as the write into `.` (chosen): every file is
    `write`, the selection is the one (c) downloads, the names are the plain names, and nothing of the server's disk
    is shown.
- D) The script command.
  - D1) `kartograf script --shell bash|powershell|curl`: no `<group> <verb>` (AGI-3.1).
  - D2) `kartograf script generate --shell bash|powershell [--direct]` (chosen, question 4).
- E) (b) on a machine with another version of Kartograf.
  - E1) `uv tool install --force` of the pinned tag: replaces the user's install.
  - E2) `uvx --from "kartograf @ …@v<version>" kartograf …` for the one command (chosen, question 5).
- F) How a client of the server writes and reads the line of a form (DEV-15.17).
  - F1) A writer of lines in the GUI's JavaScript: a second writer drifts from `format_command` (ECO-093, Rejected).
  - F2) Routes of the server outside the catalog: Latarnik routes only what the command list names (AGI-6.8).
  - F3) Catalog commands `commands format` and `commands parse` on `format_command` and `parse_command`, as
    Archiwista serves its producers' lines (chosen).
- G) The server.
  - G1) FastAPI, as Obserwator's REST server: one more dependency and a second model of every option beside the
    catalog's.
  - G2) Starlette and uvicorn, as Hydrolog's GUI (both already in the lock through the SDK of the extra `mcp`), the
    routes read from the catalog's `rest` (chosen).
- H) `plan_max_units`.
  - H1) `429 rate_limited` with `Retry-After`, as the plan writes it: a request over the bound never succeeds, so a
    `Retry-After` would mislead.
  - H2) `validation_error` (`400`, reason `too_many_units`, `details.allowed` the bound), the plan limit staying
    `429` (chosen; read differently from the plan, below).
- I) The GUI's form.
  - I1) A form of the GUI's own per command: DEV-15.17 forbids it.
  - I2) The kit's `<nogat-command-form>` fed with `kartograf-commands/1`, its line through `commands format`, a
    pasted line through `commands parse` (chosen).
- J) Where the options' sections and Polish texts go.
  - J1) In every `commands schema` page: `elevation download` would grow from about 17,000 to about 30,000
    characters, over the default page of 20,000 (DOC-1.7).
  - J2) In a page asked for them, `commands schema --form`, within the 50,000 characters of DOC-1.7; the rules stay
    on every page (chosen).

**Decision:** A2, B2, C3, D2, E2, F3, G2, H2, I2 and J2.

1. **The form's fields in the catalog.** `kartograf-commands/1` writes, from the declarations, the rules of the
   constraints as the option fields of AGI-2.3 (`requires` and `excludes` on the option given, `applies_to` and
   `required_when` as `{option: true | [values]}`) and a command's `one_of`: each non-optional `one_of` constraint as
   alternatives of one option each (`[["sheet"], ["bbox"], ["geometry"]]`), the options keeping their `one_of` group;
   an `any_of` constraint stays in the rules only. With the new option `form` (`commands schema --form`, J2) each
   option also carries its `section` (the English title of its `--help` section) and `i18n.pl` (`description`,
   `section`, and `enum`, the Polish meaning of each allowed value by the value): the catalog messages the CLI
   already renders in Polish, the meanings of the allowed values gaining their Polish text. The vendored
   `commands-1.schema.json` is Nogat's of `f5f6e67`, with `command-list-1.schema.json` and `server-1.schema.json`
   beside it.
2. **`rest` in the catalog.** Every entry of `kartograf-commands/1` and of `kartograf-command-list/1` carries `rest`,
   the route of `kartograf server`, or `null`; the command list also carries `effects`. `GET
   /api/v1/<group>/<verb>` for the read-only commands without a path that the server serves (`commands list`,
   `commands schema`, `commands guide`, `commands parse`, `sheet parse`, `sheet find`, every `list-sources` and
   `list-layers`, `elevation availability`), `POST` for `commands format` and `script generate`, whose inputs a URL
   cannot carry (an object), with `key` false; `POST` with `key` true for every data command, whose plan is
   `POST …?check=true` and whose run the server refuses whatever the key (AGI-6.8); `null` for `store *`,
   `cache *`, `config show` and `gui serve`. No command declares `long`: the server runs nothing longer than a plan.
3. **The plan's fields** (`kartograf-plan/1`, additive; store and plain plans alike). Per item: `source`, the
   registry key of the file's source (`pl.gugik.nmt_1m`), `null` for the position of the track `store`; `fetch`,
   `{url, size_bytes, sha256}`, when the file is the bytes at `url` unchanged, a field `null` when the check does not
   know it (`sha256` only where the registry pins it, CAMELS-PL); otherwise `fetch` is `null` and `fetch_reason`
   says why: `credentials` for a source whose `auth` is not `none` (CLMS OAuth, `CLMS_CREDENTIALS`) and `built` for
   a file Kartograf builds rather than fetches (a WCS or ImageServer cutout, a merged or reprojected raster, HSG, a
   file written from features, a member read out of a ZIP by range requests). At the top, `sources`: one `{key,
   provider, license: {id, attribution, url}, auth}` per source of the items, in the order of their first item, as
   `<group> list-sources` writes them. No request is added for any of them (B2). A plan without them, written by
   0.9.0, still loads.
4. **A detached plan.** `check_command(..., detached=True)` (neither `output_dir` nor `root`) plans the request as a
   plain write into a directory that does not exist and answers it as the write into `.`: `output_dir` is `"."`,
   each `path` is relative to it, every file is `write`. The server answers every plan so, and so does `script
   generate` when it plans; the options a plain write refuses (`all_campaigns`) are refused as `--output-dir`
   refuses them. The metadata cache of the process is the index cache: a plan reuses an index answer younger than
   `refresh_ttl_seconds` (ADR-056), which the server sets to `index_max_age`.
5. **`script generate`.** A catalog command of the new group `script` (library `generate_script`, CLI
   `kartograf script generate`, MCP tool `kartograf_script_generate`, REST `POST /api/v1/script/generate`): `shell`
   (`bash` or `powershell`, required), `command` (a line of a data command, read by `parse_command`; its `-o` or
   `--root` is the script's target as typed) or `plan` (a saved `kartograf-plan/1`; `--plan FILE` on the CLI, the
   document in the API), `direct` for (c), `target` (the directory (c) writes into, as typed: by default the line's
   target, else `.`). The result is `kartograf-script/1` `{shell, kind, text, files, left_out, notices}`: `kind`
   `kartograf` for (b) or `direct` for (c), `text` the script (the CLI prints it, so `> kartograf.sh` saves it),
   `files` the downloads of (c) (`name`, `unit`, `url`, `size_bytes`, `sha256`, `source`), `left_out` the files (c)
   leaves out (`name`, `unit`, `reason`: the item's `fetch_reason`, `check_failed`, or the `reason` of a conflict).
   Nothing is resolved or written: a path in the line or in `target` is text of the script. Effects read-only, with
   the network only to plan (c) without `plan`.
   - (b) needs `command` and pins `kartograf @ git+https://github.com/Daldek/Kartograf.git@v<version>` of the
     running release (a development version refuses (b): `unsupported`, reason `development_version`): it stops
     with the address of uv's installation guide when `uv` is missing, installs the pinned tag with `uv tool
     install` when `kartograf` is missing, runs the line with `uvx --from …` when another version is installed (E2)
     and otherwise with `kartograf`; before that it stops, naming them, when the variables of a keyed source of the
     command's product are unset (`CLMS_CREDENTIALS`). Kartograf's retries, checks, sidecars, store and plain-mode
     `ATTRIBUTION.txt` all apply.
   - (c) downloads each file of the plan with a `fetch` from its URL into the target under its plain name, checks
     the size where the plan knows it and the SHA-256 where the registry pins it, and writes an `ATTRIBUTION.txt`
     with the provider lines Kartograf has (CAMELS-PL) and otherwise the registry's `license.attribution` of each
     source (DEV-20.5). Its header says what it does not do (no retries or backoff of Kartograf, no format checks,
     no sidecars `kartograf-meta/1`, no store or versions, no cutout, merge or reprojection) and lists every file
     left out with its reason. A plan whose every file is left out gets no (c): `unsupported`, reason
     `no_direct_files`, the files in `details`.
   - Scripts read a key only from the environment (`$CLMS_CREDENTIALS`, `$env:CLMS_CREDENTIALS`) and never write it.
6. **`commands format` and `commands parse`.** Catalog commands on the public `format_command` and `parse_command`:
   `commands parse --line LINE` and `commands format --command C --options JSON`, each answering
   `kartograf-command-line/1` `{command, options, run, line}`; `commands format` takes the options of a call as
   `commands schema` lists them (the targets, `check` and the options of a run among them) and sorts them into the
   options and the run of the line itself. No network, read-only.
7. **`kartograf server`** (extra `server`: Starlette and uvicorn): outside the catalog, as `kartograf-mcp`, since it
   starts a process (AGI-6.1 reserves `server`), `kartograf server [--host 127.0.0.1] [--port 8065]`. It answers
   `GET /api/v1/server` (`nogat-server/1`: `tool` `kartograf`, `version`, `api` `{"1": "/api/v1"}`, `capabilities`
   `catalog`, `plan`, `script`, and `gui` and `terms` when it serves the GUI), `GET /api/v1/commands/list` (with
   `rest`), `GET /api/v1/openapi.json` (OpenAPI 3.1 from the catalog, `operationId` the catalog's, a relative
   `servers` URL) and the routes of decision 2: a `GET` takes its options from the query (an array as values joined
   by `,`), a `POST` from a JSON object; the answer is the envelope `kartograf-result/1` as `--json` prints it; an
   error is `application/problem+json` (AGI-6.3) with the status of the registry and its texts in the language of
   `Accept-Language` (AGI-6.4, `Content-Language`). Refused with `forbidden`: a run of a data command
   (`writes_disabled`), an option with `path_role` from a client (`path_option`; the inline form of `plan` is its
   document). It writes only its metadata cache, its logs and its daily totals, never data.
8. **Limits, logs and totals.** Per client address (the right-most `X-Forwarded-For` address that is no trusted
   proxy, the setting `trusted_proxies`, default `127.0.0.1`, AGI-6.9): `request_limit` per `request_window`
   (300 per 60 s, DEV-15.9) and `plan_limit` per `plan_window` (20 per 600 s) for plans and the scripts that plan,
   over either `429` with `Retry-After` and the problem of `rate_limited`; a plan of more than `plan_max_units`
   units (500) is H2's `validation_error`; `index_max_age` (86400 s) sets the cache's `refresh_ttl_seconds`; the
   addresses stay in memory for the window only. Logs `nogat-log/1` with Nogat's
   `standards/reference/nogat_logging.py` copied byte for byte (DEV-12.9), in `<state_dir>/kartograf/logs/`
   (`state_dir` a new shared setting, DEV-18.2); daily totals `<data_dir>/kartograf/stats.jsonl` (DEV-15.11: a plan
   or a script counts as `analyses_run`). The settings are keys of `[kartograf]` and `KARTOGRAF_<KEY>` (DEV-18.1);
   no key of any source is read: the server runs without `CLMS_CREDENTIALS`, and a plan of a keyed source is the
   plan Kartograf makes without it, its files `credentials`.
9. **`kartograf gui serve`** (extra `gui`: the server's dependencies): a catalog command of the new group `gui`
   (not an MCP tool, `rest` `null`) that serves the page under `src/kartograf/gui/web/` and the server's `/api/v1`
   on 127.0.0.1 in one process. The page is ES modules without a build step (DEV-15.1), in Polish (DEV-15.2), the
   kit files of Nogat 1.3.0 copied byte for byte with their commit recorded (DEV-15.6): `<nogat-command-form>`,
   `<nogat-basemaps>` with the shared catalogue (DEV-15.15), `<nogat-sources>`, `<nogat-app-menu>` and the terms of a
   public GUI (DEV-15.7, DEV-15.8); MapLibre GL JS vendored with its licence. It finds its API base as its tool's
   entry in `/api/v1/server` of its origin, so the same files run alone and behind Latarnik. The first version
   offers `elevation download` and `imagery download`, a rectangle (`--bbox … --bbox-crs EPSG:4326`) or a sheet;
   the plan before any output (the table of its files, sizes, sources and licences, their footprints on the map);
   then (a), (b) and (c), each with „Kopiuj” and „Zapisz” (`kartograf.sh`, `kartograf.ps1`). It has no field for a
   key and sends none.

**Where this ADR reads the plan differently:** `plan_max_units` answers H2's `validation_error`, not `429`; (b)
needs no plan, so `script generate` plans only for (c); the server's plans are detached plain plans (decision 4),
the plan's „target it owns and never shows”; the line of the form reaches the server through `commands format` and
`commands parse` (decision 6), which the plan did not name; the form reads the options' sections and Polish texts
from `commands schema --form` (J2), since one page of them would exceed DOC-1.7; the GUI's group `gui` and the
server's port 8065 are this ADR's.

**Consequences:** The catalog grows by `script generate`, `commands format`, `commands parse` and `gui serve`;
`AGENTS.md`, `llms.txt`, `_output_schema.py` and the tables of USAGE 8.3 and 8.6 are regenerated with each. New
documents: `kartograf-script/1`, `kartograf-command-line/1` (rows of `tests/contract/test_json_contract.py` and of
ARCHITECTURE 3.5). The deviation DEV-12.4 to DEV-12.9 of `CLAUDE.md` narrows to the CLMS Auth Proxy once the server
logs; SCOPE's „REST API server” (1.0+) and „web GUI = Archiwista” lines change; the registry's `interfaces.rest`
and the service `kartograf-server` stop being planned with the release that brings them (Nogat N2). Decisions 1 to 9
are implemented on `feat/gui` in slices: the form's fields (1), the plan (3, 4; step K2), the script (5; K3), the
server (2, 6 to 8; K4) and the GUI (9; K5); Latarnik's L1 and Archiwista's A1 follow in their repositories.

**Erratum 1 (2026-11-25, step K2, the coordinator's decision on its first open point):** decision 3 puts in
`fetch.sha256` the SHA-256 the registry pins (CAMELS-PL), but the files of a CAMELS-PL release are members read out
of its ZIP by range requests: `built`, as every file no URL serves alone, so their `fetch` is `null` and no pinned
SHA-256 reached a plan. They stay `built` and carry no `fetch.sha256`; the `sha256` of a `fetch` is for a file
downloaded whole whose SHA-256 the registry pins (none yet). The planned file names the pinned archive and its
SHA-256 instead: since the item's `source` is the registry key that `sources` is built from (decision 3), they go
into an additive key of the item, `archive` (`{url, size_bytes, member, sha256}`: the ZIP of the release and its
size, the path of the member in it and the SHA-256 of its bytes, as the registry pins them; `null` for every other
file), in store and plain plans alike and with no request (B2). (c) leaves these files out (`built`), so the
provider lines of decision 5 never reach its `ATTRIBUTION.txt`: it holds the registry's `license.attribution` of the
sources of the files it downloads.

**Erratum 2 (2026-11-25, step K2, the coordinator's decision on its second open point):** a plain check reads no
ATOM feed and B2 forbids a request for one, so in a plain or detached plan the file of an ATOM feed (GUGiK NMT
100 m, the national files of ČÚZK) had a `fetch` without a URL and (c) could not download it. A plain or detached
check now reads the feed the local metadata cache already holds, with no request, so B2 holds: `resolve_atom_file`
also stores the file it picks from a dataset feed (`atom_cache`, under a key of its own), and a plain plan names the
URL and the length of that file while it is younger than the TTL of the cache (7 days; in refresh mode too, since
the plan judges no version by it). Without such a feed in the cache the item keeps `fetch {url: null}` and has
`fetch_reason` `feed_not_cached`, a third reason beside `credentials` and `built` and the only one that comes with a
`fetch` (the file is the bytes at a URL; the plan cannot name it). (c) leaves such a file out with that reason; (b),
or a store check or a run of the same request on that machine first, gets it. The server's detached plans read the
server's cache the same way. `cache stats` counts these entries with the feed indexes (`atom_feeds`, „ATOM feed
entries”).

**Amendment 1 (2026-11-25, the coordinator's decision on the language of a plan's notices):** The plan the page
shows (`POST <group>/download?check=true`) is a JSON document, English by AGI-9.2 and ADR-053 decision 4, so its
notices reached a Polish page in English (the LAZ notice „skipped 21 LAZ tiles - the area is covered by newer
tiles …”), and the page could not render them again: a notice carries no key and no values. `Accept-Language`
translates only the problem documents (decision 7). Each notice of a JSON document now also carries the optional
`i18n`, its message in each other language of the catalog, `{"pl": "…"}`, with the Polish letters (ADR-053
amendment 1): `Notice` writes it when its message is a catalog message. `message` stays the English text, so the
document stays English for an agent, and the field only adds to the schemas `/1` (the notice of the vendored
`result-1.schema.json` allows it); it is in every document and envelope alike, the `--json` of the CLI, the
results of the MCP tools and the answers of the server. A notice read back from a document (`UpdatePlan.from_dict`)
keeps its English message only, as `ok` is computed and not read. The page's plan (`plan.js`) shows a notice's
`i18n` in the page's language when it is there, else its `message`.
