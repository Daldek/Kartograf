"""
Contract of the single GUGiK horizontal CRS parser (review-1 D3, E11).

The CRS field value (``ukladWspolrzednychPoziomych``/``ukladWspolrzednych``
of the GUGiK index (skorowidz) and ``uklad_xy`` of the LAZ WFS) is read in
three places: the index record (sheet file selection),
``horizontal_crs_for_uklad`` (sidecar) and ``LazTile.uklad`` (storage
segment). Each of them MUST give the same answer - otherwise a ``"PL-2000"``
tile without a zone ended up in ``laz/pl_2000_...`` with an ``EPSG:2180``
sidecar.

Real values (E2E 2026-10-06: 1131 index records, 294 LAZ tiles): only
``PL-1992`` and ``PL-2000:S5``..``S8``. Unusual ones are rejected
consistently: an index record without a CRS, ``horizontal_crs_for_uklad`` =
``None``, a LAZ tile skipped in discovery, and ``LazTile.uklad`` =
``ValidationError``.
"""

import xml.etree.ElementTree as ET

import pytest

from kartograf.exceptions import ValidationError
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile
from kartograf.providers.pl.skorowidz import parse_skorowidz_records
from kartograf.sources.registry import horizontal_crs_for_uklad, parse_pl_uklad
from tests.conftest import gfi_record, render_gfi_body

REAL = {
    "PL-1992": ("1992", None, "EPSG:2180"),
    "PL-2000:S5": ("2000", 5, "EPSG:2176"),
    "PL-2000:S6": ("2000", 6, "EPSG:2177"),
    "PL-2000:S7": ("2000", 7, "EPSG:2178"),
    "PL-2000:S8": ("2000", 8, "EPSG:2179"),
}
# Biale znaki na brzegach sa tolerowane (WFS i tak je obcina); reszta odrzucona.
TOLERATED = {" PL-1992": REAL["PL-1992"], "PL-2000:S7 ": REAL["PL-2000:S7"]}
ATYPICAL = ["PL-2000", "PL-2000:S9", "PL-2000:S4", "pl-2000:s6", "PL-1992:S1", ""]
ATYPICAL += ["EPSG:2180", "PL-2000 S6", "PL-1992-NH"]


def _skorowidz_record(value: str):
    body = render_gfi_body([gfi_record("N-34-130-D-d-2-4", uklad=value)])
    (record,) = parse_skorowidz_records(body, "SkorowidzeNMT2025")
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
    return GugikLazProvider()._feature_to_tile(ET.fromstring(xml))


def _hand_tile(value: str | None) -> LazTile:
    return LazTile("N-33-131-B-a-1-1-4", "u/f.laz", 2024, 12, value, 0, 0, 1, 1)


@pytest.mark.parametrize("value", [*REAL, *TOLERATED])
def test_known_value_same_answer_everywhere(value):
    uklad, zone, epsg = {**REAL, **TOLERATED}[value]

    assert parse_pl_uklad(value) == (uklad, zone)
    record = _skorowidz_record(value)
    assert (record.uklad, record.zone) == (uklad, zone)
    assert horizontal_crs_for_uklad(value) == epsg
    tile = _laz_tile(value)
    assert tile is not None and tile.uklad == uklad
    assert _hand_tile(value).uklad == uklad


@pytest.mark.parametrize("value", ATYPICAL)
def test_atypical_value_rejected_everywhere(value):
    assert parse_pl_uklad(value) is None
    assert _skorowidz_record(value).uklad is None
    assert horizontal_crs_for_uklad(value) is None
    # discovery pomija kafel zamiast zapisac go do pl_2000 z sidecarem EPSG:2180
    assert _laz_tile(value) is None
    with pytest.raises(ValidationError, match="uklad_xy"):
        _hand_tile(value).uklad  # noqa: B018 — property rzuca


def test_missing_value_rejected():
    assert parse_pl_uklad(None) is None
    assert horizontal_crs_for_uklad(None) is None
    with pytest.raises(ValidationError, match="uklad_xy"):
        _hand_tile(None).uklad  # noqa: B018
