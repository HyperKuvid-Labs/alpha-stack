import json
import re
from typing import Dict, List, Optional
from ..utils.helpers import build_project_structure_tree
from ..utils.inference import InferenceManager


class PlanningAgent:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 pm, error_tracker, tool_handler, command_log_manager=None,
                 provider_name: Optional[str] = None, thread_memory=None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm
        self.error_tracker = error_tracker
        self.tool_handler = tool_handler
        self.command_log_manager = command_log_manager
        self.thread_memory = thread_memory  # Thread memory for iteration context
        self._cached_project_structure_tree = None
        # Initialize provider
        self.provider_name = provider_name or InferenceManager.get_default_provider()
        self.provider = InferenceManager.create_provider(self.provider_name)
        self.tool_definitions = InferenceManager.get_tool_definitions()
        self.tools = self.provider.format_tools(self.tool_definitions)

    def _get_project_structure_tree(self) -> str:
        if self._cached_project_structure_tree is None:
            self._cached_project_structure_tree = build_project_structure_tree(self.project_root)
        return self._cached_project_structure_tree

    def invalidate_cache(self):
        self._cached_project_structure_tree = None

    def plan_tasks(self, errors: List[Dict] = None, error_ids: List[str] = None,
                   error_type: str = "dependency") -> List[Dict[str, str]]:
        max_tool_rounds = 5  # Prevent infinite loops

        try:
            project_structure_tree = self._get_project_structure_tree()

            # Get thread memory context if available
            iteration_history = ""
            if self.thread_memory:
                iteration_history = self.thread_memory.get_context_for_prompt(max_recent=3)

            prompt = self.pm.render("planner_task_planning.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                errors=errors or [],  # Pass actual errors to prompt
                error_type=error_type,
                error_ids=error_ids or [],
                iteration_history=iteration_history  # Thread memory context
            )

            # Initialize message history using provider abstraction
            messages = self.provider.create_initial_message(prompt)

            try:
                # Agentic loop - keep processing tool calls until model stops or we hit limit
                response = None
                for round_num in range(max_tool_rounds):
                    response = self.provider.call_model(messages, tools=self.tools)
                    function_calls = self.provider.extract_function_calls(response)

                    if not function_calls:
                        # No more tool calls - model is ready to output tasks
                        break

                    function_responses = []
                    for fc in function_calls:
                        func_name = fc["name"]
                        func_args = fc.get("args", {})
                        self.tool_handler.agent_name = "planner"
                        result = self.tool_handler.handle_function_call(func_name, func_args)

                        func_response = self.provider.create_function_response(
                            func_name, result, fc.get("id")
                        )
                        function_responses.append(func_response)

                    # CRITICAL: Accumulate messages using provider abstraction
                    self.provider.accumulate_messages(messages, response, function_responses)

                if response is None:
                    raise Exception("No response from model")

                response_text = self.provider.extract_text(response)

                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    tasks = json.loads(json_match.group())
                else:
                    tasks = json.loads(response_text)

                if isinstance(tasks, dict):
                    tasks = [tasks]

                tasks = sorted(tasks, key=lambda x: x.get('priority', 999))
                return tasks

            except Exception:
                # Fallback: try without tools
                fallback_messages = [{"role": "user", "content": prompt}]
                response = self.provider.call_model(fallback_messages)
                response_text = self.provider.extract_text(response)

                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    tasks = json.loads(json_match.group())
                else:
                    tasks = json.loads(response_text)

                if isinstance(tasks, dict):
                    tasks = [tasks]

                tasks = sorted(tasks, key=lambda x: x.get('priority', 999))
                return tasks

        except Exception:
            tasks = []
            for e in (errors or []):
                if isinstance(e, dict):
                    tasks.append({
                        "error": e.get("error", ""),
                        "title": "Fix error",
                        "steps": ["Investigate error and apply minimal fix"],
                        "files": [e.get("file", "")] if e.get("file") else [],
                        "priority": 1
                    })
            return tasks

    # Backwards compatibility
    def plan_fixes(self, errors: List[Dict] = None, logs: str = None,
                   error_type: str = "dependency") -> List[Dict[str, str]]:
        return self.plan_tasks(errors=errors, error_ids=None, error_type=error_type)
