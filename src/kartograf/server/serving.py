"""
``kartograf server`` on uvicorn, with Nogat's logs (ADR-063 decision 7, DEV-12.4).

``serve`` binds the address, serves ``create_app`` with uvicorn and blocks until
Ctrl+C or ``SIGTERM``, which stop it gracefully: it returns, so the command ends with
0. Nogat's ``ServerLog`` keeps the access, application and lifecycle records in
``<state_dir>/kartograf/logs/<kind>-YYYY-MM-DD.jsonl`` and deletes them after 14 days;
standard error gets the lifecycle records (``start`` names the address and the
limits) and the errors reduced to their type (DEV-12.7). uvicorn runs with
``log_config=None``, ``access_log=False`` (its access line names the client) and
without its proxy headers: the client's address is the server's own reading of
``X-Forwarded-For`` from a trusted proxy (AGI-6.9). The pattern is Hydrolog's ``gui
serve`` (``hydrolog.gui._serving``).

Importing this module imports neither Starlette nor uvicorn: ``serve`` does, and
reports their absence as ``missing_dependency`` (the extra ``server``).
"""

import contextlib
import errno
import importlib
import signal
import socket
import sys
import threading
from collections.abc import Iterator
from typing import Any, Final

from kartograf.exceptions import ConflictError, MissingDependencyError, ValidationError
from kartograf.messages import message, reason

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "serve", "url_of"]

DEFAULT_HOST: Final = "127.0.0.1"
"""This computer only (AGI-6.9): behind a proxy the server keeps listening here."""
DEFAULT_PORT: Final = 8065
"""The port of ``kartograf server`` (ADR-063)."""
EXTRA: Final = "server"
_MODULES: Final = ("starlette", "uvicorn")
_GRACE_S: Final = 5
"""How long open requests may take to end at a stop [s]."""
_IN_USE: Final = frozenset(
    code
    for code in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", None))
    if code is not None
)


def url_of(host: str, port: int) -> str:
    """Return the address of the server, ``http://<host>:<port>/`` (IPv6 bracketed)."""
    shown = f"[{host}]" if ":" in host else host
    return f"http://{shown}:{port}/"


def _require_extra() -> None:
    """Raise ``MissingDependencyError`` unless Starlette and uvicorn import."""
    for module in _MODULES:
        try:
            importlib.import_module(module)
        except ImportError as error:
            raise MissingDependencyError(
                message("server.missing_extra", error=reason(error)), extra=EXTRA
            ) from error


def _bind(host: str, port: int) -> socket.socket:
    """Return a socket listening on ``host:port`` (port 0: a free one).

    Raises
    ------
    ValidationError
        The host cannot be resolved (``option`` host).
    ConflictError
        The port is in use (``port_in_use``).
    """
    try:
        family, kind, proto, _, address = socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )[0]
    except (socket.gaierror, UnicodeError) as error:
        raise ValidationError(
            message("server.invalid_host", host=host, error=reason(error)),
            option="host",
        ) from error
    listener = socket.socket(family, kind, proto)
    try:
        if sys.platform != "win32":  # on Windows the option would share the port
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(address)
        listener.listen()
    except OSError as error:
        listener.close()
        if error.errno in _IN_USE:
            raise ConflictError(
                message("server.port_in_use", port=port, host=host),
                reason="port_in_use",
                hint=message("server.port_in_use_hint"),
            ) from error
        raise
    return listener


def serve(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Serve ``kartograf server`` until Ctrl+C or ``SIGTERM``.

    Parameters
    ----------
    host : str
        The address to listen on (``127.0.0.1``: this computer only).
    port : int
        The TCP port (``0`` takes a free one; the record ``start`` names it).

    Raises
    ------
    MissingDependencyError
        The extra ``server`` (Starlette, uvicorn) is not installed.
    ConflictError
        The port is in use (``port_in_use``).
    ValidationError
        The host cannot be resolved.
    """
    _require_extra()
    import uvicorn

    from kartograf import config
    from kartograf._version import build_version
    from kartograf.server.app import create_app
    from kartograf.server.nogat_logging import ServerLog
    from kartograf.server.settings import ServerSettings

    class _Server(uvicorn.Server):
        """uvicorn's server that stops quietly on a signal.

        uvicorn raises a captured ``SIGINT`` or ``SIGTERM`` again after its graceful
        stop; this server does not, so ``serve`` returns and the command ends with 0.
        """

        @contextlib.contextmanager
        def capture_signals(self) -> Iterator[None]:
            if threading.current_thread() is not threading.main_thread():
                yield
                return
            handled = [signal.SIGINT, signal.SIGTERM]
            if sys.platform == "win32":
                handled.append(signal.SIGBREAK)
            previous: dict[int, Any] = {
                number: signal.signal(number, self.handle_exit) for number in handled
            }
            try:
                yield
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)

    settings = ServerSettings.from_config()
    log = ServerLog(config.TOOL, build_version(), settings.log_dir)
    listener = _bind(host, port)
    try:
        url = url_of(host, listener.getsockname()[1])
        app = create_app(settings, log=log)
        server = _Server(
            uvicorn.Config(
                app,
                log_config=None,
                access_log=False,
                proxy_headers=False,
                server_header=False,
                lifespan="on",
                timeout_graceful_shutdown=_GRACE_S,
            )
        )
        log.start({"url": url, **settings.summary()})
        try:
            server.run(sockets=[listener])
        finally:
            log.stop()
    finally:
        listener.close()
