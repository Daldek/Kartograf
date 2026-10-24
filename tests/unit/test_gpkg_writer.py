"""Deterministic GeoPackage of ``feature_bbox`` pages (ADR-042 D5).

Pages are real answers from ``tests/fixtures/pl/feature_bbox`` (README),
copied as ``fetch_features`` saves them; the PL channels are the registry
entries ``pl.gugik.prg`` and ``pl.gugik.egib``, the RUIAN and PRNG OGC API
channels are built here.
"""

import gzip
import json
import re
import shutil
import sqlite3
import struct
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

import pyogrio
import pyogrio.raw
import pytest

from kartograf.exceptions import DownloadError
from kartograf.sources.descriptor import FeatureBBoxParams, FeatureLayer
from kartograf.sources.registry import get_source
from kartograf.transform.gpkg import GpkgSummary, write_gpkg
from kartograf.transport.feature_bbox import FeaturePages, LayerPages

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl" / "feature_bbox"


def registry_params(key: str) -> FeatureBBoxParams:
    return next(
        channel.params
        for channel in get_source(key).channels
        if isinstance(channel.params, FeatureBBoxParams)
    )


PRG = registry_params("pl.gugik.prg")
A06 = next(layer for layer in PRG.layers if layer.code == "obreb")
EGIB = registry_params("pl.gugik.egib")
DZIALKI, BUDYNKI = EGIB.layers
RUIAN = FeatureBBoxParams(
    protocol="arcgis",
    native_crs="EPSG:5514",
    axis_order="xy",
    page_size=2,
    layers=(FeatureLayer(code="obec", source="12", name="Obec", id_field="objectid"),),
    selection="level",
    order_field="objectid",
)
PRNG = FeatureBBoxParams(
    protocol="ogcapi",
    native_crs="OGC:CRS84",
    axis_order="xy",
    page_size=5,
    layers=(
        FeatureLayer(
            code="rp",
            source="NazwaGeograficznaRP",
            name="NazwaGeograficznaRP",
            id_field="id",
        ),
        FeatureLayer(
            code="world",
            source="PolskaNazwaGeograficznaSwiata",
            name="PolskaNazwaGeograficznaSwiata",
            id_field="id",
        ),
    ),
    selection="all",
)


def wfs_pages(
    root: Path,
    layer: FeatureLayer,
    schema: str,
    pages: Sequence[str | bytes],
    matched: int,
) -> LayerPages:
    """Saved WFS layer: the XSD and the pages (a fixture name or a body)."""
    layer_dir = root / layer.name
    layer_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / schema, layer_dir / "schema.xsd")
    paths = []
    for index, page in enumerate(pages):
        path = layer_dir / f"{index}.gml"
        path.write_bytes(
            page if isinstance(page, bytes) else (FIXTURES / page).read_bytes()
        )
        paths.append(path)
    return LayerPages(layer, matched, tuple(paths), layer_dir / "schema.xsd", ())


def prg_pages(root: Path, s2: bytes | None = None) -> FeaturePages:
    """PRG A06: hits 4 in pages 0/2/4 (page 2 repeats a feature of page 0)."""
    pages: list[str | bytes] = [
        "prg_a06_b4_c2_s0.xml",
        s2 if s2 is not None else "prg_a06_b4_c2_s2.xml",
        "prg_a06_b4_c2_s4.xml",
    ]
    return FeaturePages((wfs_pages(root, A06, "prg_a06_describe.xsd", pages, 4),))


def egib_pages(root: Path, order: slice = slice(None)) -> FeaturePages:
    """EGiB Warsaw: 3 parcels on pages 0/2, 1 two-part building."""
    parcels = ["egib_dzialki_bw_c2_s0.xml", "egib_dzialki_bw_c2_s2.xml"][order]
    return FeaturePages(
        (
            wfs_pages(root, DZIALKI, "egib_dzialki_describe.xsd", parcels, 3),
            wfs_pages(
                root,
                BUDYNKI,
                "egib_budynki_describe.xsd",
                ["egib_budynki_bw_c2_s0.xml"],
                1,
            ),
        )
    )


