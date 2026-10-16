"""
GUGiK campaign identity (ADR-030) — a PL-ONLY mechanism.

A campaign is one GUGiK data delivery (an index (skorowidz) record). Its
version label is ``<acquisition date>_<id>``, where ``id`` is the first
numeric segment of the file name in the URL. File validation reads ASC
headers, TIFF signatures and the signatures of the archive formats (ZIP,
Intergraph, DXF); ``measure_coverage`` additionally streams ASC pixels or
reads GeoTIFF mask windows from an already downloaded file.
``verify_record_vertical_crs`` checks the vertical datum declared by the
record (no IO).
"""

import contextlib
import hashlib
import logging
import re
import zipfile
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError, ValidationError, YearRangeError
from kartograf.sources.sidecar import read_asc_header
from kartograf.sources.variants import FORMATS

logger = logging.getLogger(__name__)

# Second link to the newest local flight declared full in the index (ADR-033).
FULL_SHEET_DIR = "full_sheet"

# record `format` field -> canonical extension (errata 2 N-2): every format of
# the variant registry (ASC grids and the archive formats, ADR-041)
FILE_FORMATS: Mapping[str, str] = {f.index_name: f.extension for f in FORMATS}

# Extensions whose valid-pixel share can be measured (``measure_coverage``).
RASTER_EXTENSIONS = (".asc", ".tif")

_ID = re.compile(r"(\d+)_")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# AAIGrid header keys per GDAL AAIGrid Identify
_AAIGRID_KEYS = (
    "ncols",
    "nrows",
    "xllcorner",
    "yllcorner",
    "xllcenter",
    "yllcenter",
    "cellsize",
    "dx",
    "dy",
)
_TIFF_SIGNATURES = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
_FORMAT_NAMES = {
    ".asc": "AAIGrid (ARC/INFO ASCII GRID)",
    ".tif": "TIFF",
    ".zip": "archiwum ZIP",
    ".ttn": "Intergraph TTN",
    ".grd": "Intergraph GRD",
    ".dxf": "DXF",
    ".dgn": "DGN",
}
# Compound endings of GUGiK archive file names before the sheet code test
# (B4): `<id>_<n>_<sheet>.xyz.zip`, `.zip.zip`, `_asc.zip`, `_tin.zip`.
_ARCHIVE_ENDINGS = (".zip.zip", ".xyz.zip", "_asc.zip", "_tin.zip")

# Share of the file extent that must lie inside the sheet frame (B4): a
# partial sheet lies inside, a neighbour or a file of another place does not.
MIN_FRAME_OVERLAP = 0.5

# Limit peak memory when counting pixels of large AAIGrid campaign files.
_COVERAGE_CHUNK = 8 * 1024 * 1024
_AAIGRID_HEADER_KEYS = frozenset(
    key.encode("ascii") for key in (*_AAIGRID_KEYS, "nodata_value")
)


def campaign_id_from_url(url: str) -> str:
    """'83233' from '.../83233_1744736_<sheet>.asc'.

    Without a leading '<digits>_' in the file name: 'u' + 8 hex chars of
    sha1(url).
    """
    name = PurePosixPath(urlparse(url).path).name
    m = _ID.match(name)
    if m:
        return m.group(1)
    return "u" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


def validate_year_bounds(min_year: int | None, max_year: int | None) -> None:
    """Validate inclusive acquisition-year bounds."""
    for name, year in (("min_year", min_year), ("max_year", max_year)):
        if year is not None and (
            not isinstance(year, int)
            or isinstance(year, bool)
            or not 1900 <= year <= 2100
        ):
            raise ValidationError(
                f"{name} musi byc liczba calkowita 1900..2100, otrzymano {year!r}"
            )
    if min_year is not None and max_year is not None and min_year > max_year:
        raise ValidationError(
            f"min_year ({min_year}) nie moze byc wiekszy niz max_year ({max_year})"
        )


def record_year(record) -> int | None:
    """Year from ``aktualnoscRok``, else ``aktualnosc[:4]``; non-digit -> None."""
    year = record.raw.get("aktualnoscRok") or record.aktualnosc[:4]
    return int(year) if year.isdigit() else None


