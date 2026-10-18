"""The JSON encoder and the ``Document`` mixin (``kartograf.serialization``)."""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest

import kartograf
from kartograf.core.bbox import BBox
from kartograf.download.collections import CollectionReport
from kartograf.download.data import (
    DOWNLOAD_KEYS,
    DataReport,
    UnitFailure,
    UnitFile,
)
from kartograf.download.fetch import VersionedFile
from kartograf.hydrology.hsg import HsgReport
from kartograf.landcover.manager import LandCoverReport, SoilReport
from kartograf.notices import Notice
from kartograf.providers.pl.gugik_laz import LazTile, SupersededLazTile
from kartograf.serialization import SCHEMAS, Document, EncodeContext, encode


@dataclass(frozen=True)
class Item:
    name: str
    size: int


@dataclass(frozen=True)
class Widget(Document):
    SCHEMA = "kartograf-test-widget/1"
    JSON_KEYS = ("name", "items", "count", "extra")
    JSON_FILL = {"extra": None}

    name: str
    items: tuple[Item, ...]

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class Pin:
    """A nested value that needs the store directory (like ``PinnedFile``)."""

    rel: str

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        if ctx.store is None:
            raise ValueError("a pin is encoded only inside a project document")
        return {"path": ctx.store / self.rel}


@dataclass(frozen=True)
class Holder(Document):
    SCHEMA = "kartograf-test-holder/1"

    store_dir: Path
    pins: tuple[Pin, ...]

    def prepare_context(self, ctx: EncodeContext) -> None:
        ctx.store = self.store_dir


class Color(Enum):
    RED = "red"
    SIZE = 3


@pytest.fixture
def isolated_schemas():
    """Classes defined by a test must not stay in the process-wide registry."""
    saved = dict(SCHEMAS)
    yield
    SCHEMAS.clear()
    SCHEMAS.update(saved)


def test_scalars_and_finite_floats():
    assert encode(None) is None
    assert encode(True) is True
    assert encode(7) == 7
    assert encode("zażółć") == "zażółć"
    assert encode(1.5) == 1.5
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="JSON number"):
            encode(bad)


def test_path_is_absolute_posix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")

    relative = encode(Path("data") / "a.asc")
    through_link = encode(tmp_path / "link" / "a.asc")

    assert relative == f"{Path.cwd().as_posix()}/data/a.asc"
    # a symlink is not resolved: the encoder does not touch the file system
    assert through_link == f"{tmp_path.as_posix()}/link/a.asc"


def test_sequences_and_sets_sorted():
    assert encode((1, 2)) == [1, 2]
    assert encode([Path("/a"), "b"]) == ["/a", "b"]
    assert encode(frozenset({"b", "a"})) == ["a", "b"]
    assert encode({3, 1, 2}) == [1, 2, 3]
    with pytest.raises(TypeError, match="orderable"):
        encode({1, "a"})


def test_mapping_keys_must_be_str():
    assert encode({"b": (1,), "a": Path("/x")}) == {"b": [1], "a": "/x"}
    assert list(encode({"b": 1, "a": 2})) == ["b", "a"]  # insertion order
    with pytest.raises(TypeError, match="keys"):
        encode({1: "a"})


def test_decimal_is_string_and_datetime_is_utc_seconds():
    assert encode(Decimal("0.5")) == "0.5"
    with pytest.raises(ValueError, match="JSON number"):
        encode(Decimal("NaN"))
    aware = datetime(
        2026, 10, 18, 12, 30, 5, 987654, tzinfo=timezone(timedelta(hours=2))
    )
    assert encode(aware) == "2026-10-18T10:30:05+00:00"
    with pytest.raises(ValueError, match="time zone"):
        encode(datetime(2026, 10, 18, 12, 30, 5))


def test_bbox_hook():
    assert encode(BBox(1, 2, 3, 4, "EPSG:2180")) == {
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "crs": "EPSG:2180",
    }
    nested = encode({"area": BBox(0.5, 0.25, 10, 20, "EPSG:4326")})
    assert nested == {"area": {"bbox": [0.5, 0.25, 10.0, 20.0], "crs": "EPSG:4326"}}


def test_enum_value():
    assert encode(Color.RED) == "red"
    assert encode([Color.SIZE]) == [3]


def test_unknown_type_is_type_error():
    for value in (object(), b"bytes", Item):
        with pytest.raises(TypeError):
            encode(value)


def test_dataclass_order_and_json_false():
    @dataclass(frozen=True)
    class Record:
        second: str
        first: int
        hidden: str = field(default="x", metadata={"json": False})

    assert list(encode(Record("a", 1))) == ["second", "first"]  # not alphabetical
    assert encode(Record("a", 1)) == {"second": "a", "first": 1}


