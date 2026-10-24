"""Z5: help, messages and input errors in Polish without diacritics (ASCII)."""

import argparse

import pytest

from kartograf import download_soil
from kartograf.cli._parser import create_parser
from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.data import download_data
from kartograf.exceptions import KartografError


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
        ["elevation", "download", "--product", "nmt", "--bbox", "1,2,3", "-o", "o"],
        "Nieprawidlowy",
    ),
    (["elevation", "download", "--product", "nmt", "-o", "o"], "Podaj"),
    (["landcover", "download", "-o", "o", "--teryt", "1465"], "wymagane"),
    (["landcover", "list-layers"], "wymagane"),
    (["imagery", "download", "--sheet", "X", "-o", "o"], "wymagane"),
    (["soil", "download", "--sheet", "N-34-130-D"], "wymagane"),
    (["soil", "hsg", "-o", "o"], "Podaj"),
    (["sheet", "parse", "Q-99"], "Nieprawidlowe"),
]


@pytest.mark.parametrize(("argv", "word"), _CLI_ERRORS)
def test_cli_error_paths_are_ascii_polish(argv, word, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and err.isascii() and word in err


def _library_errors():
    yield lambda: download_data(product="nmt", output_dir="o", sheet="X")
    yield lambda: download_data(product=None, output_dir="o", sheet="N-34-130-D")
    yield lambda: download_soil(
        output_dir="o",
        bbox=BBox(0, 0, 1, 1, "EPSG:2180"),
        property="x",
        depth="0-5cm",
        stat="mean",
        cache=False,
    )
    yield lambda: SheetParser("Q-99")
    yield lambda: SheetParser("N-34-130-D").get_all_descendants("1:3")


@pytest.mark.parametrize("call", list(_library_errors()))
def test_library_error_paths_are_ascii_polish(call, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(KartografError) as exc:
        call()
    text = str(exc.value)
    assert text.isascii(), text
    assert any(
        word in text.lower()
        for word in ("wymagane", "nieprawidlow", "nie ", "dostepne", "podaj")
    ), text
