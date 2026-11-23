"""``hydro download --product camels --country pl --whole-country`` (ADR-062): the
catchments and gauging stations of a CAMELS-PL release, read out of its ZIP on Zenodo.

The published ZIPs are 1.6 GB: the registry entry is re-pinned to the tiny fixture
archives of ``kartograf.testing`` (``tests.support.camels.use_params``; their length
and the size, CRC and SHA-256 of their GeoPackages, everything else as registered).
Zenodo is ``ZenodoServer``: the fixture ZIP of each supported release, answering
range requests, and the concept DOI with the answers recorded on 2026-11-23
(``tests/fixtures/pl/camels``: its 302 to the record of 2.1.0, then that record).
"""

import io
import json
import zipfile
import zlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from kartograf import (
    command_for_file,
    format_command,
    parse_command,
    read_sidecar,
)
from kartograf.download import collections as col
from kartograf.download.collections import check_collection, download_collection
from kartograf.download.releases import release_params
from kartograf.exceptions import ConflictError, ReleaseLayoutError, ValidationError
from kartograf.messages import message
from kartograf.notices import (
    CHECK_FAILED,
    NEWER_RELEASE,
    WHOLE_ARCHIVE,
    WHOLE_COUNTRY_SIZE,
)
from kartograf.sources.descriptor import ReleaseFilesParams
from kartograf.sources.registry import get_source
from kartograf.testing import (
    CAMELS_DATASET,
    CAMELS_SEGMENT,
    _camels_archive_bytes,
    _camels_gpkg,
)
from kartograf.transport.zip_range import TAIL_BYTES
from tests.support.camels import (
    CONCEPT_URL,
    RECORD_URL,
    ZIP_HEADERS,
    Asked,
    ZenodoServer,
    concept_answers,
    fixture_params,
    member_ranges,
    recorded_record,
    use_params,
    zenodo,
)
from tests.support.fake_packages import FakePackageSession

CHOICE = {"product": "camels", "country": "pl", "whole_country": True}
UNITS = ["pl_catchments", "pl_gauging-stations"]
THEMES = ["catchments", "gauging-stations"]
# The registry as published (the pins of the real ZIPs), read before any test.
REGISTERED = release_params(get_source(CAMELS_DATASET).channels[0])
URL_20 = "https://zenodo.org/api/records/23102156/files/CAMELS_PL_2.0.zip/content"
URL_21 = "https://zenodo.org/api/records/23275336/files/CAMELS_PL_2.1.zip/content"
RELEASE_20 = {
    "version": "2.0.0",
    "record": "23102156",
    "doi": "10.5281/zenodo.23102156",
    "published": "2026-10-07",
}
RELEASE_21 = {
    "version": "2.1.0",
    "record": "23275336",
    "doi": "10.5281/zenodo.23275336",
    "published": "2026-10-11",
}
# The provider lines S and P of IMGW-PIB and L of each release (DEV §20).
S = (
    "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – "
    "Państwowy Instytut Badawczy"
)
P = (
    "Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu "
    "Badawczego zostały przetworzone"
)
L_21 = (
    "Źródło danych: CAMELS-PL 2.1.0 (Brzezińska i in., 2026), "
    "https://doi.org/10.5281/zenodo.23275336, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/)"
)
L_20 = (
    "Źródło danych: CAMELS-PL 2.0.0 (Brzezińska i in., 2026), "
    "https://doi.org/10.5281/zenodo.23102156, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/)"
)
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"


@pytest.fixture
def fixture(monkeypatch: pytest.MonkeyPatch) -> ReleaseFilesParams:
    """The registry entry re-pinned to the fixture archives, for one test."""
    params = fixture_params()
    use_params(monkeypatch, params)
    return params


def _serve(monkeypatch: pytest.MonkeyPatch, server: ZenodoServer) -> ZenodoServer:
    session = server.session()
    monkeypatch.setattr(col, "_session", lambda: session)
    return server


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


def _concept() -> list[Asked]:
    """The lookup of the newest release: the recorded 302, then the record."""
    return [Asked("GET", CONCEPT_URL, None), Asked("GET", RECORD_URL, None)]


