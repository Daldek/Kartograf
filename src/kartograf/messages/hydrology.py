"""Messages of the hydrologic soil groups (HSG)."""

from kartograf.messages import Text

MESSAGES = {
    # ``hydrology.hsg``.
    "class_a": Text(
        "High infiltration - sandy soils, low runoff potential",
        "Duza infiltracja - gleby piaszczyste, maly potencjal splywu",
    ),
    "class_b": Text(
        "Moderate infiltration - loamy soils, moderate runoff",
        "Umiarkowana infiltracja - gleby gliniaste, umiarkowany splyw",
    ),
    "class_c": Text(
        "Low infiltration - clay loams, high runoff",
        "Mala infiltracja - gliny ilaste, duzy splyw",
    ),
    "class_d": Text(
        "Very low infiltration - clay soils, very high runoff",
        "Bardzo mala infiltracja - gleby ilaste, bardzo duzy splyw",
    ),
    "hsg_output_files": Text(
        "inputs in <DIR>/soil/..., HSG in <DIR>/hsg/...",
        "wejscia w <KATALOG>/soil/..., HSG w <KATALOG>/hsg/...",
    ),
    "root_required": Text(
        "--root required: store directory ({hsg_output_files})",
        "--root wymagane: katalog magazynu ({hsg_output_files})",
    ),
    "root_is_store_dir": Text(
        "--root is a store directory (since 0.8.0); for a file outside the store "
        "use hsg_from_rasters",
        "--root to katalog magazynu (od 0.8.0); plik poza magazynem: hsg_from_rasters",
    ),
    "exactly_one_selection": Text(
        "Give exactly one selection: --sheet, --bbox or --geometry",
        "Podaj dokladnie jeden wybor: --sheet, --bbox albo --geometry",
    ),
    "hsg_calculation": Text("HSG calculation", "obliczenie HSG"),
    "plan_requires_upgrade": Text(
        "The update plan requires update='upgrade'",
        "Plan aktualizacji wymaga update='upgrade'",
    ),
    "hsg_all_nodata": Text(
        "{relative_to}: HSG has no data at all - clay, sand and silt are zeros "
        "(SoilGrids has no data: sea, water, built-up areas, rock, ice); check --bbox",
        "{relative_to}: HSG w calosci bez danych - clay, sand i silt sa zerami "
        "(SoilGrids nie ma danych: morze, woda, zabudowa, skaly, lod); sprawdz --bbox",
    ),
    "stat_nodata_description": Text(
        "No data: cells without input values (class 0)",
        "Brak danych: komorki bez wartosci wejsc (klasa 0)",
    ),
    "pixel_m_not_positive": Text(
        "pixel_m must be positive (got {pixel_m})",
        "pixel_m musi byc dodatni (podano {pixel_m})",
    ),
}
