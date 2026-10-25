"""
Hydrologic Soil Group (HSG) calculation from soil texture data.

This module provides functions to:
1. Classify soil texture according to USDA texture triangle
2. Map texture classes to Hydrologic Soil Groups (A, B, C, D)
3. Process SoilGrids raster data to produce HSG maps

Texture -> HSG mapping (TEXTURE_TO_HSG) deliberately deviates from the TR-55
table for sandy_loam (B, not A) and clay_loam / silty_clay_loam (C, not D) -
see docs/DECISIONS.md ADR-025.

Reference:
- USDA-NRCS National Engineering Handbook, Part 630, Chapter 7
- SCS-CN method for runoff estimation
"""

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from kartograf.download.data import (
    DOWNLOAD_FILL,
    DOWNLOAD_KEYS,
    DOWNLOAD_SCHEMA,
    UnitFailure,
    UnitFile,
)
from kartograf.exceptions import ValidationError
from kartograf.messages import message
from kartograf.notices import ALL_NODATA, Notice, NoticeSink
from kartograf.serialization import Document

if TYPE_CHECKING:
    from rasterio.io import DatasetReader

    from kartograf.cache.metadata import MetadataCache
    from kartograf.core.bbox import BBox
    from kartograf.download.fetch import FileSlot, UpdateMode, VersionedFile
    from kartograf.download.plan import ItemStatus, PlanItem, Track, UpdatePlan
    from kartograf.download.versions import ContentDigest, LocalVersion, VersionRef
    from kartograf.landcover.manager import LandCoverManager
    from kartograf.providers.soilgrids import SoilGridsProvider
logger = logging.getLogger(__name__)


# USDA Soil Texture Classes
TEXTURE_CLASSES = {
    "sand": 1,
    "loamy_sand": 2,
    "sandy_loam": 3,
    "loam": 4,
    "silt_loam": 5,
    "silt": 6,
    "sandy_clay_loam": 7,
    "clay_loam": 8,
    "silty_clay_loam": 9,
    "sandy_clay": 10,
    "silty_clay": 11,
    "clay": 12,
}

# Reverse mapping for display
TEXTURE_NAMES = {v: k for k, v in TEXTURE_CLASSES.items()}

# Hydrologic Soil Groups
HSG_VALUES = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
}

# HSG descriptions (user texts: Polish in ASCII, Z5)
HSG_DESCRIPTIONS = {
    "A": message("hydrology.class_a"),
    "B": message("hydrology.class_b"),
    "C": message("hydrology.class_c"),
    "D": message("hydrology.class_d"),
}
# Statistics area: each cell split into _SUBCELLS x _SUBCELLS parts to
# measure its share inside the request area (precision 1 % of a cell).
_SUBCELLS = 10

# Mapping from USDA texture class to HSG
# Based on USDA-NRCS guidelines
TEXTURE_TO_HSG = {
    "sand": "A",
    "loamy_sand": "A",
    "sandy_loam": "B",  # Can be A/B depending on structure
    "loam": "B",
    "silt_loam": "B",
    "silt": "B",
    "sandy_clay_loam": "C",
    "clay_loam": "C",  # Can be C/D
    "silty_clay_loam": "C",
    "sandy_clay": "D",
    "silty_clay": "D",
    "clay": "D",
}


# Canonical USDA texture triangle (Soil Survey Manual) - the SINGLE source of
# truth for both the scalar and the vectorised classifier. A predicate gets
# 100 x the amounts of clay, sand and silt (``c``, ``s``, ``si``) and their
# total ``u``: the share of clay in percent is ``c / u``, so "k percent" is
# ``k * u``. The rules compare amounts and never divide them, which keeps
# every comparison exact (``classify_usda_texture_array``). A predicate
# returns a boolean mask. Order matters: first matching rule wins.
_USDA_RULES: tuple[
    tuple[
        str,
        Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    ],
    ...,
] = (
    ("sand", lambda c, s, si, u: si + 1.5 * c < 15 * u),
    (
        "loamy_sand",
        lambda c, s, si, u: (si + 1.5 * c >= 15 * u) & (si + 2 * c < 30 * u),
    ),
    (
        "sandy_loam",
        lambda c, s, si, u: (
            ((c >= 7 * u) & (c <= 20 * u) & (s > 52 * u) & (si + 2 * c >= 30 * u))
            | ((c < 7 * u) & (si < 50 * u) & (si + 2 * c >= 30 * u))
        ),
    ),
    ("silt", lambda c, s, si, u: (si >= 80 * u) & (c < 12 * u)),
    (
        "silt_loam",
        lambda c, s, si, u: (
            ((si >= 50 * u) & (c >= 12 * u) & (c < 27 * u))
            | ((si >= 50 * u) & (si < 80 * u) & (c < 12 * u))
        ),
    ),
    (
        "loam",
        lambda c, s, si, u: (
            (c >= 7 * u)
            & (c <= 27 * u)
            & (si >= 28 * u)
            & (si < 50 * u)
            & (s <= 52 * u)
        ),
    ),
    (
        "sandy_clay_loam",
        lambda c, s, si, u: (c >= 20 * u) & (c < 35 * u) & (si < 28 * u) & (s > 45 * u),
    ),
    (
        "clay_loam",
        lambda c, s, si, u: (c >= 27 * u) & (c < 40 * u) & (s > 20 * u) & (s <= 45 * u),
    ),
    (
        "silty_clay_loam",
        lambda c, s, si, u: (c >= 27 * u) & (c < 40 * u) & (s <= 20 * u),
    ),
    ("sandy_clay", lambda c, s, si, u: (c >= 35 * u) & (s > 45 * u)),
    ("silty_clay", lambda c, s, si, u: (c >= 40 * u) & (si >= 40 * u)),
    ("clay", lambda c, s, si, u: (c >= 40 * u) & (s <= 45 * u) & (si < 40 * u)),
)


