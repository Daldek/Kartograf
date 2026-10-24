"""The error module is generated from the vendored Nogat registry (ERR-3)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import jsonschema
import pytest

from kartograf import _errors

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "schemas" / "nogat" / "error_registry.json"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_errors", ROOT / "scripts" / "generate_errors.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_error_module_equals_the_generator_output():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    generated = _generator().render(registry)

    assert (ROOT / "src" / "kartograf" / "_errors.py").read_text(
        encoding="utf-8"
    ) == generated


def test_error_module_carries_every_code_and_outcome_of_the_registry():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert registry["standard_version"] == _errors.STANDARD_VERSION
    assert [c.code for c in _errors.CODES] == [e["code"] for e in registry["errors"]]
    assert _errors.BY_CODE["no_data"].exit_code == 14
    assert {
        o["status"]: o["exit_code"] for o in registry["outcomes"]
    } == _errors.OUTCOMES


@pytest.mark.parametrize("name", ["result-1", "error-1", "commands-1"])
def test_vendored_schema_is_a_valid_json_schema(name):
    path = ROOT / "schemas" / "nogat" / f"{name}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator.check_schema(schema)


def test_vendored_error_schema_lists_the_registry_codes():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    path = ROOT / "schemas" / "nogat" / "error-1.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema["$defs"]["code"]["enum"] == [e["code"] for e in registry["errors"]]
