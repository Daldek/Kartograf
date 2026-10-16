"""
Unit tests for CLI module.

This module contains tests for command-line interface commands,
verifying correct parsing and output formatting.
"""

import argparse
import json
import re
import threading
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest  # noqa: F401 - required for fixtures
import requests
import shapefile
from pyproj import CRS

from kartograf.cli.commands import (
    create_parser,
    create_progress_callback,
    format_children,
    format_descendants,
    format_hierarchy,
    format_sheet_info,
    main,
)
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.data import download_data
from kartograf.download.fetch import VersionedFile
from kartograf.download.laz import LazDownloadResult
from kartograf.download.manager import DownloadProgress, DownloadResult
from kartograf.download.options import pl_file_variant
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import Notice
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.prg import LandMask
from kartograf.sources.registry import sources_for
from kartograf.sources.variants import UNKNOWN_VERTICAL, ProductVariant, variants
from tests.conftest import WCS_FIXTURES, recorded_response, write_gpkg_layers
from tests.cz_fakes import cz_factory, route_of


@pytest.fixture(autouse=True)
def _cwd_outside_repo(tmp_path, monkeypatch):
    """The PL/CZ ``MetadataCache`` lands in cwd — outside the repo and output dir."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


def _mock_provider_and_storage(extension):
    """A (provider, storage) pair for patching ``_create_provider_and_storage``."""
    provider = Mock()
    provider.default_extension = extension
    return provider, Mock()


def _version(path, version="2025-01-01_1_0a1b2c3d", status="new", **kwargs):
    return VersionedFile(
        path=Path(path),
        version_path=Path(path).parent / "versions" / version / Path(path).name,
        label=version.rsplit("_", 1)[0],
        sha256=version.rsplit("_", 1)[-1],
        status=status,
        **kwargs,
    )


def _sheet_list_manager(*paths, failed=(), no_coverage=(), skipped=()):
    """Return a sheet-list manager with a concrete download outcome."""
    manager = Mock()
    manager.download_sheets.return_value = DownloadResult(
        succeeded=list(paths),
        failed=[*failed, *no_coverage],
        skipped=list(skipped),
        no_coverage=list(no_coverage),
        errors={sheet: f"siec {sheet}" for sheet in failed},
        files={
            Path(p).stem: (
                _version(p, status="local" if Path(p).stem in skipped else "new"),
            )
            for p in paths
        },
    )
    return manager


def _files(sheets, status="new"):
    """One version file per sheet in a fake download result."""
    return {sheet: (_version(f"{sheet}.asc", status=status),) for sheet in sheets}


def _mock_manager(path):
    """Manager mock returning a successful single-sheet result."""
    manager = Mock()
    manager.download_sheet.return_value = DownloadResult(
        succeeded=[path] if path is not None else []
    )
    return manager


def _starting_download(path):
    """A fake ``download_sheet`` that calls ``on_download`` before downloading."""

    def fake(sheet, update=None, on_progress=None, on_download=None):
        if on_download is not None:
            on_download()
        return DownloadResult(succeeded=[path])

    return fake


def _return_with_notices(manager_class, manager, method, result, *notices):
    """Fake a manager publishing its result notices through on_notice."""
    result.notices = tuple(notices)

    def run(*args, **kwargs):
        callback = manager_class.call_args.kwargs["on_notice"]
        for notice in result.notices:
            callback(notice)
        return result

    getattr(manager, method).side_effect = run


class TestCreateParser:
    """Tests for create_parser()."""

    def test_creates_parser(self):
        """Test that parser is created."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "kartograf"

    def test_has_version_argument(self):
        """Test that --version is available."""
        parser = create_parser()
        # Version action raises SystemExit
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_has_parse_subcommand(self):
        """Test that parse subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(["parse", "N-34-130-D"])
        assert args.command == "parse"
        assert args.sheet == "N-34-130-D"

    def test_parse_hierarchy_flag(self):
        """Test --hierarchy flag."""
        parser = create_parser()
        args = parser.parse_args(["parse", "N-34-130-D", "--hierarchy"])
        assert args.hierarchy is True

    def test_parse_children_flag(self):
        """Test --children flag."""
        parser = create_parser()
        args = parser.parse_args(["parse", "N-34-130-D", "--children"])
        assert args.children is True

    def test_parse_descendants_option(self):
        """Test --descendants option."""
        parser = create_parser()
        args = parser.parse_args(["parse", "N-34-130-D", "--descendants", "1:10000"])
        assert args.descendants == "1:10000"


class TestParseBboxArg:
    """K7a: cli._args.parse_bbox_arg — a single --bbox parser."""

    def test_valid_with_spaces(self):
        from kartograf.cli._args import parse_bbox_arg

        bbox = parse_bbox_arg(" 1, 2 ,3,4", "EPSG:2180")
        assert tuple(bbox) == (1.0, 2.0, 3.0, 4.0, "EPSG:2180")

    def test_point_allowed(self):
        from kartograf.cli._args import parse_bbox_arg

        assert parse_bbox_arg("5,5,5,5", "EPSG:4326").crs == "EPSG:4326"

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("1,2,3", "oczekiwano 4 wartosci rozdzielonych przecinkami, podano 3"),
            ("1,2,3,4,", "oczekiwano 4 wartosci rozdzielonych przecinkami, podano 5"),
            ("1;2;3;4", "podano 1"),
            ("a,2,3,4", "'a' nie jest liczba"),
            ("10,10,5,5", "min > max"),
            ("1,10,5,5", "min > max"),
            ("nan,1,2,3", "skonczone"),
            ("1,2,inf,4", "skonczone"),
        ],
    )
    def test_invalid(self, text, reason):
        from kartograf.cli._args import parse_bbox_arg

        with pytest.raises(ValidationError) as exc:
            parse_bbox_arg(text, "EPSG:2180")
        msg = str(exc.value)
        assert msg.startswith("Nieprawidlowy bbox: ")
        assert reason in msg
        assert "Oczekiwano: min_x,min_y,max_x,max_y" in msg


class TestCreateParserSheetStrip:
    """K5: argparse does not strip whitespace - the sheet code is stripped
    on input, before the system registry decides the country and before the
    file name is built."""

    @pytest.mark.parametrize("raw", [" 302_5550", "302_5550 ", "\t302_5550\n"])
    def test_download_sheet_stripped(self, raw):
        assert (
            create_parser().parse_args(["elevation", "download", "--sheet", raw]).sheet
            == "302_5550"
        )

    def test_parse_sheet_stripped(self):
        assert create_parser().parse_args(["parse", " N-34 "]).sheet == "N-34"

    def test_download_without_sheet_still_none(self):
        args = create_parser().parse_args(
            ["elevation", "download", "--bbox", "1,2,3,4"]
        )
        assert args.sheet is None


class TestFormatSheetInfo:
    """Tests for format_sheet_info()."""

    def test_format_1m_sheet(self):
        """Test formatting 1:1000000 sheet."""
        parser = SheetParser("N-34")
        output = format_sheet_info(parser)

        assert "N-34" in output
        assert "1:1000000" in output
        assert "1992" in output
        assert "Czlony:" in output

    def test_format_10k_sheet(self):
        """Test formatting 1:10000 sheet."""
        parser = SheetParser("N-34-130-D-d-2-4")
        output = format_sheet_info(parser)

        assert "N-34-130-D-d-2-4" in output
        assert "1:10000" in output
        assert "pas: N" in output

    def test_format_includes_all_components(self):
        """Test that all components are included."""
        parser = SheetParser("N-34-130-D")
        output = format_sheet_info(parser)

        # Should include component values
        assert "N" in output
        assert "34" in output
        assert "130" in output
        assert "D" in output


class TestFormatHierarchy:
    """Tests for format_hierarchy()."""

    def test_format_hierarchy_10k(self):
        """Test formatting hierarchy from 1:10000."""
        parser = SheetParser("N-34-130-D-d-2-4")
        output = format_hierarchy(parser)

        assert "Hierarchia" in output
        assert "N-34-130-D-d-2-4" in output
        assert "N-34-130-D-d-2" in output
        assert "N-34-130-D-d" in output
        assert "N-34-130-D" in output
        assert "N-34" in output

    def test_format_hierarchy_1m(self):
        """Test formatting hierarchy from 1:1000000."""
        parser = SheetParser("N-34")
        output = format_hierarchy(parser)

        assert "N-34" in output
        assert "1:1000000" in output


class TestFormatChildren:
    """Tests for format_children()."""

    def test_format_children_100k(self):
        """Test formatting children of 1:100000 sheet."""
        parser = SheetParser("N-34-130-D")
        output = format_children(parser)

        assert "Arkusze potomne" in output
        assert "(4)" in output
        assert "N-34-130-D-a" in output
        assert "N-34-130-D-b" in output
        assert "N-34-130-D-c" in output
        assert "N-34-130-D-d" in output

    def test_format_children_8_part_no_children(self):
        """The 8-part sheet is the lowest level (nie ma arkuszy potomnych)."""
        parser = SheetParser("N-34-130-D-d-2-4-1")
        output = format_children(parser)

        assert "nie ma arkuszy potomnych" in output

    def test_format_children_500k(self):
        """Test formatting children of 1:500000 ((36))."""
        parser = SheetParser("N-34-A")
        output = format_children(parser)

        assert "(36)" in output


class TestFormatDescendants:
    """Tests for format_descendants()."""

    def test_format_descendants_small(self):
        """Test formatting descendants (small count)."""
        parser = SheetParser("N-34-130-D-d-2")
        output = format_descendants(parser, "1:10000")

        assert "Arkusze potomne" in output
        assert "(4)" in output
        assert "N-34-130-D-d-2-1" in output
        assert "N-34-130-D-d-2-4" in output

    def test_format_descendants_large(self):
        """Test formatting descendants (large count, truncated)."""
        parser = SheetParser("N-34-130-D")
        output = format_descendants(parser, "1:10000")

        assert "(64)" in output
        assert "..." in output


class TestCmdParse:
    """Tests for cmd_parse command."""

    def test_parse_valid_sheet(self, capsys):
        """Test parsing valid sheet."""
        result = main(["parse", "N-34-130-D"])

        assert result == 0
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "1:100000" in captured.out

    def test_parse_invalid_sheet(self, capsys):
        """Test parsing invalid sheet."""
        result = main(["parse", "INVALID"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_parse_with_hierarchy(self, capsys):
        """Test parsing with --hierarchy flag."""
        result = main(["parse", "N-34-130-D", "--hierarchy"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Hierarchia" in captured.out
        assert "N-34" in captured.out

    def test_parse_with_children(self, capsys):
        """Test parsing with --children flag."""
        result = main(["parse", "N-34-130-D", "--children"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Arkusze potomne" in captured.out
        assert "N-34-130-D-a" in captured.out

    def test_parse_with_descendants(self, capsys):
        """Test parsing with --descendants option."""
        result = main(["parse", "N-34-130-D-d-2", "--descendants", "1:10000"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Arkusze potomne" in captured.out
        assert "(4)" in captured.out

    def test_parse_with_invalid_descendants_scale(self, capsys):
        """Test parsing with invalid descendants scale."""
        result = main(["parse", "N-34-130-D", "--descendants", "invalid"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestMain:
    """Tests for main() function."""

    def test_no_command_shows_help(self, capsys):
        """Test that no command shows help."""
        result = main([])

        assert result == 0
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "kartograf" in captured.out

    def test_help_flag(self, capsys):
        """Test --help flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_version_flag(self, capsys):
        """Test --version flag."""
        from kartograf import __version__

        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_parse_subcommand(self, capsys):
        """Test parse subcommand."""
        result = main(["parse", "N-34"])

        assert result == 0
        captured = capsys.readouterr()
        assert "N-34" in captured.out

    @patch("kartograf.cli.commands.cmd_parse", side_effect=RuntimeError("boom"))
    def test_unexpected_exception_is_reported_not_raised(self, mock_cmd_parse, capsys):
        """A non-KartografError exception gives a message and code 1, no traceback."""
        result = main(["parse", "N-34"])

        assert result == 1
        captured = capsys.readouterr()
        assert "RuntimeError: boom" in captured.err
        assert "KARTOGRAF_DEBUG" in captured.err

    @patch(
        "kartograf.cli.commands.cmd_parse",
        side_effect=ValidationError("zly godlo"),
    )
    def test_kartograf_error_is_reported_with_message(self, mock_cmd_parse, capsys):
        """KartografError gives a message without the class name."""
        result = main(["parse", "N-34"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error: zly godlo" in captured.err
        assert "ValidationError" not in captured.err

    @patch("kartograf.cli.commands.cmd_parse", side_effect=RuntimeError("boom"))
    def test_debug_env_reraises(self, mock_cmd_parse, capsys, monkeypatch):
        """KARTOGRAF_DEBUG=1 lets the full traceback through."""
        monkeypatch.setenv("KARTOGRAF_DEBUG", "1")

        with pytest.raises(RuntimeError):
            main(["parse", "N-34"])

    @patch(
        "kartograf.cli.commands.cmd_parse",
        side_effect=ValidationError("zly godlo"),
    )
    def test_debug_env_reraises_kartograf_error(
        self, mock_cmd_parse, capsys, monkeypatch
    ):
        """N17: KARTOGRAF_DEBUG=1 gives a traceback also for a KartografError
        reaching the ``main`` barrier."""
        monkeypatch.setenv("KARTOGRAF_DEBUG", "1")

        with pytest.raises(ValidationError, match="zly godlo"):
            main(["parse", "N-34"])


class TestCommandGroups:
    """ADR-039: data commands in groups by data type, each with its own flags."""

    _GROUPS = (
        "elevation",
        "imagery",
        "landcover",
        "soil",
        "boundaries",
        "cadastre",
        "models3d",
        "hydro",
    )
    # the selection flag of each group's download and its values
    _CHOICES = {
        "elevation": ("--product", {"nmt", "nmpt", "laz", "contours"}),
        "imagery": (
            "--product",
            {"orto", "intensity", "true-orto", "oblique-orto"},
        ),
        "landcover": ("--source", {"bdot10k", "corine", "zabaged"}),
        "boundaries": ("--product", {"admin"}),
        "cadastre": ("--product", {"map"}),
        "models3d": ("--product", {"buildings"}),
        "hydro": ("--product", {"network"}),
    }

    @pytest.mark.parametrize("group", _GROUPS)
    def test_group_without_command_prints_its_commands(self, group, capsys):
        assert main([group]) == 0
        out = capsys.readouterr().out
        assert out.startswith(f"usage: kartograf {group}")
        assert "download" in out and "list-sources" in out

    @pytest.mark.parametrize(
        ("argv", "replacement"),
        [
            (
                ["download", "--product", "nmt", "--sheet", "N-34-130-D-d-2-4"],
                "kartograf elevation download",
            ),
            (
                ["download", "--product", "orto", "--sheet", "N-34-130-D-d-2-4"],
                "kartograf imagery download",
            ),
            (["soilgrids", "hsg", "--sheet", "N-34-130-D"], "kartograf soil hsg"),
            (
                [
                    "landcover",
                    "download",
                    "--source",
                    "soilgrids",
                    "--sheet",
                    "N-34-130-D",
                ],
                "kartograf soil download",
            ),
            (
                ["landcover", "list-layers", "--source=soilgrids"],
                "kartograf soil list-layers",
            ),
        ],
        ids=[
            "download-nmt",
            "download-orto",
            "soilgrids-hsg",
            "landcover-soilgrids",
            "list-layers-soilgrids",
        ],
    )
    def test_removed_command_names_its_replacement(self, argv, replacement, capsys):
        """0.8.0 removed the old commands without aliases: an input error
        (exit 2, like any unknown command) naming the new one; nothing runs."""
        with (
            patch("kartograf.cli.download_cmd.download_data") as download,
            patch("kartograf.cli.landcover_cmd.LandCoverManager") as manager,
            patch("kartograf.hydrology.HSGCalculator") as calculator,
            pytest.raises(SystemExit) as exc,
        ):
            main([*argv, "-o", "out"])
        assert exc.value.code == 2
        assert replacement in capsys.readouterr().err
        for mock in (download, manager, calculator):
            mock.assert_not_called()

    @pytest.mark.parametrize(
        ("group", "listed", "absent"),
        [("elevation", ("nmt", "nmpt", "laz"), "orto"), ("imagery", ("orto",), "nmt")],
    )
    def test_missing_product_names_only_the_group_products(
        self, group, listed, absent, capsys, tmp_path
    ):
        with patch("kartograf.cli.download_cmd.download_data") as download:
            rc = main(
                [group, "download", "--sheet", "N-34-130-D-d-2-4", "-o", str(tmp_path)]
            )
        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: --product wymagane: ")
        assert all(f" {product} (" in err for product in listed)
        assert f" {absent} (" not in err
        download.assert_not_called()

    @pytest.mark.parametrize("group", _GROUPS)
    def test_list_sources_shows_what_the_group_downloads(self, group, capsys):
        """Every source of ``<group> list-sources`` is selectable in ``<group>
        download`` and every selection value has a registered source."""
        assert main([group, "list-sources"]) == 0
        rows = capsys.readouterr().out.splitlines()[2:]
        if group == "soil":  # one source, no selection flag
            assert "global.isric.soilgrids" in rows[0]
            return
        flag, values = self._CHOICES[group]
        shown = {row.split()[1] for row in rows if row.startswith(f"  {flag} ")}
        assert shown == values
        parser = create_parser()
        for value in shown:
            args = parser.parse_args([group, "download", flag, value])
            assert getattr(args, flag.removeprefix("--")) == value

    def test_hydro_group_registered(self):
        """``hydro download`` has only the flags of the group (ADR-039): the
        CZ network has no PL selections (``--teryt``, ``--sheet``) and no
        content flags; the area, the national file and the store flags."""
        parser = create_parser()
        group = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ).choices["hydro"]
        download = next(
            action
            for action in group._actions
            if isinstance(action, argparse._SubParsersAction)
        ).choices["download"]
        flags = {flag for action in download._actions for flag in action.option_strings}
        assert flags == {
            "-h",
            "--help",
            "--product",
            "--country",
            "--bbox",
            "--bbox-crs",
            "--geometry",
            "--layer",
            "--whole-country",
            "--output",
            "-o",
            "--check-updates",
            "--upgrade",
            "--force",
            "--plan",
            "--workers",
            "-w",
            "--quiet",
            "-q",
        }


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_full_workflow_parse(self, capsys):
        """Test full parse workflow."""
        result = main(["parse", "N-34-130-D-d-2-4", "--hierarchy", "--children"])

        assert result == 0
        captured = capsys.readouterr()
        # Should show basic info
        assert "1:10000" in captured.out
        # Should show hierarchy
        assert "Hierarchia" in captured.out
        # The 7-part sheet lists its four 8-part quarters
        assert "Arkusze potomne N-34-130-D-d-2-4 (4)" in captured.out
        assert "N-34-130-D-d-2-4-4 (1:5000)" in captured.out

    def test_all_scales(self, capsys):
        """Test parsing all scale levels."""
        test_cases = [
            ("N-34", "1:1000000"),
            ("N-34-A", "1:500000"),
            ("N-34-130", "1:200000"),
            ("N-34-130-D", "1:100000"),
            ("N-34-130-D-d", "1:50000"),
            ("N-34-130-D-d-2", "1:25000"),
            ("N-34-130-D-d-2-4", "1:10000"),
        ]

        for sheet, expected_scale in test_cases:
            result = main(["parse", sheet])
            assert result == 0, f"Failed for {sheet}"
            captured = capsys.readouterr()
            assert expected_scale in captured.out, f"Scale not found for {sheet}"


class TestCreateParserDownload:
    """Tests for download subparser."""

    def test_has_download_subcommand(self):
        """Test that download subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(["elevation", "download", "--sheet", "N-34-130-D"])
        assert args.command == "elevation"
        assert args.sheet == "N-34-130-D"

    def test_download_scale_option(self):
        """Test --scale option."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D", "--scale", "1:10000"]
        )
        assert args.scale == "1:10000"

    def test_download_output_option(self):
        """Test --output option."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D", "-o", "/custom/path"]
        )
        assert args.output == "/custom/path"

    def test_download_force_flag(self):
        """Test --force flag."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D", "--force"]
        )
        assert args.force is True

    def test_download_quiet_flag(self):
        """Test --quiet flag."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D", "-q"]
        )
        assert args.quiet is True

    def test_download_switch_defaults(self):
        """Switches stay off unless given (the only download defaults left)."""
        parser = create_parser()
        args = parser.parse_args(["elevation", "download", "--sheet", "N-34-130-D"])
        assert args.force is False
        assert args.quiet is False
        assert args.all_campaigns is False


class TestCreateParserCountry:
    """Tests for --country/--cutout/--horizontal-crs and per-country sentinels."""

    def test_country_choices(self):
        for value in ("pl", "cz", "auto"):
            args = create_parser().parse_args(
                ["elevation", "download", "--sheet", "X", "--country", value]
            )
            assert args.country == value

    def test_country_invalid_rejected(self):
        with pytest.raises(SystemExit):
            create_parser().parse_args(
                ["elevation", "download", "--sheet", "X", "--country", "de"]
            )

    def test_cutout_and_horizontal_crs_defaults_and_choices(self):
        args = create_parser().parse_args(["elevation", "download", "--sheet", "X"])
        assert args.cutout is False and args.horizontal_crs is None
        for value in ("EPSG:2180", "EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(
                [
                    "elevation",
                    "download",
                    "--sheet",
                    "X",
                    "--cutout",
                    "--horizontal-crs",
                    value,
                ]
            )
            assert args.cutout is True and args.horizontal_crs == value
        with pytest.raises(SystemExit):
            create_parser().parse_args(
                [
                    "elevation",
                    "download",
                    "--sheet",
                    "X",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:4326",
                ]
            )
        for removed in ("--target-crs", "--system"):
            with pytest.raises(SystemExit):
                create_parser().parse_args(
                    ["elevation", "download", "--sheet", "X", removed, "1992"]
                )

    def test_sentinel_defaults(self):
        """--resolution/--vertical-crs/--sheet-system default to None (per country)."""
        args = create_parser().parse_args(["elevation", "download", "--sheet", "X"])
        assert args.resolution is None
        assert args.vertical_crs is None
        assert args.sheet_system is None

    def test_new_choices_accepted(self):
        args = create_parser().parse_args(
            [
                "elevation",
                "download",
                "--sheet",
                "X",
                "--resolution",
                "2m",
                "--vertical-crs",
                "Bpv",
            ]
        )
        assert args.resolution == "2m"
        assert args.vertical_crs == "Bpv"

    def test_bbox_crs_extended_with_cz(self):
        for value in ("EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(
                ["elevation", "download", "--bbox", "1,2,3,4", "--bbox-crs", value]
            )
            assert args.bbox_crs == value


class TestProgressCallback:
    """Tests for create_progress_callback()."""

    def test_quiet_returns_none(self):
        """Test that quiet mode returns None."""
        callback = create_progress_callback(quiet=True)
        assert callback is None

    def test_returns_callable(self):
        """Test that non-quiet mode returns a callable."""
        callback = create_progress_callback(quiet=False)
        assert callable(callback)

    def test_callback_handles_downloading_status(self, capsys):
        """Test callback for downloading status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=1, total=4, sheet="N-34-130-D", status="downloading"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "1/4" in captured.out

    def test_callback_handles_completed_status(self, capsys):
        """Test callback for completed status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=4, total=4, sheet="N-34-130-D", status="completed"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "4/4 + N-34-130-D" in captured.out

    def test_callback_handles_skipped_status(self, capsys):
        """Test callback for skipped status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=2, total=4, sheet="N-34-130-D", status="skipped"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "2/4 o N-34-130-D" in captured.out

    def test_callback_handles_failed_status(self, capsys):
        """Test callback for failed status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=3, total=4, sheet="N-34-130-D", status="failed"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "3/4 x N-34-130-D" in captured.out


class TestCmdDownload:
    """Tests for cmd_download command."""

    def test_download_invalid_sheet(self, capsys):
        """Test downloading with invalid sheet."""
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "INVALID",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.download.data.DownloadManager")
    def test_download_single_sheet(self, mock_manager_class, capsys, tmp_path):
        """Test downloading a single sheet."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "test.tif"]
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_sheet.assert_called_once_with(
            "N-34-130-D-d-2-4", update=None, on_progress=None, on_download=ANY
        )

    @patch("kartograf.download.data.DownloadManager")
    def test_download_hierarchy(self, mock_manager_class, capsys, tmp_path):
        """Test downloading a hierarchy."""
        paths = [tmp_path / f"test{i}.tif" for i in range(4)]
        mock_manager = Mock()
        mock_manager.count_sheets.return_value = 4
        mock_manager.download_hierarchy.return_value = DownloadResult(succeeded=paths)
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "7.171.21",
                "--scale",
                "1:2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_hierarchy.assert_called_once()

    @patch("kartograf.download.data.DownloadManager")
    def test_download_with_force(self, mock_manager_class, tmp_path):
        """Test downloading with --force flag."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "test.tif"]
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "--force",
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_sheet.assert_called_once_with(
            "N-34-130-D-d-2-4", update="force", on_progress=None, on_download=ANY
        )

    @patch("kartograf.download.data.DownloadManager")
    def test_download_handles_error(self, mock_manager_class, capsys, tmp_path):
        """Test that download errors are handled."""
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError(
            "Network error", sheet="N-34-130-D"
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.download.data.DownloadManager")
    def test_download_invalid_scale(self, mock_manager_class, capsys, tmp_path):
        """Test downloading with invalid scale."""
        from kartograf.exceptions import ValidationError

        mock_manager = Mock()
        # count_sheets is only called when not quiet, so mock download_hierarchy
        mock_manager.download_hierarchy.side_effect = ValidationError("Invalid scale")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D",
                "--scale",
                "1:invalid",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.download.data.DownloadManager")
    def test_download_shows_progress(self, mock_manager_class, capsys, tmp_path):
        """Test that download shows progress when not quiet."""
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = _starting_download(
            tmp_path / "test.tif"
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Pobieranie" in captured.out

    # --- hierarchy exit code (A2-3) ---

    @staticmethod
    def _hierarchy_manager(result: DownloadResult):
        """Code coarser than 1:10000 returns a hierarchy result directly."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = result
        mock_manager.count_sheets.return_value = result.total
        return mock_manager

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_all_failed_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """100% download failures in the hierarchy: an error listing all sheets."""
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(
                succeeded=[],
                failed=["A", "B", "C", "D"],
                skipped=[],
                errors={sheet: "zrodlo 503" for sheet in ("A", "B", "C", "D")},
            )
        )

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "Error: 4 z 4 arkuszy nie pobrano" in err
        assert all(f"{sheet}: zrodlo 503" in err for sheet in ("A", "B", "C", "D"))
        assert "ponow pobranie" in err

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_partial_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """A download failure (not missing data) ends with 1 despite partial success."""
        paths = [tmp_path / f"test{i}.asc" for i in range(3)]
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(
                succeeded=paths, failed=["A"], skipped=[], errors={"A": "siec"}
            )
        )

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 1
        assert "Error: 1 z 4 arkuszy nie pobrano" in capsys.readouterr().err

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_no_coverage_with_files_warns_and_returns_0(
        self, mock_manager_class, capsys, tmp_path
    ):
        """D10: sea sheets under a 1:50000 code = Warning + exit code 0 (as --bbox)."""
        paths = [tmp_path / f"test{i}.asc" for i in range(3)]
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(
                succeeded=paths,
                failed=["A"],
                no_coverage=["A"],
                files=_files(["B", "C", "D"]),
            )
        )

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Warning: GUGiK nie ma danych dla 1 z 4 arkuszy (A)" in captured.err
        assert "Error:" not in captured.err
        assert "Nowe: 3, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0" in (
            captured.out
        )

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_all_no_coverage_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """D10: zero files and all without data = exit code 1 (nothing to download)."""
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(failed=["A", "B"], no_coverage=["A", "B"])
        )

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "Error: GUGiK nie ma danych dla zadnego z 2 arkuszy" in err
        assert "ponow pobranie" not in err

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_all_skipped_returns_exit_0(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Only skips (the files already exist) is still a success."""
        mock_manager = self._hierarchy_manager(
            DownloadResult(
                succeeded=[],
                failed=[],
                skipped=["A", "B", "C", "D"],
                files=_files(["A", "B", "C", "D"], "local"),
            )
        )
        mock_manager.download_sheet.return_value = DownloadResult(
            skipped=["A", "B", "C", "D"],
            files=_files(["A", "B", "C", "D"], "local"),
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert "A: lokalna wersja 2025-01-01_1" in captured.out
        assert "Nowe: 0, nowa etykieta: 0, bez zmian: 0, lokalne: 4, bledy: 0" in (
            captured.out
        )

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_scale_mode_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """The same check applies on the --scale branch."""
        mock_manager = Mock()
        mock_manager.count_sheets.return_value = 4
        mock_manager.download_hierarchy.return_value = DownloadResult(
            failed=["A", "B", "C", "D"],
            errors={sheet: "siec" for sheet in ("A", "B", "C", "D")},
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "7.171.21",
                "--scale",
                "1:2000",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 1
        assert "Error: 4 z 4 arkuszy nie pobrano" in capsys.readouterr().err


class TestDownloadCLIIntegration:
    """Integration tests for download CLI."""

    def test_download_help(self, capsys):
        """Test download --help."""
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--help",
                ]
            )

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "download" in captured.out.lower()
        assert "--scale" in captured.out
        assert "--product" in captured.out  # Should show product option

    def test_main_lists_data_groups(self, capsys):
        """Top-level help directs people to the grouped commands."""
        assert main([]) == 0
        text = capsys.readouterr().out
        assert all(
            group in text for group in ("elevation", "imagery", "landcover", "soil")
        )
        assert "  download " not in text


class TestCmdDownloadProduct:
    """Tests for --product flag in download command."""

    def test_download_parser_has_product_option(self):
        """Test that download parser has --product option."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D", "--product", "nmpt"]
        )
        assert args.product == "nmpt"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_product_nmpt(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --product nmpt creates GugikNmptProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "test.asc"]
        )
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "nmpt",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "nmpt"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_product_orto(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --product orto creates GugikOrtoProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "test.tif"]
        )
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "imagery",
                "download",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "orto",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "orto"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_product_nmt_default(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test default product creates GugikProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "test.asc"]
        )
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "nmt"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_product_nmpt(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --bbox + --product nmpt."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "--product",
                "nmpt",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "nmpt"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_product_orto(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --bbox + --product orto."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = _sheet_list_manager(tmp_path / "test.tif")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "imagery",
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "--sheet-system",
                "1992",
                "--country",
                "pl",
                "--product",
                "orto",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "orto"

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_orto_messages_do_not_claim_a_resolution(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Ortho has no resolution - the message must not say 'resolution: 1m'."""
        mock_create.return_value = _mock_provider_and_storage(".tif")
        manager = _mock_manager(tmp_path / "test.tif")
        manager.download_sheet.side_effect = _starting_download(tmp_path / "test.tif")
        mock_manager_cls.return_value = manager

        result = main(
            ["imagery", "download", "--product", "orto"]
            + ["--sheet", "N-34-130-D-d-2-4", "-o", str(tmp_path)]
        )

        assert result == 0
        out = capsys.readouterr().out
        assert "Pobieranie N-34-130-D-d-2-4 (product: orto)" in out
        assert "resolution" not in out

    # --- N6/E14: PL-path MetadataCache — --force = cache in refresh mode ---

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_force_passes_refresh_cache_to_provider_factory(
        self, mock_manager_cls, mock_create, tmp_path
    ):
        """``--force`` skips old metadata, then saves the new record."""
        from kartograf.cache.defaults import open_cache

        key = ("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4")
        old = {"source": {"url": "old"}}
        new = {"source": {"url": "new"}}
        with open_cache(True, force=False) as cache:
            assert cache is not None
            cache.set_record(*key, old)

        seen = []
        pair = _mock_provider_and_storage(".asc")

        def create(*_args, cache, **_kwargs):
            seen.append(cache.get_record(*key))
            cache.set_record(*key, new)
            return pair

        mock_create.side_effect = create
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--force",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert rc == 0
        assert seen == [None]
        with open_cache(True, force=False) as cache:
            assert cache is not None
            assert cache.get_record(*key) == new

    @pytest.mark.parametrize(
        "argv",
        [
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
            ],
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet-system",
                "1992",
                "--bbox",
                "630000,480000,637000,487000",
                "--country",
                "pl",
            ],
        ],
        ids=["sheet", "bbox-list"],
    )
    @patch("kartograf.download.data.find_sheets_for_bbox", return_value=["N-1"])
    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_without_force_reads_cache_in_cwd(
        self, mock_manager_cls, mock_create, _mock_find, tmp_path, argv
    ):
        from kartograf.cache.defaults import default_cache_path, open_cache

        sheet = "N-34-130-D-d-2-4" if "--sheet" in argv else "N-1"
        key = ("nmt", "1m", "EVRF2007", sheet)
        old = {"source": {"url": "old"}}
        with open_cache(True, force=False) as cache:
            assert cache is not None
            cache.set_record(*key, old)

        seen = []
        pair = _mock_provider_and_storage(".asc")

        def create(*_args, cache, **_kwargs):
            assert cache.db_path == default_cache_path()
            seen.append(cache.get_record(*key))
            return pair

        mock_create.side_effect = create
        mock_manager_cls.return_value = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "t.asc"]
        )

        rc = main([*argv, "-o", str(tmp_path), "-q"])

        assert rc == 0
        assert seen == [old]

    # --- product/resolution and product/vertical-crs pair validation (V2-N1) ---

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_nmpt_with_resolution_5m_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """NMPT 5m does not exist - the CLI rejects it instead of quietly using 1m."""
        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "nmpt",
                "--resolution",
                "5m",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert err.startswith(
            "Error: PL nie ma rozdzielczosci 5m dla NMPT - dostepne: "
        )
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()

    @pytest.mark.parametrize(
        "flag",
        [["--vertical-crs", "KRON86"], ["--min-density", "4"]],
        ids=lambda flag: flag[0],
    )
    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_imagery_rejects_elevation_only_flags(
        self, mock_manager_cls, mock_create, flag, capsys, tmp_path
    ):
        """Orthophoto has no vertical CRS or point density: an elevation flag
        in ``imagery download`` is an input error, not a no-op."""
        argv = ["imagery", "download", "--product", "orto"]
        argv += ["--sheet", "N-34-130-D-d-2-4", "-o", str(tmp_path), *flag]
        with pytest.raises(SystemExit) as exc:
            main(argv)

        assert exc.value.code == 2
        assert f"unrecognized arguments: {flag[0]}" in capsys.readouterr().err
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_bbox_nmpt_with_resolution_5m_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """The same validation applies in --bbox mode (PL sentinels)."""
        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "530000,382000,533000,386000",
                "--country",
                "pl",
                "--product",
                "nmpt",
                "--resolution",
                "5m",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert err.startswith(
            "Error: PL nie ma rozdzielczosci 5m dla NMPT - dostepne: "
        )
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()


class TestCreateProviderAndStorage:
    """Tests for _create_provider_and_storage helper."""

    def test_nmt_creates_gugik_provider(self, tmp_path):
        """Test that nmt creates GugikProvider + FileStorage."""
        from kartograf.download.data import _create_provider_and_storage
        from kartograf.providers.pl.gugik import GugikProvider

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikProvider)
        assert storage._resolution == "1m"
        assert storage._subdir == "nmt/pl_{system}_1m_evrf2007"

    def test_nmpt_creates_nmpt_provider(self, tmp_path):
        """Test that nmpt creates GugikNmptProvider."""
        from kartograf.download.data import _create_provider_and_storage
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikNmptProvider)
        assert storage._subdir == "nmpt/pl_{system}_1m_evrf2007"

    def test_orto_creates_orto_provider(self, tmp_path):
        """Test that orto creates GugikOrtoProvider."""
        from kartograf.download.data import _create_provider_and_storage
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider, storage = _create_provider_and_storage(
            "orto", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikOrtoProvider)
        assert storage._subdir == "orto/pl_{system}"

    def test_laz_product_raises_validation_error(self, tmp_path):
        """LAZ has a separate flow (_cmd_download_laz) - it must not get here."""
        from kartograf.download.data import _create_provider_and_storage

        with pytest.raises(ValidationError, match="Nieobslugiwany produkt"):
            _create_provider_and_storage("laz", tmp_path, "EVRF2007", "1m")

    def test_unknown_product_raises_validation_error(self, tmp_path):
        """An unknown product must not silently fall through to the NMT factory."""
        from kartograf.download.data import _create_provider_and_storage

        with pytest.raises(ValidationError, match="dmr5g"):
            _create_provider_and_storage("dmr5g", tmp_path, "EVRF2007", "1m")

    def test_nmt_kron86_storage_segment(self, tmp_path):
        from kartograf.download.data import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmt/pl_{system}_1m_kron86"

    def test_nmt_5m_needs_datum_resolved_by_sentinels(self, tmp_path):
        """The registry has no NMT 5m in KRON86: the request validation rejects
        the pair before this helper; should it reach it, the provider does."""
        from kartograf.download.data import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "EVRF2007", "5m"
        )
        assert storage._subdir == "nmt/pl_{system}_5m_evrf2007"
        with pytest.raises(ValidationError, match="tylko w EVRF2007"):
            _create_provider_and_storage("nmt", tmp_path, "KRON86", "5m")

    def test_nmpt_storage_segment(self, tmp_path):
        from kartograf.download.data import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmpt/pl_{system}_1m_kron86"


def _grid_labels(product: str, vertical_crs: str | None = None) -> list[str]:
    """Labels of the product's PL ASC grids in the variant registry, ascending."""
    by_value = {
        v.resolution_m: v.label
        for v in variants(
            product=product, country="PL", vertical_crs=vertical_crs, format="ASC"
        )
        if v.resolution_m is not None and v.label is not None
    }
    return [by_value[value] for value in sorted(by_value)]


def _registry_grids(product: str) -> set[tuple[str, str]]:
    """``{(vertical CRS, label)}`` of the product's PL variants in the product
    format (registry): the ASC grids and the voivodeship files without a
    height system (NMT 100 m, listed under ``UNKNOWN_VERTICAL``)."""
    return {
        (v.vertical_crs or UNKNOWN_VERTICAL, v.label)
        for v in variants(product=product, country="PL")
        if v.label is not None and not v.source_file
    }


def _labels_by_system(text: str) -> set[tuple[str, str]]:
    """``{(vertical CRS, label)}`` of a ``EVRF2007: 0.5m, 1m; KRON86: 1m`` text."""
    found = set()
    for group in text.split("; "):
        system, labels = group.split(": ", 1)
        found |= {(system, label) for label in labels.split(", ")}
    return found


# NMT 5m exists only in EVRF2007; the text names the KRON86 grids of the registry
_5M_KRON86_ERROR = (
    "Error: NMT 5m (PL) jest dostepny tylko w EVRF2007 - podano --vertical-crs "
    f"KRON86; dostepne w KRON86: {', '.join(_grid_labels('nmt', 'KRON86'))}"
)


def _write_pl_shp_2180(directory):
    """Small shapefile (a 1 km polygon near Krakow) in EPSG:2180 — offline data."""
    shp_path = directory / "area_pl.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        w.poly(
            [
                [
                    (420000, 230000),
                    (421000, 230000),
                    (421000, 231000),
                    (420000, 231000),
                    (420000, 230000),
                ]
            ]
        )
        w.record("area1")
    shp_path.with_suffix(".prj").write_text(
        CRS.from_epsg(2180).to_wkt(), encoding="utf-8"
    )
    return shp_path


class TestNmt5mKron86Rejected:
    """An explicit ``--resolution 5m --vertical-crs KRON86`` (NMT PL) is an
    error (code 1) before any provider or network call, without a silent swap
    to EVRF2007; the text comes from the variant registry (5m only in
    EVRF2007, the KRON86 grid labels)."""

    @pytest.mark.parametrize(
        "task",
        [
            ["--sheet", "N-34-130-D-d-2-4"],
            ["--sheet", "N-34-130-D"],
            ["--bbox", "630000,480000,637000,487000", "--country", "pl"],
            ["--bbox", "630000,480000,637000,487000"],
            # PL+CZ border area: under auto KRON86 decides PL, CZ never runs
            ["--bbox", "18.5,49.7,18.9,49.95", "--bbox-crs", "EPSG:4326"],
        ],
        ids=[
            "sheet",
            "sheet-hierarchy",
            "bbox-pl",
            "bbox-auto",
            "bbox-auto-pl-cz-border",
        ],
    )
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_kron86_5m_message_from_registry(
        self,
        mock_manager_cls,
        mock_create,
        mock_find,
        mock_cutout,
        mock_run_cz,
        capsys,
        tmp_path,
        task,
    ):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *task,
                "--resolution",
                "5m",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path / "out"),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert err.splitlines()[-1] == _5M_KRON86_ERROR
        assert "zamieniony" not in err
        mock_manager_cls.assert_not_called()
        mock_create.assert_not_called()
        mock_find.assert_not_called()
        mock_cutout.assert_not_called()
        mock_run_cz.assert_not_called()
        assert not (tmp_path / "out").exists()

    @pytest.mark.parametrize("extra", [[]], ids=["sheets"])
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.DownloadManager")
    def test_geometry_explicit_kron86_with_5m_is_error(
        self,
        mock_manager_cls,
        mock_create,
        mock_find_geom,
        mock_cutout,
        mock_run_cz,
        capsys,
        tmp_path,
        extra,
    ):
        shp = _write_pl_shp_2180(tmp_path)

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp),
                *extra,
                "--resolution",
                "5m",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path / "out"),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert _5M_KRON86_ERROR in err
        assert "zamieniony" not in err
        mock_manager_cls.assert_not_called()
        mock_create.assert_not_called()
        mock_find_geom.assert_not_called()
        mock_cutout.assert_not_called()
        mock_run_cz.assert_not_called()
        assert not (tmp_path / "out").exists()

    def test_pl_options_reject_kron86_and_missing_vertical_crs_for_5m(self):
        """5m exists only in EVRF2007; a missing vertical CRS is an error
        listing the values, KRON86 is rejected without a silent swap."""
        from types import SimpleNamespace

        from kartograf.download.options import resolve_pl_options

        def ns(vertical_crs):
            return SimpleNamespace(
                product="nmt",
                resolution="5m",
                vertical_crs=vertical_crs,
                cutout=False,
                sheet_system=None,
                scale=None,
            )

        resolve_pl_options(ns("EVRF2007"), code_system="1992")
        with pytest.raises(ValidationError) as missing:
            resolve_pl_options(ns(None), code_system="1992")
        assert "--vertical-crs wymagane" in str(missing.value)
        assert "KRON86" in str(missing.value)
        task = ns("KRON86")
        with pytest.raises(ValidationError) as kron:
            resolve_pl_options(task, code_system="1992")
        assert f"Error: {kron.value}" == _5M_KRON86_ERROR
        assert task.vertical_crs == "KRON86"  # no silent swap


