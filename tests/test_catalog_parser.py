"""The CLI parser built from the declarations of the catalog (spec 8.2): what a
parameter becomes in argparse, the usage error mode and the texts of the old
parser that survive the migration."""

import argparse
import shlex
from dataclasses import replace

import pytest

from kartograf._version import build_version
from kartograf.catalog.cliparser import (
    build_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.catalog.commands import declared
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.kinds import parse_per_country
from kartograf.catalog.shared import OUTPUT_TITLE, SELECTION_TITLE
from kartograf.catalog.spec import Command, Example, Group, Param
from kartograf.cli import _parser as old_parser
from kartograf.exceptions import UsageError, ValidationError


def _data(command_id: str, *params: Param, **fields) -> Command:
    values = {
        "id": command_id,
        "summary": f"Podsumowanie {command_id}",
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
    ),
    Param(
        "country",
        "str",
        "Kraj zrodla",
        allowed=("pl", "cz", "auto"),
        choices=True,
        normalize="lower",
        section=SELECTION_TITLE,
    ),
    Param(
        "sheet",
        "str",
        "Godlo arkusza",
        metavar="GODLO",
        normalize="strip",
        section=SELECTION_TITLE,
    ),
    Param("bbox", "bbox", "Prostokat", metavar="BBOX", section=SELECTION_TITLE),
    Param(
        "bbox_crs",
        "bbox_crs",
        "Uklad --bbox (domyslnie EPSG:2180)",
        allowed=("EPSG:2180", "EPSG:4326", "EPSG:5514"),
        choices=True,
        normalize="upper",
        cli_default="EPSG:2180",
        section=SELECTION_TITLE,
    ),
    Param(
        "resolution",
        "per_country",
        "Rozdzielczosc 100% siatki",
        short="-r",
        metavar="ROZDZIELCZOSC",
        section="Parametry produktu",
    ),
    Param(
        "layers",
        "str_list",
        "Kody po przecinku",
        metavar="KODY",
        section="Parametry produktu",
    ),
    Param("year", "int", "Rok", metavar="ROK", section="Parametry produktu"),
    Param("cutout", "flag", "Wycinek", section="Parametry produktu"),
    Param(
        "output_dir",
        "path",
        "Katalog magazynu (wymagany)",
        flag="--output",
        short="-o",
        dest="output",
        metavar="KATALOG",
        required=True,
        section=OUTPUT_TITLE,
    ),
    Param(
        "check_updates",
        "flag",
        "Sprawdz",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
    ),
    Param(
        "upgrade",
        "flag",
        "Pobierz nowsze",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
    ),
    Param(
        "force",
        "flag",
        "Pobierz ponownie",
        argument=None,
        exclusive="update",
        section=OUTPUT_TITLE,
    ),
    Param("update", "str", "Tryb", flag=None, allowed=("upgrade", "force")),
    Param("plan", "plan", "Plan", metavar="PLIK", section=OUTPUT_TITLE),
    Param(
        "workers",
        "int",
        "Liczba pobran",
        short="-w",
        metavar="N",
        default=4,
        section=OUTPUT_TITLE,
    ),
    Param("quiet", "flag", "Cicho", argument=None, short="-q", section=OUTPUT_TITLE),
)


def _declarations() -> tuple[tuple[Command, ...], tuple[Group, ...]]:
    commands = (
        _data(
            "elevation download",
            *_PARAMS,
            description="Pobierz dane do magazynu wersji",
            examples=(
                Example(
                    {"product": "nmt", "sheet": "N-34-130-D-d-2-4", "year": 2020},
                    title="Arkusz",
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
            "parse",
            Param("sheet", "str", "Godlo", metavar="GODLO", positional=True),
            Param("hierarchy", "flag", "Pokaz hierarchie"),
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
            ),
            Param("name", "str", "Nazwa", metavar="NAZWA", positional=True),
            Param(
                "arguments",
                "str_list",
                "Komenda i opcje",
                metavar="<grupa> <komenda> [opcje]",
                positional=True,
                nargs="REMAINDER",
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
            ),
            kind="query",
            function="get_project_status",
            result_schema="kartograf-project-check/1",
            description="Status",
        ),
        _data(
            "catalog",
            Param("group", "str", "Grupa", metavar="GRUPA", positional=True, nargs="?"),
            kind="query",
            function="get_catalog",
            result_schema="kartograf-catalog/1",
            description="Katalog",
        ),
    )
    groups = (
        Group("elevation", "Wysokosci", "Dane wysokosciowe"),
        Group("project", "Projekt", "Manifest projektu"),
        Group("cache", "Cache", "Cache metadanych", position=2),
    )
    return commands, groups


def _parser(**options) -> argparse.ArgumentParser:
    commands, groups = _declarations()
    return build_parser(commands, groups, **options)


def _leaf(parser: argparse.ArgumentParser, *words: str) -> argparse.ArgumentParser:
    current = parser
    for word in words:
        action = old_parser._subparsers(current)
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

    output = _action(leaf, "output")  # dest of --output is "output", not output_dir
    assert output.option_strings == ["--output", "-o"]
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

    parse = parser.parse_args(["parse", "N-34-130-D", "--hierarchy"])
    add = parser.parse_args(
        ["project", "add", "teren", "elevation", "download", "--product", "nmt"]
    )
    status = parser.parse_args(["project", "status", "a", "b"])
    nothing = parser.parse_args(["project", "status"])
    catalog = parser.parse_args(["catalog"])

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
        (["parse"], "required: GODLO"),
        (["elevation", "download", "--product", "dem"], "invalid choice"),
        (["elevation", "download", "--workers", "x"], "invalid int value"),
        (["elevation", "download", "--check-updates", "--upgrade"], "not allowed"),
        (["nope"], "invalid choice"),
    ):
        with pytest.raises(UsageError) as error:
            parse_command_line(parser, argv)
        assert text in str(error.value)
        assert error.value.code == "usage_error"
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
    root_leaf = parser.parse_args(["parse", "N-34"])
    group = parser.parse_args(["elevation"])

    assert leaf._command_id == "elevation download"
    assert root_leaf._command_id == "parse"
    assert not hasattr(group, "_command_id")
    assert group._group_parser is _leaf(parser, "elevation")
    assert group._group_parser.prog == "kartograf elevation"


