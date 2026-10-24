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
            (
                "Map scale (required): `topographic` PL 1:10000 to 1:100000, CZ"
                " 1:5000 to 1:250000."
            ),
            metavar="SKALA",
            allowed=lambda: choice_values(products(), "scale"),
            required=True,
            task=True,
            description_pl=scale_help,
        ),
        Param(
            "format",
            "str",
            (
                "File format (required): `topographic` PL TIFF or PDF, CZ TIFF,"
                " PDF, DGN or SHP."
            ),
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            required=True,
            task=True,
            description_pl=format_help,
        ),
        Param(
            "sheet_system",
            "str",
            (
                "ZTM (CZ) only: sheet system, `sjtsk` or `etrs89`; required "
                "with `bbox` or `geometry`, implied by a sheet code. BDOT10k "
                "maps (PL) use PL-1992 sheets: omit it."
            ),
            metavar="UKLAD",
            allowed=lambda: choice_values(products(), "sheet_system"),
            task=True,
            description_pl=sheet_system_help,
        ),
    )


COMMANDS = collection_commands(
    "maps",
    summary=(
        "Download topographic map sheets: BDOT10k visualisations (PL), ZTM (CZ)",
        "Pobierz arkusze mapy topograficznej",
    ),
    description=(
        "Fetches the original map files of the sheets that cover an "
        "area: BDOT10k visualisations (PL, PL-1992 sheets) or ZTM maps "
        "(CZ; sheet system `sjtsk` or `etrs89`). `scale` and `format` "
        "are required. ZTM TIFF, DGN and SHP are ZIPs, PDF is a .pdf; "
        "BDOT10k TIFF and PDF are the index files.",
        (
            "--product topographic: wizualizacje BDOT10k (--country pl; "
            "arkusze PL-1992, bez --sheet-system) albo ZTM (--country cz). "
            "--scale i --format sa wymagane. ZTM (CZ): uklad arkuszy "
            "--sheet-system sjtsk|etrs89 wynika z godla, dla "
            "--bbox/--geometry jest wymagany. ZTM TIFF, DGN i SHP sa "
            "ZIP-ami, PDF jest plikiem .pdf; BDOT10k TIFF i PDF sa "
            "oryginalnymi plikami z indeksu map."
        ),
    ),
    area_result=(
        "Downloads the map sheets that cover the area (original files).",
        "arkusze map przecinajace obszar (pliki oryginalne)",
    ),
    examples=(
        Example(
            {
                "product": "topographic",
                "country": "pl",
                "sheet": "M-34-064-D-d-1",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title="PL BDOT10k map: a sheet",
            title_pl="Mapa BDOT10k PL: arkusz",
        ),
        Example(
            {
                "product": "topographic",
                "country": "cz",
                "sheet": "0510-D-11",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title="CZ ZTM map: a sheet",
            title_pl="Mapa ZTM CZ: arkusz",
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
            title="CZ ZTM map: sheets for a rectangle",
            title_pl="Mapa ZTM CZ: arkusze dla prostokata",
        ),
    ),
    content=_content,
    sheet_help=(
        "Map sheet code: PL-1992 (`country=pl`) or ZTM in S-JTSK or "
        "ETRS89 (`country=cz`; the sheet system follows from the code).",
        (
            "Godlo mapy: PL-1992 (--country pl) albo ZTM w S-JTSK/ETRS89 "
            "(--country cz; uklad arkuszy wynika z godla)"
        ),
    ),
    sheet_systems=("pl1992", "pl2000", "cz_ztm"),
    check=(
        "Signal: the release label of the BDOT10k map index (PL) or the"
        " ETag/Last-Modified of the ZTM sheet (CZ).",
        (
            "Porownaj etykiete wydania z indeksem map BDOT10k (PL) albo "
            "ETag/Last-Modified arkusza ZTM (CZ) bez pobierania danych"
        ),
    ),
)

GROUPS = (
    collection_group(
        "maps",
        (
            "Topographic maps: BDOT10k (PL), ZTM (CZ)",
            "Mapy topograficzne: BDOT10k (PL), ZTM (CZ)",
        ),
        (
            "Topographic map sheets of BDOT10k and ZTM as the original "
            "source files (GeoTIFF, PDF, DGN or SHP).",
            (
                "Arkusze map topograficznych BDOT10k i ZTM jako oryginalne "
                "pliki ze zrodla (GeoTIFF, PDF, DGN lub SHP)."
            ),
        ),
    ),
)
