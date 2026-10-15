"""
Tests for parallel download functionality.

This module tests:
- Parallel hierarchy downloads with ThreadPoolExecutor
- Provider thread-safety (concurrent downloads)
- LandCover batch downloads
- CLI --workers flag
"""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from kartograf.cli.commands import create_parser, main
from kartograf.core.bbox import BBox
from kartograf.download.manager import (
    DownloadManager,
    DownloadResult,
)
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError
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
    """Tests for parallel download_hierarchy with multiple workers."""

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a mock provider that simulates downloads."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_parallel_download_hierarchy_success(self, tmp_path, mock_provider):
        """Test parallel download with max_workers=2 produces same results."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=2
        )

        # Download 1:25k -> 1:10k (4 sheets)
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(result.succeeded) == 4
        assert all(p.exists() and p.suffix == ".asc" for p in result.succeeded)

    def test_parallel_download_hierarchy_large(self, tmp_path, mock_provider):
        """Test parallel download with 16 sheets and 4 workers."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=4
        )

        # Download 1:50k -> 1:10k (16 sheets)
        result = manager.download_hierarchy("N-34-130-D-d", "1:10000")
        assert len(result.succeeded) == 16
        assert all(p.exists() for p in result.succeeded)

    def test_sequential_when_workers_1(self, tmp_path, mock_provider):
        """Test that max_workers=1 uses sequential path."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=1
        )

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )
        assert len(result.succeeded) == 4
        # Sequential mode sends downloading + completed for each = 8
        assert len(progress_calls) == 8
        # Sequential mode should maintain order
        statuses = [p.status for p in progress_calls]
        # Pattern: downloading, completed, downloading, completed, ...
        for i in range(0, len(statuses), 2):
            assert statuses[i] == "downloading"
            assert statuses[i + 1] == "completed"

    def test_parallel_uses_instance_default(self, tmp_path, mock_provider):
        """The manager's worker setting applies to a hierarchy call."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=3
        )
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(result.succeeded) == 4

    def test_parallel_download_handles_failures(self, tmp_path):
        """Test parallel download handles individual failures gracefully."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        call_count = {"n": 0}
        lock = threading.Lock()

        def mock_download(sheet, path, timeout=30):
            with lock:
                call_count["n"] += 1
                count = call_count["n"]
            if count == 2:
                raise DownloadError("Network error", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = mock_download

        manager = DownloadManager(output_dir=tmp_path, provider=provider, workers=2)

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )
        assert len(result.succeeded) == 3
        assert len(result.failed) == 1

        # Check that failed status was reported
        failed = [p for p in progress_calls if p.status == "failed"]
        assert len(failed) == 1

    def test_parallel_download_skip_existing(self, tmp_path, mock_provider):
        """Test that parallel download skips existing files correctly."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=2
        )

        # Pre-download some sheets (local versions)
        manager.download_sheets(["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"])

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )
        assert len(result.succeeded) == 2
        assert len(result.skipped) == 2

        # Check that 2 were skipped
        skipped = [p for p in progress_calls if p.status == "skipped"]
        assert len(skipped) == 2

    def test_parallel_progress_callback_receives_all_sheets(
        self, tmp_path, mock_provider
    ):
        """Test that progress callback is called for every sheet."""
        manager = DownloadManager(
            output_dir=tmp_path, provider=mock_provider, workers=2
        )

        progress_calls = []

        def on_progress(p):
            progress_calls.append(p)

        result = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )
        assert len(result.succeeded) == 4
        # Each sheet gets at least one progress call (completed or skipped)
        assert len(progress_calls) >= 4

    @pytest.mark.parametrize("count", [0, -5])
    def test_workers_init_minimum_1(self, tmp_path, mock_provider, count):
        """Invalid worker counts cannot disable downloads."""
        manager = DownloadManager(tmp_path, provider=mock_provider, workers=count)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        assert len(result.succeeded) == 1
        assert result.succeeded[0].exists()


