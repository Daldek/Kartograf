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
from rasterio.transform import Affine, from_bounds, from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.cuzk import create_dmr_provider
from kartograf.providers.cuzk.client import wkid
from kartograf.providers.cuzk.dmr import CUZK_NODATA, CuzkDmrProvider, bbox_to_crs
from kartograf.providers.cuzk.sheets import SheetInfo
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source
from kartograf.transform.crs import (
    TransformError,
    TransformUnavailableError,
    build_pinned_transform,
)

_CLIENT_PATCH = "kartograf.providers.cuzk.dmr.CuzkClient"
_INDEX_PATCH = "kartograf.providers.cuzk.dmr.SheetIndex"
_PINNED_PATCH = "kartograf.providers.cuzk.dmr.build_pinned_transform"
_GROUP_PATCH = "kartograf.transform.crs.TransformerGroup"
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
    def test_tm33_godlo_requests_native_then_warps_to_3045(self, tmp_path):
        """Kafel TM33 jest zdefiniowany w 3045, ale sciagany w 5514: reprojekcje
        robi Kartograf, nie serwer (ADR-024)."""
        target = tmp_path / "302_5550.tif"
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _server_emulator()
            provider = CuzkDmrProvider(resolution="2m")
            result = provider.download("302_5550", target)

        assert result == target
        kwargs = client.export_image.call_args.kwargs
        assert kwargs["pixel_size"] == 2.0
        assert kwargs["image_sr"] == "EPSG:5514"
        assert kwargs["no_data"] == CUZK_NODATA
        called_endpoint, called_bbox = client.export_image.call_args.args[:2]
        assert called_endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
        )
        assert called_bbox.crs == "EPSG:5514"
        # zadanie natywne pokrywa kafel po przeliczeniu z powrotem do 3045
        tile = BBox(302000, 5550000, 304000, 5552000, "EPSG:3045")
        back = bbox_to_crs(called_bbox, "EPSG:3045")
        assert back.min_x <= tile.min_x and back.min_y <= tile.min_y
        assert back.max_x >= tile.max_x and back.max_y >= tile.max_y
        with rasterio.open(target) as src:
            assert src.crs.to_epsg() == 3045
            assert src.bounds == (302000.0, 5550000.0, 304000.0, 5552000.0)

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

    def test_sm5_corrupted_tiff_raises_download_error_and_cleans_up(self, tmp_path):
        """ZIP ma poprawna strukture, ale rozpakowany .tif jest uszkodzony
        (np. urwane pobieranie) — rasterio.open zglasza niemapowany wyjatek
        (tu: RasterioIOError), ktory _assign_crs musi zamienic na
        DownloadError. Zarowno .tif jak i towarzyszacy .tfw musza zniknac,
        inaczej kolejny --skip-existing utrwali korupcje (F1)."""
        target = tmp_path / "CTES96.tif"
        with patch(_CLIENT_PATCH) as client_cls, patch(_INDEX_PATCH) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()

            def fake_fetch(url, output_path, *, unzip_single=None):
                output_path = Path(output_path)
                output_path.write_bytes(b"not a real tiff at all")
                output_path.with_suffix(".tfw").write_text(
                    "500.0\n0.0\n0.0\n-500.0\n-449750.0\n-1112250.0\n"
                )
                return output_path

            client_cls.return_value.fetch_file.side_effect = fake_fetch
            provider = CuzkDmrProvider(resolution="5m")
            with pytest.raises(DownloadError):
                provider.download("CTES96", target)

        assert not target.exists()
        assert not target.with_suffix(".tfw").exists()

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


# --- emulator serwera CUZK (wspolny dla testow poziomych i pionowych) --------

# zmierzony blad reprojekcji serwerowej dla okolic Cieszyna (dE, dN):
# pominiety datum shift S-JTSK->ETRS89, |d| = 135 m (pomiar 2026-08-11)
_BALLPARK_SHIFT = (119.0, 64.0)
_APEX_5514 = (-449000.0, -1113000.0)
_NATIVE_BBOX = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")


