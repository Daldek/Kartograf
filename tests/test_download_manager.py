"""
Unit tests for the download manager module.

This module contains tests for the DownloadManager class with the new architecture:
- download_sheet(godlo) -> ASC
- download_bbox(bbox) -> GeoTIFF
"""

from pathlib import Path
from unittest.mock import Mock, PropertyMock

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider


class TestDownloadProgress:
    """Tests of the DownloadProgress class."""

    def test_progress_attributes(self):
        """Test of progress attributes."""
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
        """Test of the progress percentage computation."""
        progress = DownloadProgress(
            current=5, total=10, godlo="N-34-130-D", status="downloading"
        )

        assert progress.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        """Test of the progress percentage when total=0."""
        progress = DownloadProgress(
            current=0, total=0, godlo="N-34-130-D", status="completed"
        )

        assert progress.progress_percent == 100.0

    def test_progress_default_message(self):
        """Test of the default message."""
        progress = DownloadProgress(
            current=1, total=1, godlo="N-34-130-D", status="completed"
        )

        assert progress.message == ""


class TestDownloadManagerBasic:
    """Tests of the basic DownloadManager functionality."""

    def test_init_defaults(self):
        """Test of initialisation with default values."""
        manager = DownloadManager()

        assert isinstance(manager.provider, GugikProvider)
        assert isinstance(manager.storage, FileStorage)

    def test_init_custom_output_dir(self, tmp_path):
        """Test of initialisation with a custom directory."""
        manager = DownloadManager(output_dir=tmp_path)

        assert manager.storage.output_dir == tmp_path

    def test_init_custom_provider(self):
        """Test of initialisation with a custom provider."""
        mock_provider = Mock()
        manager = DownloadManager(provider=mock_provider)

        assert manager.provider == mock_provider

    def test_repr(self, tmp_path):
        """Test the string representation."""
        manager = DownloadManager(output_dir=tmp_path)
        repr_str = repr(manager)

        assert "DownloadManager" in repr_str
        assert "GUGiK" in repr_str

    def test_default_resolution(self):
        """Test of the default resolution."""
        manager = DownloadManager()
        assert manager.resolution == "1m"

    def test_resolution_1m_explicit(self):
        """Test of explicitly setting the 1m resolution."""
        manager = DownloadManager(resolution="1m")
        assert manager.resolution == "1m"

    def test_resolution_5m(self):
        """Test of setting the 5m resolution."""
        manager = DownloadManager(resolution="5m")
        assert manager.resolution == "5m"
        # 5m forces EVRF2007
        assert manager.vertical_crs == "EVRF2007"

    def test_resolution_5m_with_kron86_raises(self):
        """0.7.1: 5m exists only in EVRF2007 - ValidationError, no silent swap."""
        with pytest.raises(ValidationError, match="uzyj vertical_crs='EVRF2007'"):
            DownloadManager(resolution="5m", vertical_crs="KRON86")

    def test_repr_includes_resolution(self, tmp_path):
        """Test that repr contains the resolution."""
        manager = DownloadManager(output_dir=tmp_path, resolution="5m")
        repr_str = repr(manager)

        assert "resolution='5m'" in repr_str


