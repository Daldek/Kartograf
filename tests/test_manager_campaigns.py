"""
The ``DownloadManager`` campaign path (ADR-030) on the version store (spec 3):
campaign versions in ``versions/``, the standard path link, the mandatory
version sidecar, returned ``DownloadResult`` and ``VersionedFile`` outcomes.

Records: real ``SkorowidzRecord`` objects from raw index (skorowidz) responses
(``tests/fixtures/gugik_skorowidz/real_2026_10_06/nmt``): C14
(N-34-139-C-a-3-1..4) and N-33-69-A-d-3-2 (campaign 72675 with a ``.xyz`` URL).
The provider is a mock with no network (``FakeCampaignProvider``); the record
cache tests run a real ``GugikProvider`` on a recorded WFS index answer
(``test_campaigns_flow.recorded_session``).
"""

import dataclasses
import errno
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.campaigns import in_year_range, record_year
from kartograf.download.links import linked_version, update_sidecar_extra
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.exceptions import (
    DownloadError,
    NoCoverageError,
    ValidationError,
    YearRangeError,
)
from kartograf.notices import NEWER_AVAILABLE, UNVERIFIED_LOCAL, Notice
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.skorowidz import parse_skorowidz_records
from kartograf.transport.http import get_with_retry

FIXTURES = Path(__file__).parent / "fixtures"
NMT = FIXTURES / "gugik_skorowidz" / "real_2026_10_06" / "nmt"
XYZ_HEAD = (
    FIXTURES / "gugik_asc" / "72675_858113_N-33-69-A-d-3-2.head.xyz"
).read_bytes()

G = "N-34-139-C-a-3-1"
G2 = "N-33-69-A-d-3-2"
SEGMENT = Path("nmt/pl_1992_1m_evrf2007")

ASC_TEMPLATE = (
    "ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n"
    "nodata_value -9999\n{tag}\n"
)


def _filtered(files: list[Path], sheet: str) -> list:
    """Records passing the hard filter (PL-1992, 1 m), newest first."""
    records = []
    for f in files:
        layer = f.stem.rsplit("_", 1)[-1]
        records += [
            r
            for r in parse_skorowidz_records(f.read_text(encoding="utf-8"), layer)
            if r.sheet == sheet and r.system == "1992" and r.resolution_m == 1.0
        ]
    return sorted(
        records, key=lambda r: (r.aktualnosc, r.dt_pzgik or "", r.url), reverse=True
    )


def c14_records(sheet: str = G) -> list:
    return _filtered(sorted((NMT / "c14").glob(f"{sheet}_EVRF2007_*.html")), sheet)


C14_ALL = c14_records()
REC = {r.url.rsplit("/", 1)[-1].split("_")[0]: r for r in C14_ALL}
C14 = {"newest": [REC["84183"]], "all": C14_ALL}

X_ALL = _filtered(sorted((NMT / G2).glob("*.body")), G2)
XREC = {r.url.rsplit("/", 1)[-1].split("_")[0]: r for r in X_ALL}


def asc_for(sheet: str, tag_line: str = "", *, shift_x: float = 0.0) -> bytes:
    """ASC header whose extent is the sheet frame (B4), optional tag line."""
    b = SheetParser(sheet).get_bbox()
    return (
        f"ncols {int(b.max_x - b.min_x)}\nnrows {int(b.max_y - b.min_y)}\n"
        f"xllcorner {b.min_x + shift_x}\nyllcorner {b.min_y}\ncellsize 1\n"
        f"nodata_value -9999\n{tag_line}\n"
    ).encode()


def asc_pixels(sheet: str, values: tuple[int, int, int, int]) -> bytes:
    """Small valid AAIGrid inside the real sheet frame, with measurable cells."""
    bbox = SheetParser(sheet).get_bbox()
    cell = min(bbox.max_x - bbox.min_x, bbox.max_y - bbox.min_y) / 2
    return (
        f"ncols 2\nnrows 2\nxllcorner {bbox.min_x}\nyllcorner {bbox.min_y}\n"
        f"cellsize {cell}\nnodata_value -9999\n"
        f"{values[0]} {values[1]}\n{values[2]} {values[3]}\n"
    ).encode()


def tag(record) -> str:
    return record.url.rsplit("/", 1)[-1]