def classify_usda_texture(clay: float, sand: float, silt: float) -> str:
    """
    Classify soil texture according to the USDA texture triangle.

    Canonical USDA texture triangle (Soil Survey Manual), single rule list
    shared with the vectorised variant.

    Parameters
    ----------
    clay : float
        Clay content in percent (0-100)
    sand : float
        Sand content in percent (0-100)
    silt : float
        Silt content in percent (0-100)

    Returns
    -------
    str
        USDA texture class name

    Notes
    -----
    Inputs are normalised to sum to 100% before classification, so any
    consistent unit works (e.g. g/kg).  Inputs summing to 0 (no data) return
    "loam".
    """
    code = int(
        classify_usda_texture_array(
            np.array([clay]), np.array([sand]), np.array([silt])
        )[0]
    )
    return TEXTURE_NAMES[code]


def texture_to_hsg(texture_class: str) -> str:
    """
    Map USDA texture class to Hydrologic Soil Group.

    Parameters
    ----------
    texture_class : str
        USDA texture class name

    Returns
    -------
    str
        Hydrologic Soil Group (A, B, C, or D)
    """
    return TEXTURE_TO_HSG.get(texture_class, "B")


def classify_usda_texture_array(
    clay: np.ndarray, sand: np.ndarray, silt: np.ndarray
) -> np.ndarray:
    """
    Classify soil texture for arrays (vectorized).

    Uses the same canonical rule list (`_USDA_RULES`) as the scalar
    `classify_usda_texture`, evaluated in float64 on the amounts and their
    total: a share is never computed (``clay / total * 100`` rounds, so a
    value exactly on a boundary of the triangle - silt + 2 * clay = 300 g/kg,
    clay = 270 g/kg - would fall on either side by the rounding). Integers
    (the g/kg of SoilGrids) are therefore classified exactly by the rules.

    Parameters
    ----------
    clay : np.ndarray
        Clay amount array (percent or any consistent unit, e.g. g/kg)
    sand : np.ndarray
        Sand amount array, in the same unit
    silt : np.ndarray
        Silt amount array, in the same unit

    Returns
    -------
    np.ndarray
        Array of texture class codes (1-12); cells whose inputs sum to 0
        (no data) get "loam".
    """
    clay = np.asarray(clay, dtype=np.float64)
    sand = np.asarray(sand, dtype=np.float64)
    silt = np.asarray(silt, dtype=np.float64)
    total = clay + sand + silt

    masks = [rule(100 * clay, 100 * sand, 100 * silt, total) for _, rule in _USDA_RULES]
    codes = [TEXTURE_CLASSES[name] for name, _ in _USDA_RULES]

    selected = np.select(masks, codes, default=TEXTURE_CLASSES["loam"])

    # The rules partition the whole simplex, but cells with a zero total are
    # not soil at all - pin them to "loam" explicitly instead of letting the
    # zeros fall into the "sand" rule.
    return np.where(total > 0, selected, TEXTURE_CLASSES["loam"]).astype(np.uint8)


def _nodata_mask(arr: np.ndarray, nodata: float | None) -> np.ndarray:
    """
    Boolean mask of cells that carry no usable value.

    Covers NaN/Inf (which survive any arithmetic and would otherwise be
    classified as soil) plus the raster's own nodata tag, when it has one.
    """
    mask = ~np.isfinite(arr)
    if nodata is not None:
        mask |= arr == nodata
    return mask


def texture_to_hsg_array(texture: np.ndarray) -> np.ndarray:
    """
    Map texture class array to HSG array.

    Parameters
    ----------
    texture : np.ndarray
        Array of texture class codes (1-12)

    Returns
    -------
    np.ndarray
        Array of HSG codes (1-4 for A-D)
    """
    # Mapping array: texture code (1-12) -> HSG code (1-4)
    mapping = np.array(
        [
            0,  # 0 - no data
            1,  # 1 - sand -> A
            1,  # 2 - loamy_sand -> A
            2,  # 3 - sandy_loam -> B
            2,  # 4 - loam -> B
            2,  # 5 - silt_loam -> B
            2,  # 6 - silt -> B
            3,  # 7 - sandy_clay_loam -> C
            3,  # 8 - clay_loam -> C
            3,  # 9 - silty_clay_loam -> C
            4,  # 10 - sandy_clay -> D
            4,  # 11 - silty_clay -> D
            4,  # 12 - clay -> D
        ],
        dtype=np.uint8,
    )

    result: np.ndarray = mapping[texture]
    return result


def _geographic_row_cell_areas(src: "DatasetReader") -> np.ndarray:
    """
    Geodetic area (m2) of one cell in every row of a geographic raster.

    For a CRS in degrees the affine determinant is square degrees, not square
    metres.  Cell area on the ellipsoid depends on latitude only (all cells in
    a row are congruent), so one polygon per row is enough.

    Parameters
    ----------
    src : rasterio.DatasetReader
        Open raster whose CRS is geographic.

    Returns
    -------
    np.ndarray
        Array of shape (height,) with the area in m2 of a single cell in
        each row, top row first.
    """
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    areas = np.empty(src.height, dtype=np.float64)

    for row in range(src.height):
        lon0, top = src.transform * (0, row)
        lon1, bottom = src.transform * (1, row + 1)
        area, _ = geod.polygon_area_perimeter(
            [lon0, lon1, lon1, lon0], [bottom, bottom, top, top]
        )
        areas[row] = abs(area)

    return areas


def _classify_hsg(
    clay: np.ndarray,
    sand: np.ndarray,
    silt: np.ndarray,
    nodata: tuple[float | None, float | None, float | None],
) -> np.ndarray:
    """HSG classes (uint8, 0 = nodata) from clay/sand/silt in g/kg.

    The texture comes from the RAW g/kg values by exact arithmetic
    (``classify_usda_texture_array`` compares them with their total, no unit
    conversion and no division); nodata comes from the raw values too: the
    texture classifier falls back to loam for anything it cannot place.
    All-zero triplets are gaps (SoilGrids convention).
    """
    texture = classify_usda_texture_array(clay, sand, silt)
    hsg = texture_to_hsg_array(texture)
    mask = (
        _nodata_mask(clay, nodata[0])
        | _nodata_mask(sand, nodata[1])
        | _nodata_mask(silt, nodata[2])
    )
    mask |= (clay == 0) & (sand == 0) & (silt == 0)
    hsg[mask] = 0
    return hsg


