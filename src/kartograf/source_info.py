"""
Registered sources and the layers of the command groups as documents.

``list_sources`` (``kartograf-sources/1``) lists the sources of one group of
``<group> download`` from the descriptor registry (``kartograf.sources``) and
names, for each source, the options that choose it (``select``).
``list_layers`` (``kartograf-layers/1``) lists what ``landcover`` and ``soil``
offer inside a product: BDOT10k layers, ZABAGED/Data50/Data250 service layers,
BDOO classes per release, CORINE releases, SoilGrids properties, depths and
statistics. Both read the registry and the catalogues of the providers: no
network, nothing written (spec 5.4.6-5.4.7). The tables of ``list-sources`` and
``list-layers`` of the CLI are rendered from these documents.

Examples
--------
>>> from kartograf.source_info import list_sources
>>> nmt = list_sources(group="elevation", product="nmt").sources[0]
>>> nmt.select["product"], nmt.select["country"]
('nmt', 'pl')
"""

from dataclasses import dataclass
from typing import get_args

from kartograf.download.collections import collection_layers, collection_products
from kartograf.download.options import ELEVATION_PRODUCTS, IMAGERY_PRODUCTS
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_PRODUCT_CHOICES,
    LANDCOVER_PRODUCTS,
    LandCoverManager,
    soil_choices,
)
from kartograf.messages import message
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.soilgrids import PROPERTY_UNITS, SoilGridsProvider
from kartograf.serialization import Document
from kartograf.sources.descriptor import SignalKind, SourceDescriptor, UnitPackageParams
from kartograf.sources.registry import get_source, sources_for

# The groups with ``list-sources`` / ``list-layers`` (the command groups of the
# data types; ``cache`` lists nothing).
SOURCE_GROUPS: tuple[str, ...] = (
    "elevation",
    "imagery",
    "landcover",
    "soil",
    "boundaries",
    "cadastre",
    "models3d",
    "hydro",
    "names",
    "maps",
    "geodesy",
)
LAYER_GROUPS: tuple[str, ...] = ("landcover", "soil")

# The product of the ``soil`` group (SoilGrids; ``download_soil`` has no
# ``product`` argument).
_SOIL_PRODUCTS: tuple[str, ...] = ("soil",)

# What a CORINE release holds: the CLMS data (with ``CLMS_CREDENTIALS``; without
# them the WMS preview) or the WMS preview only.
_CORINE_CLMS = message("source_info.corine_clms")
_CORINE_WMS = message("source_info.corine_wms")

# One option of ``select``: a value, a list of admissible values or ``None`` (a
# free choice from the values of ``list_layers``).
SelectValue = str | int | tuple[str | int, ...] | None


@dataclass(frozen=True)
class SourceLicense:
    """The license of a source.

    Its registry ``id``, the ready-made ``attribution`` text and the ``url`` of the
    terms (may be empty).
    """

    id: str
    attribution: str
    url: str


@dataclass(frozen=True)
class SourceInfo:
    """One registered source (an element of ``SourceList.sources``).

    Attributes
    ----------
    key : str
        The descriptor key - the ``dataset`` field of the sidecar of its files
        (``pl.gugik.nmt_1m``).
    name : str
        Name of the dataset.
    country : str
        ``PL``, ``CZ``, ``EU`` or ``GLOBAL``.
    provider : str
        The data provider (``GUGiK``, ``CUZK``, ...).
    product : str
        The value of ``product`` that selects the source.
    directory : str
        The segment of its files below ``root``; ``<uklad>`` and
        ``<uklad-wys>`` stand for the horizontal and the vertical system that
        follow from the choice, a variant choice (scale, format, release)
        appends ``_<value>`` parts.
    select : dict
        Every option the library function of the group (``download_data``,
        ``download_collection``, ``download_landcover``, ``download_soil``)
        needs to choose this source, in the order of the flags of the command:
        option -> its value, a tuple of admissible values (the caller chooses
        one) or ``None`` (a free choice from the values of ``list_layers``).
    license : SourceLicense
        The license and the attribution of the data.
    auth : str
        ``none`` or ``clms_oauth`` (Copernicus credentials).
    update_signals : tuple of str
        The freshness signals of the access channels (``index``,
        ``metadata``, ``http``, ``none``): what ``check_*`` can compare cheaply.
    """

    key: str
    name: str
    country: str
    provider: str
    product: str
    directory: str
    select: dict[str, SelectValue]
    license: SourceLicense
    auth: str
    update_signals: tuple[str, ...]


