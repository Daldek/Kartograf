"""Validation of the data choices of a ``download_data`` request (Z1).

Moved from the CLI: every rule that decides whether a request is valid lives
here, with the texts the CLI printed after ``Error:`` (they name the CLI
flags, because the CLI passes them 1:1 as ``ValidationError``). Values may be
plain (one value for every country of the request) or per country
(``{"pl": "1m", "cz": "2m"}``; the CLI parses ``pl=1m,cz=2m`` into it).
Nothing here touches the network.
"""

import functools
import re
from collections.abc import Iterable, Mapping, Sequence
from types import SimpleNamespace
from typing import cast

from kartograf.core.bbox import BBox, validate_bbox
from kartograf.core.sheet_parser import SheetParser, series_scale
from kartograf.download.arguments import (
    option_error,
    option_name,
    require_bool,
    require_int,
)
from kartograf.download.campaigns import validate_year_bounds
from kartograf.download.countries import BBOX_CRS_REMEDY
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import PRODUCT as CONTOURS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.cz_orto import cz_orto_sheet
from kartograf.download.orto_cutout import ORTO_CUTOUT_PL_ONLY, orto_cutout_error
from kartograf.exceptions import ParseError, ValidationError
from kartograf.messages import message, reason
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    coverage_choices,
    cutout_choice_error,
    image_directions,
    image_source,
    sheet_index,
    wcs_cutout_channels,
)
from kartograf.sources.descriptor import SheetIndexParams
from kartograf.sources.registry import all_sources, sources_for
from kartograf.sources.variants import (
    CZ_LAZ_VERTICAL_TEXT,
    CZ_VERTICAL_TEXT,
    FORMATS,
    UNKNOWN_VERTICAL,
    ProductVariant,
    cz_laz_error,
    cz_resolution_text,
    cz_variant_error,
    find_variant,
    labels_by_vertical_crs,
    variant_error,
    variants,
)

# Admissible values named in messages (also the CLI --help texts).
_PRODUCT_TEXT = {
    "nmt": "Numeryczny Model Terenu; PL i CZ",
    "nmpt": "Numeryczny Model Pokrycia Terenu; PL i CZ",
    "orto": "ortofotomapa RGB; PL i CZ",
    "laz": "chmura punktow LIDAR; PL i CZ",
    CONTOURS: "warstwice ZABAGED - wektor 2D, arkusze SM5, SHP albo DGN; CZ",
    "intensity": "obrazy intensywnosci LIDAR, 1 pasmo 0,25 m; PL",
    "true-orto": "prawdziwa ortofotomapa (true orto) wybranych miast, 0,05 m; PL",
    "oblique-orto": (
        "ortofotomapa ukosna wybranych miast, arkusz = 4 pliki kierunkow n, e, s, w; PL"
    ),
}


def product_choices(products: Iterable[str] = tuple(_PRODUCT_TEXT)) -> str:
    """Return the products named in messages and ``--help`` texts.

    ``nmt (...), nmpt (...)``: products named in messages and --help texts
    (a CLI group names only its own products, ADR-039).
    """
    return ", ".join(f"{product} ({_PRODUCT_TEXT[product]})" for product in products)


PRODUCT_CHOICES = product_choices()
# Products of the CLI groups (ADR-039): ``elevation download`` and ``imagery
# download`` offer only these; a new product of a group is added here.
ELEVATION_PRODUCTS: tuple[str, ...] = ("nmt", "nmpt", "laz", CONTOURS)
IMAGERY_PRODUCTS: tuple[str, ...] = ("orto", "intensity", "true-orto", "oblique-orto")


def require_product(product: str | None, products: Sequence[str]) -> None:
    """``product`` of a group command: one of the group's ``products``.

    Raises
    ------
    ValidationError
        Missing product (the message names only the group's products) or a
        product of another group.
    """
    if product is None:
        raise ValidationError(
            f"--product wymagane: {product_choices(products)}",
            option="product",
            allowed=tuple(products),
        )
    if product not in products:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: "
            f"{product_choices(products)}",
            option="product",
            allowed=tuple(products),
        )


def product_directory(product: str) -> str:
    """Return the top directory of the files of a product in the store.

    Top directory of the files of a ``download_data`` product in the store
    (``nmt``, ``orto``): the first element of its sources' storage segments.
    """
    tops = dict.fromkeys(
        source.storage_subdir.split("/", 1)[0]
        for source in sources_for(product=product)
    )
    return "|".join(tops) or product


_COUNTRY_TEXT = {
    "pl": "pl (GUGiK)",
    "cz": "cz (CUZK)",
    "auto": "auto (kraje wg prostokatnych obwiedni PL i CZ; obszar w obu krajach "
    "daje osobne pliki per kraj)",
}


def country_choices(codes: Iterable[str] = tuple(_COUNTRY_TEXT)) -> str:
    """Return the ``--country`` values of a command as text.

    ``pl (GUGiK), cz (CUZK), auto (...)``: the ``--country`` values of a
    command (a CLI group names only the countries of its products).
    """
    return ", ".join(_COUNTRY_TEXT[code] for code in codes)


COUNTRY_CHOICES = country_choices()
_VERTICAL_CRS_TEXT = {
    "EVRF2007": "PL-EVRF2007-NH, uklad obowiazujacy",
    "KRON86": "PL-KRON86-NH, uklad historyczny",
}
# Products with sheet variants of the registry (resolution and --format).
_SHEET_PRODUCTS = ("nmt", "nmpt")


def _image_index(product: object) -> SheetIndexParams | None:
    """Sheet index of an image product (orthophotomap family, plan E1)."""
    source = image_source(product)
    return sheet_index(source.key) if source is not None else None


def image_cutout_key(product: object) -> str | None:
    """Return the descriptor key of the WCS cutout of an image product.

    Descriptor key of the WCS cutout of an image product (``orto``,
    ``true-orto``); ``None`` for a product without one.
    """
    source = image_source(product)
    if source is None or not wcs_cutout_channels(source.key):
        return None
    return source.key


def cutout_products() -> tuple[str, ...]:
    """Return the products with a PL cutout (``--cutout``).

    Products with a PL cutout (``--cutout``): the grids and the images with
    a WCS cutout channel, registry order.
    """
    images = (p for p in IMAGERY_PRODUCTS if image_cutout_key(p) is not None)
    return (*_SHEET_PRODUCTS, *images)


def _or_list(values: Sequence[str]) -> str:
    """Join the values as ``a, b albo c``."""
    return (
        f"{', '.join(values[:-1])} albo {values[-1]}" if len(values) > 1 else values[0]
    )


