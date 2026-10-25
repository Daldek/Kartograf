"""Tests of standard path links to versions (kartograf.download.links, spec 3.2)."""

import hashlib
import json
import os
from unittest.mock import Mock

import pytest

from kartograf.download.links import (
    LinkOutcome,
    ensure_link,
    link_atomic,
    linked_version,
    version_key_of,
)
from kartograf.exceptions import DownloadError
from tests.support.smb_share import no_stable_inodes, report_one_link

A = ("2025-04-27_83233", "2025-04-27", "2025-11-17", "u1")
B = ("2025-10-21_84183", "2025-10-21", "2025-12-01", "u2")


def _version(root, label, body, date, dt, url):
    sha = hashlib.sha256(body.encode()).hexdigest()
    p = root / "seg" / "versions" / "N-34" / "139" / f"{label}_{sha[:8]}" / "x.asc"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    (p.parent / "x.asc.meta.json").write_text(
        json.dumps(
            {
                "sha256": sha,
                "extra": {
                    "version": {"label": label, "label_source": "campaign"},
                    "campaign": {
                        "id": label.split("_")[1],
                        "date": date,
                        "pzgik_date": dt,
                    },
                    "source": {"url": url},
                },
            }
        )
    )
    return p, (date, dt, url)


def _a(root, body="A"):
    return _version(root, A[0], body, *A[1:])


def _b(root, body="B"):
    return _version(root, B[0], body, *B[1:])


def _link(root):
    return root / "seg" / "N-34" / "139" / "x.asc"


def _sidecar(link):
    return link.parent / f"{link.name}.meta.json"


def _hardlinked(link, target):
    return (
        not link.is_symlink()
        and os.path.samefile(link, target)
        and os.stat(link).st_nlink == 2
    )


def _same(p, q):
    return os.path.normpath(os.path.abspath(p)) == os.path.normpath(os.path.abspath(q))


def _snapshot(link):
    """What a needless rewrite of the link or its sidecar would change."""
    sidecar = _sidecar(link)
    return (
        os.stat(link).st_ino,
        os.stat(sidecar).st_ino,
        os.stat(sidecar).st_mtime_ns,
        sidecar.read_bytes(),
    )


