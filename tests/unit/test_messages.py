"""Message catalog: both languages of every entry, every call site, no stray Polish."""

import ast
import copy
import pickle
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

import kartograf
from kartograf import messages
from kartograf.exceptions import ValidationError
from kartograf.messages import (
    DEFAULT_LANG,
    LANGS,
    Message,
    Text,
    catalogs,
    localize,
    message,
    placeholders,
    plural_forms,
    reason,
    valid_key,
)

SRC = Path(kartograf.__file__).parent
# Polish diacritics, or words that no English text uses. The texts of this package
# are Polish without diacritics (ADR-044, rule Z5), so the words are the ASCII ones.
# Domain names that are identifiers (powiat, godlo, arkusz_200k) are not in the list.
POLISH = re.compile(
    "[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]"
    r"|\b(?:nie|brak|albo|lub|oraz|jest|dla|musi|musza|gdy|jesli|tylko|przez|bez|przy"
    r"|czy|moze|mozna|jako|ani|tez|oba|byl\w*|zostal\w*|powinn\w+|wiecej|mniej|spoza"
    r"|zamiast|wylacznie|lezy|nalezy|wymaga\w*|wymagan\w+|oczekiwano|otrzymano|podano"
    r"|podaj\w*|uzyj\w*|pobierz|pobran\w+|pobiera\w*|pobranie|sprawdz\w*|wypisz|wykonaj"
    r"|porownaj|domyslnie|nieznan\w+|nieprawidlow\w+|niepoprawn\w+|nieudan\w+"
    r"|niedostepn\w+|dostepn\w+|dozwolon\w+|pominiet\w+|pominieto|brakuj\w+|ustaw\w*"
    r"|obsluguj\w+|przecina\w*|dalsze|wartosc\w*|zrodl\w+|magazyn\w*|plik\w*|katalog\w*"
    r"|warstw\w+|zakres\w*|opcj\w+|zmienn\w+|wersj\w+|zapis\w*|dane|danych|blad\w*"
    r"|obszar\w*|arkusz(?:a|e|y|u|em|ami|ach)?|kafel|kafle|kafli|kafla|paczk\w+"
    r"|wycink\w+|serwer\w*|tresc\w*|wydani\w+|wariant\w*|rozmiar\w*|odpowiedz\w*"
    r"|usluga|uslugi|wynik\w*|zadanie|zadania|roku|sciezk\w+"
    r"|uklad(?:u|zie|y|ow|em|ach)?|komunikat\w*|komend\w+|nazwa|nazwy|nazwe|eksport\w*"
    r"|nieobslug\w+|obslugiwan\w+|obiekt\w*|identyfikator\w*|odczytal\w*|rzucil\w*"
    r"|wyjat\w+|strona|strony|stron|juz|daja|rozn\w+|odrzucon\w+|kandydat\w+"
    r"|przypiet\w+|kolumn\w+|liczb\w*|napis\w*|list[ay]|zawsze|nigdy"
    r"|inn(?:y|a|e|ego|ym|ych))\b"
    r"|(?-i:\bGodl[ao]\b)",
    re.IGNORECASE,
)
# Polish words that are data, not text: a header cell, the value of a flag (NIE = no),
# the names of the contour formats of the GUGiK sheet index, compared with what the
# service sent, and the field ``uklad`` of the sidecars written before ADR-031.
DOMAIN = frozenset({"god\u0142o", "NIE", "Warstwice DXF", "Warstwice DGN", "uklad"})
# A name or a path is data too: no space, and an underscore, a slash or a CamelCase
# join (the layer, field and path names of the GUGiK services, ``zrodlo_danych``).
NAME = re.compile(r"[\w./-]*(?:[_/]|[a-z][A-Z])[\w./-]*")
# Areas whose texts are one wording in every language: legal formulas that files
# persist, so a file does not depend on the language of its writer.
_SAME_AREAS = ("legal.",)
SCOPES = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
# The generated registry of the Nogat standard carries the Polish titles of its codes.
GENERATED = frozenset({"_errors.py"})
PLURAL = re.compile(r"\{\w+:plural\([^|(){}]+(?:\|[^|(){}]+){1,2}\)\}")

