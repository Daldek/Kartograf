"""Read-only file extents (``file_footprint``) and pinned CRS operations."""

import json
import sqlite3
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf import store_geometry
from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError
from kartograf.store import StoreEntry, read_sidecar
from kartograf.store_geometry import Footprint, file_footprint, pinned_transform
from kartograf.transform.crs import TransformUnavailableError


def _entry(
    root: Path,
    name: str,
    *,
    hierarchy: str = "bbox",
    request: dict | None = None,
    crs: str | None = "EPSG:2180",
    country: str = "PL",
    body: bytes | None = None,
) -> StoreEntry:
    path = root / "data" / "nmt" / "pl_1992" / hierarchy / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is not None:
        path.write_bytes(body)
    meta = {
        "schema": "kartograf-meta/1",
        "dataset": "pl.gugik.nmt_1m",
        "country": country,
        "horizontal_crs": crs,
        "request": request or {},
    }
    Path(f"{path}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return StoreEntry(
        kind="link",
        segment="nmt/pl_1992",
        hierarchy=hierarchy,
        name=name,
        path=path,
        version_path=None,
        label=None,
        sha8=None,
        sidecar=read_sidecar(path),
        problem=None,
    )


def _coords(bbox: BBox) -> tuple[float, float, float, float]:
    return bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y


def test_request_bbox_precedes_sheet_and_header(tmp_path):
    entry = _entry(
        tmp_path,
        "6.179.12.20.asc",
        hierarchy="6/179/12/20",
        request={
            "sheet": "6.179.12.20",
            "bbox": [18.9, 50.0, 19.0, 50.1],
            "bbox_crs": "EPSG:4326",
        },
        body=b"ncols 2\nnrows 2\nxllcorner 500000\nyllcorner 500000\ncellsize 1\n",
    )
    fp = file_footprint(entry)
    assert fp == Footprint(
        BBox(18.9, 50, 19, 50.1, "EPSG:4326"),
        BBox(18.9, 50, 19, 50.1, "EPSG:4326"),
        "request",
    )


@pytest.mark.parametrize(
    ("sheet", "country", "expected_crs"),
    [
        ("N-34-130-D-d-2-4", "PL", "EPSG:2180"),
        ("6.179.12.20", "PL", "EPSG:2177"),
        ("302_5550", "CZ", "EPSG:3045"),
    ],
)
def test_computable_sheet_extent_without_file_or_network(
    tmp_path, monkeypatch, sheet, country, expected_crs
):
    entry = _entry(
        tmp_path,
        sheet + ".zip",
        hierarchy="sheets",
        country=country,
        crs=expected_crs,
        request={"sheet": sheet},
    )
    monkeypatch.setattr(
        "kartograf.store_geometry._unit_bbox",
        lambda *_: pytest.fail("sheet must not query unit index"),
    )
    fp = file_footprint(entry, network=True)
    assert fp.source == "sheet" and fp.native.crs == expected_crs
    assert fp.native.min_x < fp.native.max_x
    assert fp.wgs84.crs == "EPSG:4326"
    assert -180 < fp.wgs84.min_x < fp.wgs84.max_x < 180
    assert -90 < fp.wgs84.min_y < fp.wgs84.max_y < 90


def test_pl1992_sheet_is_the_exact_geographic_rectangle_in_wgs84(tmp_path):
    sheet = "N-34-130-D-d-2-4"
    entry = _entry(
        tmp_path, f"{sheet}.asc", hierarchy="N-34/130/D/d/2/4", request={"sheet": sheet}
    )
    fp = file_footprint(entry)
    assert fp.source == "sheet"
    assert fp.wgs84 == SheetParser(sheet).get_bbox("EPSG:4326")
    assert fp.native.crs == "EPSG:2180"


def test_entry_without_sidecar_reads_it_before_choosing_a_source(tmp_path):
    """A skipped version carries no sidecar; its request bbox still counts."""
    entry = _entry(
        tmp_path,
        "cut.tif",
        request={"bbox": [500000, 300000, 501000, 301000], "bbox_crs": "EPSG:2180"},
    )
    skipped = replace(entry, kind="version", sidecar=None, skipped=True)
    assert file_footprint(skipped) == file_footprint(entry)
    assert file_footprint(skipped).source == "request"