class TestDownloadHierarchyResult:
    """Hierarchy results report each success, skip and failure directly."""

    @pytest.fixture
    def flaky_provider(self):
        """Provider: a sheet code ending in '-1' fails, the rest download correctly."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            if sheet.endswith("-1"):
                raise DownloadError("Network error", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        return provider

    def test_no_last_result_attribute(self, tmp_path, flaky_provider):
        manager = DownloadManager(output_dir=tmp_path, provider=flaky_provider)
        assert not hasattr(manager, "last_result")
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert result.failed == ["N-34-130-D-d-2-1"]
        assert not hasattr(manager, "last_result")

    @pytest.mark.parametrize("workers", [1, 4])
    def test_hierarchy_returns_result_failures_collected(
        self, tmp_path, flaky_provider, workers
    ):
        manager = DownloadManager(
            output_dir=tmp_path, provider=flaky_provider, workers=workers
        )
        existing_sheet = "N-34-130-D-d-2-2"
        manager.download_sheet(existing_sheet)
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert result.failed == ["N-34-130-D-d-2-1"]
        assert result.skipped == [existing_sheet]
        assert len(result.succeeded) == 2
        assert all(path.exists() for path in result.succeeded)
        assert result.files[existing_sheet][0].status == "local"

    @pytest.mark.parametrize("workers", [1, 4])
    def test_progress_reports_final_status_and_message_per_sheet(
        self, tmp_path, workers
    ):
        """D10: both modes report through a single ``_emit`` - the final status
        and message of every sheet are identical (the sequential one additionally
        reports ``downloading`` before the download)."""
        from kartograf.exceptions import NoCoverageError

        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            if sheet.endswith("-1"):
                raise DownloadError("Network error", sheet=sheet)
            if sheet.endswith("-3"):
                raise NoCoverageError("morze", sheet=sheet)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        manager = DownloadManager(
            output_dir=tmp_path, provider=provider, workers=workers
        )
        manager.download_sheets(["N-34-130-D-d-2-2"])  # a local version

        events = []
        manager.download_hierarchy(
            "N-34-130-D-d-2",
            "1:10000",
            on_progress=events.append,
        )

        final = {
            e.sheet: (e.status, e.message) for e in events if e.status != "downloading"
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
        downloading = [e.sheet for e in events if e.status == "downloading"]
        expected = ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3", "N-34-130-D-d-2-4"]
        assert downloading == (expected if workers == 1 else [])

    def test_unexpected_error_collected_as_failed(self, tmp_path):
        """A non-DownloadError exception in parallel mode lands in failed."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            if sheet.endswith("-1"):
                raise RuntimeError("boom")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ASC data")
            return path

        provider.download = mock_download
        manager = DownloadManager(output_dir=tmp_path, provider=provider, workers=4)
        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert result.failed == ["N-34-130-D-d-2-1"]
        assert len(result.succeeded) == 3


class TestProviderThreadSafety:
    """Tests for provider thread-safety during concurrent downloads."""

    def test_concurrent_downloads_no_corruption(self, tmp_path):
        """Test that 16 concurrent downloads don't corrupt files."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        results_lock = threading.Lock()
        thread_ids_seen = set()

        def mock_download(sheet, path, timeout=30):
            # Record that multiple threads are used
            with results_lock:
                thread_ids_seen.add(threading.current_thread().ident)

            path.parent.mkdir(parents=True, exist_ok=True)
            # Write unique data per sheet to detect corruption
            path.write_bytes(f"data-for-{sheet}".encode())
            return path

        provider.download = mock_download

        manager = DownloadManager(output_dir=tmp_path, provider=provider, workers=4)

        # Download 1:50k -> 1:10k (16 sheets) with 4 workers
        result = manager.download_hierarchy("N-34-130-D-d", "1:10000")
        assert len(result.succeeded) == 16
        for path in result.succeeded:
            content = path.read_bytes().decode()
            sheet = path.stem  # e.g. "N-34-130-D-d-1-1"
            assert content == f"data-for-{sheet}", (
                f"File corruption detected: {path} has content '{content}'"
            )

    def test_write_atomic_thread_safe_temp_names(self, tmp_path):
        """Test that write_atomic uses unique temp filenames per thread."""
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        results = []
        errors = []

        def write_from_thread(sheet, data):
            try:
                path = storage.write_atomic(sheet, data.encode(), ".asc")
                results.append((sheet, path))
            except Exception as e:
                errors.append((sheet, e))

        threads = []
        sheets = [f"N-34-130-D-d-{i}-{j}" for i in range(1, 5) for j in range(1, 5)]

        for sheet in sheets:
            t = threading.Thread(
                target=write_from_thread, args=(sheet, f"data-{sheet}")
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 16

        # Verify content integrity
        for sheet, path in results:
            assert path.read_bytes() == f"data-{sheet}".encode()

    def test_concurrent_provider_sessions_independent(self):
        """Without an injected session the provider keeps one session per thread."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

        # No caller session: SessionPerThread creates a session per thread,
        # so the thread pool does not share a single requests.Session.
        assert provider._sessions.injected is None


class TestLandCoverParallelDownload:
    """``LandCoverManager.download(workers=)``: powiats of a BDOT10k area."""

    BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
    TERYTS = ["0616", "1261", "1465"]

    def _bdot(self, tmp_path, fail=()):
        from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider

        provider = Bdot10kProvider()
        calls: list[str] = []
        lock = threading.Lock()
        state = {"active": 0, "peak": 0}

        def package(code, output_path, **kwargs):
            with lock:
                calls.append(code)
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
            if code in fail:
                raise DownloadError("Network error")
            output_path.write_bytes(f"data-{code}".encode())
            return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

        patchers = (
            patch.object(provider, "download_package", side_effect=package),
            patch.object(provider, "teryts_for_area", return_value=self.TERYTS),
        )
        return LandCoverManager(tmp_path, provider), calls, state, patchers

    @pytest.mark.parametrize("workers", [1, 2])
    def test_workers_parallel_counties(self, tmp_path, workers):
        manager, calls, state, (pkg, prg) = self._bdot(tmp_path)
        with pkg, prg:
            area = manager.download(bbox=self.BBOX, workers=workers)
        assert sorted(calls) == self.TERYTS
        assert [r.unit for r in area.files] == self.TERYTS  # TERYT order
        for r in area.files:
            assert r.file.path.read_bytes() == f"data-{r.unit}".encode()
        assert 1 <= state["peak"] <= workers
        if workers > 1:
            assert state["peak"] == workers

    def test_parallel_county_failure_others_downloaded(self, tmp_path):
        manager, _, _, (pkg, prg) = self._bdot(tmp_path, fail={"1261"})
        with pkg, prg:
            area = manager.download(bbox=self.BBOX, workers=2)
        assert [r.unit for r in area.files] == ["0616", "1465"]
        assert [f.unit for f in area.failed] == ["1261"]
        assert not area.ok


