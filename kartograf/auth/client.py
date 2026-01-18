"""
CLMS Authentication Proxy Client.

This module provides a client for communicating with the CLMS Auth Proxy.
The proxy is automatically started as a subprocess when needed.
"""

import atexit
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Proxy startup timeout
PROXY_STARTUP_TIMEOUT = 10  # seconds
PROXY_HEALTH_CHECK_INTERVAL = 0.2  # seconds


class AuthProxyClient:
    """
    Client for CLMS Authentication Proxy.

    Manages the proxy subprocess lifecycle and provides methods
    for authenticated CLMS API requests.

    The proxy runs as a separate subprocess, isolating credentials
    from the main application. This ensures that sensitive data
    (private keys, tokens) are never exposed to the parent process.

    Examples
    --------
    >>> client = AuthProxyClient()
    >>> if client.is_available():
    ...     token = client.get_access_token()
    ...     response = client.proxy_request(
    ...         url="https://land.copernicus.eu/api/...",
    ...         method="POST",
    ...         payload={"key": "value"},
    ...     )
    """

    _instance: Optional["AuthProxyClient"] = None
    _proxy_process: Optional[subprocess.Popen] = None
    _proxy_port: Optional[int] = None

    def __new__(cls):
        """Singleton pattern - only one proxy instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize proxy client."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._session = requests.Session()
            atexit.register(self._cleanup)

    def _cleanup(self):
        """Cleanup proxy process on exit."""
        if self._proxy_process:
            logger.debug("Shutting down auth proxy...")
            self._proxy_process.terminate()
            try:
                self._proxy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proxy_process.kill()
            self._proxy_process = None
            AuthProxyClient._proxy_port = None

    def _start_proxy(self) -> bool:
        """Start the proxy subprocess."""
        if self._proxy_process and self._proxy_process.poll() is None:
            return True  # Already running

        logger.info("Starting CLMS auth proxy...")

        try:
            # Start proxy as subprocess
            self._proxy_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m", "kartograf.auth.proxy",
                    "--port", "0",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Read port from first line of stdout
            port_line = self._proxy_process.stdout.readline().strip()
            if not port_line:
                logger.error("Proxy did not output port number")
                return False

            AuthProxyClient._proxy_port = int(port_line)
            logger.info(f"Auth proxy started on port {self._proxy_port}")

            # Wait for proxy to be ready
            return self._wait_for_proxy()

        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            return False

    def _wait_for_proxy(self) -> bool:
        """Wait for proxy to become ready."""
        start = time.time()
        while time.time() - start < PROXY_STARTUP_TIMEOUT:
            try:
                resp = self._session.get(
                    f"http://127.0.0.1:{self._proxy_port}/health",
                    timeout=1,
                )
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(PROXY_HEALTH_CHECK_INTERVAL)

        logger.error("Proxy health check timed out")
        return False

    def _ensure_proxy(self) -> bool:
        """Ensure proxy is running."""
        if self._proxy_port and self._proxy_process:
            # Check if still running
            if self._proxy_process.poll() is None:
                return True
            # Process died, restart
            logger.warning("Proxy process died, restarting...")

        return self._start_proxy()

    @property
    def proxy_url(self) -> Optional[str]:
        """Return proxy base URL if available."""
        if self._proxy_port:
            return f"http://127.0.0.1:{self._proxy_port}"
        return None

    def is_available(self) -> bool:
        """
        Check if auth proxy is available and has credentials.

        Returns
        -------
        bool
            True if proxy can provide authentication.
        """
        if not self._ensure_proxy():
            return False

        try:
            resp = self._session.get(
                f"{self.proxy_url}/health",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("credentials_available", False)
        except requests.RequestException as e:
            logger.debug(f"Health check failed: {e}")

        return False

    def get_access_token(self) -> Optional[str]:
        """
        Get CLMS access token from proxy.

        Returns
        -------
        str or None
            Access token if available, None otherwise.
        """
        if not self._ensure_proxy():
            return None

        try:
            resp = self._session.get(
                f"{self.proxy_url}/token",
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("access_token")
            else:
                logger.error(f"Token request failed: {resp.text}")
        except requests.RequestException as e:
            logger.error(f"Token request error: {e}")

        return None

    def proxy_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        payload: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Send authenticated request through proxy.

        Parameters
        ----------
        url : str
            Target URL for the request.
        method : str
            HTTP method (GET, POST).
        headers : dict, optional
            Additional headers.
        payload : dict, optional
            Request payload for POST.

        Returns
        -------
        dict or None
            Response with status_code, headers, body.
        """
        if not self._ensure_proxy():
            return None

        try:
            resp = self._session.post(
                f"{self.proxy_url}/proxy",
                json={
                    "url": url,
                    "method": method,
                    "headers": headers or {},
                    "payload": payload,
                },
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Proxy request failed: {resp.text}")
        except requests.RequestException as e:
            logger.error(f"Proxy request error: {e}")

        return None

    def download_file(
        self,
        url: str,
        output_path: Path,
    ) -> bool:
        """
        Download file through authenticated proxy.

        Parameters
        ----------
        url : str
            URL to download.
        output_path : Path
            Local path to save the file.

        Returns
        -------
        bool
            True if download succeeded.
        """
        if not self._ensure_proxy():
            return False

        try:
            resp = self._session.post(
                f"{self.proxy_url}/download",
                json={"url": url},
                timeout=300,
                stream=True,
            )

            if resp.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                logger.error(f"Download failed: {resp.status_code}")

        except requests.RequestException as e:
            logger.error(f"Download error: {e}")

        return False

    def shutdown(self):
        """Explicitly shutdown the proxy."""
        self._cleanup()
