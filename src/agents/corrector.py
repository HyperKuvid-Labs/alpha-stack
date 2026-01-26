import os
from typing import Dict, Optional
from ..utils.helpers import (
    build_project_structure_tree,
    get_language_from_extension, extract_code_from_response
)
from ..utils.inference import InferenceManager
from ..utils.tools import extract_function_args


class CorrectionAgent:
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
    
    def fix_error(self, error_info: Dict[str, str]) -> bool:
        filepath = error_info.get("filepath", "")
        error = error_info.get("error", "")
        solution = error_info.get("solution", "")
        actions = error_info.get("action", [])
        
        if not solution and actions:
            solution = " ".join(actions)
        
        if filepath and not os.path.isabs(filepath):
            file_path = os.path.join(self.project_root, filepath)
        else:
            file_path = filepath
        
        try:
            file_content = ""
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            
            project_structure_tree = self._get_project_structure_tree()
            file_rel_path = os.path.relpath(file_path, self.project_root) if file_path else filepath
            
            change_log = self.error_tracker.get_change_summary()
            
            prompt = self.pm.render("common_error_correction.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                file_rel_path=file_rel_path,
                error=error,
                solution=solution,
                actions=actions,
                file_content=file_content,
                change_log=change_log
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
                        
                        if func_name == "update_file_code" and result.get("success"):
                            updated_file_path = result.get("file_path") or func_args.get("file_path", "")
                            if updated_file_path and not os.path.isabs(updated_file_path):
                                full_file_path = os.path.join(self.project_root, updated_file_path)
                            else:
                                full_file_path = updated_file_path or file_path
                            
                            self.error_tracker.log_change(
                                file_path=full_file_path,
                                change_description=func_args.get("change_description", f"Fixed error: {error[:100]}"),
                                error=error,
                                actions=actions,
                                before_content=result.get("old_content"),
                                after_content=result.get("new_content")
                            )
                            
                            self.invalidate_cache()
                            return True
                        
                        func_response = self.provider.create_function_response(
                            func_name, result, fc.get("id")
                        )
                        function_responses.append(func_response)
                    
                    update_file_called = any(fc["name"] == "update_file_code" for fc in function_calls)
                    if function_responses and not update_file_called:
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
                
                if response_text:
                    language = get_language_from_extension(file_path)
                    extracted_code = extract_code_from_response(response_text, language)
                    
                    if extracted_code:
                        result = self.tool_handler.handle_function_call(
                            "update_file_code",
                            {
                                "file_path": file_rel_path,
                                "new_content": extracted_code,
                                "change_description": f"Fixed error: {error[:100]}"
                            }
                        )
                        
                        if result.get("success"):
                            self.error_tracker.log_change(
                                file_path=file_path,
                                change_description=f"Fixed error: {error[:100]}",
                                error=error,
                                actions=actions,
                                before_content=result.get("old_content"),
                                after_content=result.get("new_content")
                            )
                            self.invalidate_cache()
                            return True
                    
            except Exception:
                pass
            
            return False
            
        except Exception:
            return False

