"""
Unit tests for the storage module.

This module contains tests for the FileStorage class, verifying the
correctness of path generation and file operations.
"""

import hashlib
import io
import json
import os
import re
from unittest.mock import Mock, patch

import pytest  # noqa: F401 - required for fixtures
import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.data import download_data
from kartograf.download.storage import FileStorage, bbox_slot
from kartograf.exceptions import ValidationError
from kartograf.sources.variants import variants
from tests.conftest import wfs_endpoint, wfs_fixture, wfs_response


class TestFileStorageBasic:
    """Tests of the basic FileStorage functionality."""

    def test_init_custom_directory(self):
        """Test initialisation with a custom directory."""
        storage = FileStorage("/custom/path", resolution="1m", vertical_crs="EVRF2007")
        assert str(storage.output_dir) == "/custom/path"

    def test_repr(self):
        """Test the string representation."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        assert "FileStorage" in repr(storage)
        assert "data" in repr(storage)


class TestFileStorageGetPath:
    """Tests of get_path()."""

    def test_get_path_1m(self):
        """Test the path for scale 1:1000000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34", ".tif")

        assert path.name == "N-34.tif"
        assert "N-34" in str(path)

    def test_get_path_500k(self):
        """Test the path for scale 1:500000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-A", ".tif")

        assert path.name == "N-34-A.tif"
        assert "N-34" in str(path)
        assert "A" in str(path)

    def test_get_path_200k(self):
        """Test the path for scale 1:200000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130", ".tif")

        assert path.name == "N-34-130.tif"
        assert "N-34" in str(path)
        assert "130" in str(path)

    def test_get_path_100k(self):
        """Test the path for scale 1:100000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D", ".tif")

        assert path.name == "N-34-130-D.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts

    def test_get_path_50k(self):
        """Test the path for scale 1:50000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d", ".tif")

        assert path.name == "N-34-130-D-d.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts
        assert "d" in parts

    def test_get_path_25k(self):
        """Test the path for scale 1:25000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d-2", ".tif")

        assert path.name == "N-34-130-D-d-2.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts
        assert "d" in parts
        assert "2" in parts

    def test_get_path_10k(self):
        """Test the path for scale 1:10000."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d-2-4", ".tif")

        assert path.name == "N-34-130-D-d-2-4.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts
        assert "d" in parts
        assert "2" in parts
        assert "4" in parts

    def test_get_path_different_extensions(self):
        """Test different file extensions."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")

        path_tif = storage.get_path("N-34-130-D", ".tif")
        path_asc = storage.get_path("N-34-130-D", ".asc")
        path_xyz = storage.get_path("N-34-130-D", ".xyz")

        assert path_tif.suffix == ".tif"
        assert path_asc.suffix == ".asc"
        assert path_xyz.suffix == ".xyz"

    def test_get_path_normalizes_sheet(self):
        """Test sheet code normalisation in the path."""
        storage = FileStorage("./data", resolution="1m", vertical_crs="EVRF2007")

        # Lowercase letters should be normalised
        path = storage.get_path("n-34-130-d", ".asc")

        assert "N-34-130-D" in path.name


class TestFileStorageEnsureDirectory:
    """Tests of ensure_directory()."""

    def test_ensure_directory_creates_dirs(self, tmp_path):
        """Test directory creation."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        dir_path = storage.ensure_directory("N-34-130-D-d-2-4", ".asc")

        assert dir_path.exists()
        assert dir_path.is_dir()

    def test_ensure_directory_idempotent(self, tmp_path):
        """Test that repeated calls cause no errors."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        dir_path1 = storage.ensure_directory("N-34-130-D", ".asc")
        dir_path2 = storage.ensure_directory("N-34-130-D", ".asc")

        assert dir_path1 == dir_path2
        assert dir_path1.exists()


class TestFileStorageExists:
    """Tests of exists()."""

    def test_exists_false_when_not_present(self, tmp_path):
        """Test that exists() returns False when the file does not exist."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        assert storage.exists("N-34-130-D", ".asc") is False

    def test_exists_true_when_present(self, tmp_path):
        """Test that exists() returns True when the file exists."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        # Create the file
        storage.write_atomic("N-34-130-D", b"test data", ".asc")

        assert storage.exists("N-34-130-D", ".asc") is True


class TestFileStorageWriteAtomic:
    """Tests of write_atomic()."""

    def test_write_atomic_bytes(self, tmp_path):
        """Test atomic byte writing."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        content = b"test data content"

        path = storage.write_atomic("N-34-130-D", content, ".asc")

        assert path.exists()
        assert path.read_bytes() == content

    def test_write_atomic_file_object(self, tmp_path):
        """Test atomic writing from a file object."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        content = b"test data from file object"
        file_obj = io.BytesIO(content)

        path = storage.write_atomic("N-34-130-D", file_obj, ".asc")

        assert path.exists()
        assert path.read_bytes() == content

    def test_write_atomic_creates_directories(self, tmp_path):
        """Test that write_atomic creates directories."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        path = storage.write_atomic("N-34-130-D-d-2-4", b"data", ".asc")

        assert path.exists()
        assert path.parent.exists()

    def test_write_atomic_no_temp_file_on_success(self, tmp_path):
        """Test that no temporary file remains after success."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        path = storage.write_atomic("N-34-130-D", b"data", ".asc")
        temp_path = path.with_suffix(".tif.tmp")

        assert path.exists()
        assert not temp_path.exists()

    def test_write_atomic_overwrites_existing(self, tmp_path):
        """Test that write_atomic overwrites an existing file."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        storage.write_atomic("N-34-130-D", b"old content", ".asc")
        path = storage.write_atomic("N-34-130-D", b"new content", ".asc")

        assert path.read_bytes() == b"new content"


