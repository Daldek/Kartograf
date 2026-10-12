"""Versioned store core (spec 3, 3.1; D17-D23)."""

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import pytest

from kartograf.download import versions as v
from kartograf.exceptions import DownloadError

NAME = "N-34-139-C-a-3-1.asc"
ASC = (
    "ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\n"
    "NODATA_value -9999\n1 2\n-9999 4\n"
)


def stage(root: Path, body: str = ASC) -> Path:
    d = v.new_incoming_dir(root)
    p = d / NAME
    p.write_text(body)
    return p


def sidecar_writer(data: Path, ref: v.VersionRef, digest: v.ContentDigest) -> None:
    """Exclusive like the real version sidecar: an existing one raises."""
    payload = {"sha256": digest.sha256, "extra": {"version": ref.to_extra()}}
    with open(data.parent / f"{data.name}.meta.json", "x", encoding="utf-8") as f:
        f.write(json.dumps(payload))


def commit(root: Path, label="2025-06-02_91234", source="campaign", body=ASC):
    staged = stage(root, body)
    digest = v.read_content(staged, ext=".asc", coverage=True)
    return v.commit_version(
        staged, root, NAME, v.VersionRef(label, source), digest, sidecar_writer
    )


def test_layout_is_per_file_under_hierarchy(tmp_path):
    c = commit(tmp_path)
    assert c.status == "new"
    assert c.path.parent.name == f"2025-06-02_91234_{c.sha256[:8]}"
    assert c.path.parent.parent == tmp_path
    assert c.path.name == NAME
    assert not any((tmp_path / v.INCOMING_DIR).rglob(NAME))  # staged removed


def test_read_content_hashes_and_measures_in_one_pass(tmp_path):
    p = tmp_path / NAME
    p.write_text(ASC)
    d = v.read_content(p, ext=".asc", coverage=True)
    assert d.sha256 == hashlib.sha256(ASC.encode()).hexdigest()
    assert d.size_bytes == len(ASC.encode())
    assert d.coverage == pytest.approx(0.75)


def test_read_content_malformed_asc_keeps_digest_without_coverage(tmp_path, caplog):
    p = tmp_path / NAME
    p.write_text(ASC.replace("-9999 4\n", "-9999\n"))  # 3 of 4 cells
    d = v.read_content(p, ext=".asc", coverage=True)
    assert d.sha256 == hashlib.sha256(p.read_bytes()).hexdigest()
    assert d.coverage is None
    assert "3 komorek" in caplog.text


def test_commit_same_content_same_label_is_unchanged(tmp_path):
    first = commit(tmp_path)
    again = commit(tmp_path)
    assert again.status == "unchanged" and again.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_same_content_new_campaign_label_is_relabeled(tmp_path):
    first = commit(tmp_path, label="2024-05-10_80000")
    second = commit(tmp_path, label="2025-02-01_90000")
    assert second.status == "relabeled"
    assert second.path != first.path
    assert os.path.samefile(first.path, second.path)  # no extra space
    labels = {x.label for x in v.list_versions(tmp_path, NAME)}
    assert labels == {"2024-05-10_80000", "2025-02-01_90000"}


def test_commit_same_content_downloaded_label_is_unchanged(tmp_path):
    commit(tmp_path, label="2026-10-10", source="downloaded")
    again = commit(tmp_path, label="2026-10-11", source="downloaded")
    assert again.status == "unchanged"
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_other_content_is_new_version(tmp_path):
    commit(tmp_path)
    other = commit(tmp_path, label="2025-06-02_91235", body=ASC.replace("4\n", "5\n"))
    assert other.status == "new"
    assert len(v.list_versions(tmp_path, NAME)) == 2


def test_commit_existing_target_other_content_is_error(tmp_path):
    first = commit(tmp_path)
    first.path.write_text("uszkodzony")  # same name, different bytes
    (first.path.parent / f"{NAME}.meta.json").unlink()
    with pytest.raises(DownloadError, match="sha256"):
        commit(tmp_path)
    assert first.path.read_text() == "uszkodzony"  # never overwritten
    assert not list((tmp_path / v.INCOMING_DIR).rglob(NAME))


