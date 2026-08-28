"""
Twarda polityka transformacji CRS.

Cztery reguly bezpieczenstwa (kazda wynika ze zmierzonej pulapki, patrz spec
sekcja 6.4 i docs/research/2026-08-10-*):
1. Transformer budowany WYLACZNIE przez TransformerGroup(..., allow_ballpark=False,
   always_xy=True) — Transformer.from_crs potrafi cicho zwrocic identycznosc.
2. Pusta lista operacji = TransformUnavailableError, nigdy fallback.
3. Filtr: odrzuc accuracy < 0 (nieznana; pyproj koduje jako -1 — 0.0 oznacza
   operacje DOKLADNA i jest akceptowane) oraz accuracy > policy.min_accuracy_m;
   nastepnie probe na punkcie kontrolnym (inf/NaN => odrzut operacji — przypadek
   siatki obcego kraju). Z pozostalych wybierz najlepsza dokladnosc.
4. Kazdy wynik transformacji przechodzi kontrole isfinite; inaczej TransformError.

Polityka obowiazuje kod NOWY (etap 1+); migracja istniejacych wywolan pyproj w
core/geometry.py, core/sheet_parser.py, core/parser_2000.py, providers/corine.py
i providers/soilgrids.py jest odlozona (spec etapu 0, sekcja "Nie wchodzi").
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pyproj import CRS, network
from pyproj.transformer import TransformerGroup

from kartograf.exceptions import KartografError


class TransformError(KartografError):
    """Blad transformacji wspolrzednych (np. wynik nieskonczony)."""


class TransformUnavailableError(TransformError):
    """Brak bezpiecznej operacji transformacji dla pary ukladow."""

    def __init__(
        self,
        message: str,
        rejected: list[tuple[str, str]] | None = None,
        remedy: str | None = None,
    ):
        super().__init__(message)
        self.rejected = rejected or []
        self.remedy = remedy


@dataclass(frozen=True)
class TransformPolicy:
    """Polityka doboru operacji transformacji."""

    min_accuracy_m: float = 1.0
    probe_point: tuple[float, float] | None = None  # w ukladzie zrodlowym
    allow_network_grids: bool = True  # PROJ CDN


@dataclass(frozen=True)
class PinnedTransform:
    """Przypieta (wybrana raz, deterministyczna) operacja transformacji."""

    accuracy_m: float
    description: str  # opis operacji (trafia do sidecara w etapie 1+)
    _transformer: Any = field(repr=False)
    src_crs: str | None = None
    dst_crs: str | None = None

    def transform(self, x, y, z=None) -> tuple:
        """Transformuj punkt lub tablice numpy; wynik inf/NaN => TransformError."""
        if z is None:
            result = self._transformer.transform(x, y)
        else:
            result = self._transformer.transform(x, y, z)
        if not all(bool(np.all(np.isfinite(v))) for v in result):
            raise TransformError(
                f"Transformacja zwrocila wartosc nieskonczona [{self.description}]"
            )
        return result

    def gdal_operation(self) -> str:
        """Ta sama operacja jako pipeline PROJ dla GDAL (``COORDINATE_OPERATION``).

        Pozwala wymusic na ``rasterio.warp.reproject`` DOKLADNIE te operacje,
        ktora przeszla polityke z ``build_pinned_transform`` — bez tego GDAL
        wybiera operacje sam (zmierzone 2026-08-11: wybor GDAL-a rozni sie od
        przypietego o srednio 0,08 m, maks. 1,9 m) i nie ma zadnego zakazu
        ballparku.

        Korekta osi jest konieczna: pipeline pochodzi z transformera
        ``always_xy=True`` (kolejnosc E-N), a GDAL podaje operacji wspolrzedne
        w kolejnosci osi AUTORYTATYWNEJ obu ukladow. Dlatego ``axisswap``
        dokladany jest NIEZALEZNIE dla zrodla (na czele) i dla celu (na koncu)
        — za kazdym razem, gdy dany uklad jest northing-first (EPSG:2180,
        EPSG:3045; EPSG:5514 nie jest). Brak korekty daje raster w calosci
        nodata — cichy, latwy do przeoczenia tryb awarii (zmierzone dla toru
        PL 2180 -> 5514 bez czolowego ``axisswap``: 0 z 46225 waznych
        pikseli) — dlatego jest wyliczana z ``axis_info``, a nie zakladana.
        """
        if self.src_crs is None or self.dst_crs is None:
            raise TransformError(
                f"Operacja GDAL wymaga znanej pary ukladow "
                f"[{self.description}] — PinnedTransform zbudowany bez nich"
            )
        pipeline = str(self._transformer.definition).strip()
        if not pipeline.startswith("proj=pipeline"):
            pipeline = f"proj=pipeline step {pipeline}"
        if _is_northing_first(self.src_crs):
            head, sep, rest = pipeline.partition(" step ")
            pipeline = f"{head} step {_AXIS_SWAP}{sep}{rest}"
        if _is_northing_first(self.dst_crs):
            pipeline = f"{pipeline} step {_AXIS_SWAP}"
        return pipeline


_AXIS_SWAP = "proj=axisswap order=2,1"


def _is_northing_first(crs: str) -> bool:
    """Czy autorytatywna kolejnosc osi ukladu zaczyna sie od polnocy/poludnia?"""
    axes = CRS.from_user_input(crs).axis_info
    return bool(axes) and axes[0].direction.lower() in ("north", "south")


@dataclass(frozen=True)
class KnownPath:
    """Wpis dokumentacyjny: zweryfikowana sciezka transformacji."""

    src: str
    dst: str
    expected_accuracy_m: float
    note: str


# Tabela referencyjna (spec 6.4); w etapie 0 konsumowana w testach.
KNOWN_PATHS: tuple[KnownPath, ...] = (
    KnownPath(
        "EPSG:5514",
        "EPSG:2180",
        0.5,
        "probe odrzuca sk_gku (inf w CZ); reprojekcja tresci LOKALNA — "
        "serwerowej CUZK nie uzywamy, gubi datum shift (ADR-024)",
    ),
    KnownPath(
        "EPSG:2180",
        "EPSG:5514",
        0.5,
        "wycinek PL --target-crs (ADR-027); zmierzone: Inverse of Poland CS92 "
        "+ ETRF2000-PL to ETRS89 (1) + Inverse of S-JTSK to ETRS89 (3) "
        "+ Krovak East North",
    ),
    KnownPath(
        "EPSG:2180",
        "EPSG:3045",
        0.0,
        "wycinek PL --target-crs (ADR-027) na siatke kafla TM33; zmierzone: "
        "Inverse of Poland CS92 + ETRF2000-PL to ETRS89 (1) + UTM zone 33N",
    ),
    KnownPath("EPSG:8353", "EPSG:2180", 0.001, "SK, bez siatek"),
    KnownPath("EPSG:25833", "EPSG:2180", 0.0, "DE, jedyna operacja, bez siatek"),
    KnownPath("EPSG:8357", "EPSG:5621", 0.1, "Bpv->EVRF2007; +0,12..+0,14 m"),
    KnownPath("EPSG:7837", "EPSG:5621", 0.1, "DHHN2016; realnie 1-14 mm"),
    KnownPath(
        "EPSG:4937",
        "EPSG:8357",
        0.03,
        "siatka sk_gku_Slovakia_ETRS89h_to_Baltic1957; probe konieczny "
        "(pierwsza operacja PROJ to siatka CZ)",
    ),
)

_KRON86_EVRF_REMEDY = (
    "Siatki pl86_2019/pl07_2019 nie sa publiczne — zainstaluj je recznie do "
    "PROJ_DATA albo uzyj EVRF2007 (EPSG:5621)."
)

# Remedium per DOCELOWY uklad, dolaczane do TransformUnavailableError.
REMEDIES: dict[str, str] = {
    "EPSG:9650": _KRON86_EVRF_REMEDY,
    "EPSG:9651": _KRON86_EVRF_REMEDY,
}


def build_pinned_transform(
    src_crs: str, dst_crs: str, policy: TransformPolicy
) -> PinnedTransform:
    """Zbuduj przypieta transformacje wg polityki albo rzuc TransformUnavailableError.

    Rzuca ``TransformUnavailableError`` gdy brak bezpiecznej operacji.
    """
    previous_network_enabled = network.is_network_enabled()
    network.set_network_enabled(policy.allow_network_grids)
    try:
        group = TransformerGroup(src_crs, dst_crs, always_xy=True, allow_ballpark=False)
        rejected: list[tuple[str, str]] = []
        candidates = []
        for transformer in group.transformers:
            accuracy = transformer.accuracy
            description = str(transformer.description)
            if accuracy < 0:
                rejected.append((description, "nieznana dokladnosc (accuracy < 0)"))
                continue
            if accuracy > policy.min_accuracy_m:
                rejected.append(
                    (
                        description,
                        f"dokladnosc {accuracy} m > limit {policy.min_accuracy_m} m",
                    )
                )
                continue
            if policy.probe_point is not None:
                px, py = policy.probe_point
                try:
                    probe = transformer.transform(px, py)
                except Exception as e:  # noqa: BLE001 — kazdy blad probe = odrzut
                    rejected.append((description, f"probe rzucil wyjatek: {e}"))
                    continue
                if not all(bool(np.all(np.isfinite(v))) for v in probe):
                    rejected.append(
                        (
                            description,
                            "probe zwrocil inf/NaN (siatka nie pokrywa obszaru danych)",
                        )
                    )
                    continue
            candidates.append((accuracy, transformer, description))
    finally:
        network.set_network_enabled(previous_network_enabled)

    if not candidates:
        raise TransformUnavailableError(
            f"Brak bezpiecznej operacji transformacji {src_crs} -> {dst_crs} "
            f"(kandydatow: {len(group.transformers)}, odrzuconych: {len(rejected)})",
            rejected=rejected,
            remedy=REMEDIES.get(dst_crs),
        )

    accuracy, transformer, description = min(candidates, key=lambda c: c[0])
    return PinnedTransform(
        accuracy_m=accuracy,
        description=description,
        _transformer=transformer,
        src_crs=src_crs,
        dst_crs=dst_crs,
    )
