"""
Build identifier for development versions of Kartograf.

``kartograf.__version__`` stays the static release string read by
``pyproject.toml``. :func:`build_version` extends a development version
(``"...dev..."``) with the git commit of the imported package, e.g.
``"0.7.0-dev+6db4408"`` or ``"0.7.0-dev+6db4408.dirty"`` when tracked files
inside the package directory have uncommitted changes. Release versions are
returned unchanged and never touch git.

The function is lazy (nothing runs at ``import kartograf``) and cached per
process. Any failure (no git, timeout, not a repository, package imported
from outside the repository) falls back to plain ``__version__``.
"""

import functools
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

GIT_TIMEOUT_S = 2.0


def _git(pkg_dir: Path, *args: str) -> str:
    """Run ``git -C <pkg_dir> <args>`` and return stripped stdout."""
    # GIT_DIR, GIT_WORK_TREE etc. would point git at another repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(
        ["git", "-C", str(pkg_dir), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
        check=True,
        env=env,
    )
    return result.stdout.strip()


@functools.cache
def build_version() -> str:
    """
    Return the package version with a commit identifier for dev builds.

    Returns
    -------
    str
        ``__version__`` for releases or when git information is unavailable;
        ``"<__version__>+<short sha>"`` for a clean development checkout;
        ``"<__version__>+<short sha>.dirty"`` when tracked files in the
        package directory differ from ``HEAD``.
    """
    import kartograf  # lazy: kartograf/__init__.py must not import this module

    version = kartograf.__version__
    if "dev" not in version:
        return version

    pkg_file = Path(kartograf.__file__).resolve()
    pkg_dir = pkg_file.parent
    try:
        toplevel = Path(_git(pkg_dir, "rev-parse", "--show-toplevel"))
        # The imported package must belong to this repository (not e.g. a
        # venv located inside some other git checkout).
        if not os.path.samefile(toplevel / "kartograf" / "__init__.py", pkg_file):
            return version
        sha = _git(pkg_dir, "rev-parse", "--short", "HEAD")
        if not sha:
            return version
        status = _git(
            pkg_dir,
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            str(pkg_dir),
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.debug("git build identifier unavailable: %s", exc)
        return version

    suffix = f"+{sha}"
    if status:
        suffix += ".dirty"
    return version + suffix
