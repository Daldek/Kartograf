"""Testy obowiazkowego sidecara (emit_sidecar(required=True), ADR-030 errata 2 N-1)."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from kartograf.exceptions import DownloadError
from kartograf.sources.sidecar import emit_sidecar

ASC_HEAD = (
    Path(__file__).parent
    / "fixtures"
    / "gugik_asc"
    / "77912_1384976_7.125.11.19.head.asc"
)


# godlo naglowka 77912 (placeholder "G" z briefu nie przechodzi build_metadata)
GODLO = "7.125.11.19"


def _data(tmp_path):
    p = tmp_path / "x.asc"
    p.write_bytes(ASC_HEAD.read_bytes())  # realny naglowek 77912
    return p


def test_required_sidecar_written_atomically(tmp_path):
    path = emit_sidecar(
        "pl.gugik.nmt_1m", _data(tmp_path), request={"godlo": GODLO}, required=True
    )
    assert path.exists() and json.loads(path.read_text())["request"] == {"godlo": GODLO}
    assert not list(tmp_path.glob("*.tmp"))


def test_required_sidecar_failure_raises_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kartograf.sources.sidecar.os.replace", Mock(side_effect=OSError("dysk pelny"))
    )
    with pytest.raises(DownloadError, match="obowiazkowego sidecara") as exc:
        emit_sidecar(
            "pl.gugik.nmt_1m", _data(tmp_path), request={"godlo": GODLO}, required=True
        )
    assert str(exc.value.__cause__) == "dysk pelny"  # porazka zapisu, nie budowy
    assert not (tmp_path / "x.asc.meta.json").exists() and not list(
        tmp_path.glob("*.tmp")
    )


def test_required_sidecar_build_error_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kartograf.sources.sidecar.build_metadata", Mock(side_effect=ValueError("x"))
    )
    with pytest.raises(DownloadError):
        emit_sidecar("pl.gugik.nmt_1m", _data(tmp_path), request={}, required=True)


@pytest.mark.parametrize("key", [None, Mock()])
def test_required_sidecar_without_descriptor_raises(tmp_path, key):
    with pytest.raises(DownloadError, match="deskryptor"):
        emit_sidecar(key, _data(tmp_path), request={}, required=True)


def test_best_effort_default_unchanged(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(
        "kartograf.sources.sidecar.build_metadata", Mock(side_effect=ValueError("x"))
    )
    assert (
        emit_sidecar("pl.gugik.nmt_1m", _data(tmp_path), request={}) is None
    )  # warning, bez wyjatku
    assert "Nie udalo sie zapisac sidecara" in caplog.text
