import os
import json
import subprocess
from typing import Dict, Any, Optional


class ToolHandler:
    def __init__(self, project_root: str, error_tracker=None, image_name: str = "project-test",
                 dependency_analyzer=None, tool_log_path: Optional[str] = None,
                 agent_name: Optional[str] = None, thread_memory=None,
                 docker_executor=None):
        from .tool_call_log import ToolCallLogger
        self.project_root = project_root
        self.error_tracker = error_tracker
        self.image_name = image_name
        self.dependency_analyzer = dependency_analyzer
        self.agent_name = agent_name
        self.thread_memory = thread_memory
        self.tool_call_logger = ToolCallLogger(tool_log_path) if tool_log_path else None
        self.docker_executor = docker_executor

    def handle_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self._log_tool_call(function_name, args)
        print(f"[tool_call] {function_name} args={list(args.keys())}")
        result = self._execute_tool(function_name, args)
        self._log_to_thread_memory(function_name, args, result)
        self._print_tool_result(function_name, result)
        return result

    def _execute_tool(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if function_name == "get_file_code":
            return self._get_file_code(
                args.get("file_path"),
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
                timeout_sec=int(args.get("timeout_sec", 5)) if args.get("timeout_sec") is not None else 5
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
        elif function_name == "docker_build":
            return self._docker_build(command=args.get("command", ""))
        elif function_name == "docker_run":
            return self._docker_run(command=args.get("command", ""))
        else:
            return {"error": f"Unknown function: {function_name}"}

    def _docker_build(self, command: str = "") -> Dict[str, Any]:
        if not self.docker_executor:
            return {"error": "Docker executor not available"}
        return self.docker_executor.build(command=command)

    def _docker_run(self, command: str = "") -> Dict[str, Any]:
        if not self.docker_executor:
            return {"error": "Docker executor not available"}
        if not command:
            return {"error": "command is required"}
        return self.docker_executor.run(command=command)

    def _log_tool_call(self, function_name: str, args: Dict[str, Any]) -> None:
        if not self.tool_call_logger:
            return
        try:
            self.tool_call_logger.log(self.agent_name, function_name, args)
        except Exception:
            pass

    def _log_to_thread_memory(self, function_name: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        if not self.thread_memory:
            return
        try:
            success = result.get("success", True) if isinstance(result, dict) else True
            if isinstance(result, dict) and "error" in result:
                success = False
            self.thread_memory.add_tool_call(
                agent=self.agent_name or "unknown",
                tool_name=function_name,
                arguments=args,
                result=result,
                success=success
            )
        except Exception:
            pass

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

    def _get_file_code(self, file_path: str, start_line: int = None, end_line: int = None) -> Dict[str, Any]:
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

    def _get_error_history(self, error_id: str = None, limit: int = 20, offset: int = 0, include_logs: bool = False) -> Dict[str, Any]:
        if not self.error_tracker:
            return {"error": "No error tracker available"}
        return self.error_tracker.get_error_history(error_id=error_id, limit=limit, offset=offset, include_logs=include_logs)

    def _get_action_history(self, limit: int = 20, offset: int = 0, task_id: str = None) -> Dict[str, Any]:
        if not self.error_tracker:
            return {"error": "No error tracker available"}
        return self.error_tracker.get_action_history(limit=limit, offset=offset, task_id=task_id)

    def _log_action(self, task_id: str, action_type: str, message: str) -> Dict[str, Any]:
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
                "old_content": old_content,
                "new_content": new_content
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

    def _run_shell_command(self, command: str, timeout_sec: int = 30) -> Dict[str, Any]:
        if not command or not isinstance(command, str):
            return {"error": "command is required"}

        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                text=True
            )
            return {
                "success": True,
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout_sec}s"}
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

