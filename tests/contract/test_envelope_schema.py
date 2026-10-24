"""The envelope and the error document validate against the Nogat schemas (AGI-4.1).

``schemas/nogat/`` holds the vendored ``result-1``, ``error-1`` and ``commands-1``
schemas; ``result-1`` points into the other two (``command_name``, ``code``,
``reason``), so they are resolved together.
"""

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from kartograf.envelope import wrap
from kartograf.error_report import error_report
from kartograf.exceptions import (
    CacheError,
    ConfigError,
    DownloadError,
    ForbiddenError,
    InvalidSidecarError,
    MissingDependencyError,
    NoCoverageError,
    ParseError,
    UsageError,
    ValidationError,
    YearRangeError,
)
from kartograf.interrupt import Terminated
from kartograf.transform.crs import TransformError, TransformUnavailableError
from tests.contract.test_json_contract import DOCUMENTS, _data_report
from tests.unit.test_envelope import _failure, _file, _report

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas" / "nogat"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def _validator(name: str) -> jsonschema.Draft202012Validator:
    schemas = [_load(n) for n in ("result-1", "error-1", "commands-1")]
    registry: Registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return jsonschema.Draft202012Validator(_load(name), registry=registry)


def _documents():
    for schema, builders in DOCUMENTS.items():
        if schema in ("kartograf-error/1", "kartograf-result/1"):
            continue
        for build in builders:
            yield pytest.param(build(), id=f"{schema}:{build.__name__.strip('_')}")


@pytest.mark.parametrize("document", list(_documents()))
def test_the_envelope_of_every_document_validates(document):
    envelope = wrap("elevation download", document)

    _validator("result-1").validate(envelope.to_dict())


@pytest.mark.parametrize(
    ("document", "status"),
    [
        (_report(files=[_file("A")]), "ok"),
        (_report(files=[_file("A")], failed=[_failure("B")], ok=False), "partial"),
        (_report(failed=[_failure("B", "no_coverage")], ok=False), "failed"),
        (_report(ok=False), "failed"),
        (replace(_data_report(), ok=True), "ok"),  # type: ignore[type-var]
        (_data_report(), "partial"),
    ],
)
def test_every_status_of_a_batch_validates_with_its_items(document, status):
    envelope = wrap("elevation download", document)

    assert envelope.status == status
    _validator("result-1").validate(envelope.to_dict())


def test_a_status_without_the_units_it_needs_does_not_validate():
    """The schema ties ``partial`` and ``failed`` to the kinds of ``items``."""
    envelope = wrap("elevation download", _data_report()).to_dict()
    validator = _validator("result-1")

    validator.validate(envelope)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**envelope, "items": []})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**envelope, "status": "failed"})


@pytest.mark.parametrize(
    "error",
    [
        ValidationError("zly argument", option="product", allowed=("nmt", "nmpt")),
        UsageError("nieznana opcja --x", command="elevation download"),
        ParseError("zle godlo"),
        ConfigError("nogat.toml", option="NOGAT_CONFIG"),
        DownloadError("HTTP 503", sheet="N-34", status_code=503),
        NoCoverageError("brak danych", "N-34", 200, ("--scale 1:2000",)),
        YearRangeError(
            "poza latami", sheets={"N-34": (2020,)}, min_year=2000, max_year=2010
        ),
        CacheError("cache"),
        InvalidSidecarError("sidecar", path=Path("/store/a.meta.json")),
        MissingDependencyError("brak pakietu mcp", extra="mcp"),
        ForbiddenError(
            "sciezka poza katalogami",
            option="output_dir",
            path=Path("/poza"),
            allowed=["/dane"],
        ),
        TransformError("wynik nieskonczony"),
        TransformUnavailableError("brak operacji", remedy="zainstaluj siatki"),
        OSError(2, "No such file", "/nie/ma"),
        KeyboardInterrupt(),
        Terminated(),
        RuntimeError("blad programu"),
    ],
    ids=lambda error: type(error).__name__,
)
def test_the_error_document_of_every_failure_validates(error):
    document = error_report(error, command="elevation download").to_dict()

    _validator("error-1").validate(document)
    # the exit code is the one of the registry for the code (also checked by the schema)
    assert document["exit_code"] in {1, 2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 130, 143}