class TestDownloadManagerStorageFromDescriptor:
    """Tests of deriving the storage subdirectory from the provider descriptor."""

    def test_manager_with_nmpt_provider_uses_nmpt_subdir(self, tmp_path):
        """A manager with an NMPT provider uses the 'nmpt' subdir, not 'nmt_1m'."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        manager = DownloadManager(output_dir=tmp_path, provider=GugikNmptProvider())

        assert manager._storage._subdir == "nmpt/pl_{uklad}_1m_evrf2007"

    def test_nmt_and_nmpt_managers_do_not_collide(self, tmp_path):
        """NMT and NMPT paths for the same sheet code must not be identical."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        nmt = DownloadManager(output_dir=tmp_path, provider=GugikProvider())
        nmpt = DownloadManager(output_dir=tmp_path, provider=GugikNmptProvider())
        g = "N-34-130-D-d-2-4"

        assert nmt._storage.get_path(g, ".asc") != nmpt._storage.get_path(g, ".asc")

    def test_manager_with_orto_provider_uses_orto_subdir(self, tmp_path):
        """A manager with the Orto provider uses the 'orto' subdirectory."""
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        manager = DownloadManager(output_dir=tmp_path, provider=GugikOrtoProvider())

        assert manager._storage._subdir == "orto/pl_{uklad}"

    def test_manager_without_descriptor_key_falls_back_to_resolution(self, tmp_path):
        """A provider without descriptor_key -> subdirectory per resolution."""
        provider = Mock()
        provider.descriptor_key = None
        provider.default_extension = ".asc"

        manager = DownloadManager(
            output_dir=tmp_path, provider=provider, resolution="5m"
        )

        assert manager._storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"

    def test_manager_with_mock_spec_provider_falls_back_to_resolution(self, tmp_path):
        """Mock(spec=GugikProvider).descriptor_key is a Mock - treated as missing."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        manager = DownloadManager(output_dir=tmp_path, provider=provider)

        assert manager._storage._subdir == "nmt/pl_{uklad}_1m_evrf2007"

    def test_explicit_storage_wins_over_descriptor(self, tmp_path):
        """An explicit storage= takes precedence over the provider descriptor."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        storage = FileStorage(tmp_path, subdir="custom")
        manager = DownloadManager(
            output_dir=tmp_path, provider=GugikNmptProvider(), storage=storage
        )

        assert manager._storage is storage
        assert manager._storage._subdir == "custom"

    def test_default_storage_respects_kron86(self, tmp_path):
        provider = Mock(spec=GugikProvider)
        provider.descriptor_key = "pl.gugik.nmt_1m"
        type(provider).default_extension = PropertyMock(return_value=".asc")
        manager = DownloadManager(
            output_dir=tmp_path, provider=provider, vertical_crs="KRON86"
        )
        assert manager._storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_manager_without_descriptor_key_keeps_kron86_in_segment(self, tmp_path):
        """Twin of the test above: without a descriptor FileStorage fills {vcrs}.

        The descriptor path fills {vcrs} already in `resolve_subdir`, so the
        `vertical_crs=` argument of the `FileStorage` constructor defends ONLY this
        fallback - without it an unresolved brace is left.
        """
        provider = Mock()
        provider.descriptor_key = None
        provider.default_extension = ".asc"

        manager = DownloadManager(
            output_dir=tmp_path, provider=provider, vertical_crs="KRON86"
        )

        assert manager._storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_default_storage_follows_provider_vertical_crs(self, tmp_path):
        """The segment takes the vertical CRS from the PROVIDER, not from the manager
        default (ADR-026).

        A library call (used by Hydrograf) passes a provider, not a flag: without
        this, KRON86 data landed in the ...evrf2007 segment, next to a sidecar
        declaring EPSG:9650 - exactly the CRS clash ADR-026 was meant to remove.
        """
        manager = DownloadManager(
            output_dir=tmp_path, provider=GugikProvider(vertical_crs="KRON86")
        )

        assert manager._storage._subdir == "nmt/pl_{uklad}_1m_kron86"
        assert manager.vertical_crs == "KRON86"

    def test_default_storage_5m_kron86_rejected(self, tmp_path):
        """0.7.1: a provider without its own datum - the manager rejects
        5m + KRON86 BEFORE the segment is built (no ``..._5m_evrf2007`` swap)."""
        provider = Mock(spec=GugikProvider)
        provider.descriptor_key = "pl.gugik.nmt_5m"
        type(provider).default_extension = PropertyMock(return_value=".asc")
        with pytest.raises(ValidationError, match="tylko w EVRF2007"):
            DownloadManager(
                output_dir=tmp_path,
                provider=provider,
                vertical_crs="KRON86",
                resolution="5m",
            )
        assert not (tmp_path / "nmt").exists()

    def test_provider_with_empty_vertical_crs_raises(self, tmp_path):
        """Finding 7 through the public API: a custom provider with vertical_crs=''."""
        from kartograf.exceptions import ValidationError

        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.vertical_crs = ""
        provider.descriptor_key = "pl.gugik.nmt_1m"
        with pytest.raises(ValidationError, match="Pusty wymiar"):
            DownloadManager(output_dir=tmp_path, provider=provider)


