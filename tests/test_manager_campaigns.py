"""
The ``DownloadManager`` campaign path (ADR-030): files in ``kampanie/``, the
standard path link, the mandatory campaign sidecar, ``SheetFetch``/``last_sheet``.

Records: real ``SkorowidzRecord`` objects from raw index (skorowidz) responses
(``tests/fixtures/gugik_skorowidz/real_2026_10_06/nmt``): C14
(N-34-139-C-a-3-1..4) and N-33-69-A-d-3-2 (campaign 72675 with a ``.xyz`` URL).
The provider is a mock with no network (``FakeCampaignProvider``).
"""

import dataclasses
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
import requests

from kartograf.download.links import linked_campaign
from kartograf.download.manager import DownloadManager, DownloadProgress, SheetFetch
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
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


def _filtered(files: list[Path], godlo: str) -> list:
    """Records passing the hard filter (PL-1992, 1 m), newest first."""
    records = []
    for f in files:
        layer = f.stem.rsplit("_", 1)[-1]
        records += [
            r
            for r in parse_skorowidz_records(f.read_text(encoding="utf-8"), layer)
            if r.godlo == godlo and r.uklad == "1992" and r.resolution_m == 1.0
        ]
    return sorted(
        records, key=lambda r: (r.aktualnosc, r.dt_pzgik or "", r.url), reverse=True
    )


def c14_records(godlo: str = G) -> list:
    return _filtered(sorted((NMT / "c14").glob(f"{godlo}_EVRF2007_*.html")), godlo)


C14_ALL = c14_records()
REC = {r.url.rsplit("/", 1)[-1].split("_")[0]: r for r in C14_ALL}
C14 = {"newest": [REC["84183"]], "all": C14_ALL}

