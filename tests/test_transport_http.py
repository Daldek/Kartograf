"""Testy kanonicznego downloadera (kartograf.transport.http)."""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.transport.http import download_to, get_with_retry, make_gugik_session


def _mock_response(chunks=(b"abc", b"def")):
    resp = MagicMock()
    resp.iter_content.return_value = iter(chunks)
    resp.raise_for_status.return_value = None
    return resp


class TestDownloadTo:
    def test_atomic_write_and_content(self, tmp_path):
        session = MagicMock()
        session.get.return_value = _mock_response()
        out = tmp_path / "sub" / "plik.tif"
        result = download_to(session, "https://example.test/plik", out, timeout=5)
        assert result == out
        assert out.read_bytes() == b"abcdef"
        leftovers = [p for p in out.parent.iterdir() if p.name != "plik.tif"]
        assert leftovers == []  # tmp sprzatniety po os.replace

    def test_temp_name_uses_pid_and_thread(self, tmp_path):
        seen = {}
        real_replace = os.replace

        def spy_replace(src, dst):
            seen["src"] = str(src)
            return real_replace(src, dst)

        session = MagicMock()
        session.get.return_value = _mock_response()
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.os.replace", side_effect=spy_replace):
            download_to(session, "https://example.test/p", out, timeout=5)
        assert f".{os.getpid()}_{threading.get_ident()}.tmp" in seen["src"]

    def test_retry_then_success(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = [
            requests.ConnectionError("boom"),
            _mock_response(),
        ]
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.time.sleep") as mock_sleep:
            result = download_to(
                session, "https://example.test/p", out, timeout=5, retries=3
            )
        assert result.read_bytes() == b"abcdef"
        assert mock_sleep.call_count == 1

    def test_exhausted_retries_raise_download_error_and_cleanup(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("boom")
        out = tmp_path / "plik.tif"
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError),
        ):
            download_to(session, "https://example.test/p", out, timeout=5, retries=3)
        assert session.get.call_count == 3
        assert list(tmp_path.iterdir()) == []  # zadnych tmp ani czesciowych plikow

    def test_error_mid_stream_cleans_tmp(self, tmp_path):
        def broken_iter(chunk_size):
            yield b"abc"
            raise requests.exceptions.ChunkedEncodingError("przerwane")

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.iter_content.side_effect = broken_iter
        session = MagicMock()
        session.get.return_value = resp
        out = tmp_path / "plik.tif"
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError),
        ):
            download_to(session, "https://example.test/p", out, timeout=5, retries=1)
        assert list(tmp_path.iterdir()) == []


class TestGetWithRetry:
    def test_connection_failure_retries_same_request(self):
        session = MagicMock(spec=requests.Session)
        response = requests.Response()
        response.status_code = 200
        response._content = b"recovered"
        session.get.side_effect = [requests.ConnectionError("reset"), response]
        with patch("kartograf.transport.http.time.sleep") as sleep:
            result = get_with_retry(session, "https://example.test/gfi", timeout=4)
        assert result.content == b"recovered"
        assert session.get.call_args_list[0] == session.get.call_args_list[1]
        sleep.assert_called_once_with(1)

    def test_http_failure_exhausts_retries(self):
        session = MagicMock(spec=requests.Session)
        response = requests.Response()
        response.status_code = 503
        session.get.return_value = response
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="warstwa 2026.*po 3 probach"),
        ):
            get_with_retry(
                session,
                "https://example.test/gfi",
                timeout=4,
                description="warstwa 2026",
            )
        assert session.get.call_count == 3
        assert [call.args for call in sleep.call_args_list] == [(1,), (2,)]

    def test_gugik_session_does_not_multiply_retries(self):
        with make_gugik_session() as session:
            assert session.headers["User-Agent"].startswith("kartograf/")
            assert session.get_adapter("https://").max_retries.total == 0