def in_year_range(year: int | None, min_year: int | None, max_year: int | None) -> bool:
    """Whether a known year lies within the closed, optionally open range."""
    return (
        year is not None
        and (min_year is None or year >= min_year)
        and (max_year is None or year <= max_year)
    )


def year_range_label(min_year: int | None, max_year: int | None) -> str:
    """Polish label of a single year, lower bound, upper bound or closed range."""
    if min_year is not None and max_year is not None:
        return (
            f"z roku {min_year}"
            if min_year == max_year
            else f"z lat {min_year}-{max_year}"
        )
    if min_year is not None:
        return f"od roku {min_year}"
    if max_year is not None:
        return f"do roku {max_year}"
    raise ValueError("year_range_label wymaga co najmniej jednej granicy")


def year_range_hints(
    conflicts: Mapping[str, Sequence[int]], min_year: int | None, max_year: int | None
) -> tuple[str, ...]:
    """Suggest a one-sided bound that admits every conflicting sheet (6.2)."""
    if not conflicts:
        return ()
    newer = (
        [{year for year in years if year > max_year} for years in conflicts.values()]
        if max_year is not None
        else []
    )
    older = (
        [{year for year in years if year < min_year} for years in conflicts.values()]
        if min_year is not None
        else []
    )
    hints: list[str] = []
    if newer and all(newer):
        if min_year is not None:
            hints.append(f"--min-year {min_year} (rok {min_year} i nowsze)")
        else:
            upper = max(min(years) for years in newer)
            hints.append(f"--max-year {upper} (rok {upper} i starsze)")
    if older and all(older):
        if max_year is not None:
            hints.append(f"--max-year {max_year} (rok {max_year} i starsze)")
        else:
            lower = min(max(years) for years in older)
            hints.append(f"--min-year {lower} (rok {lower} i nowsze)")
    return tuple(hints)


def year_range_error(
    conflicts: Mapping[str, Sequence[int]],
    min_year: int | None,
    max_year: int | None,
    *,
    total: int,
    unit: str = "arkuszy",
    subject: str = "danych",
    labels: Mapping[str, str] | None = None,
    partial_years: Mapping[str, AbstractSet[int]] | None = None,
) -> YearRangeError:
    """Build the conflict message and retain every sheet's available years.

    ``subject`` and optional per-sheet ``labels`` let LAZ report reference
    tile vintages without duplicating the year-range formatting and hints;
    years in ``partial_years[sheet]`` (LAZ: only partial sheets there) are
    marked in the message.
    """
    sheets = {
        sheet: tuple(sorted(set(years))) for sheet, years in sorted(conflicts.items())
    }
    hints = year_range_hints(sheets, min_year, max_year)
    lines = [
        f"brak {subject} {year_range_label(min_year, max_year)} "
        f"dla {len(sheets)} z {total} {unit} - nic nie pobrano:"
    ]

    def year_text(sheet: str, year: int) -> str:
        if partial_years and year in partial_years.get(sheet, ()):
            return f"{year} (tylko arkusze niepelne)"
        return str(year)

    lines.extend(
        f"  {sheet}{' ' + labels[sheet] if labels and sheet in labels else ''}: "
        f"dostepne roczniki {', '.join(year_text(sheet, y) for y in years)}"
        for sheet, years in list(sheets.items())[:20]
    )
    if len(sheets) > 20:
        lines.append(f"  ... i {len(sheets) - 20} innych")
    if hints:
        lines.append(f"Podpowiedz: {' albo '.join(hints)}")
    return YearRangeError(
        "\n".join(lines),
        sheets=sheets,
        min_year=min_year,
        max_year=max_year,
        hints=hints,
    )


