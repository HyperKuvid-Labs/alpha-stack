import os
from typing import Dict, Optional

from pydantic import BaseModel

from ..utils.helpers import build_project_structure_tree
from ..utils.inference import InferenceManager
from ..utils.prompt_manager import PromptManager
from ..utils.error_tracker import ErrorTracker
from ..utils.tools import ToolHandler
from ..utils.dependencies import build_dependency_graph_tree
from ..utils.agent_memory import AgentMemory


class PipelineState(BaseModel):
    """Single source of truth for the planner agent's pipeline progress."""
    tests_passed: bool = False
    gave_up: bool = False
    last_test_output: Optional[str] = None


class TestingPipeline:
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
        requirements_json: Optional[str] = None,
        oracle_checks: Optional[list] = None,
    ):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.dependency_analyzer = dependency_analyzer
        self.on_status = on_status
        self.requirements_json = requirements_json
        self.oracle_checks = oracle_checks or []

        self.provider = InferenceManager.get_active_provider()
        self.provider_name = InferenceManager._active_provider_name or ""

        self.error_tracker = error_tracker or ErrorTracker(project_root)

        tool_log_path = tool_log_path or os.path.join(
            project_root, ".alpha_stack", "tool_calls.jsonl"
        )

        self.tool_handler = ToolHandler(
            project_root,
            self.error_tracker,
            dependency_analyzer=self.dependency_analyzer,
            tool_log_path=tool_log_path,
            agent_name="planner",
        )

        self.tool_definitions = InferenceManager.get_planner_tool_definitions()
        self.tools = self.provider.format_tools(self.tool_definitions)

        self.max_rounds = 200  # max tool call rounds in one continuous conversation

        self.state = PipelineState()
        self.memory = AgentMemory(project_root=project_root, role="planner")
        self._cached_dep_graph: Optional[str] = None

    def _emit(self, event_type: str, message: str, **kwargs):
        print(f"[{event_type}] {message}")
        if self.on_status:
            self.on_status(event_type, message, **kwargs)

    def _build_dependency_graph(self, force_rebuild: bool = False) -> str:
        """Build the dependency graph, cached. Rebuild if files were edited."""
        if self._cached_dep_graph and not force_rebuild:
            return self._cached_dep_graph
        if self.dependency_analyzer:
            self._cached_dep_graph = build_dependency_graph_tree(self.project_root, self.dependency_analyzer)
        else:
            self._cached_dep_graph = build_project_structure_tree(self.project_root)
        return self._cached_dep_graph

    def _sync_state(self) -> None:
        """Sync PipelineState from ToolHandler's current values."""
        self.state.tests_passed = self.tool_handler.tests_passed
        self.state.gave_up = getattr(self.tool_handler, "_gave_up", False)
        self.state.last_test_output = self.tool_handler.last_test_output

    def _build_planner_prompt(self) -> str:
        self._sync_state()

        # Per-round housekeeping: clear "context already shown" so each new
        # round can re-attach DGAT context to file reads.
        self.tool_handler.clear_shown_context()

        # If files were edited last round, run `dgat update` synchronously
        # before composing the prompt — this refreshes file/edge descriptions
        # and lets us render an accurate blast radius.
        blast_radius = ""
        force_rebuild = False
        if self.dependency_analyzer and self.dependency_analyzer.has_dirty():
            edited = self.dependency_analyzer.pop_dirty()
            self._emit(
                "step",
                f"DGAT update: {len(edited)} edited file(s) → re-describing...",
            )
            update_res = self.dependency_analyzer.run_update()
            if update_res.get("ok"):
                self._emit(
                    "step",
                    f"DGAT update complete in {update_res.get('elapsed', 0):.1f}s",
                )
                force_rebuild = True
            else:
                self._emit(
                    "warning",
                    f"DGAT update skipped: {update_res.get('message', 'unknown')}",
                )
            try:
                blast_radius = self.dependency_analyzer.compute_blast_radius(edited)
            except Exception as exc:
                self._emit("warning", f"blast-radius render failed: {exc}")

        dep_graph = self._build_dependency_graph(force_rebuild=force_rebuild)

        # Prune finished jobs the planner has already seen, then render
        self.tool_handler.shell.prune_finished()
        active_jobs = self.tool_handler.shell.render_status()

        return self.pm.render(
            "planner_pipeline.j2",
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            dependency_graph=dep_graph,
            project_root=self.project_root,
            requirements_checklist=self.requirements_json,
            state=self.state,
            memory=self.memory.render(query=self.state.last_test_output) if self.memory else "",
            active_jobs=active_jobs,
            blast_radius=blast_radius,
        )

    EXCLUSIVE_TOOLS = frozenset({"batch_edit_files", "give_up", "mark_complete"})
    READ_TOOLS = frozenset({"get_file_code", "get_file_dependencies", "get_file_dependents", "batch_read_files"})

    def _affected_files_for(self, rel_path: str) -> list:
        """DGAT dependents of `rel_path`, used to enrich memory edit entries.

        Reads the analyzer's pre-update state — accurate enough for working
        memory; the post-update view becomes available next round via
        the blast-radius section.
        """
        if not rel_path or not self.dependency_analyzer:
            return []
        try:
            node = self.dependency_analyzer.find_node(rel_path)
        except Exception:
            return []
        if node is None:
            return []
        return list(getattr(node, "depended_by", []) or [])

    def _record_tool_to_memory(self, func_name: str, func_args: dict, result):
        """Record a tool call to memory. Skips read-only tools."""
        if func_name in self.READ_TOOLS:
            return

        if func_name == "update_file_code":
            fp = func_args.get("file_path", "")
            self.memory.record_edit(
                0, fp, func_args.get("change_description", ""),
                affected_files=self._affected_files_for(fp),
            )

        elif func_name == "patch_file":
            fp = func_args.get("file_path", "")
            self.memory.record_edit(
                0, fp, func_args.get("description", ""),
                affected_files=self._affected_files_for(fp),
            )

        elif func_name == "batch_edit_files":
            tasks = func_args.get("tasks", []) or []
            affected: list = []
            seen: set = set()
            for t in tasks:
                for a in self._affected_files_for(t.get("file_path", "")):
                    if a not in seen:
                        seen.add(a)
                        affected.append(a)
            self.memory.record_batch_edit(0, tasks, affected_files=affected)

        elif func_name == "run_shell_command":
            if isinstance(result, dict):
                stalled = result.get("stalled", False)
                success = result.get("success", False)
                output = result.get("stdout", result.get("output", result.get("logs", "")))
                job_id = result.get("job_id", "")

                if stalled:
                    cmd = func_args.get("command", "")
                    self.memory.record_shell(
                        0, f"{cmd} [STALLED → {job_id}]", output, success=False
                    )
                elif result.get("killed"):
                    self.memory.record_shell(
                        0, func_args.get("command", "") + " [KILLED]", output, success=False
                    )
                else:
                    self.memory.record_shell(0, func_args.get("command", ""), output, success=success)
            else:
                output = str(result) if result else ""
                self.memory.record_shell(0, func_args.get("command", ""), output, success=True)

    def run_testing_pipeline(self) -> Dict:
        """Run the planner in one continuous conversation until tests pass, it gives up, or max rounds."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._emit("step", "Starting planner-driven pipeline...")

        prompt = self._build_planner_prompt()
        messages = self.provider.create_initial_message(prompt)
        tool_calls_made = 0
        consecutive_empty = 0  # track consecutive rounds with no tool calls

        from ..utils.telemetry import TELEMETRY
        for round_num in range(1, self.max_rounds + 1):
            TELEMETRY.incr("planner_rounds")
            try:
                response = self.provider.call_model(messages, tools=self.tools)
            except Exception as e:
                self._emit("error", f"Round {round_num} LLM call failed: {e}")
                # Don't break — retry on next round with same messages
                continue

            function_calls = self.provider.extract_function_calls(response)

            if not function_calls:
                consecutive_empty += 1
                # Accumulate the empty response so the LLM sees it tried nothing
                self.provider.accumulate_messages(messages, response, [])
                if consecutive_empty >= 3:
                    TELEMETRY.incr("planner_stalled")
                    self._emit("warning", "Planner made no tool calls for 3 consecutive rounds, stopping.")
                    break
                continue

            consecutive_empty = 0

            # Group calls: exclusive tools run alone, others run in parallel
            groups = []
            current_parallel = []

            for fc in function_calls:
                if fc["name"] in self.EXCLUSIVE_TOOLS:
                    if current_parallel:
                        groups.append(("parallel", list(current_parallel)))
                        current_parallel = []
                    groups.append(("exclusive", [fc]))
                else:
                    current_parallel.append(fc)

            if current_parallel:
                groups.append(("parallel", list(current_parallel)))

            results_by_id = {}
            fc_index = {id(fc): i for i, fc in enumerate(function_calls)}
            gave_up = False

            for kind, group_fcs in groups:
                if kind == "exclusive":
                    fc = group_fcs[0]
                    func_name = fc["name"]
                    func_args = fc.get("args", {})

                    self._emit("tool_call", f"{func_name}({list(func_args.keys())})")
                    result = self.tool_handler.handle_function_call(func_name, func_args)
                    tool_calls_made += 1

                    if isinstance(result, dict) and result.get("gave_up"):
                        gave_up = True

                    self._record_tool_to_memory(func_name, func_args, result)

                    func_response = self.provider.create_function_response(
                        func_name, result, fc.get("id")
                    )
                    results_by_id[fc_index[id(fc)]] = func_response

                else:
                    # parallel group
                    if len(group_fcs) == 1:
                        fc = group_fcs[0]
                        func_name = fc["name"]
                        func_args = fc.get("args", {})

                        self._emit("tool_call", f"{func_name}({list(func_args.keys())})")
                        result = self.tool_handler.handle_function_call(func_name, func_args)
                        tool_calls_made += 1

                        if isinstance(result, dict) and result.get("gave_up"):
                            gave_up = True

                        self._record_tool_to_memory(func_name, func_args, result)

                        func_response = self.provider.create_function_response(
                            func_name, result, fc.get("id")
                        )
                        results_by_id[fc_index[id(fc)]] = func_response
                    else:
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
                                self._record_tool_to_memory(fc_done["name"], fc_done.get("args", {}), result)
                                func_response = self.provider.create_function_response(
                                    fc_done["name"], result, fc_done.get("id")
                                )
                                results_by_id[fc_index[id(fc_done)]] = func_response

            function_responses = [
                results_by_id[i] for i in range(len(function_calls))
            ]
            self.provider.accumulate_messages(messages, response, function_responses)

            if gave_up:
                self._emit("warning", "Planner gave up.")
                break

            self._sync_state()
            if self.state.tests_passed:
                # External oracle gate: author-supplied acceptance checks run
                # against the real project. Failures reject the completion and
                # re-enter the SAME conversation with the failure report, so
                # the planner keeps fixing with full context.
                oracle_feedback = self._run_oracle_gate()
                if oracle_feedback is not None:
                    self.tool_handler.tests_passed = False
                    self._sync_state()
                    messages.append(self.provider.create_initial_message(oracle_feedback)[0])
                    continue

                self._emit("success", "All tests passing")
                try:
                    self.memory.notify_success()
                except Exception:
                    pass
                return self._build_result("All tests passing", tool_calls_made)

        msg = (
            f"Pipeline ended after {tool_calls_made} tool calls: "
            f"Tests {'PASS' if self.state.tests_passed else 'FAIL'}"
        )
        self._emit("warning", msg)
        return self._build_result(msg, tool_calls_made)

    MAX_ORACLE_REJECTIONS = 3

    def _run_oracle_gate(self) -> Optional[str]:
        """Run public oracle checks after the planner claims completion.

        Returns None when the gate passes (no checks configured, all pass, or
        the rejection budget is exhausted — the run then completes on the
        pipeline's own criteria and the bench grades the miss). Returns the
        feedback message for the planner when checks fail within budget.
        """
        if not self.oracle_checks:
            return None
        from ..utils.oracle import run_checks, format_failures_for_agent
        from ..utils.telemetry import TELEMETRY

        results = run_checks(self.project_root, self.oracle_checks)
        n_pass = sum(1 for r in results if r.get("passed"))
        TELEMETRY.set_metric("oracle_public_pass", n_pass)
        TELEMETRY.set_metric("oracle_public_total", len(results))
        if n_pass == len(results):
            self._emit("success", f"Oracle checks: {n_pass}/{len(results)} passed")
            return None

        self._oracle_rejections = getattr(self, "_oracle_rejections", 0) + 1
        TELEMETRY.incr("oracle_rejections")
        if self._oracle_rejections > self.MAX_ORACLE_REJECTIONS:
            self._emit("warning",
                       f"Oracle checks still failing after {self.MAX_ORACLE_REJECTIONS} "
                       f"rejections ({n_pass}/{len(results)}) — accepting run as-is.")
            return None

        failures = format_failures_for_agent(results)
        self._emit("warning",
                   f"Oracle gate rejected completion ({n_pass}/{len(results)} passed) — "
                   f"rejection {self._oracle_rejections}/{self.MAX_ORACLE_REJECTIONS}")
        return (
            "Your completion was REJECTED: the project's tests pass, but external "
            "acceptance checks against the RUNNING project failed:\n\n"
            f"{failures}\n\n"
            "Fix the underlying behavior so these commands produce the expected "
            "results. Do NOT special-case the exact inputs shown — additional "
            "unrevealed checks verify the same behavior with different values, "
            "and hardcoded answers will fail them. When fixed, run the tests and "
            "call mark_complete again with runtime_verification."
        )

    def _build_result(self, message: str, tool_calls: int = 0) -> Dict:
        """Build the return dict from PipelineState — single source of truth."""
        # Kill any stalled background processes
        self.tool_handler.cleanup()

        try:
            self.memory.save()
        except Exception as e:
            self._emit("warning", f"Failed to save planner memory: {e}")

        return {
            "success": self.state.tests_passed,
            "tests_success": self.state.tests_passed,
            "gave_up": self.state.gave_up,
            "tool_calls": tool_calls,
            "message": message,
        }


def run_testing_pipeline(
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
    requirements_json: Optional[str] = None,
    oracle_checks: Optional[list] = None,
) -> Dict:
    pipeline = TestingPipeline(
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
        requirements_json=requirements_json,
        oracle_checks=oracle_checks,
    )
    return pipeline.run_testing_pipeline()