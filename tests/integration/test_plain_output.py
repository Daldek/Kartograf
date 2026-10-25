"""Plain output (``output_dir``, ADR-054) through a real track: CZ LAZ.

The track talks to the recorded CUZK answers of ``tests/integration/test_cuzk_laz.py``;
what is checked is what a caller sees of the plain write: the files, their names, the
report, the refusal of a second run, ``--force``, the plan, an interrupted run and the
options that need a store.
"""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf import check_cz_laz, download_cz_laz
from kartograf.core.bbox import BBox
from kartograf.download.data import check_data, download_data
from kartograf.download.manager import DownloadManager
from kartograf.exceptions import ConflictError, NoCoverageError, ValidationError
from kartograf.marker import STORE_MARKERS
from kartograf.notices import FULL_SHEET_REDUNDANT, SKIPPED_INCOMPLETE
from kartograf.output import STAGING
from tests.integration.test_cuzk_laz import (
    CTES86_URL,
    CTES96_URL,
    CUZK_FIXTURES,
    CuzkSession,
    recorded_json,
    zip_member,
)
from tests.integration.test_cz_laz import recorded
from tests.integration.test_cz_orto import SUFFIXES, _members, cuzk  # noqa: F401
from tests.integration.test_manager_campaigns import (
    C14,
    C14_ALL,
    REC,
    FakeCampaignProvider,
    G,
    asc_for,
    c14_records,
    tag,
)
from tests.support.interrupt_fakes import EndlessResponse

SHEET = {"model": "dmr4g", "vertical_crs": "Bpv", "sheet": "CTES96"}
AREA = BBox(-448000, -1114000, -446000, -1113000, "EPSG:5514")


