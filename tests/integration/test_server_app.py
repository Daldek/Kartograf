"""``kartograf server`` over HTTP (ADR-063 decisions 2, 4, 7 and 8; AGI-6).

A ``TestClient`` of ``create_app`` with its files in ``tmp_path``: what the server
refuses (a run, a path, a local command), its problem documents in the language of
``Accept-Language``, the options of a query and of a body, the detached plan of a data
command (``check_command`` replaced by a fake that returns a real plan), the limits
per client and the daily totals, ``script generate``, a failure of the server and
the access log. No request leaves the machine.
"""

import contextlib
import dataclasses
import io
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import kartograf
from kartograf.download.plan import Fetch, PlanItem, UpdatePlan
from kartograf.envelope import CommandResult, wrap
from kartograf.messages import message
from kartograf.server.app import BODY_MAX_BYTES, create_app
from kartograf.server.calls import ServerState
from kartograf.server.nogat_logging import ServerLog
from kartograf.server.routes import local_commands
from kartograf.server.settings import ServerSettings

REGISTRY = Path(__file__).resolve().parents[2] / "schemas/nogat/error_registry.json"
REGISTRY_PAGE = "https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md"
PROBLEM = "application/problem+json"
PROXY = "127.0.0.1"
VISITOR = "198.51.100.23"
DOWNLOAD = "/api/v1/elevation/download"
CHECK = f"{DOWNLOAD}?check=true"
SCRIPT = "/api/v1/script/generate"
SHEET = "N-34-130-D-d-2-4"
OPTIONS = {
    "product": "nmt",
    "sheet": SHEET,
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
LINE = (
    f"elevation download --product nmt --sheet {SHEET} --resolution 1m"
    " --vertical-crs EVRF2007 -o ./dem"
)
GEOMETRY_LINE = (
    "elevation download --product nmt --geometry zlewnia.gpkg --resolution 1m"
    " --vertical-crs EVRF2007 -o ./dem"
)
BBOX_QUERY = {
    "bbox": "565000,242000,566000,243000",
    "bbox_crs": "EPSG:2180",
    "scale": "1:10000",
    "sheet_system": "1992",
}


class Clock:
    """The monotonic clock of the limits, which the test moves."""

    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


class FakeCheck:
    """``check_command`` without network: the detached plan of ``units``."""

    def __init__(self, units: tuple[str, ...] = (SHEET,)) -> None:
        self.units = units
        self.calls: list[tuple[str, dict[str, object], bool, object]] = []

    def __call__(
        self,
        command: str,
        options: dict[str, object],
        *,
        detached: bool = False,
        cache: object = True,
        on_notice: object = None,
    ) -> CommandResult[UpdatePlan]:
        self.calls.append((command, dict(options), detached, cache))
        return wrap(command, _plan(self.units), check=True)


def _item(unit: str) -> PlanItem:
    return PlanItem(
        track="pl_sheet",
        segment="",
        hierarchy="",
        name=f"{unit}.asc",
        unit=unit,
        local_label=None,
        local_sha256=None,
        available_label="2024-05-01",
        available_signal=None,
        status="missing",
        action="write",
        path=Path(f"{unit}.asc"),
        source="pl.gugik.nmt_1m",
        fetch=Fetch(f"https://example.test/nmt/{unit}.asc", 1024),
    )


def _plan(units: tuple[str, ...]) -> UpdatePlan:
    return UpdatePlan(
        root=None,
        checked_at="2026-11-25T09:00:00+00:00",
        kartograf_version=kartograf.__version__,
        items=tuple(_item(unit) for unit in units),
        output_dir=".",
    )


def _registry() -> dict[str, dict[str, Any]]:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))["errors"]
    return {entry["code"]: entry for entry in entries}


def _state(client: TestClient) -> ServerState:
    return cast(ServerState, cast(Starlette, client.app).state.server)


