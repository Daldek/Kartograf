"""A cache that cannot be opened or written is not an unreadable one, and
clearing a cache that does not exist says so (E2E 0.8.0 P3-13, C P3-18)."""

from kartograf.cache.metadata import MetadataCache
from kartograf.cli.commands import main


def _disabled_message(db_path) -> str:
    messages: list[str] = []
    cache = MetadataCache(db_path, on_disabled=messages.append)
    cache.set_record("nmt", "1m", "EVRF2007", "N-34-130-D-d-2-4", {"no_coverage": True})
    assert cache.error is not None
    return messages[0]


def test_cache_that_cannot_be_opened_is_not_called_unreadable(tmp_path):
    blocker = tmp_path / "plik"
    blocker.write_text("to nie katalog", encoding="utf-8")  # the directory is a file
    message = _disabled_message(blocker / ".kartograf_cache.db")
    assert "cannot be opened or written" in message
    assert "unreadable" not in message and "cache clear" not in message


def test_damaged_cache_is_still_called_unreadable(tmp_path):
    db = tmp_path / ".kartograf_cache.db"
    db.write_text("to nie baza", encoding="utf-8")
    message = _disabled_message(db)
    assert "unreadable" in message and "cache clear" in message


def test_clear_without_a_database_says_there_was_nothing_to_clear(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    assert main(["cache", "clear"]) == 0
    out = capsys.readouterr().out
    assert "wyczyszczony" not in out and "nie ma pliku cache" in out
    assert not (tmp_path / ".kartograf_cache.db").exists()
