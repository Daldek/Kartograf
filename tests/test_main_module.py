"""``python -m kartograf`` is the CLI (D20): the entry point of an environment
without the scripts directory on ``PATH`` (worktrees, ``uvx``)."""

import subprocess
import sys
from pathlib import Path

import kartograf


def test_python_dash_m_kartograf_runs_the_cli():
    # cwd must be the root of the tested tree: ``-m`` puts the working directory
    # first on ``sys.path`` (an editable install points at another checkout)
    root = Path(kartograf.__file__).resolve().parents[1]

    done = subprocess.run(
        [sys.executable, "-m", "kartograf", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("kartograf ")


def test_python_dash_m_kartograf_reports_errors_like_the_script():
    root = Path(kartograf.__file__).resolve().parents[1]

    done = subprocess.run(
        [sys.executable, "-m", "kartograf", "parse", "ABC"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert done.returncode == 2
    assert done.stderr.startswith("Error: ")
    assert done.stdout == ""
