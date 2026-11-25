"""Notices represent data messages without duplicating CLI output."""

import pytest

from kartograf import Notice, messages
from kartograf.exceptions import ValidationError
from kartograf.messages import Text, localize, message
from kartograf.notices import (
    CACHE_DISABLED,
    CUTOUT_SIZE,
    LAZ_SUPERSEDED,
    LISTED_UNITS,
    NoticeSink,
    names_text,
)
from kartograf.serialization import encode


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


def test_a_catalog_notice_carries_its_polish_text_beside_the_english_one(monkeypatch):
    """ADR-063 amendment 1: a page shows a notice in its reader's language."""
    monkeypatch.setattr(
        messages,
        "_catalog",
        lambda area: {"skip": Text("skipped {n} LAZ tiles", "pominięto {n} kafli LAZ")},
    )
    notice = Notice("info", LAZ_SUPERSEDED, message("x.skip", n=21))
    english = {
        "level": "info",
        "code": LAZ_SUPERSEDED,
        "message": "skipped 21 LAZ tiles",
    }
    polish = {"i18n": {"pl": "pominięto 21 kafli LAZ"}}

    assert encode(notice) == {**english, **polish}
    assert encode(notice.localized("pl")) == {**english, **polish}
    assert encode(Notice("warning", CACHE_DISABLED, "HTTP 500")) == {
        "level": "warning",
        "code": CACHE_DISABLED,
        "message": "HTTP 500",
    }


def test_names_text_lists_all_names_up_to_the_limit_then_counts_the_rest() -> None:
    names = [f"u{i}" for i in range(LISTED_UNITS + 5)]

    assert names_text([]) == ""
    assert names_text(names[:LISTED_UNITS]) == ", ".join(names[:LISTED_UNITS])
    # the first names, then the number of the rest in the noun form of the language
    first = ", ".join(names[:LISTED_UNITS])
    for rest, english, polish in (
        (1, "other", "inny"),
        (2, "others", "inne"),
        (5, "others", "innych"),
    ):
        text = names_text(names[: LISTED_UNITS + rest])
        assert text == f"{first} and {rest} {english}"
        assert localize(text, "pl") == f"{first} i {rest} {polish}"
    # a very long list stays one short line
    assert len(names_text([f"2000/7/78944_{i}" for i in range(3884)])) < 300