X_ALL = _filtered(sorted((NMT / G2).glob("*.body")), G2)
XREC = {r.url.rsplit("/", 1)[-1].split("_")[0]: r for r in X_ALL}


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

    def download(self, godlo: str, output_path: Path, timeout: int = 30) -> Path:
        """Campaign providers download through download_record()."""
        raise NotImplementedError("FakeCampaignProvider: tor kampanii")

    def __init__(self, records_by_strategy, fail_urls=(), contents=None) -> None:
        self.records = records_by_strategy
        self.fail_urls = set(fail_urls)
        self.contents = dict(contents or {})  # url -> bytes (ASC by default)
        self.version = "v1"
        self.fixed_mtime: float | None = None
        self.downloads: list[str] = []
        self.resolve_calls: list[str] = []
        self.resolve_error: Exception | None = None  # I-1: index failure
        self._lock = threading.Lock()  # D-6: number of resolutions per sheet code

    def resolve_campaigns(
        self, godlo, *, campaigns="newest", min_year=None, timeout=None
    ):
        with self._lock:
            self.resolve_calls.append(godlo)
        if self.resolve_error is not None:
            raise self.resolve_error
        recs = [
            r
            for r in self.records[campaigns]
            if r.godlo == godlo
            and (min_year is None or int(r.aktualnosc[:4]) >= min_year)
        ]
        if not recs:
            raise NoCoverageError(f"Brak kampanii {godlo}", godlo=godlo)
        return recs

    def record_source(self, r):
        return r.to_source("https://wms")

    def download_record(self, r, path, timeout=None):
        if r.url in self.fail_urls:
            raise DownloadError("siec", godlo=r.godlo)
        with self._lock:
            self.downloads.append(r.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        if r.url in self.contents:
            path.write_bytes(self.contents[r.url])
        else:
            path.write_text(ASC_TEMPLATE.format(tag=f"{self.version} {tag(r)}"))
        if self.fixed_mtime is not None:
            os.utime(path, (self.fixed_mtime, self.fixed_mtime))
        return path


def std_path(tmp_path: Path, godlo: str = G) -> Path:
    parts = godlo.split("-")
    return tmp_path / SEGMENT / "-".join(parts[:2]) / Path(*parts[2:]) / f"{godlo}.asc"


def campaign_path(tmp_path: Path, record, godlo: str = G) -> Path:
    parts = godlo.split("-")
    dirname = f"{record.aktualnosc}_{tag(record).split('_')[0]}"
    return (
        tmp_path
        / SEGMENT
        / "kampanie"
        / dirname
        / "-".join(parts[:2])
        / Path(*parts[2:])
        / f"{godlo}.asc"
    )


def sidecar(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def meta(path: Path) -> dict:
    return json.loads(sidecar(path).read_text(encoding="utf-8"))


def linked(path: Path) -> str:
    """Campaign file per the standard sidecar (the only source of the target)."""
    return str(linked_campaign(path))


def hardlinked(path: Path) -> bool:
    """The standard path is a hard link (not a symlink) to its campaign."""
    target = linked_campaign(path)
    return (
        target is not None
        and not path.is_symlink()
        and os.path.samefile(path, target)
        and os.stat(path).st_nlink == 2
    )


def deny_links(monkeypatch):
    def denied(*args, **kwargs):
        raise OSError("brak uprawnien")

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


def test_newest_downloads_into_kampanie_and_links(tmp_path):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    path = m.download_sheet(G)
    assert (
        path
        == tmp_path / "nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc"
    )
    assert hardlinked(path) and "kampanie/2025-10-21_84183" in linked(path)
    data = json.loads((path.parent / (path.name + ".meta.json")).read_text())
    assert data["extra"]["link"] == "hardlink"
    assert data["extra"]["campaign"]["id"] == "84183"
    assert data["request"] == {"sheet": G, "campaigns": "newest"}
    assert isinstance(m.last_sheet, SheetFetch)
    assert m.last_sheet.skipped is False and m.last_sheet.link == "hardlink"
    assert m.last_sheet.downloaded == (campaign_path(tmp_path, REC["84183"]),)


def test_rerun_newest_existing_campaign_no_download_skipped(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    path = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert m.last_sheet.skipped is True
    assert m.last_sheet.reused == (campaign_path(tmp_path, REC["84183"]),)
    assert hardlinked(path) and "2025-10-21_84183" in linked(path)


def test_existing_standard_file_is_not_a_reason_to_skip(tmp_path):
    std = std_path(tmp_path)
    std.parent.mkdir(parents=True)
    std.write_text(ASC_TEMPLATE.format(tag="stary"))
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert hardlinked(std)
    assert m.last_sheet.skipped is False


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


def test_newer_campaign_appears_relinks(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    assert "2025-04-27_83233" in linked(std)
    fake.records = {"newest": [REC["84183"]]}
    m.download_sheet(G)
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]
    assert "2025-10-21_84183" in linked(std)
    assert campaign_path(tmp_path, REC["83233"]).is_file()
    assert meta(std)["extra"]["campaign"]["id"] == "84183"


# =============================================================================
# all
# =============================================================================


def test_all_downloads_every_campaign_links_newest(tmp_path):
    # list from the oldest: the link must follow sort_key, not download order
    fake = FakeCampaignProvider({"all": list(reversed(C14_ALL))})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    assert sorted(d.name for d in (tmp_path / SEGMENT / "kampanie").iterdir()) == [
        "2019-04-18_73021",
        "2023-09-05_78047",
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    assert "2025-10-21_84183" in linked(std_path(tmp_path))
    assert len(m.last_result.campaign_files[G]) == 4
    assert m.last_result.succeeded == [std_path(tmp_path)]


def test_all_skips_existing_campaigns_individually(tmp_path):
    fake = FakeCampaignProvider({"all": [REC["84183"], REC["83233"]]})
    DownloadManager(tmp_path, provider=fake, campaigns="all").download_sheets([G])
    fake.records = C14
    fake.downloads.clear()
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    assert sorted(fake.downloads) == sorted([REC["78047"].url, REC["73021"].url])
    assert len(m.last_result.campaign_files[G]) == 4


def test_all_reused_campaign_files_lists_only_local_ones(tmp_path):
    """T8 fix 1: ``reused_campaign_files`` = the subset of already local campaigns."""
    fake = FakeCampaignProvider({"all": [REC["84183"], REC["83233"]]})
    first = DownloadManager(tmp_path, provider=fake, campaigns="all")
    first.download_sheets([G])
    assert first.last_result.reused_campaign_files.get(G, ()) == ()
    fake.records = C14
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    reused = m.last_result.reused_campaign_files[G]
    assert sorted(reused) == sorted(
        campaign_path(tmp_path, REC[k]) for k in ("84183", "83233")
    )
    assert set(reused) <= set(m.last_result.campaign_files[G])
    assert len(m.last_result.campaign_files[G]) == 4


def test_all_min_year_filters(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, campaigns="all", min_year=2025)
    m.download_sheets([G])
    assert sorted(d.name for d in (tmp_path / SEGMENT / "kampanie").iterdir()) == [
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    assert meta(campaign_path(tmp_path, REC["83233"]))["request"] == {
        "sheet": G,
        "campaigns": "all",
        "min_year": 2025,
    }


def test_newest_after_all_keeps_link_on_newer_local_campaign(tmp_path):
    DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), campaigns="all"
    ).download_sheets([G])
    stale = FakeCampaignProvider({"newest": [REC["83233"]]})  # stale record_cache
    m = DownloadManager(tmp_path, provider=stale)
    path = m.download_sheet(G)
    assert stale.downloads == []
    assert "2025-10-21_84183" in linked(path)
    assert m.last_sheet.skipped is True


def test_all_partial_campaign_failure_is_hard_failure_but_links_best_local(tmp_path):
    fake = FakeCampaignProvider(C14, fail_urls={REC["84183"].url})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all", max_workers=2)
    m.download_sheets([G])
    assert m.last_result.failed == [G]
    assert m.last_result.no_coverage == []
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    for key in ("83233", "78047", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()
    assert not campaign_path(tmp_path, REC["84183"]).exists()


def test_removed_campaign_dir_redownloads_newest(tmp_path):
    """T12 step 7: the hard link survives removal of the campaign directory, but
    ``extra.link_target`` does not exist - ``newest`` downloads again."""
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    shutil.rmtree(campaign_path(tmp_path, REC["84183"]).parents[5])
    assert std.is_file() and linked_campaign(std) is None
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url] * 2
    assert hardlinked(std)
    assert linked(std) == str(campaign_path(tmp_path, REC["84183"]))
    assert m.last_sheet.skipped is False


def test_force_redownloads_all_campaigns_and_relinks(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    fake.downloads.clear()
    m.download_sheets([G], skip_existing=False)
    assert sorted(fake.downloads) == sorted(r.url for r in C14_ALL)
    assert "2025-10-21_84183" in linked(std_path(tmp_path))
    assert m.last_result.succeeded == [std_path(tmp_path)]


def test_force_redownload_relinks_copy(tmp_path, monkeypatch):
    deny_links(monkeypatch)
    fake = FakeCampaignProvider(C14)
    # target never "newer" than the copy (D-5 does not help)
    fake.fixed_mtime = 1_000_000_000.0
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    assert not std.is_symlink() and "v1" in std.read_text()
    fake.version = "v2"  # same size
    m.download_sheet(G, skip_existing=False)
    assert "v2" in campaign_path(tmp_path, REC["84183"]).read_text()
    assert "v2" in std.read_text()
    assert m.last_sheet.link == "copy"


def test_copy_fallback_reported_in_result(tmp_path, monkeypatch):
    deny_links(monkeypatch)
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    m.download_sheets([G])
    assert m.last_result.copied == [G]
    assert meta(std_path(tmp_path))["extra"]["link"] == "copy"


def test_reused_campaign_notes_parent_request_in_both_sidecars(tmp_path):
    r1, r2 = {"bbox": [1, 2, 3, 4]}, {"bbox": [5, 6, 7, 8]}
    fake = FakeCampaignProvider(C14)
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r1}
    ).download_sheets([G])
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r2}
    ).download_sheets([G])
    camp = meta(campaign_path(tmp_path, REC["84183"]))
    std = meta(std_path(tmp_path))
    for data in (camp, std):
        assert data["extra"]["parent_request"] == r1
        assert data["extra"]["parent_requests"] == [r2]


