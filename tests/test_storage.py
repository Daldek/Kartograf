"""
Testy jednostkowe dla modułu storage.

Ten moduł zawiera testy dla klasy FileStorage, weryfikujące poprawność
generowania ścieżek i operacji na plikach.
"""

import io

import pytest  # noqa: F401 - required for fixtures

from kartograf.download.storage import FileStorage


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
        expected_parts = ["1m", "N-34", "130", "D", "d", "2", "4"]
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
        # Check the common parent directory (1:25k level = 1m/N-34/130/D/d/2)
        common_parent = tmp_path / "1m" / "N-34" / "130" / "D" / "d" / "2"
        assert common_parent.exists()

        # Should have 4 subdirectories (1, 2, 3, 4)
        subdirs = list(common_parent.iterdir())
        assert len(subdirs) == 4

        # Each subdirectory should contain one file (default extension is .asc)
        for subdir in subdirs:
            files = list(subdir.glob("*.asc"))
            assert len(files) == 1