# PL NMT/NMPT sheet variants of the registry (grids and archives of the WFS
# index): every one is a valid sheet choice of `elevation download` (ADR-041)
_PL_SHEET_VARIANTS = tuple(
    v
    for v in variants(country="PL")
    if v.product in ("nmt", "nmpt") and v.index_ref is not None
)


def _variant_id(variant: ProductVariant) -> str:
    return f"{variant.source}-{variant.vertical_crs}"


def _variant_flags(variant: ProductVariant) -> list[str]:
    """``elevation download`` flags of a sheet ``variant`` (no ``--format`` =
    ASC grid); a sheet variant always has a height system."""
    assert variant.vertical_crs is not None
    flags = ["--product", variant.product, "--vertical-crs", variant.vertical_crs]
    if variant.label is not None:
        flags += ["--resolution", variant.label]
    if variant.source_file:
        flags += ["--format", variant.format]
    return flags


class TestRegistryVariantsCli:
    """ADR-041: the variant registry is the only list of NMT/NMPT choices.

    Validation, ``--help`` and ``list-sources`` are compared with
    ``kartograf.sources.variants.variants()``, never with a list in the test.
    """

    SHEET = "N-34-130-D-d-2-4"

    @pytest.mark.parametrize("variant", _PL_SHEET_VARIANTS, ids=_variant_id)
    @patch("kartograf.download.data.DownloadManager")
    def test_every_registry_variant_validates(
        self, mock_manager_cls, variant, tmp_path, capsys
    ):
        """Every PL NMT/NMPT variant (grids and archives) passes the CLI and the
        API validation and reaches the real provider as exactly that variant;
        the manager is a fake (one sheet of the index, one file, no network)."""
        manager = mock_manager_cls.return_value
        manager.provider.index_sheets.return_value = [self.SHEET]
        manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "sheet"]
        )
        manager.download_sheets.return_value = manager.download_sheet.return_value

        rc = main(
            ["elevation", "download", "--sheet", self.SHEET, *_variant_flags(variant)]
            + ["-o", str(tmp_path / "cli"), "-q"]
        )

        assert rc == 0, capsys.readouterr().err
        assert mock_manager_cls.call_args.kwargs["provider"].variant == variant

        report = download_data(
            product=variant.product,
            output_dir=tmp_path / "api",
            sheet=self.SHEET,
            vertical_crs=variant.vertical_crs,
            resolution=variant.label,
            format=variant.format if variant.source_file else None,
            cache=False,
        )

        assert report.ok, report.failed
        assert mock_manager_cls.call_args.kwargs["provider"].variant == variant

    @pytest.mark.parametrize("label", ["2m", "0,5m", "50cm", "0.50m"])
    @patch("kartograf.download.data.DownloadManager")
    def test_unknown_label_lists_registry(
        self, mock_manager_cls, label, tmp_path, capsys
    ):
        """A label outside the registry - also another spelling of an existing
        one (K2) - is an error listing the registry grids of every height
        system; nothing is downloaded."""
        rc = main(
            ["elevation", "download", "--product", "nmt", "--sheet", self.SHEET]
            + ["--vertical-crs", "EVRF2007", "--resolution", label]
            + ["-o", str(tmp_path), "-q"]
        )

        assert rc == 1
        err = capsys.readouterr().err
        prefix = f"Error: PL nie ma rozdzielczosci {label} dla NMT - dostepne: "
        assert err.startswith(prefix)
        listed = _labels_by_system(err.removeprefix(prefix).rstrip("\n"))
        assert listed == _registry_grids("nmt")
        mock_manager_cls.assert_not_called()

    @patch("kartograf.download.data.DownloadManager")
    def test_nmpt_requires_resolution(self, mock_manager_cls, tmp_path, capsys):
        """NMPT has several grids, so no default (STANDARDS 11.2): the CLI and
        the API reject a missing resolution with the same text naming the
        registry grids."""
        rc = main(
            ["elevation", "download", "--product", "nmpt", "--sheet", self.SHEET]
            + ["--vertical-crs", "EVRF2007", "-o", str(tmp_path), "-q"]
        )
        assert rc == 1
        err = capsys.readouterr().err

        with pytest.raises(ValidationError) as exc:
            download_data(
                product="nmpt",
                output_dir=tmp_path,
                sheet=self.SHEET,
                vertical_crs="EVRF2007",
                cache=False,
            )

        message = str(exc.value)
        assert err == f"Error: {message}\n"
        prefix = "--resolution wymagane dla NMPT PL: "
        assert message.startswith(prefix)
        listed = _labels_by_system(message.removeprefix(prefix))
        assert listed == _registry_grids("nmpt")
        mock_manager_cls.assert_not_called()

    def test_help_lists_registry_labels(self, capsys):
        """``elevation download --help`` lists every PL grid of the registry per
        product and height system - and no other label."""
        with pytest.raises(SystemExit) as exc:
            main(["elevation", "download", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        block = out.split("--resolution, -r RES", 1)[1].split("--vertical-crs VCRS")[0]
        text = " ".join(block.split())

        listed = {
            (product.lower(), system, label)
            for product, groups in re.findall(r"\b(NMT|NMPT) \(([^()]*)\)", text)
            for system, label in _labels_by_system(groups)
        }

        assert listed == {
            (product, system, label)
            for product in ("nmt", "nmpt")
            for system, label in _registry_grids(product)
        }

    def test_list_sources_has_every_variant_source(self, capsys):
        """``elevation list-sources`` has one row per PL source of the registry
        (grids, archives, LAZ) and its WYBOR flags select that source."""
        assert main(["elevation", "list-sources"]) == 0
        lines = capsys.readouterr().out.splitlines()
        header = lines[1]
        choice, country, key, name = (
            header.index(column) for column in ("WYBOR", "KRAJ", "KLUCZ", "NAZWA")
        )
        rows = {}
        for line in lines[2:]:
            if not line.strip():
                break
            rows[line[key:name].strip()] = line[choice:country].strip()
        pl_variants = [
            v for v in variants(country="PL") if v.product in ("nmt", "nmpt", "laz")
        ]

        assert {k for k in rows if k.startswith("pl.")} == {
            v.source for v in pl_variants
        }
        assert rows["pl.gugik.nmpt_0_5m"] == "--product nmpt --resolution 0.5m"
        parser = create_parser()
        for variant in pl_variants:
            flags = rows[variant.source]
            args = parser.parse_args(["elevation", "download", *flags.split()])
            assert args.product == variant.product, flags
            if variant.product == "laz":
                continue
            assert args.vertical_crs in (None, variant.vertical_crs), flags
            if variant.index_ref is None:  # voivodeship files (ATOM, NMT 100 m)
                assert pl_file_variant(args) == variant, flags
                continue
            cls = GugikProvider if variant.product == "nmt" else GugikNmptProvider
            provider = cls(
                vertical_crs=variant.vertical_crs,
                resolution=args.resolution,
                format=args.format or "ASC",
            )
            assert provider.descriptor_key == variant.source, flags

    def test_list_sources_cz_models_select_real_laz_variants(self, capsys, tmp_path):
        from kartograf.cli.download_cmd import download_task_arguments
        from kartograf.download.data import validate_data_request

        assert main(["elevation", "list-sources"]) == 0
        lines = capsys.readouterr().out.splitlines()
        header = lines[1]
        choice, country, key, name = (
            header.index(column) for column in ("WYBOR", "KRAJ", "KLUCZ", "NAZWA")
        )
        rows = {
            line[key:name].strip(): line[choice:country].strip()
            for line in lines[2:]
            if line[key:name].strip()
        }
        models = {v.source: v.model for v in variants(product="laz", country="CZ")}
        assert set(models) == {
            key for key in rows if key.endswith("_laz") and key.startswith("cz.")
        }
        for key, model in models.items():
            assert rows[key] == f"--product laz --country cz --model {model}"
            flags = rows[key].split()
            args = create_parser().parse_args(
                [
                    "elevation",
                    "download",
                    *flags,
                    "--sheet",
                    "CTES96",
                    "--vertical-crs",
                    "Bpv",
                ]
            )
            validate_data_request(
                **download_task_arguments(args),
                output_dir=tmp_path / key,
            )

    def test_help_cz_uses_variant_models(self, capsys):
        from kartograf.sources.variants import cz_model_text, cz_resolution_text

        with pytest.raises(SystemExit) as exc:
            main(["elevation", "download", "--help"])
        assert exc.value.code == 0
        text = " ".join(capsys.readouterr().out.split())
        assert f"NMT: {cz_resolution_text('nmt')}" in text
        assert f"NMPT: {cz_resolution_text('nmpt')}" in text
        assert cz_model_text() in text


class TestPlCutoutOnly1m:
    """A PL cutout comes from the WCS channel, which only the 1 m grid variant
    has: another label is an error before any network, no ``--resolution``
    means 1 m.

    WCS answers: the recorded 20 x 20 m windows of ``tests/fixtures/gugik_wcs/
    real_2026_10_11/`` (the bbox lies inside them); PRG mask: all land.
    """

    BBOX = ["--bbox", "567580.6,243664.7,567600.4,243684.3", "--country", "pl"]
    RECORDINGS = {
        "nmt": "nmt_evrf2007_20x20.mime",
        "nmpt": "nmpt_evrf2007_20x20_sf05.mime",
    }
    ALL_LAND = LandMask(
        (
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1e6, 0], [1e6, 1e6], [0, 1e6], [0, 0]]],
            },
        ),
        (),
    )

    def _run(self, tmp_path, product, *extra):
        recording = WCS_FIXTURES / self.RECORDINGS[product]
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=lambda url, **kw: recorded_response(recording))
        with (
            patch("kartograf.transport.http.make_gugik_session", return_value=session),
            patch(
                "kartograf.providers.pl.prg.fetch_land_mask",
                return_value=self.ALL_LAND,
            ) as mask,
        ):
            rc = main(
                ["elevation", "download", "--product", product, *self.BBOX]
                + ["--cutout", "--horizontal-crs", "EPSG:2180"]
                + ["--vertical-crs", "EVRF2007", *extra]
                + ["-o", str(tmp_path / "out"), "-q"]
            )
        return rc, session, mask

    @pytest.mark.parametrize("product", ["nmt", "nmpt"])
    def test_cutout_only_1m(self, tmp_path, capsys, product):
        rc, session, mask = self._run(tmp_path, product, "--resolution", "0.5m")

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: wycinki PL (--cutout) sa tylko 1 m")
        assert "arkusze bez --cutout" in err
        session.get.assert_not_called()
        mask.assert_not_called()
        assert not (tmp_path / "out").exists()

        rc, session, _ = self._run(tmp_path, product)

        assert rc == 0, capsys.readouterr().err
        bbox_dir = tmp_path / "out" / product / "pl_1992_1m_evrf2007" / "bbox"
        assert [p.name for p in bbox_dir.glob("*.tif")] == [
            "567580.6_243664.7_567600.4_243684.3.tif"
        ]
        session.get.assert_called_once()


