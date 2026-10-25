"""Units of plan E collection channels (ADR-043): map sheets, index tiles, CZ
cadastral areas, national themes, the channel chosen by an option value,
the ``index`` signal and the size notice before a transfer.

The channels are built here (plan E packages add the registry entries) and
installed in the registry for one test. Every service answer is a real
recording: ``tests/fixtures/pl/e0/real_2026_10_16`` (gravimetric WFS, file
headers), ``tests/fixtures/pl/index_records`` (GetFeatureInfo of the BDOT10k
map sheets, mesh 3D WFS pages), ``tests/fixtures/cuzk/real_2026_10_16``
(RUIAN, sheet index layer 2); package bodies are built from real member
names (``tests/support/fake_packages.py``).
"""

import dataclasses
import functools
import json
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.notices import DOWNLOAD_SIZE, UNIT_LIST, WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import (
    AccessChannel,
    FeatureBBoxParams,
    FeatureLayer,
    IndexSource,
    PackageVariant,
    SheetGrid,
    SourceDescriptor,
    TransportKind,
    UnitPackageParams,
)
from tests.support.fake_packages import FakeResponse, zip_bytes

TESTS = Path(__file__).parent.parent / "fixtures"
E0 = TESTS / "pl" / "e0" / "real_2026_10_16"
INDEX = TESTS / "pl" / "index_records"
CUZK = TESTS / "cuzk" / "real_2026_10_16"
FILES: dict = json.loads((E0 / "files.json").read_text(encoding="utf-8"))

MAPS_GFI = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WMS/PobieranieArkuszeMapBDOT10k"
MESH_WFS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WFS/ModeleSiatkowe3D"
GRAV_WFS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/OsnowaGrawimetryczna/WFS"
RUIAN_7 = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/7"
OPENDATA = "https://opendata.geoportal.gov.pl"

# Krakow: the BDOT10k map sheet M-34-64-D-d-1 lies inside (GetFeatureInfo
# fixture at its centre); the mesh pages answer this exact envelope.
KRAKOW = BBox(564000.0, 243500.0, 566000.0, 245000.0, "EPSG:2180")
MESH_AREA = BBox(566100.0, 244500.0, 566300.0, 244700.0, "EPSG:2180")
GRAV_AREA = BBox(500000.0, 200000.0, 650000.0, 300000.0, "EPSG:2180")
# CZ envelopes as recorded (integer coordinates in the ArcGIS queries)
TESIN = BBox(-452000, -1112000, -449000, -1110000, "EPSG:5514")
KU_AREA = BBox(-452000, -1112000, -450000, -1110500, "EPSG:5514")


# --- fake session -------------------------------------------------------------


class Response(FakeResponse):
    """A recorded answer that also parses as JSON (ArcGIS REST)."""

    def json(self):
        return json.loads(self.content)


def recorded(path: Path, body: bytes | None = None) -> Response:
    meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
    headers = {k: v for k, v in meta.items() if k not in ("status", "url")}
    return Response(
        meta["status"], headers, path.read_bytes() if body is None else body
    )


def _key(url: str, params: dict | None = None) -> tuple:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, str(v)) for k, v in (params or {}).items()]
    return (parts.scheme, parts.netloc, parts.path, tuple(sorted(query)))


class Router:
    """``requests.Session`` stand-in: a request (URL and query parameters, in
    any order) -> a response factory; ``prefixes`` answer any URL starting
    with them (GetFeatureInfo points). ``HEAD`` uses its own route or the
    headers of the GET route. ``calls`` = (method, url) in order,
    ``timeouts`` = (url, timeout) of every request."""

    def __init__(self) -> None:
        self.routes: dict[tuple, Callable[[], Response]] = {}
        self.heads: dict[tuple, dict] = {}
        self.prefixes: list[tuple[str, Callable[[], Response]]] = []
        self.calls: list[tuple[str, str]] = []
        self.timeouts: list[tuple[str, float | None]] = []

    def add(self, url: str, answer: Callable[[], Response], params=None) -> None:
        self.routes[_key(url, params)] = answer

    def add_prefix(self, prefix: str, answer: Callable[[], Response]) -> None:
        self.prefixes.append((prefix, answer))

    def add_recorded(self, path: Path, url: str | None = None) -> None:
        """Route of a recording whose ``<file>.headers.json`` names its URL."""
        meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
        self.add(url or meta["url"], lambda: recorded(path))

    def _answer(self, url: str, params) -> Response:
        answer = self.routes.get(_key(url, params))
        if answer is None:
            full = url if not params else f"{url}?{params}"
            answer = next((a for p, a in self.prefixes if full.startswith(p)), None)
        if answer is None:
            raise AssertionError(f"Nieoczekiwane zapytanie: {url} {params or ''}")
        return answer()

    def get(self, url, params=None, timeout=None, **_kwargs) -> Response:
        self.calls.append(("GET", url))
        self.timeouts.append((url, timeout))
        return self._answer(url, params)

    def head(self, url, timeout=None, **_kwargs) -> Response:
        self.calls.append(("HEAD", url))
        if _key(url) in self.heads:
            return Response(200, self.heads[_key(url)], b"")
        found = self._answer(url, None)
        return Response(found.status_code, found.headers, b"")

    def gets(self, prefix: str = "") -> int:
        return sum(1 for m, u in self.calls if m == "GET" and u.startswith(prefix))


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def file_answer(key: str, body: bytes, **headers: str) -> Callable[[], Response]:
    """A file of ``files.json`` with ``body`` (its real head or a small ZIP)."""
    found = {**FILES[key]["headers"], "Content-Length": str(len(body)), **headers}
    return lambda: Response(200, found, body)