class TestDownloadManagerDownloadSheet:
    """Tests of the download_sheet() method - downloads ASC via OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mocked provider."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_download_sheet_success(self, tmp_path, mock_provider):
        """Test of a successful download of a 1:10000 sheet as ASC."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D-d-2-4")

        assert isinstance(result, Path)
        assert result.suffix == ".asc"
        assert result.exists()

    def test_download_sheet_skip_existing(self, tmp_path, mock_provider):
        """Test of skipping an existing file."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing ASC file
        storage = FileStorage(tmp_path)
        existing_path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing data")

        result = manager.download_sheet("N-34-130-D-d-2-4", skip_existing=True)

        # Should return existing path without downloading
        assert isinstance(result, Path)
        assert result.exists()
        assert result.read_bytes() == b"existing data"

    def test_download_sheet_overwrite_existing(self, tmp_path, mock_provider):
        """Test of overwriting an existing file."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Create existing ASC file
        storage = FileStorage(tmp_path)
        existing_path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing data")

        result = manager.download_sheet("N-34-130-D-d-2-4", skip_existing=False)

        assert isinstance(result, Path)
        assert result.exists()
        assert result.read_bytes() == b"ASC data"  # New data

    def test_download_sheet_expands_25k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:25000 sheet code expands to 4 sheets 1:10000."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D-d-2")

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(p.suffix == ".asc" for p in result)
        assert all(p.exists() for p in result)

    def test_download_sheet_expands_50k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:50000 sheet code expands to 16 sheets 1:10000."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D-d")

        assert isinstance(result, list)
        assert len(result) == 16
        assert all(p.suffix == ".asc" for p in result)
        assert all(p.exists() for p in result)

    def test_download_sheet_expands_100k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:100000 code expands to 64 sheets 1:10000."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D")

        assert isinstance(result, list)
        assert len(result) == 64
        assert all(p.suffix == ".asc" for p in result)

    def test_download_sheet_expands_with_progress(self, tmp_path, mock_provider):
        """Test that download_sheet passes on_progress when expanding."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_sheet("N-34-130-D-d-2", on_progress=on_progress)

        assert isinstance(result, list)
        assert len(result) == 4
        # Each sheet gets 2 progress calls (downloading + completed)
        assert len(progress_calls) == 8


class TestLastResultSingleSheet:
    """A9: download_sheet() of one sheet sets last_result too."""

    @staticmethod
    def _plain_manager(tmp_path, fail=False):
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def fake_download(godlo, path, timeout=30):
            if fail:
                raise DownloadError("boom", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = fake_download
        return DownloadManager(output_dir=tmp_path, provider=provider)

    def test_single_sheet_sets_last_result(self, tmp_path):
        manager = self._plain_manager(tmp_path)
        path = manager.download_sheet("N-34-130-D-d-2-4")
        assert manager.last_sheet is not None
        assert manager.last_result is not None
        assert manager.last_result.succeeded == [path]
        assert manager.last_result.failed == []

    def test_single_sheet_skipped_is_in_skipped(self, tmp_path):
        manager = self._plain_manager(tmp_path)
        manager.download_sheet("N-34-130-D-d-2-4")
        manager.download_sheet("N-34-130-D-d-2-4")
        assert manager.last_result.skipped == ["N-34-130-D-d-2-4"]

    def test_single_sheet_error_leaves_none(self, tmp_path):
        manager = self._plain_manager(tmp_path, fail=True)
        with pytest.raises(DownloadError):
            manager.download_sheet("N-34-130-D-d-2-4")
        assert manager.last_result is None

    def test_single_sheet_after_list_run_has_only_its_sheet(self, tmp_path):
        """P9e: a single sheet after a hierarchy run on the same manager -
        the one-element result carries no list state (no campaign files, no
        copies, no other sheets)."""
        manager = self._plain_manager(tmp_path)
        manager.download_sheet("N-34-130-D-d-2")  # 1:25000 -> 4 sheets
        assert len(manager.last_result.succeeded) == 4
        path = manager.download_sheet("N-34-130-D-d-1-1")
        result = manager.last_result
        assert result.succeeded == [path]
        assert result.skipped == [] and result.failed == []
        assert result.campaign_files == {} and result.copied == []


class TestDownloadManagerDownloadHierarchy:
    """Tests of the download_hierarchy() method - downloads ASC via OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mocked provider."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download
        return provider

    def test_download_hierarchy_success(self, tmp_path, mock_provider):
        """Test of a successful hierarchy download."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # Download 1:50k → 1:10k (16 sheets)
        results = manager.download_hierarchy("N-34-130-D-d", "1:10000")

        assert len(results) == 16
        assert all(p.exists() for p in results)
        assert all(p.suffix == ".asc" for p in results)

    def test_download_hierarchy_with_progress(self, tmp_path, mock_provider):
        """Test of download with a progress callback."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        # Download 1:25k → 1:10k (4 sheets)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", on_progress=on_progress)

        # Should have progress calls for each sheet (downloading + completed)
        assert len(progress_calls) == 8  # 4 sheets × 2 calls each

    def test_download_hierarchy_skip_existing(self, tmp_path, mock_provider):
        """Test of skipping existing files in the hierarchy."""
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
        """Test of download error handling."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

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
        """Test of counting sheets in the hierarchy."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64


