"""Help, examples and ``kartograf parse`` of the 0.8.0 UX review: what
``--help`` offers is what the commands accept, without network."""

import shlex
from collections.abc import Iterator

import pytest

from kartograf.cli._parser import _subparsers, create_parser
from kartograf.cli.commands import main


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Nothing below may reach a service."""

    def refuse(*args, **kwargs):
        raise AssertionError("request in a help or parse command")

    monkeypatch.setattr("requests.Session.request", refuse)


def _examples() -> Iterator[str]:
    """Example command lines of every ``epilog`` of the CLI."""

    def walk(parser):
        for line in (parser.epilog or "").splitlines():
            if line.startswith("  kartograf "):
                yield line.strip()
        commands = _subparsers(parser)
        for child in commands.choices.values() if commands is not None else ():
            yield from walk(child)

    return walk(create_parser())


_DATA_EXAMPLES = sorted(
    {
        example
        for example in _examples()
        if len(words := example.split()) > 2
        and words[2] in ("download", "hsg")
        and words[1] != "project"
    }
)


def test_every_download_command_has_examples():
    """Every ``download`` (and ``soil hsg``) of a data group shows examples."""
    groups = {example.split()[1] for example in _DATA_EXAMPLES}
    root = create_parser()
    top = _subparsers(root)
    assert top is not None
    with_download = {
        name
        for name, parser in top.choices.items()
        if (commands := _subparsers(parser)) is not None
        and "download" in commands.choices
        and name != "project"
    }
    assert groups == with_download


@pytest.mark.parametrize("example", _DATA_EXAMPLES)
def test_help_example_is_a_valid_task(example, tmp_path, capsys, monkeypatch):
    """A data example of ``--help`` passes the checks of ``project add``
    (all choices, no network): the store comes from the project, so
    ``--output`` and the display flag ``--summary`` are left out."""
    monkeypatch.chdir(tmp_path)
    assert main(["project", "init", "--output", "store"]) == 0
    argv = shlex.split(example)[1:]
    argv = [a for a in argv if a != "--summary"]
    at = argv.index("-o")
    del argv[at : at + 2]
    assert main(["project", "add", "t", *argv]) == 0, capsys.readouterr().err


@pytest.mark.parametrize(
    ("sheet", "lines"),
    [
        ("CTES96", ["Uklad:     SM5 (CZ)", "CRS:       EPSG:5514"]),
        (
            "302_5550",
            [
                "Uklad:     TM33 (CZ)",
                "CRS:       EPSG:3045",
                "Zasieg:    302000,5550000,304000,5552000",
            ],
        ),
        ("0510-D-11", ["(--sheet-system sjtsk)", "CRS:       EPSG:5514"]),
        ("NM-34-07-1-D-15", ["(--sheet-system etrs89)", "CRS:       EPSG:3045"]),
    ],
)
def test_parse_describes_cz_sheet_codes(sheet, lines, capsys):
    """CZ sheet codes accepted by ``--sheet`` are recognised by ``parse``."""
    assert main(["parse", sheet]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"Godlo:     {sheet}\n")
    assert all(line in out for line in lines)


def test_parse_cz_code_without_pl_hierarchy(capsys):
    """The PL sheet hierarchy flags are an input error for a CZ code."""
    assert main(["parse", "CTES96", "--children"]) == 1
    assert "tylko godel PL" in capsys.readouterr().err


def test_parse_off_grid_tm33_tile_and_unknown_code(capsys):
    assert main(["parse", "303_5550"]) == 1
    assert "TM33" in capsys.readouterr().err
    assert main(["parse", "XYZ"]) == 1
    assert "Godla CZ: SM5" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("group", "product", "country"),
    [("hydro", "network", "pl"), ("models3d", "buildings", "cz")],
)
def test_country_offers_only_countries_of_the_group(group, product, country, capsys):
    """``--country`` of a group without sources of a country rejects it."""
    with pytest.raises(SystemExit) as exc:
        main([group, "download", "--product", product, "--country", country])
    assert exc.value.code == 2
    assert f"invalid choice: '{country}'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "directory"),
    [
        (["hydro", "download", "--product", "network"], "hydro"),
        (["names", "download", "--product", "geographic"], "names"),
        (["landcover", "download", "--product", "bdot10k"], "landcover"),
        (["soil", "download"], "soil"),
    ],
)
def test_output_help_and_error_name_the_store_directory(argv, directory, capsys):
    """The ``--output`` help and the error of a missing ``--output`` name the
    same directory of the store - the one of the group, no placeholder."""
    assert main(argv) == 1
    error = capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([argv[0], argv[1], "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    expected = f"pliki w <KATALOG>/{directory}/..."
    assert expected in error
    assert f"Katalog magazynu (wymagany): {expected}" in help_text
