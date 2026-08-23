"""
``kartograf download`` command (godlo / bbox / geometry / LAZ modes).
"""

import argparse
import sys
from pathlib import Path

from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, DownloadProgress
from kartograf.exceptions import DownloadError, ParseError, ValidationError


def create_progress_callback(quiet: bool = False):
    """
    Create a progress callback for download operations.

    Parameters
    ----------
    quiet : bool
        If True, suppress output

    Returns
    -------
    callable
        Progress callback function
    """
    if quiet:
        return None

    def on_progress(progress: DownloadProgress) -> None:
        """Print progress bar and status."""
        bar_width = 30
        filled = int(bar_width * progress.current / max(progress.total, 1))
        bar = "=" * filled + "-" * (bar_width - filled)

        status_icon = {
            "downloading": "↓",
            "completed": "✓",
            "skipped": "○",
            "failed": "✗",
        }.get(progress.status, " ")

        line = (
            f"\r[{bar}] {progress.current}/{progress.total} "
            f"{status_icon} {progress.godlo}"
        )

        # Pad to overwrite previous longer lines
        line = line.ljust(80)

        if progress.status in ("completed", "failed"):
            print(line, flush=True)
        else:
            print(line, end="", flush=True)

    return on_progress


def _create_provider_and_storage(product, output_dir, vertical_crs, resolution):
    """
    Create provider and storage based on product type.

    LAZ has a separate flow (`_cmd_download_laz`) and never reaches this
    helper — `cmd_download` short-circuits it before any provider is built.
    """
    from kartograf.download.storage import FileStorage

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(vertical_crs=vertical_crs)
        storage = FileStorage(output_dir, product="nmpt")
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider = GugikOrtoProvider()
        storage = FileStorage(output_dir, product="orto")
    elif product == "nmt":
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(vertical_crs=vertical_crs, resolution=resolution)
        storage = FileStorage(output_dir, resolution=resolution)
    else:
        raise ValidationError(
            f"Unsupported product for DownloadManager flow: {product} "
            "(LAZ uses _cmd_download_laz)"
        )

    return provider, storage


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


def _resolve_pl_sentinels(args: argparse.Namespace) -> int:
    """
    Rozwiaz sentinele None na polskie domysly; walidacje PL.

    Wywolywane WYLACZNIE na galezi PL, po rozstrzygnieciu kraju — mutuje
    ``args``, wiec argumenty lecace do CZ musza zachowac wartosc ``None``
    (``_cmd_download_cz`` odroznia „nie podano" od wartosci polskiej).

    Obejmuje walidacje par product/resolution i product/vertical_crs
    (symetrycznie do twardych odrzucen galezi CZ) — sprawdzane PRZED
    podstawieniem domyslnych, zeby „nie podano" nie udawalo wyboru
    uzytkownika.

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
    if getattr(args, "target_crs", None) is not None:
        print(
            "Error: --target-crs dziala tylko dla CZ — PL pobiera natywnie w EPSG:2180",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Wywolaj przeplyw CZ, tlumaczac wyjatek zadania na komunikat CLI.

    ``main`` nie lapi wyjatkow, a przeplyw CZ sygnalizuje zle zadanie
    wyjatkiem: ``ValidationError`` (np. ``--target-crs`` z godlem),
    ``ParseError`` (godlo pasujace wzorcem do TM33/SM5, ale niepoprawne —
    np. nieparzyste kilometry) albo ``TransformError`` (normalizacja bboxa
    do ukladu zadania nie ma bezpiecznej operacji). Dyspozycja jest ostatnim
    miejscem, w ktorym moga one zostac zamienione na kod wyjscia zamiast
    tracebacku; galaz PL lapie te same wyjatki w ``cmd_download``.
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
    """Komunikat bledu transformacji (z remedium, gdy jest); zawsze zwraca 1."""
    remedy = getattr(error, "remedy", None)
    print(
        f"Error: {error}" + (f" Remedium: {remedy}" if remedy else ""),
        file=sys.stderr,
    )
    return 1


# wkidy ukladow, w ktorych CUZK wydaje dane — zadanie w nich podane musi
# opuscic Krovaka przypieta operacja, zanim dotknie go cokolwiek polskiego
_CZ_CRS_WKIDS = frozenset({"5514", "3045"})


def _bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Bbox w WGS84 — wspolny uklad rozpoznawania krajow i przycinania.

    Uzywa transformacji z ``core/geometry`` (obwiednia z naroznikow): sluzy
    do ROZPOZNANIA kraju i przyciecia do jego obwiedni, a nie do zadania
    pobrania. Przypieta operacja (``_country_bbox`` -> ``bbox_to_crs``)
    obowiazuje przy OPUSZCZANIU ukladow czeskich (Krovak/UTM33N) — dla
    przycietego bboxa PL skok WGS84->EPSG:2180 idzie swiadomie domyslnym
    (niepinowanym) transformerem pyproj, patrz ``_country_bbox``.
    """
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox

    if bbox.crs == "EPSG:4326":
        return bbox
    return _transform_bbox(
        bbox.min_x,
        bbox.min_y,
        bbox.max_x,
        bbox.max_y,
        CRS.from_user_input(bbox.crs),
        "EPSG:4326",
    )


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


