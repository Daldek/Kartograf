"""PL orthophotomap cutout from GUGiK WCS in the store (ADR-042 D14).

Recorded WCS answers: ``tests/fixtures/pl/orto_wcs/README.md``.
"""

import json
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
import requests

from kartograf.core.bbox import BBox
from kartograf.download.area import pl_only_flags
from kartograf.download.data import check_data, download_data, validate_data_request
from kartograf.download.orto_cutout import check_image_cutout, download_image_cutout
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import ALL_NODATA, AUTO_NARROWED_TO_PL, CUTOUT_SIZE, Notice
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    GugikOrtoProvider,
    wcs_cutout_channels,
)
from kartograf.sources.descriptor import WcsCutoutParams
from kartograf.transport.chunks import ChunkLimits
from tests.conftest import recorded_response, write_gpkg_layers

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "orto_wcs"
SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"
PROVIDER_FACTORY = "kartograf.download.orto_cutout._cutout_provider"
WCS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS"
STANDARD = (f"{WCS}/StandardResolution", "Orthoimagery_StandardResolution")
HIGH = (f"{WCS}/HighResolution", "Orthoimagery_High_Resolution")

# (endpoint, COVERAGEID, SCALEFACTOR, SUBSET x0, x1, y0, y1) -> recorded answer
RECORDED = {
    (*STANDARD, "0.4", (566000.0, 566001.0, 243000.0, 243001.0)): (
        "standard_0.25m_4x4.tif"
    ),
    (*STANDARD, "0.4", (566000.0, 566000.5, 243000.5, 243001.0)): (
        "standard_0.25m_4x4_q1.tif"
    ),
    (*STANDARD, "0.4", (566000.5, 566001.0, 243000.5, 243001.0)): (
        "standard_0.25m_4x4_q2.tif"
    ),
    (*STANDARD, "0.4", (566000.0, 566000.5, 243000.0, 243000.5)): (
        "standard_0.25m_4x4_q3.tif"
    ),
    (*STANDARD, "0.4", (566000.5, 566001.0, 243000.0, 243000.5)): (
        "standard_0.25m_4x4_q4.tif"
    ),
    (*HIGH, None, (566000.0, 566000.4, 243000.0, 243000.4)): "high_0.1m_4x4.tif",
    (*HIGH, None, (738960.0, 738960.4, 626588.0, 626588.4)): (
        "high_0.1m_4x4_nodata.tif"
    ),
}

# 1 x 1 m in Krakow: 4 x 4 px at 0.25 m (one recorded GetCoverage)
KRAKOW = BBox(566000, 243000, 566001, 243001, "EPSG:2180")
ARGS = {"horizontal_crs": "EPSG:2180", "coverage": "standard", "resolution": "0.25m"}
# The orthophotomap cutout of ``download_image_cutout``.
ORTO = {"product": "orto", **ARGS}
SEGMENT = "orto/pl_1992_standard_0.25m"


