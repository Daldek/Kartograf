"""Tests of the canonical downloader (kartograf.transport.http)."""

import io
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.interrupt import current_stop
from kartograf.transport.http import (
    MAX_RETRY_AFTER,
    SessionPerThread,
    download_to,
    get_with_retry,
    head_signal,
    is_retryable,
    make_gugik_session,
    response_signal,
    retry_wait,
)
from tests.interrupt_fakes import PATIENCE_S, EndlessResponse, interrupted_after_first


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
        assert leftovers == []  # tmp cleaned up after os.replace

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
        assert list(tmp_path.iterdir()) == []  # no tmp or partial files

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
        sleep.assert_called_once_with(2)

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
        assert [call.args for call in sleep.call_args_list] == [(2,), (4,)]

    def test_gugik_session_does_not_multiply_retries(self):
        with make_gugik_session() as session:
            assert session.headers["User-Agent"].startswith("kartograf/")
            assert session.get_adapter("https://").max_retries.total == 0


def _http_response(status, headers=None, content=b""):
    """A real requests response: raise_for_status carries the response in HTTPError."""
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = content
    response.url = "https://example.test/x"
    return response


class TestRetryPolicy:
    """Only network errors, 429 and 5xx are retried; Retry-After takes precedence."""

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


class TestSessionPerThread:
    """One session per thread or the caller's session (D2)."""

    def test_injected_session_wins(self):
        session = MagicMock(spec=requests.Session)
        factory = MagicMock()
        sessions = SessionPerThread(session, factory=factory)
        assert sessions.get() is session
        factory.assert_not_called()

    def test_one_session_per_thread(self):
        sessions = SessionPerThread(factory=lambda: MagicMock(spec=requests.Session))
        seen = []
        worker = threading.Thread(target=lambda: seen.append(sessions.get()))
        worker.start()
        worker.join()
        seen.extend([sessions.get(), sessions.get()])
        assert seen[0] is not seen[1]
        assert seen[1] is seen[2]

    def test_default_factory_is_gugik_session_resolved_lazily(self):
        sessions = SessionPerThread()
        with patch("kartograf.transport.http.make_gugik_session") as factory:
            assert sessions.get() is factory.return_value
        factory.assert_called_once_with()


def _response(status: int, headers: dict, body: bytes = b"") -> requests.Response:
    """A real ``requests.Response`` (headers case-insensitive, raise_for_status)."""
    resp = requests.Response()
    resp.status_code = status
    resp.headers.update(headers)
    resp.raw = io.BytesIO(body)
    resp.url = "https://example.test/p"
    return resp


