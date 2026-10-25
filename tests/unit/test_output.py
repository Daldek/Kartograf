"""Plain output: the target list and the staging directory (DEV-19.6, 19.7, 19.11)."""

import errno
import hashlib
import os
import signal
import threading
import time

import pytest

from kartograf.download.plan import PlanItem, new_plan, plain_items
from kartograf.exceptions import ConflictError, ValidationError
from kartograf.interrupt import Terminated
from kartograf.marker import STORE_MARKERS, store_below
from kartograf.output import (
    STAGING,
    Staging,
    digest_of,
    plain_of,
    plan_plain,
    preflight,
    refuse,
    resolve_target,
    writing,
)


def states(entries):
    return [(entry.path.name, entry.action, entry.reason) for entry in entries]


# --------------------------------------------------------------------------
# What a call writes: the directory, the store, the default store (DEV-19.1, DEV-19.2)
# --------------------------------------------------------------------------


def test_a_directory_is_plain_a_root_is_the_store_and_neither_is_the_default_store(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default"))

    plain = resolve_target(output_dir=tmp_path / "files")
    store = resolve_target(root=tmp_path / "store")
    default = resolve_target()

    assert (plain.mode, plain.path) == ("plain", tmp_path / "files")
    assert (store.mode, store.path) == ("store", tmp_path / "store")
    assert (default.mode, default.path) == ("store", tmp_path / "default")


def test_both_targets_are_a_validation_error_naming_the_pair(tmp_path):
    with pytest.raises(ValidationError) as error:
        resolve_target(output_dir=tmp_path / "a", root=tmp_path / "b")

    assert error.value.reason == "exclusive_options"
    assert error.value.details() == {
        "reason": "exclusive_options",
        "option": "root",
        "options": ["output_dir", "root"],
    }


def test_an_empty_directory_is_not_the_current_one(tmp_path):
    with pytest.raises(ValidationError) as error:
        resolve_target(output_dir="")

    assert error.value.option == "output_dir"


# --------------------------------------------------------------------------
# The target list (DEV-19.6, DEV-19.9)
# --------------------------------------------------------------------------


def test_an_existing_target_is_replaced_only_with_force_and_nothing_is_written(
    tmp_path,
):
    (tmp_path / "a.asc").write_bytes(b"old")
    names = ["a.asc", "sub/b.asc"]

    assert states(plan_plain(tmp_path, names, force=False)) == [
        ("a.asc", "conflict", "output_exists"),
        ("b.asc", "write", None),
    ]
    assert states(plan_plain(tmp_path, names, force=True)) == [
        ("a.asc", "replace", None),
        ("b.asc", "write", None),
    ]
    assert (tmp_path / "a.asc").read_bytes() == b"old"
    assert not (tmp_path / "sub").exists()


def test_duplicate_names_are_conflicts_even_with_force(tmp_path):
    entries = plan_plain(tmp_path, ["x/a.asc", "x/a.asc", "b.asc"], force=True)

    assert states(entries) == [
        ("a.asc", "conflict", "duplicate_output_name"),
        ("a.asc", "conflict", "duplicate_output_name"),
        ("b.asc", "write", None),
    ]


def test_refuse_lists_every_offending_path_under_the_first_reason(tmp_path):
    (tmp_path / "a.asc").write_bytes(b"1")
    (tmp_path / "b.asc").write_bytes(b"2")
    entries = plan_plain(tmp_path, ["a.asc", "b.asc", "c.asc", "c.asc"], force=False)

    with pytest.raises(ConflictError) as error:
        refuse(entries)

    assert error.value.code == "conflict"
    assert error.value.reason == "duplicate_output_name"
    assert error.value.paths == tuple(
        str(tmp_path / name) for name in ("a.asc", "b.asc", "c.asc", "c.asc")
    )


def test_existing_targets_alone_are_output_exists_and_the_hint_names_force(tmp_path):
    for name in ("a.asc", "b.asc"):
        (tmp_path / name).write_bytes(b"1")

    with pytest.raises(ConflictError) as error:
        refuse(plan_plain(tmp_path, ["a.asc", "b.asc", "c.asc"], force=False))

    assert error.value.reason == "output_exists"
    assert error.value.paths == (str(tmp_path / "a.asc"), str(tmp_path / "b.asc"))
    assert error.value.hint is not None and "--force" in error.value.hint


def test_a_plan_without_conflicts_passes(tmp_path):
    refuse(plan_plain(tmp_path, ["a.asc", "sub/b.asc"], force=False))


# --------------------------------------------------------------------------
# A store is no output directory (DEV-19.11)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("marker", STORE_MARKERS)
def test_a_directory_that_is_or_lies_in_a_store_of_any_tool_is_refused(
    tmp_path, marker
):
    (tmp_path / "store" / "deep").mkdir(parents=True)
    (tmp_path / "store" / marker).write_text("{}")

    for directory in (tmp_path / "store", tmp_path / "store" / "deep" / "er"):
        entries = plan_plain(directory, ["a.asc"], force=True)
        assert states(entries) == [("a.asc", "conflict", "output_in_store")]
        with pytest.raises(ConflictError) as error:
            refuse(entries)
        assert error.value.reason == "output_in_store"
        assert error.value.hint is not None and "--root" in error.value.hint


def test_a_subdirectory_the_write_would_enter_must_not_hold_a_marker(tmp_path):
    (tmp_path / "out" / "inner").mkdir(parents=True)
    (tmp_path / "out" / "inner" / "imgw-store.json").write_text("{}")

    entering = plan_plain(tmp_path / "out", ["inner/x.asc"], force=False)
    beside = plan_plain(tmp_path / "out", ["other/x.asc"], force=False)

    assert states(entering) == [("x.asc", "conflict", "output_in_store")]
    assert states(beside) == [("x.asc", "write", None)]


def test_a_directory_with_a_store_elsewhere_below_it_is_a_fine_output(tmp_path):
    # <data_dir> holds the default store <data_dir>/kartograf; writing files to
    # <data_dir> is not writing into that store.
    (tmp_path / "kartograf").mkdir()
    (tmp_path / "kartograf" / "kartograf-store.json").write_text("{}")

    assert states(plan_plain(tmp_path, ["a.asc"], force=False)) == [
        ("a.asc", "write", None)
    ]
    assert store_below(tmp_path) == tmp_path / "kartograf"


# --------------------------------------------------------------------------
# The staging directory (DEV-19.7, DEV-19.8)
# --------------------------------------------------------------------------


def stage(staging, name, content):
    path = staging.stage_path(name)
    path.write_bytes(content)
    return path


def test_a_staged_file_is_read_once_and_moved_into_place(tmp_path):
    out = tmp_path / "out"

    with Staging(out) as staging:
        host, pid, token = staging.path.name.rsplit("_", 2)
        assert pid == str(os.getpid()) and token
        assert staging.path.parent == out / STAGING
        staged = stage(staging, "f.bin", b"abcd")
        assert staged.name == "f.bin" and staged.is_relative_to(staging.path)
        result = staging.commit(staged, out / "sub" / "f.bin")

    assert (result.status, result.size_bytes) == ("written", 4)
    assert result.sha256 == hashlib.sha256(b"abcd").hexdigest()
    assert (out / "sub" / "f.bin").read_bytes() == b"abcd"
    assert not (out / STAGING).exists()
    assert sorted(path.name for path in out.iterdir()) == ["sub"]  # only data files


def test_digest_of_reads_a_file_of_many_chunks(tmp_path):
    body = b"0123456789" * 300_000  # a few chunks of 1 MiB
    (tmp_path / "big.bin").write_bytes(body)

    assert digest_of(tmp_path / "big.bin") == (
        len(body),
        hashlib.sha256(body).hexdigest(),
    )


def test_an_existing_target_is_replaced_atomically_only_with_force(tmp_path):
    (tmp_path / "f.bin").write_bytes(b"old")

    with Staging(tmp_path, force=True) as staging:
        result = staging.commit(stage(staging, "f.bin", b"new"), tmp_path / "f.bin")

    assert result.status == "replaced"
    assert (tmp_path / "f.bin").read_bytes() == b"new"


def test_a_target_that_appeared_after_the_plan_is_not_replaced_without_force(tmp_path):
    with Staging(tmp_path) as staging:
        staged = stage(staging, "f.bin", b"new")
        (tmp_path / "f.bin").write_bytes(b"somebody else's")

        with pytest.raises(ConflictError) as error:
            staging.commit(staged, tmp_path / "f.bin")

    assert error.value.reason == "output_exists"
    assert (tmp_path / "f.bin").read_bytes() == b"somebody else's"
    assert not (tmp_path / STAGING).exists()


def test_the_staging_directory_goes_when_the_block_fails_and_the_target_stays(tmp_path):
    (tmp_path / "f.bin").write_bytes(b"old")

    with pytest.raises(RuntimeError), Staging(tmp_path, force=True) as staging:
        stage(staging, "f.bin", b"half")
        raise RuntimeError("transfer failed")

    assert not (tmp_path / STAGING).exists()
    assert (tmp_path / "f.bin").read_bytes() == b"old"


def test_discard_removes_the_directory_of_one_download_and_nothing_else(tmp_path):
    with Staging(tmp_path) as staging:
        kept = stage(staging, "kept.bin", b"1")
        failed = stage(staging, "failed.bin", b"2")

        staging.discard(failed)
        staging.discard(tmp_path / "not-staged.bin")  # no effect outside the staging

        assert not failed.parent.exists() and kept.exists()


def test_sigint_and_sigterm_remove_the_staging_directory(tmp_path):
    out = tmp_path / "out"
    before = signal.getsignal(signal.SIGTERM)

    with pytest.raises(KeyboardInterrupt), Staging(out) as staging:
        stage(staging, "f.bin", b"x")
        signal.raise_signal(signal.SIGINT)
    assert not (out / STAGING).exists()

    with pytest.raises(Terminated), Staging(out) as staging:
        stage(staging, "f.bin", b"x")
        signal.raise_signal(signal.SIGTERM)
    assert not (out / STAGING).exists()
    assert signal.getsignal(signal.SIGTERM) == before  # the handler is put back


def test_leftovers_older_than_24_hours_are_removed_by_the_next_run(tmp_path):
    out = tmp_path / "out"
    old, fresh = out / STAGING / "host_1_dead", out / STAGING / "host_2_live"
    for leftover in (old, fresh):
        leftover.mkdir(parents=True)
        (leftover / "000001").write_bytes(b"x")
    stale = time.time() - 25 * 60 * 60
    os.utime(old, (stale, stale))

    with Staging(out) as staging:
        stage(staging, "f.bin", b"x")  # the first transfer opens the staging directory
        assert not old.exists()
        assert fresh.exists()  # the directory of a run that may be alive stays
    assert fresh.exists()


def test_threads_of_one_run_stage_in_separate_directories(tmp_path):
    with Staging(tmp_path) as staging:
        paths = []
        threads = [
            threading.Thread(
                target=lambda: paths.append(stage(staging, "same.bin", b"x"))
            )
            for _ in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len({path.parent for path in paths}) == 8


def test_plain_output_needs_no_hard_links(tmp_path, monkeypatch):
    # FAT, exFAT and SMB cannot link: the store fails there, plain output must not.
    def no_link(*args, **kwargs):
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(os, "link", no_link)

    with Staging(tmp_path) as staging:
        result = staging.commit(
            stage(staging, "f.bin", b"data"), tmp_path / "a" / "f.bin"
        )

    assert result.status == "written"
    assert (tmp_path / "a" / "f.bin").read_bytes() == b"data"


# --------------------------------------------------------------------------
# The write of a request: the handle root, the lazy directory, the store-only options
# --------------------------------------------------------------------------


def test_nothing_is_created_before_the_first_transfer(tmp_path):
    out = tmp_path / "new" / "out"

    with Staging(out) as staging:
        assert staging.plan(["a.asc"])[0].action == "write"

    assert not (
        tmp_path / "new"
    ).exists()  # a refused or invalid request leaves no trace


def test_the_handle_root_names_the_open_write_and_no_store(tmp_path):
    with Staging(tmp_path / "out") as staging:
        assert plain_of(staging.handle) is staging
        assert plain_of(staging.handle / "nmt" / "versions") is staging
        assert plain_of(tmp_path / "store") is None
        assert plain_of(None) is None
    assert plain_of(staging.handle) is None  # forgotten when the write ends


def test_the_handle_is_found_through_a_symbolic_link(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)

    with Staging(tmp_path / "link" / "out") as staging:
        assert plain_of(staging.handle.resolve()) is staging
        assert plain_of(staging.handle) is staging


def test_writing_gives_the_store_root_or_the_handle_of_a_plain_write(tmp_path):
    with writing(root=tmp_path / "store") as root:
        assert root == tmp_path / "store"
        assert plain_of(root) is None

    with writing(output_dir=tmp_path / "out") as handle:
        write = plain_of(handle)
        assert write is not None and write.directory == tmp_path / "out"
        with writing(root=handle) as same:  # a track inside the write joins it
            assert same == handle
        assert plain_of(handle) is write

    assert not (tmp_path / "out").exists()


def open_write(handle) -> Staging:
    write = plain_of(handle)
    assert write is not None
    return write


def test_force_lets_the_write_replace_and_an_update_that_needs_versions_is_refused(
    tmp_path,
):
    with writing(output_dir=tmp_path, update="force") as handle:
        assert open_write(handle).force is True
    with writing(output_dir=tmp_path, force=True) as handle:
        assert open_write(handle).force is True
    with writing(output_dir=tmp_path) as handle:
        assert open_write(handle).force is False

    for options, flag in (
        ({"update": "upgrade"}, "--upgrade"),
        ({"plan": object()}, "--plan"),
        ({"all_campaigns": True}, "--all-campaigns"),
    ):
        with (
            pytest.raises(ValidationError) as error,
            writing(output_dir=tmp_path, **options),
        ):
            raise AssertionError("not reached")
        assert error.value.details() == {
            "reason": "store_only_option",
            "option": flag,
        }
        assert "--root" in str(error.value.hint)
    # the same options are fine with the store
    with writing(root=tmp_path / "store", update="upgrade", all_campaigns=True):
        pass


def test_preflight_lists_every_path_of_a_plain_write_and_ignores_a_store(tmp_path):
    (tmp_path / "a.laz").write_bytes(b"old")

    with writing(output_dir=tmp_path) as handle:
        with pytest.raises(ConflictError) as error:
            preflight(handle, ["a.laz", "b.laz", "b.laz"])
        preflight(handle, ["c.laz"])

    assert error.value.reason == "duplicate_output_name"
    assert error.value.details()["paths"] == [
        str(tmp_path / "a.laz"),
        str(tmp_path / "b.laz"),
        str(tmp_path / "b.laz"),
    ]
    preflight(tmp_path / "store", ["a.laz", "a.laz"])  # a store has no such rule


def test_a_plan_of_the_handle_is_the_plan_of_the_directory_with_one_action_each(
    tmp_path,
):
    (tmp_path / "old.laz").write_bytes(b"old")

    def item(name):
        return PlanItem("cz_laz", "", "", name, name, None, None, None, None, "missing")

    with writing(output_dir=tmp_path) as handle:
        plan = new_plan(
            handle, [item("new.laz"), item("old.laz"), item("dup.laz"), item("dup.laz")]
        )
        refused = plain_items(open_write(handle), [item("old.laz")])
    with writing(output_dir=tmp_path, force=True) as handle:
        (replaced,) = plain_items(open_write(handle), [item("old.laz")])

    assert (plan.mode, plan.root, plan.output_dir) == (
        "plain",
        None,
        str(tmp_path.resolve()),
    )
    assert [(i.name, i.action, i.reason, i.status) for i in plan.items] == [
        ("new.laz", "write", None, "missing"),
        ("old.laz", "conflict", "output_exists", "unverifiable"),
        ("dup.laz", "conflict", "duplicate_output_name", "unverifiable"),
        ("dup.laz", "conflict", "duplicate_output_name", "unverifiable"),
    ]
    assert plan.items[0].path == tmp_path / "new.laz"
    assert refused[0].action == "conflict"
    assert (replaced.action, replaced.status) == ("replace", "unverifiable")


def test_a_position_whose_check_failed_stays_failed_and_the_others_are_judged(
    tmp_path,
):
    """DEV-19.10: the position keeps ``check_failed``, its error and no action, as in
    the store, so the plan is not ok; its name still counts for the others."""

    def item(name, status="missing", error=None):
        return PlanItem(
            "pl_sheet", "", "", name, name, None, None, None, None, status, error
        )

    failed = item("a.asc", "check_failed", "HTTP 503")
    with writing(output_dir=tmp_path) as handle:
        plan = new_plan(handle, [failed, item("a.asc"), item("b.asc")])
        again = plain_items(open_write(handle), plan.items)

    assert plan.items[0] == failed
    assert [(i.status, i.action, i.reason, i.path) for i in plan.items[1:]] == [
        ("unverifiable", "conflict", "duplicate_output_name", tmp_path / "a.asc"),
        ("missing", "write", None, tmp_path / "b.asc"),
    ]
    assert again == plan.items
    assert not plan.ok
