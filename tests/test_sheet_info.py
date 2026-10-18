"""Sheet codes as documents (spec 5.4.4-5.4.5): ``describe_sheet`` and
``find_sheets``, their keys, their errors and their agreement with the library
functions and the facts the CLI text gave."""

import json
from pathlib import Path

import pytest

from kartograf import sheet_info
from kartograf.catalog.build import build_catalog
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import Command, Group, Param
from kartograf.core.bbox import BBox
from kartograf.core.geometry import find_sheets_for_geometry
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000, ZONE_EPSG
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.serialization import SCHEMAS
from kartograf.sheet_info import (
    SheetDescendants,
    SheetInfo,
    SheetLevel,
    SheetList,
    describe_sheet,
    find_sheets,
)

PL1992 = "N-34-130-D-d-2-4"
PL2000 = "6.179.12.20"
SM5 = "CTES96"
TM33 = "302_5550"
ZTM_SJTSK = "0510-D-11"
ZTM_ETRS89 = "NM-34-07-1-D-15"
SCALES_1992 = tuple(SheetParser.SCALE_HIERARCHY)

# the ``commands`` of the sheet systems: the ``Komendy:`` lines the CLI printed
# for the CZ codes and the literal of spec 5.4.4 for a PL code
_PL_COMMANDS = (
    "elevation download",
    "elevation availability",
    "imagery download",
    "landcover download",
    "soil download",
    "soil hsg",
    "boundaries download",
    "cadastre download",
    "models3d download",
    "names download",
    "maps download",
    "geodesy download",
)
_COMMANDS = {
    "pl1992": _PL_COMMANDS,
    "pl2000": _PL_COMMANDS,
    "cz_sm5": ("elevation download", "elevation availability", "imagery download"),
    "cz_tm33": ("elevation download", "elevation availability"),
    "cz_ztm": ("maps download",),
}
_CODES = {
    "pl1992": PL1992,
    "pl2000": PL2000,
    "cz_sm5": SM5,
    "cz_tm33": TM33,
    "cz_ztm": ZTM_SJTSK,
}


def test_describe_pl1992_sheet():
    info = describe_sheet(PL1992)

    assert (info.sheet, info.system, info.country) == (PL1992, "pl1992", "PL")
    assert (info.sheet_system, info.scale) == ("1992", "1:10000")
    assert dict(info.components or {}) == {
        "pas": "N",
        "slup": "34",
        "arkusz_200k": "130",
        "arkusz_100k": "D",
        "arkusz_50k": "d",
        "arkusz_25k": "2",
        "arkusz_10k": "4",
    }
    assert list(info.components or {}) == [
        "pas",
        "slup",
        "arkusz_200k",
        "arkusz_100k",
        "arkusz_50k",
        "arkusz_25k",
        "arkusz_10k",
    ]
    assert (info.zone, info.crs) == (None, "EPSG:2180")
    assert info.bounds == SheetParser(PL1992).get_bbox()
    assert info.bounds is not None and info.bounds.crs == info.crs
    assert (info.hierarchy, info.children, info.descendants) == (None, None, None)


def test_the_code_is_returned_in_its_canonical_form():
    assert describe_sheet("  n-34-130-d-d-2-4 ").sheet == PL1992
    assert describe_sheet(f" {SM5} ").sheet == SM5
    assert describe_sheet(f" {TM33}\n").sheet == TM33


def test_describe_pl2000_sheet():
    info = describe_sheet(PL2000)

    assert (info.sheet, info.system, info.country) == (PL2000, "pl2000", "PL")
    assert (info.sheet_system, info.scale) == ("2000", "1:2000")
    assert dict(info.components or {}) == {
        "strefa": "6",
        "pas": "179",
        "slup": "12",
        "ark_2k": "20",
    }
    assert (info.zone, info.crs) == (6, ZONE_EPSG[6])
    assert info.bounds == SheetParser(PL2000).get_bbox()
    assert info.bounds is not None and info.bounds.crs == ZONE_EPSG[6]


