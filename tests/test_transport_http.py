"""Testy kanonicznego downloadera (kartograf.transport.http)."""

import os
import threading
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.transport.http import (
    MAX_RETRY_AFTER,
    download_to,
    get_with_retry,
    is_retryable,
    make_gugik_session,
    retry_wait,
)


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


def _http_response(status, headers=None, content=b""):
    """Prawdziwa odpowiedz requests: raise_for_status niesie response w HTTPError."""
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = content
    response.url = "https://example.test/x"
    return response


class TestRetryPolicy:
    """Ponawiamy tylko bledy sieci, 429 i 5xx; Retry-After ma pierwszenstwo."""

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
    def test_client_error_is_not_retryable(self, status):
        error = requests.HTTPError(response=_http_response(status))
        assert is_retryable(error) is False

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_throttle_and_server_errors_are_retryable(self, status):
        error = requests.HTTPError(response=_http_response(status))
        assert is_retryable(error) is True

    @pytest.mark.parametrize(
        "error",
        [
            requests.ConnectionError("reset"),
            requests.Timeout("timeout"),
            requests.exceptions.ChunkedEncodingError("przerwane"),
            requests.RequestException("ogolny"),
            requests.HTTPError("bez odpowiedzi"),
        ],
    )
    def test_transport_errors_are_retryable(self, error):
        assert is_retryable(error) is True

    def test_retry_after_seconds_override_backoff(self):
        error = requests.HTTPError(response=_http_response(429, {"Retry-After": "7"}))
        assert retry_wait(error, 1) == 7

    def test_retry_after_shorter_than_backoff_keeps_backoff(self):
        error = requests.HTTPError(response=_http_response(503, {"Retry-After": "0"}))
        assert retry_wait(error, 4) == 4

    def test_retry_after_is_capped(self):
        error = requests.HTTPError(
            response=_http_response(503, {"Retry-After": "3600"})
        )
        assert retry_wait(error, 1) == MAX_RETRY_AFTER

    def test_retry_after_http_date(self):
        when = datetime.now(UTC) + timedelta(seconds=30)
        error = requests.HTTPError(
            response=_http_response(503, {"Retry-After": format_datetime(when, True)})
        )
        assert 25 <= retry_wait(error, 1) <= 31

    @pytest.mark.parametrize("value", ["jutro", "-5", ""])
    def test_invalid_retry_after_falls_back_to_backoff(self, value):
        error = requests.HTTPError(response=_http_response(503, {"Retry-After": value}))
        assert retry_wait(error, 2) == 2

    def test_transport_error_uses_backoff(self):
        assert retry_wait(requests.ConnectionError("reset"), 2) == 2


class TestGetWithRetryPolicy:
    def test_not_found_fails_at_once_with_status(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = _http_response(404)
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="HTTP 404") as exc_info,
        ):
            get_with_retry(session, "https://example.test/gfi", timeout=4)
        assert session.get.call_count == 1
        sleep.assert_not_called()
        assert exc_info.value.status_code == 404

    def test_throttled_request_waits_retry_after(self):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = [
            _http_response(429, {"Retry-After": "9"}),
            _http_response(200, content=b"ok"),
        ]
        with patch("kartograf.transport.http.time.sleep") as sleep:
            result = get_with_retry(session, "https://example.test/gfi", timeout=4)
        assert result.content == b"ok"
        sleep.assert_called_once_with(9)

    def test_exhausted_server_errors_keep_status(self):
        session = MagicMock(spec=requests.Session)
        session.get.return_value = _http_response(503)
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError) as exc_info,
        ):
            get_with_retry(session, "https://example.test/gfi", timeout=4)
        assert exc_info.value.status_code == 503


class TestDownloadToPolicy:
    def test_not_found_fails_at_once_without_tmp(self, tmp_path):
        session = MagicMock()
        session.get.return_value = _http_response(404)
        out = tmp_path / "plik.tif"
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="HTTP 404") as exc_info,
        ):
            download_to(session, "https://example.test/p", out, timeout=5)
        assert session.get.call_count == 1
        sleep.assert_not_called()
        assert exc_info.value.status_code == 404
        assert list(tmp_path.iterdir()) == []

    def test_unavailable_server_waits_retry_after(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = [
            _http_response(503, {"Retry-After": "5"}),
            _mock_response(),
        ]
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.time.sleep") as sleep:
            download_to(session, "https://example.test/p", out, timeout=5)
        assert out.read_bytes() == b"abcdef"
        sleep.assert_called_once_with(5)
