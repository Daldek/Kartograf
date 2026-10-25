"""Messages of the source and layer documents (``kartograf.source_info``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``source_info``.
    "corine_clms": Text(
        "CLMS data with CLMS_CREDENTIALS, the WMS preview without them",
        "dane CLMS z CLMS_CREDENTIALS, bez nich podglad WMS",
    ),
    "corine_wms": Text("WMS preview only", "tylko podglad WMS"),
    "unknown_product_for_group": Text(
        "product {product!r}: unknown value for the group {group} - available: "
        "{products}",
        "product {product!r}: nieznana wartosc dla grupy {group} - dostepne: "
        "{products}",
    ),
    "layers_only_groups": Text(
        "group {group!r}: only the groups {layer_groups} list layers",
        "group {group!r}: warstwy wypisuja tylko grupy {layer_groups}",
    ),
    "soil_has_no_products": Text(
        "product: the soil group has no products - omit product",
        "product: grupa soil nie ma produktow - pomin product",
    ),
    "product_required": Text(
        "--product is required: {landcover_product_choices}",
        "--product wymagane: {landcover_product_choices}",
    ),
    "unknown_product": Text(
        "--product {product!r}: unknown value - available: {landcover_product_choices}",
        "--product {product!r}: nieznana wartosc - dostepne: "
        "{landcover_product_choices}",
    ),
    "unknown_group": Text(
        "group {group!r}: unknown value - available: {source_groups}",
        "group {group!r}: nieznana wartosc - dostepne: {source_groups}",
    ),
}
