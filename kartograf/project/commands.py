"""Data commands of project tasks (ADR-040; spec 5 of the project manifest).

``COMMANDS`` has one entry per data command of the CLI (``kartograf <grupa>
download``, ``soil hsg``): the option names of a task (the data flags of the
command in ``snake_case``; ``bbox`` as 4 numbers plus ``bbox_crs``) with
their JSON kinds, the validation without network that the download function
itself runs first, the download and ``check_*`` calls and the adapter of
the result family to the files a task pins. The project has no per-product
logic: a new product of an existing command changes nothing here, a new
data command (a new group) adds one entry - plus ``_task`` in its CLI
parser and a project task test.

Options exist in two forms: library arguments (``BBox``, ``Path``, per
country mappings, sequences) and the JSON form of ``tasks[].options``.
``options_to_json`` / ``options_from_json`` convert between them;
``check_options_json`` validates the JSON form read from a manifest.
"""

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Any, Literal, Protocol

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.download.collections import (
    check_collection,
    download_collection,
    require_collection_product,
    validate_collection_request,
)
from kartograf.download.data import (
    UnitFailure,
    UnitFile,
    check_data,
    download_data,
    validate_data_request,
)
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadProgress
from kartograf.download.options import (
    ELEVATION_PRODUCTS,
    IMAGERY_PRODUCTS,
    require_product,
)
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import ValidationError
from kartograf.hydrology.hsg import HSG_INPUTS, HSGCalculator, HsgResult
from kartograf.landcover.manager import (
    LandCoverAreaResult,
    LandCoverManager,
    require_landcover_source,
)
from kartograf.notices import Notice
from kartograf.project.model import PinRole

# JSON kind of a task option: ``bbox`` is a list of 4 numbers whose CRS is the
# ``bbox_crs`` option (one ``BBox`` argument of the library); ``path`` is a
# string resolved against the project directory; ``per_country`` is a string
# or ``{"pl": ..., "cz": ...}``; ``flag`` is ``true`` (``false`` is omitted).
OptionKind = Literal[
    "str", "int", "flag", "bbox", "bbox_crs", "path", "per_country", "str_list"
]
# Library arguments of a task (without ``output_dir`` and run options).
Options = dict[str, Any]


