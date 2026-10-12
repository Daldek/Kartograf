"""Tests of campaign identity (ADR-030, kartograf/download/campaigns.py).

Fixture ``72675_858113_N-33-69-A-d-3-2.head.xyz``: a real GUGiK file 72675
(.xyz, in fact an AAIGrid, 34.8 MB) truncated to the header + 40 values of
the 7th row (448 B, CRLF); GDAL opens it as a 2131x2399 AAIGrid.
"""

import dataclasses
import hashlib
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kartograf.core.sheet_parser import SheetParser
from kartograf.download import campaigns as campaign_module
from kartograf.download.campaigns import (
    RECORD_VERTICAL_CRS,
    CampaignRef,
    campaign_extension,
    campaign_id_from_url,
    in_year_range,
    measure_coverage,
    record_year,
    validate_year_bounds,
    verify_file_format,
    verify_record_url,
    verify_record_vertical_crs,
    verify_sheet_extent,
    year_range_error,
    year_range_hints,
    year_range_label,
)
from kartograf.exceptions import DownloadError, ValidationError, YearRangeError
from kartograf.providers.pl.skorowidz import (
    SkorowidzRecord,
    parse_skorowidz_records,
    select_campaign_records,
)

URL = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83233/83233_1744736_N-34-139-C-a-3-1.asc"

ASC_FORMAT = "ARC/INFO ASCII GRID"
XYZ_HEAD = (
    Path(__file__).parent / "fixtures/gugik_asc/72675_858113_N-33-69-A-d-3-2.head.xyz"
)
ASC_HEAD = (
    Path(__file__).parent / "fixtures/gugik_asc/77912_1384976_7.125.11.19.head.asc"
)

C14 = Path(__file__).parent / "fixtures/gugik_skorowidz/real_2026_10_06/nmt/c14"


def _c14_years(suffix: int) -> tuple[int, ...]:
    sheet = f"N-34-139-C-a-3-{suffix}"
    records = [
        record
        for path in C14.glob(f"{sheet}_EVRF2007_*.html")
        for record in parse_skorowidz_records(
            path.read_text(encoding="utf-8"), path.stem
        )
    ]
    matching = select_campaign_records(
        records, sheet=sheet, system="1992", resolution_m=1.0
    )
    return tuple(
        sorted(
            {year for record in matching if (year := record_year(record)) is not None}
        )
    )


def _rec(url=URL, aktualnosc="2025-04-27", dt="2025-11-17", full=True, raw=None):
    return SimpleNamespace(
        url=url,
        sheet="N-34-139-C-a-3-1",
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


def test_coverage_of_asc_counts_nodata(tmp_path, monkeypatch):
    path = tmp_path / "x.asc"
    header = "ncols 3\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\n"
    path.write_text(header + "NODATA_value -1\n1 -1 2\n3 -1 4\n")
    assert measure_coverage(path, ".asc") == 0.6667
    path.write_text(header + "1 -9999 2\n3 -9999 4\n")
    assert measure_coverage(path, ".asc") == 0.6667
    # The token "-9999" spans multiple reads; the count must not drift.
    monkeypatch.setattr(campaign_module, "_COVERAGE_CHUNK", 2)
    assert measure_coverage(path, ".asc") == 0.6667
    path.write_text(header + "1 -9999 2\n3 -9999\n")
    with pytest.raises(DownloadError, match="5 komorek"):
        measure_coverage(path, ".asc")


def test_coverage_of_tif_without_nodata_is_none(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "x.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=3,
        count=1,
        dtype="uint8",
        transform=from_origin(0, 2, 1, 1),
    ) as dst:
        dst.write(np.array([[1, 0, 2], [3, 0, 4]], dtype="uint8"), 1)
    assert measure_coverage(path, ".tif") is None


def test_coverage_of_tif_with_nodata_uses_mask(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "x.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=3,
        count=1,
        dtype="uint8",
        nodata=0,
        transform=from_origin(0, 2, 1, 1),
    ) as dst:
        dst.write(np.array([[1, 0, 2], [3, 0, 4]], dtype="uint8"), 1)
    assert measure_coverage(path, ".tif") == 0.6667


def test_coverage_of_tif_with_alpha_uses_mask(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.enums import ColorInterp
    from rasterio.transform import from_origin

    path = tmp_path / "rgba.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=4,
        dtype="uint8",
        transform=from_origin(0, 2, 1, 1),
    ) as dst:
        for band in range(1, 4):
            dst.write(np.ones((2, 2), dtype="uint8"), band)
        dst.write(np.array([[255, 0], [255, 255]], dtype="uint8"), 4)
        dst.colorinterp = (
            ColorInterp.red,
            ColorInterp.green,
            ColorInterp.blue,
            ColorInterp.alpha,
        )
    assert measure_coverage(path, ".tif") == 0.75


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
    "min_year,max_year",
    [
        (1899, None),
        (2101, None),
        (True, None),
        ("2024", None),
        (None, 1899),
        (None, 2101),
        (None, True),
        (2025, 2023),
    ],
)
def test_validate_year_bounds_rejects_invalid_ranges(min_year, max_year):
    with pytest.raises(ValidationError):
        validate_year_bounds(min_year, max_year)


