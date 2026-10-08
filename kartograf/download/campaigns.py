"""
GUGiK campaign identity (ADR-030) — a PL-ONLY mechanism.

A campaign is one GUGiK data delivery (an index (skorowidz) record). The
campaign directory is ``<acquisition date>_<id>``, where ``id`` is the first
numeric segment of the file name in the URL. The module's only IO is
``verify_file_format`` (64 header bytes).
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from kartograf.exceptions import DownloadError, ValidationError

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
