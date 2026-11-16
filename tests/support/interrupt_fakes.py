"""Stand-ins of a download that Ctrl-C interrupts (tests of ``kartograf.interrupt``
and of the pool of every download track).

A pool keeps a unit running until its transfer ends, so a test needs transfers that
do not end: ``transfer`` is one for a fake above the transport (a provider method),
``EndlessResponse`` for a fake session below it (only the chunk loop of
``download_to`` can stop that one).
"""

import threading
import time

import pytest

from kartograf.interrupt import check_stop, run_parallel

# A real run is over in milliseconds; this only turns a regression (a pool that
# does not stop) into a failed assertion instead of a hung test run.
PATIENCE_S = 20


def transfer() -> None:
    """A transfer of 30 s: the chunk loop of the transport asks ``check_stop``."""
    for _ in range(3000):
        check_stop()
        time.sleep(0.01)
    raise AssertionError("the unit was not stopped")


def ctrl_c(*_args) -> None:
    """A callback that the caller of the pool gets Ctrl-C in."""
    raise KeyboardInterrupt


def interrupted_after_first(work, items, *, workers=2):
    """``run_parallel`` whose calling thread gets Ctrl-C when the first unit
    ends: the first item must return at once, the others run on until stopped.

    Returns the exception the call ended with and the seconds it took.
    """
    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt) as raised:
        run_parallel(work, items, workers=workers, on_done=ctrl_c)
    return raised.value, time.monotonic() - started


class FirstThenTransfer:
    """The first call ends at once, every other one is a transfer that goes on
    until it is stopped: the first unit of a pool ends (and is committed), the
    others are running or queued when the interrupt comes."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def begin(self, key: str) -> None:
        with self._lock:
            self.calls.append(key)
            first = len(self.calls) == 1
        if not first:
            transfer()


class EndlessResponse:
    """A streamed ``requests.Response`` whose body never ends."""

    status_code = 200

    def __init__(self, headers: dict | None = None) -> None:
        self.headers = {"Content-Type": "application/zip", **(headers or {})}
        self.chunks = 0

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int = 1):
        while True:
            self.chunks += 1
            yield b"x" * 16
            time.sleep(0.01)
