"""
Testy jednostkowe dla modułu storage.

Ten moduł zawiera testy dla klasy FileStorage, weryfikujące poprawność
generowania ścieżek i operacji na plikach.
"""

import io
import os

import pytest  # noqa: F401 - required for fixtures

from kartograf.download.storage import FileStorage
from kartograf.exceptions import ValidationError


class TestFileStorageBasic:
    """Testy podstawowej funkcjonalności FileStorage."""

    def test_init_default_directory(self):
        """Test inicjalizacji z domyślnym katalogiem."""
        storage = FileStorage()
        assert str(storage.output_dir) == "data"

    def test_init_custom_directory(self):
        """Test inicjalizacji z własnym katalogiem."""
        storage = FileStorage("/custom/path")
        assert str(storage.output_dir) == "/custom/path"

    def test_repr(self):
        """Test reprezentacji tekstowej."""
        storage = FileStorage("./data")
        assert "FileStorage" in repr(storage)
        assert "data" in repr(storage)


class TestFileStorageGetPath:
    """Testy metody get_path()."""

    def test_get_path_1m(self):
        """Test ścieżki dla skali 1:1000000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34", ".tif")

        assert path.name == "N-34.tif"
        assert "N-34" in str(path)

    def test_get_path_500k(self):
        """Test ścieżki dla skali 1:500000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34-A", ".tif")

        assert path.name == "N-34-A.tif"
        assert "N-34" in str(path)
        assert "A" in str(path)

    def test_get_path_200k(self):
        """Test ścieżki dla skali 1:200000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34-130", ".tif")

        assert path.name == "N-34-130.tif"
        assert "N-34" in str(path)
        assert "130" in str(path)

    def test_get_path_100k(self):
        """Test ścieżki dla skali 1:100000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34-130-D", ".tif")

        assert path.name == "N-34-130-D.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts

    def test_get_path_50k(self):
        """Test ścieżki dla skali 1:50000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34-130-D-d", ".tif")

        assert path.name == "N-34-130-D-d.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts
        assert "d" in parts

    def test_get_path_25k(self):
        """Test ścieżki dla skali 1:25000."""
        storage = FileStorage("./data")
        path = storage.get_path("N-34-130-D-d-2", ".tif")

        assert path.name == "N-34-130-D-d-2.tif"
        parts = str(path).split("/")
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts
        assert "d" in parts
        assert "2" in parts

    def test_get_path_10k(self):
        """Test ścieżki dla skali 1:10000."""
        storage = FileStorage("./data")
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
        """Test różnych rozszerzeń plików."""
        storage = FileStorage("./data")

        path_tif = storage.get_path("N-34-130-D", ".tif")
        path_asc = storage.get_path("N-34-130-D", ".asc")
        path_xyz = storage.get_path("N-34-130-D", ".xyz")

        assert path_tif.suffix == ".tif"
        assert path_asc.suffix == ".asc"
        assert path_xyz.suffix == ".xyz"

    def test_get_path_normalizes_godlo(self):
        """Test normalizacji godła w ścieżce."""
        storage = FileStorage("./data")

        # Małe litery powinny być znormalizowane
        path = storage.get_path("n-34-130-d")

        assert "N-34-130-D" in path.name


class TestFileStorageEnsureDirectory:
    """Testy metody ensure_directory()."""

    def test_ensure_directory_creates_dirs(self, tmp_path):
        """Test tworzenia katalogów."""
        storage = FileStorage(tmp_path)
        dir_path = storage.ensure_directory("N-34-130-D-d-2-4")

        assert dir_path.exists()
        assert dir_path.is_dir()

    def test_ensure_directory_idempotent(self, tmp_path):
        """Test że wielokrotne wywołanie nie powoduje błędów."""
        storage = FileStorage(tmp_path)

        dir_path1 = storage.ensure_directory("N-34-130-D")
        dir_path2 = storage.ensure_directory("N-34-130-D")

        assert dir_path1 == dir_path2
        assert dir_path1.exists()


class TestFileStorageExists:
    """Testy metody exists()."""

    def test_exists_false_when_not_present(self, tmp_path):
        """Test że exists() zwraca False gdy plik nie istnieje."""
        storage = FileStorage(tmp_path)

        assert storage.exists("N-34-130-D") is False

    def test_exists_true_when_present(self, tmp_path):
        """Test że exists() zwraca True gdy plik istnieje."""
        storage = FileStorage(tmp_path)

        # Create the file
        storage.write_atomic("N-34-130-D", b"test data")

        assert storage.exists("N-34-130-D") is True


class TestFileStorageWriteAtomic:
    """Testy metody write_atomic()."""

    def test_write_atomic_bytes(self, tmp_path):
        """Test atomowego zapisu bajtów."""
        storage = FileStorage(tmp_path)
        content = b"test data content"

        path = storage.write_atomic("N-34-130-D", content)

        assert path.exists()
        assert path.read_bytes() == content

    def test_write_atomic_file_object(self, tmp_path):
        """Test atomowego zapisu z obiektu plikowego."""
        storage = FileStorage(tmp_path)
        content = b"test data from file object"
        file_obj = io.BytesIO(content)

        path = storage.write_atomic("N-34-130-D", file_obj)

        assert path.exists()
        assert path.read_bytes() == content

    def test_write_atomic_creates_directories(self, tmp_path):
        """Test że write_atomic tworzy katalogi."""
        storage = FileStorage(tmp_path)

        path = storage.write_atomic("N-34-130-D-d-2-4", b"data")

        assert path.exists()
        assert path.parent.exists()

    def test_write_atomic_no_temp_file_on_success(self, tmp_path):
        """Test że nie pozostaje plik tymczasowy po sukcesie."""
        storage = FileStorage(tmp_path)

        path = storage.write_atomic("N-34-130-D", b"data")
        temp_path = path.with_suffix(".tif.tmp")

        assert path.exists()
        assert not temp_path.exists()

    def test_write_atomic_overwrites_existing(self, tmp_path):
        """Test że write_atomic nadpisuje istniejący plik."""
        storage = FileStorage(tmp_path)

        storage.write_atomic("N-34-130-D", b"old content")
        path = storage.write_atomic("N-34-130-D", b"new content")

        assert path.read_bytes() == b"new content"


class TestFileStorageDelete:
    """Testy metody delete()."""

    def test_delete_existing_file(self, tmp_path):
        """Test usuwania istniejącego pliku."""
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D", b"data")

        result = storage.delete("N-34-130-D")

        assert result is True
        assert not storage.exists("N-34-130-D")

    def test_delete_nonexistent_file(self, tmp_path):
        """Test usuwania nieistniejącego pliku."""
        storage = FileStorage(tmp_path)

        result = storage.delete("N-34-130-D")

        assert result is False


class TestFileStorageListFiles:
    """Testy metody list_files()."""

    def test_list_files_empty(self, tmp_path):
        """Test pustego katalogu."""
        storage = FileStorage(tmp_path)

        files = storage.list_files()

        assert files == []

    def test_list_files_with_files(self, tmp_path):
        """Test z istniejącymi plikami."""
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-A", b"data1")
        storage.write_atomic("N-34-130-B", b"data2")
        storage.write_atomic("N-34-130-C", b"data3")

        files = storage.list_files()

        assert len(files) == 3

    def test_list_files_with_pattern(self, tmp_path):
        """Test z wzorcem."""
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-A", b"data1", ".tif")
        storage.write_atomic("N-34-130-B", b"data2", ".asc")

        tif_files = storage.list_files("**/*.tif")
        asc_files = storage.list_files("**/*.asc")

        assert len(tif_files) == 1
        assert len(asc_files) == 1

    def test_list_files_nonexistent_directory(self):
        """Test dla nieistniejącego katalogu."""
        storage = FileStorage("/nonexistent/path")

        files = storage.list_files()

        assert files == []


class TestFileStorageGetSize:
    """Testy metody get_size()."""

    def test_get_size_existing_file(self, tmp_path):
        """Test rozmiaru istniejącego pliku."""
        storage = FileStorage(tmp_path)
        content = b"test data content"
        storage.write_atomic("N-34-130-D", content)

        size = storage.get_size("N-34-130-D")

        assert size == len(content)

    def test_get_size_nonexistent_file(self, tmp_path):
        """Test rozmiaru nieistniejącego pliku."""
        storage = FileStorage(tmp_path)

        size = storage.get_size("N-34-130-D")

        assert size is None


class TestFileStorageDirectoryStructure:
    """Testy struktury katalogów."""

    def test_directory_structure_10k(self, tmp_path):
        """Test pełnej struktury katalogów dla 1:10k."""
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D-d-2-4", b"data")

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
        """Test że wiele plików dzieli wspólne katalogi nadrzędne."""
        storage = FileStorage(tmp_path)

        # Write files that share common directories (same 1:25k parent)
        storage.write_atomic("N-34-130-D-d-2-1", b"data1")
        storage.write_atomic("N-34-130-D-d-2-2", b"data2")
        storage.write_atomic("N-34-130-D-d-2-3", b"data3")
        storage.write_atomic("N-34-130-D-d-2-4", b"data4")

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
        storage = FileStorage(tmp_path, product="nmpt")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")

        parts = str(path).split("/")
        assert "nmpt" in parts
        assert "nmt_1m" not in parts

    def test_product_orto_subdir(self, tmp_path):
        """Test that product='orto' uses orto as subdirectory."""
        storage = FileStorage(tmp_path, product="orto")
        path = storage.get_path("N-34-130-D-d-2-4", ".tif")

        parts = str(path).split("/")
        assert "orto" in parts
        assert path.name == "N-34-130-D-d-2-4.tif"

    def test_product_none_backward_compatible(self, tmp_path):
        """Test that product=None preserves resolution-based behavior."""
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.get_path("N-34-130-D", ".asc")

        parts = str(path).split("/")
        assert "pl_1992_1m_evrf2007" in parts

    def test_product_subdir_structure(self, tmp_path):
        """Test full directory structure with product."""
        storage = FileStorage(tmp_path, product="orto")
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

    def test_product_skips_resolution_validation(self, tmp_path):
        """Test that product mode skips resolution validation."""
        # Should not raise ValueError even though resolution default is "1m"
        storage = FileStorage(tmp_path, product="custom_product")
        assert storage._product == "custom_product"

    def test_product_repr(self, tmp_path):
        """Test repr includes product."""
        storage = FileStorage(tmp_path, product="nmpt")
        repr_str = repr(storage)

        assert "product='nmpt'" in repr_str

    def test_resolution_subdir_nmt_1m(self, tmp_path):
        """Test that resolution='1m' maps to 'nmt/pl_1992_1m_evrf2007' subdirectory."""
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.get_path("N-34-130-D", ".asc")

        assert "/nmt/pl_1992_1m_evrf2007/" in str(path)

    def test_resolution_subdir_nmt_5m(self, tmp_path):
        """Test that resolution='5m' maps to 'nmt/pl_1992_5m_evrf2007' subdirectory."""
        storage = FileStorage(tmp_path, resolution="5m")
        path = storage.get_path("N-34-130-D", ".asc")

        assert "/nmt/pl_1992_5m_evrf2007/" in str(path)


class TestFileStoragePL2000:
    """Testy struktury katalogów dla godeł PL-2000 (format z kropkami)."""

    def test_get_path_pl2000_10k(self, tmp_path):
        """Test ścieżki dla PL-2000 1:10000 (3 komponenty: strefa.pas.slup)."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        path = storage.get_path("6.179.12")

        assert path.name == "6.179.12.asc"
        parts = path.relative_to(tmp_path).parts
        assert "nmt_2000_1m" in parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts

    def test_get_path_pl2000_2k(self, tmp_path):
        """Test ścieżki dla PL-2000 1:2000 (4 komponenty: strefa.pas.slup.ark_2k)."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        path = storage.get_path("6.179.12.20")

        assert path.name == "6.179.12.20.asc"
        parts = path.relative_to(tmp_path).parts
        assert "nmt_2000_1m" in parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "20" in parts

    def test_get_path_pl2000_1k(self, tmp_path):
        """Test ścieżki dla PL-2000 1:1000 (5 komponentów)."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        path = storage.get_path("6.179.12.20.3")

        assert path.name == "6.179.12.20.3.asc"
        parts = path.relative_to(tmp_path).parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "20" in parts
        assert "3" in parts

    def test_get_path_pl2000_5k(self, tmp_path):
        """Test ścieżki dla PL-2000 1:5000 (4 komponenty: strefa.pas.slup.ark_5k)."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        path = storage.get_path("6.179.12.2")

        assert path.name == "6.179.12.2.asc"
        parts = path.relative_to(tmp_path).parts
        assert "6" in parts
        assert "179" in parts
        assert "12" in parts
        assert "2" in parts

    def test_get_path_pl1992_unchanged(self, tmp_path):
        """Test że PL-1992 godło nie jest dotknięte zmianami PL-2000."""
        storage = FileStorage(tmp_path, product="nmt_1m")
        path = storage.get_path("N-34-130-D-d-2-4")

        assert path.name == "N-34-130-D-d-2-4.asc"
        parts = path.relative_to(tmp_path).parts
        assert "N-34" in parts
        assert "130" in parts
        assert "D" in parts

    def test_exists_pl2000_false(self, tmp_path):
        """Test że exists() zwraca False dla nieistniejącego pliku PL-2000."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        assert not storage.exists("6.179.12.20")

    def test_write_and_exists_pl2000(self, tmp_path):
        """Test zapisu i sprawdzenia istnienia pliku PL-2000."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        storage.write_atomic("6.179.12.20", b"PL-2000 data")

        assert storage.exists("6.179.12.20")

    def test_directory_structure_pl2000_2k(self, tmp_path):
        """Test pełnej struktury katalogów dla PL-2000 1:2000."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        storage.write_atomic("6.179.12.20", b"data")

        expected_parts = ["nmt_2000_1m", "6", "179", "12", "20"]
        current_dir = tmp_path

        for part in expected_parts:
            current_dir = current_dir / part
            assert current_dir.exists(), f"Directory {current_dir} should exist"
            assert current_dir.is_dir(), f"{current_dir} should be a directory"

        file_path = current_dir / "6.179.12.20.asc"
        assert file_path.exists()

    def test_multiple_files_share_directories_pl2000(self, tmp_path):
        """Test że pliki PL-2000 z tego samego 10k dzielą katalogi nadrzędne."""
        storage = FileStorage(tmp_path, product="nmt_2000_1m")

        # Kilka arkuszy 1:2000 w jednym 1:10000
        storage.write_atomic("6.179.12.01", b"data1")
        storage.write_atomic("6.179.12.02", b"data2")
        storage.write_atomic("6.179.12.25", b"data3")

        # Wspólny katalog nadrzędny (1:10k level)
        common_parent = tmp_path / "nmt_2000_1m" / "6" / "179" / "12"
        assert common_parent.exists()

        subdirs = list(common_parent.iterdir())
        assert len(subdirs) == 3


