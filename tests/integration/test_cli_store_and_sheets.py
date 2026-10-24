"""``kartograf store ...`` and ``kartograf sheet find``: the CLI of the commands that
were API-only (what a line prints, its ``--json`` document, its input errors)."""

import json

import pytest

from kartograf import find_sheets
from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.testing import PL_SEGMENT, build_fixture_store
from tests.support.errors import error_document

AREA = ["--bbox", "565000,242000,566000,243000"]
SCALE = ["--scale", "1:10000", "--sheet-system", "1992"]


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "data"
    fixture = build_fixture_store(root)
    return fixture.root


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_sheet_find_prints_the_sheets_and_their_number(capsys):
    code, out, err = run(capsys, "sheet", "find", *AREA, *SCALE)

    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[0] == "Arkusze PL-1992 1:10000 (2):"
    assert lines[2:] == ["  M-34-64-D-d-1-4", "  M-34-64-D-d-3-2"]


def test_sheet_find_json_is_the_envelope_of_the_library_document(capsys):
    code, out, err = run(capsys, "sheet", "find", *AREA, *SCALE, "--json")
    expected = find_sheets(
        bbox=BBox(565000, 242000, 566000, 243000, "EPSG:2180"),
        scale="1:10000",
        sheet_system="1992",
    )

    document = json.loads(out)
    assert (code, err) == (0, "")
    assert document["command"] == "sheet find"
    assert document["result"] == expected.to_dict()


def test_sheet_find_takes_the_bbox_in_another_crs(capsys):
    code, out, _ = run(
        capsys, "sheet", "find", "--bbox", "19.9,50.0,19.91,50.01", "--bbox-crs",
        "epsg:4326", *SCALE, "--json",
    )  # fmt: skip

    assert code == 0
    assert json.loads(out)["result"]["request"]["bbox_crs"] == "EPSG:4326"


@pytest.mark.parametrize(
    ("argv", "option"),
    [
        (["sheet", "find", *SCALE], None),  # no area
        (["sheet", "find", *AREA, "--layer", "x", *SCALE], "layer"),
        (["sheet", "find", *AREA, "--sheet-system", "1992"], "scale"),
    ],
)
def test_sheet_find_input_errors_are_validation_errors(capsys, argv, option):
    code, out, err = run(capsys, *argv)

    document = error_document(err)
    assert (code, out) == (2, "")
    assert document["code"] == "validation_error"
    assert document["command"] == "sheet find"
    assert document["details"].get("option") == option


def test_store_overview_lists_the_segments(capsys, store):
    code, out, err = run(capsys, "store", "overview", "-o", str(store))

    assert (code, err) == (0, "")
    assert out.splitlines()[0].endswith("(2 segmentow):")
    assert PL_SEGMENT in out and "nmt/cz_dmr4g_bpv" in out


def test_store_overview_of_an_empty_directory_says_so(capsys, tmp_path):
    code, out, _ = run(capsys, "store", "overview", "-o", str(tmp_path))

    assert code == 0
    assert "jest pusty" in out


def test_store_overview_json_is_the_envelope_of_the_library_document(capsys, store):
    code, out, _ = run(capsys, "store", "overview", "-o", str(store), "--json")

    document = json.loads(out)
    assert code == 0
    assert document["command"] == "store overview"
    assert [s["segment"] for s in document["result"]["segments"]] == [
        "nmt/cz_dmr4g_bpv",
        PL_SEGMENT,
    ]


def test_store_entries_lists_the_first_entries_and_says_when_more_follow(capsys, store):
    code, out, err = run(
        capsys, "store", "entries", "-o", str(store), "--segment", PL_SEGMENT,
        "--limit", "2",
    )  # fmt: skip

    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[0] == f"Segment {PL_SEGMENT}: 2 wpisow (limit 2, sa dalsze)"
    assert [line.split()[0] for line in lines[2:]] == ["link", "full_sheet"]


def test_store_entries_takes_the_units_as_a_comma_separated_list(capsys, store):
    code, out, _ = run(
        capsys, "store", "entries", "-o", str(store), "--segment", PL_SEGMENT,
        "--limit", "50", "--units", "N-34-130-D-d-2-4,N-34-130-D-d-2-3", "--json",
    )  # fmt: skip

    result = json.loads(out)["result"]
    assert code == 0
    assert result["units"] == ["N-34-130-D-d-2-4", "N-34-130-D-d-2-3"]
    assert result["truncated"] is False
    assert {e["kind"] for e in result["entries"]} == {"version", "link", "full_sheet"}


@pytest.mark.parametrize(
    ("extra", "option"),
    [
        (["--limit", "5"], "segment"),
        (["--segment", PL_SEGMENT], "limit"),
        (["--segment", PL_SEGMENT, "--limit", "0"], "limit"),
    ],
)
def test_store_entries_requires_its_segment_and_a_positive_limit(
    capsys, store, extra, option
):
    code, out, err = run(capsys, "store", "entries", "-o", str(store), *extra)

    document = error_document(err)
    assert (code, out) == (2, "")
    assert document["details"]["option"] == option


def test_the_store_commands_require_the_store_and_the_path(capsys):
    code, _, err = run(capsys, "store", "overview")
    assert (code, error_document(err)["details"]["option"]) == (2, "output_dir")

    code, _, err = run(capsys, "store", "sidecar")
    assert (code, error_document(err)["details"]["option"]) == (2, "path")


def test_a_missing_store_is_an_io_error(capsys, tmp_path):
    code, out, err = run(capsys, "store", "overview", "-o", str(tmp_path / "none"))

    assert (code, out) == (9, "")
    assert error_document(err)["code"] == "io_error"


def test_store_sidecar_prints_the_sidecar_of_a_file(capsys, store):
    data = fixture_file(store)

    code, out, err = run(capsys, "store", "sidecar", "--path", str(data))

    assert (code, err) == (0, "")
    assert out.startswith(f"Sidecar: {data}\n")
    assert json.loads(out.split("\n", 1)[1])["dataset"] == "pl.gugik.nmt_1m"


def test_store_sidecar_json_has_the_raw_sidecar_and_a_bad_sidecar_is_data_error(
    capsys, store, tmp_path
):
    data = fixture_file(store)
    code, out, _ = run(capsys, "store", "sidecar", "--path", str(data), "--json")
    assert code == 0
    assert json.loads(out)["result"]["sidecar"]["raw"]["dataset"] == "pl.gugik.nmt_1m"

    orphan = tmp_path / "orphan.asc"
    orphan.write_text("x")
    code, out, err = run(capsys, "store", "sidecar", "--path", str(orphan))
    assert (code, out) == (7, "")
    assert error_document(err)["details"]["reason"] == "invalid_sidecar"


def fixture_file(store):
    return next(store.rglob("*.asc"))
