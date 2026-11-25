"""
The Starlette application of ``kartograf server`` (ADR-063 decisions 2, 7 and 8).

``create_app`` serves ``GET /api/v1/server`` (``nogat-server/1``), ``GET
/api/v1/openapi.json`` and the route of every command whose catalog entry has a
``rest`` (``kartograf.server.routes``): a ``GET`` reads its options from the query,
a ``POST`` from a JSON object (at most ``BODY_MAX_BYTES``), and a data command takes
``?check=true``. The answer is the envelope ``kartograf-result/1`` as ``--json``
prints it, ``Content-Language: en`` (AGI-9.2); an error is
``application/problem+json`` in the language of ``Accept-Language``
(``kartograf.server.problems``): ``404 not_found`` for a path that is no route,
``405 method_not_allowed`` with ``Allow`` for another method, ``403 forbidden``
(``not_served``) for a command of the user's own store, cache or settings, ``500
internal_error`` with a fixed text for a failure of the server, whose cause goes to
the application log.

Every request under ``/api/`` is a request of its client (the address of the
connection, or of ``X-Forwarded-For`` from a trusted proxy, AGI-6.9): it counts its
visitor in the daily totals and the request limit (``429 rate_limited`` with
``Retry-After``). A plan, and a script that plans, also counts by the plan limit; a
plan answered and a script generated count as ``analyses_run``. The library calls
run in worker threads, at most ``NETWORK_CALLS`` of them with the network at once.
With a ``ServerLog`` the outermost middleware is Nogat's ``AccessLog`` (DEV-12.8).
The daily totals are written every ``FLUSH_S`` and at shutdown, when the metadata
cache is closed too.
"""

import contextlib
import functools
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, Final