class TestFileStorageDelete:
    """Tests of delete()."""

    def test_delete_existing_file(self, tmp_path):
        """Test deleting an existing file."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        storage.write_atomic("N-34-130-D", b"data", ".asc")

        result = storage.delete("N-34-130-D", ".asc")

        assert result is True
        assert not storage.exists("N-34-130-D", ".asc")

    def test_delete_nonexistent_file(self, tmp_path):
        """Test deleting a nonexistent file."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        result = storage.delete("N-34-130-D", ".asc")

        assert result is False


class TestFileStorageListFiles:
    """Tests of list_files()."""

    def test_list_files_empty(self, tmp_path):
        """Test an empty directory."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        files = storage.list_files("**/*.asc")

        assert files == []

    def test_list_files_with_files(self, tmp_path):
        """Test with existing files."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        storage.write_atomic("N-34-130-A", b"data1", ".asc")
        storage.write_atomic("N-34-130-B", b"data2", ".asc")
        storage.write_atomic("N-34-130-C", b"data3", ".asc")

        files = storage.list_files("**/*.asc")

        assert len(files) == 3

    def test_list_files_with_pattern(self, tmp_path):
        """Test with a pattern."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        storage.write_atomic("N-34-130-A", b"data1", ".tif")
        storage.write_atomic("N-34-130-B", b"data2", ".asc")

        tif_files = storage.list_files("**/*.tif")
        asc_files = storage.list_files("**/*.asc")

        assert len(tif_files) == 1
        assert len(asc_files) == 1

    def test_list_files_nonexistent_directory(self):
        """Test for a nonexistent directory."""
        storage = FileStorage(
            "/nonexistent/path", resolution="1m", vertical_crs="EVRF2007"
        )

        files = storage.list_files("**/*.asc")

        assert files == []


class TestFileStorageGetSize:
    """Tests of get_size()."""

    def test_get_size_existing_file(self, tmp_path):
        """Test the size of an existing file."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        content = b"test data content"
        storage.write_atomic("N-34-130-D", content, ".asc")

        size = storage.get_size("N-34-130-D", ".asc")

        assert size == len(content)

    def test_get_size_nonexistent_file(self, tmp_path):
        """Test the size of a nonexistent file."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        size = storage.get_size("N-34-130-D", ".asc")

        assert size is None


class TestFileStorageDirectoryStructure:
    """Directory structure tests."""

    def test_directory_structure_10k(self, tmp_path):
        """Test the full directory structure for 1:10k."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        storage.write_atomic("N-34-130-D-d-2-4", b"data", ".asc")

        # Verify directory structure (includes resolution subfolder)
        expected_parts = [
            "nmt",
            "pl_1992_1m_evrf2007",
            "N-34",
            "130",
            "D",
            "d",
            "2",
            "4",
        ]
        current_dir = tmp_path

        for part in expected_parts:
            current_dir = current_dir / part
            assert current_dir.exists(), f"Directory {current_dir} should exist"
            assert current_dir.is_dir(), f"{current_dir} should be a directory"

        # Verify file exists in final directory (default extension is .asc)
        file_path = current_dir / "N-34-130-D-d-2-4.asc"
        assert file_path.exists()

    def test_multiple_files_share_directories(self, tmp_path):
        """Test that many files share common parent directories."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")

        # Write files that share common directories (same 1:25k parent)
        storage.write_atomic("N-34-130-D-d-2-1", b"data1", ".asc")
        storage.write_atomic("N-34-130-D-d-2-2", b"data2", ".asc")
        storage.write_atomic("N-34-130-D-d-2-3", b"data3", ".asc")
        storage.write_atomic("N-34-130-D-d-2-4", b"data4", ".asc")

        # Each file goes in its own final directory, but they share parent dirs
        # Check the common parent directory (1:25k level)
        common_parent = (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "N-34" / "130" / "D" / "d" / "2"
        )
        assert common_parent.exists()

        # Should have 4 subdirectories (1, 2, 3, 4)
        subdirs = list(common_parent.iterdir())
        assert len(subdirs) == 4

        # Each subdirectory should contain one file (default extension is .asc)
        for subdir in subdirs:
            files = list(subdir.glob("*.asc"))
            assert len(files) == 1


class TestFileStorageProduct:
    """Tests for product-based storage (nmpt, orto)."""

    def test_product_nmpt_subdir(self, tmp_path):
        """Test that product='nmpt' uses nmpt as subdirectory."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmpt"
        )
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")

        parts = str(path).split("/")
        assert "nmpt" in parts
        assert "nmt_1m" not in parts

    def test_product_orto_subdir(self, tmp_path):
        """Test that product='orto' uses orto as subdirectory."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs=None, product="orto"
        )
        path = storage.get_path("N-34-130-D-d-2-4", ".tif")

        parts = str(path).split("/")
        assert "orto" in parts
        assert path.name == "N-34-130-D-d-2-4.tif"

    def test_product_none_backward_compatible(self, tmp_path):
        """Test that product=None preserves resolution-based behavior."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D", ".asc")

        parts = str(path).split("/")
        assert "pl_1992_1m_evrf2007" in parts

    def test_product_subdir_structure(self, tmp_path):
        """Test full directory structure with product."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs=None, product="orto"
        )
        storage.write_atomic("N-34-130-D-d-2-4", b"TIF data", ".tif")

        # Verify directory structure
        expected_parts = [
            "orto",
            "pl_1992",
            "N-34",
            "130",
            "D",
            "d",
            "2",
            "4",
        ]
        current_dir = tmp_path

        for part in expected_parts:
            current_dir = current_dir / part
            assert current_dir.exists(), f"Directory {current_dir} should exist"

        # Verify file exists
        file_path = current_dir / "N-34-130-D-d-2-4.tif"
        assert file_path.exists()

    def test_product_repr(self, tmp_path):
        """Test repr includes product."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmpt"
        )
        repr_str = repr(storage)

        assert "product='nmpt'" in repr_str