class TestResponseSignal:
    def test_response_signal_reads_headers_case_insensitively(self):
        resp = _response(
            200,
            {
                "etag": '"abc"',
                "last-modified": "Mon, 12 Oct 2026 08:00:00 GMT",
                "content-length": "123",
            },
        )
        assert response_signal(resp) == {
            "etag": '"abc"',
            "last_modified": "Mon, 12 Oct 2026 08:00:00 GMT",
            "content_length": 123,
        }

    def test_response_signal_missing_headers_are_none(self):
        assert response_signal(_response(200, {})) == {
            "etag": None,
            "last_modified": None,
            "content_length": None,
        }

    def test_response_signal_non_numeric_length_is_none(self):
        resp = _response(200, {"Content-Length": "12x", "ETag": "W/1"})
        assert response_signal(resp)["content_length"] is None
        assert response_signal(resp)["etag"] == "W/1"

    def test_download_to_on_response_sees_last_attempt(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = [
            _response(503, {"ETag": '"stary"'}),
            _response(200, {"ETag": '"nowy"'}, b"dane"),
        ]
        seen = []
        out = tmp_path / "plik.zip"
        with patch("kartograf.transport.http.time.sleep"):
            download_to(
                session,
                "https://example.test/p",
                out,
                timeout=5,
                on_response=lambda r: seen.append(response_signal(r)),
            )
        assert [s["etag"] for s in seen] == ['"nowy"']
        assert out.read_bytes() == b"dane"

    def test_download_to_on_response_called_per_successful_attempt(self, tmp_path):
        def broken_iter(chunk_size):
            yield b"abc"
            raise requests.exceptions.ChunkedEncodingError("przerwane")

        first = _response(200, {"ETag": '"a"'})
        first.iter_content = broken_iter
        session = MagicMock()
        session.get.side_effect = [first, _response(200, {"ETag": '"b"'}, b"x")]
        seen = []
        with patch("kartograf.transport.http.time.sleep"):
            download_to(
                session,
                "https://example.test/p",
                tmp_path / "f",
                timeout=5,
                on_response=lambda r: seen.append(response_signal(r)["etag"]),
            )
        assert seen == ['"a"', '"b"']  # the caller keeps the last one


class TestHeadSignal:
    def test_head_signal_retries_and_returns_headers(self):
        session = MagicMock()
        session.head.side_effect = [
            requests.ConnectionError("boom"),
            _response(200, {"ETag": '"e1"', "Last-Modified": "lm"}),
        ]
        with patch("kartograf.transport.http.time.sleep") as sleep:
            signal = head_signal(session, "https://example.test/p", timeout=5)
        assert signal == {"etag": '"e1"', "last_modified": "lm", "content_length": None}
        assert session.head.call_count == 2
        assert sleep.call_count == 1

    def test_head_signal_404_is_download_error_without_retry(self):
        session = MagicMock()
        session.head.return_value = _response(404, {})
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError) as exc,
        ):
            head_signal(session, "https://example.test/p", timeout=5)
        assert exc.value.status_code == 404
        assert session.head.call_count == 1
        assert sleep.call_count == 0

    def test_head_signal_exhausted_retries_is_download_error(self):
        session = MagicMock()
        session.head.return_value = _response(503, {})
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError) as exc,
        ):
            head_signal(session, "https://example.test/p", timeout=5, retries=2)
        assert exc.value.status_code == 503
        assert session.head.call_count == 2


class TestStoppedPool:
    """A thread of a pool that is stopping (Ctrl-C with several workers, e2e-B
    P2-1) leaves the transport at its next check: no bytes are left on disk and
    no attempt follows."""

    URL = "https://example.test/p"

    def test_download_to_stops_between_chunks_and_removes_the_tmp_file(self, tmp_path):
        body = EndlessResponse()
        session = MagicMock()
        session.get.return_value = body

        def work(item):
            if item == "download":
                download_to(session, self.URL, tmp_path / "plik.tif", timeout=5)
            else:  # the interrupt comes while the body is being written
                deadline = time.monotonic() + PATIENCE_S
                while body.chunks < 3 and time.monotonic() < deadline:
                    time.sleep(0.01)

        error, seconds = interrupted_after_first(work, ["download", "interrupt"])

        assert type(error) is KeyboardInterrupt
        assert seconds < PATIENCE_S / 2
        assert list(tmp_path.iterdir()) == []

    def test_a_retry_pause_ends_with_the_stop(self, tmp_path):
        tried = threading.Event()

        def refuse(*args, **kwargs):
            tried.set()
            raise requests.ConnectionError("reset")

        session = MagicMock()
        session.get.side_effect = refuse

        def work(item):
            if item == "download":
                download_to(session, self.URL, tmp_path / "p", timeout=5, retries=3)
            else:
                assert tried.wait(PATIENCE_S)  # the first attempt failed: a pause

        with patch("kartograf.transport.http.backoff_delay", return_value=600):
            error, seconds = interrupted_after_first(work, ["download", "interrupt"])

        assert type(error) is KeyboardInterrupt
        assert seconds < PATIENCE_S / 2  # not the 600 s of the pause
        assert session.get.call_count == 1  # and no second attempt

    @pytest.mark.parametrize("call", [get_with_retry, head_signal])
    def test_no_request_is_sent_once_the_pool_stopped(self, call):
        session = MagicMock()

        def work(item):
            if item == "request":
                stop = current_stop()
                assert stop is not None and stop.wait(PATIENCE_S)
                call(session, self.URL, timeout=4)

        error, _ = interrupted_after_first(work, ["interrupt", "request"])

        assert type(error) is KeyboardInterrupt
        assert session.method_calls == []
