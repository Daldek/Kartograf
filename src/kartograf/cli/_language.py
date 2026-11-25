"""
The language of the human-readable output of the CLI (AGI-9.2, DEV-18.1).

Machine output is English whatever a person asked for: the ``--json`` document, the
error document on the last line of stderr and every text of the library that is a
catalog message of English default. The text for a person - the ``Error:`` line,
the ``Info:`` and ``Warning:`` lines, the status lines, the help - is rendered in
the language of ``--lang``, else of ``KARTOGRAF_LANG``, ``NOGAT_LANG`` and
``nogat.toml``, else Polish (``kartograf.config.human_language``).

``main`` sets the language once per command line (``set_language``); the modules of
the CLI read it (``language``) and render every catalog message they print with
``localized``: a text the library made, and ``localized(message("cli.<name>", ...))``
for a text of the CLI. A terminal reads ASCII whatever its code page, so
``localized`` folds the Polish letters of the catalog to ASCII (ADR-053 amendment 1).
"""

from collections.abc import Sequence

from kartograf.config import human_language
from kartograf.messages import Lang, localize, message

LANG_FLAG = "--lang"

_language: Lang = "pl"


def language() -> Lang:
    """Return the language of the output for people of the running command line."""
    return _language


def set_language(lang: Lang) -> None:
    """Set the language of the output for people (``main`` does it once per line)."""
    global _language
    _language = lang


def localized(text: str) -> str:
    """Return ``text`` for the terminal, in the language of the command line.

    A catalog message is rendered in that language with the Polish letters of its
    catalog texts folded to ASCII (``ą`` -> ``a``, ``ł`` -> ``l``) and its values (a
    path, the name of a unit) as they are; any other text (the text of a foreign
    exception, a name) is returned as it is.
    """
    return localize(text, _language, folded=True)


def yes_no(value: bool) -> str:
    """Return ``yes`` or ``no`` in the language of the command line."""
    if value:
        return localized(message("cli.yes"))
    return localized(message("cli.no"))


def language_of(argv: Sequence[str]) -> Lang:
    """Return the language a command line asks for, before it is parsed.

    The parser raises ``UsageError`` for a wrong command line in the language of the
    line, so the language is read from the tokens first (as ``json_mode`` reads
    ``--json``): ``--lang pl`` or ``--lang=pl``. A line without the flag, or with a
    value that is no language, has the language of the settings; the parser refuses
    the wrong value.
    """
    explicit: str | None = None
    for index, token in enumerate(argv):
        if token == LANG_FLAG and index + 1 < len(argv):
            explicit = argv[index + 1]
        elif token.startswith(LANG_FLAG + "="):
            explicit = token.split("=", 1)[1]
    return human_language(explicit)