def resolution_text(country: str = "PL") -> str:
    """Return the grid resolutions of every sheet product as text.

    Grid resolutions (``--resolution``) of every sheet product, from the
    variant registry: ``NMT (EVRF2007: 0.15m, ...; KRON86: 0.5m, 1m), NMPT (...)``.
    """
    parts = []
    for product in _SHEET_PRODUCTS:
        grids = tuple(
            v for v in variants(product=product, country=country) if not v.source_file
        )
        if grids:
            parts.append(f"{product.upper()} ({labels_by_vertical_crs(grids)})")
    return ", ".join(parts)


def vertical_crs_values(
    country: str = "PL", product: str | None = None
) -> tuple[str, ...]:
    """Return the height systems of the variants of a country.

    Height systems of the variants of a country (``--vertical-crs`` values),
    sorted; a variant without one takes no flag.
    """
    return tuple(
        sorted(
            {
                v.vertical_crs
                for v in variants(country=country, product=product)
                if v.vertical_crs
            }
        )
    )


def vertical_crs_text(country: str = "PL") -> str:
    """Return the height systems of the country's variants as help text.

    Height systems of the country's variants (``--vertical-crs``; a
    variant without one takes no flag).
    """
    return ", ".join(
        f"{name} ({_VERTICAL_CRS_TEXT[name]})" if name in _VERTICAL_CRS_TEXT else name
        for name in vertical_crs_values(country)
    )


def format_text(country: str = "PL") -> str:
    """File formats of the sheet products (``--format``), registry order."""
    present = {
        v.format
        for product in _SHEET_PRODUCTS
        for v in variants(product=product, country=country)
    }
    return ", ".join(
        f"{f.token} ({f.description})" for f in FORMATS if f.token in present
    )


def cz_resolution_help() -> str:
    """Return the CZ grid labels per product as help text.

    CZ grid labels per product with their CUZK model and the labels of the
    SM5 sheets (variant registry): ``NMT: 2m (DMR 5G), 5m (DMR 4G); ...``.
    """
    parts = []
    sm5 = []
    for product in _SHEET_PRODUCTS:
        text = cz_resolution_text(product)
        if text:
            parts.append(f"{product.upper()}: {text}")
        labels = dict.fromkeys(
            v.label
            for v in variants(product=product, country="CZ", system="sm5")
            if v.label is not None
        )
        if labels:
            sm5.append(f"{product.upper()} {', '.join(labels)}")
    return f"{'; '.join(parts)}; arkusz SM5 tylko {', '.join(sm5)} (mozna pominac)"


SHEET_SYSTEM_CHOICES = (
    "1992 (godla PL-1992, arkusze 1:10000), 2000 (godla PL-2000, strefy "
    "EPSG:2176-2179; wymaga --scale)"
)
SCALE_2000_CHOICES = (
    "1:5000, 1:2000, 1:1000, 1:500 (GUGiK publikuje arkusze PL-2000 najczesciej "
    "w 1:2000, takze w 1:1000 i 1:5000)"
)
# PL-2000 sheet scales GUGiK can publish below the 1:10000 frame.
SCALES_2000 = ("1:5000", "1:2000", "1:1000", "1:500")
BBOX_CRS_CHOICES = (
    "EPSG:2180",
    "EPSG:4326",
    "EPSG:2176",
    "EPSG:2177",
    "EPSG:2178",
    "EPSG:2179",
    "EPSG:5514",
    "EPSG:3045",
)


BBOX_EXPECTED = message("options.expected_min_x_min_y_max")
# Limits of an EPSG:4326 bbox in degrees (``validate_request_bbox``).
_LON_LIMIT = 180.0
_LAT_LIMIT = 90.0
_PRODUCTS = tuple(_PRODUCT_TEXT)
# Keys of a per-country value (``pl=1m,cz=2m``) and the ``--country`` values
# of a data request (also the CLI choices).
COUNTRY_KEYS = ("pl", "cz")
COUNTRIES = (*COUNTRY_KEYS, "auto")
_SHEET_SYSTEMS = ("1992", "2000")

PerCountry = str | Mapping[str, str] | None


def country_value(raw: PerCountry, code: str) -> str | None:
    """Value of a plain or per-country choice for country ``code`` (PL/CZ)."""
    if raw is None or isinstance(raw, str):
        return raw
    for key, value in raw.items():
        if key.strip().lower() == code.lower():
            return value
    return None


def check_per_country(raw: PerCountry, flag: str) -> None:
    """``ValidationError`` for choices other than a plain string or valid mapping."""
    if raw is None or isinstance(raw, str):
        return
    if isinstance(raw, Mapping):
        shown = ",".join(f"{k}={v}" for k, v in raw.items())
        keys = [k.strip().lower() for k in raw if isinstance(k, str)]
        valid = (
            len(keys) == len(raw)
            and all(k in COUNTRY_KEYS for k in keys)
            and len(set(keys)) == len(keys)
            and all(isinstance(v, str) and v.strip() for v in raw.values())
        )
    else:
        shown = str(raw)
        valid = False
    if not valid:
        raise ValidationError(
            f"{flag}: nieprawidlowa wartosc {shown!r} - podaj jedna wartosc dla "
            f"kazdego kraju zadania albo pary kraj=wartosc rozdzielone "
            f"przecinkami (kraje: pl, cz), np. {flag} pl=...,cz=...",
            option=option_name(flag),
        )


def _per_country_hint(raw: PerCountry, flag: str, countries: tuple[str, ...]) -> str:
    """Suffix suggesting the per-country form for a request spanning PL and CZ."""
    if len(countries) < 2:
        return ""
    return f" (zadanie PL+CZ: wartosci per kraj, np. {flag} pl=...,cz=...)"


def _format_of(task: SimpleNamespace) -> str | None:
    """``task.format`` (``None`` = the product format, ASC grids)."""
    return getattr(task, "format", None)


def pl_file_variant(task: SimpleNamespace) -> ProductVariant | None:
    """Select the PL variant published as voivodeship files.

    The PL variant of the request published as voivodeship files of an
    ATOM feed (no sheet index: NMT 100 m, plan E1), ``None`` for the sheet
    variants. Chosen by the product, the PL resolution and the format
    (``None`` or the variant's own); nothing is validated here.
    """
    resolution = country_value(task.resolution, "PL")
    if task.product not in _SHEET_PRODUCTS or not isinstance(resolution, str):
        return None
    fmt = _format_of(task)
    return next(
        (
            v
            for v in variants(product=task.product, country="PL", resolution=resolution)
            if v.index_ref is None and fmt in (None, v.format)
        ),
        None,
    )


# Choices of the sheet tracks a file variant has none of (flag, attribute).
_SHEET_CHOICES = (
    ("--sheet-system", "sheet_system"),
    ("--scale", "scale"),
    ("--year", "year"),
    ("--min-year", "min_year"),
    ("--max-year", "max_year"),
    ("--all-campaigns", "all_campaigns"),
    ("--full-sheet", "full_sheet"),
    ("--cutout", "cutout"),
    ("--horizontal-crs", "horizontal_crs"),
    ("--min-density", "min_density"),
)


