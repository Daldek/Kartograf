"""
Availability report of elevation data per the GUGiK index and the CUZK files
(spec 4, ADR-041; CZ and ``country="auto"``: plan B, decisions 9-10).

``check_availability`` answers, before any download, for which years, sheet
systems, resolutions, height systems and formats an area has a COMPLETE set
of full sheets: PL NMT/NMPT - the sheet variants of the registry
(``kartograf.sources.variants``: ASC grids and the archive formats
downloaded as source files), LAZ - tiles. It reads the same WFS indexes with
the same record parser as the sheet download
(``providers/pl/skorowidz_wfs.py``) and the PRG land mask
(``providers/pl/prg.py``); no data file is ever requested.

Combinations: NMT/NMPT (layer year, PL-1992|PL-2000, label K2, height system,
format) of a registered variant; LAZ (layer year, sheet system, height
system). Records Kartograf does not download (outside the registry, format
inconsistent with the file, sheet code outside ``SheetParser``, no https URL
or CRS) are no combination: one ``INDEX_UNSUPPORTED`` notice names them.

A record belongs to the area when its frame overlaps it by more than an edge
sliver (``overlaps_area`` - the rule of the archive sheet selection, so a
neighbour sharing an edge never counts). Completeness on a 1 m grid aligned
to whole metres of the EPSG:2180 envelope of the area, pixel centres, row
strips of ``_STRIP_PX``: ``target`` = area & land (PRG A00 minus W02/W03); a
combination is ``complete`` when no target pixel lies outside the frames of
its full (``TAK``) records, ``uncovered_m2`` = target pixels outside every
frame of the combination. No threshold.

CZ (CUZK) has no surveys or completeness flags: a combination is a variant
with a file channel in the native height system of its files (NMT: DMR 4G,
NMPT: DMP OK, LAZ: four models; SM5 sheets in S-JTSK/Bpv, TM33 tiles in
ETRS89/EVRF2007). Its sheets are those of the ``KladyMapovychListu`` index in
the CZ part of the area (``SheetIndex.file_sheets`` - the rule of the LAZ
download, in the CRS of the sheet system), each checked by one ``HEAD`` of its
file: 200 = a file (``Last-Modified`` = publication date, ``Content-Length``
= size), 404 = no file (``sheets_missing``; ``uncovered_m2`` = the part of the
reported area in their frames), anything else = ``DownloadError``.
``country="auto"`` reports the PL and CZ parts of the area (rectangular country
envelopes, ``split_bbox_by_country``) in one report.

The index answers, the feature types, the land mask, the CZ sheets and the
``HEAD`` answers go through the metadata cache (``index_area_cache``, TTL as
the index records): a repeated report asks no service; ``force=True`` asks
again and overwrites the entries.
"""

import functools
import json
import math
import shlex
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

