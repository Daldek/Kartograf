"""The exact keys of every JSON document, in order (spec 12.2, rule A3).

``CONTRACT`` copies the key tables of the spec: within ``/1`` only additions are
allowed, so a removed, renamed or reordered key is a failing test here and a
deliberate, reviewed edit of this table. ``NESTED`` does the same for the types
that documents contain. Documents are built from fixtures in this file, without
a network.
"""

import importlib
import pkgutil
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import pytest

import kartograf
from kartograf.core.bbox import BBox
from kartograf.download.availability import (
    AvailabilityArea,
    AvailabilityCombination,
    AvailabilityReport,
)
from kartograf.download.collections import CollectionReport
from kartograf.download.data import DataReport, UnitFailure, UnitFile
from kartograf.download.fetch import VersionedFile
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.error_report import error_report
from kartograf.exceptions import ValidationError
from kartograf.hydrology.hsg import HsgReport
from kartograf.landcover.manager import LandCoverReport, SoilReport
from kartograf.notices import Notice
from kartograf.project.model import (
    FileCheck,
    PinnedFile,
    Project,
    ProjectCheck,
    ProjectReport,
    ProjectTask,
    TaskResult,
)
from kartograf.providers.pl.gugik_laz import LazTile, SupersededLazTile
from kartograf.serialization import SCHEMAS, Document, EncodeContext, encode

STORE = Path("/srv/dane/kartograf")
SHA256 = "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6"
SHEET = "N-34-130-D-d-2-4"
SEGMENT = "nmt/pl_1992_1m_evrf2007"


# --- fixtures: one value of every type, no field left empty ---------------------


def _notice() -> Notice:
    return Notice("info", "sheet_list", f"Znaleziono arkuszy wg godla: 1 dla {SHEET}")


def _versioned_file() -> VersionedFile:
    return VersionedFile(
        path=STORE / SEGMENT / "N-34/130/D/d/2/4" / f"{SHEET}.asc",
        status="new",
        label="2022-05-10_83233",
        sha256=SHA256,
        version_path=STORE / SEGMENT / "versions" / f"{SHEET}.asc",
    )


def _unit_file() -> UnitFile:
    return UnitFile(SHEET, "PL", _versioned_file())


def _unit_failure() -> UnitFailure:
    return UnitFailure("N-34-130-D", "PL", "HTTP 500", "download")


def _plan_item() -> PlanItem:
    return PlanItem(
        track="pl_sheet",
        segment=SEGMENT,
        hierarchy="N-34/130/D/d/2/4",
        name=f"{SHEET}.asc",
        unit=SHEET,
        local_label="2022-05-10_83233",
        local_sha256=SHA256,
        available_label="2025-04-02_99887",
        available_signal={"url": "https://example.test/a.asc", "date": "2025-04-02"},
        status="newer",
    )


def _laz_tile() -> LazTile:
    return LazTile(
        sheet="N-34-139-C-a-3-1",
        url="https://example.test/N-34-139-C-a-3-1.laz",
        year=2022,
        density=12,
        crs="PL-1992",
        min_x=500000.0,
        min_y=250000.0,
        max_x=501000.0,
        max_y=251000.0,
        footprint=((500000.0, 250000.0), (501000.0, 250000.0), (501000.0, 251000.0)),
        date="2022-05-10",
        full_sheet=True,
    )


def _superseded() -> SupersededLazTile:
    return SupersededLazTile(_laz_tile(), (_laz_tile(),))


def _area() -> AvailabilityArea:
    return AvailabilityArea(
        "PL", "EPSG:2180", (500000.0, 250000.0, 501000.0, 251000.0), 1.0e6, 9.0e5
    )


def _combination() -> AvailabilityCombination:
    return AvailabilityCombination(
        country="PL",
        product="nmt",
        source="pl.gugik.nmt_1m",
        year=2022,
        acquisition_dates=("2022-05-10", "2022-06-01"),
        published=("2022-09-01", "2022-09-02"),
        campaigns=("83233",),
        horizontal="PL-1992",
        resolution="1m",
        vertical_crs="EVRF2007",
        format="ASC",
        densities=(12,),
        complete=True,
        sheets_full=(SHEET,),
        sheets_partial=(),
        sheets_missing=(),
        uncovered=False,
        uncovered_m2=0.0,
        size_bytes=None,
        download_hint=("elevation download --product nmt --sheet " + SHEET,),
    )


def _pin() -> PinnedFile:
    return PinnedFile(
        "output",
        SHEET,
        f"{SEGMENT}/N-34/130/D/d/2/4/{SHEET}.asc",
        f"{SEGMENT}/versions/N-34/130/D/d/2/4/2022-05-10_83233_10be475e/{SHEET}.asc",
        "2022-05-10_83233",
        SHA256,
        41029733,
    )