def test_invalid_request_bbox_falls_back_to_header(tmp_path):
    entry = _entry(
        tmp_path,
        "tile.asc",
        request={"bbox": [1, 3, 2, 4]},
        body=b"ncols 2\nnrows 3\nxllcenter 500000.5\nyllcenter 300000.5\n"
        b"dx 2\ndy 4\nNODATA_value -9999\n1 2\n",
    )
    fp = file_footprint(entry)
    assert fp.source == "header"
    assert _coords(fp.native) == (499999.5, 299998.5, 500003.5, 300010.5)


def test_unknown_crs_and_impossible_longitude_skip_request(tmp_path):
    body = b"ncols 1\nnrows 1\nxllcorner 500000\nyllcorner 300000\ncellsize 10\n"
    entry = _entry(
        tmp_path,
        "tile.asc",
        request={"bbox": [0, 0, 2, 2], "bbox_crs": "EPSG:999999"},
        body=body,
    )
    assert file_footprint(entry).source == "header"
    invalid_longitude = _entry(
        tmp_path,
        "pl.zip",
        hierarchy="country",
        request={"bbox": [190, 50, 200, 51], "bbox_crs": "EPSG:4326"},
    )
    assert file_footprint(invalid_longitude) is None


@pytest.mark.parametrize(
    "bbox",
    [
        [4, 3, 1, 5],
        [0, 1, float("nan"), 2],
        [0, 1, True, 2],
        [1, 2, 3],
    ],
)
def test_untrustworthy_request_does_not_create_a_footprint(tmp_path, bbox):
    entry = _entry(
        tmp_path,
        "country.zip",
        hierarchy="country",
        request={"bbox": bbox, "bbox_crs": "EPSG:4326"},
    )
    assert file_footprint(entry) is None


def test_tiff_header_uses_embedded_crs_and_read_only(tmp_path):
    entry = _entry(tmp_path, "tile.tif", crs="EPSG:4326")
    with rasterio.open(
        entry.path,
        "w",
        driver="GTiff",
        height=3,
        width=2,
        count=1,
        dtype="uint8",
        crs="EPSG:2180",
        transform=from_origin(500000, 300000, 10, 20),
    ):
        pass
    before = entry.path.stat().st_mtime_ns
    fp = file_footprint(entry)
    assert fp.source == "header"
    assert fp.native == BBox(500000, 299940, 500020, 300000, "EPSG:2180")
    assert entry.path.stat().st_mtime_ns == before


# CZ orthophoto JPEGs carry no georeference: the world file is the extent.
_NO_GEOREFERENCE = pytest.mark.filterwarnings(
    "ignore::rasterio.errors.NotGeoreferencedWarning"
)


@_NO_GEOREFERENCE
def test_jpeg_world_file_uses_pixel_edges_and_rotation(tmp_path):
    entry = _entry(
        tmp_path,
        "CTES96.jpg",
        hierarchy="CTES/96",
        country="CZ",
        crs="EPSG:5514",
        request={"sheet": "CTES96"},
    )
    with rasterio.open(
        entry.path, "w", driver="JPEG", height=2, width=3, count=1, dtype="uint8"
    ) as image:
        image.write(np.zeros((1, 2, 3), dtype="uint8"))
    entry.path.with_suffix(".jgw").write_text("2\n1\n0.5\n-2\n-450000\n-1115000\n")
    fp = file_footprint(entry)
    assert fp.source == "header"
    assert _coords(fp.native) == pytest.approx(
        (-450001.25, -1115003.5, -449994.25, -1114996.5)
    )


@_NO_GEOREFERENCE
def test_tm33_world_file_itself_has_an_extent(tmp_path):
    entry = _entry(
        tmp_path,
        "CTES96.TM33N.jgw",
        hierarchy="CTES/96",
        country="CZ",
        crs="EPSG:3045",
        request={"sheet": "CTES96"},
        body=b"2\n0\n0\n-2\n302001\n5550003\n",
    )
    image = entry.path.with_name("CTES96.jpg")
    with rasterio.open(
        image, "w", driver="JPEG", height=2, width=2, count=1, dtype="uint8"
    ) as dataset:
        dataset.write(np.zeros((1, 2, 2), dtype="uint8"))
    fp = file_footprint(entry)
    assert fp.source == "header"
    assert fp.native == BBox(302000, 5550000, 302004, 5550004, "EPSG:3045")