def listing(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


@pytest.fixture(autouse=True)
def default_root(monkeypatch, tmp_path):
    """The default store lies in the test directory: it must stay untouched."""
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default-store"))
    return tmp_path / "default-store"


def test_a_plain_run_writes_the_file_under_its_store_name_and_nothing_else(
    tmp_path, default_root
):
    out = tmp_path / "out" / "laz"

    with recorded(CuzkSession()) as session:
        result = download_cz_laz(output_dir=out, cache=False, **SHEET)

    (file,) = result.files
    body = zip_member(CTES96_URL)
    assert file.path == out / "CTES96.laz" and file.path.read_bytes() == body
    assert (file.status, file.label, file.version_path) == ("written", "", file.path)
    assert file.size_bytes == len(body)
    assert file.sha256 == hashlib.sha256(body).hexdigest()
    assert listing(out) == ["CTES96.laz"]  # no sidecar, no versions/, no staging
    assert not default_root.exists()
    assert session.of("GET") == [CTES96_URL]


def test_a_second_run_is_refused_before_the_first_byte_and_force_replaces(tmp_path):
    out = tmp_path / "out"
    with recorded(CuzkSession()):
        download_cz_laz(output_dir=out, cache=False, **SHEET)
    (out / "CTES96.laz").write_bytes(b"edited")

    with recorded(CuzkSession()) as session, pytest.raises(ConflictError) as error:
        download_cz_laz(output_dir=out, cache=False, **SHEET)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [str(out / "CTES96.laz")]
    assert session.of("GET") == []  # nothing was transferred
    assert (out / "CTES96.laz").read_bytes() == b"edited"
    assert listing(out) == ["CTES96.laz"]

    with recorded(CuzkSession()):
        forced = download_cz_laz(output_dir=out, update="force", cache=False, **SHEET)

    assert [file.status for file in forced.files] == ["replaced"]
    assert (out / "CTES96.laz").read_bytes() == zip_member(CTES96_URL)
    assert listing(out) == ["CTES96.laz"]


def test_the_plan_lists_each_target_with_its_action_and_probes_nothing(tmp_path):
    out = tmp_path / "out"

    with recorded(CuzkSession()) as session:
        before = check_cz_laz(output_dir=out, cache=False, **SHEET)
        download_cz_laz(output_dir=out, cache=False, **SHEET)
        after = check_cz_laz(output_dir=out, cache=False, **SHEET)

    assert (before.mode, before.root, before.output_dir) == (
        "plain",
        None,
        str(out.resolve()),
    )
    (planned,) = before.items
    assert (planned.action, planned.status, planned.path, planned.reason) == (
        "write",
        "missing",
        out / "CTES96.laz",
        None,
    )
    (conflict,) = after.items
    assert (conflict.action, conflict.reason) == ("conflict", "output_exists")
    assert after.ok  # a plan with a conflict is a result
    assert session.of("HEAD") == []  # no freshness signal is asked in plain mode
    assert not out.joinpath(STAGING).exists()


def test_a_failed_sheet_fails_alone_and_leaves_nothing_of_it(tmp_path):
    answer = recorded_json("klady_24_bbox_cieszyn.json")
    ctes96 = json.loads((CUZK_FIXTURES / "klady_sm5_where_ctes96.json").read_text())
    answer["features"] = ctes96["features"] + answer["features"]
    envelope = (AREA.min_x, AREA.min_y, AREA.max_x, AREA.max_y)
    session = CuzkSession(missing=(CTES86_URL,), envelopes={(24, envelope): answer})
    out = tmp_path / "out"

    with recorded(session):
        result = download_cz_laz(
            model="dmr4g", vertical_crs="Bpv", bbox=AREA, output_dir=out, cache=False
        )

    assert result.sheets == ("CTES86", "CTES96") and not result.ok
    assert [failure.sheet for failure in result.failed] == ["CTES86"]
    assert [file.status for file in result.files] == ["written"]
    assert listing(out) == ["CTES96.laz"]


class _EndlessCtes86(CuzkSession):
    def get(self, url, timeout=None, params=None, stream=False, **kwargs):
        if params is None and url == CTES86_URL:
            self._record("GET", url)
            return EndlessResponse({"Content-Length": "999999999"})
        return super().get(url, timeout, params, stream, **kwargs)


def test_ctrl_c_leaves_no_staging_directory_and_no_partial_target(tmp_path):
    answer = recorded_json("klady_24_bbox_cieszyn.json")
    ctes96 = json.loads((CUZK_FIXTURES / "klady_sm5_where_ctes96.json").read_text())
    answer["features"] = ctes96["features"] + answer["features"]
    envelope = (AREA.min_x, AREA.min_y, AREA.max_x, AREA.max_y)
    out = tmp_path / "out"

    def ctrl_c_when_a_sheet_ended(done: int, total: int) -> None:
        if done:
            raise KeyboardInterrupt

    with (
        recorded(_EndlessCtes86(envelopes={(24, envelope): answer})),
        pytest.raises(KeyboardInterrupt),
    ):
        download_cz_laz(
            model="dmr4g",
            vertical_crs="Bpv",
            bbox=AREA,
            output_dir=out,
            workers=2,
            cache=False,
            on_progress=ctrl_c_when_a_sheet_ended,
        )

    assert not (out / STAGING).exists()
    assert not any(path.suffix == ".part" for path in out.rglob("*"))
    assert "CTES86.laz" not in os.listdir(out)


def test_an_update_that_acts_on_versions_needs_the_store(tmp_path):
    with recorded(CuzkSession()) as session, pytest.raises(ValidationError) as error:
        download_cz_laz(
            output_dir=tmp_path / "out", update="upgrade", cache=False, **SHEET
        )

    assert error.value.reason == "store_only_option"
    assert error.value.option == "--upgrade"
    assert session.calls == []
    assert not (tmp_path / "out").exists()


def test_both_targets_are_refused_and_a_store_is_not_an_output(tmp_path):
    with pytest.raises(ValidationError) as error:
        download_cz_laz(output_dir=tmp_path / "a", root=tmp_path / "b", **SHEET)
    assert error.value.reason == "exclusive_options"

    store = tmp_path / "store"
    store.mkdir()
    (store / sorted(STORE_MARKERS)[0]).write_text("{}", encoding="utf-8")
    with recorded(CuzkSession()) as session, pytest.raises(ConflictError) as in_store:
        download_cz_laz(output_dir=store / "sub", cache=False, **SHEET)
    assert in_store.value.reason == "output_in_store"
    assert "--root" in str(in_store.value.hint)
    assert session.of("GET") == []
    assert listing(store) == [sorted(STORE_MARKERS)[0]]


def test_the_data_command_reports_a_plain_write_and_checks_the_whole_request_first(
    tmp_path, default_root
):
    out = tmp_path / "out"
    request = {
        "product": "laz",
        "sheet": "CTES96",
        "model": "dmr4g",
        "vertical_crs": "Bpv",
        "cache": False,
    }

    with recorded(CuzkSession()):
        plan = check_data(output_dir=out, **request)
        report = download_data(output_dir=out, **request)
    assert plan.mode == "plain" and [i.action for i in plan.items] == ["write"]
    assert not report.failed and report.ok
    assert (report.mode, report.root, report.output_dir) == ("plain", None, out)
    document = report.to_dict()
    assert document["mode"] == "plain" and document["root"] is None
    (entry,) = document["files"]
    assert entry["status"] == "written" and entry["path"] == str(out / "CTES96.laz")
    assert "label" not in entry and "version_path" not in entry
    assert listing(out) == ["CTES96.laz"]

    with recorded(CuzkSession()) as session, pytest.raises(ConflictError):
        download_data(output_dir=out, **request)
    assert session.of("GET") == []

    with recorded(CuzkSession()):
        forced = download_data(output_dir=out, update="force", **request)
    assert [f.file.status for f in forced.files] == ["replaced"]
    assert not default_root.exists()


def test_a_request_the_plain_mode_cannot_serve_fails_before_anything_is_created(
    tmp_path,
):
    out = tmp_path / "never"

    with pytest.raises(ValidationError) as error:
        download_data(
            product="nmt",
            sheet="N-34-130-D-d-2-4",
            vertical_crs="EVRF2007",
            resolution="1m",
            all_campaigns=True,
            output_dir=out,
            cache=False,
        )

    assert error.value.reason == "store_only_option"
    with pytest.raises(ValidationError):
        download_data(product="nope", sheet="x", output_dir=out, cache=False)
    assert not out.exists()


def test_the_cz_orthophoto_is_four_plain_files_of_one_archive(tmp_path, cuzk):  # noqa: F811
    out = tmp_path / "out"
    request = {"product": "orto", "country": "cz", "sheet": "CTES96", "cache": False}

    report = download_data(output_dir=out, **request)

    assert report.ok and not report.failed
    members = _members("CTES96")
    assert [(f.unit, f.file.status) for f in report.files] == [
        ("CTES96", "written")
    ] * 4
    assert listing(out) == sorted(f"CTES96{suffix}" for suffix in SUFFIXES)
    for suffix in SUFFIXES:
        assert (out / f"CTES96{suffix}").read_bytes() == members[suffix]
    (archive,) = cuzk.zip_requests()

    with pytest.raises(ConflictError) as error:
        download_data(output_dir=out, **request)  # nothing of the second run is fetched
    assert error.value.reason == "output_exists"
    assert len(error.value.details()["paths"]) == 4
    assert cuzk.zip_requests() == [archive]
    plan = check_data(output_dir=out, **request)
    assert [(i.action, i.reason) for i in plan.items] == [
        ("conflict", "output_exists")
    ] * 4


# --------------------------------------------------------------------------
# PL sheets: the newest FULL flight, a sheet without one is skipped (ADR-054, 5)
# --------------------------------------------------------------------------

PL = {
    "product": "nmt",
    "vertical_crs": "EVRF2007",
    "resolution": "1m",
    "cache": False,
}


def _pl_sheets(fake):
    return patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    )


