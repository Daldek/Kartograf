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

A PL variant without a sheet index (``index_ref=None``: NMT 100 m, the
voivodeship files of an ATOM feed, plan E) has one format - its product
format, no ``--format`` choice - and may have no height system
(``vertical_crs=None``: the source does not declare one, decision P1 of
2026-10-15; no ``--vertical-crs``).

CZ variants (plan B, ADR-041 supplement) are the rows of the route table:
one per (product, resolution or model, height system, sheet system ``sm5``
/``tm33``) with the channel serving it - the CUZK file (``DIRECT_FILES``)
or the ImageServer warped onto the tile grid (``ARCGIS_IMAGE``). A CZ
cutout is not a row: it is the ImageServer channel of the descriptor.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from kartograf.core.parser_registry import detect_system
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
        # `.xyz`: the 42 grids of NMT 2019 campaign 72675 (N-33-69) are
        # published under a `.xyz` name; every one is an AAIGrid (header
        # read live 2026-10-15), checked again after download
        (".asc", ".xyz"),
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

# CUZK models (``ProductVariant.model``): the name in messages and the
# description of the ``--model`` choice (LAZ CZ).
CZ_MODELS: dict[str, tuple[str, str]] = {
    "dmr5g": ("DMR 5G", "teren, DMR 5G"),
    "dmr4g": ("DMR 4G", "teren, siatka 5 m"),
    "dmp1g": ("DMP 1G", "powierzchnia, DMP 1G"),
    "dmpok": ("DMP OK", "powierzchnia, korelacja obrazowa"),
}
# Sheet systems of the CZ codes (``detect_system`` id -> variant system).
_CZ_SYSTEMS = {"cz_sm5": "sm5", "cz_tm33": "tm33"}
# Height systems of the CZ rasters (``--vertical-crs`` texts).
CZ_VERTICAL_TEXT = (
    "Bpv (natywny dla S-JTSK/SM5 i uslug ImageServer), EVRF2007 (natywny dla "
    "plikow ETRS89/TM33; z Bpv przypieta transformacja)"
)
# LAZ CZ: a point cloud keeps the CRS of its file, the height system chooses
# the files (S-JTSK sheets in Bpv, ETRS89 tiles in EVRF2007).
CZ_LAZ_VERTICAL_TEXT = (
    "Bpv (arkusze SM5, S-JTSK) albo EVRF2007 (kafle TM33, ETRS89); chmury "
    "punktow bez transformacji"
)
# Name of the missing height system of a variant in messages (P1).
UNKNOWN_VERTICAL = "uklad wysokosci nieznany"


@dataclass(frozen=True)
class ProductVariant:
    """One variant of a product (ADR-041, spec 3.1).

    ``systems``: horizontal systems whose sheets the variant may have - PL
    ``("1992", "2000")`` (which one a sheet has is a fact of the index, not
    of the registry), CZ ``("sm5",)`` or ``("tm33",)`` (one row of the route
    table per sheet system). ``channel``: the transport of the file - PL the
    WFS index, CZ ``DIRECT_FILES`` (CUZK file) or ``ARCGIS_IMAGE`` (the
    ImageServer warped onto the TM33 grid), PL ``DIRECT_FILES`` for the
    voivodeship files of an ATOM feed. ``index_ref`` = the WFS index of the
    records (PL); ``None`` for variants without one. ``model``: the CUZK
    model (``dmr5g``, ``dmr4g``, ``dmp1g``, ``dmpok``); ``None`` in PL.
    ``vertical_crs=None``: the source declares no height system (NMT 100 m,
    P1); ``vertical_note`` says so in the sidecar
    (``extra.vertical_crs_note``).
    """

    source: str  # descriptor key = sidecar `dataset` ("pl.gugik.nmt_0_5m")
    product: str  # "nmt" | "nmpt" | "laz"
    country: str  # "PL" | "CZ"
    resolution_m: Decimal | None  # None: LAZ, TIN/TTN (no resolution in the index)
    vertical_crs: str | None  # CLI name: "EVRF2007" | "KRON86" | "Bpv"; None: unknown
    format: str  # FileFormat.token: "ASC", "XYZ", ... ; LAZ: "LAZ"; CZ: "TIFF"
    systems: tuple[str, ...]
    channel: TransportKind
    index_ref: IndexRef | None
    model: str | None = None
    vertical_note: str | None = None

    @property
    def label(self) -> str | None:
        """Resolution label K2 (``0.5m``); ``None`` without a resolution."""
        if self.resolution_m is None:
            return None
        return resolution_label(self.resolution_m)

    @property
    def source_file(self) -> bool:
        """Check whether the variant is an archive of the sheet index.

        An archive of the sheet index (``--format`` required): the file is kept as
        published (no cutout, no mosaic). A variant without a sheet index (ATOM
        voivodeship files) has one format - its product format - even when it is an
        archive format of the index (XYZ ZIP).
        """
        known = _BY_TOKEN.get(self.format)
        return known is not None and known.source_file and self.index_ref is not None


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
    """Return the ``FileFormat`` of a token (``KeyError`` for an unknown one)."""
    return _BY_TOKEN[token]


