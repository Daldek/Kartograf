"""Units of CUZK products: sheets of any KladyMapovychListu layer and RUIAN KU.

Offline, on real responses recorded on 2026-10-16
(`tests/fixtures/cuzk/real_2026_10_16/README.md`). The fake session answers
only a request identical to a recorded one (URL and every query parameter
from `<file>.headers.json`), so a changed query fails the test.
"""

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from kartograf.cache import MetadataCache
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient
from kartograf.providers.cuzk.ruian import CadastralArea, cadastral_areas_for_bbox
from kartograf.providers.cuzk.sheets import SheetIndex
from tests.conftest import recorded_response

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cuzk" / "real_2026_10_16"
RUIAN_LAYER = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/7"

# Envelopes of the recordings (Cesky Tesin, at the PL border)
TESIN_5514 = BBox(-452000, -1112000, -449000, -1110000, "EPSG:5514")
TESIN_3045 = BBox(763000, 5517000, 766000, 5520000, "EPSG:3045")
OUTSIDE_5514 = BBox(-400000, -1100000, -399000, -1099000, "EPSG:5514")  # Poland
KU_5514 = BBox(-452000, -1112000, -450000, -1110500, "EPSG:5514")


def _recorded_request(name: str) -> tuple[str, dict[str, str]]:
    meta = json.loads((FIXTURES / f"{name}.headers.json").read_text())
    parts = urlsplit(meta["url"])
    return f"{parts.scheme}://{parts.netloc}{parts.path}", dict(parse_qsl(parts.query))


class FakeCuzk:
    """``requests.Session`` stand-in replaying the named recordings.

    A GET is answered only when its URL and parameters equal those of one
    recording; ``bodies`` replace the recorded body of a fixture;
    ``calls`` = (url, params) of every GET in order.
    """

    def __init__(self, *names: str, bodies: dict[str, bytes] | None = None) -> None:
        self.routes = [(_recorded_request(n), n) for n in names]
        self.bodies = bodies or {}
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url, params=None, timeout=None, **_kwargs):
        params = dict(params or {})
        self.calls.append((url, params))
        for (rec_url, rec_params), name in self.routes:
            if url == rec_url and params == rec_params:
                response = recorded_response(FIXTURES / name, self.bodies.get(name))
                response.json.return_value = json.loads(response.content)
                return response
        raise AssertionError(f"Nieoczekiwane zapytanie: {url} {params}")


def test_cuzk_layer_sheets_s_jtsk_drops_edge_touching_sheets():
    """Layer 2 answers 4 sheets; 2 of them only touch the envelope's edge."""
    session = FakeCuzk("klady_2_bbox_tesin.json")
    sheets = SheetIndex(session=session).sheets_for_bbox(2, TESIN_5514)
    assert [s.sheet for s in sheets] == ["0510-C-15", "0510-D-11"]
    d11 = sheets[1]
    assert d11.name == "Český Těšín 0510-D-11"
    assert (d11.bbox.min_x, d11.bbox.min_y, d11.bbox.max_x, d11.bbox.max_y) == (
        -450000,
        -1112000,
        -445000,
        -1108000,
    )
    assert d11.bbox.crs == "EPSG:5514"
    assert d11.podil is None and d11.in_cz is None


def test_cuzk_layer_sheets_etrs89_layer_in_its_native_crs():
    """Layer 14 is stored in EPSG:3045 (its map CRS is 5514): ask and answer in 3045."""
    session = FakeCuzk("klady_14_bbox_tesin.json")
    sheets = SheetIndex(session=session).sheets_for_bbox(14, TESIN_3045)
    assert [s.sheet for s in sheets] == ["NM-34-07-1-D-10", "NM-34-07-1-D-15"]
    assert all(s.bbox.crs == "EPSG:3045" for s in sheets)
    assert sheets[1].bbox.max_x == pytest.approx(764200.333, abs=0.01)


def test_cuzk_layer_sheets_follow_exceeded_transfer_limit(monkeypatch):
    monkeypatch.setattr(CuzkClient, "QUERY_PAGE_SIZE", 2)
    session = FakeCuzk("klady_2_bbox_tesin_page0.json", "klady_2_bbox_tesin_page2.json")
    sheets = SheetIndex(session=session).sheets_for_bbox(2, TESIN_5514)
    assert [params["resultOffset"] for _, params in session.calls] == ["0", "2"]
    # 0510-C-15 comes from the second page, 0510-D-11 from the first
    assert [s.sheet for s in sheets] == ["0510-C-15", "0510-D-11"]


def test_cuzk_layer_sheets_valid_empty_answer_is_empty_list():
    session = FakeCuzk("klady_2_bbox_outside.json")
    assert SheetIndex(session=session).sheets_for_bbox(2, OUTSIDE_5514) == []


def test_cuzk_layer_sheets_sheet_by_mapnom_cached(tmp_path):
    cache = MetadataCache(db_path=tmp_path / "c.db")
    session = FakeCuzk("klady_2_where_0510-D-11.json")
    info = SheetIndex(session=session, cache=cache).sheet(
        2, "0510-D-11", crs="EPSG:5514"
    )
    assert (info.sheet, info.name) == ("0510-D-11", "Český Těšín 0510-D-11")
    assert info.bbox == BBox(-450000, -1112000, -445000, -1108000, "EPSG:5514")
    # second index, same cache: no request
    offline = FakeCuzk()
    again = SheetIndex(session=offline, cache=cache).sheet(
        2, "0510-D-11", crs="EPSG:5514"
    )
    assert again == info and offline.calls == []
    cache.close()


