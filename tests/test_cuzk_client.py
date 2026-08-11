"""Testy CuzkClient — silnik ArcGIS REST + pliki openzu (offline)."""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
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