@dataclass(frozen=True)
class CampaignRef:
    id: str  # digits or 'u'+8 hex — path-safe
    date: str  # acquisition date, YYYY-MM-DD (validated)
    dt_pzgik: str | None
    url: str
    survey_work_id: str | None  # numerZgloszeniaPracy
    source: str | None  # zrDanych / zrodloDanych
    full_sheet: bool | None
    file_format: str | None  # record `format` field; None = no field (orto, old cache)

    @classmethod
    def from_record(cls, record) -> "CampaignRef":
        """Build from an index record (duck typing: url, sheet, aktualnosc,
        dt_pzgik, full_sheet, raw). An aktualnosc outside YYYY-MM-DD raises
        DownloadError — the server value ends up in a path."""
        date = record.aktualnosc
        if not isinstance(date, str) or not _DATE.fullmatch(date):
            raise DownloadError(
                f"Rekord skorowidza ma niepoprawna aktualnosc {date!r} "
                f"(oczekiwano RRRR-MM-DD)",
                sheet=getattr(record, "sheet", None),
            )
        raw = record.raw or {}
        return cls(
            id=campaign_id_from_url(record.url),
            date=date,
            dt_pzgik=record.dt_pzgik,
            url=record.url,
            survey_work_id=raw.get("numerZgloszeniaPracy"),
            source=raw.get("zrDanych") or raw.get("zrodloDanych"),
            full_sheet=record.full_sheet,
            file_format=raw.get("format"),
        )

    @classmethod
    def from_sidecar(cls, meta: dict) -> "CampaignRef | None":
        """Rebuild from a version sidecar (``extra.campaign`` +
        ``extra.source.url``); ``None`` when it describes no campaign."""
        extra = meta.get("extra")
        campaign = extra.get("campaign") if isinstance(extra, dict) else None
        source = extra.get("source") if isinstance(extra, dict) else None
        if not isinstance(campaign, dict) or not isinstance(source, dict):
            return None
        date, url = campaign.get("date"), source.get("url")
        if not isinstance(date, str) or not _DATE.fullmatch(date) or not url:
            return None
        return cls(
            id=str(campaign.get("id") or campaign_id_from_url(str(url))),
            date=date,
            dt_pzgik=campaign.get("pzgik_date"),
            url=str(url),
            survey_work_id=campaign.get("survey_work_id"),
            source=campaign.get("source"),
            full_sheet=campaign.get("full_sheet"),
            file_format=None,
        )

    @property
    def dirname(self) -> str:
        return f"{self.date}_{self.id}"

    @property
    def year(self) -> int:
        return int(self.date[:4])

    @property
    def sort_key(self) -> tuple[str, str, str]:
        """(aktualnosc, dt_pzgik, url) — ADR-028 ordering."""
        return (self.date, self.dt_pzgik or "", self.url)

    def to_extra(self) -> dict:
        """``extra.campaign`` of the campaign sidecar (English keys, ADR-031)."""
        return {
            "id": self.id,
            "date": self.date,
            "survey_work_id": self.survey_work_id,
            "source": self.source,
            "full_sheet": self.full_sheet,
            "pzgik_date": self.dt_pzgik,
        }


# Value of the record field ``ukladWspolrzednychPionowych`` per requested
# vertical CRS (``vertical_crs`` of GugikProvider/GugikNmptProvider). Measured
# on raw index responses (tests/fixtures/gugik_skorowidz/real_2026_10_06/):
# KRON86 endpoints give only "PL-KRON86-NH"; EVRF2007 endpoints (NMT 1 m,
# NMT 5 m, NMPT) only "PL-EVRF2007-NH".
RECORD_VERTICAL_CRS: Mapping[str, str] = {
    "KRON86": "PL-KRON86-NH",
    "EVRF2007": "PL-EVRF2007-NH",
}


