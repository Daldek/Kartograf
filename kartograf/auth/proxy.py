#!/usr/bin/env python3
"""
CLMS Authentication Proxy Server.

This script runs as a separate subprocess to handle CLMS API authentication.
It reads credentials from the CLMS_CREDENTIALS environment variable (JSON)
or, as a fallback, from macOS Keychain, and performs OAuth2 token exchange,
keeping credentials isolated from the main application process.

Security model:
- Credentials are only accessible to this subprocess
- Main application receives only access tokens or proxied responses
- Communication via localhost HTTP (not exposed externally)

Usage:
    python -m kartograf.auth.proxy --port 0  # Auto-select port
    python -m kartograf.auth.proxy --port 9876  # Specific port

The server prints the actual port to stdout for the parent process.
"""

import argparse
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Configure logging to stderr (stdout reserved for port number)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Keychain service name
KEYCHAIN_SERVICE = "clms-token"

# Only these hosts may receive the CLMS access token. /proxy (the CLMS API)
# refuses anything else outright; /download forwards to other https hosts as
# well - a presigned DownloadURL may point at a CDN - but then WITHOUT the
# Authorization header, so the token never leaves the allowlist.
ALLOWED_HOST_SUFFIXES = ("copernicus.eu", "eea.europa.eu")


def _host_allowed(url: str) -> bool:
    """Check whether the token may be forwarded to this URL (https + allowlist)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False

    hostname = (parsed.hostname or "").lower()
    return any(
        hostname == suffix or hostname.endswith("." + suffix)
        for suffix in ALLOWED_HOST_SUFFIXES
    )


class CLMSCredentials:
    """
    Manages CLMS OAuth2 credentials.

    Credentials come from the CLMS_CREDENTIALS environment variable (JSON)
    or, as a fallback, macOS Keychain (service clms-token).
    """

    def __init__(self):
        self._credentials: dict | None = None
        self._access_token: str | None = None
        self._token_expires: float = 0

    def load_from_env(self) -> bool:
        """Load credentials from the CLMS_CREDENTIALS environment variable."""
        raw = os.environ.get("CLMS_CREDENTIALS")
        if not raw:
            return False

        try:
            creds = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in CLMS_CREDENTIALS: {e}")
            return False

        if (
            not isinstance(creds, dict)
            or not creds.get("client_id")
            or not creds.get("private_key")
        ):
            logger.error(
                "CLMS_CREDENTIALS must be a JSON object with "
                "'client_id' and 'private_key'"
            )
            return False

        self._credentials = creds
        logger.info("Credentials loaded from CLMS_CREDENTIALS")
        return True

    def load_from_keychain(self) -> bool:
        """Load credentials from macOS Keychain."""
        if platform.system() != "Darwin":
            # Normal case once CLMS_CREDENTIALS is the primary source.
            logger.debug("Keychain only available on macOS")
            return False

        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.error(f"Keychain access failed: {result.stderr}")
                return False

            creds_data = result.stdout.strip()
            if not creds_data:
                return False

            # Handle hex-encoded data
            if not creds_data.startswith("{"):
                try:
                    decoded = bytes.fromhex(creds_data).decode("utf-8")
                    decoded = re.sub(r"\x1b\[\d+~", "", decoded)
                    decoded = decoded.lstrip("\x1b")
                    creds_data = decoded.strip()
                except (ValueError, UnicodeDecodeError):
                    pass

            self._credentials = json.loads(creds_data)
            logger.info("Credentials loaded from Keychain")
            return True

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return False

    def get_access_token(self) -> str | None:
        """Get valid access token, refreshing if needed."""
        if not self._credentials and not (
            self.load_from_env() or self.load_from_keychain()
        ):
            return None

        # Return cached token if still valid
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        # Exchange for new token
        try:
            import jwt
            import requests

            creds = self._credentials
            now = int(time.time())

            payload = {
                "iss": creds.get("client_id"),
                "sub": creds.get("user_id") or creds.get("client_id"),
                "aud": creds.get("token_uri"),
                "iat": now,
                "exp": now + 300,
            }

            headers = {}
            if creds.get("key_id"):
                headers["kid"] = creds["key_id"]

            assertion = jwt.encode(
                payload,
                creds.get("private_key"),
                algorithm="RS256",
                headers=headers if headers else None,
            )

            response = requests.post(
                creds.get("token_uri"),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            self._access_token = result.get("access_token")
            self._token_expires = time.time() + 3600
            logger.info("Access token obtained")
            return self._access_token

        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """Check if credentials are available."""
        if self._credentials:
            return True
        return self.load_from_env() or self.load_from_keychain()


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the auth proxy."""

    credentials: CLMSCredentials = None  # Set by server

    def log_message(self, format, *args):
        """Log to stderr instead of stdout."""
        logger.info("%s - %s", self.address_string(), format % args)

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json(
                {
                    "status": "ok",
                    "credentials_available": self.credentials.is_available,
                }
            )
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests - proxy to CLMS API.

        ``/proxy`` forwards an API call with the Bearer token and answers
        with JSON; the target host must be on ``ALLOWED_HOST_SUFFIXES``.
        ``/download`` streams a file body back to the client: an allowlisted
        host gets the token, any other **https** host is forwarded WITHOUT
        the Authorization header (presigned CLMS DownloadURLs may live on a
        CDN), and a non-https URL is refused with 403.
        """
        import requests
        import urllib3

        parsed = urlparse(self.path)

        if parsed.path == "/proxy":
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b""

            try:
                request_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return

            # Get target URL and method
            target_url = request_data.get("url")
            method = request_data.get("method", "GET").upper()
            headers = request_data.get("headers", {})
            payload = request_data.get("payload")

            if not target_url:
                self.send_json({"error": "Missing 'url' in request"}, 400)
                return

            if not _host_allowed(target_url):
                self.send_json(
                    {"error": f"Host not allowed: {urlparse(target_url).hostname}"},
                    403,
                )
                return

            # Add authorization
            token = self.credentials.get_access_token()
            if not token:
                self.send_json({"error": "Failed to get access token"}, 500)
                return

            headers["Authorization"] = f"Bearer {token}"

            # Proxy the request
            try:
                if method == "GET":
                    resp = requests.get(target_url, headers=headers, timeout=60)
                elif method == "POST":
                    headers.setdefault("Content-Type", "application/json")
                    resp = requests.post(
                        target_url,
                        headers=headers,
                        json=payload,
                        timeout=60,
                    )
                else:
                    self.send_json({"error": f"Unsupported method: {method}"}, 400)
                    return

                # Return proxied response
                self.send_json(
                    {
                        "status_code": resp.status_code,
                        "headers": dict(resp.headers),
                        "body": resp.text,
                    }
                )

            except requests.RequestException as e:
                self.send_json({"error": f"Proxy request failed: {e}"}, 502)

        elif parsed.path == "/download":
            # Direct file download with auth
            import requests

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b""

            try:
                request_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return

            url = request_data.get("url")
            if not url:
                self.send_json({"error": "Missing 'url'"}, 400)
                return

            # The last step of the CLMS GeoTIFF flow is a presigned
            # DownloadURL, which the API may place on a host outside the
            # allowlist (CDN/object storage). Refusing it would break the
            # whole download, so forward it - but strip the token: a
            # presigned link carries its own authorization. Plain http is
            # still refused (the request itself, and any token, would go in
            # clear text).
            if urlparse(url).scheme != "https":
                self.send_json(
                    {"error": f"Scheme not allowed: {urlparse(url).scheme}"},
                    403,
                )
                return

            headers = {}
            if _host_allowed(url):
                token = self.credentials.get_access_token()
                if not token:
                    self.send_json({"error": "Failed to get access token"}, 500)
                    return
                headers["Authorization"] = f"Bearer {token}"
            else:
                logger.info(
                    "Forwarding download without token (host outside allowlist): %s",
                    urlparse(url).hostname,
                )

            # Phase 1: connect. Nothing has been written to the client yet,
            # so a failure here is still reportable as JSON.
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=120,
                    stream=True,
                )
            except requests.RequestException as e:
                self.send_json({"error": f"Download failed: {e}"}, 502)
                return

            # The body is forwarded verbatim (decode_content=False), so the
            # upstream Content-Encoding/Content-Length keep describing exactly
            # the bytes the client receives. Without an upstream
            # Content-Length the body would be delimited by closing the
            # connection (protocol_version is HTTP/1.0), which makes a
            # truncated download indistinguishable from a complete one -
            # frame it as chunked instead and withhold the terminating chunk
            # on failure.
            use_chunked = "Content-Length" not in resp.headers

            try:
                if use_chunked:
                    self.protocol_version = "HTTP/1.1"

                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, value)
                if use_chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()

                # Phase 2: stream the body. The headers are already out, so an
                # error MUST NOT be reported with send_json - that would append
                # a whole HTTP response to the file the client is writing.
                # Drop the connection instead: the client sees a short read
                # against Content-Length, or a missing terminating chunk.
                try:
                    for chunk in resp.raw.stream(8192, decode_content=False):
                        if use_chunked:
                            self.wfile.write(b"%X\r\n" % len(chunk))
                            self.wfile.write(chunk)
                            self.wfile.write(b"\r\n")
                        else:
                            self.wfile.write(chunk)

                    if use_chunked:
                        self.wfile.write(b"0\r\n\r\n")

                except (requests.RequestException, urllib3.exceptions.HTTPError) as e:
                    logger.error("Download stream aborted: %s", e)
                    self.close_connection = True
            finally:
                resp.close()

        else:
            self.send_json({"error": "Not found"}, 404)


def run_server(port: int = 0) -> None:
    """Run the proxy server."""
    credentials = CLMSCredentials()
    ProxyHandler.credentials = credentials

    server = HTTPServer(("127.0.0.1", port), ProxyHandler)
    actual_port = server.server_address[1]

    # Print port to stdout for parent process (MUST be first line)
    print(actual_port, flush=True)

    logger.info(f"CLMS Auth Proxy listening on 127.0.0.1:{actual_port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="CLMS Authentication Proxy")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=0,
        help="Port to listen on (0 = auto-select)",
    )
    args = parser.parse_args()

    run_server(args.port)


if __name__ == "__main__":
    main()
