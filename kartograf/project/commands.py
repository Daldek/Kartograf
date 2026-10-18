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
country mappings, sequences) and the JSON form of ``tasks[].options``; the
conversion between them (``options_to_json``, ``options_from_json``,
``check_options_json``) is in ``kartograf.catalog.kinds``.
"""

import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.spec import Kind
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
from kartograf.hydrology.hsg import (
    HsgReport,
    calculate_hsg,
    check_hsg,
    validate_hsg_request,
)
from kartograf.landcover.manager import (
    LandCoverReport,
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
    require_landcover_product,
    validate_landcover_request,
    validate_soil_request,
)
from kartograf.notices import Notice
from kartograf.project.model import PinRole

# JSON kind of a task option (the kinds of the catalog parameters): ``bbox`` is
# a list of 4 numbers whose CRS is the ``bbox_crs`` option (one ``BBox``
# argument of the library); ``path`` is a string resolved against the project
# directory; ``per_country`` is a string or ``{"pl": ..., "cz": ...}``;
# ``flag`` is ``true`` (``false`` is omitted).
OptionKind = Kind
# Library arguments of a task (without ``output_dir`` and run options).
Options = dict[str, Any]


class TaskDownload(Protocol):
    """Download call of a command: the library function with the task options.

    ``workers``: parallel transfers of the task's files (``None`` = the
    default of the library function; HSG computes one raster from three
    inputs and has no workers).
    """

    def __call__(
        self,
        output_dir: Path,
        options: Options,
        /,
        *,
        update: UpdateMode | None,
        workers: int | None,
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


def _landcover_files(result: LandCoverReport) -> TaskFiles:
    """Data files and retained original packages, paired per unit."""
    files: list[tuple[PinRole, str, VersionedFile]] = []
    raw = {item.unit: item.file for item in result.raw}
    for item in result.files:
        files.append(("output", item.unit, item.file))
        if item.unit in raw:
            files.append(("raw", item.unit, raw.pop(item.unit)))
    files.extend(("raw", unit, file) for unit, file in raw.items())
    return TaskFiles(
        complete=result.ok and not result.failed,
        files=tuple(files),
        errors=tuple(f"{failure.unit}: {failure.error}" for failure in result.failed),
    )


def _hsg_files(result: HsgReport) -> TaskFiles:
    """HSG raster and its SoilGrids inputs (``<property> <unit>``)."""
    return TaskFiles(
        complete=(
            result.ok
            and not result.failed
            and bool(result.files)
            and len(result.inputs) == 3
        ),
        files=(
            *(("output", item.unit, item.file) for item in result.files),
            *(("input", item.unit, item.file) for item in result.inputs),
        ),
        errors=tuple(f"{failure.unit}: {failure.error}" for failure in result.failed),
    )


# =============================================================================
# Commands
# =============================================================================


def _run_options(workers: int | None) -> Options:
    """``workers`` for a library call; ``None`` keeps the function's default
    (``download_data``: 4, the other functions: 1, as the CLI groups)."""
    return {} if workers is None else {"workers": workers}


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
        workers: int | None,
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
            **_run_options(workers),
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
    name: str, product: str | None, options: dict[str, OptionKind]
) -> TaskCommand:
    """The land cover or SoilGrids command-level function."""

    def request(opts: Options) -> Options:
        if product is None:
            require_landcover_product(opts.get("product"))
            return opts
        return opts

    def validate(output_dir: Path, opts: Options) -> None:
        if product is None:
            validate_landcover_request(output_dir=output_dir, **request(opts))
        else:
            validate_soil_request(output_dir=output_dir, **request(opts))

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        workers: int | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        if product is None:
            return download_landcover(
                output_dir=output_dir,
                **request(opts),
                **_run_options(workers),
                cache=cache,
                update=update,
                on_notice=on_notice,
                on_progress=on_progress,
            )
        return download_soil(
            output_dir=output_dir,
            **request(opts),
            cache=cache,
            update=update,
            on_notice=on_notice,
        )

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        if product is None:
            return check_landcover(
                output_dir=output_dir, **request(opts), cache=cache, on_notice=on_notice
            )
        return check_soil(
            output_dir=output_dir, **request(opts), cache=cache, on_notice=on_notice
        )

    return TaskCommand(
        name,
        MappingProxyType(options),
        validate,
        download,
        check,
        _landcover_files if product is None else unit_report_files,
    )


def _hsg_command(name: str, options: dict[str, OptionKind]) -> TaskCommand:
    """Command-level ``calculate_hsg``/``check_hsg``."""

    def validate(output_dir: Path, opts: Options) -> None:
        validate_hsg_request(output_dir=output_dir, **opts)

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        workers: int | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        return calculate_hsg(
            output_dir=output_dir,
            **opts,
            cache=cache,
            update=update,
            on_notice=on_notice,
        )

    def check(
        output_dir: Path,
        opts: Options,
        *,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        return check_hsg(
            output_dir=output_dir, **opts, cache=cache, on_notice=on_notice
        )

    return TaskCommand(
        name, MappingProxyType(options), validate, download, check, _hsg_files
    )


def _collection_command(
    name: str, group: str, options: dict[str, OptionKind]
) -> TaskCommand:
    """``download_collection``/``check_collection`` limited to the products of
    a collection group (``boundaries``, ``cadastre``, ``models3d``, ``hydro``,
    ``names``, ``maps``, ``geodesy``; ADR-042); the result family is
    ``CollectionReport`` (``unit_report_files``)."""

    def validate(output_dir: Path, opts: Options) -> None:
        require_collection_product(opts.get("product"), group)
        validate_collection_request(output_dir=output_dir, **opts)

    def download(
        output_dir: Path,
        opts: Options,
        *,
        update: UpdateMode | None,
        workers: int | None,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> object:
        require_collection_product(opts.get("product"), group)
        return download_collection(
            output_dir=output_dir,
            update=update,
            cache=cache,
            on_progress=on_progress,
            on_notice=on_notice,
            **_run_options(workers),
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
_SHEET_COLLECTION: dict[str, OptionKind] = {
    name: kind for name, kind in _COLLECTION.items() if name != "teryt"
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
                    "model": "str",
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
                    "direction": "str_list",
                    "resolution": "per_country",
                    **_CAMPAIGNS,
                },
            ),
            _landcover_command(
                "landcover download",
                None,
                {
                    "product": "str",
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
                {
                    **_COLLECTION,
                    "whole_country": "flag",
                    "level": "per_country",
                    "format": "str",
                },
            ),
            _collection_command(
                "cadastre download",
                "cadastre",
                {**_COLLECTION, "ku": "str", "format": "str"},
            ),
            _collection_command(
                "models3d download",
                "models3d",
                {**_COLLECTION, "lod": "int", "year": "int"},
            ),
            _collection_command(
                "hydro download", "hydro", {**_CZ_COLLECTION, "whole_country": "flag"}
            ),
            _collection_command(
                "names download",
                "names",
                {
                    **_SHEET_COLLECTION,
                    "whole_country": "flag",
                    "format": "str",
                    "horizontal_crs": "str",
                },
            ),
            _collection_command(
                "maps download",
                "maps",
                {
                    **_SHEET_COLLECTION,
                    "scale": "str",
                    "format": "str",
                    "sheet_system": "str",
                },
            ),
            _collection_command(
                "geodesy download",
                "geodesy",
                {**_COLLECTION, "whole_country": "flag", "network": "per_country"},
            ),
        )
    }
)


def data_commands_text() -> str:
    """The data commands a project accepts, for messages."""
    return ", ".join(COMMANDS)


def project_command(project_dir: str | Path, subcommand: str, *args: str) -> str:
    """A ``kartograf project`` command of a hint, ready to paste: with
    ``--project <katalog>`` right after the subcommand when the project is
    not the current directory (``add`` takes it before the task name)."""
    words = ["kartograf", "project", subcommand]
    try:
        here = Path(project_dir).samefile(Path.cwd())
    except OSError:
        here = False
    if not here:
        words += ["--project", shlex.quote(str(project_dir))]
    return " ".join([*words, *args])


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
            f"do projektu mozna dodac komendy zapisujace dane: {data_commands_text()}",
            option="command",
            allowed=tuple(COMMANDS),
        )
    return command