class FakeCampaignProvider(BaseProvider):
    """supports_campaigns MUST be a CLASS attribute == True.

    DownloadManager checks ``is True``; Mock/Mock(spec=...) give a Mock ->
    plain path.
    """

    supports_campaigns = True
    descriptor_key = "pl.gugik.nmt_1m"
    vertical_crs = "EVRF2007"
    default_extension = ".asc"
    name = "fake"
    base_url = "https://wms"

    def download(self, sheet: str, output_path: Path, timeout: int = 30) -> Path:
        """Campaign providers download through download_record()."""
        raise NotImplementedError("FakeCampaignProvider: tor kampanii")

    def __init__(
        self, records_by_strategy, fail_urls=(), contents=None, errors=None
    ) -> None:
        self.records = records_by_strategy
        self.fail_urls = set(fail_urls)
        self.contents = dict(contents or {})  # url -> bytes (ASC by default)
        self.version = "v1"
        self.fixed_mtime: float | None = None
        self.downloads: list[str] = []
        self.resolve_calls: list[tuple[str, bool, int | None, int | None]] = []
        self.resolve_error: Exception | None = None  # I-1: index failure
        self.errors: dict[str, Exception] = dict(errors or {})
        self._lock = threading.Lock()  # D-6: number of resolutions per sheet code

    def resolve_campaigns(
        self, sheet, *, all_campaigns=False, min_year=None, max_year=None, timeout=None
    ):
        with self._lock:
            self.resolve_calls.append((sheet, all_campaigns, min_year, max_year))
        if sheet in self.errors:
            raise self.errors[sheet]
        if self.resolve_error is not None:
            raise self.resolve_error
        strategy = "all" if all_campaigns else "newest"
        recs = [
            r
            for r in self.records[strategy]
            if r.sheet == sheet and in_year_range(record_year(r), min_year, max_year)
        ]
        if not recs:
            raise NoCoverageError(f"Brak kampanii {sheet}", sheet=sheet)
        return recs

    def record_source(self, r):
        return r.to_source("https://wms")

    def download_record(self, r, path, timeout=None):
        if r.url in self.fail_urls:
            raise DownloadError("siec", sheet=r.sheet)
        with self._lock:
            self.downloads.append(r.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        if r.url in self.contents:
            path.write_bytes(self.contents[r.url])
        else:
            path.write_bytes(asc_for(r.sheet, f"{self.version} {tag(r)}"))
        if self.fixed_mtime is not None:
            os.utime(path, (self.fixed_mtime, self.fixed_mtime))
        return path


def std_path(tmp_path: Path, sheet: str = G) -> Path:
    parts = sheet.split("-")
    return tmp_path / SEGMENT / "-".join(parts[:2]) / Path(*parts[2:]) / f"{sheet}.asc"


def campaign_path(tmp_path: Path, record, sheet: str = G) -> Path:
    """The only version file of the record's campaign (``<date>_<id>_<sha8>``).

    No version = a path that does not exist.
    """
    parts = sheet.split("-")
    dirname = f"{record.aktualnosc}_{tag(record).split('_')[0]}"
    root = tmp_path / SEGMENT / "versions" / "-".join(parts[:2]) / Path(*parts[2:])
    found = list(root.glob(f"{dirname}_????????/{sheet}.asc"))
    assert len(found) <= 1, found
    return found[0] if found else root / f"{dirname}_missing" / f"{sheet}.asc"


def sidecar(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def meta(path: Path) -> dict:
    return json.loads(sidecar(path).read_text(encoding="utf-8"))


def linked(path: Path) -> str:
    """Version file per the standard sidecar (the only source of the target)."""
    return str(linked_version(path))


def hardlinked(path: Path) -> bool:
    """The standard path is a hard link (not a symlink) to its version."""
    target = linked_version(path)
    return (
        target is not None
        and not path.is_symlink()
        and os.path.samefile(path, target)
        and os.stat(path).st_nlink == 2
    )


def labels(root: Path) -> list[str]:
    """Sorted campaign labels of the version directories under ``root``."""
    return sorted(
        {
            d.name.rsplit("_", 1)[0]
            for d in (root / SEGMENT / "versions").rglob("*_????????")
            if d.is_dir()
        }
    )


def deny_links(monkeypatch):
    def denied(*args, **kwargs):
        raise OSError(errno.EPERM, "brak uprawnien")

    monkeypatch.setattr(os, "link", denied)


_REAL_SYMLINK = os.symlink  # user interference in the test (sidecar)


@pytest.fixture(autouse=True)
def no_symlinks(monkeypatch):
    """ADR-030 errata 4: the manager flow never creates a symlink."""

    def forbidden(*args, **kwargs):
        raise AssertionError("os.symlink wywolane w przeplywie kampanii")

    monkeypatch.setattr(os, "symlink", forbidden)


# =============================================================================
# newest
# =============================================================================


def test_newest_downloads_into_versions_and_links(tmp_path):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    result = m.download_sheet(G)
    path = result.succeeded[0]
    assert (
        path
        == tmp_path / "nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc"
    )
    version = campaign_path(tmp_path, REC["84183"])
    assert hardlinked(path) and linked(path) == str(version)
    assert "versions/N-34/139/C/a/3/1/2025-10-21_84183_" in str(version)
    data = json.loads((path.parent / (path.name + ".meta.json")).read_text())
    assert data["extra"]["link"] == "hardlink"
    assert data["extra"]["campaign"]["id"] == "84183"
    assert data["extra"]["version"] == {
        "label": "2025-10-21_84183",
        "label_source": "campaign",
    }
    assert data["request"] == {"sheet": G, "campaigns": "newest"}
    assert version.parent.name.endswith(meta(version)["sha256"][:8])
    assert result.new == [G]
    assert result.files[G][0].status == "new"
    assert result.files[G][0].label == "2025-10-21_84183"
    assert result.files[G][0].version_path == version
    assert not any((tmp_path / SEGMENT / "versions" / ".incoming").iterdir())


def test_rerun_newest_existing_campaign_no_download_skipped(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    result = m.download_sheet(G)
    path = result.files[G][0].path
    assert fake.downloads == [REC["84183"].url]
    assert result.skipped == [G] and result.local == [G]
    assert result.files[G][0].status == "local"
    assert result.files[G][0].version_path == campaign_path(tmp_path, REC["84183"])
    assert hardlinked(path) and "2025-10-21_84183" in linked(path)


def test_existing_standard_file_is_not_a_reason_to_skip(tmp_path):
    std = std_path(tmp_path)
    std.parent.mkdir(parents=True)
    std.write_text(ASC_TEMPLATE.format(tag="stary"))
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert hardlinked(std)
    assert result.new == [G]


def test_legacy_regular_file_replaced_by_link(tmp_path):
    std = std_path(tmp_path)
    std.parent.mkdir(parents=True)
    std.write_text(ASC_TEMPLATE.format(tag="stary"))
    sidecar(std).write_text(
        json.dumps({"extra": {"parent_requests": [{"bbox": [1, 2, 3, 4]}]}})
    )
    DownloadManager(tmp_path, provider=FakeCampaignProvider(C14)).download_sheet(G)
    assert hardlinked(std)
    assert linked(std) == str(campaign_path(tmp_path, REC["84183"]))
    data = meta(std)
    assert data["extra"]["campaign"]["id"] == "84183"
    assert "parent_requests" not in data["extra"]
    assert not sidecar(std).is_symlink()


def test_legacy_kampanie_files_are_not_versions(tmp_path):
    """0.7.x ``kampanie/`` is never read: the campaign is downloaded again."""
    old = tmp_path / SEGMENT / "kampanie" / "2025-10-21_84183" / "N-34" / f"{G}.asc"
    old.parent.mkdir(parents=True)
    old.write_text("stary")
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert m.storage.has_legacy_campaigns()
    assert old.read_text() == "stary"


def test_newer_campaign_reported_by_default_downloaded_by_upgrade(tmp_path):
    """D5: the default mode keeps the local version and reports the newer
    campaign; ``upgrade`` downloads it and moves the link."""
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    assert "2025-04-27_83233" in linked(std)
    fake.records = {"newest": [REC["84183"]]}
    result = m.download_sheet(G)
    assert fake.downloads == [REC["83233"].url]
    assert result.local == [G] and result.skipped == [G]
    assert result.newer == {G: "2025-10-21_84183"}
    assert result.files[G][0].status == "local"
    assert "2025-04-27_83233" in linked(std)
    upgraded = m.download_sheet(G, update="upgrade")
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]
    assert upgraded.new == [G] and upgraded.newer == {}
    assert "2025-10-21_84183" in linked(std)
    assert campaign_path(tmp_path, REC["83233"]).is_file()
    assert meta(std)["extra"]["campaign"]["id"] == "84183"


def test_newer_and_unverified_become_notices(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    received = []
    manager = DownloadManager(tmp_path, provider=fake, on_notice=received.append)
    initial = manager.download_sheet(G)
    assert initial.notices == () and received == []
    fake.records = {"newest": [REC["84183"]]}
    newer = manager.download_sheet(G)
    assert newer.newer == {G: "2025-10-21_84183"}
    assert newer.notices == (
        Notice(
            "info",
            NEWER_AVAILABLE,
            f"dostepna nowsza kampania dla 1 arkuszy ({G}) - "
            "uzyto lokalnych wersji; pobierz: --upgrade",
        ),
    )
    assert received == list(newer.notices)

    received.clear()
    fake.resolve_error = _transport_error(G, 503)
    unverified = manager.download_sheet(G)
    assert G in unverified.unverified
    assert unverified.notices == (
        Notice(
            "warning",
            UNVERIFIED_LOCAL,
            f"{G}: skorowidz GUGiK niedostepny - uzyto lokalnej "
            "wersji bez sprawdzenia nowszej "
            f"({unverified.unverified[G]})",
        ),
    )
    assert received == list(unverified.notices)


def test_upgrade_with_newest_local_downloads_nothing(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    result = m.download_sheet(G, update="upgrade")
    assert fake.downloads == [REC["84183"].url]
    assert result.local == [G] and result.newer == {}


def test_stale_record_older_than_local_is_not_newer(tmp_path):
    """A record older than the kept local version is no "newer" campaign."""
    fake = FakeCampaignProvider({"newest": [REC["84183"]]})
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.records = {"newest": [REC["78047"]]}  # stale record cache
    result = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert result.newer == {} and "84183" in linked(std_path(tmp_path))


def test_check_mode_rejected_in_download_methods(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    for call in (
        lambda: m.download_sheet(G, update="check"),
        lambda: m.download_sheets([G], update="check"),
        lambda: m.download_hierarchy("N-34-139-C-a-3", "1:10000", update="check"),
    ):
        with pytest.raises(ValidationError):
            call()
    with pytest.raises(ValidationError):
        m.download_sheet(G, update="refresh")  # type: ignore[arg-type]
    assert fake.downloads == []
    assert not std_path(tmp_path).exists()


# =============================================================================
# all
# =============================================================================


def test_all_downloads_every_campaign_links_newest(tmp_path):
    # list from the oldest: the link must follow sort_key, not download order
    fake = FakeCampaignProvider({"all": list(reversed(C14_ALL))})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G])
    assert labels(tmp_path) == [
        "2019-04-18_73021",
        "2023-09-05_78047",
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    assert "2025-10-21_84183" in linked(std_path(tmp_path))
    assert len(result.files[G]) == 4
    assert result.succeeded == [std_path(tmp_path)]


def test_all_skips_existing_campaigns_individually(tmp_path):
    fake = FakeCampaignProvider({"all": [REC["84183"], REC["83233"]]})
    DownloadManager(tmp_path, provider=fake, all_campaigns=True).download_sheets([G])
    fake.records = C14
    fake.downloads.clear()
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G])
    assert sorted(fake.downloads) == sorted([REC["78047"].url, REC["73021"].url])
    assert len(result.files[G]) == 4


def test_all_reused_campaign_files_lists_only_local_ones(tmp_path):
    """Already local campaigns remain identifiable in returned file outcomes."""
    fake = FakeCampaignProvider({"all": [REC["84183"], REC["83233"]]})
    first = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    first_result = first.download_sheets([G])
    assert all(f.status == "new" for f in first_result.files[G])
    fake.records = C14
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G])
    reused = tuple(f.version_path for f in result.files[G] if f.status == "local")
    assert sorted(reused) == sorted(
        campaign_path(tmp_path, REC[k]) for k in ("84183", "83233")
    )
    assert len(result.files[G]) == 4


def test_all_min_year_filters(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True, min_year=2025)
    m.download_sheets([G])
    assert labels(tmp_path) == ["2025-04-27_83233", "2025-10-21_84183"]
    assert meta(campaign_path(tmp_path, REC["83233"]))["request"] == {
        "sheet": G,
        "campaigns": "all",
        "min_year": 2025,
    }


def test_newest_after_all_keeps_link_on_newer_local_campaign(tmp_path):
    DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), all_campaigns=True
    ).download_sheets([G])
    stale = FakeCampaignProvider({"newest": [REC["83233"]]})  # stale record_cache
    m = DownloadManager(tmp_path, provider=stale)
    result = m.download_sheet(G)
    path = result.files[G][0].path
    assert stale.downloads == []
    assert "2025-10-21_84183" in linked(path)
    assert result.skipped == [G] and result.files[G][0].status == "local"


def test_all_partial_campaign_failure_is_hard_failure_but_links_best_local(tmp_path):
    fake = FakeCampaignProvider(C14, fail_urls={REC["84183"].url})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True, workers=2)
    result = m.download_sheets([G])
    assert result.failed == [G]
    assert result.no_coverage == []
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    for key in ("83233", "78047", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()
    assert not campaign_path(tmp_path, REC["84183"]).exists()


def test_removed_version_dir_redownloads_newest(tmp_path):
    """The hard link survives removal of the version directory, but
    ``extra.link_target`` does not exist - ``newest`` downloads again."""
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    shutil.rmtree(campaign_path(tmp_path, REC["84183"]).parent)
    assert std.is_file() and linked_version(std) is None
    result = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url] * 2
    assert hardlinked(std)
    assert linked(std) == str(campaign_path(tmp_path, REC["84183"]))
    assert result.new == [G] and result.files[G][0].status == "new"


