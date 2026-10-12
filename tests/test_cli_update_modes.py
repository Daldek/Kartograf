"""CLI ``download``: --check-updates / --upgrade / --force / --plan (spec 4.2-4.5)."""

import json
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from tests.test_manager_campaigns import C14, REC, FakeCampaignProvider

G = "N-34-139-C-a-3-1"


def _run(fake, out, *argv):
    with patch(
        "kartograf.cli.download_cmd._create_provider_and_storage",
        return_value=(fake, None),
    ):
        return main(
            [
                "download",
                "--product",
                "nmt",
                "--resolution",
                "1m",
                "--vertical-crs",
                "EVRF2007",
                "-o",
                str(out),
                *argv,
            ]
        )


@pytest.mark.parametrize(
    "flags",
    [
        ("--check-updates", "--upgrade"),
        ("--check-updates", "--force"),
        ("--upgrade", "--force"),
    ],
)
def test_flags_mutually_exclusive(tmp_path, flags, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(FakeCampaignProvider(C14), tmp_path, "--sheet", G, *flags)
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_plan_requires_check_or_upgrade(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(FakeCampaignProvider(C14), tmp_path, "--sheet", G, "--plan", "p.json")
    assert exc.value.code == 2
    assert "--plan wymaga" in capsys.readouterr().err


def test_default_reports_newer_upgrade_downloads_it(tmp_path, capsys):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    assert _run(fake, tmp_path, "--sheet", G, "-q") == 0
    fake.records = {"newest": [REC["84183"]]}
    assert _run(fake, tmp_path, "--sheet", G) == 0
    captured = capsys.readouterr()
    assert (
        f"{G}: lokalna wersja 2025-04-27_83233; dostepna nowsza 2025-10-21_84183 "
        "(--upgrade)"
    ) in captured.out
    assert "Info: dostepna nowsza kampania dla 1 arkuszy" in captured.err
    assert fake.downloads == [REC["83233"].url]
    assert _run(fake, tmp_path, "--sheet", G, "--upgrade") == 0
    assert f"{G}: nowa wersja 2025-10-21_84183_" in capsys.readouterr().out
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]


def test_check_updates_prints_report_and_downloads_nothing(tmp_path, capsys):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    assert _run(fake, tmp_path, "--sheet", G, "-q") == 0
    capsys.readouterr()
    fake.records = {"newest": [REC["84183"]]}
    assert _run(fake, tmp_path, "--sheet", G, "--check-updates", "-q") == 0
    out = capsys.readouterr().out
    assert out == (f"{G}: nowsza: 2025-10-21_84183 (lokalna 2025-04-27_83233)\n")
    assert fake.downloads == [REC["83233"].url]


def test_check_updates_failure_is_partial_success_code(tmp_path, capsys):
    from tests.test_manager_campaigns import _transport_error

    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    assert _run(fake, tmp_path, "--sheet", G, "--check-updates") == 1
    assert f"{G}: nie udalo sie sprawdzic: " in capsys.readouterr().out


def test_check_updates_writes_plan_file_and_upgrade_executes_it(tmp_path, capsys):
    fake = FakeCampaignProvider(C14)
    plan = tmp_path / "plan.json"
    out = tmp_path / "data"
    assert _run(fake, out, "--sheet", G, "--check-updates", "--plan", str(plan)) == 0
    payload = json.loads(plan.read_text(encoding="utf-8"))
    assert payload["schema"] == "kartograf-plan/1"
    assert payload["store"] == str(out.resolve())
    assert [i["status"] for i in payload["items"]] == ["missing"]
    assert fake.downloads == []
    capsys.readouterr()

    assert _run(fake, out, "--sheet", G, "--upgrade", "--plan", str(plan)) == 0
    assert f"{G}: nowa wersja 2025-10-21_84183_" in capsys.readouterr().out
    assert fake.downloads == [REC["84183"].url]


def test_upgrade_plan_of_other_store_is_error(tmp_path, capsys):
    fake = FakeCampaignProvider(C14)
    plan = tmp_path / "plan.json"
    _run(fake, tmp_path / "a", "--sheet", G, "--check-updates", "--plan", str(plan))
    capsys.readouterr()
    rc = _run(fake, tmp_path / "b", "--sheet", G, "--upgrade", "--plan", str(plan))
    assert rc == 1
    assert "innego magazynu" in capsys.readouterr().err
    assert fake.downloads == []


def test_legacy_kampanie_info_once(tmp_path, capsys):
    (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "kampanie").mkdir(parents=True)
    assert _run(FakeCampaignProvider(C14), tmp_path, "--sheet", G, "-q") == 0
    err = capsys.readouterr().err
    assert err.count("Info: katalog kampanie/ z wersji 0.7.x nie jest uzywany") == 1


@pytest.mark.parametrize(
    "argv",
    [
        ("--product", "laz", "--sheet", G),
        ("--sheet", "302_5550", "--resolution", "2m", "--vertical-crs", "Bpv"),
        (
            "--bbox",
            "500000,300000,501000,301000",
            "--country",
            "pl",
            "--target-crs",
            "EPSG:2180",
        ),
        ("--bbox", "500000,300000,501000,301000", "--country", "auto"),
    ],
    ids=["laz", "cz-sheet", "target-crs", "country-auto"],
)
@pytest.mark.parametrize("flag", ["--check-updates", "--upgrade"])
def test_update_modes_rejected_outside_pl_sheets(tmp_path, capsys, argv, flag):
    with patch("kartograf.cli.download_cmd.DownloadManager") as manager:
        rc = main(["download", "-o", str(tmp_path), "--product", "nmt", *argv, flag])
    assert rc == 1
    assert "--check-updates/--upgrade dzialaja w tej wersji tylko" in (
        capsys.readouterr().err
    )
    manager.assert_not_called()
