"""
Fixtures of the GUI's browser tests (ADR-063 decision 9): Playwright and Chromium.

Every test of this directory is marked ``e2e`` and is skipped when Playwright or
Chromium is missing (``uv run --no-sync playwright install chromium``). The page is
served by the app of ``kartograf gui serve`` (``create_gui_app``) under uvicorn in a
thread, on a free port of 127.0.0.1, with no base map, so no request of the page leaves
the machine; the server's files are in a temporary directory and its
``kartograf.__version__`` is the release ``RELEASE``, so the real server writes the
Kartograf script, which pins a released tag.

The real server answers every request but the plans, which query the sources'
indexes: ``answer_plan(page, name)`` answers them with a recorded answer
(``recorded.py``).

``open_page`` opens the page in a fresh browser context with the language, the theme
and the size chosen, and fails the test at its end on a console error, a page error or
a violation of the Content-Security-Policy, except the console errors a test causes on
purpose.
"""

import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Self

import pytest

import kartograf
from tests.e2e.recorded import RELEASE, recorded

HERE = Path(__file__).resolve().parent

_CSP_LISTENER = """
document.addEventListener("securitypolicyviolation", (event) => {
  (window.__cspViolations = window.__cspViolations || []).push(
    `${event.violatedDirective} ${event.blockedURI}`);
});
"""


def pytest_collection_modifyitems(config, items):
    for item in items:
        if HERE in Path(str(item.fspath)).resolve().parents:
            item.add_marker(pytest.mark.e2e)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _Server:
    """An ASGI application under uvicorn in a thread."""

    def __init__(self, app: Any, port: int) -> None:
        import uvicorn

        self.url = f"http://127.0.0.1:{port}/"
        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> Self:
        self.thread.start()
        deadline = time.monotonic() + 30
        while not self.server.started:
            if time.monotonic() > deadline or not self.thread.is_alive():
                raise RuntimeError("the GUI server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=30)


@pytest.fixture(scope="package")
def gui_url(tmp_path_factory) -> Iterator[str]:
    """The page and the API of ``kartograf gui serve``: no base map, not public."""
    from kartograf.gui.app import create_gui_app
    from kartograf.gui.site import GuiSite
    from kartograf.server.settings import ServerSettings

    work = tmp_path_factory.mktemp("gui")
    settings = ServerSettings(
        index_max_age=86400,
        plan_limit=1000,
        plan_window=600,
        plan_max_units=500,
        request_limit=100_000,
        request_window=60,
        trusted_proxies=("127.0.0.1",),
        cache_path=work / "metadata.db",
        log_dir=work / "logs",
        stats_path=work / "stats.jsonl",
    )
    app = create_gui_app(settings, GuiSite(basemaps=(), apps={}, terms=None))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(kartograf, "__version__", RELEASE)
        with _Server(app, _free_port()) as server:
            yield server.url


@pytest.fixture(scope="package")
def browser() -> Iterator[Any]:
    """
    Chromium of Playwright, headless; the tests are skipped without it.

    Package-scoped: Playwright's sync API keeps an event loop running in the main
    thread, so it stops after this directory's tests, before tests that call
    ``asyncio.run``.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - the dev group has it
        pytest.skip("Playwright is not installed")
    manager = sync_playwright().start()
    try:
        chromium = manager.chromium.launch()
    except Exception as exc:  # noqa: BLE001 - any launch failure means no browser
        manager.stop()
        pytest.skip(f"Chromium does not start: {exc}")
    yield chromium
    chromium.close()
    manager.stop()


class PageProblems(AssertionError):
    """Console errors, page errors or CSP violations of a page."""


@pytest.fixture
def open_page(browser, gui_url) -> Iterator[Callable[..., Any]]:
    """
    Open the page in a fresh context; fail on its console errors at the end.

    ``open_page(*, lang="pl", theme="light", width=1440, height=900, expected=())``
    returns the Playwright ``Page`` once the form of the command is drawn; ``expected``
    are parts of the console errors the test causes on purpose (the status of a refused
    plan).
    """
    opened: list[tuple[Any, Any, list[str], tuple[str, ...]]] = []

    def opener(
        *,
        lang: str = "pl",
        theme: str = "light",
        width: int = 1440,
        height: int = 900,
        expected: tuple[str, ...] = (),
    ) -> Any:
        context = browser.new_context(
            viewport={"width": width, "height": height}, accept_downloads=True
        )
        context.add_init_script(
            f"localStorage.setItem('nogat-theme', {json.dumps(theme)});"
            f"localStorage.setItem('kartograf-lang', {json.dumps(lang)});"
            + _CSP_LISTENER
        )
        page = context.new_page()
        problems: list[str] = []

        def console(message: Any) -> None:
            if message.type == "error":
                problems.append(f"console error: {message.text} ({message.location})")

        page.on("console", console)
        page.on("pageerror", lambda error: problems.append(f"page error: {error}"))
        opened.append((context, page, problems, expected))
        page.goto(gui_url)
        page.locator("nogat-command-form .nogat-command-form").wait_for(timeout=15_000)
        return page

    yield opener
    found: list[str] = []
    for context, page, problems, expected in opened:
        if not page.is_closed():
            violations = page.evaluate("window.__cspViolations || []")
            found += [f"CSP violation: {item}" for item in violations]
        found += [
            item for item in problems if not any(part in item for part in expected)
        ]
        context.close()
    if found:
        raise PageProblems("\n".join(found))


@pytest.fixture
def answer_plan() -> Callable[[Any, str], list[dict[str, Any]]]:
    """
    Answer the plans of a page with a recorded answer: ``answer_plan(page, name)``.

    Returns the list the bodies of the plans the page asks for are appended to.
    """

    def install(page: Any, name: str) -> list[dict[str, Any]]:
        asked: list[dict[str, Any]] = []
        doc = recorded(name)
        status = (
            200 if doc.get("schema") == "kartograf-result/1" else int(doc["status"])
        )
        kind = "application/json" if status == 200 else "application/problem+json"

        def plan(route: Any) -> None:
            asked.append(route.request.post_data_json)
            route.fulfill(status=status, body=json.dumps(doc), content_type=kind)

        page.route("**/api/v1/*/download?check=true", plan)
        return asked

    return install
