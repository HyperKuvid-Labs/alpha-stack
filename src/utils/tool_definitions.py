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
                        "description": "Relative path to the file from project root (e.g., 'src/main.py' or 'app/models.py')",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional start line number (1-based). If provided with end_line, only return that slice.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional end line number (1-based). If provided with start_line, only return that slice.",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "update_file_code",
            "description": "Update a file with new code content. Use this to write fixed or new code to a file. The content will be automatically cleaned of markdown artifacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to update (e.g., 'src/main.py')",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The complete new code content for the file",
                    },
                    "change_description": {
                        "type": "string",
                        "description": "Brief description of what was changed",
                    },
                },
                "required": ["file_path", "new_content", "change_description"],
            },
        },
        {
            "name": "create_directory",
            "description": "Create a directory structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Relative path to the directory to create (e.g., 'src/utils')",
                    },
                    "create_parents": {
                        "type": "boolean",
                        "description": "If true, create parent directories if they don't exist (default: true)",
                    },
                },
                "required": ["directory_path"],
            },
        },
        {
            "name": "delete_file",
            "description": "Delete a file from the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to delete (e.g., 'src/old_file.py')",
                    }
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "regenerate_file",
            "description": "Regenerate a file from the software blueprint. Use this when a file is missing or needs to be recreated based on the original specifications. Requires file path and context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to regenerate (e.g., 'src/main.py', 'config/settings.py')",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about why this file needs to be regenerated or what it should contain",
                    },
                },
                "required": ["file_path", "context"],
            },
        },
        {
            "name": "get_error_history",
            "description": "Fetch error history with optional paging or a specific error ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "error_id": {
                        "type": "string",
                        "description": "Optional error ID to fetch a specific error entry",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of entries to return (default 20)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset into error history (default 0)",
                    },
                    "include_logs": {
                        "type": "boolean",
                        "description": "If true, include error logs/details in the response",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_action_history",
            "description": "Fetch action history with optional paging.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of entries to return (default 20)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset into action history (default 0)",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Optional task id to filter action history",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "log_action",
            "description": "Log an action taken by the executor or planner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID associated with the action",
                    },
                    "action_type": {
                        "type": "string",
                        "description": "Type of action (e.g., edit, analysis, command)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Short description of the action",
                    },
                },
                "required": ["action_type", "message"],
            },
        },
        {
            "name": "run_shell_command",
            "description": "Run a read-only shell command for context. No project execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run (read-only).",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 5)",
                    },
                },
                "required": ["command"],
            },
        },
        {
            "name": "patch_file",
            "description": "Apply a surgical patch to a file without rewriting the whole thing. Supports full_rewrite, delete_lines, replace_lines, and insert_after_line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to patch (e.g., 'src/main.py')",
                    },
                    "fix_type": {
                        "type": "string",
                        "description": "Patch mode: 'full_rewrite' replaces entire file, 'delete_lines' removes a line range, 'replace_lines' swaps a line range with new_content, 'insert_after_line' inserts new_content after the given line.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of why this patch is being applied",
                    },
                    "line_start": {
                        "type": "integer",
                        "description": "1-based start line for delete_lines, replace_lines, or insert_after_line",
                    },
                    "line_end": {
                        "type": "integer",
                        "description": "1-based end line (inclusive) for delete_lines or replace_lines. Defaults to line_start if omitted.",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Replacement or insertion content. Required for full_rewrite, replace_lines, and insert_after_line.",
                    },
                },
                "required": ["file_path", "fix_type", "description"],
            },
        },
        {
            "name": "get_file_dependencies",
            "description": "Get internal dependencies for a file (paths it depends on).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    }
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_file_dependents",
            "description": "Get dependents of a file (files that import it).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    }
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "docker_build",
            "description": "Build the Docker image. You provide the full docker build command. If omitted, defaults to 'docker build --progress=plain -t <image_name> .'",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Full docker build command (e.g., 'docker build --progress=plain -t myapp .'). Leave empty to use the default.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "docker_run",
            "description": "Run a command in a Docker container. You provide the FULL 'docker run ...' command including all flags, volume mounts, image name, and the command to execute. Only commands containing test runners (pytest, npm test, etc.) update the pipeline's test_success state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Full docker run command (e.g., 'docker run --rm -v /app:/app myimage pytest -v').",
                    }
                },
                "required": ["command"],
            },
        },
        {
            "name": "batch_edit_files",
            "description": (
                "Delegate multiple file-editing tasks to parallel corrector mini-agents. "
                "Each task targets ONE file and spawns an independent LLM agent that reads "
                "the file, applies the requested changes, and verifies the result. "
                "Use this when you need to edit several files at once (e.g., fixing the same "
                "pattern across multiple files, or making coordinated changes). "
                "Each task must contain a detailed 'instructions' field describing EXACTLY "
                "what to change, including the full context of the error or requirement. "
                "The corrector agents only have access to file read/write/patch tools — "
                "they cannot run shell commands or Docker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "List of file-edit tasks. Each task is an object with 'file_path' and 'instructions'.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Relative path to the target file (e.g., 'src/main.py')",
                                },
                                "instructions": {
                                    "type": "string",
                                    "description": (
                                        "Detailed editing instructions for this file. Include: "
                                        "what to change, why, expected before/after, and any "
                                        "relevant error messages or test output."
                                    ),
                                },
                            },
                            "required": ["file_path", "instructions"],
                        },
                    }
                },
                "required": ["tasks"],
            },
        },
        {
            "name": "batch_read_files",
            "description": (
                "Read multiple files in parallel. Returns the contents of all requested "
                "files at once, much faster than calling get_file_code repeatedly. "
                "Use this when you need to inspect 2 or more files (e.g., reading a source "
                "file and its test file, or reading several related modules). "
                "Each file read is independent and fail-safe — if one file is missing or "
                "unreadable, the others still succeed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "description": "List of relative file paths to read (e.g., ['src/main.py', 'tests/test_main.py'])",
                        "items": {
                            "type": "string",
                            "description": "Relative path to a file from project root",
                        },
                    }
                },
                "required": ["file_paths"],
            },
        },
    ]


# Tools the planner is allowed to use (read + write + docker + batch edit)
PLANNER_TOOL_NAMES = {
    "get_file_code",
    "update_file_code",
    "patch_file",
    "run_shell_command",
    "get_error_history",
    "get_action_history",
    "get_file_dependencies",
    "get_file_dependents",
    "docker_build",
    "docker_run",
    "batch_edit_files",
    "batch_read_files",
}

# Tools the executor is allowed to use (file read/write only — no docker, no recursion)
EXECUTOR_TOOL_NAMES = {
    "get_file_code",
    "update_file_code",
    "patch_file",
    "run_shell_command",
    "get_file_dependencies",
    "get_file_dependents",
}


def get_planner_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions filtered for the planner agent."""
    return [t for t in get_tool_definitions() if t["name"] in PLANNER_TOOL_NAMES]


def get_executor_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions filtered for the executor agent (file read/write only)."""
    return [t for t in get_tool_definitions() if t["name"] in EXECUTOR_TOOL_NAMES]
