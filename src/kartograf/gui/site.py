"""
What the deployment gives the page of ``kartograf gui serve`` (ADR-063 decision 9).

``GuiSite.from_config`` reads, once at the start, the settings of Nogat's GUIs in
``nogat.toml`` (DEV-18.1): the base maps the page offers (``kartograf.gui.basemaps``,
DEV-15.15), the table ``gui`` of the addresses of the deployment's GUIs, which the
app menu lists (DEV-15.4), and the table ``operator`` of a public GUI, whose
regulamin it fills (``kartograf.gui.terms``, DEV-15.7). A wrong base map setting stops
the start (``ConfigError``); a wrong table of GUIs or an unfilled regulamin is logged
and the page goes without the menu or the regulamin.

The page reads its part as ``site.json`` beside it (``page_settings``): served by
``kartograf gui serve`` and by whatever hosts the same files, so the page asks no API
for them. The Content-Security-Policy names no remote origin but those of the base
maps offered (``content_security_policy``).
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from kartograf import config
from kartograf.gui.basemaps import deployment_basemaps, origin
from kartograf.gui.terms import SERVICE, URL, Terms, build_terms
from kartograf.messages import message

__all__ = ["PAGE_SETTINGS", "GuiSite"]

logger = logging.getLogger(__name__)

PAGE_SETTINGS: Final = "site.json"
"""The settings of the page, beside it."""


def _gui_table() -> dict[str, str]:
    """Return ``[nogat] gui``: the GUIs of the deployment by name, their addresses.

    The keys are the registry names in lower case; a table that is no table of texts
    is logged and read as none (the menu lists no other GUI).
    """
    table = config.config_file().sections.get(config.APP, {}).get("gui")
    if table is None:
        return {}
    if not isinstance(table, Mapping) or not all(
        isinstance(name, str) and isinstance(address, str)
        for name, address in table.items()
    ):
        logger.warning("%s", message("gui.gui_table_invalid"))
        return {}
    return {name.lower(): address for name, address in table.items()}


@dataclass(frozen=True)
class GuiSite:
    """The settings of the deployment the page and its server need.

    Attributes
    ----------
    basemaps : tuple of dict
        The entries of the base maps the page offers, the catalogue's allowed ones in
        its order, then the deployment's own (the shape of ``nogat-basemaps.json``).
    apps : Mapping of str to str
        ``[nogat] gui``: the addresses of the deployment's GUIs by registry name.
    terms : Terms or None
        The filled regulamin of a public GUI; ``None`` for a GUI that is not public.
    """

    basemaps: tuple[dict[str, Any], ...]
    apps: Mapping[str, str]
    terms: Terms | None

    @classmethod
    def from_config(cls) -> "GuiSite":
        """Read the settings in force (``nogat.toml`` and the variables).

        Raises
        ------
        ConfigError
            A setting of the base maps cannot be used.
        """
        basemaps = tuple(deployment_basemaps())
        apps = _gui_table()
        operator = config.config_file().sections.get(config.APP, {}).get("operator")
        terms = build_terms(operator, apps.get(SERVICE), basemaps)
        return cls(basemaps=basemaps, apps=apps, terms=terms)

    @property
    def address(self) -> str:
        """The address of this GUI: Kartograf's entry of ``[nogat] gui``, else ``/``."""
        return self.apps.get(SERVICE) or "/"

    def page_settings(self) -> dict[str, Any]:
        """Return ``site.json``: what the page shows of the deployment.

        ``basemaps``, the entries of ``<nogat-basemaps>``; ``apps``, the table of
        ``<nogat-app-menu>``; ``terms``, the address of the regulamin relative to the
        page, ``null`` for a GUI that is not public.
        """
        return {
            "basemaps": list(self.basemaps),
            "apps": dict(self.apps),
            "terms": URL if self.terms is not None else None,
        }

    def remote_origins(self) -> tuple[str, ...]:
        """Return the origins of the base maps the page offers, each once, sorted."""
        found = {
            origin(str(entry.get("origin") or entry.get("url") or ""))
            for entry in self.basemaps
        }
        return tuple(sorted(item for item in found if item is not None))

    def content_security_policy(self) -> str:
        """Return the page's Content-Security-Policy (DEV-15.7, DEV-15.15).

        Every script, style, font and worker of the page's own origin; ``img-src``
        and ``connect-src`` add only the origins of the base maps offered, no scheme
        source; no frame, plugin or base. MapLibre 6's worker is a file of the page
        (``worker-src 'self'``).
        """
        remote = " ".join(self.remote_origins())
        images = f"'self' data: blob: {remote}".rstrip()
        connections = f"'self' {remote}".rstrip()
        return "; ".join(
            (
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self'",
                "worker-src 'self'",
                f"img-src {images}",
                f"connect-src {connections}",
                "font-src 'self'",
                "object-src 'none'",
                "base-uri 'none'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            )
        )