def test_omit_pairs_skip_one_class_field():
    @dataclass(frozen=True)
    class Inner:
        value: int
        raw: dict[str, object]

    @dataclass(frozen=True)
    class Outer:
        raw: str
        inner: Inner

    value = Outer("keep", Inner(1, {"a": 1}))

    omitted = encode(value, EncodeContext(omit=frozenset({("Inner", "raw")})))

    assert omitted == {"raw": "keep", "inner": {"value": 1}}
    assert encode(value) == {"raw": "keep", "inner": {"value": 1, "raw": {"a": 1}}}


def test_unhashable_frozen_dataclass_encodes():
    @dataclass(frozen=True)
    class Loose:
        data: dict[str, int]
        __hash__ = None  # type: ignore[assignment]

    loose = Loose({"a": 1})
    with pytest.raises(TypeError):
        hash(loose)

    assert encode(loose) == {"data": {"a": 1}}
    assert encode((loose, loose)) == [{"data": {"a": 1}}, {"data": {"a": 1}}]


def test_document_key_resolution():
    doc = Widget("w", (Item("a", 1), Item("b", 2)))

    data = doc.to_dict()

    # field -> property -> JSON_FILL, in the order of JSON_KEYS
    assert data == {
        "schema": "kartograf-test-widget/1",
        "name": "w",
        "items": [{"name": "a", "size": 1}, {"name": "b", "size": 2}],
        "count": 2,
        "extra": None,
    }
    assert list(data) == ["schema", "name", "items", "count", "extra"]


def test_document_key_without_a_source_is_value_error(isolated_schemas):
    @dataclass(frozen=True)
    class Broken(Document):
        SCHEMA = "kartograf-test-broken/1"
        JSON_KEYS = ("name", "nowhere")

        name: str

    with pytest.raises(ValueError, match="nowhere"):
        Broken("x").to_dict()


def test_document_without_json_keys_uses_the_fields(isolated_schemas):
    @dataclass(frozen=True)
    class Plain(Document):
        SCHEMA = "kartograf-test-plain/1"

        zeta: int
        alpha: str
        hidden: str = field(default="x", metadata={"json": False})

    assert list(Plain(1, "a").to_dict()) == ["schema", "zeta", "alpha"]


def test_schema_is_first_key_and_nested_has_none(isolated_schemas):
    @dataclass(frozen=True)
    class Parent(Document):
        SCHEMA = "kartograf-test-parent/1"

        child: Widget
        children: tuple[Widget, ...]

    child = Widget("c", ())

    data = Parent(child, (child,)).to_dict()

    assert next(iter(data)) == "schema"
    assert data["schema"] == "kartograf-test-parent/1"
    nested = data["child"]
    assert isinstance(nested, dict) and "schema" not in nested
    assert nested["name"] == "c" and nested["count"] == 0
    assert data["children"] == [nested]
    assert child.schema == "kartograf-test-widget/1"


def test_json_hook_sees_context_from_prepare_context(tmp_path):
    holder = Holder(tmp_path / "store", (Pin("a.asc"), Pin("b/c.asc")))

    data = holder.to_dict()

    store = (tmp_path / "store").as_posix()
    assert data["pins"] == [{"path": f"{store}/a.asc"}, {"path": f"{store}/b/c.asc"}]
    with pytest.raises(ValueError, match="project document"):
        encode(Pin("a.asc"))


def test_context_set_by_a_nested_document_stays_in_its_subtree(
    tmp_path, isolated_schemas
):
    @dataclass(frozen=True)
    class Outer(Document):
        SCHEMA = "kartograf-test-outer/1"

        inner: Holder
        pin: Pin

    outer = Outer(Holder(tmp_path, (Pin("a"),)), Pin("b"))

    with pytest.raises(ValueError, match="project document"):
        outer.to_dict()  # the sibling pin is outside the nested holder


def test_to_json_format():
    doc = Widget("zażółć", (Item("a", 1),))

    text = doc.to_json()
    compact = doc.to_json(indent=None)

    assert text.endswith("}\n")
    assert "zażółć" in text  # ensure_ascii=False
    assert text == json.dumps(doc.to_dict(), ensure_ascii=False, indent=2) + "\n"
    assert text.splitlines()[1] == '  "schema": "kartograf-test-widget/1",'
    assert compact == json.dumps(
        doc.to_dict(), ensure_ascii=False, separators=(",", ":")
    )
    assert not compact.endswith("\n")
    assert json.loads(compact) == json.loads(text)


def test_to_json_never_writes_nan(isolated_schemas):
    @dataclass(frozen=True)
    class Measured(Document):
        SCHEMA = "kartograf-test-measured/1"

        value: float

    with pytest.raises(ValueError, match="JSON number"):
        Measured(float("nan")).to_json()


