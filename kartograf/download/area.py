"""Request areas shared by every track: CRS of a bbox and geometry envelopes.

One place for the rules the CLI used to apply on its own (Z1): a bbox in any
supported CRS reaches EPSG:2180 the same way in every track (Czech CRSs only
via the pinned operation), and a ``geometry`` file gives its envelope after
the layer choice is announced as a ``Notice``.
"""

from pathlib import Path

from kartograf.core.bbox import BBox, is_czech_crs, transform_bbox
from kartograf.exceptions import ValidationError
from kartograf.notices import GEOMETRY_LAYER_DEFAULT, NoticeSink


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
        raise ValidationError(f"File not found: {filepath}")
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
