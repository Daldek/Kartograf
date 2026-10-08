"""
Tests for parallel download functionality.

This module tests:
- Parallel hierarchy downloads with ThreadPoolExecutor
- Provider thread-safety (concurrent downloads)
- LandCover batch downloads
- CLI --workers flag
"""

import logging
import threading
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from kartograf.cli.commands import create_parser, main
from kartograf.download.manager import (
    DownloadManager,
    DownloadResult,
)
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.pl.gugik import GugikProvider


class TestDownloadResult:
    """Tests for DownloadResult dataclass."""

    def test_empty_result(self):
        """Test empty DownloadResult."""
        result = DownloadResult()
        assert result.succeeded == []
        assert result.failed == []
        assert result.skipped == []
        assert result.total == 0
        assert result.all_paths == []

    def test_result_with_data(self, tmp_path):
        """Test DownloadResult with various data."""
        p1 = tmp_path / "file1.asc"
        p2 = tmp_path / "file2.asc"
        result = DownloadResult(
            succeeded=[p1, p2],
            failed=["N-34-130-D-d-2-3"],
            skipped=["N-34-130-D-d-2-4"],
        )
        assert result.total == 4
        assert len(result.all_paths) == 2

    def test_result_total_property(self):
        """Test total property counts all categories."""
        result = DownloadResult(
            succeeded=[Path("a.asc")],
            failed=["b", "c"],
            skipped=["d"],
        )
        assert result.total == 4


class TestParallelDownloadHierarchy:
    """Tests for parallel download_hierarchy with max_workers > 1."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mock provider that simulates downloads."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_parallel_download_hierarchy_success(self, tmp_path, mock_provider):
        """Test parallel download with max_workers=2 produces same results."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=2
        )

        # Download 1:25k -> 1:10k (4 sheets)
        results = manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=2)

        assert len(results) == 4
        assert all(p.exists() for p in results)
        assert all(p.suffix == ".asc" for p in results)

    def test_parallel_download_hierarchy_large(self, tmp_path, mock_provider):
        """Test parallel download with 16 sheets and 4 workers."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=4
        )

        # Download 1:50k -> 1:10k (16 sheets)
        results = manager.download_hierarchy("N-34-130-D-d", "1:10000", max_workers=4)

        assert len(results) == 16
        assert all(p.exists() for p in results)

    def test_sequential_when_max_workers_1(self, tmp_path, mock_provider):
        """Test that max_workers=1 uses sequential path."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=1
        )

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", max_workers=1, on_progress=on_progress
        )

        assert len(results) == 4
        # Sequential mode sends downloading + completed for each = 8
        assert len(progress_calls) == 8
        # Sequential mode should maintain order
        statuses = [p.status for p in progress_calls]
        # Pattern: downloading, completed, downloading, completed, ...
        for i in range(0, len(statuses), 2):
            assert statuses[i] == "downloading"
            assert statuses[i + 1] == "completed"

    def test_parallel_uses_instance_default(self, tmp_path, mock_provider):
        """Test that max_workers=None uses instance default."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=3
        )

        results = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")

        # Should work with 3 workers (instance default)
        assert len(results) == 4

    def test_parallel_download_handles_failures(self, tmp_path):
        """Test parallel download handles individual failures gracefully."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        call_count = {"n": 0}
        lock = threading.Lock()

        def mock_download(godlo, path, timeout=30):
            with lock:
                call_count["n"] += 1
                count = call_count["n"]
            if count == 2:
                raise DownloadError("Network error", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download

        manager = DownloadManager(output_dir=tmp_path, provider=provider, max_workers=2)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", max_workers=2, on_progress=on_progress
        )

        # Should have 3 successful downloads (1 failed)
        assert len(results) == 3

        # Check that failed status was reported
        failed = [p for p in progress_calls if p.status == "failed"]
        assert len(failed) == 1

    def test_parallel_download_skip_existing(self, tmp_path, mock_provider):
        """Test that parallel download skips existing files correctly."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=2
        )

        # Pre-create some files
        storage = FileStorage(tmp_path)
        for godlo in ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]:
            path = storage.get_path(godlo, ".asc")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"existing")

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", max_workers=2, on_progress=on_progress
        )

        assert len(results) == 4

        # Check that 2 were skipped
        skipped = [p for p in progress_calls if p.status == "skipped"]
        assert len(skipped) == 2

    def test_parallel_progress_callback_receives_all_sheets(
        self, tmp_path, mock_provider
    ):
        """Test that progress callback is called for every sheet."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, max_workers=2
        )

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", max_workers=2, on_progress=on_progress
        )

        assert len(results) == 4
        # Each sheet gets at least one progress call (completed or skipped)
        assert len(progress_calls) >= 4

    def test_max_workers_init_minimum_1(self):
        """Test that max_workers is clamped to minimum 1."""
        manager = DownloadManager(max_workers=0)
        assert manager._max_workers == 1

        manager = DownloadManager(max_workers=-5)
        assert manager._max_workers == 1


