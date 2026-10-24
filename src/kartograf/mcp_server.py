"""The MCP server of Kartograf (AGI section 5).

One tool per command of the catalog (``kartograf.catalog.tools``), over stdio, for AI
agents. The name of a tool is the ``operation_id`` of its command
(``kartograf_elevation_download``); ``kartograf_commands_list`` and
``kartograf_commands_schema`` are the catalog. Every tool calls one function of the
library and answers with the envelope ``kartograf-result/1`` of its command
(``to_dict()``, the same document as the CLI ``--json``; the domain document is its
``result``); a failure that stops the call is the ``kartograf-error/1`` document with
``isError``. Everything the server says is English (AGI-9.2).

The server starts read only. Without ``--allow-writes`` a command that writes and has
a check only plans (``check_updates`` is true, the options of a run are refused with
``forbidden``) and ``project init``, ``project add`` and ``project remove`` answer
``forbidden``; ``--allow-writes`` needs ``--allow-dir``. With ``--allow-dir`` every
path of a call must lie inside one of the directories (``forbidden`` otherwise), also
the paths nested in the options of ``project add``; without it any absolute path can
be read. The module is the only one that touches the MCP SDK, and it imports the SDK
lazily: ``import kartograf.mcp_server`` works without the ``mcp`` package,
``create_server`` and ``main`` report its absence as ``missing_dependency``.

Run it with ``kartograf-mcp`` or ``python -m kartograf.mcp_server``.

Examples
--------
Claude Code::

    claude mcp add kartograf -- kartograf-mcp

Other clients (``mcpServers``)::

    {"command": "kartograf-mcp", "args": ["--allow-dir", "/home/ola/dane"]}
"""

from __future__ import annotations

import argparse
import copy
import difflib
import functools
import inspect
import logging
import sys
import threading
from collections.abc import AsyncGenerator, Callable, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import kartograf
from kartograf.cache.defaults import default_cache_path
from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.spec import CHECK_OPTION, PathRole
from kartograf.catalog.tools import (
    ALWAYS_LOAD_KEY,
    FAMILIES,
    RUN_OPTIONS,
    ToolSpec,
    check_families,
    hidden_tools,
    parse_families,
    task_paths,
    tool_specs,
)
from kartograf.commands import check_command, run_command, validate_command
from kartograf.config import LANGUAGES, check_config, resolve
from kartograf.download.manager import DownloadProgress
from kartograf.envelope import CommandResult, wrap
from kartograf.error_report import ErrorReport, error_line, error_report
from kartograf.exceptions import (
    ForbiddenError,
    KartografError,
    MissingDependencyError,
    UsageError,
    ValidationError,
)

if TYPE_CHECKING:
    import anyio
    import mcp_types as types
    from anyio.from_thread import BlockingPortal
    from mcp.server import Server, ServerRequestContext
    from mcp.server.session import ServerSession

logger = logging.getLogger(__name__)

SDK_REQUIREMENT = "mcp>=2.3.0,<3"
"""The requirement on the SDK; the ``mcp`` extra of the package says the same."""

INSTRUCTIONS_MAX = 4096
"""Claude Code cuts the instructions of a server at this many characters (DOC-1.7)."""

# At most this many calls that use the network run at once (AGI-5.11): several
# conversations do not flood GUGiK and CUZK with parallel jobs.
MAX_NETWORK_CALLS = 4

_PATH_HINT = "Give an absolute path, for example /home/ola/dane/kartograf."
_WRITES_HINT = (
    "Start kartograf-mcp with --allow-writes and --allow-dir DIR to run and write; "
    "check_updates=true plans without writing."
)


def _tool(command: str) -> str:
    """Return the name of the tool of a catalog command (``commands list``)."""
    return declared_commands()[command].operation_id


