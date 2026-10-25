"""The CLI parser built from the declarations of the catalog (spec 8.2): what a
parameter becomes in argparse, the usage error mode and the texts of the
parser's messages."""

import argparse
import shlex

import pytest

from kartograf._version import build_version
from kartograf.catalog.cliparser import (
    _subparsers,
    build_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.catalog.commands import declared
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.kinds import parse_per_country
from kartograf.catalog.shared import OUTPUT_TITLE, SELECTION_TITLE
from kartograf.catalog.spec import Command, Example, Group, Param
from kartograf.exceptions import UsageError, ValidationError


def _data(command_id: str, *params: Param, **fields) -> Command:
    values = {
        "id": command_id,
        "summary": f"Summary {command_id}",
        "summary_pl": f"Podsumowanie {command_id}",
        "kind": "data",
        "function": "download_data",
        "result_schema": "kartograf-download/1",
        "params": params,
    }
    return Command(**{**values, **fields})


_PARAMS = (
    Param(
        "product",
        "str",
        "Produkt (wymagany): nmt, nmpt",
        allowed=lambda: ("nmt", "nmpt"),
        choices=True,
        required=True,
        section=SELECTION_TITLE,
        description_pl="Produkt (wymagany): nmt, nmpt",
    ),
    Param(
        "country",
        "str",
        "Kraj zrodla",
        allowed=("pl", "cz", "auto"),
        choices=True,
        normalize="lower",
        section=SELECTION_TITLE,
        description_pl="Kraj zrodla",
    ),
    Param(
        "sheet",
        "str",
        "Godlo arkusza",
        metavar="GODLO",
        normalize="strip",
        section=SELECTION_TITLE,
        description_pl="Godlo arkusza",
    ),
    Param(
        "bbox",
        "bbox",
        "Prostokat",
        metavar="BBOX",
        section=SELECTION_TITLE,
        description_pl="Prostokat",
    ),
    Param(
        "bbox_crs",
        "bbox_crs",
        "Uklad --bbox (domyslnie EPSG:2180)",
        allowed=("EPSG:2180", "EPSG:4326", "EPSG:5514"),
        choices=True,
        normalize="upper",
        cli_default="EPSG:2180",
        section=SELECTION_TITLE,
        description_pl="Uklad --bbox (domyslnie EPSG:2180)",
    ),
    Param(
        "resolution",
        "per_country",
        "Rozdzielczosc 100% siatki",
        short="-r",
        metavar="ROZDZIELCZOSC",
        section="Parametry produktu",
        description_pl="Rozdzielczosc 100% siatki",
    ),
    Param(
        "layers",
        "str_list",
        "Kody po przecinku",
        metavar="KODY",
        section="Parametry produktu",
        description_pl="Kody po przecinku",
    ),
    Param(
        "year",
        "int",
        "Rok",
        metavar="ROK",
        section="Parametry produktu",
        description_pl="Rok",
    ),
    Param(
        "cutout",
        "flag",
        "Wycinek",
        section="Parametry produktu",
        description_pl="Wycinek",
    ),
    Param(
        "root",
        "path",
        "Katalog magazynu (wymagany)",
        flag="--root",
        short="-o",
        dest="output",
        metavar="KATALOG",
        required=True,
        section=OUTPUT_TITLE,
        description_pl="Katalog magazynu (wymagany)",
    ),
    Param(
        "check_updates",
        "flag",
        "Sprawdz",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
        description_pl="Sprawdz",
    ),
    Param(
        "upgrade",
        "flag",
        "Pobierz nowsze",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
        description_pl="Pobierz nowsze",
    ),
    Param(
        "force",
        "flag",
        "Pobierz ponownie",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
        description_pl="Pobierz ponownie",
    ),
    Param(
        "update",
        "str",
        "Tryb",
        flag=None,
        allowed=("upgrade", "force"),
        description_pl="Tryb",
    ),
    Param(
        "plan",
        "plan",
        "Plan",
        metavar="PLIK",
        section=OUTPUT_TITLE,
        description_pl="Plan",
    ),
    Param(
        "workers",
        "int",
        "Liczba pobran",
        short="-w",
        metavar="N",
        default=4,
        section=OUTPUT_TITLE,
        description_pl="Liczba pobran",
    ),
    Param(
        "quiet",
        "flag",
        "Cicho",
        argument=None,
        short="-q",
        section=OUTPUT_TITLE,
        description_pl="Cicho",
    ),
)


def _declarations() -> tuple[tuple[Command, ...], tuple[Group, ...]]:
    commands = (
        _data(
            "elevation download",
            *_PARAMS,
            description="Fetch the data into the versioned store",
            description_pl="Pobierz dane do magazynu wersji",
            examples=(
                Example(
                    {"product": "nmt", "sheet": "N-34-130-D-d-2-4", "year": 2020},
                    title="Arkusz",
                    title_pl="Arkusz",
                ),
                Example({"product": "nmpt", "layers": ["A", "B"]}),
            ),
        ),
        _data(
            "elevation list-sources",
            kind="query",
            function="list_sources",
            result_schema="kartograf-sources/1",
            description="Wypisz zrodla",
        ),
        _data(
            "sheet parse",
            Param(
                "sheet",
                "str",
                "Godlo",
                metavar="GODLO",
                positional=True,
                description_pl="Godlo",
            ),
            Param(
                "hierarchy",
                "flag",
                "Pokaz hierarchie",
                description_pl="Pokaz hierarchie",
            ),
            kind="query",
            function="describe_sheet",
            result_schema="kartograf-sheet/1",
            description="Rozpoznaj godlo",
        ),
        _data(
            "cache stats",
            kind="query",
            function="get_cache_info",
            result_schema="kartograf-cache/1",
            description="Statystyki",
        ),
        _data(
            "project add",
            Param(
                "project_dir",
                "path",
                "Katalog",
                flag="--project",
                dest="project",
                default=None,
                cli_default=".",
                metavar="KATALOG",
                description_pl="Katalog",
            ),
            Param(
                "name",
                "str",
                "Nazwa",
                metavar="NAZWA",
                positional=True,
                description_pl="Nazwa",
            ),
            Param(
                "arguments",
                "str_list",
                "Komenda i opcje",
                metavar="<grupa> <komenda> [opcje]",
                positional=True,
                nargs="REMAINDER",
                description_pl="Komenda i opcje",
            ),
            kind="manage",
            function="add_project_task",
            result_schema="kartograf-project-state/1",
            description="Dodaj zadanie",
        ),
        _data(
            "project status",
            Param(
                "tasks",
                "str_list",
                "Zadania",
                metavar="NAZWA",
                positional=True,
                nargs="*",
                description_pl="Zadania",
            ),
            kind="query",
            function="get_project_status",
            result_schema="kartograf-project-check/1",
            description="Status",
        ),
        _data(
            "commands list",
            Param(
                "group",
                "str",
                "Grupa",
                metavar="GRUPA",
                positional=True,
                nargs="?",
                description_pl="Grupa",
            ),
            kind="query",
            function="list_commands",
            result_schema="kartograf-command-list/1",
            description="Katalog",
        ),
    )
    groups = (
        Group(
            "elevation",
            "Wysokosci",
            "Dane wysokosciowe",
            summary_pl="Wysokosci",
            description_pl="Dane wysokosciowe",
        ),
        Group(
            "project",
            "Projekt",
            "Manifest projektu",
            summary_pl="Projekt",
            description_pl="Manifest projektu",
        ),
        Group(
            "sheet",
            "Godla",
            "Godla arkuszy",
            summary_pl="Godla",
            description_pl="Godla arkuszy",
        ),
        Group(
            "cache",
            "Cache",
            "Cache metadanych",
            position=2,
            summary_pl="Cache",
            description_pl="Cache metadanych",
        ),
        Group(
            "commands",
            "Katalog",
            "Katalog komend",
            position=2,
            summary_pl="Katalog",
            description_pl="Katalog komend",
        ),
    )
    return commands, groups


def _parser(**options) -> argparse.ArgumentParser:
    commands, groups = _declarations()
    return build_parser(commands, groups, **options)


def _leaf(parser: argparse.ArgumentParser, *words: str) -> argparse.ArgumentParser:
    current = parser
    for word in words:
        action = _subparsers(current)
        assert action is not None
        current = action.choices[word]
    return current


def _action(parser: argparse.ArgumentParser, dest: str) -> argparse.Action:
    return next(a for a in parser._actions if a.dest == dest)


def test_actions_follow_params():
    leaf = _leaf(_parser(), "elevation", "download")

    product = _action(leaf, "product")
    assert product.option_strings == ["--product"]
    assert list(product.choices or ()) == ["nmt", "nmpt"]
    assert (product.default, product.required, product.type) == (None, False, None)
    assert product.help == "Produkt (wymagany): nmt, nmpt"

    output = _action(leaf, "output")  # dest of --root is "output", not root
    assert output.option_strings == ["--root", "-o"]
    assert (output.metavar, output.default, output.choices) == ("KATALOG", None, None)

    workers = _action(leaf, "workers")
    assert (workers.option_strings, workers.type, workers.default) == (
        ["--workers", "-w"],
        int,
        4,
    )
    layers = _action(leaf, "layers")
    assert layers.type.__name__ == "layer_codes"  # type: ignore[union-attr]
    assert _action(leaf, "year").type is int
    cutout = _action(leaf, "cutout")
    assert isinstance(cutout, argparse._StoreTrueAction)
    assert (cutout.default, cutout.nargs) == (False, 0)
    # a flag only of the API has no action; a bbox is read as text
    assert not [a for a in leaf._actions if a.dest == "update"]
    assert _action(leaf, "bbox").type is None
    crs = _action(leaf, "bbox_crs")
    assert crs.default == "EPSG:2180"  # the default of the flag, not of the API
    assert list(crs.choices or ()) == ["EPSG:2180", "EPSG:4326", "EPSG:5514"]


def test_choices_only_when_declared():
    leaf = _leaf(_parser(), "elevation", "download")

    assert _action(leaf, "resolution").choices is None
    assert _action(leaf, "country").choices is not None


def test_flags_are_never_required():
    parsed = _parser().parse_args(["elevation", "download"])

    assert parsed.product is None
    assert parsed.output is None
    assert parsed.workers == 4
    assert parsed.bbox_crs == "EPSG:2180"
    assert (parsed.cutout, parsed.quiet) == (False, False)


def test_positional_arguments_and_their_counts():
    parser = _parser()

    parse = parser.parse_args(["sheet", "parse", "N-34-130-D", "--hierarchy"])
    add = parser.parse_args(
        ["project", "add", "teren", "elevation", "download", "--product", "nmt"]
    )
    status = parser.parse_args(["project", "status", "a", "b"])
    nothing = parser.parse_args(["project", "status"])
    catalog = parser.parse_args(["commands", "list"])

    assert (parse.sheet, parse.hierarchy) == ("N-34-130-D", True)
    assert (add.name, add.arguments, add.project) == (
        "teren",
        ["elevation", "download", "--product", "nmt"],
        ".",
    )
    assert (status.tasks, nothing.tasks) == (["a", "b"], [])
    assert catalog.group is None


def test_normalize_lower_upper_strip():
    parsed = _parser().parse_args(
        [
            "elevation",
            "download",
            "--country",
            "PL",
            "--bbox-crs",
            "epsg:5514",
            "--sheet",
            "  N-34-130-D ",
        ]
    )

    assert (parsed.country, parsed.bbox_crs, parsed.sheet) == (
        "pl",
        "EPSG:5514",
        "N-34-130-D",
    )


def test_exclusive_group(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "400")
    parser = _parser()

    parsed = parser.parse_args(["elevation", "download", "--upgrade"])
    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["elevation", "download", "--check-updates", "--upgrade"])

    assert (parsed.upgrade, parsed.check_updates, parsed.force) == (True, False, False)
    assert exit_info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
    usage = _leaf(parser, "elevation", "download").format_usage()
    assert "[--check-updates | --upgrade | --force]" in usage


