"""Notices represent data messages without duplicating CLI output."""

import pytest

from kartograf import Notice
from kartograf.exceptions import ValidationError
from kartograf.notices import CACHE_DISABLED, CUTOUT_SIZE, NoticeSink


def test_sink_forwards_in_order_and_collects() -> None:
    delivered: list[Notice] = []
    sink = NoticeSink(delivered.append)
    sink.emit("info", CUTOUT_SIZE, "Wycinek ma duzy rozmiar")
    first_snapshot = sink.notices
    sink.emit("warning", CACHE_DISABLED, "Cache nie jest dostepny")

    assert delivered == [
        Notice("info", CUTOUT_SIZE, "Wycinek ma duzy rozmiar"),
        Notice("warning", CACHE_DISABLED, "Cache nie jest dostepny"),
    ]
    assert sink.notices == tuple(delivered)
    assert first_snapshot == (delivered[0],)


def test_sink_without_callback_collects() -> None:
    sink = NoticeSink(None)
    sink.emit("info", CUTOUT_SIZE, "Przed pierwszym pobraniem")
    assert sink.notices == (Notice("info", CUTOUT_SIZE, "Przed pierwszym pobraniem"),)


@pytest.mark.parametrize("text", ["Zawartość", "Większy", "\u2014"])
def test_notice_text_ascii(text: str) -> None:
    with pytest.raises(ValueError, match="ASCII") as exc:
        Notice("warning", CACHE_DISABLED, text)
    assert not isinstance(exc.value, ValidationError)
