"""Tests of the product variant registry (kartograf.sources.variants, ADR-041).

The registry is the only definition of what a PL elevation product offers
(resolutions, height systems, file formats); validation, ``--help``,
``list-sources``, the storage segment and the record filter read it.
"""

from collections import defaultdict
from decimal import Decimal

import pytest

from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source, resolve_vertical_crs, sources_for
from kartograf.sources.variants import (
    ProductVariant,
    find_variant,
    parse_resolution,
    resolution_label,
    source_format,
    variant_error,
    variants,
)

_E = ("EVRF2007",)
_K = ("KRON86",)
_EK = ("EVRF2007", "KRON86")

# Product contract from the WFS inventory 2026-10-15 (plan A, decisions 3 and
# 13): every ASC grid and every archive format the GUGiK indexes publish on
# sheets of the PL-1992/PL-2000 systems, with their height systems.
_PL_INVENTORY_TABLE: list[tuple[str, str, str | None, tuple[str, ...]]] = [
    # ASC grids
    ("nmt", "ASC", "0.15m", _E),
    ("nmt", "ASC", "0.5m", _EK),
    ("nmt", "ASC", "0.6m", _E),
    ("nmt", "ASC", "1m", _EK),
    ("nmt", "ASC", "5m", _E),
    ("nmt", "ASC", "10m", _E),
    ("nmpt", "ASC", "0.5m", _EK),
    ("nmpt", "ASC", "0.6m", _E),
    ("nmpt", "ASC", "1m", _EK),
    # archives downloaded as source files
    ("nmt", "XYZ", "1m", _EK),
    ("nmt", "XYZ", "5m", _E),
    ("nmt", "ASCII-NMT", "0.5m", _E),
    ("nmt", "ASCII-NMT", "1m", _E),
    ("nmt", "ASCII-NMT", "5m", _EK),
    ("nmt", "TBD", "1m", _EK),
    ("nmt", "TBD", "5m", _EK),
    ("nmt", "TBD", "10m", _EK),
    ("nmt", "TBD", "15m", _EK),
    ("nmt", "TBD", "20m", _EK),
    ("nmt", "TBD", "25m", _EK),
    ("nmt", "TBD", "30m", _K),
    ("nmt", "TBD", "40m", _K),
    ("nmt", "TBD", "50m", _K),
    ("nmt", "TIN", None, _K),
    ("nmt", "TTN", None, _K),
    ("nmt", "GRD", "5m", _K),
    ("nmt", "DXF", "25m", _K),
    ("nmt", "DGN", "25m", _K),
    ("nmpt", "XYZ", "0.5m", _K),
    ("nmpt", "XYZ", "1m", _K),
    # point clouds (tiles, no resolution)
    ("laz", "LAZ", None, _EK),
]

PL_INVENTORY = {
    (product, fmt, label, vertical_crs)
    for product, fmt, label, systems in _PL_INVENTORY_TABLE
    for vertical_crs in systems
}

PL_VARIANTS = variants(country="PL")


def _variant_id(v: ProductVariant) -> str:
    return f"{v.product}-{v.format}-{v.label}-{v.vertical_crs}"


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (Decimal("0.15"), "0.15m"),
        (Decimal("0.5"), "0.5m"),
        (Decimal("0.50"), "0.5m"),
        (Decimal("1"), "1m"),
        (Decimal("10"), "10m"),
        (Decimal("50"), "50m"),
    ],
)
def test_label_round_trip(value, label):
    assert resolution_label(value) == label
    assert parse_resolution(label) == value


@pytest.mark.parametrize("text", ["0,5m", "50cm", "0.50m", "5", "5 m", "", "1.0m"])
def test_parse_resolution_accepts_only_canonical_labels(text):
    assert parse_resolution(text) is None


def test_pl_registry_matches_inventory():
    found = {(v.product, v.format, v.label, v.vertical_crs) for v in PL_VARIANTS}
    assert found == PL_INVENTORY
    # one entry per choice: no two variants share (product, format, label, CRS)
    assert len(PL_VARIANTS) == len(PL_INVENTORY)


@pytest.mark.parametrize("variant", PL_VARIANTS, ids=_variant_id)
def test_variant_source_is_descriptor(variant):
    descriptor = get_source(variant.source)
    assert descriptor.country == variant.country
    assert descriptor.product == variant.product
    assert descriptor.resolution == variant.label
    assert variant in descriptor.variants
    sheets = next(c for c in descriptor.channels if c.transport == variant.channel)
    options = sheets.vertical_crs_options
    assert resolve_vertical_crs(variant.vertical_crs, options) in options


def test_index_ref_is_one_service_per_product_and_height_system():
    refs = defaultdict(set)
    for v in PL_VARIANTS:
        assert v.channel == TransportKind.WFS
        assert v.index_ref is not None
        refs[(v.product, v.vertical_crs)].add(v.index_ref)
    assert set(refs) == {
        (product, vcrs) for product in ("nmt", "nmpt", "laz") for vcrs in _EK
    }
    for (_product, vcrs), found in refs.items():
        assert len(found) == 1
        (ref,) = found
        assert ref.endpoint.endswith(f"{vcrs}/WFS/Skorowidze")
    # every (product, height system) asks its own service
    endpoints = [next(iter(found)).endpoint for found in refs.values()]
    assert len(set(endpoints)) == len(endpoints)