def test_describe_cz_sheets():
    sm5 = describe_sheet(SM5)
    tm33 = describe_sheet(TM33)
    sjtsk = describe_sheet(ZTM_SJTSK)
    etrs89 = describe_sheet(ZTM_ETRS89)

    # the frame of an SM5 or ZTM sheet is in the CUZK index (network): no bounds
    assert (sm5.system, sm5.country, sm5.sheet_system) == ("cz_sm5", "CZ", None)
    assert (sm5.crs, sm5.bounds) == ("EPSG:5514", None)
    assert (tm33.system, tm33.country, tm33.sheet_system) == ("cz_tm33", "CZ", None)
    assert (tm33.crs, tm33.bounds) == ("EPSG:3045", ParserTM33(TM33).get_bbox())
    assert (sjtsk.system, sjtsk.sheet_system, sjtsk.crs) == (
        "cz_ztm",
        "sjtsk",
        "EPSG:5514",
    )
    assert (etrs89.system, etrs89.sheet_system, etrs89.crs) == (
        "cz_ztm",
        "etrs89",
        "EPSG:3045",
    )
    for info in (sm5, tm33, sjtsk, etrs89):
        assert info.country == "CZ"
        assert (info.scale, info.components, info.zone) == (None, None, None)
        assert (info.hierarchy, info.children, info.descendants) == (None, None, None)
    assert (sjtsk.bounds, etrs89.bounds) == (None, None)


def test_hierarchy_children_descendants_of_a_pl1992_sheet():
    parser = SheetParser(PL1992)

    info = describe_sheet(PL1992, hierarchy=True, children=True)
    big = describe_sheet("N-34-130-D", descendants="1:10000")

    assert info.hierarchy == tuple(
        SheetLevel(p.sheet, p.scale) for p in parser.get_hierarchy_up()
    )
    assert info.hierarchy is not None
    # from the sheet itself up to the 1:1000000 sheet
    assert info.hierarchy[0] == SheetLevel(PL1992, "1:10000")
    assert info.hierarchy[-1] == SheetLevel("N-34", "1:1000000")
    assert len(info.hierarchy) == 7
    assert info.children == tuple(
        SheetLevel(p.sheet, p.scale) for p in parser.get_children()
    )
    assert info.children is not None and len(info.children) == 4
    assert {child.scale for child in info.children} == {"1:5000"}
    assert info.descendants is None
    # never truncated (the CLI text showed four sheets of more than 20)
    expected = [
        p.sheet for p in SheetParser("N-34-130-D").get_all_descendants("1:10000")
    ]
    assert big.descendants == SheetDescendants("1:10000", 64, tuple(expected))
    assert len(expected) == 64 > 20
    assert (big.hierarchy, big.children) == (None, None)


def test_a_sheet_without_children_has_an_empty_list_not_none():
    info = describe_sheet("N-34-130-D-d-2-4-1", hierarchy=True, children=True)

    assert info.children == ()
    assert info.hierarchy is not None and info.hierarchy[0].scale == "1:5000"


def test_hierarchy_children_descendants_of_a_pl2000_sheet():
    info = describe_sheet(
        "6.179.12", hierarchy=True, children=True, descendants="1:2000"
    )

    assert info.hierarchy == (SheetLevel("6.179.12", "1:10000"),)
    assert info.children is not None and len(info.children) == 25
    assert info.children[0] == SheetLevel("6.179.12.01", "1:2000")
    assert info.descendants is not None
    assert (info.descendants.scale, info.descendants.count) == ("1:2000", 25)
    assert info.descendants.sheets[0] == "6.179.12.01"


