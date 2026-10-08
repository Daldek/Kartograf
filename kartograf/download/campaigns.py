"""
GUGiK campaign identity (ADR-030) — a PL-ONLY mechanism.

A campaign is one GUGiK data delivery (an index (skorowidz) record). The
campaign directory is ``<acquisition date>_<id>``, where ``id`` is the first
numeric segment of the file name in the URL. The module's only IO is
``verify_file_format`` (64 header bytes) and ``verify_sheet_extent`` (the
ASC header). ``verify_record_vertical_crs`` checks the vertical datum
declared by the record (no IO).
"""

import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.sources.sidecar import read_asc_header

logger = logging.getLogger(__name__)

CAMPAIGNS_DIR = "kampanie"
CAMPAIGN_STRATEGIES = ("newest", "all")

# record `format` field -> canonical extension (errata 2 N-2)
FILE_FORMATS: Mapping[str, str] = {"ARC/INFO ASCII GRID": ".asc"}

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
_FORMAT_NAMES = {".asc": "AAIGrid (ARC/INFO ASCII GRID)", ".tif": "TIFF"}

# Share of the file extent that must lie inside the sheet frame (B4): a
# partial sheet lies inside, a neighbour or a file of another place does not.
MIN_FRAME_OVERLAP = 0.5


def campaign_id_from_url(url: str) -> str:
    """'83233' from '.../83233_1744736_<godlo>.asc'.

    Without a leading '<digits>_' in the file name: 'u' + 8 hex chars of
    sha1(url).
    """
    name = PurePosixPath(urlparse(url).path).name
    m = _ID.match(name)
    if m:
        return m.group(1)
    return "u" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


def validate_campaign_args(campaigns: str, min_year: int | None) -> None:
    """Raise ValidationError for a strategy outside CAMPAIGN_STRATEGIES, or
    a min_year that is not an int (bool included) or is outside 1900..2100."""
    if campaigns not in CAMPAIGN_STRATEGIES:
        raise ValidationError(
            f"Nieznana strategia kampanii {campaigns!r} "
            f"(dozwolone: {', '.join(CAMPAIGN_STRATEGIES)})"
        )
    if min_year is not None and (
        not isinstance(min_year, int)
        or isinstance(min_year, bool)
        or not 1900 <= min_year <= 2100
    ):
        raise ValidationError(
            f"min_year musi byc liczba calkowita 1900..2100, otrzymano {min_year!r}"
        )


@dataclass(frozen=True)
class CampaignRef:
    id: str  # digits or 'u'+8 hex — path-safe
    date: str  # acquisition date, YYYY-MM-DD (validated)
    dt_pzgik: str | None
    url: str
    zgloszenie: str | None  # numerZgloszeniaPracy
    source: str | None  # zrDanych / zrodloDanych
    full_sheet: bool | None
    file_format: str | None  # record `format` field; None = no field (orto, old cache)

    @classmethod
    def from_record(cls, record) -> "CampaignRef":
        """Build from an index record (duck typing: url, godlo, aktualnosc,
        dt_pzgik, full_sheet, raw). An aktualnosc outside YYYY-MM-DD raises
        DownloadError — the server value ends up in a path."""
        date = record.aktualnosc
        if not isinstance(date, str) or not _DATE.fullmatch(date):
            raise DownloadError(
                f"Rekord skorowidza ma niepoprawna aktualnosc {date!r} "
                f"(oczekiwano RRRR-MM-DD)",
                godlo=getattr(record, "godlo", None),
            )
        raw = record.raw or {}
        return cls(
            id=campaign_id_from_url(record.url),
            date=date,
            dt_pzgik=record.dt_pzgik,
            url=record.url,
            zgloszenie=raw.get("numerZgloszeniaPracy"),
            source=raw.get("zrDanych") or raw.get("zrodloDanych"),
            full_sheet=record.full_sheet,
            file_format=raw.get("format"),
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
            "survey_work_id": self.zgloszenie,
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


def verify_record_vertical_crs(record, vertical_crs: str | None, godlo: str) -> None:
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
            "%s: rekord skorowidza bez ukladWspolrzednychPionowych — uklad "
            "wysokosci niesprawdzony (%s)",
            godlo,
            record.url,
        )
        return
    if declared.upper() != expected:
        raise DownloadError(
            f"{godlo}: rekord skorowidza deklaruje uklad wysokosci {declared}, "
            f"a zadano {vertical_crs} (oczekiwano {expected}) — plik nie "
            f"zostal pobrany: {record.url}",
            godlo=godlo,
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


def verify_file_format(path: Path, ext: str) -> None:
    """Verify the file content after download (first 64 bytes).

    '.asc' -> AAIGrid header, '.tif' -> TIFF/BigTIFF signature. A mismatch,
    an extension outside {'.asc', '.tif'} or a read error (``OSError``)
    raises DownloadError.
    """
    if ext not in _FORMAT_NAMES:
        raise DownloadError(f"{path.name}: brak weryfikacji formatu dla {ext!r}")
    try:
        with path.open("rb") as fh:
            head = fh.read(64)
    except OSError as e:
        raise DownloadError(f"{path.name}: odczyt do weryfikacji formatu: {e}") from e
    if ext == ".asc":
        words = head.lstrip().lower().split(None, 1)
        ok = bool(words) and words[0].decode("ascii", "ignore") in _AAIGRID_KEYS
    else:
        ok = head.startswith(_TIFF_SIGNATURES)
    if not ok:
        raise DownloadError(
            f"{path.name}: tresc nie jest {_FORMAT_NAMES[ext]} "
            f"(naglowek: {head[:16]!r})"
        )


def verify_record_url(url: str, godlo: str) -> None:
    """The record URL file name must end with the sheet code (B4).

    GUGiK names files ``<id>_<number>_<godlo>.<ext>``; a URL without the
    sheet code (or with another one) points to an unknown file. Both codes
    are compared in canonical form (``SheetParser.godlo``).
    """
    stem = PurePosixPath(urlparse(url).path).stem
    token = stem.rsplit("_", 1)[-1]
    try:
        named = SheetParser(token).godlo
    except ValidationError:
        named = None
    if named != SheetParser(godlo).godlo:
        raise DownloadError(
            f"URL rekordu skorowidza nie zawiera godla {godlo}: {url}", godlo=godlo
        )


def verify_sheet_extent(path: Path, godlo: str, ext: str) -> None:
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
            f"{path.name}: niepelny naglowek ASC (brak {e}) — nie mozna "
            f"sprawdzic zasiegu arkusza {godlo}",
            godlo=godlo,
        ) from e
    parser = SheetParser(godlo)
    frame = parser.get_bbox(crs="EPSG:2180") if x0 < 1e6 else parser.get_bbox()
    ix = max(0.0, min(x1, frame.max_x) - max(x0, frame.min_x))
    iy = max(0.0, min(y1, frame.max_y) - max(y0, frame.min_y))
    area = (x1 - x0) * (y1 - y0)
    if area <= 0 or ix * iy < MIN_FRAME_OVERLAP * area:
        raise DownloadError(
            f"{path.name}: zasieg pliku ({x0:.0f}, {y0:.0f}, {x1:.0f}, {y1:.0f}) "
            f"nie pokrywa sie z rama godla {godlo} ({frame.min_x:.0f}, "
            f"{frame.min_y:.0f}, {frame.max_x:.0f}, {frame.max_y:.0f}, {frame.crs})",
            godlo=godlo,
        )
