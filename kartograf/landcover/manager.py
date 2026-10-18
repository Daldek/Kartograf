"""
Land cover and SoilGrids downloads on the versioned store (spec 3.4,
D29-D32, ADR-044).

``download_landcover``/``check_landcover`` (``landcover download``) and
``download_soil``/``check_soil`` (``soil download``) are the command-level
functions (ADR-037 S3, ADR-044 D5): keyword-only arguments named as the CLI
flags, a report in the shape of ``CollectionReport`` (``LandCoverReport``,
``SoilReport``: ``UnitFile``/``UnitFailure``). A file that fails lands in
``failed`` and the other units still run (ADR-044 D6);
``validate_landcover_request``/``validate_soil_request`` run every check of
the download without network (``project add``).

``LandCoverManager`` is the layer below them (outside the public API): it
downloads BDOT10k, BDOO, CORINE, SoilGrids, ZABAGED, Data50 and Data250 into
the ``data/`` layout of its output directory (the store root, as
``--output``): every file is an immutable version with a hardlink at the
standard path. SoilGrids and CORINE (CLMS) versions are labelled by the
source edition (signal ``metadata``), the CORINE WMS preview and BDOT10k by
the download date (signal ``none``), the BDOT10k yearly archive (``year``)
and BDOO by their year (ADR-042 D11, ADR-043), the national files of
ZABAGED, Data50 and Data250 by the edition of their ATOM feed. Files outside
the store: ``provider.download_by_*``. BDOT10k by an area covers every
powiat of it (in parallel with ``workers``), BDOO every voivodeship of it.
The BDOT10k archive runs on the unit jobs of the collection orchestrator
(``download.collections``), the sources without a provider class (ZABAGED,
BDOO, Data50, Data250) on its requests - both on the plan track
``landcover``.
"""

import concurrent.futures
import logging
import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import bbox_coords
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.area import bbox_to_2180, geometry_envelope_2180
from kartograf.download.arguments import require_bool, require_codes, require_int
from kartograf.download.collections import (
    CollectionRequest,
    UnitJob,
    collection_classes,
    collection_layers,
    inspect_job,
    landcover_request,
    package_job,
    plan_request,
    run_job,
    run_request,
    selection_choices,
)
from kartograf.download.data import FailureKind, UnitFailure, UnitFile
from kartograf.download.fetch import (
    EditionLookup,
    FileSlot,
    UpdateMode,
    VersionedFile,
    discard_staging,
    emit_file_notices,
    inspect_version,
    link_version,
    local_version,
    memoized_edition,
    new_staging,
    refreshes_cache,
    store_file,
    use_local,
    validate_update,
)
from kartograf.download.manager import DownloadProgress
from kartograf.download.options import (
    canonical_crs,
    canonical_format,
    check_layer,
    output_required,
    validate_request_bbox,
)
from kartograf.download.plan import (
    PlanItem,
    Track,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import content_segment, unit_slot
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.landcover.store import selection_unit
from kartograf.notices import CORINE_PREVIEW, Notice, NoticeSink
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider, normalize_layers
from kartograf.providers.soilgrids import (
    DEPTH_DESCRIPTION,
    PROPERTY_DESCRIPTIONS,
    STAT_DESCRIPTIONS,
    SoilGridsProvider,
)
from kartograf.sources.descriptor import (
    AccessChannel,
    PackageVariant,
    SignalKind,
    TransportKind,
    UnitPackageParams,
)
from kartograf.sources.registry import channel_signal, get_source, sources_for
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.unit_package import select_variant

logger = logging.getLogger(__name__)


# Registry of available providers
PROVIDERS = {
    "bdot10k": Bdot10kProvider,
    "corine": CorineProvider,
    "soilgrids": SoilGridsProvider,
}
# Sources on the collection engines (ADR-042 D10, D15; ADR-043): name ->
# descriptor; no provider class - ``download``/``check`` go to
# ``download.collections``.
COLLECTION_SOURCES: dict[str, str] = {
    "zabaged": "cz.cuzk.zabaged",
    "bdoo": "pl.gugik.bdoo",
    "data50": "cz.cuzk.data50",
    "data250": "cz.cuzk.data250",
}
# Products of ``landcover download`` (ADR-039, ADR-044; SoilGrids is ``soil
# download``): the descriptors of the registry stored under ``landcover/``, in
# registry order, named by their ``product`` (= ``--product`` and the sidecar
# ``product``: ``bdot10k``), and their description in messages and --help texts.
_LANDCOVER = {
    d.product: d
    for d in sources_for()
    if d.storage_subdir.split("/", 1)[0] == "landcover"
}
LANDCOVER_PRODUCTS: tuple[str, ...] = tuple(_LANDCOVER)
LANDCOVER_PRODUCT_CHOICES = ", ".join(
    f"{name} ({d.name}, {d.country})" for name, d in _LANDCOVER.items()
)
# How messages name the products with TERYT units (``teryt``).
_TERYT_PRODUCTS = "--product bdot10k (powiat, 4 cyfry) albo bdoo (wojewodztwo, 2 cyfry)"
# The area selections of a product without TERYT units (CORINE, SoilGrids).
_AREA_CHOICES = "--sheet, --bbox albo --geometry"

# Options belonging to a different product are input errors; options not
# belonging to any product are programming errors (e.g. removed output_path).
# BDOT10k ``year`` = the yearly archive (ADR-042 D11), BDOO ``year`` = its
# release (required), CORINE ``year`` = the CORINE edition; BDOO ``layers`` =
# the classes kept from each package; ``whole_country`` = the national file
# of the ATOM feed of ZABAGED, Data50 or Data250 in the CRS
# ``horizontal_crs``.
_PRODUCT_OPTIONS: dict[str, frozenset[str]] = {
    "bdot10k": frozenset({"format", "layers", "keep_raw", "year"}),
    "bdoo": frozenset({"year", "layers"}),
    "corine": frozenset({"year"}),
    "soilgrids": frozenset({"property", "depth", "stat"}),
    "zabaged": frozenset({"whole_country", "horizontal_crs"}),
    "data50": frozenset({"whole_country", "horizontal_crs"}),
    "data250": frozenset({"whole_country", "horizontal_crs"}),
}
_OPTIONS: dict[type, frozenset[str]] = {
    Bdot10kProvider: _PRODUCT_OPTIONS["bdot10k"],
    CorineProvider: _PRODUCT_OPTIONS["corine"],
    SoilGridsProvider: _PRODUCT_OPTIONS["soilgrids"],
}
_KNOWN_OPTIONS = frozenset().union(*_PRODUCT_OPTIONS.values())
_REQUIRED: dict[type, tuple[str, ...]] = {
    Bdot10kProvider: (),
    CorineProvider: ("year",),
    SoilGridsProvider: ("property", "depth", "stat"),
}
_REQUIRED_MESSAGES = {
    "year": "--year wymagane dla corine: 2018, 2012, 2006, 2000 "
    "(edycje pokrycia terenu CLMS/WMS), 1990 (tylko podglad WMS)",
    "property": "--property wymagane: bdod (gestosc objetosciowa), "
    "cec (pojemnosc sorpcyjna), cfvo (frakcja szkieletowa), clay (il), "
    "nitrogen (azot), ocd (gestosc wegla organicznego), "
    "ocs (zasob wegla organicznego), phh2o (pH), sand (piasek), "
    "silt (pyl), soc (wegiel organiczny)",
    "depth": "--depth wymagane: 0-5cm, 5-15cm, 15-30cm, "
    "30-60cm, 60-100cm, 100-200cm "
    "(przedzial glebokosci ponizej powierzchni)",
    "stat": "--stat wymagane: mean (srednia), "
    "Q0.05 (5. percentyl), Q0.5 (mediana), "
    "Q0.95 (95. percentyl), uncertainty (niepewnosc predykcji)",
}
_PREVIEW_NOTE = {"fallback": "wms_png", "note": "podglad WMS, nie dane"}
_TRACK: Track = "landcover"
# Plan position key of a slot (segment, hierarchy, name).
_SlotKey = tuple[str, str, str]


def require_landcover_product(product: object) -> str:
    """``product`` of ``landcover download``: one of ``LANDCOVER_PRODUCTS``.

    Raises
    ------
    ValidationError
        Missing product or a product of another command (SoilGrids).
    """
    if product is None:
        raise ValidationError(f"--product wymagane: {LANDCOVER_PRODUCT_CHOICES}")
    if not isinstance(product, str) or product not in LANDCOVER_PRODUCTS:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: "
            f"{LANDCOVER_PRODUCT_CHOICES}"
        )
    return product


def _archive_channel(key: str) -> AccessChannel:
    """The unit package channel of ``key``: the powiat packages of the
    BDOT10k yearly archive (ADR-042 D11), the voivodeship packages of BDOO."""
    return next(
        channel
        for channel in get_source(key).channels
        if isinstance(channel.params, UnitPackageParams)
    )


