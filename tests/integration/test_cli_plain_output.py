"""``--output-dir`` (``-o``) and ``--root`` through the CLI (ADR-054, DEV-19.1-19.11).

The same fakes answer as in the store tests of each command; what is checked is what a
user sees of a plain write: the files and their names, the status lines, the one error
line and its document, the plan, the options that need a store, the rule of the PL
sheets and the default store.
"""

import errno
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.config import store_root
from kartograf.download import collections
from kartograf.exceptions import DownloadError
from kartograf.marker import STORE_MARKERS
from kartograf.output import STAGING
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from tests.conftest import FakeSoilGrids
from tests.integration.test_collections import AREA, _prg_route, _zip_route
from tests.integration.test_manager_campaigns import (
    C14,
    C14_ALL,
    REC,
    FakeCampaignProvider,
    G,
    asc_for,
    tag,
)
from tests.integration.test_plain_output_products import URL_0208, URL_0224
from tests.support.errors import error_document, without_error_document
from tests.support.fake_packages import FakePackageSession
from tests.support.project_fixtures import pl_sheets

NMT = [
    *("elevation", "download", "--product", "nmt", "--sheet", G),
    *("--resolution", "1m", "--vertical-crs", "EVRF2007"),
]
AREA_ARG = ",".join(str(int(value)) for value in AREA[:4])
SOIL = ["soil", "download", "--property", "clay", "--depth", "0-5cm", "--stat", "mean"]
SOIL_AREA = ["--bbox", "770000,509000,772000,511000"]


