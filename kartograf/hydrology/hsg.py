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
from typing import TYPE_CHECKING

import numpy as np

from kartograf.exceptions import ValidationError
from kartograf.notices import Notice, NoticeSink

if TYPE_CHECKING:
    from kartograf.cache.metadata import MetadataCache
    from kartograf.core.bbox import BBox
    from kartograf.download.fetch import FileSlot, UpdateMode, VersionedFile
    from kartograf.download.plan import ItemStatus, PlanItem, Track, UpdatePlan
    from kartograf.download.versions import LocalVersion
    from kartograf.landcover.manager import LandCoverManager, LandCoverResult
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

# HSG Descriptions
HSG_DESCRIPTIONS = {
    "A": "High infiltration rate - sandy soils with low runoff potential",
    "B": "Moderate infiltration rate - loamy soils with moderate runoff",
    "C": "Slow infiltration rate - clay loam soils with high runoff",
    "D": "Very slow infiltration rate - clay soils with very high runoff",
}

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
# truth for both the scalar and the vectorised classifier.  Each predicate gets
# float64 arrays with clay/sand/silt in percent (already normalised to sum 100)
# and returns a boolean mask.  Order matters: first matching rule wins.
_USDA_RULES: tuple[
    tuple[str, Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]], ...
] = (
    ("sand", lambda c, s, si: si + 1.5 * c < 15),
    ("loamy_sand", lambda c, s, si: (si + 1.5 * c >= 15) & (si + 2 * c < 30)),
    (
        "sandy_loam",
        lambda c, s, si: (
            ((c >= 7) & (c <= 20) & (s > 52) & (si + 2 * c >= 30))
            | ((c < 7) & (si < 50) & (si + 2 * c >= 30))
        ),
    ),
    ("silt", lambda c, s, si: (si >= 80) & (c < 12)),
    (
        "silt_loam",
        lambda c, s, si: (
            ((si >= 50) & (c >= 12) & (c < 27)) | ((si >= 50) & (si < 80) & (c < 12))
        ),
    ),
    (
        "loam",
        lambda c, s, si: (c >= 7) & (c <= 27) & (si >= 28) & (si < 50) & (s <= 52),
    ),
    ("sandy_clay_loam", lambda c, s, si: (c >= 20) & (c < 35) & (si < 28) & (s > 45)),
    ("clay_loam", lambda c, s, si: (c >= 27) & (c < 40) & (s > 20) & (s <= 45)),
    ("silty_clay_loam", lambda c, s, si: (c >= 27) & (c < 40) & (s <= 20)),
    ("sandy_clay", lambda c, s, si: (c >= 35) & (s > 45)),
    ("silty_clay", lambda c, s, si: (c >= 40) & (si >= 40)),
    ("clay", lambda c, s, si: (c >= 40) & (s <= 45) & (si < 40)),
)


