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
from kartograf.core.sheet_parser import series_scale
from kartograf.download.arguments import require_bool, require_int
from kartograf.download.campaigns import validate_year_bounds
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import PRODUCT as CONTOURS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.cz_orto import cz_orto_sheet
from kartograf.download.orto_cutout import ORTO_CUTOUT_PL_ONLY, orto_cutout_error
from kartograf.exceptions import ValidationError
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
    """``nmt (...), nmpt (...)``: products named in messages and --help texts
    (a CLI group names only its own products, ADR-039)."""
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
        raise ValidationError(f"--product wymagane: {product_choices(products)}")
    if product not in products:
        raise ValidationError(
            f"--product {product!r}: nieznana wartosc - dostepne: "
            f"{product_choices(products)}"
        )


def product_directory(product: str) -> str:
    """Top directory of the files of a ``download_data`` product in the store
    (``nmt``, ``orto``): the first element of its sources' storage segments."""
    tops = dict.fromkeys(
        source.storage_subdir.split("/", 1)[0]
        for source in sources_for(product=product)
    )
    return "|".join(tops) or product


COUNTRY_CHOICES = (
    "pl (GUGiK), cz (CUZK), auto (kraje wg prostokatnych obwiedni PL i CZ; "
    "obszar w obu krajach daje osobne pliki per kraj)"
)
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
    """Descriptor key of the WCS cutout of an image product (``orto``,
    ``true-orto``); ``None`` for a product without one."""
    source = image_source(product)
    if source is None or not wcs_cutout_channels(source.key):
        return None
    return source.key


def cutout_products() -> tuple[str, ...]:
    """Products with a PL cutout (``--cutout``): the grids and the images with
    a WCS cutout channel, registry order."""
    images = (p for p in IMAGERY_PRODUCTS if image_cutout_key(p) is not None)
    return (*_SHEET_PRODUCTS, *images)


def _or_list(values: Sequence[str]) -> str:
    """``a, b albo c``."""
    return (
        f"{', '.join(values[:-1])} albo {values[-1]}" if len(values) > 1 else values[0]
    )


def resolution_text(country: str = "PL") -> str:
    """Grid resolutions (``--resolution``) of every sheet product, from the
    variant registry: ``NMT (EVRF2007: 0.15m, ...; KRON86: 0.5m, 1m), NMPT (...)``."""
    parts = []
    for product in _SHEET_PRODUCTS:
        grids = tuple(
            v for v in variants(product=product, country=country) if not v.source_file
        )
        if grids:
            parts.append(f"{product.upper()} ({labels_by_vertical_crs(grids)})")
    return ", ".join(parts)