def _with_suffix(error: ValidationError, suffix: str) -> ValidationError:
    """``error`` with ``suffix`` (the per-country hint) after its text."""
    if not suffix:
        return error
    return ValidationError(
        f"{error}{suffix}",
        option=error.option,
        options=error.options,
        allowed=error.allowed,
        hint=error.hint,
    )


def _file_variant_error(
    task: SimpleNamespace, variant: ProductVariant
) -> ValidationError | None:
    """Return the error of the choices a voivodeship file variant does not take."""
    label = variant.label or ""
    shown = f"{variant.product.upper()} {label.removesuffix('m')} m"
    reason = f"{shown} to pliki wojewodztw z ATOM - bez arkuszy, lotow i wycinka"
    for flag, name in _SHEET_CHOICES:
        value = getattr(task, name)
        if value is not None and value is not False:
            return option_error(
                f"{flag} nie dotyczy --resolution {label}: {reason}", name, "resolution"
            )
    if task.country == "cz":
        return option_error(
            f"--country cz nie dotyczy --resolution {label} (tylko PL): {reason}",
            "country",
            "resolution",
        )
    if (
        country_value(task.vertical_crs, "PL") is not None
        and variant.vertical_crs is None
    ):
        return option_error(
            f"--vertical-crs nie dotyczy --resolution {label}: {UNKNOWN_VERTICAL} - "
            f"GUGiK nie deklaruje ukladu wysokosci {shown}; pomin --vertical-crs",
            "vertical_crs",
            "resolution",
        )
    return None


def pl_option_error(
    task: SimpleNamespace,
    *,
    code_system: str | None = None,
    code_scale: str | None = None,
    countries: tuple[str, ...] = ("PL",),
) -> ValidationError | None:
    """Return the error of the PL data choices of the request (``None`` = valid).

    ``code_system``/``code_scale`` describe a sheet request (sheet system and
    scale of the code); ``None`` = area request (bbox/geometry). NMT/NMPT
    choices are checked against the variant registry
    (``kartograf.sources.variants``): format, resolution, height system. A
    voivodeship file variant (``pl_file_variant``) was checked by
    ``validate_request`` already. ``option``, ``options`` and ``allowed`` of
    the error name the arguments and the values the text lists.
    """
    if pl_file_variant(task) is not None:
        return None
    product = task.product
    resolution = country_value(task.resolution, "PL")
    vertical_crs = country_value(task.vertical_crs, "PL")
    fmt = _format_of(task)
    cutout = task.cutout
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)
    source_file = fmt is not None and fmt != "ASC"
    if product == "laz" and resolution is not None:
        return option_error(
            "--resolution nie dotyczy LAZ - chmura punktow nie ma siatki; pomin "
            "--resolution",
            "resolution",
        )

    if product in _SHEET_PRODUCTS:
        if cutout:
            if source_file:
                return option_error(
                    f"--cutout dziala tylko z siatka ASC 1m (wycinek z WCS GUGiK); "
                    f"--format {fmt} to pliki zrodlowe arkuszy - pomin --cutout",
                    "cutout",
                    "format",
                )
            if resolution not in (None, "1m"):
                return option_error(
                    f"wycinki PL (--cutout) sa tylko 1 m (WCS GUGiK); arkusze "
                    f"{resolution}: pomin --cutout (arkusze bez --cutout); "
                    "wycinek: --resolution 1m albo pomin --resolution",
                    "cutout",
                    "resolution",
                )
        else:
            error = variant_error(
                product=product,
                country="PL",
                resolution=resolution,
                vertical_crs=None,
                format=fmt,
            )
            if error is not None:
                return _with_suffix(error, res_hint)
    elif fmt is not None:
        return option_error(
            f"--format dotyczy tylko --product nmt i nmpt (PL) oraz {CONTOURS} "
            f"(CZ), podano --product {product} - pomin --format",
            "format",
        )

    index = _image_index(product)
    if index is not None:
        if vertical_crs is not None:
            noun = "ortofotomapa" if product == "orto" else "obraz"
            return option_error(
                f"--vertical-crs nie dotyczy --product {product} "
                f"({noun} nie ma ukladu pionowego)",
                "vertical_crs",
            )
    elif vertical_crs is None:
        return ValidationError(
            f"--vertical-crs wymagane dla --product {product} (PL): "
            f"{vertical_crs_text()}{vcrs_hint}",
            option="vertical_crs",
            allowed=vertical_crs_values(),
        )
    elif vertical_crs not in vertical_crs_values():
        return ValidationError(
            f"{vertical_crs} nie jest ukladem wysokosci PL - dostepne: "
            f"{vertical_crs_text()}{vcrs_hint}",
            option="vertical_crs",
            allowed=vertical_crs_values(),
        )
    elif product in _SHEET_PRODUCTS:
        error = variant_error(
            product=product,
            country="PL",
            resolution="1m" if cutout and resolution is None else resolution,
            vertical_crs=vertical_crs,
            format=fmt,
        )
        if error is not None:
            return _with_suffix(error, vcrs_hint)

    if product == "laz":  # per-tile system from WFS, no sheet scale
        given = [
            (flag, name)
            for flag, name, value in (
                ("--sheet-system", "sheet_system", task.sheet_system),
                ("--scale", "scale", task.scale),
            )
            if value is not None
        ]
        if given:
            shown = " i ".join(flag for flag, _ in given)
            verb = "nie dotycza" if len(given) > 1 else "nie dotyczy"
            return option_error(
                f"{shown} {verb} LAZ PL - uklad kazdego kafla pochodzi "
                f"z WFS GUGiK; pomin {shown}",
                *(name for _, name in given),
            )
        return None
    sheet_system = task.sheet_system
    scale = task.scale
    systems = index.systems if index is not None else _SHEET_SYSTEMS
    if cutout:
        if sheet_system not in (None, "1992"):
            return option_error(
                "--cutout nie dziala z --sheet-system 2000 - bbox wielostrefowy "
                "dalby arkusze w roznych CRS (2176-2179); wycinek: --sheet-system "
                "1992 albo pomin --sheet-system",
                "cutout",
                "sheet_system",
            )
        return None
    if source_file and scale is not None:
        return option_error(
            f"--scale nie dotyczy --format {fmt}: arkusze archiwum (rozne skale) "
            "wynikaja ze skorowidza GUGiK - pomin --scale",
            "scale",
            "format",
        )
    only = ", ".join(f"PL-{system}" for system in systems)
    if code_system is None:
        if sheet_system is None:
            if len(systems) == 1:
                effective = systems[0]  # one admissible value may be omitted
            else:
                cutout_hint = (
                    "; jeden wycinek zamiast arkuszy: --cutout"
                    if product in cutout_products()
                    else ""
                )
                return ValidationError(
                    f"--sheet-system wymagane dla --bbox/--geometry w PL: "
                    f"{SHEET_SYSTEM_CHOICES}{cutout_hint}",
                    option="sheet_system",
                    allowed=tuple(systems),
                )
        elif sheet_system not in systems:
            return ValidationError(
                f"--sheet-system {sheet_system} nie dotyczy --product {product}: "
                f"GUGiK publikuje arkusze tylko {only} - pomin --sheet-system",
                option="sheet_system",
                allowed=tuple(systems),
            )
        else:
            effective = sheet_system
    elif code_system not in systems:
        return option_error(
            f"--product {product}: GUGiK publikuje arkusze tylko {only} - godlo "
            f"{task.sheet} to PL-{code_system}",
            "product",
            "sheet",
        )
    elif sheet_system is not None and sheet_system != code_system:
        return option_error(
            f"--sheet-system {sheet_system} nie zgadza sie z godlem {task.sheet} "
            f"(PL-{code_system}): uklad arkuszy wynika z godla - pomin "
            "--sheet-system",
            "sheet_system",
            "sheet",
        )
    else:
        effective = code_system
    if source_file:
        return None  # archive sheets come from the index (any scale)
    if effective == "1992":
        if scale is not None:
            parts = index.sheet_parts if index is not None else 7
            label = series_scale(parts)
            return option_error(
                "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 "
                f"tylko w {label} (godlo {parts}-czlonowe), a grubsze godlo rozwija "
                f"sie do {label} samo - pomin --scale",
                "scale",
            )
        return None
    if scale is None and (code_system is None or code_scale == "1:10000"):
        return ValidationError(
            f"--scale wymagane dla arkuszy PL-2000: {SCALE_2000_CHOICES}",
            option="scale",
            allowed=SCALES_2000,
        )
    if scale is not None and scale not in SCALES_2000:
        return ValidationError(
            f"Nieznana skala PL-2000 {scale} - dostepne: {SCALE_2000_CHOICES}",
            option="scale",
            allowed=SCALES_2000,
        )
    return None


