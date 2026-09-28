"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px); kolejni: Saksonia (brak WCS), wycinek PL (ADR-027). Nodata
jest propagowane do wyniku — NIGDY nie zamieniane na 0.
"""

import logging
import math
from collections import Counter
from pathlib import Path

import rasterio
from rasterio.merge import merge

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Tolerancja w pikselach: siatki zgodne i bboxy lezace na linii siatki
# z dokladnoscia bledu zmiennoprzecinkowego nie moga ani dokladac kolumny,
# ani rozdzielac zrodel na rozne siatki.
_GRID_TOL_PX = 1e-6


def _phase(value: float, step: float) -> int:
    """Polozenie linii siatki w obrebie piksela (w jednostkach tolerancji).

    Dwie siatki o tym samym kroku sa zgodne, gdy fazy sa rowne; faza tuz
    ponizej 1 to ta sama siatka co faza 0.
    """
    p = (value / step) % 1.0
    if p > 1.0 - _GRID_TOL_PX:
        p = 0.0
    return round(p / _GRID_TOL_PX)


def _snap_outward(
    bounds: tuple[float, float, float, float],
    paths: list[Path],
    transforms: list,
) -> tuple[tuple[float, float, float, float], list[tuple[Path, float, float]]]:
    """Bounds rozszerzone na zewnatrz do siatki zrodel + zrodla spoza niej.

    Siatka odniesienia = siatka WIEKSZOSCI zrodel (remis: pierwszej w
    kolejnosci wejscia). Linie pionowe ``x0 + k * rx``, poziome ``y0 + k * ry``
    (``y0`` to GORNA krawedz, ``transform.f``). Arkusze GUGiK jednego produktu
    leza na jednej siatce, ale NIE na wielokrotnosciach piksela (zmierzone na
    1977 arkuszach 5 m: narozniki na 5k + 2,5 m) — stad siatka z transformacji.
    Zrodlo spoza siatki nie jest bledem (arkusze sa juz w cache, blad bylby
    trwaly): wraca na liscie z przesunieciem w pikselach, a jego tresc merge
    przepisze metoda najblizszego sasiada.
    """
    for path, t in zip(paths, transforms, strict=True):
        if t.b != 0 or t.d != 0:
            raise ValidationError(
                f"mosaic_and_crop: obrocona siatka zrodla {path.name}"
            )
    rx, ry = transforms[0].a, -transforms[0].e
    keys = [(_phase(t.c, rx), _phase(t.f, ry)) for t in transforms]
    majority = Counter(keys).most_common(1)[0][0]
    ref = transforms[keys.index(majority)]
    x0, y0 = ref.c, ref.f
    off_grid = [
        (
            path,
            ((t.c - x0) / rx + 0.5) % 1.0 - 0.5,
            ((t.f - y0) / ry + 0.5) % 1.0 - 0.5,
        )
        for path, t, key in zip(paths, transforms, keys, strict=True)
        if key != majority
    ]
    min_x, min_y, max_x, max_y = bounds
    snapped = (
        x0 + math.floor((min_x - x0) / rx + _GRID_TOL_PX) * rx,
        y0 + math.floor((min_y - y0) / ry + _GRID_TOL_PX) * ry,
        x0 + math.ceil((max_x - x0) / rx - _GRID_TOL_PX) * rx,
        y0 + math.ceil((max_y - y0) / ry - _GRID_TOL_PX) * ry,
    )
    return snapped, off_grid


def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
    dst_kwds: dict | None = None,
    snap_to_source_grid: bool = False,
) -> Path:
    """Zszyj rastry wejsciowe i przytnij do bbox; zwroc output_path.

    ``dst_kwds`` nadpisuje profil wyjscia (np. driver/CRS, gdy zrodla ASC
    ich nie maja).

    Zrodla otwierane sa POJEDYNCZO: metadane czyta petla sekwencyjna (jeden
    deskryptor naraz), a ``merge`` dostaje SCIEZKI i sam otwiera zrodla po
    jednym, per kawalek wyniku. Wycinek 75 x 75 km to >1200 arkuszy, a domyslny
    limit deskryptorow to 1024 (Linux; macOS 256) — trzymanie wszystkich
    zrodel otwartych naraz konczylo sie "Too many open files" dopiero PO
    wielogodzinnym pobraniu (review max 2026-08-30, zn. 3).

    ``snap_to_source_grid`` (domyslnie ``False``, tor CZ bez zmian): przed
    przycieciem rozszerza bbox NA ZEWNATRZ do linii siatki pikseli zrodel
    (siatka WIEKSZOSCI zrodel; remis rozstrzyga kolejnosc wejscia), wiec
    wynik kopiuje piksele zrodel 1:1 zamiast przesuwac tresc o ulamek piksela
    (review max 2026-08-30, zn. 1). Zrodlo spoza tej siatki NIE przerywa
    mozaikowania (arkusze sa juz w cache — blad bylby trwaly): idzie do
    ``logger.warning`` z przesunieciem w px, a jego tresc ``merge`` przepisze
    najblizszym sasiadem. Zrodlo z obrocona siatka (rotacja/skos w transformie)
    konczy sie ``ValidationError``.
    """
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)
    paths = [Path(p) for p in inputs]

    crs_set: set[str] = set()
    res_set: set[tuple[float, float]] = set()
    transforms = []
    for path in paths:
        with rasterio.open(path) as src:
            crs_set.add(str(src.crs))
            res_set.add(src.res)
            transforms.append(src.transform)
    if len(crs_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
        )
    if len(res_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
        )

    bounds = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if snap_to_source_grid:
        # Bez tego siatke wyniku kotwiczy rog bbox, a merge przepisuje piksele
        # najblizszym sasiadem: tresc przesuwa sie o ulamek piksela, a przy
        # remisie (bbox calkowity na siatce GUGiK z narozami w k + 0,5) sasiednie
        # kolumny mieszaja sie (review max 2026-08-30, zn. 1; fakt 2 planu).
        bounds, off_grid = _snap_outward(bounds, paths, transforms)
        if off_grid:
            worst = max(max(abs(dx), abs(dy)) for _, dx, dy in off_grid)
            names = ", ".join(p.name for p, _, _ in off_grid[:10])
            logger.warning(
                f"mosaic_and_crop: {len(off_grid)} z {len(paths)} zrodel poza "
                f"siatka pikseli wiekszosci (maks. przesuniecie {worst:.3f} px) "
                f"— ich tresc przepisana najblizszym sasiadem: {names}"
                + (" ..." if len(off_grid) > 10 else "")
            )

    # merge z dst_path sam otwiera plik do zapisu (stad mkdir PRZED
    # wywolaniem) i liczy wynik kawalkami wg mem_limit; bez dst_path
    # caly raster ladowalby do jednej tablicy w RAM — szczyt 2,63x
    # rozmiaru danych, czyli ok. 2,4 GB dla zlewni 30x30 km przy DMR 5G.
    # Profil wyjscia merge bierze z PIERWSZEGO zrodla.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwds: dict = {}
    if nodata is not None:
        kwds["nodata"] = nodata
    if dst_kwds:
        kwds.update(dst_kwds)
    merge(
        paths,
        bounds=bounds,
        nodata=nodata,
        dst_path=str(output_path),
        dst_kwds=kwds or None,
    )
    return output_path