@_NO_GEOREFERENCE
def test_versioned_jpeg_finds_world_file_in_same_edition_not_current_link(tmp_path):
    label = "2025_2026-02-24"
    versions = tmp_path / "data" / "orto" / "cz_sjtsk" / "versions" / "CTES" / "96"
    image = versions / f"{label}_aaaabbbb" / "CTES96.jpg"
    world = versions / f"{label}_bbbbcccc" / "CTES96.jgw"
    image.parent.mkdir(parents=True)
    world.parent.mkdir(parents=True)
    with rasterio.open(
        image, "w", driver="JPEG", height=2, width=2, count=1, dtype="uint8"
    ) as dataset:
        dataset.write(np.zeros((1, 2, 2), dtype="uint8"))
    world.write_text("2\n0\n0\n-2\n-450001\n-1114999\n")
    metadata = {
        "schema": "kartograf-meta/1",
        "country": "CZ",
        "horizontal_crs": "EPSG:5514",
        "request": {"sheet": "CTES96"},
    }
    for path in (image, world):
        Path(f"{path}.meta.json").write_text(json.dumps(metadata))

    def version_entry(path):
        return StoreEntry(
            kind="version",
            segment="orto/cz_sjtsk",
            hierarchy="CTES/96",
            name=path.name,
            path=path,
            version_path=None,
            label=label,
            sha8=path.parent.name[-8:],
            sidecar=read_sidecar(path),
            problem=None,
        )

    jpeg_fp = file_footprint(version_entry(image))
    assert jpeg_fp.source == "header"
    assert jpeg_fp.native == BBox(-450002, -1115002, -449998, -1114998, "EPSG:5514")
    assert file_footprint(version_entry(world)) == jpeg_fp
    duplicate = versions / f"{label}_ccccdddd" / world.name
    duplicate.parent.mkdir()
    duplicate.write_text("2\n0\n0\n-2\n-999999\n-999999\n")
    assert file_footprint(version_entry(image)) is None


def test_gpkg_union_of_layers_from_immutable_metadata(tmp_path, monkeypatch):
    entry = _entry(tmp_path, "unit.gpkg")
    with sqlite3.connect(entry.path) as conn:
        conn.execute(
            "CREATE TABLE gpkg_spatial_ref_sys (srs_id INTEGER, organization TEXT,"
            " organization_coordsys_id INTEGER, definition TEXT)"
        )
        conn.execute("INSERT INTO gpkg_spatial_ref_sys VALUES (2180,'EPSG',2180,'')")
        conn.execute(
            "CREATE TABLE gpkg_contents (data_type TEXT, srs_id INTEGER,"
            " min_x REAL, min_y REAL, max_x REAL, max_y REAL)"
        )
        conn.executemany(
            "INSERT INTO gpkg_contents VALUES ('features',2180,?,?,?,?)",
            [(500000, 300000, 501000, 301000), (499000, 300500, 500500, 302000)],
        )
    from kartograf import store_geometry

    connect = sqlite3.connect
    seen = []

    def read_only(location, **kwargs):
        assert "mode=ro&immutable=1" in location and kwargs["uri"] is True
        seen.append(location)
        return connect(location, **kwargs)

    # Record the actual mode without changing SQLite's file-reading behavior.
    monkeypatch.setattr(store_geometry.sqlite3, "connect", read_only)
    before = entry.path.stat().st_mtime_ns
    fp = file_footprint(entry)
    assert fp.source == "header" and seen
    assert fp.native == BBox(499000, 300000, 501000, 302000, "EPSG:2180")
    assert entry.path.stat().st_mtime_ns == before
    assert not list(entry.path.parent.glob("*.gpkg-*"))


@pytest.mark.parametrize("suffix", ["las", "laz"])
def test_las_laz_header_extent_without_point_data(tmp_path, suffix):
    header = bytearray(227)
    header[:4] = b"LASF"
    header[24:26] = bytes((1, 2))
    struct.pack_into("<H", header, 94, 227)
    struct.pack_into("<I", header, 107, 2)
    struct.pack_into("<4d", header, 179, 501000, 500000, 302000, 301000)
    entry = _entry(tmp_path, f"tile.{suffix}", body=header)
    fp = file_footprint(entry)
    assert fp.source == "header"
    assert fp.native == BBox(500000, 301000, 501000, 302000, "EPSG:2180")