def test_sections_and_epilog_in_help():
    help_text = _leaf(_parser(), "elevation", "download").format_help()

    titles = [SELECTION_TITLE, "Parametry produktu", OUTPUT_TITLE]
    positions = [help_text.index(f"\n{title}:\n") for title in titles]
    assert positions == sorted(positions)
    assert "\nPrzyklady:\n" in help_text
    assert help_text.rstrip().endswith(
        "  kartograf elevation download --product nmpt --layers A,B -o ./data"
    )
    assert (
        "  kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--year 2020 -o ./data\n"
    ) in help_text
    assert "Pobierz dane do magazynu wersji" in help_text
    # a command without examples has no epilog
    assert (
        "Przyklady" not in _leaf(_parser(), "elevation", "list-sources").format_help()
    )


def test_percent_signs_of_a_description_are_escaped():
    leaf = _leaf(_parser(), "elevation", "download")

    assert "Rozdzielczosc 100% siatki" in leaf.format_help()


def test_usage_error_mode():
    parser = _parser(usage_errors=True)
    for argv, text in (
        (["elevation", "download", "--nope"], "--nope"),
        (["sheet", "parse"], "required: GODLO"),
        (["elevation", "download", "--product", "dem"], "invalid choice"),
        (["elevation", "download", "--workers", "x"], "invalid int value"),
        (["elevation", "download", "--check-updates", "--upgrade"], "not allowed"),
        (["nope"], "invalid choice"),
    ):
        with pytest.raises(UsageError) as error:
            parse_command_line(parser, argv)
        assert text in str(error.value)
        assert (error.value.code, error.value.reason) == ("validation_error", "usage")
        assert isinstance(error.value, ValidationError)


