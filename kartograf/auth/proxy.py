#!/usr/bin/env python3
"""
CLMS Authentication Proxy Server.

This script runs as a separate subprocess to handle CLMS API authentication.
It reads credentials from macOS Keychain and performs OAuth2 token exchange,
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
import platform
import re
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
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


class CLMSCredentials:
    """Manages CLMS OAuth2 credentials from Keychain."""

    def __init__(self):
        self._credentials: Optional[dict] = None
        self._access_token: Optional[str] = None
        self._token_expires: float = 0

    def load_from_keychain(self) -> bool:
        """Load credentials from macOS Keychain."""
        if platform.system() != "Darwin":
            logger.error("Keychain only available on macOS")
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

    def get_access_token(self) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        if not self._credentials:
            if not self.load_from_keychain():
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
        return self.load_from_keychain()


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
        elif parsed.path == "/token":
            token = self.credentials.get_access_token()
            if token:
                self.send_json({"access_token": token})
            else:
                self.send_json({"error": "Failed to get access token"}, 500)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests - proxy to CLMS API."""
        import requests

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

            token = self.credentials.get_access_token()
            if not token:
                self.send_json({"error": "Failed to get access token"}, 500)
                return

            try:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=120,
                    stream=True,
                )

                # Stream the response
                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, value)
                self.end_headers()

                for chunk in resp.iter_content(chunk_size=8192):
                    self.wfile.write(chunk)

            except requests.RequestException as e:
                self.send_json({"error": f"Download failed: {e}"}, 502)

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
