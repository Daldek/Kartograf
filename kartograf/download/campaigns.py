"""
GUGiK campaign identity (ADR-030) — a PL-ONLY mechanism.

A campaign is one GUGiK data delivery (an index (skorowidz) record). The
campaign directory is ``<acquisition date>_<id>``, where ``id`` is the first
numeric segment of the file name in the URL. File validation reads ASC
headers or TIFF signatures; ``measure_coverage`` additionally streams ASC
pixels or reads GeoTIFF mask windows from an already downloaded file.
``verify_record_vertical_crs`` checks the vertical datum declared by the
record (no IO).
"""

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError, ValidationError, YearRangeError
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

# Limit peak memory when counting pixels of large AAIGrid campaign files.
_COVERAGE_CHUNK = 8 * 1024 * 1024
_AAIGRID_HEADER_KEYS = frozenset(
    key.encode("ascii") for key in (*_AAIGRID_KEYS, "nodata_value")
)


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


def validate_campaign_args(
    campaigns: str | None, min_year: int | None, max_year: int | None
) -> None:
    """Validate a strategy (including the unresolved sentinel) and year bounds."""
    if campaigns is not None and campaigns not in CAMPAIGN_STRATEGIES:
        raise ValidationError(
            f"Nieznana strategia kampanii {campaigns!r} "
            f"(dozwolone: {', '.join(CAMPAIGN_STRATEGIES)})"
        )
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
    years in ``partial_years[godlo]`` (LAZ: only partial sheets there) are
    marked in the message.
    """
    sheets = {
        godlo: tuple(sorted(set(years))) for godlo, years in sorted(conflicts.items())
    }
    hints = year_range_hints(sheets, min_year, max_year)
    lines = [
        f"brak {subject} {year_range_label(min_year, max_year)} "
        f"dla {len(sheets)} z {total} {unit} — nic nie pobrano:"
    ]

    def year_text(godlo: str, year: int) -> str:
        if partial_years and year in partial_years.get(godlo, ()):
            return f"{year} (tylko arkusze niepelne)"
        return str(year)

    lines.extend(
        f"  {godlo}{' ' + labels[godlo] if labels and godlo in labels else ''}: "
        f"dostepne roczniki {', '.join(year_text(godlo, y) for y in years)}"
        for godlo, years in list(sheets.items())[:20]
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


def measure_coverage(path: Path, ext: str) -> float | None:
    """Return valid-pixel share of an ASC/GeoTIFF, or None without a TIFF mask.

    ASC values are streamed in bounded chunks; an incomplete or malformed
    raster raises DownloadError rather than reporting a misleading share.
    """
    if ext == ".asc":
        header = read_asc_header(path)
        try:
            cols, rows = header["ncols"], header["nrows"]
            if cols <= 0 or rows <= 0 or not cols.is_integer() or not rows.is_integer():
                raise ValueError("niepoprawne wymiary siatki")
            expected = int(cols * rows)
            nodata = header.get("nodata_value", -9999.0)
            count = valid = 0
            with path.open("rb") as stream:
                # AAIGrid permits five header lines if NODATA_value is absent.
                # Stop at the first non-header line, not after a fixed count.
                while True:
                    line = stream.readline()
                    parts = line.split(None, 1)
                    if not parts or parts[0].lower() not in _AAIGRID_HEADER_KEYS:
                        stream.seek(-len(line), 1)
                        break
                carry = b""
                while chunk := stream.read(_COVERAGE_CHUNK):
                    data = carry + chunk
                    cut = max(data.rfind(sep) for sep in (b" ", b"\n", b"\r", b"\t"))
                    if cut < 0:
                        carry = data
                        continue
                    for value in data[:cut].split():
                        count += 1
                        valid += float(value) != nodata
                    carry = data[cut + 1 :]
                for value in carry.split():
                    count += 1
                    valid += float(value) != nodata
            if count != expected:
                raise DownloadError(
                    f"{path.name}: ASC ma {count} komorek, oczekiwano {expected}"
                )
            return round(valid / expected, 4)
        except (OSError, ValueError, KeyError) as e:
            raise DownloadError(
                f"{path.name}: nie udalo sie zmierzyc pokrycia: {e}"
            ) from e
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
