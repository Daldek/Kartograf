"""Engine ``unit_package`` (ADR-042 D1-D2, ADR-043): variants, URLs, package
and file checks."""

import json
import zipfile
from pathlib import Path

import pytest

from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.sources.descriptor import PackageVariant, UnitPackageParams
from kartograf.sources.registry import get_source
from kartograf.transport.unit_package import (
    fetch_package,
    package_url,
    select_variant,
)
from tests.conftest import write_gpkg_layers
from tests.fake_packages import (
    FakePackageSession,
    package_route,
    zip_bytes,
)


def _params(key: str, capability: str) -> UnitPackageParams:
    channel = next(c for c in get_source(key).channels if capability in c.capabilities)
    assert isinstance(channel.params, UnitPackageParams)
    return channel.params


ARCHIVE = _params("pl.gugik.bdot10k", "archive_unit_files")
BUILDINGS = _params("pl.gugik.buildings", "admin_unit_files")
PRG_WOJ = _params("pl.gugik.prg", "admin_unit_files")
EGIB = _params("pl.gugik.egib", "admin_unit_files")


def _message(error: pytest.ExceptionInfo) -> str:
    return str(error.value)


class TestSelectVariant:
    def test_select_variant_requires_each_key(self):
        years = [str(year) for year in range(2014, 2026)]
        with pytest.raises(ValidationError) as missing_year:
            select_variant(ARCHIVE, format="SHP")
        assert all(year in _message(missing_year) for year in years)
        assert "--year" in _message(missing_year)

        with pytest.raises(ValidationError) as missing_format:
            select_variant(ARCHIVE, year="2024")
        assert "--format" in _message(missing_format)

        for fmt in ("GPKG", "shp"):
            with pytest.raises(ValidationError) as wrong:
                select_variant(ARCHIVE, format=fmt, year="2024")
            assert "GML, SHP" in _message(wrong)

        with pytest.raises(ValidationError):
            select_variant(ARCHIVE, format="SHP", year="2013")

    def test_select_variant_picks_the_published_one(self):
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        assert dict(variant.choice) == {"format": "SHP", "year": "2024"}
        assert (variant.edition, variant.segment_tokens) == ("2024", ("shp", "2024"))

    def test_single_variant_needs_no_choice_and_accepts_only_it(self):
        lod2 = select_variant(BUILDINGS, lod="2")
        assert (dict(lod2.choice)["year"], lod2.vertical_crs) == ("2017", "EPSG:9650")
        assert select_variant(BUILDINGS, lod="2", year="2017") is lod2
        with pytest.raises(ValidationError) as other_year:
            select_variant(BUILDINGS, lod="2", year="2016")
        assert "2017" in _message(other_year)
        with pytest.raises(ValidationError) as lod1:
            select_variant(BUILDINGS, lod="1")
        assert "2019, 2021, 2022, 2024" in _message(lod1)
        with pytest.raises(ValidationError) as nothing:
            select_variant(BUILDINGS)
        assert "--lod" in _message(nothing)

    def test_channel_without_choice(self):
        assert select_variant(PRG_WOJ).segment_tokens == ("gml",)
        with pytest.raises(ValidationError) as foreign:
            select_variant(PRG_WOJ, year="2024")
        assert "--year" in _message(foreign)


def test_package_url_from_template():
    shp = select_variant(ARCHIVE, format="SHP", year="2024")
    assert package_url(shp, teryt="1261") == (
        "https://opendata.geoportal.gov.pl/Archiwum/bdot10k/2024/SHP/12/1261_SHP_2024.zip"
    )
    lod1_2019 = select_variant(BUILDINGS, lod="1", year="2019")
    assert package_url(lod1_2019, teryt="0401").endswith("/LOD1/2019/04/0401_gml.zip")
    assert package_url(select_variant(PRG_WOJ), teryt="12").endswith(
        "/prg/granice/12_GraniceAdministracyjne.zip"
    )
    with pytest.raises(ValueError):
        package_url(shp, teryt=None)


def _fetch(tmp_path, name, params, variant, **route):
    url, response = package_route(name, **route)
    session = FakePackageSession({url: response})
    staged = tmp_path / "incoming" / "result"
    staged.parent.mkdir()
    return (
        session,
        staged,
        lambda: fetch_package(
            session, url, staged, params=params, variant=variant, timeout=5
        ),
    )