def _write_hsg_geotiff(
    output_path: Path, hsg: np.ndarray, profile: dict[str, Any]
) -> None:
    """Write HSG classes as uint8 GeoTIFF (nodata 0) with the band tags."""
    import rasterio

    profile = {
        **profile,
        "dtype": rasterio.uint8,
        "count": 1,
        "nodata": 0,
        "compress": "deflate",
    }
    # The directory appears only now, so a failed input leaves none behind.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(hsg, 1)
        dst.update_tags(
            1,
            LAYER_NAME="Hydrologic Soil Group",
            LAYER_DESCRIPTION="HSG classification: 1=A, 2=B, 3=C, 4=D",
        )


# SoilGrids inputs of HSG, in the order of ``HsgReport.inputs``.
HSG_INPUTS = ("clay", "sand", "silt")
_HSG_CLASSES = "1=A, 2=B, 3=C, 4=D"
_HSG_TRACK: "Track" = "hsg"
# HSG always classifies the mean texture estimate (R3): the store segments
# ``soil/global_soilgrids_<prop>_<depth>_mean`` and
# ``hsg/global_soilgrids_<depth>_mean`` and the sidecar ``stat`` stay as before.
_HSG_STAT = "mean"
# The source of the inputs and of the HSG sidecar.
_SOILGRIDS = "global.isric.soilgrids"
# Sidecar ``product`` of the HSG raster: its command and store directory
# (``soil hsg`` -> ``hsg/``; the inputs stay ``soil``).
_HSG_PRODUCT = "hsg"
# Where ``calculate_hsg`` writes (the ``--output`` help of ``soil hsg`` and
# the error of a call without a store).
HSG_OUTPUT_FILES = message("hydrology.hsg_output_files")
_OUTPUT_REQUIRED = message(
    "hydrology.output_required", hsg_output_files=HSG_OUTPUT_FILES
)


@dataclass(frozen=True)
class HsgReport(Document):
    """Outcome of ``calculate_hsg`` (``soil hsg``; ``kartograf-download/1``).

    ``files``: the HSG raster (one ``UnitFile``, ``unit`` = bbox coordinates
    or the sheet, ``country`` = ``GLOBAL``; status ``new``/``unchanged``/
    ``relabeled`` when computed, ``reused`` when a version of the same input
    set exists, ``local`` for a position left out of a plan; none when an
    input failed, or out of a plan without a local version). ``inputs``:
    clay, sand and silt in the store (``unit`` = ``"<property> <unit>"``,
    e.g. ``"clay N-34-130-D"``). ``failed``: an input that failed (its unit
    as in ``inputs``; no HSG is computed) or the store failure of the HSG.
    ``stale``: planned positions whose source changed since the plan.
    ``notices``: data messages (e.g. the geometry layer choice). ``ok``: no
    failure and no stale position. ``summary``: ``hsg_statistics`` of the
    HSG raster, only when ``calculate_hsg(summary=True)`` and the report has
    the raster; else ``None``.
    """

    SCHEMA = DOWNLOAD_SCHEMA
    JSON_KEYS = DOWNLOAD_KEYS
    JSON_FILL = {key: DOWNLOAD_FILL[key] for key in ("raw", "superseded")}

    files: "tuple[UnitFile, ...]"
    inputs: "tuple[UnitFile, ...]"
    failed: "tuple[UnitFailure, ...]"
    stale: "tuple[PlanItem, ...]"
    notices: "tuple[Notice, ...]"
    ok: bool
    summary: "dict[str, Any] | None" = None