class TestCmdDownloadBBox:
    """Tests for download command with --bbox option."""

    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_basic(self, mock_manager_class, capsys, tmp_path):
        """Test that --bbox calls find_sheets_for_bbox and download_sheet."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_sheets.assert_called_once()

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_sheet_list_header(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        """D15: the sheet list header = the same as for a cutout (abbreviation >10)."""
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "t.asc")
        mock_find.return_value = [f"N-{i}" for i in range(1, 13)]
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        out = capsys.readouterr().out
        assert (
            "Znaleziono arkuszy w skali 1:10000: 12 dla bbox (resolution: 1m)\n" in out
        )
        assert "  Arkusze: N-1, N-2, N-3, ..., N-11, N-12\n" in out

    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_epsg4326(self, mock_manager_class, capsys, tmp_path):
        """Test --bbox z --bbox-crs EPSG:4326."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "19.93,50.05,19.95,50.07",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_sheets.assert_called_once()

    def test_download_bbox_and_sheet_error(self, capsys):
        """Test oba sheet i --bbox → exit 1."""
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--bbox",
                "419000,230000,426000,237000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Podaj dokladnie jeden wybor obszaru" in captured.err

    def test_download_no_input_error(self, capsys):
        """Test no sheet code and no --bbox → exit 1."""
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Podaj wybor obszaru" in captured.err

    def test_download_bbox_invalid_format(self, capsys):
        """Test of a bad bbox format → exit 1."""
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "not,a,valid,bbox",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Nieprawidlowy bbox" in captured.err

    @pytest.mark.parametrize(
        "bbox", ["invalid", "10,10,5,5", "nan,1,2,3", "1,2,-inf,4", "1,2,3"]
    )
    @pytest.mark.parametrize(
        "extra",
        [[], ["--country", "pl"], ["--country", "cz"], ["--product", "laz"]],
        ids=["auto", "pl", "cz", "laz"],
    )
    def test_download_rejects_bad_bbox_before_network(
        self, bbox, extra, capsys, tmp_path
    ):
        """K7b: a single --bbox parse in all download paths (PL, CZ, LAZ): exit
        code 1, `Error: Invalid bbox format` on stderr (no ValueError, no hint on
        stdout), zero providers. Formerly a reversed bbox went on (a junk sheet),
        and NaN ended with a `ValueError`."""
        with (
            patch("kartograf.download.data.DownloadManager") as manager,
            patch(_CZ_FACTORY_PATCH) as cz_factory,
            patch("kartograf.providers.pl.gugik_laz.GugikLazProvider") as laz,
        ):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    f"--bbox={bbox}",
                    "-o",
                    str(tmp_path),
                    "-q",
                    *extra,
                ]
            )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: Nieprawidlowy bbox" in captured.err
        assert "ValueError" not in captured.err
        assert "Oczekiwano" not in captured.out
        manager.assert_not_called()
        cz_factory.assert_not_called()
        laz.assert_not_called()

    def test_download_bbox_too_few_values(self, capsys):
        """Test of too few values in the bbox → exit 1."""
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "419000,230000,426000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Nieprawidlowy bbox" in captured.err

    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_with_scale(self, mock_manager_class, capsys, tmp_path):
        """PL-1992 is fixed at 1:10000: --scale is an error before any work."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "--scale",
                "1:100000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        assert "--scale nie dotyczy PL-1992" in capsys.readouterr().err
        mock_manager_class.assert_not_called()

    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_shows_summary(self, mock_manager_class, capsys, tmp_path):
        """Test that bbox mode shows summary when not quiet."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "19.93,50.05,19.95,50.07",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Znaleziono" in captured.out
        assert "Arkusze:" in captured.out

    def test_download_parser_has_bbox_options(self):
        """Test that download parser has --bbox and --bbox-crs options."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "419000,230000,426000,237000",
                "--bbox-crs",
                "EPSG:4326",
            ]
        )
        assert args.bbox == "419000,230000,426000,237000"
        assert args.bbox_crs == "EPSG:4326"

    def test_download_parser_bbox_crs_default(self):
        """Test that --bbox-crs defaults to EPSG:2180."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "419000,230000,426000,237000",
            ]
        )
        assert args.bbox_crs == "EPSG:2180"

    def test_download_parser_sheet_optional(self):
        """Test that sheet is now optional."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "419000,230000,426000,237000",
            ]
        )
        assert args.sheet is None
        assert args.bbox == "419000,230000,426000,237000"

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_bbox_list_goes_through_download_sheets(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """The whole sheet list goes via ONE ``download_sheets`` (manager expands)."""
        mock_find.return_value = ["A", "B"]
        mock_manager = _sheet_list_manager(
            tmp_path / "A.asc", tmp_path / "B1.asc", tmp_path / "B2.asc"
        )
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "--country",
                "pl",
                "--workers",
                "1",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_manager.download_sheets.assert_called_once_with(
            ["A", "B"], update=None, on_progress=ANY
        )
        # --workers reaches the manager, not the CLI loop
        assert mock_manager_cls.call_args.kwargs["workers"] == 1
        captured = capsys.readouterr()
        assert "Nowe: 3," in captured.out


class _SheetProvider:
    """Mock of a sheet provider: outcome per sheet code suffix (S2, D2).

    ``outcomes`` maps a sheet code suffix (``"-1"``) to ``"no_coverage"`` /
    ``"fail"``; the other sheets write a file. Every ``download`` call
    lands in ``calls`` - proof that a failure does NOT abort the list.
    """

    default_extension = ".asc"
    vertical_crs = "EVRF2007"
    resolution = "1m"

    def __init__(self, outcomes: dict[str, str]):
        self.outcomes = outcomes
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def download(self, sheet, path, timeout=30):
        from kartograf.exceptions import NoCoverageError

        with self._lock:
            self.calls.append(sheet)
        outcome = next(
            (v for suffix, v in self.outcomes.items() if sheet.endswith(suffix)),
            "ok",
        )
        if outcome == "no_coverage":
            raise NoCoverageError(f"No NMT 1m data available for {sheet}", sheet=sheet)
        if outcome == "fail":
            raise DownloadError(f"timeout {sheet}", sheet=sheet)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
        return path


class TestSheetListExitCode:
    """S2/D2: sheet list mode (bbox/geometry without --cutout) with R5 tolerance.

    A real ``DownloadManager`` + ``FileStorage`` in ``tmp_path``, a mock
    provider - contract tests (exit code, messages, number of tries), not the
    CLI loop.
    """

    _SHEETS = [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]

    @staticmethod
    def _run_bbox(tmp_path, outcomes, *extra, sheets=None):
        from kartograf.download.storage import FileStorage

        provider = _SheetProvider(outcomes)
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with (
            patch(
                "kartograf.download.data._create_provider_and_storage",
                return_value=(provider, storage),
            ),
            patch(
                "kartograf.download.data.find_sheets_for_bbox",
                return_value=list(sheets or TestSheetListExitCode._SHEETS),
            ),
        ):
            rc = main(
                [
                    "elevation",
                    "download",
                    "--sheet-system",
                    "1992",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--bbox",
                    "630000,480000,637000,487000",
                    "-o",
                    str(tmp_path),
                    *extra,
                ]
            )
        files = sorted(
            p.name
            for p in tmp_path.rglob("*.asc")
            if "versions" not in p.relative_to(tmp_path).parts
        )
        return rc, provider, files

    @pytest.mark.parametrize("workers", ["1", "2"])
    def test_mixed_outcomes_try_every_sheet_and_report_both(
        self, tmp_path, capsys, workers
    ):
        """[-1 no data, -2 ok, -3 network error, -4 ok]: 4 tries, 2 files, code 1.

        Before D2 ``--workers 1`` stopped at the first sheet (1 try, 0 files),
        and the thread pool reported only the first failure by race.
        """
        rc, provider, files = self._run_bbox(
            tmp_path, {"-1": "no_coverage", "-3": "fail"}, "--workers", workers
        )

        assert rc == 1
        assert sorted(provider.calls) == self._SHEETS
        assert files == ["N-34-130-D-d-2-2.asc", "N-34-130-D-d-2-4.asc"]
        err = capsys.readouterr().err
        error_line = next(line for line in err.splitlines() if "Error:" in line)
        warning_line = next(line for line in err.splitlines() if "Warning:" in line)
        assert "N-34-130-D-d-2-3" in error_line and "ponow pobranie" in error_line
        assert "N-34-130-D-d-2-3: timeout N-34-130-D-d-2-3" in error_line
        assert all(line.startswith(("Warning:", "Error:")) for line in err.splitlines())
        assert "1 z 4 arkuszy nie pobrano" in error_line
        assert "N-34-130-D-d-2-1" in warning_line
        assert "GUGiK nie ma danych dla 1 z 4 arkuszy" in warning_line
        assert "pobrano 2" in warning_line

    def test_only_no_coverage_with_files_warns_and_returns_0(self, tmp_path, capsys):
        """A sheet without data (sea, abroad) = Warning + exit code 0, no Error."""
        rc, _provider, files = self._run_bbox(tmp_path, {"-1": "no_coverage"})

        assert rc == 0
        assert len(files) == 3
        captured = capsys.readouterr()
        assert "Error:" not in captured.err
        assert "Warning: GUGiK nie ma danych dla 1 z 4 arkuszy" in captured.err
        assert "(N-34-130-D-d-2-1)" in captured.err
        assert "Nowe: 3," in captured.out

    def test_all_no_coverage_returns_1(self, tmp_path, capsys):
        """Zero files and all without data = exit code 1 (nothing to download)."""
        rc, provider, files = self._run_bbox(tmp_path, {"": "no_coverage"})

        assert rc == 1
        assert files == []
        assert len(provider.calls) == 4
        err = capsys.readouterr().err
        assert "Error: GUGiK nie ma danych dla zadnego z 4 arkuszy" in err
        assert "ponow pobranie" not in err

    def test_quiet_keeps_warning_and_error_on_stderr(self, tmp_path, capsys):
        """-q silences stdout, but Warning:/Error: go to stderr."""
        rc, _provider, _files = self._run_bbox(
            tmp_path, {"-1": "no_coverage", "-3": "fail"}, "-q"
        )

        assert rc == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Warning:" in captured.err and "Error:" in captured.err

    def test_coarse_sheet_expands_in_manager(self, tmp_path, capsys):
        """The manager expands a coarser code; a leaf failure is in the summary."""
        rc, provider, files = self._run_bbox(
            tmp_path,
            {"-2-3": "fail"},
            sheets=["N-34-130-D-d-2"],
        )

        assert rc == 1
        assert sorted(provider.calls) == self._SHEETS
        assert len(files) == 3
        err = capsys.readouterr().err
        assert "Error: 1 z 4 arkuszy nie pobrano" in err
        assert "N-34-130-D-d-2-3" in err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_mode_uses_same_finish(
        self, mock_overall, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry without --cutout: the same R5 tolerance as --bbox."""
        from kartograf.download.storage import FileStorage

        shp_file = tmp_path / "area.shp"
        shp_file.touch()
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw - deep inside PL, auto-split will not touch CZ
        mock_find.return_value = list(self._SHEETS)
        provider = _SheetProvider({"-1": "no_coverage"})
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with patch(
            "kartograf.download.data._create_provider_and_storage",
            return_value=(provider, storage),
        ):
            rc = main(
                [
                    "elevation",
                    "download",
                    "--sheet-system",
                    "1992",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(shp_file),
                    "-o",
                    str(tmp_path),
                ]
            )

        assert rc == 0
        assert len(provider.calls) == 4
        captured = capsys.readouterr()
        assert "Warning: GUGiK nie ma danych dla 1 z 4 arkuszy" in captured.err
        assert "Nowe: 3," in captured.out


class TestProgressNoCoverage:
    """D11: a sheet without data has its own progress bar icon."""

    def test_no_coverage_prints_empty_set_icon(self, capsys):
        on_progress = create_progress_callback(quiet=False)
        on_progress(
            DownloadProgress(
                current=1, total=2, sheet="N-1", status="no_coverage", message="sea"
            )
        )
        on_progress(DownloadProgress(current=2, total=2, sheet="N-2", status="failed"))
        out = capsys.readouterr().out
        assert "1/2 0 N-1" in out and "2/2 x N-2" in out


# ===========================================================================
# Landcover CLI tests
# ===========================================================================


def _lc_result(path: Path):
    """A land cover result for a mocked ``LandCoverManager``."""
    from kartograf.download.fetch import VersionedFile
    from kartograf.landcover.manager import LandCoverResult

    return LandCoverResult(
        "u", VersionedFile(path, "new", "2026-10-12", "0" * 64, path)
    )


def _lc_area(path: Path):
    from kartograf.landcover.manager import LandCoverAreaResult

    return LandCoverAreaResult((_lc_result(path),))


class TestCmdLandcoverDownload:
    """Tests for landcover download CLI."""

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_teryt(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --teryt calls manager.download with teryt."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.output_dir = tmp_path
        mock_mgr.download.return_value = _lc_area(tmp_path / "out.gpkg")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--teryt",
                "1465",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_mgr.download.assert_called_once()
        call_kwargs = mock_mgr.download.call_args
        assert call_kwargs.kwargs.get("teryt") == "1465"

    def test_soil_download_has_no_teryt(self, capsys, tmp_path):
        """SoilGrids has no powiat selection: ``soil download --teryt`` is an
        input error of the group, no data for a guessed area."""
        out = tmp_path / "out"
        with pytest.raises(SystemExit) as exc:
            main(
                ["soil", "download", "--teryt", "1465", "--property", "soc"]
                + ["--depth", "0-5cm", "--stat", "mean", "-o", str(out)]
            )
        assert exc.value.code == 2
        assert "unrecognized arguments: --teryt 1465" in capsys.readouterr().err
        assert not out.exists()

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_sheet(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --sheet (BDOT10k) downloads every powiat of the sheet."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.output_dir = tmp_path
        mock_mgr.download.return_value = _lc_area(tmp_path / "out.gpkg")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--sheet",
                "N-34-130-D",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_mgr.download.assert_called_once()
        call_kwargs = mock_mgr.download.call_args
        assert call_kwargs.kwargs.get("sheet") == "N-34-130-D"
        assert "out.gpkg: nowa wersja " in capsys.readouterr().out

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_bbox_success(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --bbox (BDOT10k) downloads every powiat of the bbox."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.output_dir = tmp_path
        mock_mgr.download.return_value = _lc_area(tmp_path / "out.gpkg")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--bbox",
                "450000,550000,460000,560000",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_mgr.download.assert_called_once()
        assert mock_mgr.download.call_args.kwargs.get("bbox") is not None
        captured = capsys.readouterr()
        assert "out.gpkg: nowa wersja " in captured.out

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_source_corine(self, mock_mgr_cls, capsys, tmp_path):
        """--source corine creates manager with corine provider."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "CORINE Land Cover"
        mock_mgr.output_dir = tmp_path
        mock_mgr.download.return_value = _lc_area(tmp_path / "out.png")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "corine",
                "--sheet",
                "N-34-130-D",
                "--year",
                "2018",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        # Manager was created with provider="corine"
        mock_mgr_cls.assert_called_once()
        call_kwargs = mock_mgr_cls.call_args
        assert call_kwargs.kwargs.get("provider") == "corine"

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_error(self, mock_mgr_cls, capsys, tmp_path):
        """DownloadError in download -> exit 1."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.download.side_effect = DownloadError("Network error")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--teryt",
                "1465",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_landcover_download_multiple_selection(self, capsys):
        """Multiple selection methods -> exit 1."""
        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "-o",
                "unused",
                "--teryt",
                "1465",
                "--sheet",
                "N-34-130-D",
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "Error: Podaj dokladnie jeden wybor" in err

    @pytest.mark.parametrize(
        ("flags", "missing", "choices"),
        [
            (["-o", "out"], "--source", "bdot10k"),
            (["--source", "bdot10k"], "--output", "katalog"),
        ],
    )
    def test_missing_manager_argument_fails_before_download(
        self, flags, missing, choices, capsys
    ):
        """CLI checks the arguments needed to construct the manager."""
        with patch("kartograf.cli.landcover_cmd.LandCoverManager") as manager:
            rc = main(["landcover", "download", "--sheet", "N-34-130-D", *flags])
        assert rc == 1
        manager.assert_not_called()
        err = capsys.readouterr().err
        assert err.startswith("Error: ")
        assert missing in err and choices in err

    def test_list_layers_without_source_fails_with_choices(self, capsys):
        rc = main(["landcover", "list-layers"])
        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: --source")
        assert all(source in err for source in ("bdot10k", "corine"))


# ===========================================================================
# Soil CLI tests
# ===========================================================================


def _hsg_result(path: Path):
    """An HSG result for a mocked ``HSGCalculator``."""
    from kartograf.download.fetch import VersionedFile
    from kartograf.hydrology.hsg import HsgResult

    return HsgResult("u", VersionedFile(path, "new", "2.0", "0" * 64, path), ())


class TestCmdSoil:
    """Tests for soil HSG CLI behavior."""

    def test_soil_help(self, capsys):
        """The soil group exposes download, HSG and source discovery."""
        result = main(["soil"])
        assert result == 0
        captured = capsys.readouterr()
        assert all(name in captured.out for name in ("download", "hsg", "list-sources"))

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_success(self, mock_calc_cls, capsys, tmp_path):
        """soil hsg --sheet -> success output."""
        mock_calc = Mock()
        mock_calc.calculate_hsg.return_value = _hsg_result(tmp_path / "hsg.tif")
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "N-34-130-D",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "hsg.tif: nowa wersja" in captured.out
        mock_calc.calculate_hsg.assert_called_once()

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_with_stats(self, mock_calc_cls, capsys, tmp_path):
        """soil hsg --stats prints statistics."""
        mock_calc = Mock()
        mock_calc.calculate_hsg.return_value = _hsg_result(tmp_path / "hsg.tif")
        mock_calc.get_hsg_statistics.return_value = {
            "A": {
                "count": 100,
                "area_m2": 10000,
                "area_ha": 1.0,
                "percent": 50.0,
                "description": "High infiltration",
            },
            "B": {
                "count": 50,
                "area_m2": 5000,
                "area_ha": 0.5,
                "percent": 25.0,
                "description": "Moderate infiltration",
            },
            "C": {
                "count": 30,
                "area_m2": 3000,
                "area_ha": 0.3,
                "percent": 15.0,
                "description": "Slow infiltration",
            },
            "D": {
                "count": 20,
                "area_m2": 2000,
                "area_ha": 0.2,
                "percent": 10.0,
                "description": "Very slow infiltration",
            },
        }
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "N-34-130-D",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path),
                "--stats",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "Statystyki HSG" in captured.out
        assert "Grupa A" in captured.out
        assert "50.0%" in captured.out

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_error(self, mock_calc_cls, capsys, tmp_path):
        """soil hsg raises DownloadError -> exit 1."""
        mock_calc = Mock()
        mock_calc.calculate_hsg.side_effect = DownloadError("Network error")
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "N-34-130-D",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_sheet_passed_to_library(self, mock_calc_cls, tmp_path):
        """--sheet/--depth/-o go to the library as given (canonical code there)."""
        mock_calc = mock_calc_cls.return_value
        mock_calc.calculate_hsg.return_value = _hsg_result(tmp_path / "hsg.tif")
        out = tmp_path / "out"

        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "M-33-036-A",
                "-o",
                str(out),
                "--depth",
                "0-5cm",
            ]
        )

        assert result == 0
        assert mock_calc_cls.call_args.args[0] == out
        kwargs = mock_calc.calculate_hsg.call_args.kwargs
        assert (kwargs["sheet"], kwargs["depth"]) == ("M-33-036-A", "0-5cm")
        assert "stat" not in kwargs

    def test_soilgrids_hsg_out_of_range_sheet(self, capsys, tmp_path):
        """A7: an out-of-range sheet -> Error on stderr, code 1, before network."""
        out = tmp_path / "out"

        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "N-34-999-D",
                "-o",
                str(out),
                "--depth",
                "0-5cm",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Error: " in captured.err
        assert "poza zakresem" in captured.err
        assert not out.exists()

    @pytest.mark.parametrize(
        "bbox", ["invalid", "10,10,5,5", "nan,1,2,3", "1,2,-inf,4", "1,2,3"]
    )
    def test_soilgrids_hsg_rejects_bad_bbox(self, bbox, capsys, tmp_path):
        """K7a: bad --bbox -> Error on stderr, code 1, the calculator never starts."""
        with patch("kartograf.hydrology.HSGCalculator") as calc_cls:
            result = main(
                [
                    "soil",
                    "hsg",
                    f"--bbox={bbox}",
                    "-o",
                    str(tmp_path),
                    "--depth",
                    "0-5cm",
                ]
            )
        assert result == 1
        calc_cls.return_value.calculate_hsg.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: Nieprawidlowy bbox" in captured.err
        assert "ValueError" not in captured.err
        assert "Oczekiwano" not in captured.out

    def test_hsg_missing_output_fails_before_calculation(self, capsys):
        with patch("kartograf.hydrology.HSGCalculator") as calculator:
            rc = main(["soil", "hsg", "--sheet", "N-34-130-D", "--depth", "0-5cm"])
        assert rc == 1
        calculator.assert_not_called()
        assert "Error: --output" in capsys.readouterr().err

    def test_hsg_missing_depth_is_library_error(self, tmp_path, capsys):
        """The library text (same as ``calculate_hsg(depth=None)``), no network."""
        rc = main(["soil", "hsg", "--sheet", "N-34-130-D", "-o", str(tmp_path)])
        assert rc == 1
        assert capsys.readouterr().err.startswith("Error: --depth wymagane: 0-5cm")

    def test_soilgrids_hsg_no_selection(self, capsys):
        """soil hsg without --sheet or --bbox -> exit 1."""
        result = main(["soil", "hsg", "--output", "unused", "--depth", "0-5cm"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: Podaj dokladnie jeden wybor" in captured.err

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_by_bbox(self, mock_calc_cls, capsys, tmp_path):
        """soil hsg --bbox -> calculate_hsg_by_bbox called."""
        mock_calc = Mock()
        mock_calc.calculate_hsg.return_value = _hsg_result(tmp_path / "hsg.tif")
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soil",
                "hsg",
                "--bbox",
                "450000,550000,460000,560000",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_calc.calculate_hsg.assert_called_once()


def test_landcover_download_no_selection(capsys):
    """No selection method -> exit 1."""
    result = main(["landcover", "download", "--source", "bdot10k", "-o", "unused"])
    assert result == 1
    captured = capsys.readouterr()
    assert "Error: Podaj dokladnie jeden wybor" in captured.err


# ===========================================================================
# Geometry CLI tests — download command
# ===========================================================================


class TestCmdDownloadGeometry:
    """Tests for download command with --geometry option."""

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_basic(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry calls find_sheets_for_geometry and downloads."""
        # Create a fake SHP file
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw (20.90-21.05E) - deep inside PL, auto-split will not touch CZ
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        mock_manager.download_sheets.assert_called_once()

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_with_layer(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry --layer passes layer parameter."""
        gpkg_file = write_gpkg_layers(tmp_path / "area.gpkg", ["my_layer", "other"])

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw — deep inside PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(gpkg_file),
                "--layer",
                "my_layer",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("layer") == "my_layer"
        assert "warstw" not in capsys.readouterr().err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_cli_geometry_multi_layer_info_once(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """GPKG with several layers and no --layer: ONE Info naming the first
        layer and the others; every reader then gets the explicit name."""
        gpkg_file = write_gpkg_layers(tmp_path / "area.gpkg", ["layer_a", "layer_b"])
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw — deep inside PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_cls.return_value = _sheet_list_manager(tmp_path / "test.asc")

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(gpkg_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        info = [
            line for line in capsys.readouterr().err.splitlines() if "warstw" in line
        ]
        assert len(info) == 1
        assert info[0].startswith("Info:")
        assert "'layer_a'" in info[0] and "layer_b" in info[0]
        assert "--layer" in info[0]
        for mock in (mock_find, mock_overall, mock_read_crs):
            assert all(c.kwargs.get("layer") == "layer_a" for c in mock.call_args_list)

    @pytest.mark.parametrize("kind", ["single_gpkg", "shp"])
    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_cli_geometry_single_layer_no_info(
        self,
        mock_overall,
        mock_manager_cls,
        mock_find,
        mock_read_crs,
        kind,
        capsys,
        tmp_path,
    ):
        if kind == "shp":
            path = tmp_path / "area.shp"
            path.touch()
        else:
            path = write_gpkg_layers(tmp_path / "area.gpkg", ["only"])
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_cls.return_value = _sheet_list_manager(tmp_path / "test.asc")

        assert (
            main(
                [
                    "elevation",
                    "download",
                    "--sheet-system",
                    "1992",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(path),
                    "-o",
                    str(tmp_path),
                ]
            )
            == 0
        )
        assert "warstw" not in capsys.readouterr().err

    def test_cli_geometry_unknown_layer_error(self, capsys, tmp_path):
        gpkg_file = write_gpkg_layers(tmp_path / "area.gpkg", ["layer_a", "layer_b"])
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(gpkg_file),
                "--layer",
                "x",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:") and "layer_a, layer_b" in err

    def test_download_geometry_and_sheet_error(self, capsys, tmp_path):
        """--geometry + sheet -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--geometry",
                str(shp_file),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Podaj dokladnie jeden wybor obszaru" in captured.err

    def test_download_geometry_and_bbox_error(self, capsys, tmp_path):
        """--geometry + --bbox -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp_file),
                "--bbox",
                "419000,230000,426000,237000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Podaj dokladnie jeden wybor obszaru" in captured.err

    def test_download_geometry_file_not_found(self, capsys, tmp_path):
        """--geometry with nonexistent file -> error."""
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(tmp_path / "nonexistent.shp"),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Brak pliku" in captured.err

    def test_download_no_input_error_updated(self, capsys):
        """No input at all shows updated error message."""
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "--geometry" in captured.err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_list_goes_through_download_sheets(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """The whole sheet list goes via ONE ``download_sheets`` (manager expands)."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw - deep inside PL, auto-split will not touch CZ
        mock_find.return_value = ["A", "B"]
        mock_manager = _sheet_list_manager(
            tmp_path / "A.asc", tmp_path / "B1.asc", tmp_path / "B2.asc"
        )
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp_file),
                "--country",
                "pl",
                "--workers",
                "1",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_manager.download_sheets.assert_called_once()
        assert mock_manager.download_sheets.call_args.args[0] == ["A", "B"]
        captured = capsys.readouterr()
        assert "Nowe: 3," in captured.out


# ===========================================================================
# Geometry CLI tests — landcover download command
# ===========================================================================


class TestCmdLandcoverDownloadGeometry:
    """Tests for landcover download command with --geometry option."""

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_geometry_basic(self, mock_mgr_cls, capsys, tmp_path):
        """--geometry/--layer go to the library unchanged (envelope there)."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.output_dir = tmp_path
        mock_mgr.download.return_value = _lc_area(tmp_path / "out.gpkg")
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--geometry",
                str(shp_file),
                "--layer",
                "obszar",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        kwargs = mock_mgr.download.call_args.kwargs
        assert kwargs["geometry"] == shp_file and kwargs["layer"] == "obszar"
        assert kwargs["bbox"] is None
        assert "out.gpkg: nowa wersja " in capsys.readouterr().out

    def test_landcover_geometry_and_teryt_error(self, capsys, tmp_path):
        """--geometry + --teryt -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--geometry",
                str(shp_file),
                "--teryt",
                "1465",
                "-o",
                str(tmp_path / "out"),
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "Error: Podaj dokladnie jeden wybor" in err

    def test_landcover_geometry_file_not_found(self, capsys, tmp_path):
        """--geometry with nonexistent file -> error."""
        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "--geometry",
                str(tmp_path / "nonexistent.shp"),
                "-o",
                str(tmp_path / "out"),
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Brak pliku" in captured.err


# ===========================================================================
# Geometry CLI tests — soil hsg command
# ===========================================================================


class TestCmdSoilgridsHsgGeometry:
    """Tests for soil hsg command with --geometry option."""

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_geometry(self, mock_calc_cls, capsys, tmp_path):
        """--geometry/--layer go to calculate_hsg unchanged (envelope there)."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_calc = Mock()
        mock_calc.calculate_hsg.return_value = _hsg_result(tmp_path / "hsg.tif")
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soil",
                "hsg",
                "--depth",
                "0-5cm",
                "--geometry",
                str(shp_file),
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        kwargs = mock_calc.calculate_hsg.call_args.kwargs
        assert kwargs["geometry"] == shp_file and kwargs["layer"] is None
        assert kwargs["bbox"] is None and kwargs["sheet"] is None

    def test_soilgrids_hsg_geometry_and_sheet_error(self, capsys, tmp_path):
        """--geometry + --sheet -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "soil",
                "hsg",
                "--depth",
                "0-5cm",
                "--geometry",
                str(shp_file),
                "--sheet",
                "N-34-130-D",
                "-o",
                str(tmp_path / "out"),
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "Error: Podaj dokladnie jeden wybor" in err


# ===========================================================================
# PL-2000 CLI tests
# ===========================================================================


class TestFormatSheetInfoPL2000:
    """Tests for format_sheet_info() with PL-2000 sheets."""

    def test_format_pl2000_sheet_basic(self):
        """PL-2000 sheet shows correct layout and components."""
        parser = SheetParser("6.179.12")
        output = format_sheet_info(parser)

        assert "6.179.12" in output
        assert "1:10000" in output
        assert "2000" in output
        assert "Czlony:" in output
        assert "strefa: 6" in output
        assert "pas: 179" in output
        assert "slup: 12" in output

    def test_format_pl2000_shows_strefa(self):
        """PL-2000 output should include Strefa line."""
        parser = SheetParser("6.179.12")
        output = format_sheet_info(parser)

        assert "Strefa: 6" in output

    def test_format_pl2000_shows_native_crs(self):
        """PL-2000 output should include native CRS."""
        parser = SheetParser("6.179.12")
        output = format_sheet_info(parser)

        assert "Natywny CRS: EPSG:2177" in output

    def test_format_pl2000_zone5(self):
        """Zone 5 shows EPSG:2176."""
        parser = SheetParser("5.100.10")
        output = format_sheet_info(parser)

        assert "Strefa: 5" in output
        assert "Natywny CRS: EPSG:2176" in output

    def test_format_pl2000_zone8(self):
        """Zone 8 shows EPSG:2179."""
        parser = SheetParser("8.100.10")
        output = format_sheet_info(parser)

        assert "Strefa: 8" in output
        assert "Natywny CRS: EPSG:2179" in output

    def test_format_pl1992_no_strefa(self):
        """PL-1992 sheet should NOT show Strefa or Natywny CRS."""
        parser = SheetParser("N-34-130-D")
        output = format_sheet_info(parser)

        assert "Strefa:" not in output
        assert "Natywny CRS:" not in output


class TestParsePL2000Command:
    """Tests for 'kartograf parse' with PL-2000 sheets."""

    def test_parse_pl2000_sheet(self, capsys):
        """kartograf parse 6.179.12 should work."""
        result = main(["parse", "6.179.12"])

        assert result == 0
        captured = capsys.readouterr()
        assert "6.179.12" in captured.out
        assert "1:10000" in captured.out
        assert "2000" in captured.out

    def test_parse_pl2000_shows_strefa_in_output(self, capsys):
        """Parse command output includes zone info for PL-2000."""
        result = main(["parse", "6.179.12"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Strefa: 6" in captured.out
        assert "Natywny CRS: EPSG:2177" in captured.out

    def test_parse_pl2000_finer_scale(self, capsys):
        """kartograf parse 6.179.12.15 should show 1:2000."""
        result = main(["parse", "6.179.12.15"])

        assert result == 0
        captured = capsys.readouterr()
        assert "1:2000" in captured.out
        assert "Strefa: 6" in captured.out

    def test_parse_pl2000_invalid(self, capsys):
        """Invalid PL-2000 sheet returns error."""
        result = main(["parse", "9.179.12"])

        assert result == 1


class TestCreateParserDownloadSystem:
    """Tests for --sheet-system argument on download subparser."""

    def test_sheet_system_default_is_none(self):
        """--sheet-system defaults to None (sentinel; resolved per country later)."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--bbox", "419000,230000,426000,237000"]
        )
        assert args.sheet_system is None

    def test_sheet_system_2000_accepted(self):
        """--sheet-system 2000 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "419000,230000,426000,237000",
                "--sheet-system",
                "2000",
            ]
        )
        assert args.sheet_system == "2000"

    def test_sheet_system_1992_accepted(self):
        """--sheet-system 1992 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "419000,230000,426000,237000",
                "--sheet-system",
                "1992",
            ]
        )
        assert args.sheet_system == "1992"

    def test_system_invalid_rejected(self):
        """--sheet-system invalid is rejected."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "elevation",
                    "download",
                    "--bbox",
                    "419000,230000,426000,237000",
                    "--sheet-system",
                    "xyz",
                ]
            )


class TestCreateParserBBoxCrsExtended:
    """Tests for extended --bbox-crs choices with PL-2000 CRS."""

    def test_bbox_crs_epsg2177(self):
        """--bbox-crs EPSG:2177 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "6500000,5800000,6510000,5810000",
                "--bbox-crs",
                "EPSG:2177",
            ]
        )
        assert args.bbox_crs == "EPSG:2177"

    def test_bbox_crs_epsg2176(self):
        """--bbox-crs EPSG:2176 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "5500000,5800000,5510000,5810000",
                "--bbox-crs",
                "EPSG:2176",
            ]
        )
        assert args.bbox_crs == "EPSG:2176"

    def test_bbox_crs_epsg2178(self):
        """--bbox-crs EPSG:2178 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "7500000,5800000,7510000,5810000",
                "--bbox-crs",
                "EPSG:2178",
            ]
        )
        assert args.bbox_crs == "EPSG:2178"

    def test_bbox_crs_epsg2179(self):
        """--bbox-crs EPSG:2179 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--bbox",
                "8500000,5800000,8510000,5810000",
                "--bbox-crs",
                "EPSG:2179",
            ]
        )
        assert args.bbox_crs == "EPSG:2179"


class TestDownloadBBoxSystem:
    """Tests for download --bbox --sheet-system integration."""

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_system_2000_passes_param(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--sheet-system 2000 passes sheet_system='2000' to find_sheets_for_bbox."""
        mock_find.return_value = ["6.179.12"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "--sheet-system",
                "2000",
                "--scale",
                "1:2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("sheet_system") == "2000" or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "2000"
        )

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_download_bbox_default_system_1992(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """Explicit sheet_system='1992' is passed to find_sheets_for_bbox."""
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("sheet_system") == "1992" or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "1992"
        )