def _spans(years: Iterable[int]) -> str:
    """``2014-2025`` / ``2014-2016, 2018``: sorted years as runs."""
    runs: list[list[int]] = []
    for year in sorted(years):
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return ", ".join(f"{r[0]}-{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs)


def bdot10k_archive_choices() -> str:
    """``2014-2025 (--format GML albo SHP)``: the yearly releases of the
    BDOT10k archive from the registry (``--help`` and messages)."""
    params = _archive_channel("pl.gugik.bdot10k").params
    assert isinstance(params, UnitPackageParams)
    choices = [dict(variant.choice) for variant in params.variants]
    formats = " albo ".join(dict.fromkeys(choice["format"] for choice in choices))
    years = _spans({int(choice["year"]) for choice in choices})
    return f"{years} (--format {formats})"


def bdoo_year_choices() -> str:
    """``2015, 2021-2026``: the releases of BDOO from the registry (``--help``)."""
    params = _archive_channel(COLLECTION_SOURCES["bdoo"]).params
    assert isinstance(params, UnitPackageParams)
    return _spans({int(dict(variant.choice)["year"]) for variant in params.variants})


def corine_year_choices() -> str:
    """``2018, 2012, 2006, 2000, 1990``: the CORINE releases (``--year``;
    ``--help`` and ``list-sources``)."""
    return ", ".join(str(year) for year in CorineProvider.AVAILABLE_YEARS)


def soil_choices() -> dict[str, dict[str, str]]:
    """The ``property``, ``depth`` and ``stat`` values of ``download_soil``
    with their descriptions for the user (``--help``, ``soil list-layers``)."""
    return {
        "property": dict(PROPERTY_DESCRIPTIONS),
        "depth": {depth: DEPTH_DESCRIPTION for depth in SoilGridsProvider.DEPTHS},
        "stat": dict(STAT_DESCRIPTIONS),
    }


def _read_geotiff_nodata(path: Path) -> float | None:
    """NoData declared by a GeoTIFF result; None for other files or when unreadable.

    The sidecar describes the FILE: a raster without a declared NoData gets
    ``nodata: null`` (nothing is guessed from the source documentation).
    """
    if path.suffix.lower() not in {".tif", ".tiff"}:
        return None
    import rasterio  # lazy: BDOT10k/PNG results do not need GDAL
    from rasterio.errors import RasterioError

    try:
        with rasterio.open(path) as dataset:
            nodata = dataset.nodata
    except (OSError, ValueError, RasterioError):
        return None
    return float(nodata) if nodata is not None else None


@dataclass(frozen=True)
class LandCoverReport:
    """Outcome of ``download_landcover`` (``landcover download``).

    ``files``: one ``UnitFile`` per data file (``unit`` = TERYT, bbox
    coordinates, the sheet or the country code of a national file;
    ``country`` = ``PL``, ``CZ`` or ``EU``), in unit order (TERYT order of an
    area); ``raw``: the original BDOT10k packages kept by ``keep_raw`` (the
    same units); ``failed``: units that failed (``kind`` ``no_coverage`` - no
    data of the unit at the source - or ``download``), the other units still
    ran; ``stale``: planned positions changed since the plan; ``notices``;
    ``ok`` = no failure and no stale position. A unit left out of a plan
    without a local version has no file.
    """

    files: tuple[UnitFile, ...]
    raw: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    notices: tuple[Notice, ...]
    ok: bool


@dataclass(frozen=True)
class SoilReport:
    """Outcome of ``download_soil`` (``soil download``).

    ``files``: the SoilGrids raster of the area (one ``UnitFile``, ``unit`` =
    bbox coordinates or the sheet, ``country`` = ``GLOBAL``; none when it
    failed or a plan left it out without a local version); ``failed``,
    ``stale``, ``notices`` and ``ok`` as in ``LandCoverReport``.
    """

    files: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    notices: tuple[Notice, ...]
    ok: bool


@dataclass(frozen=True)
class _UnitResult:
    """The files of one unit: the data file and the original BDOT10k ZIP of
    ``keep_raw`` (``None``: out of the plan without a local version)."""

    unit: str
    file: VersionedFile | None
    raw: VersionedFile | None = None


def _failure(unit: str, country: str, error: DownloadError) -> UnitFailure:
    """A unit whose file failed (``no_coverage``: no data at the source)."""
    kind: FailureKind = (
        "no_coverage" if isinstance(error, NoCoverageError) else "download"
    )
    return UnitFailure(unit, country, str(error), kind)


def _landcover_report(
    files: Sequence[UnitFile],
    raw: Sequence[UnitFile],
    failed: Sequence[UnitFailure],
    stale: Sequence[PlanItem],
    sink: NoticeSink,
) -> LandCoverReport:
    """The report of one request: ``ok`` = no failure and no stale position."""
    return LandCoverReport(
        files=tuple(files),
        raw=tuple(raw),
        failed=tuple(failed),
        stale=tuple(stale),
        notices=sink.notices,
        ok=not failed and not stale,
    )


@dataclass(frozen=True)
class _Job:
    """One file of a request: slot, selection, signal and its version label.

    ``selection`` is the sidecar ``request`` of the file without content
    parameters (``teryt``, ``bbox``/``bbox_crs`` or ``sheet``); ``bbox`` /
    ``sheet`` the raster download selection.
    """

    slot: FileSlot
    unit: str
    signal: SignalKind
    selection: dict
    edition: EditionLookup | None = None  # signal "metadata"
    bbox: BBox | None = None
    sheet: str | None = None

    @property
    def key(self) -> _SlotKey:
        return (self.slot.segment, self.slot.hierarchy, self.slot.name)

    def version(self) -> VersionRef:
        """Label of a new version: the edition or the download date."""
        if self.edition is not None:
            return VersionRef(self.edition().id, "edition")
        return VersionRef.downloaded()


def _canonical_options(options: dict) -> None:
    """``format`` and ``horizontal_crs`` in any case: the registry spelling
    (``shp`` = ``SHP``, ``epsg:5514`` = ``EPSG:5514``; UX-11)."""
    if "format" in options:
        options["format"] = canonical_format(options["format"])
    if "horizontal_crs" in options:
        options["horizontal_crs"] = canonical_crs(options["horizontal_crs"])


_PowiatOutcome = _UnitResult | UnitFailure


def _each_powiat(
    teryts: Sequence[str],
    one: Callable[[str, Callable[[], None] | None], _PowiatOutcome],
    workers: int,
    on_progress: Callable[[DownloadProgress], None] | None,
) -> list[_PowiatOutcome]:
    """Run ``one`` for each powiat of a BDOT10k request, results in TERYT
    order (``workers`` in parallel), with progress as for a sheet list
    (``DownloadManager.download_sheets``).

    ``one(teryt, started)`` calls ``started`` right before a transfer
    (sequential mode: ``downloading``; ``None`` in a pool). After each
    powiat, in completion order: ``completed``, ``skipped`` (no transfer:
    local version or out of the plan), ``no_coverage`` (no package at the
    source) or ``failed``, as the units of ``download_collection``.
    """
    total = len(teryts)

    def emit(current: int, teryt: str, status: str) -> None:
        if on_progress is not None:
            on_progress(DownloadProgress(current, total, teryt, status))

    def status(outcome: _PowiatOutcome) -> str:
        if isinstance(outcome, UnitFailure):
            return "no_coverage" if outcome.kind == "no_coverage" else "failed"
        file = outcome.file
        return "skipped" if file is None or file.status == "local" else "completed"

    if workers <= 1 or total <= 1:
        outcomes = []
        for i, teryt in enumerate(teryts, 1):

            def started(i: int = i, teryt: str = teryt) -> None:
                emit(i, teryt, "downloading")

            outcome = one(teryt, started)
            outcomes.append(outcome)
            emit(i, teryt, status(outcome))
        return outcomes
    done: dict[str, _PowiatOutcome] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, teryt, None): teryt for teryt in teryts}
        for future in concurrent.futures.as_completed(futures):
            teryt = futures[future]
            done[teryt] = future.result()
            emit(len(done), teryt, status(done[teryt]))
    return [done[teryt] for teryt in teryts]


# Providers created by name that accept a metadata cache (CORINE has none).
_CACHED_PROVIDERS = ("bdot10k", "soilgrids")


