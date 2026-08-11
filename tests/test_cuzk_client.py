"""Testy CuzkClient — silnik ArcGIS REST + pliki openzu (offline)."""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient, _wkid

_CUZK_SESSION_PATCH = "kartograf.providers.cuzk.client.requests.Session"
_DOWNLOAD_TO_PATCH = "kartograf.providers.cuzk.client.download_to"

KLADY = "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"


def _json_response(payload):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload
    return response


def _feature(mapnom="CTES96", podil=0.507):
    return {
        "attributes": {"MAPNOM": mapnom, "MAPNAME": "Cesky Tesin 8-6", "PODIL": podil},
        "geometry": {
            "rings": [
                [
                    [-450000, -1105000],
                    [-447500, -1105000],
                    [-447500, -1103000],
                    [-450000, -1103000],
                    [-450000, -1105000],
                ]
            ]
        },
    }


class TestWkid:
    def test_epsg_prefix_stripped(self):
        assert _wkid("EPSG:5514") == "5514"

    def test_bare_code_passes(self):
        assert _wkid("3045") == "3045"


class TestSessionOwnership:
    def test_creates_own_session_when_none(self):
        with patch(_CUZK_SESSION_PATCH) as session_cls:
            client = CuzkClient()
        assert client._session is session_cls.return_value

    def test_injected_session_is_used(self):
        session = Mock()
        assert CuzkClient(session=session)._session is session


