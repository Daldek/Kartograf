# ADR-052: Command catalog documents and the MCP server on the Nogat agent interface

**Date:** 2026-10-24
**Status:** Accepted — amended by ADR-054 (the options `output_dir` and `root`, `check` instead of
`check_updates`, `store init`); partly superseded by ADR-057 (decision 9: the family `project`, the
hidden project tools and the paths nested in `project add`; erratum 3); erratum 1: the command layer
drives every command (AGI-2.1, decision 6); erratum 2: every example is the line `format_command`
writes; erratum 3: `project add` gives `add_project_task` the library arguments of its task.
The catalog documents (decisions 1 to 8), the MCP rebuild (decision 9) and the guide for agents
(decision 10) are implemented.

**Context:** The Nogat standard 2.1 asks every tool for a command catalog as the document
`<tool>-commands/1` (AGI-2.4), for `list_commands()` and `command_schema(command)` in the
public API (AGI-2.1), for MCP tools named by the `operation_id` `<tool>_<group>_<verb>`
(AGI-5.2) and for English texts with the Polish ones next to them (AGI-9.1). Until now
Kartograf published `kartograf-catalog/1` (Polish, one document with views, about 300,000
characters for the whole catalog) and 29 MCP tools named after functions (`get_catalog`,
`elevation_download`, `check_updates`). 0.8.0 is untagged, so the answer changes without a
migration (ECO-020).

**Options considered:**
- Keep `kartograf-catalog/1` and add `commands-1` beside it: two catalogs that drift (AGI-1.1).
- One `commands-1` document with every command: the schema requires options, rules, examples,
  errors and `i18n.pl` per command, so the whole catalog is about 400,000 characters, far over
  the page budget of DOC-1.7.
- A list of commands and the schema of one command (chosen), as in IMGWTools and Hydrolog.

**Decision:**
1. **Two documents.** `kartograf-command-list/1` (`tool`, `version`, `groups` with the product
   names, `commands` with `name`, `operation_id`, `summary`, `families`, `read_only`, `check`)
   and `kartograf-commands/1` (Nogat `commands-1`, vendored in `schemas/nogat/`) with the one
   command that `command_schema` was asked for. A contract test validates the schema of every
   command and the budget: 20,000 characters of compact JSON per page (DOC-1.7; the largest is
   `elevation download` with about 16,000; the CLI prints the indented envelope).
2. **Library and CLI.** `list_commands()`, `command_schema(command)` (the name or the
   `operation_id`; an unknown or missing command is `validation_error` with `details.option`
   `command` and `details.allowed`), `kartograf commands list` and `kartograf commands schema
   --command`. `get_catalog`, `data_commands`, `Catalog`, `CommandInfo`, `ParamInfo` and
   `kartograf-catalog/1` are removed without aliases (Retman and Archiwista migrate).
3. **The declarations are the one source** (the decisions of step d1b): the English text is
   authored in the declarations and the Polish text sits next to it in `*_pl` fields (what
   `--help` and the text of the CLI say); the document carries the Polish texts of a command in
   `i18n.pl` only, not those of every option (budget); the allowed values get their meaning from
   `catalog/meanings.py` (strict: a new registry value without a meaning fails a test), the
   excerpts of the results from `catalog/excerpts.py`; English descriptions do not list registry
   values.
4. **Options.** An option is a parameter that has an argument of the library function, plus
   `check_updates` of a command with a check; the flags only the CLI has (`--json`, `--quiet`,
   `--upgrade`, `--force`) and the constant argument of `<group> list-sources` are not options.
   Every `one_of` constraint of the catalog chooses the area, so it is the option group `area`
   (the sentence "Give exactly one of ..." is added to the description of each member); the
   other constraints stay in the option descriptions. A value per country is typed `string`
   and the description names the object `{pl, cz}`.
5. **Effects.** `read_only` unless the command writes the store, a project or the cache;
   `writes` is `delete` for a destructive command and `add` for the others (a store never
   overwrites a version; `replace` arrives with the plain output of the data-output change).
   `check` is the command itself with the option `check_updates` (it becomes `check` with the
   data-output change, Z7).
