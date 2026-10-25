"""CLI ``elevation download``: --check-updates / --upgrade / --force / --plan
(spec 4.2-4.5)."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.cli.commands import main
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.cz_sheets import CzSheetResult
from tests.integration.test_cli import _CZ_FACTORY_PATCH, _cz_provider_mock
from tests.integration.test_laz_download import FakeProvider, _selection, _tile
from tests.integration.test_manager_campaigns import C14, REC, FakeCampaignProvider
from tests.support.errors import without_error_document

G = "N-34-139-C-a-3-1"
# Subject of the status and plan lines: the path below --root (one format).
G_PATH = f"nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/{G}.asc"


def _run(fake, out, *argv):
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    ):
        return main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--resolution",
                "1m",
                "--vertical-crs",
                "EVRF2007",
                "--root",
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
    rc = _run(FakeCampaignProvider(C14), tmp_path, "--sheet", G, "--plan", "p.json")
    assert rc == 2
    assert "Error: --plan wymaga" in capsys.readouterr().err


def test_default_reports_newer_upgrade_downloads_it(tmp_path, capsys):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    assert _run(fake, tmp_path, "--sheet", G, "-q") == 0
    fake.records = {"newest": [REC["84183"]]}
    assert _run(fake, tmp_path, "--sheet", G) == 0
    captured = capsys.readouterr()
    assert (
        f"{G_PATH}: lokalna wersja 2025-04-27_83233; dostepna nowsza "
        "2025-10-21_84183 (--upgrade)"
    ) in captured.out
    assert "Info: dostepna nowsza kampania dla 1 arkusza" in captured.err
    assert fake.downloads == [REC["83233"].url]
    assert _run(fake, tmp_path, "--sheet", G, "--upgrade") == 0
    assert f"{G_PATH}: nowa wersja 2025-10-21_84183_" in capsys.readouterr().out
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]


def test_check_updates_prints_report_and_downloads_nothing(tmp_path, capsys):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    assert _run(fake, tmp_path, "--sheet", G, "-q") == 0
    capsys.readouterr()
    fake.records = {"newest": [REC["84183"]]}
    assert _run(fake, tmp_path, "--sheet", G, "--check-updates", "-q") == 0
    out = capsys.readouterr().out
    assert out == (f"{G_PATH}: nowsza: 2025-10-21_84183 (lokalna 2025-04-27_83233)\n")
    assert fake.downloads == [REC["83233"].url]


def test_check_updates_failure_is_partial_success_code(tmp_path, capsys):
    from tests.integration.test_manager_campaigns import _transport_error

    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    assert _run(fake, tmp_path, "--sheet", G, "--check-updates") == 11
    assert f"{G_PATH}: nie udalo sie sprawdzic: " in capsys.readouterr().out


def test_check_updates_index_failure_names_no_download(tmp_path, capsys):
    """Live test 0.8.0: an unreachable WFS index under ``--check-updates``
    ends the line with the fact ("wynik bylby niepelny") - no "ponow
    pobranie" of a download that never ran (download summaries add it)."""
    offline = Mock(spec=requests.Session)
    offline.get.side_effect = requests.ConnectionError("offline")
    with (
        patch("kartograf.transport.http.make_gugik_session", return_value=offline),
        patch("kartograf.transport.http.time.sleep"),
    ):
        grid = ["--resolution", "1m", "--vertical-crs", "EVRF2007"]
        argv = ["--sheet", G, "--root", str(tmp_path), "--check-updates"]
        rc = main(["elevation", "download", "--product", "nmt", *grid, *argv])
    assert rc == 11
    line = next(
        text for text in capsys.readouterr().out.splitlines() if text.startswith(G_PATH)
    )
    assert line.startswith(f"{G_PATH}: nie udalo sie sprawdzic: ")
    assert line.endswith(" - the result would be incomplete")


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
    assert f"{G_PATH}: nowa wersja 2025-10-21_84183_" in capsys.readouterr().out
    assert fake.downloads == [REC["84183"].url]


def test_plan_file_in_missing_directory_is_one_error_line(tmp_path, capsys):
    """Live 2026-10-12: a --plan path in a missing directory crashed with
    ``Error: FileNotFoundError: ...``; live 0.8.0: the error came only after
    the whole check of the source. Now one Error line before any request."""
    plan = tmp_path / "missing" / "plan.json"
    fake = FakeCampaignProvider(C14)
    rc = _run(
        fake,
        tmp_path / "data",
        "--sheet",
        G,
        "--check-updates",
        "--plan",
        str(plan),
    )
    assert rc == 2
    err = without_error_document(capsys.readouterr().err)
    assert err == (
        f"Error: --plan {plan}: katalog {plan.parent} nie istnieje - utworz go "
        "albo podaj inny plik planu\n"
    )
    assert fake.resolve_calls == []  # no index query before the error


def test_plan_file_that_is_a_directory_is_one_error_line(tmp_path, capsys):
    """E2E 0.8.0 P3-8: ``--plan KATALOG`` failed only after the check of the
    source (``IsADirectoryError``)."""
    plan = tmp_path / "plany"
    plan.mkdir()
    fake = FakeCampaignProvider(C14)
    args = ["--sheet", G, "--check-updates", "--plan", str(plan)]
    assert _run(fake, tmp_path / "data", *args) == 2
    assert capsys.readouterr().err.startswith(f"Error: --plan {plan}: to katalog")
    assert fake.resolve_calls == []  # no index query before the error