def test_force_redownloads_all_campaigns_same_content_unchanged(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    m.download_sheets([G])
    fake.downloads.clear()
    result = m.download_sheets([G], update="force")
    assert sorted(fake.downloads) == sorted(r.url for r in C14_ALL)
    assert "2025-10-21_84183" in linked(std_path(tmp_path))
    assert result.succeeded == [std_path(tmp_path)]
    assert result.unchanged == [G]
    assert len(list((tmp_path / SEGMENT / "versions").rglob(f"{G}.asc"))) == 4


def test_force_changed_content_same_campaign_new_version_and_relink(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    first = campaign_path(tmp_path, REC["84183"])
    fake.version = "v2"  # same size, other bytes
    result = m.download_sheet(G, update="force")
    versions = list(first.parent.parent.glob(f"2025-10-21_84183_*/{G}.asc"))
    (second,) = [v for v in versions if v != first]
    assert "v1" in first.read_text() and "v2" in second.read_text()  # old kept
    assert "v2" in std.read_text() and linked(std) == str(second)
    assert result.new == [G] and result.files[G][0].status == "new"


def test_no_hardlink_support_is_sheet_failure_without_version(tmp_path, monkeypatch):
    deny_links(monkeypatch)
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    result = m.download_sheets([G])
    assert result.failed == [G]
    assert not std_path(tmp_path).exists()
    assert labels(tmp_path) == []


def test_reuse_never_changes_version_or_link_sidecar_parent_request(tmp_path):
    """D12: ``extra.parent_requests`` is gone; ``parent_request`` is the
    request that CREATED the version."""
    r1, r2 = {"bbox": [1, 2, 3, 4]}, {"bbox": [5, 6, 7, 8]}
    fake = FakeCampaignProvider(C14)
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r1}
    ).download_sheets([G])
    version_side = sidecar(campaign_path(tmp_path, REC["84183"]))
    before = version_side.read_bytes()
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r2}
    ).download_sheets([G])
    assert version_side.read_bytes() == before
    for data in (meta(campaign_path(tmp_path, REC["84183"])), meta(std_path(tmp_path))):
        assert data["extra"]["parent_request"] == r1
        assert "parent_requests" not in data["extra"]


def test_campaign_sidecar_source_matches_its_own_record(tmp_path):
    m = DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), all_campaigns=True
    )
    m.download_sheets([G])
    for record in C14_ALL:
        data = meta(campaign_path(tmp_path, record))
        assert data["extra"]["source"]["url"] == record.url
        assert data["extra"]["campaign"]["date"] == record.aktualnosc
        assert data["extra"]["source"]["index_url"] == "https://wms"


# =============================================================================
# file format (errata 2 N-2)
# =============================================================================


def test_real_xyz_72675_saved_as_asc_and_linked(tmp_path):
    x = XREC["72675"]
    fake = FakeCampaignProvider({"newest": [x]}, contents={x.url: XYZ_HEAD})
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheet(G2)
    path = result.succeeded[0]
    assert path == std_path(tmp_path, G2) and path.exists()
    assert linked(path).endswith(
        "versions/N-33/69/A/d/3/2/"
        f"2019-04-29_72675_{meta(path)['sha256'][:8]}/N-33-69-A-d-3-2.asc"
    )
    assert list(tmp_path.rglob("*.xyz")) == []
    data = meta(campaign_path(tmp_path, x, G2))
    assert data["extra"]["source"]["url"].endswith(".xyz")


def test_all_with_real_xyz_72675_links_newest(tmp_path):
    x = XREC["72675"]
    assert [tag(r).split("_")[0] for r in X_ALL] == [
        "81025",
        "81616",
        "75506",
        "74160",
        "72675",
    ]
    fake = FakeCampaignProvider({"all": X_ALL}, contents={x.url: XYZ_HEAD})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G2])
    assert len(list((tmp_path / SEGMENT / "versions").rglob("*.asc"))) == 5
    assert "2024-09-23_81025" in linked(std_path(tmp_path, G2))
    assert result.failed == [] and len(result.files[G2]) == 5


def test_unknown_format_fails_before_file_download(tmp_path):
    x = XREC["72675"]
    bad = dataclasses.replace(x, raw={**x.raw, "format": "XYZ ASCII"})
    fake = FakeCampaignProvider({"newest": [REC["84183"], bad]})
    m = DownloadManager(tmp_path, provider=fake)
    previous = m.download_sheet(G)
    assert previous.files[G][0].status == "new"
    with pytest.raises(DownloadError, match="'XYZ ASCII'"):
        m.download_sheet(G2)
    assert fake.downloads == [REC["84183"].url]
    std = std_path(tmp_path, G2)
    assert not std.exists() and not std.is_symlink()
    assert labels(tmp_path) == ["2025-10-21_84183"]


def test_content_mismatch_removes_file_and_fails(tmp_path):
    old, new = XREC["75506"], XREC["81025"]
    fake = FakeCampaignProvider(
        {"newest": [old]}, contents={new.url: b"<html>404</html>"}
    )
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G2).succeeded[0]
    fake.records = {"newest": [new]}
    with pytest.raises(DownloadError, match="tresc nie jest"):
        m.download_sheet(G2, update="upgrade")
    bad = campaign_path(tmp_path, new, G2)
    assert not bad.exists() and not sidecar(bad).exists()
    assert "2022-03-20_75506" in linked(std)


def test_record_url_without_sheet_fails_before_download(tmp_path):
    """B4: a record URL that does not name the sheet is never downloaded."""
    bad = dataclasses.replace(REC["84183"], url="https://x/NMT/84183/84183_1_G.asc")
    fake = FakeCampaignProvider({"newest": [bad]})
    m = DownloadManager(tmp_path, provider=fake)
    with pytest.raises(DownloadError, match="nie zawiera godla"):
        m.download_sheet(G)
    assert fake.downloads == []


def test_neighbour_extent_removes_campaign_file(tmp_path):
    """B4: a file whose header lies outside the sheet frame is rejected."""
    rec = REC["84183"]
    b = SheetParser(G).get_bbox()
    fake = FakeCampaignProvider(
        {"newest": [rec]}, contents={rec.url: asc_for(G, shift_x=b.max_x - b.min_x)}
    )
    m = DownloadManager(tmp_path, provider=fake)
    with pytest.raises(DownloadError, match="zasieg"):
        m.download_sheet(G)
    bad = campaign_path(tmp_path, rec)
    assert not bad.exists() and not sidecar(bad).exists()


def test_all_content_mismatch_on_newest_links_previous(tmp_path):
    fake = FakeCampaignProvider(C14, contents={REC["84183"].url: b"<html>404</html>"})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G])
    assert result.failed == [G]
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    assert not campaign_path(tmp_path, REC["84183"]).exists()


def test_cache_entry_without_format_uses_default_and_verifies(tmp_path):
    r = REC["84183"]
    no_format = dataclasses.replace(
        r, raw={k: v for k, v in r.raw.items() if k != "format"}
    )
    fake = FakeCampaignProvider({"newest": [no_format]})
    from kartograf.download import manager as manager_module

    with patch.object(
        manager_module,
        "verify_file_format",
        wraps=manager_module.verify_file_format,
    ) as verify:
        DownloadManager(tmp_path, provider=fake).download_sheet(G)
    target = campaign_path(tmp_path, r)
    verify.assert_called_once()
    assert verify.call_args.args[1] == ".asc"  # staged file, before the commit
    assert target.is_file()


# =============================================================================
# mandatory campaign sidecar (errata 2 N-1)
# =============================================================================


def test_campaign_sidecar_failure_removes_data_and_keeps_link(tmp_path, monkeypatch):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    before = sidecar(std).read_bytes()

    def broken(*args, **kwargs):
        raise OSError("dysk pelny")

    monkeypatch.setattr("kartograf.sources.sidecar.build_metadata", broken)
    fake.records = {"newest": [REC["84183"]]}
    with pytest.raises(DownloadError, match="obowiazkowego sidecara"):
        m.download_sheet(G, update="upgrade")
    assert not campaign_path(tmp_path, REC["84183"]).exists()
    assert "2025-04-27_83233" in linked(std)
    assert sidecar(std).read_bytes() == before


def test_all_campaign_sidecar_failure_is_partial_failure(tmp_path, monkeypatch):
    from kartograf.sources import sidecar as sidecar_module

    original = sidecar_module.build_metadata

    def flaky(*args, **kwargs):
        if "84183" in str(kwargs.get("data_path")):
            raise OSError("dysk pelny")
        return original(*args, **kwargs)

    monkeypatch.setattr(sidecar_module, "build_metadata", flaky)
    m = DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), all_campaigns=True
    )
    result = m.download_sheets([G])
    assert result.failed == [G]
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    assert not campaign_path(tmp_path, REC["84183"]).exists()
    for key in ("83233", "78047", "73021"):
        assert sidecar(campaign_path(tmp_path, REC[key])).is_file()


def test_version_without_sidecar_is_redownloaded_and_repaired(tmp_path):
    """D18: a version without its sidecar is invalid; the next commit of the
    same content repairs it in place (sha256 checked)."""
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    target = campaign_path(tmp_path, REC["84183"])
    sidecar(target).unlink()
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url] * 2
    assert campaign_path(tmp_path, REC["84183"]) == target
    assert meta(target)["extra"]["campaign"]["id"] == "84183"
    assert hardlinked(std) and linked(std) == str(target)


