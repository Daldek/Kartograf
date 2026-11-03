"""The result envelope ``kartograf-result/1``: status, units and exit codes."""

import dataclasses
import json
from dataclasses import replace

import pytest

import kartograf
from kartograf.download.availability import AvailabilityReport
from kartograf.download.data import DataReport, UnitFailure, UnitFile
from kartograf.download.plan import UpdatePlan
from kartograf.envelope import (
    _READERS,
    CommandResult,
    ResultItem,
    exit_code_of,
    outcome_of,
    wrap,
)
from kartograf.serialization import SCHEMAS, Document, encode
from tests.contract.test_json_contract import (
    _area,
    _notice,
    _plan_item,
    _sources,
    _unit_file,
)

COMMAND = "elevation download"


def _file(unit: str) -> UnitFile:
    return replace(_unit_file(), unit=unit)


def _failure(unit: str, kind: str = "download") -> UnitFailure:
    return UnitFailure(unit, "PL", f"{unit}: error", kind)  # type: ignore[arg-type]


def _report(*, files=(), failed=(), stale=(), ok=True, notices=()) -> DataReport:
    return DataReport(
        files=tuple(files),
        failed=tuple(failed),
        stale=tuple(stale),
        superseded=(),
        notices=tuple(notices),
        ok=ok,
    )


def _summary(document: Document | None, **kwargs) -> tuple[str, list[tuple[str, ...]]]:
    """The status and the ``(id, status, code, reason)`` of every item."""
    outcome = outcome_of(document, **kwargs)
    return outcome.status, [
        (i.id, i.status, i.code or "", i.reason or "") for i in outcome.items
    ]


# -- the reports of kartograf-download/1 --------------------------------------------


def test_a_report_with_every_unit_done_is_ok_and_lists_each_unit_once():
    report = _report(files=[_file("A"), _file("A"), _file("B")])

    assert _summary(report) == ("ok", [("A", "ok", "", ""), ("B", "ok", "", "")])
    assert exit_code_of(report) == 0


def test_a_failed_unit_next_to_a_done_one_is_partial():
    report = _report(
        files=[_file("A")], failed=[_failure("B", "no_coverage")], ok=False
    )

    assert _summary(report) == (
        "partial",
        [("A", "ok", "", ""), ("B", "failed", "no_data", "no_coverage")],
    )
    assert exit_code_of(report) == 10


def test_a_run_with_no_unit_done_is_failed():
    report = _report(
        failed=[_failure("A"), _failure("B", "year_out_of_range")], ok=False
    )

    assert _summary(report) == (
        "failed",
        [
            ("A", "failed", "source_unavailable", ""),
            ("B", "failed", "no_data", "year_out_of_range"),
        ],
    )
    assert exit_code_of(report) == 11


def test_the_item_of_a_failure_carries_its_text():
    report = _report(failed=[_failure("A")], ok=False)

    (item,) = outcome_of(report).items

    assert item == ResultItem(
        "A", "failed", "source_unavailable", None, report.failed[0].error
    )


def test_a_unit_with_a_file_and_a_failure_is_one_failed_item():
    report = _report(files=[_file("A"), _file("B")], failed=[_failure("A")], ok=False)

    assert _summary(report) == (
        "partial",
        [("B", "ok", "", ""), ("A", "failed", "source_unavailable", "")],
    )


def test_a_failed_part_of_a_successful_report_is_a_notice_not_an_item():
    """``--country auto`` with one country down: ``ok`` stays true (A3-2)."""
    report = _report(files=[_file("A")], failed=[_failure("CZ", "country")], ok=True)

    assert _summary(report) == ("ok", [("A", "ok", "", "")])
    assert exit_code_of(report) == 0


def test_a_position_the_source_changed_since_the_plan_is_a_conflict():
    stale = _plan_item()
    report = _report(files=[_file("A")], stale=[stale], ok=False)

    status, items = _summary(report)

    assert status == "partial"
    assert items[1] == (stale.store_path, "failed", "conflict", "stale_plan")


def test_ok_false_without_a_failed_unit_is_an_internal_error_of_the_command():
    status, items = _summary(_report(ok=False), command=COMMAND)

    assert (status, items) == ("failed", [(COMMAND, "failed", "internal_error", "")])


