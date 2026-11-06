"""``hydro download --product pgw --country pl`` (ADR-059): the national archive.

The published file is served by a fake session with the answer recorded on
2026-11-06 (``tests/fixtures/pl/pgw``: the real size in ``HEAD``) and the tiny
archive of ``kartograf.testing`` as its body, which has the published structure.
"""

import json
from pathlib import Path

import pytest

from kartograf.download import collections as col
from kartograf.download.collections import check_collection, download_collection
from kartograf.notices import WHOLE_COUNTRY_SIZE
from kartograf.testing import PGW_ARCHIVE_SEGMENT, build_pgw_archive
from tests.support.fake_packages import FakePackageSession, zip_bytes

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pl" / "pgw" / "archive.json"
RECORDED = json.loads(FIXTURE.read_text(encoding="utf-8"))
URL = RECORDED["url"]
HEAD = RECORDED["head"]["headers"]
CHOICE = {"product": "pgw", "country": "pl", "whole_country": True, "cache": False}


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return build_pgw_archive(tmp_path_factory.mktemp("pgw") / "pl.zip").read_bytes()


def _published(body: bytes) -> FakePackageSession:
    """The published file: ``HEAD`` with the recorded size, ``GET`` of ``body``."""
    return FakePackageSession(
        {URL: (200, {**HEAD, "Content-Length": str(len(body))}, body)},
        heads={URL: HEAD},
    )


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


def test_whole_country_stores_the_archive_under_its_edition(
    tmp_path, monkeypatch, frozen_clock, archive
):
    """The ZIP 1:1 in ``hydro/pl_pgw_gdb/country/pl.zip``, labelled by the edition
    of the file (2023-09-15), not by the download date; the recorded size is
    announced before the transfer; the sidecar names the source and the
    reservation of the publication."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    seen: list[tuple[str, int]] = []

    report = download_collection(
        **CHOICE,
        root=tmp_path,
        on_notice=lambda n: seen.append((n.code, session.gets(URL))),
    )

    assert report.ok
    (item,) = report.files
    assert item.file.path == tmp_path / PGW_ARCHIVE_SEGMENT / "country" / "pl.zip"
    assert item.file.path.read_bytes() == archive
    assert item.file.version_path.parent.name == f"2023-09-15_{item.file.sha256[:8]}"
    assert seen == [(WHOLE_COUNTRY_SIZE, 0)]
    assert HEAD["Content-Length"] in report.notices[0].message
    meta = _meta(item.file.version_path)
    assert (meta["dataset"], meta["product"], meta["provider"]) == (
        "pl.pgw.pgw",
        "pgw",
        "PGW Wody Polskie",
    )
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["request"] == {"whole_country": True}
    assert meta["extra"]["source"] == {"url": URL, "edition": "2023-09-15"}
    assert meta["extra"]["version"] == {
        "label": "2023-09-15",
        "label_source": "edition",
    }
    assert meta["license"]["url"] == RECORDED["page"]
    assert meta["license"]["attribution"].startswith(
        "Dane: PGW Wody Polskie, KZGW, IIaPGW"
    )


def test_local_archive_is_used_and_checked_without_a_request(
    tmp_path, monkeypatch, archive
):
    """Signal ``none``: without a local version the plan says ``missing``; once
    stored, a new run uses the local version and ``--check`` says
    ``unverifiable``, and neither sends a request."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    (before,) = check_collection(**CHOICE, root=tmp_path).items
    assert before.status == "missing"
    download_collection(**CHOICE, root=tmp_path)
    session.calls.clear()

    again = download_collection(**CHOICE, root=tmp_path)
    (planned,) = check_collection(**CHOICE, root=tmp_path).items

    assert [item.file.status for item in again.files] == ["local"]
    assert planned.status == "unverifiable"
    assert session.calls == []


def test_archive_of_another_edition_is_refused(tmp_path, monkeypatch):
    """The member check finds the edition date in the geodatabase name: an
    archive of another edition behind the URL fails and leaves no version."""
    other = zip_bytes(
        [
            "Geobaza_2aPGW_ver_20240101.gdb/",
            "Geobaza_2aPGW_ver_20240101.gdb/a00000001.gdbtable",
            "Geobaza_2aPGW_ver_20240101.gdb/gdb",
        ]
    )
    monkeypatch.setattr(col, "_session", lambda: _published(other))

    report = download_collection(**CHOICE, root=tmp_path)

    assert not report.ok and report.files == ()
    (failure,) = report.failed
    assert failure.kind == "download"
    assert "_ver_20230915.gdb/gdb" in failure.error
    assert list(tmp_path.rglob("*.zip")) == []
