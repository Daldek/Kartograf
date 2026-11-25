"""
The limits of ``kartograf server`` per client (DEV-15.9, AGI-6.9, ADR-063 decision 8).

A client is its IP address: the address of the connection, or, when that address is
a trusted proxy (the setting ``trusted_proxies``, ``127.0.0.1`` by default), the
right-most address of ``X-Forwarded-For`` that is no trusted proxy (AGI-6.9). An
address stays in memory for its window only and is never written anywhere.

``RateLimiter`` is the window of Hydrolog's public GUI (``hydrolog.gui._public``): a
window of ``window_s`` seconds from a client's first counted request, ``limit``
requests in it, then ``Retry-After`` until the window ends. The server keeps one for
the requests of its API (``request_limit`` per ``request_window``) and one for the
plans and the scripts that plan (``plan_limit`` per ``plan_window``).
"""

import collections
import ipaddress
import math
import threading
import time
from collections.abc import Callable, Iterable

Network = ipaddress.IPv4Network | ipaddress.IPv6Network

__all__ = ["RateLimiter", "client_address", "networks"]


def networks(addresses: Iterable[str]) -> tuple[Network, ...]:
    """Return the networks of the setting ``trusted_proxies`` (an address is a /32)."""
    return tuple(ipaddress.ip_network(address, strict=False) for address in addresses)


def _trusted(address: str, trusted: tuple[Network, ...]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in trusted)


def client_address(
    peer: str | None, forwarded_for: str | None, trusted: tuple[Network, ...]
) -> str:
    """Return the address a limit counts (AGI-6.9).

    Parameters
    ----------
    peer : str, optional
        The address of the connection (``None`` when the server does not know it).
    forwarded_for : str, optional
        The ``X-Forwarded-For`` header: believed only from a trusted ``peer``.
    trusted : tuple of networks
        The trusted proxies.

    Returns
    -------
    str
        The right-most address of ``X-Forwarded-For`` that is no trusted proxy when
        the peer is one, else the peer (``unknown`` without one).
    """
    address = peer or "unknown"
    if forwarded_for is None or not _trusted(address, trusted):
        return address
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _trusted(hop, trusted):
            return hop
    return hops[0] if hops else address


class RateLimiter:
    """A window of ``window_s`` per client address, from its first counted request.

    An address that has made ``limit`` requests in its window waits for the window's
    end. Addresses are forgotten as soon as their window ends (the oldest first), so
    one stays in memory for its window only.

    Parameters
    ----------
    limit : int
        Requests of one address in a window.
    window_s : float
        The window [s].
    clock : callable, optional
        Monotonic clock [s]; tests pass their own.
    """

    def __init__(
        self,
        limit: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._lock = threading.Lock()
        # address -> [start, count], in the order of the starts
        self._windows: collections.OrderedDict[str, list[float]] = (
            collections.OrderedDict()
        )

    def _purge(self, now: float) -> None:
        while self._windows:
            start = next(iter(self._windows.values()))[0]
            if now - start < self.window_s:
                break
            self._windows.popitem(last=False)

    def hit(self, address: str) -> int | None:
        """Count a request of ``address``.

        Returns
        -------
        int or None
            ``None`` when the request is within the limit; else the whole seconds
            until the address's window ends (at least 1), the ``Retry-After``.
        """
        with self._lock:
            now = self._clock()
            self._purge(now)
            window = self._windows.get(address)
            if window is None:
                self._windows[address] = [now, 1]
                return None
            if window[1] >= self.limit:
                return max(1, math.ceil(window[0] + self.window_s - now))
            window[1] += 1
            return None

    def __len__(self) -> int:
        """Return the number of addresses in memory."""
        with self._lock:
            return len(self._windows)
