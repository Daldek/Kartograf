"""
Cadastral areas (katastralni uzemi, KU) of an area from the RUIAN ArcGIS layer.

The layer ``KatastralniUzemi`` (``ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/
MapServer/7``) answers an envelope query with the attributes ``kod`` (integer,
six digits) and ``nazev``; the geometry is not requested. Zero IO at import.
"""

import re
from dataclasses import dataclass

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient

KU_CODE = re.compile(r"[0-9]{6}")

_FIELDS = "kod,nazev"


@dataclass(frozen=True)
class CadastralArea:
    """One cadastral area (KU) of RUIAN."""

    code: str  # "623164"
    name: str  # nazev


def cadastral_areas_for_bbox(
    client: CuzkClient, layer_url: str, bbox: BBox
) -> list[CadastralArea]:
    """KU of the RUIAN layer ``layer_url`` intersecting ``bbox``.

    ``layer_url`` is the full ArcGIS layer URL (``.../RUIAN/MapServer/7``);
    the envelope goes as ``inSR`` = ``bbox.crs``. Sorted by code, unique;
    ``[]`` for a valid empty answer. A code outside ``KU_CODE`` or a missing
    ``kod``/``nazev`` is a source failure (``DownloadError``).
    """
    endpoint, _, layer = layer_url.rstrip("/").rpartition("/")
    if not endpoint or not layer.isdigit():
        raise ValueError(f"Adres warstwy RUIAN bez numeru warstwy: {layer_url!r}")
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            f"Niepoprawny bbox: ({bbox.min_x}, {bbox.min_y}, "
            f"{bbox.max_x}, {bbox.max_y})"
        )
    features = client.query(
        endpoint,
        int(layer),
        bbox=bbox,
        out_fields=_FIELDS,
        return_geometry=False,
    )
    areas: dict[str, CadastralArea] = {}
    for feature in features:
        area = _area(feature, layer_url)
        areas[area.code] = area
    return [areas[code] for code in sorted(areas)]


def _area(feature: dict, layer_url: str) -> CadastralArea:
    attrs = feature.get("attributes") or {}
    code = attrs.get("kod")
    name = attrs.get("nazev")
    # bool is an int subclass; a code is a number or a string of digits
    if isinstance(code, bool) or not isinstance(code, int | str):
        raise DownloadError(
            f"RUIAN {layer_url}: obiekt bez poprawnego pola 'kod': {attrs}"
        )
    text = str(code).strip()
    if not KU_CODE.fullmatch(text):
        raise DownloadError(
            f"RUIAN {layer_url}: kod katastralniho uzemi spoza wzorca 6 cyfr: {code!r}"
        )
    if not isinstance(name, str) or not name.strip():
        raise DownloadError(
            f"RUIAN {layer_url}: katastralni uzemi {text} bez pola 'nazev'"
        )
    return CadastralArea(code=text, name=name.strip())
