"""Source editions — the ``metadata`` signal of SoilGrids and CORINE (D29)."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.corine import CorineProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.edition import Edition, edition_label

FIXTURES = Path(__file__).parent.parent / "fixtures" / "signals" / "real_2026_10_12"
CAPABILITIES = (FIXTURES / "isric_soilgrids_capabilities_get.xml").read_bytes()
CATALOGUE = json.loads((FIXTURES / "clms_corine_2018_search.json").read_text())


def _session(*, content: bytes = b"", payload: object = None, status: int = 200):
    response = Mock()
    response.status_code = status
    response.content = content
    response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status}", response=response
        )
    session = Mock()
    session.get.return_value = response
    return session


@pytest.mark.parametrize("raw", ["", "2.0 beta", "a/b", "v1\n"])
def test_edition_label_rejects_unsafe(raw):
    with pytest.raises(DownloadError, match="etykiete"):
        edition_label(raw, what="X")


def test_edition_label_accepts_release_ids():
    assert edition_label("V2020_20u1", what="X") == "V2020_20u1"
    assert edition_label("2.0+2.1", what="X") == "2.0+2.1"


def test_edition_to_extra_skips_none():
    assert Edition("2.0", "https://x").to_extra() == {"id": "2.0", "url": "https://x"}
    assert Edition("V1", "u", dataset_uid="abc").to_extra() == {
        "id": "V1",
        "url": "u",
        "dataset_uid": "abc",
    }


class TestSoilGridsEdition:
    def test_from_recorded_capabilities(self):
        session = _session(content=CAPABILITIES)
        edition = SoilGridsProvider(session=session).edition("clay")
        assert edition.id == "2.0"
        assert edition.title == "SoilGrids250m 2.0 - Clay content"
        assert "map=/map/clay.map" in edition.url
        assert "REQUEST=GetCapabilities" in edition.url
        assert session.get.call_count == 1
        assert session.get.call_args.args[0] == edition.url

    def test_unknown_title_is_download_error(self):
        xml = CAPABILITIES.replace(b"SoilGrids250m 2.0 - ", b"Soil maps ")
        with pytest.raises(DownloadError, match="brak wydania"):
            SoilGridsProvider(session=_session(content=xml)).edition("clay")

    def test_broken_xml_is_download_error(self):
        with pytest.raises(DownloadError, match="XML"):
            SoilGridsProvider(session=_session(content=b"<oops")).edition("clay")

    def test_http_error_is_download_error(self):
        session = _session(status=404)
        with pytest.raises(DownloadError):
            SoilGridsProvider(session=session).edition("clay")
        assert session.get.call_count == 1  # 4xx: no retries

    def test_unknown_property_rejected_before_network(self):
        session = _session(content=CAPABILITIES)
        with pytest.raises(ValidationError):
            SoilGridsProvider(session=session).edition("gold")
        session.get.assert_not_called()


class TestCorineEdition:
    def test_from_recorded_catalogue(self):
        session = _session(payload=CATALOGUE)
        edition = CorineProvider(session=session, use_proxy=False).edition(2018)
        assert edition.id == "V2020_20u1"
        assert edition.dataset_uid == "0407d497d3c44bcd93ce8fd5bf78596a"
        assert edition.url == (
            "https://land.copernicus.eu/api/@search"
            "?UID=0407d497d3c44bcd93ce8fd5bf78596a&fullobjects=1"
        )

    def test_without_credentials_sends_no_token(self):
        session = _session(payload=CATALOGUE)
        CorineProvider(session=session, use_proxy=False).edition(2018)
        headers = session.get.call_args.kwargs["headers"]
        assert headers == {"Accept": "application/json"}
        assert "Authorization" not in headers

    def test_no_record_is_download_error(self):
        session = _session(payload={"items": [], "items_total": 0})
        with pytest.raises(DownloadError, match="1 rekordu"):
            CorineProvider(session=session, use_proxy=False).edition(2012)

    def test_record_without_release_is_download_error(self):
        record = dict(CATALOGUE["items"][0])
        del record["characteristics_release_major_version"]
        session = _session(payload={"items": [record], "items_total": 1})
        with pytest.raises(DownloadError, match="characteristics_release"):
            CorineProvider(session=session, use_proxy=False).edition(2018)

    def test_preview_only_year_is_validation_error(self):
        session = _session(payload=CATALOGUE)
        with pytest.raises(ValidationError):
            CorineProvider(session=session, use_proxy=False).edition(1990)
        session.get.assert_not_called()

    def test_uids_match_catalogue(self):
        """docs/research/2026-10-12-plan3-spec-check/raport.md, UID table."""
        assert CorineProvider.CLMS_DATASET_UIDS == {
            2018: "0407d497d3c44bcd93ce8fd5bf78596a",
            2012: "a5ee71470be04d66bcff498f94ceb5dc",
            2006: "d443c86fec2f49e08ff12c7decdbf2af",
            2000: "6704f90ca82e4f228a46111519f8978e",
        }
        assert CorineProvider.CLMS_RASTER_DOWNLOAD_IDS == {
            2018: "7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb",
            2012: "b1027c88-6256-435b-98a3-62f019cbb381",
            2006: "4841f8cb-6e7c-4227-bb35-cd787609c546",
            2000: "19d7fbd8-53ee-4d09-89b6-fe5231247763",
        }

    @pytest.mark.parametrize(
        ("token", "year", "expected"),
        [(True, 2018, True), (True, 1990, False), (False, 2018, False)],
    )
    def test_uses_clms(self, token, year, expected):
        with patch.object(CorineProvider, "has_clms_token", new=token):
            assert CorineProvider(use_proxy=False).uses_clms(year) is expected


@pytest.mark.live
def test_live_soilgrids_edition():
    provider = SoilGridsProvider()
    ids = {provider.edition(p).id for p in ("clay", "sand", "silt")}
    assert len(ids) == 1
    edition_label(ids.pop(), what="SoilGrids")


@pytest.mark.live
def test_live_corine_edition_2018():
    edition = CorineProvider(use_proxy=False).edition(2018)
    assert edition.dataset_uid == CorineProvider.CLMS_DATASET_UIDS[2018]
    edition_label(edition.id, what="CORINE")