class TestFileStorageGetRawPath:
    """Tests for get_raw_path (opaque identifiers, e.g. LAZ tile godła)."""

    def test_raw_path_pl1992_fine_godlo(self, tmp_path):
        """Fine PL-1992 godło (finer than 1:10000) is split without parsing."""
        storage = FileStorage(tmp_path, product="laz")
        path = storage.get_raw_path(
            "N-33-131-B-a-1-1-4", "81121_1573132_N-33-131-B-a-1-1-4.laz"
        )
        parts = str(path).split("/")
        assert "laz" in parts
        # Hierarchy: base "N-33" then each remaining component
        assert parts[-8:-1] == ["N-33", "131", "B", "a", "1", "1", "4"]
        assert path.name == "81121_1573132_N-33-131-B-a-1-1-4.laz"

    def test_raw_path_pl2000_godlo(self, tmp_path):
        """PL-2000 dotted godło is split on dots."""
        storage = FileStorage(tmp_path, product="laz")
        path = storage.get_raw_path("6.162.34.02.3", "x_6.162.34.02.3.laz")
        parts = str(path).split("/")
        assert parts[-6:-1] == ["6", "162", "34", "02", "3"]
        assert path.name == "x_6.162.34.02.3.laz"

    def test_raw_path_does_not_parse_identifier(self, tmp_path):
        """A non-parseable identifier must NOT raise (unlike get_path)."""
        storage = FileStorage(tmp_path, product="laz")
        # get_path would raise ParseError on this; get_raw_path must not
        path = storage.get_raw_path("M-34-27-B-b-2-1-1", "f.laz")
        assert path.name == "f.laz"
        assert "laz" in str(path).split("/")

    def test_raw_path_preserves_original_filename(self, tmp_path):
        """The provided filename is used verbatim (preserves density/seq id)."""
        storage = FileStorage(tmp_path, product="laz")
        path = storage.get_raw_path("6.1.1", "12345_67890_tile.laz")
        assert path.name == "12345_67890_tile.laz"