def head_of(key: str) -> bytes:
    return (E0 / FILES[key]["head"]).read_bytes()


# --- test channels -------------------------------------------------------------


def install(monkeypatch, *descriptors: SourceDescriptor) -> None:
    for descriptor in descriptors:
        monkeypatch.setitem(registry._SOURCES, descriptor.key, descriptor)


def source(
    key: str,
    product: str,
    country: str,
    subdir: str,
    *channels: AccessChannel,
) -> SourceDescriptor:
    return SourceDescriptor(
        key=key,
        country=country,
        product=product,
        name=f"test {product}",
        provider_name="GUGiK" if country == "PL" else "CUZK",
        channels=channels,
        tile_scheme=None,
        storage_subdir=subdir,
        default_extension=".zip",
        license=registry._GUGIK_LICENSE if country == "PL" else registry._CUZK_LICENSE,
    )


def files_channel(
    params: UnitPackageParams, signal: str, crs: str = "EPSG:2180", cap: str = "x"
) -> AccessChannel:
    return AccessChannel(
        transport=TransportKind.DIRECT_FILES,
        horizontal_crs=crs,
        capabilities=frozenset({cap}),
        update_signal=signal,  # type: ignore[arg-type]
        params=params,
    )


MAP_INDEX = IndexSource(
    kind="wms_gfi",
    endpoint=MAPS_GFI,
    parser="map_links",
    unit_field="godlo",
    url_field=None,
    label_fields=("stan_bazy",),
)
MAPS = source(
    "pl.test.maps",
    "e0maps",
    "PL",
    "maps/pl_test",
    files_channel(
        UnitPackageParams(
            unit="sheet",
            index=MAP_INDEX,
            variants=tuple(
                PackageVariant(
                    choice=(("scale", "1:10000"), ("format", fmt)),
                    url_template=None,
                    segment_tokens=("10000", fmt.lower()),
                    sheet_grid=SheetGrid(system="1992", parts=6),
                    index_layer="Mapy10k",
                    file_kind=kind,  # type: ignore[arg-type]
                )
                for fmt, kind in (("TIFF", "tiff"), ("PDF", "pdf"))
            ),
        ),
        "index",
        cap="sheet_files",
    ),
)

# Sheets computed from the extent, files from a template (no index).
SERIES = source(
    "pl.test.series",
    "e0series",
    "PL",
    "geodesy/pl_test_series",
    files_channel(
        UnitPackageParams(
            unit="sheet",
            variants=tuple(
                PackageVariant(
                    choice=(("scale", label),),
                    url_template=f"{OPENDATA}/test/{label}/{{sheet}}.zip",
                    segment_tokens=(label.replace(":", "-"),),
                    sheet_grid=SheetGrid(system="1992", parts=parts),
                )
                for label, parts in (("1:10000", 6), ("1:100000", 3))
            ),
        ),
        "none",
        cap="sheet_files",
    ),
)

MESH_INDEX = IndexSource(
    kind="wfs",
    endpoint=MESH_WFS,
    parser=None,
    unit_field="modul",
    url_field="URL_do_pobrania",
    label_fields=("Aktualnosc", "Numer_zgloszenia_pracy"),
    year_field="akt_rok",
    zone_field="uklad_xy",
)
MESH = source(
    "pl.test.mesh",
    "e0mesh",
    "PL",
    "models3d/pl_test_mesh",
    files_channel(
        UnitPackageParams(
            unit="tile",
            index=MESH_INDEX,
            variants=(
                PackageVariant(
                    choice=(),
                    url_template=None,
                    index_layer="gugik:SkorowidzModeleSiatkowe3D",
                    members=(".obj",),
                ),
            ),
        ),
        "index",
        cap="area_files",
    ),
)

