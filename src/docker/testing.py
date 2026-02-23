import os
import re
import select
import shlex
import subprocess
import time
from typing import Dict, Optional

from pydantic import BaseModel

from ..utils.helpers import build_project_structure_tree
from ..utils.inference import InferenceManager
from ..utils.prompt_manager import PromptManager
from ..utils.error_tracker import ErrorTracker
from ..utils.tools import ToolHandler
from ..utils.thread_memory import ThreadMemory
from ..utils.dependencies import build_dependency_graph_tree
from .generator import generate_dockerignore_content


class PipelineState(BaseModel):
    """Single source of truth for the planner agent's pipeline progress."""
    build_success: bool = False
    test_success: bool = False
    session: int = 0
    max_sessions: int = 25
    last_build_logs: Optional[str] = None
    last_test_logs: Optional[str] = None


class DockerExecutor:
    def __init__(
        self,
        project_root: str,
        image_name: str,
        on_status=None,
    ):
        self.project_root = project_root
        self.image_name = image_name
        self.on_status = on_status
        self.build_success = False
        self.test_success = False
        self.last_build_logs: Optional[str] = None
        self.last_test_logs: Optional[str] = None

    def _emit(self, event_type: str, message: str):
        print(f"[{event_type}] {message}")
        if self.on_status:
            self.on_status(event_type, message)

    def build(self, command: str = "") -> Dict:
        """Run a docker build command. Agent provides the full command."""
        if not command:
            command = f"docker build --progress=plain -t {self.image_name} ." # ask to regenerate

        try:
            env = os.environ.copy()
            env["DOCKER_BUILDKIT"] = "1"

            process = subprocess.Popen(
                shlex.split(command),
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            output_lines = []
            last_output_time = time.time()
            stall_seconds = 150

            try:
                assert process.stdout is not None
                while True:
                    if process.poll() is not None:
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                            self._emit("docker_build", remaining.strip())
                        break

                    if hasattr(select, "select"):
                        readable, _, _ = select.select([process.stdout], [], [], 1.0)
                        if readable:
                            line = process.stdout.readline()
                            if line:
                                output_lines.append(line)
                                self._emit("docker_build", line.strip())
                                last_output_time = time.time()
                        else:
                            if time.time() - last_output_time > stall_seconds:
                                process.kill()
                                process.wait()
                                logs = (
                                    "".join(output_lines)
                                    + f"\nDocker build stalled for > {stall_seconds}s"
                                )
                                self.build_success = False
                                self.last_build_logs = logs[-3000:]
                                return {"success": False, "logs": self.last_build_logs}
                    else:
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            self._emit("docker_build", line.strip())
                            last_output_time = time.time()
                        elif process.poll() is not None:
                            break
                        elif time.time() - last_output_time > stall_seconds:
                            process.kill()
                            process.wait()
                            logs = (
                                "".join(output_lines)
                                + f"\nDocker build stalled for > {stall_seconds}s"
                            )
                            self.build_success = False
                            self.last_build_logs = logs[-3000:]
                            return {"success": False, "logs": self.last_build_logs}

                process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self.build_success = False
                self.last_build_logs = "Docker build timeout (exceeded 10 minutes)"
                return {
                    "success": False,
                    "logs": self.last_build_logs,
                }

            logs = "".join(output_lines)
            self.build_success = process.returncode == 0
            self.last_build_logs = logs[-3000:]

            return {
                "success": self.build_success,
                "logs": self.last_build_logs,
                "build_success": self.build_success,
            }

        except Exception as e:
            self.build_success = False
            self.last_build_logs = f"Docker build error: {str(e)}"
            return {"success": False, "logs": self.last_build_logs}

    def _is_test_command(self, command: str) -> bool:
        test_keywords = [
            "pytest", "npm test", "yarn test", "jest", 
            "cargo test", "go test", "rspec", "phpunit", 
            "mocha", "vitest", "python -m unittest",
            "test_runner"
        ]
        cmd_lower = command.lower()
        return any(keyword in cmd_lower for keyword in test_keywords)

    def run(self, command: str) -> Dict:
        """Run a full docker run command. Agent provides the entire command."""
        if not command:
            return {"success": False, "logs": "command is required", "exit_code": -1}

        try:
            result = subprocess.run(
                shlex.split(command),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,
            )

            logs = result.stdout + "\n" + result.stderr
            success = result.returncode == 0
            is_test = self._is_test_command(command)

            # Fix: Update internal state so it correctly syncs to PipelineState
            # Append to previous logs rather than overwriting completely
            prev_logs = self.last_test_logs
            if prev_logs:
                combined = prev_logs + f"\n\n--- Output of {command} ---\n{logs}"
            else:
                combined = f"--- Output of {command} ---\n{logs}"

            if is_test:
                self.test_success = success
            self.last_test_logs = combined[-3000:]

            return {
                "success": success,
                "logs": logs[-3000:],
                "exit_code": result.returncode,
                "test_success": self.test_success,
                "build_success": self.build_success,
                "is_test_command": is_test,
            }

        except subprocess.TimeoutExpired:
            timeout_msg = f"Command timeout (10 minutes): {command}"
            prev_logs = self.last_test_logs
            if prev_logs:
                combined = prev_logs + f"\n\n--- Output of {command} ---\n{timeout_msg}"
            else:
                combined = f"--- Output of {command} ---\n{timeout_msg}"
                
            self.test_success = False
            self.last_test_logs = combined[-3000:]
            return {
                "success": False,
                "logs": timeout_msg,
                "exit_code": -1,
                "test_success": False,
            }
        except Exception as e:
            return {
                "success": False,
                "logs": f"Docker run error: {str(e)}",
                "exit_code": -1,
                "test_success": self.test_success,
            }


class DockerTestingPipeline:
    def __init__(
        self,
        project_root: str,
        software_blueprint: Dict,
        folder_structure: str,
        file_output_format: Dict,
        pm: Optional[PromptManager] = None,
        error_tracker: Optional[ErrorTracker] = None,
        dependency_analyzer=None,
        on_status=None,
        tool_log_path: Optional[str] = None,
        provider_name: Optional[str] = None,
    ):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.dockerfile_path = os.path.join(project_root, "Dockerfile")
        self.dependency_analyzer = dependency_analyzer
        self.on_status = on_status

        self.provider_name = provider_name or InferenceManager.get_default_provider()
        self.provider = InferenceManager.create_provider(self.provider_name)

        project_name = os.path.basename(os.path.normpath(project_root))
        self.image_name = re.sub(r"[^a-z0-9-]", "-", project_name.lower())

        self.error_tracker = error_tracker or ErrorTracker(project_root)
        self.thread_memory = ThreadMemory(token_threshold=25000)

        self.docker_executor = DockerExecutor(
            project_root=project_root,
            image_name=self.image_name,
            on_status=on_status,
        )

        tool_log_path = tool_log_path or os.path.join(
            project_root, ".alpha_stack", "tool_calls.jsonl"
        )

        self.tool_handler = ToolHandler(
            project_root,
            self.error_tracker,
            image_name=self.image_name,
            dependency_analyzer=self.dependency_analyzer,
            tool_log_path=tool_log_path,
            agent_name="planner",
            thread_memory=self.thread_memory,
            docker_executor=self.docker_executor,
        )

        self.tool_definitions = InferenceManager.get_planner_tool_definitions()
        self.tools = self.provider.format_tools(self.tool_definitions)

        self.max_sessions = 25
        self.max_rounds_per_session = 15

        self.state = PipelineState(max_sessions=self.max_sessions)

    def _emit(self, event_type: str, message: str, **kwargs):
        print(f"[{event_type}] {message}")
        if self.on_status:
            self.on_status(event_type, message, **kwargs)

    def _build_dependency_graph(self) -> str:
        if self.dependency_analyzer:
            return build_dependency_graph_tree(
                self.project_root, self.dependency_analyzer
            )
        return build_project_structure_tree(self.project_root)

    def generate_dockerfile(self) -> bool:
        """Generate a Dockerfile by delegating to DockerTestFileGenerator for consistency."""
        try:
            from .generator import DockerTestFileGenerator

            gen = DockerTestFileGenerator(
                project_root=self.project_root,
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                metadata_dict={},  # We don't have a full metadata dict here, but generator can handle it
                dependency_analyzer=self.dependency_analyzer,
                pm=self.pm,
                on_status=self.on_status,
                provider=self.provider,
            )
            return gen.generate_dockerfile()
        except Exception as e:
            self._emit("error", f"Failed to generate Dockerfile: {e}")
            return False

    def _sync_state(self) -> None:
        """Sync PipelineState from DockerExecutor's current values."""
        self.state.build_success = self.docker_executor.build_success
        self.state.test_success = self.docker_executor.test_success
        self.state.last_build_logs = self.docker_executor.last_build_logs
        self.state.last_test_logs = self.docker_executor.last_test_logs

    def _build_planner_prompt(self) -> str:
        self._sync_state()
        dep_graph = self._build_dependency_graph()
        memory_context = self.thread_memory.get_context_for_prompt(max_recent=3)

        return self.pm.render(
            "planner_pipeline.j2",
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            dependency_graph=dep_graph,
            project_root=self.project_root,
            image_name=self.image_name,
            state=self.state,
            memory_context=memory_context,
        )

    # Tools that must run exclusively (never in parallel with anything)
    EXCLUSIVE_TOOLS = frozenset({"docker_build", "docker_run", "batch_edit_files"})

    def _run_planner_session(self) -> int:
        """Run one planner session. Returns the number of tool calls made.

        Tool calls are executed in parallel when possible:
        - Non-Docker tools run concurrently via a thread pool.
        - docker_build / docker_run always run alone (sequential, exclusive).
        - Results are collected in the original call order and sent back
          to the LLM only after every call in the batch has finished.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        prompt = self._build_planner_prompt()
        messages = self.provider.create_initial_message(prompt)
        tool_calls_made = 0

        for _ in range(self.max_rounds_per_session):
            response = self.provider.call_model(messages, tools=self.tools)
            function_calls = self.provider.extract_function_calls(response)

            if not function_calls:
                break

            # ── partition into ordered groups ──────────────────────────
            # Each group is either:
            #   ("parallel", [fc, fc, …])   – safe to run concurrently
            #   ("exclusive", [fc])          – must run alone
            groups = []
            current_parallel = []

            for fc in function_calls:
                if fc["name"] in self.EXCLUSIVE_TOOLS:
                    # flush any pending parallel calls first
                    if current_parallel:
                        groups.append(("parallel", list(current_parallel)))
                        current_parallel = []
                    groups.append(("exclusive", [fc]))
                else:
                    current_parallel.append(fc)

            if current_parallel:
                groups.append(("parallel", list(current_parallel)))

            # ── execute each group ────────────────────────────────────
            # results[i] will hold the function_response for function_calls[i]
            results_by_id = {}  # fc index → func_response

            # map each fc to its original index so we can reassemble in order
            fc_index = {id(fc): i for i, fc in enumerate(function_calls)}

            for kind, group_fcs in groups:
                if kind == "exclusive":
                    # single exclusive tool — run synchronously
                    fc = group_fcs[0]
                    func_name = fc["name"]
                    func_args = fc.get("args", {})

                    self._emit("tool_call", f"{func_name}({list(func_args.keys())})")
                    result = self.tool_handler.handle_function_call(func_name, func_args)
                    tool_calls_made += 1

                    func_response = self.provider.create_function_response(
                        func_name, result, fc.get("id")
                    )
                    results_by_id[fc_index[id(fc)]] = func_response

                else:
                    # parallel group — run concurrently
                    if len(group_fcs) == 1:
                        # optimisation: skip thread pool for a single call
                        fc = group_fcs[0]
                        func_name = fc["name"]
                        func_args = fc.get("args", {})

                        self._emit("tool_call", f"{func_name}({list(func_args.keys())})")
                        result = self.tool_handler.handle_function_call(func_name, func_args)
                        tool_calls_made += 1

                        func_response = self.provider.create_function_response(
                            func_name, result, fc.get("id")
                        )
                        results_by_id[fc_index[id(fc)]] = func_response
                    else:
                        # log all calls first
                        for fc in group_fcs:
                            self._emit(
                                "tool_call",
                                f"{fc['name']}({list(fc.get('args', {}).keys())}) [parallel]",
                            )

                        def _exec(fc_item):
                            return (
                                fc_item,
                                self.tool_handler.handle_function_call(
                                    fc_item["name"], fc_item.get("args", {})
                                ),
                            )

                        with ThreadPoolExecutor(max_workers=len(group_fcs)) as pool:
                            futures = {pool.submit(_exec, fc): fc for fc in group_fcs}
                            for future in as_completed(futures):
                                fc_done, result = future.result()
                                tool_calls_made += 1

                                func_response = self.provider.create_function_response(
                                    fc_done["name"], result, fc_done.get("id")
                                )
                                results_by_id[fc_index[id(fc_done)]] = func_response

            # ── reassemble responses in original order ────────────────
            function_responses = [
                results_by_id[i] for i in range(len(function_calls))
            ]

            self.provider.accumulate_messages(messages, response, function_responses)

            self._sync_state()
            if self.state.build_success and self.state.test_success:
                break

        self.thread_memory._check_and_summarize()
        return tool_calls_made

    def run_testing_pipeline(self) -> Dict:
        if not os.path.exists(self.dockerfile_path):
            self._emit("step", "No Dockerfile found, generating...")
            if not self.generate_dockerfile():
                return self._build_result("Failed to generate Dockerfile")

        self._emit("step", "Starting planner-driven pipeline...")

        for session_num in range(1, self.max_sessions + 1):
            self.state.session = session_num

            self._emit(
                "session",
                f"Session {session_num}/{self.max_sessions} "
                f"(build={'PASS' if self.state.build_success else 'PENDING'}, "
                f"test={'PASS' if self.state.test_success else 'PENDING'})",
            )

            try:
                tool_calls_made = self._run_planner_session()
            except Exception as e:
                self._emit("error", f"Session {session_num} failed: {e}")
                continue

            if self.state.build_success and self.state.test_success:
                self._emit("success", "All pipeline steps successful")
                return self._build_result("All pipeline steps successful")

            if tool_calls_made == 0:
                self._emit("warning", "Planner made no tool calls, stopping.")
                break

        msg = (
            f"Pipeline incomplete after {self.state.session} sessions: "
            f"Build {'PASS' if self.state.build_success else 'FAIL'} "
            f"Tests {'PASS' if self.state.test_success else 'FAIL'}"
        )
        self._emit("warning", msg)
        return self._build_result(msg)

    def _build_result(self, message: str) -> Dict:
        """Build the return dict from PipelineState — single source of truth."""
        return {
            "success": self.state.build_success and self.state.test_success,
            "build_success": self.state.build_success,
            "tests_success": self.state.test_success,
            "total_sessions": self.state.session,
            "message": message,
        }


def run_docker_testing(
    project_root: str,
    software_blueprint: Dict,
    folder_structure: str,
    file_output_format: Dict,
    pm=None,
    error_tracker=None,
    dependency_analyzer=None,
    on_status=None,
    tool_log_path: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Dict:
    pipeline = DockerTestingPipeline(
        project_root=project_root,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status,
        tool_log_path=tool_log_path,
        provider_name=provider_name,
    )
    return pipeline.run_testing_pipeline()