def _request(url: str) -> tuple:
    """(endpoint, COVERAGEID, SCALEFACTOR, SUBSET) of a GetCoverage URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert query["REQUEST"] == ["GetCoverage"]
    assert query["FORMAT"] == ["image/tiff"]
    subsets = query["SUBSET"]
    x = next(s for s in subsets if s.startswith("x("))[2:-1].split(",")
    y = next(s for s in subsets if s.startswith("y("))[2:-1].split(",")
    return (
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        query["COVERAGEID"][0],
        query.get("SCALEFACTOR", [None])[0],
        (float(x[0]), float(x[1]), float(y[0]), float(y[1])),
    )


def _session(answer=None) -> Mock:
    """``session.get`` replays the recorded answer of each recorded request;
    ``answer(url)`` replaces it (a failing server)."""
    session = Mock(spec=requests.Session)

    def respond(url, **kwargs):
        if answer is not None:
            return answer(url)
        return recorded_response(FIXTURES / RECORDED[_request(url)])

    session.get = Mock(side_effect=respond)
    return session


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text("utf-8"))


def _read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        return src.read(), {
            "size": (src.width, src.height),
            "transform": tuple(src.transform)[:6],
            "dtypes": src.dtypes,
            "epsg": src.crs.to_epsg(),
        }


def _quarters() -> np.ndarray:
    q = [_read(FIXTURES / f"standard_0.25m_4x4_q{i}.tif")[0] for i in (1, 2, 3, 4)]
    return np.concatenate(
        [np.concatenate(q[:2], axis=2), np.concatenate(q[2:], axis=2)], axis=1
    )


def _left_behind(root: Path) -> list[Path]:
    """Files of a failed download: versions, links, staging."""
    return [p for p in root.rglob("*") if p.is_file()]


# --- registry -------------------------------------------------------------


@pytest.mark.parametrize(
    ("variant", "fixture"),
    [("standard", "describe_standard.xml"), ("high", "describe_high.xml")],
)
def test_registry_channels_match_describe_coverage(variant, fixture):
    """The WCS channels carry what DescribeCoverage declares (id, step, CRS)."""
    ns = {
        "wcs": "http://www.opengis.net/wcs/2.0",
        "gml": "http://www.opengis.net/gml/3.2",
    }
    root = ET.parse(FIXTURES / fixture).getroot()
    coverage_id = root.findtext(".//wcs:CoverageId", namespaces=ns)
    steps = {
        abs(float(v))
        for vector in root.iterfind(".//gml:offsetVector", ns)
        for v in (vector.text or "").split()
        if float(v)
    }
    crs = {e.get("srsName") for e in root.iter() if e.get("srsName") is not None}
    (channel,) = [
        c
        for c in wcs_cutout_channels(ORTO_KEY)
        if isinstance(c.params, WcsCutoutParams) and c.params.variant == variant
    ]
    assert isinstance(channel.params, WcsCutoutParams)
    assert channel.params.coverage_id == coverage_id
    assert steps == {float(channel.params.native_step)}
    assert crs == {"http://www.opengis.net/def/crs/EPSG/0/2180"}
    assert channel.horizontal_crs == "EPSG:2180"
    assert channel.update_signal == "none"


# --- validation -------------------------------------------------------------


BASE = {
    "product": "orto",
    "bbox": KRAKOW,
    "country": "pl",
    "cutout": True,
    **ARGS,
}


@pytest.mark.parametrize(
    ("overrides", "fragments"),
    [
        (
            {"coverage": None},
            [
                "--coverage wymagane",
                "standard (najnowsze dostepne ortofotomapy)",
                "high (ortofotomapy o pikselu 10 cm i mniejszym)",
            ],
        ),
        ({"coverage": "medium"}, ["--coverage 'medium'", "standard", "high"]),
        ({"resolution": None}, ["--resolution wymagane", "0.1m, 0.25m, 0.5m, 1m"]),
        ({"resolution": "0.2m"}, ["--resolution '0.2m'", "0.1m, 0.25m, 0.5m, 1m"]),
        ({"horizontal_crs": None}, ["--horizontal-crs wymagane", "tylko EPSG:2180"]),
        (
            {"horizontal_crs": "EPSG:5514"},
            ["--horizontal-crs EPSG:5514", "tylko EPSG:2180 (bez przeprobkowania"],
        ),
        (
            {"bbox": None, "country": None, "sheet": "N-34-139-C-a-3-1"},
            ["--cutout dziala tylko z --bbox/--geometry"],
        ),
        ({"country": "cz"}, ["--cutout z --product orto", "tylko dla PL"]),
        ({"vertical_crs": "EVRF2007"}, ["--vertical-crs nie dotyczy --product orto"]),
        ({"year": 2024}, ["--year nie dziala z --cutout"]),
        (
            {"cutout": False, "horizontal_crs": None, "resolution": None},
            ["--coverage dziala tylko z --cutout --product orto"],
        ),
        (
            {"product": "nmt", "vertical_crs": "EVRF2007", "resolution": "1m"},
            ["--coverage dziala tylko z --cutout --product orto"],
        ),
        (
            {"cutout": False, "horizontal_crs": None, "coverage": None},
            ["--resolution z --product orto dotyczy tylko wycinka (--cutout)"],
        ),
    ],
)
def test_orto_cutout_requires_variant(tmp_path, overrides, fragments):
    """Every rule of the orto cutout fails before any request or write."""
    selection = {"output_dir": tmp_path / "data", **BASE, **overrides}
    with (
        patch(SESSION_FACTORY) as factory,
        pytest.raises(ValidationError) as exc,
    ):
        validate_data_request(**selection)
    for fragment in fragments:
        assert fragment in str(exc.value)
    factory.assert_not_called()
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"horizontal_crs": "EPSG:5514"}, "tylko EPSG:2180"),
        ({"coverage": "medium"}, "--coverage 'medium'"),
        ({"resolution": "25cm"}, "0.1m, 0.25m, 0.5m, 1m"),
    ],
)
def test_download_image_cutout_rejects_choice_before_network(
    tmp_path, overrides, fragment
):
    with (
        patch(SESSION_FACTORY) as factory,
        pytest.raises(ValidationError, match=fragment),
    ):
        download_image_cutout(
            KRAKOW, output_dir=tmp_path, cache=False, **{**ORTO, **overrides}
        )
    factory.assert_not_called()
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"resolution": "0.25m"},  # a cutout pixel without a coverage
        {"coverage": "high", "resolution": "0.25m", "color": "CIR"},
    ],
)
def test_provider_cutout_choice_errors(kwargs):
    with pytest.raises(ValidationError):
        GugikOrtoProvider(**{"color": "RGB", **kwargs})


def test_provider_cutout_is_geotiff_only(tmp_path):
    provider = GugikOrtoProvider(
        session=_session(), color="RGB", coverage="standard", resolution="0.25m"
    )
    with pytest.raises(ValidationError, match="GTiff"):
        provider.download_bbox(KRAKOW, tmp_path / "a.png", format="PNG")


# --- store ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "bbox", "fixture", "source"),
    [
        (
            ARGS,
            KRAKOW,
            "standard_0.25m_4x4.tif",
            {
                "service": "WCS",
                "endpoint": STANDARD[0],
                "coverage": STANDARD[1],
                "format": "image/tiff",
                "scalefactor": 0.4,
                "composition": "server",
            },
        ),
        (
            {**ARGS, "coverage": "high", "resolution": "0.1m"},
            BBox(566000, 243000, 566000.4, 243000.4, "EPSG:2180"),
            "high_0.1m_4x4.tif",
            {
                "service": "WCS",
                "endpoint": HIGH[0],
                "coverage": HIGH[1],
                "format": "image/tiff",
                "composition": "server",
            },
        ),
    ],
)
def test_orto_cutout_slot_and_sidecar(tmp_path, args, bbox, fixture, source):
    session = _session()
    with patch(SESSION_FACTORY, return_value=session):
        result = download_image_cutout(
            bbox, product="orto", output_dir=tmp_path, cache=False, **args
        )

    coords = "_".join(
        format(v, ".10g") for v in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    )
    segment = f"orto/pl_1992_{args['coverage']}_{args['resolution']}"
    assert result.file.path == tmp_path / segment / "bbox" / f"{coords}.tif"
    assert result.file.status == "new"
    assert result.notices == ()
    # one chunk: the server's GeoTIFF is the version, byte for byte
    assert result.file.path.read_bytes() == (FIXTURES / fixture).read_bytes()
    (call,) = session.get.call_args_list
    assert call.kwargs["timeout"] == 300
    meta = _meta(result.file.path)
    assert meta["dataset"] == "pl.gugik.orto"
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:2180", None)
    assert meta["request"] == {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "bbox_crs": "EPSG:2180",
        "coverage": args["coverage"],
        "resolution": args["resolution"],
    }
    assert meta["extra"]["source"] == source
    assert "parent_request" not in meta["extra"]
    assert meta["extra"]["version"]["label_source"] == "downloaded"


def test_orto_cutout_grid_and_chunks(tmp_path):
    """An off-grid request widens to whole 0.25 m pixels; above the budget it
    is fetched in chunks copied 1:1 (each chunk a recorded server answer)."""
    session = _session()
    provider = GugikOrtoProvider(
        session=session, color="RGB", coverage="standard", resolution="0.25m"
    )
    # budget of 25 coverage pixels = 2 x 2 px of 0.25 m per request
    provider.WCS_CHUNK_LIMITS = ChunkLimits(
        max_width=40_000, max_height=40_000, max_pixels=25
    )
    seen: list[object] = []
    session.get.side_effect = lambda url, **kw: (
        seen.append(_request(url)[3]),
        recorded_response(FIXTURES / RECORDED[_request(url)]),
    )[1]
    request = BBox(566000.1, 243000.05, 566000.9, 243000.95, "EPSG:2180")
    with patch(PROVIDER_FACTORY, return_value=provider):
        result = download_image_cutout(
            request,
            output_dir=tmp_path,
            cache=False,
            on_notice=seen.append,
            **ORTO,
        )

    assert result.file.path.name == "566000_243000_566001_243001.tif"
    notice, *subsets = seen
    assert isinstance(notice, Notice) and notice.code == CUTOUT_SIZE
    assert "4 x 4 px" in notice.text and "4 zapytan" in notice.text
    assert subsets == [  # N->S, W->E: q1, q2, q3, q4
        (566000.0, 566000.5, 243000.5, 243001.0),
        (566000.5, 566001.0, 243000.5, 243001.0),
        (566000.0, 566000.5, 243000.0, 243000.5),
        (566000.5, 566001.0, 243000.0, 243000.5),
    ]
    data, info = _read(result.file.path)
    assert info["size"] == (4, 4)
    assert info["transform"] == (0.25, 0.0, 566000.0, 0.0, -0.25, 243001.0)
    assert info["dtypes"] == ("uint8", "uint8", "uint8")
    assert info["epsg"] == 2180
    np.testing.assert_array_equal(data, _quarters())


@pytest.mark.parametrize(
    ("resolution", "per_pixel"), [("0.1m", 1), ("0.25m", 6.25), ("1m", 100)]
)
def test_chunks_within_native_budget(resolution, per_pixel):
    """Chunks of a 500 x 500 m area: <= 4 Mpx of 0.1 m coverage each, even
    sizes on the result grid, together exactly the aligned area."""
    provider = GugikOrtoProvider(
        color="RGB", coverage="standard", resolution=resolution
    )
    step = float(Decimal(resolution[:-1]))
    chunks = provider.plan_wcs_chunks(
        BBox(566000.01, 243000.01, 566499.99, 243499.99, "EPSG:2180")
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.width * chunk.height * per_pixel <= 4_000_000
        assert chunk.width % 2 == 0 and chunk.height % 2 == 0
        for edge in (chunk.bbox.min_x, chunk.bbox.max_x, chunk.bbox.min_y):
            assert edge / step == pytest.approx(round(edge / step), abs=1e-6)
    assert min(c.bbox.min_x for c in chunks) == 566000.0
    assert max(c.bbox.max_x for c in chunks) == pytest.approx(566500.0)
    assert min(c.bbox.min_y for c in chunks) == pytest.approx(243000.0)
    assert max(c.bbox.max_y for c in chunks) == 243500.0
    area = sum(c.width * c.height for c in chunks) * step**2
    assert area == pytest.approx(500 * 500)


def _exception(url):
    return recorded_response(FIXTURES / "exception_extent.xml")


def _exception_with_200(url):
    """The same ExceptionReport served with HTTP 200 (OGC services may)."""
    response = recorded_response(FIXTURES / "exception_extent.xml")
    response.status_code = 200
    response.raise_for_status = Mock()
    return response


def _wrong_grid(url):
    """A real server GeoTIFF on another grid (odd 0.25 m request, README)."""
    return recorded_response(FIXTURES / "standard_0.25m_odd_3x3.tif")


@pytest.mark.parametrize("answer", [_exception, _exception_with_200, _wrong_grid])
def test_orto_cutout_exception_report_is_download_error(tmp_path, answer):
    session = _session(answer)
    with (
        patch(SESSION_FACTORY, return_value=session),
        pytest.raises(DownloadError),
    ):
        download_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    assert _left_behind(tmp_path) == []
    plan = check_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    assert plan.items[0].status == "missing"


def test_orto_cutout_local_reuse_and_force_unchanged(tmp_path):
    first_session = _session()
    with patch(SESSION_FACTORY, return_value=first_session):
        first = download_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    with patch(SESSION_FACTORY) as factory:
        local = download_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    forced_session = _session()
    with patch(SESSION_FACTORY, return_value=forced_session):
        forced = download_image_cutout(
            KRAKOW, output_dir=tmp_path, cache=False, update="force", **ORTO
        )

    assert first.file.status == "new"
    assert (local.file.status, local.file.unverified) == ("local", "none")
    factory.assert_not_called()
    assert forced.file.status == "unchanged"
    assert forced_session.get.call_count == 1
    assert local.file.sha256 == forced.file.sha256 == first.file.sha256
    assert forced.file.version_path == first.file.version_path


def test_check_image_cutout_unverifiable(tmp_path):
    with patch(SESSION_FACTORY) as factory:
        before = check_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    factory.assert_not_called()
    with patch(SESSION_FACTORY, return_value=_session()):
        result = download_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    with patch(SESSION_FACTORY) as factory:
        after = check_image_cutout(KRAKOW, output_dir=tmp_path, cache=False, **ORTO)
    factory.assert_not_called()

    (missing,) = before.items
    (item,) = after.items
    assert (missing.track, missing.segment, missing.status) == (
        "pl_cutout",
        SEGMENT,
        "missing",
    )
    assert missing.unit == item.unit == result.file.path.stem
    assert item.status == "unverifiable"
    assert item.local_sha256 == result.file.sha256


def test_orto_cutout_all_black_is_kept_with_warning(tmp_path):
    """High outside its 10 cm areas answers 0,0,0: a version with a warning."""
    bbox = BBox(738960, 626588, 738960.4, 626588.4, "EPSG:2180")
    args = {**ORTO, "coverage": "high", "resolution": "0.1m"}
    seen: list[Notice] = []
    with patch(SESSION_FACTORY, return_value=_session()):
        result = download_image_cutout(
            bbox, output_dir=tmp_path, cache=False, on_notice=seen.append, **args
        )
    with patch(SESSION_FACTORY) as factory:
        local = download_image_cutout(bbox, output_dir=tmp_path, cache=False, **args)

    assert result.file.status == "new"
    assert [(n.level, n.code) for n in seen] == [("warning", ALL_NODATA)]
    assert result.notices == tuple(seen)
    assert _meta(result.file.path)["extra"]["all_nodata"] is True
    assert local.file.status == "local" and local.notices == ()
    factory.assert_not_called()


# --- download_data ----------------------------------------------------------


@pytest.mark.parametrize("area", ["bbox", "geometry"])
def test_download_data_routes_orto_cutout(tmp_path, area):
    selection: dict = {"product": "orto", "country": "pl", "cutout": True, **ARGS}
    patches = []
    if area == "bbox":
        selection["bbox"] = KRAKOW
    else:
        from pyproj import CRS

        selection["geometry"] = write_gpkg_layers(tmp_path / "area.gpkg", ["area"])
        patches = [
            patch(
                "kartograf.core.geometry.read_source_crs",
                return_value=CRS.from_epsg(2180),
            ),
            patch("kartograf.core.geometry.get_overall_bbox", return_value=KRAKOW),
        ]
    output = tmp_path / "data"
    for p in patches:
        p.start()
    try:
        with patch(SESSION_FACTORY, return_value=_session()):
            report = download_data(output_dir=output, cache=False, **selection)
        plan = check_data(output_dir=output, cache=False, **selection)
    finally:
        for p in patches:
            p.stop()

    assert report.ok and report.failed == ()
    (unit_file,) = report.files
    assert unit_file.country == "PL"
    assert unit_file.unit == f"{SEGMENT}/bbox/566000_243000_566001_243001.tif"
    assert _meta(unit_file.file.path)["extra"]["parent_request"]["countries"] == ["PL"]
    (item,) = plan.items
    assert (item.segment, item.status) == (SEGMENT, "unverifiable")


def test_download_data_orto_cutout_source_error_is_country_failure(tmp_path):
    with patch(SESSION_FACTORY, return_value=_session(_exception)):
        report = download_data(
            product="orto",
            output_dir=tmp_path,
            bbox=KRAKOW,
            country="pl",
            cutout=True,
            cache=False,
            **ARGS,
        )
    assert not report.ok and report.files == ()
    (failure,) = report.failed
    assert (failure.country, failure.kind) == ("PL", "download")
    assert "ExtentError" in failure.error or "400" in failure.error


def test_auto_narrows_orto_cutout_to_pl(tmp_path):
    """A border area with ``coverage`` goes to PL only (ADR-023 point 5)."""
    seen: list[Notice] = []
    plan = check_data(
        product="orto",
        output_dir=tmp_path,
        bbox=BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326"),
        country="auto",
        cutout=True,
        cache=False,
        on_notice=seen.append,
        **ARGS,
    )
    (narrowed,) = [n for n in seen if n.code == AUTO_NARROWED_TO_PL]
    assert "--coverage standard" in narrowed.text
    assert [item.segment for item in plan.items] == [SEGMENT]


def test_orto_cutout_choices_stay_pl_only_with_a_cz_orthophoto():
    """``coverage`` and the cutout ``resolution`` narrow ``auto`` to PL even
    when CZ has an orthophotomap source of its own."""
    cz_orto = SimpleNamespace(resolution=None, key="cz.example.orto")
    with patch(
        "kartograf.sources.registry.sources_for",
        side_effect=lambda country=None, product=None: (
            [cz_orto] if (country, product) == ("CZ", "orto") else []
        ),
    ):
        flags = pl_only_flags("orto", None, "0.25m", None, "standard")
    assert "--product orto" not in flags
    assert "--resolution 0.25m" in flags and "--coverage standard" in flags
