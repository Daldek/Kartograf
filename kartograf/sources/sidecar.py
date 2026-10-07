"""
Sidecar metadanych wyniku pobrania: `<pelna_nazwa_pliku>.meta.json`.

Kontrakt dla konsumentow (Hydrograf): CRS-y, nodata, zrodlo, licencja.
W 0.7.0 dane transgraniczne scala konsument; scalanie PL+CZ w jedna
powierzchnie to etap 2 Kartografa (R6). Format wersjonowany polem `schema`;
pola dokladane addytywnie.
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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


def _read_asc_header(path: Path) -> dict[str, float]:
    """Naglowek Arc/Info ASCII Grid: {klucz malymi literami: wartosc}; {} gdy brak."""
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
    """Odczytaj NODATA_value z naglowka Arc/Info ASCII Grid (None gdy brak)."""
    return _read_asc_header(path).get("nodata_value")


def _file_min_x(path: Path) -> float | None:
    """Lewa krawedz rastra (x) z naglowka ASC albo z rasterio; None gdy nieczytelna."""
    suffix = path.suffix.lower()
    if suffix == ".asc":
        header = _read_asc_header(path)
        return header.get("xllcorner", header.get("xllcenter"))
    if suffix in {".tif", ".tiff"}:
        import rasterio  # lazy: sidecar arkusza ASC nie potrzebuje GDAL

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
    """Uklad FAKTYCZNY pliku arkusza PL: strefa z godla, sprawdzona wspolrzednymi.

    Godlo PL-2000 wyznacza strefe (EPSG:2176..2179), PL-1992 -> EPSG:2180.
    Gdy plik da sie odczytac, a jego lewa krawedz wskazuje inny uklad (arkusz
    PL-1992 podstawiony pod godlo PL-2000 przez cache sprzed 0.7.0 — K4),
    sidecar opisuje PLIK: zwracany jest uklad z pliku, z ostrzezeniem.
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
    """Dobierz kanal do zadania (bbox -> kanal bbox_*, inaczej pierwszy pasujacy)."""
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
    """Uklad kanalu; dla arkusza PL po godle — uklad pliku (strefa PL-2000, N8)."""
    godlo = request.get("godlo")
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
    """Pierwszy kanal deklarujacy capability; KeyError gdy brak."""
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
    """Zbuduj metadane z deskryptora + kontekstu wywolania.

    ``horizontal_crs`` (jawny) opisuje uklad FAKTYCZNEGO wyniku i ma
    pierwszenstwo przed kanalem. Bez niego arkusz PL pobrany przez godlo
    (kanal ``sheet_files``) dostaje uklad z ``pl_sheet_horizontal_crs``
    — strefe PL-2000 z godla sprawdzona wspolrzednymi pliku; pozostale
    wyniki dziedzicza ``horizontal_crs`` kanalu.
    """
    from kartograf import __version__  # lazy: unika cyklu importow

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
        kartograf_version=__version__,
    )


def write_sidecar(
    data_path: Path, meta: ResultMetadata, *, atomic: bool = False
) -> Path:
    """Zapisz `<data_path>.meta.json` obok pliku danych; zwroc sciezke sidecara.

    ``atomic=False`` (domyslnie): wyjatki IO sa lapane i logowane jako
    warning (spec sekcja 8) — brak sidecara nigdy nie przerywa pobrania;
    przy bledzie zwracana sciezka wskazuje plik, ktory NIE powstal.

    ``atomic=True`` (sidecar obowiazkowy, ADR-030 errata 2 N-1): zapis do
    ``<name>.meta.json.<pid>_<tid>.tmp`` + ``os.replace``; ``OSError``
    WYLATUJE, tmp jest sprzatany (nigdy czesciowy sidecar).
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
    """Opis przypietej operacji w polu ``transform`` sidecara (jeden format)."""
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
    """Best-effort sidecar wyniku — jedyne miejsce polityki "sidecar nigdy
    nie przerywa pobrania" (D7): kazdy wyjatek budowy/zapisu konczy sie
    ostrzezeniem w logu i ``None``.

    ``descriptor_key`` nie bedacy ``str`` (provider bez deskryptora, atrapa
    ``Mock``) = brak sidecara, bez ostrzezenia. ``pinned_transforms``
    (``{"horizontal": PinnedTransform | None, "vertical": ...}``) trafia do
    ``transform`` w formacie ``pinned_label``; wpisy ``None`` sa pomijane,
    a pusty wynik daje ``transform: null``. Pozostale argumenty jak
    w ``build_metadata`` (``horizontal_crs`` = uklad FAKTYCZNEGO wyniku).

    ``required=True`` (sidecar pliku kampanii, ADR-030 errata 2 N-1): zapis
    atomowy (``write_sidecar(atomic=True)``), a brak deskryptora albo
    dowolny wyjatek budowy/zapisu konczy sie ``DownloadError`` — wolajacy
    wybiera tylko tryb, interpretacja porazki zostaje tutaj (D7).

    Returns
    -------
    Path or None
        Sciezka sidecara albo ``None``, gdy nie powstal z powodu bledu
        budowy metadanych lub braku deskryptora (tylko ``required=False``).

    Raises
    ------
    DownloadError
        Tylko przy ``required=True``, gdy sidecar nie powstal.
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
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        if required:
            raise DownloadError(
                f"Nie udalo sie zapisac obowiazkowego sidecara {sidecar_path}: {e}"
            ) from e
        logger.warning(f"Nie udalo sie zapisac sidecara dla {data_path}: {e}")
        return None