def _pinned_5514_to(target_crs):
    from kartograf.providers.cuzk.dmr import _HORIZONTAL_POLICY, NATIVE_CRS

    return build_pinned_transform(NATIVE_CRS, target_crs, _HORIZONTAL_POLICY)


def _apex_in(target_crs):
    """Wierzcholek stozka w ukladzie docelowym wg pyproj (wzorzec prawdy)."""
    x, y = _pinned_5514_to(target_crs).transform(*_APEX_5514)
    return float(x), float(y)


def _server_emulator(calls=None, *, nodata_west_of=None, flat=None):
    """side_effect dla export_image odtwarzajacy zachowanie ArcGIS CUZK.

    Odpowiedz natywna (5514) jest poprawna; kazda inna dostaje tresc
    przesunieta o `_BALLPARK_SHIFT` — dokladnie tak, jak zmierzony serwer.
    Kod ufajacy reprojekcji serwerowej przepusci to przesuniecie do pliku
    wynikowego; kod pobierajacy natywnie i reprojektujacy lokalnie — nie.
    """

    def _fake(endpoint, bbox, **kwargs):
        if calls is not None:
            calls.append((bbox, kwargs["image_sr"], kwargs["pixel_size"]))
        pixel = kwargs["pixel_size"]
        output_path = Path(kwargs["output_path"])
        if wkid(kwargs["image_sr"]) == "5514":
            apex = _APEX_5514
        else:
            ax, ay = _apex_in(kwargs["image_sr"])
            apex = (ax + _BALLPARK_SHIFT[0], ay + _BALLPARK_SHIFT[1])
        width = max(1, round((bbox.max_x - bbox.min_x) / pixel))
        height = max(1, round((bbox.max_y - bbox.min_y) / pixel))
        cols, rows = np.meshgrid(np.arange(width), np.arange(height))
        xs = bbox.min_x + (cols + 0.5) * pixel
        ys = bbox.max_y - (rows + 0.5) * pixel
        if flat is None:
            data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
        else:
            data = np.full((height, width), flat, dtype="float32")
        if nodata_west_of is not None:
            data[xs < nodata_west_of] = CUZK_NODATA
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "count": 1,
            "width": width,
            "height": height,
            "crs": kwargs["image_sr"],
            "transform": from_origin(bbox.min_x, bbox.max_y, pixel, pixel),
            "nodata": CUZK_NODATA,
        }
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(data, 1)
        return output_path

    return _fake


def _apex_of(path):
    """Wspolrzedne piksela o najwyzszej wartosci (wierzcholek stozka)."""
    with rasterio.open(path) as ds:
        data = ds.read(1, masked=True)
        row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
        return ds.xy(int(row), int(col))


