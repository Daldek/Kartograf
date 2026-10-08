"""
``kartograf download`` command (godlo / bbox / geometry / LAZ modes).
"""

import argparse
import contextlib
import json
import math
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from kartograf.cli._parser import parse_bbox_arg
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.campaigns import validate_campaign_args
from kartograf.download.manager import (
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    SheetFetch,
)
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.sources.registry import horizontal_crs_for_godlo


class _ProgressPrinter:
    """Callback paska postepu; ``pending`` = ostatnia linia bez konca linii.

    Przy ``--workers > 1`` ``pending`` odzwierciedla ostatni zapis (najwyzej
    zbedny albo brakujacy ``\\n`` przed ``Error:``).
    """

    def __init__(self) -> None:
        self.pending = False

    def __call__(self, progress: DownloadProgress) -> None:
        """Print progress bar and status."""
        bar_width = 30
        filled = int(bar_width * progress.current / max(progress.total, 1))
        bar = "=" * filled + "-" * (bar_width - filled)

        status_icon = {
            "downloading": "↓",
            "completed": "✓",
            "skipped": "○",
            "failed": "✗",
            # D11: arkusz bez danych u zrodla (morze, obszar za granica) to
            # oczekiwany stan, nie awaria — inna ikona niz porazka pobrania
            "no_coverage": "∅",
        }.get(progress.status, " ")

        line = (
            f"\r[{bar}] {progress.current}/{progress.total} "
            f"{status_icon} {progress.godlo}"
        )

        # Pad to overwrite previous longer lines
        line = line.ljust(80)

        if progress.status in ("completed", "failed", "no_coverage"):
            print(line, flush=True)
            self.pending = False
        else:
            print(line, end="", flush=True)
            self.pending = True


def create_progress_callback(quiet: bool = False):
    """
    Create a progress callback for download operations.

    Parameters
    ----------
    quiet : bool
        If True, suppress output

    Returns
    -------
    callable or None
        Progress callback (``None`` przy ``quiet``)
    """
    if quiet:
        return None
    return _ProgressPrinter()


def _error_lead(on_progress) -> str:
    """``"\\n"`` tylko gdy pasek postepu zostal bez konca linii (bez pustej linii)."""
    return "\n" if getattr(on_progress, "pending", False) is True else ""


def _create_provider_and_storage(
    product, output_dir, vertical_crs, resolution, cache=None
):
    """
    Create provider and storage based on product type.

    ``cache`` (``MetadataCache`` albo ``None``) trafia do providera: rekordy
    skorowidza GUGiK sa czytane i zapisywane wylacznie z cache (N6; CLI:
    ``--force`` = cache w trybie ``refresh``, patrz ``_pl_metadata_cache``).

    LAZ has a separate flow (`_cmd_download_laz`) and never reaches this
    helper — `cmd_download` short-circuits it before any provider is built.
    """
    from kartograf.download.storage import storage_for_provider

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(vertical_crs=vertical_crs, cache=cache)
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider = GugikOrtoProvider(cache=cache)
    elif product == "nmt":
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution, cache=cache
        )
    else:
        raise ValidationError(
            f"Unsupported product for DownloadManager flow: {product} "
            "(LAZ uses _cmd_download_laz)"
        )

    storage = storage_for_provider(
        output_dir, provider, resolution=resolution, vertical_crs=vertical_crs
    )
    return provider, storage


@contextlib.contextmanager
def _pl_metadata_cache(args: argparse.Namespace) -> Iterator[object | None]:
    """
    ``MetadataCache`` toru PL na czas jednego zadania (N6; wzor: tor CZ).

    ``--force`` = ``MetadataCache(refresh=True)`` (E14): rekordy skorowidza
    NIE sa czytane, ale swiezo wybrany rekord (i potwierdzony brak pokrycia)
    jest ZAPISYWANY — kolejny przebieg bez ``--force`` dostaje nowy rekord,
    a nie stary sprzed zmiany kampanii (do wygasniecia TTL 7 d). Cache jest
    otwierany w cwd i zamykany po zadaniu (``close()`` czysci wygasle wpisy).
    """
    from kartograf.cache import MetadataCache

    cache = MetadataCache(refresh=bool(args.force))
    try:
        yield cache
    finally:
        cache.close()


def _product_label(product: str, resolution: str | None) -> str:
    """Etykieta zadania w komunikatach: orto nie ma rozdzielczosci (K5)."""
    if product == "orto":
        return "product: orto"
    return f"resolution: {resolution}"


def _print_sheet_list(
    godla: list[str], target_scale: str, *, what: str, label: str
) -> None:
    """Naglowek listy arkuszy PL (wycinek i tryb listy, D15): do 10 godel
    w calosci, dluzsza lista jako 3 pierwsze + ``...`` + 2 ostatnie."""
    print(f"Found {len(godla)} sheets at {target_scale} for {what} ({label})")
    sample = godla if len(godla) <= 10 else godla[:3] + ["..."] + godla[-2:]
    print(f"  Sheets: {', '.join(sample)}")
    print()


_CZ_ONLY_NMT_MSG = (
    "Error: --product {product} dla CZ bedzie dostepny w etapie 2 — teraz tylko nmt"
)


def _reject_non_nmt_for_cz(product: str) -> bool:
    """
    True (po komunikacie na stderr), gdy produkt CZ jest inny niz ``nmt``.

    Guard zyje w warstwie dyspozycji — przeplyw ``_cmd_download_cz`` zaklada
    juz rozstrzygniety produkt.
    """
    if product == "nmt":
        return False
    print(_CZ_ONLY_NMT_MSG.format(product=product), file=sys.stderr)
    return True


def _campaign_opts(args: argparse.Namespace) -> tuple[str, int | None]:
    """``(campaigns, min_year)`` — getattr, bo testy buduja Namespace recznie."""
    return getattr(args, "campaigns", "newest"), getattr(args, "min_year", None)


def _reject_campaign_opts_without_pl(
    args: argparse.Namespace, countries: tuple[str, ...]
) -> bool:
    """
    Opcje kampanii (``--campaigns all``, ``--min-year``) dotycza tylko PL.

    Jedna regula dla wszystkich punktow wejscia CLI (ADR-030, errata (j) Q9
    i errata 2 N-3): bez PL wsrod krajow -> ``Error:`` i True (przed siecia);
    PL i CZ -> ``Info:`` raz, False (CZ pobierane dalej, biezaca wersja);
    brak opcji albo sama PL -> False, cisza. Komunikaty na stderr (``-q`` ich
    nie tlumi). Opcje kampanii celowo NIE wchodza do ``_pl_only_flags`` —
    inaczej ``auto`` zwezaloby obszar przygraniczny do PL.
    """
    campaigns, min_year = _campaign_opts(args)
    if campaigns == "newest" and min_year is None:
        return False
    if "PL" not in countries:
        print(
            "Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year "
            "dotycza tylko PL",
            file=sys.stderr,
        )
        return True
    if "CZ" in countries:
        print(
            "Info: --campaigns/--min-year dotycza tylko czesci PL "
            "(CZ: biezaca wersja danych CUZK)",
            file=sys.stderr,
        )
    return False


def _reject_campaign_opts_with_target_crs(args: argparse.Namespace) -> bool:
    """
    Wycinek PL ``--target-crs`` + ``--campaigns all``/``--min-year`` = blad.

    Errata (j) Q2: wycinek sklada jedna kampanie na arkusz, a jego nazwa nie
    niesie granicy roku. True (po ``Error:`` na stderr) przed siecia.
    Wolana wylacznie w ``_dispatch_area`` (jedyna droga do wycinka PL), przed
    galezia CZ; godlo z ``--target-crs`` odrzuca wczesniej straz godla.
    """
    if getattr(args, "target_crs", None) is None:
        return False
    campaigns, min_year = _campaign_opts(args)
    if campaigns == "all":
        print(
            "Error: --campaigns all nie dziala z --target-crs — wycinek sklada "
            "jedna kampanie na arkusz; laczenie kampanii: narzedzie 0.7.1",
            file=sys.stderr,
        )
        return True
    if min_year is not None:
        print(
            "Error: --min-year nie dziala z --target-crs — nazwa wycinka nie "
            "niesie granicy roku",
            file=sys.stderr,
        )
        return True
    return False


def _resolve_pl_sentinels(args: argparse.Namespace) -> int:
    """
    Rozwiaz sentinele None na polskie domysly; walidacje PL.

    Wywolywane WYLACZNIE na galezi PL, po rozstrzygnieciu kraju — mutuje
    ``args``, wiec argumenty lecace do CZ musza zachowac wartosc ``None``
    (``_cmd_download_cz`` odroznia „nie podano" od wartosci polskiej).

    Obejmuje walidacje par product/resolution i product/vertical_crs
    (symetrycznie do twardych odrzucen galezi CZ) oraz wylaczen
    ``--target-crs`` (produkt != nmt, ``--system 2000`` — ADR-027)
    — sprawdzane PRZED podstawieniem domyslnych, zeby „nie podano" nie
    udawalo wyboru uzytkownika.

    Returns
    -------
    int
        0 = OK, 1 = blad (komunikat juz wypisany na stderr)
    """
    product = getattr(args, "product", "nmt")
    if product == "nmpt" and getattr(args, "resolution", None) == "5m":
        print(
            "Error: --product nmpt jest dostepny tylko w rozdzielczosci 1m (podano 5m)",
            file=sys.stderr,
        )
        return 1
    if product == "orto" and getattr(args, "vertical_crs", None) is not None:
        print(
            "Error: --vertical-crs nie dotyczy --product orto "
            "(ortofotomapa nie ma ukladu pionowego)",
            file=sys.stderr,
        )
        return 1

    target_crs = getattr(args, "target_crs", None)
    if target_crs is not None and product in ("nmpt", "orto", "laz"):
        print(
            "Error: --target-crs w 0.7.0 dziala tylko z --product nmt "
            "(nmpt/orto — etap 2; laz to chmura punktow, nie raster)",
            file=sys.stderr,
        )
        return 1
    if target_crs is not None and getattr(args, "system", None) == "2000":
        print(
            "Error: --target-crs nie dziala z --system 2000 — bbox "
            "wielostrefowy dalby arkusze w roznych CRS (2176-2179), "
            "mozaika miedzystrefowa to etap 2; uzyj domyslnego --system 1992",
            file=sys.stderr,
        )
        return 1

    args.resolution = getattr(args, "resolution", None) or "1m"
    args.vertical_crs = getattr(args, "vertical_crs", None) or "EVRF2007"
    args.system = getattr(args, "system", None) or "1992"

    if args.resolution == "2m":
        print(
            "Error: PL nie ma rozdzielczosci 2m — dostepne: 1m, 5m (2m to DMR 5G w CZ)",
            file=sys.stderr,
        )
        return 1
    if args.vertical_crs == "Bpv":
        print(
            "Error: Bpv to uklad czeski — dla PL dostepne: KRON86, EVRF2007",
            file=sys.stderr,
        )
        return 1
    if product == "nmt":
        # D11: jedna regula (`nmt_vertical_crs`), jeden skutek — korekta;
        # CLI pokazuje ja jawnie (stderr, jak inne Info:), dalej leci juz
        # pion FAKTYCZNY, wiec fabryka/manager/wycinek nic nie koryguja.
        from kartograf.providers.pl import nmt_vertical_crs

        actual = nmt_vertical_crs(args.resolution, args.vertical_crs, log=False)
        if actual != args.vertical_crs:
            print(
                f"Info: NMT 5m (PL) jest dostepny tylko w {actual} — "
                f"--vertical-crs {args.vertical_crs} zamieniony na {actual}",
                file=sys.stderr,
            )
            args.vertical_crs = actual
    return 0