def cz_option_error(
    task: SimpleNamespace,
    *,
    system: str | None = None,
    countries: tuple[str, ...] = ("CZ",),
) -> ValidationError | None:
    """Return the error of the CZ data choices.

    The error of the CZ data choices (``None`` = valid), from the variant
    registry (``cz_variant_error``).

    ``system``: ``"sm5"``/``"tm33"`` of a sheet code, ``None`` = an area (a
    cutout of the ImageServer, any label of the product).
    """
    resolution = country_value(task.resolution, "CZ")
    vertical_crs = country_value(task.vertical_crs, "CZ")
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)
    if _format_of(task) is not None:
        return option_error(
            f"--format dotyczy w CZ tylko --product {CONTOURS} (warstwice); "
            f"{task.product.upper()} CZ to pliki CUZK bez wyboru formatu - pomin "
            "--format",
            "format",
        )
    if task.product == "laz":
        if task.resolution is not None:
            return option_error(
                "--resolution nie dotyczy LAZ CZ - pomin --resolution", "resolution"
            )
        if task.min_density is not None:
            return option_error(
                "--min-density dotyczy tylko LAZ PL - pomin --min-density",
                "min_density",
            )
        if task.sheet_system is not None and "PL" not in countries:
            return option_error(
                "--sheet-system dotyczy tylko PL (godla CZ wykrywane wzorcem)",
                "sheet_system",
            )
        error = cz_laz_error(model=task.model, vertical_crs=vertical_crs, system=system)
        if error is not None:
            return _with_suffix(error, vcrs_hint)
        if vertical_crs is None:
            return ValidationError(
                f"--vertical-crs wymagane dla LAZ CZ: "
                f"{CZ_LAZ_VERTICAL_TEXT}{vcrs_hint}",
                option="vertical_crs",
                allowed=vertical_crs_values("CZ", "laz"),
            )
        return None
    error = cz_variant_error(
        product=task.product, resolution=resolution, vertical_crs=None, system=system
    )
    if error is not None:
        return _with_suffix(error, res_hint)
    if vertical_crs is None:
        return ValidationError(
            f"--vertical-crs wymagane dla {task.product.upper()} CZ: "
            f"{CZ_VERTICAL_TEXT}{vcrs_hint}",
            option="vertical_crs",
            allowed=vertical_crs_values("CZ", task.product),
        )
    error = cz_variant_error(
        product=task.product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    if error is not None:
        return _with_suffix(error, vcrs_hint)
    if "PL" not in countries and task.sheet_system is not None:
        return option_error(
            "--sheet-system dotyczy tylko PL (godla CZ wykrywane wzorcem)",
            "sheet_system",
        )
    return None


def _contours_error(task: SimpleNamespace) -> ValidationError | None:
    """Return the error of a CZ contours request.

    The error of a CZ contours request (``None`` = valid): vector SM5
    sheets take ``--format`` (required, values of the registry) and the
    height system of their files (one value: may be omitted); no grid,
    flight, cutout or view choice.
    """
    if task.product != CONTOURS:
        return None
    reason = "warstwice to arkusze SM5 (wektor) - bez rozdzielczosci, lotow i wycinka"
    for flag, name in (
        ("--resolution", "resolution"),
        *_SHEET_CHOICES,
        ("--coverage", "coverage"),
        ("--direction", "direction"),
    ):
        value = getattr(task, name)
        if value is not None and value is not False:
            return option_error(
                f"{flag} nie dotyczy --product {CONTOURS}: {reason}", name
            )
    formats = contours_formats()
    fmt = _format_of(task)
    if fmt is None:
        return ValidationError(
            f"--format wymagane dla --product {CONTOURS}: {', '.join(formats)}",
            option="format",
            allowed=formats,
        )
    if fmt not in formats:
        return ValidationError(
            f"--format {fmt!r}: nieznana wartosc dla --product {CONTOURS} - "
            f"dostepne: {', '.join(formats)}",
            option="format",
            allowed=formats,
        )
    heights = vertical_crs_values("CZ", CONTOURS)
    vertical_crs = country_value(task.vertical_crs, "CZ")
    if vertical_crs is not None and vertical_crs not in heights:
        return ValidationError(
            f"--vertical-crs {vertical_crs} nie dotyczy --product {CONTOURS}: "
            f"warstwice ZABAGED maja wysokosci {', '.join(heights)} (mozna pominac "
            "--vertical-crs)",
            option="vertical_crs",
            allowed=heights,
        )
    return None


def cz_orto_option_error(
    task: SimpleNamespace, *, countries: tuple[str, ...] = ("CZ",)
) -> ValidationError | None:
    """Return the error of the CZ orthophoto choices (``None`` = valid; ADR-042 D13).

    CUZK publishes only the current release of an SM5 sheet (archival
    orthophotos are paid - out of scope) as a JPEG with world files: no
    year, campaign, sheet system or scale choice (a request with PL applies
    them to its PL part), no height system or format (``--resolution`` of
    orthophoto sheets is rejected for both countries by ``validate_request``).
    """
    if task.sheet is not None:
        try:
            cz_orto_sheet(task.sheet)
        except ValidationError as e:
            return e
    if "PL" not in countries:
        flag = next(
            (
                name
                for name, given in (
                    ("--year", task.year is not None),
                    ("--min-year", task.year is None and task.min_year is not None),
                    ("--max-year", task.year is None and task.max_year is not None),
                    ("--all-campaigns", task.all_campaigns),
                    ("--full-sheet", task.full_sheet),
                )
                if given
            ),
            None,
        )
        if flag is not None:
            return option_error(
                f"{flag} dotyczy tylko PL - CUZK publikuje tylko aktualny rocznik "
                "arkusza ortofoto CZ (archiwalne ortofoto CUZK sa platne, poza "
                "zakresem)",
                option_name(flag),
            )
        if task.sheet_system is not None:
            return option_error(
                "--sheet-system dotyczy tylko PL - ortofoto CZ to arkusze SM5 "
                "(godlo rozpoznawane wzorcem, arkusze obszaru z indeksu SM5)",
                "sheet_system",
            )
        if task.scale is not None:
            return option_error(
                "--scale dotyczy tylko PL - ortofoto CZ to arkusze SM5 w jednej "
                "skali (1:5000)",
                "scale",
            )
    if country_value(task.vertical_crs, "CZ") is not None:
        return option_error(
            "--vertical-crs nie dotyczy --product orto "
            "(ortofotomapa nie ma ukladu pionowego)",
            "vertical_crs",
        )
    if _format_of(task) is not None:
        return option_error(
            "--format nie dotyczy ortofoto CZ (pliki CUZK: JPEG i JGW bez "
            "konwersji) - pomin --format",
            "format",
        )
    return None


def require_cz_cutout(task: SimpleNamespace, countries: tuple[str, ...]) -> None:
    """Require a cutout for CZ raster areas.

    CZ raster areas require cutout; CZ LAZ and orthophoto areas use the
    indexed sheets.
    """
    if (
        task.product in ("laz", "orto", CONTOURS)
        or task.sheet is not None
        or "CZ" not in countries
        or task.cutout
    ):
        return
    if "PL" in countries:
        raise option_error(
            "obszar siega CZ, a CUZK daje dla obszaru tylko jeden wycinek - "
            "dodaj --cutout --horizontal-crs <uklad> (czesc PL tez bedzie "
            "wycinkiem z WCS GUGiK) albo uzyj --country pl (tylko arkusze PL)",
            "cutout",
            "horizontal_crs",
        )
    raise option_error(
        "obszar CZ (CUZK) jest pobierany tylko jako jeden wycinek - dodaj "
        "--cutout --horizontal-crs <uklad> (np. EPSG:5514, uklad natywny CUZK)",
        "cutout",
        "horizontal_crs",
    )


# Enumerated values given in any case (UX-11): the spelling of the registry
# when the value is one of its values in another case; anything else stays as
# given, so a message names it as the user wrote it.
# A CRS code ``<authority>:<code>`` (``epsg:2180``); authorities are upper case.
_CRS_CODE = re.compile(r"[A-Za-z]+:[0-9A-Za-z]+")


def _spelling[T](value: T, known: Mapping[str, str]) -> T:
    """Return ``value`` in the registry spelling.

    ``value`` as ``known[value.lower()]`` (``known``: lower case -> registry
    spelling); a value of another type or not known unchanged.
    """
    if not isinstance(value, str):
        return value
    return cast(T, known.get(value.strip().lower(), value))


def canonical_country[T](value: T) -> T:
    """``PL`` -> ``pl``, ``Auto`` -> ``auto`` (``--country``)."""
    return _spelling(value, {code: code for code in COUNTRIES})


@functools.cache
def _formats() -> dict[str, str]:
    """Map lower case to the registry spelling of every source file format.

    Lower case -> registry spelling of every file format a source offers
    (variants of the sheet products, package variants and channel choices).
    """
    found: dict[str, str] = {}
    for source in all_sources():
        for variant in source.variants:
            found.setdefault(variant.format.lower(), variant.format)
        for channel in source.channels:
            params = channel.params
            choices = [dict(getattr(params, "choice", ()))]
            choices += [dict(v.choice) for v in getattr(params, "variants", ())]
            for choice in choices:
                fmt = choice.get("format")
                if fmt is not None:
                    found.setdefault(fmt.lower(), fmt)
    return found


def canonical_format[T](value: T) -> T:
    """``shp`` -> ``SHP``, ``ascii-nmt`` -> ``ASCII-NMT`` (``--format``)."""
    return _spelling(value, _formats())


def canonical_crs[T](value: T) -> T:
    """Return a CRS code with an upper case authority.

    ``epsg:2180`` -> ``EPSG:2180``: a CRS code with an upper case authority
    (``--bbox-crs``, ``--horizontal-crs``); not a CRS code: unchanged.
    """
    if isinstance(value, str) and _CRS_CODE.fullmatch(value.strip()):
        return cast(T, value.strip().upper())
    return value


@functools.cache
def _vertical_names() -> dict[str, str]:
    """Lower case -> registry spelling of every height system."""
    names = {v.vertical_crs for v in variants() if v.vertical_crs}
    return {name.lower(): name for name in names}


def canonical_vertical_crs[T](value: T) -> T:
    """Return a height system in the spelling of the variant registry.

    ``evrf2007`` -> ``EVRF2007``, ``BPV`` -> ``Bpv``: a height system (plain
    or per country) in the spelling of the variant registry.
    """
    if isinstance(value, Mapping):
        names = _vertical_names()
        return cast(T, {key: _spelling(name, names) for key, name in value.items()})
    return _spelling(value, _vertical_names())


def canonical_bbox[T](bbox: T) -> T:
    """Return a ``BBox`` with its CRS code in the upper case spelling.

    A ``BBox`` with its CRS code in the upper case spelling
    (``epsg:5514`` = ``EPSG:5514``); any other value unchanged.
    """
    if isinstance(bbox, BBox):
        return cast(T, bbox._replace(crs=canonical_crs(bbox.crs)))
    return bbox


def validate_request_bbox(bbox: BBox) -> BBox:
    """Validate parsed bbox coordinates and return the normalized bbox.

    Validate parsed bbox coordinates with the same text for CLI and API;
    returns the bbox with its CRS code in the registry spelling
    (``epsg:2180`` = ``EPSG:2180``) - callers go on with it.

    The one check of every ``--bbox`` (a command of any group, before any
    request): a supported CRS, finite numbers, ``min < max`` on both axes
    (a point or a line has no area; ``core.bbox.validate_bbox`` allows it for
    the sheet finder) and, in EPSG:4326, a longitude within +-180 and a
    latitude within +-90 - metres given as degrees (``--bbox-crs`` forgotten)
    or swapped axes would reach the sources as ``inf``/``nan``.
    """
    bbox = canonical_bbox(bbox)
    if bbox.crs not in BBOX_CRS_CHOICES:
        raise ValidationError(
            message(
                "options.invalid_bbox_unsupported_crs",
                crs=bbox.crs,
                bbox_crs_choices=", ".join(BBOX_CRS_CHOICES),
            ),
            option="bbox",
            allowed=BBOX_CRS_CHOICES,
        )
    # CLI numbers are floats; library callers may use ints for the same bbox.
    normalized = BBox(
        float(bbox.min_x),
        float(bbox.min_y),
        float(bbox.max_x),
        float(bbox.max_y),
        bbox.crs,
    )
    try:
        validate_bbox(normalized)
    except ValidationError as e:
        raise ValidationError(
            message(
                "kinds.invalid_bbox", reason=reason(e), bbox_expected=BBOX_EXPECTED
            ),
            option="bbox",
        ) from e
    coords = (normalized.min_x, normalized.min_y, normalized.max_x, normalized.max_y)
    if normalized.min_x == normalized.max_x or normalized.min_y == normalized.max_y:
        raise ValidationError(
            message(
                "options.invalid_bbox_bbox_zero_area",
                coords=coords,
                bbox_expected=BBOX_EXPECTED,
            ),
            option="bbox",
        )
    if normalized.crs == "EPSG:4326" and (
        max(abs(normalized.min_x), abs(normalized.max_x)) > _LON_LIMIT
        or max(abs(normalized.min_y), abs(normalized.max_y)) > _LAT_LIMIT
    ):
        raise ValidationError(
            message(
                "options.invalid_bbox_coordinates_lie_outside",
                coords=coords,
                bbox_crs_remedy=BBOX_CRS_REMEDY,
                bbox_expected=BBOX_EXPECTED,
            ),
            option="bbox",
            hint=message(
                "options.bbox_crs_remedy_hint", bbox_crs_remedy=BBOX_CRS_REMEDY
            ),
        )
    return bbox


def geometry_area_error(envelope: BBox, what: str) -> ValidationError:
    """Build the refusal of a ``--geometry`` without an area.

    The refusal of a ``--geometry`` without an area (``option="geometry"``):
    ``what`` is the track that needs one (``wycinek (--cutout)``).
    """
    coords = tuple(
        float(value)
        for value in (envelope.min_x, envelope.min_y, envelope.max_x, envelope.max_y)
    )
    return ValidationError(
        "--geometry: obwiednia obiektow ma zerowa powierzchnie (punkt albo linia "
        f"rownolegla do osi), {coords} w {envelope.crs}; {what} wymaga obszaru - "
        "podaj wielobok albo --bbox o dodatniej powierzchni",
        option="geometry",
    )


def require_geometry_area(envelope: BBox, what: str) -> None:
    """Require that the envelope of a ``--geometry`` has an area.

    The envelope of a ``--geometry`` has an area, for the tracks that cut,
    select tiles of or measure the AREA (``what``: a cutout, LAZ tiles, HSG,
    the availability report). The tracks that pick the sheets, units or pixels
    a point lies in do not call it - a point is a valid ``--geometry`` there
    (``--bbox`` of zero area is refused everywhere: ``validate_request_bbox``).

    Raises
    ------
    ValidationError
        ``min == max`` on an axis (``option="geometry"``).
    """
    if envelope.min_x == envelope.max_x or envelope.min_y == envelope.max_y:
        raise geometry_area_error(envelope, what)


def validate_area_choice(
    sheet: str | None,
    bbox: BBox | None,
    geometry: object | None,
    layer: object | None = None,
) -> None:
    """Check the area choice of a request without network access.

    Exactly one area choice, a valid bbox and ``layer`` only with
    ``geometry`` (texts shared by every command taking
    ``--sheet/--bbox/--geometry``; no network).
    """
    # the CLI parses --bbox before anything else: the same first error
    if bbox is not None:
        validate_request_bbox(bbox)
    given = tuple(
        name
        for name, value in (("sheet", sheet), ("bbox", bbox), ("geometry", geometry))
        if value is not None
    )
    if len(given) > 1:
        raise ValidationError(
            "Podaj dokladnie jeden wybor obszaru: --sheet, --bbox albo --geometry",
            options=given,
        )
    if not given:
        raise ValidationError(
            "Podaj wybor obszaru: --sheet, --bbox albo --geometry",
            options=("sheet", "bbox", "geometry"),
        )
    check_layer(layer, geometry)


def check_layer(layer: object, geometry: object, *, landcover: bool = False) -> None:
    """Check that ``layer`` is used only together with ``geometry``.

    ``layer`` names a layer of the ``geometry`` file; without a geometry
    file it would be ignored. ``landcover``: the message points to
    ``--layers`` (the data layers of BDOT10k and BDOO).

    Raises
    ------
    ValidationError
        ``layer`` without ``geometry``.
    """
    if layer is not None and geometry is None:
        hint = "; warstwy danych BDOT10k i BDOO wybiera --layers" if landcover else ""
        raise ValidationError(
            f"--layer dotyczy tylko --geometry (warstwa pliku GPKG z obszarem){hint}",
            options=("layer", "geometry"),
        )


def parse_sheet(sheet: str) -> SheetParser:
    """``SheetParser`` of the ``sheet`` argument of a command-level function.

    Raises
    ------
    ParseError
        A malformed code; its ``option`` is ``"sheet"``.
    """
    try:
        return SheetParser(sheet)
    except ParseError as e:
        e.option = "sheet"
        raise


def store_files(directories: Iterable[str]) -> str:
    """Return the text naming where a store command writes.

    ``pliki w <KATALOG>/nmt|nmpt/...``: where a store command writes, by the
    top directories of its files (``nmt``, ``boundaries``; ``a|b`` values are
    split) - one text for the ``--output`` help and its missing-value error.
    """
    tops = dict.fromkeys(top for found in directories for top in found.split("|"))
    return f"pliki w <KATALOG>/{'|'.join(tops)}/..."


def output_required(directory: str) -> str:
    """Return the error text of a request without ``output_dir``.

    Error text of a request without ``output_dir`` (every store command):
    ``directory`` = the top directory of its files (``nmt``, ``boundaries``).
    """
    return f"--output wymagane: katalog magazynu ({store_files([directory])})"


def year_bounds(
    year: int | None, min_year: int | None, max_year: int | None
) -> tuple[int | None, int | None]:
    """Return the year bounds ``(min_year, max_year)`` of the year flags.

    ``(min_year, max_year)`` of the year flags (``year`` = both bounds);
    ``ValidationError`` naming the flags for a contradictory choice.
    """
    if year is not None and (min_year is not None or max_year is not None):
        raise ValidationError(
            "--year wyklucza sie z --min-year/--max-year "
            "(--year Y to skrot --min-year Y --max-year Y)",
            options=(
                "year",
                *(
                    name
                    for name, value in (("min_year", min_year), ("max_year", max_year))
                    if value is not None
                ),
            ),
        )
    if year is not None:
        min_year = max_year = year
    try:
        validate_year_bounds(min_year, max_year)
    except ValidationError as e:
        # ``year`` stands for both bounds: its error is about ``year``
        rename = {"min_year": "year"} if year is not None else {}
        raise ValidationError(
            str(e)
            .replace("min_year", "--year" if year is not None else "--min-year")
            .replace("max_year", "--max-year"),
            option=rename.get(e.option, e.option) if e.option else None,
            options=tuple(rename.get(name, name) for name in e.options or ()) or None,
        ) from None
    return min_year, max_year


def validate_request(task: SimpleNamespace) -> None:
    """Check the whole request before anything else (no network).

    Exactly one selection, explicit product/output, country for areas,
    per-country syntax, year bounds (``year`` = ``min_year = max_year``),
    LAZ-only and non-LAZ options, the image cutout (orthophotomap
    ``coverage``, pixel, EPSG:2180 only, PL only), the view directions
    (``direction``, oblique orthophotomap; narrowed to a tuple of codes in
    registry order), ``full_sheet`` only where the index declares full
    sheets, the choices a voivodeship file variant (NMT 100 m) does not
    take. Narrows ``task.min_year``/``max_year``. Types of library arguments
    first (``year="2018"``, ``cutout="no"``: ``ValidationError``, no
    conversion).
    """
    validate_area_choice(task.sheet, task.bbox, task.geometry, task.layer)
    for flag, name in (
        ("--cutout", "cutout"),
        ("--all-campaigns", "all_campaigns"),
        ("--full-sheet", "full_sheet"),
    ):
        require_bool(getattr(task, name), flag)
    if task.min_density is not None:
        require_int(task.min_density, "--min-density")
    if task.product is None:
        raise ValidationError(
            f"--product wymagane: {PRODUCT_CHOICES}",
            option="product",
            allowed=_PRODUCTS,
        )
    if task.product not in _PRODUCTS:
        raise ValidationError(
            f"--product {task.product!r}: nieznana wartosc - dostepne: "
            f"{PRODUCT_CHOICES}",
            option="product",
            allowed=_PRODUCTS,
        )
    if task.output_dir is None:
        raise ValidationError(
            output_required(product_directory(task.product)), option="output_dir"
        )
    if task.sheet is None and task.country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}",
            option="country",
            allowed=COUNTRIES,
        )
    if task.country is not None and task.country not in COUNTRIES:
        raise ValidationError(
            f"--country {task.country!r}: nieznana wartosc - dostepne: "
            f"{COUNTRY_CHOICES}",
            option="country",
            allowed=COUNTRIES,
        )
    if task.sheet_system is not None and task.sheet_system not in _SHEET_SYSTEMS:
        raise ValidationError(
            f"--sheet-system {task.sheet_system!r}: nieznana wartosc - dostepne: "
            f"{SHEET_SYSTEM_CHOICES}",
            option="sheet_system",
            allowed=_SHEET_SYSTEMS,
        )
    cutout_key = image_cutout_key(task.product)
    image_cutout = task.cutout and cutout_key is not None
    if (
        task.horizontal_crs is not None
        and not image_cutout
        and task.horizontal_crs not in CUTOUT_CRS
    ):
        raise ValidationError(
            f"--horizontal-crs {task.horizontal_crs!r}: nieznana wartosc - "
            f"dostepne: {', '.join(CUTOUT_CRS)}",
            option="horizontal_crs",
            allowed=CUTOUT_CRS,
        )
    check_per_country(task.resolution, "--resolution")
    check_per_country(task.vertical_crs, "--vertical-crs")
    error = _contours_error(task)
    if error is not None:
        raise error
    file_variant = pl_file_variant(task)
    if file_variant is not None:
        error = _file_variant_error(task, file_variant)
        if error is not None:
            raise error
    if task.model is not None and task.product != "laz":
        raise option_error(
            "--model dotyczy tylko --product laz w CZ", "model", "product"
        )
    if task.model is not None and task.country == "pl":
        raise option_error(
            "--model dotyczy tylko --product laz w CZ - pomin --model dla PL",
            "model",
            "country",
        )
    task.min_year, task.max_year = year_bounds(task.year, task.min_year, task.max_year)
    if task.product != "laz" and task.min_density is not None:
        raise option_error(
            f"--min-density dziala tylko z --product laz (podano "
            f"{task.product}); pomin --min-density",
            "min_density",
            "product",
        )
    if task.product == "laz" and task.full_sheet:
        raise option_error(
            "--full-sheet dziala tylko z NMT/NMPT i obrazami (podano laz) - LAZ "
            "nie ma sciezki standardowej ani dowiazania full_sheet/; "
            "pomin --full-sheet",
            "full_sheet",
            "product",
        )
    index = _image_index(task.product)
    if task.full_sheet and index is not None and not index.full_sheet:
        raise option_error(
            f"--full-sheet nie dotyczy --product {task.product}: rekordy skorowidza "
            "GUGiK nie deklaruja pelnego arkusza (bez calyArkuszWypelnionyTrescia) "
            "- pomin --full-sheet",
            "full_sheet",
            "product",
        )
    error = _direction_error(task)
    if error is not None:
        raise error
    if task.cutout:
        if task.sheet is not None:
            raise option_error(
                "--cutout dziala tylko z --bbox/--geometry; --sheet wyznacza "
                "zasieg i uklad produktu (arkusz PL 1:1 w ukladzie arkusza, "
                "arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce EPSG:3045)",
                "cutout",
                "sheet",
            )
        if task.product not in cutout_products():
            raise option_error(
                f"--cutout dziala tylko z --product {_or_list(cutout_products())} "
                f"(wycinek z WCS GUGiK); {task.product} - pobierz bez --cutout",
                "cutout",
                "product",
            )
        if image_cutout:
            assert cutout_key is not None  # image_cutout
            if task.product == "orto" and task.country == "cz":
                raise option_error(ORTO_CUTOUT_PL_ONLY, "cutout", "country")
            error = orto_cutout_error(
                key=cutout_key,
                coverage=task.coverage,
                resolution=country_value(task.resolution, "PL"),
                horizontal_crs=task.horizontal_crs,
            )
            if error is not None:
                raise error
        elif task.horizontal_crs is None:
            raise ValidationError(
                f"--horizontal-crs wymagane z --cutout (uklad wycinka): "
                f"{', '.join(CUTOUT_CRS)}",
                option="horizontal_crs",
                allowed=CUTOUT_CRS,
            )
    elif task.horizontal_crs is not None:
        raise option_error(
            "--horizontal-crs dziala tylko z --cutout (uklad jednego wycinka); "
            "arkusze maja uklad z godla - dodaj --cutout albo pomin "
            "--horizontal-crs",
            "horizontal_crs",
            "cutout",
        )
    if task.coverage is not None and not image_cutout:
        if cutout_key is not None and len(wcs_cutout_channels(cutout_key)) == 1:
            error = cutout_choice_error(cutout_key, task.coverage, None)
            assert error is not None  # a coverage of a one-channel cutout
            raise error
        raise option_error(
            "--coverage dziala tylko z --cutout --product orto (wariant WCS "
            f"wycinka ortofotomapy: {coverage_choices(ORTO_KEY)}) - pomin --coverage",
            "coverage",
            "cutout",
        )
    if (
        image_source(task.product) is not None
        and not task.cutout
        and task.resolution is not None
    ):
        if task.product == "orto":
            raise option_error(
                "--resolution z --product orto dotyczy tylko wycinka (--cutout); "
                "arkusze ortofotomapy maja piksel zrodla (PL: kampanii, CZ: arkusza "
                "SM5 w pliku JGW) - pomin --resolution",
                "resolution",
                "cutout",
            )
        where = "dotyczy tylko wycinka (--cutout)" if cutout_key else "nie dotyczy"
        raise option_error(
            f"--resolution z --product {task.product} {where}; arkusze maja "
            "piksel zrodla (rekordu skorowidza GUGiK) - pomin --resolution",
            "resolution",
            "cutout",
        )


