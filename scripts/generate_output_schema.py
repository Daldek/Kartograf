"""Generate ``src/kartograf/_output_schema.py``: the ``outputSchema`` of every MCP tool.

AGI-5.5: the output schema of a tool is the result envelope. The vendored
``schemas/nogat/result-1.schema.json`` points into ``commands-1`` and ``error-1`` with
``$ref`` to other files, and a client resolves nothing outside the schema it was
given, so the generated schema is self-contained: the referenced definitions are
copied into ``$defs`` and the references point inside the document, ``$id`` is dropped
and the title names the tool (``kartograf-result/1``). A contract test
(``tests/contract/test_output_schema.py``) compares the module with this output.

Usage::

    uv run scripts/generate_output_schema.py            # write the module
    uv run scripts/generate_output_schema.py --check    # fail when the module is stale
"""

import argparse
import copy
import json
import pprint
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas" / "nogat"
MODULE = ROOT / "src" / "kartograf" / "_output_schema.py"
TITLE = "kartograf-result/1"
_REFERENCED = ("commands-1", "error-1")


def _load(name: str) -> dict[str, Any]:
    path = SCHEMAS / f"{name}.schema.json"
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def self_contained(
    result: dict[str, Any], others: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Return ``result`` with the definitions it takes from other files copied in.

    Parameters
    ----------
    result : dict
        The schema ``result-1``.
    others : dict
        The schemas it refers to by file name (``commands-1.schema.json``).

    Raises
    ------
    ValueError
        A reference that is not ``<file>#/$defs/<name>`` of a given file, a definition
        that clashes with one of ``result``, or a copied definition that itself has a
        reference (it would point into the wrong document).
    """
    schema = copy.deepcopy(result)
    definitions: dict[str, Any] = schema["$defs"]

    def walk(node: object) -> None:
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str) and not reference.startswith("#"):
                node["$ref"] = _import(reference)
            for value in list(node.values()):
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    def _import(reference: str) -> str:
        file_name, _, pointer = reference.partition("#")
        prefix = "/$defs/"
        if file_name not in others or not pointer.startswith(prefix):
            raise ValueError(f"cannot import {reference!r}")
        name = pointer.removeprefix(prefix)
        target = others[file_name]["$defs"][name]
        if name in definitions and definitions[name] != target:
            raise ValueError(f"the definition {name!r} clashes with one of result-1")
        if "$ref" in json.dumps(target):
            raise ValueError(f"the definition {name!r} has a reference of its own")
        definitions[name] = copy.deepcopy(target)
        return f"#/$defs/{name}"

    walk(schema)
    del schema["$id"]
    schema["title"] = TITLE
    return schema


def render() -> str:
    """Return the text of the generated module."""
    schema = self_contained(
        _load("result-1"), {f"{name}.schema.json": _load(name) for name in _REFERENCED}
    )
    body = pprint.pformat(schema, width=84, sort_dicts=False)
    lines = [
        '"""``outputSchema`` of every MCP tool (AGI-5.5), generated.',
        "",
        "The schema is ``kartograf-result/1``: ``schemas/nogat/result-1.schema.json``",
        "made self-contained by ``scripts/generate_output_schema.py``; do not edit.",
        '"""',
        "",
        "from typing import Any, Final",
        "",
        f"OUTPUT_SCHEMA: Final[dict[str, Any]] = {body}",
        "",
    ]
    return _formatted("\n".join(lines))


def _formatted(text: str) -> str:
    """Return ``text`` formatted by ruff with the settings of the project."""
    done = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", str(MODULE), "-"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return done.stdout


def main(argv: list[str] | None = None) -> int:
    """Write the module, or with ``--check`` fail when it is stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="do not write")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        if MODULE.read_text(encoding="utf-8") != text:
            print(f"{MODULE.relative_to(ROOT)} is stale: run generate_output_schema.py")
            return 1
        return 0
    MODULE.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
