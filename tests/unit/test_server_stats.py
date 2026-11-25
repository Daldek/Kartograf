"""The daily totals of ``kartograf server`` (DEV-15.11, ADR-063 decision 8).

One line per UTC day in ``stats.jsonl``, in date order; a visitor is an address with
a ``User-Agent``, counted once a day; a restart adds to the day's line; the day rolls
at 00:00 UTC.
"""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from kartograf.server.stats import STATS_KEYS, DailyStats, read_days

UA = "Mozilla/5.0 (X11; Linux x86_64) Firefox/130.0"
WARSAW = timezone(timedelta(hours=1))


class Clock:
    """The current time, which the test moves."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _line(date: str, **counts: int) -> dict[str, object]:
    return {"date": date, **dict.fromkeys(STATS_KEYS, 0), **counts}


def _days(path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2026, 11, 25, 12, 0, tzinfo=UTC))


def test_daily_stats_visitor_is_an_address_with_its_user_agent(tmp_path, clock):
    stats = DailyStats(tmp_path / "stats.jsonl", clock)

    stats.visit("198.51.100.1", UA)
    stats.visit("198.51.100.1", UA)
    stats.visit("198.51.100.1", "curl/8.5.0")
    stats.visit("198.51.100.2", UA)

    assert stats.snapshot()["visitors"] == 3


def test_daily_stats_counts_its_totals(tmp_path, clock):
    stats = DailyStats(tmp_path / "stats.jsonl", clock)

    stats.count("analyses_run")
    stats.count("analyses_run")
    stats.count("page_views")

    assert stats.snapshot() == _line("2026-11-25", analyses_run=2, page_views=1)


@pytest.mark.parametrize("key", ["visitors", "plans"])
def test_daily_stats_count_of_another_key_raises_key_error(tmp_path, clock, key):
    stats = DailyStats(tmp_path / "stats.jsonl", clock)

    with pytest.raises(KeyError):
        stats.count(key)


def test_daily_stats_flush_writes_one_line_per_day_in_date_order(tmp_path, clock):
    path = tmp_path / "stats.jsonl"
    later, earlier = _line("2026-11-27", visitors=4), _line("2026-11-20", visitors=7)
    path.write_text(f"{json.dumps(later)}\n{json.dumps(earlier)}\n", encoding="utf-8")
    stats = DailyStats(path, clock)
    stats.visit("198.51.100.1", UA)

    stats.flush()

    assert _days(path) == [earlier, _line("2026-11-25", visitors=1), later]


def test_daily_stats_flush_without_a_change_writes_nothing(tmp_path, clock):
    path = tmp_path / "data" / "stats.jsonl"
    stats = DailyStats(path, clock)

    stats.flush()

    assert not path.parent.exists()


def test_daily_stats_flush_after_a_flush_without_a_change_keeps_the_file(
    tmp_path, clock
):
    path = tmp_path / "stats.jsonl"
    stats = DailyStats(path, clock)
    stats.count("analyses_run")
    stats.flush()
    path.write_text("edited\n", encoding="utf-8")

    stats.flush()

    assert path.read_text(encoding="utf-8") == "edited\n"


def test_daily_stats_restart_adds_to_the_stored_day(tmp_path, clock):
    path = tmp_path / "stats.jsonl"
    first = DailyStats(path, clock)
    first.visit("198.51.100.1", UA)
    first.count("analyses_run")
    first.flush()
    second = DailyStats(path, clock)
    second.visit("198.51.100.2", UA)
    second.count("analyses_run")

    second.flush()

    assert _days(path) == [_line("2026-11-25", visitors=2, analyses_run=2)]


def test_daily_stats_day_rolls_at_midnight_utc(tmp_path):
    path = tmp_path / "stats.jsonl"
    # 00:30 in Warsaw is still 23:30 UTC of the day before
    clock = Clock(datetime(2026, 11, 26, 0, 30, tzinfo=WARSAW))
    stats = DailyStats(path, clock)
    stats.visit("198.51.100.1", UA)
    stats.count("analyses_run")
    clock.now = datetime(2026, 11, 26, 1, 0, 1, tzinfo=WARSAW)

    stats.visit("198.51.100.1", UA)
    stats.flush()

    assert _days(path) == [
        _line("2026-11-25", visitors=1, analyses_run=1),
        _line("2026-11-26", visitors=1),
    ]


def test_daily_stats_old_day_stays_final_after_the_roll(tmp_path, clock):
    path = tmp_path / "stats.jsonl"
    stats = DailyStats(path, clock)
    stats.count("analyses_run")
    stats.flush()
    clock.now += timedelta(days=1)
    stats.count("analyses_run")
    stats.count("analyses_run")

    stats.flush()

    assert _days(path) == [
        _line("2026-11-25", analyses_run=1),
        _line("2026-11-26", analyses_run=2),
    ]


def test_read_days_skips_unusable_lines(tmp_path):
    path = tmp_path / "stats.jsonl"
    good = _line("2026-11-25", visitors=2)
    path.write_text(
        "\n".join(
            [
                "not json",
                "[1, 2]",
                json.dumps({"visitors": 3}),
                json.dumps({"date": 20261125}),
                json.dumps(good),
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert read_days(path) == [good]


def test_read_days_of_a_missing_file_is_empty(tmp_path):
    assert read_days(tmp_path / "stats.jsonl") == []
