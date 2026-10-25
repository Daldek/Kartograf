"""``list_sources`` and ``list_layers``: the registered sources and the layers of
the command groups as documents (``kartograf-sources/1``, ``kartograf-layers/1``,
spec 5.4.6-5.4.7). Everything comes from the registry and the provider
catalogues: no network, nothing written.
"""

import inspect
import json
from typing import Any

import pytest

from kartograf import (
    download_collection,
    download_data,
    download_landcover,
    download_soil,
)
from kartograf.exceptions import ValidationError
from kartograf.serialization import SCHEMAS
from kartograf.source_info import LayerList, SourceList, list_layers, list_sources
from kartograf.sources.registry import all_sources, get_source

# The 11 groups with ``list-sources`` (spec 5.4.6) - a literal on purpose: a new
# group is a deliberate edit of this table.
GROUPS = (
    "elevation",
    "imagery",
    "landcover",
    "soil",
    "boundaries",
    "cadastre",
    "models3d",
    "hydro",
    "names",
    "maps",
    "geodesy",
)

GROUP_FUNCTIONS = {
    "elevation": download_data,
    "imagery": download_data,
    "landcover": download_landcover,
    "soil": download_soil,
    **dict.fromkeys(
        ("boundaries", "cadastre", "models3d", "hydro", "names", "maps", "geodesy"),
        download_collection,
    ),
}


def _sources(group: str) -> dict[str, Any]:
    """The ``sources`` of the document of ``group`` by key (the JSON form)."""
    document: Any = list_sources(group=group).to_dict()
    return {source["key"]: source for source in document["sources"]}


def _select(group: str, key: str) -> dict:
    return _sources(group)[key]["select"]


def test_every_registered_source_of_a_group_is_listed_once():
    listed = [
        source.key for group in GROUPS for source in list_sources(group=group).sources
    ]

    assert len(listed) == len(set(listed))
    assert sorted(listed) == sorted(source.key for source in all_sources())


def test_sources_of_a_group_follow_the_products_of_the_group():
    for group in GROUPS:
        document = list_sources(group=group)

        positions = [document.products.index(s.product) for s in document.sources]

        assert positions == sorted(positions), group


def test_product_filter_keeps_the_sources_of_that_product_only():
    full = list_sources(group="elevation")

    laz = list_sources(group="elevation", product="laz")

    assert laz.products == full.products
    assert [s.key for s in laz.sources] == [
        s.key for s in full.sources if s.product == "laz"
    ]
    assert len(laz.sources) == 5