def _by_ranges(params: ReleaseFilesParams, version: str, url: str) -> list[Asked]:
    """The range requests of a release: its directory, then each member's local
    header and stored bytes, in the order of the registry."""
    archive = _camels_archive_bytes(version)
    (release,) = [r for r in params.releases if r.version == version]
    return [
        Asked("GET", url, f"bytes=-{TAIL_BYTES}"),
        *(
            Asked("GET", url, span)
            for member in release.members
            for span in member_ranges(archive, member.path)
        ),
    ]


# --- a run -------------------------------------------------------------------------


def test_newest_release_is_read_by_ranges_into_the_store(
    tmp_path, monkeypatch, fixture
):
    """The default release, 2.1.0: the concept DOI asked once (it names 2.1.0, which
    the registry knows: no notice), the size announced after the directory and
    before any member; both files labelled by the date of the first release with
    their bytes, 2.0.0 of 2026-10-07, and linked from their standard paths."""
    server = _serve(monkeypatch, zenodo(fixture))
    seen: list[tuple[str, int]] = []

    report = download_collection(
        **CHOICE,
        root=tmp_path,
        on_notice=lambda n: seen.append((n.code, len(server.asked))),
    )

    assert report.ok and report.failed == () and report.stale == ()
    assert [(item.unit, item.file.status) for item in report.files] == [
        ("pl_catchments", "new"),
        ("pl_gauging-stations", "new"),
    ]
    for item, theme in zip(report.files, THEMES, strict=True):
        file = item.file
        assert file.path == tmp_path / CAMELS_SEGMENT / "country" / f"{item.unit}.gpkg"
        assert file.version_path == (
            tmp_path
            / CAMELS_SEGMENT
            / "versions"
            / "country"
            / f"2026-10-07_{file.sha256[:8]}"
            / f"{item.unit}.gpkg"
        )
        assert file.label == "2026-10-07"
        assert file.path.samefile(file.version_path)
        assert file.path.read_bytes() == _camels_gpkg(theme)
    assert server.asked == [*_concept(), *_by_ranges(fixture, "2.1.0", URL_21)]
    assert seen == [(WHOLE_COUNTRY_SIZE, 3)]
    (size,) = report.notices
    assert size.level == "warning"
    assert f"of {fixture.releases[-1].size} B" in size.message


@pytest.mark.parametrize(
    ("version", "release", "url", "line"),
    [(None, RELEASE_21, URL_21, L_21), ("2.0.0", RELEASE_20, URL_20, L_20)],
    ids=["newest", "2.0.0"],
)
def test_sidecar_names_the_release_its_twin_and_the_provider_lines(
    tmp_path, monkeypatch, fixture, version, release, url, line
):
    """``request`` and ``extra.release`` name the release read, ``extra.releases``
    every release with these bytes (both), the attribution is S, P and the L of
    the release read, ``extra.source`` the published member read by ranges."""
    server = _serve(monkeypatch, zenodo(fixture))

    report = download_collection(**CHOICE, root=tmp_path, version=version)

    (pinned,) = [r for r in fixture.releases if r.version == release["version"]]
    assert server.asked == [*_concept(), *_by_ranges(fixture, pinned.version, url)]
    for item, member in zip(report.files, pinned.members, strict=True):
        meta = _meta(item.file.version_path)
        assert (meta["dataset"], meta["country"], meta["product"]) == (
            "pl.camels.camels",
            "PL",
            "camels",
        )
        assert (meta["provider"], meta["horizontal_crs"]) == ("CAMELS-PL", "EPSG:2180")
        assert meta["request"] == {"whole_country": True, "version": pinned.version}
        assert meta["license"] == {
            "id": "CC-BY-4.0",
            "attribution": f"{S}\n{P}\n{line}",
            "url": LICENSE_URL,
        }
        assert meta["extra"] == {
            "source": {
                "url": url,
                "member": member.path,
                "crc32": member.crc32,
                "read": "range",
            },
            "release": release,
            "releases": [RELEASE_20, RELEASE_21],
            "attribution": [S, P, line],
            "version": {"label": "2026-10-07", "label_source": "edition"},
        }
        assert (meta["sha256"], meta["size_bytes"]) == (member.sha256, member.size)
        assert member.path.startswith(f"CAMELS_PL_{pinned.version[:3]}/")