def test_hardlink_is_atomic_and_replaces_legacy_file(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    link.write_text("legacy")
    assert ensure_link(link, a, k_a) == LinkOutcome(a, True)
    assert _hardlinked(link, a) and link.read_text() == "A"
    assert not list(link.parent.glob("*.tmp"))


def test_link_without_hardlink_support_is_error(tmp_path, monkeypatch):
    a, _ = _a(tmp_path)
    link = _link(tmp_path)
    monkeypatch.setattr(os, "symlink", Mock(side_effect=AssertionError("symlink")))
    monkeypatch.setattr(os, "link", Mock(side_effect=OSError(95, "not supported")))
    with pytest.raises(DownloadError, match="hardlink"):
        link_atomic(a, link)
    assert not link.exists() and not link.is_symlink()
    assert not list(link.parent.glob("*.tmp"))


def test_link_sidecar_is_regular_file_with_link_fields(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    sc = _sidecar(link)
    assert sc.is_file() and not sc.is_symlink()
    extra = json.loads(sc.read_text())["extra"]
    assert extra["link"] == "hardlink"
    assert extra["link_target"] == f"../../versions/N-34/139/{a.parent.name}/x.asc"
    assert extra["version"]["label"] == A[0]


def test_symlinked_link_and_sidecar_replaced_without_writing_through(tmp_path):
    a, _ = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    a_sc = a.parent / "x.asc.meta.json"
    before = a_sc.read_bytes()
    os.symlink(os.path.relpath(a_sc, link.parent), _sidecar(link))
    os.symlink(os.path.relpath(a, link.parent), link)
    out = ensure_link(link, b, k_b)
    assert out.changed and _same(out.target, b)
    sc = _sidecar(link)
    assert not sc.is_symlink() and sc.is_file()
    assert json.loads(sc.read_text())["extra"]["campaign"]["date"] == "2025-10-21"
    assert a_sc.read_bytes() == before
    assert _hardlinked(link, b)
    assert a.read_text() == "A" and os.stat(a).st_nlink == 1


def test_copy_sidecar_from_older_release_is_unknown(tmp_path):
    """A 0.7.x link sidecar with ``extra.link == "copy"`` is never trusted (D22)."""
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    link.write_text("A")  # a copy, not a hardlink
    _sidecar(link).write_text(
        json.dumps({"extra": {"link": "copy", "link_target": "../../x.asc"}})
    )
    assert linked_version(link) is None
    assert ensure_link(link, a, k_a).changed is True
    assert _hardlinked(link, a)


def test_independent_copy_of_the_version_is_restored_as_hardlink(tmp_path):
    """The path holds the version's bytes (so the version), but it is not
    its hardlink: ``ensure_link`` restores the hardlink (D22), of that
    version."""
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    other = link.parent / "other.asc"
    other.write_text("A")
    os.replace(other, link)  # same content, other inode
    assert _same(linked_version(link), a)
    assert ensure_link(link, a, k_a) == LinkOutcome(a, True)
    assert _hardlinked(link, a)
    assert ensure_link(link, a, k_a).changed is False  # a hardlink again


def test_independent_copy_of_a_newer_version_is_not_moved_back(tmp_path):
    """The content decides what the path holds: the copy of B stays on B
    when an older A is chosen."""
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, b, k_b)
    other = link.parent / "other.asc"
    other.write_text("B")
    os.replace(other, link)
    assert ensure_link(link, a, k_a) == LinkOutcome(b, True)
    assert link.read_text() == "B" and _hardlinked(link, b)


def test_newer_version_moves_link_older_never(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    assert ensure_link(link, b, k_b).changed is True
    out = ensure_link(link, a, k_a, refresh=True)
    assert out == LinkOutcome(b, False)
    assert _hardlinked(link, b)


def test_equal_key_moves_only_on_refresh(tmp_path):
    """New content of the same campaign (same key, other version directory):
    the link moves only when that version was committed in this call."""
    a, k_a = _a(tmp_path)
    a2, k_a2 = _a(tmp_path, body="A2")
    assert k_a == k_a2 and a != a2
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    assert ensure_link(link, a2, k_a2).changed is False
    assert ensure_link(link, a2, k_a2, refresh=True).changed is True
    assert _hardlinked(link, a2)


def test_same_version_is_noop_missing_sidecar_relinks(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    assert ensure_link(link, a, k_a).changed is False
    _sidecar(link).unlink()
    assert linked_version(link) is None
    assert ensure_link(link, a, k_a).changed is True


def test_removed_version_dir_is_missing_and_relinked(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, b, k_b)
    (b.parent / "x.asc.meta.json").unlink()
    b.unlink()
    b.parent.rmdir()
    assert linked_version(link) is None
    assert ensure_link(link, a, k_a).changed is True
    assert _hardlinked(link, a)


def test_current_target_without_valid_sidecar_does_not_block_relink(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, b, k_b)
    (b.parent / "x.asc.meta.json").write_text("{zepsuty")
    assert version_key_of(b) is None
    assert ensure_link(link, a, k_a).changed is True


def test_failed_sidecar_write_drops_stale_sidecar_and_heals(
    tmp_path, monkeypatch, caplog
):
    """ADR-030 errata 10 (M-8): the link moved to B but its sidecar write
    failed - the old sidecar (describing A) is removed, never left behind;
    the next call relinks and writes the sidecar of B."""
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    real_replace = os.replace

    def failing(src, dst):
        if str(dst).endswith(".meta.json"):
            raise OSError("brak miejsca")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing)
    assert ensure_link(link, b, k_b).changed is True
    monkeypatch.setattr(os, "replace", real_replace)

    assert _hardlinked(link, b)
    assert not _sidecar(link).exists()
    assert not list(link.parent.glob("*.tmp"))
    assert "Could not write sidecar" in caplog.text
    assert linked_version(link) is None
    assert ensure_link(link, b, k_b).changed is True
    meta = json.loads(_sidecar(link).read_text())
    assert meta["extra"]["version"]["label"] == B[0]


def test_relpath_valueerror_gives_absolute_link_target(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    monkeypatch.setattr(os.path, "relpath", Mock(side_effect=ValueError("other drive")))
    ensure_link(link, a, k_a)
    target = json.loads(_sidecar(link).read_text())["extra"]["link_target"]
    assert os.path.isabs(target)
    monkeypatch.undo()
    assert _same(linked_version(link), a)
    assert not list(link.parent.glob("*.tmp"))


def test_failed_replace_keeps_old_link_and_no_tmp(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    monkeypatch.setattr(os, "replace", Mock(side_effect=OSError("dysk pelny")))
    with pytest.raises(OSError):
        ensure_link(link, b, k_b)
    monkeypatch.undo()
    assert _same(linked_version(link), a) and link.read_text() == "A"
    assert not list(link.parent.glob("*.tmp"))


def test_aux_xml_removed_on_relink(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    aux = link.parent / "x.asc.aux.xml"
    aux.write_text("<PAMDataset/>")
    assert ensure_link(link, a, k_a).changed is False
    assert aux.exists()
    assert ensure_link(link, b, k_b).changed is True
    assert not aux.exists()


@pytest.mark.parametrize("refresh", [False, True])
def test_link_does_not_move_back_while_smb_reports_one_link(
    tmp_path, monkeypatch, refresh
):
    """SMB without ``serverino``: the client reports one link for a path it
    has just opened. The path still holds the newer version B, so an older
    A is not linked (e2e 0.8.0: the link moved back to the 2022 flight)."""
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, b, k_b)
    before = _snapshot(link)
    with monkeypatch.context() as smb:
        no_stable_inodes(smb)
        report_one_link(smb, link)
        assert ensure_link(link, a, k_a, refresh=refresh) == LinkOutcome(b, False)
        assert _same(linked_version(link), b)
    assert _snapshot(link) == before  # nothing was rewritten
    assert link.read_text() == "B" and _hardlinked(link, b)


def test_local_version_with_one_reported_link_writes_nothing(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    before = _snapshot(link)
    with monkeypatch.context() as smb:
        no_stable_inodes(smb)
        report_one_link(smb, link)
        assert ensure_link(link, a, k_a) == LinkOutcome(a, False)
    assert _snapshot(link) == before


def test_link_stays_on_newer_version_when_every_path_reports_one_link(
    tmp_path, monkeypatch
):
    """The link count is no evidence at all: with one reported for the
    version file too the link may be re-linked, but never to an older one."""
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, b, k_b)
    with monkeypatch.context() as smb:
        no_stable_inodes(smb)
        report_one_link(smb)
        assert _same(linked_version(link), b)
        assert _same(ensure_link(link, a, k_a).target, b)
    assert link.read_text() == "B" and _hardlinked(link, b)


def test_hardlink_confirmed_by_sha256_without_inode_identity(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    no_stable_inodes(monkeypatch)
    assert _same(linked_version(link), a)
    assert ensure_link(link, a, k_a).changed is False  # no relink each run


def test_edited_link_rejected_without_inode_identity(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path, body="AAAA")
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    link.write_text("BBBB")  # same size, edited in place (both names)
    no_stable_inodes(monkeypatch)
    assert linked_version(link) is None


def test_lone_copy_is_restored_without_inode_identity(tmp_path, monkeypatch):
    """No path reports a second name: an independent copy of the version
    (``rsync -a`` without ``-H``), restored as a hardlink of the same version."""
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    other = link.parent / "other.asc"
    other.write_text("A")
    os.replace(other, link)
    with monkeypatch.context() as smb:
        no_stable_inodes(smb)
        assert _same(linked_version(link), a)
        assert ensure_link(link, a, k_a) == LinkOutcome(a, True)
    assert _hardlinked(link, a)
