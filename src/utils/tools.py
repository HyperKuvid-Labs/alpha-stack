import os
import subprocess
import threading
import time
from typing import Dict, Any, Optional


class ShellManager:
    """Persistent shell process manager — runs as a separate entity.

    The planner interacts with it through four operations:
      - run(command)     → starts a process, returns job_id immediately
      - check(job_id)    → returns status + latest output (non-blocking)
      - kill(job_id)     → kills the process
      - wait(job_id)     → blocks until the process finishes

    Each job has a background reader thread that drains stdout continuously,
    so output is always available regardless of when the planner checks.
    """

    def __init__(self, cwd: str):
        self.cwd = cwd
        self._jobs: Dict[str, "_ShellJob"] = {}
        self._lock = threading.Lock()
        self._next_id = 0

    def run(self, command: str) -> str:
        """Start a command and return a job ID immediately."""
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        with self._lock:
            self._next_id += 1
            job_id = f"job_{self._next_id}"
            self._jobs[job_id] = _ShellJob(process, command, job_id)
        return job_id

    def check(self, job_id: str) -> Dict[str, Any]:
        """Non-blocking status check. Returns current output + state."""
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        return job.status()

    def wait(self, job_id: str, timeout: float = 300) -> Dict[str, Any]:
        """Block until the job finishes or timeout."""
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        job.done_event.wait(timeout=timeout)
        return job.status()

    def kill(self, job_id: str) -> Dict[str, Any]:
        """Kill a running job."""
        job = self._get_job(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        job.kill()
        return job.status()

    def list_jobs(self) -> list[Dict[str, Any]]:
        """List all jobs with their current status."""
        with self._lock:
            return [j.status(brief=True) for j in self._jobs.values()]

    def cleanup(self):
        """Kill all running jobs. Call on pipeline exit."""
        with self._lock:
            for job in self._jobs.values():
                if job.is_alive():
                    print(f"[ShellManager] Killing {job.job_id}: {job.command[:60]}")
                    job.kill()
            self._jobs.clear()

    def render_status(self) -> str:
        """Render a prompt-ready summary of all jobs the planner should know about.

        Shows running/stalled jobs with latest output tail,
        and recently finished jobs with their exit status and output tail.
        Returns empty string if nothing noteworthy.
        """
        with self._lock:
            if not self._jobs:
                return ""

            lines = []
            for job in self._jobs.values():
                alive = job.is_alive()
                elapsed = round(time.time() - job.start_time, 1)
                n_lines = len(job.output_lines)

                if alive:
                    status_str = f"RUNNING ({elapsed}s, {n_lines} output lines)"
                else:
                    rc = job.process.returncode
                    passed = "PASS" if rc == 0 else "FAIL"
                    status_str = f"FINISHED exit={rc} [{passed}] ({elapsed}s, {n_lines} output lines)"

                # Show last 3 lines of output so the planner knows what's happening
                with job._lock:
                    tail = [l.rstrip() for l in job.output_lines[-3:] if l.strip()]
                tail_str = "\n".join(f"      | {l}" for l in tail) if tail else "      | (no output yet)"

                # Flag unseen output
                with job._lock:
                    unseen = len(job.output_lines) - job._output_cursor
                unseen_note = f" ({unseen} new lines since last check)" if unseen > 0 else ""

                lines.append(
                    f"  {job.job_id} (PID {job.pid}) [{status_str}]{unseen_note}\n"
                    f"    cmd: {job.command[:100]}\n"
                    f"    recent output:\n{tail_str}"
                )

            return "\n".join(lines)

    def has_active_jobs(self) -> bool:
        """True if any jobs are currently running."""
        with self._lock:
            return any(j.is_alive() for j in self._jobs.values())

    def prune_finished(self):
        """Remove finished jobs that the planner has already checked.

        Keeps running jobs and finished jobs with unseen output.
        """
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

    def _get_job(self, job_id: str) -> Optional["_ShellJob"]:
        with self._lock:
            return self._jobs.get(job_id)


class _ShellJob:
    """A single shell process managed by ShellManager."""

    def __init__(self, process: subprocess.Popen, command: str, job_id: str):
        self.process = process
        self.command = command
        self.job_id = job_id
        self.pid = process.pid
        self.start_time = time.time()
        self.output_lines: list[str] = []
        self.done_event = threading.Event()
        self._lock = threading.Lock()
        self._output_cursor = 0  # tracks what the planner has already seen

        # Daemon thread drains stdout continuously
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self):
        try:
            assert self.process.stdout is not None
            for line in self.process.stdout:
                with self._lock:
                    self.output_lines.append(line)
        except (ValueError, OSError):
            pass
        finally:
            self.process.wait()
            self.done_event.set()

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def kill(self):
        try:
            self.process.kill()
            self.process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        self.done_event.set()

    def status(self, brief: bool = False) -> Dict[str, Any]:
        alive = self.is_alive()
        elapsed = round(time.time() - self.start_time, 1)

        with self._lock:
            full_output = "".join(self.output_lines)
            # New output since last check
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
            result["exit_code"] = self.process.returncode
            result["success"] = self.process.returncode == 0

        result["new_output"] = new_output[-3000:]
        result["full_output"] = full_output[-3000:]
        return result


