"""
Collections on the versioned store (ADR-042 D2, D6-D10, D12; ADR-043).

One orchestrator for every channel with typed engine parameters
(``AccessChannel.params``): ``download_collection``/``check_collection`` are
the ``download`` commands of the collection groups (``boundaries``,
``cadastre``, ``models3d``, ``hydro`` and the groups of plan E).
``validate_collection_request`` checks the whole choice WITHOUT network
(exactly one selection, product, country, unit, channel, variant, level,
CRS) and is the only place of these rules. The kind of selection and the
option values (``format``, ``scale``, ``sheet_system``, ``network``, read
from the descriptor, K1) pick the channel: ``teryt`` -> the package of that
unit (``unit_package``); ``ku`` -> the package of a CZ cadastral area; an
area (``bbox``/``sheet``/``geometry``) -> one GeoPackage of the area in the
native CRS of the service (``feature_bbox``: WFS, ArcGIS REST, OGC API
Features), the files of its map sheets (PL-1992 series computed from the
extent, a layer of the CUZK sheet index), of its index tiles (WFS records)
or of its CZ cadastral areas (RUIAN), or - for a product without such a
channel - the package of every powiat of the area (PRG); the units of an
area are listed in a ``UNIT_LIST`` notice. ``whole_country`` -> the
national file (one per theme; ``unit_package`` of the country or a file of
a CUZK ATOM feed, ``atom_files``: edition = signal ``metadata``) after a
``WHOLE_COUNTRY_SIZE`` notice (K7). A unit file over 100 MiB is announced
by ``DOWNLOAD_SIZE`` (``HEAD``) before its transfer (K9). The record of an
index (GetFeatureInfo, WFS) gives the URL of a sheet or tile file and the
label of its version: signal ``index`` compares that label with the local
version without a transfer. Every file goes through
``fetch_version``/``inspect_version`` of its slot (plan track
``collection``); a failing unit lands in ``failed``, the others still run.

``LandCoverManager`` runs the BDOT10k archive through the same unit jobs
(``package_job``, ``run_job``, ``inspect_job``) and ZABAGED through
``landcover_request``/``run_request``/``plan_request`` on its own plan track.
"""

import concurrent.futures
import functools
import logging
import re
import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords, is_czech_crs, transform_bbox
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox, series_scale
from kartograf.download.area import (
    bbox_to_2180,
    emit_clipping_notices,
    geometry_envelope,
    parent_request_for,
    resolve_geometry_layer,
)
from kartograf.download.arguments import require_bool, require_int, require_str
from kartograf.download.countries import countries_for_bbox, country_bbox
from kartograf.download.data import UnitFailure, UnitFile
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    emit_file_notices,
    fetch_version,
    inspect_version,
    link_version,
    local_version,
    validate_update,
)
from kartograf.download.options import (
    COUNTRY_CHOICES,
    check_per_country,
    country_value,
    validate_request_bbox,
)
from kartograf.download.plan import (
    PlanItem,
    Track,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import bbox_cutout_path, content_segment, unit_slot
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.notices import (
    AUTO_NARROWED_TO_CZ,
    AUTO_NARROWED_TO_PL,
    DOWNLOAD_SIZE,
    LARGE_FILE_BYTES,
    UNIT_LIST,
    WHOLE_COUNTRY_SIZE,
    Notice,
    NoticeSink,
    size_text,
)
from kartograf.providers.pl.bdot10k import WOJEWODZTWO_NAMES
from kartograf.providers.pl.prg import discover_teryts_for_bbox
from kartograf.sources.descriptor import (
    AccessChannel,
    AtomFilesParams,
    ChannelParams,
    FeatureBBoxParams,
    FeatureLayer,
    PackageVariant,
    SheetGrid,
    SignalKind,
    SourceDescriptor,
    UnitPackageParams,
)
from kartograf.sources.edition import Edition
from kartograf.sources.registry import (
    get_source,
    horizontal_crs_for_system,
    sources_for,
)
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.atom import (
    AtomFile,
    atom_segment_tokens,
    check_atom_crs,
    fetch_atom_file,
    resolve_atom_file,
)
from kartograf.transport.http import SessionPerThread, head_signal
from kartograf.transport.index_records import IndexRecord, gfi_records, wfs_records
from kartograf.transport.unit_package import (
    FILE_SUFFIX,
    choice_keys,
    fetch_package,
    index_url,
    package_url,
    select_variant,
)

logger = logging.getLogger(__name__)

# One WFS/REST request (pages of GUGiK services answer in seconds; a busy
# service gets the shared retry policy; a slower service declares its own
# ``FeatureBBoxParams.timeout``), one package transfer (as BDOT10k), a HEAD
# of a file and the PRG powiat query.
SERVICE_TIMEOUT = 60
PACKAGE_TIMEOUT = 120
PROBE_TIMEOUT = 30

_TRACK: Track = "collection"
# Land cover products stay with LandCoverManager (ADR-039 D8, ADR-042 D10).
_LANDCOVER_GROUP = "landcover"
_TERYT = re.compile(r"[0-9]{2}(?:[0-9]{2})?")
_KU = re.compile(r"[0-9]{6}")
_MAPNOM = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
_UNIT_TEXT = {
    "powiat": "paczek powiatow",
    "woj": "paczek wojewodztw",
    "country": "pliku krajowego",
    "ku": "paczek katastralnich uzemi",
}
# Option values that select a channel or a published variant (ADR-043); the
# allowed values are read from the descriptors (K1).
_OPTION_NAMES = ("format", "scale", "sheet_system", "network")
# CRSs ``find_sheets_for_bbox`` accepts as they are (PL-1992, WGS84, PL-2000).
_PL_GRID_CRS = (
    "EPSG:2180",
    "EPSG:4326",
    "EPSG:2176",
    "EPSG:2177",
    "EPSG:2178",
    "EPSG:2179",
)
_SLOT_KEY = tuple[str, str, str]

_sessions = SessionPerThread()


def _session() -> requests.Session:
    """HTTP session of the current thread (one per worker)."""
    return _sessions.get()


# =============================================================================
# Products of the collection commands
# =============================================================================


def _is_collection(descriptor: SourceDescriptor) -> bool:
    """A product of ``download_collection``: a channel of a collection engine
    (unit packages, features of an area) outside ``landcover``; the ATOM and
    WCS cutout channels of ``imagery`` products are not collections."""
    return descriptor.storage_subdir.split("/", 1)[0] != _LANDCOVER_GROUP and any(
        isinstance(channel.params, UnitPackageParams | FeatureBBoxParams)
        for channel in descriptor.channels
    )


def collection_products(group: str | None = None) -> tuple[str, ...]:
    """Products of ``download_collection`` in registry order; ``group`` = the CLI
    group (first element of the storage segment: ``boundaries``, ...)."""
    products: list[str] = []
    for descriptor in sources_for():
        if not _is_collection(descriptor):
            continue
        if group is not None and not descriptor.storage_subdir.startswith(f"{group}/"):
            continue
        if descriptor.product not in products:
            products.append(descriptor.product)
    return tuple(products)


def collection_product_choices(products: Sequence[str] | None = None) -> str:
    """``admin (PRG - granice ..., PL), ...``: products named in messages and
    ``--help`` (a CLI group names only its own)."""
    names = collection_products() if products is None else tuple(products)
    texts = []
    for product in names:
        descriptors = [d for d in sources_for(product=product) if _is_collection(d)]
        sources = "; ".join(f"{d.name}, {d.country}" for d in descriptors)
        texts.append(f"{product} ({sources})")
    return ", ".join(texts)


def _distinct(values: Iterable[str]) -> tuple[str, ...]:
    """Distinct values in their first order."""
    return tuple(dict.fromkeys(values))


def _channel_options(params: ChannelParams | None) -> dict[str, tuple[str, ...]]:
    """Option values a channel offers (ADR-043): the variant choices of a unit
    package channel, the ``choice`` selecting a feature or ATOM channel and
    the layer codes chosen by ``selection_key``."""
    if isinstance(params, UnitPackageParams):
        return {
            key: _distinct(dict(variant.choice)[key] for variant in params.variants)
            for key in choice_keys(params)
        }
    options: dict[str, tuple[str, ...]] = {}
    if isinstance(params, FeatureBBoxParams | AtomFilesParams):
        options = {key: (value,) for key, value in params.choice}
    if isinstance(params, FeatureBBoxParams) and params.selection == "level":
        options[params.selection_key] = _distinct(layer.code for layer in params.layers)
    return options


def collection_choice_values(product: str, key: str) -> dict[str, tuple[str, ...]]:
    """Values of the option ``key`` of a collection product per country, in
    registry order (``level``, ``lod``, ``year``, ``format``, ``scale``,
    ``sheet_system``, ``network``; ``--help`` and messages; empty: the
    product has no such option)."""
    found: dict[str, list[str]] = {}
    for descriptor in sources_for(product=product):
        if not _is_collection(descriptor):
            continue
        for channel in descriptor.channels:
            for value in _channel_options(channel.params).get(key, ()):
                values = found.setdefault(descriptor.country, [])
                if value not in values:
                    values.append(value)
    return {country: tuple(values) for country, values in found.items()}


def collection_levels(product: str) -> dict[str, tuple[str, ...]]:
    """``--level`` values of a product per country (empty: no levels)."""
    return collection_choice_values(product, "level")


def collection_layers(descriptor_key: str) -> tuple[FeatureLayer, ...]:
    """Layers of the area channel of a source (``()``: no area channel)."""
    channel = _feature_channel(get_source(descriptor_key))
    if channel is None:
        return ()
    assert isinstance(channel.params, FeatureBBoxParams)
    return channel.params.layers


def require_collection_product(product: str | None, group: str) -> None:
    """``product`` of a collection group command (``boundaries download``,
    ...): one of the group's products; a missing one names only them.

    Raises
    ------
    ValidationError
        Missing product or a product of another group.
    """
    products = collection_products(group)
    if product is None:
        raise ValidationError(
            f"--product wymagane: {collection_product_choices(products)}"
        )
    if product not in products:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: "
            f"{collection_product_choices(products)}"
        )


