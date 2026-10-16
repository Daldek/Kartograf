"""
Collections on the versioned store (ADR-042 D2, D6-D10, D12).

One orchestrator for every channel with typed engine parameters
(``AccessChannel.params``): ``download_collection``/``check_collection`` are
the ``download`` commands of the ``boundaries``, ``cadastre``, ``models3d``
and ``hydro`` groups. ``validate_collection_request``
checks the whole choice WITHOUT network (exactly one selection, product,
country, unit, variant, level, CRS) and is the only place of these rules.
The kind of selection picks the channel: ``teryt`` -> the package of that
unit (``unit_package``); an area (``bbox``/``sheet``/``geometry``) -> one
GeoPackage of the area in the native CRS of the service (``feature_bbox``),
or - for a product without an area channel - the package of every powiat
of the area (PRG, ``UNIT_LIST``); ``whole_country`` -> the national file
(``unit_package`` of the country or a file of a CUZK ATOM feed,
``atom_files``: edition = signal ``metadata``) after a
``WHOLE_COUNTRY_SIZE`` notice (K7). Every file goes through
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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords, is_czech_crs, transform_bbox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.area import (
    bbox_to_2180,
    emit_clipping_notices,
    geometry_envelope,
    parent_request_for,
    resolve_geometry_layer,
)
from kartograf.download.arguments import require_bool, require_int
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
    UNIT_LIST,
    WHOLE_COUNTRY_SIZE,
    Notice,
    NoticeSink,
)
from kartograf.providers.pl.bdot10k import WOJEWODZTWO_NAMES
from kartograf.providers.pl.prg import discover_teryts_for_bbox
from kartograf.sources.descriptor import (
    AccessChannel,
    AtomFilesParams,
    FeatureBBoxParams,
    FeatureLayer,
    PackageVariant,
    SignalKind,
    SourceDescriptor,
    UnitPackageParams,
)
from kartograf.sources.edition import Edition
from kartograf.sources.registry import get_source, sources_for
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.atom import (
    AtomFile,
    atom_segment_tokens,
    check_atom_crs,
    fetch_atom_file,
    resolve_atom_file,
)
from kartograf.transport.http import SessionPerThread, head_signal
from kartograf.transport.unit_package import (
    choice_keys,
    fetch_package,
    package_url,
    select_variant,
)

logger = logging.getLogger(__name__)

# One WFS/REST request (pages of GUGiK services answer in seconds; a busy
# service gets the shared retry policy), one package transfer (as BDOT10k),
# a HEAD of a file and the PRG powiat query.
SERVICE_TIMEOUT = 60
PACKAGE_TIMEOUT = 120
PROBE_TIMEOUT = 30

_TRACK: Track = "collection"
# Land cover products stay with LandCoverManager (ADR-039 D8, ADR-042 D10).
_LANDCOVER_GROUP = "landcover"
_TERYT = re.compile(r"[0-9]{2}(?:[0-9]{2})?")
_UNIT_TEXT = {"powiat": "powiatow", "woj": "wojewodztw", "country": "plik krajowy"}
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


def collection_levels(product: str) -> dict[str, tuple[str, ...]]:
    """``--level`` values of a product per country (empty: no levels)."""
    levels: dict[str, tuple[str, ...]] = {}
    for descriptor in sources_for(product=product):
        if not _is_collection(descriptor):
            continue
        for channel in descriptor.channels:
            params = channel.params
            if isinstance(params, FeatureBBoxParams) and params.selection == "level":
                levels[descriptor.country] = tuple(
                    layer.code for layer in params.layers
                )
    return levels


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
    (``year``, ``lod``, ``level``); ``area`` the area of the part (native CRS
    of a ``feature_bbox`` channel; any CRS for the powiats of a package
    channel); ``parent`` the ``extra.parent_request`` of its files.
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


@dataclass(frozen=True)
class CollectionRequest:
    """A request checked by ``validate_collection_request`` (no network)."""

    product: str
    output_dir: Path
    teryt: str | None
    whole_country: bool
    parts: tuple[CollectionPart, ...]


@dataclass(frozen=True)
class CollectionReport:
    """Outcome of ``download_collection``.

    ``files``: one ``UnitFile`` per file (``unit`` = TERYT, bbox
    coordinates or the country code); ``failed``: units that failed
    (``kind`` ``no_coverage`` - no data of the unit at the source -
    or ``download``), the others still ran; ``stale``: planned positions
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


