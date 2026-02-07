import os
import json
import shlex
import subprocess
from typing import Dict, Any, Optional
from google.genai import types

def _get_skip_dirs():
    from .helpers import SKIP_DIRS
    return SKIP_DIRS


def extract_function_args(function_call) -> Dict[str, Any]:
    func_args = {}

    if hasattr(function_call, 'args'):
        if isinstance(function_call.args, dict):
            func_args = function_call.args
        elif hasattr(function_call.args, '__dict__'):
            func_args = function_call.args.__dict__
        else:
            try:
                func_args = dict(function_call.args)
            except (TypeError, ValueError):
                func_args = {}

    elif hasattr(function_call, 'function_call') and hasattr(function_call.function_call, 'args'):
        if isinstance(function_call.function_call.args, dict):
            func_args = function_call.function_call.args
        elif hasattr(function_call.function_call.args, '__dict__'):
            func_args = function_call.function_call.args.__dict__
        else:
            try:
                func_args = dict(function_call.function_call.args)
            except (TypeError, ValueError):
                func_args = {}

    return func_args


def get_all_tools() -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_file_code",
                description="Get the code content of a file from the project. Use this to read any file you need to understand before making changes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the file from project root (e.g., 'src/main.py' or 'app/models.py')"
                        )
                    },
                    required=["file_path"]
                )
            ),
            types.FunctionDeclaration(
                name="find_files",
                description="Search for files in the project by name or pattern and return matches with paths and optional content previews.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Filename or substring to search for (e.g., 'config.py', 'ci.yml')."
                        ),
                        "include_content": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="If true, include a short preview of file content for each match (first 2000 chars)."
                        ),
                        "max_results": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum number of results to return (default 50)."
                        )
                    },
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="regenerate_file",
                description="Regenerate a file from the software blueprint. Use this when a file is missing or needs to be recreated based on the original specifications. Requires file path and context.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the file to regenerate (e.g., 'src/main.py', 'config/settings.py')"
                        ),
                        "context": types.Schema(
                            type=types.Type.STRING,
                            description="Additional context about why this file needs to be regenerated or what it should contain"
                        )
                    },
                    required=["file_path", "context"]
                )
            ),
            types.FunctionDeclaration(
                name="check_file_exists",
                description="Check if a file exists in the project.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the file from project root (e.g., 'src/main.py')"
                        )
                    },
                    required=["file_path"]
                )
            ),
            types.FunctionDeclaration(
                name="list_directory",
                description="List directory contents (files and subdirectories).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "directory_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the directory (optional, defaults to project root)"
                        )
                    },
                    required=[]
                )
            ),
            types.FunctionDeclaration(
                name="create_directory",
                description="Create a directory structure.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "directory_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the directory to create (e.g., 'src/utils')"
                        ),
                        "create_parents": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="If true, create parent directories if they don't exist (default: true)"
                        )
                    },
                    required=["directory_path"]
                )
            ),
            types.FunctionDeclaration(
                name="delete_file",
                description="Delete a file from the project.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the file to delete (e.g., 'src/old_file.py')"
                        )
                    },
                    required=["file_path"]
                )
            ),
            types.FunctionDeclaration(
                name="update_file_code",
                description="Update a file with new code content. Use this to write fixed or new code to a file. The content will be automatically cleaned of markdown artifacts.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Relative path to the file to update (e.g., 'src/main.py')"
                        ),
                        "new_content": types.Schema(
                            type=types.Type.STRING,
                            description="The complete new code content for the file"
                        ),
                        "change_description": types.Schema(
                            type=types.Type.STRING,
                            description="Brief description of what was changed"
                        )
                    },
                    required=["file_path", "new_content", "change_description"]
                )
            )
        ]
    )


