import os
import json
import re
from typing import Dict, List, Optional
from google.genai import types
from ..utils.helpers import retry_api_call, build_project_structure_tree
from src.utils.inference import InferenceManager
from ..utils.tools import get_all_tools, extract_function_args


class PlanningAgent:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 pm, error_tracker, tool_handler, command_log_manager=None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm
        self.error_tracker = error_tracker
        self.tool_handler = tool_handler
        self.command_log_manager = command_log_manager
        self._cached_project_structure_tree = None

    def _get_project_structure_tree(self) -> str:
        if self._cached_project_structure_tree is None:
            self._cached_project_structure_tree = build_project_structure_tree(self.project_root)
        return self._cached_project_structure_tree

    def invalidate_cache(self):
        self._cached_project_structure_tree = None

    def plan_fixes(self, errors: List[Dict] = None, logs: str = None,
                   error_type: str = "dependency") -> List[Dict[str, str]]:
        try:
            project_structure_tree = self._get_project_structure_tree()

            errors_list = []
            if errors:
                for e in errors:
                    if isinstance(e, dict):
                        errors_list.append(e)
                    else:
                        errors_list.append({
                            "error": getattr(e, 'message', str(e)),
                            "file": os.path.relpath(getattr(e, 'file_path', ''), self.project_root) if getattr(e, 'file_path', None) else "",
                            "line_number": getattr(e, 'line_number', None),
                            "error_type": getattr(e, 'error_type', 'unknown')
                        })

            change_log = self.error_tracker.get_change_summary()

            command_execution_history = ""
            if self.command_log_manager:
                command_execution_history = self.command_log_manager.get_formatted_history_for_planning(max_tokens=10000)

            prompt = self.pm.render("common_error_planning.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                errors=errors_list,
                error_type=error_type,
                logs=logs[-5000:] if logs else "",
                change_log=change_log,
                command_execution_history=command_execution_history
            )

            provider = InferenceManager.get_active_provider()
            tools = get_all_tools()

            try:
                messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt

                response = provider.call_model(messages, tools=tools, tool_choice="auto")

                response_message = response.choices[0].message

                if response_message.tool_calls:
                    messages.append(response_message)

                    for tool_call in response_message.tool_calls:
                        func_name = tool_call.function.name
                        func_args = extract_function_args(tool_call)

                        result = self.tool_handler.handle_function_call(func_name, func_args)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": func_name,
                            "content": json.dumps(result)
                        })

                    final_response = provider.call_model(messages, tools=tools, tool_choice="none")
                    response_text = provider.extract_text(final_response).strip()

                else:
                    response_text = response_message.content.strip()

                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    fix_plan = json.loads(json_match.group())
                else:
                    fix_plan = json.loads(response_text)

                if isinstance(fix_plan, dict):
                    fix_plan = [fix_plan]

                fix_plan = sorted(fix_plan, key=lambda x: x.get('priority', 999))
                return fix_plan

            except Exception as e:
                messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt

                response = provider.call_model(messages)
                response_text = provider.extract_text(response).strip()

                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    fix_plan = json.loads(json_match.group())
                else:
                    fix_plan = json.loads(response_text)

                if isinstance(fix_plan, dict):
                    fix_plan = [fix_plan]

                fix_plan = sorted(fix_plan, key=lambda x: x.get('priority', 999))
                return fix_plan

        except Exception:
            fix_plan = []
            for e in (errors or []):
                if isinstance(e, dict):
                    fix_plan.append({
                        "error": e.get("error", ""),
                        "action": ["Fix error"],
                        "filepath": e.get("file", ""),
                        "priority": 1
                    })
            return fix_plan