@pytest.mark.parametrize(
    ("group", "key", "expected"),
    [
        pytest.param(
            "elevation",
            "pl.gugik.nmt_1m",
            {
                "product": "nmt",
                "country": "pl",
                "resolution": "1m",
                "vertical_crs": ["EVRF2007", "KRON86"],
            },
            id="nmt-1m-two-height-systems",
        ),
        pytest.param(
            "elevation",
            "pl.gugik.nmt_5m",
            {
                "product": "nmt",
                "country": "pl",
                "resolution": "5m",
                "vertical_crs": "EVRF2007",
            },
            id="nmt-5m-one-height-system-is-a-plain-value",
        ),
        pytest.param(
            "elevation",
            "pl.gugik.nmt_xyz_1m",
            {
                "product": "nmt",
                "country": "pl",
                "format": "XYZ",
                "resolution": "1m",
                "vertical_crs": ["EVRF2007", "KRON86"],
            },
            id="source-archive-names-the-format-first",
        ),
        pytest.param(
            "elevation",
            "pl.gugik.nmt_100m",
            {"product": "nmt", "country": "pl", "resolution": "100m"},
            id="nmt-100m-declares-no-height-system",
        ),
        pytest.param(
            "elevation",
            "pl.gugik.laz",
            {
                "product": "laz",
                "country": "pl",
                "vertical_crs": ["EVRF2007", "KRON86"],
            },
            id="pl-laz-has-no-resolution",
        ),
        pytest.param(
            "elevation",
            "cz.cuzk.dmr4g",
            {
                "product": "nmt",
                "country": "cz",
                "resolution": "5m",
                "vertical_crs": ["Bpv", "EVRF2007"],
            },
            id="cz-grid",
        ),
        pytest.param(
            "elevation",
            "cz.cuzk.dmr5g_laz",
            {
                "product": "laz",
                "country": "cz",
                "model": "dmr5g",
                "vertical_crs": ["Bpv", "EVRF2007"],
            },
            id="cz-laz-is-chosen-by-model",
        ),
        pytest.param(
            "elevation",
            "cz.cuzk.zabaged_contours_shp",
            {"product": "contours", "country": "cz", "format": "SHP"},
            id="contours-are-chosen-by-format",
        ),
        pytest.param(
            "imagery",
            "pl.gugik.orto",
            {"product": "orto", "country": "pl"},
            id="orthophoto",
        ),
        pytest.param(
            "imagery",
            "cz.cuzk.orto",
            {"product": "orto", "country": "cz"},
            id="cz-orthophoto",
        ),
        pytest.param(
            "boundaries",
            "pl.gugik.prg_addresses",
            {"product": "addresses", "country": "pl"},
            id="collection-product-and-country",
        ),
        pytest.param(
            "hydro",
            "cz.cuzk.hynet",
            {"product": "network", "country": "cz"},
            id="collection-without-pl-source",
        ),
        pytest.param(
            "landcover",
            "pl.gugik.bdot10k",
            {"product": "bdot10k"},
            id="bdot10k-needs-only-the-product",
        ),
        pytest.param(
            "landcover",
            "cz.cuzk.zabaged",
            {"product": "zabaged"},
            id="cz-landcover",
        ),
        pytest.param(
            "landcover",
            "eu.clms.corine",
            {"product": "corine", "year": [2018, 2012, 2006, 2000, 1990]},
            id="corine-year-is-a-list-of-releases",
        ),
        pytest.param(
            "soil",
            "global.isric.soilgrids",
            {"property": None, "depth": None, "stat": None},
            id="soil-is-a-free-choice-from-list-layers",
        ),
    ],
)
def test_select_names_the_options_that_choose_the_source(group, key, expected):
    select = _select(group, key)

    # the key order is the order of the flags in ``<group> download``
    assert list(select.items()) == list(expected.items())


def test_bdoo_select_lists_every_release_year_as_a_number():
    years = _select("landcover", "pl.gugik.bdoo")["year"]

    assert list(_select("landcover", "pl.gugik.bdoo")) == ["product", "year"]
    assert all(isinstance(year, int) for year in years)
    assert years == sorted(years)
    assert 2015 in years and 2023 in years


@pytest.mark.parametrize("group", GROUPS)
def test_select_options_are_arguments_of_the_group_function(group):
    arguments = set(inspect.signature(GROUP_FUNCTIONS[group]).parameters)

    for source in list_sources(group=group).sources:
        assert set(source.select) <= arguments, source.key


def test_source_fields():
    nmt = _sources("elevation")["pl.gugik.nmt_1m"]
    corine = _sources("landcover")["eu.clms.corine"]

    assert nmt["key"] == "pl.gugik.nmt_1m"
    assert nmt["name"] == "Digital Terrain Model 1 m (ASC grid)"
    assert nmt["country"] == "PL"
    assert nmt["provider"] == "GUGiK"
    assert nmt["product"] == "nmt"
    assert nmt["directory"] == "nmt/pl_<crs>_1m_<vertical-crs>"
    assert nmt["license"]["id"] == "PL-PGiK-40a"
    assert nmt["license"]["attribution"]
    assert nmt["auth"] == "none"
    assert nmt["update_signals"] == ["index", "none"]
    assert corine["country"] == "EU"
    assert corine["auth"] == "clms_oauth"
    assert corine["license"]["id"] == "COPERNICUS-CLMS"


def test_update_signals_are_the_signals_of_the_channels():
    for group in GROUPS:
        for source in list_sources(group=group).sources:
            channels = get_source(source.key).channels

            assert set(source.update_signals) == {c.update_signal for c in channels}
            assert len(source.update_signals) == len(set(source.update_signals))