def test_las_14_extended_point_count_and_empty_file(tmp_path):
    header = bytearray(375)
    header[:4] = b"LASF"
    header[24:26] = bytes((1, 4))
    struct.pack_into("<H", header, 94, 375)
    struct.pack_into("<4d", header, 179, 501000, 500000, 302000, 301000)
    entry = _entry(tmp_path, "tile.laz", body=header)
    assert file_footprint(entry) is None
    struct.pack_into("<Q", header, 247, 2)
    entry.path.write_bytes(header)
    assert file_footprint(entry).native == BBox(
        500000, 301000, 501000, 302000, "EPSG:2180"
    )


def test_missing_georeference_and_country_archive_have_no_guessed_extent(tmp_path):
    entry = _entry(tmp_path, "pl.zip", hierarchy="country", body=b"archive")
    assert file_footprint(entry) is None
    raw = _entry(
        tmp_path,
        "tile.asc",
        crs=None,
        body=b"ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\n",
    )
    assert file_footprint(raw) is None


def test_wgs84_envelope_densifies_non_linear_edge(tmp_path, monkeypatch):
    entry = _entry(
        tmp_path,
        "country.zip",
        hierarchy="country",
        request={"bbox": [0, 0, 2, 2], "bbox_crs": "EPSG:3857"},
    )

    class Curved:
        def transform(self, xs, ys):
            return xs, ys + ys * (2 - ys)

    monkeypatch.setattr(
        "kartograf.store_geometry.pinned_transform", lambda *_: Curved()
    )
    fp = file_footprint(entry)
    assert fp.wgs84.max_y > 2.2  # a four-corner envelope would stop at 2


def test_pinned_transform_is_offline_and_rejects_unsafe_operations(monkeypatch):
    from kartograf.transform import crs as transforms

    constructor = transforms.TransformerGroup

    def checking(*args, **kwargs):
        assert kwargs["allow_ballpark"] is False and kwargs["always_xy"] is True
        assert transforms.network.is_network_enabled() is False
        return constructor(*args, **kwargs)

    monkeypatch.setattr(transforms, "TransformerGroup", checking)
    monkeypatch.setattr(store_geometry, "_LOCAL", threading.local())
    result = pinned_transform("EPSG:5514", "EPSG:4326")
    assert "S-JTSK to WGS 84 (1)" in result.description
    assert result.accuracy_m == 1.0
    x, y = result.transform(-598000, -1160000)
    assert 10 < x < 20 and 45 < y < 55
    monkeypatch.setattr(
        transforms,
        "TransformerGroup",
        lambda *args, **kwargs: SimpleNamespace(transformers=[]),
    )
    with pytest.raises(TransformUnavailableError):
        pinned_transform("EPSG:2180", "EPSG:4326")


def test_pinned_transform_is_built_once_per_thread(monkeypatch):
    """pyproj operations of a TransformerGroup are not thread-safe: every
    thread gets its own, reused on the next call in that thread."""
    monkeypatch.setattr(store_geometry, "_LOCAL", threading.local())
    here = pinned_transform("EPSG:2180", "EPSG:4326")
    assert pinned_transform("EPSG:2180", "EPSG:4326") is here
    elsewhere: list = []
    worker = threading.Thread(
        target=lambda: elsewhere.append(pinned_transform("EPSG:2180", "EPSG:4326"))
    )
    worker.start()
    worker.join()
    assert elsewhere[0] is not here
    assert elsewhere[0].description == here.description


