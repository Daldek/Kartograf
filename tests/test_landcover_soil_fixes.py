"""Regression tests of the E2E 0.8.0 findings of ``landcover`` and ``soil`` (C P2-1..4,
P2-6, P2-7, P3-04, P3-06..08, P3-10, P3-24): the WMS layer of a CORINE year, a
blank preview, the SoilGrids layers and units, the exact HSG triangle, the
BDOT10k classes and the volume limit of a BDOT10k area."""

import json
import shlex
import struct
import zlib
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import numpy as np
import pytest

from kartograf import download_landcover, download_soil
from kartograf.auth.proxy import CLMSCredentials
from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.hydrology.hsg import _classify_hsg, classify_usda_texture_array
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import NoticeSink
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import (
    Bdot10kPackage,
    Bdot10kProvider,
    normalize_layers,
)
from kartograf.providers.soilgrids import (
    SoilGridsProvider,
    _at_least_one_pixel,
    is_empty,
    units_for,
)
from tests.conftest import FakeSoilGrids
from tests.test_landcover import _bdot_zip, _zip_session
from tests.test_parity_landcover import _providers

ROOT = Path(__file__).resolve().parent.parent
AREA = BBox(450000, 550000, 452000, 552000, "EPSG:2180")


# --- CORINE (P2-1, P2-2, P3-04) ---------------------------------------------


def _capabilities(layers: list[tuple[str | None, str]]) -> bytes:
    body = "".join(
        f"<Layer>{f'<Name>{n}</Name>' if n else ''}<Title>{t}</Title></Layer>"
        for n, t in layers
    )
    return (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability><Layer>'
        f"<Title>CLC</Title>{body}</Layer></Capability></WMS_Capabilities>"
    ).encode()