def ruian_pages(root: Path) -> FeaturePages:
    layer_dir = root / "Obec"
    layer_dir.mkdir(parents=True)
    schema = layer_dir / "layer.json"
    shutil.copy(FIXTURES / "ruian_layer12_info.json", schema)
    paths = []
    for offset in (0, 2):
        path = layer_dir / f"{offset}.json"
        gz = FIXTURES / f"ruian_l12_r2_o{offset}.json.gz"
        path.write_bytes(gzip.decompress(gz.read_bytes()))
        paths.append(path)
    fields = tuple(
        (field["name"], field["type"])
        for field in json.loads(schema.read_bytes())["fields"]
    )
    return FeaturePages((LayerPages(RUIAN.layers[0], 4, tuple(paths), schema, fields),))


def ogcapi_pages(
    root: Path, layer: FeatureLayer, pages: Sequence[bytes], matched: int
) -> LayerPages:
    """Saved OGC API layer: the GeoJSON pages ``<k>.json``, no schema."""
    layer_dir = root / layer.name
    layer_dir.mkdir(parents=True)
    paths = []
    for index, page in enumerate(pages):
        path = layer_dir / f"{index}.json"
        path.write_bytes(page)
        paths.append(path)
    return LayerPages(layer, matched, tuple(paths), None, ())


def polygons(wkb: bytes) -> int:
    """Number of polygons of a (Multi)Polygon WKB."""
    order = "<" if wkb[0] == 1 else ">"
    (code,) = struct.unpack_from(f"{order}I", wkb, 1)
    if code % 1000 == 3:
        return 1
    assert code % 1000 == 6
    return struct.unpack_from(f"{order}I", wkb, 5)[0]


def test_gpkg_is_deterministic(tmp_path):
    """Same pages (also in another order) = the same bytes; features sorted by
    id; the response-time field ``DATA`` is not in the GPKG but returned."""
    first = write_gpkg(tmp_path / "a.gpkg", egib_pages(tmp_path / "a"), params=EGIB)
    second = write_gpkg(
        tmp_path / "b.gpkg",
        egib_pages(tmp_path / "b", slice(None, None, -1)),
        params=EGIB,
    )

    assert (tmp_path / "a.gpkg").read_bytes() == (tmp_path / "b.gpkg").read_bytes()
    assert first == second
    assert first.features == {"dzialki": 3, "budynki": 1}
    assert first.dropped == {"DATA": ("2026-10-14",)}
    info = pyogrio.read_info(tmp_path / "a.gpkg", layer="dzialki")
    assert "DATA" not in list(info["fields"])
    _, _, _, fields = pyogrio.raw.read(
        tmp_path / "a.gpkg", layer="dzialki", columns=["gml_id"]
    )
    assert list(fields[0]) == [
        "dzialki.146510_8.0309.23/106",
        "dzialki.146510_8.0309.23/63",
        "dzialki.146510_8.0309.25/2",
    ]


@pytest.fixture
def gdal_options():
    """Caller-set GDAL options that ``write_gpkg`` overrides while it works."""
    options = {
        "OGR_CURRENT_DATE": "2011-11-11T11:11:11.000Z",
        "GML_FETCH_ALL_GEOMETRIES": "NO",
    }
    pyogrio.set_gdal_config_options(options)
    yield {key: pyogrio.get_gdal_config_option(key) for key in options}
    pyogrio.set_gdal_config_options(dict.fromkeys(options))


def test_gdal_config_restored_after_write(gdal_options, tmp_path):
    """The process-wide GDAL options are the caller's again after a write and
    after a failed one; the caller's values do not leak into the file (the
    multi-part building keeps both parts despite GML_FETCH_ALL_GEOMETRIES=NO)."""
    write_gpkg(tmp_path / "egib.gpkg", egib_pages(tmp_path / "ok"), params=EGIB)
    restored = {key: pyogrio.get_gdal_config_option(key) for key in gdal_options}
    page = (FIXTURES / "prg_a06_b4_c2_s2.xml").read_bytes()
    with pytest.raises(DownloadError):
        write_gpkg(
            tmp_path / "prg.gpkg",
            prg_pages(tmp_path / "bad", s2=_changed_attribute(page)),
            params=PRG,
        )

    assert restored == gdal_options
    assert {
        key: pyogrio.get_gdal_config_option(key) for key in gdal_options
    } == gdal_options
    _, _, geometries, _ = pyogrio.raw.read(
        tmp_path / "egib.gpkg", layer="budynki", columns=[]
    )
    assert polygons(bytes(geometries[0])) == 2
    with closing(sqlite3.connect(tmp_path / "egib.gpkg")) as connection:
        dates = {
            row[0]
            for row in connection.execute("SELECT last_change FROM gpkg_contents")
        }
    assert gdal_options["OGR_CURRENT_DATE"] not in dates