KM = source(
    "cz.test.km",
    "e0km",
    "CZ",
    "cadastre/cz_test_km",
    files_channel(
        UnitPackageParams(
            unit="ku",
            ku_layer=RUIAN_7,
            variants=(
                PackageVariant(
                    choice=(("format", "SHP"),),
                    url_template="https://services.cuzk.gov.cz/shp/ku/epsg-5514/{ku}.zip",
                    segment_tokens=("shp",),
                ),
                PackageVariant(
                    choice=(("format", "DXF"),),
                    url_template="https://services.cuzk.gov.cz/dxf/ku/{ku}.zip",
                    segment_tokens=("dxf",),
                ),
            ),
        ),
        "http",
        crs="EPSG:5514",
        cap="admin_unit_files",
    ),
)

ZTM = source(
    "cz.test.ztm",
    "e0ztm",
    "CZ",
    "maps/cz_test_ztm",
    files_channel(
        UnitPackageParams(
            unit="sheet",
            variants=(
                PackageVariant(
                    choice=(("format", "TIFF"),),
                    url_template="https://openzu.cuzk.gov.cz/opendata/ZTM10-SJTSK-TIFF/{sheet}.zip",
                    segment_tokens=("10000", "sjtsk", "tiff"),
                    sheet_grid=SheetGrid(system="cuzk", layer=2, crs="EPSG:5514"),
                ),
            ),
        ),
        "http",
        crs="EPSG:5514",
        cap="sheet_files",
    ),
)

PRNG = source(
    "pl.test.names",
    "e0names",
    "PL",
    "names/pl_test",
    files_channel(
        UnitPackageParams(
            unit="country",
            themes=("MIEJSCOWOSCI", "OBIEKTY_FIZJOGRAFICZNE"),
            variants=(
                PackageVariant(
                    choice=(("format", "GML"),),
                    url_template=f"{OPENDATA}/prng/PRNG_{{theme}}_GML.zip",
                    segment_tokens=("gml",),
                ),
            ),
        ),
        "none",
        cap="country_files",
    ),
)

RCN = source(
    "pl.test.prices",
    "e0prices",
    "PL",
    "cadastre/pl_test_rcn",
    files_channel(
        UnitPackageParams(
            unit="powiat",
            variants=(
                PackageVariant(
                    choice=(),
                    url_template=(
                        f"{OPENDATA}/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/"
                        "{teryt}_transakcje_ceny.gpkg.zip"
                    ),
                ),
            ),
        ),
        "none",
        cap="admin_unit_files",
    ),
)


def grav_layers() -> tuple[FeatureLayer, ...]:
    return tuple(
        FeatureLayer(code=code, source=f"ms:{name}", name=name, id_field="nr_punktu")
        for code, name in (
            ("fundamentalna", "Fundamentalna_grawimetryczna"),
            ("bazowa", "Bazowa_grawimetryczna"),
        )
    )


def wfs_channel(network: str, endpoint: str) -> AccessChannel:
    return AccessChannel(
        transport=TransportKind.WFS,
        horizontal_crs="EPSG:2180",
        capabilities=frozenset({"bbox_vector"}),
        update_signal="none",
        endpoint=endpoint,
        params=FeatureBBoxParams(
            protocol="wfs",
            native_crs="EPSG:2180",
            axis_order="yx",
            page_size=1000,
            layers=grav_layers(),
            selection="all",
            choice=(("network", network),),
        ),
    )


CONTROL = source(
    "pl.test.control",
    "e0control",
    "PL",
    "geodesy/pl_test_control",
    wfs_channel("vertical", f"{OPENDATA}/no-such-vertical-wfs"),
    wfs_channel("gravity", GRAV_WFS),
)


def _gravity_routes(router: Router) -> None:
    grav = {"SERVICE": "WFS", "VERSION": "2.0.0"}
    router.add(
        GRAV_WFS,
        lambda: recorded(E0 / "grav_capabilities.xml"),
        {**grav, "REQUEST": "GetCapabilities"},
    )
    for short, layer in (
        ("fundamentalna", "ms:Fundamentalna_grawimetryczna"),
        ("bazowa", "ms:Bazowa_grawimetryczna"),
    ):
        query = {
            **grav,
            "REQUEST": "GetFeature",
            "TYPENAMES": layer,
            "SRSNAME": "urn:ogc:def:crs:EPSG::2180",
            "BBOX": "200000,500000,300000,650000,urn:ogc:def:crs:EPSG::2180",
        }
        router.add(
            GRAV_WFS,
            functools.partial(recorded, E0 / f"grav_{short}_describe.xsd"),
            {**grav, "REQUEST": "DescribeFeatureType", "TYPENAMES": layer},
        )
        router.add(
            GRAV_WFS,
            functools.partial(recorded, E0 / f"grav_{short}_hits.xml"),
            {**query, "RESULTTYPE": "hits"},
        )
        router.add(
            GRAV_WFS,
            functools.partial(recorded, E0 / f"grav_{short}_c1000_s0.xml"),
            {**query, "COUNT": "1000", "STARTINDEX": "0"},
        )


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