@pytest.mark.parametrize(
    "min_year,max_year",
    [(None, None), (2023, 2024), (2024, None)],
)
def test_validate_year_bounds_accepts_valid_ranges(min_year, max_year):
    validate_year_bounds(min_year, max_year)


def test_in_year_range_boundaries():
    assert in_year_range(2023, 2023, 2024)
    assert in_year_range(2024, 2023, 2024)
    assert not in_year_range(2022, 2023, 2024)
    assert not in_year_range(2025, 2023, 2024)
    assert in_year_range(2024, None, 2024)
    assert in_year_range(2024, 2024, None)
    assert in_year_range(2024, None, None)
    assert not in_year_range(None, None, None)


def test_record_year_prefers_aktualnosc_rok():
    path = C14 / "N-34-139-C-a-3-1_EVRF2007_SkorowidzeNMT2025.html"
    record = next(
        r
        for r in parse_skorowidz_records(path.read_text(encoding="utf-8"), path.stem)
        if "84183_" in r.url
    )
    assert record_year(record) == 2025
    assert (
        record_year(dataclasses.replace(record, raw={"aktualnoscRok": "2024"})) == 2024
    )
    assert record_year(dataclasses.replace(record, raw={})) == 2025
    assert (
        record_year(
            dataclasses.replace(
                record, aktualnosc="nieznana", raw={"aktualnoscRok": ""}
            )
        )
        is None
    )


@pytest.mark.parametrize(
    "suffixes,min_year,max_year,hints",
    [
        ((2,), 2018, 2018, ("--min-year 2018 (rok 2018 i nowsze)",)),
        ((1,), 2026, 2026, ("--max-year 2026 (rok 2026 i starsze)",)),
        (
            (1, 3),
            2024,
            2024,
            (
                "--min-year 2024 (rok 2024 i nowsze)",
                "--max-year 2024 (rok 2024 i starsze)",
            ),
        ),
        ((1, 3), 2026, 2026, ("--max-year 2026 (rok 2026 i starsze)",)),
        ((1, 3), 2026, None, ("--min-year 2025 (rok 2025 i nowsze)",)),
        (
            (3,),
            2023,
            2024,
            (
                "--min-year 2023 (rok 2023 i nowsze)",
                "--max-year 2024 (rok 2024 i starsze)",
            ),
        ),
    ],
)
def test_year_range_hints_spec_cases(suffixes, min_year, max_year, hints):
    years = {f"N-34-139-C-a-3-{suffix}": _c14_years(suffix) for suffix in suffixes}
    assert year_range_hints(years, min_year, max_year) == hints


def test_year_range_error_lists_years_and_truncates():
    conflicts = {
        "N-34-139-C-a-3-1": _c14_years(1),
        "N-34-139-C-a-3-3": _c14_years(3),
    }
    error = year_range_error(conflicts, 2024, 2024, total=4)
    assert isinstance(error, YearRangeError)
    assert isinstance(error, DownloadError)
    assert "z roku 2024 dla 2 z 4 arkuszy" in str(error)
    assert "N-34-139-C-a-3-1: dostepne roczniki 2019, 2023, 2025" in str(error)
    assert "N-34-139-C-a-3-3: dostepne roczniki 2019, 2025" in str(error)
    assert error.sheets == conflicts
    assert error.min_year == error.max_year == 2024
    assert error.hints == (
        "--min-year 2024 (rok 2024 i nowsze)",
        "--max-year 2024 (rok 2024 i starsze)",
    )
    assert "Podpowiedz: " + " albo ".join(error.hints) in str(error)

    many = {f"N-34-139-C-a-3-{i:02d}": (2019, 2025) for i in range(25)}
    truncated = year_range_error(many, 2024, 2024, total=25)
    assert len(truncated.sheets) == 25
    assert (
        len(
            [
                line
                for line in str(truncated).splitlines()
                if "dostepne roczniki" in line
            ]
        )
        == 20
    )
    assert "... i 5 innych" in str(truncated)


