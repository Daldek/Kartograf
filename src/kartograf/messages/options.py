"""Messages of the area ``options``."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.options``.
    "expected_min_x_min_y_max": Text(
        "Expected: min_x,min_y,max_x,max_y (e.g. 450000,550000,460000,560000)",
        "Oczekiwano: min_x,min_y,max_x,max_y (np. 450000,550000,460000,560000)",
    ),
    "invalid_bbox_unsupported_crs": Text(
        "Invalid bbox: unsupported CRS {crs!r} - available: {bbox_crs_choices}",
        "Nieprawidlowy bbox: nieobslugiwany uklad {crs!r} - dostepne: "
        "{bbox_crs_choices}",
    ),
    "invalid_bbox_bbox_zero_area": Text(
        "Invalid bbox: a bbox with zero area (min == max): {coords}; expected min_x < "
        "max_x and min_y < max_y. {bbox_expected}",
        "Nieprawidlowy bbox: bbox o zerowej powierzchni (min == max): {coords}; "
        "oczekiwano min_x < max_x i min_y < max_y. {bbox_expected}",
    ),
    "invalid_bbox_coordinates_lie_outside": Text(
        "Invalid bbox: coordinates {coords} lie outside the range of EPSG:4326 "
        "(longitude -180..180, latitude -90..90). {bbox_crs_remedy}. {bbox_expected}",
        "Nieprawidlowy bbox: wspolrzedne {coords} leza poza zakresem EPSG:4326 "
        "(dlugosc -180..180, szerokosc -90..90). {bbox_crs_remedy}. {bbox_expected}",
    ),
    "bbox_crs_remedy_hint": Text("{bbox_crs_remedy}.", "{bbox_crs_remedy}."),
}