def collection_level_choices(products: Sequence[str]) -> str:
    """``admin PL: wojewodztwo, powiat, ...``: ``--level`` values of
    ``products`` per country (``--help``)."""
    return "; ".join(
        f"{product} {country}: {', '.join(codes)}"
        for product in products
        for country, codes in collection_levels(product).items()
    )


def collection_variant_choices(products: Sequence[str]) -> str:
    """``buildings: --lod 1 (--year 2019, 2021), --lod 2 (--year 2017)``: the
    published package variants of ``products`` (``--help`` of the variant
    flags; a channel with one variant needs no choice)."""
    texts = []
    for product in products:
        for descriptor in sources_for(product=product):
            if not _is_collection(descriptor):
                continue
            for channel in descriptor.channels:
                params = channel.params
                if not isinstance(params, UnitPackageParams):
                    continue
                keys = choice_keys(params)
                if not keys:
                    continue
                first, rest = keys[0], keys[1:]
                groups: dict[str, list[dict[str, str]]] = {}
                for variant in params.variants:
                    choice = dict(variant.choice)
                    groups.setdefault(choice[first], []).append(choice)
                items = []
                for value, choices in groups.items():
                    others = "; ".join(
                        f"--{key} {', '.join(dict.fromkeys(c[key] for c in choices))}"
                        for key in rest
                    )
                    items.append(
                        f"--{first} {value}" + (f" ({others})" if others else "")
                    )
                texts.append(f"{product}: {', '.join(items)}")
    return "; ".join(texts)


# =============================================================================
# Validated request (no network)
# =============================================================================


@dataclass(frozen=True)
class CollectionPart:
    """One country part of a validated request.

    ``variant`` (``unit_package``) or ``layers`` (``feature_bbox``) is the
    content; ``choice`` the content values of the sidecar ``request``
    (``year``, ``lod``, ``level``, ``format``, ``scale``, ``sheet_system``,
    ``network``); ``area`` the area of the part (native CRS of a
    ``feature_bbox`` channel; any CRS for the units of a package channel);
    ``sheet`` the requested sheet code of a sheet channel (the series sheets
    of its extent, or the CUZK sheet itself); ``year_filter`` the year of the
    index records of a ``tile``/``sheet`` channel (the newest record of a
    unit without it); ``parent`` the ``extra.parent_request`` of its files;
    ``extra`` more ``extra`` of their sidecars (``vertical_crs_note``).
    """

    country: str
    descriptor: SourceDescriptor
    channel: AccessChannel
    variant: PackageVariant | None
    layers: tuple[FeatureLayer, ...]
    segment: str
    ext: str
    choice: dict
    area: BBox | None = None
    parent: dict | None = None
    sheet: str | None = None
    year_filter: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CollectionRequest:
    """A request checked by ``validate_collection_request`` (no network)."""

    product: str
    output_dir: Path
    teryt: str | None
    whole_country: bool
    parts: tuple[CollectionPart, ...]
    ku: str | None = None


@dataclass(frozen=True)
class CollectionReport:
    """Outcome of ``download_collection``.

    ``files``: one ``UnitFile`` per file (``unit`` = TERYT, bbox
    coordinates, the country code with its theme, the sheet code, the tile
    or the CZ cadastral area); ``failed``: units that failed (``kind``
    ``no_coverage`` - no data of the unit at the source - or
    ``download``), the others still ran; ``stale``: planned positions
    changed since the plan; ``ok`` = no failure and no stale position.
    """

    files: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    notices: tuple[Notice, ...]
    ok: bool


def _str(value: object) -> str | None:
    return None if value is None else str(value)


def _descriptors(product: str | None) -> dict[str, SourceDescriptor]:
    """Collection descriptors of ``product`` by country code."""
    if product is None:
        raise ValidationError(f"--product wymagane: {collection_product_choices()}")
    found = {d.country: d for d in sources_for(product=product) if _is_collection(d)}
    if not found:
        raise ValidationError(
            f"Nieznany produkt '{product}'. Dostepne: {collection_product_choices()}"
        )
    return found


_AREA_UNITS = ("sheet", "tile", "ku")
_AREA_TEXT = {
    "sheet": "--bbox/--sheet/--geometry (arkusze obszaru)",
    "tile": "--bbox/--sheet/--geometry (kafle obszaru)",
    "ku": "--bbox/--sheet/--geometry (katastralni uzemi obszaru)",
}


def _available(descriptor: SourceDescriptor) -> str:
    """Selections a product offers (hint of a selection it does not have).

    An area names the channels ``_channel_for`` gives it: the objects of the
    area (``feature_bbox``), its sheets, tiles or cadastral areas, and only
    without those the packages of its powiats.
    """
    area_units = bool(_area_channels(descriptor))
    options: list[str] = []
    for channel in descriptor.channels:
        params = channel.params
        if isinstance(params, UnitPackageParams):
            if params.unit in _AREA_UNITS:
                if params.unit == "ku":
                    options.append("--ku <6 cyfr> (paczka katastralniho uzemi)")
                options.append(_AREA_TEXT[params.unit])
                continue
            options.append(
                {
                    "powiat": "--teryt <4 cyfry> (paczka powiatu)",
                    "woj": "--teryt <2 cyfry> (paczka wojewodztwa)",
                    "country": "--whole-country (plik krajowy)",
                }[params.unit]
            )
            if params.unit == "powiat" and not area_units:
                options.append("--bbox/--sheet/--geometry (paczki powiatow obszaru)")
        elif isinstance(params, FeatureBBoxParams):
            options.append("--bbox/--sheet/--geometry (obiekty obszaru)")
        elif isinstance(params, AtomFilesParams):
            options.append("--whole-country (plik krajowy)")
    return ", ".join(dict.fromkeys(options))


def _package_channels(descriptor: SourceDescriptor, unit: str) -> list[AccessChannel]:
    return [
        channel
        for channel in descriptor.channels
        if isinstance(channel.params, UnitPackageParams) and channel.params.unit == unit
    ]


def _area_channels(descriptor: SourceDescriptor) -> list[AccessChannel]:
    """Channels of an area: features, sheets, tiles and cadastral areas."""
    return [
        channel
        for channel in descriptor.channels
        if isinstance(channel.params, FeatureBBoxParams)
        or (
            isinstance(channel.params, UnitPackageParams)
            and channel.params.unit in _AREA_UNITS
        )
    ]


def _feature_channel(descriptor: SourceDescriptor) -> AccessChannel | None:
    """The first ``feature_bbox`` channel (land cover sources have one)."""
    for channel in descriptor.channels:
        if isinstance(channel.params, FeatureBBoxParams):
            return channel
    return None


def _cuzk_sheet_channel(descriptor: SourceDescriptor) -> bool:
    """Whether a channel addresses the sheets of a CUZK sheet index layer."""
    return any(
        isinstance(channel.params, UnitPackageParams)
        and channel.params.unit == "sheet"
        and any(
            variant.sheet_grid is not None and variant.sheet_grid.system == "cuzk"
            for variant in channel.params.variants
        )
        for channel in descriptor.channels
    )


def subject(descriptor: SourceDescriptor) -> str:
    """How messages name a source: the product of a collection group
    (``admin``), the ``--source`` of a land cover source (``zabaged``)."""
    if descriptor.storage_subdir.split("/", 1)[0] == _LANDCOVER_GROUP:
        return descriptor.key.rsplit(".", 1)[-1]
    return descriptor.product


_SELECTION_TEXT = {
    "teryt": "--teryt",
    "ku": "--ku",
    "whole_country": "--whole-country",
    "area": "obszaru",
}


def _candidates(
    descriptor: SourceDescriptor, kind: str, teryt: str | None
) -> tuple[list[AccessChannel], str]:
    """Channels of a kind of selection (ADR-042 D2, ADR-043) and the text of
    their absence."""
    product, country = subject(descriptor), descriptor.country
    if kind == "teryt":
        assert teryt is not None
        unit = "woj" if len(teryt) == 2 else "powiat"
        missing = f"--teryt {teryt}: {product} nie ma {_UNIT_TEXT[unit]}"
        return _package_channels(descriptor, unit), missing
    if kind == "ku":
        missing = f"--ku: {product} ({country}) nie ma {_UNIT_TEXT['ku']}"
        return _package_channels(descriptor, "ku"), missing
    if kind == "whole_country":
        atom = [c for c in descriptor.channels if isinstance(c.params, AtomFilesParams)]
        missing = f"--whole-country: {product} ({country}) nie ma pliku krajowego"
        return _package_channels(descriptor, "country") + atom, missing
    channels = _area_channels(descriptor) or _package_channels(descriptor, "powiat")
    return channels, f"{product} ({country}) nie ma danych dla obszaru"


def _selecting_options(params: ChannelParams | None) -> dict[str, tuple[str, ...]]:
    """Option values that tell channels apart: the variant choices of a unit
    package channel and the ``choice`` of a feature or ATOM channel (the
    layer codes of ``selection_key`` choose layers inside one channel)."""
    options = _channel_options(params)
    if (
        isinstance(params, FeatureBBoxParams)
        and params.selection == "level"
        and params.selection_key not in dict(params.choice)
    ):
        options.pop(params.selection_key, None)
    return options


def _channel_for(
    descriptor: SourceDescriptor,
    kind: str,
    teryt: str | None,
    options: Mapping[str, str | None],
) -> AccessChannel:
    """The channel of a kind of selection (ADR-042 D2); of several, the one
    whose option values (``network``, ``format``, ...) admit the given ones
    (ADR-043: one WFS service per network, one ATOM feed per format). A
    single candidate is returned as it is - its content checks name the
    allowed values (``_content``)."""
    candidates, missing = _candidates(descriptor, kind, teryt)
    if not candidates:
        raise ValidationError(f"{missing}; dostepne: {_available(descriptor)}")
    if len(candidates) == 1:
        return candidates[0]
    offered = [_selecting_options(channel.params) for channel in candidates]
    keys = _distinct(key for found in offered for key in found)
    given = {k: v for k, v in options.items() if v is not None and k in keys}
    where = f"{_SELECTION_TEXT[kind]} {subject(descriptor)} ({descriptor.country})"

    def admits(found: dict[str, tuple[str, ...]], pairs: dict[str, str]) -> bool:
        return all(value in found.get(key, ()) for key, value in pairs.items())

    admitted = [
        c for c, found in zip(candidates, offered, strict=True) if admits(found, given)
    ]
    if not admitted:
        for key, value in given.items():
            if not any(admits(found, {key: value}) for found in offered):
                values = _distinct(v for found in offered for v in found.get(key, ()))
                raise ValidationError(
                    f"--{key} {value}: niedostepne dla {where}; dostepne: "
                    f"{', '.join(values)}"
                )
        chosen = " ".join(f"--{key} {value}" for key, value in given.items())
        raise ValidationError(f"{chosen}: niedostepne razem dla {where}")
    if len(admitted) > 1:
        found_admitted = [
            found
            for channel, found in zip(candidates, offered, strict=True)
            if channel in admitted
        ]
        for key in keys:
            if key in given:
                continue
            sets = {found.get(key, ()) for found in found_admitted}
            if len(sets) > 1:
                values = _distinct(
                    v for found in found_admitted for v in found.get(key, ())
                )
                raise ValidationError(
                    f"--{key} wymagane dla {where}: {', '.join(values)}"
                )
    return admitted[0]


