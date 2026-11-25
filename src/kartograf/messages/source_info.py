"""Messages of the source and layer documents (``kartograf.source_info``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``source_info``.
    "corine_clms": Text(
        "CLMS data with CLMS_CREDENTIALS, the WMS preview without them",
        "dane CLMS z CLMS_CREDENTIALS, bez nich podgląd WMS",
    ),
    "corine_wms": Text("WMS preview only", "tylko podgląd WMS"),
    "unknown_product_for_group": Text(
        "product {product!r}: unknown value for the group {group} - available: "
        "{products}",
        "product {product!r}: nieznana wartość dla grupy {group} - dostępne: "
        "{products}",
    ),
    "layers_only_groups": Text(
        "group {group!r}: only the groups {layer_groups} list layers",
        "group {group!r}: warstwy wypisują tylko grupy {layer_groups}",
    ),
    "soil_has_no_products": Text(
        "product: the soil group has no products - omit product",
        "product: grupa soil nie ma produktów - pomiń product",
    ),
    "product_required": Text(
        "--product is required: {landcover_product_choices}",
        "--product wymagane: {landcover_product_choices}",
    ),
    "unknown_product": Text(
        "--product {product!r}: unknown value - available: {landcover_product_choices}",
        "--product {product!r}: nieznana wartość - dostępne: "
        "{landcover_product_choices}",
    ),
    "unknown_group": Text(
        "group {group!r}: unknown value - available: {source_groups}",
        "group {group!r}: nieznana wartość - dostępne: {source_groups}",
    ),
}
