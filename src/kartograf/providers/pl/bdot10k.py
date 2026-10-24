"""
BDOT10k provider for downloading land cover data.

This module provides the Bdot10kProvider class for downloading
land cover data from the Polish BDOT10k database (Baza Danych
Obiektów Topograficznych) maintained by GUGiK.

A powiat package holds one table per class and geometry type
(``OT_<CODE>_<A|L|P>``), 47-70 tables depending on the objects of the powiat.
``BDOT10K_CLASSES`` lists the 58 classes of the BDOT10k classification
(the regulation of 2021, Dz.U. 2021 poz. 1412, annex 1) - every value that
``layers`` accepts; among them the land cover (PT, 12 classes) and the
hydrographic network (SW, 3 classes: SWKN canals, SWRM drainage ditches,
SWRS rivers and streams).
"""

import logging
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.interrupt import check_stop
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.pl.prg import discover_teryts_for_bbox
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
    response_signal,
)

logger = logging.getLogger(__name__)

# Layer code = the 4 letters after OT_ in GUGiK table names (e.g. PTWP in OT_PTWP_A)
_LAYER_CODE = re.compile(r"[A-Z]{4}")

# The classes of BDOT10k (code -> Polish name without diacritics): the
# classification of the regulation of 27 July 2021 (Dz.U. 2021 poz. 1412, annex
# 1: 58 classes, categories AD BU KU OI PT RT SK SU SW TC), the codes of the
# ``OT_<CODE>_<A|L|P>`` tables of the 2021 schema packages (checked 2026-10-19
# against the packages of powiats 2463, 2472, 2476: 47-49 classes each, all in
# this list; GUGiK's own table OT_BIUB_L of powiat 2472 is a typo of BUIB).
# A class a powiat has no objects of is missing in its package.
BDOT10K_CLASSES = {
    "ADJA": "Jednostki podzialu administracyjnego",
    "ADMS": "Miejscowosci",
    "BUBD": "Budynki",
    "BUHD": "Budowle hydrotechniczne",
    "BUIB": "Inne budowle",
    "BUIN": "Budowle inzynierskie",
    "BUIT": "Inne urzadzenia techniczne",
    "BUSP": "Budowle sportowe",
    "BUTR": "Urzadzenia transportowe",
    "BUUO": "Umocnienia drogowe, kolejowe i wodne",
    "BUWT": "Wysokie budowle techniczne",
    "BUZM": "Budowle ziemne",
    "BUZT": "Zbiorniki techniczne",
    "KUHO": "Kompleksy uslug hotelarskich",
    "KUHU": "Bazary i targowiska",
    "KUKO": "Kompleksy komunikacyjne",
    "KUMN": "Osiedla mieszkaniowe",
    "KUOS": "Kompleksy oswiatowe",
    "KUOZ": "Kompleksy ochrony zdrowia i opieki spolecznej",
    "KUPG": "Kompleksy przemyslowo-gospodarcze",
    "KUPW": "Poligony wojskowe",
    "KUSC": "Kompleksy sakralne i cmentarze",
    "KUSK": "Kompleksy sportowe i rekreacyjne",
    "KUZA": "Kompleksy zabytkowo-historyczne",
    "OIKM": "Obiekty zwiazane z komunikacja",
    "OIMK": "Mokradla",
    "OIOR": "Obiekty o znaczeniu orientacyjnym",
    "OIPR": "Obiekty przyrodnicze",
    "OISZ": "Szuwary",
    "PTGN": "Grunty nieuzytkowe",
    "PTKM": "Tereny komunikacyjne",
    "PTLZ": "Tereny lesne",
    "PTNZ": "Tereny niezabudowane",
    "PTPL": "Place",
    "PTRK": "Roslinnosc krzewiasta",
    "PTSO": "Skladowiska",
    "PTTR": "Tereny rolne",
    "PTUT": "Uprawy trwale",
    "PTWP": "Wody powierzchniowe",
    "PTWZ": "Wyrobiska i zwalowiska",
    "PTZB": "Tereny zabudowane",
    "RTLW": "Linie wysokosciowe",
    "RTPW": "Punkty wysokosciowe",
    "SKDR": "Drogi",
    "SKJZ": "Jezdnie",
    "SKPP": "Przeprawy",
    "SKRP": "Ciagi ruchu pieszego i rowerowego",
    "SKRW": "Ronda i wezly drogowe",
    "SKTR": "Tory i zespoly torow",
    "SULN": "Linie elektroenergetyczne",
    "SUPR": "Przewody rurowe",
    "SWKN": "Kanaly",
    "SWRM": "Rowy melioracyjne",
    "SWRS": "Rzeki i strumienie",
    "TCON": "Obszary Natura 2000",
    "TCPK": "Parki krajobrazowe",
    "TCPN": "Parki narodowe",
    "TCRZ": "Rezerwaty",
}


