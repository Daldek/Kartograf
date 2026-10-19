"""``kartograf.interrupt``: the stop of the units of a pool (Ctrl-C with
``--workers >= 2``) and SIGTERM as Ctrl-C (e2e 0.8.0: B P2-1/P3-6, C P2-5,
D P2-2)."""

import os
import signal
import threading
import time

import pytest

from kartograf.interrupt import (
    Stopped,
    Terminated,
    current_stop,
    run_parallel,
    sigterm_interrupts,
)
from tests.interrupt_fakes import PATIENCE_S, interrupted_after_first, transfer


def test_results_follow_the_items_and_progress_the_completion_order():
    order = [2, 0, 1]
    gates = {item: threading.Event() for item in order}
    gates[order[0]].set()
    ended = []

    def work(item):
        assert gates[item].wait(PATIENCE_S)
        return f"r{item}"

    def on_done(count, item, result):
        ended.append((count, item, result))
        if count < len(order):
            gates[order[count]].set()  # the next unit may end

    results = run_parallel(work, [0, 1, 2], workers=3, on_done=on_done)

    assert results == ["r0", "r1", "r2"]
    assert ended == [(1, 2, "r2"), (2, 0, "r0"), (3, 1, "r1")]


def test_ctrl_c_stops_the_running_units_and_never_starts_the_queued_ones():
    started, committed = [], []

    def work(item):
        started.append(item)
        if item == 0:
            return "ended before the interrupt"
        transfer()
        committed.append(item)  # what a unit that went on would publish

    threads_before = threading.active_count()

    error, seconds = interrupted_after_first(work, list(range(8)))

    assert type(error) is KeyboardInterrupt  # the interrupt itself, not Stopped
    assert committed == []
    # two workers: the unit after 0 may have been picked before the stop, never
    # a unit behind it
    assert set(started) <= {0, 1, 2}
    assert seconds < PATIENCE_S / 2
    # the call returns after the units ended: no thread of the pool is left
    assert threading.active_count() <= threads_before


def test_a_stopped_pool_commits_nothing(tmp_path):
    """The commit of a version is a point where a stopping unit stops: the
    staged file of a transfer that ended right at the interrupt is not
    published."""
    from kartograf.download.versions import (
        INCOMING_DIR,
        VersionRef,
        commit_version,
        read_content,
    )

    versions = tmp_path / "versions"
    incoming = versions / INCOMING_DIR / "host_1_abc"
    incoming.mkdir(parents=True)
    staged = incoming / "plik.tif"
    staged.write_bytes(b"data")

    def work(item):
        if item == 0:
            return None
        stop = current_stop()
        assert stop is not None and stop.wait(PATIENCE_S)  # until the interrupt
        digest = read_content(staged, ext=".tif", coverage=False)
        commit_version(
            staged,
            versions / "bbox",
            "plik.tif",
            VersionRef("2026-10-19", "downloaded"),
            digest,
            lambda data, ref, dg: pytest.fail("the sidecar of a version was written"),
        )

    error, seconds = interrupted_after_first(work, [0, 1])

    assert type(error) is KeyboardInterrupt
    assert seconds < PATIENCE_S / 2
    assert not (versions / "bbox").exists()  # no version directory
    assert staged.exists()  # the caller's cleanup removes it, the commit did not


def test_a_failing_unit_stops_the_pool_and_its_error_is_raised():
    started = []

    def work(item):
        started.append(item)
        if item == 0:
            raise OSError("brak miejsca")
        transfer()

    with pytest.raises(OSError, match="brak miejsca"):
        run_parallel(work, list(range(8)), workers=2)

    assert set(started) <= {0, 1, 2}


def test_stopped_and_terminated_are_interrupts_not_exceptions():
    """No ``except Exception`` of the package may turn a stopped unit into a
    failed one (a ``UnitFailure``, a ``failed`` status)."""
    for cls in (Stopped, Terminated):
        assert issubclass(cls, KeyboardInterrupt)
        assert not issubclass(cls, Exception)


@pytest.fixture
def sigterm_at_default():
    """A process that can take SIGTERM in the main thread with its default
    action; the tests of the handler send a real signal."""
    if (
        os.name == "nt"
        or threading.current_thread() is not threading.main_thread()
        or signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
    ):
        pytest.skip("SIGTERM is handled by the test runner")


def test_sigterm_raises_terminated_in_the_main_thread_within_the_block(
    sigterm_at_default,
):
    with sigterm_interrupts():
        assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
        with pytest.raises(Terminated):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(PATIENCE_S)  # the handler raises here, in the main thread
        # the first signal restores the default: a second one kills the process
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL

    assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL


def test_sigterm_handler_of_the_program_is_left_alone(sigterm_at_default):
    program = signal.signal(signal.SIGTERM, lambda signum, frame: None)
    try:
        handler = signal.getsignal(signal.SIGTERM)
        with sigterm_interrupts():
            assert signal.getsignal(signal.SIGTERM) is handler
        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGTERM, program)


def test_sigterm_is_not_touched_outside_the_main_thread(sigterm_at_default):
    inside = []

    def block():
        with sigterm_interrupts():
            inside.append(signal.getsignal(signal.SIGTERM))

    thread = threading.Thread(target=block)
    thread.start()
    thread.join(PATIENCE_S)

    assert inside == [signal.SIG_DFL]
