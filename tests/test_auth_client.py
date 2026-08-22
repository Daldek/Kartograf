"""
Tests for CLMS Authentication Proxy Client.

Tests cover singleton pattern, proxy lifecycle, token management,
proxy requests, file downloads, and cleanup.
"""

import io
import logging
import subprocess
import threading
import time
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.auth.client import AuthProxyClient


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton state before each test."""
    AuthProxyClient._instance = None
    AuthProxyClient._proxy_process = None
    AuthProxyClient._proxy_port = None
    yield
    AuthProxyClient._instance = None
    AuthProxyClient._proxy_process = None
    AuthProxyClient._proxy_port = None


class TestSingleton:
    """Test singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """AuthProxyClient() called twice returns the same object."""
        with patch("kartograf.auth.client.atexit"):
            a = AuthProxyClient()
            b = AuthProxyClient()
        assert a is b

    @patch("kartograf.auth.client.atexit")
    def test_init_registers_atexit(self, mock_atexit):
        """__init__ registers _cleanup with atexit."""
        client = AuthProxyClient()
        mock_atexit.register.assert_called_once_with(client._cleanup)


class TestStartProxy:
    """Test _start_proxy method."""

    @patch("kartograf.auth.client.atexit")
    def test_start_proxy_already_running(self, _atexit):
        """If process is already running, return True immediately."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.poll.return_value = None  # Still running
        client._proxy_process = mock_proc
        assert client._start_proxy() is True

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen")
    def test_start_proxy_success(self, mock_popen, _atexit):
        """Successful proxy start reads port and waits for health."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.stdout.readline.return_value = "12345\n"
        mock_popen.return_value = mock_proc

        with patch.object(client, "_wait_for_proxy", return_value=True):
            assert client._start_proxy() is True
        assert AuthProxyClient._proxy_port == 12345

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen")
    def test_start_proxy_no_port_terminates_process(self, mock_popen, _atexit):
        """Empty port line -> False, and the failed child is cleaned up."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.stdout.readline.return_value = ""
        mock_proc.stderr = io.StringIO("")
        mock_popen.return_value = mock_proc

        assert client._start_proxy() is False
        mock_proc.terminate.assert_called_once()
        assert client._proxy_process is None
        assert AuthProxyClient._proxy_port is None

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen")
    def test_start_proxy_port_read_timeout(self, mock_popen, _atexit):
        """A child that never prints the port must not hang the caller."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.stdout.readline.side_effect = lambda: time.sleep(5) or ""
        mock_proc.stderr = io.StringIO("")
        mock_popen.return_value = mock_proc

        with patch("kartograf.auth.client.PROXY_STARTUP_TIMEOUT", 0.2):
            start = time.perf_counter()
            result = client._start_proxy()
            elapsed = time.perf_counter() - start

        assert result is False
        assert elapsed < 2.0
        mock_proc.terminate.assert_called_once()
        assert client._proxy_process is None

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen")
    def test_start_proxy_drains_stderr(self, mock_popen, _atexit, caplog):
        """stderr of the child is drained by a daemon thread into DEBUG logs."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.stdout.readline.return_value = "12345\n"
        mock_proc.stderr = io.StringIO("line1\nline2\n")
        mock_popen.return_value = mock_proc

        with caplog.at_level(logging.DEBUG, logger="kartograf.auth.client"):
            with patch.object(client, "_wait_for_proxy", return_value=True):
                assert client._start_proxy() is True
            client._stderr_thread.join(1)

        assert client._stderr_thread.daemon is True
        assert "line1" in caplog.text
        assert "line2" in caplog.text

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen", side_effect=OSError("fail"))
    def test_start_proxy_exception(self, _popen, _atexit):
        """Popen raising exception -> return False."""
        client = AuthProxyClient()
        assert client._start_proxy() is False


class TestWaitForProxy:
    """Test _wait_for_proxy method."""

    @patch("kartograf.auth.client.atexit")
    def test_wait_for_proxy_success(self, _atexit):
        """Health check returns 200 -> True."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        client._session = Mock()
        client._session.get.return_value = mock_resp

        assert client._wait_for_proxy() is True

    @patch("kartograf.auth.client.time")
    @patch("kartograf.auth.client.atexit")
    def test_wait_for_proxy_timeout(self, _atexit, mock_time):
        """Health check always fails -> timeout -> False."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        # Simulate time passing beyond PROXY_STARTUP_TIMEOUT
        mock_time.time.side_effect = [0, 0, 100]
        mock_time.sleep = Mock()

        client._session = Mock()
        client._session.get.side_effect = requests.RequestException("conn refused")

        assert client._wait_for_proxy() is False


class TestEnsureProxy:
    """Test _ensure_proxy method."""

    @patch("kartograf.auth.client.atexit")
    def test_ensure_proxy_running(self, _atexit):
        """Port set, process alive -> True."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        client._proxy_process = mock_proc

        assert client._ensure_proxy() is True

    @patch("kartograf.auth.client.atexit")
    def test_ensure_proxy_dead_restarts(self, _atexit):
        """Process died -> calls _start_proxy."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999
        mock_proc = Mock()
        mock_proc.poll.return_value = 1  # Exited
        client._proxy_process = mock_proc

        with patch.object(client, "_start_proxy", return_value=True) as mock_start:
            assert client._ensure_proxy() is True
            mock_start.assert_called_once()


class TestIsAvailable:
    """Test is_available method."""

    @patch("kartograf.auth.client.atexit")
    def test_is_available_true(self, _atexit, monkeypatch):
        """Proxy running and credentials available -> True."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"credentials_available": True}
        client._session = Mock()
        client._session.get.return_value = mock_resp

        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.is_available() is True

    @patch("kartograf.auth.client.atexit")
    def test_is_available_no_proxy(self, _atexit, monkeypatch):
        """Proxy cannot start -> False."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
        client = AuthProxyClient()
        with patch.object(client, "_ensure_proxy", return_value=False):
            assert client.is_available() is False

    @patch("kartograf.auth.client.atexit")
    def test_is_available_no_credentials(self, _atexit, monkeypatch):
        """Proxy running but no credentials -> False."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"credentials_available": False}
        client._session = Mock()
        client._session.get.return_value = mock_resp

        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.is_available() is False

    @patch("kartograf.auth.client.atexit")
    def test_is_available_request_error(self, _atexit, monkeypatch):
        """Health check raises RequestException -> False."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        client._session = Mock()
        client._session.get.side_effect = requests.RequestException("fail")

        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.is_available() is False

    @patch("kartograf.auth.client.atexit")
    def test_is_available_short_circuits_without_creds(self, _atexit, monkeypatch):
        """No env credentials and no Keychain (non-macOS) -> no subprocess."""
        monkeypatch.delenv("CLMS_CREDENTIALS", raising=False)
        client = AuthProxyClient()

        with (
            patch("kartograf.auth.client.platform.system", return_value="Linux"),
            patch("kartograf.auth.client.subprocess.Popen") as mock_popen,
        ):
            assert client.is_available() is False
            mock_popen.assert_not_called()

    @patch("kartograf.auth.client.atexit")
    def test_is_available_with_env_creds_starts_proxy(self, _atexit, monkeypatch):
        """CLMS_CREDENTIALS in env is a credentials source also outside macOS."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"credentials_available": True}
        client._session = Mock()
        client._session.get.return_value = mock_resp

        with (
            patch("kartograf.auth.client.platform.system", return_value="Linux"),
            patch.object(client, "_ensure_proxy", return_value=True) as mock_ensure,
        ):
            assert client.is_available() is True
            mock_ensure.assert_called_once()

    @patch("kartograf.auth.client.atexit")
    @patch("kartograf.auth.client.subprocess.Popen")
    def test_concurrent_is_available_consistent(self, mock_popen, _atexit):
        """Parallel callers must not observe a half-started proxy."""
        client = AuthProxyClient()

        def slow_readline():
            time.sleep(0.3)
            return "12345\n"

        mock_proc = Mock()
        mock_proc.stdout.readline.side_effect = slow_readline
        mock_proc.stderr = io.StringIO("")
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"credentials_available": True}

        def fake_get(url, timeout=None):
            # A half-started proxy yields proxy_url None -> "None/health".
            if not url.startswith("http://127.0.0.1:12345/"):
                raise requests.RequestException(f"unreachable: {url}")
            return mock_resp

        client._session = Mock()
        client._session.get.side_effect = fake_get

        results = []

        def worker():
            results.append(client.is_available())

        with (
            patch("kartograf.auth.client.platform.system", return_value="Darwin"),
            patch.object(client, "_wait_for_proxy", return_value=True),
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)

        assert results == [True, True]
        mock_popen.assert_called_once()