def test_note_reuse_never_writes_through_symlink(tmp_path):
    r1, r2 = {"bbox": [1, 2, 3, 4]}, {"bbox": [5, 6, 7, 8]}
    fake = FakeCampaignProvider(C14)
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r1}
    ).download_sheets([G])
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r2}
    ).download_sheets([G])
    std_side = sidecar(std_path(tmp_path))
    assert std_side.is_file() and not std_side.is_symlink()
    camp_side = sidecar(campaign_path(tmp_path, REC["84183"]))
    assert not camp_side.is_symlink()
    camp = json.loads(camp_side.read_text())
    assert camp["extra"]["parent_requests"] == [r2]
    assert "link" not in camp["extra"]


def test_campaign_sidecar_source_matches_its_own_record(tmp_path):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), campaigns="all")
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
    path = m.download_sheet(G2)
    assert path == std_path(tmp_path, G2) and path.exists()
    assert linked(path).endswith(
        "kampanie/2019-04-29_72675/N-33/69/A/d/3/2/N-33-69-A-d-3-2.asc"
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
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G2])
    assert len(list((tmp_path / SEGMENT / "kampanie").rglob("*.asc"))) == 5
    assert "2024-09-23_81025" in linked(std_path(tmp_path, G2))
    assert m.last_result.failed == []


