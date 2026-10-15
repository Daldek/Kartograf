"""Validation of the data choices of a ``download_data`` request (Z1).

Moved from the CLI: every rule that decides whether a request is valid lives
here, with the texts the CLI printed after ``Error:`` (they name the CLI
flags, because the CLI passes them 1:1 as ``ValidationError``). Values may be
plain (one value for every country of the request) or per country
(``{"pl": "1m", "cz": "2m"}``; the CLI parses ``pl=1m,cz=2m`` into it).
Nothing here touches the network.
"""

from collections.abc import Iterable, Mapping, Sequence
from types import SimpleNamespace

from kartograf.core.bbox import BBox, validate_bbox
from kartograf.download.arguments import require_bool, require_int
from kartograf.download.campaigns import validate_year_bounds
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_sheets import RESOLUTION_CZ, cz_sheet_resolution
from kartograf.exceptions import ValidationError
from kartograf.sources.variants import (
    FORMATS,
    find_variant,
    labels_by_vertical_crs,
    variant_error,
    variants,
)

# Admissible values named in messages (also the CLI --help texts).
_PRODUCT_TEXT = {
    "nmt": "Numeryczny Model Terenu; PL i CZ",
    "nmpt": "Numeryczny Model Pokrycia Terenu; PL",
    "orto": "ortofotomapa RGB; PL",
    "laz": "chmura punktow LIDAR; PL",
}


def product_choices(products: Iterable[str] = tuple(_PRODUCT_TEXT)) -> str:
    """``nmt (...), nmpt (...)``: products named in messages and --help texts
    (a CLI group names only its own products, ADR-039)."""
    return ", ".join(f"{product} ({_PRODUCT_TEXT[product]})" for product in products)


PRODUCT_CHOICES = product_choices()
# Products of the CLI groups (ADR-039): ``elevation download`` and ``imagery
# download`` offer only these; a new product of a group is added here.
ELEVATION_PRODUCTS: tuple[str, ...] = ("nmt", "nmpt", "laz")
IMAGERY_PRODUCTS: tuple[str, ...] = ("orto",)


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
    """Height systems of the country's variants (``--vertical-crs``)."""
    names = sorted({v.vertical_crs for v in variants(country=country)})
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


# Height systems of CZ requests (CUZK native Bpv, EVRF2007 by transformation).
CZ_VERTICAL_CRS = ("Bpv", "EVRF2007")
VERTICAL_CRS_CZ = (
    "Bpv (natywny uklad CUZK), EVRF2007 (transformacja z Bpv, "
    "ok. +0,11..+0,15 m, rosnaco S->N)"
)
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


CZ_ONLY_NMT = "--product {product} dla CZ bedzie dostepny w etapie 2 - teraz tylko nmt"
BBOX_EXPECTED = "Oczekiwano: min_x,min_y,max_x,max_y (np. 450000,550000,460000,560000)"
_PRODUCTS = tuple(_PRODUCT_TEXT)
_COUNTRIES = ("pl", "cz", "auto")
_SHEET_SYSTEMS = ("1992", "2000")

