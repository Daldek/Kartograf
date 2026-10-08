"""
CLMS Authentication Proxy Client.

This module provides a client for communicating with the CLMS Auth Proxy.
The proxy is automatically started as a subprocess when needed.
"""

import atexit
import contextlib
import logging
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Optional

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
    ...     response = client.proxy_request(
    ...         url="https://land.copernicus.eu/api/...",
    ...         method="POST",
    ...         payload={"key": "value"},
    ...     )
    ...     client.download_file(
    ...         url="https://land.copernicus.eu/...",
    ...         output_path=Path("clc.tif"),
    ...     )
    """

    _instance: Optional["AuthProxyClient"] = None
    # Subprocess state is CLASS state, like _proxy_port: a second object
    # (a lost __new__ race, or an explicitly reset singleton) must see the
    # already running child instead of starting a second proxy.
    _proxy_process: subprocess.Popen | None = None
    _proxy_port: int | None = None
    _stderr_thread: threading.Thread | None = None
    # Guards the whole start/check sequence: without it a second thread sees
    # a live process with _proxy_port still unset and builds "None/health".
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one proxy instance.

        Double-checked under ``_lock``: the first client is routinely built
        from several threads at once (``LandCoverManager.download_batch``
        runs 4 workers by default), and two instances would mean two proxy
        subprocesses. ``__new__`` never runs under ``_ensure_proxy``, so the
        non-reentrant lock is never taken twice.
        """
        if cls._instance is None:
            with cls._lock:
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
        proc = AuthProxyClient._proxy_process
        if proc:
            logger.debug("Shutting down auth proxy...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                # kill() only delivers the signal - reap the child so it
                # does not linger as a zombie for the rest of the session.
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5)
            AuthProxyClient._proxy_process = None
            AuthProxyClient._proxy_port = None

    def _start_proxy(self) -> bool:
        """Start the proxy subprocess.

        Called under ``_lock`` from :meth:`_ensure_proxy` (the lock is not
        reentrant, so it is never taken again here).
        """
        proc_running = AuthProxyClient._proxy_process
        if proc_running and proc_running.poll() is None:
            return True  # Already running

        logger.info("Starting CLMS auth proxy...")

        try:
            # Start proxy as subprocess
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "kartograf.auth.proxy",
                    "--port",
                    "0",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            AuthProxyClient._proxy_process = proc
            # Both pipes exist (stdout/stderr=PIPE); the check narrows the
            # Optional types of Popen.stdout/stderr.
            stdout, stderr = proc.stdout, proc.stderr
            if stdout is None or stderr is None:
                raise RuntimeError("Proxy process pipes are not available")

            # The child logs one line per request to stderr. Nobody reading
            # that pipe means the child blocks on write() once the ~64 kB
            # pipe buffer fills (a few dozen downloads) - drain it.
            AuthProxyClient._stderr_thread = threading.Thread(
                target=self._drain_stderr,
                args=(stderr,),
                daemon=True,
            )
            AuthProxyClient._stderr_thread.start()

            # Read the port in a thread: a child that never prints it (and
            # never exits) would otherwise block this call forever.
            port_line: list[str] = []
            reader = threading.Thread(
                target=lambda: port_line.append(stdout.readline()),
                daemon=True,
            )
            reader.start()
            reader.join(PROXY_STARTUP_TIMEOUT)

            if reader.is_alive() or not port_line or not port_line[0].strip():
                self._fail_proxy("Proxy did not output port number")
                return False

            AuthProxyClient._proxy_port = int(port_line[0].strip())
            logger.info(f"Auth proxy started on port {self._proxy_port}")

            # Wait for proxy to be ready
            if not self._wait_for_proxy():
                self._fail_proxy("Proxy did not become ready")
                return False

            return True

        except Exception as e:
            self._fail_proxy(f"Failed to start proxy: {e}")
            return False

    @staticmethod
    def _drain_stderr(stream: IO[str]) -> None:
        """Forward the child's stderr to DEBUG logs until it closes."""
        try:
            for line in stream:
                logger.debug(f"auth proxy: {line.rstrip()}")
        except Exception as e:  # pragma: no cover - stream closed abruptly
            logger.debug(f"Stopped draining proxy stderr: {e}")

    def _fail_proxy(self, message: str) -> None:
        """Log a startup failure and leave no half-started child behind."""
        logger.error(message)

        proc = AuthProxyClient._proxy_process
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    # kill() only delivers the signal - reap the child.
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=5)
            except Exception as e:  # pragma: no cover - already dead
                logger.debug(f"Failed to terminate proxy: {e}")

        AuthProxyClient._proxy_process = None
        AuthProxyClient._proxy_port = None

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
        """Ensure proxy is running.

        The whole check-and-start sequence runs under ``_lock`` so that a
        concurrent caller either waits for the port or sees a ready proxy -
        never a live process with ``_proxy_port`` still unset.
        """
        with AuthProxyClient._lock:
            proc = AuthProxyClient._proxy_process
            if AuthProxyClient._proxy_port and proc:
                # Check if still running
                if proc.poll() is None:
                    return True
                # Process died, restart
                logger.warning("Proxy process died, restarting...")

            return self._start_proxy()

    @property
    def proxy_url(self) -> str | None:
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
        # The proxy reads credentials from CLMS_CREDENTIALS or (macOS only)
        # from the Keychain. With neither source the answer is already known,
        # so do not pay for a subprocess and an open localhost port.
        if platform.system() != "Darwin" and not os.environ.get("CLMS_CREDENTIALS"):
            logger.debug("No CLMS credentials source available - proxy not started")
            return False

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

    def proxy_request(
        self,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        payload: dict | None = None,
    ) -> dict | None:
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
            True only if the whole body was received and moved into place.
            A truncated download returns False and leaves no file behind.
        """
        if not self._ensure_proxy():
            return False

        # Write through a per-process/per-thread temp file so that a partial
        # body never becomes the output: the proxy signals a truncated stream
        # by dropping the connection (missing terminating chunk or a short
        # read against Content-Length), which surfaces here as a
        # RequestException in the middle of iter_content.
        tmp_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
        )

        resp = None
        try:
            resp = self._session.post(
                f"{self.proxy_url}/download",
                json={"url": url},
                timeout=300,
                stream=True,
            )

            if resp.status_code != 200:
                logger.error(f"Download failed: {resp.status_code}")
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    written += len(chunk)

            if not self._body_complete(resp, written):
                return False

            os.replace(tmp_path, output_path)
            return True

        except requests.RequestException as e:
            logger.error(f"Download error: {e}")
        finally:
            # stream=True keeps the connection open until the body is read to
            # the end; a truncated read would otherwise leak the socket.
            if resp is not None:
                resp.close()
            # No-op after a successful os.replace.
            tmp_path.unlink(missing_ok=True)

        return False

    @staticmethod
    def _body_complete(resp: requests.Response, written: int) -> bool:
        """
        Check the received size against Content-Length where comparable.

        The proxy forwards the upstream body verbatim (raw bytes plus the
        original Content-Encoding), so Content-Length counts the *encoded*
        bytes while iter_content yields decoded ones. The comparison is
        therefore only meaningful when no content coding is in play.
        """
        expected = resp.headers.get("Content-Length")
        if expected is None:
            return True

        encoding = resp.headers.get("Content-Encoding")
        if encoding and encoding.lower() != "identity":
            return True

        try:
            expected_bytes = int(expected)
        except (TypeError, ValueError):
            logger.debug(f"Unparsable Content-Length: {expected!r}")
            return True

        if written != expected_bytes:
            logger.error(
                f"Download truncated: got {written} B, expected {expected_bytes} B"
            )
            return False

        return True

    def shutdown(self):
        """Explicitly shutdown the proxy."""
        self._cleanup()