_OPENDATA = "https://opendata.geoportal.gov.pl/NumDaneWys"


@pytest.mark.parametrize(
    ("record_format", "url", "token"),
    [
        (
            "ARC/INFO ASCII GRID",
            f"{_OPENDATA}/NMT/73843/73843_1036985_N-33-58-A-c-1-4.asc",
            "ASC",
        ),
        # the 42 grids of campaign 72675 have a `.xyz` name (AAIGrid inside)
        (
            "ARC/INFO ASCII GRID",
            f"{_OPENDATA}/NMT/72675/72675_858106_N-33-69-A-d-1-3.xyz",
            "ASC",
        ),
        (
            "ASCII XYZ GRID",
            f"{_OPENDATA}/NMT/3647/3647_66584_N-33-58-A-c-1-4.xyz.zip",
            "XYZ",
        ),
        (
            "ASCII NMT",
            f"{_OPENDATA}/NMT/72674/72674_858064_N-33-69-A-d-1-3.zip",
            "ASCII-NMT",
        ),
        (
            "ASCII TBD",
            f"{_OPENDATA}/NMT/5119/5119_368708_N-33-58-A-c-1_asc.zip",
            "TBD",
        ),
        ("ESRI TIN", f"{_OPENDATA}/NMT/4510/4510_370143_N-33-58-A-c-1_tin.zip", "TIN"),
        (
            "Intergraph TTN",
            f"{_OPENDATA}/NMT/4511/4511_373294_N-33-58-A-c-1.ttn",
            "TTN",
        ),
        (
            "Intergraph GRD",
            f"{_OPENDATA}/NMT/4512/4512_373000_N-33-58-A-c-1.grd",
            "GRD",
        ),
        ("Warstwice DXF", f"{_OPENDATA}/NMT/4513/4513_372870_N-33-58-A-c-1.dxf", "DXF"),
        ("Warstwice DGN", f"{_OPENDATA}/NMT/4514/4514_372871_N-33-58-A-c-1.dgn", "DGN"),
        # archive format with a grid URL, an unzipped XYZ archive and a grid
        # format with an archive URL
        ("ASCII XYZ GRID", f"{_OPENDATA}/NMT/1/1_2_N-33-58-A-c-1-4.asc", None),
        ("ASCII XYZ GRID", f"{_OPENDATA}/NMT/1/1_2_N-33-58-A-c-1-4.xyz", None),
        ("ARC/INFO ASCII GRID", f"{_OPENDATA}/NMT/1/1_2_N-33-58-A-c-1-4_asc.zip", None),
        # formats outside the registry and a record without a format
        ("LAS", f"{_OPENDATA}/NMT/1/1_2_N-33-58-A-c-1-4.asc", None),
        (None, f"{_OPENDATA}/NMT/1/1_2_N-33-58-A-c-1-4.asc", None),
    ],
)
def test_source_format_requires_url_of_the_format(record_format, url, token):
    assert source_format(record_format, url) == token


def test_wcs_only_for_1m():
    with_wcs = {
        d.key
        for d in sources_for(country="PL")
        if d.product in ("nmt", "nmpt")
        and any(c.transport == TransportKind.WCS for c in d.channels)
    }
    assert with_wcs == {"pl.gugik.nmt_1m", "pl.gugik.nmpt"}
    for key in with_wcs:
        assert get_source(key).resolution == "1m"
        assert {v.format for v in get_source(key).variants} == {"ASC"}


def test_variants_filters_combine():
    found = variants(country="PL", product="nmt", resolution="0.5m")
    assert {(v.format, v.vertical_crs) for v in found} == {
        ("ASC", "EVRF2007"),
        ("ASC", "KRON86"),
        ("ASCII-NMT", "EVRF2007"),
    }
    assert {v.source for v in variants(product="nmpt", format="XYZ")} == {
        "pl.gugik.nmpt_xyz_0_5m",
        "pl.gugik.nmpt_xyz_1m",
    }
    assert variants(country="PL", system="2000") == PL_VARIANTS
    assert variants(country="PL", system="sm5") == ()


@pytest.mark.parametrize("variant", PL_VARIANTS, ids=_variant_id)
def test_every_variant_is_found_by_its_choice(variant):
    assert (
        find_variant(
            product=variant.product,
            country=variant.country,
            resolution=variant.label,
            vertical_crs=variant.vertical_crs,
            format=variant.format,
        )
        == variant
    )


