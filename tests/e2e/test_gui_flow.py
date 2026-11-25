"""
The page of ``kartograf gui serve`` in Chromium: the main flow of the plan's step K5.

A rectangle drawn on the map, or a sheet picked among the sheets of the view, becomes
the area of the form; „Sprawdź plan” shows the plan (a recorded answer of the server) as
a table and as the footprints of its units on the map; the command line, the Kartograf
script and the direct script of the plan then come from the real server, to copy and to
save. A refused plan and an option the server refuses are said where they belong, an
edit after the check takes the outputs away until it is undone, and a pasted line of
the other command switches the form.
"""

import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import expect

from tests.e2e.recorded import RELEASE, recorded

WARSAW = "{center: [21.01, 52.205], zoom: 13}"
"""A view of the recorded plans' area, near enough to show the sheets of the view."""
SHEET = "N-34-139-A-c-1-3"
"""A 1:10 000 PL-1992 sheet of that view, its centre at `SHEET_CENTRE` (lon, lat)."""
SHEET_CENTRE = [21.015625, 52.21875]


def _until(page, expression: str, timeout: float = 10) -> Any:
    """Evaluate `expression` until it is true (no wait_for_function: the page's CSP)."""
    deadline = time.monotonic() + timeout
    while not (value := page.evaluate(expression)):
        assert time.monotonic() < deadline, f"not true in {timeout} s: {expression}"
        page.wait_for_timeout(100)
    return value


def _draw_rectangle(page) -> None:
    page.evaluate(f"window.kartograf.view.map.jumpTo({WARSAW})")
    page.locator("#draw").click()
    box = page.locator("#map").bounding_box()
    x, y = box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.4
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 120, y + 90, steps=6)
    page.mouse.up()


def _options(page) -> dict[str, Any]:
    return page.evaluate("window.kartograf.data.form.options")


def _product(page, product: str) -> None:
    field = page.locator("nogat-command-form [data-option=product]")
    field.get_by_label(product, exact=True).check()


def _check(page) -> None:
    page.get_by_role("button", name="Sprawdź plan").click()


def _saved(page) -> tuple[str, str]:
    with page.expect_download() as info:
        page.locator("#output-save").click()
    download = info.value
    return download.suggested_filename, Path(download.path()).read_text(
        encoding="utf-8"
    )