6. **Gap to AGI-2.1, kept on purpose.** `validate_command`, `check_command` and `run_command`
   keep `(command, options, *, output_dir, ...)` and the twelve data commands (the keys of
   `kartograf.project.commands.COMMANDS`); AGI-2.1 asks `**options` and every command. The
   options of a data command are the JSON object of `tasks[].options` of a project, the run
   options (`update`, `plan`, `workers`, `summary`, `cache`, `on_progress`) are not task
   options, and the commands that need no store are the library functions named by `function`.
   A generic driver reads `command_schema(name)` and calls that function. The data-output
   change decides the store argument; revisit then.
7. **Tables.** The exit code and error code tables and the list of schemas are no longer part
   of the catalog: the tables of `docs/USAGE.md` 9.3 are generated from
   `kartograf.error_report` and the registry is vendored.
8. **Hints.** The hint of a usage error is `Parametry komendy: kartograf commands schema
   --command "<id>"`.
9. **MCP.** One tool per command of the catalog that has a family (39), named by its
   `operation_id` `kartograf_<group>_<verb>` (at most 48 characters, in the order of the
   catalog). The old names (`elevation_download`, `parse_sheet`, `find_sheets`, `list_sources` and
   `list_layers` with a `group` argument, `commands_list`, `get_catalog`) and the tools
   `check_updates` and `project_check_updates` are gone without aliases: the check is the option
   `check_updates` of each tool that has a plan (it becomes `check` with the data-output change,
   Z7); `<group> list-sources` and `<group> list-layers` are one tool per group whose `group`
   the tool fixes. The families are `discovery`, `availability`, `data`, `project`, `store` and
   `core` (the ten tools of the main tasks: `commands list`, `commands schema`, `sheet find`,
   `elevation availability`, `elevation download`, `imagery download`, `landcover download`,
   `soil download`, `soil hsg`, `store overview`); the family `check` is gone.

   *The tools* come from the declarations alone (`catalog/tools.py`; `Command.tool` and the
   `_BRIEF` tables are removed): the description is the summary, the description and the rules
   (at most 600 characters), every property has the description, the `enum` values, the
   bounds, the default and the examples of its option; the meaning of an allowed value stays in
   `kartograf_commands_schema` (listing it in every tool doubles the list), a value per country
   is `anyOf` a string or `{pl, cz}`, `one_of` is a sentence of the descriptions (clients
   reject `oneOf` at the top level of a schema) and `bbox` needs `bbox_crs` by
   `dependentRequired`. The annotations are `title` and all four hints, always set (a client
   takes an unset `destructiveHint` as true), derived from `effects` and from the mode of the
   server; `kartograf_commands_list` and `kartograf_commands_schema` carry
   `_meta["anthropic/alwaysLoad"]`; `outputSchema` is `result-1` made self-contained and kept as
   data (`scripts/generate_output_schema.py`, a contract test: the module equals the generator
   and decides like the vendored schema).

   *The mode* is read only by default (AGI-1.3, AGI-5.8). `--allow-writes` needs `--allow-dir`
   (usage error, exit code 2). Without it a tool that writes and has a check is its plan-only
   variant (no `update`, `plan`, `workers` or `summary`, `check_updates` fixed to `true`,
   `readOnlyHint: true`), and the three that write without a check (`project init`, `project add`,
   `project remove`) are not offered; an option of a run, `check_updates: false` and a call of a
   hidden tool answer `forbidden`. A path outside `--allow-dir` is `forbidden` too (it was
   `validation_error`), also a path nested in the options of `project add`; a server without
   `--allow-dir` still reads any absolute path. `ForbiddenError` (`forbidden`, 12; `option`,
   `path`, `allowed`) and `MissingDependencyError` (`missing_dependency`, 6; the missing `mcp`
   extra, hint `uv add "kartograf[mcp]"`, the error document as the last line of stderr) are
   raised by the MCP server only; they have no `reason`, the arguments of the call tell the
   case. `--lang pl|en` is validated and reported in the start line; the server answers in
   English whatever it is (AGI-9.2), so it changes nothing.

   *The texts* of the MCP layer (instructions, descriptions, its own messages) are English; the
   instructions are built from the names of the catalog and the mode (`build_instructions`, about
   2,300 characters of the 4,096 allowed). The messages of the library and the hints that
   `error_report` composes stay Polish until the message catalogue (PROGRESS, Next item 25), so
   an invalid value has an English message and a Polish hint for now.

   *The budget.* The 30,000 characters of `tools/list` that ADR-046 (D22) set no longer hold: the
   descriptions of the catalog and the `outputSchema` make the list about 207,000 characters of
   compact JSON for the 39 tools (87,000 without the `outputSchema`), 188,000 (77,000) for the
   36 of a server that does not write and 64,000 (34,000) for `--tools core`. The standard
   limits the description (600), the instructions (4,096) and the page of a result (20,000), not
   the list; a client that loads every definition should start with `--tools core`. The gate
   test of AGI-5.13 starts the server over stdio with the SDK client: names, annotations with
   `title`, schemas and `outputSchema`, descriptions, instructions and page, a cold start with
   `tools/list` under 5 seconds (about 1.4 seconds measured), one read-only call, one
   validation error with `isError`, the code and the hint (the SDK client validates every
   non-error result against the `outputSchema`).

   *Known gap.* `project download`, `project status` and `project verify` read the store path
   from the project manifest, and `--allow-dir` checks the project directory, not that path.