class ToolHandler:
    def __init__(self, project_root: str, error_tracker=None,
                 dependency_analyzer=None, tool_log_path: Optional[str] = None,
                 agent_name: Optional[str] = None):
        from .tool_call_log import ToolCallLogger
        self.project_root = project_root
        self.error_tracker = error_tracker
        self.dependency_analyzer = dependency_analyzer
        self.agent_name = agent_name
        self.tool_call_logger = ToolCallLogger(tool_log_path) if tool_log_path else None
        self.tests_passed: bool = False
        self.last_test_output: str = ""
        self._gave_up: bool = False
        self.shell = ShellManager(cwd=project_root)

    def cleanup(self):
        """Kill any running shell processes. Call on pipeline exit."""
        self.shell.cleanup()

    def handle_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self._log_tool_call(function_name, args)
        print(f"[tool_call] {function_name} args={list(args.keys())}")
        result = self._execute_tool(function_name, args)
        self._print_tool_result(function_name, result)
        return result

    def _execute_tool(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if function_name == "get_file_code":
            return self._get_file_code(
                args.get("file_path", ""),
                start_line=args.get("start_line"),
                end_line=args.get("end_line")
            )
        elif function_name == "update_file_code":
            file_path = args.get("file_path", "")
            new_content = (
                args.get("new_content") or
                args.get("content") or
                args.get("file_content") or
                args.get("code") or
                ""
            )
            change_description = args.get("change_description", args.get("description", ""))
            if not new_content:
                return {
                    "success": False,
                    "error": "No content provided. Expected 'new_content', 'content', 'file_content', or 'code' parameter."
                }
            return self._update_file_code(file_path, new_content, change_description)
        elif function_name == "log_change":
            return self._log_change(
                args["file_path"],
                args["change_description"],
                args["error_context"]
            )
        elif function_name == "regenerate_file":
            return self._regenerate_file(
                file_path=args.get("file_path", ""),
                context=args.get("context", "")
            )
        elif function_name == "create_directory":
            return self._create_directory(
                args.get("directory_path", ""),
                args.get("create_parents", True)
            )
        elif function_name == "delete_file":
            return self._delete_file(args.get("file_path", ""))
        elif function_name == "get_error_history":
            return self._get_error_history(
                error_id=args.get("error_id"),
                limit=int(args.get("limit", 20)) if args.get("limit") is not None else 20,
                offset=int(args.get("offset", 0)) if args.get("offset") is not None else 0,
                include_logs=bool(args.get("include_logs", False))
            )
        elif function_name == "get_action_history":
            return self._get_action_history(
                limit=int(args.get("limit", 20)) if args.get("limit") is not None else 20,
                offset=int(args.get("offset", 0)) if args.get("offset") is not None else 0,
                task_id=args.get("task_id")
            )
        elif function_name == "log_action":
            return self._log_action(
                task_id=args.get("task_id"),
                action_type=args.get("action_type", ""),
                message=args.get("message", "")
            )
        elif function_name == "run_shell_command":
            return self._run_shell_command(
                command=args.get("command", ""),
                timeout_sec=int(args.get("timeout_sec", 60)) if args.get("timeout_sec") is not None else 60
            )
        elif function_name == "patch_file":
            return self._patch_file(
                file_path=args.get("file_path", ""),
                fix_type=args.get("fix_type", ""),
                description=args.get("description", ""),
                line_start=int(args["line_start"]) if args.get("line_start") is not None else None,
                line_end=int(args["line_end"]) if args.get("line_end") is not None else None,
                new_content=args.get("new_content")
            )
        elif function_name == "get_file_dependencies":
            return self._get_file_dependencies(args.get("file_path", ""))
        elif function_name == "get_file_dependents":
            return self._get_file_dependents(args.get("file_path", ""))
        elif function_name == "batch_edit_files":
            return self._batch_edit_files(tasks=args.get("tasks", []))
        elif function_name == "batch_read_files":
            return self._batch_read_files(file_paths=args.get("file_paths", []))
        elif function_name == "give_up":
            return self._give_up(reason=args.get("reason", "No reason provided."))
        elif function_name == "mark_complete":
            return self._mark_complete(reason=args.get("reason", "No reason provided."))
        else:
            return {"error": f"Unknown function: {function_name}"}

    def _log_tool_call(self, function_name: str, args: Dict[str, Any]) -> None:
        if not self.tool_call_logger:
            return
        try:
            self.tool_call_logger.log(self.agent_name, function_name, args)
        except Exception:
            pass

    def _give_up(self, reason: str) -> Dict[str, Any]:
        """Stop everything and signal that the agent has given up."""
        print(f"\n[!] AGENT GAVE UP: {reason}\n")
        self._gave_up = True
        return {
            "success": False,
            "gave_up": True,
            "reason": reason,
            "message": "Session terminated because the agent gave up."
        }

    def _mark_complete(self, reason: str) -> Dict[str, Any]:
        """Agent signals tests pass. Requires that at least one shell command has been run."""
        if not self.last_test_output:
            return {
                "success": False,
                "error": (
                    "Cannot mark complete: no shell commands have been run yet. "
                    "Run your test command first and confirm the output shows tests passing."
                ),
            }

        self.tests_passed = True
        print(f"\n[✓] AGENT MARKED COMPLETE: {reason}\n")
        return {
            "success": True,
            "marked_complete": True,
            "reason": reason,
            "message": "Pipeline marked as complete by agent.",
        }

    @staticmethod
    def _print_tool_result(function_name: str, result: Dict[str, Any]) -> None:
        try:
            preview = dict(result)
            if "content" in preview and isinstance(preview["content"], str):
                preview["content"] = preview["content"][:300]
            if "stdout" in preview and isinstance(preview["stdout"], str):
                preview["stdout"] = preview["stdout"][:300]
            if "stderr" in preview and isinstance(preview["stderr"], str):
                preview["stderr"] = preview["stderr"][:300]
            print(f"[tool_result] {function_name} -> {preview}")
        except Exception:
            print(f"[tool_result] {function_name} -> <unavailable>")

    def _get_file_code(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        if not file_path:
            return {"error": "file_path is required"}

        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return {"error": f"File not found: {file_path}"}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            if start_line is not None or end_line is not None:
                start = max(int(start_line or 1), 1)
                end = min(int(end_line or total_lines), total_lines)
                if start > end:
                    return {"error": "start_line must be <= end_line"}
                content = "".join(lines[start - 1:end])
                return {
                    "success": True,
                    "file_path": file_path,
                    "content": content,
                    "start_line": start,
                    "end_line": end,
                    "total_lines": total_lines
                }

            content = "".join(lines)
            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "total_lines": total_lines
            }
        except Exception as e:
            return {"error": f"Error reading file: {str(e)}"}

    def _log_change(self, file_path: str, change_description: str, error_context: str) -> Dict[str, Any]:
        if self.error_tracker:
            full_path = os.path.join(self.project_root, file_path)
            self.error_tracker.log_change(
                file_path=full_path,
                change_description=change_description,
                error_context=error_context
            )
            return {"success": True, "message": "Change logged successfully"}
        else:
            return {"success": True, "message": "Change logged (no tracker available)"}

    def _get_error_history(self, error_id: Optional[str] = None, limit: int = 20, offset: int = 0, include_logs: bool = False) -> Dict[str, Any]:
        if not self.error_tracker:
            return {"error": "No error tracker available"}
        return self.error_tracker.get_error_history(error_id=error_id, limit=limit, offset=offset, include_logs=include_logs)

    def _get_action_history(self, limit: int = 20, offset: int = 0, task_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.error_tracker:
            return {"error": "No error tracker available"}
        return self.error_tracker.get_action_history(limit=limit, offset=offset, task_id=task_id)

    def _log_action(self, task_id: Optional[str], action_type: str, message: str) -> Dict[str, Any]:
        if not self.error_tracker:
            return {"success": False, "error": "No error tracker available"}
        return self.error_tracker.log_action(task_id=task_id, action_type=action_type, message=message)

    def _regenerate_file(self, file_path: str, context: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "File regeneration requires blueprint context. Use update_file_code with content generated from blueprint.",
            "file_path": file_path,
            "context": context
        }

    def _update_file_code(self, file_path: str, new_content: str, change_description: str) -> Dict[str, Any]:
        from .helpers import clean_agent_output

        if not file_path:
            return {"error": "file_path is required"}

        new_content = clean_agent_output(new_content)

        full_path = os.path.join(self.project_root, file_path)

        old_content = None
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except Exception:
                pass

        try:
            dir_path = os.path.dirname(full_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return {
                "success": True,
                "file_path": file_path,
                "message": f"File updated successfully: {change_description}",
                "bytes_written": len(new_content),
            }
        except Exception as e:
            return {"error": f"Error updating file: {str(e)}"}

    def _create_directory(self, directory_path: str, create_parents: bool = True) -> Dict[str, Any]:
        if not directory_path:
            return {"error": "directory_path is required"}

        full_path = os.path.join(self.project_root, directory_path)

        if os.path.exists(full_path):
            if os.path.isdir(full_path):
                return {
                    "success": True,
                    "directory_path": directory_path,
                    "message": "Directory already exists"
                }
            else:
                return {"error": f"Path exists but is not a directory: {directory_path}"}

        try:
            if create_parents:
                os.makedirs(full_path, exist_ok=True)
            else:
                parent = os.path.dirname(full_path)
                if not os.path.exists(parent):
                    return {"error": f"Parent directory does not exist: {os.path.dirname(directory_path)}"}
                os.mkdir(full_path)

            return {
                "success": True,
                "directory_path": directory_path
            }
        except Exception as e:
            return {"error": f"Error creating directory: {str(e)}"}

    def _delete_file(self, file_path: str) -> Dict[str, Any]:
        if not file_path:
            return {"error": "file_path is required"}

        full_path = os.path.join(self.project_root, file_path)

        if not os.path.exists(full_path):
            return {"error": f"File not found: {file_path}"}

        if os.path.isdir(full_path):
            return {"error": f"Path is a directory, not a file: {file_path}"}

        try:
            os.remove(full_path)
            return {
                "success": True,
                "file_path": file_path
            }
        except Exception as e:
            return {"error": f"Error deleting file: {str(e)}"}

    # Patterns that suggest the process is waiting for user input
    _STDIN_WAIT_PATTERNS = (
        "[y/n]", "[yes/no]", "(y/n)", "(yes/no)",
        "password:", "passphrase:", "enter password",
        "press enter", "press any key",
        "are you sure", "do you want to continue",
        "proceed?", "confirm",
    )

    def _detect_stall_cause(self, output: str) -> str:
        """Analyze the last few output lines to guess why the process stalled."""
        lines = [l for l in output.strip().splitlines() if l.strip()]
        tail = "\n".join(lines[-5:]).lower()

        for pattern in self._STDIN_WAIT_PATTERNS:
            if pattern in tail:
                return (
                    f"Likely waiting for user input (detected '{pattern}'). "
                    f"Fix: pipe 'yes |' before the command, or add flags like --yes, -y, "
                    f"--non-interactive, or remove interactive prompts from the code."
                )

        if not lines:
            return (
                "No output was produced at all. Possible causes: "
                "command not found, immediate deadlock, or blocked on network/DNS."
            )

        return (
            "Process produced output then went silent. Possible causes: "
            "deadlock, infinite loop without print, waiting for stdin, "
            "or blocked on a network request/external service."
        )

    def _run_shell_command(self, command: str, timeout_sec: int = 60) -> Dict[str, Any]:
        """Run a shell command via ShellManager.

        Submits the command, then polls for completion. If the process
        produces no new output for ``timeout_sec`` seconds, it is considered
        stalled — control returns to the planner with the process still alive.
        The planner can then investigate, kill it, or check back later.
        """
        if not command or not isinstance(command, str):
            return {"error": "command is required"}

        # Job management commands — planner can manage background processes
        cmd_stripped = command.strip()

        if cmd_stripped.startswith("check_job "):
            jid = cmd_stripped.split(" ", 1)[1].strip()
            result = self.shell.check(jid)
            if "full_output" in result:
                self.last_test_output = result["full_output"][-3000:]
            return result

        if cmd_stripped.startswith("kill_job "):
            jid = cmd_stripped.split(" ", 1)[1].strip()
            result = self.shell.kill(jid)
            # After killing, get the full status with all collected output
            final = self.shell.check(jid)
            if "full_output" in final:
                self.last_test_output = final["full_output"][-3000:]
                result = final
                result["killed"] = True
            return result

        if cmd_stripped.startswith("wait_job "):
            # Block until job finishes — useful if planner wants to resume waiting
            jid = cmd_stripped.split(" ", 1)[1].strip()
            result = self.shell.wait(jid, timeout=300)
            if "full_output" in result:
                self.last_test_output = result["full_output"][-3000:]
            return result

        if cmd_stripped == "list_jobs":
            return {"jobs": self.shell.list_jobs()}

        try:
            job_id = self.shell.run(command)
            job = self.shell._get_job(job_id)
            if not job:
                return {"error": "Failed to start command"}

            # Wait for completion, checking for stalls
            last_output_len = 0
            last_progress_time = time.time()

            while not job.done_event.wait(timeout=1.0):
                current_len = len(job.output_lines)
                if current_len > last_output_len:
                    last_output_len = current_len
                    last_progress_time = time.time()
                elif time.time() - last_progress_time > timeout_sec:
                    # Stalled — return control to planner, process stays alive
                    status = job.status()
                    output = status.get("full_output", "")
                    stall_cause = self._detect_stall_cause(output)

                    tail_lines = output.strip().splitlines()[-5:]
                    tail_preview = "\n".join(tail_lines) if tail_lines else "(no output)"

                    stall_msg = (
                        f"Command stalled — no output for {timeout_sec}s. "
                        f"Process still running ({job_id}, PID {job.pid}).\n"
                        f"\n"
                        f"Last output before stall:\n{tail_preview}\n"
                        f"\n"
                        f"Diagnosis: {stall_cause}\n"
                        f"\n"
                        f"Actions available:\n"
                        f"  - run_shell_command(command=\"check_job {job_id}\") → see latest output\n"
                        f"  - run_shell_command(command=\"kill_job {job_id}\") → kill the process\n"
                        f"  - run other shell commands to investigate (ps, read logs, etc)"
                    )

                    self.last_test_output = output[-3000:] + f"\n\n[STALLED] {stall_msg}"
                    return {
                        "success": False,
                        "command": command,
                        "exit_code": -1,
                        "job_id": job_id,
                        "pid": job.pid,
                        "stdout": output[-3000:],
                        "stalled": True,
                        "stall_seconds": timeout_sec,
                        "stderr": stall_msg,
                    }

            # Process finished
            status = job.status()
            output = status.get("full_output", "")
            success = status.get("success", False)
            exit_code = status.get("exit_code", -1)

            self.last_test_output = output[-3000:]

            if not success and self.error_tracker:
                self.error_tracker.log_error({
                    "error_type": "command_failed",
                    "file": "",
                    "error": f"exit {exit_code}: {command}",
                })

            return {
                "success": success,
                "command": command,
                "exit_code": exit_code,
                "job_id": job_id,
                "stdout": output[-3000:],
                "stderr": "",
            }

        except Exception as e:
            return {"error": f"Command failed: {str(e)}"}

    def _patch_file(
        self,
        file_path: str,
        fix_type: str,
        description: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        new_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not file_path:
            return {"error": "file_path is required"}
        if fix_type not in ("full_rewrite", "delete_lines", "replace_lines", "insert_after_line"):
            return {"error": f"Unknown fix_type '{fix_type}'. Must be one of: full_rewrite, delete_lines, replace_lines, insert_after_line"}

        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return {"error": f"File not found: {file_path}"}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return {"error": f"Error reading file: {str(e)}"}

        # Capture old snippet for the result summary
        old_snippet = "(none)"
        if fix_type != "full_rewrite" and line_start is not None:
            start_idx = line_start - 1
            end_idx = (line_end or line_start) - 1
            old_snippet = "".join(lines[start_idx: end_idx + 1]).strip() or "(none)"

        new_snippet = (new_content or "(delete)").strip()

        # Apply the patch
        n = len(lines)
        if fix_type == "full_rewrite":
            content = new_content or ""
            if not content.endswith("\n"):
                content += "\n"
            patched_lines = [content]
        elif fix_type == "delete_lines":
            start = max(0, (line_start or 1) - 1)
            end = max(start, min((line_end or line_start or 1) - 1, n - 1))
            patched_lines = lines[:start] + lines[end + 1:]
        elif fix_type == "replace_lines":
            start = max(0, (line_start or 1) - 1)
            end = max(start, min((line_end or line_start or 1) - 1, n - 1))
            replacement = new_content or ""
            if not replacement.endswith("\n"):
                replacement += "\n"
            patched_lines = lines[:start] + [replacement] + lines[end + 1:]
        elif fix_type == "insert_after_line":
            end = max(0, min((line_end or line_start or 1) - 1, n - 1))
            insertion = new_content or ""
            if not insertion.endswith("\n"):
                insertion += "\n"
            patched_lines = lines[:end + 1] + [insertion] + lines[end + 1:]
        else:
            patched_lines = lines

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write("".join(patched_lines))
        except Exception as e:
            return {"error": f"Error writing patched file: {str(e)}"}

        return {
            "success": True,
            "file_path": file_path,
            "fix_type": fix_type,
            "description": description,
            "line_start": line_start,
            "line_end": line_end,
            "old": old_snippet,
            "new": new_snippet,
        }

    def _get_file_dependencies(self, file_path: str) -> Dict[str, Any]:
        if not self.dependency_analyzer:
            return {"error": "Dependency analyzer not available"}
        if not file_path:
            return {"error": "file_path is required"}
        full_path = os.path.join(self.project_root, file_path)
        deps = self.dependency_analyzer.get_dependencies(full_path)
        rel_deps = [os.path.relpath(p, self.project_root) for p in deps]
        return {"success": True, "file_path": file_path, "dependencies": rel_deps}

    def _get_file_dependents(self, file_path: str) -> Dict[str, Any]:
        if not self.dependency_analyzer:
            return {"error": "Dependency analyzer not available"}
        if not file_path:
            return {"error": "file_path is required"}
        full_path = os.path.join(self.project_root, file_path)
        deps = self.dependency_analyzer.get_dependents(full_path)
        rel_deps = [os.path.relpath(p, self.project_root) for p in deps]
        return {"success": True, "file_path": file_path, "dependents": rel_deps}

    def _batch_edit_files(self, tasks: list) -> Dict[str, Any]:
        from .corrector_tool import batch_edit_files
        return batch_edit_files(tasks, self)

    def _batch_read_files(self, file_paths: list) -> Dict[str, Any]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not file_paths:
            return {"success": False, "error": "No file_paths provided"}

        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for fp in file_paths:
            if fp and fp not in seen:
                seen.add(fp)
                unique_paths.append(fp)

        if not unique_paths:
            return {"success": False, "error": "No valid file paths provided"}

        print(f"[batch_read] Reading {len(unique_paths)} files in parallel...")

        def _read_one(fp: str) -> Dict[str, Any]:
            try:
                result = self._get_file_code(fp)
                return {"file_path": fp, **result}
            except Exception as e:
                return {"file_path": fp, "success": False, "error": str(e)}

        results = []
        with ThreadPoolExecutor(max_workers=min(len(unique_paths), 8)) as pool:
            future_to_path = {
                pool.submit(_read_one, fp): fp for fp in unique_paths
            }
            for future in as_completed(future_to_path):
                try:
                    result = future.result()
                except Exception as e:
                    fp = future_to_path[future]
                    result = {"file_path": fp, "success": False, "error": str(e)}
                results.append(result)

        # Sort results back to input order
        path_order = {fp: i for i, fp in enumerate(unique_paths)}
        results.sort(key=lambda r: path_order.get(r["file_path"], 999))

        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded

        return {
            "success": failed == 0,
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