class TestFileStoragePL2000:
    """Directory structure tests for PL-2000 sheet codes (dotted format)."""

    def test_get_path_pl2000_10k(self, tmp_path):
        """Test the path for PL-2000 1:10000 (3 components: zone.band.column)."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        path = storage.get_path("6.179.12", ".asc")

        assert path.name == "6.179.12.asc"
        parts = path.relative_to(tmp_path).parts
        assert "nmt_2000_1m" in parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts

    def test_get_path_pl2000_2k(self, tmp_path):
        """Test the path for PL-2000 1:2000 (4 components: zone.band.column.ark_2k)."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        path = storage.get_path("6.179.12.20", ".asc")

        assert path.name == "6.179.12.20.asc"
        parts = path.relative_to(tmp_path).parts
        assert "nmt_2000_1m" in parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "20" in parts

    def test_get_path_pl2000_1k(self, tmp_path):
        """Test the path for PL-2000 1:1000 (5 components)."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        path = storage.get_path("6.179.12.20.3", ".asc")

        assert path.name == "6.179.12.20.3.asc"
        parts = path.relative_to(tmp_path).parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "20" in parts
        assert "3" in parts

    def test_get_path_pl2000_5k(self, tmp_path):
        """Test the path for PL-2000 1:5000 (4 components: zone.band.column.ark_5k)."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        path = storage.get_path("6.179.12.2", ".asc")

        assert path.name == "6.179.12.2.asc"
        parts = path.relative_to(tmp_path).parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "2" in parts

    def test_get_path_pl1992_unchanged(self, tmp_path):
        """Test that a PL-1992 sheet code is not affected by the PL-2000 changes."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_1m"
        )
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")

        assert path.name == "N-34-130-D-d-2-4.asc"
        parts = path.relative_to(tmp_path).parts
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts

    def test_exists_pl2000_false(self, tmp_path):
        """Test that exists() returns False for a nonexistent PL-2000 file."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        assert not storage.exists("6.179.12.20", ".asc")

    def test_write_and_exists_pl2000(self, tmp_path):
        """Test writing and checking the existence of a PL-2000 file."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        storage.write_atomic("6.179.12.20", b"PL-2000 data", ".asc")

        assert storage.exists("6.179.12.20", ".asc")

    def test_directory_structure_pl2000_2k(self, tmp_path):
        """Test the full directory structure for PL-2000 1:2000."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        storage.write_atomic("6.179.12.20", b"data", ".asc")

        expected_parts = ["nmt_2000_1m", "6", "179", "12", "20"]
        current_dir = tmp_path

        for part in expected_parts:
            current_dir = current_dir / part
            assert current_dir.exists(), f"Directory {current_dir} should exist"
            assert current_dir.is_dir(), f"{current_dir} should be a directory"

        file_path = current_dir / "6.179.12.20.asc"
        assert file_path.exists()

    def test_multiple_files_share_directories_pl2000(self, tmp_path):
        """Test that PL-2000 files from the same 10k share parent directories."""
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )

        # Several 1:2000 sheets in one 1:10000
        storage.write_atomic("6.179.12.01", b"data1", ".asc")
        storage.write_atomic("6.179.12.02", b"data2", ".asc")
        storage.write_atomic("6.179.12.25", b"data3", ".asc")

        # Common parent directory (1:10k level)
        common_parent = tmp_path / "nmt_2000_1m" / "6" / "179" / "12"
        assert common_parent.exists()

        subdirs = list(common_parent.iterdir())
        assert len(subdirs) == 3