def _level_hint(level: str | Mapping[str, str] | None, product: str) -> str:
    """Hint of the per-country ``--level`` syntax for a request in PL and CZ
    given one plain value (the levels of the countries differ)."""
    if not isinstance(level, str):
        return ""
    levels = collection_levels(product)
    if len(levels) < 2:
        return ""
    example = ",".join(f"{code.lower()}=<poziom>" for code in levels)
    return f" (zadanie PL+CZ: poziom per kraj, np. --level {example})"


def _content(
    code: str,
    descriptor: SourceDescriptor,
    channel: AccessChannel,
    *,
    level: str | Mapping[str, str] | None,
    lod: int | None,
    year: int | None,
    options: Mapping[str, str | None],
    horizontal_crs: str | None,
    countries: tuple[str, ...] = (),
) -> CollectionPart:
    """Content of one country part: variant, layers or ATOM file, segment and
    request values. ``options``: ``format``, ``scale``, ``sheet_system``,
    ``network`` (``None`` = not given). ``countries``: the countries of an
    area request (hint of the per-country ``--level`` syntax)."""
    product = subject(descriptor)
    params = channel.params
    level_value = country_value(level, code)
    given = {key: value for key, value in options.items() if value is not None}
    variant: PackageVariant | None = None
    layers: tuple[FeatureLayer, ...] = ()
    year_filter: int | None = None
    choice: dict[str, object]
    if isinstance(params, UnitPackageParams):
        if level_value is not None:
            raise ValidationError(
                f"--level dotyczy obiektow obszaru (--bbox/--sheet/--geometry), nie "
                f"paczek {product}"
            )
        # the year of index records filters them when it is not a variant
        record_year = params.index is not None and "year" not in choice_keys(params)
        variant = select_variant(
            params,
            lod=_str(lod),
            year=None if record_year else _str(year),
            **given,
        )
        if record_year:
            year_filter = year
        segment = content_segment(descriptor.key, variant.segment_tokens)
        ext = params.unpack or FILE_SUFFIX[variant.file_kind]
        choice = {
            key: value
            for key, value in (("lod", lod), ("year", year), *given.items())
            if value is not None
        }
        crs = channel.horizontal_crs
    elif isinstance(params, AtomFilesParams):
        selecting = dict(params.choice)
        rest = [(k, v) for k, v in given.items() if k not in selecting]
        for name, value in (
            ("level", level_value),
            ("lod", lod),
            ("year", year),
            *rest,
        ):
            if value is not None:
                raise ValidationError(
                    f"--{name} nie dotyczy pliku krajowego {product} "
                    f"({descriptor.country}: biezace wydanie z feedu ATOM)"
                )
        _check_selecting(selecting, given, f"pliku krajowego {product} ({code})")
        check_atom_crs(params, horizontal_crs)
        segment = content_segment(
            descriptor.key, atom_segment_tokens(params, horizontal_crs)
        )
        ext = ".zip"
        choice = dict(given)
        crs = horizontal_crs or channel.horizontal_crs
    else:
        assert isinstance(params, FeatureBBoxParams)
        layers, tokens, choice = _feature_content(
            params, descriptor, code, level, level_value, lod, year, given, countries
        )
        segment = content_segment(descriptor.key, tokens)
        ext = ".gpkg"
        crs = params.native_crs
        if horizontal_crs is not None and horizontal_crs != crs:
            raise ValidationError(
                f"--horizontal-crs {horizontal_crs}: obiekty obszaru {product} "
                f"({descriptor.country}) sa zawsze w ukladzie uslugi {crs}"
            )
    if horizontal_crs is not None and horizontal_crs != crs:
        raise ValidationError(
            f"--horizontal-crs {horizontal_crs}: {product} ({descriptor.country}) "
            f"publikuje ten plik tylko w {crs}"
        )
    if horizontal_crs is not None:
        choice["horizontal_crs"] = horizontal_crs
    return CollectionPart(
        code,
        descriptor,
        channel,
        variant,
        layers,
        segment,
        ext,
        choice,
        year_filter=year_filter,
    )


def _check_selecting(
    selecting: Mapping[str, str], given: Mapping[str, str], where: str
) -> None:
    """A given value of an option selecting the channel equals the channel's."""
    for key, value in given.items():
        if key in selecting and selecting[key] != value:
            raise ValidationError(
                f"--{key} {value}: niedostepne dla {where}; dostepne: {selecting[key]}"
            )


def _feature_content(
    params: FeatureBBoxParams,
    descriptor: SourceDescriptor,
    code: str,
    level: str | Mapping[str, str] | None,
    level_value: str | None,
    lod: int | None,
    year: int | None,
    given: Mapping[str, str],
    countries: tuple[str, ...],
) -> tuple[tuple[FeatureLayer, ...], tuple[str, ...], dict[str, object]]:
    """Layers, segment tokens and request values of a ``feature_bbox`` part:
    the values of the channel ``choice`` and of its ``selection_key``."""
    product = subject(descriptor)
    where = f"obszaru {product} ({descriptor.country})"
    for name, number in (("lod", lod), ("year", year)):
        if number is not None:
            raise ValidationError(
                f"--{name} nie dotyczy obiektow obszaru produktu {product} "
                f"({descriptor.country}: biezacy stan uslugi)"
            )
    selecting = dict(params.choice)
    selector = params.selection_key if params.selection == "level" else None
    for key in given:
        if key not in selecting and key != selector:
            raise ValidationError(
                f"--{key} nie dotyczy obiektow obszaru produktu {product} "
                f"({descriptor.country})"
            )
    _check_selecting(selecting, given, where)
    choice: dict[str, object] = dict(selecting)
    tokens = tuple(selecting.values())
    codes = _distinct(layer.code for layer in params.layers)
    if selector is None:
        if level_value is not None:
            raise ValidationError(
                f"--level nie dotyczy produktu {product} (stala zawartosc: "
                f"{', '.join(codes)})"
            )
        return params.layers, tokens, choice
    if selector == "level":
        value = level_value
        hint = _level_hint(level, descriptor.product) if len(countries) > 1 else ""
        unknown = f"nieznany poziom {product} ({descriptor.country})"
    else:
        if level_value is not None:
            raise ValidationError(
                f"--level nie dotyczy produktu {product} (wybor: --{selector} "
                f"{', '.join(codes)})"
            )
        value, hint, unknown = given.get(selector), "", f"niedostepne dla {where}"
    if value is None:
        raise ValidationError(
            f"--{selector} wymagane dla {where}: {', '.join(codes)}{hint}"
        )
    if value not in codes:
        raise ValidationError(
            f"--{selector} {value}: {unknown}; dostepne: {', '.join(codes)}{hint}"
        )
    layers = tuple(layer for layer in params.layers if layer.code == value)
    return layers, (*tokens, value), {**choice, selector: value}


def _selection_kind(args: dict) -> str:
    given = [
        name
        for name in ("teryt", "ku", "sheet", "bbox", "geometry")
        if args[name] is not None
    ] + (["whole_country"] if args["whole_country"] else [])
    if len(given) != 1:
        raise ValidationError(
            "Podaj dokladnie jeden wybor: --teryt, --ku, --sheet, --bbox, "
            "--geometry albo --whole-country"
        )
    return {"sheet": "area", "bbox": "area", "geometry": "area"}.get(given[0], given[0])


def _to_crs(bbox: BBox, crs: str) -> BBox:
    """The area in the native CRS of a service (Czech CRSs: pinned operation)."""
    if bbox.crs == crs:
        return bbox
    if crs == "EPSG:2180":
        return bbox_to_2180(bbox)
    if is_czech_crs(crs) or is_czech_crs(bbox.crs):
        from kartograf.providers.cuzk.raster import bbox_to_crs

        return bbox_to_crs(bbox, crs)
    return transform_bbox(bbox, crs)


def validate_collection_request(
    *,
    product: str | None,
    output_dir: str | Path | None,
    country: str | None = None,
    teryt: str | None = None,
    ku: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    format: str | None = None,
    scale: str | None = None,
    sheet_system: str | None = None,
    network: str | None = None,
    horizontal_crs: str | None = None,
) -> CollectionRequest:
    """Check a collection request without network (ADR-042 D2, ADR-043).

    The same rules as ``download_collection`` and ``check_collection``
    (they call it first): ``bbox`` coordinates, exactly one of ``teryt``
    (2 digits = voivodeship, 4 = powiat; PL), ``ku`` (CZ cadastral area,
    6 digits), ``sheet``, ``bbox``, ``geometry``, ``whole_country``;
    ``product`` of the registry; ``country`` (``pl``/``cz``/``auto``)
    required with an area and with ``whole_country`` (``auto`` not), from
    the code with ``sheet``, ``pl`` with ``teryt``, ``cz`` with ``ku``; a
    channel for the kind of selection and the option values (``format``,
    ``scale``, ``sheet_system``, ``network`` - the values of the
    descriptors); the variant (``lod``, ``year`` and those options)
    required when the source publishes several, a level (``level``, per
    country with ``auto``) for an area of a product with levels;
    ``horizontal_crs`` only equal to the CRS of the file. Reads the
    geometry file (its envelope) - never the network.

    Raises
    ------
    ValidationError
        Any invalid or missing choice; the text names the CLI flags.
    """
    return _resolve(dict(locals()), NoticeSink(None))