def test_default_mode_prints_usage_and_exits_with_2(capsys):
    parser = _parser()

    with pytest.raises(SystemExit) as exit_info:
        parse_command_line(parser, ["elevation", "download", "--product", "dem"])

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert error.startswith("usage: kartograf elevation download")
    assert "invalid choice: 'dem'" in error


def test_usage_error_mode_reaches_every_command_parser():
    parser = _parser(usage_errors=True)

    for words in (
        ("project", "add"),
        ("cache", "stats"),
        ("elevation", "list-sources"),
    ):
        with pytest.raises(UsageError):
            parser.parse_args([*words, "--nope"])


def test_negative_bbox_values_are_joined():
    parser = _parser()

    parsed = parse_command_line(
        parser,
        [
            "elevation",
            "download",
            "--bbox",
            "-447000,-1100000,-437000.5,-1090000",
            "--bbox-crs",
            "EPSG:5514",
        ],
    )

    assert parsed.bbox == "-447000,-1100000,-437000.5,-1090000"


def test_no_abbreviation_of_flags(capsys):
    parser = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["elevation", "download", "--out", "x"])

    assert "unrecognized arguments: --out" in capsys.readouterr().err


def test_leaf_parsers_carry_command_id_and_groups_carry_group_parser():
    parser = _parser()

    leaf = parser.parse_args(["elevation", "download"])
    root_leaf = parser.parse_args(["sheet", "parse", "N-34"])
    group = parser.parse_args(["elevation"])

    assert leaf._command_id == "elevation download"
    assert root_leaf._command_id == "sheet parse"
    assert not hasattr(group, "_command_id")
    assert group._group_parser is _leaf(parser, "elevation")
    assert group._group_parser.prog == "kartograf elevation"