# -- the plan and the availability report ---------------------------------------------


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["current", "missing", "newer", "unverifiable"], ("ok", 0)),
        (["current", "check_failed"], ("partial", 10)),
        (["check_failed"], ("failed", 11)),
    ],
)
def test_the_units_of_a_plan_are_its_positions(statuses, expected):
    items = tuple(
        replace(_plan_item(), name=f"{n}.asc", status=status)  # type: ignore[arg-type]
        for n, status in enumerate(statuses)
    )
    failed = [i for i in items if i.status == "check_failed"]
    plan = UpdatePlan(
        "/store",
        "2026-10-24T10:00:00+00:00",
        "0.8.0",
        tuple(replace(i, error="HTTP 503") if i in failed else i for i in items),
        (),
    )

    outcome = outcome_of(plan)

    assert (outcome.status, exit_code_of(plan)) == expected
    assert [i.id for i in outcome.items] == [i.store_path for i in plan.items]
    for item in outcome.items:
        if item.status == "failed":
            assert (item.code, item.reason, item.message) == (
                "source_unavailable",
                "check_failed",
                "HTTP 503",
            )


def _availability(*, failed=(), ok=True) -> AvailabilityReport:
    return AvailabilityReport(
        request={"product": "nmt"},
        checked_at="2026-10-24T10:00:00+00:00",
        areas=(_area(), replace(_area(), country="CZ")),
        combinations=(),
        failed=tuple(failed),
        notices=(_notice(),),
        ok=ok,
    )


def test_the_units_of_an_availability_report_are_its_countries():
    report = _availability()

    assert _summary(report) == ("ok", [("PL", "ok", "", ""), ("CZ", "ok", "", "")])


def test_a_country_that_could_not_be_checked_makes_the_report_partial():
    report = _availability(failed=[_failure("CZ", "country")], ok=False)

    assert _summary(report) == (
        "partial",
        [
            ("PL", "ok", "", ""),
            ("CZ", "ok", "", ""),
            ("CZ", "failed", "source_unavailable", ""),
        ],
    )


# -- documents with no verdict -------------------------------------------------------


def test_a_document_with_no_verdict_is_ok_with_no_items():
    assert _summary(_sources()) == ("ok", [])
    assert _summary(None) == ("ok", [])
    assert outcome_of(_sources()).notices == ()


def test_a_document_with_a_verdict_and_no_reader_is_a_program_error():
    @dataclasses.dataclass(frozen=True)
    class Unread(Document):
        SCHEMA = "kartograf-test-unread/1"

        ok: bool

    with pytest.raises(TypeError, match="Unread.*no reader"):
        outcome_of(Unread(ok=True))


def test_every_document_of_the_package_with_a_verdict_has_a_reader():
    documents = {
        cls
        for classes in SCHEMAS.values()
        for cls in classes
        if cls.__module__.startswith("kartograf.")
    }
    judged = {
        cls
        for cls in documents
        if "ok" in {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        or isinstance(getattr(cls, "ok", None), property)
    }

    assert judged
    assert judged <= set(_READERS)


# -- the document ------------------------------------------------------------------


def test_the_envelope_has_a_fixed_set_of_keys_and_its_result_keeps_its_schema():
    report = _report(files=[_file("A")], notices=[_notice()])

    document = wrap(COMMAND, report).to_dict()

    assert list(document) == [
        "schema",
        "tool",
        "version",
        "command",
        "check",
        "status",
        "result",
        "items",
        "notices",
    ]
    assert document["schema"] == "kartograf-result/1"
    assert (document["tool"], document["version"]) == (
        "kartograf",
        kartograf.__version__,
    )
    assert (document["command"], document["check"], document["status"]) == (
        COMMAND,
        False,
        "ok",
    )
    assert document["result"] == report.to_dict()
    assert document["items"] == [{"id": "A", "status": "ok"}]
    assert document["notices"] == [
        {"level": "info", "code": "sheet_list", "message": _notice().message}
    ]


def test_items_and_notices_are_always_present_and_nothing_is_paged():
    document = wrap("elevation list-sources", _sources()).to_dict()

    assert document["items"] == [] and document["notices"] == []
    assert "page" not in document


def test_an_item_leaves_out_the_keys_it_has_no_value_for():
    assert encode(ResultItem("A", "ok")) == {"id": "A", "status": "ok"}
    assert encode(ResultItem("A", "failed", "io_error")) == {
        "id": "A",
        "status": "failed",
        "code": "io_error",
    }


def test_the_json_text_is_the_document_and_the_exit_code_follows_the_status():
    envelope = wrap(COMMAND, _report(failed=[_failure("A")], ok=False))

    assert json.loads(envelope.to_json()) == envelope.to_dict()
    assert envelope.to_json().endswith("}\n")
    assert isinstance(envelope, CommandResult)
    assert envelope.exit_code == 11
    assert replace(envelope, status="cancelled").exit_code == 130


def test_a_plan_is_wrapped_as_a_check():
    plan = UpdatePlan("/store", "2026-10-24T10:00:00+00:00", "0.8.0", (), ())

    envelope = wrap(COMMAND, plan, check=True)

    assert envelope.result is plan
    assert envelope.to_dict()["check"] is True
    assert envelope.to_dict()["result"] == plan.to_dict()
