"""Retry policy for downloading GUGiK files (NMT/NMPT/orto/LAZ/BDOT10k),
CORINE and SoilGrids (review 2026-10-06 D1/N9).

Only network errors, 429 and 5xx are retried (with Retry-After); other 4xx end
the download at once with the HTTP code in DownloadError.status_code.
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.soilgrids import SoilGridsProvider

_URL = "https://opendata.geoportal.gov.pl/x"
_SLEEP = "kartograf.transport.http.time.sleep"
_BBOX_2180 = BBox(450000, 550000, 460000, 560000, "EPSG:2180")


def _sheet(cls):
    """NMT/NMPT/orto: a sheet with a resolved index record -> file."""

    def run(provider, out):
        record = SimpleNamespace(url=_URL)
        with patch.object(provider, "_resolve_sheet", return_value=record):
            return provider.download("N-34-130-D-d-2-4", out)

    return run


def _laz(provider, out):
    return provider.download(_URL, out)


def _bdot10k(provider, out):
    return provider.download_by_admin_unit("1465", out, format="SHP")


def _corine(provider, out):
    return provider._download_via_wms(_BBOX_2180, out, 2018, 30)


def _soilgrids(provider, out):
    return provider._download_via_wcs(
        (19.0, 50.0, 19.1, 50.1), out, "soc", "0-5cm", "mean", 30
    )


# Each provider through its OWN file download path (not through the transport
# directly): proof that all the old copies of the loop go through download_to.
PROVIDERS = [
    pytest.param(GugikProvider, _sheet(GugikProvider), ".bin", id="nmt"),
    pytest.param(GugikNmptProvider, _sheet(GugikNmptProvider), ".bin", id="nmpt"),
    pytest.param(GugikOrtoProvider, _sheet(GugikOrtoProvider), ".bin", id="orto"),
    pytest.param(GugikLazProvider, _laz, ".bin", id="laz"),
    pytest.param(Bdot10kProvider, _bdot10k, ".zip", id="bdot10k"),
    pytest.param(CorineProvider, _corine, ".png", id="corine"),
    pytest.param(SoilGridsProvider, _soilgrids, ".tif", id="soilgrids"),
]


def _http_response(status, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = b""
    response.url = _URL
    return response


def _ok_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_content.return_value = iter([b"dane"])
    return response


@pytest.mark.parametrize(("cls", "download", "suffix"), PROVIDERS)
def test_not_found_is_not_retried(cls, download, suffix, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _http_response(404)
    provider = cls(session=session)
    with (
        patch(_SLEEP) as sleep,
        pytest.raises(DownloadError, match="HTTP 404") as exc_info,
    ):
        download(provider, tmp_path / "x.bin")
    assert session.get.call_count == 1
    sleep.assert_not_called()
    assert exc_info.value.status_code == 404
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("cls", "download", "suffix"), PROVIDERS)
def test_throttled_download_waits_retry_after(cls, download, suffix, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        _http_response(429, {"Retry-After": "11"}),
        _ok_response(),
    ]
    provider = cls(session=session)
    out = tmp_path / "x.bin"
    with patch(_SLEEP) as sleep:
        assert download(provider, out) == out.with_suffix(suffix)
    sleep.assert_called_once_with(11)
    assert out.with_suffix(suffix).read_bytes() == b"dane"
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"x{suffix}"]


@pytest.mark.parametrize(("cls", "download", "suffix"), PROVIDERS)
def test_exhausted_server_errors_keep_status(cls, download, suffix, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _http_response(503)
    provider = cls(session=session)
    with (
        patch(_SLEEP) as sleep,
        pytest.raises(DownloadError, match="po 3 probach") as exc_info,
    ):
        download(provider, tmp_path / "x.bin")
    assert session.get.call_count == cls.MAX_RETRIES
    assert exc_info.value.status_code == 503
    # one backoff exponent for all providers (D1, 2026-10-07)
    assert [c.args for c in sleep.call_args_list] == [(2,), (4,)]


def _windows_rename(self, target):
    """Path.rename with Windows semantics: an existing target = FileExistsError."""
    if Path(target).exists():
        raise FileExistsError(f"[WinError 183] {target}")
    return os.replace(self, target)


@pytest.mark.parametrize(("cls", "download", "suffix"), PROVIDERS)
def test_redownload_overwrites_existing_file(cls, download, suffix, tmp_path):
    """--force over an already downloaded file: an atomic write through os.replace.

    The old copies in the providers used ``Path.rename``, which on Windows
    does not overwrite an existing file (review 2026-10-06 D1 point 3).
    """
    out = tmp_path / "x.bin"
    out.with_suffix(suffix).write_bytes(b"stare")
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _ok_response()
    provider = cls(session=session)
    with patch.object(Path, "rename", _windows_rename):
        assert download(provider, out) == out.with_suffix(suffix)
    assert out.with_suffix(suffix).read_bytes() == b"dane"


class TestBdot10kSession:
    """BDOT10k without an injected session: one GUGiK session per thread."""

    def test_downloads_and_teryt_share_one_gugik_session(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        teryt = MagicMock()
        teryt.raise_for_status.return_value = None
        teryt.text = "https://opendata.geoportal.gov.pl/bdot10k/GPKG/14/1465_GPKG.zip"
        session.get.side_effect = [_ok_response(), _ok_response(), teryt]
        with patch(
            "kartograf.transport.http.make_gugik_session", return_value=session
        ) as factory:
            provider = Bdot10kProvider()
            _bdot10k(provider, tmp_path / "a.bin")
            _bdot10k(provider, tmp_path / "b.bin")
            assert provider._get_teryt_for_point(637000, 486000) == "1465"
        factory.assert_called_once_with()
        assert session.get.call_count == 3

    def test_threads_get_separate_sessions(self):
        import threading

        sessions = []
        with patch(
            "kartograf.transport.http.make_gugik_session",
            side_effect=lambda: MagicMock(spec=requests.Session),
        ):
            provider = Bdot10kProvider()
            worker = threading.Thread(
                target=lambda: sessions.append(provider._sessions.get())
            )
            worker.start()
            worker.join()
            sessions.append(provider._sessions.get())
            sessions.append(provider._sessions.get())
        assert sessions[0] is not sessions[1]
        assert sessions[1] is sessions[2]

    def test_injected_session_wins(self):
        session = MagicMock(spec=requests.Session)
        with patch("kartograf.transport.http.make_gugik_session") as factory:
            provider = Bdot10kProvider(session=session)
            assert provider._sessions.get() is session
        factory.assert_not_called()


def _json_ok(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _teryt_ok():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = "https://opendata.geoportal.gov.pl/bdot10k/GPKG/14/1465_GPKG.zip"
    return response


_KLADY = "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"


def _cuzk_query(session):
    from kartograf.providers.cuzk.client import CuzkClient

    return CuzkClient(session=session).query(_KLADY, 24, where="MAPNOM='CTES96'")


def _teryt_query(session):
    return Bdot10kProvider(session=session)._get_teryt_for_point(637000, 486000)


SINGLE_QUERIES = [
    pytest.param(_cuzk_query, _json_ok({"features": [{"a": 1}]}), id="cuzk_query"),
    pytest.param(_teryt_query, _teryt_ok(), id="bdot10k_teryt"),
]


class TestSingleQueryRetries:
    """CuzkClient.query and the BDOT10k TERYT queries go through get_with_retry (N5)."""

    @pytest.mark.parametrize(("query", "ok"), SINGLE_QUERIES)
    def test_connection_error_is_retried(self, query, ok):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = [requests.ConnectionError("reset"), ok]
        with patch("kartograf.transport.http.time.sleep") as sleep:
            result = query(session)
        assert result in ([{"a": 1}], "1465")
        assert session.get.call_count == 2
        sleep.assert_called_once_with(2)

    @pytest.mark.parametrize(("query", "ok"), SINGLE_QUERIES)
    def test_not_found_is_not_retried(self, query, ok):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = _http_response(404)
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="HTTP 404") as exc_info,
        ):
            query(session)
        assert session.get.call_count == 1
        sleep.assert_not_called()
        assert exc_info.value.status_code == 404

    def test_cuzk_invalid_json_is_not_retried(self):
        session = MagicMock(spec=requests.Session)
        bad = MagicMock()
        bad.raise_for_status.return_value = None
        bad.json.side_effect = ValueError("not json")
        session.get.return_value = bad
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="nieudane"),
        ):
            _cuzk_query(session)
        assert session.get.call_count == 1
        sleep.assert_not_called()
