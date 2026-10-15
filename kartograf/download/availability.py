"""
Availability report of elevation data per the GUGiK index (spec 4, ADR-041).

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

The index answers, the feature types and the land mask go through the
metadata cache (``index_area_cache``, TTL as the index records): a repeated
report asks no service; ``force=True`` asks again and overwrites the entries.
"""

import json
import math
import shlex
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
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
    expand_convex,
    normalize_convex,
    polygon_area,
    rectangle,
)
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.area import bbox_to_2180, resolve_geometry_layer
from kartograf.download.arguments import require_bool
from kartograf.download.campaigns import in_year_range, year_range_label
from kartograf.download.options import (
    product_choices,
    validate_area_choice,
    year_bounds,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import INDEX_UNSUPPORTED, Notice, NoticeSink
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
from kartograf.sources.registry import parse_pl_system
from kartograf.sources.variants import (
    FORMATS,
    IndexRef,
    ProductVariant,
    resolution_label,
    source_format,
    variants,
)
from kartograf.transport.http import MAX_RETRIES, SessionPerThread

AVAILABILITY_SCHEMA = "kartograf-availability/1"
# Products of the report (the `elevation` group).
AVAILABILITY_PRODUCTS = ("nmt", "nmpt", "laz")
# Countries of the report (plan B adds cz and auto).
AVAILABILITY_COUNTRIES = {"pl": "pl (GUGiK)"}
COUNTRY_CHOICES = ", ".join(AVAILABILITY_COUNTRIES.values())

# Timeout (s) of every index and PRG request (as the sheet providers).
_TIMEOUT = 30
# Pixels per row strip of the completeness grid (as LandMask.apply).
_STRIP_PX = 4_000_000
_HORIZONTAL = {"1992": "PL-1992", "2000": "PL-2000"}
_FORMAT_ORDER = {f.token: i for i, f in enumerate(FORMATS)}
# Why an index record is not downloadable (INDEX_UNSUPPORTED texts).
_REASONS = {
    "sheet": "godla spoza ukladow arkuszy PL-1992/PL-2000 (np. 8-czlonowe)",
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
    W02/W03) - the part every combination is measured against.
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
    ``sheets_missing`` and ``size_bytes`` are CZ fields (plan B; PL: empty).
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

    ``combinations`` newest year first, then sheet system, resolution,
    height system and format; ``ok`` is ``False`` only when a part of the
    request could not be checked (plan B, ``country="auto"``).
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
    sheet: SheetParser | None
    bbox: BBox | None
    geometry: Path | None
    layer: str | None
    min_year: int | None
    max_year: int | None


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
    """Report which data the index has for an area - nothing is downloaded.

    Parameter names and values are the ``elevation availability`` flags in
    ``snake_case``: ``product`` (``nmt``, ``nmpt``, ``laz``), one area choice
    (``sheet``, ``bbox`` in any supported CRS, ``geometry`` SHP/GPKG with
    ``layer``), ``country`` (``pl``; required with ``bbox``/``geometry``, a
    sheet code names its country), year bounds as in ``download_data``
    (``year`` = ``min_year = max_year``; the index layers outside them are
    not queried). ``cache``: ``True`` = default metadata cache in the current
    directory, a ``MetadataCache`` = that cache, ``False`` = none; ``force``
    asks the services again (and overwrites the cache). ``on_notice``
    receives each notice when it is emitted.

    Raises
    ------
    ValidationError
        Invalid or missing choice (before the network; texts name the CLI
        flags as in ``download_data``), or year bounds without a layer in the
        index (after GetCapabilities).
    ParseError
        Malformed sheet code.
    DownloadError
        An index or PRG request failed - never an empty report.
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
    areas = _area_polygons(request, layer_name)
    envelope = area_envelope(areas)
    sessions = SessionPerThread(None)
    with open_cache(cache, force=force, on_notice=sink.add) as metadata:
        services = _services(request.product)
        typed = [
            (service, _feature_types(service, sessions, metadata))
            for service in services
        ]
        selected = [
            (
                service,
                [
                    name
                    for name in types
                    if in_year_range(
                        type_year(name), request.min_year, request.max_year
                    )
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
    combinations = tuple(
        _combination(request, group, missing, uncovered)
        for group, (missing, uncovered) in zip(groups, measured, strict=True)
    )
    return AvailabilityReport(
        request=_request_payload(request, layer_name),
        checked_at=_clock.now().isoformat(timespec="seconds"),
        areas=(
            AvailabilityArea(
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
            ),
        ),
        combinations=combinations,
        notices=sink.notices,
        ok=True,
    )


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
    """Checks before the network, with the texts of ``download_data``."""
    from kartograf.core.parser_registry import detect_system

    validate_area_choice(sheet, bbox, geometry)
    choices = product_choices(AVAILABILITY_PRODUCTS)
    if product is None:
        raise ValidationError(f"--product wymagane: {choices}")
    if product not in AVAILABILITY_PRODUCTS:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: {choices}"
        )
    parsed = None
    if sheet is not None:
        system = detect_system(sheet)
        if system.country != "PL":
            raise ValidationError(
                f"Godlo '{sheet}' nalezy do systemu {system.id} (kraj "
                f"{system.country}) - raport dostepnosci obejmuje: {COUNTRY_CHOICES}"
            )
        parsed = SheetParser(sheet)
    elif country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    if country is not None and country not in AVAILABILITY_COUNTRIES:
        raise ValidationError(
            f"--country {country!r}: raport dostepnosci obejmuje: {COUNTRY_CHOICES}"
        )
    lo, hi = year_bounds(year, min_year, max_year)
    return _Request(
        product=product,
        sheet=parsed,
        bbox=bbox,
        geometry=Path(geometry) if geometry is not None else None,
        layer=layer,
        min_year=lo,
        max_year=hi,
    )


def _request_payload(request: _Request, layer_name: str | None) -> dict:
    """``AvailabilityReport.request``: product, country, area (as the sidecar
    ``request``), year bounds."""
    payload: dict = {"product": request.product, "country": "pl"}
    if request.sheet is not None:
        payload["sheet"] = request.sheet.sheet
    elif request.bbox is not None:
        payload["bbox"] = bbox_coords(request.bbox)
        payload["bbox_crs"] = request.bbox.crs
    else:
        payload["geometry"] = str(request.geometry)
        payload["layer"] = layer_name
    payload["min_year"] = request.min_year
    payload["max_year"] = request.max_year
    return payload


def _area_polygons(request: _Request, layer_name: str | None) -> list[Polygon]:
    """The area as convex (E, N) polygons in EPSG:2180 - the area a download
    of the same choice covers: NMT/NMPT the sheet frame, the bbox envelope,
    the feature envelopes of the geometry file (sheets per feature); LAZ the
    envelope of the sheet frame or of the whole geometry (tiles of one bbox).
    """
    from kartograf.core.geometry import get_overall_bbox, read_feature_bboxes

    laz = request.product == "laz"
    if request.sheet is not None:
        if laz:
            b = request.sheet.get_bbox(crs="EPSG:2180")
            return [rectangle(b.min_x, b.min_y, b.max_x, b.max_y)]
        return [sheet_frame_2180(request.sheet.sheet)]
    if request.bbox is not None:
        b = bbox_to_2180(request.bbox)
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
    request: _Request, group: _Group, missing: int, uncovered: int
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
        download_hint=_download_hint(request, group, by_sheet),
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
# Download hint (decision 8 of plan A)
# =============================================================================


def _scale_order(scale: str) -> int:
    """``1:5000`` before ``1:2000`` (coarser first)."""
    return -int(scale.split(":")[1])


def _number(value: float) -> str:
    return format(float(value), ".15g")


def _area_flags(request: _Request) -> list[str]:
    """``--country pl`` and the bbox/geometry of the request."""
    if request.bbox is not None:
        b = request.bbox
        coords = ",".join(_number(v) for v in (b.min_x, b.min_y, b.max_x, b.max_y))
        bbox = [f"--bbox={coords}"] if coords.startswith("-") else ["--bbox", coords]
        crs = ["--bbox-crs", b.crs] if b.crs != "EPSG:2180" else []
        return ["--country", "pl", *bbox, *crs]
    assert request.geometry is not None
    layer = ["--layer", request.layer] if request.layer is not None else []
    return ["--country", "pl", "--geometry", str(request.geometry), *layer]


def _sheet_area(request: _Request, group: _Group, sheets: list[str]) -> list[list[str]]:
    """Area flags of a sheet request: the code itself when a download of it
    reaches the combination's sheets, else one command per sheet."""
    code = request.sheet
    assert code is not None
    if request.product == "laz":
        return [["--sheet", code.sheet]]
    if group.system == code.sheet_system:
        if group.variant.source_file or group.system == "1992":
            return [["--sheet", code.sheet]]
        if all(s == code.sheet or s.startswith(code.sheet + ".") for s in sheets):
            scales = sorted({SheetParser(s).scale for s in sheets}, key=_scale_order)
            return [
                ["--sheet", code.sheet]
                + ([] if scale == code.scale else ["--scale", scale])
                for scale in scales
            ]
    return [["--sheet", sheet] for sheet in sheets]


def _download_hint(
    request: _Request, group: _Group, by_sheet: dict[str, list[_Entry]]
) -> tuple[str, ...]:
    """Commands downloading the combination (after ``kartograf ``, without
    ``--output``): the area of the request, the sheet system and scale
    (PL-2000 grids: one command per scale), the variant, ``--year`` and
    ``--full-sheet`` when a sheet's newest record of the year is partial while
    a full one exists."""
    sheets = sorted(by_sheet)
    if request.sheet is not None:
        areas = _sheet_area(request, group, sheets)
    elif request.product == "laz":
        areas = [_area_flags(request)]
    else:
        base = [*_area_flags(request), "--sheet-system", group.system]
        if group.system == "2000" and not group.variant.source_file:
            scales = sorted({SheetParser(s).scale for s in sheets}, key=_scale_order)
            areas = [[*base, "--scale", scale] for scale in scales]
        else:
            areas = [base]
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