def listing(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


def run(capsys, *argv: str | Path) -> tuple[int, str, str]:
    code = main([str(word) for word in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_nmt(capsys, fake, *flags: str | Path) -> tuple[int, str, str]:
    with pl_sheets(fake):
        return run(capsys, *NMT, *flags)


@pytest.fixture
def default_root(monkeypatch, tmp_path) -> Path:
    """The default store lies in the test directory: a plain write must not touch it."""
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default-store"))
    return tmp_path / "default-store"


def test_a_plain_run_writes_the_full_flight_under_its_store_name_and_nothing_else(
    capsys, tmp_path, default_root
):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"

    code, stdout, stderr = run_nmt(capsys, fake, "-o", out)

    assert (code, stderr) == (0, "")
    assert f"{G}.asc: zapisano" in stdout
    full = REC[
        "83233"
    ]  # the newest flight, 84183, is partial: a plain file says nothing
    assert fake.downloads == [full.url]
    assert listing(out) == [f"{G}.asc"]  # no sidecar, no versions/, no staging
    assert (out / f"{G}.asc").read_bytes() == asc_for(G, f"v1 {tag(full)}")
    assert not default_root.exists()


def test_a_second_run_is_one_conflict_before_any_transfer_and_force_replaces(
    capsys, tmp_path
):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"
    run_nmt(capsys, fake, "--output-dir", out)
    target = out / f"{G}.asc"
    target.write_bytes(b"edited")

    code, stdout, stderr = run_nmt(capsys, fake, "--output-dir", out, "--lang", "en")

    assert (code, stdout) == (4, "")
    document = error_document(stderr)
    assert (document["code"], document["exit_code"]) == ("conflict", 4)
    assert document["details"] == {"reason": "output_exists", "paths": [str(target)]}
    assert "--force" in document["hint"]
    assert without_error_document(stderr).startswith("Error: 1 output files exist")
    assert fake.downloads == [REC["83233"].url]  # nothing of the second run was fetched
    assert target.read_bytes() == b"edited"

    code, stdout, stderr = run_nmt(capsys, fake, "-o", out, "--force")

    assert (code, stderr) == (0, "")
    assert f"{G}.asc: zastapiono" in stdout
    assert target.read_bytes() == asc_for(G, f"v1 {tag(REC['83233'])}")
    assert listing(out) == [f"{G}.asc"]  # --force deleted nothing and left no staging


def test_the_plan_says_write_replace_or_conflict_and_is_a_result(capsys, tmp_path):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"

    first = run_nmt(capsys, fake, "-o", out, "--check")
    run_nmt(capsys, fake, "-o", out)
    existing = run_nmt(capsys, fake, "-o", out, "--check")
    forced = run_nmt(capsys, fake, "-o", out, "--check", "--force")

    assert first[0] == existing[0] == forced[0] == 0  # a conflict in a plan is no error
    assert first[1] == f"{G}.asc: do zapisania\n"
    assert existing[1] == f"{G}.asc: konflikt: plik istnieje (zastepuje go --force)\n"
    assert forced[1] == f"{G}.asc: do zastapienia (--force)\n"
    assert fake.downloads == [REC["83233"].url]  # the plans fetched no data
    assert listing(out) == [f"{G}.asc"]


def test_a_sheet_the_index_cannot_tell_fails_the_plan_as_in_the_store(capsys, tmp_path):
    """DEV-19.10: a position whose check failed (the sheet index is unreachable) stays
    ``check_failed`` in a plain plan: a failed result (exit 11) whose line says why,
    as the plan of the store and the run; it is no target with an action."""
    fake = FakeCampaignProvider(C14, errors={G: DownloadError("HTTP 503")})
    out = tmp_path / "out"

    plain = run_nmt(capsys, fake, "-o", out, "--check")
    store = run_nmt(capsys, fake, "--root", tmp_path / "store", "--check")
    code, stdout, _ = run_nmt(capsys, fake, "-o", out, "--check", "--json")
    run_code = run_nmt(capsys, fake, "-o", out)[0]

    assert (plain[0], store[0], code, run_code) == (11, 11, 11, 11)
    assert plain[1] == f"{G}.asc: nie udalo sie sprawdzic: HTTP 503\n"
    assert store[1].endswith(f"/{G}.asc: nie udalo sie sprawdzic: HTTP 503\n")
    envelope = json.loads(stdout)
    (item,) = envelope["result"]["items"]
    assert (item["status"], item["error"]) == ("check_failed", "HTTP 503")
    assert (item["action"], item["path"], item["reason"]) == (None, None, None)
    assert envelope["result"]["ok"] is False
    assert [(i["status"], i["code"], i["reason"]) for i in envelope["items"]] == [
        ("failed", "source_unavailable", "check_failed")
    ]
    assert fake.downloads == [] and not out.exists()


def test_the_json_of_a_plain_run_lists_files_and_says_where_it_wrote(capsys, tmp_path):
    out = tmp_path / "out"

    code, stdout, _ = run_nmt(capsys, FakeCampaignProvider(C14), "-o", out, "--json")

    assert code == 0
    document = json.loads(stdout)
    report = document["result"]
    assert (report["mode"], report["root"], report["output_dir"]) == (
        "plain",
        None,
        str(out),
    )
    (entry,) = report["files"]
    body = (out / f"{G}.asc").read_bytes()
    assert entry == {
        "unit": G,
        "country": "PL",
        "path": str(out / f"{G}.asc"),
        "size_bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "status": "written",
    }
    assert [(i["id"], i["status"]) for i in document["items"]] == [(G, "ok")]


@pytest.mark.parametrize(
    ("flags", "reason", "option"),
    [
        (["--root", "STORE"], "exclusive_options", "root"),
        (["--upgrade"], "store_only_option", "--upgrade"),
        (["--check", "--plan", "PLAN"], "store_only_option", "--plan"),
        (["--all-campaigns"], "store_only_option", "--all-campaigns"),
    ],
    ids=["root", "upgrade", "plan", "all-campaigns"],
)
def test_what_needs_a_store_is_refused_with_output_dir_naming_root(
    capsys, tmp_path, flags, reason, option
):
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"
    flags = [str(tmp_path / word.lower()) if word.isupper() else word for word in flags]

    code, stdout, stderr = run_nmt(capsys, fake, "-o", out, *flags)

    assert (code, stdout) == (2, "")
    document = error_document(stderr)
    assert document["code"] == "validation_error"
    assert (document["details"]["reason"], document["details"]["option"]) == (
        reason,
        option,
    )
    assert "--root" in document["hint"]
    assert fake.downloads == [] and not out.exists()


@pytest.mark.parametrize("marker", sorted(STORE_MARKERS))
def test_an_output_dir_inside_a_store_of_any_tool_is_a_conflict_naming_root(
    capsys, tmp_path, marker
):
    store = tmp_path / "store"
    store.mkdir()
    (store / marker).write_text("{}", encoding="utf-8")
    fake = FakeCampaignProvider(C14)

    code, _, stderr = run_nmt(capsys, fake, "-o", store / "sub")

    assert code == 4
    document = error_document(stderr)
    assert (document["code"], document["details"]["reason"]) == (
        "conflict",
        "output_in_store",
    )
    assert "--root" in document["hint"]
    assert fake.downloads == [] and listing(store) == [marker]


def test_without_a_target_the_default_store_is_written_and_root_names_another(
    capsys, tmp_path, default_root
):
    fake = FakeCampaignProvider(C14)

    code, stdout, _ = run_nmt(capsys, fake)

    assert code == 0
    assert store_root().root == default_root
    assert default_root.joinpath("kartograf-store.json").is_file()
    assert sorted(p.name for p in default_root.rglob("*.asc")) == [f"{G}.asc"] * 2
    assert "nowa wersja" in stdout and "zapisano" not in stdout
    default_files = listing(default_root)
    other = tmp_path / "other"

    code, _, _ = run_nmt(capsys, fake, "--root", other)

    assert code == 0 and other.joinpath("kartograf-store.json").is_file()
    assert listing(default_root) == default_files  # the default store is untouched


def test_a_sheet_without_a_full_flight_is_skipped_loudly_and_all_skipped_is_no_data(
    capsys, tmp_path
):
    partial = {
        "all": [replace(r, full_sheet=False) for r in C14_ALL],
        "newest": [replace(r, full_sheet=False) for r in C14["newest"]],
    }
    out = tmp_path / "out"

    code, stdout, stderr = run_nmt(
        capsys, FakeCampaignProvider(partial), "-o", out, "--json"
    )

    assert code == 11  # a failed result, as for a request without coverage
    document = json.loads(stdout)
    assert document["status"] == "failed"
    (skipped,) = document["result"]["skipped"]
    assert (skipped["id"], skipped["reason"]) == (G, "skipped_incomplete")
    assert "--root" in skipped["message"]
    (item,) = document["items"]
    assert (item["code"], item["reason"]) == ("no_data", "skipped_incomplete")
    assert [n["code"] for n in document["notices"]] == ["skipped_incomplete"]
    assert not out.exists() and stderr == ""


def test_a_plain_soil_layer_and_hsg_raster_are_single_files_named_as_in_the_store(
    capsys, tmp_path
):
    out = tmp_path / "out"
    fake = FakeSoilGrids("2.0")

    with patch("kartograf.transport.http.SessionPerThread.get", return_value=fake):
        code, stdout, _ = run(capsys, *SOIL, *SOIL_AREA, "-o", out)

    assert code == 0
    coords = "770000_509000_772000_511000"
    assert listing(out) == [f"{coords}.tif"]
    assert f"{coords}.tif: zapisano" in stdout
    assert fake.capabilities == 0  # a plain file has no edition label to ask for

    with patch("kartograf.transport.http.SessionPerThread.get", return_value=fake):
        code, _, stderr = run(capsys, *SOIL, *SOIL_AREA, "-o", out)
    assert code == 4
    assert error_document(stderr)["details"]["paths"] == [str(out / f"{coords}.tif")]


def test_a_plain_collection_is_one_file_per_unit_and_a_rerun_names_them_all(
    capsys, tmp_path, monkeypatch, frozen_clock
):
    session = FakePackageSession({})
    session.routes.update([_prg_route(), _zip_route(URL_0208), _zip_route(URL_0224)])
    monkeypatch.setattr(collections, "_session", lambda: session)
    out = tmp_path / "out"
    request = [
        *("models3d", "download", "--product", "buildings", "--lod", "1"),
        *("--year", "2024", "--country", "pl", "--bbox", AREA_ARG),
        *("--bbox-crs", "EPSG:2180"),
    ]

    code, stdout, _ = run(capsys, *request, "-o", out)

    assert code == 0
    assert listing(out) == ["0208.zip", "0224.zip"]
    assert "0208.zip: zapisano" in stdout and "0224.zip: zapisano" in stdout
    assert f"Zapisane: 2, zastapione: 0, bledy: 0 ({out})" in stdout

    code, _, stderr = run(capsys, *request, "-o", out)

    assert code == 4
    assert error_document(stderr)["details"]["paths"] == [
        str(out / "0208.zip"),
        str(out / "0224.zip"),
    ]
    code, stdout, _ = run(capsys, *request, "-o", out, "--force")
    assert code == 0
    assert f"Zapisane: 0, zastapione: 2, bledy: 0 ({out})" in stdout


def test_a_plain_land_cover_package_is_one_file_and_the_plan_says_write(
    capsys, tmp_path
):
    def package(code, output_path, **kwargs):
        output_path.write_bytes(b"gpkg")
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    out = tmp_path / "out"
    request = ["landcover", "download", "--product", "bdot10k", "--teryt", "1465"]

    with patch.object(Bdot10kProvider, "download_package", side_effect=package) as get:
        planned = run(capsys, *request, "-o", out, "--check")
        written = run(capsys, *request, "-o", out)
        refused = run(capsys, *request, "-o", out)

    assert planned[:2] == (0, "1465.gpkg: do zapisania\n")
    assert written[:2] == (0, "1465.gpkg: zapisano\n")
    assert refused[0] == 4 and get.call_count == 1
    assert listing(out) == ["1465.gpkg"]
    assert not out.joinpath(STAGING).exists()


def test_a_project_takes_no_output_dir_and_says_so(capsys, tmp_path, default_root):
    project = tmp_path / "project"
    project.mkdir()
    assert run(capsys, "project", "init", "--project", project)[0] == 0

    code, _, stderr = run(
        capsys,
        *("project", "add", "--project", project, "area"),
        *NMT,
        *("-o", tmp_path / "out"),
    )

    assert code == 2
    document = error_document(stderr)
    assert (document["details"]["reason"], document["details"]["option"]) == (
        "store_only_option",
        "--output-dir",
    )
    assert "--root" in document["hint"]
    manifest = json.loads((project / "kartograf-project.json").read_text())
    assert manifest["tasks"] == []


def test_a_plain_write_needs_no_link_of_any_kind(capsys, tmp_path, monkeypatch):
    """FAT, exFAT and SMB give no hard link and often no symlink (DEV-19.8)."""

    def denied(*args, **kwargs):
        raise OSError(errno.EPERM, "no links on this file system")

    monkeypatch.setattr(os, "link", denied)
    monkeypatch.setattr(os, "symlink", denied)
    fake = FakeCampaignProvider(C14)
    out = tmp_path / "out"

    first = run_nmt(capsys, fake, "-o", out)
    forced = run_nmt(capsys, fake, "-o", out, "--force")

    assert (first[0], first[2]) == (0, "") and f"{G}.asc: zapisano" in first[1]
    assert (forced[0], forced[2]) == (0, "") and f"{G}.asc: zastapiono" in forced[1]
    assert os.stat(out / f"{G}.asc").st_nlink == 1
    assert listing(out) == [f"{G}.asc"]
