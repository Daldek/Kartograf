"""``kartograf maps``: BDOT10k visualizations (PL) and ZTM sheets (CZ)."""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param


def _content(products: Products) -> tuple[Param, ...]:
    def scale_help() -> str:
        return f"Skala mapy (wymagana): {choice_text(products(), 'scale')}"

    def format_help() -> str:
        return f"Format pliku (wymagany): {choice_text(products(), 'format')}"

    def sheet_system_help() -> str:
        return (
            "Tylko ZTM (CZ): uklad arkuszy - wymagany z --bbox/--geometry, "
            "z --sheet wynika z godla; mapy BDOT10k (PL) maja arkusze PL-1992 "
            f"(pomin --sheet-system): {choice_text(products(), 'sheet_system')}"
        )

    return (
        Param(
            "scale",
            "str",
            scale_help,
            metavar="SKALA",
            allowed=lambda: choice_values(products(), "scale"),
            required=True,
            task=True,
        ),
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            required=True,
            task=True,
        ),
        Param(
            "sheet_system",
            "str",
            sheet_system_help,
            metavar="UKLAD",
            allowed=lambda: choice_values(products(), "sheet_system"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "maps",
    summary="Pobierz arkusze mapy topograficznej",
    description="--product topographic: wizualizacje BDOT10k (--country pl; "
    "arkusze PL-1992, bez --sheet-system) albo ZTM (--country cz). --scale "
    "i --format sa wymagane. ZTM (CZ): uklad arkuszy --sheet-system "
    "sjtsk|etrs89 wynika z godla, dla --bbox/--geometry jest wymagany. ZTM "
    "TIFF, DGN i SHP sa ZIP-ami, PDF jest plikiem .pdf; BDOT10k TIFF i PDF "
    "sa oryginalnymi plikami z indeksu map.",
    area_result="arkusze map przecinajace obszar (pliki oryginalne)",
    examples=(
        Example(
            {
                "product": "topographic",
                "country": "pl",
                "sheet": "M-34-064-D-d-1",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title="Mapa BDOT10k PL: arkusz",
        ),
        Example(
            {
                "product": "topographic",
                "country": "cz",
                "sheet": "0510-D-11",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title="Mapa ZTM CZ: arkusz",
        ),
        Example(
            {
                "product": "topographic",
                "country": "cz",
                "bbox": [-452000, -1112000, -450000, -1110000],
                "bbox_crs": "EPSG:5514",
                "scale": "1:10000",
                "sheet_system": "sjtsk",
                "format": "PDF",
            },
            title="Mapa ZTM CZ: arkusze dla prostokata",
        ),
    ),
    content=_content,
    sheet_help="Godlo mapy: PL-1992 (--country pl) albo ZTM w S-JTSK/ETRS89 "
    "(--country cz; uklad arkuszy wynika z godla)",
    sheet_systems=("pl1992", "pl2000", "cz_ztm"),
    check="Porownaj etykiete wydania z indeksem map BDOT10k (PL) albo "
    "ETag/Last-Modified arkusza ZTM (CZ) bez pobierania danych",
)

GROUPS = (
    collection_group(
        "maps",
        "Mapy topograficzne: BDOT10k (PL), ZTM (CZ)",
        "Arkusze map topograficznych BDOT10k i ZTM jako oryginalne "
        "pliki ze zrodla (GeoTIFF, PDF, DGN lub SHP).",
    ),
)
