"""Messages of the CRS transformations, the GeoPackage writer and the reprojection."""

from kartograf.messages import Text

MESSAGES = {
    # ``transform.crs``.
    "transformation_returned_infinite_value": Text(
        "The transformation returned an infinite value [{description}]",
        "Transformacja zwróciła wartość nieskończoną [{description}]",
    ),
    "gdal_operation_needs_known_pair_systems": Text(
        "A GDAL operation needs a known pair of systems [{description}] - the "
        "PinnedTransform was built without them",
        "Operacja GDAL wymaga znanej pary układów [{description}] - PinnedTransform "
        "zbudowany bez nich",
    ),
    "grids_pl86_2019_pl07_2019_not": Text(
        "The grids pl86_2019/pl07_2019 are not public - install them manually into "
        "PROJ_DATA or use EVRF2007 (EPSG:5621).",
        "Siatki pl86_2019/pl07_2019 nie są publiczne - zainstaluj je ręcznie do "
        "PROJ_DATA albo użyj EVRF2007 (EPSG:5621).",
    ),
    "no_safe_transformation_operation": Text(
        "No safe transformation operation {src_crs} -> {dst_crs} (candidates: "
        "{transformers_count}, rejected: {rejected_count})",
        "Brak bezpiecznej operacji transformacji {src_crs} -> {dst_crs} (kandydatów: "
        "{transformers_count}, odrzuconych: {rejected_count})",
    ),
    # ``transform.gpkg``.
    "gdal_did_not_read_page": Text(
        "{context}: GDAL did not read the page {name}: {error}",
        "{context}: GDAL nie odczytał strony {name}: {error}",
    ),
    "field_has_type_page_earlier_ones": Text(
        "{context}: the field {name} has the type {dtype} on the page {page_name} and "
        "{known} on the earlier ones",
        "{context}: pole {name} ma na stronie {page_name} typ {dtype}, a na "
        "wcześniejszych {known}",
    ),
    "gdal_read_different_number_features_page": Text(
        "{context}: GDAL read a different number of features of the page",
        "{context}: GDAL odczytał inną liczbę obiektów strony",
    ),
    "gdal_read_different_number_features_page_2": Text(
        "{context}: GDAL read a different number of features of the page {name}",
        "{context}: GDAL odczytał inną liczbę obiektów strony {name}",
    ),
    "page_has_feature_whose_properties_not": Text(
        "{context}: the page {name} has a feature whose properties are not a "
        "dictionary",
        "{context}: strona {name} ma obiekt z properties innym niż słownik",
    ),
    "property_id_differs_feature_identifier": Text(
        "{context}: the property id={id_value!r} differs from the feature identifier "
        "{ident!r}",
        "{context}: właściwość id={id_value!r} różna od identyfikatora obiektu "
        "{ident!r}",
    ),
    "layer_schema_has_no_field": Text(
        "{context}: the layer schema has no field {id_field}",
        "{context}: schemat warstwy nie ma pola {id_field}",
    ),
    "value_field_not_type": Text(
        "{context}: the value {value!r} of the field {name} is not of the type {esri}",
        "{context}: wartość {value!r} pola {name} nie jest typu {esri}",
    ),
    "feature_without_identifier": Text(
        "{context}: feature without an identifier {id_field}",
        "{context}: obiekt bez identyfikatora {id_field}",
    ),
    "feature_occurs_twice_different_content": Text(
        "{context}: the feature {id_field}={ident!r} occurs twice with different "
        "content",
        "{context}: obiekt {id_field}={ident!r} występuje dwa razy z inną treścią",
    ),
    "pages_give_different_features": Text(
        "{context}: the pages give {rows_count} different features, expected "
        "{matched} (incomplete response)",
        "{context}: strony dają {rows_count} różnych obiektów, oczekiwano {matched} "
        "(niepełna odpowiedź)",
    ),
    "identifiers_not_comparable": Text(
        "{source}: the identifiers {id_field} are not comparable",
        "{source}: identyfikatory {id_field} nie są porównywalne",
    ),
    "archive_unreadable": Text(
        "{context}: GDAL cannot read it: {error}",
        "{context}: GDAL nie odczytuje: {error}",
    ),
    "archive_geodatabases": Text(
        "{archive}: {count} geodatabases (*.gdb directories) in the archive, expected "
        "one",
        "{archive}: {count} geobaz (katalogów *.gdb) w archiwum, oczekiwano jednej",
    ),
    "archive_missing_layers": Text(
        "{context}: no layer {missing} in the geodatabase",
        "{context}: brak warstwy {missing} w geobazie",
    ),
    "archive_layer_identifier": Text(
        "{context}: the identifier column is {found}, expected {expected}",
        "{context}: kolumna identyfikatora to {found}, oczekiwano {expected}",
    ),
    "archive_layer_grid": Text(
        "{context}: the CRS {found} does not have the projection of {crs}; nothing is "
        "reprojected",
        "{context}: układ {found} nie ma odwzorowania {crs}; nic nie jest przeliczane",
    ),
    "archive_geometry": Text(
        "{context}: a geometry cannot be compared with the area: {error}",
        "{context}: geometrii nie da się porównać z obszarem: {error}",
    ),
    "archive_no_features": Text(
        "{context}: no feature of {codes} intersects {bbox} ({crs})",
        "{context}: żaden obiekt {codes} nie przecina {bbox} ({crs})",
    ),
    # ``transform.raster``.
    "warp_grid_source_has_bands": Text(
        "warp_to_grid: the source {name} has {count} bands - the reprojection "
        "supports only single-band rasters",
        "warp_to_grid: źródło {name} ma {count} pasm - reprojekcja obsługuje tylko "
        "rastry jednopasmowe",
    ),
    "inconsistent_pair_systems": Text(
        "Inconsistent pair of systems: the pinned operation is {src_crs} -> "
        "{dst_crs}, but the requested reprojection is {want_src} -> {want_dst} "
        "[{description}]",
        "Niespójna para układów: operacja przypięta to {src_crs} -> {dst_crs}, a "
        "żądana reprojekcja {want_src} -> {want_dst} [{description}]",
    ),
    "warp_grid_no_input_rasters": Text(
        "warp_to_grid: no input rasters",
        "warp_to_grid: brak rastrów wejściowych",
    ),
}
