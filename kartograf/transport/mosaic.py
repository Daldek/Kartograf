"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px); kolejni: Saksonia (brak WCS). Nodata jest propagowane do
wyniku — NIGDY nie zamieniane na 0.
"""

import contextlib
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
) -> Path:
    """Zszyj rastry wejsciowe i przytnij do bbox; zwroc output_path."""
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)

    with contextlib.ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(p)) for p in inputs]

        crs_set = {str(src.crs) for src in sources}
        if len(crs_set) > 1:
            raise ValidationError(
                f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
            )
        res_set = {src.res for src in sources}
        if len(res_set) > 1:
            raise ValidationError(
                f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
            )

        # merge z dst_path sam otwiera plik do zapisu (stad mkdir PRZED
        # wywolaniem) i liczy wynik kawalkami wg mem_limit; bez dst_path
        # caly raster ladowalby do jednej tablicy w RAM — szczyt 2,63x
        # rozmiaru danych, czyli ok. 2,4 GB dla zlewni 30x30 km przy DMR 5G.
        # Profil wyjscia merge bierze z PIERWSZEGO zrodla, dokladnie jak
        # wczesniejsza reczna kopia sources[0].profile.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merge(
            sources,
            bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
            nodata=nodata,
            dst_path=str(output_path),
            dst_kwds={"nodata": nodata} if nodata is not None else None,
        )
    return output_path