def _direction_error(task: SimpleNamespace) -> ValidationError | None:
    """Return the error of ``direction``.

    The error of ``direction`` (``None`` = valid); a valid choice is
    narrowed to the tuple of its codes in registry order (``None`` stays:
    every direction of the product).
    """
    direction = task.direction
    if direction is None:
        return None
    codes = image_directions(task.product)
    if not codes:
        products = [p for p in IMAGERY_PRODUCTS if image_directions(p)]
        return option_error(
            f"--direction dotyczy tylko --product {_or_list(products)} (kierunki "
            "widoku orto ukosnej) - pomin --direction",
            "direction",
            "product",
        )
    values = (direction,) if isinstance(direction, str) else direction
    if (
        not isinstance(values, tuple | list)
        or not values
        or not all(isinstance(value, str) for value in values)
    ):
        return ValidationError(
            f"--direction {direction!r}: podaj kierunek albo liste kierunkow: "
            f"{', '.join(codes)}",
            option="direction",
            allowed=codes,
        )
    for value in values:
        if value not in codes:
            return ValidationError(
                f"--direction {value!r}: nieznana wartosc - dostepne: "
                f"{', '.join(codes)} (polnoc, wschod, poludnie, zachod)",
                option="direction",
                allowed=codes,
            )
    task.direction = tuple(code for code in codes if code in values)
    return None


