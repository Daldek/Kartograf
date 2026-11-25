"""
The answers of ``kartograf server`` the browser tests give the page for a plan.

A plan queries the sources' sheet indexes, so the tests answer ``POST
/api/v1/<group>/download?check=true`` with answers the server's routes gave on
2026-11-25 against GUGiK (``tests/fixtures/gui/real_2026_11_25/``), each for the area
``--bbox 21,52.2,21.02,52.21 --bbox-crs EPSG:4326 --country pl``: ``plan_nmt.json``
(NMT 1 m, EVRF2007, the 1992 sheets: two sheets), ``plan_laz.json`` (LAZ, EVRF2007:
twelve tiles of nine-member codes) and ``plan_nmpt.json`` (NMPT 1 m: the problem
document of ``no_data``, ``404``, with the hint of the resolution the index has).
"""

import json
from pathlib import Path
from typing import Any, Final

FIXTURES: Final = (
    Path(__file__).resolve().parents[1] / "fixtures" / "gui" / "real_2026_11_25"
)
RELEASE: Final = "0.9.0"
"""The version of the served Kartograf: a release, whose tag the script pins."""


def recorded(name: str) -> dict[str, Any]:
    """Return a recorded answer of the server (``FIXTURES / name``)."""
    doc: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return doc