class TestDownloadGeometrySystem:
    """Tests for download --geometry --sheet-system integration."""

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_system_2000(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry --sheet-system 2000 reaches find_sheets_for_geometry."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw - deep inside PL (--sheet-system applies to PL only)
        mock_find.return_value = ["6.179.12"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp_file),
                "--sheet-system",
                "2000",
                "--scale",
                "1:2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("sheet_system") == "2000"

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_default_system_1992(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """Explicit sheet_system='1992' for geometry download."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw — deep inside PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("sheet_system") == "1992"


def _selection(tiles, superseded=()):
    from kartograf.providers.pl.gugik_laz import LazTileSelection

    return LazTileSelection(tiles=tuple(tiles), superseded=tuple(superseded))


def _write_laz_tile(_url, target, **_kwargs):
    """Stub tile bytes at the staged location consumed by the version store."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"LASF")
    return target


class TestCmdDownloadLaz:
    """Tests for the LAZ product flow in the download command."""

    def _fake_tiles(self):
        from kartograf.providers.pl.gugik_laz import LazTile

        return [
            LazTile(
                sheet="N-33-131-B-a-1-1-4",
                url="https://opendata.geoportal.gov.pl/x/81121_1_N-33-131-B-a-1-1-4.laz",
                year=2024,
                density=25,
                crs="PL-2000:S6",
                min_x=530500,
                min_y=382500,
                max_x=531000,
                max_y=383000,
            ),
            LazTile(
                sheet="N-33-131-B-a-1-2-3",
                url="https://opendata.geoportal.gov.pl/x/81279_2_N-33-131-B-a-1-2-3.laz",
                year=2024,
                density=25,
                crs="PL-2000:S6",
                min_x=531000,
                min_y=383000,
                max_x=531500,
                max_y=383500,
            ),
        ]

    def test_parser_accepts_laz_and_flags(self):
        parser = create_parser()
        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "--year",
                "2024",
                "--min-density",
                "12",
            ]
        )
        assert args.product == "laz"
        assert args.year == 2024
        assert args.min_density == 12

    def test_laz_invalid_product_choice_rejected(self):
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["elevation", "download", "--sheet", "X", "--product", "nope"]
            )

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_sheet_mode_downloads_all_tiles(self, mock_provider_cls, tmp_path):
        """sheet code → discover tiles → download each via provider.download_tile."""
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download_tile.side_effect = _write_laz_tile
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        # discovery happened once, download once per tile
        instance.select_tiles.assert_called_once()
        assert instance.download_tile.call_count == 2
        # bbox passed to select_tiles is in EPSG:2180
        bbox_arg = instance.select_tiles.call_args[0][0]
        assert bbox_arg.crs == "EPSG:2180"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_bbox_mode(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download_tile.side_effect = _write_laz_tile
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "530000,382000,533000,386000",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        assert instance.download_tile.call_count == 2

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_tile_failures_are_error_with_full_list(
        self, mock_provider_cls, tmp_path, capsys
    ):
        """Tile failures -> `Error:` (not `Warning:`), the FULL list, exit code 1 (N6).

        Pattern: `_finish_pl_sheets` - `Warning:` means exit code 0, and the user
        must get every failed tile to know what to retry.
        """
        from dataclasses import replace

        from kartograf.exceptions import DownloadError

        base = self._fake_tiles()[0]
        sheets = [f"N-33-131-B-a-1-1-{i}" for i in range(1, 9)]
        tiles = [
            replace(base, sheet=g, url=f"https://opendata.geoportal.gov.pl/x/{g}.laz")
            for g in sheets
        ]
        good = sheets[0]

        def _download(url, target, **_kwargs):
            if good in url:
                return _write_laz_tile(url, target)
            raise DownloadError(f"HTTP 503 dla {url}")

        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(tiles)
        instance.download_tile.side_effect = _download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        err = capsys.readouterr().err
        assert result == 1
        assert "Warning:" not in err
        assert "Error: 7 z 8 kafli LAZ nie pobrano" in err
        for tile in tiles[1:]:
            assert tile.sheet in err
        assert f"{good}:" not in err

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_year_and_density_forwarded(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download_tile.side_effect = _write_laz_tile
        mock_provider_cls.return_value = instance

        main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "--year",
                "2023",
                "--min-density",
                "12",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        kwargs = instance.select_tiles.call_args.kwargs
        assert kwargs["min_year"] == kwargs["max_year"] == 2023
        assert kwargs.get("year") is None
        assert kwargs["min_density"] == 12

    def test_laz_no_tiles_found_errors(self, capsys, tmp_path):
        capabilities = Mock(
            text="""\
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0">
  <wfs:FeatureTypeList>
    <wfs:FeatureType>
      <wfs:Name>gugik:SkorowidzDanychPomiarowychLIDAR2024</wfs:Name>
    </wfs:FeatureType>
    <wfs:FeatureType>
      <wfs:Name>gugik:SkorowidzDanychPomiarowychLIDAR2023</wfs:Name>
    </wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>"""
        )
        empty_page = Mock(
            text='<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
            'numberReturned="0"/>'
        )

        with patch(
            "requests.Session.get", side_effect=[capabilities, empty_page, empty_page]
        ) as get:
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "M-34-27-B-b-2-1",
                    "--product",
                    "laz",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )
        assert result == 1
        err = capsys.readouterr().err
        assert "Brak kafli LAZ" in err
        # N7: discovery is all-or-nothing, so an empty list = extent/filters
        assert "--year" in err and "wszystkie roczniki WFS odpowiedzialy" in err
        assert get.call_count == 3  # Capabilities and both available years completed.

    @pytest.mark.parametrize("year_args", [[], ["--year", "2024"]])
    def test_laz_wfs_failure_reports_network_error(self, year_args, capsys, tmp_path):
        with (
            patch(
                "requests.Session.get",
                side_effect=requests.ConnectionError("connection reset by peer"),
            ) as get,
            patch("kartograf.transport.http.time.sleep"),
        ):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "M-34-27-B-b-2-1",
                    "--product",
                    "laz",
                    *year_args,
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 1
        err = capsys.readouterr().err
        assert "Error: WFS" in err
        assert "connection reset by peer" in err
        assert "Brak kafli LAZ" not in err
        assert get.call_count == 3

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_writes_sidecar_next_to_tile(self, mock_provider_cls, tmp_path):
        """Every downloaded tile gets a <name>.laz.meta.json sidecar."""
        import json

        from kartograf.download.storage import FileStorage

        tile = self._fake_tiles()[0]
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection([tile])

        def fake_download(url, target, **kwargs):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"LASF")
            return target

        instance.download_tile.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        sidecars = [
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        ]
        assert len(sidecars) == 1
        sidecar = sidecars[0]
        assert sidecar.name == f"{tile.filename}.meta.json"
        target = sidecar.parent / tile.filename
        assert target.exists()
        assert "pl_2000_evrf2007" in str(sidecar.parent)
        # Finding 8 (P-09): the file lands EXACTLY where the library API points for the
        # same tile (uklad_xy PL-2000:S6, hyphenated sheet code) - not only the
        # segment substring (as above), but also path equality AND the literal
        # segment. Equality with ``FileStorage(...).get_raw_path(...)`` alone is not
        # enough: if the same (potentially mutated) function computed both sides, the
        # assertion would stay green even with broken production code.
        expected_storage = FileStorage(
            tmp_path, product="laz", resolution=None, vertical_crs="EVRF2007"
        )
        assert target == expected_storage.get_raw_path(
            tile.sheet, tile.filename, system=tile.system
        )
        assert target.parts[-10:-8] == ("laz", "pl_2000_evrf2007")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.laz"
        assert payload["vertical_crs"] == "EPSG:9651"
        assert payload["extra"]["tile_sheet"] == tile.sheet
        assert payload["extra"]["year"] == tile.year
        assert payload["request"]["bbox_crs"] == "EPSG:2180"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_segment_carries_vertical_crs_from_flag(
        self, mock_provider_cls, tmp_path
    ):
        """The {vcrs} segment carries --vertical-crs, not the FileStorage default.

        Without this assertion the test would also pass if someone removed
        ``vertical_crs=vertical_crs`` from the ``FileStorage`` constructor in
        ``_cmd_download_laz`` - the FileStorage default ("EVRF2007") would mask
        the error exactly as it masked the side effect of Task 2 (LAZ segment
        always "evrf2007" regardless of the flag). This test forces
        KRON86 (different from the default) and checks that it reached the segment
        of both the tile and the sidecar.
        """
        import json

        tile = self._fake_tiles()[0]
        instance = Mock()
        instance.vertical_crs = "KRON86"
        instance.select_tiles.return_value = _selection([tile])

        def fake_download(url, target, **kwargs):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"LASF")
            return target

        instance.download_tile.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        sidecars = [
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        ]
        assert len(sidecars) == 1
        sidecar = sidecars[0]
        assert "pl_2000_kron86" in str(sidecar.parent)
        kafel = sidecar.parent / tile.filename
        assert kafel.exists()
        assert "pl_2000_kron86" in str(kafel.parent)
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["vertical_crs"] == "EPSG:9650"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_sidecar_horizontal_crs_comes_from_tile(
        self, mock_provider_cls, tmp_path
    ):
        """N8: a PL-2000:S7 tile gets EPSG:2178 (not the WFS channel's default CRS)."""
        from dataclasses import replace

        tile = replace(self._fake_tiles()[0], crs="PL-2000:S7")
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection([tile])

        def fake_download(url, target, **kwargs):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"LASF")
            return target

        instance.download_tile.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        (sidecar,) = (
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["horizontal_crs"] == "EPSG:2178"

    def test_laz_invalid_sheet_errors(self, capsys, tmp_path):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "NOT-A-GODLO!!",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1

    def test_laz_missing_geometry_file_errors(self, capsys, tmp_path):
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(tmp_path / "missing.shp"),
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        assert "brak pliku" in capsys.readouterr().err.lower()


def _cz_args(tmp_path, **overrides):
    """Namespace for direct _cmd_download_cz calls (2m/Bpv; SM5 sheets: 5m only)."""
    sheet = overrides.get("sheet", "302_5550")
    sm5 = sheet is not None and re.fullmatch(r"\s*[A-Z]{4}\d{2}\s*", sheet)
    base = dict(
        sheet="302_5550",
        bbox=None,
        bbox_crs="EPSG:2180",
        geometry=None,
        layer=None,
        scale=None,
        output=str(tmp_path),
        force=False,
        quiet=True,
        vertical_crs="Bpv",
        resolution=None if sm5 else "2m",
        product="nmt",
        sheet_system=None,
        country="cz",
        horizontal_crs=None,
        workers=1,
        year=None,
        min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _cmd_download_cz(args, bbox=None):
    """The CZ request described by ``_cz_args`` run through ``main`` (a sheet
    code, or ``bbox`` with its CRS as ``--bbox-crs``; an area is a cutout,
    by default in the native EPSG:5514)."""
    argv = [
        "elevation",
        "download",
        "--product",
        args.product,
        "--country",
        args.country,
    ]
    argv += ["-o", str(args.output), "--vertical-crs", args.vertical_crs]
    if args.resolution:
        argv += ["--resolution", args.resolution]
    if bbox is not None:
        coords = f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y}"
        argv += [f"--bbox={coords}", "--bbox-crs", bbox.crs]
        argv += ["--cutout", "--horizontal-crs", args.horizontal_crs or "EPSG:5514"]
    else:
        argv += ["--sheet", args.sheet]
        if args.horizontal_crs:
            argv += ["--cutout", "--horizontal-crs", args.horizontal_crs]
    for flag in ("force", "quiet", "upgrade", "check_updates"):
        if getattr(args, flag, False):
            argv.append("--" + flag.replace("_", "-"))
    if args.sheet_system:
        argv += ["--sheet-system", args.sheet_system]
    return main(argv)


def _cz_provider_mock(resolution="2m"):
    """``CuzkRasterProvider`` mock (NMT) for the CLI flow.

    The route of a sheet or cutout is the row of the real variant registry
    (``route_of``): ``target_crs`` = the CRS of a cutout (``None`` = native
    EPSG:5514; ``cz_factory`` sets it from the factory call),
    ``vertical_pinned`` = the Bpv->EVRF2007 operation of a non-native route.
    """
    provider = Mock()
    provider.descriptor_key = "cz.cuzk.dmr5g" if resolution == "2m" else "cz.cuzk.dmr4g"
    provider.product = "nmt"
    provider.resolution = resolution
    provider.vertical_crs = "Bpv"
    provider.target_crs = None
    provider.vertical_pinned = None
    provider.file_signal.return_value = {
        "etag": '"d19f2c604d89dc1:0"',
        "last_modified": "Mon, 19 Jan 2026 14:10:33 GMT",
        "content_length": 752795,
    }

    def fake_horizontal(target_crs):
        """CuzkRasterProvider.horizontal_transform contract: None for native."""
        if target_crs.endswith("5514"):
            return None
        pinned = Mock()
        pinned.description = f"S-JTSK to ETRS89 (1) -> {target_crs}"
        pinned.accuracy_m = 1.0
        return pinned

    provider.horizontal_transform.side_effect = fake_horizontal
    provider.route.side_effect = lambda sheet=None: route_of(
        provider.descriptor_key,
        provider.vertical_crs,
        sheet,
        target_crs=provider.target_crs,
        horizontal=fake_horizontal,
        vertical=provider.vertical_pinned,
    )

    def fake_download(sheet, target, timeout=60, *, on_download=None, on_response=None):
        # provider contract: announce after validation, before the transfer
        if on_download is not None:
            on_download()
        if on_response is not None:
            on_response(
                Mock(
                    headers={
                        "ETag": '"d19f2c604d89dc1:0"',
                        "Last-Modified": "Mon, 19 Jan 2026 14:10:33 GMT",
                        "Content-Length": "752795",
                    }
                )
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download.side_effect = fake_download
    provider.download_bbox.side_effect = lambda bbox, target, **kw: fake_download(
        "x", target, on_download=kw.get("on_download")
    )
    return provider


_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_cz_raster_provider"


class TestCzDownloadingAfterValidation:
    """``Downloading ...`` in the CZ flow only when the transfer really starts.

    Uses the real ``CuzkRasterProvider`` (offline: ``CuzkClient`` and
    ``SheetIndex`` mocked), so validations inside the provider run for real.
    """

    _CLIENT = "kartograf.providers.cuzk.raster.CuzkClient"
    _INDEX = "kartograf.providers.cuzk.raster.SheetIndex"

    @staticmethod
    def _sm5_info():
        from kartograf.providers.cuzk.sheets import SheetInfo

        return SheetInfo(
            sheet="CTES96",
            name=None,
            bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
            podil=None,
            in_cz=None,
        )

    @staticmethod
    def _write_tif(path, crs):
        import numpy as np
        import rasterio
        from rasterio.transform import from_bounds

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            dtype="float32",
            count=1,
            width=4,
            height=4,
            crs=crs,
            transform=from_bounds(0, 0, 8, 8, 4, 4),
            nodata=-9999.0,
        ) as dst:
            dst.write(np.full((4, 4), 100.0, dtype="float32"), 1)

    def test_unknown_sm5_sheet_is_error_without_downloading(self, tmp_path, capsys):
        out = tmp_path / "out"
        with patch(self._CLIENT) as client_cls, patch(self._INDEX) as index_cls:
            index_cls.return_value.sm5_sheet.side_effect = ValidationError(
                "Arkusz SM5 'ABCD12' nie istnieje w indeksie KladyMapovychListu"
            )
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=5m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "ABCD12",
                    "--country",
                    "cz",
                    "-o",
                    str(out),
                ]
            )
            client_cls.return_value.fetch_file.assert_not_called()

        captured = capsys.readouterr()
        assert rc == 1
        assert "Pobieranie" not in captured.out
        assert "Error: Arkusz SM5 'ABCD12' nie istnieje" in captured.err
        assert not list(out.rglob("*.tif"))

    def test_invalid_tm33_tile_is_error_without_downloading(self, tmp_path, capsys):
        """Odd kilometres match the TM33 pattern but fail ``ParserTM33``."""
        with patch(self._CLIENT) as client_cls, patch(self._INDEX):
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "301_5550",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path / "o"),
                ]
            )
            client_cls.return_value.export_image.assert_not_called()

        captured = capsys.readouterr()
        assert rc == 1
        assert "Pobieranie" not in captured.out
        assert "Error:" in captured.err and "parzyste" in captured.err