def test_unknown_format_fails_before_file_download(tmp_path):
    x = XREC["72675"]
    bad = dataclasses.replace(x, raw={**x.raw, "format": "XYZ ASCII"})
    fake = FakeCampaignProvider({"newest": [REC["84183"], bad]})
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    assert m.last_sheet is not None
    with pytest.raises(DownloadError, match="'XYZ ASCII'"):
        m.download_sheet(G2)
    assert fake.downloads == [REC["84183"].url]
    std = std_path(tmp_path, G2)
    assert not std.exists() and not std.is_symlink()
    assert not (tmp_path / SEGMENT / "kampanie" / "2019-04-29_72675").exists()
    assert m.last_sheet is None


def test_content_mismatch_removes_file_and_fails(tmp_path):
    old, new = XREC["75506"], XREC["81025"]
    fake = FakeCampaignProvider(
        {"newest": [old]}, contents={new.url: b"<html>404</html>"}
    )
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G2)
    fake.records = {"newest": [new]}
    with pytest.raises(DownloadError, match="tresc nie jest"):
        m.download_sheet(G2)
    bad = campaign_path(tmp_path, new, G2)
    assert not bad.exists() and not sidecar(bad).exists()
    assert "2022-03-20_75506" in linked(std)


def test_all_content_mismatch_on_newest_links_previous(tmp_path):
    fake = FakeCampaignProvider(C14, contents={REC["84183"].url: b"<html>404</html>"})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    assert m.last_result.failed == [G]
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
    verify.assert_called_once_with(target, ".asc")
    assert target.is_file()


# =============================================================================
# mandatory campaign sidecar (errata 2 N-1)
# =============================================================================


def test_campaign_sidecar_failure_removes_data_and_keeps_link(tmp_path, monkeypatch):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    before = sidecar(std).read_bytes()

    def broken(*args, **kwargs):
        raise OSError("dysk pelny")

    monkeypatch.setattr("kartograf.sources.sidecar.build_metadata", broken)
    fake.records = {"newest": [REC["84183"]]}
    with pytest.raises(DownloadError, match="obowiazkowego sidecara"):
        m.download_sheet(G)
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
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), campaigns="all")
    m.download_sheets([G])
    assert m.last_result.failed == [G]
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    assert not campaign_path(tmp_path, REC["84183"]).exists()
    for key in ("83233", "78047", "73021"):
        assert sidecar(campaign_path(tmp_path, REC[key])).is_file()


def test_reused_campaign_without_sidecar_gets_sidecar(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    target = campaign_path(tmp_path, REC["84183"])
    sidecar(target).unlink()
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert meta(target)["extra"]["campaign"]["id"] == "84183"
    assert hardlinked(std) and linked(std) == str(target)


def _mock_provider(tmp_payload: bytes = b"ncols 1\n") -> Mock:
    p = Mock(spec=GugikProvider)
    type(p).default_extension = PropertyMock(return_value=".asc")
    type(p).descriptor_key = PropertyMock(return_value="pl.gugik.nmt_1m")
    type(p).vertical_crs = PropertyMock(return_value="EVRF2007")
    p.name = "mock"

    def download(godlo, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tmp_payload)
        return path

    p.download.side_effect = download
    p.source_info.return_value = None
    return p


def test_plain_track_sidecar_failure_still_best_effort(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("dysk pelny")

    monkeypatch.setattr("kartograf.sources.sidecar.build_metadata", broken)
    m = DownloadManager(tmp_path, provider=_mock_provider())
    path = m.download_sheet(G)
    assert path.is_file() and not path.is_symlink()
    assert not sidecar(path).exists()


# =============================================================================
# sheet list, parallelism, logs
# =============================================================================


def test_min_year_newest_no_coverage_in_list_is_no_coverage_status(
    tmp_path: Path,
) -> None:
    events: list[DownloadProgress] = []
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), min_year=2026)
    m.download_sheets([G], on_progress=events.append)
    result = m.last_result
    assert result is not None
    assert result.no_coverage == [G]
    assert result.failed == [G]
    assert events[-1].status == "no_coverage"


