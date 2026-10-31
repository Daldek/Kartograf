# ADR-057: Projects move to Archiwista

**Date:** 2026-10-31
**Status:** Accepted (the author approved option B of the Nogat plan and its recommended answers
D1 to D7 on 2026-10-31); supersedes ADR-040; partly supersedes ADR-051 (decision 1: `check` of
`exit_code_of`; decision 3: the units of `download_project` and of the project checks) and ADR-052
(decision 9: the family `project`, the hidden project tools and the paths nested in `project add`;
erratum 3)
**Standard:** Nogat 2.1: HUB-5.2, DEV-17.4, DEV-19.18, REL-5.3, REL-5.4, ECO-020; plan
[`docs/plans/2026-10-31-archiwista-projects.md`](https://github.com/Daldek/Nogat/blob/main/docs/plans/2026-10-31-archiwista-projects.md)
of Nogat (step 2)

**Context:** A project records the work on one task: the area it covers, the store versions it uses,
the activity on it and the exports for further work. In 0.8.0-dev the notion was split in three:
Kartograf's `kartograf-project.json` (`kartograf-project/1`; `kartograf.project`, `cli/project_cmd.py`,
the catalog group `project`, about 3,000 lines), IMGWTools' `imgw-project.json` of the same shape, and
the project of Archiwista (owner, sharing, own data, snapshots, project jobs). Kartograf's model made a
pin the result of running its task's command: a pin existed only inside a task and only after a full
run, so data already in the store could be pinned only by adding a command whose run found it there
(the live run of 2026-10-15, scenario 2: three index requests, nothing downloaded). Neither producer
pinned a stored version as it is, and neither had a project area, an activity record or an export.
Projects were never released: the last tag is `v0.7.2` and projects are in the untagged 0.8.0, so a
removal breaks no released user (ECO-020).

**Options:**
- A) Keep the manifest; Archiwista shows one "Projekt" over both producers' manifests and asks each
  producer for a "pin what the store holds" operation. The split stays, and every new project feature
  crosses three repositories.
- B) Projects only in Archiwista; Kartograf keeps download, check, the store and its read API, and
  gains one read-only function that gives the command of a stored version (chosen).
- C) A shared project library imported by every tool: a new dependency between all tools for a
  notion only Archiwista presents.
- D) Release with the projects now and move them later: the release would publish an interface only
  to break it in the next one.

**Decision:** B, as a clean cutover: no aliases, no deprecated paths, no reader of old manifests.
1. **Removed.** The package `kartograf.project` (model, manifest, operations, the table of task
   commands), `cli/project_cmd.py`, the catalog group `project` (`init`, `add`, `remove`, `download`,
   `status`, `verify`), the MCP tools `kartograf_project_*` and the family `project`,
   `ProjectLockedError` (`project_locked`), `PROJECT_LOCK`, the notice `project_geometry_changed`, the
   documents `kartograf-project-state/1`, `kartograf-project-report/1` and `kartograf-project-check/1`,
   the project names of `kartograf.__all__`, `kartograf.testing.build_project` and the messages of the
   area `project`.
2. **What only projects needed goes with them.** In the catalog: `Param.task` and
   `Command.task_options` (for every data command they were the `call_options`),
   `Command.project_task` (exactly the commands of kind `data`), the kind `options`, the positional
   `REMAINDER`, the effect `project_write`; `parse_command(tasks=)` and the data command nested in a
   `project add` line; `options_to_json`, `options_from_json`, `check_options_json` and `base_dir` of
   `convert_arguments`; `check` of `outcome_of` and `exit_code_of` (only a project check read it);
   `EncodeContext.store` (the store of the pin paths); `ToolSpec.task_options` becomes
   `ToolSpec.data_options`.
3. **What stays, under its real name.** `validate_command`, `run_command` and `check_command` call a
   data command through the checks its function makes before the first request, the download and the
   `check_*` twin limited to the products of its group. That table was `kartograf.project.commands.COMMANDS`;
   it is not a project notion, so it moves to `kartograf.data_commands.DATA_COMMANDS` (`DataCommand`:
   `name`, `options`, `validate`, `download`, `check`) without the adapter of a result to the files a
   task pins. A new data command adds its declaration (kind `data`) and one entry there.
4. **No migration** (decision D4 of the plan): a `kartograf-project.json` of 0.8.0-dev is not read by
   any Kartograf function; Archiwista keeps projects in `archiwista-project.json`
   (`archiwista-project/1`) and pins any producer's stored versions there.
5. **The command of a stored file** (KB-6, `command_for_file`) is the one function the plan adds for
   Archiwista; it is decided below, in its own section.

**Consequences:** Kartograf only downloads data and keeps the versioned store; the store, the
sidecar, the read API and `kartograf.testing` (without project builders) are unchanged. Archiwista's
`ProjectActionAdapter` (`adapter/kartograf/actions.py`) loses its target and is replaced in the plan's
step 5; until then Archiwista keeps its pin of Kartograf. Reproducing a project with Kartograf's CLI
alone is no longer possible: Archiwista's export writes the command lines (`polecenia.sh`) and its
restore runs them. The MCP server offers no tool that writes without a check, so `hidden_tools` is empty
in every mode; the rule stays for a future command of that kind. `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`
(the spec of ADR-040) is superseded with it.

## KB-6: command of a stored file

The decision is recorded by the follow-up change that adds `command_for_file`.
