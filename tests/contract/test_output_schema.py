"""The ``outputSchema`` of the MCP tools is ``result-1`` made self-contained (AGI-5.5).

``src/kartograf/_output_schema.py`` is generated from the vendored Nogat schemas
(``scripts/generate_output_schema.py``): the module must equal the generator output,
and the schema must decide like the vendored ``result-1`` with its two neighbours,
without resolving anything outside itself (a client does not).
"""

import copy
import importlib.util
import json
import re
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest
from referencing import Registry

from kartograf._output_schema import OUTPUT_SCHEMA
from kartograf.envelope import wrap
from tests.contract.test_envelope_schema import _validator
from tests.contract.test_json_contract import DOCUMENTS, _data_report
from tests.unit.test_envelope import _failure, _file, _report

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "kartograf" / "_output_schema.py"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_output_schema", ROOT / "scripts" / "generate_output_schema.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _own() -> jsonschema.Draft202012Validator:
    """The schema as a client has it: an empty registry, nothing else to read."""
    return jsonschema.Draft202012Validator(OUTPUT_SCHEMA, registry=Registry())


def _valid_envelopes() -> list[dict[str, Any]]:
    envelopes = [
        wrap("elevation download", build()).to_dict()
        for schema, builders in DOCUMENTS.items()
        if schema not in ("kartograf-error/1", "kartograf-result/1")
        for build in builders
    ]
    envelopes += [
        wrap("elevation download", _report(files=[_file("A")])).to_dict(),
        wrap(
            "elevation download",
            _report(files=[_file("A")], failed=[_failure("B")], ok=False),
        ).to_dict(),
        wrap(
            "elevation download",
            _report(failed=[_failure("B", "no_coverage")], ok=False),
        ).to_dict(),
        wrap("elevation download", replace(_data_report(), ok=True)).to_dict(),  # type: ignore[type-var]
    ]
    return envelopes


def _broken(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    """Envelopes that break one rule of the schema."""

    def changed(**changes: object) -> dict[str, Any]:
        return {**copy.deepcopy(envelope), **changes}

    failed = wrap("elevation download", _data_report()).to_dict()
    return [
        changed(command="Elevation Download"),
        changed(status="done"),
        changed(check="yes"),
        changed(result={"no_schema_key": 1}),
        changed(notices=[{"level": "debug", "code": "x", "message": "m"}]),
        changed(page={"truncated": True}),
        {**failed, "items": []},
        {**failed, "status": "failed"},
        {
            **failed,
            "items": [{"id": "a", "status": "failed", "code": "not_a_registry_code"}],
        },
        {key: value for key, value in envelope.items() if key != "status"},
    ]


def test_the_module_equals_the_generator_output():
    assert MODULE.read_text(encoding="utf-8") == _generator().render()


def test_the_schema_points_only_inside_itself():
    text = json.dumps(OUTPUT_SCHEMA)
    references = re.findall(r'"\$ref": "([^"]+)"', text)
    definitions = OUTPUT_SCHEMA["$defs"]

    assert "$id" not in OUTPUT_SCHEMA
    assert OUTPUT_SCHEMA["title"] == "kartograf-result/1"
    assert references
    assert all(reference.startswith("#/$defs/") for reference in references)
    assert {reference.removeprefix("#/$defs/") for reference in references} <= set(
        definitions
    )
    # the definitions that came from the neighbouring schemas
    assert {"command_name", "code", "reason"} <= set(definitions)
    jsonschema.Draft202012Validator.check_schema(OUTPUT_SCHEMA)


def test_the_generator_refuses_a_reference_it_cannot_import():
    generator = _generator()
    result = {
        "$id": "x",
        "$defs": {},
        "properties": {"a": {"$ref": "other.schema.json#/$defs/missing_file"}},
    }

    with pytest.raises(ValueError, match="cannot import"):
        generator.self_contained(result, {})
    clash = {"$id": "x", "$defs": {"code": {"type": "null"}}}
    clash["properties"] = {"a": {"$ref": "o.schema.json#/$defs/code"}}  # type: ignore[assignment]
    with pytest.raises(ValueError, match="clashes"):
        generator.self_contained(clash, {"o.schema.json": {"$defs": {"code": {}}}})


@pytest.mark.parametrize("envelope", _valid_envelopes(), ids=lambda e: e["command"])
def test_it_accepts_what_the_vendored_schema_accepts(envelope):
    _validator("result-1").validate(envelope)

    _own().validate(envelope)


@pytest.mark.parametrize("index", range(10))
def test_it_rejects_what_the_vendored_schema_rejects(index):
    base = wrap("elevation download", _report(files=[_file("A")])).to_dict()
    envelope = _broken(base)[index]

    assert not _validator("result-1").is_valid(envelope)
    assert not _own().is_valid(envelope)