class LandCoverManager:
    """
    Land cover and SoilGrids downloads into the version store (the layer
    below ``download_landcover``/``download_soil``; not in the public API).

    Every file lands in a segment of ``output_dir`` that carries its
    content parameters (spec 3.4): ``landcover/pl_bdot10k_gpkg[_<layers>]``,
    ``landcover/pl_bdot10k_shp``, ``landcover/pl_bdot10k_gpkg_zip``
    (``keep_raw``), ``landcover/pl_bdot10k_<gml|shp>_<year>`` (the yearly
    archive, ADR-042 D11), ``landcover/pl_bdoo_<year>[_<classes>]``,
    ``landcover/eu_corine_<year>[_preview]``,
    ``landcover/cz_<zabaged|data50|data250>`` (an area) and
    ``landcover/cz_<source>_<gpkg|shp>_<epsg>`` (a national file),
    ``soil/global_soilgrids_<property>_<depth>_<stat>``; below it
    ``teryt/<TERYT>``, ``bbox/<coords>``, ``country/cz`` or the sheet
    hierarchy. ``update``
    selects the mode (spec 4.2): ``None`` uses local versions and only
    reports newer content, ``"upgrade"`` downloads newer content, ``"force"``
    downloads again (same content = ``unchanged``). Checking without a
    download: ``check`` with the same selection (plan ``kartograf-plan/1``,
    track ``landcover``), executed with ``update="upgrade", plan=...``.
    The catalogue of a source (``get_available_layers``,
    ``get_supported_formats``) needs no network.

    Parameters
    ----------
    output_dir : str or Path
        Store root (``--output``); created only when a file is written.
    provider : LandCoverProvider or str
        Provider instance or name: "bdot10k" (Polish topographic vectors),
        "corine" (European land cover raster), "soilgrids" (soil rasters),
        or a source on the collection engines: "bdoo" (Polish general
        geographic database), "zabaged", "data50", "data250" (CZ).
    cache : MetadataCache or bool
        Metadata cache of a provider created BY NAME (BDOT10k: PRG TERYT
        answers; SoilGrids; CORINE has none): ``True`` = default cache in the
        current directory, a ``MetadataCache`` = that cache, ``False`` = none.
        A provider instance keeps its own cache: ``update="force"`` skips
        reads only of the cache opened here, so an instance's cache is not
        refreshed (build it with ``MetadataCache(path, refresh=True)``).
    """

    def __init__(
        self,
        output_dir: str | Path,
        provider: LandCoverProvider | str,
        cache: MetadataCache | bool = True,
    ):
        """
        Initialize LandCoverManager.

        Parameters
        ----------
        output_dir : str or Path
            Store root. It is not created here: the directory appears only
            when a download writes its first file.
        provider : LandCoverProvider or str
            Provider instance or name: "bdot10k" (topographic vectors),
            "corine" (land cover raster), "soilgrids" (soil rasters) or a
            source on the collection engines without a provider class:
            "bdoo" (PL general geographic database), "zabaged", "data50",
            "data250" (CZ).
        cache : MetadataCache or bool
            Cache for providers created by name (see the class docstring);
            opened per ``download``/``check`` call.
        """
        self._output_dir = Path(output_dir)
        self._cache = cache
        self._provider: LandCoverProvider
        self._provider_name: str | None = None
        self._collection: str | None = None
        self.set_provider(provider)

    @staticmethod
    def _get_provider_by_name(
        name: str, cache: MetadataCache | None = None
    ) -> LandCoverProvider:
        """
        Provider instance by name ("bdot10k", "corine", "soilgrids").

        Raises
        ------
        ValidationError
            If provider name is unknown
        """
        name_lower = name.lower()
        if name_lower not in PROVIDERS:
            raise ValidationError(
                f"Nieznane zrodlo: {name}. Dostepne: "
                f"{[*PROVIDERS, *COLLECTION_SOURCES]}"
            )
        if name_lower == "bdot10k":
            return Bdot10kProvider(cache=cache)
        if name_lower == "soilgrids":
            return SoilGridsProvider(cache=cache)
        return PROVIDERS[name_lower]()

    @property
    def output_dir(self) -> Path:
        """Store root."""
        return self._output_dir

    @property
    def provider(self) -> LandCoverProvider:
        """Return current provider.

        Raises
        ------
        ValidationError
            A source on the collection engines (``zabaged``) has no provider.
        """
        if self._collection is not None:
            raise ValidationError(
                f"{self._provider_name}: zrodlo bez providera (silniki kolekcji) - "
                "pobranie: download(), warstwy: get_available_layers()"
            )
        return self._provider

    @property
    def provider_name(self) -> str:
        """Return current provider name (the dataset name of a collection source)."""
        if self._collection is not None:
            return get_source(self._collection).name
        return self._provider.name

    def set_provider(self, provider: LandCoverProvider | str) -> None:
        """
        Set the active provider.

        Parameters
        ----------
        provider : LandCoverProvider or str
            Provider instance or name ("bdot10k", "corine", "soilgrids") or a
            source on the collection engines ("bdoo", "zabaged", "data50",
            "data250")
        """
        if isinstance(provider, str) and provider.lower() in COLLECTION_SOURCES:
            self._collection = COLLECTION_SOURCES[provider.lower()]
            self._provider_name = provider.lower()
            logger.info(f"Provider set to: {self._collection}")
            return
        self._collection = None
        if isinstance(provider, str):
            cache = self._cache if isinstance(self._cache, MetadataCache) else None
            self._provider = self._get_provider_by_name(provider, cache)
            self._provider_name = provider.lower()
        else:
            self._provider = provider
            self._provider_name = None
        logger.info(f"Provider set to: {self._provider.name}")

    @contextmanager
    def _session(self, *, force: bool, sink: NoticeSink) -> Iterator[None]:
        """One call: a provider created by name uses the call's metadata cache.

        The provider instance stays the same (its cache is attached for the
        call only); a provider instance passed by the caller keeps its cache.
        """
        if self._provider_name not in _CACHED_PROVIDERS:
            yield
            return
        provider = self._provider
        with open_cache(self._cache, force=force, on_notice=sink.add) as metadata:
            previous = provider._cache  # type: ignore[attr-defined]
            provider._cache = metadata  # type: ignore[attr-defined]
            try:
                yield
            finally:
                provider._cache = previous  # type: ignore[attr-defined]

    # =========================================================================
    # Download / check (command level)
    # =========================================================================

    def download(
        self,
        *,
        teryt: str | None = None,
        sheet: str | None = None,
        bbox: BBox | None = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        workers: int = 1,
        on_notice: Callable[[Notice], None] | None = None,
        on_progress: Callable[[DownloadProgress], None] | None = None,
        **options,
    ) -> LandCoverReport:
        """
        Download the files of one request into the store.

        Exactly one of ``teryt``, ``sheet``, ``bbox``, ``geometry`` (the
        collection sources also ``whole_country``); ``options`` are the
        content choices of the source given (``None`` and ``False`` values
        left out): see ``download_landcover`` and ``download_soil``.
        BDOT10k by an area: the package of EVERY powiat intersecting it
        (PRG), one file ``teryt/<T>`` each, in TERYT order, with
        ``extra.parent_request`` (``workers`` in parallel); BDOO by an area:
        the package of every voivodeship of it. A file that fails lands in
        ``failed`` (``UnitFailure`` of its unit), the other units still run.
        ``on_progress``: one ``DownloadProgress`` per unit of an area of
        BDOT10k powiats or BDOO voivodeships (``sheet`` = TERYT) -
        ``downloading`` right before its transfer (``workers=1`` only), then
        ``completed``, ``skipped``, ``no_coverage`` or ``failed`` in
        completion order.

        Raises
        ------
        ValidationError
            Not exactly one selection, invalid source options, an option of
            a wrong type (``year="2018"``, ``layers="SWRS,PTWP"``; never
            converted), a plan of another store or without
            ``update="upgrade"``, an area over the volume limits of the
            collection engines.
        TypeError
            An option that belongs to no source (e.g. ``timeout``).
        NoCoverageError
            A BDOT10k or BDOO area intersecting no powiat.
        DownloadError
            The PRG powiat query of an area failed.
        """
        sink = NoticeSink(on_notice)
        validate_update(
            update,
            check=(
                "check_soil"
                if self._collection is None
                and isinstance(self._provider, SoilGridsProvider)
                else "check_landcover"
            ),
        )
        require_int(workers, "--workers")
        _canonical_options(options)
        if self._collection is not None:
            request = self._collection_request(
                teryt, sheet, bbox, geometry, layer, options, sink
            )
            unit_files, unit_failures, stale = run_request(
                request,
                update=update,
                plan=plan,
                workers=workers,
                cache=self._cache,
                sink=sink,
                track=_TRACK,
                on_progress=on_progress,
            )
            return _landcover_report(unit_files, (), unit_failures, stale, sink)
        teryt, sheet, bbox = self._validated(
            teryt, sheet, bbox, geometry, layer, options, sink
        )
        with self._session(force=refreshes_cache(update), sink=sink):
            if self._archive(options):
                outcomes, stale = self._download_archive(
                    teryt,
                    bbox,
                    sheet,
                    options,
                    update,
                    plan,
                    workers,
                    sink,
                    on_progress,
                )
            elif teryt is None and isinstance(self._provider, Bdot10kProvider):
                outcomes, stale = self._download_counties(
                    bbox, sheet, options, update, plan, workers, on_progress
                )
            else:
                if teryt is not None:
                    jobs, parent = self._jobs(teryt=teryt, kwargs=options), None
                else:
                    jobs, parent = self._area_jobs(
                        bbox=bbox, sheet=sheet, kwargs=options
                    )
                planned, stale = self._planned(
                    lambda: [self._inspect(job) for job in jobs], update, plan
                )
                self._corine_preview(options, sink)
                outcomes = [
                    self._unit(
                        jobs[0].unit,
                        lambda: self._run(
                            jobs, options, update, planned, parent=parent
                        ),
                    )
                ]
        return self._report(outcomes, stale, update, sink)

    def _report(
        self,
        outcomes: Sequence[_PowiatOutcome],
        stale: Sequence[PlanItem],
        update: UpdateMode | None,
        sink: NoticeSink,
    ) -> LandCoverReport:
        """The report of the units of a request in their order: the data
        files, the raw ZIPs of ``keep_raw`` and the failures, with the signal
        notices of each file."""
        country = self._country()
        files: list[UnitFile] = []
        raw: list[UnitFile] = []
        failed: list[UnitFailure] = []
        for outcome in outcomes:
            if isinstance(outcome, UnitFailure):
                failed.append(outcome)
                continue
            for file, found in ((outcome.file, files), (outcome.raw, raw)):
                if file is not None:
                    self._emit_file_notices(file, update, sink)
                    found.append(UnitFile(outcome.unit, country, file))
        return _landcover_report(files, raw, failed, stale, sink)

    def check(
        self,
        *,
        teryt: str | None = None,
        sheet: str | None = None,
        bbox: BBox | None = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        on_notice: Callable[[Notice], None] | None = None,
        **options,
    ) -> UpdatePlan:
        """Plan of ``download`` with the same selection WITHOUT downloading data.

        SoilGrids and CORINE (CLMS) compare the local version with the
        source edition (GetCapabilities / CLMS catalogue), the national files
        of ZABAGED, Data50 and Data250 with the edition of their ATOM feed;
        BDOT10k (also the archive of ``year``), BDOO, the CORINE preview and
        the areas of ZABAGED, Data50 and Data250 have no cheap signal
        (``unverifiable``/``missing``). BDOT10k and BDOO by an area ask PRG
        for its units (every powiat or voivodeship is a position).
        ``keep_raw`` adds the raw ZIP position of the same unit. The source
        is always asked: the metadata cache opened here is refreshed, never
        read (an instance ``MetadataCache`` too: its file, refreshing).
        """
        sink = NoticeSink(on_notice)
        _canonical_options(options)
        if self._collection is not None:
            request = self._collection_request(
                teryt, sheet, bbox, geometry, layer, options, sink
            )
            plan = plan_request(request, cache=self._cache, sink=sink, track=_TRACK)
            return replace(plan, notices=sink.notices)
        teryt, sheet, bbox = self._validated(
            teryt, sheet, bbox, geometry, layer, options, sink
        )
        with self._session(force=True, sink=sink):
            if self._archive(options):
                teryts = (
                    [teryt] if teryt is not None else self._area_teryts(bbox, sheet)[0]
                )
                archive = self._archive_jobs(teryts, options, parent=None)
                plan = new_plan(
                    self._output_dir, [self._inspect_archive(job) for job in archive]
                )
                return replace(plan, notices=sink.notices)
            if teryt is not None:
                jobs = self._jobs(teryt=teryt, kwargs=options)
            elif isinstance(self._provider, Bdot10kProvider):
                teryts, _ = self._area_teryts(bbox, sheet)
                jobs = [j for t in teryts for j in self._jobs(teryt=t, kwargs=options)]
            else:
                jobs, _ = self._area_jobs(bbox=bbox, sheet=sheet, kwargs=options)
            plan = new_plan(self._output_dir, [self._inspect(job) for job in jobs])
            return replace(plan, notices=sink.notices)

    def validate_request(
        self,
        *,
        teryt: str | None = None,
        sheet: str | None = None,
        bbox: BBox | None = None,
        geometry: str | Path | None = None,
        layer: str | None = None,
        **options,
    ) -> None:
        """Every check of ``download``/``check`` before the first request.

        No network and nothing written (a ``geometry`` file is read for its
        envelope): the same exception type and text as ``download`` with the
        same selection and options (``project add``, ADR-040).

        Raises
        ------
        ValidationError
            Not exactly one selection, invalid TERYT or sheet code, invalid
            or missing source options.
        TypeError
            An option that belongs to no source.
        """
        _canonical_options(options)
        if self._collection is not None:
            self._collection_request(
                teryt, sheet, bbox, geometry, layer, options, NoticeSink(None)
            )
            return
        self._validated(teryt, sheet, bbox, geometry, layer, options, NoticeSink(None))

    def _validated(
        self,
        teryt: str | None,
        sheet: str | None,
        bbox: BBox | None,
        geometry: str | Path | None,
        layer: str | None,
        options: dict,
        sink: NoticeSink,
    ) -> tuple[str | None, str | None, BBox | None]:
        """The prologue of ``download``/``check``: options, then the selection."""
        if bbox is not None:  # the CLI parses --bbox first: the same first error
            bbox = validate_request_bbox(bbox)
        self._check_options(options)
        return self._selection(teryt, sheet, bbox, geometry, layer, sink)

    def _collection_request(
        self,
        teryt: str | None,
        sheet: str | None,
        bbox: BBox | None,
        geometry: str | Path | None,
        layer: str | None,
        options: dict,
        sink: NoticeSink,
    ) -> CollectionRequest:
        """The prologue of a collection source (ZABAGED, BDOO, Data50,
        Data250): bbox, options, the selection - the rules of
        ``download.collections`` (no network)."""
        if bbox is not None:  # the CLI parses --bbox first: the same first error
            bbox = validate_request_bbox(bbox)
        source = self._provider_name
        assert source is not None and self._collection is not None
        allowed = _PRODUCT_OPTIONS[source]
        unknown = sorted(set(options) - _KNOWN_OPTIONS)
        if unknown:
            raise TypeError(
                f"{source}: nieznane opcje {unknown} (dozwolone: {sorted(allowed)})"
            )
        for name, value in options.items():
            if name not in allowed and value is not None:
                if name in ("keep_raw", "whole_country") and not value:
                    continue
                owners = [s for s, names in _PRODUCT_OPTIONS.items() if name in names]
                raise ValidationError(
                    f"--{name.replace('_', '-')} dziala tylko z --product "
                    f"{' albo '.join(owners)}"
                )
        # library calls only: the CLI parses its flags (STANDARDS 11.2)
        if options.get("year") is not None:
            require_int(options["year"], "--year")
        if options.get("layers") is not None:
            require_codes(options["layers"], "--layers", "['ADJA', 'PTWP']")
        whole_country = options.get("whole_country", False)
        horizontal_crs = options.get("horizontal_crs")
        if horizontal_crs is not None and not isinstance(horizontal_crs, str):
            raise ValidationError(
                f"--horizontal-crs: oczekiwano napisu (np. 'EPSG:5514'), podano "
                f"{horizontal_crs!r}"
            )
        if teryt is not None and get_source(self._collection).country != "PL":
            raise ValidationError(
                f"--teryt dziala tylko z {_TERYT_PRODUCTS}; --product {source}: "
                "podaj --bbox, --geometry albo --whole-country"
            )
        return landcover_request(
            self._collection,
            output_dir=self._output_dir,
            teryt=teryt,
            sheet=sheet,
            bbox=bbox,
            geometry=geometry,
            layer=layer,
            whole_country=whole_country,
            year=options.get("year"),
            layers=options.get("layers"),
            horizontal_crs=horizontal_crs,
            sink=sink,
        )

    def _unit(
        self, unit: str, run: Callable[[], _UnitResult]
    ) -> _UnitResult | UnitFailure:
        """The files of one unit (``run``); a ``DownloadError`` of its file
        (download, edition, store) is a failure of the unit, not of the
        request: the other units still run."""
        try:
            return run()
        except DownloadError as e:
            logger.debug("%s %s: %s", self.provider_name, unit, e)
            return _failure(unit, self._country(), e)

    def _country(self) -> str:
        """Country code of the files of the provider's source
        (``UnitFile.country``: ``PL``, ``EU``, ``GLOBAL``)."""
        return get_source(self._descriptor_key()).country

    def _download_counties(
        self,
        bbox: BBox | None,
        sheet: str | None,
        options: dict,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int,
        on_progress: Callable[[DownloadProgress], None] | None,
    ) -> tuple[list[_PowiatOutcome], tuple[PlanItem, ...]]:
        """BDOT10k packages of EVERY powiat of an area (PRG), TERYT order."""
        teryts, parent = self._area_teryts(bbox, sheet)
        jobs = {t: self._jobs(teryt=t, kwargs=options) for t in teryts}
        planned, stale = self._planned(
            lambda: [self._inspect(job) for group in jobs.values() for job in group],
            update,
            plan,
        )

        def one(teryt: str, started: Callable[[], None] | None) -> _PowiatOutcome:
            return self._unit(
                teryt,
                lambda: self._run(
                    jobs[teryt],
                    options,
                    update,
                    planned,
                    parent=parent,
                    on_download=started,
                ),
            )

        return _each_powiat(teryts, one, workers, on_progress), stale

    def _download_archive(
        self,
        teryt: str | None,
        bbox: BBox | None,
        sheet: str | None,
        options: dict,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int,
        sink: NoticeSink,
        on_progress: Callable[[DownloadProgress], None] | None,
    ) -> tuple[list[_PowiatOutcome], tuple[PlanItem, ...]]:
        """BDOT10k archive packages (``year``) of one powiat or of every
        powiat of an area (PRG, TERYT order) through the collection unit jobs
        (ADR-042 D10-D11): the original ZIP 1:1, labelled by its year.

        A failing powiat lands in ``failed``. Progress per powiat of an area
        only (``_each_powiat``).
        """
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)
        if teryt is not None:
            teryts, parent = [teryt], None
        else:
            teryts, parent = self._area_teryts(bbox, sheet)
        jobs = self._archive_jobs(teryts, options, parent=parent)
        planned, stale = self._planned(
            lambda: [self._inspect_archive(job) for job in jobs], update, plan
        )
        by_unit = {job.unit: job for job in jobs}

        def one(unit: str, started: Callable[[], None] | None) -> _PowiatOutcome:
            job = by_unit[unit]
            return self._unit(
                unit,
                lambda: _UnitResult(
                    unit,
                    run_job(
                        job,
                        update,
                        sink=sink,
                        planned=planned,
                        session=provider.session(),
                        on_download=started,
                    ),
                ),
            )

        outcomes = _each_powiat(
            list(by_unit), one, workers, on_progress if teryt is None else None
        )
        return outcomes, stale

    def _archive(self, kwargs: dict) -> bool:
        """BDOT10k with ``year``: the yearly archive (ADR-042 D11)."""
        return (
            isinstance(self._provider, Bdot10kProvider)
            and kwargs.get("year") is not None
        )

    def _archive_jobs(
        self, teryts: Sequence[str], kwargs: dict, *, parent: dict | None
    ) -> list[UnitJob]:
        """Unit jobs of the archive packages of ``teryts`` (sidecar ``request``
        = the powiat, ``format`` and ``year``)."""
        key = self._descriptor_key()
        variant = self._archive_variant(kwargs)
        descriptor, channel = get_source(key), _archive_channel(key)
        fmt, year = kwargs["format"], kwargs["year"]
        return [
            package_job(
                self._output_dir,
                descriptor,
                channel,
                variant,
                country="PL",
                teryt=teryt,
                request={"teryt": teryt, "format": fmt, "year": year},
                parent=parent,
            )
            for teryt in teryts
        ]

    def _inspect_archive(self, job: UnitJob) -> PlanItem:
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)
        return inspect_job(job, track=_TRACK, session=provider.session())

    # =========================================================================
    # Request -> jobs
    # =========================================================================

    def _selection(
        self,
        teryt: str | None,
        sheet: str | None,
        bbox: BBox | None,
        geometry: str | Path | None,
        layer: str | None,
        sink: NoticeSink,
    ) -> tuple[str | None, str | None, BBox | None]:
        """Exactly one selection; ``geometry`` -> its EPSG:2180 envelope.

        A raster bbox goes to EPSG:2180 (the store slot); a BDOT10k bbox
        stays in its CRS (PRG converts it, ``parent_request`` keeps it).
        """
        given = [v for v in (teryt, sheet, bbox, geometry) if v is not None]
        provider = self._provider
        bdot = isinstance(provider, Bdot10kProvider)
        corine = isinstance(provider, CorineProvider)  # else SoilGrids (soil group)
        if len(given) != 1:
            if bdot:
                raise ValidationError(
                    "Podaj dokladnie jeden wybor dla --product bdot10k: "
                    f"{selection_choices(self._descriptor_key())}"
                )
            where = " dla --product corine" if corine else ""
            raise ValidationError(
                f"Podaj dokladnie jeden wybor{where}: {_AREA_CHOICES}"
            )
        check_layer(layer, geometry, landcover=bdot)
        if teryt is not None:
            if not bdot:
                name = "--product corine" if corine else "SoilGrids"
                raise ValidationError(
                    f"--teryt dziala tylko z {_TERYT_PRODUCTS}; {name}: podaj "
                    f"{_AREA_CHOICES}"
                )
            if not provider.validate_admin_unit(teryt):
                if re.fullmatch(r"[0-9]{2}", teryt):
                    raise ValidationError(
                        f"--teryt {teryt}: BDOT10k jest publikowany per powiat - "
                        "podaj --teryt <4 cyfry> (np. 1465); dostepne: "
                        f"{selection_choices(self._descriptor_key())}"
                    )
                raise ValidationError(
                    f"Nieprawidlowy kod TERYT {teryt!r}: powiat BDOT10k (4 cyfry, "
                    "np. 1465)"
                )
        if sheet is not None:
            SheetParser(sheet)  # a malformed code: ParseError before any request
        if geometry is not None:
            bbox = geometry_envelope_2180(geometry, layer, sink)
        elif bbox is not None:
            bbox = validate_request_bbox(bbox)
            if not isinstance(self._provider, Bdot10kProvider):
                bbox = bbox_to_2180(bbox)
        return teryt, sheet, bbox

    def _corine_preview(self, options: dict, sink: NoticeSink) -> None:
        """``CORINE_PREVIEW`` before downloading a WMS preview instead of data."""
        provider = self._provider
        if isinstance(provider, CorineProvider) and not provider.uses_clms(
            options["year"]
        ):
            sink.emit(
                "info",
                CORINE_PREVIEW,
                f"CORINE {options['year']}: podglad WMS (stylizowany PNG, nie dane; "
                "dane CLMS wymagaja CLMS_CREDENTIALS)",
            )

    def _kind(self) -> type:
        for cls in _OPTIONS:
            if isinstance(self._provider, cls):
                return cls
        raise ValidationError(
            f"LandCoverManager obsluguje BDOT10k, CORINE i SoilGrids, "
            f"nie {self._provider.name!r} (plik poza magazynem: "
            "provider.download_by_*)"
        )

    def _check_options(self, kwargs: dict) -> None:
        """Reject wrong-source values and missing required options as input errors."""
        kind = self._kind()
        unknown = sorted(set(kwargs) - _KNOWN_OPTIONS)
        if unknown:
            raise TypeError(
                f"{self._provider.name}: nieznane opcje {unknown} (dozwolone: "
                f"{sorted(_OPTIONS[kind])}; plik poza magazynem: "
                "provider.download_by_*)"
            )
        for name in _REQUIRED[kind]:
            if kwargs.get(name) is None:
                raise ValidationError(_REQUIRED_MESSAGES[name])
        for name in kwargs:
            if name not in _OPTIONS[kind] and kwargs[name] is not None:
                if name in ("keep_raw", "whole_country") and not kwargs[name]:
                    continue
                products = [
                    product
                    for product, options in _PRODUCT_OPTIONS.items()
                    if name in options
                ]
                raise ValidationError(
                    f"--{name.replace('_', '-')} dziala tylko z --product "
                    f"{' albo '.join(products)}"
                )
        # library calls only: the CLI parses its flags (STANDARDS 11.2)
        if kwargs.get("year") is not None:
            require_int(kwargs["year"], "--year")
        if kwargs.get("layers") is not None:
            require_codes(kwargs["layers"], "--layers", "['PTWP', 'SWRS']")
        if kwargs.get("keep_raw") is not None:
            require_bool(kwargs["keep_raw"], "--keep-raw")
        provider = self._provider
        if isinstance(provider, SoilGridsProvider):
            for name, label, allowed in (
                ("property", "wlasciwosc", provider.PROPERTIES),
                ("depth", "glebokosc", provider.DEPTHS),
                ("stat", "statystyka", provider.STATS),
            ):
                if kwargs[name] not in allowed:
                    raise ValidationError(
                        f"Nieprawidlowa {label}: {kwargs[name]}. "
                        f"Dostepne: {', '.join(allowed)}"
                    )
        elif isinstance(provider, CorineProvider):
            if kwargs["year"] not in provider.AVAILABLE_YEARS:
                raise ValidationError(
                    f"Nieprawidlowy rok: {kwargs['year']}. "
                    f"Dostepne lata: {provider.AVAILABLE_YEARS}"
                )
        else:
            self._check_bdot10k(kwargs)

    def _check_bdot10k(self, kwargs: dict) -> None:
        """BDOT10k: current packages (``format`` GPKG/SHP, ``layers`` and
        ``keep_raw`` of GPKG) or, with ``year``, the yearly archive (ADR-042
        D11: ``format`` GML or SHP required, the package 1:1)."""
        if kwargs.get("year") is not None:
            for name in ("layers", "keep_raw"):
                if kwargs.get(name) not in (None, False):
                    raise ValidationError(
                        f"--{name.replace('_', '-')} nie dotyczy archiwum BDOT10k "
                        "(--year: paczka powiatu GML albo SHP zapisywana 1:1)"
                    )
            self._archive_variant(kwargs)
            return
        fmt = kwargs.get("format", "GPKG")
        if fmt not in ("GPKG", "SHP"):
            raise ValidationError(
                f"--format {fmt}: biezace paczki BDOT10k to GPKG albo SHP; GML "
                "tylko z --year (archiwum rocznikow)"
            )
        if kwargs.get("layers") is not None:
            normalize_layers(kwargs["layers"])
            if fmt != "GPKG":
                raise ValidationError(
                    "--layers dotyczy tylko --format GPKG (SHP to oryginalny ZIP "
                    "paczki)"
                )
        if kwargs.get("keep_raw") and fmt != "GPKG":
            raise ValidationError(
                "--keep-raw dotyczy tylko --format GPKG (SHP to juz oryginalny ZIP)"
            )

    def _archive_variant(self, kwargs: dict) -> PackageVariant:
        """The archive package of ``format`` and ``year`` (no network).

        Raises
        ------
        ValidationError
            Missing or unpublished format (GML, SHP) or year (2014-2025).
        """
        params = _archive_channel(self._descriptor_key()).params
        assert isinstance(params, UnitPackageParams)
        return select_variant(
            params, format=kwargs.get("format"), year=str(kwargs["year"])
        )

    def _emit_file_notices(
        self, file: VersionedFile, update: UpdateMode | None, sink: NoticeSink
    ) -> None:
        """Report signal failures and unchecked local versions of a store file."""
        unit = file.path.relative_to(self._output_dir).as_posix()
        emit_file_notices(sink, unit, file, update)

    def _content_params(self, kwargs: dict) -> dict[str, object]:
        """Provider options that change the CONTENT of the result.

        They name the segment and go into the sidecar ``request``.
        """
        provider = self._provider
        if isinstance(provider, SoilGridsProvider):
            return {
                "property": kwargs["property"],
                "depth": kwargs["depth"],
                "stat": kwargs["stat"],
            }
        if isinstance(provider, CorineProvider):
            return {"year": kwargs["year"]}
        params: dict[str, object] = {"format": kwargs.get("format", "GPKG")}
        if kwargs.get("layers") is not None:
            params["layers"] = normalize_layers(kwargs["layers"])
        return params

    def _jobs(
        self,
        *,
        teryt: str | None = None,
        bbox: BBox | None = None,
        sheet: str | None = None,
        kwargs: dict,
    ) -> list[_Job]:
        """Files of one selection (BDOT10k: by TERYT; ``keep_raw`` = 2 files)."""
        provider = self._provider
        key = self._descriptor_key()
        out = self._output_dir
        tokens: tuple[str, ...]
        if isinstance(provider, Bdot10kProvider):
            assert teryt is not None
            params = self._content_params(kwargs)
            signal = channel_signal(key, TransportKind.DIRECT_FILES)
            layers = params.get("layers")
            if params["format"] == "SHP":
                tokens, ext = ("shp",), ".zip"
            elif isinstance(layers, list):
                tokens, ext = ("gpkg", "-".join(layers)), ".gpkg"
            else:
                tokens, ext = ("gpkg",), ".gpkg"
            segment = content_segment(key, tokens)
            selection = {"teryt": teryt}
            jobs = [
                _Job(
                    unit_slot(out, segment, ext, teryt=teryt),
                    teryt,
                    signal,
                    selection,
                )
            ]
            if kwargs.get("keep_raw"):
                raw = content_segment(key, ("gpkg", "zip"))
                raw_slot = unit_slot(out, raw, ".zip", teryt=teryt)
                jobs.append(_Job(raw_slot, teryt, signal, selection))
            return jobs
        unit = selection_unit(bbox=bbox, sheet=sheet)
        if bbox is not None:
            request: dict = {
                "bbox": bbox_coords(bbox),
                "bbox_crs": bbox.crs,
            }
        else:
            request = {"sheet": unit}
        edition: EditionLookup | None
        if isinstance(provider, SoilGridsProvider):
            soil = provider
            prop = kwargs["property"]
            tokens = (prop, kwargs["depth"], kwargs["stat"])
            ext, transport = ".tif", TransportKind.WCS
            edition = memoized_edition(lambda: soil.edition(prop))
        else:
            assert isinstance(provider, CorineProvider)
            corine = provider
            year = kwargs["year"]
            if corine.uses_clms(year):
                tokens, ext, transport = (str(year),), ".tif", TransportKind.CLMS_API
                edition = memoized_edition(lambda: corine.edition(year))
            else:
                tokens, ext = (str(year), "preview"), ".png"
                transport, edition = TransportKind.WMS, None
        signal = channel_signal(key, transport)
        slot = unit_slot(out, content_segment(key, tokens), ext, bbox=bbox, sheet=sheet)
        return [
            _Job(
                slot,
                unit,
                signal,
                request,
                edition if signal == "metadata" else None,
                bbox=bbox,
                sheet=unit if sheet is not None else None,
            )
        ]

    def _descriptor_key(self) -> str:
        key = getattr(self._provider, "descriptor_key", None)
        assert isinstance(key, str)  # the three supported providers (_kind)
        return key

    def _area_teryts(
        self, bbox: BBox | None, sheet: str | None
    ) -> tuple[list[str], dict]:
        """Powiats of a BDOT10k area (PRG, its 30 s timeout - P7) and its
        ``extra.parent_request``."""
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)  # callers: BDOT10k only
        parent, area = self._bdot_area(bbox, sheet)
        teryts = provider.teryts_for_area(area)
        if not teryts:
            raise NoCoverageError("BDOT10k: obszar nie przecina zadnego powiatu (PRG)")
        return teryts, parent

    def _area_jobs(
        self, *, bbox: BBox | None = None, sheet: str | None = None, kwargs: dict
    ) -> tuple[list[_Job], dict | None]:
        """Jobs of a raster bbox/sheet selection (one file, no parent)."""
        if sheet is not None:
            sheet = SheetParser(sheet).sheet  # one canonical code (A7)
        return self._jobs(bbox=bbox, sheet=sheet, kwargs=kwargs), None

    @staticmethod
    def _bdot_area(bbox: BBox | None, sheet: str | None) -> tuple[dict, BBox]:
        """``extra.parent_request`` and the PRG query area of a BDOT10k selection."""
        if sheet is not None:
            parser = SheetParser(sheet)
            parent: dict = {"sheet": parser.sheet, "countries": ["PL"]}
            return parent, parser.get_bbox(crs="EPSG:2180")
        assert bbox is not None
        parent = {
            "bbox": bbox_coords(bbox),
            "bbox_crs": bbox.crs,
            "countries": ["PL"],
        }
        return parent, bbox

    # =========================================================================
    # Store policy
    # =========================================================================

    @staticmethod
    def _inspect(job: _Job) -> PlanItem:
        return inspect_version(
            job.slot,
            track=_TRACK,
            unit=job.unit,
            signal=job.signal,
            edition=job.edition,
        )

    def _planned(
        self,
        inspect: Callable[[], list[PlanItem]],
        update: UpdateMode | None,
        plan: UpdatePlan | None,
    ) -> tuple[set[_SlotKey] | None, tuple[PlanItem, ...]]:
        """Planned slots to execute now (``None`` = no plan) and stale positions;
        ``inspect`` gives the current plan positions of the request's files."""
        validate_update(update)
        if plan is None:
            return None, ()
        if update != "upgrade":
            raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
        require_store(plan, store_id(self._output_dir))
        todo, stale = select_planned(plan, inspect(), _TRACK)
        return {(i.segment, i.hierarchy, i.name) for i in todo}, tuple(stale)

    @staticmethod
    def _local_only(slot: FileSlot) -> VersionedFile | None:
        """A position left out of the plan: its local version, never a download."""
        local = local_version(slot)
        if local is None:
            return None
        link_version(slot.std, local, refresh=False)
        return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)

    def _run(
        self,
        jobs: list[_Job],
        kwargs: dict,
        update: UpdateMode | None,
        planned: set[_SlotKey] | None,
        *,
        parent: dict | None,
        on_download: Callable[[], None] | None = None,
    ) -> _UnitResult:
        """Local versions or one download for the jobs of one unit (spec 4.2).

        A job out of the plan keeps its local version; the others go through
        ``use_local``. When any job needs a download, the content is
        downloaded once and every job in scope is stored (``store_file``;
        same content = ``unchanged``, decision 9). ``on_download`` is called
        right before that download.
        """
        outcome: list[VersionedFile | None] = []
        in_scope: list[bool] = []
        for job in jobs:
            if planned is not None and job.key not in planned:
                outcome.append(self._local_only(job.slot))
                in_scope.append(False)
            else:
                outcome.append(
                    use_local(job.slot, update, signal=job.signal, edition=job.edition)
                )
                in_scope.append(True)
        if any(s and f is None for s, f in zip(in_scope, outcome, strict=True)):
            if on_download is not None:
                on_download()
            if isinstance(self._provider, Bdot10kProvider):
                outcome = self._fetch_bdot(jobs, in_scope, outcome, kwargs, parent)
            else:
                outcome = [self._fetch_raster(jobs[0], kwargs)]
        return _UnitResult(
            jobs[0].unit,
            outcome[0],
            raw=outcome[1] if len(outcome) > 1 else None,
        )

    def _request(self, job: _Job, kwargs: dict) -> dict:
        """Sidecar ``request``: the selection of this file + content params."""
        return {**job.selection, **self._content_params(kwargs)}

    def _fetch_raster(self, job: _Job, kwargs: dict) -> VersionedFile:
        """Download one SoilGrids/CORINE file and store it as a version."""
        provider = self._provider
        key = self._descriptor_key()
        version = job.version()  # the edition BEFORE the download (D30)
        request = self._request(job, kwargs)
        horizontal_crs = None
        extra: dict = {}
        if isinstance(provider, CorineProvider) and job.signal == "none":
            # WMS preview: EEA Discomap (EPSG:3857) or DLR for 1990 (EPSG:4326)
            year = kwargs["year"]
            horizontal_crs = (
                "EPSG:3857" if year in CorineProvider.EEA_YEARS else "EPSG:4326"
            )
            extra.update(_PREVIEW_NOTE)
        if job.edition is not None:
            extra["edition"] = job.edition().to_extra()

        def write(data: Path, ref: VersionRef, dg: ContentDigest, _http) -> None:
            emit_sidecar(
                key,
                data,
                request=request,
                horizontal_crs=horizontal_crs,
                extra=extra or None,
                nodata=_read_geotiff_nodata(data),
                exclusive=True,
                digest=(dg.sha256, dg.size_bytes),
                version=ref.to_extra(),
            )

        staged = new_staging(job.slot)
        try:
            if job.sheet is not None:
                path = provider.download_by_sheet(job.sheet, staged, **kwargs)
            else:
                assert job.bbox is not None
                path = provider.download_by_bbox(job.bbox, staged, **kwargs)
            if Path(path) != staged:
                os.replace(path, staged)
        except BaseException:
            discard_staging(staged, job.slot)
            raise
        return store_file(
            job.slot,
            staged,
            version=version,
            write_sidecar=write,
            http=None,
            signal=job.signal,
        )

    def _fetch_bdot(
        self,
        jobs: list[_Job],
        in_scope: list[bool],
        outcome: list[VersionedFile | None],
        kwargs: dict,
        parent: dict | None,
    ) -> list[VersionedFile | None]:
        """Download one BDOT10k package; store the raw ZIP, then the result."""
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)
        key = self._descriptor_key()
        main = jobs[0]
        raw = jobs[1] if len(jobs) > 1 and in_scope[1] else None
        teryt = main.unit
        version = VersionRef.downloaded()
        staged = new_staging(main.slot)
        staged_raw = new_staging(raw.slot) if raw is not None else None
        options = {"format": kwargs["format"]} if "format" in kwargs else {}
        try:
            package = provider.download_package(
                teryt,
                staged,
                layers=kwargs.get("layers"),
                keep_raw=staged_raw is not None,
                raw_path=staged_raw,
                **options,
            )
            if package.path != staged:
                os.replace(package.path, staged)
        except BaseException:
            discard_staging(staged, main.slot)
            if raw is not None and staged_raw is not None:
                discard_staging(staged_raw, raw.slot)
            raise
        source = {"url": package.url, "teryt": package.teryt, "format": package.format}
        base: dict = {"source": source, "http": package.http}
        if parent:
            base["parent_request"] = parent

        def writer(request: dict, extra: dict) -> Callable:
            def write(data: Path, ref: VersionRef, dg: ContentDigest, _http) -> None:
                emit_sidecar(
                    key,
                    data,
                    request=request,
                    extra=extra,
                    exclusive=True,
                    digest=(dg.sha256, dg.size_bytes),
                    version=ref.to_extra(),
                )

            return write

        result = list(outcome)
        main_extra = dict(base)
        if raw is not None and staged_raw is not None:
            try:
                raw_file = store_file(
                    raw.slot,
                    staged_raw,
                    version=version,
                    # The raw ZIP is the full package: no layers in its request.
                    write_sidecar=writer({"teryt": teryt, "format": "GPKG"}, base),
                    http=package.http,
                    signal=raw.signal,
                )
            except BaseException:
                discard_staging(staged, main.slot)
                raise
            result[1] = raw_file
            main_extra["source_files"] = [
                {
                    "name": "package",
                    "file": raw_file.version_path.relative_to(
                        self._output_dir
                    ).as_posix(),
                    "sha256": raw_file.sha256,
                }
            ]
        result[0] = store_file(
            main.slot,
            staged,
            version=version,
            write_sidecar=writer(self._request(main, kwargs), main_extra),
            http=package.http,
            signal=main.signal,
        )
        return result

    # =========================================================================
    # Info methods
    # =========================================================================

    @staticmethod
    def get_available_providers() -> list[str]:
        """Return list of available provider (source) names."""
        return [*PROVIDERS, *COLLECTION_SOURCES]

    def get_available_layers(self) -> list[str]:
        """Return available layers from current provider (a collection
        source: the GPKG layer names of an area result, registry order; a
        source of packages with classes - BDOO - the class codes of every
        release, sorted; ``layers`` of a release: ``collection_classes``)."""
        if self._collection is not None:
            layers = collection_layers(self._collection)
            if layers:
                return [layer.name for layer in layers]
            classes = collection_classes(self._collection).values()
            return sorted({code for codes in classes for code in codes})
        return self._provider.get_available_layers()

    def get_supported_formats(self) -> list[str]:
        """Return supported formats from current provider (a collection
        source: GPKG of an area, the national file as published; BDOO: the
        ZIP of GML files as published)."""
        if self._collection is not None:
            return ["GPKG"] if collection_layers(self._collection) else ["ZIP"]
        return self._provider.get_supported_formats()

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"LandCoverManager("
            f"provider={self.provider_name!r}, "
            f"output_dir={self._output_dir!r})"
        )


