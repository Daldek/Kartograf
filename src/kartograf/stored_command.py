"""The command of a stored file (KB-6 of Archiwista, ADR-057).

``command_for_file`` reads the sidecar of a store file and returns the store-mode
``CommandCall`` of the catalog command that selects that file again: the call
``format_command``, ``validate_command``, ``run_command`` and ``check_command``
take, without the store root (the caller gives ``root``). Archiwista pins stored
versions itself and needs it to check a pin for updates and to restore it.

The call is rebuilt from what the sidecar records - ``dataset`` (the product and,
through the variant registry, the resolution, the height system, the format and the
CUZK model), ``request`` (the sheet, the box or the unit of the file and its content
choices) and ``extra`` (the campaign year, the LAZ tile year, the view direction) -
and pins every option that chooses a version where the command has one: a PL sheet
or LAZ tile gets its data year with ``all_campaigns`` (the year alone selects the
newest flight of the year, which need not be this one). Nothing is guessed: a file
whose sidecar does not give the call is refused with ``CommandNotRebuildableError``
(``unsupported``, ``details.reason`` ``command_not_rebuildable``, ``details.family``),
a field of a wrong form is ``InvalidSidecarError`` (``data_error``).

Families (``details.family``):

- ``sheet``: an elevation or imagery file of one sheet (PL NMT/NMPT grids and
  archives, orthophotomaps, CZ rasters, CZ contours, CZ orthophoto);
- ``cutout``: an elevation or imagery cutout of a box (PL WCS in EPSG:2180, PL
  orthophoto, CZ); a PL WCS cutout reprojected to another CRS is refused - its
  recorded grid is the envelope of the requested area, not that area;
- ``laz``: a PL LAZ tile (the area of its request) or a CZ LAZ sheet;
- ``unit``: a land cover, soil or collection file of one unit: TERYT, CZ cadastral
  area, sheet or the whole country;
- ``area`` (refused): a land cover, soil or collection file chosen by a box or an
  index tile of an area, and a NMT 100 m voivodeship file - the selection a command
  could repeat is not in the sidecar;
- ``hsg`` (refused): ``soil hsg``, derived from SoilGrids inputs its sidecar does
  not record (decision D5 of the plan of ADR-057);
- ``unknown`` (refused): a dataset the registry does not know or a request that
  names no selection.
"""

import math
from collections.abc import Mapping
from typing import Any, Literal, NoReturn

from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.spec import Command
from kartograf.commands import CommandCall
from kartograf.download.cz_contours import PRODUCT as CONTOURS
from kartograf.download.options import ELEVATION_PRODUCTS, IMAGERY_PRODUCTS
from kartograf.exceptions import (
    CommandNotRebuildableError,
    InvalidSidecarError,
    ValidationError,
)
from kartograf.messages import message
from kartograf.sources.descriptor import SourceDescriptor
from kartograf.sources.registry import get_source, resolve_vertical_crs
from kartograf.store import Sidecar

Family = Literal["sheet", "cutout", "laz", "unit", "area", "hsg", "unknown"]

# The derived product of ``soil hsg`` (``build_metadata(product=)``).
_HSG = "hsg"
# The units a land cover, soil or collection command selects by an option.
_UNIT_KEYS = ("teryt", "ku", "sheet", "whole_country")
# Selections of an area: the units behind them are not in the sidecar.
_AREA_KEYS = ("bbox", "tile")
# The CRS of a PL WCS cutout that its recorded grid gives back (no reprojection).
_PL_NATIVE_CRS = "EPSG:2180"


def _refuse(
    sidecar: Sidecar,
    family: Family,
    key: str,
    *,
    field: str | None = None,
    **params: Any,
) -> NoReturn:
    """Raise the refusal ``key`` (a ``commands`` message) of a file of ``family``."""
    raise CommandNotRebuildableError(
        message(key, dataset=sidecar.dataset, field=field, **params),
        family=family,
        field=field,
    )


