"""Testy CuzkDmrProvider — dispatch SM5/TM33/bbox, CRS, transformacja pionowa.

Wartosci arkusza CTES96 (MAPNAME, PODIL, bbox) pochodza z fixtury rekonesansu
`tests/fixtures/cuzk/klady_sm5_where_ctes96.json` — "Cesky Tesin 9-6",
PODIL 0.99, zasieg (-450000, -1114000, -447500, -1112000) w EPSG:5514.

Testy sa offline: CuzkClient i SheetIndex sa mockowane, a pliki GeoTIFF
powstaja lokalnie przez rasterio (wzor: test_cuzk_client.py).
"""

import warnings
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.cuzk import create_dmr_provider
from kartograf.providers.cuzk.dmr import CUZK_NODATA, CuzkDmrProvider
from kartograf.providers.cuzk.sheets import SheetInfo
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source
from kartograf.transform.crs import TransformUnavailableError

_CLIENT_PATCH = "kartograf.providers.cuzk.dmr.CuzkClient"
_INDEX_PATCH = "kartograf.providers.cuzk.dmr.SheetIndex"
_PINNED_PATCH = "kartograf.providers.cuzk.dmr.build_pinned_transform"
_SOURCE_PATCH = "kartograf.providers.cuzk.dmr.get_source"