@dataclass(frozen=True)
class SourceList(Document):
    """The sources of one group (``kartograf-sources/1``).

    ``products`` are the products of the whole group even when ``sources`` is
    narrowed to one ``product``; the sources follow the order of the products,
    within a product the order of the registry.
    """

    SCHEMA = "kartograf-sources/1"

    group: str
    products: tuple[str, ...]
    sources: tuple[SourceInfo, ...]


@dataclass(frozen=True)
class LayerInfo:
    """A layer, a soil property or a statistic.

    Its ``code`` (the value to pass) and the ``description`` (``None``: the source names
    the layer only).
    """

    code: str
    description: str | None


@dataclass(frozen=True)
class PropertyInfo(LayerInfo):
    """A SoilGrids property.

    Its ``code`` and ``description`` (the text names the unit), the ``unit`` of the
    integer values in the file (the ISRIC "mapped units"), the ``conventional_unit`` and
    the ``divisor``: the familiar value is ``value / divisor``; ``depths``: the depth
    intervals published for it.
    """

    unit: str
    conventional_unit: str
    divisor: int
    depths: tuple[str, ...]


@dataclass(frozen=True)
class YearInfo:
    """A CORINE release.

    ``year`` (the reference year, the value of ``year``), ``data`` - ``clms`` (the CLMS
    data; the WMS preview without credentials) or ``wms`` (the preview only) - and the
    ``description`` of it.
    """

    year: int
    data: str
    description: str


@dataclass(frozen=True)
class LayerList(Document):
    """What a product of ``landcover`` or ``soil`` offers (``kartograf-layers/1``).

    Only the fields of the product are filled, the others are empty (``layers``)
    or ``None``: ``layers`` (BDOT10k: the code and description of every class
    ``--layers`` accepts; ZABAGED, Data50, Data250: the name of the layer of
    the service), ``classes`` (BDOO: release year -> class codes), ``years``
    (CORINE), ``properties`` (``PropertyInfo``), ``depths`` (the depth
    intervals of all properties) and ``statistics`` (SoilGrids). ``product`` is
    ``None`` for ``soil``.
    """

    SCHEMA = "kartograf-layers/1"

    group: str
    product: str | None
    source: str
    layers: tuple[LayerInfo, ...] = ()
    classes: dict[str, tuple[str, ...]] | None = None
    years: tuple[YearInfo, ...] | None = None
    properties: tuple[LayerInfo, ...] | None = None
    depths: tuple[str, ...] | None = None
    statistics: tuple[LayerInfo, ...] | None = None


def list_sources(*, group: str, product: str | None = None) -> SourceList:
    """Return the registered sources of a command group, with the options choosing each.

    Parameters
    ----------
    group : str
        One of ``SOURCE_GROUPS``: ``elevation``, ``imagery``, ``landcover``,
        ``soil``, ``boundaries``, ``cadastre``, ``models3d``, ``hydro``,
        ``names``, ``maps``, ``geodesy``.
    product : str, optional
        Only the sources of this product of the group (default: all).

    Returns
    -------
    SourceList
        The document ``kartograf-sources/1``. No network, nothing written.

    Raises
    ------
    ValidationError
        An unknown ``group`` (``option="group"``) or a ``product`` the group
        does not have (``option="product"``); ``allowed`` lists the values.

    Examples
    --------
    >>> from kartograf.source_info import list_sources
    >>> corine = list_sources(group="landcover", product="corine").sources[0]
    >>> corine.select
    {'product': 'corine', 'year': (2018, 2012, 2006, 2000, 1990)}
    """
    products = _group_products(group)
    if product is not None and product not in products:
        raise ValidationError(
            message(
                "source_info.unknown_product_for_group",
                product=product,
                group=group,
                products=", ".join(products),
            ),
            option="product",
            allowed=products,
        )
    chosen = products if product is None else (product,)
    return SourceList(
        group=group,
        products=products,
        sources=tuple(
            _source_info(group, descriptor)
            for name in chosen
            for descriptor in sources_for(product=name)
        ),
    )