class TestFetchPackage:
    def test_zip_stored_one_to_one(self, tmp_path):
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        session, staged, run = _fetch(
            tmp_path, "bdot10k_2024_shp_1261", ARCHIVE, variant
        )
        package = run()
        assert package.path == staged
        assert package.size == staged.stat().st_size
        assert package.http["content_length"] == package.size
        with zipfile.ZipFile(staged) as archive:
            assert "PL.PZGiK.283.1261__OT_PTWP_A.shp" in archive.namelist()
        assert session.gets() == 1

    def test_fetch_package_rejects_html_200(self, tmp_path):
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        url, _ = package_route("bdot10k_2024_shp_1261")
        html = b"plik nie istnieje: /Archiwum/bdot10k/2024/SHP/12/1261_SHP_2024.zip"
        session = FakePackageSession(
            {url: (200, {"Content-Type": "text/html; charset=UTF-8"}, html)}
        )
        staged = tmp_path / "result.zip"
        with pytest.raises(DownloadError) as error:
            fetch_package(
                session, url, staged, params=ARCHIVE, variant=variant, timeout=5
            )
        assert not isinstance(error.value, NoCoverageError)
        assert not staged.exists()

    def test_fetch_package_rejects_truncated(self, tmp_path):
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        _session, staged, run = _fetch(
            tmp_path, "bdot10k_2024_shp_1261", ARCHIVE, variant, length=47404309
        )
        with pytest.raises(DownloadError):
            run()
        assert list(staged.parent.iterdir()) == []

    def test_fetch_package_rejects_missing_members(self, tmp_path):
        """A GML package where the SHP variant was requested is not that data."""
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        members = ["PL.PZGiK.283.1261/BDOT10k/PL.PZGiK.283.1261__OT_PTWP_A.xml"]
        _session, staged, run = _fetch(
            tmp_path, "bdot10k_2024_shp_1261", ARCHIVE, variant, members=members
        )
        with pytest.raises(DownloadError):
            run()
        assert not staged.exists()

    def test_fetch_package_rejects_not_a_zip(self, tmp_path):
        variant = select_variant(ARCHIVE, format="SHP", year="2024")
        url, _ = package_route("bdot10k_2024_shp_1261")
        body = b"PK\x03\x04 obciety"
        session = FakePackageSession(
            {
                url: (
                    200,
                    {
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(len(body)),
                    },
                    body,
                )
            }
        )
        staged = tmp_path / "result.zip"
        with pytest.raises(DownloadError):
            fetch_package(
                session, url, staged, params=ARCHIVE, variant=variant, timeout=5
            )
        assert not staged.exists()

    def test_fetch_package_404_is_no_coverage(self, tmp_path):
        lod2 = select_variant(BUILDINGS, lod="2")
        url, response = package_route("buildings_lod2_2017_3262_missing")
        session = FakePackageSession({url: response})
        staged = tmp_path / "3262.zip"
        with pytest.raises(NoCoverageError) as error:
            fetch_package(
                session, url, staged, params=BUILDINGS, variant=lod2, timeout=5
            )
        assert error.value.status_code == 404
        assert session.gets() == 1  # 404 is not retried
        assert not staged.exists()

    def test_directory_entries_and_nested_members_count(self, tmp_path):
        lod2 = select_variant(BUILDINGS, lod="2")
        _session, staged, run = _fetch(
            tmp_path, "buildings_lod2_2017_1261", BUILDINGS, lod2
        )
        assert run().member is None
        assert staged.is_file()


