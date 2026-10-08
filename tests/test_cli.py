"""
Unit tests for CLI module.

This module contains tests for command-line interface commands,
verifying correct parsing and output formatting.
"""

import argparse
import json
import threading
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest  # noqa: F401 - required for fixtures
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
from kartograf.download.manager import DownloadProgress, DownloadResult
from kartograf.exceptions import DownloadError, ValidationError


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


def _sheet_list_manager(*paths, failed=(), no_coverage=(), skipped=()):
    """Sheet-list mode manager mock: ``download_sheets`` + ``last_result``.

    ``paths`` are the files returned from ``download_sheets`` (downloaded and
    skipped); ``failed``/``no_coverage``/``skipped`` land in ``last_result`` as
    in the real ``DownloadManager`` (``no_coverage`` is a subset of
    ``failed``).
    """
    manager = Mock()
    manager.last_result = None
    manager.download_sheets.return_value = list(paths)
    manager.last_result = DownloadResult(
        succeeded=list(paths),
        failed=[*failed, *no_coverage],
        skipped=list(skipped),
        no_coverage=list(no_coverage),
    )
    return manager


def _mock_manager(path):
    """Manager mock returning ``path`` and NO failures (``last_result=None``)."""
    manager = Mock()
    manager.last_result = None
    manager.download_sheet.return_value = path
    return manager


def _starting_download(path):
    """A fake ``download_sheet`` that calls ``on_download`` before downloading."""

    def fake(godlo, skip_existing=True, on_progress=None, on_download=None):
        if on_download is not None:
            on_download()
        return path

    return fake


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
        assert args.godlo == "N-34-130-D"

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
    """K7a: cli._parser.parse_bbox_arg — a single --bbox parser."""

    def test_valid_with_spaces(self):
        from kartograf.cli._parser import parse_bbox_arg

        bbox = parse_bbox_arg(" 1, 2 ,3,4", "EPSG:2180")
        assert tuple(bbox) == (1.0, 2.0, 3.0, 4.0, "EPSG:2180")

    def test_point_allowed(self):
        from kartograf.cli._parser import parse_bbox_arg

        assert parse_bbox_arg("5,5,5,5", "EPSG:4326").crs == "EPSG:4326"

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("1,2,3", "expected 4 comma-separated values, got 3"),
            ("1,2,3,4,", "expected 4 comma-separated values, got 5"),
            ("1;2;3;4", "got 1"),
            ("a,2,3,4", "'a' is not a number"),
            ("10,10,5,5", "min > max"),
            ("1,10,5,5", "min > max"),
            ("nan,1,2,3", "skonczone"),
            ("1,2,inf,4", "skonczone"),
        ],
    )
    def test_invalid(self, text, reason):
        from kartograf.cli._parser import parse_bbox_arg

        with pytest.raises(ValidationError) as exc:
            parse_bbox_arg(text, "EPSG:2180")
        msg = str(exc.value)
        assert msg.startswith("Invalid bbox format: ")
        assert reason in msg
        assert "Expected: min_x,min_y,max_x,max_y" in msg


class TestCreateParserGodloStrip:
    """K5: argparse does not strip whitespace - the sheet code (godlo) is stripped
    on input, before the system registry decides the country and before the
    file name is built."""

    @pytest.mark.parametrize("raw", [" 302_5550", "302_5550 ", "\t302_5550\n"])
    def test_download_godlo_stripped(self, raw):
        assert create_parser().parse_args(["download", raw]).godlo == "302_5550"

    def test_parse_godlo_stripped(self):
        assert create_parser().parse_args(["parse", " N-34 "]).godlo == "N-34"

    def test_download_without_godlo_still_none(self):
        args = create_parser().parse_args(["download", "--bbox", "1,2,3,4"])
        assert args.godlo is None


class TestFormatSheetInfo:
    """Tests for format_sheet_info()."""

    def test_format_1m_sheet(self):
        """Test formatting 1:1000000 sheet."""
        parser = SheetParser("N-34")
        output = format_sheet_info(parser)

        assert "N-34" in output
        assert "1:1000000" in output
        assert "1992" in output
        assert "Components:" in output

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

        assert "Hierarchy" in output
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

        assert "Children" in output
        assert "4 sheets" in output
        assert "N-34-130-D-a" in output
        assert "N-34-130-D-b" in output
        assert "N-34-130-D-c" in output
        assert "N-34-130-D-d" in output

    def test_format_children_10k_no_children(self):
        """Test formatting children of 1:10000 (no children)."""
        parser = SheetParser("N-34-130-D-d-2-4")
        output = format_children(parser)

        assert "no children" in output

    def test_format_children_500k(self):
        """Test formatting children of 1:500000 (36 sheets)."""
        parser = SheetParser("N-34-A")
        output = format_children(parser)

        assert "36 sheets" in output


class TestFormatDescendants:
    """Tests for format_descendants()."""

    def test_format_descendants_small(self):
        """Test formatting descendants (small count)."""
        parser = SheetParser("N-34-130-D-d-2")
        output = format_descendants(parser, "1:10000")

        assert "Descendants" in output
        assert "4 sheets" in output
        assert "N-34-130-D-d-2-1" in output
        assert "N-34-130-D-d-2-4" in output

    def test_format_descendants_large(self):
        """Test formatting descendants (large count, truncated)."""
        parser = SheetParser("N-34-130-D")
        output = format_descendants(parser, "1:10000")

        assert "64 sheets" in output
        assert "..." in output


