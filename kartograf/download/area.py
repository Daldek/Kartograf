"""Request areas shared by every track: CRS, countries, geometry envelopes.

One place for the rules the CLI used to apply on its own (Z1): a bbox in any
supported CRS reaches EPSG:2180 the same way in every track (Czech CRSs only
via the pinned operation), a ``geometry`` file gives its envelope after the
layer choice is announced as a ``Notice``, ``country="auto"`` clipping is
described by ``Notice``s and every area file carries ``parent_request``.
"""

import math
from collections.abc import Sequence
from pathlib import Path

from kartograf.core.bbox import BBox, bbox_coords, is_czech_crs, transform_bbox
from kartograf.exceptions import ValidationError
from kartograf.notices import (
    AUTO_AREA_OUTSIDE,
    AUTO_CLIPPED,
    GEOMETRY_LAYER_DEFAULT,
    NoticeSink,
)


def bbox_to_2180(bbox: BBox) -> BBox:
    """Request in EPSG:2180: Czech CRSs via the pinned operation, the rest as before.

    PL/WGS84 CRSs — deliberately the default transformer, envelope from
    densified edges (``core.bbox.transform_bbox``; four corners lost a strip
    at 19E — up to ~480 m in the S for a 2 x 0.2 deg bbox). A Czech CRS
    (Krovak/UTM33N) is left ONLY via the pinned operation - an unpinned pyproj
    transformer (ballpark, unknown accuracy) would shift the selection on the
    border strip. The CRS label is compared case- and whitespace-insensitively
    (``is_czech_crs``).
    """
    if is_czech_crs(bbox.crs):
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        return bbox_to_crs(bbox, "EPSG:2180")
    return transform_bbox(bbox, "EPSG:2180")


def resolve_geometry_layer(
    path: str | Path, layer: str | None, sink: NoticeSink
) -> str | None:
    """The layer of ``path`` read for the request (``None`` for a shapefile).

    A GPKG with several layers and no ``layer`` is read from its first layer
    only - the area of the request comes from it; ``GEOMETRY_LAYER_DEFAULT``
    names the choice and the other layers.

    Raises
    ------
    ValidationError
        Missing file, unsupported format, no feature tables or unknown layer.
    """
    from kartograf.core.geometry import resolve_layer

    filepath = Path(path)
    if not filepath.exists():
        raise ValidationError(f"Brak pliku: {filepath}")
    choice = resolve_layer(filepath, layer)
    if choice.defaulted and len(choice.available) > 1:
        sink.emit(
            "info",
            GEOMETRY_LAYER_DEFAULT,
            f"{filepath.name}: liczba warstw {len(choice.available)}, uzyto "
            f"pierwszej '{choice.name}' (pozostale: "
            f"{', '.join(choice.available[1:])}); inna warstwa: --layer NAZWA",
        )
    return choice.name


def geometry_envelope_2180(
    path: str | Path, layer: str | None, sink: NoticeSink
) -> BBox:
    """EPSG:2180 envelope of every feature of the chosen layer of ``path``."""
    from kartograf.core.geometry import get_overall_bbox

    name = resolve_geometry_layer(path, layer, sink)
    return get_overall_bbox(Path(path), layer=name, target_crs="EPSG:2180")


def parent_request_for(bbox: BBox, countries: Sequence[str]) -> dict:
    """``extra.parent_request`` of an area request (ADR-023 (f).1).

    Groups the files of one bbox/geometry request (including those on both
    sides of the border): the ORIGINAL bbox before per-country clipping, its
    CRS and the countries QUERIED (attempted, not downloaded - ADR-023 point
    3). The returned dict must not be mutated later: sidecars hold it.
    """
    return {
        "bbox": bbox_coords(bbox),
        "bbox_crs": bbox.crs,
        "countries": list(countries),
    }


def geometry_envelope(path: Path, layer: str | None) -> BBox:
    """Envelope of a geometry for country dispatch (``auto``/``pl``).

    A file in a Czech CRS (EPSG:5514/3045): the envelope IN THE FILE'S CRS
    labelled with the EPSG code - the jump to EPSG:2180 is done later by the
    pinned operation (country split). Other CRSs: straight to EPSG:2180.
    """
    from kartograf.core.geometry import get_overall_bbox, read_source_crs

    source_crs = read_source_crs(path, layer=layer)
    epsg = source_crs.to_epsg()
    if epsg is not None and is_czech_crs(f"EPSG:{epsg}"):
        env = get_overall_bbox(path, layer=layer, target_crs=source_crs.to_wkt())
        return BBox(env.min_x, env.min_y, env.max_x, env.max_y, f"EPSG:{epsg}")
    return get_overall_bbox(path, layer=layer, target_crs="EPSG:2180")


def cz_geometry_bbox(path: Path, layer: str | None, image_crs: str) -> BBox:
    """Envelope of a geometry in the CZ request CRS (explicit ``country="cz"``).

    Computed IN THE FILE'S CRS and moved to ``image_crs`` by ``bbox_to_crs``
    (pinned operation + edge sampling), never by the default transformer.
    """
    from pyproj import CRS

    from kartograf.core.geometry import get_overall_bbox, read_source_crs
    from kartograf.providers.cuzk.dmr import bbox_to_crs

    source_crs = read_source_crs(path, layer=layer)
    bbox = get_overall_bbox(path, layer=layer, target_crs=source_crs.to_wkt())
    if source_crs == CRS.from_user_input(image_crs):
        return BBox(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, image_crs)
    return bbox_to_crs(bbox, image_crs)