# =============================================================================
# Command-level functions (``landcover download``, ``soil download``; ADR-044)
# =============================================================================

# Content choices of ``landcover download`` and ``soil download``: the
# ``LandCoverManager`` options of the product given.
_LANDCOVER_CHOICES = (
    "whole_country",
    "year",
    "format",
    "layers",
    "keep_raw",
    "horizontal_crs",
)
_SOIL_CHOICES = ("property", "depth", "stat")


def _given(arguments: dict, names: Sequence[str]) -> dict:
    """The choices given (``None`` and ``False`` = not chosen)."""
    return {
        name: arguments[name]
        for name in names
        if arguments[name] is not None and arguments[name] is not False
    }


def _landcover_manager(
    product: str | None, output_dir: str | Path | None, cache: MetadataCache | bool
) -> LandCoverManager:
    """The manager of ``product`` in the store ``output_dir`` (both checked
    first, without network)."""
    chosen = require_landcover_product(product)
    if output_dir is None:
        raise ValidationError(output_required("landcover"))
    return LandCoverManager(output_dir, chosen, cache=cache)


def _soil_manager(
    output_dir: str | Path | None, cache: MetadataCache | bool
) -> LandCoverManager:
    """The SoilGrids manager of the store ``output_dir`` (checked first)."""
    if output_dir is None:
        raise ValidationError(output_required("soil"))
    return LandCoverManager(output_dir, "soilgrids", cache=cache)