import anyio
import anyio.to_thread
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from kartograf._version import build_version
from kartograf.catalog.spec import CHECK_OPTION
from kartograf.exceptions import (
    ForbiddenError,
    KartografError,
    MethodNotAllowedError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from kartograf.messages import message, reason
from kartograf.server.calls import NETWORK_CALLS, ServerState, prepare
from kartograf.server.nogat_logging import AccessLog, ServerLog
from kartograf.server.openapi import (
    OPENAPI_PATH,
    SERVER_PATH,
    openapi_document,
    server_document,
)
from kartograf.server.problems import (
    PROBLEM_MEDIA_TYPE,
    Location,
    language_of,
    problem,
)
from kartograf.server.routes import (
    LocalCommand,
    ServedCommand,
    local_commands,
    query_options,
    served_commands,
)
from kartograf.server.settings import ServerSettings
from kartograf.server.stats import FLUSH_S, DailyStats

__all__ = ["BODY_MAX_BYTES", "create_app"]

BODY_MAX_BYTES: Final = 4 * 1024 * 1024
"""The largest body of a request (a saved plan of ``script generate`` among them)."""
_COUNTED_PREFIX: Final = "/api/"
_JSON: Final = "application/json"
_ALL_METHODS: Final = ("GET", "POST", "PUT", "PATCH", "DELETE")
_TRUE: Final = frozenset({"true", "1"})
_FALSE: Final = frozenset({"false", "0"})

Endpoint = Callable[[Request], Awaitable[Response]]


def _client(request: Request, state: ServerState) -> str:
    """Return the address of the client of a request (AGI-6.9)."""
    peer = request.client.host if request.client is not None else None
    forwarded = ", ".join(request.headers.getlist("x-forwarded-for")) or None
    return state.client(peer, forwarded)


def _problem_response(
    error: BaseException,
    request: Request,
    *,
    command: str | None = None,
    given: Mapping[str, object] | None = None,
    location: Location = "body",
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Return the ``application/problem+json`` answer of an error.

    Its texts follow ``Accept-Language``; ``Content-Language`` and ``Vary`` say so
    (AGI-6.4). ``rate_limited`` carries ``Retry-After``.
    """
    lang = language_of(request.headers.get("accept-language"))
    body = problem(
        error,
        instance=request.url.path,
        lang=lang,
        command=command,
        given=given,
        location=location,
    )
    sent = {"Content-Language": lang, "Vary": "Accept-Language", **(headers or {})}
    if isinstance(error, RateLimitedError):
        sent["Retry-After"] = str(error.retry_after_s)
    status = body["status"]
    assert isinstance(status, int)  # problem() writes the registry's status
    return JSONResponse(
        body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=sent
    )


def _document_response(body: bytes) -> Response:
    """Return the answer of a JSON document whose texts are English (AGI-9.2)."""
    return Response(body, media_type=_JSON, headers={"Content-Language": "en"})


def _check_of(request: Request, served: ServedCommand) -> bool:
    """Return ``check`` of the query of a ``POST``, its only parameter.

    Raises
    ------
    ValidationError
        Another parameter (the options of a ``POST`` are its body), ``check`` of a
        command that plans nothing, or a ``check`` that is no switch.
    """
    check = False
    for name, value in request.query_params.multi_items():
        if name != CHECK_OPTION or not served.plans:
            raise ValidationError(
                message("server.query_in_post", name=name, route=request.url.path),
                option=name,
            )
        word = value.strip().lower()
        if word not in _TRUE | _FALSE:
            raise ValidationError(
                message("server.check_not_switch", value=value), option=CHECK_OPTION
            )
        check = word in _TRUE
    return check


async def _body(request: Request, served: ServedCommand) -> dict[str, object]:
    """Return the options of a ``POST``: its body, a JSON object (empty: none).

    Raises
    ------
    ValidationError
        A body larger than ``BODY_MAX_BYTES`` (``body_too_large``), no JSON, or JSON
        that is no object.
    """
    declared = request.headers.get("content-length", "")
    too_large = ValidationError(
        message("server.body_too_large", limit=BODY_MAX_BYTES), reason="body_too_large"
    )
    if declared.isdigit() and int(declared) > BODY_MAX_BYTES:
        raise too_large
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > BODY_MAX_BYTES:
            raise too_large
    if not data.strip():
        return {}
    try:
        value = json.loads(bytes(data))
    except ValueError as error:
        raise ValidationError(
            message("server.body_not_json", error=reason(error))
        ) from error
    if not isinstance(value, dict):
        raise ValidationError(
            message(
                "server.body_not_object",
                route=request.url.path,
                command=served.command.id,
            )
        )
    return value


def _command_endpoint(
    served: ServedCommand, state: ServerState, network: anyio.CapacityLimiter
) -> Endpoint:
    """Return the endpoint of the route of a served command."""
    location: Location = "query" if served.rest.method == "GET" else "body"

    async def endpoint(request: Request) -> Response:
        options: dict[str, object] = {}
        # the query of a POST is read before its body: a mistake in it is the query's
        where: Location = "query"
        try:
            if location == "query":
                check = False
                options = query_options(served, request.query_params.multi_items())
            else:
                check = _check_of(request, served)
                where = location
                options = await _body(request, served)
            call = await anyio.to_thread.run_sync(
                functools.partial(prepare, served, options, check=check, state=state)
            )
            if call.plans:
                state.hit_plan(_client(request, state))

            def answer() -> bytes:
                return call.run().to_json(indent=None).encode("utf-8")

            body = await anyio.to_thread.run_sync(
                answer, limiter=network if call.network else None
            )
        except KartografError as error:
            return _problem_response(
                error,
                request,
                command=served.command.id,
                given=options,
                location=where,
            )
        if call.counted:
            state.count_analysis()
        return _document_response(body)

    return endpoint


def _not_served_endpoint(local: LocalCommand) -> Endpoint:
    """Return the endpoint of a command the server does not serve (``forbidden``)."""
    command = local.command.id

    async def endpoint(request: Request) -> Response:
        error = ForbiddenError(
            message("server.not_served", command=command),
            hint=message("server.not_served_hint", command=command),
            reason="not_served",
        )
        return _problem_response(error, request, command=command)

    return endpoint


async def _http_error(request: Request, error: Exception) -> Response:
    """Answer an error of the routing: no route (404) or another method (405)."""
    assert isinstance(error, HTTPException)  # the handler of HTTPException
    path = request.url.path
    if error.status_code == 405:
        allow = (error.headers or {}).get("Allow", "")
        allowed = [method.strip() for method in allow.split(",") if method.strip()]
        refused = MethodNotAllowedError(
            message(
                "server.method_not_allowed",
                route=path,
                allowed=", ".join(allowed),
                method=request.method,
            ),
            method=request.method,
            allowed=allowed,
        )
        return _problem_response(refused, request, headers={"Allow": allow})
    if error.status_code == 404:
        missing = NotFoundError(
            message("server.unknown_route", route=path),
            reason="unknown_route",
            route=path,
            hint=message("server.unknown_route_hint"),
        )
        return _problem_response(missing, request)
    return _problem_response(error, request)


async def _defect(request: Request, error: Exception) -> Response:
    """Answer a failure of the server: ``internal_error``, the cause in the log."""
    return _problem_response(error, request)


class _RequestLimit:
    """ASGI middleware: the request limit and the visitors of the API (DEV-15.9).

    Every HTTP request under ``/api/`` counts: its visitor in the daily totals and
    its client's request limit, over which it is answered ``429 rate_limited`` with
    ``Retry-After`` and goes no further.
    """

    def __init__(self, app: ASGIApp, state: ServerState) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Count a request of the API; refuse it over the limit."""
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith(
            _COUNTED_PREFIX
        ):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        address = _client(request, self.state)
        if self.state.stats is not None:
            self.state.stats.visit(address, request.headers.get("user-agent", ""))
        try:
            self.state.hit_request(address)
        except RateLimitedError as error:
            response = _problem_response(error, request)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


async def _flush_every(stats: DailyStats) -> None:
    """Write the daily totals every ``FLUSH_S`` (DEV-15.11)."""
    while True:
        await anyio.sleep(FLUSH_S)
        await anyio.to_thread.run_sync(stats.flush)


def _encoded(document: Mapping[str, Any]) -> bytes:
    """Return a document as compact UTF-8 JSON, the form of every answer."""
    return json.dumps(
        document, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def create_app(
    settings: ServerSettings | None = None,
    *,
    log: ServerLog | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Starlette:
    """Return the application of ``kartograf server``.

    Parameters
    ----------
    settings : ServerSettings, optional
        The limits and the files (default: the settings in force).
    log : ServerLog, optional
        Nogat's logs; with it the access log is the outermost middleware. ``serve``
        starts and stops it.
    clock : callable, optional
        The monotonic clock of the limits [s]; tests pass their own.

    Returns
    -------
    Starlette
        The application; ``app.state.server`` is its ``ServerState``.
    """
    settings = ServerSettings.from_config() if settings is None else settings
    state = ServerState(settings, stats=DailyStats(settings.stats_path), clock=clock)
    network = anyio.CapacityLimiter(NETWORK_CALLS)
    version = build_version()
    openapi = _encoded(openapi_document(version))
    server = _encoded(server_document(version))

    async def describe_server(request: Request) -> Response:
        return _document_response(server)

    async def describe_api(request: Request) -> Response:
        return _document_response(openapi)

    routes = [
        Route(SERVER_PATH, describe_server, methods=["GET"]),
        Route(OPENAPI_PATH, describe_api, methods=["GET"]),
        *(
            Route(
                served.rest.path,
                _command_endpoint(served, state, network),
                methods=[served.rest.method],
            )
            for served in served_commands()
        ),
        *(
            Route(local.path, _not_served_endpoint(local), methods=list(_ALL_METHODS))
            for local in local_commands()
        ),
    ]

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        try:
            async with anyio.create_task_group() as group:
                if state.stats is not None:
                    group.start_soon(_flush_every, state.stats)
                yield
                group.cancel_scope.cancel()
        finally:
            await anyio.to_thread.run_sync(state.close)

    handlers: dict[Any, Callable[[Request, Exception], Awaitable[Response]]] = {
        HTTPException: _http_error,
        Exception: _defect,
    }
    app = Starlette(
        routes=routes,
        middleware=[Middleware(_RequestLimit, state=state)],
        exception_handlers=handlers,
        lifespan=lifespan,
    )
    if log is not None:
        app.add_middleware(AccessLog, log=log)
    app.state.server = state
    return app
