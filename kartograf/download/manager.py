"""
Download manager for coordinating NMT data downloads.

This module provides the DownloadManager class for downloading
single sheets and entire hierarchies of map sheets.

Supports parallel downloads via ThreadPoolExecutor when max_workers > 1.
"""

import concurrent.futures
import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.campaigns import (
    CampaignRef,
    campaign_extension,
    validate_campaign_args,
    verify_file_format,
)
from kartograf.download.links import (
    LinkOutcome,
    ensure_standard_link,
    linked_campaign,
    write_standard_sidecar,
)
from kartograf.download.storage import FileStorage, storage_for_provider
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl import create_nmt_provider, nmt_vertical_crs
from kartograf.providers.pl.skorowidz import SkorowidzRecord

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """
    Progress information for download operations.

    Attributes
    ----------
    current : int
        Number of sheets processed so far
    total : int
        Total number of sheets to process
    godlo : str
        Current sheet being processed
    status : str
        Status of current operation ("downloading", "skipped", "completed",
        "failed", "no_coverage"). ``no_coverage`` is a sheet the source has
        no data for (``NoCoverageError``: sea, area beyond the border) — an
        expected outcome, not a transport failure; it is still listed in
        ``DownloadResult.failed`` (and ``no_coverage``).
    message : str
        Optional message with additional details
    """

    current: int
    total: int
    godlo: str
    status: str
    message: str = ""

    @property
    def progress_percent(self) -> float:
        """Return progress as percentage (0-100)."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100


@dataclass
class DownloadResult:
    """
    Result of a batch/hierarchy download operation.

    Attributes
    ----------
    succeeded : list[Path]
        Paths to successfully downloaded files
    failed : list[str]
        Godlo identifiers that failed to download
    skipped : list[str]
        Godlo identifiers that were skipped (already existed)
    no_coverage : list[str]
        Subset of ``failed``: sheets the source has no data for
        (``NoCoverageError``) — as opposed to a transport/service failure.
    campaign_files : dict[str, tuple[Path, ...]]
        Tor kampanii (ADR-030): godlo -> pliki kampanii pobrane w tym
        przebiegu i juz lokalne (dla udanych arkuszy). Tor bez kampanii: puste.
    copied : list[str]
        Godla, ktorych sciezka standardowa jest KOPIA pliku kampanii
        (symlink i hardlink niedostepne).
    reused_campaign_files : dict[str, tuple[Path, ...]]
        Podzbior ``campaign_files``: godlo -> pliki kampanii juz lokalne
        (nie pobrane w tym przebiegu). Tor bez kampanii: puste.
    unverified : dict[str, str]
        Podzbior ``skipped``: godlo -> blad transportu skorowidza GUGiK,
        przy ktorym ``newest`` uzyl lokalnej kampanii bez sprawdzenia
        nowszej (``SheetFetch.unverified``). Inaczej puste.

    Notes
    -----
    Populated by `download_hierarchy` and `download_sheets` (and so by
    `download_sheet` when it expands a coarser PL-1992 godlo) and exposed as
    `DownloadManager.last_result`.
    """

    succeeded: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    no_coverage: list[str] = field(default_factory=list)
    campaign_files: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    copied: list[str] = field(default_factory=list)
    reused_campaign_files: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    unverified: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Return total number of sheets processed."""
        return len(self.succeeded) + len(self.failed) + len(self.skipped)

    @property
    def all_paths(self) -> list[Path]:
        """Return paths of successfully downloaded files."""
        return list(self.succeeded)

    @property
    def hard_failures(self) -> list[str]:
        """``failed`` minus ``no_coverage``: transport/service failures only.

        These are the sheets worth retrying — a sheet the source has no
        data for stays missing no matter how often it is requested.
        """
        no_data = set(self.no_coverage)
        return [g for g in self.failed if g not in no_data]


@dataclass(frozen=True)
class SheetFetch:
    """Wynik pobrania jednego arkusza (``DownloadManager.last_sheet``).

    Attributes
    ----------
    godlo : str
        Arkusz.
    path : Path
        Sciezka standardowa (tor kampanii — dowiazanie) albo plik (tor bez
        kampanii).
    skipped : bool
        Nic nie pobrano w tym wywolaniu (wszystko juz lokalnie).
    downloaded : tuple[Path, ...]
        Pliki kampanii pobrane teraz.
    reused : tuple[Path, ...]
        Pliki kampanii juz lokalne.
    link : str or None
        ``symlink``/``hardlink``/``copy``; ``None`` = tor bez kampanii.
    unverified : str or None
        ``newest``: tresc bledu TRANSPORTU skorowidza GUGiK (siec, 429, 5xx),
        przy ktorym uzyto istniejacej lokalnej kampanii bez sprawdzenia, czy
        jest nowsza (``skipped=True``, dowiazanie nietkniete). ``None`` =
        rekord rozwiazany normalnie.
    """

    godlo: str
    path: Path
    skipped: bool
    downloaded: tuple[Path, ...] = ()
    reused: tuple[Path, ...] = ()
    link: str | None = None
    unverified: str | None = None


