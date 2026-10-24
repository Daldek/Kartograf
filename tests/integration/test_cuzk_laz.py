"""CUZK point clouds (``CuzkLazProvider``): sheets of an area and the pair rule.

Server answers are the recordings of 2026-10-15
(``tests/fixtures/cuzk/real_2026_10_15/``, see its README) replayed by
``CuzkSession``: openzu ``HEAD`` headers, the LAZ ZIPs of ``CTES96`` (S-JTSK)
and ``760_5518`` (ETRS89/TM33) and the ``KladyMapovychListu`` answers for the
Cieszyn area ``-447000,-1114000,-446000,-1113000`` (EPSG:5514). Any other
request fails the test. The track tests (``tests/integration/test_cz_laz.py``) reuse it.
"""

import json
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk import CuzkLazProvider

CUZK_FIXTURES = Path(__file__).parent.parent / "fixtures" / "cuzk"
RECORDED = CUZK_FIXTURES / "real_2026_10_15"
OPENZU = "https://openzu.cuzk.gov.cz/opendata"
KLADY = "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"

CTES96_URL = f"{OPENZU}/DMR4G/epsg-5514/CTES96.zip"
CTES86_URL = f"{OPENZU}/DMR4G/epsg-5514/CTES86.zip"
TM33_URL = f"{OPENZU}/DMR4G/epsg-3045/760_5518.zip"
# DMR 4G raster tile of the ETRS89 files (EPSG:3045, EVRF2007 natively).
TM33_TIFF_URL = f"{OPENZU}/DMR4G-TIFF/epsg-3045/760_5518.zip"

# Recorded area on the PL/CZ border and its EPSG:3045 envelope (``bbox_to_crs``)
# sent with the layer 26 query (fixture README).
CIESZYN = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
CIESZYN_3045 = (760922.38, 5516225.51, 762043.52, 5517346.64)

_ZIPS = {
    CTES96_URL: RECORDED / "openzu_DMR4G_5514_CTES96.zip",
    TM33_URL: RECORDED / "openzu_DMR4G_3045_760_5518.zip",
    TM33_TIFF_URL: RECORDED / "openzu_DMR4G-TIFF_3045_760_5518.zip",
}
_HEADER_NAMES = ("ETag", "Last-Modified", "Content-Length", "Content-Type")
# A 404 of openzu (fixture README): text/html, 1245 B, no ETag/Last-Modified.
_NOT_FOUND = {"Content-Length": "1245", "Content-Type": "text/html"}
# (layer, where clause) and (layer, envelope) -> recorded answer.
_WHERE = {
    (24, "MAPNOM='CTES86'"): RECORDED / "klady_24_where_ctes86.json",
    (24, "MAPNOM='CTES96'"): CUZK_FIXTURES / "klady_sm5_where_ctes96.json",
}
_LAYER_CRS = {24: "5514", 26: "3045"}
ENVELOPE_TOLERANCE = 0.01


def recorded_heads() -> dict[str, tuple[int, dict]]:
    """``url -> (status, headers)`` of the recorded openzu ``HEAD`` requests."""
    data = json.loads((RECORDED / "openzu_head.json").read_text(encoding="utf-8"))
    return {r["url"]: (r["status"], r["headers"]) for r in data["responses"]}


def recorded_json(name: str) -> dict:
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


def zip_member(url: str) -> bytes:
    """The single ``.laz`` member of a recorded openzu ZIP."""
    import zipfile

    with zipfile.ZipFile(_ZIPS[url]) as archive:
        (name,) = [n for n in archive.namelist() if n.endswith(".laz")]
        return archive.read(name)


def _response(status: int, headers: dict, body: bytes = b"") -> Mock:
    response = Mock()
    response.status_code = status
    response.headers = dict(headers)
    response.content = body
    response.iter_content = lambda chunk_size=1: (
        body[i : i + 65536] for i in range(0, len(body), 65536)
    )
    response.json = lambda: json.loads(body)
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status} Client Error: Not Found for url", response=response
        )
    return response


