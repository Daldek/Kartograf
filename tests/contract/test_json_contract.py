"""The exact keys of every JSON document, in order (spec 12.2, rule A3).

``CONTRACT`` copies the key tables of the spec: within ``/1`` only additions are
allowed, so a removed, renamed or reordered key is a failing test here and a
deliberate, reviewed edit of this table. ``NESTED`` does the same for the types
that documents contain. Documents are built from fixtures in this file, without
a network.
"""

import importlib
import json
import pkgutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import pytest

import kartograf
from kartograf.cache_info import CacheEntries, CacheInfo
from kartograf.catalog import get_catalog
from kartograf.core.bbox import BBox
from kartograf.download.availability import (
    AvailabilityArea,
    AvailabilityCampaign,
    AvailabilityCombination,
    AvailabilityRecord,
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
from kartograf.sheet_info import (
    SheetDescendants,
    SheetLevel,
    SheetList,
    SheetRequest,
    describe_sheet,
)
from kartograf.source_info import (
    LayerInfo,
    LayerList,
    SourceInfo,
    SourceLicense,
    SourceList,
    YearInfo,
)
from kartograf.store import Sidecar, StoreEntry, describe_segment
from kartograf.store_documents import StoreEntries, StoreOverview, StoreSidecar

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
        full_m2=9.0e5,
        sheet_records=(_record(),),
        campaign_coverage=(_campaign(),),
    )


def _record() -> AvailabilityRecord:
    return AvailabilityRecord(
        sheet=SHEET,
        campaign="83233",
        acquisition_date="2022-05-10",
        published="2022-09-01",
        full_sheet=True,
        url=f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83233/{SHEET}.asc",
    )


def _campaign() -> AvailabilityCampaign:
    return AvailabilityCampaign(campaign="83233", complete=True, full_m2=9.0e5)


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


def _license() -> SourceLicense:
    return SourceLicense("pl-gugik", "Dane GUGiK", "https://example.org/licencja")


def _source() -> SourceInfo:
    return SourceInfo(
        key="pl.gugik.nmt_1m",
        name="Numeryczny Model Terenu 1 m",
        country="PL",
        provider="GUGiK",
        product="nmt",
        directory="nmt/<uklad>_1m_<uklad-wys>",
        select={
            "product": "nmt",
            "country": "pl",
            "vertical_crs": ("EVRF2007", "KRON86"),
        },
        license=_license(),
        auth="none",
        update_signals=("index", "none"),
    )


def _sources() -> Document:
    return SourceList("elevation", ("nmt", "nmpt"), (_source(),))


def _layer() -> LayerInfo:
    return LayerInfo("BUBD", "Budynki")


def _year() -> YearInfo:
    return YearInfo(2018, "clms", "CORINE Land Cover 2018")


def _layers() -> Document:
    return LayerList(
        group="landcover",
        product="corine",
        source="global.copernicus.corine",
        layers=(_layer(),),
        classes={"2021": ("BUBD",)},
        years=(_year(),),
        properties=(_layer(),),
        depths=("0-5cm",),
        statistics=(_layer(),),
    )


def _cache_entries() -> CacheEntries:
    return CacheEntries(1, 2, 3, 4, 5, 6)


def _cache() -> Document:
    return CacheInfo(
        "clear",
        Path("/srv/praca/.kartograf_cache.db"),
        True,
        4096,
        _cache_entries(),
        True,
        False,
    )


def _sidecar() -> Sidecar:
    raw = {"schema": "kartograf-meta/1", "dataset": "pl.gugik.nmt_1m", "sha256": SHA256}
    return Sidecar(
        schema="kartograf-meta/1",
        dataset="pl.gugik.nmt_1m",
        dataset_key="pl.gugik.nmt_1m",
        country="PL",
        product="nmt",
        provider="GUGiK",
        horizontal_crs="EPSG:2180",
        vertical_crs="EVRF2007",
        vertical_source="geoid",
        resolution="1 m",
        nodata=-9999.0,
        request={"sheet": SHEET},
        license={"id": "pl-gugik"},
        downloaded_at="2026-10-18T10:20:30+00:00",
        kartograf_version="0.8.0",
        transform={"pipeline": "x"},
        extra={"version": {"label": "2022"}},
        sha256=SHA256,
        size_bytes=48,
        data_year=2022,
        data_date="2022-05-10",
        campaign={"year": 2022},
        survey_work_id="P.1234",
        edition="2022",
        full_sheet=False,
        coverage=1.0,
        unit=SHEET,
        raw=raw,
    )


