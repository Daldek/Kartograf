"""Testy dowiazan sciezki standardowej (kartograf.download.links, ADR-030 d)."""

import json
import logging
import os
import shutil
from unittest.mock import Mock

import pytest

from kartograf.download.links import (
    LinkOutcome,
    campaign_key_of,
    ensure_standard_link,
    link_atomic,
    linked_campaign,
    write_standard_sidecar,
)

A = ("2025-04-27_83233", "2025-04-27", "2025-11-17", "u1")
B = ("2025-10-21_84183", "2025-10-21", "2025-12-01", "u2")


def _campaign(root, dirname, body, date, dt, url):
    p = root / "seg" / "kampanie" / dirname / "N-34" / "139" / "x.asc"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    (p.parent / "x.asc.meta.json").write_text(
        json.dumps(
            {
                "extra": {
                    "campaign": {
                        "id": dirname.split("_")[1],
                        "date": date,
                        "dt_pzgik": dt,
                    },
                    "source": {"url": url},
                }
            }
        )
    )
    return p, (date, dt, url)


def _a(root, body="A"):
    return _campaign(root, A[0], body, *A[1:])


def _b(root, body="B"):
    return _campaign(root, B[0], body, *B[1:])


def _link(root):
    return root / "seg" / "N-34" / "139" / "x.asc"


def _sidecar(link):
    return link.parent / f"{link.name}.meta.json"


def _no_links(monkeypatch):
    monkeypatch.setattr(os, "link", Mock(side_effect=OSError(1, "not permitted")))


def _hardlinked(link, target):
    return (
        not link.is_symlink()
        and os.path.samefile(link, target)
        and os.stat(link).st_nlink == 2
    )


def _same(p, q):
    return os.path.normpath(os.path.abspath(p)) == os.path.normpath(os.path.abspath(q))


def test_hardlink_is_atomic(tmp_path):
    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    link.write_text("legacy")
    out = ensure_standard_link(link, old, k_old)
    assert out == LinkOutcome("hardlink", old, True)
    assert _hardlinked(link, old) and link.read_text() == "A"
    assert not list(link.parent.glob("*.tmp"))


def test_link_atomic_never_creates_symlink(tmp_path, monkeypatch):
    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    monkeypatch.setattr(os, "symlink", Mock(side_effect=AssertionError("symlink")))
    assert link_atomic(old, link) == "hardlink"
    with monkeypatch.context() as m:
        _no_links(m)
        assert link_atomic(old, link) == "copy"
    assert not link.is_symlink()


def test_standard_sidecar_is_regular_file_with_link_fields(tmp_path):
    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, old, k_old)
    sc = _sidecar(link)
    assert sc.is_file() and not sc.is_symlink()
    extra = json.loads(sc.read_text())["extra"]
    assert extra["link"] == "hardlink"
    assert extra["link_target"] == "../../kampanie/2025-04-27_83233/N-34/139/x.asc"
    assert extra["campaign"]["date"] == "2025-04-27"
    assert extra["campaign"]["dt_pzgik"] == "2025-11-17"


def test_standard_sidecar_is_regular_file_even_if_symlink_existed(tmp_path):
    a, _ = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    a_sc = a.parent / "x.asc.meta.json"
    before = a_sc.read_bytes()
    os.symlink(os.path.relpath(a_sc, link.parent), _sidecar(link))
    os.symlink(os.path.relpath(a, link.parent), link)
    out = ensure_standard_link(link, b, k_b)
    assert out.changed and _same(out.target, b)
    sc = _sidecar(link)
    assert not sc.is_symlink() and sc.is_file()
    assert json.loads(sc.read_text())["extra"]["campaign"]["date"] == "2025-10-21"
    assert a_sc.read_bytes() == before
    # os.replace zastepuje SAM symlink, cel symlinku nietkniety
    assert _hardlinked(link, b)
    assert a.read_text() == "A" and os.stat(a).st_nlink == 1


def test_legacy_symlink_with_symlink_sidecar_is_unknown_and_replaced(tmp_path):
    """Errata 4: symlink z sidecarem ``extra.link=symlink`` (dane sprzed
    wydania) to sciezka nieznana — nawet przy tym samym celu ``newest``
    zastepuje go hardlinkiem, bez zapisu przez symlink."""
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    os.symlink(os.path.relpath(a, link.parent), link)
    meta = json.loads((a.parent / "x.asc.meta.json").read_text())
    meta["extra"]["link"] = "symlink"
    meta["extra"]["link_target"] = os.path.relpath(a, link.parent)
    _sidecar(link).write_text(json.dumps(meta))
    a_side = (a.parent / "x.asc.meta.json").read_bytes()
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out == LinkOutcome("hardlink", a, True)
    assert _hardlinked(link, a) and a.read_text() == "A"
    assert not a.is_symlink() and (a.parent / "x.asc.meta.json").read_bytes() == a_side
    assert json.loads(_sidecar(link).read_text())["extra"]["link"] == "hardlink"