class TestFileStorageGetRawPath:
    """Tests for get_raw_path (opaque identifiers, e.g. LAZ tile sheet codes)."""

    def test_raw_path_pl1992_fine_sheet(self, tmp_path):
        """Fine PL-1992 sheet code (finer than 1:10000) is split without parsing."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        path = storage.get_raw_path(
            "N-33-131-B-a-1-1-4", "81121_1573132_N-33-131-B-a-1-1-4.laz"
        )
        parts = str(path).split("/")
        assert "laz" in parts
        # Hierarchy: base "N-33" then each remaining component
        assert parts[-8:-1] == ["N-33", "131", "B", "a", "1", "1", "4"]
        assert path.name == "81121_1573132_N-33-131-B-a-1-1-4.laz"

    def test_raw_path_pl2000_sheet(self, tmp_path):
        """PL-2000 dotted sheet code is split on dots."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        path = storage.get_raw_path("6.162.34.02.3", "x_6.162.34.02.3.laz")
        parts = str(path).split("/")
        assert parts[-6:-1] == ["6", "162", "34", "02", "3"]
        assert path.name == "x_6.162.34.02.3.laz"

    def test_raw_path_does_not_parse_identifier(self, tmp_path):
        """A non-parseable identifier must NOT raise (unlike get_path)."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        # get_path would raise ParseError on this; get_raw_path must not
        path = storage.get_raw_path("M-34-27-B-b-2-1-1", "f.laz")
        assert path.name == "f.laz"
        assert "laz" in str(path).split("/")

    def test_raw_path_preserves_original_filename(self, tmp_path):
        """The provided filename is used verbatim (preserves density/seq id)."""
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        path = storage.get_raw_path("6.1.1", "12345_67890_tile.laz")
        assert path.name == "12345_67890_tile.laz"


class TestSubdirOverride:
    """Stage 0: descriptor-driven subdir (stage 1: e.g. cz_dmr5g)."""

    def test_subdir_takes_precedence(self, tmp_path):
        storage = FileStorage(
            tmp_path, subdir="cz_dmr5g", resolution="1m", vertical_crs="EVRF2007"
        )
        path = storage.get_raw_path("302_5550", "302_5550.tif")
        # "302_5550" is a TM33 sheet code (cz_tm33 registration, Task 11) — nested
        # directories ["302", "5550"] per path_parts, like other multi-part systems.
        assert path == tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif"

    def test_subdir_wins_over_product_and_resolution(self, tmp_path):
        storage = FileStorage(
            tmp_path,
            resolution="5m",
            product="orto",
            subdir="wlasny",
            vertical_crs="EVRF2007",
        )
        assert storage.get_path("N-34", ".asc") == (
            tmp_path / "wlasny" / "N-34" / "N-34.asc"
        )

    def test_none_keeps_legacy_behavior(self, tmp_path):
        assert FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007").get_path(
            "N-34", ".asc"
        ) == (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc")
        assert FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmpt"
        ).get_path("N-34", ".asc") == (
            tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc"
        )

    def test_repr_with_subdir(self, tmp_path):
        assert "subdir='cz_dmr5g'" in repr(
            FileStorage(
                tmp_path, subdir="cz_dmr5g", resolution="1m", vertical_crs="EVRF2007"
            )
        )


class TestDeleteRemovesSidecar:
    """delete() must not leave an orphaned .meta.json."""

    def test_delete_removes_data_file_and_sidecar(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ncols 1\n", encoding="ascii")
        sidecar = path.with_name(path.name + ".meta.json")
        sidecar.write_text("{}\n", encoding="utf-8")

        assert storage.delete("N-34-130-D-d-2-4", ".asc") is True
        assert not path.exists()
        assert not sidecar.exists()

    def test_delete_without_sidecar_still_works(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ncols 1\n", encoding="ascii")

        assert storage.delete("N-34-130-D-d-2-4", ".asc") is True
        assert not path.exists()


class TestFileStorageSegments:
    """data/ layout 0.7.0: <product>/<country>_<crs>[_<variant>][_<vcrs>] (ADR-026)."""

    def test_default_pl1992_evrf2007(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        assert storage.get_path("N-34-130-D-d-2-4", ".asc") == (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "N-34"
            / "130"
            / "D"
            / "d"
            / "2"
            / "4"
            / "N-34-130-D-d-2-4.asc"
        )

    def test_kron86_segment(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="KRON86")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        assert "pl_1992_1m_kron86" in path.parts

    def test_pl2000_gets_own_segment(self, tmp_path):
        """ADR-017 closed: PL-2000 no longer shares a directory with PL-1992."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        assert storage.get_path("6.179.12.20", ".asc") == (
            tmp_path
            / "nmt"
            / "pl_2000_1m_evrf2007"
            / "6"
            / "179"
            / "12"
            / "20"
            / "6.179.12.20.asc"
        )

    def test_nmt_5m_segment(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="5m", vertical_crs="EVRF2007")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        assert "pl_1992_5m_evrf2007" in path.parts

    def test_nmpt_segment(self, tmp_path):
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmpt"
        )
        path = storage.get_path("N-34", ".asc")
        assert path == (tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc")

    def test_orto_segment_no_vcrs(self, tmp_path):
        """Orto has no vertical - the segment without {vcrs} also for None."""
        storage = FileStorage(
            tmp_path, product="orto", vertical_crs=None, resolution="1m"
        )
        assert storage.get_path("N-34", ".tif") == (
            tmp_path / "orto" / "pl_1992" / "N-34" / "N-34.tif"
        )

    def test_laz_segment_by_identifier(self, tmp_path):
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        p1992 = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz")
        p2000 = storage.get_raw_path("6.162.34.02.3", "b.laz")
        assert tuple(p1992.parts[-10:-8]) == ("laz", "pl_1992_evrf2007")
        assert tuple(p2000.parts[-8:-6]) == ("laz", "pl_2000_evrf2007")

    def test_laz_system_from_tile_overrides_identifier(self, tmp_path):
        """Finding 8: a PL-2000:S6 tile with a hyphenated code lands in pl_2000.

        Also through the library API (previously the library gave pl_1992 and
        the CLI pl_2000).
        """
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        path = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz", system="2000")
        assert tuple(path.parts[-10:-8]) == ("laz", "pl_2000_evrf2007")

    def test_laz_unknown_system_rejected(self, tmp_path):
        with pytest.raises(ValidationError):
            FileStorage(
                tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
            ).get_raw_path("N-33-131-B-a-1-1-4", "a.laz", system="1965")

    def test_unresolved_vcrs_raises(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs=None)
        with pytest.raises(ValidationError, match="vcrs"):
            storage.get_path("N-34-130-D-d-2-4", ".asc")

    def test_empty_vcrs_raises_instead_of_dangling_segment(self, tmp_path):
        """An empty ``vertical_crs`` means no dimension, not an empty dimension.

        It used to give a silent ``nmt/pl_1992_1m_`` segment - less readable
        than an unresolved brace and invisible to ``_ensure_resolved``.
        """
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="")
        with pytest.raises(ValidationError, match="vcrs"):
            storage.get_path("N-34-130-D-d-2-4", ".asc")

    def test_unknown_product_passthrough(self, tmp_path):
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        assert storage.get_path("6.179.12.20", ".asc") == (
            tmp_path / "nmt_2000_1m" / "6" / "179" / "12" / "20" / "6.179.12.20.asc"
        )

    def test_subdir_override_fills_vcrs(self, tmp_path):
        storage = FileStorage(
            tmp_path, subdir="nmt/cz_dmr5g_{vcrs}", vertical_crs="Bpv", resolution="1m"
        )
        assert storage.get_raw_path("302_5550", "302_5550.tif") == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        )

    def test_list_files_spans_both_systems(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        storage.write_atomic("N-34-130-D-d-2-4", b"x", ".asc")
        storage.write_atomic("6.179.12.20", b"y", ".asc")
        assert len(storage.list_files("**/*.asc")) == 2

    def test_delete_with_sidecar_in_new_layout(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        path = storage.write_atomic("6.179.12.20", b"x", ".asc")
        sidecar = path.with_name(path.name + ".meta.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        assert storage.delete("6.179.12.20", ".asc") is True
        assert not path.exists() and not sidecar.exists()

    @pytest.mark.parametrize(
        ("kwargs", "key", "sheet", "expected"),
        [
            (
                {"resolution": "1m"},
                "pl.gugik.nmt_1m",
                "N-34-130-D-d-2-4",
                "nmt/test_1992_evrf2007",
            ),
            (
                {"product": "nmpt", "resolution": "1m"},
                "pl.gugik.nmpt",
                "N-34-130-D-d-2-4",
                "nmpt/test_1992_evrf2007",
            ),
        ],
    )
    def test_segment_templates_come_from_registry(
        self, tmp_path, monkeypatch, kwargs, key, sheet, expected
    ):
        """Finding 11: one source of truth - the template comes from the descriptor.

        Not a copy in FileStorage (ADR-026: a new source = a new descriptor
        entry, no path code changes).
        """
        from dataclasses import replace

        from kartograf.download import storage as storage_mod
        from kartograf.sources.registry import get_source as real_get_source

        def fake_get_source(k):
            d = real_get_source(k)
            if k == key:
                return replace(
                    d, storage_subdir=expected.split("/")[0] + "/test_{system}_{vcrs}"
                )
            return d

        monkeypatch.setattr(storage_mod, "get_source", fake_get_source)
        storage = FileStorage(
            tmp_path, **{"resolution": None, "vertical_crs": "EVRF2007", **kwargs}
        )
        path = storage.get_path(sheet, ".asc")
        assert expected in path.as_posix()


def _grid_labels(product: str) -> list[str]:
    """Labels of the product's PL ASC grids in the variant registry, ascending."""
    by_value = {
        v.resolution_m: v.label
        for v in variants(product=product, country="PL", format="ASC")
        if v.resolution_m is not None and v.label is not None
    }
    return [by_value[value] for value in sorted(by_value)]


class TestRegistryVariantStorage:
    """ADR-041: the segment of an NMT/NMPT file is the descriptor of its
    variant in the registry (labels K2, archive formats) - in the public
    ``FileStorage`` and in a real sheet download."""

    SHEET = "N-33-58-A-c-1-4"
    HIERARCHY = ("N-33", "58", "A", "c", "1", "4")

    @pytest.mark.parametrize(
        ("kwargs", "segment", "ext"),
        [
            (
                {"resolution": "0.5m", "vertical_crs": "EVRF2007"},
                ("nmt", "pl_1992_0.5m_evrf2007"),
                ".asc",
            ),
            (
                {"product": "nmpt", "resolution": "0.6m", "vertical_crs": "EVRF2007"},
                ("nmpt", "pl_1992_0.6m_evrf2007"),
                ".asc",
            ),
            (
                {"resolution": "25m", "vertical_crs": "KRON86", "format": "TBD"},
                ("nmt", "pl_1992_tbd_25m_kron86"),
                ".zip",
            ),
            (
                {"resolution": None, "vertical_crs": "KRON86", "format": "TIN"},
                ("nmt", "pl_1992_tin_kron86"),
                ".zip",
            ),
        ],
        ids=["nmt-0.5m", "nmpt-0.6m", "archive-tbd-25m", "archive-tin"],
    )
    def test_filestorage_public_constructor_accepts_registry_labels(
        self, tmp_path, kwargs, segment, ext
    ):
        storage = FileStorage(tmp_path, **kwargs)

        path = storage.get_path(self.SHEET, ext)

        assert path.relative_to(tmp_path).parts == (
            *segment,
            *self.HIERARCHY,
            f"{self.SHEET}{ext}",
        )

    @pytest.mark.parametrize(
        ("product", "resolution"),
        [("nmt", "2m"), ("nmpt", "2m"), ("nmpt", None)],
        ids=["nmt-2m", "nmpt-2m", "nmpt-without-resolution"],
    )
    def test_filestorage_unknown_label_lists_registry_labels(
        self, tmp_path, product, resolution
    ):
        """No default and no label outside the registry: the error lists the
        product's grid labels, ascending."""
        with pytest.raises(ValidationError) as exc:
            FileStorage(
                tmp_path,
                product=product,
                resolution=resolution,
                vertical_crs="EVRF2007",
            )

        message = str(exc.value)
        assert message.startswith(f"Nieobslugiwana rozdzielczosc: '{resolution}'")
        listed = re.findall(r"'([^']+)'", message.split("Obslugiwane", 1)[1])
        assert listed == _grid_labels(product)

    def test_segment_from_variant(self, tmp_path):
        """A real 0.5m sheet download (recorded WFS answer of the sheet, a small
        ASC inside its frame): file, version and sidecar name the 0.5m variant
        and the WFS record it came from."""
        url = (
            "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/84020/"
            f"84020_1844081_{self.SHEET}.asc"
        )
        frame = SheetParser(self.SHEET).get_bbox(crs="EPSG:2180")
        body = (
            f"ncols 2\nnrows 2\nxllcorner {frame.min_x + 10}\n"
            f"yllcorner {frame.min_y + 10}\ncellsize 0.5\nNODATA_value -9999\n"
            "1 2\n3 4\n"
        ).encode("ascii")
        endpoint = wfs_endpoint("nmt_evrf2007")
        index = wfs_fixture(f"sheet_nmt_evrf2007_{self.SHEET}.xml")

        def get(requested, **kwargs):
            if requested.startswith(f"{endpoint}?"):
                return wfs_response(index)
            assert requested == url
            response = Mock(spec=requests.Response)
            response.status_code = 200
            response.raise_for_status = Mock()
            response.headers = {}
            response.iter_content = Mock(return_value=[body])
            return response

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=get)
        with patch("kartograf.transport.http.make_gugik_session", return_value=session):
            report = download_data(
                product="nmt",
                output_dir=tmp_path,
                sheet=self.SHEET,
                vertical_crs="EVRF2007",
                resolution="0.5m",
                cache=False,
            )

        assert report.ok, report.failed
        (unit,) = report.files
        path = unit.file.path
        assert path.relative_to(tmp_path).parts == (
            "nmt",
            "pl_1992_0.5m_evrf2007",
            *self.HIERARCHY,
            f"{self.SHEET}.asc",
        )
        sha8 = hashlib.sha256(body).hexdigest()[:8]
        assert unit.file.version_path.parent.name == f"2025-01-30_84020_{sha8}"
        meta = json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))
        assert meta["dataset"] == "pl.gugik.nmt_0_5m"
        assert meta["resolution"] == "0.5m"
        source = meta["extra"]["source"]
        assert source["layer"] == "SkorowidzNMT2025"
        assert source["index_url"] == endpoint
        assert source["url"] == url