class TestDownloadResultNoCoverage:
    """R5: no data at the source is told apart from a download failure."""

    @pytest.fixture
    def provider(self):
        from kartograf.exceptions import NoCoverageError

        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def download(godlo, path, timeout=30):
            if godlo.endswith("-1"):
                raise NoCoverageError(
                    f"No NMT 1m data available for {godlo}",
                    godlo=godlo,
                    hints=("uzyj --scale 1:2000",),
                )
            if godlo.endswith("-2"):
                raise DownloadError(f"timeout {godlo}", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = download
        return provider

    @pytest.mark.parametrize("workers", [1, 4])
    def test_no_coverage_is_subset_of_failed(self, tmp_path, provider, workers):
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=workers)
        result = manager.last_result
        assert sorted(result.failed) == ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]
        assert result.no_coverage == ["N-34-130-D-d-2-1"]
        assert len(result.succeeded) == 2

    @pytest.mark.parametrize("workers", [1, 4])
    def test_no_coverage_hints_kept_only_for_no_coverage(
        self, tmp_path, provider, workers
    ):
        """O-6: NoCoverageError hints in the list result; a hard failure has none."""
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=workers)
        result = manager.last_result
        assert result.no_coverage_hints == {
            "N-34-130-D-d-2-1": ("uzyj --scale 1:2000",)
        }
        assert "N-34-130-D-d-2-2" in result.failed
        assert "N-34-130-D-d-2-2" not in result.no_coverage_hints

    @pytest.mark.parametrize("workers", [1, 4])
    def test_hard_failures_excludes_no_coverage_and_progress_status(
        self, tmp_path: Path, provider, workers
    ) -> None:
        """D2/D11: ``hard_failures`` = failures worth a retry; a sheet without
        data reports the ``no_coverage`` status (not ``failed``)."""
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        statuses: dict[str, str] = {}
        manager.download_sheets(
            ["N-34-130-D-d-2"],
            max_workers=workers,
            on_progress=lambda p: statuses.__setitem__(p.godlo, p.status),
        )
        result = manager.last_result
        assert result is not None
        assert result.hard_failures == ["N-34-130-D-d-2-2"]
        assert statuses["N-34-130-D-d-2-1"] == "no_coverage"
        assert statuses["N-34-130-D-d-2-2"] == "failed"
        assert statuses["N-34-130-D-d-2-3"] == "completed"