class TestHorizontalReprojection:
    """Reprojekcja tresci CZ jest LOKALNA (przypieta operacja), a nie serwerowa."""

    BALLPARK_SHIFT = _BALLPARK_SHIFT
    APEX_5514 = _APEX_5514

    _apex_in = staticmethod(_apex_in)
    _apex_of = staticmethod(_apex_of)

    @staticmethod
    def _fake_server(calls, **kwargs):
        return _server_emulator(calls, **kwargs)

    def test_bbox_target_crs_puts_content_where_pyproj_says(self, tmp_path):
        """Regresja TRESCI: wierzcholek ma trafic tam, gdzie wskazuje pyproj."""
        target = tmp_path / "area.tif"
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        calls: list = []
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server(calls)
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, target)

        expected = self._apex_in("EPSG:2180")
        got = self._apex_of(target)
        assert abs(got[0] - expected[0]) < 2.0, f"E: {got} vs {expected}"
        assert abs(got[1] - expected[1]) < 2.0, f"N: {got} vs {expected}"

    def test_server_is_asked_only_for_native_5514(self, tmp_path):
        """Zadania exportImage bija wylacznie w uklad natywny, niezaleznie od celu."""
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        calls: list = []
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server(calls)
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, tmp_path / "area.tif")

        assert calls, "serwer nie zostal odpytany"
        assert all(wkid(image_sr) == "5514" for _, image_sr, _ in calls)
        assert all(wkid(sent.crs) == "5514" for sent, _, _ in calls)

    def test_tm33_godlo_also_goes_native_then_local_warp(self, tmp_path):
        """Kafel TM33 (3045) tez nie ufa reprojekcji serwerowej."""
        target = tmp_path / "302_5550.tif"
        calls: list = []
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server(calls)
            CuzkDmrProvider(resolution="2m").download("302_5550", target)

        assert all(wkid(image_sr) == "5514" for _, image_sr, _ in calls)
        with rasterio.open(target) as ds:
            assert ds.crs.to_epsg() == 3045
            assert ds.bounds == (302000.0, 5550000.0, 304000.0, 5552000.0)
            assert (ds.width, ds.height) == (1000, 1000)

    def test_native_request_covers_whole_target_bbox(self, tmp_path):
        """Obwiednia zadania natywnego musi POKRYWAC cel (z zapasem na warp)."""
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        calls: list = []
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server(calls)
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, tmp_path / "area.tif")

        target_bbox = bbox_to_crs(bbox, "EPSG:2180")
        sent = calls[0][0]
        corners = bbox_to_crs(sent, "EPSG:2180")
        assert corners.min_x <= target_bbox.min_x
        assert corners.min_y <= target_bbox.min_y
        assert corners.max_x >= target_bbox.max_x
        assert corners.max_y >= target_bbox.max_y

    def test_nodata_does_not_bleed_into_interpolation(self, tmp_path):
        """Piksele nodata nie moga rozcienczac wartosci sasiadow ani zniknac.

        Pole zrodlowe jest PLASKIE (300 m) z polowa obszaru jako nodata:
        kazda wartosc rozna od 300 w wyniku byloby dowodem, ze interpolator
        wmieszal `-9999` do sredniej wazonej na krawedzi maski.
        """
        target = tmp_path / "area.tif"
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server(
                [], nodata_west_of=-449000.0, flat=300.0
            )
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, target)

        with rasterio.open(target) as ds:
            data = ds.read(1)
            assert ds.nodata == CUZK_NODATA
            valid = data[data != CUZK_NODATA]
            assert valid.size > 0
            assert (data == CUZK_NODATA).sum() > 0
            assert np.array_equal(valid, np.full(valid.shape, 300.0, dtype="float32"))

    def test_temporary_native_file_is_cleaned_up(self, tmp_path):
        target = tmp_path / "area.tif"
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client_cls.return_value.export_image.side_effect = self._fake_server([])
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, target)

        assert sorted(p.name for p in tmp_path.iterdir()) == ["area.tif"]

    def test_failed_warp_leaves_no_output(self, tmp_path):
        target = tmp_path / "area.tif"
        bbox = BBox(-450000, -1114000, -448000, -1112000, "EPSG:5514")
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(
                "kartograf.providers.cuzk.dmr.reproject",
                side_effect=RuntimeError("warp padl"),
            ),
            pytest.raises(RuntimeError),
        ):
            client_cls.return_value.export_image.side_effect = self._fake_server([])
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, target)

        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        ("kind", "target_crs"),
        [("bbox", "EPSG:2180"), ("godlo", "EPSG:3045")],
    )
    def test_warp_forces_the_pinned_operation(self, tmp_path, kind, target_crs):
        """Operacja MUSI byc podana GDAL-owi jawnie (ADR-024 pkt b).

        Bez `COORDINATE_OPERATION` warp nadal sie udaje i nadal trafia blisko
        prawdy — GDAL wybiera wtedy operacje sam, poza polityka
        `transform/crs.py` (zakaz ballparku, limit dokladnosci, probe).
        Roznica wzgledem operacji przypietej to srednio 0,08 m, ale do 1,9 m
        w pojedynczych pikselach — czyli za malo, by wywrocic asercje TRESCI
        (tolerancja 1 px = 2 m), a wiec za malo, by wykryc regresje. Ten test
        pilnuje samego wymuszenia: sprawdza, ktora operacja poszla do GDAL-a.
        """
        from rasterio.warp import reproject as real_reproject

        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(
                "kartograf.providers.cuzk.dmr.reproject", wraps=real_reproject
            ) as warp,
        ):
            client_cls.return_value.export_image.side_effect = _server_emulator()
            if kind == "bbox":
                provider = CuzkDmrProvider(resolution="2m", target_crs=target_crs)
                provider.download_bbox(_NATIVE_BBOX, tmp_path / "area.tif")
            else:
                CuzkDmrProvider(resolution="2m").download(
                    "302_5550", tmp_path / "302_5550.tif"
                )

        warp.assert_called_once()
        expected = _pinned_5514_to(target_crs).gdal_operation()
        assert warp.call_args.kwargs["COORDINATE_OPERATION"] == expected
        # sanity: wymuszona operacja niesie transformacje datum S-JTSK->ETRS89
        # (jej brak to wlasnie zmierzony blad 135 m serwera CUZK)
        assert "molobadekas" in expected

    def test_horizontal_transform_is_none_for_native(self):
        provider = CuzkDmrProvider(resolution="2m")
        assert provider.horizontal_transform("EPSG:5514") is None
        pinned = provider.horizontal_transform("EPSG:2180")
        assert pinned is not None
        assert pinned.accuracy_m <= 1.0

    def test_unavailable_horizontal_operation_fails_before_download(self, tmp_path):
        """Fail-fast: brak bezpiecznej operacji przerywa PRZED transferem."""
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(
                _PINNED_PATCH,
                side_effect=TransformUnavailableError("brak operacji"),
            ),
            pytest.raises(TransformUnavailableError),
        ):
            CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
        client_cls.return_value.export_image.assert_not_called()


