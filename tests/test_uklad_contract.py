"""
Contract of the single GUGiK horizontal CRS parser (review-1 D3, E11).

The CRS field value (``ukladWspolrzednychPoziomych``/``ukladWspolrzednych``
of the WMS index (orthophoto), ``uklad_xy`` of the WFS index (NMT/NMPT) and
of the LAZ WFS) is read in four places: the index records (sheet file
selection), ``horizontal_crs_for_system`` (sidecar) and ``LazTile.system``
(storage segment). Each of them MUST give the same answer - otherwise a
``"PL-2000"`` tile without a zone ended up in ``laz/pl_2000_...`` with an
``EPSG:2180`` sidecar.

Real values (E2E 2026-10-06: 1131 index records, 294 LAZ tiles): only
``PL-1992`` and ``PL-2000:S5``..``S8``. Unusual ones are rejected
consistently: an index record without a CRS, ``horizontal_crs_for_system`` =
``None``, a LAZ tile skipped in discovery, and ``LazTile.system`` =
``ValidationError``.
"""

import xml.etree.ElementTree as ET

import pytest

from kartograf.exceptions import ValidationError
from kartograf.providers.pl.gugik_laz import LazTile, laz_tile
from kartograf.providers.pl.skorowidz import parse_skorowidz_records
from kartograf.providers.pl.skorowidz_wfs import parse_index_feature
from kartograf.sources.registry import horizontal_crs_for_system, parse_pl_system
from tests.conftest import gfi_record, render_gfi_body, render_wfs_body, wfs_record

REAL = {
    "PL-1992": ("1992", None, "EPSG:2180"),
    "PL-2000:S5": ("2000", 5, "EPSG:2176"),
    "PL-2000:S6": ("2000", 6, "EPSG:2177"),
    "PL-2000:S7": ("2000", 7, "EPSG:2178"),
    "PL-2000:S8": ("2000", 8, "EPSG:2179"),
}
# Whitespace at the edges is tolerated (WFS trims it anyway); the rest rejected.
TOLERATED = {" PL-1992": REAL["PL-1992"], "PL-2000:S7 ": REAL["PL-2000:S7"]}
ATYPICAL = ["PL-2000", "PL-2000:S9", "PL-2000:S4", "pl-2000:s6", "PL-1992:S1", ""]
ATYPICAL += ["EPSG:2180", "PL-2000 S6", "PL-1992-NH"]


def _skorowidz_record(value: str):
    body = render_gfi_body([gfi_record("N-34-130-D-d-2-4", system=value)])
    (record,) = parse_skorowidz_records(body, "SkorowidzeNMT2025")
    return record


def _wfs_index_record(value: str):
    body = render_wfs_body([wfs_record("N-34-130-D-d-2-4", system=value)])
    (feature,) = [
        elem for elem in ET.fromstring(body).iter() if elem.tag.endswith("NMT2024")
    ]
    record = parse_index_feature(feature)
    assert record is not None
    return record


def _laz_tile(value: str) -> LazTile | None:
    xml = f"""<gugik:SkorowidzDanychPomiarowychLIDAR2024
        xmlns:gugik="http://www.gugik.gov.pl">
      <gugik:godlo>6.162.34.02.3</gugik:godlo>
      <gugik:akt_rok>2024</gugik:akt_rok>
      <gugik:char_przestrz>12 p/m2</gugik:char_przestrz>
      <gugik:uklad_xy>{value}</gugik:uklad_xy>
      <gugik:url_do_pobrania>https://x/81121_1_6.162.34.02.3.laz</gugik:url_do_pobrania>
    </gugik:SkorowidzDanychPomiarowychLIDAR2024>"""
    return laz_tile(ET.fromstring(xml))


def _hand_tile(value: str | None) -> LazTile:
    return LazTile("N-33-131-B-a-1-1-4", "u/f.laz", 2024, 12, value, 0, 0, 1, 1)


@pytest.mark.parametrize("value", [*REAL, *TOLERATED])
def test_known_value_same_answer_everywhere(value):
    system, zone, epsg = {**REAL, **TOLERATED}[value]

    assert parse_pl_system(value) == (system, zone)
    record = _skorowidz_record(value)
    assert (record.system, record.zone) == (system, zone)
    wfs = _wfs_index_record(value)
    assert (wfs.system, wfs.zone) == (system, zone)
    assert horizontal_crs_for_system(value) == epsg
    tile = _laz_tile(value)
    assert tile is not None and tile.system == system
    assert _hand_tile(value).system == system


@pytest.mark.parametrize("value", ATYPICAL)
def test_atypical_value_rejected_everywhere(value):
    assert parse_pl_system(value) is None
    assert _skorowidz_record(value).system is None
    assert _wfs_index_record(value).system is None
    assert horizontal_crs_for_system(value) is None
    # discovery skips the tile rather than write it to pl_2000 with a 2180 sidecar
    assert _laz_tile(value) is None
    with pytest.raises(ValidationError, match="uklad_xy"):
        _hand_tile(value).system  # noqa: B018 — the property raises


def test_missing_value_rejected():
    assert parse_pl_system(None) is None
    assert horizontal_crs_for_system(None) is None
    with pytest.raises(ValidationError, match="uklad_xy"):
        _hand_tile(None).system  # noqa: B018
