"""The marker of a store, ``kartograf-store.json`` (DEV-19.12 to DEV-19.14, ADR-054)."""

import errno
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kartograf import (
    ConflictError,
    InvalidLayoutError,
    StoreUnavailableError,
    ValidationError,
    error_report,
    init_store,
)
from kartograf.marker import (
    MARKER,
    MARKER_SCHEMA,
    has_layout,
    lenient_store,
    managed_trees,
    prepare_store,
    store_around,
    store_below,
)

SEGMENT = Path("nmt") / "pl_1992_1m_evrf2007"


def marker_of(root: Path) -> dict[str, str]:
    return json.loads((root / MARKER).read_text(encoding="utf-8"))


def seed_layout(root: Path, *, schema: str = "kartograf-meta/1") -> Path:
    """A store of 0.8.0-dev: a version with its sidecar and no marker."""
    version = root / SEGMENT / "versions" / "N-34" / "2022-05-10_ab12cd34"
    version.mkdir(parents=True)
    (version / "a.asc").write_text("data")
    (version / "a.asc.meta.json").write_text(json.dumps({"schema": schema}))
    return version


# -- the marker ----------------------------------------------------------------


def test_the_first_write_marks_a_new_root_with_the_four_fields(tmp_path):
    root = tmp_path / "a" / "store"

    assert prepare_store(root) == root
    marker = marker_of(root)

    assert set(marker) == {"schema", "tool", "created_at", "producer_version"}
    assert (marker["schema"], marker["tool"]) == (MARKER_SCHEMA, "kartograf")
    assert datetime.fromisoformat(marker["created_at"]).utcoffset() is not None
    assert marker["producer_version"]


def test_a_marked_root_keeps_its_marker_on_every_later_write(tmp_path):
    prepare_store(tmp_path)
    before = (tmp_path / MARKER).read_bytes()

    prepare_store(tmp_path)

    assert (tmp_path / MARKER).read_bytes() == before