def vertical_crs_text(country: str = "PL") -> str:
    """Height systems of the country's variants (``--vertical-crs``; a
    variant without one takes no flag)."""
    names = sorted(
        {v.vertical_crs for v in variants(country=country) if v.vertical_crs}
    )
    return ", ".join(
        f"{name} ({_VERTICAL_CRS_TEXT[name]})" if name in _VERTICAL_CRS_TEXT else name
        for name in names
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
    """CZ grid labels per product with their CUZK model and the labels of the
    SM5 sheets (variant registry): ``NMT: 2m (DMR 5G), 5m (DMR 4G); ...``."""
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


BBOX_EXPECTED = "Oczekiwano: min_x,min_y,max_x,max_y (np. 450000,550000,460000,560000)"
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
            f"przecinkami (kraje: pl, cz), np. {flag} pl=...,cz=..."
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
    """The PL variant of the request published as voivodeship files of an
    ATOM feed (no sheet index: NMT 100 m, plan E1), ``None`` for the sheet
    variants. Chosen by the product, the PL resolution and the format
    (``None`` or the variant's own); nothing is validated here."""
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


def _file_variant_error(task: SimpleNamespace, variant: ProductVariant) -> str | None:
    """Error text of the choices a voivodeship file variant does not take."""
    label = variant.label or ""
    shown = f"{variant.product.upper()} {label.removesuffix('m')} m"
    reason = f"{shown} to pliki wojewodztw z ATOM - bez arkuszy, lotow i wycinka"
    for flag, name in _SHEET_CHOICES:
        value = getattr(task, name)
        if value is not None and value is not False:
            return f"{flag} nie dotyczy --resolution {label}: {reason}"
    if task.country == "cz":
        return f"--country cz nie dotyczy --resolution {label} (tylko PL): {reason}"
    if (
        country_value(task.vertical_crs, "PL") is not None
        and variant.vertical_crs is None
    ):
        return (
            f"--vertical-crs nie dotyczy --resolution {label}: {UNKNOWN_VERTICAL} - "
            f"GUGiK nie deklaruje ukladu wysokosci {shown}; pomin --vertical-crs"
        )
    return None


def pl_option_error(
    task: SimpleNamespace,
    *,
    code_system: str | None = None,
    code_scale: str | None = None,
    countries: tuple[str, ...] = ("PL",),
) -> str | None:
    """Error text for the PL data choices of the request (``None`` = valid).

    ``code_system``/``code_scale`` describe a sheet request (sheet system and
    scale of the code); ``None`` = area request (bbox/geometry). NMT/NMPT
    choices are checked against the variant registry
    (``kartograf.sources.variants``): format, resolution, height system. A
    voivodeship file variant (``pl_file_variant``) was checked by
    ``validate_request`` already.
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
        return (
            "--resolution nie dotyczy LAZ - chmura punktow nie ma siatki; pomin "
            "--resolution"
        )

    if product in _SHEET_PRODUCTS:
        if cutout:
            if source_file:
                return (
                    f"--cutout dziala tylko z siatka ASC 1m (wycinek z WCS GUGiK); "
                    f"--format {fmt} to pliki zrodlowe arkuszy - pomin --cutout"
                )
            if resolution not in (None, "1m"):
                return (
                    f"wycinki PL (--cutout) sa tylko 1 m (WCS GUGiK); arkusze "
                    f"{resolution}: pomin --cutout (arkusze bez --cutout); "
                    "wycinek: --resolution 1m albo pomin --resolution"
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
                return f"{error}{res_hint}"
    elif fmt is not None:
        return (
            f"--format dotyczy tylko --product nmt i nmpt (PL) oraz {CONTOURS} "
            f"(CZ), podano --product {product} - pomin --format"
        )

    index = _image_index(product)
    if index is not None:
        if vertical_crs is not None:
            noun = "ortofotomapa" if product == "orto" else "obraz"
            return (
                f"--vertical-crs nie dotyczy --product {product} "
                f"({noun} nie ma ukladu pionowego)"
            )
    elif vertical_crs is None:
        return (
            f"--vertical-crs wymagane dla --product {product} (PL): "
            f"{vertical_crs_text()}{vcrs_hint}"
        )
    elif vertical_crs not in {v.vertical_crs for v in variants(country="PL")}:
        return (
            f"{vertical_crs} nie jest ukladem wysokosci PL - dostepne: "
            f"{vertical_crs_text()}{vcrs_hint}"
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
            return f"{error}{vcrs_hint}"

    if product == "laz":  # per-tile system from WFS, no sheet scale
        flags = [
            flag
            for flag, value in (
                ("--sheet-system", task.sheet_system),
                ("--scale", task.scale),
            )
            if value is not None
        ]
        if flags:
            verb = "nie dotycza" if len(flags) > 1 else "nie dotyczy"
            return (
                f"{' i '.join(flags)} {verb} LAZ PL - uklad kazdego kafla pochodzi "
                f"z WFS GUGiK; pomin {' i '.join(flags)}"
            )
        return None
    sheet_system = task.sheet_system
    scale = task.scale
    systems = index.systems if index is not None else _SHEET_SYSTEMS
    if cutout:
        if sheet_system not in (None, "1992"):
            return (
                "--cutout nie dziala z --sheet-system 2000 - bbox wielostrefowy "
                "dalby arkusze w roznych CRS (2176-2179); wycinek: --sheet-system "
                "1992 albo pomin --sheet-system"
            )
        return None
    if source_file and scale is not None:
        return (
            f"--scale nie dotyczy --format {fmt}: arkusze archiwum (rozne skale) "
            "wynikaja ze skorowidza GUGiK - pomin --scale"
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
                return (
                    f"--sheet-system wymagane dla --bbox/--geometry w PL: "
                    f"{SHEET_SYSTEM_CHOICES}{cutout_hint}"
                )
        elif sheet_system not in systems:
            return (
                f"--sheet-system {sheet_system} nie dotyczy --product {product}: "
                f"GUGiK publikuje arkusze tylko {only} - pomin --sheet-system"
            )
        else:
            effective = sheet_system
    elif code_system not in systems:
        return (
            f"--product {product}: GUGiK publikuje arkusze tylko {only} - godlo "
            f"{task.sheet} to PL-{code_system}"
        )
    elif sheet_system is not None and sheet_system != code_system:
        return (
            f"--sheet-system {sheet_system} nie zgadza sie z godlem {task.sheet} "
            f"(PL-{code_system}): uklad arkuszy wynika z godla - pomin "
            "--sheet-system"
        )
    else:
        effective = code_system
    if source_file:
        return None  # archive sheets come from the index (any scale)
    if effective == "1992":
        if scale is not None:
            parts = index.sheet_parts if index is not None else 7
            label = series_scale(parts)
            return (
                "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 "
                f"tylko w {label} (godlo {parts}-czlonowe), a grubsze godlo rozwija "
                f"sie do {label} samo - pomin --scale"
            )
        return None
    if scale is None and (code_system is None or code_scale == "1:10000"):
        return f"--scale wymagane dla arkuszy PL-2000: {SCALE_2000_CHOICES}"
    if scale is not None and scale not in SCALES_2000:
        return f"Nieznana skala PL-2000 {scale} - dostepne: {SCALE_2000_CHOICES}"
    return None


def cz_option_error(
    task: SimpleNamespace,
    *,
    system: str | None = None,
    countries: tuple[str, ...] = ("CZ",),
) -> str | None:
    """Error text for the CZ data choices (``None`` = valid), from the variant
    registry (``cz_variant_error``).

    ``system``: ``"sm5"``/``"tm33"`` of a sheet code, ``None`` = an area (a
    cutout of the ImageServer, any label of the product).
    """
    resolution = country_value(task.resolution, "CZ")
    vertical_crs = country_value(task.vertical_crs, "CZ")
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)
    if _format_of(task) is not None:
        return (
            f"--format dotyczy w CZ tylko --product {CONTOURS} (warstwice); "
            f"{task.product.upper()} CZ to pliki CUZK bez wyboru formatu - pomin "
            "--format"
        )
    if task.product == "laz":
        if task.resolution is not None:
            return "--resolution nie dotyczy LAZ CZ - pomin --resolution"
        if task.min_density is not None:
            return "--min-density dotyczy tylko LAZ PL - pomin --min-density"
        if task.sheet_system is not None and "PL" not in countries:
            return "--sheet-system dotyczy tylko PL (godla CZ wykrywane wzorcem)"
        error = cz_laz_error(model=task.model, vertical_crs=vertical_crs, system=system)
        if error is not None:
            return f"{error}{vcrs_hint}"
        if vertical_crs is None:
            return (
                f"--vertical-crs wymagane dla LAZ CZ: {CZ_LAZ_VERTICAL_TEXT}{vcrs_hint}"
            )
        return None
    error = cz_variant_error(
        product=task.product, resolution=resolution, vertical_crs=None, system=system
    )
    if error is not None:
        return f"{error}{res_hint}"
    if vertical_crs is None:
        return (
            f"--vertical-crs wymagane dla {task.product.upper()} CZ: "
            f"{CZ_VERTICAL_TEXT}{vcrs_hint}"
        )
    error = cz_variant_error(
        product=task.product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    if error is not None:
        return f"{error}{vcrs_hint}"
    if "PL" not in countries and task.sheet_system is not None:
        return "--sheet-system dotyczy tylko PL (godla CZ wykrywane wzorcem)"
    return None


def _contours_error(task: SimpleNamespace) -> str | None:
    """Error text of a CZ contours request (``None`` = valid): vector SM5
    sheets take ``--format`` (required, values of the registry) and the
    height system of their files (one value: may be omitted); no grid,
    flight, cutout or view choice."""
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
            return f"{flag} nie dotyczy --product {CONTOURS}: {reason}"
    formats = contours_formats()
    fmt = _format_of(task)
    if fmt is None:
        return f"--format wymagane dla --product {CONTOURS}: {', '.join(formats)}"
    if fmt not in formats:
        return (
            f"--format {fmt!r}: nieznana wartosc dla --product {CONTOURS} - "
            f"dostepne: {', '.join(formats)}"
        )
    heights = sorted(
        {v.vertical_crs for v in variants(product=CONTOURS) if v.vertical_crs}
    )
    vertical_crs = country_value(task.vertical_crs, "CZ")
    if vertical_crs is not None and vertical_crs not in heights:
        return (
            f"--vertical-crs {vertical_crs} nie dotyczy --product {CONTOURS}: "
            f"warstwice ZABAGED maja wysokosci {', '.join(heights)} (mozna pominac "
            "--vertical-crs)"
        )
    return None


def cz_orto_option_error(
    task: SimpleNamespace, *, countries: tuple[str, ...] = ("CZ",)
) -> str | None:
    """Error text for the CZ orthophoto choices (``None`` = valid; ADR-042 D13).

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
            return str(e)
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
            return (
                f"{flag} dotyczy tylko PL - CUZK publikuje tylko aktualny rocznik "
                "arkusza ortofoto CZ (archiwalne ortofoto CUZK sa platne, poza "
                "zakresem)"
            )
        if task.sheet_system is not None:
            return (
                "--sheet-system dotyczy tylko PL - ortofoto CZ to arkusze SM5 "
                "(godlo rozpoznawane wzorcem, arkusze obszaru z indeksu SM5)"
            )
        if task.scale is not None:
            return (
                "--scale dotyczy tylko PL - ortofoto CZ to arkusze SM5 w jednej "
                "skali (1:5000)"
            )
    if country_value(task.vertical_crs, "CZ") is not None:
        return (
            "--vertical-crs nie dotyczy --product orto "
            "(ortofotomapa nie ma ukladu pionowego)"
        )
    if _format_of(task) is not None:
        return (
            "--format nie dotyczy ortofoto CZ (pliki CUZK: JPEG i JGW bez "
            "konwersji) - pomin --format"
        )
    return None


def require_cz_cutout(task: SimpleNamespace, countries: tuple[str, ...]) -> None:
    """CZ raster areas require cutout; CZ LAZ and orthophoto areas use the
    indexed sheets."""
    if (
        task.product in ("laz", "orto", CONTOURS)
        or task.sheet is not None
        or "CZ" not in countries
        or task.cutout
    ):
        return
    if "PL" in countries:
        raise ValidationError(
            "obszar siega CZ, a CUZK daje dla obszaru tylko jeden wycinek - "
            "dodaj --cutout --horizontal-crs <uklad> (czesc PL tez bedzie "
            "wycinkiem z WCS GUGiK) albo uzyj --country pl (tylko arkusze PL)"
        )
    raise ValidationError(
        "obszar CZ (CUZK) jest pobierany tylko jako jeden wycinek - dodaj "
        "--cutout --horizontal-crs <uklad> (np. EPSG:5514, uklad natywny CUZK)"
    )


# Enumerated values given in any case (UX-11): the spelling of the registry
# when the value is one of its values in another case; anything else stays as
# given, so a message names it as the user wrote it.
# A CRS code ``<authority>:<code>`` (``epsg:2180``); authorities are upper case.
_CRS_CODE = re.compile(r"[A-Za-z]+:[0-9A-Za-z]+")


def _spelling[T](value: T, known: Mapping[str, str]) -> T:
    """``value`` as ``known[value.lower()]`` (``known``: lower case -> registry
    spelling); a value of another type or not known unchanged."""
    if not isinstance(value, str):
        return value
    return cast(T, known.get(value.strip().lower(), value))


def canonical_country[T](value: T) -> T:
    """``PL`` -> ``pl``, ``Auto`` -> ``auto`` (``--country``)."""
    return _spelling(value, {code: code for code in COUNTRIES})


@functools.cache
def _formats() -> dict[str, str]:
    """Lower case -> registry spelling of every file format a source offers
    (variants of the sheet products, package variants and channel choices)."""
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
    """``epsg:2180`` -> ``EPSG:2180``: a CRS code with an upper case authority
    (``--bbox-crs``, ``--horizontal-crs``); not a CRS code: unchanged."""
    if isinstance(value, str) and _CRS_CODE.fullmatch(value.strip()):
        return cast(T, value.strip().upper())
    return value


@functools.cache
def _vertical_names() -> dict[str, str]:
    """Lower case -> registry spelling of every height system."""
    names = {v.vertical_crs for v in variants() if v.vertical_crs}
    return {name.lower(): name for name in names}


def canonical_vertical_crs[T](value: T) -> T:
    """``evrf2007`` -> ``EVRF2007``, ``BPV`` -> ``Bpv``: a height system (plain
    or per country) in the spelling of the variant registry."""
    if isinstance(value, Mapping):
        names = _vertical_names()
        return cast(T, {key: _spelling(name, names) for key, name in value.items()})
    return _spelling(value, _vertical_names())


def canonical_bbox[T](bbox: T) -> T:
    """A ``BBox`` with its CRS code in the upper case spelling
    (``epsg:5514`` = ``EPSG:5514``); any other value unchanged."""
    if isinstance(bbox, BBox):
        return cast(T, bbox._replace(crs=canonical_crs(bbox.crs)))
    return bbox


def validate_request_bbox(bbox: BBox) -> BBox:
    """Validate parsed bbox coordinates with the same text for CLI and API;
    returns the bbox with its CRS code in the registry spelling
    (``epsg:2180`` = ``EPSG:2180``) - callers go on with it."""
    bbox = canonical_bbox(bbox)
    if bbox.crs not in BBOX_CRS_CHOICES:
        raise ValidationError(
            f"Nieprawidlowy bbox: nieobslugiwany uklad {bbox.crs!r} - dostepne: "
            f"{', '.join(BBOX_CRS_CHOICES)}"
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
        raise ValidationError(f"Nieprawidlowy bbox: {e}. {BBOX_EXPECTED}") from e
    return bbox


def validate_area_choice(
    sheet: str | None,
    bbox: BBox | None,
    geometry: object | None,
    layer: object | None = None,
) -> None:
    """Exactly one area choice, a valid bbox and ``layer`` only with
    ``geometry`` (texts shared by every command taking
    ``--sheet/--bbox/--geometry``; no network)."""
    # the CLI parses --bbox before anything else: the same first error
    if bbox is not None:
        validate_request_bbox(bbox)
    provided = sum(v is not None for v in (sheet, bbox, geometry))
    if provided > 1:
        raise ValidationError(
            "Podaj dokladnie jeden wybor obszaru: --sheet, --bbox albo --geometry"
        )
    if provided == 0:
        raise ValidationError("Podaj wybor obszaru: --sheet, --bbox albo --geometry")
    check_layer(layer, geometry)


def check_layer(layer: object, geometry: object, *, landcover: bool = False) -> None:
    """``layer`` names a layer of the ``geometry`` file; without a geometry
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
            f"--layer dotyczy tylko --geometry (warstwa pliku GPKG z obszarem){hint}"
        )


def output_required(directory: str) -> str:
    """Error text of a request without ``output_dir`` (every store command):
    ``directory`` = the top directory of its files (``nmt``, ``boundaries``)."""
    return f"--output wymagane: katalog magazynu (pliki w <KATALOG>/{directory}/...)"


def year_bounds(
    year: int | None, min_year: int | None, max_year: int | None
) -> tuple[int | None, int | None]:
    """``(min_year, max_year)`` of the year flags (``year`` = both bounds);
    ``ValidationError`` naming the flags for a contradictory choice."""
    if year is not None and (min_year is not None or max_year is not None):
        raise ValidationError(
            "--year wyklucza sie z --min-year/--max-year "
            "(--year Y to skrot --min-year Y --max-year Y)"
        )
    if year is not None:
        min_year = max_year = year
    try:
        validate_year_bounds(min_year, max_year)
    except ValidationError as e:
        raise ValidationError(
            str(e)
            .replace("min_year", "--year" if year is not None else "--min-year")
            .replace("max_year", "--max-year")
        ) from None
    return min_year, max_year


def validate_request(task: SimpleNamespace) -> None:
    """Checks of the whole request before anything else (no network).

    Exactly one selection, explicit product/output, country for areas,
    per-country syntax, year bounds (``year`` = ``min_year = max_year``),
    LAZ-only and non-LAZ options, the image cutout (orthophotomap
    ``coverage``, pixel, EPSG:2180 only, PL only), the view directions
    (``direction``, oblique orthophotomap; narrowed to a tuple of codes in
    registry order), ``full_sheet`` only where the index declares full
    sheets, the choices a voivodeship file variant (NMT 100 m) does not
    take. Narrows ``task.min_year``/``max_year``. Types of library arguments
    first (``year="2018"``, ``cutout="no"``: ``ValidationError``, no
    conversion; STANDARDS 11.2).
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
        raise ValidationError(f"--product wymagane: {PRODUCT_CHOICES}")
    if task.product not in _PRODUCTS:
        raise ValidationError(
            f"--product {task.product!r}: nieznana wartosc - dostepne: "
            f"{PRODUCT_CHOICES}"
        )
    if task.output_dir is None:
        raise ValidationError(output_required(product_directory(task.product)))
    if task.sheet is None and task.country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    if task.country is not None and task.country not in COUNTRIES:
        raise ValidationError(
            f"--country {task.country!r}: nieznana wartosc - dostepne: "
            f"{COUNTRY_CHOICES}"
        )
    if task.sheet_system is not None and task.sheet_system not in _SHEET_SYSTEMS:
        raise ValidationError(
            f"--sheet-system {task.sheet_system!r}: nieznana wartosc - dostepne: "
            f"{SHEET_SYSTEM_CHOICES}"
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
            f"dostepne: {', '.join(CUTOUT_CRS)}"
        )
    check_per_country(task.resolution, "--resolution")
    check_per_country(task.vertical_crs, "--vertical-crs")
    error = _contours_error(task)
    if error is not None:
        raise ValidationError(error)
    file_variant = pl_file_variant(task)
    if file_variant is not None:
        error = _file_variant_error(task, file_variant)
        if error is not None:
            raise ValidationError(error)
    if task.model is not None and task.product != "laz":
        raise ValidationError("--model dotyczy tylko --product laz w CZ")
    if task.model is not None and task.country == "pl":
        raise ValidationError(
            "--model dotyczy tylko --product laz w CZ - pomin --model dla PL"
        )
    task.min_year, task.max_year = year_bounds(task.year, task.min_year, task.max_year)
    if task.product != "laz" and task.min_density is not None:
        raise ValidationError(
            f"--min-density dziala tylko z --product laz (podano "
            f"{task.product}); pomin --min-density"
        )
    if task.product == "laz" and task.full_sheet:
        raise ValidationError(
            "--full-sheet dziala tylko z NMT/NMPT i obrazami (podano laz) - LAZ "
            "nie ma sciezki standardowej ani dowiazania full_sheet/; pomin --full-sheet"
        )
    index = _image_index(task.product)
    if task.full_sheet and index is not None and not index.full_sheet:
        raise ValidationError(
            f"--full-sheet nie dotyczy --product {task.product}: rekordy skorowidza "
            "GUGiK nie deklaruja pelnego arkusza (bez calyArkuszWypelnionyTrescia) "
            "- pomin --full-sheet"
        )
    error = _direction_error(task)
    if error is not None:
        raise ValidationError(error)
    if task.cutout:
        if task.sheet is not None:
            raise ValidationError(
                "--cutout dziala tylko z --bbox/--geometry; --sheet wyznacza "
                "zasieg i uklad produktu (arkusz PL 1:1 w ukladzie arkusza, "
                "arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce EPSG:3045)"
            )
        if task.product not in cutout_products():
            raise ValidationError(
                f"--cutout dziala tylko z --product {_or_list(cutout_products())} "
                f"(wycinek z WCS GUGiK); {task.product} - pobierz bez --cutout"
            )
        if image_cutout:
            assert cutout_key is not None  # image_cutout
            if task.product == "orto" and task.country == "cz":
                raise ValidationError(ORTO_CUTOUT_PL_ONLY)
            error = orto_cutout_error(
                key=cutout_key,
                coverage=task.coverage,
                resolution=country_value(task.resolution, "PL"),
                horizontal_crs=task.horizontal_crs,
            )
            if error is not None:
                raise ValidationError(error)
        elif task.horizontal_crs is None:
            raise ValidationError(
                f"--horizontal-crs wymagane z --cutout (uklad wycinka): "
                f"{', '.join(CUTOUT_CRS)}"
            )
    elif task.horizontal_crs is not None:
        raise ValidationError(
            "--horizontal-crs dziala tylko z --cutout (uklad jednego wycinka); "
            "arkusze maja uklad z godla - dodaj --cutout albo pomin "
            "--horizontal-crs"
        )
    if task.coverage is not None and not image_cutout:
        if cutout_key is not None and len(wcs_cutout_channels(cutout_key)) == 1:
            error = cutout_choice_error(cutout_key, task.coverage, None)
            assert error is not None  # a coverage of a one-channel cutout
            raise ValidationError(error)
        raise ValidationError(
            "--coverage dziala tylko z --cutout --product orto (wariant WCS "
            f"wycinka ortofotomapy: {coverage_choices(ORTO_KEY)}) - pomin --coverage"
        )
    if (
        image_source(task.product) is not None
        and not task.cutout
        and task.resolution is not None
    ):
        if task.product == "orto":
            raise ValidationError(
                "--resolution z --product orto dotyczy tylko wycinka (--cutout); "
                "arkusze ortofotomapy maja piksel zrodla (PL: kampanii, CZ: arkusza "
                "SM5 w pliku JGW) - pomin --resolution"
            )
        where = "dotyczy tylko wycinka (--cutout)" if cutout_key else "nie dotyczy"
        raise ValidationError(
            f"--resolution z --product {task.product} {where}; arkusze maja "
            "piksel zrodla (rekordu skorowidza GUGiK) - pomin --resolution"
        )


def _direction_error(task: SimpleNamespace) -> str | None:
    """Error text of ``direction`` (``None`` = valid); a valid choice is
    narrowed to the tuple of its codes in registry order (``None`` stays:
    every direction of the product)."""
    direction = task.direction
    if direction is None:
        return None
    codes = image_directions(task.product)
    if not codes:
        products = [p for p in IMAGERY_PRODUCTS if image_directions(p)]
        return (
            f"--direction dotyczy tylko --product {_or_list(products)} (kierunki "
            "widoku orto ukosnej) - pomin --direction"
        )
    values = (direction,) if isinstance(direction, str) else direction
    if (
        not isinstance(values, tuple | list)
        or not values
        or not all(isinstance(value, str) for value in values)
    ):
        return (
            f"--direction {direction!r}: podaj kierunek albo liste kierunkow: "
            f"{', '.join(codes)}"
        )
    for value in values:
        if value not in codes:
            return (
                f"--direction {value!r}: nieznana wartosc - dostepne: "
                f"{', '.join(codes)} (polnoc, wschod, poludnie, zachod)"
            )
    task.direction = tuple(code for code in codes if code in values)
    return None


def campaign_opts_given(task: SimpleNamespace) -> bool:
    """Any PL-only campaign/year choice of the request."""
    return bool(
        task.all_campaigns
        or task.min_year is not None
        or task.max_year is not None
        or task.year is not None
        or task.full_sheet
    )


def reject_campaign_opts_with_cutout(task: SimpleNamespace) -> None:
    """A PL cutout (WCS, ADR-035) has no year or campaign choice."""
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
        raise ValidationError(
            f"{flag} nie dziala z --cutout - wycinek z WCS GUGiK ma "
            "kompozycje lotow serwera (bez wyboru roku); rok danych: pobierz "
            "arkusze bez --cutout"
        )
    if task.all_campaigns:
        raise ValidationError(
            "--all-campaigns nie dziala z --cutout - wycinek z WCS "
            "GUGiK ma jedna kompozycje lotow serwera; wszystkie kampanie: "
            "pobierz arkusze bez --cutout"
        )
    if task.full_sheet:
        raise ValidationError(
            "--full-sheet nie dziala z --cutout - wycinek pochodzi "
            "z WCS GUGiK, nie z arkuszy"
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
        raise ValidationError(error)
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
    """An archive format (``--format`` other than ASC): sheets from the index."""
    fmt = _format_of(task)
    return fmt is not None and fmt != "ASC"


def pl_target_scale(task: SimpleNamespace) -> str:
    """Sheet scale of a PL area request: PL-2000 ``scale``, PL-1992 the level
    of the product (``1:10000``; the 8-part ``1:5000`` codes of the true
    orthophotomap, ``series_scale``)."""
    if task.sheet_system == "2000":
        return task.scale
    index = _image_index(task.product)
    return series_scale(index.sheet_parts if index is not None else 7)