def _png(visible: bool) -> bytes:
    """A 2 x 2 RGBA PNG, every pixel opaque (``visible``) or fully transparent."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes([200, 30, 30, 255 if visible else 0] * 2)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * 2))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(
    ("year", "name"),
    [
        (2018, "12"),
        (2012, "Corine_Land_Cover_2012_raster59601"),
        (2006, "Corine_Land_Cover_2006_raster43084"),
        (2000, "Corine_Land_Cover_2000_raster11306"),
    ],
)
def test_eea_raster_layer_is_read_from_the_capabilities_of_the_year(year, name):
    """Only CLC2018 names its raster layer ``12``: the others carry a number that
    changes, so the layer is found by its title and read once per provider."""
    provider = CorineProvider(use_proxy=False)
    answer = _capabilities(
        [
            (None, f"Corine Land Cover {year} DOMs raster"),
            (f"U2018_CLC{year}_V2020_20u1_FR_GLP_R_WM", "U2018_FR_GLP_R_WM"),
            (name, f"Corine Land Cover {year} raster"),
            ("13", f"Corine Land Cover {year} vector"),
        ]
    )
    with patch(
        "kartograf.providers.corine.get_with_retry",
        return_value=SimpleNamespace(content=answer),
    ) as get:
        assert provider._eea_raster_layer(year, 30) == name
        assert provider._eea_raster_layer(year, 30) == name
    assert get.call_count == 1
    assert f"CLC{year}_WM" in get.call_args.args[1]


def test_eea_service_without_the_raster_layer_is_a_readable_error():
    provider = CorineProvider(use_proxy=False)
    answer = _capabilities([("5", "Corine Land Cover 2012 vector")])
    with (
        patch(
            "kartograf.providers.corine.get_with_retry",
            return_value=SimpleNamespace(content=answer),
        ),
        pytest.raises(DownloadError) as error,
    ):
        provider._eea_raster_layer(2012, 30)
    assert "nie ma warstwy rastrowej" in str(error.value)
    assert "WMS returned" not in str(error.value)


def _serve_png(visible: bool, urls: list[str]):
    def download_to(session, url, path, **kwargs):
        urls.append(url)
        Path(path).write_bytes(_png(visible))
        return Path(path)

    return patch("kartograf.providers.corine.download_to", download_to)


def test_getmap_asks_the_layer_of_the_year(tmp_path):
    provider = CorineProvider(use_proxy=False)
    provider._wms_layers[2012] = "Corine_Land_Cover_2012_raster59601"
    urls: list[str] = []
    with _serve_png(True, urls):
        path = provider._download_via_wms(AREA, tmp_path / "x.png", 2012, 30)
    assert path.is_file()
    assert "LAYERS=Corine_Land_Cover_2012_raster59601" in urls[0]


@pytest.mark.parametrize("year", [1990, 2018])
def test_fully_transparent_preview_is_no_coverage_and_leaves_no_file(tmp_path, year):
    """The service has no CLC data of the area: no image, no version."""
    provider = CorineProvider(use_proxy=False)
    provider._wms_layers[2018] = "12"
    with _serve_png(False, []), pytest.raises(NoCoverageError) as error:
        provider._download_via_wms(AREA, tmp_path / "x.png", year, 30)
    assert "w calosci przezroczysty" in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_corine_year_error_lists_the_years_with_the_flag():
    with pytest.raises(ValidationError) as error:
        CorineProvider.check_year(2019)
    assert str(error.value) == (
        "--year 2019: niedostepne dla --product corine; dostepne: 2018, 2012, "
        "2006, 2000, 1990"
    )
    assert error.value.option == "year"


# --- CLMS_CREDENTIALS (P3-08) -----------------------------------------------


def test_unusable_clms_credentials_are_a_warning_naming_the_reason(tmp_path):
    manager = LandCoverManager(tmp_path, CorineProvider(use_proxy=False))
    for year, level in ((2018, "warning"), (1990, "info")):
        sink = NoticeSink(None)
        with patch.object(
            CorineProvider,
            "clms_credentials_problem",
            new_callable=PropertyMock,
            return_value="CLMS_CREDENTIALS nie jest poprawnym JSON (x)",
        ):
            manager._corine_preview({"year": year}, sink)
        (notice,) = sink.notices
        assert (notice.level, notice.code) == (level, "corine_preview")
        assert ("nie jest poprawnym JSON" in notice.text) == (level == "warning")


def test_proxy_names_why_the_variable_is_unusable(monkeypatch):
    monkeypatch.setenv("CLMS_CREDENTIALS", "not json at all")
    credentials = CLMSCredentials()
    assert credentials.is_available is False
    assert credentials.env_error is not None
    assert "nie jest poprawnym JSON" in credentials.env_error
    assert "not json" not in credentials.env_error  # never the value
    monkeypatch.setenv("CLMS_CREDENTIALS", "{}")
    assert "client_id i private_key" in (CLMSCredentials().env_error or "") or (
        CLMSCredentials().is_available is False
    )


# --- SoilGrids (P2-3, P2-4, P3-06, P3-07) -----------------------------------


def test_ocs_is_published_at_0_30cm_only():
    check = SoilGridsProvider.check_layer
    check("ocs", "0-30cm", "mean")
    check("clay", "0-5cm", "mean")
    with pytest.raises(ValidationError) as error:
        check("ocs", "0-5cm", "mean")
    assert error.value.option == "depth" and error.value.allowed == ("0-30cm",)
    with pytest.raises(ValidationError):
        check("clay", "0-30cm", "mean")
    # the layers the service lists: 10 properties x 6 depths x 5 statistics + ocs
    assert len(SoilGridsProvider.layers()) == 10 * 6 * 5 + 5


def test_ocd_edition_comes_from_the_clay_map_its_title_has_none():
    maps = {
        "ocd": "Soilgrids property: Organic carbon density",
        "clay": "SoilGrids250m 2.0 - Clay content",
    }

    def get(session, url, **kwargs):
        title = next(t for p, t in maps.items() if f"/{p}.map" in url)
        return SimpleNamespace(
            content=(
                '<c xmlns:ows="http://www.opengis.net/ows/2.0"><ows:ServiceIdentification>'
                f"<ows:Title>{title}</ows:Title></ows:ServiceIdentification></c>"
            ).encode()
        )

    provider = SoilGridsProvider()
    with patch("kartograf.providers.soilgrids.get_with_retry", get):
        edition = provider.edition("ocd")
        assert edition.id == "2.0" and "/clay.map" in edition.url
        assert provider.edition("clay").id == "2.0"
        maps["clay"] = "Soilgrids property: Clay"
        with pytest.raises(DownloadError, match="brak wydania"):
            provider.edition("ocd")


def test_values_of_a_file_are_converted_with_the_isric_units():
    assert units_for("clay", "mean").to_extra() == {
        "mapped": "g/kg",
        "conventional": "%",
        "divisor": 10,
    }
    assert units_for("bdod", "Q0.5").divisor == 100
    assert units_for("phh2o", "mean").mapped == "pH x 10"
    # the statistic changes the unit: a ratio, whatever the property
    assert units_for("bdod", "uncertainty") == units_for("clay", "uncertainty")


def test_window_under_a_pixel_is_widened_not_refused(tmp_path):
    assert _at_least_one_pixel((19.5, 52.0, 19.5001, 52.0001)) == pytest.approx(
        (
            19.5 + 0.00005 - 0.001125,
            52.0 + 0.00005 - 0.001125,
            19.5 + 0.00005 + 0.001125,
            52.0 + 0.00005 + 0.001125,
        ),
    )
    big = (19.5, 52.0, 19.6, 52.1)
    assert _at_least_one_pixel(big) == big
    urls: list[str] = []

    def download_to(session, url, path, **kwargs):
        urls.append(url)
        return Path(path)

    tiny = BBox(500000, 500000, 500010, 500010, "EPSG:2180")
    with patch("kartograf.providers.soilgrids.download_to", download_to):
        SoilGridsProvider().download_by_bbox(
            tiny, tmp_path / "a.tif", property="clay", depth="0-5cm", stat="mean"
        )
    lon = url_span(urls[0], "long")
    lat = url_span(urls[0], "lat")
    assert lon >= 0.00225 - 1e-9 and lat >= 0.00225 - 1e-9


def url_span(url: str, axis: str) -> float:
    low, high = url.split(f"SUBSET={axis}(")[1].split(")")[0].split(",")
    return float(high) - float(low)


def _zeros(tmp_path, value):
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "r.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=from_origin(19.0, 50.0, 0.01, 0.01),
    ) as dst:
        dst.write(np.full((1, 2, 2), value, dtype="int16"))
    return path


def test_all_zero_raster_is_empty_except_for_cfvo(tmp_path):
    zeros, data = _zeros(tmp_path, 0), _zeros(tmp_path / "..", 7)
    assert is_empty(zeros, "clay") and not is_empty(data, "clay")
    assert not is_empty(zeros, "cfvo")  # 0 is a value of the coarse fragments
    assert not is_empty(tmp_path / "missing.tif", "clay")


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize("value", [0, 87])
def test_soil_sidecar_has_the_units_and_an_empty_raster_is_reported(tmp_path, value):
    notices = []
    with _providers(
        soilgrids=lambda: SoilGridsProvider(
            session=FakeSoilGrids(values={"clay": value})
        )
    ):
        report = download_soil(
            output_dir=tmp_path / "store",
            bbox=AREA,
            property="clay",
            depth="0-5cm",
            stat="mean",
            cache=False,
            on_notice=notices.append,
        )
    assert report.ok, report.failed
    path = report.files[0].file.path
    extra = json.loads(Path(f"{path}.meta.json").read_text())["extra"]
    assert extra["units"] == {"mapped": "g/kg", "conventional": "%", "divisor": 10}
    empty = [n for n in notices if n.code == "all_nodata"]
    assert bool(empty) == (value == 0) == (extra.get("all_nodata") is True)
    if empty:
        assert empty[0].level == "warning"


# --- HSG (P3-10) ------------------------------------------------------------


def _oracle(clay: int, sand: int, silt: int) -> int:
    """USDA triangle on exact fractions, the rules written out independently."""
    total = Fraction(clay + sand + silt)
    c, s, si = (Fraction(100 * v) / total for v in (clay, sand, silt))
    half = Fraction(3, 2)
    rules = [
        (1, si + half * c < 15),
        (2, (si + half * c >= 15) and (si + 2 * c < 30)),
        (
            3,
            (7 <= c <= 20 and s > 52 and si + 2 * c >= 30)
            or (c < 7 and si < 50 and si + 2 * c >= 30),
        ),
        (6, si >= 80 and c < 12),
        (5, (si >= 50 and 12 <= c < 27) or (50 <= si < 80 and c < 12)),
        (4, 7 <= c <= 27 and 28 <= si < 50 and s <= 52),
        (7, 20 <= c < 35 and si < 28 and s > 45),
        (8, 27 <= c < 40 and 20 < s <= 45),
        (9, 27 <= c < 40 and s <= 20),
        (10, c >= 35 and s > 45),
        (11, c >= 40 and si >= 40),
        (12, c >= 40 and s <= 45 and si < 40),
    ]
    return next((code for code, hit in rules if hit), 4)


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
def test_values_on_a_triangle_boundary_are_classified_by_the_rule(dtype):
    """g/kg on the boundaries (silt + 2 clay = 300, clay = 270, clay = 400...) were
    decided by float32 rounding; every integer triple now follows the rules."""
    triples = [
        (clay, 1000 - clay - silt, silt)
        for clay in range(0, 460, 10)
        for silt in range(0, 1001 - clay, 10)
    ]
    clay, sand, silt = (np.array(v, dtype=dtype) for v in zip(*triples, strict=True))
    got = classify_usda_texture_array(clay, sand, silt)
    expected = [_oracle(*triple) for triple in triples]
    assert got.tolist() == expected
    hsg = _classify_hsg(clay, sand, silt, (None, None, None))
    assert (hsg > 0).all()  # no triple of these is a gap


# --- BDOT10k (P2-6, P2-7, P3-24) --------------------------------------------


def test_layers_name_only_classes_of_the_classification_and_no_blank_code():
    assert normalize_layers(["ptwp", "BUBD"]) == ["BUBD", "PTWP"]
    with pytest.raises(ValidationError) as unknown:
        normalize_layers(["PTWP", "XXXX"])
    assert unknown.value.option == "layers"
    assert "--layers XXXX: brak takich klas w BDOT10k" in str(unknown.value)
    with pytest.raises(ValidationError, match="pusty kod warstwy"):
        normalize_layers(["SWRS", ""])


def test_class_absent_from_a_powiat_package_is_reported_not_an_error(tmp_path):
    body = _bdot_zip(tmp_path, ["OT_PTWP_A", "OT_PTLZ_A"])
    provider = Bdot10kProvider(session=_zip_session(body))
    package = provider.download_package(
        "0262", tmp_path / "o" / "x.gpkg", layers=["PTWP", "SWKN"]
    )
    assert package.classes == ("PTWP",) and package.absent == ("SWKN",)
    with pytest.raises(NoCoverageError, match="nie ma plikow klas SWKN"):
        provider.download_package("0262", tmp_path / "p" / "x.gpkg", layers=["SWKN"])


def test_absent_class_of_a_powiat_is_an_info_and_the_others_are_saved(tmp_path):
    def package(code, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x")
        return Bdot10kPackage(
            path=output_path,
            teryt=code,
            url="u",
            format="GPKG",
            classes=("PTWP",),
            absent=("SWKN",),
        )

    notices = []
    with patch.object(Bdot10kProvider, "download_package", side_effect=package):
        report = download_landcover(
            product="bdot10k",
            output_dir=tmp_path,
            teryt="2264",
            layers=["SWKN", "PTWP"],
            cache=False,
            on_notice=notices.append,
        )
    assert report.ok and not report.failed
    (info,) = [n for n in notices if n.code == "classes_absent"]
    assert info.level == "info"
    assert "paczka nie ma plikow klas SWKN" in info.text
    assert "zapisano klasy PTWP" in info.text
    meta = json.loads(Path(f"{report.files[0].file.path}.meta.json").read_text())
    assert meta["request"]["layers"] == ["PTWP", "SWKN"]
    assert meta["extra"]["source"]["classes"] == ["PTWP"]


def test_bdot10k_area_over_the_volume_limit_is_refused_before_any_download(tmp_path):
    """The whole of Poland is 378 powiats and 18 GB: the same limit as the
    collections (100 files, 10 GB), checked by HEAD before the first transfer."""
    teryts = [f"02{i:02d}" for i in range(1, 61)] + [f"04{i:02d}" for i in range(1, 42)]
    notices = []
    with (
        patch.object(Bdot10kProvider, "teryts_for_area", return_value=teryts),
        patch("kartograf.download.collections._head_length", return_value=48_000_000),
        patch.object(
            Bdot10kProvider, "download_package", side_effect=AssertionError("download")
        ),
        pytest.raises(ValidationError) as refused,
    ):
        download_landcover(
            product="bdot10k",
            output_dir=tmp_path,
            bbox=BBox(100000, 100000, 800000, 800000, "EPSG:2180"),
            cache=False,
            on_notice=notices.append,
        )
    assert str(refused.value).startswith("bdot10k: obszar daje 101 plikow do pobrania")
    assert "wybierz jednostke (--teryt <4 cyfry>)" in str(refused.value)
    (listed,) = [n for n in notices if n.code == "unit_list"]
    assert "bdot10k: powiaty obszaru wg PRG (101): 0201, 0202" in listed.text
    assert listed.text.endswith("i 91 innych")
    assert not list(tmp_path.rglob("*.gpkg"))


def test_bdot10k_area_within_the_limit_downloads_every_powiat(tmp_path):
    def package(code, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x")
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    with (
        patch.object(Bdot10kProvider, "teryts_for_area", return_value=["0208", "0224"]),
        patch("kartograf.download.collections._head_length", return_value=48_000_000),
        patch.object(Bdot10kProvider, "download_package", side_effect=package),
    ):
        report = download_landcover(
            product="bdot10k",
            output_dir=tmp_path,
            bbox=AREA,
            cache=False,
        )
    assert report.ok and [f.unit for f in report.files] == ["0208", "0224"]


# --- llms.txt (P3-01) -------------------------------------------------------


def test_offline_query_commands_of_llms_txt_run():
    """The first file an agent reads: its commands without network exit 0 (the
    ``list-layers`` of landcover needs ``--product``)."""
    lines = [
        line
        for line in (ROOT / "llms.txt").read_text().splitlines()
        if line.startswith("kartograf ")
        and (" list-layers" in line or " list-sources" in line)
    ]
    assert any("landcover list-layers" in line for line in lines)
    for line in lines:
        assert main(shlex.split(line)[1:]) == 0, line