def test_an_empty_directory_is_marked_and_a_root_with_other_files_is_refused(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    prepare_store(empty)
    assert (empty / MARKER).is_file()

    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("mine")
    with pytest.raises(ConflictError) as caught:
        prepare_store(other)

    assert (caught.value.reason, caught.value.exit_code) == ("not_empty", 4)
    assert sorted(path.name for path in other.iterdir()) == ["notes.txt"]


def test_racing_first_writes_leave_one_whole_marker(tmp_path):
    root = tmp_path / "store"

    with ThreadPoolExecutor(8) as pool:
        for future in [pool.submit(prepare_store, root) for _ in range(16)]:
            future.result()

    assert marker_of(root)["schema"] == MARKER_SCHEMA
    assert [path.name for path in root.iterdir()] == [MARKER]


def test_a_file_system_without_hard_links_gets_its_marker_too(tmp_path, monkeypatch):
    def no_link(*args, **kwargs):
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(os, "link", no_link)

    prepare_store(tmp_path / "fat")

    assert marker_of(tmp_path / "fat")["schema"] == MARKER_SCHEMA
    assert [path.name for path in (tmp_path / "fat").iterdir()] == [MARKER]


# -- a layout without a marker ----------------------------------------------------


@pytest.mark.parametrize("check", [prepare_store, lenient_store])
def test_the_layout_of_a_store_without_a_marker_is_store_unavailable(tmp_path, check):
    seed_layout(tmp_path)

    with pytest.raises(StoreUnavailableError) as caught:
        check(tmp_path)

    error = caught.value
    assert (error.reason, error.exit_code) == ("no_marker", 8)
    assert f"kartograf store init --root {tmp_path}" in (error.hint or "")
    assert not (tmp_path / MARKER).exists()
    assert error_report(error).details == {"reason": "no_marker", "path": str(tmp_path)}


def test_the_files_of_version_0_7_are_a_layout_too(tmp_path):
    (tmp_path / SEGMENT / "kampanie").mkdir(parents=True)
    assert not has_layout(tmp_path)  # directories without a file are no store

    (tmp_path / SEGMENT / "kampanie" / "2022").write_text("old")
    (tmp_path / "laz").mkdir()
    (tmp_path / "laz" / "plain.laz").write_text("old")

    assert has_layout(tmp_path)
    with pytest.raises(StoreUnavailableError):
        prepare_store(tmp_path)


def test_the_directories_and_staging_of_a_first_write_are_no_content(tmp_path):
    # a writer makes the directories of its first file before it asks for the marker
    (tmp_path / SEGMENT / "versions" / ".incoming" / "token").mkdir(parents=True)
    (tmp_path / SEGMENT / "versions" / ".incoming" / "token" / "half.asc").write_text(
        "x"
    )

    # also under a product directory that Kartograf does not register (a custom storage)
    custom = tmp_path / "custom" / "v" / "versions" / ".incoming" / "token"
    custom.mkdir(parents=True)
    (custom / "half.asc").write_text("x")

    assert not has_layout(tmp_path)
    prepare_store(tmp_path)
    assert (tmp_path / MARKER).is_file()


def test_a_plan_creates_nothing_in_a_missing_or_empty_root(tmp_path):
    assert lenient_store(tmp_path / "missing") == tmp_path / "missing"
    assert not (tmp_path / "missing").exists()

    (tmp_path / "empty").mkdir()
    lenient_store(tmp_path / "empty")
    assert list((tmp_path / "empty").iterdir()) == []


def test_a_plan_refuses_a_root_that_a_write_would_refuse(tmp_path):
    (tmp_path / "notes.txt").write_text("mine")

    with pytest.raises(ConflictError) as caught:
        lenient_store(tmp_path)

    assert caught.value.reason == "not_empty"


# -- a store never nests -------------------------------------------------------------


@pytest.mark.parametrize("name", ["kartograf-store.json", "imgw-store.json"])
def test_a_root_inside_a_store_of_any_tool_is_refused(tmp_path, name):
    (tmp_path / name).write_text("{}")

    with pytest.raises(ConflictError) as caught:
        prepare_store(tmp_path / "inner" / "store")

    assert caught.value.reason == "nested_store"
    assert not (tmp_path / "inner").exists()


def test_a_root_that_holds_the_marker_of_another_tool_is_refused(tmp_path):
    (tmp_path / "imgw-store.json").write_text("{}")

    for check in (prepare_store, lenient_store, init_store):
        with pytest.raises(ConflictError) as caught:
            check(tmp_path)
        assert caught.value.reason == "nested_store"


def test_a_store_below_the_root_is_refused_but_the_product_trees_are_not_entered(
    tmp_path,
):
    below = tmp_path / "work" / "imgw"
    below.mkdir(parents=True)
    (below / "imgw-store.json").write_text("{}")
    with pytest.raises(ConflictError) as caught:
        prepare_store(tmp_path)
    assert caught.value.reason == "nested_store"

    store = tmp_path / "ours"
    prepare_store(store)
    hidden = store / "nmt" / "x"
    hidden.mkdir(parents=True)
    (hidden / "imgw-store.json").write_text("{}")  # inside a managed product tree
    prepare_store(store)  # not looked into


def test_store_around_and_below_find_a_marker_by_its_file_name(tmp_path):
    prepare_store(tmp_path / "s")
    inner = tmp_path / "s" / "nmt" / "a" / "b"
    inner.mkdir(parents=True)
    (tmp_path / "t").mkdir()

    assert store_around(inner) == (tmp_path / "s").resolve()
    assert store_around(tmp_path / "s") == (tmp_path / "s").resolve()
    assert store_around(tmp_path / "t") is None
    assert store_below(tmp_path) == tmp_path / "s"
    assert store_below(tmp_path, skip=frozenset({"s"})) is None


def test_the_managed_trees_are_the_product_directories_and_hsg():
    trees = managed_trees()

    assert {"nmt", "nmpt", "orto", "laz", "boundaries", "landcover", "soil", "hsg"} <= (
        trees
    )


# -- store init ----------------------------------------------------------------------


def test_init_writes_the_marker_once(tmp_path):
    first = init_store(tmp_path / "store", created_at=datetime(2026, 1, 2, tzinfo=UTC))
    again = init_store(tmp_path / "store")

    assert (first.created, again.created) == (True, False)
    assert first.created_at == again.created_at == "2026-01-02T00:00:00+00:00"
    assert first.marker == tmp_path / "store" / MARKER
    assert again.producer_version == first.producer_version != ""


def test_init_without_a_root_marks_the_default_store(monkeypatch, tmp_path):
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default"))

    assert init_store().root == tmp_path / "default"
    assert (tmp_path / "default" / MARKER).is_file()


def test_init_needs_a_time_zone_and_writes_nothing_without_one(tmp_path):
    with pytest.raises(ValidationError) as caught:
        init_store(tmp_path / "store", created_at=datetime(2026, 1, 2))

    assert caught.value.option == "created_at"
    assert not (tmp_path / "store").exists()


def test_init_marks_a_verified_layout_and_touches_no_file(tmp_path):
    version = seed_layout(tmp_path)
    before = sorted(str(path) for path in tmp_path.rglob("*"))

    result = init_store(tmp_path)

    assert result.created is True
    assert sorted(str(path) for path in tmp_path.rglob("*")) == sorted(
        [*before, str(tmp_path / MARKER)]
    )
    assert (version / "a.asc").read_text() == "data"
    prepare_store(tmp_path)  # a write is possible now


def test_init_lists_every_problem_of_a_layout_that_is_not_a_store(tmp_path):
    seed_layout(tmp_path, schema="imgw-meta/1")
    (tmp_path / "notes.txt").write_text("mine")

    with pytest.raises(InvalidLayoutError) as caught:
        init_store(tmp_path)

    error = caught.value
    assert (error.reason, error.exit_code) == ("invalid_layout", 7)
    assert len(error.problems or ()) == 2
    assert any("notes.txt" in problem for problem in error.problems or ())
    assert any(".meta.json" in problem for problem in error.problems or ())
    assert not (tmp_path / MARKER).exists()


def test_init_refuses_a_directory_with_other_files_and_no_layout(tmp_path):
    (tmp_path / "notes.txt").write_text("mine")

    with pytest.raises(ConflictError) as caught:
        init_store(tmp_path)

    assert caught.value.reason == "not_empty"


def test_a_marker_that_is_not_a_store_document_is_invalid_layout(tmp_path):
    (tmp_path / MARKER).write_text("{not json")

    for check in (prepare_store, lenient_store, init_store):
        with pytest.raises(InvalidLayoutError):
            check(tmp_path)

    (tmp_path / MARKER).write_text(json.dumps({"schema": "kartograf-store/2"}))
    with pytest.raises(InvalidLayoutError):
        prepare_store(tmp_path)