def _file_check() -> FileCheck:
    return FileCheck(
        "teren", SHEET, f"{SEGMENT}/N-34/130/D/d/2/4/{SHEET}.asc", "newer",
        "2022-05-10_83233", "2025-04-02_99887", "nowsza wersja",
    )  # fmt: skip


def _task() -> ProjectTask:
    return ProjectTask(
        name="teren",
        command="elevation download",
        options=MappingProxyType({"product": "nmt", "sheet": SHEET}),
        pinned_at="2026-10-20T08:15:02+00:00",
        kartograf_version="0.8.0",
        geometry_sha256=MappingProxyType({"area.shp": SHA256}),
        files=(_pin(),),
    )


def _task_result() -> TaskResult:
    return TaskResult("teren", "updated", (_pin(),), (_pin(),), ("blad",))


def _project() -> Project:
    return Project(Path("/home/ola/projekty/wisla"), STORE, (_task(),))


# --- documents ------------------------------------------------------------------


def _error_document() -> Document:
    exc = ValidationError("zly argument", option="product", allowed=("nmt", "nmpt"))
    return error_report(exc, command="elevation download")


def _plan() -> Document:
    return UpdatePlan(
        store=STORE.as_posix(),
        checked_at="2026-10-18T10:15:02+00:00",
        kartograf_version="0.8.0",
        items=(_plan_item(),),
        notices=(_notice(),),
    )


def _availability() -> Document:
    return AvailabilityReport(
        request={
            "product": "nmt",
            "country": "pl",
            "sheet": SHEET,
            "min_year": None,
            "max_year": None,
        },
        checked_at="2026-10-18T10:15:02+00:00",
        areas=(_area(),),
        combinations=(_combination(),),
        notices=(_notice(),),
        ok=True,
    )


def _data_report() -> Document:
    return DataReport(
        files=(_unit_file(),),
        failed=(_unit_failure(),),
        stale=(_plan_item(),),
        superseded=(_superseded(),),
        notices=(_notice(),),
        ok=False,
    )


def _collection_report() -> Document:
    return CollectionReport(
        files=(_unit_file(),),
        failed=(_unit_failure(),),
        stale=(_plan_item(),),
        notices=(_notice(),),
        ok=False,
    )


def _landcover_report() -> Document:
    return LandCoverReport(
        files=(_unit_file(),),
        raw=(_unit_file(),),
        failed=(_unit_failure(),),
        stale=(_plan_item(),),
        notices=(_notice(),),
        ok=False,
    )


def _soil_report() -> Document:
    return SoilReport(
        files=(_unit_file(),),
        failed=(_unit_failure(),),
        stale=(_plan_item(),),
        notices=(_notice(),),
        ok=False,
    )


def _hsg_report() -> Document:
    return HsgReport(
        files=(_unit_file(),),
        inputs=(_unit_file(),),
        failed=(_unit_failure(),),
        stale=(_plan_item(),),
        notices=(_notice(),),
        ok=False,
        summary={"A": {"count": 1}},
    )


def _project_report() -> Document:
    return ProjectReport(
        project=_project(),
        tasks=(_task_result(),),
        notices=(_notice(),),
        ok=False,
    )


def _project_check() -> Document:
    return ProjectCheck(
        project=_project(),
        files=(_file_check(),),
        not_downloaded=("gleby",),
        notices=(_notice(),),
        ok=False,
    )


# schema -> a document of every class of that schema, built without a network
DOCUMENTS: dict[str, tuple[Callable[[], Document], ...]] = {
    "kartograf-error/1": (_error_document,),
    "kartograf-plan/1": (_plan,),
    "kartograf-availability/1": (_availability,),
    "kartograf-download/1": (
        _data_report,
        _collection_report,
        _landcover_report,
        _soil_report,
        _hsg_report,
    ),
    "kartograf-project-state/1": (_project,),
    "kartograf-project-report/1": (_project_report,),
    "kartograf-project-check/1": (_project_check,),
}

# schema -> the keys of the document in order (``schema`` first)
CONTRACT: dict[str, list[str]] = {
    "kartograf-error/1": [
        "schema",
        "code",
        "message",
        "hint",
        "exception",
        "exit_code",
        "command",
        "details",
    ],
    "kartograf-plan/1": [
        "schema",
        "store",
        "checked_at",
        "kartograf_version",
        "items",
        "notices",
        "ok",
    ],
    "kartograf-availability/1": [
        "schema",
        "request",
        "checked_at",
        "areas",
        "combinations",
        "notices",
        "ok",
    ],
    "kartograf-download/1": [
        "schema",
        "files",
        "raw",
        "inputs",
        "failed",
        "stale",
        "superseded",
        "summary",
        "notices",
        "ok",
    ],
    "kartograf-project-state/1": ["schema", "directory", "output_dir", "tasks"],
    "kartograf-project-report/1": ["schema", "project", "tasks", "notices", "ok"],
    "kartograf-project-check/1": [
        "schema",
        "project",
        "files",
        "not_downloaded",
        "notices",
        "ok",
    ],
}

