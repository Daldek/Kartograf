"""
Integration tests for Kartograf.

This module contains end-to-end integration tests that verify the complete
workflow of parsing, storing, and downloading map sheets.
"""

from unittest.mock import Mock

import pytest  # noqa: F401 - required for fixtures

from kartograf import (
    SheetParser,
    DownloadManager,
    DownloadProgress,
    FileStorage,
    GugikProvider,
    ParseError,
    ValidationError,
)


class TestPublicAPIImports:
    """Test that public API is correctly exposed."""

    def test_import_sheet_parser(self):
        """Test SheetParser import from main module."""
        from kartograf import SheetParser

        parser = SheetParser("N-34-130-D")
        assert parser.godlo == "N-34-130-D"

    def test_import_download_manager(self):
        """Test DownloadManager import from main module."""
        from kartograf import DownloadManager

        manager = DownloadManager()
        assert manager is not None

    def test_import_exceptions(self):
        """Test exceptions import from main module."""
        from kartograf import ParseError

        with pytest.raises(ParseError):
            SheetParser("INVALID")

    def test_version(self):
        """Test version is accessible and follows semver format."""
        from kartograf import __version__

        # Version should be a valid semver string (e.g., "0.3.1" or "0.3.1-dev")
        import re

        semver_pattern = r"^\d+\.\d+\.\d+(-\w+)?$"
        assert re.match(semver_pattern, __version__), f"Invalid version: {__version__}"
        assert __version__ == "0.3.2"


class TestParserStorageIntegration:
    """Test integration between SheetParser and FileStorage."""

    def test_parse_and_store(self, test_data_dir):
        """Test parsing godlo and storing file."""
        parser = SheetParser("N-34-130-D-d-2-4")
        storage = FileStorage(test_data_dir)

        # Verify path generation matches parser components
        path = storage.get_path(parser.godlo)

        assert "N-34" in str(path)
        assert "130" in str(path)
        assert "D" in str(path)
        assert "d" in str(path)
        assert "2" in str(path)
        assert "4" in str(path)

    def test_hierarchy_storage_structure(self, test_data_dir, mock_tif_data):
        """Test that hierarchy sheets are stored in correct structure."""
        storage = FileStorage(test_data_dir)
        parser = SheetParser("N-34-130-D-d-2")

        # Get all children and store them
        children = parser.get_children()
        for child in children:
            storage.write_atomic(child.godlo, mock_tif_data)

        # Verify all files exist
        for child in children:
            assert storage.exists(child.godlo)

        # Verify common parent directory (includes resolution subfolder)
        common_parent = test_data_dir / "1m" / "N-34" / "130" / "D" / "d" / "2"
        assert common_parent.exists()

    def test_all_scales_storage(self, test_data_dir, sample_godlos, mock_tif_data):
        """Test storage for all scale levels."""
        storage = FileStorage(test_data_dir)

        for scale, godlo in sample_godlos.items():
            storage.write_atomic(godlo, mock_tif_data)
            assert storage.exists(godlo), f"Failed for {scale}: {godlo}"


