"""Tests of campaign identity (ADR-030, kartograf/download/campaigns.py).

Fixture ``72675_858113_N-33-69-A-d-3-2.head.xyz``: a real GUGiK file 72675
(.xyz, in fact an AAIGrid, 34.8 MB) truncated to the header + 40 values of
the 7th row (448 B, CRLF); GDAL opens it as a 2131x2399 AAIGrid.
"""

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.campaigns import (
    CampaignRef,
    campaign_extension,
    campaign_id_from_url,
    validate_campaign_args,
    verify_file_format,
    verify_record_url,
    verify_sheet_extent,
)
from kartograf.exceptions import DownloadError, ValidationError

URL = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83233/83233_1744736_N-34-139-C-a-3-1.asc"

ASC_FORMAT = "ARC/INFO ASCII GRID"
XYZ_HEAD = (
    Path(__file__).parent / "fixtures/gugik_asc/72675_858113_N-33-69-A-d-3-2.head.xyz"
)
ASC_HEAD = (
    Path(__file__).parent / "fixtures/gugik_asc/77912_1384976_7.125.11.19.head.asc"
)


def _rec(url=URL, aktualnosc="2025-04-27", dt="2025-11-17", full=True, raw=None):
    return SimpleNamespace(
        url=url,
        godlo="N-34-139-C-a-3-1",
        aktualnosc=aktualnosc,
        dt_pzgik=dt,
        full_sheet=full,
        raw=raw
        if raw is not None
        else {
            "numerZgloszeniaPracy": "GK-FOTO.6201.5.2025",
            "zrDanych": "Skaning laserowy",
            "format": ASC_FORMAT,
        },
    )


@pytest.mark.parametrize(
    "url,expected",
    [
        (URL, "83233"),
        (
            "https://opendata.geoportal.gov.pl/ortofotomapa/84466/84466_1602825_M-34-90-C-b-4-4.tif",
            "84466",
        ),
        (
            "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/76969/76969_1297751_N-33-115-C-d-2-2.ASC",
            "76969",
        ),
        (
            "https://opendata.geoportal.gov.pl/ortofotomapa/23/23_176192_N-34-139-A-c-1.tif",
            "23",
        ),
    ],
)
def test_campaign_id_from_real_urls(url, expected):
    assert campaign_id_from_url(url) == expected


def test_campaign_id_without_numeric_prefix_is_sha1():
    url = "https://example.org/NMT/N-34-139-C-a-3-1.asc"
    assert campaign_id_from_url(url) == "u" + hashlib.sha1(url.encode()).hexdigest()[:8]


def test_campaign_id_ignores_digits_not_followed_by_underscore():
    url = "https://example.org/NMT/2019/5.167.25.13.asc"  # numeric directory
    assert campaign_id_from_url(url).startswith("u")


def test_ref_fields_dirname_and_extra():
    ref = CampaignRef.from_record(_rec())
    assert ref.dirname == "2025-04-27_83233"
    assert ref.year == 2025 and ref.file_format == ASC_FORMAT
    assert ref.to_extra() == {
        "id": "83233",
        "date": "2025-04-27",
        "survey_work_id": "GK-FOTO.6201.5.2025",
        "source": "Skaning laserowy",
        "full_sheet": True,
        "pzgik_date": "2025-11-17",
    }


def test_ref_source_falls_back_to_zrodloDanych():
    assert (
        CampaignRef.from_record(_rec(raw={"zrodloDanych": "Zdjecia lotnicze"})).source
        == "Zdjecia lotnicze"
    )


# --- errata 2 N-2: format from the record's `format` field, not from the URL ---
def test_real_xyz_record_72675_gets_canonical_asc():
    url = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/72675/72675_858113_N-33-69-A-d-3-2.xyz"
    ref = CampaignRef.from_record(
        _rec(url=url, aktualnosc="2019-04-29", dt="2019-08-09")
    )
    assert (ref.id, ref.dirname) == ("72675", "2019-04-29_72675")
    assert campaign_extension(ref, ".asc") == ".asc"


def test_uppercase_url_suffix_is_irrelevant():  # 76969 `.ASC`
    ref = CampaignRef.from_record(_rec(url="https://x/NMT/1/1_2_N-33-115-C-d-2-2.ASC"))
    assert campaign_extension(ref, ".asc") == ".asc"


def test_campaign_extension_missing_format_uses_product_default():  # orto, old cache
    ref = CampaignRef.from_record(_rec(raw={}))
    assert ref.file_format is None and campaign_extension(ref, ".tif") == ".tif"