def _mock_provider(tmp_payload: bytes = b"ncols 1\n") -> Mock:
    p = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
    type(p).default_extension = PropertyMock(return_value=".asc")
    type(p).descriptor_key = PropertyMock(return_value="pl.gugik.nmt_1m")
    type(p).vertical_crs = PropertyMock(return_value="EVRF2007")
    p.name = "mock"

    def download(sheet, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tmp_payload)
        return path

    p.download.side_effect = download
    p.source_info.return_value = None
    return p


def test_plain_track_sidecar_failure_fails_sheet_without_version(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("dysk pelny")

    monkeypatch.setattr("kartograf.sources.sidecar.build_metadata", broken)
    m = DownloadManager(tmp_path, provider=_mock_provider())
    with pytest.raises(DownloadError, match="obowiazkowego sidecara"):
        m.download_sheet(G)
    assert not std_path(tmp_path).exists()
    assert list((tmp_path / SEGMENT / "versions").rglob(f"{G}.asc")) == []


# =============================================================================
# sheet list, parallelism, logs
# =============================================================================


def c14_fake(**kwargs):
    """All four C14 sheets from raw index bodies, including their newest records."""
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    records = [r for g in sheets for r in c14_records(g)]
    return FakeCampaignProvider(
        {"all": records, "newest": [c14_records(g)[0] for g in sheets]}, **kwargs
    )


def test_manager_min_year_alone_conflict_is_error_not_skip(tmp_path):
    fake = c14_fake()
    manager = DownloadManager(tmp_path, provider=fake, min_year=2026)
    with pytest.raises(YearRangeError) as exc:
        manager.download_sheets([f"N-34-139-C-a-3-{i}" for i in range(1, 5)])
    assert set(exc.value.sheets) == {G, "N-34-139-C-a-3-3"}
    assert any("--min-year 2025" in hint for hint in exc.value.hints)
    assert not fake.downloads
    assert not list(tmp_path.rglob("*.asc"))


def test_manager_year_2024_list_stops_before_any_download(tmp_path):
    fake = c14_fake()
    manager = DownloadManager(tmp_path, provider=fake, min_year=2024, max_year=2024)
    with pytest.raises(YearRangeError) as exc:
        manager.download_sheets([f"N-34-139-C-a-3-{i}" for i in range(1, 5)])
    assert set(exc.value.sheets) == {G, "N-34-139-C-a-3-3"}
    assert exc.value.sheets[G] == (2019, 2023, 2025)
    assert not fake.downloads
    assert not list(tmp_path.rglob("*.asc"))


@pytest.mark.parametrize(("all_campaigns", "files"), [(False, 4), (True, 10)])
def test_manager_year_2025_list_flights_per_sheet_link_newest(
    tmp_path, all_campaigns, files
):
    """Year bounds pick admissible years; the switch controls flight count."""
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(
        tmp_path,
        provider=fake,
        all_campaigns=all_campaigns,
        min_year=2025,
        max_year=2025,
    )
    result = manager.download_sheets(sheets)
    assert manager.all_campaigns is all_campaigns and manager.max_year == 2025
    assert len(fake.downloads) == files
    assert len(list((tmp_path / SEGMENT / "versions").rglob("*.asc"))) == files
    for g in sheets:
        assert "84183" in linked(std_path(tmp_path, g))
        request = meta(std_path(tmp_path, g))["request"]
        assert request["campaigns"] == ("all" if all_campaigns else "newest")
        assert request["year"] == 2025
        assert request["min_year"] == request["max_year"] == 2025
        assert meta(std_path(tmp_path, g))["extra"]["available_years"] == sorted(
            {record_year(r) for r in c14_records(g)}
        )
    assert result.link_outside_range == {}


@pytest.mark.parametrize(("all_campaigns", "files"), [(False, 4), (True, 6)])
def test_manager_max_year_2022_list(tmp_path, all_campaigns, files):
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=all_campaigns, max_year=2022
    )
    manager.download_sheets(sheets)
    assert len(fake.downloads) == files
    for i, g in enumerate(sheets, 1):
        assert ("73021" if i in (1, 3) else "75162") in linked(std_path(tmp_path, g))
        assert meta(std_path(tmp_path, g))["request"]["max_year"] == 2022


def test_manager_min_year_alone_downloads_newest_only(tmp_path):
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(tmp_path, provider=fake, min_year=2024)
    manager.download_sheets(sheets)
    assert manager.all_campaigns is False and len(fake.downloads) == 4
    for i, g in enumerate(sheets, 1):
        assert ("84183" if i in (1, 3) else "83998") in linked(std_path(tmp_path, g))
        assert meta(std_path(tmp_path, g))["request"]["campaigns"] == "newest"


def test_year_equals_min_max(tmp_path):
    fake = c14_fake()
    result = DownloadManager(
        tmp_path, provider=fake, year=2025, all_campaigns=True
    ).download_sheet(G)
    assert {f.label for f in result.files[G]} == {
        "2025-04-27_83233",
        "2025-10-21_84183",
    }
    request = meta(std_path(tmp_path))["request"]
    assert request["year"] == request["min_year"] == request["max_year"] == 2025
    assert all(record_year(r) == 2025 for r in C14_ALL if r.url in fake.downloads)


@pytest.mark.parametrize("bound", ["min_year", "max_year"])
def test_year_with_min_year_is_validation_error(tmp_path, bound):
    with pytest.raises(ValidationError) as exc:
        DownloadManager(tmp_path, provider=c14_fake(), year=2025, **{bound: 2024})
    assert str(exc.value) == (
        "--year wyklucza sie z --min-year/--max-year "
        "(--year Y to skrot --min-year Y --max-year Y)"
    )


def test_manager_explicit_all_with_min_year_downloads_every_flight(tmp_path):
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(
        tmp_path, provider=fake, min_year=2024, all_campaigns=True
    )
    manager.download_sheets(sheets)
    assert len(fake.downloads) == 14
    assert all(
        meta(std_path(tmp_path, g))["request"]["campaigns"] == "all" for g in sheets
    )


