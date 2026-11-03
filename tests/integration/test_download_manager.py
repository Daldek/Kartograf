"""
Unit tests for the download manager module.

This module contains tests for the DownloadManager class with the new architecture:
- download_sheet -> ASC
"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, PropertyMock

import pytest

from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.marker import prepare_store
from kartograf.providers.pl.gugik import GugikProvider


class TestDownloadProgress:
    """Tests of the DownloadProgress class."""

    def test_progress_attributes(self):
        """Test of progress attributes."""
        progress = DownloadProgress(
            current=5,
            total=10,
            sheet="N-34-130-D",
            status="downloading",
            message="In progress",
        )

        assert progress.current == 5
        assert progress.total == 10
        assert progress.sheet == "N-34-130-D"
        assert progress.status == "downloading"
        assert progress.message == "In progress"

    def test_progress_percent(self):
        """Test of the progress percentage computation."""
        progress = DownloadProgress(
            current=5, total=10, sheet="N-34-130-D", status="downloading"
        )

        assert progress.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        """Test of the progress percentage when total=0."""
        progress = DownloadProgress(
            current=0, total=0, sheet="N-34-130-D", status="completed"
        )

        assert progress.progress_percent == 100.0

    def test_progress_default_message(self):
        """Test of the default message."""
        progress = DownloadProgress(
            current=1, total=1, sheet="N-34-130-D", status="completed"
        )

        assert progress.message == ""


class TestDownloadManagerBasic:
    """Tests of the basic DownloadManager functionality."""

    def test_init_custom_root(self, tmp_path):
        """Test of initialisation with a custom directory."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        assert manager.storage.root == tmp_path

    def test_init_custom_provider(self, tmp_path):
        """A custom provider selects its own explicitly declared dataset."""
        mock_provider = Mock()
        mock_provider.descriptor_key = None
        mock_provider.resolution = "1m"
        mock_provider.vertical_crs = "EVRF2007"
        manager = DownloadManager(root=tmp_path, provider=mock_provider)
        assert manager.provider is mock_provider

    def test_repr(self, tmp_path):
        """Test the string representation."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )
        repr_str = repr(manager)

        assert "DownloadManager" in repr_str
        assert "GUGiK" in repr_str

    def test_resolution_1m_explicit(self, tmp_path):
        """Test of explicitly setting the 1m resolution."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )
        assert manager.resolution == "1m"

    def test_resolution_5m(self, tmp_path):
        """Test of setting the 5m resolution."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="5m"),
        )
        assert manager.resolution == "5m"

    def test_repr_includes_resolution(self, tmp_path):
        """Test that repr contains the resolution."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="5m"),
        )
        repr_str = repr(manager)

        assert "resolution='5m'" in repr_str