def verify_record_vertical_crs(record, vertical_crs: str | None, sheet: str) -> None:
    """The vertical datum declared by the record must be the requested one.

    The datum is chosen only by the endpoint (one WMS index per datum); the
    record field ``ukladWspolrzednychPionowych`` is the check that the
    endpoint served what it should. No field (or empty) = cannot verify:
    accepted with a debug log. ``vertical_crs`` ``None`` (orto) or outside
    ``RECORD_VERTICAL_CRS`` = nothing to compare. Duck typing: ``url`` and
    optional ``raw``.

    Raises
    ------
    DownloadError
        The record declares another datum (before any download).
    """
    expected = RECORD_VERTICAL_CRS.get(vertical_crs) if vertical_crs else None
    if expected is None:
        return
    raw = getattr(record, "raw", None) or {}
    declared = (raw.get("ukladWspolrzednychPionowych") or "").strip()
    if not declared:
        logger.debug(
            "%s: rekord skorowidza bez ukladWspolrzednychPionowych - uklad "
            "wysokosci niesprawdzony (%s)",
            sheet,
            record.url,
        )
        return
    if declared.upper() != expected:
        raise DownloadError(
            f"{sheet}: rekord skorowidza deklaruje uklad wysokosci {declared}, "
            f"a zadano {vertical_crs} (oczekiwano {expected}) - plik nie "
            f"zostal pobrany: {record.url}",
            sheet=sheet,
        )


def campaign_extension(ref: CampaignRef, default_ext: str) -> str:
    """Campaign file extension from the record `format` field (not the URL).

    No field -> default_ext (orto, old cache entries); a known format
    matching the product -> default_ext; otherwise DownloadError BEFORE
    the download.
    """
    fmt = ref.file_format
    if fmt is None:
        return default_ext
    known = FILE_FORMATS.get(fmt)
    if known is not None and known.lower() == default_ext.lower():
        return default_ext
    raise DownloadError(
        f"Kampania {ref.dirname}: format {fmt!r} nieobslugiwany "
        f"(produkt: {default_ext})"
    )


def _intergraph(head: bytes) -> bool:
    """IGDS header element (type 9) of Intergraph DGN v7/GRD: level byte
    ``0x08`` with optional flags, type ``0x09``."""
    return len(head) >= 2 and head[0] & 0x3F == 0x08 and head[1] == 0x09


def verify_file_format(path: Path, ext: str) -> None:
    """Verify the file content after download.

    '.asc' -> AAIGrid header, '.tif' -> TIFF/BigTIFF signature, archives
    (ADR-041): '.zip' -> a complete ZIP (central directory readable, so a
    truncated transfer fails), '.ttn' -> ``TTN`` signature, '.grd'/'.dgn' ->
    Intergraph header (DGN v8: OLE signature), '.dxf' -> ``SECTION`` in the
    first group codes. A mismatch, another extension or a read error
    (``OSError``) raises DownloadError.
    """
    if ext not in _FORMAT_NAMES:
        raise DownloadError(f"{path.name}: brak weryfikacji formatu dla {ext!r}")
    try:
        with path.open("rb") as fh:
            head = fh.read(64)
        if ext == ".zip":
            ok = zipfile.is_zipfile(path)
        elif ext == ".asc":
            words = head.lstrip().lower().split(None, 1)
            ok = bool(words) and words[0].decode("ascii", "ignore") in _AAIGRID_KEYS
        elif ext == ".tif":
            ok = head.startswith(_TIFF_SIGNATURES)
        elif ext == ".ttn":
            ok = head.startswith(b"TTN")
        elif ext == ".dxf":
            ok = b"SECTION" in head.upper() and head.lstrip()[:1] == b"0"
        elif ext == ".dgn":
            ok = _intergraph(head) or head.startswith(b"\xd0\xcf\x11\xe0")
        else:  # .grd
            ok = _intergraph(head)
    except OSError as e:
        raise DownloadError(f"{path.name}: odczyt do weryfikacji formatu: {e}") from e
    if not ok:
        raise DownloadError(
            f"{path.name}: tresc nie jest {_FORMAT_NAMES[ext]} "
            f"(naglowek: {head[:16]!r})"
        )