def test_server_that_ignores_ranges_gets_the_whole_zip_read(
    tmp_path, monkeypatch, fixture
):
    """200 to the range of the directory: a warning, the whole ZIP downloaded into
    staging (its length checked), the members read from it and the ZIP removed."""
    server = _serve(monkeypatch, zenodo(fixture, ranges=False))

    report = download_collection(**CHOICE, root=tmp_path)

    assert report.ok
    assert [(n.level, n.code) for n in report.notices] == [("warning", WHOLE_ARCHIVE)]
    assert [item.file.status for item in report.files] == ["new", "new"]
    for item, theme in zip(report.files, THEMES, strict=True):
        assert item.file.path.read_bytes() == _camels_gpkg(theme)
        assert _meta(item.file.version_path)["extra"]["source"]["read"] == "archive"
    assert server.asked == [
        *_concept(),
        Asked("GET", URL_21, f"bytes=-{TAIL_BYTES}"),
        Asked("GET", URL_21, None),
    ]
    assert server.bodies[2].taken == 0
    assert list(tmp_path.rglob("*.zip")) == []


class _RangesOfTheDirectoryOnly(ZenodoServer):
    """A server that answers the range of the directory, then ignores ``Range``."""

    def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ):
        response = super().send(
            request,
            stream=stream,
            timeout=timeout,
            verify=verify,
            cert=cert,
            proxies=proxies,
        )
        if response.status_code == 206:
            self._ranges = False
        return response


def test_ranges_refused_after_the_directory_get_the_whole_zip_read(
    tmp_path, monkeypatch, fixture
):
    """The size is announced after the directory; the member whose range is refused
    is discarded and the whole ZIP is read instead."""
    files = {
        r.url: (_camels_archive_bytes(r.version), ZIP_HEADERS)
        for r in fixture.releases[1:]
    }
    server = _serve(
        monkeypatch, _RangesOfTheDirectoryOnly(files, answers=concept_answers())
    )

    report = download_collection(**CHOICE, root=tmp_path)

    header, _ = member_ranges(
        _camels_archive_bytes("2.1.0"), fixture.releases[-1].members[0].path
    )
    assert report.ok
    assert [n.code for n in report.notices] == [WHOLE_COUNTRY_SIZE, WHOLE_ARCHIVE]
    assert [item.file.status for item in report.files] == ["new", "new"]
    assert server.asked == [
        *_concept(),
        Asked("GET", URL_21, f"bytes=-{TAIL_BYTES}"),
        Asked("GET", URL_21, header),
        Asked("GET", URL_21, None),
    ]
    assert {
        _meta(item.file.version_path)["extra"]["source"]["read"]
        for item in report.files
    } == {"archive"}
    assert list(tmp_path.rglob("*.zip")) == []
    assert list(tmp_path.rglob(".incoming/*")) == []


def test_release_with_the_same_bytes_makes_no_new_version(
    tmp_path, monkeypatch, fixture
):
    """2.0.0, then 2.1.0 (the same bytes): the versions of 2.0.0 are the files of
    2.1.0, without a request; ``update="force"`` reads the ZIP again and finds the
    same bytes (``unchanged``). The version keeps the sidecar written first."""
    server = _serve(monkeypatch, zenodo(fixture))
    first = download_collection(**CHOICE, root=tmp_path, version="2.0.0")
    server.asked.clear()

    newest = download_collection(**CHOICE, root=tmp_path)
    asked = list(server.asked)
    forced = download_collection(**CHOICE, root=tmp_path, update="force")

    assert [item.file.status for item in first.files] == ["new", "new"]
    assert [item.file.status for item in newest.files] == ["local", "local"]
    assert asked == []
    assert [item.file.status for item in forced.files] == ["unchanged", "unchanged"]
    assert server.asked == [*_concept(), *_by_ranges(fixture, "2.1.0", URL_21)]
    for report in (newest, forced):
        assert [item.file.version_path for item in report.files] == [
            item.file.version_path for item in first.files
        ]
    versions = tmp_path / CAMELS_SEGMENT / "versions" / "country"
    assert sorted(path.name for path in versions.iterdir()) == sorted(
        item.file.version_path.parent.name for item in first.files
    )
    for item in forced.files:
        assert _meta(item.file.version_path)["request"]["version"] == "2.0.0"