def _normalize_pct(
    clay, sand, silt
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Normalise clay/sand/silt to percentages summing to 100 (float64).

    Returns the three normalised arrays plus the raw total, so callers can tell
    apart real soil from the "no input at all" case (total == 0).
    """
    clay = np.asarray(clay, dtype=np.float64)
    sand = np.asarray(sand, dtype=np.float64)
    silt = np.asarray(silt, dtype=np.float64)

    total = clay + sand + silt
    valid = total > 0

    normalised = tuple(
        np.divide(part, total, out=np.zeros_like(part), where=valid) * 100
        for part in (clay, sand, silt)
    )

    return normalised[0], normalised[1], normalised[2], total


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
    `classify_usda_texture`, evaluated in float64.

    Parameters
    ----------
    clay : np.ndarray
        Clay content array in percent (0-100)
    sand : np.ndarray
        Sand content array in percent (0-100)
    silt : np.ndarray
        Silt content array in percent (0-100)

    Returns
    -------
    np.ndarray
        Array of texture class codes (1-12); cells whose inputs sum to 0
        (no data) get "loam".
    """
    clay_n, sand_n, silt_n, total = _normalize_pct(clay, sand, silt)

    masks = [rule(clay_n, sand_n, silt_n) for _, rule in _USDA_RULES]
    codes = [TEXTURE_CLASSES[name] for name, _ in _USDA_RULES]

    selected = np.select(masks, codes, default=TEXTURE_CLASSES["loam"])

    # The rules partition the whole simplex, but cells with a zero total are
    # not soil at all - pin them to "loam" explicitly instead of letting the
    # normalised zeros fall into the "sand" rule.
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

    return mapping[texture]


def _geographic_row_cell_areas(src) -> np.ndarray:
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

    Nodata comes from the RAW values (before g/kg -> %): the texture
    classifier falls back to loam for anything it cannot place. All-zero
    triplets are gaps (SoilGrids convention).
    """
    factor = HSGCalculator.CONVERSION_FACTOR
    texture = classify_usda_texture_array(clay / factor, sand / factor, silt / factor)
    hsg = texture_to_hsg_array(texture)
    mask = (
        _nodata_mask(clay, nodata[0])
        | _nodata_mask(sand, nodata[1])
        | _nodata_mask(silt, nodata[2])
    )
    mask |= (clay == 0) & (sand == 0) & (silt == 0)
    hsg[mask] = 0
    return hsg


def _write_hsg_geotiff(output_path: Path, hsg: np.ndarray, profile: dict) -> None:
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


# SoilGrids inputs of HSG, in the order of ``HsgResult.inputs``.
HSG_INPUTS = ("clay", "sand", "silt")
_HSG_CLASSES = "1=A, 2=B, 3=C, 4=D"
_HSG_TRACK: "Track" = "hsg"
# HSG always classifies the mean texture estimate (R3): the store segments
# ``soil/global_soilgrids_<prop>_<depth>_mean`` and
# ``hsg/global_soilgrids_<depth>_mean`` and the sidecar ``stat`` stay as before.
_HSG_STAT = "mean"


@dataclass(frozen=True)
class HsgResult:
    """HSG of one selection (``unit``: bbox coordinates or the sheet).

    ``file``: the HSG version (``new``/``unchanged``/``relabeled`` when
    computed, ``reused`` when a version of the same input set exists,
    ``local`` for a position left out of a plan; ``None`` only then, without
    a local version). ``inputs``: clay, sand, silt in the store. ``stale``:
    planned positions whose source changed since the plan. ``notices``: data
    messages (e.g. the geometry layer choice). ``ok``: no stale position.
    """

    unit: str
    file: "VersionedFile | None"
    inputs: "tuple[LandCoverResult, ...]"
    stale: "tuple[PlanItem, ...]" = ()
    notices: "tuple[Notice, ...]" = ()

    @property
    def ok(self) -> bool:
        """True when no planned position went stale."""
        return not self.stale


class HSGCalculator:
    """
    Hydrologic Soil Groups from SoilGrids clay/sand/silt in the version store.

    The inputs are SoilGrids ``mean`` versions of ``output_dir``
    (``soil/global_soilgrids_{clay,sand,silt}_<depth>_mean/``, labelled by
    the SoilGrids edition, D33); the HSG raster is a version of
    ``hsg/global_soilgrids_<depth>_mean/`` with the same selection
    hierarchy (``bbox/<coords>`` or the sheet hierarchy). A version whose
    ``extra.source_files`` has the same three input sha256 is used again
    (``reused``, nothing computed). Rasters outside the store:
    ``hsg_from_rasters``.

    Examples
    --------
    >>> from kartograf.hydrology import HSGCalculator
    >>> calc = HSGCalculator("./data")
    >>> result = calc.calculate_hsg(sheet="N-34-130-D", depth="0-5cm")
    >>> result.file.path, result.file.status  # hsg/.../N-34-130-D.tif, "new"
    >>> calc.get_hsg_statistics(result.file.path)
    """

    # SoilGrids conversion factors
    # Data is stored as g/kg, divide by 10 for percentage
    CONVERSION_FACTOR = 10.0

    def __init__(
        self,
        output_dir: str | Path,
        provider=None,
        cache: "MetadataCache | bool" = True,
    ):
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
                "--output to katalog magazynu (od 0.8.0); plik poza "
                "magazynem: hsg_from_rasters"
            )
        self._provider = provider
        self._cache = cache

    @property
    def provider(self):
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
        depth: str,
        update: "UpdateMode | None" = None,
        plan: "UpdatePlan | None" = None,
        timeout: int = 120,
        on_notice: "Callable[[Notice], None] | None" = None,
    ) -> HsgResult:
        """
        HSG of one selection: exactly one of ``sheet``, ``bbox``, ``geometry``.

        Parameters
        ----------
        sheet : str, optional
            Map sheet (canonical code, sheet hierarchy).
        bbox : BBox, optional
            Area in any supported CRS (``bbox/<coords>`` of its EPSG:2180
            envelope; Czech CRSs via the pinned operation).
        geometry : str or Path, optional
            SHP/GPKG file; its EPSG:2180 envelope is the area (``layer`` of a
            GPKG; default first layer with a ``GEOMETRY_LAYER_DEFAULT`` notice).
        depth : str
            Soil interval below surface: 0-5cm, 5-15cm, 15-30cm,
            30-60cm, 60-100cm, or 100-200cm. The statistic is always ``mean``.
        update : None, "upgrade" or "force", optional
            Mode of the INPUTS (spec 4.2): ``None`` uses local versions,
            ``"upgrade"`` downloads a newer SoilGrids edition, ``"force"``
            downloads again. HSG is computed only for a new input set.
        plan : UpdatePlan, optional
            From ``check_hsg``; with ``update="upgrade"`` only the planned
            positions execute.
        timeout : int, optional
            Request timeout in seconds (default: 120)
        on_notice : callable, optional
            Receives each data notice when emitted.

        Returns
        -------
        HsgResult

        Raises
        ------
        DownloadError
            An input failed (no HSG is written) or a store failure.
        ValidationError
            Not exactly one selection, bad mode, a plan of another store or
            a ``timeout`` that is not a positive number (``"120"``).
        """
        from kartograf.download.arguments import require_timeout

        require_timeout(timeout)
        sink = NoticeSink(on_notice)
        selection = self._validated(sheet, bbox, geometry, layer, depth, sink)
        result = self._calculate(
            selection, depth, _HSG_STAT, update, plan, timeout, sink
        )
        return replace(result, notices=sink.notices)

    def check_hsg(
        self,
        *,
        sheet: str | None = None,
        bbox: "BBox | None" = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        depth: str,
        timeout: int = 120,
        on_notice: "Callable[[Notice], None] | None" = None,
    ) -> "UpdatePlan":
        """Plan of ``calculate_hsg`` with the same selection, WITHOUT
        downloading or computing: 3 x ``landcover`` + 1 x ``hsg``."""
        from kartograf.download.arguments import require_timeout

        require_timeout(timeout)
        sink = NoticeSink(on_notice)
        selection = self._validated(sheet, bbox, geometry, layer, depth, sink)
        return self._check(selection, depth, _HSG_STAT, timeout, sink)

    def validate_request(
        self,
        *,
        sheet: str | None = None,
        bbox: "BBox | None" = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        depth: str,
    ) -> None:
        """Every check of ``calculate_hsg``/``check_hsg`` before the first
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
        depth: str,
        sink: NoticeSink,
    ) -> dict:
        """The selection, then the depth by the input manager's own checks."""
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
    ) -> dict:
        """HSG selection: the canonical sheet or an EPSG:2180 bbox."""
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.download.area import bbox_to_2180, geometry_envelope_2180
        from kartograf.download.options import validate_request_bbox
        from kartograf.exceptions import ValidationError

        if sum(v is not None for v in (sheet, bbox, geometry)) != 1:
            raise ValidationError(
                "Podaj dokladnie jeden wybor: sheet, bbox albo geometry"
            )
        if sheet is not None:
            return {"sheet": SheetParser(sheet).sheet}
        if geometry is not None:
            return _bbox_request(geometry_envelope_2180(geometry, layer, sink))
        assert bbox is not None
        validate_request_bbox(bbox)
        return _bbox_request(bbox_to_2180(bbox))

    # -------------------------------------------------------------------------

    def _manager(self) -> "LandCoverManager":
        from kartograf.landcover.manager import LandCoverManager

        if self._provider is None:  # by name: the manager attaches the cache
            return LandCoverManager(self._output_dir, "soilgrids", cache=self._cache)
        return LandCoverManager(self._output_dir, self._provider)

    def _slot(self, selection: dict, depth: str, stat: str) -> "FileSlot":
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
        self, selection: dict, depth: str, stat: str, timeout: int, sink: "NoticeSink"
    ) -> "UpdatePlan":
        from kartograf.download.plan import new_plan

        inputs = self._input_items(selection, depth, stat, timeout, sink)
        return new_plan(
            self._output_dir, [*inputs, self._hsg_item(selection, depth, stat, inputs)]
        )

    def _input_items(
        self, selection: dict, depth: str, stat: str, timeout: int, sink: "NoticeSink"
    ) -> list:
        manager = self._manager()
        where = _where(selection)
        return [
            item
            for prop in HSG_INPUTS
            for item in manager.check(
                **where,
                property=prop,
                depth=depth,
                stat=stat,
                timeout=timeout,
                on_notice=sink.add,
            ).items
        ]

    def _hsg_item(self, selection: dict, depth: str, stat: str, inputs: list):
        """Plan position of the HSG: ``current`` when a version of the current
        local inputs exists and every input is current; ``check_failed`` when an
        input could not be checked; otherwise ``missing`` (to compute)."""
        from kartograf.download.fetch import local_version
        from kartograf.download.plan import PlanItem
        from kartograf.landcover.store import selection_unit

        slot = self._slot(selection, depth, stat)
        labels = [i.available_label for i in inputs]
        label = "+".join(sorted(set(labels))) if all(labels) else None
        failed = [i for i in inputs if i.status == "check_failed"]
        shas = tuple(i.local_sha256 for i in inputs)
        reusable = (
            _matching_version(slot, shas) if all(shas) else None  # type: ignore[arg-type]
        )
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
        selection: dict,
        depth: str,
        stat: str,
        update: "UpdateMode | None",
        plan: "UpdatePlan | None",
        timeout: int,
        sink: "NoticeSink",
    ) -> HsgResult:
        from kartograf.download.fetch import validate_update
        from kartograf.download.plan import require_store, select_planned, store_id
        from kartograf.exceptions import ValidationError
        from kartograf.landcover.store import selection_unit

        validate_update(update)
        slot = self._slot(selection, depth, stat)
        unit = selection_unit(
            bbox=selection.get("bbox_obj"), sheet=selection.get("sheet")
        )
        planned_hsg = True
        stale: list = []
        if plan is not None:
            if update != "upgrade":
                raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
            require_store(plan, store_id(self._output_dir))
            # The HSG position is checked BEFORE the inputs change.
            fresh = self._hsg_item(
                selection,
                depth,
                stat,
                self._input_items(selection, depth, stat, timeout, sink),
            )
            todo, skipped = select_planned(plan, [fresh], _HSG_TRACK)
            planned_hsg, stale = bool(todo), list(skipped)

        from kartograf.landcover.manager import LandCoverResult

        manager = self._manager()
        where = _where(selection)
        areas = [
            manager.download(
                **where,
                update=update,
                plan=_input_plan(plan, prop, depth, stat),
                property=prop,
                depth=depth,
                stat=stat,
                timeout=timeout,
                on_notice=sink.add,
            )
            for prop in HSG_INPUTS
        ]
        # one raster per input; a plan may leave it without a file
        inputs = tuple(
            area.files[0] if area.files else LandCoverResult(unit, None)
            for area in areas
        )
        for area in areas:
            stale.extend(area.stale)
        files = [r.file for r in inputs]
        if not planned_hsg or any(f is None for f in files):
            return HsgResult(unit, _local_only(slot), inputs, tuple(stale))
        hsg = self._reuse_or_compute(
            slot, selection, depth, stat, [f for f in files if f is not None]
        )
        return HsgResult(unit, hsg, inputs, tuple(stale))

    def _reuse_or_compute(
        self,
        slot: "FileSlot",
        selection: dict,
        depth: str,
        stat: str,
        files: "list[VersionedFile]",
    ) -> "VersionedFile":
        """The HSG version of these inputs: reused, or computed and stored."""
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
            logger.info(f"HSG {slot.std}: wersja {match.label} uzyta ponownie")
            return VersionedFile(
                slot.std, "reused", match.label, match.sha256, match.path
            )

        label = "+".join(sorted({f.label for f in files}))
        staged = new_staging(slot)
        try:
            arrays, nodatas = [], []
            for f in files:
                with rasterio.open(f.version_path) as src:
                    arrays.append(src.read(1).astype(np.float32))
                    nodatas.append(src.nodata)
                    if len(arrays) == 1:  # grid of clay = grid of the result
                        profile = src.profile.copy()
            logger.info("Classifying HSG...")
            hsg = _classify_hsg(
                arrays[0], arrays[1], arrays[2], (nodatas[0], nodatas[1], nodatas[2])
            )
            _write_hsg_geotiff(staged, hsg, profile)
        except BaseException:
            discard_staging(staged, slot)
            raise
        crs = profile.get("crs")
        request = {k: v for k, v in selection.items() if k != "bbox_obj"}
        extra = {
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

        def write(data: Path, ref, dg, _http) -> None:
            emit_sidecar(
                "global.isric.soilgrids",
                data,
                request=request,
                horizontal_crs=str(crs) if crs else None,
                capability="bbox_raster",
                nodata=0,
                extra=extra,
                exclusive=True,
                digest=(dg.sha256, dg.size_bytes),
                version=ref.to_extra(),
            )

        return store_file(
            slot,
            staged,
            version=VersionRef(label, "edition"),
            write_sidecar=write,
            http=None,
            signal="metadata",
        )

    def get_hsg_statistics(self, hsg_path: Path) -> dict:
        """
        Calculate statistics for an HSG raster.

        Parameters
        ----------
        hsg_path : Path
            Path to HSG GeoTIFF

        Returns
        -------
        dict
            Per-group dict (``A``-``D``) with keys: count, area_m2, area_ha,
            percent (share of the cells WITH data), description; plus
            ``nodata`` - the cells without data (class 0: an input gap, e.g.
            a SoilGrids cell with 0 in every input) with the same keys and
            ``percent`` = share of ALL cells of the raster.

        Notes
        -----
        Areas are in square metres / hectares regardless of the raster CRS:
        for a geographic CRS (SoilGrids output is EPSG:4326) cell areas are
        computed geodetically per raster row, not from the affine
        determinant, which would give square degrees.
        """
        import rasterio

        with rasterio.open(hsg_path) as src:
            hsg = src.read(1)
            if src.crs is not None and src.crs.is_geographic:
                # transform[0]*transform[4] would be square DEGREES here
                row_area = _geographic_row_cell_areas(src)
            else:
                row_area = np.full(
                    src.height, abs(src.transform[0] * src.transform[4])
                )  # m²

        # Count pixels for each HSG; the shares are of the cells with data,
        # the cells without data (0) get their own entry (share of all cells)
        total_valid = np.sum(hsg > 0)
        stats = {}

        for name, value in HSG_VALUES.items():
            per_row = np.sum(hsg == value, axis=1)
            count = np.sum(per_row)
            area_m2 = float(np.sum(per_row * row_area))
            pct = (count / total_valid * 100) if total_valid > 0 else 0

            stats[name] = {
                "count": int(count),
                "area_m2": float(area_m2),
                "area_ha": float(area_m2 / 10000),
                "percent": float(pct),
                "description": HSG_DESCRIPTIONS[name],
            }

        empty = np.sum(hsg == 0, axis=1)
        empty_m2 = float(np.sum(empty * row_area))
        stats["nodata"] = {
            "count": int(np.sum(empty)),
            "area_m2": empty_m2,
            "area_ha": empty_m2 / 10000,
            "percent": float(np.sum(empty) / hsg.size * 100) if hsg.size else 0.0,
            "description": "Brak danych: komorki bez wartosci wejsc (klasa 0)",
        }
        return stats


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
        raise ValidationError(f"pixel_m musi byc dodatni (podano {pixel_m})")
    grid = bbox if bbox.crs == crs else transform_bbox(bbox, crs)
    layers = {"clay": Path(clay), "sand": Path(sand), "silt": Path(silt)}
    arrays: dict[str, np.ndarray] = {}
    nodatas: dict[str, float | None] = {}
    profile: dict = {}
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
                arrays[name] = w.read(1).astype(np.float32)
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
        "global.isric.soilgrids",
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
    )


