"""
Unit tests for CLI module.

This module contains tests for command-line interface commands,
verifying correct parsing and output formatting.
"""

import pytest  # noqa: F401 - required for fixtures

from kartograf.cli.commands import (
    create_parser,
    main,
    format_sheet_info,
    format_hierarchy,
    format_children,
    format_descendants,
)
from kartograf.core.sheet_parser import SheetParser


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
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_parse_subcommand(self, capsys):
        """Test parse subcommand."""
        result = main(["parse", "N-34"])

        assert result == 0
        captured = capsys.readouterr()
        assert "N-34" in captured.out


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