def _group_of(*transformers):
    """Zamiennik TransformerGroup: podane operacje, bez ruchu sieciowego."""
    group = MagicMock()
    group.transformers = list(transformers)
    group.unavailable_operations = []
    return group


def _fake_operation(accuracy, description, result):
    t = MagicMock()
    t.accuracy = accuracy
    t.description = description
    t.transform.return_value = result
    return t


class TestProbePoint:
    """Punkt kontrolny w politykach POZIOMYCH CZ: siatka obcego kraju
    (np. sk_gku, Slowacja) bywa dokladniejsza na papierze, a nad Czechami
    zwraca inf — probe ma ja odrzucic, zanim popsuje pobranie (audyt A1-2).
    """

    def test_horizontal_policy_rejects_operation_returning_inf(self):
        t_bad = _fake_operation(0.051, "sk_gku fake", (float("inf"), float("inf")))
        t_good = _fake_operation(0.5, "Krovak good", (472887.5, 208337.5))
        with patch(_GROUP_PATCH, return_value=_group_of(t_bad, t_good)):
            provider = CuzkDmrProvider(
                resolution="2m", target_crs="EPSG:2180", session=MagicMock()
            )
            pinned = provider.horizontal_transform("EPSG:2180")
        assert pinned is not None
        assert pinned.description == "Krovak good"
        assert pinned.accuracy_m == 0.5

    def test_envelope_policy_probe_is_bbox_center(self):
        """Obwiednia: punkt kontrolny to srodek przeliczanego bboxa
        (w ukladzie ZRODLOWYM, wiec bez dodatkowej transformacji)."""
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_PINNED_PATCH, wraps=build_pinned_transform) as pinned_mock:
            provider = CuzkDmrProvider(resolution="2m", session=MagicMock())
            provider._bbox_to_crs(bbox, "EPSG:4326")
        assert pinned_mock.call_args.args[:2] == ("EPSG:5514", "EPSG:4326")
        assert pinned_mock.call_args.args[2].probe_point == (-446500.0, -1113500.0)

    def test_module_level_bbox_to_crs_carries_probe(self):
        """Galaz `pinned is None` modulowej `bbox_to_crs` — jedyna, ktorej
        uzywa CLI (`_country_bbox`, normalizacja nazwy pliku, `--country auto`,
        sciezka mozaiki). Provider jej nie dotyka, wiec bez tej asercji ciche
        usuniecie probe w tej galezi przeszloby bez sladu."""
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_PINNED_PATCH, wraps=build_pinned_transform) as pinned_mock:
            bbox_to_crs(bbox, "EPSG:4326")
        assert pinned_mock.call_args.args[:2] == ("EPSG:5514", "EPSG:4326")
        assert pinned_mock.call_args.args[2].probe_point == (-446500.0, -1113500.0)

    def test_horizontal_policy_probe_is_cz_native_center(self):
        from kartograf.providers.cuzk.dmr import CZ_PROBE_NATIVE

        with patch(_PINNED_PATCH, wraps=build_pinned_transform) as pinned_mock:
            provider = CuzkDmrProvider(resolution="2m", session=MagicMock())
            provider.horizontal_transform("EPSG:2180")
        assert pinned_mock.call_args.args[:2] == ("EPSG:5514", "EPSG:2180")
        assert pinned_mock.call_args.args[2].probe_point == CZ_PROBE_NATIVE

    def test_all_horizontal_pinned_calls_carry_probe(self, tmp_path):
        """Zadna operacja POZIOMA nie jest budowana bez punktu kontrolnego —
        ani reprojekcja tresci, ani obwiednia, ani lon/lat dla shiftu pionowego.
        Wyjatek jest jeden: para czysto pionowa 8357->5621."""
        calls: list = []
        vertical = MagicMock()
        vertical.description = "Baltic 1957 height to EVRF2007 height (1)"
        vertical.accuracy_m = 0.1
        vertical.transform.side_effect = lambda x, y, z: (x, y, np.asarray(z) + 0.13)

        def recording(src_crs, dst_crs, policy):
            calls.append((src_crs, dst_crs, policy))
            if (src_crs, dst_crs) == ("EPSG:8357", "EPSG:5621"):
                return vertical
            return build_pinned_transform(src_crs, dst_crs, policy)

        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=recording),
        ):
            client_cls.return_value.export_image.side_effect = _server_emulator(
                flat=300.0
            )
            provider = CuzkDmrProvider(
                resolution="2m", target_crs="EPSG:2180", vertical_crs="EVRF2007"
            )
            provider.download_bbox(_NATIVE_BBOX, tmp_path / "area.tif")

        horizontal = [c for c in calls if (c[0], c[1]) != ("EPSG:8357", "EPSG:5621")]
        assert {(c[0], c[1]) for c in horizontal} == {
            ("EPSG:5514", "EPSG:2180"),  # reprojekcja tresci
            ("EPSG:2180", "EPSG:5514"),  # obwiednia zadania natywnego
            ("EPSG:2180", "EPSG:4326"),  # lon/lat dla operacji pionowej
        }
        assert all(policy.probe_point is not None for _, _, policy in horizontal)


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

    def test_target_crs_produces_target_grid_from_native_request(self, tmp_path):
        """`--target-crs` zmienia siatke WYNIKU, ale nie uklad ZADANIA."""
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        target = tmp_path / "area.tif"
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = _server_emulator()
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, target)

        kwargs = client.export_image.call_args.kwargs
        assert kwargs["image_sr"] == "EPSG:5514"
        sent = client.export_image.call_args.args[1]
        assert sent.crs == "EPSG:5514"
        # wynik lezy na siatce zadanej: okolice Cieszyna w PL-1992
        expected = bbox_to_crs(bbox, "EPSG:2180")
        with rasterio.open(target) as src:
            assert src.crs.to_epsg() == 2180
            assert src.bounds.left == pytest.approx(expected.min_x, abs=2.0)
            assert src.bounds.top == pytest.approx(expected.max_y, abs=2.0)
            assert 460_000 < src.bounds.left < 480_000
            assert 200_000 < src.bounds.bottom < 220_000

    def test_non_gtiff_format_rejected(self, tmp_path):
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with pytest.raises(ValidationError, match="GTiff"):
            CuzkDmrProvider().download_bbox(bbox, tmp_path / "a.png", format="PNG")


