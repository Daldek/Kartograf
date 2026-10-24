"""``get_cache_info`` and ``clear_cache``: the metadata cache as the document
``kartograf-cache/1`` (spec 5.4.9). The cache is ``<cwd>/.kartograf_cache.db``:
every test works in its own ``tmp_path`` as the current directory.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from kartograf.cache.metadata import MetadataCache
from kartograf.cache_info import CacheInfo, clear_cache, get_cache_info, get_cache_path
from kartograf.core.bbox import BBox
from kartograf.error_report import error_report
from kartograf.exceptions import CacheError
from kartograf.serialization import SCHEMAS

DB_NAME = ".kartograf_cache.db"
ENTRY_KEYS = ["records", "campaigns", "teryt", "sheets", "index_areas", "atom_feeds"]


@pytest.fixture
def db(tmp_path, monkeypatch) -> Path:
    """The default cache file of a test run in ``tmp_path`` (not created)."""
    monkeypatch.chdir(tmp_path)
    return Path.cwd() / DB_NAME


def _populate(path: Path) -> None:
    """A database with a different number of entries in every table."""
    cache = MetadataCache(path)
    cache.set_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4", {"a": 1})
    for sheet in ("N-34-130-D-d-2-4", "N-34-130-D-d-2-3"):
        cache.set_campaigns("nmt", "1m", "EVRF2007", sheet, {"campaigns": []})
    cache.set_teryt(1.0, 2.0, "1465")
    cache.set_teryt(3.0, 4.0, "1465")
    cache.set_teryts_for_bbox(BBox(1.0, 2.0, 3.0, 4.0, "EPSG:2180"), ["1465"])
    for sheet in ("CTES96", "CTES97", "CTES98", "CTES99"):
        cache.set_sheet("cz_sm5", sheet, {"name": sheet})
    for key in ("a", "b", "c", "d", "e"):
        cache.set_index_area(key, {"payload": key})
    for feed in ("f1", "f2", "f3", "f4", "f5", "f6"):
        cache.set_atom_entries(feed, None, {"entries": 1})
    cache.close()


def _garbage(path: Path) -> None:
    path.write_bytes(b"to nie jest baza SQLite\n" * 200)


def _truncated(path: Path) -> None:
    """A valid database of several pages cut to half of its size."""
    cache = MetadataCache(path)
    for i in range(300):
        cache.set_record("nmt", "1m", "EVRF2007", f"G-{i}", {"pad": "x" * 200})
    cache.close()
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])


def _no_read_permission(path: Path) -> None:
    cache = MetadataCache(path)
    cache.set_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4", {"a": 1})
    cache.close()
    path.chmod(0)


_needs_non_root = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignoruje prawa dostepu do pliku",
)

UNREADABLE = [
    pytest.param(_garbage, id="garbage"),
    pytest.param(_truncated, id="truncated"),
    pytest.param(_no_read_permission, id="no-read-permission", marks=_needs_non_root),
]


def _hold_lock(path: Path, *, exclusive: bool = False) -> sqlite3.Connection:
    """Another connection to ``path`` in the middle of a transaction: a writer
    (the WAL database stays readable) or, with ``exclusive``, one that locks the
    file against every other connection."""
    holder = sqlite3.connect(path, isolation_level=None)
    if exclusive:
        holder.execute("PRAGMA locking_mode=EXCLUSIVE")
        holder.execute("BEGIN EXCLUSIVE")
    else:
        holder.execute("BEGIN IMMEDIATE")
    return holder


@pytest.fixture
def short_lock_timeout(monkeypatch):
    """A connection that meets a lock gives up after 50 ms, not after 5 s."""
    real_connect = sqlite3.connect

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        return real_connect(*args, **{**kwargs, "timeout": 0.05})

    monkeypatch.setattr(sqlite3, "connect", connect)


@pytest.mark.usefixtures("db")
def test_info_without_a_database_does_not_create_it(tmp_path):
    info = get_cache_info()

    assert info.action == "info"
    assert info.path == Path.cwd() / DB_NAME
    assert info.path.is_absolute()
    assert info.exists is False
    assert info.size_bytes is None
    assert info.entries is None
    assert info.cleared is None
    assert info.removed_unreadable is None
    assert list(tmp_path.iterdir()) == []


def test_info_counts_entries(db):
    _populate(db)

    info = get_cache_info()

    assert info.exists is True
    assert info.size_bytes == db.stat().st_size
    assert info.size_bytes > 0
    # every table has its own count: a swapped column would show here
    assert json.loads(info.to_json())["entries"] == {
        "records": 1,
        "campaigns": 2,
        "teryt": 3,
        "sheets": 4,
        "index_areas": 5,
        "atom_feeds": 6,
    }


def test_clear_empties_the_cache(db):
    _populate(db)

    cleared = clear_cache()
    after = get_cache_info()

    assert cleared.action == "clear"
    assert cleared.path == db
    assert cleared.cleared is True
    assert cleared.removed_unreadable is False
    assert cleared.entries is None
    assert cleared.exists is True
    assert cleared.size_bytes == db.stat().st_size
    assert after.action == "info"
    assert json.loads(after.to_json())["entries"] == dict.fromkeys(ENTRY_KEYS, 0)


def test_clear_reclaims_the_space_of_the_entries(db):
    cache = MetadataCache(db)
    for i in range(300):
        cache.set_record("nmt", "1m", "EVRF2007", f"G-{i}", {"pad": "x" * 200})
    cache.close()
    before = get_cache_info()

    cleared = clear_cache()

    assert before.size_bytes is not None and cleared.size_bytes is not None
    assert cleared.size_bytes < before.size_bytes


@pytest.mark.usefixtures("db")
def test_clear_without_a_database_does_not_create_it(tmp_path):
    cleared = clear_cache()

    assert cleared.action == "clear"
    assert cleared.cleared is True
    assert cleared.removed_unreadable is False
    assert cleared.exists is False
    assert cleared.size_bytes is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("make_broken", UNREADABLE)
def test_clear_removes_an_unreadable_file_with_wal_and_shm(db, tmp_path, make_broken):
    make_broken(db)
    Path(f"{db}-wal").write_bytes(b"x")
    Path(f"{db}-shm").write_bytes(b"x")

    cleared = clear_cache()

    assert cleared.removed_unreadable is True
    assert cleared.cleared is True
    assert cleared.exists is False
    assert cleared.size_bytes is None
    assert cleared.entries is None
    assert list(tmp_path.iterdir()) == []
    # the regular path works again: a fresh database is created
    cache = MetadataCache(db)
    cache.set_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4", {"a": 1})
    assert cache.get_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4") == {"a": 1}
    cache.close()


@_needs_non_root
def test_clear_without_the_right_to_delete_is_a_cache_error(tmp_path, monkeypatch):
    work = tmp_path / "ro"
    work.mkdir()
    monkeypatch.chdir(work)
    target = Path.cwd() / DB_NAME
    _garbage(target)
    work.chmod(0o500)
    try:
        with pytest.raises(CacheError) as error:
            clear_cache()
    finally:
        work.chmod(0o700)

    assert str(error.value).startswith(
        f"nie mozna usunac nieczytelnego pliku cache {target}: "
    )
    assert target.exists()
    # the advice is not the command that just failed
    assert error.value.hint is not None
    assert "kartograf cache clear" not in error.value.hint


@pytest.mark.usefixtures("short_lock_timeout")
def test_clear_never_removes_a_locked_database(db):
    _populate(db)
    holder = _hold_lock(db)
    try:
        with pytest.raises(CacheError) as error:
            clear_cache()
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert str(error.value).startswith(f"cache zablokowany przez inny proces: {db} (")
    assert str(error.value).endswith("- sprobuj ponownie po jego zakonczeniu")
    # a locked cache is not repaired by clearing it: the advice is to wait
    assert error.value.hint is not None
    assert "kartograf cache clear" not in error.value.hint
    assert db.exists()
    # nothing was deleted: the entries are still there once the lock is gone
    after = get_cache_info()
    assert after.entries is not None
    assert after.entries.records == 1


@pytest.mark.usefixtures("short_lock_timeout")
def test_info_reads_a_database_that_another_connection_is_writing(db):
    # the WAL database lets readers through while a writer holds its lock
    _populate(db)
    holder = _hold_lock(db)
    try:
        info = get_cache_info()
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert info.entries is not None
    assert info.entries.records == 1


@pytest.mark.usefixtures("short_lock_timeout")
def test_info_of_a_database_locked_exclusively_is_a_cache_error(db):
    _populate(db)
    holder = _hold_lock(db, exclusive=True)
    try:
        with pytest.raises(CacheError) as error:
            get_cache_info()
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert str(error.value).startswith(f"cache zablokowany przez inny proces: {db} (")
    assert db.exists()


@pytest.mark.parametrize("make_broken", UNREADABLE)
def test_info_of_an_unreadable_database_is_cache_error(db, make_broken):
    make_broken(db)
    content = db.read_bytes() if os.access(db, os.R_OK) else None

    with pytest.raises(CacheError) as error:
        get_cache_info()

    message = str(error.value)
    assert message.startswith(f"cache nieczytelny: {db} (")
    assert message.endswith("- uzyj `kartograf cache clear`")
    assert "DatabaseError" not in message
    assert error_report(error.value).hint == CacheError.DEFAULT_HINT
    # reading never repairs and never deletes
    assert db.exists()
    if content is not None:
        assert db.read_bytes() == content


@pytest.mark.usefixtures("db")
def test_path_of_a_missing_database_is_reported_and_not_created(tmp_path):
    info = get_cache_path()

    assert info.action == "path"
    assert info.path == Path.cwd() / DB_NAME
    assert info.path.is_absolute()
    assert (info.exists, info.size_bytes, info.entries) == (False, None, None)
    assert (info.cleared, info.removed_unreadable) == (None, None)
    assert list(tmp_path.iterdir()) == []


def test_path_of_a_database_says_where_it_is_and_does_not_count_it(db):
    _populate(db)

    info = get_cache_path()

    assert info.path == db
    assert info.exists is True
    assert info.size_bytes == db.stat().st_size
    assert info.entries is None


@pytest.mark.parametrize("make_broken", UNREADABLE)
def test_path_of_an_unreadable_database_is_still_the_path(db, make_broken):
    """The path is what one needs to repair a cache that cannot be read: it is
    given without opening the database (``get_cache_info`` is a ``CacheError``)."""
    make_broken(db)
    content = db.read_bytes() if os.access(db, os.R_OK) else None
    with pytest.raises(CacheError):
        get_cache_info()

    info = get_cache_path()

    assert (info.path, info.exists) == (db, True)
    assert info.size_bytes == db.stat().st_size
    if content is not None:
        assert db.read_bytes() == content


@pytest.mark.usefixtures("short_lock_timeout")
def test_path_of_a_database_locked_exclusively_is_still_the_path(db):
    _populate(db)
    holder = _hold_lock(db, exclusive=True)
    try:
        info = get_cache_path()
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert (info.path, info.exists, info.entries) == (db, True, None)


def test_document_has_the_keys_of_the_spec(db):
    _populate(db)
    info: Any = get_cache_info()
    document: Any = info.to_dict()
    cleared: Any = clear_cache().to_dict()

    assert SCHEMAS["kartograf-cache/1"] == (CacheInfo,)
    keys = [
        "schema",
        "action",
        "path",
        "exists",
        "size_bytes",
        "entries",
        "cleared",
        "removed_unreadable",
    ]
    assert list(document) == keys
    assert list(cleared) == keys
    assert document["schema"] == "kartograf-cache/1"
    assert list(document["entries"]) == ENTRY_KEYS
    assert document["path"] == db.as_posix()
    assert (document["cleared"], document["removed_unreadable"]) == (None, None)
    assert (cleared["action"], cleared["entries"]) == ("clear", None)
    assert json.loads(info.to_json()) == document
