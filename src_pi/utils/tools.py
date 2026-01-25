import os
import json
from typing import Dict, Any


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
            except Exception as e:
                print(f"Unable to extract function args from: {function_call.args}, the error is {e}")
                # func_args = {}

    elif hasattr(function_call, 'function_call') and hasattr(function_call.function_call, 'args'):
        if isinstance(function_call.function_call.args, dict):
            func_args = function_call.function_call.args
        elif hasattr(function_call.function_call.args, '__dict__'):
            func_args = function_call.function_call.args.__dict__
        else:
            try:
                func_args = dict(function_call.function_call.args)
            except Exception as e:
                print(f"Unable to extract function args from: {function_call.args}, the error is {e}")
                # func_args = {}

    return func_args


def get_all_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_file_code",
                "description": "Get the code content of a file from the project. Use this to read any file you need to understand before making changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative path to the file from project root (e.g., 'src/main.py' or 'app/models.py')"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_files",
                "description": "Search for files in the project by name or pattern and return matches with paths and optional content previews.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Filename or substring to search for (e.g., 'config.py', 'ci.yml')."
                        },
                        "include_content": {
                            "type": "boolean",
                            "description": "If true, include a short preview of file content for each match (first 2000 chars)."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 50)."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "regenerate_file",
                "description": "Regenerate a file from the software blueprint. Use this when a file is missing or needs to be recreated based on the original specifications. Requires file path and context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative path to the file to regenerate (e.g., 'src/main.py', 'config/settings.py')"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context about why this file needs to be regenerated or what it should contain"
                        }
                    },
                    "required": ["file_path", "context"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_file_exists",
                "description": "Check if a file exists in the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative path to the file from project root (e.g., 'src/main.py')"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List directory contents (files and subdirectories).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "Relative path to the directory (optional, defaults to project root)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_directory",
                "description": "Create a directory structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "Relative path to the directory to create (e.g., 'src/utils')"
                        },
                        "create_parents": {
                            "type": "boolean",
                            "description": "If true, create parent directories if they don't exist (default: true)"
                        }
                    },
                    "required": ["directory_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": "Delete a file from the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative path to the file to delete (e.g., 'src/old_file.py')"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_file_code",
                "description": "Update a file with new code content. Use this to write fixed or new code to a file. The content will be automatically cleaned of markdown artifacts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative path to the file to update (e.g., 'src/main.py')"
                        },
                        "new_content": {
                            "type": "string",
                            "description": "The complete new code content for the file"
                        },
                        "change_description": {
                            "type": "string",
                            "description": "Brief description of what was changed"
                        }
                    },
                    "required": ["file_path", "new_content", "change_description"]
                }
            }
        }
    ]


class ToolHandler:
    def __init__(self, project_root: str, error_tracker=None, image_name: str = "project-test"):
        # from .helpers import clean_agent_output
        self.project_root = project_root
        self.error_tracker = error_tracker
        self.image_name = image_name

    def handle_function_call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if function_name == "get_file_code":
            return self._get_file_code(args["file_path"])
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
        else:
            return {"error": f"Unknown function: {function_name}"}

    def _get_file_code(self, file_path: str) -> Dict[str, Any]:
        if not file_path:
            return {"error": "file_path is required"}

        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return {"error": f"File not found: {file_path}"}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "success": True,
                "file_path": file_path,
                "content": content
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

    def _find_files(self, query: str, include_content: bool = False, max_results: int = 50) -> Dict[str, Any]:
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