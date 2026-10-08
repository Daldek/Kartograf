"""
Strict CRS transformation policy.

Four safety rules (each follows from a measured pitfall, see spec
section 6.4 and docs/research/2026-08-10-*):
1. The Transformer is built ONLY through TransformerGroup(..., allow_ballpark=False,
   always_xy=True) - Transformer.from_crs can silently return the identity.
2. An empty list of operations = TransformUnavailableError, never a fallback.
3. Filter: reject accuracy < 0 (unknown; pyproj encodes it as -1 - 0.0 means
   an EXACT operation and is accepted) and accuracy > policy.min_accuracy_m;
   then pin the datum step for CRSs shared between countries and probe
   a control point (inf/NaN => the operation is rejected - the case of a
   foreign country's grid). Of the rest, pick the best accuracy.
4. Every transformation result passes an isfinite check; otherwise TransformError.

The policy applies to NEW code (stage 1+); migration of the existing pyproj calls in
core/geometry.py, core/sheet_parser.py, core/parser_2000.py, providers/corine.py
and providers/soilgrids.py is deferred (stage 0 spec, section "Out of scope").
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pyproj import CRS, network
from pyproj.transformer import TransformerGroup

from kartograf.exceptions import KartografError


class TransformError(KartografError):
    """Coordinate transformation error (e.g. an infinite result)."""


class TransformUnavailableError(TransformError):
    """No safe transformation operation for the CRS pair."""

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
    probe_point: tuple[float, float] | None = None  # in the source CRS
    allow_network_grids: bool = True  # PROJ CDN


# Policy for operations that reproject raster CONTENT (the CZ path
# ``CuzkDmrProvider`` and the PL cutout ``download/cutout.py``) - the only one
# that moves pixels, so the accuracy limit is stricter than for envelopes. The
# datum step to the 2180/3045 CRSs is pinned to the Czech EPSG:1622 (1.0 m,
# KNOWN_PATHS);
# probe_point is added per request (``dataclasses.replace``).
CONTENT_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)
# Source envelope margin in pixels for the warp: covers the uncertainty of the
# envelope operation (<= 2 m) and the bilinear interpolator halo (1 px) at the edges.
WARP_MARGIN_PX = 4


@dataclass(frozen=True)
class PinnedTransform:
    """Przypieta (wybrana raz, deterministyczna) operacja transformacji."""

    accuracy_m: float
    description: str  # operation description (goes to the sidecar in stage 1+)
    _transformer: Any = field(repr=False)
    src_crs: str | None = None
    dst_crs: str | None = None

    def transform(self, x, y, z=None) -> tuple:
        """Transform a point or numpy arrays; an inf/NaN result => TransformError."""
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
        """The same operation as a PROJ pipeline for GDAL (``COORDINATE_OPERATION``).

        Lets ``rasterio.warp.reproject`` be forced to use EXACTLY the operation
        that passed the policy in ``build_pinned_transform`` - without it GDAL
        picks the operation itself (measured 2026-08-11: GDAL's choice differs from
        the pinned one by 0.08 m on average, 1.9 m max) and has no ban
        on ballpark.

        The axis correction is necessary: the pipeline comes from an
        ``always_xy=True`` transformer (E-N order), while GDAL passes coordinates to
        the operation in the AUTHORITATIVE axis order of both CRSs. Therefore
        ``axisswap``
        is added INDEPENDENTLY for the source (at the front) and for the target (at the
        end)
        - each time the given CRS is northing-first (EPSG:2180,
        EPSG:3045; EPSG:5514 is not). Without the correction the raster is entirely
        nodata - a silent failure mode that is easy to overlook (measured for the
        PL 2180 -> 5514 path without the leading ``axisswap``: 0 of 46225 valid
        pixels) - so it is derived from ``axis_info`` rather than assumed.
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
    """Whether the CRS's authoritative axis order starts with north/south?"""
    axes = CRS.from_user_input(crs).axis_info
    return bool(axes) and axes[0].direction.lower() in ("north", "south")


@dataclass(frozen=True)
class KnownPath:
    """Documentation entry: a verified transformation path."""

    src: str
    dst: str
    expected_accuracy_m: float
    note: str


