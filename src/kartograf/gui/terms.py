"""
The regulamin of a public GUI (Nogat DEV-15.7, DEV-15.8, DEV-18.1; ADR-063 decision 9).

A deployment that anyone uses without signing in names its operator in the table
``operator`` of ``[nogat]`` of its ``nogat.toml``. ``kartograf gui serve`` then fills
the kit's template ``nogat-terms.html`` (copied byte for byte into ``web/nogat/``)
once at the start and serves it at ``/regulamin.html``; the page links it in the app
menu, at the foot of its rail and in the dialog of its sources. Without the table,
with a value missing or without Kartograf's address in ``[nogat.gui]`` there is
neither page nor link: a GUI on this computer is no service offered to others.

Filling follows Nogat's ``design/README.md`` (its reference is ``fill`` of
``scripts/terms.py``; Hydrograf's ``core/terms.py`` is the model): first the blocks,
then the fields, each value HTML-escaped. The blocks kept are those of the sources of
the data the page plans (GUGiK and ČÚZK: NMT, NMPT, LAZ and the orthophoto) and those
the base maps the deployment offers name (``osm``, ``gugik``).
"""

import datetime
import html
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from kartograf.gui.basemaps import KIT_DIR, basemap_blocks
from kartograf.messages import message

__all__ = ["DATA_BLOCKS", "URL", "Terms", "build_terms", "fill", "kept_blocks"]

logger = logging.getLogger(__name__)

URL: Final = "regulamin.html"
"""Where the regulamin is served, beside the start page (relative to it)."""
TEMPLATE: Final = "nogat-terms.html"
SERVICE: Final = "kartograf"
"""Kartograf's key of ``[nogat.gui]``: the address of this GUI."""
# The project's own values (DEV-15.7): its registry name, the licence of
# pyproject.toml, its repository in Nogat's ecosystem.yaml and the addresses of its
# tokens and kit relative to the page.
PROJECT_VALUES: Final[Mapping[str, str]] = {
    "service_name": "Kartograf",
    "software_licence": "MIT",
    "source_url": "https://github.com/Daldek/Kartograf",
    "tokens_href": "nogat/tokens.css",
    "kit_href": "nogat/",
}
DATA_BLOCKS: Final = ("gugik", "cuzk")
"""The blocks of the data the page plans: GUGiK (PL) and ČÚZK (CZ) elevation and
orthophoto; Copernicus and ISRIC come with land cover and soil."""
# A key of [nogat.operator] -> the field of the template it fills.
OPERATOR_FIELDS: Final[Mapping[str, str]] = {
    "name": "operator_name",
    "email": "operator_email",
    "terms_effective": "terms_effective",
    "processor": "processor",
    "processor_transfer": "processor_transfer",
    "processor_cookie": "processor_cookie",
    "mail_provider": "mail_provider",
    "mail_transfer": "mail_transfer",
}
OPTIONAL: Final = frozenset({"processor_transfer", "processor_cookie", "mail_transfer"})
"""The only fields that may be empty (each a whole sentence or nothing)."""

_PLACEHOLDER: Final = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_BLOCK: Final = re.compile(
    r"^<!-- block: (?P<name>[a-z][a-z0-9-]*) -->\n(?P<body>.*?)^<!-- /block -->\n",
    re.MULTILINE | re.DOTALL,
)
_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
# The version the regulamin carries in its first paragraph, the one that names the
# day it takes effect („Wersja 1.1, obowiązuje od …”).
_VERSION: Final = re.compile(r"<p>\S+ (\d+\.\d+), [^<]*\{\{terms_effective\}\}</p>")


@dataclass(frozen=True)
class Terms:
    """The filled regulamin of the deployment.

    Attributes
    ----------
    page : str
        The HTML page served at ``URL``.
    version : str
        The version the regulamin carries („Wersja 1.1”), which ``GET /api/v1/server``
        names (``nogat-server/1``).
    """

    page: str
    version: str


