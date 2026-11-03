"""Messages of the command catalog: the declarations of ``maps``."""

from kartograf.messages import Text

MESSAGES = {
    "scale_description": Text(
        "Map scale (required): `topographic` PL 1:10000 to 1:100000, CZ 1:5000 to "
        "1:250000.{choice_text:skip}",
        "Skala mapy (wymagana): {choice_text}",
    ),
    "format_description": Text(
        "File format (required): `topographic` PL TIFF or PDF, CZ TIFF, PDF, DGN or "
        "SHP.{choice_text:skip}",
        "Format pliku (wymagany): {choice_text}",
    ),
    "sheet_system_description": Text(
        "ZTM (CZ) only: sheet system, `sjtsk` or `etrs89`; required with `bbox` or "
        "`geometry`, implied by a sheet code. BDOT10k maps (PL) use PL-1992 sheets: "
        "omit it.{choice_text:skip}",
        "Tylko ZTM (CZ): uklad arkuszy - wymagany z --bbox/--geometry, z --sheet "
        "wynika z godla; mapy BDOT10k (PL) maja arkusze PL-1992 (pomin "
        "--sheet-system): {choice_text}",
    ),
    "download_summary": Text(
        "Download topographic map sheets: BDOT10k visualisations (PL), ZTM (CZ)",
        "Pobierz arkusze mapy topograficznej",
    ),
    "download_description": Text(
        "Fetches the original map files of the sheets that cover an area: BDOT10k "
        "visualisations (PL, PL-1992 sheets) or ZTM maps (CZ; sheet system `sjtsk` or "
        "`etrs89`). `scale` and `format` are required. ZTM TIFF, DGN and SHP are "
        "ZIPs, PDF is a .pdf; BDOT10k TIFF and PDF are the index files.",
        "--product topographic: wizualizacje BDOT10k (--country pl; arkusze PL-1992, "
        "bez --sheet-system) albo ZTM (--country cz). --scale i --format sa wymagane. "
        "ZTM (CZ): uklad arkuszy --sheet-system sjtsk|etrs89 wynika z godla, dla "
        "--bbox/--geometry jest wymagany. ZTM TIFF, DGN i SHP sa ZIP-ami, PDF jest "
        "plikiem .pdf; BDOT10k TIFF i PDF sa oryginalnymi plikami z indeksu map.",
    ),
    "area_result_description": Text(
        "Downloads the map sheets that cover the area (original files).",
        "arkusze map przecinajace obszar (pliki oryginalne)",
    ),
    "sheet_help_description": Text(
        "Map sheet code: PL-1992 (`country=pl`) or ZTM in S-JTSK or ETRS89 "
        "(`country=cz`; the sheet system follows from the code).",
        "Godlo mapy: PL-1992 (--country pl) albo ZTM w S-JTSK/ETRS89 (--country cz; "
        "uklad arkuszy wynika z godla)",
    ),
    "check_description": Text(
        "Signal: the release label of the BDOT10k map index (PL) or the "
        "ETag/Last-Modified of the ZTM sheet (CZ).",
        "Porownaj etykiete wydania z indeksem map BDOT10k (PL) albo "
        "ETag/Last-Modified arkusza ZTM (CZ) bez pobierania danych",
    ),
    "example_pl_bdot10k_map_sheet": Text(
        "PL BDOT10k map: a sheet",
        "Mapa BDOT10k PL: arkusz",
    ),
    "example_cz_ztm_map_sheet": Text("CZ ZTM map: a sheet", "Mapa ZTM CZ: arkusz"),
    "example_cz_ztm_map_sheets_rectangle": Text(
        "CZ ZTM map: sheets for a rectangle",
        "Mapa ZTM CZ: arkusze dla prostokata",
    ),
    "group_summary": Text(
        "Topographic maps: BDOT10k (PL), ZTM (CZ)",
        "Mapy topograficzne: BDOT10k (PL), ZTM (CZ)",
    ),
    "group_description": Text(
        "Topographic map sheets of BDOT10k and ZTM as the original source files "
        "(GeoTIFF, PDF, DGN or SHP).",
        "Arkusze map topograficznych BDOT10k i ZTM jako oryginalne pliki ze zrodla "
        "(GeoTIFF, PDF, DGN lub SHP).",
    ),
}
