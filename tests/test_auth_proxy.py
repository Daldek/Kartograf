"""
Tests for CLMS Authentication Proxy Server.

Tests cover CLMSCredentials (keychain loading, token exchange),
ProxyHandler endpoints, and server startup.
"""

import json
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from kartograf.auth.proxy import CLMSCredentials, ProxyHandler, run_server


@pytest.fixture(autouse=True)
def _clean_clms_env(monkeypatch):
    """CLMS_CREDENTIALS from the developer shell must not leak into tests."""
    monkeypatch.delenv("CLMS_CREDENTIALS", raising=False)


class TestCLMSCredentialsEnvLoad:
    """Test CLMSCredentials.load_from_env (CLMS_CREDENTIALS)."""

    def test_load_from_env_success(self, monkeypatch):
        """Valid JSON in CLMS_CREDENTIALS -> True and credentials cached."""
        monkeypatch.setenv(
            "CLMS_CREDENTIALS",
            json.dumps(
                {
                    "client_id": "x",
                    "private_key": "k",
                    "token_uri": "https://land.copernicus.eu/@@oauth2-token",
                }
            ),
        )

        creds = CLMSCredentials()
        assert creds.load_from_env() is True
        assert creds._credentials["client_id"] == "x"

    def test_load_from_env_invalid_json(self, monkeypatch):
        """Malformed JSON -> False, no exception, no credentials."""
        monkeypatch.setenv("CLMS_CREDENTIALS", "{not json")

        creds = CLMSCredentials()
        assert creds.load_from_env() is False
        assert creds._credentials is None

    def test_load_from_env_missing(self, monkeypatch):
        """CLMS_CREDENTIALS not set -> False."""
        monkeypatch.delenv("CLMS_CREDENTIALS", raising=False)

        creds = CLMSCredentials()
        assert creds.load_from_env() is False

    def test_load_from_env_missing_required_key(self, monkeypatch):
        """JSON without private_key -> False (incomplete credentials)."""
        monkeypatch.setenv("CLMS_CREDENTIALS", json.dumps({"client_id": "x"}))

        creds = CLMSCredentials()
        assert creds.load_from_env() is False
        assert creds._credentials is None


class TestCLMSCredentialsKeychainLoad:
    """Test CLMSCredentials.load_from_keychain."""

    @patch("kartograf.auth.proxy.platform.system", return_value="Linux")
    def test_load_from_keychain_not_darwin(self, _sys):
        """Non-macOS platform -> False."""
        creds = CLMSCredentials()
        assert creds.load_from_keychain() is False

    @patch("kartograf.auth.proxy.platform.system", return_value="Darwin")
    @patch("kartograf.auth.proxy.subprocess.run")
    def test_load_from_keychain_success(self, mock_run, _sys):
        """macOS + valid JSON from security -> True."""
        creds_json = json.dumps(
            {"client_id": "test", "private_key": "pk", "token_uri": "https://tok"}
        )
        mock_run.return_value = Mock(returncode=0, stdout=creds_json + "\n")

        creds = CLMSCredentials()
        assert creds.load_from_keychain() is True
        assert creds._credentials["client_id"] == "test"

    @patch("kartograf.auth.proxy.platform.system", return_value="Darwin")
    @patch("kartograf.auth.proxy.subprocess.run")
    def test_load_from_keychain_hex_encoded(self, mock_run, _sys):
        """Hex-encoded JSON in keychain -> decoded successfully."""
        creds_json = json.dumps({"client_id": "hex_test", "private_key": "pk"})
        hex_data = creds_json.encode("utf-8").hex()
        mock_run.return_value = Mock(returncode=0, stdout=hex_data + "\n")

        creds = CLMSCredentials()
        assert creds.load_from_keychain() is True
        assert creds._credentials["client_id"] == "hex_test"

    @patch("kartograf.auth.proxy.platform.system", return_value="Darwin")
    @patch("kartograf.auth.proxy.subprocess.run")
    def test_load_from_keychain_fail(self, mock_run, _sys):
        """security command fails -> False."""
        mock_run.return_value = Mock(returncode=1, stderr="not found")

        creds = CLMSCredentials()
        assert creds.load_from_keychain() is False

    @patch("kartograf.auth.proxy.platform.system", return_value="Darwin")
    @patch("kartograf.auth.proxy.subprocess.run")
    def test_load_from_keychain_empty_output(self, mock_run, _sys):
        """security returns empty output -> False."""
        mock_run.return_value = Mock(returncode=0, stdout="\n")

        creds = CLMSCredentials()
        assert creds.load_from_keychain() is False

    @patch("kartograf.auth.proxy.platform.system", return_value="Darwin")
    @patch("kartograf.auth.proxy.subprocess.run", side_effect=Exception("boom"))
    def test_load_from_keychain_exception(self, _run, _sys):
        """Exception during keychain access -> False."""
        creds = CLMSCredentials()
        assert creds.load_from_keychain() is False


