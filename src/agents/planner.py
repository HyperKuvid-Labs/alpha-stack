import os
import json
import re
from typing import Dict, List, Optional
from ..utils.helpers import build_project_structure_tree
from ..utils.inference import InferenceManager
from ..utils.tools import extract_function_args


class PlanningAgent:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 pm, error_tracker, tool_handler, command_log_manager=None,
                 provider_name: Optional[str] = None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm
        self.error_tracker = error_tracker
        self.tool_handler = tool_handler
        self.command_log_manager = command_log_manager
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
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response = self.provider.call_model(messages, tools=self.tools)
                
                function_calls = self.provider.extract_function_calls(response)
                
                if function_calls:
                    function_responses = []
                    
                    for fc in function_calls:
                        func_name = fc["name"]
                        func_args = fc.get("args", {})
                        
                        result = self.tool_handler.handle_function_call(func_name, func_args)
                        
                        func_response = self.provider.create_function_response(
                            func_name, result, fc.get("id")
                        )
                        function_responses.append(func_response)
                    
                    if function_responses:
                        # Send function responses back to model
                        if self.provider_name == "google":
                            from google.genai import types
                            tool_content = types.Content(role='tool', parts=function_responses)
                            final_messages = [
                                types.Content(role='user', parts=[types.Part.from_text(text=prompt)]),
                                tool_content
                            ]
                        else:  # openrouter
                            final_messages = messages + function_responses
                        
                        final_response = self.provider.call_model(final_messages, tools=self.tools)
                        response = final_response
                
                response_text = self.provider.extract_text(response)
                
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
                # Fallback: try without tools
                response = self.provider.call_model(messages)
                response_text = self.provider.extract_text(response)
                
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