class HSGCalculator:
    """
    Compute Hydrologic Soil Groups from SoilGrids in the version store.

    Hydrologic Soil Groups from SoilGrids clay/sand/silt in the version
    store (the layer below ``calculate_hsg``/``check_hsg``; not in the
    public API).

    The inputs are SoilGrids ``mean`` versions of ``output_dir``
    (``soil/global_soilgrids_{clay,sand,silt}_<depth>_mean/``, labelled by
    the SoilGrids edition, D33); the HSG raster is a version of
    ``hsg/global_soilgrids_<depth>_mean/`` with the same selection
    hierarchy (``bbox/<coords>`` or the sheet hierarchy). A version whose
    ``extra.source_files`` has the same three input sha256 is used again
    (``reused``, nothing computed). Rasters outside the store:
    ``hsg_from_rasters``.
    """

    def __init__(
        self,
        output_dir: str | Path,
        provider: "SoilGridsProvider | None" = None,
        cache: "MetadataCache | bool" = True,
    ) -> None:
        """
        Initialize HSG calculator.

        Parameters
        ----------
        output_dir : str or Path
            Store root (``--output``); created only when a file is written.
        provider : SoilGridsProvider, optional
            Provider of the inputs (keeps its own cache). Default: a
            SoilGrids provider using ``cache``.
        cache : MetadataCache or bool
            ``True`` = default metadata cache in the current directory, a
            ``MetadataCache`` = that cache, ``False`` = none (default provider).
        """
        self._output_dir = Path(output_dir)
        if self._output_dir.suffix.lower() in (".tif", ".tiff"):
            raise ValidationError(
                message("hydrology.output_is_store_dir"),
                option="output_dir",
            )
        self._provider = provider
        self._cache = cache

    @property
    def provider(self) -> "SoilGridsProvider":
        """Return the input provider without changing cache ownership."""
        if self._provider is not None:
            return self._provider
        from kartograf.providers.soilgrids import SoilGridsProvider

        return SoilGridsProvider()

    def calculate_hsg(
        self,
        *,
        sheet: str | None = None,
        bbox: "BBox | None" = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        depth: str | None,
        update: "UpdateMode | None" = None,
        plan: "UpdatePlan | None" = None,
        on_notice: "Callable[[Notice], None] | None" = None,
    ) -> HsgReport:
        """HSG of one selection (see the module function ``calculate_hsg``).

        Raises
        ------
        ValidationError
            Not exactly one selection, a missing or invalid depth, bad mode,
            a plan of another store or without ``update="upgrade"``.
        """
        sink = NoticeSink(on_notice)
        selection = self._validated(sheet, bbox, geometry, layer, depth, sink)
        assert depth is not None  # checked with the selection
        report = self._calculate(selection, depth, _HSG_STAT, update, plan, sink)
        return replace(report, notices=sink.notices)

    def check_hsg(
        self,
        *,
        sheet: str | None = None,
        bbox: "BBox | None" = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        depth: str | None,
        on_notice: "Callable[[Notice], None] | None" = None,
    ) -> "UpdatePlan":
        """Return the plan of ``calculate_hsg`` without downloading or computing.

        Plan of ``calculate_hsg`` with the same selection, WITHOUT
        downloading or computing: 3 x ``landcover`` + 1 x ``hsg``.
        """
        sink = NoticeSink(on_notice)
        selection = self._validated(sheet, bbox, geometry, layer, depth, sink)
        assert depth is not None  # checked with the selection
        plan = self._check(selection, depth, _HSG_STAT, sink)
        return replace(plan, notices=sink.notices)

    def validate_request(
        self,
        *,
        sheet: str | None = None,
        bbox: "BBox | None" = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        depth: str | None,
    ) -> None:
        """Check the request of ``calculate_hsg`` before the first network access.

        Every check of ``calculate_hsg``/``check_hsg`` before the first
        request: one selection and the input depth (no network, nothing
        written; a ``geometry`` file is read for its envelope) - the same
        exception type and text as ``calculate_hsg`` (``project add``,
        ADR-040).

        Raises
        ------
        ValidationError
            Not exactly one selection, an invalid sheet code or depth.
        """
        self._validated(sheet, bbox, geometry, layer, depth, NoticeSink(None))

    def _validated(
        self,
        sheet: str | None,
        bbox: "BBox | None",
        geometry: str | Path | None,
        layer: str | None,
        depth: str | None,
        sink: NoticeSink,
    ) -> dict[str, Any]:
        """Check the selection, then the depth by the input manager's own checks."""
        selection = self._selection(sheet, bbox, geometry, layer, sink)
        self._manager().validate_request(
            **_where(selection), property=HSG_INPUTS[0], depth=depth, stat=_HSG_STAT
        )
        return selection

    @staticmethod
    def _selection(
        sheet: str | None,
        bbox: "BBox | None",
        geometry: str | Path | None,
        layer: str | None,
        sink: "NoticeSink",
    ) -> dict[str, Any]:
        """HSG selection: the canonical sheet or an EPSG:2180 bbox."""
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.download.area import bbox_to_2180, geometry_envelope_2180
        from kartograf.download.options import (
            check_layer,
            require_geometry_area,
            validate_request_bbox,
        )
        from kartograf.exceptions import ValidationError

        if sum(v is not None for v in (sheet, bbox, geometry)) != 1:
            raise ValidationError(
                message("hydrology.exactly_one_selection"),
                options=("sheet", "bbox", "geometry"),
            )
        check_layer(layer, geometry)
        if sheet is not None:
            return {"sheet": SheetParser(sheet).sheet}
        if geometry is not None:
            envelope = geometry_envelope_2180(geometry, layer, sink)
            require_geometry_area(envelope, message("hydrology.hsg_calculation"))
            return _bbox_request(envelope)
        assert bbox is not None
        return _bbox_request(bbox_to_2180(validate_request_bbox(bbox)))

    # -------------------------------------------------------------------------

    def _manager(self) -> "LandCoverManager":
        from kartograf.landcover.manager import LandCoverManager

        if self._provider is None:  # by name: the manager attaches the cache
            return LandCoverManager(self._output_dir, "soilgrids", cache=self._cache)
        return LandCoverManager(self._output_dir, self._provider)

    def _slot(self, selection: dict[str, Any], depth: str, stat: str) -> "FileSlot":
        from kartograf.download.storage import unit_slot
        from kartograf.landcover.store import hsg_segment

        return unit_slot(
            self._output_dir,
            hsg_segment(depth, stat),
            ".tif",
            bbox=selection.get("bbox_obj"),
            sheet=selection.get("sheet"),
        )

    def _check(
        self, selection: dict[str, Any], depth: str, stat: str, sink: "NoticeSink"
    ) -> "UpdatePlan":
        from kartograf.download.plan import new_plan

        inputs = self._input_items(selection, depth, stat, sink)
        return new_plan(
            self._output_dir, [*inputs, self._hsg_item(selection, depth, stat, inputs)]
        )

    def _input_items(
        self, selection: dict[str, Any], depth: str, stat: str, sink: "NoticeSink"
    ) -> list[Any]:
        manager = self._manager()
        where = _where(selection)
        return [
            item
            for prop in HSG_INPUTS
            for item in manager.check(
                **where, property=prop, depth=depth, stat=stat, on_notice=sink.add
            ).items
        ]

    def _hsg_item(
        self, selection: dict[str, Any], depth: str, stat: str, inputs: list[Any]
    ) -> "PlanItem":
        """Return the plan position of the HSG.

        Plan position of the HSG: ``current`` when a version of the current
        local inputs exists and every input is current; ``check_failed`` when an
        input could not be checked; otherwise ``missing`` (to compute).
        """
        from kartograf.download.fetch import local_version
        from kartograf.download.plan import PlanItem
        from kartograf.landcover.store import selection_unit

        slot = self._slot(selection, depth, stat)
        labels = [i.available_label for i in inputs]
        label = "+".join(sorted(set(labels))) if all(labels) else None
        failed = [i for i in inputs if i.status == "check_failed"]
        shas = tuple(i.local_sha256 for i in inputs)
        reusable = _matching_version(slot, shas) if all(shas) else None
        local = local_version(slot)
        status: ItemStatus
        if failed:
            status = "check_failed"
        elif reusable is not None and all(i.status == "current" for i in inputs):
            status = "current"
        else:
            status = "missing"
        return PlanItem(
            track=_HSG_TRACK,
            segment=slot.segment,
            hierarchy=slot.hierarchy,
            name=slot.name,
            unit=selection_unit(
                bbox=selection.get("bbox_obj"), sheet=selection.get("sheet")
            ),
            local_label=local.label if local is not None else None,
            local_sha256=local.sha256 if local is not None else None,
            available_label=label,
            available_signal=None,
            status=status,
            error=failed[0].error if failed else None,
        )

    def _calculate(
        self,
        selection: dict[str, Any],
        depth: str,
        stat: str,
        update: "UpdateMode | None",
        plan: "UpdatePlan | None",
        sink: "NoticeSink",
    ) -> HsgReport:
        """Run the inputs, then the HSG of their set.

        The inputs, then the HSG of their set (computed or reused). An
        input that failed leaves the HSG out (its failure in ``failed``);
        a plan without the HSG position keeps its local version.
        """
        from kartograf.download.data import UnitFailure, UnitFile
        from kartograf.download.fetch import validate_update
        from kartograf.download.plan import require_store, select_planned, store_id
        from kartograf.exceptions import DownloadError, ValidationError
        from kartograf.landcover.store import selection_unit
        from kartograf.sources.registry import get_source

        validate_update(update, check="check_hsg")
        slot = self._slot(selection, depth, stat)
        unit = selection_unit(
            bbox=selection.get("bbox_obj"), sheet=selection.get("sheet")
        )
        planned_hsg = True
        stale: list[Any] = []
        if plan is not None:
            if update != "upgrade":
                raise ValidationError(
                    message("hydrology.plan_requires_upgrade"),
                    options=("plan", "update"),
                )
            require_store(plan, store_id(self._output_dir))
            # The HSG position is checked BEFORE the inputs change.
            fresh = self._hsg_item(
                selection,
                depth,
                stat,
                self._input_items(selection, depth, stat, sink),
            )
            todo, skipped = select_planned(plan, [fresh], _HSG_TRACK)
            planned_hsg, stale = bool(todo), list(skipped)

        manager = self._manager()
        where = _where(selection)
        inputs: list[UnitFile] = []
        failed: list[UnitFailure] = []
        for prop in HSG_INPUTS:
            report = manager.download(
                **where,
                update=update,
                plan=_input_plan(plan, prop, depth, stat),
                property=prop,
                depth=depth,
                stat=stat,
                on_notice=sink.add,
            )
            # one raster per input (a plan may leave it without a file); its
            # unit names the property, as the inputs pinned by a project
            inputs += [replace(i, unit=f"{prop} {i.unit}") for i in report.files]
            failed += [replace(i, unit=f"{prop} {i.unit}") for i in report.failed]
            stale.extend(report.stale)
        country = get_source(_SOILGRIDS).country
        hsg: VersionedFile | None = None
        if not failed:  # no HSG of an incomplete input set
            if not planned_hsg or len(inputs) != len(HSG_INPUTS):
                hsg = _local_only(slot)
            else:
                try:
                    hsg = self._reuse_or_compute(
                        slot, selection, depth, stat, [i.file for i in inputs], sink
                    )
                except DownloadError as e:  # the store: a failure of the HSG
                    logger.debug("HSG %s: %s", unit, e)
                    failed.append(UnitFailure(unit, country, str(e), "download"))
        files = (UnitFile(unit, country, hsg),) if hsg is not None else ()
        return HsgReport(
            files=files,
            inputs=tuple(inputs),
            failed=tuple(failed),
            stale=tuple(stale),
            notices=(),
            ok=not failed and not stale,
        )

    def _reuse_or_compute(
        self,
        slot: "FileSlot",
        selection: dict[str, Any],
        depth: str,
        stat: str,
        files: "list[VersionedFile]",
        sink: "NoticeSink",
    ) -> "VersionedFile":
        """Return the HSG version of these inputs, reusing or computing it.

        The HSG version of these inputs: reused, or computed and stored (a
        computed HSG without a single class - every input cell is a gap -
        gets ``extra.all_nodata`` and the ``ALL_NODATA`` warning).
        """
        import rasterio

        from kartograf.download.fetch import (
            VersionedFile,
            discard_staging,
            link_version,
            new_staging,
            store_file,
        )
        from kartograf.download.versions import VersionRef
        from kartograf.sources.sidecar import emit_sidecar

        shas = tuple(f.sha256 for f in files)
        match = _matching_version(slot, shas)
        if match is not None:
            link_version(slot.std, match, refresh=True)
            logger.info(f"HSG {slot.std}: version {match.label} reused")
            return VersionedFile(
                slot.std, "reused", match.label, match.sha256, match.path
            )

        label = "+".join(sorted({f.label for f in files}))
        staged = new_staging(slot)
        try:
            arrays, nodatas = [], []
            for f in files:
                with rasterio.open(f.version_path) as src:
                    arrays.append(src.read(1).astype(np.float64))
                    nodatas.append(src.nodata)
                    if len(arrays) == 1:  # grid of clay = grid of the result
                        profile = src.profile.copy()
            logger.info("Classifying HSG...")
            hsg = _classify_hsg(
                arrays[0], arrays[1], arrays[2], (nodatas[0], nodatas[1], nodatas[2])
            )
            empty = not hsg.any()
            _write_hsg_geotiff(staged, hsg, profile)
        except BaseException:
            discard_staging(staged, slot)
            raise
        crs = profile.get("crs")
        request = {k: v for k, v in selection.items() if k != "bbox_obj"}
        extra: dict[str, object] = {
            "derived": "hsg",
            "depth": depth,
            "stat": stat,
            "classes": _HSG_CLASSES,
            "source_layers": list(HSG_INPUTS),
            "source_files": [
                {
                    "name": name,
                    "file": f.version_path.relative_to(self._output_dir).as_posix(),
                    "sha256": f.sha256,
                    "label": f.label,
                }
                for name, f in zip(HSG_INPUTS, files, strict=True)
            ],
        }
        if empty:
            extra["all_nodata"] = True

        def write(
            data: Path,
            ref: "VersionRef",
            dg: "ContentDigest",
            _http: dict[str, Any] | None,
        ) -> None:
            emit_sidecar(
                _SOILGRIDS,
                data,
                request=request,
                horizontal_crs=str(crs) if crs else None,
                capability="bbox_raster",
                nodata=0,
                extra=extra,
                exclusive=True,
                digest=(dg.sha256, dg.size_bytes),
                version=ref.to_extra(),
                product=_HSG_PRODUCT,
            )

        stored = store_file(
            slot,
            staged,
            version=VersionRef(label, "edition"),
            write_sidecar=write,
            http=None,
            signal="metadata",
        )
        if empty:
            sink.emit(
                "warning",
                ALL_NODATA,
                message(
                    "hydrology.hsg_all_nodata",
                    relative_to=stored.path.relative_to(self._output_dir).as_posix(),
                ),
            )
        return stored