def list_layers(*, group: str, product: str | None = None) -> LayerList:
    """Return the layers a product of ``landcover`` or ``soil`` offers.

    Parameters
    ----------
    group : str
        ``landcover`` or ``soil``.
    product : str, optional
        ``landcover``: the product - ``bdot10k``, ``bdoo``, ``corine``,
        ``zabaged``, ``data50`` or ``data250`` (required); ``soil``: not given.

    Returns
    -------
    LayerList
        The document ``kartograf-layers/1``. No network, nothing written.

    Raises
    ------
    ValidationError
        A ``group`` without layers (``option="group"``), a missing or unknown
        ``product`` of ``landcover``, a ``product`` given for ``soil``
        (``option="product"``).

    Examples
    --------
    >>> from kartograf.source_info import list_layers
    >>> [y.year for y in list_layers(group="landcover", product="corine").years]
    [2018, 2012, 2006, 2000, 1990]
    """
    if group not in LAYER_GROUPS:
        raise ValidationError(
            message(
                "source_info.layers_only_groups",
                group=group,
                layer_groups=", ".join(LAYER_GROUPS),
            ),
            option="group",
            allowed=LAYER_GROUPS,
        )
    if group == "soil":
        if product is not None:
            raise ValidationError(
                message("source_info.soil_has_no_products"),
                option="product",
            )
        return _soil_layers()
    if product is None:
        raise ValidationError(
            message(
                "source_info.product_required",
                landcover_product_choices=LANDCOVER_PRODUCT_CHOICES,
            ),
            option="product",
            allowed=LANDCOVER_PRODUCTS,
        )
    if product not in LANDCOVER_PRODUCTS:
        raise ValidationError(
            message(
                "source_info.unknown_product",
                product=product,
                landcover_product_choices=LANDCOVER_PRODUCT_CHOICES,
            ),
            option="product",
            allowed=LANDCOVER_PRODUCTS,
        )
    return _landcover_layers(product)


# =============================================================================
# Sources
# =============================================================================


def _group_products(group: str) -> tuple[str, ...]:
    """Return the products of ``group`` in the order of its ``download`` command."""
    if group not in SOURCE_GROUPS:
        raise ValidationError(
            message(
                "source_info.unknown_group",
                group=group,
                source_groups=", ".join(SOURCE_GROUPS),
            ),
            option="group",
            allowed=SOURCE_GROUPS,
        )
    if group == "elevation":
        return ELEVATION_PRODUCTS
    if group == "imagery":
        return IMAGERY_PRODUCTS
    if group == "landcover":
        return LANDCOVER_PRODUCTS
    if group == "soil":
        return _SOIL_PRODUCTS
    return collection_products(group)


def _source_info(group: str, source: SourceDescriptor) -> SourceInfo:
    signals = {channel.update_signal for channel in source.channels}
    order = get_args(SignalKind)
    return SourceInfo(
        key=source.key,
        name=source.name,
        country=source.country,
        provider=source.provider_name,
        product=source.product,
        directory=source.storage_subdir.replace("{system}", "<crs>").replace(
            "{vcrs}", "<vertical-crs>"
        ),
        select=_select(group, source),
        license=SourceLicense(
            source.license.id, source.license.attribution, source.license.url
        ),
        auth=source.auth,
        update_signals=tuple(sorted(signals, key=order.index)),
    )


def _select(group: str, source: SourceDescriptor) -> dict[str, SelectValue]:
    """Return the options that choose ``source`` in ``download`` of ``group``."""
    if group == "elevation":
        return _elevation_select(source)
    if group == "landcover":
        return _landcover_select(source)
    if group == "soil":
        # SoilGrids: one source, the layer is a free choice (``list_layers``)
        return {"property": None, "depth": None, "stat": None}
    # imagery and the collection groups: the product and the country of the source
    return {"product": source.product, "country": source.country.lower()}


def _one_or_choice[T](values: tuple[T, ...]) -> T | tuple[T, ...]:
    """One admissible value is the value itself, several are a choice."""
    return values[0] if len(values) == 1 else values