@pytest.fixture
def settings(tmp_path) -> ServerSettings:
    return ServerSettings(
        index_max_age=3600,
        plan_limit=100,
        plan_window=600,
        plan_max_units=10,
        request_limit=1000,
        request_window=60,
        trusted_proxies=(PROXY,),
        cache_path=tmp_path / "cache" / "metadata.db",
        log_dir=tmp_path / "logs",
        stats_path=tmp_path / "data" / "stats.jsonl",
    )


@pytest.fixture
def released(monkeypatch):
    """A released Kartograf, whose tag a Kartograf script pins."""
    monkeypatch.setattr(kartograf, "__version__", "0.9.0")


@pytest.fixture
def fake_check(monkeypatch) -> FakeCheck:
    """The plan of a data command and of a direct script of a line, offline."""
    fake = FakeCheck()
    monkeypatch.setattr("kartograf.server.calls.check_command", fake)
    monkeypatch.setattr("kartograf.script.check_command", fake)
    return fake


@pytest.fixture
def open_server(settings) -> Iterator[Callable[..., TestClient]]:
    """Open a ``TestClient`` of ``create_app``; it is closed after the test."""
    with contextlib.ExitStack() as stack:

        def open_(
            changed: dict[str, Any] | None = None,
            *,
            peer: str = PROXY,
            clock: Callable[[], float] | None = None,
            log: ServerLog | None = None,
            raise_server_exceptions: bool = True,
        ) -> TestClient:
            app = create_app(
                dataclasses.replace(settings, **(changed or {})),
                log=log,
                clock=clock or Clock(),
            )
            client = TestClient(
                app,
                client=(peer, 50000),
                raise_server_exceptions=raise_server_exceptions,
            )
            return stack.enter_context(client)

        yield open_


@pytest.fixture
def client(open_server) -> TestClient:
    return open_server()


# --- what the server refuses -----------------------------------------------------


@pytest.mark.parametrize(
    ("url", "body"),
    [
        pytest.param(DOWNLOAD, OPTIONS, id="no_check"),
        pytest.param(f"{DOWNLOAD}?check=false", OPTIONS, id="check_false"),
        pytest.param(DOWNLOAD, {**OPTIONS, "check": False}, id="body_check_false"),
    ],
)
def test_data_command_without_check_is_forbidden_writes_disabled(
    client, fake_check, url, body
):
    response = client.post(url, json=body)

    assert response.status_code == 403
    problem = response.json()
    assert (problem["code"], problem["details"]["reason"]) == (
        "forbidden",
        "writes_disabled",
    )
    assert problem["details"]["option"] == "check"
    assert fake_check.calls == []


@pytest.mark.parametrize(
    ("name", "value"),
    [("update", "newer"), ("workers", 4), ("plan", {"schema": "kartograf-plan/1"})],
)
def test_data_command_with_a_run_option_is_forbidden_writes_disabled(
    client, fake_check, name, value
):
    response = client.post(CHECK, json={**OPTIONS, name: value})

    assert response.status_code == 403
    details = response.json()["details"]
    assert (details["reason"], details["option"]) == ("writes_disabled", name)
    assert fake_check.calls == []


def test_soil_hsg_summary_is_forbidden_writes_disabled(client, fake_check):
    response = client.post(
        "/api/v1/soil/hsg?check=true",
        json={"depth": "0-30cm", "sheet": SHEET, "summary": True},
    )

    assert response.status_code == 403
    assert response.json()["details"]["option"] == "summary"


@pytest.mark.parametrize(
    ("url", "body", "name"),
    [
        pytest.param(CHECK, {**OPTIONS, "root": "/srv/data"}, "root", id="root"),
        pytest.param(DOWNLOAD, {**OPTIONS, "root": "/srv"}, "root", id="root_no_check"),
        pytest.param(CHECK, {**OPTIONS, "output_dir": "dem"}, "output_dir", id="out"),
        pytest.param(
            CHECK,
            {"product": "nmt", "geometry": "area.gpkg", "resolution": "1m"},
            "geometry",
            id="geometry",
        ),
    ],
)
def test_data_command_path_option_is_forbidden_path_option(
    client, fake_check, url, body, name
):
    response = client.post(url, json=body)

    assert response.status_code == 403
    details = response.json()["details"]
    assert (details["reason"], details["option"]) == ("path_option", name)
    assert fake_check.calls == []