class TestCmdDownloadCz:
    """Tests for the CZ (CUZK) flow in the download command."""

    def test_tm33_sheet_saves_under_cz_dmr5g(self, tmp_path):

        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 0
        assert factory.call_args.kwargs["resolution"] == "2m"
        assert factory.call_args.kwargs["vertical_crs"] == "Bpv"
        staged = provider.download.call_args.args[1]
        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        assert staged.name == target.name
        assert ".incoming" in staged.parts
        assert target.read_bytes() == b"II*\x00dane"
        assert (
            json.loads(Path(f"{target}.meta.json").read_text())["extra"]["link"]
            == "hardlink"
        )

    @pytest.mark.parametrize("force", [False, True])
    def test_force_refreshes_sheet_index_cache(self, tmp_path, force):
        """Forced CZ requests miss old sheet data but persist the replacement."""
        from kartograf.cache.defaults import open_cache

        old = {"name": "old"}
        new = {"name": "new"}
        with open_cache(True, force=False) as cache:
            assert cache is not None
            cache.set_sheet("cz_tm33", "302_5550", old)

        seen = []

        def factory(**kwargs):
            cache = kwargs["cache"]
            seen.append(cache.get_sheet("cz_tm33", "302_5550"))
            cache.set_sheet("cz_tm33", "302_5550", new)
            return _cz_provider_mock()

        with patch(_CZ_FACTORY_PATCH, side_effect=factory):
            result = _cmd_download_cz(_cz_args(tmp_path, force=force))

        assert result == 0
        assert seen == [None if force else old]
        with open_cache(True, force=False) as cache:
            assert cache is not None
            assert cache.get_sheet("cz_tm33", "302_5550") == new

    def test_unreadable_cache_warns_and_downloads(self, tmp_path, capsys):
        """An unreadable cache in the CZ path: one ``Warning:``, code 0."""

        db = Path.cwd() / ".kartograf_cache.db"
        db.write_bytes(b"to nie jest baza SQLite\n" * 200)

        def factory(**kwargs):
            kwargs["cache"].get_sheet("cz_sm5", "CTES96")
            return _cz_provider_mock()

        with patch(_CZ_FACTORY_PATCH, side_effect=factory):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 0
        err = capsys.readouterr().err
        assert "Error:" not in err
        assert f"Warning: cache metadanych nieczytelny ({db})" in err

    def test_tm33_sheet_writes_sidecar(self, tmp_path):

        with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()):
            _cmd_download_cz(_cz_args(tmp_path))

        sidecar = (
            tmp_path
            / "nmt"
            / "cz_dmr5g_bpv"
            / "302"
            / "5550"
            / "302_5550.tif.meta.json"
        )
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "cz.cuzk.dmr5g"
        assert payload["country"] == "CZ"
        assert payload["horizontal_crs"] == "EPSG:3045"  # the tile's actual CRS
        assert payload["vertical_crs"] == "EPSG:8357"  # Bpv natively
        assert payload["license"]["id"] == "CC-BY-4.0"
        assert payload["request"] == {"sheet": "302_5550"}
        # the TM33 tile lies in 3045, and CUZK data in 5514 - the reprojection is LOCAL
        # and the sidecar carries its accuracy (ADR-024)
        assert payload["transform"] == {
            "horizontal": "pinned: S-JTSK to ETRS89 (1) -> EPSG:3045 (1.0 m)"
        }
        # sheet code mode without the field
        assert "parent_request" not in payload["extra"]

    def test_sm5_sheet_enriches_extra_with_cz_share(self, tmp_path):

        from kartograf.providers.cuzk.sheets import SheetInfo

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.return_value = SheetInfo(
            sheet="CTES96",
            name="Český Těšín 9-6",
            bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
            podil=0.99,
            in_cz=None,
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, sheet="CTES96", resolution="5m")
            )

        assert result == 0
        sidecar = (
            tmp_path / "nmt" / "cz_dmr4g_bpv" / "CTES" / "96" / "CTES96.tif.meta.json"
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["extra"]["mapname"] == "Český Těšín 9-6"
        assert payload["extra"]["cz_share"] == 0.99

    def test_sm5_index_failure_after_download_keeps_file(self, tmp_path):
        """Index error at PODIL: warning, the file and sidecar without podil stay."""

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.side_effect = DownloadError("siec padla")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, sheet="CTES96", resolution="5m")
            )

        assert result == 0
        target = tmp_path / "nmt" / "cz_dmr4g_bpv" / "CTES" / "96" / "CTES96.tif"
        assert target.exists()
        payload = json.loads(
            (target.parent / "CTES96.tif.meta.json").read_text(encoding="utf-8")
        )
        assert "cz_share" not in payload["extra"]

    @pytest.mark.parametrize("country", ["auto", "cz"])
    def test_sm5_sheet_without_resolution_defaults_to_5m(
        self, tmp_path, capsys, country
    ):
        """An SM5 sheet exists only at 5 m (DMR 4G): without ``--resolution``
        the resolution follows from the sheet code - the download starts, without an
        extra message (the resolution is visible in ``Downloading``)."""
        from kartograf.providers.cuzk.sheets import SheetInfo

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.return_value = SheetInfo(
            sheet="CTES96",
            name=None,
            bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
            podil=None,
            in_cz=None,
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=5m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "CTES96",
                    "--country",
                    country,
                    "-o",
                    str(tmp_path / "out"),
                ]
            )

        assert rc == 0
        assert factory.call_args.kwargs["resolution"] == "5m"
        provider.download.assert_called_once()
        captured = capsys.readouterr()
        assert "Pobieranie CTES96 (CZ, resolution: 5m)..." in captured.out
        assert captured.err == ""

    def test_sm5_sheet_with_explicit_2m_is_error_without_network(
        self, tmp_path, capsys
    ):
        """An explicit ``--resolution 2m`` with an SM5 sheet code is a contradictory
        request:
        ``Error:`` before the provider is created and without ``Downloading``."""
        with patch(_CZ_FACTORY_PATCH) as factory:
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=5m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "CTES96",
                    "--resolution",
                    "2m",
                    "-o",
                    str(tmp_path / "out"),
                ]
            )

        assert rc == 1
        factory.assert_not_called()
        captured = capsys.readouterr()
        assert "Pobieranie" not in captured.out
        assert "Error: Arkusze SM5" in captured.err
        assert "5m" in captured.err

    def test_tm33_sheet_without_resolution_stays_2m(self, tmp_path):
        """TM33 tile cut from the service: 2 m by default, as before."""
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "302_5550",
                    "-o",
                    str(tmp_path / "out"),
                    "-q",
                ]
            )

        assert rc == 0
        assert factory.call_args.kwargs["resolution"] == "2m"

    def test_cz_bbox_without_resolution_stays_2m(self, tmp_path):
        """CZ ``--bbox`` cutout: 2 m by default, as before."""
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--bbox=-447000,-1114000,-446000,-1113000",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path / "out"),
                    "-q",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                ]
            )

        assert rc == 0
        assert factory.call_args.kwargs["resolution"] == "2m"

    def test_bbox_mode_file_in_bbox_subdir_and_parent_request(self, tmp_path):

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        parent = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": "EPSG:5514",
            "countries": ["CZ"],
        }
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox)

        assert result == 0
        target = (
            tmp_path
            / "nmt"
            / "cz_dmr5g_bpv"
            / "bbox"
            / "-447000_-1114000_-446000_-1113000.tif"
        )
        staged = provider.download_bbox.call_args.args[1]
        assert staged.name == target.name
        assert staged.parent.parent.name == ".incoming"
        assert staged.parent.parent.parent == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "versions"
        )
        assert target.exists()
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["request"]["bbox_crs"] == "EPSG:5514"
        assert payload["nodata"] == -9999.0  # GeoTIFF tag unreadable -> default
        assert payload["transform"] is None  # native EPSG:5514: no reprojection

    def test_bbox_string_is_normalized_to_image_sr(self, tmp_path):
        """The file name carries the coordinates of the FINAL request (after
        normalisation).

        Through ``main`` (K7b): the CZ area mode always gets a ready bbox
        from ``_dispatch_area``; the former direct call with ``args.bbox``
        as text went through a dead parsing branch in ``_cz_download_bbox``.
        """
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--bbox",
                    "472887.5,208337.5,473808.0,209409.8",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path),
                    "-q",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                ]
            )

        assert result == 0
        sent_bbox, target = provider.download_bbox.call_args.args[:2]
        assert sent_bbox.crs == "EPSG:5514"
        assert -450000 < sent_bbox.min_x < -440000  # Krovak: negative values
        assert target.parent.parent.name == ".incoming"
        assert target.parent.parent.parent == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "versions"
        )
        assert target.name == (
            f"{format(sent_bbox.min_x, '.10g')}"
            f"_{format(sent_bbox.min_y, '.10g')}"
            f"_{format(sent_bbox.max_x, '.10g')}"
            f"_{format(sent_bbox.max_y, '.10g')}.tif"
        )
        assert (tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox" / target.name).exists()

    def test_bbox_with_horizontal_crs_records_pinned_transform(self, tmp_path):

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, side_effect=cz_factory(provider)) as factory:
            result = _cmd_download_cz(
                _cz_args(tmp_path, sheet=None, horizontal_crs="EPSG:3045"), bbox=bbox
            )

        assert result == 0
        assert factory.call_args.kwargs["horizontal_crs"] == "EPSG:3045"
        sent_bbox, target = provider.download_bbox.call_args.args[:2]
        assert sent_bbox.crs == "EPSG:3045"
        assert target.parent.parent.name == ".incoming"
        link = tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox" / target.name
        payload = json.loads(
            (link.parent / f"{link.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["horizontal_crs"] == "EPSG:3045"
        assert payload["transform"] == {
            "horizontal": "pinned: S-JTSK to ETRS89 (1) -> EPSG:3045 (1.0 m)"
        }

    def test_sheet_without_safe_horizontal_operation_exits_cleanly(
        self, tmp_path, capsys
    ):
        """The TM33 sheet code path builds the horizontal operation only at download
        time (a sheet code has no `--cutout`, so the constructor does not touch
        it) - a missing safe operation must give a message with a remedy and exit
        code 1, NOT a traceback.

        The safeguard lies in `_run_cz`, not in `_cz_download_sheet`, so it is
        easy to overlook in a refactor - hence this test on the full CLI flow
        (`main`), not on the helper function alone.
        """
        from kartograf.cli.commands import main
        from kartograf.transform.crs import TransformUnavailableError

        def _boom(src_crs, dst_crs, policy):
            raise TransformUnavailableError(
                f"Brak bezpiecznej operacji transformacji {src_crs} -> {dst_crs}",
                remedy="zainstaluj siatki recznie do PROJ_DATA",
            )

        with patch(
            "kartograf.providers.cuzk.raster.build_pinned_transform", side_effect=_boom
        ):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "302_5550",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert result == 1
        captured = capsys.readouterr()
        assert "EPSG:5514 -> EPSG:3045" in captured.err
        assert "Remedium: zainstaluj siatki recznie" in captured.err
        assert "Traceback" not in captured.err
        assert not list(tmp_path.rglob("*.tif"))

    def test_provider_factory_transform_error_reports_remedy(self, tmp_path, capsys):
        """D6: TransformError from the provider constructor (the operation for
        ``--horizontal-crs``) - the same ``Error: ... Remedium: ...`` format as the
        other CLI paths, exit code 1, no traceback."""
        from kartograf.transform.crs import TransformUnavailableError

        boom = TransformUnavailableError(
            "Brak bezpiecznej operacji transformacji EPSG:5514 -> EPSG:3045",
            remedy="zainstaluj siatki recznie do PROJ_DATA",
        )
        with patch(_CZ_FACTORY_PATCH, side_effect=boom):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--bbox=-447000,-1114000,-446000,-1113000",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--country",
                    "cz",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:3045",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert result == 1
        err = capsys.readouterr().err
        assert (
            "Error: Brak bezpiecznej operacji transformacji EPSG:5514 -> EPSG:3045 "
            "Remedium: zainstaluj siatki recznie do PROJ_DATA"
        ) in err
        assert "Traceback" not in err

    def test_cutout_with_sheet_rejected(self, tmp_path, capsys):

        assert _cmd_download_cz(_cz_args(tmp_path, horizontal_crs="EPSG:2180")) == 1
        assert "Error: --cutout dziala tylko z --bbox/--geometry" in (
            capsys.readouterr().err
        )

    def test_resolution_1m_rejected(self, tmp_path, capsys):

        result = _cmd_download_cz(_cz_args(tmp_path, resolution="1m"))
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_sheet_system_flag_rejected(self, tmp_path, capsys):

        result = _cmd_download_cz(_cz_args(tmp_path, sheet_system="1992"))
        assert result == 1
        assert "--sheet-system" in capsys.readouterr().err

    def test_kron86_prints_remedy(self, tmp_path, capsys):

        from kartograf.transform.crs import TransformUnavailableError

        with patch(
            _CZ_FACTORY_PATCH,
            side_effect=TransformUnavailableError(
                "brak operacji", remedy="uzyj EVRF2007 (EPSG:5621)"
            ),
        ):
            result = _cmd_download_cz(_cz_args(tmp_path, vertical_crs="KRON86"))
        assert result == 1
        err = capsys.readouterr().err
        assert "EVRF2007" in err

    def test_download_error_returns_1(self, tmp_path, capsys):

        provider = _cz_provider_mock()
        provider.download.side_effect = DownloadError("404 openzu")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 1
        assert "404 openzu" in capsys.readouterr().err
        assert not (tmp_path / "nmt" / "cz_dmr5g_bpv").exists()

    def test_legacy_plain_sheet_is_replaced_by_version(self, tmp_path):

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"stare")
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path))
        assert result == 0
        provider.download.assert_called_once()
        assert target.read_bytes() == b"II*\x00dane"
        assert (
            json.loads(Path(f"{target}.meta.json").read_text())["extra"]["link"]
            == "hardlink"
        )

    def test_force_redownloads_existing_version_without_overwrite(self, tmp_path):

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(_cz_args(tmp_path)) == 0
            before = next((tmp_path / "nmt").rglob("versions/**/*.tif"))
            assert _cmd_download_cz(_cz_args(tmp_path, force=True)) == 0
        assert provider.download.call_count == 2
        assert target.read_bytes() == b"II*\x00dane"
        assert list((tmp_path / "nmt").rglob("versions/**/*.tif")) == [before]

    def test_evrf2007_transform_lands_in_sidecar(self, tmp_path):
        """Bpv->EVRF2007 vertical transformation recorded in the sidecar.

        The segment carries the provider's vertical CRS (ADR-026).
        """

        provider = _cz_provider_mock()
        provider.vertical_crs = "EVRF2007"
        pinned = Mock()
        pinned.description = "Baltic 1957 height to EVRF2007 height (1)"
        pinned.accuracy_m = 0.1
        provider.vertical_pinned = pinned
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            _cmd_download_cz(_cz_args(tmp_path, vertical_crs="EVRF2007"))

        payload = json.loads(
            (
                tmp_path
                / "nmt"
                / "cz_dmr5g_evrf2007"
                / "302"
                / "5550"
                / "302_5550.tif.meta.json"
            ).read_text(encoding="utf-8")
        )
        assert payload["vertical_crs"] == "EPSG:5621"
        assert payload["transform"]["vertical"] == (
            "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"
        )

    def test_version_sidecar_failure_aborts_download(self, tmp_path, capsys):
        """A version without a sidecar cannot become a valid local version."""

        provider = _cz_provider_mock()
        with (
            patch(_CZ_FACTORY_PATCH, return_value=provider),
            patch(
                "kartograf.sources.sidecar.build_metadata",
                side_effect=RuntimeError("deskryptor padl"),
            ),
        ):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 1
        assert "deskryptor padl" in capsys.readouterr().err
        assert not list((tmp_path / "nmt").rglob("*.tif"))

    def test_factory_validation_error_returns_1(self, tmp_path, capsys):

        with patch(
            _CZ_FACTORY_PATCH,
            side_effect=ValidationError("Nieobslugiwany uklad pionowy dla CZ"),
        ):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 1
        assert "Error: Nieobslugiwany uklad pionowy" in capsys.readouterr().err

    def test_verbose_sheet_reports_progress_and_skip(self, tmp_path, capsys):
        """Per-file messages in the LAZ/PL flow convention."""

        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(_cz_args(tmp_path, quiet=False)) == 0
            first = capsys.readouterr().out
            assert _cmd_download_cz(_cz_args(tmp_path, quiet=False)) == 0
            second = capsys.readouterr().out

        assert "Pobieranie 302_5550 (CZ, resolution: 2m)" in first
        assert "302_5550: nowa wersja " in first
        assert "302_5550: lokalna wersja " in second
        assert "(bez sprawdzania; --check-updates)" in second  # TM33: signal none
        provider.download.assert_called_once()

    def test_verbose_bbox_reports_progress_and_skip(self, tmp_path, capsys):

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        args = _cz_args(tmp_path, sheet=None, quiet=False)
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(args, bbox=bbox) == 0
            first = capsys.readouterr().out
            assert _cmd_download_cz(args, bbox=bbox) == 0
            second = capsys.readouterr().out

        assert "Pobieranie CZ bbox (2m, EPSG:5514)" in first
        unit = "nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif"
        assert f"{unit}: nowa wersja " in first
        assert f"{unit}: lokalna wersja " in second
        assert "(bez sprawdzania; --check-updates)" in second
        provider.download_bbox.assert_called_once()

    def test_bbox_download_error_returns_1(self, tmp_path, capsys):

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = DownloadError("exportImage 500")
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox)

        assert result == 1
        assert "exportImage 500" in capsys.readouterr().err
        assert not (tmp_path / "nmt").exists()

    def test_sidecar_nodata_comes_from_geotiff_tag(self, tmp_path):
        """Sidecar nodata comes from the downloaded raster's tag, not a constant."""
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        def real_tif(sheet, target, timeout=60, *, on_download=None, on_response=None):
            target.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(
                target,
                "w",
                driver="GTiff",
                width=2,
                height=2,
                count=1,
                dtype="float32",
                crs="EPSG:3045",
                transform=from_origin(302000.0, 5552000.0, 2.0, 2.0),
                nodata=-32767.0,
            ) as ds:
                ds.write(np.zeros((2, 2), dtype="float32"), 1)
            return target

        provider = _cz_provider_mock()
        provider.download.side_effect = real_tif
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(_cz_args(tmp_path)) == 0

        payload = json.loads(
            (
                tmp_path
                / "nmt"
                / "cz_dmr5g_bpv"
                / "302"
                / "5550"
                / "302_5550.tif.meta.json"
            ).read_text(encoding="utf-8")
        )
        assert payload["nodata"] == -32767.0

    # --- N2: raster entirely nodata = Warning:, code 0 ---

    @staticmethod
    def _real_tif_writer(fill: float, nodata: float = -9999.0):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        def write(*call_args, **_kwargs):
            target = next(a for a in call_args if hasattr(a, "parent"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(
                target,
                "w",
                driver="GTiff",
                width=4,
                height=4,
                count=1,
                dtype="float32",
                crs="EPSG:5514",
                transform=from_origin(-447000.0, -1113000.0, 250.0, 250.0),
                nodata=nodata,
            ) as ds:
                ds.write(np.full((4, 4), fill, dtype="float32"), 1)
            return target

        return write

    def test_bbox_all_nodata_warns_but_returns_0(self, tmp_path, capsys):
        """A CZ cutout without a single valid pixel: Warning:, exit code 0, sidecar."""

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = self._real_tif_writer(-9999.0)
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox)

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "w calosci nodata" in err
        assert "poza granica CZ?" in err
        assert list((tmp_path / "nmt").rglob("*.tif.meta.json"))

    def test_bbox_all_nodata_message_printed_once(self, tmp_path, capsys, monkeypatch):
        """The library log does not repeat the CLI 'Warning:' line on stderr."""
        import logging

        # no handler on the 'kartograf' branch -> logging.lastResort writes to
        # stderr, as in a real CLI run (pytest's root handler would hide it)
        monkeypatch.setattr(logging.getLogger("kartograf"), "propagate", False)
        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = self._real_tif_writer(-9999.0)
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox)

        assert rc == 0
        err = capsys.readouterr().err
        assert err.count("w calosci nodata") == 1
        assert "Warning:" in err

    def test_library_log_unmuted_after_cli_call(self, tmp_path):
        """The muted library logger is restored - also after a failed download."""
        import logging

        log = logging.getLogger("kartograf.download.cz_cutout")
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")

        ok = _cz_provider_mock()
        ok.download_bbox.side_effect = self._real_tif_writer(-9999.0)
        with patch(_CZ_FACTORY_PATCH, return_value=ok):
            assert _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox) == 0
        assert log.disabled is False

        failing = _cz_provider_mock()
        failing.download_bbox.side_effect = DownloadError("boom")
        with patch(_CZ_FACTORY_PATCH, return_value=failing):
            rc = _cmd_download_cz(_cz_args(tmp_path / "b", sheet=None), bbox=bbox)
        assert rc == 1
        assert log.disabled is False

        crashing = _cz_provider_mock()
        crashing.download_bbox.side_effect = KeyboardInterrupt
        with (
            patch(_CZ_FACTORY_PATCH, return_value=crashing),
            pytest.raises(KeyboardInterrupt),
        ):
            _cmd_download_cz(_cz_args(tmp_path / "c", sheet=None), bbox=bbox)
        assert log.disabled is False

    def test_tm33_sheet_all_nodata_warns_but_returns_0(self, tmp_path, capsys):

        provider = _cz_provider_mock()
        provider.download.side_effect = self._real_tif_writer(-9999.0)
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path))

        assert rc == 0
        err = capsys.readouterr().err
        assert "302_5550.tif jest w calosci nodata" in err

    def test_bbox_with_data_has_no_nodata_warning(self, tmp_path, capsys):
        """Control: a raster with data (even one pixel) — no message."""

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = self._real_tif_writer(123.0)
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox)

        assert rc == 0
        assert "Warning:" not in capsys.readouterr().err

    # --- D12: a file skipped from before the S-JTSK operation fix (K2) ---

    @staticmethod
    def _existing_with_sidecar(target, horizontal):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"stare")
        transform = None if horizontal is None else {"horizontal": horizontal}
        (target.parent / f"{target.name}.meta.json").write_text(
            json.dumps({"transform": transform}), encoding="utf-8"
        )

    def test_legacy_bbox_cutout_replaced_by_version_without_legacy_warning(
        self, tmp_path, capsys
    ):

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        target = (
            tmp_path
            / "nmt"
            / "cz_dmr5g_bpv"
            / "bbox"
            / "-447000_-1114000_-446000_-1113000.tif"
        )
        self._existing_with_sidecar(target, "S-JTSK to ETRS89 (3) -> EPSG:2180")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(_cz_args(tmp_path, sheet=None), bbox=bbox) == 0

        provider.download_bbox.assert_called_once()
        assert target.read_bytes() != b"stare"
        assert "sprzed naprawy operacji S-JTSK" not in capsys.readouterr().err
        assert (
            json.loads(target.with_name(target.name + ".meta.json").read_text())[
                "extra"
            ]["link"]
            == "hardlink"
        )

    def test_cutout_with_sheet_message_names_product_frames(self, tmp_path, capsys):
        """K2: the message says WHAT the code defines (SM5 in 5514, TM33 on 3045)."""

        assert _cmd_download_cz(_cz_args(tmp_path, horizontal_crs="EPSG:2180")) == 1
        assert "kafel TM33 na siatce EPSG:3045" in capsys.readouterr().err


def _write_prague_shp(directory):
    """Small shapefile (a polygon near Prague) in EPSG:4326 — offline data."""
    import shapefile
    from pyproj import CRS

    shp_path = directory / "area_cz.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        w.poly(
            [
                [
                    (14.40, 50.06),
                    (14.45, 50.06),
                    (14.45, 50.10),
                    (14.40, 50.10),
                    (14.40, 50.06),
                ]
            ]
        )
        w.record("praha")
    shp_path.with_suffix(".prj").write_text(
        CRS.from_epsg(4326).to_wkt(), encoding="utf-8"
    )
    return shp_path


def _write_krovak_shp(directory):
    """A shapefile in EPSG:5514 (the CZ request CRS) with an exactly known envelope."""
    import shapefile
    from pyproj import CRS

    shp_path = directory / "area_krovak.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        w.poly(
            [
                [
                    (-447000.0, -1114000.0),
                    (-446000.0, -1114000.0),
                    (-446000.0, -1113000.0),
                    (-447000.0, -1113000.0),
                    (-447000.0, -1114000.0),
                ]
            ]
        )
        w.record("krovak")
    shp_path.with_suffix(".prj").write_text(
        CRS.from_epsg(5514).to_wkt(), encoding="utf-8"
    )
    return shp_path


