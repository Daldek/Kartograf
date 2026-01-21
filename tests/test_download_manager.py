"""
Testy jednostkowe dla modułu download manager.

Ten moduł zawiera testy dla klasy DownloadManager z nową architekturą:
- download_sheet(godlo) → ASC
- download_bbox(bbox) → GeoTIFF
"""

import pytest
from unittest.mock import Mock

from kartograf.core.sheet_parser import BBox
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

    def test_repr(self, tmp_path):
        """Test reprezentacji tekstowej."""
        manager = DownloadManager(output_dir=tmp_path)
        repr_str = repr(manager)

        assert "DownloadManager" in repr_str
        assert "GUGiK" in repr_str

    def test_default_resolution(self):
        """Test domyślnej rozdzielczości."""
        manager = DownloadManager()
        assert manager.resolution == "1m"

    def test_resolution_1m_explicit(self):
        """Test jawnego ustawienia rozdzielczości 1m."""
        manager = DownloadManager(resolution="1m")
        assert manager.resolution == "1m"

    def test_resolution_5m(self):
        """Test ustawienia rozdzielczości 5m."""
        manager = DownloadManager(resolution="5m")
        assert manager.resolution == "5m"
        # 5m forces EVRF2007
        assert manager.vertical_crs == "EVRF2007"

    def test_resolution_5m_forces_evrf2007(self):
        """Test że 5m wymusza EVRF2007."""
        manager = DownloadManager(resolution="5m", vertical_crs="KRON86")
        # Should be changed to EVRF2007
        assert manager.vertical_crs == "EVRF2007"
        assert manager.resolution == "5m"

    def test_repr_includes_resolution(self, tmp_path):
        """Test że repr zawiera rozdzielczość."""
        manager = DownloadManager(output_dir=tmp_path, resolution="5m")
        repr_str = repr(manager)

        assert "resolution='5m'" in repr_str


class TestDownloadManagerDownloadSheet:
    """Testy metody download_sheet() - pobiera ASC przez OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture z mockowanym providerem."""
        provider = Mock(spec=GugikProvider)

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_download_sheet_success(self, tmp_path, mock_provider):
        """Test udanego pobierania arkusza jako ASC."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D")

        assert result.suffix == ".asc"
        assert result.exists()

    def test_download_sheet_skip_existing(self, tmp_path, mock_provider):
        """Test pomijania istniejącego pliku."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing ASC file
        storage = FileStorage(tmp_path)
        existing_path = storage.get_path("N-34-130-D", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing data")

        result = manager.download_sheet("N-34-130-D", skip_existing=True)

        # Should return existing path without downloading
        assert result.exists()
        assert result.read_bytes() == b"existing data"

    def test_download_sheet_overwrite_existing(self, tmp_path, mock_provider):
        """Test nadpisywania istniejącego pliku."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing ASC file
        storage = FileStorage(tmp_path)
        existing_path = storage.get_path("N-34-130-D", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing data")

        result = manager.download_sheet("N-34-130-D", skip_existing=False)

        assert result.exists()
        assert result.read_bytes() == b"ASC data"  # New data


class TestDownloadManagerDownloadHierarchy:
    """Testy metody download_hierarchy() - pobiera ASC przez OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture z mockowanym providerem."""
        provider = Mock(spec=GugikProvider)

        def mock_download(godlo, path, timeout=30):
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
        assert all(p.suffix == ".asc" for p in results)

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

        # Pre-create some ASC files
        storage = FileStorage(tmp_path)
        for godlo in ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]:
            path = storage.get_path(godlo, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"existing")

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

        # First two succeed, third fails, fourth succeeds
        call_count = [0]

        def mock_download(godlo, path, timeout=30):
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


class TestDownloadManagerDownloadBbox:
    """Testy metody download_bbox() - pobiera GeoTIFF przez WCS."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture z mockowanym providerem."""
        provider = Mock(spec=GugikProvider)

        def mock_download_bbox(bbox, path, format="GTiff", timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"TIFF data")
            return path

        provider.download_bbox = mock_download_bbox
        return provider

    @pytest.fixture
    def sample_bbox(self):
        """Przykładowy bbox."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_bbox_success(self, tmp_path, mock_provider, sample_bbox):
        """Test udanego pobierania bbox."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_bbox(sample_bbox, "test.tif")

        assert result.exists()
        assert result.name == "test.tif"

    def test_download_bbox_custom_format(self, tmp_path, sample_bbox):
        """Test pobierania bbox z własnym formatem."""
        mock_provider = Mock(spec=GugikProvider)

        def mock_download_bbox(bbox, path, format="GTiff", timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"PNG data")
            return path

        mock_provider.download_bbox = Mock(side_effect=mock_download_bbox)

        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        manager.download_bbox(sample_bbox, "test.png", format="PNG")

        # Verify format was passed
        mock_provider.download_bbox.assert_called_once()
        call_kwargs = mock_provider.download_bbox.call_args.kwargs
        assert call_kwargs["format"] == "PNG"


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

        # Pre-create some ASC files
        storage = FileStorage(tmp_path)
        for godlo in ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3"]:
            path = storage.get_path(godlo, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 2
        assert "N-34-130-D-d-2-1" not in missing
        assert "N-34-130-D-d-2-2" in missing
        assert "N-34-130-D-d-2-3" not in missing
        assert "N-34-130-D-d-2-4" in missing

    def test_get_missing_sheets_none_missing(self, tmp_path):
        """Test gdy żaden arkusz nie brakuje."""
        manager = DownloadManager(output_dir=tmp_path)

        # Pre-create all ASC files
        storage = FileStorage(tmp_path)
        for i in range(1, 5):
            godlo = f"N-34-130-D-d-2-{i}"
            path = storage.get_path(godlo, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")

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