class TestUnpack:
    def _gpkg_package(self, tmp_path, members: list[str]):
        gpkg = write_gpkg_layers(
            tmp_path / "1261.gpkg", ["dzialki", "budynki", "transakcje"]
        )
        body = gpkg.read_bytes()
        url, _ = package_route("egib_1261")

        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in members:
                archive.writestr(name, body)
        data = buffer.getvalue()
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(data)),
        }
        return url, FakePackageSession({url: (200, headers, data)}), body

    def test_unpack_single_member(self, tmp_path):
        (variant,) = EGIB.variants
        url, session, body = self._gpkg_package(tmp_path, ["1261.gpkg"])
        staged = tmp_path / "incoming" / "1261.gpkg"
        staged.parent.mkdir()
        package = fetch_package(
            session, url, staged, params=EGIB, variant=variant, timeout=5
        )
        assert package.member == "1261.gpkg"
        assert staged.read_bytes() == body
        assert sorted(p.name for p in staged.parent.iterdir()) == ["1261.gpkg"]

    @pytest.mark.parametrize("members", [[], ["1261.gpkg", "kopia/1261.gpkg"]])
    def test_unpack_needs_exactly_one_member(self, tmp_path, members):
        (variant,) = EGIB.variants
        url, session, _ = self._gpkg_package(tmp_path, members or ["readme.txt"])
        staged = tmp_path / "incoming" / "1261.gpkg"
        staged.parent.mkdir()
        with pytest.raises(DownloadError):
            fetch_package(session, url, staged, params=EGIB, variant=variant, timeout=5)
        assert list(staged.parent.iterdir()) == []

    def test_unpack_bad_crc_is_download_error(self, tmp_path):
        (variant,) = EGIB.variants
        data = bytearray(zip_bytes(["1261.gpkg"], content=b"G" * 4096))
        start = data.index(b"1261.gpkg") + len("1261.gpkg") + 8
        data[start] ^= 0xFF  # corrupt the compressed member, keep the length
        url, _ = package_route("egib_1261")
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(data)),
        }
        session = FakePackageSession({url: (200, headers, bytes(data))})
        staged = tmp_path / "incoming" / "1261.gpkg"
        staged.parent.mkdir()
        with pytest.raises(DownloadError):
            fetch_package(session, url, staged, params=EGIB, variant=variant, timeout=5)
        assert list(staged.parent.iterdir()) == []


def test_variant_members_are_case_insensitive(tmp_path):
    params = UnitPackageParams(
        unit="powiat",
        variants=(
            PackageVariant(
                choice=(), url_template="https://x/{teryt}.zip", members=(".shp",)
            ),
        ),
    )
    url = "https://x/1261.zip"
    body = zip_bytes(["A.SHP"])
    session = FakePackageSession(
        {
            url: (
                200,
                {"Content-Type": "application/zip", "Content-Length": str(len(body))},
                body,
            )
        }
    )
    package = fetch_package(
        session,
        url,
        tmp_path / "1261.zip",
        params=params,
        variant=params.variants[0],
        timeout=5,
    )
    assert package.size == len(body)


E0 = Path(__file__).parent / "fixtures" / "pl" / "e0" / "real_2026_10_16"
E0_FILES = json.loads((E0 / "files.json").read_text(encoding="utf-8"))


def _published(key: str) -> tuple[str, dict, bytes]:
    """URL, headers and the recorded first bytes of a published file."""
    entry = E0_FILES[key]
    head = (E0 / entry["head"]).read_bytes()
    return entry["url"], {**entry["headers"], "Content-Length": str(len(head))}, head


@pytest.mark.parametrize(
    ("key", "kind", "foreign"),
    [
        ("map10k_tiff", "tiff", "map10k_pdf"),
        ("map10k_pdf", "pdf", "geoid2021_txt"),
        ("geoid2021_txt", "txt", "map10k_tiff"),
    ],
)
def test_non_zip_files_checked_by_kind(tmp_path, key, kind, foreign):
    """A map sheet (TIFF, PDF) or a quasi-geoid model (TXT) is stored as
    published after a check of its content: TIFF magic, ``%PDF``, a text
    header. HTML at HTTP 200 and a file of another kind are a
    ``DownloadError`` and leave no file."""
    variant = PackageVariant(choice=(), url_template=None, file_kind=kind)
    params = UnitPackageParams(unit="sheet", variants=(variant,))
    url, headers, body = _published(key)

    def fetch(answer: tuple[int, dict, bytes]):
        staged = tmp_path / kind / "result"
        staged.parent.mkdir(exist_ok=True)
        session = FakePackageSession({url: answer})
        return staged, lambda: fetch_package(
            session,  # type: ignore[arg-type]
            url,
            staged,
            params=params,
            variant=variant,
            timeout=5,
        )

    staged, run = fetch((200, headers, body))
    package = run()
    assert (package.path, package.member) == (staged, None)
    assert staged.read_bytes() == body

    _, other_headers, other = _published(foreign)
    html = b"<html><body>Plik nie istnieje</body></html>"
    for answer in (
        (200, {**headers, "Content-Type": "text/html", "Content-Length": "44"}, html),
        (200, {**headers, "Content-Length": str(len(html))}, html),
        (200, other_headers, other),
    ):
        staged.unlink(missing_ok=True)
        staged, run = fetch(answer)
        with pytest.raises(DownloadError):
            run()
        assert list(staged.parent.iterdir()) == []
