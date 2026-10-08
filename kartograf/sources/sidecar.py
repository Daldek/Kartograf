"""
Result sidecar for a download: `<full_file_name>.meta.json`.

Contract for consumers (Hydrograf): CRSs, nodata, source, license.
In 0.7.0 the consumer merges cross-border data; merging PL+CZ into one
surface is Kartograf stage 2 (R6). The format is versioned by the `schema` field;
fields are added additively.
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kartograf._version import build_version
from kartograf.core.parser_2000 import ZONE_EPSG
from kartograf.exceptions import DownloadError
from kartograf.sources.descriptor import AccessChannel, SourceDescriptor
from kartograf.sources.registry import (
    PL_1992_CRS,
    horizontal_crs_for_godlo,
    resolve_vertical_crs,
)

logger = logging.getLogger(__name__)

_BBOX_CAPS = {"bbox_raster", "bbox_vector"}


@dataclass(kw_only=True)
class ResultMetadata:
    """Metadata of a single result file."""

    dataset: str  # descriptor key
    country: str
    product: str
    provider: str
    horizontal_crs: str
    vertical_crs: str | None
    vertical_source: str  # "native" | "ellipsoidal" | "server"
    resolution: str | None
    nodata: float | None
    request: dict  # {"sheet": ...} | {"bbox": [...], "bbox_crs": ...}
    license: dict  # {"id","attribution","url"}
    downloaded_at: str  # ISO 8601 UTC
    kartograf_version: str
    transform: dict | None = None  # stage 0: None
    extra: dict = field(default_factory=dict)
    schema: str = "kartograf-meta/1"


def _read_asc_header(path: Path) -> dict[str, float]:
    """Arc/Info ASCII Grid header: {lowercase key: value}; {} if absent."""
    header: dict[str, float] = {}
    try:
        with open(path, encoding="ascii", errors="replace") as f:
            for _ in range(6):
                parts = f.readline().split()
                if len(parts) != 2:
                    continue
                try:
                    header[parts[0].lower()] = float(parts[1])
                except ValueError:
                    continue
    except OSError:
        return {}
    return header


def read_asc_nodata(path: Path) -> float | None:
    """Read NODATA_value from an Arc/Info ASCII Grid header (None if absent)."""
    return _read_asc_header(path).get("nodata_value")


def _file_min_x(path: Path) -> float | None:
    """Raster left edge (x) from the ASC header or rasterio; None if unreadable."""
    suffix = path.suffix.lower()
    if suffix == ".asc":
        header = _read_asc_header(path)
        return header.get("xllcorner", header.get("xllcenter"))
    if suffix in {".tif", ".tiff"}:
        import rasterio  # lazy: an ASC sheet sidecar does not need GDAL

        try:
            with rasterio.open(path) as dataset:
                return float(dataset.bounds.left)
        except (OSError, ValueError):
            return None
    return None


def _crs_from_pl_coordinate(x: float) -> str | None:
    """PL-2000 ma x = strefa * 1e6 + easting (5..8 mln); PL-1992 x < 1e6."""
    if x < 1e6:
        return PL_1992_CRS
    return ZONE_EPSG.get(int(x // 1e6))


def pl_sheet_horizontal_crs(data_path: Path | None, godlo: str) -> str:
    """ACTUAL CRS of a PL sheet file: zone from the sheet code, checked against
    coordinates.

    A PL-2000 sheet code determines the zone (EPSG:2176..2179), PL-1992 -> EPSG:2180.
    When the file is readable and its left edge points to a different CRS (a
    PL-1992 sheet substituted for a PL-2000 sheet code by a pre-0.7.0 cache - K4),
    the sidecar describes the FILE: the CRS from the file is returned, with a warning.
    """
    expected = horizontal_crs_for_godlo(godlo)
    if data_path is None:
        return expected
    x = _file_min_x(Path(data_path))
    actual = _crs_from_pl_coordinate(x) if x is not None else None
    if actual is None or actual == expected:
        return expected
    logger.warning(
        f"Sidecar {data_path}: godlo {godlo} wskazuje {expected}, ale wspolrzedne "
        f"pliku (x = {x:.0f}) sa w {actual} — zapisano uklad pliku"
    )
    return actual


def _select_channel(descriptor: SourceDescriptor, request: dict) -> AccessChannel:
    """Pick the request channel (bbox -> a bbox_* channel, else the first match)."""
    want_bbox = "bbox" in request
    for ch in descriptor.channels:
        has_bbox = bool(ch.capabilities & _BBOX_CAPS)
        if want_bbox == has_bbox:
            return ch
    return descriptor.channels[0]


def _default_horizontal_crs(
    descriptor: SourceDescriptor,
    channel: AccessChannel,
    request: dict,
    data_path: Path | None,
) -> str:
    """Channel CRS; for a PL sheet by sheet code - the file's CRS (PL-2000 zone, N8)."""
    godlo = request.get("sheet")
    if (
        descriptor.country == "PL"
        and "sheet_files" in channel.capabilities
        and isinstance(godlo, str)
    ):
        return pl_sheet_horizontal_crs(data_path, godlo)
    return channel.horizontal_crs


def _select_channel_by_capability(
    descriptor: SourceDescriptor, capability: str
) -> AccessChannel:
    """First channel declaring the capability; KeyError if none."""
    for ch in descriptor.channels:
        if capability in ch.capabilities:
            return ch
    raise KeyError(
        f"Deskryptor '{descriptor.key}' nie ma kanalu z capability '{capability}'"
    )


