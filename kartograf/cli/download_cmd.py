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
    """Create provider and storage based on product type."""
    from kartograf.download.storage import FileStorage

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(vertical_crs=vertical_crs)
        storage = FileStorage(output_dir, product="nmpt")
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider = GugikOrtoProvider()
        storage = FileStorage(output_dir, product="orto")
    elif product == "laz":
        from kartograf.providers.pl.gugik_laz import GugikLazProvider

        provider = GugikLazProvider(vertical_crs=vertical_crs)
        storage = FileStorage(output_dir, product="laz")
    else:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(vertical_crs=vertical_crs, resolution=resolution)
        storage = FileStorage(output_dir, resolution=resolution)

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

    Returns
    -------
    int
        0 = OK, 1 = blad (komunikat juz wypisany na stderr)
    """
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
    wyjatkiem: ``ValidationError`` (np. ``--target-crs`` z godlem) albo
    ``ParseError`` (godlo pasujace wzorcem do TM33/SM5, ale niepoprawne —
    np. nieparzyste kilometry). Dyspozycja jest ostatnim miejscem, w ktorym
    moga one zostac zamienione na kod wyjscia zamiast tracebacku; galaz PL
    lapie dokladnie te sama pare w ``cmd_download``.
    """
    try:
        return _cmd_download_cz(args, bbox=bbox, parent_request=parent_request)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _resolve_cz_geometry_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Obwiednia geometrii w ukladzie zadania CZ (None => blad juz wypisany).

    CUZK nie przyjmuje pliku geometrii — zadanie obszarowe to jeden wycinek
    ``exportImage``, wiec geometria sprowadza sie tu do obwiedni (jak
    w przeplywie LAZ, tyle ze w ukladzie czeskim zamiast EPSG:2180).

    Obwiednia liczona jest W UKLADZIE PLIKU, a skok do ukladu docelowego robi
    ``_bbox_to_crs`` (przypieta operacja + probkowanie krawedzi). Transformacja
    z ``core/geometry`` jest tu niedopuszczalna: uzywa domyslnego transformera
    pyproj (ballpark dozwolony, nieznana dokladnosc) i obwiedni z czterech
    naroznikow, ktora przy obroconym Krovaku ucina skrawki obszaru. Jeden skok
    prosto do ukladu zadania oznacza tez, ze ``_cz_download_bbox`` nie
    transformuje juz po raz drugi.
    """
    from pyproj import CRS

    from kartograf.core.geometry import get_overall_bbox, read_source_crs
    from kartograf.providers.cuzk.dmr import _bbox_to_crs
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
        return _bbox_to_crs(bbox, image_sr)
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

    # TYMCZASOWE (Zad. 17 zastapi auto-splitem): tryby obszarowe nie dziela
    # jeszcze zadania per kraj — jawny --country cz idzie w calosci do CUZK
    # (bez parent_request, ktore dolozy Zad. 17), a pl/auto zachowuje sie
    # jak dotychczas, czyli PL.
    if has_bbox or has_geometry:
        if country_flag == "cz":
            if _reject_non_nmt_for_cz(product):
                return 1
            bbox = None
            if has_geometry:
                bbox = _resolve_cz_geometry_bbox(args)
                if bbox is None:
                    return 1  # error already printed
            return _run_cz(args, bbox=bbox)
        if _resolve_pl_sentinels(args):
            return 1

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
    vertical_crs = getattr(args, "vertical_crs", "KRON86")
    resolution = getattr(args, "resolution", "1m")
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

    return 0


def _download_godlo_list(
    manager: DownloadManager,
    godlo_list: list[str],
    skip_existing: bool,
    on_progress,
    max_workers: int,
) -> list[Path]:
    """
    Download a list of godla, using parallel threads when max_workers > 1.

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
    list[Path]
        List of downloaded file paths
    """
    if max_workers <= 1:
        # Sequential download
        all_paths: list[Path] = []
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
        return all_paths

    # Parallel download using ThreadPoolExecutor
    import concurrent.futures
    import threading

    all_paths: list[Path] = []
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

    return all_paths


def _cmd_download_bbox(args: argparse.Namespace) -> int:
    """
    Handle download command in bbox mode.

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
    vertical_crs = getattr(args, "vertical_crs", "KRON86")
    resolution = getattr(args, "resolution", "1m")
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
        all_paths = _download_godlo_list(
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
    server_crs: str | None = None,
    extra: dict | None = None,
) -> None:
    """Best-effort sidecar dla wyniku CZ (blad nie przerywa pobrania).

    `horizontal_crs` to uklad FAKTYCZNEGO wyniku (kafel TM33: EPSG:3045,
    --target-crs: uklad zadany serwerowi), a nie domyslny uklad kanalu.
    """
    import logging

    try:
        from kartograf.providers.cuzk.client import _wkid
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
        # tylko FAKTYCZNA reprojekcja serwerowa — zadanie o uklad natywny kanalu
        # (meta.horizontal_crs przed nadpisaniem) transformacja nie jest
        if server_crs is not None and _wkid(server_crs) != _wkid(meta.horizontal_crs):
            transform["horizontal"] = f"server:{server_crs}"
        pinned = provider.vertical_transform
        if pinned is not None:
            transform["vertical"] = (
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
    """Bbox CZ: jeden wycinek serwerowy plasko w katalogu wyjsciowym."""
    from kartograf.providers.cuzk.client import _wkid
    from kartograf.providers.cuzk.dmr import CUZK_NODATA, _bbox_to_crs
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
    if _wkid(bbox.crs) != _wkid(image_sr):
        # normalizacja PRZED nazwaniem pliku: nazwa niesie wspolrzedne
        # faktycznie zadanego wycinka (w download_bbox to juz no-op)
        bbox = _bbox_to_crs(bbox, image_sr)

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
        server_crs=args.target_crs,
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
    serwerowy), a sidecary pisze warstwa CLI.

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
    Handle download command in geometry mode.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.geometry set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    from kartograf.core.geometry import find_sheets_for_geometry

    filepath = Path(args.geometry)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
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
    vertical_crs = getattr(args, "vertical_crs", "KRON86")
    resolution = getattr(args, "resolution", "1m")
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
        all_paths = _download_godlo_list(
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

    return 0