def download_landcover(
    *,
    product: str | None,
    output_dir: str | Path | None,
    teryt: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    year: int | None = None,
    format: str | None = None,
    layers: Sequence[str] | None = None,
    keep_raw: bool = False,
    horizontal_crs: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 1,
    cache: MetadataCache | bool = True,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_notice: Callable[[Notice], None] | None = None,
) -> LandCoverReport:
    """Download land cover data (``landcover download``) into the version
    store of ``output_dir``.

    Parameter names and values are the flags of the command in
    ``snake_case``; every data choice is explicit. ``product``:
    ``bdot10k``, ``bdoo``, ``corine``, ``zabaged``, ``data50``,
    ``data250`` (``LANDCOVER_PRODUCTS``; SoilGrids: ``download_soil``).
    Exactly one selection: ``teryt`` (BDOT10k: a powiat, 4 digits; BDOO: a
    voivodeship, 2 digits), ``sheet``, ``bbox`` (any supported CRS),
    ``geometry`` (SHP/GPKG; its envelope, ``layer`` of a GPKG) or
    ``whole_country`` (ZABAGED, Data50, Data250).

    - BDOT10k: ``format`` ``"GPKG"`` (default) or ``"SHP"`` (the ZIP of the
      package), optional ``layers`` (layer codes, e.g. ``["PTWP", "SWRS"]``;
      GPKG) and ``keep_raw`` (the original ZIP as a second file, ``raw``);
      an area = the package of EVERY powiat of it (PRG), ``workers`` in
      parallel. With ``year`` 2014-2025 the yearly archive (state at the
      start of the year): the powiat package 1:1 with a required ``format``
      ``"GML"`` or ``"SHP"``, labelled by its year, identical years stored
      once (``relabeled``, ADR-042 D7, D11).
    - BDOO (PL): required ``year`` 2015, 2021-2026 - the original GML
      package of each voivodeship (of ``teryt`` or of the area); optional
      ``layers`` - class codes of that release (``["ADJA", "PTWP"]``): a ZIP
      of the files of those classes only (a class without objects in the
      voivodeship: ``CLASSES_ABSENT``; none of them: a ``no_coverage``
      failure of the voivodeship).
    - CORINE: required ``year`` 2018/2012/2006/2000 (CLMS data with
      ``CLMS_CREDENTIALS``, else the WMS preview: ``CORINE_PREVIEW``),
      1990 (WMS preview only).
    - ZABAGED, Data50, Data250 (CZ): an area (``bbox``/``geometry``) -> one
      GPKG of the object layers of the service in EPSG:5514;
      ``whole_country=True`` with ``horizontal_crs`` ``"EPSG:5514"`` or
      ``"EPSG:3045"`` -> the national file of the ATOM feed 1:1, labelled by
      its edition, size announced first (``WHOLE_COUNTRY_SIZE``).

    Files: ``landcover/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|
    <arkusz>|country/cz}`` with versions in ``versions/`` (spec 3.4).
    ``update``/``plan`` as in every store command (``plan`` from
    ``check_landcover`` with ``update="upgrade"``); ``cache``: metadata
    cache of the PRG powiat query and of the ATOM feed index (``True``:
    default file in the current directory, ``False``: none);
    ``on_progress``: the units of an area of BDOT10k powiats or BDOO
    voivodeships as for a sheet list; ``on_notice`` receives each notice
    when emitted.

    Returns
    -------
    LandCoverReport
        ``files``, ``raw``, ``failed`` (a file that failed, the other units
        still ran), ``stale``, ``notices`` and ``ok``.

    Raises
    ------
    ValidationError
        Invalid or missing choice or an argument of a wrong type
        (``year="2018"``, ``layers="SWRS,PTWP"``; never converted) - before
        any request; a plan of another store or without
        ``update="upgrade"``; an area of a collection source over the volume
        limits (before any transfer).
    NoCoverageError
        A BDOT10k or BDOO area intersecting no powiat.
    DownloadError
        The PRG powiat query of an area failed.

    Examples
    --------
    >>> report = download_landcover(
    ...     product="bdot10k", output_dir="./data", teryt="1465"
    ... )
    >>> report.files[0].file.path  # data/landcover/pl_bdot10k_gpkg/teryt/1465.gpkg
    >>> area = download_landcover(
    ...     product="bdot10k", output_dir="./data", layers=["PTWP", "SWRS"],
    ...     bbox=BBox(450000, 550000, 460000, 560000, "EPSG:2180"), workers=4,
    ... )
    >>> [item.unit for item in area.files], area.failed, area.ok
    """
    manager = _landcover_manager(product, output_dir, cache)
    return manager.download(
        teryt=teryt,
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        update=update,
        plan=plan,
        workers=workers,
        on_notice=on_notice,
        on_progress=on_progress,
        **_given(locals(), _LANDCOVER_CHOICES),
    )


