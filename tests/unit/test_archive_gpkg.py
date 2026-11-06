"""GeoPackage of the layers of an area read from a national archive (ADR-059).

The archive is the tiny IIaPGW geodatabase of ``kartograf.testing`` (the
published feature datasets, layer names, fields and CRS definition; fictional
features around ``PGW_AREA``); the layers are the registry entry of
``pl.pgw.pgw``.
"""

import sqlite3
import zipfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.sources.descriptor import ArchiveLayersParams, FeatureLayer
from kartograf.sources.registry import get_source
from kartograf.testing import PGW_AREA, build_pgw_archive
from kartograf.transform.gpkg import write_archive_gpkg

PARAMS = next(
    channel.params
    for channel in get_source("pl.pgw.pgw").channels
    if isinstance(channel.params, ArchiveLayersParams)
)
GDB = "Geobaza_2aPGW_ver_20230915.gdb"


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_pgw_archive(tmp_path_factory.mktemp("pgw") / "pl.zip")


@pytest.fixture(scope="module")
def written(archive: Path, tmp_path_factory: pytest.TempPathFactory):
    """The GeoPackage of ``PGW_AREA`` with every layer, and its summary."""
    path = tmp_path_factory.mktemp("area") / "area.gpkg"
    summary = write_archive_gpkg(
        path, archive, params=PARAMS, layers=PARAMS.layers, area=PGW_AREA
    )
    return path, summary


def _layer(name: str) -> FeatureLayer:
    return next(layer for layer in PARAMS.layers if layer.name == name)


