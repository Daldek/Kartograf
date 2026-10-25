"""Behavior of the default metadata cache shared by CLI and library."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from kartograf.cache import MetadataCache
from kartograf.cache.defaults import CACHE_FILENAME, default_cache_path, open_cache
from kartograf.notices import CACHE_DISABLED, Notice

KEY = ("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4")
OLD = {"source": {"url": "old"}}
NEW = {"source": {"url": "new"}}


def test_true_opens_the_default_cache_and_closes(
    tmp_path, monkeypatch, user_environment
):
    monkeypatch.chdir(tmp_path)
    expected = user_environment / "cache" / "kartograf" / CACHE_FILENAME
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.db_path == default_cache_path() == expected
        assert not cache.db_path.exists()
        cache.set_record(*KEY, OLD)
        connection = cache._conn
        assert connection is not None
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.get_record(*KEY) == OLD
    assert expected.is_file()
    assert list(tmp_path.iterdir()) == []  # nothing is written to the cwd (DEV-18.2)


def test_the_default_cache_follows_cache_dir_of_the_settings(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("NOGAT_CACHE_DIR", str(elsewhere))
    assert default_cache_path() == elsewhere / "kartograf" / CACHE_FILENAME
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "own"))
    assert default_cache_path() == tmp_path / "own" / "kartograf" / CACHE_FILENAME


@pytest.mark.parametrize("force", [False, True])
def test_false_is_none(tmp_path, monkeypatch, force):
    monkeypatch.chdir(tmp_path)
    with open_cache(False, force=force) as cache:
        assert cache is None
    assert not default_cache_path().exists()
    assert not default_cache_path().parent.exists()  # nothing is made for no cache


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
    cache_dir = tmp_path / directory
    (cache_dir / "kartograf").mkdir(parents=True)
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(cache_dir))
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
    assert "readonly database" in notices[0].message
    assert notices[0].message.isascii()


def test_the_first_write_makes_the_cache_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "not" / "there"))
    assert not (tmp_path / "not").exists()
    with open_cache(True, force=False) as cache:
        assert cache is not None
        assert cache.get_record(*KEY) is None  # a read makes nothing
        assert not (tmp_path / "not").exists()
        cache.set_record(*KEY, OLD)
    assert (tmp_path / "not" / "there" / "kartograf" / CACHE_FILENAME).is_file()


def test_a_cache_directory_that_cannot_be_made_disables_the_cache(
    tmp_path, monkeypatch
):
    """A file in the way of the directory is the state of an unwritable cache."""
    (tmp_path / "file").write_text("x", encoding="utf-8")
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "file" / "cache"))
    notices: list[Notice] = []

    with open_cache(True, force=False, on_notice=notices.append) as cache:
        assert cache is not None
        cache.set_record(*KEY, OLD)
        assert cache.get_record(*KEY) is None
        assert isinstance(cache.error, sqlite3.OperationalError)
        assert isinstance(cache.error.__cause__, OSError)

    assert [notice.code for notice in notices] == [CACHE_DISABLED]
    assert "cannot be opened or written" in notices[0].message
    assert notices[0].message.isascii()