def _store_entry() -> StoreEntry:
    path = STORE / SEGMENT / "N-34/130/D/d/2/4" / f"{SHEET}.asc"
    return StoreEntry(
        kind="link",
        segment=SEGMENT,
        hierarchy="N-34/130/D/d/2/4",
        name=f"{SHEET}.asc",
        path=path,
        version_path=STORE / SEGMENT / "versions" / f"{SHEET}.asc",
        label="2022",
        sha8=SHA256[:8],
        sidecar=_sidecar(),
        problem=None,
    )


def _store_overview() -> Document:
    return StoreOverview(STORE, (describe_segment(SEGMENT),))


def _store_entries() -> Document:
    return StoreEntries(STORE, SEGMENT, (SHEET,), 10, False, (_store_entry(),))


def _store_sidecar() -> Document:
    return StoreSidecar(STORE / SEGMENT / f"{SHEET}.asc", _sidecar())


def _sheet_info() -> Document:
    # a PL-2000 code: the zone is set; every optional block is asked for
    return describe_sheet(
        "6.179.12.20", hierarchy=True, children=True, descendants="1:500"
    )


def _sheet_level() -> SheetLevel:
    return SheetLevel(SHEET, "1:10000")


def _sheet_descendants() -> SheetDescendants:
    return SheetDescendants("1:5000", 1, (f"{SHEET}-1",))


def _sheet_request() -> SheetRequest:
    # a request has a bbox or a geometry file; both are set to see every key
    return SheetRequest(
        "1:10000",
        "1992",
        (1.0, 2.0, 3.0, 4.0),
        "EPSG:2180",
        Path("/srv/praca/obszar.gpkg"),
        "zlewnie",
    )


def _sheets() -> Document:
    return SheetList(_sheet_request(), (SHEET,))


def _catalog() -> Document:
    return get_catalog(command="elevation download")


def _catalog_overview() -> Document:
    return get_catalog()


def _catalog_command() -> object:
    return get_catalog(command="elevation download").commands[0]


def _catalog_param() -> object:
    return get_catalog(command="elevation download").commands[0].params[0]  # type: ignore[index]


def _catalog_constraint() -> object:
    return get_catalog(command="elevation download").commands[0].constraints[0]  # type: ignore[index]


def _catalog_example() -> object:
    return get_catalog(command="elevation download").commands[0].examples[0]  # type: ignore[index]


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
    "kartograf-sources/1": (_sources,),
    "kartograf-layers/1": (_layers,),
    "kartograf-cache/1": (_cache,),
    "kartograf-store-overview/1": (_store_overview,),
    "kartograf-store-entries/1": (_store_entries,),
    "kartograf-store-sidecar/1": (_store_sidecar,),
    "kartograf-sheet/1": (_sheet_info,),
    "kartograf-sheets/1": (_sheets,),
    "kartograf-catalog/1": (_catalog, _catalog_overview),
}