class TestProxyRequest:
    """Test proxy_request method."""

    @patch("kartograf.auth.client.atexit")
    def test_proxy_request_success(self, _atexit):
        """Proxy /proxy endpoint returns 200 -> dict."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status_code": 200,
            "headers": {},
            "body": "ok",
        }
        client._session = Mock()
        client._session.post.return_value = mock_resp

        with patch.object(client, "_ensure_proxy", return_value=True):
            result = client.proxy_request("https://example.com", method="GET")
        assert result == {"status_code": 200, "headers": {}, "body": "ok"}

    @patch("kartograf.auth.client.atexit")
    def test_proxy_request_fail(self, _atexit):
        """Proxy not available -> None."""
        client = AuthProxyClient()
        with patch.object(client, "_ensure_proxy", return_value=False):
            assert client.proxy_request("https://example.com") is None

    @patch("kartograf.auth.client.atexit")
    def test_proxy_request_server_error(self, _atexit):
        """Proxy /proxy endpoint returns 500 -> None."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        client._session = Mock()
        client._session.post.return_value = mock_resp

        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.proxy_request("https://example.com") is None


class TestDownloadFile:
    """Test download_file method."""

    @patch("kartograf.auth.client.atexit")
    def test_download_file_success(self, _atexit, tmp_path):
        """Successful file download via proxy."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b"data123"]
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is True
        assert output.read_bytes() == b"data123"

    @patch("kartograf.auth.client.atexit")
    def test_download_file_failure(self, _atexit, tmp_path):
        """Download endpoint returns 500 -> False."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 500
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is False
        assert not output.exists()
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("kartograf.auth.client.atexit")
    def test_download_file_success_uses_temp_then_rename(self, _atexit, tmp_path):
        """The body lands atomically: no .tmp leftovers, full content in place."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "7"}
        mock_resp.iter_content.return_value = [b"data", b"123"]
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is True
        assert output.read_bytes() == b"data123"
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("kartograf.auth.client.atexit")
    def test_download_file_stream_broken_returns_false_and_leaves_no_file(
        self, _atexit, tmp_path
    ):
        """A truncated stream must not be reported as a successful download."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        def broken_stream(chunk_size=8192):
            yield b"II*\x00"
            raise requests.exceptions.ChunkedEncodingError("Response ended prematurely")

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.iter_content.side_effect = broken_stream
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is False
        assert not output.exists()
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("kartograf.auth.client.atexit")
    def test_download_file_content_length_mismatch_returns_false(
        self, _atexit, tmp_path
    ):
        """Fewer bytes than announced -> False and nothing left behind."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "100"}
        mock_resp.iter_content.return_value = [b"0123456789"]
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is False
        assert not output.exists()
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("kartograf.auth.client.atexit")
    def test_download_file_compressed_body_is_not_a_mismatch(self, _atexit, tmp_path):
        """Content-Length counts compressed bytes; iter_content yields decoded."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 9999

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "21", "Content-Encoding": "gzip"}
        mock_resp.iter_content.return_value = [b"A" * 100]
        client._session = Mock()
        client._session.post.return_value = mock_resp

        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=True):
            assert client.download_file("https://example.com/file", output) is True
        assert output.read_bytes() == b"A" * 100
        assert list(tmp_path.glob("*.tmp")) == []

    @patch("kartograf.auth.client.atexit")
    def test_download_file_proxy_down(self, _atexit, tmp_path):
        """Proxy not available -> False."""
        client = AuthProxyClient()
        output = tmp_path / "out.tif"
        with patch.object(client, "_ensure_proxy", return_value=False):
            assert client.download_file("https://example.com/file", output) is False