def test_sheet_find_geometry_is_forbidden_path_option(client):
    response = client.get(
        "/api/v1/sheet/find",
        params={"geometry": "/etc/passwd", "scale": "1:10000", "sheet_system": "1992"},
    )

    assert response.status_code == 403
    details = response.json()["details"]
    assert (details["reason"], details["option"]) == ("path_option", "geometry")


def test_direct_script_of_a_geometry_line_is_forbidden_path_option(client, fake_check):
    body = {"shell": "bash", "command": GEOMETRY_LINE, "direct": True}

    response = client.post(SCRIPT, json=body)

    assert response.status_code == 403
    details = response.json()["details"]
    assert (details["reason"], details["option"]) == ("path_option", "command")
    assert fake_check.calls == []


def test_kartograf_script_of_a_geometry_line_is_served(client, released):
    response = client.post(SCRIPT, json={"shell": "bash", "command": GEOMETRY_LINE})

    assert response.status_code == 200
    assert response.json()["result"]["kind"] == "kartograf"


@pytest.mark.parametrize(
    "path", [local.path for local in local_commands()], ids=lambda path: path
)
def test_local_command_route_is_forbidden_not_served(client, path):
    responses = [client.request(method, path) for method in ("GET", "POST", "DELETE")]

    assert [r.status_code for r in responses] == [403, 403, 403]
    assert {r.json()["details"]["reason"] for r in responses} == {"not_served"}


@pytest.mark.parametrize(
    "path", ["/api/v1/nothing", "/api/v2/server", "/api/v1/elevation/download/x"]
)
def test_unknown_route_is_not_found_unknown_route(client, path):
    response = client.get(path)

    assert response.status_code == 404
    problem = response.json()
    assert (problem["code"], problem["details"]) == (
        "not_found",
        {"reason": "unknown_route", "route": path},
    )


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", DOWNLOAD, ["POST"]),
        ("POST", "/api/v1/sheet/parse", ["GET", "HEAD"]),
        ("DELETE", "/api/v1/server", ["GET", "HEAD"]),
    ],
)
def test_wrong_method_is_method_not_allowed_with_allow(client, method, path, allowed):
    response = client.request(method, path)

    assert response.status_code == 405
    allow = [part.strip() for part in response.headers["allow"].split(",")]
    assert sorted(allow) == allowed
    problem = response.json()
    assert problem["code"] == "method_not_allowed"
    assert (problem["details"]["method"], sorted(problem["details"]["allowed"])) == (
        method,
        allowed,
    )


# --- the problem documents -----------------------------------------------------


