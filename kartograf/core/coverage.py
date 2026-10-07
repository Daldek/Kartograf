"""
Pokrycie obszaru wypuklymi wielokatami — czysta geometria, bez IO i zaleznosci.

Uzywane przez wybor kafli LAZ (``providers/pl/gugik_laz.py``): kafel starszy
jest zbedny, jesli jego czesc wspolna z obszarem zadania jest juz pokryta
przez kafle nowsze. Kafle GUGiK to czworokaty (rama arkusza, w EPSG:2180
lekko obrocone — takze arkusze PL-1992 1:2500), wiec wystarcza arytmetyka
wielokatow WYPUKLYCH:

- przeciecie dwoch wypuklych = obcinanie Sutherlanda-Hodgmana (wynik wypukly),
- roznica ``P \\ Q`` dla wypuklego ``Q`` = rozlaczne kawalki
  ``P ∩ H1 ∩ ... ∩ H(i-1) ∩ ¬Hi`` (``Hi`` — polplaszczyzna wewnetrzna i-tej
  krawedzi ``Q``), kazdy wypukly,
- tolerancja krawedzi = przesuniecie kazdej krawedzi pokrycia na zewnatrz
  (bufor z ostrymi naroznikami — nieco wiekszy od okraglego w naroznikach).

Wielokaty sa krotkami punktow ``(x, y)`` w kierunku przeciwnym do wskazowek
zegara (CCW), bez wierzcholka zamykajacego. Wspolrzedne warto przesunac do
lokalnego poczatku (np. rogu obszaru) — rzad 10^5 m zjada precyzje pol.
"""

from collections.abc import Iterable, Sequence

Point = tuple[float, float]
Polygon = tuple[Point, ...]

# Kawalki o polu nie wiekszym niz to (m^2) sa szumem numerycznym obcinania,
# nie realnym niepokrytym obszarem (przy wspolrzednych lokalnych ~10^3 m blad
# zaokraglen to ~10^-13 m).
AREA_EPS = 1e-6
# Wierzcholek odchylony od prostej sasiadow o nie wiecej niz tyle metrow jest
# traktowany jako wspolliniowy i usuwany. Ramy arkuszy PL-1992 1:2500 maja
# w WFS po 9 punktow (srodki bokow): boki rownoleznikowe sa w EPSG:2180 lukami,
# srodek odchyla sie od cieciwy o ~3 cm (realny kafel M-34-76-A-a-1-1-3), raz
# na zewnatrz, raz do wnetrza — bez progu rama wychodzi "wklesla". 10 cm
# pokrywa tez wieksze arkusze, a zmiana ramy o <= 10 cm jest pomijalna wobec
# tolerancji pokrycia (1 m).
COLLINEAR_TOL_M = 0.10


def polygon_area(poly: Sequence[Point]) -> float:
    """Pole ze znakiem (wzor Gaussa): dodatnie dla CCW."""
    total = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float) -> Polygon:
    """Prostokat osiowy jako wielokat CCW."""
    return ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y))


def normalize_convex(points: Iterable[Point]) -> Polygon | None:
    """
    Pierscien z WFS -> wypukly wielokat CCW albo ``None``.

    Usuwa wierzcholek zamykajacy, powtorzenia i wierzcholki wspolliniowe
    (GUGiK publikuje ramy arkuszy 1:2500 z dziewiecioma punktami — srodki
    bokow), odwraca pierscien CW. ``None`` dla wielokata niewypuklego albo
    zdegenerowanego (< 3 wierzcholki, zerowe pole): wolajacy decyduje, jak
    zachowac sie ostroznie.
    """
    pts: list[Point] = []
    for x, y in points:
        p = (float(x), float(y))
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return None
    if polygon_area(pts) < 0:
        pts.reverse()
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            prev, cur, nxt = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            chord = ((nxt[0] - prev[0]) ** 2 + (nxt[1] - prev[1]) ** 2) ** 0.5
            if chord == 0 or abs(_cross(prev, cur, nxt)) / chord <= COLLINEAR_TOL_M:
                del pts[i]
                changed = True
                break
    if len(pts) < 3:
        return None
    n = len(pts)
    for i in range(n):
        if _cross(pts[i - 1], pts[i], pts[(i + 1) % n]) <= 0:
            return None  # wklesly (albo zdegenerowany) — bez zgadywania
    return tuple(pts)