# --- sheets ---------------------------------------------------------------------


def test_pl_sheet_series_by_parts(tmp_path, router, monkeypatch):
    """The GUGiK 1:10000 series has 6-member sheet codes and 1:100000 the
    3-member ones (1-144 grid): the units equal ``find_sheets_for_bbox`` with
    the Kartograf label one level finer - the series follows the number of
    members, not a scale text. No request (template, signal ``none``)."""
    install(monkeypatch, SERIES)
    for scale, parts, label in (("1:10000", 6, "1:25000"), ("1:100000", 3, "1:200000")):
        plan = check_collection(
            product="e0series",
            root=tmp_path,
            country="pl",
            bbox=KRAKOW,
            scale=scale,
            cache=False,
        )
        units = [item.unit for item in plan.items]
        assert units == find_sheets_for_bbox(KRAKOW, label, "1992")
        assert units and all(len(unit.split("-")) == parts for unit in units)
        assert {item.status for item in plan.items} == {"missing"}
    assert "M-34-64" in units
    assert router.calls == []


def test_sheet_code_of_a_series(tmp_path, router, monkeypatch):
    """``--sheet`` of a sheet product: the series sheets of its extent - the
    sheet itself, the parent of a finer one, the sheets of a coarser one -
    in the slot of the canonical code (GUGiK writes ``M-34-064``)."""
    install(monkeypatch, SERIES)

    def units(sheet: str, scale: str) -> list[str]:
        plan = check_collection(
            product="e0series",
            root=tmp_path,
            sheet=sheet,
            scale=scale,
            cache=False,
        )
        return [item.unit for item in plan.items]

    assert units("M-34-064", "1:100000") == ["M-34-64"]
    assert units("M-34-64-D-d-1", "1:100000") == ["M-34-64"]
    assert units("M-34-64-D-d-1", "1:10000") == ["M-34-64-D-d-1"]
    assert len(units("M-34-64-D", "1:10000")) == 16
    plan = check_collection(
        product="e0series",
        root=tmp_path,
        sheet="M-34-64-D-d-1",
        scale="1:10000",
        cache=False,
    )
    assert plan.items[0].segment == "geodesy/pl_test_series_1-10000"
    assert plan.items[0].hierarchy == "M-34/64/D/d/1"
    assert router.calls == []


def test_sheet_area_meaning_kept_for_c_products(tmp_path):
    """``sheet=`` of a plan C product stays the area of the sheet (ADR-039 D4):
    the EGiB objects of its EPSG:2180 extent, no sheet unit."""
    request = validate_collection_request(
        product="map", root=tmp_path, sheet="N-34-130-D"
    )
    (part,) = request.parts
    extent = SheetParser("N-34-130-D").get_bbox(crs="EPSG:2180")
    assert part.layers and part.area == extent and part.sheet is None
    assert part.parent == {"sheet": "N-34-130-D", "countries": ["PL"]}


def test_map_links_record_gives_file_and_label(
    tmp_path, router, monkeypatch, frozen_clock
):
    """A map sheet: the link of the chosen format from the GetFeatureInfo
    record, stored 1:1 in the slot of the canonical sheet code, labelled by
    the base date of the record (signal ``index``)."""
    install(monkeypatch, MAPS)
    router.add_prefix(
        f"{MAPS_GFI}?", lambda: recorded(INDEX / "gfi_mapy10k_M-34-64-D-d-1.html")
    )
    router.add(
        FILES["map10k_tiff"]["url"], file_answer("map10k_tiff", head_of("map10k_tiff"))
    )

    report = download_collection(
        product="e0maps",
        root=tmp_path,
        sheet="M-34-064-D-d-1",
        scale="1:10000",
        format="TIFF",
        cache=False,
    )

    assert report.ok, report.failed
    (item,) = report.files
    assert item.unit == "M-34-64-D-d-1"
    path = tmp_path / "maps/pl_test_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif"
    assert item.file.path == path
    assert (item.file.status, item.file.label) == ("new", "2026-05-27")
    meta = _meta(item.file.version_path)
    assert meta["extra"]["version"] == {
        "label": "2026-05-27",
        "label_source": "edition",
    }
    source_meta = meta["extra"]["source"]
    assert source_meta["url"] == FILES["map10k_tiff"]["url"]
    assert (source_meta["index"], source_meta["layer"]) == (MAPS_GFI, "Mapy10k")
    assert source_meta["record"]["godlo"] == "M-34-064-D-d-1"
    assert meta["request"] == {
        "sheet": "M-34-64-D-d-1",
        "scale": "1:10000",
        "format": "TIFF",
    }