@pytest.mark.parametrize(
    ("method", "url", "body", "code"),
    [
        pytest.param("GET", "/api/v1/sheet/parse", None, "validation_error", id="400"),
        pytest.param("POST", DOWNLOAD, OPTIONS, "forbidden", id="403"),
        pytest.param("GET", "/api/v1/nothing", None, "not_found", id="404"),
        pytest.param("GET", DOWNLOAD, None, "method_not_allowed", id="405"),
    ],
)
def test_problem_status_and_title_follow_the_registry(client, method, url, body, code):
    entry = _registry()[code]

    response = client.request(method, url, json=body)

    path = url.split("?")[0]
    assert response.status_code == entry["http_status"]
    assert response.headers["content-type"] == PROBLEM
    problem = response.json()
    assert {key: problem[key] for key in ("type", "title", "status", "instance")} == {
        "type": f"{REGISTRY_PAGE}#{code}",
        "title": entry["title_en"],
        "status": entry["http_status"],
        "instance": path,
    }
    assert problem["code"] == code
    assert isinstance(problem["detail"], str) and problem["detail"]


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        pytest.param("GET", "/api/v1/sheet/parse", None, id="validation"),
        pytest.param("POST", DOWNLOAD, OPTIONS, id="forbidden"),
        pytest.param("GET", "/api/v1/nothing", None, id="not_found"),
    ],
)
def test_problem_texts_follow_accept_language(client, method, url, body):
    english = client.request(method, url, json=body)
    polish = client.request(
        method, url, json=body, headers={"Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5"}
    )

    assert (
        english.headers["content-language"],
        polish.headers["content-language"],
    ) == (
        "en",
        "pl",
    )
    assert english.headers["vary"] == polish.headers["vary"] == "Accept-Language"
    en, pl = english.json(), polish.json()
    assert (en["title"], pl["title"]) == (
        _registry()[en["code"]]["title_en"],
        _registry()[en["code"]]["title_pl"],
    )
    assert en["detail"] != pl["detail"]
    texts = {"title", "detail", "hint", "errors"}
    assert {k: v for k, v in en.items() if k not in texts} == {
        k: v for k, v in pl.items() if k not in texts
    }
    assert [(e["pointer"], e["type"]) for e in en.get("errors", [])] == [
        (e["pointer"], e["type"]) for e in pl.get("errors", [])
    ]


@pytest.mark.parametrize(
    ("header", "lang"),
    [
        ("en;q=0.5, pl;q=0.9", "pl"),
        ("pl;q=0.4, de;q=0.8", "en"),
        ("pl;q=0, en", "en"),
        ("PL", "pl"),
        ("pl;q=nonsense, en;q=0.1", "en"),
    ],
)
def test_problem_language_is_the_preferred_of_accept_language(client, header, lang):
    response = client.get("/api/v1/nothing", headers={"Accept-Language": header})

    assert response.headers["content-language"] == lang


