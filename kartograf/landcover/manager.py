"""
Land Cover download manager.

This module provides the LandCoverManager class for coordinating
downloads of land cover data from multiple providers.

Supports parallel batch downloads via ThreadPoolExecutor.
"""

import concurrent.futures
import logging
from pathlib import Path

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.storage import FileStorage
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider

logger = logging.getLogger(__name__)


# Registry of available providers
PROVIDERS = {
    "bdot10k": Bdot10kProvider,
    "corine": CorineProvider,
    "soilgrids": SoilGridsProvider,
}

# Providers whose result is a GeoTIFF (CORINE falls back to a .png preview).
_RASTER_PROVIDERS = (CorineProvider, SoilGridsProvider)

# Provider options of a BDOT10k powiat package (``Bdot10kProvider.download_package``).
_BDOT_OPTIONS = ("format", "layers", "timeout", "keep_raw")


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


class LandCoverManager:
    """
    Manager for downloading land cover data.

    Coordinates downloads from multiple land cover providers,
    handles file storage, and provides a unified interface
    for downloading by TERYT, bbox, or sheet code (godlo).

    Parameters
    ----------
    output_dir : str or Path, optional
        Directory for downloaded files (default: "./data/landcover")
    provider : LandCoverProvider or str, optional
        Provider instance or name ("bdot10k", "corine", "soilgrids").
        Default: Bdot10kProvider
    cache : MetadataCache, optional
        Metadata cache handed to a provider created BY NAME (BDOT10k: PRG
        TERYT answers; SoilGrids accepts it; CORINE has none). A provider
        instance keeps its own cache.

    Examples
    --------
    >>> manager = LandCoverManager()
    >>>
    >>> # Download by TERYT (BDOT10k)
    >>> manager.download(teryt="1465")
    >>>
    >>> # Download by sheet code (BDOT10k: the sheet must lie in one powiat)
    >>> manager.download(godlo="N-34-130-D")
    >>>
    >>> # BDOT10k of every powiat of an area, selected layers only
    >>> from kartograf import BBox
    >>> bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
    >>> manager.download_all_counties(bbox=bbox, layers=["PTWP", "SWRS"])
    >>>
    >>> # Download CORINE data
    >>> manager.set_provider("corine")
    >>> manager.download(godlo="N-34-130-D", year=2018)
    >>>
    >>> # Download by bbox
    >>> manager.download(bbox=bbox)
    """

    def __init__(
        self,
        output_dir: str | Path = "./data/landcover",
        provider: LandCoverProvider | str | None = None,
        cache: MetadataCache | None = None,
    ):
        """
        Initialize LandCoverManager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Directory for downloaded files. It is not created here: the
            directory appears only when a download writes its first file.
        provider : LandCoverProvider or str, optional
            Provider instance or name
        cache : MetadataCache, optional
            Cache for providers created by name (see the class docstring)
        """
        self._output_dir = Path(output_dir)
        self._storage = FileStorage(output_dir)
        self._cache = cache

        # Initialize provider
        self._provider: LandCoverProvider
        if provider is None:
            self._provider = Bdot10kProvider(cache=cache)
        elif isinstance(provider, str):
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
        ValueError
            If provider name is unknown
        """
        name_lower = name.lower()
        if name_lower not in PROVIDERS:
            raise ValueError(
                f"Unknown provider: {name}. "
                f"Available providers: {list(PROVIDERS.keys())}"
            )
        if name_lower == "bdot10k":
            return Bdot10kProvider(cache=self._cache)
        if name_lower == "soilgrids":
            return SoilGridsProvider(cache=self._cache)
        return PROVIDERS[name_lower]()

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

    def download(
        self,
        teryt: str | None = None,
        bbox: BBox | None = None,
        godlo: str | None = None,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data.

        Exactly one of teryt, bbox, or godlo must be provided.

        Parameters
        ----------
        teryt : str, optional
            TERYT code (4-digit for powiat)
        bbox : BBox, optional
            Bounding box (EPSG:2180; BDOT10k accepts any supported CRS)
        godlo : str, optional
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path, optional
            Custom output path. If not provided, auto-generated.
        **kwargs
            Additional provider-specific options (e.g., year, layers)

        Returns
        -------
        Path
            Path to downloaded file

        Raises
        ------
        ValueError
            If none or multiple selection methods provided
        ValidationError
            BDOT10k: the area intersects several powiats (see
            `download_all_counties`)
        """
        # Validate exactly one selection method
        methods = [teryt, bbox, godlo]
        provided = [m for m in methods if m is not None]

        if len(provided) == 0:
            raise ValueError("Must provide one of: teryt, bbox, or godlo")
        if len(provided) > 1:
            raise ValueError("Provide only one of: teryt, bbox, or godlo")

        if teryt is not None:
            return self.download_by_teryt(teryt, output_path, **kwargs)
        if bbox is not None:
            return self.download_by_bbox(bbox, output_path, **kwargs)
        if godlo is not None:
            return self.download_by_godlo(godlo, output_path, **kwargs)
        # Unreachable after the validation above; keeps godlo narrowed to str.
        raise ValueError("Must provide one of: teryt, bbox, or godlo")

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a TERYT code.

        Parameters
        ----------
        teryt : str
            TERYT code (4-digit for powiat)
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options (BDOT10k: ``format``, ``layers``,
            ``timeout``, ``keep_raw`` - see ``Bdot10kProvider.download_package``;
            the sidecar gets ``extra.source`` and ``extra.http``)

        Returns
        -------
        Path
            Path to downloaded file
        """
        if isinstance(self._provider, Bdot10kProvider):
            return self._download_county(teryt, kwargs, None, output_path)
        if output_path is None:
            output_path = self._generate_output_path(teryt, None, None, kwargs)
        path = self._provider.download_by_teryt(teryt, output_path, **kwargs)
        self._write_sidecar(path, {"teryt": teryt}, kwargs)
        return path

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a bounding box.

        BDOT10k without ``output_path``: the package of the ONE powiat
        intersecting the bbox, at the standard path
        ``bdot10k[_<layers>]_teryt_<T>.<ext>`` with ``extra.parent_request``
        (the bbox) in the sidecar - the same file as `download_all_counties`
        would give. Several powiats: ``ValidationError`` listing the codes.
        With ``output_path`` the same powiat package goes there and the
        sidecar ``request`` is the bbox. Either way the BDOT10k sidecar has
        ``extra.source``/``extra.http`` (`_write_bdot_sidecars`).

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 (BDOT10k: any supported CRS)
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        request = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
        }
        if isinstance(self._provider, Bdot10kProvider):
            parent, area = self._bdot_area(bbox, None)
            teryt = self._provider._single_teryt(area, "BDOT10k bbox")
            if output_path is None:
                return self._download_county(teryt, kwargs, parent)
            return self._download_county(teryt, kwargs, None, output_path, request)
        if output_path is None:
            output_path = self._generate_output_path(None, bbox, None, kwargs)
        path = self._provider.download_by_bbox(bbox, output_path, **kwargs)
        self._write_sidecar(path, request, kwargs)
        return path

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path | None = None,
        **kwargs,
    ) -> Path:
        """
        Download land cover data for a map sheet.

        BDOT10k without ``output_path``: as in `download_by_bbox` - the ONE
        powiat intersecting the sheet frame, file ``..._teryt_<T>``, sidecar
        ``extra.parent_request = {"sheet": godlo, "countries": ["PL"]}``;
        with ``output_path``: that path and ``request = {"sheet": godlo}``.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path, optional
            Custom output path. Default path follows the same naming as
            `download()` (see `_generate_output_path`).
        **kwargs
            Provider-specific options

        Returns
        -------
        Path
            Path to downloaded file
        """
        # One canonical sheet code in the name and the sidecar (A7)
        godlo = SheetParser(godlo).godlo
        if isinstance(self._provider, Bdot10kProvider):
            parent, area = self._bdot_area(None, godlo)
            teryt = self._provider._single_teryt(area, f"BDOT10k {parent['sheet']}")
            if output_path is None:
                return self._download_county(teryt, kwargs, parent)
            return self._download_county(
                teryt, kwargs, None, output_path, {"sheet": godlo}
            )
        if output_path is None:
            output_path = self._generate_output_path(None, None, godlo, kwargs)
        path = self._provider.download_by_godlo(godlo, output_path, **kwargs)
        self._write_sidecar(path, {"sheet": godlo}, kwargs)
        return path

    def download_all_counties(
        self, *, bbox: BBox | None = None, godlo: str | None = None, **kwargs
    ) -> list[Path]:
        """BDOT10k packages of EVERY powiat intersecting the area, one file each.

        Exactly one of ``bbox``/``godlo``. Files ``bdot10k[_<layers>]_teryt_<T>``
        in TERYT order; each sidecar has ``request.teryt`` and
        ``extra.parent_request`` (the area). Provider options (``format``,
        ``layers``, ``timeout``, ``keep_raw``) as in ``download_by_teryt``.

        Raises
        ------
        ValidationError
            Not a BDOT10k provider, or not exactly one of bbox/godlo.
        NoCoverageError
            The area intersects no powiat.
        DownloadError
            PRG or package download failure (files downloaded before it stay).
        """
        if not isinstance(self._provider, Bdot10kProvider):
            raise ValidationError("download_all_counties dziala tylko dla BDOT10k")
        if (bbox is None) == (godlo is None):
            raise ValidationError("Podaj dokladnie jedno z: bbox, godlo")
        parent, area = self._bdot_area(bbox, godlo)
        teryts = self._provider.teryts_for_area(area)
        if not teryts:
            raise NoCoverageError("BDOT10k: obszar nie przecina zadnego powiatu (PRG)")
        return [self._download_county(teryt, kwargs, parent) for teryt in teryts]

    @staticmethod
    def _bdot_area(bbox: BBox | None, godlo: str | None) -> tuple[dict, BBox]:
        """``extra.parent_request`` and the PRG query area of a BDOT10k selection."""
        if godlo is not None:
            parser = SheetParser(godlo)
            parent: dict = {"sheet": parser.godlo, "countries": ["PL"]}
            return parent, parser.get_bbox(crs="EPSG:2180")
        assert bbox is not None
        parent = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
            "countries": ["PL"],
        }
        return parent, bbox

    def _download_county(
        self,
        teryt: str,
        kwargs: dict,
        parent: dict | None,
        output_path: Path | None = None,
        request: dict | None = None,
    ) -> Path:
        """One powiat package with its sidecars (A2, A4); ``parent`` = the area.

        The single BDOT10k download path of the manager (TERYT, bbox, godlo,
        all counties); default target = the standard ``..._teryt_<T>`` path
        and default sidecar ``request`` = ``{"teryt": teryt}`` (an explicit
        ``output_path`` from bbox/godlo keeps that selection as ``request``).
        """
        provider = self._provider
        assert isinstance(provider, Bdot10kProvider)
        options = {k: v for k, v in kwargs.items() if k in _BDOT_OPTIONS}
        if output_path is None and kwargs.get("keep_raw"):
            # The raw ZIP is the full package: the standard name WITHOUT the
            # layers token (A2), one file for every layer filter.
            full = self._generate_output_path(
                teryt, None, None, self._without_layers(kwargs)
            )
            options["raw_path"] = full.with_name(f"{full.stem}_GPKG.zip")
        target = output_path or self._generate_output_path(teryt, None, None, kwargs)
        package = provider.download_package(teryt, target, **options)
        extra = {"parent_request": parent} if parent else None
        self._write_bdot_sidecars(package, request or {"teryt": teryt}, kwargs, extra)
        return package.path

    def _write_bdot_sidecars(
        self,
        package: Bdot10kPackage,
        request: dict,
        kwargs: dict,
        extra: dict | None = None,
    ) -> None:
        """Sidecars of a BDOT10k package: the result file and the raw ZIP (A4).

        Both get ``extra.source`` (``url``, ``teryt``, ``format``) and
        ``extra.http`` (response headers) over ``extra``; the result's source
        also names the raw ZIP (``raw_file``) when it was kept. The raw ZIP is
        the full package, so its ``request`` never has ``layers``.
        """
        source = {"url": package.url, "teryt": package.teryt, "format": package.format}
        base = {**(extra or {}), "http": package.http}
        if package.raw_path is not None:
            self._write_sidecar(
                package.raw_path,
                request,
                self._without_layers(kwargs),
                extra={**base, "source": source},
            )
            source = {**source, "raw_file": package.raw_path.name}
        self._write_sidecar(
            package.path, request, kwargs, extra={**base, "source": source}
        )

    @staticmethod
    def _without_layers(kwargs: dict) -> dict:
        """``kwargs`` without the BDOT10k layer filter (the full package)."""
        return {k: v for k, v in kwargs.items() if k != "layers"}

    def download_batch(
        self,
        items: list[dict],
        max_workers: int = 4,
        **kwargs,
    ) -> list[Path]:
        """
        Download land cover data for multiple items in parallel.

        Each item dict should contain exactly one of: teryt, bbox, godlo.

        Parameters
        ----------
        items : list[dict]
            List of download items, each with one of:
            - {"teryt": "1465"}
            - {"bbox": BBox(...)}
            - {"godlo": "N-34-130-D"}
        max_workers : int, optional
            Maximum number of parallel download threads (default: 4).
            When <= 1, downloads sequentially.
        **kwargs
            Additional provider-specific options passed to each download.

        Returns
        -------
        list[Path]
            List of paths to successfully downloaded files.
            Failed items are logged but do not stop the batch.

        Examples
        --------
        >>> manager = LandCoverManager()
        >>> items = [
        ...     {"teryt": "1465"},
        ...     {"teryt": "1261"},
        ...     {"godlo": "N-34-130-D"},
        ... ]
        >>> paths = manager.download_batch(items, max_workers=2)
        """
        if not items:
            return []

        def _download_single(item: dict) -> Path | None:
            """Download a single item, returning path or None on failure."""
            try:
                return self.download(**item, **kwargs)
            except Exception as e:
                item_desc = str(item)
                logger.error(f"Batch download failed for {item_desc}: {e}")
                return None

        results: list[Path] = []

        if max_workers <= 1:
            # Sequential
            for item in items:
                path = _download_single(item)
                if path is not None:
                    results.append(path)
        else:
            # Parallel
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = {
                    executor.submit(_download_single, item): item for item in items
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        path = future.result()
                        if path is not None:
                            results.append(path)
                    except Exception as e:
                        item_desc = str(futures[future])
                        logger.error(
                            f"Unexpected error in batch download for {item_desc}: {e}"
                        )

        logger.info(f"Batch download complete: {len(results)}/{len(items)} successful")
        return results

    def _content_params(self, kwargs: dict | None = None) -> dict[str, object]:
        """Effective provider options that change the CONTENT of the result.

        Defaults are filled in, so the result is unambiguous without knowing
        them: SoilGrids ``property``/``depth``/``stat``, CORINE ``year``,
        BDOT10k ``format`` (and ``layers`` when a filter is given). Options
        that do not change the content (e.g. ``timeout``) are left out; an
        unknown provider gives ``{}``.

        The values go into the file name (`_generate_output_path`) and into
        the sidecar ``request`` (`_write_sidecar`) - one source for both.
        """
        kwargs = kwargs or {}
        provider = self._provider
        if isinstance(provider, SoilGridsProvider):
            return {
                "property": kwargs.get("property", provider.DEFAULT_PROPERTY),
                "depth": kwargs.get("depth", provider.DEFAULT_DEPTH),
                "stat": kwargs.get("stat", provider.DEFAULT_STAT),
            }
        if isinstance(provider, CorineProvider):
            return {"year": kwargs.get("year", provider.DEFAULT_YEAR)}
        if isinstance(provider, Bdot10kProvider):
            # Default of Bdot10kProvider.download_package (``format="GPKG"``).
            params: dict[str, object] = {"format": kwargs.get("format", "GPKG")}
            if kwargs.get("layers") is not None:
                params["layers"] = sorted(set(kwargs["layers"]))
            return params
        return {}

    def _generate_output_path(
        self,
        teryt: str | None,
        bbox: BBox | None,
        godlo: str | None,
        kwargs: dict | None = None,
    ) -> Path:
        """Generate the output path from the selection method and the options.

        Pattern: ``<source>[_<param>...]_<mode>_<id>.<ext>``, e.g.
        ``soilgrids_clay_0-5cm_mean_bbox_<coords>.tif``,
        ``corine_2018_godlo_N-34-130-D.tif``, ``bdot10k_teryt_1465.gpkg``,
        ``bdot10k_PTWP-SWRS_teryt_1465.gpkg`` (layer filter: codes joined
        with ``-``). Every option that changes the content of the result
        (`_content_params`) is part of the name, so different options never
        share a file and the same options always give the same path. The
        BDOT10k ``format`` is carried by the extension (the provider saves
        SHP as ``.zip``), CORINE without CLMS credentials saves ``.png``.
        BDOT10k by bbox/godlo goes through `_download_county`, so its name
        is always ``teryt_<T>``.
        """
        prefix = self._source_prefix()
        params = self._content_params(kwargs)
        tokens = [
            "-".join(v) if isinstance(v, list) else str(v)
            for k, v in params.items()
            if k != "format"
        ]

        if teryt:
            selection = f"teryt_{teryt}"
        elif bbox:
            selection = (
                f"bbox_{bbox.min_x:.0f}_{bbox.min_y:.0f}"
                f"_{bbox.max_x:.0f}_{bbox.max_y:.0f}"
            )
        else:
            selection = f"godlo_{godlo}"

        suffix = ".tif" if isinstance(self._provider, _RASTER_PROVIDERS) else ".gpkg"
        filename = "_".join([prefix, *tokens, selection]) + suffix
        return self._output_dir / filename

    def _source_prefix(self) -> str:
        """File name prefix: the registry key of the provider (``--source``)."""
        for key, cls in PROVIDERS.items():
            if isinstance(self._provider, cls):
                return key
        return self._provider.name.lower().replace(" ", "_")

    def _write_sidecar(
        self,
        data_path: Path,
        request: dict,
        kwargs: dict | None = None,
        extra: dict | None = None,
    ) -> None:
        """Best-effort write of the .meta.json sidecar (``emit_sidecar``, D7).

        ``extra`` (e.g. ``parent_request`` of a BDOT10k powiat file) is merged
        over the CORINE PNG fallback keys.
        """
        from kartograf.sources.sidecar import emit_sidecar

        horizontal_crs = None
        fallback = None
        # CORINE without CLMS credentials falls back to a PNG preview from WMS - a
        # different CRS than the one declared for the CLMS GeoTIFF channel (EPSG:3035).
        is_png = data_path.suffix.lower() == ".png"
        key = getattr(self._provider, "descriptor_key", None)
        if is_png and key == "eu.clms.corine":
            year = (kwargs or {}).get("year", 2018)
            # 1990 is the only DLR vintage (WMS DLR, EPSG:4326); the others
            # go through EEA Discomap (EPSG:3857) - see CorineProvider.EEA_YEARS.
            horizontal_crs = (
                "EPSG:4326" if year not in CorineProvider.EEA_YEARS else "EPSG:3857"
            )
            fallback = {"fallback": "wms_png", "note": "podglad WMS, nie dane"}
        merged = {**(fallback or {}), **(extra or {})} or None
        emit_sidecar(
            key,
            data_path,
            request={**request, **self._content_params(kwargs)},
            vertical_crs=getattr(self._provider, "vertical_crs", None),
            horizontal_crs=horizontal_crs,
            extra=merged,
            nodata=_read_geotiff_nodata(data_path),
        )

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