class TestCLMSCredentialsToken:
    """Test CLMSCredentials.get_access_token."""

    def test_get_access_token_cached(self):
        """Return cached token if not expired."""
        import time

        creds = CLMSCredentials()
        creds._credentials = {"client_id": "test"}  # Must be set to skip keychain
        creds._access_token = "cached_tok"
        creds._token_expires = time.time() + 3600  # 1 hour from now

        assert creds.get_access_token() == "cached_tok"

    def test_get_access_token_exchange(self):
        """Token exchange via JWT -> access token."""
        import jwt as jwt_module

        creds = CLMSCredentials()
        creds._credentials = {
            "client_id": "test_client",
            "user_id": "test_user",
            "token_uri": "https://example.com/token",
            "private_key": "fake_key",
            "key_id": "kid123",
        }

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "new_token"}
        mock_resp.raise_for_status = Mock()

        with (
            patch.object(jwt_module, "encode", return_value="fake_assertion"),
            patch("requests.post", return_value=mock_resp),
        ):
            token = creds.get_access_token()
        assert token == "new_token"

    def test_get_access_token_loads_env_first(self, monkeypatch):
        """CLMS_CREDENTIALS set -> token exchanged without touching Keychain."""
        import jwt as jwt_module

        monkeypatch.setenv(
            "CLMS_CREDENTIALS",
            json.dumps(
                {
                    "client_id": "test_client",
                    "user_id": "test_user",
                    "token_uri": "https://land.copernicus.eu/@@oauth2-token",
                    "private_key": "fake_key",
                }
            ),
        )

        creds = CLMSCredentials()

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "env_token"}
        mock_resp.raise_for_status = Mock()

        with (
            patch.object(
                creds, "load_from_keychain", return_value=False
            ) as mock_keychain,
            patch.object(jwt_module, "encode", return_value="fake_assertion"),
            patch("requests.post", return_value=mock_resp),
        ):
            token = creds.get_access_token()

        assert token == "env_token"
        mock_keychain.assert_not_called()

    def test_get_access_token_no_creds(self):
        """No credentials and keychain fails -> None."""
        creds = CLMSCredentials()

        with patch.object(creds, "load_from_keychain", return_value=False):
            assert creds.get_access_token() is None

    def test_get_access_token_exchange_failure(self):
        """Token exchange fails -> None."""
        import jwt as jwt_module

        creds = CLMSCredentials()
        creds._credentials = {
            "client_id": "c",
            "token_uri": "https://example.com/t",
            "private_key": "k",
        }
        with (
            patch.object(jwt_module, "encode", return_value="assertion"),
            patch("requests.post", side_effect=Exception("fail")),
        ):
            assert creds.get_access_token() is None