def test_to_json_is_byte_stable():
    doc = Widget("w", (Item("a", 1), Item("b", 2)))

    assert doc.to_json() == doc.to_json()
    assert Widget("w", (Item("a", 1), Item("b", 2))).to_json() == doc.to_json()


def test_schemas_registry(isolated_schemas):
    @dataclass(frozen=True)
    class First(Document):
        SCHEMA = "kartograf-test-pair/1"

        x: int

    @dataclass(frozen=True)
    class Second(Document):
        SCHEMA = "kartograf-test-pair/1"

        x: int

    assert SCHEMAS["kartograf-test-pair/1"] == (First, Second)
    assert SCHEMAS["kartograf-test-widget/1"] == (Widget,)


@pytest.mark.parametrize(
    "name",
    [
        "bad",
        "kartograf-/1",
        "kartograf-x/0",
        "kartograf-x/01",
        "kartograf-X/1",
        "kartograf-x/1\n",
        "other-x/1",
    ],
)
def test_schema_name_must_match_the_pattern(name, isolated_schemas):
    with pytest.raises(ValueError, match="SCHEMA"):
        type("Bad", (Document,), {"SCHEMA": name})
    assert name not in SCHEMAS


def test_schema_field_is_rejected(isolated_schemas):
    with pytest.raises(ValueError, match="'schema'"):

        class Clash(Document):
            SCHEMA = "kartograf-test-clash/1"
            schema: str = "x"

    assert "kartograf-test-clash/1" not in SCHEMAS


def test_json_keys_must_not_list_schema(isolated_schemas):
    with pytest.raises(ValueError, match="JSON_KEYS"):
        type(
            "Bad",
            (Document,),
            {"SCHEMA": "kartograf-test-bad-keys/1", "JSON_KEYS": ("schema",)},
        )


