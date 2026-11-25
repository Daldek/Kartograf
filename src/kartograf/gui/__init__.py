"""
``kartograf gui serve``: the page of the plans and scripts, with the server (ADR-063).

The page under ``web/`` (ES modules without a build step, DEV-15.1) builds the call of a
data command in Nogat's command form, shows its plan as a table and its footprints on
a map over the ecosystem's shared base maps, and gives the command line, the Kartograf
script and the direct script to copy or to save (ADR-063 decision 9). ``serve_gui``
serves it with the ``/api/v1`` of ``kartograf server`` in one process
(``kartograf.gui.app``); the page finds its API by ``GET /api/v1/server`` of its
origin, so the same files run alone and behind Latarnik. The settings of the
deployment the page needs (the base maps, the other GUIs, the operator of a public
GUI) are read and checked before the server starts (``kartograf.gui.site``).

Importing this package imports neither Starlette nor uvicorn: ``serve_gui`` does, and
reports their absence as ``missing_dependency`` (the extra ``gui``).
"""

import logging
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from kartograf import _clock
from kartograf.download.arguments import require_bool, require_int, require_str
from kartograf.exceptions import ValidationError
from kartograf.messages import message
from kartograf.serialization import Document
from kartograf.server.serving import DEFAULT_HOST, DEFAULT_PORT, require_extra, run_app

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "EXTRA", "GuiServed", "serve_gui"]

logger = logging.getLogger(__name__)

EXTRA: Final = "gui"
"""The extra of ``kartograf gui serve``: the dependencies of the server."""
PROGRAM: Final = "kartograf gui serve"
_MAX_PORT: Final = 65535


@dataclass(frozen=True)
class GuiServed(Document):
    """The GUI served until it was stopped (``kartograf-gui/1``).

    Attributes
    ----------
    url : str
        The address of the page, ``http://<host>:<port>/``.
    started_at, stopped_at : datetime
        When the server started and when it stopped (UTC).
    """

    SCHEMA = "kartograf-gui/1"

    url: str
    started_at: datetime
    stopped_at: datetime


def _checked(host: object, port: object, no_browser: object) -> None:
    """Check the types and ranges of the arguments of ``serve_gui``."""
    require_str(host, "host")
    if not str(host).strip():
        raise ValidationError(
            message("server.invalid_host", host=host, error=message("gui.empty_host")),
            option="host",
        )
    require_int(port, "port")
    assert isinstance(port, int)
    if not 0 <= port <= _MAX_PORT:
        raise ValidationError(
            message("server.cli_port_invalid", value=port), option="port"
        )
    require_bool(no_browser, "no_browser")


def _open_page(url: str) -> None:
    """Open the page in the person's web browser; a failure is only logged."""
    try:
        opened = webbrowser.open(url)
    except webbrowser.Error as error:
        logger.warning("%s", message("gui.browser_failed", url=url, error=error))
        return
    if not opened:
        logger.warning("%s", message("gui.browser_failed", url=url, error="-"))


def serve_gui(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    no_browser: bool = False,
) -> GuiServed:
    """Serve the GUI and the server's API on this computer until it is stopped.

    The library function of ``kartograf gui serve`` (ADR-063 decision 9): the page at
    ``/``, the regulamin of a public GUI at ``/regulamin.html``, the settings of the
    page at ``/site.json`` and every route of ``kartograf server`` under ``/api/v1``,
    read only, until Ctrl+C or ``SIGTERM``. The record ``start`` on standard error
    names the address; the page opens in a web browser unless ``no_browser``.

    Parameters
    ----------
    host : str
        The address to listen on; ``127.0.0.1``, this computer only, by default.
    port : int
        The TCP port, 0 to 65535 (``0`` takes a free one); 8065 by default.
    no_browser : bool
        Do not open the page in a web browser.

    Returns
    -------
    GuiServed
        ``kartograf-gui/1``: the address and when the server ran, after its stop.

    Raises
    ------
    ValidationError
        An argument of a wrong type or range, a host that cannot be resolved
        (``option`` names it).
    ConfigError
        A setting of the page cannot be used: ``basemaps``, ``basemap_mirrors``,
        ``basemap_extra`` (``option`` and ``value`` name it).
    MissingDependencyError
        The extra ``gui`` (Starlette, uvicorn) is not installed.
    ConflictError
        The port is in use (``port_in_use``).
    """
    _checked(host, port, no_browser)
    require_extra(EXTRA, PROGRAM)
    from kartograf.gui.app import create_gui_app
    from kartograf.gui.site import GuiSite

    site = GuiSite.from_config()
    started = _clock.now()
    url = run_app(
        lambda settings, log: create_gui_app(settings, site, log=log),
        host=host,
        port=port,
        ready=None if no_browser else _open_page,
    )
    return GuiServed(url=url, started_at=started, stopped_at=_clock.now())