class TestDownloadManagerStorageFromDescriptor:
    """Tests of deriving the storage subdirectory from the provider descriptor."""

    def test_manager_with_nmpt_provider_uses_nmpt_subdir(self, tmp_path):
        """A manager with an NMPT provider uses the 'nmpt' subdir, not 'nmt_1m'."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        manager = DownloadManager(
            root=tmp_path,
            provider=GugikNmptProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        assert manager._storage._subdir == "nmpt/pl_{system}_1m_evrf2007"

    def test_nmt_and_nmpt_managers_do_not_collide(self, tmp_path):
        """NMT and NMPT paths for the same sheet code must not be identical."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        nmt = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )
        nmpt = DownloadManager(
            root=tmp_path,
            provider=GugikNmptProvider(vertical_crs="EVRF2007", resolution="1m"),
        )
        g = "N-34-130-D-d-2-4"

        assert nmt._storage.get_path(g, ".asc") != nmpt._storage.get_path(g, ".asc")

    def test_manager_with_orto_provider_uses_orto_subdir(self, tmp_path):
        """A manager with the Orto provider uses the 'orto' subdirectory."""
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        manager = DownloadManager(
            root=tmp_path, provider=GugikOrtoProvider(color="RGB")
        )

        assert manager._storage._subdir == "orto/pl_{system}"

    def test_manager_without_descriptor_key_falls_back_to_resolution(self, tmp_path):
        """A provider without descriptor_key -> subdirectory per resolution."""
        provider = Mock()
        provider.descriptor_key = None
        provider.default_extension = ".asc"
        provider.resolution = "5m"
        provider.vertical_crs = "EVRF2007"

        manager = DownloadManager(root=tmp_path, provider=provider)

        assert manager._storage._subdir == "nmt/pl_{system}_5m_evrf2007"

    def test_manager_with_mock_spec_provider_falls_back_to_resolution(self, tmp_path):
        """Mock(spec=GugikProvider).descriptor_key is a Mock - treated as missing."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.resolution = "1m"
        provider.vertical_crs = "EVRF2007"

        manager = DownloadManager(root=tmp_path, provider=provider)

        assert manager._storage._subdir == "nmt/pl_{system}_1m_evrf2007"

    def test_explicit_storage_wins_over_descriptor(self, tmp_path):
        """An explicit storage= takes precedence over the provider descriptor."""
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", subdir="custom"
        )
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikNmptProvider(vertical_crs="EVRF2007", resolution="1m"),
            storage=storage,
        )

        assert manager._storage is storage
        assert manager._storage._subdir == "custom"

    def test_default_storage_respects_kron86(self, tmp_path):
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        provider.descriptor_key = "pl.gugik.nmt_1m"
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.resolution = "1m"
        provider.vertical_crs = "KRON86"
        manager = DownloadManager(root=tmp_path, provider=provider)
        assert manager._storage._subdir == "nmt/pl_{system}_1m_kron86"

    def test_manager_without_descriptor_key_keeps_kron86_in_segment(self, tmp_path):
        """Twin of the test above: without a descriptor FileStorage fills {vcrs}.

        The descriptor path fills {vcrs} already in `resolve_subdir`, so the
        `vertical_crs=` argument of the `FileStorage` constructor defends ONLY this
        fallback - without it an unresolved brace is left.
        """
        provider = Mock()
        provider.descriptor_key = None
        provider.default_extension = ".asc"
        provider.resolution = "1m"
        provider.vertical_crs = "KRON86"

        manager = DownloadManager(root=tmp_path, provider=provider)

        assert manager._storage._subdir == "nmt/pl_{system}_1m_kron86"

    def test_storage_follows_provider_vertical_crs(self, tmp_path):
        """The output segment and sidecar must match the provider's datum."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="KRON86", resolution="1m"),
        )

        assert manager._storage._subdir == "nmt/pl_{system}_1m_kron86"
        assert manager.vertical_crs == "KRON86"

    def test_provider_with_empty_vertical_crs_raises(self, tmp_path):
        """Finding 7 through the public API: a custom provider with vertical_crs=''."""
        from kartograf.exceptions import ValidationError

        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.vertical_crs = ""
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        with pytest.raises(ValidationError, match="Empty storage segment dimension"):
            DownloadManager(root=tmp_path, provider=provider)


class TestDownloadManagerDownloadSheet:
    """Tests of the download_sheet() method - downloads ASC via OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mocked provider."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_download_sheet_returns_result_with_versioned_files(
        self, tmp_path, mock_provider
    ):
        manager = DownloadManager(root=tmp_path, provider=mock_provider)
        sheet = "N-34-130-D-d-2-4"
        result = manager.download_sheet(sheet)
        assert len(result.succeeded) == 1
        (file,) = result.files[sheet]
        assert file.path == result.succeeded[0]
        assert file.path.exists() and file.path.suffix == ".asc"
        assert file.version_path.exists() and file.label
        assert file.status == "new"

    def test_download_sheet_skip_existing(self, tmp_path, mock_provider):
        """A local version is used without a download (skip_existing)."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)
        first = manager.download_sheet("N-34-130-D-d-2-4")

        def must_not_download(sheet, path, timeout=30):
            raise AssertionError("download")

        mock_provider.download = must_not_download
        result = manager.download_sheet("N-34-130-D-d-2-4")

        assert result.succeeded == []
        assert result.files["N-34-130-D-d-2-4"][0].path == first.succeeded[0]
        assert first.succeeded[0].read_bytes() == b"ASC data"
        assert result.skipped == ["N-34-130-D-d-2-4"]
        assert result.files["N-34-130-D-d-2-4"][0].status == "local"

    def test_download_sheet_overwrite_existing(self, tmp_path, mock_provider):
        """Test of overwriting an existing file."""
        prepare_store(tmp_path)
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        # Create existing ASC file
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        existing_path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing data")

        result = manager.download_sheet("N-34-130-D-d-2-4", update="force")

        assert len(result.succeeded) == 1
        assert result.succeeded[0].read_bytes() == b"ASC data"

    def test_download_sheet_expands_25k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:25000 sheet code expands to 4 sheets 1:10000."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D-d-2")

        assert len(result.succeeded) == 4
        assert all(p.suffix == ".asc" and p.exists() for p in result.succeeded)

    def test_download_sheet_expands_50k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:50000 sheet code expands to 16 sheets 1:10000."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D-d")

        assert len(result.succeeded) == 16
        assert all(p.suffix == ".asc" and p.exists() for p in result.succeeded)

    def test_download_sheet_expands_100k_to_10k(self, tmp_path, mock_provider):
        """download_sheet with a 1:100000 code expands to 64 sheets 1:10000."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        result = manager.download_sheet("N-34-130-D")

        assert len(result.succeeded) == 64
        assert all(p.suffix == ".asc" for p in result.succeeded)

    def test_download_sheet_expands_with_progress(self, tmp_path, mock_provider):
        """Test that download_sheet passes on_progress when expanding."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_sheet("N-34-130-D-d-2", on_progress=on_progress)

        assert len(result.succeeded) == 4
        # Each sheet gets 2 progress calls (downloading + completed)
        assert len(progress_calls) == 8