_COUNTRY_KEYS = ("pl", "cz")

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
            and all(k in _COUNTRY_KEYS for k in keys)
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
    (``kartograf.sources.variants``): format, resolution, height system.
    """
    product = task.product
    resolution = country_value(task.resolution, "PL")
    vertical_crs = country_value(task.vertical_crs, "PL")
    fmt = _format_of(task)
    cutout = task.cutout
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)
    source_file = fmt is not None and fmt != "ASC"

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
            f"--format dotyczy tylko --product nmt i nmpt (PL), podano "
            f"--product {product} - pomin --format"
        )

    if product == "orto":
        if vertical_crs is not None:
            return (
                "--vertical-crs nie dotyczy --product orto "
                "(ortofotomapa nie ma ukladu pionowego)"
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

    if product == "laz":
        return None  # LAZ: per-tile system from WFS, no sheet scale
    sheet_system = task.sheet_system
    scale = task.scale
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
    if code_system is None:
        if sheet_system is None:
            return (
                f"--sheet-system wymagane dla --bbox/--geometry w PL: "
                f"{SHEET_SYSTEM_CHOICES}; jeden wycinek zamiast arkuszy: --cutout"
            )
        effective = sheet_system
    else:
        effective = code_system
    if source_file:
        return None  # archive sheets come from the index (any scale)
    if effective == "1992":
        if scale is not None:
            return (
                "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 "
                "tylko w 1:10000 (godlo 7-czlonowe), a grubsze godlo rozwija sie "
                "do 1:10000 samo - pomin --scale"
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
    is_sm5: bool = False,
    countries: tuple[str, ...] = ("CZ",),
) -> str | None:
    """Error text for the CZ data choices (``is_sm5``: an SM5 sheet code)."""
    resolution = country_value(task.resolution, "CZ")
    vertical_crs = country_value(task.vertical_crs, "CZ")
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)
    if _format_of(task) is not None:
        return (
            "--format dotyczy tylko PL (siatki ASC i archiwa GUGiK) - dla CZ "
            "pomin --format"
        )
    if is_sm5:
        try:
            cz_sheet_resolution(task.sheet, resolution)
        except ValidationError as e:
            return str(e)
    elif resolution is None:
        return f"--resolution wymagane dla NMT CZ: {RESOLUTION_CZ}{res_hint}"
    elif resolution not in ("2m", "5m"):
        return (
            f"CZ nie ma rozdzielczosci {resolution} - dostepne: "
            f"{RESOLUTION_CZ}{res_hint}"
        )
    if vertical_crs is None:
        return f"--vertical-crs wymagane dla NMT CZ: {VERTICAL_CRS_CZ}{vcrs_hint}"
    if vertical_crs not in CZ_VERTICAL_CRS:
        return (
            f"{vertical_crs} nie jest dostepny dla CZ - dostepne: "
            f"{VERTICAL_CRS_CZ}{vcrs_hint}"
        )
    if "PL" not in countries and task.sheet_system is not None:
        return "--sheet-system dotyczy tylko PL (godla CZ wykrywane wzorcem)"
    return None


def require_cz_cutout(task: SimpleNamespace, countries: tuple[str, ...]) -> None:
    """An area reaching CZ needs ``cutout``: CUZK has no sheets for an area."""
    if task.sheet is not None or "CZ" not in countries or task.cutout:
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


def validate_request_bbox(bbox: BBox) -> None:
    """Validate parsed bbox coordinates with the same text for CLI and API."""
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


def validate_area_choice(
    sheet: str | None, bbox: BBox | None, geometry: object | None
) -> None:
    """Exactly one area choice and a valid bbox (texts shared by every
    command taking ``--sheet/--bbox/--geometry``; no network)."""
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
    LAZ-only and non-LAZ options. Narrows ``task.min_year``/``max_year``.
    Types of library arguments first (``year="2018"``, ``cutout="no"``:
    ``ValidationError``, no conversion; STANDARDS 11.2).
    """
    validate_area_choice(task.sheet, task.bbox, task.geometry)
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
        raise ValidationError(
            "--output wymagane: katalog wyniku (pliki trafiaja do "
            "<KATALOG>/<produkt>/<segment>/...)"
        )
    if task.sheet is None and task.country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    if task.country is not None and task.country not in _COUNTRIES:
        raise ValidationError(
            f"--country {task.country!r}: nieznana wartosc - dostepne: "
            f"{COUNTRY_CHOICES}"
        )
    if task.sheet_system is not None and task.sheet_system not in _SHEET_SYSTEMS:
        raise ValidationError(
            f"--sheet-system {task.sheet_system!r}: nieznana wartosc - dostepne: "
            f"{SHEET_SYSTEM_CHOICES}"
        )
    if task.horizontal_crs is not None and task.horizontal_crs not in CUTOUT_CRS:
        raise ValidationError(
            f"--horizontal-crs {task.horizontal_crs!r}: nieznana wartosc - "
            f"dostepne: {', '.join(CUTOUT_CRS)}"
        )
    check_per_country(task.resolution, "--resolution")
    check_per_country(task.vertical_crs, "--vertical-crs")
    task.min_year, task.max_year = year_bounds(task.year, task.min_year, task.max_year)
    if task.product != "laz" and task.min_density is not None:
        raise ValidationError(
            f"--min-density dziala tylko z --product laz (podano "
            f"{task.product}); pomin --min-density"
        )
    if task.product == "laz" and task.full_sheet:
        raise ValidationError(
            "--full-sheet dziala tylko z NMT/NMPT/orto (podano laz) - LAZ "
            "nie ma sciezki standardowej ani dowiazania full_sheet/; pomin --full-sheet"
        )
    if task.cutout:
        if task.sheet is not None:
            raise ValidationError(
                "--cutout dziala tylko z --bbox/--geometry; --sheet wyznacza "
                "zasieg i uklad produktu (arkusz PL 1:1 w ukladzie arkusza, "
                "arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce EPSG:3045)"
            )
        if task.product in ("orto", "laz"):
            raise ValidationError(
                "--cutout dziala tylko z --product nmt albo nmpt (wycinek "
                "wysokosci); orto i laz - pobierz bez --cutout"
            )
        if task.horizontal_crs is None:
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
    from the code.
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
    if code_system is not None:
        task.sheet_system = code_system
    elif task.cutout:
        task.sheet_system = "1992"


def is_source_file_request(task: SimpleNamespace) -> bool:
    """An archive format (``--format`` other than ASC): sheets from the index."""
    fmt = _format_of(task)
    return fmt is not None and fmt != "ASC"


def pl_target_scale(task: SimpleNamespace) -> str:
    """Sheet scale of a PL area request: PL-1992 fixed 1:10000, PL-2000 ``scale``."""
    return task.scale if task.sheet_system == "2000" else "1:10000"