class TestDownloadManagerDownloadSheets:
    """download_sheets(): sheet list -> 1:10000 leaves, failures in last_result."""

    @pytest.fixture
    def provider(self):
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.calls = []
        provider.fail = set()

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            if godlo in provider.fail:
                raise DownloadError(f"blad {godlo}", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = download
        return provider

    def test_expand_sheets_leaves_dedup_order(self):
        assert DownloadManager.expand_sheets(
            ["N-34-130-D-d-2-4", "N-34-130-D-d-2", "6.179.12.20"]
        ) == [
            "N-34-130-D-d-2-4",
            "N-34-130-D-d-2-1",
            "N-34-130-D-d-2-2",
            "N-34-130-D-d-2-3",
            "6.179.12.20",
        ]

    @pytest.mark.parametrize("workers", [1, 4])
    def test_expands_coarse_and_dedupes(self, tmp_path, provider, workers):
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        paths = manager.download_sheets(
            ["N-34-130-D-d-2", "N-34-130-D-d-2-4", "N-34-130-D-d-2-4"],
            max_workers=workers,
        )
        assert len(paths) == 4
        assert sorted(provider.calls) == [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]
        assert manager.last_result.total == 4 and manager.last_result.failed == []

    @pytest.mark.parametrize("workers", [1, 4])
    def test_failures_collected_not_raised(self, tmp_path, provider, workers):
        provider.fail = {"N-34-130-D-d-2-1", "N-34-130-D-d-2-3"}
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        paths = manager.download_sheets(["N-34-130-D-d-2"], max_workers=workers)
        assert len(paths) == 2
        assert sorted(manager.last_result.failed) == [
            "N-34-130-D-d-2-1",
            "N-34-130-D-d-2-3",
        ]
        assert manager.last_result.total == 4

    def test_skip_existing(self, tmp_path, provider):
        existing = FileStorage(tmp_path).get_path("N-34-130-D-d-2-1", ".asc")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"old")
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        manager.download_sheets(["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"])
        assert provider.calls == ["N-34-130-D-d-2-2"]
        assert manager.last_result.skipped == ["N-34-130-D-d-2-1"]

    def test_invalid_godlo_raises_before_any_download(self, tmp_path, provider):
        from kartograf.exceptions import ParseError

        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        with pytest.raises(ParseError):
            manager.download_sheets(["N-34-130-D-d-2-1", "XYZ"])
        assert provider.calls == []


class TestDownloadManagerDownloadBbox:
    """Tests of the download_bbox() method - downloads GeoTIFF via WCS."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mocked provider."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download_bbox(bbox, path, format="GTiff", timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"TIFF data")
            return path

        provider.download_bbox = mock_download_bbox
        return provider

    @pytest.fixture
    def sample_bbox(self):
        """Sample bbox."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_bbox_success(self, tmp_path, mock_provider, sample_bbox):
        """Test of a successful bbox download."""
        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)

        result = manager.download_bbox(sample_bbox, "test.tif")

        assert result.exists()
        assert result.name == "test.tif"

    def test_download_bbox_custom_format(self, tmp_path, sample_bbox):
        """Test of bbox download with a custom format."""
        mock_provider = Mock(spec=GugikProvider)
        type(mock_provider).default_extension = PropertyMock(return_value=".asc")

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
    """Tests of get_missing_sheets()."""

    def test_get_missing_sheets_all_missing(self, tmp_path):
        """Test when all sheets are missing."""
        manager = DownloadManager(output_dir=tmp_path)

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 4

    def test_get_missing_sheets_some_exist(self, tmp_path):
        """Test when some sheets exist."""
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
        """Test when no sheet is missing."""
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
    """Tests of count_sheets()."""

    def test_count_sheets_small_hierarchy(self, tmp_path):
        """Test of counting a small hierarchy."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:25k → 1:10k = 4 sheets
        count = manager.count_sheets("N-34-130-D-d-2", "1:10000")

        assert count == 4

    def test_count_sheets_medium_hierarchy(self, tmp_path):
        """Test of counting a medium hierarchy."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:50k → 1:10k = 4 × 4 = 16 sheets
        count = manager.count_sheets("N-34-130-D-d", "1:10000")

        assert count == 16

    def test_count_sheets_large_hierarchy(self, tmp_path):
        """Test of counting a large hierarchy."""
        manager = DownloadManager(output_dir=tmp_path)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64

    def test_count_sheets_500k_to_200k(self, tmp_path):
        """Test of counting the hierarchy 1:500k -> 1:200k (36 sheets)."""
        manager = DownloadManager(output_dir=tmp_path)

        count = manager.count_sheets("N-34-A", "1:200000")

        assert count == 36