def test_regular_file_claiming_hardlink_to_other_campaign_is_not_trusted(tmp_path):
    a, k_a = _a(tmp_path)
    b, _ = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, a, k_a)
    meta = json.loads(_sidecar(link).read_text())
    meta["extra"]["link_target"] = os.path.relpath(b, link.parent)
    _sidecar(link).write_text(json.dumps(meta))
    assert linked_campaign(link) is None


def test_newer_campaign_moves_link(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, a, k_a)
    out = ensure_standard_link(link, b, k_b)
    assert out.changed is True and _same(out.target, b)
    assert link.read_text() == "B" and _same(linked_campaign(link), b)


def test_ensure_link_never_regresses_to_older_campaign(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, b, k_b)
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is False and _same(out.target, b)
    assert link.read_text() == "B"


def test_same_campaign_is_noop_missing_sidecar_relinks(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    assert ensure_standard_link(link, a, k_a).changed is True
    assert ensure_standard_link(link, a, k_a).changed is False
    _sidecar(link).unlink()  # sidecar = jedyne zrodlo celu: sciezka nieznana
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and out.method == "hardlink"
    assert _hardlinked(link, a)  # rename na ten sam i-wezel: tmp sprzatniety
    assert not list(link.parent.glob("*.tmp"))
    assert _sidecar(link).is_file()
    assert json.loads(_sidecar(link).read_text())["extra"]["link"] == "hardlink"


def test_removed_campaign_dir_is_missing_and_relinked(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, b, k_b)
    shutil.rmtree(tmp_path / "seg" / "kampanie" / B[0])
    assert link.is_file()  # hardlink przezywa usuniecie kampanii
    assert linked_campaign(link) is None  # link_target z sidecara nie istnieje
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and _same(out.target, a)
    assert link.read_text() == "A"


def test_legacy_regular_file_without_link_field_is_replaced(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    link.parent.mkdir(parents=True)
    link.write_text("legacy")
    _sidecar(link).write_text(json.dumps({"extra": {"source": {"url": "old"}}}))
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and _hardlinked(link, a)


def test_no_hardlink_falls_back_to_copy_with_warning(tmp_path, monkeypatch, caplog):
    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    _no_links(monkeypatch)
    with caplog.at_level(logging.WARNING, logger="kartograf.download.links"):
        out = ensure_standard_link(link, old, k_old)
    assert out.method == "copy" and out.changed is True
    assert link.read_text() == "A" and not os.path.samefile(link, old)
    assert not link.is_symlink()
    assert json.loads(_sidecar(link).read_text())["extra"]["link"] == "copy"
    assert any(
        r.levelno == logging.WARNING and "kopia" in r.getMessage()
        for r in caplog.records
    )
    assert not list(link.parent.glob("*.tmp"))


def test_relpath_valueerror_gives_absolute_link_target(tmp_path, monkeypatch):
    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    monkeypatch.setattr(os.path, "relpath", Mock(side_effect=ValueError("other drive")))
    out = ensure_standard_link(link, old, k_old)
    assert out.method == "hardlink" and _hardlinked(link, old)
    target = json.loads(_sidecar(link).read_text())["extra"]["link_target"]
    assert os.path.isabs(target)
    monkeypatch.undo()
    assert _same(linked_campaign(link), old)
    assert not list(link.parent.glob("*.tmp"))


def test_copy_detected_via_sidecar_on_next_run(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    with monkeypatch.context() as m:
        _no_links(m)
        assert ensure_standard_link(link, a, k_a).method == "copy"
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is False and out.method == "copy"
    assert _same(linked_campaign(link), a)


def test_copy_with_size_mismatch_is_replaced(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    _no_links(monkeypatch)
    ensure_standard_link(link, a, k_a)
    link.write_text("inny rozmiar")
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and link.read_text() == "A"


def test_hardlink_broken_by_edit_is_replaced(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    assert ensure_standard_link(link, a, k_a).method == "hardlink"
    other = link.parent / "other.asc"
    other.write_text("A")
    os.replace(other, link)
    assert not os.path.samefile(link, a)
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and os.path.samefile(link, a)


def test_refresh_recopies_when_target_redownloaded(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    _no_links(monkeypatch)
    ensure_standard_link(link, a, k_a)
    a.write_text("Z")  # ten sam rozmiar
    t = link.stat().st_mtime - 10  # cel nie "nowszy" od kopii: tylko refresh decyduje
    os.utime(a, (t, t))
    assert _same(linked_campaign(link), a)
    out = ensure_standard_link(link, a, k_a, refresh=True)
    assert out.changed is True and link.read_text() == "Z"


def test_failed_replace_keeps_old_link_and_no_tmp(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, a, k_a)
    monkeypatch.setattr(os, "replace", Mock(side_effect=OSError("dysk pelny")))
    with pytest.raises(OSError):
        ensure_standard_link(link, b, k_b)
    monkeypatch.undo()
    assert _same(linked_campaign(link), a) and link.read_text() == "A"
    assert not list(link.parent.glob("*.tmp"))


def test_aux_xml_removed_on_relink(tmp_path):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, a, k_a)
    aux = link.parent / "x.asc.aux.xml"
    aux.write_text("<PAMDataset/>")
    assert ensure_standard_link(link, a, k_a).changed is False
    assert aux.exists()
    assert ensure_standard_link(link, b, k_b).changed is True
    assert not aux.exists()


def test_ensure_link_replaces_older_target_set_by_other_process(tmp_path):
    a, _ = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, b, k_b)
    # inny proces (R2) ustawia link na A po tym, jak B byl celem
    assert link_atomic(a, link) == "hardlink"
    write_standard_sidecar(link, a, "hardlink")
    assert _same(linked_campaign(link), a)
    out = ensure_standard_link(link, b, k_b)
    assert out.changed is True and _same(out.target, b) and link.read_text() == "B"


# --- poprawki po weryfikacji (D-1, D-5) ---


@pytest.mark.parametrize("method", ["hardlink", "copy"])
def test_missing_target_sidecar_still_prevents_regression(
    tmp_path, monkeypatch, method
):
    a, k_a = _a(tmp_path)
    b, k_b = _b(tmp_path)
    link = _link(tmp_path)
    if method == "copy":
        _no_links(monkeypatch)
    assert ensure_standard_link(link, b, k_b).method == method
    (b.parent / "x.asc.meta.json").unlink()
    assert _sidecar(link).exists()
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is False and _same(out.target, b)
    assert link.read_text() == "B"
    assert campaign_key_of(b) == ("2025-10-21", "", "")


def test_same_target_with_missing_sidecar_is_noop(tmp_path):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    ensure_standard_link(link, a, k_a)
    (a.parent / "x.asc.meta.json").unlink()
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is False and _same(out.target, a)


def test_unparsable_campaign_dir_without_sidecar_gives_no_key(tmp_path):
    p = tmp_path / "seg" / "kampanie" / "2025-04-27_83233x" / "N-34" / "x.asc"
    p.parent.mkdir(parents=True)
    p.write_text("A")
    assert campaign_key_of(p) is None


def test_copy_older_than_target_is_replaced(tmp_path, monkeypatch):
    a, k_a = _a(tmp_path)
    link = _link(tmp_path)
    _no_links(monkeypatch)
    ensure_standard_link(link, a, k_a)
    t0 = link.stat().st_mtime
    tmp = a.with_name("x.asc.part")
    tmp.write_text("N")  # ten sam rozmiar, jak download_to (tmp + os.replace)
    os.replace(tmp, a)
    os.utime(a, (t0 + 10, t0 + 10))
    assert linked_campaign(link) is None
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is True and link.read_text() == "N"


# --- Fix round 1: segment "kampanie" w korzeniu katalogu wyjsciowego ---


def test_campaign_key_from_dir_uses_last_kampanie_segment(tmp_path):
    root = tmp_path / "kampanie" / "data"
    b, _ = _b(root)
    (b.parent / "x.asc.meta.json").unlink()
    assert campaign_key_of(b) == ("2025-10-21", "", "")


def test_kampanie_in_output_root_still_prevents_regression(tmp_path):
    root = tmp_path / "kampanie" / "data"
    a, k_a = _a(root)
    b, k_b = _b(root)
    link = _link(root)
    ensure_standard_link(link, b, k_b)
    (b.parent / "x.asc.meta.json").unlink()
    out = ensure_standard_link(link, a, k_a)
    assert out.changed is False and _same(out.target, b)
    assert link.read_text() == "B"


# --- Fix round 1: porazka sprzatania tmp nie gubi proby kopii ---


def test_tmp_cleanup_failure_after_hardlink_error_still_copies(tmp_path, monkeypatch):
    from pathlib import Path

    old, k_old = _a(tmp_path)
    link = _link(tmp_path)
    real_unlink = Path.unlink
    calls = {"n": 0}

    def link_then_fail(src, dst):
        Path(dst).write_text("polowiczny")  # tmp zostal, ale link sie nie udal
        raise OSError(1, "not permitted")

    def flaky_unlink(self, missing_ok=False):
        if self.name.endswith(".link.tmp"):
            calls["n"] += 1
            if calls["n"] > 1:  # pierwsze = sprzatanie po przerwanym przebiegu
                raise OSError(16, "busy")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(os, "link", link_then_fail)
    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    out = ensure_standard_link(link, old, k_old)
    assert out.method == "copy" and link.read_text() == "A"
    assert calls["n"] >= 2