@pytest.mark.parametrize(
    ("product", "fmt", "resolution", "vertical_crs", "source", "label"),
    [
        # no --format = the ASC grid
        ("nmt", None, "0.5m", "KRON86", "pl.gugik.nmt_0_5m", "0.5m"),
        ("nmpt", None, "1m", "EVRF2007", "pl.gugik.nmpt", "1m"),
        # resolution may be omitted when the choice leaves one label
        ("nmt", "GRD", None, "KRON86", "pl.gugik.nmt_grd_5m", "5m"),
        ("nmt", "XYZ", None, "KRON86", "pl.gugik.nmt_xyz_1m", "1m"),
        ("nmt", "TIN", None, "KRON86", "pl.gugik.nmt_tin", None),
        ("nmt", "TTN", None, "KRON86", "pl.gugik.nmt_ttn", None),
        ("nmpt", "XYZ", "0.5m", "KRON86", "pl.gugik.nmpt_xyz_0_5m", "0.5m"),
        ("laz", None, None, "KRON86", "pl.gugik.laz", None),
    ],
)
def test_find_variant_unique_choice(
    product, fmt, resolution, vertical_crs, source, label
):
    v = find_variant(
        product=product,
        country="PL",
        resolution=resolution,
        vertical_crs=vertical_crs,
        format=fmt,
    )
    assert (v.source, v.label, v.vertical_crs) == (source, label, vertical_crs)
    assert v.format == (fmt or ("LAZ" if product == "laz" else "ASC"))


_NMT_LABELS = "EVRF2007: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; KRON86: 0.5m, 1m"
_NMPT_LABELS = "EVRF2007: 0.5m, 0.6m, 1m; KRON86: 0.5m, 1m"


@pytest.mark.parametrize(
    ("product", "fmt", "resolution", "vertical_crs", "message"),
    [
        # resolution of another height system
        (
            "nmt",
            None,
            "5m",
            "KRON86",
            "NMT 5m (PL) jest dostepny tylko w EVRF2007 - podano --vertical-crs "
            "KRON86; dostepne w KRON86: 0.5m, 1m",
        ),
        # resolution absent from the product
        (
            "nmpt",
            None,
            "5m",
            "EVRF2007",
            f"PL nie ma rozdzielczosci 5m dla NMPT - dostepne: {_NMPT_LABELS}",
        ),
        # a non-canonical label is not a label of the registry
        (
            "nmt",
            None,
            "0.50m",
            "EVRF2007",
            f"PL nie ma rozdzielczosci 0.50m dla NMT - dostepne: {_NMT_LABELS}",
        ),
        # several labels left: --resolution required
        (
            "nmpt",
            None,
            None,
            "EVRF2007",
            f"--resolution wymagane dla NMPT PL: {_NMPT_LABELS}",
        ),
        (
            "nmt",
            "TBD",
            None,
            "KRON86",
            "--resolution wymagane dla NMT TBD PL: EVRF2007: 1m, 5m, 10m, 15m, "
            "20m, 25m; KRON86: 1m, 5m, 10m, 15m, 20m, 25m, 30m, 40m, 50m",
        ),
        # format not available for the product
        (
            "nmpt",
            "TBD",
            "1m",
            "EVRF2007",
            "--format TBD: niedostepny dla NMPT PL - dostepne: ASC, XYZ",
        ),
        (
            "nmt",
            "LAS",
            "1m",
            "EVRF2007",
            "--format LAS: niedostepny dla NMT PL - dostepne: ASC, XYZ, ASCII-NMT, "
            "TBD, TIN, TTN, GRD, DXF, DGN",
        ),
        # height system not available for the format / product
        (
            "nmt",
            "GRD",
            None,
            "EVRF2007",
            "NMT GRD (PL) jest dostepny tylko w KRON86 - podano --vertical-crs "
            "EVRF2007",
        ),
        (
            "nmt",
            None,
            "1m",
            "Bpv",
            "NMT (PL) jest dostepny tylko w EVRF2007, KRON86 - podano "
            "--vertical-crs Bpv",
        ),
        # a format without resolution in the index
        (
            "nmt",
            "TIN",
            "5m",
            "KRON86",
            "--resolution nie dotyczy NMT TIN (skorowidz nie podaje rozdzielczosci) "
            "- pomin --resolution",
        ),
    ],
)
def test_variant_error_names_flags_and_registry_values(
    product, fmt, resolution, vertical_crs, message
):
    choice = {
        "product": product,
        "country": "PL",
        "resolution": resolution,
        "vertical_crs": vertical_crs,
        "format": fmt,
    }
    assert variant_error(**choice) == message
    with pytest.raises(ValidationError) as exc:
        find_variant(**choice)
    assert str(exc.value) == message


def test_variant_error_without_vertical_crs_checks_resolution_in_any_system():
    # 0.15m exists only in EVRF2007 - still a valid label before the CRS is known
    assert (
        variant_error(
            product="nmt", country="PL", resolution="0.15m", vertical_crs=None
        )
        is None
    )
    assert variant_error(
        product="nmt", country="PL", resolution="3m", vertical_crs=None
    ) == (f"PL nie ma rozdzielczosci 3m dla NMT - dostepne: {_NMT_LABELS}")


def test_variant_error_for_country_without_variants():
    # plan B adds CZ variants; a country outside the registry has none
    assert (
        variant_error(product="nmt", country="DE", resolution="1m", vertical_crs=None)
        == "--product nmt nie ma wariantow w DE"
    )