@pytest.mark.parametrize(
    ("group", "key", "signals"),
    [
        ("elevation", "pl.gugik.nmt_5m", ["index"]),
        ("elevation", "pl.gugik.nmt_100m", ["metadata"]),
        ("elevation", "cz.cuzk.dmr5g", ["none"]),
        # the order is the one of the spec: index, metadata, http, none
        ("elevation", "cz.cuzk.dmr4g", ["http", "none"]),
        ("landcover", "eu.clms.corine", ["metadata", "none"]),
    ],
)
def test_update_signals_come_in_the_order_of_the_spec(group, key, signals):
    assert _sources(group)[key]["update_signals"] == signals


def test_directory_names_the_placeholders_of_the_storage_segment():
    sources = _sources("elevation")

    assert sources["pl.gugik.nmt_xyz_1m"]["directory"] == (
        "nmt/pl_<crs>_xyz_1m_<vertical-crs>"
    )
    assert sources["pl.gugik.nmt_100m"]["directory"] == "nmt/pl_1992_100m"
    assert all("{" not in s["directory"] for s in sources.values())


def test_unknown_group_and_product_are_input_errors():
    with pytest.raises(ValidationError) as unknown_group:
        list_sources(group="rivers")
    with pytest.raises(ValidationError) as unknown_product:
        list_sources(group="elevation", product="orto")

    assert unknown_group.value.option == "group"
    assert unknown_group.value.allowed == GROUPS
    assert unknown_product.value.option == "product"
    assert unknown_product.value.allowed == ("nmt", "nmpt", "laz", "contours")
    assert "rivers" in str(unknown_group.value)
    assert "orto" in str(unknown_product.value)


def test_list_sources_is_offline_and_writes_nothing(tmp_path, monkeypatch):
    # the network is closed by the autouse ``_block_network`` of conftest: any
    # connection attempt fails this test
    monkeypatch.chdir(tmp_path)

    for group in GROUPS:
        list_sources(group=group)
    for product in ("bdot10k", "bdoo", "corine", "zabaged", "data50", "data250"):
        list_layers(group="landcover", product=product)
    list_layers(group="soil")

    assert list(tmp_path.iterdir()) == []


def test_list_layers_bdot10k():
    document = list_layers(group="landcover", product="bdot10k")

    layers = {layer.code: layer.description for layer in document.layers}
    assert (document.group, document.product) == ("landcover", "bdot10k")
    assert document.source == "BDOT10k"
    assert {"PTWP", "SWRS", "BUBD"} <= set(layers)
    assert list(layers) == sorted(layers)
    assert layers["PTWP"] == "Surface waters"
    assert document.classes is None
    assert document.years is None
    assert document.properties is None
    assert document.depths is None
    assert document.statistics is None


def test_list_layers_of_a_cz_source_are_service_names_without_description():
    document = list_layers(group="landcover", product="zabaged")

    assert document.source.startswith("ZABAGED")
    assert len(document.layers) > 0
    assert all(layer.code and layer.description is None for layer in document.layers)
    assert document.classes is None


def test_list_layers_corine_years_and_data():
    document = list_layers(group="landcover", product="corine")

    years = {year.year: year for year in document.years or ()}
    assert document.source == "CORINE Land Cover"
    assert document.layers == ()
    assert list(years) == [2018, 2012, 2006, 2000, 1990]
    assert [years[year].data for year in years] == ["clms"] * 4 + ["wms"]
    assert years[2018].description == (
        "CLMS data with CLMS_CREDENTIALS, the WMS preview without them"
    )
    assert years[1990].description == "WMS preview only"
    assert document.classes is None


def test_list_layers_bdoo_classes():
    document = list_layers(group="landcover", product="bdoo")

    classes = document.classes
    assert classes is not None
    assert document.layers == ()
    assert document.years is None
    assert all(year.isdigit() for year in classes)
    assert all(codes and len(set(codes)) == len(codes) for codes in classes.values())
    # the releases of the classes are the releases ``list_sources`` offers
    select_years = _select("landcover", "pl.gugik.bdoo")["year"]
    assert list(classes) == [str(year) for year in select_years]