def _available(descriptor: SourceDescriptor) -> str:
    """Selections a product offers (hint of a selection it does not have).

    An area names the channel ``_channel_for`` gives it: the objects of the
    area when the product has a ``feature_bbox`` channel, otherwise the
    packages of its powiats.
    """
    area_objects = _feature_channel(descriptor) is not None
    options: list[str] = []
    for channel in descriptor.channels:
        params = channel.params
        if isinstance(params, UnitPackageParams):
            options.append(
                {
                    "powiat": "--teryt <4 cyfry> (paczka powiatu)",
                    "woj": "--teryt <2 cyfry> (paczka wojewodztwa)",
                    "country": "--whole-country (plik krajowy)",
                }[params.unit]
            )
            if params.unit == "powiat" and not area_objects:
                options.append("--bbox/--sheet/--geometry (paczki powiatow obszaru)")
        elif isinstance(params, FeatureBBoxParams):
            options.append("--bbox/--sheet/--geometry (obiekty obszaru)")
    return ", ".join(dict.fromkeys(options))


def _package_channel(descriptor: SourceDescriptor, unit: str) -> AccessChannel | None:
    for channel in descriptor.channels:
        params = channel.params
        if isinstance(params, UnitPackageParams) and params.unit == unit:
            return channel
    return None


def _feature_channel(descriptor: SourceDescriptor) -> AccessChannel | None:
    for channel in descriptor.channels:
        if isinstance(channel.params, FeatureBBoxParams):
            return channel
    return None


def _atom_channel(descriptor: SourceDescriptor) -> AccessChannel | None:
    for channel in descriptor.channels:
        if isinstance(channel.params, AtomFilesParams):
            return channel
    return None


def subject(descriptor: SourceDescriptor) -> str:
    """How messages name a source: the product of a collection group
    (``admin``), the ``--source`` of a land cover source (``zabaged``)."""
    if descriptor.storage_subdir.split("/", 1)[0] == _LANDCOVER_GROUP:
        return descriptor.key.rsplit(".", 1)[-1]
    return descriptor.product