def test_footprints_and_transforms_are_safe_from_a_thread_pool(tmp_path, monkeypatch):
    """Archiwista calls ``file_footprint`` and ``pinned_transform`` from a
    thread pool with one shared ``cache`` dict: every thread gets the same
    results as a sequential run and its own transform object."""
    monkeypatch.setattr(store_geometry, "_LOCAL", threading.local())
    tiff = _entry(tmp_path, "tile.tif")
    with rasterio.open(
        tiff.path,
        "w",
        driver="GTiff",
        height=3,
        width=2,
        count=1,
        dtype="uint8",
        crs="EPSG:2180",
        transform=from_origin(500000, 300000, 10, 20),
    ):
        pass
    entries = [
        _entry(
            tmp_path,
            "18.9_50_19_50.1.tif",
            request={"bbox": [18.9, 50.0, 19.0, 50.1], "bbox_crs": "EPSG:4326"},
        ),
        _entry(
            tmp_path,
            "N-34-130-D-d-2-4.asc",
            hierarchy="N-34/130/D/d/2/4",
            request={"sheet": "N-34-130-D-d-2-4"},
        ),
        _entry(
            tmp_path,
            "6.179.12.20.asc",
            hierarchy="6/179/12/20",
            crs="EPSG:2177",
            request={"sheet": "6.179.12.20"},
        ),
        _entry(
            tmp_path,
            "302_5550.zip",
            hierarchy="sheets",
            country="CZ",
            crs="EPSG:3045",
            request={"sheet": "302_5550"},
        ),
        tiff,
        _entry(tmp_path, "1465.zip", hierarchy="teryt", request={"teryt": "1465"}),
    ]
    cache = {("teryt", "1465"): BBox(630000, 480000, 660000, 500000, "EPSG:2180")}
    # (src, dst, lon, lat) inside the area of each operation (PL, CZ)
    pairs = [
        (
            "EPSG:4326",
            "EPSG:2180",
            np.linspace(14.2, 24.1, 50),
            np.linspace(49, 54.8, 50),
        ),
        (
            "EPSG:4326",
            "EPSG:5514",
            np.linspace(12.2, 18.8, 50),
            np.linspace(48.6, 51, 50),
        ),
    ]

    def run() -> tuple[list, list]:
        footprints = [file_footprint(entry, cache=cache) for entry in entries]
        points = [pinned_transform(s, d).transform(x, y) for s, d, x, y in pairs]
        return footprints, points

    expected: list = []
    reference = threading.Thread(target=lambda: expected.append(run()))
    reference.start()
    reference.join()
    footprints, points = expected[0]
    assert [fp.source for fp in footprints] == [
        "request",
        "sheet",
        "sheet",
        "sheet",
        "header",
        "unit",
    ]

    workers = 8
    start = threading.Barrier(workers)
    objects: dict[int, object] = {}
    lock = threading.Lock()

    def job(_: int) -> tuple[list, list]:
        start.wait()  # the first builds of every thread overlap
        result = [run() for _ in range(5)]
        with lock:
            objects[threading.get_ident()] = pinned_transform("EPSG:4326", "EPSG:2180")
        return result[-1]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(job, range(workers)))

    for got_footprints, got_points in results:
        assert got_footprints == footprints
        for got, want in zip(got_points, points, strict=True):
            np.testing.assert_array_equal(got, want)
    assert len({id(obj) for obj in objects.values()}) == len(objects) == workers
    assert set(cache) == {("teryt", "1465")}


def test_unit_indexes_are_opt_in_and_cached_in_memory(tmp_path, monkeypatch):
    from kartograf.providers.cuzk import client, sheets

    calls = {"prg": 0, "ruian": 0, "sm5": 0}

    def prg(code):
        assert code == "1465"
        calls["prg"] += 1
        return BBox(500000, 300000, 501000, 301000, "EPSG:2180")

    def query(self, endpoint, layer, **kwargs):
        calls["ruian"] += 1
        assert endpoint.endswith("RUIAN/MapServer") and layer == 7
        assert kwargs["where"] == "kod=623164" and kwargs["out_sr"] == "EPSG:5514"
        return [
            {
                "attributes": {"kod": 623164},
                "geometry": {
                    "rings": [
                        [
                            [-450000, -1110000],
                            [-449000, -1110000],
                            [-449000, -1109000],
                            [-450000, -1110000],
                        ]
                    ]
                },
            }
        ]

    def sm5(self, code):
        calls["sm5"] += 1
        assert code == "CTES96"
        return SimpleNamespace(
            bbox=BBox(-455000, -1115000, -450000, -1110000, "EPSG:5514")
        )

    monkeypatch.setattr(store_geometry, "_teryt_bbox", prg)
    monkeypatch.setattr(client.CuzkClient, "query", query)
    monkeypatch.setattr(sheets.SheetIndex, "sm5_sheet", sm5)
    cases = [
        (
            _entry(tmp_path, "1465.zip", hierarchy="teryt", request={"teryt": "1465"}),
            "teryt",
            "prg",
        ),
        (
            _entry(
                tmp_path,
                "623164.zip",
                hierarchy="ku",
                country="CZ",
                request={"ku": "623164"},
            ),
            "ku",
            "ruian",
        ),
        (
            _entry(
                tmp_path,
                "CTES96.zip",
                hierarchy="CTES/96",
                country="CZ",
                request={"sheet": "CTES96"},
            ),
            "sm5",
            "sm5",
        ),
    ]
    memory: dict[tuple[str, str], BBox] = {}
    for entry, kind, method in cases:
        assert file_footprint(entry, cache=memory) is None
        assert calls[method] == 0
        first = file_footprint(entry, network=True, cache=memory)
        assert first.source == "unit"
        assert first.native == memory[(kind, entry.path.stem)]
        assert first.wgs84.crs == "EPSG:4326"
        assert file_footprint(entry, network=True, cache=memory) == first
        # A known unit needs no network: offline scans keep the extent.
        assert file_footprint(entry, cache=memory) == first
        assert calls[method] == 1


