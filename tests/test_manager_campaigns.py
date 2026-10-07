"""
Tor kampanii ``DownloadManager`` (ADR-030): pliki w ``kampanie/``, dowiazanie
sciezki standardowej, obowiazkowy sidecar kampanii, ``SheetFetch``/``last_sheet``.

Rekordy: prawdziwe ``SkorowidzRecord`` z surowych odpowiedzi skorowidza
(``tests/fixtures/gugik_skorowidz/real_2026_10_06/nmt``): C14
(N-34-139-C-a-3-1..4) oraz N-33-69-A-d-3-2 (kampania 72675 z URL ``.xyz``).
Provider to atrapa bez sieci (``FakeCampaignProvider``).
"""

import dataclasses
import json
import logging
import os
import threading
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from kartograf.download.manager import DownloadManager, DownloadProgress, SheetFetch
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.skorowidz import parse_skorowidz_records

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
    """Rekordy przechodzace twardy filtr (PL-1992, 1 m), od najnowszego."""
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


class FakeCampaignProvider:
    """supports_campaigns MUSI byc atrybutem KLASOWYM == True (DownloadManager
    sprawdza ``is True``; Mock/Mock(spec=...) daja Mock -> tor plain)."""

    supports_campaigns = True
    descriptor_key = "pl.gugik.nmt_1m"
    vertical_crs = "EVRF2007"
    default_extension = ".asc"
    name = "fake"

    def __init__(self, records_by_strategy, fail_urls=(), contents=None):
        self.records = records_by_strategy
        self.fail_urls = set(fail_urls)
        self.contents = dict(contents or {})  # url -> bajty (domyslnie ASC)
        self.version = "v1"
        self.fixed_mtime: float | None = None
        self.downloads: list[str] = []
        self.resolve_calls: list[str] = []
        self._lock = threading.Lock()  # D-6: liczba rozwiazan per godlo

    def resolve_campaigns(
        self, godlo, *, campaigns="newest", min_year=None, timeout=None
    ):
        with self._lock:
            self.resolve_calls.append(godlo)
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
    return os.path.realpath(path)


def deny_links(monkeypatch):
    def denied(*args, **kwargs):
        raise OSError("brak uprawnien")

    monkeypatch.setattr(os, "symlink", denied)
    monkeypatch.setattr(os, "link", denied)


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
    assert path.is_symlink() and "kampanie/2025-10-21_84183" in os.readlink(path)
    data = json.loads((path.parent / (path.name + ".meta.json")).read_text())
    assert data["extra"]["link"] == "symlink"
    assert data["extra"]["campaign"]["id"] == "84183"
    assert data["request"] == {"godlo": G, "campaigns": "newest"}
    assert isinstance(m.last_sheet, SheetFetch)
    assert m.last_sheet.skipped is False and m.last_sheet.link == "symlink"
    assert m.last_sheet.downloaded == (campaign_path(tmp_path, REC["84183"]),)


def test_rerun_newest_existing_campaign_no_download_skipped(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    path = m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert m.last_sheet.skipped is True
    assert m.last_sheet.reused == (campaign_path(tmp_path, REC["84183"]),)
    assert path.is_symlink() and "2025-10-21_84183" in os.readlink(path)


def test_existing_standard_file_is_not_a_reason_to_skip(tmp_path):
    std = std_path(tmp_path)
    std.parent.mkdir(parents=True)
    std.write_text(ASC_TEMPLATE.format(tag="stary"))
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url]
    assert std.is_symlink()
    assert m.last_sheet.skipped is False


def test_legacy_regular_file_replaced_by_link(tmp_path):
    std = std_path(tmp_path)
    std.parent.mkdir(parents=True)
    std.write_text(ASC_TEMPLATE.format(tag="stary"))
    sidecar(std).write_text(
        json.dumps({"extra": {"parent_requests": [{"bbox": [1, 2, 3, 4]}]}})
    )
    DownloadManager(tmp_path, provider=FakeCampaignProvider(C14)).download_sheet(G)
    assert std.is_symlink()
    assert linked(std) == str(campaign_path(tmp_path, REC["84183"]))
    data = meta(std)
    assert data["extra"]["campaign"]["id"] == "84183"
    assert "parent_requests" not in data["extra"]
    assert not sidecar(std).is_symlink()


def test_newer_campaign_appears_relinks(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    assert "2025-04-27_83233" in os.readlink(std)
    fake.records = {"newest": [REC["84183"]]}
    m.download_sheet(G)
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]
    assert "2025-10-21_84183" in os.readlink(std)
    assert campaign_path(tmp_path, REC["83233"]).is_file()
    assert meta(std)["extra"]["campaign"]["id"] == "84183"


# =============================================================================
# all
# =============================================================================


