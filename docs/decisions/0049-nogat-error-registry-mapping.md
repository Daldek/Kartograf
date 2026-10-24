# ADR-049: Error codes and exit codes follow the Nogat registry

**Date:** 2026-10-24
**Status:** Accepted

**Context:** The Nogat standard 2.1 gives every tool the same error codes, exit codes and
error document, so that an agent or a script handles the errors of all tools alike (ERR §2,
ERR §4, AGI-4.3). Kartograf had its own codes (`invalid_input`, `no_coverage`, ...), the exit
codes 0/1/2/130/143 and a `kartograf-error/1` document with an `exception` field. The
release 0.8.0 is not tagged, so the change breaks consumers without a migration (ECO-020).

**Options considered:**
- Keep the project codes and document a mapping table: consumers would go on branching on
  codes that no other tool has.
- A new exception class per registry code: the classes carry meaning of their own
  (`except NoCoverageError` is used by consumers) and several of them share one code.
- Give each existing class a registry code and keep the old name as `details.reason`
  (chosen).

**Decision:**
1. Every `KartografError` class defines a registry `code` and, where the registry code is
   coarser than the class, a `reason`. The mapping is the table of ERR §4:
   `ValidationError` (`invalid_input`), `UsageError` (`usage`) and `ParseError`
   (`invalid_sheet_code`) are `validation_error` (2); `NoCoverageError` (`no_coverage`) and
   `YearRangeError` (`year_out_of_range`) are `no_data` (14); `DownloadError` is
   `source_unavailable` (5); `CacheError` is `store_unavailable` (`cache`, 8);
   `InvalidSidecarError` is `data_error` (`invalid_sidecar`, 7); `TransformError` is
   `calculation_error` (`transform_failed`, 13); `TransformUnavailableError` is `unsupported`
   (`transform_unavailable`, 15). The base `KartografError` is `internal_error` (1). The
   exit code is the registry's and is set when the class is created.
2. `error_report` builds the cases that have no class: `OSError` is `io_error` (9),
   `KeyboardInterrupt` is `cancelled` (130), `kartograf.interrupt.Terminated` is
   `terminated` (143), every other exception is `internal_error` (1).
3. The document `kartograf-error/1` follows AGI-4.3: `code`, `title` (the registry title),
   `message`, `hint`, `details` (always present, `reason` first), `exit_code`, `command`.
   `hint` and `command` are left out when empty. The `exception` field is dropped: the class
   name is an implementation detail, and `code` with `reason` identifies the failure.
4. The tables of the exit codes and of the errors are data of `kartograf.error_report`;
   the two tables of `docs/USAGE.md` 9.3 are generated from them and a contract test checks
   them.
5. A result with `ok: false` keeps exit code 1 until the result envelope replaces it with
   the outcomes 10 and 11 (a later step of the adoption).

**Consequences:** Consumers that read `code`, `exit_code` or the exit status of the CLI
change: Retman compares `err.code` with `no_coverage` (now `no_data` with `reason`
`no_coverage`, or `except NoCoverageError`); scripts that tested the exit status 1 for a
source failure now get 5, 14 or 15 as the error says. `except KartografError` and the class
hierarchy are unchanged. The messages and hints are the texts of the library as before.
