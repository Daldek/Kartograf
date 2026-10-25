"""SIGINT and SIGTERM during a real plain write (DEV-19.7, ADR-054 decision 3).

A plain write leaves no partial target and no staging directory when the process is
interrupted. These tests start ``kartograf elevation download --output-dir`` in a
process of its own (``tests/support/interrupt_driver.py``: the command is real, its
source stops in the middle of a transfer), send the signal and look at the exit code,
at the error document and at what is left on disk: with and without ``--force`` over
a file that already exists.
"""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from kartograf.output import STAGING
from tests.integration.test_manager_campaigns import G

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX signals: SIGINT and SIGTERM"
)

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 60.0
OLD = b"old content of the target\n"
EXIT = {
    "sigint": (signal.SIGINT, 130, "cancelled"),
    "sigterm": (signal.SIGTERM, 143, "terminated"),
}
SHEET = [
    *("elevation", "download", "--product", "nmt", "--sheet", G),
    *("--resolution", "1m", "--vertical-crs", "EVRF2007"),
]


class Command:
    """The driver running ``kartograf`` in a process of its own."""

    def __init__(self, tmp_path: Path, *arguments: object) -> None:
        self.ready, self.release = tmp_path / "ready", tmp_path / "release"
        self.stdout, self.stderr = tmp_path / "stdout", tmp_path / "stderr"
        (tmp_path / "nogat.toml").write_text("", encoding="utf-8")
        dead = "http://127.0.0.1:9"
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("KARTOGRAF_", "NOGAT_"))
        }
        env |= {
            "KARTOGRAF_DATA_DIR": str(tmp_path / "data"),
            "KARTOGRAF_CACHE_DIR": str(tmp_path / "cache"),
            "NOGAT_CONFIG": str(tmp_path / "nogat.toml"),
            "HTTP_PROXY": dead,
            "HTTPS_PROXY": dead,
            "ALL_PROXY": dead,
            "NO_PROXY": "",
        }
        with self.stdout.open("wb") as out, self.stderr.open("wb") as err:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    *("-m", "tests.support.interrupt_driver"),
                    str(self.ready),
                    str(self.release),
                    *map(str, arguments),
                ],
                cwd=ROOT,
                stdout=out,
                stderr=err,
                env=env,
            )

    def errors(self) -> str:
        return self.stderr.read_text(encoding="utf-8")

    def until(self, done: Callable[[], bool], what: str) -> None:
        """Wait (a minute at most) until ``done()``; fail if the command ends first."""
        deadline = time.monotonic() + LIMIT
        while not done():
            ended = self.process.poll() is not None
            if ended or time.monotonic() > deadline:
                state = "ended before it could" if ended else "did not"
                raise AssertionError(f"kartograf {state} {what}\n{self.errors()}")
            time.sleep(0.02)

    def interrupted(self, how: str) -> int:
        """Signal the command once its transfer is half done; its exit status."""
        self.until(self.ready.exists, "stop in the middle of the transfer")
        self.process.send_signal(EXIT[how][0])
        try:
            return self.process.wait(timeout=LIMIT)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"kartograf did not end\n{self.errors()}") from None

    def error_document(self) -> dict[str, object]:
        """The error document of the last line of stderr."""
        document: dict[str, object] = json.loads(self.errors().splitlines()[-1])
        return document


@pytest.fixture
def start(tmp_path):
    """Start the driver; a command still alive when the test ends is killed."""
    started: list[Command] = []

    def run(*arguments: object) -> Command:
        started.append(Command(tmp_path, *arguments))
        return started[-1]

    yield run
    for command in started:
        if command.process.poll() is None:
            command.process.kill()
        command.process.wait()


@pytest.mark.parametrize("how", list(EXIT))
def test_an_interrupted_forced_write_leaves_no_staging_and_the_old_file(
    start, tmp_path, how
):
    out = tmp_path / "out"
    target = out / f"{G}.asc"
    out.mkdir()
    target.write_bytes(OLD)
    command = start(*SHEET, "--output-dir", out, "--force")

    command.until(command.ready.exists, "stop in the middle of the transfer")
    staged = list((out / STAGING).rglob("*.asc"))  # the half file is in the staging
    assert [path.name for path in staged] == [target.name]
    status = command.interrupted(how)

    _, code, name = EXIT[how]
    assert status == code, command.errors()
    assert not (out / STAGING).exists()
    assert target.read_bytes() == OLD  # replaced only after the transfer is verified
    assert sorted(path.name for path in out.iterdir()) == [target.name]
    assert command.error_document()["code"] == name
    printed = command.stdout.read_text(encoding="utf-8")
    assert "zapisano" not in printed and "zastapiono" not in printed
    assert "Traceback" not in command.errors()


@pytest.mark.parametrize("how", list(EXIT))
def test_an_interrupted_first_write_leaves_no_target_and_no_staging(
    start, tmp_path, how
):
    out = tmp_path / "out"
    command = start(*SHEET, "-o", out)

    status = command.interrupted(how)

    _, code, name = EXIT[how]
    assert status == code, command.errors()
    assert not (out / STAGING).exists()
    assert list(out.glob("*.asc")) == []  # no partial target
    assert command.error_document()["code"] == name
    assert "Traceback" not in command.errors()
