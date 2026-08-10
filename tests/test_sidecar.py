"""Testy sidecara metadanych (kartograf.sources.sidecar)."""

import json
import logging

from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import (
    ResultMetadata,
    build_metadata,
    read_asc_nodata,
    write_sidecar,
)


class TestBuildMetadata:
    def test_godlo_request_nmt(self, tmp_path):
        asc = tmp_path / "N-34-130-D-d-2-4.asc"
        asc.write_text(
            "ncols 10\nnrows 10\nxllcorner 0\nyllcorner 0\n"
            "cellsize 1\nNODATA_value -9999\n"
        )
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"godlo": "N-34-130-D-d-2-4"},
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
        assert meta.request == {"godlo": "N-34-130-D-d-2-4"}
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
            get_source("pl.gugik.orto"), request={"godlo": "N-34-130-D-d-2-4"}
        )
        assert meta.vertical_crs is None
        assert meta.resolution is None

    def test_extra_fields(self):
        meta = build_metadata(
            get_source("pl.gugik.laz"),
            request={"bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:2180"},
            vertical_crs="KRON86",
            extra={"godlo_kafla": "N-33-131-B-a-1-1-4", "rok": 2024},
        )
        assert meta.vertical_crs == "EPSG:9650"
        assert meta.extra["rok"] == 2024


class TestWriteSidecar:
    def _meta(self) -> ResultMetadata:
        return build_metadata(
            get_source("pl.gugik.orto"), request={"godlo": "N-34-130-D-d-2-4"}
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