class TestCmdParse:
    """Tests for cmd_parse command."""

    def test_parse_valid_godlo(self, capsys):
        """Test parsing valid godlo."""
        result = main(["parse", "N-34-130-D"])

        assert result == 0
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "1:100000" in captured.out

    def test_parse_invalid_godlo(self, capsys):
        """Test parsing invalid godlo."""
        result = main(["parse", "INVALID"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_parse_with_hierarchy(self, capsys):
        """Test parsing with --hierarchy flag."""
        result = main(["parse", "N-34-130-D", "--hierarchy"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Hierarchy" in captured.out
        assert "N-34" in captured.out

    def test_parse_with_children(self, capsys):
        """Test parsing with --children flag."""
        result = main(["parse", "N-34-130-D", "--children"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Children" in captured.out
        assert "N-34-130-D-a" in captured.out

    def test_parse_with_descendants(self, capsys):
        """Test parsing with --descendants option."""
        result = main(["parse", "N-34-130-D-d-2", "--descendants", "1:10000"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Descendants" in captured.out
        assert "4 sheets" in captured.out

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

    def test_top_level_help_mentions_cuzk_and_soilgrids(self, capsys):
        """--help texts describe CZ/CUZK, SoilGrids and the hydrography layers."""
        with pytest.raises(SystemExit):
            main(["--help"])
        captured = capsys.readouterr()
        assert "CUZK" in captured.out

        with pytest.raises(SystemExit):
            main(["landcover", "download", "--help"])
        captured = capsys.readouterr()
        assert "SoilGrids" in captured.out

        result = main(["landcover", "list-sources"])
        assert result == 0
        captured = capsys.readouterr()
        assert "SW" in captured.out


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
        assert "Hierarchy" in captured.out
        # Should show no children message
        assert "no children" in captured.out

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

        for godlo, expected_scale in test_cases:
            result = main(["parse", godlo])
            assert result == 0, f"Failed for {godlo}"
            captured = capsys.readouterr()
            assert expected_scale in captured.out, f"Scale not found for {godlo}"


class TestCreateParserDownload:
    """Tests for download subparser."""

    def test_has_download_subcommand(self):
        """Test that download subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D"])
        assert args.command == "download"
        assert args.godlo == "N-34-130-D"

    def test_download_scale_option(self):
        """Test --scale option."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D", "--scale", "1:10000"])
        assert args.scale == "1:10000"

    def test_download_output_option(self):
        """Test --output option."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D", "-o", "/custom/path"])
        assert args.output == "/custom/path"

    def test_download_force_flag(self):
        """Test --force flag."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D", "--force"])
        assert args.force is True

    def test_download_quiet_flag(self):
        """Test --quiet flag."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D", "-q"])
        assert args.quiet is True

    def test_download_default_values(self):
        """Test default values for download options."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D"])
        assert args.output == "./data"
        assert args.force is False
        assert args.quiet is False
        assert args.scale is None


class TestCreateParserCountry:
    """Tests for --country/--target-crs and per-country sentinels on download."""

    def test_country_default_auto(self):
        args = create_parser().parse_args(["download", "X"])
        assert args.country == "auto"

    def test_country_choices(self):
        for value in ("pl", "cz", "auto"):
            args = create_parser().parse_args(["download", "X", "--country", value])
            assert args.country == value

    def test_country_invalid_rejected(self):
        with pytest.raises(SystemExit):
            create_parser().parse_args(["download", "X", "--country", "de"])

    def test_target_crs_default_none_and_choices(self):
        args = create_parser().parse_args(["download", "X"])
        assert args.target_crs is None
        for value in ("EPSG:2180", "EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(["download", "X", "--target-crs", value])
            assert args.target_crs == value
        with pytest.raises(SystemExit):
            create_parser().parse_args(["download", "X", "--target-crs", "EPSG:4326"])

    def test_sentinel_defaults(self):
        """--resolution/--vertical-crs/--system default to None (per country)."""
        args = create_parser().parse_args(["download", "X"])
        assert args.resolution is None
        assert args.vertical_crs is None
        assert args.system is None

    def test_new_choices_accepted(self):
        args = create_parser().parse_args(
            ["download", "X", "--resolution", "2m", "--vertical-crs", "Bpv"]
        )
        assert args.resolution == "2m"
        assert args.vertical_crs == "Bpv"

    def test_bbox_crs_extended_with_cz(self):
        for value in ("EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(
                ["download", "--bbox", "1,2,3,4", "--bbox-crs", value]
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
            current=1, total=4, godlo="N-34-130-D", status="downloading"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "1/4" in captured.out

    def test_callback_handles_completed_status(self, capsys):
        """Test callback for completed status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=4, total=4, godlo="N-34-130-D", status="completed"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "N-34-130-D" in captured.out
        assert "✓" in captured.out

    def test_callback_handles_skipped_status(self, capsys):
        """Test callback for skipped status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=2, total=4, godlo="N-34-130-D", status="skipped"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "○" in captured.out

    def test_callback_handles_failed_status(self, capsys):
        """Test callback for failed status."""
        callback = create_progress_callback(quiet=False)
        progress = DownloadProgress(
            current=3, total=4, godlo="N-34-130-D", status="failed"
        )
        callback(progress)
        captured = capsys.readouterr()
        assert "✗" in captured.out


class TestCmdDownload:
    """Tests for cmd_download command."""

    def test_download_invalid_godlo(self, capsys):
        """Test downloading with invalid godlo."""
        result = main(["download", "INVALID", "-q"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_single_sheet(self, mock_manager_class, capsys, tmp_path):
        """Test downloading a single sheet."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.tif"
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])

        assert result == 0
        mock_manager.download_sheet.assert_called_once_with(
            "N-34-130-D-d-2-4", skip_existing=True, on_progress=None, on_download=ANY
        )

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_hierarchy(self, mock_manager_class, capsys, tmp_path):
        """Test downloading a hierarchy."""
        paths = [tmp_path / f"test{i}.tif" for i in range(4)]
        mock_manager = Mock()
        mock_manager.count_sheets.return_value = 4
        mock_manager.download_hierarchy.return_value = paths
        mock_manager.last_result = DownloadResult(succeeded=paths)
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
                "N-34-130-D-d-2",
                "--scale",
                "1:10000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_hierarchy.assert_called_once()

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_with_force(self, mock_manager_class, tmp_path):
        """Test downloading with --force flag."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.tif"
        mock_manager_class.return_value = mock_manager

        result = main(
            ["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "--force", "-q"]
        )

        assert result == 0
        mock_manager.download_sheet.assert_called_once_with(
            "N-34-130-D-d-2-4", skip_existing=False, on_progress=None, on_download=ANY
        )

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_handles_error(self, mock_manager_class, capsys, tmp_path):
        """Test that download errors are handled."""
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError(
            "Network error", godlo="N-34-130-D"
        )
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D", "-o", str(tmp_path), "-q"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_invalid_scale(self, mock_manager_class, capsys, tmp_path):
        """Test downloading with invalid scale."""
        from kartograf.exceptions import ValidationError

        mock_manager = Mock()
        # count_sheets is only called when not quiet, so mock download_hierarchy
        mock_manager.download_hierarchy.side_effect = ValidationError("Invalid scale")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
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

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_shows_progress(self, mock_manager_class, capsys, tmp_path):
        """Test that download shows progress when not quiet."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.side_effect = _starting_download(
            tmp_path / "test.tif"
        )
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)])

        assert result == 0
        captured = capsys.readouterr()
        assert "Downloading" in captured.out
        assert "Downloaded to" in captured.out

    # --- hierarchy exit code (A2-3) ---

    @staticmethod
    def _hierarchy_manager(result: DownloadResult):
        """Code coarser than 1:10000: ``download_sheet`` -> list + ``last_result``."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = list(result.succeeded)
        mock_manager.count_sheets.return_value = result.total
        mock_manager.last_result = result
        return mock_manager

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_all_failed_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """100% download failures in the hierarchy: an error listing all sheets."""
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(succeeded=[], failed=["A", "B", "C", "D"], skipped=[])
        )

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 1
        err = capsys.readouterr().err
        assert "Error: 4 z 4 arkuszy nie pobrano" in err
        assert "A, B, C, D" in err and "ponow pobranie" in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_partial_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """A download failure (not missing data) ends with 1 despite partial success."""
        paths = [tmp_path / f"test{i}.asc" for i in range(3)]
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(succeeded=paths, failed=["A"], skipped=[])
        )

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 1
        assert "Error: 1 z 4 arkuszy nie pobrano" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_no_coverage_with_files_warns_and_returns_0(
        self, mock_manager_class, capsys, tmp_path
    ):
        """D10: sea sheets under a 1:50000 code = Warning + exit code 0 (as --bbox)."""
        paths = [tmp_path / f"test{i}.asc" for i in range(3)]
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(succeeded=paths, failed=["A"], no_coverage=["A"])
        )

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 0
        captured = capsys.readouterr()
        assert "Warning: GUGiK nie ma danych dla 1 z 4 arkuszy (A)" in captured.err
        assert "Error:" not in captured.err
        assert "Downloaded 3 files" in captured.out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_all_no_coverage_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """D10: zero files and all without data = exit code 1 (nothing to download)."""
        mock_manager_class.return_value = self._hierarchy_manager(
            DownloadResult(failed=["A", "B"], no_coverage=["A", "B"])
        )

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 1
        err = capsys.readouterr().err
        assert "Error: GUGiK nie ma danych dla zadnego z 2 arkuszy" in err
        assert "ponow pobranie" not in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_all_skipped_returns_exit_0(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Only skips (the files already exist) is still a success."""
        mock_manager = self._hierarchy_manager(
            DownloadResult(succeeded=[], failed=[], skipped=["A", "B", "C", "D"])
        )
        mock_manager.download_sheet.return_value = [tmp_path / "x.asc"] * 4
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert "Downloaded 0 files" in captured.out
        assert "4 already existed" in captured.out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_scale_mode_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """The same check applies on the --scale branch."""
        mock_manager = Mock()
        mock_manager.count_sheets.return_value = 4
        mock_manager.download_hierarchy.return_value = []
        mock_manager.last_result = DownloadResult(
            succeeded=[], failed=["A", "B", "C", "D"], skipped=[]
        )
        mock_manager_class.return_value = mock_manager

        result = main(
            ["download", "N-34-130-D-d-2", "--scale", "1:10000", "-o", str(tmp_path)]
        )

        assert result == 1
        assert "Error: 4 z 4 arkuszy nie pobrano" in capsys.readouterr().err


class TestDownloadCLIIntegration:
    """Integration tests for download CLI."""

    def test_download_help(self, capsys):
        """Test download --help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["download", "--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "download" in captured.out.lower()
        assert "--scale" in captured.out
        assert "--product" in captured.out  # Should show product option

    def test_main_includes_download(self, capsys):
        """Test that main help includes download command."""
        result = main([])

        assert result == 0
        captured = capsys.readouterr()
        assert "download" in captured.out


class TestCmdDownloadProduct:
    """Tests for --product flag in download command."""

    def test_download_parser_has_product_option(self):
        """Test that download parser has --product option."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D", "--product", "nmpt"])
        assert args.product == "nmpt"

    def test_download_product_default_nmt(self):
        """Test that --product defaults to nmt."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D"])
        assert args.product == "nmt"

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_product_nmpt(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --product nmpt creates GugikNmptProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
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

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_product_orto(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test --product orto creates GugikOrtoProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.tif"
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
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

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_product_nmt_default(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Test default product creates GugikProvider."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"
        mock_storage = Mock()
        mock_create.return_value = (mock_provider, mock_storage)

        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
        mock_manager_cls.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])

        assert result == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "nmt"

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
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

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
                "--bbox",
                "630000,480000,637000,487000",
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

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_orto_messages_do_not_claim_a_resolution(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Ortho has no resolution - the message must not say 'resolution: 1m'."""
        mock_create.return_value = _mock_provider_and_storage(".tif")
        manager = _mock_manager(tmp_path / "test.tif")
        manager.download_sheet.side_effect = _starting_download(tmp_path / "test.tif")
        mock_manager_cls.return_value = manager

        result = main(
            ["download", "N-34-130-D-d-2-4", "--product", "orto", "-o", str(tmp_path)]
        )

        assert result == 0
        out = capsys.readouterr().out
        assert "Downloading N-34-130-D-d-2-4 (product: orto)" in out
        assert "resolution" not in out

    # --- N6/E14: PL-path MetadataCache — --force = cache in refresh mode ---

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_force_passes_refresh_cache_to_provider_factory(
        self, mock_manager_cls, mock_create, tmp_path
    ):
        """E14: --force skips the cache read but writes the new record."""
        from kartograf.cache import MetadataCache

        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        rc = main(
            ["download", "N-34-130-D-d-2-4", "--force", "-o", str(tmp_path), "-q"]
        )

        assert rc == 0
        cache = mock_create.call_args.kwargs["cache"]
        assert isinstance(cache, MetadataCache)
        assert cache._refresh is True
        assert cache._conn is None  # closed after the task

    @pytest.mark.parametrize(
        "argv",
        [
            ["download", "N-34-130-D-d-2-4"],
            ["download", "--bbox", "630000,480000,637000,487000", "--country", "pl"],
        ],
        ids=["godlo", "bbox-list"],
    )
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox", return_value=["N-1"])
    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_without_force_opens_cache_in_cwd_and_closes_it(
        self, mock_manager_cls, mock_create, _mock_find, tmp_path, argv
    ):
        from kartograf.cache import MetadataCache

        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value.download_sheet.return_value = tmp_path / "t.asc"

        rc = main([*argv, "-o", str(tmp_path), "-q"])

        assert rc == 0
        cache = mock_create.call_args.kwargs["cache"]
        assert isinstance(cache, MetadataCache)
        assert cache._db_path.parent == Path.cwd()
        # closed after the task (CZ pattern): connection released
        assert cache._conn is None

    # --- product/resolution and product/vertical-crs pair validation (V2-N1) ---

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_nmpt_with_resolution_5m_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """NMPT 5m does not exist - the CLI rejects it instead of quietly using 1m."""
        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        result = main(
            [
                "download",
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
        assert "nmpt" in err
        assert "1m" in err
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_orto_with_vertical_crs_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """Orthophoto has no vertical CRS - the flag is an error, not a no-op."""
        mock_create.return_value = _mock_provider_and_storage(".tif")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.tif")

        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--product",
                "orto",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "orto" in err
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_orto_without_vertical_crs_still_works(
        self, mock_manager_cls, mock_create, tmp_path
    ):
        """Regression: ortho without --vertical-crs works as before."""
        mock_create.return_value = _mock_provider_and_storage(".tif")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.tif")

        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--product",
                "orto",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_bbox_nmpt_with_resolution_5m_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """The same validation applies in --bbox mode (PL sentinels)."""
        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        result = main(
            [
                "download",
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
        assert "nmpt" in err
        assert "1m" in err
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_bbox_orto_with_vertical_crs_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """The same validation applies in --bbox mode (PL sentinels)."""
        mock_create.return_value = _mock_provider_and_storage(".asc")
        mock_manager_cls.return_value = _mock_manager(tmp_path / "test.asc")

        result = main(
            [
                "download",
                "--bbox",
                "530000,382000,533000,386000",
                "--country",
                "pl",
                "--product",
                "orto",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "orto" in err
        mock_create.assert_not_called()
        mock_manager_cls.assert_not_called()


class TestCreateProviderAndStorage:
    """Tests for _create_provider_and_storage helper."""

    def test_nmt_creates_gugik_provider(self, tmp_path):
        """Test that nmt creates GugikProvider + FileStorage."""
        from kartograf.cli.download_cmd import _create_provider_and_storage
        from kartograf.providers.pl.gugik import GugikProvider

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikProvider)
        assert storage._resolution == "1m"
        assert storage._subdir == "nmt/pl_{uklad}_1m_evrf2007"

    def test_nmpt_creates_nmpt_provider(self, tmp_path):
        """Test that nmpt creates GugikNmptProvider."""
        from kartograf.cli.download_cmd import _create_provider_and_storage
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikNmptProvider)
        assert storage._subdir == "nmpt/pl_{uklad}_1m_evrf2007"

    def test_orto_creates_orto_provider(self, tmp_path):
        """Test that orto creates GugikOrtoProvider."""
        from kartograf.cli.download_cmd import _create_provider_and_storage
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider, storage = _create_provider_and_storage(
            "orto", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikOrtoProvider)
        assert storage._subdir == "orto/pl_{uklad}"

    def test_laz_product_raises_validation_error(self, tmp_path):
        """LAZ has a separate flow (_cmd_download_laz) - it must not get here."""
        from kartograf.cli.download_cmd import _create_provider_and_storage

        with pytest.raises(ValidationError, match="LAZ"):
            _create_provider_and_storage("laz", tmp_path, "EVRF2007", "1m")

    def test_unknown_product_raises_validation_error(self, tmp_path):
        """An unknown product must not silently fall through to the NMT factory."""
        from kartograf.cli.download_cmd import _create_provider_and_storage

        with pytest.raises(ValidationError, match="dmr5g"):
            _create_provider_and_storage("dmr5g", tmp_path, "EVRF2007", "1m")

    def test_nmt_kron86_storage_segment(self, tmp_path):
        from kartograf.cli.download_cmd import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_nmt_5m_kron86_storage_follows_provider_correction(self, tmp_path):
        """Factory corrects 5m=>EVRF2007 - the segment carries the fact, not a flag."""
        from kartograf.cli.download_cmd import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "5m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"

    def test_nmpt_storage_segment(self, tmp_path):
        from kartograf.cli.download_cmd import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmpt/pl_{uklad}_1m_kron86"


class TestCmdDownloadBBox:
    """Tests for download command with --bbox option."""

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_basic(self, mock_manager_class, capsys, tmp_path):
        """Test that --bbox calls find_sheets_for_bbox and download_sheet."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_manager.download_sheets.assert_called_once()

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_sheet_list_header(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        """D15: the sheet list header = the same as for a cutout (abbreviation >10)."""
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "t.asc")
        mock_find.return_value = [f"N-{i}" for i in range(1, 13)]
        result = main(
            ["download", "--bbox", "630000,480000,637000,487000", "-o", str(tmp_path)]
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "Found 12 sheets at 1:10000 for bbox (resolution: 1m)\n" in out
        assert "  Sheets: N-1, N-2, N-3, ..., N-11, N-12\n" in out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_epsg4326(self, mock_manager_class, capsys, tmp_path):
        """Test --bbox z --bbox-crs EPSG:4326."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
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

    def test_download_bbox_and_godlo_error(self, capsys):
        """Test oba godlo i --bbox → exit 1."""
        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--bbox",
                "419000,230000,426000,237000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Specify only one of" in captured.err

    def test_download_no_input_error(self, capsys):
        """Test no sheet code and no --bbox → exit 1."""
        result = main(["download", "-q"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Must specify" in captured.err

    def test_download_bbox_invalid_format(self, capsys):
        """Test of a bad bbox format → exit 1."""
        result = main(
            [
                "download",
                "--bbox",
                "not,a,valid,bbox",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid bbox format" in captured.err

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
            patch("kartograf.cli.download_cmd.DownloadManager") as manager,
            patch(_CZ_FACTORY_PATCH) as cz_factory,
            patch("kartograf.providers.pl.gugik_laz.GugikLazProvider") as laz,
        ):
            result = main(
                ["download", f"--bbox={bbox}", "-o", str(tmp_path), "-q", *extra]
            )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: Invalid bbox format" in captured.err
        assert "ValueError" not in captured.err
        assert "Expected" not in captured.out
        manager.assert_not_called()
        cz_factory.assert_not_called()
        laz.assert_not_called()

    def test_download_bbox_too_few_values(self, capsys):
        """Test of too few values in the bbox → exit 1."""
        result = main(
            [
                "download",
                "--bbox",
                "419000,230000,426000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid bbox format" in captured.err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_with_scale(self, mock_manager_class, capsys, tmp_path):
        """Test --bbox z --scale 1:100000."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "--scale",
                "1:100000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        # A smaller scale = fewer sheets
        mock_manager.download_sheets.assert_called_once()

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_shows_summary(self, mock_manager_class, capsys, tmp_path):
        """Test that bbox mode shows summary when not quiet."""
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
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
        assert "Found" in captured.out
        assert "sheets" in captured.out

    def test_download_parser_has_bbox_options(self):
        """Test that download parser has --bbox and --bbox-crs options."""
        parser = create_parser()
        args = parser.parse_args(
            [
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
                "download",
                "--bbox",
                "419000,230000,426000,237000",
            ]
        )
        assert args.bbox_crs == "EPSG:2180"

    def test_download_parser_godlo_optional(self):
        """Test that godlo is now optional."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "download",
                "--bbox",
                "419000,230000,426000,237000",
            ]
        )
        assert args.godlo is None
        assert args.bbox == "419000,230000,426000,237000"

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
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
            ["A", "B"], skip_existing=True, on_progress=ANY
        )
        # --workers reaches the manager, not the CLI loop
        assert mock_manager_cls.call_args.kwargs["max_workers"] == 1
        captured = capsys.readouterr()
        assert "Downloaded 3 files" in captured.out


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

    def download(self, godlo, path, timeout=30):
        from kartograf.exceptions import NoCoverageError

        with self._lock:
            self.calls.append(godlo)
        outcome = next(
            (v for suffix, v in self.outcomes.items() if godlo.endswith(suffix)),
            "ok",
        )
        if outcome == "no_coverage":
            raise NoCoverageError(f"No NMT 1m data available for {godlo}", godlo=godlo)
        if outcome == "fail":
            raise DownloadError(f"timeout {godlo}", godlo=godlo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
        return path


class TestSheetListExitCode:
    """S2/D2: sheet list mode (bbox/geometry without --target-crs) with R5 tolerance.

    A real ``DownloadManager`` + ``FileStorage`` in ``tmp_path``, a mock
    provider - contract tests (exit code, messages, number of tries), not the
    CLI loop.
    """

    _GODLA = [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]

    @staticmethod
    def _run_bbox(tmp_path, outcomes, *extra, godla=None):
        from kartograf.download.storage import FileStorage

        provider = _SheetProvider(outcomes)
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with (
            patch(
                "kartograf.cli.download_cmd._create_provider_and_storage",
                return_value=(provider, storage),
            ),
            patch(
                "kartograf.cli.download_cmd.find_sheets_for_bbox",
                return_value=list(godla or TestSheetListExitCode._GODLA),
            ),
        ):
            rc = main(
                [
                    "download",
                    "--bbox",
                    "630000,480000,637000,487000",
                    "-o",
                    str(tmp_path),
                    *extra,
                ]
            )
        files = sorted(p.name for p in tmp_path.rglob("*.asc"))
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
        assert sorted(provider.calls) == self._GODLA
        assert files == ["N-34-130-D-d-2-2.asc", "N-34-130-D-d-2-4.asc"]
        err = capsys.readouterr().err
        error_line = next(line for line in err.splitlines() if "Error:" in line)
        warning_line = next(line for line in err.splitlines() if "Warning:" in line)
        assert "N-34-130-D-d-2-3" in error_line and "ponow pobranie" in error_line
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
        assert "Downloaded 3 files" in captured.out

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

    def test_coarse_godlo_expands_in_manager(self, tmp_path, capsys):
        """The manager expands a coarser code; a leaf failure is in the summary."""
        rc, provider, files = self._run_bbox(
            tmp_path,
            {"-2-3": "fail"},
            "--scale",
            "1:25000",
            godla=["N-34-130-D-d-2"],
        )

        assert rc == 1
        assert sorted(provider.calls) == self._GODLA
        assert len(files) == 3
        err = capsys.readouterr().err
        assert "Error: 1 z 4 arkuszy nie pobrano" in err
        assert "N-34-130-D-d-2-3" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz", return_value=0)
    def test_auto_partial_no_coverage_with_cz_ok_has_no_false_warning(
        self, mock_cz, tmp_path, capsys
    ):
        """auto + CZ ok + PL partly without data -> code 0, no 'PL part ... error'."""
        from kartograf.download.storage import FileStorage

        provider = _SheetProvider({"-1": "no_coverage"})
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with (
            patch(
                "kartograf.cli.download_cmd._create_provider_and_storage",
                return_value=(provider, storage),
            ),
            patch(
                "kartograf.cli.download_cmd.find_sheets_for_bbox",
                return_value=list(self._GODLA),
            ),
        ):
            rc = main(
                [
                    "download",
                    "--bbox",
                    "18.4,49.55,18.8,49.75",
                    "--bbox-crs",
                    "EPSG:4326",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert rc == 0
        assert mock_cz.called
        err = capsys.readouterr().err
        assert "GUGiK nie ma danych dla 1 z 4 arkuszy" in err
        assert "zakonczyla sie bledem" not in err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_mode_uses_same_finish(
        self, mock_overall, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry without --target-crs: the same R5 tolerance as --bbox."""
        from kartograf.download.storage import FileStorage

        shp_file = tmp_path / "area.shp"
        shp_file.touch()
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw - deep inside PL, auto-split will not touch CZ
        mock_find.return_value = list(self._GODLA)
        provider = _SheetProvider({"-1": "no_coverage"})
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with patch(
            "kartograf.cli.download_cmd._create_provider_and_storage",
            return_value=(provider, storage),
        ):
            rc = main(["download", "--geometry", str(shp_file), "-o", str(tmp_path)])

        assert rc == 0
        assert len(provider.calls) == 4
        captured = capsys.readouterr()
        assert "Warning: GUGiK nie ma danych dla 1 z 4 arkuszy" in captured.err
        assert "Downloaded 3 files" in captured.out


class TestProgressNoCoverage:
    """D11: a sheet without data has its own progress bar icon."""

    def test_no_coverage_prints_empty_set_icon(self, capsys):
        on_progress = create_progress_callback(quiet=False)
        on_progress(
            DownloadProgress(
                current=1, total=2, godlo="N-1", status="no_coverage", message="sea"
            )
        )
        on_progress(DownloadProgress(current=2, total=2, godlo="N-2", status="failed"))
        out = capsys.readouterr().out
        assert "∅ N-1" in out and "✗ N-2" in out


# ===========================================================================
# Landcover CLI tests
# ===========================================================================


class TestCmdLandcoverDownload:
    """Tests for landcover download CLI."""

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_teryt(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --teryt calls manager.download with teryt."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.download.return_value = tmp_path / "out.gpkg"
        mock_mgr_cls.return_value = mock_mgr

        result = main(["landcover", "download", "--teryt", "1465", "-o", str(tmp_path)])
        assert result == 0
        mock_mgr.download.assert_called_once()
        call_kwargs = mock_mgr.download.call_args
        assert call_kwargs.kwargs.get("teryt") == "1465"

    def test_landcover_download_soilgrids_teryt_unsupported(self, capsys, tmp_path):
        """--source soilgrids --teryt -> exit 1, no data for a guessed area."""
        result = main(
            [
                "landcover",
                "download",
                "--source",
                "soilgrids",
                "--teryt",
                "1465",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: SoilGrids does not support TERYT" in captured.err

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_godlo(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --godlo calls manager.download with godlo."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.download.return_value = tmp_path / "out.gpkg"
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            ["landcover", "download", "--godlo", "N-34-130-D", "-o", str(tmp_path)]
        )
        assert result == 0
        mock_mgr.download.assert_called_once()
        call_kwargs = mock_mgr.download.call_args
        assert call_kwargs.kwargs.get("godlo") == "N-34-130-D"

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_by_bbox_success(self, mock_mgr_cls, capsys, tmp_path):
        """landcover download --bbox calls manager.download with bbox."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.download.return_value = tmp_path / "out.gpkg"
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--bbox",
                "450000,550000,460000,560000",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_mgr.download.assert_called_once()
        captured = capsys.readouterr()
        assert "Downloaded to" in captured.out

    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_download_source_corine(self, mock_mgr_cls, capsys, tmp_path):
        """--source corine creates manager with corine provider."""
        mock_mgr = Mock()
        mock_mgr.provider_name = "CORINE Land Cover"
        mock_mgr.download.return_value = tmp_path / "out.png"
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "corine",
                "--godlo",
                "N-34-130-D",
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

        result = main(["landcover", "download", "--teryt", "1465", "-o", str(tmp_path)])
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_landcover_download_multiple_selection(self, capsys):
        """Multiple selection methods -> exit 1."""
        result = main(
            ["landcover", "download", "--teryt", "1465", "--godlo", "N-34-130-D"]
        )
        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "only one of" in err.lower() or "Provide only one" in err

    def test_landcover_list_layers_soilgrids(self, capsys):
        """list-layers --source soilgrids shows soil properties."""
        result = main(["landcover", "list-layers", "--source", "soilgrids"])
        assert result == 0
        captured = capsys.readouterr()
        assert "clay" in captured.out
        assert "sand" in captured.out
        assert "silt" in captured.out

    def test_landcover_format_gml_rejected_by_argparse(self, capsys):
        """--format GML is not an implemented format; argparse rejects it."""
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    "--teryt",
                    "1465",
                    "--format",
                    "GML",
                ]
            )
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err

    def test_landcover_list_sources_does_not_advertise_gml(self, capsys):
        """list-sources must not advertise the unimplemented GML format."""
        result = main(["landcover", "list-sources"])
        assert result == 0
        captured = capsys.readouterr()
        assert "GML" not in captured.out


# ===========================================================================
# Soilgrids CLI tests
# ===========================================================================


class TestCmdSoilgrids:
    """Tests for soilgrids CLI commands."""

    def test_soilgrids_help(self, capsys):
        """soilgrids with no subcommand shows help."""
        result = main(["soilgrids"])
        assert result == 0
        captured = capsys.readouterr()
        assert "hsg" in captured.out

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_success(self, mock_calc_cls, capsys, tmp_path):
        """soilgrids hsg --godlo -> success output."""
        mock_calc = Mock()
        mock_calc.calculate_hsg_by_godlo.return_value = tmp_path / "hsg.tif"
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soilgrids",
                "hsg",
                "--godlo",
                "N-34-130-D",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "HSG raster saved to" in captured.out
        mock_calc.calculate_hsg_by_godlo.assert_called_once()

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_with_stats(self, mock_calc_cls, capsys, tmp_path):
        """soilgrids hsg --stats prints statistics."""
        mock_calc = Mock()
        mock_calc.calculate_hsg_by_godlo.return_value = tmp_path / "hsg.tif"
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
                "soilgrids",
                "hsg",
                "--godlo",
                "N-34-130-D",
                "-o",
                str(tmp_path),
                "--stats",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "HSG Statistics" in captured.out
        assert "Group A" in captured.out
        assert "50.0%" in captured.out

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_error(self, mock_calc_cls, capsys, tmp_path):
        """soilgrids hsg raises DownloadError -> exit 1."""
        mock_calc = Mock()
        mock_calc.calculate_hsg_by_godlo.side_effect = DownloadError("Network error")
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soilgrids",
                "hsg",
                "--godlo",
                "N-34-130-D",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_godlo_leading_zeros_canonical(self, mock_calc_cls, tmp_path):
        """A7: default HSG file name and the calculator use the canonical godlo."""
        mock_calc = mock_calc_cls.return_value
        mock_calc.calculate_hsg_by_godlo.return_value = tmp_path / "hsg.tif"
        out = tmp_path / "out"

        result = main(["soilgrids", "hsg", "--godlo", "M-33-036-A", "-o", str(out)])

        assert result == 0
        kwargs = mock_calc.calculate_hsg_by_godlo.call_args.kwargs
        assert kwargs["godlo"] == "M-33-36-A"
        assert kwargs["output_path"] == out / "hsg_M-33-36-A_0-5cm.tif"

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_out_of_range_godlo(self, mock_calc_cls, capsys, tmp_path):
        """A7: an out-of-range godlo -> Error on stderr, code 1, no calculation."""
        out = tmp_path / "out"

        result = main(["soilgrids", "hsg", "--godlo", "N-34-999-D", "-o", str(out)])

        assert result == 1
        mock_calc_cls.return_value.calculate_hsg_by_godlo.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: " in captured.err
        assert "poza zakresem" in captured.err

    @pytest.mark.parametrize(
        "bbox", ["invalid", "10,10,5,5", "nan,1,2,3", "1,2,-inf,4", "1,2,3"]
    )
    def test_soilgrids_hsg_rejects_bad_bbox(self, bbox, capsys, tmp_path):
        """K7a: bad --bbox -> Error on stderr, code 1, the calculator never starts."""
        with patch("kartograf.hydrology.HSGCalculator") as calc_cls:
            result = main(["soilgrids", "hsg", f"--bbox={bbox}", "-o", str(tmp_path)])
        assert result == 1
        calc_cls.return_value.calculate_hsg_by_bbox.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: Invalid bbox format" in captured.err
        assert "ValueError" not in captured.err
        assert "Expected" not in captured.out

    def test_soilgrids_hsg_no_selection(self, capsys):
        """soilgrids hsg without --godlo or --bbox -> exit 1."""
        result = main(["soilgrids", "hsg"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Must provide one of" in captured.err

    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_by_bbox(self, mock_calc_cls, capsys, tmp_path):
        """soilgrids hsg --bbox -> calculate_hsg_by_bbox called."""
        mock_calc = Mock()
        mock_calc.calculate_hsg_by_bbox.return_value = tmp_path / "hsg.tif"
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soilgrids",
                "hsg",
                "--bbox",
                "450000,550000,460000,560000",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 0
        mock_calc.calculate_hsg_by_bbox.assert_called_once()


class TestSoilgridsHsgOutputName:
    """Default HSG file names carry the depth, so depths do not overwrite."""

    @staticmethod
    def _run(args, tmp_path, method):
        with patch("kartograf.hydrology.HSGCalculator") as calc_cls:
            calc = calc_cls.return_value
            getattr(calc, method).return_value = tmp_path / "x.tif"
            assert main(["soilgrids", "hsg", *args, "-o", str(tmp_path)]) == 0
            return getattr(calc, method).call_args.kwargs["output_path"]

    def test_godlo_name_has_depth(self, tmp_path):
        a = self._run(
            ["--godlo", "N-34-130-D", "--depth", "0-5cm"],
            tmp_path,
            "calculate_hsg_by_godlo",
        )
        b = self._run(
            ["--godlo", "N-34-130-D", "--depth", "5-15cm"],
            tmp_path,
            "calculate_hsg_by_godlo",
        )
        assert a.name == "hsg_N-34-130-D_0-5cm.tif"
        assert b.name == "hsg_N-34-130-D_5-15cm.tif"

    def test_bbox_name_has_depth(self, tmp_path):
        path = self._run(
            ["--bbox", "450000,550000,460000,560000", "-d", "15-30cm"],
            tmp_path,
            "calculate_hsg_by_bbox",
        )
        assert path.name == "hsg_bbox_15-30cm.tif"


def test_landcover_download_no_selection(capsys):
    """No selection method -> exit 1."""
    result = main(["landcover", "download"])
    assert result == 1
    captured = capsys.readouterr()
    assert "Must provide one of" in captured.err


# ===========================================================================
# Geometry CLI tests — download command
# ===========================================================================


class TestCmdDownloadGeometry:
    """Tests for download command with --geometry option."""

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
            ["download", "--geometry", str(shp_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        mock_find.assert_called_once()
        mock_manager.download_sheets.assert_called_once()

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_with_layer(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry --layer passes layer parameter."""
        gpkg_file = tmp_path / "area.gpkg"
        gpkg_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw — deep inside PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
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

    def test_download_geometry_and_godlo_error(self, capsys, tmp_path):
        """--geometry + godlo -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--geometry",
                str(shp_file),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Specify only one of" in captured.err

    def test_download_geometry_and_bbox_error(self, capsys, tmp_path):
        """--geometry + --bbox -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "download",
                "--geometry",
                str(shp_file),
                "--bbox",
                "419000,230000,426000,237000",
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Specify only one of" in captured.err

    def test_download_geometry_file_not_found(self, capsys, tmp_path):
        """--geometry with nonexistent file -> error."""
        result = main(
            [
                "download",
                "--geometry",
                str(tmp_path / "nonexistent.shp"),
                "-q",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "File not found" in captured.err

    def test_download_no_input_error_updated(self, capsys):
        """No input at all shows updated error message."""
        result = main(["download", "-q"])

        assert result == 1
        captured = capsys.readouterr()
        assert "--geometry" in captured.err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
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
        assert "Downloaded 3 files" in captured.out


# ===========================================================================
# Geometry CLI tests — landcover download command
# ===========================================================================


class TestCmdLandcoverDownloadGeometry:
    """Tests for landcover download command with --geometry option."""

    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.cli.landcover_cmd.LandCoverManager")
    def test_landcover_geometry_basic(self, mock_mgr_cls, mock_bbox, capsys, tmp_path):
        """--geometry computes overall bbox and downloads."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_bbox.return_value = BBox(420000, 230000, 421000, 231000, "EPSG:2180")
        mock_mgr = Mock()
        mock_mgr.provider_name = "BDOT10k"
        mock_mgr.download.return_value = tmp_path / "out.gpkg"
        mock_mgr_cls.return_value = mock_mgr

        result = main(
            [
                "landcover",
                "download",
                "--geometry",
                str(shp_file),
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_bbox.assert_called_once()
        mock_mgr.download.assert_called_once()
        call_kwargs = mock_mgr.download.call_args
        assert call_kwargs.kwargs.get("bbox") is not None

    def test_landcover_geometry_and_teryt_error(self, capsys, tmp_path):
        """--geometry + --teryt -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "landcover",
                "download",
                "--geometry",
                str(shp_file),
                "--teryt",
                "1465",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "only one of" in err.lower() or "Provide only one" in err

    def test_landcover_geometry_file_not_found(self, capsys, tmp_path):
        """--geometry with nonexistent file -> error."""
        result = main(
            [
                "landcover",
                "download",
                "--geometry",
                str(tmp_path / "nonexistent.shp"),
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "File not found" in captured.err


# ===========================================================================
# Geometry CLI tests — soilgrids hsg command
# ===========================================================================


class TestCmdSoilgridsHsgGeometry:
    """Tests for soilgrids hsg command with --geometry option."""

    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.hydrology.HSGCalculator")
    def test_soilgrids_hsg_geometry(self, mock_calc_cls, mock_bbox, capsys, tmp_path):
        """--geometry computes bbox and calls calculate_hsg_by_bbox."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_bbox.return_value = BBox(420000, 230000, 421000, 231000, "EPSG:2180")
        mock_calc = Mock()
        mock_calc.calculate_hsg_by_bbox.return_value = tmp_path / "hsg.tif"
        mock_calc_cls.return_value = mock_calc

        result = main(
            [
                "soilgrids",
                "hsg",
                "--geometry",
                str(shp_file),
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_bbox.assert_called_once()
        mock_calc.calculate_hsg_by_bbox.assert_called_once()

    def test_soilgrids_hsg_geometry_and_godlo_error(self, capsys, tmp_path):
        """--geometry + --godlo -> mutual exclusivity error."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        result = main(
            [
                "soilgrids",
                "hsg",
                "--geometry",
                str(shp_file),
                "--godlo",
                "N-34-130-D",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        err = captured.err
        assert "only one of" in err.lower() or "Provide only one" in err


# ===========================================================================
# PL-2000 CLI tests
# ===========================================================================


class TestFormatSheetInfoPL2000:
    """Tests for format_sheet_info() with PL-2000 godla."""

    def test_format_pl2000_sheet_basic(self):
        """PL-2000 godlo shows correct layout and components."""
        parser = SheetParser("6.179.12")
        output = format_sheet_info(parser)

        assert "6.179.12" in output
        assert "1:10000" in output
        assert "2000" in output
        assert "Components:" in output
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
        """PL-1992 godlo should NOT show Strefa or Natywny CRS."""
        parser = SheetParser("N-34-130-D")
        output = format_sheet_info(parser)

        assert "Strefa:" not in output
        assert "Natywny CRS:" not in output


class TestParsePL2000Command:
    """Tests for 'kartograf parse' with PL-2000 godla."""

    def test_parse_pl2000_godlo(self, capsys):
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
        """Invalid PL-2000 godlo returns error."""
        result = main(["parse", "9.179.12"])

        assert result == 1


class TestCreateParserDownloadSystem:
    """Tests for --system argument on download subparser."""

    def test_system_default_is_none(self):
        """--system defaults to None (sentinel; resolved per country later)."""
        parser = create_parser()
        args = parser.parse_args(["download", "--bbox", "419000,230000,426000,237000"])
        assert args.system is None

    def test_system_2000_accepted(self):
        """--system 2000 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            ["download", "--bbox", "419000,230000,426000,237000", "--system", "2000"]
        )
        assert args.system == "2000"

    def test_system_1992_accepted(self):
        """--system 1992 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            ["download", "--bbox", "419000,230000,426000,237000", "--system", "1992"]
        )
        assert args.system == "1992"

    def test_system_invalid_rejected(self):
        """--system invalid is rejected."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["download", "--bbox", "419000,230000,426000,237000", "--system", "xyz"]
            )


class TestCreateParserBBoxCrsExtended:
    """Tests for extended --bbox-crs choices with PL-2000 CRS."""

    def test_bbox_crs_epsg2177(self):
        """--bbox-crs EPSG:2177 is accepted."""
        parser = create_parser()
        args = parser.parse_args(
            [
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
                "download",
                "--bbox",
                "8500000,5800000,8510000,5810000",
                "--bbox-crs",
                "EPSG:2179",
            ]
        )
        assert args.bbox_crs == "EPSG:2179"


class TestDownloadBBoxSystem:
    """Tests for download --bbox --system integration."""

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_system_2000_passes_param(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--system 2000 passes system='2000' to find_sheets_for_bbox."""
        mock_find.return_value = ["6.179.12"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "--system",
                "2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("system") == "2000" or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "2000"
        )

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_default_system_1992(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """Default system='1992' is passed to find_sheets_for_bbox."""
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
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
        assert call_kwargs.kwargs.get("system") == "1992" or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "1992"
        )


class TestDownloadGeometrySystem:
    """Tests for download --geometry --system integration."""

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_system_2000(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """--geometry --system 2000 passes system='2000' to find_sheets_for_geometry."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warsaw - deep inside PL (--system applies to PL only)
        mock_find.return_value = ["6.179.12"]
        mock_manager = _sheet_list_manager(tmp_path / "test.asc")
        mock_manager_cls.return_value = mock_manager

        result = main(
            [
                "download",
                "--geometry",
                str(shp_file),
                "--system",
                "2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs.kwargs.get("system") == "2000"

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_default_system_1992(
        self, mock_overall, mock_manager_cls, mock_find, mock_read_crs, capsys, tmp_path
    ):
        """Default system='1992' for geometry download."""
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
                "download",
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
        assert call_kwargs.kwargs.get("system") == "1992"


def _selection(tiles, superseded=()):
    from kartograf.providers.pl.gugik_laz import LazTileSelection

    return LazTileSelection(tiles=tuple(tiles), superseded=tuple(superseded))


class TestCmdDownloadLaz:
    """Tests for the LAZ product flow in the download command."""

    def _fake_tiles(self):
        from kartograf.providers.pl.gugik_laz import LazTile

        return [
            LazTile(
                godlo="N-33-131-B-a-1-1-4",
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
                godlo="N-33-131-B-a-1-2-3",
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
                "download",
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
            parser.parse_args(["download", "X", "--product", "nope"])

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_godlo_mode_downloads_all_tiles(self, mock_provider_cls, tmp_path):
        """sheet code → discover tiles → download each via provider.download."""
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download.return_value = tmp_path / "x.laz"
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
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
        assert instance.download.call_count == 2
        # bbox passed to select_tiles is in EPSG:2180
        bbox_arg = instance.select_tiles.call_args[0][0]
        assert bbox_arg.crs == "EPSG:2180"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_bbox_mode(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download.return_value = tmp_path / "x.laz"
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
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
        assert instance.download.call_count == 2

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
        godla = [f"N-33-131-B-a-1-1-{i}" for i in range(1, 9)]
        tiles = [
            replace(base, godlo=g, url=f"https://opendata.geoportal.gov.pl/x/{g}.laz")
            for g in godla
        ]
        good = godla[0]

        def _download(url, target, **_kwargs):
            if good in url:
                return target
            raise DownloadError(f"HTTP 503 dla {url}")

        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(tiles)
        instance.download.side_effect = _download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
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
            assert tile.godlo in err
        assert f"{good}:" not in err

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_year_and_density_forwarded(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.select_tiles.return_value = _selection(self._fake_tiles())
        instance.download.return_value = tmp_path / "x.laz"
        mock_provider_cls.return_value = instance

        main(
            [
                "download",
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
        assert kwargs.get("year") == 2023
        assert kwargs.get("min_density") == 12

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
                    "download",
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
        assert "No LAZ tiles" in err
        # N7: discovery is all-or-nothing, so an empty list = extent/filters
        assert "--year" in err and "wszystkie roczniki WFS odpowiedzialy" in err
        assert get.call_count == 3  # Capabilities and both available years completed.

    @pytest.mark.parametrize("year_args", [[], ["--year", "2024"]])
    def test_laz_wfs_failure_reports_network_error(self, year_args, capsys, tmp_path):
        import requests

        with (
            patch(
                "requests.Session.get",
                side_effect=requests.ConnectionError("connection reset by peer"),
            ) as get,
            patch("kartograf.transport.http.time.sleep"),
        ):
            result = main(
                [
                    "download",
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
        assert "No LAZ tiles" not in err
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

        instance.download.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        sidecars = list(tmp_path.rglob("*.meta.json"))
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
        expected_storage = FileStorage(tmp_path, product="laz", vertical_crs="EVRF2007")
        assert target == expected_storage.get_raw_path(
            tile.godlo, tile.filename, uklad=tile.uklad
        )
        assert target.parts[-10:-8] == ("laz", "pl_2000_evrf2007")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.laz"
        assert payload["vertical_crs"] == "EPSG:9651"
        assert payload["extra"]["tile_sheet"] == tile.godlo
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

        instance.download.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
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
        sidecars = list(tmp_path.rglob("*.meta.json"))
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

        instance.download.side_effect = fake_download
        mock_provider_cls.return_value = instance

        result = main(
            [
                "download",
                "M-34-27-B-b-2-1",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        (sidecar,) = tmp_path.rglob("*.meta.json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["horizontal_crs"] == "EPSG:2178"

    def test_laz_invalid_godlo_errors(self, capsys, tmp_path):
        result = main(
            ["download", "NOT-A-GODLO!!", "--product", "laz", "-o", str(tmp_path), "-q"]
        )
        assert result == 1

    def test_laz_missing_geometry_file_errors(self, capsys, tmp_path):
        result = main(
            [
                "download",
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
        assert "not found" in capsys.readouterr().err.lower()


class TestResolveLazBbox:
    """Tests for _resolve_laz_bbox helper."""

    def test_godlo_to_2180(self):
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox

        args = Namespace(godlo="M-34-27-B-b-2-1", bbox=None, geometry=None)
        bbox = _resolve_laz_bbox(args)
        assert bbox.crs == "EPSG:2180"
        assert bbox.min_x < bbox.max_x and bbox.min_y < bbox.max_y

    def test_bbox_wgs84_across_19e_keeps_southern_band(self):
        """K6: an envelope from densified edges - four corners lost
        ~479 m in the S for a bbox through 19E (LAZ tile selection too narrow)."""
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox

        args = Namespace(
            godlo=None, bbox="18,50,20,50.2", bbox_crs="EPSG:4326", geometry=None
        )
        bbox = _resolve_laz_bbox(args)
        assert bbox.crs == "EPSG:2180"
        assert bbox.min_y == pytest.approx(236968.4486, abs=0.01)

    def test_bbox_2180_passthrough(self):
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox

        args = Namespace(
            godlo=None,
            bbox="530000,382000,533000,386000",
            bbox_crs="EPSG:2180",
            geometry=None,
        )
        bbox = _resolve_laz_bbox(args)
        assert (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y) == (
            530000.0,
            382000.0,
            533000.0,
            386000.0,
        )

    def test_bbox_wrong_value_count_raises(self):
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox

        args = Namespace(godlo=None, bbox="1,2,3", bbox_crs="EPSG:2180", geometry=None)
        with pytest.raises(ValidationError, match="Invalid bbox format"):
            _resolve_laz_bbox(args)

    def test_bbox_from_krovak_uses_pinned_transform(self):
        """--bbox-crs EPSG:5514 (F2): the step to 2180 must go through the pinned
        operation (bbox_to_crs), NOT an unpinned pyproj transformer - otherwise
        LAZ tile selection on the border strip could result from a ballpark."""
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox
        from kartograf.core import bbox as core_bbox
        from kartograf.providers.cuzk import dmr

        args = Namespace(
            godlo=None,
            bbox="-788231,-1052442,-741087,-1013379",
            bbox_crs="EPSG:5514",
            geometry=None,
        )
        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(
                core_bbox, "_transformer", wraps=core_bbox._transformer
            ) as plain,
        ):
            bbox = _resolve_laz_bbox(args)

        assert bbox.crs == "EPSG:2180"
        assert pinned.called
        plain.assert_not_called()

    def test_bbox_from_utm33n_uses_pinned_transform(self):
        """As above, but for the second Czech CRS (EPSG:3045)."""
        from argparse import Namespace

        from kartograf.cli.download_cmd import _resolve_laz_bbox
        from kartograf.core import bbox as core_bbox
        from kartograf.providers.cuzk import dmr

        args = Namespace(
            godlo=None,
            bbox="450000,5540000,455000,5545000",
            bbox_crs="EPSG:3045",
            geometry=None,
        )
        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(
                core_bbox, "_transformer", wraps=core_bbox._transformer
            ) as plain,
        ):
            bbox = _resolve_laz_bbox(args)

        assert bbox.crs == "EPSG:2180"
        assert pinned.called
        plain.assert_not_called()


def _cz_args(tmp_path, **overrides):
    """Namespace for direct _cmd_download_cz calls."""
    base = dict(
        godlo="302_5550",
        bbox=None,
        bbox_crs="EPSG:2180",
        geometry=None,
        layer=None,
        scale=None,
        output=str(tmp_path),
        force=False,
        quiet=True,
        vertical_crs=None,
        resolution=None,
        product="nmt",
        system=None,
        country="cz",
        target_crs=None,
        workers=1,
        year=None,
        min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _cz_provider_mock(resolution="2m"):
    """CuzkDmrProvider mock for the CLI flow."""
    provider = Mock()
    provider.descriptor_key = "cz.cuzk.dmr5g" if resolution == "2m" else "cz.cuzk.dmr4g"
    provider.resolution = resolution
    provider.vertical_crs = "Bpv"
    provider.vertical_transform = None

    def fake_horizontal(target_crs):
        """CuzkDmrProvider.horizontal_transform contract: None for native."""
        if target_crs.endswith("5514"):
            return None
        pinned = Mock()
        pinned.description = f"S-JTSK to ETRS89 (1) -> {target_crs}"
        pinned.accuracy_m = 1.0
        return pinned

    provider.horizontal_transform.side_effect = fake_horizontal

    def fake_download(godlo, target, timeout=60, *, on_download=None):
        # provider contract: announce after validation, before the transfer
        if on_download is not None:
            on_download()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download.side_effect = fake_download
    provider.download_bbox.side_effect = lambda bbox, target, **kw: fake_download(
        "x", target, on_download=kw.get("on_download")
    )
    return provider


_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_dmr_provider"


class TestCzDownloadingAfterValidation:
    """``Downloading ...`` in the CZ flow only when the transfer really starts.

    Uses the real ``CuzkDmrProvider`` (offline: ``CuzkClient`` and
    ``SheetIndex`` mocked), so validations inside the provider run for real.
    """

    _CLIENT = "kartograf.providers.cuzk.dmr.CuzkClient"
    _INDEX = "kartograf.providers.cuzk.dmr.SheetIndex"

    @staticmethod
    def _sm5_info():
        from kartograf.providers.cuzk.sheets import SheetInfo

        return SheetInfo(
            godlo="CTES96",
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
            rc = main(["download", "ABCD12", "--country", "cz", "-o", str(out)])
            client_cls.return_value.fetch_file.assert_not_called()

        captured = capsys.readouterr()
        assert rc == 1
        assert "Downloading" not in captured.out
        assert "Error: Arkusz SM5 'ABCD12' nie istnieje" in captured.err
        assert not list(out.rglob("*.tif"))

    def test_invalid_tm33_tile_is_error_without_downloading(self, tmp_path, capsys):
        """Odd kilometres match the TM33 pattern but fail ``ParserTM33``."""
        with patch(self._CLIENT) as client_cls, patch(self._INDEX):
            rc = main(
                ["download", "301_5550", "--country", "cz", "-o", str(tmp_path / "o")]
            )
            client_cls.return_value.export_image.assert_not_called()

        captured = capsys.readouterr()
        assert rc == 1
        assert "Downloading" not in captured.out
        assert "Error:" in captured.err and "parzyste" in captured.err

    def test_sm5_announces_once_before_file_is_written(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        seen_at_fetch: list[str] = []

        def fake_fetch(url, output_path, *, unzip_single=None):
            seen_at_fetch.append(capsys.readouterr().out)
            self._write_tif(output_path, crs=None)
            return output_path

        with patch(self._CLIENT) as client_cls, patch(self._INDEX) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = self._sm5_info()
            client_cls.return_value.fetch_file.side_effect = fake_fetch
            rc = main(
                ["download", "CTES96", "--country", "cz", "-o", str(tmp_path / "o")]
            )

        rest = capsys.readouterr().out
        assert rc == 0
        assert len(seen_at_fetch) == 1
        assert seen_at_fetch[0].count("Downloading CTES96 (CZ, resolution: 5m)") == 1
        assert "Downloading" not in rest
        assert "Downloaded to " in rest

    def test_tm33_announces_once_before_export(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        seen_at_export: list[str] = []

        def fake_export(endpoint, bbox, **kwargs):
            seen_at_export.append(capsys.readouterr().out)
            self._write_tif(kwargs["output_path"], crs="EPSG:5514")
            return kwargs["output_path"]

        with (
            patch(self._CLIENT) as client_cls,
            patch(self._INDEX),
            patch("kartograf.providers.cuzk.dmr.warp_to_grid") as warp,
        ):
            warp.side_effect = lambda src, dst, *a, **k: self._write_tif(
                dst, crs="EPSG:3045"
            )
            client_cls.return_value.export_image.side_effect = fake_export
            rc = main(
                ["download", "302_5550", "--country", "cz", "-o", str(tmp_path / "o")]
            )

        rest = capsys.readouterr().out
        assert rc == 0
        assert len(seen_at_export) == 1
        assert seen_at_export[0].count("Downloading 302_5550 (CZ, resolution: 2m)") == 1
        assert "Downloading" not in rest

    def test_bbox_announces_once_before_export(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        seen_at_export: list[str] = []

        def fake_export(endpoint, bbox, **kwargs):
            seen_at_export.append(capsys.readouterr().out)
            self._write_tif(kwargs["output_path"], crs="EPSG:5514")
            return kwargs["output_path"]

        with patch(self._CLIENT) as client_cls, patch(self._INDEX):
            client_cls.return_value.export_image.side_effect = fake_export
            rc = main(
                [
                    "download",
                    "--bbox=-447000,-1114000,-446000,-1113000",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path / "o"),
                ]
            )

        rest = capsys.readouterr().out
        assert rc == 0
        assert len(seen_at_export) == 1
        assert seen_at_export[0].count("Downloading CZ bbox (2m, EPSG:5514)") == 1
        assert "Downloading" not in rest

    def test_bbox_rejected_in_provider_is_error_without_downloading(
        self, tmp_path, capsys
    ):
        """A validation failure inside ``download_bbox`` (before exportImage)."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = ValidationError("zly bbox")
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        args = _cz_args(tmp_path, godlo=None, quiet=False)
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(args, bbox=bbox)

        captured = capsys.readouterr()
        assert rc == 1
        assert "Downloading" not in captured.out
        assert "Error: zly bbox" in captured.err

    @pytest.mark.parametrize("bbox_mode", [False, True])
    def test_quiet_passes_no_announcement(self, tmp_path, capsys, bbox_mode):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        args = _cz_args(tmp_path, godlo=None if bbox_mode else "302_5550")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(args, bbox=bbox if bbox_mode else None)

        assert rc == 0
        assert capsys.readouterr().out == ""
        called = provider.download_bbox if bbox_mode else provider.download
        called.assert_called_once()


class TestCmdDownloadCz:
    """Tests for the CZ (CUZK) flow in the download command."""

    def test_tm33_godlo_saves_under_cz_dmr5g(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 0
        assert factory.call_args.kwargs["resolution"] == "2m"
        assert factory.call_args.kwargs["vertical_crs"] == "Bpv"
        target = provider.download.call_args.args[1]
        assert target == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        )

    @pytest.mark.parametrize("force", [False, True])
    def test_force_refreshes_sheet_index_cache(self, tmp_path, force):
        """D16: ``--force`` in the CZ path = ``MetadataCache(refresh=True)`` as in PL
        (the SM5 sheet index is queried anew and saved); without ``--force``
        the cache is read normally. The cache is closed after the task."""
        from kartograf.cache import MetadataCache
        from kartograf.cli.download_cmd import _cmd_download_cz

        with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()) as factory:
            result = _cmd_download_cz(_cz_args(tmp_path, force=force))

        assert result == 0
        cache = factory.call_args.kwargs["cache"]
        assert isinstance(cache, MetadataCache)
        assert cache._refresh is force
        assert cache._conn is None

    def test_unreadable_cache_warns_and_downloads(self, tmp_path, capsys):
        """An unreadable cache in the CZ path: one ``Warning:``, code 0."""
        from kartograf.cli.download_cmd import _cmd_download_cz

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

    def test_tm33_godlo_writes_sidecar(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

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

    def test_sm5_godlo_enriches_extra_with_cz_share(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz
        from kartograf.providers.cuzk.sheets import SheetInfo

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.return_value = SheetInfo(
            godlo="CTES96",
            name="Český Těšín 9-6",
            bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
            podil=0.99,
            in_cz=None,
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo="CTES96", resolution="5m")
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
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.side_effect = DownloadError("siec padla")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo="CTES96", resolution="5m")
            )

        assert result == 0
        target = tmp_path / "nmt" / "cz_dmr4g_bpv" / "CTES" / "96" / "CTES96.tif"
        assert target.exists()
        payload = json.loads(
            (target.parent / "CTES96.tif.meta.json").read_text(encoding="utf-8")
        )
        assert "cz_share" not in payload["extra"]

    @pytest.mark.parametrize("country", ["auto", "cz"])
    def test_sm5_godlo_without_resolution_defaults_to_5m(
        self, tmp_path, capsys, country
    ):
        """An SM5 sheet exists only at 5 m (DMR 4G): without ``--resolution``
        the resolution follows from the sheet code - the download starts, without an
        extra message (the resolution is visible in ``Downloading``)."""
        from kartograf.providers.cuzk.sheets import SheetInfo

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.return_value = SheetInfo(
            godlo="CTES96",
            name=None,
            bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
            podil=None,
            in_cz=None,
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(
                [
                    "download",
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
        assert "Downloading CTES96 (CZ, resolution: 5m)..." in captured.out
        assert captured.err == ""

    def test_sm5_godlo_with_explicit_2m_is_error_without_network(
        self, tmp_path, capsys
    ):
        """An explicit ``--resolution 2m`` with an SM5 sheet code is a contradictory
        request:
        ``Error:`` before the provider is created and without ``Downloading``."""
        with patch(_CZ_FACTORY_PATCH) as factory:
            rc = main(
                [
                    "download",
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
        assert "Downloading" not in captured.out
        assert "Error: Arkusze SM5" in captured.err
        assert "5m" in captured.err

    def test_tm33_godlo_without_resolution_stays_2m(self, tmp_path):
        """TM33 tile cut from the service: 2 m by default, as before."""
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(["download", "302_5550", "-o", str(tmp_path / "out"), "-q"])

        assert rc == 0
        assert factory.call_args.kwargs["resolution"] == "2m"

    def test_cz_bbox_without_resolution_stays_2m(self, tmp_path):
        """CZ ``--bbox`` cutout: 2 m by default, as before."""
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            rc = main(
                [
                    "download",
                    "--bbox=-447000,-1114000,-446000,-1113000",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path / "out"),
                    "-q",
                ]
            )

        assert rc == 0
        assert factory.call_args.kwargs["resolution"] == "2m"

    def test_bbox_mode_file_in_bbox_subdir_and_parent_request(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        parent = {
            "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["CZ", "PL"],
        }
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo=None), bbox=bbox, parent_request=parent
            )

        assert result == 0
        target = (
            tmp_path
            / "nmt"
            / "cz_dmr5g_bpv"
            / "bbox"
            / "-447000_-1114000_-446000_-1113000.tif"
        )
        assert provider.download_bbox.call_args.args[1] == target
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["request"]["bbox_crs"] == "EPSG:5514"
        assert payload["nodata"] == -9999.0  # GeoTIFF tag unreadable -> default
        assert payload["transform"] is None  # without --target-crs: native CRS

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
                    "download",
                    "--bbox",
                    "472887.5,208337.5,473808.0,209409.8",
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        sent_bbox, target = provider.download_bbox.call_args.args[:2]
        assert sent_bbox.crs == "EPSG:5514"
        assert -450000 < sent_bbox.min_x < -440000  # Krovak: negative values
        assert target.parent == tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox"
        assert target.name == (
            f"{format(sent_bbox.min_x, '.10g')}"
            f"_{format(sent_bbox.min_y, '.10g')}"
            f"_{format(sent_bbox.max_x, '.10g')}"
            f"_{format(sent_bbox.max_y, '.10g')}.tif"
        )

    def test_bbox_with_target_crs_records_pinned_transform(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo=None, target_crs="EPSG:3045"), bbox=bbox
            )

        assert result == 0
        assert factory.call_args.kwargs["target_crs"] == "EPSG:3045"
        sent_bbox, target = provider.download_bbox.call_args.args[:2]
        assert sent_bbox.crs == "EPSG:3045"
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["horizontal_crs"] == "EPSG:3045"
        assert payload["transform"] == {
            "horizontal": "pinned: S-JTSK to ETRS89 (1) -> EPSG:3045 (1.0 m)"
        }

    def test_godlo_without_safe_horizontal_operation_exits_cleanly(
        self, tmp_path, capsys
    ):
        """The TM33 sheet code path builds the horizontal operation only at download
        time (a sheet code has no `--target-crs`, so the constructor does not touch
        it) - a missing safe operation must give a message with a remedy and exit
        code 1, NOT a traceback.

        The safeguard lies in `_run_cz`, not in `_cz_download_godlo`, so it is
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
            "kartograf.providers.cuzk.dmr.build_pinned_transform", side_effect=_boom
        ):
            result = main(
                ["download", "302_5550", "--country", "cz", "-o", str(tmp_path)]
            )

        assert result == 1
        captured = capsys.readouterr()
        assert "EPSG:5514 -> EPSG:3045" in captured.err
        assert "Remedium: zainstaluj siatki recznie" in captured.err
        assert "Traceback" not in captured.err
        assert not list(tmp_path.rglob("*.tif"))

    def test_provider_factory_transform_error_reports_remedy(self, tmp_path, capsys):
        """D6: TransformError from the provider constructor (the operation for
        ``--target-crs``) - the same ``Error: ... Remedium: ...`` format as the
        other CLI paths, exit code 1, no traceback."""
        from kartograf.transform.crs import TransformUnavailableError

        boom = TransformUnavailableError(
            "Brak bezpiecznej operacji transformacji EPSG:5514 -> EPSG:3045",
            remedy="zainstaluj siatki recznie do PROJ_DATA",
        )
        with patch(_CZ_FACTORY_PATCH, side_effect=boom):
            result = main(
                [
                    "download",
                    "--bbox=-447000,-1114000,-446000,-1113000",
                    "--bbox-crs",
                    "EPSG:5514",
                    "--country",
                    "cz",
                    "--target-crs",
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

    def test_target_crs_with_godlo_rejected(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        with pytest.raises(ValidationError, match="--target-crs"):
            _cmd_download_cz(_cz_args(tmp_path, target_crs="EPSG:2180"))

    def test_resolution_1m_rejected(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        result = _cmd_download_cz(_cz_args(tmp_path, resolution="1m"))
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_system_flag_rejected(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        result = _cmd_download_cz(_cz_args(tmp_path, system="1992"))
        assert result == 1
        assert "--system" in capsys.readouterr().err

    def test_kron86_prints_remedy(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz
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
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download.side_effect = DownloadError("404 openzu")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 1
        assert "404 openzu" in capsys.readouterr().err
        assert not (tmp_path / "nmt" / "cz_dmr5g_bpv").exists()

    def test_skip_existing(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"stare")
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path))
        assert result == 0
        provider.download.assert_not_called()

    def test_force_overwrites_existing(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"stare")
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path, force=True))
        assert result == 0
        provider.download.assert_called_once()

    def test_evrf2007_transform_lands_in_sidecar(self, tmp_path):
        """Bpv->EVRF2007 vertical transformation recorded in the sidecar.

        The segment carries the provider's vertical CRS (ADR-026).
        """
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.vertical_crs = "EVRF2007"
        pinned = Mock()
        pinned.description = "Baltic 1957 height to EVRF2007 height (1)"
        pinned.accuracy_m = 0.1
        provider.vertical_transform = pinned
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

    def test_sidecar_failure_does_not_fail_download(self, tmp_path, caplog):
        """A sidecar write error = warning, not a download failure."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        with (
            patch(_CZ_FACTORY_PATCH, return_value=provider),
            patch(
                "kartograf.sources.sidecar.build_metadata",
                side_effect=RuntimeError("deskryptor padl"),
            ),
        ):
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 0
        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        assert target.exists()
        assert not (target.parent / "302_5550.tif.meta.json").exists()

    def test_factory_validation_error_returns_1(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        with patch(
            _CZ_FACTORY_PATCH,
            side_effect=ValidationError("Nieobslugiwany uklad pionowy dla CZ"),
        ):
            result = _cmd_download_cz(_cz_args(tmp_path, vertical_crs="KRON86"))

        assert result == 1
        assert "Error: Nieobslugiwany uklad pionowy" in capsys.readouterr().err

    def test_verbose_godlo_reports_progress_and_skip(self, tmp_path, capsys):
        """Per-file messages in the LAZ/PL flow convention."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(_cz_args(tmp_path, quiet=False)) == 0
            first = capsys.readouterr().out
            assert _cmd_download_cz(_cz_args(tmp_path, quiet=False)) == 0
            second = capsys.readouterr().out

        assert "Downloading 302_5550 (CZ, resolution: 2m)" in first
        assert "Downloaded to " in first
        assert "Skipped 302_5550 - already exists at " in second
        provider.download.assert_called_once()

    def test_verbose_bbox_reports_progress_and_skip(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        args = _cz_args(tmp_path, godlo=None, quiet=False)
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(args, bbox=bbox) == 0
            first = capsys.readouterr().out
            assert _cmd_download_cz(args, bbox=bbox) == 0
            second = capsys.readouterr().out

        assert "Downloading CZ bbox (2m, EPSG:5514)" in first
        assert "Downloaded to " in first
        assert "Skipped - already exists at " in second
        provider.download_bbox.assert_called_once()

    def test_bbox_download_error_returns_1(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = DownloadError("exportImage 500")
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path, godlo=None), bbox=bbox)

        assert result == 1
        assert "exportImage 500" in capsys.readouterr().err
        assert not (tmp_path / "nmt").exists()

    def test_sidecar_nodata_comes_from_geotiff_tag(self, tmp_path):
        """Sidecar nodata comes from the downloaded raster's tag, not a constant."""
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from kartograf.cli.download_cmd import _cmd_download_cz

        def real_tif(godlo, target, timeout=60, *, on_download=None):
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
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = self._real_tif_writer(-9999.0)
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path, godlo=None), bbox=bbox)

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "w calosci nodata" in err
        assert "poza granica CZ?" in err
        assert list((tmp_path / "nmt").rglob("*.tif.meta.json"))

    def test_tm33_godlo_all_nodata_warns_but_returns_0(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download.side_effect = self._real_tif_writer(-9999.0)
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path))

        assert rc == 0
        err = capsys.readouterr().err
        assert "302_5550.tif jest w calosci nodata" in err

    def test_bbox_with_data_has_no_nodata_warning(self, tmp_path, capsys):
        """Control: a raster with data (even one pixel) — no message."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.download_bbox.side_effect = self._real_tif_writer(123.0)
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path, godlo=None), bbox=bbox)

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

    @pytest.mark.parametrize(
        ("horizontal", "expect_info"),
        [
            ("S-JTSK to ETRS89 (3) + UTM zone 33N (0.5 m)", True),
            ("S-JTSK to ETRS89 (1) + UTM zone 33N (1 m)", False),
            (None, False),
        ],
    )
    def test_skipped_tm33_tile_reports_legacy_krovak_sidecar(
        self, tmp_path, capsys, horizontal, expect_info
    ):
        from kartograf.cli.download_cmd import _cmd_download_cz

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        self._existing_with_sidecar(target, horizontal)
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            rc = _cmd_download_cz(_cz_args(tmp_path))

        assert rc == 0
        provider.download.assert_not_called()
        err = capsys.readouterr().err
        assert ("sprzed naprawy operacji S-JTSK" in err) is expect_info
        if expect_info:
            assert str(target) in err and "--force" in err

    def test_skipped_bbox_cutout_reports_legacy_krovak_sidecar(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        args = _cz_args(tmp_path, godlo=None, target_crs="EPSG:2180")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(args, bbox=bbox) == 0
        target = next((tmp_path / "nmt").rglob("*.tif"))
        self._existing_with_sidecar(target, "S-JTSK to ETRS89 (3) -> EPSG:2180")
        capsys.readouterr()

        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            assert _cmd_download_cz(args, bbox=bbox) == 0

        provider.download_bbox.assert_called_once()
        assert "sprzed naprawy operacji S-JTSK" in capsys.readouterr().err

    def test_skipped_file_without_sidecar_is_silent(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"stare")
        with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()):
            assert _cmd_download_cz(_cz_args(tmp_path)) == 0
        assert capsys.readouterr().err == ""

    def test_target_crs_with_godlo_message_names_product_frames(self, tmp_path):
        """K2: the message says WHAT the code defines (SM5 in 5514, TM33 on 3045)."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        with pytest.raises(ValidationError, match="kafel TM33 na siatce EPSG:3045"):
            _cmd_download_cz(_cz_args(tmp_path, target_crs="EPSG:2180"))


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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_godlo_routes_to_cz_flow(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(["download", "302_5550", "-o", str(tmp_path), "-q"])
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_sm5_godlo_auto_detected(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            ["download", "CTES96", "--resolution", "5m", "-o", str(tmp_path), "-q"]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_godlo_with_country_cz_routes_to_cz_flow(self, mock_cz, tmp_path):
        """An explicit --country cz consistent with the sheet code is not a conflict."""
        mock_cz.return_value = 0
        result = main(
            ["download", "302_5550", "--country", "cz", "-o", str(tmp_path), "-q"]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_godlo_keeps_sentinels_unresolved(self, mock_cz, tmp_path):
        """PL sentinels must not touch the arguments going to CZ."""
        mock_cz.return_value = 0
        main(["download", "302_5550", "-o", str(tmp_path), "-q"])
        args = mock_cz.call_args.args[0]
        assert args.resolution is None
        assert args.vertical_crs is None
        assert args.system is None

    def test_cz_godlo_with_country_pl_conflicts(self, tmp_path, capsys):
        result = main(["download", "CTES96", "--country", "pl", "-o", str(tmp_path)])
        assert result == 1
        assert "cz_sm5" in capsys.readouterr().err

    def test_pl_godlo_with_country_cz_conflicts(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--country", "cz", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "pl" in capsys.readouterr().err.lower()

    # --- sentinele PL ---

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_godlo_sentinels_resolved_to_defaults(
        self, mock_manager_class, tmp_path
    ):
        """Observable PL behaviour unchanged: None -> 1m/EVRF2007."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["resolution"] == "1m"
        assert kwargs["vertical_crs"] == "EVRF2007"

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_5m_kron86_corrected_with_info(
        self, mock_manager_class, mock_create, tmp_path, capsys
    ):
        """D11: one "5m => EVRF2007" rule, one effect - an explicit correction.

        Previously the correction went only to the log (invisible in the CLI); now
        ``Info:`` on stderr (also with ``-q``), and the factory and manager get
        the ACTUAL vertical CRS.
        """
        mock_create.return_value = (Mock(), Mock())
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--resolution",
                "5m",
                "--vertical-crs",
                "KRON86",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        err = capsys.readouterr().err
        assert "Info:" in err and "KRON86" in err and "EVRF2007" in err
        assert mock_create.call_args.args[2] == "EVRF2007"
        assert mock_manager_class.call_args.kwargs["vertical_crs"] == "EVRF2007"

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_1m_kron86_no_correction(self, mock_manager_class, tmp_path, capsys):
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(
            [
                "download",
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
        assert mock_manager_class.call_args.kwargs["vertical_crs"] == "KRON86"

    def test_5m_rule_only_for_nmt(self, capsys):
        """LAZ also goes through the PL sentinels - the NMT rule does not apply."""
        from kartograf.cli.download_cmd import _resolve_pl_sentinels

        args = argparse.Namespace(
            product="laz",
            resolution="5m",
            vertical_crs="KRON86",
            target_crs=None,
            system=None,
        )
        assert _resolve_pl_sentinels(args) == 0
        assert args.vertical_crs == "KRON86"
        assert "Info:" not in capsys.readouterr().err

    def test_pl_godlo_with_2m_rejected(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--resolution", "2m", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_pl_godlo_with_bpv_rejected(self, tmp_path, capsys):
        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--vertical-crs",
                "Bpv",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "Bpv" in capsys.readouterr().err

    def test_pl_godlo_with_target_crs_rejected(self, tmp_path, capsys):
        result = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    # PL bbox + --target-crs has been a legal cutout flow since ADR-027 —
    # covered by tests/test_pl_cutout.py (TestDownloadPlBboxCutout).

    # --- ValidationError from the CZ flow does not escape as a traceback ---

    def test_cz_godlo_parse_error_returns_1_without_traceback(self, tmp_path, capsys):
        """TM33 pattern with odd km: a CLI error (ParseError), not a traceback."""
        result = main(["download", "301_5551", "-o", str(tmp_path), "-q"])
        assert result == 1
        err = capsys.readouterr().err
        assert "Error:" in err
        assert "301_5551" in err

    def test_cz_godlo_with_target_crs_returns_1_without_traceback(
        self, tmp_path, capsys
    ):
        """R9: --target-crs + CZ sheet code = a CLI error (main catches nothing)."""
        result = main(
            ["download", "302_5550", "--target-crs", "EPSG:3045", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--target-crs" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_validation_error_from_area_mode_returns_1(
        self, mock_cz, tmp_path, capsys
    ):
        mock_cz.side_effect = ValidationError("cos nie gra")
        result = main(
            [
                "download",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "cos nie gra" in capsys.readouterr().err

    # --- products other than nmt for CZ ---

    def test_laz_with_country_cz_rejected(self, tmp_path, capsys):
        result = main(["download", "302_5550", "--product", "laz", "-o", str(tmp_path)])
        assert result == 1
        assert "etapie 2" in capsys.readouterr().err

    def test_laz_bbox_with_country_cz_rejected(self, tmp_path, capsys):
        result = main(
            [
                "download",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "etapie 2" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_orto_bbox_with_country_cz_rejected(self, mock_cz, tmp_path, capsys):
        result = main(
            [
                "download",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--product",
                "orto",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "etapie 2" in capsys.readouterr().err
        mock_cz.assert_not_called()

    # --- area modes: explicit --country cz ---

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_bbox_with_country_cz_routes_to_cz_flow(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "download",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
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
                    "download",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        requested = CRS.from_user_input(spy_bbox.call_args.kwargs["target_crs"])
        assert requested == CRS.from_epsg(4326)  # the file's CRS, not Krovak
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_cz_bbox_goes_through_pinned_transform(self, mock_cz, tmp_path):
        """The hop to Krovak uses the pinned operation with edge sampling."""
        from kartograf.providers.cuzk import dmr

        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0
        with patch.object(
            dmr, "build_pinned_transform", wraps=dmr.build_pinned_transform
        ) as spy:
            result = main(
                [
                    "download",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
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
                    "download",
                    "--geometry",
                    str(shp),
                    "--country",
                    "cz",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        mock_transformer.assert_not_called()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_cz_target_crs_in_one_hop(self, mock_cz, tmp_path):
        """--target-crs: the envelope directly in the CRS requested from the server."""
        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0

        result = main(
            [
                "download",
                "--geometry",
                str(shp),
                "--country",
                "cz",
                "--target-crs",
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
                "download",
                "--geometry",
                str(tmp_path / "missing.shp"),
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        assert "not found" in capsys.readouterr().err.lower()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    def test_bbox_auto_stays_pl(self, mock_find, mock_manager_class, mock_cz, tmp_path):
        """--country auto + a bbox deep inside PL (Warsaw): the CZ flow untouched."""
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        assert mock_find.call_args.kwargs.get("system") == "1992"

    def test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl(
        self, tmp_path
    ):
        """Finding 4 of review max: a geometry file in EPSG:5514 with --country pl.

        The PL envelope is built by the pinned operation (like --bbox in a Czech
        CRS), not by the default transformer from core/geometry (~1.2 m
        difference).
        """
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        shp = _write_krovak_shp(tmp_path)
        captured = {}

        def fake_pl_geometry(args, filepath, parent_request, bbox):
            captured.update(bbox=bbox, parent=parent_request)
            return 0

        with patch(
            "kartograf.cli.download_cmd._download_pl_geometry",
            side_effect=fake_pl_geometry,
        ):
            rc = main(
                [
                    "download",
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


class TestAutoSplitBBox:
    """--country auto: a cross-border bbox split into countries, parent_request."""

    # 18.4-18.8E / 49.55-49.75N — PL/CZ border strip (both country envelopes
    # contain this rectangle: CZ up to 18.86E/51.06N, PL from 14.07E/49.0N)
    _BORDER = [
        "download",
        "--bbox",
        "18.4,49.55,18.8,49.75",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 21.0-21.2E / 52.0-52.2N — Warsaw, east of the CZ envelope (18.86E)
    _PL_ONLY = [
        "download",
        "--bbox",
        "21.0,52.0,21.2,52.2",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 13.3-13.5E / 49.7-49.8N — Plzen, west of the PL envelope (14.07E)
    _CZ_ONLY = [
        "download",
        "--bbox",
        "13.3,49.7,13.5,49.8",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_border_bbox_splits_into_both_countries(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        expected_parent = {
            "bbox": [18.4, 49.55, 18.8, 49.75],
            "bbox_crs": "EPSG:4326",
            "countries": ["CZ", "PL"],
        }
        # PL: the manager received sidecar_extra with parent_request
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"] == {"parent_request": expected_parent}
        # CZ: flow called with the same parent_request and a bbox in Krovak
        cz_kwargs = mock_cz.call_args.kwargs
        assert cz_kwargs["parent_request"] == expected_parent
        assert cz_kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_country_order_is_deterministic(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Country order from all_countries() — sorted (CZ before PL)."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        main(self._BORDER + ["-o", str(tmp_path)])

        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["countries"] == sorted(parent["countries"])

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_branch_does_not_poison_cz_args(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """The PL branch works on a COPY of args — the CZ sentinels stay None."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        main(self._BORDER + ["-o", str(tmp_path)])

        # the mock holds a REFERENCE to the Namespace — had the PL branch (run
        # after CZ) mutated the same object, the sentinels would be resolved
        cz_args = mock_cz.call_args.args[0]
        assert cz_args.resolution is None
        assert cz_args.vertical_crs is None
        assert cz_args.system is None

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_cz_only_bbox_skips_pl_flow(self, mock_manager_class, mock_cz, tmp_path):
        """A bbox entirely in CZ (13.3-13.5E, west of 14.07E): CUZK only."""
        mock_cz.return_value = 0
        result = main(self._CZ_ONLY + ["-o", str(tmp_path)])

        assert result == 0
        mock_manager_class.assert_not_called()
        assert mock_cz.call_args.kwargs["parent_request"]["countries"] == ["CZ"]

    def test_cz_only_bbox_with_orto_rejected_as_stage_2(self, tmp_path, capsys):
        """Country decided by the area - a stage 2 message, not about the choice."""
        result = main(self._CZ_ONLY + ["--product", "orto", "-o", str(tmp_path)])
        assert result == 1
        assert "etapie 2" in capsys.readouterr().err

    def test_single_country_error_has_no_country_hint(self, tmp_path, capsys):
        """With a single country the --country hint would be empty."""
        result = main(self._CZ_ONLY + ["--resolution", "1m", "-o", str(tmp_path)])
        assert result == 1
        err = capsys.readouterr().err
        assert "nie istnieje dla CZ" in err
        assert "uzyj jawnie" not in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_explicit_cz_bbox_gets_parent_request(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            [
                "download",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_clips_cz_part_to_country_extent(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Auto mode clips the CZ part to the country envelope (18.86E)."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(
            [
                "download",
                "--bbox",
                "18.4,49.55,19.5,49.75",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path),
                "-q",
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

    def _run_auto(self, mock_find, mock_manager_class, tmp_path, bbox, crs):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")
        return main(
            ["download", "--bbox", bbox, "--bbox-crs", crs, "-o", str(tmp_path), "-q"]
        )

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
        assert "N: 54,90°N" in err
        assert "request.sheet" in err and "plik i request.bbox" not in err
        assert "poza zasiegiem PL/CZ" in err
        assert "--country pl" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
        assert "W: 14,07°E" in err
        assert "poza zasiegiem PL/CZ" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_bogatynia_cz_clipped_but_nothing_lost(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """The clipped CZ part lies in PL: one Info: (CZ, 51,06°N), nothing lost."""
        mock_cz.return_value = 0
        rc = self._run_auto(
            mock_find, mock_manager_class, tmp_path, "15.0,50.9,15.3,51.2", "EPSG:4326"
        )

        assert rc == 0
        err = capsys.readouterr().err
        info_lines = [line for line in err.splitlines() if line.startswith("Info:")]
        assert len(info_lines) == 1
        assert "czesc CZ przycieta" in info_lines[0] and "N: 51,06°N" in info_lines[0]
        assert "poza zasiegiem" not in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_bbox_inside_both_extents_stays_silent(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Silence regression: no Info: without clipping."""
        mock_cz.return_value = 0
        rc = self._run_auto(
            mock_find,
            mock_manager_class,
            tmp_path,
            "18.4,49.55,18.8,49.75",
            "EPSG:4326",
        )

        assert rc == 0
        assert "Info:" not in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_corner_loss_reported_even_when_edges_look_covered(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """13-15°E x 53-55°N: the corner loss shows only after the split."""
        rc = self._run_auto(
            mock_find, mock_manager_class, tmp_path, "13,53,15,55", "EPSG:4326"
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "W: 14,07°E, N: 54,90°N" in err
        assert "13,00°E-15,00°E x 53,00°N-55,00°N" in err
        assert "% powierzchni zadania" in err

    def test_area_outside_extents_splits_bbox_into_cells(self):
        """Pure function: cells outside all rectangles + the share."""
        from kartograf.cli.download_cmd import _area_outside_extents

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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_part_of_cz_crs_bbox_leaves_krovak_pinned(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """A request in Krovak also routed to PL: the 5514->2180 step is pinned.

        The bbox 13.73-14.46E / 49.95-50.35N (given in EPSG:5514) crosses both
        countries and is ACTUALLY clipped for PL (the PL envelope starts
        at 14.07E) - i.e. it enters the path in which GUGiK sheet selection
        could result from unpinned Krovak transformations.
        """
        from kartograf.cli.download_cmd import _bbox_to_wgs84
        from kartograf.core import bbox as core_bbox
        from kartograf.core.bbox import is_czech_crs
        from kartograf.providers.cuzk import dmr

        mock_find.return_value = ["M-33-46-A-a-1-1"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(
                core_bbox, "_transformer", wraps=core_bbox._transformer
            ) as plain,
        ):
            result = main(
                [
                    "download",
                    "--bbox=-788231,-1052442,-741087,-1013379",
                    "--bbox-crs",
                    "EPSG:5514",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert result == 0
        # the PL branch got a bbox in the Polish CRS
        pl_bbox = mock_find.call_args.args[0]
        assert pl_bbox.crs == "EPSG:2180"
        # ...clipped to the PL envelope (request reached 13.73E, PL from 14.07E)
        assert _bbox_to_wgs84(pl_bbox).min_x > 13.9
        # ...and derived from Krovak with the pinned operation
        assert any(call.args[1] == "EPSG:2180" for call in pinned.call_args_list)
        # an unpinned transformer never targets a Czech CRS
        assert not any(is_czech_crs(call.args[1]) for call in plain.call_args_list)

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_cz_failure_does_not_skip_pl_and_warns(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """A failure of the first country cancels neither the second nor the task."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 1  # CZ goes first (sorting) and fails

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        mock_manager.download_sheets.assert_called_once()
        err = capsys.readouterr().err
        assert "Warning:" in err
        assert "czesc CZ zadania zakonczyla sie bledem" in err
        assert "pobrano PL" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_failure_with_cz_success_warns_and_returns_0(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(failed=["M-34-86-D-d-4-3"])
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        err = capsys.readouterr().err
        assert "Error: 1 z 1 arkuszy nie pobrano" in err
        assert "Warning: czesc PL zadania zakonczyla sie bledem" in err

    # --- A3-2: rectangular country envelopes vs exit code ---

    # 14.40-14.45E / 50.05-50.10N - Prague, deep in CZ, but inside the PL
    # rectangle (from 14.07E): auto also queries GUGiK, which has no data there
    _PRAGUE = [
        "download",
        "--bbox",
        "14.40,50.05,14.45,50.10",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_one_country_failed_other_succeeded_returns_0(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """A country with no data in the other's area does not break the task."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = _sheet_list_manager(no_coverage=["M-33-65-D-b-3-3"])
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._PRAGUE + ["-o", str(tmp_path)])

        assert result == 0
        err = capsys.readouterr().err
        assert "Error: GUGiK nie ma danych dla zadnego z 1 arkuszy" in err
        assert "Warning: czesc PL zadania zakonczyla sie bledem" in err
        assert "pobrano CZ" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_all_countries_failed_returns_1(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """When all countries failed, the exit code stays unchanged."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = _sheet_list_manager(failed=["M-33-65-D-b-3-3"])
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 1

        result = main(self._PRAGUE + ["-o", str(tmp_path)])

        assert result == 1
        assert "Warning:" not in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_explicit_country_failure_still_returns_1(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Explicit --country: the user knows the extent, so a failure is a failure."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = _sheet_list_manager(failed=["M-33-65-D-b-3-3"])
        mock_manager_class.return_value = mock_manager

        result = main(self._PRAGUE + ["--country", "pl", "-o", str(tmp_path)])

        assert result == 1
        mock_cz.assert_not_called()
        assert "Warning:" not in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_godlo_mode_has_no_parent_request(self, mock_manager_class, tmp_path):
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs.get("sidecar_extra") is None

    # --- N6-2: PL-only flags resolve `auto` instead of failing the task ---

    def _pl_mocks(self, mock_manager_class, mock_find, tmp_path, godlo):
        """PL branch: one sheet, the manager returns a ready file."""
        mock_find.return_value = [godlo]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        return mock_manager

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_resolution_1m_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """1m does not exist in CZ (2m/5m): auto resolves the country to PL."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "M-34-86-D-d-4-3")

        result = main(self._BORDER + ["--resolution", "1m", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert "--country auto -> pl" in err
        assert "--resolution 1m" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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

    def test_border_bbox_with_2m_unresolvable_for_pl(self, tmp_path, capsys):
        result = main(self._BORDER + ["--resolution", "2m", "-o", str(tmp_path)])
        assert result == 1
        assert "--country" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_system_2000_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """--system does not apply to CZ: auto = pl, and the sidecar carries PL only."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "6.179.12.20")

        result = main(self._BORDER + ["--system", "2000", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        parent = mock_manager_class.call_args.kwargs["sidecar_extra"]["parent_request"]
        assert parent["countries"] == ["PL"]
        err = capsys.readouterr().err
        assert "--country auto -> pl" in err
        assert "--system" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
                "--bbox",
                "13.5,50.0,14.5,50.4",
                "--bbox-crs",
                "EPSG:4326",
                "--system",
                "2000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        mock_cz.assert_not_called()
        used_bbox = mock_find.call_args.args[0]
        assert (used_bbox.min_x, used_bbox.max_x) == (13.5, 14.5)

    def test_explicit_cz_with_system_still_rejected(self, tmp_path, capsys):
        """Explicit --country cz: validation unchanged (nothing to resolve)."""
        result = main(
            self._BORDER + ["--country", "cz", "--system", "2000", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--system dotyczy tylko PL" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_border_bbox_with_target_crs_runs_both_countries(self, mock_cz, tmp_path):
        """ADR-027/erratum to ADR-023: target-crs is no longer a Czech flag -
        the border area in one command gives two cutouts with a shared
        parent_request."""
        mock_cz.return_value = 0
        with patch(
            "kartograf.cli.download_cmd._download_pl_bbox", return_value=0
        ) as mock_pl:
            result = main(
                self._BORDER
                + [
                    "--target-crs",
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
        assert parent == mock_pl.call_args.args[2]
        # the CZ part goes in the RESULT CRS (cz_crs = target), not in Krovak
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:2180"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_product_nmpt_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """NMPT for CZ is stage 2: auto resolves the country to PL."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "M-34-86-D-d-4-3")

        result = main(self._BORDER + ["--product", "nmpt", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert "--country auto -> pl" in err
        assert "--product nmpt" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_product_orto_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Orthophoto for CZ is stage 2: auto resolves the country to PL."""
        self._pl_mocks(mock_manager_class, mock_find, tmp_path, "M-34-86-D-d-4-3")

        result = main(self._BORDER + ["--product", "orto", "-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        assert "--product orto" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_resolution_5m_resolvable_for_both(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """5m exists on both sides — auto-split goes ahead."""
        mock_find.return_value = ["M-34-86-D"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0
        result = main(self._BORDER + ["--resolution", "5m", "-o", str(tmp_path)])
        assert result == 0
        assert mock_cz.called

    def test_bbox_outside_known_countries(self, tmp_path, capsys):
        result = main(
            [
                "download",
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

    def test_laz_bbox_border_auto_rejected(self, tmp_path, capsys):
        """LAZ (PL-only) + a bbox crossing CZ + auto => an error with a hint,
        instead of quietly downloading only the PL part (spec 5.7: no silent
        skipping of a country)."""
        result = main(
            [
                "download",
                "--bbox",
                "18.4,49.55,18.8,49.75",
                "--bbox-crs",
                "EPSG:4326",
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        assert "--country pl" in capsys.readouterr().err

    def test_laz_godlo_untouched_by_guard(self, tmp_path, capsys):
        """The LAZ sheet code mode does not go through the cross-border guard.

        Sheet code M-34-86-D-d-4-3 lies at the CZ border (inside the CZ envelope),
        so in area mode the guard would fire - the sheet code's country is however
        unambiguous.
        """
        from kartograf.providers.pl import gugik_laz

        with patch.object(gugik_laz, "GugikLazProvider") as provider_cls:
            provider_cls.return_value.select_tiles.return_value = _selection([])
            result = main(
                ["download", "M-34-86-D-d-4-3", "--product", "laz", "-o", str(tmp_path)]
            )

        assert result == 1
        err = capsys.readouterr().err
        assert "--country pl" not in err
        assert "No LAZ tiles" in err

    @patch("kartograf.providers.cuzk.dmr.bbox_to_crs")
    def test_cz_bbox_transform_error_returns_1_with_remedy(
        self, mock_to_crs, tmp_path, capsys
    ):
        """TransformError in CZ bbox normalisation = a CLI message, not a traceback."""
        from kartograf.transform.crs import TransformUnavailableError

        mock_to_crs.side_effect = TransformUnavailableError(
            "brak bezpiecznej operacji", remedy="podaj --target-crs EPSG:5514"
        )
        result = main(
            [
                "download",
                "--bbox",
                "419000,230000,426000,237000",
                "--country",
                "cz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert result == 1
        err = capsys.readouterr().err
        assert "brak bezpiecznej operacji" in err
        assert "Remedium" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd._country_bbox")
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
                "download",
                "--bbox",
                "18.60,49.752,18.65,49.768",
                "--bbox-crs",
                "EPSG:4326",
                "-o",
                str(tmp_path / "out"),
                "-q",
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
    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_geometry_border_splits(
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
        # envelope in 2180 intersecting both countries (Cieszyn area:
        # 18.513-18.792E / 49.666-49.847N — inside the CZ and PL envelopes)
        mock_overall.return_value = BBox(
            465000.0, 200000.0, 485000.0, 220000.0, "EPSG:2180"
        )
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = _sheet_list_manager(tmp_path / "x.asc")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["bbox"] == [465000.0, 200000.0, 485000.0, 220000.0]
        assert parent["bbox_crs"] == "EPSG:2180"
        assert parent["countries"] == ["CZ", "PL"]
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:5514"
        assert mock_manager_class.call_args.kwargs["sidecar_extra"] == {
            "parent_request": parent
        }

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        mock_cz.assert_not_called()
        parent = mock_manager_class.call_args.kwargs["sidecar_extra"]["parent_request"]
        assert parent["countries"] == ["PL"]

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        mock_cz.assert_not_called()
        err = capsys.readouterr().err
        assert "Info: --country auto:" not in err
        assert "poza zasiegiem PL/CZ" not in err

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.cli.download_cmd._cmd_download_cz", return_value=0)
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_geometry_auto_informs_only_clipped_cz(
        self, manager_class, find, overall, cz, read_crs, tmp_path, capsys
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        overall.return_value = BBox(465000.0, 200000.0, 505000.0, 220000.0, "EPSG:2180")
        find.return_value = ["M-34-86-D-d-4-3"]
        manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")

        assert (
            main(
                [
                    "download",
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_explicit_cz_gets_parent_request(self, mock_cz, tmp_path):
        """Explicit --country cz: parent_request from the request-CRS envelope."""
        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0

        result = main(
            [
                "download",
                "--geometry",
                str(shp),
                "--country",
                "cz",
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

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_geometry_in_task_crs_skips_transform(self, mock_run_cz, tmp_path):
        """File already in EPSG:5514: the envelope goes to CUZK bit for bit, no step."""
        shp = _write_krovak_shp(tmp_path)
        mock_run_cz.return_value = 0

        result = main(
            [
                "download",
                "--geometry",
                str(shp),
                "--country",
                "cz",
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

    @patch("kartograf.cli.download_cmd._run_cz")
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
                "download",
                "--geometry",
                str(shp),
                "--country",
                "cz",
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
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 1
        assert "kraju" in capsys.readouterr().err


class TestPublicApiCz:
    """Public API exports for the CZ modules (task 18)."""

    def test_cz_exports_available(self):
        from kartograf import CuzkDmrProvider, ParserTM33, create_dmr_provider

        assert ParserTM33("302_5550").get_bbox().crs == "EPSG:3045"
        assert callable(create_dmr_provider)
        assert CuzkDmrProvider.__name__ == "CuzkDmrProvider"

    def test_version_bumped(self):
        from kartograf import __version__

        assert __version__ == "0.7.1-dev"


class _PartialSheetProvider(_SheetProvider):
    """A provider with origin: sheets with ``partial`` suffixes have
    ``full_sheet=False`` (the newest campaign is partial, E2E-B C12-a/C14-b)."""

    descriptor_key = "pl.gugik.nmt_1m"

    def __init__(self, partial: tuple[str, ...]):
        super().__init__({})
        self.partial = partial

    def source_info(self, godlo):
        return {
            "url": f"https://opendata.geoportal.gov.pl/NMT/1/1_{godlo}.asc",
            "layer": "SkorowidzeNMT2025",
            "acquisition_date": "2025-10-21",
            "full_sheet": not godlo.endswith(self.partial),
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
                "kartograf.cli.download_cmd._create_provider_and_storage",
                return_value=(provider, storage),
            ),
            patch(
                "kartograf.cli.download_cmd.find_sheets_for_bbox",
                return_value=list(TestSheetListExitCode._GODLA),
            ),
        ):
            return main([*argv, "-o", str(tmp_path)])

    def test_single_godlo_partial_sheet_warns(self, tmp_path, capsys):
        rc = self._run(tmp_path, ("-1",), ["download", "N-34-130-D-d-2-1"])

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "niepelna" in err and "N-34-130-D-d-2-1" in err
        (sidecar,) = tmp_path.rglob("*.meta.json")
        meta = json.loads(sidecar.read_text("utf-8"))
        assert meta["extra"]["source"]["full_sheet"] is False

    def test_single_godlo_full_sheet_is_silent(self, tmp_path, capsys):
        rc = self._run(tmp_path, ("-9",), ["download", "N-34-130-D-d-2-1"])

        assert rc == 0
        assert "niepelna" not in capsys.readouterr().err

    def test_sheet_list_names_only_partial_sheets(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            ("-2", "-4"),
            ["download", "--bbox", "630000,480000,637000,487000"],
        )

        assert rc == 0
        warning = next(
            line for line in capsys.readouterr().err.splitlines() if "niepelna" in line
        )
        assert "Warning:" in warning and "2 arkuszy" in warning
        assert "N-34-130-D-d-2-2" in warning and "N-34-130-D-d-2-4" in warning
        assert "N-34-130-D-d-2-1" not in warning

    def test_hierarchy_partial_sheet_warns(self, tmp_path, capsys):
        rc = self._run(tmp_path, ("-3",), ["download", "N-34-130-D-d-2"])

        assert rc == 0
        err = capsys.readouterr().err
        assert "niepelna" in err and "N-34-130-D-d-2-3" in err


class TestSingleGodloSkipMessage:
    """E15 (E2E-B C17): skipping one sheet code says skip, not ``Downloaded to``."""

    @staticmethod
    def _run(tmp_path, provider, *extra):
        from kartograf.download.storage import FileStorage

        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        with patch(
            "kartograf.cli.download_cmd._create_provider_and_storage",
            return_value=(provider, storage),
        ):
            return main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), *extra])

    def test_second_run_reports_skip(self, tmp_path, capsys):
        provider = _SheetProvider({})
        assert self._run(tmp_path, provider) == 0
        first = capsys.readouterr().out
        assert "Downloaded to" in first

        assert self._run(tmp_path, provider) == 0

        out = capsys.readouterr().out
        assert provider.calls == ["N-34-130-D-d-2-4"]  # the second run without network
        assert "Downloaded to" not in out
        assert "Skipped N-34-130-D-d-2-4 - already exists at" in out

    def test_force_reports_download(self, tmp_path, capsys):
        provider = _SheetProvider({})
        self._run(tmp_path, provider)
        capsys.readouterr()

        assert self._run(tmp_path, provider, "--force") == 0

        assert "Downloaded to" in capsys.readouterr().out
        assert len(provider.calls) == 2


class _CachingSheetProvider(_SheetProvider):
    """``_SheetProvider`` that reads/writes the CLI cache like GugikProvider."""

    def __init__(self, cache):
        super().__init__({})
        self.cache = cache

    def download(self, godlo, path, timeout=30):
        if self.cache.get_record("nmt", "1m", "EVRF2007", godlo) is None:
            self.cache.set_record("nmt", "1m", "EVRF2007", godlo, {"godlo": godlo})
        return super().download(godlo, path, timeout)


class TestUnreadableMetadataCache:
    """An unreadable ``.kartograf_cache.db`` in the cwd does not block downloads.

    Before the fix every sheet of a list failed with ``file is not a
    database`` (code 1, nothing downloaded) and a single sheet code ended with
    ``Error: DatabaseError`` from the ``main`` barrier.
    """

    _GODLA = [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]

    @staticmethod
    def _broken_cache() -> Path:
        db = Path.cwd() / ".kartograf_cache.db"
        db.write_bytes(b"to nie jest baza SQLite\n" * 200)
        return db

    @staticmethod
    def _run(tmp_path, argv, godla=()):
        from kartograf.download.storage import FileStorage

        out = tmp_path / "out"
        storage = FileStorage(out, resolution="1m", vertical_crs="EVRF2007")
        providers = []

        def create(*_args, cache=None, **_kwargs):
            providers.append(_CachingSheetProvider(cache))
            return providers[-1], storage

        with (
            patch(
                "kartograf.cli.download_cmd._create_provider_and_storage",
                side_effect=create,
            ),
            patch(
                "kartograf.cli.download_cmd.find_sheets_for_bbox",
                return_value=list(godla),
            ),
        ):
            rc = main([*argv, "-o", str(out)])
        files = sorted(p.name for p in out.rglob("*.asc"))
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
        argv = ["download", "--bbox", "630000,480000,637000,487000"]
        argv += ["--country", "pl", "--workers", workers]
        if quiet:
            argv.append("-q")

        rc, providers, files = self._run(tmp_path, argv, godla=self._GODLA)

        assert rc == 0
        assert files == [f"{g}.asc" for g in self._GODLA]
        assert sorted(providers[0].calls) == self._GODLA
        err = capsys.readouterr().err
        assert "Error:" not in err
        assert "file is not a database" in err
        warnings = self._cache_warnings(err)
        assert warnings == [
            f"Warning: cache metadanych nieczytelny ({db}): file is not a "
            "database — praca bez cache; uzyj `kartograf cache clear` albo "
            "usun plik"
        ]
        assert db.read_bytes().startswith(b"to nie jest baza")  # untouched

    def test_single_godlo_downloads_with_warning(self, tmp_path, capsys):
        self._broken_cache()

        rc, providers, files = self._run(tmp_path, ["download", "N-34-130-D-d-2-4"])

        assert rc == 0
        assert files == ["N-34-130-D-d-2-4.asc"]
        assert providers[0].calls == ["N-34-130-D-d-2-4"]
        captured = capsys.readouterr()
        assert "Downloaded to" in captured.out
        assert "Error:" not in captured.err
        assert len(self._cache_warnings(captured.err)) == 1
        assert captured.err.startswith("Warning: cache metadanych nieczytelny (")

    def test_warning_once_per_command_not_per_process(self, tmp_path, capsys):
        """Every command reports the broken cache again (dedup reset)."""
        self._broken_cache()
        argv = ["download", "N-34-130-D-d-2-4", "--force"]

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

        instance.download.side_effect = fake_download
        with patch(
            "kartograf.providers.pl.gugik_laz.GugikLazProvider", return_value=instance
        ):
            rc = main(
                ["download", "M-34-27-B-b-2-1", "--product", "laz"]
                + list(extra)
                + ["-o", str(tmp_path), "-q"]
            )
        (sidecar,) = tmp_path.rglob("*.meta.json")
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

    GODLO = "7.125.11.19"
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
        import requests

        from tests.conftest import gfi_record, render_gfi_body

        body = render_gfi_body(
            [
                gfi_record(
                    self.GODLO,
                    uklad="PL-2000:S7",
                    aktualnosc="2023-03-17",
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
                "kartograf.cli.download_cmd.find_sheets_for_bbox",
                return_value=[self.GODLO],
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

    def test_single_godlo_warns_with_prefix(self, tmp_path, capsys):
        rc = self._run(tmp_path, ["download", self.GODLO])

        assert rc == 0
        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.GODLO in warning and "EPSG:2178" in warning

    def test_skip_repeats_warning(self, tmp_path, capsys):
        assert self._run(tmp_path, ["download", self.GODLO]) == 0
        capsys.readouterr()

        assert self._run(tmp_path, ["download", self.GODLO]) == 0

        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.GODLO in warning

    def test_sheet_list_warns(self, tmp_path, capsys):
        rc = self._run(
            tmp_path,
            [
                "download",
                "--bbox",
                "7564000,5530000,7566000,5532000",
                "--bbox-crs",
                "EPSG:2178",
                "--system",
                "2000",
                "--country",
                "pl",
            ],
        )

        assert rc == 0
        (warning,) = self._warnings(capsys.readouterr().err)
        assert self.GODLO in warning and "EPSG:2178" in warning

    def test_file_in_zone_crs_is_silent(self, tmp_path, capsys):
        head = self.FIXTURE.read_bytes().replace(b"567975.95", b"7567975.95", 1)
        assert head != self.FIXTURE.read_bytes()

        rc = self._run(tmp_path, ["download", self.GODLO], raw=head)

        assert rc == 0
        assert "innym ukladzie" not in capsys.readouterr().err


# --- ADR-030 T8: --campaigns / --min-year w CLI ---------------------------

_CAMPAIGN_INFO = "Info: --campaigns/--min-year dotycza tylko czesci PL"
_CZ_CAMPAIGN_ERROR = (
    "Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year dotycza tylko PL"
)
# PL/CZ border strip (both rectangular envelopes, ADR-023)
_BORDER_BBOX = ["--bbox", "18.4,49.55,18.8,49.75", "--bbox-crs", "EPSG:4326"]
# Ceske Budejovice: _countries_for_bbox == ("CZ",)
_CZ_ONLY_BBOX = ["--bbox", "14.45,48.95,14.50,49.00", "--bbox-crs", "EPSG:4326"]
_PL_BBOX_2180 = ["--bbox", "530000,382000,533000,386000", "--country", "pl"]


class TestCampaignOptions:
    """``--campaigns {newest,all}`` i ``--min-year`` (ADR-030, plan 1.8)."""

    def test_parser_campaigns_default_newest_and_min_year(self):
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4"])
        assert args.campaigns == "newest"
        assert args.min_year is None

        args = parser.parse_args(
            ["download", "N-34-130-D-d-2-4", "--campaigns", "all", "--min-year", "2024"]
        )
        assert args.campaigns == "all"
        assert args.min_year == 2024

        with pytest.raises(SystemExit):
            parser.parse_args(["download", "X", "--campaigns", "coverage"])

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_campaigns_passed_to_manager_godlo_and_list(
        self, mock_manager_class, mock_find, tmp_path
    ):
        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")
        opts = ["--campaigns", "all", "--min-year", "2024", "-o", str(tmp_path), "-q"]

        assert main(["download", "N-34-130-D-d-2-4", *opts]) == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["campaigns"] == "all"
        assert kwargs["min_year"] == 2024

        mock_manager_class.reset_mock()
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "a.asc")
        assert main(["download", *_PL_BBOX_2180, *opts]) == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["campaigns"] == "all"
        assert kwargs["min_year"] == 2024

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_min_year_out_of_range_error_no_network(
        self, mock_manager_class, capsys, tmp_path
    ):
        rc = main(
            ["download", "N-34-130-D-d-2-4", "--min-year", "1800", "-o", str(tmp_path)]
        )
        assert rc == 1
        assert "Error:" in capsys.readouterr().err
        mock_manager_class.assert_not_called()

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_year_and_min_year_exclusive(self, mock_provider_cls, capsys, tmp_path):
        rc = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--product",
                "laz",
                "--year",
                "2024",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert (
            "Error: --min-year i --year wykluczaja sie (LAZ)" in capsys.readouterr().err
        )
        mock_provider_cls.assert_not_called()

    @patch("kartograf.download.laz.run_laz_download")
    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_campaign_opts_forwarded(self, mock_provider_cls, mock_run, tmp_path):
        instance = Mock()
        instance.select_tiles.return_value = Mock(tiles=[Mock()], superseded=[])
        mock_provider_cls.return_value = instance
        mock_run.return_value = Mock(downloaded=[], skipped=[], failed=[])

        rc = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--product",
                "laz",
                "--campaigns",
                "all",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
        assert rc == 0
        kwargs = instance.select_tiles.call_args.kwargs
        assert kwargs["campaigns"] == "all" and kwargs["min_year"] == 2020
        kwargs = mock_run.call_args.kwargs
        assert kwargs["campaigns"] == "all" and kwargs["min_year"] == 2020

    @patch("kartograf.download.cutout.prepare_pl_cutout")
    def test_target_crs_with_campaigns_all_rejected_before_network(
        self, mock_prepare, capsys, tmp_path
    ):
        rc = main(
            [
                "download",
                *_PL_BBOX_2180,
                "--target-crs",
                "EPSG:2180",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --campaigns all nie dziala z --target-crs" in err
        assert "0.7.1" in err
        mock_prepare.assert_not_called()

    @patch("kartograf.download.cutout.prepare_pl_cutout")
    def test_target_crs_with_min_year_rejected(self, mock_prepare, capsys, tmp_path):
        rc = main(
            [
                "download",
                *_PL_BBOX_2180,
                "--target-crs",
                "EPSG:2180",
                "--min-year",
                "2020",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert (
            "Error: --min-year nie dziala z --target-crs — nazwa wycinka nie "
            "niesie granicy roku"
        ) in err
        mock_prepare.assert_not_called()

    @patch("kartograf.download.cutout.prepare_pl_cutout")
    @patch("kartograf.cli.download_cmd._run_cz")
    def test_target_crs_with_all_cross_border_rejected_before_cz(
        self, mock_run_cz, mock_prepare, capsys, tmp_path
    ):
        """Under auto CZ goes before PL — the guard must fire before CZ."""
        mock_run_cz.return_value = 0
        rc = main(
            [
                "download",
                *_BORDER_BBOX,
                "--target-crs",
                "EPSG:2180",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "0.7.1" in capsys.readouterr().err
        mock_run_cz.assert_not_called()
        mock_prepare.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_cz_godlo_explicit_country_with_all_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        rc = main(
            [
                "download",
                "302_5550",
                "--country",
                "cz",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_cz_godlo_auto_with_all_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(["download", "302_5550", "--campaigns", "all", "-o", str(tmp_path)])
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_cz_godlo_auto_with_min_year_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(["download", "302_5550", "--min-year", "2020", "-o", str(tmp_path)])
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_cz_sm5_godlo_auto_with_all_is_error(self, mock_run_cz, capsys, tmp_path):
        rc = main(["download", "CTES96", "--campaigns", "all", "-o", str(tmp_path)])
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_area_explicit_cz_with_all_error(self, mock_run_cz, capsys, tmp_path):
        mock_run_cz.return_value = 0
        rc = main(
            [
                "download",
                *_BORDER_BBOX,
                "--country",
                "cz",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert _CZ_CAMPAIGN_ERROR in capsys.readouterr().err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._resolve_cz_geometry_bbox")
    @patch("kartograf.cli.download_cmd._run_cz")
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
                "download",
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

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_area_auto_entirely_cz_with_all_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        mock_run_cz.return_value = 0
        rc = main(
            ["download", *_CZ_ONLY_BBOX, "--campaigns", "all", "-o", str(tmp_path)]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._run_cz")
    def test_area_auto_entirely_cz_with_min_year_is_error(
        self, mock_run_cz, capsys, tmp_path
    ):
        mock_run_cz.return_value = 0
        rc = main(
            ["download", *_CZ_ONLY_BBOX, "--min-year", "2020", "-o", str(tmp_path)]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert _CZ_CAMPAIGN_ERROR in err
        assert "Info:" not in err
        mock_run_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_area_auto_cross_border_with_all_info_once(
        self, mock_manager_class, mock_find, mock_cz, capsys, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")
        mock_cz.return_value = 0

        rc = main(
            ["download", *_BORDER_BBOX, "--campaigns", "all", "-o", str(tmp_path), "-q"]
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert err.count(_CAMPAIGN_INFO) == 1
        assert "--country auto -> pl" not in err
        assert mock_manager_class.call_args.kwargs["campaigns"] == "all"
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_area_auto_pl_only_flag_plus_all_no_campaign_info(
        self, mock_manager_class, mock_find, mock_cz, capsys, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.tif")

        rc = main(
            [
                "download",
                *_BORDER_BBOX,
                "--product",
                "orto",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "Info: --country auto -> pl (--product orto dotyczy tylko PL)" in err
        assert _CAMPAIGN_INFO not in err
        mock_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_skip_message_from_last_sheet(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch("N-34-130-D-d-2-4", path, skipped=True)
        mock_manager_class.return_value = manager

        assert main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert f"Skipped N-34-130-D-d-2-4 - already exists at {path}" in out
        assert "Downloaded to" not in out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_mock_manager_reports_downloaded(
        self, mock_manager_class, capsys, tmp_path
    ):
        """I-1: a Mock() fake has ``last_sheet.skipped`` = Mock (truthy)."""
        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")

        assert main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "Downloaded to" in out
        assert "Skipped" not in out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_existing_link_but_new_campaign_reports_downloaded(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        target = tmp_path / "N-34-130-D-d-2-4.asc"
        target.write_bytes(b"old link target")
        manager = _mock_manager(target)
        manager.storage.get_path.return_value = target
        manager.last_sheet = SheetFetch(
            "N-34-130-D-d-2-4",
            target,
            skipped=False,
            downloaded=(tmp_path / "kampanie" / "new.asc",),
            link="hardlink",
        )
        mock_manager_class.return_value = manager

        assert main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert f"Downloaded to {target}" in out
        assert "Skipped" not in out

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_copy_fallback_warning_in_list_mode(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        mock_find.return_value = ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
        manager = _sheet_list_manager(tmp_path / "a.asc", tmp_path / "b.asc")
        manager.last_result.copied = ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
        mock_manager_class.return_value = manager

        rc = main(["download", *_PL_BBOX_2180, "-o", str(tmp_path), "-q"])

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: hardlink niedostepny na tym systemie plikow — sciezka "
            "standardowa jest KOPIA najnowszej kampanii dla 2 arkuszy "
            "(N-34-130-D-d-2-4, N-34-130-D-d-2-3) (extra.link=copy)"
        ) in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_copy_fallback_warning_single_sheet(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch(
            "N-34-130-D-d-2-4", path, skipped=False, link="copy"
        )
        mock_manager_class.return_value = manager

        assert main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"]) == 0
        assert "(extra.link=copy)" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_summary_counts_campaign_files(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        mock_find.return_value = ["A", "B", "C"]
        a, b, c = (tmp_path / f"{n}.asc" for n in "abc")
        manager = _sheet_list_manager(a, b, c, skipped=["C"])
        manager.last_result.succeeded = [a, b]
        manager.last_result.campaign_files = {
            "A": (tmp_path / "k1" / "a.asc", tmp_path / "k2" / "a.asc"),
            "B": (tmp_path / "k1" / "b.asc",),
            "C": (tmp_path / "k1" / "c.asc", tmp_path / "k2" / "c.asc"),
        }
        # a skipped sheet = all its campaigns already local (like the manager)
        manager.last_result.reused_campaign_files = {
            "C": manager.last_result.campaign_files["C"]
        }
        mock_manager_class.return_value = manager

        rc = main(
            ["download", *_PL_BBOX_2180, "--campaigns", "all", "-o", str(tmp_path)]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert (
            f"Downloaded 3 campaign files for 3 sheets to {tmp_path} "
            "(2 already existed)"
        ) in out
        assert "Downloaded 2 files" not in out

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_summary_partially_new_sheets(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        """Fix 1: 10 sheets x (1 new + 3 local) -> 10 downloaded, 30 local."""
        godla = [f"N-34-130-D-d-2-{i}" for i in range(10)]
        mock_find.return_value = godla
        paths = [tmp_path / f"{g}.asc" for g in godla]
        manager = _sheet_list_manager(*paths)
        files = {
            g: tuple(tmp_path / f"k{k}" / f"{g}.asc" for k in range(4)) for g in godla
        }
        manager.last_result.campaign_files = files
        manager.last_result.reused_campaign_files = {g: f[1:] for g, f in files.items()}
        mock_manager_class.return_value = manager

        rc = main(
            ["download", *_PL_BBOX_2180, "--campaigns", "all", "-o", str(tmp_path)]
        )

        assert rc == 0
        assert (
            f"Downloaded 10 campaign files for 10 sheets to {tmp_path} "
            "(30 already existed)"
        ) in capsys.readouterr().out

    @patch("kartograf.download.cutout.prepare_pl_cutout")
    @patch("kartograf.cli.download_cmd._run_cz")
    def test_target_crs_with_all_cross_border_no_info_before_error(
        self, mock_run_cz, mock_prepare, capsys, tmp_path
    ):
        """Fix 2: the --target-crs guard comes before the campaign Info."""
        rc = main(
            [
                "download",
                *_BORDER_BBOX,
                "--target-crs",
                "EPSG:2180",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "0.7.1" in err
        assert "Info:" not in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_godlo_target_crs_with_all_gets_godlo_error(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Fix 3: the more general sheet code guard (--target-crs with a code) wins."""
        rc = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--target-crs",
                "EPSG:2180",
                "--campaigns",
                "all",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --target-crs dziala tylko z --bbox/--geometry" in err
        assert "0.7.1" not in err
        mock_manager_class.assert_not_called()

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_min_year_error_names_cli_flag(self, mock_manager_class, capsys, tmp_path):
        """Fix 4: the CLI says --min-year, not min_year (a library parameter)."""
        rc = main(
            ["download", "N-34-130-D-d-2-4", "--min-year", "1800", "-o", str(tmp_path)]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: --min-year musi byc" in err and "1800" in err
        assert " min_year" not in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_campaigns_passed_to_manager_hierarchy(self, mock_manager_class, tmp_path):
        """Fix 5: the hierarchy path (--scale)."""
        manager = Mock()
        manager.download_hierarchy.return_value = [tmp_path / "a.asc"]
        manager.count_sheets.return_value = 1
        manager.last_result = DownloadResult(succeeded=[tmp_path / "a.asc"])
        mock_manager_class.return_value = manager

        rc = main(
            [
                "download",
                "N-34-130-D",
                "--scale",
                "1:10000",
                "--campaigns",
                "all",
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
        assert kwargs["campaigns"] == "all" and kwargs["min_year"] == 2021

    @patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
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
                "download",
                "--geometry",
                str(geometry_file),
                "--country",
                "pl",
                "--campaigns",
                "all",
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
        assert kwargs["campaigns"] == "all" and kwargs["min_year"] == 2022

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_newest_min_year_single_sheet_no_coverage_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.exceptions import NoCoverageError

        manager = _mock_manager(None)
        manager.download_sheet.side_effect = NoCoverageError(
            "N-34-130-D-d-2-4: najnowsza kampania 2019-05-21 starsza niz "
            "--min-year 2024",
            godlo="N-34-130-D-d-2-4",
        )
        mock_manager_class.return_value = manager

        rc = main(
            ["download", "N-34-130-D-d-2-4", "--min-year", "2024", "-o", str(tmp_path)]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error:" in err and "2019-05-21" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_quiet_does_not_hide_campaign_info(
        self, mock_manager_class, mock_find, mock_cz, capsys, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager_class.return_value = _sheet_list_manager(tmp_path / "x.asc")
        mock_cz.return_value = 0

        main(
            ["download", *_BORDER_BBOX, "--campaigns", "all", "-o", str(tmp_path), "-q"]
        )

        captured = capsys.readouterr()
        assert _CAMPAIGN_INFO in captured.err
        assert _CAMPAIGN_INFO not in captured.out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_format_error_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        manager = _mock_manager(None)
        manager.download_sheet.side_effect = DownloadError(
            "N-34-130-D-d-2-4: nie pobrano 1 z 1 kampanii (2020-01-01_123: "
            "format 'X' nieobslugiwany)"
        )
        mock_manager_class.return_value = manager

        rc = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error:" in err and "format 'X' nieobslugiwany" in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_namespace_without_new_attrs_defaults(self, mock_manager_class, tmp_path):
        from kartograf.cli.download_cmd import cmd_download

        mock_manager_class.return_value = _mock_manager(tmp_path / "a.asc")
        args = argparse.Namespace(
            godlo="N-34-130-D-d-2-4",
            bbox=None,
            output=str(tmp_path),
            force=False,
            quiet=True,
            scale=None,
            vertical_crs=None,
            resolution=None,
            target_crs=None,
            system=None,
        )
        assert cmd_download(args) == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["campaigns"] == "newest"
        assert kwargs["min_year"] is None

    # -------------------------------------------------------------------------
    # I-1: newest on an index failure -> local campaign + Warning
    # -------------------------------------------------------------------------

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_unverified_local_campaign_warns_single_sheet(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch(
            "N-34-130-D-d-2-4",
            path,
            skipped=True,
            reused=(tmp_path / "kampanie" / "a.asc",),
            link="hardlink",
            unverified="pobranie nieudane po 3 probach: HTTP 503",
        )
        mock_manager_class.return_value = manager

        rc = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: N-34-130-D-d-2-4: skorowidz GUGiK niedostepny — uzyto "
            "lokalnej kampanii bez sprawdzenia nowszej "
            "(pobranie nieudane po 3 probach: HTTP 503)"
        ) in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_verified_single_sheet_has_no_unverified_warning(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch("N-34-130-D-d-2-4", path, skipped=True)
        mock_manager_class.return_value = manager

        assert main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"]) == 0
        assert "skorowidz GUGiK niedostepny" not in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_unverified_local_campaign_warns_in_list_mode(
        self, mock_manager_class, mock_find, capsys, tmp_path
    ):
        godla = ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
        mock_find.return_value = godla
        manager = _sheet_list_manager(
            tmp_path / "a.asc", tmp_path / "b.asc", skipped=godla
        )
        manager.last_result.succeeded = []
        manager.last_result.unverified = {g: "HTTP 503" for g in godla}
        mock_manager_class.return_value = manager

        rc = main(["download", *_PL_BBOX_2180, "-o", str(tmp_path), "-q"])

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: skorowidz GUGiK niedostepny — dla 2 arkuszy uzyto lokalnej "
            "kampanii bez sprawdzenia nowszej (N-34-130-D-d-2-4, N-34-130-D-d-2-3) "
            "(HTTP 503)"
        ) in err

    def test_unverified_end_to_end_with_real_manager(self, capsys, tmp_path):
        """A real ``DownloadManager`` + a campaign provider without network: the second
        run on an index failure = exit code 0 and ``Warning:`` despite ``-q``."""
        from tests.test_manager_campaigns import C14, FakeCampaignProvider

        fake = FakeCampaignProvider(C14)
        godlo = "N-34-139-C-a-3-1"
        out = tmp_path / "out"
        argv = ["download", godlo, "-o", str(out), "-q"]
        with patch(
            "kartograf.cli.download_cmd._create_provider_and_storage",
            return_value=(fake, None),
        ):
            assert main(argv) == 0
            fake.resolve_error = DownloadError(
                "GetFeatureInfo: pobranie nieudane po 3 probach", status_code=503
            )
            capsys.readouterr()
            assert main(argv) == 0
            err = capsys.readouterr().err
            assert f"Warning: {godlo}: skorowidz GUGiK niedostepny" in err

            fake.resolve_error = DownloadError("raport wyjatku OGC")
            assert main(argv) == 1
            assert "Error:" in capsys.readouterr().err

    # -------------------------------------------------------------------------
    # M-1: single sheet code with --campaigns all — summary line as for a list
    # -------------------------------------------------------------------------

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_single_sheet_summary_counts_campaign_files(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch(
            "N-34-130-D-d-2-4",
            path,
            skipped=False,
            downloaded=(tmp_path / "k1" / "a.asc", tmp_path / "k2" / "a.asc"),
            reused=(tmp_path / "k3" / "a.asc",),
            link="hardlink",
        )
        mock_manager_class.return_value = manager

        rc = main(
            ["download", "N-34-130-D-d-2-4", "--campaigns", "all", "-o", str(tmp_path)]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert (
            f"Downloaded 2 campaign files for 1 sheets to {tmp_path} "
            "(1 already existed)"
        ) in out
        assert "Downloaded to" not in out
        assert "Skipped" not in out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_single_sheet_all_local_summary(
        self, mock_manager_class, capsys, tmp_path
    ):
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)
        manager.last_sheet = SheetFetch(
            "N-34-130-D-d-2-4",
            path,
            skipped=True,
            reused=(tmp_path / "k1" / "a.asc", tmp_path / "k2" / "a.asc"),
            link="hardlink",
        )
        mock_manager_class.return_value = manager

        rc = main(
            ["download", "N-34-130-D-d-2-4", "--campaigns", "all", "-o", str(tmp_path)]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert (
            f"Downloaded 0 campaign files for 1 sheets to {tmp_path} "
            "(2 already existed)"
        ) in out


class TestListMessagesUx:
    """O-3 / O-6 / O-7: CLI messages on no data, skip and download."""

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_skip_has_no_downloading_line(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-3: Skipped is not preceded by 'Downloading ...'."""
        from kartograf.download.manager import SheetFetch

        path = tmp_path / "a.asc"
        manager = _mock_manager(path)  # the mock does not call on_download (skip)
        manager.last_sheet = SheetFetch("N-34-130-D-d-2-4", path, skipped=True)
        mock_manager_class.return_value = manager

        rc = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Skipped" in out
        assert "Downloading" not in out

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_error_has_no_downloading_line(
        self, mock_manager_class, capsys, tmp_path
    ):
        """O-3: Error (no record) is not preceded by 'Downloading ...'."""
        manager = _mock_manager(tmp_path / "a.asc")
        manager.download_sheet.side_effect = DownloadError("brak")
        mock_manager_class.return_value = manager

        rc = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "Error: brak" in captured.err
        assert "Downloading" not in captured.out

    @staticmethod
    def _list_manager(result):
        manager = Mock()
        manager.last_result = result
        manager.download_sheets.return_value = []
        manager.download_sheet.return_value = []
        return manager

    @staticmethod
    def _real_error(godlo):
        """A real index ``no_coverage_error`` (PL-2000 descendant)."""
        from kartograf.providers.pl.skorowidz import (
            SkorowidzRecord,
            coverage_hints,
            no_coverage_error,
        )

        parser = SheetParser(godlo)
        child = SkorowidzRecord(
            url="https://example.invalid/x.asc",
            godlo=f"{godlo}.01",
            aktualnosc="2024-01-01",
            dt_pzgik=None,
            layer="L",
            uklad="2000",
            zone=7,
            resolution_m=1.0,
            full_sheet=True,
            raw={},
        )
        return no_coverage_error(
            parser, f"Brak NMT dla {godlo}", coverage_hints(parser, [child])
        )

    _BBOX_ARGS = (
        "download",
        "--bbox",
        "419000,230000,426000,237000",
        "--system",
        "2000",
        "--country",
        "pl",
    )

    @patch("kartograf.cli.download_cmd.DownloadManager")
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
            "Info: Dostepny potomek 7.173.21.01 — uzyj --scale 1:2000",
            "Info: Dostepny potomek 7.173.22.01 — uzyj --scale 1:2000",
        ]
        assert "Downloaded 0" not in captured.out

    @staticmethod
    def _info_lines(hints_by_godlo, capsys, tmp_path):
        result = DownloadResult(
            failed=list(hints_by_godlo),
            no_coverage=list(hints_by_godlo),
            no_coverage_hints=hints_by_godlo,
        )
        with patch("kartograf.cli.download_cmd.DownloadManager") as cls:
            cls.return_value = TestListMessagesUx._list_manager(result)
            main([*TestListMessagesUx._BBOX_ARGS, "-o", str(tmp_path)])
        err = capsys.readouterr().err
        return [x for x in err.splitlines() if x.startswith("Info:")]

    def test_pl1992_hints_with_different_godlo_are_all_kept(self, capsys, tmp_path):
        """Different sheet codes in hints (PL-1992) are not merged into one."""
        h = "Skorowidz ma ten obszar w PL-1992: {g} (1:10000) — uzyj tego godla"
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

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_message_with_dot_but_no_hints_prints_no_info(
        self, mock_manager_class, capsys, tmp_path
    ):
        """A message with ". " without `hints` gives no false hint."""
        result = DownloadResult(failed=["A"], no_coverage=["A"])
        mock_manager_class.return_value = self._list_manager(result)

        rc = main([*self._BBOX_ARGS, "-o", str(tmp_path)])

        assert rc == 1
        assert "Info:" not in capsys.readouterr().err

    @pytest.mark.parametrize("campaigns", ["newest", "all"])
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_no_coverage_quiet_keeps_stderr_no_summary(
        self, mock_manager_class, campaigns, capsys, tmp_path
    ):
        """O-7 on both paths and with -q: Error/Info on stderr, no summary."""
        err = self._real_error("7.173.21")
        result = DownloadResult(
            failed=["7.173.21"],
            no_coverage=["7.173.21"],
            no_coverage_hints={"7.173.21": err.hints},
        )
        mock_manager_class.return_value = self._list_manager(result)

        rc = main(
            [*self._BBOX_ARGS, "--campaigns", campaigns, "-q", "-o", str(tmp_path)]
        )

        assert rc == 1
        captured = capsys.readouterr()
        assert "nie ma danych dla zadnego z 1 arkuszy" in captured.err
        assert "Info: Dostepny potomek 7.173.21.01" in captured.err
        assert "Downloaded" not in captured.out

    @pytest.mark.parametrize("campaigns", ["newest", "all"])
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_all_no_coverage_not_quiet_no_summary(
        self, mock_manager_class, campaigns, capsys, tmp_path
    ):
        result = DownloadResult(failed=["A"], no_coverage=["A"])
        mock_manager_class.return_value = self._list_manager(result)

        rc = main([*self._BBOX_ARGS, "--campaigns", campaigns, "-o", str(tmp_path)])

        assert rc == 1
        assert "Downloaded" not in capsys.readouterr().out

    @patch("kartograf.cli.download_cmd.DownloadManager")
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

        rc = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "uzyj --scale 1:2000" in captured.err
        assert "Downloaded 0" not in captured.out


class TestErrorWithoutBlankLine:
    """FB-1: no blank line before `Error:` when the progress bar is not running."""

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_single_sheet_error_starts_stderr(
        self, mock_manager_class, capsys, tmp_path
    ):
        manager = _mock_manager(tmp_path / "a.asc")
        manager.download_sheet.side_effect = DownloadError("brak kampanii od 2024")
        mock_manager_class.return_value = manager

        rc = main(["download", "7.125.11.19", "-o", str(tmp_path)])

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: brak kampanii od 2024")

    def test_error_lead_only_after_unfinished_progress_line(self, capsys):
        from kartograf.cli.download_cmd import _error_lead, create_progress_callback

        cb = create_progress_callback(False)
        assert _error_lead(cb) == ""
        cb(DownloadProgress(0, 1, "N-1", "downloading", ""))
        assert _error_lead(cb) == "\n"
        cb(DownloadProgress(1, 1, "N-1", "failed", ""))
        assert _error_lead(cb) == ""
        assert _error_lead(None) == ""


class TestSoilgridsHsgNoEarlyMkdir:
    """soilgrids hsg does not leave an empty output directory after an error."""

    def test_missing_geometry_leaves_no_default_dir(
        self, capsys, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        result = main(["soilgrids", "hsg", "--geometry", "nieistniejacy.shp"])
        assert result == 1
        assert "Error:" in capsys.readouterr().err
        assert not (tmp_path / "data").exists()

    @patch("kartograf.hydrology.HSGCalculator")
    def test_calculation_error_leaves_no_dir(
        self, mock_calc_cls, capsys, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_calc_cls.return_value.calculate_hsg_by_godlo.side_effect = DownloadError(
            "siec"
        )
        out = tmp_path / "out" / "hsg"
        result = main(["soilgrids", "hsg", "--godlo", "N-34-130-D", "-o", str(out)])
        assert result == 1
        assert not (tmp_path / "out").exists()
