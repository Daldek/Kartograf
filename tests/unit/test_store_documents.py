"""Store reader documents (``kartograf-store-*/1``, spec 5.4.10, ADR-045)."""

import json
import os
from pathlib import Path

import pytest

from kartograf.exceptions import InvalidSidecarError, ValidationError
from kartograf.store_documents import (
    StoreOverview,
    describe_store,
    list_store_entries,
    read_store_sidecar,
)
from tests.integration.test_store_api import (
    HIERARCHY,
    SEGMENT,
    SHEET,
    _data,
    _linked,
    _meta,
    _version,
)


def _three_entries(root: Path) -> None:
    """A link and its version (two entries) plus a second sheet's file."""
    version = _version(root, SEGMENT, HIERARCHY, "2024", f"{SHEET}.asc")
    _linked(root / SEGMENT / HIERARCHY / f"{SHEET}.asc", version)
    _data(root / SEGMENT / "N-34/130/D/d/2/3" / "N-34-130-D-d-2-3.asc")


def test_describe_store_lists_segments_with_info(tmp_path):
    root = tmp_path / "data"
    _data(root / SEGMENT / HIERARCHY / f"{SHEET}.asc")
    (root / "own" / "dir").mkdir(parents=True)

    overview = describe_store(root)

    assert isinstance(overview, StoreOverview)
    assert [(s.segment, s.known) for s in overview.segments] == [
        ("nmt/pl_1992_1m_evrf2007", True),
        ("own/dir", False),
    ]
    body = overview.to_dict()
    assert list(body) == ["schema", "output_dir", "segments"]
    assert body["schema"] == "kartograf-store-overview/1"
    nmt = body["segments"][0]
    assert list(nmt) == [
        "segment",
        "product",
        "country",
        "dataset_key",
        "name",
        "known",
    ]
    assert (nmt["product"], nmt["dataset_key"]) == ("nmt", "pl.gugik.nmt_1m")
    assert body["segments"][1]["product"] is None


def test_describe_store_missing_output_dir_is_oserror(tmp_path):
    with pytest.raises(OSError):
        describe_store(tmp_path / "brak")


def test_entries_limit_and_truncated(tmp_path):
    root = tmp_path / "data"
    _three_entries(root)

    cut = list_store_entries(root, segment=SEGMENT, limit=2)
    full = list_store_entries(root, segment=SEGMENT, limit=3)
    roomy = list_store_entries(root, segment=SEGMENT, limit=50)

    assert (len(cut.entries), cut.truncated) == (2, True)
    assert (len(full.entries), full.truncated) == (3, False)
    assert (len(roomy.entries), roomy.truncated) == (3, False)
    assert cut.entries == full.entries[:2]
    assert (cut.limit, full.limit) == (2, 3)