def _bbox_request(bbox: "BBox") -> dict:
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
    """The plan positions of one input (its segment): the other inputs are
    separate requests of the manager, not files that left the selection."""
    if plan is None:
        return None
    from dataclasses import replace

    from kartograf.download.storage import content_segment

    segment = content_segment("global.isric.soilgrids", (prop, depth, stat))
    return replace(plan, items=tuple(i for i in plan.items if i.segment == segment))


def _where(selection: dict) -> dict:
    """``LandCoverManager`` selection keyword of an HSG selection."""
    if "sheet" in selection:
        return {"sheet": selection["sheet"]}
    return {"bbox": selection["bbox_obj"]}


def _matching_version(slot: "FileSlot", shas: tuple[str, ...]) -> "LocalVersion | None":
    """The newest HSG version computed from inputs with exactly these sha256."""
    from kartograf.download.versions import list_versions, newest_version

    def inputs_of(version) -> tuple[str, ...]:
        extra = version.meta.get("extra") or {}
        files = extra.get("source_files") or []
        return tuple(str(f.get("sha256")) for f in files if isinstance(f, dict))

    return newest_version(
        v for v in list_versions(slot.versions_root, slot.name) if inputs_of(v) == shas
    )


def _local_only(slot: "FileSlot") -> "VersionedFile | None":
    """A position left out of the plan: its local version, nothing computed."""
    from kartograf.download.fetch import VersionedFile, link_version, local_version

    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)