def test_gpkg_axes_and_crs(tmp_path):
    """PRG pages carry (N,E) pairs of urn EPSG::2180; the GPKG is EPSG:2180
    with x = easting (the recorded area: E 566000-566400, N 244000-244400)."""
    write_gpkg(tmp_path / "prg.gpkg", prg_pages(tmp_path), params=PRG)

    info = pyogrio.read_info(tmp_path / "prg.gpkg", force_total_bounds=True)
    assert info["crs"] == "EPSG:2180"
    assert info["layer_metadata"] == {"DESCRIPTION": A06.source}
    min_x, min_y, max_x, max_y = info["total_bounds"]
    assert min_x < 566000 < 566400 < max_x
    assert min_y < 244000 < 244400 < max_y


def test_curves_preserved_or_linearized_consistently(tmp_path):
    """EGiB layers (``gml:SurfacePropertyType``) come out as one linear type:
    readable MultiPolygon layers with the matched number of features. Live
    2026-10-15 the EGiB answers held no arcs; pyogrio linearizes curves."""
    write_gpkg(tmp_path / "egib.gpkg", egib_pages(tmp_path), params=EGIB)

    layers = {name: kind for name, kind in pyogrio.list_layers(tmp_path / "egib.gpkg")}
    assert layers == {"dzialki": "MultiPolygon", "budynki": "MultiPolygon"}
    counts = {
        name: pyogrio.read_info(tmp_path / "egib.gpkg", layer=name)["features"]
        for name in layers
    }
    assert counts == {"dzialki": 3, "budynki": 1}


def test_multipart_feature_keeps_every_part(tmp_path):
    """MapServer writes the two-part building as two ``<ms:geom>`` elements;
    both polygons reach the GPKG (GDAL alone keeps only the last one)."""
    write_gpkg(tmp_path / "egib.gpkg", egib_pages(tmp_path), params=EGIB)

    _, _, geometries, fields = pyogrio.raw.read(
        tmp_path / "egib.gpkg", layer="budynki", columns=["gml_id"]
    )
    assert list(fields[0]) == ["budynki.146510_8.0309.18_BUD"]
    assert polygons(bytes(geometries[0])) == 2


def _changed_attribute(page: bytes) -> bytes:
    """Page 2 with the repeated feature renamed (S-62 -> S-63)."""
    changed = page.replace(b"<ms:JPT_NAZWA_>S-62<", b"<ms:JPT_NAZWA_>S-63<", 1)
    assert changed != page
    return changed


def _changed_vertex(page: bytes) -> bytes:
    """Page 2 with one vertex of the repeated feature (its first ring) moved."""
    match = re.search(rb'<gml:posList srsDimension="2">(\S+) (\S+) (\S+)', page)
    assert match is not None
    moved = f"{float(match.group(3)) + 0.5:.6f}".encode()
    return page[: match.start(3)] + moved + page[match.end(3) :]


@pytest.mark.parametrize("change", [_changed_attribute, _changed_vertex])
def test_conflicting_duplicate_is_download_error(change, tmp_path):
    """The feature repeated on page 2 differs from its copy on page 0: not
    skipped as a duplicate - ``DownloadError`` and no file left behind."""
    page = (FIXTURES / "prg_a06_b4_c2_s2.xml").read_bytes()

    with pytest.raises(DownloadError):
        write_gpkg(
            tmp_path / "prg.gpkg", prg_pages(tmp_path, s2=change(page)), params=PRG
        )

    assert not (tmp_path / "prg.gpkg").exists()


def test_identical_duplicate_ignores_drop_fields(tmp_path):
    """A repeated feature whose only difference is ``DATA`` (an answer around
    midnight) is the same feature; both dates are reported."""
    page = (FIXTURES / "egib_dzialki_bw_c2_s0.xml").read_bytes()
    later = page.replace(b"<ms:DATA>2026-10-14<", b"<ms:DATA>2026-10-15<")
    assert later != page
    pages = FeaturePages(
        (wfs_pages(tmp_path, DZIALKI, "egib_dzialki_describe.xsd", [page, later], 2),)
    )

    summary = write_gpkg(tmp_path / "egib.gpkg", pages, params=EGIB)

    assert summary.features == {"dzialki": 2}
    assert summary.dropped == {"DATA": ("2026-10-14", "2026-10-15")}