def test_parallel_all_campaigns_writes_each_file_once(tmp_path):
    godla = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    records = [r for g in godla for r in c14_records(g)]
    fake = FakeCampaignProvider({"all": records})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all", max_workers=4)
    m.download_sheets(godla)
    assert sorted(fake.downloads) == sorted(r.url for r in records)
    assert m.last_result.failed == []
    for g in godla:
        assert std_path(tmp_path, g).exists()
        assert len(m.last_result.campaign_files[g]) == len(c14_records(g))


def test_duplicate_godla_in_list_download_once_and_link_once(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, max_workers=4)
    m.download_sheets([G, G, G])
    assert fake.resolve_calls == [G]
    assert fake.downloads == [REC["84183"].url]
    assert m.last_result.total == 1


def test_campaign_count_logged_at_info(tmp_path, caplog):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), campaigns="all")
    with caplog.at_level(logging.INFO, logger="kartograf.download.manager"):
        m.download_sheets([G])
    assert any(
        r.name == "kartograf.download.manager"
        and r.levelno == logging.INFO
        and G in r.getMessage()
        and "4 kampanii" in r.getMessage()
        for r in caplog.records
    )


def test_last_sheet_none_after_list_download(tmp_path):
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14))
    m.download_sheet(G)
    assert m.last_sheet is not None
    m.download_sheets([G])
    assert m.last_sheet is None


# =============================================================================
# provider without campaigns (plain path) and validation
# =============================================================================


def test_provider_without_campaigns_keeps_plain_flow(tmp_path):
    p = _mock_provider()
    m = DownloadManager(tmp_path, provider=p)
    path = m.download_sheet(G)
    assert path == std_path(tmp_path)
    assert path.is_file() and not path.is_symlink()
    assert not (tmp_path / SEGMENT / "kampanie").exists()
    assert m.last_sheet == SheetFetch(G, path, skipped=False)
    m.download_sheet(G)
    assert m.last_sheet.skipped is True and m.last_sheet.link is None
    assert p.download.call_count == 1


def test_provider_without_campaigns_rejects_all_and_min_year():
    with pytest.raises(ValidationError, match="nie obsluguje kampanii"):
        DownloadManager(provider=_mock_provider(), campaigns="all")
    with pytest.raises(ValidationError, match="nie obsluguje kampanii"):
        DownloadManager(provider=_mock_provider(), min_year=2024)


def test_spec_mock_is_not_campaign_aware(tmp_path):
    p = Mock(spec=GugikProvider)
    type(p).default_extension = PropertyMock(return_value=".asc")
    m = DownloadManager(tmp_path, provider=p)  # no exception
    assert m.campaigns == "newest" and m.min_year is None

    def download(godlo, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ncols 1\n")
        return path

    p.download.side_effect = download
    path = m.download_sheet(G)  # plain path: provider.download, not resolve_campaigns
    assert p.download.call_count == 1
    assert path.is_file() and not path.is_symlink()


def test_invalid_campaigns_value():
    with pytest.raises(ValidationError):
        DownloadManager(provider=FakeCampaignProvider(C14), campaigns="mosaic")
    with pytest.raises(ValidationError):
        DownloadManager(provider=FakeCampaignProvider(C14), min_year=True)


# =============================================================================
# Fix round 1
# =============================================================================


def test_note_reuse_with_symlinked_valid_standard_sidecar(tmp_path):
    """<std>.meta.json as a symlink to the CORRECT content of the standard
    sidecar located elsewhere: the data link stays (no download), and reuse
    (also without ``parent_request``) turns the standard sidecar into a regular
    file, without writing through the symlink."""
    r1 = {"bbox": [1, 2, 3, 4]}
    fake = FakeCampaignProvider(C14)
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r1}
    ).download_sheets([G])
    std_side = sidecar(std_path(tmp_path))
    elsewhere = tmp_path / "gdzie_indziej.json"
    elsewhere.write_bytes(std_side.read_bytes())
    std_side.unlink()
    _REAL_SYMLINK(elsewhere, std_side)
    before = elsewhere.read_bytes()

    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheets([G])

    assert fake.downloads == [REC["84183"].url]
    assert m.last_result.skipped == [G]
    assert elsewhere.read_bytes() == before
    assert std_side.is_file() and not std_side.is_symlink()
    assert meta(std_path(tmp_path))["extra"]["link"] == "hardlink"