def _run_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Wywolaj przeplyw CZ, tlumaczac wyjatek zadania na komunikat CLI.

    Przeplyw CZ sygnalizuje zle zadanie wyjatkiem: ``ValidationError`` (np.
    ``--target-crs`` z godlem), ``ParseError`` (godlo pasujace wzorcem do
    TM33/SM5, ale niepoprawne — np. nieparzyste kilometry) albo
    ``TransformError`` (normalizacja bboxa do ukladu zadania nie ma
    bezpiecznej operacji). ``main`` ma bariere (``KartografError`` ->
    ``Error: ...``, kod 1), ale wyjatek wyciekajacy stad przerwalby petle
    krajow ``_dispatch_area`` — pod ``--country auto`` sukces drugiego kraju
    nie dalby juz kodu 0 (ADR-023 pkt 4-5). Dlatego sa tlumaczone tutaj;
    galaz PL lapie te same wyjatki w ``cmd_download``.
    """
    from kartograf.transform.crs import TransformError

    try:
        return _cmd_download_cz(args, bbox=bbox, parent_request=parent_request)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except TransformError as e:
        return _print_transform_error(e)


def _print_transform_error(error: Exception) -> int:
    """Komunikat bledu transformacji (z remedium, gdy jest); zawsze zwraca 1.

    Jedyne miejsce formatu ``Error: <blad> Remedium: <remedium>`` w CLI;
    wyjatek bez atrybutu ``remedy`` daje samo ``Error: <blad>``.
    """
    remedy = getattr(error, "remedy", None)
    print(
        f"Error: {error}" + (f" Remedium: {remedy}" if remedy else ""),
        file=sys.stderr,
    )
    return 1


def _bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Bbox w WGS84 — wspolny uklad rozpoznawania krajow i przycinania.

    Domyslny transformer pyproj (``core.bbox.transform_bbox``, obwiednia
    z zageszczonych krawedzi): sluzy do ROZPOZNANIA kraju i przyciecia do jego
    obwiedni, a nie do zadania pobrania. Przypieta operacja (``_country_bbox``
    -> ``bbox_to_crs``) obowiazuje przy OPUSZCZANIU ukladow czeskich
    (Krovak/UTM33N) — dla przycietego bboxa PL skok WGS84->EPSG:2180 idzie
    swiadomie domyslnym (niepinowanym) transformerem pyproj, patrz
    ``_country_bbox``.
    """
    from kartograf.core.bbox import transform_bbox

    return transform_bbox(bbox, "EPSG:4326")


def _countries_for_bbox(bbox: BBox) -> tuple[str, ...]:
    """
    Kody krajow, ktorych ``extent_wgs84`` przecina bbox (posortowane).

    Obwiednie krajow sa prostokatami, wiec pas przygraniczny jednego kraju
    potrafi lezec wewnatrz prostokata sasiada (np. Opolszczyzna wewnatrz
    obwiedni CZ) — auto-split zada wtedy obu zrodel, a nie zgaduje granicy.
    """
    from kartograf.sources.registry import all_countries

    wgs = _bbox_to_wgs84(bbox)
    hits = [
        profile.code
        for profile in all_countries()
        if (
            wgs.min_x < profile.extent_wgs84.max_x
            and wgs.max_x > profile.extent_wgs84.min_x
            and wgs.min_y < profile.extent_wgs84.max_y
            and wgs.max_y > profile.extent_wgs84.min_y
        )
    ]
    return tuple(sorted(hits))


@dataclass(frozen=True)
class CountryPart:
    """Czesc zadania obszarowego dla jednego kraju (``_country_bbox``).

    ``clipped`` wymienia krawedzie WGS84 faktycznie przyciete do obwiedni
    kraju (``"W"``, ``"S"``, ``"E"``, ``"N"``; puste = bbox bez zmian) —
    ``_dispatch_area`` robi z tego ``Info:`` (S3).
    """

    bbox: BBox
    clipped: tuple[str, ...] = ()


# krawedz -> (pole BBox, czy przyciecie podnosi minimum, jednostka)
_EDGES = (
    ("W", "min_x", True, "E"),
    ("S", "min_y", True, "N"),
    ("E", "max_x", False, "E"),
    ("N", "max_y", False, "N"),
)


def _deg(value: float, unit: str) -> str:
    """``54,90°N`` — stopnie z przecinkiem dziesietnym (komunikaty PL)."""
    return f"{value:.2f}".replace(".", ",") + f"°{unit}"


def _country_bbox(
    bbox: BBox, code: str, *, auto: bool, cz_crs: str = "EPSG:5514"
) -> CountryPart:
    """
    Czesc bboxa dla kraju w ukladzie jego zadania.

    Tryb ``auto`` przycina bbox do obwiedni kraju (w WGS84) i podaje wynik
    w ukladzie roboczym: CZ — ``cz_crs`` (Krovak albo ``--target-crs``), PL —
    uklad zadania bez zmian (zachowuje strefe PL-2000 i zerowy dryf). Jawny
    ``--country`` NIE przycina niczego (uzytkownik zna zasieg swojego zadania).
    Przyciete krawedzie wracaja w ``CountryPart.clipped`` — komunikat
    ``Info:`` wypisuje ``_dispatch_area`` (S3).

    Gdy przyciecie nic nie zmienia, transformowany jest ORYGINALNY bbox —
    jeden skok z ukladu zadania zamiast dwoch (przez WGS84).

    PL po przycieciu (S3): tylko krawedzie z ``clipped`` biora wartosc
    z transformacji przycietego prostokata (obwiednia zakrzywionej krawedzi
    kraju — konserwatywna na zewnatrz), pozostale zostaja wartoscia
    oryginalu 1:1. Obwiednia CALEGO przycietego prostokata poszerzala
    nietkniete krawedzie o dziesiatki metrow (Rozewie: W 110 / S 38 / E 82 m),
    bo poludnik zadania nie jest linia prosta w EPSG:2180. Czesc CZ jest
    z definicji w innym ukladzie (``bbox_to_crs`` z probkowaniem krawedzi),
    wiec tam poszerzenie jest nieuniknione i uczciwe — bez zmian.

    Zadanie podane w ukladzie czeskim, ale kierowane do PL (``--bbox-crs
    EPSG:5514`` z ``--country pl`` albo z auto-splitem), opuszcza Krovaka
    OD RAZU i wylacznie przypieta operacja: dalsze kroki (przyciecie, wybor
    arkuszy) pracuja juz w EPSG:2180, wiec selekcja arkuszy GUGiK nigdy nie
    wynika z niepinowanej transformacji Krovaka.
    """
    from kartograf.core.bbox import is_czech_crs, transform_bbox
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_country

    if code != "CZ" and is_czech_crs(bbox.crs):
        bbox = bbox_to_crs(bbox, "EPSG:2180")

    if not auto:
        return CountryPart(bbox)

    wgs = _bbox_to_wgs84(bbox)
    extent = get_country(code).extent_wgs84
    clipped = tuple(
        edge
        for edge, attr, is_min, _unit in _EDGES
        if (
            getattr(wgs, attr) < getattr(extent, attr)
            if is_min
            else getattr(wgs, attr) > getattr(extent, attr)
        )
    )
    if not clipped:
        source = bbox  # przyciecie bylo no-opem
    else:
        source = BBox(
            max(wgs.min_x, extent.min_x),
            max(wgs.min_y, extent.min_y),
            min(wgs.max_x, extent.max_x),
            min(wgs.max_y, extent.max_y),
            "EPSG:4326",
        )

    target = cz_crs if code == "CZ" else bbox.crs
    if wkid(source.crs) == wkid(target):
        return CountryPart(source, clipped)
    if code == "CZ":
        # do ukladu czeskiego wylacznie przypieta operacja z probkowaniem
        # krawedzi (obraz prostokata w Krovaku ma krzywe boki)
        return CountryPart(bbox_to_crs(source, target), clipped)
    transformed = transform_bbox(source, target)
    if not clipped:
        return CountryPart(transformed)
    # PL: nietkniete krawedzie 1:1 z oryginalu, przyciete z transformacji
    values = {
        attr: getattr(transformed if edge in clipped else bbox, attr)
        for edge, attr, _is_min, _unit in _EDGES
    }
    return CountryPart(BBox(**values, crs=target), clipped)


def _area_outside_extents(
    wgs: BBox, extents: Sequence[BBox]
) -> tuple[BBox | None, float]:
    """
    Czesc bboxa WGS84 poza WSZYSTKIMI prostokatami ``extents`` (S3).

    Krawedzie prostokatow tna bbox na komorki; komorka, ktorej srodka nie
    przykrywa zaden prostokat, jest utracona (pod ``--country auto`` nikt jej
    nie pobierze). Zwraca obwiednie utraconych komorek (``None`` gdy bbox
    jest w calosci pokryty) i udzial ich powierzchni w powierzchni bboxa
    (0..1; komorki wazone ``cos(szerokosci)``, wiec udzial jest metryczny).

    Sam test krawedzi nie wystarcza: bbox 13-15°E x 53-55°N ma krawedz W
    wewnatrz zakresu dlugosci CZ, ale CZ konczy sie na 51,06°N — utrata
    w narozniku jest widoczna dopiero po podziale na komorki.
    """
    xs = sorted(
        {wgs.min_x, wgs.max_x}
        | {v for e in extents for v in (e.min_x, e.max_x) if wgs.min_x < v < wgs.max_x}
    )
    ys = sorted(
        {wgs.min_y, wgs.max_y}
        | {v for e in extents for v in (e.min_y, e.max_y) if wgs.min_y < v < wgs.max_y}
    )
    total = 0.0
    lost_area = 0.0
    lost: list[tuple[float, float, float, float]] = []
    for x0, x1 in zip(xs, xs[1:], strict=False):
        for y0, y1 in zip(ys, ys[1:], strict=False):
            area = (x1 - x0) * (y1 - y0) * math.cos(math.radians((y0 + y1) / 2))
            total += area
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not any(
                e.min_x <= cx <= e.max_x and e.min_y <= cy <= e.max_y for e in extents
            ):
                lost.append((x0, y0, x1, y1))
                lost_area += area
    if not lost or total <= 0:
        return None, 0.0
    envelope = BBox(
        min(c[0] for c in lost),
        min(c[1] for c in lost),
        max(c[2] for c in lost),
        max(c[3] for c in lost),
        "EPSG:4326",
    )
    return envelope, lost_area / total


