"""
A request of ``kartograf server`` as a call of the library (ADR-063 decisions 4, 7, 8).

``ServerState`` is what a running server keeps: its settings, its metadata cache (the
index cache: an index answer younger than ``index_max_age`` is reused by a plan,
ADR-056), the limits per client and the daily totals. ``prepare`` turns the options
of a route into a ``Call`` without network and without writing; the refusals of the
server come first, each ``forbidden``: an option with a ``path_role`` (``path_option``;
the inline form of a plan is its document), the run of a data command or an option
of its run (``writes_disabled``), an input file of the line a call would plan
(``path_option``). The options are checked next (``validate_command``), so that a
mistake costs no plan. The call is then the plan of a data command
(``check_command(..., detached=True)``: a plain write into a directory that does not
exist, answered as the write into ``.``, so the plan tells nothing of the server's
disk), or the function of a read-only command (``run_command``), ``script generate``
among them, which plans a direct script of a line. A plan, and a script that plans,
is counted by the plan limit before it runs (the caller's ``ServerState.hit_plan``)
and refused after it when it has more than ``plan_max_units`` units
(``validation_error``, ``too_many_units``).
"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.spec import CHECK_OPTION, RUN_OPTIONS
from kartograf.commands import (
    CommandCall,
    check_command,
    parse_command,
    run_command,
    validate_command,
)
from kartograf.download.plan import UpdatePlan
from kartograf.envelope import CommandResult
from kartograf.exceptions import ForbiddenError, RateLimitedError, ValidationError
from kartograf.messages import message
from kartograf.script import PLANNED_LINES, ScriptResult
from kartograf.serialization import Document
from kartograf.server.limits import RateLimiter, client_address, networks
from kartograf.server.routes import ServedCommand
from kartograf.server.settings import ServerSettings
from kartograf.server.stats import DailyStats

__all__ = ["Call", "ServerState", "prepare"]

NETWORK_CALLS: Final = 4
"""At most this many calls that use the network run at once (as the MCP server's)."""
ANALYSES: Final = "analyses_run"
"""The daily total of the plans answered and the scripts generated (DEV-15.11)."""


class ServerState:
    """What a running ``kartograf server`` keeps between requests.

    Parameters
    ----------
    settings : ServerSettings
        The limits and the files of the server.
    stats : DailyStats, optional
        The daily totals (``None``: not counted).
    clock : callable, optional
        The monotonic clock of the limits [s]; tests pass their own.
    """

    def __init__(
        self,
        settings: ServerSettings,
        *,
        stats: DailyStats | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.stats = stats
        self.cache = MetadataCache(
            settings.cache_path, refresh_ttl_seconds=settings.index_max_age
        )
        self.requests = RateLimiter(
            settings.request_limit, settings.request_window, clock
        )
        self.plans = RateLimiter(settings.plan_limit, settings.plan_window, clock)
        self._trusted = networks(settings.trusted_proxies)

    def client(self, peer: str | None, forwarded_for: str | None) -> str:
        """Return the address of a client (AGI-6.9; ``limits.client_address``)."""
        return client_address(peer, forwarded_for, self._trusted)

    def hit_request(self, address: str) -> None:
        """Count a request of ``address`` (DEV-15.9).

        Raises
        ------
        RateLimitedError
            The client has made ``request_limit`` requests in its window
            (``request_limit``).
        """
        retry = self.requests.hit(address)
        if retry is not None:
            limit, window = self.settings.request_limit, self.settings.request_window
            raise RateLimitedError(
                message(
                    "server.request_limit", limit=limit, window=window, seconds=retry
                ),
                reason="request_limit",
                retry_after_s=retry,
                limit=limit,
                window_s=window,
            )

    def hit_plan(self, address: str) -> None:
        """Count a plan of ``address``, or a script that plans.

        Raises
        ------
        RateLimitedError
            The client has asked ``plan_limit`` plans in its window (``plan_limit``).
        """
        retry = self.plans.hit(address)
        if retry is not None:
            limit, window = self.settings.plan_limit, self.settings.plan_window
            raise RateLimitedError(
                message("server.plan_limit", limit=limit, window=window, seconds=retry),
                reason="plan_limit",
                retry_after_s=retry,
                limit=limit,
                window_s=window,
                hint=message("server.plan_limit_hint"),
            )

    def count_analysis(self) -> None:
        """Count a plan answered or a script generated in the daily totals."""
        if self.stats is not None:
            self.stats.count(ANALYSES)

    def close(self) -> None:
        """Close the cache and write the daily totals."""
        self.cache.close()
        if self.stats is not None:
            self.stats.flush()


@dataclass(frozen=True)
class Call:
    """A request turned into a call of the library, ready to run.

    Attributes
    ----------
    command : str
        The catalog id of the command.
    plans : bool
        The call plans (a data command, or a direct script of a line): the plan limit
        counts it and ``plan_max_units`` bounds it.
    counted : bool
        The call counts as ``analyses_run`` when it succeeds: a plan or a script.
    network : bool
        The call may use the network (its command's ``effects``).
    run : callable
        The call: the envelope ``kartograf-result/1`` of the command, or an error of
        the library.
    """

    command: str
    plans: bool
    counted: bool
    network: bool
    run: Callable[[], CommandResult[Any]]


def _given(value: object) -> bool:
    """Say whether an option is given: ``None`` and a false switch are not."""
    return value is not None and value is not False


def _refuse_paths(served: ServedCommand, options: Mapping[str, object]) -> None:
    """Refuse every option with a ``path_role`` a request gives (AGI-6.1)."""
    for name, role in served.paths.items():
        if options.get(name) is not None:
            raise ForbiddenError(
                message("server.path_option", option=name, role=role),
                option=name,
                hint=message("server.path_option_hint", option=name),
                reason="path_option",
            )


def _units(document: Document | None) -> int:
    """Return the units of a plan or of the plan of a direct script."""
    if isinstance(document, UpdatePlan):
        return len({item.unit for item in document.items})
    if isinstance(document, ScriptResult):
        return len(
            {file.unit for file in document.files}
            | {file.unit for file in document.left_out}
        )
    return 0


def _bounded[T: Document](result: CommandResult[T], max_units: int) -> CommandResult[T]:
    """Return the result of a plan of at most ``max_units`` units.

    Raises
    ------
    ValidationError
        More units (``too_many_units``; ``allowed`` the bound, ADR-063 decision 8).
    """
    count = _units(result.result)
    if count > max_units:
        raise ValidationError(
            message("server.too_many_units", count=count, limit=max_units),
            allowed=(str(max_units),),
            hint=message("server.too_many_units_hint"),
            reason="too_many_units",
        )
    return result


def _plan_call(
    served: ServedCommand,
    options: Mapping[str, object],
    *,
    check: bool,
    state: ServerState,
) -> Call:
    """Return the call of a data command: its detached plan, or a refusal."""
    command = served.command.id
    for name in RUN_OPTIONS:
        if _given(options.get(name)):
            raise ForbiddenError(
                message("server.run_option", option=name, command=command),
                option=name,
                hint=message("server.writes_disabled_hint"),
                reason="writes_disabled",
            )
    in_body = options.get(CHECK_OPTION)
    if in_body is not None and not isinstance(in_body, bool):
        raise ValidationError(
            message("server.check_not_switch", value=in_body), option=CHECK_OPTION
        )
    if not (check or in_body is True):
        raise ForbiddenError(
            message("server.writes_disabled", command=command),
            option=CHECK_OPTION,
            hint=message("server.writes_disabled_hint"),
            reason="writes_disabled",
        )
    call_options = {k: v for k, v in options.items() if k != CHECK_OPTION}
    validate_command(command, call_options)
    max_units = state.settings.plan_max_units

    def run() -> CommandResult[Any]:
        plan = check_command(command, call_options, detached=True, cache=state.cache)
        return _bounded(plan, max_units)

    return Call(command, plans=True, counted=True, network=True, run=run)


def _planned_line(
    served: ServedCommand, options: Mapping[str, object]
) -> CommandCall | None:
    """Return the line a call would plan (``PLANNED_LINES``), its input files refused.

    Raises
    ------
    ForbiddenError
        The line names an input file (``geometry``), which the plan would read
        (``path_option``).
    UsageError, ValidationError
        The line cannot be read, as ``parse_command`` says.
    """
    planned = PLANNED_LINES.get(served.command.id)
    if planned is None:
        return None
    option, switch = planned
    line = options.get(option)
    if options.get(switch) is not True or not isinstance(line, str):
        return None
    call = parse_command(line)
    for param in declared_commands()[call.command].params:
        if param.path_role != "input":
            continue
        if call.options.get(param.name) is not None or param.name in call.run:
            raise ForbiddenError(
                message(
                    "server.path_in_line",
                    command=served.command.id,
                    option=param.name,
                ),
                option=option,
                hint=message("server.path_option_hint", option=param.name),
                reason="path_option",
            )
    return call


def _query_call(
    served: ServedCommand, options: Mapping[str, object], *, state: ServerState
) -> Call:
    """Return the call of a read-only command (``run_command``)."""
    command = served.command.id
    planned = _planned_line(served, options)
    plans = planned is not None and options.get("plan") is None
    if planned is not None and plans:
        validate_command(planned.command, planned.options)
    # the options of a call proper and every name the check of the call refuses; the
    # rest are given by name (the ``plan`` document of ``script generate``)
    others = {
        k: v
        for k, v in options.items()
        if k in served.kinds and k not in served.call and k != CHECK_OPTION
    }
    call_options = {k: v for k, v in options.items() if k not in others}
    run_arguments: dict[str, Any] = convert_arguments(
        {name: served.kinds[name] for name in others}, others
    )
    max_units = state.settings.plan_max_units

    def run() -> CommandResult[Any]:
        result = run_command(command, call_options, cache=state.cache, **run_arguments)
        return _bounded(result, max_units) if plans else result

    return Call(
        command,
        plans=plans,
        counted=command in PLANNED_LINES,
        network=served.entry.effects.network,
        run=run,
    )


def prepare(
    served: ServedCommand,
    options: Mapping[str, object],
    *,
    check: bool,
    state: ServerState,
) -> Call:
    """Turn the options of a request into a call, without network and without writing.

    Parameters
    ----------
    served : ServedCommand
        The command of the route.
    options : Mapping
        The options of the request in the JSON form (the query of a ``GET``, the body
        of a ``POST``).
    check : bool
        ``?check=true`` of a ``POST`` of a data command.
    state : ServerState
        The server.

    Returns
    -------
    Call
        The call; running it may use the network.

    Raises
    ------
    ForbiddenError
        An option with a ``path_role`` or an input file of a planned line
        (``path_option``); the run of a data command or an option of its run
        (``writes_disabled``).
    ValidationError
        The options, as ``validate_command`` checks them.
    """
    _refuse_paths(served, options)
    if served.plans:
        return _plan_call(served, options, check=check, state=state)
    return _query_call(served, options, state=state)
