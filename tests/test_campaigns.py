"""Testy tozsamosci kampanii (ADR-030, kartograf/download/campaigns.py).

Fixtura ``72675_858113_N-33-69-A-d-3-2.head.xyz``: realny plik GUGiK 72675
(.xyz, w istocie AAIGrid, 34,8 MB) przyciety do naglowka + 40 wartosci
7. wiersza (448 B, CRLF); GDAL otwiera go jako AAIGrid 2131x2399.
"""

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kartograf.download.campaigns import (
    CampaignRef,
    campaign_extension,
    campaign_id_from_url,
    validate_campaign_args,
    verify_file_format,
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
    url = "https://example.org/NMT/2019/5.167.25.13.asc"  # katalog liczbowy
    assert campaign_id_from_url(url).startswith("u")


def test_ref_fields_dirname_and_extra():
    ref = CampaignRef.from_record(_rec())
    assert ref.dirname == "2025-04-27_83233"
    assert ref.year == 2025 and ref.file_format == ASC_FORMAT
    assert ref.to_extra() == {
        "id": "83233",
        "date": "2025-04-27",
        "zgloszenie": "GK-FOTO.6201.5.2025",
        "source": "Skaning laserowy",
        "full_sheet": True,
        "dt_pzgik": "2025-11-17",
    }


def test_ref_source_falls_back_to_zrodloDanych():
    assert (
        CampaignRef.from_record(_rec(raw={"zrodloDanych": "Zdjecia lotnicze"})).source
        == "Zdjecia lotnicze"
    )


# --- errata 2 N-2: format z pola `format` rekordu, nie z URL ---
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


def test_campaign_extension_missing_format_uses_product_default():  # orto, stary cache
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
)  # realne naglowki: xllcorner (72675) i xllcenter (77912)
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
        ),  # punkty XYZ != AAIGrid
        (b"", ".asc"),
        (b"TIFF header data\x00", ".tif"),
        (None, ".tif"),  # None = tresc XYZ_HEAD (AAIGrid) zapisana jako .tif
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
    )  # remis daty i dt_pzgik -> URL (ADR-028)


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
    assert a.sort_key > b.sort_key  # dt_pzgik wygrywa mimo mniejszego URL


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
    """M-2: ``OSError`` odczytu (brak pliku, katalog) -> ``DownloadError``."""
    with pytest.raises(DownloadError, match="missing.asc"):
        verify_file_format(tmp_path / "missing.asc", ".asc")
    (tmp_path / "dir.tif").mkdir()
    with pytest.raises(DownloadError, match="dir.tif"):
        verify_file_format(tmp_path / "dir.tif", ".tif")
