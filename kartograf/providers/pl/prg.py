"""Powiat TERYT codes from the GUGiK PRG WFS (A1, 0.7.1).

The one place that asks which powiats an area or a point lies in. The
filter is the powiat GEOMETRY (MapServer WFS 2.0, verified live
2026-10-08), not its envelope. A service or response failure is a
``DownloadError``; an empty list only comes from a valid response
without features (sea, abroad).
"""

import logging
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError
from kartograf.transport.http import SessionPerThread, get_with_retry

logger = logging.getLogger(__name__)

PRG_WFS_ENDPOINT = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
)
POWIAT_LAYER = "ms:A02_Granice_powiatow"
_MS = "{http://mapserver.gis.umn.edu/mapserver}"
_WFS_COLLECTION = "{http://www.opengis.net/wfs/2.0}FeatureCollection"
_TERYT = re.compile(r"\d{4}")
# Upper bound of features per request; Poland has ~380 powiats.
_COUNT = 1000
# Half-size (m) of the query square around a point.
_POINT_HALF = 0.5

_sessions = SessionPerThread(None)


def _to_2180(bbox: BBox) -> BBox:
    """Area in EPSG:2180 - the PL cutout rule (Czech CRSs via the pinned operation)."""
    # providers -> download must stay lazy (download imports providers)
    from kartograf.download.cutout import bbox_to_2180

    return bbox_to_2180(bbox)


def _mm(value: float, rounding: Callable[[float], int]) -> str:
    """Coordinate rounded to whole millimetres by ``math.floor``/``math.ceil``.

    Outward rounding never shrinks the area; millimetres (not metres) keep
    the 1 m point square of ``teryt_for_point`` a 1 m square. Trailing
    zeros are dropped (``290000.000`` -> ``290000``).
    """
    text = f"{rounding(round(value * 1000, 6)) / 1000:.3f}"
    return text.rstrip("0").rstrip(".")


def _query(bbox: BBox, session: requests.Session, timeout: float) -> list[str]:
    """Sorted unique powiat codes of one GetFeature request (``bbox`` in 2180)."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": POWIAT_LAYER,
        "PROPERTYNAME": "JPT_KOD_JE",
        "COUNT": str(_COUNT),
        # WFS 2.0 + urn CRS: (N, E) axis order; widened outward (rounding to
        # the nearest metre could drop a 0.5 m edge strip of the area)
        "BBOX": (
            f"{_mm(bbox.min_y, math.floor)},{_mm(bbox.min_x, math.floor)},"
            f"{_mm(bbox.max_y, math.ceil)},{_mm(bbox.max_x, math.ceil)},"
            "urn:ogc:def:crs:EPSG::2180"
        ),
    }
    response = get_with_retry(
        session,
        PRG_WFS_ENDPOINT,
        timeout=timeout,
        description="zapytanie PRG (powiaty)",
        params=params,
    )
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        raise DownloadError(f"PRG WFS: odpowiedz nie jest XML: {e}") from e
    if root.tag != _WFS_COLLECTION:
        text = " ".join(t.strip() for t in root.itertext() if t.strip())[:300]
        raise DownloadError(f"PRG WFS: blad uslugi ({root.tag}): {text}")
    codes = []
    for element in root.iter(f"{_MS}JPT_KOD_JE"):
        code = (element.text or "").strip()
        if not _TERYT.fullmatch(code):
            raise DownloadError(f"PRG WFS: nieprawidlowy kod TERYT powiatu {code!r}")
        codes.append(code)
    _check_complete(root, len(codes))
    return sorted(set(codes))


def _check_complete(root: ET.Element, found: int) -> None:
    """DownloadError when the server may have cut the list (Review Focus 1).

    Cut = ``numberReturned < numberMatched``; with a non-numeric
    ``numberMatched`` (MapServer ``unknown``: matches not counted) a full
    page (``>= _COUNT``) counts as cut; a ``next`` link always does. The
    real MapServer page (recorded 2026-10-08) carries ``unknown`` and a
    ``next`` link.
    """
    matched = root.get("numberMatched", "")
    returned_attr = root.get("numberReturned", "")
    returned = int(returned_attr) if returned_attr.isdigit() else found
    # non-numeric numberMatched ('unknown'): a full page counts as cut
    cut = returned < int(matched) if matched.isdigit() else returned >= _COUNT
    if cut or root.get("next"):
        raise DownloadError(
            f"PRG WFS: niepelna lista powiatow ({returned} z "
            f"{matched or 'nieznanej liczby'}) — zmniejsz obszar"
        )


def discover_teryts_for_bbox(
    bbox: BBox,
    *,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    timeout: float = 30,
) -> list[str]:
    """TERYT codes (4 digits, sorted) of powiats whose geometry intersects ``bbox``.

    ``bbox`` in any supported CRS (converted to EPSG:2180). ``cache`` keeps
    the answer for its TTL (also an empty one); ``MetadataCache(refresh=True)``
    skips the read.

    Raises
    ------
    DownloadError
        Service failure (after the shared retry policy), a response that is
        not a WFS feature collection, a truncated list or a malformed code.
    """
    area = _to_2180(bbox)
    if cache is not None:
        cached = cache.get_teryts_for_bbox(area)
        if cached is not None:
            return cached
    codes = _query(area, session or _sessions.get(), timeout)
    if cache is not None:
        cache.set_teryts_for_bbox(area, codes)
    logger.debug("PRG: %s -> %s", area, codes)
    return codes


def teryt_for_point(
    x: float,
    y: float,
    crs: str,
    *,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    timeout: float = 30,
) -> str | None:
    """TERYT code of the powiat containing the point; None = no powiat there.

    A point exactly on a boundary of two powiats gives the lower code. A
    found code goes to the point cache (``teryt_cache``); the query square
    goes through ``discover_teryts_for_bbox``, so an empty answer (sea) is
    cached too (``teryt_bbox_cache``) and not asked again within the TTL.
    """
    point = _to_2180(BBox(x, y, x, y, crs))
    px, py = point.min_x, point.min_y
    if cache is not None:
        cached = cache.get_teryt(px, py)
        if cached is not None:
            return cached
    half = _POINT_HALF
    square = BBox(px - half, py - half, px + half, py + half, "EPSG:2180")
    codes = discover_teryts_for_bbox(
        square, session=session, cache=cache, timeout=timeout
    )
    if not codes:
        return None
    if cache is not None:
        cache.set_teryt(px, py, codes[0])
    return codes[0]