# Files that still hold Polish string literals outside the catalog. One comment line
# names an area, so the commit that migrates an area touches only its own lines.
# A file leaves the set as soon as its last Polish literal does (checked below).
_PENDING = frozenset(
    {
        # Root modules: documents, MCP server, store read API, notices.
        "notices.py",
        # Downloads.
        "download/area.py",
        "download/arguments.py",
        "download/availability.py",
        "download/campaigns.py",
        "download/collections.py",
        "download/cutout.py",
        "download/cz_contours.py",
        "download/cz_cutout.py",
        "download/cz_laz.py",
        "download/cz_orto.py",
        "download/cz_sheets.py",
        "download/data.py",
        "download/fetch.py",
        "download/laz.py",
        "download/links.py",
        "download/manager.py",
        "download/options.py",
        "download/orto_cutout.py",
        "download/plan.py",
        "download/storage.py",
        "download/versions.py",
        # Projects.
        "project/commands.py",
        "project/manifest.py",
        "project/operations.py",
    }
)


def is_polish(value: str) -> bool:
    """Whether a string literal is Polish text: not a domain token, a name or a URL."""
    return (
        POLISH.search(value) is not None
        and value not in DOMAIN
        and NAME.fullmatch(value) is None
        and not value.startswith(("http://", "https://"))
    )


def sources() -> Iterator[tuple[str, ast.Module]]:
    """Every module of the package outside the catalogs, parsed."""
    for path in sorted(SRC.rglob("*.py")):
        name = path.relative_to(SRC).as_posix()
        if not name.startswith("messages/") and name not in GENERATED:
            yield name, ast.parse(path.read_text(encoding="utf-8"))


def entries() -> list[tuple[str, Text]]:
    return [
        (f"{area}.{name}", text)
        for area, catalog in catalogs().items()
        for name, text in catalog.items()
    ]


def string_values(tree: ast.AST) -> Iterator[ast.Constant]:
    """String constants that are not docstrings."""
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, SCOPES) and node.body and isinstance(node.body[0], ast.Expr)
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            yield node


def message_calls() -> Iterator[tuple[str, ast.Call]]:
    for name, tree in sources():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "message"
            ):
                yield name, node


# --------------------------------------------------------------------------
# The catalogs
# --------------------------------------------------------------------------


def test_every_entry_has_both_languages_with_the_same_placeholders():
    problems = []
    for key, text in entries():
        if not valid_key(key):
            problems.append(f"{key}: not <area>.<name> in snake_case")
        for lang in LANGS:
            if not getattr(text, lang).strip():
                problems.append(f"{key}: empty {lang} text")
            if not getattr(text, lang).isascii():
                problems.append(f"{key}: the {lang} text is not ASCII")
        try:
            english, polish = placeholders(text.en), placeholders(text.pl)
        except ValueError as exc:
            problems.append(f"{key}: {exc}")
            continue
        if english != polish:
            problems.append(
                f"{key}: placeholders {sorted(english)} != {sorted(polish)}"
            )
        if "lang" in english:
            problems.append(f"{key}: a placeholder is called lang")
        if (
            text.en == text.pl
            and not key.startswith(_SAME_AREAS)
            and re.search(r"[^\W\d_]", re.sub(r"\{[^}]*\}", " ", text.en))
        ):
            problems.append(f"{key}: the Polish text is the English one")
        for template in (text.en, text.pl):
            if template.count("plural(") != len(PLURAL.findall(template)):
                problems.append(f"{key}: a plural spec is not plural(a|b[|c])")
    assert not problems, "\n".join(problems)


def test_every_call_names_an_entry_and_gives_exactly_its_placeholders():
    known = dict(entries())
    problems = []
    for name, call in message_calls():
        where = f"{name}:{call.lineno}"
        first = call.args[0] if call.args else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue  # a key chosen at run time, e.g. from a table
        if len(call.args) > 2:
            problems.append(f"{where}: positional arguments after the key and lang")
        if first.value not in known:
            problems.append(f"{where}: unknown key {first.value!r}")
            continue
        if any(keyword.arg is None for keyword in call.keywords):
            continue
        given = {keyword.arg for keyword in call.keywords} - {"lang"}
        wanted = placeholders(known[first.value].en)
        if given != wanted:
            problems.append(f"{where}: {first.value} wants {sorted(wanted)}")
    assert not problems, "\n".join(problems)