def _write_tif(
    path: Path,
    *,
    crs,
    bounds=(0, 0, 20, 20),
    size=(10, 10),
    value=100.0,
    nodata=CUZK_NODATA,
):
    transform = from_bounds(*bounds, size[0], size[1])
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": size[0],
        "height": size[1],
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    data = np.full((size[1], size[0]), value, dtype="float32")
    data[0, 0] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def _write_dmr4g_pair(path: Path):
    """Realny ksztalt pliku z openzu: GeoTIFF bez CRS i bez geotransformacji,
    georeferencja wylacznie w .tfw (rekonesans Zad. 1, krok 6)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NotGeoreferencedWarning — celowe
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            dtype="float32",
            count=1,
            width=5,
            height=4,
            nodata=CUZK_NODATA,
        ) as dst:
            dst.write(np.full((4, 5), 300.0, dtype="float32"), 1)
    # 500 m/px, srodek lewego-gornego piksela — zasieg CTES96
    path.with_suffix(".tfw").write_text(
        "500.0\n0.0\n0.0\n-500.0\n-449750.0\n-1112250.0\n"
    )


def _exporting(crs):
    """side_effect dla export_image: zapisz maly GeoTIFF w zadanym CRS."""

    def _fake(endpoint, bbox, **kwargs):
        output_path = Path(kwargs["output_path"])
        _write_tif(output_path, crs=crs)
        return output_path

    return _fake


def _ctes96_info():
    return SheetInfo(
        godlo="CTES96",
        name="Český Těšín 9-6",
        bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
        podil=0.99,
        in_cz=None,
    )


class TestConstruction:
    def test_resolution_selects_descriptor(self):
        assert CuzkDmrProvider(resolution="2m").descriptor_key == "cz.cuzk.dmr5g"
        assert CuzkDmrProvider(resolution="5m").descriptor_key == "cz.cuzk.dmr4g"

    def test_default_extension(self):
        assert CuzkDmrProvider().default_extension == ".tif"

    def test_invalid_resolution_rejected_by_factory(self):
        with pytest.raises(ValidationError, match="2m, 5m"):
            create_dmr_provider(resolution="1m")

    def test_invalid_resolution_rejected_by_constructor(self):
        with pytest.raises(ValidationError, match="2m, 5m"):
            CuzkDmrProvider(resolution="1m")

    def test_kron86_raises_with_remedy(self):
        with pytest.raises(TransformUnavailableError) as exc:
            CuzkDmrProvider(vertical_crs="KRON86")
        assert exc.value.remedy  # remedium z REMEDIES (siatki niepubliczne)

    def test_unknown_vertical_rejected(self):
        with pytest.raises(ValidationError):
            CuzkDmrProvider(vertical_crs="NAP")

    def test_endpoints_come_from_descriptor(self):
        provider = CuzkDmrProvider(resolution="2m")
        channel = get_source("cz.cuzk.dmr5g").channels[0]
        assert provider.base_url == channel.endpoint

    def test_missing_image_channel_is_config_error(self):
        descriptor = get_source("cz.cuzk.dmr5g")
        without_image = replace(descriptor, channels=())
        with (
            patch(_SOURCE_PATCH, return_value=without_image),
            pytest.raises(ValidationError, match="ARCGIS_IMAGE"),
        ):
            CuzkDmrProvider(resolution="2m")

    def test_metadata_properties(self):
        """Warstwa CLI (Zad. 15) czyta te wlasciwosci przy budowie sidecara."""
        provider = CuzkDmrProvider(resolution="5m", vertical_crs="Bpv")
        assert provider.name == "CUZK DMR (5m)"
        assert provider.resolution == "5m"
        assert provider.vertical_crs == "Bpv"
        assert provider.sheet_index is provider.sheet_index  # jeden indeks


class TestDownloadDispatch:
    def test_tm33_godlo_exports_native_3045(self, tmp_path):
        target = tmp_path / "302_5550.tif"
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:3045")
            provider = CuzkDmrProvider(resolution="2m")
            result = provider.download("302_5550", target)

        assert result == target
        kwargs = client.export_image.call_args.kwargs
        assert kwargs["pixel_size"] == 2.0
        assert kwargs["image_sr"] == "EPSG:3045"
        assert kwargs["no_data"] == CUZK_NODATA
        called_endpoint, called_bbox = client.export_image.call_args.args[:2]
        assert called_endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
        )
        assert called_bbox == BBox(302000, 5550000, 304000, 5552000, "EPSG:3045")

    def test_sm5_godlo_validates_fetches_and_repairs_crs(self, tmp_path):
        target = tmp_path / "CTES96.tif"
        with patch(_CLIENT_PATCH) as client_cls, patch(_INDEX_PATCH) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()
            client = client_cls.return_value

            def fake_fetch(url, output_path, *, unzip_single=None):
                # DMR4G-TIFF: crs=None (georeferencja tylko w .tfw)
                _write_tif(Path(output_path), crs=None)
                return Path(output_path)

            client.fetch_file.side_effect = fake_fetch
            provider = CuzkDmrProvider(resolution="5m")
            provider.download("CTES96", target)

        index_cls.return_value.sm5_sheet.assert_called_once_with("CTES96")
        url = client.fetch_file.call_args.args[0]
        assert url == (
            "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/CTES96.zip"
        )
        assert client.fetch_file.call_args.kwargs["unzip_single"] == ".tif"
        with rasterio.open(target) as src:
            assert src.crs is not None and src.crs.to_epsg() == 5514

    def test_sm5_crs_repair_keeps_worldfile_georeference(self, tmp_path):
        """Naprawa CRS nie moze zgubic georeferencji trzymanej w .tfw."""
        target = tmp_path / "CTES96.tif"
        with patch(_CLIENT_PATCH) as client_cls, patch(_INDEX_PATCH) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()

            def fake_fetch(url, output_path, *, unzip_single=None):
                _write_dmr4g_pair(Path(output_path))
                return Path(output_path)

            client_cls.return_value.fetch_file.side_effect = fake_fetch
            CuzkDmrProvider(resolution="5m").download("CTES96", target)

        with rasterio.open(target) as src:
            assert src.crs.to_epsg() == 5514
            assert src.bounds == pytest.approx(
                (-450000.0, -1114000.0, -447500.0, -1112000.0)
            )
            assert src.nodata == CUZK_NODATA

    def test_sm5_with_2m_resolution_rejected(self, tmp_path):
        provider = CuzkDmrProvider(resolution="2m")
        with pytest.raises(ValidationError, match="5m"):
            provider.download("CTES96", tmp_path / "CTES96.tif")

    def test_non_cz_godlo_rejected(self, tmp_path):
        provider = CuzkDmrProvider()
        with pytest.raises(ValidationError, match="CZ"):
            provider.download("N-34-130-D-d-2-4", tmp_path / "x.tif")

    def test_openzu_404_points_to_sheet_index(self, tmp_path):
        """404 openzu dla arkusza znanego indeksowi => czytelna podpowiedz."""
        with patch(_CLIENT_PATCH) as client_cls, patch(_INDEX_PATCH) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()
            client_cls.return_value.fetch_file.side_effect = DownloadError(
                "Pobieranie nieudane po 3 probach: 404 Client Error"
            )
            provider = CuzkDmrProvider(resolution="5m")
            with pytest.raises(DownloadError) as exc:
                provider.download("CTES96", tmp_path / "CTES96.tif")
        assert "404" in str(exc.value)  # oryginalny komunikat zachowany
        assert "KladyMapovychListu" in str(exc.value)

    def test_missing_files_channel_is_config_error(self, tmp_path):
        """Deskryptor bez kanalu plikowego => jasny blad, nie AttributeError."""
        descriptor = get_source("cz.cuzk.dmr4g")
        without_files = replace(
            descriptor,
            channels=tuple(
                ch
                for ch in descriptor.channels
                if ch.transport != TransportKind.DIRECT_FILES
            ),
        )
        with patch(_SOURCE_PATCH, return_value=without_files), patch(_INDEX_PATCH):
            provider = CuzkDmrProvider(resolution="5m")
            with pytest.raises(ValidationError, match="DIRECT_FILES"):
                provider.download("CTES96", tmp_path / "CTES96.tif")

    def test_timeout_reaches_client(self, tmp_path):
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = _exporting("EPSG:3045")
            provider = CuzkDmrProvider(resolution="2m")
            provider.download("302_5550", tmp_path / "302_5550.tif", timeout=15)
        assert any(
            call.kwargs.get("timeout") == 15 for call in client_cls.call_args_list
        )


class TestDownloadBbox:
    def test_native_5514(self, tmp_path):
        target = tmp_path / "area.tif"
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:5514")
            CuzkDmrProvider(resolution="2m").download_bbox(bbox, target)
        assert client.export_image.call_args.kwargs["image_sr"] == "EPSG:5514"
        assert client.export_image.call_args.args[1] == bbox

    def test_bbox_works_for_5m_too(self, tmp_path):
        """Rekonesans krok 4: dmr4g/exportImage dziala — bbox nie jest blokowany."""
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:5514")
            CuzkDmrProvider(resolution="5m").download_bbox(bbox, tmp_path / "a.tif")
        assert client.export_image.call_args.kwargs["pixel_size"] == 5.0
        assert client.export_image.call_args.args[0] == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer"
        )

    def test_target_crs_via_server_reprojection(self, tmp_path):
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:2180")
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, tmp_path / "area.tif")
        kwargs = client.export_image.call_args.kwargs
        assert kwargs["image_sr"] == "EPSG:2180"
        # bbox znormalizowany do ukladu wyjsciowego (kafelkowanie bez szwow)
        sent = client.export_image.call_args.args[1]
        assert sent.crs == "EPSG:2180"
        # okolice Cieszyna w PL-1992: E ~470 km, N ~209 km
        assert 460_000 < sent.min_x < 480_000
        assert 200_000 < sent.min_y < 220_000

    def test_non_gtiff_format_rejected(self, tmp_path):
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with pytest.raises(ValidationError, match="GTiff"):
            CuzkDmrProvider().download_bbox(bbox, tmp_path / "a.png", format="PNG")


class TestVerticalTransform:
    def _pinned_fakes(self):
        """side_effect dla build_pinned_transform: OSOBNE fake'i dla operacji
        pionowej 8357->5621 (3-argumentowa, przesuwa z o +0.13) i pomocniczej
        poziomej raster_crs->4326 (2-argumentowa, identycznosc) —
        _apply_vertical_shift buduje obie przez te sama funkcje."""
        vertical = MagicMock()
        vertical.description = "Baltic 1957 height to EVRF2007 height (1)"
        vertical.accuracy_m = 0.1
        vertical.transform.side_effect = lambda x, y, z: (x, y, np.asarray(z) + 0.13)
        horizontal = MagicMock()
        horizontal.transform.side_effect = lambda x, y: (x, y)

        def factory(src_crs, dst_crs, policy):
            return vertical if src_crs == "EPSG:8357" else horizontal

        return factory, vertical

    def test_bpv_native_no_transform(self):
        provider = CuzkDmrProvider()  # vertical_crs="Bpv"
        assert provider.vertical_transform is None

    def test_evrf2007_builds_8357_to_5621(self):
        factory, _ = self._pinned_fakes()
        with patch(_PINNED_PATCH, side_effect=factory) as pinned_mock:
            provider = CuzkDmrProvider(vertical_crs="EVRF2007")
            assert provider.vertical_transform is not None
        assert pinned_mock.call_args.args[:2] == ("EPSG:8357", "EPSG:5621")

    def test_evrf2007_shifts_values_and_keeps_nodata(self, tmp_path):
        target = tmp_path / "302_5550.tif"
        factory, vertical = self._pinned_fakes()
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:3045")
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", target)

        with rasterio.open(target) as src:
            data = src.read(1)
        assert data[5, 5] == pytest.approx(100.13, abs=1e-4)
        assert data[0, 0] == CUZK_NODATA  # nodata NIE jest transformowane
        assert vertical.transform.called

    def test_bbox_mode_also_shifts_values(self, tmp_path):
        target = tmp_path / "area.tif"
        factory, vertical = self._pinned_fakes()
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client_cls.return_value.export_image.side_effect = _exporting("EPSG:5514")
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download_bbox(bbox, target)

        with rasterio.open(target) as src:
            data = src.read(1)
        assert data[5, 5] == pytest.approx(100.13, abs=1e-4)
        assert data[0, 0] == CUZK_NODATA
        assert vertical.transform.called

    def test_all_nodata_raster_is_left_alone(self, tmp_path):
        """Kafel calkiem poza CZ (sam noData) nie moze zostac przesuniety."""
        target = tmp_path / "empty.tif"
        factory, vertical = self._pinned_fakes()
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client_cls.return_value.export_image.side_effect = lambda e, b, **kw: (
                _write_tif(Path(kw["output_path"]), crs="EPSG:3045", value=CUZK_NODATA)
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", target)

        with rasterio.open(target) as src:
            assert np.all(src.read(1) == CUZK_NODATA)
        assert not vertical.transform.called

    def test_raster_without_crs_reports_clear_error(self, tmp_path):
        """Bez CRS nie da sie policzyc (lon, lat) — czytelny blad zamiast CRSError."""
        factory, _ = self._pinned_fakes()
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client_cls.return_value.export_image.side_effect = _exporting(None)
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            with pytest.raises(ValidationError, match="CRS"):
                provider.download("302_5550", tmp_path / "t.tif")

    def test_chunking_covers_whole_raster(self, tmp_path):
        """Raster wyzszy niz jeden pas: kazdy piksel danych przesuniety raz."""
        factory, _ = self._pinned_fakes()
        target = tmp_path / "wide.tif"
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
            patch("kartograf.providers.cuzk.dmr._CHUNK_PIXELS", 20),
        ):
            client_cls.return_value.export_image.side_effect = lambda e, b, **kw: (
                _write_tif(Path(kw["output_path"]), crs="EPSG:3045", size=(10, 10))
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", target)

        with rasterio.open(target) as src:
            data = src.read(1)
        assert data[0, 0] == CUZK_NODATA
        assert np.all(data[data != CUZK_NODATA] == pytest.approx(100.13, abs=1e-4))

    def test_vertical_transform_gets_lon_lat_order(self, tmp_path):
        """Rekonesans 7a: przy always_xy=True argumentami sa (lon, lat, h);
        zamiana daje cichy blad ~0,44 m."""
        factory, vertical = self._pinned_fakes()
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory) as pinned_mock,
        ):
            client = client_cls.return_value
            # raster w EPSG:4326: piksele leza w okolicach Cieszyna
            client.export_image.side_effect = lambda e, b, **kw: (
                _write_tif(
                    Path(kw["output_path"]),
                    crs="EPSG:4326",
                    bounds=(18.6, 49.7, 18.7, 49.8),
                )
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", tmp_path / "t.tif")

        # transformacja pomocnicza budowana z CRS rastra do WGS84
        horizontal_calls = [
            call for call in pinned_mock.call_args_list if call.args[0] != "EPSG:8357"
        ]
        assert horizontal_calls
        assert all(call.args[1] == "EPSG:4326" for call in horizontal_calls)
        lon, lat, z = vertical.transform.call_args.args
        assert np.all((np.asarray(lon) > 18.6) & (np.asarray(lon) < 18.7))
        assert np.all((np.asarray(lat) > 49.7) & (np.asarray(lat) < 49.8))
        assert np.all(np.asarray(z) == 100.0)


class TestDescriptorProviderConsistency:
    """Wzor: TestDescriptorProviderConsistency z test_sources_registry."""

    def test_dmr5g(self, tmp_path):
        from kartograf.download.storage import FileStorage

        d = get_source("cz.cuzk.dmr5g")
        provider = create_dmr_provider(resolution="2m")
        assert provider.descriptor_key == d.key
        assert provider.default_extension == d.default_extension
        storage = FileStorage(tmp_path, subdir=d.storage_subdir)
        assert storage._subdir == d.storage_subdir
        for ch in d.channels:
            assert ch.vertical_crs_options == ("EPSG:8357",)
            assert ch.endpoint  # silnik jest sterowany deskryptorem

    def test_dmr4g(self, tmp_path):
        d = get_source("cz.cuzk.dmr4g")
        provider = create_dmr_provider(resolution="5m")
        assert provider.descriptor_key == d.key
        capabilities = [set(ch.capabilities) for ch in d.channels]
        assert {"sheet_files"} in capabilities
        assert {"bbox_raster"} in capabilities