class TestDownloadManagerDefaultExtension:
    """Tests for dynamic file extension based on provider."""

    def test_default_extension_asc(self, tmp_path):
        """Test that default GugikProvider uses .asc extension."""
        manager = DownloadManager(output_dir=tmp_path)
        assert manager._default_ext == ".asc"

    def test_custom_extension_tif(self, tmp_path):
        """Test that provider with .tif extension is used."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"

        manager = DownloadManager(output_dir=tmp_path, provider=mock_provider)
        assert manager._default_ext == ".tif"

    def test_manager_product_storage(self, tmp_path):
        """Test that manager uses product-based storage correctly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"

        storage = FileStorage(tmp_path, product="orto")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        assert manager._default_ext == ".tif"
        assert manager.storage._product == "orto"


class TestDownloadManagerPL2000:
    """Tests of DownloadManager with PL-2000 sheet codes."""

    def test_count_sheets_pl2000_10k_to_2k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:10000 -> 1:2000 (25 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12", target_scale="1:2000")
        assert count == 25

    def test_count_sheets_pl2000_10k_to_5k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:10000 -> 1:5000 (4 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12", target_scale="1:5000")
        assert count == 4

    def test_count_sheets_pl2000_2k_to_1k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:2000 -> 1:1000 (4 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12.20", target_scale="1:1000")
        assert count == 4

    def test_download_sheet_pl2000_10k_direct(self, tmp_path):
        """download_sheet with a PL-2000 1:10000 code downloads it directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        result = manager.download_sheet("6.179.12")

        assert isinstance(result, Path)
        assert result.suffix == ".asc"
        assert result.exists()

    def test_download_sheet_pl2000_sub10k_direct(self, tmp_path):
        """Test that PL-2000 1:2000 downloads directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        # PL-2000 1:2000 sheet code - should download directly, NOT expand to 1:10000
        result = manager.download_sheet("6.179.12.20")

        assert isinstance(result, Path)
        assert result.suffix == ".asc"
        assert result.exists()
        assert "6.179.12.20" in str(result)

    def test_download_sheet_pl2000_5k_direct(self, tmp_path):
        """download_sheet with a PL-2000 1:5000 code downloads it directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, storage=storage
        )

        # PL-2000 1:5000 sheet code - should download directly
        result = manager.download_sheet("6.179.12.1")

        assert isinstance(result, Path)
        assert result.suffix == ".asc"
        assert result.exists()


class TestCreateNmtProviderFactory:
    def test_defaults(self):
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider()
        assert provider.resolution == "1m"
        assert provider.vertical_crs == "EVRF2007"

    def test_5m_kron86_raises_with_remedy(self, caplog):
        """0.7.1: no silent swap to EVRF2007 - an error naming the remedy."""
        import logging

        from kartograf.providers.pl import create_nmt_provider

        with caplog.at_level(logging.WARNING), pytest.raises(ValidationError) as exc:
            create_nmt_provider(vertical_crs="KRON86", resolution="5m")
        message = str(exc.value)
        assert "NMT 5m (PL) jest dostepny tylko w EVRF2007" in message
        assert "uzyj vertical_crs='EVRF2007' albo resolution='1m'" in message
        assert caplog.text == ""

    def test_require_rule_silent_and_public_rule_unchanged(self, caplog):
        """``require_nmt_vertical_crs`` never logs; ``nmt_vertical_crs`` keeps
        its 0.7.0 contract (public API: ``log=True`` warns, still corrects)."""
        import logging

        from kartograf.providers.pl import nmt_vertical_crs, require_nmt_vertical_crs

        with caplog.at_level(logging.DEBUG):
            assert require_nmt_vertical_crs("5m", "EVRF2007") == "EVRF2007"
            assert require_nmt_vertical_crs("1m", "KRON86") == "KRON86"
            with pytest.raises(ValidationError):
                require_nmt_vertical_crs("5m", "KRON86")
        assert caplog.text == ""
        with caplog.at_level(logging.WARNING):
            assert nmt_vertical_crs("5m", "KRON86") == "EVRF2007"
        assert "5m only supports EVRF2007" in caplog.text

    def test_rule_without_log_is_silent(self, caplog):
        """D11: ``log=False`` (CLI, ``prepare_pl_cutout``) - corrected, not logged."""
        import logging

        from kartograf.providers.pl import nmt_vertical_crs

        with caplog.at_level(logging.WARNING):
            assert nmt_vertical_crs("5m", "KRON86", log=False) == "EVRF2007"
            assert nmt_vertical_crs("1m", "KRON86") == "KRON86"
        assert caplog.text == ""

    def test_passes_session_and_cache(self):
        from unittest.mock import MagicMock

        from kartograf.providers.pl import create_nmt_provider

        session, cache = MagicMock(), MagicMock()
        provider = create_nmt_provider(session=session, cache=cache)
        assert provider._sessions.injected is session and provider._cache is cache


class TestSidecarWritten:
    """A .meta.json sidecar next to every successful download (spec stage 0)."""

    def _mock_provider(self):
        from unittest.mock import MagicMock

        provider = MagicMock()
        provider.default_extension = ".asc"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.vertical_crs = "EVRF2007"

        def fake_download(godlo, target, timeout=30):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\n"
                "cellsize 1\nNODATA_value -9999\n1 2\n3 4\n"
            )
            return target

        provider.download.side_effect = fake_download
        return provider

    def test_download_sheet_writes_sidecar(self, tmp_path):
        import json

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4")
        sidecar = result.parent / f"{result.name}.meta.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.nmt_1m"
        assert payload["vertical_crs"] == "EPSG:9651"
        assert payload["nodata"] == -9999.0
        assert payload["request"] == {"sheet": "N-34-130-D-d-2-4"}

    def test_download_sheet_sidecar_describes_file_bytes(self, tmp_path):
        """P9a: ``sha256``/``size_bytes`` of the file the manager returns (the
        consumer verifies the data against the sidecar)."""
        import hashlib
        import json

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        data = result.read_bytes()
        assert payload["sha256"] == hashlib.sha256(data).hexdigest()
        assert payload["size_bytes"] == len(data)

    @pytest.mark.parametrize("mode", ["sheet", "list_seq", "list_parallel"])
    def test_every_mode_returns_provider_path(self, tmp_path, mode):
        """D10: one "download sheet" content - the path and sidecar are the file the
        provider RETURNED. Previously ``download_sheet`` returned (and described
        with a sidecar) the manager's target path, while the list mode used the
        provider result."""
        provider = self._mock_provider()
        written = self._mock_provider().download.side_effect

        def download_elsewhere(godlo, target, timeout=30):
            return written(godlo, target.with_name(f"{target.stem}_v2.asc"))

        provider.download.side_effect = download_elsewhere
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        godlo = "N-34-130-D-d-2-4"
        if mode == "sheet":
            path = manager.download_sheet(godlo)
        else:
            workers = 1 if mode == "list_seq" else 3
            (path,) = manager.download_sheets([godlo], max_workers=workers)
        assert path.name == f"{godlo}_v2.asc"
        assert (path.parent / f"{path.name}.meta.json").exists()

    def test_skip_existing_writes_no_sidecar(self, tmp_path):
        provider = self._mock_provider()
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        sidecar = result.parent / f"{result.name}.meta.json"
        sidecar.unlink()
        manager.download_sheet("N-34-130-D-d-2-4")  # skip_existing=True
        assert not sidecar.exists()

    def test_sidecar_failure_does_not_break_download(self, tmp_path):
        from unittest.mock import patch

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        with patch(
            "kartograf.sources.sidecar.write_sidecar",
            side_effect=OSError("dysk pelny"),
        ):
            result = manager.download_sheet("N-34-130-D-d-2-4")
        assert result.exists()

    def test_mock_provider_without_key_is_skipped(self, tmp_path):
        provider = self._mock_provider()
        del provider.descriptor_key  # Mock attribute, not str -> the guard skips
        provider.descriptor_key = object()
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        assert not (result.parent / f"{result.name}.meta.json").exists()

    def test_sidecar_extra_merged_into_extra(self, tmp_path):
        import json

        parent = {
            "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["CZ", "PL"],
        }
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=self._mock_provider(),
            sidecar_extra={"parent_request": parent},
        )
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent

    def test_sidecar_extra_none_keeps_extra_empty(self, tmp_path):
        import json

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"] == {}

    def test_sidecar_carries_provider_source(self, tmp_path):
        """D5: ``extra.source`` = sheet origin per ``provider.source_info``."""
        import json

        source = {
            "url": "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/1/1_N.asc",
            "index_url": "https://mapy.geoportal.gov.pl/.../SkorowidzeUkladEVRF2007",
            "layer": "SkorowidzeNMT2026",
            "sheet": "N-34-130-D-d-2-4",
            "acquisition_date": "2026-03-01",
            "resolution_m": 1.0,
        }
        provider = self._mock_provider()
        provider.source_info = lambda godlo: (
            source if godlo == "N-34-130-D-d-2-4" else None
        )
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=provider,
            sidecar_extra={"parent_request": {"bbox_crs": "EPSG:2180"}},
        )
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["source"] == source
        assert payload["extra"]["parent_request"] == {"bbox_crs": "EPSG:2180"}
        assert payload["schema"] == "kartograf-meta/1"

    def test_sidecar_without_provider_source_has_no_source_key(self, tmp_path):
        """``source_info`` returning None (a provider without origin) or a Mock
        (``Mock(spec=GugikProvider)``) does not reach the sidecar."""
        import json

        provider = self._mock_provider()  # MagicMock: source_info(...) -> MagicMock
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert "source" not in payload["extra"]

        provider.source_info = lambda godlo: None
        result.unlink()
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"] == {}


class TestReuseNotedInSidecar:
    """N4: a SKIPPED sheet (already in cache) gets ``extra.parent_requests``."""

    _FIRST = {
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }
    _SECOND = {
        "bbox": [5.0, 6.0, 7.0, 8.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }

    @staticmethod
    def _manager(tmp_path, request):
        return DownloadManager(
            output_dir=tmp_path,
            provider=TestSidecarWritten()._mock_provider(),
            sidecar_extra={"parent_request": request},
        )

    @staticmethod
    def _payload(path):
        import json

        return json.loads((path.parent / f"{path.name}.meta.json").read_text("utf-8"))

    @pytest.mark.parametrize("workers", [1, 3])
    def test_skipped_sheet_gets_reusing_request_appended(self, tmp_path, workers):
        """The first request downloads (``parent_request``), later ones reuse
        (``parent_requests``: a list, without duplicates, also without the
        downloading request). ``downloaded_at`` and the rest of the sidecar
        unchanged."""
        first = self._manager(tmp_path, self._FIRST)
        (path,) = first.download_sheets(["N-34-130-D-d-2-4"], max_workers=workers)
        before = self._payload(path)

        second = self._manager(tmp_path, self._SECOND)
        second.download_sheets(["N-34-130-D-d-2-4"], max_workers=workers)
        second.download_sheets(["N-34-130-D-d-2-4"], max_workers=workers)  # duplicate
        first.download_sheets(["N-34-130-D-d-2-4"], max_workers=workers)  # = parent

        after = self._payload(path)
        assert after["extra"]["parent_request"] == self._FIRST
        assert after["extra"]["parent_requests"] == [self._SECOND]
        assert after["downloaded_at"] == before["downloaded_at"]
        assert {k: v for k, v in after.items() if k != "extra"} == {
            k: v for k, v in before.items() if k != "extra"
        }

    def test_download_sheet_skip_path_also_notes_reuse(self, tmp_path):
        first = self._manager(tmp_path, self._FIRST)
        path = first.download_sheet("N-34-130-D-d-2-4")
        self._manager(tmp_path, self._SECOND).download_sheet("N-34-130-D-d-2-4")
        assert self._payload(path)["extra"]["parent_requests"] == [self._SECOND]

    def test_no_sidecar_means_nothing_is_invented(self, tmp_path):
        """Pre-0.7.0 cache (no sidecar): no sidecar is created."""
        first = self._manager(tmp_path, self._FIRST)
        path = first.download_sheet("N-34-130-D-d-2-4")
        (path.parent / f"{path.name}.meta.json").unlink()

        self._manager(tmp_path, self._SECOND).download_sheet("N-34-130-D-d-2-4")

        assert not (path.parent / f"{path.name}.meta.json").exists()

    def test_manager_without_parent_request_leaves_sidecar_untouched(self, tmp_path):
        first = self._manager(tmp_path, self._FIRST)
        path = first.download_sheet("N-34-130-D-d-2-4")
        DownloadManager(
            output_dir=tmp_path, provider=TestSidecarWritten()._mock_provider()
        ).download_sheet("N-34-130-D-d-2-4")
        assert "parent_requests" not in self._payload(path)["extra"]