class CuzkSession:
    """``requests.Session`` stand-in answering only recorded CUZK requests.

    ``missing``: openzu URLs answered with the recorded 404; ``etags``: URL ->
    a changed ``ETag`` (a republished file); ``envelopes``: extra
    ``(layer, (min_x, min_y, max_x, max_y)) -> answer`` of index bbox queries.
    ``calls`` lists ``(method, url-or-query)`` in order (thread-safe).
    """

    def __init__(
        self,
        *,
        missing: tuple[str, ...] = (),
        etags: dict[str, str] | None = None,
        envelopes: dict[tuple[int, tuple[float, ...]], dict] | None = None,
    ) -> None:
        self.missing = set(missing)
        self.etags = dict(etags or {})
        self.envelopes = {
            (24, (CIESZYN.min_x, CIESZYN.min_y, CIESZYN.max_x, CIESZYN.max_y)): (
                recorded_json("klady_24_bbox_cieszyn.json")
            ),
            (26, CIESZYN_3045): recorded_json("klady_26_bbox_cieszyn.json"),
            **(envelopes or {}),
        }
        self.calls: list[tuple[str, str]] = []
        self._heads = recorded_heads()
        self._lock = threading.Lock()

    def _record(self, method: str, target: str) -> None:
        with self._lock:
            self.calls.append((method, target))

    def _headers(self, url: str, headers: dict) -> dict:
        if url in self.etags:
            return {**headers, "ETag": self.etags[url]}
        return headers

    def head(self, url: str, timeout=None, allow_redirects=True, **kwargs):
        self._record("HEAD", url)
        if url in self.missing:
            return _response(404, _NOT_FOUND)
        if url not in self._heads:
            raise AssertionError(f"HEAD poza nagraniem: {url}")
        status, headers = self._heads[url]
        return _response(status, self._headers(url, headers))

    def get(self, url: str, timeout=None, params=None, stream=False, **kwargs):
        if params is not None:
            return self._query(url, params)
        self._record("GET", url)
        if url in self.missing:
            return _response(404, _NOT_FOUND)
        if url not in _ZIPS:
            raise AssertionError(f"GET poza nagraniem: {url}")
        path = _ZIPS[url]
        meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
        headers = {name: meta[name] for name in _HEADER_NAMES}
        return _response(meta["status"], self._headers(url, headers), path.read_bytes())

    def _query(self, url: str, params: dict) -> Mock:
        prefix = f"{KLADY}/"
        if not url.startswith(prefix) or not url.endswith("/query"):
            raise AssertionError(f"Zapytanie poza nagraniem: {url}")
        layer = int(url[len(prefix) : -len("/query")])
        if "where" in params:
            self._record("QUERY", f"{layer}:{params['where']}")
            path = _WHERE.get((layer, params["where"]))
            if path is None:
                raise AssertionError(f"Zapytanie poza nagraniem: {layer} {params}")
            return _response(200, {}, path.read_bytes())
        self._record("QUERY", f"{layer}:{params['geometry']}")
        assert params["inSR"] == _LAYER_CRS[layer], params
        sent = tuple(float(v) for v in params["geometry"].split(","))
        for (known_layer, envelope), answer in self.envelopes.items():
            if known_layer == layer and all(
                abs(a - b) < ENVELOPE_TOLERANCE
                for a, b in zip(sent, envelope, strict=True)
            ):
                return _response(200, {}, json.dumps(answer).encode())
        raise AssertionError(f"Zapytanie poza nagraniem: {layer} {params}")

    def of(self, method: str) -> list[str]:
        return [target for kind, target in self.calls if kind == method]


class TestPairRule:
    """A point cloud is never transformed: S-JTSK + Bpv or ETRS89 + EVRF2007."""

    @pytest.mark.parametrize(
        ("vertical_crs", "sheet", "shown"),
        [
            ("EVRF2007", "CTES96", "arkusze SM5 (S-JTSK) sa tylko w Bpv"),
            ("Bpv", "760_5518", "kafle TM33 (ETRS89) sa tylko w EVRF2007"),
        ],
    )
    def test_laz_wrong_pair_rejected(self, vertical_crs, sheet, shown, tmp_path):
        session = CuzkSession()
        provider = CuzkLazProvider("dmr4g", session, vertical_crs=vertical_crs)
        for call in (
            lambda: provider.download(sheet, tmp_path / f"{sheet}.laz"),
            lambda: provider.file_signal(sheet),
            lambda: provider.file_url(sheet),
        ):
            with pytest.raises(ValidationError) as caught:
                call()
            assert shown in str(caught.value)
            assert "chmury punktow bez transformacji" in str(caught.value)
        assert session.calls == []
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        ("model", "vertical_crs", "expected"),
        [
            (None, "Bpv", "--model wymagane"),
            ("dmr6g", "Bpv", "--model 'dmr6g': nieznana wartosc"),
            ("dmr4g", "KRON86", "KRON86 nie jest dostepny dla LAZ CZ"),
        ],
    )
    def test_bad_choice_rejected_before_network(self, model, vertical_crs, expected):
        session = CuzkSession()
        with pytest.raises(ValidationError, match=expected):
            CuzkLazProvider(model, session, vertical_crs=vertical_crs)
        assert session.calls == []


class TestAreaSheets:
    def test_laz_area_sheets(self):
        """Bpv: SM5 sheets of layer 24 (CTES87 only touches the area);
        EVRF2007: TM33 tiles of layer 26 for the area carried to EPSG:3045."""
        session = CuzkSession()
        bpv = CuzkLazProvider("dmr5g", session, vertical_crs="Bpv")
        sm5 = bpv.sheets(CIESZYN)
        assert [info.sheet for info in sm5] == ["CTES86"]
        assert sm5[0].podil == pytest.approx(0.19)

        evrf = CuzkLazProvider("dmr5g", session, vertical_crs="EVRF2007")
        assert [info.sheet for info in evrf.sheets(CIESZYN)] == ["760_5516"]
        assert [kind for kind, _ in session.calls] == ["QUERY", "QUERY"]

    def test_sm5_sheet_outside_cz_dropped(self):
        """PODIL 0 = a sheet with no part in CZ territory: no file to fetch."""
        answer = recorded_json("klady_24_bbox_cieszyn.json")
        for feature in answer["features"]:
            feature["attributes"]["PODIL"] = 0.0
        key = (24, (CIESZYN.min_x, CIESZYN.min_y, CIESZYN.max_x, CIESZYN.max_y))
        session = CuzkSession(envelopes={key: answer})
        provider = CuzkLazProvider("dmr4g", session, vertical_crs="Bpv")
        assert provider.sheets(CIESZYN) == []