class ToolHandler:
    def __init__(self, project_root: str, error_tracker=None, image_name: str = "project-test",
                 dependency_analyzer=None, tool_log_path: Optional[str] = None,
                 agent_name: Optional[str] = None, thread_memory=None):
        from .helpers import clean_agent_output
        from .tool_call_log import ToolCallLogger
        self.project_root = project_root
        self.error_tracker = error_tracker
        self.image_name = image_name
        self.dependency_analyzer = dependency_analyzer
        self.agent_name = agent_name
        self.thread_memory = thread_memory  # Thread memory for tracking tool calls
        self.tool_call_logger = ToolCallLogger(tool_log_path) if tool_log_path else None

    def set_thread_memory(self, thread_memory) -> None:
        """Set or update thread memory reference"""
        self.thread_memory = thread_memory

    def handle_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self._log_tool_call(function_name, args)
        print(f"[tool_call] {function_name} args={list(args.keys())}")

        # Execute the tool and get result
        result = self._execute_tool(function_name, args)

        # Log to thread memory if available
        self._log_to_thread_memory(function_name, args, result)

        self._print_tool_result(function_name, result)
        return result

    def _execute_tool(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result"""
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
        elif function_name == "find_files":
            return self._find_files(
                query=args.get("query", ""),
                include_content=bool(args.get("include_content", False)),
                max_results=int(args.get("max_results", 50))
            )
        elif function_name == "regenerate_file":
            return self._regenerate_file(
                file_path=args.get("file_path", ""),
                context=args.get("context", "")
            )
        elif function_name == "check_file_exists":
            return self._check_file_exists(args.get("file_path", ""))
        elif function_name == "list_directory":
            return self._list_directory(args.get("directory_path", ""))
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
        elif function_name == "get_file_dependencies":
            return self._get_file_dependencies(args.get("file_path", ""))
        elif function_name == "get_file_dependents":
            return self._get_file_dependents(args.get("file_path", ""))
        else:
            return {"error": f"Unknown function: {function_name}"}

    def _log_tool_call(self, function_name: str, args: Dict[str, Any]) -> None:
        if not self.tool_call_logger:
            return
        try:
            self.tool_call_logger.log(self.agent_name, function_name, args)
        except Exception:
            pass

    def _log_to_thread_memory(self, function_name: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Log tool call to thread memory for iteration context"""
        if not self.thread_memory:
            return
        try:
            # Determine success based on result
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
            pass  # Don't let logging failures affect tool execution

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
        print("log_change")
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

    def _find_files(self, query: str, include_content: bool = False, max_results: int = 50) -> Dict[str, Any]:
        print("find_files")
        if not query:
            return {"error": "query is required"}
        matches = []
        try:
            skip_dirs = _get_skip_dirs()
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
                for fname in files:
                    if query.lower() in fname.lower():
                        full_path = os.path.join(root, fname)
                        rel_path = os.path.relpath(full_path, self.project_root)
                        item = {"path": rel_path, "size_bytes": os.path.getsize(full_path)}
                        if include_content:
                            try:
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    item["content_preview"] = f.read(2000)
                            except Exception:
                                item["content_preview"] = ""
                        matches.append(item)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
            return {"success": True, "query": query, "results": matches}
        except Exception as e:
            return {"error": f"Error searching files: {str(e)}"}

    def _regenerate_file(self, file_path: str, context: str) -> Dict[str, Any]:
        print("regenerate_file")
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

    def _check_file_exists(self, file_path: str) -> Dict[str, Any]:
        print("check_file_exists")
        if not file_path:
            return {"error": "file_path is required"}

        full_path = os.path.join(self.project_root, file_path)
        exists = os.path.exists(full_path) and os.path.isfile(full_path)

        return {
            "success": True,
            "exists": exists,
            "file_path": file_path
        }

    def _list_directory(self, directory_path: str = "") -> Dict[str, Any]:
        print("list_directory")
        if directory_path:
            full_path = os.path.join(self.project_root, directory_path)
        else:
            full_path = self.project_root

        if not os.path.exists(full_path):
            return {"error": f"Directory not found: {directory_path or 'project root'}"}

        if not os.path.isdir(full_path):
            return {"error": f"Path is not a directory: {directory_path or 'project root'}"}

        try:
            entries = os.listdir(full_path)
            files = []
            directories = []

            for entry in entries:
                if entry.startswith('.') and entry not in {'.', '..'}:
                    continue

                entry_path = os.path.join(full_path, entry)
                rel_path = os.path.relpath(entry_path, self.project_root)

                if os.path.isdir(entry_path):
                    directories.append(rel_path)
                else:
                    files.append(rel_path)

            return {
                "success": True,
                "directory_path": directory_path or ".",
                "files": sorted(files),
                "directories": sorted(directories)
            }
        except Exception as e:
            return {"error": f"Error listing directory: {str(e)}"}

    def _create_directory(self, directory_path: str, create_parents: bool = True) -> Dict[str, Any]:
        print("create_directory")
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
        print("delete_file")
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

    def _run_shell_command(self, command: str, timeout_sec: int = 5) -> Dict[str, Any]:
        if not command or not isinstance(command, str):
            return {"error": "command is required"}

        blocked_tokens = {
            "python", "pip", "npm", "yarn", "pnpm", "bun", "go", "cargo",
            "docker", "podman", "pytest", "make", "gradle", "mvn", "node"
        }
        safe_prefixes = {
            "ls", "cat", "head", "tail", "sed", "grep", "rg", "find",
            "pwd", "wc", "stat", "du", "sort", "uniq", "cut"
        }

        try:
            parts = shlex.split(command)
        except ValueError:
            return {"error": "Invalid command string"}

        if not parts:
            return {"error": "Empty command"}

        if parts[0] not in safe_prefixes:
            return {"error": "Command not allowed"}

        if any(token in blocked_tokens for token in parts):
            return {"error": "Command contains blocked tokens"}

        try:
            completed = subprocess.run(
                parts,
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
            return {"error": "Command timed out"}
        except Exception as e:
            return {"error": f"Command failed: {str(e)}"}

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