@pytest.mark.parametrize(
    "fmt,default", [("XYZ ASCII", ".asc"), ("GeoTIFF", ".asc"), (ASC_FORMAT, ".tif")]
)
def test_campaign_extension_unknown_or_foreign_format_is_download_error(fmt, default):
    ref = CampaignRef.from_record(_rec(raw={"format": fmt}))
    with pytest.raises(DownloadError, match=re.escape(repr(fmt))):
        campaign_extension(ref, default)


@pytest.mark.parametrize(
    "path", [XYZ_HEAD, ASC_HEAD]
)  # real headers: xllcorner (72675) and xllcenter (77912)
def test_verify_file_format_accepts_real_aaigrid(path, tmp_path):
    dst = tmp_path / "x.asc"
    dst.write_bytes(path.read_bytes())
    verify_file_format(dst, ".asc")


def test_verify_file_format_accepts_tiff_signatures(tmp_path):
    for sig in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        f = tmp_path / "x.tif"
        f.write_bytes(sig + b"\x00" * 12)
        verify_file_format(f, ".tif")


@pytest.mark.parametrize(
    "body,ext",
    [
        (b"<html><body>404</body></html>", ".asc"),
        (
            b"314511.5 708632.5 -9999.0\n314512.5 708632.5 201.5\n",
            ".asc",
        ),  # XYZ points != AAIGrid
        (b"", ".asc"),
        (b"TIFF header data\x00", ".tif"),
        (None, ".tif"),  # None = XYZ_HEAD content (AAIGrid) saved as .tif
    ],
)
def test_verify_file_format_rejects_mismatch(body, ext, tmp_path):
    f = tmp_path / ("x" + ext)
    f.write_bytes(XYZ_HEAD.read_bytes() if body is None else body)
    with pytest.raises(DownloadError, match="tresc nie jest"):
        verify_file_format(f, ext)


def test_verify_file_format_unsupported_extension(tmp_path):
    f = tmp_path / "x.laz"
    f.write_bytes(b"ncols 1")
    with pytest.raises(DownloadError):
        verify_file_format(f, ".laz")


def test_same_date_different_id_distinct_dirs_and_order():
    a = CampaignRef.from_record(
        _rec(
            url="https://x/NMT/81467/81467_1_G.asc",
            aktualnosc="2025-04-04",
            dt="2025-06-04",
        )
    )
    b = CampaignRef.from_record(
        _rec(
            url="https://x/NMT/81468/81468_1_G.asc",
            aktualnosc="2025-04-04",
            dt="2025-06-04",
        )
    )
    assert a.dirname != b.dirname
    assert (
        max([a, b], key=lambda r: r.sort_key) is b
    )  # date and dt_pzgik tie -> URL (ADR-028)


def test_sort_key_uses_dt_pzgik_before_url():
    url_a = "https://x/NMT/81467/81467_1_G.asc"
    url_b = "https://x/NMT/81468/81468_1_G.asc"
    a = CampaignRef.from_record(
        _rec(url=url_a, aktualnosc="2025-04-04", dt="2025-06-05")
    )
    b = CampaignRef.from_record(
        _rec(url=url_b, aktualnosc="2025-04-04", dt="2025-06-04")
    )
    assert a.sort_key == ("2025-04-04", "2025-06-05", url_a)
    assert a.sort_key > b.sort_key  # dt_pzgik wins despite the smaller URL


def test_sort_key_date_beats_dt_pzgik():
    old = CampaignRef.from_record(_rec(aktualnosc="2025-04-27", dt="2026-12-31"))
    new = CampaignRef.from_record(
        _rec(
            url="https://x/NMT/84183/84183_1_G.asc",
            aktualnosc="2025-10-21",
            dt="2026-07-10",
        )
    )
    assert new.sort_key > old.sort_key


@pytest.mark.parametrize("bad", ["", "2025", "2025-4-27", "../etc", "2025-04-27T00:00"])
def test_invalid_aktualnosc_is_download_error(bad):
    with pytest.raises(DownloadError, match="aktualnosc"):
        CampaignRef.from_record(_rec(aktualnosc=bad))


@pytest.mark.parametrize(
    "campaigns,min_year",
    [("mosaic", None), ("newest", 1899), ("all", 2101), ("all", True), ("all", "2024")],
)
def test_validate_campaign_args_rejects(campaigns, min_year):
    with pytest.raises(ValidationError):
        validate_campaign_args(campaigns, min_year)


def test_validate_campaign_args_accepts():
    validate_campaign_args("newest", None)
    validate_campaign_args("all", 2024)