def _calculator(
    output_dir: str | Path | None, cache: "MetadataCache | bool"
) -> HSGCalculator:
    """Return the calculator of the store ``output_dir`` (checked first)."""
    if output_dir is None:
        raise ValidationError(_OUTPUT_REQUIRED, option="output_dir")
    return HSGCalculator(output_dir, cache=cache)


def calculate_hsg(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: "BBox | None" = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    depth: str | None = None,
    update: "UpdateMode | None" = None,
    plan: "UpdatePlan | None" = None,
    summary: bool = False,
    cache: "MetadataCache | bool" = True,
    on_notice: "Callable[[Notice], None] | None" = None,
) -> HsgReport:
    """Calculate Hydrologic Soil Groups of an area in the version store.

    Hydrologic Soil Groups of an area (``soil hsg``) in the version store
    of ``output_dir``.

    Parameter names and values are the flags of the command in
    ``snake_case``. One area: ``sheet`` (canonical code, sheet hierarchy),
    ``bbox`` (any supported CRS; ``bbox/<coords>`` of its EPSG:2180
    envelope) or ``geometry`` (SHP/GPKG, ``layer`` of a GPKG); ``depth``
    (required): 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm or 100-200cm, the
    statistic is always ``mean``. The inputs are the SoilGrids clay, sand and
    silt of the area in the store
    (``soil/global_soilgrids_<property>_<depth>_mean/``, downloaded when
    missing); the HSG raster ``hsg/global_soilgrids_<depth>_mean/`` (uint8,
    1=A, 2=B, 3=C, 4=D, 0 = no data) is computed only for a new input set,
    a version of the same inputs is used again (``reused``). ``update`` is
    the mode of the INPUTS (spec 4.2); ``plan`` from ``check_hsg`` with
    ``update="upgrade"``; ``summary``: also put ``hsg_statistics`` of the HSG
    raster into the report (``soil hsg --summary``); ``cache``: SoilGrids
    metadata cache (``True``: default file in the current directory,
    ``False``: none); ``on_notice`` receives each notice when emitted.
    Statistics of any HSG raster: ``hsg_statistics``; rasters outside the
    store: ``hsg_from_rasters``.

    Returns
    -------
    HsgReport
        ``files`` (the HSG raster), ``inputs``, ``failed`` (an input that
        failed - no HSG is computed - or the store failure of the HSG),
        ``stale``, ``notices``, ``ok`` and ``summary`` (``None`` unless
        ``summary=True`` and the report has the HSG raster).

    Raises
    ------
    ValidationError
        Missing store (or a ``.tif`` path - a file outside the store is
        ``hsg_from_rasters``), not exactly one selection, a missing or
        invalid depth, bad mode, a plan of another store or without
        ``update="upgrade"`` - before any request.

    Examples
    --------
    >>> report = calculate_hsg(
    ...     output_dir="./data", sheet="N-34-130-D", depth="0-5cm"
    ... )
    >>> hsg = report.files[0].file
    >>> hsg.path, hsg.status  # data/hsg/.../N-34-130-D.tif, "new"
    >>> hsg_statistics(hsg.path)["B"]["percent"]
    """
    report = _calculator(output_dir, cache).calculate_hsg(
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        depth=depth,
        update=update,
        plan=plan,
        on_notice=on_notice,
    )
    if summary and report.files:
        return replace(report, summary=hsg_statistics(report.files[0].file.path))
    return report


