"""Polityka ponowien pobierania plikow GUGiK (NMT/NMPT/orto/LAZ/BDOT10k).

Ponawiamy tylko bledy sieci, 429 i 5xx (z Retry-After); inne 4xx koncza
pobieranie od razu z kodem HTTP w DownloadError.status_code.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

PROVIDERS = [
    pytest.param(GugikProvider, "kartograf.providers.pl.gugik", id="nmt"),
    pytest.param(GugikNmptProvider, "kartograf.providers.pl.gugik", id="nmpt"),
    pytest.param(GugikOrtoProvider, "kartograf.providers.pl.gugik_orto", id="orto"),
    pytest.param(GugikLazProvider, "kartograf.providers.pl.gugik_laz", id="laz"),
    pytest.param(Bdot10kProvider, "kartograf.providers.pl.bdot10k", id="bdot10k"),
]


def _http_response(status, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = b""
    response.url = "https://opendata.geoportal.gov.pl/x"
    return response


def _ok_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_content.return_value = iter([b"dane"])
    return response


def _download(provider, out):
    return provider._download_with_retry(
        "https://opendata.geoportal.gov.pl/x", out, 30, "arkusz testowy"
    )


@pytest.mark.parametrize(("cls", "module"), PROVIDERS)
def test_not_found_is_not_retried(cls, module, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _http_response(404)
    provider = cls(session=session)
    with (
        patch(f"{module}.time.sleep") as sleep,
        pytest.raises(DownloadError, match="HTTP 404") as exc_info,
    ):
        _download(provider, tmp_path / "x.bin")
    assert session.get.call_count == 1
    sleep.assert_not_called()
    assert exc_info.value.status_code == 404
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("cls", "module"), PROVIDERS)
def test_throttled_download_waits_retry_after(cls, module, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        _http_response(429, {"Retry-After": "11"}),
        _ok_response(),
    ]
    provider = cls(session=session)
    out = tmp_path / "x.bin"
    with patch(f"{module}.time.sleep") as sleep:
        assert _download(provider, out) == out
    sleep.assert_called_once_with(11)
    assert out.read_bytes() == b"dane"


@pytest.mark.parametrize(("cls", "module"), PROVIDERS)
def test_exhausted_server_errors_keep_status(cls, module, tmp_path):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _http_response(503)
    provider = cls(session=session)
    with (
        patch(f"{module}.time.sleep"),
        pytest.raises(DownloadError) as exc_info,
    ):
        _download(provider, tmp_path / "x.bin")
    assert session.get.call_count == cls.MAX_RETRIES
    assert exc_info.value.status_code == 503


class TestBdot10kSession:
    """BDOT10k bez wstrzyknietej sesji: jedna sesja GUGiK na watek."""

    def test_downloads_and_teryt_share_one_gugik_session(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        teryt = MagicMock()
        teryt.raise_for_status.return_value = None
        teryt.text = "https://opendata.geoportal.gov.pl/bdot10k/GPKG/14/1465_GPKG.zip"
        session.get.side_effect = [_ok_response(), _ok_response(), teryt]
        with patch(
            "kartograf.providers.pl.bdot10k.make_gugik_session", return_value=session
        ) as factory:
            provider = Bdot10kProvider()
            _download(provider, tmp_path / "a.bin")
            _download(provider, tmp_path / "b.bin")
            assert provider._get_teryt_for_point(637000, 486000) == "1465"
        factory.assert_called_once_with()
        assert session.get.call_count == 3

    def test_threads_get_separate_sessions(self):
        import threading

        sessions = []
        with patch(
            "kartograf.providers.pl.bdot10k.make_gugik_session",
            side_effect=lambda: MagicMock(spec=requests.Session),
        ):
            provider = Bdot10kProvider()
            worker = threading.Thread(
                target=lambda: sessions.append(provider._session_for_thread())
            )
            worker.start()
            worker.join()
            sessions.append(provider._session_for_thread())
            sessions.append(provider._session_for_thread())
        assert sessions[0] is not sessions[1]
        assert sessions[1] is sessions[2]

    def test_injected_session_wins(self):
        session = MagicMock(spec=requests.Session)
        with patch("kartograf.providers.pl.bdot10k.make_gugik_session") as factory:
            provider = Bdot10kProvider(session=session)
            assert provider._session_for_thread() is session
        factory.assert_not_called()
