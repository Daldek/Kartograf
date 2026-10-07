"""
Przeplyw kampanii ADR-030 end-to-end: PRAWDZIWY ``GugikProvider`` na surowych
odpowiedziach GetFeatureInfo (``tests/fixtures/gugik_skorowidz/real_2026_10_06``)
+ sesja pobran oddajaca maly ASC z ramy arkusza (EPSG:2180) dla URL-i opendata.
"""

import json
import os
import re
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import rasterio
import requests

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.links import linked_campaign
from kartograf.download.manager import DownloadManager
from kartograf.providers.pl.gugik import GugikProvider

FIXTURES = Path(__file__).parent / "fixtures"
REAL = FIXTURES / "gugik_skorowidz" / "real_2026_10_06"
EMPTY = (FIXTURES / "gugik_skorowidz" / "empty.body").read_text(encoding="utf-8")
XYZ_HEAD = (
    FIXTURES / "gugik_asc" / "72675_858113_N-33-69-A-d-3-2.head.xyz"
).read_bytes()

G = "N-34-139-C-a-3-1"
G2 = "N-33-69-A-d-3-2"
SEGMENT = Path("nmt/pl_1992_1m_evrf2007")


def _response(body: str) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def asc_bytes(godlo: str, value: int) -> bytes:
    """Maly ASC 5x5 z xllcorner/yllcorner z ramy arkusza (EPSG:2180)."""
    frame = SheetParser(godlo).get_bbox("EPSG:2180")
    rows = "\n".join(" ".join([str(value)] * 5) for _ in range(5))
    header = (
        f"ncols 5\nnrows 5\nxllcorner {frame.min_x}\nyllcorner {frame.min_y}\n"
        f"cellsize 1\nnodata_value -9999\n"
    )
    return (header + rows + "\n").encode("ascii")


def routed_session(path_for_layer, downloads=None) -> Mock:
    """GetFeatureInfo -> surowe body warstwy; plik opendata -> ASC (albo
    ``downloads[url]``); wartosc ASC = pierwszy segment liczbowy nazwy pliku."""
    session = Mock(spec=requests.Session)

    def get(url, **kwargs):
        if url.startswith("https://opendata.geoportal.gov.pl/"):
            if downloads and url in downloads:
                content = downloads[url]
            else:
                name = url.rsplit("/", 1)[-1]
                godlo = re.sub(r"^\d+_\d+_", "", name).rsplit(".", 1)[0]
                content = asc_bytes(godlo, int(name.split("_")[0]))
            response = _response("")
            response.iter_content = Mock(return_value=[content])
            return response
        layer = parse_qs(urlparse(url).query)["LAYERS"][0]
        path = path_for_layer(layer)
        return _response(path.read_text(encoding="utf-8") if path else EMPTY)

    session.get = Mock(side_effect=get)
    return session


def c14_session(godlo: str) -> Mock:
    def path_for_layer(layer):
        path = REAL / "nmt" / "c14" / f"{godlo}_EVRF2007_{layer}.html"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def nmt_session(godlo: str, prefix: str, downloads=None) -> Mock:
    def path_for_layer(layer):
        path = REAL / "nmt" / godlo / f"{prefix}__{layer}.body"
        return path if path.exists() else None

    return routed_session(path_for_layer, downloads)


def std_path(tmp_path: Path, godlo: str) -> Path:
    parts = godlo.split("-")
    return tmp_path / SEGMENT / "-".join(parts[:2]) / Path(*parts[2:]) / f"{godlo}.asc"


def sidecar(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def test_end_to_end_all_on_real_c14_bodies(tmp_path):
    m = DownloadManager(
        tmp_path, provider=GugikProvider(session=c14_session(G)), campaigns="all"
    )
    m.download_sheet(G)

    files = m.storage.list_files(campaigns=True)
    root = tmp_path / SEGMENT / "kampanie"
    assert sorted(p.relative_to(root).parts[0] for p in files) == [
        "2019-04-18_73021",
        "2023-09-05_78047",
        "2025-04-27_83233",
        "2025-10-21_84183",
    ]
    meta = json.loads(sidecar(std_path(tmp_path, G)).read_text(encoding="utf-8"))
    assert meta["extra"]["source"]["full_sheet"] is False
    assert meta["extra"]["campaign"]["zgloszenie"] == "DFT.7201.053.2025"
    assert "2025-10-21_84183" in str(linked_campaign(std_path(tmp_path, G)))


def test_download_sheet_returns_standard_path_readable_by_rasterio(tmp_path):
    m = DownloadManager(tmp_path, provider=GugikProvider(session=c14_session(G)))
    path = m.download_sheet(G)

    assert path == std_path(tmp_path, G)
    [campaign_file] = m.storage.list_files(campaigns=True)
    assert not path.is_symlink() and os.path.samefile(path, campaign_file)
    meta = json.loads(sidecar(path).read_text(encoding="utf-8"))
    assert meta["extra"]["link"] == "hardlink"
    with rasterio.open(path) as src, rasterio.open(campaign_file) as direct:
        assert src.read(1).tolist() == direct.read(1).tolist()
        assert src.read(1)[0, 0] == 84183  # najnowsza kampania
        assert src.shape == (5, 5)


def test_exports():
    from kartograf import CampaignRef, SheetFetch
    from kartograf.download.campaigns import CampaignRef as Original
    from kartograf.download.manager import SheetFetch as OriginalFetch

    assert CampaignRef is Original and SheetFetch is OriginalFetch


def test_end_to_end_all_with_real_xyz_campaign(tmp_path):
    url = (
        "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/72675/"
        "72675_858113_N-33-69-A-d-3-2.xyz"
    )
    session = nmt_session(G2, "nmt1_evr", downloads={url: XYZ_HEAD})
    m = DownloadManager(
        tmp_path, provider=GugikProvider(session=session), campaigns="all"
    )
    m.download_sheet(G2)

    asc = m.storage.list_files("**/*.asc", campaigns=True)
    assert len(asc) == 5
    assert any(
        p.as_posix().endswith(f"2019-04-29_72675/N-33/69/A/d/3/2/{G2}.asc") for p in asc
    )
    assert list(tmp_path.rglob("*.xyz")) == []
    [old] = [p for p in asc if "2019-04-29_72675" in p.as_posix()]
    meta = json.loads(sidecar(old).read_text(encoding="utf-8"))
    assert meta["extra"]["source"]["url"].endswith(".xyz")
    assert "2024-09-23_81025" in str(linked_campaign(std_path(tmp_path, G2)))


def test_newest_uses_local_campaign_when_skorowidz_unreachable(tmp_path):
    """I-1 na prawdziwym ``GugikProvider`` bez ``MetadataCache``: kolejny
    ``download_sheet`` pyta skorowidz; awaria sieci -> lokalna kampania."""
    from unittest.mock import patch

    m = DownloadManager(tmp_path, provider=GugikProvider(session=c14_session(G)))
    std = m.download_sheet(G)
    before = str(linked_campaign(std))
    assert "2025-10-21_84183" in before

    offline = Mock(spec=requests.Session)
    offline.get = Mock(side_effect=requests.ConnectionError("GUGiK lezy"))
    m2 = DownloadManager(tmp_path, provider=GugikProvider(session=offline))
    with patch("kartograf.transport.http.time.sleep"):
        path = m2.download_sheet(G)

    assert offline.get.called  # bez cache rekordow: zapytanie przy kazdym wywolaniu
    assert path == std and str(linked_campaign(std)) == before
    assert m2.last_sheet.skipped is True
    assert "GUGiK lezy" in m2.last_sheet.unverified