def _resolve(
    args: dict,
    sink: NoticeSink,
    descriptors: dict[str, SourceDescriptor] | None = None,
) -> CollectionRequest:
    """``validate_collection_request`` with the notices of the area choice;
    ``descriptors``: the sources by country (default: the collection
    descriptors of ``product``; a land cover source passes its own)."""
    if args["bbox"] is not None:  # the CLI parses --bbox first: the same first error
        validate_request_bbox(args["bbox"])
    # library calls only: the CLI parses its flags (STANDARDS 11.2)
    require_bool(args["whole_country"], "--whole-country")
    for name in ("lod", "year"):
        if args[name] is not None:
            require_int(args[name], f"--{name}")
    for name in ("teryt", "ku", "sheet", *_OPTION_NAMES):
        if args[name] is not None:
            require_str(args[name], f"--{name.replace('_', '-')}")
    product = args["product"]
    if descriptors is None:
        descriptors = _descriptors(product)
    if args["output_dir"] is None:
        raise ValidationError(
            "--output wymagane: katalog magazynu (pliki w <KATALOG>/<grupa>/...)"
        )
    kind = _selection_kind(args)
    check_per_country(args["level"], "--level")
    country = args["country"]
    if country is not None and country not in ("pl", "cz", "auto"):
        raise ValidationError(f"Nieznany kraj --country {country!r}: {COUNTRY_CHOICES}")
    options = {name: args[name] for name in _OPTION_NAMES}
    content = {
        "level": args["level"],
        "lod": args["lod"],
        "year": args["year"],
        "options": options,
        "horizontal_crs": args["horizontal_crs"],
    }
    teryt, ku = args["teryt"], args["ku"]
    output_dir = Path(args["output_dir"])

    def part(
        code: str, area_kind: str, countries: tuple[str, ...] = ()
    ) -> CollectionPart:
        descriptor = descriptors.get(code)
        if descriptor is None:
            raise ValidationError(
                f"--product {product} jest dostepny tylko dla "
                f"{', '.join(sorted(descriptors))}"
            )
        channel = _channel_for(descriptor, area_kind, teryt, options)
        return _content(code, descriptor, channel, countries=countries, **content)

    if kind == "teryt":
        assert teryt is not None
        if country not in (None, "pl"):
            raise ValidationError(
                f"--teryt to kod TERYT (PL); usun --country {country}"
            )
        if not _TERYT.fullmatch(teryt) or teryt[:2] not in WOJEWODZTWO_NAMES:
            raise ValidationError(
                f"Nieprawidlowy kod TERYT {teryt!r}: wojewodztwo (2 cyfry, np. 12) "
                "albo powiat (4 cyfry, np. 1261)"
            )
        return CollectionRequest(
            product, output_dir, teryt, False, (part("PL", "teryt"),)
        )
    if kind == "ku":
        assert ku is not None
        if country not in (None, "cz"):
            raise ValidationError(
                f"--ku to kod katastralniho uzemi (CZ); usun --country {country}"
            )
        if not _KU.fullmatch(ku):
            raise ValidationError(
                f"Nieprawidlowy kod katastralniho uzemi {ku!r}: 6 cyfr, np. 623164"
            )
        return CollectionRequest(
            product, output_dir, None, False, (part("CZ", "ku"),), ku=ku
        )
    if kind == "whole_country":
        if country not in ("pl", "cz"):
            raise ValidationError(
                "--whole-country wymaga --country pl albo --country cz (plik krajowy "
                "jednego kraju)"
            )
        whole = part(country.upper(), "whole_country")
        return CollectionRequest(product, output_dir, None, True, (whole,))
    if args["sheet"] is not None:
        return CollectionRequest(
            product,
            output_dir,
            None,
            False,
            (_sheet_part(args, descriptors, part, options),),
        )
    if country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    return CollectionRequest(
        product, output_dir, None, False, _area_parts(args, descriptors, part, sink)
    )


def _is_pl_sheet(sheet: str) -> bool:
    try:
        SheetParser(sheet)
    except ValidationError:
        return False
    return True


def _sheet_part(
    args: dict,
    descriptors: dict[str, SourceDescriptor],
    part: Callable[..., CollectionPart],
    options: dict[str, str | None],
) -> CollectionPart:
    """The part of a sheet code (ADR-039 D4, ADR-043).

    A PL sheet code is an area: its extent (EPSG:2180) for objects, powiats
    and tiles, the sheets of a series intersecting it (its geographic extent:
    the series sheet itself, its sub-sheets' parent or the sheets inside a
    coarser sheet) for a channel of PL map sheets. A code that is not a PL
    sheet code is the sheet itself of a product whose CZ channel addresses
    a CUZK sheet index layer (``MAPNOM``, checked against the layer when the
    units are built).
    """
    from kartograf.core.parser_registry import detect_system

    sheet, country = args["sheet"].strip(), args["country"]
    cz = descriptors.get("CZ")
    if (
        cz is not None
        and country in (None, "auto", "cz")
        and not _is_pl_sheet(sheet)
        and _cuzk_sheet_channel(cz)
    ):
        if cz.key == "cz.cuzk.ztm":
            if re.fullmatch(r"[0-9]{4}-[A-Za-z0-9-]+", sheet):
                inferred = "sjtsk"
            elif re.fullmatch(r"[A-Za-z]{2}-[0-9]{2}-[A-Za-z0-9-]+", sheet):
                inferred = "etrs89"
            else:
                inferred = None
            selected = options["sheet_system"]
            if inferred is not None and selected is not None and selected != inferred:
                raise ValidationError(
                    f"--sheet {sheet} nalezy do ukladu {inferred}, a podano "
                    f"--sheet-system {selected}"
                )
            if inferred is not None:
                options["sheet_system"] = inferred
        base = part("CZ", "area")
        grid = base.variant.sheet_grid if base.variant is not None else None
        if grid is None or grid.system != "cuzk":
            raise ValidationError(
                f"--sheet {sheet}: {subject(cz)} (CZ) w wybranym wariancie nie ma "
                "arkuszy CUZK - podaj --bbox"
            )
        if not _MAPNOM.fullmatch(sheet):
            raise ValidationError(
                f"Nieprawidlowe godlo arkusza CUZK {sheet!r} (dozwolone litery, cyfry "
                "i '-')"
            )
        return replace(base, sheet=sheet, parent={"sheet": sheet, "countries": ["CZ"]})
    system = detect_system(sheet)
    if country not in (None, "auto") and country != system.country.lower():
        raise ValidationError(
            f"Godlo '{sheet}' nalezy do systemu {system.id} (kraj {system.country}), "
            f"a podano --country {country}"
        )
    if system.country != "PL":
        raise ValidationError(
            f"--sheet {sheet} ({system.id}): obszar kolekcji wyznacza godlo PL; "
            "dla CZ podaj --bbox (np. w EPSG:5514)"
        )
    parser = SheetParser(sheet)
    parent = {"sheet": parser.sheet, "countries": ["PL"]}
    base = part("PL", "area")
    grid = base.variant.sheet_grid if base.variant is not None else None
    if grid is not None and grid.system == "1992":
        area = parser.get_bbox(crs="EPSG:4326")
        return replace(base, area=area, sheet=parser.sheet, parent=parent)
    extent = parser.get_bbox(crs="EPSG:2180")
    return replace(base, area=_part_area(base, extent), parent=parent)


def _part_area(base: CollectionPart, area: BBox) -> BBox:
    params = base.channel.params
    if isinstance(params, FeatureBBoxParams):
        return _to_crs(area, params.native_crs)
    return area


def _area_parts(
    args: dict,
    descriptors: dict[str, SourceDescriptor],
    part: Callable[..., CollectionPart],
    sink: NoticeSink,
) -> tuple[CollectionPart, ...]:
    """Country parts of a bbox/geometry area (``auto``: clipped, narrowed)."""
    product, country = args["product"], args["country"]
    geometry = args["geometry"]
    if geometry is not None:
        path = Path(geometry)
        layer = resolve_geometry_layer(path, args["layer"], sink)
        area = geometry_envelope(path, layer)
    else:
        area = args["bbox"]
    auto = country == "auto"
    if auto:
        found = countries_for_bbox(area)
        if not found:
            raise ValidationError(
                "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)"
            )
        countries = tuple(code for code in found if code in descriptors)
        if not countries:
            raise ValidationError(
                f"--product {product} jest dostepny tylko dla "
                f"{', '.join(sorted(descriptors))}, a obszar lezy w {', '.join(found)}"
            )
        if countries != found:
            code = AUTO_NARROWED_TO_PL if countries == ("PL",) else AUTO_NARROWED_TO_CZ
            sink.emit(
                "info",
                code,
                f"--country auto -> {', '.join(c.lower() for c in countries)} "
                f"(--product {product} tylko dla {', '.join(sorted(descriptors))})",
            )
    else:
        countries = (country.upper(),)
    bases = {code: part(code, "area", countries) for code in countries}
    cz = bases.get("CZ")
    cz_params = cz.channel.params if cz is not None else None
    cz_crs = (
        cz_params.native_crs
        if isinstance(cz_params, FeatureBBoxParams)
        else "EPSG:5514"
    )
    pieces = {
        code: country_bbox(area, code, auto=auto, cz_crs=cz_crs) for code in countries
    }
    if auto:
        emit_clipping_notices(sink, area, countries, pieces)
    parent = parent_request_for(area, countries)
    parts = []
    for code in countries:
        base = bases[code]
        native = _part_area(base, pieces[code].bbox)
        derived = auto or geometry is not None or native != area
        packages = not isinstance(base.channel.params, FeatureBBoxParams)
        parts.append(
            replace(base, area=native, parent=parent if derived or packages else None)
        )
    return tuple(parts)


# =============================================================================
# Unit jobs (one file each)
# =============================================================================


