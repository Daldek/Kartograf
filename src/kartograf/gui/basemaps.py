"""
The base maps of the page (Nogat DEV-15.15, DEV-18.1; ADR-063 decision 9).

Nogat's GUI kit lists the base maps every GUI with a map shares in its catalogue
``nogat-basemaps.json``, copied byte for byte into ``web/nogat/`` (DEV-15.6): for each
its id, label, kind (``vector`` or ``raster``), address and origin, zooms and bounds,
whether it is grey, whether a GUI may open on it, its credit and the blocks of the
regulamin its data need. A deployment chooses which of them the page offers
(``basemaps``), may serve copies of them from its own addresses (``basemap_mirrors``)
and may add base maps of its own (``basemap_extra``): ``basemaps`` from
``KARTOGRAF_BASEMAPS`` or ``NOGAT_BASEMAPS`` (the ids joined by ``,``), else from the
key of ``[kartograf]`` before that of ``[nogat]`` in ``nogat.toml``; the other two from
the file only. A wrong value is a ``ConfigError`` naming the setting and the value, and
``kartograf gui serve`` does not start.

The page gets ``deployment_basemaps`` in its settings (``kartograf.gui.site``) and
draws them with the kit's ``nogat-basemaps.js``; the CSP names their origins and the
regulamin keeps the blocks they name. The checks follow Hydrograf's
``core/basemaps.py``, the model of the shared base maps.
"""

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qsl, quote_plus, urlsplit

from kartograf import config
from kartograf.exceptions import ConfigError
from kartograf.messages import Message, message

__all__ = [
    "CATALOGUE",
    "KIT_DIR",
    "basemap_blocks",
    "catalogue",
    "deployment_basemaps",
    "origin",
    "wms_template",
]

KIT_DIR: Final = Path(__file__).resolve().parent / "web" / "nogat"
"""The copy of Nogat's kit the page loads (DEV-15.6)."""
CATALOGUE: Final = "nogat-basemaps.json"

# A kind of an own base map -> the kind of its entry for the page.
EXTRA_KINDS: Final[Mapping[str, str]] = {
    "xyz": "raster",
    "wms": "raster",
    "vector": "vector",
}
EXTRA_KEYS: Final = ("id", "name", "kind", "url", "attribution", "grayscale")
_REQUIRED: Final = ("id", "name", "kind", "url", "attribution")
# The id the page keeps for the choice "no base map".
_NO_BASEMAP: Final = "none"
# The tile of a WMS base map, as Archiwista's `tileUrl` builds it.
TILE_PX: Final = 256
WMS_DEFAULTS: Final[Mapping[str, str]] = {
    "SERVICE": "WMS",
    "REQUEST": "GetMap",
    "VERSION": "1.1.1",
    "STYLES": "",
    "FORMAT": "image/png",
    "TRANSPARENT": "TRUE",
}
_WMS_REPLACED: Final = ("SRS", "CRS", "BBOX", "WIDTH", "HEIGHT")
_DEFAULT_PORTS: Final = {"http": 80, "https": 443}


class _Found:
    """A value of a setting and where it was read: a variable or a table's key."""

    def __init__(self, value: Any, name: str, path: Path | None) -> None:
        self.value = value
        self.name = name
        self.path = path


def catalogue(kit_dir: Path = KIT_DIR) -> list[dict[str, Any]]:
    """Return the entries of the kit's catalogue of base maps, in its order.

    Raises
    ------
    ConfigError
        ``nogat-basemaps.json`` cannot be read or has no list ``entries``.
    """
    path = kit_dir / CATALOGUE
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
        if not isinstance(entries, list):
            raise TypeError("entries is not a list")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ConfigError(
            message("gui.catalogue_unreadable", path=path, error=error), path=path
        ) from error
    return entries


