"""
Land cover and HSG in the ``data/`` layout (versioned store spec 3.4).

A segment carries the content parameters (layers, format, year, soil
property, depth, statistic) as lowercase tokens after the descriptor's
``storage_subdir`` prefix; below it the selection: ``teryt/<TERYT>``,
``bbox/<coords>`` (as cutouts) or the sheet hierarchy (as NMT).
"""

import re
from collections.abc import Sequence
from pathlib import Path

from kartograf.core.parser_registry import path_parts
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.fetch import FileSlot
from kartograf.download.storage import bbox_cutout_path, bbox_slot
from kartograf.download.versions import VERSIONS_DIR
from kartograf.exceptions import ValidationError
from kartograf.sources.registry import get_source

# Derived product: no descriptor of its own (D33).
HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"

_TOKEN = re.compile(r"[a-z0-9.-]+")


def _segment(prefix: str, tokens: Sequence[str]) -> str:
    lowered = [str(t).lower() for t in tokens]
    for token in lowered:
        if not _TOKEN.fullmatch(token):
            raise ValidationError(
                f"Niedozwolony element segmentu {token!r} (dozwolone [a-z0-9.-])"
            )
    return "_".join([prefix, *lowered])


def landcover_segment(descriptor_key: str, tokens: Sequence[str]) -> str:
    """``<storage_subdir>_<token>_...`` of a land cover source (lowercase).

    Raises
    ------
    ValidationError
        A token outside ``[a-z0-9.-]`` (after lowercasing).
    """
    return _segment(get_source(descriptor_key).storage_subdir, tokens)


def hsg_segment(depth: str, stat: str) -> str:
    """``hsg/global_soilgrids_<depth>_<stat>`` (lowercase)."""
    return _segment(HSG_SEGMENT_PREFIX, (depth, stat))


def _require_one(teryt: str | None, bbox: BBox | None, sheet: str | None) -> None:
    if sum(x is not None for x in (teryt, bbox, sheet)) != 1:
        raise ValidationError("Podaj dokladnie jeden wybor: teryt, bbox albo sheet")


def selection_slot(
    output_dir: Path,
    segment: str,
    ext: str,
    *,
    teryt: str | None = None,
    bbox: BBox | None = None,
    sheet: str | None = None,
) -> FileSlot:
    """Version slot of one land cover/HSG file (exactly one selection).

    ``teryt`` -> ``<segment>/teryt/<TERYT><ext>``; ``bbox`` (EPSG:2180) ->
    ``<segment>/bbox/<coords><ext>`` (``bbox_slot``); ``sheet`` ->
    ``<segment>/<path_parts>/<canonical sheet><ext>``. Versions live in
    ``<segment>/versions/<same hierarchy>/``.

    Raises
    ------
    ValidationError
        Not exactly one selection, a bbox outside EPSG:2180 or an invalid
        sheet code.
    """
    _require_one(teryt, bbox, sheet)
    output_dir = Path(output_dir)
    base = output_dir / segment / VERSIONS_DIR
    if bbox is not None:
        if bbox.crs != "EPSG:2180":
            raise ValidationError(f"bbox land cover w EPSG:2180, nie {bbox.crs}")
        return bbox_slot(output_dir, segment, bbox, ext)
    if teryt is not None:
        parts, name = ["teryt"], teryt
    else:
        assert sheet is not None
        name = SheetParser(sheet).sheet
        parts = path_parts(name)
    return FileSlot(
        output_dir=output_dir,
        std=output_dir.joinpath(segment, *parts, f"{name}{ext}"),
        versions_base=base,
        versions_root=base.joinpath(*parts),
        ext=ext,
    )


def selection_unit(
    *, teryt: str | None = None, bbox: BBox | None = None, sheet: str | None = None
) -> str:
    """Plan unit of a selection: TERYT, bbox coordinates or the canonical sheet."""
    _require_one(teryt, bbox, sheet)
    if teryt is not None:
        return teryt
    if bbox is not None:
        return bbox_cutout_path(".", "", bbox, "").name
    assert sheet is not None
    return SheetParser(sheet).sheet
