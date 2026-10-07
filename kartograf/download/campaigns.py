"""
Tozsamosc kampanii GUGiK (ADR-030) — mechanizm WYLACZNIE PL.

Kampania = jedna dostawa danych GUGiK (rekord skorowidza). Katalog kampanii
to ``<aktualnosc>_<id>``, gdzie ``id`` to pierwszy segment liczbowy nazwy
pliku w URL. Jedyne IO modulu: ``verify_file_format`` (64 bajty naglowka).
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

# pole `format` rekordu -> rozszerzenie kanoniczne (errata 2 N-2)
FILE_FORMATS: Mapping[str, str] = {"ARC/INFO ASCII GRID": ".asc"}

_ID = re.compile(r"(\d+)_")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Klucze naglowka AAIGrid wg GDAL AAIGrid Identify
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
    """'83233' z '.../83233_1744736_<godlo>.asc'.

    Bez wiodacego '<cyfry>_' w nazwie pliku: 'u' + 8 znakow hex sha1(url).
    """
    name = PurePosixPath(urlparse(url).path).name
    m = _ID.match(name)
    if m:
        return m.group(1)
    return "u" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


def validate_campaign_args(campaigns: str, min_year: int | None) -> None:
    """ValidationError: strategia spoza CAMPAIGN_STRATEGIES, min_year nie-int
    (takze bool) albo poza 1900..2100."""
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
    id: str  # cyfry albo 'u'+8 hex — bezpieczne w sciezce
    date: str  # aktualnosc, RRRR-MM-DD (walidowane)
    dt_pzgik: str | None
    url: str
    zgloszenie: str | None  # numerZgloszeniaPracy
    source: str | None  # zrDanych / zrodloDanych
    full_sheet: bool | None
    file_format: (
        str | None
    )  # pole `format` rekordu; None = brak pola (orto, stary cache)

    @classmethod
    def from_record(cls, record) -> "CampaignRef":
        """Z rekordu skorowidza (duck typing: url, godlo, aktualnosc, dt_pzgik,
        full_sheet, raw). aktualnosc spoza RRRR-MM-DD -> DownloadError —
        wartosc z serwera trafia do sciezki."""
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
        """(aktualnosc, dt_pzgik, url) — kolejnosc ADR-028."""
        return (self.date, self.dt_pzgik or "", self.url)

    def to_extra(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "zgloszenie": self.zgloszenie,
            "source": self.source,
            "full_sheet": self.full_sheet,
            "dt_pzgik": self.dt_pzgik,
        }


def campaign_extension(ref: CampaignRef, default_ext: str) -> str:
    """Rozszerzenie pliku kampanii z pola `format` rekordu (nie z URL).

    Brak pola -> default_ext (orto, stare wpisy cache); znany format zgodny
    z produktem -> default_ext; inaczej DownloadError PRZED pobraniem.
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
    """Weryfikacja tresci pliku po pobraniu (64 pierwsze bajty).

    '.asc' -> naglowek AAIGrid, '.tif' -> sygnatura TIFF/BigTIFF. Niezgodnosc,
    rozszerzenie spoza {'.asc', '.tif'} albo blad odczytu (``OSError``)
    -> DownloadError.
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