def test_root_lists_commands_then_groups_by_position():
    parser = _parser()
    top = _subparsers(parser)
    assert top is not None

    # the groups by position and name
    assert list(top.choices) == [
        "elevation",
        "project",
        "sheet",
        "cache",
        "commands",
    ]


def test_group_without_command_name_lists_its_commands():
    group = _leaf(_parser(), "elevation")
    help_text = group.format_help()

    assert "KOMENDA" in help_text
    assert "download" in help_text and "list-sources" in help_text
    assert "Podsumowanie elevation download" in help_text


def test_command_names_come_from_the_ids():
    parser = _parser()

    assert list(_subparsers(_leaf(parser, "cache")).choices) == ["stats"]  # type: ignore[union-attr]


def test_removed_commands_name_their_replacement():
    elevation = (
        "kartograf elevation download (--product nmt, nmpt, laz) albo kartograf "
        "imagery download (--product orto)"
    )
    soil = (
        "kartograf soil hsg (grupy HSG) albo kartograf soil download "
        "(wlasciwosci SoilGrids)"
    )
    landcover = (
        "SoilGrids jest w grupie soil od 0.8.0 - uzyj kartograf soil download "
        "albo kartograf soil list-layers"
    )
    expected = {
        (): None,
        ("download",): f"komenda 'download' usunieta w 0.8.0 - uzyj {elevation}",
        ("soilgrids", "--property", "clay"): (
            f"komenda 'soilgrids' usunieta w 0.8.0 - uzyj {soil}"
        ),
        ("landcover", "download", "--product", "soilgrids"): landcover,
        ("landcover", "download", "--source", "soilgrids"): landcover,
        ("landcover", "list-layers", "-s", "soilgrids"): landcover,
        ("landcover", "download", "--product=bdot10k"): None,
        ("elevation", "download", "--product", "nmt"): None,
    }

    for argv, text in expected.items():
        assert removed_command_error(list(argv)) == text