def test_upgrade_plan_that_runs_nothing_says_so(tmp_path, capsys):
    """E2E 0.8.0 P3-25: a plan of an up-to-date store (and a plan run twice)
    printed nothing at all."""
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    plan, out = tmp_path / "plan.json", tmp_path / "data"
    assert _run(fake, out, "--sheet", G, "-q") == 0  # a local version
    assert _run(fake, out, "--sheet", G, "--check-updates", "--plan", str(plan)) == 0
    capsys.readouterr()
    assert _run(fake, out, "--sheet", G, "--upgrade", "--plan", str(plan)) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"Info: plan {plan}: brak pozycji do wykonania" in captured.err

    fake.records = {"newest": [REC["84183"]]}  # a newer flight: the plan has work
    assert _run(fake, out, "--sheet", G, "--check-updates", "--plan", str(plan)) == 0
    capsys.readouterr()
    assert _run(fake, out, "--sheet", G, "--upgrade", "--plan", str(plan)) == 0
    executed = capsys.readouterr()
    assert "nowa wersja" in executed.out and "brak pozycji" not in executed.err
    assert _run(fake, out, "--sheet", G, "--upgrade", "--plan", str(plan)) == 0
    again = capsys.readouterr()  # done since the plan was made
    assert again.out == "" and "brak pozycji do wykonania" in again.err


def test_upgrade_plan_of_other_store_is_error(tmp_path, capsys):
    fake = FakeCampaignProvider(C14)
    plan = tmp_path / "plan.json"
    _run(fake, tmp_path / "a", "--sheet", G, "--check-updates", "--plan", str(plan))
    capsys.readouterr()
    rc = _run(fake, tmp_path / "b", "--sheet", G, "--upgrade", "--plan", str(plan))
    assert rc == 2
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
CZ_2M_PATH = "nmt/cz_dmr5g_bpv/302/5550/302_5550.tif"
SM5_PATH = "nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif"
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
    return main(
        ["elevation", "download", "--product", "nmt", "--root", str(out), *argv]
    )


def _no_pl_wcs():
    """PL cutout: any PRG/WCS request fails the test."""
    return patch(
        "kartograf.providers.pl.prg.fetch_land_mask",
        side_effect=AssertionError("PRG/WCS nie powinno byc wolane"),
    )


TRACKS = {
    "laz": ("--product", "laz", "--sheet", LAZ_SHEET, "--vertical-crs", "EVRF2007"),
    "cz-sheet": ("--sheet", "302_5550", *CZ_2M),
    "cz-bbox": (
        *CZ_BBOX,
        "--country",
        "cz",
        *CZ_2M,
        "--cutout",
        "--horizontal-crs",
        "EPSG:5514",
    ),
    "pl-cutout": (*PL_BBOX, *PL_1M, "--cutout", "--horizontal-crs", "EPSG:5514"),
    "auto": (*BORDER, *AUTO, "--cutout", "--horizontal-crs", "EPSG:3045"),
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
            "--cutout",
            "--horizontal-crs",
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
    argv = (*BORDER, *AUTO, "--cutout", "--horizontal-crs", "EPSG:3045")
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
    assert out.startswith(f"{CZ_2M_PATH}: lokalna wersja ")
    assert out.rstrip().endswith("(bez sprawdzania; --check-updates)")
    cz.download.assert_called_once()


def test_upgrade_none_signal_info_force(tmp_path, capsys):
    cz = _cz_provider_mock()
    with patch(_CZ_FACTORY_PATCH, return_value=cz):
        _download(tmp_path, "--sheet", "302_5550", *CZ_2M, "-q")
        assert _download(tmp_path, "--sheet", "302_5550", *CZ_2M, "--upgrade") == 0
    captured = capsys.readouterr()
    assert f"{CZ_2M_PATH}: lokalna wersja " in captured.out
    assert "(bez sprawdzania" not in captured.out
    assert "Info: 302_5550: lokalna wersja " in captured.err
    assert "pobierz ponownie: --force" in captured.err
    cz.download.assert_called_once()


def test_sm5_check_failed_exit_code_default_asks_nothing(tmp_path, capsys):
    """A failed check is exit 1; the default download then uses the local
    file without a HEAD (ADR-036 erratum 3) - no warning, the line says it
    was not checked."""
    from kartograf.exceptions import DownloadError

    cz = _cz_provider_mock("5m")
    cz.sheet_index.sm5_sheet.return_value = SimpleNamespace(name="CTES96", podil=1.0)
    sm5 = ("--sheet", "CTES96", "--vertical-crs", "Bpv")
    with patch(_CZ_FACTORY_PATCH, return_value=cz):
        assert _download(tmp_path, *sm5, "-q") == 0
        cz.file_signal.side_effect = DownloadError("HEAD 503")
        capsys.readouterr()
        assert _download(tmp_path, *sm5, "--check-updates") == 11
        assert f"{SM5_PATH}: nie udalo sie sprawdzic: HEAD 503" in (
            capsys.readouterr().out
        )
        heads = cz.file_signal.call_count
        assert _download(tmp_path, *sm5) == 0
    captured = capsys.readouterr()
    assert "Warning:" not in captured.err
    assert captured.out.startswith(f"{SM5_PATH}: lokalna wersja ")
    assert "(bez sprawdzania; --check-updates)" in captured.out
    assert cz.file_signal.call_count == heads
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
    assert run.call_args.kwargs["sheet"] == "302_5550"
    assert run.call_args.kwargs["update"] == update
    assert run.call_args.kwargs["resolution"] == "2m"