class TestDirectSheetResult:
    """A sheet call reports only that call's outcomes."""

    @staticmethod
    def _plain_manager(tmp_path, fail=False):
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def fake_download(sheet, path, timeout=30):
            if fail:
                raise DownloadError("boom", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = fake_download
        return DownloadManager(root=tmp_path, provider=provider)

    def test_single_sheet_result(self, tmp_path):
        manager = self._plain_manager(tmp_path)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        assert len(result.succeeded) == 1
        assert result.failed == []

    def test_single_sheet_skipped_is_in_skipped(self, tmp_path):
        manager = self._plain_manager(tmp_path)
        manager.download_sheet("N-34-130-D-d-2-4")
        result = manager.download_sheet("N-34-130-D-d-2-4")
        assert result.skipped == ["N-34-130-D-d-2-4"]

    def test_single_sheet_error_does_not_store_result(self, tmp_path):
        manager = self._plain_manager(tmp_path, fail=True)
        with pytest.raises(DownloadError):
            manager.download_sheet("N-34-130-D-d-2-4")
        assert not hasattr(manager, "last_result")

    def test_single_sheet_after_hierarchy_contains_only_its_sheet(self, tmp_path):
        manager = self._plain_manager(tmp_path)
        manager.download_sheet("N-34-130-D-d-2")
        result = manager.download_sheet("N-34-130-D-d-1-1")
        assert len(result.succeeded) == 1
        assert result.skipped == [] and result.failed == []
        assert set(result.files) == {"N-34-130-D-d-1-1"}


class TestDownloadManagerDownloadHierarchy:
    """Tests of the download_hierarchy() method - downloads ASC via OpenData."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mocked provider."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download
        return provider

    def test_download_hierarchy_success(self, tmp_path, mock_provider):
        """Test of a successful hierarchy download."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        # Download 1:50k → 1:10k (16 sheets)
        results = manager.download_hierarchy("N-34-130-D-d", "1:10000")

        assert len(results.succeeded) == 16
        assert all(p.exists() and p.suffix == ".asc" for p in results.succeeded)

    def test_download_hierarchy_with_progress(self, tmp_path, mock_provider):
        """Test of download with a progress callback."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        # Download 1:25k → 1:10k (4 sheets)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", on_progress=on_progress)

        # Should have progress calls for each sheet (downloading + completed)
        assert len(progress_calls) == 8  # 4 sheets × 2 calls each

    def test_download_hierarchy_skip_existing(self, tmp_path, mock_provider):
        """Test of skipping sheets with a local version in the hierarchy."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)
        manager.download_sheets(["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"])
        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )

        assert len(results.succeeded) == 2
        assert len(results.skipped) == 2

        # Check that 2 were skipped
        skipped = [p for p in progress_calls if p.status == "skipped"]
        assert len(skipped) == 2

    def test_download_hierarchy_handles_failures(self, tmp_path):
        """Test of download error handling."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        # First two succeed, third fails, fourth succeeds
        call_count = [0]

        def mock_download(sheet, path, timeout=30):
            call_count[0] += 1
            if call_count[0] == 3:
                raise DownloadError("Network error", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download

        manager = DownloadManager(root=tmp_path, provider=provider)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )

        assert len(results.succeeded) == 3
        assert len(results.failed) == 1

        # Check failed status was reported
        failed = [p for p in progress_calls if p.status == "failed"]
        assert len(failed) == 1

    def test_download_hierarchy_count(self, tmp_path, mock_provider):
        """Test of counting sheets in the hierarchy."""
        manager = DownloadManager(root=tmp_path, provider=mock_provider)

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64


class TestDownloadResultNoCoverage:
    """R5: no data at the source is told apart from a download failure."""

    @pytest.fixture
    def provider(self):
        from kartograf.exceptions import NoCoverageError

        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def download(sheet, path, timeout=30):
            if sheet.endswith("-1"):
                raise NoCoverageError(
                    f"No NMT 1m data available for {sheet}",
                    sheet=sheet,
                    hints=("uzyj --scale 1:2000",),
                )
            if sheet.endswith("-2"):
                raise DownloadError(f"timeout {sheet}", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = download
        return provider

    @pytest.mark.parametrize("workers", [1, 4])
    def test_no_coverage_is_subset_of_failed(self, tmp_path, provider, workers):
        manager = DownloadManager(root=tmp_path, provider=provider, workers=workers)
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert sorted(result.failed) == ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]
        assert len(result.succeeded) == 2
        assert result.no_coverage == ["N-34-130-D-d-2-1"]

    @pytest.mark.parametrize("workers", [1, 4])
    def test_no_coverage_hints_kept_only_for_no_coverage(
        self, tmp_path, provider, workers
    ):
        manager = DownloadManager(root=tmp_path, provider=provider, workers=workers)
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert result.no_coverage_hints == {
            "N-34-130-D-d-2-1": ("uzyj --scale 1:2000",)
        }
        assert "N-34-130-D-d-2-2" not in result.no_coverage_hints

    @pytest.mark.parametrize("workers", [1, 4])
    def test_hard_failures_excludes_no_coverage_and_progress_status(
        self, tmp_path: Path, provider, workers
    ) -> None:
        """D2/D11: ``hard_failures`` = failures worth a retry; a sheet without
        data reports the ``no_coverage`` status (not ``failed``)."""
        manager = DownloadManager(root=tmp_path, provider=provider, workers=workers)
        statuses: dict[str, str] = {}
        result = manager.download_sheets(
            ["N-34-130-D-d-2"],
            on_progress=lambda p: statuses.__setitem__(p.sheet, p.status),
        )
        assert sorted(result.failed) == ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]
        assert result.hard_failures == ["N-34-130-D-d-2-2"]
        assert statuses["N-34-130-D-d-2-1"] == "no_coverage"
        assert statuses["N-34-130-D-d-2-2"] == "failed"
        assert statuses["N-34-130-D-d-2-3"] == "completed"


class TestDownloadManagerDownloadSheets:
    """download_sheets() expands leaves and collects failures."""

    @pytest.fixture
    def provider(self):
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.calls = []
        provider.fail = set()

        def download(sheet, path, timeout=30):
            provider.calls.append(sheet)
            if sheet in provider.fail:
                raise DownloadError(f"blad {sheet}", sheet=sheet)
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

    def test_expand_sheets_to_the_sheet_level(self):
        """A code coarser than the provider's sheet level expands to it; an
        8-part code is the sheet itself for 7-part products (GUGiK publishes
        some 1 m grids per quarter) and the leaf of the 8-part level."""
        quarters = [f"N-34-50-A-c-3-2-{quarter}" for quarter in range(1, 5)]

        assert DownloadManager.expand_sheets(["N-34-50-A-c-3-2-3"]) == [
            "N-34-50-A-c-3-2-3"
        ]
        assert DownloadManager.expand_sheets(["N-34-50-A-c-3-2"], "1:5000") == (
            quarters
        )
        assert len(DownloadManager.expand_sheets(["N-34-50-A-c-3"], "1:5000")) == 16

    @pytest.mark.parametrize("workers", [1, 4])
    def test_expands_coarse_and_dedupes(self, tmp_path, provider, workers):
        manager = DownloadManager(root=tmp_path, provider=provider, workers=workers)
        result = manager.download_sheets(
            ["N-34-130-D-d-2", "N-34-130-D-d-2-4", "N-34-130-D-d-2-4"],
        )
        assert len(result.succeeded) == 4
        assert sorted(provider.calls) == [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]
        assert result.total == 4 and result.failed == []

    @pytest.mark.parametrize("workers", [1, 4])
    def test_failures_collected_not_raised(self, tmp_path, provider, workers):
        provider.fail = {"N-34-130-D-d-2-1", "N-34-130-D-d-2-3"}
        manager = DownloadManager(root=tmp_path, provider=provider, workers=workers)
        result = manager.download_sheets(["N-34-130-D-d-2"])
        assert len(result.succeeded) == 2
        assert sorted(result.failed) == [
            "N-34-130-D-d-2-1",
            "N-34-130-D-d-2-3",
        ]
        assert result.total == 4

    def test_skip_existing(self, tmp_path, provider):
        manager = DownloadManager(root=tmp_path, provider=provider)
        manager.download_sheets(["N-34-130-D-d-2-1"])
        provider.calls.clear()
        result = manager.download_sheets(["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"])
        assert provider.calls == ["N-34-130-D-d-2-2"]
        assert result.skipped == ["N-34-130-D-d-2-1"]
        assert result.files["N-34-130-D-d-2-1"][0].status == "local"
        assert result.files["N-34-130-D-d-2-2"][0].status == "new"

    def test_invalid_sheet_raises_before_any_download(self, tmp_path, provider):
        from kartograf.exceptions import ParseError

        manager = DownloadManager(root=tmp_path, provider=provider)
        with pytest.raises(ParseError):
            manager.download_sheets(["N-34-130-D-d-2-1", "XYZ"])
        assert provider.calls == []


class TestDownloadManagerGetMissingSheets:
    """Tests of get_missing_sheets()."""

    def test_get_missing_sheets_all_missing(self, tmp_path):
        """Test when all sheets are missing."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 4

    def test_get_missing_sheets_some_exist(self, tmp_path):
        """Test when some sheets exist."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        # Pre-create some ASC files
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        for sheet in ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3"]:
            path = storage.get_path(sheet, ".asc")
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
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        # Pre-create all ASC files
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        for i in range(1, 5):
            sheet = f"N-34-130-D-d-2-{i}"
            path = storage.get_path(sheet, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")

        missing = manager.get_missing_sheets("N-34-130-D-d-2", "1:10000")

        assert len(missing) == 0


class TestDownloadManagerCountSheets:
    """Tests of count_sheets()."""

    def test_count_sheets_small_hierarchy(self, tmp_path):
        """Test of counting a small hierarchy."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        # 1:25k → 1:10k = 4 sheets
        count = manager.count_sheets("N-34-130-D-d-2", "1:10000")

        assert count == 4

    def test_count_sheets_medium_hierarchy(self, tmp_path):
        """Test of counting a medium hierarchy."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        # 1:50k → 1:10k = 4 × 4 = 16 sheets
        count = manager.count_sheets("N-34-130-D-d", "1:10000")

        assert count == 16

    def test_count_sheets_large_hierarchy(self, tmp_path):
        """Test of counting a large hierarchy."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        # 1:100k → 1:10k = 4 × 4 × 4 = 64 sheets
        count = manager.count_sheets("N-34-130-D", "1:10000")

        assert count == 64

    def test_count_sheets_500k_to_200k(self, tmp_path):
        """Test of counting the hierarchy 1:500k -> 1:200k (36 sheets)."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )

        count = manager.count_sheets("N-34-A", "1:200000")

        assert count == 36


class TestDownloadManagerDefaultExtension:
    """Tests for dynamic file extension based on provider."""

    def test_default_extension_asc(self, tmp_path):
        """Test that default GugikProvider uses .asc extension."""
        manager = DownloadManager(
            root=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
        )
        assert manager._default_ext == ".asc"

    def test_custom_extension_tif(self, tmp_path):
        """Test that provider with .tif extension is used."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"
        mock_provider.resolution = "1m"
        mock_provider.vertical_crs = "EVRF2007"

        manager = DownloadManager(root=tmp_path, provider=mock_provider)
        assert manager._default_ext == ".tif"

    def test_manager_product_storage(self, tmp_path):
        """Test that manager uses product-based storage correctly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".tif"

        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs=None, product="orto"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        assert manager._default_ext == ".tif"
        assert manager.storage._product == "orto"


class TestDownloadManagerPL2000:
    """Tests of DownloadManager with PL-2000 sheet codes."""

    def test_count_sheets_pl2000_10k_to_2k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:10000 -> 1:2000 (25 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12", target_scale="1:2000")
        assert count == 25

    def test_count_sheets_pl2000_10k_to_5k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:10000 -> 1:5000 (4 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12", target_scale="1:5000")
        assert count == 4

    def test_count_sheets_pl2000_2k_to_1k(self, tmp_path):
        """Test of counting PL-2000 sheets 1:2000 -> 1:1000 (4 sheets)."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        count = manager.count_sheets("6.179.12.20", target_scale="1:1000")
        assert count == 4

    def test_download_sheet_pl2000_10k_direct(self, tmp_path):
        """download_sheet with a PL-2000 1:10000 code downloads it directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        result = manager.download_sheet("6.179.12")

        assert len(result.succeeded) == 1
        assert result.succeeded[0].suffix == ".asc" and result.succeeded[0].exists()

    def test_download_sheet_pl2000_sub10k_direct(self, tmp_path):
        """Test that PL-2000 1:2000 downloads directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        # PL-2000 1:2000 sheet code - should download directly, NOT expand to 1:10000
        result = manager.download_sheet("6.179.12.20")

        assert len(result.succeeded) == 1
        assert result.succeeded[0].suffix == ".asc"
        assert result.succeeded[0].exists()
        assert "6.179.12.20" in str(result.succeeded[0])

    def test_download_sheet_pl2000_5k_direct(self, tmp_path):
        """download_sheet with a PL-2000 1:5000 code downloads it directly."""
        mock_provider = Mock()
        mock_provider.default_extension = ".asc"

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        mock_provider.download = mock_download

        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmt_2000_1m"
        )
        manager = DownloadManager(
            root=tmp_path, provider=mock_provider, storage=storage
        )

        # PL-2000 1:5000 sheet code - should download directly
        result = manager.download_sheet("6.179.12.1")

        assert len(result.succeeded) == 1
        assert result.succeeded[0].suffix == ".asc" and result.succeeded[0].exists()