def test_index_signal_check_downloads_nothing(
    tmp_path, router, monkeypatch, frozen_clock
):
    """``check_collection`` compares the label of the current record with the
    local version and never asks for the file: ``current`` with the same
    base date, ``newer`` with another one; the default download keeps the
    local version without asking the index (ADR-036 erratum 3), ``upgrade``
    fetches the newer record."""
    install(monkeypatch, MAPS)
    gfi = (INDEX / "gfi_mapy10k_M-34-64-D-d-1.html").read_bytes()
    record = {"body": gfi, "asked": 0}

    def answer():
        record["asked"] += 1
        return recorded(INDEX / "gfi_mapy10k_M-34-64-D-d-1.html", record["body"])

    router.add_prefix(f"{MAPS_GFI}?", answer)
    pdf_url = FILES["map10k_pdf"]["url"]
    router.add(pdf_url, file_answer("map10k_pdf", head_of("map10k_pdf")))
    choice = {
        "product": "e0maps",
        "root": tmp_path,
        "sheet": "M-34-64-D-d-1",
        "scale": "1:10000",
        "format": "PDF",
        "cache": False,
    }
    first = download_collection(**choice)
    assert first.files[0].file.path.name == "M-34-64-D-d-1.pdf"
    del router.routes[_key(pdf_url)]  # a check never asks for the file

    (current,) = check_collection(**choice).items
    assert (current.status, current.available_label) == ("current", "2026-05-27")

    record["body"] = gfi.replace(b"2026-05-27", b"2026-09-30")
    (newer,) = check_collection(**choice).items
    assert (newer.status, newer.local_label, newer.available_label) == (
        "newer",
        "2026-05-27",
        "2026-09-30",
    )
    asked = record["asked"]
    kept = download_collection(**choice)
    assert (kept.files[0].file.status, kept.files[0].file.newer) == ("local", None)
    assert kept.files[0].file.unverified == "unchecked"
    assert record["asked"] == asked  # no GetFeatureInfo for a local sheet
    assert router.gets(pdf_url) == 1

    router.add(pdf_url, file_answer("map10k_pdf", head_of("map10k_pdf") + b"%v2"))
    upgraded = download_collection(**choice, update="upgrade")
    assert (upgraded.files[0].file.status, upgraded.files[0].file.label) == (
        "new",
        "2026-09-30",
    )


def test_sheet_without_record_is_not_a_unit(tmp_path, router, monkeypatch):
    """A sheet whose point has no record (empty GetFeatureInfo) is listed and
    left out; none with a record = ``NoCoverageError``."""
    install(monkeypatch, MAPS)
    router.add_prefix(
        f"{MAPS_GFI}?", lambda: recorded(INDEX / "gfi_mapy10k_outside.html")
    )
    notices = []
    with pytest.raises(NoCoverageError):
        check_collection(
            product="e0maps",
            root=tmp_path,
            sheet="M-34-64-D-d-1",
            scale="1:10000",
            format="TIFF",
            cache=False,
            on_notice=notices.append,
        )
    assert [n.code for n in notices] == [UNIT_LIST]
    assert "without an index record (1): M-34-64-D-d-1" in notices[0].message


def test_cuzk_layer_sheet_units(tmp_path, router, monkeypatch):
    """Sheets of a CUZK sheet index layer: the ``MAPNOM`` intersecting an area
    (edge-touching ones dropped) in the hierarchy of their codes (ADR-044 D7),
    or one given sheet checked against the layer; an unknown sheet is a
    ``ValidationError``."""
    install(monkeypatch, ZTM)
    for name in (
        "klady_2_bbox_tesin.json",
        "klady_2_where_0510-D-11.json",
        "klady_2_where_unknown.json",
    ):
        router.add_recorded(CUZK / name)
    for sheet in ("0510-C-15", "0510-D-11"):  # a check compares the ETag (HEAD)
        entry = FILES[f"cz_ztm10_tiff_{sheet}"]
        router.heads[_key(entry["url"])] = entry["headers"]

    plan = check_collection(
        product="e0ztm", root=tmp_path, country="cz", bbox=TESIN, cache=False
    )
    assert [i.unit for i in plan.items] == ["0510-C-15", "0510-D-11"]
    assert {(i.segment, i.hierarchy) for i in plan.items} == {
        ("maps/cz_test_ztm_10000_sjtsk_tiff", "0510/C/15"),
        ("maps/cz_test_ztm_10000_sjtsk_tiff", "0510/D/11"),
    }
    assert plan.items[1].name == "0510-D-11.zip"

    (one,) = check_collection(
        product="e0ztm", root=tmp_path, sheet="0510-D-11", cache=False
    ).items
    assert one.unit == "0510-D-11"

    calls = len(router.calls)
    with pytest.raises(ValidationError):
        check_collection(product="e0ztm", root=tmp_path, sheet="0510 D 11", cache=False)
    assert len(router.calls) == calls  # bad characters: no request
    with pytest.raises(ValidationError):
        check_collection(product="e0ztm", root=tmp_path, sheet="0000-Z-99", cache=False)


