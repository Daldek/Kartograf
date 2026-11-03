"""The data commands of the catalog as library calls (``kartograf.commands``).

``DATA_COMMANDS`` has one entry per data command of the CLI (``kartograf <group>
download``, ``soil hsg``; the commands of kind ``data`` in ``kartograf.catalog``): the
options of a call with their JSON kinds (``Command.call_options``; ``bbox`` as 4
numbers plus ``bbox_crs``), the validation without network that the download function
itself runs first, and the download and ``check_*`` calls limited to the products of
the group. ``validate_command``, ``run_command`` and ``check_command`` call a data
command through its entry. A new product of an existing command changes nothing here;
a new data command (a new group) adds its declaration to the catalog and one entry
here.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.spec import Kind
from kartograf.download.collections import (
    check_collection,
    download_collection,
    require_collection_product,
    validate_collection_request,
)
from kartograf.download.data import check_data, download_data, validate_data_request
from kartograf.download.fetch import UpdateMode
from kartograf.download.manager import DownloadProgress
from kartograf.download.options import (
    ELEVATION_PRODUCTS,
    IMAGERY_PRODUCTS,
    require_product,
)
from kartograf.download.plan import UpdatePlan
from kartograf.hydrology.hsg import calculate_hsg, check_hsg, validate_hsg_request
from kartograf.landcover.manager import (
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
    require_landcover_product,
    validate_landcover_request,
    validate_soil_request,
)
from kartograf.notices import Notice
from kartograf.serialization import Document

# Library arguments of a call (without the targets and the options of a run).
Options = dict[str, Any]


class DataDownload(Protocol):
    """Download call of a command: the library function with the options of a call.

    ``root`` (the store, ``None``: the default store) and ``output_dir`` (plain files)
    are the two targets: the library function takes at most one. ``workers``: parallel
    transfers (``None`` = the default of the library function; HSG computes one raster
    from three inputs and has no workers). ``plan``: the plan of ``update="upgrade"``.
    ``summary``: HSG statistics in the report (``soil hsg`` only; the other commands
    ignore it).
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
        """Run the download of the options into ``root`` or ``output_dir``."""
        ...


class DataCheck(Protocol):
    """``check_*`` call of a command: the update plan of the options of a call.

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
        """Plan the update of the options in ``root`` or ``output_dir``."""
        ...


@dataclass(frozen=True)
class DataCommand:
    """One data command of the catalog (an entry of ``DATA_COMMANDS``).

    ``options``: the options of a call (the data flags of the CLI command) with their
    kinds, in the order of the declaration. ``validate(root, options)``: the checks of
    the download function before its first request (no network; ``ValidationError``).
    ``download``/``check``: the library function and its ``check_*`` twin.
    """

    name: str
    options: Mapping[str, Kind]
    validate: Callable[[Path, Options], None]
    download: DataDownload
    check: DataCheck


def _run_options(workers: int | None) -> Options:
    """Return the ``workers`` keyword for a library call.

    ``None`` means the library default; an explicit value is forwarded
    so that ``workers=0`` is rejected by the library.
    """
    return {} if workers is None else {"workers": workers}


def _options(name: str) -> Mapping[str, Kind]:
    """Return the options of a call of a data command with their kinds.

    The keys and kinds are those of the declaration of the command in the catalog
    (``Command.call_options``).
    """
    return MappingProxyType(
        {param.name: param.kind for param in declared_commands()[name].call_options}
    )


def _data_command(name: str, products: tuple[str, ...]) -> DataCommand:
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

    return DataCommand(name, _options(name), validate, download, check)


def _landcover_command(name: str, product: str | None) -> DataCommand:
    """Return the land cover or SoilGrids command-level function."""

    def request(opts: Options) -> Options:
        if product is None:
            require_landcover_product(opts.get("product"))
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

    return DataCommand(name, _options(name), validate, download, check)


def _hsg_command(name: str) -> DataCommand:
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

    return DataCommand(name, _options(name), validate, download, check)


def _collection_command(name: str, group: str) -> DataCommand:
    """Build the command limited to the products of a collection group.

    It wraps ``download_collection``/``check_collection`` for a group (``boundaries``,
    ``cadastre``, ``models3d``, ``hydro``, ``names``, ``maps``, ``geodesy``; ADR-042).
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

    return DataCommand(name, _options(name), validate, download, check)


DATA_COMMANDS: Mapping[str, DataCommand] = MappingProxyType(
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
