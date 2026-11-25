"""The client of a request and its window of the limits of ``kartograf server``.

A client is the address of the connection, or the right-most hop of
``X-Forwarded-For`` that is no trusted proxy when the connection is from one (AGI-6.9);
a limit counts ``limit`` requests per window from the first, then answers the whole
seconds to the window's end (DEV-15.9, ADR-063 decision 8).
"""

import pytest

from kartograf.server.limits import RateLimiter, client_address, networks

PROXY = networks(["127.0.0.1"])


class Clock:
    """A monotonic clock the test moves."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    ("peer", "forwarded", "expected"),
    [
        pytest.param("203.0.113.9", "198.51.100.1", "203.0.113.9", id="untrusted"),
        pytest.param("127.0.0.1", None, "127.0.0.1", id="no_header"),
        pytest.param("127.0.0.1", "198.51.100.1", "198.51.100.1", id="one_hop"),
        pytest.param(
            "127.0.0.1", "198.51.100.1, 198.51.100.2", "198.51.100.2", id="right_most"
        ),
        pytest.param(
            "127.0.0.1",
            "198.51.100.1, 198.51.100.2, 127.0.0.1",
            "198.51.100.2",
            id="trusted_hop_skipped",
        ),
        pytest.param("127.0.0.1", " , ", "127.0.0.1", id="empty_hops"),
        pytest.param(None, "198.51.100.1", "unknown", id="no_peer"),
    ],
)
def test_client_address_of_a_peer_and_its_forwarded_for(peer, forwarded, expected):
    assert client_address(peer, forwarded, PROXY) == expected


def test_client_address_every_hop_trusted_takes_the_left_most():
    trusted = networks(["10.0.0.0/8"])

    address = client_address("10.0.0.1", "10.1.1.1, 10.2.2.2, 10.3.3.3", trusted)

    assert address == "10.1.1.1"


def test_client_address_trusts_a_cidr_network_and_ipv6():
    trusted = networks(["10.0.0.0/8", "::1", "fd00::/8"])

    from_network = client_address("10.20.30.40", "198.51.100.7, 10.9.9.9", trusted)
    from_ipv6 = client_address("::1", "2001:db8::5, fd00::2", trusted)
    outside = client_address("2001:db8::9", "198.51.100.7", trusted)

    assert (from_network, from_ipv6, outside) == (
        "198.51.100.7",
        "2001:db8::5",
        "2001:db8::9",
    )


def test_rate_limiter_over_the_limit_answers_seconds_to_the_window_end():
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)
    first = limiter.hit("a")
    clock.now += 10.2
    second = limiter.hit("a")

    refused = limiter.hit("a")

    assert (first, second, refused) == (None, None, 50)


def test_rate_limiter_retry_after_is_at_least_one_second():
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.hit("a")
    clock.now += 59.99

    assert limiter.hit("a") == 1


def test_rate_limiter_counts_each_address_on_its_own():
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.hit("a")

    assert (limiter.hit("b"), limiter.hit("a")) == (None, 60)


def test_rate_limiter_new_window_after_the_end_of_the_old():
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.hit("a")
    clock.now += 60

    assert (limiter.hit("a"), limiter.hit("a")) == (None, 60)


def test_rate_limiter_forgets_an_address_when_its_window_ends():
    clock = Clock()
    limiter = RateLimiter(5, 60, clock)
    limiter.hit("a")
    clock.now += 30
    limiter.hit("b")
    sizes = []

    for _ in range(2):
        clock.now += 30
        limiter.hit("c")
        sizes.append(len(limiter))

    # 60 s: a's window ends (b, c left); 90 s: b's ends (c left)
    assert sizes == [2, 1]
