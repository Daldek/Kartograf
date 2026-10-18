"""The ``--json`` mode of the CLI: the document of stdout and the exit code of a
result (spec 7.1)."""

import pytest

from kartograf.cli._json import emit_document
from kartograf.download.plan import PlanItem, new_plan
from kartograf.error_report import error_report
from kartograf.exceptions import DownloadError, ValidationError

SHEET = "N-34-130-D-d-2-4"


@pytest.mark.parametrize(
    ("status", "code"),
    [("current", 0), ("missing", 0), ("check_failed", 1)],
)
def test_emit_document_prints_the_document_and_returns_the_code_of_ok(
    capsys, tmp_path, status, code
):
    item = PlanItem(
        "pl_sheet", "nmt", "1992", SHEET, SHEET, None, None, None, None, status
    )
    plan = new_plan(tmp_path, [item])

    assert emit_document(plan) == code
    assert capsys.readouterr().out == plan.to_json()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ValidationError("zle dane"), 2),
        (DownloadError("siec"), 1),
        (KeyboardInterrupt(), 130),
    ],
)
def test_emit_document_returns_the_exit_code_of_an_error_document(capsys, error, code):
    report = error_report(error)

    assert emit_document(report) == code == report.exit_code
    assert capsys.readouterr().out == report.to_json()