@pytest.mark.parametrize(
    ("arguments", "option", "options"),
    [
        ({"hierarchy": True}, "hierarchy", None),
        ({"children": True}, "children", None),
        ({"descendants": "1:10000"}, "descendants", None),
        (
            {"children": True, "descendants": "1:10000"},
            "children",
            ("children", "descendants"),
        ),
        (
            {"hierarchy": True, "children": True, "descendants": "1:10000"},
            "hierarchy",
            ("hierarchy", "children", "descendants"),
        ),
    ],
)
@pytest.mark.parametrize("code", [SM5, TM33, ZTM_SJTSK, ZTM_ETRS89])
def test_cz_sheets_have_no_hierarchy_children_or_descendants(
    code, arguments, option, options
):
    with pytest.raises(ValidationError) as error:
        describe_sheet(code, **arguments)

    assert error.value.option == option
    assert error.value.options == options
    assert "tylko godel PL" in str(error.value)
    assert not isinstance(error.value, ParseError)


@pytest.mark.parametrize("scale", ["1:7", "", "1:5"])
def test_unknown_descendants_scale_names_the_option_and_the_scales(scale):
    with pytest.raises(ValidationError) as error:
        describe_sheet("N-34-130-D", descendants=scale)
    with pytest.raises(ValidationError) as error_2000:
        describe_sheet("6.179.12", descendants=scale)

    assert error.value.option == "descendants"
    assert error.value.allowed == SCALES_1992
    assert error_2000.value.option == "descendants"
    assert error_2000.value.allowed == tuple(SCALE_HIERARCHY_2000)


def test_descendants_scale_not_finer_than_the_sheet_is_an_error_of_the_option():
    with pytest.raises(ValidationError) as error:
        describe_sheet("N-34-130-D", descendants="1:200000")

    assert error.value.option == "descendants"
    assert error.value.allowed is None
    assert "musi byc wieksza" in str(error.value)


@pytest.mark.parametrize("code", ["XYZ", "", "   ", "N-99-1", "6.179", "1:5000"])
def test_bad_code_is_parse_error_with_option_sheet(code):
    with pytest.raises(ParseError) as error:
        describe_sheet(code)

    assert error.value.option == "sheet"
    assert error.value.code == "invalid_sheet_code"
    # the text of the CLI: the library's message and the CZ code formats
    assert "Godla CZ: SM5 (np. CTES96)" in str(error.value)


def test_bad_codes_that_are_not_text_or_off_the_tm33_grid():
    with pytest.raises(ParseError) as number:
        describe_sheet(5)  # type: ignore[arg-type]
    with pytest.raises(ParseError) as off_grid:
        describe_sheet("301_5550")

    assert number.value.option == "sheet"
    assert off_grid.value.option == "sheet"
    assert "kafle co 2 km" in str(off_grid.value)
    assert "Godla CZ:" not in str(off_grid.value)