10. **The guide for agents (AGI section 8).** `kartograf commands guide --format
    agents|llms|agents-md-block` and the library function `agent_guide(format=)` (the document
    `AgentGuide` = `kartograf-guide/1` with `format` and `text`, both exported) render
    `AGENTS.md`, `llms.txt` and the compact block of AGI-8.2, in English whatever the setting
    `lang` (AGI-9.2); the command is offline and read only and has no MCP tool.

    *The templates* are hand-written Markdown in `src/kartograf/_data/agents/` (`agents.md`,
    `llms.md`, `agents-md-block.md`, packaged by `package-data`). A marker
    `<!-- kartograf:NAME -->` is replaced by a block that `kartograf.guide` builds from the
    catalog and the error registry: the group names, one line per command with its
    `operation_id` (or "no MCP tool"), the table of every registry code with its exit code and
    what an agent does about it (a code without advice stops the generator), the rules, the
    typical flows and the call of the library. The text depends only on the installed package
    (no date, version or local path), so the files `AGENTS.md` and `llms.txt` of the
    repository are the output of the command written to a file, and a contract test compares
    them byte for byte; they are regenerated with the catalog, not edited.

    *No stale example.* Every command line of a flow or of the block is read by the parser of
    the CLI and, for a data command, by `validate_command` while the guide is rendered; the
    rules name their options and commands as `{opt:NAME}` and `{cmd:NAME}`, which are looked up
    in the catalog; the call of the library is checked against its signature. A renamed option
    or command stops the generator with a `ValueError`, so the data-output change (`--output`,
    `--check-updates`) cannot leave a wrong line in the guide: it regenerates the guide or the
    test fails.

    *The budgets* of DOC-1.7 are checked by the contract test: `AGENTS.md` 200 lines and
    16 KiB (165 lines and 15.8 KB now, the sections of DOC-4.2 and the last line "Developing
    this repository? Read CLAUDE.md."), `llms.txt` 8,000 characters before its first link
    list (the layout of DOC-5.1; its links are raw links to files of the repository, DOC-5.2),
    the block 60 lines.

    *The block* (AGI-8.2). `--inject FILE` is an option of the CLI only: the library function
    returns the text and writes no file, and `kartograf.guide.inject_block(existing, block)`
    (not in `__all__`) is the text part. The block between `<!-- BEGIN kartograf -->` and
    `<!-- END kartograf -->` replaces the old one in the file or is appended after a blank
    line; the file is written through a temporary file and a rename, so repeating the command
    changes nothing. `--inject` needs `--format agents-md-block` (`validation_error`).

    *Open.* `kartograf mcp` (AGI-3.8) is not added: `kartograf-mcp` stays the entry point of
    the server. The flows use today's option names (`--output`, `--check-updates`).

**Consequences:** A consumer reads the options of a data command from `command_schema`; the task
options are its options except the run options `output_dir`, `update`, `plan`, `workers`,
`summary` and `check_updates` (the `task` flag of the old document is not published). The error
code table is read from the registry. `kartograf commands list` takes no argument. The
repository files `AGENTS.md` and `llms.txt` change whenever the catalog, the error registry or
a template does; the contract test says so until they are regenerated (USAGE 9.7).

**Erratum 1 (2026-10-25, AGI-2.1; ADR-054, decision 14):** Decision 6, the gap to AGI-2.1, is closed
in part. `parse_command`, `validate_command`, `format_command`, `run_command` and `check_command` take
every command of the catalog (45), by its name or its `operation_id`, not the twelve data commands
only, and know no command by name: the function, its arguments, the required options, the allowed
values, the bounds, the rules among the options and the `check_*` twin come from the declaration
(`Command.call_options`, `function`, `check_function`; `kartograf.catalog.arguments.check_call`). The
twelve data commands keep the validation of their own function. A read-only command returns its
document in the envelope, `store init` writes the marker, and `check_command("store init")` is its plan
(`check_store`, `kartograf-plan/1`: the marker as one position of the track `store`; a root that is a
`conflict` is listed and the plan is `ok`, as in a data command; any other refusal is raised): the
command has a `check` now, so `kartograf_store_init` is a plan on a server that does not write (37
tools). `project add` is the call with the options `command` and `options`, which `parse_command` reads
from, and `format_command` writes as, the words after the task name. A command without a `check`
answers `check_command` with `validation_error`, `details.reason` `no_check` (as Hydrolog and Retman
do; the catalog says `check: null`). What stays as decided: the calling convention
`(command, options, *, ...)`, with the targets (`root`, `output_dir`) and the options of a run
(`update`, `plan`, `workers`, `summary`) by name and not `**options` (the options of a call are the
JSON object of `tasks[].options` and of an MCP tool), and `validate_command` returns nothing and fills
no default (the functions apply them). The MCP server keeps its own glue between a tool call and the
functions; `tests/integration/test_commands_catalog.py` compares the layer with the envelope of the
CLI for every command that runs offline.

**Erratum 2 (2026-10-25, AGI-2.1; request of Archiwista):** Every example of the catalog is canonical:
the `call` of an example in `kartograf-commands/1` (the same line as the `--help` of the command and the
hints) is the line `format_command` writes for the call `parse_command` reads from it, the order of the
flags too, so a tool that exchanges command lines compares them as text. The flags of the data command
of a `project add` example are declared as words, so their order is the author's: the HSG task had
`--sheet` before `--depth`, and the parameters of `soil hsg` put `--depth` first. A contract test
(`tests/contract/test_commands_schema.py`) writes every example back and compares the text.

**Erratum 3 (2026-10-26, AGI-1.2; request of Archiwista):** the options of a `project add` call are the
JSON form of its task (erratum 1), and `add_project_task` takes library arguments (ADR-040), but
`run_command` and the MCP tool `kartograf_project_add` passed the options on unconverted: a box (`bbox`
with `bbox_crs`) passed `validate_command` and was then refused (`option 'bbox_crs' does not belong to
the task`), where `kartograf project add` converted it. The three now convert the options of the task
with one function, `kartograf.project.commands.task_arguments` (`convert_arguments` with the kinds of
the data command): the box becomes one `BBox`, a path a `Path`, a list a tuple, and the manifest holds
the same task from every interface (`tests/integration/test_commands_catalog.py` compares it with the
CLI, `tests/integration/test_mcp_server.py` the tool with `run_command`). Rejected: `add_project_task`
taking both forms (two forms of one argument), and the conversion in `convert_arguments` for the kind
`options` (the generic conversion would have to know the project commands, and `validate_command`
checks the carried command in the JSON form).