def campaign_option_names(task: SimpleNamespace) -> tuple[str, ...]:
    """Return the PL-only campaign/year choices of the request.

    The PL-only campaign/year choices of the request, by argument name
    (``year`` was narrowed into both bounds: it counts once).
    """
    return tuple(
        name
        for name, given in (
            ("all_campaigns", task.all_campaigns),
            ("min_year", task.year is None and task.min_year is not None),
            ("max_year", task.year is None and task.max_year is not None),
            ("year", task.year is not None),
            ("full_sheet", task.full_sheet),
        )
        if given
    )


def reject_campaign_opts_with_cutout(task: SimpleNamespace) -> None:
    """Check that a PL cutout (WCS, ADR-035) has no year or campaign choice."""
    if not task.cutout:
        return
    flag = next(
        (
            name
            for name, supplied in (
                ("--year", task.year),
                ("--min-year", task.min_year),
                ("--max-year", task.max_year),
            )
            if supplied is not None
        ),
        None,
    )
    if flag is not None:
        raise option_error(
            f"{flag} nie dziala z --cutout - wycinek z WCS GUGiK ma "
            "kompozycje lotow serwera (bez wyboru roku); rok danych: pobierz "
            "arkusze bez --cutout",
            option_name(flag),
            "cutout",
        )
    if task.all_campaigns:
        raise option_error(
            "--all-campaigns nie dziala z --cutout - wycinek z WCS "
            "GUGiK ma jedna kompozycje lotow serwera; wszystkie kampanie: "
            "pobierz arkusze bez --cutout",
            "all_campaigns",
            "cutout",
        )
    if task.full_sheet:
        raise option_error(
            "--full-sheet nie dziala z --cutout - wycinek pochodzi "
            "z WCS GUGiK, nie z arkuszy",
            "full_sheet",
            "cutout",
        )