def _print_clipping_info(
    bbox: BBox,
    countries: tuple[str, ...],
    parts: dict[str, CountryPart],
    *,
    pl_geometry_sheets: bool = False,
    pl_sheet_list: bool = False,
) -> None:
    """``Info:`` o przycieciu pod ``--country auto`` (S3; stderr, ``-q`` nie tlumi).

    PL --geometry bez wycinka pobiera arkusze z calej geometrii, wiec
    przyciecie jej pomocniczego bboxa nie ogranicza pobierania PL.
    """
    from kartograf.sources.registry import get_country

    for code in countries:
        if code == "PL" and pl_geometry_sheets:
            continue
        part = parts[code]
        if not part.clipped:
            continue
        extent = get_country(code).extent_wgs84
        edges = ", ".join(
            f"{edge}: {_deg(getattr(extent, attr), unit)}"
            for edge, attr, _is_min, unit in _EDGES
            if edge in part.clipped
        )
        if code == "PL" and pl_sheet_list:
            result = (
                "arkusze wyznaczono z przycietego bboxa, sidecar ma "
                "request.sheet; oryginal w extra.parent_request.bbox"
            )
        else:
            result = (
                "plik i request.bbox niosa zasieg przyciety, oryginal "
                "w extra.parent_request.bbox"
            )
        print(
            f"Info: --country auto: czesc {code} przycieta do obwiedni kraju "
            f"({edges}); {result}",
            file=sys.stderr,
        )
    if not any(parts[code].clipped for code in countries):
        return
    if pl_geometry_sheets and "PL" in countries:
        # PL czyta CALA geometrie, wiec rowniez obszar poza prostokatami.
        return
    lost, share = _area_outside_extents(
        _bbox_to_wgs84(bbox), [get_country(c).extent_wgs84 for c in countries]
    )
    if lost is None:
        return
    explicit = "pl" if "PL" in countries else countries[0].lower()
    print(
        f"Info: --country auto: obszar {_deg(lost.min_x, 'E')}-{_deg(lost.max_x, 'E')}"
        f" x {_deg(lost.min_y, 'N')}-{_deg(lost.max_y, 'N')} (~{share * 100:.0f} % "
        "powierzchni zadania) lezy poza zasiegiem PL/CZ i zostal pominiety; "
        f"caly bbox pobiera jawne --country {explicit} (za granica: arkusze "
        "bez danych / nodata)",
        file=sys.stderr,
    )


def _build_parent_request(bbox: BBox, countries: tuple[str, ...]) -> dict:
    """
    Opis zadania obszarowego do ``extra.parent_request`` sidecarow.

    Grupuje pliki jednego zadania bbox/geometry (takze te lezace po roznych
    stronach granicy): niesie ORYGINALNY bbox zadania — przed przycieciem per
    kraj — jego uklad i kraje ODPYTANE w tym wywolaniu (probowane, nie
    pobrane — ADR-023 pkt 3).

    Zwrocony slownik NIE moze byc pozniej mutowany: konsumenci (sidecary CZ,
    ``DownloadManager(sidecar_extra=)``) trzymaja go przez referencje, a plytka
    kopia w managerze nie chroni zagniezdzen.
    """
    return {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "bbox_crs": bbox.crs,
        "countries": list(countries),
    }


_CROSS_COUNTRY_HINT = "uzyj jawnie --country pl albo --country cz"


def _validate_cross_country(
    args: argparse.Namespace, countries: tuple[str, ...]
) -> int:
    """
    Opcje musza byc rozwiazywalne dla KAZDEGO przecietego kraju (0=OK, 1=blad).

    Walidacja idzie PRZED jakimkolwiek pobraniem — inaczej czesc jednego kraju
    zostalaby pobrana, a druga galaz dopiero potem odrzucilaby zadanie
    (czesciowe wykonanie). Zamiast cicho pomijac kraj, CLI podpowiada jawny
    ``--country`` — ale tylko gdy obszar faktycznie przecina wiecej niz jeden
    kraj (przy jednym kraju wybor jest juz rozstrzygniety).

    KOLEJNOSC: pod ``--country auto`` czesc opcji jest juz rozstrzygnieta
    wczesniej (``_pl_only_flags`` w ``_dispatch_area``, ADR-023 pkt 5), wiec
    ``countries`` jest wtedy jednoelementowe i te checki widza wylacznie
    zadania faktycznie niejednoznaczne (np. ``--resolution 2m``, ktore nie ma
    odpowiednika po stronie PL) albo jawny ``--country``, ktorego CLI nie
    nadpisuje.

    ``--target-crs`` NIE jest tu walidowane: od ADR-027 dziala po obu stronach
    granicy (PL: scalony wycinek), wiec zadanie transgraniczne z ta flaga jest
    legalne. Wylaczenia PL (produkt != nmt, ``--system 2000``) sprawdza
    ``_resolve_pl_sentinels``, juz na galezi polskiej.
    """
    product = getattr(args, "product", "nmt")
    resolution = getattr(args, "resolution", None)
    vertical_crs = getattr(args, "vertical_crs", None)
    checks: list[tuple[bool, str]] = [
        (
            "CZ" in countries and product != "nmt",
            f"--product {product} jest dostepny tylko dla PL",
        ),
        (
            "CZ" in countries and resolution == "1m",
            "--resolution 1m nie istnieje dla CZ (dostepne 2m/5m)",
        ),
        (
            "PL" in countries and resolution == "2m",
            "--resolution 2m nie istnieje dla PL (dostepne 1m/5m)",
        ),
        (
            "CZ" in countries and vertical_crs == "KRON86",
            "KRON86 nie jest osiagalny dla CZ (siatki GUGiK niepubliczne)",
        ),
        ("PL" in countries and vertical_crs == "Bpv", "Bpv to uklad czeski"),
        (
            "CZ" in countries and getattr(args, "system", None) is not None,
            "--system dotyczy tylko PL",
        ),
    ]
    hint = f"; {_CROSS_COUNTRY_HINT}" if len(countries) > 1 else ""
    for failed, message in checks:
        if failed:
            print(f"Error: {message}{hint}", file=sys.stderr)
            return 1
    return 0


def _pl_only_flags(args: argparse.Namespace) -> list[str]:
    """
    Opcje zadania, ktore w etapie 1 nie maja zadnego odpowiednika po CZ.

    Sluza rozstrzygnieciu ``--country auto`` (ADR-023 pkt 5): skoro wariant
    istnieje wylacznie dla PL, intencja uzytkownika jest jednoznaczna i lepiej
    wybrac kraj niz odrzucic cale zadanie. Lista jest CELOWO waska:

    * ``--product laz`` nie nalezy do niej mimo bycia PL-owym — ma wlasny
      przeplyw (``_cmd_download_laz``) i nigdy nie dociera do ``_dispatch_area``;
    * ``--resolution 5m`` istnieje po obu stronach granicy (PL 5m, DMR 4G);
    * ``--resolution 2m`` i ``--vertical-crs Bpv`` sa czeskie, wiec rozstrzygaja
      co najwyzej w druga strone (dzis: blad walidacji);
    * ``--target-crs`` od ADR-027 dziala po obu stronach granicy (PL: scalony
      wycinek), wiec nie rozstrzyga kraju w zadna strone;
    * ``--campaigns all``/``--min-year`` (ADR-030) tez nie: obszar PL+CZ
      pobiera CZ w biezacej wersji (``_reject_campaign_opts_without_pl``).
    """
    flags: list[str] = []
    product = getattr(args, "product", "nmt")
    if product in ("nmpt", "orto"):
        flags.append(f"--product {product}")
    if getattr(args, "system", None) is not None:
        flags.append("--system")
    if getattr(args, "vertical_crs", None) == "KRON86":
        flags.append("--vertical-crs KRON86")
    if getattr(args, "resolution", None) == "1m":
        flags.append("--resolution 1m")
    return flags


def _dispatch_area(
    args: argparse.Namespace, bbox: BBox, filepath: Path | None = None
) -> int:
    """
    Rozdziel zadanie obszarowe (bbox albo geometria) na kraje i wykonaj je.

    ``bbox`` to zadanie uzytkownika: podany bbox albo obwiednia geometrii.
    Przy ``filepath`` galaz PL pracuje dalej na pliku (arkusze per obiekt,
    a nie z obwiedni), a bbox sluzy rozpoznaniu krajow i ``parent_request``.

    Komunikaty ``Info:``/``Warning:`` o rozstrzygnieciu kraju i o czesciowym
    sukcesie ida na stderr, wiec ``-q`` (tlumiacy stdout) ich NIE ukrywa —
    tak samo jak komunikatow ``Error:``.
    """
    from kartograf.transform.crs import TransformError

    country_flag = getattr(args, "country", "auto")
    auto = country_flag == "auto"
    countries = _countries_for_bbox(bbox) if auto else (country_flag.upper(),)
    if not countries:
        print(
            "Error: obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
            file=sys.stderr,
        )
        return 1
    # ADR-023 pkt 5 (N6-2): obwiednie krajow sa prostokatami (pkt 4), wiec
    # auto-split wciaga CZ takze do zadan lezacych w calosci w Polsce — a wtedy
    # opcja bez odpowiednika czeskiego przewracala cale polecenie (`--system
    # 2000` pod Raciborzem: kod 1, regresja wzgledem 0.6.1). Taka opcja
    # rozstrzyga wiec kraj, zamiast psuc zadanie; dalej jest to dokladnie jawny
    # `--country pl` (auto=False => bez przycinania do obwiedni). Warunek
    # `len(countries) > 1 and "PL" in countries` zaweza to do obszarow
    # faktycznie spornych: obszar w calosci czeski dostaje nadal komunikat
    # o etapie 2 (nizej), a obszar w calosci polski niczego nie potrzebuje.
    if auto and len(countries) > 1 and "PL" in countries:
        pl_only = _pl_only_flags(args)
        if pl_only:
            print(
                f"Info: --country auto -> pl ({', '.join(pl_only)} dotyczy tylko PL)",
                file=sys.stderr,
            )
            auto = False
            countries = ("PL",)
    product = getattr(args, "product", "nmt")
    # obszar w calosci czeski: komunikat o etapie 2 jest trafniejszy niz
    # podpowiedz "wybierz kraj" — kraj jest juz rozstrzygniety
    if countries == ("CZ",) and _reject_non_nmt_for_cz(product):
        return 1
    if _validate_cross_country(args, countries):
        return 1
    # Wycinek PL + opcje kampanii: jedyne miejsce tej strazy (wycinek PL
    # powstaje tylko stad). Tu, a nie w galezi PL — pod auto CZ idzie PRZED
    # PL (sortowanie), wiec pozniejsza straz przyszlaby po pobraniu CZ; przed
    # Info o kampaniach, zeby odrzucone zadanie nie dostalo Info. Kraje sa
    # juz rozstrzygniete (`_pl_only_flags` wyzej): obszar bez PL odrzuca
    # opcje kampanii, obszar PL+CZ dostaje Info.
    if "PL" in countries and _reject_campaign_opts_with_target_crs(args):
        return 1
    if _reject_campaign_opts_without_pl(args, countries):
        return 1

    parent_request = _build_parent_request(bbox, countries)
    cz_crs = getattr(args, "target_crs", None) or "EPSG:5514"

    # Czesci per kraj PRZED jakimkolwiek pobraniem: bledy transformacji
    # przewracaja zadanie w calosci, a komunikaty o przycieciu (S3) ida
    # jednym blokiem przed praca.
    parts: dict[str, CountryPart] = {}
    for code in countries:
        try:
            parts[code] = _country_bbox(bbox, code, auto=auto, cz_crs=cz_crs)
        except TransformError as e:
            return _print_transform_error(e)
    if auto:
        pl_geometry_sheets = filepath is not None and not getattr(
            args, "target_crs", None
        )
        _print_clipping_info(
            bbox,
            countries,
            parts,
            pl_geometry_sheets=pl_geometry_sheets,
            pl_sheet_list=filepath is None and not getattr(args, "target_crs", None),
        )

    results: list[tuple[str, int]] = []
    for code in countries:
        part = parts[code].bbox
        if code == "CZ":
            rc = _run_cz(args, bbox=part, parent_request=parent_request)
        else:
            # KOPIA args: _resolve_pl_sentinels mutuje Namespace (None->"1m"),
            # co zatrulo by galaz CZ; kopia uniezaleznia od kolejnosci krajow
            pl_args = argparse.Namespace(**vars(args))
            if filepath is not None:
                rc = _download_pl_geometry(pl_args, filepath, parent_request, bbox=part)
            else:
                rc = _download_pl_bbox(pl_args, part, parent_request)
        results.append((code, rc))

    exit_codes = [rc for _, rc in results]
    # A3-2: pod `auto` kraje bierze sie z PROSTOKATNYCH obwiedni (ADR-023
    # pkt 4), wiec zadanie w glebi jednego kraju rutynowo trafia takze do
    # drugiego, ktory danych tam nie ma — to normalny wynik doboru krajow,
    # a nie awaria zadania. Kod 0, ale z ostrzezeniem, zeby porazka jednego
    # kraju na pasie przygranicznym nie zniknela po cichu. Jawny `--country`
    # (uzytkownik sam wskazal zasieg) i porazka WSZYSTKICH krajow zostaja
    # przy dotychczasowym `max(exit_codes)`. Tresc bez zgadywania przyczyny:
    # po D2 kod 1 galezi PL znaczy "blad pobrania albo zero danych" (czesc
    # arkuszy mogla sie pobrac), a szczegoly stoja w Error wyzej.
    if auto and len(results) > 1 and 0 in exit_codes and max(exit_codes) != 0:
        failed = [code for code, rc in results if rc != 0]
        ok = [code for code, rc in results if rc == 0]
        print(
            f"Warning: czesc {', '.join(failed)} zadania zakonczyla sie bledem "
            f"(patrz Error wyzej) — pobrano {', '.join(ok)}; kod 0 "
            "(prostokatne obwiednie krajow, ADR-023 pkt 4-5)",
            file=sys.stderr,
        )
        return 0
    return max(exit_codes)


