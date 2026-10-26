"""Data commands of project tasks (ADR-040; spec 5 of the project manifest).

``COMMANDS`` has one entry per data command of the CLI (``kartograf <grupa>
download``, ``soil hsg``): the option names of a task with their JSON kinds -
the parameters of the declaration of the command in ``kartograf.catalog`` that
are task options (``Command.task_options``; ``bbox`` as 4 numbers plus
``bbox_crs``) - the validation without network that the download function
itself runs first, the download and ``check_*`` calls and the adapter of
the result family to the files a task pins. The project has no per-product
logic: a new product of an existing command changes nothing here, a new
data command (a new group) adds its declaration to the catalog and one entry
here.

Options exist in two forms: library arguments (``BBox``, ``Path``, per
country mappings, sequences) and the JSON form of ``tasks[].options``; the
conversion between them (``options_to_json``, ``options_from_json``,
``check_options_json``) is in ``kartograf.catalog.kinds``, and ``task_arguments``
gives the library arguments of the options of a call (``project add``).
"""

import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments
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
from kartograf.messages import message
from kartograf.notices import Notice
from kartograf.project.model import PinRole
from kartograf.serialization import Document

# JSON kind of a task option (the kinds of the catalog parameters): ``bbox`` is
# a list of 4 numbers whose CRS is the ``bbox_crs`` option (one ``BBox``
# argument of the library); ``path`` is a string resolved against the project
# directory; ``per_country`` is a string or ``{"pl": ..., "cz": ...}``;
# ``flag`` is ``true`` (``false`` is omitted).
OptionKind = Kind
# Library arguments of a task (without ``root`` and run options).
Options = dict[str, Any]