def resolve_pl_options(
    task: SimpleNamespace,
    *,
    code_system: str | None = None,
    code_scale: str | None = None,
) -> None:
    """Validate the PL choices and narrow ``task`` to the plain PL values.

    Called on the PL branch only, on a COPY of the request (the CZ branch
    keeps its own values). Single-valued choices are filled in: the cutout
    is 1m only and PL-1992 only, a variant with one label in the registry
    (archive ``GRD``: 5m) takes it, a sheet request takes its sheet system
    from the code, an image product with one sheet system (true orto:
    PL-1992, oblique orto: PL-2000) takes it.
    """
    error = pl_option_error(task, code_system=code_system, code_scale=code_scale)
    if error is not None:
        raise error
    resolution = country_value(task.resolution, "PL")
    vertical_crs = country_value(task.vertical_crs, "PL")
    if task.product in _SHEET_PRODUCTS and resolution is None:
        if task.cutout:
            resolution = "1m"
        elif vertical_crs is not None:
            resolution = find_variant(
                product=task.product,
                country="PL",
                resolution=None,
                vertical_crs=vertical_crs,
                format=_format_of(task),
            ).label
    task.resolution = resolution
    task.vertical_crs = vertical_crs
    if task.product == "laz":
        return  # every tile has its system from the WFS index (no sheet system)
    if code_system is not None:
        task.sheet_system = code_system
    elif task.cutout:
        task.sheet_system = "1992"
    elif task.sheet_system is None:
        index = _image_index(task.product)
        if index is not None and len(index.systems) == 1:
            task.sheet_system = index.systems[0]


def is_source_file_request(task: SimpleNamespace) -> bool:
    """Return True for an archive format request (``--format`` other than ASC)."""
    fmt = _format_of(task)
    return fmt is not None and fmt != "ASC"


def pl_target_scale(task: SimpleNamespace) -> str:
    """Return the sheet scale of a PL area request.

    Sheet scale of a PL area request: PL-2000 ``scale``, PL-1992 the level
    of the product (``1:10000``; the 8-part ``1:5000`` codes of the true
    orthophotomap, ``series_scale``).
    """
    if task.sheet_system == "2000":
        scale: str = task.scale
        return scale
    index = _image_index(task.product)
    return series_scale(index.sheet_parts if index is not None else 7)
