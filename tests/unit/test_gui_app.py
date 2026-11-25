"""``kartograf gui serve``: the page beside the API (ADR-063 decision 9).

``create_gui_app`` over Starlette's ``TestClient`` with its files in ``tmp_path``: the
page and its Content-Security-Policy from the base maps offered (DEV-15.15), the
settings of the page, the regulamin of a public GUI only (DEV-15.7), the GUI in
``nogat-server/1``, the request limit and the page views of its HTML pages (DEV-15.9,
DEV-15.11); ``GuiSite.from_config`` refusing a base map setting; and ``serve_gui``
serving the real application under uvicorn until a signal stops it.
"""

import signal
import threading
import urllib.request
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kartograf.gui
from kartograf.exceptions import ConfigError
from kartograf.gui import serve_gui
from kartograf.gui.app import create_gui_app
from kartograf.gui.basemaps import catalogue
from kartograf.gui.site import GuiSite
from kartograf.server.settings import ServerSettings

OPERATOR = """
[nogat.gui]
kartograf = "https://kartograf.example/"
obserwator = "https://obserwator.example/"

[nogat.operator]
name = "Operator <Test>"
email = "operator@example.org"
terms_effective = 2026-11-20
processor = "Cloudflare, Inc."
processor_transfer = ""
processor_cookie = ""
mail_provider = "Poczta"
mail_transfer = ""
"""


def _settings(tmp_path: Path, *, request_limit: int = 300) -> ServerSettings:
    return ServerSettings(
        index_max_age=86400,
        plan_limit=20,
        plan_window=600,
        plan_max_units=500,
        request_limit=request_limit,
        request_window=60,
        trusted_proxies=("127.0.0.1",),
        cache_path=tmp_path / "metadata.db",
        log_dir=tmp_path / "logs",
        stats_path=tmp_path / "stats.jsonl",
    )


def _site(*ids: str) -> GuiSite:
    entries = tuple(entry for entry in catalogue() if entry["id"] in ids)
    return GuiSite(basemaps=entries, apps={}, terms=None)


@pytest.fixture
def nogat_toml(tmp_path, monkeypatch):
    """Write ``nogat.toml`` (``NOGAT_CONFIG``) with the given text."""

    def write(text: str) -> None:
        path = tmp_path / "nogat.toml"
        path.write_text(text, encoding="utf-8")
        monkeypatch.setenv("NOGAT_CONFIG", str(path))

    for name in ("KARTOGRAF_BASEMAPS", "NOGAT_BASEMAPS"):
        monkeypatch.delenv(name, raising=False)
    return write


def test_gui_app_csp_names_only_the_origins_of_the_basemaps_offered(tmp_path):
    app = create_gui_app(_settings(tmp_path), _site("openfreemap"))

    with TestClient(app) as client:
        page = client.get("/")

    csp = page.headers["content-security-policy"]
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["cache-control"] == "no-cache"
    assert "img-src 'self' data: blob: https://tiles.openfreemap.org;" in csp
    assert "connect-src 'self' https://tiles.openfreemap.org;" in csp
    assert "geoportal" not in csp
    assert "script-src 'self';" in csp and "worker-src 'self';" in csp
    assert "cross-origin-opener-policy" not in page.headers  # the app menu reuses tabs


def test_gui_app_without_operator_serves_no_regulamin(tmp_path):
    app = create_gui_app(_settings(tmp_path), _site("openfreemap", "gugik-ortho"))

    with TestClient(app) as client:
        settings = client.get("/site.json").json()
        terms = client.get("/regulamin.html")
        service = client.get("/api/v1/server").json()["services"][0]

    assert [entry["id"] for entry in settings["basemaps"]] == [
        "openfreemap",
        "gugik-ortho",
    ]
    assert (settings["apps"], settings["terms"]) == ({}, None)
    assert terms.status_code == 404
    assert service["gui"] == "/"
    assert "terms" not in service


def test_gui_app_public_gui_serves_its_filled_regulamin(tmp_path, nogat_toml):
    nogat_toml(OPERATOR)
    site = GuiSite.from_config()
    app = create_gui_app(_settings(tmp_path), site)

    with TestClient(app) as client:
        settings = client.get("/site.json").json()
        page = client.get("/regulamin.html")
        service = client.get("/api/v1/server").json()["services"][0]

    assert settings["terms"] == "regulamin.html"
    assert settings["apps"]["obserwator"] == "https://obserwator.example/"
    assert page.status_code == 200
    assert "Operator &lt;Test&gt;" in page.text
    assert "{{" not in page.text and "<!-- block:" not in page.text
    assert "geoportal.gov.pl" in page.text  # the block gugik: data and base maps
    assert service["gui"] == "https://kartograf.example/"
    assert service["terms"] == {
        "url": "https://kartograf.example/regulamin.html",
        "version": "1.1",
    }


def test_gui_app_counts_its_pages_not_its_files_and_refuses_a_page_over_the_limit(
    tmp_path,
):
    app = create_gui_app(_settings(tmp_path, request_limit=2), _site("openfreemap"))

    with TestClient(app) as client:
        first, second = client.get("/"), client.get("/index.html")
        script = client.get("/src/main.js")
        refused = client.get("/", headers={"Accept-Language": "pl"})
        views = app.state.server.stats.snapshot()["page_views"]

    assert (first.status_code, second.status_code, script.status_code) == (200,) * 3
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) > 0
    assert refused.headers["content-type"].startswith("text/html")
    assert "Zbyt wiele zadan" in refused.text
    assert "content-security-policy" in refused.headers
    assert views == 2


def test_gui_site_refuses_a_basemap_the_catalogue_does_not_have(
    nogat_toml, monkeypatch
):
    nogat_toml("")
    monkeypatch.setenv("KARTOGRAF_BASEMAPS", "openfreemap,szkic")

    with pytest.raises(ConfigError) as raised:
        GuiSite.from_config()

    assert (raised.value.option, raised.value.value) == ("KARTOGRAF_BASEMAPS", "szkic")


def test_gui_site_refuses_basemaps_of_nogat_toml_that_are_no_list(nogat_toml):
    nogat_toml('[nogat]\nbasemaps = "openfreemap"\n')

    with pytest.raises(ConfigError) as raised:
        GuiSite.from_config()

    assert raised.value.option == "[nogat] basemaps"


def test_serve_gui_serves_the_page_until_a_signal_stops_it(
    tmp_path, nogat_toml, monkeypatch
):
    nogat_toml("")
    for key in ("STATE_DIR", "DATA_DIR", "CACHE_DIR"):
        monkeypatch.setenv(f"KARTOGRAF_{key}", str(tmp_path / key.lower()))
    fetched: list[tuple[str, int, str]] = []

    def opened(url: str) -> None:
        try:
            with urllib.request.urlopen(url, timeout=10) as answer:
                csp = answer.headers["Content-Security-Policy"]
                fetched.append((url, answer.status, csp))
        finally:
            signal.raise_signal(signal.SIGINT)

    monkeypatch.setattr(kartograf.gui, "_open_page", opened)
    assert threading.current_thread() is threading.main_thread()

    served = serve_gui(host="127.0.0.1", port=0)

    assert len(fetched) == 1
    url, status, csp = fetched[0]
    assert (served.url, status) == (url, 200)
    assert "default-src 'self'" in csp
    assert served.stopped_at >= served.started_at
