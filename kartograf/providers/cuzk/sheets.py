"""
SheetIndex — indeks arkuszy KladyMapovychListu (ArcGIS REST /query) z cache.

Warstwa 24: SM5 (MAPNOM, MAPNAME, PODIL) w EPSG:5514.
Warstwa 26: siatka TM33 2x2 km (MAPNOM, IN_CZ) w EPSG:3045.
Uwaga: host `arcgis`, nie `arcgis2`. Zero IO przy imporcie i konstrukcji.

FILTR NADMIAROWEGO WYBORU (rekonesans Zad. 1, krok 3b) — `esriSpatialRelIntersects`
selekcjonuje wiecej, niz zada koperta:
1. arkusze stykajace sie z koperta wylacznie krawedzia/narozem (koperta z fixtury
   `klady_sm5_bbox.json`: 13 zwroconych, 7 faktycznie przecinajacych),
2. przy `inSR` innym niz natywny Krovak — arkusze oddalone nawet o ~2 km, bo serwer
   reprojektuje koperte i uzywa jej obwiedni rownoleglej do osi w Krovaku (rotacja
   ~7 stopni); koperta wielkosci jednego kafla TM33 zwrocila 9 kafli.
Dlatego kazda metoda bbox-owa filtruje wynik PO STRONIE KLIENTA: zostaja tylko
arkusze, ktorych zasieg przecina koperte WNETRZEM (styk krawedzia sie nie liczy —
konwencja `find_tiles_tm33_for_bbox` / `find_sheets_for_bbox`). Porownanie zawsze
w jednym ukladzie: koperta musi byc w natywnym CRS warstwy, w ktorym usluga zwraca
geometrie (`ValidationError` w przeciwnym razie).

IN_CZ (warstwa 26) ma tylko jedna wartosc — "CZ" dla wszystkich 20 308 kafli — wiec
NIE jest dyskryminatorem granicy; wskaznikiem "ile arkusza lezy w CZ" jest PODIL
warstwy 24.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_tm33 import TM33_CRS
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient

logger = logging.getLogger(__name__)

KLADY_ENDPOINT = (
    "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"
)
SM5_LAYER = 24
TM33_LAYER = 26
SM5_CRS = "EPSG:5514"
SM5_SYSTEM = "cz_sm5"  # klucz `system` w sheet_cache

_SM5_FIELDS = "MAPNOM,MAPNAME,PODIL"
_TM33_FIELDS = "MAPNOM,IN_CZ"

_SM5_RE = re.compile(r"^[A-Z]{4}\d{2}$")
_SM5_HINT = "oczekiwano 4 wielkich liter + 2 cyfr, np. CTES96"

# Wspolrzedne z ArcGIS niosa szum siatkowania rzedu 1e-3 m (np. -449999.999308
# zamiast -450000), wiec styk krawedzia trzeba wykrywac z tolerancja. 1 cm jest
# o rzad wielkosci powyzej szumu i o rzedy wielkosci ponizej rozmiaru arkusza
# (2500 x 2000 m) czy kafla (2000 x 2000 m).
_OVERLAP_TOLERANCE_M = 0.01


@dataclass(frozen=True)
class SheetInfo:
    """Jeden arkusz/kafel z indeksu KladyMapovychListu."""

    godlo: str  # MAPNOM ("CTES96" / "744_5534")
    name: str | None  # MAPNAME ("Český Těšín 9-6"); None dla TM33
    bbox: BBox  # EPSG:5514 (w. 24) / EPSG:3045 (w. 26)
    podil: float | None  # udzial arkusza w terytorium CZ; None dla TM33
    in_cz: bool | None  # warstwa 26; None dla SM5


class SheetIndex:
    """Indeks arkuszy z zapytaniami po MAPNOM/bbox i cache sheet_cache."""

    def __init__(
        self,
        session: Any = None,
        cache: MetadataCache | None = None,
        endpoint: str = KLADY_ENDPOINT,
    ):
        self._client = CuzkClient(session=session)
        self._cache = cache
        self._endpoint = endpoint

    def sm5_sheet(self, mapnom: str) -> SheetInfo:
        """Arkusz SM5 po MAPNOM; ValidationError gdy nieznany (przed pobraniem)."""
        if not isinstance(mapnom, str) or not _SM5_RE.match(mapnom):
            raise ValidationError(f"Niepoprawne godlo SM5: '{mapnom}' ({_SM5_HINT})")
        if self._cache is not None:
            cached = self._cache.get_sheet(SM5_SYSTEM, mapnom)
            if cached is not None:
                info = _info_from_payload(cached)
                if info is not None:
                    return info
        # mapnom przeszedl _SM5_RE (tylko [A-Z] i cyfry) — brak ryzyka wstrzykniecia
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            where=f"MAPNOM='{mapnom}'",
            out_fields=_SM5_FIELDS,
            out_sr=SM5_CRS,
        )
        if not features:
            raise ValidationError(
                f"Arkusz SM5 '{mapnom}' nie istnieje w indeksie "
                f"KladyMapovychListu (warstwa {SM5_LAYER})"
            )
        info = _sm5_info(features[0])
        if self._cache is not None:
            self._cache.set_sheet(SM5_SYSTEM, mapnom, _payload_from_info(info))
        return info

    def sm5_sheets_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """Arkusze SM5 przecinajace bbox (fundament etapu 2: LAZ/Orto)."""
        _validate_request_bbox(bbox, SM5_CRS, "sm5_sheets_for_bbox")
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            bbox=bbox,
            out_fields=_SM5_FIELDS,
            out_sr=SM5_CRS,
        )
        return _intersecting(bbox, [_sm5_info(f) for f in features])

    def tm33_tiles_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """Kafle TM33 przecinajace bbox (z atrybutem IN_CZ)."""
        _validate_request_bbox(bbox, TM33_CRS, "tm33_tiles_for_bbox")
        features = self._client.query(
            self._endpoint,
            TM33_LAYER,
            bbox=bbox,
            out_fields=_TM33_FIELDS,
            out_sr=TM33_CRS,
        )
        return _intersecting(bbox, [_tm33_info(f) for f in features])


class Sm5Sheet:
    """Obiekt parsera dla rejestru cz_sm5 — bbox przez SheetIndex (lazy).

    Sciezka szczesliwa pobierania SM5 nie potrzebuje bboxa (URL openzu to
    czysta nazwa arkusza) — get_bbox() to jedyne miejsce z IO.
    """

    uklad = "cz_sm5"

    def __init__(self, godlo: str, index: SheetIndex | None = None):
        if not isinstance(godlo, str) or not _SM5_RE.match(godlo.strip()):
            raise ParseError(f"Niepoprawne godlo SM5: '{godlo}' ({_SM5_HINT})")
        self.godlo = godlo.strip()
        self._index = index

    def get_bbox(self) -> BBox:
        """BBox arkusza w EPSG:5514 (zapytanie do indeksu, z cache)."""
        if self._index is None:
            self._index = SheetIndex(cache=MetadataCache())
        return self._index.sm5_sheet(self.godlo).bbox

    def __repr__(self) -> str:
        return f"Sm5Sheet('{self.godlo}')"


def _validate_request_bbox(bbox: BBox, expected_crs: str, method: str) -> None:
    """Koperta musi byc w CRS warstwy (filtr przeciec dziala w jednym ukladzie)."""
    if bbox.crs.strip().upper() != expected_crs:
        raise ValidationError(
            f"{method} wymaga bbox w {expected_crs} (usluga zwraca geometrie "
            f"w tym ukladzie, a filtr przeciec wymaga wspolnego CRS), "
            f"otrzymano: {bbox.crs}"
        )
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            f"Niepoprawny bbox: ({bbox.min_x}, {bbox.min_y}, "
            f"{bbox.max_x}, {bbox.max_y})"
        )


def _overlaps_interior(sheet: BBox, request: BBox) -> bool:
    """Czy zasiegi maja czesc wspolna o dodatnim polu (styk krawedzia => False)."""
    width = min(sheet.max_x, request.max_x) - max(sheet.min_x, request.min_x)
    height = min(sheet.max_y, request.max_y) - max(sheet.min_y, request.min_y)
    return width > _OVERLAP_TOLERANCE_M and height > _OVERLAP_TOLERANCE_M


def _intersecting(bbox: BBox, infos: list[SheetInfo]) -> list[SheetInfo]:
    """Odsiej nadmiarowy wybor uslugi; wynik posortowany po godle (determinizm)."""
    kept = [i for i in infos if _overlaps_interior(i.bbox, bbox)]
    if len(kept) != len(infos):
        dropped = sorted({i.godlo for i in infos} - {i.godlo for i in kept})
        logger.debug(
            f"KladyMapovychListu: odrzucono {len(infos) - len(kept)} "
            f"nieprzecinajacych arkuszy: {', '.join(dropped)}"
        )
    return sorted(kept, key=lambda i: i.godlo)


def _rings_envelope(feature: dict, crs: str) -> BBox:
    """Obwiednia WSZYSTKICH pierscieni geometrii.

    Dla wielokata z dziurami pierscienie wewnetrzne leza w zewnetrznym, wiec
    obwiednia jest dokladna. Dla wielokata wieloczesciowego obwiednia jest
    nadzbiorem czesci — filtr moze wtedy zostawic arkusz o jeden za duzo,
    ale NIGDY nie zgubi arkusza faktycznie przecinajacego koperte (bezpieczny
    kierunek bledu). Arkusze SM5 i kafle TM33 sa w praktyce prostokatami
    o jednym pierscieniu.
    """
    geometry = feature.get("geometry") or {}
    points = [pt for ring in geometry.get("rings") or [] for pt in ring]
    if not points:
        raise ParseError(
            f"Feature bez geometrii 'rings' w odpowiedzi KladyMapovychListu: "
            f"{feature.get('attributes')}"
        )
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return BBox(min(xs), min(ys), max(xs), max(ys), crs)


def _mapnom(feature: dict) -> str:
    mapnom = (feature.get("attributes") or {}).get("MAPNOM")
    if not mapnom:
        raise ParseError(
            f"Feature bez atrybutu MAPNOM w odpowiedzi KladyMapovychListu: {feature}"
        )
    return str(mapnom)


def _sm5_info(feature: dict) -> SheetInfo:
    attrs = feature.get("attributes") or {}
    podil = attrs.get("PODIL")
    return SheetInfo(
        godlo=_mapnom(feature),
        name=attrs.get("MAPNAME"),
        bbox=_rings_envelope(feature, SM5_CRS),
        podil=float(podil) if podil is not None else None,
        in_cz=None,
    )


def _tm33_info(feature: dict) -> SheetInfo:
    attrs = feature.get("attributes") or {}
    return SheetInfo(
        godlo=_mapnom(feature),
        name=None,
        bbox=_rings_envelope(feature, TM33_CRS),
        podil=None,
        in_cz=_parse_in_cz(attrs.get("IN_CZ")),
    )


def _parse_in_cz(value: Any) -> bool | None:
    """IN_CZ przychodzi jako string ("CZ"); w praktyce zawsze ta sama wartosc."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().upper() == "CZ"
    return bool(value)


def _payload_from_info(info: SheetInfo) -> dict:
    return {
        "godlo": info.godlo,
        "name": info.name,
        "bbox": [info.bbox.min_x, info.bbox.min_y, info.bbox.max_x, info.bbox.max_y],
        "bbox_crs": info.bbox.crs,
        "podil": info.podil,
        "in_cz": info.in_cz,
    }


def _info_from_payload(payload: dict) -> SheetInfo | None:
    """Odtworz SheetInfo z cache; None gdy wpis jest niekompletny/stary schematem."""
    try:
        min_x, min_y, max_x, max_y = payload["bbox"]
        return SheetInfo(
            godlo=payload["godlo"],
            name=payload.get("name"),
            bbox=BBox(min_x, min_y, max_x, max_y, payload["bbox_crs"]),
            podil=payload.get("podil"),
            in_cz=payload.get("in_cz"),
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Pomijam niezdatny wpis sheet_cache ({e}): {payload}")
        return None
