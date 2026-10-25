"""Messages of the area ``sheet_info``."""

from kartograf.messages import Text

MESSAGES = {
    # ``sheet_info``.
    "cz_codes": Text(
        "CZ sheet codes: SM5 (e.g. CTES96), TM33 tile (e.g. 302_5550), ZTM (e.g. "
        "0510-D-11, NM-34-07-1-D-15).",
        "Godla CZ: SM5 (np. CTES96), kafel TM33 (np. 302_5550), ZTM (np. 0510-D-11, "
        "NM-34-07-1-D-15).",
    ),
    "must_be_switch": Text(
        "{flag} must be a switch (True or False), got {value!r}",
        "{flag} musi byc przelacznikiem (True albo False), otrzymano {value!r}",
    ),
    "descendants_must_be_string": Text(
        "--descendants must be a string (str), got {descendants!r}",
        "--descendants musi byc napisem (str), otrzymano {descendants!r}",
    ),
    "hierarchy_children_descendants_apply": Text(
        "--hierarchy, --children and --descendants apply only to PL sheet codes "
        "(PL-1992, PL-2000)",
        "--hierarchy, --children i --descendants dotycza tylko godel PL (PL-1992, "
        "PL-2000)",
    ),
    "error_with_cz_codes": Text("{error} {cz_codes}", "{error} {cz_codes}"),
    "give_exactly_one_area_choice": Text(
        "Give exactly one area choice: bbox or geometry",
        "Podaj dokladnie jeden wybor obszaru: bbox albo geometry",
    ),
    "layer_must_be_string": Text(
        "layer must be a string (str), got {layer!r}",
        "layer musi byc napisem (str), otrzymano {layer!r}",
    ),
    "layer_applies_only_geometry": Text(
        "layer applies only to geometry (a layer of the GPKG file with the area)",
        "layer dotyczy tylko geometry (warstwa pliku GPKG z obszarem)",
    ),
    "bbox_must_be_bbox_object": Text(
        "bbox must be a BBox object (with a CRS), got {bbox!r}",
        "bbox musi byc obiektem BBox (z ukladem), otrzymano {bbox!r}",
    ),
    "geometry_must_be_file_path": Text(
        "geometry must be a file path, got {geometry!r}",
        "geometry musi byc sciezka pliku, otrzymano {geometry!r}",
    ),
}