# --- tiles ----------------------------------------------------------------------


def test_tile_units_from_index_records(tmp_path, router, monkeypatch, frozen_clock):
    """Tiles of an area from the WFS records (two pages): each tile in the
    directory of its CRS, labelled by its record, the CRS of the record in
    the sidecar; a year without records = ``NoCoverageError``."""
    install(monkeypatch, MESH)
    monkeypatch.setattr("kartograf.providers.pl.skorowidz_wfs.PAGE_SIZE", 2)
    first = (INDEX / "mesh_p1.xml").read_bytes()
    router.add(
        MESH_WFS,
        lambda: recorded(INDEX / "mesh_p1.xml"),
        {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": "gugik:SkorowidzModeleSiatkowe3D",
            "SRSNAME": "urn:ogc:def:crs:EPSG::2180",
            "BBOX": "244500.0,566100.0,244700.0,566300.0,urn:ogc:def:crs:EPSG::2180",
            "COUNT": "2",
        },
    )
    following = (
        first.split(b'next="', 1)[1].split(b'"', 1)[0].decode().replace("&amp;", "&")
    )
    router.add(following, lambda: recorded(INDEX / "mesh_p2.xml"))

    plan = check_collection(
        product="e0mesh", root=tmp_path, country="pl", bbox=MESH_AREA, cache=False
    )
    tiles = ["74228_55480", "74228_55482", "74230_55480", "74230_55482"]
    assert [i.unit for i in plan.items] == [f"2000/7/{t}" for t in tiles]
    assert {i.hierarchy for i in plan.items} == {"2000/7"}
    assert {i.available_label for i in plan.items} == {"2021-10-03_DFT.7201.043.2023"}

    with pytest.raises(NoCoverageError) as missing:
        check_collection(
            product="e0mesh",
            root=tmp_path,
            country="pl",
            bbox=MESH_AREA,
            year=2020,
            cache=False,
        )
    assert "2021" in str(missing.value)

    url = next(
        i.available_signal["url"] for i in plan.items if i.unit == "2000/7/74230_55482"
    )
    router.add(
        url,
        lambda: Response(
            200,
            {"Content-Type": "application/zip"},
            zip_bytes(["74230_55482.obj", "74230_55482.mtl"]),
        ),
    )
    for tile in tiles[:3]:
        other = next(
            i.available_signal["url"] for i in plan.items if i.unit == f"2000/7/{tile}"
        )
        router.add(
            other,
            lambda t=tile: Response(
                200, {"Content-Type": "application/zip"}, zip_bytes([f"{t}.obj"])
            ),
        )
    report = download_collection(
        product="e0mesh",
        root=tmp_path,
        country="pl",
        bbox=MESH_AREA,
        year=2021,
        cache=False,
    )
    assert report.ok, report.failed
    file = next(f.file for f in report.files if f.unit == "2000/7/74230_55482")
    assert file.path == tmp_path / "models3d/pl_test_mesh/2000/7/74230_55482.zip"
    meta = _meta(file.version_path)
    assert meta["horizontal_crs"] == "EPSG:2178"
    assert meta["extra"]["version"]["label"] == "2021-10-03_DFT.7201.043.2023"
    assert meta["request"] == {"tile": "2000/7/74230_55482", "year": 2021}
    assert meta["extra"]["parent_request"]["bbox"] == [
        566100.0,
        244500.0,
        566300.0,
        244700.0,
    ]


# --- CZ cadastral areas -----------------------------------------------------------


