"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px); kolejni: Saksonia (brak WCS), wycinek PL (ADR-027). Nodata
jest propagowane do wyniku — NIGDY nie zamieniane na 0.
"""

from pathlib import Path

import rasterio
from rasterio.merge import merge

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError


def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
    dst_kwds: dict | None = None,
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
    """
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)
    paths = [Path(p) for p in inputs]

    crs_set: set[str] = set()
    res_set: set[tuple[float, float]] = set()
    for path in paths:
        with rasterio.open(path) as src:
            crs_set.add(str(src.crs))
            res_set.add(src.res)
    if len(crs_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
        )
    if len(res_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
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
        bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
        nodata=nodata,
        dst_path=str(output_path),
        dst_kwds=kwds or None,
    )
    return output_path
