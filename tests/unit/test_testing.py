"""The producer's test fixtures (``kartograf.testing``, Nogat DEV-10.6).

The fixtures are read back through the public read API, never through the
writers that made them.
"""

import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pyogrio
import pyogrio.raw
import pytest
import shapely

import kartograf
from kartograf import (
    _clock,
    command_for_file,
    describe_segment,
    file_footprint,
    iter_store,
    link_target,
    list_partitions,
    list_segments,
    read_sidecar,
)
from kartograf.download.collections import download_collection
from kartograf.exceptions import (
    CommandNotRebuildableError,
    DownloadError,
    InvalidSidecarError,
    ValidationError,
)
from kartograf.testing import (
    CZ_SEGMENT,
    PGW_ARCHIVE_SEGMENT,
    PGW_AREA,
    PGW_AREA_SEGMENT,
    PL_SEGMENT,
    PL_SHEET,
    VARIANTS,
    FixtureStore,
    _pgw_archive_bytes,
    build_fixture_store,
    build_pgw_archive,
    build_pgw_store,
    make_sidecar,
)

DEFECTS = [v for v in VARIANTS if v != "complete"]
PL_LABELS = ["2022-05-10_83233", "2025-01-30_84020", "2025-06-02_84500"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root: Path) -> dict[str, bytes]:
    """Relative path -> content of every file (links read as the file)."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _link_groups(root: Path) -> set[frozenset[str]]:
    """Paths grouped by inode: which names are hard links of one file."""
    groups: dict[int, set[str]] = defaultdict(set)
    for path in root.rglob("*"):
        if path.is_file():
            groups[path.stat().st_ino].add(path.relative_to(root).as_posix())
    return {frozenset(names) for names in groups.values()}


@pytest.fixture
def store(tmp_path) -> FixtureStore:
    return build_fixture_store(tmp_path / "data")


# --- build_fixture_store: the complete store ---------------------------------------


def test_complete_store_is_seen_by_the_read_api_as_a_clean_two_product_store(store):
    assert list_segments(store.root) == [CZ_SEGMENT, PL_SEGMENT]
    entries = list(iter_store(store.root))
    count = defaultdict(int)
    for entry in entries:
        count[entry.kind] += 1
    # 3 PL versions + 1 CZ version; PL standard + full_sheet link; CZ link
    assert dict(count) == {"version": 4, "link": 2, "full_sheet": 1}
    assert all(e.problem is None and e.sidecar is not None for e in entries)
    assert {e.segment for e in entries} == {CZ_SEGMENT, PL_SEGMENT}
    assert store.variant == "complete" and store.defective is None
    for segment, dataset in (
        (PL_SEGMENT, "pl.gugik.nmt_1m"),
        (CZ_SEGMENT, "cz.cuzk.dmr4g"),
    ):
        info = describe_segment(segment)
        assert (info.known, info.dataset_key) == (True, dataset)


def test_versions_of_the_pl_sheet_keep_history_with_campaign_sidecars(store):
    pl = store.file(PL_SEGMENT)
    assert [v.label for v in pl.versions] == PL_LABELS
    assert [v.status for v in pl.versions] == ["new", "new", "relabeled"]
    by_path = {e.path: e for e in iter_store(store.root) if e.kind == "version"}
    for version in pl.versions:
        entry = by_path[version.path]
        assert (entry.label, entry.sha8) == (version.label, version.sha256[:8])
        assert entry.hierarchy == "N-34/130/D/d/2/4"
        assert _sha256(version.path) == version.sha256
        meta = read_sidecar(version.path)
        assert meta.sha256 == version.sha256 and meta.size_bytes == version.size_bytes
        assert meta.schema == "kartograf-meta/1"
        assert (meta.dataset_key, meta.country, meta.product) == (
            "pl.gugik.nmt_1m",
            "PL",
            "nmt",
        )
        assert meta.unit == PL_SHEET and meta.request is not None
        assert meta.request["sheet"] == PL_SHEET
        assert (meta.horizontal_crs, meta.nodata) == ("EPSG:2180", -9999.0)
        assert meta.extra is not None
        assert meta.extra["version"] == {
            "label": version.label,
            "label_source": "campaign",
        }
    first, second, third = pl.versions
    assert [read_sidecar(v.path).data_year for v in pl.versions] == [2022, 2025, 2025]
    assert read_sidecar(first.path).survey_work_id == "P.83233"
    assert read_sidecar(first.path).data_date == "2022-05-10"
    # history: the second version still holds its own content
    assert second.path.is_file() and _sha256(second.path) == second.sha256
    assert first.sha256 != second.sha256
    assert second.sha256 == third.sha256 and second.path != third.path


def test_standard_and_full_sheet_paths_are_hard_links_of_the_newest_version(store):
    pl = store.file(PL_SEGMENT)
    first, second, third = pl.versions
    assert pl.full_sheet_path is not None
    for link in (pl.path, pl.full_sheet_path):
        assert os.path.samefile(link, third.path)
        assert not os.path.samefile(link, first.path)
        assert link.read_bytes() == third.path.read_bytes() != first.path.read_bytes()
        assert link_target(link) == third.path
    # a relabeled version shares the data (hard link) of the one it relabels
    assert os.path.samefile(second.path, third.path)
    assert third.path.stat().st_nlink >= 4
    by_kind = {
        e.kind: e
        for e in iter_store(store.root, segment=PL_SEGMENT)
        if e.kind != "version"
    }
    assert by_kind["link"].path == pl.path
    assert by_kind["full_sheet"].path == pl.full_sheet_path
    assert by_kind["link"].version_path == third.path
    assert by_kind["link"].label == third.label
    # the link's own sidecar says it is a hard link of that version
    link_meta = read_sidecar(pl.path)
    assert link_meta.extra is not None and link_meta.extra["link"] == "hardlink"
    assert link_meta.sha256 == third.sha256


def test_cz_sheet_is_a_geotiff_with_its_own_sidecar_and_footprint(store):
    cz = store.file(CZ_SEGMENT)
    assert cz.full_sheet_path is None and len(cz.versions) == 1
    (version,) = cz.versions
    assert os.path.samefile(cz.path, version.path)
    assert cz.path.read_bytes()[:4] in (b"II*\x00", b"MM\x00*")
    meta = read_sidecar(cz.path)
    assert (meta.dataset_key, meta.country, meta.unit) == (
        "cz.cuzk.dmr4g",
        "CZ",
        "CTES96",
    )
    assert meta.horizontal_crs == "EPSG:5514" and meta.vertical_crs == "EPSG:8357"
    assert meta.sha256 == version.sha256
    entry = next(e for e in iter_store(store.root) if e.path == cz.path)
    footprint = file_footprint(entry)
    assert footprint is not None and footprint.source == "header"
    # Prague: the raster really lies in Czechia
    assert 14.0 < footprint.wgs84.min_x < 15.0 and 49.5 < footprint.wgs84.min_y < 50.5


def test_pl_footprint_comes_from_the_sheet_code_and_partitions_split_the_segment(store):
    entry = next(
        e for e in iter_store(store.root) if e.path == store.file(PL_SEGMENT).path
    )
    footprint = file_footprint(entry)
    assert footprint is not None and footprint.source == "sheet"
    assert footprint.native.crs == "EPSG:2180"
    assert list_partitions(store.root, PL_SEGMENT) == [".", "N-34/130/D/d/2/4"]


def test_build_refuses_a_non_empty_root_and_an_unknown_variant(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x").write_text("x")
    with pytest.raises(ValidationError, match="does not exist or is empty"):
        build_fixture_store(tmp_path / "data")
    with pytest.raises(ValidationError) as unknown:
        build_fixture_store(tmp_path / "other", variant="nope")  # type: ignore[arg-type]
    assert unknown.value.option == "variant"
    assert unknown.value.allowed == VARIANTS
    assert not (tmp_path / "other").exists()


def test_an_empty_existing_root_is_accepted(tmp_path):
    (tmp_path / "data").mkdir()
    built = build_fixture_store(tmp_path / "data")
    assert list_segments(built.root) == [CZ_SEGMENT, PL_SEGMENT]


def test_build_leaves_no_staging_directories_and_restores_the_clock(tmp_path):
    original = _clock.now
    built = build_fixture_store(tmp_path / "data")
    assert _clock.now is original
    assert not list(built.root.rglob(".incoming"))
    with pytest.raises(ValidationError):
        build_fixture_store(tmp_path / "again", variant="nope")  # type: ignore[arg-type]
    assert _clock.now is original


# --- variants ----------------------------------------------------------------------


def _intact_rows(root: Path, skip: str | None) -> set[tuple]:
    """``(kind, relative path, label, problem)`` of the entries outside ``skip``."""
    return {
        (e.kind, e.path.relative_to(root).as_posix(), e.label, e.problem)
        for e in iter_store(root)
        if skip is None or skip not in e.path.as_posix()
    }


@pytest.mark.parametrize("variant", DEFECTS)
def test_every_variant_is_the_complete_store_plus_one_damaged_file(tmp_path, variant):
    complete = build_fixture_store(tmp_path / "complete")
    damaged = build_fixture_store(tmp_path / "damaged", variant=variant)
    assert damaged.variant == variant and damaged.defective is not None
    assert [f.segment for f in damaged.files] == [f.segment for f in complete.files]
    skip = "N-34-130-D-d-2-3" if variant != "unknown_segment" else "newproduct"
    assert _intact_rows(damaged.root, skip) == _intact_rows(complete.root, None)
    for ours, theirs in zip(damaged.files, complete.files, strict=True):
        assert [v.sha256 for v in ours.versions] == [v.sha256 for v in theirs.versions]


@pytest.mark.parametrize(
    ("variant", "problem", "message"),
    [
        ("unreadable_sidecar", "invalid_sidecar", "Cannot read the sidecar"),
        ("unknown_schema", "invalid_sidecar", "Unknown sidecar schema"),
        ("missing_sidecar", "missing_sidecar", "Cannot read the sidecar"),
    ],
)
def test_sidecar_variants_give_the_documented_problem_for_one_version(
    tmp_path, variant, problem, message
):
    built = build_fixture_store(tmp_path / "data", variant=variant)
    assert built.defective is not None
    (version,) = built.defective.versions
    problems = [e for e in iter_store(built.root) if e.kind == "problem"]
    assert [(e.problem, e.path, e.sidecar) for e in problems] == [
        (problem, version.path, None)
    ]
    assert problems[0].segment == PL_SEGMENT
    assert problems[0].label == version.label
    with pytest.raises(InvalidSidecarError, match=message) as error:
        read_sidecar(version.path)
    assert error.value.path == version.path.with_name(version.path.name + ".meta.json")
    # the data and the links of the sheet are still there; the neighbours read
    assert version.path.is_file() and built.defective.path.is_file()
    assert read_sidecar(built.file(PL_SEGMENT).versions[0].path).sha256
    assert read_sidecar(built.defective.path).sha256 == version.sha256


def test_unknown_segment_variant_is_a_segment_no_descriptor_produces(tmp_path):
    built = build_fixture_store(tmp_path / "data", variant="unknown_segment")
    assert built.defective is not None
    segment = built.defective.segment
    assert segment == "newproduct/pl_experimental"
    assert list_segments(built.root) == [segment, CZ_SEGMENT, PL_SEGMENT]
    info = describe_segment(segment)
    assert (info.known, info.product, info.dataset_key, info.name) == (
        False,
        None,
        None,
        segment,
    )
    problems = [e for e in iter_store(built.root) if e.kind == "problem"]
    assert [(e.problem, e.segment) for e in problems] == [("unknown_segment", segment)]
    assert read_sidecar(built.defective.path).dataset_key == "pl.gugik.bdot10k"


# --- determinism -------------------------------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_two_builds_with_the_same_arguments_are_byte_identical(tmp_path, variant):
    one = build_fixture_store(tmp_path / "one" / "data", variant=variant)
    two = build_fixture_store(tmp_path / "two" / "data", variant=variant)
    assert _tree(one.root) == _tree(two.root)
    assert _link_groups(one.root) == _link_groups(two.root)
    assert [v.sha256 for f in one.files for v in f.versions] == [
        v.sha256 for f in two.files for v in f.versions
    ]
    # the sidecars carry the fixed clock, never the time of the build
    stamps = {read_sidecar(v.path).downloaded_at for f in one.files for v in f.versions}
    assert all(
        stamp is not None and stamp.startswith("2026-10-12T") for stamp in stamps
    )


# --- build_pgw_archive and build_pgw_store (ADR-059) -------------------------------

_PGW_GDB = "Geobaza_2aPGW_ver_20230915.gdb"


@pytest.fixture(scope="module")
def pgw_archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_pgw_archive(tmp_path_factory.mktemp("pgw") / "pl.zip")


def _pgw_structure() -> dict:
    data = Path(kartograf.__file__).parent / "_data" / "pgw_geodatabase.json"
    return json.loads(data.read_text(encoding="utf-8"))


def test_pgw_archive_has_the_recorded_structure_of_the_publication(pgw_archive):
    """Every spatial layer of the published archive in its feature dataset, with
    its identifier and geometry columns, fields and CRS definition, and the
    attribute table beside them."""
    structure = _pgw_structure()
    gdb = f"/vsizip/{pgw_archive}/{_PGW_GDB}"
    _, _, _, (names, paths) = pyogrio.raw.read(
        gdb,
        layer="GDB_Items",
        columns=["Name", "Path"],
        read_geometry=False,
        LIST_ALL_TABLES="YES",
    )
    owner = {
        str(name): str(path).strip("\\").split("\\")[0]
        for name, path in zip(names, paths, strict=True)
        if str(path).count("\\") == 2
    }
    for layer in structure["layers"]:
        info = pyogrio.read_info(gdb, layer=layer["name"])
        assert owner[layer["name"]] == layer["dataset"]
        assert (info["fid_column"], info["geometry_name"]) == (
            layer["fid"],
            layer["geometry_column"],
        )
        assert list(info["fields"]) == list(layer["fields"])
        assert info["crs"] == structure["crs"]
    table = pyogrio.read_info(gdb, layer=structure["table"]["name"])
    assert table["geometry_type"] is None
    assert list(table["fields"]) == list(structure["table"]["fields"])
    assert len(pyogrio.list_layers(gdb)) == len(structure["layers"]) + 1


def test_pgw_river_catchments_lie_around_the_fixture_area_as_documented(pgw_archive):
    """Inside the square, across its east edge, on its north edge, outside."""
    _, _, geometries, (codes, *_) = pyogrio.raw.read(
        f"/vsizip/{pgw_archive}/{_PGW_GDB}", layer="Zlewnie_JCWP_rzecznych"
    )
    square = shapely.box(PGW_AREA.min_x, PGW_AREA.min_y, PGW_AREA.max_x, PGW_AREA.max_y)
    shapes = dict(zip(codes, shapely.from_wkb(geometries), strict=True))
    inside, across, edge, outside = (shapes[code] for code in sorted(shapes))
    assert inside.within(square)
    assert across.intersects(square) and not across.within(square)
    assert edge.touches(square)
    assert outside.disjoint(square)


def test_pgw_archive_bytes_do_not_change_between_builds(pgw_archive):
    """Reproducible UUIDs and fixed member dates: an independent build of the
    geodatabase gives the ZIP the first build gave."""
    assert _pgw_archive_bytes.__wrapped__() == pgw_archive.read_bytes()


@pytest.fixture(scope="module")
def pgw_store(tmp_path_factory: pytest.TempPathFactory):
    return build_pgw_store(tmp_path_factory.mktemp("pgw-store") / "data")


def test_pgw_store_holds_the_archive_as_the_whole_country_command_stores_it(
    pgw_store, pgw_archive
):
    assert list_segments(pgw_store.root) == [PGW_ARCHIVE_SEGMENT, PGW_AREA_SEGMENT]
    entries = list(iter_store(pgw_store.root))
    assert sorted(entry.kind for entry in entries) == [
        "link",
        "link",
        "version",
        "version",
    ]
    assert all(entry.problem is None for entry in entries)
    (version,) = pgw_store.archive.versions
    assert (version.label, version.status) == ("2023-09-15", "new")
    assert version.path.read_bytes() == pgw_archive.read_bytes()
    assert pgw_store.archive.path.samefile(version.path)
    meta = read_sidecar(version.path)
    assert (meta.dataset_key, meta.product, meta.unit) == ("pl.pgw.pgw", "pgw", "pl")
    assert meta.request == {"whole_country": True}
    assert meta.extra is not None
    assert meta.extra["version"] == {"label": "2023-09-15", "label_source": "edition"}
    assert command_for_file(meta).options == {
        "product": "pgw",
        "country": "pl",
        "whole_country": True,
    }


def test_pgw_store_holds_the_area_geopackage_the_area_command_writes(tmp_path):
    """The GeoPackage of ``PGW_AREA`` with the layers of ``PGW_WP``, written from
    the stored archive it names: the same request reuses it without a request,
    and ``command_for_file`` refuses it (a file chosen by an area)."""
    pgw_store = build_pgw_store(tmp_path / "data")
    (version,) = pgw_store.area.versions
    (archive,) = pgw_store.archive.versions
    meta = read_sidecar(version.path)

    again = download_collection(
        product="pgw",
        country="pl",
        bbox=PGW_AREA,
        layers=["PGW_WP"],
        root=pgw_store.root,
        cache=False,
    )

    assert (pgw_store.area.segment, pgw_store.area.unit) == (
        PGW_AREA_SEGMENT,
        "380000_540000_390000_550000",
    )
    assert (version.label, version.status) == ("2023-09-15", "new")
    assert pgw_store.area.path.samefile(version.path)
    layers = [str(name) for name, _ in pyogrio.list_layers(version.path)]
    assert len(layers) == 16 and "zlewnie_jcwp_rzecznych" in layers
    catchments = pyogrio.read_info(version.path, layer="zlewnie_jcwp_rzecznych")
    assert (catchments["features"], catchments["crs"]) == (3, "EPSG:2180")
    assert meta.request == {
        "bbox": [380000.0, 540000.0, 390000.0, 550000.0],
        "bbox_crs": "EPSG:2180",
        "layers": ["PGW_WP"],
    }
    assert meta.extra is not None
    assert [(f["sha256"], f["label"]) for f in meta.extra["source_files"]] == [
        (archive.sha256, archive.label)
    ]
    (reused,) = again.files
    assert (reused.file.status, reused.file.version_path) == ("reused", version.path)
    with pytest.raises(CommandNotRebuildableError):
        command_for_file(meta)


def test_two_pgw_store_builds_are_byte_identical(tmp_path, pgw_store):
    """The GeoPackage and the sidecars too: a fixed clock and a fixed GDAL date."""
    again = build_pgw_store(tmp_path / "data")

    assert _tree(again.root) == _tree(pgw_store.root)


# --- make_sidecar ------------------------------------------------------------------


def test_make_sidecar_default_is_a_valid_meta_document_of_a_pl_sheet(tmp_path):
    meta = make_sidecar()
    assert meta["schema"] == "kartograf-meta/1"
    assert meta["dataset"] == "pl.gugik.nmt_1m" and meta["request"] == {
        "sheet": PL_SHEET
    }
    assert meta["extra"]["version"] == {
        "label": "2025-01-30",
        "label_source": "edition",
    }
    assert meta["downloaded_at"] == "2026-10-12T08:30:45.123456+00:00"
    assert (meta["horizontal_crs"], meta["nodata"]) == ("EPSG:2180", -9999.0)
    assert meta == make_sidecar()
    # the read API takes it as a sidecar of a file with that content
    data = tmp_path / f"{PL_SHEET}.asc"
    data.write_bytes(b"x")
    data.with_name(data.name + ".meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    parsed = read_sidecar(data)
    assert (parsed.dataset_key, parsed.unit, parsed.sha256) == (
        "pl.gugik.nmt_1m",
        PL_SHEET,
        meta["sha256"],
    )


def test_make_sidecar_describes_the_given_data_and_arguments():
    body = b"abcdef"
    meta = make_sidecar(
        "pl.gugik.bdot10k",
        request={"teryt": "1465"},
        name="1465.gpkg",
        data=body,
        label="2025",
        label_source="edition",
        extra={"note": "n"},
    )
    assert (
        meta["sha256"] == hashlib.sha256(body).hexdigest() and meta["size_bytes"] == 6
    )
    assert meta["dataset"] == "pl.gugik.bdot10k" and meta["request"] == {
        "teryt": "1465"
    }
    assert meta["extra"] == {
        "note": "n",
        "version": {"label": "2025", "label_source": "edition"},
    }
    assert meta["country"] == "PL" and meta["license"]["id"]


def test_make_sidecar_has_the_keys_the_store_writer_gives_a_version(store):
    sidecar = store.file(PL_SEGMENT).versions[0].path
    on_disk = json.loads(
        sidecar.with_name(sidecar.name + ".meta.json").read_text(encoding="utf-8")
    )
    assert set(make_sidecar()) == set(on_disk)


def test_make_sidecar_rejects_an_unregistered_dataset():
    with pytest.raises(DownloadError):
        make_sidecar("no.such.dataset")


# --- the module itself -------------------------------------------------------------


def test_importing_the_module_adds_nothing_to_the_import_of_kartograf():
    code = (
        "import sys, kartograf\n"
        "before = set(sys.modules)\n"
        "import kartograf.testing\n"
        "print(sorted(set(sys.modules) - before))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "['kartograf.testing']"
