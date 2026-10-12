"""Offline CLI/API parity helpers shared by the download scenario tests.

Freeze ``frozen_clock`` in the calling test before running both paths. The API
callback receives its own output store; the CLI receives ``-o`` automatically.
"""

import contextlib
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from kartograf.cli import main
from kartograf.exceptions import KartografError


@dataclass(frozen=True)
class ParityRun:
    """CLI output and API outcome from the same invocation context."""

    cli_store: Path
    api_store: Path
    cli_code: int
    cli_stdout: str
    cli_stderr: str
    api_result: object | None
    api_error: KartografError | TypeError | None


def run_both(
    cli_argv: list[str], api_call: Callable[[Path], object], tmp_path: Path
) -> ParityRun:
    """Run CLI and API with separate stores, the same cwd, and captured CLI output.

    Expected API input errors are returned as ``api_error`` for comparison
    with the CLI error line. Unexpected exceptions propagate as test failures.
    """
    cli_store, api_store = tmp_path / "cli", tmp_path / "api"
    stdout, stderr = io.StringIO(), io.StringIO()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(tmp_path)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                cli_code = main([*cli_argv, "-o", str(cli_store)])
            except SystemExit as exc:
                if not isinstance(exc.code, int):
                    raise
                cli_code = exc.code
        try:
            api_result = api_call(api_store)
            api_error = None
        except (KartografError, TypeError) as exc:
            api_result = None
            api_error = exc
    return ParityRun(
        cli_store,
        api_store,
        cli_code,
        stdout.getvalue(),
        stderr.getvalue(),
        api_result,
        api_error,
    )


def assert_same_store(a: Path, b: Path) -> None:
    """Assert identical relative tree paths and file bytes, including sidecars."""
    a_entries = {p.relative_to(a): p for p in a.rglob("*")}
    b_entries = {p.relative_to(b): p for p in b.rglob("*")}
    for relative in sorted(a_entries.keys() | b_entries.keys()):
        left, right = a_entries.get(relative), b_entries.get(relative)
        assert left is not None, f"Only in {b.name}: {relative}"
        assert right is not None, f"Only in {a.name}: {relative}"
        assert left.is_file() == right.is_file(), f"Different entry type: {relative}"
        if left.is_file():
            assert left.read_bytes() == right.read_bytes(), (
                f"Different bytes: {relative}"
            )
