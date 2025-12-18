import os
from typing import Dict
from google.genai import types
from ..utils.helpers import (
    get_client, retry_api_call, build_project_structure_tree,
    get_language_from_extension, extract_code_from_response, is_valid_code,
    MODEL_NAME_FLASH
)
from ..utils.tools import get_all_tools, extract_function_args


class CorrectionAgent:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 pm, error_tracker, tool_handler):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm
        self.error_tracker = error_tracker
        self.tool_handler = tool_handler
        self._cached_project_structure_tree = None
    
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
            
            client = get_client()
            tools = get_all_tools()
            
            try:
                response = retry_api_call(
                    client.models.generate_content,
                    model=MODEL_NAME_FLASH,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[tools],
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )
                
                if hasattr(response, 'function_calls') and response.function_calls:
                    function_response_parts = []
                    
                    for function_call in response.function_calls:
                        func_name = function_call.name
                        func_args = extract_function_args(function_call)
                        
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
                        
                        function_response_part = types.Part.from_function_response(
                            name=func_name,
                            response=result
                        )
                        function_response_parts.append(function_response_part)
                    
                    update_file_called = any(fc.name == "update_file_code" for fc in response.function_calls)
                    if function_response_parts and not update_file_called:
                        function_response_content = types.Content(
                            role='tool',
                            parts=function_response_parts
                        )
                        final_response = retry_api_call(
                            client.models.generate_content,
                            model=MODEL_NAME_FLASH,
                            contents=[
                                types.Content(role='user', parts=[types.Part.from_text(text=prompt)]),
                                function_response_content
                            ]
                        )
                        
                        if hasattr(final_response, 'text') and final_response.text:
                            response = final_response
                
                if hasattr(response, 'text') and response.text:
                    language = get_language_from_extension(file_path)
                    extracted_code = extract_code_from_response(response.text, language)
                    
                    if extracted_code and is_valid_code(extracted_code, language):
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