def _malformed(
    sidecar: Sidecar,
    field: str,
    value: object,
    cause: Exception | None = None,
) -> NoReturn:
    """Raise ``InvalidSidecarError`` for a field of a wrong form."""
    raise InvalidSidecarError(
        message(
            "commands.file_field_malformed",
            dataset=sidecar.dataset,
            field=field,
            value=repr(value),
        ),
        field=field,
        hint=message("commands.file_field_malformed_hint"),
    ) from cause


def _text(
    sidecar: Sidecar, data: Mapping[str, Any], name: str, field: str
) -> str | None:
    """Return a text field: ``None`` if absent, ``InvalidSidecarError`` if not text."""
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        _malformed(sidecar, field, value)
    return value


def _year(sidecar: Sidecar, value: object, field: str) -> int | None:
    """Return a year written as a number or as digits; ``None`` when absent."""
    if value is None:
        return None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    _malformed(sidecar, field, value)


def _needed[T](sidecar: Sidecar, family: Family, value: T | None, field: str) -> T:
    """Return ``value``; refuse the file when the sidecar lacks it."""
    if value is None:
        _refuse(sidecar, family, "commands.file_missing_field", field=field)
    return value


def _bbox(
    sidecar: Sidecar, request: Mapping[str, Any], family: Family
) -> tuple[list[float], str]:
    """Return ``request.bbox`` as four numbers and its ``bbox_crs``."""
    bbox = _needed(sidecar, family, request.get("bbox"), "request.bbox")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or not all(
            isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
            for v in bbox
        )
    ):
        _malformed(sidecar, "request.bbox", bbox)
    crs = _needed(
        sidecar,
        family,
        _text(sidecar, request, "bbox_crs", "request.bbox_crs"),
        "request.bbox_crs",
    )
    return [float(v) for v in bbox], crs


def _source(sidecar: Sidecar) -> Mapping[str, Any]:
    source = (sidecar.extra or {}).get("source")
    return source if isinstance(source, Mapping) else {}


def _variant_options(
    sidecar: Sidecar, descriptor: SourceDescriptor, family: Family
) -> dict[str, Any]:
    """Return the options of the dataset's variant of the sidecar's height system.

    ``resolution``, ``vertical_crs``, ``format`` (an archive of the sheet index or
    CZ contours) and ``model`` (CZ, for LAZ): the inverse of the variant registry
    (ADR-041). A dataset without variants (orthophotomaps) gives none.
    """
    if not descriptor.variants:
        return {}
    code = sidecar.vertical_crs
    if code is None and any(v.vertical_crs for v in descriptor.variants):
        _refuse(sidecar, family, "commands.file_missing_field", field="vertical_crs")
    found = {
        (v.label, v.vertical_crs, v.format, v.model, v.source_file)
        for v in descriptor.variants
        if (v.vertical_crs is None and code is None)
        or (
            v.vertical_crs is not None
            and code is not None
            and resolve_vertical_crs(v.vertical_crs, (code,)) == code
        )
    }
    if len(found) != 1:
        _malformed(sidecar, "vertical_crs", code)
    label, vertical, fmt, model, source_file = found.pop()
    options: dict[str, Any] = {}
    if label is not None:
        options["resolution"] = label
    if vertical is not None:
        options["vertical_crs"] = vertical
    if source_file or descriptor.product == CONTOURS:
        options["format"] = fmt
    if model is not None and descriptor.product == "laz":
        options["model"] = model
    return options


def _country(sidecar: Sidecar, family: Family) -> str:
    country = _needed(sidecar, family, sidecar.country, "country")
    if country not in ("PL", "CZ"):
        _malformed(sidecar, "country", country)
    return country.lower()


