"""Messages of the hydrologic soil groups (HSG)."""

from kartograf.messages import Text

MESSAGES = {
    # ``hydrology.hsg``.
    "class_a": Text(
        "High infiltration - sandy soils, low runoff potential",
        "Duża infiltracja - gleby piaszczyste, mały potencjał spływu",
    ),
    "class_b": Text(
        "Moderate infiltration - loamy soils, moderate runoff",
        "Umiarkowana infiltracja - gleby gliniaste, umiarkowany spływ",
    ),
    "class_c": Text(
        "Low infiltration - clay loams, high runoff",
        "Mała infiltracja - gliny ilaste, duży spływ",
    ),
    "class_d": Text(
        "Very low infiltration - clay soils, very high runoff",
        "Bardzo mała infiltracja - gleby ilaste, bardzo duży spływ",
    ),
    "hsg_output_files": Text(
        "inputs in <DIR>/soil/..., HSG in <DIR>/hsg/...",
        "wejścia w <KATALOG>/soil/..., HSG w <KATALOG>/hsg/...",
    ),
    "root_is_store_dir": Text(
        "--root is a store directory (since 0.8.0); for a file outside the store "
        "use hsg_from_rasters",
        "--root to katalog magazynu (od 0.8.0); plik poza magazynem: hsg_from_rasters",
    ),
    "exactly_one_selection": Text(
        "Give exactly one selection: --sheet, --bbox or --geometry",
        "Podaj dokładnie jeden wybór: --sheet, --bbox albo --geometry",
    ),
    "depth_with_depth_rule": Text(
        "Give exactly one of --depth and --depth-rule: the rule reads the layers "
        "of 0-100cm itself",
        "Podaj dokładnie jedno z --depth i --depth-rule: reguła sama czyta warstwy "
        "0-100cm",
    ),
    "depth_rule_not_allowed": Text(
        "Unknown --depth-rule '{value}'; allowed: {rules:join}",
        "Nieznana --depth-rule '{value}'; dozwolone: {rules:join}",
    ),
    "hsg_calculation": Text("HSG calculation", "obliczenie HSG"),
    "plan_requires_upgrade": Text(
        "The update plan requires update='upgrade'",
        "Plan aktualizacji wymaga update='upgrade'",
    ),
    "hsg_all_nodata": Text(
        "{relative_to}: HSG has no data at all - clay, sand and silt are zeros "
        "(SoilGrids has no data: sea, water, built-up areas, rock, ice); check --bbox",
        "{relative_to}: HSG w całości bez danych - clay, sand i silt są zerami "
        "(SoilGrids nie ma danych: morze, woda, zabudowa, skały, lód); sprawdź --bbox",
    ),
    "stat_nodata_description": Text(
        "No data: cells without input values (class 0)",
        "Brak danych: komórki bez wartości wejść (klasa 0)",
    ),
    "pixel_m_not_positive": Text(
        "pixel_m must be positive (got {pixel_m})",
        "pixel_m musi być dodatni (podano {pixel_m})",
    ),
}