@dataclass(frozen=True)
class UnitJob:
    """One file of a collection request: its slot, request and source.

    ``url`` + ``variant``: a package (``whole_country`` = a national file,
    its size announced before the transfer); ``record``: the index record
    of a sheet or tile (URL, version label with signal ``index``, the
    sidecar ``extra.source``); ``layers`` + ``bbox``: the objects of an
    area; ``atom`` = a file of an ATOM feed: the dataset ``atom_key`` (a
    voivodeship TERYT code; ``""`` = the only dataset, the national file) in
    the CRS ``atom_crs`` (its URL and edition come from the feed at run
    time). ``request`` is the sidecar ``request`` (the user's choice in
    this unit), ``parent`` its ``extra.parent_request``, ``extra`` more
    ``extra`` of the sidecar.
    """

    descriptor: SourceDescriptor
    channel: AccessChannel
    country: str
    unit: str
    slot: FileSlot
    request: dict
    parent: dict | None = None
    variant: PackageVariant | None = None
    url: str | None = None
    layers: tuple[FeatureLayer, ...] = ()
    bbox: BBox | None = None
    whole_country: bool = False
    atom: bool = False
    atom_crs: str | None = None
    atom_key: str = ""
    record: IndexRecord | None = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> _SLOT_KEY:
        return (self.slot.segment, self.slot.hierarchy, self.slot.name)

    @property
    def signal(self) -> SignalKind:
        """Freshness signal of the job's channel (ADR-042 D6)."""
        return self.channel.update_signal


def _related_roots(
    output_dir: Path,
    descriptor: SourceDescriptor,
    params: UnitPackageParams,
    variant: PackageVariant,
    ext: str,
    *,
    teryt: str | None,
    country: str | None,
) -> tuple[Path, ...]:
    """Version directories of the same unit in other editions (ADR-042 D7).

    Editions of one content: variants whose choice differs only in the
    values equal to the edition (``year``) - same format, same LoD. Only
    existing directories.
    """
    if variant.edition is None:
        return ()
    edition_keys = {key for key, value in variant.choice if value == variant.edition}
    if not edition_keys:
        return ()
    rest = {(k, v) for k, v in variant.choice if k not in edition_keys}
    roots = []
    for other in params.variants:
        if other.edition in (None, variant.edition):
            continue
        if {(k, v) for k, v in other.choice if k not in edition_keys} != rest:
            continue
        segment = content_segment(descriptor.key, other.segment_tokens)
        root = unit_slot(output_dir, segment, ext, teryt=teryt, country=country)
        if root.versions_root.is_dir():
            roots.append(root.versions_root)
    return tuple(roots)


def _country_unit(country: str, theme: str | None) -> str:
    """Unit of a national file: the country code, with the theme of a
    national product of several files (``pl-obiekty-fizjograficzne``)."""
    code = country.lower()
    return code if theme is None else f"{code}-{theme.lower().replace('_', '-')}"


def package_job(
    output_dir: Path,
    descriptor: SourceDescriptor,
    channel: AccessChannel,
    variant: PackageVariant,
    *,
    country: str,
    teryt: str | None,
    request: dict,
    parent: dict | None = None,
    theme: str | None = None,
) -> UnitJob:
    """The package of one unit (``teryt``) or the national file (``teryt=None``;
    ``theme``: one file of a national product of several themes)."""
    params = channel.params
    assert isinstance(params, UnitPackageParams)
    segment = content_segment(descriptor.key, variant.segment_tokens)
    ext = params.unpack or FILE_SUFFIX[variant.file_kind]
    code = None if teryt is not None else _country_unit(country, theme)
    related = _related_roots(
        output_dir, descriptor, params, variant, ext, teryt=teryt, country=code
    )
    slot = unit_slot(
        output_dir, segment, ext, teryt=teryt, country=code, related_roots=related
    )
    return UnitJob(
        descriptor=descriptor,
        channel=channel,
        country=country,
        unit=teryt if teryt is not None else str(code),
        slot=slot,
        request=request,
        parent=parent,
        variant=variant,
        url=package_url(variant, teryt=teryt, theme=theme),
        whole_country=teryt is None,
    )


def _feature_job(output_dir: Path, part: CollectionPart) -> UnitJob:
    assert part.area is not None
    slot = unit_slot(output_dir, part.segment, part.ext, bbox=part.area)
    return UnitJob(
        descriptor=part.descriptor,
        channel=part.channel,
        country=part.country,
        unit=bbox_cutout_path(".", "", part.area, "").name,
        slot=slot,
        request={
            "bbox": bbox_coords(part.area),
            "bbox_crs": part.area.crs,
            **part.choice,
        },
        parent=part.parent,
        layers=part.layers,
        bbox=part.area,
    )


def _atom_job(output_dir: Path, part: CollectionPart) -> UnitJob:
    """The national file of an ATOM channel (``whole_country``)."""
    code = part.country.lower()
    crs = part.choice.get("horizontal_crs")
    return UnitJob(
        descriptor=part.descriptor,
        channel=part.channel,
        country=part.country,
        unit=code,
        slot=unit_slot(output_dir, part.segment, part.ext, country=code),
        request={"whole_country": True, **part.choice},
        whole_country=True,
        atom=True,
        atom_crs=crs if isinstance(crs, str) else None,
    )


def _voivodeship_jobs(
    out: Path,
    part: CollectionPart,
    product: str,
    sink: NoticeSink,
    metadata: MetadataCache | None,
) -> list[UnitJob]:
    """The files of the voivodeships of an area from an ATOM feed keyed by
    ``woj`` (the first two digits of the powiats of the area, PRG)."""
    params = part.channel.params
    assert isinstance(params, AtomFilesParams) and part.area is not None
    if "woj" not in re.compile(params.entry_pattern).groupindex:
        raise ValueError(f"{part.descriptor.key}: obszar kanalu ATOM wymaga grupy woj")
    teryts = discover_teryts_for_bbox(
        part.area, session=_session(), cache=metadata, timeout=PROBE_TIMEOUT
    )
    codes = sorted({teryt[:2] for teryt in teryts})
    if not codes:
        raise NoCoverageError(
            f"{product}: obszar nie przecina zadnego wojewodztwa (PRG)"
        )
    named = ", ".join(f"{code} ({WOJEWODZTWO_NAMES.get(code, '?')})" for code in codes)
    sink.emit(
        "info",
        UNIT_LIST,
        f"{product}: wojewodztwa obszaru wg PRG ({len(codes)}): {named}",
    )
    return [
        UnitJob(
            descriptor=part.descriptor,
            channel=part.channel,
            country=part.country,
            unit=code,
            slot=unit_slot(out, part.segment, part.ext, teryt=code),
            request={"teryt": code, **part.choice},
            parent=part.parent,
            atom=True,
            atom_key=code,
            extra=part.extra,
        )
        for code in codes
    ]


def atom_area_request(
    descriptor_key: str,
    *,
    product: str,
    output_dir: Path,
    area: BBox,
    parent: dict | None,
    choice: dict,
    extra: dict,
) -> CollectionRequest:
    """The request of the voivodeship files of an area from the ATOM channel
    of ``descriptor_key`` (``download_data``: NMT 100 m, plan E1; no network).

    ``area`` in any supported CRS, ``parent`` = ``extra.parent_request`` of
    the files, ``choice`` = the content values of their sidecar ``request``,
    ``extra`` = more ``extra`` of their sidecars. The files land in
    ``<storage_subdir>/teryt/<woj><ext>`` (track ``collection``).
    """
    descriptor = get_source(descriptor_key)
    channel = next(
        c for c in descriptor.channels if isinstance(c.params, AtomFilesParams)
    )
    assert isinstance(channel.params, AtomFilesParams)
    part = CollectionPart(
        country=descriptor.country,
        descriptor=descriptor,
        channel=channel,
        variant=None,
        layers=(),
        segment=content_segment(
            descriptor_key, atom_segment_tokens(channel.params, None)
        ),
        ext=".zip",
        choice=dict(choice),
        area=area,
        parent=parent,
        extra=dict(extra),
    )
    return CollectionRequest(product, Path(output_dir), None, False, (part,))


def _record_job(
    part: CollectionPart,
    *,
    unit: str,
    slot: FileSlot,
    tokens: dict[str, str],
    request: dict,
    record: IndexRecord | None = None,
) -> UnitJob:
    """The file of one sheet, tile or cadastral area: the URL from the
    template (``tokens``) or from the unit's index record."""
    variant = part.variant
    assert variant is not None
    if variant.url_template is not None:
        url = package_url(variant, **tokens)
    elif record is not None:
        url = index_url(variant, record.urls, unit=unit)
    else:
        raise ValueError(
            f"{part.descriptor.key}: wariant bez szablonu URL wymaga indeksu rekordow"
        )
    return UnitJob(
        descriptor=part.descriptor,
        channel=part.channel,
        country=part.country,
        unit=unit,
        slot=slot,
        request=request,
        parent=part.parent,
        variant=variant,
        url=url,
        record=record,
    )


def _newest(records: Iterable[IndexRecord]) -> IndexRecord | None:
    """The newest record of a unit (year, then the label: date first)."""
    return max(records, key=lambda r: (r.year or 0, r.label), default=None)


def _series_sheets(grid: SheetGrid, area: BBox) -> list[str]:
    """PL-1992 sheets of a series (``grid.parts`` members) intersecting
    ``area`` with a positive area (``find_sheets_for_bbox``; the series is
    mapped by its number of members, never by a scale label, plan E)."""
    label = series_scale(grid.parts or 0)
    if area.crs.strip().upper() not in _PL_GRID_CRS:
        area = _to_crs(area, "EPSG:4326")
    return find_sheets_for_bbox(area, label, "1992")


def _cuzk_sheets(
    part: CollectionPart, grid: SheetGrid, metadata: MetadataCache | None
) -> list[str]:
    """``MAPNOM`` of the CUZK sheet index layer of the part: the requested
    sheet (checked in the layer) or the sheets of its area."""
    from kartograf.providers.cuzk.sheets import SheetIndex

    if grid.layer is None or grid.crs is None:
        raise ValueError("Siatka arkuszy CUZK wymaga warstwy i ukladu (layer, crs)")
    index = SheetIndex(session=_session(), cache=metadata)
    if part.sheet is not None:
        return [index.sheet(grid.layer, part.sheet, crs=grid.crs).sheet]
    assert part.area is not None
    area = _to_crs(part.area, grid.crs)
    return [info.sheet for info in index.sheets_for_bbox(grid.layer, area)]