def build_metadata(
    descriptor: SourceDescriptor,
    *,
    request: dict,
    vertical_crs: str | None = None,
    data_path: Path | None = None,
    transform: dict | None = None,
    extra: dict | None = None,
    capability: str | None = None,
    nodata: float | None = None,
    horizontal_crs: str | None = None,
) -> ResultMetadata:
    """Build metadata from the descriptor + the call context.

    ``horizontal_crs`` (explicit) describes the ACTUAL result's CRS and takes
    precedence over the channel. Without it a PL sheet downloaded by sheet code
    (channel ``sheet_files``) gets the CRS from ``pl_sheet_horizontal_crs``
    - the PL-2000 zone from the sheet code checked against the file's coordinates;
    other results inherit the channel's ``horizontal_crs``.
    """
    if capability is not None:
        channel = _select_channel_by_capability(descriptor, capability)
    else:
        channel = _select_channel(descriptor, request)

    vertical: str | None = None
    if channel.vertical_crs_options and vertical_crs is not None:
        vertical = resolve_vertical_crs(vertical_crs, channel.vertical_crs_options)

    if nodata is None and data_path is not None and data_path.suffix.lower() == ".asc":
        nodata = read_asc_nodata(data_path)

    return ResultMetadata(
        dataset=descriptor.key,
        country=descriptor.country,
        product=descriptor.product,
        provider=descriptor.provider_name,
        horizontal_crs=horizontal_crs
        or _default_horizontal_crs(descriptor, channel, request, data_path),
        vertical_crs=vertical,
        vertical_source=channel.vertical_source,
        resolution=descriptor.resolution,
        nodata=nodata,
        request=request,
        license={
            "id": descriptor.license.id,
            "attribution": descriptor.license.attribution,
            "url": descriptor.license.url,
        },
        transform=transform,
        extra=extra or {},
        downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
    )


def write_sidecar(
    data_path: Path, meta: ResultMetadata, *, atomic: bool = False
) -> Path:
    """Write `<data_path>.meta.json` next to the data file; return the sidecar path.

    ``atomic=False`` (default): IO exceptions are caught and logged as a
    warning (spec section 8) - a missing sidecar never aborts the download;
    on error the returned path points to a file that was NOT created.

    ``atomic=True`` (mandatory sidecar, ADR-030 errata 2 N-1): written to
    ``<name>.meta.json.<pid>_<tid>.tmp`` + ``os.replace``; ``OSError``
    PROPAGATES, the tmp file is cleaned up (never a partial sidecar).
    """
    sidecar_path = data_path.parent / f"{data_path.name}.meta.json"
    if atomic:
        payload = json.dumps(asdict(meta), ensure_ascii=False, indent=2)
        tmp = sidecar_path.with_name(
            f"{sidecar_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
        )
        try:
            tmp.write_text(payload + "\n", encoding="utf-8")
            os.replace(tmp, sidecar_path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return sidecar_path
    try:
        payload = json.dumps(asdict(meta), ensure_ascii=False, indent=2)
        sidecar_path.write_text(payload + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar_path}: {e}")
    return sidecar_path


def pinned_label(pinned) -> str:
    """Pinned operation description for the sidecar ``transform`` field (one format)."""
    return f"pinned: {pinned.description} ({pinned.accuracy_m} m)"


def emit_sidecar(
    descriptor_key: object,
    data_path: Path,
    *,
    request: dict,
    vertical_crs: str | None = None,
    horizontal_crs: str | None = None,
    pinned_transforms: dict | None = None,
    extra: dict | None = None,
    capability: str | None = None,
    nodata: float | None = None,
    required: bool = False,
) -> Path | None:
    """Best-effort result sidecar - the one place of the policy "a sidecar never
    aborts the download" (D7): any build/write exception ends in
    a log warning and ``None``.

    A ``descriptor_key`` that is not a ``str`` (provider without a descriptor, a
    ``Mock`` stand-in) = no sidecar, without a warning. ``pinned_transforms``
    (``{"horizontal": PinnedTransform | None, "vertical": ...}``) goes into
    ``transform`` in the ``pinned_label`` format; ``None`` entries are skipped,
    and an empty result gives ``transform: null``. Other arguments as
    in ``build_metadata`` (``horizontal_crs`` = the ACTUAL result's CRS).

    ``required=True`` (campaign file sidecar, ADR-030 errata 2 N-1): atomic
    write (``write_sidecar(atomic=True)``), and a missing descriptor or
    any build/write exception ends in ``DownloadError`` - the caller
    chooses only the mode, the interpretation of the failure stays here (D7).

    Returns
    -------
    Path or None
        Sidecar path or ``None`` when it was not created due to a metadata
        build error or a missing descriptor (``required=False`` only).

    Raises
    ------
    DownloadError
        Only with ``required=True``, when the sidecar was not created.
    """
    sidecar_path = data_path.parent / f"{data_path.name}.meta.json"
    if not isinstance(descriptor_key, str):
        if required:
            raise DownloadError(
                f"Nie udalo sie zapisac obowiazkowego sidecara {sidecar_path}: "
                f"brak deskryptora zrodla ({descriptor_key!r})"
            )
        return None
    try:
        from kartograf.sources.registry import get_source

        transform = {
            axis: pinned_label(pinned)
            for axis, pinned in (pinned_transforms or {}).items()
            if pinned is not None
        }
        meta = build_metadata(
            get_source(descriptor_key),
            request=request,
            vertical_crs=vertical_crs,
            data_path=data_path,
            transform=transform or None,
            extra=extra,
            capability=capability,
            nodata=nodata,
            horizontal_crs=horizontal_crs,
        )
        return write_sidecar(data_path, meta, atomic=required)
    except Exception as e:  # noqa: BLE001 — failure policy in one place (D7)
        if required:
            raise DownloadError(
                f"Nie udalo sie zapisac obowiazkowego sidecara {sidecar_path}: {e}"
            ) from e
        logger.warning(f"Nie udalo sie zapisac sidecara dla {data_path}: {e}")
        return None