class TestQuery:
    def test_where_query_builds_params(self):
        session = Mock()
        session.get.return_value = _json_response({"features": [_feature()]})
        client = CuzkClient(session=session)

        features = client.query(
            KLADY,
            24,
            where="MAPNOM='CTES96'",
            out_fields="MAPNOM,MAPNAME,PODIL",
            out_sr="EPSG:5514",
        )

        assert len(features) == 1
        (url,), kwargs = session.get.call_args
        assert url == f"{KLADY}/24/query"
        params = kwargs["params"]
        assert params["f"] == "json"
        assert params["where"] == "MAPNOM='CTES96'"
        assert params["outFields"] == "MAPNOM,MAPNAME,PODIL"
        assert params["outSR"] == "5514"
        assert params["resultOffset"] == "0"
        assert "geometry" not in params

    def test_bbox_query_builds_envelope(self):
        session = Mock()
        session.get.return_value = _json_response({"features": []})
        client = CuzkClient(session=session)

        client.query(
            KLADY, 26, bbox=BBox(744000, 5540000, 760000, 5556000, "EPSG:3045")
        )

        params = session.get.call_args.kwargs["params"]
        assert params["geometry"] == "744000,5540000,760000,5556000"
        assert params["geometryType"] == "esriGeometryEnvelope"
        assert params["inSR"] == "3045"
        assert params["spatialRel"] == "esriSpatialRelIntersects"

    def test_pagination_follows_exceeded_transfer_limit(self):
        session = Mock()
        page1 = {
            "features": [_feature("AAAA01"), _feature("AAAA02")],
            "exceededTransferLimit": True,
        }
        page2 = {"features": [_feature("AAAA03")]}
        session.get.side_effect = [_json_response(page1), _json_response(page2)]
        client = CuzkClient(session=session)

        features = client.query(KLADY, 24, where="1=1")

        assert [f["attributes"]["MAPNOM"] for f in features] == [
            "AAAA01",
            "AAAA02",
            "AAAA03",
        ]
        assert session.get.call_count == 2
        first_params = session.get.call_args_list[0].kwargs["params"]
        assert first_params["resultRecordCount"] == str(CuzkClient.QUERY_PAGE_SIZE)
        second_params = session.get.call_args_list[1].kwargs["params"]
        assert second_params["resultOffset"] == "2"

    def test_arcgis_error_payload_raises(self):
        session = Mock()
        session.get.return_value = _json_response(
            {"error": {"code": 400, "message": "Invalid query"}}
        )
        client = CuzkClient(session=session)
        with pytest.raises(DownloadError, match="Invalid query"):
            client.query(KLADY, 24, where="zle")

    def test_real_fixture_shape_parses(self):
        """Fixture z rekonesansu (Zad. 1) przechodzi przez query 1:1."""
        fixture = json.loads(
            Path("tests/fixtures/cuzk/klady_sm5_where_ctes96.json").read_text(
                encoding="utf-8"
            )
        )
        session = Mock()
        session.get.return_value = _json_response(fixture)
        features = CuzkClient(session=session).query(KLADY, 24, where="MAPNOM='CTES96'")
        assert features[0]["attributes"]["MAPNOM"] == "CTES96"


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestFetchFile:
    def _client_with_zip(self, tmp_path, zip_content: bytes):
        def fake_download(session, url, output_path, *, timeout, **kwargs):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(zip_content)
            return Path(output_path)

        return fake_download

    def test_plain_download_delegates_to_download_to(self, tmp_path):
        target = tmp_path / "plik.laz"
        with patch(_DOWNLOAD_TO_PATCH) as mock_dl:
            mock_dl.return_value = target
            result = CuzkClient(session=Mock()).fetch_file("http://x/plik.laz", target)
        assert result == target
        assert mock_dl.call_count == 1

    def test_unzip_single_extracts_tif_and_tfw(self, tmp_path):
        zip_content = _zip_bytes(
            {"CTES96.tif": b"II*\x00tifdata", "CTES96.tfw": b"5\n0\n0\n-5\n1\n2\n"}
        )
        target = tmp_path / "CTES96.tif"
        fake_download = self._client_with_zip(tmp_path, zip_content)
        with patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download):
            result = CuzkClient(session=Mock()).fetch_file(
                "http://x/CTES96.zip", target, unzip_single=".tif"
            )
        assert result == target
        assert target.read_bytes() == b"II*\x00tifdata"
        assert (tmp_path / "CTES96.tfw").read_bytes().startswith(b"5\n")
        # ZIP posprzatany
        assert list(tmp_path.glob("*.zip")) == []

    def test_unzip_single_without_expected_file_raises(self, tmp_path):
        zip_content = _zip_bytes({"readme.txt": b"nic"})
        target = tmp_path / "CTES96.tif"
        fake_download = self._client_with_zip(tmp_path, zip_content)
        with (
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
            pytest.raises(DownloadError, match="1 pliku"),
        ):
            CuzkClient(session=Mock()).fetch_file(
                "http://x/CTES96.zip", target, unzip_single=".tif"
            )
        assert not target.exists()
        # ZIP i ewentualne pliki tymczasowe posprzatane po bledzie
        assert list(tmp_path.glob("*.zip")) == []
        assert list(tmp_path.glob("*.tmp")) == []

    def test_corrupted_zip_raises_download_error(self, tmp_path):
        target = tmp_path / "CTES96.tif"
        fake_download = self._client_with_zip(tmp_path, b"to nie zip")
        with (
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
            pytest.raises(DownloadError, match="ZIP"),
        ):
            CuzkClient(session=Mock()).fetch_file(
                "http://x/CTES96.zip", target, unzip_single=".tif"
            )
        assert not target.exists()
        # ZIP i ewentualne pliki tymczasowe posprzatane po bledzie
        assert list(tmp_path.glob("*.zip")) == []
        assert list(tmp_path.glob("*.tmp")) == []

    def test_unzip_single_tfw_extraction_failure_leaves_no_files(self, tmp_path):
        """Regresja (review Zad. 8): jesli ekstrakcja towarzyszacego .tfw
        zawiedzie PO udanej ekstrakcji .tif (np. OSError, dysk pelny), cala
        operacja ma byc atomowa jako calosc — na dysku nie moze zostac ani
        czesciowy .tif, ani osierocony .tfw, ani smieci tymczasowe/ZIP."""
        zip_content = _zip_bytes(
            {"CTES96.tif": b"II*\x00tifdata", "CTES96.tfw": b"5\n0\n0\n-5\n1\n2\n"}
        )
        target = tmp_path / "CTES96.tif"
        fake_download = self._client_with_zip(tmp_path, zip_content)

        import kartograf.providers.cuzk.client as client_module

        real_extract_to = client_module._extract_to
        calls = {"n": 0}

        def flaky_extract_to(zf, member, dest):
            calls["n"] += 1
            if calls["n"] == 2:
                # Druga ekstrakcja (towarzyszacy .tfw) pada - symulacja
                # OSError/dysk pelny PO tym, jak .tif juz zostal wypakowany
                # do pliku tymczasowego.
                raise OSError("disk full (symulowany)")
            real_extract_to(zf, member, dest)

        with (
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
            patch.object(client_module, "_extract_to", side_effect=flaky_extract_to),
            pytest.raises(DownloadError, match="Rozpakowanie"),
        ):
            CuzkClient(session=Mock()).fetch_file(
                "http://x/CTES96.zip", target, unzip_single=".tif"
            )

        assert calls["n"] == 2
        assert not target.exists()
        assert not (tmp_path / "CTES96.tfw").exists()
        assert list(tmp_path.glob("*.zip")) == []
        assert list(tmp_path.glob("*.tmp")) == []