def check_hsg(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: "BBox | None" = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    depth: str | None = None,
    cache: "MetadataCache | bool" = True,
    on_notice: "Callable[[Notice], None] | None" = None,
) -> "UpdatePlan":
    """Return the update plan of ``calculate_hsg`` without downloading.

    Update plan of ``calculate_hsg`` with the same choice, WITHOUT
    downloading or computing: the three inputs (track ``landcover``,
    compared with the SoilGrids edition) and the HSG (track ``hsg``:
    ``current`` when a version of the current inputs exists, else
    ``missing``).

    Raises
    ------
    ValidationError
        Invalid or missing choice (as ``calculate_hsg``).
    """
    return _calculator(output_dir, cache).check_hsg(
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        depth=depth,
        on_notice=on_notice,
    )


def validate_hsg_request(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: "BBox | None" = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    depth: str | None = None,
) -> None:
    """Check the request of ``calculate_hsg`` before the first network access.

    Every check of ``calculate_hsg``/``check_hsg`` before the first
    request: the store, one selection and the input depth (no network,
    nothing written; a ``geometry`` file is read for its envelope) - the
    same exception type and text as ``calculate_hsg`` (``project add``,
    ADR-040).

    Raises
    ------
    ValidationError
        Invalid or missing choice.
    """
    _calculator(output_dir, False).validate_request(
        sheet=sheet, bbox=bbox, geometry=geometry, layer=layer, depth=depth
    )


