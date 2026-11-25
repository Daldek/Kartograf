"""
The application of ``kartograf gui serve``: the page and the API (ADR-063 decision 9).

``create_gui_app`` is the application of ``kartograf server`` (``create_app``) with a
``Page``: the files of ``web/`` at ``/`` (``index.html`` the start page), the settings
the page reads (``site.json``, ``GuiSite.page_settings``) and, on a public GUI, the
filled regulamin at ``/regulamin.html`` (DEV-15.7). Every answer carries the
Content-Security-Policy of the site, which names no remote origin but the base maps'
(DEV-15.15), and the other security headers; no ``Cross-Origin-Opener-Policy``, so the
app menu's tabs of the other GUIs are reused (Nogat's design README). The start page
and the regulamin count in the request limit, the visitors and the page views like
the requests of the API; over the limit a page is answered with a short page of its
own, ``429`` with ``Retry-After`` (DEV-15.9). Files are revalidated on every load
(``Cache-Control: no-cache``), so a new version of the page is never mixed with an old
one.
"""

import html
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final
from urllib.parse import urljoin

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles

from kartograf.exceptions import RateLimitedError
from kartograf.gui.site import PAGE_SETTINGS, GuiSite
from kartograf.gui.terms import URL as TERMS_URL
from kartograf.messages import message
from kartograf.server.app import Page, create_app
from kartograf.server.nogat_logging import ServerLog
from kartograf.server.problems import language_of
from kartograf.server.settings import ServerSettings

__all__ = ["PAGES", "WEB_DIR", "create_gui_app", "security_headers"]

WEB_DIR: Final = Path(__file__).resolve().parent / "web"
"""The page: ES modules, styles, the kit's and the vendored files."""
PAGES: Final = frozenset({"/", "/index.html", f"/{TERMS_URL}"})
"""The HTML pages a person opens: counted like the requests of the API."""
_NO_CACHE: Final = {"Cache-Control": "no-cache"}
_PERMISSIONS: Final = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer",
        "autoplay",
        "bluetooth",
        "camera",
        "display-capture",
        "geolocation",
        "gyroscope",
        "hid",
        "magnetometer",
        "microphone",
        "midi",
        "payment",
        "serial",
        "usb",
        "xr-spatial-tracking",
    )
)
_REFUSAL: Final = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/nogat/tokens.css">
</head>
<body>
<main>
<h1>{title}</h1>
<p>{text}</p>
</main>
</body>
</html>
"""


class _WebFiles(StaticFiles):
    """The files of the page, each revalidated on every load."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        """Answer a file with its validators and ``Cache-Control: no-cache``."""
        response = super().file_response(*args, **kwargs)
        response.headers.update(_NO_CACHE)
        return response


def security_headers(site: GuiSite) -> dict[str, str]:
    """Return the headers of every answer of the GUI (DEV-15.7, DEV-15.15)."""
    return {
        "Content-Security-Policy": site.content_security_policy(),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": _PERMISSIONS,
    }


def _refusal(request: Request, error: RateLimitedError) -> Response:
    """Answer a page over the request limit: ``429`` and a short page (DEV-15.9)."""
    lang = language_of(request.headers.get("accept-language"))
    seconds = error.retry_after_s
    page = _REFUSAL.format(
        lang=lang,
        title=html.escape(message("gui.rate_limited_title", lang)),
        text=html.escape(message("gui.rate_limited_page", lang, seconds=seconds)),
    )
    return HTMLResponse(
        page,
        status_code=429,
        headers={
            "Retry-After": str(seconds),
            "Cache-Control": "no-store",
            "Content-Language": lang,
            "Vary": "Accept-Language",
        },
    )


def _routes(site: GuiSite, web_dir: Path) -> list[BaseRoute]:
    """Return the routes of the page: its settings, its regulamin and its files."""
    settings = json.dumps(site.page_settings(), ensure_ascii=False).encode("utf-8")

    async def page_settings(request: Request) -> Response:
        return Response(settings, media_type="application/json", headers=_NO_CACHE)

    routes: list[BaseRoute] = [
        Route(f"/{PAGE_SETTINGS}", page_settings, methods=["GET"])
    ]
    terms = site.terms
    if terms is not None:

        async def regulamin(request: Request) -> Response:
            return HTMLResponse(terms.page, headers=_NO_CACHE)

        routes.append(Route(f"/{TERMS_URL}", regulamin, methods=["GET"]))
    routes.append(Mount("/", app=_WebFiles(directory=web_dir, html=True)))
    return routes


def create_gui_app(
    settings: ServerSettings | None,
    site: GuiSite,
    *,
    log: ServerLog | None = None,
    clock: Callable[[], float] = time.monotonic,
    web_dir: Path = WEB_DIR,
) -> Starlette:
    """Return the application of ``kartograf gui serve``: the page and the API.

    Parameters
    ----------
    settings : ServerSettings or None
        The limits and the files of the server (default: the settings in force).
    site : GuiSite
        What the deployment gives the page: base maps, other GUIs, regulamin.
    log : ServerLog, optional
        Nogat's logs; with it the access log is the outermost middleware.
    clock : callable, optional
        The monotonic clock of the limits [s]; tests pass their own.
    web_dir : Path, optional
        The files of the page (tests pass their own).

    Returns
    -------
    Starlette
        The application; ``app.state.server`` is its ``ServerState``.
    """
    terms = (
        None
        if site.terms is None
        else {
            "url": urljoin(site.address, TERMS_URL),
            "version": site.terms.version,
        }
    )
    page = Page(
        routes=_routes(site, web_dir),
        paths=PAGES,
        refusal=_refusal,
        headers=security_headers(site),
        gui=site.address,
        terms=terms,
    )
    return create_app(settings, log=log, clock=clock, page=page)
