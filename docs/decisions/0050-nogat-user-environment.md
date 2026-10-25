# ADR-050: User environment: nogat.toml, variables, user directories and `config show`

**Date:** 2026-10-24
**Status:** Accepted — amended by ADR-054 (the default root is the target of a command without a target option)

**Context:** The Nogat standard 2.1 gives every tool one user environment (DEV-18, ECO-028): a
shared `nogat.toml`, the variables `<TOOL>_<KEY>` and `NOGAT_<KEY>`, a data and a cache
directory per user, credentials from the environment only, and `<tool> config show --json`.
Kartograf kept its metadata cache in the current directory (`<cwd>/.kartograf_cache.db`), the
MCP server used a second cache file of its own, `KARTOGRAF_DEBUG` was read in one place and
nothing reported the settings in force. The release 0.8.0 is not tagged, so the change breaks
the location of the cache without a migration (ECO-020); the cache holds lookups, never data.

**Options considered:**
- Read the file and the variables where they are needed: every module would repeat the order
  of the sources, and `config show` would copy the rules.
- Take `pydantic-settings` as IMGWTools does: a heavy dependency for five keys, and Kartograf
  has no `.env` file.
- One module `kartograf.config` with `tomllib` and `platformdirs`, the sources in one function
  (chosen, the design of `imgwtools._environment`).

**Decision:**
1. **Order (DEV-18.1).** A setting comes from the first of: the command-line option, the
   variable `KARTOGRAF_<KEY>`, `NOGAT_<KEY>` (only `data_dir`, `cache_dir`, `lang`), the table
   `[kartograf]` of `nogat.toml`, the table `[nogat]` (shared keys only), the default. An empty
   variable counts as unset. `nogat.toml` is in `platformdirs.user_config_path("nogat")` or at
   `NOGAT_CONFIG`; it is read with `tomllib`, its absence is no error, and Kartograf needs
   neither the `nogat` package nor a `.env` file. No key has a command-line option yet.
2. **Keys.** `root` (`KARTOGRAF_ROOT`, default `<data_dir>/kartograf`, DEV-19.2), `data_dir`,
   `cache_dir`, `lang` (`pl` or `en`, default `pl`) and `debug` (`KARTOGRAF_DEBUG`; it
   replaces the direct read in the CLI, and `0`, `false`, `no` and `off` now mean off). `root` is
   not a shared key. Until the data-output change the commands still take the store from
   `--output`: `root` is reported and nothing else. `lang` is validated and reported; the
   human-readable output stays Polish until the message catalogue lands (PROGRESS Next item 25).
3. **Unusable settings.** A file that cannot be read, is not UTF-8 text (the
   `UnicodeDecodeError` is caught), is not valid TOML, has a section that is not a table, or is
   named by `NOGAT_CONFIG` and missing, and a `lang` other than `pl` or `en`, are a `ConfigError`:
   `validation_error`, exit code 2, `details.reason` `invalid_config` (snake_case, as the error
   schema wants; the prose is in `message`), with `details.option`, `details.path` and for a
   value `details.value` and `details.allowed`. Every CLI command except `config show` and the
   start of the MCP server check the settings and stop with it; the library functions read the
   settings without validating, ignore an unusable file and use the defaults, so a broken file
   cannot stop a calculation that does not need it.
4. **Cache out of the current directory (DEV-18.2).** The default metadata cache is
   `<cache_dir>/kartograf/metadata.db` (`cache/defaults.py::default_cache_path`), the same file
   for the CLI, the library and the MCP server (`default_cache_file` delegates). The directory is
   made by the first write; a directory that cannot be made disables the cache with the usual
   warning, as an unwritable file does. The old `<cwd>/.kartograf_cache.db` is not read or
   moved.
5. **Credentials (DEV-18.4).** `CLMS_CREDENTIALS` comes from the environment only; `config show`
   says `present` or `missing`, and a credential key in `[kartograf]` is listed under
   `config_file.ignored`.
6. **`kartograf config show` (DEV-18.6).** Library function `get_config`, document
   `kartograf-config/1` in the shape of `imgw-config/1`: `config_file` (`path`, `source`,
   `exists`, `error`, `ignored`), `keys` (`value`, `source`, `name`, and `error` for a value that
   was dropped), `credentials`, `store` (`root`, `source`, `name`, `exists`, `size_bytes`; a
   hard-linked file is counted once). It works with a file that cannot be used. It is a command
   of the catalog (group `config`, a query) and has no MCP tool: it reports paths of the host
   and walks the store.
7. **Documentation (DEV-18.3, DEV-18.5).** `.env.example` and the README table list every
   variable; the README says how to back up a store (`rsync -aH`, hard links) and which data
   cannot be downloaded again. `platformdirs>=4` is a core dependency.

**Consequences:** A run no longer leaves `.kartograf_cache.db` in the working directory, and
`kartograf cache path` names the new file; tests of the library and the CLI isolate the user
environment (`tests/conftest.py::user_environment`). Consumers that read or deleted
`.kartograf_cache.db` (none is known) follow `get_cache_path()`. A machine with `NOGAT_LANG` or
`NOGAT_CACHE_DIR` set for another tool now configures Kartograf too, which is the point of the
shared keys; an invalid shared `lang` stops every Kartograf command until it is fixed.