def _channel_for(
    descriptor: SourceDescriptor, kind: str, teryt: str | None
) -> AccessChannel:
    """The channel of a kind of selection (ADR-042 D2)."""
    product = subject(descriptor)
    if kind == "teryt":
        assert teryt is not None
        unit = "woj" if len(teryt) == 2 else "powiat"
        channel = _package_channel(descriptor, unit)
        missing = f"--teryt {teryt}: {product} nie ma paczek {_UNIT_TEXT[unit]}"
    elif kind == "whole_country":
        channel = _package_channel(descriptor, "country") or _atom_channel(descriptor)
        missing = (
            f"--whole-country: {product} ({descriptor.country}) nie ma pliku krajowego"
        )
    else:
        channel = _feature_channel(descriptor) or _package_channel(descriptor, "powiat")
        missing = f"{product} ({descriptor.country}) nie ma danych dla obszaru"
    if channel is None:
        raise ValidationError(f"{missing}; dostepne: {_available(descriptor)}")
    return channel


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
    horizontal_crs: str | None,
    countries: tuple[str, ...] = (),
) -> CollectionPart:
    """Content of one country part: variant, layers or ATOM file, segment and
    request values. ``countries``: the countries of an area request (hint
    of the per-country ``--level`` syntax)."""
    product = subject(descriptor)
    params = channel.params
    level_value = country_value(level, code)
    variant: PackageVariant | None = None
    layers: tuple[FeatureLayer, ...] = ()
    choice: dict[str, object]
    if isinstance(params, UnitPackageParams):
        if level_value is not None:
            raise ValidationError(
                f"--level dotyczy obiektow obszaru (--bbox/--sheet/--geometry), nie "
                f"paczek {product}"
            )
        variant = select_variant(params, lod=_str(lod), year=_str(year))
        segment = content_segment(descriptor.key, variant.segment_tokens)
        ext = params.unpack or ".zip"
        choice = {k: v for k, v in (("lod", lod), ("year", year)) if v is not None}
        crs = channel.horizontal_crs
    elif isinstance(params, AtomFilesParams):
        for name, value in (("level", level_value), ("lod", lod), ("year", year)):
            if value is not None:
                raise ValidationError(
                    f"--{name} nie dotyczy pliku krajowego {product} "
                    f"({descriptor.country}: biezace wydanie z feedu ATOM)"
                )
        check_atom_crs(params, horizontal_crs)
        segment = content_segment(
            descriptor.key, atom_segment_tokens(params, horizontal_crs)
        )
        ext = ".zip"
        choice = {}
        crs = horizontal_crs or channel.horizontal_crs
    else:
        assert isinstance(params, FeatureBBoxParams)
        for name, value in (("lod", lod), ("year", year)):
            if value is not None:
                raise ValidationError(
                    f"--{name} nie dotyczy obiektow obszaru produktu {product} "
                    f"({descriptor.country}: biezacy stan uslugi)"
                )
        codes = [layer.code for layer in params.layers]
        if params.selection == "level":
            hint = _level_hint(level, descriptor.product) if len(countries) > 1 else ""
            if level_value is None:
                raise ValidationError(
                    f"--level wymagane dla obszaru {product} ({descriptor.country}): "
                    f"{', '.join(codes)}{hint}"
                )
            if level_value not in codes:
                raise ValidationError(
                    f"--level {level_value}: nieznany poziom {product} "
                    f"({descriptor.country}); dostepne: {', '.join(codes)}{hint}"
                )
            layers = tuple(lay for lay in params.layers if lay.code == level_value)
            tokens: tuple[str, ...] = (level_value,)
            choice = {"level": level_value}
        else:
            if level_value is not None:
                raise ValidationError(
                    f"--level nie dotyczy produktu {product} (stala zawartosc: "
                    f"{', '.join(codes)})"
                )
            layers, tokens, choice = params.layers, (), {}
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
        code, descriptor, channel, variant, layers, segment, ext, choice
    )


