"""
Sheet codes as documents: ``describe_sheet`` and ``find_sheets`` (spec 5.4.4-5.4.5).

``describe_sheet`` is the library form of ``kartograf parse``: what a sheet code
is - its system (PL-1992, PL-2000, CZ SM5, TM33 tile or ZTM map sheet), scale,
parts, native CRS and bounds, the commands that take it in ``--sheet`` and, on
request, its hierarchy, children and descendants. ``find_sheets`` lists the
sheets of an area (``find_sheets_for_bbox`` and ``find_sheets_for_geometry`` as a
document). Neither of them uses the network.

The commands a code can be given to are read from the declarations of the
catalog (``ParamInfo.accepts`` of the ``sheet`` parameter), so a command that
starts to take a sheet system lists it here without a second edit.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

from kartograf.catalog import get_catalog
from kartograf.core.bbox import BBox, bbox_coords
from kartograf.core.geometry import find_sheets_for_geometry
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000
from kartograf.core.parser_registry import detect_system, ztm_sheet_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.serialization import Document

_CZ_CODES = (
    "Godla CZ: SM5 (np. CTES96), kafel TM33 (np. 302_5550), ZTM (np. 0510-D-11, "
    "NM-34-07-1-D-15)."
)
_SM5_CRS = "EPSG:5514"
# ZTM map sheets by their ``sheet_system`` value (``--sheet-system``).
_ZTM_CRS = {"sjtsk": "EPSG:5514", "etrs89": "EPSG:3045"}
# The scales of the sheets of each PL sheet system, coarsest first.
_SCALES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "1992": tuple(SheetParser.SCALE_HIERARCHY),
        "2000": tuple(SCALE_HIERARCHY_2000),
    }
)


@dataclass(frozen=True)
class SheetLevel:
    """A sheet with its scale: a step of the hierarchy or a child."""

    sheet: str
    scale: str


@dataclass(frozen=True)
class SheetDescendants:
    """The sheets below a sheet down to the scale asked for (never truncated)."""

    scale: str
    count: int
    sheets: tuple[str, ...]


@dataclass(frozen=True)
class SheetInfo(Document):
    """What a sheet code is (``kartograf-sheet/1``; ``kartograf parse``).

    Attributes
    ----------
    sheet : str
        The code in its canonical form (``SheetParser.sheet``; a CZ code as
        given, without padding).
    system : str
        ``pl1992``, ``pl2000``, ``cz_sm5``, ``cz_tm33`` (the ids of
        ``core.parser_registry.SYSTEMS``) or ``cz_ztm`` (a ZTM map sheet).
    country : str
        ``PL`` or ``CZ``.
    sheet_system : str, optional
        The value of the option ``sheet_system``: ``1992`` or ``2000`` (PL),
        ``sjtsk`` or ``etrs89`` (ZTM); ``None`` for SM5 and TM33.
    scale : str, optional
        ``1:10000``...; ``None`` for a CZ code.
    components : mapping, optional
        The parts of a PL code in order (``pas``, ``slup``, ``arkusz_200k``...;
        PL-2000: ``strefa``, ``pas``, ``slup``, ``ark_2k``); ``None`` for CZ.
    zone : int, optional
        PL-2000 zone (5-8).
    crs : str
        Native CRS of the sheet (``EPSG:2180``, ``EPSG:2176``-``EPSG:2179``,
        ``EPSG:5514``, ``EPSG:3045``).
    bounds : BBox, optional
        The sheet's bounding box in ``crs``; ``None`` for SM5 and ZTM sheets
        (their frame is in the CUZK index, which needs the network).
    commands : tuple of str
        Ids of the catalog commands that take this code in ``--sheet``.
    hierarchy : tuple of SheetLevel, optional
        From the sheet (first) up to 1:1000000 (PL-1992) or 1:10000 (PL-2000);
        only when asked for (PL codes only).
    children : tuple of SheetLevel, optional
        The direct children; only when asked for (PL codes only).
    descendants : SheetDescendants, optional
        Every sheet down to the asked scale; only when asked for (PL only).
    """

    SCHEMA: ClassVar[str] = "kartograf-sheet/1"

    sheet: str
    system: str
    country: str
    sheet_system: str | None
    scale: str | None
    components: Mapping[str, str] | None
    zone: int | None
    crs: str
    bounds: BBox | None
    commands: tuple[str, ...]
    hierarchy: tuple[SheetLevel, ...] | None = None
    children: tuple[SheetLevel, ...] | None = None
    descendants: SheetDescendants | None = None


@dataclass(frozen=True)
class SheetRequest:
    """The request of a sheet search as the document echoes it.

    The area is a ``bbox`` with its ``bbox_crs`` or a ``geometry`` file with its
    ``layer`` (the other fields are ``None``).
    """

    scale: str
    sheet_system: str
    bbox: tuple[float, ...] | None
    bbox_crs: str | None
    geometry: Path | None
    layer: str | None


@dataclass(frozen=True)
class SheetList(Document):
    """The sheets of an area (``kartograf-sheets/1``; ``find_sheets``).

    Attributes
    ----------
    request : SheetRequest
        What was asked.
    sheets : tuple of str
        The sheet codes in the order of ``find_sheets_for_bbox``/
        ``find_sheets_for_geometry`` (sorted).
    """

    SCHEMA: ClassVar[str] = "kartograf-sheets/1"
    JSON_KEYS: ClassVar[tuple[str, ...] | None] = ("request", "sheets", "count")

    request: SheetRequest
    sheets: tuple[str, ...]

    @property
    def count(self) -> int:
        """The number of sheets."""
        return len(self.sheets)


def _accepting(system: str) -> tuple[str, ...]:
    """Return the ids of the commands whose ``sheet`` accepts ``system``.

    The order is that of the catalog.
    """
    return tuple(
        command.id
        for command in get_catalog(params=True).commands
        for param in command.params or ()
        if param.name == "sheet" and system in (param.accepts or ())
    )


def _require_flag(value: object, flag: str, option: str) -> None:
    if not isinstance(value, bool):
        raise ValidationError(
            f"{flag} musi byc przelacznikiem (True albo False), otrzymano {value!r}",
            option=option,
        )


def _cz_sheet(code: str) -> SheetInfo | None:
    """Return the description of a CZ code (SM5 sheet, TM33 tile, ZTM map sheet).

    ``None`` for any other code (a PL code or an invalid one).

    Raises
    ------
    ParseError
        A TM33 tile code off the 2 km grid.
    """
    system = detect_system(code).id
    ztm = ztm_sheet_system(code)
    bounds: BBox | None = None
    sheet_system: str | None = None
    if system == "cz_tm33":
        try:
            bounds = ParserTM33(code).get_bbox()
        except ParseError as error:
            raise ParseError(str(error), option="sheet", hint=error.hint) from error
        crs = bounds.crs
    elif system == "cz_sm5":
        crs = _SM5_CRS
    elif ztm is not None:
        system, sheet_system, crs = "cz_ztm", ztm, _ZTM_CRS[ztm]
    else:
        return None
    return SheetInfo(
        sheet=code,
        system=system,
        country="CZ",
        sheet_system=sheet_system,
        scale=None,
        components=None,
        zone=None,
        crs=crs,
        bounds=bounds,
        commands=_accepting(system),
    )


def _levels(parsers: list[SheetParser]) -> tuple[SheetLevel, ...]:
    return tuple(SheetLevel(parser.sheet, parser.scale) for parser in parsers)


def describe_sheet(
    sheet: str,
    *,
    hierarchy: bool = False,
    children: bool = False,
    descendants: str | None = None,
) -> SheetInfo:
    """Describe what a sheet code is: ``kartograf parse`` as a document.

    Parameters
    ----------
    sheet : str
        A PL-1992 (``N-34-130-D-d-2-4``), PL-2000 (``6.179.12.20``), SM5
        (``CTES96``), TM33 (``302_5550``) or ZTM (``0510-D-11``,
        ``NM-34-07-1-D-15``) sheet code; whitespace around it is ignored.
    hierarchy : bool
        Add the hierarchy from the sheet up to the coarsest sheet (PL only).
    children : bool
        Add the direct children (PL only).
    descendants : str, optional
        Add every sheet down to this scale (``1:10000``; PL only).

    Returns
    -------
    SheetInfo
        The facts about the code; ``hierarchy``, ``children`` and
        ``descendants`` are ``None`` unless asked for.

    Raises
    ------
    ParseError
        A code outside the nomenclatures (``option="sheet"``).
    ValidationError
        ``hierarchy``, ``children`` or ``descendants`` for a CZ code, or an
        unknown or not finer ``descendants`` scale (``option`` names the
        argument).
    """
    _require_flag(hierarchy, "--hierarchy", "hierarchy")
    _require_flag(children, "--children", "children")
    if descendants is not None and not isinstance(descendants, str):
        raise ValidationError(
            f"--descendants musi byc napisem (str), otrzymano {descendants!r}",
            option="descendants",
        )
    if not isinstance(sheet, str):
        raise ParseError(
            f"Godlo musi byc stringiem, otrzymano: {type(sheet)}", option="sheet"
        )
    code = sheet.strip()
    asked = [
        name
        for name, wanted in (
            ("hierarchy", hierarchy),
            ("children", children),
            ("descendants", descendants is not None),
        )
        if wanted
    ]
    cz = _cz_sheet(code)
    if cz is not None:
        if asked:
            raise ValidationError(
                "--hierarchy, --children i --descendants dotycza tylko godel PL "
                "(PL-1992, PL-2000)",
                option=asked[0],
                options=asked if len(asked) > 1 else None,
            )
        return cz
    try:
        parser = SheetParser(code)
    except ParseError as error:
        raise ParseError(
            f"{error} {_CZ_CODES}", option="sheet", hint=error.hint
        ) from error
    except ValidationError as error:
        raise ValidationError(
            f"{error} {_CZ_CODES}", option="sheet", hint=error.hint
        ) from error
    components = parser.components
    zone = int(components["strefa"]) if parser.sheet_system == "2000" else None
    bounds = parser.get_bbox()
    found = None
    if descendants is not None:
        scales = _SCALES[parser.sheet_system]
        try:
            below = parser.get_all_descendants(descendants)
        except ValidationError as error:
            error.option = "descendants"
            if descendants not in scales:
                error.allowed = scales
            raise
        found = SheetDescendants(
            descendants, len(below), tuple(item.sheet for item in below)
        )
    system = f"pl{parser.sheet_system}"
    return SheetInfo(
        sheet=parser.sheet,
        system=system,
        country="PL",
        sheet_system=parser.sheet_system,
        scale=parser.scale,
        components=MappingProxyType(components),
        zone=zone,
        crs=bounds.crs,
        bounds=bounds,
        commands=_accepting(system),
        hierarchy=_levels(parser.get_hierarchy_up()) if hierarchy else None,
        children=_levels(parser.get_children()) if children else None,
        descendants=found,
    )


def _blame(error: ValidationError, *, scale: str, sheet_system: str, area: str) -> None:
    """Set ``option`` of an error of a library sheet search that has none.

    The sheet system, the scale (with the values the system has) or else the area.
    """
    if error.option is None:
        if sheet_system not in _SCALES:
            error.option, error.allowed = "sheet_system", tuple(_SCALES)
        elif scale not in _SCALES[sheet_system]:
            error.option, error.allowed = "scale", _SCALES[sheet_system]
        else:
            error.option = area


def find_sheets(
    *,
    bbox: BBox | None = None,
    geometry: str | os.PathLike[str] | None = None,
    layer: str | None = None,
    scale: str,
    sheet_system: str,
) -> SheetList:
    """Return the sheets covering an area.

    ``find_sheets_for_bbox`` or ``find_sheets_for_geometry`` as a document.

    Parameters
    ----------
    bbox : BBox, optional
        The area as a rectangle (EPSG:2180, EPSG:4326 or a PL-2000 zone CRS).
    geometry : str or path, optional
        The area as a SHP or GPKG file (the sheets its features intersect).
    layer : str, optional
        The GPKG layer of ``geometry`` (default: the first one).
    scale : str
        The scale of the sheets: PL-1992 ``1:1000000`` to ``1:5000``, PL-2000
        ``1:10000`` to ``1:500``.
    sheet_system : str
        ``1992`` or ``2000``. Neither this nor ``scale`` has a default: the
        choice of the sheets is explicit.

    Returns
    -------
    SheetList
        The request and the sheet codes (sorted, none truncated).

    Raises
    ------
    ValidationError
        Not exactly one of ``bbox`` and ``geometry``, ``layer`` without
        ``geometry``, a wrong type, an unknown ``sheet_system`` or ``scale``
        or an area the library refuses (``option`` names the argument).
    """
    given = [
        name
        for name, value in (("bbox", bbox), ("geometry", geometry))
        if value is not None
    ]
    if len(given) != 1:
        raise ValidationError(
            "Podaj dokladnie jeden wybor obszaru: bbox albo geometry",
            options=("bbox", "geometry"),
        )
    if layer is not None:
        if not isinstance(layer, str):
            raise ValidationError(
                f"layer musi byc napisem (str), otrzymano {layer!r}", option="layer"
            )
        if geometry is None:
            raise ValidationError(
                "layer dotyczy tylko geometry (warstwa pliku GPKG z obszarem)",
                option="layer",
            )
    if bbox is not None:
        if not isinstance(bbox, BBox):
            raise ValidationError(
                f"bbox musi byc obiektem BBox (z ukladem), otrzymano {bbox!r}",
                option="bbox",
            )
        try:
            sheets = find_sheets_for_bbox(bbox, scale, sheet_system)
        except ValidationError as error:
            _blame(error, scale=scale, sheet_system=sheet_system, area="bbox")
            raise
        request = SheetRequest(
            scale, sheet_system, tuple(bbox_coords(bbox)), bbox.crs, None, None
        )
    else:
        if not isinstance(geometry, str | os.PathLike):
            raise ValidationError(
                f"geometry musi byc sciezka pliku, otrzymano {geometry!r}",
                option="geometry",
            )
        path = Path(geometry)
        try:
            sheets = find_sheets_for_geometry(
                path, scale, layer, sheet_system=sheet_system
            )
        except ValidationError as error:
            _blame(error, scale=scale, sheet_system=sheet_system, area="geometry")
            raise
        request = SheetRequest(scale, sheet_system, None, None, path, layer)
    return SheetList(request, tuple(sheets))