# Reference table (spec 6.4); in stage 0 consumed by tests.
KNOWN_PATHS: tuple[KnownPath, ...] = (
    KnownPath(
        "EPSG:5514",
        "EPSG:2180",
        1.0,
        "EPSG:1622 S-JTSK to ETRS89 (1), Czechy; pin DATUM_STEP_PINS — "
        "EPSG:4829 (0,5 m) to operacja slowacka; reprojekcja tresci LOKALNA, "
        "serwer CUZK gubi datum shift dla imageSR=2180 (ADR-024)",
    ),
    KnownPath(
        "EPSG:2180",
        "EPSG:5514",
        1.0,
        "wycinek PL --target-crs (ADR-027); pin odwrotnej EPSG:1622: "
        "Inverse of Poland CS92 + ETRF2000-PL to ETRS89 (1) "
        "+ Inverse of S-JTSK to ETRS89 (1) + Krovak East North",
    ),
    KnownPath(
        "EPSG:5514",
        "EPSG:3045",
        1.0,
        "kafel TM33; pin EPSG:1622 S-JTSK to ETRS89 (1), Czechy",
    ),
    KnownPath(
        "EPSG:5514",
        "EPSG:4326",
        1.0,
        "lon/lat i obwiednie; pin EPSG:1623 S-JTSK to WGS 84 (1), Czechy; "
        "te same parametry Helmerta co EPSG:1622",
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
    KnownPath("EPSG:8357", "EPSG:5621", 0.1, "Bpv->EVRF2007; +0,11..+0,15 m"),
    KnownPath("EPSG:7837", "EPSG:5621", 0.1, "DHHN2016; realnie 1-14 mm"),
    KnownPath(
        "EPSG:4937",
        "EPSG:8357",
        0.03,
        "siatka sk_gku_Slovakia_ETRS89h_to_Baltic1957; probe konieczny "
        "(pierwsza operacja PROJ to siatka CZ)",
    ),
)

# EPSG areas of use are rectangles: the Slovak one also covers Zlin
# and Jablunkov, so neither the AOI nor the PROJ ranking decides a data's country.
# The CUZK S-JTSK needs the Czech datum step, not the Slovak operation
# (EPSG:4829) that is more accurate on paper. Both pins have the same Helmert
# parameters.
DATUM_STEP_PINS: dict[int, frozenset[str]] = {
    5514: frozenset({"EPSG:1622", "EPSG:1623"}),
}

_KRON86_EVRF_REMEDY = (
    "Siatki pl86_2019/pl07_2019 nie sa publiczne — zainstaluj je recznie do "
    "PROJ_DATA albo uzyj EVRF2007 (EPSG:5621)."
)

# Remedy per TARGET CRS, attached to TransformUnavailableError.
REMEDIES: dict[str, str] = {
    "EPSG:9650": _KRON86_EVRF_REMEDY,
    "EPSG:9651": _KRON86_EVRF_REMEDY,
}


def _epsg_code(crs: str) -> int | None:
    """EPSG code of a CRS (None for WKT/proj-string without an authority)."""
    try:
        return CRS.from_user_input(crs).to_epsg()
    except Exception:  # noqa: BLE001
        return None


def _operation_codes(transformer: Any) -> frozenset[str]:
    """Codes of operation steps, including inverted ones: INVERSE(EPSG) -> EPSG."""
    doc = transformer.to_json_dict()
    steps = doc.get("steps") or [doc]
    codes = set()
    for step in steps:
        ident = step.get("id") or {}
        authority = str(ident.get("authority", ""))
        authority = authority.removeprefix("INVERSE(").removesuffix(")")
        if authority and "code" in ident:
            codes.add(f"{authority}:{ident['code']}")
    return frozenset(codes)


def build_pinned_transform(
    src_crs: str, dst_crs: str, policy: TransformPolicy
) -> PinnedTransform:
    """Build a pinned transformation per the policy or raise TransformUnavailableError.

    Raises ``TransformUnavailableError`` when there is no safe operation.
    """
    required: frozenset[str] = frozenset()
    for crs in (src_crs, dst_crs):
        epsg = _epsg_code(crs)
        if epsg is not None:
            required |= DATUM_STEP_PINS.get(epsg, frozenset())
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
            if required and not (_operation_codes(transformer) & required):
                rejected.append(
                    (
                        description,
                        f"krok datum spoza przypietych {sorted(required)} "
                        "(operacja innego kraju dla tego samego datum)",
                    )
                )
                continue
            if policy.probe_point is not None:
                px, py = policy.probe_point
                try:
                    probe = transformer.transform(px, py)
                except Exception as e:  # noqa: BLE001 — any probe error = rejection
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