class TestDownloadHierarchyLastResult:
    """Tests of the DownloadManager.last_result attribute filled by the hierarchy."""

    @pytest.fixture
    def flaky_provider(self):
        """Provider: a sheet code ending in '-1' fails, the rest download correctly."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            if godlo.endswith("-1"):
                raise DownloadError("Network error", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_last_result_is_none_before_download(self, tmp_path, flaky_provider):
        """Before the first hierarchy last_result is None."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        assert manager.last_result is None

    @pytest.mark.parametrize("workers", [1, 4])
    def test_last_result_counts_succeeded_skipped_failed(
        self, tmp_path, flaky_provider, caplog, workers
    ):
        """last_result separates downloaded, skipped and failed sheets."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        existing_godlo = "N-34-130-D-d-2-2"
        existing_path = manager.storage.get_path(existing_godlo, ".asc")
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(b"existing")

        with caplog.at_level(logging.INFO, logger="kartograf.download.manager"):
            paths = manager.download_hierarchy(
                "N-34-130-D-d-2", "1:10000", max_workers=workers
            )

        assert manager.last_result is not None
        assert manager.last_result.failed == ["N-34-130-D-d-2-1"]
        assert set(manager.last_result.skipped) == {existing_godlo}
        assert len(manager.last_result.succeeded) == 2
        assert manager.last_result.total == 4

        # Return type unchanged: a list of paths (2 downloaded + 1 skipped)
        assert len(paths) == 3
        assert all(isinstance(p, Path) for p in paths)

        assert "2 downloaded, 1 skipped, 1 failed" in caplog.text

    @pytest.mark.parametrize("workers", [1, 4])
    def test_progress_reports_final_status_and_message_per_sheet(
        self, tmp_path, workers
    ):
        """D10: both modes report through a single ``_emit`` - the final status
        and message of every sheet are identical (the sequential one additionally
        reports ``downloading`` before the download)."""
        from kartograf.exceptions import NoCoverageError

        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            if godlo.endswith("-1"):
                raise DownloadError("Network error", godlo=godlo)
            if godlo.endswith("-3"):
                raise NoCoverageError("morze", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        existing = manager.storage.get_path("N-34-130-D-d-2-2", ".asc")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"existing")

        events = []
        manager.download_hierarchy(
            "N-34-130-D-d-2",
            "1:10000",
            max_workers=workers,
            on_progress=events.append,
        )

        final = {
            e.godlo: (e.status, e.message) for e in events if e.status != "downloading"
        }
        assert final["N-34-130-D-d-2-1"][0] == "failed"
        assert "Network error" in final["N-34-130-D-d-2-1"][1]
        assert final["N-34-130-D-d-2-2"] == ("skipped", "Already exists")
        assert final["N-34-130-D-d-2-3"][0] == "no_coverage"
        assert "morze" in final["N-34-130-D-d-2-3"][1]
        assert final["N-34-130-D-d-2-4"] == ("completed", "")
        assert sorted(e.current for e in events if e.status != "downloading") == [
            1,
            2,
            3,
            4,
        ]
        downloading = [e.godlo for e in events if e.status == "downloading"]
        expected = ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3", "N-34-130-D-d-2-4"]
        assert downloading == (expected if workers == 1 else [])

    def test_last_result_counts_unexpected_error_as_failed(self, tmp_path):
        """A non-DownloadError exception in parallel mode lands in failed."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            if godlo.endswith("-1"):
                raise RuntimeError("boom")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        manager = DownloadManager(output_dir=tmp_path, provider=provider)

        paths = manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=4)

        assert len(paths) == 3
        assert manager.last_result is not None
        assert manager.last_result.failed == ["N-34-130-D-d-2-1"]
        assert len(manager.last_result.succeeded) == 3

    def test_last_result_reset_when_next_hierarchy_fails_before_loop(
        self, tmp_path, flaky_provider
    ):
        """A new hierarchy call clears the previous result before entering the loop."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=1)
        assert manager.last_result is not None
        assert manager.last_result.failed == ["N-34-130-D-d-2-1"]

        with pytest.raises(ValidationError):
            manager.download_hierarchy("N-34-130-D-d-2", "1:5000")

        # The caller must not get the result of the PREVIOUS run.
        assert manager.last_result is None

    def test_last_result_reset_when_sequential_run_aborts(
        self, tmp_path, flaky_provider
    ):
        """An exception other than DownloadError (sequential) leaves no old result."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=1)
        assert manager.last_result is not None

        def boom(godlo, path, timeout=30):
            raise RuntimeError("boom")

        flaky_provider.download = boom

        with pytest.raises(RuntimeError):
            manager.download_hierarchy("N-34-130-D-d-1", "1:10000", max_workers=1)

        assert manager.last_result is None

    def test_last_result_reset_by_download_sheet_of_single_10k(
        self, tmp_path, flaky_provider
    ):
        """download_sheet of a single 1:10000 clears the previous hierarchy result."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        manager.download_hierarchy("N-34-130-D-d-1", "1:10000", max_workers=1)
        assert manager.last_result is not None
        assert manager.last_result.failed == ["N-34-130-D-d-1-1"]

        path = manager.download_sheet("N-34-130-D-d-2-4")

        assert path.exists()
        # A single sheet does not fill last_result - nor does it leave the old one.
        assert manager.last_result is None

    def test_last_result_set_when_download_sheet_expands_hierarchy(
        self, tmp_path, flaky_provider
    ):
        """download_sheet with a code coarser than 1:10000 still fills last_result."""
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)

        paths = manager.download_sheet("N-34-130-D-d-2")

        assert isinstance(paths, list)
        assert manager.last_result is not None
        assert manager.last_result.failed == ["N-34-130-D-d-2-1"]
        assert len(manager.last_result.succeeded) == 3


class TestProviderThreadSafety:
    """Tests for provider thread-safety during concurrent downloads."""

    def test_concurrent_downloads_no_corruption(self, tmp_path):
        """Test that 16 concurrent downloads don't corrupt files."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        results_lock = threading.Lock()
        thread_ids_seen = set()

        def mock_download(godlo, path, timeout=30):
            # Record that multiple threads are used
            with results_lock:
                thread_ids_seen.add(threading.current_thread().ident)

            path.parent.mkdir(parents=True, exist_ok=True)
            # Write unique data per godlo to detect corruption
            path.write_bytes(f"data-for-{godlo}".encode())
            return path

        provider.download = mock_download

        manager = DownloadManager(output_dir=tmp_path, provider=provider, max_workers=4)

        # Download 1:50k -> 1:10k (16 sheets) with 4 workers
        results = manager.download_hierarchy("N-34-130-D-d", "1:10000", max_workers=4)

        assert len(results) == 16

        # Verify each file has correct content
        for path in results:
            content = path.read_bytes().decode()
            godlo = path.stem  # e.g. "N-34-130-D-d-1-1"
            assert content == f"data-for-{godlo}", (
                f"File corruption detected: {path} has content '{content}'"
            )

    def test_write_atomic_thread_safe_temp_names(self, tmp_path):
        """Test that write_atomic uses unique temp filenames per thread."""
        storage = FileStorage(tmp_path)
        results = []
        errors = []

        def write_from_thread(godlo, data):
            try:
                path = storage.write_atomic(godlo, data.encode(), ".asc")
                results.append((godlo, path))
            except Exception as e:
                errors.append((godlo, e))

        threads = []
        godlos = [f"N-34-130-D-d-{i}-{j}" for i in range(1, 5) for j in range(1, 5)]

        for godlo in godlos:
            t = threading.Thread(
                target=write_from_thread, args=(godlo, f"data-{godlo}")
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 16

        # Verify content integrity
        for godlo, path in results:
            assert path.read_bytes() == f"data-{godlo}".encode()

    def test_concurrent_provider_sessions_independent(self):
        """Without an injected session the provider keeps one session per thread."""
        provider = GugikProvider()

        # No caller session: SessionPerThread creates a session per thread,
        # so the thread pool does not share a single requests.Session.
        assert provider._sessions.injected is None


class TestLandCoverParallelDownload:
    """Tests for LandCoverManager.download_batch."""

    def test_download_batch_sequential(self, tmp_path):
        """Test download_batch with max_workers=1 (sequential)."""
        mock_provider = Mock()
        mock_provider.name = "bdot10k"
        mock_provider.get_available_layers.return_value = []

        call_count = {"n": 0}

        def mock_download_by_teryt(teryt, output_path, **kwargs):
            call_count["n"] += 1
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"data")
            return output_path

        mock_provider.download_by_teryt = mock_download_by_teryt

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        items = [
            {"teryt": "1465"},
            {"teryt": "1261"},
            {"teryt": "0616"},
        ]

        results = manager.download_batch(items, max_workers=1)

        assert len(results) == 3
        assert call_count["n"] == 3

    def test_download_batch_parallel(self, tmp_path):
        """Test download_batch with max_workers=2."""
        mock_provider = Mock()
        mock_provider.name = "bdot10k"
        mock_provider.get_available_layers.return_value = []

        def mock_download_by_teryt(teryt, output_path, **kwargs):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(f"data-{teryt}".encode())
            return output_path

        mock_provider.download_by_teryt = mock_download_by_teryt

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        items = [
            {"teryt": "1465"},
            {"teryt": "1261"},
            {"teryt": "0616"},
        ]

        results = manager.download_batch(items, max_workers=2)

        assert len(results) == 3

    def test_download_batch_handles_failures(self, tmp_path):
        """Test that download_batch logs failures but continues."""
        mock_provider = Mock()
        mock_provider.name = "bdot10k"
        mock_provider.get_available_layers.return_value = []

        call_count = {"n": 0}

        def mock_download_by_teryt(teryt, output_path, **kwargs):
            call_count["n"] += 1
            if teryt == "1261":
                raise DownloadError("Network error")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"data")
            return output_path

        mock_provider.download_by_teryt = mock_download_by_teryt

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        items = [
            {"teryt": "1465"},
            {"teryt": "1261"},
            {"teryt": "0616"},
        ]

        results = manager.download_batch(items, max_workers=2)

        # 2 succeeded, 1 failed
        assert len(results) == 2

    def test_download_batch_empty_list(self, tmp_path):
        """Test download_batch with empty list returns empty."""
        mock_provider = Mock()
        mock_provider.name = "bdot10k"
        mock_provider.get_available_layers.return_value = []

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        results = manager.download_batch([], max_workers=2)

        assert results == []

    def test_download_batch_with_kwargs(self, tmp_path):
        """Test download_batch passes kwargs to each download."""
        mock_provider = Mock()
        mock_provider.name = "corine"
        mock_provider.get_available_layers.return_value = []

        def mock_download_by_godlo(godlo, output_path, **kwargs):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Store kwargs in file to verify they were passed
            output_path.write_bytes(str(kwargs).encode())
            return output_path

        mock_provider.download_by_godlo = mock_download_by_godlo

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        items = [
            {"godlo": "N-34-130-D"},
            {"godlo": "N-34-130-C"},
        ]

        results = manager.download_batch(items, max_workers=1, year=2018)

        assert len(results) == 2
        # Verify kwargs were passed through
        for path in results:
            content = path.read_bytes().decode()
            assert "'year': 2018" in content