def test_all_downloads_every_campaign_links_newest(tmp_path):
    # lista od najstarszej: link musi isc za sort_key, nie za kolejnoscia pobran
    fake = FakeCampaignProvider({"all": list(reversed(C14_ALL))})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    assert sorted(d.name for d in (tmp_path / SEGMENT / "kampanie").iterdir()) == [
        "2019-04-18_73021",
        "2023-09-05_78047",
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    assert "2025-10-21_84183" in os.readlink(std_path(tmp_path))
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


def test_all_min_year_filters(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, campaigns="all", min_year=2025)
    m.download_sheets([G])
    assert sorted(d.name for d in (tmp_path / SEGMENT / "kampanie").iterdir()) == [
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    assert meta(campaign_path(tmp_path, REC["83233"]))["request"] == {
        "godlo": G,
        "campaigns": "all",
        "min_year": 2025,
    }


def test_newest_after_all_keeps_link_on_newer_local_campaign(tmp_path):
    DownloadManager(
        tmp_path, provider=FakeCampaignProvider(C14), campaigns="all"
    ).download_sheets([G])
    stale = FakeCampaignProvider({"newest": [REC["83233"]]})  # stary record_cache
    m = DownloadManager(tmp_path, provider=stale)
    path = m.download_sheet(G)
    assert stale.downloads == []
    assert "2025-10-21_84183" in os.readlink(path)
    assert m.last_sheet.skipped is True


def test_all_partial_campaign_failure_is_hard_failure_but_links_best_local(tmp_path):
    fake = FakeCampaignProvider(C14, fail_urls={REC["84183"].url})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all", max_workers=2)
    m.download_sheets([G])
    assert m.last_result.failed == [G]
    assert m.last_result.no_coverage == []
    assert "2025-04-27_83233" in os.readlink(std_path(tmp_path))
    for key in ("83233", "78047", "73021"):
        assert campaign_path(tmp_path, REC[key]).is_file()
    assert not campaign_path(tmp_path, REC["84183"]).exists()


def test_dangling_link_redownloads_newest(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    campaign_path(tmp_path, REC["84183"]).unlink()
    assert not std.exists()
    m.download_sheet(G)
    assert fake.downloads == [REC["84183"].url] * 2
    assert std.exists() and std.is_symlink()
    assert m.last_sheet.skipped is False


def test_force_redownloads_all_campaigns_and_relinks(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    fake.downloads.clear()
    m.download_sheets([G], skip_existing=False)
    assert sorted(fake.downloads) == sorted(r.url for r in C14_ALL)
    assert "2025-10-21_84183" in os.readlink(std_path(tmp_path))
    assert m.last_result.succeeded == [std_path(tmp_path)]


def test_force_redownload_relinks_copy(tmp_path, monkeypatch):
    deny_links(monkeypatch)
    fake = FakeCampaignProvider(C14)
    fake.fixed_mtime = 1_000_000_000.0  # cel nigdy "nowszy" od kopii (D-5 nie pomaga)
    m = DownloadManager(tmp_path, provider=fake)
    std = m.download_sheet(G)
    assert not std.is_symlink() and "v1" in std.read_text()
    fake.version = "v2"  # ten sam rozmiar
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
        assert data["extra"]["source"]["skorowidz"] == "https://wms"


# =============================================================================
# format pliku (errata 2 N-2)
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
    assert "2024-09-23_81025" in os.readlink(std_path(tmp_path, G2))
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
    assert "2022-03-20_75506" in os.readlink(std)


def test_all_content_mismatch_on_newest_links_previous(tmp_path):
    fake = FakeCampaignProvider(C14, contents={REC["84183"].url: b"<html>404</html>"})
    m = DownloadManager(tmp_path, provider=fake, campaigns="all")
    m.download_sheets([G])
    assert m.last_result.failed == [G]
    assert "2025-04-27_83233" in os.readlink(std_path(tmp_path))
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
# sidecar kampanii obowiazkowy (errata 2 N-1)
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
    assert "2025-04-27_83233" in os.readlink(std)
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
    assert "2025-04-27_83233" in os.readlink(std_path(tmp_path))
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
    assert std.is_symlink() and linked(std) == str(target)


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
# lista arkuszy, rownoleglosc, logi
# =============================================================================


def test_min_year_newest_no_coverage_in_list_is_no_coverage_status(tmp_path):
    events: list[DownloadProgress] = []
    m = DownloadManager(tmp_path, provider=FakeCampaignProvider(C14), min_year=2026)
    m.download_sheets([G], on_progress=events.append)
    assert m.last_result.no_coverage == [G]
    assert m.last_result.failed == [G]
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
# provider bez kampanii (tor plain) i walidacja
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
    m = DownloadManager(tmp_path, provider=p)  # bez wyjatku
    assert m.campaigns == "newest" and m.min_year is None

    def download(godlo, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ncols 1\n")
        return path

    p.download.side_effect = download
    path = m.download_sheet(G)  # tor plain: provider.download, nie resolve_campaigns
    assert p.download.call_count == 1
    assert path.is_file() and not path.is_symlink()


def test_invalid_campaigns_value():
    with pytest.raises(ValidationError):
        DownloadManager(provider=FakeCampaignProvider(C14), campaigns="mosaic")
    with pytest.raises(ValidationError):
        DownloadManager(provider=FakeCampaignProvider(C14), min_year=True)