def _sheet_record(
    params: UnitPackageParams, variant: PackageVariant, sheet: str, year: int | None
) -> IndexRecord | None:
    """The newest index record of a PL sheet (GetFeatureInfo at its centre or
    the WFS records of its extent); ``None``: the index has none."""
    index = params.index
    assert index is not None
    if variant.index_layer is None:
        raise ValueError("Wariant z indeksem rekordow wymaga index_layer")
    if index.kind == "wms_gfi":
        found = gfi_records(
            _session(), index, variant.index_layer, sheet, timeout=SERVICE_TIMEOUT
        )
    else:
        extent = SheetParser(sheet).get_bbox(crs="EPSG:2180")
        found = wfs_records(
            _session, index, variant.index_layer, extent, timeout=SERVICE_TIMEOUT
        )
    return _newest(
        r for r in found if r.unit == sheet and (year is None or r.year == year)
    )


def _sheet_jobs(
    out: Path,
    part: CollectionPart,
    product: str,
    sink: NoticeSink,
    metadata: MetadataCache | None,
) -> list[UnitJob]:
    """The files of the map sheets of an area or of a sheet (ADR-043)."""
    params, variant = part.channel.params, part.variant
    assert isinstance(params, UnitPackageParams) and variant is not None
    grid = variant.sheet_grid
    if grid is None:
        raise ValueError(f"{part.descriptor.key}: wariant arkuszowy bez SheetGrid")
    cuzk = grid.system == "cuzk"
    if cuzk:
        sheets = _cuzk_sheets(part, grid, metadata)
    else:
        assert part.area is not None
        sheets = _series_sheets(grid, part.area)
    if not sheets:
        raise NoCoverageError(f"{product}: obszar nie przecina zadnego arkusza")
    records: dict[str, IndexRecord] = {}
    if params.index is not None:
        for sheet in sheets:
            record = _sheet_record(params, variant, sheet, part.year_filter)
            if record is not None:
                records[sheet] = record
        missing = [sheet for sheet in sheets if sheet not in records]
        sheets = [sheet for sheet in sheets if sheet in records]
    else:
        missing = []
    text = f"{product}: arkusze ({len(sheets)}): {', '.join(sheets) or '-'}"
    if missing:
        text += f"; bez rekordu w indeksie ({len(missing)}): {', '.join(missing)}"
    sink.emit("info", UNIT_LIST, text)
    if not sheets:
        year = f" z roku {part.year_filter}" if part.year_filter is not None else ""
        raise NoCoverageError(
            f"{product}: indeks nie ma rekordow{year} dla arkuszy obszaru "
            f"({', '.join(missing)})"
        )
    return [
        _record_job(
            part,
            unit=sheet,
            slot=unit_slot(
                out,
                part.segment,
                part.ext,
                mapnom=sheet if cuzk else None,
                sheet=None if cuzk else sheet,
            ),
            tokens={"sheet": sheet},
            request={"sheet": sheet, **part.choice},
            record=records.get(sheet),
        )
        for sheet in sheets
    ]


def _tile_jobs(
    out: Path, part: CollectionPart, product: str, sink: NoticeSink
) -> list[UnitJob]:
    """The files of the index tiles of an area: the newest record of each tile,
    or the record of the requested year (ADR-028, ADR-043)."""
    params, variant = part.channel.params, part.variant
    assert isinstance(params, UnitPackageParams) and variant is not None
    index = params.index
    if index is None or index.kind != "wfs" or variant.index_layer is None:
        raise ValueError(f"{part.descriptor.key}: kafle wymagaja indeksu WFS")
    assert part.area is not None
    area = _to_crs(part.area, "EPSG:2180")
    found = wfs_records(
        _session, index, variant.index_layer, area, timeout=SERVICE_TIMEOUT
    )
    if not found:
        raise NoCoverageError(
            f"{product}: brak kafli w obszarze (indeks {index.endpoint})"
        )
    by_tile: dict[tuple[str | None, str], list[IndexRecord]] = {}
    for record in found:
        by_tile.setdefault((record.zone, record.unit), []).append(record)
    year = part.year_filter
    chosen: dict[tuple[str | None, str], IndexRecord] = {}
    for key, records in sorted(
        by_tile.items(), key=lambda item: (item[0][0] or "", item[0][1])
    ):
        newest = _newest(r for r in records if year is None or r.year == year)
        if newest is not None:
            chosen[key] = newest
    if not chosen:
        years = sorted({r.year for r in found if r.year is not None})
        raise NoCoverageError(
            f"{product}: brak kafli z roku {year} w obszarze (lata w indeksie: "
            f"{', '.join(map(str, years)) or '-'})"
        )
    names = {key: f"{key[0]}/{key[1]}" if key[0] else key[1] for key in chosen}
    sink.emit(
        "info",
        UNIT_LIST,
        f"{product}: kafle obszaru ({len(chosen)}): {', '.join(names.values())}",
    )
    return [
        _record_job(
            part,
            unit=names[key],
            slot=unit_slot(out, part.segment, part.ext, tile=key[1], zone=key[0]),
            tokens={},
            request={"tile": names[key], **part.choice},
            record=record,
        )
        for key, record in chosen.items()
    ]


def _ku_jobs(
    out: Path, part: CollectionPart, request: CollectionRequest, sink: NoticeSink
) -> list[UnitJob]:
    """The packages of a CZ cadastral area or of the areas of an area (RUIAN)."""
    params = part.channel.params
    assert isinstance(params, UnitPackageParams)
    if request.ku is not None:
        codes = [request.ku]
    else:
        from kartograf.providers.cuzk.client import CuzkClient
        from kartograf.providers.cuzk.ruian import cadastral_areas_for_bbox

        if params.ku_layer is None:
            raise ValueError(f"{part.descriptor.key}: jednostki ku wymagaja ku_layer")
        assert part.area is not None
        client = CuzkClient(session=_session(), timeout=SERVICE_TIMEOUT)
        areas = cadastral_areas_for_bbox(
            client, params.ku_layer, _to_crs(part.area, "EPSG:5514")
        )
        if not areas:
            raise NoCoverageError(
                f"{request.product}: obszar nie przecina zadnego katastralniho "
                "uzemi (RUIAN)"
            )
        codes = [area.code for area in areas]
        sink.emit(
            "info",
            UNIT_LIST,
            f"{request.product}: katastralni uzemi obszaru wg RUIAN ({len(codes)}): "
            f"{', '.join(codes)}",
        )
    return [
        _record_job(
            part,
            unit=code,
            slot=unit_slot(out, part.segment, part.ext, ku=code),
            tokens={"ku": code},
            request={"ku": code, **part.choice},
        )
        for code in codes
    ]


def _jobs(
    request: CollectionRequest, sink: NoticeSink, metadata: MetadataCache | None
) -> list[UnitJob]:
    """Unit jobs of a request; the units of an area come from PRG (powiats,
    voivodeships of an ATOM feed), the sheet grid or index, the tile index
    or RUIAN."""
    out = request.output_dir
    jobs: list[UnitJob] = []
    for part in request.parts:
        if part.layers:
            jobs.append(_feature_job(out, part))
            continue
        params = part.channel.params
        if isinstance(params, AtomFilesParams):
            if request.whole_country:
                jobs.append(_atom_job(out, part))
            else:
                jobs.extend(
                    _voivodeship_jobs(out, part, request.product, sink, metadata)
                )
            continue
        assert isinstance(params, UnitPackageParams) and part.variant is not None
        if params.unit == "sheet":
            jobs.extend(_sheet_jobs(out, part, request.product, sink, metadata))
            continue
        if params.unit == "tile":
            jobs.extend(_tile_jobs(out, part, request.product, sink))
            continue
        if params.unit == "ku":
            jobs.extend(_ku_jobs(out, part, request, sink))
            continue
        if request.teryt is not None or request.whole_country:
            selection = (
                {"teryt": request.teryt}
                if request.teryt is not None
                else {"whole_country": True}
            )
            for theme in params.themes or (None,):
                jobs.append(
                    package_job(
                        out,
                        part.descriptor,
                        part.channel,
                        part.variant,
                        country=part.country,
                        teryt=request.teryt,
                        request={**selection, **part.choice},
                        theme=theme,
                    )
                )
            continue
        assert part.area is not None
        teryts = discover_teryts_for_bbox(
            part.area, session=_session(), cache=metadata, timeout=PROBE_TIMEOUT
        )
        if not teryts:
            raise NoCoverageError(
                f"{request.product}: obszar nie przecina zadnego powiatu (PRG)"
            )
        sink.emit(
            "info",
            UNIT_LIST,
            f"{request.product}: powiaty obszaru wg PRG ({len(teryts)}): "
            f"{', '.join(teryts)}",
        )
        for teryt in teryts:
            jobs.append(
                package_job(
                    out,
                    part.descriptor,
                    part.channel,
                    part.variant,
                    country=part.country,
                    teryt=teryt,
                    request={"teryt": teryt, **part.choice},
                    parent=part.parent,
                )
            )
    return jobs


def _capability(descriptor: SourceDescriptor, channel: AccessChannel) -> str:
    """The capability that names ``channel`` in the sidecar: one no other
    channel of the descriptor has, else its first one (several channels of
    one kind - one WFS service per network - share it and declare the same
    CRSs, which the sidecar reads from the first of them)."""
    others = [c for c in descriptor.channels if c is not channel]
    own = sorted(channel.capabilities)
    unique = [cap for cap in own if all(cap not in o.capabilities for o in others)]
    return (unique or own)[0]


def _http(session: requests.Session | None) -> requests.Session:
    """The caller's session, else the current thread's session of this module."""
    return session if session is not None else _session()


def _probe(job: UnitJob, session: requests.Session | None):
    """``HEAD`` of the file for a channel with the ``http`` signal."""
    if job.signal != "http" or job.url is None:
        return None
    url = job.url
    return lambda: head_signal(_http(session), url, timeout=PROBE_TIMEOUT)


