"""The MCP server of Kartograf (spec 9).

The tools of ``kartograf.catalog.tools`` over stdio, for AI agents.

Every tool calls one function of the library and returns the envelope
``kartograf-result/1`` of its command (``to_dict()``, the same document as the CLI
``--json``; the domain document is its ``result``); a failure that stops the call is
the ``kartograf-error/1`` document with ``isError``. The module is the only one that
touches the MCP SDK, and it imports the SDK lazily:
``import kartograf.mcp_server`` works without the ``mcp`` package,
``create_server`` and ``main`` report its absence with the install command.

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
import functools
import inspect
import logging
import sys
import threading
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import kartograf
from kartograf.cache.defaults import default_cache_path
from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.tools import (
    CHECK_UPDATES,
    FAMILIES,
    ToolSpec,
    check_arguments_schema,
    tool_specs,
)
from kartograf.commands import check_command, run_command, validate_command
from kartograf.config import check_config
from kartograf.download.manager import DownloadProgress
from kartograf.envelope import CommandResult, wrap
from kartograf.error_report import ErrorReport, error_report
from kartograf.exceptions import ConfigError, KartografError, ValidationError

if TYPE_CHECKING:
    import anyio
    import mcp_types as types
    from anyio.from_thread import BlockingPortal
    from mcp.server import Server, ServerRequestContext
    from mcp.server.session import ServerSession

logger = logging.getLogger(__name__)

INSTALL_HINT = 'Brak pakietu mcp: pip install "kartograf[mcp]"'

# Text for the client (``instructions`` of the server): Polish, ASCII, four
# paragraphs, under 2000 characters (spec 9.9). The tools do not repeat what is
# the same in many of them (the area, the paths, the update mode, the result
# documents): it is said here once, and ``commands_schema`` has the rest. Claude
# Code loads this text at the start of every session and cuts it at 4096
# characters.
INSTRUCTIONS = "\n".join(
    (
        "Kartograf pobiera dane przestrzenne Polski i Czech (GUGiK, CUZK, "
        "Copernicus, ISRIC) do magazynu wersji w katalogu output_dir. Zacznij od "
        "commands_list (przeglad: grupy, produkty, komendy); parametry komendy: "
        'commands_schema(command="elevation download"). Jakie lata i uklady ma '
        "obszar: elevation_availability.",
        "Wspolne argumenty. Sciezki (output_dir, geometry, project_dir, path) "
        "podawaj bezwzglednie. Obszar: sheet (godlo arkusza, np. "
        "N-34-130-D-d-2-4), bbox ([min_x, min_y, max_x, max_y] w ukladzie "
        "bbox_crs, ktory jest wymagany: bez wartosci domyslnej) albo geometry "
        "(plik SHP albo GPKG, obwiednia obiektow; layer: warstwa GPKG) - "
        "dokladnie jeden; czesc komend ma tez teryt, ku albo whole_country. "
        "country: pl, cz albo auto (wymagany z bbox i geometry, z sheet wynika "
        "z godla).",
        "Dane wybierasz jawnie (product, resolution, vertical_crs...): Kartograf "
        "nie zgaduje; wartosc per kraj to tekst albo {pl, cz}. update: pominiety "
        "- tylko brakujace wersje, upgrade - nowsza tresc wg zrodla, force - od "
        "nowa; pobranie nie nadpisuje danych. check_updates (tool, arguments) "
        "sprawdza aktualnosc bez pobierania; jego plan (result koperty, "
        "kartograf-plan/1) wykonasz z update=upgrade i plan.",
        "Wynik to koperta kartograf-result/1: status (ok, partial albo failed), "
        "result (dokument komendy, narzedzia danych: kartograf-download/1 z "
        "polem ok), items (jednostki; nieudana ma code i reason) i notices. "
        "partial i failed to wyniki (is_error=false): sprawdz items. Blad "
        "(is_error=true) to kartograf-error/1 z code, hint i details.option.",
    )
)

# At most this many calls that use the network run at once (spec 9.7): several
# conversations do not flood GUGiK and CUZK with parallel jobs.
MAX_NETWORK_CALLS = 4

_PATH_HINT = "Podaj sciezke bezwzgledna, np. /home/ola/dane/kartograf"


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


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


_TYPE_TEXT = {
    "string": "tekst",
    "integer": "liczba calkowita",
    "number": "liczba",
    "boolean": "wartosc logiczna",
    "array": "tablica",
    "object": "obiekt",
    "null": "null",
}


def _type_text(value: object) -> str:
    """Return the Polish name of the JSON type of a Python value."""
    if value is None:
        return _TYPE_TEXT["null"]
    if isinstance(value, bool):
        return _TYPE_TEXT["boolean"]
    if isinstance(value, int):
        return _TYPE_TEXT["integer"]
    if isinstance(value, float):
        return _TYPE_TEXT["number"]
    if isinstance(value, str):
        return _TYPE_TEXT["string"]
    if isinstance(value, list | tuple):
        return _TYPE_TEXT["array"]
    if isinstance(value, Mapping):
        return _TYPE_TEXT["object"]
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
    """``ValidationError`` of a violation of the input schema.

    ``option`` is the argument, the message says what is wrong (Polish, ASCII).
    """
    path = list(error.absolute_path)
    option = str(path[0]) if path else None
    where = option
    for part in path[1:]:
        where = f"{where}[{part}]" if isinstance(part, int) else f"{where}.{part}"
    rule, expected = error.validator, error.validator_value
    if rule == "required" and not path:
        option = next(name for name in expected if name not in error.instance)
        return ValidationError(f"brak wymaganego argumentu {option}", option=option)
    if rule == "additionalProperties" and not path:
        known = list(error.schema.get("properties", {}))
        option = next(name for name in error.instance if name not in known)
        return ValidationError(
            f"nieznany argument {option}",
            option=option,
            hint=f"Dozwolone argumenty: {', '.join(known)}",
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
            f"argument {option} jest wymagany razem z {key}",
            option=option,
            options=(key, option),
        )
    prefix = f"argument {where}:"
    if rule == "enum":
        return ValidationError(
            _ascii(f"{prefix} wartosc {error.instance!r} spoza dozwolonych"),
            option=option,
            allowed=[str(value) for value in expected],
        )
    if rule == "type":
        names = [expected] if isinstance(expected, str) else expected
        wanted = " albo ".join(_TYPE_TEXT.get(name, name) for name in names)
        got = _type_text(error.instance)
        message = f"{prefix} oczekiwano {wanted}, podano {got}"
    elif rule == "minimum":
        message = f"{prefix} wartosc {error.instance} jest mniejsza niz {expected}"
    elif rule in ("minItems", "maxItems"):
        message = (
            f"{prefix} oczekiwano tablicy o dokladnie {expected} elementach, "
            f"podano {len(error.instance)}"
        )
    elif rule == "anyOf":
        message = (
            f"{prefix} wartosc nie pasuje do dozwolonej postaci "
            "(tekst albo obiekt z kluczami pl i cz)"
        )
    else:
        message = f"{prefix} {error.message}"
    return ValidationError(_ascii(message), option=option)


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
    return _ascii(text.strip())


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


class _Toolbox:
    """The tools of a server.

    The check of the arguments of a call and the call of the library (no SDK in here:
    the glue is ``create_server``).
    """

    def __init__(
        self,
        specs: Sequence[ToolSpec],
        *,
        cache: MetadataCache | bool,
        allow_dirs: Sequence[Path],
        validator_class: Any,
    ) -> None:
        self._validator_class = validator_class
        self.specs = {spec.name: spec for spec in specs}
        # nested checks (``check_updates``, ``project_add``) need every data tool
        self._data = {spec.name: spec for spec in tool_specs(("data",))}
        self._data_by_command = {spec.commands[0]: spec for spec in self._data.values()}
        self._validators = {
            spec.name: validator_class(spec.input_schema) for spec in specs
        }
        self._cache = cache
        self._allow_dirs = tuple(allow_dirs)

    def command_of(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> str | None:
        """Return the id of the catalog command a call is about.

        As far as the arguments tell (for the error document; never raises).
        """
        if len(spec.commands) == 1:
            return spec.commands[0]
        if spec.name == CHECK_UPDATES:
            target = self._data.get(str(arguments.get("tool")))
            return target.commands[0] if target else None
        group = arguments.get("group")
        for command in spec.commands:
            if isinstance(group, str) and command.startswith(f"{group} "):
                return command
        return None

    def plan(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> _Plan:
        """Check the arguments of a call and prepare its library call.

        The checks (spec 9.4) are the input schema, the rule of absolute paths and
        ``--allow-dir``.

        Raises
        ------
        ValidationError
            An argument breaks the schema or the rule of paths.
        """
        self._check_schema(self._validators[spec.name], arguments)
        self._check_paths(spec.kinds, arguments)
        if spec.name == CHECK_UPDATES:
            return self._check_updates(arguments)
        if spec.family == "data":
            return self._data_tool(spec, arguments)
        if spec.name == "project_add":
            # the paths among the task options follow the rules of a data tool
            target = self._data_by_command.get(arguments["command"])
            if target is not None:
                self._check_paths(target.kinds, arguments["options"])
        return self._function_tool(spec, arguments)

    @staticmethod
    def _check_schema(validator: Any, arguments: Mapping[str, Any]) -> None:
        error = _first_violation(validator, arguments)
        if error is not None:
            raise _violation(error)

    def _check_paths(self, kinds: Mapping[str, str], values: Mapping[str, Any]) -> None:
        """Check that every path is absolute and inside an allowed directory.

        With ``--allow-dir``, inside one of the directories (after
        ``Path.resolve()``).
        """
        for option, value in values.items():
            if kinds.get(option) != "path" or not isinstance(value, str):
                continue  # a value of a wrong form is the library's to report
            path = Path(value)
            if not path.is_absolute():
                raise ValidationError(
                    f"argument {option}: sciezka musi byc bezwzgledna, "
                    f"podano {value!r}",
                    option=option,
                    hint=_PATH_HINT,
                )
            allowed = self._allow_dirs
            if allowed and not any(path.resolve().is_relative_to(d) for d in allowed):
                raise ValidationError(
                    f"argument {option}: sciezka {value!r} lezy poza katalogami "
                    "dozwolonymi dla serwera (--allow-dir)",
                    option=option,
                    hint="Dozwolone katalogi: "
                    + ", ".join(directory.as_posix() for directory in allowed),
                )

    def _data_tool(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> _Plan:
        command = spec.commands[0]
        options = {k: v for k, v in arguments.items() if k in spec.task_options}
        run_kinds = {k: v for k, v in spec.kinds.items() if k not in spec.task_options}
        run = convert_arguments(
            run_kinds, {k: v for k, v in arguments.items() if k in run_kinds}
        )
        output_dir = run["output_dir"]

        def validate() -> None:
            validate_command(command, options, output_dir=output_dir)

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

        assert spec.function is not None
        takes_progress = _takes(spec.function, "on_progress")
        return _Plan(validate, call, takes_progress)

    def _check_updates(self, arguments: Mapping[str, Any]) -> _Plan:
        target = self._data[arguments["tool"]]
        inner = arguments["arguments"]
        validator = self._validator_class(check_arguments_schema(target.name))
        self._check_schema(validator, inner)
        kinds = {
            name: kind
            for name, kind in target.kinds.items()
            if name in target.task_options or name == "output_dir"
        }
        self._check_paths(kinds, inner)
        output_dir = Path(inner["output_dir"])
        options = {k: v for k, v in inner.items() if k != "output_dir"}
        data_command = target.commands[0]

        def validate() -> None:
            validate_command(data_command, options, output_dir=output_dir)

        def call(
            _on_progress: Callable[[DownloadProgress], None] | None,
        ) -> CommandResult[Any]:
            return check_command(
                data_command, options, output_dir=output_dir, cache=self._cache
            )

        return _Plan(validate, call, False)

    def _function_tool(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> _Plan:
        assert spec.function is not None
        function = getattr(kartograf, spec.function)
        converted = convert_arguments(spec.kinds, arguments)
        if _takes(spec.function, "cache"):
            converted["cache"] = self._cache
        takes_progress = _takes(spec.function, "on_progress")
        command = self.command_of(spec, arguments)
        assert command is not None  # the schema checked the group of a shared tool

        def call(
            on_progress: Callable[[DownloadProgress], None] | None,
        ) -> CommandResult[Any]:
            extra = {"on_progress": on_progress} if takes_progress else {}
            return wrap(command, function(**converted, **extra), check=spec.check)

        return _Plan(None, call, takes_progress)


def _takes(function: str, parameter: str) -> bool:
    """Check whether a library function (a name of ``kartograf``) has the parameter."""
    return parameter in inspect.signature(getattr(kartograf, function)).parameters


def _wire_tool(spec: ToolSpec) -> types.Tool:
    """Return the protocol form of a tool (``tools/list``)."""
    import mcp_types as types

    hints = spec.annotations
    return types.Tool(
        name=spec.name,
        description=spec.description,
        input_schema=copy.deepcopy(spec.input_schema),
        annotations=types.ToolAnnotations(
            read_only_hint=hints.read_only_hint,
            destructive_hint=hints.destructive_hint,
            idempotent_hint=hints.idempotent_hint,
            open_world_hint=hints.open_world_hint,
        ),
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
    """Run a planned call in worker threads (spec 9.7) and encode its document.

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