def origin(address: str) -> str | None:
    """Return the origin of an http or https address, ``None`` for any other.

    As ``new URL(address).origin`` of a browser: the scheme, the host in lower case
    (an IPv6 address in brackets) and the port unless it is the scheme's default.
    """
    if any(char.isspace() for char in address):
        return None
    try:
        parts = urlsplit(address)
        host = parts.hostname
        port = parts.port
        if parts.scheme not in _DEFAULT_PORTS or not host:
            return None
        if not host.isascii():
            host = host.encode("idna").decode("ascii")
    except (ValueError, UnicodeError):  # a port out of range, a bad name
        return None
    if ":" in host:
        host = f"[{host}]"
    if port is None or port == _DEFAULT_PORTS[parts.scheme]:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def wms_template(address: str) -> str:
    """Return the tile template of a WMS address, as Archiwista's ``tileUrl``.

    The parameters of the address are kept; those of ``WMS_DEFAULTS`` it lacks (in
    any case) are added; SRS, CRS, BBOX, WIDTH and HEIGHT (in any case) go, then SRS,
    or CRS for a VERSION 1.3, is EPSG:3857 and the tile 256 by 256 px. MapLibre fills
    ``{bbox-epsg-3857}``, whose braces stay unencoded.
    """
    parts = urlsplit(address)
    params = parse_qsl(parts.query, keep_blank_values=True)
    given = {name.upper() for name, _ in params}
    params += [
        (name, value) for name, value in WMS_DEFAULTS.items() if name not in given
    ]
    params = [
        (name, value) for name, value in params if name.upper() not in _WMS_REPLACED
    ]
    version = next(
        (value for name, value in params if name.upper() == "VERSION"), "1.1.1"
    )
    crs = "CRS" if version.startswith("1.3") else "SRS"
    params += [(crs, "EPSG:3857"), ("WIDTH", str(TILE_PX)), ("HEIGHT", str(TILE_PX))]
    query = "&".join(f"{_form(name)}={_form(value)}" for name, value in params)
    return f"{origin(address)}{parts.path or '/'}?{query}&BBOX={{bbox-epsg-3857}}"


def _form(text: str) -> str:
    """Encode a name or value as ``URLSearchParams`` does (form encoding)."""
    return quote_plus(text, safe="*").replace("~", "%7E")


def _text(value: object) -> str:
    """Return a value of a setting as the text an error names: text as it is."""
    return value if isinstance(value, str) else repr(value)


def _in_file(key: str) -> _Found | None:
    """Return ``key`` of ``[kartograf]``, else of ``[nogat]`` of ``nogat.toml``."""
    file = config.config_file()
    for section in (config.TOOL, config.APP):
        table = file.sections.get(section, {})
        if key in table:
            return _Found(table[key], f"[{section}] {key}", file.path)
    return None


def _error(text: Message, found: _Found, value: object) -> ConfigError:
    """Return the error of a value of a setting that cannot be used."""
    return ConfigError(text, option=found.name, value=_text(value), path=found.path)


def _checked_ids(ids: Iterable[object], known: list[str], found: _Found) -> list[str]:
    """Return the ids, each of the catalogue, or raise naming the first that is not."""
    checked: list[str] = []
    for basemap in ids:
        if not isinstance(basemap, str) or basemap not in known:
            raise ConfigError(
                message(
                    "gui.basemap_unknown",
                    name=found.name,
                    value=_text(basemap),
                    known=", ".join(known),
                ),
                option=found.name,
                value=_text(basemap),
                allowed=known,
                path=found.path,
                hint=message("gui.basemap_hint", known=", ".join(known)),
            )
        checked.append(basemap)
    return checked


def _allowed_ids(known: list[str]) -> set[str]:
    """Return the ids of the setting ``basemaps``; every id of ``known`` by default."""
    key = "basemaps"
    for variable in (f"{config.PREFIX}BASEMAPS", f"{config.SHARED_PREFIX}BASEMAPS"):
        raw = os.environ.get(variable)
        if raw:  # an empty variable counts as unset (DEV-18.1)
            found = _Found(raw, variable, None)
            ids = [part.strip() for part in raw.split(",") if part.strip()]
            return set(_checked_ids(ids, known, found))
    in_file = _in_file(key)
    if in_file is None:
        return set(known)
    value = in_file.value
    if not isinstance(value, list):
        raise _error(
            message("gui.basemaps_invalid", name=in_file.name, value=_text(value)),
            in_file,
            value,
        )
    return set(_checked_ids(value, known, in_file))