class TestCreateNmtProviderFactory:
    def test_rejects_combination_outside_registry_with_registry_text(self, caplog):
        """No silent swap of the height system and no list of its own: NMT 5m
        exists only in EVRF2007, the error names the KRON86 labels of the
        variant registry (``kartograf.sources.variants``); nothing is logged."""
        import logging

        from kartograf.providers.pl import create_nmt_provider
        from kartograf.sources.variants import variants

        grids = sorted(
            variants(product="nmt", country="PL", vertical_crs="KRON86", format="ASC"),
            key=lambda v: v.resolution_m or Decimal(0),
        )
        labels = ", ".join(v.label for v in grids if v.label is not None)
        assert labels

        with caplog.at_level(logging.WARNING), pytest.raises(ValidationError) as exc:
            create_nmt_provider(vertical_crs="KRON86", resolution="5m")
        message = str(exc.value)
        assert "5m (PL) is only available in EVRF2007" in message
        assert "got --vertical-crs KRON86" in message
        assert message.endswith(f"; available in KRON86: {labels}")
        assert caplog.text == ""


class TestSidecarWritten:
    """A .meta.json sidecar next to every successful download (spec stage 0)."""

    def _mock_provider(self):
        from unittest.mock import MagicMock

        provider = MagicMock()
        provider.default_extension = ".asc"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"

        def fake_download(sheet, target, timeout=30):
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

        manager = DownloadManager(root=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
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

        manager = DownloadManager(root=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        data = result.read_bytes()
        assert payload["sha256"] == hashlib.sha256(data).hexdigest()
        assert payload["size_bytes"] == len(data)

    @pytest.mark.parametrize("mode", ["sheet", "list_seq", "list_parallel"])
    def test_every_mode_returns_standard_link_to_provider_file(self, tmp_path, mode):
        """D10 + spec 3: whatever path the provider RETURNS becomes the version;
        every mode returns the standard path linked to it."""
        provider = self._mock_provider()
        written = self._mock_provider().download.side_effect

        def download_elsewhere(sheet, target, timeout=30):
            return written(sheet, target.with_name(f"{target.stem}_v2.asc"))

        provider.download.side_effect = download_elsewhere
        manager = DownloadManager(
            root=tmp_path,
            provider=provider,
            workers=1 if mode != "list_parallel" else 3,
        )
        sheet = "N-34-130-D-d-2-4"
        result = (
            manager.download_sheet(sheet)
            if mode == "sheet"
            else manager.download_sheets([sheet])
        )
        (path,) = result.succeeded
        assert path == manager.storage.get_path(sheet, ".asc")
        assert "1 2" in path.read_text()
        assert (path.parent / f"{path.name}.meta.json").exists()

    def test_rerun_never_rewrites_version_sidecar(self, tmp_path):
        """D12: the version sidecar is written once."""
        manager = DownloadManager(root=tmp_path, provider=self._mock_provider())
        sheet = "N-34-130-D-d-2-4"
        manager.download_sheet(sheet)
        (version,) = manager.storage.list_files("**/*.asc", versions=True)
        sidecar = version.parent / f"{version.name}.meta.json"
        before = sidecar.read_bytes()
        manager.download_sheet(sheet)
        manager.download_sheet(sheet, update="force")
        assert sidecar.read_bytes() == before

    def test_sidecar_failure_fails_sheet_without_version(self, tmp_path):
        from unittest.mock import patch

        manager = DownloadManager(root=tmp_path, provider=self._mock_provider())
        with (
            patch(
                "kartograf.sources.sidecar.write_sidecar",
                side_effect=OSError("dysk pelny"),
            ),
            pytest.raises(DownloadError, match="mandatory sidecar"),
        ):
            manager.download_sheet("N-34-130-D-d-2-4")
        assert manager.storage.list_files("**/*.asc") == []
        assert manager.storage.list_files("**/*.asc", versions=True) == []

    def test_provider_without_descriptor_gets_bare_version_sidecar(self, tmp_path):
        import json

        provider = self._mock_provider()
        del provider.descriptor_key  # Mock attribute, not str
        provider.descriptor_key = object()
        manager = DownloadManager(root=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert "dataset" not in payload
        assert payload["request"] == {"sheet": "N-34-130-D-d-2-4"}
        assert payload["extra"]["version"]["label_source"] == "downloaded"
        assert len(payload["sha256"]) == 64

    def test_sidecar_extra_merged_into_extra(self, tmp_path):
        import json

        parent = {
            "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["CZ", "PL"],
        }
        manager = DownloadManager(
            root=tmp_path,
            provider=self._mock_provider(),
            sidecar_extra={"parent_request": parent},
        )
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent

    def test_sidecar_extra_none_keeps_only_version_and_link(self, tmp_path):
        import json

        manager = DownloadManager(root=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert set(payload["extra"]) == {"version", "link", "link_target"}

    def test_sidecar_carries_provider_source(self, tmp_path):
        """D5: ``extra.source`` = sheet origin per ``provider.source_info``."""
        import json

        source = {
            "url": "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/1/1_N.asc",
            "index_url": "https://mapy.geoportal.gov.pl/.../WFS/Skorowidze",
            "layer": "SkorowidzNMT2026",
            "sheet": "N-34-130-D-d-2-4",
            "acquisition_date": "2026-03-01",
            "resolution_m": 1.0,
        }
        provider = self._mock_provider()
        provider.source_info = lambda sheet: (
            source if sheet == "N-34-130-D-d-2-4" else None
        )
        manager = DownloadManager(
            root=tmp_path,
            provider=provider,
            sidecar_extra={"parent_request": {"bbox_crs": "EPSG:2180"}},
        )
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
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
        manager = DownloadManager(root=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert "source" not in payload["extra"]

        provider.source_info = lambda sheet: None
        result = manager.download_sheet("N-34-130-D-d-2-4", update="force").succeeded[0]
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert "source" not in payload["extra"]


def test_reuse_keeps_parent_request_of_the_creating_request(tmp_path):
    """D12: ``extra.parent_requests`` is gone; a later request reusing the
    version changes no sidecar."""
    first = {"bbox": [1.0, 2.0, 3.0, 4.0], "bbox_crs": "EPSG:2180"}
    second = {"bbox": [5.0, 6.0, 7.0, 8.0], "bbox_crs": "EPSG:2180"}

    def manager(request):
        return DownloadManager(
            root=tmp_path,
            provider=TestSidecarWritten()._mock_provider(),
            sidecar_extra={"parent_request": request},
        )

    path = manager(first).download_sheet("N-34-130-D-d-2-4").succeeded[0]
    sidecar = path.parent / f"{path.name}.meta.json"
    before = sidecar.read_bytes()
    manager(second).download_sheets(["N-34-130-D-d-2-4"])
    assert sidecar.read_bytes() == before
    assert b"parent_requests" not in before
