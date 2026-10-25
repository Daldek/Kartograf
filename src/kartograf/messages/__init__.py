"""
Message catalog: every text for a person has an English default and a Polish variant.

Machine output is English (AGI-9.2): the message and the hint of an error, the text
of a notice, the texts of a result envelope and everything the MCP server says. The
Polish variants serve human-readable output (the CLI help, its status lines and its
``Error:`` line when ``--lang pl`` or ``KARTOGRAF_LANG=pl`` asks for them, which is
the default of a person at a terminal) and live next to the English text, so a text
and its translation are edited together (DEV-2.3). Polish texts are ASCII (ADR-044,
rule Z5).

A catalog is the module ``kartograf.messages.<area>``; its mapping ``MESSAGES``
holds a `Text` per name. The key of a message is ``<area>.<name>`` in snake_case
(``errors.interrupted``). `message` renders a key with the values of its
placeholders and returns a `Message`: the text as a ``str`` that also remembers
its key and values, so an adapter can render the same message again in the
language of its caller (`Message.localized`, `localize`) instead of parsing text.

A template is ``str.format`` text with named placeholders; a counted noun is
written ``{count} {count:plural(file|files)}`` (two forms: one and other) or
``{count:plural(plik|pliki|plikow)}`` (three forms: one, few and many, as Polish
needs them), so a text and its plural forms stay in one entry per language.

Raise sites and notices call `message` with the key as a literal and one keyword
per placeholder; ``tests/unit/test_messages.py`` checks every call against its
catalog entry (the key exists and the keywords are the placeholders), both
languages of every entry and the absence of Polish literals outside this package.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
import string
from collections.abc import Mapping, Sequence
from functools import cache
from types import MappingProxyType
from typing import Any, Literal, NamedTuple, cast

__all__ = [
    "DEFAULT_LANG",
    "LANGS",
    "Lang",
    "Message",
    "Text",
    "catalogs",
    "localize",
    "message",
    "placeholders",
    "plural_forms",
    "reason",
    "valid_key",
]

Lang = Literal["en", "pl"]
LANGS: tuple[Lang, ...] = ("en", "pl")
"""The languages of the catalogs, the default first."""
DEFAULT_LANG: Lang = "en"
"""Language of machine output and of every text that nobody asked to translate."""

_KEY = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+")
_AREA = re.compile(r"[a-z][a-z0-9_]*")
_PLURAL = re.compile(r"plural\(([^|()]+(?:\|[^|()]+){1,2})\)")


class Text(NamedTuple):
    """
    One catalog entry: the English default and its Polish variant.

    Attributes
    ----------
    en : str
        English template, ``str.format`` syntax with named placeholders
        (``{name}``); a brace that is text is written ``{{`` or ``}}``.
    pl : str
        Polish template (ASCII) with exactly the placeholders of ``en``.
    """

    en: str
    pl: str


class Message(str):
    """
    A catalog text in one language that remembers its key and placeholder values.

    It is a ``str`` (the rendered text), so it can be compared, joined,
    serialised and passed wherever text is expected. Operations that build
    another string from it (``+``, an f-string, ``str.join``) give a plain
    ``str`` in the language of this message; pass a `Message` as a value of a
    placeholder of another message to keep it translatable.

    Attributes
    ----------
    key : str
        Catalog key ``<area>.<name>``.
    params : Mapping[str, object]
        The values of the placeholders (a `Message` among them is rendered again
        with its parent).
    lang : {"en", "pl"}
        Language of the text.
    """

    __slots__ = ("key", "lang", "params")

    key: str
    params: Mapping[str, object]
    lang: Lang

    def __new__(
        cls, text: str, key: str, params: Mapping[str, object], lang: Lang
    ) -> Message:
        """Wrap the rendered ``text`` of ``key`` in ``lang``."""
        instance = super().__new__(cls, text)
        instance.key = key
        instance.params = MappingProxyType(dict(params))
        instance.lang = lang
        return instance

    def __reduce__(self) -> tuple[Any, ...]:
        """Pickle and copy a message through its key, so it renders anew."""
        return (_restore, (self.key, self.lang, dict(self.params)))

    def localized(self, lang: Lang) -> Message:
        """
        Render the message again in ``lang``.

        Parameters
        ----------
        lang : {"en", "pl"}
            Target language.

        Returns
        -------
        Message
            The same key with the same values in ``lang`` (this message when it
            already is in ``lang``); a `Message` among the values is rendered
            in ``lang`` too.
        """
        if lang == self.lang:
            return self
        return message(self.key, lang, **self.params)


def _restore(key: str, lang: Lang, params: dict[str, object]) -> Message:
    return message(key, lang, **params)


def plural_forms(count: object, forms: Sequence[str]) -> str:
    """
    Choose the form of a counted noun.

    Parameters
    ----------
    count : int
        The number of things.
    forms : sequence of str
        Two forms (one, other: English) or three (one, few, many: Polish).

    Returns
    -------
    str
        With three forms: the first for 1, the second for a count that ends in 2-4
        and is not 12-14, the third for any other. With two: the first for 1, the
        second otherwise.

    Raises
    ------
    ValueError
        If ``count`` is not an integer or ``forms`` has another length.
    """
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError(f"A counted noun needs an integer, not {count!r}")
    if len(forms) == 2:
        return forms[0] if count == 1 else forms[1]
    if len(forms) != 3:
        raise ValueError(f"A counted noun has two or three forms: {forms!r}")
    if count == 1:
        return forms[0]
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return forms[1]
    return forms[2]


class _Formatter(string.Formatter):
    """``str.format`` plus the specs ``plural(a|b)`` and ``plural(a|b|c)``."""

    def format_field(self, value: Any, format_spec: str) -> str:
        found = _PLURAL.fullmatch(format_spec)
        if found is not None:
            return plural_forms(value, found.group(1).split("|"))
        return str(super().format_field(value, format_spec))


_FORMATTER = _Formatter()


@cache
def _catalog(area: str) -> Mapping[str, Text]:
    if _AREA.fullmatch(area) is None:
        raise KeyError(f"Not a message area: {area!r}")
    try:
        module = importlib.import_module(f"{__name__}.{area}")
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.{area}":
            raise
        raise KeyError(f"No message catalog for the area {area!r}") from None
    return cast("Mapping[str, Text]", module.MESSAGES)


def message(key: str, /, lang: Lang = DEFAULT_LANG, **params: object) -> Message:
    """
    Render the catalog message ``key`` in ``lang``.

    Parameters
    ----------
    key : str
        ``<area>.<name>`` of an entry of the catalog ``kartograf.messages.<area>``.
    lang : {"en", "pl"}, optional
        Language of the text; English by default, because machine output is
        English (AGI-9.2) and an adapter translates a message only for a
        caller who asked for another language.
    **params : object
        Values of the placeholders of the template.

    Returns
    -------
    Message
        The text with its key and values.

    Raises
    ------
    KeyError
        If the area or the name is not in the catalogs (a program error).
    ValueError
        If ``lang`` is not a catalog language.
    """
    area, _, name = key.partition(".")
    try:
        text = _catalog(area)[name]
    except KeyError:
        raise KeyError(f"Unknown message key {key!r}") from None
    if lang not in LANGS:
        raise ValueError(f"Unknown message language {lang!r}; allowed: {LANGS}")
    template = text.pl if lang == "pl" else text.en
    values = {
        name: value.localized(lang) if isinstance(value, Message) else value
        for name, value in params.items()
    }
    return Message(_FORMATTER.vformat(template, (), values), key, values, lang)


def localize(text: str, lang: Lang) -> str:
    """
    Return ``text`` in ``lang`` when it is a catalog message.

    Parameters
    ----------
    text : str
        A `Message`, or any other string (a foreign error text, a name).
    lang : {"en", "pl"}
        Target language.

    Returns
    -------
    str
        The message rendered in ``lang`` as a plain string (a final text, which
        a later conversion must not render again); another string unchanged.
    """
    return str(text.localized(lang)) if isinstance(text, Message) else text


def placeholders(template: str) -> frozenset[str]:
    """
    Names of the placeholders of a catalog template.

    Parameters
    ----------
    template : str
        ``str.format`` template.

    Returns
    -------
    frozenset of str
        The field names, without attribute access, indexes, conversions and
        format specifications.

    Raises
    ------
    ValueError
        If the template is malformed or a field is not a plain name.
    """
    names = set()
    for _, field, _, _ in string.Formatter().parse(template):
        if field is None:
            continue
        if not field.isidentifier():
            raise ValueError(f"Placeholder {field!r} is not a plain name: {template!r}")
        names.add(field)
    return frozenset(names)


def reason(exc: BaseException, /) -> str:
    """
    Text of an exception for use as a value inside another message.

    Parameters
    ----------
    exc : BaseException
        A caught exception.

    Returns
    -------
    str
        The `Message` the exception was raised with (a `KartografError` or an
        internal ``ValueError`` that carries a catalog text), so a message that
        embeds it stays translatable; ``str(exc)`` for any other exception, whose
        text is the foreign (English) text of the library that raised it.
    """
    first = exc.args[0] if len(exc.args) == 1 else None
    return first if isinstance(first, Message) else str(exc)


@cache
def catalogs() -> Mapping[str, Mapping[str, Text]]:
    """
    Load every catalog of the package.

    Returns
    -------
    Mapping of str to Mapping of str to Text
        The entries of each area by area name; for tests and tools that
        check or export the catalogs.
    """
    areas = sorted(
        module.name
        for module in pkgutil.iter_modules(__path__)
        if not module.name.startswith("_")
    )
    return MappingProxyType({area: _catalog(area) for area in areas})


def valid_key(key: str) -> bool:
    """Whether ``key`` has the form ``<area>.<name>`` in snake_case."""
    return _KEY.fullmatch(key) is not None