def test_entries_require_segment_and_a_positive_limit(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    for limit in (0, -1):
        with pytest.raises(ValidationError) as small:
            list_store_entries(root, segment=SEGMENT, limit=limit)
        assert small.value.option == "limit"
    with pytest.raises(ValidationError) as text:
        list_store_entries(root, segment=SEGMENT, limit="10")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as flag:
        list_store_entries(root, segment=SEGMENT, limit=True)
    with pytest.raises(ValidationError) as none:
        list_store_entries(root, segment=None, limit=5)  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as bad:
        list_store_entries(root, segment="zly", limit=5)
    assert (text.value.option, flag.value.option) == ("limit", "limit")
    assert (none.value.option, bad.value.option) == ("segment", "segment")


def test_entries_of_a_missing_store_is_oserror(tmp_path):
    with pytest.raises(OSError):
        list_store_entries(tmp_path / "brak", segment=SEGMENT, limit=1)


def test_unit_of_a_sidecar_selects_the_same_unit_again(tmp_path):
    root = tmp_path / "data"
    segment = "names/pl_prng_shp"
    request = {"whole_country": True, "country": "pl"}
    version = _version(
        root, segment, "country", "2026", "pl_miejscowosci.zip", request=request
    )
    link = root / segment / "country" / "pl_miejscowosci.zip"
    _linked(link, version)
    _meta(link, request=request)
    _version(root, segment, "country", "2026", "pl_other.zip", b"other")

    everything = list_store_entries(root, segment=segment, limit=50)
    unit = next(
        entry.sidecar.unit
        for entry in everything.entries
        if entry.kind == "link" and entry.sidecar is not None
    )
    again = list_store_entries(root, segment=segment, units=[unit], limit=50)

    assert unit == "pl_miejscowosci"
    assert {e.path for e in again.entries} == {link, version}
    assert again.units == ("pl_miejscowosci",)
    assert everything.units is None
    assert len(everything.entries) > len(again.entries)


@pytest.mark.parametrize("unit", ["versions", "full_sheet", "kampanie", "x" * 300])
def test_reserved_unit_option_units(tmp_path, unit):
    root = tmp_path / "data"
    root.mkdir()

    with pytest.raises(ValidationError) as caught:
        list_store_entries(root, segment=SEGMENT, units=[unit], limit=5)

    assert caught.value.option == "units"


def test_units_given_as_text_is_refused_not_split_into_letters(tmp_path):
    root = tmp_path / "data"
    root.mkdir()

    with pytest.raises(ValidationError) as caught:
        list_store_entries(root, segment=SEGMENT, units=SHEET, limit=5)  # type: ignore[arg-type]

    assert caught.value.option == "units"


def test_units_may_be_any_iterable(tmp_path):
    root = tmp_path / "data"
    _three_entries(root)

    result = list_store_entries(
        root, segment=SEGMENT, units=(code for code in [SHEET]), limit=50
    )

    assert result.units == (SHEET,)
    assert {e.hierarchy for e in result.entries} == {HIERARCHY}


def test_entries_document_omits_raw_and_sidecar_document_keeps_it(tmp_path):
    root = tmp_path / "data"
    data = _data(root / SEGMENT / HIERARCHY / f"{SHEET}.asc")

    entries = list_store_entries(root, segment=SEGMENT, limit=5).to_dict()
    sidecar = read_store_sidecar(data).to_dict()

    first = entries["entries"][0]
    assert list(entries) == [
        "schema",
        "output_dir",
        "segment",
        "units",
        "limit",
        "truncated",
        "entries",
    ]
    assert first["sidecar"] is not None and "raw" not in first["sidecar"]
    assert first["sidecar"]["dataset_key"] == "pl.gugik.nmt_1m"
    assert sidecar["schema"] == "kartograf-store-sidecar/1"
    assert list(sidecar) == ["schema", "path", "sidecar"]
    assert sidecar["sidecar"]["raw"]["dataset"] == "pl.gugik.nmt_1m"
    assert json.loads(read_store_sidecar(data).to_json()) == sidecar


def test_read_store_sidecar_missing_file_is_invalid_sidecar_error(tmp_path):
    missing = tmp_path / "brak.asc"

    with pytest.raises(InvalidSidecarError) as caught:
        read_store_sidecar(missing)

    assert caught.value.code == "invalid_sidecar"
    assert caught.value.path == missing.with_name("brak.asc.meta.json")


def test_bare_sidecar_without_schema_reads_with_schema_constant(tmp_path):
    """A provider without a descriptor writes the ``emit_sidecar`` shape (no
    ``schema``); the document still shows ``kartograf-meta/1``."""
    data = tmp_path / "plik.asc"
    data.write_bytes(b"x")
    bare = {"sha256": "a" * 64, "size_bytes": 1, "extra": {"note": "n"}}
    data.with_name("plik.asc.meta.json").write_text(json.dumps(bare), encoding="utf-8")

    body = read_store_sidecar(data).to_dict()["sidecar"]

    assert body["schema"] == "kartograf-meta/1"
    assert "schema" not in body["raw"]
    assert body["raw"] == bare


def test_paths_are_absolute_for_a_relative_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _three_entries(tmp_path / "data")

    overview = describe_store("data").to_dict()
    entries = list_store_entries("data", segment=SEGMENT, limit=5).to_dict()
    sidecar = read_store_sidecar(f"data/{SEGMENT}/{HIERARCHY}/{SHEET}.asc").to_dict()

    root = (tmp_path / "data").as_posix()
    assert overview["output_dir"] == entries["output_dir"] == root
    assert all(
        os.path.isabs(e["path"]) and e["path"].startswith(root)
        for e in entries["entries"]
    )
    assert any(e["version_path"] for e in entries["entries"])
    assert sidecar["path"] == f"{root}/{SEGMENT}/{HIERARCHY}/{SHEET}.asc"