class TaskDownload(Protocol):
    """Download call of a command: the library function with the task options.

    ``root`` (the store, ``None``: the default store) and ``output_dir`` (plain files)
    are the two targets: the library function takes at most one. ``workers``: parallel
    transfers of the task's files (``None`` = the default of the library function; HSG
    computes one raster from three inputs and has no workers). ``plan``: the plan of
    ``update="upgrade"`` (a project passes ``None``). ``summary``: HSG statistics in
    the report (``soil hsg`` only; the other commands ignore it).
    """

    def __call__(
        self,
        root: Path | None,
        options: Options,
        /,
        *,
        output_dir: Path | None = None,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int | None,
        summary: bool,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> Document:
        """Run the download of the task options into ``root`` or ``output_dir``."""
        ...


class TaskCheck(Protocol):
    """``check_*`` call of a command: the update plan of the task options.

    With ``output_dir`` the plan is that of a plain write; ``force`` makes an existing
    file a ``replace`` there.
    """

    def __call__(
        self,
        root: Path | None,
        options: Options,
        /,
        *,
        output_dir: Path | None = None,
        force: bool = False,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        """Plan the update of the task options in ``root`` or ``output_dir``."""
        ...


@dataclass(frozen=True)
class TaskFiles:
    """Store files of one task run (spec 4.6).

    ``complete``: full success of the result family (only then a task is
    pinned or re-pinned); ``files``: ``(role, unit, file)`` in result order;
    ``errors``: the failed parts when not complete, ``code`` and ``reason`` the
    registry code of the first of them (``None``: no failed part).
    """

    complete: bool
    files: tuple[tuple[PinRole, str, VersionedFile], ...]
    errors: tuple[str, ...]
    code: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TaskCommand:
    """One data command a project task may run (an entry of ``COMMANDS``).

    ``options``: JSON keys of ``tasks[].options`` (the data flags of the
    CLI command) with their kinds, in the order of the manifest.
    ``validate(root, options)``: the checks of the download function
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
    def files(self) -> Sequence[UnitFile]:
        """Return the data files, one per unit."""
        ...

    @property
    def failed(self) -> Sequence[UnitFailure]:
        """Return the failed units."""
        ...

    @property
    def ok(self) -> bool:
        """Return True when no unit failed."""
        ...


def _first_failure(failed: Sequence[UnitFailure]) -> tuple[str | None, str | None]:
    """Return the registry ``(code, reason)`` of the first failed unit, if any."""
    if not failed:
        return None, None
    return failed[0].code, failed[0].reason


def unit_report_files(report: UnitReport) -> TaskFiles:
    """Files of a ``DataReport``-like result: each file is an ``output``.

    Full success = ``ok`` without any failure: ``country="auto"`` with one
    country failed is ``ok`` for the CLI, but a project never pins half of
    a task.
    """
    code, reason = _first_failure(report.failed)
    return TaskFiles(
        complete=report.ok and not report.failed,
        files=tuple(("output", item.unit, item.file) for item in report.files),
        errors=tuple(failure.error for failure in report.failed),
        code=code,
        reason=reason,
    )


def _landcover_files(result: LandCoverReport) -> TaskFiles:
    """Pair data files and retained original packages per unit."""
    files: list[tuple[PinRole, str, VersionedFile]] = []
    raw = {item.unit: item.file for item in result.raw}
    for item in result.files:
        files.append(("output", item.unit, item.file))
        if item.unit in raw:
            files.append(("raw", item.unit, raw.pop(item.unit)))
    files.extend(("raw", unit, file) for unit, file in raw.items())
    code, reason = _first_failure(result.failed)
    return TaskFiles(
        complete=result.ok and not result.failed,
        files=tuple(files),
        errors=tuple(
            message("project.unit_problem", unit=failure.unit, problem=failure.error)
            for failure in result.failed
        ),
        code=code,
        reason=reason,
    )


def _hsg_files(result: HsgReport) -> TaskFiles:
    """HSG raster and its SoilGrids inputs (``<property> <unit>``)."""
    code, reason = _first_failure(result.failed)
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
        errors=tuple(
            message("project.unit_problem", unit=failure.unit, problem=failure.error)
            for failure in result.failed
        ),
        code=code,
        reason=reason,
    )


# =============================================================================
# Commands
# =============================================================================


def _run_options(workers: int | None) -> Options:
    """Return the ``workers`` keyword for a library call.

    ``None`` keeps the function's default (``download_data``: 4, the other functions: 1,
    as the CLI groups).
    """
    return {} if workers is None else {"workers": workers}


def _options(name: str) -> Mapping[str, OptionKind]:
    """Return the options of a task of a data command.

    They are the parameters of its declaration in the catalog that are task options, in
    the order of the manifest.
    """
    return MappingProxyType(declared_commands()[name].task_options)


def _data_command(name: str, products: tuple[str, ...]) -> TaskCommand:
    """``download_data``/``check_data`` limited to the products of a group."""

    def validate(root: Path, opts: Options) -> None:
        require_product(opts.get("product"), products)
        validate_data_request(root=root, **opts)

    def download(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int | None,
        summary: bool,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> Document:
        require_product(opts.get("product"), products)
        return download_data(
            root=root,
            output_dir=output_dir,
            update=update,
            plan=plan,
            cache=cache,
            on_progress=on_progress,
            on_notice=on_notice,
            **_run_options(workers),
            **opts,
        )

    def check(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        force: bool = False,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        require_product(opts.get("product"), products)
        return check_data(
            root=root,
            output_dir=output_dir,
            force=force,
            cache=cache,
            on_notice=on_notice,
            **opts,
        )

    return TaskCommand(
        name, _options(name), validate, download, check, unit_report_files
    )


def _landcover_command(name: str, product: str | None) -> TaskCommand:
    """Return the land cover or SoilGrids command-level function."""

    def request(opts: Options) -> Options:
        if product is None:
            require_landcover_product(opts.get("product"))
            return opts
        return opts

    def validate(root: Path, opts: Options) -> None:
        if product is None:
            validate_landcover_request(root=root, **request(opts))
        else:
            validate_soil_request(root=root, **request(opts))

    def download(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int | None,
        summary: bool,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> Document:
        if product is None:
            return download_landcover(
                root=root,
                output_dir=output_dir,
                **request(opts),
                **_run_options(workers),
                cache=cache,
                update=update,
                plan=plan,
                on_notice=on_notice,
                on_progress=on_progress,
            )
        return download_soil(
            root=root,
            output_dir=output_dir,
            **request(opts),
            cache=cache,
            update=update,
            plan=plan,
            on_notice=on_notice,
        )

    def check(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        force: bool = False,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        if product is None:
            return check_landcover(
                root=root,
                output_dir=output_dir,
                force=force,
                **request(opts),
                cache=cache,
                on_notice=on_notice,
            )
        return check_soil(
            root=root,
            output_dir=output_dir,
            force=force,
            **request(opts),
            cache=cache,
            on_notice=on_notice,
        )

    return TaskCommand(
        name,
        _options(name),
        validate,
        download,
        check,
        _landcover_files if product is None else unit_report_files,
    )


def _hsg_command(name: str) -> TaskCommand:
    """Command-level ``calculate_hsg``/``check_hsg``."""

    def validate(root: Path, opts: Options) -> None:
        validate_hsg_request(root=root, **opts)

    def download(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int | None,
        summary: bool,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> Document:
        return calculate_hsg(
            root=root,
            output_dir=output_dir,
            **opts,
            cache=cache,
            update=update,
            plan=plan,
            summary=summary,
            on_notice=on_notice,
        )

    def check(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        force: bool = False,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        return check_hsg(
            root=root,
            output_dir=output_dir,
            force=force,
            **opts,
            cache=cache,
            on_notice=on_notice,
        )

    return TaskCommand(name, _options(name), validate, download, check, _hsg_files)


def _collection_command(name: str, group: str) -> TaskCommand:
    """Build the command limited to the products of a collection group.

    It wraps ``download_collection``/``check_collection`` for a group (``boundaries``,
    ``cadastre``, ``models3d``, ``hydro``, ``names``, ``maps``, ``geodesy``; ADR-042);
    the result family is ``CollectionReport`` (``unit_report_files``).
    """

    def validate(root: Path, opts: Options) -> None:
        require_collection_product(opts.get("product"), group)
        validate_collection_request(root=root, **opts)

    def download(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        update: UpdateMode | None,
        plan: UpdatePlan | None,
        workers: int | None,
        summary: bool,
        cache: MetadataCache | bool,
        on_progress: Callable[[DownloadProgress], None] | None,
        on_notice: Callable[[Notice], None] | None,
    ) -> Document:
        require_collection_product(opts.get("product"), group)
        return download_collection(
            root=root,
            output_dir=output_dir,
            update=update,
            plan=plan,
            cache=cache,
            on_progress=on_progress,
            on_notice=on_notice,
            **_run_options(workers),
            **opts,
        )

    def check(
        root: Path | None,
        opts: Options,
        *,
        output_dir: Path | None = None,
        force: bool = False,
        cache: MetadataCache | bool,
        on_notice: Callable[[Notice], None] | None,
    ) -> UpdatePlan:
        require_collection_product(opts.get("product"), group)
        return check_collection(
            root=root,
            output_dir=output_dir,
            force=force,
            cache=cache,
            on_notice=on_notice,
            **opts,
        )

    return TaskCommand(
        name, _options(name), validate, download, check, unit_report_files
    )


COMMANDS: Mapping[str, TaskCommand] = MappingProxyType(
    {
        command.name: command
        for command in (
            _data_command("elevation download", ELEVATION_PRODUCTS),
            _data_command("imagery download", IMAGERY_PRODUCTS),
            _landcover_command("landcover download", None),
            _landcover_command("soil download", "soilgrids"),
            _hsg_command("soil hsg"),
            _collection_command("boundaries download", "boundaries"),
            _collection_command("cadastre download", "cadastre"),
            _collection_command("models3d download", "models3d"),
            _collection_command("hydro download", "hydro"),
            _collection_command("names download", "names"),
            _collection_command("maps download", "maps"),
            _collection_command("geodesy download", "geodesy"),
        )
    }
)


def data_commands_text() -> str:
    """Return the data commands a project accepts, for messages."""
    return ", ".join(COMMANDS)


def project_command(project_dir: str | Path, subcommand: str, *args: str) -> str:
    """Return a ``kartograf project`` command of a hint, ready to paste.

    It has ``--project <katalog>`` right after the subcommand when the project is not
    the current directory (``add`` takes it before the task name).
    """
    words = ["kartograf", "project", subcommand]
    try:
        here = Path(project_dir).samefile(Path.cwd())
    except OSError:
        here = False
    if not here:
        words += ["--project", shlex.quote(str(project_dir))]
    return " ".join([*words, *args])


def task_command(name: str) -> TaskCommand:
    """Return the entry of a data command.

    Raises
    ------
    ValidationError
        Not a data command (listing the accepted ones).
    """
    command = COMMANDS.get(name)
    if command is None:
        raise ValidationError(
            message(
                "project.data_commands_allowed", data_commands_text=data_commands_text()
            ),
            option="command",
            allowed=tuple(COMMANDS),
        )
    return command


def task_arguments(name: str, options: Mapping[str, object]) -> Options:
    """Return the options of a task in the JSON form as the library arguments.

    The form ``add_project_task`` takes: ``bbox`` with ``bbox_crs`` becomes one
    ``BBox``, a path a ``Path`` (a relative one stays relative), a list a tuple.
    ``kartograf project add``, ``run_command("project add", ...)`` and the MCP tool
    ``kartograf_project_add`` read the options of the task in the JSON form (the
    keys of ``kartograf commands schema``) and convert them with this function.

    Parameters
    ----------
    name : str
        The data command of the task (``elevation download``).
    options : Mapping
        Its options in the JSON form.

    Raises
    ------
    ValidationError
        Not a data command (``option="command"``, ``allowed``), an option the
        command does not have or a value of a wrong form (``option`` names it).
    """
    return convert_arguments(task_command(name).options, options)
