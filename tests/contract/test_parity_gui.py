"""CLI and public API serve the same GUI (``gui serve``, ADR-063 decision 9): the flags
reach ``serve_gui`` as its arguments, so the server is started at the same address
with the same browser choice, and ``--json`` prints the envelope of the library's
``kartograf-gui/1``. No server runs: ``run_app`` of ``kartograf.gui`` is replaced by
a recorder that returns at once, as a stop would."""

from collections.abc import Callable

import pytest

from kartograf import GuiServed, ValidationError, run_command, serve_gui
from kartograf.cli import main
from kartograf.envelope import wrap
from kartograf.server.serving import url_of
from tests.support.errors import error_document


class _Served:
    """``run_app`` that records where it would serve and whether a page opens."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, bool]] = []

    def __call__(
        self,
        build: Callable[..., object],
        *,
        host: str,
        port: int,
        ready: Callable[[str], None] | None = None,
    ) -> str:
        self.calls.append((host, port, ready is not None))
        return url_of(host, port)


@pytest.fixture
def served(monkeypatch, frozen_clock) -> _Served:
    recorder = _Served()
    monkeypatch.setattr("kartograf.gui.run_app", recorder)
    return recorder


@pytest.mark.parametrize(
    ("argv", "options"),
    [
        ([], {}),
        (
            ["--host", "0.0.0.0", "--port", "8080", "--no-browser"],
            {"host": "0.0.0.0", "port": 8080, "no_browser": True},
        ),
        (["--port", "0"], {"port": 0}),
    ],
    ids=["defaults", "every-flag", "free-port"],
)
def test_gui_serve_flags_are_the_arguments_of_serve_gui(argv, options, served, capsys):
    code = main(["gui", "serve", *argv, "--json"])
    printed = capsys.readouterr().out
    library = serve_gui(**options)
    layer = run_command("gui serve", options)

    cli_call, api_call, layer_call = served.calls
    assert code == 0
    assert cli_call == api_call == layer_call
    assert printed == wrap("gui serve", library).to_json() == layer.to_json()
    assert isinstance(library, GuiServed)


def test_gui_serve_defaults_are_this_computer_port_8065_and_a_browser(served, capsys):
    main(["gui", "serve"])

    assert served.calls == [("127.0.0.1", 8065, True)]


def test_gui_serve_text_mode_prints_nothing_on_stdout(served, capsys):
    code = main(["gui", "serve", "--no-browser"])

    assert (code, capsys.readouterr().out) == (0, "")
    assert served.calls == [("127.0.0.1", 8065, False)]


def test_gui_serve_port_out_of_range_is_refused_before_serving(served, capsys):
    code = main(["gui", "serve", "--port", "65536", "--json"])
    captured = capsys.readouterr()
    with pytest.raises(ValidationError) as caught:
        serve_gui(port=65536)

    assert (code, captured.out) == (2, "")
    assert error_document(captured.err)["code"] == "validation_error"
    assert caught.value.option == "port"
    assert served.calls == []