def _partial(records):
    return [replace(record, full_sheet=False) for record in records]


def test_a_pl_sheet_is_the_newest_full_flight_not_the_newest_flight(tmp_path):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"

    result = DownloadManager(fake, output_dir=out).download_sheet(G)

    full = REC["83233"]  # 2025-04-27; the newest flight, 84183, is partial
    (file,) = result.files[G]
    assert (file.status, file.label, file.path) == ("written", "", out / f"{G}.asc")
    assert file.path.read_bytes() == asc_for(G, f"v1 {tag(full)}")
    assert fake.downloads == [full.url]
    assert result.written == [G] and result.incomplete == {}
    assert listing(out) == [f"{G}.asc"]  # no sidecar, no versions/, no full_sheet/


def test_year_bounds_filter_the_flights_before_the_full_one_is_taken(tmp_path):
    fake = FakeCampaignProvider(C14)

    DownloadManager(fake, output_dir=tmp_path, max_year=2024).download_sheet(G)

    assert fake.downloads == [REC["78047"].url]  # 2023: the newest full one <= 2024


def test_a_sheet_without_a_full_flight_is_left_out_with_its_newest_flight(tmp_path):
    fake = FakeCampaignProvider(
        {"all": _partial(C14_ALL), "newest": _partial(C14["newest"])}
    )

    with pytest.raises(NoCoverageError) as error:
        DownloadManager(fake, output_dir=tmp_path).download_sheet(G)

    assert error.value.reason == "skipped_incomplete"
    assert "2025-10-21" in str(error.value) and "--root" in str(error.value.hint)
    assert fake.downloads == [] and listing(tmp_path) == []


