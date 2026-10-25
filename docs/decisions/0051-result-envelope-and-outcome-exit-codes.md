# ADR-051: Result envelope kartograf-result/1, outcome exit codes 10 and 11, error document on stderr

**Date:** 2026-10-24
**Status:** Accepted — amended by ADR-054 (`files[]` and `skipped[]` of the download reports)

**Context:** The Nogat standard 2.1 gives every tool one answer shape (AGI-4.2): the
envelope `<tool>-result/1` with `status` (`ok`, `partial`, `failed`), the domain document
as `result`, the outcome of every unit in `items` and the `notices`. A batch that finished
with failed units is an outcome with its own exit codes, 10 and 11 (ERR §1), and an error
is the document `<tool>-error/1` on the last line of stderr in both modes, with nothing on
stdout (AGI-3.2, AGI-3.3). Until now Kartograf printed the bare domain document, flagged a
failed unit with `ok: false` and exit code 1 (the code of `internal_error`), and put the
error document on stdout under `--json`. 0.8.0 is untagged, so the answer changes
without a migration (ECO-020).

**Options considered:**
- Keep the documents and add `status` to each: five reports, a plan, an availability report
  and two project documents would each carry the envelope keys, and the schema of the
  envelope (`schemas/nogat/result-1.schema.json`) could not be validated as one document.
- One envelope module that wraps the unchanged domain documents (chosen): the documents of
  ADR-046 keep their schemas and keys, the envelope is built from them in one place.

**Decision:**
1. **Module `kartograf.envelope`.** `CommandResult` is a `Document` (`kartograf-result/1`,
   generic in its `result`), `ResultItem` an entry of `items` (keys without a value are left
   out). `to_dict()` writes `result` with its own `schema`; `page` is not written until a
   command pages its result (`store entries` has no cursor yet). `wrap(command, document,
   check=)` builds it, `exit_code_of(document, check=)` is the exit code of the CLI.
2. **Status.** It follows the verdict `ok` of the domain document: `ok`; `partial` when
   `ok` is false and a unit succeeded; `failed` when `ok` is false and none did. The exit
   codes are `kartograf._errors.OUTCOMES` (0, 10, 11), now in the table of USAGE 9.3. A
   document with no verdict is `ok` with no items; a document with a verdict that has no
   reader in `envelope._READERS` is a `TypeError` (dispatch is by type, and a test checks that
   every document of the package with `ok` has a reader). `cancelled` is never produced: a
   cancelled command is the error `cancelled` (130).
3. **Units.** The five reports of `kartograf-download/1`: an ok unit per distinct
   `UnitFile.unit`; a failed unit per `UnitFailure` with its registry `code` and `reason`
   (`no_coverage` and `year_out_of_range` are `no_data`, `download` and `country` are
   `source_unavailable`); a planned position the source changed since the plan is
   `conflict`/`stale_plan`; a unit with a file and a failure is the failed item only. A plan:
   a unit per position (`check_failed` is `source_unavailable`/`check_failed`). Availability:
   a unit per checked country and one per country that could not be checked (the new key
   `failed`). `download_project`: a unit per task, with `TaskResult.code` and `.reason` set
   where the task fails (`data_error`/`corrupt_pin`, `conflict`/`geometry_changed`,
   `conflict`/`pin_mismatch`, `conflict`/`concurrent_change`, `data_error`/`not_pinnable`,
   `io_error`, the code of the first failed unit or of the `KartografError`). `project
   status`, `verify` and the check: a unit per task (a task with no pins fails `status` and
   `verify`, not a check; `missing` is `not_found`/`missing_file`, `corrupt` is
   `data_error`/`corrupt_file`, `check_failed` is `source_unavailable`). An `ok: false` with
   no failed unit gets one synthetic `internal_error` item (the schema wants one).
4. **A partial success that stays `ok`.** `--country auto` with one country down while the
   other succeeded is `ok: true` in the report (A3-2); its failed country is a notice, not an
   item, and the status is `ok`. Making it `partial` is a decision for the author (PROGRESS,
   open question about the same case in a project).
5. **CLI.** `emit_result(command, document, check=)` prints the envelope and returns 0, 10
   or 11; text mode returns the same codes. `emit_error` writes the document as the last line
   of stderr, compact and ASCII (`error_line`: a character outside ASCII is a JSON escape,
   because stderr has any encoding and an error must always be reported), stdout stays
   empty. In text mode the `Error:` line comes first; the parser of argparse prints the usage,
   its own line and then the document before it exits with 2; a call with no command prints
   the help and the document. Outcomes print no error document.
6. **Library and MCP.** `run_command` and `check_command` return `CommandResult`
   (`check_command(...).result` is the plan `run_command(plan=)` takes). Every MCP tool
   returns the envelope as structured content and as compact text; only an error document is
   `isError` (AGI-5.7), the outcomes 10 and 11 are results.

**Consequences:** Consumers read the document of a command from `result` (Retman and
Archiwista read `run_command(...).result`), branch on `status` and the exit codes 10 and 11
instead of `ok` and 1, and read the error document from the last line of stderr instead of
stdout (and from `structuredContent` with `isError` in MCP). The documents of ADR-046 are
unchanged except for the notice key (`text` is `message`), `TaskResult.code` and `.reason`,
and `failed` in `kartograf-availability/1`. `notices` are in the envelope and in the result
(the same list). AGI-2.1 asks `run`, `check` and `validate` for every command; they stay
data commands only (the twelve of `kartograf.commands`), a known gap for the catalog step.