def test_commit_repairs_orphan_only_when_sha_matches(tmp_path):
    first = commit(tmp_path)
    (first.path.parent / f"{NAME}.meta.json").unlink()  # interrupted before sidecar
    assert v.list_versions(tmp_path, NAME) == []  # invalid version skipped
    repaired = commit(tmp_path)
    assert repaired.status == "new" and repaired.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_concurrent_same_content_one_version(tmp_path):
    results = []
    barrier = threading.Barrier(2)

    def run():
        staged = stage(tmp_path)
        digest = v.read_content(staged, ext=".asc", coverage=False)
        barrier.wait()
        results.append(
            v.commit_version(
                staged,
                tmp_path,
                NAME,
                v.VersionRef("2025-06-02_91234", "campaign"),
                digest,
                sidecar_writer,
            ).status
        )

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["new", "unchanged"]
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_without_hardlink_support_is_error(tmp_path, monkeypatch):
    def no_link(*a, **k):
        raise OSError(95, "Operation not supported")

    monkeypatch.setattr(v.os, "link", no_link)
    with pytest.raises(DownloadError, match="hardlink"):
        commit(tmp_path)
    assert v.list_versions(tmp_path, NAME) == []


def test_sidecar_failure_removes_data(tmp_path):
    staged = stage(tmp_path)
    digest = v.read_content(staged, ext=".asc", coverage=False)

    def broken(*a):
        raise OSError("dysk pelny")

    with pytest.raises(DownloadError):
        v.commit_version(
            staged, tmp_path, NAME, v.VersionRef("x_1", "campaign"), digest, broken
        )
    assert not list(tmp_path.glob(f"x_1_*/{NAME}"))


def test_sidecar_failure_on_repair_keeps_existing_data(tmp_path):
    first = commit(tmp_path)
    (first.path.parent / f"{NAME}.meta.json").unlink()
    staged = stage(tmp_path)
    digest = v.read_content(staged, ext=".asc", coverage=False)

    def broken(*a):
        raise OSError("dysk pelny")

    with pytest.raises(DownloadError):
        v.commit_version(
            staged,
            tmp_path,
            NAME,
            v.VersionRef("2025-06-02_91234", "campaign"),
            digest,
            broken,
        )
    assert first.path.read_text() == ASC  # not created by this call: kept


def test_list_versions_ignores_incoming_and_empty_dirs(tmp_path):
    commit(tmp_path)
    stage(tmp_path)  # leftover staging
    (tmp_path / "2020-01-01_1_deadbeef").mkdir()  # empty version dir
    (tmp_path / "1").mkdir()  # child hierarchy level (PL-2000)
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_list_versions_skips_dir_whose_sha_prefix_disagrees(tmp_path):
    c = commit(tmp_path)
    c.path.parent.rename(tmp_path / "2025-06-02_91234_00000000")
    assert v.list_versions(tmp_path, NAME) == []


def test_newest_version_campaign_key_and_downloaded_key(tmp_path):
    older = commit(tmp_path, label="2024-05-10_80000")
    (older.path.parent / f"{NAME}.meta.json").write_text(
        json.dumps(
            {
                "sha256": older.sha256,
                "extra": {
                    "version": {
                        "label": "2024-05-10_80000",
                        "label_source": "campaign",
                    },
                    "campaign": {"date": "2024-05-10", "pzgik_date": None},
                    "source": {"url": "https://x/80000_1_G.asc"},
                },
            }
        )
    )
    newer = commit(tmp_path, label="2025-02-01_90000", body=ASC.replace("4\n", "5\n"))
    (newer.path.parent / f"{NAME}.meta.json").write_text(
        json.dumps(
            {
                "sha256": newer.sha256,
                "extra": {
                    "version": {
                        "label": "2025-02-01_90000",
                        "label_source": "campaign",
                    },
                    "campaign": {"date": "2025-02-01", "pzgik_date": "2025-03-01"},
                    "source": {"url": "https://x/90000_1_G.asc"},
                },
            }
        )
    )
    found = v.list_versions(tmp_path, NAME)
    newest = v.newest_version(found)
    assert newest is not None and newest.label == "2025-02-01_90000"
    assert v.newest_version([]) is None


def test_downloaded_label_is_utc_date():
    from datetime import UTC, datetime, timedelta, timezone

    late = datetime(2026, 10, 11, 23, 30, tzinfo=timezone(timedelta(hours=-2)))
    assert v.VersionRef.downloaded(late) == v.VersionRef("2026-10-12", "downloaded")
    assert (
        v.VersionRef.downloaded(datetime(2026, 1, 2, tzinfo=UTC)).label == "2026-01-02"
    )


def test_cleanup_keeps_young_incoming(tmp_path):
    young = stage(tmp_path).parent
    old = stage(tmp_path).parent
    past = time.time() - v.STALE_AFTER_S - 10
    os.utime(old / NAME, (past, past))
    os.utime(old, (past, past))
    v.cleanup_stale(tmp_path)
    assert young.exists() and not old.exists()


