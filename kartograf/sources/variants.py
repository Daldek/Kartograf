"""
Product variant registry (ADR-041): one definition of what a product offers.

A variant is one combination of product, country, resolution, vertical CRS
and file format, bound to the descriptor that stores it (``source`` = the
sidecar ``dataset``) and to the sheet index (skorowidz WFS) its records come
from. Validation of the CLI/API choices, the ``--help`` texts,
``list-sources``, the storage segment and the hard record filter of the
index read THIS registry - no other module keeps a list of resolutions,
vertical CRSs or formats.

The variants live in the descriptors (``SourceDescriptor.variants``,
``kartograf/sources/registry.py``); this module adds the queries and the
rules shared by every reader: the resolution label (K2: ``0.5m``, ``10m``),
the GUGiK file formats of the index (``ASC`` grids and the archive formats
downloaded as source files) and the variant error messages. Pure data and
pure functions, no IO.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import TransportKind


@dataclass(frozen=True)
class IndexRef:
    """WFS sheet index of a variant: one service per product and height system.

    ``endpoint`` is the WFS address (``.../NumerycznyModelTerenuEVRF2007/WFS/
    Skorowidze``); its feature types are ``<layer_prefix><year>`` (one year
    per type, e.g. ``gugik:SkorowidzNMT2025``).
    """

    endpoint: str
    layer_prefix: str


@dataclass(frozen=True)
class FileFormat:
    """A file format of the GUGiK sheet index (record field ``format``).

    ``token`` is the CLI/API value (``--format``), ``extension`` the file
    extension in the store (the record ``format`` decides it, never the URL),
    ``url_suffixes`` the accepted endings of the record URL path (a record
    whose URL does not end with one of them is inconsistent and is not
    downloaded), ``source_file`` marks the archive formats: kept as the
    original file (no conversion, no cutout, no mosaic).
    """

    token: str
    index_name: str
    extension: str
    url_suffixes: tuple[str, ...]
    description: str
    source_file: bool


# GUGiK formats of the NMT/NMPT indexes (full WFS inventory 2026-10-15,
# docs/research/2026-10-15-plan-a-b/raport.md 1.1-1.2). The ASC grid is the
# product format; the rest are archives published until 2020.
FORMATS: tuple[FileFormat, ...] = (
    FileFormat(
        "ASC",
        "ARC/INFO ASCII GRID",
        ".asc",
        (".asc",),
        "ARC/INFO ASCII GRID",
        source_file=False,
    ),
    FileFormat(
        "XYZ",
        "ASCII XYZ GRID",
        ".zip",
        (".zip",),
        "ASCII XYZ GRID, ZIP",
        source_file=True,
    ),
    FileFormat(
        "ASCII-NMT",
        "ASCII NMT",
        ".zip",
        (".zip",),
        "ASCII NMT - punkty X Y Z, ZIP",
        source_file=True,
    ),
    FileFormat(
        "TBD",
        "ASCII TBD",
        ".zip",
        (".zip",),
        "ASCII TBD - punkty i linie struktury, ZIP",
        source_file=True,
    ),
    FileFormat(
        "TIN",
        "ESRI TIN",
        ".zip",
        (".zip",),
        "ESRI TIN, ZIP",
        source_file=True,
    ),
    FileFormat(
        "TTN",
        "Intergraph TTN",
        ".ttn",
        (".ttn",),
        "Intergraph TTN",
        source_file=True,
    ),
    FileFormat(
        "GRD",
        "Intergraph GRD",
        ".grd",
        (".grd",),
        "Intergraph GRD",
        source_file=True,
    ),
    FileFormat(
        "DXF",
        "Warstwice DXF",
        ".dxf",
        (".dxf",),
        "warstwice DXF",
        source_file=True,
    ),
    FileFormat(
        "DGN",
        "Warstwice DGN",
        ".dgn",
        (".dgn",),
        "warstwice DGN",
        source_file=True,
    ),
)

_BY_TOKEN = {f.token: f for f in FORMATS}
_BY_INDEX_NAME = {f.index_name: f for f in FORMATS}

# Display names of products in messages (identifiers stay lowercase).
_PRODUCT_NAMES = {"nmt": "NMT", "nmpt": "NMPT", "laz": "LAZ"}


@dataclass(frozen=True)
class ProductVariant:
    """One variant of a product (ADR-041, spec 3.1).

    ``systems``: horizontal systems whose sheets the variant may have - PL
    ``("1992", "2000")`` (which one a sheet has is a fact of the index, not
    of the registry). ``index_ref`` = the WFS index of the records (PL);
    ``None`` for variants without one.
    """

    source: str  # descriptor key = sidecar `dataset` ("pl.gugik.nmt_0_5m")
    product: str  # "nmt" | "nmpt" | "laz"
    country: str  # "PL"
    resolution_m: Decimal | None  # None: LAZ, TIN/TTN (no resolution in the index)
    vertical_crs: str  # CLI name: "EVRF2007" | "KRON86"
    format: str  # FileFormat.token: "ASC", "XYZ", ... ; LAZ: "LAZ"
    systems: tuple[str, ...]
    channel: TransportKind
    index_ref: IndexRef | None

    @property
    def label(self) -> str | None:
        """Resolution label K2 (``0.5m``); ``None`` without a resolution."""
        if self.resolution_m is None:
            return None
        return resolution_label(self.resolution_m)

    @property
    def source_file(self) -> bool:
        """Archive format: the file is kept as published (no cutout)."""
        known = _BY_TOKEN.get(self.format)
        return known is not None and known.source_file


def resolution_label(value: Decimal) -> str:
    """Label K2 of a resolution in metres: ``Decimal("0.5")`` -> ``0.5m``.

    ``format(..., "f")`` because ``Decimal("10").normalize()`` is ``1E+1``.
    """
    return format(value.normalize(), "f") + "m"


_LABEL = re.compile(r"(\d+(?:\.\d+)?)m")


def parse_resolution(label: str) -> Decimal | None:
    """``"0.5m"`` -> ``Decimal("0.5")``; ``None`` when not an exact label K2.

    Only the canonical text is a label: ``0,5m``, ``50cm``, ``0.50m``, ``5``
    or ``5 m`` give ``None`` (the caller lists the labels of the registry).
    """
    match = _LABEL.fullmatch(label) if isinstance(label, str) else None
    if match is None:
        return None
    try:
        value = Decimal(match[1])
    except InvalidOperation:
        return None
    return value if resolution_label(value) == label else None


def file_format(token: str) -> FileFormat:
    """The ``FileFormat`` of a token (``KeyError`` for an unknown one)."""
    return _BY_TOKEN[token]


def source_format(record_format: str | None, url: str) -> str | None:
    """Token of an index record's file: its ``format`` AND its URL agree.

    ``("ARC/INFO ASCII GRID", ".../x.asc")`` -> ``"ASC"``; the same format
    with a ``.xyz`` URL (42 NMT 2019 records) -> ``None``: an inconsistent
    record is never downloaded. Unknown formats -> ``None``.
    """
    known = _BY_INDEX_NAME.get((record_format or "").strip())
    if known is None:
        return None
    path = urlparse(url).path.lower()
    return known.token if path.endswith(known.url_suffixes) else None


def variants(
    *,
    product: str | None = None,
    country: str | None = None,
    vertical_crs: str | None = None,
    resolution: str | None = None,
    system: str | None = None,
    format: str | None = None,
) -> tuple[ProductVariant, ...]:
    """Registered variants matching every given filter (registry order).

    ``resolution`` compares the label K2 (``"0.5m"``), ``system`` looks into
    ``ProductVariant.systems``, ``format`` compares the token (``"ASC"``).
    """
    # local import: the registry builds its descriptors from this module
    from kartograf.sources.registry import all_sources

    return tuple(
        variant
        for descriptor in all_sources()
        for variant in descriptor.variants
        if (product is None or variant.product == product)
        and (country is None or variant.country == country)
        and (vertical_crs is None or variant.vertical_crs == vertical_crs)
        and (resolution is None or variant.label == resolution)
        and (system is None or system in variant.systems)
        and (format is None or variant.format == format)
    )


def _sorted_labels(found: tuple[ProductVariant, ...]) -> list[str]:
    values = sorted({v.resolution_m for v in found if v.resolution_m is not None})
    return [resolution_label(value) for value in values]


def labels_by_vertical_crs(found: tuple[ProductVariant, ...]) -> str:
    """``EVRF2007: 0.5m, 1m; KRON86: 1m`` - labels of the variants per height
    system (registry order of the systems)."""
    groups: dict[str, list[ProductVariant]] = {}
    for variant in found:
        groups.setdefault(variant.vertical_crs, []).append(variant)
    parts = []
    for vertical_crs, group in groups.items():
        labels = _sorted_labels(tuple(group))
        parts.append(
            f"{vertical_crs}: {', '.join(labels) if labels else 'bez rozdzielczosci'}"
        )
    return "; ".join(parts)


def _primary(found: tuple[ProductVariant, ...]) -> tuple[ProductVariant, ...]:
    """Variants in the product format (no archive)."""
    return tuple(v for v in found if not v.source_file)


def format_tokens(found: tuple[ProductVariant, ...]) -> list[str]:
    """Format tokens of the variants in the order of ``FORMATS``."""
    present = {v.format for v in found}
    return [f.token for f in FORMATS if f.token in present]


def variant_error(
    *,
    product: str,
    country: str,
    resolution: str | None,
    vertical_crs: str | None,
    format: str | None = None,
) -> str | None:
    """Error text for a variant choice (``None`` = the choice fits a variant).

    ``format=None`` = the product format (PL: ``ASC`` grids); a source-file
    format must be named (``--format``). ``resolution=None`` is valid when
    the format and height system leave one label (or the format has no
    resolution, TIN/TTN). ``vertical_crs=None`` checks only what does not
    depend on the height system (format, resolution in any system) - the
    caller reports a missing ``--vertical-crs`` itself. Texts name the CLI
    flags (the CLI passes them 1:1, STANDARDS 11).
    """
    name = _PRODUCT_NAMES.get(product, product.upper())
    found = variants(product=product, country=country)
    if not found:
        return f"--product {product} nie ma wariantow w {country}"
    if format is None:
        chosen = _primary(found)
        shown = name
    else:
        chosen = tuple(v for v in found if v.format == format)
        shown = f"{name} {format}"
        if not chosen:
            return (
                f"--format {format}: niedostepny dla {name} {country} - dostepne: "
                f"{', '.join(format_tokens(found))}"
            )
    if vertical_crs is None:
        in_crs = chosen
    else:
        in_crs = tuple(v for v in chosen if v.vertical_crs == vertical_crs)
        if not in_crs:
            systems = sorted({v.vertical_crs for v in chosen})
            return (
                f"{shown} ({country}) jest dostepny tylko w {', '.join(systems)} - "
                f"podano --vertical-crs {vertical_crs}"
            )
    labels = _sorted_labels(in_crs)
    if resolution is None:
        if len({v.label for v in in_crs}) <= 1:
            return None
        return (
            f"--resolution wymagane dla {shown} {country}: "
            f"{labels_by_vertical_crs(chosen)}"
        )
    if not labels:
        return (
            f"--resolution nie dotyczy {shown} (skorowidz nie podaje "
            "rozdzielczosci) - pomin --resolution"
        )
    if resolution in labels:
        return None
    everywhere = _sorted_labels(chosen)
    if resolution in everywhere:
        systems = sorted({v.vertical_crs for v in chosen if v.label == resolution})
        return (
            f"{shown} {resolution} ({country}) jest dostepny tylko w "
            f"{', '.join(systems)} - podano --vertical-crs {vertical_crs}; "
            f"dostepne w {vertical_crs}: {', '.join(labels)}"
        )
    return (
        f"{country} nie ma rozdzielczosci {resolution} dla {shown} - dostepne: "
        f"{labels_by_vertical_crs(chosen)}"
    )


def find_variant(
    *,
    product: str,
    country: str,
    resolution: str | None,
    vertical_crs: str,
    format: str | None = None,
) -> ProductVariant:
    """The one variant of a choice; ``ValidationError`` with ``variant_error``.

    ``resolution=None`` selects the only variant of the format and height
    system (``GRD``: 5m, ``TIN``: none); ``format=None`` = product format.
    """
    error = variant_error(
        product=product,
        country=country,
        resolution=resolution,
        vertical_crs=vertical_crs,
        format=format,
    )
    if error is not None:
        raise ValidationError(error)
    found = variants(product=product, country=country, vertical_crs=vertical_crs)
    candidates = (
        _primary(found)
        if format is None
        else tuple(v for v in found if v.format == format)
    )
    if resolution is not None:
        candidates = tuple(v for v in candidates if v.label == resolution)
    return candidates[0]