class AscCoverage:
    """Valid-cell share of an AAIGrid fed as consecutive raw byte chunks.

    One streaming pass serves both ``measure_coverage`` and the version store
    commit, which hashes the same chunks (D20). The header ends at the first
    line whose first word is not an AAIGrid header key; a missing
    ``NODATA_value`` means -9999. Tokens split across chunks are carried over.
    """

    def __init__(self, name: str):
        self._name = name
        self._header: dict[str, float] = {}
        self._in_header = True
        self._carry = b""
        self._nodata = -9999.0
        self._count = 0
        self._valid = 0
        self._error: ValueError | None = None

    def feed(self, chunk: bytes) -> None:
        """Consume the next chunk of the file."""
        if self._error is not None:
            return
        data = self._carry + chunk
        if self._in_header:
            data = self._consume_header(data, final=False)
            if self._in_header:
                self._carry = data
                return
        cut = max(data.rfind(sep) for sep in (b" ", b"\n", b"\r", b"\t"))
        if cut < 0:
            self._carry = data
            return
        self._count_values(data[:cut])
        self._carry = data[cut + 1 :]

    def result(self) -> float:
        """Valid share rounded to 4 places; ``DownloadError`` when malformed."""
        if self._error is None:
            data, self._carry = self._carry, b""
            if self._in_header:
                data = self._consume_header(data, final=True)
            self._count_values(data)
        try:
            if self._error is not None:
                raise self._error
            cols, rows = self._header["ncols"], self._header["nrows"]
            if cols <= 0 or rows <= 0 or not cols.is_integer() or not rows.is_integer():
                raise ValueError("niepoprawne wymiary siatki")
        except (ValueError, KeyError) as e:
            raise DownloadError(
                f"{self._name}: nie udalo sie zmierzyc pokrycia: {e}"
            ) from e
        expected = int(cols * rows)
        if self._count != expected:
            raise DownloadError(
                f"{self._name}: ASC ma {self._count} komorek, oczekiwano {expected}"
            )
        return round(self._valid / expected, 4)

    def _consume_header(self, data: bytes, *, final: bool) -> bytes:
        """Parse complete header lines; return the unconsumed rest."""
        while True:
            end = data.find(b"\n")
            if end < 0 and not final:
                return data
            line = data if end < 0 else data[: end + 1]
            parts = line.split()
            if not parts or parts[0].lower() not in _AAIGRID_HEADER_KEYS:
                self._in_header = False
                self._nodata = self._header.get("nodata_value", -9999.0)
                return data
            if len(parts) == 2:
                with contextlib.suppress(ValueError):
                    self._header[parts[0].lower().decode("ascii")] = float(parts[1])
            data = b"" if end < 0 else data[end + 1 :]

    def _count_values(self, data: bytes) -> None:
        nodata = self._nodata
        try:
            for value in data.split():
                self._count += 1
                self._valid += float(value) != nodata
        except ValueError as e:
            self._error = e


def measure_coverage(path: Path, ext: str) -> float | None:
    """Return valid-pixel share of an ASC/GeoTIFF, or None without a TIFF mask.

    ASC values are streamed in bounded chunks; an incomplete or malformed
    raster raises DownloadError rather than reporting a misleading share.
    """
    if ext == ".asc":
        counter = AscCoverage(path.name)
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(_COVERAGE_CHUNK):
                    counter.feed(chunk)
        except OSError as e:
            raise DownloadError(
                f"{path.name}: nie udalo sie zmierzyc pokrycia: {e}"
            ) from e
        return counter.result()
    if ext == ".tif":
        import numpy as np
        import rasterio
        from rasterio.enums import ColorInterp, MaskFlags

        try:
            with rasterio.open(path) as dataset:
                if dataset.nodata is None and (
                    MaskFlags.alpha not in dataset.mask_flag_enums[0]
                    and ColorInterp.alpha not in dataset.colorinterp
                ):
                    return None
                valid = total = 0
                for _, window in dataset.block_windows(1):
                    mask = dataset.read_masks(1, window=window)
                    valid += int(np.count_nonzero(mask))
                    total += mask.size
                return round(valid / total, 4)
        except (OSError, ValueError, rasterio.errors.RasterioError) as e:
            raise DownloadError(
                f"{path.name}: nie udalo sie zmierzyc pokrycia: {e}"
            ) from e
    raise DownloadError(f"{path.name}: brak pomiaru pokrycia dla {ext!r}")


def _alnum(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text)