def test_ku_units_from_ruian(tmp_path, router, monkeypatch, frozen_clock):
    """``--ku`` downloads the package of one cadastral area; an area asks
    RUIAN for its areas; the second run uses the local package without a
    request (ADR-036 erratum 3)."""
    install(monkeypatch, KM)
    router.add_recorded(CUZK / "ruian_7_bbox_tesin.json")
    for code in ("652954", "696137", "753521"):  # a check compares the ETag (HEAD)
        entry = FILES[f"cz_km_shp_{code}"]
        router.heads[_key(entry["url"])] = entry["headers"]
    plan = check_collection(
        product="e0km",
        root=tmp_path,
        country="cz",
        bbox=KU_AREA,
        format="SHP",
        cache=False,
    )
    assert [i.unit for i in plan.items] == ["652954", "696137", "753521"]
    assert {i.hierarchy for i in plan.items} == {"ku"}

    entry = FILES["cz_km_shp_623164"]
    body = zip_bytes(entry["members"])
    router.add(entry["url"], file_answer("cz_km_shp_623164", body))
    first = download_collection(
        product="e0km", root=tmp_path, ku="623164", format="SHP", cache=False
    )
    (item,) = first.files
    assert item.file.path == tmp_path / "cadastre/cz_test_km_shp/ku/623164.zip"
    assert _meta(item.file.version_path)["request"] == {"ku": "623164", "format": "SHP"}
    second = download_collection(
        product="e0km", root=tmp_path, ku="623164", format="SHP", cache=False
    )
    assert second.files[0].file.status == "local"
    assert second.files[0].file.unverified == "unchecked"
    assert router.gets(entry["url"]) == 1


# --- national themes ------------------------------------------------------------


def test_national_file_of_several_themes(tmp_path, router, monkeypatch, frozen_clock):
    """A national product of two files: one unit per theme, each announced
    with its size before the transfer."""
    install(monkeypatch, PRNG)
    for key in ("prng_miejscowosci_gml", "prng_obiekty_gml"):
        entry = FILES[key]
        router.add(entry["url"], file_answer(key, zip_bytes(entry["members"])))
        router.heads[_key(entry["url"])] = entry["headers"]
    notices = []
    report = download_collection(
        product="e0names",
        root=tmp_path,
        country="pl",
        whole_country=True,
        format="GML",
        cache=False,
        on_notice=notices.append,
    )
    assert report.ok, report.failed
    assert [f.file.path.relative_to(tmp_path).as_posix() for f in report.files] == [
        "names/pl_test_gml/country/pl_miejscowosci.zip",
        "names/pl_test_gml/country/pl_obiekty-fizjograficzne.zip",
    ]
    sizes = [n.message for n in notices if n.code == WHOLE_COUNTRY_SIZE]
    assert len(sizes) == 2 and "20358653 B" in sizes[0] and "26414682 B" in sizes[1]


# --- options, channels and sizes ----------------------------------------------------


def test_feature_channel_by_choice(tmp_path, router, monkeypatch, frozen_clock):
    """``network="gravity"`` picks the gravimetric WFS of a product with one
    service per network; the network names the segment; without it the
    networks are listed."""
    install(monkeypatch, CONTROL)
    _gravity_routes(router)
    with pytest.raises(ValidationError) as missing:
        validate_collection_request(
            product="e0control", root=tmp_path, country="pl", bbox=GRAV_AREA
        )
    assert "--network required" in str(missing.value)
    assert "vertical, gravity" in str(missing.value)

    report = download_collection(
        product="e0control",
        root=tmp_path,
        country="pl",
        bbox=GRAV_AREA,
        network="gravity",
        cache=False,
    )
    assert report.ok, report.failed
    file = report.files[0].file
    assert file.path.parent.parent.name == "pl_test_control_gravity"
    meta = _meta(file.version_path)
    assert meta["request"]["network"] == "gravity"
    assert [layer["features"] for layer in meta["extra"]["source"]["layers"]] == [12, 6]
    assert all(url.startswith(GRAV_WFS) for _, url in router.calls)


def test_selection_key_names_several_layers(tmp_path, monkeypatch):
    """``selection_key="network"``: one network code may name several layers
    (CZ survey control: horizontal = layers 18 and 20); both are asked."""
    layers = (
        FeatureLayer(code="horizontal", source="18", name="zpbp", id_field="OBJECTID"),
        FeatureLayer(
            code="horizontal", source="20", name="zpbp_etrs", id_field="OBJECTID"
        ),
        FeatureLayer(code="vertical", source="44", name="zvbp", id_field="OBJECTID"),
    )
    channel = AccessChannel(
        transport=TransportKind.ARCGIS_QUERY,
        horizontal_crs="EPSG:5514",
        capabilities=frozenset({"bbox_vector"}),
        endpoint="https://ags.cuzk.gov.cz/arcgis/rest/services/BodovaPole/MapServer",
        params=FeatureBBoxParams(
            protocol="arcgis",
            native_crs="EPSG:5514",
            axis_order="xy",
            page_size=1000,
            layers=layers,
            selection="level",
            order_field="OBJECTID",
            selection_key="network",
        ),
    )
    install(
        monkeypatch,
        source(
            "cz.test.control", "e0control", "CZ", "geodesy/cz_test_control", channel
        ),
    )
    request = validate_collection_request(
        product="e0control",
        root=tmp_path,
        country="cz",
        bbox=TESIN,
        network="horizontal",
    )
    (part,) = request.parts
    assert [layer.source for layer in part.layers] == ["18", "20"]
    assert part.segment == "geodesy/cz_test_control_horizontal"
    with pytest.raises(ValidationError) as missing:
        validate_collection_request(
            product="e0control", root=tmp_path, country="cz", bbox=TESIN
        )
    assert "--network required" in str(missing.value)
    assert "horizontal, vertical" in str(missing.value)
    with pytest.raises(ValidationError):  # the levels of other products do not apply
        validate_collection_request(
            product="e0control",
            root=tmp_path,
            country="cz",
            bbox=TESIN,
            level="obec",
        )