class TestVerticalTransform:
    """Przedmiotem testow jest `_apply_vertical_shift`, dlatego rastry ida
    sciezka NATYWNA (bbox w 5514) — bez reprojekcji poziomej, ktora
    przeprobkowalaby syntetyczne fixtury. Wspolgranie obu transformacji
    sprawdza `test_tm33_godlo_warps_then_shifts_vertically`."""

    def _pinned_fakes(self, real_horizontal=False):
        """side_effect dla build_pinned_transform: OSOBNE fake'i dla operacji
        pionowej 8357->5621 (3-argumentowa, przesuwa z o +0.13) i pomocniczej
        poziomej raster_crs->4326 (2-argumentowa, identycznosc) —
        _apply_vertical_shift buduje obie przez te sama funkcje.

        `real_horizontal=True` zostawia operacje reprojekcji TRESCI (5514->cel)
        prawdziwa — fake'owy pipeline nie przeszedlby przez GDAL.
        """
        vertical = MagicMock()
        vertical.description = "Baltic 1957 height to EVRF2007 height (1)"
        vertical.accuracy_m = 0.1
        vertical.transform.side_effect = lambda x, y, z: (x, y, np.asarray(z) + 0.13)
        horizontal = MagicMock()
        horizontal.transform.side_effect = lambda x, y: (x, y)

        def factory(src_crs, dst_crs, policy):
            if src_crs == "EPSG:8357":
                return vertical
            if real_horizontal and dst_crs != "EPSG:4326":
                return build_pinned_transform(src_crs, dst_crs, policy)
            return horizontal

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
        target = tmp_path / "area.tif"
        factory, vertical = self._pinned_fakes()
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client = client_cls.return_value
            client.export_image.side_effect = _exporting("EPSG:5514")
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download_bbox(_NATIVE_BBOX, target)

        with rasterio.open(target) as src:
            data = src.read(1)
        assert data[5, 5] == pytest.approx(100.13, abs=1e-4)
        assert data[0, 0] == CUZK_NODATA  # nodata NIE jest transformowane
        assert vertical.transform.called

    def test_tm33_godlo_warps_then_shifts_vertically(self, tmp_path):
        """Kafel TM33: reprojekcja pozioma i przesuniecie pionowe skladaja sie
        (raster w 3045, wartosci po operacji Bpv->EVRF2007, nodata nietkniete)."""
        target = tmp_path / "302_5550.tif"
        factory, vertical = self._pinned_fakes(real_horizontal=True)
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            client_cls.return_value.export_image.side_effect = _server_emulator(
                flat=300.0
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", target)

        with rasterio.open(target) as src:
            assert src.crs.to_epsg() == 3045
            data = src.read(1)
        valid = data[data != CUZK_NODATA]
        assert valid.size > 0
        assert np.all(valid == pytest.approx(300.13, abs=1e-4))
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
                _write_tif(Path(kw["output_path"]), crs="EPSG:5514", value=CUZK_NODATA)
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download_bbox(_NATIVE_BBOX, target)

        with rasterio.open(target) as src:
            assert np.all(src.read(1) == CUZK_NODATA)
        assert not vertical.transform.called

    def test_unavailable_operation_fails_before_any_download(self, tmp_path):
        """Fail-fast jak przy KRON86: brak bezpiecznej operacji 8357->5621
        przerywa w konstruktorze, zanim cokolwiek zostanie pobrane."""
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(
                _PINNED_PATCH,
                side_effect=TransformUnavailableError("brak bezpiecznej operacji"),
            ),
        ):
            with pytest.raises(TransformUnavailableError):
                CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            client_cls.return_value.export_image.assert_not_called()
            client_cls.return_value.fetch_file.assert_not_called()
        assert not list(tmp_path.iterdir())

    def test_failed_shift_leaves_no_half_transformed_file(self, tmp_path):
        """Awaria na drugim pasie nie moze zostawic rastra o wymieszanych
        ukladach pionowych pod docelowa nazwa (skip_existing utrwalilby korupcje)."""
        target = tmp_path / "area.tif"
        factory, vertical = self._pinned_fakes()
        calls = {"n": 0}

        def failing(x, y, z):
            calls["n"] += 1
            if calls["n"] > 1:
                raise TransformError("Transformacja zwrocila wartosc nieskonczona")
            return (x, y, np.asarray(z) + 0.13)

        vertical.transform.side_effect = failing
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_PINNED_PATCH, side_effect=factory),
            patch("kartograf.providers.cuzk.dmr._CHUNK_PIXELS", 20),  # 5 pasow
        ):
            client_cls.return_value.export_image.side_effect = _exporting("EPSG:5514")
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            with pytest.raises(TransformError):
                provider.download_bbox(_NATIVE_BBOX, target)

        assert calls["n"] > 1  # awaria faktycznie po zapisaniu pierwszego pasa
        assert not target.exists()
        assert list(tmp_path.iterdir()) == []  # zero plikow tymczasowych

    def test_failed_shift_removes_sm5_worldfile_too(self, tmp_path):
        """Sciezka SM5: razem z .tif znika towarzyszacy .tfw (zaden osierocony
        plik nie zostaje na dysku)."""
        target = tmp_path / "CTES96.tif"
        factory, vertical = self._pinned_fakes()
        vertical.transform.side_effect = TransformError("wartosc nieskonczona")
        with (
            patch(_CLIENT_PATCH) as client_cls,
            patch(_INDEX_PATCH) as index_cls,
            patch(_PINNED_PATCH, side_effect=factory),
        ):
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()
            client_cls.return_value.fetch_file.side_effect = (
                lambda url, output_path, **kw: (
                    _write_dmr4g_pair(Path(output_path)) or Path(output_path)
                )
            )
            provider = CuzkDmrProvider(resolution="5m", vertical_crs="EVRF2007")
            with pytest.raises(TransformError):
                provider.download("CTES96", target)

        assert list(tmp_path.iterdir()) == []

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
                provider.download_bbox(_NATIVE_BBOX, tmp_path / "t.tif")

    def test_vertical_shift_rejects_raster_without_geotransform(self, tmp_path):
        """Raster z CRS, ale z jednostkowa geotransformacja (DMR4G-TIFF, ktory
        zgubil .tfw): (lon, lat) wyszlyby z NUMEROW pikseli, a wysokosci
        zostalyby cicho przesuniete o zly offset (rzedu 0,14 m). Ma byc jawny
        blad i sprzatniecie, a nie po cichu zly plik."""
        path = tmp_path / "CTES96.tif"
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
                crs="EPSG:5514",
                transform=Affine.identity(),
            ) as dst:
                dst.write(np.full((4, 5), 300.0, dtype="float32"), 1)

        factory, vertical = self._pinned_fakes()
        with patch(_PINNED_PATCH, side_effect=factory):
            provider = CuzkDmrProvider(resolution="5m", vertical_crs="EVRF2007")
            with pytest.raises(ValidationError, match="geotransformacj"):
                provider._apply_vertical_shift(path)

        assert not vertical.transform.called  # nic nie zostalo przeliczone
        assert not path.exists()
        assert not path.with_suffix(".tfw").exists()
        assert list(tmp_path.iterdir()) == []  # zero plikow tymczasowych

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
                _write_tif(Path(kw["output_path"]), crs="EPSG:5514", size=(10, 10))
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download_bbox(_NATIVE_BBOX, target)

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
            provider.download_bbox(_NATIVE_BBOX, tmp_path / "t.tif")

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