@pytest.mark.parametrize(
    "min_year,max_year,label",
    [
        (2024, 2024, "z roku 2024"),
        (2026, None, "od roku 2026"),
        (None, 2020, "do roku 2020"),
        (2023, 2024, "z lat 2023-2024"),
    ],
)
def test_year_range_label(min_year, max_year, label):
    assert year_range_label(min_year, max_year) == label


def test_verify_file_format_oserror_is_download_error(tmp_path):
    """M-2: a read ``OSError`` (missing file, directory) -> ``DownloadError``."""
    with pytest.raises(DownloadError, match="missing.asc"):
        verify_file_format(tmp_path / "missing.asc", ".asc")
    (tmp_path / "dir.tif").mkdir()
    with pytest.raises(DownloadError, match="dir.tif"):
        verify_file_format(tmp_path / "dir.tif", ".tif")


GUGIK_ASC = Path(__file__).parent / "fixtures" / "gugik_asc"


def _asc_for_frame(
    path, sheet, *, shift_x=0.0, shift_y=0.0, shrink=1.0, center=False, cell=1.0
):
    """ASC whose extent is the sheet frame (optionally shifted/shrunk)."""
    b = SheetParser(sheet).get_bbox()
    width = (b.max_x - b.min_x) * shrink
    height = (b.max_y - b.min_y) * shrink
    ncols, nrows = round(width / cell), round(height / cell)
    x0, y0 = b.min_x + shift_x, b.min_y + shift_y
    kx, ky = ("xllcenter", "yllcenter") if center else ("xllcorner", "yllcorner")
    off = cell / 2 if center else 0.0
    path.write_text(
        f"ncols {ncols}\nnrows {nrows}\n{kx} {x0 + off}\n{ky} {y0 + off}\n"
        f"cellsize {cell}\nNODATA_value -9999\n"
    )
    return path


class TestVerifyRecordUrl:
    def test_url_with_sheet_passes(self):
        verify_record_url(
            "https://x/NMT/1/73044_1234_N-34-130-D-d-2-4.asc", "N-34-130-D-d-2-4"
        )

    def test_pl2000_url_passes(self):
        verify_record_url("https://x/64878_364829_7.124.07.24.tif", "7.124.07.24")

    def test_url_without_sheet_raises(self):
        with pytest.raises(DownloadError, match="nie zawiera godla"):
            verify_record_url("https://x/NMT/84183/84183_1_G.asc", "N-34-130-D-d-2-4")

    def test_url_with_other_sheet_raises(self):
        with pytest.raises(DownloadError, match="nie zawiera godla"):
            verify_record_url("https://x/1_2_N-34-130-D-d-2-3.asc", "N-34-130-D-d-2-4")


class TestVerifySheetExtent:
    G = "N-34-130-D-d-2-4"

    def test_matching_sheet_passes(self, tmp_path):
        verify_sheet_extent(_asc_for_frame(tmp_path / "a.asc", self.G), self.G, ".asc")

    def test_center_variant_passes(self, tmp_path):
        p = _asc_for_frame(tmp_path / "a.asc", self.G, center=True)
        verify_sheet_extent(p, self.G, ".asc")

    def test_center_header_half_cell_correction(self, tmp_path):
        """P9b: with a coarse 600 m cell the half-cell shift of an
        ``xllcenter`` header decides the 50 % frame overlap both ways."""
        # corner 400 m off: 65 % overlap (without the correction 47 %)
        inside = _asc_for_frame(
            tmp_path / "in.asc", self.G, shift_x=400, shift_y=400, center=True, cell=600
        )
        verify_sheet_extent(inside, self.G, ".asc")
        # corner 700 m off: 47 % overlap (a sign error would give 65 %)
        outside = _asc_for_frame(
            tmp_path / "out.asc",
            self.G,
            shift_x=700,
            shift_y=700,
            center=True,
            cell=600,
        )
        with pytest.raises(DownloadError, match="zasieg"):
            verify_sheet_extent(outside, self.G, ".asc")

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

    def test_pl2000_sheet_with_2180_file_of_other_place_raises(self, tmp_path):
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