def test_manager_range_reports_link_kept_on_newer_flight(tmp_path):
    """U15: the link never moves back; a ranged request reports the kept target."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    newest = campaign_path(tmp_path, REC["84183"])
    manager = DownloadManager(tmp_path, provider=fake, max_year=2022)
    ranged = manager.download_sheet(G)
    assert campaign_path(tmp_path, REC["73021"]).exists()
    assert "84183" in linked(std_path(tmp_path))
    assert ranged.link_outside_range[G].resolve() == newest.resolve()
    assert ranged.files[G][0].version_path == campaign_path(tmp_path, REC["73021"])
    # a range that selects the linked flight reports nothing
    within = DownloadManager(tmp_path, provider=fake, min_year=2025)
    selected = within.download_sheet(G)
    assert selected.link_outside_range == {}


def test_manager_year_with_no_data_sheet_is_skipped(tmp_path):
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(tmp_path, provider=fake, min_year=2025, max_year=2025)
    result = manager.download_sheets([*sheets, G2])
    assert result.no_coverage == [G2]
    assert G2 not in result.files
    assert len(fake.downloads) == 4


def test_manager_check_failure_aborts_whole_task(tmp_path):
    fake = c14_fake(errors={"N-34-139-C-a-3-4": DownloadError("blad sieci")})
    manager = DownloadManager(tmp_path, provider=fake, min_year=2025, max_year=2025)
    with pytest.raises(DownloadError, match="N-34-139-C-a-3-4") as exc:
        manager.download_sheets([f"N-34-139-C-a-3-{i}" for i in range(1, 5)])
    assert "blad skorowidza" in str(exc.value)
    assert not fake.downloads
    assert not list(tmp_path.rglob("*.asc"))


def test_manager_check_reads_full_list_once_per_sheet(tmp_path):
    fake = c14_fake()
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, max_year=2025, workers=4
    )
    check = manager.check_year_range(sheets)
    assert len(check.selected[G]) == 4
    assert check.available[G] == (2019, 2023, 2025)
    fake.resolve_calls.clear()
    manager.download_sheets(sheets)
    assert sorted(fake.resolve_calls) == [(g, True, None, None) for g in sheets]


def test_manager_without_range_unchanged_uses_record_cache(tmp_path):
    from tests.test_campaigns_flow import G as W
    from tests.test_campaigns_flow import recorded_session

    key = ("pl.gugik.nmt_1m", "1m", "EVRF2007", W)
    cache = MetadataCache(tmp_path / "cache.db")
    provider = GugikProvider(
        session=recorded_session(W),
        cache=cache,
        vertical_crs="EVRF2007",
        resolution="1m",
    )
    manager = DownloadManager(tmp_path, provider=provider)
    manager.download_sheet(W)
    assert cache.get_record(*key) is not None
    assert cache.get_campaigns(*key) is None
    offline = Mock(spec=requests.Session)
    offline.get = Mock(side_effect=requests.ConnectionError("brak indeksu"))
    refresh = MetadataCache(tmp_path / "cache.db", refresh=True)
    manager = DownloadManager(
        tmp_path,
        provider=GugikProvider(
            session=offline, cache=refresh, vertical_crs="EVRF2007", resolution="1m"
        ),
    )
    with patch("kartograf.transport.http.time.sleep"):
        result = manager.download_sheet(W)
    assert W in result.unverified
    assert "80196" in linked(std_path(tmp_path, W))


def test_range_index_down_all_local_uses_local(tmp_path, caplog):
    """D14: every sheet has a local version from the range -> local versions
    with a warning, no download."""
    from tests.test_campaigns_flow import G as W
    from tests.test_campaigns_flow import recorded_session

    cache = MetadataCache(tmp_path / "cache.db")
    DownloadManager(
        tmp_path,
        provider=GugikProvider(
            session=recorded_session(W),
            cache=cache,
            vertical_crs="EVRF2007",
            resolution="1m",
        ),
    ).download_sheet(W)
    offline = Mock(spec=requests.Session)
    offline.get = Mock(side_effect=requests.ConnectionError("brak indeksu"))
    refresh = MetadataCache(tmp_path / "cache.db", refresh=True)
    manager = DownloadManager(
        tmp_path,
        provider=GugikProvider(
            session=offline, cache=refresh, vertical_crs="EVRF2007", resolution="1m"
        ),
        min_year=2024,
    )
    with (
        patch("kartograf.transport.http.time.sleep"),
        caplog.at_level(logging.WARNING, logger="kartograf.download.manager"),
    ):
        result = manager.download_sheet(W)
    assert result.files[W][0].path == std_path(tmp_path, W)
    assert result.local == [W]
    assert result.files[W][0].label == "2024-09-21_80196"
    assert result.files[W][0].unverified
    assert result.unverified.keys() == {W}
    assert "80196" in linked(std_path(tmp_path, W))
    assert len(result.notices) == 1
    assert result.notices[0].code == UNVERIFIED_LOCAL
    assert not any(
        "skorowidz GUGiK niedostepny" in r.getMessage() for r in caplog.records
    )


def test_range_index_down_one_missing_fails_task(tmp_path):
    """D14: one sheet without a local version from the range -> the whole
    task fails before any download."""
    g2 = "N-34-139-C-a-3-2"
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    fake.downloads.clear()
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake, min_year=2024)
    with pytest.raises(DownloadError, match="nie udalo sie sprawdzic"):
        m.download_sheets([G, g2])
    assert fake.downloads == []


@pytest.mark.parametrize("update", ["upgrade", "force"])
def test_range_index_down_upgrade_and_force_fail_task(tmp_path, update):
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake, min_year=2024)
    with pytest.raises(DownloadError, match="nie udalo sie sprawdzic"):
        m.download_sheet(G, update=update)


def test_range_index_down_local_outside_range_fails_task(tmp_path):
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G)  # 2025 flight
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake, max_year=2024)
    with pytest.raises(DownloadError, match="nie udalo sie sprawdzic"):
        m.download_sheet(G)


def test_manager_direct_sheet_conflict_and_no_data_do_not_fetch(tmp_path):
    fake = c14_fake()
    manager = DownloadManager(tmp_path, provider=fake, max_year=2024, min_year=2024)
    with pytest.raises(YearRangeError) as exc:
        manager.download_sheet(G)
    assert exc.value.sheets[G] == (2019, 2023, 2025)
    with pytest.raises(NoCoverageError):
        manager.download_sheet(G2)
    assert not fake.downloads


def test_manager_hierarchy_check_precedes_every_download(tmp_path):
    fake = c14_fake()
    manager = DownloadManager(tmp_path, provider=fake, min_year=2024, max_year=2024)
    with pytest.raises(YearRangeError) as exc:
        manager.download_hierarchy("N-34-139-C-a-3", "1:10000")
    assert G in exc.value.sheets and "N-34-139-C-a-3-3" in exc.value.sheets
    assert not fake.downloads
    assert not list(tmp_path.rglob("*.asc"))


def test_manager_coverage_measured_at_commit_for_partial_flights(tmp_path):
    """D13: every flight not declared full gets ``extra.coverage`` in its
    version sidecar at commit; a declared-full flight is not measured but
    counts as fully covered when looking for a better flight."""
    newest, older = REC["84183"], REC["83233"]
    fake = c14_fake(
        contents={
            newest.url: asc_pixels(G, (7, -9999, -9999, -9999)),
            older.url: asc_pixels(G, (7, 8, 9, 10)),
        }
    )
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2025, max_year=2025
    )
    result = manager.download_sheet(G)
    assert meta(campaign_path(tmp_path, newest))["extra"]["coverage"] == 0.25
    assert "coverage" not in meta(campaign_path(tmp_path, older))["extra"]
    standard = meta(std_path(tmp_path))
    assert standard["extra"]["coverage"] == 0.25  # copied from the version
    assert standard["extra"]["better_coverage"] == "83233"
    assert standard["extra"]["flights"] == [
        {"id": "84183", "date": "2025-10-21", "full_sheet": False, "coverage": 0.25},
        {"id": "83233", "date": "2025-04-27", "full_sheet": True},
    ]
    assert "84183" in linked(std_path(tmp_path))
    assert result.better_coverage == {G: "83233"}

    full = "N-34-139-C-a-3-4"
    manager = DownloadManager(
        tmp_path / "full",
        provider=c14_fake(),
        all_campaigns=True,
        min_year=2025,
        max_year=2025,
    )
    full_result = manager.download_sheet(full)
    full_meta = meta(std_path(tmp_path / "full", full))["extra"]
    assert len(full_meta["flights"]) == 3
    assert all("coverage" not in f for f in full_meta["flights"])
    assert "coverage" not in full_meta and "better_coverage" not in full_meta
    assert full_result.better_coverage == {}


def test_coverage_written_at_commit_for_single_partial_flight(tmp_path):
    fake = c14_fake(
        contents={REC["84183"].url: asc_pixels(G, (1, -9999, -9999, -9999))}
    )
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    assert meta(campaign_path(tmp_path, REC["84183"]))["extra"][
        "coverage"
    ] == pytest.approx(0.25)


def test_manager_coverage_newest_has_more_data_no_info(tmp_path):
    fake = c14_fake(
        contents={
            REC["84183"].url: asc_pixels(G, (1, 2, 3, 4)),
            REC["83233"].url: asc_pixels(G, (1, -9999, -9999, -9999)),
        }
    )
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2025, max_year=2025
    )
    result = manager.download_sheet(G)
    extra = meta(std_path(tmp_path))["extra"]
    assert [flight.get("coverage") for flight in extra["flights"]] == [1.0, None]
    assert "better_coverage" not in extra
    assert result.better_coverage == {}


def test_manager_single_flight_in_range_no_measurement(tmp_path):
    manager = DownloadManager(
        tmp_path, provider=c14_fake(), all_campaigns=True, min_year=2019, max_year=2019
    )
    manager.download_sheet(G)
    extra = meta(std_path(tmp_path))["extra"]
    assert extra["flights"] == [
        {"id": "73021", "date": "2019-04-18", "full_sheet": True}
    ]
    assert "coverage" not in meta(campaign_path(tmp_path, REC["73021"]))["extra"]
    assert "better_coverage" not in extra


def test_manager_coverage_read_from_version_sidecar_on_rerun(tmp_path):
    fake = c14_fake(
        contents={
            REC["84183"].url: asc_pixels(G, (1, -9999, -9999, -9999)),
            REC["83233"].url: asc_pixels(G, (1, 2, 3, 4)),
        }
    )
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2025, max_year=2025
    )
    first = manager.download_sheet(G)
    assert first.better_coverage == {G: "83233"}
    with patch("kartograf.download.manager.read_content") as measure:
        second = manager.download_sheet(G)
    measure.assert_not_called()
    assert second.skipped == [G]
    assert all(f.status == "local" for f in second.files[G])
    assert second.better_coverage == {G: "83233"}
    assert len(fake.downloads) == 2


def test_manager_new_range_clears_obsolete_better_flight_without_relinking(tmp_path):
    fake = c14_fake(
        contents={
            REC["84183"].url: asc_pixels(G, (1, -9999, -9999, -9999)),
            REC["83233"].url: asc_pixels(G, (1, 2, 3, 4)),
        }
    )
    DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2025, max_year=2025
    ).download_sheet(G)
    assert meta(std_path(tmp_path))["extra"]["better_coverage"] == "83233"
    older = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2019, max_year=2019
    )
    older_result = older.download_sheet(G)
    extra = meta(std_path(tmp_path))["extra"]
    assert extra["flights"] == [
        {"id": "73021", "date": "2019-04-18", "full_sheet": True}
    ]
    assert "better_coverage" not in extra
    assert older_result.better_coverage == {}
    assert "84183" in linked(std_path(tmp_path))


def test_update_sidecar_extra_replaces_symlink_without_touching_version(tmp_path):
    manager = DownloadManager(
        tmp_path, provider=c14_fake(), min_year=2019, max_year=2019
    )
    manager.download_sheet(G)
    std = std_path(tmp_path)
    version = campaign_path(tmp_path, REC["73021"])
    original = meta(version)
    sidecar(std).unlink()
    _REAL_SYMLINK(sidecar(version), sidecar(std))
    update_sidecar_extra(std, {"flights": [{"id": "73021"}]})
    assert not sidecar(std).is_symlink()
    assert meta(std)["extra"]["flights"] == [{"id": "73021"}]
    assert meta(version) == original


def test_manager_min_year_alone_lists_no_flights(tmp_path):
    manager = DownloadManager(tmp_path, provider=c14_fake(), min_year=2024)
    result = manager.download_sheet(G)
    assert manager.all_campaigns is False
    assert "flights" not in meta(std_path(tmp_path))["extra"]
    assert result.better_coverage == {}


def test_manager_coverage_read_error_does_not_fail_sheet(tmp_path, caplog):
    fake = c14_fake(contents={REC["83233"].url: asc_pixels(G, (1, 2, 3, 4))})
    manager = DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, min_year=2025, max_year=2025
    )
    with caplog.at_level(logging.WARNING, logger="kartograf.download.versions"):
        result = manager.download_sheet(G)
    assert result.failed == []
    assert "84183" in linked(std_path(tmp_path))
    assert "pokrycia" in caplog.text
    assert "coverage" not in meta(campaign_path(tmp_path, REC["84183"]))["extra"]
    flights = meta(std_path(tmp_path))["extra"]["flights"]
    assert all("coverage" not in flight for flight in flights)
    assert "better_coverage" not in meta(std_path(tmp_path))["extra"]


def test_parallel_all_campaigns_writes_each_file_once(tmp_path):
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    records = [r for g in sheets for r in c14_records(g)]
    fake = FakeCampaignProvider({"all": records})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True, workers=4)
    result = m.download_sheets(sheets)
    assert sorted(fake.downloads) == sorted(r.url for r in records)
    assert result.failed == []
    for g in sheets:
        assert std_path(tmp_path, g).exists()
        assert len(result.files[g]) == len(c14_records(g))


def test_duplicate_sheets_in_list_download_once_and_link_once(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, workers=4)
    result = m.download_sheets([G, G, G])
    assert fake.resolve_calls == [(G, False, None, None)]
    assert fake.downloads == [REC["84183"].url]
    assert result.total == 1 and len(result.files[G]) == 1


def test_campaign_count_logged_at_info(tmp_path, caplog):
    m = DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), all_campaigns=True
    )
    with caplog.at_level(logging.INFO, logger="kartograf.download.manager"):
        m.download_sheets([G])
    assert any(
        r.name == "kartograf.download.manager"
        and r.levelno == logging.INFO
        and G in r.getMessage()
        and "4 kampanii" in r.getMessage()
        for r in caplog.records
    )


def test_sheet_and_list_calls_each_return_complete_result(tmp_path):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    first = m.download_sheet(G)
    second = m.download_sheets([G])
    assert first.new == [G] and first.files[G][0].status == "new"
    assert second.skipped == [G] and second.files[G][0].status == "local"


# =============================================================================
# provider without campaigns (plain path) and validation
# =============================================================================


def test_provider_without_campaigns_versions_by_download_date(tmp_path):
    """Plan 1/3 decision 7: the plain flow stores a ``downloaded`` version."""
    p = _mock_provider()
    m = DownloadManager(tmp_path, provider=p)
    initial = m.download_sheet(G)
    path = initial.succeeded[0]
    assert path == std_path(tmp_path)
    assert path.is_file() and not path.is_symlink()
    target = linked_version(path)
    assert target is not None and os.path.samefile(path, target)
    assert meta(target)["extra"]["version"]["label_source"] == "downloaded"
    assert initial.new == [G]
    assert initial.files[G][0].status == "new"
    assert initial.files[G][0].label == target.parent.name[:10]
    assert initial.files[G][0].version_path == target
    local = m.download_sheet(G)
    assert local.skipped == [G] and local.files[G][0].status == "local"
    assert p.download.call_count == 1
    unchanged = m.download_sheet(G, update="force")
    assert unchanged.unchanged == [G]
    assert unchanged.files[G][0].status == "unchanged"
    assert len(list((tmp_path / SEGMENT / "versions").rglob(f"{G}.asc"))) == 1


def test_provider_without_campaigns_rejects_all_and_min_year(tmp_path):
    with pytest.raises(ValidationError, match="nie obsluguje kampanii"):
        DownloadManager(tmp_path, provider=_mock_provider(), all_campaigns=True)
    with pytest.raises(ValidationError, match="nie obsluguje kampanii"):
        DownloadManager(tmp_path, provider=_mock_provider(), min_year=2024)


def test_spec_mock_is_not_campaign_aware(tmp_path):
    p = Mock(spec=GugikProvider, resolution="1m", vertical_crs="EVRF2007")
    type(p).default_extension = PropertyMock(return_value=".asc")
    m = DownloadManager(tmp_path, provider=p)  # no exception
    assert m.all_campaigns is False and m.min_year is None

    def download(sheet, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ncols 1\n")
        return path

    p.download.side_effect = download
    result = m.download_sheet(G)  # plain path: provider.download, not resolve_campaigns
    path = result.succeeded[0]
    assert p.download.call_count == 1
    assert path.is_file() and not path.is_symlink()


def test_invalid_year_bound(tmp_path):
    with pytest.raises(ValidationError):
        DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), min_year=True)


# =============================================================================
# Fix round 1
# =============================================================================


@pytest.mark.parametrize("to_version", [False, True], ids=["elsewhere", "version"])
def test_symlinked_standard_sidecar_rewritten_without_writing_through(
    tmp_path, to_version
):
    """<std>.meta.json replaced by a user symlink (to a copy elsewhere or to
    the version sidecar): a rerun without download keeps the data link,
    never writes through the symlink and leaves a regular link sidecar."""
    fake = FakeCampaignProvider(C14)
    DownloadManager(tmp_path, provider=fake).download_sheets([G])
    std_side = sidecar(std_path(tmp_path))
    version_side = sidecar(campaign_path(tmp_path, REC["84183"]))
    target = tmp_path / "gdzie_indziej.json"
    target.write_bytes(std_side.read_bytes())
    if to_version:
        target = version_side
    std_side.unlink()
    _REAL_SYMLINK(target, std_side)
    before = target.read_bytes()

    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheets([G])

    assert fake.downloads == [REC["84183"].url]
    assert result.skipped == [G]
    assert target.read_bytes() == before
    assert std_side.is_file() and not std_side.is_symlink()
    assert meta(std_path(tmp_path))["extra"]["link"] == "hardlink"
    assert "link" not in json.loads(version_side.read_text())["extra"]


def _fail_link_for(monkeypatch, sheet: str) -> None:
    """The standard/full link swap of ``sheet`` fails with a disk error."""
    from kartograf.download import links

    real = links.link_atomic

    def link_atomic(target, link):
        if sheet in link.name:
            raise OSError("dysk pelny")
        return real(target, link)

    monkeypatch.setattr(links, "link_atomic", link_atomic)


def test_link_failure_is_sheet_failure_and_list_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R5: a link failure = a sheet failure, not an abort of the list at
    workers=1; the committed version stays."""
    g3 = "N-34-139-C-a-3-2"
    other = c14_records(g3)[0]
    _fail_link_for(monkeypatch, G)
    events: list[DownloadProgress] = []
    fake = FakeCampaignProvider({"newest": [REC["84183"], other]})
    m = DownloadManager(tmp_path, provider=fake, workers=1)
    result = m.download_sheets([G, g3], on_progress=events.append)
    assert result.failed == [G]
    assert result.no_coverage == []
    assert result.succeeded == [std_path(tmp_path, g3)]
    assert campaign_path(tmp_path, REC["84183"]).is_file()
    assert not std_path(tmp_path).exists()
    failed = next(e for e in events if e.sheet == G and e.status == "failed")
    assert "dowiazanie" in failed.message and "dysk pelny" in failed.message


