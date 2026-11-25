"""Z5: help, messages and input errors in Polish, ASCII on the terminal.

The Polish texts of the catalog have their diacritics; the CLI prints them folded to
ASCII and the values they carry as they are (ADR-053 amendment 1).
"""

import argparse
import contextlib
import logging
import string
from functools import cache

import pytest

from kartograf import download_soil, messages
from kartograf.cli._parser import create_parser
from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.data import download_data
from kartograf.exceptions import KartografError
from kartograf.messages import Text, fold, message


def _all_parsers(parser: argparse.ArgumentParser):
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                yield from _all_parsers(sub)


def test_help_of_every_command_is_ascii():
    parsers = list(_all_parsers(create_parser()))
    # top, parse, cache x4 and the groups: elevation x3, imagery x3,
    # landcover x4, soil x5
    assert len(parsers) >= 21
    for parser in parsers:
        text = parser.format_help()
        assert text.isascii(), (parser.prog, [c for c in text if not c.isascii()])


# (argv, expected Polish word) - representative input errors of the CLI
_CLI_ERRORS = [
    (["elevation", "download", "--sheet", "X"], "wymagane"),
    (
        ["elevation", "download", "--product", "nmt", "--bbox", "1,2,3", "--root", "o"],
        "Nieprawidlowy",
    ),
    (["elevation", "download", "--product", "nmt", "--root", "o"], "Podaj"),
    (["landcover", "download", "--root", "o", "--teryt", "1465"], "wymagane"),
    (["landcover", "list-layers"], "wymagane"),
    (["imagery", "download", "--sheet", "X", "--root", "o"], "wymagane"),
    (["soil", "download", "--sheet", "N-34-130-D"], "wymagane"),
    (["soil", "hsg", "--root", "o"], "Podaj"),
    (["sheet", "parse", "Q-99"], "Nieprawidlowe"),
]


@pytest.mark.parametrize(("argv", "word"), _CLI_ERRORS)
def test_cli_error_paths_are_ascii_polish(argv, word, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and err.isascii() and word in err


def _library_errors():
    yield lambda: download_data(product="nmt", root="o", sheet="X")
    yield lambda: download_data(product=None, root="o", sheet="N-34-130-D")
    yield lambda: download_soil(
        root="o",
        bbox=BBox(0, 0, 1, 1, "EPSG:2180"),
        property="x",
        depth="0-5cm",
        stat="mean",
        cache=False,
    )
    yield lambda: SheetParser("Q-99")
    yield lambda: SheetParser("N-34-130-D").get_all_descendants("1:3")


@pytest.mark.parametrize("call", list(_library_errors()))
def test_library_error_paths_are_english_ascii_and_polish_on_request(
    call, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(KartografError) as exc:
        call()
    text = fold(exc.value.localized("pl"))
    assert str(exc.value).isascii() and text.isascii(), text
    assert any(
        word in text.lower()
        for word in ("wymagane", "nieprawidlow", "nie ", "dostepne", "podaj")
    ), text


_ACCENTS = str.maketrans("acelnoszACELNOSZ", "ąćęłńóśżĄĆĘŁŃÓŚŻ")


def _accented(template: str) -> str:
    """``template`` with each a, c, e, l, n, o, s and z of its text a Polish letter."""
    parts = []
    for text, field, spec, conversion in string.Formatter().parse(template):
        parts.append(text.translate(_ACCENTS).replace("{", "{{").replace("}", "}}"))
        if field is not None:
            parts.append(
                "{"
                + field
                + (f"!{conversion}" if conversion else "")
                + (f":{spec}" if spec else "")
                + "}"
            )
    return "".join(parts)


# Lines of the text mode whose output holds Polish texts of the catalog, with a word
# of them: the help, a description of a sheet, a table with its note, an error of the
# library (with a value outside ASCII that stays) and a usage error of the parser.
_TERMINAL_LINES = [
    (["elevation", "download", "--help"], "Przyklady"),
    (["sheet", "parse", "N-34-130-D", "--hierarchy"], "Godlo"),
    (["elevation", "list-sources"], "Zrodla"),
    (["elevation", "download", "--product", "nmt", "--root", "o"], "Podaj wybor"),
    (["sheet", "parse", "Q-99ł"], "Nieprawidlowe godlo: 'Q-99ł'"),
    (["elevation", "download", "--bogus"], "nieznana opcja"),
]


def _terminal(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    """What a person reads of ``argv`` in Polish, with a warning of the library."""
    with contextlib.suppress(SystemExit):  # --help ends the process, as in argparse
        main([*argv, "--lang", "pl"])
    logging.getLogger("kartograf.test").warning(message("errors.interrupted"))
    out, err = capsys.readouterr()
    return out + err


def test_the_terminal_reads_the_polish_catalog_folded_and_the_values_as_they_are(
    tmp_path, monkeypatch, capsys
):
    """Any Polish letter of the catalog reaches the terminal folded to ASCII: the
    help, the status lines, the log lines and the errors of the library and of the
    parser print the same text whether the catalog has diacritics or not."""
    monkeypatch.chdir(tmp_path)
    catalog = messages._catalog

    def polish(transform):
        return cache(
            lambda area: {
                name: Text(text.en, transform(text.pl))
                for name, text in catalog(area).items()
            }
        )

    monkeypatch.setattr(messages, "_catalog", polish(_accented))
    accented = [_terminal(argv, capsys) for argv, _ in _TERMINAL_LINES]
    monkeypatch.setattr(messages, "_catalog", polish(fold))
    folded = [_terminal(argv, capsys) for argv, _ in _TERMINAL_LINES]

    assert accented == folded
    for text, (argv, word) in zip(accented, _TERMINAL_LINES, strict=True):
        assert word in text and "Warning: przerwano (Ctrl-C)" in text, argv
        assert text.replace("ł", "").isascii(), argv  # only the value keeps its letter