def _country_bbox(
    bbox: BBox, code: str, *, auto: bool, cz_crs: str = "EPSG:5514"
) -> BBox:
    """
    Czesc bboxa dla kraju w ukladzie jego zadania.

    Tryb ``auto`` przycina bbox do obwiedni kraju (w WGS84) i podaje wynik
    w ukladzie roboczym: CZ — ``cz_crs`` (Krovak albo ``--target-crs``), PL —
    uklad zadania bez zmian (zachowuje strefe PL-2000 i zerowy dryf). Jawny
    ``--country`` NIE przycina niczego (uzytkownik zna zasieg swojego zadania).

    Gdy przyciecie nic nie zmienia, transformowany jest ORYGINALNY bbox —
    jeden skok z ukladu zadania zamiast dwoch (przez WGS84).

    Zadanie podane w ukladzie czeskim, ale kierowane do PL (``--bbox-crs
    EPSG:5514`` z ``--country pl`` albo z auto-splitem), opuszcza Krovaka
    OD RAZU i wylacznie przypieta operacja: dalsze kroki (przyciecie, wybor
    arkuszy) pracuja juz w EPSG:2180, wiec selekcja arkuszy GUGiK nigdy nie
    wynika z niepinowanej transformacji Krovaka.
    """
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_country

    if code != "CZ" and wkid(bbox.crs) in _CZ_CRS_WKIDS:
        bbox = bbox_to_crs(bbox, "EPSG:2180")

    if not auto:
        return bbox

    wgs = _bbox_to_wgs84(bbox)
    extent = get_country(code).extent_wgs84
    clipped = (
        max(wgs.min_x, extent.min_x),
        max(wgs.min_y, extent.min_y),
        min(wgs.max_x, extent.max_x),
        min(wgs.max_y, extent.max_y),
    )
    if clipped == (wgs.min_x, wgs.min_y, wgs.max_x, wgs.max_y):
        source = bbox  # przyciecie bylo no-opem
    else:
        source = BBox(*clipped, "EPSG:4326")

    target = cz_crs if code == "CZ" else bbox.crs
    if wkid(source.crs) == wkid(target):
        return source
    if code == "CZ":
        # do ukladu czeskiego wylacznie przypieta operacja z probkowaniem
        # krawedzi (obraz prostokata w Krovaku ma krzywe boki)
        return bbox_to_crs(source, target)
    return _transform_bbox(
        source.min_x,
        source.min_y,
        source.max_x,
        source.max_y,
        CRS.from_user_input(source.crs),
        target,
    )