# --- refused requests ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "text"),
    [
        (
            "1.0.0",
            message(
                "releases.refused_version",
                dataset="CAMELS-PL",
                version="1.0.0",
                record="20133183",
                refusal=message("sources.camels_1_0_0_refused"),
                versions="2.0.0, 2.1.0",
            ),
        ),
        (
            "9.9.9",
            message(
                "releases.unknown_version",
                dataset="CAMELS-PL",
                version="9.9.9",
                product="camels",
                versions="2.0.0, 2.1.0",
            ),
        ),
    ],
    ids=["refused", "unknown"],
)
def test_refused_or_unknown_version_is_refused_before_any_request(
    tmp_path, monkeypatch, fixture, version, text
):
    server = _serve(monkeypatch, zenodo(fixture))
    root = tmp_path / "store"

    for call in (download_collection, check_collection):
        with pytest.raises(ValidationError) as raised:
            call(**CHOICE, root=root, version=version)
        assert str(raised.value) == text
        assert (raised.value.option, raised.value.allowed) == (
            "version",
            ("2.0.0", "2.1.0"),
        )

    assert server.asked == []
    assert not root.exists()


@pytest.mark.parametrize(
    "choice",
    [
        {"product": "pgw", "country": "pl", "whole_country": True},
        {"product": "network", "country": "cz", "whole_country": True},
        {"product": "admin", "country": "pl", "whole_country": True},
    ],
    ids=["pgw", "network", "admin"],
)
def test_version_of_another_product_is_refused_before_any_request(
    tmp_path, monkeypatch, choice
):
    session = FakePackageSession({})
    monkeypatch.setattr(col, "_session", lambda: session)

    with pytest.raises(ValidationError) as raised:
        download_collection(**choice, version="2.1.0", root=tmp_path / "store")

    assert raised.value.option == "version"
    assert "--product camels" in str(raised.value)
    assert session.calls == []
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("level", "powiat"),
        ("year", 2024),
        ("layers", ["catchments"]),
        ("horizontal_crs", "EPSG:4326"),
    ],
)
def test_content_options_of_other_products_are_refused_for_a_release(
    tmp_path, monkeypatch, fixture, option, value
):
    server = _serve(monkeypatch, zenodo(fixture))

    with pytest.raises(ValidationError) as raised:
        download_collection(**CHOICE, root=tmp_path / "store", **{option: value})

    assert option in (raised.value.option, *(raised.value.options or ()))
    assert server.asked == []


# --- a ZIP of another layout -------------------------------------------------------


def _members(version: str) -> list[tuple[zipfile.ZipInfo, bytes]]:
    """The members of the fixture ZIP of ``version`` with their bytes."""
    archive = zipfile.ZipFile(io.BytesIO(_camels_archive_bytes(version)))
    return [(info, archive.read(info)) for info in archive.infolist()]


def _rezip(members: list[tuple[str, bytes, int]]) -> bytes:
    """A ZIP of ``(name, body, method)`` with the date of the fixture members."""
    date = _members("2.1.0")[0][0].date_time
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body, method in members:
            info = zipfile.ZipInfo(name, date_time=date)
            info.compress_type = method
            archive.writestr(info, body)
    return buffer.getvalue()