@pytest.mark.parametrize("parent", [None, {"bbox": [5, 6, 7, 8]}])
def test_note_reuse_with_symlinked_standard_sidecar(tmp_path, parent):
    """<std>.meta.json being a SYMLINK to the campaign sidecar: reuse does not
    modify the campaign sidecar through the link, and the standard sidecar
    becomes a regular file."""
    r1 = {"bbox": [1, 2, 3, 4]}
    fake = FakeCampaignProvider(C14)
    DownloadManager(
        tmp_path, provider=fake, sidecar_extra={"parent_request": r1}
    ).download_sheets([G])
    camp_side = sidecar(campaign_path(tmp_path, REC["84183"]))
    std_side = sidecar(std_path(tmp_path))
    std_side.unlink()
    _REAL_SYMLINK(os.path.relpath(camp_side, std_side.parent), std_side)
    before = camp_side.read_bytes()

    extra = {"parent_request": parent} if parent else None
    DownloadManager(tmp_path, provider=fake, sidecar_extra=extra).download_sheets([G])

    assert fake.downloads == [REC["84183"].url]
    assert std_side.is_file() and not std_side.is_symlink()
    assert not camp_side.is_symlink()
    camp = json.loads(camp_side.read_text())
    assert "link" not in camp["extra"] and "link_target" not in camp["extra"]
    std = json.loads(std_side.read_text())
    assert std["extra"]["link"] == "hardlink"
    if parent is None:
        assert camp_side.read_bytes() == before
        assert "parent_requests" not in std["extra"]
    else:
        assert camp["extra"]["parent_requests"] == [parent]
        assert std["extra"]["parent_requests"] == [parent]