class TestCLIWorkersFlag:
    """Tests for CLI --workers / -w flag."""

    def test_download_parser_has_workers_flag(self):
        """Test that download parser accepts --workers."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4", "--workers", "8"])
        assert args.workers == 8

    def test_download_parser_workers_short_flag(self):
        """Test that download parser accepts -w shorthand."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4", "-w", "2"])
        assert args.workers == 2

    def test_download_parser_workers_default(self):
        """Test that --workers defaults to 4."""
        parser = create_parser()
        args = parser.parse_args(["download", "N-34-130-D-d-2-4"])
        assert args.workers == 4

    def test_workers_passed_to_download_manager(self, tmp_path):
        """Test that --workers value is passed to DownloadManager."""
        with (
            patch(
                "kartograf.cli.download_cmd._create_provider_and_storage"
            ) as mock_create,
            patch("kartograf.cli.download_cmd.DownloadManager") as mock_dm_class,
        ):
            mock_provider = Mock()
            mock_provider.default_extension = ".asc"
            mock_storage = Mock()
            mock_create.return_value = (mock_provider, mock_storage)

            mock_dm = Mock()
            mock_dm.last_result = None
            mock_dm.download_sheet.return_value = Path("test.asc")
            mock_dm_class.return_value = mock_dm

            main(
                [
                    "download",
                    "N-34-130-D-d-2-4",
                    "--workers",
                    "8",
                    "-q",
                    "--output",
                    str(tmp_path),
                ]
            )

            # Verify DownloadManager was created with max_workers=8
            mock_dm_class.assert_called_once()
            call_kwargs = mock_dm_class.call_args.kwargs
            assert call_kwargs["max_workers"] == 8