class CampaignProvider(Protocol):
    """API kampanii providera GUGiK (ADR-030; mechanizm WYLACZNIE PL).

    ``BaseProvider`` go nie deklaruje — manager wybiera tor kampanii po
    ``supports_campaigns is True`` i rzutuje providera na ten protokol.
    """

    def resolve_campaigns(
        self, godlo: str, *, campaigns: str = "newest", min_year: int | None = None
    ) -> list[SkorowidzRecord]: ...

    def download_record(self, record: SkorowidzRecord, output_path: Path) -> Path: ...

    def record_source(self, record: SkorowidzRecord) -> dict: ...


# Type alias for progress callback
ProgressCallback = Callable[[DownloadProgress], None]


def _is_transport_failure(error: DownloadError) -> bool:
    """Blad TRANSPORTU (siec, 429, 5xx) wg polityki ``transport/http.py``.

    ``status_code`` niesie kod HTTP ostatniej proby (``http_failure``): 429
    i 5xx = transport, inne 4xx nie. Bez kodu rozstrzyga przyczyna
    (``get_with_retry`` rzuca ``... from`` wyjatku ``requests``): blad
    sieci/timeout. Brak pokrycia (``NoCoverageError``) i bledy tresci
    odpowiedzi (raport OGC, zly szablon, XML) nie maja ani kodu, ani
    przyczyny z ``requests`` — nie sa transportem.
    """
    if error.status_code is not None:
        return error.status_code == 429 or error.status_code >= 500
    return isinstance(error.__cause__, requests.RequestException)


