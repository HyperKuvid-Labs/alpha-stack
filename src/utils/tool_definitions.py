"""Tool definitions in JSON Schema format (provider-agnostic)"""
from typing import List, Dict, Any

def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions in JSON Schema format"""
    return [
        {
            "name": "get_file_code",
            "description": "Get the code content of a file from the project. Use this to read any file you need to understand before making changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from project root (e.g., 'src/main.py' or 'app/models.py')"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional start line number (1-based). If provided with end_line, only return that slice."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional end line number (1-based). If provided with start_line, only return that slice."
                    }
                },
                "required": ["file_path"]
            }
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        ,
        {
            "name": "get_error_history",
            "description": "Fetch error history with optional paging or a specific error ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "error_id": {
                        "type": "string",
                        "description": "Optional error ID to fetch a specific error entry"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of entries to return (default 20)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset into error history (default 0)"
                    },
                    "include_logs": {
                        "type": "boolean",
                        "description": "If true, include error logs/details in the response"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_action_history",
            "description": "Fetch action history with optional paging.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of entries to return (default 20)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset into action history (default 0)"
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Optional task id to filter action history"
                    }
                },
                "required": []
            }
        },
        {
            "name": "log_action",
            "description": "Log an action taken by the executor or planner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID associated with the action"
                    },
                    "action_type": {
                        "type": "string",
                        "description": "Type of action (e.g., edit, analysis, command)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Short description of the action"
                    }
                },
                "required": ["action_type", "message"]
            }
        },
        {
            "name": "run_shell_command",
            "description": "Run a read-only shell command for context. No project execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run (read-only)."
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 5)"
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "get_file_dependencies",
            "description": "Get internal dependencies for a file (paths it depends on).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "get_file_dependents",
            "description": "Get dependents of a file (files that import it).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file"
                    }
                },
                "required": ["file_path"]
            }
        }
    ]

