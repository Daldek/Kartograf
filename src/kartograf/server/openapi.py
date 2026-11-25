"""
The OpenAPI 3.1 document of ``kartograf server``, built from the catalog (AGI-6.2).

``GET /api/v1/openapi.json`` answers it. Every route of the catalog is an operation
whose ``operationId`` is the command's ``operation_id``, with its summary, its
description (when to use it and when not, its rules), its options (the query of a
``GET``, the JSON body of a ``POST``; the options a server refuses, those with a
``path_role`` and those of a run, are left out), examples and the problems it
answers; ``/server`` and ``/openapi.json`` are the server's own. The paths are
relative to the base of the API, and ``servers`` is the relative URL ``../v1``: the
document reads right at ``/api/v1/openapi.json`` and behind a proxy that routes
``/kartograf/v1/`` to it (Latarnik, AGI-6.9). The texts are English, as every machine
document (AGI-9.2).
"""

import copy
import functools
from collections.abc import Iterable, Mapping
from typing import Any, Final

from kartograf._errors import BY_CODE, CODES
from kartograf._output_schema import OUTPUT_SCHEMA
from kartograf.catalog.build import declared_options
from kartograf.catalog.commands import declared
from kartograf.catalog.excerpts import EXCERPTS
from kartograf.catalog.spec import CHECK_OPTION, RUN_OPTIONS
from kartograf.catalog.tools import option_schema
from kartograf.script import PLANNED_LINES
from kartograf.server.problems import PROBLEM_MEDIA_TYPE, REGISTRY_PAGE, http_status
from kartograf.server.routes import API_BASE, ServedCommand, served_commands

__all__ = ["CAPABILITIES", "OPENAPI_PATH", "SERVER_PATH", "openapi_document"]

OPENAPI_PATH: Final = f"{API_BASE}/openapi.json"
SERVER_PATH: Final = f"{API_BASE}/server"
CAPABILITIES: Final = ("catalog", "plan", "script")
"""What the server serves (``nogat-server/1``): the catalog with the queries without
paths, the plans of the data commands and ``script generate``."""

