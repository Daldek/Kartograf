"""Transaction prices (RCN): the real export ZIP of powiat 1201 (trimmed to three
features per layer, recorded 2026-10-16) and the recorded file heads."""

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pyogrio
import pytest

from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from kartograf.exceptions import ValidationError
from kartograf.notices import DOWNLOAD_SIZE
from kartograf.transport import unit_package
from tests.support.fake_packages import FakePackageSession

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl" / "rcn" / "real_2026_10_16"
FILES: dict = json.loads((FIXTURES / "files.json").read_text(encoding="utf-8"))
RECORDED_ZIP = FIXTURES / "1201_transakcje_ceny.gpkg.zip"
LAYERS = {"transakcje_dzialki", "transakcje_budynki", "transakcje_lokale"}


def _gpkg(tmp_path: Path, *, drop: str | None = None) -> bytes:
    """The recorded GeoPackage, optionally without one layer (built locally)."""
    path = tmp_path / "source.gpkg"
    with zipfile.ZipFile(RECORDED_ZIP) as archive:
        path.write_bytes(archive.read("1201_transakcje_ceny.gpkg"))
    if drop is not None:
        db = sqlite3.connect(path)
        with db:
            db.execute(f"DROP TABLE {drop}")
            db.execute("DELETE FROM gpkg_contents WHERE table_name = ?", (drop,))
        db.close()
    return path.read_bytes()


def _zip(member: str, data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, data)
    return buffer.getvalue()


def _session(key: str, body: bytes) -> FakePackageSession:
    entry = FILES[key]
    headers = {**entry["headers"], "Content-Length": str(len(body))}
    return FakePackageSession(
        {entry["url"]: (200, headers, body)}, heads={entry["url"]: entry["headers"]}
    )


def test_rcn_powiat_export_is_one_geopackage_of_three_layers(tmp_path, monkeypatch):
    """``--teryt 1201``: the GeoPackage of the export is stored (not the ZIP);
    SQLite opens only the local working copy, never a file in the store."""
    store, local = tmp_path / "store", tmp_path / "local"
    local.mkdir()
    monkeypatch.setattr(unit_package.tempfile, "tempdir", str(local))
    opened: list[Path] = []
    connect = sqlite3.connect

    def spy(database, *args, **kwargs):
        opened.append(Path(str(database).removeprefix("file:").split("?", 1)[0]))
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(unit_package.sqlite3, "connect", spy)
    fake = _session("rcn_1201", RECORDED_ZIP.read_bytes())
    monkeypatch.setattr(col, "_session", lambda: fake)
    url = FILES["rcn_1201"]["url"]

    report = download_collection(
        product="prices", teryt="1201", root=store, cache=False
    )

    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path == store / "cadastre/pl_rcn/teryt/1201.gpkg"
    assert {name for name, _ in pyogrio.list_layers(item.file.path)} == LAYERS
    for layer in LAYERS:
        assert pyogrio.read_info(item.file.path, layer=layer)["features"] == 3
    meta = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())
    assert meta["dataset"] == "pl.gugik.rcn"
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["request"] == {"teryt": "1201"}
    assert meta["extra"]["source"]["member"] == "1201_transakcje_ceny.gpkg"
    assert opened and all(path.is_relative_to(local) for path in opened)
    assert list(local.iterdir()) == []  # the working copy is gone
    assert fake.calls == [("HEAD", url), ("GET", url)]

    again = download_collection(product="prices", teryt="1201", root=store, cache=False)
    assert again.files[0].file.status == "local"
    assert fake.gets() == 1


def test_rcn_export_without_a_layer_is_not_stored(tmp_path, monkeypatch):
    """A GeoPackage without ``transakcje_lokale`` is not the RCN export: the
    unit fails as a download error and no version appears."""
    body = _zip("1201_transakcje_ceny.gpkg", _gpkg(tmp_path, drop="transakcje_lokale"))
    monkeypatch.setattr(col, "_session", lambda: _session("rcn_1201", body))
    store = tmp_path / "store"

    report = download_collection(
        product="prices", teryt="1201", root=store, cache=False
    )

    assert report.files == ()
    (failure,) = report.failed
    assert failure.kind == "download"
    assert "transakcje_lokale" in failure.error
    assert not [p for p in store.rglob("*") if p.is_file()]


def test_rcn_voivodeship_export_and_size_notice(tmp_path, monkeypatch):
    """``--teryt 12`` takes the voivodeship export; its recorded size (over
    100 MiB) is announced before the transfer. Another code length is an
    input error before any request."""
    body = _zip("12_transakcje_ceny.gpkg", _gpkg(tmp_path))
    fake = _session("rcn_12", body)
    monkeypatch.setattr(col, "_session", lambda: fake)
    url = FILES["rcn_12"]["url"]
    seen = []

    report = download_collection(
        product="prices",
        teryt="12",
        root=tmp_path / "store",
        cache=False,
        on_notice=lambda notice: seen.append((notice.code, fake.gets(url))),
    )

    assert report.ok, report.failed
    assert report.files[0].file.path.relative_to(tmp_path / "store").as_posix() == (
        "cadastre/pl_rcn/teryt/12.gpkg"
    )
    assert seen == [(DOWNLOAD_SIZE, 0)]
    assert "604038367 B" in report.notices[0].message
    with pytest.raises(ValidationError, match="Nieprawidlowy kod TERYT"):
        download_collection(product="prices", teryt="126", root=tmp_path)
    assert fake.calls == [("HEAD", url), ("GET", url)]


def test_rcn_has_no_national_file(tmp_path):
    """``--whole-country`` names the selections RCN has instead (K7)."""
    with pytest.raises(ValidationError, match="nie ma pliku krajowego.*--teryt"):
        download_collection(
            product="prices", country="pl", whole_country=True, root=tmp_path
        )