def source_format(record_format: str | None, url: str) -> str | None:
    """Token of an index record's file: its ``format`` AND its URL agree.

    ``("ARC/INFO ASCII GRID", ".../x.asc")`` -> ``"ASC"`` (also the ``.xyz``
    names of the 72675 grids, ``FORMATS``); a grid format with a ``.zip`` URL
    or an archive format with a ``.asc`` URL -> ``None``: an inconsistent
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
    model: str | None = None,
) -> tuple[ProductVariant, ...]:
    """Return the registered variants matching every given filter.

    ``resolution`` compares the label K2 (``"0.5m"``), ``system`` looks into
    ``ProductVariant.systems``, ``format`` compares the token (``"ASC"``),
    ``model`` the CUZK model (``"dmr4g"``).
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
        and (model is None or variant.model == model)
    )


def _sorted_labels(found: tuple[ProductVariant, ...]) -> list[str]:
    values = sorted({v.resolution_m for v in found if v.resolution_m is not None})
    return [resolution_label(value) for value in values]


def _system_name(vertical_crs: str | None) -> str:
    return UNKNOWN_VERTICAL if vertical_crs is None else vertical_crs


def _named_systems(found: tuple[ProductVariant, ...]) -> list[str]:
    """Return the sorted height systems a ``--vertical-crs`` can name.

    Height systems of the variants a ``--vertical-crs`` can name, sorted (a variant
    without one takes no flag).
    """
    return sorted({v.vertical_crs for v in found if v.vertical_crs is not None})


def labels_by_vertical_crs(found: tuple[ProductVariant, ...]) -> str:
    """Format the variant labels per height system.

    ``EVRF2007: 0.5m, 1m; KRON86: 1m`` - labels of the variants per height system
    (registry order of the systems; variants without one under ``UNKNOWN_VERTICAL``).
    """
    groups: dict[str | None, list[ProductVariant]] = {}
    for variant in found:
        groups.setdefault(variant.vertical_crs, []).append(variant)
    parts = []
    for vertical_crs, group in groups.items():
        labels = _sorted_labels(tuple(group))
        parts.append(
            f"{_system_name(vertical_crs)}: "
            f"{', '.join(labels) if labels else 'bez rozdzielczosci'}"
        )
    return "; ".join(parts)


