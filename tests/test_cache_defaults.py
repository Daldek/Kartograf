"""Behavior of the default metadata cache shared by CLI and library."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from kartograf.cache import MetadataCache
from kartograf.cache.defaults import (
    DEFAULT_CACHE_FILENAME,
    default_cache_path,
    open_cache,
)
from kartograf.notices import CACHE_DISABLED, Notice

KEY = ("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4")
OLD = {"source": {"url": "old"}}
NEW = {"source": {"url": "new"}}


def test_true_opens_cwd_cache_and_closes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.db_path == default_cache_path()
        assert cache.db_path == tmp_path / DEFAULT_CACHE_FILENAME
        assert not cache.db_path.exists()
        cache.set_record(*KEY, OLD)
        connection = cache._conn
        assert connection is not None
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.get_record(*KEY) == OLD


@pytest.mark.parametrize("force", [False, True])
def test_false_is_none(tmp_path, monkeypatch, force):
    monkeypatch.chdir(tmp_path)
    with open_cache(False, force=force) as cache:
        assert cache is None
    assert not default_cache_path().exists()


def test_instance_passed_through_not_closed(tmp_path):
    instance = MetadataCache(tmp_path / "custom.db")
    try:
        instance.set_record(*KEY, OLD)
        connection = instance._conn
        assert connection is not None
        with open_cache(instance, force=False) as cache:
            assert cache is instance
            assert cache.get_record(*KEY) == OLD
        assert connection.execute("SELECT 1").fetchone() == (1,)
        assert instance.get_record(*KEY) == OLD
    finally:
        instance.close()


def test_force_true_reads_miss_writes_hit_on_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with open_cache(True, force=False) as cache:
        assert cache is not None
        cache.set_record(*KEY, OLD)
    with open_cache(True, force=True) as cache:
        assert cache is not None
        assert cache.get_record(*KEY) is None
        cache.set_record(*KEY, NEW)
        assert cache.get_record(*KEY) is None
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.get_record(*KEY) == NEW


def test_force_with_user_cache_does_not_flip_shared_instance(tmp_path):
    shared = MetadataCache(tmp_path / "custom.db", ttl_seconds=60, strict=True)
    try:
        shared.set_record(*KEY, OLD)
        with open_cache(shared, force=True) as refreshing:
            assert refreshing is not None
            assert refreshing is not shared
            assert refreshing.db_path == shared.db_path
            assert refreshing.get_record(*KEY) is None
            with ThreadPoolExecutor(max_workers=1) as workers:
                assert workers.submit(shared.get_record, *KEY).result(timeout=3) == OLD
                refreshing.set_record(*KEY, NEW)
                assert workers.submit(shared.get_record, *KEY).result(timeout=3) == NEW
        assert shared.get_record(*KEY) == NEW
    finally:
        shared.close()


@pytest.mark.parametrize("directory", ["readonly", "zażółć"])
def test_disabled_cache_emits_notice(tmp_path, monkeypatch, directory):
    readonly = tmp_path / directory
    readonly.mkdir(mode=0o555)
    readonly.chmod(0o555)
    monkeypatch.chdir(readonly)
    notices: list[Notice] = []
    # Permission checks are not reliable under root; emulate SQLite's error
    # when opening a database in a directory without write permissions.
    error = sqlite3.OperationalError("attempt to write a readonly database")
    with (
        patch("kartograf.cache.metadata.sqlite3.connect", side_effect=error),
        open_cache(True, force=False, on_notice=notices.append) as cache,
    ):
        assert cache is not None
        cache.set_record(*KEY, OLD)
        cache.set_record(*KEY, NEW)
        assert cache.get_record(*KEY) is None
    assert len(notices) == 1
    assert notices[0].level == "warning"
    assert notices[0].code == CACHE_DISABLED
    assert "readonly database" in notices[0].text
    assert notices[0].text.isascii()