def _mirrors(known: list[str]) -> dict[str, str]:
    """Return the setting ``basemap_mirrors``: an id -> the address of its copy."""
    found = _in_file("basemap_mirrors")
    if found is None:
        return {}
    table = found.value
    if not isinstance(table, dict):
        raise _error(
            message("gui.basemap_mirrors_invalid", name=found.name, value=_text(table)),
            found,
            table,
        )
    _checked_ids(table, known, found)
    for address in table.values():
        if not isinstance(address, str) or origin(address) is None:
            raise _error(
                message(
                    "gui.basemap_mirrors_invalid", name=found.name, value=_text(address)
                ),
                found,
                address,
            )
    return dict(table)


def _extra_error(found: _Found, field: str, value: object) -> ConfigError:
    """Return the error of a wrong value of ``basemap_extra``."""
    return _error(
        message(
            "gui.basemap_extra_invalid",
            name=found.name,
            field=field,
            value=_text(value),
        ),
        found,
        value,
    )


def _extra_entry(
    item: object, found: _Found, known: list[str], seen: set[str]
) -> dict[str, Any]:
    """Return the page's entry of one own base map of ``basemap_extra``, checked."""
    if not isinstance(item, dict):
        raise _extra_error(found, "basemap_extra", item)
    for key, value in item.items():
        if key not in EXTRA_KEYS:
            raise _extra_error(found, key, value)
    for key in _REQUIRED:
        if key not in item:
            shown = item.get("id", item)
            raise _error(
                message(
                    "gui.basemap_extra_missing",
                    name=found.name,
                    field=key,
                    value=_text(shown),
                ),
                found,
                shown,
            )
    basemap, kind, url = item["id"], item["kind"], item["url"]
    if (
        not isinstance(basemap, str)
        or not basemap.strip()
        or basemap == _NO_BASEMAP
        or basemap in known
        or basemap in seen
    ):
        raise _extra_error(found, "id", basemap)
    for key in ("name", "attribution"):
        if not isinstance(item[key], str) or not item[key].strip():
            raise _extra_error(found, key, item[key])
    if not isinstance(kind, str) or kind not in EXTRA_KINDS:
        raise _extra_error(found, "kind", kind)
    address = origin(url) if isinstance(url, str) else None
    if address is None:
        raise _extra_error(found, "url", url)
    grey = item.get("grayscale", False)
    if not isinstance(grey, bool):
        raise _extra_error(found, "grayscale", grey)
    seen.add(basemap)
    return {
        "id": basemap,
        "label": item["name"],
        "kind": EXTRA_KINDS[kind],
        "url": wms_template(url) if kind == "wms" else url,
        "origin": address,
        "grey": grey,
        "default": False,
        "credit": {"text": item["attribution"], "links": []},
    }


def _extra_entries(known: list[str]) -> list[dict[str, Any]]:
    """Return the page's entries of ``basemap_extra``."""
    found = _in_file("basemap_extra")
    if found is None:
        return []
    value = found.value
    if not isinstance(value, list):
        raise _extra_error(found, "basemap_extra", value)
    seen: set[str] = set()
    return [_extra_entry(item, found, known, seen) for item in value]


def deployment_basemaps(kit_dir: Path = KIT_DIR) -> list[dict[str, Any]]:
    """Return the entries of the base maps the deployment's page offers.

    The catalogue's entries ``basemaps`` allows, in its order and as in the file but
    for the ``url`` and ``origin`` of a copy of ``basemap_mirrors``; then the own base
    maps of ``basemap_extra``, with no ``blocks``, zooms or bounds.

    Raises
    ------
    ConfigError
        The catalogue cannot be read, or a setting cannot be used (``option`` names
        the variable or ``[<section>] <key>``, ``value`` the value).
    """
    entries = catalogue(kit_dir)
    known = [str(entry["id"]) for entry in entries]
    allowed = _allowed_ids(known)
    copies = _mirrors(known)
    page: list[dict[str, Any]] = []
    for entry in entries:
        if entry["id"] not in allowed:
            continue
        item = dict(entry)
        if entry["id"] in copies:
            item["url"] = copies[entry["id"]]
            item["origin"] = origin(item["url"])
        page.append(item)
    return page + _extra_entries(known)


def basemap_blocks(entries: Iterable[Mapping[str, Any]]) -> set[str]:
    """Return the blocks of the regulamin the entries name (own ones name none)."""
    return {block for entry in entries for block in entry.get("blocks", ())}