class TestDownloadManagerRepr:
    """Tests for updated repr with max_workers."""

    def test_repr_includes_max_workers(self, tmp_path):
        """Test that repr includes max_workers."""
        manager = DownloadManager(output_dir=tmp_path, max_workers=4)
        repr_str = repr(manager)
        assert "max_workers=4" in repr_str

    def test_repr_default_max_workers(self, tmp_path):
        """Test that repr shows max_workers=1 by default."""
        manager = DownloadManager(output_dir=tmp_path)
        repr_str = repr(manager)
        assert "max_workers=1" in repr_str


class TestParallelDownloadRaceConditions:
    """Tests to detect race conditions in parallel downloads.

    These tests run multiple times to increase chance of catching
    intermittent race conditions.
    """

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a thread-safe mock provider."""
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(godlo, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"data-{godlo}".encode())
            return path

        provider.download = mock_download
        return provider

    @pytest.mark.parametrize("run", range(5))
    def test_parallel_download_consistency(self, tmp_path, mock_provider, run):
        """Test parallel download produces consistent results across runs."""
        work_dir = tmp_path / f"run_{run}"
        work_dir.mkdir()

        manager = DownloadManager(
            output_dir=work_dir, provider=mock_provider, max_workers=4
        )

        results = manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=4)

        assert len(results) == 4
        # Verify all files exist and have correct content
        godlos_found = set()
        for path in results:
            assert path.exists()
            content = path.read_bytes().decode()
            godlo = path.stem
            assert content == f"data-{godlo}"
            godlos_found.add(godlo)

        # All 4 godlos should be unique
        assert len(godlos_found) == 4

    @pytest.mark.parametrize("run", range(3))
    def test_parallel_progress_counter_consistency(self, tmp_path, mock_provider, run):
        """Test that progress counter is consistent under parallelism."""
        work_dir = tmp_path / f"progress_run_{run}"
        work_dir.mkdir()

        manager = DownloadManager(
            output_dir=work_dir, provider=mock_provider, max_workers=4
        )

        progress_calls = []
        lock = threading.Lock()

        def on_progress(p):
            with lock:
                progress_calls.append(p)

        results = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", max_workers=4, on_progress=on_progress
        )

        assert len(results) == 4
        # Each sheet gets exactly one progress call (completed)
        assert len(progress_calls) == 4

        # All current values should be unique (1, 2, 3, 4 in some order)
        current_values = sorted([p.current for p in progress_calls])
        assert current_values == [1, 2, 3, 4]
