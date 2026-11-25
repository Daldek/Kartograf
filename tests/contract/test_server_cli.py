"""``kartograf server``: its options, its failures to start and its logs (ADR-063
decision 7, AGI-3.3, DEV-12.4).

A failure to start ends with the exit code of its registry code and the
``kartograf-error/1`` document as the last line of stderr; a server that starts and
stops writes the lifecycle records ``start`` and ``stop`` in
``<state_dir>/kartograf/logs``. uvicorn never serves here: its ``Server.run``
returns at once.
"""

import json
import socket

import pytest
import uvicorn

from kartograf import config
from kartograf.cli.commands import main
from tests.support.errors import error_document


def _run(capsys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_server_help_names_host_and_port(capsys):
    with pytest.raises(SystemExit) as exit_:
        main(["server", "--help"])

    out = capsys.readouterr().out
    assert exit_.value.code == 0
    assert "--host" in out
    assert "--port" in out


@pytest.mark.parametrize("port", ["99999", "-1", "http"])
def test_server_invalid_port_exits_2_with_the_error_document(capsys, port):
    code, out, err = _run(capsys, ["server", "--port", port])

    assert code == 2
    assert out == ""
    document = error_document(err)
    assert (document["code"], document["exit_code"]) == ("validation_error", 2)


def test_server_port_in_use_exits_4_port_in_use(capsys):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]

        code, out, err = _run(capsys, ["server", "--port", str(port)])

    assert (code, out) == (4, "")
    document = error_document(err)
    assert (document["code"], document["details"]["reason"]) == (
        "conflict",
        "port_in_use",
    )


def test_server_without_its_extra_exits_6_missing_dependency(capsys, monkeypatch):
    def import_module(name: str, package: str | None = None):
        raise ImportError(f"No module named '{name}'")

    monkeypatch.setattr(
        "kartograf.server.serving.importlib.import_module", import_module
    )

    code, out, err = _run(capsys, ["server", "--port", "0"])

    assert (code, out) == (6, "")
    document = error_document(err)
    assert (document["code"], document["details"]["extra"]) == (
        "missing_dependency",
        "server",
    )


def test_server_start_and_stop_are_lifecycle_records(capsys, monkeypatch):
    served = []

    def run(self, sockets=None):
        served.append(sockets[0].getsockname()[1])

    monkeypatch.setattr(uvicorn.Server, "run", run)

    code, _, err = _run(capsys, ["server", "--port", "0"])

    assert code == 0
    directory = config.state_dir() / "kartograf" / "logs"
    records = [
        json.loads(line)
        for path in sorted(directory.glob("lifecycle-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event"] for record in records] == ["start", "stop"]
    (port,) = served
    settings = records[0]["settings"]
    assert settings["url"] == f"http://127.0.0.1:{port}/"
    assert settings["plan_limit"] == config.limit("plan_limit")
    assert [json.loads(line)["event"] for line in err.splitlines()] == [
        "start",
        "stop",
    ]