@pytest.mark.parametrize(
    "argv",
    [
        ["elevation", "download", "--nope"],
        ["elevation", "download", "--teryt", "12"],
        ["elevation", "download", "extra"],
        ["project", "status", "--nope=1"],
    ],
)
def test_unknown_argument_text_names_the_commands_that_have_it(argv, capsys):
    parser = _parser()

    with pytest.raises(SystemExit) as exit_info:
        parse_command_line(parser, argv)

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "nieznan" in error
    assert f"Opcje: kartograf {argv[0]}" in error


def test_unknown_flag_owners_are_listed():
    parser = _parser(usage_errors=True)

    with pytest.raises(UsageError) as error:
        parse_command_line(parser, ["project", "status", "--hierarchy"])

    assert "nieznana opcja --hierarchy (maja ja: sheet parse)" in str(error.value)


def test_version_action_prints_version(capsys):
    parser = _parser()

    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"kartograf {build_version()}\n"


def test_help_wraps_paragraphs_and_keeps_example_lines(monkeypatch):
    monkeypatch.setenv("COLUMNS", "60")
    leaf = _leaf(_parser(), "elevation", "download")

    help_text = leaf.format_help()

    example = (
        "  kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--year 2020 -o ./data"
    )
    assert len(example) > 60
    assert example in help_text.splitlines()


# =============================================================================
# The examples of the declarations, read back by the parser
# =============================================================================

_DECLARED = declared()
_DATA_EXAMPLES = [
    (command, index)
    for command in _DECLARED.commands
    if command.project_task
    for index in range(len(command.examples))
]


def _options_of(command: Command, parsed: argparse.Namespace) -> dict:
    """The task options (JSON form of the manifest) a parsed line gives."""
    options: dict = {}
    for param in command.params:
        value = getattr(parsed, param.cli_dest, None) if param.task else None
        if value is None or value is False:
            continue
        if param.kind == "bbox":
            options["bbox"] = [float(v) for v in value.split(",")]
            options["bbox_crs"] = parsed.bbox_crs
        elif param.kind == "per_country":
            options[param.name] = parse_per_country(value, param.cli_flag or "")
        elif param.kind == "str_list":
            options[param.name] = list(value)
        elif param.kind != "bbox_crs":
            options[param.name] = value
    return options


@pytest.mark.parametrize(
    ("command", "index"),
    _DATA_EXAMPLES,
    ids=[f"{c.id}#{i}" for c, i in _DATA_EXAMPLES],
)
def test_example_command_lines_round_trip(command, index):
    parser = build_parser(_DECLARED.commands, _DECLARED.groups, usage_errors=True)
    example = command.examples[index]

    words = shlex.split(example_command_line(command, example))
    parsed = parse_command_line(parser, words[1:])

    assert words[:1] == ["kartograf"]
    assert parsed._command_id == command.id
    assert _options_of(command, parsed) == example.options
    assert parsed.root == "./data"


def test_example_command_lines_of_every_command_parse():
    parser = build_parser(_DECLARED.commands, _DECLARED.groups, usage_errors=True)

    for command in _DECLARED.commands:
        for example in command.examples:
            words = shlex.split(example_command_line(command, example))
            parsed = parse_command_line(parser, words[1:])
            assert parsed._command_id == command.id
