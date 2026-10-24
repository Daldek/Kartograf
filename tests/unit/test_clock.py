"""The shared UTC clock keeps offline CLI/API results byte-identical."""

import json

import pytest

from kartograf.download.plan import new_plan
from kartograf.download.versions import VersionRef
from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import build_metadata, write_sidecar
from tests.support.parity import assert_same_store, run_both


def test_frozen_clock_fixes_downloaded_at_label_and_checked_at(tmp_path, frozen_clock):
    metadata = build_metadata(
        get_source("pl.gugik.orto"), request={"sheet": "N-34-130-D-d-2-4"}
    )
    assert metadata.downloaded_at == frozen_clock.isoformat(timespec="microseconds")
    assert VersionRef.downloaded().label == frozen_clock.date().isoformat()
    assert new_plan(tmp_path, ()).checked_at == frozen_clock.isoformat(
        timespec="seconds"
    )


def test_two_runs_same_instant_byte_identical_sidecar(tmp_path, frozen_clock):
    for store in (tmp_path / "first", tmp_path / "second"):
        store.mkdir()
        data = store / "sheet.tif"
        data.write_bytes(b"same-data")
        write_sidecar(
            data,
            build_metadata(
                get_source("pl.gugik.orto"),
                request={"sheet": "N-34-130-D-d-2-4"},
                data_path=data,
                version=VersionRef.downloaded().to_extra(),
            ),
        )
    assert_same_store(tmp_path / "first", tmp_path / "second")
    first = tmp_path / "first" / "sheet.tif.meta.json"
    assert json.loads(first.read_text())["downloaded_at"] == frozen_clock.isoformat(
        timespec="microseconds"
    )


def test_assert_same_store_reports_first_difference(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "different.meta.json").write_bytes(b"one")
    (b / "different.meta.json").write_bytes(b"two")
    with pytest.raises(AssertionError, match="different.meta.json"):
        assert_same_store(a, b)


def test_run_both_captures_cli_output_and_api_result(tmp_path):
    def api_call(output_dir):
        output_dir.mkdir()
        (output_dir / "data.bin").write_bytes(b"payload")
        return "api-result"

    result = run_both(["--help"], api_call, tmp_path)
    assert result.cli_code == 0
    assert "kartograf" in result.cli_stdout
    assert result.cli_stderr == ""
    assert result.api_result == "api-result"
    assert result.api_error is None
    assert result.api_store == tmp_path / "api"
    assert result.cli_store == tmp_path / "cli"
    assert (result.api_store / "data.bin").read_bytes() == b"payload"