def _primary(found: tuple[ProductVariant, ...]) -> tuple[ProductVariant, ...]:
    """Variants in the product format (no archive of the sheet index)."""
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
) -> ValidationError | None:
    """Return the error of a variant choice (``None`` = the choice fits a variant).

    ``format=None`` = the product format (PL: ``ASC`` grids); a source-file
    format must be named (``--format``). ``resolution=None`` is valid when
    the format and height system leave one label (or the format has no
    resolution, TIN/TTN). ``vertical_crs=None`` checks only what does not
    depend on the height system - the caller reports a missing
    ``--vertical-crs`` itself. Texts name the CLI flags (the CLI passes them
    1:1); ``option`` and ``allowed`` of the error are the
    argument and the registry values the text lists.
    """
    name = _PRODUCT_NAMES.get(product, product.upper())
    found = variants(product=product, country=country)
    if not found:
        return ValidationError(
            f"--product {product} nie ma wariantow w {country}",
            option="product",
            allowed=tuple(dict.fromkeys(v.product for v in variants(country=country))),
        )
    if format is None:
        chosen = _primary(found)
        shown = name
    else:
        chosen = tuple(v for v in found if v.format == format)
        shown = f"{name} {format}"
        if not chosen:
            tokens = format_tokens(found)
            return ValidationError(
                f"--format {format}: niedostepny dla {name} {country} - dostepne: "
                f"{', '.join(tokens)}",
                option="format",
                allowed=tuple(tokens),
            )
    if vertical_crs is None:
        in_crs = chosen
    else:
        in_crs = tuple(v for v in chosen if v.vertical_crs == vertical_crs)
        if not in_crs:
            named = _named_systems(chosen)
            if not named:
                return ValidationError(
                    f"{shown} ({country}): {UNKNOWN_VERTICAL} (zrodlo go nie "
                    "deklaruje) - pomin --vertical-crs",
                    option="vertical_crs",
                )
            return ValidationError(
                f"{shown} ({country}) jest dostepny tylko w {', '.join(named)} - "
                f"podano --vertical-crs {vertical_crs}",
                option="vertical_crs",
                allowed=tuple(named),
            )
    labels = _sorted_labels(in_crs)
    if resolution is None:
        if len({v.label for v in in_crs}) <= 1:
            return None
        return ValidationError(
            f"--resolution wymagane dla {shown} {country}: "
            f"{labels_by_vertical_crs(chosen)}",
            option="resolution",
            allowed=tuple(labels),
        )
    if not labels:
        return ValidationError(
            f"--resolution nie dotyczy {shown} (skorowidz nie podaje "
            "rozdzielczosci) - pomin --resolution",
            option="resolution",
        )
    if resolution in labels:
        return None
    everywhere = _sorted_labels(chosen)
    if resolution in everywhere:
        of_label = tuple(v for v in chosen if v.label == resolution)
        named = _named_systems(of_label)
        if not named:
            return ValidationError(
                f"{shown} {resolution} ({country}): {UNKNOWN_VERTICAL} (zrodlo go "
                "nie deklaruje) - pomin --vertical-crs",
                option="vertical_crs",
            )
        return ValidationError(
            f"{shown} {resolution} ({country}) jest dostepny tylko w "
            f"{', '.join(named)} - podano --vertical-crs {vertical_crs}; "
            f"dostepne w {vertical_crs}: {', '.join(labels)}",
            options=("resolution", "vertical_crs"),
        )
    return ValidationError(
        f"{country} nie ma rozdzielczosci {resolution} dla {shown} - dostepne: "
        f"{labels_by_vertical_crs(chosen)}",
        option="resolution",
        allowed=tuple(everywhere),
    )


def find_variant(
    *,
    product: str,
    country: str,
    resolution: str | None,
    vertical_crs: str | None,
    format: str | None = None,
) -> ProductVariant:
    """Return the one variant of a choice, or raise its ``variant_error``.

    ``resolution=None`` selects the only variant of the format and height
    system (``GRD``: 5m, ``TIN``: none); ``format=None`` = product format;
    ``vertical_crs=None`` = a variant without a height system (NMT 100 m).
    """
    error = variant_error(
        product=product,
        country=country,
        resolution=resolution,
        vertical_crs=vertical_crs,
        format=format,
    )
    if error is not None:
        raise error
    found = variants(product=product, country=country)
    candidates = tuple(
        v
        for v in (_primary(found) if format is None else found)
        if v.vertical_crs == vertical_crs
        and (format is None or v.format == format)
        and (resolution is None or v.label == resolution)
    )
    if not candidates:
        name = _PRODUCT_NAMES.get(product, product.upper())
        raise ValidationError(
            f"--vertical-crs wymagane dla {name} {country}: "
            f"{', '.join(_named_systems(found))}",
            option="vertical_crs",
            allowed=tuple(_named_systems(found)),
        )
    return candidates[0]