def test_link_failure_reported_together_with_campaign_errors(tmp_path, monkeypatch):
    _fail_link_for(monkeypatch, G)
    fake = FakeCampaignProvider(C14, fail_urls={REC["78047"].url})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    with pytest.raises(DownloadError) as exc:
        m.download_sheet(G)
    assert "2023-09-05_78047" in str(exc.value)
    assert "dowiazanie" in str(exc.value)
    for key in ("84183", "83233", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()


def test_invalid_aktualnosc_is_campaign_failure_links_best_valid(tmp_path):
    """R16 (as Q10): one record's bad acquisition date does not break the loop."""
    bad = dataclasses.replace(REC["84183"], aktualnosc="2025/10/21")
    fake = FakeCampaignProvider({"all": [bad, *C14_ALL[1:]]})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    with pytest.raises(DownloadError, match="84183_1852496") as exc:
        m.download_sheet(G)
    assert "nie pobrano 1 z 4 kampanii" in str(exc.value)
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    for key in ("83233", "78047", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()


# =============================================================================
# I-1: newest on an index transport failure -> local campaign
# =============================================================================


def _transport_error(sheet: str, failure) -> DownloadError:
    """``DownloadError`` exactly from ``get_with_retry`` (retries without waiting).

    ``failure``: a ``session.get`` exception or the HTTP status code of the response.
    """
    session = Mock(spec=requests.Session)
    if isinstance(failure, int):
        response = Mock(spec=requests.Response)
        response.status_code = failure
        response.headers = {}
        response.raise_for_status = Mock(
            side_effect=requests.HTTPError(f"HTTP {failure}", response=response)
        )
        session.get = Mock(return_value=response)
    else:
        session.get = Mock(side_effect=failure)
    with patch("kartograf.transport.http.time.sleep"):
        try:
            get_with_retry(session, "https://wms", timeout=1, description=sheet)
        except DownloadError as e:
            return e
    raise AssertionError("get_with_retry nie zglosil bledu")


TRANSPORT_FAILURES = [
    requests.ConnectionError("brak sieci"),
    requests.Timeout("timeout"),
    503,
    429,
]


@pytest.mark.parametrize(
    "failure", TRANSPORT_FAILURES, ids=["conn", "timeout", "503", "429"]
)
def test_newest_transport_failure_uses_local_campaign(tmp_path, failure, caplog):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    before = linked(std)
    fake.resolve_error = _transport_error(G, failure)
    with caplog.at_level(logging.WARNING, logger="kartograf.download.manager"):
        result = m.download_sheet(G)
    target = campaign_path(tmp_path, REC["84183"])
    assert result.files[G][0].path == std and linked(std) == before
    assert fake.downloads == [REC["84183"].url]
    assert result.skipped == [G]
    fetch = result.files[G][0]
    assert fetch.version_path == target and fetch.status == "local"
    assert fetch.label == "2025-10-21_84183"
    assert fetch.unverified and str(fake.resolve_error) in fetch.unverified
    assert len(result.notices) == 1
    assert result.notices[0].code == UNVERIFIED_LOCAL
    assert not any(
        "skorowidz GUGiK niedostepny" in r.getMessage() for r in caplog.records
    )


def test_newest_transport_failure_in_list_is_skipped_and_reported(
    tmp_path: Path,
) -> None:
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.resolve_error = _transport_error(G, 503)
    events: list[DownloadProgress] = []
    result = m.download_sheets([G], on_progress=events.append)
    assert result.files[G][0].path == std_path(tmp_path)
    assert result.skipped == [G] and result.failed == []
    assert set(result.unverified) == {G}
    assert "503" in result.unverified[G]
    assert events[-1].status == "skipped"


def test_newest_transport_failure_keeps_link_untouched(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    inode = std.stat().st_ino
    (std.parent / f"{std.name}.aux.xml").write_text("<PAMDataset/>")
    fake.resolve_error = _transport_error(G, requests.ConnectionError("x"))
    result = m.download_sheet(G)
    assert std.stat().st_ino == inode
    assert (std.parent / f"{std.name}.aux.xml").exists()
    assert result.local == [G] and result.unverified.keys() == {G}


@pytest.mark.parametrize(
    ("kwargs", "update", "error"),
    [
        # no coverage = a data state, not transport
        ({}, None, NoCoverageError("Brak kampanii", sheet=G)),
        # 4xx without retries and a response-content error are not transport
        ({}, None, "404"),
        ({}, None, DownloadError("raport wyjatku OGC", sheet=G)),
        # only the default mode falls back to the local version
        ({}, "upgrade", "conn"),
        ({"all_campaigns": True}, "force", "conn"),
    ],
    ids=["no-coverage", "http-404", "ogc", "upgrade", "all-force"],
)
def test_resolve_failure_without_fallback_still_fails(tmp_path, kwargs, update, error):
    fake = FakeCampaignProvider(C14)
    DownloadManager(tmp_path, provider=fake, **kwargs).download_sheets([G])
    assert std_path(tmp_path).exists()
    if error == "404":
        error = _transport_error(G, 404)
    elif error == "conn":
        error = _transport_error(G, requests.ConnectionError("x"))
    fake.resolve_error = error
    m = DownloadManager(tmp_path, provider=fake, **kwargs)
    with pytest.raises(type(error)) as exc:
        m.download_sheet(G, update=update)
    assert exc.value is error


def test_all_strategy_transport_failure_uses_local_link_target(tmp_path):
    """I-1 for every strategy (spec 4.2): ``all`` without year bounds."""
    fake = FakeCampaignProvider(C14)
    DownloadManager(tmp_path, provider=fake, all_campaigns=True).download_sheets([G])
    fake.resolve_error = _transport_error(G, requests.ConnectionError("x"))
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheet(G)
    assert result.local == [G] and result.unverified.keys() == {G}
    assert result.files[G][0].label == "2025-10-21_84183"


def test_transport_failure_without_local_campaign_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake)
    with pytest.raises(DownloadError):
        m.download_sheet(G)
    result = m.download_sheets([G])
    assert result.failed == [G] and result.unverified == {}


def test_transport_failure_with_dangling_link_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    campaign_path(tmp_path, REC["84183"]).unlink()
    fake.resolve_error = _transport_error(G, 503)
    with pytest.raises(DownloadError):
        m.download_sheet(G)
    assert std.is_file() and linked_version(std) is None  # untouched


def test_transport_failure_with_force_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.resolve_error = _transport_error(G, 503)
    with pytest.raises(DownloadError):
        m.download_sheet(G, update="force")


# =============================================================================
# D18: a version file without a sidecar is never overwritten
# =============================================================================


def test_corrupted_version_without_sidecar_is_collision_error(tmp_path):
    """The same version directory holding OTHER bytes and no sidecar: the
    commit compares sha256 and fails without touching the file."""
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    target = campaign_path(tmp_path, REC["84183"])
    sidecar(target).unlink()
    std.unlink()  # break the hardlink so the edit touches only the version
    target.write_bytes(b"<html>blad serwera</html>")
    with pytest.raises(DownloadError, match="sha256") as exc:
        m.download_sheet(G)
    assert "2025-10-21_84183" in str(exc.value)
    assert target.read_bytes() == b"<html>blad serwera</html>"
    assert not sidecar(target).exists()
    assert fake.downloads == [REC["84183"].url] * 2


# =============================================================================
# M-6: a re-run without download does not move the link
# =============================================================================


def test_rerun_without_download_does_not_relink(tmp_path: Path) -> None:
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G).succeeded[0]
    assert isinstance(std, Path)
    inode = std.stat().st_ino
    aux = std.parent / f"{std.name}.aux.xml"
    aux.write_text("<PAMDataset/>")
    std_meta = sidecar(std).read_text(encoding="utf-8")
    again = m.download_sheet(G)
    assert std.stat().st_ino == inode
    assert aux.exists()
    assert sidecar(std).read_text(encoding="utf-8") == std_meta
    assert again.skipped == [G] and again.files[G][0].status == "local"
    assert fake.downloads == [REC["84183"].url]


# --- 0.7.1: vertical datum declared by the record ------------------------------

GK = "N-33-59-C-a-1-3"  # raw KRON86 index bodies (C9a), records PL-KRON86-NH
KRN_ALL = _filtered(sorted((NMT / GK).glob("nmt1_krn__*.body")), GK)
SEGMENT_KRON86 = Path("nmt/pl_1992_1m_kron86")


def _without_vertical(record):
    """The record without ``ukladWspolrzednychPionowych`` (cannot be verified)."""
    raw = {k: v for k, v in record.raw.items() if k != "ukladWspolrzednychPionowych"}
    return dataclasses.replace(record, raw=raw)


def test_newest_record_of_other_vertical_crs_fails_before_download(tmp_path):
    """0.7.1, standard path: a KRON86 record served by the EVRF2007 index."""
    rec = KRN_ALL[0]
    fake = FakeCampaignProvider({"newest": [rec]})  # vertical_crs EVRF2007
    m = DownloadManager(tmp_path, provider=fake)
    with pytest.raises(DownloadError) as exc:
        m.download_sheet(GK)
    message = str(exc.value)
    assert GK in message
    assert "deklaruje uklad wysokosci PL-KRON86-NH" in message
    assert "zadano EVRF2007 (oczekiwano PL-EVRF2007-NH)" in message
    assert fake.downloads == []
    assert not (tmp_path / SEGMENT).exists()


def test_all_campaign_of_other_vertical_crs_fails_others_kept(tmp_path):
    """0.7.1, campaign path: the mislabelled campaign fails, the rest is kept."""
    bad = dataclasses.replace(
        REC["78047"],
        raw={**REC["78047"].raw, "ukladWspolrzednychPionowych": "PL-KRON86-NH"},
    )
    records = [bad if r is REC["78047"] else r for r in C14_ALL]
    fake = FakeCampaignProvider({"all": records})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    with pytest.raises(DownloadError, match="nie pobrano 1 z 4 kampanii") as exc:
        m.download_sheet(G)
    assert "2023-09-05_78047" in str(exc.value)
    assert "PL-KRON86-NH" in str(exc.value)
    assert bad.url not in fake.downloads and len(fake.downloads) == 3
    assert not campaign_path(tmp_path, bad).exists()
    assert "2025-10-21_84183" in linked(std_path(tmp_path))


def test_kron86_provider_downloads_real_kron86_record(tmp_path):
    """0.7.1: the record of the queried datum passes (KRON86 segment)."""
    rec = KRN_ALL[0]
    fake = FakeCampaignProvider({"newest": [rec]})
    fake.vertical_crs = "KRON86"
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(GK)
    assert fake.downloads == [rec.url]
    assert (tmp_path / SEGMENT_KRON86).is_dir()


def test_record_without_vertical_field_is_downloaded(tmp_path):
    """0.7.1: no field = cannot verify -> accepted (debug log only)."""
    rec = _without_vertical(REC["84183"])
    fake = FakeCampaignProvider({"newest": [rec]})
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    assert fake.downloads == [rec.url]


# =============================================================================
# full_sheet/: second link to the newest declared-full flight (ADR-033)
# =============================================================================

G4 = "N-34-139-C-a-3-4"


def full_path(tmp_path: Path, sheet: str = G) -> Path:
    parts = sheet.split("-")
    return (
        tmp_path
        / SEGMENT
        / "full_sheet"
        / "-".join(parts[:2])
        / Path(*parts[2:])
        / f"{sheet}.asc"
    )


def _rec_of(sheet: str, flight: str):
    return next(r for r in c14_records(sheet) if tag(r).startswith(f"{flight}_"))


def test_full_link_same_file_when_newest_full(tmp_path):
    """F1: the newest flight is full -> both links share the campaign inode."""
    fake = c14_fake()
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheet(G4)
    newest = _rec_of(G4, "83998")
    camp = campaign_path(tmp_path, newest, G4)
    full = full_path(tmp_path, G4)
    assert fake.downloads == [newest.url]
    assert os.path.samefile(full, camp)
    assert os.path.samefile(full, std_path(tmp_path, G4))
    extra = meta(full)["extra"]
    assert extra["link"] == "hardlink" and extra["campaign"]["full_sheet"] is True
    assert linked_version(full) == camp
    assert result.full_links == {G4: full}
    assert result.files[G4][0].version_path == camp


def test_without_flag_partial_newest_downloads_one_flight(tmp_path):
    """F2: no flag, the newest flight is partial -> one flight, no full_sheet/."""
    fake = c14_fake()
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert {c[1] for c in fake.resolve_calls} == {False}
    assert not full_path(tmp_path).exists()
    assert result.full_links == {}
    assert result.files[G][0].status == "new"


def test_campaigns_all_links_newest_full_flight(tmp_path):
    """F4: ``all`` -> full_sheet/ = newest full flight, standard = newest."""
    m = DownloadManager(tmp_path, provider=c14_fake(), all_campaigns=True)
    result = m.download_sheets([G])
    assert linked_version(full_path(tmp_path)) == campaign_path(tmp_path, REC["83233"])
    assert linked_version(std_path(tmp_path)) == campaign_path(tmp_path, REC["84183"])
    assert result.full_links == {G: full_path(tmp_path)}


def test_full_link_only_for_declared_full_flights(tmp_path):
    """NIE and a missing flag both mean "not full" -> no full_sheet/ link."""
    records = [
        dataclasses.replace(r, full_sheet=None if i % 2 else False)
        for i, r in enumerate(C14_ALL)
    ]
    fake = FakeCampaignProvider({"all": records})
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True)
    result = m.download_sheets([G])
    assert len(fake.downloads) == len(C14_ALL)
    assert not full_path(tmp_path).exists()
    assert result.full_links == {}


