"""Tool definitions in JSON Schema format (provider-agnostic)"""

from typing import List, Dict, Any


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions in JSON Schema format.

    Ordering convention: dgat-backed analysis tools come first. The LLM
    should reach for these before structural/mutation tools — they're
    cheaper (pre-computed) and give broader context about the project.
    """
    return [
        # ── dgat-backed primary analysis tools ─────────────────────────────
        {
            "name": "get_file_description",
            "description": (
                "PRIMARY tool. Return the dgat-generated natural-language "
                "description of a file — what it does and why it matters. "
                "Always try this before reading file contents. Backed by "
                "dgat's LLM-annotated file tree."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'src/main.py')",
                    }
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_file_dependencies",
            "description": (
                "PRIMARY tool. Internal files that the given file depends on, "
                "resolved by dgat's cross-language import analysis. Prefer this "
                "over grep-style searches for understanding code structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                    "include_descriptions": {
                        "type": "boolean",
                        "description": "If true, include each dependency's file description (default false).",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_file_dependents",
            "description": (
                "PRIMARY tool. Files that import or depend on the given file "
                "(dgat reverse-edges). Essential before changing a module — "
                "tells you who breaks if you edit this file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                    "include_descriptions": {
                        "type": "boolean",
                        "description": "If true, include each dependent's file description (default false).",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_file_edges",
            "description": (
                "PRIMARY tool. Full directional edges for a file — both "
                "outgoing (what it imports) and incoming (what imports it), "
                "each with the original import statement and an LLM-generated "
                "description of *how* one file uses another. Use this when "
                "`get_file_dependencies`/`get_file_dependents` is too thin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_project_blueprint",
            "description": (
                "PRIMARY tool. Return the dgat-synthesized architectural "
                "blueprint of the whole project (markdown). Call this first "
                "when you need broad orientation — it summarises every file "
                "bottom-up into an overview."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "search_files",
            "description": (
                "PRIMARY tool. Search the project by file name or "
                "description using dgat's file tree. Returns ranked matches "
                "with rel_path, name, and description. Use this instead of "
                "grepping the filesystem for concept-level lookups."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name fragment or concept to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                },
                "required": ["query"],
            },
        },
        # ── external-context tools (web) ───────────────────────────────────
        {
            "name": "web_search",
            "description": (
                "Cheap web search (DuckDuckGo) for external context — library "
                "docs, error-message lookups, API usage. Returns ranked "
                "{title, url, snippet}. Cached per run. Prefer this first; "
                "fall back to browse_url only when a snippet isn't enough."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "1-10, default 5",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "browse_url",
            "description": (
                "Fetch a web page and return its readable text. Uses a real "
                "Chrome via browser-harness CDP when the daemon is running "
                "(handles JS-rendered pages); falls back to plain HTTP "
                "otherwise. Heavier than web_search — only call it when you "
                "have a specific URL from web_search that snippets didn't "
                "cover."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Absolute URL to fetch",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Truncate output (default 8000)",
                    },
                },
                "required": ["url"],
            },
        },
        # ── structural / mutation tools (come after dgat analysis) ─────────
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
            "description": "Run any shell command: install dependencies, run tests, build projects, or inspect files. This is the primary way to run tests. If a command stalls (no output for 60s), the process stays alive in the background and you get diagnostic info. You can then manage it with special commands: 'check_job <job_id>' (see latest output), 'kill_job <job_id>' (kill it), or 'list_jobs' (see all running/finished jobs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run, OR a job management command: 'check_job <job_id>' (new output since last check), 'kill_job <job_id>' (kill + get full output), 'wait_job <job_id>' (block until done), 'list_jobs'. Examples: 'pytest -v', 'check_job job_1', 'kill_job job_2'.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "Stall timeout — if no output for this many seconds, the process is kept alive in background and control returns to you (default 60).",
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
                "they cannot run shell commands."
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
        {
            "name": "give_up",
            "description": "Call this tool when you have tried everything and don't know how to proceed or fix the remaining issues. This will end your session and report that you have given up on the task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "The reason why you are giving up and what challenges were insurmountable.",
                    }
                },
                "required": ["reason"],
            },
        },
        {
            "name": "run_acceptance_tests",
            "description": "Run ALL externally-provided acceptance test cases against the real project and return ONLY a verdict: how many passed/failed, and the failing cases' inputs (never their expected outputs). Cheap to call — use it after every meaningful fix. mark_complete will be rejected while any case fails.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "mark_complete",
            "description": "Call this tool ONLY after (1) running the test suite and confirming all tests pass AND (2) actually running the project itself — executing the entry point / CLI commands / server endpoints with realistic inputs — and confirming it works. The pipeline will NOT stop until you call this. It rejects the call if runtime verification is missing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Summary of what was done: what was fixed, how many tests pass, etc.",
                    },
                    "runtime_verification": {
                        "type": "string",
                        "description": "Exactly which commands you executed to run the real project (not the tests), and what output you observed. E.g. 'ran python main.py add --amount 5 --category food (exit 0, printed confirmation); python main.py summary --month 2026-07 (printed category table)'.",
                    },
                },
                "required": ["reason", "runtime_verification"],
            },
        },
    ]


# Tools the planner is allowed to use. dgat tools come first — the planner
# should consult descriptions, dependencies, and the blueprint before
# reading file contents.
PLANNER_TOOL_NAMES = {
    # dgat-backed primary tools
    "get_file_description",
    "get_file_dependencies",
    "get_file_dependents",
    "get_file_edges",
    "get_project_blueprint",
    "search_files",
    # external context
    "web_search",
    "browse_url",
    # structural / mutation
    "get_file_code",
    "update_file_code",
    "patch_file",
    "run_shell_command",
    "get_error_history",
    "get_action_history",
    "batch_edit_files",
    "batch_read_files",
    "give_up",
    "mark_complete",
    "run_acceptance_tests",
}

# Tools the executor is allowed to use (no recursion).
EXECUTOR_TOOL_NAMES = {
    # dgat-backed (read-only analysis)
    "get_file_description",
    "get_file_dependencies",
    "get_file_dependents",
    "get_file_edges",
    "search_files",
    # structural / mutation
    "get_file_code",
    "update_file_code",
    "patch_file",
    "run_shell_command",
}


def get_planner_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions filtered for the planner agent."""
    return [t for t in get_tool_definitions() if t["name"] in PLANNER_TOOL_NAMES]


def get_executor_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions filtered for the executor agent (file read/write only)."""
    return [t for t in get_tool_definitions() if t["name"] in EXECUTOR_TOOL_NAMES]


# Tools available to the architecture planning agent (Phase 0).
# Research-only: no file mutation, no project-specific tools.
ARCH_PLANNER_TOOL_NAMES = {
    "web_search",
    "browse_url",
    "run_shell_command",
}


def get_arch_planner_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions for the Phase 0 architecture planning agent."""
    return [t for t in get_tool_definitions() if t["name"] in ARCH_PLANNER_TOOL_NAMES]