# schema -> the keys of the document in order (``schema`` first)
CONTRACT: dict[str, list[str]] = {
    "kartograf-error/1": [
        "schema",
        "code",
        "title",
        "message",
        "hint",
        "details",
        "exit_code",
        "command",
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
    "kartograf-sources/1": ["schema", "group", "products", "sources"],
    "kartograf-layers/1": [
        "schema",
        "group",
        "product",
        "source",
        "layers",
        "classes",
        "years",
        "properties",
        "depths",
        "statistics",
    ],
    "kartograf-cache/1": [
        "schema",
        "action",
        "path",
        "exists",
        "size_bytes",
        "entries",
        "cleared",
        "removed_unreadable",
    ],
    "kartograf-store-overview/1": ["schema", "output_dir", "segments"],
    "kartograf-store-entries/1": [
        "schema",
        "output_dir",
        "segment",
        "units",
        "limit",
        "truncated",
        "entries",
    ],
    "kartograf-store-sidecar/1": ["schema", "path", "sidecar"],
    "kartograf-sheet/1": [
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
    ],
    "kartograf-sheets/1": ["schema", "request", "sheets", "count"],
    "kartograf-catalog/1": [
        "schema",
        "view",
        "kartograf_version",
        "language",
        "groups",
        "commands",
        "exit_codes",
        "errors",
        "schemas",
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
            "full_m2",
            "sheet_records",
            "campaign_coverage",
        ],
    ),
    "AvailabilityRecord": (
        _record,
        ["sheet", "campaign", "acquisition_date", "published", "full_sheet", "url"],
    ),
    "AvailabilityCampaign": (_campaign, ["campaign", "complete", "full_m2"]),
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
    "SourceInfo": (
        _source,
        [
            "key",
            "name",
            "country",
            "provider",
            "product",
            "directory",
            "select",
            "license",
            "auth",
            "update_signals",
        ],
    ),
    "SourceLicense": (_license, ["id", "attribution", "url"]),
    "LayerInfo": (_layer, ["code", "description"]),
    "YearInfo": (_year, ["year", "data", "description"]),
    "CacheEntries": (
        _cache_entries,
        ["records", "campaigns", "teryt", "sheets", "index_areas", "atom_feeds"],
    ),
    "SegmentInfo": (
        lambda: describe_segment(SEGMENT),
        ["segment", "product", "country", "dataset_key", "name", "known"],
    ),
    "StoreEntry": (
        _store_entry,
        [
            "kind",
            "segment",
            "hierarchy",
            "name",
            "path",
            "version_path",
            "label",
            "sha8",
            "sidecar",
            "problem",
            "skipped",
        ],
    ),
    "Sidecar": (
        _sidecar,
        [
            "schema",
            "dataset",
            "dataset_key",
            "country",
            "product",
            "provider",
            "horizontal_crs",
            "vertical_crs",
            "vertical_source",
            "resolution",
            "nodata",
            "request",
            "license",
            "downloaded_at",
            "kartograf_version",
            "transform",
            "extra",
            "sha256",
            "size_bytes",
            "data_year",
            "data_date",
            "campaign",
            "survey_work_id",
            "edition",
            "full_sheet",
            "coverage",
            "unit",
            "raw",
        ],
    ),
    "SheetLevel": (_sheet_level, ["sheet", "scale"]),
    "SheetDescendants": (_sheet_descendants, ["scale", "count", "sheets"]),
    "SheetRequest": (
        _sheet_request,
        ["scale", "sheet_system", "bbox", "bbox_crs", "geometry", "layer"],
    ),
    "GroupInfo": (
        lambda: get_catalog().groups[0],
        ["name", "summary", "description", "products", "commands"],
    ),
    "ProductInfo": (
        lambda: get_catalog().groups[0].products[0],
        ["name", "summary", "countries", "sources"],
    ),
    "CommandInfo": (
        _catalog_command,
        [
            "id",
            "group",
            "name",
            "summary",
            "description",
            "kind",
            "effects",
            "idempotent",
            "destructive",
            "project_task",
            "function",
            "check_function",
            "result_schema",
            "check_result_schema",
            "supports_check",
            "check_tool",
            "cli",
            "tool",
            "params",
            "constraints",
            "examples",
        ],
    ),
    "ParamInfo": (
        _catalog_param,
        [
            "name",
            "argument",
            "flag",
            "short",
            "positional",
            "kind",
            "required",
            "task",
            "allowed",
            "default",
            "cli_default",
            "accepts",
            "section",
            "description",
        ],
    ),
    "ConstraintInfo": (
        _catalog_constraint,
        ["type", "param", "params", "when", "message"],
    ),
    "ExampleInfo": (_catalog_example, ["title", "options", "command_line"]),
    "ExitCodeInfo": (
        lambda: get_catalog(tables=True).exit_codes[0],  # type: ignore[index]
        ["code", "name", "meaning"],
    ),
    "ErrorCodeInfo": (
        lambda: get_catalog(tables=True).errors[0],  # type: ignore[index]
        ["code", "reason", "exception", "exit_code", "meaning"],
    ),
    "SchemaInfo": (
        lambda: get_catalog(tables=True).schemas[0],  # type: ignore[index]
        ["schema", "description", "produced_by"],
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


def test_contract_equals_the_schemas_of_every_document_class():
    """Both ways: a document class without a contract row, and a row of a
    schema no class produces, fail here."""
    assert set(CONTRACT) == {cls.SCHEMA for cls in DOCUMENT_CLASSES}


def test_importing_the_package_registers_every_schema():
    """A consumer (the catalog, MCP) that only does ``import kartograf`` finds
    every document in ``SCHEMAS``; checked in a fresh interpreter, where no
    submodule was imported by something else."""
    code = (
        "import json, kartograf\n"
        "from kartograf.serialization import SCHEMAS\n"
        "print(json.dumps(sorted(SCHEMAS)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent.parent,
    )

    assert json.loads(done.stdout) == sorted(CONTRACT)
