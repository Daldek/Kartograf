"""Testy sidecara metadanych (kartograf.sources.sidecar)."""

import json
import logging
from pathlib import Path

import pytest

from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source, horizontal_crs_for_uklad
from kartograf.sources.sidecar import (
    ResultMetadata,
    _select_channel_by_capability,
    build_metadata,
    pl_sheet_horizontal_crs,
    read_asc_nodata,
    write_sidecar,
)


def _asc(path, xllcorner: float, key: str = "xllcorner") -> None:
    path.write_text(
        f"ncols 10\nnrows 10\n{key} {xllcorner}\nyllcorner 500000\n"
        "cellsize 1\nNODATA_value -9999\n"
    )


class TestPlSheetHorizontalCrs:
    """N8: sidecar arkusza PL-2000 opisuje strefe (EPSG:2176-2179), nie 2180."""

    def test_pl2000_sheet_sidecar_carries_zone_crs(self, tmp_path):
        asc = tmp_path / "6.179.12.20.asc"
        _asc(asc, 6_500_000.0)
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"sheet": "6.179.12.20"},
            vertical_crs="EVRF2007",
            data_path=asc,
        )
        assert meta.horizontal_crs == "EPSG:2177"
        assert meta.nodata == -9999.0

    @pytest.mark.parametrize(
        ("godlo", "expected"),
        [
            ("5.176.14", "EPSG:2176"),
            ("7.124.07.24", "EPSG:2178"),
            ("8.170.10", "EPSG:2179"),
            ("N-34-130-D-d-2-4", "EPSG:2180"),
        ],
    )
    def test_without_file_zone_comes_from_godlo(self, godlo, expected):
        meta = build_metadata(get_source("pl.gugik.orto"), request={"sheet": godlo})
        assert meta.horizontal_crs == expected
        assert pl_sheet_horizontal_crs(None, godlo) == expected

    def test_pl1992_sheet_with_pl1992_coordinates_stays_2180(self, tmp_path, caplog):
        asc = tmp_path / "M-34-76-A-a-2-4.asc"
        _asc(asc, 542_560.30, key="xllcenter")
        with caplog.at_level(logging.WARNING):
            assert pl_sheet_horizontal_crs(asc, "M-34-76-A-a-2-4") == "EPSG:2180"
        assert "zapisano uklad pliku" not in caplog.text

    def test_file_in_other_system_wins_with_warning(self, tmp_path, caplog):
        """K4: plik PL-1992 pod godlem PL-2000 (cache sprzed 0.7.0) — uklad pliku."""
        asc = tmp_path / "7.123.8.asc"
        _asc(asc, 542_560.30)
        with caplog.at_level(logging.WARNING):
            meta = build_metadata(
                get_source("pl.gugik.nmt_1m"),
                request={"sheet": "7.123.8"},
                vertical_crs="EVRF2007",
                data_path=asc,
            )
        assert meta.horizontal_crs == "EPSG:2180"
        assert "7.123.8" in caplog.text
        assert "EPSG:2178" in caplog.text
        assert "EPSG:2180" in caplog.text

    def test_unreadable_file_falls_back_to_godlo(self, tmp_path):
        missing = tmp_path / "6.179.12.20.asc"
        assert pl_sheet_horizontal_crs(missing, "6.179.12.20") == "EPSG:2177"

    def test_pl2000_tif_is_checked_with_rasterio(self, tmp_path, caplog):
        import rasterio
        from rasterio.transform import from_origin

        tif = tmp_path / "7.124.07.24.tif"
        with rasterio.open(
            tif,
            "w",
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="uint8",
            transform=from_origin(7_540_000.0, 5_530_000.0, 0.25, 0.25),
        ):
            pass  # pusty raster: liczy sie tylko georeferencja
        with caplog.at_level(logging.WARNING):
            meta = build_metadata(
                get_source("pl.gugik.orto"),
                request={"sheet": "7.124.07.24"},
                data_path=tif,
            )
        assert meta.horizontal_crs == "EPSG:2178"
        assert "zapisano uklad pliku" not in caplog.text

        # ten sam TIF pod godlem PL-1992 = rozjazd: uklad pliku + ostrzezenie
        with caplog.at_level(logging.WARNING):
            assert pl_sheet_horizontal_crs(tif, "M-34-76-A-a-1-1") == "EPSG:2178"
        assert "zapisano uklad pliku" in caplog.text

    def test_explicit_horizontal_crs_overrides_channel_and_godlo(self, tmp_path):
        asc = tmp_path / "6.179.12.20.asc"
        _asc(asc, 6_500_000.0)
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"sheet": "6.179.12.20"},
            data_path=asc,
            horizontal_crs="EPSG:5514",
        )
        assert meta.horizontal_crs == "EPSG:5514"

    def test_laz_tile_crs_from_uklad_xy(self):
        """Kafel LAZ: godlo myslnikowe, dane w PL-2000:S6 — uklad z uklad_xy."""
        meta = build_metadata(
            get_source("pl.gugik.laz"),
            request={"bbox": [530500, 382500, 531000, 383000], "bbox_crs": "EPSG:2180"},
            vertical_crs="EVRF2007",
            extra={"tile_sheet": "N-33-131-B-a-1-1-4"},
            horizontal_crs=horizontal_crs_for_uklad("PL-2000:S6"),
        )
        assert meta.horizontal_crs == "EPSG:2177"

    def test_non_sheet_pl_product_keeps_channel_crs(self):
        """BDOT10k po godle PL-2000 to GPKG w EPSG:2180 — godlo tylko wybiera obszar."""
        meta = build_metadata(
            get_source("pl.gugik.bdot10k"), request={"sheet": "6.179.12"}
        )
        assert meta.horizontal_crs == "EPSG:2180"

    def test_cz_sheet_request_keeps_channel_crs(self):
        meta = build_metadata(get_source("cz.cuzk.dmr4g"), request={"sheet": "CTES96"})
        assert meta.horizontal_crs == "EPSG:5514"