def verify_record_url(url: str, sheet: str, suffix: str = "") -> None:
    """The record URL file name must end with the sheet code (B4).

    GUGiK names files ``<id>_<number>_<sheet>.<ext>``; a URL without the
    sheet code (or with another one) points to an unknown file. Both codes
    are compared in canonical form (``SheetParser.sheet``). Archive names
    (full WFS inventory 2026-10-15): compound endings (``.xyz.zip``,
    ``.zip.zip``, ``_asc.zip``, ``_tin.zip``), an ``NMT-`` prefix
    (``NMT-N-33-77-B-c-3-3.zip``) and the code without separators
    (``NMT-N34121Cb33.xyz.zip``) name the sheet too; a name of another
    sheet (2 archive records of the inventory) is still an error.
    ``suffix``: the file name ends with the sheet code followed by it,
    compared without case (a view direction of the oblique orthophotomap:
    ``_n`` for ``..._7.125.11.08_N.tif``).
    """
    name = PurePosixPath(urlparse(url).path).name
    lowered = name.lower()
    ending = next((e for e in _ARCHIVE_ENDINGS if lowered.endswith(e)), None)
    stem = name[: -len(ending)] if ending else PurePosixPath(name).stem
    if suffix:
        if not stem.lower().endswith(suffix.lower()):
            raise DownloadError(
                f"URL rekordu skorowidza nie konczy sie godlem {sheet} "
                f"z przyrostkiem {suffix}: {url}",
                sheet=sheet,
            )
        stem = stem[: -len(suffix)]
    token = stem.rsplit("_", 1)[-1]
    if token.upper().startswith("NMT-"):
        token = token[4:]
    expected = SheetParser(sheet).sheet
    try:
        named: str | None = SheetParser(token).sheet
    except ValidationError:
        named = None
    if named != expected and _alnum(token) != _alnum(expected):
        raise DownloadError(
            f"URL rekordu skorowidza nie zawiera godla {sheet}: {url}", sheet=sheet
        )


def verify_sheet_extent(path: Path, sheet: str, ext: str) -> None:
    """The ASC header extent must lie in the sheet frame (B4; '.asc' only).

    At least ``MIN_FRAME_OVERLAP`` of the file extent must lie inside the
    frame. The frame is taken in the FILE's CRS (the rule of
    ``sidecar.pl_sheet_horizontal_crs``): x < 1e6 means EPSG:2180 - also a
    PL-2000 sheet that GUGiK published in EPSG:2180 (E17); otherwise the
    native CRS of the sheet code (PL-2000 zone). Other extensions are not
    checked; an unreadable or incomplete header raises DownloadError.
    """
    if ext != ".asc":
        return
    h = read_asc_header(path)
    try:
        cell = h["cellsize"]
        half = cell / 2
        x0 = h["xllcorner"] if "xllcorner" in h else h["xllcenter"] - half
        y0 = h["yllcorner"] if "yllcorner" in h else h["yllcenter"] - half
        x1, y1 = x0 + h["ncols"] * cell, y0 + h["nrows"] * cell
    except KeyError as e:
        raise DownloadError(
            f"{path.name}: niepelny naglowek ASC (brak {e}) - nie mozna "
            f"sprawdzic zasiegu arkusza {sheet}",
            sheet=sheet,
        ) from e
    parser = SheetParser(sheet)
    frame = parser.get_bbox(crs="EPSG:2180") if x0 < 1e6 else parser.get_bbox()
    ix = max(0.0, min(x1, frame.max_x) - max(x0, frame.min_x))
    iy = max(0.0, min(y1, frame.max_y) - max(y0, frame.min_y))
    area = (x1 - x0) * (y1 - y0)
    if area <= 0 or ix * iy < MIN_FRAME_OVERLAP * area:
        raise DownloadError(
            f"{path.name}: zasieg pliku ({x0:.0f}, {y0:.0f}, {x1:.0f}, {y1:.0f}) "
            f"nie pokrywa sie z rama godla {sheet} ({frame.min_x:.0f}, "
            f"{frame.min_y:.0f}, {frame.max_x:.0f}, {frame.max_y:.0f}, {frame.crs})",
            sheet=sheet,
        )