def test_link_failure_is_sheet_failure_and_list_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R5: a link failure (the copy fails) = a sheet failure, not an abort of
    the list at max_workers=1; the downloaded campaign stays."""
    import shutil

    g3 = "N-34-139-C-a-3-2"
    other = c14_records(g3)[0]
    deny_links(monkeypatch)
    real_copy = shutil.copyfile

    def copyfile(src, dst, *args, **kwargs):
        if G in str(src):
            raise OSError("dysk pelny")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", copyfile)
    events: list[DownloadProgress] = []
    fake = FakeCampaignProvider({"newest": [REC["84183"], other]})
    m = DownloadManager(tmp_path, provider=fake, max_workers=1)
    m.download_sheets([G, g3], on_progress=events.append)
    result = m.last_result
    assert result is not None
    assert result.failed == [G]
    assert result.no_coverage == []
    assert result.succeeded == [std_path(tmp_path, g3)]
    assert campaign_path(tmp_path, REC["84183"]).is_file()
    assert not std_path(tmp_path).exists()
    failed = next(e for e in events if e.godlo == G and e.status == "failed")
    assert "dowiazanie" in failed.message and "dysk pelny" in failed.message


def test_link_failure_reported_together_with_campaign_errors(tmp_path, monkeypatch):
    import shutil

    deny_links(monkeypatch)

    def copyfile(*args, **kwargs):
        raise OSError("dysk pelny")

    monkeypatch.setattr(shutil, "copyfile", copyfile)
    fake = FakeCampaignProvider(C14, fail_urls={REC["78047"].url})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
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
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    with pytest.raises(DownloadError, match="84183_1852496") as exc:
        m.download_sheet(G)
    assert "nie pobrano 1 z 4 kampanii" in str(exc.value)
    assert "2025-04-27_83233" in linked(std_path(tmp_path))
    for key in ("83233", "78047", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()


# =============================================================================
# I-1: newest on an index transport failure -> local campaign
# =============================================================================


def _transport_error(godlo: str, failure) -> DownloadError:
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
            get_with_retry(session, "https://wms", timeout=1, description=godlo)
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
    std = m.download_sheet(G)
    before = linked(std)
    fake.resolve_error = _transport_error(G, failure)
    with caplog.at_level(logging.WARNING, logger="kartograf.download.manager"):
        path = m.download_sheet(G)
    target = campaign_path(tmp_path, REC["84183"])
    assert path == std and linked(std) == before
    assert fake.downloads == [REC["84183"].url]
    fetch = m.last_sheet
    assert fetch.skipped is True
    assert fetch.reused == (target,) and fetch.downloaded == ()
    assert fetch.link == "hardlink"
    assert fetch.unverified and str(fake.resolve_error) in fetch.unverified
    assert any(
        r.levelno == logging.WARNING and G in r.getMessage() for r in caplog.records
    )


def test_newest_transport_failure_in_list_is_skipped_and_reported(
    tmp_path: Path,
) -> None:
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.resolve_error = _transport_error(G, 503)
    events: list[DownloadProgress] = []
    paths = m.download_sheets([G], on_progress=events.append)
    result = m.last_result
    assert result is not None
    assert paths == [std_path(tmp_path)]
    assert result.skipped == [G] and result.failed == []
    assert set(result.unverified) == {G}
    assert "503" in result.unverified[G]
    assert events[-1].status == "skipped"


def test_newest_transport_failure_keeps_copy_link_untouched(tmp_path, monkeypatch):
    deny_links(monkeypatch)
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    (std.parent / f"{std.name}.aux.xml").write_text("<PAMDataset/>")
    fake.resolve_error = _transport_error(G, requests.ConnectionError("x"))
    with patch("shutil.copyfile") as copy:
        m.download_sheet(G)
    copy.assert_not_called()
    assert (std.parent / f"{std.name}.aux.xml").exists()
    assert m.last_sheet.link == "copy" and m.last_sheet.unverified


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        # no coverage = a data state, not transport
        ({}, NoCoverageError("Brak kampanii", godlo=G)),
        # 4xx without retries and a response-content error are not transport
        ({}, "404"),
        ({}, DownloadError("raport wyjatku OGC", godlo=G)),
        # only newest without min_year
        ({"campaigns": "all"}, "conn"),
        ({"min_year": 2020}, "conn"),
    ],
    ids=["no-coverage", "http-404", "ogc", "all", "min-year"],
)
def test_resolve_failure_without_fallback_still_fails(tmp_path, kwargs, error):
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
        m.download_sheet(G)
    assert exc.value is error
    assert m.last_sheet is None


def test_transport_failure_without_local_campaign_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    m = DownloadManager(tmp_path, provider=fake)
    with pytest.raises(DownloadError):
        m.download_sheet(G)
    m.download_sheets([G])
    assert m.last_result.failed == [G] and m.last_result.unverified == {}


def test_transport_failure_with_dangling_link_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    campaign_path(tmp_path, REC["84183"]).unlink()
    fake.resolve_error = _transport_error(G, 503)
    with pytest.raises(DownloadError):
        m.download_sheet(G)
    assert std.is_file() and linked_campaign(std) is None  # untouched


def test_transport_failure_with_force_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.resolve_error = _transport_error(G, 503)
    with pytest.raises(DownloadError):
        m.download_sheet(G, skip_existing=False)


# =============================================================================
# M-2: campaign file without a sidecar (R22) - content verification
# =============================================================================


def test_reused_campaign_without_sidecar_with_foreign_content_fails(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    target = campaign_path(tmp_path, REC["84183"])
    sidecar(target).unlink()
    target.write_bytes(b"<html>blad serwera</html>")
    with pytest.raises(DownloadError, match="2025-10-21_84183") as exc:
        m.download_sheet(G)
    assert "AAIGrid" in str(exc.value)
    assert not target.exists() and not sidecar(target).exists()
    assert fake.downloads == [REC["84183"].url]
    # the next run downloads the campaigns again (the file was not "local")
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url] * 2
    assert hardlinked(std) and linked(std) == str(target)


# =============================================================================
# M-6: a re-run without download does not move the link (copy)
# =============================================================================


def test_rerun_without_download_does_not_recopy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    deny_links(monkeypatch)
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    assert isinstance(std, Path)
    first = m.last_sheet
    assert first is not None
    assert first.link == "copy"
    aux = std.parent / f"{std.name}.aux.xml"
    aux.write_text("<PAMDataset/>")
    std_meta = sidecar(std).read_text(encoding="utf-8")
    real_copy = shutil.copyfile
    calls: list = []

    def copyfile(*args, **kwargs):
        calls.append(args)
        return real_copy(*args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", copyfile)
    m.download_sheet(G)
    assert calls == []
    assert aux.exists()
    assert sidecar(std).read_text(encoding="utf-8") == std_meta
    again = m.last_sheet
    assert again is not None
    assert again.skipped is True and again.link == "copy"
    assert fake.downloads == [REC["84183"].url]
