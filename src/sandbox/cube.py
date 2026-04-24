"""CubeSandbox-backed isolated execution for the testing pipeline.

CubeSandbox (https://github.com/TencentCloud/CubeSandbox) speaks the same
SDK as E2B (`from e2b_code_interpreter import Sandbox`), so we go through
that client and point it at the local CubeSandbox API URL.

Two pieces live here:
  - ``CubeSession``: owns the sandbox handle, mirrors the local project tree
    into ``/workspace`` on start, and exposes mirror operations
    (push_file/delete_file/mkdir) for the ToolHandler to call after
    successful local edits.
  - ``SandboxShellManager`` (and ``_SandboxJob``): a drop-in replacement for
    ``utils.tools.ShellManager`` that runs commands inside the sandbox.
    Same method names, same return-dict shape — so the planner's
    ``_run_shell_command`` and the prompt's ``render_status`` work unchanged.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional


class SandboxStartupError(RuntimeError):
    """Raised when the sandbox cannot be started (missing config, SDK, etc.)."""


# Directories/files we never copy into the sandbox — saves time and avoids
# stuffing the microVM with build artefacts that the planner never needs.
_SKIP_DIRS = frozenset({
    ".git",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".alpha_stack",
    ".idea",
    ".vscode",
})

_SKIP_SUFFIXES = (".pyc", ".pyo", ".pyd")


class CubeSession:
    """A live CubeSandbox session, mirroring the local project tree."""

    def __init__(
        self,
        project_root: str,
        template_id: str,
        workdir: str = "/workspace",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        if not template_id:
            raise SandboxStartupError(
                "CubeSandbox template_id is required. Run "
                "`alphastack sandbox --template-id <id>` after creating a template "
                "with `cubemastercli tpl create-from-image --image "
                "ccr.ccs.tencentyun.com/ags-image/sandbox-code:latest`."
            )

        self.project_root = os.path.abspath(project_root)
        self.template_id = template_id
        self.workdir = workdir.rstrip("/") or "/workspace"
        self.api_url = api_url
        self.api_key = api_key

        self.sandbox = None
        self._closed = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> "CubeSession":
        """Create the sandbox and seed it with the project tree."""
        if self.sandbox is not None:
            return self

        try:
            from e2b_code_interpreter import Sandbox
        except ImportError as exc:
            raise SandboxStartupError(
                "e2b_code_interpreter is not installed. Run "
                "`pip install e2b-code-interpreter` (or reinstall alphastack)."
            ) from exc

        # The E2B SDK reads connection info from env vars, so set them just for
        # the lifetime of the call. Don't overwrite values the user has already
        # exported themselves.
        prev_url = os.environ.get("E2B_API_URL")
        prev_key = os.environ.get("E2B_API_KEY")
        try:
            if self.api_url and not prev_url:
                os.environ["E2B_API_URL"] = self.api_url
            if self.api_key and not prev_key:
                os.environ["E2B_API_KEY"] = self.api_key

            try:
                self.sandbox = Sandbox.create(template=self.template_id)
            except Exception as exc:
                raise SandboxStartupError(
                    f"Failed to create CubeSandbox (template={self.template_id}): {exc}"
                ) from exc
        finally:
            if prev_url is None and "E2B_API_URL" in os.environ and self.api_url:
                # leave the env var set so child processes can also reach the sandbox
                pass

        try:
            self.sandbox.commands.run(f"mkdir -p {self.workdir}")
        except Exception:
            pass

        self._upload_project()
        return self

    def __enter__(self) -> "CubeSession":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Idempotent shutdown — kills the sandbox if still alive."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            sb = self.sandbox
            self.sandbox = None
        if sb is None:
            return
        try:
            sb.kill()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # mirroring
    # ------------------------------------------------------------------
    def _iter_project_files(self):
        """Yield (rel_path, abs_path) for every file we should ship to the sandbox."""
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # Filter directories in-place so os.walk skips them entirely.
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

            for fname in filenames:
                if fname.endswith(_SKIP_SUFFIXES):
                    continue
                abs_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(abs_path, self.project_root)
                rel = rel.replace(os.sep, "/")
                yield rel, abs_path

    def _upload_project(self) -> None:
        if self.sandbox is None:
            return
        for rel, abs_path in self._iter_project_files():
            try:
                with open(abs_path, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            try:
                self.sandbox.files.write(self._sandbox_path(rel), data)
            except Exception:
                # Best-effort — surface upload failures via the planner's first
                # shell command rather than crashing the whole pipeline.
                pass

    def _sandbox_path(self, rel_path: str) -> str:
        rel = (rel_path or "").replace(os.sep, "/").lstrip("/")
        return f"{self.workdir}/{rel}" if rel else self.workdir

    def push_file(self, rel_path: str) -> None:
        """Mirror a single locally-edited file into the sandbox."""
        if self.sandbox is None or not rel_path:
            return
        abs_path = os.path.join(self.project_root, rel_path)
        if not os.path.isfile(abs_path):
            return
        with open(abs_path, "rb") as fh:
            data = fh.read()
        self.sandbox.files.write(self._sandbox_path(rel_path), data)

    def delete_file(self, rel_path: str) -> None:
        if self.sandbox is None or not rel_path:
            return
        target = self._sandbox_path(rel_path)
        # Use a shell call: avoids needing a separate files.delete API and
        # doesn't error when the file has already been removed.
        self.sandbox.commands.run(f"rm -f '{target}'")

    def mkdir(self, rel_path: str) -> None:
        if self.sandbox is None or not rel_path:
            return
        target = self._sandbox_path(rel_path)
        self.sandbox.commands.run(f"mkdir -p '{target}'")


# ----------------------------------------------------------------------
# Sandbox-backed shell manager
# ----------------------------------------------------------------------


class _SandboxJob:
    """A single sandbox command — mirrors ``utils.tools._ShellJob``."""

    def __init__(self, command: str, job_id: str, workdir: str):
        self.command = command
        self.job_id = job_id
        self.pid = 0  # populated once the sandbox tells us
        self.start_time = time.time()
        self.workdir = workdir
        self.output_lines: List[str] = []
        self.done_event = threading.Event()
        self._lock = threading.Lock()
        self._output_cursor = 0
        self.exit_code: Optional[int] = None
        self.handle = None  # CommandHandle from e2b_code_interpreter

    def _on_stdout(self, line: str) -> None:
        if line is None:
            return
        text = line if line.endswith("\n") else line + "\n"
        with self._lock:
            self.output_lines.append(text)

    def _on_stderr(self, line: str) -> None:
        self._on_stdout(line)

    def attach(self, handle) -> None:
        self.handle = handle
        try:
            self.pid = getattr(handle, "pid", 0) or 0
        except Exception:
            self.pid = 0

        thread = threading.Thread(target=self._wait_for_exit, daemon=True)
        thread.start()

    def _wait_for_exit(self) -> None:
        if self.handle is None:
            self.done_event.set()
            return
        try:
            result = self.handle.wait()
        except Exception as exc:
            self._on_stderr(f"[sandbox] wait failed: {exc}")
            self.exit_code = -1
        else:
            code = getattr(result, "exit_code", None)
            if code is None:
                code = getattr(result, "exitCode", None)
            self.exit_code = int(code) if code is not None else -1
        finally:
            self.done_event.set()

    def is_alive(self) -> bool:
        return not self.done_event.is_set()

    def kill(self) -> None:
        if self.handle is not None:
            try:
                self.handle.kill()
            except Exception:
                pass
        self.done_event.set()

    def status(self, brief: bool = False) -> Dict[str, Any]:
        alive = self.is_alive()
        elapsed = round(time.time() - self.start_time, 1)

        with self._lock:
            full_output = "".join(self.output_lines)
            new_output = "".join(self.output_lines[self._output_cursor:])
            self._output_cursor = len(self.output_lines)

        result: Dict[str, Any] = {
            "job_id": self.job_id,
            "pid": self.pid,
            "command": self.command,
            "running": alive,
            "elapsed_seconds": elapsed,
        }

        if brief:
            result["output_lines"] = len(self.output_lines)
            return result

        if not alive:
            rc = self.exit_code if self.exit_code is not None else -1
            result["exit_code"] = rc
            result["success"] = rc == 0

        result["new_output"] = new_output[-3000:]
        result["full_output"] = full_output[-3000:]
        return result


class SandboxShellManager:
    """Drop-in replacement for ``ShellManager`` that runs inside CubeSandbox."""

    def __init__(self, session: CubeSession):
        self.session = session
        self.workdir = session.workdir
        self._jobs: Dict[str, _SandboxJob] = {}
        self._lock = threading.Lock()
        self._next_id = 0

    # ------------------------------------------------------------------
    # job operations (same surface as ShellManager)
    # ------------------------------------------------------------------
    def run(self, command: str) -> str:
        sandbox = self._require_sandbox()
        with self._lock:
            self._next_id += 1
            job_id = f"job_{self._next_id}"
            job = _SandboxJob(command, job_id, self.workdir)
            self._jobs[job_id] = job

        full_cmd = f"cd {self.workdir} && {command}"
        handle = sandbox.commands.run(
            full_cmd,
            background=True,
            on_stdout=job._on_stdout,
            on_stderr=job._on_stderr,
        )
        job.attach(handle)
        return job_id

    def check(self, job_id: str) -> Dict[str, Any]:
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        return job.status()

    def wait(self, job_id: str, timeout: float = 300) -> Dict[str, Any]:
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        job.done_event.wait(timeout=timeout)
        return job.status()

    def kill(self, job_id: str) -> Dict[str, Any]:
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        job.kill()
        return job.status()

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.status(brief=True) for j in self._jobs.values()]

    def cleanup(self) -> None:
        with self._lock:
            jobs = list(self._jobs.values())
            self._jobs.clear()
        for job in jobs:
            if job.is_alive():
                print(f"[SandboxShellManager] Killing {job.job_id}: {job.command[:60]}")
                job.kill()

    def has_active_jobs(self) -> bool:
        with self._lock:
            return any(j.is_alive() for j in self._jobs.values())

    def prune_finished(self) -> None:
        with self._lock:
            to_remove = []
            for jid, job in self._jobs.items():
                if not job.is_alive():
                    with job._lock:
                        unseen = len(job.output_lines) - job._output_cursor
                    if unseen == 0:
                        to_remove.append(jid)
            for jid in to_remove:
                del self._jobs[jid]

    def render_status(self) -> str:
        with self._lock:
            if not self._jobs:
                return ""

            lines: List[str] = []
            for job in self._jobs.values():
                alive = job.is_alive()
                elapsed = round(time.time() - job.start_time, 1)
                n_lines = len(job.output_lines)

                if alive:
                    status_str = f"RUNNING ({elapsed}s, {n_lines} output lines)"
                else:
                    rc = job.exit_code if job.exit_code is not None else -1
                    passed = "PASS" if rc == 0 else "FAIL"
                    status_str = (
                        f"FINISHED exit={rc} [{passed}] ({elapsed}s, {n_lines} output lines)"
                    )

                with job._lock:
                    tail = [l.rstrip() for l in job.output_lines[-3:] if l.strip()]
                tail_str = (
                    "\n".join(f"      | {l}" for l in tail)
                    if tail
                    else "      | (no output yet)"
                )

                with job._lock:
                    unseen = len(job.output_lines) - job._output_cursor
                unseen_note = (
                    f" ({unseen} new lines since last check)" if unseen > 0 else ""
                )

                lines.append(
                    f"  {job.job_id} (PID {job.pid}) [{status_str}]{unseen_note}\n"
                    f"    cmd: {job.command[:100]}\n"
                    f"    recent output:\n{tail_str}"
                )

            return "\n".join(lines)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _get_job(self, job_id: str) -> Optional[_SandboxJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def _require_sandbox(self):
        if self.session.sandbox is None:
            raise SandboxStartupError(
                "CubeSandbox session is not running. Call start() first."
            )
        return self.session.sandbox
