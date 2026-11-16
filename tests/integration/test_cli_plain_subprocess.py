"""A plain write (``--output-dir``) by ``kartograf`` in a process of its own, offline.

The in-process tests of ``tests/integration/test_cli_plain_output.py`` call
``main``; these start a process with the environment of a user
(``tests.support.offline_process``: dead proxies, the default store in the test
directory) and read what it leaves: the exit code, the document on stdout or the
last line of stderr, the files on disk. No source of Kartograf can be replaced from
the command line, so a write runs ``tests/support/plain_driver.py`` (the real
command, the PL sheets of a fake index); the refusals, which come before any
request, run the installed ``kartograf`` script itself.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any

from kartograf.marker import MARKER
from tests.integration.test_manager_campaigns import G
from tests.support.errors import error_document
from tests.support.offline_process import offline_env

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 120.0
NMT = [
    *("elevation", "download", "--product", "nmt", "--sheet", G),
    *("--resolution", "1m", "--vertical-crs", "EVRF2007"),
]


def listing(directory: Path) -> list[str]:
    return sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*"))


def kartograf_script() -> str:
    """The ``kartograf`` console script installed beside this interpreter."""
    script = shutil.which("kartograf", path=sysconfig.get_path("scripts"))
    assert script is not None, "the kartograf console script is not installed"
    return script


def run(
    tmp_path: Path, command: list[str], *arguments: str | Path
) -> subprocess.CompletedProcess[str]:
    """Run ``command`` with ``arguments`` offline; the default store is in tmp_path."""
    env = offline_env(tmp_path) | {"KARTOGRAF_ROOT": str(tmp_path / "default-store")}
    return subprocess.run(
        [*command, *map(str, arguments)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=LIMIT,
        check=False,
    )


def same_path(reported: Any, expected: Path) -> bool:
    return (
        isinstance(reported, str) and Path(reported).as_posix() == expected.as_posix()
    )


def test_a_plain_write_in_its_own_process_lists_the_file_it_wrote(tmp_path):
    out = tmp_path / "out"

    done = run(
        tmp_path,
        [sys.executable, "-m", "tests.support.plain_driver"],
        *NMT,
        "--output-dir",
        out,
        "--json",
    )

    assert done.returncode == 0, done.stderr
    document = json.loads(done.stdout)
    assert (document["schema"], document["command"], document["status"]) == (
        "kartograf-result/1",
        "elevation download",
        "ok",
    )
    report = document["result"]
    assert (report["mode"], report["root"]) == ("plain", None)
    assert same_path(report["output_dir"], out)
    (entry,) = report["files"]
    body = (out / f"{G}.asc").read_bytes()
    assert same_path(entry.pop("path"), out / f"{G}.asc")
    assert entry == {
        "unit": G,
        "country": "PL",
        "size_bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "status": "written",
    }
    assert listing(out) == [f"{G}.asc"]  # no staging directory, no sidecar
    assert not (tmp_path / "default-store").exists()


def test_the_script_refuses_an_output_dir_inside_a_store_before_any_request(
    tmp_path,
):
    store = tmp_path / "store"
    store.mkdir()
    (store / MARKER).write_text("{}", encoding="utf-8")

    done = run(tmp_path, [kartograf_script()], *NMT, "--output-dir", store / "sub")

    assert (done.returncode, done.stdout) == (4, "")
    document = error_document(done.stderr)
    assert (document["code"], document["details"]["reason"]) == (
        "conflict",
        "output_in_store",
    )
    assert listing(store) == [MARKER]
    assert not (tmp_path / "default-store").exists()


def test_the_script_refuses_root_beside_output_dir_as_a_usage_error(tmp_path):
    root, out = tmp_path / "root", tmp_path / "out"

    done = run(
        tmp_path, [kartograf_script()], *NMT, "--output-dir", out, "--root", root
    )

    assert (done.returncode, done.stdout) == (2, "")
    document = error_document(done.stderr)
    assert document["code"] == "validation_error"
    assert (document["details"]["reason"], document["details"]["option"]) == (
        "exclusive_options",
        "root",
    )
    assert not root.exists() and not out.exists()
    assert not (tmp_path / "default-store").exists()