def _selection_kind(args: dict) -> str:
    given = [
        name
        for name in ("teryt", "sheet", "bbox", "geometry")
        if args[name] is not None
    ] + (["whole_country"] if args["whole_country"] else [])
    if len(given) != 1:
        raise ValidationError(
            "Podaj dokladnie jeden wybor: --teryt, --sheet, --bbox, --geometry "
            "albo --whole-country"
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
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    horizontal_crs: str | None = None,
) -> CollectionRequest:
    """Check a collection request without network (ADR-042 D2).

    The same rules as ``download_collection`` and ``check_collection``
    (they call it first): ``bbox`` coordinates, exactly one of ``teryt``
    (2 digits = voivodeship, 4 = powiat; PL), ``sheet``, ``bbox``,
    ``geometry``, ``whole_country``; ``product`` of the registry; ``country``
    (``pl``/``cz``/``auto``) required with an area and with
    ``whole_country`` (``auto`` not), from the code with ``sheet``, ``pl``
    with ``teryt``; a channel for the kind of selection; the variant
    (``lod``, ``year``) required when the source publishes several, a level
    (``level``, per country with ``auto``) for an area of a product with
    levels; ``horizontal_crs`` only equal to the CRS of the file. Reads the
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
    content = {
        "level": args["level"],
        "lod": args["lod"],
        "year": args["year"],
        "horizontal_crs": args["horizontal_crs"],
    }
    teryt = args["teryt"]
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
        channel = _channel_for(descriptor, area_kind, teryt)
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
            product, output_dir, None, False, (_sheet_part(args, part),)
        )
    if country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    return CollectionRequest(
        product, output_dir, None, False, _area_parts(args, descriptors, part, sink)
    )


def _sheet_part(args: dict, part: Callable[..., CollectionPart]) -> CollectionPart:
    """Area of a sheet code: its extent (PL sheet codes, EPSG:2180)."""
    from kartograf.core.parser_registry import detect_system

    sheet, country = args["sheet"], args["country"]
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
    extent = parser.get_bbox(crs="EPSG:2180")
    parent = {"sheet": parser.sheet, "countries": ["PL"]}
    base = part("PL", "area")
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
    its size announced before the transfer); ``layers`` + ``bbox``: the
    objects of an area; ``atom`` = the national file of a CUZK ATOM feed in
    the CRS ``atom_crs`` (its URL and edition come from the feed at run
    time). ``request`` is the sidecar ``request`` (the user's choice in this
    unit), ``parent`` its ``extra.parent_request``.
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
) -> UnitJob:
    """The package of one unit (``teryt``) or the national file (``teryt=None``)."""
    params = channel.params
    assert isinstance(params, UnitPackageParams)
    segment = content_segment(descriptor.key, variant.segment_tokens)
    ext = params.unpack or ".zip"
    code = None if teryt is not None else country.lower()
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
        url=package_url(variant, teryt=teryt),
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


def _jobs(
    request: CollectionRequest, sink: NoticeSink, metadata: MetadataCache | None
) -> list[UnitJob]:
    """Unit jobs of a request; an area of a package product asks PRG."""
    out = request.output_dir
    jobs: list[UnitJob] = []
    for part in request.parts:
        if part.layers:
            jobs.append(_feature_job(out, part))
            continue
        if isinstance(part.channel.params, AtomFilesParams):
            jobs.append(_atom_job(out, part))
            continue
        assert part.variant is not None
        if request.teryt is not None or request.whole_country:
            selection = (
                {"teryt": request.teryt}
                if request.teryt is not None
                else {"whole_country": True}
            )
            jobs.append(
                package_job(
                    out,
                    part.descriptor,
                    part.channel,
                    part.variant,
                    country=part.country,
                    teryt=request.teryt,
                    request={**selection, **part.choice},
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
    """The capability that selects ``channel`` in the sidecar (unique in it)."""
    others = [c for c in descriptor.channels if c is not channel]
    return next(
        cap
        for cap in sorted(channel.capabilities)
        if all(cap not in other.capabilities for other in others)
    )


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
            key="",
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
    a new edition).
    """
    edition = (
        _atom_edition(_atom_file(job, session, cache, refresh=True))
        if job.atom
        else None
    )
    return inspect_version(
        job.slot,
        track=track,
        unit=job.unit,
        signal=job.signal,
        probe=_probe(job, session),
        edition=edition,
    )


def _local_only(slot: FileSlot) -> VersionedFile | None:
    """A position left out of the plan: its local version, never a download."""
    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)


def _size_text(length: int | None) -> str:
    if length is None:
        return "rozmiar nieznany (serwer nie podal Content-Length)"
    return f"{length} B (ok. {length / 1e6:.0f} MB)"


@dataclass
class _Source:
    """``extra.source`` of the file being downloaded (set by the fetch)."""

    value: dict = field(default_factory=dict)


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
    if job.whole_country:
        try:
            length = head_signal(session, job.url, timeout=PROBE_TIMEOUT)[
                "content_length"
            ]
        except DownloadError as e:
            logger.debug("HEAD %s: %s", job.url, e)
            length = None
        sink.emit(
            "warning",
            WHOLE_COUNTRY_SIZE,
            f"{subject(job.descriptor)} {job.country}: plik krajowy {job.url} - "
            f"{_size_text(length)}",
        )
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
    """The national file of an ATOM feed: its size from the feed before the
    transfer (K7), the ZIP 1:1."""
    sink.emit(
        "warning",
        WHOLE_COUNTRY_SIZE,
        f"{subject(job.descriptor)} {job.country}: plik krajowy {file.url} - "
        f"{_size_text(file.length)}",
    )
    http = fetch_atom_file(session, file, staged, timeout=timeout)
    source.value = {
        "url": file.url,
        "dataset_feed": file.dataset_feed,
        "edition": file.edition,
        "updated": file.updated,
    }
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
    its edition (``label_source="edition"``) or the download date, a file of
    an ATOM feed by the edition of the feed (signal ``metadata``), an area
    result by the download date; the sidecar names the channel by its
    capability and carries ``extra.source`` (``url``/``edition``/``member``,
    ``url``/``dataset_feed``/``edition``/``updated`` or
    ``service``/``layers``/``dropped_fields``), ``extra.http`` of a file and
    ``extra.parent_request``. ``session``: HTTP session of the requests
    (``LandCoverManager``: its provider's; ``None``: one per thread of this
    module); ``timeout``: seconds of one request (``None``:
    ``PACKAGE_TIMEOUT`` for a file, ``SERVICE_TIMEOUT`` for a page);
    ``on_download`` is called right before the transfer starts (never for
    a local version); ``cache``: the metadata cache of the ATOM feed index
    (revalidated with ``update="upgrade"``).

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
            _fetch_features(
                job, staged, source, _http(session), timeout or SERVICE_TIMEOUT
            )
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
        extra: dict = {"source": source.value}
        if http:
            extra["http"] = http
        if job.parent:
            extra["parent_request"] = job.parent
        params = job.channel.params
        if isinstance(params, FeatureBBoxParams):
            crs = params.native_crs
        else:
            crs = job.atom_crs or job.channel.horizontal_crs
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
    "sheet",
    "bbox",
    "geometry",
    "layer",
    "whole_country",
    "level",
    "lod",
    "year",
    "horizontal_crs",
)