def test_root_lists_commands_then_groups_by_position():
    parser = _parser()
    top = old_parser._subparsers(parser)
    assert top is not None

    # the commands without a group first (declaration order), then the groups by
    # position and name
    assert list(top.choices) == ["parse", "catalog", "elevation", "project", "cache"]


def test_group_without_command_name_lists_its_commands():
    group = _leaf(_parser(), "elevation")
    help_text = group.format_help()

    assert "KOMENDA" in help_text
    assert "download" in help_text and "list-sources" in help_text
    assert "Podsumowanie elevation download" in help_text


def test_command_names_come_from_the_ids():
    parser = _parser()

    assert list(old_parser._subparsers(_leaf(parser, "cache")).choices) == ["stats"]  # type: ignore[union-attr]


def test_removed_command_and_unknown_flag_texts_equal_the_old_parser():
    argvs = [
        [],
        ["download"],
        ["soilgrids", "--property", "clay"],
        ["landcover", "download", "--product", "soilgrids"],
        ["landcover", "download", "--source", "soilgrids"],
        ["landcover", "list-layers", "-s", "soilgrids"],
        ["landcover", "download", "--product=bdot10k"],
        ["elevation", "download", "--product", "nmt"],
    ]

    for argv in argvs:
        assert removed_command_error(argv) == old_parser.removed_command_error(argv)


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

    assert "nieznana opcja --hierarchy (maja ja: parse)" in str(error.value)


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
# The parser of the declarations against the old parser (stage 1 of the
# migration, O6). The old parser and this part go away with it in T5.
# =============================================================================

# Examples of an old ``epilog`` that the canonical command line writes with the
# flags in another order (the order of the declaration; the same call).
_REORDERED_EXAMPLES = {
    "kartograf elevation download --product nmt --country cz --bbox "
    "-447000,-1114000,-446000,-1113000 --bbox-crs EPSG:5514 --cutout "
    "--horizontal-crs EPSG:5514 --resolution 5m --vertical-crs Bpv -o ./data": (
        "kartograf elevation download --product nmt --country cz --bbox "
        "-447000,-1114000,-446000,-1113000 --bbox-crs EPSG:5514 --resolution 5m "
        "--vertical-crs Bpv --cutout --horizontal-crs EPSG:5514 -o ./data"
    ),
    "kartograf boundaries download --product admin --country pl --level gmina "
    "--bbox 550000,220000,590000,270000 -o ./data": (
        "kartograf boundaries download --product admin --country pl --bbox "
        "550000,220000,590000,270000 --level gmina -o ./data"
    ),
    "kartograf geodesy download --product control --network horizontal "
    "--teryt 1201 -o ./data": (
        "kartograf geodesy download --product control --teryt 1201 "
        "--network horizontal -o ./data"
    ),
    "kartograf geodesy download --product control --country pl --network "
    "vertical --bbox 560000,240000,575000,250000 -o ./data": (
        "kartograf geodesy download --product control --country pl --bbox "
        "560000,240000,575000,250000 --network vertical -o ./data"
    ),
    "kartograf landcover download --product corine --year 2018 --sheet "
    "N-34-130-D -o ./data": (
        "kartograf landcover download --product corine --sheet N-34-130-D "
        "--year 2018 -o ./data"
    ),
    "kartograf maps download --product topographic --country cz --bbox "
    "-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514 --scale 1:10000 "
    "--sheet-system sjtsk --format PDF -o ./data": (
        "kartograf maps download --product topographic --country cz --bbox "
        "-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514 --scale 1:10000 "
        "--format PDF --sheet-system sjtsk -o ./data"
    ),
    "kartograf models3d download --product buildings --lod 1 --year 2024 "
    "--teryt 1261 -o ./data": (
        "kartograf models3d download --product buildings --teryt 1261 --lod 1 "
        "--year 2024 -o ./data"
    ),
    "kartograf soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 "
    "--summary -o ./data": (
        "kartograf soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 "
        "-o ./data --summary"
    ),
}
# Examples the catalog adds to an old ``epilog``: every data command shows an
# example of each country its products have (``boundaries`` had only PL ones).
_ADDED_EXAMPLES = {
    "kartograf boundaries download": (
        "kartograf boundaries download --product admin --country cz --bbox "
        "-470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514 --level obec "
        "-o ./data",
    ),
}