def hsg_statistics(hsg_path: str | Path) -> dict[str, Any]:
    """
    Compute statistics of an HSG raster over its request area.

    Statistics of an HSG raster over its request area (``soil hsg
    --summary``).

    The area is the ``request`` of the raster's sidecar: the bbox
    (``calculate_hsg``: the EPSG:2180 envelope of ``bbox``/``geometry``;
    ``hsg_from_rasters``: its grid) or the sheet frame. The SoilGrids grid
    reaches beyond the area, so each cell counts with its share inside it;
    without a sidecar area the whole raster is counted.

    Parameters
    ----------
    hsg_path : str or Path
        Path to an HSG GeoTIFF (``calculate_hsg``, ``hsg_from_rasters``).

    Returns
    -------
    dict
        Per-group dict (``A``-``D``) with keys: count (cells of the group
        touching the area), area_m2, area_ha (the group's area inside the
        area), percent (share of the area WITH data), description; plus
        ``nodata`` - the cells without data (class 0: an input gap, e.g.
        a SoilGrids cell with 0 in every input) with the same keys and
        ``percent`` = share of the WHOLE area. The areas of all keys add up
        to the area.

    Notes
    -----
    Areas are in square metres / hectares regardless of the raster CRS:
    for a geographic CRS (SoilGrids output is EPSG:4326) cell areas are
    computed geodetically per raster row, not from the affine
    determinant, which would give square degrees.
    """
    import rasterio

    area = _request_area(Path(hsg_path))
    with rasterio.open(hsg_path) as src:
        hsg = src.read(1)
        if src.crs is not None and src.crs.is_geographic:
            # transform[0]*transform[4] would be square DEGREES here
            row_area = _geographic_row_cell_areas(src)
        else:
            row_area = np.full(
                src.height, abs(src.transform[0] * src.transform[4])
            )  # m²
        share = (
            np.ones(hsg.shape)
            if area is None or src.crs is None
            else _area_shares(src, area)
        )

    # m2 of every cell inside the area; group shares of the area with data,
    # the cells without data (0) get their own entry (share of the area)
    cell_m2 = share * row_area[:, None]
    total_m2 = float(np.sum(cell_m2))
    valid_m2 = float(np.sum(cell_m2[hsg > 0]))
    stats = {}

    for name, value in HSG_VALUES.items():
        group = hsg == value
        area_m2 = float(np.sum(cell_m2[group]))
        stats[name] = {
            "count": int(np.sum(group & (share > 0))),
            "area_m2": area_m2,
            "area_ha": area_m2 / 10000,
            "percent": area_m2 / valid_m2 * 100 if valid_m2 > 0 else 0.0,
            "description": HSG_DESCRIPTIONS[name],
        }

    empty = hsg == 0
    empty_m2 = float(np.sum(cell_m2[empty]))
    stats["nodata"] = {
        "count": int(np.sum(empty & (share > 0))),
        "area_m2": empty_m2,
        "area_ha": empty_m2 / 10000,
        "percent": empty_m2 / total_m2 * 100 if total_m2 > 0 else 0.0,
        "description": message("hydrology.stat_nodata_description"),
    }
    return stats


def _request_area(hsg_path: Path) -> "BBox | None":
    """Return the request area of an HSG raster from its sidecar.

    The request area of an HSG raster from its sidecar: ``request.bbox``
    in ``request.bbox_crs`` or the frame of ``request.sheet``; ``None``
    without a readable sidecar or area.
    """
    import json

    from kartograf.core.bbox import BBox
    from kartograf.core.sheet_parser import SheetParser

    try:
        meta = json.loads(
            hsg_path.with_name(f"{hsg_path.name}.meta.json").read_text("utf-8")
        )
    except (OSError, ValueError):
        return None
    request = meta.get("request") if isinstance(meta, dict) else None
    if not isinstance(request, dict):
        return None
    if request.get("bbox") and request.get("bbox_crs"):
        min_x, min_y, max_x, max_y = request["bbox"]
        return BBox(min_x, min_y, max_x, max_y, request["bbox_crs"])
    if request.get("sheet"):
        return SheetParser(request["sheet"]).get_bbox()
    return None


def _area_shares(src: "DatasetReader", area: "BBox") -> np.ndarray:
    """Share (0-1) of every raster cell inside ``area``.

    The area outline (densified edges) is transformed to the raster CRS and
    rasterized on a grid ``_SUBCELLS`` times finer; a cell's share is the
    part of its subcells inside.
    """
    from pyproj import Transformer
    from rasterio.features import geometry_mask
    from rasterio.transform import Affine

    steps = np.linspace(0.0, 1.0, 64, endpoint=False)
    dx, dy = area.max_x - area.min_x, area.max_y - area.min_y
    xs = np.concatenate(
        [
            area.min_x + steps * dx,
            np.full(steps.size, area.max_x),
            area.max_x - steps * dx,
            np.full(steps.size, area.min_x),
        ]
    )
    ys = np.concatenate(
        [
            np.full(steps.size, area.min_y),
            area.min_y + steps * dy,
            np.full(steps.size, area.max_y),
            area.max_y - steps * dy,
        ]
    )
    to_raster = Transformer.from_crs(area.crs, src.crs.to_wkt(), always_xy=True)
    rx, ry = to_raster.transform(xs, ys)
    ring = [(float(x), float(y)) for x, y in zip(rx, ry, strict=True)]
    inside = geometry_mask(
        [{"type": "Polygon", "coordinates": [[*ring, ring[0]]]}],
        out_shape=(src.height * _SUBCELLS, src.width * _SUBCELLS),
        transform=src.transform * Affine.scale(1 / _SUBCELLS),
        invert=True,
    )
    shares: np.ndarray = inside.reshape(
        src.height, _SUBCELLS, src.width, _SUBCELLS
    ).mean(axis=(1, 3))
    return shares