def _atom_file(
    job: UnitJob,
    session: requests.Session | None,
    cache: MetadataCache | None,
    refresh: bool,
) -> Callable[[], AtomFile]:
    """The file of an ATOM job from its feeds, asked at most once (the
    edition and the URL of one run come from the same answer)."""
    params = job.channel.params
    assert isinstance(params, AtomFilesParams)
    return functools.cache(
        lambda: resolve_atom_file(
            _http(session),
            params,
            key=job.atom_key,
            crs=job.atom_crs,
            cache=cache,
            refresh=refresh,
        )
    )


def _atom_edition(file: Callable[[], AtomFile]) -> Callable[[], Edition]:
    def edition() -> Edition:
        found = file()
        return Edition(id=found.edition, url=found.dataset_feed)

    return edition


def _record_edition(job: UnitJob) -> Callable[[], Edition] | None:
    """The label of the job's index record as the edition of signal ``index``
    (ADR-043; ``None``: no record or another signal)."""
    record, params = job.record, job.channel.params
    if job.signal != "index" or record is None:
        return None
    assert isinstance(params, UnitPackageParams) and params.index is not None
    url = params.index.endpoint
    return lambda: Edition(id=record.label, url=url)


def inspect_job(
    job: UnitJob,
    *,
    track: Track = _TRACK,
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
) -> PlanItem:
    """Plan position of a unit job WITHOUT downloading its data.

    ``track``: the plan track of the calling command (``landcover`` for the
    BDOT10k archive and ZABAGED); ``session``: HTTP session of a ``HEAD`` or
    of the ATOM feeds (``None``: one per thread of this module); ``cache``:
    the metadata cache of the ATOM feed index (revalidated: a check must see
    a new edition). A file of an index record is compared by the record's
    label (signal ``index``), never downloaded.
    """
    edition: Callable[[], Edition] | None
    if job.atom:
        edition = _atom_edition(_atom_file(job, session, cache, refresh=True))
    else:
        edition = _record_edition(job)
    available: tuple[str | None, dict | None] = (None, None)
    if job.record is not None and edition is not None:
        available = (job.record.label, {"url": job.url, **job.record.raw})
    return inspect_version(
        job.slot,
        track=track,
        unit=job.unit,
        signal=job.signal,
        probe=_probe(job, session),
        edition=edition,
        available=available,
    )


def _local_only(slot: FileSlot) -> VersionedFile | None:
    """A position left out of the plan: its local version, never a download."""
    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)


@dataclass
class _Source:
    """``extra.source`` of the file being downloaded (set by the fetch)."""

    value: dict = field(default_factory=dict)


def _announce_size(job: UnitJob, sink: NoticeSink, session: requests.Session) -> None:
    """The size of a package from ``HEAD`` before its transfer: always for a
    national file (``WHOLE_COUNTRY_SIZE``, K7), above ``LARGE_FILE_BYTES``
    for a unit file (``DOWNLOAD_SIZE``, K9; the GUGiK opendata server ignores
    ``Range``: the file comes whole)."""
    assert job.url is not None
    try:
        length = head_signal(session, job.url, timeout=PROBE_TIMEOUT)["content_length"]
    except DownloadError as e:
        logger.debug("HEAD %s: %s", job.url, e)
        length = None
    what = subject(job.descriptor)
    if job.whole_country:
        sink.emit(
            "warning",
            WHOLE_COUNTRY_SIZE,
            f"{what} {job.country}: plik krajowy {job.url} - {size_text(length)}",
        )
    elif length is not None and length > LARGE_FILE_BYTES:
        sink.emit(
            "warning",
            DOWNLOAD_SIZE,
            f"{what} {job.country} {job.unit}: duzy plik {job.url} - "
            f"{size_text(length)}",
        )


def _fetch_package(
    job: UnitJob,
    staged: Path,
    source: _Source,
    sink: NoticeSink,
    session: requests.Session,
    timeout: int,
) -> dict:
    assert job.url is not None and job.variant is not None
    params = job.channel.params
    assert isinstance(params, UnitPackageParams)
    _announce_size(job, sink, session)
    package = fetch_package(
        session,
        job.url,
        staged,
        params=params,
        variant=job.variant,
        timeout=timeout,
    )
    value: dict = {"url": job.url}
    if job.variant.edition is not None:
        value["edition"] = job.variant.edition
    if package.member is not None:
        value["member"] = package.member
    if job.record is not None:
        assert params.index is not None
        value["index"] = params.index.endpoint
        if job.variant.index_layer is not None:
            value["layer"] = job.variant.index_layer
        value["record"] = dict(job.record.raw)
    source.value = value
    return package.http


def _fetch_atom(
    job: UnitJob,
    staged: Path,
    source: _Source,
    sink: NoticeSink,
    file: AtomFile,
    session: requests.Session,
    timeout: int,
) -> dict:
    """A file of an ATOM feed, the ZIP 1:1: the size from the feed before
    the transfer - always for the national file (``WHOLE_COUNTRY_SIZE``,
    K7), above ``LARGE_FILE_BYTES`` for a voivodeship file
    (``DOWNLOAD_SIZE``, K9)."""
    what = subject(job.descriptor)
    if job.whole_country:
        sink.emit(
            "warning",
            WHOLE_COUNTRY_SIZE,
            f"{what} {job.country}: plik krajowy {file.url} - {size_text(file.length)}",
        )
    elif file.length is not None and file.length > LARGE_FILE_BYTES:
        sink.emit(
            "warning",
            DOWNLOAD_SIZE,
            f"{what} {job.country} {job.unit}: duzy plik {file.url} - "
            f"{size_text(file.length)}",
        )
    http = fetch_atom_file(session, file, staged, timeout=timeout)
    params = job.channel.params
    assert isinstance(params, AtomFilesParams)
    value: dict = {
        "url": file.url,
        "service_feed": params.service_feed,
        "dataset_feed": file.dataset_feed,
    }
    if job.atom_key:
        value["dataset"] = job.atom_key
    value.update(edition=file.edition, updated=file.updated, length=file.length)
    source.value = value
    return http


def _fetch_features(
    job: UnitJob,
    staged: Path,
    source: _Source,
    session: requests.Session,
    timeout: int,
) -> None:
    # lazy: GDAL vector (pyogrio) only for area results
    from kartograf.transform.gpkg import write_gpkg
    from kartograf.transport.feature_bbox import fetch_features

    params = job.channel.params
    assert isinstance(params, FeatureBBoxParams) and job.bbox is not None
    work = Path(tempfile.mkdtemp(prefix="kartograf-features-"))
    try:
        pages = fetch_features(
            session,
            job.channel.endpoint,
            params,
            job.layers,
            job.bbox,
            work,
            timeout=timeout,
        )
        result = work / "result.gpkg"
        summary = write_gpkg(result, pages, params=params)
        shutil.move(str(result), staged)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    value: dict = {
        "service": job.channel.endpoint,
        "protocol": params.protocol,
        "layers": [
            {
                "code": layer.code,
                "source": layer.source,
                "name": layer.name,
                "features": summary.features.get(layer.name, 0),
            }
            for layer in job.layers
        ],
    }
    if summary.dropped:
        value["dropped_fields"] = {
            name: list(values) for name, values in sorted(summary.dropped.items())
        }
    source.value = value


def run_job(
    job: UnitJob,
    update: UpdateMode | None,
    *,
    sink: NoticeSink,
    planned: set[_SLOT_KEY] | None = None,
    session: requests.Session | None = None,
    timeout: int | None = None,
    on_download: Callable[[], None] | None = None,
    cache: MetadataCache | None = None,
) -> VersionedFile | None:
    """Local version or download of one unit job (spec 4.2, ADR-042 D6).

    Out of the plan (``planned`` given, the job not in it): the local
    version or ``None``. Otherwise ``fetch_version``: a package labelled by
    its edition (``label_source="edition"``), by the label of its index
    record (signal ``index``, ADR-043) or the download date, a file of an
    ATOM feed by the edition of the feed (signal ``metadata``), an area
    result by the download date; the sidecar names the channel by its
    capability and carries ``extra.source``
    (``url``/``edition``/``member``/``index``/``layer``/``record``,
    ``url``/``service_feed``/``dataset_feed``/``dataset``/``edition``/
    ``updated``/``length`` or ``service``/``layers``/``dropped_fields``),
    ``extra.http`` of a file, ``extra.parent_request`` and the job's
    ``extra``; a tile record declaring its CRS (``uklad_xy``)
    names it as the CRS of the file. ``session``: HTTP session of the
    requests (``LandCoverManager``: its provider's; ``None``: one per thread
    of this module); ``timeout``: seconds of one request (``None``:
    ``PACKAGE_TIMEOUT`` for a file, the channel's ``timeout`` or
    ``SERVICE_TIMEOUT`` for a page); ``on_download`` is called right before
    the transfer starts (never for a local version); ``cache``: the metadata
    cache of the ATOM feed index (revalidated with ``update="upgrade"``).

    Raises
    ------
    NoCoverageError
        No data of the unit at the source.
    DownloadError
        Download, response, edition, version or link failure.
    """
    if planned is not None and job.key not in planned:
        return _local_only(job.slot)
    source = _Source()
    atom = _atom_file(job, session, cache, update == "upgrade") if job.atom else None

    def fetch(staged: Path) -> dict | None:
        if on_download is not None:
            on_download()
        if job.layers:
            params = job.channel.params
            assert isinstance(params, FeatureBBoxParams)
            pages = timeout or params.timeout or SERVICE_TIMEOUT
            _fetch_features(job, staged, source, _http(session), pages)
            return None
        if atom is not None:
            return _fetch_atom(
                job,
                staged,
                source,
                sink,
                atom(),
                _http(session),
                timeout or PACKAGE_TIMEOUT,
            )
        return _fetch_package(
            job, staged, source, sink, _http(session), timeout or PACKAGE_TIMEOUT
        )

    def write(
        data: Path, ref: VersionRef, digest: ContentDigest, http: dict | None
    ) -> None:
        extra: dict = {"source": source.value, **job.extra}
        if http:
            extra["http"] = http
        if job.parent:
            extra["parent_request"] = job.parent
        params = job.channel.params
        if isinstance(params, FeatureBBoxParams):
            crs = params.native_crs
        else:
            grid = job.variant.sheet_grid if job.variant is not None else None
            crs = (
                job.atom_crs
                or _record_crs(job)
                or (grid.crs if grid is not None else None)
                or job.channel.horizontal_crs
            )
        emit_sidecar(
            job.descriptor.key,
            data,
            request=job.request,
            horizontal_crs=crs,
            vertical_crs=job.variant.vertical_crs if job.variant is not None else None,
            capability=_capability(job.descriptor, job.channel),
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=ref.to_extra(),
            exclusive=True,
        )

    if atom is not None:
        return fetch_version(
            job.slot,
            update,
            signal=job.signal,
            fetch=fetch,
            write_sidecar=write,
            edition=_atom_edition(atom),
        )
    record_edition = _record_edition(job)
    if record_edition is not None:
        return fetch_version(
            job.slot,
            update,
            signal=job.signal,
            fetch=fetch,
            write_sidecar=write,
            edition=record_edition,
        )
    edition = job.variant.edition if job.variant is not None else None
    version = VersionRef(edition, "edition") if edition else VersionRef.downloaded()
    return fetch_version(
        job.slot,
        update,
        signal=job.signal,
        fetch=fetch,
        write_sidecar=write,
        version=version,
        probe=_probe(job, session),
    )


