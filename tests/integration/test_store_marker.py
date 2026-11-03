"""The writers and the commands meet the store marker (ADR-054)."""

import json

import pytest

from kartograf import StoreUnavailableError, init_store, list_segments
from kartograf.cli import main
from kartograf.download.manager import DownloadManager
from kartograf.marker import MARKER
from kartograf.testing import build_fixture_store
from tests.integration.test_manager_campaigns import G, c14_fake
from tests.support.errors import error_document


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def seed_unmarked_store(root):
    """The layout of a store of 0.8.0-dev: one version, no marker."""
    version = root / "nmt" / "pl_1992_1m_evrf2007" / "versions" / "N-34" / "v"
    version.mkdir(parents=True)
    (version / "a.asc").write_text("data")
    (version / "a.asc.meta.json").write_text(json.dumps({"schema": "kartograf-meta/1"}))


def test_a_download_into_a_new_root_marks_it(tmp_path):
    root = tmp_path / "store"

    result = DownloadManager(provider=c14_fake(), root=root).download_sheet(G)

    assert result.succeeded
    assert json.loads((root / MARKER).read_text())["tool"] == "kartograf"
    assert list_segments(root)  # the marker is no segment


def test_an_unmarked_store_refuses_a_download_before_the_first_byte(tmp_path):
    seed_unmarked_store(tmp_path)
    fake = c14_fake()

    with pytest.raises(StoreUnavailableError) as caught:
        DownloadManager(provider=fake, root=tmp_path).download_sheet(G)

    assert caught.value.reason == "no_marker"
    assert fake.downloads == []
    assert not (tmp_path / MARKER).exists()

    init_store(tmp_path)
    assert DownloadManager(provider=fake, root=tmp_path).download_sheet(G).succeeded


def test_the_plan_of_an_unmarked_store_fails_the_same_way_and_writes_nothing(tmp_path):
    seed_unmarked_store(tmp_path)
    before = sorted(tmp_path.rglob("*"))

    with pytest.raises(StoreUnavailableError):
        DownloadManager(provider=c14_fake(), root=tmp_path).check_sheets([G])

    assert sorted(tmp_path.rglob("*")) == before


def test_the_plan_of_a_new_root_creates_nothing(tmp_path):
    root = tmp_path / "store"

    plan = DownloadManager(provider=c14_fake(), root=root).check_sheets([G])

    assert plan.items
    assert not root.exists()


def test_the_fixture_store_has_its_marker(tmp_path):
    store = build_fixture_store(tmp_path / "data")

    assert (store.root / MARKER).is_file()
    assert init_store(store.root).created is False


def test_store_init_marks_the_store_and_says_so(capsys, tmp_path):
    root = tmp_path / "store"

    code, out, err = run(capsys, "store", "init", "--root", str(root), "--lang", "en")
    assert (code, err) == (0, "")
    assert str(root / MARKER) in out and "Wrote" in out

    code, out, err = run(capsys, "store", "init", "--root", str(root), "--json")
    result = json.loads(out)["result"]
    assert (code, err) == (0, "")
    assert (result["schema"], result["created"], result["tool"]) == (
        "kartograf-store-init/1",
        False,
        "kartograf",
    )
    assert result["root"] == str(root)


def test_store_init_reports_what_is_wrong_with_the_root(capsys, tmp_path):
    (tmp_path / "notes.txt").write_text("mine")

    code, out, err = run(capsys, "store", "init", "--root", str(tmp_path), "--json")

    document = error_document(err)
    assert (code, out) == (4, "")
    assert (document["code"], document["details"]["reason"]) == (
        "conflict",
        "not_empty",
    )
    assert document["command"] == "store init"
