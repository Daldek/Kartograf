"""The documents of ``kartograf server`` against the Nogat schemas and OpenAPI 3.1.

``GET /api/v1/server`` is ``nogat-server/1``, the envelopes of the served commands
are ``result-1`` and ``GET /api/v1/commands/list`` is ``command-list-1``
(``schemas/nogat/``, AGI-4.1, AGI-6.7). ``GET /api/v1/openapi.json`` validates
against the official OpenAPI 3.1 JSON Schema, vendored byte for byte as
``tests/fixtures/openapi/oas-3.1-schema-2022-10-07.json`` from
https://spec.openapis.org/oas/3.1/schema/2022-10-07, and agrees with the command
catalog (AGI-6.2, AGI-6.6): one operation per route of the catalog, reachable from
the document's own address and behind a proxy's prefix.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import jsonschema
import pytest
from referencing import Registry, Resource
from starlette.testclient import TestClient

from kartograf.catalog.spec import CHECK_OPTION, RUN_OPTIONS
from kartograf.server.app import create_app
from kartograf.server.routes import served_commands
from kartograf.server.settings import ServerSettings

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "nogat"
OPENAPI_SCHEMA = (
    ROOT / "tests" / "fixtures" / "openapi" / "oas-3.1-schema-2022-10-07.json"
)
API = "/api/v1"
PROBLEM = "application/problem+json"
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nogat(name: str) -> jsonschema.Draft202012Validator:
    schemas = [
        _load(SCHEMAS / f"{n}.schema.json")
        for n in ("result-1", "error-1", "commands-1", "command-list-1", "server-1")
    ]
    registry: Registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return jsonschema.Draft202012Validator(
        _load(SCHEMAS / f"{name}.schema.json"), registry=registry
    )


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    directory = tmp_path / "server"
    settings = ServerSettings(
        index_max_age=3600,
        plan_limit=1000,
        plan_window=60,
        plan_max_units=10,
        request_limit=100000,
        request_window=60,
        trusted_proxies=("127.0.0.1",),
        cache_path=directory / "metadata.db",
        log_dir=directory / "logs",
        stats_path=directory / "stats.jsonl",
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as opened:
        yield opened


@pytest.fixture
def catalog(client) -> dict[str, dict[str, Any]]:
    """The rows of ``GET /commands/list``, each with its ``GET /commands/schema``."""
    rows = client.get(f"{API}/commands/list").json()["result"]["commands"]
    catalog = {}
    for row in rows:
        answer = client.get(f"{API}/commands/schema", params={"command": row["name"]})
        (command,) = answer.json()["result"]["commands"]
        catalog[row["name"]] = {**command, **row}
    return catalog


@pytest.fixture
def openapi(client) -> dict[str, Any]:
    return client.get(f"{API}/openapi.json").json()


def _operations(document: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in document["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                yield path, method.upper(), operation


def _query(options: dict[str, object]) -> dict[str, str]:
    """The query of a ``GET`` of options in the JSON form (an array joined by ``,``)."""
    query = {}
    for name, value in options.items():
        if isinstance(value, list):
            query[name] = ",".join(str(part) for part in value)
        elif isinstance(value, bool):
            query[name] = "true" if value else "false"
        else:
            query[name] = str(value)
    return query


def _served_get_examples() -> list[Any]:
    """The examples of the catalog of the ``GET`` routes without network or paths."""
    params = []
    for served in served_commands():
        if served.rest.method != "GET" or served.entry.effects.network:
            continue
        for number, example in enumerate(served.command.examples, start=1):
            if any(name in served.paths for name in example.options):
                continue
            params.append(
                pytest.param(
                    served.rest.path,
                    dict(example.options),
                    id=f"{served.command.id}:{number}",
                )
            )
    return params


def _is_data(row: dict[str, Any]) -> bool:
    """A data command: the command that checks it is itself (``check=true``)."""
    return row["check"] == row["name"]


def _refs(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                yield item
            else:
                yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _resolve(document: dict[str, Any], ref: str) -> object:
    target: Any = document
    for part in ref.removeprefix("#/").split("/"):
        target = target[part.replace("~1", "/").replace("~0", "~")]
    return target


# --- the Nogat documents -----------------------------------------------------------


def test_server_document_validates_against_server_1(client):
    response = client.get(f"{API}/server")

    assert response.status_code == 200
    document = response.json()
    _nogat("server-1").validate(document)
    (service,) = document["services"]
    assert service["tool"] == "kartograf"
    assert f"{service['api']['1']}/server" == f"{API}/server"


@pytest.mark.parametrize(("path", "options"), _served_get_examples())
def test_served_get_envelope_validates_against_result_1(client, path, options):
    response = client.get(path, params=_query(options))

    assert response.status_code == 200, response.text
    _nogat("result-1").validate(response.json())


def test_commands_list_result_validates_against_command_list_1(client):
    envelope = client.get(f"{API}/commands/list").json()

    _nogat("command-list-1").validate(envelope["result"])


def test_every_rest_of_the_command_list_is_a_route_with_its_method(client, catalog):
    routes = [row["rest"] for row in catalog.values() if row["rest"] is not None]

    statuses = {
        (rest["method"], rest["path"]): client.request(
            rest["method"], rest["path"]
        ).status_code
        for rest in routes
    }

    # no options: the answer, an invalid input or a data command's refusal of a run
    assert routes
    assert {
        route: status
        for route, status in statuses.items()
        if status not in (200, 400, 403)
    } == {}


# --- the OpenAPI document ----------------------------------------------------------


def test_openapi_document_validates_against_openapi_3_1(openapi):
    validator = jsonschema.Draft202012Validator(_load(OPENAPI_SCHEMA))

    validator.validate(openapi)

    assert openapi["openapi"].startswith("3.1.")


def test_openapi_has_one_operation_per_route_of_the_catalog(openapi, catalog):
    own = {"kartograf_server", "kartograf_openapi"}
    operations = {
        operation["operationId"]: (method, path)
        for path, method, operation in _operations(openapi)
        if operation["operationId"] not in own
    }
    routed = {
        row["operation_id"]: (row["rest"]["method"], row["rest"]["path"])
        for row in catalog.values()
        if row["rest"] is not None
    }

    assert len(operations) == len(list(_operations(openapi))) - len(own)
    assert {
        operation_id: (method, f"{API}{path}")
        for operation_id, (method, path) in operations.items()
    } == routed


@pytest.mark.parametrize("base", [API, "/kartograf/v1"])
def test_openapi_paths_resolve_to_the_routes_from_its_address(openapi, catalog, base):
    server = urljoin(
        f"http://localhost{base}/openapi.json", openapi["servers"][0]["url"]
    )
    # the URL of an operation is the server's URL followed by the path (OpenAPI 4.8.1)
    resolved = {
        operation["operationId"]: f"{server}{path}"
        for path, _, operation in _operations(openapi)
    }

    for row in catalog.values():
        if row["rest"] is not None:
            route = row["rest"]["path"].removeprefix(API)
            assert resolved[row["operation_id"]] == f"http://localhost{base}{route}"
    assert resolved["kartograf_server"] == f"http://localhost{base}/server"
    assert resolved["kartograf_openapi"] == f"http://localhost{base}/openapi.json"


def test_openapi_operations_have_texts_a_result_and_problems(openapi, catalog):
    data = {row["operation_id"] for row in catalog.values() if _is_data(row)}
    for path, method, operation in _operations(openapi):
        name = f"{method} {path}"
        assert operation["summary"], name
        assert operation["description"], name
        responses = operation["responses"]
        assert "application/json" in responses["200"]["content"], name
        problems = {
            status
            for status, response in responses.items()
            if PROBLEM in response.get("content", {})
        }
        expected = {"429", "500"}
        if operation["operationId"] not in ("kartograf_server", "kartograf_openapi"):
            expected.add("400")
        if operation["operationId"] in data:
            expected.add("403")
        assert expected <= problems, name


def test_openapi_get_parameters_are_the_options_without_paths(openapi, catalog):
    by_id = {
        operation["operationId"]: operation for _, _, operation in _operations(openapi)
    }
    for row in catalog.values():
        if row["rest"] is None or row["rest"]["method"] != "GET":
            continue
        operation = by_id[row["operation_id"]]

        names = [p["name"] for p in operation.get("parameters", [])]

        offered = [o["name"] for o in row["options"] if o.get("path_role") is None]
        assert names == offered, row["name"]
        assert {p["in"] for p in operation.get("parameters", [])} <= {"query"}


def test_openapi_post_bodies_leave_out_paths_and_the_run(openapi, catalog):
    by_id = {
        operation["operationId"]: operation for _, _, operation in _operations(openapi)
    }
    refused = {CHECK_OPTION, *RUN_OPTIONS}
    for row in catalog.values():
        if row["rest"] is None or row["rest"]["method"] != "POST":
            continue
        operation = by_id[row["operation_id"]]
        body = operation["requestBody"]["content"]["application/json"]["schema"]
        is_data = _is_data(row)

        names = list(body["properties"])

        offered = [
            o["name"]
            for o in row["options"]
            if o.get("path_role") is None and not (is_data and o["name"] in refused)
        ]
        assert names == offered, row["name"]
        parameters = operation.get("parameters", [])
        if is_data:
            assert [(p["name"], p["in"], p["required"]) for p in parameters] == [
                (CHECK_OPTION, "query", True)
            ], row["name"]
        else:
            assert parameters == [], row["name"]


def test_openapi_every_ref_resolves_within_the_document(openapi):
    refs = sorted(set(_refs(openapi)))

    unresolved = []
    for ref in refs:
        try:
            _resolve(openapi, ref)
        except (KeyError, IndexError, TypeError):
            unresolved.append(ref)

    assert refs
    assert all(ref.startswith("#/") for ref in refs)
    assert unresolved == []