def _layout(case: str) -> tuple[bytes, ReleaseFilesParams, str, str | None]:
    """The ZIP served for 2.1.0, the registry pins, the error text and its member.

    The registry pins the length of the served ZIP (but for ``zip-length``), so the
    check of the case is the one that fails.
    """
    params = fixture_params()
    *older, release = params.releases
    catchments, gauges = release.members
    pattern = params.files[0].pattern
    members = [(i.filename, body, i.compress_type) for i, body in _members("2.1.0")]
    common: dict[str, Any] = {
        "dataset": "CAMELS-PL",
        "version": "2.1.0",
        "record": "23275336",
    }
    if case == "zip-length":
        served = _rezip(
            [*members, ("CAMELS_PL_2.1/README.txt", b"CAMELS-PL", zipfile.ZIP_STORED)]
        )
        text = message(
            "releases.zip_length",
            **common,
            url=URL_21,
            length=len(served),
            expected=release.size,
        )
        return served, params, text, None
    if case == "pattern-none":
        renamed = catchments.path.replace(".gpkg", "_v2.gpkg")
        edited = [(renamed if n == catchments.path else n, b, m) for n, b, m in members]
        served = _rezip(edited)
        text = message("releases.member_count", **common, pattern=pattern, count=0)
        member: str | None = pattern
    elif case == "pattern-twice":
        copy = catchments.path.replace("CAMELS_PL_2.1/", "CAMELS_PL_2.1/old/")
        body = _camels_gpkg("catchments")
        served = _rezip([*members, (copy, body, zipfile.ZIP_DEFLATED)])
        text = message("releases.member_count", **common, pattern=pattern, count=2)
        member = pattern
    elif case == "size-crc":
        other = _camels_gpkg("catchments") + bytes(1024)
        edited = [(n, other if n == catchments.path else b, m) for n, b, m in members]
        served = _rezip(edited)
        text = message(
            "releases.member_differs",
            **common,
            member=catchments.path,
            size=len(other),
            crc32=f"{zlib.crc32(other):08x}",
            expected_size=catchments.size,
            expected_crc32=catchments.crc32,
        )
        member = catchments.path
    elif case == "method":
        edited = [
            (n, b, zipfile.ZIP_BZIP2 if n == catchments.path else m)
            for n, b, m in members
        ]
        served = _rezip(edited)
        text = message(
            "releases.member_method",
            **common,
            member=catchments.path,
            method=zipfile.ZIP_BZIP2,
        )
        member = catchments.path
    else:  # sha256: the registry pins the published bytes, Zenodo has other ones
        served = _camels_archive_bytes("2.1.0")
        published = REGISTERED.releases[-1].member("gauging-stations").sha256
        gauges = replace(gauges, sha256=published)
        release = replace(release, members=(catchments, gauges))
        text = message(
            "releases.member_sha256",
            **common,
            member=gauges.path,
            sha256=fixture_params().releases[-1].members[1].sha256,
            expected=published,
        )
        member = gauges.path
    pinned = replace(release, size=len(served))
    return served, replace(params, releases=(*older, pinned)), text, member


@pytest.mark.parametrize(
    "case",
    ["zip-length", "pattern-none", "pattern-twice", "size-crc", "method", "sha256"],
)
def test_zip_of_another_layout_is_refused_and_nothing_is_written(
    tmp_path, monkeypatch, case
):
    """Any difference from the pins of the release: ``ReleaseLayoutError`` naming
    the version and the file, the DOI in its hint; no version, no standard path,
    no staging and no marker are left."""
    served, params, text, member = _layout(case)
    use_params(monkeypatch, params)
    server = _serve(
        monkeypatch,
        ZenodoServer({URL_21: (served, ZIP_HEADERS)}, answers=concept_answers()),
    )
    root = tmp_path / "store"

    with pytest.raises(ReleaseLayoutError) as raised:
        download_collection(**CHOICE, root=root)

    error = raised.value
    assert str(error) == text
    assert (error.version, error.record, error.url, error.member) == (
        "2.1.0",
        "23275336",
        URL_21,
        member,
    )
    assert (error.code, error.reason, error.exit_code) == (
        "data_error",
        "release_layout",
        7,
    )
    assert error.hint is not None
    assert "https://doi.org/10.5281/zenodo.23275336" in error.hint
    assert server.asked[: len(_concept())] == _concept()
    assert sorted(root.rglob("*")) == []


# --- a plain write ------------------------------------------------------------------


def test_plain_write_writes_both_files_and_the_provider_lines(
    tmp_path, monkeypatch, fixture
):
    _serve(monkeypatch, zenodo(fixture))
    out = tmp_path / "out"

    plan = check_collection(**CHOICE, output_dir=out)
    report = download_collection(**CHOICE, output_dir=out)

    assert [(item.name, item.action) for item in plan.items] == [
        ("pl_catchments.gpkg", "write"),
        ("pl_gauging-stations.gpkg", "write"),
        ("ATTRIBUTION.txt", "write"),
    ]
    assert report.ok
    assert [(item.unit, item.file.status) for item in report.files] == [
        ("pl_catchments", "written"),
        ("pl_gauging-stations", "written"),
        ("ATTRIBUTION.txt", "written"),
    ]
    assert sorted(path.name for path in out.iterdir()) == [
        "ATTRIBUTION.txt",
        "pl_catchments.gpkg",
        "pl_gauging-stations.gpkg",
    ]
    for unit, theme in zip(UNITS, THEMES, strict=True):
        assert (out / f"{unit}.gpkg").read_bytes() == _camels_gpkg(theme)
    assert (out / "ATTRIBUTION.txt").read_text("utf-8") == f"{S}\n{P}\n{L_21}\n"