class TestCLMSCredentialsAvailability:
    """Test CLMSCredentials.is_available property."""

    def test_is_available_with_creds(self):
        """Credentials already loaded -> True."""
        creds = CLMSCredentials()
        creds._credentials = {"client_id": "test"}
        assert creds.is_available is True

    def test_is_available_loads_keychain(self):
        """No cached credentials -> tries keychain."""
        creds = CLMSCredentials()
        with patch.object(creds, "load_from_keychain", return_value=True):
            assert creds.is_available is True

    def test_is_available_prefers_env_over_keychain(self, monkeypatch):
        """CLMS_CREDENTIALS set -> available without querying Keychain."""
        monkeypatch.setenv(
            "CLMS_CREDENTIALS",
            json.dumps({"client_id": "x", "private_key": "k"}),
        )

        creds = CLMSCredentials()
        with patch.object(creds, "load_from_keychain") as mock_keychain:
            assert creds.is_available is True

        mock_keychain.assert_not_called()

    def test_is_available_no_keychain(self):
        """No cached credentials, keychain fails -> False."""
        creds = CLMSCredentials()
        with patch.object(creds, "load_from_keychain", return_value=False):
            assert creds.is_available is False


class TestProxyHandlerEndpoints:
    """Test ProxyHandler HTTP endpoints using mock request/response."""

    def _make_handler(self, method, path, body=None, credentials=None):
        """Create a mock ProxyHandler for testing."""
        handler = Mock(spec=ProxyHandler)
        handler.path = path
        handler.headers = {}
        handler.wfile = BytesIO()

        if body is not None:
            handler.rfile = BytesIO(body)
            handler.headers = {"Content-Length": str(len(body))}

        if credentials is None:
            credentials = Mock()
        handler.credentials = credentials
        ProxyHandler.credentials = credentials

        # Set up send_json to track calls
        sent_responses = []

        def fake_send_json(data, status=200):
            sent_responses.append({"data": data, "status": status})
            # Mirror the real send_json: the body lands in wfile.
            handler.wfile.write(json.dumps(data).encode("utf-8"))

        handler.send_json = fake_send_json
        handler._sent = sent_responses

        return handler

    def test_health_endpoint(self):
        """GET /health returns credentials_available status."""
        creds = Mock()
        creds.is_available = True
        handler = self._make_handler("GET", "/health", credentials=creds)

        ProxyHandler.do_GET(handler)

        assert len(handler._sent) == 1
        assert handler._sent[0]["status"] == 200
        assert handler._sent[0]["data"]["status"] == "ok"
        assert handler._sent[0]["data"]["credentials_available"] is True

    def test_token_endpoint_removed(self):
        """GET /token no longer hands the access token to local processes."""
        creds = Mock()
        creds.get_access_token.return_value = "test_token"
        handler = self._make_handler("GET", "/token", credentials=creds)

        ProxyHandler.do_GET(handler)

        assert len(handler._sent) == 1
        assert handler._sent[0]["status"] == 404
        assert "access_token" not in handler._sent[0]["data"]
        creds.get_access_token.assert_not_called()

    def test_proxy_rejects_foreign_host(self):
        """POST /proxy to a host outside the allowlist -> 403, no token used."""
        creds = Mock()
        creds.get_access_token.return_value = "SECRET-TOKEN"
        body = json.dumps({"url": "https://attacker.invalid/steal"}).encode()
        handler = self._make_handler("POST", "/proxy", body=body, credentials=creds)

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            ProxyHandler.do_POST(handler)

        assert handler._sent[0]["status"] == 403
        mock_get.assert_not_called()
        mock_post.assert_not_called()
        creds.get_access_token.assert_not_called()

    def test_proxy_rejects_lookalike_host(self):
        """Suffix match must not accept copernicus.eu.attacker.invalid."""
        creds = Mock()
        creds.get_access_token.return_value = "SECRET-TOKEN"
        body = json.dumps(
            {"url": "https://land.copernicus.eu.attacker.invalid/steal"}
        ).encode()
        handler = self._make_handler("POST", "/proxy", body=body, credentials=creds)

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            ProxyHandler.do_POST(handler)

        assert handler._sent[0]["status"] == 403
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    def test_download_rejects_foreign_host(self):
        """POST /download to a host outside the allowlist -> 403."""
        creds = Mock()
        creds.get_access_token.return_value = "SECRET-TOKEN"
        body = json.dumps({"url": "https://attacker.invalid/steal.tif"}).encode()
        handler = self._make_handler("POST", "/download", body=body, credentials=creds)

        with patch("requests.get") as mock_get:
            ProxyHandler.do_POST(handler)

        assert handler._sent[0]["status"] == 403
        mock_get.assert_not_called()
        creds.get_access_token.assert_not_called()

    def test_proxy_rejects_http_scheme(self):
        """Plain http to an allowed host would leak the token -> 403."""
        creds = Mock()
        creds.get_access_token.return_value = "SECRET-TOKEN"
        body = json.dumps({"url": "http://land.copernicus.eu/api/x"}).encode()
        handler = self._make_handler("POST", "/proxy", body=body, credentials=creds)

        with patch("requests.get") as mock_get:
            ProxyHandler.do_POST(handler)

        assert handler._sent[0]["status"] == 403
        mock_get.assert_not_called()

    def test_proxy_allows_copernicus_host(self):
        """POST /proxy to land.copernicus.eu is forwarded with the token."""
        creds = Mock()
        creds.get_access_token.return_value = "tok123"
        body = json.dumps(
            {
                "url": "https://land.copernicus.eu/api/@datarequest_post",
                "method": "POST",
            }
        ).encode()
        handler = self._make_handler("POST", "/proxy", body=body, credentials=creds)

        upstream = Mock()
        upstream.status_code = 200
        upstream.headers = {}
        upstream.text = "ok"

        with patch("requests.post", return_value=upstream) as mock_post:
            ProxyHandler.do_POST(handler)

        assert handler._sent[0]["status"] == 200
        assert handler._sent[0]["data"]["status_code"] == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer tok123"

    def test_download_stream_error_after_headers_does_not_append_json(self):
        """Aborted stream must not append an HTTP 502 body to the raster."""
        import requests

        creds = Mock()
        creds.get_access_token.return_value = "tok123"
        body = json.dumps(
            {"url": "https://land.copernicus.eu/api/download/clc.tif"}
        ).encode()
        handler = self._make_handler("POST", "/download", body=body, credentials=creds)

        def fake_send_response(status, message=None):
            handler.wfile.write(f"HTTP/1.0 {status}\r\n".encode())

        def fake_send_header(key, value):
            handler.wfile.write(f"{key}: {value}\r\n".encode())

        def fake_end_headers():
            handler.wfile.write(b"\r\n")

        handler.send_response = fake_send_response
        handler.send_header = fake_send_header
        handler.end_headers = fake_end_headers

        def broken_stream(chunk_size=8192):
            yield b"II*\x00AAAA"
            raise requests.RequestException("Response ended prematurely")

        upstream = Mock()
        upstream.status_code = 200
        upstream.headers = {"Content-Type": "image/tiff"}
        upstream.iter_content = broken_stream

        with patch("requests.get", return_value=upstream):
            ProxyHandler.do_POST(handler)

        written = handler.wfile.getvalue()
        assert handler._sent == []
        assert handler.close_connection is True
        assert b'{"error"' not in written
        assert written.endswith(b"AAAA")

    def test_unknown_get_endpoint(self):
        """GET /unknown -> 404."""
        handler = self._make_handler("GET", "/unknown")

        ProxyHandler.do_GET(handler)

        assert handler._sent[0]["status"] == 404


class TestRunServer:
    """Test run_server and main."""

    @patch("kartograf.auth.proxy.HTTPServer")
    def test_run_server_starts(self, mock_httpserver_cls, capsys):
        """run_server creates server and prints port."""
        mock_server = Mock()
        mock_server.server_address = ("127.0.0.1", 54321)
        mock_server.serve_forever.side_effect = KeyboardInterrupt
        mock_httpserver_cls.return_value = mock_server

        run_server(port=0)

        captured = capsys.readouterr()
        assert "54321" in captured.out

    @patch("kartograf.auth.proxy.argparse.ArgumentParser")
    @patch("kartograf.auth.proxy.run_server")
    def test_main_parses_args(self, mock_run, mock_parser_cls):
        """main() parses --port and calls run_server."""
        from kartograf.auth.proxy import main

        mock_parser = Mock()
        mock_args = Mock()
        mock_args.port = 8080
        mock_parser.parse_args.return_value = mock_args
        mock_parser_cls.return_value = mock_parser

        main()

        mock_run.assert_called_once_with(8080)