def normalize_layers(layers: Sequence[str]) -> list[str]:
    """Return sorted unique BDOT10k layer codes in upper case (``ptwp`` = ``PTWP``).

    ``ValidationError`` (before any network) for a bad code.

    A code is 4 letters of a class of ``BDOT10K_CLASSES`` (``PTWP``, ``SWRS``);
    an empty selection and an empty code (a stray comma) are errors too. A
    class a powiat package has no objects of is not an error here: the package
    download reports it (``Bdot10kPackage.absent``).
    """
    wanted = sorted({layer.strip().upper() for layer in layers})
    if not wanted:
        raise ValidationError(
            "--layers: podaj co najmniej jeden kod warstwy BDOT10k (4 litery, "
            "np. PTWP, SWRS)",
            option="layers",
        )
    if "" in wanted:
        raise ValidationError(
            "--layers: pusty kod warstwy (nadmiarowy przecinek?); podaj kody "
            "BDOT10k po przecinku (4 litery, np. PTWP,SWRS)",
            option="layers",
        )
    bad = [layer for layer in wanted if not _LAYER_CODE.fullmatch(layer)]
    if bad:
        raise ValidationError(
            f"Nieprawidlowe kody warstw BDOT10k: {', '.join(bad)} (4 litery, np. "
            "PTWP, SWRS)",
            option="layers",
        )
    unknown = [layer for layer in wanted if layer not in BDOT10K_CLASSES]
    if unknown:
        raise ValidationError(
            f"--layers {', '.join(unknown)}: brak takich klas w BDOT10k; "
            f"dostepne: {', '.join(BDOT10K_CLASSES)}",
            option="layers",
            allowed=tuple(BDOT10K_CLASSES),
        )
    return wanted


@dataclass(frozen=True)
class Bdot10kPackage:
    """One downloaded powiat package (``Bdot10kProvider.download_package``).

    ``classes``: the classes kept in the GPKG when ``layers`` was given (else
    ``None``: the whole package); ``absent``: the requested classes the package
    has no table of (no objects of them in the powiat).
    """

    path: Path  # the file actually written (.gpkg, or .zip for SHP)
    teryt: str
    url: str
    format: str
    # Response headers: etag / last_modified / content_length (None = not sent)
    http: dict[str, Any] = field(default_factory=dict)
    raw_path: Path | None = None  # original GUGiK ZIP (keep_raw=True)
    classes: tuple[str, ...] | None = None
    absent: tuple[str, ...] = ()


# Mapping of voivodeship (wojewodztwo) TERYT codes to names used in OpenData URLs
WOJEWODZTWO_NAMES = {
    "02": "dolnoslaskie",
    "04": "kujawsko-pomorskie",
    "06": "lubelskie",
    "08": "lubuskie",
    "10": "lodzkie",
    "12": "malopolskie",
    "14": "mazowieckie",
    "16": "opolskie",
    "18": "podkarpackie",
    "20": "podlaskie",
    "22": "pomorskie",
    "24": "slaskie",
    "26": "swietokrzyskie",
    "28": "warminsko-mazurskie",
    "30": "wielkopolskie",
    "32": "zachodniopomorskie",
}


