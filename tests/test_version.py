"""Tests for kartograf._version.build_version (dev build identifier)."""

import subprocess
from pathlib import Path

import pytest

import kartograf
from kartograf import _version
from kartograf._version import build_version

PKG_DIR = Path(kartograf.__file__).resolve().parent
TOPLEVEL = str(PKG_DIR.parent)


@pytest.fixture(autouse=True)
def _reset_cache():
    build_version.cache_clear()
    yield
    build_version.cache_clear()


def _fake_git(*, sha="abc1234", status="", toplevel=TOPLEVEL, calls=None):
    """Return a fake ``subprocess.run`` answering the three git queries."""

    def run(cmd, **kwargs):
        if calls is not None:
            calls.append((cmd, kwargs))
        if "--show-toplevel" in cmd:
            out = toplevel + "\n"
        elif "--short" in cmd:
            out = sha + "\n"
        elif "status" in cmd:
            out = status
        else:  # pragma: no cover - unexpected command
            raise AssertionError(f"unexpected git call: {cmd}")
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return run


@pytest.fixture
def dev_version(monkeypatch):
    monkeypatch.setattr(kartograf, "__version__", "0.7.0-dev")


class TestBuildVersion:
    def test_release_version_skips_git(self, monkeypatch):
        monkeypatch.setattr(kartograf, "__version__", "0.7.0")
        calls = []
        monkeypatch.setattr(_version.subprocess, "run", _fake_git(calls=calls))
        assert build_version() == "0.7.0"
        assert calls == []

    def test_dev_clean_appends_sha(self, monkeypatch, dev_version):
        monkeypatch.setattr(_version.subprocess, "run", _fake_git())
        assert build_version() == "0.7.0-dev+abc1234"

    def test_dev_dirty_appends_dirty(self, monkeypatch, dev_version):
        monkeypatch.setattr(
            _version.subprocess, "run", _fake_git(status=" M kartograf/x.py\n")
        )
        assert build_version() == "0.7.0-dev+abc1234.dirty"

    def test_git_calls_are_safe(self, monkeypatch, dev_version):
        calls = []
        monkeypatch.setattr(_version.subprocess, "run", _fake_git(calls=calls))
        build_version()
        assert len(calls) == 3
        for cmd, kwargs in calls:
            assert isinstance(cmd, list)
            assert cmd[0] == "git"
            assert cmd[1:3] == ["-C", str(PKG_DIR)]
            assert not kwargs.get("shell")
            assert kwargs.get("timeout")
            assert kwargs.get("check") is True
            env = kwargs.get("env")
            assert env is not None
            assert not any(k.startswith("GIT_") for k in env)
        status_cmd = calls[2][0]
        assert "--untracked-files=no" in status_cmd
        assert status_cmd[-2:] == ["--", str(PKG_DIR)]

    def test_git_env_vars_are_dropped(self, monkeypatch, dev_version):
        monkeypatch.setenv("GIT_DIR", "/nonexistent")
        monkeypatch.setenv("GIT_WORK_TREE", "/nonexistent")
        calls = []
        monkeypatch.setattr(_version.subprocess, "run", _fake_git(calls=calls))
        build_version()
        for _cmd, kwargs in calls:
            assert "GIT_DIR" not in kwargs["env"]
            assert "GIT_WORK_TREE" not in kwargs["env"]

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError("git"),
            subprocess.TimeoutExpired(["git"], 2),
            subprocess.CalledProcessError(128, ["git"]),
            PermissionError("git"),
        ],
    )
    def test_git_failure_returns_plain_version(self, monkeypatch, dev_version, exc):
        def boom(cmd, **kwargs):
            raise exc

        monkeypatch.setattr(_version.subprocess, "run", boom)
        assert build_version() == "0.7.0-dev"

    def test_foreign_repo_returns_plain_version(
        self, monkeypatch, dev_version, tmp_path
    ):
        # Package imported from a venv living in another repository.
        (tmp_path / "kartograf").mkdir()
        (tmp_path / "kartograf" / "__init__.py").write_text("")
        monkeypatch.setattr(
            _version.subprocess, "run", _fake_git(toplevel=str(tmp_path))
        )
        assert build_version() == "0.7.0-dev"

    def test_toplevel_without_package_returns_plain_version(
        self, monkeypatch, dev_version, tmp_path
    ):
        monkeypatch.setattr(
            _version.subprocess, "run", _fake_git(toplevel=str(tmp_path))
        )
        assert build_version() == "0.7.0-dev"

    def test_empty_sha_returns_plain_version(self, monkeypatch, dev_version):
        monkeypatch.setattr(_version.subprocess, "run", _fake_git(sha=""))
        assert build_version() == "0.7.0-dev"

    def test_result_is_cached(self, monkeypatch, dev_version):
        calls = []
        monkeypatch.setattr(_version.subprocess, "run", _fake_git(calls=calls))
        assert build_version() == build_version() == "0.7.0-dev+abc1234"
        assert len(calls) == 3

    def test_import_does_not_call_git(self):
        code = (
            "import subprocess, sys\n"
            "def boom(*a, **k): raise AssertionError('git at import')\n"
            "subprocess.run = boom\n"
            "import kartograf, kartograf.cli.commands, kartograf.sources.sidecar\n"
        )
        result = subprocess.run(
            [__import__("sys").executable, "-c", code],
            cwd=TOPLEVEL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr


class TestVersionUsage:
    def test_sidecar_uses_build_version(self, monkeypatch):
        from kartograf.sources import sidecar
        from kartograf.sources.registry import get_source

        monkeypatch.setattr(sidecar, "build_version", lambda: "9.9.9-dev+feed123")
        meta = sidecar.build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"godlo": "N-34-130-D-d-2-4"},
            vertical_crs="EVRF2007",
        )
        assert meta.kartograf_version == "9.9.9-dev+feed123"

    def test_cli_version_uses_build_version(self, monkeypatch, capsys):
        from kartograf.cli import _parser
        from kartograf.cli.commands import main

        monkeypatch.setattr(_parser, "build_version", lambda: "9.9.9-dev+feed123")
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        assert capsys.readouterr().out.strip() == "kartograf 9.9.9-dev+feed123"
