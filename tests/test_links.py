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


def test_regular_file_claiming_hardlink_is_not_trusted(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_link(link, a, k_a)
    other = link.parent / "other.asc"
    other.write_text("A")
    os.replace(other, link)  # same content, other inode
    assert linked_version(link) is None
    assert ensure_link(link, a, k_a).changed is True
    assert os.path.samefile(link, a)


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
