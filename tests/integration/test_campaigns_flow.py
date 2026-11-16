"""
ADR-030 campaign flow end-to-end: a REAL ``GugikProvider`` on recorded WFS
GetFeature answers of the NMT index (``tests/fixtures/gugik_wfs/
real_2026_10_15``, ``sheet_nmt_evrf2007_<sheet>.xml``) + a download session
returning a small ASC with the sheet frame (EPSG:2180) for opendata URLs.
"""

import json
import os
import re
from pathlib import Path
from unittest.mock import Mock

import rasterio
import requests

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.links import linked_version
from kartograf.download.manager import DownloadManager
from kartograf.providers.pl.gugik import GugikProvider
from tests.conftest import render_wfs_body, wfs_endpoint, wfs_fixture, wfs_response

# Recorded sheet: 1m ASC flights 2019, 2021, 2022, 2024 and an ASCII NMT 1m
# archive (.zip) of the 2019 delivery, plus 0.5m/0.6m/5m/XYZ records
G = "N-33-77-B-c-3-3"
# Recorded sheet: 1m ASC flights 2021, 2022, 2024 (two) and the 2019 grid of
# campaign 72675 published under a `.xyz` name (an AAIGrid inside)
G2 = "N-33-69-A-d-1-3"
SEGMENT = Path("nmt/pl_1992_1m_evrf2007")
NMT_EVRF2007 = wfs_endpoint("nmt_evrf2007")
OPENDATA = "https://opendata.geoportal.gov.pl/"


def _response(body: str) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def asc_bytes(sheet: str, value: int) -> bytes:
    """Small 5x5 ASC with xllcorner/yllcorner from the sheet frame (EPSG:2180)."""
    frame = SheetParser(sheet).get_bbox("EPSG:2180")
    rows = "\n".join(" ".join([str(value)] * 5) for _ in range(5))
    header = (
        f"ncols 5\nnrows 5\nxllcorner {frame.min_x}\nyllcorner {frame.min_y}\n"
        f"cellsize 1\nnodata_value -9999\n"
    )
    return (header + rows + "\n").encode("ascii")


def recorded_session(sheet: str) -> Mock:
    """NMT EVRF2007 WFS -> the recorded answer of the sheet; any other index
    service -> an empty collection; opendata file -> ASC whose value is the
    first numeric segment of the file name."""
    answer = wfs_fixture(f"sheet_nmt_evrf2007_{sheet}.xml")
    session = Mock(spec=requests.Session)

    def get(url, *args, **kwargs):
        if url.startswith(OPENDATA):
            name = url.rsplit("/", 1)[-1]
            file_sheet = re.sub(r"^\d+_\d+_", "", name).rsplit(".", 1)[0]
            response = _response("")
            response.iter_content = Mock(
                return_value=[asc_bytes(file_sheet, int(name.split("_")[0]))]
            )
            return response
        if url.startswith(f"{NMT_EVRF2007}?"):
            return wfs_response(answer)
        return wfs_response(render_wfs_body([]))

    session.get = Mock(side_effect=get)
    return session


def file_requests(session: Mock) -> list[str]:
    """Opendata file URLs the session was asked for."""
    return [
        c.args[0] for c in session.get.call_args_list if c.args[0].startswith(OPENDATA)
    ]


def std_path(tmp_path: Path, sheet: str) -> Path:
    parts = sheet.split("-")
    return tmp_path / SEGMENT / "-".join(parts[:2]) / Path(*parts[2:]) / f"{sheet}.asc"


def sidecar(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def test_end_to_end_all_on_recorded_wfs_answer(tmp_path):
    """Every 1m ASC flight of the sheet; the ASCII NMT archive of the 2019
    delivery and the other resolutions/formats are never downloaded."""
    session = recorded_session(G)
    m = DownloadManager(
        provider=GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        ),
        all_campaigns=True,
        root=tmp_path,
    )
    m.download_sheet(G)

    files = m.storage.list_files("**/*.asc", versions=True)
    assert sorted(p.parent.name.rsplit("_", 1)[0] for p in files) == [
        "2019-04-02_72759",
        "2021-03-30_74601",
        "2022-03-22_76001",
        "2024-09-21_80196",
    ]
    assert all(url.endswith(".asc") for url in file_requests(session))
    assert len(file_requests(session)) == 4
    meta = json.loads(sidecar(std_path(tmp_path, G)).read_text(encoding="utf-8"))
    assert meta["extra"]["source"]["full_sheet"] is True
    assert meta["extra"]["source"]["index_url"] == NMT_EVRF2007
    assert meta["extra"]["source"]["layer"] == "SkorowidzNMT2024"
    assert meta["extra"]["campaign"]["survey_work_id"] == "GK-FOTO.6201.26.2024"
    assert "2024-09-21_80196" in str(linked_version(std_path(tmp_path, G)))


