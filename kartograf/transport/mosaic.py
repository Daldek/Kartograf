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

        data, transform = merge(
            sources,
            bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
            nodata=nodata,
        )

        profile = sources[0].profile.copy()
        profile.update(
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            transform=transform,
        )
        if nodata is not None:
            profile["nodata"] = nodata

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data)
    return output_path
