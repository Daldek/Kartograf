# ADR-053: Message catalog and English machine output

**Date:** 2026-10-25
**Status:** Accepted. The catalog, the language switch of the CLI and the error document
(decisions 1 to 6) are implemented; the texts of the other modules move area by area
(decision 7). Amends ADR-037 (Z5, S6: the language of messages).

**Context:** AGI-9.2 makes every machine output English (`--json`, the error document on
the last line of stderr, MCP results, descriptions and instructions, `AGENTS.md`,
`llms.txt`) and leaves Polish to the human-readable output on request; DEV-2.3 keeps the
text for a person in translation resources, not inline. ADR-037 (Z5, S6) did the opposite:
help, CLI messages and the texts of `KartografError` were Polish ASCII, so an agent read
Polish in `message` and `hint` of every error and in every notice. About 780 `raise` sites,
114 `print` calls in `kartograf.cli`, the notices, the hints of `error_report` and the
`*_pl` texts of the command declarations carry such text. 0.8.0 is untagged, so the
change needs no migration (ECO-020). Options: (a) gettext with `.po` files; (b)
`locales/pl.toml` keyed by the English sentence; (c) Python catalogs keyed by English ids
with both texts side by side (chosen, as in IMGWTools ADR-006); (d) English literals at the
raise sites and a Polish dictionary keyed by the sentence.

**Decisions:**

1. **Catalog.** The package `kartograf.messages`; one module per area
   (`messages/<area>.py`) with `MESSAGES: dict[str, Text]`; `Text(en, pl)`, English first;
   the key is `<area>.<name>` in snake_case; placeholders are `str.format` fields with
   plain names (a brace in the text is `{{`). A text and its translation are edited
   together. The Polish texts stay ASCII (ADR-044, Z5), checked by the guard test.
2. **`Message`.** `message(key, lang="en", **values)` renders an entry as a `Message`: a
   `str` that remembers its key, values and language. `Message.localized(lang)` renders it
   again (a `Message` among the values too), `localize(text, lang)` gives a plain `str`, and
   `reason(exc)` gives the catalog message of a caught exception so that a message that
   embeds it stays translatable. An f-string, `+` or `join` of a message is plain text:
   composition happens inside a template and a message is passed as a value.
3. **Counted nouns.** A template writes a counted noun as `{n} {n:plural(file|files)}`
   (two forms: one, other) or `{n:plural(plik|pliki|plikow)}` (three forms: one, few, many,
   as Polish needs them); `message` formats with a `string.Formatter` that knows this spec.
   It replaces `notices.count_text` and its noun tables, which only Polish could use.
   A list of messages or names is written `{items:join}` (joined with `, `) or
   `{items:join(; )}`; a `Message` among the items is rendered in the language of its
   parent, so a list of fragments (the problems of a sheet code) stays translatable.
4. **Where a text is rendered.** The raise site and the notice give English (a `Message`).
   `KartografError.localized(lang)` renders the text of an exception, `Notice.localized(lang)`
   the text of a notice, `error_report(exc, lang=)` the title, message and hint of the error
   document (English by default; the CLI asks for the language of a person only for the
   `Error:` line of the text mode). The last line of stderr, the `--json` document, the MCP
   server and the guides are always English.
5. **Language of a person (AGI-3.4, AGI-9.2, DEV-18.1).** Every command has the CLI-only
   option `--lang pl|en` (declared once, `catalog/shared.py::LANG`, added to each command by
   `catalog/commands.declared`; not an option of the library or of an MCP tool), then
   `KARTOGRAF_LANG`, `NOGAT_LANG`, `[kartograf] lang`, `[nogat] lang`, then `pl`
   (`config.human_language`). `kartograf.cli._language` holds the language of the running
   line (`set_language` in `main`, `language()`, `localized(text)`) and reads it from the
   tokens before the parse (`language_of`), so even a mistake of the line is reported in it.
   A log record that is a catalog message prints in that language, and in English in the
   `--json` mode.
6. **Guards.** `tests/unit/test_messages.py`: both languages of an entry are not empty, ASCII
   and have the same placeholders and plural specs; every `message("<literal>")` call names
   an entry and gives exactly its placeholders; no entry is unused; and no Polish literal is
   left outside the catalog and the files of `_PENDING`. During the migration `_PENDING`
   lists the files that still hold Polish, grouped by area; a file leaves it with its last
   Polish literal, and the set is deleted when it is empty. The generated registry
   (`_errors.py`, Polish titles with diacritics from the Nogat registry) is outside the scan.
7. **Migration by area.** One commit per group of files, gate green: the error document and
   the CLI language first (this decision), then the CLI texts, the command catalog (the
   `*_pl` texts of the declarations become `messages/commands.py` entries), the MCP server
   and the root modules, `core`, `transform`, `transport`, `providers`, `sources`,
   `project`, `landcover`, and `download`. A log record at WARNING or above is a
   user-visible line and becomes a catalog message; a lower one, a `ValueError` for a
   program error and an assertion text are plain English. Tests assert the key
   (`exc.args[0].key`), the English text or `lang="pl"`; they do not match Polish text.
   A sentence that wraps a caught error (`{reason}` of `reason(exc)`) moves in the same
   commit as the errors it wraps (a partial migration of the wrapper's file), so a Polish
   sentence never carries English text; CLI and API parity tests compare the CLI line with
   `error.localized("pl")`.
8. **Open.** The reasons of internal validators (a `ValueError` whose text another message
   embeds) are catalog messages where a person reads them and plain English where only a
   developer does; the help of `argparse` itself (`usage:`, `options:`) stays English.

**Consequences:** An agent reads the same English text whatever the setting of the user, and
a Polish user keeps Polish human output. A new text costs two strings in a catalog and one
`message("<key>", name=value)` call; the guard test fails on a missing translation, a wrong
placeholder, an unused entry and a stray Polish literal. A text assembled by an f-string at a
call site is not translatable and is a defect. Until an area is migrated its texts stay Polish
(see `_PENDING`); the language switch already works for the messages that are in the catalog.
