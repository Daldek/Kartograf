"""
Testy jednostkowe dla modułu download manager.

Ten moduł zawiera testy dla klasy DownloadManager, weryfikujące poprawność
pobierania pojedynczych arkuszy i całych hierarchii.
"""

from pathlib import Path

import pytest  # noqa: F401 - required for fixtures
from unittest.mock import Mock

from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError
from kartograf.providers.gugik import GugikProvider


class TestDownloadProgress:
    """Testy klasy DownloadProgress."""

    def test_progress_attributes(self):
        """Test atrybutów progress."""
        progress = DownloadProgress(
            current=5,
            total=10,
            godlo="N-34-130-D",
            status="downloading",
            message="In progress",
        )

        assert progress.current == 5
        assert progress.total == 10
        assert progress.godlo == "N-34-130-D"
        assert progress.status == "downloading"
        assert progress.message == "In progress"

    def test_progress_percent(self):
        """Test obliczania procentu postępu."""
        progress = DownloadProgress(
            current=5, total=10, godlo="N-34-130-D", status="downloading"
        )

        assert progress.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        """Test procentu postępu gdy total=0."""
        progress = DownloadProgress(
            current=0, total=0, godlo="N-34-130-D", status="completed"
        )

        assert progress.progress_percent == 100.0

    def test_progress_default_message(self):
        """Test domyślnej wiadomości."""
        progress = DownloadProgress(
            current=1, total=1, godlo="N-34-130-D", status="completed"
        )

        assert progress.message == ""


class TestDownloadManagerBasic:
    """Testy podstawowej funkcjonalności DownloadManager."""

    def test_init_defaults(self):
        """Test inicjalizacji z domyślnymi wartościami."""
        manager = DownloadManager()

        assert manager.format == "GTiff"
        assert isinstance(manager.provider, GugikProvider)
        assert isinstance(manager.storage, FileStorage)

    def test_init_custom_output_dir(self, tmp_path):
        """Test inicjalizacji z własnym katalogiem."""
        manager = DownloadManager(output_dir=tmp_path)

        assert manager.storage.output_dir == tmp_path

    def test_init_custom_provider(self):
        """Test inicjalizacji z własnym providerem."""
        mock_provider = Mock()
        manager = DownloadManager(provider=mock_provider)

        assert manager.provider == mock_provider

    def test_init_custom_format(self):
        """Test inicjalizacji z własnym formatem."""
        manager = DownloadManager(format="AAIGrid")

        assert manager.format == "AAIGrid"

    def test_repr(self, tmp_path):
        """Test reprezentacji tekstowej."""
        manager = DownloadManager(output_dir=tmp_path)
        repr_str = repr(manager)

        assert "DownloadManager" in repr_str
        assert "GUGiK" in repr_str


