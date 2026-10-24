# ADR-052: Command catalog documents and the MCP server on the Nogat agent interface

**Date:** 2026-10-24
**Status:** Accepted. The catalog documents (decisions 1 to 8) are implemented; the MCP
rebuild (decision 9) follows in the next step and extends this record.

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
9. **MCP (next step).** Tools `kartograf_<group>_<verb>` from the catalog, annotations with
   `title`, `outputSchema`, `--allow-writes` (needs `--allow-dir`), `forbidden` and
   `missing_dependency`, English instructions, `--lang` validated and reported only, the gate
   test of AGI-5.13. Until then the tool `get_catalog` is `commands_list` and
   `commands_schema`.

**Consequences:** A consumer reads the options of a data command from `command_schema`; the task
options are its options except the run options `output_dir`, `update`, `plan`, `workers`,
`summary` and `check_updates` (the `task` flag of the old document is not published). The error
code table is read from the registry. `kartograf commands list` takes no argument.