def check_landcover(
    *,
    product: str | None,
    output_dir: str | Path | None,
    teryt: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    year: int | None = None,
    format: str | None = None,
    layers: Sequence[str] | None = None,
    keep_raw: bool = False,
    horizontal_crs: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_landcover`` with the same choice; no data
    is downloaded (``kartograf-plan/1``, track ``landcover``).

    CORINE (CLMS) compares the local version with the CLMS catalogue, the
    national files of ZABAGED, Data50 and Data250 with the edition of their
    ATOM feed; BDOT10k (also the archive), BDOO, the CORINE preview and the
    areas of the CZ sources have no cheap signal (``unverifiable``/
    ``missing``). An area of BDOT10k or BDOO asks PRG for its units (every
    powiat or voivodeship is a position); ``keep_raw`` adds the position of
    the raw ZIP. The source is always asked: the metadata cache is
    refreshed, never read.

    Raises
    ------
    ValidationError
        Invalid or missing choice (as ``download_landcover``).
    NoCoverageError
        A BDOT10k or BDOO area intersecting no powiat.
    DownloadError
        The PRG powiat query of an area failed.
    """
    manager = _landcover_manager(product, output_dir, cache)
    return manager.check(
        teryt=teryt,
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        on_notice=on_notice,
        **_given(locals(), _LANDCOVER_CHOICES),
    )


def validate_landcover_request(
    *,
    product: str | None,
    output_dir: str | Path | None,
    teryt: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    year: int | None = None,
    format: str | None = None,
    layers: Sequence[str] | None = None,
    keep_raw: bool = False,
    horizontal_crs: str | None = None,
) -> None:
    """Every check ``download_landcover``/``check_landcover`` make before
    their first request, without network and without writing (a
    ``geometry`` file is read for its envelope): the same exception type and
    text as the download (``project add``, ADR-040).

    Raises
    ------
    ValidationError
        Invalid or missing choice.
    """
    _landcover_manager(product, output_dir, False).validate_request(
        teryt=teryt,
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        **_given(locals(), _LANDCOVER_CHOICES),
    )


def download_soil(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    property: str | None = None,
    depth: str | None = None,
    stat: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> SoilReport:
    """Download one SoilGrids layer (``soil download``) of an area into the
    version store of ``output_dir``.

    Parameter names and values are the flags of the command in
    ``snake_case``; every choice is required: one area (``sheet``,
    ``bbox`` in any supported CRS - the store slot is its EPSG:2180
    envelope - or ``geometry`` with ``layer`` of a GPKG), ``property`` (bdod
    density, cec exchange capacity, cfvo coarse fragments, clay, nitrogen,
    ocd organic carbon density, ocs organic carbon stock, phh2o pH, sand,
    silt, soc organic carbon), ``depth`` (0-5cm, 5-15cm, 15-30cm, 30-60cm,
    60-100cm, 100-200cm below surface) and ``stat`` (mean, Q0.05, Q0.5,
    Q0.95, uncertainty). File:
    ``soil/global_soilgrids_<property>_<depth>_<stat>/{bbox/<coords>|<arkusz>}.tif``,
    labelled by the SoilGrids edition (e.g. ``2.0``). ``update``/``plan``
    (from ``check_soil``), ``cache`` (SoilGrids capabilities) and
    ``on_notice`` as in ``download_landcover``.

    Returns
    -------
    SoilReport
        ``files`` (the raster), ``failed``, ``stale``, ``notices``, ``ok``.

    Raises
    ------
    ValidationError
        Invalid or missing choice - before any request; a plan of another
        store or without ``update="upgrade"``.

    Examples
    --------
    >>> report = download_soil(
    ...     output_dir="./data", sheet="N-34-130-D",
    ...     property="clay", depth="0-5cm", stat="mean",
    ... )
    >>> report.files[0].file.label  # the SoilGrids edition, e.g. 2.0
    """
    report = _soil_manager(output_dir, cache).download(
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        update=update,
        plan=plan,
        on_notice=on_notice,
        **_given(locals(), _SOIL_CHOICES),
    )
    return SoilReport(
        files=report.files,
        failed=report.failed,
        stale=report.stale,
        notices=report.notices,
        ok=report.ok,
    )


def check_soil(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    property: str | None = None,
    depth: str | None = None,
    stat: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_soil`` with the same choice (track
    ``landcover``): the local version compared with the SoilGrids edition
    (GetCapabilities, cache refreshed); no data is downloaded.

    Raises
    ------
    ValidationError
        Invalid or missing choice (as ``download_soil``).
    """
    return _soil_manager(output_dir, cache).check(
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        on_notice=on_notice,
        **_given(locals(), _SOIL_CHOICES),
    )


def validate_soil_request(
    *,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    property: str | None = None,
    depth: str | None = None,
    stat: str | None = None,
) -> None:
    """Every check of ``download_soil``/``check_soil`` before the first
    request, without network (``project add``, ADR-040).

    Raises
    ------
    ValidationError
        Invalid or missing choice.
    """
    _soil_manager(output_dir, False).validate_request(
        sheet=sheet,
        bbox=bbox,
        geometry=geometry,
        layer=layer,
        **_given(locals(), _SOIL_CHOICES),
    )