def hsg_from_rasters(
    clay: Path,
    sand: Path,
    silt: Path,
    *,
    bbox: "BBox",
    crs: str,
    pixel_m: float,
    output_path: Path,
) -> Path:
    """HSG raster from ready clay/sand/silt rasters (g/kg) on an explicit grid (A8).

    Each input is reprojected with a pinned operation (``CONTENT_POLICY``,
    bilinear) onto the grid anchored at ``bbox`` (converted to ``crs``) with
    ``pixel_m`` pixels, then classified like ``calculate_hsg``:
    input nodata from its tag only (no tag = no nodata value), cells outside
    an input and all-zero triplets are gaps (0). No configuration defaults.

    Raises
    ------
    TransformError
        No safe pinned operation from an input CRS to ``crs``.
    ValidationError
        ``pixel_m`` not positive.
    """
    import rasterio

    from kartograf.core.bbox import transform_bbox
    from kartograf.exceptions import ValidationError
    from kartograf.transform.crs import CONTENT_POLICY, build_pinned_transform
    from kartograf.transform.raster import warp_to_grid

    if pixel_m <= 0:
        raise ValidationError(
            message("hydrology.pixel_m_not_positive", pixel_m=pixel_m), option="pixel_m"
        )
    grid = bbox if bbox.crs == crs else transform_bbox(bbox, crs)
    layers = {"clay": Path(clay), "sand": Path(sand), "silt": Path(silt)}
    arrays: dict[str, np.ndarray] = {}
    nodatas: dict[str, float | None] = {}
    profile: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, src_path in layers.items():
            with rasterio.open(src_path) as src:
                src_crs = src.crs.to_string()
                nodatas[name] = src.nodata  # tag only, like calculate_hsg
            pinned = build_pinned_transform(src_crs, crs, CONTENT_POLICY)
            warped = Path(tmp) / f"{name}.tif"
            # Untagged input: NaN as the warp fill - cells outside the input
            # become NaN, which _nodata_mask catches; no value is masked.
            fill = nodatas[name]
            warp_to_grid(
                src_path,
                warped,
                grid,
                pixel_m,
                pinned,
                src_crs=src_crs,
                nodata=float("nan") if fill is None else fill,
            )
            with rasterio.open(warped) as w:
                arrays[name] = w.read(1).astype(np.float64)
                profile = w.profile.copy()
    hsg = _classify_hsg(
        arrays["clay"],
        arrays["sand"],
        arrays["silt"],
        (nodatas["clay"], nodatas["sand"], nodatas["silt"]),
    )
    output_path = Path(output_path)
    _write_hsg_geotiff(output_path, hsg, profile)
    _write_rasters_sidecar(output_path, grid, crs, layers)
    return output_path


def _write_rasters_sidecar(
    output_path: Path, grid: "BBox", crs: str, layers: dict[str, Path]
) -> None:
    """Best-effort sidecar of hsg_from_rasters (inputs identified by sha256)."""
    from kartograf.core.bbox import bbox_coords
    from kartograf.sources.sidecar import emit_sidecar, file_digest

    emit_sidecar(
        _SOILGRIDS,
        output_path,
        request={
            "bbox": bbox_coords(grid),
            "bbox_crs": crs,
        },
        horizontal_crs=crs,
        capability="bbox_raster",
        nodata=0,
        extra={
            "derived": "hsg",
            "source_layers": list(layers),
            "source_files": [
                {"name": name, "file": path.name, "sha256": file_digest(path)[0]}
                for name, path in layers.items()
            ],
            "classes": "1=A, 2=B, 3=C, 4=D",
        },
        product=_HSG_PRODUCT,
    )


def _bbox_request(bbox: "BBox") -> dict[str, Any]:
    """HSG selection of a bbox: sidecar ``request`` + the ``BBox`` itself."""
    from kartograf.core.bbox import bbox_coords

    return {
        "bbox": bbox_coords(bbox),
        "bbox_crs": bbox.crs,
        "bbox_obj": bbox,
    }


def _input_plan(
    plan: "UpdatePlan | None", prop: str, depth: str, stat: str
) -> "UpdatePlan | None":
    """Narrow the plan to the positions of one input.

    The plan positions of one input (its segment): the other inputs are
    separate requests of the manager, not files that left the selection.
    """
    if plan is None:
        return None
    from dataclasses import replace

    from kartograf.download.storage import content_segment

    segment = content_segment(_SOILGRIDS, (prop, depth, stat))
    return replace(plan, items=tuple(i for i in plan.items if i.segment == segment))


def _where(selection: dict[str, Any]) -> dict[str, Any]:
    """``LandCoverManager`` selection keyword of an HSG selection."""
    if "sheet" in selection:
        return {"sheet": selection["sheet"]}
    return {"bbox": selection["bbox_obj"]}


def _matching_version(slot: "FileSlot", shas: tuple[str, ...]) -> "LocalVersion | None":
    """Return the newest HSG version computed from inputs with these sha256."""
    from kartograf.download.versions import list_versions, newest_version

    def inputs_of(version: "LocalVersion") -> tuple[str, ...]:
        extra = version.meta.get("extra") or {}
        files = extra.get("source_files") or []
        return tuple(str(f.get("sha256")) for f in files if isinstance(f, dict))

    return newest_version(
        v for v in list_versions(slot.versions_root, slot.name) if inputs_of(v) == shas
    )


def _local_only(slot: "FileSlot") -> "VersionedFile | None":
    """Return the local version of a position left out of the plan."""
    from kartograf.download.fetch import VersionedFile, link_version, local_version

    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)