class TestRetryPropagation:
    """Retry/backoff pochodzi z transport.download_to — spec 7:
    wyczerpanie prob => DownloadError."""

    def test_fetch_file_exhausts_retries(self, tmp_path):
        import requests as requests_lib

        session = Mock()
        session.get.side_effect = requests_lib.RequestException("padlo")
        with (
            patch("kartograf.transport.http.time.sleep") as mock_sleep,
            pytest.raises(DownloadError, match="3 probach"),
        ):
            CuzkClient(session=session).fetch_file(
                "http://x/CTES96.zip", tmp_path / "CTES96.zip"
            )
        assert session.get.call_count == 3
        assert mock_sleep.call_count == 2


DMR5G = "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"

# CRS faktycznie zwracany przez exportImage CUZK (rekonesans Zad. 1, krok 4):
# LOCAL_CS zamiast PROJCS — GDAL nie rozwiazuje go do kodu EPSG mimo poprawnego
# AUTHORITY. Uzywany w fixture'ach TestExportImage zamiast zwyklego
# "EPSG:3045", zeby testy CRS-nadpisania faktycznie wykrywaly regresje: przy
# hardkodowanym z gory poprawnym CRS-ie asercja `to_epsg() == 3045` przechodzi
# nawet po usunieciu wywolania _overwrite_crs z export_image (reproduce
# potwierdzone standalone przy review).
_UNRESOLVABLE_CRS_WKT = (
    'LOCAL_CS["S-JTSK / Krovak East North",'
    'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
    'AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","5514"]]'
)
assert rasterio.crs.CRS.from_wkt(_UNRESOLVABLE_CRS_WKT).to_epsg() is None, (
    "sanity: fixture CRS musi byc nierozwiazywalny do EPSG, inaczej test nie "
    "wykryje regresji nadpisania CRS"
)


def _write_geotiff(
    path: Path,
    bbox: BBox,
    width: int,
    height: int,
    value: float = 100.0,
    nodata: float = -9999.0,
    crs: str = "EPSG:3045",
) -> None:
    """Syntetyczny GeoTIFF float32 pokrywajacy bbox (do testow mozaiki)."""
    from rasterio.transform import from_bounds

    transform = from_bounds(
        bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, width, height
    )
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": width,
        "height": height,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    data = np.full((height, width), value, dtype="float32")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