def test_document_answer_is_the_english_envelope(client):
    response = client.get(
        "/api/v1/sheet/parse",
        params={"sheet": SHEET},
        headers={"Accept-Language": "pl"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-language"] == "en"
    envelope = response.json()
    assert (envelope["schema"], envelope["command"], envelope["check"]) == (
        "kartograf-result/1",
        "sheet parse",
        False,
    )


def test_validation_error_points_into_the_query(client):
    response = client.get("/api/v1/sheet/parse")

    assert response.status_code == 400
    errors = response.json()["errors"]
    assert [(e["pointer"], e["type"]) for e in errors] == [
        ("/query/sheet", "invalid_input")
    ]


def test_validation_error_points_into_the_body(client, fake_check):
    response = client.post(CHECK, json={"product": "nmt", "resolution": "1m"})

    assert response.status_code == 400
    problem = response.json()
    pointers = [error["pointer"] for error in problem["errors"]]
    assert pointers == ["/body/sheet", "/body/bbox", "/body/geometry"]
    assert {error["message"] for error in problem["errors"]} == {problem["detail"]}
    assert fake_check.calls == []


# --- the options of a query and of a body --------------------------------------


def test_query_bbox_joined_by_commas_is_four_numbers(client):
    response = client.get("/api/v1/sheet/find", params=BBOX_QUERY)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["request"]["bbox"] == [565000.0, 242000.0, 566000.0, 243000.0]
    assert result["count"] > 0


def test_query_name_given_twice_is_validation_error(client):
    response = client.get(f"/api/v1/sheet/parse?sheet={SHEET}&sheet=N-34-130-D")

    assert response.status_code == 400
    problem = response.json()
    assert problem["code"] == "validation_error"
    assert [error["pointer"] for error in problem["errors"]] == ["/query/sheet"]


@pytest.mark.parametrize(
    ("url", "name"),
    [
        pytest.param("/api/v1/commands/format?command=x", "command", id="option"),
        pytest.param("/api/v1/commands/format?check=true", "check", id="check_no_plan"),
        pytest.param(f"{CHECK}&product=nmt", "product", id="data_command"),
        pytest.param(f"{DOWNLOAD}?check=maybe", "check", id="check_no_switch"),
    ],
)
def test_post_query_other_than_check_is_validation_error(client, fake_check, url, name):
    response = client.post(url, json=OPTIONS)

    assert response.status_code == 400
    problem = response.json()
    assert (problem["code"], problem["details"]["option"]) == (
        "validation_error",
        name,
    )
    assert [error["pointer"] for error in problem["errors"]] == [f"/query/{name}"]
    assert fake_check.calls == []


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"{", id="not_json"),
        pytest.param(b"[1, 2]", id="array"),
        pytest.param(b'"text"', id="string"),
    ],
)
def test_post_body_not_a_json_object_is_validation_error(client, content):
    response = client.post(
        "/api/v1/commands/format",
        content=content,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"


def test_post_body_over_the_limit_is_body_too_large(client):
    body = b" " * (BODY_MAX_BYTES + 1)

    declared = client.post(SCRIPT, content=body)
    streamed = client.post(SCRIPT, content=iter([body[:1024], body[1024:]]))

    assert [declared.status_code, streamed.status_code] == [400, 400]
    assert {r.json()["details"]["reason"] for r in (declared, streamed)} == {
        "body_too_large"
    }


def test_post_body_at_the_limit_is_read(client):
    text = json.dumps({"command": "sheet parse", "options": {"sheet": SHEET}})
    body = text.encode("ascii").ljust(BODY_MAX_BYTES)

    response = client.post("/api/v1/commands/format", content=body)

    assert response.status_code == 200
    assert response.json()["command"] == "commands format"


# --- the plan of a data command ------------------------------------------------


@pytest.mark.parametrize(
    ("url", "body"),
    [
        pytest.param(CHECK, OPTIONS, id="query"),
        pytest.param(DOWNLOAD, {**OPTIONS, "check": True}, id="body"),
    ],
)
def test_data_command_check_answers_the_detached_plan(client, fake_check, url, body):
    response = client.post(url, json=body)

    assert response.status_code == 200
    envelope = response.json()
    assert (envelope["command"], envelope["check"]) == ("elevation download", True)
    assert envelope["result"]["schema"] == "kartograf-plan/1"
    assert fake_check.calls == [
        ("elevation download", OPTIONS, True, _state(client).cache)
    ]


@pytest.mark.parametrize(
    ("units", "status"),
    [
        pytest.param(("A", "B"), 200, id="at_the_bound"),
        pytest.param(("A", "B", "A", "B"), 200, id="distinct_units"),
        pytest.param(("A", "B", "C"), 400, id="over_the_bound"),
    ],
)
def test_plan_units_are_bounded_by_plan_max_units(
    open_server, fake_check, units, status
):
    client = open_server({"plan_max_units": 2})
    fake_check.units = units

    response = client.post(CHECK, json=OPTIONS)

    assert response.status_code == status
    if status == 400:
        problem = response.json()
        assert (problem["code"], problem["details"]["reason"]) == (
            "validation_error",
            "too_many_units",
        )
        assert problem["details"]["allowed"] == ["2"]


def test_direct_script_of_a_line_is_bounded_by_plan_max_units(open_server, fake_check):
    client = open_server({"plan_max_units": 1})
    fake_check.units = ("A", "B")

    response = client.post(
        SCRIPT, json={"shell": "bash", "command": LINE, "direct": True}
    )

    assert response.status_code == 400
    assert response.json()["details"]["reason"] == "too_many_units"


# --- the limits ------------------------------------------------------------------


def test_plan_limit_refuses_the_next_plan_until_the_window_ends(
    open_server, fake_check
):
    clock = Clock()
    client = open_server({"plan_limit": 2, "plan_window": 600}, clock=clock)
    client.post(CHECK, json=OPTIONS)
    clock.now += 100
    client.post(CHECK, json=OPTIONS)

    refused = client.post(CHECK, json=OPTIONS)
    clock.now += 500
    again = client.post(CHECK, json=OPTIONS)

    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "500"
    problem = refused.json()
    assert (problem["code"], problem["details"]["reason"]) == (
        "rate_limited",
        "plan_limit",
    )
    assert again.status_code == 200
    assert len(fake_check.calls) == 3


def test_plan_limit_a_refused_or_invalid_request_costs_no_plan(open_server, fake_check):
    client = open_server({"plan_limit": 1})
    statuses = [
        client.post(CHECK, json={"product": "nmt"}).status_code,
        client.post(DOWNLOAD, json=OPTIONS).status_code,
        client.post(CHECK, json={**OPTIONS, "workers": 2}).status_code,
        client.post(CHECK, json={**OPTIONS, "root": "/srv"}).status_code,
        client.post(f"{CHECK}&x=1", json=OPTIONS).status_code,
    ]

    first = client.post(CHECK, json=OPTIONS)
    second = client.post(CHECK, json=OPTIONS)

    assert statuses == [400, 403, 403, 403, 400]
    assert (first.status_code, second.status_code) == (200, 429)


def test_plan_limit_counts_a_direct_script_of_a_line(open_server, fake_check):
    client = open_server({"plan_limit": 1})
    client.post(CHECK, json=OPTIONS)

    response = client.post(
        SCRIPT, json={"shell": "bash", "command": LINE, "direct": True}
    )

    assert response.status_code == 429
    assert response.json()["details"]["reason"] == "plan_limit"


def test_plan_limit_does_not_count_a_script_that_plans_nothing(
    open_server, fake_check, released
):
    client = open_server({"plan_limit": 1})
    plan = json.loads(_plan((SHEET,)).to_json())
    scripts = [
        client.post(SCRIPT, json={"shell": "bash", "plan": plan, "direct": True}),
        client.post(SCRIPT, json={"shell": "bash", "command": LINE}),
    ]

    response = client.post(CHECK, json=OPTIONS)

    assert [r.status_code for r in scripts] == [200, 200]
    assert response.status_code == 200


def test_request_limit_refuses_a_client_over_it(open_server):
    client = open_server({"request_limit": 2, "request_window": 60})
    first = {"X-Forwarded-For": VISITOR}
    other = {"X-Forwarded-For": "198.51.100.99"}
    client.get("/api/v1/server", headers=first)
    client.get("/api/v1/nothing", headers=first)

    refused = client.get("/api/v1/server", headers=first)
    served = client.get("/api/v1/server", headers=other)

    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "60"
    problem = refused.json()
    assert (problem["code"], problem["details"]["reason"]) == (
        "rate_limited",
        "request_limit",
    )
    assert served.status_code == 200


def test_request_limit_ignores_forwarded_for_of_an_untrusted_peer(open_server):
    client = open_server({"request_limit": 2}, peer="203.0.113.50")

    statuses = [
        client.get("/api/v1/server", headers={"X-Forwarded-For": f"198.51.100.{n}"})
        for n in range(3)
    ]

    assert [r.status_code for r in statuses] == [200, 200, 429]


def test_request_limit_counts_only_the_api(open_server):
    client = open_server({"request_limit": 1})
    client.get("/favicon.ico")
    client.get("/index.html")

    response = client.get("/api/v1/server")

    assert response.status_code == 200


# --- the daily totals ------------------------------------------------------------


def test_stats_count_visitors_and_analyses(client, fake_check, released):
    client.get("/api/v1/server", headers={"User-Agent": "Firefox/130.0"})
    client.get("/api/v1/server", headers={"User-Agent": "Firefox/130.0"})
    client.get("/api/v1/server", headers={"User-Agent": "curl/8.5.0"})
    client.post(CHECK, json=OPTIONS)
    client.post(SCRIPT, json={"shell": "bash", "command": LINE})
    client.post(DOWNLOAD, json=OPTIONS)  # refused: no analysis
    client.get("/api/v1/sheet/parse", params={"sheet": SHEET})  # no analysis

    snapshot = _state(client).stats.snapshot()  # type: ignore[union-attr]

    assert (snapshot["visitors"], snapshot["analyses_run"]) == (3, 2)


def test_stats_are_written_at_shutdown(settings, fake_check):
    with TestClient(create_app(settings), client=(PROXY, 50000)) as client:
        client.post(CHECK, json=OPTIONS)

    line = json.loads(settings.stats_path.read_text(encoding="utf-8"))
    assert (line["visitors"], line["analyses_run"]) == (1, 1)


# --- script generate ---------------------------------------------------------------


def test_script_generate_kartograf_script_without_network(client, fake_check, released):
    response = client.post(SCRIPT, json={"shell": "bash", "command": LINE})

    assert response.status_code == 200
    result = response.json()["result"]
    assert (result["schema"], result["kind"]) == ("kartograf-script/1", "kartograf")
    assert result["text"].startswith("#!/usr/bin/env bash")
    assert fake_check.calls == []


def test_script_generate_direct_of_a_plan_document_without_network(client, fake_check):
    plan = json.loads(_plan((SHEET,)).to_json())

    response = client.post(SCRIPT, json={"shell": "bash", "plan": plan, "direct": True})

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["kind"] == "direct"
    assert [file["url"] for file in result["files"]] == [
        f"https://example.test/nmt/{SHEET}.asc"
    ]
    assert fake_check.calls == []


def test_script_generate_direct_of_a_line_plans_detached_with_the_server_cache(
    client, fake_check
):
    response = client.post(
        SCRIPT, json={"shell": "bash", "command": LINE, "direct": True}
    )

    assert response.status_code == 200
    assert response.json()["result"]["kind"] == "direct"
    assert [(c[0], c[2], c[3]) for c in fake_check.calls] == [
        ("elevation download", True, _state(client).cache)
    ]


# --- a failure of the server -----------------------------------------------------


def test_unexpected_exception_is_internal_error_without_its_text(
    open_server, monkeypatch
):
    def broken(*args, **kwargs):
        raise RuntimeError("boom at /srv/secret/path")

    monkeypatch.setattr("kartograf.server.calls.check_command", broken)
    client = open_server(raise_server_exceptions=False)

    english = client.post(CHECK, json=OPTIONS)
    polish = client.post(CHECK, json=OPTIONS, headers={"Accept-Language": "pl"})

    assert (english.status_code, polish.status_code) == (500, 500)
    assert english.headers["content-type"] == PROBLEM
    assert [english.json()["detail"], polish.json()["detail"]] == [
        message("server.internal_error", "en"),
        message("server.internal_error", "pl"),
    ]
    assert english.json()["code"] == "internal_error"
    for response in (english, polish):
        assert "boom" not in response.text
        assert "secret" not in response.text
        assert "RuntimeError" not in response.text


# --- the access log --------------------------------------------------------------


def test_access_log_has_a_record_per_request_without_the_client(open_server, tmp_path):
    directory = tmp_path / "logs"
    log = ServerLog("kartograf", "0.9.0", directory, stream=io.StringIO())
    log.start()
    try:
        client = open_server(log=log)
        forwarded = {"X-Forwarded-For": VISITOR}
        client.get("/api/v1/server", headers=forwarded)
        client.get("/api/v1/nothing", headers=forwarded)
        client.post(DOWNLOAD, json=OPTIONS, headers=forwarded)
    finally:
        log.stop()

    records = [
        json.loads(line)
        for path in sorted(directory.glob("access-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert [(r["method"], r["path"], r["status"]) for r in records] == [
        ("GET", "/api/v1/server", 200),
        ("GET", "/api/v1/nothing", 404),
        ("POST", DOWNLOAD, 403),
    ]
    written = "".join(p.read_text(encoding="utf-8") for p in directory.iterdir())
    assert VISITOR not in written
    assert PROXY not in written
