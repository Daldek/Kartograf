"""
Bounding box i jego obwiednia w innym ukladzie wspolrzednych.

Modul-lisc warstwy ``core`` (zaleznosci: ``pyproj``, ``numpy``,
``kartograf.exceptions``): jedno miejsce decyzji "jak przeliczyc bbox miedzy
ukladami". Obwiednia jest ZAWSZE liczona z zageszczonych krawedzi — obraz
prostokata w innym ukladzie to czworokat o krzywych bokach, a cztery
narozniki gubia pas przy poludniku osiowym ukladu docelowego (19E dla
EPSG:2180, 15/18/21/24E dla stref PL-2000; do ~480 m dla bboxa 2 x 0,2 st.).

Operacja przypieta (ADR-024, ``kartograf.transform.crs.PinnedTransform``)
wchodzi przez duck typing (``transformer=``): ``core`` nie importuje
``transform`` i nie wybiera operacji — dostaje ja od wolajacego.
"""

from __future__ import annotations

import functools
import math
from typing import Any, NamedTuple

import numpy as np
from pyproj import CRS, Transformer

from kartograf.exceptions import ValidationError

# Liczba punktow na krawedz (jak corine/soilgrids `transform_bounds`).
_DENSIFY = 21

# wkidy ukladow, w ktorych CUZK wydaje dane (S-JTSK/Krovak, ETRS89/TM33);
# zadanie w nich podane opuszcza Krovaka wylacznie przypieta operacja (ADR-024)
_CZ_WKIDS = frozenset({"5514", "3045"})
_CZ_AUTHORITIES = frozenset({"", "EPSG", "ESRI"})


class BBox(NamedTuple):
    """Bounding box z współrzędnymi i układem odniesienia."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str


def _norm_label(crs: str) -> str:
    return crs.strip().upper()


@functools.lru_cache(maxsize=64)
def _transformer(src: str, dst: str) -> Transformer:
    """Transformer pary ukladow, raz na proces (thread-safe od pyproj 3.1)."""
    return Transformer.from_crs(src, dst, always_xy=True)


@functools.lru_cache(maxsize=64)
def _same_crs(src: str, dst: str) -> bool:
    """Czy dwie etykiety (albo WKT) opisuja ten sam uklad."""
    if _norm_label(src) == _norm_label(dst):
        return True
    return bool(CRS.from_user_input(src) == CRS.from_user_input(dst))


def validate_bbox(bbox: BBox, *, crs: str | None = None) -> None:
    """
    Sprawdza poprawnosc bboxa.

    Bbox zdegenerowany (punkt/linia, ``min == max``) jest DOZWOLONY —
    udokumentowane zachowanie ``find_sheets_for_bbox`` (dokladnie jeden
    arkusz).

    Parameters
    ----------
    bbox : BBox
        Bbox do sprawdzenia
    crs : str, optional
        Oczekiwany uklad bboxa (porownanie etykiet bez wielkosci liter
        i bialych znakow)

    Raises
    ------
    ValidationError
        Wspolrzedna nieskonczona/NaN, ``min > max`` na ktorejs osi albo
        uklad rozny od oczekiwanego.
    """
    coords = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if not all(math.isfinite(v) for v in coords):
        raise ValidationError(
            f"wspolrzedne bboxa musza byc skonczone, otrzymano {coords}"
        )
    if bbox.min_x > bbox.max_x or bbox.min_y > bbox.max_y:
        raise ValidationError(
            f"bbox odwrocony (min > max): {coords}; "
            "oczekiwano min_x <= max_x i min_y <= max_y"
        )
    if crs is not None and _norm_label(bbox.crs) != _norm_label(crs):
        raise ValidationError(f"bbox w ukladzie {bbox.crs!r}, oczekiwano {crs!r}")


def transform_bbox(bbox: BBox, target_crs: str, *, transformer: Any = None) -> BBox:
    """
    Obwiednia bboxa w ukladzie docelowym, zawsze z zageszczonych krawedzi.

    Parameters
    ----------
    bbox : BBox
        Bbox zrodlowy; ``bbox.crs`` to etykieta (``"EPSG:2180"``) albo WKT
    target_crs : str
        Uklad docelowy; trafia do pola ``crs`` wyniku bez zmian
    transformer : object, optional
        ``None`` -> transformer pyproj z cache, ``transform_bounds`` z
        ``densify_pts=21``. Obiekt z metoda ``.transform(xs, ys)``
        (np. ``PinnedTransform``) -> 21 probek na krawedz (84 punkty),
        obwiednia min/max; zrodlo/cel wyznacza obiekt, nie etykiety.

    Returns
    -------
    BBox
        Obwiednia w ``target_crs``. Ten sam uklad (np. ``"epsg:2180"`` ->
        ``"EPSG:2180"``) -> te same wspolrzedne z etykieta docelowa.
    """
    if transformer is None:
        if _same_crs(bbox.crs, target_crs):
            return bbox._replace(crs=target_crs)
        pyproj_transformer = _transformer(bbox.crs, target_crs)
        min_x, min_y, max_x, max_y = pyproj_transformer.transform_bounds(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, densify_pts=_DENSIFY
        )
        return BBox(min_x, min_y, max_x, max_y, target_crs)

    xs = np.linspace(bbox.min_x, bbox.max_x, _DENSIFY)
    ys = np.linspace(bbox.min_y, bbox.max_y, _DENSIFY)
    west = np.full(_DENSIFY, bbox.min_x)
    east = np.full(_DENSIFY, bbox.max_x)
    south = np.full(_DENSIFY, bbox.min_y)
    north = np.full(_DENSIFY, bbox.max_y)
    out_x, out_y = transformer.transform(
        np.concatenate([xs, xs, west, east]),
        np.concatenate([south, north, ys, ys]),
    )
    return BBox(
        float(np.min(out_x)),
        float(np.min(out_y)),
        float(np.max(out_x)),
        float(np.max(out_y)),
        target_crs,
    )


def is_czech_crs(label: str) -> bool:
    """
    Czy uklad jest czeskim ukladem danych CUZK (EPSG:5514 / EPSG:3045).

    Porownanie po wkid: ``" epsg:5514 "``, ``"5514"`` i ``"ESRI:5514"``
    (ArcGIS uzywa tych samych wkidow) daja True.
    """
    norm = _norm_label(label)
    authority, _, code = norm.rpartition(":")
    return authority in _CZ_AUTHORITIES and code in _CZ_WKIDS