class TestCountryDispatch:
    """Per-country dispatch in cmd_download (sheet code -> system registry)."""

    # --- sheet code -> country ---

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_routes_to_cz_flow(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.download.data._download_cz")
    def test_sm5_sheet_auto_detected(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "CTES96",
                "--resolution",
                "5m",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_with_country_cz_routes_to_cz_flow(self, mock_cz, tmp_path):
        """An explicit --country cz consistent with the sheet code is not a conflict."""
        mock_cz.return_value = 0
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_gets_raw_per_country_values(self, mock_cz, tmp_path):
        """The CZ flow receives the per-country values unnarrowed by PL."""
        mock_cz.return_value = 0
        main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        args = mock_cz.call_args.args[0]
        assert args.resolution == {"pl": "1m", "cz": "2m"}
        assert args.vertical_crs == {"pl": "EVRF2007", "cz": "Bpv"}
        assert args.sheet_system is None

    def test_cz_sheet_with_country_pl_conflicts(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "CTES96",
                "--country",
                "pl",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "cz_sm5" in capsys.readouterr().err

    def test_pl_sheet_with_country_cz_conflicts(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "pl" in capsys.readouterr().err.lower()

    # --- sentinele PL ---

    @patch("kartograf.download.data.DownloadManager")
    def test_pl_sheet_takes_pl_part_of_per_country_values(
        self, mock_manager_class, tmp_path
    ):
        """pl=1m,cz=2m / pl=EVRF2007,cz=Bpv -> the PL provider gets 1m/EVRF2007."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "x.asc"]
        )
        mock_manager_class.return_value = mock_manager
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        provider = mock_manager_class.call_args.kwargs["provider"]
        assert provider.resolution == "1m"
        assert provider.vertical_crs == "EVRF2007"

    @patch("kartograf.download.data.DownloadManager")
    def test_pl_1m_kron86_no_correction(self, mock_manager_class, tmp_path, capsys):
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "x.asc"]
        )
        mock_manager_class.return_value = mock_manager
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        assert "Info:" not in capsys.readouterr().err
        assert mock_manager_class.call_args.kwargs["provider"].vertical_crs == "KRON86"

    def test_5m_rule_only_for_nmt(self):
        """LAZ also goes through the PL options - the NMT 5m rule does not apply."""
        from types import SimpleNamespace

        from kartograf.download.options import resolve_pl_options

        task = SimpleNamespace(
            product="laz",
            resolution="5m",
            vertical_crs="KRON86",
            cutout=False,
            sheet_system=None,
            scale=None,
        )
        resolve_pl_options(task)
        assert task.vertical_crs == "KRON86"

    def test_pl_sheet_with_2m_rejected(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--resolution",
                "2m",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_pl_sheet_with_bpv_rejected(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--vertical-crs",
                "Bpv",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "Bpv" in capsys.readouterr().err

    def test_pl_sheet_with_cutout_rejected(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    # PL bbox + --cutout has been a legal cutout flow since ADR-027/038 —
    # covered by tests/test_pl_cutout.py (TestDownloadPlBboxCutout).

    # --- ValidationError from the CZ flow does not escape as a traceback ---

    def test_cz_sheet_parse_error_returns_1_without_traceback(self, tmp_path, capsys):
        """TM33 pattern with odd km: a CLI error (ParseError), not a traceback."""
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "301_5551",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Error:" in err
        assert "301_5551" in err

    def test_cz_sheet_with_cutout_returns_1_without_traceback(self, tmp_path, capsys):
        """R9: --cutout + CZ sheet code = a CLI error (main catches nothing)."""
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--cutout",
                "--horizontal-crs",
                "EPSG:3045",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "--cutout dziala tylko z --bbox/--geometry" in capsys.readouterr().err

    @patch("kartograf.download.data._download_cz")
    def test_cz_validation_error_from_area_mode_returns_1(
        self, mock_cz, tmp_path, capsys
    ):
        mock_cz.side_effect = ValidationError("cos nie gra")
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "cos nie gra" in capsys.readouterr().err

    # --- LAZ CZ selection is explicit; no model is silently chosen ---

    def test_laz_cz_sheet_requires_model(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "laz",
                "--sheet",
                "760_5518",
                "--vertical-crs",
                "EVRF2007",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Error: --model wymagane" in err and "dmpok" in err
        assert not (tmp_path / "laz").exists()

    def test_laz_cz_bbox_requires_model(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "laz",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--vertical-crs",
                "Bpv",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Error: --model wymagane" in err and "dmr5g" in err
        assert not (tmp_path / "laz").exists()

    @pytest.mark.parametrize(
        ("sheet", "product", "model", "vertical_crs", "resolution", "expected"),
        [
            (
                "CTES96",
                "nmpt",
                "dmpok",
                "Bpv",
                "0.5m",
                "--model dotyczy tylko --product laz",
            ),
            (
                "N-34-130-D-d-2-4",
                "laz",
                "dmr4g",
                "EVRF2007",
                None,
                "--model dotyczy tylko --product laz w CZ",
            ),
            (
                "760_5518",
                "laz",
                "dmr4g",
                "Bpv",
                None,
                "kafle TM33 (ETRS89) sa tylko w EVRF2007",
            ),
        ],
    )
    def test_model_rules(
        self,
        sheet,
        product,
        model,
        vertical_crs,
        resolution,
        expected,
        tmp_path,
        capsys,
    ):
        args = [
            "elevation",
            "download",
            "--sheet",
            sheet,
            "--product",
            product,
            "--model",
            model,
            "--vertical-crs",
            vertical_crs,
            "-o",
            str(tmp_path),
        ]
        if resolution is not None:
            args += ["--resolution", resolution]
        assert main(args) == 1
        with pytest.raises(ValidationError) as exc:
            download_data(
                product=product,
                model=model,
                output_dir=tmp_path,
                sheet=sheet,
                resolution=resolution,
                vertical_crs=vertical_crs,
            )
        assert str(exc.value) == capsys.readouterr().err.removeprefix("Error: ").strip()
        assert expected in str(exc.value)
        assert not (tmp_path / "laz").exists() and not (tmp_path / "nmpt").exists()

    # --- area modes: explicit --country cz ---

    @patch("kartograf.download.data._download_cz")
    def test_bbox_with_country_cz_routes_to_cz_flow(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.download.data._download_cz")
    def test_geometry_with_country_cz_reads_bbox_in_file_crs(self, mock_cz, tmp_path):
        """The envelope is computed in the FILE's CRS - the CZ layer transforms it."""
        from pyproj import CRS

        from kartograf.core import geometry as geom

        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0
        with patch.object(
            geom, "get_overall_bbox", wraps=geom.get_overall_bbox
        ) as spy_bbox:
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        requested = CRS.from_user_input(spy_bbox.call_args.kwargs["target_crs"])
        assert requested == CRS.from_epsg(4326)  # the file's CRS, not Krovak
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.download.data._download_cz")
    def test_geometry_cz_bbox_goes_through_pinned_transform(self, mock_cz, tmp_path):
        """The hop to Krovak uses the pinned operation with edge sampling."""
        from kartograf.providers.cuzk import raster

        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0
        with patch.object(
            raster, "build_pinned_transform", wraps=raster.build_pinned_transform
        ) as spy:
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        spy.assert_called_once()
        assert spy.call_args.args[1] == "EPSG:5514"
        bbox = mock_cz.call_args.kwargs["bbox"]
        assert bbox.crs == "EPSG:5514"
        # Prague in Krovak: both coordinates negative, |X| ~ 743 km, |Y| ~ 1044 km
        assert -745000 < bbox.min_x < -740000
        assert -1047000 < bbox.min_y < -1041000
        assert bbox.max_x > bbox.min_x and bbox.max_y > bbox.min_y

    @patch("kartograf.download.data._download_cz")
    def test_geometry_cz_skips_unpinned_transformer(self, mock_cz, tmp_path):
        """An unpinned pyproj transformer (``core.bbox``, ballpark) is unused."""
        from kartograf.core import bbox as core_bbox

        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0
        with patch.object(
            core_bbox, "_transformer", wraps=core_bbox._transformer
        ) as mock_transformer:
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        mock_transformer.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_geometry_cz_horizontal_crs_in_one_hop(self, mock_cz, tmp_path):
        """--cutout: the envelope directly in the CRS requested from the server."""
        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp),
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:3045",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        bbox = mock_cz.call_args.kwargs["bbox"]
        assert bbox.crs == "EPSG:3045"
        assert 450000 < bbox.min_x < 465000
        assert 5540000 < bbox.min_y < 5555000

    def test_geometry_with_country_cz_missing_file(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(tmp_path / "missing.shp"),
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        assert "brak pliku" in capsys.readouterr().err.lower()

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    def test_bbox_auto_stays_pl(self, mock_find, mock_manager_class, mock_cz, tmp_path):
        """--country auto + a bbox deep inside PL (Warsaw): the CZ flow untouched."""
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        assert mock_find.call_args.kwargs.get("sheet_system") == "1992"

    def test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl(
        self, tmp_path
    ):
        """Finding 4 of review max: a geometry file in EPSG:5514 with --country pl.

        The PL envelope is built by the pinned operation (like --bbox in a Czech
        CRS), not by the default transformer from core/geometry (~1.2 m
        difference).
        """
        from kartograf.providers.cuzk.raster import bbox_to_crs

        shp = _write_krovak_shp(tmp_path)
        captured = {}

        def fake_pl_geometry(task, run, filepath, parent_request, bbox):
            captured.update(bbox=bbox, parent=parent_request)
            return 0

        with patch(
            "kartograf.download.data._download_pl_geometry",
            side_effect=fake_pl_geometry,
        ):
            rc = main(
                [
                    "elevation",
                    "download",
                    "--sheet-system",
                    "1992",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(shp),
                    "--country",
                    "pl",
                    "-o",
                    str(tmp_path / "out"),
                ]
            )

        assert rc == 0
        expected = bbox_to_crs(
            BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"), "EPSG:2180"
        )
        got = captured["bbox"]
        assert got.crs == "EPSG:2180"
        assert (got.min_x, got.min_y, got.max_x, got.max_y) == pytest.approx(
            (expected.min_x, expected.min_y, expected.max_x, expected.max_y), abs=1e-6
        )
        assert captured["parent"]["bbox_crs"] == "EPSG:5514"


# ===========================================================================
# Auto-split of bbox/geometry per country + extra.parent_request (Task 17)
# ===========================================================================

# Choices the registry has only for PL decide `--country auto` (ADR-023
# point 5): grid labels without a CZ source of the product (CZ: NMT DMR 5G 2m
# and DMR 4G 5m, NMPT DMP OK 0.5m and DMP 1G 2m) - e.g. NMT 1m, NMPT 0.6m.
_PL_ONLY_CHOICES = [
    (product, label)
    for product in ("nmt", "nmpt")
    for label in _grid_labels(product)
    if label not in {d.resolution for d in sources_for(country="CZ", product=product)}
]


class TestAutoSplitBBox:
    """--country auto: a cross-border bbox split into countries, parent_request."""

    # 18.4-18.8E / 49.55-49.75N — PL/CZ border strip (both country envelopes
    # contain this rectangle: CZ up to 18.86E/51.06N, PL from 14.07E/49.0N)
    _BORDER = [
        "elevation",
        "download",
        "--sheet-system",
        "1992",
        "--product",
        "nmt",
        "-o",
        "./data",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "pl=EVRF2007,cz=Bpv",
        "--bbox",
        "18.4,49.55,18.8,49.75",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 21.0-21.2E / 52.0-52.2N — Warsaw, east of the CZ envelope (18.86E)
    _PL_ONLY = [
        "elevation",
        "download",
        "--sheet-system",
        "1992",
        "--product",
        "nmt",
        "-o",
        "./data",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "pl=EVRF2007,cz=Bpv",
        "--bbox",
        "21.0,52.0,21.2,52.2",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 13.3-13.5E / 49.7-49.8N — Plzen, west of the PL envelope (14.07E)
    _CZ_ONLY = [
        "elevation",
        "download",
        "--product",
        "nmt",
        "-o",
        "./data",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "pl=EVRF2007,cz=Bpv",
        "--bbox",
        "13.3,49.7,13.5,49.8",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # an area reaching CZ is a cutout (ADR-038): CZ native, PL from WCS
    _CUTOUT = ["--cutout", "--horizontal-crs", "EPSG:5514"]

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_border_bbox_splits_into_both_countries(self, mock_pl, mock_cz, tmp_path):
        mock_pl.return_value = 0
        mock_cz.return_value = 0

        result = main(self._BORDER + self._CUTOUT + ["-o", str(tmp_path)])

        assert result == 0
        expected_parent = {
            "bbox": [18.4, 49.55, 18.8, 49.75],
            "bbox_crs": "EPSG:4326",
            "countries": ["CZ", "PL"],
        }
        # PL: the cutout received the same parent_request
        assert mock_pl.call_args.args[3] == expected_parent
        # CZ: flow called with the same parent_request and a bbox in Krovak
        cz_kwargs = mock_cz.call_args.kwargs
        assert cz_kwargs["parent_request"] == expected_parent
        assert cz_kwargs["bbox"].crs == "EPSG:5514"

    def test_border_bbox_without_cutout_rejected_before_download(
        self, tmp_path, capsys
    ):
        """ADR-038 D3: PL sheets + CZ cutout is not a mode; --cutout or --country pl."""
        with (
            patch("kartograf.download.data._download_cz") as mock_cz,
            patch("kartograf.download.data.DownloadManager") as mock_manager,
        ):
            result = main(self._BORDER + ["-o", str(tmp_path)])
        assert result == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: obszar siega CZ") and "--country pl" in err
        mock_cz.assert_not_called()
        mock_manager.assert_not_called()
        assert not (tmp_path / "nmt").exists()

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_country_order_is_deterministic(self, mock_pl, mock_cz, tmp_path):
        """Country order from all_countries() — sorted (CZ before PL)."""
        mock_pl.return_value = 0
        mock_cz.return_value = 0

        main(self._BORDER + self._CUTOUT + ["-o", str(tmp_path)])

        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["countries"] == sorted(parent["countries"])

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_pl_branch_does_not_poison_cz_args(self, mock_pl, mock_cz, tmp_path):
        """Each country works on its own COPY of args: the CZ flow gets raw values."""
        mock_pl.return_value = 0
        mock_cz.return_value = 0

        main(self._BORDER + self._CUTOUT + ["-o", str(tmp_path)])

        # the mock holds a REFERENCE to the Namespace — had the PL branch (run
        # after CZ) mutated a shared object, the CZ values would be narrowed
        cz_args = mock_cz.call_args.args[0]
        assert cz_args.resolution == {"pl": "1m", "cz": "2m"}
        assert cz_args.vertical_crs == {"pl": "EVRF2007", "cz": "Bpv"}
        assert cz_args.sheet_system == "1992"
        pl_args = mock_pl.call_args.args[0]
        assert (pl_args.resolution, pl_args.vertical_crs) == ("1m", "EVRF2007")

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_pl_only_bbox_no_cz_flow_but_parent_request_present(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        mock_find.return_value = ["N-34-138-A-b-1-1"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager

        result = main(self._PL_ONLY + ["-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"]["parent_request"]["countries"] == ["PL"]

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.DownloadManager")
    def test_cz_only_bbox_skips_pl_flow(self, mock_manager_class, mock_cz, tmp_path):
        """A bbox entirely in CZ (13.3-13.5E, west of 14.07E): CUZK only."""
        mock_cz.return_value = 0
        result = main(self._CZ_ONLY + self._CUTOUT + ["-o", str(tmp_path)])

        assert result == 0
        mock_manager_class.assert_not_called()
        assert mock_cz.call_args.kwargs["parent_request"]["countries"] == ["CZ"]

    def test_single_country_error_has_no_country_hint(self, tmp_path, capsys):
        """With a single country the --country hint would be empty."""
        result = main(
            self._CZ_ONLY + self._CUTOUT + ["--resolution", "1m", "-o", str(tmp_path)]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "CZ nie ma rozdzielczosci 1m" in err
        assert "uzyj jawnie" not in err and "pl=" not in err

    @patch("kartograf.download.data._download_cz")
    def test_explicit_cz_bbox_gets_parent_request(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
                *self._CUTOUT,
            ]
        )
        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["countries"] == ["CZ"]
        assert parent["bbox_crs"] == "EPSG:5514"
        # explicit country: bbox without clipping (the original passed)
        assert mock_cz.call_args.kwargs["bbox"] == BBox(
            -447000, -1114000, -446000, -1113000, "EPSG:5514"
        )

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_explicit_pl_bbox_not_clipped(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Explicit --country pl: the whole cross-border bbox goes to PL, without CZ."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager

        result = main(self._BORDER + ["--country", "pl", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        used_bbox = mock_find.call_args.args[0]
        assert (used_bbox.min_x, used_bbox.max_x) == (18.4, 18.8)
        assert mock_manager_class.call_args.kwargs["sidecar_extra"] == {
            "parent_request": {
                "bbox": [18.4, 49.55, 18.8, 49.75],
                "bbox_crs": "EPSG:4326",
                "countries": ["PL"],
            }
        }

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_auto_clips_cz_part_to_country_extent(self, mock_pl, mock_cz, tmp_path):
        """Auto mode clips the CZ part to the country envelope (18.86E)."""
        from kartograf.providers.cuzk.raster import bbox_to_crs

        mock_pl.return_value = 0
        mock_cz.return_value = 0

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "18.4,49.55,19.5,49.75",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path),
                "-q",
                *self._CUTOUT,
            ]
        )

        assert result == 0
        expected = bbox_to_crs(
            BBox(18.4, 49.55, 18.86, 49.75, "EPSG:4326"), "EPSG:5514"
        )
        assert mock_cz.call_args.kwargs["bbox"] == expected
        # parent_request carries the ORIGINAL request bbox (before clipping)
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["bbox"] == [18.4, 49.55, 19.5, 49.75]

    # --- S3: clipping under auto is explicit (Info:) and does not widen edges ---

    def _run_auto(self, mock_find, mock_manager_class, tmp_path, bbox, crs, extra=()):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")
        return main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                bbox,
                "--bbox-crs",
                crs,
                "-o",
                str(tmp_path),
                "-q",
                *extra,
            ]
        )

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_rozewie_clips_only_north_edge_and_informs(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Rozewie: N clipped to 54.90°N, W/S/E EXACTLY from the request + Info:.

        Before S3 the envelope of the whole clipped rectangle widened the untouched
        edges (454889.74 / 772961.81 / 459082.21), without any message.
        """
        rc = self._run_auto(
            mock_find,
            mock_manager_class,
            tmp_path,
            "455000,773000,459000,784000",
            "EPSG:2180",
        )

        assert rc == 0
        mock_cz.assert_not_called()
        used = mock_find.call_args.args[0]
        assert (used.min_x, used.min_y, used.max_x) == (455000, 773000, 459000)
        assert used.max_y < 784000
        assert used.crs == "EPSG:2180"
        err = capsys.readouterr().err
        assert "Info: --country auto: czesc PL przycieta" in err
        assert "N: 54,90 st.N" in err
        assert "request.sheet" in err and "plik i request.bbox" not in err
        assert "poza zasiegiem PL/CZ" in err
        assert "--country pl" in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_osinow_west_edge_info_keeps_parent_request(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        rc = self._run_auto(
            mock_find,
            mock_manager_class,
            tmp_path,
            "14.03,52.835,14.16,52.85",
            "EPSG:4326",
        )

        assert rc == 0
        used = mock_find.call_args.args[0]
        assert (used.min_x, used.min_y, used.max_x, used.max_y) == (
            14.07,
            52.835,
            14.16,
            52.85,
        )
        parent = mock_manager_class.call_args.kwargs["sidecar_extra"]["parent_request"]
        assert parent["bbox"] == [14.03, 52.835, 14.16, 52.85]
        err = capsys.readouterr().err
        assert "W: 14,07 st.E" in err
        assert "poza zasiegiem PL/CZ" in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_bogatynia_cz_clipped_but_nothing_lost(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """The clipped CZ part lies in PL: one Info: (CZ, 51,06°N), nothing lost."""
        mock_cz.return_value = 0
        with patch("kartograf.download.data._download_pl_cutout", return_value=0):
            rc = self._run_auto(
                mock_find,
                mock_manager_class,
                tmp_path,
                "15.0,50.9,15.3,51.2",
                "EPSG:4326",
                self._CUTOUT,
            )

        assert rc == 0
        err = capsys.readouterr().err
        # clipping messages only (the vertical CRS Info of d1 is separate)
        info_lines = [
            line
            for line in err.splitlines()
            if line.startswith("Info:") and "Bpv" not in line
        ]
        assert len(info_lines) == 1
        assert "czesc CZ przycieta" in info_lines[0]
        assert "N: 51,06 st.N" in info_lines[0]
        assert "poza zasiegiem" not in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_bbox_inside_both_extents_stays_silent(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Silence regression: no clipping Info: without clipping."""
        mock_cz.return_value = 0
        with patch("kartograf.download.data._download_pl_cutout", return_value=0):
            rc = self._run_auto(
                mock_find,
                mock_manager_class,
                tmp_path,
                "18.4,49.55,18.8,49.75",
                "EPSG:4326",
                self._CUTOUT,
            )

        assert rc == 0
        err = capsys.readouterr().err
        assert "przycieta" not in err and "poza zasiegiem" not in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_corner_loss_reported_even_when_edges_look_covered(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """13-15°E x 53-55°N: the corner loss shows only after the split."""
        rc = self._run_auto(
            mock_find, mock_manager_class, tmp_path, "13,53,15,55", "EPSG:4326"
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "W: 14,07 st.E, N: 54,90 st.N" in err
        assert "13,00 st.E-15,00 st.E x 53,00 st.N-55,00 st.N" in err
        assert "% powierzchni zadania" in err

    def test_area_outside_extents_splits_bbox_into_cells(self):
        """Pure function: cells outside all rectangles + the share."""
        from kartograf.download.area import (
            area_outside_extents as _area_outside_extents,
        )

        pl = BBox(14.07, 49.0, 24.2, 54.9, "EPSG:4326")
        cz = BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326")

        # bbox entirely inside PL
        assert _area_outside_extents(BBox(18, 50, 19, 51, "EPSG:4326"), [pl, cz]) == (
            None,
            0.0,
        )
        # strip west of 14.07 - loss only there (a column of cells)
        lost, share = _area_outside_extents(
            BBox(14.0, 52.0, 14.2, 52.1, "EPSG:4326"), [pl]
        )
        assert lost == BBox(14.0, 52.0, 14.07, 52.1, "EPSG:4326")
        assert share == pytest.approx(0.07 / 0.2)
        # corner: the W edge is inside the CZ longitude range, but CZ ends
        # at 51.06°N - the loss is L-shaped, the envelope is the whole bbox
        lost, share = _area_outside_extents(BBox(13, 53, 15, 55, "EPSG:4326"), [pl, cz])
        assert lost == BBox(13, 53, 15, 55, "EPSG:4326")
        assert 0.5 < share < 0.6
        # bbox entirely outside — everything lost
        lost, share = _area_outside_extents(BBox(10, 56, 11, 57, "EPSG:4326"), [pl, cz])
        assert lost == BBox(10, 56, 11, 57, "EPSG:4326") and share == 1.0

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_pl_part_of_cz_crs_bbox_leaves_krovak_pinned(
        self, mock_pl, mock_cz, tmp_path
    ):
        """A request in Krovak also routed to PL: the 5514->2180 step is pinned.

        The bbox 13.73-14.46E / 49.95-50.35N (given in EPSG:5514) crosses both
        countries and is ACTUALLY clipped for PL (the PL envelope starts
        at 14.07E) - i.e. it enters the path in which the GUGiK request area
        could result from unpinned Krovak transformations.
        """
        from kartograf.core import bbox as core_bbox
        from kartograf.core.bbox import is_czech_crs
        from kartograf.download.countries import bbox_to_wgs84 as _bbox_to_wgs84
        from kartograf.providers.cuzk import raster

        mock_pl.return_value = 0
        mock_cz.return_value = 0

        with (
            patch.object(raster, "bbox_to_crs", wraps=raster.bbox_to_crs) as pinned,
            patch.object(
                core_bbox, "_transformer", wraps=core_bbox._transformer
            ) as plain,
        ):
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--bbox=-788231,-1052442,-741087,-1013379",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--sheet-system",
                    "1992",
                    "-o",
                    str(tmp_path),
                    "-q",
                    *self._CUTOUT,
                ]
            )

        assert result == 0
        # the PL branch got a bbox in the Polish CRS
        pl_bbox = mock_pl.call_args.args[2]
        assert pl_bbox.crs == "EPSG:2180"
        # ...clipped to the PL envelope (request reached 13.73E, PL from 14.07E)
        assert _bbox_to_wgs84(pl_bbox).min_x > 13.9
        # ...and derived from Krovak with the pinned operation
        assert any(call.args[1] == "EPSG:2180" for call in pinned.call_args_list)
        # an unpinned transformer never targets a Czech CRS
        assert not any(is_czech_crs(call.args[1]) for call in plain.call_args_list)

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_cz_failure_does_not_skip_pl_and_warns(
        self, mock_pl, mock_cz, tmp_path, capsys
    ):
        """A failure of the first country cancels neither the second nor the task."""
        mock_pl.return_value = 0
        mock_cz.return_value = 1  # CZ goes first (sorting) and fails

        result = main(self._BORDER + self._CUTOUT + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        mock_pl.assert_called_once()
        err = capsys.readouterr().err
        assert "Warning:" in err
        assert "czesc CZ zadania zakonczyla sie bledem" in err
        assert "pobrano PL" in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_pl_failure_with_cz_success_warns_and_returns_0(
        self, mock_pl, mock_cz, tmp_path, capsys
    ):
        mock_pl.side_effect = lambda task, run, bbox, parent: run.fail(
            "PL", "PL", "WCS GUGiK 503", "download"
        )
        mock_cz.return_value = 0

        result = main(self._BORDER + self._CUTOUT + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        err = capsys.readouterr().err
        assert "Error: WCS GUGiK 503" in err
        assert "Warning: czesc PL zadania zakonczyla sie bledem" in err

    # --- A3-2: rectangular country envelopes vs exit code ---

    # 14.40-14.45E / 50.05-50.10N - Prague, deep in CZ, but inside the PL
    # rectangle (from 14.07E): auto also queries GUGiK, which has no data there
    _PRAGUE = [
        "elevation",
        "download",
        "--product",
        "nmt",
        "-o",
        "./data",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "pl=EVRF2007,cz=Bpv",
        "--bbox",
        "14.40,50.05,14.45,50.10",
        "--bbox-crs",
        "EPSG:4326",
        "--sheet-system",
        "1992",
        "-q",
        "--cutout",
        "--horizontal-crs",
        "EPSG:5514",
    ]

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_auto_one_country_failed_other_succeeded_returns_0(
        self, mock_pl, mock_cz, tmp_path, capsys
    ):
        """A country with no data in the other's area does not break the task."""
        mock_pl.side_effect = lambda task, run, bbox, parent: run.fail(
            "PL", "PL", "WCS GUGiK: obszar bez danych", "no_coverage"
        )
        mock_cz.return_value = 0

        result = main(self._PRAGUE + ["-o", str(tmp_path)])

        assert result == 0
        err = capsys.readouterr().err
        assert "Error: WCS GUGiK: obszar bez danych" in err
        assert "Warning: czesc PL zadania zakonczyla sie bledem" in err
        assert "pobrano CZ" in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_auto_all_countries_failed_returns_1(
        self, mock_pl, mock_cz, tmp_path, capsys
    ):
        """When all countries failed, the exit code stays unchanged."""
        mock_pl.return_value = 1
        mock_cz.return_value = 1

        result = main(self._PRAGUE + ["-o", str(tmp_path)])

        assert result == 1
        assert "Warning:" not in capsys.readouterr().err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_explicit_country_failure_still_returns_1(
        self, mock_pl, mock_cz, tmp_path, capsys
    ):
        """Explicit --country: the user knows the extent, so a failure is a failure."""
        mock_pl.return_value = 1

        result = main(self._PRAGUE + ["--country", "pl", "-o", str(tmp_path)])

        assert result == 1
        mock_pl.assert_called_once()
        mock_cz.assert_not_called()
        assert "Warning:" not in capsys.readouterr().err

    @patch("kartograf.download.data.DownloadManager")
    def test_sheet_mode_has_no_parent_request(self, mock_manager_class, tmp_path):
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = DownloadResult(
            succeeded=[tmp_path / "x.asc"]
        )
        mock_manager_class.return_value = mock_manager
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs.get("sidecar_extra") is None

    # --- N6-2: PL-only flags resolve `auto` instead of failing the task ---

    def _pl_mocks(self, mock_manager_class, mock_find, tmp_path, sheet):
        """PL branch: one sheet, the manager returns a ready file."""
        mock_find.return_value = [sheet]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        return mock_manager

    @pytest.mark.parametrize(("product", "label"), _PL_ONLY_CHOICES)
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_pl_only_flags_from_registry(
        self, mock_manager_class, mock_find, mock_cz, product, label, tmp_path, capsys
    ):
        """A label without a CZ source of the product in the registry resolves
        ``auto`` to PL with one Info line; CZ never runs and PL downloads that
        variant."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "M-34-86-D-d-4-3")

        result = main(
            self._BORDER
            + ["--product", product, "--resolution", label, "-o", str(tmp_path)]
        )

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert (
            f"Info: --country auto -> pl (--resolution {label} dotyczy tylko PL)\n"
            in err
        )
        variant = mock_manager_class.call_args.kwargs["provider"].variant
        assert (variant.product, variant.label) == (product, label)

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_auto_with_kron86_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """KRON86 is unreachable for CZ (ADR-023 e): country = PL."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "M-34-86-D-d-4-3")

        result = main(self._BORDER + ["--vertical-crs", "KRON86", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert "--country auto -> pl" in err
        assert "KRON86" in err

    def test_border_bbox_with_bpv_unresolvable_for_pl(self, tmp_path, capsys):
        """A plain value inadmissible for one country: the per-country hint."""
        result = main(
            self._BORDER + self._CUTOUT + ["--vertical-crs", "Bpv", "-o", str(tmp_path)]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Bpv nie jest ukladem wysokosci PL" in err
        assert "--vertical-crs pl=...,cz=..." in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_auto_pl_only_flags_do_not_clip_bbox(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Resolving to PL works like an explicit --country pl: without clipping.

        The bbox 13.5-14.5E reaches west of the PL envelope (14.07E), so in auto
        mode the PL branch would get it clipped - after resolution the PL-only
        flag must get the original.
        """
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "6.179.12.20")

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "13.5,50.0,14.5,50.4",
                "--bbox-crs",
                "EPSG:4326",
                "--sheet-system",
                "1992",
                "--resolution",
                "1m",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        used_bbox = mock_find.call_args.args[0]
        assert (used_bbox.min_x, used_bbox.max_x) == (13.5, 14.5)

    def test_explicit_cz_with_sheet_system_still_rejected(self, tmp_path, capsys):
        """Explicit --country cz: validation unchanged (nothing to resolve)."""
        result = main(
            self._BORDER
            + self._CUTOUT
            + ["--country", "cz", "--sheet-system", "2000", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--sheet-system dotyczy tylko PL" in capsys.readouterr().err

    @patch("kartograf.download.data._download_cz")
    def test_border_bbox_with_cutout_runs_both_countries(self, mock_cz, tmp_path):
        """ADR-027/038: the cutout is not a Czech mode - the border area in one
        command gives two cutouts with a shared parent_request."""
        mock_cz.return_value = 0
        with patch(
            "kartograf.download.data._download_pl_bbox", return_value=0
        ) as mock_pl:
            result = main(
                self._BORDER
                + [
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:2180",
                    "--vertical-crs",
                    "EVRF2007",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert result == 0
        mock_cz.assert_called_once()
        mock_pl.assert_called_once()
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent == mock_pl.call_args.args[3]
        # the CZ part goes in the RESULT CRS (cz_crs = target), not in Krovak
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:2180"

    def test_resolution_5m_border_cutout_rejected_for_pl(self, tmp_path, capsys):
        """5m exists on both sides, but a border area is a cutout (ADR-038 D3)
        and the PL cutout is 1 m only: an error before any download."""
        with patch("kartograf.download.data._download_cz") as mock_cz:
            result = main(
                self._BORDER
                + self._CUTOUT
                + ["--resolution", "5m", "-o", str(tmp_path)]
            )
        assert result == 1
        assert "wycinki PL (--cutout) sa tylko 1 m" in capsys.readouterr().err
        mock_cz.assert_not_called()

    def test_bbox_outside_known_countries(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "2.0,40.0,2.5,40.5",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        assert "kraju" in capsys.readouterr().err

    def test_laz_bbox_border_auto_requires_model(self, tmp_path, capsys):
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "laz",
                "--country",
                "auto",
                "--bbox",
                "18.4,49.55,18.8,49.75",
                "--bbox-crs",
                "EPSG:4326",
                "--vertical-crs",
                "EVRF2007",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "obszar siega CZ: podaj --model" in err
        assert "--country pl" in err
        assert not (tmp_path / "laz").exists()

    def test_laz_sheet_untouched_by_guard(self, tmp_path, capsys):
        """The LAZ sheet code mode does not go through the cross-border guard.

        Sheet code M-34-86-D-d-4-3 lies at the CZ border (inside the CZ envelope),
        so in area mode the guard would fire - the sheet code's country is however
        unambiguous.
        """
        from kartograf.providers.pl import gugik_laz

        with patch.object(gugik_laz, "GugikLazProvider") as provider_cls:
            provider_cls.return_value.select_tiles.return_value = _selection([])
            result = main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "M-34-86-D-d-4-3",
                    "--product",
                    "laz",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert result == 1
        err = capsys.readouterr().err
        assert "--country pl" not in err
        assert "Brak kafli LAZ" in err

    @patch("kartograf.providers.cuzk.raster.bbox_to_crs")
    def test_cz_bbox_transform_error_returns_1_with_remedy(
        self, mock_to_crs, tmp_path, capsys
    ):
        """TransformError in CZ bbox normalisation = a CLI message, not a traceback."""
        from kartograf.transform.crs import TransformUnavailableError

        mock_to_crs.side_effect = TransformUnavailableError(
            "brak bezpiecznej operacji", remedy="podaj --horizontal-crs EPSG:5514"
        )
        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "419000,230000,426000,237000",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
                *self._CUTOUT,
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "brak bezpiecznej operacji" in err
        assert "Remedium" in err

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.country_bbox")
    def test_country_bbox_transform_error_returns_1_before_download(
        self, mock_country_bbox, mock_cz, tmp_path, capsys
    ):
        """TransformError splitting the area into countries = code 1, no download."""
        from kartograf.transform.crs import TransformUnavailableError

        mock_country_bbox.side_effect = TransformUnavailableError(
            "brak operacji dla obwiedni kraju", remedy="podaj --bbox-crs EPSG:2180"
        )
        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "18.60,49.752,18.65,49.768",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path / "out"),
                "-q",
                *self._CUTOUT,
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "Error: brak operacji dla obwiedni kraju" in err
        assert "Remedium: podaj --bbox-crs EPSG:2180" in err
        mock_cz.assert_not_called()
        assert not (tmp_path / "out").exists()


class TestAutoSplitGeometry:
    """--geometry in auto mode: the envelope decides the countries."""

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.download.data._download_pl_cutout")
    def test_geometry_border_splits(
        self,
        mock_pl,
        mock_overall,
        mock_cz,
        mock_read_crs,
        tmp_path,
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        # envelope in 2180 intersecting both countries (Cieszyn area:
        # 18.513-18.792E / 49.666-49.847N — inside the CZ and PL envelopes)
        mock_overall.return_value = BBox(
            465000.0, 200000.0, 485000.0, 220000.0, "EPSG:2180"
        )
        mock_pl.return_value = 0
        mock_cz.return_value = 0

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(geometry_file),
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["bbox"] == [465000.0, 200000.0, 485000.0, 220000.0]
        assert parent["bbox_crs"] == "EPSG:2180"
        assert parent["countries"] == ["CZ", "PL"]
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:5514"
        assert mock_pl.call_args.args[3] == parent

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    def test_geometry_pl_only_skips_cz(
        self,
        mock_manager_class,
        mock_find,
        mock_overall,
        mock_cz,
        mock_read_crs,
        tmp_path,
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw — outside the CZ envelope
        mock_find.return_value = ["N-34-138-A-b-1-1"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(geometry_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        parent = mock_manager_class.call_args.kwargs["sidecar_extra"]["parent_request"]
        assert parent["countries"] == ["PL"]

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    def test_geometry_auto_clipping_does_not_print_pl_info(
        self,
        mock_manager_class,
        mock_find,
        mock_overall,
        mock_cz,
        mock_read_crs,
        tmp_path,
        capsys,
    ):
        """PL downloads sheets for the whole geometry: no false Info about clipping."""
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(
            455000.0, 773000.0, 459000.0, 784000.0, "EPSG:2180"
        )  # Rozewie — the envelope reaches beyond 54.90°N
        mock_find.return_value = ["N-33-38-B-d-1-1"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(geometry_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert "Info: --country auto:" not in err
        assert "poza zasiegiem PL/CZ" not in err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.download.data._download_cz", return_value=0)
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.download.data._download_pl_cutout", return_value=0)
    def test_geometry_auto_informs_only_clipped_cz(
        self, pl, overall, cz, read_crs, tmp_path, capsys
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        overall.return_value = BBox(465000.0, 200000.0, 505000.0, 220000.0, "EPSG:2180")

        assert (
            main(
                [
                    "elevation",
                    "download",
                    "--cutout",
                    "--horizontal-crs",
                    "EPSG:5514",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--geometry",
                    str(geometry_file),
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )
            == 0
        )
        cz.assert_called_once()
        err = capsys.readouterr().err
        assert "Info: --country auto: czesc CZ przycieta" in err
        assert "Info: --country auto: czesc PL" not in err
        assert "poza zasiegiem PL/CZ" not in err

    @patch("kartograf.download.data._download_cz")
    def test_geometry_explicit_cz_gets_parent_request(self, mock_cz, tmp_path):
        """Explicit --country cz: parent_request from the request-CRS envelope."""
        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp),
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["countries"] == ["CZ"]
        assert parent["bbox_crs"] == "EPSG:5514"
        assert parent["bbox"] == [
            mock_cz.call_args.kwargs["bbox"].min_x,
            mock_cz.call_args.kwargs["bbox"].min_y,
            mock_cz.call_args.kwargs["bbox"].max_x,
            mock_cz.call_args.kwargs["bbox"].max_y,
        ]

    @patch("kartograf.download.data._download_cz")
    def test_geometry_in_task_crs_skips_transform(self, mock_run_cz, tmp_path):
        """File already in EPSG:5514: the envelope goes to CUZK bit for bit, no step."""
        shp = _write_krovak_shp(tmp_path)
        mock_run_cz.return_value = 0

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp),
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        bbox = mock_run_cz.call_args.kwargs["bbox"]
        assert bbox.min_x == -447000.0
        assert bbox.min_y == -1114000.0
        assert bbox.max_x == -446000.0
        assert bbox.max_y == -1113000.0
        assert bbox.crs == "EPSG:5514"

    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.core.geometry.read_source_crs")
    def test_geometry_cz_transform_unavailable_reports_remedy(
        self, mock_read_crs, mock_run_cz, tmp_path, capsys
    ):
        """No safe operation: exit code 1 and Remedium on stderr, zero downloads."""
        from kartograf.transform.crs import TransformUnavailableError

        shp = tmp_path / "area.shp"
        shp.write_bytes(b"stub")
        mock_read_crs.side_effect = TransformUnavailableError(
            "brak operacji", rejected=[], remedy="zainstaluj siatki"
        )

        result = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(shp),
                "--country",
                "cz",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        assert "Remedium: zainstaluj siatki" in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_outside_known_countries(
        self, mock_overall, mock_read_crs, tmp_path, capsys
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(2.0, 40.0, 2.5, 40.5, "EPSG:4326")

        result = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(geometry_file),
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        assert "kraju" in capsys.readouterr().err


class TestPublicApiCz:
    """Public API exports for the CZ modules (task 18)."""

    def test_cz_exports_available(self):
        from kartograf import CuzkRasterProvider, ParserTM33, create_cz_raster_provider

        assert ParserTM33("302_5550").get_bbox().crs == "EPSG:3045"
        provider = create_cz_raster_provider("nmpt", "0.5m", vertical_crs="Bpv")
        assert isinstance(provider, CuzkRasterProvider)
        assert provider.descriptor_key == "cz.cuzk.dmpok"

    def test_version_bumped(self):
        from kartograf import __version__

        assert __version__ == "0.8.0-dev"


class _PartialSheetProvider(_SheetProvider):
    """A provider with origin: sheets with ``partial`` suffixes have
    ``full_sheet=False`` (the newest campaign is partial, E2E-B C12-a/C14-b)."""

    descriptor_key = "pl.gugik.nmt_1m"

    def __init__(self, partial: tuple[str, ...]):
        super().__init__({})
        self.partial = partial

    def source_info(self, sheet):
        return {
            "url": f"https://opendata.geoportal.gov.pl/NMT/1/1_{sheet}.asc",
            "layer": "SkorowidzNMT2025",
            "acquisition_date": "2025-10-21",
            "full_sheet": not sheet.endswith(self.partial),
        }


class TestPartialSheetWarning:
    """E13: ``Warning:`` on selecting a partial sheet (sheet code and list paths).

    The selection rule (ADR-028: newest campaign) is unchanged - the file is
    downloaded, but the user knows it may have a lot of nodata/black.
    """

    @staticmethod
    def _run(tmp_path, partial, argv):
        from kartograf.download.storage import FileStorage

        provider = _PartialSheetProvider(partial)
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with (
            patch(
                "kartograf.download.data._create_provider_and_storage",
                return_value=(provider, storage),
            ),
            patch(
                "kartograf.download.data.find_sheets_for_bbox",
                return_value=list(TestSheetListExitCode._SHEETS),
            ),
        ):
            return main([*argv, "-o", str(tmp_path)])

    def test_single_sheet_partial_sheet_warns(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            ("-1",),
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-1",
            ],
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "niepelna" in err and "N-34-130-D-d-2-1" in err
        (sidecar,) = (
            p
            for p in tmp_path.rglob("*.meta.json")
            if "versions" not in p.relative_to(tmp_path).parts
        )
        meta = json.loads(sidecar.read_text("utf-8"))
        assert meta["extra"]["source"]["full_sheet"] is False

    def test_single_sheet_full_sheet_is_silent(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            ("-9",),
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-1",
            ],
        )

        assert rc == 0
        assert "niepelna" not in capsys.readouterr().err

    def test_sheet_list_names_only_partial_sheets(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            ("-2", "-4"),
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet-system",
                "1992",
                "--bbox",
                "630000,480000,637000,487000",
            ],
        )

        assert rc == 0
        warning = next(
            line for line in capsys.readouterr().err.splitlines() if "niepelna" in line
        )
        assert "Warning:" in warning and "2 arkuszy" in warning
        assert "N-34-130-D-d-2-2" in warning and "N-34-130-D-d-2-4" in warning
        assert "N-34-130-D-d-2-1" not in warning

    def test_hierarchy_partial_sheet_warns(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            ("-3",),
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
            ],
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "niepelna" in err and "N-34-130-D-d-2-3" in err


class TestSingleSheetSkipMessage:
    """E15 + spec 4.5: one sheet code reports the version status per file."""

    @staticmethod
    def _run(tmp_path, provider, *extra):
        from kartograf.download.storage import FileStorage

        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with patch(
            "kartograf.download.data._create_provider_and_storage",
            return_value=(provider, storage),
        ):
            return main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "N-34-130-D-d-2-4",
                    "-o",
                    str(tmp_path),
                    *extra,
                ]
            )

    def test_second_run_reports_local_version(self, tmp_path, capsys):
        provider = _SheetProvider({})
        assert self._run(tmp_path, provider) == 0
        first = capsys.readouterr().out
        assert "N-34-130-D-d-2-4: nowa wersja " in first

        assert self._run(tmp_path, provider) == 0

        out = capsys.readouterr().out
        assert provider.calls == ["N-34-130-D-d-2-4"]  # the second run without network
        assert "nowa wersja" not in out
        assert "N-34-130-D-d-2-4: lokalna wersja " in out

    def test_force_reports_unchanged_content(self, tmp_path, capsys):
        provider = _SheetProvider({})
        self._run(tmp_path, provider)
        capsys.readouterr()

        assert self._run(tmp_path, provider, "--force") == 0

        assert "N-34-130-D-d-2-4: bez zmian " in capsys.readouterr().out
        assert len(provider.calls) == 2


class _CachingSheetProvider(_SheetProvider):
    """``_SheetProvider`` that reads/writes the CLI cache like GugikProvider."""

    def __init__(self, cache):
        super().__init__({})
        self.cache = cache

    def download(self, sheet, path, timeout=30):
        if self.cache.get_record("nmt", "1m", "EVRF2007", sheet) is None:
            self.cache.set_record("nmt", "1m", "EVRF2007", sheet, {"godlo": sheet})
        return super().download(sheet, path, timeout)


class TestUnreadableMetadataCache:
    """An unreadable ``.kartograf_cache.db`` in the cwd does not block downloads.

    Before the fix every sheet of a list failed with ``file is not a
    database`` (code 1, nothing downloaded) and a single sheet code ended with
    ``Error: DatabaseError`` from the ``main`` barrier.
    """

    _SHEETS = [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]

    @staticmethod
    def _broken_cache() -> Path:
        db = Path.cwd() / ".kartograf_cache.db"
        db.write_bytes(b"to nie jest baza SQLite\n" * 200)
        return db

    @staticmethod
    def _run(tmp_path, argv, sheets=()):
        from kartograf.download.storage import FileStorage

        out = tmp_path / "out"
        storage = FileStorage(out, resolution="1m", vertical_crs="EVRF2007")
        providers = []

        def create(*_args, cache=None, **_kwargs):
            providers.append(_CachingSheetProvider(cache))
            return providers[-1], storage

        with (
            patch(
                "kartograf.download.data._create_provider_and_storage",
                side_effect=create,
            ),
            patch(
                "kartograf.download.data.find_sheets_for_bbox",
                return_value=list(sheets),
            ),
        ):
            rc = main([*argv, "-o", str(out)])
        files = sorted(
            p.name
            for p in out.rglob("*.asc")
            if "versions" not in p.relative_to(out).parts
        )
        return rc, providers, files

    @staticmethod
    def _cache_warnings(err: str) -> list[str]:
        return [line for line in err.splitlines() if "cache metadanych" in line]

    @pytest.mark.parametrize("workers", ["1", "4"])
    @pytest.mark.parametrize("quiet", [False, True], ids=["verbose", "quiet"])
    def test_sheet_list_downloads_with_one_warning(
        self, tmp_path, capsys, workers, quiet
    ):
        db = self._broken_cache()
        argv = [
            "elevation",
            "download",
            "--sheet-system",
            "1992",
            "--product",
            "nmt",
            "-o",
            "./data",
            "--country",
            "auto",
            "--resolution",
            "pl=1m,cz=2m",
            "--vertical-crs",
            "pl=EVRF2007,cz=Bpv",
            "--bbox",
            "630000,480000,637000,487000",
        ]
        argv += ["--country", "pl", "--workers", workers]
        if quiet:
            argv.append("-q")

        rc, providers, files = self._run(tmp_path, argv, sheets=self._SHEETS)

        assert rc == 0
        assert files == [f"{g}.asc" for g in self._SHEETS]
        assert sorted(providers[0].calls) == self._SHEETS
        err = capsys.readouterr().err
        assert "Error:" not in err
        assert "file is not a database" in err
        warnings = self._cache_warnings(err)
        assert len(warnings) == 1
        assert warnings[0].startswith(f"Warning: cache metadanych nieczytelny ({db})")
        assert warnings[0].isascii()
        assert db.read_bytes().startswith(b"to nie jest baza")  # untouched

    def test_single_sheet_downloads_with_warning(self, tmp_path, capsys):
        self._broken_cache()

        rc, providers, files = self._run(
            tmp_path,
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
            ],
        )

        assert rc == 0
        assert files == ["N-34-130-D-d-2-4.asc"]
        assert providers[0].calls == ["N-34-130-D-d-2-4"]
        captured = capsys.readouterr()
        assert "N-34-130-D-d-2-4: nowa wersja " in captured.out
        assert "Error:" not in captured.err
        assert len(self._cache_warnings(captured.err)) == 1
        assert captured.err.startswith("Warning: cache metadanych nieczytelny (")

    def test_warning_once_per_command_not_per_process(self, tmp_path, capsys):
        """Every command reports the broken cache again (dedup reset)."""
        self._broken_cache()
        argv = [
            "elevation",
            "download",
            "--product",
            "nmt",
            "-o",
            "./data",
            "--country",
            "auto",
            "--resolution",
            "pl=1m,cz=2m",
            "--vertical-crs",
            "pl=EVRF2007,cz=Bpv",
            "--sheet",
            "N-34-130-D-d-2-4",
            "--force",
        ]

        self._run(tmp_path, argv)
        self._run(tmp_path, argv)

        assert len(self._cache_warnings(capsys.readouterr().err)) == 2


class TestLazSidecarRequestFilters:
    """E16 (E2E-B C13-f): LAZ sidecar ``request`` records --year/--min-density."""

    @staticmethod
    def _run(tmp_path, *extra):
        tile = TestCmdDownloadLaz()._fake_tiles()[0]
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection([tile])

        def fake_download(url, target, **kwargs):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"LASF")
            return target

        instance.download_tile.side_effect = fake_download
        with patch(
            "kartograf.providers.pl.gugik_laz.GugikLazProvider", return_value=instance
        ):
            rc = main(
                [
                    "elevation",
                    "download",
                    "--sheet",
                    "M-34-27-B-b-2-1",
                    "--product",
                    "laz",
                    "--vertical-crs",
                    "EVRF2007",
                ]
                + list(extra)
                + ["-o", str(tmp_path), "-q"]
            )
        (sidecar,) = (
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        )
        return rc, json.loads(sidecar.read_text(encoding="utf-8"))["request"]

    def test_filters_recorded(self, tmp_path):
        rc, request = self._run(tmp_path, "--year", "2023", "--min-density", "13")

        assert rc == 0
        assert request["year"] == 2023
        assert request["min_density"] == 13

    def test_no_filters_no_keys(self, tmp_path):
        rc, request = self._run(tmp_path)

        assert rc == 0
        assert "year" not in request and "min_density" not in request


class TestSheetCrsMismatchWarning:
    """E17 (E2E-A C6b/C6h): a PL-2000 zone 7 sheet published in
    EPSG:2180 coordinates - CLI ``Warning:`` on stderr (also with ``-q``
    and on skip), exit code 0; the fact is read from the result file's sidecar.

    Fixture: a truncated header of the raw GUGiK file
    ``77912_1384976_7.125.11.19.asc`` (record ``PL-2000:S7``).
    """

    SHEET = "7.125.11.19"
    URL = (
        "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/77912/"
        "77912_1384976_7.125.11.19.asc"
    )
    FIXTURE = (
        Path(__file__).parent
        / "fixtures"
        / "gugik_asc"
        / "77912_1384976_7.125.11.19.head.asc"
    )

    def _run(self, tmp_path, argv, raw=None):
        from tests.conftest import render_wfs_body, wfs_record

        body = render_wfs_body(
            [
                wfs_record(
                    self.SHEET,
                    system="PL-2000:S7",
                    akt_data="2023-03-17",
                    url=self.URL,
                )
            ]
        )
        data = self.FIXTURE.read_bytes() if raw is None else raw

        def get(url, **kwargs):
            response = Mock(spec=requests.Response)
            response.status_code = 200
            response.raise_for_status = Mock()
            response.text = body
            response.iter_content = Mock(return_value=[data])
            response.headers = {}
            return response

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=get)
        with (
            patch(
                "kartograf.transport.http.make_gugik_session",
                return_value=session,
            ),
            patch(
                "kartograf.download.data.find_sheets_for_bbox",
                return_value=[self.SHEET],
            ),
        ):
            return main([*argv, "-o", str(tmp_path / "out"), "-q"])

    @staticmethod
    def _warnings(err):
        return [
            line
            for line in err.splitlines()
            if line.startswith("Warning:") and "EPSG:2180" in line
        ]

    def test_single_sheet_warns_with_prefix(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                self.SHEET,
            ],
        )

        assert rc == 0
        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.SHEET in warning and "EPSG:2178" in warning

    def test_skip_repeats_warning(self, tmp_path, capsys):
        assert (
            self._run(
                tmp_path,
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    self.SHEET,
                ],
            )
            == 0
        )
        capsys.readouterr()

        assert (
            self._run(
                tmp_path,
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    self.SHEET,
                ],
            )
            == 0
        )

        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.SHEET in warning

    def test_sheet_list_warns(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "7564000,5530000,7566000,5532000",
                "--bbox-crs",
                "EPSG:2178",
                "--sheet-system",
                "2000",
                "--scale",
                "1:2000",
                "--country",
                "pl",
            ],
        )

        assert rc == 0
        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.SHEET in warning and "EPSG:2178" in warning

    def test_file_in_zone_crs_is_silent(self, tmp_path, capsys):
        # header moved into the real EPSG:2178 frame of 7.125.11.19
        # (7424800, 5546000, 7426400, 5547000) - B4 extent check passes
        raw = self.FIXTURE.read_bytes()
        head = raw.replace(b"567975.95", b"7424800.5", 1).replace(
            b"242449.35", b"5546000.5", 1
        )
        assert head.count(b"7424800.5") == 1 and head.count(b"5546000.5") == 1

        rc = self._run(
            tmp_path,
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                self.SHEET,
            ],
            raw=head,
        )

        assert rc == 0
        assert "innym ukladzie" not in capsys.readouterr().err


# --- Campaign and year selection in the CLI -------------------------------

_CZ_CAMPAIGN_ERROR = (
    "CZ (CUZK) nie ma kampanii - "
    "--all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza tylko PL"
)
# PL/CZ border strip (both rectangular envelopes, ADR-023)
_BORDER_BBOX = [
    "--bbox",
    "18.4,49.55,18.8,49.75",
    "--bbox-crs",
    "EPSG:4326",
    "--sheet-system",
    "1992",
]
# Ceske Budejovice: _countries_for_bbox == ("CZ",)
_CZ_ONLY_BBOX = ["--bbox", "14.45,48.95,14.50,49.00", "--bbox-crs", "EPSG:4326"]
_PL_BBOX_2180 = [
    "--bbox",
    "530000,382000,533000,386000",
    "--country",
    "pl",
    "--sheet-system",
    "1992",
]


class TestCampaignOptions:
    """Year bounds and campaigns for PL GUGiK sheets and LAZ."""

    def test_parser_max_year_and_year_for_nmt(self):
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D-d-2-4"]
        )
        assert args.all_campaigns is False
        assert args.min_year is None
        assert args.max_year is None
        assert args.year is None

        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--year",
                "2024",
                "--max-year",
                "2025",
                "--all-campaigns",
            ]
        )
        assert (args.year, args.max_year, args.all_campaigns) == (2024, 2025, True)

        args = parser.parse_args(
            [
                "elevation",
                "download",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--all-campaigns",
                "--min-year",
                "2024",
            ]
        )
        assert args.all_campaigns is True
        assert args.min_year == 2024

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_campaigns_passed_to_manager_sheet_and_list(
        self, mock_manager_class, mock_find, tmp_path
    ):
        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")
        opts = ["--all-campaigns", "--min-year", "2024", "-o", str(tmp_path), "-q"]

        assert (
            main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "N-34-130-D-d-2-4",
                    *opts,
                ]
            )
            == 0
        )
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["all_campaigns"] is True
        assert kwargs["min_year"] == 2024

        mock_manager_class.reset_mock()
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "a.asc")
        assert (
            main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    *_PL_BBOX_2180,
                    *opts,
                ]
            )
            == 0
        )
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["all_campaigns"] is True
        assert kwargs["min_year"] == 2024

    @patch("kartograf.download.data.DownloadManager")
    def test_min_year_out_of_range_error_no_network(
        self, mock_manager_class, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--min-year",
                "1800",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "Error:" in capsys.readouterr().err
        mock_manager_class.assert_not_called()

    @pytest.mark.parametrize("product", ["laz", "nmt"])
    @pytest.mark.parametrize("bound", ["--min-year", "--max-year"])
    @patch("kartograf.download.data.DownloadManager")
    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_cli_year_conflicts_with_min_max(
        self, mock_provider_cls, mock_manager_class, product, bound, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                product,
                "--year",
                "2024",
                bound,
                "2020",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 1
        assert "--year wyklucza sie z --min-year/--max-year" in capsys.readouterr().err
        mock_provider_cls.assert_not_called()
        mock_manager_class.assert_not_called()

    @pytest.mark.parametrize(
        ("flags", "expected"),
        [
            (["--min-year", "2025", "--max-year", "2023"], "--min-year (2025)"),
            (["--max-year", "2200"], "--max-year musi byc"),
            (["--year", "2200"], "--year musi byc"),
        ],
    )
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_year_bounds_validated_before_network(
        self, mock_manager, flags, expected, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                *flags,
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert expected in err and ("2200" in err or "2023" in err)
        mock_manager.assert_not_called()

    @pytest.mark.parametrize("product", ["nmt", "nmpt", "orto"])
    @pytest.mark.parametrize("mode", ["sheet", "bbox"])
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_year_passed_to_manager_for_nmt_nmpt_orto(
        self, mock_manager_class, mock_find, product, mode, tmp_path
    ):
        path = tmp_path / "N-34-130-D-d-2-4.asc"
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_class.return_value = (
            _mock_manager(path) if mode == "sheet" else _sheet_list_manager(path)
        )
        location = ["--sheet", "N-34-130-D-d-2-4"] if mode == "sheet" else _PL_BBOX_2180
        if product == "orto":
            group = ["imagery", "download", "--country", "auto"]
        else:
            group = ["elevation", "download", "--country", "auto"]
            group += [
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
            ]
        rc = main(
            [*group, *location, "--product", product, "--year", "2025"]
            + ["-o", str(tmp_path), "-q"]
        )
        assert rc == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert (kwargs["min_year"], kwargs["max_year"], kwargs["all_campaigns"]) == (
            2025,
            2025,
            False,
        )

    @pytest.mark.parametrize(
        ("flags", "all_campaigns", "bounds"),
        [
            (["--min-year", "2024"], False, (2024, None)),
            (["--max-year", "2024"], False, (None, 2024)),
            (["--all-campaigns", "--max-year", "2024"], True, (None, 2024)),
            (["--all-campaigns", "--year", "2025"], True, (2025, 2025)),
        ],
    )
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_campaigns_independent_of_year_flags(
        self, mock_manager_class, flags, all_campaigns, bounds, tmp_path
    ):
        """Year flags set the bounds; the switch controls flight count."""
        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                *flags,
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert (kwargs["min_year"], kwargs["max_year"]) == bounds
        assert kwargs["all_campaigns"] is all_campaigns

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_reports_link_kept_outside_range(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        """U15: `Info:` names the sheet and the campaign the link still uses."""
        sheet = "N-34-130-D-d-2-4"
        mock_find.return_value = [sheet]
        manager = _sheet_list_manager(tmp_path / f"{sheet}.asc")
        manager.download_sheets.return_value.link_outside_range = {
            sheet: tmp_path / "versions" / "2025-10-21_84183_3fa91c2e" / f"{sheet}.asc"
        }
        mock_manager_class.return_value = manager
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_PL_BBOX_2180,
                "--max-year",
                "2022",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        (line,) = [ln for ln in err.splitlines() if ln.startswith(f"  {sheet}:")]
        assert "sciezka standardowa" in line and "2025-10-21_84183" in line
        assert "Info:" in err

    @patch("kartograf.download.data._create_provider_and_storage")
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_year_nmt_list_error_message_and_hints(
        self, mock_manager_class, mock_find, mock_factory, capsys, tmp_path
    ):
        from kartograf.cache import MetadataCache
        from kartograf.download.campaigns import year_range_error

        mock_factory.return_value = _mock_provider_and_storage(".asc")
        mock_find.return_value = [f"N-34-139-C-a-3-{number}" for number in range(1, 5)]
        mock_manager_class.return_value.download_sheets.side_effect = year_range_error(
            {
                "N-34-139-C-a-3-1": [2019, 2023, 2025],
                "N-34-139-C-a-3-3": [2019, 2025],
            },
            2024,
            2024,
            total=4,
        )
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_PL_BBOX_2180,
                "--year",
                "2024",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 1
        lines = capsys.readouterr().err.splitlines()
        assert lines[0].startswith("Error: brak danych z roku 2024 dla 2 z 4 arkuszy")
        assert lines[1] == ("  N-34-139-C-a-3-1: dostepne roczniki 2019, 2023, 2025")
        assert lines[2] == "  N-34-139-C-a-3-3: dostepne roczniki 2019, 2025"
        assert lines[3].startswith("Podpowiedz: ")
        assert "--min-year 2024" in lines[3] and "--max-year 2024" in lines[3]
        assert len(lines) == 4
        cache = mock_factory.call_args.kwargs["cache"]
        assert isinstance(cache, MetadataCache)
        assert cache._conn is None

    @pytest.mark.parametrize("mode", ["sheet", "bbox"])
    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_cli_year_info_better_coverage(
        self, mock_manager_class, mock_find, mode, capsys, tmp_path
    ):
        """A higher-coverage flight is reported for sheet and bbox modes."""

        sheet = "N-34-139-C-a-3-1"
        path = tmp_path / f"{sheet}.asc"
        sidecar = {
            "extra": {
                "campaign": {"id": "84183"},
                "flights": [
                    {
                        "id": "84183",
                        "date": "2025-10-21",
                        "full_sheet": False,
                        "coverage": 0.009,
                    },
                    {
                        "id": "83233",
                        "date": "2025-04-27",
                        "full_sheet": True,
                        "coverage": 0.998,
                    },
                ],
            },
        }
        (tmp_path / f"{sheet}.asc.meta.json").write_text(json.dumps(sidecar))
        mock_find.return_value = [sheet]
        if mode == "sheet":
            manager = _mock_manager(path)
            manager.download_sheet.return_value.better_coverage = {sheet: "83233"}
            location = ["--sheet", sheet]
        else:
            manager = _sheet_list_manager(path)
            manager.download_sheets.return_value.better_coverage = {sheet: "83233"}
            location = _PL_BBOX_2180
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *location,
                "--year",
                "2025",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "Info: dla 1 arkuszy starszy lot z przedzialu" in err
        assert f"{sheet}: dowiazanie 2025-10-21_84183" in err
        assert "niepelny, pokrycie 0,9 %" in err
        assert "wieksze pokrycie: 2025-04-27_83233 (pelny, pokrycie 99,8 %)" in err

    def test_cli_better_coverage_caps_details_at_ten(self, tmp_path):
        from kartograf.download.data import _better_coverage, _Run
        from kartograf.notices import NoticeSink

        coverage = {f"N-34-139-C-a-3-{n:02}": "83233" for n in range(12)}
        result = DownloadResult(better_coverage=coverage)
        run = _Run(NoticeSink(None), None, False, None, False, 1, None)
        _better_coverage(run, result, [tmp_path / f"{code}.asc" for code in coverage])

        (notice,) = run.sink.notices
        lines = notice.text.splitlines()
        assert "dla 12 arkuszy" in lines[0]
        assert len(lines) == 12
        assert "N-34-139-C-a-3-00" in lines[1]
        assert "N-34-139-C-a-3-09" in lines[10]
        assert lines[11] == "  ... i 2 innych"
        assert "N-34-139-C-a-3-10" not in "\n".join(lines)

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_cli_laz_superseded_suggests_all_year_flags(
        self, mock_provider_cls, capsys, tmp_path
    ):
        from kartograf.providers.pl.gugik_laz import SupersededLazTile

        tile = TestCmdDownloadLaz()._fake_tiles()[0]
        provider = mock_provider_cls.return_value
        provider.select_tiles.return_value = _selection(
            [], [SupersededLazTile(tile, ())]
        )
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 1
        assert "inny rocznik: --year/--min-year/--max-year" in capsys.readouterr().err

    @patch("kartograf.download.laz._run_laz_download")
    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_campaign_opts_forwarded(self, mock_provider_cls, mock_run, tmp_path):
        instance = Mock()
        instance.select_tiles.return_value = Mock(tiles=[Mock()], superseded=[])
        mock_provider_cls.return_value = instance
        mock_run.return_value = LazDownloadResult(tiles=())

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "laz",
                "--all-campaigns",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        kwargs = instance.select_tiles.call_args.kwargs
        assert kwargs["all_campaigns"] is True and kwargs["min_year"] == 2020
        kwargs = mock_run.call_args.kwargs
        assert kwargs["all_campaigns"] is True and kwargs["min_year"] == 2020

    @patch("kartograf.download.cutout.download_pl_cutout")
    def test_cutout_with_campaigns_all_rejected_before_network(
        self, mock_prepare, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_PL_BBOX_2180,
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --all-campaigns nie dziala z --cutout" in err
        # no promise of a campaign-composing tool in a given release (ADR-030
        # errata 6): the message ends with the reason
        assert "0.7.1" not in err
        assert "narzedzie" not in err
        mock_prepare.assert_not_called()

    @pytest.mark.parametrize("location", [_PL_BBOX_2180, _BORDER_BBOX])
    @pytest.mark.parametrize("flag", ["--year", "--min-year", "--max-year"])
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.cutout.download_pl_cutout")
    def test_cli_year_flags_rejected_with_cutout(
        self, mock_prepare, mock_run_cz, flag, location, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *location,
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                flag,
                "2020",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert f"Error: {flag} nie dziala z --cutout" in err
        assert "pobierz arkusze bez --cutout" in err
        mock_prepare.assert_not_called()
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.cutout.download_pl_cutout")
    @patch("kartograf.download.data._download_cz")
    def test_cutout_with_all_cross_border_rejected_before_cz(
        self, mock_run_cz, mock_prepare, capsys, tmp_path
    ):
        """Under auto CZ goes before PL — the guard must fire before CZ."""
        mock_run_cz.return_value = 0
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_BORDER_BBOX,
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "Error: --all-campaigns nie dziala z --cutout" in capsys.readouterr().err
        mock_run_cz.assert_not_called()
        mock_prepare.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_explicit_country_with_all_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--country",
                "cz",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_auto_with_all_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sheet_auto_with_min_year_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_cz_sm5_sheet_auto_with_all_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=5m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "CTES96",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @pytest.mark.parametrize("sheet", ["CTES96", "302_5550"])
    @patch("kartograf.download.data._download_cz")
    def test_cli_year_cz_sheet_rejected(self, mock_run_cz, sheet, capsys, tmp_path):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                sheet,
                "--year",
                "2023",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_area_explicit_cz_with_all_error(self, mock_run_cz, capsys, tmp_path):
        mock_run_cz.return_value = 0
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--bbox",
                "18.4,49.55,18.8,49.75",
                "--bbox-crs",
                "EPSG:4326",
                "--country",
                "cz",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data.cz_geometry_bbox")
    @patch("kartograf.download.data._download_cz")
    def test_geometry_explicit_cz_with_min_year_error(
        self, mock_run_cz, mock_cz_bbox, tmp_path, capsys
    ):
        gpkg = tmp_path / "area.gpkg"
        gpkg.write_bytes(b"stub")
        mock_cz_bbox.return_value = BBox(
            -447000.0, -1114000.0, -446000.0, -1113000.0, "EPSG:5514"
        )
        mock_run_cz.return_value = 0
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(gpkg),
                "--country",
                "cz",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path / "out"),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_area_auto_entirely_cz_with_all_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        mock_run_cz.return_value = 0
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_CZ_ONLY_BBOX,
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_area_auto_entirely_cz_with_min_year_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        mock_run_cz.return_value = 0
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_CZ_ONLY_BBOX,
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @pytest.mark.parametrize(
        "campaign",
        [["--all-campaigns"], ["--year", "2023"], ["--full-sheet"]],
        ids=["all", "year", "full-sheet"],
    )
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.data.DownloadManager")
    def test_area_auto_cross_border_with_campaign_options_needs_country_pl(
        self, mock_manager_class, mock_cz, campaign, capsys, tmp_path
    ):
        """ADR-038 D3: a border area is a cutout and a cutout has no campaigns -
        the error names --country pl (PL sheets with campaigns) before any
        download."""
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_BORDER_BBOX,
                *campaign,
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: obszar siega CZ") and "--country pl" in err
        assert "Info:" not in err
        mock_manager_class.assert_not_called()
        mock_cz.assert_not_called()

    @staticmethod
    def _single(tmp_path):
        return main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
            ]
        )

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_local_version_with_newer_campaign(
        self, mock_manager_class, capsys, tmp_path
    ):
        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.download_sheet.return_value = DownloadResult(
            skipped=["N-34-130-D-d-2-4"],
            files={
                "N-34-130-D-d-2-4": (
                    _version(
                        path,
                        "2025-04-27_83233_0a1b2c3d",
                        "local",
                        newer="2025-10-21_84183",
                    ),
                )
            },
        )
        manager.download_sheet.return_value.newer = {
            "N-34-130-D-d-2-4": "2025-10-21_84183"
        }
        _return_with_notices(
            mock_manager_class,
            manager,
            "download_sheet",
            manager.download_sheet.return_value,
            Notice(
                "info",
                "newer_available",
                "dostepna nowsza kampania dla 1 arkuszy (N-34-130-D-d-2-4) - "
                "uzyto lokalnych wersji; pobierz: --upgrade",
            ),
        )
        mock_manager_class.return_value = manager

        assert self._single(tmp_path) == 0
        captured = capsys.readouterr()
        assert (
            "N-34-130-D-d-2-4: lokalna wersja 2025-04-27_83233; dostepna nowsza "
            "2025-10-21_84183 (--upgrade)"
        ) in captured.out
        assert "Info: dostepna nowsza kampania dla 1 arkuszy" in captured.err

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_new_version_line(self, mock_manager_class, capsys, tmp_path):
        target = tmp_path / "N-34-130-D-d-2-4.asc"
        manager = _mock_manager(target)
        manager.download_sheet.return_value = DownloadResult(
            succeeded=[target],
            files={
                "N-34-130-D-d-2-4": (_version(target, "2025-10-21_84183_0a1b2c3d"),)
            },
        )
        mock_manager_class.return_value = manager

        assert self._single(tmp_path) == 0
        out = capsys.readouterr().out
        assert "N-34-130-D-d-2-4: nowa wersja 2025-10-21_84183_0a1b2c3d" in out

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_all_list_status_line_per_file_and_counters(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        mock_find.return_value = ["A", "B", "C"]
        a, b, c = (tmp_path / f"{n}.asc" for n in "abc")
        manager = _sheet_list_manager(a, b, c)
        manager.download_sheets.return_value.files = {
            "A": (
                _version(a, "2025-10-21_84183_0a1b2c3d"),
                _version(a, "2023-09-05_78047_1a1b2c3d", "local"),
            ),
            "B": (
                _version(
                    b,
                    "2025-10-21_84190_2a1b2c3d",
                    "relabeled",
                    same_as="2023-09-05_78047",
                ),
            ),
            "C": (
                _version(c, "2025-10-21_84191_3a1b2c3d", "unchanged"),
                _version(c, "2019-04-18_73021_4a1b2c3d", "local"),
            ),
        }
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_PL_BBOX_2180,
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "A: nowa wersja 2025-10-21_84183_0a1b2c3d" in out
        assert "A: lokalna wersja 2023-09-05_78047" in out
        assert (
            "B: nowa etykieta 2025-10-21_84190 (plik identyczny z 2023-09-05_78047)"
            in out
        )
        assert "C: bez zmian 2025-10-21_84191" in out
        assert (
            "Nowe: 1, nowa etykieta: 1, bez zmian: 1, lokalne: 2, bledy: 0 "
            f"({tmp_path})"
        ) in out

    @patch("kartograf.download.cutout.download_pl_cutout")
    @patch("kartograf.download.data._download_cz")
    def test_cutout_with_all_cross_border_no_info_before_error(
        self, mock_run_cz, mock_prepare, capsys, tmp_path
    ):
        """Fix 2: the --cutout guard comes before the campaign Info."""
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_BORDER_BBOX,
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --all-campaigns nie dziala z --cutout" in err
        assert "Info:" not in err

    @patch("kartograf.download.data.DownloadManager")
    def test_pl_sheet_cutout_with_all_gets_sheet_error(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Fix 3: the more general sheet code guard (--cutout with a code) wins."""
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--all-campaigns",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --cutout dziala tylko z --bbox/--geometry" in err
        assert "--all-campaigns nie dziala" not in err
        mock_manager_class.assert_not_called()

    @patch("kartograf.download.data.DownloadManager")
    def test_min_year_error_names_cli_flag(self, mock_manager_class, capsys, tmp_path):
        """Fix 4: the CLI says --min-year, not min_year (a library parameter)."""
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--min-year",
                "1800",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --min-year musi byc" in err and "1800" in err
        assert " min_year" not in err

    @patch("kartograf.download.data.DownloadManager")
    def test_campaigns_passed_to_manager_hierarchy(self, mock_manager_class, tmp_path):
        """Fix 5: the hierarchy path (--scale)."""
        manager = Mock()
        manager.download_hierarchy.return_value = DownloadResult(
            succeeded=[tmp_path / "a.asc"]
        )
        manager.count_sheets.return_value = 1
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "7.171.21",
                "--scale",
                "1:2000",
                "--all-campaigns",
                "--min-year",
                "2021",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        manager.download_hierarchy.assert_called_once()
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["all_campaigns"] is True and kwargs["min_year"] == 2021

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.download.data.DownloadManager")
    def test_campaigns_passed_to_manager_geometry_list(
        self, mock_manager_class, mock_find, mock_overall, mock_read_crs, tmp_path
    ):
        """Fix 5: the list path with PL --geometry."""
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(
            530000.0, 382000.0, 533000.0, 386000.0, "EPSG:2180"
        )
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")

        rc = main(
            [
                "elevation",
                "download",
                "--sheet-system",
                "1992",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--geometry",
                str(geometry_file),
                "--country",
                "pl",
                "--all-campaigns",
                "--min-year",
                "2022",
                "-o",
                str(tmp_path / "out"),
                "-q",
            ]
        )
        assert rc == 0
        mock_find.assert_called_once()
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["all_campaigns"] is True and kwargs["min_year"] == 2022

    @patch("kartograf.download.data.DownloadManager")
    def test_newest_min_year_single_sheet_no_coverage_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.exceptions import NoCoverageError

        manager = _mock_manager(None)
        manager.download_sheet.side_effect = NoCoverageError(
            "N-34-130-D-d-2-4: najnowsza kampania 2019-05-21 starsza niz "
            "--min-year 2024",
            sheet="N-34-130-D-d-2-4",
        )
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--min-year",
                "2024",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error:" in err and "2019-05-21" in err

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_format_error_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        manager = _mock_manager(None)
        manager.download_sheet.side_effect = DownloadError(
            "N-34-130-D-d-2-4: nie pobrano 1 z 1 kampanii (2020-01-01_123: "
            "format 'X' nieobslugiwany)"
        )
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error:" in err and "format 'X' nieobslugiwany" in err

    @patch("kartograf.download.data.DownloadManager")
    def test_namespace_without_new_attrs_defaults(self, mock_manager_class, tmp_path):
        from kartograf.cli.download_cmd import cmd_download

        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")
        args = argparse.Namespace(
            sheet="N-34-130-D-d-2-4",
            bbox=None,
            output=str(tmp_path),
            force=False,
            quiet=True,
            scale=None,
            vertical_crs="EVRF2007",
            resolution="1m",
            product="nmt",
            country=None,
            cutout=False,
            horizontal_crs=None,
            sheet_system=None,
        )
        assert cmd_download(args) == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["all_campaigns"] is False
        assert kwargs["min_year"] is None

    # -------------------------------------------------------------------------
    # I-1: newest on an index failure -> local campaign + Warning
    # -------------------------------------------------------------------------

    @patch("kartograf.download.data.DownloadManager")
    def test_unverified_local_campaign_warns_single_sheet(
        self, mock_manager_class, capsys, tmp_path
    ):
        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.download_sheet.return_value = DownloadResult(
            skipped=["N-34-130-D-d-2-4"],
            files={
                "N-34-130-D-d-2-4": (
                    _version(
                        path,
                        status="local",
                        unverified=(
                            "check_failed: pobranie nieudane po 3 probach: HTTP 503"
                        ),
                    ),
                )
            },
        )
        _return_with_notices(
            mock_manager_class,
            manager,
            "download_sheet",
            manager.download_sheet.return_value,
            Notice(
                "warning",
                "unverified_local",
                "N-34-130-D-d-2-4: skorowidz GUGiK niedostepny - uzyto "
                "lokalnej wersji bez sprawdzenia nowszej "
                "(pobranie nieudane po 3 probach: HTTP 503)",
            ),
        )
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: N-34-130-D-d-2-4: skorowidz GUGiK niedostepny - uzyto "
            "lokalnej wersji bez sprawdzenia nowszej "
            "(pobranie nieudane po 3 probach: HTTP 503)"
        ) in err
        assert err.count("Warning:") == 1

    @patch("kartograf.download.data.DownloadManager")
    def test_verified_single_sheet_has_no_unverified_warning(
        self, mock_manager_class, capsys, tmp_path
    ):
        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.download_sheet.return_value = DownloadResult(
            skipped=["N-34-130-D-d-2-4"],
            files={"N-34-130-D-d-2-4": (_version(path, status="local"),)},
        )
        mock_manager_class.return_value = manager

        assert (
            main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "N-34-130-D-d-2-4",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )
            == 0
        )
        assert "skorowidz GUGiK niedostepny" not in capsys.readouterr().err

    @patch("kartograf.download.data.find_sheets_for_bbox")
    @patch("kartograf.download.data.DownloadManager")
    def test_unverified_local_campaign_warns_in_list_mode(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        sheets = ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
        mock_find.return_value = sheets
        manager = _sheet_list_manager(
            tmp_path / "a.asc", tmp_path / "b.asc", skipped=sheets
        )
        manager.download_sheets.return_value.succeeded = []
        manager.download_sheets.return_value.files = {
            g: (
                _version(
                    tmp_path / f"{g}.asc",
                    status="local",
                    unverified="check_failed: HTTP 503",
                ),
            )
            for g in sheets
        }
        _return_with_notices(
            mock_manager_class,
            manager,
            "download_sheets",
            manager.download_sheets.return_value,
            Notice(
                "warning",
                "unverified_local",
                "skorowidz GUGiK niedostepny - dla 2 arkuszy uzyto lokalnych "
                "wersji bez sprawdzenia nowszej "
                "(N-34-130-D-d-2-4, N-34-130-D-d-2-3) (HTTP 503)",
            ),
        )
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_PL_BBOX_2180,
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: skorowidz GUGiK niedostepny - dla 2 arkuszy uzyto lokalnych "
            "wersji bez sprawdzenia nowszej (N-34-130-D-d-2-4, N-34-130-D-d-2-3) "
            "(HTTP 503)"
        ) in err
        assert err.count("Warning:") == 1

    def test_unverified_end_to_end_with_real_manager(self, capsys, tmp_path):
        """A real ``DownloadManager`` + a campaign provider without network: the second
        run on an index failure = exit code 0 and ``Warning:`` despite ``-q``."""
        from tests.test_manager_campaigns import C14, FakeCampaignProvider

        fake = FakeCampaignProvider(C14)
        sheet = "N-34-139-C-a-3-1"
        out = tmp_path / "out"
        argv = [
            "elevation",
            "download",
            "--product",
            "nmt",
            "-o",
            "./data",
            "--country",
            "auto",
            "--resolution",
            "pl=1m,cz=2m",
            "--vertical-crs",
            "pl=EVRF2007,cz=Bpv",
            "--sheet",
            sheet,
            "-o",
            str(out),
            "-q",
        ]
        with patch(
            "kartograf.download.data._create_provider_and_storage",
            return_value=(fake, None),
        ):
            assert main(argv) == 0
            fake.resolve_error = DownloadError(
                "WFS GetFeature 9 typow SkorowidzNMT (strona 1): pobranie "
                "nieudane po 3 probach - wynik bylby niepelny",
                status_code=503,
            )
            capsys.readouterr()
            assert main(argv) == 0
            err = capsys.readouterr().err
            assert f"Warning: {sheet}: skorowidz GUGiK niedostepny" in err
            assert err.count(f"Warning: {sheet}: skorowidz GUGiK niedostepny") == 1

            fake.resolve_error = DownloadError("raport wyjatku OGC")
            assert main(argv) == 1
            assert "Error:" in capsys.readouterr().err

    # -------------------------------------------------------------------------
    # M-1: single sheet code with --all-campaigns — summary line as for a list
    # -------------------------------------------------------------------------


class TestListMessagesUx:
    """O-3 / O-6 / O-7: CLI messages on no data, skip and download."""

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_skip_has_no_downloading_line(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-3: a local version is not preceded by 'Pobieranie ...'."""
        path = tmp_path / "a.asc"
        manager = _mock_manager(path)  # the mock does not call on_download (skip)
        manager.download_sheet.return_value = DownloadResult(
            skipped=["N-34-130-D-d-2-4"],
            files={
                "N-34-130-D-d-2-4": (
                    _version(path, "2025-04-27_83233_0a1b2c3d", "local"),
                )
            },
        )
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
            ]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "N-34-130-D-d-2-4: lokalna wersja 2025-04-27_83233" in out
        assert "Pobieranie" not in out

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_error_has_no_downloading_line(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-3: Error (no record) is not preceded by 'Pobieranie ...'."""
        manager = _mock_manager(tmp_path / "a.asc")
        manager.download_sheet.side_effect = DownloadError("brak")
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "-o",
                str(tmp_path),
            ]
        )

        assert rc == 1
        captured = capsys.readouterr()
        assert "Error: brak" in captured.err
        assert "Pobieranie" not in captured.out

    @staticmethod
    def _list_manager(result):
        manager = Mock()
        manager.download_sheets.return_value = result
        manager.download_sheet.return_value = result
        return manager

    @staticmethod
    def _real_error(sheet):
        """A real index ``no_coverage_error`` (PL-2000 descendant)."""
        from kartograf.providers.pl.skorowidz import (
            SkorowidzRecord,
            coverage_hints,
            no_coverage_error,
        )

        parser = SheetParser(sheet)
        child = SkorowidzRecord(
            url="https://example.invalid/x.asc",
            sheet=f"{sheet}.01",
            aktualnosc="2024-01-01",
            dt_pzgik=None,
            layer="L",
            system="2000",
            zone=7,
            resolution_m=1.0,
            full_sheet=True,
            raw={},
        )
        return no_coverage_error(
            parser, f"Brak NMT dla {sheet}", coverage_hints(parser, [child])
        )

    _BBOX_ARGS = (
        "elevation",
        "download",
        "--product",
        "nmt",
        "--resolution",
        "1m",
        "--vertical-crs",
        "EVRF2007",
        "--bbox",
        "419000,230000,426000,237000",
        "--sheet-system",
        "2000",
        "--scale",
        "1:5000",
        "--country",
        "pl",
    )

    @patch("kartograf.download.data.DownloadManager")
    def test_all_no_coverage_list_prints_real_hints(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-6/O-7: real `hints` -> `Info:` per sheet code; no 'Downloaded 0'."""
        errors = {g: self._real_error(g) for g in ("7.173.21", "7.173.22")}
        result = DownloadResult(
            failed=list(errors),
            no_coverage=list(errors),
            no_coverage_hints={g: e.hints for g, e in errors.items()},
        )
        mock_manager_class.return_value = self._list_manager(result)

        rc = main([*self._BBOX_ARGS, "-o", str(tmp_path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "nie ma danych dla zadnego z 2 arkuszy" in captured.err
        info = [x for x in captured.err.splitlines() if x.startswith("Info:")]
        assert info == [
            "Info: Dostepny potomek 7.173.21.01 - uzyj --scale 1:2000",
            "Info: Dostepny potomek 7.173.22.01 - uzyj --scale 1:2000",
        ]
        assert "Downloaded 0" not in captured.out

    @staticmethod
    def _info_lines(hints_by_sheet, capsys, tmp_path):
        result = DownloadResult(
            failed=list(hints_by_sheet),
            no_coverage=list(hints_by_sheet),
            no_coverage_hints=hints_by_sheet,
        )
        with patch("kartograf.download.data.DownloadManager") as cls:
            cls.return_value = TestListMessagesUx._list_manager(result)
            main([*TestListMessagesUx._BBOX_ARGS, "-o", str(tmp_path)])
        err = capsys.readouterr().err
        return [x for x in err.splitlines() if x.startswith("Info:")]

    def test_pl1992_hints_with_different_sheet_are_all_kept(self, capsys, tmp_path):
        """Different sheet codes in hints (PL-1992) are not merged into one."""
        h = "Skorowidz ma ten obszar w PL-1992: {g} (1:10000) - uzyj tego godla"
        lines = self._info_lines(
            {
                "S1": (h.format(g="M-34-63-A-c-2-1"),),
                "S2": (h.format(g="M-34-63-A-c-2-2"),),
            },
            capsys,
            tmp_path,
        )
        assert lines == [
            "Info: " + h.format(g="M-34-63-A-c-2-1"),
            "Info: " + h.format(g="M-34-63-A-c-2-2"),
        ]

    def test_literal_duplicate_hint_printed_once(self, capsys, tmp_path):
        lines = self._info_lines(
            {"S1": ("rada A",), "S2": ("rada A",)}, capsys, tmp_path
        )
        assert lines == ["Info: rada A"]

    def test_seven_hints_capped_at_five_plus_summary(self, capsys, tmp_path):
        hints = {f"S{i}": (f"rada {i}",) for i in range(7)}
        lines = self._info_lines(hints, capsys, tmp_path)
        assert lines[:5] == [f"Info: rada {i}" for i in range(5)]
        assert len(lines) == 6
        assert "i 2 innych podpowiedzi" in lines[5]
        assert "no_coverage_hints" in lines[5]

    @patch("kartograf.download.data.DownloadManager")
    def test_message_with_dot_but_no_hints_prints_no_info(
        self, mock_manager_class, capsys, tmp_path
    ):
        """A message with ". " without `hints` gives no false hint."""
        result = DownloadResult(failed=["A"], no_coverage=["A"])
        mock_manager_class.return_value = self._list_manager(result)

        rc = main([*self._BBOX_ARGS, "-o", str(tmp_path)])

        assert rc == 1
        assert "Info:" not in capsys.readouterr().err

    @pytest.mark.parametrize("all_campaigns", [False, True])
    @patch("kartograf.download.data.DownloadManager")
    def test_all_no_coverage_quiet_keeps_stderr_no_summary(
        self, mock_manager_class, all_campaigns, capsys, tmp_path
    ):
        """O-7 on both paths and with -q: Error/Info on stderr, no summary."""
        err = self._real_error("7.173.21")
        result = DownloadResult(
            failed=["7.173.21"],
            no_coverage=["7.173.21"],
            no_coverage_hints={"7.173.21": err.hints},
        )
        mock_manager_class.return_value = self._list_manager(result)

        flags = ["--all-campaigns"] if all_campaigns else []
        rc = main([*self._BBOX_ARGS, *flags, "-q", "-o", str(tmp_path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "nie ma danych dla zadnego z 1 arkuszy" in captured.err
        assert "Info: Dostepny potomek 7.173.21.01" in captured.err
        assert "Downloaded" not in captured.out

    @pytest.mark.parametrize("all_campaigns", [False, True])
    @patch("kartograf.download.data.DownloadManager")
    def test_all_no_coverage_not_quiet_no_summary(
        self, mock_manager_class, all_campaigns, capsys, tmp_path
    ):
        result = DownloadResult(failed=["A"], no_coverage=["A"])
        mock_manager_class.return_value = self._list_manager(result)

        flags = ["--all-campaigns"] if all_campaigns else []
        rc = main([*self._BBOX_ARGS, *flags, "-o", str(tmp_path)])

        assert rc == 1
        assert "Downloaded" not in capsys.readouterr().out

    @patch("kartograf.download.data.DownloadManager")
    def test_hierarchy_all_no_coverage_has_hint_and_no_summary(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-6/O-7 in the hierarchy: a hint, without a 0-files summary."""
        err = self._real_error("7.173.21")
        mock_manager_class.return_value = self._list_manager(
            DownloadResult(
                failed=["A"], no_coverage=["A"], no_coverage_hints={"A": err.hints}
            )
        )

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2",
                "-o",
                str(tmp_path),
            ]
        )

        assert rc == 1
        captured = capsys.readouterr()
        assert "uzyj --scale 1:2000" in captured.err
        assert "Downloaded 0" not in captured.out


class TestErrorWithoutBlankLine:
    """FB-1: no blank line before `Error:` when the progress bar is not running."""

    @patch("kartograf.download.data.DownloadManager")
    def test_single_sheet_error_starts_stderr(
        self, mock_manager_class, capsys, tmp_path
    ):
        manager = _mock_manager(tmp_path / "a.asc")
        manager.download_sheet.side_effect = DownloadError("brak kampanii od 2024")
        mock_manager_class.return_value = manager

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "7.125.11.19",
                "-o",
                str(tmp_path),
            ]
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: brak kampanii od 2024")

    def test_unfinished_progress_line_ends_before_status_lines(self, capsys):
        """A bar line left open (last unit ``skipped``: live 2026-10-15 the
        first status line was glued to it) gets its line end exactly once."""
        from kartograf.cli.download_cmd import _end_progress, create_progress_callback

        cb = create_progress_callback(False)
        cb(DownloadProgress(1, 2, "N-1", "completed", ""))
        cb(DownloadProgress(2, 2, "N-2", "skipped", ""))
        _end_progress(cb)
        _end_progress(cb)
        _end_progress(None)
        last = capsys.readouterr().out.split("\r")[-1]
        assert "o N-2" in last and last.endswith("\n") and last.count("\n") == 1


class TestSoilgridsHsgNoEarlyMkdir:
    """soil hsg does not leave an empty output directory after an error."""

    def test_missing_geometry_leaves_no_output_dir(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = main(
            [
                "soil",
                "hsg",
                "--geometry",
                "nieistniejacy.shp",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path / "out"),
            ]
        )
        assert result == 1
        assert "Error:" in capsys.readouterr().err
        assert not (tmp_path / "out").exists()

    @patch("kartograf.hydrology.HSGCalculator")
    def test_calculation_error_leaves_no_dir(
        self, mock_calc_cls, capsys, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_calc_cls.return_value.calculate_hsg.side_effect = DownloadError("siec")
        out = tmp_path / "out" / "hsg"
        result = main(
            [
                "soil",
                "hsg",
                "--sheet",
                "N-34-130-D",
                "-o",
                str(out),
                "--depth",
                "0-5cm",
            ]
        )
        assert result == 1
        assert not (tmp_path / "out").exists()


_LAZ_ONLY_DENSITY_ERROR = (
    "Error: --min-density dziala tylko z --product laz (podano {product}); pomin "
    "--min-density"
)
# Every download path rejects point density for non-LAZ products.
_LAZ_ONLY_PATHS = {
    "sheet": ["--sheet", "N-34-130-D-d-2-4"],
    "hierarchy": ["--sheet", "N-34-130-D"],
    "hierarchy_scale": ["--sheet", "N-34-130-D-d-2-4", "--scale", "1:10000"],
    "list_bbox": _PL_BBOX_2180,
    "geometry": ["--geometry", "area.gpkg"],
    "cutout": [*_PL_BBOX_2180, "--cutout", "--horizontal-crs", "EPSG:2180"],
    "auto_border": _BORDER_BBOX,
    "auto_cz_bbox": _CZ_ONLY_BBOX,
    "cz_sheet": ["--sheet", "302_5550"],
    "cz_forced": [*_CZ_ONLY_BBOX, "--country", "cz"],
}
# elevation products other than LAZ (imagery has no --min-density at all:
# TestCmdDownloadProduct.test_imagery_rejects_elevation_only_flags)
_LAZ_ONLY_PRODUCTS = ["nmt", "nmpt"]


class TestLazOnlyOptions:
    """``--min-density`` is only available for ``--product laz``."""

    @pytest.fixture
    def guards(self):
        """Everything that would reach the network or the disk."""
        with (
            patch("kartograf.download.data.DownloadManager") as manager,
            patch("kartograf.download.data._create_provider_and_storage") as factory,
            patch("kartograf.download.cutout.download_pl_cutout") as cutout,
            patch("kartograf.download.data._download_cz") as run_cz,
            patch("kartograf.download.data._download_cz") as cmd_cz,
            patch("kartograf.providers.pl.gugik_laz.GugikLazProvider") as laz,
        ):
            yield [manager, factory, cutout, run_cz, cmd_cz, laz]

    @pytest.mark.parametrize("path", sorted(_LAZ_ONLY_PATHS))
    @pytest.mark.parametrize("product", _LAZ_ONLY_PRODUCTS)
    def test_min_density_rejected_for_other_products(
        self, product, path, guards, capsys, tmp_path
    ):
        out = tmp_path / "out"
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *_LAZ_ONLY_PATHS[path],
                "--product",
                product,
                "--min-density",
                "12",
                "-o",
                str(out),
            ]
        )
        assert rc == 1
        assert capsys.readouterr().err == (
            _LAZ_ONLY_DENSITY_ERROR.format(product=product) + "\n"
        )
        for guard in guards:
            guard.assert_not_called()
        assert not out.exists()

    @pytest.mark.parametrize(
        ("flags", "bounds"),
        [
            (["--year", "2022"], (2022, 2022)),
            (["--max-year", "2022"], (None, 2022)),
            (["--year", "2022", "--all-campaigns"], (2022, 2022)),
        ],
    )
    @patch("kartograf.download.laz._run_laz_download")
    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_cli_laz_year_mapped_to_range(
        self, mock_provider_cls, mock_run, flags, bounds, tmp_path
    ):
        instance = Mock()
        instance.select_tiles.return_value = Mock(tiles=[Mock()], superseded=[])
        mock_provider_cls.return_value = instance
        mock_run.return_value = LazDownloadResult(tiles=())

        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--product",
                "laz",
                *flags,
                "--min-density",
                "12",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        for kwargs in (
            instance.select_tiles.call_args.kwargs,
            mock_run.call_args.kwargs,
        ):
            assert kwargs["min_year"] == bounds[0]
            assert kwargs["max_year"] == bounds[1]
            assert kwargs["all_campaigns"] is ("--all-campaigns" in flags)
            assert kwargs.get("year") is None
            assert kwargs["min_density"] == 12


class TestFullSheetOption:
    """ADR-033: ``--full-sheet``, its guards and the combined E13 ``Warning:``."""

    G = "N-34-139-C-a-3-1"  # newest 84183 partial, 83233 full

    @staticmethod
    def _run(fake, *argv):
        with patch(
            "kartograf.download.data._create_provider_and_storage",
            return_value=(fake, None),
        ):
            return main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    *argv,
                ]
            )

    @staticmethod
    def _partial_warning(err: str) -> str:
        (line,) = [ln for ln in err.splitlines() if "niepelna" in ln]
        assert line.startswith("Warning:")
        return line

    def test_parser_flag_default_off(self):
        assert (
            create_parser()
            .parse_args(["elevation", "download", "--sheet", "X"])
            .full_sheet
            is False
        )
        args = create_parser().parse_args(
            ["elevation", "download", "--sheet", "X", "--full-sheet"]
        )
        assert args.full_sheet is True

    @patch("kartograf.download.laz._run_laz_download")
    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_rejected_before_network(self, provider_cls, run, capsys, tmp_path):
        out = tmp_path / "out"
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                self.G,
                "--product",
                "laz",
                "--full-sheet",
                "-o",
                str(out),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:") and "--full-sheet" in err
        provider_cls.assert_not_called()
        run.assert_not_called()
        assert not out.exists()

    @pytest.mark.parametrize("location", [_PL_BBOX_2180, _BORDER_BBOX])
    @patch("kartograf.download.data._download_cz")
    @patch("kartograf.download.cutout.download_pl_cutout")
    def test_cutout_rejected_before_network(
        self, prepare, run_cz, location, capsys, tmp_path
    ):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *location,
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--full-sheet",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --full-sheet nie dziala z --cutout" in err
        prepare.assert_not_called()
        run_cz.assert_not_called()

    @patch("kartograf.download.data._download_cz")
    def test_cz_only_is_error(self, run_cz, capsys, tmp_path):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--sheet",
                "302_5550",
                "--full-sheet",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err and "Info:" not in err
        run_cz.assert_not_called()

    def test_flag_fetches_full_flight_and_warns_once(self, capsys, tmp_path):
        """F3 + F5: two campaign files, one Warning naming full_sheet/; a rerun
        skips without network and repeats the same Warning."""
        from tests.test_manager_campaigns import REC, c14_fake

        fake = c14_fake()
        out = str(tmp_path / "out")
        assert self._run(fake, "--sheet", self.G, "--full-sheet", "-o", out) == 0
        captured = capsys.readouterr()
        assert fake.downloads == [REC["84183"].url, REC["83233"].url]
        assert captured.out.count(f"{self.G}: nowa wersja ") == 2
        first = self._partial_warning(captured.err)
        assert self.G in first and "full_sheet/" in first
        assert "uzyj --full-sheet" not in first

        assert self._run(fake, "--sheet", self.G, "--full-sheet", "-o", out) == 0
        captured = capsys.readouterr()
        assert len(fake.downloads) == 2
        assert captured.out.count(f"{self.G}: lokalna wersja ") == 2
        assert self._partial_warning(captured.err) == first

    def test_without_flag_hints_full_sheet(self, capsys, tmp_path):
        """F2: the partial newest flight only; the Warning suggests the flag."""
        from tests.test_manager_campaigns import c14_fake

        fake = c14_fake()
        assert (
            self._run(fake, "--sheet", self.G, "-o", str(tmp_path / "out"), "-q") == 0
        )
        line = self._partial_warning(capsys.readouterr().err)
        assert self.G in line and "--full-sheet" in line
        assert len(fake.downloads) == 1

    def test_no_full_flight_in_index(self, capsys, tmp_path):
        """F7: the flag finds no full flight -> named in the Warning, code 0."""
        import dataclasses

        from tests.test_manager_campaigns import C14_ALL, FakeCampaignProvider

        records = [dataclasses.replace(r, full_sheet=False) for r in C14_ALL]
        fake = FakeCampaignProvider({"newest": records[:1], "all": records})
        out = str(tmp_path / "out")
        assert self._run(fake, "--sheet", self.G, "--full-sheet", "-o", out, "-q") == 0
        line = self._partial_warning(capsys.readouterr().err)
        assert "brak pelnego lotu w skorowidzu" in line and self.G in line
        assert "uzyj --full-sheet" not in line

    def test_full_link_outside_range_info(self, capsys, tmp_path):
        """F8: the full_sheet/ link stays on a newer full flight -> Info line."""
        from tests.test_manager_campaigns import c14_fake

        fake = c14_fake()
        out = str(tmp_path / "out")
        assert (
            self._run(fake, "--sheet", self.G, "--all-campaigns", "-o", out, "-q") == 0
        )
        capsys.readouterr()
        argv = [
            "--sheet",
            self.G,
            "--all-campaigns",
            "--max-year",
            "2024",
            "-o",
            out,
            "-q",
        ]
        assert self._run(fake, *argv) == 0
        err = capsys.readouterr().err
        assert "Info:" in err
        (line,) = [ln for ln in err.splitlines() if "full_sheet/ ->" in ln]
        assert self.G in line and "2025-04-27_83233" in line

    def test_hierarchy_warning_splits_linked_and_absent_sheets(self, capsys, tmp_path):
        """``--all-campaigns`` over a hierarchy: one Warning, two groups."""
        import dataclasses

        from tests.test_manager_campaigns import FakeCampaignProvider, c14_records

        g3 = "N-34-139-C-a-3-3"
        records = []
        for i in range(1, 5):
            sheet = f"N-34-139-C-a-3-{i}"
            for r in c14_records(sheet):
                no_full = sheet == g3
                records.append(
                    dataclasses.replace(r, full_sheet=False) if no_full else r
                )
        fake = FakeCampaignProvider({"all": records})
        out = str(tmp_path / "out")
        argv = ["--sheet", "N-34-139-C-a-3", "--all-campaigns", "-o", out, "-q"]
        assert self._run(fake, *argv) == 0
        line = self._partial_warning(capsys.readouterr().err)
        linked, absent = line.split("pelny lot w <segment>/full_sheet/: ")[1].split(
            "; brak pelnego lotu w skorowidzu: "
        )
        assert linked == self.G and absent == g3

    def test_ranged_absent_group_names_year_bounds(self, capsys, tmp_path):
        """A full flight outside the year bounds is not "missing in the index"."""
        import dataclasses

        from tests.test_manager_campaigns import C14_ALL, FakeCampaignProvider

        records = [
            dataclasses.replace(r, full_sheet=False) if r.aktualnosc < "2024" else r
            for r in C14_ALL
        ]
        fake = FakeCampaignProvider({"newest": records[:1], "all": records})
        out = str(tmp_path / "out")
        argv = [
            "--sheet",
            self.G,
            "--full-sheet",
            "--max-year",
            "2024",
            "-o",
            out,
            "-q",
        ]
        assert self._run(fake, *argv) == 0
        line = self._partial_warning(capsys.readouterr().err)
        assert (
            f"brak pelnego lotu w skorowidzu w zakresie lat zadania: {self.G}" in line
        )