def fill(template: str, values: Mapping[str, str], listed: Iterable[str]) -> str:
    """Return the template with its blocks chosen and its fields filled.

    A block named in ``listed`` keeps its lines without its two marker lines; any
    other block goes with its markers. Each ``{{name}}`` becomes its value,
    HTML-escaped.

    Raises
    ------
    ValueError
        A field has no value, a value outside ``OPTIONAL`` is empty, or a ``{{`` is
        left in the page.
    """
    keep = set(listed)
    missing = sorted(
        name
        for name in set(_PLACEHOLDER.findall(template))
        if name not in values or (name not in OPTIONAL and not values[name].strip())
    )
    if missing:
        raise ValueError(message("gui.terms_value_missing", names=", ".join(missing)))
    text = _BLOCK.sub(lambda m: m["body"] if m["name"] in keep else "", template)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _PLACEHOLDER.sub(lambda m: html.escape(values[m[1]]), text)
    if "{{" in text:
        raise ValueError(message("gui.terms_left"))
    return text


def operator_values(table: Mapping[str, Any]) -> dict[str, str]:
    """Return the fields of the template that ``[nogat.operator]`` gives.

    ``terms_effective`` is a TOML date or a ``YYYY-MM-DD`` text; every other value is
    text. A key the table lacks is left out, so ``fill`` names it.

    Raises
    ------
    ValueError
        A value is not text, or ``terms_effective`` is no date.
    """
    values: dict[str, str] = {}
    for key, field in OPERATOR_FIELDS.items():
        if key not in table:
            continue
        value = table[key]
        if key == "terms_effective":
            if isinstance(value, datetime.date) and not isinstance(
                value, datetime.datetime
            ):
                value = value.isoformat()
            if not isinstance(value, str) or not _DATE.fullmatch(value):
                raise ValueError(message("gui.terms_not_date"))
        elif not isinstance(value, str):
            raise ValueError(message("gui.terms_not_text", key=key))
        values[field] = value
    return values


def kept_blocks(entries: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """Return the blocks the regulamin keeps: ``DATA_BLOCKS``, then the base maps'."""
    extra = basemap_blocks(entries) - set(DATA_BLOCKS)
    return DATA_BLOCKS + tuple(sorted(extra))


def build_terms(
    operator: object,
    address: str | None,
    basemaps: Iterable[Mapping[str, Any]],
    kit_dir: Path = KIT_DIR,
) -> Terms | None:
    """Fill the regulamin of a deployment.

    Parameters
    ----------
    operator : object
        ``[nogat.operator]`` of ``nogat.toml``; ``None`` without the table.
    address : str or None
        Kartograf's address of ``[nogat.gui]`` (``service_url``).
    basemaps : iterable of Mapping
        The entries of the base maps the page offers (their ``blocks``).
    kit_dir : Path
        The kit's copy with the template.

    Returns
    -------
    Terms or None
        ``None`` without the table (a GUI that is not public) and when the regulamin
        cannot be filled: a value missing or invalid, no address of Kartograf, no
        template or one that names no version. The cause is logged; values never
        are.
    """
    if operator is None:
        logger.info("%s", message("gui.terms_none"))
        return None
    try:
        if not isinstance(operator, Mapping):
            raise TypeError(message("gui.terms_not_table"))
        if not address:
            raise ValueError(message("gui.terms_no_address"))
        values = {
            **PROJECT_VALUES,
            **operator_values(operator),
            "service_url": address,
        }
        template = (kit_dir / TEMPLATE).read_text(encoding="utf-8")
        version = _VERSION.search(template)
        if version is None:
            raise ValueError(message("gui.terms_no_version"))
        page = fill(template, values, kept_blocks(basemaps))
    except (OSError, TypeError, ValueError) as error:
        logger.warning("%s", message("gui.terms_failed", error=error))
        return None
    return Terms(page=page, version=version[1])
