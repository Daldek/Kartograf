"""Validation of the data choices of a ``download_data`` request (Z1).

Moved from the CLI: every rule that decides whether a request is valid lives
here, with the texts the CLI printed after ``Error:`` (they name the CLI
flags, because the CLI passes them 1:1 as ``ValidationError``). Values may be
plain (one value for every country of the request) or per country
(``{"pl": "1m", "cz": "2m"}``; the CLI parses ``pl=1m,cz=2m`` into it).
Nothing here touches the network.
"""

from collections.abc import Mapping
from types import SimpleNamespace

from kartograf.download.campaigns import validate_year_bounds
from kartograf.download.cz_sheets import RESOLUTION_CZ, cz_sheet_resolution
from kartograf.exceptions import ValidationError
from kartograf.providers.pl import require_nmt_vertical_crs

# Admissible values named in messages (also the CLI --help texts).
PRODUCT_CHOICES = (
    "nmt (Numeryczny Model Terenu; PL i CZ), nmpt (Numeryczny Model Pokrycia "
    "Terenu; PL, tylko 1m), orto (ortofotomapa RGB; PL), laz (chmura punktow "
    "LIDAR; PL)"
)
COUNTRY_CHOICES = (
    "pl (GUGiK), cz (CUZK), auto (kraje wg prostokatnych obwiedni PL i CZ; "
    "obszar w obu krajach daje osobne pliki per kraj)"
)
RESOLUTION_PL = "1m (NMT 1 m), 5m (NMT 5 m, tylko --vertical-crs EVRF2007)"
VERTICAL_CRS_PL = (
    "EVRF2007 (PL-EVRF2007-NH, uklad obowiazujacy), KRON86 (PL-KRON86-NH, "
    "uklad historyczny; nie dla NMT 5m)"
)
VERTICAL_CRS_CZ = (
    "Bpv (natywny uklad CUZK), EVRF2007 (transformacja z Bpv, "
    "ok. +0,11..+0,15 m, rosnaco S->N)"
)
SYSTEM_CHOICES = (
    "1992 (godla PL-1992, arkusze 1:10000), 2000 (godla PL-2000, strefy "
    "EPSG:2176-2179; wymaga --scale)"
)
SCALE_2000_CHOICES = (
    "1:5000, 1:2000, 1:1000, 1:500 (GUGiK publikuje arkusze PL-2000 najczesciej "
    "w 1:2000, takze w 1:1000 i 1:5000)"
)
# PL-2000 sheet scales GUGiK can publish below the 1:10000 frame.
SCALES_2000 = ("1:5000", "1:2000", "1:1000", "1:500")

CZ_ONLY_NMT = "--product {product} dla CZ bedzie dostepny w etapie 2 - teraz tylko nmt"
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
    """``ValidationError`` for a per-country mapping with unknown or empty keys."""
    if raw is None or isinstance(raw, str):
        return
    keys = [k.strip().lower() for k in raw]
    if (
        any(k not in _COUNTRY_KEYS for k in keys)
        or len(set(keys)) != len(keys)
        or any(not str(v).strip() for v in raw.values())
    ):
        shown = ",".join(f"{k}={v}" for k, v in raw.items())
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