def build_instructions(
    *,
    allow_writes: bool = False,
    allow_dirs: Sequence[Path | str] = (),
    families: Sequence[str] | None = None,
) -> str:
    """Return the ``instructions`` of the server (AGI-5.10).

    What the descriptions of the tools cannot say once for all of them: the order of
    the work (discover, check, run, read), the arguments they share, the update modes,
    what the results and the errors are, and the state of this server (writes,
    directories, families). The names of the tools are read from the catalog.
    Claude Code loads this text at the start of every session and cuts it at
    ``INSTRUCTIONS_MAX`` characters.

    Parameters
    ----------
    allow_writes : bool
        The server writes (``--allow-writes``).
    allow_dirs : sequence of path
        The directories of ``--allow-dir``.
    families : sequence of str, optional
        The families of ``--tools`` (``None``: every tool).
    """
    schema = _tool("commands schema")
    flow = (
        "Kartograf downloads spatial data of Poland and Czechia (GUGiK, CUZK, "
        "Copernicus, ISRIC) into a versioned store: the directory output_dir, one "
        "directory per product, files never overwritten. Order: discover, check, run, "
        f"read. Discover with {_tool('commands list')} (groups, products and commands) "
        f'and {schema}(command="elevation download") (the options of one command, '
        "its allowed values with their meanings, rules, examples and errors). What "
        f"years, grids and CRSs an area has: {_tool('elevation availability')}. Read "
        f"the store: {_tool('store overview')}, {_tool('store entries')}, "
        f"{_tool('store sidecar')}; the sidecar of a file has its CRS, source and "
        "licence."
    )
    shared = (
        "Shared arguments. Paths (output_dir, project_dir, geometry, path) are "
        "absolute. Area: sheet (a sheet code, for example N-34-130-D-d-2-4), bbox "
        "([min_x, min_y, max_x, max_y] in bbox_crs, which is required: there is no "
        "default) or geometry (a SHP or GPKG file; layer is its GPKG layer), exactly "
        "one; some commands also take teryt, ku or whole_country. country is pl, cz or "
        "auto: required with bbox and geometry, implied by a sheet code. Select data "
        "explicitly (product, resolution, vertical_crs, ...): nothing is guessed. A "
        'value per country is a string or {"pl": ..., "cz": ...}.'
    )
    updates = (
        "Updates. update omitted fetches what is missing, update=upgrade fetches newer "
        "content when the source signals it, update=force fetches again; a version is "
        "never overwritten. check_updates=true plans without fetching: its plan (the "
        "result of the envelope, kartograf-plan/1) runs later with update=upgrade and "
        "plan."
    )
    directories = ", ".join(Path(directory).as_posix() for directory in allow_dirs)
    if allow_writes:
        state = f"Writes are enabled inside {directories}; a path outside is forbidden."
    else:
        state = (
            "This server does not write: a command that writes only plans "
            "(check_updates is true; update, plan, workers and summary are "
            "forbidden), and "
            f"{_tool('project init')}, {_tool('project add')} and "
            f"{_tool('project remove')} are unavailable. Start kartograf-mcp with "
            "--allow-writes and --allow-dir DIR to download."
        )
        if directories:
            state += f" Paths must lie inside {directories}."
    results = (
        "Results. A result is the envelope kartograf-result/1: status (ok, partial, "
        "failed), result (the document of the command), items (one per unit; a failed "
        "one has code and reason) and notices. partial and failed are results "
        "(isError false): read items. An error (isError true) is kartograf-error/1 "
        "with code, message, hint and details; details.option names the argument to "
        "fix. forbidden is a path outside --allow-dir or a write on a server that "
        "only plans."
    )
    parts = [flow, shared, updates, state, results]
    if families is not None:
        parts.append(
            f"Exposed families (--tools): {', '.join(families)}; other tools are not "
            "listed."
        )
    return "\n".join(parts)


# The instructions of a server in the default state (read only, no directory, every
# tool): the text quoted in USAGE 9.6.
INSTRUCTIONS = build_instructions()


@dataclass
class _State:
    """What a connection of the server shares: the limit of the network calls."""

    limiter: anyio.CapacityLimiter


@dataclass(frozen=True)
class _Plan:
    """A tool call that passed the checks of its arguments.

    ``validate`` (``None``: nothing to check) is the check of the library that
    needs no network; ``run`` calls the library and gets the progress callback
    (``None`` when the function reports none).
    """

    validate: Callable[[], None] | None
    run: Callable[[Callable[[DownloadProgress], None] | None], CommandResult[Any]]
    progress: bool


