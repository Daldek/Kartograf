"""
Interrupting a run: SIGTERM like Ctrl-C, and the stop of the threads of a pool.

Ctrl-C raises ``KeyboardInterrupt`` in the main thread only, and a download with
``--workers >= 2`` keeps its units in the threads of a pool: leaving a
``with ThreadPoolExecutor`` block waits for every queued unit, so an interrupt
used to wait for (and commit) the whole queue. ``run_parallel`` is the one place
where the units of a request run in a pool. When the thread that waits for the
results is interrupted or fails, the units that have not started are cancelled
and the running ones are told to stop; the call returns only after they ended,
so nothing of the pool is left running and no unit is committed afterwards.

A running unit stops at the points where the transport layer asks
``check_stop`` (before a request, between the chunks of a body, before a
version is committed) and in ``current_stop().wait`` instead of a retry pause. It
stops with ``Stopped``, a ``KeyboardInterrupt``: every cleanup that Ctrl-C
triggers in the sequential mode (``except BaseException``, ``finally``) runs the
same way, and no ``except Exception`` of the package swallows it. A request
blocked on the network ends at the latest with its timeout.

``sigterm_interrupts`` makes SIGTERM (``timeout``, ``docker stop``, a
supervisor) behave like Ctrl-C: ``Terminated`` is raised in the main thread, so
the staging directories are cleaned and the entry point reports the interruption
and exits with 143 (``128 + SIGTERM``; Ctrl-C: 130).
"""

import signal
import threading
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager


class Terminated(KeyboardInterrupt):
    """The process got SIGTERM while ``sigterm_interrupts`` was active.

    A ``KeyboardInterrupt``: everything that handles Ctrl-C (cleanup, the
    pool stop) handles it too. The entry points tell the two apart by the
    exit code (143 and 130) and the code of the error document (``terminated``
    and ``interrupted``).
    """


class Stopped(KeyboardInterrupt):
    """Raised in a thread of a pool that is stopping (see ``check_stop``).

    Never reaches the caller of ``run_parallel``: it re-raises the exception
    that stopped the pool, not the ones the stopped units end with.
    """


_running = threading.local()


def current_stop() -> threading.Event | None:
    """Return the stop flag of the pool the current thread works for.

    ``None`` outside a pool: the main thread, which gets its interrupt as
    ``KeyboardInterrupt``.
    """
    return getattr(_running, "stop", None)


def check_stop() -> None:
    """Raise ``Stopped`` in a pool thread whose pool is stopping.

    Do nothing elsewhere.
    """
    stop = current_stop()
    if stop is not None and stop.is_set():
        raise Stopped


def _run_unit[T, R](stop: threading.Event, work: Callable[[T], R], item: T) -> R:
    """One unit in a pool thread.

    It does not start once the pool is stopping and sees the stop flag while it runs.
    """
    if stop.is_set():
        raise Stopped
    _running.stop = stop
    try:
        return work(item)
    finally:
        _running.stop = None  # the thread is reused for the next unit


def run_parallel[T, R](
    work: Callable[[T], R],
    items: Sequence[T],
    *,
    workers: int,
    on_done: Callable[[int, T, R], None] | None = None,
) -> list[R]:
    """Run ``work(item)`` for every item in ``workers`` threads.

    The results in the order of ``items``.

    ``on_done(ended, item, result)`` is called in the calling thread for every
    unit that ended normally, in completion order; ``ended`` counts the units
    that ended so far, this one included (progress reporting).

    The first exception that leaves the loop - ``KeyboardInterrupt`` of the
    calling thread, an exception of a unit, an exception of ``on_done`` - stops
    the pool: the units that have not started never do, the running ones stop at
    their next ``check_stop`` (``Stopped``), and the call waits for them before
    the exception is raised again. Units that ended before it stay done
    (their versions are committed); none is committed after it.

    Raises
    ------
    BaseException
        The first one raised by ``work`` or ``on_done``, or the interrupt.
    """
    stop = threading.Event()
    pool = ThreadPoolExecutor(max_workers=workers)
    done: dict[int, R] = {}
    try:
        futures = {
            pool.submit(_run_unit, stop, work, item): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            done[index] = future.result()
            if on_done is not None:
                on_done(len(done), items[index], done[index])
    except BaseException:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown()
    return [done[index] for index in range(len(items))]


@contextmanager
def sigterm_interrupts() -> Iterator[None]:
    """Make SIGTERM raise ``Terminated`` in the main thread within the block.

    It works as Ctrl-C raises ``KeyboardInterrupt``.

    The first SIGTERM restores the default action: a second one kills the
    process at once (a stuck cleanup can always be forced). Nothing changes
    outside the main thread (Python allows handlers there only) or when
    SIGTERM is not at its default action (ignored, or handled by the program
    that embeds the library).
    """
    if (
        threading.current_thread() is not threading.main_thread()
        or signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
    ):
        yield
        return

    def terminate(signum: int, frame: object) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        raise Terminated

    signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