def download_collection(
    *,
    product: str | None,
    output_dir: str | Path | None,
    country: str | None = None,
    teryt: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    horizontal_crs: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 1,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> CollectionReport:
    """Download a collection product (``boundaries``/``cadastre``/``models3d``/
    ``hydro`` ``download``) into the version store of ``output_dir``.

    Choices as in ``validate_collection_request`` (called first, no network):
    ``product`` (``admin`` PRG and RUIAN, ``map`` EGiB, ``buildings`` 3D
    models, ``network`` HY-NET), one selection (``teryt``, ``sheet``,
    ``bbox``, ``geometry`` or ``whole_country``), ``country``
    (``pl``/``cz``/``auto``), ``level`` (``admin`` of an area: PL
    ``wojewodztwo``, ``powiat``, ``gmina``, ``jednostka-ewidencyjna``,
    ``obreb``; CZ ``kraj``, ``okres``, ``obec``, ``katastralni-uzemi``; per
    country with ``auto``: ``{"pl": "gmina", "cz": "obec"}``), ``lod`` and
    ``year`` (``buildings``: LoD1 2019, 2021, 2022, 2024; LoD2 2017),
    ``horizontal_crs`` (a national file published in several CRSs). Files:
    ``<grupa>/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>}``
    with versions in ``versions/`` (ADR-042 D8). ``update``/``plan`` as in
    every store command (``plan`` from ``check_collection`` with
    ``update="upgrade"``); ``workers`` = units downloaded in parallel;
    ``cache`` = metadata cache of the PRG powiat query and of the ATOM feed
    index (``True``: default file in the current directory, ``False``:
    none); ``on_notice`` receives each notice when emitted (``UNIT_LIST``,
    ``WHOLE_COUNTRY_SIZE`` before a national transfer, clipping notices of
    ``auto``).

    Raises
    ------
    ValidationError
        Invalid or missing choice (before any request), a plan of another
        store or without ``update="upgrade"``.
    NoCoverageError
        An area of a package product without any powiat (PRG).
    DownloadError
        The PRG powiat query failed (unit failures land in ``failed``).
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
        "sheet": sheet,
        "bbox": bbox,
        "geometry": geometry,
        "layer": layer,
        "whole_country": whole_country,
        "level": None,
        "lod": None,
        "year": None,
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
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,
    lod: int | None = None,
    year: int | None = None,
    horizontal_crs: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_collection`` with the same choice; no data
    is downloaded (``kartograf-plan/1``, track ``collection``).

    Packages and area results of GUGiK have no cheap freshness signal: a
    local version is ``unverifiable``, a missing one ``missing``; files
    with ``ETag`` (``http``) are compared by ``HEAD``, files of an ATOM feed
    by the edition of the feed. An area of a package product asks PRG for
    its powiats.
    """
    sink = NoticeSink(on_notice)
    request = _resolve(_choices(locals()), sink)
    return plan_request(request, cache=cache, sink=sink)