class TestSubdirOverride:
    """Etap 0: subdir sterowany deskryptorem (etap 1: np. cz_dmr5g)."""

    def test_subdir_takes_precedence(self, tmp_path):
        storage = FileStorage(tmp_path, subdir="cz_dmr5g")
        path = storage.get_raw_path("302_5550", "302_5550.tif")
        # "302_5550" to godlo TM33 (rejestracja cz_tm33, Zad. 11) — nested
        # katalogi ["302", "5550"] wg path_parts, jak inne systemy wieloczesciowe.
        assert path == tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif"

    def test_subdir_wins_over_product_and_resolution(self, tmp_path):
        storage = FileStorage(
            tmp_path, resolution="5m", product="orto", subdir="wlasny"
        )
        assert storage.get_path("N-34", ".asc") == (
            tmp_path / "wlasny" / "N-34" / "N-34.asc"
        )

    def test_none_keeps_legacy_behavior(self, tmp_path):
        assert FileStorage(tmp_path, resolution="1m").get_path("N-34", ".asc") == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc"
        )
        assert FileStorage(tmp_path, product="nmpt").get_path("N-34", ".asc") == (
            tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc"
        )

    def test_repr_with_subdir(self, tmp_path):
        assert "subdir='cz_dmr5g'" in repr(FileStorage(tmp_path, subdir="cz_dmr5g"))


