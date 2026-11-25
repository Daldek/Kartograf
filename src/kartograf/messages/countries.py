"""Messages of the area ``countries``."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.countries``.
    "check_bbox_crs": Text(
        "Check --bbox-crs (default EPSG:2180; S-JTSK coordinates: --bbox-crs "
        "EPSG:5514) and the axis order (EPSG:4326: longitude,latitude)",
        "Sprawdź --bbox-crs (domyślnie EPSG:2180; współrzędne S-JTSK: --bbox-crs "
        "EPSG:5514) i kolejność osi (EPSG:4326: długość,szerokość)",
    ),
    "lies_outside_epsg_4326": Text(
        "{flag} ({crs}) lies outside {code} (in EPSG:4326: {coords})",
        "{flag} ({crs}) leży poza {code} (w EPSG:4326: {coords})",
    ),
    "check_coordinate_system_geometry_file": Text(
        "{text}. Check the coordinate system of the geometry file",
        "{text}. Sprawdź układ współrzędnych pliku geometrii",
    ),
    "with_remedy": Text("{text}. {remedy}", "{text}. {remedy}"),
    "with_swapped_axes": Text(
        "{text}; the axes look swapped: --bbox {coords}",
        "{text}; osie wyglądają na zamienione: --bbox {coords}",
    ),
}
