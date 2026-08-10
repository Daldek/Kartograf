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

    # --- Produkt LAZ: dyskretny przepływ area→WFS→tiles (wszystkie 3 tryby) ---
    if getattr(args, "product", "nmt") == "laz":
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

    try:
        bbox = _resolve_laz_bbox(args)
    except (ParseError, ValidationError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if bbox is None:
        return 1  # error already printed

    vertical_crs = getattr(args, "vertical_crs", "EVRF2007")
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