def test_verify_file_format_oserror_is_download_error(tmp_path):
    """M-2: a read ``OSError`` (missing file, directory) -> ``DownloadError``."""
    with pytest.raises(DownloadError, match="missing.asc"):
        verify_file_format(tmp_path / "missing.asc", ".asc")
    (tmp_path / "dir.tif").mkdir()
    with pytest.raises(DownloadError, match="dir.tif"):
        verify_file_format(tmp_path / "dir.tif", ".tif")


GUGIK_ASC = Path(__file__).parent / "fixtures" / "gugik_asc"


def _asc_for_frame(path, godlo, *, shift_x=0.0, shrink=1.0, center=False):
    """ASC whose extent is the godlo frame (optionally shifted/shrunk)."""
    b = SheetParser(godlo).get_bbox()
    width = (b.max_x - b.min_x) * shrink
    height = (b.max_y - b.min_y) * shrink
    cell = 1.0
    ncols, nrows = int(width), int(height)
    x0, y0 = b.min_x + shift_x, b.min_y
    kx, ky = ("xllcenter", "yllcenter") if center else ("xllcorner", "yllcorner")
    off = cell / 2 if center else 0.0
    path.write_text(
        f"ncols {ncols}\nnrows {nrows}\n{kx} {x0 + off}\n{ky} {y0 + off}\n"
        f"cellsize {cell}\nNODATA_value -9999\n"
    )
    return path


class TestVerifyRecordUrl:
    def test_url_with_godlo_passes(self):
        verify_record_url(
            "https://x/NMT/1/73044_1234_N-34-130-D-d-2-4.asc", "N-34-130-D-d-2-4"
        )

    def test_pl2000_url_passes(self):
        verify_record_url("https://x/64878_364829_7.124.07.24.tif", "7.124.07.24")

    def test_url_without_godlo_raises(self):
        with pytest.raises(DownloadError, match="nie zawiera godla"):
            verify_record_url("https://x/NMT/84183/84183_1_G.asc", "N-34-130-D-d-2-4")

    def test_url_with_other_godlo_raises(self):
        with pytest.raises(DownloadError, match="nie zawiera godla"):
            verify_record_url("https://x/1_2_N-34-130-D-d-2-3.asc", "N-34-130-D-d-2-4")


class TestVerifySheetExtent:
    G = "N-34-130-D-d-2-4"

    def test_matching_sheet_passes(self, tmp_path):
        verify_sheet_extent(_asc_for_frame(tmp_path / "a.asc", self.G), self.G, ".asc")

    def test_center_variant_passes(self, tmp_path):
        p = _asc_for_frame(tmp_path / "a.asc", self.G, center=True)
        verify_sheet_extent(p, self.G, ".asc")

    def test_partial_sheet_inside_frame_passes(self, tmp_path):
        """Review Focus 4: full_sheet=False sheet smaller than the frame."""
        p = _asc_for_frame(tmp_path / "a.asc", self.G, shrink=0.3)
        verify_sheet_extent(p, self.G, ".asc")

    def test_neighbour_sheet_raises(self, tmp_path):
        b = SheetParser(self.G).get_bbox()
        p = _asc_for_frame(tmp_path / "a.asc", self.G, shift_x=b.max_x - b.min_x)
        with pytest.raises(DownloadError, match="zasieg"):
            verify_sheet_extent(p, self.G, ".asc")

    def test_pl2000_sheet_in_zone_crs_passes(self, tmp_path):
        p = _asc_for_frame(tmp_path / "a.asc", "7.124.07.24")  # EPSG:2178 frame
        verify_sheet_extent(p, "7.124.07.24", ".asc")

    def test_pl2000_sheet_published_in_2180_passes(self):
        """E17: GUGiK publishes some zone-7 PL-2000 sheets in EPSG:2180."""
        head = GUGIK_ASC / "77912_1384976_7.125.11.19.head.asc"
        verify_sheet_extent(head, "7.125.11.19", ".asc")

    def test_pl2000_godlo_with_2180_file_of_other_place_raises(self, tmp_path):
        # EPSG:2180 header of N-34-130-D-d-2-4 - far from 7.124.07.24
        p = _asc_for_frame(tmp_path / "a.asc", self.G)
        with pytest.raises(DownloadError, match="zasieg"):
            verify_sheet_extent(p, "7.124.07.24", ".asc")

    def test_unreadable_header_raises(self, tmp_path):
        p = tmp_path / "a.asc"
        p.write_text("garbage\n")
        with pytest.raises(DownloadError, match="naglowek"):
            verify_sheet_extent(p, self.G, ".asc")

    def test_tif_not_checked(self, tmp_path):
        p = tmp_path / "a.tif"
        p.write_bytes(b"II*\x00")
        verify_sheet_extent(p, self.G, ".tif")