def test_second_plain_write_of_another_release_merges_its_line(
    tmp_path, monkeypatch, fixture
):
    """Without ``force`` the files are a conflict before any request; with it they
    are replaced and ``ATTRIBUTION.txt`` gets the ``L`` line of 2.0.0 after the one
    of 2.1.0, none removed."""
    server = _serve(monkeypatch, zenodo(fixture))
    out = tmp_path / "out"
    download_collection(**CHOICE, output_dir=out)
    asked = len(server.asked)

    with pytest.raises(ConflictError):
        download_collection(**CHOICE, output_dir=out, version="2.0.0")
    refused = len(server.asked)
    plan = check_collection(**CHOICE, output_dir=out, version="2.0.0", force=True)
    again = download_collection(
        **CHOICE, output_dir=out, version="2.0.0", update="force"
    )

    assert refused == asked
    assert [(item.name, item.action) for item in plan.items] == [
        ("pl_catchments.gpkg", "replace"),
        ("pl_gauging-stations.gpkg", "replace"),
        ("ATTRIBUTION.txt", "replace"),
    ]
    assert [(item.unit, item.file.status) for item in again.files] == [
        ("pl_catchments", "replaced"),
        ("pl_gauging-stations", "replaced"),
        ("ATTRIBUTION.txt", "replaced"),
    ]
    assert (out / "ATTRIBUTION.txt").read_text("utf-8") == (
        f"{S}\n{P}\n{L_21}\n{L_20}\n"
    )


def test_plain_write_beside_an_unreadable_attribution_needs_force(
    tmp_path, monkeypatch, fixture
):
    """An ``ATTRIBUTION.txt`` that is no UTF-8 text: the plan says ``conflict`` and
    the run raises ``output_exists`` before any request, writing nothing; with
    ``force`` the provider lines alone replace it."""
    server = _serve(monkeypatch, zenodo(fixture))
    out = tmp_path / "out"
    out.mkdir()
    (out / "ATTRIBUTION.txt").write_bytes(b"\xff\xfe\x00")

    plan = check_collection(**CHOICE, output_dir=out)
    asked = list(server.asked)
    with pytest.raises(ConflictError) as raised:
        download_collection(**CHOICE, output_dir=out)
    refused = list(server.asked)
    kept = sorted(path.name for path in out.iterdir())
    forced = download_collection(**CHOICE, output_dir=out, update="force")

    (attribution,) = [item for item in plan.items if item.name == "ATTRIBUTION.txt"]
    assert (attribution.action, attribution.reason) == ("conflict", "output_exists")
    assert raised.value.reason == "output_exists"
    assert refused == asked == _concept()
    assert kept == ["ATTRIBUTION.txt"]
    assert [(item.unit, item.file.status) for item in forced.files] == [
        ("pl_catchments", "written"),
        ("pl_gauging-stations", "written"),
        ("ATTRIBUTION.txt", "replaced"),
    ]
    assert (out / "ATTRIBUTION.txt").read_text("utf-8") == f"{S}\n{P}\n{L_21}\n"


# --- --check -------------------------------------------------------------------------


