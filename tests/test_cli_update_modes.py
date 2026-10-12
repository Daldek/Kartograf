"""CLI ``download``: --check-updates / --upgrade / --force / --plan (spec 4.2-4.5)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.cz_sheets import CzSheetResult
from tests.test_cli import _CZ_FACTORY_PATCH, _cz_provider_mock
from tests.test_laz_download import FakeProvider, _selection, _tile
from tests.test_manager_campaigns import C14, REC, FakeCampaignProvider

G = "N-34-139-C-a-3-1"


def _run(fake, out, *argv):
    with patch(
        "kartograf.download.data._create_provider_and_storage",
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


# --- every download track (plan 2/3 Task 11) ---------------------------------

CZ_BBOX = ("--bbox=-447000,-1114000,-446000,-1113000", "--bbox-crs", "EPSG:5514")
CZ_2M = ("--resolution", "2m", "--vertical-crs", "Bpv")
PL_1M = ("--resolution", "1m", "--vertical-crs", "EVRF2007")
PL_BBOX = ("--bbox", "500000,300000,501000,301000", "--country", "pl")
LAZ_SHEET = "N-34-130-D-d-2-4"
# Cieszyn: a bbox crossing the PL-CZ border (EPSG:4326)
BORDER = ("--bbox", "18.60,49.73,18.66,49.76", "--bbox-crs", "EPSG:4326")
AUTO = (
    "--country",
    "auto",
    "--resolution",
    "pl=1m,cz=2m",
    "--vertical-crs",
    "pl=EVRF2007,cz=Bpv",
)


class LazCliProvider(FakeProvider):
    """LAZ provider of the CLI: one selected tile, downloads counted."""

    def select_tiles(self, bbox, **kwargs):
        return _selection(_tile(LAZ_SHEET, crs="PL-1992"))


def _download(out, *argv):
    return main(["download", "--product", "nmt", "-o", str(out), *argv])


def _no_pl_wcs():
    """PL cutout: any PRG/WCS request fails the test."""
    return patch(
        "kartograf.providers.pl.prg.fetch_land_mask",
        side_effect=AssertionError("PRG/WCS nie powinno byc wolane"),
    )


TRACKS = {
    "laz": ("--product", "laz", "--sheet", LAZ_SHEET, "--vertical-crs", "EVRF2007"),
    "cz-sheet": ("--sheet", "302_5550", *CZ_2M),
    "cz-bbox": (*CZ_BBOX, "--country", "cz", *CZ_2M),
    "pl-cutout": (*PL_BBOX, *PL_1M, "--target-crs", "EPSG:5514"),
    "auto": (*BORDER, *AUTO, "--target-crs", "EPSG:3045"),
}


@pytest.mark.parametrize("flag", ["--check-updates", "--upgrade"])
@pytest.mark.parametrize("track", sorted(TRACKS))
def test_update_flags_accepted_for_every_download_track(tmp_path, capsys, track, flag):
    cz = _cz_provider_mock()
    laz = LazCliProvider()
    with (
        patch(_CZ_FACTORY_PATCH, return_value=cz),
        patch("kartograf.providers.pl.gugik_laz.GugikLazProvider", return_value=laz),
        _no_pl_wcs() as prg,
        patch(
            "kartograf.download.cutout.download_pl_cutout",
            return_value=PlCutoutResult(None),
        ) as pl_run,
    ):
        rc = _download(tmp_path / "out", *TRACKS[track], flag)
    err = capsys.readouterr().err
    assert rc == 0, err
    assert "Error:" not in err
    prg.assert_not_called()
    if flag == "--check-updates":  # checking never downloads
        assert laz.calls == []
        cz.download.assert_not_called()
        cz.download_bbox.assert_not_called()
        pl_run.assert_not_called()


def test_check_updates_auto_writes_merged_plan(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    out = tmp_path / "out"
    with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()), _no_pl_wcs():
        rc = _download(
            out,
            *BORDER,
            *AUTO,
            "--target-crs",
            "EPSG:3045",
            "--check-updates",
            "--plan",
            str(plan),
        )
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    payload = json.loads(plan.read_text(encoding="utf-8"))
    assert payload["store"] == str(out.resolve())
    assert sorted(i["track"] for i in payload["items"]) == ["cz_cutout", "pl_cutout"]
    assert {i["status"] for i in payload["items"]} == {"missing"}
    assert captured.err.count("Info: zapisano plan aktualizacji") == 1


def test_upgrade_plan_executes_only_planned_tracks(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    out = tmp_path / "out"
    cz = _cz_provider_mock()
    argv = (*BORDER, *AUTO, "--target-crs", "EPSG:3045")
    with patch(_CZ_FACTORY_PATCH, return_value=cz), _no_pl_wcs() as prg:
        _download(out, *argv, "--check-updates", "--plan", str(plan))
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["items"] = [i for i in payload["items"] if i["track"] == "cz_cutout"]
        plan.write_text(json.dumps(payload), encoding="utf-8")
        capsys.readouterr()
        rc = _download(out, *argv, "--upgrade", "--plan", str(plan))
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    cz.download_bbox.assert_called_once()  # the planned CZ cutout
    prg.assert_not_called()  # the PL cutout was removed from the plan
    assert ": nowa wersja " in captured.out
    assert not list(out.glob("nmt/pl_*/bbox/*.tif"))


def test_status_line_local_none_hint(tmp_path, capsys):
    cz = _cz_provider_mock()
    with patch(_CZ_FACTORY_PATCH, return_value=cz):
        assert _download(tmp_path, "--sheet", "302_5550", *CZ_2M) == 0
        capsys.readouterr()
        assert _download(tmp_path, "--sheet", "302_5550", *CZ_2M) == 0
    out = capsys.readouterr().out
    assert out.startswith("302_5550: lokalna wersja ")
    assert out.rstrip().endswith("(bez sprawdzania; --check-updates)")
    cz.download.assert_called_once()


def test_upgrade_none_signal_info_force(tmp_path, capsys):
    cz = _cz_provider_mock()
    with patch(_CZ_FACTORY_PATCH, return_value=cz):
        _download(tmp_path, "--sheet", "302_5550", *CZ_2M, "-q")
        assert _download(tmp_path, "--sheet", "302_5550", *CZ_2M, "--upgrade") == 0
    captured = capsys.readouterr()
    assert "302_5550: lokalna wersja " in captured.out
    assert "(bez sprawdzania" not in captured.out
    assert "Info: 302_5550: lokalna wersja " in captured.err
    assert "pobierz ponownie: --force" in captured.err
    cz.download.assert_called_once()


def test_sm5_check_failed_warning_exit_code(tmp_path, capsys):
    from kartograf.exceptions import DownloadError

    cz = _cz_provider_mock("5m")
    cz.sheet_index.sm5_sheet.return_value = SimpleNamespace(name="CTES96", podil=1.0)
    sm5 = ("--sheet", "CTES96", "--vertical-crs", "Bpv")
    with patch(_CZ_FACTORY_PATCH, return_value=cz):
        assert _download(tmp_path, *sm5, "-q") == 0
        cz.sm5_signal.side_effect = DownloadError("HEAD 503")
        capsys.readouterr()
        assert _download(tmp_path, *sm5, "--check-updates") == 1
        assert "CTES96: nie udalo sie sprawdzic: HEAD 503" in capsys.readouterr().out
        assert _download(tmp_path, *sm5) == 0
    captured = capsys.readouterr()
    assert "Warning: CTES96: nie udalo sie sprawdzic zrodla (HEAD 503)" in captured.err
    assert captured.out.startswith("CTES96: lokalna wersja ")
    cz.download.assert_called_once()


def test_laz_summary_counters(tmp_path, capsys):
    laz = LazCliProvider()
    argv = TRACKS["laz"]
    with patch("kartograf.providers.pl.gugik_laz.GugikLazProvider", return_value=laz):
        assert _download(tmp_path, *argv) == 0
        first = capsys.readouterr().out
        assert _download(tmp_path, *argv) == 0
        second = capsys.readouterr().out
    assert "Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0" in first
    assert "Nowe: 0, nowa etykieta: 0, bez zmian: 0, lokalne: 1, bledy: 0" in second
    assert ".laz: lokalna wersja " in second
    assert len(laz.calls) == 1


@pytest.mark.parametrize(
    ("flag", "update"),
    [((), None), (("--upgrade",), "upgrade"), (("--force",), "force")],
)
def test_cz_sheet_cli_uses_library(tmp_path, flag, update):
    with patch(
        "kartograf.download.cz_sheets.download_cz_sheet",
        return_value=CzSheetResult(None, False),
    ) as run:
        assert _download(tmp_path, "--sheet", "302_5550", *CZ_2M, *flag) == 0
    assert run.call_args.args[0] == "302_5550"
    assert run.call_args.kwargs["update"] == update
    assert run.call_args.kwargs["resolution"] == "2m"
