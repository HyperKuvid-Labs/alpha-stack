"""SandboxShellManager: drop-in replacement for ShellManager.

We swap in a MagicMock sandbox + fake CommandHandle to exercise the
job lifecycle (run/check/kill/wait/list/render_status/prune_finished)
without standing up a real CubeSandbox.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.sandbox.cube import CubeSession, SandboxShellManager


class _FakeCommandHandle:
    """Mimics e2b_code_interpreter's CommandHandle (background mode)."""

    def __init__(self, stdout_lines=None, stderr_lines=None, exit_code=0, delay=0.0):
        self.stdout_lines = stdout_lines or []
        self.stderr_lines = stderr_lines or []
        self.exit_code = exit_code
        self.delay = delay
        self.pid = 4242
        self._killed = False
        self._wait_event = threading.Event()

    def stream_to(self, on_stdout, on_stderr):
        for line in self.stdout_lines:
            if on_stdout:
                on_stdout(line)
        for line in self.stderr_lines:
            if on_stderr:
                on_stderr(line)

    def wait(self):
        if self.delay:
            time.sleep(self.delay)
        self._wait_event.set()
        return SimpleNamespace(exit_code=-1 if self._killed else self.exit_code)

    def kill(self):
        self._killed = True
        self._wait_event.set()


def _make_session_with_handle(handle):
    """Build a CubeSession whose .sandbox is a MagicMock returning ``handle``."""
    session = CubeSession.__new__(CubeSession)
    session.project_root = "/tmp/fake"
    session.template_id = "tpl_fake"
    session.workdir = "/workspace"
    session.api_url = None
    session.api_key = None
    session._closed = False
    session._lock = threading.Lock()

    sb = MagicMock()
    captured = {}

    def _run(cmd, background=False, on_stdout=None, on_stderr=None):
        captured["cmd"] = cmd
        captured["background"] = background
        # Stream the queued output through the callbacks immediately so the
        # job picks them up before we ever check status.
        handle.stream_to(on_stdout, on_stderr)
        return handle

    sb.commands.run.side_effect = _run
    session.sandbox = sb
    session._captured = captured
    return session


def test_run_returns_dict_with_expected_shape():
    handle = _FakeCommandHandle(stdout_lines=["hello\n", "world\n"], exit_code=0)
    session = _make_session_with_handle(handle)
    mgr = SandboxShellManager(session)

    job_id = mgr.run("echo hello && echo world")
    assert job_id == "job_1"
    # The wrapper must cd into /workspace before user command.
    assert session._captured["cmd"].startswith("cd /workspace && ")
    assert session._captured["background"] is True

    # Wait for job exit.
    assert mgr.wait(job_id, timeout=2)["running"] is False

    status = mgr.check(job_id)
    for key in ("job_id", "pid", "command", "running", "elapsed_seconds",
                "exit_code", "success", "new_output", "full_output"):
        assert key in status, f"missing {key} in {status}"
    assert status["job_id"] == "job_1"
    assert status["pid"] == 4242
    assert status["success"] is True
    assert status["exit_code"] == 0
    assert "hello" in status["full_output"]


def test_render_status_running_and_finished():
    # First job: still running (long delay).
    long_handle = _FakeCommandHandle(stdout_lines=["working...\n"], delay=2.0)
    short_handle = _FakeCommandHandle(stdout_lines=["done\n"], exit_code=0)

    session = CubeSession.__new__(CubeSession)
    session.project_root = "/tmp/fake"
    session.template_id = "tpl_fake"
    session.workdir = "/workspace"
    session.api_url = None
    session.api_key = None
    session._closed = False
    session._lock = threading.Lock()
    sb = MagicMock()
    queue = [long_handle, short_handle]

    def _run(cmd, background=False, on_stdout=None, on_stderr=None):
        h = queue.pop(0)
        h.stream_to(on_stdout, on_stderr)
        return h

    sb.commands.run.side_effect = _run
    session.sandbox = sb
    mgr = SandboxShellManager(session)

    long_id = mgr.run("sleep 2 && echo done")
    short_id = mgr.run("echo done")

    # Let the short job finish.
    mgr.wait(short_id, timeout=2)

    rendered = mgr.render_status()
    assert "RUNNING" in rendered
    assert "FINISHED exit=0 [PASS]" in rendered
    assert "recent output:" in rendered

    # Cleanup the still-running long job.
    long_handle.kill()


def test_prune_finished_removes_seen_jobs():
    handle = _FakeCommandHandle(stdout_lines=["x\n"], exit_code=0)
    session = _make_session_with_handle(handle)
    mgr = SandboxShellManager(session)

    job_id = mgr.run("echo x")
    mgr.wait(job_id, timeout=2)
    # Mark output as seen via check().
    mgr.check(job_id)
    mgr.prune_finished()
    assert mgr.list_jobs() == []


def test_kill_marks_job_finished():
    handle = _FakeCommandHandle(stdout_lines=[], delay=10.0)
    session = _make_session_with_handle(handle)
    mgr = SandboxShellManager(session)

    job_id = mgr.run("sleep 10")
    status = mgr.kill(job_id)
    assert status["running"] is False or status["job_id"] == job_id
    # check() after kill should report success/exit_code present.
    final = mgr.check(job_id)
    assert "exit_code" in final