class TestCleanup:
    """Test _cleanup and shutdown methods."""

    @patch("kartograf.auth.client.atexit")
    def test_cleanup_terminates_process(self, _atexit):
        """_cleanup terminates and waits for the proxy process."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.wait.return_value = None
        client._proxy_process = mock_proc
        AuthProxyClient._proxy_port = 9999

        client._cleanup()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)
        assert client._proxy_process is None
        assert AuthProxyClient._proxy_port is None

    @patch("kartograf.auth.client.atexit")
    def test_cleanup_kills_on_timeout(self, _atexit):
        """If wait times out, kill the process."""
        client = AuthProxyClient()
        mock_proc = Mock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("proc", 5)
        client._proxy_process = mock_proc
        AuthProxyClient._proxy_port = 9999

        client._cleanup()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @patch("kartograf.auth.client.atexit")
    def test_cleanup_no_process(self, _atexit):
        """_cleanup with no process does nothing."""
        client = AuthProxyClient()
        client._cleanup()  # Should not raise

    @patch("kartograf.auth.client.atexit")
    def test_shutdown_calls_cleanup(self, _atexit):
        """shutdown() delegates to _cleanup()."""
        client = AuthProxyClient()
        with patch.object(client, "_cleanup") as mock_cleanup:
            client.shutdown()
            mock_cleanup.assert_called_once()


class TestProxyUrl:
    """Test proxy_url property."""

    @patch("kartograf.auth.client.atexit")
    def test_proxy_url_with_port(self, _atexit):
        """proxy_url returns URL when port is set."""
        client = AuthProxyClient()
        AuthProxyClient._proxy_port = 12345
        assert client.proxy_url == "http://127.0.0.1:12345"

    @patch("kartograf.auth.client.atexit")
    def test_proxy_url_no_port(self, _atexit):
        """proxy_url returns None when no port."""
        client = AuthProxyClient()
        assert client.proxy_url is None