class TestDeleteRemovesSidecar:
    """delete() nie moze zostawiac osieroconego .meta.json."""

    def test_delete_removes_data_file_and_sidecar(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ncols 1\n", encoding="ascii")
        sidecar = path.with_name(path.name + ".meta.json")
        sidecar.write_text("{}\n", encoding="utf-8")

        assert storage.delete("N-34-130-D-d-2-4") is True
        assert not path.exists()
        assert not sidecar.exists()

    def test_delete_without_sidecar_still_works(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ncols 1\n", encoding="ascii")

        assert storage.delete("N-34-130-D-d-2-4") is True
        assert not path.exists()


class TestFileStorageSegments:
    """Uklad data/ 0.7.0: <produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>] (ADR-026)."""

    def test_default_pl1992_evrf2007(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
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
        """ADR-017 domkniety: PL-2000 nie dzieli juz katalogu z PL-1992."""
        storage = FileStorage(tmp_path, resolution="1m")
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
        storage = FileStorage(tmp_path, resolution="5m")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        assert "pl_1992_5m_evrf2007" in path.parts

    def test_nmpt_segment(self, tmp_path):
        storage = FileStorage(tmp_path, product="nmpt")
        path = storage.get_path("N-34", ".asc")
        assert path == (tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc")

    def test_orto_segment_no_vcrs(self, tmp_path):
        """Orto nie ma pionowego — segment bez {vcrs} takze przy None."""
        storage = FileStorage(tmp_path, product="orto", vertical_crs=None)
        assert storage.get_path("N-34", ".tif") == (
            tmp_path / "orto" / "pl_1992" / "N-34" / "N-34.tif"
        )

    def test_laz_segment_by_identifier(self, tmp_path):
        storage = FileStorage(tmp_path, product="laz")
        p1992 = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz")
        p2000 = storage.get_raw_path("6.162.34.02.3", "b.laz")
        assert tuple(p1992.parts[-10:-8]) == ("laz", "pl_1992_evrf2007")
        assert tuple(p2000.parts[-8:-6]) == ("laz", "pl_2000_evrf2007")

    def test_laz_uklad_from_tile_overrides_identifier(self, tmp_path):
        """Zn. 8: kafel PL-2000:S6 z godlem myslnikowym laduje w pl_2000 takze
        przez API biblioteki (dotad biblioteka dawala pl_1992, a CLI pl_2000)."""
        storage = FileStorage(tmp_path, product="laz")
        path = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz", uklad="2000")
        assert tuple(path.parts[-10:-8]) == ("laz", "pl_2000_evrf2007")

    def test_laz_unknown_uklad_rejected(self, tmp_path):
        with pytest.raises(ValidationError):
            FileStorage(tmp_path, product="laz").get_raw_path(
                "N-33-131-B-a-1-1-4", "a.laz", uklad="1965"
            )

    def test_unresolved_vcrs_raises(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs=None)
        with pytest.raises(ValidationError, match="vcrs"):
            storage.get_path("N-34-130-D-d-2-4", ".asc")

    def test_empty_vcrs_raises_instead_of_dangling_segment(self, tmp_path):
        """Pusty ``vertical_crs`` to brak wymiaru, nie wymiar pusty.

        Dotad dawal cichy segment ``nmt/pl_1992_1m_`` — mniej czytelny niz
        nierozwiazana klamra i niewidoczny dla ``_ensure_resolved``.
        """
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="")
        with pytest.raises(ValidationError, match="vcrs"):
            storage.get_path("N-34-130-D-d-2-4", ".asc")

    def test_unknown_product_passthrough(self, tmp_path):
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        assert storage.get_path("6.179.12.20", ".asc") == (
            tmp_path / "nmt_2000_1m" / "6" / "179" / "12" / "20" / "6.179.12.20.asc"
        )

    def test_subdir_override_fills_vcrs(self, tmp_path):
        storage = FileStorage(
            tmp_path, subdir="nmt/cz_dmr5g_{vcrs}", vertical_crs="Bpv"
        )
        assert storage.get_raw_path("302_5550", "302_5550.tif") == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        )

    def test_list_files_spans_both_uklady(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        storage.write_atomic("N-34-130-D-d-2-4", b"x", ".asc")
        storage.write_atomic("6.179.12.20", b"y", ".asc")
        assert len(storage.list_files()) == 2

    def test_delete_with_sidecar_in_new_layout(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.write_atomic("6.179.12.20", b"x", ".asc")
        sidecar = path.with_name(path.name + ".meta.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        assert storage.delete("6.179.12.20") is True
        assert not path.exists() and not sidecar.exists()

    @pytest.mark.parametrize(
        ("kwargs", "key", "godlo", "expected"),
        [
            (
                {"resolution": "1m"},
                "pl.gugik.nmt_1m",
                "N-34-130-D-d-2-4",
                "nmt/test_1992_evrf2007",
            ),
            (
                {"product": "nmpt"},
                "pl.gugik.nmpt",
                "N-34-130-D-d-2-4",
                "nmpt/test_1992_evrf2007",
            ),
        ],
    )
    def test_segment_templates_come_from_registry(
        self, tmp_path, monkeypatch, kwargs, key, godlo, expected
    ):
        """Zn. 11: jedno zrodlo prawdy — szablon z deskryptora, nie kopia w FileStorage
        (ADR-026: nowe zrodlo = nowy wpis deskryptora, zero zmian w kodzie sciezek)."""
        from dataclasses import replace

        from kartograf.download import storage as storage_mod
        from kartograf.sources.registry import get_source as real_get_source

        def fake_get_source(k):
            d = real_get_source(k)
            if k == key:
                return replace(
                    d, storage_subdir=expected.split("/")[0] + "/test_{uklad}_{vcrs}"
                )
            return d

        monkeypatch.setattr(storage_mod, "get_source", fake_get_source)
        path = FileStorage(tmp_path, **kwargs).get_path(godlo, ".asc")
        assert expected in path.as_posix()


class TestPruneEmptyDirs:
    """Zn. 10: porazka nie zostawia pustego drzewa <segment>/bbox/."""

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
    """E12: wariant produktu jako sufiks segmentu (orto CIR/B-W)."""

    def test_variant_suffix_and_default_without_suffix(self, tmp_path):
        g = "N-34-130-D-d-2-4"
        rgb = FileStorage(tmp_path, product="orto").get_path(g, ".tif")
        cir = FileStorage(tmp_path, product="orto", variant="cir").get_path(g, ".tif")

        assert rgb.relative_to(tmp_path).parts[:2] == ("orto", "pl_1992")
        assert cir.relative_to(tmp_path).parts[:2] == ("orto", "pl_1992_cir")

    @pytest.mark.parametrize("variant", ["", "CIR", "b/w", "_cir"])
    def test_invalid_variant_rejected(self, tmp_path, variant):
        with pytest.raises(ValidationError, match="wariant"):
            FileStorage(tmp_path, product="orto", variant=variant)


class TestStorageForProvider:
    """D18: jedyna fabryka FileStorage segmentu providera."""

    G = "N-34-130-D-d-2-4"

    def _segment(self, storage, tmp_path, ext=".asc"):
        return storage.get_path(self.G, ext).relative_to(tmp_path).parts[:2]

    def test_without_provider_uses_nmt_resolution_template(self, tmp_path):
        from kartograf.download.storage import storage_for_provider

        storage = storage_for_provider(tmp_path, resolution="5m")
        assert self._segment(storage, tmp_path) == ("nmt", "pl_1992_5m_evrf2007")

    def test_descriptor_segment_and_provider_vertical_win(self, tmp_path):
        """Pion FAKTYCZNY providera wygrywa z argumentem wolajacego."""
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(
            descriptor_key="pl.gugik.nmpt", vertical_crs="KRON86"
        )
        storage = storage_for_provider(tmp_path, provider, vertical_crs="EVRF2007")
        assert self._segment(storage, tmp_path) == ("nmpt", "pl_1992_1m_kron86")

    def test_variant_suffix(self, tmp_path):
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(
            descriptor_key="pl.gugik.orto", vertical_crs=None, storage_variant="cir"
        )
        storage = storage_for_provider(tmp_path, provider)
        assert self._segment(storage, tmp_path, ".tif") == ("orto", "pl_1992_cir")

    def test_cz_descriptor_segment(self, tmp_path):
        from types import SimpleNamespace

        from kartograf.download.storage import storage_for_provider

        provider = SimpleNamespace(descriptor_key="cz.cuzk.dmr5g", vertical_crs="Bpv")
        storage = storage_for_provider(tmp_path, provider)
        assert storage._subdir == "nmt/cz_dmr5g_bpv"

    def test_mock_attributes_are_ignored(self, tmp_path):
        """Mock(spec=...) daje Mock zamiast str — fallback na argumenty."""
        from unittest.mock import Mock

        from kartograf.download.storage import storage_for_provider
        from kartograf.providers.pl.gugik import GugikProvider

        storage = storage_for_provider(
            tmp_path, Mock(spec=GugikProvider), vertical_crs="KRON86"
        )
        assert self._segment(storage, tmp_path) == ("nmt", "pl_1992_1m_kron86")


# --- ADR-030: sciezki kampanii ---
from types import SimpleNamespace  # noqa: E402

from kartograf.download.campaigns import CampaignRef  # noqa: E402


def _rec(
    url="https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83233/83233_1744736_N-34-139-C-a-3-1.asc",
):
    return SimpleNamespace(
        url=url,
        godlo="N-34-139-C-a-3-1",
        aktualnosc="2025-04-27",
        dt_pzgik="2025-11-17",
        full_sheet=True,
        raw={"format": "ARC/INFO ASCII GRID"},
    )


REF = CampaignRef.from_record(_rec())


class TestCampaignPaths:
    def test_campaign_path_layout_adr030(self, tmp_path):
        ref = CampaignRef.from_record(_rec())
        path = FileStorage(tmp_path, resolution="1m").get_campaign_path(
            "N-34-139-C-a-3-1", ref, ".asc"
        )
        assert path == (
            tmp_path
            / "nmt/pl_1992_1m_evrf2007/kampanie/2025-04-27_83233"
            / "N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc"
        )

    def test_campaign_path_keeps_orto_variant_segment(self, tmp_path):
        st = FileStorage(tmp_path, product="orto", variant="cir")
        path = st.get_campaign_path("M-34-90-C-b-4-4", REF, ".tif")
        assert "orto/pl_1992_cir/kampanie/" in path.as_posix()

    def test_campaign_path_pl2000(self, tmp_path):
        p = FileStorage(tmp_path).get_campaign_path("6.129.30.13.4", REF, ".asc")
        assert p.relative_to(tmp_path).parts[:3] == (
            "nmt",
            "pl_2000_1m_evrf2007",
            "kampanie",
        )

    def test_list_files_excludes_campaigns_and_dangling_links(self, tmp_path):
        st = FileStorage(tmp_path)
        camp = st.get_campaign_path("N-34-139-C-a-3-1", REF, ".asc")
        camp.parent.mkdir(parents=True)
        camp.write_text("x")
        std = st.get_path("N-34-139-C-a-3-1", ".asc")
        std.parent.mkdir(parents=True)
        std.symlink_to(os.path.relpath(camp, std.parent))
        dang = st.get_path("N-34-139-C-a-3-2", ".asc")
        dang.parent.mkdir(parents=True, exist_ok=True)
        dang.symlink_to("../../../kampanie/nie-ma/x.asc")
        assert st.list_files() == [std]
        assert st.list_files(campaigns=True) == [camp]

    def test_delete_removes_dangling_link_and_sidecar_not_campaign(self, tmp_path):
        st = FileStorage(tmp_path)
        other = st.get_campaign_path("N-34-139-C-a-3-2", REF, ".asc")
        other.parent.mkdir(parents=True)
        other.write_text("x")
        link = st.get_path("N-34-139-C-a-3-1", ".asc")
        link.parent.mkdir(parents=True)
        link.symlink_to("../../../kampanie/nie-ma/x.asc")
        sidecar = link.with_name(link.name + ".meta.json")
        sidecar.write_text("{}")
        assert link.is_symlink() and not link.exists()
        assert st.delete("N-34-139-C-a-3-1", ".asc") is True
        assert not link.is_symlink()
        assert not sidecar.exists()
        assert other.exists()

    def test_delete_symlink_keeps_campaign_file(self, tmp_path):
        st = FileStorage(tmp_path)
        camp = st.get_campaign_path("N-34-139-C-a-3-1", REF, ".asc")
        camp.parent.mkdir(parents=True)
        camp.write_text("x")
        link = st.get_path("N-34-139-C-a-3-1", ".asc")
        link.parent.mkdir(parents=True)
        link.symlink_to(os.path.relpath(camp, link.parent))
        assert st.delete("N-34-139-C-a-3-1", ".asc") is True
        assert not link.is_symlink()
        assert camp.exists()