def test_full_link_kept_when_run_has_no_full_candidate(tmp_path):
    """F6: a later run without a full flight leaves the existing link alone."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake, all_campaigns=True).download_sheets([G])
    full = full_path(tmp_path)
    before = full.stat()
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheets([G])
    after = full.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert linked_version(full) == campaign_path(tmp_path, REC["83233"])
    assert result.full_links == {G: full}
    assert result.full_link_outside_range == {}


def test_full_link_never_moves_back_reports_outside_range(tmp_path):
    """F8: an older full flight in range never replaces a newer full link."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake, all_campaigns=True).download_sheets([G])
    target = campaign_path(tmp_path, REC["83233"])
    m = DownloadManager(tmp_path, provider=fake, all_campaigns=True, max_year=2024)
    result = m.download_sheets([G])
    assert linked_version(full_path(tmp_path)) == target
    kept = result.full_link_outside_range[G]
    assert kept.resolve() == target.resolve()


def test_full_link_failure_fails_sheet(tmp_path, monkeypatch):
    """A full_sheet/ link failure is a sheet failure, the standard link stays."""
    from kartograf.download import manager as manager_module

    real = manager_module.ensure_link

    def broken(link, *args, **kwargs):
        if "full_sheet" in link.parts:
            raise OSError("dysk pelny")
        return real(link, *args, **kwargs)

    monkeypatch.setattr(manager_module, "ensure_link", broken)
    m = DownloadManager(tmp_path, provider=c14_fake(), all_campaigns=True)
    with pytest.raises(DownloadError) as exc:
        m.download_sheet(G)
    assert "dowiazanie" in str(exc.value) and "full_sheet" in str(exc.value)
    assert linked_version(std_path(tmp_path)) == campaign_path(tmp_path, REC["84183"])


