"""
Sidecar metadanych wyniku pobrania: `<pelna_nazwa_pliku>.meta.json`.

Kontrakt dla Hydrografa (scalanie danych transgranicznych poza Kartografem):
CRS-y, nodata, zrodlo, licencja. Format wersjonowany polem `schema`;
pola dokladane addytywnie.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kartograf.sources.descriptor import AccessChannel, SourceDescriptor
from kartograf.sources.registry import vertical_crs_code

logger = logging.getLogger(__name__)

_BBOX_CAPS = {"bbox_raster", "bbox_vector"}


@dataclass(kw_only=True)
class ResultMetadata:
    """Metadane jednego pliku wynikowego."""

    dataset: str  # klucz deskryptora
    country: str
    product: str
    provider: str
    horizontal_crs: str
    vertical_crs: str | None
    vertical_source: str  # "native" | "ellipsoidal" | "server"
    resolution: str | None
    nodata: float | None
    request: dict  # {"godlo": ...} | {"bbox": [...], "bbox_crs": ...}
    license: dict  # {"id","attribution","url"}
    downloaded_at: str  # ISO 8601 UTC
    kartograf_version: str
    transform: dict | None = None  # etap 0: None
    extra: dict = field(default_factory=dict)
    schema: str = "kartograf-meta/1"


def read_asc_nodata(path: Path) -> float | None:
    """Odczytaj NODATA_value z naglowka Arc/Info ASCII Grid (None gdy brak)."""
    try:
        with open(path, encoding="ascii", errors="replace") as f:
            for _ in range(6):
                parts = f.readline().split()
                if len(parts) == 2 and parts[0].lower() == "nodata_value":
                    return float(parts[1])
    except (OSError, ValueError):
        return None
    return None


def _select_channel(descriptor: SourceDescriptor, request: dict) -> AccessChannel:
    """Dobierz kanal do zadania (bbox -> kanal bbox_*, inaczej pierwszy pasujacy)."""
    want_bbox = "bbox" in request
    for ch in descriptor.channels:
        has_bbox = bool(ch.capabilities & _BBOX_CAPS)
        if want_bbox == has_bbox:
            return ch
    return descriptor.channels[0]


def build_metadata(
    descriptor: SourceDescriptor,
    *,
    request: dict,
    vertical_crs: str | None = None,
    data_path: Path | None = None,
    transform: dict | None = None,
    extra: dict | None = None,
) -> ResultMetadata:
    """Zbuduj metadane z deskryptora + kontekstu wywolania."""
    from kartograf import __version__  # lazy: unika cyklu importow

    channel = _select_channel(descriptor, request)

    vertical: str | None = None
    if channel.vertical_crs_options and vertical_crs is not None:
        vertical = vertical_crs_code(vertical_crs)

    nodata: float | None = None
    if data_path is not None and data_path.suffix.lower() == ".asc":
        nodata = read_asc_nodata(data_path)

    return ResultMetadata(
        dataset=descriptor.key,
        country=descriptor.country,
        product=descriptor.product,
        provider=descriptor.provider_name,
        horizontal_crs=channel.horizontal_crs,
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
        kartograf_version=__version__,
    )


def write_sidecar(data_path: Path, meta: ResultMetadata) -> Path:
    """Zapisz `<data_path>.meta.json` obok pliku danych; zwroc sciezke sidecara.

    Wyjatki IO sa lapane i logowane jako warning (spec sekcja 8) — brak
    sidecara nigdy nie przerywa pobrania; przy bledzie zwracana sciezka
    wskazuje plik, ktory NIE powstal.
    """
    sidecar_path = data_path.parent / f"{data_path.name}.meta.json"
    try:
        payload = json.dumps(asdict(meta), ensure_ascii=False, indent=2)
        sidecar_path.write_text(payload + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar_path}: {e}")
    return sidecar_path