class TestExportImage:
    def test_single_shot_url_params(self, tmp_path):
        captured = {}

        def fake_download(session, url, output_path, *, timeout, **kwargs):
            captured["url"] = url
            # Poprawka 2 (rekonesans): export_image nadpisuje CRS bezwarunkowo
            # po kazdym eksporcie (rasterio "r+"), wiec fixture musi byc
            # naprawde otwieralnym GeoTIFF-em, nie tylko 4-bajtowym naglowkiem
            # sniffowanym po magic number. CRS ustawiony na nierozwiazywalny
            # (jak realna odpowiedz CUZK) — patrz asercja PO nizej.
            _write_geotiff(Path(output_path), bbox, 2, 2, crs=_UNRESOLVABLE_CRS_WKT)
            return Path(output_path)

        target = tmp_path / "out.tif"
        bbox = BBox(302000, 5550000, 304000, 5552000, "EPSG:3045")
        with patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download):
            CuzkClient(session=Mock()).export_image(
                DMR5G,
                bbox,
                pixel_size=2.0,
                image_sr="EPSG:3045",
                output_path=target,
            )

        parsed = urlparse(captured["url"])
        assert parsed.path.endswith("/exportImage")
        params = parse_qs(parsed.query)
        assert params["f"] == ["image"]
        assert params["format"] == ["tiff"]
        assert params["pixelType"] == ["F32"]
        assert params["bbox"] == ["302000,5550000,304000,5552000"]
        assert params["bboxSR"] == ["3045"]
        assert params["imageSR"] == ["3045"]
        assert params["size"] == ["1000,1000"]
        assert params["noData"] == ["-9999"]
        assert params["noDataInterpretation"] == ["esriNoDataMatchAny"]
        # CRS nadpisany bezwarunkowo (rekonesans: to_epsg() bezuzyteczne dla
        # obu SR zwracanych przez CUZK — patrz docs/research/...krok 4-5).
        # Fixture PRZED nadpisaniem miala to_epsg()==None (_UNRESOLVABLE_CRS_WKT
        # sanity-checkowany wyzej) — ta asercja wiec faktycznie dowodzi, ze
        # _overwrite_crs zadzialal, a nie tylko przepisal juz-poprawny CRS.
        with rasterio.open(target) as src:
            assert src.crs.to_epsg() == 3045

    def test_non_tiff_response_raises_with_content(self, tmp_path):
        def fake_download(session, url, output_path, *, timeout, **kwargs):
            Path(output_path).write_bytes(b'{"error":{"code":400,"message":"Bad"}}')
            return Path(output_path)

        target = tmp_path / "out.tif"
        bbox = BBox(0, 0, 100, 100, "EPSG:5514")
        with (
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
            pytest.raises(DownloadError, match="error"),
        ):
            CuzkClient(session=Mock()).export_image(
                DMR5G,
                bbox,
                pixel_size=2.0,
                image_sr="EPSG:5514",
                output_path=target,
            )
        assert not target.exists()

    def test_tiling_above_limits_mosaics(self, tmp_path):
        """Patch limitow na male wartosci: bbox 8x8 px przy limicie 4x4
        => 4 kafle 4x4, kazdy z tym samym noData, zszyte mosaic_and_crop."""
        requested = []

        def fake_download(session, url, output_path, *, timeout, **kwargs):
            params = parse_qs(urlparse(url).query)
            tile_bbox = [float(v) for v in params["bbox"][0].split(",")]
            w, h = (int(v) for v in params["size"][0].split(","))
            requested.append((tile_bbox, w, h, params["noData"][0]))
            # CRS nierozwiazywalny (jak realna odpowiedz CUZK dla kazdego
            # kafla) — patrz asercja PO nizej i sanity-check przy
            # _UNRESOLVABLE_CRS_WKT.
            _write_geotiff(
                Path(output_path),
                BBox(
                    tile_bbox[0], tile_bbox[1], tile_bbox[2], tile_bbox[3], "EPSG:3045"
                ),
                w,
                h,
                value=float(len(requested)),
                crs=_UNRESOLVABLE_CRS_WKT,
            )
            return Path(output_path)

        target = tmp_path / "mosaic.tif"
        bbox = BBox(0, 0, 16, 16, "EPSG:3045")  # 8x8 px przy pixel_size=2
        client = CuzkClient(session=Mock())
        with (
            patch.object(CuzkClient, "MAX_EXPORT_WIDTH", 4),
            patch.object(CuzkClient, "MAX_EXPORT_HEIGHT", 4),
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
        ):
            client.export_image(
                DMR5G,
                bbox,
                pixel_size=2.0,
                image_sr="EPSG:3045",
                output_path=target,
            )

        assert len(requested) == 4
        assert all(nd == "-9999" for (_, _, _, nd) in requested)
        with rasterio.open(target) as src:
            assert src.width == 8 and src.height == 8
            assert src.bounds == (0.0, 0.0, 16.0, 16.0)
            assert src.nodata == -9999.0
            # Kazdy kafel mial to_epsg()==None (LOCAL_CS) przed mozaika/
            # nadpisaniem — ta asercja dowodzi, ze _overwrite_crs zadzialal
            # po mosaic_and_crop, a nie ze przepisal juz-poprawny CRS.
            assert src.crs.to_epsg() == 3045
        # pliki czastkowe posprzatane
        assert list(tmp_path.glob("*.part*.tif")) == []

    def test_tiling_with_crs_mismatch_raises(self, tmp_path):
        bbox = BBox(0, 0, 16, 16, "EPSG:5514")
        client = CuzkClient(session=Mock())
        with (
            patch.object(CuzkClient, "MAX_EXPORT_WIDTH", 4),
            patch.object(CuzkClient, "MAX_EXPORT_HEIGHT", 4),
            pytest.raises(ValidationError, match="image_sr"),
        ):
            client.export_image(
                DMR5G,
                bbox,
                pixel_size=2.0,
                image_sr="EPSG:2180",
                output_path=tmp_path / "x.tif",
            )