class TestDownloadManagerDownloadSheet:
    """Testy metody download_sheet()."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture z mockowanym providerem."""
        provider = Mock(spec=GugikProvider)
        provider.get_file_extension = Mock(return_value=".tif")
        provider.download = Mock(return_value=Path("/mock/path/file.tif"))
        return provider

    def test_download_sheet_success(self, tmp_path, mock_provider):
        """Test udanego pobierania arkusza."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D")

        assert result.suffix == ".tif"
        mock_provider.download.assert_called_once()

    def test_download_sheet_skip_existing(self, tmp_path, mock_provider):
        """Test pomijania istniejącego pliku."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing file
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D", b"existing data")

        result = manager.download_sheet("N-34-130-D", skip_existing=True)

        # Should return existing path without downloading
        assert result.exists()
        mock_provider.download.assert_not_called()

    def test_download_sheet_overwrite_existing(self, tmp_path, mock_provider):
        """Test nadpisywania istniejącego pliku."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing file
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D", b"existing data")

        # Mock the download to actually create a file
        def mock_download(godlo, path, format):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"new data")
            return path

        mock_provider.download = mock_download

        result = manager.download_sheet("N-34-130-D", skip_existing=False)

        assert result.exists()

    def test_download_sheet_custom_format(self, tmp_path, mock_provider):
        """Test pobierania z własnym formatem."""
        mock_provider.get_file_extension = Mock(return_value=".asc")
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        manager.download_sheet("N-34-130-D", format="AAIGrid")

        call_kwargs = mock_provider.download.call_args.kwargs
        assert call_kwargs["format"] == "AAIGrid"


class TestDownloadManagerDownloadHierarchy:
    """Testy metody download_hierarchy()."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture z mockowanym providerem."""
        provider = Mock(spec=GugikProvider)
        provider.get_file_extension = Mock(return_value=".tif")

        def mock_download(godlo, path, format):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download
        return provider

    def test_download_hierarchy_success(self, tmp_path, mock_provider):
        """Test udanego pobierania hierarchii."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Download 1:50k → 1:10k (16 sheets)
        results = manager.download_hierarchy("N-34-130-D-d", "1:10000")

        assert len(results) == 16
        assert all(p.exists() for p in results)

    def test_download_hierarchy_with_progress(self, tmp_path, mock_provider):
        """Test pobierania z callback postępu."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        # Download 1:25k → 1:10k (4 sheets)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", on_progress=on_progress)

        # Should have progress calls for each sheet (downloading + completed)
        assert len(progress_calls) == 8  # 4 sheets × 2 calls each

    def test_download_hierarchy_skip_existing(self, tmp_path, mock_provider):
        """Test pomijania istniejących plików w hierarchii."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Pre-create some files
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D-d-2-1", b"existing")
        storage.write_atomic("N-34-130-D-d-2-2", b"existing")

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )

        # All 4 should be returned
        assert len(results) == 4

        # Check that 2 were skipped
        skipped = [p for p in progress_calls if p.status == "skipped"]
        assert len(skipped) == 2

    def test_download_hierarchy_handles_failures(self, tmp_path):
        """Test obsługi błędów pobierania."""
        provider = Mock(spec=GugikProvider)
        provider.get_file_extension = Mock(return_value=".tif")

        # First two succeed, third fails, fourth succeeds
        call_count = [0]

        def mock_download(godlo, path, format):
            call_count[0] += 1
            if call_count[0] == 3:
                raise DownloadError("Network error", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download

        manager = DownloadManager(output_dir=tmp_path, provider=provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )

        # Should have 3 successful downloads
        assert len(results) == 3

        # Check failed status was reported
        failed = [p for p in progress_calls if p.status == "failed"]
        assert len(failed) == 1

    def test_download_hierarchy_count(self, tmp_path, mock_provider):
        """Test liczenia arkuszy w hierarchii."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64


class TestDownloadManagerGetMissingSheets:
    """Testy metody get_missing_sheets()."""

    def test_get_missing_sheets_all_missing(self, tmp_path):
        """Test gdy wszystkie arkusze brakują."""
        manager = DownloadManager(output_dir=tmp_path)

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 4

    def test_get_missing_sheets_some_exist(self, tmp_path):
        """Test gdy niektóre arkusze istnieją."""
        manager = DownloadManager(output_dir=tmp_path)

        # Pre-create some files
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D-d-2-1", b"data")
        storage.write_atomic("N-34-130-D-d-2-3", b"data")

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 2
        assert "N-34-130-D-d-2-1" not in missing
        assert "N-34-130-D-d-2-2" in missing
        assert "N-34-130-D-d-2-3" not in missing
        assert "N-34-130-D-d-2-4" in missing

    def test_get_missing_sheets_none_missing(self, tmp_path):
        """Test gdy żaden arkusz nie brakuje."""
        manager = DownloadManager(output_dir=tmp_path)

        # Pre-create all files
        storage = FileStorage(tmp_path)
        storage.write_atomic("N-34-130-D-d-2-1", b"data")
        storage.write_atomic("N-34-130-D-d-2-2", b"data")
        storage.write_atomic("N-34-130-D-d-2-3", b"data")
        storage.write_atomic("N-34-130-D-d-2-4", b"data")

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 0


class TestDownloadManagerCountSheets:
    """Testy metody count_sheets()."""

    def test_count_sheets_small_hierarchy(self, tmp_path):
        """Test liczenia małej hierarchii."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:25k → 1:10k = 4 sheets
        count = manager.count_sheets("N-34-130-D-d-2", "1:10000")

        assert count == 4

    def test_count_sheets_medium_hierarchy(self, tmp_path):
        """Test liczenia średniej hierarchii."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:50k → 1:10k = 4 × 4 = 16 sheets
        count = manager.count_sheets("N-34-130-D-d", "1:10000")

        assert count == 16

    def test_count_sheets_large_hierarchy(self, tmp_path):
        """Test liczenia dużej hierarchii."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64

    def test_count_sheets_500k_to_200k(self, tmp_path):
        """Test liczenia hierarchii 1:500k → 1:200k (36 arkuszy)."""
        manager = DownloadManager(output_dir=tmp_path)

        count = manager.count_sheets("N-34-A", "1:200000")

        assert count == 36