from kartograf import _clock
from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords
from kartograf.core.coverage import (
    AREA_EPS,
    Polygon,
    clip_convex,
    expand_convex,
    normalize_convex,
    polygon_area,
    rectangle,
)
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.download.area import (
    bbox_to_2180,
    geometry_envelope,
    resolve_geometry_layer,
)
from kartograf.download.arguments import require_bool
from kartograf.download.campaigns import in_year_range, year_range_label
from kartograf.download.countries import country_bbox, split_bbox_by_country
from kartograf.download.options import (
    product_choices,
    validate_area_choice,
    year_bounds,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import (
    AUTO_NARROWED_TO_PL,
    CHECK_FAILED,
    CZ_SERVICE_ONLY,
    INDEX_UNSUPPORTED,
    Notice,
    NoticeSink,
)
from kartograf.providers.cuzk.client import wkid
from kartograf.providers.cuzk.raster import bbox_to_crs
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.providers.pl.gugik_laz import laz_tile
from kartograf.providers.pl.prg import ABROAD, LAND, LandMask, fetch_land_mask
from kartograf.providers.pl.skorowidz import metres
from kartograf.providers.pl.skorowidz_wfs import (
    EDGE_TOLERANCE_M,
    WfsIndex,
    area_envelope,
    feature_footprint,
    feature_text,
    index_feature_issue,
    localname,
    overlaps_area,
    parse_index_feature,
    sheet_frame_2180,
    time_position,
    type_year,
)
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import (
    CZ_SYSTEM_CRS,
    channel_for,
    parse_pl_system,
    vertical_crs_code,
)
from kartograf.sources.variants import (
    CZ_MODELS,
    FORMATS,
    IndexRef,
    ProductVariant,
    cz_sheet_system,
    resolution_label,
    source_format,
    variants,
)
from kartograf.transform.crs import CONTENT_POLICY, build_pinned_transform
from kartograf.transport.http import MAX_RETRIES, SessionPerThread, head_signal

AVAILABILITY_SCHEMA = "kartograf-availability/1"
# Products of the report (the `elevation` group).
AVAILABILITY_PRODUCTS = ("nmt", "nmpt", "laz")
# Countries of the report (`--country`; a sheet code names its country).
AVAILABILITY_COUNTRIES = {
    "pl": "pl (GUGiK)",
    "cz": "cz (CUZK)",
    "auto": "auto (czesci PL i CZ wg prostokatnych obwiedni krajow w jednym raporcie)",
}
COUNTRY_CHOICES = ", ".join(AVAILABILITY_COUNTRIES.values())

# Timeout (s) of every index and PRG request (as the sheet providers).
_TIMEOUT = 30
# Timeout (s) of the CUZK file HEADs (as the CUZK providers and their index
# client, ``CuzkClient``).
_CZ_TIMEOUT = 60
# Parallel HEAD requests of the CZ files (plan B, decision 9).
_HEAD_WORKERS = 8
# CRS of the CZ part of the report (``AvailabilityArea.crs``, ``auto`` split).
_CZ_CRS = "EPSG:5514"
_CZ_HORIZONTAL = {"sm5": "S-JTSK", "tm33": "ETRS89-TM33"}
# Year bounds choose GUGiK index layers; CUZK files carry a publication date.
_CZ_NO_YEARS = (
    "CZ (CUZK) nie publikuje lat nalotu - --year/--min-year/--max-year dotycza "
    "tylko PL (raport CZ podaje date publikacji plikow)"
)
# Pixels per row strip of the completeness grid (as LandMask.apply).
_STRIP_PX = 4_000_000
_HORIZONTAL = {"1992": "PL-1992", "2000": "PL-2000"}
_FORMAT_ORDER = {f.token: i for i, f in enumerate(FORMATS)}
# Why an index record is not downloadable (INDEX_UNSUPPORTED texts).
_REASONS = {
    "sheet": "godla spoza ukladow arkuszy PL-1992/PL-2000",
    "url": "bez adresu https pliku",
    "crs": "bez ukladu wspolrzednych",
    "file": "format rekordu niezgodny z plikiem",
    "format": "format spoza rejestru wariantow",
    "registry": "wariant spoza rejestru (rozdzielczosc albo uklad wysokosci)",
}


@dataclass(frozen=True)
class AvailabilityArea:
    """The area of a report in one country.

    ``bounds`` = envelope of the area in ``crs``; ``area_m2`` = the area
    inside the country, ``land_m2`` = its land (PL: PRG A00 minus the sea
    W02/W03) - the part every combination is measured against. CZ: ``crs``
    EPSG:5514, ``area_m2`` = the rectangle of the CZ part (a sheet code: its
    frame), ``land_m2 = area_m2`` (no land mask).
    """

    country: str
    crs: str
    bounds: tuple[float, float, float, float]
    area_m2: float
    land_m2: float


@dataclass(frozen=True)
class AvailabilityCombination:
    """One downloadable combination of the area (spec 4.1).

    ``source`` = descriptor key (sidecar ``dataset``); ``year`` = year of the
    index layer; ``acquisition_dates``/``published`` = min/max ``akt_data``/
    ``dt_pzgik`` of its records; ``campaigns`` = survey work ids
    (``nr_zglosz``). ``complete``: the land of the area lies entirely in its
    full sheets (``sheets_full``: a full record; ``sheets_partial``: only
    partial records). ``uncovered_m2``: land outside every sheet of the
    combination. ``download_hint``: commands to paste after ``kartograf ``
    or ``kartograf project add NAME `` (without ``--output``).
    ``sheets_missing`` and ``size_bytes`` are CZ fields (PL: empty/``None``).

    CZ: ``year``/``acquisition_dates`` ``None``, ``campaigns`` empty,
    ``published`` = min/max ``Last-Modified`` of the files (``YYYY-MM-DD``),
    ``sheets_full`` = index sheets with a file, ``sheets_missing`` = without
    one (HTTP 404), ``complete`` = no sheet without a file,
    ``uncovered_m2`` = the area in the frames of ``sheets_missing``,
    ``size_bytes`` = sum of ``Content-Length`` (``None``: a file without it).
    """

    country: str
    product: str
    source: str
    year: int | None
    acquisition_dates: tuple[str, str] | None
    published: tuple[str, str] | None
    campaigns: tuple[str, ...]
    horizontal: str
    resolution: str | None
    vertical_crs: str
    format: str
    densities: tuple[int, ...]
    complete: bool
    sheets_full: tuple[str, ...]
    sheets_partial: tuple[str, ...]
    sheets_missing: tuple[str, ...]
    uncovered: bool
    uncovered_m2: float
    size_bytes: int | None
    download_hint: tuple[str, ...]


@dataclass(frozen=True)
class AvailabilityReport:
    """Outcome of ``check_availability`` (schema ``kartograf-availability/1``).

    ``areas`` and ``combinations`` per country (``areas`` order); PL
    combinations newest year first, then sheet system, resolution, height
    system and format; CZ in registry order (model, then S-JTSK before
    ETRS89-TM33). ``ok`` is ``False`` only when a part of the request could
    not be checked (``country="auto"``: its ``CHECK_FAILED`` notice).
    """

    request: dict
    checked_at: str
    areas: tuple[AvailabilityArea, ...]
    combinations: tuple[AvailabilityCombination, ...]
    notices: tuple[Notice, ...]
    ok: bool
    schema: str = AVAILABILITY_SCHEMA

    def to_json(self) -> str:
        """The report as JSON (the CLI ``--json`` prints exactly this text)."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"


@dataclass(frozen=True)
class _Entry:
    """One feature of an index answer (cached as JSON).

    ``sheet`` is the canonical code (as published when ``issue`` is set),
    ``year`` the year of the feature type, ``footprint`` the (E, N) frame in
    EPSG:2180; ``issue`` (``_REASONS`` key) marks a record Kartograf does not
    download for a reason found while parsing.
    """

    layer: str
    year: int
    sheet: str
    system: str | None
    resolution_m: float | None
    format: str | None
    url: str
    full: bool | None
    date: str
    published: str | None
    campaign: str | None
    density: int | None
    footprint: tuple[tuple[float, float], ...] | None
    issue: str | None


@dataclass(frozen=True)
class _Service:
    """A WFS index service of the product and its height system."""

    vertical_crs: str
    ref: IndexRef


@dataclass(frozen=True)
class _Request:
    product: str
    country: str  # "pl" | "cz" | "auto"; with a sheet code: its country
    sheet: SheetParser | None  # PL sheet code
    cz_sheet: str | None  # CZ sheet code (SM5 sheet or TM33 tile)
    bbox: BBox | None
    geometry: Path | None
    layer: str | None
    min_year: int | None
    max_year: int | None
    years: tuple[str, ...]  # the year flags as given ("--year 2025"), PL only


@dataclass(frozen=True)
class _CzPart:
    """The CZ part of a request: the area as given (``bbox`` in its CRS: the
    request bbox or the geometry envelope; ``clip``: ``auto`` clips it to the
    CZ envelope) or a CZ sheet code (``bbox=None``)."""

    bbox: BBox | None
    sheet: str | None = None
    clip: bool = False


@dataclass(frozen=True)
class _Parts:
    """Countries of a request in report order and the area of each part:
    PL - convex (E, N) polygons in EPSG:2180, CZ - ``_CzPart``."""

    countries: tuple[str, ...]
    pl: list[Polygon] | None
    cz: _CzPart | None


@dataclass(frozen=True)
class _CzFile:
    """A file channel of a CZ variant in the native height system of its
    files; ``endpoint`` = openzu ``.../{sheet}.zip``."""

    variant: ProductVariant
    system: str  # "sm5" | "tm33"
    endpoint: str

    def url(self, sheet: str) -> str:
        return self.endpoint.format(sheet=sheet)


@dataclass(frozen=True)
class _CzSheet:
    """An index sheet of a CZ file channel (cached as JSON); ``frame`` in the
    CRS of its sheet system."""

    sheet: str
    frame: tuple[float, float, float, float]


@dataclass
class _Group:
    """Records of one combination."""

    year: int
    system: str
    vertical_crs: str
    variant: ProductVariant
    entries: list[_Entry] = field(default_factory=list)


def check_availability(
    *,
    product: str | None,
    country: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    cache: MetadataCache | bool = True,
    force: bool = False,
    on_notice: Callable[[Notice], None] | None = None,
) -> AvailabilityReport:
    """Report which data the sources have for an area - nothing is downloaded.

    Parameter names and values are the ``elevation availability`` flags in
    ``snake_case``: ``product`` (``nmt``, ``nmpt``, ``laz``), one area choice
    (``sheet`` - a PL or CZ sheet code, ``bbox`` in any supported CRS,
    ``geometry`` SHP/GPKG with ``layer``), ``country`` (``pl``, ``cz`` or
    ``auto``; required with ``bbox``/``geometry``, a sheet code names its
    country), year bounds as in ``download_data`` (``year`` = ``min_year =
    max_year``; the index layers outside them are not queried). ``cache``:
    ``True`` = default metadata cache in the current directory, a
    ``MetadataCache`` = that cache, ``False`` = none; ``force`` asks the
    services again (and overwrites the cache). ``on_notice`` receives each
    notice when it is emitted.

    ``country="auto"`` reports the PL and CZ parts of the area (rectangular
    country envelopes, ``split_bbox_by_country``; a geometry: PL its
    features, CZ the part of its envelope); a part that cannot be checked
    while the other one was is a ``CHECK_FAILED`` warning and ``ok=False``.
    Year bounds are PL-only (CUZK publishes no survey years): with ``cz`` or
    a CZ sheet code they are a ``ValidationError``; with ``auto`` they narrow
    the request to PL (``AUTO_NARROWED_TO_PL``) or, for an area only in CZ,
    are a ``ValidationError`` - as the PL-only choices of ``download_data``.

    Raises
    ------
    ValidationError
        Invalid or missing choice (before the network; texts name the CLI
        flags as in ``download_data``), year bounds without a layer in the
        index (after GetCapabilities), or an SM5 code missing in the index.
    ParseError
        Malformed sheet code.
    DownloadError
        An index, PRG or CUZK request failed (``auto``: of every country) -
        never an empty report. A CZ file answering 404 is a sheet without a
        file, any other failure is this error.
    """
    request = _validated(
        product, country, sheet, bbox, geometry, layer, year, min_year, max_year
    )
    require_bool(force, "--force")  # library calls only (STANDARDS 11.2)
    sink = NoticeSink(on_notice)
    layer_name = (
        resolve_geometry_layer(request.geometry, layer, sink)
        if request.geometry is not None
        else None
    )
    parts = _parts(request, layer_name, sink)
    sessions = SessionPerThread(None)
    areas: list[AvailabilityArea] = []
    combinations: list[AvailabilityCombination] = []
    failed: list[tuple[str, DownloadError]] = []
    with open_cache(cache, force=force, on_notice=sink.add) as metadata:
        for code in parts.countries:
            try:
                if code == "CZ":
                    assert parts.cz is not None
                    area, found = _check_cz(request, parts.cz, sessions, metadata, sink)
                else:
                    assert parts.pl is not None
                    area, found = _check_pl(request, parts.pl, sessions, metadata, sink)
            except DownloadError as error:
                if len(parts.countries) == 1:
                    raise
                failed.append((code, error))
                continue
            areas.append(area)
            combinations.extend(found)
    if failed and len(failed) == len(parts.countries):
        raise failed[0][1]
    for code, failure in failed:
        text = (
            f"--country auto: nie udalo sie sprawdzic czesci {code} ({failure}) - "
            f"raport obejmuje tylko {', '.join(a.country for a in areas)}"
        )
        sink.emit("warning", CHECK_FAILED, text.encode("ascii", "replace").decode())
    return AvailabilityReport(
        request=_request_payload(request, layer_name),
        checked_at=_clock.now().isoformat(timespec="seconds"),
        areas=tuple(areas),
        combinations=tuple(combinations),
        notices=sink.notices,
        ok=not failed,
    )


def _check_pl(
    request: _Request,
    areas: list[Polygon],
    sessions: SessionPerThread,
    metadata: MetadataCache | None,
    sink: NoticeSink,
) -> tuple[AvailabilityArea, list[AvailabilityCombination]]:
    """The PL part: GUGiK WFS indexes of the product and the PRG land mask."""
    envelope = area_envelope(areas)
    services = _services(request.product)
    typed = [
        (service, _feature_types(service, sessions, metadata)) for service in services
    ]
    selected = [
        (
            service,
            [
                name
                for name in types
                if in_year_range(type_year(name), request.min_year, request.max_year)
            ],
        )
        for service, types in typed
    ]
    if not any(chosen for _, chosen in selected):
        raise ValidationError(_no_layer_text(request, typed))
    answers = [
        (service, _index_entries(service, chosen, envelope, sessions, metadata))
        for service, chosen in selected
        if chosen
    ]
    mask = _land_mask(envelope, sessions, metadata)
    groups, unsupported = _group(request.product, answers, areas)
    area_px, land_px, measured = _measure(
        areas,
        envelope,
        mask,
        groups,
        sheet_frame=request.sheet is not None and request.product != "laz",
    )
    if unsupported:
        sink.emit("info", INDEX_UNSUPPORTED, _unsupported_text(unsupported))
    area = AvailabilityArea(
        country="PL",
        crs="EPSG:2180",
        bounds=(
            float(envelope.min_x),
            float(envelope.min_y),
            float(envelope.max_x),
            float(envelope.max_y),
        ),
        area_m2=float(area_px),
        land_m2=float(land_px),
    )
    # one grid selection per sheet system and scale for all the hints
    select = functools.cache(functools.partial(_selected_sheets, request))
    return area, [
        _combination(request, group, missing, uncovered, select)
        for group, (missing, uncovered) in zip(groups, measured, strict=True)
    ]


# =============================================================================
# Request
# =============================================================================


def _validated(
    product: str | None,
    country: str | None,
    sheet: str | None,
    bbox: BBox | None,
    geometry: str | Path | None,
    layer: str | None,
    year: int | None,
    min_year: int | None,
    max_year: int | None,
) -> _Request:
    """Checks before the network, with the texts of ``download_data``.

    Year bounds are PL-only: with ``cz`` (or a CZ sheet code) they are a
    ``ValidationError``; ``auto`` resolves them in ``_parts`` once the
    countries of the area are known.
    """
    from kartograf.core.parser_registry import detect_system

    validate_area_choice(sheet, bbox, geometry)
    choices = product_choices(AVAILABILITY_PRODUCTS)
    if product is None:
        raise ValidationError(f"--product wymagane: {choices}")
    if product not in AVAILABILITY_PRODUCTS:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: {choices}"
        )
    if sheet is None and country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    if country is not None and country not in AVAILABILITY_COUNTRIES:
        raise ValidationError(
            f"--country {country!r}: raport dostepnosci obejmuje: {COUNTRY_CHOICES}"
        )
    parsed = cz_sheet = None
    if sheet is not None:
        # the registry ends with the pl1992 fallback (always matches)
        system = detect_system(sheet)
        if country not in (None, "auto") and country != system.country.lower():
            raise ValidationError(
                f"Godlo '{sheet}' nalezy do systemu {system.id} (kraj "
                f"{system.country}), a podano --country {country}"
            )
        country = system.country.lower()
        if country == "pl":
            parsed = SheetParser(sheet)
        else:
            cz_sheet = sheet.strip()
            if cz_sheet_system(cz_sheet) == "tm33":
                ParserTM33(cz_sheet)  # ParseError: odd kilometres
    assert country is not None
    lo, hi = year_bounds(year, min_year, max_year)
    years = tuple(
        f"{flag} {value}"
        for flag, value in (
            ("--year", year),
            ("--min-year", min_year),
            ("--max-year", max_year),
        )
        if value is not None
    )
    if country == "cz" and years:
        raise ValidationError(_CZ_NO_YEARS)
    return _Request(
        product=product,
        country=country,
        sheet=parsed,
        cz_sheet=cz_sheet,
        bbox=bbox,
        geometry=Path(geometry) if geometry is not None else None,
        layer=layer,
        min_year=lo,
        max_year=hi,
        years=years,
    )


def _request_payload(request: _Request, layer_name: str | None) -> dict:
    """``AvailabilityReport.request``: product, country (a sheet code: its
    country), area (as the sidecar ``request``), year bounds."""
    payload: dict = {"product": request.product, "country": request.country}
    if request.sheet is not None:
        payload["sheet"] = request.sheet.sheet
    elif request.cz_sheet is not None:
        payload["sheet"] = request.cz_sheet
    elif request.bbox is not None:
        payload["bbox"] = bbox_coords(request.bbox)
        payload["bbox_crs"] = request.bbox.crs
    else:
        payload["geometry"] = str(request.geometry)
        payload["layer"] = layer_name
    payload["min_year"] = request.min_year
    payload["max_year"] = request.max_year
    return payload


def _parts(request: _Request, layer_name: str | None, sink: NoticeSink) -> _Parts:
    """Countries of the request and the area of each part (before the
    network; a ``TransformError`` fails the request).

    ``auto`` splits the bbox (a geometry: its envelope) by the rectangular
    country envelopes as ``download_data`` does (``split_bbox_by_country``);
    the PL part of a geometry stays its features, the CZ part is clipped per
    sheet system in ``_cz_area``. ``cz`` takes the bbox or the geometry
    envelope as given (the LAZ download of an area).
    Year bounds narrow an area reaching both countries to PL
    (``AUTO_NARROWED_TO_PL``, as the PL-only LAZ flags of ``download_data``).
    """
    if request.cz_sheet is not None:
        return _Parts(("CZ",), None, _CzPart(None, request.cz_sheet))
    if request.country == "pl":
        return _Parts(("PL",), _area_polygons(request, layer_name), None)
    if request.country == "cz":
        if request.bbox is not None:
            return _Parts(("CZ",), None, _CzPart(request.bbox))
        assert request.geometry is not None
        envelope = geometry_envelope(request.geometry, layer_name)
        return _Parts(("CZ",), None, _CzPart(envelope))
    if request.geometry is not None:
        area = geometry_envelope(request.geometry, layer_name)
    else:
        assert request.bbox is not None
        area = request.bbox
    split = split_bbox_by_country(area, cz_crs=_CZ_CRS)
    countries = tuple(code for code in ("PL", "CZ") if code in split)
    if not countries:
        raise ValidationError(
            "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)"
        )
    if request.years and "CZ" in countries:
        if "PL" not in countries:
            raise ValidationError(_CZ_NO_YEARS)
        sink.emit(
            "info",
            AUTO_NARROWED_TO_PL,
            f"--country auto -> pl ({', '.join(request.years)} dotyczy tylko PL)",
        )
        countries = ("PL",)
    pl = None
    if "PL" in countries:
        part = None if request.geometry is not None else split["PL"].bbox
        pl = _area_polygons(request, layer_name, part)
    cz = _CzPart(area, clip=True) if "CZ" in countries else None
    return _Parts(countries, pl, cz)


def _area_polygons(
    request: _Request, layer_name: str | None, bbox: BBox | None = None
) -> list[Polygon]:
    """The PL area as convex (E, N) polygons in EPSG:2180 - the area a
    download of the same choice covers: NMT/NMPT the sheet frame, the bbox
    envelope (``bbox``: the PL part of ``auto``), the feature envelopes of the
    geometry file (sheets per feature); LAZ the envelope of the sheet frame or
    of the whole geometry (tiles of one bbox).
    """
    from kartograf.core.geometry import get_overall_bbox, read_feature_bboxes

    laz = request.product == "laz"
    if request.sheet is not None:
        if laz:
            b = request.sheet.get_bbox(crs="EPSG:2180")
            return [rectangle(b.min_x, b.min_y, b.max_x, b.max_y)]
        return [sheet_frame_2180(request.sheet.sheet)]
    area = bbox if bbox is not None else request.bbox
    if area is not None:
        b = bbox_to_2180(area)
        return [rectangle(b.min_x, b.min_y, b.max_x, b.max_y)]
    assert request.geometry is not None
    boxes = read_feature_bboxes(request.geometry, layer_name, "EPSG:2180")
    if not boxes:
        raise ValidationError(f"{request.geometry.name}: warstwa bez obiektow")
    if laz:
        b = get_overall_bbox(request.geometry, layer=layer_name, target_crs="EPSG:2180")
        return [rectangle(b.min_x, b.min_y, b.max_x, b.max_y)]
    return [rectangle(b.min_x, b.min_y, b.max_x, b.max_y) for b in boxes]


# =============================================================================
# Index and land mask (network or cache)
# =============================================================================


def _services(product: str) -> list[_Service]:
    """WFS index services of the product (registry order, one per endpoint)."""
    found: dict[str, _Service] = {}
    for variant in variants(product=product, country="PL"):
        if variant.index_ref is not None:
            found.setdefault(
                variant.index_ref.endpoint,
                _Service(variant.vertical_crs, variant.index_ref),
            )
    return list(found.values())


def _index(service: _Service, sessions: SessionPerThread) -> WfsIndex:
    return WfsIndex(
        sessions.get,
        service.ref.endpoint,
        service.ref.layer_prefix,
        timeout=_TIMEOUT,
        retries=MAX_RETRIES,
    )


def _feature_types(
    service: _Service, sessions: SessionPerThread, cache: MetadataCache | None
) -> list[str]:
    """Yearly feature types of the service (GetCapabilities or the cache)."""
    key = f"wfs-types|{service.ref.endpoint}"
    if cache is not None:
        cached = cache.get_index_area(key)
        if (
            isinstance(cached, list)
            and cached
            and all(isinstance(name, str) for name in cached)
        ):
            return cached
    types = _index(service, sessions).feature_types()
    if cache is not None:
        cache.set_index_area(key, types)
    return types


def _no_layer_text(request: _Request, typed: list[tuple[_Service, list[str]]]) -> str:
    """Year bounds outside every layer of the product's services."""
    name = request.product.upper()
    available = "; ".join(
        f"{service.vertical_crs}: "
        + ", ".join(str(y) for y in sorted({type_year(t) for t in types}, reverse=True))
        for service, types in typed
    )
    flags = (
        f"--year {request.min_year}"
        if request.min_year is not None and request.min_year == request.max_year
        else "--min-year/--max-year"
    )
    return (
        f"{flags}: skorowidz GUGiK {name} nie ma rocznika "
        f"{year_range_label(request.min_year, request.max_year)} - dostepne "
        f"roczniki: {available}"
    )


def _mm(bbox: BBox) -> str:
    """Cache key part: the envelope in whole millimetres."""
    return ",".join(
        str(round(value * 1000))
        for value in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    )


def _index_entries(
    service: _Service,
    types: list[str],
    envelope: BBox,
    sessions: SessionPerThread,
    cache: MetadataCache | None,
) -> list[_Entry]:
    """Every record of ``types`` in the envelope (one GetFeature, all pages)."""
    key = f"wfs|{service.ref.endpoint}|{','.join(types)}|{_mm(envelope)}"
    if cache is not None:
        restored = _restore_entries(cache.get_index_area(key))
        if restored is not None:
            return restored
    parse = _laz_entry if service.ref.layer_prefix.endswith("LIDAR") else _sheet_entry
    entries = [
        parse(feature)
        for feature in _index(service, sessions).features(envelope, types)
    ]
    if cache is not None:
        cache.set_index_area(key, [asdict(entry) for entry in entries])
    return entries


def _restore_entries(payload: object) -> list[_Entry] | None:
    """Entries of a cache payload; ``None`` (a miss) for an unreadable one."""
    if not isinstance(payload, list):
        return None
    entries = []
    try:
        for item in payload:
            footprint = item.pop("footprint")
            entries.append(
                _Entry(
                    **item,
                    footprint=(
                        None
                        if footprint is None
                        else tuple((float(x), float(y)) for x, y in footprint)
                    ),
                )
            )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return entries


def _sheet_entry(feature) -> _Entry:
    """Entry of an NMT/NMPT feature (the record parser of the sheet download)."""
    layer = localname(feature.tag)
    footprint = feature_footprint(feature)
    record = parse_index_feature(feature)
    if record is None:
        issue = index_feature_issue(feature) or "url"
        crs = parse_pl_system(feature_text(feature, "uklad_xy"))
        return _Entry(
            layer=layer,
            year=type_year(layer),
            sheet=feature_text(feature, "godlo") or "-",
            system=crs[0] if crs else None,
            resolution_m=metres(feature_text(feature, "char_przestrz")),
            format=feature_text(feature, "format"),
            url=feature_text(feature, "url_do_pobrania") or "",
            full=None,
            date=time_position(feature, "akt_data") or "",
            published=time_position(feature, "dt_pzgik"),
            campaign=feature_text(feature, "nr_zglosz"),
            density=None,
            footprint=footprint,
            issue=issue,
        )
    return _Entry(
        layer=layer,
        year=type_year(layer),
        sheet=record.sheet,
        system=record.system,
        resolution_m=record.resolution_m,
        format=record.file_format,
        url=record.url,
        full=record.full_sheet,
        date=record.aktualnosc,
        published=record.dt_pzgik,
        campaign=record.raw.get("numerZgloszeniaPracy"),
        density=None,
        footprint=footprint or sheet_frame_2180(record.sheet),
        issue=None if record.system is not None else "crs",
    )


def _laz_entry(feature) -> _Entry:
    """Entry of a LAZ feature (the tile parser of the LAZ download)."""
    layer = localname(feature.tag)
    tile = laz_tile(feature)
    url = tile.url if tile is not None else feature_text(feature, "url_do_pobrania")
    footprint = feature_footprint(feature)
    if (
        tile is not None
        and footprint is None
        and not any(
            math.isnan(v) for v in (tile.min_x, tile.min_y, tile.max_x, tile.max_y)
        )
    ):
        footprint = rectangle(tile.min_x, tile.min_y, tile.max_x, tile.max_y)
    if tile is None:
        issue: str | None = "url" if not (url or "").startswith("https://") else "crs"
    else:
        issue = None if tile.url.startswith("https://") else "url"
    return _Entry(
        layer=layer,
        year=type_year(layer),
        sheet=tile.sheet if tile is not None else feature_text(feature, "godlo") or "-",
        system=tile.system if tile is not None else None,
        resolution_m=None,
        format=feature_text(feature, "format") or "LAZ",
        url=url or "",
        full=tile.full_sheet if tile is not None else None,
        date=time_position(feature, "akt_data") or "",
        published=time_position(feature, "dt_pzgik"),
        campaign=feature_text(feature, "nr_zglosz"),
        density=tile.density if tile is not None else None,
        footprint=footprint,
        issue=issue,
    )


def _land_mask(
    envelope: BBox, sessions: SessionPerThread, cache: MetadataCache | None
) -> LandMask:
    """PRG land mask of the envelope (PRG WFS or the cache)."""
    key = f"prg|{_mm(envelope)}"
    if cache is not None:
        restored = LandMask.from_payload(cache.get_index_area(key))
        if restored is not None:
            return restored
    mask = fetch_land_mask(envelope, session=sessions.get(), timeout=_TIMEOUT)
    if cache is not None:
        cache.set_index_area(key, mask.to_payload())
    return mask


# =============================================================================
# Combinations
# =============================================================================


def _member(entry: _Entry, areas: Sequence[Polygon]) -> bool:
    """The record's frame overlaps the area by more than an edge sliver (a
    record without a frame counts: the server matched it to the envelope)."""
    if entry.footprint is None:
        return entry.issue is not None
    return any(overlaps_area(entry.footprint, area) for area in areas)


def _label(resolution_m: float | None) -> str | None:
    return (
        None if resolution_m is None else resolution_label(Decimal(repr(resolution_m)))
    )


def _group(
    product: str,
    answers: list[tuple[_Service, list[_Entry]]],
    areas: Sequence[Polygon],
) -> tuple[list[_Group], dict[tuple, dict]]:
    """Records of the area grouped into combinations; the rest by reason."""
    groups: dict[tuple, _Group] = {}
    unsupported: dict[tuple, dict] = {}
    found: dict[tuple, ProductVariant | None] = {}
    for service, entries in answers:
        for entry in entries:
            if not _member(entry, areas):
                continue
            reason, variant = _variant(product, service.vertical_crs, entry, found)
            if variant is None or entry.system is None:
                label = _label(entry.resolution_m)
                name = (entry.format or "bez formatu").strip()
                if reason == "file":
                    suffix = entry.url.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
                    name = f"{name}, plik .{suffix}"
                slot = unsupported.setdefault(
                    (service.vertical_crs, name, label or "", reason or "crs"),
                    {"years": set(), "sheets": set()},
                )
                slot["years"].add(entry.year)
                slot["sheets"].add(entry.sheet)
                continue
            key = (entry.year, entry.system, variant.source, service.vertical_crs)
            group = groups.get(key)
            if group is None:
                group = groups[key] = _Group(
                    entry.year, entry.system, service.vertical_crs, variant
                )
            group.entries.append(entry)
    ordered = sorted(groups.values(), key=_group_order)
    return ordered, unsupported


def _variant(
    product: str,
    vertical_crs: str,
    entry: _Entry,
    found: dict[tuple, ProductVariant | None],
) -> tuple[str | None, ProductVariant | None]:
    """``(reason, variant)``: the registered variant of a record, else why not."""
    if entry.issue is not None:
        return entry.issue, None
    if product == "laz":
        laz = variants(product="laz", country="PL", vertical_crs=vertical_crs)
        return (None, laz[0]) if laz else ("registry", None)
    token = source_format(entry.format, entry.url)
    if token is None:
        known = {f.index_name for f in FORMATS}
        return ("file" if (entry.format or "").strip() in known else "format"), None
    label = _label(entry.resolution_m)
    key = (product, vertical_crs, token, label)
    if key not in found:
        found[key] = next(
            (
                v
                for v in variants(
                    product=product,
                    country="PL",
                    vertical_crs=vertical_crs,
                    format=token,
                )
                if v.label == label
            ),
            None,
        )
    variant = found[key]
    return (None, variant) if variant is not None else ("registry", None)


def _group_order(group: _Group) -> tuple:
    """Year descending, then sheet system, resolution, height system, format."""
    value = group.variant.resolution_m
    return (
        -group.year,
        group.system,
        value is None,
        value if value is not None else Decimal(0),
        group.vertical_crs,
        _FORMAT_ORDER.get(group.variant.format, len(_FORMAT_ORDER)),
    )


def _geojson(polygon: Sequence[tuple[float, float]]) -> dict:
    ring = [[x, y] for x, y in polygon]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


def _burn(shapes: list[dict], transform, shape: tuple[int, int]) -> np.ndarray:
    """Pixels whose centre lies in any of ``shapes`` (bool)."""
    if not shapes:
        return np.zeros(shape, dtype=bool)
    return rasterize(
        [(geometry, 1) for geometry in shapes],
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=False,
        dtype=np.uint8,
    ).astype(bool)


def _inner(area: Polygon) -> Polygon | None:
    """The area without its ``EDGE_TOLERANCE_M`` rim (``None``: narrower).

    Used for a sheet request: its area is the sheet frame computed here,
    while the index records carry the GUGiK frame of the same sheet - the
    two differ by centimetres (sampled curved edges), which must not turn
    into uncovered pixels along the frame. Frames are compared up to the
    tolerance of the record membership.
    """
    ox, oy = area[0]
    local = normalize_convex((x - ox, y - oy) for x, y in area)
    if local is None or polygon_area(local) <= AREA_EPS:
        return None
    inner = expand_convex(local, -EDGE_TOLERANCE_M)
    if polygon_area(inner) <= AREA_EPS:
        return None
    return tuple((x + ox, y + oy) for x, y in inner)


def _measure(
    areas: Sequence[Polygon],
    envelope: BBox,
    mask: LandMask,
    groups: list[_Group],
    *,
    sheet_frame: bool,
) -> tuple[int, int, list[tuple[int, int]]]:
    """``(area_px, land_px, [(missing_full_px, uncovered_px) per group])`` on
    the 1 m grid of the envelope (pixel = 1 m2), in row strips.

    ``area_px``/``land_px`` measure the whole area; the coverage of the
    combinations is measured on its land - for a sheet request
    (``sheet_frame``) without the rim of the frame (``_inner``).
    """
    x0, x1 = math.floor(envelope.min_x), math.ceil(envelope.max_x)
    y0, y1 = math.floor(envelope.min_y), math.ceil(envelope.max_y)
    width, height = max(1, x1 - x0), max(1, y1 - y0)
    area_shapes = [_geojson(area) for area in areas]
    measured = (
        [inner for area in areas if (inner := _inner(area)) is not None]
        if sheet_frame
        else list(areas)
    )
    inner_shapes = [_geojson(area) for area in measured]
    every = [
        [_geojson(e.footprint) for e in group.entries if e.footprint is not None]
        for group in groups
    ]
    full = [
        [
            _geojson(e.footprint)
            for e in group.entries
            if e.full is True and e.footprint is not None
        ]
        for group in groups
    ]
    missing = [0] * len(groups)
    uncovered = [0] * len(groups)
    area_px = land_px = 0
    rows = max(1, _STRIP_PX // width)
    for top in range(0, height, rows):
        shape = (min(rows, height - top), width)
        transform = from_origin(x0, y1 - top, 1.0, 1.0)
        inside = _burn(area_shapes, transform, shape)
        if not inside.any():
            continue
        classes = mask.burn(transform, shape)
        area_px += int(np.count_nonzero(inside & (classes != ABROAD)))
        land_px += int(np.count_nonzero(inside & (classes == LAND)))
        target = _burn(inner_shapes, transform, shape) & (classes == LAND)
        if not target.any():
            continue
        for i in range(len(groups)):
            covered = _burn(every[i], transform, shape)
            uncovered[i] += int(np.count_nonzero(target & ~covered))
            complete = _burn(full[i], transform, shape)
            missing[i] += int(np.count_nonzero(target & ~complete))
    return area_px, land_px, list(zip(missing, uncovered, strict=True))


def _span(values: list[str]) -> tuple[str, str] | None:
    present = sorted(v for v in values if v)
    return (present[0], present[-1]) if present else None


def _combination(
    request: _Request,
    group: _Group,
    missing: int,
    uncovered: int,
    select: Callable[[str, str], frozenset[str]],
) -> AvailabilityCombination:
    """The combination of a group of records, its sheets and download hint."""
    by_sheet: dict[str, list[_Entry]] = {}
    for entry in group.entries:
        by_sheet.setdefault(entry.sheet, []).append(entry)
    full = sorted(
        s for s, rows in by_sheet.items() if any(r.full is True for r in rows)
    )
    partial = sorted(s for s in by_sheet if s not in full)
    variant = group.variant
    return AvailabilityCombination(
        country="PL",
        product=request.product,
        source=variant.source,
        year=group.year,
        acquisition_dates=_span([e.date for e in group.entries]),
        published=_span([e.published or "" for e in group.entries]),
        campaigns=tuple(sorted({e.campaign for e in group.entries if e.campaign})),
        horizontal=_HORIZONTAL[group.system],
        resolution=variant.label,
        vertical_crs=group.vertical_crs,
        format=variant.format,
        densities=tuple(
            sorted({e.density for e in group.entries if e.density is not None})
        ),
        complete=missing == 0,
        sheets_full=tuple(full),
        sheets_partial=tuple(partial),
        sheets_missing=(),
        uncovered=uncovered > 0,
        uncovered_m2=float(uncovered),
        size_bytes=None,
        download_hint=_download_hint(request, group, by_sheet, select),
    )


def _unsupported_text(unsupported: dict[tuple, dict]) -> str:
    """``INDEX_UNSUPPORTED``: the records of the area Kartograf does not download."""
    parts = []
    for vertical_crs, name, label, reason in sorted(unsupported):
        slot = unsupported[(vertical_crs, name, label, reason)]
        years = ", ".join(str(y) for y in sorted(slot["years"], reverse=True))
        shown = f"{name} {label}" if label else name
        parts.append(
            f"{shown} {vertical_crs} ({years}; arkusze: {len(slot['sheets'])}) - "
            f"{_REASONS[reason]}"
        )
    text = (
        "Skorowidz GUGiK ma dla obszaru tez rekordy, ktorych Kartograf nie "
        "pobiera: " + "; ".join(parts)
    )
    return text.encode("ascii", "replace").decode("ascii")


# =============================================================================
# CZ: CUZK index sheets and files (plan B, decision 9)
# =============================================================================


@dataclass(frozen=True)
class _Head:
    """``HEAD`` of a CZ file (cached as JSON): ``found`` = HTTP 200 (``False``:
    404 - the index sheet has no file), ``Last-Modified``, ``Content-Length``."""

    found: bool
    last_modified: str | None
    content_length: int | None


def _check_cz(
    request: _Request,
    part: _CzPart,
    sessions: SessionPerThread,
    metadata: MetadataCache | None,
    sink: NoticeSink,
) -> tuple[AvailabilityArea, list[AvailabilityCombination]]:
    """The CZ part: index sheets of every file channel of the product and one
    ``HEAD`` per file (in parallel) - nothing is downloaded.

    The sheets of a sheet system are those of the area in the CRS of the
    system (``_cz_area``; ``SheetIndex.file_sheets``, the rule of the LAZ
    download of an area); a sheet code is its own only sheet in its system.
    """
    files = _cz_files(request.product)
    index = SheetIndex(session=sessions.get(), cache=metadata)
    own: str | None = None
    own_sheets: tuple[_CzSheet, ...] = ()
    if part.sheet is not None:
        own = cz_sheet_system(part.sheet)
        area, own_sheets = _cz_code_sheets(index, part.sheet, own)
    else:
        assert part.bbox is not None
        area = part.bbox
    bounds = _cz_area(part, area, _CZ_CRS)
    # a sheet code: its frame; an area: the rectangle of the CZ part
    reported = area if part.sheet is not None else bounds
    sheets: dict[str, tuple[_CzSheet, ...]] = {}
    for system in dict.fromkeys(file.system for file in files):
        sheets[system] = (
            own_sheets
            if system == own
            else _cz_index_sheets(
                index, system, _cz_area(part, area, CZ_SYSTEM_CRS[system]), metadata
            )
        )
    heads = _heads(
        [file.url(s.sheet) for file in files for s in sheets[file.system]],
        sessions,
        metadata,
    )
    combinations = [
        _cz_combination(request, file, sheets[file.system], heads, reported)
        for file in files
        if sheets[file.system]
    ]
    service_only = _cz_service_only(request.product)
    # an ``auto`` part without any CUZK sheet (an area in PL inside the CZ
    # envelope) has no CZ data at all: nothing to say about the models
    if service_only is not None and any(sheets.values()):
        sink.emit("info", CZ_SERVICE_ONLY, service_only)
    area_cz = AvailabilityArea(
        country="CZ",
        crs=_CZ_CRS,
        bounds=(
            float(bounds.min_x),
            float(bounds.min_y),
            float(bounds.max_x),
            float(bounds.max_y),
        ),
        area_m2=_rect_area(reported),
        land_m2=_rect_area(reported),
    )
    return area_cz, combinations


def _cz_files(product: str) -> list[_CzFile]:
    """File channels of the CZ variants of ``product`` in the native height
    system of their files (registry order) - the combinations of the report:
    NMT DMR 4G, NMPT DMP OK (S-JTSK/Bpv and ETRS89-TM33/EVRF2007), LAZ every
    model in both pairs."""
    found = []
    for variant in variants(product=product, country="CZ"):
        if variant.channel != TransportKind.DIRECT_FILES:
            continue
        (system,) = variant.systems
        channel = channel_for(
            variant.source, TransportKind.DIRECT_FILES, CZ_SYSTEM_CRS[system]
        )
        native = vertical_crs_code(variant.vertical_crs) in channel.vertical_crs_options
        if native and channel.endpoint is not None:
            found.append(_CzFile(variant, system, channel.endpoint))
    return found


def _cz_service_only(product: str) -> str | None:
    """``CZ_SERVICE_ONLY``: the CZ models of ``product`` without sheet files
    (DMR 5G, DMP 1G) - outside the report, still downloadable; ``None`` when
    every model has files (LAZ)."""
    rows: dict[str, list[ProductVariant]] = {}
    for variant in variants(product=product, country="CZ"):
        if variant.model is not None:
            rows.setdefault(variant.model, []).append(variant)
    service = [
        (model, found)
        for model, found in rows.items()
        if all(v.channel != TransportKind.DIRECT_FILES for v in found)
    ]
    if not service:
        return None
    names = " i ".join(
        f"{CZ_MODELS[model][0]} ({found[0].label})" for model, found in service
    )
    have, are = ("nie ma", "jest") if len(service) == 1 else ("nie maja", "sa")
    models = ", ".join(model for model, _ in service)
    return (
        f"{names} {have} plikow arkuszy CUZK (raport ich nie obejmuje) - {are} "
        "dla calego CZ jako wycinek (--cutout), kafel TM33 z uslugi ImageServer "
        f"(--sheet, np. 302_5550) i LAZ (--product laz --model {models})"
    )


def _cz_area(part: _CzPart, area: BBox, crs: str) -> BBox:
    """The CZ part in ``crs`` as the LAZ download selects sheets: an ``auto``
    area clipped to the CZ envelope straight into ``crs`` (``country_bbox``),
    else the area (a sheet code: its frame) moved by ``_in_crs``."""
    if part.clip:
        return country_bbox(area, "CZ", auto=True, cz_crs=crs).bbox
    return _in_crs(area, crs)


def _in_crs(bbox: BBox, crs: str) -> BBox:
    """``bbox`` in ``crs``: the same rectangle, or its envelope through the
    pinned operation (``bbox_to_crs``, as the LAZ download of an area)."""
    if wkid(bbox.crs) == wkid(crs):
        return BBox(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, crs)
    return bbox_to_crs(bbox, crs)


def _rect_area(bbox: BBox) -> float:
    """Area of a rectangle in whole square metres."""
    return float(round((bbox.max_x - bbox.min_x) * (bbox.max_y - bbox.min_y)))


def _cz_sheet(sheet: str, frame: BBox) -> _CzSheet:
    return _CzSheet(sheet, (frame.min_x, frame.min_y, frame.max_x, frame.max_y))


def _cz_code_sheets(
    index: SheetIndex, code: str, system: str
) -> tuple[BBox, tuple[_CzSheet, ...]]:
    """Frame of a CZ sheet code and its file sheet: an SM5 sheet from the
    index (``ValidationError``: a code missing in it; no file sheet with
    ``PODIL`` 0), a TM33 tile computed from the code."""
    if system == "sm5":
        info = index.sm5_sheet(code)
        files = info.podil is None or info.podil > 0
        return info.bbox, ((_cz_sheet(info.sheet, info.bbox),) if files else ())
    frame = ParserTM33(code).get_bbox()
    return frame, (_cz_sheet(code, frame),)


def _cz_index_sheets(
    index: SheetIndex, system: str, area: BBox, cache: MetadataCache | None
) -> tuple[_CzSheet, ...]:
    """File sheets of a sheet system in ``area`` (its CRS): the index or the
    cache (``cz-sheets|<system>|<area in mm>``)."""
    key = f"cz-sheets|{system}|{_mm(area)}"
    if cache is not None:
        restored = _restore_cz_sheets(cache.get_index_area(key))
        if restored is not None:
            return restored
    found = tuple(
        _cz_sheet(info.sheet, info.bbox) for info in index.file_sheets(system, area)
    )
    if cache is not None:
        cache.set_index_area(key, [asdict(sheet) for sheet in found])
    return found


def _restore_cz_sheets(payload: object) -> tuple[_CzSheet, ...] | None:
    """Sheets of a cache payload; ``None`` (a miss) for an unreadable one."""
    if not isinstance(payload, list):
        return None
    found = []
    try:
        for item in payload:
            x0, y0, x1, y1 = (float(v) for v in item["frame"])
            found.append(_CzSheet(str(item["sheet"]), (x0, y0, x1, y1)))
    except (KeyError, TypeError, ValueError):
        return None
    return tuple(found)


def _heads(
    urls: list[str], sessions: SessionPerThread, cache: MetadataCache | None
) -> dict[str, _Head]:
    """``HEAD`` of every file, in parallel (``_HEAD_WORKERS``); the first
    failure is raised after the running requests end (queued ones are
    cancelled)."""

    def one(url: str) -> _Head:
        return _head(url, sessions, cache)

    if len(urls) <= 1:
        return {url: one(url) for url in urls}
    pool = ThreadPoolExecutor(max_workers=_HEAD_WORKERS)
    try:
        found = list(pool.map(one, urls))
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return dict(zip(urls, found, strict=True))


def _head(url: str, sessions: SessionPerThread, cache: MetadataCache | None) -> _Head:
    """One file: the cache (``head|<url>``) or one ``HEAD`` (retry policy of
    ``head_signal``). 404 = no file; any other failure (5xx, timeout, other
    4xx) = ``DownloadError`` - never "no file"."""
    key = f"head|{url}"
    if cache is not None:
        restored = _restore_head(cache.get_index_area(key))
        if restored is not None:
            return restored
    try:
        signal = head_signal(sessions.get(), url, timeout=_CZ_TIMEOUT)
    except DownloadError as error:
        if error.status_code != 404:
            raise
        found = _Head(False, None, None)
    else:
        found = _Head(True, signal["last_modified"], signal["content_length"])
    if cache is not None:
        cache.set_index_area(key, asdict(found))
    return found


def _restore_head(payload: object) -> _Head | None:
    """``_Head`` of a cache payload; ``None`` (a miss) for an unreadable one."""
    if not isinstance(payload, dict):
        return None
    found = payload.get("found")
    modified = payload.get("last_modified")
    length = payload.get("content_length")
    if (
        not isinstance(found, bool)
        or not (modified is None or isinstance(modified, str))
        or not (length is None or (isinstance(length, int) and length >= 0))
    ):
        return None
    return _Head(found, modified, length)


def _http_date(value: str | None) -> str | None:
    """``YYYY-MM-DD`` of an HTTP date (``Last-Modified``, GMT); ``None`` when
    absent or unreadable."""
    if value is None:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def _uncovered_m2(missing: list[_CzSheet], system_crs: str, area: BBox) -> float:
    """Area of ``area`` (the reported rectangle) in the frames of the sheets
    without a file, measured in the CRS of ``area``: a frame of another CRS
    (a TM33 tile against the S-JTSK rectangle of an area) is moved there corner
    by corner through the pinned operation - its envelope would be larger than
    the frame, and the uncovered area larger than the area itself."""
    if not missing:
        return 0.0
    move = None
    if wkid(system_crs) != wkid(area.crs):
        x0, y0, x1, y1 = missing[0].frame
        probe = replace(CONTENT_POLICY, probe_point=((x0 + x1) / 2, (y0 + y1) / 2))
        move = build_pinned_transform(system_crs, area.crs, probe)
    # local coordinates: 10^5-10^6 m would eat the precision of the area
    ox, oy = area.min_x, area.min_y
    clip = rectangle(0.0, 0.0, area.max_x - ox, area.max_y - oy)
    total = 0.0
    for sheet in missing:
        x0, y0, x1, y1 = sheet.frame
        xs, ys = np.array([x0, x1, x1, x0]), np.array([y0, y0, y1, y1])
        if move is not None:
            xs, ys = move.transform(xs, ys)
        frame: Polygon = tuple(
            (float(x) - ox, float(y) - oy) for x, y in zip(xs, ys, strict=True)
        )
        if polygon_area(frame) < 0:
            frame = frame[::-1]
        total += polygon_area(clip_convex(frame, clip))
    return float(round(total))


def _cz_combination(
    request: _Request,
    file: _CzFile,
    sheets: tuple[_CzSheet, ...],
    heads: dict[str, _Head],
    area: BBox,
) -> AvailabilityCombination:
    """A CZ combination: index sheets with (``sheets_full``) and without
    (``sheets_missing``) a file, publication dates and size of the files,
    ``uncovered_m2`` = the part of ``area`` (the reported rectangle) in the
    frames of the sheets without a file."""
    found = [(sheet, heads[file.url(sheet.sheet)]) for sheet in sheets]
    full = [sheet.sheet for sheet, head in found if head.found]
    missing = [sheet for sheet, head in found if not head.found]
    present = [head for _, head in found if head.found]
    sizes = [head.content_length for head in present]
    known = [size for size in sizes if size is not None]
    variant = file.variant
    return AvailabilityCombination(
        country="CZ",
        product=request.product,
        source=variant.source,
        year=None,
        acquisition_dates=None,
        published=_span([_http_date(head.last_modified) or "" for head in present]),
        campaigns=(),
        horizontal=_CZ_HORIZONTAL[file.system],
        resolution=variant.label,
        vertical_crs=variant.vertical_crs,
        format=variant.format,
        densities=(),
        complete=not missing,
        sheets_full=tuple(full),
        sheets_partial=(),
        sheets_missing=tuple(sheet.sheet for sheet in missing),
        uncovered=bool(missing),
        uncovered_m2=_uncovered_m2(missing, CZ_SYSTEM_CRS[file.system], area),
        size_bytes=sum(known) if present and len(known) == len(sizes) else None,
        download_hint=_cz_hint(request, file, full),
    )


# =============================================================================
# Download hint (decision 8 of plan A; CZ: decision 10 of plan B)
# =============================================================================


def _scale_order(scale: str) -> int:
    """``1:5000`` before ``1:2000`` (coarser first)."""
    return -int(scale.split(":")[1])


def _number(value: float) -> str:
    return format(float(value), ".15g")


def _area_flags(request: _Request, country: str) -> list[str]:
    """``--country`` of the combination (``pl``/``cz``: an ``auto`` request
    gives commands per country) and the bbox/geometry of the request."""
    if request.bbox is not None:
        b = request.bbox
        coords = ",".join(_number(v) for v in (b.min_x, b.min_y, b.max_x, b.max_y))
        bbox = [f"--bbox={coords}"] if coords.startswith("-") else ["--bbox", coords]
        crs = ["--bbox-crs", b.crs] if b.crs != "EPSG:2180" else []
        return ["--country", country, *bbox, *crs]
    assert request.geometry is not None
    layer = ["--layer", request.layer] if request.layer is not None else []
    return ["--country", country, "--geometry", str(request.geometry), *layer]


def _selected_sheets(request: _Request, system: str, scale: str) -> frozenset[str]:
    """Sheets that a PL download of the request's own selection plans at
    ``scale`` (``download/data.py``): the grid of the area (``--country pl``:
    the whole bbox, unclipped) or the descendants of the sheet code - with
    the grid sheets that have no GUGiK record, e.g. abroad at the border."""
    if request.sheet is not None:
        code = request.sheet
        if code.scale == scale:
            return frozenset((code.sheet,))
        return frozenset(d.sheet for d in code.get_all_descendants(scale))
    if request.bbox is not None:
        area = country_bbox(request.bbox, "PL", auto=False).bbox
        return frozenset(find_sheets_for_bbox(area, scale, sheet_system=system))
    from kartograf.core.geometry import find_sheets_for_geometry

    assert request.geometry is not None
    return frozenset(
        find_sheets_for_geometry(
            request.geometry, scale, request.layer, sheet_system=system
        )
    )


def _grid_areas(
    system: str,
    sheets: list[str],
    select: Callable[[str, str], frozenset[str]],
    command: Callable[[str], list[str]],
) -> list[list[str]]:
    """Selection flags of a grid combination: per scale (PL-1992: 1:10000)
    ``command(scale)`` when its download plans only sheets with a record of
    the combination, else one ``--sheet`` per sheet - a hint never plans a
    sheet without a GUGiK record (it would end with "Brak danych", exit 1)."""
    if system == "2000":
        scales = sorted({SheetParser(s).scale for s in sheets}, key=_scale_order)
        parts = [(s, [x for x in sheets if SheetParser(x).scale == s]) for s in scales]
    else:
        parts = [("1:10000", sheets)]
    areas: list[list[str]] = []
    for scale, own in parts:
        if select(system, scale) <= set(own):
            areas.append(command(scale))
        else:
            areas.extend(["--sheet", sheet] for sheet in own)
    return areas


def _sheet_area(
    request: _Request,
    group: _Group,
    sheets: list[str],
    select: Callable[[str, str], frozenset[str]],
) -> list[list[str]]:
    """Area flags of a sheet request: the code itself when a download of it
    plans exactly sheets of the combination, else one command per sheet."""
    code = request.sheet
    assert code is not None
    if request.product == "laz":
        return [["--sheet", code.sheet]]
    if group.system == code.sheet_system:
        if group.variant.source_file:
            return [["--sheet", code.sheet]]
        if group.system == "1992":
            return _grid_areas(
                "1992", sheets, select, lambda _: ["--sheet", code.sheet]
            )
        if all(s == code.sheet or s.startswith(code.sheet + ".") for s in sheets):
            return _grid_areas(
                "2000",
                sheets,
                select,
                lambda scale: (
                    ["--sheet", code.sheet]
                    + ([] if scale == code.scale else ["--scale", scale])
                ),
            )
    return [["--sheet", sheet] for sheet in sheets]


def _download_hint(
    request: _Request,
    group: _Group,
    by_sheet: dict[str, list[_Entry]],
    select: Callable[[str, str], frozenset[str]],
) -> tuple[str, ...]:
    """Commands downloading the combination (after ``kartograf ``, without
    ``--output``): the area of the request, the sheet system and scale
    (PL-2000 grids: one command per scale), the variant, ``--year`` and
    ``--full-sheet`` when a sheet's newest record of the year is partial while
    a full one exists. A grid area or sheet code whose download would plan a
    sheet without a record of the combination (coordinator decision
    2026-10-16) gives one ``--sheet`` command per sheet instead."""
    sheets = sorted(by_sheet)
    if request.sheet is not None:
        areas = _sheet_area(request, group, sheets, select)
    elif request.product == "laz":
        areas = [_area_flags(request, "pl")]
    else:
        base = [*_area_flags(request, "pl"), "--sheet-system", group.system]
        if group.variant.source_file:
            areas = [base]
        else:
            areas = _grid_areas(
                group.system,
                sheets,
                select,
                lambda scale: (
                    [*base, "--scale", scale] if group.system == "2000" else base
                ),
            )
    variant = group.variant
    flags: list[str] = []
    if request.product != "laz":
        if variant.source_file:
            flags += ["--format", variant.format]
        if variant.label is not None:
            flags += ["--resolution", variant.label]
    flags += ["--vertical-crs", group.vertical_crs, "--year", str(group.year)]
    if request.product != "laz" and any(
        _needs_full_sheet(rows) for rows in by_sheet.values()
    ):
        flags.append("--full-sheet")
    return tuple(
        shlex.join(
            ["elevation", "download", "--product", request.product, *area, *flags]
        )
        for area in areas
    )


def _needs_full_sheet(rows: list[_Entry]) -> bool:
    """The newest record of a sheet is not full while a full one exists."""
    newest = max(rows, key=lambda r: (r.date, r.published or "", r.url))
    return newest.full is not True and any(r.full is True for r in rows)


def _cz_hint(request: _Request, file: _CzFile, sheets: list[str]) -> tuple[str, ...]:
    """Commands downloading the files ``sheets`` of a CZ combination (after
    ``kartograf ``, without ``--output``): a raster - one command per sheet
    (``--sheet``, label, native height system); LAZ - one command for the
    area of the request (``--country cz``, ``--model``), a sheet request -
    one per sheet (a code reaches only its own sheet system)."""
    if not sheets:
        return ()
    variant = file.variant
    product = request.product
    if product == "laz":
        assert variant.model is not None
        flags = ["--model", variant.model, "--vertical-crs", variant.vertical_crs]
        areas = (
            [["--sheet", sheet] for sheet in sheets]
            if request.cz_sheet is not None
            else [_area_flags(request, "cz")]
        )
    else:
        assert variant.label is not None
        flags = ["--resolution", variant.label, "--vertical-crs", variant.vertical_crs]
        areas = [["--sheet", sheet] for sheet in sheets]
    return tuple(
        shlex.join(["elevation", "download", "--product", product, *area, *flags])
        for area in areas
    )