def test_no_entry_is_unused_and_no_key_like_literal_is_misspelled():
    literals = {
        node.value
        for _, tree in sources()
        for node in string_values(tree)
        if valid_key(node.value)
    }
    known = {key for key, _ in entries()}
    areas = set(catalogs())
    unused = sorted(known - literals)
    misspelled = sorted(
        value
        for value in literals - known
        if value.split(".")[0] in areas and value.rsplit(".", 1)[-1] not in {"py", "md"}
    )
    assert not unused, f"entries nobody uses: {unused}"
    assert not misspelled, f"literals that look like keys of a catalog: {misspelled}"


def test_polish_literals_stay_only_in_the_catalog_and_the_pending_files():
    found = {
        name
        for name, tree in sources()
        if any(is_polish(node.value) for node in string_values(tree))
    }
    assert found - _PENDING == set(), "a Polish text belongs in kartograf.messages"
    assert _PENDING - found == set(), "no Polish literal left: drop the file"


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def test_a_message_is_english_by_default_and_remembers_its_key_and_values():
    text = message("errors.io_error_hint", path="/data/a")

    assert DEFAULT_LANG == "en"
    assert isinstance(text, str)
    assert text == "Check the path and the permissions: /data/a"
    assert (text.key, text.lang, dict(text.params)) == (
        "errors.io_error_hint",
        "en",
        {"path": "/data/a"},
    )


def test_localized_renders_the_same_key_and_values_in_the_other_language():
    text = message("errors.allowed_values", flag="--product", values="nmt, laz")

    polish = text.localized("pl")

    assert polish == "Dozwolone wartosci --product: nmt, laz."
    assert polish.lang == "pl"
    assert polish.localized("en") == text
    assert text.localized("en") is text


def test_a_message_among_the_values_is_rendered_in_the_language_of_its_parent(
    monkeypatch,
):
    nested = message("errors.interrupted")
    monkeypatch.setattr(
        messages,
        "_catalog",
        lambda area: (
            {"wrap": Text("Stopped: {why}", "Zatrzymano: {why}")}
            if area == "x"
            else messages.importlib.import_module(f"kartograf.messages.{area}").MESSAGES
        ),
    )
    text = message("x.wrap", why=nested)

    assert text == "Stopped: interrupted (Ctrl-C)"
    assert text.localized("pl") == "Zatrzymano: przerwano (Ctrl-C)"


def test_operations_on_a_message_give_plain_text_but_copies_keep_it_translatable():
    text = message("errors.cache_default_hint")

    assert type(f"{text}!") is str
    for clone in (
        copy.deepcopy(text),
        pickle.loads(pickle.dumps(text)),
        pickle.loads(pickle.dumps(text.localized("pl"))),
    ):
        assert isinstance(clone, Message)
        assert clone.key == text.key
        assert clone.localized("pl") == "Wyczysc cache: kartograf cache clear"


def test_reason_keeps_the_message_of_an_exception_translatable_and_stringifies_others():
    nested = message("errors.interrupted")

    assert reason(ValueError(nested)) is nested
    assert reason(ValidationError(nested)) is nested
    assert reason(OSError(2, "No such file")) == "[Errno 2] No such file"
    assert type(reason(ValueError("plain"))) is str
    assert ValidationError(nested).localized("pl") == "przerwano (Ctrl-C)"
    assert ValidationError("plain").localized("pl") == "plain"


def test_localize_changes_only_catalog_messages():
    assert localize(message("errors.interrupted"), "pl") == "przerwano (Ctrl-C)"
    assert localize("przerwano (Ctrl-C)", "en") == "przerwano (Ctrl-C)"
    assert localize("plain text", "pl") == "plain text"


def test_a_counted_noun_takes_its_form_from_the_count_in_each_language(monkeypatch):
    monkeypatch.setattr(
        messages,
        "_catalog",
        lambda area: {
            "files": Text(
                "{n} {n:plural(file|files)}", "{n} {n:plural(plik|pliki|plikow)}"
            )
        },
    )

    english = [str(message("x.files", n=n)) for n in (0, 1, 2, 5)]
    polish = [str(message("x.files", "pl", n=n)) for n in (0, 1, 2, 5, 12, 22, 112)]

    assert english == ["0 files", "1 file", "2 files", "5 files"]
    assert polish == [
        "0 plikow",
        "1 plik",
        "2 pliki",
        "5 plikow",
        "12 plikow",
        "22 pliki",
        "112 plikow",
    ]
    with pytest.raises(ValueError, match="integer"):
        plural_forms("3", ("file", "files"))
    with pytest.raises(ValueError, match="two or three"):
        plural_forms(3, ("file",))