@pytest.mark.parametrize(
    ("product", "choice", "allowed"),
    [
        ("e0maps", {"sheet": "M-34-64-D-d-1", "format": "GIF"}, "TIFF, PDF"),
        (
            "e0maps",
            {"sheet": "M-34-64-D-d-1", "format": "TIFF", "scale": "1:5000"},
            "1:10000",
        ),
        ("e0maps", {"sheet": "M-34-64-D-d-1", "scale": "1:10000"}, "TIFF, PDF"),
        (
            "e0maps",
            {"sheet": "M-34-64-D-d-1", "format": "TIFF", "network": "gravity"},
            "--scale",
        ),
        ("e0ztm", {"sheet": "0510-D-11", "sheet_system": "etrs89"}, "--format"),
        ("e0km", {"ku": "62316", "format": "SHP"}, "6 digits"),
        ("e0km", {"ku": "623164"}, "SHP, DXF"),
        ("e0km", {"ku": "623164", "format": "SHP", "country": "pl"}, "CZ"),
        ("e0km", {"teryt": "1261", "format": "SHP"}, "available only for CZ"),
        (
            "e0control",
            {"bbox": GRAV_AREA, "country": "pl", "network": "magnetic"},
            "vertical, gravity",
        ),
        ("e0names", {"whole_country": True, "country": "pl", "format": "SHP"}, "GML"),
    ],
)
def test_new_selection_validated_before_network(
    tmp_path, router, monkeypatch, product, choice, allowed
):
    """An option value outside the descriptor, a missing required option, a KU
    code that is not 6 digits or a selection the product has not: a
    ``ValidationError`` naming the allowed values, before any request."""
    install(monkeypatch, MAPS, ZTM, KM, CONTROL, PRNG)
    with pytest.raises(ValidationError) as error:
        download_collection(product=product, root=tmp_path, cache=False, **choice)
    assert allowed in str(error.value)
    assert router.calls == []


def test_size_notice_before_get(tmp_path, router, monkeypatch, frozen_clock):
    """A unit file over 100 MiB (``HEAD``) is announced before its first
    ``GET``; ``check_collection`` never asks for it."""
    install(monkeypatch, RCN)
    entry = FILES["rcn_1261"]
    router.add(
        entry["url"], file_answer("rcn_1261", zip_bytes(["1261_transakcje_ceny.gpkg"]))
    )
    router.heads[_key(entry["url"])] = entry["headers"]
    seen: list[tuple[str, int]] = []
    report = download_collection(
        product="e0prices",
        root=tmp_path,
        teryt="1261",
        cache=False,
        on_notice=lambda n: seen.append((n.code, router.gets(entry["url"]))),
    )
    assert report.ok, report.failed
    assert seen == [(DOWNLOAD_SIZE, 0)]
    assert "301623607 B" in next(
        n.message for n in report.notices if n.code == DOWNLOAD_SIZE
    )

    gets = router.gets()
    check_collection(product="e0prices", root=tmp_path, teryt="1261", cache=False)
    assert router.gets() == gets


def test_channel_timeout_for_a_slow_service(
    tmp_path, router, monkeypatch, frozen_clock
):
    """The pages of a service slower than the default wait the timeout of
    its channel (OGC API Features of GUGiK answer in 73-93 s)."""
    slow = dataclasses.replace(
        CONTROL,
        channels=tuple(
            dataclasses.replace(ch, params=dataclasses.replace(ch.params, timeout=300))
            for ch in CONTROL.channels
        ),
    )
    install(monkeypatch, slow)
    _gravity_routes(router)
    download_collection(
        product="e0control",
        root=tmp_path,
        country="pl",
        bbox=GRAV_AREA,
        network="gravity",
        cache=False,
    )
    assert {timeout for url, timeout in router.timeouts if url == GRAV_WFS} == {300}
