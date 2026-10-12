"""Policy for files without campaigns (kartograf.download.fetch, spec 4.2)."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.download import versions as v
from kartograf.download.fetch import FileSlot, fetch_version, inspect_version
from kartograf.exceptions import DownloadError, ValidationError

NAME = "CTES96.tif"
E1 = {"etag": '"e1"', "last_modified": "Mon, 05 Oct 2026", "content_length": 3}
E2 = {"etag": '"e2"', "last_modified": "Tue, 06 Oct 2026", "content_length": 3}
NO_TAG = {"etag": None, "last_modified": None, "content_length": 3}


def make_slot(root: Path) -> FileSlot:
    base = root / "nmt/cz_dmr4g_bpv/versions"
    return FileSlot(
        output_dir=root,
        std=root / "nmt/cz_dmr4g_bpv/CTES/CTES96.tif",
        versions_base=base,
        versions_root=base / "CTES",
        ext=".tif",
    )


class Source:
    """Fake source: body and HTTP signal of a download, HEAD probe."""

    def __init__(self, body=b"abc", signal=None, head=None):
        self.body, self.signal, self.head = body, signal, head
        self.downloads = 0
        self.probes = 0

    def fetch(self, staged: Path) -> dict | None:
        self.downloads += 1
        staged.write_bytes(self.body)
        return self.signal

    def probe(self) -> dict:
        self.probes += 1
        if isinstance(self.head, Exception):
            raise self.head
        return self.head or {}


def write_sidecar(data, ref, digest, http):
    payload = {
        "sha256": digest.sha256,
        "extra": {"version": ref.to_extra(), "http": http},
    }
    with open(data.parent / f"{data.name}.meta.json", "x", encoding="utf-8") as f:
        f.write(json.dumps(payload))


def run(slot, src, update=None, *, signal="http", label="2026-10-12", probe=True):
    return fetch_version(
        slot,
        update,
        signal=signal,
        fetch=src.fetch,
        version=v.VersionRef(label, "downloaded"),
        write_sidecar=write_sidecar,
        probe=src.probe if probe else None,
    )


def seed(slot, signal=E1, body=b"abc", label="2026-10-01"):
    """A local version downloaded earlier with ``signal``."""
    return run(slot, Source(body, signal), signal="http", label=label, probe=False)


def test_first_download_is_version_with_link_and_extra_http(tmp_path):
    slot = make_slot(tmp_path)
    src = Source(b"abc", E1, head=E1)
    result = run(slot, src)
    assert result.status == "new" and src.downloads == 1 and src.probes == 0
    assert result.version_path.parent.parent == slot.versions_root
    assert result.version_path.parent.name.startswith("2026-10-12_")
    assert os.path.samefile(slot.std, result.version_path)
    meta = json.loads(Path(f"{result.version_path}.meta.json").read_text())
    assert meta["extra"]["http"] == E1
    assert not any((slot.versions_base / v.INCOMING_DIR).iterdir())


# Spec 4.2 table: (local signal, source HEAD, mode) -> outcome.
MATRIX = [
    # http, equal signal
    ("http", E1, None, "local", None, None, 0),
    ("http", E1, "upgrade", "local", None, None, 0),
    ("http", E1, "force", "unchanged", None, None, 1),
    # http, different signal
    ("http", E2, None, "local", '"e2"', None, 0),
    ("http", E2, "upgrade", "relabeled", None, None, 1),
    ("http", E2, "force", "relabeled", None, None, 1),
    # http, not comparable (source without ETag/Last-Modified)
    ("http", NO_TAG, None, "local", None, "none", 0),
    ("http", NO_TAG, "upgrade", "local", None, "none", 0),
    ("http", NO_TAG, "force", "unchanged", None, None, 1),
    # http, probe failure (default; upgrade raises — separate test)
    ("http", DownloadError("HEAD 503"), None, "local", None, "check_failed", 0),
    ("http", DownloadError("HEAD 503"), "force", "unchanged", None, None, 1),
    # none: no cheap signal
    ("none", None, None, "local", None, "none", 0),
    ("none", None, "upgrade", "local", None, "none", 0),
    ("none", None, "force", "unchanged", None, None, 1),
    # index/metadata: the caller selected the file by its signal
    ("index", None, None, "local", None, None, 0),
    ("index", None, "upgrade", "local", None, None, 0),
    ("index", None, "force", "unchanged", None, None, 1),
    ("metadata", None, None, "local", None, None, 0),
]


@pytest.mark.parametrize(
    ("signal", "head", "update", "status", "newer", "unverified", "downloads"), MATRIX
)
def test_fetch_version_matrix(
    tmp_path, signal, head, update, status, newer, unverified, downloads
):
    slot = make_slot(tmp_path)
    first = seed(slot)
    sent = E2 if head is E2 else E1  # a download returns the source's signal
    src = Source(b"abc", sent, head=head)
    result = run(slot, src, update, signal=signal, probe=signal == "http")
    assert result.status == status
    assert result.newer == newer
    assert (result.unverified or "").split(":")[0] == (unverified or "")
    assert src.downloads == downloads
    assert src.probes == (1 if signal == "http" and update != "force" else 0)
    assert os.path.samefile(slot.std, result.version_path)
    if status == "local":
        assert result.version_path == first.version_path


def test_fetch_version_missing_local_downloads_in_every_mode(tmp_path):
    for i, update in enumerate((None, "upgrade", "force")):
        slot = make_slot(tmp_path / str(i))
        src = Source(head=E1)
        assert run(slot, src, update).status == "new"
        assert (src.downloads, src.probes) == (1, 0)


def test_fetch_version_upgrade_probe_failure_raises(tmp_path):
    slot = make_slot(tmp_path)
    seed(slot)
    src = Source(head=DownloadError("HEAD 503"))
    with pytest.raises(DownloadError, match="503"):
        run(slot, src, "upgrade")
    assert src.downloads == 0


def test_fetch_version_new_content_is_new_version_link_moves(tmp_path):
    slot = make_slot(tmp_path)
    first = seed(slot)
    result = run(slot, Source(b"xyz", E2, head=E2), "upgrade")
    assert result.status == "new" and result.version_path != first.version_path
    assert os.path.samefile(slot.std, result.version_path)
    assert len(v.list_versions(slot.versions_root, NAME)) == 2


def test_fetch_version_never_reads_twice(tmp_path):
    slot = make_slot(tmp_path)
    with patch("kartograf.download.fetch.read_content", wraps=v.read_content) as reads:
        run(slot, Source(head=E1))
    assert reads.call_count == 1


def test_fetch_version_failure_leaves_no_version_and_no_staging(tmp_path):
    slot = make_slot(tmp_path)

    def broken(staged: Path) -> dict:
        staged.write_bytes(b"pol")
        raise DownloadError("przerwane")

    with pytest.raises(DownloadError, match="przerwane"):
        fetch_version(
            slot,
            None,
            signal="none",
            fetch=broken,
            version=v.VersionRef("2026-10-12", "downloaded"),
            write_sidecar=write_sidecar,
        )
    assert list(tmp_path.iterdir()) == []  # no versions/, no .incoming/


def test_fetch_version_failure_keeps_previous_version_and_link(tmp_path):
    slot = make_slot(tmp_path)
    first = seed(slot)

    def broken(staged: Path) -> dict:
        raise DownloadError("503")

    with pytest.raises(DownloadError):
        fetch_version(
            slot,
            "force",
            signal="none",
            fetch=broken,
            version=v.VersionRef("2026-10-12", "downloaded"),
            write_sidecar=write_sidecar,
        )
    assert os.path.samefile(slot.std, first.version_path)
    assert [x.path for x in v.list_versions(slot.versions_root, NAME)] == [
        first.version_path
    ]


def test_fetch_version_check_mode_is_validation_error(tmp_path):
    src = Source()
    with pytest.raises(ValidationError, match="check"):
        run(make_slot(tmp_path), src, "check")
    assert src.downloads == 0


def test_fetch_version_legacy_plain_file_replaced_by_link(tmp_path):
    """D24: a regular 0.7.x file at the standard path becomes a hardlink."""
    slot = make_slot(tmp_path)
    slot.std.parent.mkdir(parents=True)
    slot.std.write_bytes(b"stary")
    Path(f"{slot.std}.meta.json").write_text(json.dumps({"sha256": "0" * 64}))
    result = run(slot, Source(b"nowy", E1, head=E1))
    assert result.status == "new"
    assert os.path.samefile(slot.std, result.version_path)
    assert slot.std.read_bytes() == b"nowy"


# --- inspect_version -----------------------------------------------------


def inspect(slot, src, signal="http", available=(None, None)):
    return inspect_version(
        slot,
        track="cz_sheet",
        unit="CTES96",
        signal=signal,
        probe=src.probe if signal == "http" else None,
        available=available,
    )


@pytest.mark.parametrize(
    ("seeded", "signal", "head", "status"),
    [
        (False, "http", E1, "missing"),
        (True, "http", E1, "current"),
        (True, "http", E2, "newer"),
        (True, "http", NO_TAG, "unverifiable"),
        (True, "http", DownloadError("HEAD 503"), "check_failed"),
        (True, "none", None, "unverifiable"),
        (False, "none", None, "missing"),
        (True, "index", None, "current"),
    ],
)
def test_inspect_version_statuses(tmp_path, seeded, signal, head, status):
    slot = make_slot(tmp_path)
    if seeded:
        seed(slot)
    src = Source(head=head)
    item = inspect(slot, src, signal)
    assert item.status == status
    assert src.downloads == 0
    assert (item.track, item.unit, item.name) == ("cz_sheet", "CTES96", NAME)
    assert item.segment == "nmt/cz_dmr4g_bpv" and item.hierarchy == "CTES"
    if status == "check_failed":
        assert "503" in (item.error or "")
    if signal == "http" and status != "check_failed":
        assert item.available_signal == head
    assert (item.local_label is not None) == seeded


def test_inspect_version_index_keeps_callers_signal(tmp_path):
    src = Source()
    sig = {"url": "https://example.test/a.laz", "year": 2025, "date": "2025-04-05"}
    item = inspect(make_slot(tmp_path), src, "index", ("2025-04-05_83998", sig))
    assert item.available_label == "2025-04-05_83998"
    assert item.available_signal == sig and item.status == "missing"


def test_inspect_version_never_calls_fetch(tmp_path):
    slot = make_slot(tmp_path)
    seed(slot)
    src = Source(head=E2)
    for signal in ("http", "none", "index"):
        inspect(slot, src, signal)
    assert src.downloads == 0
    assert not (slot.versions_base / v.INCOMING_DIR).exists() or not any(
        (slot.versions_base / v.INCOMING_DIR).iterdir()
    )