def create_server(
    *,
    families: Sequence[str] | None = None,
    cache: MetadataCache | Path | bool | None = None,
    allow_dirs: Sequence[str | Path] = (),
) -> Server[_State]:
    """Build the MCP server with the tools of the given families (all by default).

    Parameters
    ----------
    families : sequence of str, optional
        ``discovery``, ``availability``, ``data``, ``check``, ``project``,
        ``store`` (``kartograf.catalog.tools.FAMILIES``).
    cache : MetadataCache, Path or False, optional
        The metadata cache of the library calls: an open cache, the file of one
        (the server closes the cache it opened), ``False`` for none; by default
        ``default_cache_file()``.
    allow_dirs : sequence of path, optional
        Absolute directories (``~`` allowed); when given, every path of a tool
        call must lie in one of them (after ``Path.resolve()``).

    Raises
    ------
    ConfigError
        ``nogat.toml`` or a setting cannot be used (``kartograf.config.check_config``);
        checked first, before the SDK is imported.
    ImportError
        The ``mcp`` package is not installed.
    ValueError
        An unknown family, ``cache=True`` or a relative directory in ``allow_dirs``.
    """
    check_config()  # unusable settings stop the server instead of being ignored
    try:
        import anyio
        import mcp_types as types
        from jsonschema import Draft202012Validator
        from mcp.server import Server
        from mcp.shared.exceptions import MCPError
    except ImportError as error:
        raise ImportError(INSTALL_HINT) from error
    if cache is True:
        raise ValueError("cache=True: podaj MetadataCache, plik cache albo False")
    allowed = [_allowed_directory(directory) for directory in allow_dirs]
    specs = tool_specs(families)
    owned: MetadataCache | None = None
    library_cache: MetadataCache | bool
    if cache is None or isinstance(cache, Path):
        owned = _open_cache(default_cache_file() if cache is None else cache)
        library_cache = owned
    else:
        library_cache = cache
    toolbox = _Toolbox(
        specs,
        cache=library_cache,
        allow_dirs=allowed,
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
        if spec is None:
            raise MCPError(types.INVALID_PARAMS, f"Nieznane narzedzie: {params.name}")
        arguments = params.arguments or {}
        command = toolbox.command_of(spec, arguments)
        try:
            plan = toolbox.plan(spec, arguments)
            return await _execute(ctx, spec, plan)
        except Exception as exc:
            if not isinstance(exc, KartografError | OSError):
                logger.exception("Narzedzie %s: blad programu", spec.name)
            return _result(error_report(exc, command=command, given=arguments))

    return Server(
        "kartograf",
        version=kartograf.__version__,
        instructions=INSTRUCTIONS,
        lifespan=lifespan,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _families(text: str) -> list[str]:
    """Return the value of ``--tools``: families separated by commas."""
    names = [name.strip() for name in text.split(",")]
    unknown = [name for name in names if name not in FAMILIES]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"nieznana rodzina narzedzi: {', '.join(unknown) or '(pusta)'} "
            f"(dozwolone: {', '.join(FAMILIES)})"
        )
    return names


def _allowed_directory(directory: str | Path) -> Path:
    """Return a directory of ``--allow-dir`` as an absolute path (``~`` expanded).

    A relative one would stand for the working directory the client chose for the
    server, which the paths of the calls (always absolute) do not share.

    Raises
    ------
    ValueError
        The directory is not absolute.
    """
    path = Path(directory).expanduser()
    if not path.is_absolute():
        raise ValueError(
            f"--allow-dir wymaga sciezki bezwzglednej, jest {str(directory)!r} "
            "(wzgledna zalezalaby od katalogu roboczego serwera)"
        )
    return path.resolve()


def _allow_dir_argument(text: str) -> Path:
    """Return the type of ``--allow-dir``: a usage error for a relative directory."""
    try:
        return _allowed_directory(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kartograf-mcp",
        description="Serwer MCP (stdio): narzedzia Kartografa dla agentow AI - "
        "katalog, godla, dostepnosc, pobieranie i sprawdzanie aktualnosci danych "
        "oraz odczyt magazynu.",
    )
    parser.add_argument(
        "--tools",
        type=_families,
        metavar="RODZINY",
        help="rodziny narzedzi po przecinku: " + ", ".join(FAMILIES) + " (domyslnie "
        "wszystkie; klienty z limitem narzedzi: discovery,availability,data,check)",
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
        "--allow-dir",
        action="append",
        default=[],
        type=_allow_dir_argument,
        metavar="KATALOG",
        help="katalog bezwzgledny (albo z ~), w ktorym musza lezec sciezki narzedzi "
        "(powtarzalne; bez tej flagi: dowolna sciezka bezwzgledna)",
    )
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


def main(argv: Sequence[str] | None = None) -> int:
    """``kartograf-mcp``: serve the tools over stdio until the client closes it.

    Returns
    -------
    int
        0 after a normal end, 1 when the ``mcp`` package is missing (the install
        command is printed on stderr), 2 when the settings cannot be used (the
        ``kartograf-error/1`` document is the last line of stderr), 130 after
        Ctrl-C; a wrong argument exits with 2.
    """
    args = _parser().parse_args(argv)
    cache: Path | bool | None = False if args.no_cache else args.cache_file
    try:
        server = create_server(
            families=args.tools, cache=cache, allow_dirs=args.allow_dir
        )
    except ImportError as error:
        print(error, file=sys.stderr)
        return 1
    except ConfigError as error:
        print(error_report(error).to_json(indent=None), file=sys.stderr)
        return error.exit_code
    import anyio

    try:
        anyio.run(_serve, server)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