def test_arguments_of_a_wrong_type_name_their_option():
    with pytest.raises(ValidationError) as hierarchy:
        describe_sheet(PL1992, hierarchy="yes")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as children:
        describe_sheet(PL1992, children=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as descendants:
        describe_sheet(PL1992, descendants=10000)  # type: ignore[arg-type]

    assert hierarchy.value.option == "hierarchy"
    assert children.value.option == "children"
    assert descendants.value.option == "descendants"
    for error in (hierarchy, children, descendants):
        assert not isinstance(error.value, ParseError)


def test_pl1992_document_is_the_spec_example():
    document = describe_sheet(PL1992).to_dict()

    bounds = document.pop("bounds")
    assert document == {
        "schema": "kartograf-sheet/1",
        "sheet": "N-34-130-D-d-2-4",
        "system": "pl1992",
        "country": "PL",
        "sheet_system": "1992",
        "scale": "1:10000",
        "components": {
            "pas": "N",
            "slup": "34",
            "arkusz_200k": "130",
            "arkusz_100k": "D",
            "arkusz_50k": "d",
            "arkusz_25k": "2",
            "arkusz_10k": "4",
        },
        "zone": None,
        "crs": "EPSG:2180",
        "commands": list(_PL_COMMANDS),
        "hierarchy": None,
        "children": None,
        "descendants": None,
    }
    assert isinstance(bounds, dict)
    assert bounds["crs"] == "EPSG:2180"
    assert bounds["bbox"] == pytest.approx(
        [769911.0902514459, 508419.16283969115, 772163.7346478042, 510851.5730979936]
    )
    assert list(describe_sheet(PL1992).to_dict()) == [
        "schema",
        "sheet",
        "system",
        "country",
        "sheet_system",
        "scale",
        "components",
        "zone",
        "crs",
        "bounds",
        "commands",
        "hierarchy",
        "children",
        "descendants",
    ]


def test_optional_blocks_are_objects_in_the_document():
    document = describe_sheet(
        "N-34-130-D", hierarchy=True, children=True, descendants="1:50000"
    ).to_dict()

    assert document["hierarchy"][0] == {"sheet": "N-34-130-D", "scale": "1:100000"}
    assert document["children"][0] == {"sheet": "N-34-130-D-a", "scale": "1:50000"}
    descendants = document["descendants"]
    assert list(descendants) == ["scale", "count", "sheets"]
    assert descendants["count"] == len(descendants["sheets"]) == 4
    assert json.loads(describe_sheet(TM33).to_json())["bounds"] == {
        "bbox": [302000.0, 5550000.0, 304000.0, 5552000.0],
        "crs": "EPSG:3045",
    }


def test_documents_are_registered_with_their_schemas():
    assert SCHEMAS["kartograf-sheet/1"] == (SheetInfo,)
    assert SCHEMAS["kartograf-sheets/1"] == (SheetList,)
    assert describe_sheet(SM5).schema == "kartograf-sheet/1"


def test_the_json_text_is_repeatable_and_ascii():
    first = describe_sheet(PL2000, hierarchy=True, children=True).to_json()
    second = describe_sheet(PL2000, hierarchy=True, children=True).to_json()

    assert first == second
    assert first.isascii()
    assert first.endswith("}\n")


# =============================================================================
# SheetInfo.commands follow the declarations of the catalog
# =============================================================================


def _accepting(system: str) -> list[str]:
    """The commands whose ``sheet`` declaration accepts ``system``, read from the
    declarations (not from the catalog document ``describe_sheet`` reads)."""
    return [
        command.id
        for command in declared().commands
        if any(
            p.name == "sheet" and system in (p.accepts or ()) for p in command.params
        )
    ]


@pytest.mark.parametrize("system", sorted(_CODES))
def test_commands_follow_the_accepts_of_the_catalog(system):
    info = describe_sheet(_CODES[system])

    assert info.system == system
    assert list(info.commands) == _accepting(system)
    assert info.commands == _COMMANDS[system]


def test_commands_come_from_the_catalog_not_from_a_copy(monkeypatch):
    def sheet(*accepts: str) -> Param:
        return Param("sheet", "str", "Godlo", accepts=accepts)

    def command(name: str, *params: Param) -> Command:
        return Command(
            f"elevation {name}",
            "Komenda",
            "query",
            "describe_sheet",
            "kartograf-sheet/1",
            params,
        )

    catalog = build_catalog(
        (
            command("download", sheet("pl1992")),
            command("list-sources"),
            command("availability", sheet("pl1992", "cz_sm5")),
        ),
        (Group("elevation", "Wysokosci", "Dane wysokosciowe"),),
        params=True,
    )
    monkeypatch.setattr(sheet_info, "get_catalog", lambda **_: catalog)

    assert describe_sheet(PL1992).commands == (
        "elevation download",
        "elevation availability",
    )
    assert describe_sheet(SM5).commands == ("elevation availability",)
    assert describe_sheet(TM33).commands == ()


def test_describe_sheet_needs_no_network():
    # the autouse guard of tests/conftest.py fails any non-loopback connection
    for code in (PL1992, PL2000, SM5, TM33, ZTM_SJTSK):
        assert describe_sheet(code, hierarchy=code in (PL1992, PL2000)).sheet == code


# =============================================================================
# find_sheets
# =============================================================================

_BBOX = BBox(565000, 242000, 569000, 246000, "EPSG:2180")


def test_find_sheets_equals_library_functions():
    document = find_sheets(bbox=_BBOX, scale="1:10000", sheet_system="1992")
    zone = BBox(6433000, 5815000, 6436500, 5818000, "EPSG:2177")
    fine = find_sheets(bbox=zone, scale="1:2000", sheet_system="2000")
    degrees = BBox(19.93, 50.05, 19.95, 50.07, "EPSG:4326")
    wide = find_sheets(bbox=degrees, scale="1:200000", sheet_system="1992")

    assert document.sheets == tuple(find_sheets_for_bbox(_BBOX, "1:10000", "1992"))
    assert fine.sheets == tuple(find_sheets_for_bbox(zone, "1:2000", "2000"))
    assert wide.sheets == tuple(find_sheets_for_bbox(degrees, "1:200000", "1992"))
    assert document.count == len(document.sheets) > 1
    assert list(document.sheets) == sorted(document.sheets)
    assert document.request == sheet_info.SheetRequest(
        "1:10000",
        "1992",
        (565000.0, 242000.0, 569000.0, 246000.0),
        "EPSG:2180",
        None,
        None,
    )
    assert fine.request.bbox_crs == "EPSG:2177"


def test_find_sheets_does_not_truncate():
    big = BBox(300000, 200000, 700000, 700000, "EPSG:2180")

    document = find_sheets(bbox=big, scale="1:50000", sheet_system="1992")

    assert document.count == len(find_sheets_for_bbox(big, "1:50000", "1992")) > 100


@pytest.fixture
def shapefile_path(tmp_path: Path) -> Path:
    """Two polygons 80 km apart in EPSG:2180."""
    import shapefile
    from pyproj import CRS

    path = tmp_path / "area.shp"
    with shapefile.Writer(str(path)) as writer:
        writer.field("name", "C", 20)
        for x, y in ((420000, 230000), (500000, 300000)):
            writer.poly(
                [[(x, y), (x + 1000, y), (x + 1000, y + 1000), (x, y + 1000), (x, y)]]
            )
            writer.record("area")
    path.with_suffix(".prj").write_text(CRS.from_epsg(2180).to_wkt(), encoding="utf-8")
    return path


def test_find_sheets_of_a_geometry_file(shapefile_path):
    document = find_sheets(
        geometry=str(shapefile_path), scale="1:10000", sheet_system="1992"
    )
    as_path = find_sheets(geometry=shapefile_path, scale="1:10000", sheet_system="1992")

    expected = tuple(
        find_sheets_for_geometry(shapefile_path, "1:10000", sheet_system="1992")
    )
    assert document.sheets == as_path.sheets == expected
    assert len(expected) >= 2  # scattered features: the sheets they intersect only
    assert document.request.geometry == shapefile_path
    assert (document.request.bbox, document.request.bbox_crs) == (None, None)
    assert document.request.layer is None
    encoded = document.to_dict()["request"]
    assert isinstance(encoded, dict)
    assert encoded["geometry"] == shapefile_path.absolute().as_posix()
    assert encoded["bbox"] is None


def test_find_sheets_passes_the_layer_to_the_library(monkeypatch, tmp_path):
    seen = {}

    def fake(path, scale, layer=None, *, sheet_system):
        seen.update(path=path, scale=scale, layer=layer, sheet_system=sheet_system)
        return ["N-34-130-D-d-2-4"]

    monkeypatch.setattr(sheet_info, "find_sheets_for_geometry", fake)

    document = find_sheets(
        geometry=tmp_path / "x.gpkg",
        layer="zlewnie",
        scale="1:10000",
        sheet_system="1992",
    )

    assert seen == {
        "path": tmp_path / "x.gpkg",
        "scale": "1:10000",
        "layer": "zlewnie",
        "sheet_system": "1992",
    }
    assert document.request.layer == "zlewnie"
    assert document.sheets == ("N-34-130-D-d-2-4",)


def test_find_sheets_document_keys():
    document = find_sheets(bbox=_BBOX, scale="1:100000", sheet_system="1992")

    data = document.to_dict()
    assert list(data) == ["schema", "request", "sheets", "count"]
    assert data["schema"] == "kartograf-sheets/1"
    assert list(data["request"]) == [  # type: ignore[call-overload]
        "scale",
        "sheet_system",
        "bbox",
        "bbox_crs",
        "geometry",
        "layer",
    ]
    assert data["count"] == len(data["sheets"])  # type: ignore[arg-type]
    assert json.loads(document.to_json()) == data


@pytest.mark.parametrize(
    "area",
    [{}, {"bbox": _BBOX, "geometry": "area.shp"}],
    ids=["no area", "two areas"],
)
def test_exactly_one_area_is_required(area):
    with pytest.raises(ValidationError) as error:
        find_sheets(scale="1:10000", sheet_system="1992", **area)

    assert error.value.options == ("bbox", "geometry")
    assert error.value.option is None


def test_layer_needs_a_geometry_file():
    with pytest.raises(ValidationError) as error:
        find_sheets(bbox=_BBOX, layer="x", scale="1:10000", sheet_system="1992")

    assert error.value.option == "layer"


@pytest.mark.parametrize(
    ("arguments", "option", "allowed"),
    [
        ({"sheet_system": "1965"}, "sheet_system", ("1992", "2000")),
        ({"sheet_system": None}, "sheet_system", ("1992", "2000")),
        ({"scale": "1:7"}, "scale", SCALES_1992),
        ({"scale": None}, "scale", SCALES_1992),
        ({"scale": "1:2000"}, "scale", SCALES_1992),
        (
            {"scale": "1:1000000", "sheet_system": "2000"},
            "scale",
            tuple(SCALE_HIERARCHY_2000),
        ),
    ],
)
def test_scale_and_sheet_system_are_checked_by_name(arguments, option, allowed):
    keywords = {"scale": "1:10000", "sheet_system": "1992", **arguments}

    with pytest.raises(ValidationError) as error:
        find_sheets(bbox=_BBOX, **keywords)

    assert error.value.option == option
    assert error.value.allowed == allowed


@pytest.mark.parametrize(
    "bbox",
    [
        BBox(565000, 242000, 569000, 246000, "EPSG:5514"),
        BBox(569000, 246000, 565000, 242000, "EPSG:2180"),
        BBox(565000, 242000, float("nan"), 246000, "EPSG:2180"),
    ],
    ids=["Czech CRS", "inverted", "nan"],
)
def test_a_bbox_the_library_refuses_names_the_bbox(bbox):
    with pytest.raises(ValidationError) as error:
        find_sheets(bbox=bbox, scale="1:10000", sheet_system="1992")

    assert error.value.option == "bbox"


def test_arguments_of_a_wrong_type_name_their_option_in_find_sheets():
    cases = [
        ({"bbox": (1, 2, 3, 4)}, "bbox"),
        ({"geometry": 5}, "geometry"),
        ({"geometry": "a.shp", "layer": 5}, "layer"),
    ]
    for area, option in cases:
        with pytest.raises(ValidationError) as error:
            find_sheets(scale="1:10000", sheet_system="1992", **area)  # type: ignore[arg-type]
        assert error.value.option == option


def test_an_unsupported_geometry_file_names_the_geometry(tmp_path):
    with pytest.raises(ValidationError) as error:
        find_sheets(
            geometry=tmp_path / "area.txt", scale="1:10000", sheet_system="1992"
        )

    assert error.value.option == "geometry"
    assert "Nieobslugiwany format geometrii" in str(error.value)


def test_missing_keyword_arguments_are_a_type_error():
    with pytest.raises(TypeError):
        find_sheets(bbox=_BBOX, sheet_system="1992")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        find_sheets(bbox=_BBOX, scale="1:10000")  # type: ignore[call-arg]