def _build_parent_request(bbox: BBox, countries: tuple[str, ...]) -> dict:
    """
    Opis zadania obszarowego do ``extra.parent_request`` sidecarow.

    Grupuje pliki jednego zadania bbox/geometry (takze te lezace po roznych
    stronach granicy): niesie ORYGINALNY bbox zadania — przed przycieciem per
    kraj — jego uklad i kraje faktycznie pobrane w tym wywolaniu.

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
    zadania faktycznie niejednoznaczne (np. ``--resolution 2m`` albo
    ``--target-crs``, ktore nie maja odpowiednika po stronie PL) albo jawny
    ``--country``, ktorego CLI nie nadpisuje.
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
        (
            "PL" in countries and getattr(args, "target_crs", None) is not None,
            "--target-crs dziala tylko dla CZ — PL pobiera natywnie w EPSG:2180",
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
    * ``--resolution 2m``, ``--vertical-crs Bpv`` i ``--target-crs`` sa czeskie,
      wiec rozstrzygaja co najwyzej w druga strone (dzis: blad walidacji).
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

    parent_request = _build_parent_request(bbox, countries)
    cz_crs = getattr(args, "target_crs", None) or "EPSG:5514"

    results: list[tuple[str, int]] = []
    for code in countries:
        try:
            part = _country_bbox(bbox, code, auto=auto, cz_crs=cz_crs)
        except TransformError as e:
            return _print_transform_error(e)
        if code == "CZ":
            rc = _run_cz(args, bbox=part, parent_request=parent_request)
        else:
            # KOPIA args: _resolve_pl_sentinels mutuje Namespace (None->"1m"),
            # co zatrulo by galaz CZ; kopia uniezaleznia od kolejnosci krajow
            pl_args = argparse.Namespace(**vars(args))
            if filepath is not None:
                rc = _download_pl_geometry(pl_args, filepath, parent_request)
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
    # przy dotychczasowym `max(exit_codes)`.
    if auto and len(results) > 1 and 0 in exit_codes and max(exit_codes) != 0:
        failed = [code for code, rc in results if rc != 0]
        ok = [code for code, rc in results if rc == 0]
        print(
            f"Warning: nie pobrano danych z {', '.join(failed)} dla tego "
            "obszaru (brak pokrycia albo awaria zrodla — patrz Error wyzej) "
            f"— pobrano {', '.join(ok)} "
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
        remedy = getattr(e, "remedy", None)
        print(
            f"Error: {e}" + (f" Remedium: {remedy}" if remedy else ""), file=sys.stderr
        )
        return None


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

    country_flag = getattr(args, "country", "auto")
    product = getattr(args, "product", "nmt")

    if has_godlo:
        system = detect_system(args.godlo)
        # rejestr konczy sie fallbackiem pl1992 (zawsze pasuje) — None tylko
        # gdyby rejestr byl pusty
        system_id = system.id if system is not None else "pl1992"
        system_country = system.country if system is not None else "PL"
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
            return _run_cz(args)
        if _resolve_pl_sentinels(args):
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

    workers = getattr(args, "workers", 4)

    provider, storage = _create_provider_and_storage(
        product, output_dir, vertical_crs, resolution
    )
    manager = DownloadManager(
        output_dir=output_dir,
        provider=provider,
        storage=storage,
        # provider juz przeszedl korekte "5m => EVRF2007" w fabryce — przekazujemy
        # jego faktyczna wartosc, zeby manager nie ostrzegal drugi raz
        vertical_crs=getattr(provider, "vertical_crs", vertical_crs),
        resolution=resolution,
        max_workers=workers,
    )

    skip_existing = not args.force
    on_progress = create_progress_callback(args.quiet)

    try:
        if args.scale:
            # Download hierarchy
            if not args.quiet:
                count = manager.count_sheets(args.godlo, args.scale)
                print(
                    f"Downloading {count} sheets from {args.godlo} to {args.scale} "
                    f"(resolution: {resolution})"
                )
                print()

            paths = manager.download_hierarchy(
                args.godlo,
                args.scale,
                skip_existing=skip_existing,
                on_progress=on_progress,
            )

            if not args.quiet:
                print()
                print(f"Downloaded {len(paths)} files to {output_dir}")
        else:
            # Download single sheet (may expand to hierarchy for non-1:10000)
            if not args.quiet:
                print(f"Downloading {args.godlo} (resolution: {resolution})...")

            result = manager.download_sheet(
                args.godlo,
                skip_existing=skip_existing,
                on_progress=on_progress,
            )

            if not args.quiet:
                if isinstance(result, list):
                    print()
                    print(f"Downloaded {len(result)} files to {output_dir}")
                else:
                    print(f"Downloaded to {result}")

    except DownloadError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Hierarchia polyka porazki pojedynczych arkuszy (raportuje je przez
    # `on_progress`), wiec kod wyjscia bierzemy z podsumowania managera.
    # `None` znaczy „bez hierarchii" — pojedynczy arkusz 1:10000 nie wypelnia
    # `last_result` i tam sukces = brak wyjatku.
    summary = manager.last_result
    if summary is not None and summary.failed:
        print(
            f"\nError: {len(summary.failed)} of {summary.total} sheets failed "
            f"to download (see messages above)",
            file=sys.stderr,
        )
        return 1

    return 0


def _expands_to_hierarchy(godlo: str) -> bool:
    """
    True, gdy ``DownloadManager.download_sheet`` rozwinie godlo do hierarchii.

    Lustro warunku z ``download_sheet`` (godla PL-2000 pobierane bezposrednio,
    PL-1992 grubsze niz 1:10000 rozwijane do arkuszy 1:10000). CLI musi znac
    ten warunek przed wywolaniem, bo tylko rozwiniecie wypelnia
    ``manager.last_result`` — a zebranie go z puli watkow nie jest bezpieczne
    (patrz ``_download_godlo_list``). Niepoprawne godlo zglosi
    ``download_sheet`` — tu odpowiadamy False i nie dublujemy walidacji.
    """
    try:
        parser = SheetParser(godlo)
    except (ParseError, ValidationError):
        return False
    return parser.uklad != "2000" and parser.scale != "1:10000"


def _download_godlo_list(
    manager: DownloadManager,
    godlo_list: list[str],
    skip_existing: bool,
    on_progress,
    max_workers: int,
) -> tuple[list[Path], list[str]]:
    """
    Download a list of godla, using parallel threads when max_workers > 1.

    Godla grubsze niz 1:10000 rozwijaja sie w ``download_sheet`` do
    ``download_hierarchy``, ktora polyka porazki pojedynczych arkuszy i zdaje
    z nich sprawe wylacznie przez ``manager.last_result``. Ten atrybut jest
    JEDEN na managera i kasowany na wejsciu do kazdego ``download_sheet``,
    wiec z puli watkow nie da sie go przypisac do wlasciwego godla. Dlatego
    lista, ktorej godla sie rozwijaja, idzie petla sekwencyjna — rownoleglosc
    nie ginie, bo to ``download_hierarchy`` pobiera wtedy arkusze na
    ``max_workers`` watkach (i znika zwielokrotnienie watkow: dotad bylo ich
    ``max_workers`` razy ``max_workers``). Pula watkow zostaje dla list
    arkuszy 1:10000, gdzie ``last_result`` i tak jest zawsze ``None``.

    Parameters
    ----------
    manager : DownloadManager
        Configured download manager
    godlo_list : list[str]
        List of godlo identifiers to download
    skip_existing : bool
        Whether to skip already-downloaded files
    on_progress : callable or None
        Progress callback
    max_workers : int
        Number of parallel download threads

    Returns
    -------
    tuple[list[Path], list[str]]
        Downloaded file paths and godla arkuszy, ktorych nie udalo sie pobrac
        (puste, gdy wszystko sie powiodlo). Niepusta druga pozycja jest juz
        zgloszona na stderr — wywolujacy ma z niej zrobic kod wyjscia 1.
    """
    expands = any(_expands_to_hierarchy(godlo) for godlo in godlo_list)

    if max_workers <= 1 or expands:
        # Sequential download
        all_paths: list[Path] = []
        failed: list[str] = []
        total = 0
        for godlo in godlo_list:
            result = manager.download_sheet(
                godlo,
                skip_existing=skip_existing,
                on_progress=on_progress,
            )
            if isinstance(result, list):
                all_paths.extend(result)
            else:
                all_paths.append(result)

            summary = manager.last_result
            if summary is None:
                total += 1  # pojedynczy arkusz 1:10000 — sukces bez hierarchii
            else:
                total += summary.total
                failed.extend(summary.failed)

        _report_failed_sheets(failed, total)
        return all_paths, failed

    # Parallel download using ThreadPoolExecutor.
    # Tu zaden godlo sie nie rozwija, wiec `last_result` zostaje None i nie ma
    # czego zbierac — porazka pojedynczego arkusza leci wyjatkiem.
    import concurrent.futures
    import threading

    all_paths = []
    lock = threading.Lock()

    def _download_one(godlo: str) -> list[Path]:
        result = manager.download_sheet(
            godlo,
            skip_existing=skip_existing,
            on_progress=on_progress,
        )
        if isinstance(result, list):
            return result
        return [result]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_godlo = {
            executor.submit(_download_one, godlo): godlo for godlo in godlo_list
        }
        for future in concurrent.futures.as_completed(future_to_godlo):
            godlo = future_to_godlo[future]
            try:
                paths = future.result()
                with lock:
                    all_paths.extend(paths)
            except (DownloadError, ValidationError):
                raise

    return all_paths, []


def _report_failed_sheets(failed: list[str], total: int) -> None:
    """Wypisz na stderr arkusze, ktorych hierarchia nie zdolala pobrac."""
    if not failed:
        return
    print(
        f"Error: {len(failed)} of {total} sheets failed: {', '.join(failed)}",
        file=sys.stderr,
    )


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
    # Parse bbox string
    try:
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("BBOX must have 4 values")
        bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
    except ValueError as e:
        print(f"Error: Invalid bbox format: {e}", file=sys.stderr)
        print("Expected: min_x,min_y,max_x,max_y (e.g., 419000,230000,426000,237000)")
        return 1

    return _dispatch_area(args, bbox)


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
    """
    if _resolve_pl_sentinels(args):
        return 1

    target_scale = args.scale or "1:10000"

    # Find sheets covering the bbox
    try:
        godlo_list = find_sheets_for_bbox(bbox, target_scale, system=args.system)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not godlo_list:
        print("Error: No sheets found for the given bbox", file=sys.stderr)
        return 1

    # Create download manager
    output_dir = Path(args.output)
    # sentinele PL sa juz rozwiazane (`_resolve_pl_sentinels`), a argparse
    # zawsze tworzy oba atrybuty — czytamy je wprost
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    workers = getattr(args, "workers", 4)

    provider, storage = _create_provider_and_storage(
        product, output_dir, vertical_crs, resolution
    )
    manager = DownloadManager(
        output_dir=output_dir,
        provider=provider,
        storage=storage,
        # provider juz przeszedl korekte "5m => EVRF2007" w fabryce — przekazujemy
        # jego faktyczna wartosc, zeby manager nie ostrzegal drugi raz
        vertical_crs=getattr(provider, "vertical_crs", vertical_crs),
        resolution=resolution,
        max_workers=workers,
        sidecar_extra={"parent_request": parent_request},
    )

    skip_existing = not args.force
    on_progress = create_progress_callback(args.quiet)

    if not args.quiet:
        print(
            f"Found {len(godlo_list)} sheets at {target_scale} "
            f"for bbox (resolution: {resolution})"
        )
        if len(godlo_list) <= 10:
            print(f"  Sheets: {', '.join(godlo_list)}")
        else:
            sample = godlo_list[:3] + ["..."] + godlo_list[-2:]
            print(f"  Sheets: {', '.join(sample)}")
        print()

    try:
        all_paths, failed_sheets = _download_godlo_list(
            manager, godlo_list, skip_existing, on_progress, workers
        )

        if not args.quiet:
            print()
            print(f"Downloaded {len(all_paths)} files to {output_dir}")

    except DownloadError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # komunikat wypisal juz `_download_godlo_list` — tu zostaje kod wyjscia
    if failed_sheets:
        return 1

    return 0