def _resolve_cz_geometry_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Obwiednia geometrii w ukladzie zadania CZ (None => blad juz wypisany).

    CUZK nie przyjmuje pliku geometrii — zadanie obszarowe to jeden wycinek
    ``exportImage``, wiec geometria sprowadza sie tu do obwiedni (jak
    w przeplywie LAZ, tyle ze w ukladzie czeskim zamiast EPSG:2180).

    Obwiednia liczona jest W UKLADZIE PLIKU, a skok do ukladu docelowego robi
    ``bbox_to_crs`` (przypieta operacja + probkowanie krawedzi). Transformacja
    z ``core/geometry`` jest tu niedopuszczalna: uzywa domyslnego transformera
    pyproj (ballpark dozwolony, nieznana dokladnosc) i obwiedni z czterech
    naroznikow, ktora przy obroconym Krovaku ucina skrawki obszaru. Jeden skok
    prosto do ukladu zadania oznacza tez, ze ``_cz_download_bbox`` nie
    transformuje juz po raz drugi.
    """
    from pyproj import CRS

    from kartograf.core.geometry import get_overall_bbox, read_source_crs
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.transform.crs import TransformError

    filepath = Path(args.geometry)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return None

    layer = getattr(args, "layer", None)
    image_sr = getattr(args, "target_crs", None) or "EPSG:5514"
    try:
        source_crs = read_source_crs(filepath, layer=layer)
        bbox = get_overall_bbox(filepath, layer=layer, target_crs=source_crs.to_wkt())
        if source_crs == CRS.from_user_input(image_sr):
            # plik juz w ukladzie zadania — tylko etykieta, zero transformacji
            return BBox(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, image_sr)
        return bbox_to_crs(bbox, image_sr)
    except (ValidationError, ValueError, TransformError) as e:
        _print_transform_error(e)
        return None


def _geometry_envelope(filepath: Path, layer: str | None) -> BBox:
    """Obwiednia geometrii dla dyspozycji krajow (``--country auto``/``pl``).

    Plik w ukladzie czeskim (EPSG:5514/3045): obwiednia W UKLADZIE PLIKU
    z etykieta KODU EPSG — skok do EPSG:2180 wykona przypieta operacja
    w ``_country_bbox`` (review max 2026-08-30, zn. 4: domyslny transformer
    z ``core/geometry`` przesuwal siatke wyniku o ~1,2 m). Etykieta WKT by nie
    wystarczyla: ``wkid()`` jej nie rozpoznaje i skok przypiety zostalby
    pominiety. Pozostale uklady — jak dotad, wprost do EPSG:2180.
    """
    from kartograf.core.bbox import is_czech_crs
    from kartograf.core.geometry import get_overall_bbox, read_source_crs

    source_crs = read_source_crs(filepath, layer=layer)
    epsg = source_crs.to_epsg()
    if epsg is not None and is_czech_crs(f"EPSG:{epsg}"):
        # obwiednia w ukladzie pliku (tozsamosc — zero transformacji)
        env = get_overall_bbox(filepath, layer=layer, target_crs=source_crs.to_wkt())
        return BBox(env.min_x, env.min_y, env.max_x, env.max_y, f"EPSG:{epsg}")
    return get_overall_bbox(filepath, layer=layer, target_crs="EPSG:2180")


def cmd_download(args: argparse.Namespace) -> int:
    """
    Execute the download command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    has_godlo = args.godlo is not None
    has_bbox = args.bbox is not None
    has_geometry = getattr(args, "geometry", None) is not None

    provided = sum([has_godlo, has_bbox, has_geometry])
    if provided > 1:
        print(
            "Error: Specify only one of: godlo, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    if provided == 0:
        print(
            "Error: Must specify one of: godlo, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    # --- Dyspozycja per kraj: godlo rozstrzyga kraj przez rejestr systemow ---
    from kartograf.core.parser_registry import detect_system

    # ADR-030: --min-year 1900..2100 (i strategia) przed jakakolwiek praca
    campaigns, min_year = _campaign_opts(args)
    try:
        validate_campaign_args(campaigns, min_year)
    except ValidationError as e:
        # komunikat biblioteki nazywa parametr; CLI mowi o fladze
        print(f"Error: {str(e).replace('min_year', '--min-year')}", file=sys.stderr)
        return 1

    country_flag = getattr(args, "country", "auto")
    product = getattr(args, "product", "nmt")

    if has_godlo:
        # rejestr konczy sie fallbackiem pl1992 (zawsze pasuje, nigdy None)
        system = detect_system(args.godlo)
        system_id = system.id
        system_country = system.country
        if country_flag != "auto" and country_flag.upper() != system_country:
            print(
                f"Error: Godlo '{args.godlo}' nalezy do systemu {system_id} "
                f"(kraj {system_country}), a podano --country {country_flag}",
                file=sys.stderr,
            )
            return 1
        if system_country == "CZ":
            if _reject_non_nmt_for_cz(product):
                return 1
            # godlo CZ niezaleznie od `country_flag` (jawne cz albo auto)
            if _reject_campaign_opts_without_pl(args, ("CZ",)):
                return 1
            return _run_cz(args)
        if _resolve_pl_sentinels(args):
            return 1
        if getattr(args, "target_crs", None) is not None:
            print(
                "Error: --target-crs dziala tylko z --bbox/--geometry; godlo "
                "wyznacza zasieg i uklad produktu (arkusz PL 1:1 w ukladzie "
                "godla, arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce "
                "EPSG:3045)",
                file=sys.stderr,
            )
            return 1

    # --- Produkt LAZ: dyskretny przepływ area→WFS→tiles (wszystkie 3 tryby) ---
    if product == "laz":
        return _cmd_download_laz(args)

    # --- Tryb geometry ---
    if has_geometry:
        return _cmd_download_geometry(args)

    # --- Tryb bbox ---
    if has_bbox:
        return _cmd_download_bbox(args)

    # --- Tryb godlo (istniejąca logika) ---
    try:
        # Validate godlo first
        SheetParser(args.godlo)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create download manager with vertical CRS, resolution, and product
    output_dir = Path(args.output)
    # sentinele PL sa juz rozwiazane (`_resolve_pl_sentinels`), a argparse
    # zawsze tworzy oba atrybuty — czytamy je wprost
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    label = _product_label(product, resolution)

    workers = getattr(args, "workers", 4)

    with _pl_metadata_cache(args) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                # pion juz FAKTYCZNY: "5m => EVRF2007" w _resolve_pl_sentinels (D11)
                vertical_crs=vertical_crs,
                resolution=resolution,
                max_workers=workers,
                campaigns=campaigns,
                min_year=min_year,
            )
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        skip_existing = not args.force

        try:
            if args.scale:
                # Download hierarchy
                if not args.quiet:
                    count = manager.count_sheets(args.godlo, args.scale)
                    print(
                        f"Downloading {count} sheets from {args.godlo} to "
                        f"{args.scale} ({label})"
                    )
                    print()

                paths = manager.download_hierarchy(
                    args.godlo,
                    args.scale,
                    skip_existing=skip_existing,
                    on_progress=on_progress,
                )
            else:
                # Download single sheet (may expand to hierarchy for non-1:10000)
                def announce() -> None:
                    # O-3: dopiero gdy rusza pobieranie (nie przy Skipped/Error)
                    if not args.quiet:
                        print(f"Downloading {args.godlo} ({label})...")

                parsed = SheetParser(args.godlo)
                if parsed.uklad != "2000" and parsed.scale != "1:10000":
                    announce()  # godlo grubsze: rozwiniecie do hierarchii

                result = manager.download_sheet(
                    args.godlo,
                    skip_existing=skip_existing,
                    on_progress=on_progress,
                    on_download=announce,
                )
                if not isinstance(result, list):
                    # pojedynczy arkusz 1:10000 / PL-2000: sukces = brak
                    # wyjatku (brak danych = DownloadError, kod 1 — D10).
                    # E15: o skipie mowi manager (`last_sheet`), nie istnienie
                    # sciezki standardowej — dowiazanie moze istniec, a nowa
                    # kampania i tak zostac pobrana. isinstance (I-1): atrapa
                    # Mock() managera ma `last_sheet.skipped` = Mock (prawda).
                    fetch = manager.last_sheet
                    sheet = fetch if isinstance(fetch, SheetFetch) else None
                    if not args.quiet:
                        if campaigns == "all" and sheet is not None:
                            # M-1: jak lista — pliki kampanii, nie arkusz
                            _print_campaign_summary(
                                len(sheet.downloaded), 1, output_dir, len(sheet.reused)
                            )
                        elif sheet is not None and sheet.skipped:
                            print(f"Skipped {args.godlo} - already exists at {result}")
                        else:
                            print(f"Downloaded to {result}")
                    if sheet is not None and sheet.link == "copy":
                        _warn_copied_links([args.godlo])
                    if sheet is not None and sheet.unverified is not None:
                        print(
                            f"Warning: {args.godlo}: skorowidz GUGiK niedostepny "
                            "— uzyto lokalnej kampanii bez sprawdzenia nowszej "
                            f"({sheet.unverified})",
                            file=sys.stderr,
                        )
                    _warn_sheet_sidecars([result])
                    return 0
                paths = result

        except DownloadError as e:
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Hierarchia (--scale albo godlo grubsze niz 1:10000) polyka porazki
    # pojedynczych arkuszy i zdaje z nich sprawe w `last_result` — ten sam
    # finisz co tryb listy arkuszy (D10: arkusze morskie pod godlem 1:50000
    # na wybrzezu to ta sama sytuacja co pod --bbox).
    return _finish_pl_sheets(
        _last_result(manager),
        paths,
        output_dir=output_dir,
        quiet=args.quiet,
        campaigns=campaigns,
    )


def _last_result(manager: DownloadManager) -> DownloadResult:
    """``manager.last_result`` po hierarchii/liscie — zawsze wypelnione (kontrakt)."""
    result = manager.last_result
    if result is None:  # pragma: no cover — kontrakt download_sheets/hierarchy
        raise RuntimeError("DownloadManager nie wypelnil last_result po pobraniu listy")
    return result


def _download_godlo_list(
    manager: DownloadManager,
    godlo_list: list[str],
    skip_existing: bool,
    on_progress,
) -> tuple[list[Path], DownloadResult]:
    """
    Pobierz liste godel jednym ``DownloadManager.download_sheets`` (S2/D2).

    Godla grubsze niz 1:10000 rozwija ``expand_sheets`` (manager), pobranie
    idzie na ``max_workers`` managera, a porazki pojedynczych arkuszy NIE
    przerywaja listy: ``NoCoverageError`` (morze, arkusz za granica) i
    ``DownloadError`` (siec, serwer) laduja w ``DownloadResult`` — kazdy
    arkusz jest probowany niezaleznie od ``--workers``. Kod wyjscia i
    komunikaty robi ``_finish_pl_sheets``.

    Returns
    -------
    tuple[list[Path], DownloadResult]
        Pliki dostepne po zadaniu (pobrane + pominiete jako istniejace)
        i podsumowanie per arkusz (``manager.last_result``).
    """
    paths = manager.download_sheets(
        godlo_list, skip_existing=skip_existing, on_progress=on_progress
    )
    return list(paths), _last_result(manager)


def _warn_copied_links(godla: Sequence[str]) -> None:
    """``Warning:`` o sciezce standardowej jako KOPII kampanii (ADR-030)."""
    shown = ", ".join(godla[:10]) + (" ..." if len(godla) > 10 else "")
    print(
        "Warning: hardlink niedostepny na tym systemie plikow — sciezka "
        f"standardowa jest KOPIA najnowszej kampanii dla {len(godla)} arkuszy "
        f"({shown}) (extra.link=copy)",
        file=sys.stderr,
    )


MAX_HINT_LINES = 5


def _print_coverage_hints(result: DownloadResult) -> None:
    """``Info:`` z podpowiedziami ``NoCoverageError`` (stderr, mimo ``-q``).

    Podpowiedzi buduje provider (``NoCoverageError.hints``); CLI tylko je
    przenosi: bez doslownych duplikatow, w kolejnosci pierwszego wystapienia,
    do ``MAX_HINT_LINES`` linii; reszta to jedna linia z liczba pominietych
    (pelna lista w ``DownloadResult.no_coverage_hints``).
    """
    unique = dict.fromkeys(
        h for hints in result.no_coverage_hints.values() for h in hints
    )
    hints = list(unique)
    for hint in hints[:MAX_HINT_LINES]:
        print(f"Info: {hint}", file=sys.stderr)
    rest = len(hints) - MAX_HINT_LINES
    if rest > 0:
        print(
            f"Info: ... i {rest} innych podpowiedzi "
            "(pelna lista: DownloadResult.no_coverage_hints)",
            file=sys.stderr,
        )


def _print_campaign_summary(
    downloaded: int, sheets: int, output_dir: Path, existed: int
) -> None:
    """Podsumowanie ``--campaigns all`` (lista arkuszy i pojedyncze godlo)."""
    print(
        f"Downloaded {downloaded} campaign files for "
        f"{sheets} sheets to {output_dir} ({existed} already existed)"
    )


def _warn_unverified(unverified: dict[str, str], *, from_sidecar: bool = False) -> None:
    """``Warning:`` o arkuszach z lokalnej kampanii bez sprawdzenia (I-1)."""
    godla = list(unverified)
    shown = ", ".join(godla[:10]) + (" ..." if len(godla) > 10 else "")
    print(
        "Warning: skorowidz GUGiK niedostepny — dla "
        f"{len(godla)} arkuszy uzyto lokalnej kampanii bez sprawdzenia nowszej "
        f"({shown}) ({unverified[godla[0]]})"
        + (" (z sidecara istniejacego wycinka)" if from_sidecar else ""),
        file=sys.stderr,
    )


def _finish_pl_sheets(
    result: DownloadResult,
    paths: list[Path],
    *,
    output_dir: Path,
    quiet: bool,
    campaigns: str = "newest",
) -> int:
    """
    Wspolne podsumowanie i kod wyjscia trybu wielu arkuszy PL (D2/D10).

    Uzywany przez ``--bbox``/``--geometry`` (lista arkuszy) i przez tryb
    godla z hierarchia (``--scale`` albo godlo grubsze niz 1:10000) — ta sama
    semantyka "wiele plikow", te same arkusze morskie pod godlem 1:50000 na
    wybrzezu co pod bboxem. Tolerancja R5 jak w wycinku:

    - wszystko pobrane/pominiete -> 0, cisza;
    - >= 1 plik, reszta bez danych GUGiK (``no_coverage``) -> ``Warning:``
      z lista (do 10 godel), kod 0;
    - >= 1 porazka pobrania (``hard_failures``: siec, serwer) -> ``Error:``
      z PELNA lista i "ponow pobranie", kod 1 (plus ``Warning:`` jw., gdy
      sa tez arkusze bez danych);
    - 0 plikow i wszystkie bez danych -> ``Error:``, kod 1 (nic do pobrania,
      spojnie z wycinkiem: ``ValidationError``).

    Arkusze z niepelnej najnowszej kampanii (sidecar
    ``extra.source.full_sheet: false``) -> ``Warning:`` (E13), kod bez zmian.
    Sciezka standardowa jako KOPIA kampanii (``result.copied``) ->
    ``Warning:``, kod bez zmian. ``campaigns="all"``: podsumowanie liczy
    pliki kampanii (``result.campaign_files``), nie arkusze. Arkusze
    ``newest`` z lokalnej kampanii przy awarii skorowidza
    (``result.unverified``, I-1) -> ``Warning:``, kod bez zmian.

    ``Warning:``/``Error:`` ida na stderr, wiec ``-q`` ich NIE tlumi.
    """
    _warn_sheet_sidecars(paths)
    if result.copied:
        _warn_copied_links(result.copied)
    if result.unverified:
        _warn_unverified(result.unverified)
    if not quiet:
        # pasek postepu konczy "skipped"/"downloading" bez nowej linii
        print()
    if not quiet and paths:
        # O-7: bez pliku i bez skipu (same braki/porazki) podsumowanie 0 = szum
        if campaigns == "all":
            # `campaign_files` = pobrane + lokalne; lokalne osobno
            # (`reused_campaign_files`, podzbior per arkusz)
            files = result.campaign_files
            existed = sum(len(f) for f in result.reused_campaign_files.values())
            total_files = sum(len(f) for f in files.values())
            _print_campaign_summary(
                total_files - existed, len(files), output_dir, existed
            )
        else:
            print(
                f"Downloaded {len(result.succeeded)} files to {output_dir} "
                f"({len(result.skipped)} already existed)"
            )
    total = result.total
    hard = result.hard_failures
    missing = result.no_coverage
    if missing and (paths or hard):
        shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        print(
            f"Warning: GUGiK nie ma danych dla {len(missing)} z {total} arkuszy "
            f"({shown}) — pominiete (morze, obszar za granica); pobrano "
            f"{len(paths)}",
            file=sys.stderr,
        )
        _print_coverage_hints(result)
    if hard:
        print(
            f"Error: {len(hard)} z {total} arkuszy nie pobrano (blad pobrania, "
            f"nie brak danych): {', '.join(hard)} — ponow pobranie",
            file=sys.stderr,
        )
        return 1
    if not paths:
        print(
            f"Error: GUGiK nie ma danych dla zadnego z {total} arkuszy obszaru",
            file=sys.stderr,
        )
        _print_coverage_hints(result)
        return 1
    return 0


def _cmd_download_bbox(args: argparse.Namespace) -> int:
    """
    Handle download command in bbox mode (dyspozycja per kraj).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.bbox set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    # ValidationError (zly format, NaN, min > max) -> `Error: ...` w main
    return _dispatch_area(args, parse_bbox_arg(args.bbox, args.bbox_crs))


def _read_sheet_sidecar(path: Path) -> dict | None:
    """Sidecar ``<plik>.meta.json`` arkusza; ``None`` gdy brak/nieczytelny."""
    sidecar = path.with_name(f"{path.name}.meta.json")
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def _is_partial_sheet(path: Path) -> bool:
    """Sidecar arkusza deklaruje niepelny arkusz (``extra.source.full_sheet``
    ``false``, E13). Best-effort: brak/nieczytelny sidecar = ``False``."""
    try:
        source = (_read_sheet_sidecar(path) or {})["extra"]["source"]
        return source.get("full_sheet") is False
    except (KeyError, TypeError, AttributeError):
        return False


def _sheet_crs_mismatch(path: Path) -> tuple[str, str, str] | None:
    """E17: ``(godlo, uklad_godla, uklad_pliku)`` gdy sidecar arkusza PL ma
    ``horizontal_crs`` (uklad PLIKU, ``pl_sheet_horizontal_crs``) inny niz
    wynika z godla — np. arkusz PL-2000 strefy 7 opublikowany przez GUGiK
    we wspolrzednych EPSG:2180. Best-effort: brak sidecara/godla = ``None``."""
    meta = _read_sheet_sidecar(path)
    if meta is None or meta.get("country") != "PL":
        return None
    request = meta.get("request")
    godlo = request.get("sheet") if isinstance(request, dict) else None
    actual = meta.get("horizontal_crs")
    if not isinstance(godlo, str) or not isinstance(actual, str):
        return None
    try:
        expected = horizontal_crs_for_godlo(godlo)
    except KartografError:
        return None
    if expected == actual:
        return None
    return godlo, expected, actual


def _warn_crs_mismatch_sheets(paths) -> None:
    """E17: ``Warning:`` o arkuszach, ktorych plik jest w innym ukladzie niz
    deklaruje godlo/rekord skorowidza. Kod wyjscia bez zmian; sidecar opisuje
    uklad PLIKU. Czyta sidecary, wiec powtarza sie przy skip."""
    found = [m for m in (_sheet_crs_mismatch(Path(p)) for p in paths) if m]
    if not found:
        return
    found.sort()
    shown = ", ".join(
        f"{godlo} (godlo: {expected}, plik: {actual})"
        for godlo, expected, actual in found[:10]
    ) + (" ..." if len(found) > 10 else "")
    print(
        f"Warning: {len(found)} arkuszy GUGiK opublikowano w innym ukladzie "
        f"niz wskazuje godlo: {shown} — sidecar opisuje uklad pliku "
        "(horizontal_crs); deklaracja rekordu w extra.source.declared_crs",
        file=sys.stderr,
    )


def _warn_sheet_sidecars(paths) -> None:
    """Ostrzezenia CLI z sidecarow arkuszy wyniku: niepelny arkusz (E13)
    i uklad pliku inny niz godla (E17)."""
    _warn_partial_sheets(paths)
    _warn_crs_mismatch_sheets(paths)


def _warn_partial_sheets(paths) -> None:
    """E13: ``Warning:`` o arkuszach z niepelnej najnowszej kampanii GUGiK.

    Regula wyboru (ADR-028: najnowsza kampania, bez preferencji pelnego
    arkusza) zostaje — ostrzezenie tylko ja uwidacznia. Czyta sidecary
    plikow wyniku, wiec dziala takze dla arkuszy pominietych jako istniejace.
    """
    partial = sorted(Path(p).stem for p in paths if _is_partial_sheet(Path(p)))
    if not partial:
        return
    shown = ", ".join(partial[:10]) + (" ..." if len(partial) > 10 else "")
    print(
        f"Warning: najnowsza kampania GUGiK jest niepelna dla {len(partial)} "
        f"arkuszy ({shown}) — skorowidz deklaruje arkusz nie w calosci "
        "wypelniony trescia; plik moze miec duzo nodata/czerni "
        "(extra.source.full_sheet w sidecarze)",
        file=sys.stderr,
    )


def _warn_missing_sheets(missing: tuple[str, ...], *, from_sidecar: bool) -> None:
    """R5: ``Warning:`` o arkuszach bez danych GUGiK w wycinku (stderr, -q nie tlumi).

    Przy pominietym wycinku lista pochodzi z jego sidecara (N4) — ten sam
    komunikat co przy budowie, z dopiskiem o zrodle.
    """
    if not missing:
        return
    shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
    origin = " (z sidecara istniejacego wycinka)" if from_sidecar else ""
    print(
        f"Warning: GUGiK nie ma danych dla {len(missing)} arkuszy wycinka "
        f"({shown}) — w tych miejscach wycinek ma nodata (lista w sidecarze: "
        f"extra.missing_sheets){origin}",
        file=sys.stderr,
    )


def _report_pl_cutout(result, *, from_sidecar: bool) -> None:
    """Komunikaty o tresci wycinka: brak arkuszy (R5), W1 (S5), same nodata (N2),
    arkusze z niepelnej najnowszej kampanii (E13).

    Przy pominietym wycinku wszystkie dane pochodza z jego sidecara
    (``skipped_pl_cutout``) — ostrzezenia powtarzaja sie z dopiskiem o zrodle.
    """
    _warn_missing_sheets(result.missing_sheets, from_sidecar=from_sidecar)
    unverified = getattr(result, "unverified", None)
    if isinstance(unverified, dict) and unverified:
        # I-1: jak lista/godlo; lista pelna w sidecarze (extra.unverified_sheets)
        _warn_unverified(unverified, from_sidecar=from_sidecar)
    origin = " (z sidecara istniejacego wycinka)" if from_sidecar else ""
    if result.off_grid_sheets:
        print(
            f"Info: {len(result.off_grid_sheets)} arkuszy o innej fazie siatki "
            "przeprobkowanych osobno (W1; lista w sidecarze: "
            f"extra.off_grid_sheets){origin}",
            file=sys.stderr,
        )
    partial = tuple(getattr(result, "partial_sheets", ()))
    shown = ", ".join(partial[:10]) + (" ..." if len(partial) > 10 else "")
    if result.all_nodata and partial:
        # C14-b: GUGiK ma dane w starszej kampanii, a najnowsza (wybrana wg
        # ADR-028) jest ucieta — "brak danych GUGiK" bylby mylacy
        print(
            "Warning: wycinek w calosci nodata — najnowsza kampania GUGiK "
            f"jest niepelna dla {len(partial)} arkuszy ({shown}) i nie pokrywa "
            "obszaru zadania (starsza kampania moze miec dane; "
            f"extra.sheet_sources[].full_sheet){origin}",
            file=sys.stderr,
        )
    elif result.all_nodata:
        print(
            "Warning: wycinek w calosci nodata — pobrane arkusze nie wnosza "
            "zadnego piksela w obszarze zadania (brak danych GUGiK / obszar "
            f"poza pokryciem){origin}",
            file=sys.stderr,
        )
    elif partial:
        print(
            f"Warning: najnowsza kampania GUGiK jest niepelna dla {len(partial)} "
            f"arkuszy wycinka ({shown}) — wycinek moze miec w ich obszarze "
            f"nodata (extra.sheet_sources[].full_sheet){origin}",
            file=sys.stderr,
        )


# opis kroku datum w sidecarach sprzed naprawy K2 (EPSG:4829, obszar uzycia:
# Slowacja; tresc przesunieta 1-5 m) — po naprawie tor CZ i wycinek PL -> 5514
# pinuja "S-JTSK to ETRS89 (1)"/"(2)"
_LEGACY_KROVAK_STEP = "S-JTSK to ETRS89 (3)"


def _print_legacy_krovak_info(target: Path) -> None:
    """D12: pomijany plik sprzed naprawy operacji S-JTSK dostaje ``Info:``.

    Czyta sidecar ``<plik>.meta.json`` (best-effort: brak/nieczytelny =
    cisza) i sprawdza ``transform.horizontal``. Bez automatycznej
    przebudowy — uzytkownik decyduje (``--force``).
    """
    sidecar = target.parent / f"{target.name}.meta.json"
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        horizontal = (payload.get("transform") or {}).get("horizontal")
    except (OSError, ValueError, AttributeError):
        return
    if isinstance(horizontal, str) and _LEGACY_KROVAK_STEP in horizontal:
        print(
            f"Info: {target} pochodzi sprzed naprawy operacji S-JTSK (tresc "
            "przesunieta 1-5 m) — pobierz ponownie z --force",
            file=sys.stderr,
        )


def _download_pl_cutout(
    args: argparse.Namespace,
    bbox: BBox,
    parent_request: dict,
    geometry: Path | None = None,
) -> int:
    """Polski wycinek --target-crs (ADR-027): nakladka CLI na download/cutout.py.

    Wolane po ``_resolve_pl_sentinels``. Bledy przygotowania
    (``TransformError``/``ValidationError``), selekcji arkuszy
    (``ValidationError``) i KAZDY blad pobrania lub budowy wycinka (takze
    ``GridMismatchError`` z podpowiedzia innego ``--target-crs``, S5) koncza
    sie kodem 1 z komunikatem, nie tracebackiem: wyjatek wyciekajacy poza
    petle krajow ``_dispatch_area`` zlamalby kontrakt czesciowego sukcesu
    (ADR-023 pkt 4-5). Arkusz bez danych GUGiK nie jest bledem (R5): wycinek
    powstaje z nodata w jego miejscu, a ``Warning:`` na stderr wymienia takie
    arkusze (do 10; pelna lista w sidecarze, ``extra.missing_sheets``) —
    takze przy pominieciu istniejacego wycinka (lista z jego sidecara, N4).
    Wycinek bez ani jednego waznego piksela (N2) = ``Warning:``, kod 0.
    """
    from kartograf.download.cutout import (
        prepare_pl_cutout,
        run_pl_cutout,
        select_pl_cutout_sheets,
        skipped_pl_cutout,
    )
    from kartograf.transform.crs import TransformError

    output_dir = Path(args.output)
    with _pl_metadata_cache(args) as cache:
        provider, storage = _create_provider_and_storage(
            getattr(args, "product", "nmt"),
            output_dir,
            args.vertical_crs,
            args.resolution,
            cache=cache,
        )
        try:
            # fail-fast: operacja przypieta budowana PRZED jakakolwiek siecia
            cutout = prepare_pl_cutout(
                bbox,
                args.target_crs,
                output_dir=output_dir,
                resolution=args.resolution,
                vertical_crs=args.vertical_crs,
            )
        except TransformError as e:
            return _print_transform_error(e)
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if not args.force and cutout.target_path.exists():
            result = skipped_pl_cutout(cutout)
            if not args.quiet:
                print(f"Skipped - already exists at {cutout.target_path}")
            _report_pl_cutout(result, from_sidecar=True)
            _print_legacy_krovak_info(cutout.target_path)
            return 0

        target_scale = args.scale or "1:10000"
        try:
            sheets = select_pl_cutout_sheets(
                cutout,
                geometry=geometry,
                layer=getattr(args, "layer", None),
                scale=target_scale,
            )
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if not args.quiet:
            _print_sheet_list(
                list(sheets.godla),
                target_scale,
                what="bbox" if geometry is None else f"geometry {geometry.name}",
                label=_product_label("nmt", args.resolution),
            )

        if cutout.estimated_bytes >= 2**30:
            # stderr, nie stdout: -q NIE tlumi Info:/Warning: (jak wyzej)
            height, width = cutout.grid_shape
            print(
                f"Info: wycinek ~{cutout.estimated_bytes / 2**30:.1f} GiB "
                f"({width} x {height} px float32)",
                file=sys.stderr,
            )

        on_progress = create_progress_callback(args.quiet)
        try:
            result = run_pl_cutout(
                cutout,
                sheets,
                provider=provider,
                storage=storage,
                max_workers=getattr(args, "workers", 4),
                force=args.force,
                on_progress=on_progress,
                parent_request=parent_request,
            )
        except Exception as e:  # noqa: BLE001 — kod 1 zamiast tracebacku (ADR-023)
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
    if not args.quiet:
        # pasek postepu konczy "skipped" bez nowej linii — jak dotad pusta
        # linia przed podsumowaniem (i przed ostrzezeniem na stderr ponizej)
        print()
    _report_pl_cutout(result, from_sidecar=False)
    if not args.quiet:
        print(f"Downloaded to {result.path}")
    return 0


def _download_pl_bbox(
    args: argparse.Namespace, bbox: BBox, parent_request: dict
) -> int:
    """
    Polska czesc zadania bbox: arkusze GUGiK z sidecarami niosacymi rodzica.

    ``args`` to KOPIA namespace'u zadania (patrz ``_dispatch_area``) — sentinele
    rozwiazywane sa tutaj, zeby nie dotknac argumentow lecacych do CZ.

    ``bbox`` jest juz w ukladzie polskim: zadania podane w ukladzie czeskim
    normalizuje ``_country_bbox`` przypieta operacja (tu drugi, niepinowany
    skok Krovaka bylby wlasnie tym, czego etap zabrania).

    Z ``--target-crs`` (ADR-027) — ``_download_pl_cutout`` (biblioteka
    ``download/cutout.py``): jeden scalony wycinek zamiast listy arkuszy.
    Bez niego — lista arkuszy z tolerancja R5 (``_finish_pl_sheets``, D2).
    """
    if _resolve_pl_sentinels(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request)

    target_scale = args.scale or "1:10000"

    # Find sheets covering the bbox (zero sieci, zero cache)
    try:
        godlo_list = find_sheets_for_bbox(bbox, target_scale, system=args.system)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not godlo_list:
        print("Error: No sheets found for the given bbox", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args, godlo_list, parent_request, what="bbox", target_scale=target_scale
    )


def _download_pl_sheet_list(
    args: argparse.Namespace,
    godlo_list: list[str],
    parent_request: dict,
    *,
    what: str,
    target_scale: str,
) -> int:
    """Tryb listy arkuszy PL (bbox/geometry bez ``--target-crs``): manager + finisz.

    Sentinele PL sa juz rozwiazane (``_resolve_pl_sentinels``), a argparse
    zawsze tworzy oba atrybuty — czytamy je wprost. ``MetadataCache`` zyje
    tylko na czas zadania (N6).
    """
    output_dir = Path(args.output)
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    workers = getattr(args, "workers", 4)
    skip_existing = not args.force
    campaigns, min_year = _campaign_opts(args)

    if not args.quiet:
        _print_sheet_list(
            godlo_list,
            target_scale,
            what=what,
            label=_product_label(product, resolution),
        )

    with _pl_metadata_cache(args) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                # pion juz FAKTYCZNY: "5m => EVRF2007" w _resolve_pl_sentinels (D11)
                vertical_crs=vertical_crs,
                resolution=resolution,
                max_workers=workers,
                sidecar_extra={"parent_request": parent_request},
                campaigns=campaigns,
                min_year=min_year,
            )
            all_paths, result = _download_godlo_list(
                manager, godlo_list, skip_existing, on_progress
            )
        except DownloadError as e:
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    return _finish_pl_sheets(
        result,
        all_paths,
        output_dir=output_dir,
        quiet=args.quiet,
        campaigns=campaigns,
    )


def _resolve_laz_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Resolve a godło / --bbox / --geometry input to an EPSG:2180 BBox for LAZ.

    Returns None (after printing an error) if a geometry file is missing.
    Raises ParseError / ValidationError on invalid input.
    """
    if getattr(args, "geometry", None):
        from kartograf.core.geometry import get_overall_bbox

        filepath = Path(args.geometry)
        if not filepath.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            return None
        return get_overall_bbox(
            filepath, layer=getattr(args, "layer", None), target_crs="EPSG:2180"
        )

    if args.bbox is not None:
        bbox = parse_bbox_arg(args.bbox, args.bbox_crs)
        from kartograf.core.bbox import is_czech_crs, transform_bbox

        if is_czech_crs(bbox.crs):
            # Uklad czeski (Krovak/UTM33N) opuszczany WYLACZNIE przypieta
            # operacja (jak _country_bbox) — niepinowany transformer pyproj
            # (ballpark, nieznana dokladnosc) grozilby zla selekcja kafli
            # LAZ na pasie granicznym.
            from kartograf.providers.cuzk.dmr import bbox_to_crs

            return bbox_to_crs(bbox, "EPSG:2180")
        return transform_bbox(bbox, "EPSG:2180")

    # godło mode — SheetParser validates and transforms to EPSG:2180
    return SheetParser(args.godlo).get_bbox(crs="EPSG:2180")


def _laz_parent_request(args: argparse.Namespace, bbox: BBox) -> dict | None:
    """``extra.parent_request`` kafli LAZ (ADR-023 (f).1, review-2 N15).

    Tylko tryb ``--bbox``/``--geometry`` (godlo: ``None``). Jak w pozostalych
    torach: ``--bbox`` w ukladzie PODANYM (przed transformacja do EPSG:2180),
    ``--geometry`` jako obwiednia EPSG:2180; ``countries`` = ``["PL"]`` — LAZ
    odpytuje tylko GUGiK.
    """
    if args.godlo is not None:
        return None
    if args.bbox is not None:
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
    return _build_parent_request(bbox, ("PL",))


def _laz_tile_label(tile) -> str:
    return f"{tile.godlo} ({tile.year}, {tile.crs})"


def _print_laz_superseded(superseded) -> None:
    """``Info:`` o kaflach pominietych przy wyborze (stderr, takze z ``-q``)."""
    if not superseded:
        return
    print(
        f"Info: pominieto {len(superseded)} kafli LAZ — obszar pokrywaja "
        "nowsze kafle (domyslnie najnowszy rocznik per obszar; starszy "
        "rocznik: --year)",
        file=sys.stderr,
    )
    for entry in superseded:
        if entry.covered_by:
            covering = ", ".join(_laz_tile_label(t) for t in entry.covered_by)
            reason = f"pokryty przez {covering}"
        else:
            reason = "rama kafla nie przecina obszaru (tylko obwiednia WFS)"
        print(f"  {_laz_tile_label(entry.tile)}: {reason}", file=sys.stderr)


def _cmd_download_laz(args: argparse.Namespace) -> int:
    """
    Handle the download command for the LAZ product (area-based via WFS).

    Accepts the same inputs as the other products — a godło (down to 1:10000),
    --bbox/--bbox-crs, or --geometry/--layer — resolves them to an EPSG:2180
    bbox and hands the work to the library (``kartograf.download.laz``):
    ``GugikLazProvider.select_tiles`` (newest tile per area) and
    ``run_laz_download`` (parallel download, sidecars, failures). This
    function only prints and maps the result to an exit code.
    """
    from kartograf.download.laz import NO_TILES_MESSAGE, run_laz_download
    from kartograf.providers.pl.gugik_laz import GugikLazProvider

    # godlo CZ + laz odpada juz w dyspozycji; tu zostaje jawny --country cz
    # w trybie obszarowym (LAZ omija galezie bbox/geometry w cmd_download)
    if getattr(args, "country", "auto") == "cz":
        print(_CZ_ONLY_NMT_MSG.format(product="laz"), file=sys.stderr)
        return 1
    campaigns, min_year = _campaign_opts(args)
    if min_year is not None and getattr(args, "year", None) is not None:
        print("Error: --min-year i --year wykluczaja sie (LAZ)", file=sys.stderr)
        return 1
    if _resolve_pl_sentinels(args):
        return 1

    try:
        bbox = _resolve_laz_bbox(args)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if bbox is None:
        return 1  # error already printed

    # tryb obszarowy: LAZ istnieje tylko dla PL, wiec obszar siegajacy CZ
    # zostalby pobrany po cichu tylko czesciowo (spec 5.7: bez cichego pomijania
    # kraju). Godlo PL jednoznacznie wskazuje kraj — bez guardu.
    if (
        getattr(args, "country", "auto") == "auto"
        and args.godlo is None
        and "CZ" in _countries_for_bbox(bbox)
    ):
        print(
            "Error: --product laz jest dostepny tylko dla PL, a obszar "
            "przecina CZ (LAZ dla CZ: etap 2); uzyj jawnie --country pl",
            file=sys.stderr,
        )
        return 1

    vertical_crs = args.vertical_crs
    year = getattr(args, "year", None)
    min_density = getattr(args, "min_density", None)
    workers = getattr(args, "workers", 4) or 1
    output_dir = Path(args.output)
    quiet = args.quiet

    provider = GugikLazProvider(vertical_crs=vertical_crs)

    if not quiet:
        print(f"Querying GUGiK WFS for LAZ tiles ({vertical_crs})...")
    try:
        selection = provider.select_tiles(
            bbox,
            year=year,
            min_density=min_density,
            campaigns=campaigns,
            min_year=min_year,
        )
    except (ValueError, ValidationError, DownloadError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    _print_laz_superseded(selection.superseded)
    if not selection.tiles:
        # N7: discovery przeszlo (wszystkie roczniki odpowiedzialy), wiec pusta
        # lista to zasieg/filtry, nie awaria WFS
        print(f"Error: {NO_TILES_MESSAGE}", file=sys.stderr)
        return 1

    total = len(selection.tiles)
    if not quiet:
        print(f"Found {total} LAZ tiles. Downloading with {workers} worker(s)...")
        print()

    def _progress(done: int, count: int) -> None:
        if not quiet:
            print(f"\r  {done}/{count} tiles", end="", flush=True)

    result = run_laz_download(
        selection,
        provider=provider,
        bbox=bbox,
        output_dir=output_dir,
        year=year,
        min_density=min_density,
        campaigns=campaigns,
        min_year=min_year,
        max_workers=workers,
        force=args.force,
        on_progress=_progress,
        parent_request=_laz_parent_request(args, bbox),
    )

    if not quiet:
        print()
        print(
            f"Downloaded {len(result.downloaded)} tiles "
            f"({len(result.skipped)} skipped) to {output_dir / 'laz'}"
        )
    if result.failed:
        # Kod 1 => `Error:` (konwencja: `Warning:` tylko przy kodzie 0) i PELNA
        # lista nieudanych kafli do ponowienia — wzor `_finish_pl_sheets` (N6).
        names = ", ".join(f.tile.godlo for f in result.failed)
        print(
            f"Error: {len(result.failed)} z {total} kafli LAZ nie pobrano "
            f"(blad pobrania): {names} — ponow pobranie",
            file=sys.stderr,
        )
        for failure in result.failed:
            print(f"  {failure.tile.godlo}: {failure.error}", file=sys.stderr)
        return 1

    return 0


def _read_tif_nodata(path: Path) -> float | None:
    """Nodata z tagu GeoTIFF (None gdy brak/nieczytelny)."""
    try:
        import rasterio

        with rasterio.open(path) as src:
            return src.nodata
    except Exception:  # noqa: BLE001 — metadane wzbogacone < dane
        return None


def _warn_cz_all_nodata(target: Path, nodata: float | None) -> None:
    """N2: ``Warning:`` gdy raster CZ nie ma ani jednego waznego piksela (kod 0).

    Best-effort jak ``_read_tif_nodata`` — blad odczytu = cisza (mocki
    providera nie zapisuja pliku). Brak tagu nodata: CUZK pisze -9999.
    """
    from kartograf.providers.cuzk.dmr import CUZK_NODATA
    from kartograf.transport.mosaic import has_valid_pixels

    try:
        empty = not has_valid_pixels(target, CUZK_NODATA if nodata is None else nodata)
    except Exception:  # noqa: BLE001 — ostrzezenie nigdy nie przerywa pobrania
        return
    if empty:
        print(
            f"Warning: {target} jest w calosci nodata — obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)",
            file=sys.stderr,
        )


def _write_cz_sidecar(
    provider,
    target: Path,
    *,
    request: dict,
    capability: str,
    horizontal_crs: str,
    nodata: float | None,
    extra: dict | None = None,
) -> None:
    """Best-effort sidecar dla wyniku CZ (blad nie przerywa pobrania).

    `horizontal_crs` to uklad FAKTYCZNEGO wyniku (kafel TM33: EPSG:3045,
    --target-crs: uklad zadany przez uzytkownika), a nie domyslny uklad kanalu.

    Obie pozycje `transform` opisuja PRZYPIETE operacje wykonane lokalnie —
    poziomo i pionowo tak samo (ADR-024). Wczesniej pole poziome niosło
    `"server:EPSG:<kod>"` bez dokladnosci, co ukrywalo blad reprojekcji
    serwerowej (135 m) przed konsumentem sidecara.
    """
    from kartograf.sources.sidecar import emit_sidecar

    emit_sidecar(
        provider.descriptor_key,
        target,
        request=request,
        vertical_crs=provider.vertical_crs,
        horizontal_crs=horizontal_crs,
        pinned_transforms={
            "horizontal": provider.horizontal_transform(horizontal_crs),
            "vertical": provider.vertical_transform,
        },
        capability=capability,
        nodata=nodata,
        extra=extra,
    )


def _cz_download_godlo(args, provider, *, quiet: bool, skip_existing: bool) -> int:
    """Godlo CZ: kafel TM33 (exportImage) lub arkusz SM5 (openzu) do FileStorage."""
    import logging

    from kartograf.core.parser_registry import detect_system
    from kartograf.download.storage import storage_for_provider
    from kartograf.sources.registry import get_source

    godlo = args.godlo
    system = detect_system(godlo)
    descriptor = get_source(provider.descriptor_key)
    storage = storage_for_provider(args.output, provider)
    target = storage.get_raw_path(godlo, f"{godlo}{descriptor.default_extension}")

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped {godlo} - already exists at {target}")
        _print_legacy_krovak_info(target)
        return 0

    if not quiet:
        print(f"Downloading {godlo} (CZ, resolution: {provider.resolution})...")
    try:
        provider.download(godlo, target)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    nodata = _read_tif_nodata(target)
    _warn_cz_all_nodata(target, nodata)
    is_sm5 = system.id == "cz_sm5"
    extra: dict = {}
    if is_sm5:
        try:
            info = provider.sheet_index.sm5_sheet(godlo)
            if info.name is not None:
                extra["mapname"] = info.name
            if info.podil is not None:
                extra["cz_share"] = info.podil
        except Exception as e:  # noqa: BLE001 — dane wazniejsze niz metadane
            logging.getLogger(__name__).warning(
                f"Sidecar {godlo} bez extra.cz_share (PODIL; blad indeksu): {e}"
            )
    _write_cz_sidecar(
        provider,
        target,
        request={"sheet": godlo},
        capability="sheet_files" if is_sm5 else "bbox_raster",
        # arkusz SM5 przychodzi w Krovaku, kafel TM33 w siatce UTM33/ETRS89
        horizontal_crs="EPSG:5514" if is_sm5 else "EPSG:3045",
        nodata=nodata,
        extra=extra or None,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


def _cz_download_bbox(
    args,
    provider,
    bbox: BBox,
    parent_request: dict | None,
    *,
    quiet: bool,
    skip_existing: bool,
) -> int:
    """Bbox CZ: jeden wycinek `exportImage` w `<subdir>/bbox/<coords>.tif`.

    Bbox jest normalizowany do ukladu WYNIKU (`--target-crs` albo natywny
    5514) — nazwa pliku niesie wspolrzedne faktycznie zadanego wycinka.
    Do serwera idzie potem zadanie w ukladzie natywnym, a na siatke wyniku
    przenosi je lokalny warp w providerze (ADR-024).
    """
    from kartograf.download.storage import bbox_cutout_path, prune_empty_dirs
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.dmr import CUZK_NODATA, bbox_to_crs
    from kartograf.sources.registry import get_source

    image_sr = args.target_crs or "EPSG:5514"
    if wkid(bbox.crs) != wkid(image_sr):
        # normalizacja PRZED nazwaniem pliku: nazwa niesie wspolrzedne
        # faktycznie zadanego wycinka (w download_bbox to juz no-op)
        bbox = bbox_to_crs(bbox, image_sr)

    descriptor = get_source(provider.descriptor_key)
    target = bbox_cutout_path(
        args.output,
        descriptor.resolve_subdir(vertical_crs=provider.vertical_crs),
        bbox,
        descriptor.default_extension,
    )

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped - already exists at {target}")
        _print_legacy_krovak_info(target)
        return 0

    if not quiet:
        print(f"Downloading CZ bbox ({provider.resolution}, {image_sr})...")
    # provider tworzy katalogi dopiero przy fetchu — sidecar wymaga ich zawsze
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        provider.download_bbox(bbox, target)
    except (DownloadError, ValidationError) as e:
        # zn. 10: porazka nie zostawia pustego drzewa <segment>/bbox/
        prune_empty_dirs(target.parent, Path(args.output))
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except BaseException:
        prune_empty_dirs(target.parent, Path(args.output))
        raise

    nodata = _read_tif_nodata(target)
    _warn_cz_all_nodata(target, nodata)
    _write_cz_sidecar(
        provider,
        target,
        request={
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
        },
        capability="bbox_raster",
        horizontal_crs=image_sr,
        nodata=nodata if nodata is not None else CUZK_NODATA,
        extra={"parent_request": parent_request} if parent_request else None,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


def _cmd_download_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Handle the download command for Czech (CUZK) sources.

    Wzor: :func:`_cmd_download_laz` — przeplyw poza ``DownloadManager``, bo
    zadanie CZ daje dokladnie jeden plik (kafel TM33, arkusz SM5 albo wycinek
    `exportImage`), a sidecary pisze warstwa CLI.

    Parameters
    ----------
    args : argparse.Namespace
        Sparsowane argumenty (godlo / --bbox / --target-crs / --resolution ...).
    bbox : BBox, optional
        Bbox trybu obszarowego (``_dispatch_area`` podaje go zawsze, takze
        przy jawnym ``--country cz``); ``None`` = tryb godlowy (``args.godlo``).
    parent_request : dict, optional
        Oryginalne zadanie uzytkownika przed podzialem per kraj; trafia do
        ``extra.parent_request`` sidecara.

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)

    Raises
    ------
    ValidationError
        Gdy ``--target-crs`` towarzyszy godlu (godlo wyznacza zasieg i uklad
        produktu: arkusz SM5 1:1 w EPSG:5514, kafel TM33 lokalnym warpem na
        siatce EPSG:3045). Tlumaczy go ``_run_cz`` (wolany z ``cmd_download``
        i ``_dispatch_area``) — tak jak inne przeplywy traktuja
        ValidationError.
    """
    from kartograf.cache import MetadataCache
    from kartograf.core.parser_registry import detect_system
    from kartograf.providers.cuzk import create_dmr_provider
    from kartograf.transform.crs import TransformError

    has_godlo = bbox is None
    # An SM5 sheet is a ready-made DMR 4G file that exists only at 5 m, so the
    # sheet itself determines the resolution; TM33 tiles and bbox cutouts are
    # cut from the service, where 2 m (default) and 5 m are a real choice.
    is_sm5 = has_godlo and detect_system(args.godlo).id == "cz_sm5"
    resolution = args.resolution or ("5m" if is_sm5 else "2m")
    vertical_crs = args.vertical_crs or "Bpv"

    if resolution == "1m":
        print(
            "Error: CZ nie ma rozdzielczosci 1m — dostepne: 2m (DMR 5G), 5m (DMR 4G)",
            file=sys.stderr,
        )
        return 1
    if is_sm5 and resolution != "5m":
        # contradictory request: rejected before the provider (no network)
        # and before the "Downloading" announcement
        print(
            f"Error: Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) — pomin "
            f"--resolution albo podaj 5m; dla {resolution} uzyj godla TM33 "
            f"albo --bbox [godlo: {args.godlo}]",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "system", None) is not None:
        print(
            "Error: --system dotyczy tylko PL (godla CZ wykrywane wzorcem)",
            file=sys.stderr,
        )
        return 1
    if has_godlo and args.target_crs is not None:
        # provider ignoruje target_crs w trybie godlowym — cisza bylaby klamstwem
        raise ValidationError(
            "--target-crs dziala tylko z --bbox/--geometry; godlo wyznacza "
            "zasieg i uklad produktu (arkusz SM5 1:1 w EPSG:5514, kafel TM33 "
            "na siatce EPSG:3045)"
        )

    # D16: --force jak w torze PL — odczyt cache (indeks arkuszy SM5)
    # pominiety, swiezy wpis zapisany
    cache = MetadataCache(refresh=bool(args.force))
    try:
        try:
            provider = create_dmr_provider(
                resolution=resolution,
                cache=cache,
                target_crs=None if has_godlo else args.target_crs,
                vertical_crs=vertical_crs,
            )
        except TransformError as e:
            return _print_transform_error(e)
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        quiet = args.quiet
        skip_existing = not args.force
        if bbox is None:
            return _cz_download_godlo(
                args, provider, quiet=quiet, skip_existing=skip_existing
            )
        return _cz_download_bbox(
            args,
            provider,
            bbox,
            parent_request,
            quiet=quiet,
            skip_existing=skip_existing,
        )
    finally:
        cache.close()


def _cmd_download_geometry(args: argparse.Namespace) -> int:
    """
    Handle download command in geometry mode (dyspozycja per kraj).

    Jawny ``--country cz`` idzie sciezka ``_resolve_cz_geometry_bbox``
    (obwiednia w ukladzie PLIKU + jeden skok przypieta operacja). Tryb auto
    i ``--country pl`` licza obwiednie przez ``_geometry_envelope``: plik
    w ukladzie czeskim (EPSG:5514/3045) zostaje w ukladzie PLIKU (etykieta
    EPSG) i opuszcza Krovaka dopiero w ``_country_bbox`` przypieta operacja,
    pozostale uklady licza obwiednie wprost w EPSG:2180 jak dotad. Wynik
    rozstrzyga kraje i trafia do ``parent_request``, a arkusze PL dalej
    wyznacza sama geometria (per obiekt), nie jej obwiednia.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.geometry set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    country_flag = getattr(args, "country", "auto")
    if country_flag == "cz":
        if _reject_non_nmt_for_cz(getattr(args, "product", "nmt")):
            return 1
        # ta galaz omija `_dispatch_area` — straz kampanii takze tutaj
        if _reject_campaign_opts_without_pl(args, ("CZ",)):
            return 1
        bbox = _resolve_cz_geometry_bbox(args)
        if bbox is None:
            return 1  # error already printed
        return _run_cz(
            args, bbox=bbox, parent_request=_build_parent_request(bbox, ("CZ",))
        )

    filepath = Path(args.geometry)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return 1

    try:
        overall = _geometry_envelope(filepath, getattr(args, "layer", None))
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return _dispatch_area(args, overall, filepath=filepath)


def _download_pl_geometry(
    args: argparse.Namespace,
    filepath: Path,
    parent_request: dict,
    bbox: BBox,
) -> int:
    """
    Polska czesc zadania geometrycznego (arkusze per obiekt, nie z obwiedni).

    ``args`` to KOPIA namespace'u zadania — patrz ``_dispatch_area``.

    ``bbox`` — obwiednia zadania PL (przycieta pod auto), wymagana. Z
    ``--target-crs`` (ADR-027) — ``_download_pl_cutout`` (biblioteka
    ``download/cutout.py``): obwiednia wyznacza siatke i crop wycinka, wiec
    wynik obejmuje CALA obwiednie geometrii, bez maskowania do jej obiektow
    (przy warpie arkusze to suma godel geometrii i obwiedni z zapasem, R-01 —
    ``select_pl_cutout_sheets``). Bez ``--target-crs`` arkusze wyznacza sama
    geometria, a ``bbox`` nie jest uzywany; lista idzie przez
    ``_download_pl_sheet_list`` (tolerancja R5, D2).
    """
    from kartograf.core.geometry import find_sheets_for_geometry

    if _resolve_pl_sentinels(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request, geometry=filepath)

    target_scale = args.scale or "1:10000"
    layer = getattr(args, "layer", None)

    try:
        godlo_list = find_sheets_for_geometry(
            filepath, target_scale=target_scale, layer=layer, system=args.system
        )
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not godlo_list:
        print("Error: No sheets found for the given geometry", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args,
        godlo_list,
        parent_request,
        what=f"geometry {filepath.name}",
        target_scale=target_scale,
    )
