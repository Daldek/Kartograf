"""
Unit tests for CLI module.

This module contains tests for command-line interface commands,
verifying correct parsing and output formatting.
"""

import argparse
import json
from unittest.mock import Mock, patch

import pytest  # noqa: F401 - required for fixtures

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


def _mock_provider_and_storage(extension):
    """Para (provider, storage) dla patcha ``_create_provider_and_storage``."""
    provider = Mock()
    provider.default_extension = extension
    return provider, Mock()


def _mock_manager(path):
    """Manager-mock zwracajacy ``path`` i BEZ porazek (``last_result=None``)."""
    manager = Mock()
    manager.last_result = None
    manager.download_sheet.return_value = path
    return manager


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
        """Wyjatek spoza KartografError daje komunikat i kod 1, nie traceback."""
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
        """KartografError daje komunikat bez nazwy klasy."""
        result = main(["parse", "N-34"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error: zly godlo" in captured.err
        assert "ValidationError" not in captured.err

    @patch("kartograf.cli.commands.cmd_parse", side_effect=RuntimeError("boom"))
    def test_debug_env_reraises(self, mock_cmd_parse, capsys, monkeypatch):
        """KARTOGRAF_DEBUG=1 przepuszcza pelny traceback."""
        monkeypatch.setenv("KARTOGRAF_DEBUG", "1")

        with pytest.raises(RuntimeError):
            main(["parse", "N-34"])

    def test_top_level_help_mentions_cuzk_and_soilgrids(self, capsys):
        """Teksty --help opisuja CZ/CUZK, SoilGrids i warstwy hydrografii."""
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
        """Domyslne --resolution/--vertical-crs/--system to None (per kraj)."""
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
            "N-34-130-D-d-2-4", skip_existing=True, on_progress=None
        )

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_hierarchy(self, mock_manager_class, capsys, tmp_path):
        """Test downloading a hierarchy."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.count_sheets.return_value = 4
        mock_manager.download_hierarchy.return_value = [
            tmp_path / f"test{i}.tif" for i in range(4)
        ]
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
            "N-34-130-D-d-2-4", skip_existing=False, on_progress=None
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
        mock_manager.download_sheet.return_value = tmp_path / "test.tif"
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path)])

        assert result == 0
        captured = capsys.readouterr()
        assert "Downloading" in captured.out
        assert "Downloaded to" in captured.out

    # --- kod wyjscia hierarchii (A2-3) ---

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_all_failed_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """100% porazek w hierarchii to blad, a nie 'Downloaded 0 files' z exit 0."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = []
        mock_manager.count_sheets.return_value = 4
        mock_manager.last_result = DownloadResult(
            succeeded=[], failed=["A", "B", "C", "D"], skipped=[]
        )
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 1
        assert "4 of 4 sheets failed" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_partial_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Czesciowy sukces tez konczy sie 1 — skrypt ma sie dowiedziec o brakach."""
        paths = [tmp_path / f"test{i}.asc" for i in range(3)]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = paths
        mock_manager.count_sheets.return_value = 4
        mock_manager.last_result = DownloadResult(
            succeeded=paths, failed=["A"], skipped=[]
        )
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 1
        assert "1 of 4 sheets failed" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_all_skipped_returns_exit_0(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Same pominiecia (pliki juz sa) to nadal sukces."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = []
        mock_manager.count_sheets.return_value = 4
        mock_manager.last_result = DownloadResult(
            succeeded=[], failed=[], skipped=["A", "B", "C", "D"]
        )
        mock_manager_class.return_value = mock_manager

        result = main(["download", "N-34-130-D-d-2", "-o", str(tmp_path)])

        assert result == 0
        assert "failed" not in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_hierarchy_scale_mode_failure_returns_exit_1(
        self, mock_manager_class, capsys, tmp_path
    ):
        """Ta sama kontrola obowiazuje na galezi --scale."""
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
        assert "4 of 4 sheets failed" in capsys.readouterr().err


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

        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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

        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.tif"
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

    # --- walidacja par product/resolution i product/vertical-crs (V2-N1) ---

    @patch("kartograf.cli.download_cmd._create_provider_and_storage")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_nmpt_with_resolution_5m_rejected(
        self, mock_manager_cls, mock_create, capsys, tmp_path
    ):
        """NMPT 5m nie istnieje — CLI odrzuca zamiast cicho pobrac 1m."""
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
        """Ortofotomapa nie ma ukladu pionowego — flaga jest bledem, nie no-opem."""
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
        """Regresja: orto bez --vertical-crs dziala jak dotad."""
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
        """Ta sama walidacja obowiazuje w trybie --bbox (sentinele PL)."""
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
        """Ta sama walidacja obowiazuje w trybie --bbox (sentinele PL)."""
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
        from kartograf.cli.commands import _create_provider_and_storage
        from kartograf.providers.pl.gugik import GugikProvider

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikProvider)
        assert storage._product is None
        assert storage._resolution == "1m"

    def test_nmpt_creates_nmpt_provider(self, tmp_path):
        """Test that nmpt creates GugikNmptProvider."""
        from kartograf.cli.commands import _create_provider_and_storage
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikNmptProvider)
        assert storage._product == "nmpt"

    def test_orto_creates_orto_provider(self, tmp_path):
        """Test that orto creates GugikOrtoProvider."""
        from kartograf.cli.commands import _create_provider_and_storage
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider, storage = _create_provider_and_storage(
            "orto", tmp_path, "EVRF2007", "1m"
        )
        assert isinstance(provider, GugikOrtoProvider)
        assert storage._product == "orto"

    def test_laz_product_raises_validation_error(self, tmp_path):
        """LAZ ma osobny przeplyw (_cmd_download_laz) — tu nie ma prawa dotrzec."""
        from kartograf.cli.commands import _create_provider_and_storage

        with pytest.raises(ValidationError, match="LAZ"):
            _create_provider_and_storage("laz", tmp_path, "EVRF2007", "1m")

    def test_unknown_product_raises_validation_error(self, tmp_path):
        """Nieznany produkt nie moze po cichu spasc na fabryke NMT."""
        from kartograf.cli.commands import _create_provider_and_storage

        with pytest.raises(ValidationError, match="dmr5g"):
            _create_provider_and_storage("dmr5g", tmp_path, "EVRF2007", "1m")

    def test_nmt_kron86_storage_segment(self, tmp_path):
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_nmt_5m_kron86_storage_follows_provider_correction(self, tmp_path):
        """Fabryka koryguje 5m=>EVRF2007 — segment ma niesc fakt, nie flage."""
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "5m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"

    def test_nmpt_storage_segment(self, tmp_path):
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmpt/pl_{uklad}_1m_kron86"


class TestCmdDownloadBBox:
    """Tests for download command with --bbox option."""

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_basic(self, mock_manager_class, capsys, tmp_path):
        """Test --bbox wywołuje find_sheets_for_bbox i download_sheet."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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
        # download_sheet powinien być wywołany co najmniej raz
        assert mock_manager.download_sheet.call_count >= 1

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_epsg4326(self, mock_manager_class, capsys, tmp_path):
        """Test --bbox z --bbox-crs EPSG:4326."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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
        assert mock_manager.download_sheet.call_count >= 1

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
        """Test brak godlo i --bbox → exit 1."""
        result = main(["download", "-q"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Must specify" in captured.err

    def test_download_bbox_invalid_format(self, capsys):
        """Test zły format bbox → exit 1."""
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

    def test_download_bbox_too_few_values(self, capsys):
        """Test za mało wartości w bbox → exit 1."""
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
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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
        # Mniejsza skala = mniej arkuszy
        assert mock_manager.download_sheet.call_count >= 1

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_download_bbox_shows_summary(self, mock_manager_class, capsys, tmp_path):
        """Test that bbox mode shows summary when not quiet."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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
    def test_bbox_workers_1_sequential_collects_all_paths(
        self, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--workers 1 idzie petla sekwencyjna i zbiera WSZYSTKIE sciezki."""
        mock_find.return_value = ["A", "B"]
        mock_manager = Mock()
        mock_manager.last_result = None
        # drugi wynik to list[Path] — galaz splaszczania hierarchii
        mock_manager.download_sheet.side_effect = [
            tmp_path / "A.asc",
            [tmp_path / "B1.asc", tmp_path / "B2.asc"],
        ]
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
        assert mock_manager.download_sheet.call_count == 2
        captured = capsys.readouterr()
        assert "Downloaded 3 files" in captured.out


class TestAreaModeHierarchyExitCode:
    """Kod wyjscia trybow --bbox/--geometry, gdy godla rozwijaja sie do hierarchii."""

    @staticmethod
    def _manager_for(results):
        """Manager-mock: kolejne `download_sheet` ustawiaja kolejne `last_result`."""
        manager = Mock()
        manager.last_result = None
        pending = iter(results)

        def _download_sheet(godlo, **kwargs):
            manager.last_result = next(pending)
            return list(manager.last_result.succeeded)

        manager.download_sheet.side_effect = _download_sheet
        return manager

    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    def test_bbox_coarse_scale_failure_returns_exit_1(
        self, mock_find, mock_manager_class, capsys, tmp_path
    ):
        """Porazki arkuszy wewnatrz hierarchii nie moga zginac w petli po godlach."""
        mock_find.return_value = ["N-34-130-D-d-2", "N-34-130-D-d-4"]
        mock_manager_class.return_value = self._manager_for(
            [
                DownloadResult(
                    succeeded=[tmp_path / "a.asc"], failed=["N-34-130-D-d-2-3"]
                ),
                DownloadResult(succeeded=[tmp_path / "b.asc", tmp_path / "c.asc"]),
            ]
        )

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "--scale",
                "1:25000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "1 of 4 sheets failed" in err
        assert "N-34-130-D-d-2-3" in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    def test_bbox_coarse_scale_all_succeeded_returns_exit_0(
        self, mock_find, mock_manager_class, capsys, tmp_path
    ):
        """Regresja: hierarchie bez porazek nadal koncza sie zerem i cisza."""
        mock_find.return_value = ["N-34-130-D-d-2", "N-34-130-D-d-4"]
        mock_manager_class.return_value = self._manager_for(
            [
                DownloadResult(succeeded=[tmp_path / "a.asc"]),
                DownloadResult(succeeded=[tmp_path / "b.asc"], skipped=["X"]),
            ]
        )

        result = main(
            [
                "download",
                "--bbox",
                "630000,480000,637000,487000",
                "--scale",
                "1:25000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 0
        assert capsys.readouterr().err == ""

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_coarse_scale_failure_returns_exit_1(
        self, mock_overall, mock_manager_class, mock_find, capsys, tmp_path
    ):
        """Ta sama kontrola obowiazuje w trybie --geometry."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — glebia PL, auto-split nie dotknie CZ
        mock_find.return_value = ["N-34-130-D-d-2"]
        mock_manager_class.return_value = self._manager_for(
            [DownloadResult(succeeded=[], failed=["N-34-130-D-d-2-1"])]
        )

        result = main(
            [
                "download",
                "--geometry",
                str(shp_file),
                "--scale",
                "1:25000",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )

        assert result == 1
        err = capsys.readouterr().err
        assert "1 of 1 sheets failed" in err
        assert "N-34-130-D-d-2-1" in err

    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    def test_bbox_leaf_scale_stays_parallel(
        self, mock_find, mock_manager_class, tmp_path
    ):
        """Regresja: arkusze 1:10000 (bez rozwiniecia) ida nadal przez pule watkow."""
        mock_find.return_value = ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
        manager = Mock()
        manager.last_result = None
        manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = manager

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
        assert manager.download_sheet.call_count == 2


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

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_basic(
        self, mock_overall, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--geometry calls find_sheets_for_geometry and downloads."""
        # Create a fake SHP file
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa (20.90-21.05E) — glebia PL, auto-split nie dotknie CZ
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
        mock_manager_cls.return_value = mock_manager

        result = main(
            ["download", "--geometry", str(shp_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        mock_find.assert_called_once()
        mock_manager.download_sheet.assert_called_once()

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_with_layer(
        self, mock_overall, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--geometry --layer passes layer parameter."""
        gpkg_file = tmp_path / "area.gpkg"
        gpkg_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — glebia PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_workers_1_sequential_collects_all_paths(
        self, mock_overall, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--workers 1 idzie petla sekwencyjna i zbiera WSZYSTKIE sciezki."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — glebia PL, auto-split nie dotknie CZ
        mock_find.return_value = ["A", "B"]
        mock_manager = Mock()
        mock_manager.last_result = None
        # drugi wynik to list[Path] — galaz splaszczania hierarchii
        mock_manager.download_sheet.side_effect = [
            tmp_path / "A.asc",
            [tmp_path / "B1.asc", tmp_path / "B2.asc"],
        ]
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
        assert mock_manager.download_sheet.call_count == 2
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
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_system_2000(
        self, mock_overall, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """--geometry --system 2000 passes system='2000' to find_sheets_for_geometry."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — glebia PL (--system dotyczy tylko PL)
        mock_find.return_value = ["6.179.12"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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

    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_download_geometry_default_system_1992(
        self, mock_overall, mock_manager_cls, mock_find, capsys, tmp_path
    ):
        """Default system='1992' for geometry download."""
        shp_file = tmp_path / "area.shp"
        shp_file.touch()

        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — glebia PL
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "test.asc"
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


class TestLazUklad:
    """Kaskada ukladu kafla LAZ: uklad_xy -> format godla -> 2000 (spec 5.5)."""

    def _tile(self, godlo="N-33-131-B-a-1-1-4", crs="PL-2000:S6"):
        from kartograf.providers.pl.gugik_laz import LazTile

        return LazTile(
            godlo=godlo,
            url="u/f.laz",
            year=2024,
            density=25,
            crs=crs,
            min_x=0.0,
            min_y=0.0,
            max_x=1.0,
            max_y=1.0,
        )

    def test_crs_pl2000_wins_over_dash_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        # godlo myslnikowe, ale uklad_xy mowi PL-2000 — crs wygrywa
        assert _laz_uklad(self._tile()) == "2000"

    def test_crs_pl1992(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs="PL-1992")) == "1992"

    def test_none_crs_falls_back_to_dot_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(godlo="6.162.34.02.3", crs=None)) == "2000"

    def test_none_crs_falls_back_to_dash_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs=None)) == "1992"

    def test_unrecognized_crs_falls_back_to_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs="EPSG:2180")) == "1992"

    def test_everything_fails_defaults_2000_with_warning(self, caplog):
        import logging

        from kartograf.cli.download_cmd import _laz_uklad

        with caplog.at_level(logging.WARNING):
            assert _laz_uklad(self._tile(godlo="XYZ99", crs=None)) == "2000"
        assert "XYZ99" in caplog.text


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
        """godło → discover tiles → download each via provider.download."""
        instance = Mock()
        instance.discover_tiles.return_value = self._fake_tiles()
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
        instance.discover_tiles.assert_called_once()
        assert instance.download.call_count == 2
        # bbox passed to discover_tiles is in EPSG:2180
        bbox_arg = instance.discover_tiles.call_args[0][0]
        assert bbox_arg.crs == "EPSG:2180"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_bbox_mode(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.discover_tiles.return_value = self._fake_tiles()
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
    def test_laz_year_and_density_forwarded(self, mock_provider_cls, tmp_path):
        instance = Mock()
        instance.discover_tiles.return_value = self._fake_tiles()
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
        kwargs = instance.discover_tiles.call_args.kwargs
        assert kwargs.get("year") == 2023
        assert kwargs.get("min_density") == 12

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_no_tiles_found_errors(self, mock_provider_cls, capsys, tmp_path):
        instance = Mock()
        instance.discover_tiles.return_value = []
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
        assert result == 1
        assert "No LAZ tiles" in capsys.readouterr().err

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_writes_sidecar_next_to_tile(self, mock_provider_cls, tmp_path):
        """Kazdy pobrany kafel dostaje sidecar <nazwa>.laz.meta.json."""
        import json

        tile = self._fake_tiles()[0]
        instance = Mock()
        instance.vertical_crs = "EVRF2007"
        instance.discover_tiles.return_value = [tile]

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
        assert (sidecar.parent / tile.filename).exists()
        assert "pl_2000_evrf2007" in str(sidecar.parent)
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.laz"
        assert payload["vertical_crs"] == "EPSG:9651"
        assert payload["extra"]["godlo_kafla"] == tile.godlo
        assert payload["extra"]["rok"] == tile.year
        assert payload["request"]["bbox_crs"] == "EPSG:2180"

    @patch("kartograf.providers.pl.gugik_laz.GugikLazProvider")
    def test_laz_segment_carries_vertical_crs_from_flag(
        self, mock_provider_cls, tmp_path
    ):
        """Segment {vcrs} niesie --vertical-crs, nie default FileStorage.

        Bez ta asercja test przeszedlby takze wtedy, gdyby ktos usunal
        ``vertical_crs=vertical_crs`` z wywolania ``resolve_subdir`` w
        ``_storage_for`` — default FileStorage ("EVRF2007") maskowalby
        blad dokladnie tak, jak maskowal efekt uboczny Zad. 2 (segment
        LAZ zawsze "evrf2007" niezaleznie od flagi). Ten test wymusza
        KRON86 (rozny od defaultu) i sprawdza, ze trafil do segmentu
        zarowno kafla, jak i sidecara.
        """
        import json

        tile = self._fake_tiles()[0]
        instance = Mock()
        instance.vertical_crs = "KRON86"
        instance.discover_tiles.return_value = [tile]

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

        from kartograf.cli.commands import _resolve_laz_bbox

        args = Namespace(godlo="M-34-27-B-b-2-1", bbox=None, geometry=None)
        bbox = _resolve_laz_bbox(args)
        assert bbox.crs == "EPSG:2180"
        assert bbox.min_x < bbox.max_x and bbox.min_y < bbox.max_y

    def test_bbox_2180_passthrough(self):
        from argparse import Namespace

        from kartograf.cli.commands import _resolve_laz_bbox

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

        from kartograf.cli.commands import _resolve_laz_bbox

        args = Namespace(godlo=None, bbox="1,2,3", bbox_crs="EPSG:2180", geometry=None)
        with pytest.raises(ValueError):
            _resolve_laz_bbox(args)

    def test_bbox_from_krovak_uses_pinned_transform(self):
        """--bbox-crs EPSG:5514 (F2): przejscie do 2180 musi isc przypieta
        operacja (bbox_to_crs), NIE niepinowanym _transform_bbox — inaczej
        selekcja kafli LAZ na pasie granicznym mogla wyniknac z ballparku."""
        from argparse import Namespace

        from kartograf.cli.commands import _resolve_laz_bbox
        from kartograf.core import geometry as geom
        from kartograf.providers.cuzk import dmr

        args = Namespace(
            godlo=None,
            bbox="-788231,-1052442,-741087,-1013379",
            bbox_crs="EPSG:5514",
            geometry=None,
        )
        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(geom, "_transform_bbox", wraps=geom._transform_bbox) as plain,
        ):
            bbox = _resolve_laz_bbox(args)

        assert bbox.crs == "EPSG:2180"
        assert pinned.called
        plain.assert_not_called()

    def test_bbox_from_utm33n_uses_pinned_transform(self):
        """Jak wyzej, ale dla drugiego czeskiego ukladu (EPSG:3045)."""
        from argparse import Namespace

        from kartograf.cli.commands import _resolve_laz_bbox
        from kartograf.core import geometry as geom
        from kartograf.providers.cuzk import dmr

        args = Namespace(
            godlo=None,
            bbox="450000,5540000,455000,5545000",
            bbox_crs="EPSG:3045",
            geometry=None,
        )
        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(geom, "_transform_bbox", wraps=geom._transform_bbox) as plain,
        ):
            bbox = _resolve_laz_bbox(args)

        assert bbox.crs == "EPSG:2180"
        assert pinned.called
        plain.assert_not_called()


def _cz_args(tmp_path, **overrides):
    """Namespace dla bezposrednich wywolan _cmd_download_cz."""
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
    """Mock CuzkDmrProvider dla przeplywu CLI."""
    provider = Mock()
    provider.descriptor_key = "cz.cuzk.dmr5g" if resolution == "2m" else "cz.cuzk.dmr4g"
    provider.resolution = resolution
    provider.vertical_crs = "Bpv"
    provider.vertical_transform = None

    def fake_horizontal(target_crs):
        """Kontrakt CuzkDmrProvider.horizontal_transform: None dla natywnego."""
        if target_crs.endswith("5514"):
            return None
        pinned = Mock()
        pinned.description = f"S-JTSK to ETRS89 (3) -> {target_crs}"
        pinned.accuracy_m = 0.5
        return pinned

    provider.horizontal_transform.side_effect = fake_horizontal

    def fake_download(godlo, target, timeout=60):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download.side_effect = fake_download
    provider.download_bbox.side_effect = lambda bbox, target, **kw: fake_download(
        "x", target
    )
    return provider


_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_dmr_provider"


class TestCmdDownloadCz:
    """Tests for the CZ (CUZK) flow in the download command."""

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """MetadataCache laduje w cwd — poza repo i poza katalogiem wyjsciowym."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

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
        assert payload["horizontal_crs"] == "EPSG:3045"  # faktyczny uklad kafla
        assert payload["vertical_crs"] == "EPSG:8357"  # Bpv natywnie
        assert payload["license"]["id"] == "CC-BY-4.0"
        assert payload["request"] == {"godlo": "302_5550"}
        # kafel TM33 lezy w 3045, a dane CUZK w 5514 — reprojekcja jest LOKALNA
        # i sidecar niesie jej dokladnosc (ADR-024)
        assert payload["transform"] == {
            "horizontal": "pinned: S-JTSK to ETRS89 (3) -> EPSG:3045 (0.5 m)"
        }
        assert "parent_request" not in payload["extra"]  # tryb godlowy bez pola

    def test_sm5_godlo_enriches_extra_with_podil(self, tmp_path):
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
        assert payload["extra"]["podil"] == 0.99

    def test_sm5_index_failure_after_download_keeps_file(self, tmp_path):
        """Blad indeksu przy PODIL: warning, plik i sidecar bez podil zostaja."""
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
        assert "podil" not in payload["extra"]

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
        assert payload["nodata"] == -9999.0  # tag GeoTIFF nieczytelny -> domyslna
        assert payload["transform"] is None  # bez --target-crs: uklad natywny

    def test_bbox_string_is_normalized_to_image_sr(self, tmp_path):
        """Nazwa pliku niesie wspolrzedne FINALNEGO zadania (po normalizacji)."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        args = _cz_args(
            tmp_path,
            godlo=None,
            bbox="472887.5,208337.5,473808.0,209409.8",
            bbox_crs="EPSG:2180",
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(args)

        assert result == 0
        sent_bbox, target = provider.download_bbox.call_args.args[:2]
        assert sent_bbox.crs == "EPSG:5514"
        assert -450000 < sent_bbox.min_x < -440000  # Krovak: wartosci ujemne
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
            "horizontal": "pinned: S-JTSK to ETRS89 (3) -> EPSG:3045 (0.5 m)"
        }

    def test_godlo_without_safe_horizontal_operation_exits_cleanly(
        self, tmp_path, capsys
    ):
        """Sciezka godlowa TM33 buduje operacje pozioma dopiero przy pobieraniu
        (godlo nie ma `--target-crs`, wiec konstruktor jej nie tyka) — brak
        bezpiecznej operacji ma dac komunikat z remedium i kod 1, NIE traceback.

        Zabezpieczenie lezy w `_run_cz`, nie w `_cz_download_godlo`, wiec jest
        latwe do przeoczenia przy refaktorze — stad ten test na pelnym
        przeplywie CLI (`main`), a nie na samej funkcji pomocniczej.
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

    def test_invalid_bbox_string_returns_1(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()):
            result = _cmd_download_cz(_cz_args(tmp_path, godlo=None, bbox="1,2,3"))

        assert result == 1
        assert "bbox" in capsys.readouterr().err.lower()

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
        """Transformacja pionowa Bpv->EVRF2007 w sidecarze; segment niesie
        pion providera (ADR-026)."""
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
        """Blad zapisu sidecara = warning, nie porazka pobrania."""
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
        """Komunikaty per plik w konwencji przeplywu LAZ/PL."""
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

    def test_sidecar_nodata_comes_from_geotiff_tag(self, tmp_path):
        """Nodata w sidecarze pochodzi z tagu pobranego rastra, nie ze stalej."""
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from kartograf.cli.download_cmd import _cmd_download_cz

        def real_tif(godlo, target, timeout=60):
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


def _write_prague_shp(directory):
    """Maly shapefile (poligon w okolicach Pragi) w EPSG:4326 — dane offline."""
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
    """Shapefile w EPSG:5514 (uklad zadania CZ) o dokladnie znanej obwiedni."""
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
    """Dyspozycja per kraj w cmd_download (godlo -> rejestr systemow)."""

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """MetadataCache laduje w cwd — poza repo i katalogiem wyjsciowym."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

    # --- godlo -> kraj ---

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
        """Jawny --country cz zgodny z godlem nie jest konfliktem."""
        mock_cz.return_value = 0
        result = main(
            ["download", "302_5550", "--country", "cz", "-o", str(tmp_path), "-q"]
        )
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_godlo_keeps_sentinels_unresolved(self, mock_cz, tmp_path):
        """Sentinele PL nie moga dotknac argumentow lecacych do CZ."""
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
        """Zachowanie obserwowalne PL bez zmian: None -> 1m/EVRF2007."""
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["resolution"] == "1m"
        assert kwargs["vertical_crs"] == "EVRF2007"

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
        assert "natywnie" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    def test_pl_bbox_with_target_crs_rejected(self, mock_find, tmp_path, capsys):
        """Sentinele PL dzialaja tez w trybie obszarowym (przed szukaniem arkuszy)."""
        result = main(
            [
                "download",
                "--bbox",
                "419000,230000,426000,237000",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert result == 1
        assert "natywnie" in capsys.readouterr().err
        mock_find.assert_not_called()

    # --- ValidationError z przeplywu CZ nie wychodzi jako traceback ---

    def test_cz_godlo_parse_error_returns_1_without_traceback(self, tmp_path, capsys):
        """Wzorzec TM33 z nieparzystymi km: blad CLI (ParseError), nie traceback."""
        result = main(["download", "301_5551", "-o", str(tmp_path), "-q"])
        assert result == 1
        err = capsys.readouterr().err
        assert "Error:" in err
        assert "301_5551" in err

    def test_cz_godlo_with_target_crs_returns_1_without_traceback(
        self, tmp_path, capsys
    ):
        """R9: --target-crs + godlo CZ = blad CLI (main nie lapie wyjatkow)."""
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

    # --- produkty inne niz nmt dla CZ ---

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

    # --- tryby obszarowe: jawny --country cz ---

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
        """Obwiednia liczona w ukladzie PLIKU — transformacje robi warstwa CZ."""
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
        assert requested == CRS.from_epsg(4326)  # uklad pliku, nie Krovak
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_cz_bbox_goes_through_pinned_transform(self, mock_cz, tmp_path):
        """Skok do Krovaka idzie przypieta operacja z probkowaniem krawedzi."""
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
        # Praga w Krovaku: obie wspolrzedne ujemne, |X| ~ 743 km, |Y| ~ 1044 km
        assert -745000 < bbox.min_x < -740000
        assert -1047000 < bbox.min_y < -1041000
        assert bbox.max_x > bbox.min_x and bbox.max_y > bbox.min_y

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_cz_skips_unpinned_transformer(self, mock_cz, tmp_path):
        """core/geometry Transformer (ballpark dozwolony) nie jest uzywany."""
        shp = _write_prague_shp(tmp_path)
        mock_cz.return_value = 0
        with patch("kartograf.core.geometry.Transformer") as mock_transformer:
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
        mock_transformer.from_crs.assert_not_called()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_cz_target_crs_in_one_hop(self, mock_cz, tmp_path):
        """--target-crs: obwiednia od razu w ukladzie zadanym serwerowi."""
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
        """--country auto + bbox w glebi PL (Warszawa): przeplyw CZ nietkniety."""
        mock_find.return_value = ["N-34-130-D-d-2-4"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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


# ===========================================================================
# Auto-split bbox/geometrii per kraj + extra.parent_request (Zad. 17)
# ===========================================================================


class TestAutoSplitBBox:
    """--country auto: bbox transgraniczny dzielony na kraje, parent_request."""

    # 18.4-18.8E / 49.55-49.75N — pas przygraniczny PL/CZ (obie obwiednie
    # krajow zawieraja ten prostokat: CZ do 18.86E/51.06N, PL od 14.07E/49.0N)
    _BORDER = [
        "download",
        "--bbox",
        "18.4,49.55,18.8,49.75",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 21.0-21.2E / 52.0-52.2N — Warszawa, na wschod od obwiedni CZ (18.86E)
    _PL_ONLY = [
        "download",
        "--bbox",
        "21.0,52.0,21.2,52.2",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]
    # 13.3-13.5E / 49.7-49.8N — Pilzno, na zachod od obwiedni PL (14.07E)
    _CZ_ONLY = [
        "download",
        "--bbox",
        "13.3,49.7,13.5,49.8",
        "--bbox-crs",
        "EPSG:4326",
        "-q",
    ]

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """MetadataCache laduje w cwd — poza repo i katalogiem wyjsciowym."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_border_bbox_splits_into_both_countries(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        expected_parent = {
            "bbox": [18.4, 49.55, 18.8, 49.75],
            "bbox_crs": "EPSG:4326",
            "countries": ["CZ", "PL"],
        }
        # PL: manager dostal sidecar_extra z parent_request
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"] == {"parent_request": expected_parent}
        # CZ: przeplyw wywolany z tym samym parent_request i bboxem w Krovaku
        cz_kwargs = mock_cz.call_args.kwargs
        assert cz_kwargs["parent_request"] == expected_parent
        assert cz_kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_country_order_is_deterministic(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Kolejnosc krajow z all_countries() — posortowana (CZ przed PL)."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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
        """Galaz PL pracuje na KOPII args — sentinele CZ zostaja None."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        main(self._BORDER + ["-o", str(tmp_path)])

        # mock trzyma REFERENCJE do Namespace'u — gdyby galaz PL (idaca po CZ)
        # mutowala ten sam obiekt, sentinele bylyby juz rozwiazane
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
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager

        result = main(self._PL_ONLY + ["-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"]["parent_request"]["countries"] == ["PL"]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_cz_only_bbox_skips_pl_flow(self, mock_manager_class, mock_cz, tmp_path):
        """Bbox w calosci w CZ (13.3-13.5E, na zachod od 14.07E): tylko CUZK."""
        mock_cz.return_value = 0
        result = main(self._CZ_ONLY + ["-o", str(tmp_path)])

        assert result == 0
        mock_manager_class.assert_not_called()
        assert mock_cz.call_args.kwargs["parent_request"]["countries"] == ["CZ"]

    def test_cz_only_bbox_with_orto_rejected_as_stage_2(self, tmp_path, capsys):
        """Kraj rozstrzygniety obszarem — komunikat o etapie 2, nie o wyborze."""
        result = main(self._CZ_ONLY + ["--product", "orto", "-o", str(tmp_path)])
        assert result == 1
        assert "etapie 2" in capsys.readouterr().err

    def test_single_country_error_has_no_country_hint(self, tmp_path, capsys):
        """Przy jednym kraju podpowiedz --country byla by bez tresci."""
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
        # jawny kraj: bbox bez przycinania (przekazany oryginal)
        assert mock_cz.call_args.kwargs["bbox"] == BBox(
            -447000, -1114000, -446000, -1113000, "EPSG:5514"
        )

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_explicit_pl_bbox_not_clipped(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Jawny --country pl: caly bbox transgraniczny idzie do PL, bez CZ."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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
        """Tryb auto przycina czesc CZ do obwiedni kraju (18.86E)."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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
        # parent_request niesie ORYGINALNY bbox zadania (przed przycieciem)
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["bbox"] == [18.4, 49.55, 19.5, 49.75]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_part_of_cz_crs_bbox_leaves_krovak_pinned(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """Zadanie w Krovaku kierowane tez do PL: skok 5514->2180 przypiety.

        Bbox 13.73-14.46E / 49.95-50.35N (podany w EPSG:5514) przecina oba
        kraje i jest dla PL FAKTYCZNIE przycinany (obwiednia PL zaczyna sie
        na 14.07E) — czyli wchodzi w sciezke, w ktorej selekcja arkuszy GUGiK
        moglaby wyniknac z niepinowanych transformacji Krovaka.
        """
        from kartograf.cli.download_cmd import _bbox_to_wgs84
        from kartograf.core import geometry as geom
        from kartograf.providers.cuzk import dmr
        from kartograf.providers.cuzk.client import wkid

        mock_find.return_value = ["M-33-46-A-a-1-1"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(geom, "_transform_bbox", wraps=geom._transform_bbox) as plain,
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
        # galaz PL dostala bbox w ukladzie polskim
        pl_bbox = mock_find.call_args.args[0]
        assert pl_bbox.crs == "EPSG:2180"
        # ...przyciety do obwiedni PL (zadanie siegalo 13.73E, PL od 14.07E)
        assert _bbox_to_wgs84(pl_bbox).min_x > 13.9
        # ...i wyprowadzony przypieta operacja z Krovaka
        assert any(call.args[1] == "EPSG:2180" for call in pinned.call_args_list)
        # niepinowany transformer nigdy nie celuje w uklad czeski
        assert not any(
            wkid(str(call.args[5])) in {"5514", "3045"} for call in plain.call_args_list
        )

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_cz_failure_does_not_skip_pl_and_warns(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Porazka pierwszego kraju nie anuluje drugiego ani calego zadania."""
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 1  # CZ idzie pierwsze (sortowanie) i pada

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        mock_manager.download_sheet.assert_called()
        err = capsys.readouterr().err
        assert "Warning:" in err
        assert "nie pobrano danych z CZ" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_failure_with_cz_success_warns_and_returns_0(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError("serwer padl")
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        assert mock_cz.called
        assert "nie pobrano danych z PL" in capsys.readouterr().err

    # --- A3-2: prostokatne obwiednie krajow a kod wyjscia ---

    # 14,40-14,45E / 50,05-50,10N — Praga, w glebi CZ, ale wewnatrz prostokata
    # PL (od 14,07E): auto odpytuje tez GUGiK, ktory danych tam nie ma
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
        """Kraj bez danych na obszarze drugiego kraju nie psuje calego zadania."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError(
            "No NMT 1m data available for M-33-65-D-b-3-3"
        )
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._PRAGUE + ["-o", str(tmp_path)])

        assert result == 0
        err = capsys.readouterr().err
        assert "Warning:" in err
        assert "PL" in err
        assert "CZ" in err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_all_countries_failed_returns_1(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """Gdy padly wszystkie kraje, kod wyjscia zostaje bez zmian."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError("serwer padl")
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
        """Jawny --country: uzytkownik zna zasieg, wiec porazka to porazka."""
        mock_find.return_value = ["M-33-65-D-b-3-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.side_effect = DownloadError("serwer padl")
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

    # --- N6-2: flagi tylko-PL rozstrzygaja `auto`, zamiast przewracac zadanie ---

    def _pl_mocks(self, mock_manager_class, mock_find, tmp_path, godlo):
        """Galaz PL: jeden arkusz, manager zwraca gotowy plik."""
        mock_find.return_value = [godlo]
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        return mock_manager

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_resolution_1m_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """1m nie istnieje w CZ (2m/5m): auto rozstrzyga kraj na PL."""
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
        """KRON86 jest nieosiagalny dla CZ (ADR-023 e): kraj = PL."""
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
        """--system nie dotyczy CZ: auto = pl, a sidecar niesie tylko PL."""
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
        """Rozstrzygniecie na PL dziala jak jawny --country pl: bez przyciecia.

        Bbox 13,5-14,5E siega na zachod od obwiedni PL (14,07E), wiec w trybie
        auto galaz PL dostalaby go przycietego — po rozstrzygnieciu flaga
        tylko-PL ma dostac oryginal.
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
        """Jawny --country cz: walidacja bez zmian (nie ma czego rozstrzygac)."""
        result = main(
            self._BORDER + ["--country", "cz", "--system", "2000", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--system dotyczy tylko PL" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_border_bbox_with_target_crs_rejected_before_any_download(
        self, mock_cz, tmp_path, capsys
    ):
        """Walidacja PRZED pobraniem — inaczej CZ pobralby sie, a PL odrzucil."""
        result = main(self._BORDER + ["--target-crs", "EPSG:3045", "-o", str(tmp_path)])
        assert result == 1
        assert "--country" in capsys.readouterr().err
        mock_cz.assert_not_called()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_auto_with_product_nmpt_resolves_to_pl(
        self, mock_manager_class, mock_find, mock_cz, tmp_path, capsys
    ):
        """NMPT dla CZ to etap 2: auto rozstrzyga kraj na PL."""
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
        """Ortofotomapa dla CZ to etap 2: auto rozstrzyga kraj na PL."""
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
        """5m istnieje po obu stronach — auto-split przechodzi."""
        mock_find.return_value = ["M-34-86-D"]
        mock_manager = Mock()
        mock_manager.last_result = None
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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
        """LAZ (PL-only) + bbox przecinajacy CZ + auto => blad z podpowiedzia,
        zamiast cichego pobrania tylko czesci PL (spec 5.7: bez cichego
        pomijania kraju)."""
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
        """Tryb godlowy LAZ nie przechodzi przez guard transgraniczny.

        Godlo M-34-86-D-d-4-3 lezy przy granicy z CZ (wewnatrz obwiedni CZ),
        wiec w trybie obszarowym guard by zadzialal — kraj godla jest jednak
        jednoznaczny.
        """
        from kartograf.providers.pl import gugik_laz

        with patch.object(gugik_laz, "GugikLazProvider") as provider_cls:
            provider_cls.return_value.discover_tiles.return_value = []
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
        """TransformError z normalizacji bboxa CZ = komunikat CLI, nie traceback."""
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


class TestAutoSplitGeometry:
    """--geometry w trybie auto: obwiednia decyduje o krajach."""

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_geometry_border_splits(
        self, mock_manager_class, mock_find, mock_overall, mock_cz, tmp_path
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        # obwiednia w 2180 przecinajaca oba kraje (okolice Cieszyna:
        # 18.513-18.792E / 49.666-49.847N — wewnatrz obwiedni CZ i PL)
        mock_overall.return_value = BBox(
            465000.0, 200000.0, 485000.0, 220000.0, "EPSG:2180"
        )
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
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

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_geometry_pl_only_skips_cz(
        self, mock_manager_class, mock_find, mock_overall, mock_cz, tmp_path
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(
            630000.0, 480000.0, 640000.0, 490000.0, "EPSG:2180"
        )  # Warszawa — poza obwiednia CZ
        mock_find.return_value = ["N-34-138-A-b-1-1"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager

        result = main(
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        mock_cz.assert_not_called()
        parent = mock_manager_class.call_args.kwargs["sidecar_extra"]["parent_request"]
        assert parent["countries"] == ["PL"]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_geometry_explicit_cz_gets_parent_request(self, mock_cz, tmp_path):
        """Jawny --country cz: parent_request z obwiedni w ukladzie zadania."""
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
        """Plik juz w EPSG:5514: obwiednia idzie do CUZK bit w bit, bez skoku."""
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
        """Brak bezpiecznej operacji: kod 1 i Remedium na stderr, zero pobierania."""
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

    @patch("kartograf.core.geometry.get_overall_bbox")
    def test_geometry_outside_known_countries(self, mock_overall, tmp_path, capsys):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        mock_overall.return_value = BBox(2.0, 40.0, 2.5, 40.5, "EPSG:4326")

        result = main(
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 1
        assert "kraju" in capsys.readouterr().err


class TestPublicApiCz:
    """Eksporty publiczne API dla modulow CZ (zad. 18)."""

    def test_cz_exports_available(self):
        from kartograf import CuzkDmrProvider, ParserTM33, create_dmr_provider

        assert ParserTM33("302_5550").get_bbox().crs == "EPSG:3045"
        assert callable(create_dmr_provider)
        assert CuzkDmrProvider.__name__ == "CuzkDmrProvider"

    def test_version_bumped(self):
        from kartograf import __version__

        assert __version__ == "0.7.0-dev"