def pl_option_error(
    task: SimpleNamespace,
    *,
    sheet_system: str | None = None,
    sheet_scale: str | None = None,
    countries: tuple[str, ...] = ("PL",),
) -> str | None:
    """Error text for the PL data choices of the request (``None`` = valid).

    ``sheet_system``/``sheet_scale`` describe a sheet request (system and
    scale of the code); ``None`` = area request (bbox/geometry).
    """
    product = task.product
    resolution = country_value(task.resolution, "PL")
    vertical_crs = country_value(task.vertical_crs, "PL")
    target_crs = task.target_crs
    res_hint = _per_country_hint(task.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(task.vertical_crs, "--vertical-crs", countries)

    if target_crs is not None and product in ("orto", "laz"):
        return (
            "--target-crs dla PL dziala tylko z --product nmt albo nmpt "
            "(wycinek wysokosci z WCS GUGiK; orto i laz - pobierz bez "
            "--target-crs)"
        )
    if product == "nmt":
        if target_crs is not None:
            if resolution not in (None, "1m"):
                return (
                    "wycinki --target-crs sa tylko 1 m (WCS GUGiK); arkusze 5 m: "
                    "pomin --target-crs; wycinek: --resolution 1m albo pomin "
                    "--resolution"
                )
        elif resolution is None:
            return f"--resolution wymagane dla NMT PL: {RESOLUTION_PL}{res_hint}"
        elif resolution not in ("1m", "5m"):
            return (
                f"PL nie ma rozdzielczosci {resolution} - dostepne: "
                f"{RESOLUTION_PL}{res_hint}"
            )
    elif product == "nmpt" and resolution not in (None, "1m"):
        return (
            f"--product nmpt jest dostepny tylko w rozdzielczosci 1m (podano "
            f"{resolution}); pomin --resolution albo podaj 1m"
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
            f"{VERTICAL_CRS_PL}{vcrs_hint}"
        )
    elif vertical_crs not in ("KRON86", "EVRF2007"):
        return (
            f"{vertical_crs} nie jest ukladem wysokosci PL - dostepne: "
            f"{VERTICAL_CRS_PL}{vcrs_hint}"
        )
    elif product == "nmt":
        # the library rule (`require_nmt_vertical_crs`): 5m only in EVRF2007
        try:
            require_nmt_vertical_crs(resolution or "1m", vertical_crs)
        except ValidationError:
            return (
                f"NMT {resolution} (PL) jest dostepny tylko w EVRF2007 - podano "
                f"--vertical-crs {vertical_crs}; uzyj --vertical-crs EVRF2007 "
                f"albo --resolution 1m dla {vertical_crs}"
            )

    if product == "laz":
        return None  # LAZ: per-tile system from WFS, no sheet scale
    system = task.system
    scale = task.scale
    if target_crs is not None:
        if system not in (None, "1992"):
            return (
                "--target-crs nie dziala z --system 2000 - bbox wielostrefowy "
                "dalby arkusze w roznych CRS (2176-2179); wycinek: --system 1992 "
                "albo pomin --system"
            )
        return None
    if sheet_system is None:
        if system is None:
            return f"--system wymagane dla --bbox/--geometry w PL: {SYSTEM_CHOICES}"
        effective = system
    else:
        effective = sheet_system
    if effective == "1992":
        if scale is not None:
            return (
                "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 "
                "tylko w 1:10000 (godlo 7-czlonowe), a grubsze godlo rozwija sie "
                "do 1:10000 samo - pomin --scale"
            )
        return None
    if scale is None and (sheet_system is None or sheet_scale == "1:10000"):
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
    if vertical_crs not in ("Bpv", "EVRF2007"):
        return (
            f"{vertical_crs} nie jest dostepny dla CZ - dostepne: "
            f"{VERTICAL_CRS_CZ}{vcrs_hint}"
        )
    if "PL" not in countries and task.system is not None:
        return "--system dotyczy tylko PL (godla CZ wykrywane wzorcem)"
    return None


def validate_request(task: SimpleNamespace) -> None:
    """Checks of the whole request before anything else (no network).

    Exactly one selection, explicit product/output, country for areas,
    per-country syntax, year bounds (``year`` = ``min_year = max_year``),
    LAZ-only and non-LAZ options. Narrows ``task.min_year``/``max_year``.
    """
    provided = sum(v is not None for v in (task.sheet, task.bbox, task.geometry))
    if provided > 1:
        raise ValidationError("Specify only one of: --sheet, --bbox, or --geometry")
    if provided == 0:
        raise ValidationError("Must specify one of: --sheet, --bbox, or --geometry")
    if task.product is None:
        raise ValidationError(f"--product wymagane: {PRODUCT_CHOICES}")
    if task.output_dir is None:
        raise ValidationError(
            "--output wymagane: katalog wyniku (pliki trafiaja do "
            "<DIR>/<produkt>/<segment>/...)"
        )
    if task.sheet is None and task.country is None:
        raise ValidationError(
            f"--country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}"
        )
    check_per_country(task.resolution, "--resolution")
    check_per_country(task.vertical_crs, "--vertical-crs")
    year = task.year
    if year is not None and (task.min_year is not None or task.max_year is not None):
        raise ValidationError(
            "--year wyklucza sie z --min-year/--max-year "
            "(--year Y to skrot --min-year Y --max-year Y)"
        )
    if year is not None:
        task.min_year = task.max_year = year
    try:
        validate_year_bounds(task.min_year, task.max_year)
    except ValidationError as e:
        raise ValidationError(
            str(e)
            .replace("min_year", "--year" if year is not None else "--min-year")
            .replace("max_year", "--max-year")
        ) from None
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


def campaign_opts_given(task: SimpleNamespace) -> bool:
    """Any PL-only campaign/year choice of the request."""
    return bool(
        task.all_campaigns
        or task.min_year is not None
        or task.max_year is not None
        or task.year is not None
        or task.full_sheet
    )


def reject_campaign_opts_with_target_crs(task: SimpleNamespace) -> None:
    """A PL cutout (WCS, ADR-035) has no year or campaign choice."""
    if task.target_crs is None:
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
            f"{flag} nie dziala z --target-crs - wycinek z WCS GUGiK ma "
            "kompozycje lotow serwera (bez wyboru roku); rok danych: pobierz "
            "arkusze bez --target-crs"
        )
    if task.all_campaigns:
        raise ValidationError(
            "--all-campaigns nie dziala z --target-crs - wycinek z WCS "
            "GUGiK ma jedna kompozycje lotow serwera; wszystkie kampanie: "
            "pobierz arkusze bez --target-crs"
        )
    if task.full_sheet:
        raise ValidationError(
            "--full-sheet nie dziala z --target-crs - wycinek pochodzi "
            "z WCS GUGiK, nie z arkuszy"
        )


def resolve_pl_options(
    task: SimpleNamespace,
    *,
    sheet_system: str | None = None,
    sheet_scale: str | None = None,
) -> None:
    """Validate the PL choices and narrow ``task`` to the plain PL values.

    Called on the PL branch only, on a COPY of the request (the CZ branch
    keeps its own values). Single-valued choices are filled in: NMPT and the
    ``target_crs`` cutout are 1m only, the cutout is PL-1992 only, a sheet
    request takes its system from the code.
    """
    error = pl_option_error(task, sheet_system=sheet_system, sheet_scale=sheet_scale)
    if error is not None:
        raise ValidationError(error)
    resolution = country_value(task.resolution, "PL")
    if resolution is None and (task.product == "nmpt" or task.target_crs is not None):
        resolution = "1m"
    task.resolution = resolution
    task.vertical_crs = country_value(task.vertical_crs, "PL")
    if sheet_system is not None:
        task.system = sheet_system
    elif task.target_crs is not None:
        task.system = "1992"


def pl_target_scale(task: SimpleNamespace) -> str:
    """Sheet scale of a PL area request: PL-1992 fixed 1:10000, PL-2000 ``scale``."""
    return task.scale if task.system == "2000" else "1:10000"
