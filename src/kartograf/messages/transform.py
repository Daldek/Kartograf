"""Messages of the CRS transformations, the GeoPackage writer and the reprojection."""

from kartograf.messages import Text

MESSAGES = {
    # ``transform.crs``.
    "transformation_returned_infinite_value": Text(
        "The transformation returned an infinite value [{description}]",
        "Transformacja zwrocila wartosc nieskonczona [{description}]",
    ),
    "gdal_operation_needs_known_pair_systems": Text(
        "A GDAL operation needs a known pair of systems [{description}] - the "
        "PinnedTransform was built without them",
        "Operacja GDAL wymaga znanej pary ukladow [{description}] - PinnedTransform "
        "zbudowany bez nich",
    ),
    "grids_pl86_2019_pl07_2019_not": Text(
        "The grids pl86_2019/pl07_2019 are not public - install them manually into "
        "PROJ_DATA or use EVRF2007 (EPSG:5621).",
        "Siatki pl86_2019/pl07_2019 nie sa publiczne - zainstaluj je recznie do "
        "PROJ_DATA albo uzyj EVRF2007 (EPSG:5621).",
    ),
    "no_safe_transformation_operation": Text(
        "No safe transformation operation {src_crs} -> {dst_crs} (candidates: "
        "{transformers_count}, rejected: {rejected_count})",
        "Brak bezpiecznej operacji transformacji {src_crs} -> {dst_crs} (kandydatow: "
        "{transformers_count}, odrzuconych: {rejected_count})",
    ),
    # ``transform.gpkg``.
    "gdal_did_not_read_page": Text(
        "{context}: GDAL did not read the page {name}: {error}",
        "{context}: GDAL nie odczytal strony {name}: {error}",
    ),
    "field_has_type_page_earlier_ones": Text(
        "{context}: the field {name} has the type {dtype} on the page {page_name} and "
        "{known} on the earlier ones",
        "{context}: pole {name} ma na stronie {page_name} typ {dtype}, a na "
        "wczesniejszych {known}",
    ),
    "gdal_read_different_number_features_page": Text(
        "{context}: GDAL read a different number of features of the page",
        "{context}: GDAL odczytal inna liczbe obiektow strony",
    ),
    "gdal_read_different_number_features_page_2": Text(
        "{context}: GDAL read a different number of features of the page {name}",
        "{context}: GDAL odczytal inna liczbe obiektow strony {name}",
    ),
    "page_has_feature_whose_properties_not": Text(
        "{context}: the page {name} has a feature whose properties are not a "
        "dictionary",
        "{context}: strona {name} ma obiekt z properties innym niz slownik",
    ),
    "property_id_differs_feature_identifier": Text(
        "{context}: the property id={id_value!r} differs from the feature identifier "
        "{ident!r}",
        "{context}: wlasciwosc id={id_value!r} rozna od identyfikatora obiektu "
        "{ident!r}",
    ),
    "layer_schema_has_no_field": Text(
        "{context}: the layer schema has no field {id_field}",
        "{context}: schemat warstwy nie ma pola {id_field}",
    ),
    "value_field_not_type": Text(
        "{context}: the value {value!r} of the field {name} is not of the type {esri}",
        "{context}: wartosc {value!r} pola {name} nie jest typu {esri}",
    ),
    "feature_without_identifier": Text(
        "{context}: feature without an identifier {id_field}",
        "{context}: obiekt bez identyfikatora {id_field}",
    ),
    "feature_occurs_twice_different_content": Text(
        "{context}: the feature {id_field}={ident!r} occurs twice with different "
        "content",
        "{context}: obiekt {id_field}={ident!r} wystepuje dwa razy z inna trescia",
    ),
    "pages_give_different_features": Text(
        "{context}: the pages give {rows_count} different features, expected "
        "{matched} (incomplete response)",
        "{context}: strony daja {rows_count} roznych obiektow, oczekiwano {matched} "
        "(niepelna odpowiedz)",
    ),
    "identifiers_not_comparable": Text(
        "{source}: the identifiers {id_field} are not comparable",
        "{source}: identyfikatory {id_field} nie sa porownywalne",
    ),
    # ``transform.raster``.
    "warp_grid_source_has_bands": Text(
        "warp_to_grid: the source {name} has {count} bands - the reprojection "
        "supports only single-band rasters",
        "warp_to_grid: zrodlo {name} ma {count} pasm - reprojekcja obsluguje tylko "
        "rastry jednopasmowe",
    ),
    "inconsistent_pair_systems": Text(
        "Inconsistent pair of systems: the pinned operation is {src_crs} -> "
        "{dst_crs}, but the requested reprojection is {want_src} -> {want_dst} "
        "[{description}]",
        "Niespojna para ukladow: operacja przypieta to {src_crs} -> {dst_crs}, a "
        "zadana reprojekcja {want_src} -> {want_dst} [{description}]",
    ),
    "warp_grid_no_input_rasters": Text(
        "warp_to_grid: no input rasters",
        "warp_to_grid: brak rastrow wejsciowych",
    ),
}