def _record_crs(job: UnitJob) -> str | None:
    """CRS of the file declared by its index record (``zone_field``: GUGiK
    ``PL-2000:S7`` -> ``EPSG:2178``); ``None``: not declared."""
    params = job.channel.params
    if job.record is None or not isinstance(params, UnitPackageParams):
        return None
    index = params.index
    if index is None or index.zone_field is None:
        return None
    return horizontal_crs_for_system(job.record.raw.get(index.zone_field))


# =============================================================================
# Commands
# =============================================================================


def _choices(values: dict) -> dict:
    return {name: values[name] for name in _CHOICE_NAMES}


_CHOICE_NAMES = (
    "product",
    "output_dir",
    "country",
    "teryt",
    "ku",
    "sheet",
    "bbox",
    "geometry",
    "layer",
    "whole_country",
    "level",
    "lod",
    "year",
    "format",
    "scale",
    "sheet_system",
    "network",
    "horizontal_crs",
)


def download_collection(
    *,
    product: str | None,
    output_dir: str | Path | None,
    country: str | None = None,
    teryt: str | None = None,
    ku: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    format: str | None = None,
    scale: str | None = None,
    sheet_system: str | None = None,
    network: str | None = None,
    horizontal_crs: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 1,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> CollectionReport:
    """Download a collection product (``download`` of the collection groups)
    into the version store of ``output_dir``.

    Choices as in ``validate_collection_request`` (called first, no network):
    ``product`` (``admin`` PRG and RUIAN, ``map`` EGiB, ``buildings`` 3D
    models, ``network`` HY-NET, the products of plan E), one selection
    (``teryt``, ``ku``, ``sheet``, ``bbox``, ``geometry`` or
    ``whole_country``), ``country`` (``pl``/``cz``/``auto``), ``level``
    (``admin`` of an area: PL ``wojewodztwo``, ``powiat``, ``gmina``,
    ``jednostka-ewidencyjna``, ``obreb``; CZ ``kraj``, ``okres``, ``obec``,
    ``katastralni-uzemi``; per country with ``auto``: ``{"pl": "gmina",
    "cz": "obec"}``), ``lod`` and ``year`` (``buildings``: LoD1 2019, 2021,
    2022, 2024; LoD2 2017; the year of the index records of a tile product,
    whose newest record is taken without it), ``format``, ``scale``,
    ``sheet_system``, ``network`` (values of the descriptor of the product:
    a channel or a published variant), ``horizontal_crs`` (a national file
    published in several CRSs). Files:
    ``<grupa>/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>[-<temat>]|ku/<kod>|<arkusz>|<strefa>/<kafel>}``
    with versions in ``versions/`` (ADR-042 D8, ADR-043). ``update``/``plan``
    as in every store command (``plan`` from ``check_collection`` with
    ``update="upgrade"``); ``workers`` = units downloaded in parallel;
    ``cache`` = metadata cache of the PRG powiat query, of the CUZK sheet
    index and of the ATOM feed index (``True``: default file in the current
    directory, ``False``: none); ``on_notice`` receives each notice when
    emitted (``UNIT_LIST``, ``WHOLE_COUNTRY_SIZE`` before a national
    transfer, ``DOWNLOAD_SIZE`` before a unit file over 100 MiB, clipping
    notices of ``auto``).

    Raises
    ------
    ValidationError
        Invalid or missing choice (before any request), a plan of another
        store or without ``update="upgrade"``; a CUZK sheet code missing
        from its sheet index layer (after the index query).
    NoCoverageError
        An area without any unit (powiat, sheet with an index record, tile,
        cadastral area).
    DownloadError
        The query of the units failed (PRG, sheet index, tile index, RUIAN;
        unit failures land in ``failed``).
    """
    sink = NoticeSink(on_notice)
    validate_update(update)
    request = _resolve(_choices(locals()), sink)
    files, failed, stale = run_request(
        request,
        update=update,
        plan=plan,
        workers=workers,
        cache=cache,
        sink=sink,
    )
    return CollectionReport(
        files=files,
        failed=failed,
        stale=stale,
        notices=sink.notices,
        ok=not failed and not stale,
    )


def landcover_request(
    descriptor_key: str,
    *,
    output_dir: str | Path | None,
    sheet: str | None,
    bbox: BBox | None,
    geometry: str | Path | None,
    layer: str | None,
    whole_country: bool,
    horizontal_crs: str | None,
    sink: NoticeSink,
) -> CollectionRequest:
    """The request of a land cover source on the collection engines
    (``LandCoverManager``: ZABAGED, ADR-042 D10/D15): its one country, an
    area or ``whole_country``; the same rules as ``validate_collection_request``
    (no network)."""
    descriptor = get_source(descriptor_key)
    args = {
        "product": descriptor.product,
        "output_dir": output_dir,
        "country": descriptor.country.lower(),
        "teryt": None,
        "ku": None,
        "sheet": sheet,
        "bbox": bbox,
        "geometry": geometry,
        "layer": layer,
        "whole_country": whole_country,
        "level": None,
        "lod": None,
        "year": None,
        "format": None,
        "scale": None,
        "sheet_system": None,
        "network": None,
        "horizontal_crs": horizontal_crs,
    }
    return _resolve(args, sink, {descriptor.country: descriptor})


def run_request(
    request: CollectionRequest,
    *,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    workers: int,
    cache: MetadataCache | bool,
    sink: NoticeSink,
    track: Track = _TRACK,
    timeout: int | None = None,
) -> tuple[tuple[UnitFile, ...], tuple[UnitFailure, ...], tuple[PlanItem, ...]]:
    """Files, unit failures and stale plan positions of a validated request
    (``download_collection``; ``LandCoverManager`` on the track ``landcover``).

    Raises
    ------
    ValidationError
        A plan of another store or without ``update="upgrade"``, bad workers.
    NoCoverageError
        An area of a package product without any powiat (PRG).
    DownloadError
        The PRG powiat query failed (unit failures land in the result).
    """
    validate_update(update)
    if plan is not None:
        if update != "upgrade":
            raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
        require_store(plan, store_id(request.output_dir))
    require_int(workers, "--workers")
    if workers < 1:
        raise ValidationError(f"workers musi byc >= 1, podano {workers}")
    with open_cache(cache, force=update == "force", on_notice=sink.add) as metadata:
        jobs = _jobs(request, sink, metadata)
        planned: set[_SLOT_KEY] | None = None
        stale: tuple[PlanItem, ...] = ()
        if plan is not None:
            current = [inspect_job(j, track=track, cache=metadata) for j in jobs]
            todo, stale_items = select_planned(plan, current, track)
            planned = {(i.segment, i.hierarchy, i.name) for i in todo}
            stale = tuple(stale_items)

        def one(job: UnitJob) -> VersionedFile | UnitFailure | None:
            try:
                return run_job(
                    job,
                    update,
                    sink=sink,
                    planned=planned,
                    timeout=timeout,
                    cache=metadata,
                )
            except NoCoverageError as e:
                return UnitFailure(job.unit, job.country, str(e), "no_coverage")
            except DownloadError as e:
                logger.debug("%s %s: %s", request.product, job.unit, e)
                return UnitFailure(job.unit, job.country, str(e), "download")

        if workers > 1 and len(jobs) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                outcomes = list(pool.map(one, jobs))
        else:
            outcomes = [one(job) for job in jobs]
    files: list[UnitFile] = []
    failed: list[UnitFailure] = []
    for job, outcome in zip(jobs, outcomes, strict=True):
        if isinstance(outcome, UnitFailure):
            failed.append(outcome)
        elif outcome is not None:
            files.append(UnitFile(job.unit, job.country, outcome))
            unit = outcome.path.relative_to(request.output_dir).as_posix()
            emit_file_notices(sink, unit, outcome, update)
    return tuple(files), tuple(failed), stale


def plan_request(
    request: CollectionRequest,
    *,
    cache: MetadataCache | bool,
    sink: NoticeSink,
    track: Track = _TRACK,
) -> UpdatePlan:
    """Update plan of a validated request (no data downloaded)."""
    with open_cache(cache, force=False, on_notice=sink.add) as metadata:
        jobs = _jobs(request, sink, metadata)
        items = [inspect_job(job, track=track, cache=metadata) for job in jobs]
    return new_plan(request.output_dir, items)


def check_collection(
    *,
    product: str | None,
    output_dir: str | Path | None,
    country: str | None = None,
    teryt: str | None = None,
    ku: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    format: str | None = None,
    scale: str | None = None,
    sheet_system: str | None = None,
    network: str | None = None,
    horizontal_crs: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_collection`` with the same choice; no data
    is downloaded (``kartograf-plan/1``, track ``collection``).

    Packages and area results of GUGiK have no cheap freshness signal: a
    local version is ``unverifiable``, a missing one ``missing``; files
    with ``ETag`` (``http``) are compared by ``HEAD``, files of an ATOM feed
    by the edition of the feed, files of an index record (signal ``index``)
    by the record's label. The units of an area are asked as for a download
    (PRG powiats, sheet grid or index, tile index, RUIAN).
    """
    sink = NoticeSink(on_notice)
    request = _resolve(_choices(locals()), sink)
    return plan_request(request, cache=cache, sink=sink)
