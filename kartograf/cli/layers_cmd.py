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

from kartograf.cli._json import emit_document, wants_json
from kartograf.landcover.manager import soil_choices
from kartograf.source_info import LayerList, list_layers

_WIDTH = 78
_CLASSES_NOTE = (
    "--layers zapisuje ZIP plikow wybranych klas. Paczka ma pliki tylko "
    "tych klas, ktorych obiekty sa w wojewodztwie (do 2023): brak czesci "
    "klas = Info, brak wszystkich = blad wojewodztwa."
)
_AREA_LAYERS_NOTE = (
    "Nazwy = warstwy GeoPackage obszaru (--bbox/--geometry); wynik "
    "obszaru ma zawsze wszystkie te warstwy (--layers dziala tylko "
    "z --product bdot10k albo bdoo). Plik krajowy (--whole-country) "
    "ma warstwy pelnej bazy pod nazwami CUZK."
)


def _depth_note() -> str:
    """The explanation of the depth codes: the description the library gives the
    depths of SoilGrids (every depth is a depth interval below the surface)."""
    return "; ".join(dict.fromkeys(soil_choices()["depth"].values()))


def _wrapped(text: str, indent: str) -> str:
    return textwrap.fill(
        text, width=_WIDTH, initial_indent=indent, subsequent_indent=indent
    )


def _classes(layers: LayerList) -> list[str]:
    """Class codes of a source of packages (BDOO) per release (``--year``)."""
    lines = [
        "  Klasy obiektow (--layers) wg rocznika; kod = OT_<KOD> w nazwach plikow",
        "  paczki wojewodztwa.",
    ]
    for year, codes in (layers.classes or {}).items():
        lines += [
            "",
            f"  --year {year} ({len(codes)}):",
            _wrapped(", ".join(codes), "    "),
        ]
    return [*lines, "", _wrapped(_CLASSES_NOTE, "  ")]


def _soil(layers: LayerList) -> list[str]:
    """Properties, depths and statistics of SoilGrids."""
    return [
        "  Wlasciwosci gleb:",
        *(
            f"    {item.code:11} - {item.description}"
            for item in layers.properties or ()
        ),
        "",
        f"  Glebokosci ({_depth_note()}):",
        *(f"    {depth}" for depth in layers.depths or ()),
        "",
        "  Statystyki:",
        *(
            f"    {item.code:11} - {item.description}"
            for item in layers.statistics or ()
        ),
        "",
        "  Wybor pobrania: --property, --depth, --stat.",
    ]


def _corine(layers: LayerList) -> list[str]:
    """The release years of CORINE: CLMS data or the WMS preview."""
    return [
        "  CORINE: jedna klasyfikacja pokrycia terenu.",
        "  Dostepne lata (--year, rok referencyjny):",
        *(f"    {item.year}  ({item.description})" for item in layers.years or ()),
    ]


def _named(layers: LayerList) -> list[str]:
    """Layers with a description (BDOT10k), or only the names of the layers of
    the service (ZABAGED, Data50, Data250) with the note on the area result."""
    if any(layer.description is not None for layer in layers.layers):
        return [f"    {layer.code}  - {layer.description}" for layer in layers.layers]
    return [
        *(f"    {layer.code}" for layer in layers.layers),
        "",
        _wrapped(_AREA_LAYERS_NOTE, "  "),
    ]


def format_layers(layers: LayerList) -> str:
    """The text of ``list-layers``: the source and what the product offers."""
    if layers.properties is not None:
        body = _soil(layers)
    elif layers.classes:
        body = _classes(layers)
    elif layers.years is not None:
        body = _corine(layers)
    else:
        body = _named(layers)
    return "\n".join([f"Warstwy zrodla {layers.source}:", "", *body])


def cmd_list_layers(args: argparse.Namespace, group: str) -> int:
    """``<group> list-layers`` (``landcover`` with its ``--product``, ``soil``):
    the text, or with ``--json`` the document of ``list_layers``."""
    layers = list_layers(group=group, product=getattr(args, "product", None))
    if wants_json(args):
        return emit_document(layers)
    print(format_layers(layers))
    return 0
