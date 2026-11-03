"""Offline stand-in for a store on an SMB share mounted without ``serverino``.

The Linux cifs client then gives two names of one file different inode
numbers (``samefile`` is false for a hardlink) and reports ``st_nlink == 1``
for a path it has just opened - a read of that path included - for a few
seconds, sometimes longer. Both are simulated on top of a real hardlink, so
the files keep their real inodes and link counts. Patch inside
``with monkeypatch.context() as smb:`` and assert on the real inodes and link
counts after the block.
"""

import os
import stat
from pathlib import Path

import pytest

# fields of the stat tuple; the other ``st_*`` attributes are not in it
_TUPLE_FIELDS = (
    "st_mode",
    "st_ino",
    "st_dev",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_size",
)


def no_stable_inodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """``os.path.samefile`` is false for every pair of names."""
    monkeypatch.setattr(os.path, "samefile", lambda first, second: False)


def report_one_link(monkeypatch: pytest.MonkeyPatch, *paths: Path) -> None:
    """``os.stat``/``os.lstat`` report ``st_nlink == 1`` for ``paths``
    (for every path when none is given)."""
    only = {os.path.abspath(path) for path in paths}

    def faked(real):
        def call(path, *args, **kwargs):
            result = real(path, *args, **kwargs)
            if not isinstance(path, str | os.PathLike):
                return result
            if only and os.path.abspath(path) not in only:
                return result
            fields = list(result)
            fields[stat.ST_NLINK] = 1
            extra = {
                name: getattr(result, name)
                for name in dir(result)
                if name.startswith("st_") and name not in _TUPLE_FIELDS
            }
            return os.stat_result(fields, extra)

        return call

    monkeypatch.setattr(os, "stat", faked(os.stat))
    monkeypatch.setattr(os, "lstat", faked(os.lstat))