def test_prg_wfs_unit_query_uses_filtered_real_protocol(tmp_path, monkeypatch):
    from kartograf.transport import http

    entry = _entry(tmp_path, "1465.zip", hierarchy="teryt", request={"teryt": "1465"})
    response = b"""<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
      xmlns:ms="http://mapserver.gis.umn.edu/mapserver"
      xmlns:gml="http://www.opengis.net/gml/3.2" numberMatched="1" numberReturned="1">
      <wfs:member><ms:A02_Granice_powiatow><ms:JPT_KOD_JE>1465</ms:JPT_KOD_JE>
      <gml:boundedBy><gml:Envelope srsName="urn:ogc:def:crs:EPSG::2180">
      <gml:lowerCorner>300000 500000</gml:lowerCorner>
      <gml:upperCorner>301000 501000</gml:upperCorner>
      </gml:Envelope></gml:boundedBy></ms:A02_Granice_powiatow></wfs:member>
      </wfs:FeatureCollection>"""

    def request(session, url, *, params, **kwargs):
        assert "PRG/WFS/AdministrativeBoundaries" in url
        assert params["TYPENAMES"] == "ms:A02_Granice_powiatow"
        assert "JPT_KOD_JE" in params["FILTER"] and "1465" in params["FILTER"]
        return SimpleNamespace(content=response)

    monkeypatch.setattr(http, "get_with_retry", request)
    fp = file_footprint(entry, network=True)
    assert fp.source == "unit"
    assert fp.native == BBox(500000, 300000, 501000, 301000, "EPSG:2180")


def test_broken_network_source_does_not_invent_extent(tmp_path, monkeypatch):
    from kartograf.providers.cuzk import client

    entry = _entry(tmp_path, "623164.zip", hierarchy="ku", country="CZ")
    monkeypatch.setattr(client.CuzkClient, "query", lambda *_a, **_kw: [])
    assert file_footprint(entry, network=True) is None

    def unavailable(*args, **kwargs):
        raise DownloadError("unavailable")

    monkeypatch.setattr(client.CuzkClient, "query", unavailable)
    with pytest.raises(DownloadError, match="unavailable"):
        file_footprint(entry, network=True)


def test_sm5_sheet_unknown_to_the_index_has_no_extent(tmp_path, monkeypatch):
    """Like an unknown TERYT or KU: no footprint, not an error."""
    from kartograf.providers.cuzk import client

    entry = _entry(
        tmp_path,
        "CTES96.zip",
        hierarchy="CTES/96",
        country="CZ",
        request={"sheet": "CTES96"},
    )
    monkeypatch.setattr(client.CuzkClient, "query", lambda *_a, **_kw: [])
    assert file_footprint(entry, network=True) is None


def test_prg_unit_query_identifies_itself_as_kartograf(tmp_path, monkeypatch):
    from kartograf import __version__
    from kartograf.transport import http

    entry = _entry(tmp_path, "1465.zip", hierarchy="teryt", request={"teryt": "1465"})
    seen = []

    def request(session, url, **kwargs):
        seen.append(session.headers["User-Agent"])
        return SimpleNamespace(
            content=b'<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"'
            b' numberMatched="0" numberReturned="0"/>'
        )

    monkeypatch.setattr(http, "get_with_retry", request)
    assert file_footprint(entry, network=True) is None
    assert seen == [f"kartograf/{__version__}"]
