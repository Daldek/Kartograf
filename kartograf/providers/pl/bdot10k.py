"""
BDOT10k provider for downloading land cover data.

This module provides the Bdot10kProvider class for downloading
land cover data from the Polish BDOT10k database (Baza Danych
Obiektów Topograficznych) maintained by GUGiK.

BDOT10k contains 15 layers in two categories:

Land cover (PT - Pokrycie Terenu, 12 layers):
- PTGN: Grunty nieużytkowe (unused land)
- PTKM: Tereny komunikacyjne (transportation areas)
- PTLZ: Tereny leśne (forests)
- PTNZ: Tereny niezabudowane (unbuilt areas)
- PTPL: Place (squares/plazas)
- PTRK: Roślinność krzewiasta (shrub vegetation)
- PTSO: Składowiska (landfills)
- PTTR: Tereny rolne (agricultural land)
- PTUT: Uprawy trwałe (permanent crops)
- PTWP: Wody powierzchniowe (surface waters)
- PTWZ: Tereny zabagnione (wetlands)
- PTZB: Tereny zabudowane (built-up areas)

Hydrographic (SW - Sieć Wodna, 3 layers):
- SWKN: Kanały (canals)
- SWRM: Rowy melioracyjne (drainage ditches)
- SWRS: Rzeki i strumienie (rivers/streams)
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

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.pl.prg import discover_teryts_for_bbox
from kartograf.transport.http import MAX_RETRIES, SessionPerThread, download_to

logger = logging.getLogger(__name__)

# Layer code = the 4 letters after OT_ in GUGiK table names (e.g. PTWP in OT_PTWP_A)
_LAYER_CODE = re.compile(r"[A-Z]{4}")


@dataclass(frozen=True)
class Bdot10kPackage:
    """One downloaded powiat package (``Bdot10kProvider.download_package``)."""

    path: Path  # the file actually written (.gpkg, or .zip for SHP)
    teryt: str
    url: str
    format: str
    # Response headers: etag / last_modified / content_length (None = not sent)
    http: dict = field(default_factory=dict)
    raw_path: Path | None = None  # original GUGiK ZIP (keep_raw=True)


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
    - By bbox or sheet code (godlo): the ONE powiat intersecting the area;
      several powiats = ``ValidationError`` (use
      ``LandCoverManager.download_all_counties`` or ``teryts_for_area``),
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
    >>> # Download by sheet code (godlo)
    >>> provider.download_by_godlo("N-34-130-D", Path("./data/sheet.gpkg"))
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

    def __init__(self, session: requests.Session | None = None, cache=None):
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
            ``content_length`` of the response; None when not sent) and
            ``raw_path`` (the raw ZIP with ``keep_raw``, else None)

        Raises
        ------
        ValidationError
            Invalid TERYT or layer code (before the network); ``layers`` or
            ``keep_raw`` with SHP; ``raw_path`` without ``keep_raw``.
        DownloadError
            Download failure, a requested layer missing in the package, or two
            package files with the same table name.
        """
        if not self.validate_admin_unit(code):
            raise ValidationError(f"Invalid TERYT code: {code}")
        if format not in ["GPKG", "SHP"]:
            raise ValueError(f"Unsupported format: {format}. Use 'GPKG' or 'SHP'")
        wanted = None
        if layers is not None:
            wanted = sorted(set(layers))
            bad = [layer for layer in wanted if not _LAYER_CODE.fullmatch(layer)]
            if bad or not wanted:
                raise ValidationError(
                    f"Nieprawidlowe kody warstw BDOT10k: {bad or '[]'} "
                    "(4 wielkie litery, np. PTWP, SWRS)"
                )
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
        headers: dict = {}

        def capture(response: requests.Response) -> None:
            def text(name: str) -> str | None:
                # str only: anything else (e.g. a test double) is "absent"
                value = response.headers.get(name)
                return value if isinstance(value, str) else None

            length = text("Content-Length")
            headers.clear()
            headers.update(
                etag=text("ETag"),
                last_modified=text("Last-Modified"),
                content_length=int(length) if length and length.isdigit() else None,
            )

        if keep_raw and raw_path is None:
            raw_path = output_path.with_name(f"{output_path.stem}_GPKG.zip")

        def save(response: requests.Response, target: Path) -> Path:
            return self._extract_gpkg_from_zip(
                response, target, layers=wanted, raw_path=raw_path
            )

        path = download_to(
            self._sessions.get(),
            url,
            output_path,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=f"BDOT10k TERYT {code}",
            validate=capture,
            save=save if format == "GPKG" else None,
        )
        return Bdot10kPackage(
            path=path,
            teryt=code,
            url=url,
            format=format,
            http=dict(headers),
            raw_path=raw_path,
        )

    def download_by_admin_unit(
        self,
        code: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs,
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
                f"Unknown województwo code: {woj_code}. "
                f"Valid codes: {list(WOJEWODZTWO_NAMES.keys())}"
            )

        pattern = self.OPENDATA_PATTERNS.get(format, self.OPENDATA_PATTERNS["GPKG"])

        return pattern.format(base=self.OPENDATA_BASE, woj=woj_code, teryt=teryt)

    # =========================================================================
    # Download by sheet code / bbox → the one powiat of the area (PRG)
    # =========================================================================

    def teryts_for_area(self, bbox: BBox, timeout: int = 30) -> list[str]:
        """Powiat TERYT codes intersecting ``bbox`` (``discover_teryts_for_bbox``)."""
        return discover_teryts_for_bbox(
            bbox, session=self._sessions.get(), cache=self._cache, timeout=timeout
        )

    def _single_teryt(self, bbox: BBox, what: str, timeout: int = 30) -> str:
        """The one powiat of an area (several: ValidationError, none: NoCoverage)."""
        teryts = self.teryts_for_area(bbox, timeout=timeout)
        if not teryts:
            raise NoCoverageError(f"{what}: obszar nie przecina zadnego powiatu (PRG)")
        if len(teryts) > 1:
            raise ValidationError(
                f"{what}: obszar przecina {len(teryts)} powiaty ({', '.join(teryts)}); "
                "uzyj LandCoverManager.download_all_counties albo pobierz kazdy "
                "powiat przez --teryt"
            )
        return teryts[0]

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k data for a map sheet (godlo).

        Finds the ONE powiat (county) intersecting the sheet frame (PRG WFS)
        and downloads the entire county package. A sheet spanning several
        powiats is an error - use ``LandCoverManager.download_all_counties``.

        Parameters
        ----------
        godlo : str
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

        bbox = SheetParser(godlo).get_bbox(crs="EPSG:2180")
        teryt = self._single_teryt(bbox, f"BDOT10k {godlo}", timeout)
        logger.info(f"Godło {godlo} is in powiat {teryt}, downloading county package")
        return self.download_by_admin_unit(
            teryt, output_path, timeout, format=format, **kwargs
        )

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        format: str = "GPKG",
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k land cover data for a bounding box.

        Finds the ONE powiat (county) intersecting the bbox (PRG WFS) and
        downloads the entire county package. A bbox spanning several powiats
        is an error - use ``LandCoverManager.download_all_counties``.

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
            Layer codes to keep (``OT_<code>_*`` files); None = all
        raw_path : Path, optional
            Where to also save the downloaded ZIP unchanged (atomically, only
            after a successful merge); None = not kept

        Returns
        -------
        Path
            Path to the merged GPKG file that was actually written to disk

        Raises
        ------
        DownloadError
            Not a ZIP, no GPKG inside, a requested layer missing in the
            package, two files with the same table name, or an I/O error
            while extracting, merging or writing the raw ZIP (a failed raw
            ZIP write also removes the merged GPKG: no data file is left
            without its sidecar)
        """
        # Read ZIP into memory
        zip_data = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            zip_data.write(chunk)
        zip_data.seek(0)

        try:
            with zipfile.ZipFile(zip_data, "r") as zf:
                all_gpkg = [f for f in zf.namelist() if f.endswith(".gpkg")]

                if not all_gpkg:
                    raise DownloadError(
                        f"No GPKG files found in ZIP. Contents: {zf.namelist()}"
                    )

                if layers is not None:
                    by_code = {
                        code: [f for f in all_gpkg if f"__OT_{code}_" in Path(f).name]
                        for code in layers
                    }
                    missing = [code for code, files in by_code.items() if not files]
                    if missing:
                        raise DownloadError(
                            f"Paczka BDOT10k nie zawiera warstw: {', '.join(missing)}"
                        )
                    all_gpkg = [f for files in by_code.values() for f in files]

                logger.debug(f"Found {len(all_gpkg)} layers to merge")

                # Create temp directory for extraction
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)

                    extracted_files = []
                    for gpkg_file in all_gpkg:
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

                    # Merge all layers into single GPKG
                    output_gpkg = output_path.with_suffix(".gpkg")
                    self._merge_gpkg_files(extracted_files, output_gpkg)
                    if raw_path is not None:
                        try:
                            self._write_raw_zip(zip_data, raw_path)
                        except BaseException as e:
                            # The caller writes the GPKG sidecar only after a
                            # successful return: drop the GPKG instead of
                            # leaving a data file without its sidecar.
                            output_gpkg.unlink(missing_ok=True)
                            if isinstance(e, OSError):
                                raise DownloadError(
                                    "Nie udalo sie zapisac oryginalnego ZIP "
                                    f"BDOT10k {raw_path.name}: {e}; plik "
                                    f"{output_gpkg.name} usuniety"
                                ) from e
                            raise
                    return output_gpkg

        except zipfile.BadZipFile as e:
            raise DownloadError(f"Invalid ZIP file: {e}") from e
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

    def _merge_gpkg_files(self, source_files: list[Path], output_path: Path) -> None:
        """
        Merge multiple GeoPackage files into one.

        Each source file is expected to have a single data table.
        All tables are copied to the output file, preserving geometry.

        Parameters
        ----------
        source_files : list[Path]
            List of source GPKG files to merge
        output_path : Path
            Output merged GPKG file

        Raises
        ------
        DownloadError
            No files, or a table name repeated across files (the merge
            would silently lose the second copy)
        """
        if not source_files:
            raise DownloadError("No files to merge")

        # SQLite ALWAYS writes in a local temp directory: on a CIFS/SMB share without
        # `nobrl`, byte-range locks ended the merge with `database is locked`. The
        # target receives the finished file (copy + os.replace).
        final_tmp = output_path.with_suffix(".gpkg.tmp")

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
                        self._copy_gpkg_layer(cursor, source_file)
                    conn.commit()
                finally:
                    conn.close()

                shutil.copyfile(local_path, final_tmp)

            # Atomic rename
            # os.replace: overwrites an existing file on Windows too (--force)
            final_tmp.replace(output_path)
            logger.info(f"Merged {len(source_files)} layers into {output_path}")

        except Exception:
            final_tmp.unlink(missing_ok=True)
            raise

    def _copy_gpkg_layer(self, cursor, source_path: Path) -> None:
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
                        f"jednym pliku ({source_path.name}) — scalenie zgubiloby dane"
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

    def _copy_rtree_index(self, cursor, table_name: str) -> None:
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
        return {
            "PTGN": "Grunty nieużytkowe",
            "PTKM": "Tereny komunikacyjne",
            "PTLZ": "Tereny leśne",
            "PTNZ": "Tereny niezabudowane",
            "PTPL": "Place",
            "PTRK": "Roślinność krzewiasta",
            "PTSO": "Składowiska",
            "PTTR": "Tereny rolne",
            "PTUT": "Uprawy trwałe",
            "PTWP": "Wody powierzchniowe",
            "PTWZ": "Tereny zabagnione",
            "PTZB": "Tereny zabudowane",
            "SWRS": "Rzeki i strumienie",
            "SWKN": "Kanały",
            "SWRM": "Rowy melioracyjne",
        }

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