class DownloadManager:
    """
    Manages downloading of NMT data sheets.

    Coordinates between the provider (data source), storage (file system),
    and sheet parser to download single sheets or entire hierarchies.

    Two download modes:
    - By godło: downloads ASC files from OpenData
    - By bbox: downloads GeoTIFF from WCS (1m and KRON86 only — GUGiK withdrew
      the EVRF2007 WCS endpoint; for EVRF2007 heights of an area use sheets or
      ``kartograf.download_pl_cutout``)

    Supports vertical CRS:
    - EVRF2007 (default) - European Vertical Reference Frame 2007
    - KRON86 - legacy Kronsztadt 86

    Supports resolutions:
    - 1m (default) - high resolution, available for both EVRF2007 and KRON86
    - 5m - lower resolution, available only for EVRF2007

    Attributes
    ----------
    last_result : DownloadResult or None
        Per-sheet outcome of the most recent multi-sheet download. Reset to
        None at the start of each `download_sheet` / `download_hierarchy` /
        `download_sheets` call; set by `download_hierarchy` and
        `download_sheets` (and so by `download_sheet` when it expands a
        coarser PL-1992 godlo). A single sheet downloaded directly via
        `download_sheet` (a 1:10000 or PL-2000 godlo) leaves it None;
        `download_bbox` does not touch it.
    last_sheet : SheetFetch or None
        Wynik pojedynczego arkusza pobranego bezposrednio przez
        `download_sheet` (1:10000 albo PL-2000). Zerowany (None) na starcie
        kazdego `download_sheet` / `download_hierarchy` / `download_sheets`
        (wyjatek nie zostawia starego wyniku); None po rozwinieciu do
        hierarchii i po liscie arkuszy.

    Examples
    --------
    >>> manager = DownloadManager(output_dir="./data")
    >>>
    >>> # Download single sheet (ASC)
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    PosixPath('data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc')
    >>>
    >>> # Download hierarchy (ASC)
    >>> manager.download_hierarchy("N-34-130-D", "1:10000")
    >>>
    >>> # Download by bounding box (GeoTIFF, WCS) - only 1m and KRON86
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> kron = DownloadManager(output_dir="./data", vertical_crs="KRON86")
    >>> kron.download_bbox(bbox, "area.tif")
    >>>
    >>> # Download in legacy KRON86 vertical CRS
    >>> manager = DownloadManager(vertical_crs="KRON86")
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    >>>
    >>> # Download 5m resolution (only EVRF2007)
    >>> manager = DownloadManager(resolution="5m")
    >>> manager.download_sheet("N-34-130-D-d-2-4")
    """

    def __init__(
        self,
        output_dir: str | Path = "./data",
        provider: BaseProvider | None = None,
        storage: FileStorage | None = None,
        vertical_crs: str = "EVRF2007",
        resolution: str = "1m",
        max_workers: int = 1,
        sidecar_extra: dict | None = None,
        campaigns: str = "newest",
        min_year: int | None = None,
    ):
        """
        Initialize download manager.

        Parameters
        ----------
        output_dir : str or Path, optional
            Base directory for downloads (default: "./data")
        provider : BaseProvider, optional
            Data provider (default: GugikProvider with specified settings)
        storage : FileStorage, optional
            Storage manager (default: FileStorage whose subdirectory comes
            from the provider's source descriptor
            (`resolve_subdir(vertical_crs=...)`, `{uklad}` resolved per godlo),
            falling back to `resolution` when the provider has no
            `descriptor_key`; the provider's `storage_variant`, e.g. orto CIR,
            is appended as `_<variant>`)
        vertical_crs : str, optional
            Vertical CRS: "EVRF2007" or "KRON86" (default: "EVRF2007").
            Note: 5m resolution only supports EVRF2007.
        resolution : str, optional
            Grid resolution: "1m" or "5m" (default: "1m").
            Note: 5m is only available for EVRF2007 and does not support
            bbox download (WCS).
        max_workers : int, optional
            Maximum number of parallel download threads (default: 1).
            When 1, downloads are sequential (backward compatible).
            When > 1, uses ThreadPoolExecutor for parallel downloads.
        sidecar_extra : dict, optional
            Dodatkowe pola scalane do `extra` kazdego sidecara (etap 1:
            `parent_request` w trybie bbox/geometry).
        campaigns : str, optional
            Strategia kampanii ADR-030: ``"newest"`` (domyslnie) albo
            ``"all"``. Dotyczy tylko providera z ``supports_campaigns is
            True`` (GUGiK NMT/NMPT/orto).
        min_year : int, optional
            Dolna granica roku ``aktualnosc`` kampanii (obie strategie).

        Raises
        ------
        ValidationError
            Nieznana strategia / niepoprawny ``min_year`` albo provider bez
            kampanii z ``campaigns="all"`` lub ``min_year``.
        """
        validate_campaign_args(campaigns, min_year)
        # Regula "5m => EVRF2007" zyje w fabryce (`nmt_vertical_crs`, D11);
        # bez providera koryguje (i loguje) fabryka.
        self._provider = provider or create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution
        )
        # The provider is the authority on the vertical CRS actually delivered:
        # `DownloadManager(provider=GugikProvider(vertical_crs="KRON86"))` used
        # to write into a `..._evrf2007` segment next to a sidecar declaring
        # EPSG:9650 (sidecars already read the provider, see `_write_sidecar`).
        # isinstance(str), not `is not None`: for Mock(spec=Provider) the
        # attribute yields a Mock, which must not reach the segment template.
        provider_vertical_crs = getattr(self._provider, "vertical_crs", None)
        if isinstance(provider_vertical_crs, str):
            vertical_crs = provider_vertical_crs
        else:
            vertical_crs = nmt_vertical_crs(resolution, vertical_crs)
        if storage is None:
            storage = storage_for_provider(
                output_dir,
                self._provider,
                resolution=resolution,
                vertical_crs=vertical_crs,
            )
        self._storage = storage
        self._vertical_crs = vertical_crs
        self._resolution = resolution
        self._default_ext = self._provider.default_extension
        self._max_workers = max(1, max_workers)
        self._sidecar_extra = sidecar_extra
        # `is True`, nie prawdziwosc: Mock/Mock(spec=...) daje Mock -> tor plain.
        self._campaign_aware = (
            getattr(self._provider, "supports_campaigns", False) is True
        )
        if not self._campaign_aware and (campaigns != "newest" or min_year is not None):
            raise ValidationError(
                f"Provider {self._provider.name} nie obsluguje kampanii "
                f"(--campaigns/--min-year)"
            )
        self._campaigns = campaigns
        self._min_year = min_year
        self.last_result: DownloadResult | None = None
        self.last_sheet: SheetFetch | None = None

    @property
    def vertical_crs(self) -> str:
        """Return current vertical CRS."""
        return self._vertical_crs

    @property
    def resolution(self) -> str:
        """Return current resolution."""
        return self._resolution

    @property
    def campaigns(self) -> str:
        """Strategia kampanii (``newest``/``all``)."""
        return self._campaigns

    @property
    def min_year(self) -> int | None:
        """Dolna granica roku kampanii (``None`` = bez granicy)."""
        return self._min_year

    @property
    def provider(self) -> BaseProvider:
        """Return the data provider."""
        return self._provider

    @property
    def storage(self) -> FileStorage:
        """Return the storage manager."""
        return self._storage

    @property
    def _campaign_provider(self) -> CampaignProvider:
        """Provider toru kampanii (``supports_campaigns is True``, GUGiK)."""
        return cast(CampaignProvider, self._provider)

    # =========================================================================
    # Download by godło → ASC
    # =========================================================================

    def download_sheet(
        self,
        godlo: str,
        skip_existing: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> Path | list[Path]:
        """
        Download a map sheet as ASC.

        For sheets at scale 1:10000, downloads a single file.
        For coarser scales (e.g. 1:25000, 1:50000), automatically expands
        to all descendant 1:10000 sheets via download_hierarchy().

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        skip_existing : bool, optional
            Skip download if file exists (default: True)
        on_progress : callable, optional
            Callback function for progress updates (used when expanding hierarchy).

        Returns
        -------
        Path or list[Path]
            Path to the downloaded ASC file (for 1:10000),
            or list of paths (for coarser scales expanded to 1:10000)

        Raises
        ------
        DownloadError
            If download fails
        ParseError
            If godlo is invalid

        Notes
        -----
        `self.last_result` is reset to None at the start of the call and set
        only by the expansion to 1:10000 (via `download_hierarchy`), so a
        single sheet downloaded here directly (a 1:10000 or PL-2000 godlo)
        leaves it None and never exposes the previous run's result.
        `self.last_sheet` is reset the same way and set (``SheetFetch``) only
        for a single sheet downloaded directly.
        """
        # Wynik poprzedniego przebiegu nie moze przeciec do tego wywolania.
        # Reset jest idempotentny — rozwiniecie do hierarchii zeruje go ponownie.
        self.last_result = None
        self.last_sheet = None

        parser = SheetParser(godlo)

        # PL-2000 godła are always downloaded directly (individual files on GUGiK)
        # PL-1992 coarser than 1:10000 must be expanded to 1:10000 descendants
        if parser.uklad != "2000" and parser.scale != "1:10000":
            return self.download_hierarchy(
                godlo, "1:10000", skip_existing=skip_existing, on_progress=on_progress
            )

        fetch = self._fetch_sheet(godlo, skip_existing)
        self.last_sheet = fetch
        return fetch.path

    def download_hierarchy(
        self,
        godlo: str,
        target_scale: str,
        skip_existing: bool = True,
        on_progress: ProgressCallback | None = None,
        max_workers: int | None = None,
    ) -> list[Path]:
        """
        Download all descendant sheets to target scale as ASC.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier (e.g., "N-34-130-D")
        target_scale : str
            Target scale to download (e.g., "1:10000")
        skip_existing : bool, optional
            Skip download if file exists (default: True)
        on_progress : callable, optional
            Callback function for progress updates.
        max_workers : int, optional
            Maximum parallel download threads. If None, uses instance default.
            When <= 1, downloads sequentially (backward compatible).

        Returns
        -------
        list[Path]
            List of paths to downloaded ASC files

        Raises
        ------
        ValidationError
            If target_scale is invalid
        ParseError
            If godlo is invalid

        Notes
        -----
        Per-sheet `DownloadError` failures (incl. `NoCoverageError`) do not
        raise; they are collected in `self.last_result.failed` (see
        `DownloadResult`). Any other exception from a sheet (e.g. `OSError`
        while writing it) propagates and stops the download when running
        sequentially (`max_workers <= 1`); with parallel workers it is
        collected in `failed` like a download error. The returned list
        contains downloaded AND skipped (pre-existing) files.
        `self.last_result` is reset to None at the start of the call and set
        when the download completes (`download_sheets` works the same way),
        so a call that raises never leaves the previous run's result behind.

        Examples
        --------
        >>> manager = DownloadManager()
        >>> paths = manager.download_hierarchy("N-34-130-D-d", "1:10000")
        >>> len(paths)  # 4 * 4 = 16 sheets
        16
        """
        # Wynik poprzedniego przebiegu nie moze przeciec do tego wywolania —
        # kasujemy go, zanim cokolwiek moze rzucic (ParseError/ValidationError).
        self.last_result = None
        self.last_sheet = None

        # Parse starting sheet and get all descendants
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)

        total = len(descendants)
        workers = max_workers if max_workers is not None else self._max_workers

        logger.info(
            f"Starting hierarchy download: {godlo} → {target_scale} "
            f"({total} sheets, workers={workers})"
        )

        return self._download_many(
            [d.godlo for d in descendants], skip_existing, on_progress, workers
        )

    @staticmethod
    def expand_sheets(godla: list[str]) -> list[str]:
        """
        Leaf sheets actually requested from the provider for a list of godla.

        PL-1992 godla coarser than 1:10000 expand to their 1:10000
        descendants (like :meth:`download_sheet`); 1:10000 and PL-2000 godla
        stay as they are. Identifiers are normalized, duplicates dropped,
        first-seen order kept.

        Raises
        ------
        ParseError
            If any godlo is invalid
        """
        leaves: list[str] = []
        seen: set[str] = set()
        for godlo in godla:
            parser = SheetParser(godlo)
            if parser.uklad != "2000" and parser.scale != "1:10000":
                expanded = [d.godlo for d in parser.get_all_descendants("1:10000")]
            else:
                expanded = [parser.godlo]
            for leaf in expanded:
                if leaf not in seen:
                    seen.add(leaf)
                    leaves.append(leaf)
        return leaves

    def download_sheets(
        self,
        godla: list[str],
        skip_existing: bool = True,
        on_progress: ProgressCallback | None = None,
        max_workers: int | None = None,
    ) -> list[Path]:
        """
        Download a list of sheets (see :meth:`expand_sheets`).

        Unlike calling :meth:`download_sheet` in a loop, per-sheet download
        failures (``DownloadError``) do not raise: they are collected in
        ``self.last_result`` exactly like in :meth:`download_hierarchy`
        (``failed``; ``no_coverage`` for sheets the source has no data for;
        other exceptions as described in its Notes).

        Returns
        -------
        list[Path]
            Downloaded AND skipped (pre-existing) files

        Raises
        ------
        ParseError
            If any godlo is invalid — raised before any download starts
        """
        self.last_result = None
        self.last_sheet = None
        leaves = [SheetParser(g) for g in self.expand_sheets(godla)]
        total = len(leaves)
        workers = max_workers if max_workers is not None else self._max_workers
        logger.info(f"Starting sheet list download: {total} sheets, workers={workers}")
        return self._download_many(
            [leaf.godlo for leaf in leaves], skip_existing, on_progress, workers
        )

    def _fetch_sheet(
        self,
        godlo: str,
        skip_existing: bool,
        on_download: Callable[[], None] | None = None,
    ) -> SheetFetch:
        """
        Pobierz jeden arkusz — jedyna tresc "pobierz arkusz" (D10).

        Provider z kampaniami (``supports_campaigns is True``) idzie torem
        kampanii (``_fetch_campaigns``), kazdy inny — dzisiejszym torem
        (``_fetch_sheet_plain``). ``on_download`` jest wolany tuz przed
        pierwszym pobraniem (tryb sekwencyjny raportuje ``"downloading"``).
        """
        if self._campaign_aware:
            return self._fetch_campaigns(godlo, skip_existing, on_download)
        return self._fetch_sheet_plain(godlo, skip_existing, on_download)

    def _fetch_sheet_plain(
        self,
        godlo: str,
        skip_existing: bool,
        on_download: Callable[[], None] | None = None,
    ) -> SheetFetch:
        """
        Tor bez kampanii (atrapy, obce providery) — zachowanie sprzed ADR-030.

        Sciezka z ``FileStorage``; istniejacy plik przy ``skip_existing``
        jest pomijany (i notowany w sidecarze, N4); inaczej provider pobiera
        plik, a manager pisze sidecar (best-effort). Wyjatki providera
        wylatuja bez zmian.
        """
        target_path = self._storage.get_path(godlo, self._default_ext)
        if skip_existing and target_path.exists():
            logger.info(f"Skipping {godlo} - already exists at {target_path}")
            self._note_reuse(target_path)
            return SheetFetch(godlo, target_path, skipped=True)
        if on_download is not None:
            on_download()
        logger.info(f"Downloading {godlo}...")
        path = self._provider.download(godlo, target_path)
        self._write_sidecar(path, {"godlo": godlo})
        return SheetFetch(godlo, path, skipped=False)

    def _fetch_campaigns(
        self,
        godlo: str,
        skip_existing: bool,
        on_download: Callable[[], None] | None = None,
    ) -> SheetFetch:
        """
        Tor kampanii (ADR-030): pliki w ``kampanie/``, dowiazanie standardowe.

        Rekordy z ``provider.resolve_campaigns`` (pusta lista nigdy — brak
        = ``NoCoverageError``). Dla kazdej kampanii: rozszerzenie z pola
        ``format`` rekordu (PRZED siecia), pominiecie istniejacego pliku
        kampanii przy ``skip_existing`` (istnienie sciezki standardowej NIE
        jest powodem pominiecia), inaczej ``download_record`` ->
        ``verify_file_format`` -> obowiazkowy sidecar kampanii; porazka
        ktoregokolwiek z tych krokow usuwa plik danych (nigdy plik bez
        sidecara albo z obca trescia). Po zebraniu kampanii sciezka
        standardowa wskazuje najnowsza LOKALNA kampanie (``max`` po
        ``sort_key``; ``ensure_standard_link`` nigdy nie cofa dowiazania).
        Istniejacy plik kampanii BEZ sidecara (R22: przerwanie przed jego
        zapisem) przechodzi ``verify_file_format`` przed odtworzeniem
        sidecara; niezgodna tresc = plik usuniety + porazka kampanii.

        Wspolbieznosc: dowiazanie jest ustawiane RAZ na arkusz, po zebraniu
        wszystkich jego kampanii, a ``expand_sheets`` deduplikuje godla —
        jeden arkusz = jeden watek. Bezpieczenstwo w jednym wywolaniu
        managera wynika wiec ze struktury, nie z blokady (blokad nie ma);
        wyscig miedzy procesami opisuje ``ensure_standard_link``.

        Awaria skorowidza (I-1): ``newest`` bez ``min_year`` przy
        ``skip_existing``, gdy ``resolve_campaigns`` konczy sie bledem
        TRANSPORTU (``_is_transport_failure``), a sciezka standardowa wskazuje
        istniejaca lokalna kampanie (``linked_campaign``) — NIE porazka:
        ``logger.warning`` i ``SheetFetch(skipped=True, unverified=<blad>)``
        z lokalnej kampanii, dowiazanie bez zmian. ``all``, ``min_year``,
        ``--force``, brak lokalnej kampanii albo inny blad — wyjatek jak dotad.

        Raises
        ------
        NoCoverageError
            Brak kampanii (z ``resolve_campaigns``).
        DownloadError
            Porazka choc jednej kampanii (takze niepoprawna ``aktualnosc``
            rekordu) albo dowiazania (``OSError`` z ``ensure_standard_link``)
            — wszystko w jednym komunikacie; kampanie udane zostaja na dysku,
            a dowiazanie wskazuje najnowsza z nich.
        """
        std = self._storage.get_path(godlo, self._default_ext)
        try:
            records = self._campaign_provider.resolve_campaigns(
                godlo, campaigns=self._campaigns, min_year=self._min_year
            )
        except DownloadError as e:
            if (
                self._campaigns == "newest"
                and self._min_year is None
                and skip_existing
                and _is_transport_failure(e)
            ):
                fetch = self._local_newest(godlo, std, e)
                if fetch is not None:
                    return fetch
            raise
        logger.info("%s: %d kampanii (%s)", godlo, len(records), self._campaigns)
        downloaded: list[Path] = []
        reused: list[Path] = []
        local: list[tuple[CampaignRef, Path]] = []
        errors: list[tuple[str, DownloadError]] = []  # (kampania, blad)
        started = False
        for record in records:
            try:  # R16 (w duchu Q10): zla aktualnosc = porazka tej kampanii
                ref = CampaignRef.from_record(record)
            except DownloadError as e:
                errors.append((record.url, e))
                continue
            try:
                ext = campaign_extension(ref, self._default_ext)  # przed siecia
            except DownloadError as e:
                errors.append((ref.dirname, e))
                continue
            path = self._storage.get_campaign_path(godlo, ref, ext)
            if skip_existing and path.exists():
                if path.with_name(path.name + ".meta.json").exists():
                    self._note_reuse(path)
                else:  # R22: proces przerwany przed sidecarem — odtworz
                    try:  # tresc niesprawdzona (przerwanie przed weryfikacja)
                        verify_file_format(path, ext)
                    except DownloadError as e:
                        path.unlink(missing_ok=True)
                        errors.append((ref.dirname, e))
                        continue
                    try:
                        self._write_campaign_sidecar(path, godlo, record, ref)
                    except DownloadError as e:
                        errors.append(
                            (ref.dirname, e)
                        )  # plik zostaje (sprzed przebiegu)
                        continue
                logger.info(f"Skipping {godlo} {ref.dirname} - already exists")
                reused.append(path)
                local.append((ref, path))
                continue
            if on_download is not None and not started:
                on_download()
                started = True
            logger.info(f"Downloading {godlo} {ref.dirname}...")
            try:
                self._campaign_provider.download_record(record, path)
                verify_file_format(path, ext)
                self._write_campaign_sidecar(path, godlo, record, ref)
            except DownloadError as e:
                path.unlink(missing_ok=True)
                errors.append((ref.dirname, e))
                continue
            downloaded.append(path)
            local.append((ref, path))  # kandydat dowiazania DOPIERO z sidecarem
        method: str | None = None
        link_error: OSError | None = None
        if local:
            ref, path = max(local, key=lambda rp: rp[0].sort_key)
            try:
                outcome = ensure_standard_link(
                    std, path, ref.sort_key, refresh=path in downloaded
                )
            except OSError as e:  # R5: porazka arkusza, nie przerwanie listy
                link_error = e
            else:
                method = outcome.method
                if not outcome.changed:
                    self._note_standard_reuse(std, outcome)
        if errors or link_error is not None:  # Q10: pelna lista porazek
            problems = []
            if errors:
                listing = ", ".join(f"{name}: {e}" for name, e in errors)
                problems.append(
                    f"nie pobrano {len(errors)} z {len(records)} kampanii ({listing})"
                )
            if link_error is not None:
                problems.append(f"dowiazanie {std}: {link_error}")
            raise DownloadError(f"{godlo}: " + "; ".join(problems), godlo=godlo)
        return SheetFetch(
            godlo,
            std,
            skipped=not downloaded,
            downloaded=tuple(downloaded),
            reused=tuple(reused),
            link=method,
        )

    def _note_standard_reuse(self, std: Path, outcome: LinkOutcome) -> None:
        """Dowiazanie bez zmian: sidecar standardowy jako zwykly plik + N4."""
        std_sidecar = std.with_name(std.name + ".meta.json")
        if std_sidecar.is_symlink():  # nigdy zapis "przez" dowiazanie
            write_standard_sidecar(std, outcome.target, outcome.method)
        self._note_reuse(std)

    def _local_newest(
        self, godlo: str, std: Path, error: DownloadError
    ) -> SheetFetch | None:
        """I-1: lokalna kampania ``newest``, gdy skorowidz GUGiK niedostepny.

        ``None`` = brak lokalnej kampanii (brak pliku, wiszace dowiazanie,
        stary zwykly plik) — wolajacy zglasza pierwotny blad. Dowiazanie NIE
        jest przestawiane: ``ensure_standard_link`` z biezacym celem i
        najnizszym kluczem zwraca je bez zmian (odtwarza najwyzej brakujacy
        sidecar standardowy).
        """
        target = linked_campaign(std)
        if target is None:
            return None
        try:
            outcome = ensure_standard_link(std, target, ("", "", ""))
        except OSError:
            return None
        logger.warning(
            f"{godlo}: skorowidz GUGiK niedostepny ({error}) — uzyto lokalnej "
            f"kampanii {outcome.target} bez sprawdzenia nowszej"
        )
        self._note_reuse(outcome.target)
        self._note_standard_reuse(std, outcome)
        return SheetFetch(
            godlo,
            std,
            skipped=True,
            reused=(outcome.target,),
            link=outcome.method,
            unverified=str(error),
        )

    def _download_single_sheet_task(
        self,
        godlo: str,
        skip_existing: bool,
        on_download: Callable[[], None] | None = None,
    ) -> tuple[str, SheetFetch | None, str, str]:
        """
        Pobierz arkusz listy: ``DownloadError`` -> status zamiast wyjatku.

        Wspolne dla trybu sekwencyjnego i rownoleglego. Inny wyjatek (np.
        ``OSError`` zapisu) wylatuje: sekwencyjnie przerywa liste, w puli
        watkow lapie go ``_download_many`` jako ``"failed"``.

        Returns
        -------
        tuple[str, SheetFetch | None, str, str]
            (godlo, fetch_or_none, status, message)
            status is one of: "skipped", "completed", "failed", "no_coverage"
        """
        try:
            fetch = self._fetch_sheet(godlo, skip_existing, on_download)
        except NoCoverageError as e:
            logger.warning(f"No data for {godlo}: {e}")
            return (godlo, None, "no_coverage", str(e))
        except DownloadError as e:
            logger.error(f"Failed to download {godlo}: {e}")
            return (godlo, None, "failed", str(e))
        if fetch.skipped:
            return (godlo, fetch, "skipped", "Already exists")
        return (godlo, fetch, "completed", "")

    @staticmethod
    def _record(
        result: DownloadResult,
        paths: list[Path],
        godlo: str,
        fetch: SheetFetch | None,
        status: str,
    ) -> None:
        """Wpisz wynik jednego arkusza do ``DownloadResult`` i listy sciezek."""
        if status in ("completed", "skipped") and fetch is not None:
            if status == "skipped":
                result.skipped.append(godlo)
            else:
                result.succeeded.append(fetch.path)
            paths.append(fetch.path)
            if fetch.downloaded or fetch.reused:
                result.campaign_files[godlo] = fetch.downloaded + fetch.reused
                result.reused_campaign_files[godlo] = fetch.reused
            if fetch.link == "copy":
                result.copied.append(godlo)
            if fetch.unverified is not None:
                result.unverified[godlo] = fetch.unverified
        elif status in ("failed", "no_coverage"):
            # R5: brak danych u zrodla — porazka listy, ale rozpoznawalna
            result.failed.append(godlo)
            if status == "no_coverage":
                result.no_coverage.append(godlo)

    @staticmethod
    def _emit(
        on_progress: ProgressCallback | None,
        current: int,
        total: int,
        godlo: str,
        status: str,
        message: str = "",
    ) -> None:
        """Jedno miejsce budowy ``DownloadProgress`` dla obu trybow."""
        if on_progress:
            on_progress(
                DownloadProgress(
                    current=current,
                    total=total,
                    godlo=godlo,
                    status=status,
                    message=message,
                )
            )

    def _download_many(
        self,
        godla: list[str],
        skip_existing: bool,
        on_progress: ProgressCallback | None,
        workers: int,
    ) -> list[Path]:
        """Pobierz liste arkuszy (``workers <= 1`` sekwencyjnie, inaczej pula).

        Oba tryby wolaja ``_download_single_sheet_task`` i raportuja przez
        ``_emit``/``_record``. Sekwencyjny dodatkowo zglasza ``"downloading"``
        przed kazdym pobraniem i przepuszcza wyjatki spoza ``DownloadError``;
        rownolegly (kolejnosc ukonczenia) liczy je jako ``"failed"``.
        """
        downloaded_paths: list[Path] = []
        result = DownloadResult()
        total = len(godla)

        if workers <= 1:
            for i, godlo in enumerate(godla, 1):

                def started(i: int = i, godlo: str = godlo) -> None:
                    self._emit(on_progress, i, total, godlo, "downloading")

                _, fetch, status, message = self._download_single_sheet_task(
                    godlo, skip_existing, on_download=started
                )
                self._record(result, downloaded_paths, godlo, fetch, status)
                self._emit(on_progress, i, total, godlo, status, message)
        else:
            lock = threading.Lock()
            counter = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_godlo = {
                    executor.submit(
                        self._download_single_sheet_task, godlo, skip_existing
                    ): godlo
                    for godlo in godla
                }
                for future in concurrent.futures.as_completed(future_to_godlo):
                    godlo = future_to_godlo[future]
                    try:
                        godlo, fetch, status, message = future.result()
                    except Exception as e:
                        logger.error(f"Unexpected error downloading {godlo}: {e}")
                        fetch, status, message = None, "failed", str(e)
                    with lock:
                        counter += 1
                        current = counter
                        self._record(result, downloaded_paths, godlo, fetch, status)
                    self._emit(on_progress, current, total, godlo, status, message)

        self.last_result = result
        logger.info(
            f"Hierarchy download complete: {len(result.succeeded)} downloaded, "
            f"{len(result.skipped)} skipped, {len(result.failed)} failed (of {total})"
        )
        return downloaded_paths

    # =========================================================================
    # Download by bbox → GeoTIFF
    # =========================================================================

    def download_bbox(
        self,
        bbox: BBox,
        filename: str,
        format: str = "GTiff",
    ) -> Path:
        """
        Download NMT data for a bounding box as GeoTIFF.

        Use this method when you need data for an arbitrary area
        (not aligned to standard map sheets).

        Note: WCS download is only available for 1m resolution and KRON86
        heights (GUGiK withdrew the EVRF2007 WCS endpoint). For 5m, or for
        EVRF2007 heights, use download_sheet() with a godło instead, or
        ``kartograf.download_pl_cutout`` for one GeoTIFF built from sheets.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        filename : str
            Output filename (will be placed in output_dir)
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If download fails
        ValueError
            If format is not supported, bbox CRS is wrong, or resolution is 5m
        ValidationError
            If the provider refuses the request before going out to the
            network - today: EVRF2007 heights, whose WCS endpoint GUGiK
            withdrew (see ``GugikProvider.download_bbox``)

        Examples
        --------
        >>> manager = DownloadManager(output_dir="./data", vertical_crs="KRON86")
        >>> bbox = BBox(
        ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        ... )
        >>> path = manager.download_bbox(bbox, "my_area.tif")
        """
        output_path = self._storage.output_dir / filename

        logger.info(f"Downloading bbox to {output_path}...")
        result = self._provider.download_bbox(bbox, output_path, format=format)
        self._write_sidecar(
            result,
            {
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
        )
        return result

    # =========================================================================
    # Utility methods
    # =========================================================================

    def get_missing_sheets(
        self,
        godlo: str,
        target_scale: str,
    ) -> list[str]:
        """
        Get list of sheets that haven't been downloaded yet.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier
        target_scale : str
            Target scale to check

        Returns
        -------
        list[str]
            List of godło identifiers for missing sheets
        """
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)

        missing = []
        for descendant in descendants:
            if not self._storage.exists(descendant.godlo, self._default_ext):
                missing.append(descendant.godlo)

        return missing

    def count_sheets(self, godlo: str, target_scale: str) -> int:
        """
        Count total number of sheets in hierarchy.

        Parameters
        ----------
        godlo : str
            Starting map sheet identifier
        target_scale : str
            Target scale to count

        Returns
        -------
        int
            Number of sheets
        """
        parser = SheetParser(godlo)
        descendants = parser.get_all_descendants(target_scale)
        return len(descendants)

    def _write_sidecar(
        self,
        data_path: Path,
        request: dict,
        *,
        extra_override: dict | None = None,
        required: bool = False,
    ) -> None:
        """Zapis sidecara .meta.json; domyslnie best-effort (blad nie przerywa
        pobrania).

        Dla zadania z ``godlo`` dopisuje ``extra.source`` — pochodzenie pliku
        wg ``provider.source_info(godlo)`` (rekord skorowidza GUGiK: URL,
        warstwa, aktualnosc; D5). Tylko ``dict`` trafia do sidecara: provider
        bez pochodzenia zwraca ``None``, a ``Mock(spec=...)`` — ``Mock``.
        ``extra_override`` (sidecar kampanii) zastepuje ``source_info``:
        jego pola sa scalane do ``extra`` po ``sidecar_extra``.
        ``required=True`` = sidecar obowiazkowy (``emit_sidecar`` rzuca
        ``DownloadError``, gdy nie powstal).
        """
        from kartograf.sources.sidecar import emit_sidecar

        extra = dict(self._sidecar_extra) if self._sidecar_extra else {}
        if extra_override is not None:
            extra.update(extra_override)
        else:
            godlo = request.get("godlo")
            source_info = getattr(self._provider, "source_info", None)
            if godlo is not None and callable(source_info):
                source = source_info(godlo)
                if isinstance(source, dict):
                    extra["source"] = source
        emit_sidecar(
            getattr(self._provider, "descriptor_key", None),
            data_path,
            request=request,
            vertical_crs=getattr(self._provider, "vertical_crs", None),
            extra=extra or None,
            required=required,
        )

    def _write_campaign_sidecar(
        self, path: Path, godlo: str, record: SkorowidzRecord, ref: CampaignRef
    ) -> None:
        """OBOWIAZKOWY sidecar pliku kampanii (errata 2 N-1).

        ``request = {godlo, campaigns}`` + ``min_year`` tylko gdy podany;
        ``extra`` = ``sidecar_extra`` + ``source`` (``provider.record_source``
        TEGO rekordu, R13) + ``campaign`` (``ref.to_extra()``). Porazka =
        ``DownloadError`` (wolajacy usuwa plik danych).
        """
        request: dict = {"godlo": godlo, "campaigns": self._campaigns}
        if self._min_year is not None:
            request["min_year"] = self._min_year
        try:
            source = self._campaign_provider.record_source(record)
        except Exception as e:  # noqa: BLE001 — sidecar obowiazkowy: porazka kampanii
            raise DownloadError(
                f"Nie udalo sie zapisac obowiazkowego sidecara kampanii "
                f"{ref.dirname}: {e}",
                godlo=godlo,
            ) from e
        self._write_sidecar(
            path,
            request,
            extra_override={"source": source, "campaign": ref.to_extra()},
            required=True,
        )

    def _note_reuse(self, data_path: Path) -> None:
        """Dopisz biezace zadanie do sidecara arkusza POMINIETEGO (N4, best-effort).

        ``extra.parent_request`` to zadanie, ktore plik POBRALO (bez zmian —
        ``downloaded_at`` zostaje prawdziwe); kolejne zadania obszarowe, ktore
        arkusz reuzyly z cache, laduja w liscie ``extra.parent_requests``
        (bez duplikatow; zadanie rowne ``parent_request`` nie jest dopisywane).
        Konsument szuka ``parent_request == R or R in parent_requests``.
        Bez sidecara (cache sprzed 0.7.0) nic nie powstaje — sidecar z
        niepewna data i bez ``extra.source`` bylby zmyslaniem. Zapis przez plik
        tymczasowy + ``os.replace`` (dwa procesy nad tym samym arkuszem).
        """
        request = (self._sidecar_extra or {}).get("parent_request")
        if request is None:
            return
        sidecar = data_path.parent / f"{data_path.name}.meta.json"
        try:
            if not sidecar.exists():
                return
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            extra = payload.get("extra")
            if not isinstance(extra, dict):
                extra = {}
                payload["extra"] = extra
            if extra.get("parent_request") == request:
                return
            seen = extra.get("parent_requests")
            if not isinstance(seen, list):
                seen = []
            if request in seen:
                return
            extra["parent_requests"] = [*seen, request]
            tmp = sidecar.with_name(
                f"{sidecar.name}.{os.getpid()}_{threading.get_ident()}.tmp"
            )
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, sidecar)
        except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
            logger.warning(f"Nie udalo sie dopisac zadania do sidecara {sidecar}: {e}")

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"DownloadManager(provider={self._provider.name}, "
            f"output_dir='{self._storage.output_dir}', "
            f"resolution='{self._resolution}', "
            f"max_workers={self._max_workers})"
        )