def test_a_list_skips_the_incomplete_sheet_and_writes_the_others(tmp_path):
    records = [*_partial(c14_records(G)), *c14_records("N-34-139-C-a-3-2")]
    fake = FakeCampaignProvider({"all": records, "newest": records[:1]})

    result = DownloadManager(fake, output_dir=tmp_path).download_sheets(
        [G, "N-34-139-C-a-3-2"]
    )

    assert list(result.incomplete) == [G] and result.failed == []
    assert result.written == ["N-34-139-C-a-3-2"]
    assert listing(tmp_path) == ["N-34-139-C-a-3-2.asc"]


def test_the_data_command_reports_the_skipped_sheet_and_fails_when_all_are_skipped(
    tmp_path,
):
    partial = FakeCampaignProvider(
        {"all": _partial(C14_ALL), "newest": _partial(C14["newest"])}
    )
    with _pl_sheets(partial):
        report = download_data(sheet=G, output_dir=tmp_path / "out", **PL)

    assert not report.ok and report.files == ()
    (skipped,) = report.skipped
    assert (skipped.id, skipped.reason) == (G, "skipped_incomplete")
    assert "--root" in skipped.message
    (failure,) = report.failed
    assert (failure.code, failure.reason) == ("no_data", "skipped_incomplete")
    assert [n.code for n in report.notices] == [SKIPPED_INCOMPLETE]
    assert report.notices[0].level == "warning"
    assert not (tmp_path / "out").exists()
    assert report.to_dict()["skipped"][0]["reason"] == "skipped_incomplete"


def test_the_data_command_writes_the_full_flight_and_checks_before_the_first_byte(
    tmp_path,
):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"
    with _pl_sheets(fake):
        plan = check_data(sheet=G, output_dir=out, full_sheet=True, **PL)
        report = download_data(sheet=G, output_dir=out, full_sheet=True, **PL)

    assert [(i.name, i.action, i.segment) for i in plan.items] == [
        (f"{G}.asc", "write", "")
    ]
    assert plan.items[0].available_label == "2025-04-27_83233"
    assert report.ok and [f.file.status for f in report.files] == ["written"]
    assert [n.code for n in report.notices] == [FULL_SHEET_REDUNDANT]
    assert fake.downloads == [REC["83233"].url]  # the extra full flight is not fetched
    assert listing(out) == [f"{G}.asc"]

    with _pl_sheets(fake), pytest.raises(ConflictError) as error:
        download_data(sheet=G, output_dir=out, **PL)
    assert error.value.reason == "output_exists"
    assert len(fake.downloads) == 1
    with _pl_sheets(fake):
        forced = download_data(sheet=G, output_dir=out, update="force", **PL)
    assert [f.file.status for f in forced.files] == ["replaced"]
