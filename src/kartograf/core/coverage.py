"""
Area coverage by convex polygons - pure geometry, no IO and no dependencies.

Used by LAZ tile selection (``providers/pl/gugik_laz.py``): an older tile is
redundant if its intersection with the requested area is already covered by
newer tiles. GUGiK tiles are quadrilaterals (the sheet frame, slightly
rotated in EPSG:2180 - including PL-1992 1:2500 sheets), so arithmetic on
CONVEX polygons is enough:

- intersection of two convex polygons = Sutherland-Hodgman clipping (the
  result is convex),
- difference ``P \\ Q`` for convex ``Q`` = disjoint pieces
  ``P ∩ H1 ∩ ... ∩ H(i-1) ∩ ¬Hi`` (``Hi`` - the inner half-plane of the
  i-th edge of ``Q``), each convex,
- edge tolerance = shifting every edge of the cover outwards (a buffer with
  sharp corners - slightly larger than a round one at the corners).

Polygons are tuples of ``(x, y)`` points in counter-clockwise (CCW) order,
without a closing vertex. It is worth shifting coordinates to a local origin
(e.g. the corner of the area) - the order of 10^5 m eats area precision.
"""

from collections.abc import Iterable, Sequence

Point = tuple[float, float]
Polygon = tuple[Point, ...]

# Pieces with an area no larger than this (m^2) are numerical clipping noise,
# not a real uncovered area (with local coordinates of ~10^3 m the rounding
# error is ~10^-13 m).
AREA_EPS = 1e-6
# A vertex deviating from the line of its neighbours by no more than this many
# metres is treated as collinear and removed. PL-1992 1:2500 sheet frames have
# 9 points in WFS (edge midpoints): parallel-aligned edges are arcs in
# EPSG:2180, the midpoint deviates from the chord by ~3 cm (real tile
# M-34-76-A-a-1-1-3), once outwards, once inwards - without a threshold the
# frame comes out "concave". 10 cm also covers larger sheets, and changing the
# frame by <= 10 cm is negligible against the coverage tolerance (1 m).
COLLINEAR_TOL_M = 0.10


def polygon_area(poly: Sequence[Point]) -> float:
    """Signed area (shoelace formula): positive for CCW."""
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
    """Axis-aligned rectangle as a CCW polygon."""
    return ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y))


def normalize_convex(points: Iterable[Point]) -> Polygon | None:
    """
    WFS ring -> convex CCW polygon or ``None``.

    Removes the closing vertex, repeated and collinear vertices (GUGiK
    publishes 1:2500 sheet frames with nine points - edge midpoints), and
    reverses a CW ring. ``None`` for a non-convex or degenerate polygon
    (< 3 vertices, zero area): the caller decides how to behave cautiously.
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
            return None  # concave (or degenerate) - no guessing
    return tuple(pts)


def _clip_halfplane(poly: Sequence[Point], a: Point, b: Point) -> Polygon:
    """Part of ``poly`` on the left of (and on) the directed line ``a -> b``."""
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
    """Intersection of the convex polygon ``subject`` with the convex CCW ``clip``."""
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
    """``subject \\ hole`` as a list of disjoint convex pieces (noise-free)."""
    pieces: list[Polygon] = []
    rest: Polygon = tuple(subject)
    n = len(hole)
    for i in range(n):
        a, b = hole[i], hole[(i + 1) % n]
        outside = _clip_halfplane(rest, b, a)  # right side of the edge a -> b
        if _significant(outside):
            pieces.append(outside)
        rest = _clip_halfplane(rest, a, b)
        if not _significant(rest):
            break
    return pieces


def expand_convex(poly: Sequence[Point], distance: float) -> Polygon:
    """Every edge of a convex CCW polygon shifted outwards by ``distance``."""
    if distance == 0:
        return tuple(poly)
    n = len(poly)
    lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        # outward normal for CCW: (dy, -dx)
        ox, oy = dy / length * distance, -dx / length * distance
        lines.append(((x1 + ox, y1 + oy), (dx, dy)))
    out: list[Point] = []
    for i in range(n):
        (px, py), (rx, ry) = lines[i - 1]
        (qx, qy), (sx, sy) = lines[i]
        denom = rx * sy - ry * sx
        # adjacent edges of a normalized convex polygon are not parallel
        t = ((qx - px) * sy - (qy - py) * sx) / denom
        out.append((px + t * rx, py + t * ry))
    return tuple(out)


def uncovered_pieces(
    region: Sequence[Point], covers: Iterable[Sequence[Point]]
) -> list[Polygon]:
    """Part of ``region`` not covered by the union of convex ``covers`` (pieces)."""
    pieces: list[Polygon] = [tuple(region)] if _significant(region) else []
    for cover in covers:
        if not pieces:
            break
        next_pieces: list[Polygon] = []
        for piece in pieces:
            next_pieces.extend(subtract_convex(piece, cover))
        pieces = next_pieces
    return pieces