def _walk(parser, path=()):
    """Every parser of the tree with its words (the root: ``()``)."""
    yield path, parser
    sub = old_parser._subparsers(parser)
    if sub is not None:
        for name, child in sub.choices.items():
            yield from _walk(child, (*path, name))


def _without_json(commands):
    """The declarations as the old CLI has them: no ``catalog`` and no ``--json``
    (the old ``elevation availability`` has its own)."""
    return [
        replace(
            command,
            params=tuple(
                p
                for p in command.params
                if p.name != "json" or command.id == "elevation availability"
            ),
        )
        for command in commands
        if command.id != "catalog"
    ]


_DECLARED = declared()
_OLD = dict(_walk(old_parser.create_parser()))
_NEW = dict(_walk(build_parser(_without_json(_DECLARED.commands), _DECLARED.groups)))
_CLI_COMMANDS = [
    command
    for command in _DECLARED.commands
    if command.cli is not None and command.id != "catalog"
]
_DATA_EXAMPLES = [
    (command, index)
    for command in _DECLARED.commands
    if command.project_task
    for index in range(len(command.examples))
]


def _type_name(action: argparse.Action) -> str | None:
    kind = action.type
    if kind is None:
        return None
    return getattr(kind, "__qualname__", None) or repr(kind)


def _dump(parser: argparse.ArgumentParser) -> list[dict]:
    """Every action of a parser as data: what the parser accepts and shows."""
    titles = {
        id(action): group.title
        for group in parser._action_groups
        for action in group._group_actions
    }
    exclusive = {
        id(action): index
        for index, group in enumerate(parser._mutually_exclusive_groups)
        for action in group._group_actions
    }
    return [
        {
            "option_strings": list(action.option_strings),
            "dest": action.dest,
            "action": type(action).__name__,
            "type": _type_name(action),
            "choices": None if action.choices is None else list(action.choices),
            "default": repr(action.default),
            "nargs": action.nargs,
            "required": action.required,
            "const": repr(action.const),
            "metavar": action.metavar,
            "help": action.help,
            "section": titles.get(id(action)),
            "exclusive": exclusive.get(id(action)),
        }
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction)
    ]


def _old_help(parser: argparse.ArgumentParser) -> str:
    """The help of an old parser with its re-ordered examples written the way the
    declarations write them and the examples the catalog adds (the epilog is the
    last block of a help)."""
    text = parser.format_help()
    for old, new in _REORDERED_EXAMPLES.items():
        text = text.replace(f"  {old}\n", f"  {new}\n")
    return text + "".join(
        f"  {line}\n" for line in _ADDED_EXAMPLES.get(parser.prog, ())
    )


@pytest.mark.parametrize("command", _CLI_COMMANDS, ids=[c.id for c in _CLI_COMMANDS])
def test_new_parser_equals_old_parser(command, monkeypatch):
    monkeypatch.setenv("COLUMNS", "100")
    words = tuple(command.id.split())
    old, new = _OLD[words], _NEW[words]

    assert new.prog == old.prog
    assert new.description == old.description
    assert _dump(new) == _dump(old)
    assert new.format_help() == _old_help(old)


@pytest.mark.parametrize(
    "group", _DECLARED.groups, ids=[g.name for g in _DECLARED.groups]
)
def test_group_help_equals_old(group, monkeypatch):
    monkeypatch.setenv("COLUMNS", "100")
    old, new = _OLD[(group.name,)], _NEW[(group.name,)]

    assert new.format_help() == old.format_help()
    declared_names = {c.name for c in _CLI_COMMANDS if c.group == group.name}
    old_names = {
        words[-1] for words in _OLD if len(words) == 2 and words[0] == group.name
    }
    assert declared_names == old_names


def test_every_reordered_example_is_still_an_old_example():
    old_epilogs = "\n".join(p.epilog or "" for p in _OLD.values())
    new_epilogs = "\n".join(p.epilog or "" for p in _NEW.values())

    for old, new in _REORDERED_EXAMPLES.items():
        assert f"  {old}\n" in f"{old_epilogs}\n"
        assert f"  {new}\n" in f"{new_epilogs}\n"


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
    assert parsed.output == "./data"


def test_example_command_lines_of_every_command_parse():
    parser = build_parser(_DECLARED.commands, _DECLARED.groups, usage_errors=True)

    for command in _DECLARED.commands:
        for example in command.examples:
            words = shlex.split(example_command_line(command, example))
            parsed = parse_command_line(parser, words[1:])
            assert parsed._command_id == command.id