def _elevation_select(source: SourceDescriptor) -> dict[str, SelectValue]:
    """Every required choice of ``elevation download``, from the variant registry.

    ``country``, ``resolution``/``format``/``model`` and ``vertical_crs`` with the
    height systems of the source (none for NMT 100 m; contours take only Bpv, which may
    be omitted).
    """
    select: dict[str, SelectValue] = {
        "product": source.product,
        "country": source.country.lower(),
    }
    variant = source.variants[0] if source.variants else None
    if variant is None:
        return select
    systems = tuple(
        dict.fromkeys(v.vertical_crs for v in source.variants if v.vertical_crs)
    )
    if source.country == "CZ":
        if source.product == "laz":
            assert variant.model is not None  # a CZ cloud is a model of CUZK
            select["model"] = variant.model
        elif variant.label is None:  # contours: one format each
            select["format"] = variant.format
            return select
        else:
            assert source.resolution is not None
            select["resolution"] = source.resolution
    else:
        if variant.source_file and source.product != "laz":
            select["format"] = variant.format
        if variant.label is not None:
            select["resolution"] = variant.label
    if systems:
        select["vertical_crs"] = _one_or_choice(systems)
    return select


def _landcover_select(source: SourceDescriptor) -> dict[str, SelectValue]:
    """Return the ``product`` of a descriptor (``bdot10k``) with its releases.

    The ``year`` is required by some products (BDOO, CORINE).
    """
    select: dict[str, SelectValue] = {"product": source.product}
    if source.product == "bdoo":
        select["year"] = _one_or_choice(_release_years(source.key))
    elif source.product == "corine":
        select["year"] = _one_or_choice(tuple(CorineProvider.AVAILABLE_YEARS))
    return select


def _release_years(key: str) -> tuple[int, ...]:
    """Return the release years of the unit packages of source ``key``, ascending."""
    return tuple(
        sorted(
            {
                int(dict(variant.choice)["year"])
                for channel in get_source(key).channels
                if isinstance(channel.params, UnitPackageParams)
                for variant in channel.params.variants
            }
        )
    )


# =============================================================================
# Layers
# =============================================================================


def _landcover_layers(product: str) -> LayerList:
    # the catalogue of the product (no network, nothing written)
    manager = LandCoverManager(product, cache=False, root=".")
    source = manager.provider_name
    if product in COLLECTION_SOURCES:
        key = COLLECTION_SOURCES[product]
        classes = _release_classes(key)
        if classes:
            return LayerList("landcover", product, source, classes=classes)
        layers = tuple(LayerInfo(layer.name, None) for layer in collection_layers(key))
        return LayerList("landcover", product, source, layers)
    provider = manager.provider
    if product == "bdot10k":
        assert isinstance(provider, Bdot10kProvider)
        layers = tuple(
            LayerInfo(code, provider.get_layer_description(code))
            for code in provider.get_available_layers()
        )
        return LayerList("landcover", product, source, layers)
    assert isinstance(provider, CorineProvider)
    years = tuple(
        YearInfo(
            year,
            "clms" if year in provider.CLMS_YEARS else "wms",
            _CORINE_CLMS if year in provider.CLMS_YEARS else _CORINE_WMS,
        )
        for year in provider.get_available_years()
    )
    return LayerList("landcover", product, source, years=years)


def _release_classes(key: str) -> dict[str, tuple[str, ...]]:
    """Return the class codes ``layers`` may keep from the packages of ``key``.

    The codes are given by release year (``{}``: the source has no class
    selection).
    """
    return {
        dict(variant.choice)["year"]: variant.classes
        for channel in get_source(key).channels
        if isinstance(channel.params, UnitPackageParams)
        for variant in channel.params.variants
        if variant.classes
    }


def _soil_layers() -> LayerList:
    # the catalogue of the source (no network, nothing written)
    provider = LandCoverManager("soilgrids", cache=False, root=".").provider
    assert isinstance(provider, SoilGridsProvider)
    choices = soil_choices()
    return LayerList(
        "soil",
        None,
        provider.name,
        properties=tuple(
            PropertyInfo(
                code,
                provider.get_property_description(code),
                PROPERTY_UNITS[code].mapped,
                PROPERTY_UNITS[code].conventional,
                PROPERTY_UNITS[code].divisor,
                tuple(provider.depths_for(code)),
            )
            for code in provider.get_available_properties()
        ),
        depths=tuple(choices["depth"]),
        statistics=tuple(
            LayerInfo(code, text) for code, text in choices["stat"].items()
        ),
    )