class TestPruneEmptyDirs:
    """Finding 10: a failure does not leave an empty <segment>/bbox/ tree."""

    def test_removes_empty_chain_but_not_stop(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        leaf = tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox"
        leaf.mkdir(parents=True)
        prune_empty_dirs(leaf, tmp_path)
        assert not (tmp_path / "nmt").exists() and tmp_path.exists()

    def test_stops_at_non_empty_parent(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        leaf = tmp_path / "nmt" / "seg" / "bbox"
        leaf.mkdir(parents=True)
        (tmp_path / "nmt" / "seg" / "arkusz.asc").write_text("x")
        prune_empty_dirs(leaf, tmp_path)
        assert not leaf.exists() and (tmp_path / "nmt" / "seg").exists()

    def test_never_touches_outside_stop(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        outside = tmp_path / "a" / "b"
        outside.mkdir(parents=True)
        prune_empty_dirs(outside, tmp_path / "other")
        assert outside.exists()


class TestStorageVariant:
    """E12: product variant as a segment suffix (orto CIR/B-W)."""

    def test_variant_suffix_and_default_without_suffix(self, tmp_path):
        g = "N-34-130-D-d-2-4"
        rgb = FileStorage(
            tmp_path, resolution=None, vertical_crs=None, product="orto"
        ).get_path(g, ".tif")
        cir = FileStorage(
            tmp_path,
            product="orto",
            variant="cir",
            resolution="1m",
            vertical_crs="EVRF2007",
        ).get_path(g, ".tif")

        assert rgb.relative_to(tmp_path).parts[:2] == ("orto", "pl_1992")
        assert cir.relative_to(tmp_path).parts[:2] == ("orto", "pl_1992_cir")

    @pytest.mark.parametrize("variant", ["", "CIR", "b/w", "_cir"])
    def test_invalid_variant_rejected(self, tmp_path, variant):
        with pytest.raises(ValidationError, match="wariant"):
            FileStorage(
                tmp_path,
                product="orto",
                variant=variant,
                resolution="1m",
                vertical_crs="EVRF2007",
            )


class TestStorageForProvider:
    """D18: the single FileStorage factory for a provider segment."""

    G = "N-34-130-D-d-2-4"

    def _segment(self, storage, tmp_path, ext=".asc"):
        return storage.get_path(self.G, ext).relative_to(tmp_path).parts[:2]

    def test_without_provider_uses_nmt_resolution_template(self, tmp_path):
        from kartograf.download.storage import storage_for_provider

        storage = storage_for_provider(
            tmp_path, None, resolution="5m", vertical_crs="EVRF2007"
        )
        assert self._segment(storage, tmp_path) == ("nmt", "pl_1992_5m_evrf2007")

    def test_descriptor_segment_and_provider_vertical_win(self, tmp_path):
        """The provider's ACTUAL vertical CRS wins over the caller's argument."""
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(
            descriptor_key="pl.gugik.nmpt", vertical_crs="KRON86"
        )
        storage = storage_for_provider(
            tmp_path, provider, resolution="1m", vertical_crs="EVRF2007"
        )
        assert self._segment(storage, tmp_path) == ("nmpt", "pl_1992_1m_kron86")

    def test_variant_suffix(self, tmp_path):
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(
            descriptor_key="pl.gugik.orto", vertical_crs=None, storage_variant="cir"
        )
        storage = storage_for_provider(
            tmp_path, provider, resolution=None, vertical_crs=None
        )
        assert self._segment(storage, tmp_path, ".tif") == ("orto", "pl_1992_cir")

    def test_cz_descriptor_segment(self, tmp_path):
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(descriptor_key="cz.cuzk.dmr5g", vertical_crs="Bpv")
        storage = storage_for_provider(
            tmp_path, provider, resolution="2m", vertical_crs="Bpv"
        )
        assert storage._subdir == "nmt/cz_dmr5g_bpv"

    def test_mock_attributes_are_ignored(self, tmp_path):
        """Mock(spec=...) gives a Mock instead of str — fall back to the arguments."""
        from unittest.mock import Mock

        from kartograf.download.storage import storage_for_provider
        from kartograf.providers.pl.gugik import GugikProvider

        storage = storage_for_provider(
            tmp_path, Mock(spec=GugikProvider), resolution="1m", vertical_crs="KRON86"
        )
        assert self._segment(storage, tmp_path) == ("nmt", "pl_1992_1m_kron86")


# --- spec 3: version store paths ---
VERSION_DIR = "2025-04-27_83233_3fa91c2e"


class TestVersionPaths:
    def test_versions_root_mirrors_hierarchy(self, tmp_path):
        st = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        g = "N-34-139-C-a-3-1"
        assert st.get_versions_root(g) == (
            tmp_path / "nmt/pl_1992_1m_evrf2007/versions/N-34/139/C/a/3/1"
        )
        assert st.get_versions_base(g) == tmp_path / "nmt/pl_1992_1m_evrf2007/versions"
        assert st.get_versions_root("M-33-036-A-a-1-1") == st.get_versions_root(
            "M-33-36-A-a-1-1"
        )

    def test_versions_root_keeps_orto_variant_and_pl2000_segment(self, tmp_path):
        orto = FileStorage(
            tmp_path,
            product="orto",
            variant="cir",
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        assert "orto/pl_1992_cir/versions/" in (
            orto.get_versions_root("M-34-90-C-b-4-4").as_posix()
        )
        nmt = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        assert nmt.get_versions_root("6.129.30.13.4").relative_to(tmp_path).parts[
            :3
        ] == ("nmt", "pl_2000_1m_evrf2007", "versions")

    def test_list_files_standard_paths_or_versions_only(self, tmp_path):
        st = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        g = "N-34-139-C-a-3-1"
        version = st.get_versions_root(g) / VERSION_DIR / f"{g}.asc"
        staged = st.get_versions_base(g) / ".incoming" / "h_1_ab" / f"{g}.asc"
        legacy = st.get_versions_base(g).parent / "kampanie" / "x" / f"{g}.asc"
        std = st.get_path(g, ".asc")
        full = st.get_full_sheet_path(g, ".asc")
        for p in (version, staged, legacy, std, full):
            p.parent.mkdir(parents=True)
            p.write_text("x")
        assert st.list_files("**/*.asc") == [std]
        assert st.list_files("**/*.asc", versions=True) == [version]

    def test_has_legacy_campaigns(self, tmp_path):
        st = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        assert st.has_legacy_campaigns() is False
        (tmp_path / "nmt/pl_2000_1m_evrf2007/kampanie").mkdir(parents=True)
        assert st.has_legacy_campaigns() is True

    def test_full_sheet_path_mirrors_standard_hierarchy(self, tmp_path):
        st = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        g = "N-34-139-C-a-3-1"
        assert st.get_full_sheet_path(g, ".asc") == (
            tmp_path
            / "nmt/pl_1992_1m_evrf2007/full_sheet"
            / "N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc"
        )
        std = st.get_path(g, ".asc").relative_to(tmp_path / "nmt/pl_1992_1m_evrf2007")
        full = st.get_full_sheet_path(g, ".asc").relative_to(
            tmp_path / "nmt/pl_1992_1m_evrf2007/full_sheet"
        )
        assert full == std
        p = st.get_full_sheet_path("6.129.30.13.4", ".asc")
        assert p.relative_to(tmp_path).parts[:3] == (
            "nmt",
            "pl_2000_1m_evrf2007",
            "full_sheet",
        )

    def test_delete_removes_standard_and_full_sheet_links_keeps_version(self, tmp_path):
        st = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        g = "N-34-139-C-a-3-1"
        version = st.get_versions_root(g) / VERSION_DIR / f"{g}.asc"
        version.parent.mkdir(parents=True)
        version.write_text("x")
        links = [st.get_path(g, ".asc"), st.get_full_sheet_path(g, ".asc")]
        for link in links:
            link.parent.mkdir(parents=True)
            os.link(version, link)
            link.with_name(link.name + ".meta.json").write_text("{}")
        assert st.delete(g, ".asc") is True
        for link in links:
            assert not link.exists()
            assert not link.with_name(link.name + ".meta.json").exists()
        assert version.read_text() == "x" and version.stat().st_nlink == 1
        # only the full_sheet/ link left: still a deletion
        os.link(version, links[1])
        assert st.delete(g, ".asc") is True
        assert not links[1].exists()
        assert st.delete(g, ".asc") is False


def test_leading_zero_sheet_same_path_and_sidecar(tmp_path):
    """A7: '036' and '36' -> one path, one canonical code everywhere."""
    import json
    from unittest.mock import Mock

    from kartograf.download.manager import DownloadManager

    storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
    assert storage.get_path("M-33-036-A-a-1-1", ".asc") == storage.get_path(
        "M-33-36-A-a-1-1", ".asc"
    )

    provider = Mock(
        spec=[
            "download",
            "descriptor_key",
            "supports_campaigns",
            "default_extension",
            "vertical_crs",
            "resolution",
        ]
    )
    provider.supports_campaigns = False
    provider.descriptor_key = "pl.gugik.nmt_1m"
    provider.default_extension = ".asc"
    provider.vertical_crs = "EVRF2007"
    provider.resolution = "1m"

    def fake_download(sheet, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n0\n")
        return target

    provider.download.side_effect = fake_download
    manager = DownloadManager(output_dir=tmp_path, provider=provider)
    path = manager.download_sheet("M-33-036-A-a-1-1").succeeded[0]
    assert path.name == "M-33-36-A-a-1-1.asc"
    assert provider.download.call_args[0][0] == "M-33-36-A-a-1-1"
    meta = json.loads(path.with_name(path.name + ".meta.json").read_text())
    assert meta["request"]["sheet"] == "M-33-36-A-a-1-1"


class TestVersionSlots:
    """Version roots of opaque identifiers and bbox cutouts (plan 2/3 Task 4)."""

    def test_raw_versions_root_follows_hierarchy_and_system(self, tmp_path):
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        sheet = "N-33-131-B-a-1-1-4"
        root = storage.get_raw_versions_root(sheet, system="2000")
        base = tmp_path / "laz" / "pl_2000_evrf2007" / "versions"
        assert storage.get_raw_versions_base(sheet, system="2000") == base
        std = storage.get_raw_path(sheet, "a.laz", system="2000")
        hierarchy = std.parent.relative_to(tmp_path / "laz" / "pl_2000_evrf2007")
        assert root == base / hierarchy
        default = storage.get_raw_versions_root(sheet).relative_to(tmp_path)
        assert default.parts[:3] == ("laz", "pl_1992_evrf2007", "versions")
        with pytest.raises(ValidationError):
            storage.get_raw_versions_root(sheet, system="1965")

    def test_bbox_slot_paths(self, tmp_path):
        bbox = BBox(500000.0, 600000.0, 500500.5, 600500.0, "EPSG:2180")
        slot = bbox_slot(tmp_path, "nmt/pl_1992_1m_evrf2007", bbox, ".tif")
        segment = tmp_path / "nmt" / "pl_1992_1m_evrf2007"
        assert slot.std == segment / "bbox" / "500000_600000_500500.5_600500.tif"
        assert slot.versions_root == segment / "versions" / "bbox"
        assert slot.versions_base == segment / "versions"
        assert (slot.segment, slot.hierarchy) == ("nmt/pl_1992_1m_evrf2007", "bbox")
        assert slot.name == slot.std.name