class TestBuildMetadata:
    def test_godlo_request_nmt(self, tmp_path):
        asc = tmp_path / "N-34-130-D-d-2-4.asc"
        asc.write_text(
            "ncols 10\nnrows 10\nxllcorner 0\nyllcorner 0\n"
            "cellsize 1\nNODATA_value -9999\n"
        )
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"sheet": "N-34-130-D-d-2-4"},
            vertical_crs="EVRF2007",
            data_path=asc,
        )
        assert meta.schema == "kartograf-meta/1"
        assert meta.dataset == "pl.gugik.nmt_1m"
        assert meta.country == "PL"
        assert meta.product == "nmt"
        assert meta.provider == "GUGiK"
        assert meta.horizontal_crs == "EPSG:2180"
        assert meta.vertical_crs == "EPSG:9651"
        assert meta.vertical_source == "native"
        assert meta.resolution == "1m"
        assert meta.nodata == -9999.0
        assert meta.request == {"sheet": "N-34-130-D-d-2-4"}
        assert meta.license["id"] == "PL-PGiK-40a"
        assert meta.transform is None
        assert meta.downloaded_at.endswith("+00:00")
        assert meta.kartograf_version

    def test_bbox_request_selects_bbox_channel(self):
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={
                "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
                "bbox_crs": "EPSG:2180",
            },
            vertical_crs="EVRF2007",
        )
        assert meta.horizontal_crs == "EPSG:2180"
        assert meta.nodata is None
        assert meta.request["bbox_crs"] == "EPSG:2180"

    def test_no_vertical_for_orto(self):
        meta = build_metadata(
            get_source("pl.gugik.orto"), request={"sheet": "N-34-130-D-d-2-4"}
        )
        assert meta.vertical_crs is None
        assert meta.resolution is None

    def test_extra_fields(self):
        meta = build_metadata(
            get_source("pl.gugik.laz"),
            request={"bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:2180"},
            vertical_crs="KRON86",
            extra={"tile_sheet": "N-33-131-B-a-1-1-4", "year": 2024},
        )
        assert meta.vertical_crs == "EPSG:9650"
        assert meta.extra["year"] == 2024


class TestWriteSidecar:
    def _meta(self) -> ResultMetadata:
        return build_metadata(
            get_source("pl.gugik.orto"), request={"sheet": "N-34-130-D-d-2-4"}
        )

    def test_writes_full_filename_meta_json(self, tmp_path):
        data = tmp_path / "N-34-130-D-d-2-4.tif"
        data.write_bytes(b"x")
        out = write_sidecar(data, self._meta())
        assert out == tmp_path / "N-34-130-D-d-2-4.tif.meta.json"
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["schema"] == "kartograf-meta/1"
        assert payload["dataset"] == "pl.gugik.orto"
        assert payload["license"]["id"] == "PL-PGiK-40a"

    def test_write_failure_warns_and_does_not_raise(self, tmp_path, caplog):
        # Spec sekcja 8: wyjatki IO w write_sidecar lapane i logowane jako
        # warning — pobranie (wolajacy) dostaje wynik normalnie.
        data = tmp_path / "missing-dir" / "x.tif"
        with caplog.at_level(logging.WARNING):
            out = write_sidecar(data, self._meta())
        assert not out.exists()
        assert "sidecar" in caplog.text.lower()


