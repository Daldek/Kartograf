"""
Land Cover download manager on the versioned store (spec 3.4, D29-D32).

``LandCoverManager`` downloads BDOT10k, CORINE and SoilGrids into the
``data/`` layout of its output directory (the store root, as ``--output``):
every file is an immutable version with a hardlink at the standard path.
SoilGrids and CORINE (CLMS) versions are labelled by the source edition
(signal ``metadata``), the CORINE WMS preview and BDOT10k by the download
date (signal ``none``). Files outside the store: ``provider.download_by_*``.

Supports parallel batch downloads via ThreadPoolExecutor.
"""

import concurrent.futures
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.fetch import (
    EditionLookup,
    FileSlot,
    UpdateMode,
    VersionedFile,
    discard_staging,
    inspect_version,
    link_version,
    local_version,
    memoized_edition,
    new_staging,
    store_file,
    use_local,
    validate_update,
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
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.landcover.store import landcover_segment, selection_slot, selection_unit
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider, normalize_layers
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.descriptor import SignalKind, TransportKind
from kartograf.sources.registry import channel_signal
from kartograf.sources.sidecar import emit_sidecar

logger = logging.getLogger(__name__)


# Registry of available providers
PROVIDERS = {
    "bdot10k": Bdot10kProvider,
    "corine": CorineProvider,
    "soilgrids": SoilGridsProvider,
}

# Options each provider accepts (anything else is a TypeError: e.g. the
# removed ``output_path``, D32).
_OPTIONS: dict[type, frozenset[str]] = {
    Bdot10kProvider: frozenset({"format", "layers", "timeout", "keep_raw"}),
    CorineProvider: frozenset({"year", "timeout"}),
    SoilGridsProvider: frozenset({"property", "depth", "stat", "timeout"}),
}
_REQUIRED: dict[type, tuple[str, ...]] = {
    Bdot10kProvider: (),
    CorineProvider: ("year",),
    SoilGridsProvider: ("property", "depth", "stat"),
}
_PREVIEW_NOTE = {"fallback": "wms_png", "note": "podglad WMS, nie dane"}
_TRACK: Track = "landcover"
# Plan position key of a slot (segment, hierarchy, name).
_SlotKey = tuple[str, str, str]


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
class LandCoverResult:
    """One land cover file of a request (``unit``: TERYT, bbox coords, sheet).

    ``file`` is the store outcome (``path`` = standard path, ``status``,
    ``label``, ``newer``/``unverified``); ``None`` only with ``plan=`` when
    the position was not planned and there is no local version. ``raw``:
    the original BDOT10k ZIP (``keep_raw``). ``stale``: planned positions
    whose source changed since the plan (not downloaded).
    """

    unit: str
    file: VersionedFile | None
    raw: VersionedFile | None = None
    stale: tuple[PlanItem, ...] = ()


@dataclass(frozen=True)
class LandCoverFailure:
    """A BDOT10k powiat that failed in ``download_all_counties``."""

    unit: str
    error: str


@dataclass(frozen=True)
class LandCoverAreaResult:
    """Every BDOT10k powiat of an area: successes, failures, stale positions."""

    files: tuple[LandCoverResult, ...]
    failed: tuple[LandCoverFailure, ...] = ()
    stale: tuple[PlanItem, ...] = ()


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


class LandCoverManager:
    """
    Manager for downloading land cover data into the version store.

    Every file lands in a segment of ``output_dir`` that carries its
    content parameters (spec 3.4): ``landcover/pl_bdot10k_gpkg[_<layers>]``,
    ``landcover/pl_bdot10k_shp``, ``landcover/pl_bdot10k_gpkg_zip``
    (``keep_raw``), ``landcover/eu_corine_<year>[_preview]``,
    ``soil/global_soilgrids_<property>_<depth>_<stat>``; below it
    ``teryt/<TERYT>``, ``bbox/<coords>`` or the sheet hierarchy. ``update``
    selects the mode (spec 4.2): ``None`` uses local versions and only
    reports newer content, ``"upgrade"`` downloads newer content, ``"force"``
    downloads again (same content = ``unchanged``). Checking without a
    download: ``check``/``check_all_counties`` (plan ``kartograf-plan/1``,
    track ``landcover``), executed with ``update="upgrade", plan=...``.

    Parameters
    ----------
    output_dir : str or Path
        Store root (``--output``); created only when a file is written.
    provider : LandCoverProvider or str
        Provider instance or name: "bdot10k" (Polish topographic vectors),
        "corine" (European land cover raster), or "soilgrids" (soil rasters).
    cache : MetadataCache, optional
        Metadata cache handed to a provider created BY NAME (BDOT10k: PRG
        TERYT answers; SoilGrids accepts it; CORINE has none). A provider
        instance keeps its own cache.

    Examples
    --------
    >>> manager = LandCoverManager("./data", "bdot10k")
    >>> result = manager.download(teryt="1465")
    >>> result.file.path  # data/landcover/pl_bdot10k_gpkg/teryt/1465.gpkg
    >>>
    >>> # BDOT10k of every powiat of an area, selected layers only
    >>> from kartograf import BBox
    >>> bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
    >>> area = manager.download_all_counties(bbox=bbox, layers=["PTWP", "SWRS"])
    >>> [r.file.path for r in area.files], area.failed
    >>>
    >>> # SoilGrids: the version label is the SoilGrids edition (e.g. 2.0)
    >>> manager.set_provider("soilgrids")
    >>> manager.download(sheet="N-34-130-D", property="clay", depth="0-5cm",
    ...                  stat="mean").file.label
    >>>
    >>> # Check without downloading, then execute the plan
    >>> plan = manager.check(sheet="N-34-130-D", property="clay",
    ...                      depth="0-5cm", stat="mean")
    >>> manager.download(sheet="N-34-130-D", property="clay", depth="0-5cm",
    ...                  stat="mean", update="upgrade", plan=plan)
    """

    def __init__(
        self,
        output_dir: str | Path,
        provider: LandCoverProvider | str,
        cache: MetadataCache | None = None,
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
            "corine" (land cover raster), or "soilgrids" (soil rasters).
        cache : MetadataCache, optional
            Cache for providers created by name (see the class docstring).
        """
        self._output_dir = Path(output_dir)
        self._cache = cache

        # Initialize provider
        self._provider: LandCoverProvider
        if isinstance(provider, str):
            self._provider = self._get_provider_by_name(provider)
        else:
            self._provider = provider

    def _get_provider_by_name(self, name: str) -> LandCoverProvider:
        """
        Get provider instance by name.

        Parameters
        ----------
        name : str
            Provider name ("bdot10k", "corine", "soilgrids")

        Returns
        -------
        LandCoverProvider
            Provider instance

        Raises
        ------
        ValidationError
            If provider name is unknown
        """
        name_lower = name.lower()
        if name_lower not in PROVIDERS:
            raise ValidationError(
                f"Unknown provider: {name}. "
                f"Available providers: {list(PROVIDERS.keys())}"
            )
        if name_lower == "bdot10k":
            return Bdot10kProvider(cache=self._cache)
        if name_lower == "soilgrids":
            return SoilGridsProvider(cache=self._cache)
        return PROVIDERS[name_lower]()

    @property
    def output_dir(self) -> Path:
        """Store root."""
        return self._output_dir

    @property
    def provider(self) -> LandCoverProvider:
        """Return current provider."""
        return self._provider

    @property
    def provider_name(self) -> str:
        """Return current provider name."""
        return self._provider.name

    def set_provider(self, provider: LandCoverProvider | str) -> None:
        """
        Set the active provider.

        Parameters
        ----------
        provider : LandCoverProvider or str
            Provider instance or name ("bdot10k", "corine", "soilgrids")
        """
        if isinstance(provider, str):
            self._provider = self._get_provider_by_name(provider)
        else:
            self._provider = provider
        logger.info(f"Provider set to: {self._provider.name}")

    # =========================================================================
    # Download
    # =========================================================================

    def download(
        self,
        teryt: str | None = None,
        bbox: BBox | None = None,
        sheet: str | None = None,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        **kwargs,
    ) -> LandCoverResult:
        """
        Download one land cover file into the store.

        Exactly one of teryt, bbox, or sheet must be provided.

        Parameters
        ----------
        teryt : str, optional
            TERYT code (4-digit for powiat; BDOT10k only)
        bbox : BBox, optional
            Bounding box (EPSG:2180; BDOT10k accepts any supported CRS)
        sheet : str, optional
            Map sheet identifier (e.g., "N-34-130-D")
        update : None, "upgrade" or "force", optional
            Download mode (spec 4.2); ``None`` = local versions are used.
        plan : UpdatePlan, optional
            With ``update="upgrade"``: download only the planned positions.
        **kwargs
            CORINE: required ``year`` 2018/2012/2006/2000 (CLMS with
            credentials, else WMS preview), 1990 (WMS preview only).
            SoilGrids: required ``property`` (bdod density, cec exchange
            capacity, cfvo coarse fragments, clay, nitrogen, ocd organic
            carbon density, ocs organic carbon stock, phh2o pH, sand, silt,
            soc organic carbon), ``depth`` (0-5cm, 5-15cm, 15-30cm,
            30-60cm, 60-100cm, 100-200cm below surface), ``stat`` (mean
            average, Q0.05 5th percentile, Q0.5 median, Q0.95 95th
            percentile, uncertainty). BDOT10k: ``format`` GPKG (default) or
            SHP (ZIP), optional ``layers`` and ``keep_raw``. All: ``timeout``.

        Returns
        -------
        LandCoverResult
            The file in the store (``file.path`` = standard path).

        Raises
        ------
        ValidationError
            None or several selections, invalid source options; BDOT10k: the
            area intersects several powiats (see `download_all_counties`);
            a plan of another store or without ``update="upgrade"``.
        TypeError
            An option the provider does not accept (e.g. ``output_path``).
        DownloadError
            Download, edition or store failure.
        """
        self._require_one(teryt, bbox, sheet)
        if teryt is not None:
            return self.download_by_teryt(teryt, update=update, plan=plan, **kwargs)
        if bbox is not None:
            return self.download_by_bbox(bbox, update=update, plan=plan, **kwargs)
        assert sheet is not None
        return self.download_by_sheet(sheet, update=update, plan=plan, **kwargs)

    def download_by_teryt(
        self,
        teryt: str,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        **kwargs,
    ) -> LandCoverResult:
        """
        Download the BDOT10k package of one powiat into ``teryt/<TERYT>``.

        Options and modes as in `download`; the version sidecar has
        ``extra.source`` (``url``, ``teryt``, ``format``) and ``extra.http``,
        with ``keep_raw`` the GeoPackage names the raw ZIP version in
        ``extra.source_files``.
        """
        self._check_options(kwargs)
        jobs = self._jobs(teryt=teryt, kwargs=kwargs)
        planned, stale = self._planned(jobs, update, plan)
        return self._run(jobs, kwargs, update, planned, stale, parent=None)

    def download_by_bbox(
        self,
        bbox: BBox,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        **kwargs,
    ) -> LandCoverResult:
        """
        Download land cover data for a bounding box.

        Rasters: ``<segment>/bbox/<coords>`` (EPSG:2180). BDOT10k: the
        package of the ONE powiat intersecting the bbox, at
        ``teryt/<TERYT>`` with ``extra.parent_request`` (the bbox) - the
        same file as `download_all_counties` gives. Several powiats:
        ``ValidationError`` listing the codes. Options and modes as in
        `download`.
        """
        self._check_options(kwargs)
        jobs, parent = self._area_jobs(bbox=bbox, kwargs=kwargs)
        planned, stale = self._planned(jobs, update, plan)
        return self._run(jobs, kwargs, update, planned, stale, parent=parent)

    def download_by_sheet(
        self,
        sheet: str,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        **kwargs,
    ) -> LandCoverResult:
        """
        Download land cover data for a map sheet.

        Rasters: the sheet hierarchy of the segment (canonical sheet code).
        BDOT10k: as in `download_by_bbox` - the ONE powiat intersecting the
        sheet frame, ``extra.parent_request = {"sheet": ..., "countries":
        ["PL"]}``. Options and modes as in `download`.
        """
        self._check_options(kwargs)
        jobs, parent = self._area_jobs(sheet=sheet, kwargs=kwargs)
        planned, stale = self._planned(jobs, update, plan)
        return self._run(jobs, kwargs, update, planned, stale, parent=parent)

    def download_all_counties(
        self,
        *,
        bbox: BBox | None = None,
        sheet: str | None = None,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        **kwargs,
    ) -> LandCoverAreaResult:
        """BDOT10k packages of EVERY powiat intersecting the area, one file each.

        Exactly one of ``bbox``/``sheet``. Files ``teryt/<T>`` in TERYT
        order; each version sidecar has ``request.teryt`` and
        ``extra.parent_request`` (the area). A powiat failing with
        ``DownloadError`` lands in ``failed``, the others still run
        (spec 4.2). Options and modes as in `download`.

        Raises
        ------
        ValidationError
            Not a BDOT10k provider, or not exactly one of bbox/sheet.
        NoCoverageError
            The area intersects no powiat.
        DownloadError
            PRG failure.
        """
        self._require_bdot()
        self._check_options(kwargs)
        teryts, parent = self._area_teryts(bbox, sheet, kwargs)
        jobs = {t: self._jobs(teryt=t, kwargs=kwargs) for t in teryts}
        planned, stale = self._planned(
            [job for group in jobs.values() for job in group], update, plan
        )
        files: list[LandCoverResult] = []
        failed: list[LandCoverFailure] = []
        for teryt in teryts:
            try:
                result = self._run(
                    jobs[teryt], kwargs, update, planned, (), parent=parent
                )
            except DownloadError as e:
                logger.error(f"BDOT10k {teryt}: {e}")
                failed.append(LandCoverFailure(teryt, str(e)))
                continue
            if result.file is not None:
                files.append(result)
        return LandCoverAreaResult(tuple(files), tuple(failed), stale)

    # =========================================================================
    # Check (no download)
    # =========================================================================

    def check(
        self,
        teryt: str | None = None,
        bbox: BBox | None = None,
        sheet: str | None = None,
        **kwargs,
    ) -> UpdatePlan:
        """Plan of one request WITHOUT downloading data (track ``landcover``).

        SoilGrids and CORINE (CLMS) compare the local version with the
        source edition (GetCapabilities / CLMS catalogue); BDOT10k and the
        CORINE preview have no cheap signal (``unverifiable``/``missing``).
        BDOT10k by bbox/sheet asks PRG for the powiat. ``keep_raw`` adds the
        raw ZIP position of the same unit.
        """
        self._require_one(teryt, bbox, sheet)
        self._check_options(kwargs)
        if teryt is not None:
            jobs = self._jobs(teryt=teryt, kwargs=kwargs)
        else:
            jobs, _ = self._area_jobs(bbox=bbox, sheet=sheet, kwargs=kwargs)
        return new_plan(self._output_dir, [self._inspect(job) for job in jobs])

    def check_all_counties(
        self, *, bbox: BBox | None = None, sheet: str | None = None, **kwargs
    ) -> UpdatePlan:
        """Plan of `download_all_counties` WITHOUT downloading (PRG only)."""
        self._require_bdot()
        self._check_options(kwargs)
        teryts, _ = self._area_teryts(bbox, sheet, kwargs)
        items = [
            self._inspect(job)
            for teryt in teryts
            for job in self._jobs(teryt=teryt, kwargs=kwargs)
        ]
        return new_plan(self._output_dir, items)

    # =========================================================================
    # Batch
    # =========================================================================

    def download_batch(
        self,
        items: list[dict],
        max_workers: int = 4,
        **kwargs,
    ) -> list[LandCoverResult]:
        """
        Download land cover data for multiple items in parallel.

        Each item dict should contain exactly one of: teryt, bbox, sheet.

        Parameters
        ----------
        items : list[dict]
            List of download items, each with one of:
            - {"teryt": "1465"}
            - {"bbox": BBox(...)}
            - {"sheet": "N-34-130-D"}
        max_workers : int, optional
            Maximum number of parallel download threads (default: 4).
            When <= 1, downloads sequentially.
        **kwargs
            Provider-specific choices and ``update`` as for ``download``;
            CORINE ``year`` and SoilGrids ``property``, ``depth``, ``stat``
            are required.

        Returns
        -------
        list[LandCoverResult]
            Results of the successful items. Failed items are logged but do
            not stop the batch.

        Examples
        --------
        >>> manager = LandCoverManager("./data", "bdot10k")
        >>> items = [{"teryt": "1465"}, {"teryt": "1261"}]
        >>> results = manager.download_batch(items, max_workers=2)
        """
        if not items:
            return []

        def _download_single(item: dict) -> LandCoverResult | None:
            try:
                return self.download(**item, **kwargs)
            except Exception as e:
                logger.error(f"Batch download failed for {item}: {e}")
                return None

        results: list[LandCoverResult] = []
        if max_workers <= 1:
            for item in items:
                result = _download_single(item)
                if result is not None:
                    results.append(result)
        else:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = {
                    executor.submit(_download_single, item): item for item in items
                }
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result is not None:
                        results.append(result)

        logger.info(f"Batch download complete: {len(results)}/{len(items)} successful")
        return results

    # =========================================================================
    # Request -> jobs
    # =========================================================================

    @staticmethod
    def _require_one(teryt, bbox, sheet) -> None:
        provided = [m for m in (teryt, bbox, sheet) if m is not None]
        if not provided:
            raise ValidationError("Must provide one of: teryt, bbox, or sheet")
        if len(provided) > 1:
            raise ValidationError("Provide only one of: teryt, bbox, or sheet")

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
        """Reject unknown options (TypeError) and invalid values (ValidationError)."""
        kind = self._kind()
        unknown = sorted(set(kwargs) - _OPTIONS[kind])
        if unknown:
            raise TypeError(
                f"{self._provider.name}: nieznane opcje {unknown} (dozwolone: "
                f"{sorted(_OPTIONS[kind])}; plik poza magazynem: "
                "provider.download_by_*)"
            )
        missing = [k for k in _REQUIRED[kind] if kwargs.get(k) is None]
        if missing:
            raise TypeError(f"{self._provider.name}: wymagane opcje {missing}")
        provider = self._provider
        if isinstance(provider, SoilGridsProvider):
            for name, allowed in (
                ("property", provider.PROPERTIES),
                ("depth", provider.DEPTHS),
                ("stat", provider.STATS),
            ):
                if kwargs[name] not in allowed:
                    raise ValidationError(
                        f"Invalid {name}: {kwargs[name]}. "
                        f"Available: {', '.join(allowed)}"
                    )
        elif isinstance(provider, CorineProvider):
            if kwargs["year"] not in provider.AVAILABLE_YEARS:
                raise ValidationError(
                    f"Invalid year: {kwargs['year']}. "
                    f"Available years: {provider.AVAILABLE_YEARS}"
                )
        else:
            fmt = kwargs.get("format", "GPKG")
            if fmt not in ("GPKG", "SHP"):
                raise ValidationError(f"Unsupported format: {fmt}. Use 'GPKG' or 'SHP'")
            if kwargs.get("layers") is not None:
                normalize_layers(kwargs["layers"])
                if fmt != "GPKG":
                    raise ValidationError("Filtr warstw BDOT10k dziala tylko z GPKG")
            if kwargs.get("keep_raw") and fmt != "GPKG":
                raise ValidationError(
                    "keep_raw dotyczy tylko GPKG (SHP to juz oryginalny ZIP)"
                )

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
            segment = landcover_segment(key, tokens)
            selection = {"teryt": teryt}
            jobs = [
                _Job(
                    selection_slot(out, segment, ext, teryt=teryt),
                    teryt,
                    signal,
                    selection,
                )
            ]
            if kwargs.get("keep_raw"):
                raw = landcover_segment(key, ("gpkg", "zip"))
                raw_slot = selection_slot(out, raw, ".zip", teryt=teryt)
                jobs.append(_Job(raw_slot, teryt, signal, selection))
            return jobs
        if teryt is not None:
            raise NotImplementedError(
                f"{provider.name} does not support TERYT selection - use --bbox "
                "or --sheet (download_by_bbox / download_by_sheet)"
            )
        unit = selection_unit(bbox=bbox, sheet=sheet)
        if bbox is not None:
            request: dict = {
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            }
        else:
            request = {"sheet": unit}
        edition: EditionLookup | None
        if isinstance(provider, SoilGridsProvider):
            soil = provider
            prop = kwargs["property"]
            soil_timeout = kwargs.get("timeout", soil.DEFAULT_TIMEOUT)
            tokens = (prop, kwargs["depth"], kwargs["stat"])
            ext, transport = ".tif", TransportKind.WCS
            edition = memoized_edition(lambda: soil.edition(prop, timeout=soil_timeout))
        else:
            assert isinstance(provider, CorineProvider)
            corine = provider
            year = kwargs["year"]
            corine_timeout = kwargs.get("timeout", corine.DEFAULT_TIMEOUT)
            if corine.uses_clms(year):
                tokens, ext, transport = (str(year),), ".tif", TransportKind.CLMS_API
                edition = memoized_edition(
                    lambda: corine.edition(year, timeout=corine_timeout)
                )
            else:
                tokens, ext = (str(year), "preview"), ".png"
                transport, edition = TransportKind.WMS, None
        signal = channel_signal(key, transport)
        slot = selection_slot(
            out, landcover_segment(key, tokens), ext, bbox=bbox, sheet=sheet
        )
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

    def _require_bdot(self) -> None:
        if not isinstance(self._provider, Bdot10kProvider):
            raise ValidationError("download_all_counties dziala tylko dla BDOT10k")

    def _area_teryts(
        self, bbox: BBox | None, sheet: str | None, kwargs: dict
    ) -> tuple[list[str], dict]:
        """Powiats of a BDOT10k area (PRG) and its ``extra.parent_request``."""
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)  # _require_bdot
        if (bbox is None) == (sheet is None):
            raise ValidationError("Podaj dokladnie jedno z: bbox, sheet")
        parent, area = self._bdot_area(bbox, sheet)
        teryts = provider.teryts_for_area(area, timeout=self._prg_timeout(kwargs))
        if not teryts:
            raise NoCoverageError("BDOT10k: obszar nie przecina zadnego powiatu (PRG)")
        return teryts, parent

    def _area_jobs(
        self, *, bbox: BBox | None = None, sheet: str | None = None, kwargs: dict
    ) -> tuple[list[_Job], dict | None]:
        """Jobs of a bbox/sheet selection; BDOT10k: the ONE powiat (PRG)."""
        provider = self._provider
        if isinstance(provider, Bdot10kProvider):
            parent, area = self._bdot_area(bbox, sheet)
            what = f"BDOT10k {parent['sheet']}" if sheet is not None else "BDOT10k bbox"
            teryt = provider._single_teryt(area, what, self._prg_timeout(kwargs))
            return self._jobs(teryt=teryt, kwargs=kwargs), parent
        if sheet is not None:
            sheet = SheetParser(sheet).sheet  # one canonical code (A7)
        return self._jobs(bbox=bbox, sheet=sheet, kwargs=kwargs), None

    @staticmethod
    def _prg_timeout(kwargs: dict) -> int:
        """PRG lookup timeout: the BDOT10k ``timeout`` option, else 30 s (P7)."""
        return kwargs.get("timeout", 30)

    @staticmethod
    def _bdot_area(bbox: BBox | None, sheet: str | None) -> tuple[dict, BBox]:
        """``extra.parent_request`` and the PRG query area of a BDOT10k selection."""
        if sheet is not None:
            parser = SheetParser(sheet)
            parent: dict = {"sheet": parser.sheet, "countries": ["PL"]}
            return parent, parser.get_bbox(crs="EPSG:2180")
        assert bbox is not None
        parent = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
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
        self, jobs: list[_Job], update: UpdateMode | None, plan: UpdatePlan | None
    ) -> tuple[set[_SlotKey] | None, tuple[PlanItem, ...]]:
        """Planned slots to execute now (``None`` = no plan) and stale positions."""
        validate_update(update)
        if plan is None:
            return None, ()
        if update != "upgrade":
            raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
        require_store(plan, store_id(self._output_dir))
        todo, stale = select_planned(plan, [self._inspect(j) for j in jobs], _TRACK)
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
        stale: tuple[PlanItem, ...],
        *,
        parent: dict | None,
    ) -> LandCoverResult:
        """Local versions or one download for the jobs of one unit (spec 4.2).

        A job out of the plan keeps its local version; the others go through
        ``use_local``. When any job needs a download, the content is
        downloaded once and every job in scope is stored (``store_file``;
        same content = ``unchanged``, decision 9).
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
            if isinstance(self._provider, Bdot10kProvider):
                outcome = self._fetch_bdot(jobs, in_scope, outcome, kwargs, parent)
            else:
                outcome = [self._fetch_raster(jobs[0], kwargs)]
        return LandCoverResult(
            jobs[0].unit,
            outcome[0],
            raw=outcome[1] if len(outcome) > 1 else None,
            stale=stale,
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
        options = {k: kwargs[k] for k in ("timeout", "format") if k in kwargs}
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
        """Return list of available provider names."""
        return list(PROVIDERS.keys())

    def get_available_layers(self) -> list[str]:
        """Return available layers from current provider."""
        return self._provider.get_available_layers()

    def get_supported_formats(self) -> list[str]:
        """Return supported formats from current provider."""
        return self._provider.get_supported_formats()

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"LandCoverManager("
            f"provider={self._provider.name!r}, "
            f"output_dir={self._output_dir!r})"
        )