def _clip_halfplane(poly: Sequence[Point], a: Point, b: Point) -> Polygon:
    """Czesc ``poly`` po lewej stronie (lacznie z prosta) skierowanej ``a -> b``."""
    out: list[Point] = []
    n = len(poly)
    for i in range(n):
        cur = poly[i]
        nxt = poly[(i + 1) % n]
        c_cur = _cross(a, b, cur)
        c_nxt = _cross(a, b, nxt)
        if c_cur >= 0:
            out.append(cur)
        if (c_cur >= 0) != (c_nxt >= 0):
            t = c_cur / (c_cur - c_nxt)
            out.append((cur[0] + t * (nxt[0] - cur[0]), cur[1] + t * (nxt[1] - cur[1])))
    return tuple(out)


def clip_convex(subject: Sequence[Point], clip: Sequence[Point]) -> Polygon:
    """Przeciecie wielokata wypuklego ``subject`` z wypuklym CCW ``clip``."""
    result: Polygon = tuple(subject)
    n = len(clip)
    for i in range(n):
        if len(result) < 3:
            return ()
        result = _clip_halfplane(result, clip[i], clip[(i + 1) % n])
    return result if len(result) >= 3 else ()


def _significant(poly: Sequence[Point]) -> bool:
    return len(poly) >= 3 and abs(polygon_area(poly)) > AREA_EPS


def subtract_convex(subject: Sequence[Point], hole: Sequence[Point]) -> list[Polygon]:
    """``subject \\ hole`` jako lista rozlacznych wypuklych kawalkow (bez szumu)."""
    pieces: list[Polygon] = []
    rest: Polygon = tuple(subject)
    n = len(hole)
    for i in range(n):
        a, b = hole[i], hole[(i + 1) % n]
        outside = _clip_halfplane(rest, b, a)  # prawa strona krawedzi a -> b
        if _significant(outside):
            pieces.append(outside)
        rest = _clip_halfplane(rest, a, b)
        if not _significant(rest):
            break
    return pieces


def expand_convex(poly: Sequence[Point], distance: float) -> Polygon:
    """Kazda krawedz wypuklego CCW przesunieta o ``distance`` na zewnatrz."""
    if distance == 0:
        return tuple(poly)
    n = len(poly)
    lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        # normalna zewnetrzna dla CCW: (dy, -dx)
        ox, oy = dy / length * distance, -dx / length * distance
        lines.append(((x1 + ox, y1 + oy), (dx, dy)))
    out: list[Point] = []
    for i in range(n):
        (px, py), (rx, ry) = lines[i - 1]
        (qx, qy), (sx, sy) = lines[i]
        denom = rx * sy - ry * sx
        # sasiednie krawedzie wypuklego po normalizacji nie sa rownolegle
        t = ((qx - px) * sy - (qy - py) * sx) / denom
        out.append((px + t * rx, py + t * ry))
    return tuple(out)


def uncovered_pieces(
    region: Sequence[Point], covers: Iterable[Sequence[Point]]
) -> list[Polygon]:
    """Czesc ``region`` niepokryta przez sume wypuklych ``covers`` (kawalki)."""
    pieces: list[Polygon] = [tuple(region)] if _significant(region) else []
    for cover in covers:
        if not pieces:
            break
        next_pieces: list[Polygon] = []
        for piece in pieces:
            next_pieces.extend(subtract_convex(piece, cover))
        pieces = next_pieces
    return pieces
