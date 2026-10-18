"""The exact keys of every JSON document, in order (spec 12.2, rule A3).

``CONTRACT`` copies the key tables of the spec: within ``/1`` only additions are
allowed, so a removed, renamed or reordered key is a failing test here and a
deliberate, reviewed edit of this table. Documents are built from fixtures in
this file, without a network.
"""

from collections.abc import Callable

import pytest

from kartograf.error_report import error_report
from kartograf.exceptions import ValidationError
from kartograf.serialization import Document


def _error_document() -> Document:
    exc = ValidationError("zly argument", option="product", allowed=("nmt", "nmpt"))
    return error_report(exc, command="elevation download")


# schema -> a document of that schema built without a network
DOCUMENTS: dict[str, Callable[[], Document]] = {
    "kartograf-error/1": _error_document,
}

# schema -> the keys of the document in order (``schema`` first)
CONTRACT: dict[str, list[str]] = {
    "kartograf-error/1": [
        "schema",
        "code",
        "message",
        "hint",
        "exception",
        "exit_code",
        "command",
        "details",
    ],
}


def test_every_contract_row_has_a_fixture_and_the_other_way_round():
    assert sorted(DOCUMENTS) == sorted(CONTRACT)


@pytest.mark.parametrize("schema", sorted(CONTRACT))
def test_document_keys_and_their_order(schema):
    document = DOCUMENTS[schema]()

    data = document.to_dict()

    assert document.schema == schema
    assert list(data) == CONTRACT[schema]
    assert data["schema"] == schema
