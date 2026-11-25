"""Messages of the sheet code parsers and the geometry readers (``kartograf.core``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``core.bbox``.
    "bbox_coordinates_must_be_finite": Text(
        "bbox coordinates must be finite, got {coords}",
        "współrzędne bboxa muszą być skończone, otrzymano {coords}",
    ),
    "bbox_inverted": Text(
        "bbox is inverted (min > max): {coords}; expected min_x <= max_x and min_y <= "
        "max_y",
        "bbox odwrócony (min > max): {coords}; oczekiwano min_x <= max_x i min_y <= "
        "max_y",
    ),
    "bbox_crs_mismatch": Text(
        "bbox is in {found!r}, expected {expected!r}",
        "bbox w układzie {found!r}, oczekiwano {expected!r}",
    ),
    # ``core.geometry``.
    "gpkg_geometry_without_envelope_header": Text(
        "GPKG geometry without an envelope in the header (envelope_type=0) for WKB "
        "type {wkb_type} - rebuild the file with envelopes (e.g. ogr2ogr) or use SHP",
        "Geometria GPKG bez obwiedni w nagłówku (envelope_type=0) dla typu WKB "
        "{wkb_type} - przebuduj plik z obwiedniami (np. ogr2ogr) albo użyj SHP",
    ),
    "no_prj_file_shapefile": Text(
        "No .prj file of the shapefile: {prj_path}. The coordinate system cannot be "
        "determined.",
        "Brak pliku .prj shapefile: {prj_path}. Nie da się ustalić układu "
        "współrzędnych.",
    ),
    "cannot_read_coordinate_system": Text(
        "Cannot read the coordinate system from {prj_path}: {error}",
        "Nie da się odczytać układu z {prj_path}: {error}",
    ),
    "no_geometry_column_metadata_table": Text(
        "No geometry column metadata of the table '{table_name}'",
        "Brak metadanych kolumny geometrii tabeli '{table_name}'",
    ),
    "no_srs_definition_srs_id": Text(
        "No SRS definition for srs_id={srs_id}",
        "Brak definicji SRS dla srs_id={srs_id}",
    ),
    "cannot_read_coordinate_system_srs_id": Text(
        "Cannot read the coordinate system for srs_id={srs_id}: {error}",
        "Nie da się odczytać układu dla srs_id={srs_id}: {error}",
    ),
    "no_feature_tables_geopackage": Text(
        "No feature tables in the GeoPackage: {filepath}",
        "Brak tabel obiektów w GeoPackage: {filepath}",
    ),
    "no_layer_geopackage": Text(
        "No layer '{layer}' in the GeoPackage. Available layers: {tables}",
        "Brak warstwy '{layer}' w GeoPackage. Dostępne warstwy: {tables}",
    ),
    "no_features_geometry": Text(
        "No features with geometry in: {filepath}",
        "Brak obiektów z geometrią w: {filepath}",
    ),
    "unreadable_feature_geometry": Text(
        "Cannot read the geometry of feature {number} of {filepath}: {error}",
        "Nie da się odczytać geometrii obiektu {number} z {filepath}: {error}",
    ),
    "gpkg_invalid_envelope_indicator": Text(
        "the GeoPackage geometry header has the invalid envelope contents "
        "indicator {indicator}",
        "nagłówek geometrii GeoPackage ma nieprawidłowy wskaźnik obwiedni {indicator}",
    ),
    "not_geojson": Text(
        "Not a GeoJSON FeatureCollection, Feature or geometry: {filepath}",
        "To nie jest GeoJSON (FeatureCollection, Feature ani geometria): {filepath}",
    ),
    "not_geojson_driver": Text(
        "Not a GeoJSON FeatureCollection, Feature or geometry: {filepath} (GDAL "
        "reads it as {driver})",
        "To nie jest GeoJSON (FeatureCollection, Feature ani geometria): {filepath} "
        "(GDAL czyta go jako {driver})",
    ),
    # ``core.parser_2000``.
    "sheet_code_must_be_string": Text(
        "The sheet code must be a string, got: {sheet_type}",
        "Godło musi być stringiem, otrzymano: {sheet_type}",
    ),
    "sheet_code_must_not_be_empty": Text(
        "The sheet code must not be empty",
        "Godło nie może być puste",
    ),
    "pl2000_code_is_pl1992": Text(
        "Invalid PL-2000 sheet code: '{sheet}'. The PL-1992 format (with hyphens) is "
        "not supported by Parser2000.",
        "Nieprawidłowe godło PL-2000: '{sheet}'. Format PL-1992 (z myślnikami) nie "
        "jest obsługiwany przez Parser2000.",
    ),
    "pl2000_code_format": Text(
        "Invalid PL-2000 sheet code: '{sheet}'. The sheet code must have the format: "
        "zone.strip.column[.subdivisions]",
        "Nieprawidłowe godło PL-2000: '{sheet}'. Godło musi być w formacie: "
        "strefa.pas.słup[.subdivisions]",
    ),
    "sheet_code_parsing_error": Text(
        "Sheet code parsing error: {sheet}",
        "Błąd parsowania godła: {sheet}",
    ),
    "invalid_1_2000_sheet_number": Text(
        "Invalid 1:2000 sheet number: {ark_val}. Allowed values: 01-25.",
        "Nieprawidłowy numer arkusza 1:2000: {ark_val}. Dozwolone wartości: 01-25.",
    ),
    "scale_system_2000": Text(
        "{sheet} (scale {scale}, system 2000)",
        "{sheet} (skala {scale}, układ 2000)",
    ),
    "unsupported_coordinate_system": Text(
        "Unsupported coordinate system: {crs}. Supported: {supported_crs}",
        "Nieobsługiwany układ współrzędnych: {crs}. Obsługiwane: {supported_crs}",
    ),
    "unknown_scale_allowed": Text(
        "Unknown scale: {target_scale}. Allowed: {scale_hierarchy_2000}",
        "Nieznana skala: {target_scale}. Dozwolone: {scale_hierarchy_2000}",
    ),
    "target_scale_coarser_current_scale": Text(
        "The target scale {target_scale} is coarser than the current scale {scale}.",
        "Skala docelowa {target_scale} jest grubsza niż bieżąca skala {scale}.",
    ),
    "sheet_1_5000_has_no_descendants": Text(
        "The 1:5000 sheet has no descendants at the scale {target_scale}. The 1:5000 "
        "branch is independent and has no finer divisions.",
        "Arkusz 1:5000 nie ma potomków w skali {target_scale}. Gałąź 1:5000 jest "
        "niezależna i nie ma drobniejszych podziałków.",
    ),
    "sheet_has_no_descendants_scale": Text(
        "The sheet {sheet} ({scale}) has no descendants at the scale {target_scale}.",
        "Arkusz {sheet} ({scale}) nie ma potomków w skali {target_scale}.",
    ),
    "invalid_scale_allowed": Text(
        "Invalid scale: '{target_scale}'. Allowed: {scale_hierarchy_2000}",
        "Nieprawidłowa skala: '{target_scale}'. Dozwolone: {scale_hierarchy_2000}",
    ),
    # ``core.parser_tm33``.
    "tm33_sheet_code_must_be_string": Text(
        "The TM33 sheet code must be a string, got: {sheet_type}",
        "Godło TM33 musi być stringiem, otrzymano: {sheet_type}",
    ),
    "tm33_code_format": Text(
        "Invalid TM33 sheet code: '{sheet}' (expected EEE_NNNN, e.g. 302_5550)",
        "Niepoprawne godło TM33: '{sheet}' (oczekiwano EEE_NNNN, np. 302_5550)",
    ),
    "tm33_code_odd_km": Text(
        "Invalid TM33 sheet code: '{sheet}' (tiles every 2 km - the kilometres must be "
        "even)",
        "Niepoprawne godło TM33: '{sheet}' (kafle co 2 km - kilometry muszą być "
        "parzyste)",
    ),
    "invalid_bbox": Text(
        "Invalid bbox: ({min_x}, {min_y}, {max_x}, {max_y})",
        "Niepoprawny bbox: ({min_x}, {min_y}, {max_x}, {max_y})",
    ),
    # ``core.sheet_parser``.
    "zone_number_not_sheet": Text(
        "Invalid sheet code: '{sheet}'. This is a PL-2000 zone number, not a sheet "
        "code. The coarsest PL-2000 sheet code has the format zone.strip.column "
        "(1:10000), e.g. 6.179.12.",
        "Nieprawidłowe godło: '{sheet}'. To numer strefy PL-2000, a nie godło arkusza. "
        "Najgrubsze godło PL-2000 ma format strefa.pas.słup (1:10000), np. 6.179.12.",
    ),
    "sheet_code_has_pl_2000_format": Text(
        "The sheet code '{cleaned}' has the PL-2000 format, but "
        "sheet_system='{sheet_system}' was given",
        "Godło '{cleaned}' ma format PL-2000, ale podano sheet_system='{sheet_system}'",
    ),
    "sheet_code_has_pl_1992_format": Text(
        "The sheet code '{cleaned}' has the PL-1992 format, but sheet_system='2000' "
        "was given",
        "Godło '{cleaned}' ma format PL-1992, ale podano sheet_system='2000'",
    ),
    "invalid_system_allowed_values": Text(
        "Invalid system: '{system}'. Allowed values: {valid_systems}",
        "Nieprawidłowy układ: '{system}'. Dozwolone wartości: {valid_systems}",
    ),
    "sheet_code_unknown_format": Text(
        "Invalid sheet code: '{original_sheet}'. Expected a PL-1992 sheet code (e.g. "
        "N-34-130-D-d-2-4) or a PL-2000 one (e.g. 6.179.12).",
        "Nieprawidłowe godło: '{original_sheet}'. Oczekiwano godła PL-1992 (np. "
        "N-34-130-D-d-2-4) albo PL-2000 (np. 6.179.12).",
    ),
    "row_allowed_m": Text("row {pas} (allowed: M, N)", "pas {pas} (dozwolone: M, N)"),
    "column_allowed_33_35": Text(
        "column {slup} (allowed: 33-35)",
        "słup {slup} (dozwolone: 33-35)",
    ),
    "sheet_allowed_1_144": Text(
        "sheet {sheet} (allowed: 1-144)",
        "arkusz {sheet} (dozwolone: 1-144)",
    ),
    "sheet_code_out_of_range": Text(
        "Invalid sheet code: '{original_sheet}' - outside the range of the PL-1992 "
        "nomenclature: {problems:join}",
        "Nieprawidłowe godło: '{original_sheet}' - poza zakresem nomenklatury PL-1992: "
        "{problems:join}",
    ),
    "scale_system": Text(
        "{sheet} (scale {scale}, system {system})",
        "{sheet} (skala {scale}, układ {system})",
    ),
    "invalid_scale_allowed_2": Text(
        "Invalid scale: '{target_scale}'. Allowed: {scale_hierarchy}",
        "Nieprawidłowa skala: '{target_scale}'. Dozwolone: {scale_hierarchy}",
    ),
    "target_scale_must_be_larger": Text(
        "The target scale {target_scale} must be larger (more detailed) than the "
        "current {scale}",
        "Skala docelowa {target_scale} musi być większa (bardziej szczegółowa) niż "
        "bieżąca {scale}",
    ),
    "unsupported_coordinate_system_2": Text(
        "Unsupported coordinate system: {crs}. Supported: EPSG:2180, EPSG:4326",
        "Nieobsługiwany układ współrzędnych: {crs}. Obsługiwane: EPSG:2180, EPSG:4326",
    ),
    "unsupported_sheet_system": Text(
        "Unsupported sheet system: {sheet_system!r}. Allowed: '1992', '2000'",
        "Nieobsługiwany system godeł: {sheet_system!r}. Dozwolone: '1992', '2000'",
    ),
    # ``core.geometry``.
    "unsupported_geometry_format": Text(
        "Unsupported geometry format: '{ext}'. Supported: {supported_extensions}",
        "Nieobsługiwany format geometrii: '{ext}'. Obsługiwane: {supported_extensions}",
    ),
    # ``core.sheet_parser``.
    "unsupported_crs_supported": Text(
        "Unsupported CRS: '{crs}'. Supported: {pl_bbox_crs}",
        "Nieobsługiwany CRS: '{crs}'. Obsługiwane: {pl_bbox_crs}",
    ),
}
