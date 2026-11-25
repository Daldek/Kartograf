"""CLI and public API write the same script (``script generate``, ADR-063 decision 5):
the text the CLI prints, the envelope of ``--json`` and the direct script of a plan
file of ``--plan``, which the command layer takes as the document of the plan."""

import json

import pytest

import kartograf
from kartograf import UnsupportedError, generate_script, run_command
from kartograf.cli import main
from kartograf.download.plan import UpdatePlan
from kartograf.envelope import wrap
from kartograf.error_report import error_report
from tests.unit.test_script import CORINE, LINE, _item, _nmt_source, _plan


@pytest.fixture(autouse=True)
def released(monkeypatch):
    """A released Kartograf, whose tag a Kartograf script pins."""
    monkeypatch.setattr(kartograf, "__version__", "0.9.0")


def _cli(argv, capsys) -> tuple[int, str, str]:
    code = main(["script", "generate", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize("shell", ["bash", "powershell"])
@pytest.mark.parametrize("line", [LINE, CORINE], ids=["nmt", "corine"])
def test_the_kartograf_script_is_the_text_of_the_library(shell, line, capsys):
    code, out, err = _cli(["--shell", shell, "--command", line], capsys)

    assert (code, err) == (0, "")
    assert out == generate_script(shell=shell, command=line).text


def test_json_prints_the_envelope_of_the_script(capsys):
    argv = ["--shell", "bash", "--command", LINE, "--json"]

    code, out, err = _cli(argv, capsys)

    script = generate_script(shell="bash", command=LINE)
    assert (code, err) == (0, "")
    assert out == wrap("script generate", script).to_json()
    assert json.loads(out)["result"]["schema"] == "kartograf-script/1"


@pytest.mark.parametrize("shell", ["bash", "powershell"])
def test_the_direct_script_of_a_plan_file_is_the_text_of_the_library(
    shell, tmp_path, capsys
):
    plan = _plan(
        _item("a.asc", url="https://example.test/a.asc", size=24),
        _item("c.tif", fetch=False, fetch_reason="built"),
        sources=(_nmt_source("Dane GUGiK"),),
    )
    path = tmp_path / "plan.json"
    path.write_text(plan.to_json(), encoding="utf-8")
    argv = ["--shell", shell, "--plan", str(path), "--direct", "--target", "~/out"]

    code, out, err = _cli(argv, capsys)
    json_code, envelope, _ = _cli([*argv, "--json"], capsys)

    saved = UpdatePlan.from_json(path.read_text(encoding="utf-8"))
    script = generate_script(shell=shell, plan=saved, direct=True, target="~/out")
    layer = run_command(
        "script generate",
        {"shell": shell, "direct": True, "target": "~/out"},
        plan=json.loads(path.read_text(encoding="utf-8")),  # type: ignore[arg-type]
    )
    assert (code, err) == (0, "")
    assert out == script.text
    assert json_code == 0
    assert envelope == wrap("script generate", script).to_json() == layer.to_json()
    assert [file["reason"] for file in json.loads(envelope)["result"]["left_out"]] == [
        "built"
    ]


def test_a_plan_with_nothing_to_download_is_the_error_of_the_library(tmp_path, capsys):
    plan = _plan(_item("c.tif", fetch=False, fetch_reason="built"))
    path = tmp_path / "plan.json"
    path.write_text(plan.to_json(), encoding="utf-8")
    argv = ["--shell", "bash", "--plan", str(path), "--direct", "--json"]

    code, out, err = _cli(argv, capsys)

    with pytest.raises(UnsupportedError) as caught:
        generate_script(shell="bash", plan=plan, direct=True)
    expected = error_report(caught.value).to_dict()
    printed = json.loads(err.splitlines()[-1])
    assert out == ""
    assert code == expected["exit_code"] == 15
    assert {k: printed[k] for k in ("code", "message", "details")} == {
        k: expected[k] for k in ("code", "message", "details")
    }