class TestSelectChannelByCapability:
    # dmr4g (Zad. 3) ma dwa kanaly o TYM SAMYM horizontal_crs (EPSG:5514) —
    # ResultMetadata nie niesie pola transport, wiec asercje na samym
    # ResultMetadata nie odrozniaja poprawnej selekcji od heurystyki/ignorowania
    # `capability=`. Testujemy wiec `_select_channel_by_capability` bezposrednio
    # na zwroconym kanale (transport + capabilities) — patrz R5 w task brief.
    def test_sheet_files_returns_direct_files_channel(self):
        d = get_source("cz.cuzk.dmr4g")
        ch = _select_channel_by_capability(d, "sheet_files")
        assert ch.transport == TransportKind.DIRECT_FILES
        assert "sheet_files" in ch.capabilities

    def test_bbox_raster_returns_arcgis_image_channel(self):
        d = get_source("cz.cuzk.dmr4g")
        ch = _select_channel_by_capability(d, "bbox_raster")
        assert ch.transport == TransportKind.ARCGIS_IMAGE
        assert "bbox_raster" in ch.capabilities

    def test_unknown_capability_raises_keyerror(self):
        d = get_source("pl.gugik.orto")
        with pytest.raises(KeyError):
            _select_channel_by_capability(d, "bbox_raster")


class TestBuildMetadataCapabilityAndNodata:
    def test_capability_selects_named_channel(self):
        # Smoke test z briefu: oba kanaly dmr4g maja EPSG:5514, wiec ta
        # asercja sama w sobie nie dowodzi poprawnej selekcji (patrz
        # TestSelectChannelByCapability powyzej dla wlasciwego dowodu).
        d = get_source("cz.cuzk.dmr4g")
        meta_files = build_metadata(
            d, request={"sheet": "CTES96"}, capability="sheet_files"
        )
        assert meta_files.horizontal_crs == "EPSG:5514"
        meta_bbox = build_metadata(
            d, request={"sheet": "CTES96"}, capability="bbox_raster"
        )
        # oba kanaly dmr4g maja 5514; rozroznia je transport — sprawdzamy,
        # ze selekcja nie uzyla heurystyki bbox (request godlo + capability bbox)
        assert meta_bbox.horizontal_crs == "EPSG:5514"

    def test_capability_unknown_raises_keyerror(self):
        d = get_source("pl.gugik.orto")
        with pytest.raises(KeyError):
            build_metadata(d, request={"sheet": "X"}, capability="bbox_raster")

    def test_nodata_param_takes_precedence_over_asc_sniff(self, tmp_path):
        asc = tmp_path / "x.asc"
        asc.write_text(
            "ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\n"
            "cellsize 1\nNODATA_value -9999\n"
        )
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"sheet": "N-34-130-D-d-2-4"},
            data_path=asc,
            nodata=-8888.0,
        )
        assert meta.nodata == -8888.0

    def test_nodata_param_for_tif(self, tmp_path):
        meta = build_metadata(
            get_source("cz.cuzk.dmr5g"),
            request={"bbox": [1.0, 2.0, 3.0, 4.0], "bbox_crs": "EPSG:5514"},
            nodata=-9999.0,
        )
        assert meta.nodata == -9999.0
        assert meta.dataset == "cz.cuzk.dmr5g"
        assert meta.license["id"] == "CC-BY-4.0"


class TestReadAscNodata:
    def test_reads_nodata(self, tmp_path):
        p = tmp_path / "a.asc"
        p.write_text("ncols 2\nnrows 2\nNODATA_value -9999\n1 2\n3 4\n")
        assert read_asc_nodata(p) == -9999.0

    def test_missing_header_or_file(self, tmp_path):
        p = tmp_path / "b.asc"
        p.write_text("ncols 2\nnrows 2\n1 2\n3 4\n")
        assert read_asc_nodata(p) is None
        assert read_asc_nodata(tmp_path / "nie-ma.asc") is None