class TestDownloadManagerIntegration:
    """Test DownloadManager integration with components."""

    def test_manager_uses_provider_and_storage(self, test_data_dir):
        """Test that manager correctly coordinates provider and storage."""
        manager = DownloadManager(output_dir=test_data_dir)

        # Verify components are properly initialized
        assert isinstance(manager.provider, GugikProvider)
        assert isinstance(manager.storage, FileStorage)
        assert manager.storage.output_dir == test_data_dir

    def test_manager_skip_existing(self, test_data_dir, mock_tif_data):
        """Test that manager skips existing files."""
        storage = FileStorage(test_data_dir)

        # Create existing ASC file
        existing_path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(mock_tif_data)

        mock_provider = Mock()
        manager = DownloadManager(
            output_dir=test_data_dir,
            provider=mock_provider,
        )

        result = manager.download_sheet("N-34-130-D-d-2-4", skip_existing=True)

        # Should return path without calling provider
        assert result.exists()
        mock_provider.download.assert_not_called()

    def test_manager_hierarchy_counting(self, test_data_dir):
        """Test hierarchy sheet counting."""
        manager = DownloadManager(output_dir=test_data_dir)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")
        assert count == 64

        # 1:25k → 1:10k = 4 sheets
        count = manager.count_sheets("N-34-130-D-d-2", "1:10000")
        assert count == 4

    def test_manager_missing_sheets(self, test_data_dir, mock_tif_data):
        """Test missing sheets detection."""
        storage = FileStorage(test_data_dir)

        # Pre-create 2 of 4 sheets (as ASC files)
        for godlo in ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3"]:
            path = storage.get_path(godlo, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(mock_tif_data)

        manager = DownloadManager(output_dir=test_data_dir)
        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 2
        assert "N-34-130-D-d-2-2" in missing
        assert "N-34-130-D-d-2-4" in missing


class TestHierarchyWorkflow:
    """Test complete hierarchy workflows."""

    def test_full_hierarchy_traversal(self, sample_godlos):
        """Test traversing hierarchy from 1:10k to 1:1M."""
        parser = SheetParser(sample_godlos["1:10000"])
        hierarchy = parser.get_hierarchy_up()

        # Should have 7 levels (from 1:10k to 1:1M, skipping 1:500k which is implicit)
        # Actually the hierarchy excludes 1:500k in path but includes it
        scales = [h.scale for h in hierarchy]

        assert scales[0] == "1:10000"
        assert scales[-1] == "1:1000000"

    def test_descendants_match_children_recursion(self):
        """Test that get_all_descendants matches recursive get_children."""
        parser = SheetParser("N-34-130-D-d")  # 1:50k

        # Get all descendants to 1:10k
        descendants = parser.get_all_descendants("1:10000")

        # Should be 4 * 4 = 16 sheets
        assert len(descendants) == 16

        # All should be at 1:10k scale
        for desc in descendants:
            assert desc.scale == "1:10000"

    def test_parent_child_roundtrip(self, sample_godlos):
        """Test parent-child relationships are consistent."""
        for scale in ["1:500000", "1:200000", "1:100000", "1:50000", "1:25000"]:
            godlo = sample_godlos[scale]
            parser = SheetParser(godlo)

            children = parser.get_children()
            for child in children:
                parent = child.get_parent()
                assert parent is not None
                assert parent.godlo == parser.godlo


class TestProgressCallback:
    """Test progress callback integration."""

    def test_progress_callback_receives_all_statuses(
        self, test_data_dir, mock_tif_data
    ):
        """Test that progress callback receives correct status updates."""
        storage = FileStorage(test_data_dir)

        # Pre-create one ASC file to trigger skip
        existing_path = storage.get_path("N-34-130-D-d-2-1", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(mock_tif_data)

        mock_provider = Mock()

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(mock_tif_data)
            return path

        mock_provider.download = mock_download

        manager = DownloadManager(output_dir=test_data_dir, provider=mock_provider)

        progress_calls = []

        def on_progress(p: DownloadProgress):
            progress_calls.append(
                {
                    "godlo": p.godlo,
                    "status": p.status,
                    "current": p.current,
                    "total": p.total,
                }
            )

        manager.download_hierarchy(
            "N-34-130-D-d-2",
            "1:10000",
            on_progress=on_progress,
        )

        # Should have 7 calls: 1 skipped, 3 × (downloading + completed)
        # First file is skipped, others are downloaded
        statuses = [p["status"] for p in progress_calls]
        assert "skipped" in statuses
        assert "downloading" in statuses
        assert "completed" in statuses


class TestErrorHandling:
    """Test error handling across components."""

    def test_invalid_godlo_raises_parse_error(self):
        """Test that invalid godlo raises ParseError."""
        with pytest.raises(ParseError):
            SheetParser("INVALID-FORMAT")

    def test_invalid_scale_raises_validation_error(self):
        """Test that invalid scale raises ValidationError."""
        parser = SheetParser("N-34-130-D")

        with pytest.raises(ValidationError):
            parser.get_all_descendants("invalid_scale")

    def test_descendant_to_larger_scale_raises_error(self):
        """Test that requesting larger scale descendants raises error."""
        parser = SheetParser("N-34-130-D-d-2-4")  # 1:10k

        with pytest.raises(ValueError):
            parser.get_all_descendants("1:100000")  # Can't go to larger scale


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_1m_sheet_has_no_parent(self):
        """Test that 1:1M sheet has no parent."""
        parser = SheetParser("N-34")
        assert parser.get_parent() is None

    def test_10k_sheet_has_no_children(self):
        """Test that 1:10k sheet has no children."""
        parser = SheetParser("N-34-130-D-d-2-4")
        assert parser.get_children() == []

    def test_500k_to_200k_has_36_children(self):
        """Test special 1:500k to 1:200k division."""
        parser = SheetParser("N-34-A")
        children = parser.get_children()

        assert len(children) == 36
        # All should be at 1:200k scale
        for child in children:
            assert child.scale == "1:200000"

    def test_empty_storage_lists_no_files(self, test_data_dir):
        """Test that empty storage returns no files."""
        storage = FileStorage(test_data_dir)
        files = storage.list_files()

        assert files == []

    def test_progress_percent_edge_cases(self):
        """Test progress percentage edge cases."""
        # Zero total
        progress = DownloadProgress(
            current=0, total=0, godlo="N-34", status="completed"
        )
        assert progress.progress_percent == 100.0

        # Partial progress
        progress = DownloadProgress(
            current=1, total=4, godlo="N-34", status="downloading"
        )
        assert progress.progress_percent == 25.0

        # Complete
        progress = DownloadProgress(
            current=4, total=4, godlo="N-34", status="completed"
        )
        assert progress.progress_percent == 100.0