def test_cuzk_layer_sheets_unknown_mapnom_is_validation_error():
    session = FakeCuzk("klady_2_where_unknown.json")
    with pytest.raises(ValidationError, match="0000-Z-99"):
        SheetIndex(session=session).sheet(2, "0000-Z-99", crs="EPSG:5514")


@pytest.mark.parametrize(
    "mapnom", ["0510-D-11' OR '1'='1", "0510 D 11", "", "744_5534"]
)
def test_cuzk_layer_sheets_bad_characters_rejected_before_network(mapnom):
    session = FakeCuzk()
    with pytest.raises(ValidationError):
        SheetIndex(session=session).sheet(2, mapnom, crs="EPSG:5514")
    assert session.calls == []


TESIN_KU = [
    CadastralArea("652954", "Chotěbuz"),
    CadastralArea("696137", "Mosty u Českého Těšína"),
    CadastralArea("753521", "Stanislavice"),
]


def test_ku_units_from_ruian_sorted_without_geometry():
    session = FakeCuzk("ruian_7_bbox_tesin.json")
    areas = cadastral_areas_for_bbox(CuzkClient(session=session), RUIAN_LAYER, KU_5514)
    assert areas == TESIN_KU
    ((url, params),) = session.calls
    assert url == f"{RUIAN_LAYER}/query"
    assert params["returnGeometry"] == "false"


def test_ku_units_from_ruian_valid_empty_answer_is_empty_list():
    session = FakeCuzk("ruian_7_bbox_outside.json")
    client = CuzkClient(session=session)
    assert cadastral_areas_for_bbox(client, RUIAN_LAYER, OUTSIDE_5514) == []


def _ruian_body(edit) -> bytes:
    data = json.loads((FIXTURES / "ruian_7_bbox_tesin.json").read_bytes())
    edit(data["features"])
    return json.dumps(data).encode()


def test_ku_units_from_ruian_duplicates_merged():
    """Offset paging without an order may repeat a KU on the next page."""
    body = _ruian_body(lambda features: features.append(dict(features[0])))
    session = FakeCuzk(
        "ruian_7_bbox_tesin.json", bodies={"ruian_7_bbox_tesin.json": body}
    )
    areas = cadastral_areas_for_bbox(CuzkClient(session=session), RUIAN_LAYER, KU_5514)
    assert areas == TESIN_KU


@pytest.mark.parametrize(
    "attributes",
    [
        {"kod": 65295, "nazev": "Chotebuz"},  # 5 digits
        {"kod": "65295a", "nazev": "Chotebuz"},
        {"kod": 6529540, "nazev": "Chotebuz"},
        {"nazev": "Chotebuz"},
        {"kod": 652954},
    ],
)
def test_ku_units_from_ruian_bad_answer_is_download_error(attributes):
    body = _ruian_body(lambda features: features[0].update(attributes=attributes))
    session = FakeCuzk(
        "ruian_7_bbox_tesin.json", bodies={"ruian_7_bbox_tesin.json": body}
    )
    with pytest.raises(DownloadError):
        cadastral_areas_for_bbox(CuzkClient(session=session), RUIAN_LAYER, KU_5514)


def test_ku_units_cached_asks_no_service_again_also_when_empty(tmp_path):
    """The answer of an area is kept in the metadata cache (also 'no KU
    there'): a repeated run needs no service - the session of the second
    call answers nothing at all."""
    cache = MetadataCache(tmp_path / "meta.db")
    first = cadastral_areas_for_bbox(
        CuzkClient(session=FakeCuzk("ruian_7_bbox_tesin.json")),
        RUIAN_LAYER,
        KU_5514,
        cache=cache,
    )
    empty = cadastral_areas_for_bbox(
        CuzkClient(session=FakeCuzk("ruian_7_bbox_outside.json")),
        RUIAN_LAYER,
        OUTSIDE_5514,
        cache=cache,
    )

    offline = CuzkClient(session=FakeCuzk())  # any request fails the test
    assert cadastral_areas_for_bbox(offline, RUIAN_LAYER, KU_5514, cache=cache) == (
        first
    )
    assert cadastral_areas_for_bbox(
        offline, RUIAN_LAYER, OUTSIDE_5514, cache=cache
    ) == (empty)
    assert first == TESIN_KU and empty == []


def test_ku_units_refreshing_cache_asks_again_and_stores_the_answer(tmp_path):
    """``--force``/``--upgrade``/``--check-updates`` (a refreshing cache) ask
    the service even for a stored area; the answer replaces the stored one
    for the next plain run."""
    path = tmp_path / "meta.db"
    fewer = _ruian_body(lambda features: features.pop())  # an older answer
    cadastral_areas_for_bbox(
        CuzkClient(
            session=FakeCuzk(
                "ruian_7_bbox_tesin.json", bodies={"ruian_7_bbox_tesin.json": fewer}
            )
        ),
        RUIAN_LAYER,
        KU_5514,
        cache=MetadataCache(path),
    )
    session = FakeCuzk("ruian_7_bbox_tesin.json")

    refreshed = cadastral_areas_for_bbox(
        CuzkClient(session=session),
        RUIAN_LAYER,
        KU_5514,
        cache=MetadataCache(path, refresh=True),
    )

    assert refreshed == TESIN_KU and len(session.calls) == 1
    plain = cadastral_areas_for_bbox(
        CuzkClient(session=FakeCuzk()), RUIAN_LAYER, KU_5514, cache=MetadataCache(path)
    )
    assert plain == TESIN_KU