def default_cache_file() -> Path:
    """Return the metadata cache of the server.

    The cache of the CLI and the library, ``<cache_dir>/kartograf/metadata.db``
    (``cache_dir``: ``KARTOGRAF_CACHE_DIR``, ``NOGAT_CACHE_DIR``, ``nogat.toml``,
    else the user cache directory of ``nogat``; DEV-18.2). The path does not depend
    on the working directory the client chose for the server.
    """
    return default_cache_path()


def _open_cache(path: Path) -> MetadataCache:
    """Return the cache at ``path``.

    Its directory and file are made by the first write of the library. A directory
    that cannot be made (a read-only home, a file in the way) does not stop the server:
    like the CLI and the library with a cache they cannot open, it warns and works
    without the cache.
    """
    return MetadataCache(path)


def _json_type(value: object) -> str:
    """Return the name of the JSON type of a Python value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list | tuple):
        return "array"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


# The order in which a violation is reported when the arguments break several rules.
_RANK = {"required": 0, "additionalProperties": 1, "dependentRequired": 2}


def _first_violation(validator: Any, arguments: Mapping[str, Any]) -> Any | None:
    """Return the violation of the schema to report.

    A missing argument, then an unknown one, then a missing companion, then a wrong
    value (in the order of the arguments); ``None`` when the arguments are valid.
    """
    errors = list(validator.iter_errors(arguments))
    if not errors:
        return None

    def rank(error: Any) -> tuple[int, list[str]]:
        return _RANK.get(error.validator, 3), [str(p) for p in error.absolute_path]

    return min(errors, key=rank)


def _violation(error: Any) -> ValidationError:
    """Return the ``ValidationError`` of a violation of the input schema.

    ``option`` is the argument; the message says what is wrong and, for a value
    outside an ``enum``, ``allowed`` lists the values (``error_report`` adds the hint
    with an example from the catalog).
    """
    path = list(error.absolute_path)
    option = str(path[0]) if path else None
    where = option
    for part in path[1:]:
        where = f"{where}[{part}]" if isinstance(part, int) else f"{where}.{part}"
    rule, expected = error.validator, error.validator_value
    if rule == "required" and not path:
        option = next(name for name in expected if name not in error.instance)
        return ValidationError(f"missing required argument {option}", option=option)
    if rule == "additionalProperties" and not path:
        known = list(error.schema.get("properties", {}))
        option = next(name for name in error.instance if name not in known)
        return ValidationError(
            f"unknown argument {option}",
            option=option,
            hint=f"Arguments of this tool: {', '.join(known)}.",
        )
    if rule == "dependentRequired" and not path:
        key, option = next(
            (key, dependency)
            for key, dependencies in expected.items()
            if key in error.instance
            for dependency in dependencies
            if dependency not in error.instance
        )
        return ValidationError(
            f"argument {option} is required together with {key}",
            option=option,
            options=(key, option),
        )
    prefix = f"argument {where}:"
    if rule == "enum":
        return ValidationError(
            f"{prefix} {error.instance!r} is not an allowed value",
            option=option,
            allowed=[str(value) for value in expected],
        )
    if rule == "type":
        names = [expected] if isinstance(expected, str) else expected
        message = (
            f"{prefix} expected {' or '.join(names)}, got {_json_type(error.instance)}"
        )
    elif rule == "minimum":
        message = f"{prefix} {error.instance} is below the minimum {expected}"
    elif rule in ("minItems", "maxItems"):
        message = (
            f"{prefix} expected an array of exactly {expected} items, "
            f"got {len(error.instance)}"
        )
    elif rule == "anyOf":
        message = (
            f"{prefix} the value is neither a string nor an object with the keys "
            "pl and cz"
        )
    elif rule == "const":
        message = f"{prefix} must be {expected!r}"
    else:
        message = f"{prefix} {error.message}"
    return ValidationError(message, option=option)


def _progress_text(event: DownloadProgress) -> str:
    """Return the text of a progress event.

    The form is ``<status> <unit> (<current>/<total>). <message>`` (ASCII; the
    empty parts are left out).
    """
    text = " ".join(part for part in (event.status, event.sheet) if part)
    if event.total:
        text += f" ({event.current}/{event.total})"
    if event.message:
        text += f": {event.message}"
    return text.strip().encode("ascii", "backslashreplace").decode("ascii")


class _Progress:
    """The progress callback of a library call for the client.

    The library calls it from worker threads (``workers > 1``); each event is
    sent as ``notifications/progress`` with the number of the event (1, 2, 3...,
    strictly increasing: the count and the send are under one lock) and a text.
    The total is unknown (``None``): the number of units is not always known and
    the protocol does not allow an invented one. A client that went away or
    cancelled the call stops the notifications, never the library call.
    """

    def __init__(self, portal: BlockingPortal, session: ServerSession) -> None:
        self._portal = portal
        self._session = session
        self._lock = threading.Lock()
        self._count = 0
        self._lost = False

    def __call__(self, event: DownloadProgress) -> None:
        text = _progress_text(event)
        with self._lock:
            if self._lost:
                return
            self._count += 1
            send = self._session.report_progress
            try:
                self._portal.call(send, self._count, None, text)
            except Exception:  # the client is gone: the download goes on
                self._lost = True


def _takes(function: str, parameter: str) -> bool:
    """Check whether a library function (a name of ``kartograf``) has the parameter."""
    return parameter in inspect.signature(getattr(kartograf, function)).parameters


def _given(value: object) -> bool:
    """Say whether an argument is given: ``None`` and a false flag are not."""
    return value is not None and value is not False


def _writes_disabled(spec: ToolSpec, option: str) -> ForbiddenError:
    return ForbiddenError(
        f"{spec.name} only plans on this server: {option} is not available",
        option=option,
        hint=_WRITES_HINT,
    )


class _Toolbox:
    """The tools of a server.

    The check of the arguments of a call and the call of the library (no SDK in here:
    the glue is ``create_server``).
    """

    def __init__(
        self,
        specs: Sequence[ToolSpec],
        hidden: Mapping[str, str],
        *,
        cache: MetadataCache | bool,
        allow_dirs: Sequence[Path],
        validator_class: Any,
    ) -> None:
        self.specs = {spec.name: spec for spec in specs}
        self.hidden = dict(hidden)
        self._validators = {
            spec.name: validator_class(spec.input_schema) for spec in specs
        }
        self._cache = cache
        self._allow_dirs = tuple(allow_dirs)

    def refusal(self, name: str) -> ForbiddenError | None:
        """Return the error of a tool that exists but is not offered (or ``None``)."""
        command = self.hidden.get(name)
        if command is None:
            return None
        return ForbiddenError(
            f"{name} writes ({command}) and this server does not write",
            hint=_WRITES_HINT,
        )

    def plan(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> _Plan:
        """Check the arguments of a call and prepare its library call.

        The order of the checks: the writes a plan-only tool refuses, the input
        schema, the paths (absolute; ``--allow-dir``), the options a plan has none of;
        the checks of the library come in ``_execute``.

        Raises
        ------
        ForbiddenError
            A plan-only tool was asked to run, or a path lies outside ``--allow-dir``.
        ValidationError
            An argument breaks the schema or the rule of paths, or ``check_updates``
            is combined with an option of a run.
        """
        self._refuse_writes(spec, arguments)
        self._check_schema(self._validators[spec.name], arguments)
        self._check_paths(spec.paths, arguments)
        check = spec.plan_only or arguments.get(CHECK_OPTION) is True
        if check:
            self._no_run_options(spec, arguments)
        if spec.task_options:
            return self._data_tool(spec, arguments, check=check)
        if spec.command == "project add":
            # the paths among the task options follow the rules of a data tool
            self._check_paths(task_paths(arguments["command"]), arguments["options"])
        return self._function_tool(spec, arguments, check=check)

    @staticmethod
    def _refuse_writes(spec: ToolSpec, arguments: Mapping[str, Any]) -> None:
        if not spec.plan_only:
            return
        for name in arguments:
            if name in spec.refused and _given(arguments[name]):
                raise _writes_disabled(spec, name)
        if arguments.get(CHECK_OPTION) is False:
            raise _writes_disabled(spec, CHECK_OPTION)

    @staticmethod
    def _check_schema(validator: Any, arguments: Mapping[str, Any]) -> None:
        error = _first_violation(validator, arguments)
        if error is not None:
            raise _violation(error)

    def _check_paths(
        self, paths: Mapping[str, PathRole], values: Mapping[str, Any]
    ) -> None:
        """Check that every path is absolute and inside an allowed directory.

        With ``--allow-dir``, inside one of the directories (after
        ``Path.resolve()``); every role is confined: the server reads and writes only
        there.
        """
        for option, value in values.items():
            if option not in paths or not isinstance(value, str):
                continue  # a value of a wrong form is the library's to report
            path = Path(value)
            if not path.is_absolute():
                raise ValidationError(
                    f"argument {option}: the path must be absolute, got {value!r}",
                    option=option,
                    hint=_PATH_HINT,
                )
            resolved = path.resolve()
            if self._allow_dirs and not any(
                resolved.is_relative_to(directory) for directory in self._allow_dirs
            ):
                directories = [directory.as_posix() for directory in self._allow_dirs]
                raise ForbiddenError(
                    f"argument {option}: the path {value!r} lies outside the "
                    "directories this server allows (--allow-dir)",
                    option=option,
                    path=resolved,
                    allowed=directories,
                    hint=f"Allowed directories: {', '.join(directories)}.",
                )

    @staticmethod
    def _no_run_options(spec: ToolSpec, arguments: Mapping[str, Any]) -> None:
        """Refuse an option of a run next to ``check_updates``: it fetches nothing."""
        for name in RUN_OPTIONS:
            if name in arguments and _given(arguments[name]):
                raise ValidationError(
                    f"check_updates plans without fetching: {name} belongs to a run",
                    option=name,
                    options=(CHECK_OPTION, name),
                    hint="Drop check_updates to run, or drop update, plan, workers "
                    "and summary to plan.",
                )

    def _data_tool(
        self, spec: ToolSpec, arguments: Mapping[str, Any], *, check: bool
    ) -> _Plan:
        command = spec.command
        options = {k: v for k, v in arguments.items() if k in spec.task_options}
        run_kinds = {k: v for k, v in spec.kinds.items() if k not in spec.task_options}
        run = convert_arguments(
            run_kinds, {k: v for k, v in arguments.items() if k in run_kinds}
        )
        output_dir = run["output_dir"]

        def validate() -> None:
            validate_command(command, options, output_dir=output_dir)

        if check:

            def plan_call(
                _on_progress: Callable[[DownloadProgress], None] | None,
            ) -> CommandResult[Any]:
                return check_command(
                    command, options, output_dir=output_dir, cache=self._cache
                )

            return _Plan(validate, plan_call, False)

        def call(
            on_progress: Callable[[DownloadProgress], None] | None,
        ) -> CommandResult[Any]:
            return run_command(
                command,
                options,
                output_dir=output_dir,
                update=run.get("update"),
                plan=run.get("plan"),
                workers=run.get("workers"),
                summary=run.get("summary", False),
                cache=self._cache,
                on_progress=on_progress,
            )

        return _Plan(validate, call, _takes(spec.function, "on_progress"))

    def _function_tool(
        self, spec: ToolSpec, arguments: Mapping[str, Any], *, check: bool
    ) -> _Plan:
        name = spec.check_function if check else spec.function
        assert name is not None  # a command with the option has the twin
        function = getattr(kartograf, name)
        converted = convert_arguments(
            spec.kinds, {k: v for k, v in arguments.items() if k != CHECK_OPTION}
        )
        converted.update(spec.fixed)
        if _takes(name, "cache"):
            converted["cache"] = self._cache
        takes_progress = not check and _takes(name, "on_progress")

        def call(
            on_progress: Callable[[DownloadProgress], None] | None,
        ) -> CommandResult[Any]:
            extra = {"on_progress": on_progress} if takes_progress else {}
            return wrap(spec.command, function(**converted, **extra), check=check)

        return _Plan(None, call, takes_progress)


def _wire_tool(spec: ToolSpec) -> types.Tool:
    """Return the protocol form of a tool (``tools/list``)."""
    import mcp_types as types

    hints = spec.annotations
    return types.Tool(
        name=spec.name,
        title=spec.title,
        description=spec.description,
        input_schema=copy.deepcopy(spec.input_schema),
        output_schema=copy.deepcopy(spec.output_schema),
        annotations=types.ToolAnnotations(
            title=hints.title,
            read_only_hint=hints.read_only_hint,
            destructive_hint=hints.destructive_hint,
            idempotent_hint=hints.idempotent_hint,
            open_world_hint=hints.open_world_hint,
        ),
        _meta={ALWAYS_LOAD_KEY: True} if spec.always_load else None,
    )


def _result(document: CommandResult[Any] | ErrorReport) -> types.CallToolResult:
    """Return the result of a tool.

    The document as compact JSON text and as structured content. Only an error
    document is an error (AGI-5.7): the outcomes ``partial`` and ``failed`` of a
    command are results, as the CLI prints their envelope.
    """
    import mcp_types as types

    return types.CallToolResult(
        content=[types.TextContent(text=document.to_json(indent=None))],
        structured_content=document.to_dict(),
        is_error=isinstance(document, ErrorReport),
    )


async def _execute(
    ctx: ServerRequestContext[_State], spec: ToolSpec, plan: _Plan
) -> types.CallToolResult:
    """Run a planned call in worker threads (AGI-5.11) and encode its document.

    The document is encoded there, so that a large document does not stop the
    other calls.

    The check of the library (no network) comes first and does not wait for a
    free slot; a call that uses the network takes one of ``MAX_NETWORK_CALLS``.
    A call the client cancelled is abandoned, not stopped: the thread finishes
    (versions are committed atomically), its result is dropped, and the process
    ends after the last such thread.
    """
    import anyio.to_thread
    from anyio.from_thread import BlockingPortal

    def work(
        progress: Callable[[DownloadProgress], None] | None,
    ) -> types.CallToolResult:
        return _result(plan.run(progress))

    if plan.validate is not None:
        await anyio.to_thread.run_sync(plan.validate, abandon_on_cancel=True)
    # open_world_hint = the tool uses the network
    limiter = ctx.lifespan_context.limiter if spec.annotations.open_world_hint else None
    if not plan.progress:
        return await anyio.to_thread.run_sync(
            functools.partial(work, None), limiter=limiter, abandon_on_cancel=True
        )
    async with BlockingPortal() as portal:
        progress = _Progress(portal, ctx.session)
        result = await anyio.to_thread.run_sync(
            functools.partial(work, progress), limiter=limiter, abandon_on_cancel=True
        )
    return result


def _unknown_tool(name: str, names: Iterable[str]) -> str:
    close = difflib.get_close_matches(name, list(names), n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    return f"Unknown tool {name!r}.{hint}"


def create_server(
    *,
    families: Sequence[str] | None = None,
    cache: MetadataCache | Path | bool | None = None,
    allow_dirs: Sequence[str | Path] = (),
    allow_writes: bool = False,
) -> Server[_State]:
    """Build the MCP server with the tools of the given families (all by default).

    Parameters
    ----------
    families : sequence of str, optional
        ``discovery``, ``availability``, ``data``, ``project``, ``store`` or
        ``core`` (``kartograf.catalog.tools.FAMILIES``).
    cache : MetadataCache, Path or False, optional
        The metadata cache of the library calls: an open cache, the file of one
        (the server closes the cache it opened), ``False`` for none; by default
        ``default_cache_file()``.
    allow_dirs : sequence of path, optional
        Absolute directories (``~`` allowed); when given, every path of a tool
        call must lie in one of them (after ``Path.resolve()``), else the call is
        ``forbidden``.
    allow_writes : bool, optional
        Let the tools that write write (inside ``allow_dirs``, which they need).
        By default a command that writes and has a check only plans and the
        others that write answer ``forbidden``.

    Raises
    ------
    ConfigError
        ``nogat.toml`` or a setting cannot be used (``kartograf.config.check_config``);
        checked first, before the SDK is imported.
    ValidationError
        An unknown or empty family, ``allow_writes`` without ``allow_dirs``,
        ``cache=True`` or a relative directory in ``allow_dirs``
        (``option`` names the argument).
    MissingDependencyError
        The ``mcp`` package is not installed (hint: ``uv add "kartograf[mcp]"``).
    """
    check_config()  # unusable settings stop the server instead of being ignored
    chosen = None if families is None else check_families(families)
    directories = [_allowed_directory(directory) for directory in allow_dirs]
    if allow_writes and not directories:
        raise ValidationError(
            "allow_writes needs allow_dirs: the server writes only inside the "
            "directories of --allow-dir",
            option="allow_writes",
            options=("allow_writes", "allow_dirs"),
            hint="Start kartograf-mcp with --allow-writes and --allow-dir DIR.",
        )
    if cache is True:
        raise ValidationError(
            "cache=True: give a MetadataCache, the file of a cache or False",
            option="cache",
        )
    try:
        import anyio
        import mcp_types as types
        from jsonschema import Draft202012Validator
        from mcp.server import Server
        from mcp.shared.exceptions import MCPError
    except ImportError as error:
        raise MissingDependencyError(
            f"the MCP server needs the mcp package ({SDK_REQUIREMENT})", extra="mcp"
        ) from error
    specs = tool_specs(chosen, allow_writes=allow_writes)
    hidden = hidden_tools(chosen, allow_writes=allow_writes)
    owned: MetadataCache | None = None
    library_cache: MetadataCache | bool
    if cache is None or isinstance(cache, Path):
        owned = _open_cache(default_cache_file() if cache is None else cache)
        library_cache = owned
    else:
        library_cache = cache
    toolbox = _Toolbox(
        specs,
        hidden,
        cache=library_cache,
        allow_dirs=directories,
        validator_class=Draft202012Validator,
    )
    tools = [_wire_tool(spec) for spec in specs]

    @asynccontextmanager
    async def lifespan(_server: Server[_State]) -> AsyncGenerator[_State, None]:
        try:
            yield _State(limiter=anyio.CapacityLimiter(MAX_NETWORK_CALLS))
        finally:
            if owned is not None:
                owned.close()

    async def list_tools(
        _ctx: ServerRequestContext[_State], _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def call_tool(
        ctx: ServerRequestContext[_State], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        spec = toolbox.specs.get(params.name)
        arguments = params.arguments or {}
        if spec is None:
            refusal = toolbox.refusal(params.name)
            if refusal is None:
                raise MCPError(
                    types.INVALID_PARAMS, _unknown_tool(params.name, toolbox.specs)
                )
            return _result(error_report(refusal, command=toolbox.hidden[params.name]))
        try:
            plan = toolbox.plan(spec, arguments)
            return await _execute(ctx, spec, plan)
        except Exception as exc:
            if not isinstance(exc, KartografError | OSError):
                logger.exception("Tool %s: program error", spec.name)
            return _result(error_report(exc, command=spec.command, given=arguments))

    return Server(
        "kartograf",
        version=kartograf.__version__,
        title="Kartograf",
        instructions=build_instructions(
            allow_writes=allow_writes, allow_dirs=directories, families=chosen
        ),
        lifespan=lifespan,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _allowed_directory(directory: str | Path) -> Path:
    """Return a directory of ``--allow-dir`` as an absolute path (``~`` expanded).

    A relative one would stand for the working directory the client chose for the
    server, which the paths of the calls (always absolute) do not share.

    Raises
    ------
    ValidationError
        The directory is not absolute (``option="allow_dirs"``).
    """
    path = Path(directory).expanduser()
    if not path.is_absolute():
        raise ValidationError(
            f"--allow-dir needs an absolute path, got {str(directory)!r} (a relative "
            "one would depend on the working directory of the server)",
            option="allow_dirs",
            hint="Give an absolute directory, for example --allow-dir /home/ola/dane.",
        )
    return path.resolve()


def _argument(convert: Callable[[str], Any]) -> Callable[[str], Any]:
    """Return ``convert`` as an argparse type that reports a ``ValidationError``."""

    @functools.wraps(convert)
    def typed(text: str) -> Any:
        try:
            return convert(text)
        except ValidationError as error:
            raise argparse.ArgumentTypeError(str(error)) from error

    return typed


class _ServerParser(argparse.ArgumentParser):
    """The parser of ``kartograf-mcp``: a usage error is a ``UsageError``.

    ``main`` reports it like every other failure to start, with the error document as
    the last line of stderr (AGI-3.3).
    """

    def error(self, message: str) -> NoReturn:
        """Raise a ``UsageError`` instead of printing the usage and exiting."""
        raise UsageError(message, hint=f"Run {self.prog} --help for the options.")


def _parser() -> argparse.ArgumentParser:
    parser = _ServerParser(
        prog="kartograf-mcp",
        description="Serwer MCP (stdio): narzedzia Kartografa dla agentow AI - "
        "katalog komend, godla, dostepnosc, pobieranie i sprawdzanie aktualnosci "
        "danych oraz odczyt magazynu. Domyslnie serwer nie zapisuje.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--tools",
        type=_argument(parse_families),
        metavar="RODZINY",
        help="rodziny narzedzi po przecinku: " + ", ".join(FAMILIES) + " (domyslnie "
        "wszystkie; core to najwazniejsze zadania, dla klientow z limitem narzedzi)",
    )
    parser.add_argument(
        "--allow-dir",
        action="append",
        default=[],
        type=_argument(_allowed_directory),
        metavar="KATALOG",
        help="katalog bezwzgledny (albo z ~), w ktorym musza lezec sciezki narzedzi "
        "(powtarzalna; sciezka poza nim to forbidden; bez tej flagi: dowolna sciezka "
        "bezwzgledna do odczytu)",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="narzedzia, ktore zapisuja, zapisuja (tylko w katalogach --allow-dir, "
        "ktore jest wtedy wymagane); bez tej flagi planuja (check_updates)",
    )
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        help="jezyk tekstu dla czlowieka (pl albo en); serwer odpowiada zawsze po "
        "angielsku, wartosc jest tylko sprawdzana i podana w linii startowej",
    )
    caching = parser.add_mutually_exclusive_group()
    caching.add_argument(
        "--cache-file",
        type=Path,
        metavar="PLIK",
        help="plik cache metadanych (domyslnie <katalog cache uzytkownika>/"
        "kartograf/metadata.db)",
    )
    caching.add_argument("--no-cache", action="store_true", help="bez cache metadanych")
    parser.add_argument(
        "--version", action="version", version=f"kartograf-mcp {kartograf.__version__}"
    )
    return parser


async def _serve(server: Server[_State]) -> None:
    """Serve one connection on stdin and stdout.

    Stray output of the library on stdout goes to stderr (the SDK claims the descriptors
    while it serves).
    """
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def _fail(error: KartografError) -> int:
    """Report a failure to start and return its exit code.

    An ``Error:`` line, then the ``kartograf-error/1`` document as the last line of
    stderr (AGI-3.3); stdout belongs to the protocol and stays empty.
    """
    report = error_report(error)
    print(f"Error: {report.message}", file=sys.stderr)
    print(error_line(report), file=sys.stderr, flush=True)
    return report.exit_code


def _start_line(args: argparse.Namespace) -> str:
    """Return the line that says on stderr how the server started.

    The state the options chose, ``lang`` included: the language is validated and
    reported and changes nothing, as everything the server says is English.
    """
    lang = args.lang or str(resolve("lang").value)
    return (
        f"kartograf-mcp {kartograf.__version__}: stdio, "
        f"writes {'on' if args.allow_writes else 'off'}, "
        f"allow-dir {', '.join(d.as_posix() for d in args.allow_dir) or 'none'}, "
        f"tools {','.join(args.tools) if args.tools else 'all'}, lang {lang}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """``kartograf-mcp``: serve the tools over stdio until the client closes it.

    Returns
    -------
    int
        0 after a normal end; 2 for a wrong argument or setting (an unknown family,
        a relative ``--allow-dir``, ``--allow-writes`` without ``--allow-dir``, an
        unusable ``nogat.toml``); 6 when the ``mcp`` package is missing; 130 after
        Ctrl-C. A failure to start writes the ``kartograf-error/1`` document as the
        last line of stderr; ``--help`` and ``--version`` end the process
        (``SystemExit``) as argparse does.
    """
    try:
        args = _parser().parse_args(argv)
        cache: Path | bool | None = False if args.no_cache else args.cache_file
        server = create_server(
            families=args.tools,
            cache=cache,
            allow_dirs=args.allow_dir,
            allow_writes=args.allow_writes,
        )
    except KartografError as error:
        return _fail(error)
    print(_start_line(args), file=sys.stderr, flush=True)
    import anyio

    try:
        anyio.run(_serve, server)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