REAL_NMT = (
    Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06" / "nmt"
)
VFIELD = "ukladWspolrzednychPionowych"


def _real_records(pattern: str) -> list:
    """Records of raw GUGiK index bodies (``REAL_NMT`` glob), unfiltered."""
    return [
        record
        for path in sorted(REAL_NMT.glob(pattern))
        for record in parse_skorowidz_records(
            path.read_text(encoding="utf-8"), path.stem.rsplit("_", 1)[-1]
        )
    ]


KRON86_RECORDS = _real_records("*/nmt1_krn__*.body")
EVRF2007_RECORDS = _real_records("*/*_evr__*.body") + _real_records("c14/*.html")


def _declaring(record, value):
    """The record with the vertical datum field set to ``value`` (None = no field)."""
    raw = {k: v for k, v in record.raw.items() if k != VFIELD}
    if value is not None:
        raw[VFIELD] = value
    return dataclasses.replace(record, raw=raw)


class TestVerifyRecordVerticalCrs:
    """0.7.1: the record must declare the vertical datum of the request."""

    def test_mapping_equals_values_of_real_records(self):
        """Measured, not guessed: every raw record of a KRON86/EVRF2007 index."""
        assert KRON86_RECORDS and EVRF2007_RECORDS
        assert {r.raw[VFIELD] for r in KRON86_RECORDS} == {
            RECORD_VERTICAL_CRS["KRON86"]
        }
        assert {r.raw[VFIELD] for r in EVRF2007_RECORDS} == {
            RECORD_VERTICAL_CRS["EVRF2007"]
        }

    def test_every_real_record_passes_for_its_own_index(self):
        for record in KRON86_RECORDS:
            verify_record_vertical_crs(record, "KRON86", record.sheet)
        for record in EVRF2007_RECORDS:
            verify_record_vertical_crs(record, "EVRF2007", record.sheet)

    @pytest.mark.parametrize(
        ("records", "requested"),
        [(KRON86_RECORDS, "EVRF2007"), (EVRF2007_RECORDS, "KRON86")],
    )
    def test_other_datum_raises_naming_sheet_and_both_datums(self, records, requested):
        record = records[0]
        with pytest.raises(DownloadError) as exc:
            verify_record_vertical_crs(record, requested, record.sheet)
        message = str(exc.value)
        assert record.sheet in message
        assert f"deklaruje uklad wysokosci {record.raw[VFIELD]}" in message
        assert f"zadano {requested}" in message
        assert RECORD_VERTICAL_CRS[requested] in message
        assert exc.value.sheet == record.sheet

    @pytest.mark.parametrize("value", [None, "", "  "])
    def test_missing_or_empty_field_is_accepted_with_debug_log(self, value, caplog):
        record = _declaring(KRON86_RECORDS[0], value)
        with caplog.at_level(logging.DEBUG, logger="kartograf.download.campaigns"):
            verify_record_vertical_crs(record, "EVRF2007", record.sheet)
        assert "niesprawdzony" in caplog.text

    def test_case_and_whitespace_of_declared_value_are_tolerated(self):
        record = _declaring(EVRF2007_RECORDS[0], " pl-evrf2007-nh ")
        verify_record_vertical_crs(record, "EVRF2007", record.sheet)

    @pytest.mark.parametrize("requested", [None, "Bpv"])
    def test_request_without_known_datum_is_not_checked(self, requested):
        """Orto (no vertical datum) and datums outside the mapping."""
        record = KRON86_RECORDS[0]
        verify_record_vertical_crs(record, requested, record.sheet)

    def test_record_restored_from_cache_keeps_the_check(self):
        """Cache round trip (A3 ``declared_vertical_crs`` -> raw field again)."""
        cached = SkorowidzRecord.from_source(KRON86_RECORDS[0].to_source("https://wms"))
        with pytest.raises(DownloadError, match="PL-KRON86-NH"):
            verify_record_vertical_crs(cached, "EVRF2007", cached.sheet)
