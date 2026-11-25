"""The copies the page of ``kartograf gui serve`` serves (ADR-063 decision 9, DEV-15.6).

Nogat's kit is copied byte for byte with its manifest ``nogat-kit.json``; ``nogat.json``
records the Nogat commit and the hashes of ``tokens.css`` (two comment lines added) and
the marks; ``vendor/vendor.json`` the hashes of MapLibre GL JS and the glyphs. A copy
edited in place, or a manifest not updated with a new copy, fails here.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "src/kartograf/gui/web"
KIT = WEB / "nogat"
VENDOR = WEB / "vendor"
MANIFEST = json.loads((KIT / "nogat-kit.json").read_text(encoding="utf-8"))
RECORD = json.loads((KIT / "nogat.json").read_text(encoding="utf-8"))
LIBRARIES = json.loads((VENDOR / "vendor.json").read_text(encoding="utf-8"))[
    "libraries"
]
# The kit's files the page loads: the command form, the base maps and their catalogue,
# the sources strip, the app menu and the regulamin (ADR-063 decision 9).
USED = (
    "nogat-command-form.js",
    "nogat-command-form.css",
    "nogat-basemaps.js",
    "nogat-basemaps.css",
    "nogat-basemaps.json",
    "nogat-sources.js",
    "nogat-sources.css",
    "nogat-app-menu.js",
    "nogat-app-menu.css",
    "nogat-terms.html",
    "nogat-terms.css",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("name", sorted(MANIFEST["files"]))
def test_gui_kit_file_is_the_kit_its_manifest_names(name):
    assert _sha256(KIT / name) == MANIFEST["files"][name]


def test_gui_kit_is_version_1_3_with_every_file_the_page_loads():
    assert MANIFEST["version"] == "1.3.0"
    assert set(USED) <= set(MANIFEST["files"])
    beside = {path.name for path in KIT.iterdir() if path.is_file()}
    assert beside == {*MANIFEST["files"], "nogat-kit.json", "nogat.json", "tokens.css"}


def test_gui_kit_record_names_the_commit_and_the_manifest():
    assert re.fullmatch(r"[0-9a-f]{40}", RECORD["commit"])
    assert RECORD["kit"]["version"] == MANIFEST["version"]
    assert RECORD["kit"]["sha256"] == _sha256(KIT / "nogat-kit.json")


@pytest.mark.parametrize("name", sorted(RECORD["files"]))
def test_gui_identity_copy_has_its_recorded_hash(name):
    assert _sha256(KIT / name) == RECORD["files"][name]["sha256"]


def test_gui_tokens_are_the_source_after_their_two_comment_lines():
    lines = (KIT / "tokens.css").read_bytes().split(b"\n", 2)
    assert lines[0].startswith(b"/* Copied from Nogat design/tokens.css at commit ")
    assert RECORD["commit"].startswith(lines[0].split(b"commit ")[1][:7].decode())
    source = hashlib.sha256(lines[2]).hexdigest()
    assert source == RECORD["files"]["tokens.css"]["from_sha256"]


@pytest.mark.parametrize(
    "name",
    sorted(name for library in LIBRARIES for name in library["files"]),
)
def test_gui_vendored_file_has_its_recorded_hash(name):
    recorded = next(
        library["files"][name] for library in LIBRARIES if name in library["files"]
    )
    assert _sha256(VENDOR / name) == recorded["sha256"]


def test_gui_vendors_maplibre_6_14_with_its_licence():
    maplibre = next(lib for lib in LIBRARIES if lib["name"] == "maplibre-gl")
    assert maplibre["version"] == "6.14.0"
    assert (VENDOR / maplibre["license_file"]).is_file()