# =============================================================================
# CZ (plan B): rows of the route table and their messages
# =============================================================================

# Sheet systems of CZ variants in messages, with an example code.
_CZ_SYSTEM_TEXT = {
    "sm5": ("arkusze SM5 (S-JTSK)", "CTES96"),
    "tm33": ("kafle TM33 (ETRS89)", "760_5518"),
}


def cz_sheet_system(sheet: str) -> str:
    """``"sm5"``/``"tm33"``: the system of a CZ sheet code (variant ``systems``).

    Raises
    ------
    ValidationError
        A code outside the CZ systems.
    """
    sheet = sheet.strip()
    system = _CZ_SYSTEMS.get(detect_system(sheet).id)
    if system is None:
        raise ValidationError(
            f"Godlo '{sheet}' nie nalezy do zadnego systemu CZ (arkusz SM5, "
            "np. CTES96, albo kafel TM33, np. 302_5550)",
            option="sheet",
        )
    return system


def _model_name(variant: ProductVariant) -> str:
    return CZ_MODELS[variant.model][0] if variant.model in CZ_MODELS else "?"


def _cz_labels(found: tuple[ProductVariant, ...]) -> str:
    """``2m (DMR 5G), 5m (DMR 4G)``: labels with the model, by resolution."""
    named = {
        v.resolution_m: _model_name(v) for v in found if v.resolution_m is not None
    }
    return ", ".join(
        f"{resolution_label(value)} ({named[value]})" for value in sorted(named)
    )


def cz_resolution_text(product: str) -> str:
    """``2m (DMR 5G), 5m (DMR 4G)``: the CZ grid labels of a product."""
    return _cz_labels(variants(product=product, country="CZ"))


def cz_models() -> tuple[str, ...]:
    """Return the models of LAZ CZ (``--model``) in registry order."""
    return tuple(
        dict.fromkeys(
            v.model
            for v in variants(product="laz", country="CZ")
            if v.model is not None
        )
    )


def cz_model_text() -> str:
    """``dmr5g (teren, DMR 5G), ...``: the models of LAZ CZ (``--model``)."""
    return ", ".join(f"{model} ({CZ_MODELS[model][1]})" for model in cz_models())


def cz_variant_error(
    *,
    product: str,
    resolution: str | None,
    vertical_crs: str | None,
    system: str | None = None,
) -> ValidationError | None:
    """Return the error of a CZ raster choice (``None`` = it has a variant).

    ``system``: ``"sm5"``/``"tm33"`` of a sheet code, ``None`` for an area
    (a cutout of the ImageServer: any label of the product). An SM5 sheet
    may omit ``resolution`` when one label of the product has SM5 files.
    ``vertical_crs=None`` checks only what does not depend on the height
    system (the caller reports a missing ``--vertical-crs`` itself).
    ``option`` and ``allowed`` of the error: see ``variant_error``.
    """
    name = _PRODUCT_NAMES.get(product, product.upper())
    found = tuple(
        v for v in variants(product=product, country="CZ") if v.product != "laz"
    )
    if not found:
        return ValidationError(
            f"--product {product} nie ma wariantow rastrowych w CZ",
            option="product",
            allowed=tuple(
                dict.fromkeys(
                    v.product for v in variants(country="CZ") if v.product != "laz"
                )
            ),
        )
    on_sm5 = tuple(v for v in found if "sm5" in v.systems)
    sm5_labels = {v.label for v in on_sm5 if v.label is not None}
    if resolution is None:
        if system != "sm5" or len(sm5_labels) != 1:
            return ValidationError(
                f"--resolution wymagane dla {name} CZ: {_cz_labels(found)}",
                option="resolution",
                allowed=tuple(_sorted_labels(found)),
            )
    elif resolution not in {v.label for v in found}:
        return ValidationError(
            f"CZ nie ma rozdzielczosci {resolution} dla {name} - dostepne: "
            f"{_cz_labels(found)}",
            option="resolution",
            allowed=tuple(_sorted_labels(found)),
        )
    elif system == "sm5" and resolution not in sm5_labels:
        return ValidationError(
            f"Arkusze SM5 {name} CZ sa tylko w {_cz_labels(on_sm5)} - pomin "
            f"--resolution albo podaj {', '.join(_sorted_labels(on_sm5))}; "
            f"{resolution}: kafel "
            "TM33 (np. 302_5550) albo --bbox z --cutout",
            option="resolution",
            allowed=tuple(_sorted_labels(on_sm5)),
        )
    if vertical_crs is not None and vertical_crs not in {v.vertical_crs for v in found}:
        return ValidationError(
            f"{vertical_crs} nie jest dostepny dla CZ - dostepne: {CZ_VERTICAL_TEXT}",
            option="vertical_crs",
            allowed=tuple(_named_systems(found)),
        )
    return None