# type name -> (a value, the keys of its object in order); spec 5.3 and 5.4
NESTED: dict[str, tuple[Callable[[], object], list[str]]] = {
    "Notice": (_notice, ["level", "code", "text"]),
    "VersionedFile": (
        _versioned_file,
        [
            "path",
            "status",
            "label",
            "sha256",
            "version_path",
            "newer",
            "unverified",
            "same_as",
        ],
    ),
    "UnitFile": (_unit_file, ["unit", "country", "file"]),
    "UnitFailure": (_unit_failure, ["unit", "country", "error", "kind"]),
    "PlanItem": (
        _plan_item,
        [
            "track",
            "segment",
            "hierarchy",
            "name",
            "unit",
            "local_label",
            "local_sha256",
            "available_label",
            "available_signal",
            "status",
            "error",
        ],
    ),
    "LazTile": (
        _laz_tile,
        [
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
        ],
    ),
    "SupersededLazTile": (_superseded, ["tile", "covered_by"]),
    "AvailabilityArea": (
        _area,
        ["country", "crs", "bounds", "area_m2", "land_m2"],
    ),
    "AvailabilityCombination": (
        _combination,
        [
            "country",
            "product",
            "source",
            "year",
            "acquisition_dates",
            "published",
            "campaigns",
            "horizontal",
            "resolution",
            "vertical_crs",
            "format",
            "densities",
            "complete",
            "sheets_full",
            "sheets_partial",
            "sheets_missing",
            "uncovered",
            "uncovered_m2",
            "size_bytes",
            "download_hint",
        ],
    ),
    "BBoxValue": (lambda: BBox(1, 2, 3, 4, "EPSG:2180"), ["bbox", "crs"]),
    "PinnedFile": (
        _pin,
        ["role", "unit", "path", "version", "label", "sha256", "size_bytes"],
    ),
    "FileCheck": (
        _file_check,
        [
            "task",
            "unit",
            "path",
            "status",
            "pinned_label",
            "available_label",
            "detail",
        ],
    ),
    "ProjectTask": (
        _task,
        [
            "name",
            "command",
            "options",
            "pinned_at",
            "kartograf_version",
            "geometry_sha256",
            "files",
        ],
    ),
    "TaskResult": (
        _task_result,
        ["name", "outcome", "pinned", "unpinned", "errors"],
    ),
}

_CASES = [
    pytest.param(schema, build, id=f"{schema}:{build.__name__.strip('_')}")
    for schema, builders in DOCUMENTS.items()
    for build in builders
]


def test_every_contract_row_has_a_fixture_and_the_other_way_round():
    assert sorted(DOCUMENTS) == sorted(CONTRACT)


@pytest.mark.parametrize(("schema", "build"), _CASES)
def test_document_keys_and_their_order(schema, build):
    """Every class of a schema gives the same keys: a consumer reads the five
    reports of ``kartograf-download/1`` with one schema."""
    document = build()

    data = document.to_dict()

    assert document.schema == schema
    assert list(data) == CONTRACT[schema]
    assert data["schema"] == schema


@pytest.mark.parametrize("name", sorted(NESTED))
def test_nested_type_keys_and_their_order(name):
    build, keys = NESTED[name]

    encoded = encode(build(), EncodeContext(store=STORE))

    assert isinstance(encoded, dict)
    assert list(encoded) == keys


def test_nested_documents_have_no_schema_key():
    """``project`` of a report is the document of the project without the key
    ``schema`` (it is only the first key of the top level)."""
    data = _project_report().to_dict()

    assert list(data["project"]) == ["directory", "output_dir", "tasks"]  # type: ignore[call-overload]


def _document_classes() -> list[type[Document]]:
    """Every ``Document`` class defined anywhere in the package."""
    for info in pkgutil.walk_packages(kartograf.__path__, "kartograf."):
        if not info.name.endswith(".__main__"):
            importlib.import_module(info.name)
    found: set[type[Document]] = set()
    pending: list[type[Document]] = [Document]
    while pending:
        for subclass in pending.pop().__subclasses__():
            # the tests define Documents of their own (``test_serialization``)
            if subclass.__module__.startswith("kartograf.") and subclass not in found:
                found.add(subclass)
                pending.append(subclass)
    return sorted(found, key=lambda cls: (cls.SCHEMA, cls.__name__))


DOCUMENT_CLASSES = _document_classes()


@pytest.mark.parametrize("cls", DOCUMENT_CLASSES, ids=lambda cls: cls.__name__)
def test_every_document_class_is_registered(cls):
    """A result type that is a ``Document`` is in ``SCHEMAS`` under its schema:
    the catalog and the MCP tools find the documents there."""
    assert cls in SCHEMAS[cls.SCHEMA]


def test_every_contract_schema_is_registered_by_the_package():
    assert set(CONTRACT) <= {cls.SCHEMA for cls in DOCUMENT_CLASSES}