def test_gui_rectangle_plan_and_its_three_outputs(open_page, answer_plan):
    page = open_page()
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    asked = answer_plan(page, "plan_nmt.json")
    form = page.locator("nogat-command-form")

    _draw_rectangle(page)
    options = _options(page)
    form.locator("fieldset[data-group=target]").get_by_role(
        "radio", name="output_dir"
    ).check()
    form.locator("[data-option=output_dir] input").fill("./nmt")
    _check(page)

    # The rectangle is the form's area in degrees; the plan gets the call, no target
    assert options["bbox_crs"] == "EPSG:4326"
    west, south, east, north = options["bbox"]
    assert 20.9 < west < east < 21.2 and 52.1 < south < north < 52.3
    expect(page.locator("#plan-body")).to_be_visible()
    assert asked == [options]
    rows = page.locator("#plan-table tbody tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("N-34-139-A-c-1-3.asc")
    expect(rows.nth(0)).to_contain_text("GUGiK, PL-PGiK-40a")
    expect(rows.nth(0)).to_contain_text("do pobrania")
    expect(rows.nth(1)).to_contain_text("N-34-139-A-c-3-1.asc")
    footprints = page.locator("#plan-footprints")
    expect(footprints).to_have_text("Zarysy na mapie: 2 z 2 jednostek.")
    expect(page.locator("#plan-sources")).to_contain_text("Glowny Urzad Geodezji")
    # (a) the command line, copied and saved
    text = page.locator("#output-text")
    expect(text).to_contain_text("kartograf elevation download --product nmt")
    expect(text).to_contain_text("--bbox-crs EPSG:4326")
    expect(text).to_contain_text("-o ./nmt")
    page.get_by_role("tabpanel").get_by_role("button", name="Kopiuj").click()
    expect(page.locator("#output-status")).to_have_text("Skopiowano do schowka.")
    line = page.evaluate("navigator.clipboard.readText()")
    assert line == text.inner_text()
    assert _saved(page) == ("kartograf.txt", f"{line}\n")
    # (b) the Kartograf script of the line, in bash then in PowerShell
    page.get_by_role("tab", name="Skrypt Kartografa").click()
    pin = f"kartograf @ git+https://github.com/Daldek/Kartograf.git@v{RELEASE}"
    expect(text).to_contain_text("uv tool install")
    expect(text).to_contain_text(pin)
    expect(text).to_contain_text(line)
    page.get_by_role("button", name="PowerShell", exact=True).click()
    expect(text).to_contain_text("$ErrorActionPreference = 'Stop'")
    name, saved = _saved(page)
    assert name == "kartograf.ps1" and pin in saved
    # (c) the direct script of the plan checked: the server does not plan again
    with page.expect_request(
        lambda request: (
            request.url.endswith("/api/v1/script/generate")
            and (request.post_data_json or {}).get("direct") is True
        )
    ) as sent:
        page.get_by_role("tab", name="Skrypt bezpośredni").click()
    assert sent.value.post_data_json == {
        "shell": "powershell",
        "plan": recorded("plan_nmt.json")["result"],
        "direct": True,
        "target": "./nmt",
    }
    expect(text).to_contain_text("Invoke-WebRequest")
    expect(text).to_contain_text("83233_1744697_N-34-139-A-c-1-3.asc")
    expect(page.locator("#output-note")).to_contain_text("Plików do pobrania: 2.")
    page.get_by_role("button", name="bash", exact=True).click()
    expect(text).to_contain_text("target=./nmt")
    name, saved = _saved(page)
    assert name == "kartograf.sh" and saved.startswith("#!/usr/bin/env bash\n")


def test_gui_plan_of_laz_tiles_draws_their_footprints_in_english(
    open_page, answer_plan
):
    page = open_page(lang="en", theme="dark")
    answer_plan(page, "plan_laz.json")
    _product(page, "laz")

    _draw_rectangle(page)
    page.get_by_role("button", name="Check the plan").click()

    rows = page.locator("#plan-table tbody tr")
    expect(rows).to_have_count(12)
    footprints = page.locator("#plan-footprints")
    expect(footprints).to_have_text("Footprints on the map: 12 of 12 units.")
    assert page.evaluate("window.kartograf.view.footprints.length") == 12
    row = rows.nth(3)
    row.click()
    expect(row).to_have_attribute("aria-current", "true")
    chosen = page.evaluate(
        "window.kartograf.view.footprints[window.kartograf.view.selected].properties.unit"
    )
    assert chosen == row.get_attribute("data-unit")


def test_gui_sheet_picked_on_the_map_becomes_the_area(open_page):
    page = open_page()
    page.evaluate(f"window.kartograf.view.map.jumpTo({WARSAW})")

    page.get_by_role("button", name="Arkusze widoku").click()
    expect(page.locator("#map-hint")).to_have_text("Kliknij arkusz, aby go wybrać.")
    _until(
        page,
        "window.kartograf.view.map"
        ".queryRenderedFeatures({layers: ['sheets-fill']}).length",
    )
    x, y = page.evaluate(
        "(() => { const map = window.kartograf.view.map;"
        f" const point = map.project({SHEET_CENTRE});"
        " const box = map.getContainer().getBoundingClientRect();"
        " return [box.left + point.x, box.top + point.y]; })()"
    )
    page.mouse.click(x, y)

    expect(page.locator("nogat-command-form [data-option=sheet] input")).to_have_value(
        SHEET
    )
    options = _options(page)
    assert options["sheet"] == SHEET
    assert "bbox" not in options


def test_gui_refused_plan_says_why_and_gives_no_outputs(open_page, answer_plan):
    page = open_page(expected=("status of 404",))
    answer_plan(page, "plan_nmpt.json")
    _product(page, "nmpt")
    _draw_rectangle(page)

    _check(page)

    error = page.locator("#plan-error")
    expect(error).to_contain_text(
        "GUGiK has no data for any of the 2 sheets of the area"
    )
    expect(error).to_contain_text("use --resolution 0.5m")
    expect(page.locator("#plan-body")).to_be_hidden()
    expect(page.locator("#outputs-body")).to_be_hidden()


def test_gui_option_the_server_refuses_stands_under_its_field(open_page):
    page = open_page(expected=("status of 400",))
    resolution = page.locator("nogat-command-form [data-option=resolution]")
    _product(page, "laz")
    one_metre = resolution.locator("option").filter(has_text=re.compile(r"^1m\b"))
    resolution.locator("select").select_option(value=one_metre.get_attribute("value"))
    _draw_rectangle(page)

    _check(page)

    message = resolution.locator(".nogat-command-form-message")
    expect(message).to_contain_text("--resolution nie dotyczy LAZ")
    expect(page.locator("#plan-error")).to_be_visible()


def test_gui_edit_after_the_check_takes_the_outputs_away_until_undone(
    open_page, answer_plan
):
    page = open_page()
    answer_plan(page, "plan_nmt.json")
    _draw_rectangle(page)
    _check(page)
    stale, outputs = page.locator("#plan-stale"), page.locator("#outputs-body")
    expect(outputs).to_be_visible()

    _product(page, "laz")
    expect(stale).to_be_visible()
    expect(outputs).to_be_hidden()
    _product(page, "nmt")

    expect(stale).to_be_hidden()
    expect(outputs).to_be_visible()


def test_gui_pasted_line_of_the_other_command_switches_the_form(open_page):
    page = open_page()
    paste = page.locator("nogat-command-form .nogat-command-form-paste")
    line = (
        f"kartograf imagery download --product orto --country pl --sheet {SHEET} "
        "--sheet-system 1992 -o ./orto"
    )

    paste.locator("input").fill(line)
    paste.get_by_role("button", name="Wczytaj").click()

    imagery = page.locator("input[name=command][value='imagery download']")
    expect(imagery).to_be_checked()
    expect(page.locator("nogat-command-form [data-option=sheet] input")).to_have_value(
        SHEET
    )
    assert _options(page) == {
        "product": "orto",
        "country": "pl",
        "sheet": SHEET,
        "sheet_system": "1992",
        "output_dir": "./orto",
    }