def find_cz_variant(
    *,
    product: str,
    resolution: str | None,
    vertical_crs: str,
    system: str,
) -> ProductVariant:
    """Return the route table row of a CZ raster sheet (decision 2 of plan B).

    ``resolution=None`` selects the only SM5 label of the product.

    Raises
    ------
    ValidationError
        The ``cz_variant_error`` of the choice.
    """
    error = cz_variant_error(
        product=product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    if error is not None:
        raise error
    return next(
        v
        for v in variants(
            product=product, country="CZ", vertical_crs=vertical_crs, system=system
        )
        if resolution is None or v.label == resolution
    )


def cz_laz_error(
    *, model: str | None, vertical_crs: str | None, system: str | None = None
) -> ValidationError | None:
    """Return the error of a LAZ CZ choice (``None`` = the choice has a variant).

    ``system``: ``"sm5"``/``"tm33"`` of a sheet code, ``None`` for an area
    (the height system decides the files). The files exist only in the pairs
    S-JTSK + Bpv and ETRS89 + EVRF2007; a point cloud is never transformed.
    ``vertical_crs=None`` checks only the model. ``option`` and ``allowed`` of
    the error: see ``variant_error``.
    """
    if model is None:
        return ValidationError(
            f"--model wymagane dla --product laz w CZ: {cz_model_text()}",
            option="model",
            allowed=cz_models(),
        )
    rows = variants(product="laz", country="CZ", model=model)
    if not rows:
        return ValidationError(
            f"--model {model!r}: nieznana wartosc - dostepne: {cz_model_text()}",
            option="model",
            allowed=cz_models(),
        )
    if vertical_crs is None:
        return None
    chosen = tuple(v for v in rows if v.vertical_crs == vertical_crs)
    if not chosen:
        return ValidationError(
            f"{vertical_crs} nie jest dostepny dla LAZ CZ - dostepne: "
            f"{CZ_LAZ_VERTICAL_TEXT}",
            option="vertical_crs",
            allowed=tuple(_named_systems(rows)),
        )
    if system is not None and not any(system in v.systems for v in chosen):
        native = _named_systems(tuple(v for v in rows if system in v.systems))
        other = chosen[0].systems[0]
        shown, _example = _CZ_SYSTEM_TEXT[system]
        alternative, example = _CZ_SYSTEM_TEXT[other]
        return ValidationError(
            f"LAZ CZ - {shown} sa tylko w {', '.join(native)}, podano "
            f"--vertical-crs {vertical_crs} (chmury punktow bez transformacji); "
            f"{vertical_crs}: {alternative}, np. {example}, albo obszar "
            "(--bbox/--geometry)",
            options=("vertical_crs", "sheet"),
        )
    return None


def find_cz_laz_variant(
    *, model: str | None, vertical_crs: str, system: str | None = None
) -> ProductVariant:
    """Return the LAZ CZ row of a model and height system.

    Raises
    ------
    ValidationError
        The ``cz_laz_error`` of the choice.
    """
    error = cz_laz_error(model=model, vertical_crs=vertical_crs, system=system)
    if error is not None:
        raise error
    return variants(
        product="laz", country="CZ", model=model, vertical_crs=vertical_crs
    )[0]
