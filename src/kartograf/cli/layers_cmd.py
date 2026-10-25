"""
``landcover list-layers`` and ``soil list-layers``: what a product offers.

The text is rendered from the library document ``list_layers``
(``kartograf-layers/1``): the layers of BDOT10k, ZABAGED, Data50 or Data250, the
classes of BDOO per release, the years of CORINE, the properties, depths and
statistics of SoilGrids. With ``--json`` the CLI prints that document. No
network, nothing written.
"""

import argparse
import textwrap

from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.landcover.manager import soil_choices
from kartograf.messages import message
from kartograf.source_info import LayerInfo, LayerList, PropertyInfo, list_layers

_WIDTH = 78
_CLASSES_NOTE = message("cli.classes_note")
_AREA_LAYERS_NOTE = message("cli.area_layers_note")
_SOIL_NOTE = message("cli.soil_note")


def _depth_note() -> str:
    """Return the explanation of the depth codes.

    The description the library gives the depths of SoilGrids (every depth is a depth
    interval below the surface).
    """
    return "; ".join(
        dict.fromkeys(localized(text) for text in soil_choices()["depth"].values())
    )


def _wrapped(text: str, indent: str) -> str:
    return textwrap.fill(
        text, width=_WIDTH, initial_indent=indent, subsequent_indent=indent
    )


def _description(item: LayerInfo) -> str:
    """Return the description of a layer, property or statistic as a person reads it."""
    return localized(item.description or "")


def _classes(layers: LayerList) -> list[str]:
    """Class codes of a source of packages (BDOO) per release (``--year``)."""
    lines: list[str] = [
        message("cli.classes_header_line1", lang=language()),
        message("cli.classes_header_line2", lang=language()),
    ]
    for year, codes in (layers.classes or {}).items():
        lines += [
            "",
            f"  --year {year} ({len(codes)}):",
            _wrapped(", ".join(codes), "    "),
        ]
    return [*lines, "", _wrapped(localized(_CLASSES_NOTE), "  ")]


def _depths(layers: LayerList) -> list[str]:
    """Return the depth intervals.

    One published for a minority of the properties (``ocs``: 0-30cm) is marked with the
    properties that have it.
    """
    properties = [p for p in layers.properties or () if isinstance(p, PropertyInfo)]
    lines = []
    for depth in layers.depths or ():
        owners = [p.code for p in properties if depth in p.depths]
        only = (
            message("cli.depths_only_owners", lang=language(), owners=", ".join(owners))
            if len(owners) * 2 < len(properties)
            else ""
        )
        lines.append(f"    {depth}{only}")
    return lines


def _soil(layers: LayerList) -> list[str]:
    """Properties, depths and statistics of SoilGrids."""
    return [
        message("cli.soil_properties_header", lang=language()),
        *(
            f"    {item.code:11} - {_description(item)}"
            for item in layers.properties or ()
        ),
        "",
        message("cli.soil_depths_header", lang=language(), depth_note=_depth_note()),
        *_depths(layers),
        "",
        message("cli.soil_statistics_header", lang=language()),
        *(
            f"    {item.code:11} - {_description(item)}"
            for item in layers.statistics or ()
        ),
        "",
        message("cli.soil_download_selection", lang=language()),
        "",
        _wrapped(localized(_SOIL_NOTE), "  "),
    ]


def _corine(layers: LayerList) -> list[str]:
    """Return the release years of CORINE: CLMS data or the WMS preview."""
    return [
        message("cli.corine_intro", lang=language()),
        message("cli.corine_available_years", lang=language()),
        *(
            f"    {item.year}  ({localized(item.description)})"
            for item in layers.years or ()
        ),
    ]


def _named(layers: LayerList) -> list[str]:
    """Return layers with a description (BDOT10k, with the note on the classes).

    Or only the names of the layers of the service (ZABAGED, Data50, Data250) with the
    note on the area result.
    """
    if any(layer.description is not None for layer in layers.layers):
        return [
            *(f"    {layer.code}  - {_description(layer)}" for layer in layers.layers),
            "",
            _wrapped(
                message(
                    "cli.bdot10k_classes_note",
                    lang=language(),
                    count=len(layers.layers),
                ),
                "  ",
            ),
        ]
    return [
        *(f"    {layer.code}" for layer in layers.layers),
        "",
        _wrapped(localized(_AREA_LAYERS_NOTE), "  "),
    ]


def format_layers(layers: LayerList) -> str:
    """Return the text of ``list-layers``: the source and what the product offers."""
    if layers.properties is not None:
        body = _soil(layers)
    elif layers.classes:
        body = _classes(layers)
    elif layers.years is not None:
        body = _corine(layers)
    else:
        body = _named(layers)
    return "\n".join(
        [
            message("cli.source_layers_header", lang=language(), source=layers.source),
            "",
            *body,
        ]
    )


def cmd_list_layers(args: argparse.Namespace, group: str) -> int:
    """Run ``<group> list-layers`` (``landcover`` with its ``--product``, ``soil``).

    The result is the text, or with ``--json`` the document of ``list_layers``.
    """
    layers = list_layers(group=group, product=getattr(args, "product", None))
    if wants_json(args):
        return emit_result(command_id(args), layers)
    print(format_layers(layers))
    return 0
