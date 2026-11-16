"""Policy for files without campaigns (kartograf.download.fetch, spec 4.2)."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import versions as v
from kartograf.download.fetch import (
    FileSlot,
    fetch_version,
    inspect_version,
    new_staging,
    store_file,
    use_local,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.marker import prepare_store
from kartograf.sources.edition import Edition

NAME = "CTES96.tif"
E1 = {"etag": '"e1"', "last_modified": "Mon, 05 Oct 2026", "content_length": 3}
E2 = {"etag": '"e2"', "last_modified": "Tue, 06 Oct 2026", "content_length": 3}
NO_TAG = {"etag": None, "last_modified": None, "content_length": 3}


def make_slot(root: Path) -> FileSlot:
    base = root / "nmt/cz_dmr4g_bpv/versions"
    return FileSlot(
        root=root,
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


# Spec 4.2 table: (local signal, source HEAD, mode) -> outcome. The default
# mode asks no source for a local version (ADR-036 erratum 3): "unchecked".
MATRIX = [
    # http, equal signal
    ("http", E1, None, "local", None, "unchecked", 0),
    ("http", E1, "upgrade", "local", None, None, 0),
    ("http", E1, "force", "unchanged", None, None, 1),
    # http, different signal
    ("http", E2, None, "local", None, "unchecked", 0),
    ("http", E2, "upgrade", "relabeled", None, None, 1),
    ("http", E2, "force", "relabeled", None, None, 1),
    # http, not comparable (source without ETag/Last-Modified)
    ("http", NO_TAG, None, "local", None, "unchecked", 0),
    ("http", NO_TAG, "upgrade", "local", None, "none", 0),
    ("http", NO_TAG, "force", "unchanged", None, None, 1),
    # http, probe failure (default: not asked; upgrade raises — separate test)
    ("http", DownloadError("HEAD 503"), None, "local", None, "unchecked", 0),
    ("http", DownloadError("HEAD 503"), "force", "unchanged", None, None, 1),
    # none: no cheap signal
    ("none", None, None, "local", None, "none", 0),
    ("none", None, "upgrade", "local", None, "none", 0),
    ("none", None, "force", "unchanged", None, None, 1),
    # index: the caller selected the file by its signal
    ("index", None, None, "local", None, None, 0),
    ("index", None, "upgrade", "local", None, None, 0),
    ("index", None, "force", "unchanged", None, None, 1),
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
    assert src.probes == (1 if signal == "http" and update == "upgrade" else 0)
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


_AREA = {"bbox": BBox(500000, 300000, 501000, 301000, "EPSG:2180")}


@pytest.mark.parametrize(
    ("function", "arguments", "check"),
    [
        (
            "download_landcover",
            {"product": "bdot10k", "teryt": "1863"},
            "check_landcover",
        ),
        (
            "download_soil",
            {**_AREA, "property": "clay", "depth": "0-5cm", "stat": "mean"},
            "check_soil",
        ),
        ("calculate_hsg", {**_AREA, "depth": "0-5cm"}, "check_hsg"),
        (
            "download_image_cutout",
            {**_AREA, "product": "true-orto", "horizontal_crs": "EPSG:2180"}
            | {"resolution": "0.05m"},
            "check_image_cutout",
        ),
        ("download_data", {**_AREA, "product": "nmt", "country": "pl"}, "check_data"),
        (
            "download_collection",
            {**_AREA, "product": "admin", "country": "pl", "level": "gmina"},
            "check_collection",
        ),
    ],
)
def test_check_mode_names_the_plan_function_of_the_track(
    tmp_path, function, arguments, check
):
    """``update="check"`` in a download function names the plan function of
    its own track, before any request or write."""
    import kartograf

    with pytest.raises(ValidationError, match=rf"use {check}\(\)"):
        getattr(kartograf, function)(
            root=tmp_path, update="check", cache=False, **arguments
        )
    assert list(tmp_path.iterdir()) == []


def test_fetch_version_legacy_plain_file_replaced_by_link(tmp_path):
    """D24: a regular 0.7.x file at the standard path becomes a hardlink."""
    prepare_store(tmp_path)
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


# --- metadata (edition) signal, plan 3/3 decision 2 -------------------------


class Editions:
    """Fake edition lookup: ``id`` or a ``DownloadError``, counts calls."""

    def __init__(self, current):
        self.current, self.calls = current, 0

    def __call__(self) -> Edition:
        self.calls += 1
        if isinstance(self.current, Exception):
            raise self.current
        return Edition(self.current, "https://example.test/caps")


def run_meta(slot, src, update=None, *, edition):
    return fetch_version(
        slot,
        update,
        signal="metadata",
        fetch=src.fetch,
        write_sidecar=write_sidecar,
        edition=edition,
    )


def seed_meta(slot, label="2.0", body=b"abc"):
    return run_meta(slot, Source(body), edition=Editions(label))


FAIL = DownloadError("GetCapabilities 503")

# (local, edition(), mode) -> (status, label, newer, unverified, downloads)
META_MATRIX = [
    (None, "2.0", None, "new", "2.0", None, None, 1),
    (None, "2.0", "upgrade", "new", "2.0", None, None, 1),
    (None, "2.0", "force", "new", "2.0", None, None, 1),
    ("2.0", "2.0", None, "local", "2.0", None, "unchecked", 0),
    ("2.0", "2.0", "upgrade", "local", "2.0", None, None, 0),
    ("2.0", "2.0", "force", "unchanged", "2.0", None, None, 1),
    ("2.0", "2.1", None, "local", "2.0", None, "unchecked", 0),
    ("2.0", "2.1", "upgrade", "relabeled", "2.1", None, None, 1),
    ("2.0", "2.1", "force", "relabeled", "2.1", None, None, 1),
    ("2.0", FAIL, None, "local", "2.0", None, "unchecked", 0),
    ("downloaded", "2.0", None, "local", "2026-10-01", None, "unchecked", 0),
    ("downloaded", "2.0", "upgrade", "local", "2026-10-01", None, "none", 0),
    ("downloaded", "2.0", "force", "relabeled", "2.0", None, None, 1),
]


@pytest.mark.parametrize(
    ("local", "current", "update", "status", "label", "newer", "unverified", "dl"),
    META_MATRIX,
)
def test_fetch_version_metadata_matrix(
    tmp_path, local, current, update, status, label, newer, unverified, dl
):
    slot = make_slot(tmp_path)
    if local == "downloaded":
        seed(slot, signal=None)  # a version not labelled by an edition
    elif local is not None:
        seed_meta(slot, local)
    src, editions = Source(b"abc"), Editions(current)
    result = run_meta(slot, src, update, edition=editions)
    assert (result.status, result.label) == (status, label)
    assert result.newer == newer
    assert (result.unverified or "").split(":")[0] == (unverified or "")
    assert src.downloads == dl
    if update is None and local is not None:
        assert editions.calls == 0  # the default mode asks no source
    else:
        assert editions.calls <= 1
    assert os.path.samefile(slot.std, result.version_path)


@pytest.mark.parametrize(
    ("local", "update"),
    [
        (None, None),
        (None, "upgrade"),
        (None, "force"),
        ("2.0", "upgrade"),
        ("2.0", "force"),
    ],
)
def test_fetch_version_metadata_unavailable_is_error(tmp_path, local, update):
    """No version without an edition; ``--upgrade``/``--force`` need it too."""
    slot = make_slot(tmp_path)
    if local is not None:
        seed_meta(slot, local)
    src = Source(b"new")
    with pytest.raises(DownloadError, match="503"):
        run_meta(slot, src, update, edition=Editions(FAIL))
    assert src.downloads == 0
    assert len(v.list_versions(slot.versions_root, NAME)) == (local is not None)


def test_metadata_same_content_new_edition_is_relabeled(tmp_path):
    """D23: same sha256 under a new edition = own directory, hardlinked data."""
    slot = make_slot(tmp_path)
    first = seed_meta(slot, "2.0")
    result = run_meta(slot, Source(b"abc"), "upgrade", edition=Editions("2.1"))
    assert result.status == "relabeled"
    assert result.version_path.parent.name == f"2.1_{first.sha256[:8]}"
    assert os.path.samefile(result.version_path, first.version_path)
    meta = json.loads(Path(f"{result.version_path}.meta.json").read_text())
    assert meta["extra"]["version"] == {"label": "2.1", "label_source": "edition"}


def test_metadata_edition_called_once_per_file(tmp_path):
    slot = make_slot(tmp_path)
    seed_meta(slot, "2.0")
    editions = Editions("2.1")
    run_meta(slot, Source(b"new"), "upgrade", edition=editions)
    assert editions.calls == 1  # compared with the local version AND labelled


@pytest.mark.parametrize(
    ("local", "current", "status", "label"),
    [
        (None, "2.0", "missing", "2.0"),
        ("2.0", "2.0", "current", "2.0"),
        ("2.0", "2.1", "newer", "2.1"),
        ("2.0", FAIL, "check_failed", None),
        ("downloaded", "2.0", "unverifiable", "2.0"),
    ],
)
def test_inspect_version_metadata_statuses(tmp_path, local, current, status, label):
    slot = make_slot(tmp_path)
    if local == "downloaded":
        seed(slot, signal=None)
    elif local is not None:
        seed_meta(slot, local)
    item = inspect_version(
        slot, track="landcover", unit="u", signal="metadata", edition=Editions(current)
    )
    assert (item.status, item.available_label) == (status, label)
    if label is not None:
        assert item.available_signal == {"edition": label}
    if status == "check_failed":
        assert "503" in (item.error or "")


def test_inspect_version_metadata_requires_edition(tmp_path):
    with pytest.raises(ValidationError):
        inspect_version(
            make_slot(tmp_path), track="landcover", unit="u", signal="metadata"
        )


def test_none_channel_headers_are_not_a_signal(tmp_path):
    """Plan 3/3 decision 4: headers of a ``none`` channel never relabel."""
    slot = make_slot(tmp_path)
    day1 = v.VersionRef.downloaded(datetime(2026, 10, 1, tzinfo=UTC))
    day2 = v.VersionRef.downloaded(datetime(2026, 10, 2, tzinfo=UTC))
    for ref, length in ((day1, 10), (day2, 11)):
        result = fetch_version(
            slot,
            "force",
            signal="none",
            fetch=Source(b"abc", {"content_length": length}).fetch,
            version=ref,
            write_sidecar=write_sidecar,
        )
    assert (result.status, result.label) == ("unchanged", "2026-10-01")
    assert len(v.list_versions(slot.versions_root, NAME)) == 1


def test_store_file_equals_fetch_version_tail(tmp_path):
    """``use_local`` + ``store_file`` give the same version as ``fetch_version``."""
    a, b = make_slot(tmp_path / "a"), make_slot(tmp_path / "b")
    ref = v.VersionRef("2026-10-12", "downloaded")
    via_fetch = fetch_version(
        a,
        None,
        signal="http",
        fetch=Source(b"abc", E1).fetch,
        version=ref,
        write_sidecar=write_sidecar,
    )
    assert use_local(b, None, signal="http") is None
    staged = new_staging(b)
    staged.write_bytes(b"abc")
    via_store = store_file(
        b, staged, version=ref, write_sidecar=write_sidecar, http=E1, signal="http"
    )
    assert (via_store.status, via_store.label, via_store.sha256) == (
        via_fetch.status,
        via_fetch.label,
        via_fetch.sha256,
    )
    assert via_store.version_path.relative_to(tmp_path / "b") == (
        via_fetch.version_path.relative_to(tmp_path / "a")
    )
    assert json.loads(Path(f"{via_store.version_path}.meta.json").read_text()) == (
        json.loads(Path(f"{via_fetch.version_path}.meta.json").read_text())
    )
    assert not any((b.versions_base / v.INCOMING_DIR).iterdir())
    assert use_local(b, None, signal="http") is not None


@pytest.mark.parametrize(
    ("signal", "with_version", "with_edition"),
    [
        ("metadata", True, True),
        ("metadata", True, False),
        ("metadata", False, False),
        ("http", False, True),
        ("none", True, True),
        ("none", False, False),
    ],
)
def test_fetch_version_rejects_version_and_edition_mix(
    tmp_path, signal, with_version, with_edition
):
    src = Source()
    with pytest.raises(ValidationError):
        fetch_version(
            make_slot(tmp_path),
            None,
            signal=signal,
            fetch=src.fetch,
            write_sidecar=write_sidecar,
            version=v.VersionRef("x", "downloaded") if with_version else None,
            edition=Editions("2.0") if with_edition else None,
        )
    assert src.downloads == 0