def test_list_layers_soil_properties_depths_statistics():
    document = list_layers(group="soil")

    properties = {p.code: p.description for p in document.properties or ()}
    statistics = {s.code: s.description for s in document.statistics or ()}
    assert (document.group, document.product) == ("soil", None)
    assert document.source == "SoilGrids"
    assert document.layers == ()
    assert list(properties)[:2] == ["bdod", "cec"]
    assert "in the file g/kg" in properties["clay"]
    assert document.depths == (
        "0-5cm",
        "5-15cm",
        "15-30cm",
        "30-60cm",
        "60-100cm",
        "100-200cm",
        "0-30cm",
    )
    clay, ocs = (p for p in document.properties or () if p.code in ("clay", "ocs"))
    assert (clay.unit, clay.conventional_unit, clay.divisor) == ("g/kg", "%", 10)
    assert ocs.depths == ("0-30cm",) and len(clay.depths) == 6
    assert list(statistics) == ["mean", "Q0.05", "Q0.5", "Q0.95", "uncertainty"]
    assert statistics["Q0.5"] == "median"
    assert document.classes is None and document.years is None


def test_list_layers_landcover_requires_product():
    with pytest.raises(ValidationError) as missing:
        list_layers(group="landcover")
    with pytest.raises(ValidationError) as unknown:
        list_layers(group="landcover", product="soil")

    assert missing.value.option == "product"
    assert missing.value.allowed == (
        "bdot10k",
        "bdoo",
        "corine",
        "zabaged",
        "data50",
        "data250",
    )
    assert unknown.value.option == "product"
    assert unknown.value.allowed == missing.value.allowed


def test_list_layers_input_errors_name_the_argument():
    with pytest.raises(ValidationError) as no_layers:
        list_layers(group="elevation")
    with pytest.raises(ValidationError) as soil_product:
        list_layers(group="soil", product="soil")

    assert no_layers.value.option == "group"
    assert no_layers.value.allowed == ("landcover", "soil")
    assert soil_product.value.option == "product"


def test_documents_are_registered_with_spec_keys() -> None:
    sources: Any = list_sources(group="elevation").to_dict()
    bdot10k: Any = list_layers(group="landcover", product="bdot10k").to_dict()
    corine: Any = list_layers(group="landcover", product="corine").to_dict()
    soil: Any = list_layers(group="soil").to_dict()

    assert SCHEMAS["kartograf-sources/1"] == (SourceList,)
    assert SCHEMAS["kartograf-layers/1"] == (LayerList,)
    assert list(sources) == ["schema", "group", "products", "sources"]
    assert sources["schema"] == "kartograf-sources/1"
    assert list(sources["sources"][0]) == [
        "key",
        "name",
        "country",
        "provider",
        "product",
        "directory",
        "select",
        "license",
        "auth",
        "update_signals",
    ]
    assert list(sources["sources"][0]["license"]) == [
        "id",
        "attribution",
        "url",
    ]
    layer_keys = [
        "schema",
        "group",
        "product",
        "source",
        "layers",
        "classes",
        "years",
        "properties",
        "depths",
        "statistics",
    ]
    for layers in (bdot10k, corine, soil):
        assert list(layers) == layer_keys
        assert layers["schema"] == "kartograf-layers/1"
    assert list(bdot10k["layers"][0]) == ["code", "description"]
    assert list(corine["years"][0]) == ["year", "data", "description"]
    assert list(soil["properties"][0]) == [
        "code",
        "description",
        "unit",
        "conventional_unit",
        "divisor",
        "depths",
    ]
    assert list(soil["statistics"][0]) == ["code", "description"]


def test_documents_are_json_with_ascii_texts():
    documents = [list_sources(group=group) for group in GROUPS]
    documents += [
        list_layers(group="landcover", product=product)
        for product in ("bdot10k", "bdoo", "corine", "zabaged", "data50", "data250")
    ]
    documents.append(list_layers(group="soil"))

    for document in documents:
        text = document.to_json()

        assert json.loads(text) == document.to_dict()
        assert text.isascii()