def pl_only_flags(product: str, vertical_crs: object, resolution: object) -> list[str]:
    """Choices with no CZ counterpart: they resolve ``country="auto"`` to PL.

    ADR-023 point 5; DELIBERATELY narrow: LAZ has its own flow, ``5m``
    exists on both sides, per-country values name both countries, ``system``
    is required for every PL area, ``target_crs`` and campaign options work
    with both countries.
    """
    flags: list[str] = []
    if product in ("nmpt", "orto"):
        flags.append(f"--product {product}")
    if vertical_crs == "KRON86":
        flags.append("--vertical-crs KRON86")
    if resolution == "1m":
        flags.append("--resolution 1m")
    return flags


def _deg(value: float, unit: str) -> str:
    """``54,90 st.N`` - degrees with a decimal comma (Polish ASCII messages)."""
    return f"{value:.2f}".replace(".", ",") + f" st.{unit}"


def area_outside_extents(
    wgs: BBox, extents: Sequence[BBox]
) -> tuple[BBox | None, float]:
    """Part of the WGS84 bbox outside ALL ``extents`` rectangles (S3).

    The rectangle edges cut the bbox into cells; a cell whose center is not
    covered by any rectangle is lost. Returns the envelope of the lost cells
    (``None`` when fully covered) and their share of the bbox area (cells
    weighted by ``cos(latitude)``).
    """
    xs = sorted(
        {wgs.min_x, wgs.max_x}
        | {v for e in extents for v in (e.min_x, e.max_x) if wgs.min_x < v < wgs.max_x}
    )
    ys = sorted(
        {wgs.min_y, wgs.max_y}
        | {v for e in extents for v in (e.min_y, e.max_y) if wgs.min_y < v < wgs.max_y}
    )
    total = 0.0
    lost_area = 0.0
    lost: list[tuple[float, float, float, float]] = []
    for x0, x1 in zip(xs, xs[1:], strict=False):
        for y0, y1 in zip(ys, ys[1:], strict=False):
            area = (x1 - x0) * (y1 - y0) * math.cos(math.radians((y0 + y1) / 2))
            total += area
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not any(
                e.min_x <= cx <= e.max_x and e.min_y <= cy <= e.max_y for e in extents
            ):
                lost.append((x0, y0, x1, y1))
                lost_area += area
    if not lost or total <= 0:
        return None, 0.0
    envelope = BBox(
        min(c[0] for c in lost),
        min(c[1] for c in lost),
        max(c[2] for c in lost),
        max(c[3] for c in lost),
        "EPSG:4326",
    )
    return envelope, lost_area / total


def emit_clipping_notices(
    sink: NoticeSink,
    bbox: BBox,
    countries: tuple[str, ...],
    parts: dict,
    *,
    pl_geometry_sheets: bool = False,
    pl_sheet_list: bool = False,
) -> None:
    """``AUTO_CLIPPED``/``AUTO_AREA_OUTSIDE`` for ``country="auto"`` (S3).

    PL by geometry without a cutout downloads sheets of the whole geometry,
    so clipping its auxiliary bbox does not limit the PL download.
    """
    from kartograf.download.countries import EDGES, bbox_to_wgs84
    from kartograf.sources.registry import get_country

    for code in countries:
        if code == "PL" and pl_geometry_sheets:
            continue
        part = parts[code]
        if not part.clipped:
            continue
        extent = get_country(code).extent_wgs84
        edges = ", ".join(
            f"{edge}: {_deg(getattr(extent, attr), unit)}"
            for edge, attr, _is_min, unit in EDGES
            if edge in part.clipped
        )
        if code == "PL" and pl_sheet_list:
            result = (
                "arkusze wyznaczono z przycietego bboxa, sidecar ma "
                "request.sheet; oryginal w extra.parent_request.bbox"
            )
        else:
            result = (
                "plik i request.bbox niosa zasieg przyciety, oryginal "
                "w extra.parent_request.bbox"
            )
        sink.emit(
            "info",
            AUTO_CLIPPED,
            f"--country auto: czesc {code} przycieta do obwiedni kraju "
            f"({edges}); {result}",
        )
    if not any(parts[code].clipped for code in countries):
        return
    if pl_geometry_sheets and "PL" in countries:
        return  # PL reads the WHOLE geometry, also outside the rectangles
    lost, share = area_outside_extents(
        bbox_to_wgs84(bbox), [get_country(c).extent_wgs84 for c in countries]
    )
    if lost is None:
        return
    explicit = "pl" if "PL" in countries else countries[0].lower()
    sink.emit(
        "info",
        AUTO_AREA_OUTSIDE,
        f"--country auto: obszar {_deg(lost.min_x, 'E')}-{_deg(lost.max_x, 'E')}"
        f" x {_deg(lost.min_y, 'N')}-{_deg(lost.max_y, 'N')} (~{share * 100:.0f} % "
        "powierzchni zadania) lezy poza zasiegiem PL/CZ i zostal pominiety; "
        f"caly bbox pobiera jawne --country {explicit} (za granica: arkusze "
        "bez danych / nodata)",
    )
