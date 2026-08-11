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
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pyproj import network
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
        "probe odrzuca sk_gku (inf w CZ); preferowac reprojekcje serwerowa CUZK",
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
        accuracy_m=accuracy, description=description, _transformer=transformer
    )