def test_download_sheet_returns_standard_path_readable_by_rasterio(tmp_path):
    m = DownloadManager(
        provider=GugikProvider(
            session=recorded_session(G), vertical_crs="EVRF2007", resolution="1m"
        ),
        root=tmp_path,
    )
    result = m.download_sheet(G)
    (path,) = result.succeeded
    assert path == std_path(tmp_path, G)
    assert result.files[G][0].version_path.exists()
    [campaign_file] = m.storage.list_files("**/*.asc", versions=True)
    assert not path.is_symlink() and os.path.samefile(path, campaign_file)
    meta = json.loads(sidecar(path).read_text(encoding="utf-8"))
    assert meta["extra"]["link"] == "hardlink"
    with rasterio.open(path) as src, rasterio.open(campaign_file) as direct:
        assert src.read(1).tolist() == direct.read(1).tolist()
        assert src.read(1)[0, 0] == 80196  # newest campaign
        assert src.shape == (5, 5)


def test_exports():
    from kartograf import CampaignRef
    from kartograf.download.campaigns import CampaignRef as Original

    assert CampaignRef is Original


def test_end_to_end_all_keeps_grid_published_under_xyz_name(tmp_path):
    """The 2019 record declares ARC/INFO ASCII GRID and links a ``.xyz`` file
    (campaign 72675: an AAIGrid under that name) - a grid campaign stored as
    ``.asc`` beside the four ``.asc`` flights; the newest is linked."""
    session = recorded_session(G2)
    m = DownloadManager(
        provider=GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        ),
        all_campaigns=True,
        root=tmp_path,
    )
    m.download_sheet(G2)

    asc = m.storage.list_files("**/*.asc", versions=True)
    assert sorted(p.parent.name.rsplit("_", 1)[0] for p in asc) == [
        "2019-04-29_72675",
        "2021-05-31_74160",
        "2022-03-20_75506",
        "2024-07-21_81616",
        "2024-09-23_81025",
    ]
    assert [url for url in file_requests(session) if "72675" in url] == [
        f"{OPENDATA}NumDaneWys/NMT/72675/72675_858106_{G2}.xyz"
    ]
    assert list(tmp_path.rglob("*.xyz")) == []
    assert "2024-09-23_81025" in str(linked_version(std_path(tmp_path, G2)))


def test_newest_uses_local_campaign_when_skorowidz_unreachable(tmp_path):
    """I-1 on a real ``GugikProvider`` without ``MetadataCache``: the next
    ``download_sheet`` queries the index (skorowidz); network failure -> local
    campaign."""
    from unittest.mock import patch

    m = DownloadManager(
        provider=GugikProvider(
            session=recorded_session(G), vertical_crs="EVRF2007", resolution="1m"
        ),
        root=tmp_path,
    )
    std = m.download_sheet(G).succeeded[0]
    before = str(linked_version(std))
    assert "2024-09-21_80196" in before

    offline = Mock(spec=requests.Session)
    offline.get = Mock(side_effect=requests.ConnectionError("GUGiK lezy"))
    m2 = DownloadManager(
        provider=GugikProvider(
            session=offline, vertical_crs="EVRF2007", resolution="1m"
        ),
        root=tmp_path,
    )
    with patch("kartograf.transport.http.time.sleep"):
        result = m2.download_sheet(G)

    assert offline.get.called
    assert result.succeeded == [] and str(linked_version(std)) == before
    assert result.skipped == [G]
    assert result.files[G][0].path == std
    assert "connection broken or refused" in result.files[G][0].unverified
