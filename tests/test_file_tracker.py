"""FileTracker wait semantics: completion, failure, timeout, and cycle breaking.

wait_for_file used to block forever, which could starve the bounded worker
pool (real deadlock) when every running worker waited on a file whose worker
was still queued. These tests pin the guarded behavior.
"""

import threading
import time

from src.orchestrator import FileTracker


def test_wait_returns_done_when_marked():
    tracker = FileTracker()
    tracker.mark_done("a.py")
    assert tracker.wait_for_file("a.py") == "done"


def test_wait_returns_failed_when_marked():
    tracker = FileTracker()
    tracker.mark_failed("a.py")
    assert tracker.wait_for_file("a.py") == "failed"


def test_wait_wakes_on_mark_done_from_other_thread():
    tracker = FileTracker()
    result = {}

    def waiter():
        result["status"] = tracker.wait_for_file("a.py", waiter="b.py", timeout=5)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.1)
    tracker.mark_done("a.py")
    t.join(timeout=5)
    assert not t.is_alive()
    assert result["status"] == "done"


def test_wait_times_out_instead_of_blocking_forever():
    tracker = FileTracker()
    start = time.monotonic()
    status = tracker.wait_for_file("never.py", waiter="a.py", timeout=0.2)
    assert status == "timeout"
    assert time.monotonic() - start < 2


def test_cycle_between_two_waiters_is_broken():
    """A waits on B while B waits on A: the edge that closes the cycle gets
    "deadlock" immediately; the other waiter proceeds once its target lands."""
    tracker = FileTracker()
    statuses = {}
    a_waiting = threading.Event()

    def worker_a():
        a_waiting.set()
        statuses["a"] = tracker.wait_for_file("b.py", waiter="a.py", timeout=5)

    def worker_b():
        a_waiting.wait(timeout=5)
        time.sleep(0.1)  # let A actually block on the condition
        statuses["b"] = tracker.wait_for_file("a.py", waiter="b.py", timeout=5)
        # B proceeds without A's code and eventually finishes its file
        tracker.mark_done("b.py")

    ta = threading.Thread(target=worker_a)
    tb = threading.Thread(target=worker_b)
    ta.start()
    tb.start()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert not ta.is_alive() and not tb.is_alive()
    assert statuses["b"] == "deadlock"
    assert statuses["a"] == "done"


def test_wait_edge_cleared_after_return():
    """A finished wait must not leave a stale edge that fakes later cycles."""
    tracker = FileTracker()
    tracker.mark_done("b.py")
    assert tracker.wait_for_file("b.py", waiter="a.py") == "done"
    # If a.py -> b.py leaked, this would report a bogus cycle.
    tracker.mark_done("a.py")
    assert tracker.wait_for_file("a.py", waiter="b.py") == "done"