class TestCLIWorkersFlag:
    """Tests for CLI --workers / -w flag."""

    def test_download_parser_has_workers_flag(self):
        """Test that download parser accepts --workers."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D-d-2-4", "--workers", "8"]
        )
        assert args.workers == 8

    def test_download_parser_workers_short_flag(self):
        """Test that download parser accepts -w shorthand."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D-d-2-4", "-w", "2"]
        )
        assert args.workers == 2

    def test_download_parser_workers_default(self):
        """Test that --workers defaults to 4."""
        parser = create_parser()
        args = parser.parse_args(
            ["elevation", "download", "--sheet", "N-34-130-D-d-2-4"]
        )
        assert args.workers == 4

    def test_workers_passed_to_download_manager(self, tmp_path):
        """Test that --workers value is passed to DownloadManager."""
        with (
            patch(
                "kartograf.download.data._create_provider_and_storage"
            ) as mock_create,
            patch("kartograf.download.data.DownloadManager") as mock_dm_class,
        ):
            mock_provider = Mock()
            mock_provider.default_extension = ".asc"
            mock_storage = Mock()
            mock_create.return_value = (mock_provider, mock_storage)

            mock_dm = Mock()
            mock_dm.download_sheet.return_value = DownloadResult(
                succeeded=[Path("test.asc")]
            )
            mock_dm_class.return_value = mock_dm

            main(
                [
                    "elevation",
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--sheet",
                    "N-34-130-D-d-2-4",
                    "--workers",
                    "8",
                    "-q",
                    "--output",
                    str(tmp_path),
                ]
            )

            mock_dm_class.assert_called_once()
            assert mock_dm_class.call_args.kwargs["workers"] == 8


class TestDownloadManagerRepr:
    """Tests for the manager's worker representation."""

    def test_repr_includes_workers(self, tmp_path):
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=GugikProvider(vertical_crs="EVRF2007", resolution="1m"),
            workers=4,
        )
        assert "workers=4" in repr(manager)


class TestParallelDownloadRaceConditions:
    """Tests to detect race conditions in parallel downloads.

    These tests run multiple times to increase chance of catching
    intermittent race conditions.
    """

    @pytest.fixture
    def mock_provider(self):
        """Fixture with a thread-safe mock provider."""
        provider = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def mock_download(sheet, path, timeout=30):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"data-{sheet}".encode())
            return path

        provider.download = mock_download
        return provider

    @pytest.mark.parametrize("run", range(5))
    def test_parallel_download_consistency(self, tmp_path, mock_provider, run):
        """Test parallel download produces consistent results across runs."""
        work_dir = tmp_path / f"run_{run}"
        work_dir.mkdir()

        manager = DownloadManager(
            output_dir=work_dir, provider=mock_provider, workers=4
        )

        result = manager.download_hierarchy("N-34-130-D-d-2", "1:10000")
        assert len(result.succeeded) == 4
        sheets_found = set()
        for path in result.succeeded:
            assert path.exists()
            content = path.read_bytes().decode()
            sheet = path.stem
            assert content == f"data-{sheet}"
            sheets_found.add(sheet)

        # All 4 sheets should be unique
        assert len(sheets_found) == 4

    @pytest.mark.parametrize("run", range(3))
    def test_parallel_progress_counter_consistency(self, tmp_path, mock_provider, run):
        """Test that progress counter is consistent under parallelism."""
        work_dir = tmp_path / f"progress_run_{run}"
        work_dir.mkdir()

        manager = DownloadManager(
            output_dir=work_dir, provider=mock_provider, workers=4
        )

        progress_calls = []
        lock = threading.Lock()

        def on_progress(p):
            with lock:
                progress_calls.append(p)

        result = manager.download_hierarchy(
            "N-34-130-D-d-2", "1:10000", on_progress=on_progress
        )
        assert len(result.succeeded) == 4
        # Each sheet gets exactly one progress call (completed)
        assert len(progress_calls) == 4

        # All current values should be unique (1, 2, 3, 4 in some order)
        current_values = sorted([p.current for p in progress_calls])
        assert current_values == [1, 2, 3, 4]