def _resolve_laz_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Resolve a godło / --bbox / --geometry input to an EPSG:2180 BBox for LAZ.

    Returns None (after printing an error) if a geometry file is missing.
    Raises ParseError / ValidationError / ValueError on invalid input.
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
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("BBOX must have 4 values: min_x,min_y,max_x,max_y")
        bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
        if bbox.crs != "EPSG:2180":
            from kartograf.providers.cuzk.client import wkid

            if wkid(bbox.crs) in _CZ_CRS_WKIDS:
                # Uklad czeski (Krovak/UTM33N) opuszczany WYLACZNIE przypieta
                # operacja (jak _country_bbox) — niepinowany _transform_bbox
                # (ballpark, nieznana dokladnosc) grozilby zla selekcja kafli
                # LAZ na pasie granicznym.
                from kartograf.providers.cuzk.dmr import bbox_to_crs

                bbox = bbox_to_crs(bbox, "EPSG:2180")
            else:
                from pyproj import CRS

                from kartograf.core.geometry import _transform_bbox

                bbox = _transform_bbox(
                    bbox.min_x,
                    bbox.min_y,
                    bbox.max_x,
                    bbox.max_y,
                    CRS.from_user_input(bbox.crs),
                    "EPSG:2180",
                )
        return bbox

    # godło mode — SheetParser validates and transforms to EPSG:2180
    return SheetParser(args.godlo).get_bbox(crs="EPSG:2180")


