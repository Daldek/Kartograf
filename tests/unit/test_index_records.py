"""
Tests of the index records of sheet and tile units (``index_records``).

Server answers are the recordings of 2026-10-16
(``tests/fixtures/pl/index_records/``, see its README): GetFeatureInfo of the
BDOT10k map sheets and two GetFeature pages of the mesh 3D index, served by
fake sessions routed by the request URL. Offline only.
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError
from kartograf.sources.descriptor import IndexSource
from kartograf.transport.index_records import (
    gfi_records,
    records_from_gfi,
    records_from_wfs,
    wfs_records,
)
from tests.conftest import recorded_response

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl" / "index_records"
OPENDATA = "https://opendata.geoportal.gov.pl/Mapy/Topograficzne"
MAPS = IndexSource(
    kind="wms_gfi",
    endpoint="https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WMS/PobieranieArkuszeMapBDOT10k",
    parser="map_links",
    unit_field="godlo",
    url_field=None,
    label_fields=("stan_bazy",),
)
MESH = IndexSource(
    kind="wfs",
    endpoint="https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WFS/ModeleSiatkowe3D",
    parser=None,
    unit_field="modul",
    url_field="URL_do_pobrania",
    label_fields=("Aktualnosc", "Numer_zgloszenia_pracy"),
    year_field="akt_rok",
    zone_field="uklad_xy",
)
MESH_LAYER = "gugik:SkorowidzModeleSiatkowe3D"
# Krakow area of the recorded pages (README): 4 tiles, COUNT=2 -> 2 pages
KRAKOW = BBox(566100.0, 244500.0, 566300.0, 244700.0, "EPSG:2180")


def _gfi(name: str) -> list:
    return records_from_gfi(
        (FIXTURES / name).read_bytes(), source=MAPS, layer="Mapy10k", context="test"
    )


def _gfi_error(content: bytes) -> str:
    with pytest.raises(DownloadError) as caught:
        records_from_gfi(content, source=MAPS, layer="Mapy10k", context="test")
    return str(caught.value)


def test_map_links_record():
    """One table -> one record of the canonical sheet with both formats."""
    [record] = _gfi("gfi_mapy10k_M-34-64-D-d-1.html")
    folder = f"{OPENDATA}/Wizualizacja_BDOT10k_10000/M-34-064"
    assert record.unit == "M-34-64-D-d-1"
    assert dict(record.urls) == {
        "PDF": f"{folder}/M-34-064-D-d-1.pdf",
        "TIFF": f"{folder}/M-34-064-D-d-1.tif",
    }
    assert (record.label, record.year, record.zone) == ("2026-05-27", 2026, None)
    assert record.raw["godlo"] == "M-34-064-D-d-1"

    # point outside the layer: empty body
    assert _gfi("gfi_mapy10k_outside.html") == []
    # a real HTML page without the sheet table (WFS service info page)
    message = _gfi_error((FIXTURES / "mesh_no_params.html").read_bytes())
    assert message.endswith("the result would be incomplete")
    # the table without the base date row is not a record
    page = (FIXTURES / "gfi_mapy10k_M-34-64-D-d-1.html").read_text("utf-8")
    undated = re.sub(r"<tr>\s*<th[^>]*>Stan bazy.*?</tr>", "", page, flags=re.S)
    assert undated != page
    assert _gfi_error(undated.encode()).endswith("the result would be incomplete")
    # OGC exception (unknown layer) at HTTP 200
    message = _gfi_error((FIXTURES / "gfi_exception_bad_layer.xml").read_bytes())
    assert "LayerNotDefined" in message or "Invalid layer" in message


@pytest.mark.parametrize(
    ("name", "unit", "label"),
    [
        ("gfi_mapy25k_M-34-64-D-d.html", "M-34-64-D-d", "2026-06-29"),
        ("gfi_mapy50k_M-34-64-D.html", "M-34-64-D", "2025-03-02"),
        ("gfi_mapy100k_M-34-64.html", "M-34-64", "2025-01-31"),
    ],
)
def test_map_links_other_scales(name: str, unit: str, label: str):
    """Smaller scales: date with a time, 1:25000 TIFF link in an unnamed row."""
    [record] = _gfi(name)
    assert (record.unit, record.label, record.year) == (unit, label, int(label[:4]))
    assert set(record.urls) == {"PDF", "TIFF"}
    assert record.urls["PDF"].endswith(".pdf")
    assert record.urls["TIFF"].endswith(".tif")


def test_gfi_queries_sheet_centre():
    """The GetFeatureInfo point lies inside the sheet frame (EPSG:2180, N,E)."""
    sheet = "M-34-64-D-d-1"
    seen: list[str] = []

    def get(url: str, **kwargs):
        seen.append(url)
        query = parse_qs(urlparse(url).query)
        assert query["QUERY_LAYERS"] == ["Mapy10k"]
        return recorded_response(FIXTURES / "gfi_mapy10k_M-34-64-D-d-1.html")

    session = Mock()
    session.get.side_effect = get

    [record] = gfi_records(session, MAPS, "Mapy10k", sheet, timeout=5)

    assert record.unit == sheet
    [url] = seen
    assert url.startswith(f"{MAPS.endpoint}?")
    north_min, east_min, north_max, east_max = (
        float(v) for v in parse_qs(urlparse(url).query)["BBOX"][0].split(",")
    )
    frame = SheetParser(sheet).get_bbox(crs="EPSG:2180")
    assert frame.min_x < (east_min + east_max) / 2 < frame.max_x
    assert frame.min_y < (north_min + north_max) / 2 < frame.max_y


class _MeshPages:
    """Fake session of the mesh WFS: recorded page 1 (no ``STARTINDEX``) and
    the page its ``next`` points to; ``first`` overrides page 1."""

    def __init__(self, first: tuple[str, bytes | None] = ("mesh_p1.xml", None)):
        self.first = first
        following = ET.parse(FIXTURES / "mesh_p1.xml").getroot().get("next")
        assert following is not None
        self.second = following

    def get(self, url: str, **kwargs):
        if url == self.second:
            return recorded_response(FIXTURES / "mesh_p2.xml")
        query = parse_qs(urlparse(url).query)
        assert query["TYPENAMES"] == [MESH_LAYER], url
        assert "STARTINDEX" not in query, url
        name, body = self.first
        return recorded_response(FIXTURES / name, body)

    def factory(self):
        session = Mock()
        session.get.side_effect = self.get
        return session


def test_tile_units_from_wfs_pages(monkeypatch):
    """Two pages (``next``) -> the unique tiles; a broken page is an error."""
    monkeypatch.setattr("kartograf.providers.pl.skorowidz_wfs.PAGE_SIZE", 2)
    pages = _MeshPages()

    records = wfs_records(pages.factory, MESH, MESH_LAYER, KRAKOW, timeout=5)

    assert [r.unit for r in records] == [
        "74230_55482",
        "74228_55482",
        "74230_55480",
        "74228_55480",
    ]
    assert {(r.zone, r.label, r.year) for r in records} == {
        ("2000/7", "2021-10-03_DFT.7201.043.2023", 2021)
    }
    first = records[0]
    assert dict(first.urls) == {
        "": "https://opendata.geoportal.gov.pl/DaneFotogrametryczne/Mesh/78944/"
        "78944_6777_74230_55482.zip"
    }
    assert first.raw["format"] == "OBJ"
    assert "msGeometry" not in first.raw

    page = (FIXTURES / "mesh_p1.xml").read_bytes()
    broken = [
        ("mesh_p1.xml", page.replace(b'numberReturned="2"', b'numberReturned="3"')),
        (
            "mesh_p1.xml",
            page.replace(b"https://mapy.geoportal.gov.pl/", b"https://example.org/"),
        ),
        ("mesh_no_params.html", None),  # HTML at HTTP 200
    ]
    for first_page in broken:
        with pytest.raises(DownloadError, match="the result would be incomplete"):
            wfs_records(
                _MeshPages(first_page).factory, MESH, MESH_LAYER, KRAKOW, timeout=5
            )


def test_unusable_tile_skipped(caplog):
    """A feature with an unknown CRS is skipped with its gml:id, not fatal."""
    root = ET.fromstring(
        (FIXTURES / "mesh_p1.xml").read_bytes().replace(b"PL-2000:S7", b"PL-2000", 1)
    )
    features = [e for e in root.iter() if e.tag.endswith("}SkorowidzModeleSiatkowe3D")]
    with caplog.at_level(logging.WARNING):
        records = records_from_wfs(features, source=MESH)
    assert [r.unit for r in records] == ["74228_55482"]
    assert "SkorowidzModeleSiatkowe3D.6777" in caplog.text


@pytest.mark.parametrize(
    ("declared", "zone"),
    [
        ("PL-1992", "1992"),
        ("PL-2000:S5", "2000/5"),
        ("PL-2000:S7", "2000/7"),
        ("PL-2000:S8", "2000/8"),
    ],
)
def test_tile_zone_directory_names_pl_system(declared, zone):
    """ADR-044 D7: the slot directory of a tile is the PL system of its
    record as in the segments (``1992``), a PL-2000 zone below it as the
    first part of a PL-2000 sheet code (``2000/7``) - never ``pl1992``/``s7``."""
    page = (FIXTURES / "mesh_p1.xml").read_bytes()
    root = ET.fromstring(page.replace(b"PL-2000:S7", declared.encode()))
    features = [e for e in root.iter() if e.tag.endswith("}SkorowidzModeleSiatkowe3D")]
    assert {r.zone for r in records_from_wfs(features, source=MESH)} == {zone}


def test_file_name_is_the_unit_without_unit_field():
    """Without ``unit_field`` a record is the unit of its own file (the mesh
    ``modul`` names tiles of several works, measured 2026-10-16): the unit is
    the file name without ``.zip``, the zone and label stay those of the
    record."""
    root = ET.fromstring((FIXTURES / "mesh_p1.xml").read_bytes())
    features = [e for e in root.iter() if e.tag.endswith("}SkorowidzModeleSiatkowe3D")]
    source = IndexSource(**{**MESH.__dict__, "unit_field": None})

    records = records_from_wfs(features, source=source)

    assert [r.unit for r in records] == [
        "78944_6777_74230_55482",
        "78944_6776_74228_55482",
    ]
    assert {r.zone for r in records} == {"2000/7"}
    assert {r.raw["modul"] for r in records} == {"74230_55482", "74228_55482"}