def test_local_newest_leaves_full_link_untouched(tmp_path):
    """F11: index outage (I-1) keeps the full_sheet/ link as it is."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake, all_campaigns=True).download_sheets([G])
    full = full_path(tmp_path)
    before = full.stat()
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake)
    result = m.download_sheet(G)
    assert result.unverified.keys() == {G}
    after = full.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert result.full_links == {G: full}


def test_force_with_changed_content_moves_full_link(tmp_path):
    """``--force``: new content of the full flight is a new version and the
    ``full_sheet/`` link moves to it; equal content leaves the link alone."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G4)
    full = full_path(tmp_path, G4)
    before = full.stat().st_ino
    DownloadManager(tmp_path, provider=fake).download_sheet(G4, update="force")
    assert full.stat().st_ino == before  # unchanged content
    fake.version = "v2"
    DownloadManager(tmp_path, provider=fake).download_sheet(G4, update="force")
    assert full.stat().st_ino != before
    assert "v2" in full.read_text() and linked_version(full) is not None


def test_full_sheet_flag_fetches_newest_full_flight(tmp_path):
    """F3: ``full_sheet=True`` adds the newest full flight to a partial newest."""
    fake = c14_fake()
    m = DownloadManager(tmp_path, provider=fake, full_sheet=True)
    result = m.download_sheets([G])
    newest = campaign_path(tmp_path, REC["84183"])
    full_flight = campaign_path(tmp_path, REC["83233"])
    assert fake.downloads == [REC["84183"].url, REC["83233"].url]
    assert linked_version(std_path(tmp_path)) == newest
    assert linked_version(full_path(tmp_path)) == full_flight
    assert m.full_sheet is True
    assert {f.version_path for f in result.files[G]} == {newest, full_flight}
    assert meta(full_flight)["request"]["full_sheet"] is True
    assert result.full_links == {G: full_path(tmp_path)}
    assert result.without_full == []


def test_full_sheet_flag_keeps_standard_link_on_newest(tmp_path):
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake, full_sheet=True).download_sheet(G)
    target = meta(std_path(tmp_path))["extra"]["link_target"]
    assert "2025-10-21_84183" in target


def test_full_sheet_flag_noop_when_newest_full(tmp_path):
    """F13: the newest flight is full -> the flag downloads nothing more."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake, full_sheet=True).download_sheet(G4)
    assert fake.downloads == [_rec_of(G4, "83998").url]
    assert {c[1] for c in fake.resolve_calls} == {False}
    assert os.path.samefile(full_path(tmp_path, G4), std_path(tmp_path, G4))


def test_full_sheet_flag_without_full_flight_reports(tmp_path):
    """F7: no full flight in the index -> one flight, no link, ``without_full``."""
    records = [dataclasses.replace(r, full_sheet=False) for r in C14_ALL]
    fake = FakeCampaignProvider({"newest": records[:1], "all": records})
    m = DownloadManager(tmp_path, provider=fake, full_sheet=True)
    result = m.download_sheets([G])
    assert fake.downloads == [REC["84183"].url]
    assert not full_path(tmp_path).exists()
    assert result.without_full == [G] and result.failed == []


def test_full_sheet_flag_respects_year_range(tmp_path):
    """The year bounds filter the full flight too."""
    fake = c14_fake()
    m = DownloadManager(tmp_path, provider=fake, full_sheet=True, max_year=2024)
    m.download_sheets([G])
    assert fake.downloads == [REC["78047"].url]  # newest in range is full
    assert linked_version(full_path(tmp_path)) == campaign_path(tmp_path, REC["78047"])

    other = tmp_path / "other"
    records = [
        dataclasses.replace(r, full_sheet=False) if r is REC["78047"] else r
        for r in C14_ALL
    ]
    fake = FakeCampaignProvider({"newest": records[:1], "all": records})
    m = DownloadManager(other, provider=fake, full_sheet=True, max_year=2024)
    m.download_sheets([G])
    assert fake.downloads == [REC["78047"].url, REC["73021"].url]
    assert linked_version(full_path(other)) == campaign_path(other, REC["73021"])


def test_full_sheet_flag_with_all_adds_nothing(tmp_path):
    fake = c14_fake()
    DownloadManager(
        tmp_path, provider=fake, all_campaigns=True, full_sheet=True
    ).download_sheets([G])
    assert sorted(fake.downloads) == sorted(r.url for r in C14_ALL)


def test_full_sheet_requires_campaign_provider(tmp_path):
    with pytest.raises(ValidationError, match="nie obsluguje kampanii"):
        DownloadManager(tmp_path, provider=_mock_provider(), full_sheet=True)


def test_full_sheet_full_flight_download_failure_fails_sheet(tmp_path):
    fake = c14_fake(fail_urls={REC["83233"].url})
    m = DownloadManager(tmp_path, provider=fake, full_sheet=True)
    with pytest.raises(DownloadError, match="83233"):
        m.download_sheet(G)
    assert linked_version(std_path(tmp_path)) == campaign_path(tmp_path, REC["84183"])
    assert not full_path(tmp_path).exists()


def test_full_sheet_missing_full_flight_downloaded_by_default(tmp_path):
    """Spec 4.2: a missing newest full flight is "no local version" — the
    default mode downloads it, the local newest flight is not touched."""
    fake = c14_fake()
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    m = DownloadManager(tmp_path, provider=fake, full_sheet=True)
    result = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url, REC["83233"].url]
    assert linked_version(full_path(tmp_path)) == campaign_path(tmp_path, REC["83233"])
    assert result.new == [G]