class TestPl2000SheetPublishedIn2180:
    """E17 (E2E-A C6b/C6h): GUGiK publikuje czesc arkuszy PL-2000 strefy 7
    we wspolrzednych EPSG:2180 z niecalkowitym ``cellsize``.

    Fixtura: naglowek + 2 wiersze surowego pliku GUGiK
    ``77912_1384976_7.125.11.19.asc`` (rekord ``PL-2000:S7``, 2023-03-17;
    ``xllcenter 567975.95``, ``cellsize 0.9993671653521061``). Oczekiwane:
    sidecar ``horizontal_crs`` = uklad PLIKU (EPSG:2180),
    ``extra.source.uklad`` = deklaracja rekordu, ostrzezenie, segment sciezki
    wg godla (``pl_2000_...``, ADR-026).
    """

    GODLO = "7.125.11.19"
    URL = (
        "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/77912/"
        "77912_1384976_7.125.11.19.asc"
    )
    FIXTURE = (
        Path(__file__).parent
        / "fixtures"
        / "gugik_asc"
        / "77912_1384976_7.125.11.19.head.asc"
    )

    def test_sidecar_describes_file_not_record(self, tmp_path, caplog):
        from unittest.mock import Mock, patch

        import requests

        from kartograf.download.manager import DownloadManager
        from kartograf.providers.pl.gugik import GugikProvider
        from tests.conftest import gfi_record, render_gfi_body

        body = render_gfi_body(
            [
                gfi_record(
                    self.GODLO,
                    uklad="PL-2000:S7",
                    aktualnosc="2023-03-17",
                    url=self.URL,
                )
            ]
        )
        raw = self.FIXTURE.read_bytes()

        def get(url, **kwargs):
            response = Mock(spec=requests.Response)
            response.status_code = 200
            response.raise_for_status = Mock()
            response.text = body
            response.iter_content = Mock(return_value=[raw])
            response.headers = {}
            return response

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=get)
        with (
            patch(
                "kartograf.transport.http.make_gugik_session",
                return_value=session,
            ),
            caplog.at_level(logging.WARNING, logger="kartograf.sources.sidecar"),
        ):
            manager = DownloadManager(output_dir=tmp_path, provider=GugikProvider())
            path = manager.download_sheet(self.GODLO)

        assert path.relative_to(tmp_path).parts[:2] == ("nmt", "pl_2000_1m_evrf2007")
        assert session.get.call_args_list[-1][0][0] == self.URL
        meta = json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))
        assert meta["horizontal_crs"] == "EPSG:2180"
        assert meta["extra"]["source"]["declared_crs"] == "PL-2000:S7"
        assert meta["nodata"] == -9999
        warning = next(r for r in caplog.records if "wskazuje" in r.message)
        assert warning.levelno == logging.WARNING
        assert "EPSG:2178" in warning.getMessage()
        assert "zapisano uklad pliku" in warning.getMessage()


class TestEmitSidecar:
    """D7: jedno opakowanie best-effort dla wszystkich torow."""

    def _data(self, tmp_path):
        path = tmp_path / "wynik.tif"
        path.write_bytes(b"II*\x00")
        return path

    def test_non_str_key_writes_nothing(self, tmp_path):
        from unittest.mock import Mock

        from kartograf.sources.sidecar import emit_sidecar

        data = self._data(tmp_path)
        assert emit_sidecar(Mock(), data, request={"sheet": "X"}) is None
        assert emit_sidecar(None, data, request={"sheet": "X"}) is None
        assert list(tmp_path.glob("*.meta.json")) == []

    def test_build_error_is_logged_not_raised(self, tmp_path, caplog):
        import logging

        from kartograf.sources.sidecar import emit_sidecar

        data = self._data(tmp_path)
        with caplog.at_level(logging.WARNING):
            result = emit_sidecar("brak.takiego.klucza", data, request={"bbox": [1]})
        assert result is None
        assert "Nie udalo sie zapisac sidecara" in caplog.text

    def test_pinned_transforms_and_horizontal_override(self, tmp_path):
        from types import SimpleNamespace

        from kartograf.sources.sidecar import emit_sidecar

        data = self._data(tmp_path)
        pinned = SimpleNamespace(description="S-JTSK to ETRS89 (1)", accuracy_m=1.0)
        sidecar = emit_sidecar(
            "cz.cuzk.dmr5g",
            data,
            request={"bbox": [0, 0, 1, 1], "bbox_crs": "EPSG:2180"},
            vertical_crs="Bpv",
            horizontal_crs="EPSG:2180",
            pinned_transforms={"horizontal": pinned, "vertical": None},
            capability="bbox_raster",
            nodata=-9999.0,
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["transform"] == {
            "horizontal": "pinned: S-JTSK to ETRS89 (1) (1.0 m)"
        }
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["nodata"] == -9999.0

    def test_only_none_transforms_give_null(self, tmp_path):
        from kartograf.sources.sidecar import emit_sidecar

        data = self._data(tmp_path)
        sidecar = emit_sidecar(
            "cz.cuzk.dmr5g",
            data,
            request={"bbox": [0, 0, 1, 1], "bbox_crs": "EPSG:5514"},
            pinned_transforms={"horizontal": None},
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["transform"] is None