def test_check_tells_missing_current_and_newer_without_a_transfer(
    tmp_path, monkeypatch, fixture
):
    """Only the concept DOI is asked. ``missing`` without a version, ``current`` when
    a version holds the pinned bytes, ``newer`` when the store holds other bytes only
    (here: the fixture bytes, judged by the registry as published)."""
    server = _serve(monkeypatch, zenodo(fixture))
    before = check_collection(**CHOICE, root=tmp_path)
    download_collection(**CHOICE, root=tmp_path)
    server.asked.clear()

    after = check_collection(**CHOICE, root=tmp_path)
    use_params(monkeypatch, REGISTERED)
    published = check_collection(**CHOICE, root=tmp_path)

    assert [(item.unit, item.status) for item in before.items] == [
        ("pl_catchments", "missing"),
        ("pl_gauging-stations", "missing"),
    ]
    assert [
        (item.unit, item.status, item.local_label, item.available_label)
        for item in after.items
    ] == [
        ("pl_catchments", "current", "2026-10-07", "2026-10-07"),
        ("pl_gauging-stations", "current", "2026-10-07", "2026-10-07"),
    ]
    assert [item.available_signal for item in after.items] == [
        {"version": "2.1.0", "record": "23275336", "sha256": member.sha256}
        for member in fixture.releases[-1].members
    ]
    assert [(item.unit, item.status) for item in published.items] == [
        ("pl_catchments", "newer"),
        ("pl_gauging-stations", "newer"),
    ]
    assert [item.available_signal["sha256"] for item in published.items] == [
        "dadc37e02febc0f188683c0df18b2380767a4396e7948213b73617ff4746d6b9",
        "a0616fc6eef89b1a3e84de3688e35a87c54ffb2517dc1a54ddcc3af4579d8c14",
    ]
    assert server.asked == _concept() * 2
    assert before.notices == after.notices == published.notices == ()


def test_concept_record_of_an_unknown_release_is_a_notice(
    tmp_path, monkeypatch, fixture
):
    """The recorded record edited into a fictional newer release (2.2.0, record
    24000000), to which the concept DOI redirects: an info notice in a check and in
    a run, which still reads the newest release the registry supports."""
    record = recorded_record()
    record.update(id=24000000, doi="10.5281/zenodo.24000000")
    record["metadata"].update(version="2.2.0", publication_date="2027-03-01")
    server = _serve(monkeypatch, zenodo(fixture, concept=concept_answers(record)))
    text = message(
        "releases.newer_release",
        dataset="CAMELS-PL",
        version="2.2.0",
        record="24000000",
        doi="10.5281/zenodo.24000000",
        published="2027-03-01",
        newest="2.1.0",
    )

    plan = check_collection(**CHOICE, root=tmp_path)
    report = download_collection(**CHOICE, root=tmp_path)

    assert [(n.level, n.code, n.message) for n in plan.notices] == [
        ("info", NEWER_RELEASE, text)
    ]
    assert [n.code for n in report.notices] == [NEWER_RELEASE, WHOLE_COUNTRY_SIZE]
    assert server.asked[:2] == [
        Asked("GET", CONCEPT_URL, None),
        Asked("GET", "https://zenodo.org/api/records/24000000", None),
    ]
    assert {
        _meta(item.file.version_path)["extra"]["release"]["version"]
        for item in report.files
    } == {"2.1.0"}


def test_failed_concept_lookup_warns_in_a_check_and_is_silent_in_a_run(
    tmp_path, monkeypatch, fixture
):
    """The concept DOI answers 404: a ``check_failed`` warning in a check, nothing in
    a run, which reads the release as without the lookup."""
    server = _serve(monkeypatch, zenodo(fixture, concept={}))

    plan = check_collection(**CHOICE, root=tmp_path)
    report = download_collection(**CHOICE, root=tmp_path)

    (warning,) = plan.notices
    assert (warning.level, warning.code) == ("warning", CHECK_FAILED)
    assert "https://doi.org/10.5281/zenodo.20133182" in warning.message
    assert [item.status for item in plan.items] == ["missing", "missing"]
    assert report.ok
    assert [n.code for n in report.notices] == [WHOLE_COUNTRY_SIZE]
    assert [item.file.status for item in report.files] == ["new", "new"]
    assert server.asked[0] == Asked("GET", CONCEPT_URL, None)


# --- the stored file and its command -------------------------------------------------


def test_command_for_a_stored_file_names_its_release(tmp_path, monkeypatch, fixture):
    _serve(monkeypatch, zenodo(fixture))
    report = download_collection(**CHOICE, root=tmp_path)

    for item in report.files:
        call = command_for_file(read_sidecar(item.file.path))
        line = format_command(call.command, call.options)

        assert line == (
            "kartograf hydro download --product camels --country pl --whole-country "
            "--version 2.1.0"
        )
        assert parse_command(line) == call