def test_serializer_imports_nothing_from_the_package():
    """Result types import the serializer, never the other way round: with
    an empty stand-in for ``kartograf`` only the module itself gets loaded."""
    code = (
        "import json, sys, types\n"
        "package = types.ModuleType('kartograf')\n"
        "package.__path__ = [sys.argv[1]]\n"
        "sys.modules['kartograf'] = package\n"
        "import kartograf.serialization\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('kartograf'))\n"
        "print(json.dumps(loaded))\n"
    )
    package_dir = Path(kartograf.__file__).resolve().parent

    done = subprocess.run(
        [sys.executable, "-c", code, str(package_dir)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )

    assert json.loads(done.stdout) == ["kartograf", "kartograf.serialization"]


# --- the five command reports share kartograf-download/1 (spec 5.4.1) ----------

_DOWNLOAD_REPORTS = {
    "DataReport": lambda: DataReport(
        files=(), failed=(), stale=(), superseded=(), notices=(), ok=True
    ),
    "CollectionReport": lambda: CollectionReport(
        files=(), failed=(), stale=(), notices=(), ok=True
    ),
    "LandCoverReport": lambda: LandCoverReport(
        files=(), raw=(), failed=(), stale=(), notices=(), ok=True
    ),
    "SoilReport": lambda: SoilReport(
        files=(), failed=(), stale=(), notices=(), ok=True
    ),
    "HsgReport": lambda: HsgReport(
        files=(), inputs=(), failed=(), stale=(), notices=(), ok=True
    ),
}


@pytest.mark.parametrize("name", list(_DOWNLOAD_REPORTS))
def test_download_family_has_one_key_set(name):
    """A consumer reads the five reports with one schema: the same keys in the
    same order, a key the class has no field for is ``[]`` (``summary``: null)."""
    report = _DOWNLOAD_REPORTS[name]()

    data = report.to_dict()

    assert list(data) == ["schema", *DOWNLOAD_KEYS]
    assert data["schema"] == "kartograf-download/1" == report.schema
    assert data["summary"] is None and data["ok"] is True
    for key in ("files", "raw", "inputs", "failed", "stale", "superseded", "notices"):
        assert data[key] == []


def test_download_family_is_registered_under_one_schema():
    registered = {cls.__name__ for cls in SCHEMAS["kartograf-download/1"]}
    assert registered == set(_DOWNLOAD_REPORTS)


_SPEC_SHA256 = "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6"


def _spec_file() -> VersionedFile:
    store = Path("/data/kartograf/nmt/pl_1992_1m_evrf2007")
    version = "2022-05-10_83233_10be475e"
    name = "N-34-130-D-d-2-4.asc"
    return VersionedFile(
        path=store / "N-34/130/D/d/2/4" / name,
        status="new",
        label="2022-05-10_83233",
        sha256=_SPEC_SHA256,
        version_path=store / "versions/N-34/130/D/d/2/4" / version / name,
    )


def test_download_report_equals_the_spec_example():
    """The example of spec 5.4.1: absolute paths, a ``Notice`` as an object."""
    sheet_list = Notice(
        "info",
        "sheet_list",
        "Znaleziono arkuszy wg godla: 1 dla N-34-130-D-d-2-4 (NMT 1 m)\n"
        "  Arkusze: N-34-130-D-d-2-4",
    )
    report = DataReport(
        files=(UnitFile("N-34-130-D-d-2-4", "PL", _spec_file()),),
        failed=(),
        stale=(),
        superseded=(),
        notices=(sheet_list,),
        ok=True,
    )

    assert report.to_dict() == {
        "schema": "kartograf-download/1",
        "files": [
            {
                "unit": "N-34-130-D-d-2-4",
                "country": "PL",
                "file": {
                    "path": "/data/kartograf/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/"
                    "N-34-130-D-d-2-4.asc",
                    "status": "new",
                    "label": "2022-05-10_83233",
                    "sha256": _SPEC_SHA256,
                    "version_path": "/data/kartograf/nmt/pl_1992_1m_evrf2007/versions/"
                    "N-34/130/D/d/2/4/2022-05-10_83233_10be475e/N-34-130-D-d-2-4.asc",
                    "newer": None,
                    "unverified": None,
                    "same_as": None,
                },
            }
        ],
        "raw": [],
        "inputs": [],
        "failed": [],
        "stale": [],
        "superseded": [],
        "summary": None,
        "notices": [{"level": "info", "code": "sheet_list", "text": sheet_list.text}],
        "ok": True,
    }


def _tile(sheet: str, **fields) -> LazTile:
    values: dict[str, object] = {
        "sheet": sheet,
        "url": f"https://example.test/{sheet}.laz",
        "year": 2022,
        "density": 12,
        "crs": "PL-1992",
        "min_x": 500000.0,
        "min_y": 250000.0,
        "max_x": 501000.0,
        "max_y": 251000.0,
        "footprint": ((500000.0, 250000.0), (501000.0, 250000.0), (501000.0, 251000.0)),
        "date": "2022-05-10",
        "full_sheet": True,
    }
    return LazTile(**{**values, **fields})  # type: ignore[arg-type]


def test_superseded_encodes_tile_and_covered_by():
    older = _tile("N-34-139-C-a-3-1", year=2018, full_sheet=None)
    newer = _tile("N-34-139-C-a-3-1-n")
    # a covering tile the WFS gave no geometry for: its extent is NaN in memory
    # and ``null`` in the document (NaN is no JSON value)
    unknown = _tile(
        "N-34-139-C-a-3-2", min_x=float("nan"), min_y=float("nan"),
        max_x=float("nan"), max_y=float("nan"), footprint=None, date=None,
    )  # fmt: skip
    report = DataReport(
        files=(),
        failed=(),
        stale=(),
        superseded=(
            SupersededLazTile(older, (newer, unknown)),
            SupersededLazTile(_tile("N-34-139-C-b-1-1"), ()),
        ),
        notices=(),
        ok=True,
    )

    data = report.to_dict()

    first, second = data["superseded"]
    assert list(first) == ["tile", "covered_by"]
    assert list(first["tile"]) == [
        "sheet",
        "url",
        "year",
        "density",
        "crs",
        "min_x",
        "min_y",
        "max_x",
        "max_y",
        "footprint",
        "date",
        "full_sheet",
    ]
    assert first["tile"]["year"] == 2018 and first["tile"]["full_sheet"] is None
    assert first["tile"]["footprint"] == [
        [500000.0, 250000.0],
        [501000.0, 250000.0],
        [501000.0, 251000.0],
    ]
    covering, no_geometry = first["covered_by"]
    assert covering["sheet"] == "N-34-139-C-a-3-1-n"
    assert [no_geometry[k] for k in ("min_x", "min_y", "max_x", "max_y")] == [None] * 4
    assert no_geometry["footprint"] is None and no_geometry["date"] is None
    assert second["covered_by"] == []
    json.dumps(data, allow_nan=False)  # the whole document is plain JSON


def test_unit_failure_and_unit_file_keys():
    failure = UnitFailure("1465", "PL", "HTTP 500", "download")
    unit_file = UnitFile("1465", "PL", _spec_file())

    assert encode(failure) == {
        "unit": "1465",
        "country": "PL",
        "error": "HTTP 500",
        "kind": "download",
    }
    assert list(encode(unit_file)) == ["unit", "country", "file"]
    assert list(encode(unit_file.file)) == [  # type: ignore[call-overload]
        "path",
        "status",
        "label",
        "sha256",
        "version_path",
        "newer",
        "unverified",
        "same_as",
    ]