class Bdot10kProvider(LandCoverProvider):
    """
    Provider for downloading land cover data from BDOT10k.

    BDOT10k (Baza Danych Obiektów Topograficznych 1:10000) is the Polish
    topographic database maintained by GUGiK. It contains detailed land
    cover information for the entire country.

    Every download is a pre-packaged powiat (county) package from OpenData:
    - By TERYT code: that powiat (``download_package``)
    - By bbox or sheet code: the ONE powiat intersecting the area;
      several powiats = ``ValidationError`` (use
      ``download_landcover(product="bdot10k", bbox=..., output_dir=...)`` or
      ``teryts_for_area``),
      none = ``NoCoverageError``. The area may be in any supported CRS.

    Examples
    --------
    >>> provider = Bdot10kProvider()
    >>>
    >>> # Download by TERYT (powiat code)
    >>> provider.download_package("1465", Path("./data/powiat_1465.gpkg"))
    >>>
    >>> # Download by bbox (one powiat)
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_by_bbox(bbox, Path("./data/area.gpkg"))
    >>>
    >>> # Download by sheet code
    >>> provider.download_by_sheet("N-34-130-D", Path("./data/sheet.gpkg"))
    """

    # OpenData base URL for BDOT10k packages
    OPENDATA_BASE = "https://opendata.geoportal.gov.pl/bdot10k"

    # URL patterns for different formats (2021 schema)
    # Pattern: {base}/schemat2021/{subdir}/{woj_code}/{teryt}_{suffix}.zip
    OPENDATA_PATTERNS = {
        "GPKG": "{base}/schemat2021/GPKG/{woj}/{teryt}_GPKG.zip",
        "SHP": "{base}/schemat2021/SHP/{woj}/{teryt}_SHP.zip",
    }

    # Default settings
    DEFAULT_TIMEOUT = 120  # package download (all modes); TERYT (PRG): 30 s
    MAX_RETRIES = MAX_RETRIES

    def __init__(
        self,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
    ):
        """
        Initialize BDOT10k provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests. Default: one keep-alive
            GUGiK session per thread (``make_gugik_session``).
        cache : MetadataCache, optional
            Metadata cache for the PRG TERYT discovery (``teryts_for_area``).
            If None, no caching is performed (default behavior).
        """
        self._sessions = SessionPerThread(session)
        self._cache = cache
        self.descriptor_key = "pl.gugik.bdot10k"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "BDOT10k"

    @property
    def base_url(self) -> str:
        """Return source URL."""
        return "https://www.geoportal.gov.pl/dane/bdot10k"

    def session(self) -> requests.Session:
        """Return the HTTP session of the current thread.

        The injected one (``session=``) or one per thread (e.g. the BDOT10k archive of
        ``LandCoverManager``).
        """
        return self._sessions.get()

    # =========================================================================
    # Download by TERYT → OpenData packages
    # =========================================================================

    def download_package(
        self,
        code: str,
        output_path: Path,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        layers: Sequence[str] | None = None,
        keep_raw: bool = False,
        raw_path: Path | None = None,
    ) -> Bdot10kPackage:
        """Download one powiat package; ``layers`` keeps only those layer codes (GPKG).

        Pre-packaged data from OpenData: the fastest way to get a large area,
        as the files are pre-generated. The GPKG package is unpacked and its
        per-layer files merged into one GeoPackage (``output_path`` with the
        extension ``.gpkg``); the SHP package is saved as the original GUGiK
        archive with shapefiles (``.zip``).

        Parameters
        ----------
        code : str
            4-digit TERYT code for powiat (e.g., "1465" for powiat
            warszawski zachodni)
        output_path : Path
            Path where the file should be saved (extension follows the format)
        timeout : int, optional
            Request timeout in seconds (default: 120)
        format : str, optional
            Output format: "GPKG" or "SHP" (default: "GPKG")
        layers : Sequence[str], optional
            Layer codes to keep (4 upper-case letters, e.g. ``PTWP``,
            ``SWRS``); every other layer of the package is dropped. GPKG only.
        keep_raw : bool, optional
            Also keep the original GUGiK ZIP next to the GeoPackage as
            ``<output stem>_GPKG.zip`` (written only after a successful
            merge). GPKG only: the SHP result already is the original ZIP.
        raw_path : Path, optional
            Where ``keep_raw`` saves the original ZIP instead of
            ``<output stem>_GPKG.zip`` (e.g. one unfiltered name shared by
            every layer filter); only together with ``keep_raw``.

        Returns
        -------
        Bdot10kPackage
            ``path`` = the file actually written, plus ``teryt``, ``url``,
            ``format``, ``http`` (``etag``, ``last_modified``,
            ``content_length`` of the response; None when not sent),
            ``raw_path`` (the raw ZIP with ``keep_raw``, else None) and, with
            ``layers``, ``classes`` (kept in the GPKG) and ``absent`` (the
            requested classes the package has no table of)

        Raises
        ------
        ValidationError
            Invalid TERYT, layer code or class (before the network); ``layers``
            or ``keep_raw`` with SHP; ``raw_path`` without ``keep_raw``.
        NoCoverageError
            With ``layers``: the package has none of the requested classes
            (no objects of them in the powiat).
        DownloadError
            Download failure or two package files with the same table name.
        """
        if not self.validate_admin_unit(code):
            raise ValidationError(f"Nieprawidlowy kod TERYT: {code}")
        if format not in ["GPKG", "SHP"]:
            raise ValidationError(
                f"Nieobslugiwany format: {format}. Uzyj 'GPKG' albo 'SHP'"
            )
        wanted = None
        if layers is not None:
            wanted = normalize_layers(layers)
            if format != "GPKG":
                raise ValidationError("Filtr warstw BDOT10k dziala tylko z GPKG")
        if keep_raw and format != "GPKG":
            raise ValidationError(
                "keep_raw dotyczy tylko GPKG (SHP to juz oryginalny ZIP)"
            )
        if raw_path is not None and not keep_raw:
            raise ValidationError("raw_path wymaga keep_raw=True")
        output_path = Path(output_path)
        if format == "SHP":
            # The SHP package is a ZIP archive of shapefiles (not unpacked): the name
            # must say so rather than pretend to be a GeoPackage (review N1). Symmetric
            # to GPKG, where `_extract_gpkg_from_zip` assigns .gpkg.
            output_path = output_path.with_suffix(".zip")
        url = self._construct_opendata_url(code, format)
        headers: dict[str, Any] = {}
        found: dict[str, Any] = {}

        def capture(response: requests.Response) -> None:
            headers.clear()
            headers.update(response_signal(response))

        if keep_raw and raw_path is None:
            raw_path = output_path.with_name(f"{output_path.stem}_GPKG.zip")

        def save(response: requests.Response, target: Path) -> Path:
            return self._extract_gpkg_from_zip(
                response, target, layers=wanted, raw_path=raw_path, report=found
            )

        path = download_to(
            self._sessions.get(),
            url,
            output_path,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=f"BDOT10k TERYT {code}",
            on_response=capture,
            save=save if format == "GPKG" else None,
        )
        return Bdot10kPackage(
            path=path,
            teryt=code,
            url=url,
            format=format,
            http=dict(headers),
            raw_path=raw_path,
            classes=tuple(found["classes"]) if "classes" in found else None,
            absent=tuple(found.get("absent", ())),
        )

    def download_by_admin_unit(
        self,
        code: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs: Any,
    ) -> Path:
        """``LandCoverProvider`` entry point: ``download_package(...).path``.

        ``kwargs`` may carry ``layers`` and ``keep_raw`` (see
        ``download_package``); other options are ignored.
        """
        return self.download_package(
            code,
            output_path,
            timeout=timeout,
            format=format,
            layers=kwargs.get("layers"),
            keep_raw=kwargs.get("keep_raw", False),
        ).path

    def _construct_opendata_url(self, teryt: str, format: str) -> str:
        """
        Construct OpenData URL for BDOT10k package.

        URL pattern: .../bdot10k/schemat2021/{subdir}/{woj}/{teryt}_{suffix}.zip

        Parameters
        ----------
        teryt : str
            4-digit TERYT code
        format : str
            Output format (GPKG or SHP)

        Returns
        -------
        str
            Full OpenData URL
        """
        woj_code = teryt[:2]

        if woj_code not in WOJEWODZTWO_NAMES:
            raise ValidationError(
                f"Nieznany kod wojewodztwa: {woj_code}. "
                f"Dostepne kody: {list(WOJEWODZTWO_NAMES.keys())}"
            )

        pattern = self.OPENDATA_PATTERNS.get(format, self.OPENDATA_PATTERNS["GPKG"])

        return pattern.format(base=self.OPENDATA_BASE, woj=woj_code, teryt=teryt)

    def package_url(self, teryt: str, format: str = "GPKG") -> str:
        """Return the OpenData URL of the package of powiat ``teryt``.

        The file ``download_package`` downloads; ``HEAD`` of it gives its size.
        """
        return self._construct_opendata_url(teryt, format)

    # =========================================================================
    # Download by sheet code / bbox → the one powiat of the area (PRG)
    # =========================================================================

    def teryts_for_area(self, bbox: BBox, timeout: int = 30) -> list[str]:
        """Powiat TERYT codes intersecting ``bbox`` (``discover_teryts_for_bbox``)."""
        return discover_teryts_for_bbox(
            bbox, session=self._sessions.get(), cache=self._cache, timeout=timeout
        )

    def _single_teryt(self, bbox: BBox, what: str, timeout: int = 30) -> str:
        """Return the one powiat of an area.

        Several: ValidationError, none: NoCoverage.
        """
        teryts = self.teryts_for_area(bbox, timeout=timeout)
        if not teryts:
            raise NoCoverageError(f"{what}: obszar nie przecina zadnego powiatu (PRG)")
        if len(teryts) > 1:
            raise ValidationError(
                f"{what}: obszar przecina {len(teryts)} powiaty ({', '.join(teryts)}); "
                "uzyj download_landcover(product='bdot10k', bbox=..., "
                "output_dir=...) albo pobierz kazdy powiat przez --teryt"
            )
        return teryts[0]

    def download_by_sheet(
        self,
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs: Any,
    ) -> Path:
        """
        Download BDOT10k data for a map sheet.

        Finds the ONE powiat (county) intersecting the sheet frame (PRG WFS)
        and downloads the entire county package. A sheet spanning several
        powiats is an error - use ``download_landcover(product="bdot10k",
        sheet=..., output_dir=...)``.

        Parameters
        ----------
        sheet : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120)
        format : str, optional
            Output format: "GPKG" or "SHP" (default: "GPKG")
        **kwargs
            ``layers`` (see ``download_package``); other options are ignored

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ValidationError
            The sheet intersects more than one powiat (codes in the message)
        NoCoverageError
            The sheet intersects no powiat
        DownloadError
            PRG query or download failure
        """
        from kartograf.core.sheet_parser import SheetParser

        bbox = SheetParser(sheet).get_bbox(crs="EPSG:2180")
        teryt = self._single_teryt(bbox, f"BDOT10k {sheet}", timeout)
        logger.info(f"Godlo {sheet} is in powiat {teryt}, downloading county package")
        return self.download_by_admin_unit(
            teryt, output_path, timeout, format=format, **kwargs
        )

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs: Any,
    ) -> Path:
        """
        Download BDOT10k land cover data for a bounding box.

        Finds the ONE powiat (county) intersecting the bbox (PRG WFS) and
        downloads the entire county package. A bbox spanning several powiats
        is an error - use ``download_landcover(product="bdot10k",
        bbox=..., output_dir=...)``.

        Note: The returned data covers the entire county, not just the bbox.
        Use GIS software to clip to the exact bbox if needed.

        Parameters
        ----------
        bbox : BBox
            Bounding box in any supported CRS (converted to EPSG:2180 for
            the PRG query)
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120)
        format : str, optional
            Output format: "GPKG" or "SHP" (default: "GPKG")
        **kwargs
            ``layers`` (see ``download_package``); other options are ignored

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ValidationError
            The bbox intersects more than one powiat (codes in the message)
        NoCoverageError
            The bbox intersects no powiat
        DownloadError
            PRG query or download failure
        """
        teryt = self._single_teryt(bbox, "BDOT10k bbox", timeout)
        logger.info(f"Bbox is in powiat {teryt}, downloading county package")
        return self.download_by_admin_unit(
            teryt, output_path, timeout, format=format, **kwargs
        )

    # =========================================================================
    # Common utilities
    # =========================================================================

    def _extract_gpkg_from_zip(
        self,
        response: requests.Response,
        output_path: Path,
        layers: Sequence[str] | None = None,
        raw_path: Path | None = None,
        report: dict[str, Any] | None = None,
    ) -> Path:
        """
        Extract and merge all layers from downloaded ZIP.

        BDOT10k packages contain separate GPKG files for each layer
        (``PL.PZGiK.337.BDOT10k.<TERYT>__OT_<CODE>_<A|L|P>.gpkg``, one table
        each). This method extracts the layers and merges them into a single
        GeoPackage file.

        Parameters
        ----------
        response : requests.Response
            HTTP response with ZIP content
        output_path : Path
            Target path for merged GPKG (the actual file is written to
            ``output_path.with_suffix(".gpkg")``, which is also what is
            returned)
        layers : Sequence[str], optional
            Layer codes to keep (``OT_<code>_*`` files); None = all. A class
            without a file in the package is skipped (``report["absent"]``)
            unless none of them is in the package
        raw_path : Path, optional
            Where to also save the downloaded ZIP unchanged (atomically, only
            after a successful merge, before the GPKG replaces the previous
            one); None = not kept
        report : dict, optional
            Filled with ``classes`` (kept) and ``absent`` (requested, not in
            the package) when ``layers`` is given

        Returns
        -------
        Path
            Path to the merged GPKG file that was actually written to disk

        Raises
        ------
        NoCoverageError
            ``layers`` given and the package has a file of none of them.
        DownloadError
            Not a ZIP, no GPKG inside, two files with the same table name,
            or an I/O error
            while extracting, merging or writing the raw ZIP. The merged
            GPKG waits in ``<name>.gpkg.<pid>_<tid>.tmp`` and replaces ``output_path``
            only after the raw ZIP is saved, so on any error the previous
            GPKG (and the sidecar the caller wrote for it) stays untouched
            (P1). Residual window: a failure between the two ``os.replace``
            calls (raw ZIP, then GPKG) leaves the new raw ZIP with its old
            sidecar.
        """
        # Read ZIP into memory
        zip_data = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            check_stop()
            zip_data.write(chunk)
        zip_data.seek(0)

        try:
            with zipfile.ZipFile(zip_data, "r") as zf:
                all_gpkg = [f for f in zf.namelist() if f.endswith(".gpkg")]

                if not all_gpkg:
                    raise DownloadError(
                        f"Brak plikow GPKG w ZIP. Zawartosc: {zf.namelist()}"
                    )

                if layers is not None:
                    by_code = {
                        code: [f for f in all_gpkg if f"__OT_{code}_" in Path(f).name]
                        for code in layers
                    }
                    kept = [code for code, files in by_code.items() if files]
                    absent = [code for code in by_code if code not in kept]
                    if not kept:
                        raise NoCoverageError(
                            "paczka BDOT10k nie ma plikow klas "
                            f"{', '.join(absent)} (brak obiektow tych klas w "
                            "powiecie)"
                        )
                    if report is not None:
                        report["classes"] = kept
                        report["absent"] = absent
                    all_gpkg = [f for code in kept for f in by_code[code]]

                logger.debug(f"Found {len(all_gpkg)} layers to merge")

                # Create temp directory for extraction
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)

                    extracted_files = []
                    for gpkg_file in all_gpkg:
                        check_stop()
                        # Extract to temp directory
                        extracted_path = tmpdir_path / Path(gpkg_file).name
                        with (
                            zf.open(gpkg_file) as src,
                            open(extracted_path, "wb") as dst,
                        ):
                            # streamed: never a whole layer in memory
                            shutil.copyfileobj(src, dst)
                        extracted_files.append(extracted_path)
                        logger.debug(f"Extracted {Path(gpkg_file).name}")

                    # Merge all layers into a staged GPKG next to the target
                    # (pid/tid in the name: concurrent downloads of the same
                    # powiat never share it)
                    output_gpkg = output_path.with_suffix(".gpkg")
                    staged = output_gpkg.with_name(
                        f"{output_gpkg.name}.{os.getpid()}_{threading.get_ident()}.tmp"
                    )
                    self._merge_gpkg_files(extracted_files, staged)
                    try:
                        if raw_path is not None:
                            try:
                                self._write_raw_zip(zip_data, raw_path)
                            except OSError as e:
                                raise DownloadError(
                                    "Nie udalo sie zapisac oryginalnego ZIP "
                                    f"BDOT10k {raw_path.name}: {e}; poprzedni "
                                    f"{output_gpkg.name} (jesli byl) bez zmian"
                                ) from e
                        # os.replace: overwrites an existing file on Windows
                        # too (--force)
                        os.replace(staged, output_gpkg)
                    except BaseException:
                        staged.unlink(missing_ok=True)
                        raise
                    logger.info(
                        f"Merged {len(extracted_files)} layers into {output_gpkg}"
                    )
                    return output_gpkg

        except zipfile.BadZipFile as e:
            raise DownloadError(f"Nieprawidlowy plik ZIP: {e}") from e
        except OSError as e:
            # disk full, no memory for the temp file, share errors: a
            # KartografError, not a bare OSError
            raise DownloadError(
                "Nie udalo sie rozpakowac ani zapisac paczki BDOT10k "
                f"({output_path.with_suffix('.gpkg').name}): {e}"
            ) from e

    @staticmethod
    def _write_raw_zip(zip_data: BytesIO, raw_path: Path) -> None:
        """Save the original GUGiK ZIP (A4) atomically, like ``download_to``.

        Writes from a view of the buffer (no second in-memory copy).
        """
        tmp = raw_path.with_name(
            f"{raw_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
        )
        try:
            with zip_data.getbuffer() as view:
                tmp.write_bytes(view)
            os.replace(tmp, raw_path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def _merge_gpkg_files(self, source_files: list[Path], staged_path: Path) -> None:
        """
        Merge multiple GeoPackage files into one, written to ``staged_path``.

        Each source file is expected to have a single data table.
        All tables are copied to the output file, preserving geometry. The
        caller moves ``staged_path`` to its final name (``os.replace``) when
        everything else succeeded; on an error here ``staged_path`` is removed.

        Parameters
        ----------
        source_files : list[Path]
            List of source GPKG files to merge
        staged_path : Path
            Merged GPKG file (a temporary name next to the final one)

        Raises
        ------
        DownloadError
            No files, or a table name repeated across files (the merge
            would silently lose the second copy)
        """
        if not source_files:
            raise DownloadError("Brak plikow do scalenia")

        # SQLite ALWAYS writes in a local temp directory: on a CIFS/SMB share without
        # `nobrl`, byte-range locks ended the merge with `database is locked`. The
        # target directory receives the finished file (copy).
        try:
            with tempfile.TemporaryDirectory() as work_dir:
                local_path = Path(work_dir) / "merged.gpkg"

                # Copy first file as base (includes GPKG metadata structure)
                first_file = source_files[0]
                shutil.copyfile(first_file, local_path)

                logger.debug(f"Using {first_file.name} as base GPKG")

                # Merge remaining files
                conn = sqlite3.connect(local_path)
                try:
                    cursor = conn.cursor()
                    for source_file in source_files[1:]:
                        check_stop()
                        self._copy_gpkg_layer(cursor, source_file)
                    conn.commit()
                finally:
                    conn.close()

                shutil.copyfile(local_path, staged_path)
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise

    def _copy_gpkg_layer(self, cursor: sqlite3.Cursor, source_path: Path) -> None:
        """
        Copy a layer from source GPKG to destination (via cursor).

        Parameters
        ----------
        cursor : sqlite3.Cursor
            Cursor to destination database
        source_path : Path
            Source GPKG file
        """
        # Attach source database
        cursor.execute(f"ATTACH DATABASE '{source_path}' AS src")

        try:
            # Get data table name (exclude gpkg_* and rtree_* tables)
            cursor.execute(
                """
                SELECT name FROM src.sqlite_master
                WHERE type='table'
                AND name NOT LIKE 'gpkg_%'
                AND name NOT LIKE 'rtree_%'
                AND name NOT LIKE 'sqlite_%'
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table_name in tables:
                # Check if table already exists in destination
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone():
                    raise DownloadError(
                        f"Paczka BDOT10k: tabela {table_name} wystepuje w wiecej niz "
                        f"jednym pliku ({source_path.name}) - scalenie zgubiloby dane"
                    )

                # Get table schema from source
                cursor.execute(
                    "SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                create_sql = cursor.fetchone()[0]

                # Create table in destination
                cursor.execute(create_sql)

                # Copy data
                cursor.execute(
                    f"INSERT INTO [{table_name}] SELECT * FROM src.[{table_name}]"
                )

                # Copy gpkg_contents entry
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO gpkg_contents
                    SELECT * FROM src.gpkg_contents WHERE table_name=?
                    """,
                    (table_name,),
                )

                # Copy gpkg_geometry_columns entry
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO gpkg_geometry_columns
                    SELECT * FROM src.gpkg_geometry_columns WHERE table_name=?
                    """,
                    (table_name,),
                )

                # Copy rtree spatial index if present
                self._copy_rtree_index(cursor, table_name)

                logger.debug(f"Copied layer {table_name}")

            # Commit before detaching to release locks
            cursor.connection.commit()

        finally:
            cursor.execute("DETACH DATABASE src")

    def _copy_rtree_index(self, cursor: sqlite3.Cursor, table_name: str) -> None:
        """
        Copy rtree spatial index for a table from attached source database.

        Parameters
        ----------
        cursor : sqlite3.Cursor
            Cursor to destination database (with source attached as 'src')
        table_name : str
            Name of the data table to copy rtree index for
        """
        # Get geometry column name from gpkg_geometry_columns
        cursor.execute(
            """
            SELECT column_name FROM src.gpkg_geometry_columns
            WHERE table_name=?
            """,
            (table_name,),
        )
        row = cursor.fetchone()
        if not row:
            return  # No geometry column -> no rtree

        geom_col = row[0]
        rtree_name = f"rtree_{table_name}_{geom_col}"

        # Check if rtree exists in source
        cursor.execute(
            "SELECT name FROM src.sqlite_master WHERE type='table' AND name=?",
            (rtree_name,),
        )
        if not cursor.fetchone():
            return  # No rtree in source

        # Create rtree virtual table in destination
        cursor.execute(
            f"CREATE VIRTUAL TABLE [{rtree_name}] "
            f"USING rtree(id, minx, maxx, miny, maxy)"
        )

        # Copy rtree data
        cursor.execute(f"INSERT INTO [{rtree_name}] SELECT * FROM src.[{rtree_name}]")

        # Copy gpkg_extensions entry for rtree if gpkg_extensions exists in source
        cursor.execute(
            "SELECT name FROM src.sqlite_master "
            "WHERE type='table' AND name='gpkg_extensions'"
        )
        if cursor.fetchone():
            # Ensure gpkg_extensions exists in destination
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='gpkg_extensions'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "CREATE TABLE gpkg_extensions ("
                    "table_name TEXT, column_name TEXT, extension_name TEXT, "
                    "definition TEXT, scope TEXT)"
                )

            cursor.execute(
                """
                INSERT OR IGNORE INTO gpkg_extensions
                SELECT * FROM src.gpkg_extensions
                WHERE table_name=? AND extension_name='gpkg_rtree_index'
                """,
                (table_name,),
            )

        logger.debug(f"Copied rtree index {rtree_name}")

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_available_layers(self) -> list[str]:
        """Return list of available BDOT10k layers."""
        return list(self._layer_descriptions().keys())

    @staticmethod
    def _layer_descriptions() -> dict[str, str]:
        """Return mapping of layer codes to descriptions."""
        return dict(BDOT10K_CLASSES)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["GPKG", "SHP"]

    def get_layer_description(self, layer: str) -> str:
        """
        Get human-readable description for layer.

        Parameters
        ----------
        layer : str
            Layer code (e.g., "PTLZ")

        Returns
        -------
        str
            Layer description in Polish
        """
        return self._layer_descriptions().get(layer, layer)