def test_cleanup_removes_only_old_empty_version_dirs(tmp_path):
    c = commit(tmp_path)
    young = tmp_path / "2020-01-01_1_deadbeef"
    old = tmp_path / "2019-01-01_1_cafebabe"
    young.mkdir()
    old.mkdir()
    past = time.time() - v.STALE_AFTER_S - 10
    os.utime(old, (past, past))
    os.utime(c.path.parent, (past, past))  # old but a valid version
    v.cleanup_stale(tmp_path)
    assert young.exists() and not old.exists() and c.path.exists()


def test_incoming_dirs_are_unique_per_call(tmp_path):
    assert v.new_incoming_dir(tmp_path) != v.new_incoming_dir(tmp_path)


def http_writer(signal):
    """Version sidecar with ``extra.http`` (as the tracks write it)."""

    def write(data: Path, ref: v.VersionRef, digest: v.ContentDigest) -> None:
        payload = {
            "sha256": digest.sha256,
            "extra": {"version": ref.to_extra(), "http": signal},
        }
        with open(data.parent / f"{data.name}.meta.json", "x", encoding="utf-8") as f:
            f.write(json.dumps(payload))

    return write


def commit_http(root: Path, label: str, signal: dict | None):
    staged = stage(root)
    digest = v.read_content(staged, ext=".asc", coverage=False)
    return v.commit_version(
        staged,
        root,
        NAME,
        v.VersionRef(label, "downloaded"),
        digest,
        http_writer(signal),
        signal=signal,
    )


E1 = {"etag": '"e1"', "last_modified": "Mon, 05 Oct 2026", "content_length": 1}
E2 = {"etag": '"e2"', "last_modified": "Mon, 05 Oct 2026", "content_length": 1}


def test_commit_same_content_new_etag_is_relabeled(tmp_path):
    first = commit_http(tmp_path, "2026-10-10", E1)
    second = commit_http(tmp_path, "2026-10-12", E2)
    assert second.status == "relabeled" and second.label == "2026-10-12"
    assert second.path.parent.name == f"2026-10-12_{first.sha256[:8]}"
    assert os.path.samefile(first.path, second.path)
    newest = v.newest_version(v.list_versions(tmp_path, NAME))
    assert newest is not None and v.http_signal_of(newest) == E2


def test_commit_same_content_same_etag_is_unchanged(tmp_path):
    first = commit_http(tmp_path, "2026-10-10", E1)
    again = commit_http(tmp_path, "2026-10-12", dict(E1, content_length=999))
    assert again.status == "unchanged" and again.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_same_content_without_signal_is_unchanged(tmp_path):
    first = commit_http(tmp_path, "2026-10-10", E1)
    again = commit_http(tmp_path, "2026-10-12", None)
    assert again.status == "unchanged" and again.path == first.path


def test_commit_same_day_relabel_collision_is_unchanged(tmp_path):
    first = commit_http(tmp_path, "2026-10-12", E1)
    again = commit_http(tmp_path, "2026-10-12", E2)
    assert again.status == "unchanged" and again.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


@pytest.mark.parametrize(
    ("local", "remote", "expected"),
    [
        ({"etag": "a"}, {"etag": "a"}, True),
        ({"etag": "a", "last_modified": "x"}, {"etag": "b", "last_modified": "x"}, 0),
        ({"etag": None, "last_modified": "x"}, {"etag": "b", "last_modified": "x"}, 1),
        ({"last_modified": "x"}, {"last_modified": "y"}, False),
        ({"etag": "a"}, {"etag": None, "last_modified": "x"}, None),
        ({"content_length": 1}, {"content_length": 2}, None),
        ({"etag": "a", "content_length": 1}, {"etag": "a", "content_length": 2}, True),
        (None, {"etag": "a"}, None),
        ({"etag": "a"}, None, None),
    ],
)
def test_same_http_signal_rules(local, remote, expected):
    if expected in (0, 1):
        expected = bool(expected)
    assert v.same_http_signal(local, remote) is expected


@pytest.mark.parametrize("variant", ["removed_after_create", "exists_but_gone"])
def test_new_incoming_dir_survives_concurrent_cleanup(tmp_path, monkeypatch, variant):
    """A failed download of another worker removes the empty ``.incoming``
    tree while we create it; staging must still be created."""
    real_mkdir = os.mkdir
    raced = []

    def racing_mkdir(path, mode=0o777):
        if Path(path).name == v.INCOMING_DIR and not raced:
            raced.append(path)
            if variant == "exists_but_gone":
                # another worker created it, the cleanup removed it again
                raise FileExistsError(path)
            real_mkdir(path, mode)
            os.rmdir(path)
            return
        real_mkdir(path, mode)

    monkeypatch.setattr(os, "mkdir", racing_mkdir)
    staging = v.new_incoming_dir(tmp_path / "versions")
    assert staging.is_dir() and raced