def test_a_list_of_messages_is_joined_and_each_item_follows_the_language_of_the_text(
    monkeypatch,
):
    monkeypatch.setattr(
        messages,
        "_catalog",
        lambda area: (
            {
                "list": Text("Problems: {items:join}", "Problemy: {items:join}"),
                "semi": Text("{items:join(; )}", "{items:join(; )}"),
            }
            if area == "x"
            else messages.importlib.import_module(f"kartograf.messages.{area}").MESSAGES
        ),
    )
    items = [message("errors.interrupted"), "plain", message("errors.terminated")]

    text = message("x.list", items=items)

    assert text == "Problems: interrupted (Ctrl-C), plain, terminated (SIGTERM)"
    assert (
        text.localized("pl")
        == "Problemy: przerwano (Ctrl-C), plain, przerwano (SIGTERM)"
    )
    assert message("x.semi", items=tuple(items[:2])) == "interrupted (Ctrl-C); plain"
    assert placeholders("{items:join(; )} {n:plural(a|b)}") == {"items", "n"}


def test_a_skipped_placeholder_is_given_but_only_the_other_language_prints_it(
    monkeypatch,
):
    monkeypatch.setattr(
        messages,
        "_catalog",
        lambda area: {"help": Text("Product.{choices:skip}", "Produkt: {choices}")},
    )

    english = message("x.help", choices="nmt, nmpt")

    assert english == "Product."
    assert english.localized("pl") == "Produkt: nmt, nmpt"
    assert placeholders("Product.{choices:skip}") == {"choices"}
    with pytest.raises(KeyError):
        message("x.help")


def test_the_error_document_is_english_unless_a_person_asks_for_polish():
    from kartograf.error_report import error_report

    exc = ValidationError("m", option="vertical_crs", allowed=("EVRF2007", "KRON86"))

    assert error_report(KeyboardInterrupt()).message == "interrupted (Ctrl-C)"
    assert error_report(exc).hint == "Allowed values of vertical_crs: EVRF2007, KRON86."
    polish = error_report(KeyboardInterrupt(), lang="pl")
    assert polish.message == "przerwano (Ctrl-C)"
    assert polish.title != error_report(KeyboardInterrupt()).title
    assert (
        error_report(exc, lang="pl").hint
        == "Dozwolone wartosci vertical_crs: EVRF2007, KRON86."
    )


def test_a_notice_is_rendered_again_in_the_language_asked_for():
    from kartograf.notices import Notice

    notice = Notice("info", "demo", message("errors.interrupted"))

    assert notice.localized("pl").message == "przerwano (Ctrl-C)"
    assert Notice("info", "demo", "plain").localized("pl").message == "plain"


def test_the_language_of_a_command_line_is_the_flag_then_the_settings(monkeypatch):
    from kartograf.cli._language import language_of
    from kartograf.config import human_language

    assert language_of(["sheet", "parse", "X"]) == "pl"
    assert language_of(["sheet", "parse", "X", "--lang", "en"]) == "en"
    assert language_of(["sheet", "--lang=en", "parse"]) == "en"
    assert language_of(["sheet", "--lang", "xx"]) == "pl"  # the parser refuses it
    monkeypatch.setenv("KARTOGRAF_LANG", "en")
    assert human_language() == "en"
    assert human_language("pl") == "pl"
    monkeypatch.setenv("KARTOGRAF_LANG", "de")  # invalid: check_config reports it
    assert human_language() == "pl"


def test_a_wrong_language_flag_is_a_usage_error_and_the_flag_is_on_every_command():
    from kartograf.catalog.commands import declared
    from kartograf.cli.commands import main

    assert all(
        any(p.name == "lang" and p.argument is None for p in c.params)
        for c in declared().commands
    )
    assert main(["sheet", "parse", "N-34-130-D", "--lang", "xx", "--json"]) == 2


def test_a_wrong_key_or_language_is_a_program_error():
    with pytest.raises(KeyError):
        message("errors.no_such_message")
    with pytest.raises(KeyError):
        message("no_such_area.title")
    with pytest.raises(KeyError):
        message("errors")
    with pytest.raises(ValueError, match="allowed"):
        message("errors.interrupted", "de")
    with pytest.raises(ValueError):
        placeholders("{0}")
    with pytest.raises(ValueError):
        placeholders("{value.name}")
    assert placeholders("{a} {b!r:>5} {{literal}} {n:plural(a|b)}") == {"a", "b", "n"}