_OPENAPI: Final = "3.1.0"
_SERVERS_URL: Final = "../v1"
_JSON: Final = "application/json"
# Every route can answer these: an invalid query or body, the request limit and a
# failure of the server.
_ALWAYS: Final = ("validation_error", "rate_limited", "internal_error")
_RESULT_REF: Final = {"$ref": "#/components/schemas/Result"}
_PROBLEM_REF: Final = {"$ref": "#/components/schemas/Problem"}
_DESCRIPTION: Final = (
    "The read-only HTTP server of Kartograf (ADR-063): the command catalog, the "
    "queries without paths, the plans of the data commands and the scripts of a "
    "request for the user's own machine. It runs no download and writes no data; "
    "the data bytes go between the user and the source. A route of a command is the "
    "`rest` of its entry in `GET /commands/list`; its answer is the envelope "
    "`kartograf-result/1`, as `kartograf ... --json` prints it, and an error is "
    "`application/problem+json` in the language of `Accept-Language` (en, pl). "
    "Limits per client: `request_limit` requests per `request_window` and "
    "`plan_limit` plans per `plan_window` (429 `rate_limited` with `Retry-After`), "
    "`plan_max_units` units per plan (400 `too_many_units`)."
)
_SERVERS_DESCRIPTION: Final = (
    "The base of the API, relative to this document: /api/v1 on the server, the "
    "route of a proxy behind one."
)
_DATA_NOTE: Final = (
    "This server only plans: `POST ...?check=true` answers the plan "
    "(`kartograf-plan/1`) of a plain write into a directory that does not exist yet "
    "(`output_dir` `.`, the paths relative to it, every file `write`), with the URL, "
    "size, source and licence of each file. Without `check=true`, with an option of "
    "a run or with an option that is a path the answer is 403 `forbidden` "
    "(`writes_disabled`, `path_option`). Counted by `plan_limit`; more than "
    "`plan_max_units` units answer 400 `too_many_units`."
)
_PATH_NOTE: Final = (
    "An option that is a path ({names}) is refused with 403 `forbidden` "
    "(`path_option`): the server reads no file of a client."
)
_SCRIPT_NOTE: Final = (
    "A direct script of a line (`direct` with `command`) is planned on the server: "
    "counted by `plan_limit` and bounded by `plan_max_units`; a line with `--geometry` "
    "is refused (403 `path_option`)."
)
_CHECK_PARAMETER: Final = {
    "name": CHECK_OPTION,
    "in": "query",
    "required": True,
    "description": "Must be true: the answer is the plan of the request, nothing is "
    "run (a run answers 403 `forbidden`, `writes_disabled`).",
    "schema": {"type": "boolean", "const": True},
    "example": True,
}
_PROBLEM_SCHEMA: Final = {
    "type": "object",
    "description": "An error (RFC 9457, AGI-6.3): the texts follow `Accept-Language`, "
    "`Content-Language` names their language.",
    "required": ["type", "title", "status", "detail", "code"],
    "properties": {
        "type": {
            "type": "string",
            "format": "uri",
            "description": "The entry of `code` in the Nogat error registry.",
        },
        "title": {"type": "string", "description": "The registry's title of `code`."},
        "status": {"type": "integer", "description": "The HTTP status of `code`."},
        "detail": {"type": "string", "description": "What happened."},
        "instance": {
            "type": "string",
            "format": "uri-reference",
            "description": "The path of the request.",
        },
        "code": {
            "type": "string",
            "enum": [entry.code for entry in CODES],
            "description": "The code of the Nogat error registry.",
        },
        "hint": {"type": "string", "description": "How to fix it, one line."},
        "details": {
            "type": "object",
            "description": "`reason`, the refinement of `code`, and the facts of the "
            "error (`option`, `allowed`, `retry_after_s`, ...).",
            "properties": {"reason": {"type": "string"}},
        },
        "errors": {
            "type": "array",
            "description": "The invalid options of a `validation_error`.",
            "items": {
                "type": "object",
                "required": ["pointer", "message"],
                "properties": {
                    "pointer": {
                        "type": "string",
                        "description": "JSON Pointer of the option: `/query/<name>` "
                        "or `/body/<name>`.",
                    },
                    "type": {"type": "string", "description": "`details.reason`."},
                    "message": {"type": "string"},
                },
            },
        },
    },
}
_SERVER_SCHEMA: Final = {
    "type": "object",
    "description": "`nogat-server/1` (Nogat schemas/exchange/server-1.schema.json): "
    "one service, this server.",
    "required": ["schema", "services"],
    "properties": {
        "schema": {"const": "nogat-server/1"},
        "services": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["tool", "version", "api", "capabilities"],
                "properties": {
                    "tool": {"const": "kartograf"},
                    "version": {"type": "string"},
                    "api": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "gui": {
                        "type": "string",
                        "description": "The address of the GUI served with the API "
                        "(`kartograf gui serve`), from `[nogat.gui]` of `nogat.toml`, "
                        "else `/`.",
                    },
                    "terms": {
                        "type": "object",
                        "description": "The regulamin of a public GUI and its version "
                        "(DEV-15.7).",
                        "required": ["url", "version"],
                        "properties": {
                            "url": {"type": "string"},
                            "version": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
}


def _result_schema() -> dict[str, Any]:
    """Return the schema of the envelope, its ``$defs`` reachable in the document."""
    schema = copy.deepcopy(dict(OUTPUT_SCHEMA))
    schema.pop("$schema", None)

    def moved(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: (
                    item.replace("#/$defs/", "#/components/schemas/Result/$defs/")
                    if key == "$ref" and isinstance(item, str)
                    else moved(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [moved(item) for item in value]
        return value

    result = moved(schema)
    assert isinstance(result, dict)  # a schema is an object
    return result


def _problems(codes: Iterable[str]) -> dict[str, Any]:
    """Return the problem responses of the codes, one per HTTP status."""
    by_status: dict[int, list[str]] = {}
    for code in dict.fromkeys(codes):
        if BY_CODE[code].http_status is not None:
            by_status.setdefault(http_status(code), []).append(code)
    return {
        str(status): {
            "description": "; ".join(
                f"`{code}`: {BY_CODE[code].title}" for code in codes_of_status
            ),
            "content": {
                PROBLEM_MEDIA_TYPE: {
                    "schema": _PROBLEM_REF,
                    "example": _problem_example(codes_of_status[0]),
                }
            },
        }
        for status, codes_of_status in sorted(by_status.items())
    }


def _problem_example(code: str) -> dict[str, object]:
    """Return an example problem of a code (the registry's title, English)."""
    return {
        "type": f"{REGISTRY_PAGE}#{code}",
        "title": BY_CODE[code].title,
        "status": http_status(code),
        "detail": BY_CODE[code].meaning,
        "instance": f"{API_BASE}/...",
        "code": code,
    }


def _envelope(served: ServedCommand, result: Mapping[str, object]) -> dict[str, Any]:
    """Return an example envelope of a route with the excerpt of its result."""
    return {
        "schema": "kartograf-result/1",
        "tool": "kartograf",
        "version": "...",
        "command": served.command.id,
        "check": served.plans,
        "status": "ok",
        "result": dict(result),
        "items": [],
        "notices": [],
    }


def _result_excerpt(served: ServedCommand) -> Mapping[str, object]:
    """Return the excerpt of the result of a route (a data command: its plan)."""
    if served.plans:
        return {
            **EXCERPTS["kartograf-plan/1"],
            "mode": "plain",
            "root": None,
            "output_dir": ".",
        }
    if served.entry.examples:
        return served.entry.examples[0].result
    return EXCERPTS[served.entry.result.schema]


def _offered(served: ServedCommand) -> list[tuple[str, dict[str, Any], bool]]:
    """Return the options a client may give: name, schema and whether required.

    The options with a ``path_role`` are refused, and so are ``check`` and the
    options of a run of a data command (``check`` is the query's).
    """
    refused = set(served.paths)
    if served.plans:
        refused |= {CHECK_OPTION, *RUN_OPTIONS}
    command = served.command
    return [
        (param.name, option_schema(command, param, option), option.required)
        for param, option in zip(
            declared_options(command), served.entry.options, strict=True
        )
        if param.name not in refused
    ]


def _example_options(served: ServedCommand) -> list[tuple[str, dict[str, object]]]:
    """Return the examples of the catalog as the options of a request: title, options.

    The options a client may not give are left out of them.
    """
    offered = {name for name, _, _ in _offered(served)}
    return [
        (
            example.title or served.entry.summary,
            {
                name: value
                for name, value in {**example.options, **example.run}.items()
                if name in offered
            },
        )
        for example in served.command.examples
    ]


def _description(served: ServedCommand) -> str:
    """Return the description of an operation: the catalog's and the server's notes."""
    parts = [served.entry.description, *served.entry.rules]
    if served.plans:
        parts.append(_DATA_NOTE)
    elif served.paths:
        parts.append(_PATH_NOTE.format(names=", ".join(sorted(served.paths))))
    if served.command.id in PLANNED_LINES:
        parts.append(_SCRIPT_NOTE)
    return "\n\n".join(part for part in parts if part)


def _operation(served: ServedCommand) -> dict[str, Any]:
    """Return the operation of the route of a command."""
    entry = served.entry
    offered = _offered(served)
    examples = _example_options(served)
    operation: dict[str, Any] = {
        "operationId": entry.operation_id,
        "summary": entry.summary,
        "description": _description(served),
        "tags": [served.command.group],
    }
    if served.rest.method == "GET":
        parameters = []
        for name, schema, required in offered:
            parameter: dict[str, Any] = {
                "name": name,
                "in": "query",
                "required": required,
                "description": schema.get("description", ""),
                "schema": schema,
            }
            if schema.get("type") == "array":
                parameter.update(style="form", explode=False)
            example = next((opts[name] for _, opts in examples if name in opts), None)
            if example is not None:
                parameter["example"] = example
            parameters.append(parameter)
        if parameters:
            operation["parameters"] = parameters
    else:
        if served.plans:
            operation["parameters"] = [dict(_CHECK_PARAMETER)]
        body: dict[str, Any] = {
            "type": "object",
            "properties": {name: schema for name, schema, _ in offered},
            "additionalProperties": False,
        }
        needed_names = [name for name, _, needed in offered if needed]
        if needed_names:
            body["required"] = needed_names
        if "bbox" in body["properties"] and "bbox_crs" in body["properties"]:
            body["dependentRequired"] = {"bbox": ["bbox_crs"]}
        content: dict[str, Any] = {"schema": body}
        if examples:
            content["examples"] = {
                f"example{number}": {"summary": title, "value": options}
                for number, (title, options) in enumerate(examples, start=1)
            }
        operation["requestBody"] = {"required": True, "content": {_JSON: content}}
    codes = [*_ALWAYS, *entry.errors]
    if served.plans or served.paths or served.command.id in PLANNED_LINES:
        codes.append("forbidden")
    operation["responses"] = {
        "200": {
            "description": f"The envelope `kartograf-result/1` with "
            f"`{'kartograf-plan/1' if served.plans else entry.result.schema}`.",
            "content": {
                _JSON: {
                    "schema": _RESULT_REF,
                    "example": _envelope(served, _result_excerpt(served)),
                }
            },
        },
        **_problems(codes),
    }
    return operation


def _own_paths(version: str) -> dict[str, Any]:
    """Return the operations of the server's own routes."""
    return {
        SERVER_PATH.removeprefix(API_BASE): {
            "get": {
                "operationId": "kartograf_server",
                "summary": "Describe this server: nogat-server/1",
                "description": "What this server serves (AGI-6.7): the tool, its "
                "version, the base of each major of its API and its capabilities "
                f"({', '.join(CAPABILITIES)}). A client finds the API with this one "
                "request, here and behind a proxy. Not for the commands: use "
                "`GET /commands/list`.",
                "tags": ["server"],
                "responses": {
                    "200": {
                        "description": "`nogat-server/1`.",
                        "content": {
                            _JSON: {
                                "schema": {"$ref": "#/components/schemas/Server"},
                                "example": server_document(version),
                            }
                        },
                    },
                    **_problems(("rate_limited", "internal_error")),
                },
            }
        },
        OPENAPI_PATH.removeprefix(API_BASE): {
            "get": {
                "operationId": "kartograf_openapi",
                "summary": "Describe the API: this OpenAPI 3.1 document",
                "description": "The routes, their options, results and problems, "
                "built from the command catalog (AGI-6.2). Not for the options of one "
                "command with their Polish texts: use `GET /commands/schema`.",
                "tags": ["server"],
                "responses": {
                    "200": {
                        "description": "OpenAPI 3.1.",
                        "content": {_JSON: {"schema": {"type": "object"}}},
                    },
                    **_problems(("rate_limited", "internal_error")),
                },
            }
        },
    }


def server_document(
    version: str,
    *,
    gui: str | None = None,
    terms: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return ``nogat-server/1`` of this server (AGI-6.7, ADR-063 decision 7).

    Parameters
    ----------
    version : str
        The version of Kartograf.
    gui : str, optional
        The address of the GUI served with the API (``kartograf gui serve``).
    terms : Mapping, optional
        ``{url, version}`` of the regulamin of a public GUI (DEV-15.7).
    """
    service: dict[str, Any] = {
        "tool": "kartograf",
        "version": version,
        "api": {"1": API_BASE},
        "capabilities": list(CAPABILITIES),
    }
    if gui is not None:
        service["gui"] = gui
    if terms is not None:
        service["terms"] = dict(terms)
    return {"schema": "nogat-server/1", "services": [service]}


@functools.cache
def openapi_document(version: str) -> Mapping[str, Any]:
    """Return the OpenAPI 3.1 document of the server (the same object every time).

    Parameters
    ----------
    version : str
        The version of Kartograf (``info.version``).
    """
    paths = _own_paths(version)
    summaries = {group.name: group.summary for group in declared().groups}
    groups: dict[str, str] = {}
    for served in served_commands():
        path = served.rest.path.removeprefix(API_BASE)
        paths.setdefault(path, {})[served.rest.method.lower()] = _operation(served)
        group = served.command.group
        groups.setdefault(group, str(summaries.get(group, group)))
    return {
        "openapi": _OPENAPI,
        "info": {
            "title": "Kartograf",
            "version": version,
            "summary": "Plans and scripts of official spatial data of Poland and "
            "Czechia, read only",
            "description": _DESCRIPTION,
            "license": {"name": "MIT", "identifier": "MIT"},
        },
        "servers": [{"url": _SERVERS_URL, "description": _SERVERS_DESCRIPTION}],
        "tags": [
            {"name": "server", "description": "The server's own routes."},
            *({"name": name, "description": text} for name, text in groups.items()),
        ],
        "paths": paths,
        "components": {
            "schemas": {
                "Result": _result_schema(),
                "Problem": _PROBLEM_SCHEMA,
                "Server": _SERVER_SCHEMA,
            }
        },
    }