def _sheet_options(
    sidecar: Sidecar, descriptor: SourceDescriptor, request: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the options of a file of one sheet: sheet, variant, campaign year."""
    options: dict[str, Any] = {
        "product": descriptor.product,
        "sheet": _text(sidecar, request, "sheet", "request.sheet"),
        **_variant_options(sidecar, descriptor, "sheet"),
    }
    source = _source(sidecar)
    if sidecar.campaign is not None or "campaigns" in request:
        field = "extra.source.acquisition_year"
        year = _year(sidecar, source.get("acquisition_year"), field)
        options["year"] = _needed(sidecar, "sheet", year, field)
        options["all_campaigns"] = True
    if descriptor.product == "oblique-orto":
        field = "extra.source.direction"
        direction = _text(sidecar, source, "direction", field)
        options["direction"] = [_needed(sidecar, "sheet", direction, field)]
    return options


def _cutout_options(
    sidecar: Sidecar,
    descriptor: SourceDescriptor,
    request: Mapping[str, Any],
    command: str,
) -> dict[str, Any]:
    """Return the options of a cutout: the box of its grid in the result CRS."""
    bbox, crs = _bbox(sidecar, request, "cutout")
    country = _country(sidecar, "cutout")
    options: dict[str, Any] = {
        "product": descriptor.product,
        "country": country,
        "bbox": bbox,
        "bbox_crs": crs,
        "cutout": True,
        "horizontal_crs": crs,
    }
    if command == "imagery download":
        if country != "pl":
            _refuse(
                sidecar,
                "unknown",
                "commands.file_no_selection",
                keys="bbox",
                command=command,
            )
        coverage = _text(sidecar, request, "coverage", "request.coverage")
        if coverage is not None:
            options["coverage"] = coverage
        options["resolution"] = _needed(
            sidecar,
            "cutout",
            _text(sidecar, request, "resolution", "request.resolution"),
            "request.resolution",
        )
        return options
    if country == "pl" and crs != _PL_NATIVE_CRS:
        _refuse(sidecar, "cutout", "commands.file_reprojected_cutout", crs=crs)
    return {**options, **_variant_options(sidecar, descriptor, "cutout")}


def _laz_options(
    sidecar: Sidecar, descriptor: SourceDescriptor, request: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the options of a LAZ file: PL its request area and year, CZ its sheet."""
    options: dict[str, Any] = {"product": "laz"}
    if _country(sidecar, "laz") == "cz":
        options["sheet"] = _needed(
            sidecar,
            "laz",
            _text(sidecar, request, "sheet", "request.sheet"),
            "request.sheet",
        )
        return {**options, **_variant_options(sidecar, descriptor, "laz")}
    bbox, crs = _bbox(sidecar, request, "laz")
    field = "extra.year"
    year = _year(sidecar, (sidecar.extra or {}).get("year"), field)
    options.update(
        country="pl",
        bbox=bbox,
        bbox_crs=crs,
        **_variant_options(sidecar, descriptor, "laz"),
        year=_needed(sidecar, "laz", year, field),
        all_campaigns=True,
    )
    density = request.get("min_density")
    if density is not None:
        options["min_density"] = density
    return options


def _unit_options(
    sidecar: Sidecar,
    descriptor: SourceDescriptor,
    request: Mapping[str, Any],
    declaration: Command,
) -> dict[str, Any]:
    """Return the options of a land cover, soil or collection file of one unit."""
    names = {param.name for param in declaration.call_options}
    options: dict[str, Any] = {}
    if "product" in names:
        options["product"] = descriptor.product
    if "country" in names:
        options["country"] = _country(sidecar, "unit")
    for key, value in request.items():
        if value is None:
            continue
        if key not in names:
            _refuse(
                sidecar,
                "unit",
                "commands.file_not_an_option",
                field=f"request.{key}",
                command=declaration.id,
            )
        options[key] = value
    if (
        descriptor.product == "bdot10k"
        and options.get("format") == "GPKG"
        and "year" not in options
    ):
        # The raw package (``keep_raw``) and the GPKG of a powiat have one request:
        # with ``keep_raw`` the call selects the file whichever of the two it is.
        options["keep_raw"] = True
    return options


def _command_id(sidecar: Sidecar, descriptor: SourceDescriptor) -> str:
    """Return the data command of the catalog that downloads the dataset."""
    product = descriptor.product
    if product in ELEVATION_PRODUCTS:
        return "elevation download"
    if product in IMAGERY_PRODUCTS:
        return "imagery download"
    group = descriptor.storage_subdir.split("/", 1)[0]
    command = declared_commands().get(f"{group} download")
    if command is None or command.kind != "data":
        _refuse(sidecar, "unknown", "commands.file_unknown_dataset", field="dataset")
    return command.id


def command_for_file(sidecar: Sidecar) -> CommandCall:
    """Return the command that selects a stored file again (KB-6, ADR-057).

    Read-only and without network: the store-mode ``CommandCall`` of the data
    command of the file, rebuilt from its sidecar, with every option that chooses
    a version pinned where the command has one (the data year of a PL sheet or LAZ
    tile with ``all_campaigns``, the height system, the resolution, the format, the
    CUZK model, the view direction). ``run`` is empty: the caller gives ``root``
    to ``run_command``/``check_command``. ``format_command`` writes it and
    ``parse_command`` reads that line back into the same call.

    Parameters
    ----------
    sidecar : Sidecar
        The sidecar of the file as ``read_sidecar`` returns it.

    Returns
    -------
    CommandCall
        The command id, its options (JSON form, in the order of the parameters of
        the command) and an empty ``run``.

    Raises
    ------
    ValidationError
        ``sidecar`` is not a ``Sidecar`` (``option="sidecar"``).
    CommandNotRebuildableError
        No command selects this file again (``unsupported``, ``details.reason``
        ``command_not_rebuildable``): a land cover, soil or collection file chosen
        by an area (also CZ), a NMT 100 m voivodeship file, ``soil hsg``, a PL WCS
        cutout reprojected to another CRS, an unknown dataset, or a sidecar without
        a field the command needs (``details.family``; ``details.field`` names the
        missing field).
    InvalidSidecarError
        A field the call is read from has a value of a wrong form (``data_error``;
        ``details.field`` names it).

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from kartograf import command_for_file, format_command, read_sidecar
    >>> from kartograf.testing import build_fixture_store
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     store = build_fixture_store(Path(tmp) / "data")
    ...     call = command_for_file(read_sidecar(store.files[0].versions[0].path))
    >>> format_command(call.command, call.options)
    'kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 \
--resolution 1m --vertical-crs EVRF2007 --year 2022 --all-campaigns'
    """
    if not isinstance(sidecar, Sidecar):
        raise ValidationError(
            message("commands.file_sidecar_type", kind=type(sidecar).__name__),
            option="sidecar",
        )
    if sidecar.product == _HSG:
        _refuse(sidecar, "hsg", "commands.file_hsg")
    if sidecar.dataset_key is None:
        _refuse(sidecar, "unknown", "commands.file_unknown_dataset", field="dataset")
    descriptor = get_source(sidecar.dataset_key)
    command = _command_id(sidecar, descriptor)
    declaration = declared_commands()[command]
    if "request" in sidecar.raw and sidecar.request is None:
        _malformed(sidecar, "request", sidecar.raw["request"])
    request = _needed(sidecar, "unknown", sidecar.request, "request")
    options: dict[str, Any]
    if command in ("elevation download", "imagery download"):
        if descriptor.product == "laz":
            options = _laz_options(sidecar, descriptor, request)
        elif "sheet" in request:
            options = _sheet_options(sidecar, descriptor, request)
        elif "bbox" in request:
            options = _cutout_options(sidecar, descriptor, request, command)
        elif "teryt" in request:
            _refuse(sidecar, "area", "commands.file_area")
        else:
            _refuse(
                sidecar,
                "unknown",
                "commands.file_no_selection",
                keys=", ".join(request) or "-",
                command=command,
            )
    elif any(key in request for key in _AREA_KEYS):
        _refuse(sidecar, "area", "commands.file_area")
    elif any(key in request for key in _UNIT_KEYS):
        options = _unit_options(sidecar, descriptor, request, declaration)
    else:
        _refuse(
            sidecar,
            "unknown",
            "commands.file_no_selection",
            keys=", ".join(request) or "-",
            command=command,
        )
    kinds = {param.name: param.kind for param in declaration.call_options}
    try:
        convert_arguments(kinds, options)
    except ValidationError as error:
        field = error.option or "request"
        _malformed(sidecar, field, options.get(field), error)
    ordered = {name: options[name] for name in kinds if name in options}
    return CommandCall(command, ordered, {})