def test_incomplete_pages_is_download_error(tmp_path):
    """Pages with fewer unique features than ``matched`` are not written."""
    pages = FeaturePages(
        (
            wfs_pages(
                tmp_path,
                A06,
                "prg_a06_describe.xsd",
                ["prg_a06_b4_c2_s0.xml", "prg_a06_b4_c2_s2.xml"],
                4,
            ),
        )
    )

    with pytest.raises(DownloadError):
        write_gpkg(tmp_path / "prg.gpkg", pages, params=PRG)

    assert not (tmp_path / "prg.gpkg").exists()


def test_arcgis_field_types_from_layer_fields(tmp_path):
    """RUIAN GeoJSON attributes typed by the layer ``fields``: OID/Integer/
    SmallInteger/Double as numbers, Date (epoch ms) as a UTC DATETIME, nulls
    kept; EPSG:5514 with x = X (east)."""
    write_gpkg(tmp_path / "ruian.gpkg", ruian_pages(tmp_path), params=RUIAN)

    info = pyogrio.read_info(tmp_path / "ruian.gpkg", force_total_bounds=True)
    types = dict(zip(info["fields"], info["dtypes"], strict=True))
    assert {name: types[name] for name in ("objectid", "kod", "okres", "nazev")} == {
        "objectid": "int64",
        "kod": "int32",
        "okres": "int16",
        "nazev": "object",
    }
    assert types["platiod"] == "datetime64[ms]"
    assert types["st_area(shape)"] == "float64"
    assert "shape" not in types
    assert info["crs"] == "EPSG:5514"
    min_x, min_y, max_x, max_y = info["total_bounds"]
    assert -460000 < min_x < max_x < -440000
    assert -1120000 < min_y < max_y < -1100000
    query = "SELECT nazev, platiod, platido, idtransakce FROM Obec WHERE objectid = ?"
    with closing(sqlite3.connect(tmp_path / "ruian.gpkg")) as connection:
        row = connection.execute(query, (6169,)).fetchone()
    assert row == ("Albrechtice", "2024-04-12T00:00:00Z", None, 5472359.0)


def test_ogcapi_field_types_span_pages(tmp_path):
    """PRNG pages with ``idPRNG`` null on the first page and integers on the
    second: one int64 column with nulls, the same bytes as one page holding
    all nine names; a field without any value is text; an empty layer (the
    recorded empty answer) has the id column only."""
    first = json.loads((FIXTURES / "prng_rp_krk_l5_o0.json").read_bytes())
    second = json.loads((FIXTURES / "prng_rp_krk_l5_o5.json").read_bytes())
    for feature in first["features"]:
        feature["properties"]["idPRNG"] = None
    merged = {**second, "features": first["features"] + second["features"]}
    empty = (FIXTURES / "prng_rp_sea_l5_o0.json").read_bytes()
    names, world = PRNG.layers

    def write(name: str, pages: list[dict]) -> tuple[Path, GpkgSummary]:
        bodies = [json.dumps(page, ensure_ascii=False).encode() for page in pages]
        layers = (
            ogcapi_pages(tmp_path / name, names, bodies, 9),
            ogcapi_pages(tmp_path / name, world, [empty], 0),
        )
        path = tmp_path / f"{name}.gpkg"
        return path, write_gpkg(path, FeaturePages(layers), params=PRNG)

    split, summary = write("split", [first, second])
    whole, _ = write("whole", [merged])

    assert split.read_bytes() == whole.read_bytes()
    assert summary.features == {
        "NazwaGeograficznaRP": 9,
        "PolskaNazwaGeograficznaSwiata": 0,
    }
    info = pyogrio.read_info(split, layer="NazwaGeograficznaRP")
    types = dict(zip(info["fields"], info["dtypes"], strict=True))
    assert (types["id"], types["idPRNG"], types["nazwaOboczna"]) == (
        "object",
        "int64",
        "object",
    )
    with closing(sqlite3.connect(split)) as connection:
        rows = dict(connection.execute("SELECT id, idPRNG FROM NazwaGeograficznaRP"))
    assert rows == {
        **{feature["id"]: None for feature in first["features"]},
        **{
            feature["id"]: feature["properties"]["idPRNG"]
            for feature in second["features"]
        },
    }
    info = pyogrio.read_info(split, layer=world.name)
    assert (info["features"], list(info["fields"])) == (0, ["id"])