class TaskDownload(Protocol):
    """Download call of a command: the library function with the task options."""

    def __call__(
        self,
        output_dir: Path,
        options: Options,
        /,
        *,
        update: UpdateMode | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object: ...


class TaskCheck(Protocol):
    """``check_*`` call of a command: the update plan of the task options."""

    def __call__(
        self,
        output_dir: Path,
        options: Options,
        /,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan: ...


@dataclass(frozen=True)
class TaskFiles:
    """Store files of one task run (spec 4.6).

    ``complete``: full success of the result family (only then a task is
    pinned or re-pinned); ``files``: ``(role, unit, file)`` in result order;
    ``errors``: the failed parts when not complete.
    """

    complete: bool
    files: tuple[tuple[PinRole, str, VersionedFile], ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class TaskCommand:
    """One data command a project task may run (an entry of ``COMMANDS``).

    ``options``: JSON keys of ``tasks[].options`` (the data flags of the
    CLI command) with their kinds, in the order of the manifest.
    ``validate(output_dir, options)``: the checks of the download function
    before its first request (no network; ``ValidationError``).
    ``download``/``check``: the library function and its ``check_*`` twin.
    ``files(result)``: the pinned files of a result and its full success.
    """

    name: str
    options: Mapping[str, OptionKind]
    validate: Callable[[Path, Options], None]
    download: TaskDownload
    check: TaskCheck
    files: Callable[[Any], TaskFiles]


class UnitReport(Protocol):
    """A command-level report with one ``UnitFile`` per file (``DataReport``)."""

    @property
    def files(self) -> Sequence[UnitFile]: ...

    @property
    def failed(self) -> Sequence[UnitFailure]: ...

    @property
    def ok(self) -> bool: ...


def unit_report_files(report: UnitReport) -> TaskFiles:
    """Files of a ``DataReport``-like result: each file is an ``output``.

    Full success = ``ok`` without any failure: ``country="auto"`` with one
    country failed is ``ok`` for the CLI, but a project never pins half of
    a task.
    """
    return TaskFiles(
        complete=report.ok and not report.failed,
        files=tuple(("output", item.unit, item.file) for item in report.files),
        errors=tuple(failure.error for failure in report.failed),
    )


def _landcover_files(result: LandCoverAreaResult) -> TaskFiles:
    """Files of a ``LandCoverAreaResult``: the data files (``output``) and
    the original BDOT10k packages of ``keep_raw`` (``raw``)."""
    files: list[tuple[PinRole, str, VersionedFile]] = []
    for item in result.files:
        if item.file is not None:
            files.append(("output", item.unit, item.file))
        if item.raw is not None:
            files.append(("raw", item.unit, item.raw))
    return TaskFiles(
        complete=result.ok and all(item.file is not None for item in result.files),
        files=tuple(files),
        errors=tuple(f"{failure.unit}: {failure.error}" for failure in result.failed),
    )


def _hsg_files(result: HsgResult) -> TaskFiles:
    """Files of an ``HsgResult``: the HSG raster (``output``) and its three
    SoilGrids inputs (``input``, unit ``<property> <unit>``)."""
    files: list[tuple[PinRole, str, VersionedFile]] = []
    if result.file is not None:
        files.append(("output", result.unit, result.file))
    inputs = list(zip(HSG_INPUTS, result.inputs, strict=False))
    for prop, item in inputs:
        if item.file is not None:
            files.append(("input", f"{prop} {item.unit}", item.file))
    complete = (
        result.ok
        and result.file is not None
        and len(inputs) == len(HSG_INPUTS)
        and all(item.file is not None for _, item in inputs)
    )
    return TaskFiles(complete=complete, files=tuple(files), errors=())


# =============================================================================
# Commands
# =============================================================================

_AREA: dict[str, OptionKind] = {
    "sheet": "str",
    "bbox": "bbox",
    "bbox_crs": "bbox_crs",
    "geometry": "path",
    "layer": "str",
}
_CAMPAIGNS: dict[str, OptionKind] = {
    "year": "int",
    "min_year": "int",
    "max_year": "int",
    "all_campaigns": "flag",
    "full_sheet": "flag",
}


def _data_command(
    name: str, products: tuple[str, ...], options: dict[str, OptionKind]
) -> TaskCommand:
    """``download_data``/``check_data`` limited to the products of a group."""

    def validate(output_dir: Path, opts: Options) -> None:
        require_product(opts.get("product"), products)
        validate_data_request(output_dir=output_dir, **opts)

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        require_product(opts.get("product"), products)
        return download_data(
            output_dir=output_dir,
            update=update,
            cache=cache,
            on_progress=on_progress,
            on_notice=on_notice,
            **opts,
        )

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        require_product(opts.get("product"), products)
        return check_data(
            output_dir=output_dir, cache=cache, on_notice=on_notice, **opts
        )

    return TaskCommand(
        name, MappingProxyType(options), validate, download, check, unit_report_files
    )


def _landcover_command(
    name: str, source: str | None, options: dict[str, OptionKind]
) -> TaskCommand:
    """``LandCoverManager.download``/``.check``: of the task's ``source``
    (``landcover download``) or of a fixed source (``soil download``)."""

    def manager(
        output_dir: Path, opts: Options, cache: MetadataCache | bool
    ) -> tuple[LandCoverManager, Options]:
        rest = dict(opts)
        chosen = (
            source
            if source is not None
            else require_landcover_source(rest.pop("source", None))
        )
        return LandCoverManager(output_dir, chosen, cache=cache), rest

    def validate(output_dir: Path, opts: Options) -> None:
        lc, rest = manager(output_dir, opts, False)
        lc.validate_request(**rest)

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        lc, rest = manager(output_dir, opts, cache)
        return lc.download(
            **rest, update=update, on_notice=on_notice, on_progress=on_progress
        )

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        lc, rest = manager(output_dir, opts, cache)
        return lc.check(**rest, on_notice=on_notice)

    return TaskCommand(
        name, MappingProxyType(options), validate, download, check, _landcover_files
    )


def _hsg_command(name: str, options: dict[str, OptionKind]) -> TaskCommand:
    """``HSGCalculator.calculate_hsg``/``.check_hsg``; a missing ``depth``
    reaches the library as ``None`` (its own "--depth wymagane" error)."""

    def request(opts: Options) -> Options:
        return {"depth": None, **opts}

    def validate(output_dir: Path, opts: Options) -> None:
        HSGCalculator(output_dir, cache=False).validate_request(**request(opts))

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        calc = HSGCalculator(output_dir, cache=cache)
        return calc.calculate_hsg(**request(opts), update=update, on_notice=on_notice)

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        calc = HSGCalculator(output_dir, cache=cache)
        return calc.check_hsg(**request(opts), on_notice=on_notice)

    return TaskCommand(
        name, MappingProxyType(options), validate, download, check, _hsg_files
    )


def _collection_command(
    name: str, group: str, options: dict[str, OptionKind]
) -> TaskCommand:
    """``download_collection``/``check_collection`` limited to the products of
    a collection group (``boundaries``, ``cadastre``, ``models3d``, ``hydro``;
    ADR-042); the result family is ``CollectionReport`` (``unit_report_files``)."""

    def validate(output_dir: Path, opts: Options) -> None:
        require_collection_product(opts.get("product"), group)
        validate_collection_request(output_dir=output_dir, **opts)

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        require_collection_product(opts.get("product"), group)
        return download_collection(
            output_dir=output_dir,
            update=update,
            cache=cache,
            on_notice=on_notice,
            **opts,
        )

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        require_collection_product(opts.get("product"), group)
        return check_collection(
            output_dir=output_dir, cache=cache, on_notice=on_notice, **opts
        )

    return TaskCommand(
        name, MappingProxyType(options), validate, download, check, unit_report_files
    )


# The selection of a collection group (ADR-042 D9): product, country, unit
# or area; each group adds only its own content flags.
_COLLECTION: dict[str, OptionKind] = {
    "product": "str",
    "country": "str",
    "teryt": "str",
    **_AREA,
}
# A group without PL sources (``hydro``): no TERYT and no sheet code (both
# select PL units and sheets).
_CZ_COLLECTION: dict[str, OptionKind] = {
    name: kind for name, kind in _COLLECTION.items() if name not in ("teryt", "sheet")
}


COMMANDS: Mapping[str, TaskCommand] = MappingProxyType(
    {
        command.name: command
        for command in (
            _data_command(
                "elevation download",
                ELEVATION_PRODUCTS,
                {
                    "product": "str",
                    **_AREA,
                    "country": "str",
                    "resolution": "per_country",
                    "vertical_crs": "per_country",
                    "format": "str",
                    "sheet_system": "str",
                    "scale": "str",
                    "cutout": "flag",
                    "horizontal_crs": "str",
                    **_CAMPAIGNS,
                    "min_density": "int",
                },
            ),
            _data_command(
                "imagery download",
                IMAGERY_PRODUCTS,
                {
                    "product": "str",
                    **_AREA,
                    "country": "str",
                    "sheet_system": "str",
                    "scale": "str",
                    "cutout": "flag",
                    "horizontal_crs": "str",
                    "coverage": "str",
                    "resolution": "per_country",
                    **_CAMPAIGNS,
                },
            ),
            _landcover_command(
                "landcover download",
                None,
                {
                    "source": "str",
                    "teryt": "str",
                    **_AREA,
                    "whole_country": "flag",
                    "year": "int",
                    "format": "str",
                    "layers": "str_list",
                    "keep_raw": "flag",
                    "horizontal_crs": "str",
                },
            ),
            _landcover_command(
                "soil download",
                "soilgrids",
                {**_AREA, "property": "str", "depth": "str", "stat": "str"},
            ),
            _hsg_command("soil hsg", {**_AREA, "depth": "str"}),
            _collection_command(
                "boundaries download",
                "boundaries",
                {**_COLLECTION, "whole_country": "flag", "level": "per_country"},
            ),
            _collection_command("cadastre download", "cadastre", dict(_COLLECTION)),
            _collection_command(
                "models3d download",
                "models3d",
                {**_COLLECTION, "lod": "int", "year": "int"},
            ),
            _collection_command(
                "hydro download", "hydro", {**_CZ_COLLECTION, "whole_country": "flag"}
            ),
        )
    }
)


def data_commands_text() -> str:
    """The data commands a project accepts, for messages."""
    return ", ".join(COMMANDS)


def task_command(name: str) -> TaskCommand:
    """The entry of a data command.

    Raises
    ------
    ValidationError
        Not a data command (listing the accepted ones).
    """
    command = COMMANDS.get(name)
    if command is None:
        raise ValidationError(
            f"do projektu mozna dodac komendy zapisujace dane: {data_commands_text()}"
        )
    return command


# =============================================================================
# Options: library arguments <-> JSON form
# =============================================================================

_KIND_TEXT: dict[OptionKind, str] = {
    "str": "napis",
    "int": "liczba calkowita",
    "flag": "true",
    "bbox": "lista 4 liczb [min_x, min_y, max_x, max_y] z bbox_crs",
    "bbox_crs": "napis (uklad bbox) razem z bbox",
    "path": "niepusta sciezka (napis)",
    "per_country": 'napis albo obiekt {"pl": napis, "cz": napis}',
    "str_list": "lista napisow",
}


def _argument_names(command: TaskCommand) -> list[str]:
    """Library argument names of a command (``bbox_crs`` is part of ``bbox``)."""
    return [name for name, kind in command.options.items() if kind != "bbox_crs"]


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _json_value(kind: OptionKind, value: object) -> object | None:
    """The JSON form of one library argument; ``None`` = wrong type."""
    if kind == "str":
        return value if isinstance(value, str) else None
    if kind == "int":
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if kind == "flag":
        return True if value is True else None
    if kind == "path":
        if isinstance(value, str | os.PathLike) and os.fspath(value):
            return PurePath(os.fspath(value)).as_posix()
        return None
    if kind == "per_country":
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            return dict(value)
        return None
    if kind == "str_list":
        if isinstance(value, Sequence) and not isinstance(value, str):
            items = list(value)
            return items if all(isinstance(item, str) for item in items) else None
        return None
    return None


def options_to_json(command: TaskCommand, options: Mapping[str, object]) -> dict:
    """Library arguments of ``command`` -> ``tasks[].options`` (spec 3.3).

    ``None`` and ``False`` are omitted (only chosen values are recorded);
    keys follow the order of ``command.options``; a ``BBox`` becomes
    ``bbox`` (4 numbers) and ``bbox_crs``, a path a string with ``/``.

    Raises
    ------
    ValidationError
        An option of another command or not a library argument (e.g.
        ``output_dir``, ``update``, ``timeout``), or a value of a wrong type.
    """
    given = {
        name: value
        for name, value in options.items()
        if value is not None and value is not False
    }
    names = _argument_names(command)
    for name in given:
        if name not in names:
            raise ValidationError(
                f"opcja {name!r} nie nalezy do zadania komendy {command.name} "
                f"(opcje: {', '.join(names)})"
            )
    data: dict = {}
    for name in names:
        if name not in given:
            continue
        value = given[name]
        kind = command.options[name]
        if kind == "bbox":
            if not isinstance(value, BBox):
                raise ValidationError(f"opcja bbox: oczekiwano BBox, podano {value!r}")
            data["bbox"] = [value.min_x, value.min_y, value.max_x, value.max_y]
            data["bbox_crs"] = value.crs
            continue
        converted = _json_value(kind, value)
        if converted is None:
            raise ValidationError(
                f"opcja {name}: oczekiwano {_KIND_TEXT[kind]}, podano {value!r}"
            )
        data[name] = converted
    return data


def check_options_json(command: TaskCommand, data: object) -> str | None:
    """Error text of ``tasks[].options`` read from a manifest (``None`` = valid).

    Keys of ``command.options`` only, values of their kind; ``null`` and
    ``false`` are not written by Kartograf (an omitted key means "not
    chosen"); ``bbox`` and ``bbox_crs`` come together.
    """
    if not isinstance(data, dict):
        return "options: oczekiwano obiektu"
    for name, value in data.items():
        kind = command.options.get(name)
        if kind is None:
            return (
                f"options: opcja {name!r} nie nalezy do komendy {command.name} "
                f"(opcje: {', '.join(command.options)})"
            )
        if kind == "bbox":
            valid = (
                isinstance(value, list)
                and len(value) == 4
                and all(_is_number(v) and math.isfinite(v) for v in value)
                and "bbox_crs" in data
            )
        elif kind == "bbox_crs":
            valid = isinstance(value, str) and "bbox" in data
        elif kind == "path":
            valid = isinstance(value, str) and bool(value)
        else:
            valid = value is not False and _json_value(kind, value) is not None
        if not valid:
            return f"options.{name}: oczekiwano {_KIND_TEXT[kind]}"
    return None


def options_from_json(
    command: TaskCommand, data: Mapping[str, Any], *, project_dir: Path
) -> Options:
    """``tasks[].options`` (validated by ``check_options_json``) -> library
    arguments; a relative path is resolved against ``project_dir``."""
    options: Options = {}
    for name, value in data.items():
        kind = command.options[name]
        if kind == "bbox":
            x0, y0, x1, y1 = value
            options["bbox"] = BBox(x0, y0, x1, y1, str(data["bbox_crs"]))
        elif kind == "bbox_crs":
            continue
        elif kind == "path":
            path = Path(str(value))
            if not path.is_absolute():
                path = Path(os.path.abspath(project_dir / path))
            options[name] = path
        elif kind == "str_list":
            options[name] = tuple(value)
        elif kind == "per_country" and isinstance(value, Mapping):
            options[name] = dict(value)
        else:
            options[name] = value
    return options
