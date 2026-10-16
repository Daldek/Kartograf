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
from kartograf.sources.registry import (
    CZ_SYSTEM_CRS,
    channel_for,
    get_source,
    resolve_vertical_crs,
    sources_for,
)
from kartograf.sources.variants import (
    CZ_LAZ_VERTICAL_TEXT,
    CZ_MODELS,
    CZ_VERTICAL_TEXT,
    ProductVariant,
    cz_laz_error,
    cz_model_text,
    cz_resolution_text,
    cz_sheet_system,
    cz_variant_error,
    find_cz_laz_variant,
    find_cz_variant,
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
# sheets of the PL-1992/PL-2000 systems, with their height systems; plus the
# voivodeship files of the ATOM feed NMT 100 m (plan E1), whose height system
# GUGiK does not declare (decision P1: None).
_PL_INVENTORY_TABLE: list[tuple[str, str, str | None, tuple[str | None, ...]]] = [
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
    ("nmt", "ASCII-NMT", "10m", _E),
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
    # voivodeship files of the ATOM feed (no sheet index, no height system)
    ("nmt", "XYZ", "100m", (None,)),
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
    if variant.vertical_crs is None:  # no height system: the channel declares none
        assert options == ()
        assert variant.vertical_note
    else:
        assert resolve_vertical_crs(variant.vertical_crs, options) in options


def test_index_ref_is_one_service_per_product_and_height_system():
    refs = defaultdict(set)
    for v in PL_VARIANTS:
        if v.index_ref is None:  # the ATOM voivodeship files: no sheet index
            assert v.channel == TransportKind.DIRECT_FILES
            assert not v.source_file  # its format is the product format
            continue
        assert v.channel == TransportKind.WFS
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
    # every sheet variant may have PL-2000 sheets; the voivodeship files are
    # PL-1992 only
    assert variants(country="PL", system="2000") == tuple(
        v for v in PL_VARIANTS if v.index_ref is not None
    )
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


_NMT_LABELS = (
    "EVRF2007: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; KRON86: 0.5m, 1m; "
    "uklad wysokosci nieznany: 100m"
)
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


# =============================================================================
# CZ (plan B): rows of the route table (decision 2)
# =============================================================================

_F = TransportKind.DIRECT_FILES
_I = TransportKind.ARCGIS_IMAGE
_CZ_MODELS = ("dmr5g", "dmr4g", "dmp1g", "dmpok")
# (product, label, model or format, height system, sheet system, transport): a
# CUZK file where one is published (S-JTSK files in Bpv, also EVRF2007 through
# the pinned operation; ETRS89 files in EVRF2007), else the ImageServer warped
# onto the TM33 grid; LAZ only as published (S-JTSK = Bpv, ETRS89 = EVRF2007);
# ZABAGED contours: the SM5 ZIPs of both published formats (plan E1).
_CZ_ROUTES = {
    ("nmt", "2m", "Bpv", "tm33", _I),
    ("nmt", "2m", "EVRF2007", "tm33", _I),
    ("nmt", "5m", "Bpv", "sm5", _F),
    ("nmt", "5m", "EVRF2007", "sm5", _F),
    ("nmt", "5m", "EVRF2007", "tm33", _F),
    ("nmt", "5m", "Bpv", "tm33", _I),
    ("nmpt", "0.5m", "Bpv", "sm5", _F),
    ("nmpt", "0.5m", "EVRF2007", "sm5", _F),
    ("nmpt", "0.5m", "EVRF2007", "tm33", _F),
    ("nmpt", "0.5m", "Bpv", "tm33", _I),
    ("nmpt", "2m", "Bpv", "tm33", _I),
    ("nmpt", "2m", "EVRF2007", "tm33", _I),
    *(("laz", model, "Bpv", "sm5", _F) for model in _CZ_MODELS),
    *(("laz", model, "EVRF2007", "tm33", _F) for model in _CZ_MODELS),
    *(("contours", fmt, "Bpv", "sm5", _F) for fmt in ("SHP", "DGN")),
}
CZ_VARIANTS = variants(country="CZ")


def _cz_id(v: ProductVariant) -> str:
    return (
        f"{v.product}-{v.label or v.model or v.format}-{v.vertical_crs}-{v.systems[0]}"
    )


def test_cz_registry_matches_publication():
    found = {
        (
            v.product,
            v.label or v.model or v.format,
            v.vertical_crs,
            v.systems[0],
            v.channel,
        )
        for v in CZ_VARIANTS
    }
    assert found == _CZ_ROUTES
    assert len(CZ_VARIANTS) == len(_CZ_ROUTES)
    for v in CZ_VARIANTS:
        assert len(v.systems) == 1 and v.index_ref is None
        if v.product == "contours":
            assert v.model is None and v.label is None
            continue
        assert v.model in CZ_MODELS
        assert v.format == ("LAZ" if v.product == "laz" else "TIFF")


@pytest.mark.parametrize("variant", CZ_VARIANTS, ids=_cz_id)
def test_cz_row_has_its_channel(variant):
    """A row names one channel of its descriptor (files: in the CRS of the
    sheet system); heights are native for the S-JTSK file and the ImageServer
    in Bpv and for the ETRS89 file in EVRF2007, otherwise transformed."""
    descriptor = get_source(variant.source)
    assert variant in descriptor.variants
    assert descriptor.product == variant.product
    system = variant.systems[0]
    crs = CZ_SYSTEM_CRS[system] if variant.channel == _F else None
    channel = channel_for(variant.source, variant.channel, crs)
    code = resolve_vertical_crs(variant.vertical_crs, channel.vertical_crs_options)
    native = variant.vertical_crs == "Bpv" or (
        variant.channel == _F and system == "tm33"
    )
    assert (code in channel.vertical_crs_options) is native
    if variant.product == "laz":
        assert native  # point clouds are never transformed


def test_cz_model_values():
    found = variants(product="laz", country="CZ", vertical_crs="Bpv")
    assert [v.model for v in found] == list(_CZ_MODELS)
    assert cz_model_text() == (
        "dmr5g (teren, DMR 5G), dmr4g (teren, siatka 5 m), dmp1g (powierzchnia, "
        "DMP 1G), dmpok (powierzchnia, korelacja obrazowa)"
    )
    assert cz_resolution_text("nmt") == "2m (DMR 5G), 5m (DMR 4G)"
    assert cz_resolution_text("nmpt") == "0.5m (DMP OK), 2m (DMP 1G)"


@pytest.mark.parametrize(
    ("sheet", "system"), [("CTES96", "sm5"), (" 760_5518 ", "tm33")]
)
def test_cz_sheet_system(sheet, system):
    assert cz_sheet_system(sheet) == system


def test_cz_sheet_system_rejects_pl_code():
    with pytest.raises(ValidationError, match="nie nalezy do zadnego systemu CZ"):
        cz_sheet_system("N-34-130-D")


@pytest.mark.parametrize(
    ("product", "resolution", "vertical_crs", "system", "message"),
    [
        (
            "nmt",
            "2m",
            "Bpv",
            "sm5",
            "Arkusze SM5 NMT CZ sa tylko w 5m (DMR 4G) - pomin --resolution albo "
            "podaj 5m; 2m: kafel TM33 (np. 302_5550) albo --bbox z --cutout",
        ),
        (
            "nmpt",
            "2m",
            None,
            "sm5",
            "Arkusze SM5 NMPT CZ sa tylko w 0.5m (DMP OK) - pomin --resolution "
            "albo podaj 0.5m; 2m: kafel TM33 (np. 302_5550) albo --bbox z --cutout",
        ),
        (
            "nmt",
            None,
            "Bpv",
            "tm33",
            "--resolution wymagane dla NMT CZ: 2m (DMR 5G), 5m (DMR 4G)",
        ),
        (
            "nmpt",
            None,
            "Bpv",
            None,
            "--resolution wymagane dla NMPT CZ: 0.5m (DMP OK), 2m (DMP 1G)",
        ),
        (
            "nmpt",
            "1m",
            "Bpv",
            None,
            "CZ nie ma rozdzielczosci 1m dla NMPT - dostepne: 0.5m (DMP OK), "
            "2m (DMP 1G)",
        ),
        (
            "nmt",
            "5m",
            "KRON86",
            "tm33",
            f"KRON86 nie jest dostepny dla CZ - dostepne: {CZ_VERTICAL_TEXT}",
        ),
        ("orto", None, None, None, "--product orto nie ma wariantow rastrowych w CZ"),
    ],
)
def test_cz_variant_error_names_flags_and_registry_values(
    product, resolution, vertical_crs, system, message
):
    error = cz_variant_error(
        product=product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    assert error == message


@pytest.mark.parametrize(
    ("product", "resolution", "vertical_crs", "system", "source", "channel"),
    [
        # SM5 sheets: the only label with SM5 files may be omitted
        ("nmt", None, "Bpv", "sm5", "cz.cuzk.dmr4g", _F),
        ("nmpt", None, "EVRF2007", "sm5", "cz.cuzk.dmpok", _F),
        # TM33 5 m in EVRF2007: the ETRS89 file (no longer a warp)
        ("nmt", "5m", "EVRF2007", "tm33", "cz.cuzk.dmr4g", _F),
        ("nmt", "5m", "Bpv", "tm33", "cz.cuzk.dmr4g", _I),
        ("nmpt", "2m", "EVRF2007", "tm33", "cz.cuzk.dmp1g", _I),
    ],
)
def test_find_cz_variant(product, resolution, vertical_crs, system, source, channel):
    found = find_cz_variant(
        product=product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )
    assert (found.source, found.channel, found.systems) == (source, channel, (system,))
    assert found.vertical_crs == vertical_crs


def test_find_cz_variant_raises_the_error_text():
    with pytest.raises(ValidationError, match="Arkusze SM5 NMT CZ sa tylko w 5m"):
        find_cz_variant(
            product="nmt", resolution="2m", vertical_crs="Bpv", system="sm5"
        )


_MODELS_TEXT = (
    "dmr5g (teren, DMR 5G), dmr4g (teren, siatka 5 m), dmp1g (powierzchnia, "
    "DMP 1G), dmpok (powierzchnia, korelacja obrazowa)"
)


@pytest.mark.parametrize(
    ("model", "vertical_crs", "system", "message"),
    [
        (None, "Bpv", None, f"--model wymagane dla --product laz w CZ: {_MODELS_TEXT}"),
        (
            "dmr6g",
            "Bpv",
            None,
            f"--model 'dmr6g': nieznana wartosc - dostepne: {_MODELS_TEXT}",
        ),
        (
            "dmr5g",
            "EVRF2007",
            "sm5",
            "LAZ CZ - arkusze SM5 (S-JTSK) sa tylko w Bpv, podano --vertical-crs "
            "EVRF2007 (chmury punktow bez transformacji); EVRF2007: kafle TM33 "
            "(ETRS89), np. 760_5518, albo obszar (--bbox/--geometry)",
        ),
        (
            "dmpok",
            "Bpv",
            "tm33",
            "LAZ CZ - kafle TM33 (ETRS89) sa tylko w EVRF2007, podano --vertical-crs "
            "Bpv (chmury punktow bez transformacji); Bpv: arkusze SM5 (S-JTSK), "
            "np. CTES96, albo obszar (--bbox/--geometry)",
        ),
        (
            "dmr4g",
            "KRON86",
            None,
            f"KRON86 nie jest dostepny dla LAZ CZ - dostepne: {CZ_LAZ_VERTICAL_TEXT}",
        ),
    ],
)
def test_cz_laz_error(model, vertical_crs, system, message):
    assert (
        cz_laz_error(model=model, vertical_crs=vertical_crs, system=system) == message
    )
    with pytest.raises(ValidationError) as exc:
        find_cz_laz_variant(model=model, vertical_crs=vertical_crs, system=system)
    assert str(exc.value) == message


@pytest.mark.parametrize(
    ("vertical_crs", "system"), [("Bpv", "sm5"), ("EVRF2007", "tm33")]
)
def test_find_cz_laz_variant_by_height_system(vertical_crs, system):
    """The height system chooses the files of an area (no --sheet-system)."""
    found = find_cz_laz_variant(model="dmpok", vertical_crs=vertical_crs)
    assert (found.source, found.systems) == ("cz.cuzk.dmpok_laz", (system,))
    assert (
        find_cz_laz_variant(model="dmpok", vertical_crs=vertical_crs, system=system)
        == found
    )