def _write_laz_sidecar(provider, tile, target: Path, bbox: BBox) -> None:
    """Best-effort sidecar dla kafla LAZ (blad nie przerywa pobrania)."""
    import logging

    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        key = getattr(provider, "descriptor_key", None)
        meta = build_metadata(
            get_source(key if isinstance(key, str) else "pl.gugik.laz"),
            request={
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
            vertical_crs=provider.vertical_crs,
            extra={
                "godlo_kafla": tile.godlo,
                "rok": tile.year,
                "gestosc": tile.density,
                "url": tile.url,
            },
        )
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logging.getLogger(__name__).warning(
            f"Nie udalo sie zapisac sidecara dla {target}: {e}"
        )


def _cmd_download_laz(args: argparse.Namespace) -> int:
    """
    Handle the download command for the LAZ product (area-based via WFS).

    Accepts the same inputs as the other products — a godło (down to 1:10000),
    --bbox/--bbox-crs, or --geometry/--layer — resolves them to an EPSG:2180
    bbox, discovers every intersecting LAZ tile via WFS, and downloads them in
    parallel. One 1:10000 area maps to many LAZ tiles (GUGiK tiles LAZ finer
    than 1:10000); each tile is saved under its own opaque godło.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from kartograf.download.storage import FileStorage
    from kartograf.providers.pl.gugik_laz import GugikLazProvider

    # godlo CZ + laz odpada juz w dyspozycji; tu zostaje jawny --country cz
    # w trybie obszarowym (LAZ omija galezie bbox/geometry w cmd_download)
    if getattr(args, "country", "auto") == "cz":
        print(_CZ_ONLY_NMT_MSG.format(product="laz"), file=sys.stderr)
        return 1
    if _resolve_pl_sentinels(args):
        return 1

    try:
        bbox = _resolve_laz_bbox(args)
    except (ParseError, ValidationError, ValueError) as e:
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
    skip_existing = not args.force

    provider = GugikLazProvider(vertical_crs=vertical_crs)
    storage = FileStorage(output_dir, product="laz")

    if not quiet:
        print(f"Querying GUGiK WFS for LAZ tiles ({vertical_crs})...")
    try:
        tiles = provider.discover_tiles(bbox, year=year, min_density=min_density)
    except (ValueError, DownloadError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not tiles:
        print("Error: No LAZ tiles found for the given area.", file=sys.stderr)
        return 1

    if not quiet:
        print(f"Found {len(tiles)} LAZ tiles. Downloading with {workers} worker(s)...")
        print()

    def _fetch(tile):
        target = storage.get_raw_path(tile.godlo, tile.filename)
        if skip_existing and target.exists():
            return "skip", target, None
        try:
            provider.download(tile.url, target)
            _write_laz_sidecar(provider, tile, target, bbox)
            return "ok", target, None
        except DownloadError as e:
            return "fail", tile, e

    results: list[tuple] = []
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_fetch, t) for t in tiles]
            for future in as_completed(futures):
                results.append(future.result())
                if not quiet:
                    print(f"\r  {len(results)}/{len(tiles)} tiles", end="", flush=True)
    else:
        for tile in tiles:
            results.append(_fetch(tile))
            if not quiet:
                print(f"\r  {len(results)}/{len(tiles)} tiles", end="", flush=True)

    ok = [r for r in results if r[0] == "ok"]
    skipped = [r for r in results if r[0] == "skip"]
    failed = [r for r in results if r[0] == "fail"]

    if not quiet:
        print()
        print(
            f"Downloaded {len(ok)} tiles "
            f"({len(skipped)} skipped) to {output_dir / 'laz'}"
        )
    if failed:
        print(f"Warning: {len(failed)} tiles failed to download", file=sys.stderr)
        for _status, tile, error in failed[:5]:
            print(f"  {tile.godlo}: {error}", file=sys.stderr)
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
    import logging

    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        meta = build_metadata(
            get_source(provider.descriptor_key),
            request=request,
            vertical_crs=provider.vertical_crs,
            capability=capability,
            nodata=nodata,
            extra=extra,
        )
        transform: dict = {}
        for axis, pinned in (
            ("horizontal", provider.horizontal_transform(horizontal_crs)),
            ("vertical", provider.vertical_transform),
        ):
            if pinned is not None:
                transform[axis] = (
                    f"pinned: {pinned.description} ({pinned.accuracy_m} m)"
                )
        meta.transform = transform or None
        meta.horizontal_crs = horizontal_crs
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logging.getLogger(__name__).warning(
            f"Nie udalo sie zapisac sidecara dla {target}: {e}"
        )


def _cz_download_godlo(args, provider, *, quiet: bool, skip_existing: bool) -> int:
    """Godlo CZ: kafel TM33 (exportImage) lub arkusz SM5 (openzu) do FileStorage."""
    import logging

    from kartograf.core.parser_registry import detect_system
    from kartograf.download.storage import FileStorage
    from kartograf.sources.registry import get_source

    godlo = args.godlo
    system = detect_system(godlo)
    descriptor = get_source(provider.descriptor_key)
    storage = FileStorage(args.output, subdir=descriptor.storage_subdir)
    target = storage.get_raw_path(godlo, f"{godlo}{descriptor.default_extension}")

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped {godlo} - already exists at {target}")
        return 0

    if not quiet:
        print(f"Downloading {godlo} (CZ, resolution: {provider.resolution})...")
    try:
        provider.download(godlo, target)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    is_sm5 = system is not None and system.id == "cz_sm5"
    extra: dict = {}
    if is_sm5:
        try:
            info = provider.sheet_index.sm5_sheet(godlo)
            if info.name is not None:
                extra["mapname"] = info.name
            if info.podil is not None:
                extra["podil"] = info.podil
        except Exception as e:  # noqa: BLE001 — dane wazniejsze niz metadane
            logging.getLogger(__name__).warning(
                f"Sidecar {godlo} bez PODIL (blad indeksu): {e}"
            )
    _write_cz_sidecar(
        provider,
        target,
        request={"godlo": godlo},
        capability="sheet_files" if is_sm5 else "bbox_raster",
        # arkusz SM5 przychodzi w Krovaku, kafel TM33 w siatce UTM33/ETRS89
        horizontal_crs="EPSG:5514" if is_sm5 else "EPSG:3045",
        nodata=_read_tif_nodata(target),
        extra=extra or None,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


def _cz_download_bbox(
    args,
    provider,
    bbox: BBox | None,
    parent_request: dict | None,
    *,
    quiet: bool,
    skip_existing: bool,
) -> int:
    """Bbox CZ: jeden wycinek `exportImage` plasko w katalogu wyjsciowym.

    Bbox jest normalizowany do ukladu WYNIKU (`--target-crs` albo natywny
    5514) — nazwa pliku niesie wspolrzedne faktycznie zadanego wycinka.
    Do serwera idzie potem zadanie w ukladzie natywnym, a na siatke wyniku
    przenosi je lokalny warp w providerze (ADR-024).
    """
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.dmr import CUZK_NODATA, bbox_to_crs
    from kartograf.sources.registry import get_source

    if bbox is None:
        try:
            parts = [float(x.strip()) for x in args.bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("BBOX must have 4 values")
            bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
        except ValueError as e:
            print(f"Error: Invalid bbox format: {e}", file=sys.stderr)
            return 1

    image_sr = args.target_crs or "EPSG:5514"
    if wkid(bbox.crs) != wkid(image_sr):
        # normalizacja PRZED nazwaniem pliku: nazwa niesie wspolrzedne
        # faktycznie zadanego wycinka (w download_bbox to juz no-op)
        bbox = bbox_to_crs(bbox, image_sr)

    descriptor = get_source(provider.descriptor_key)
    coords = "_".join(
        format(v, ".10g") for v in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    )
    target = Path(args.output) / (
        f"{descriptor.storage_subdir}_{coords}{descriptor.default_extension}"
    )

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped - already exists at {target}")
        return 0

    if not quiet:
        print(f"Downloading CZ bbox ({provider.resolution}, {image_sr})...")
    try:
        provider.download_bbox(bbox, target)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    nodata = _read_tif_nodata(target)
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
        Gotowy bbox — pomija parsowanie ``args.bbox`` (uzywane przez auto-split
        wieloknajowy, Zad. 17).
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
        Gdy ``--target-crs`` towarzyszy godlu (tryb godlowy jest natywny 1:1).
        Warstwa dyspozycji (``cmd_download``) tlumaczy ten wyjatek na komunikat
        CLI — tak jak inne przeplywy traktuja ValidationError.
    """
    from kartograf.cache import MetadataCache
    from kartograf.providers.cuzk import create_dmr_provider
    from kartograf.transform.crs import TransformError

    resolution = args.resolution or "2m"
    vertical_crs = args.vertical_crs or "Bpv"
    has_godlo = args.godlo is not None and bbox is None

    if resolution == "1m":
        print(
            "Error: CZ nie ma rozdzielczosci 1m — dostepne: 2m (DMR 5G), 5m (DMR 4G)",
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
            "--target-crs dziala tylko z --bbox/--geometry; "
            "tryb godlowy dostarcza dane natywne 1:1"
        )

    cache = MetadataCache()
    try:
        try:
            provider = create_dmr_provider(
                resolution=resolution,
                cache=cache,
                target_crs=None if has_godlo else args.target_crs,
                vertical_crs=vertical_crs,
            )
        except TransformError as e:
            remedy = getattr(e, "remedy", None)
            message = f"Error: {e}" + (f" Remedium: {remedy}" if remedy else "")
            print(message, file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        quiet = args.quiet
        skip_existing = not args.force
        if has_godlo:
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
    i ``--country pl`` licza obwiednie w EPSG:2180: rozstrzyga ona kraje
    i trafia do ``parent_request``, a arkusze PL dalej wyznacza sama geometria
    (per obiekt), nie jej obwiednia.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.geometry set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    from kartograf.core.geometry import get_overall_bbox

    country_flag = getattr(args, "country", "auto")
    if country_flag == "cz":
        if _reject_non_nmt_for_cz(getattr(args, "product", "nmt")):
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
        overall = get_overall_bbox(
            filepath, layer=getattr(args, "layer", None), target_crs="EPSG:2180"
        )
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return _dispatch_area(args, overall, filepath=filepath)


def _download_pl_geometry(
    args: argparse.Namespace, filepath: Path, parent_request: dict
) -> int:
    """
    Polska czesc zadania geometrycznego (arkusze per obiekt, nie z obwiedni).

    ``args`` to KOPIA namespace'u zadania — patrz ``_dispatch_area``.
    """
    from kartograf.core.geometry import find_sheets_for_geometry

    if _resolve_pl_sentinels(args):
        return 1

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

    # Create download manager
    output_dir = Path(args.output)
    # sentinele PL sa juz rozwiazane (`_resolve_pl_sentinels`), a argparse
    # zawsze tworzy oba atrybuty — czytamy je wprost
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    workers = getattr(args, "workers", 4)

    provider, storage = _create_provider_and_storage(
        product, output_dir, vertical_crs, resolution
    )
    manager = DownloadManager(
        output_dir=output_dir,
        provider=provider,
        storage=storage,
        # provider juz przeszedl korekte "5m => EVRF2007" w fabryce — przekazujemy
        # jego faktyczna wartosc, zeby manager nie ostrzegal drugi raz
        vertical_crs=getattr(provider, "vertical_crs", vertical_crs),
        resolution=resolution,
        max_workers=workers,
        sidecar_extra={"parent_request": parent_request},
    )

    skip_existing = not args.force
    on_progress = create_progress_callback(args.quiet)

    if not args.quiet:
        print(
            f"Found {len(godlo_list)} sheets at {target_scale} "
            f"for geometry {filepath.name} (resolution: {resolution})"
        )
        if len(godlo_list) <= 10:
            print(f"  Sheets: {', '.join(godlo_list)}")
        else:
            sample = godlo_list[:3] + ["..."] + godlo_list[-2:]
            print(f"  Sheets: {', '.join(sample)}")
        print()

    try:
        all_paths, failed_sheets = _download_godlo_list(
            manager, godlo_list, skip_existing, on_progress, workers
        )

        if not args.quiet:
            print()
            print(f"Downloaded {len(all_paths)} files to {output_dir}")

    except DownloadError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # komunikat wypisal juz `_download_godlo_list` — tu zostaje kod wyjscia
    if failed_sheets:
        return 1

    return 0
