import os
from typing import Dict, Optional, Any
from ..utils.helpers import build_project_structure_tree
from ..utils.inference import InferenceManager


class ExecutorAgent:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 pm, error_tracker, tool_handler, provider_name: Optional[str] = None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm
        self.error_tracker = error_tracker
        self.tool_handler = tool_handler
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
    
    def execute_task(self, task: Dict[str, str]) -> Dict[str, Any]:
        changed_files = []
        task_id = task.get("task_id")
        try:
            project_structure_tree = self._get_project_structure_tree()
            change_log = self.error_tracker.get_change_summary()
            
            prompt = self.pm.render("executor_task_execution.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                task=task,
                change_log=change_log
            )
            
            messages = [{"role": "user", "content": prompt}]
            response = self.provider.call_model(messages, tools=self.tools)
            
            function_calls = self.provider.extract_function_calls(response)
            if function_calls:
                function_responses = []
                for fc in function_calls:
                    func_name = fc["name"]
                    func_args = fc.get("args", {})
                    result = self.tool_handler.handle_function_call(func_name, func_args)
                    
                    if func_name == "update_file_code" and result.get("success"):
                        updated_file_path = result.get("file_path") or func_args.get("file_path", "")
                        if updated_file_path and not os.path.isabs(updated_file_path):
                            full_file_path = os.path.join(self.project_root, updated_file_path)
                        else:
                            full_file_path = updated_file_path
                        
                        changed_files.append(full_file_path)
                        self.error_tracker.log_change(
                            file_path=full_file_path,
                            change_description=func_args.get("change_description", "Applied executor change"),
                            actions=task.get("steps", []),
                            before_content=result.get("old_content"),
                            after_content=result.get("new_content")
                        )
                        self.error_tracker.log_action(
                            task_id=task_id,
                            action_type="edit",
                            message=f"Updated {updated_file_path}"
                        )
                        self.invalidate_cache()
                    
                    func_response = self.provider.create_function_response(
                        func_name, result, fc.get("id")
                    )
                    function_responses.append(func_response)
                
                if function_responses:
                    if self.provider_name == "google":
                        from google.genai import types
                        tool_content = types.Content(role='tool', parts=function_responses)
                        final_messages = [
                            types.Content(role='user', parts=[types.Part.from_text(text=prompt)]),
                            tool_content
                        ]
                    else:
                        final_messages = messages + function_responses
                    
                    final_response = self.provider.call_model(final_messages, tools=self.tools)
                    response = final_response
            
            response_text = self.provider.extract_text(response)
            if response_text and changed_files:
                self.error_tracker.log_action(
                    task_id=task_id,
                    action_type="note",
                    message="Executor completed task with file edits"
                )
            
            return {"success": True, "changed_files": changed_files}
        except Exception as e:
            self.error_tracker.log_action(
                task_id=task_id,
                action_type="error",
                message=f"Executor failed: {str(e)}"
            )
            return {"success": False, "changed_files": changed_files, "error": str(e)}


# Backwards compatibility alias
class CorrectionAgent(ExecutorAgent):
    pass