def _rows(path: Path, layer: str, *columns: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as db:
        return db.execute(f'SELECT {", ".join(columns)} FROM "{layer}"').fetchall()


def test_features_meeting_the_area_with_its_boundary(written):
    """A feature stays when it meets the rectangle - inside, across an edge,
    or touching it (the ``BBOX`` filter of a WFS); one outside does not. The
    features are whole and in the order of their identifier."""
    path, summary = written

    catchments = _rows(path, "zlewnie_jcwp_rzecznych", "OBJECTID", "MS_KOD")
    lakes = _rows(path, "zlewnie_bezposrednie_jcwp_jeziornych", "MS_KOD")
    monuments = _rows(
        path, "obszary_chronione_wodozalezne_pominiki_przyrody", "kodinspire"
    )

    assert [code for _, code in catchments] == [
        "RW600019000001",  # inside
        "RW600019000002",  # across the east edge
        "RW600019000003",  # touching the north edge
    ]
    assert [fid for fid, _ in catchments] == sorted(fid for fid, _ in catchments)
    assert lakes == [("LW10001",)]
    assert monuments == [("PL.ZIPOP.1393.PP.0000001",)]
    bounds = pyogrio.read_info(path, layer="zlewnie_jcwp_rzecznych")["total_bounds"]
    assert tuple(bounds) == (381000.0, 541000.0, 393000.0, 556000.0)  # not clipped
    assert summary.features["zlewnie_jcwp_rzecznych"] == 3
    assert summary.member == GDB


def test_every_chosen_layer_with_its_schema_name_and_description(written, archive):
    """Every layer, an empty one too, under its lowercase ASCII name with the
    identifier first and then the published fields; ``DESCRIPTION`` names the
    feature dataset and the source layer; EPSG:2180 is written."""
    path, summary = written
    source = f"/vsizip/{archive}/{GDB}"

    assert [str(name) for name, _ in pyogrio.list_layers(path)] == [
        layer.name for layer in PARAMS.layers
    ]
    with closing(sqlite3.connect(path)) as db:
        described = dict(
            db.execute("SELECT table_name, description FROM gpkg_contents")
        )
    for layer in PARAMS.layers:
        published = pyogrio.read_info(source, layer=layer.source)
        info = pyogrio.read_info(path, layer=layer.name)
        assert list(info["fields"]) == [layer.id_field, *published["fields"]]
        assert info["crs"] == "EPSG:2180"
        assert info["features"] == summary.features[layer.name]
        assert described[layer.name] == f"{layer.code}/{layer.source}"
    empty = pyogrio.read_info(
        path, layer="jednolite_czesci_wod_powierzchniowych_przybrzeznych"
    )
    assert (empty["features"], empty["geometry_type"]) == (0, "MultiPolygon")


def test_identifier_column_of_the_layer(written):
    """The authorities keep their own identifier column (``OBJECTID_1``)."""
    path, _ = written
    info = pyogrio.read_info(path, layer="regionalne_zarzady_gospodarki_wodnej")
    assert list(info["fields"])[0] == "OBJECTID_1"
    assert _rows(path, "regionalne_zarzady_gospodarki_wodnej", "OBJECTID_1") == [(1,)]


def test_integer_fields_keep_their_type_and_nulls(written):
    """An integer field read with nulls (floats in pyogrio) is written as an
    integer with the nulls."""
    path, _ = written
    with closing(sqlite3.connect(path)) as db:
        types = {
            name: kind
            for _, name, kind, *_ in db.execute('PRAGMA table_info("rzeki_glowne")')
        }
        values = db.execute(
            'SELECT RZAD, typeof(RZAD), STR_DOP FROM "rzeki_glowne"'
        ).fetchall()
    assert types["RZAD"] == types["STR_DOP"] == "MEDIUMINT"
    assert values == [(1, "integer", None)]


def test_chosen_layers_only(archive, tmp_path):
    chosen = tuple(layer for layer in PARAMS.layers if layer.code == "SIG")
    path = tmp_path / "sig.gpkg"

    summary = write_archive_gpkg(
        path, archive, params=PARAMS, layers=chosen, area=PGW_AREA
    )

    assert [str(name) for name, _ in pyogrio.list_layers(path)] == [
        layer.name for layer in chosen
    ]
    assert set(summary.features) == {layer.name for layer in chosen}


def test_same_archive_and_area_give_the_same_bytes(archive, written, tmp_path):
    path, _ = written
    again = tmp_path / "again.gpkg"

    write_archive_gpkg(
        again, archive, params=PARAMS, layers=PARAMS.layers, area=PGW_AREA
    )

    assert again.read_bytes() == path.read_bytes()


def test_area_without_features_is_no_coverage(archive, tmp_path):
    path = tmp_path / "empty.gpkg"
    far = BBox(700000.0, 200000.0, 701000.0, 201000.0, "EPSG:2180")

    with pytest.raises(NoCoverageError, match="PGW_WP, JCWPd, SIG"):
        write_archive_gpkg(path, archive, params=PARAMS, layers=PARAMS.layers, area=far)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("params", "layers", "problem"),
    [
        # another projection: nothing is reprojected
        (replace(PARAMS, native_crs="EPSG:2177"), PARAMS.layers, "projection"),
        # a declared layer the geodatabase lacks
        (
            PARAMS,
            (*PARAMS.layers, FeatureLayer("SIG", "Missing_layer", "x", "OBJECTID")),
            "no layer Missing_layer",
        ),
        # another identifier column than declared
        (
            PARAMS,
            (
                replace(
                    _layer("regionalne_zarzady_gospodarki_wodnej"), id_field="OBJECTID"
                ),
            ),
            "identifier column is OBJECTID_1",
        ),
    ],
    ids=["projection", "missing-layer", "identifier"],
)
def test_archive_unlike_the_declaration_is_refused(
    archive, tmp_path, params, layers, problem
):
    path = tmp_path / "area.gpkg"

    with pytest.raises(DownloadError, match=problem):
        write_archive_gpkg(path, archive, params=params, layers=layers, area=PGW_AREA)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("members", "problem"),
    [
        (["readme.txt"], "0 geodatabases"),
        (["a.gdb/gdb", "b.gdb/gdb"], "2 geodatabases"),
        (None, "cannot read"),
    ],
    ids=["none", "two", "not-a-zip"],
)
def test_archive_without_one_geodatabase_is_refused(tmp_path, members, problem):
    archive = tmp_path / "pl.zip"
    if members is None:
        archive.write_bytes(b"<html>not a zip</html>")
    else:
        with zipfile.ZipFile(archive, "w") as opened:
            for name in members:
                opened.writestr(name, b"x")

    with pytest.raises(DownloadError, match=problem):
        write_archive_gpkg(
            tmp_path / "area.gpkg",
            archive,
            params=PARAMS,
            layers=PARAMS.layers,
            area=PGW_AREA,
        )

    assert not (tmp_path / "area.gpkg").exists()
