import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from .inference import InferenceManager
from .prompt_manager import PromptManager

CORRECTOR_TOOL_DEFS = [
    {
        "name": "get_file_code",
        "description": "Read a file's contents. Supports optional start_line/end_line for slicing.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file from project root",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional 1-based start line",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional 1-based end line",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "update_file_code",
        "description": "Replace entire file content with new code. Preferred method for edits.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file to update",
                },
                "new_content": {
                    "type": "string",
                    "description": "Complete new code content for the file",
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
        "name": "patch_file",
        "description": "Surgical patch: full_rewrite | delete_lines | replace_lines | insert_after_line.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file to patch",
                },
                "fix_type": {
                    "type": "string",
                    "description": "Patch mode: full_rewrite, delete_lines, replace_lines, insert_after_line",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of why this patch is applied",
                },
                "line_start": {
                    "type": "integer",
                    "description": "1-based start line",
                },
                "line_end": {
                    "type": "integer",
                    "description": "1-based end line (inclusive)",
                },
                "new_content": {
                    "type": "string",
                    "description": "Replacement or insertion content",
                },
            },
            "required": ["file_path", "fix_type", "description"],
        },
    },
]

ALLOWED_TOOLS = frozenset(t["name"] for t in CORRECTOR_TOOL_DEFS)


def _run_one(task: Dict[str, str], tool_handler: Any, pm: PromptManager) -> Dict[str, Any]:
    file_path = task["file_path"]
    try:
        prompt = pm.render(
            "corrector_agent.j2",
            file_path=file_path,
            instructions=task["instructions"],
        )

        provider = InferenceManager.get_active_provider()
        tools = provider.format_tools(CORRECTOR_TOOL_DEFS)
        messages = provider.create_initial_message(prompt)
        changes_made: List[Dict[str, Any]] = []

        for _ in range(6):
            response = provider.call_model(messages, tools=tools)
            function_calls = provider.extract_function_calls(response)
            if not function_calls:
                break

            function_responses = []
            for fc in function_calls:
                func_name = fc["name"]
                func_args = fc.get("args", {})

                if func_name not in ALLOWED_TOOLS:
                    result = {"error": f"Tool '{func_name}' is not available to the corrector agent."}
                else:
                    result = tool_handler.handle_function_call(func_name, func_args)

                if func_name in ("update_file_code", "patch_file"):
                    changes_made.append({
                        "tool": func_name,
                        "file": func_args.get("file_path", file_path),
                        "success": result.get("success", False),
                        "description": func_args.get("change_description", func_args.get("description", "")),
                    })

                function_responses.append(
                    provider.create_function_response(func_name, result, fc.get("id"))
                )

            provider.accumulate_messages(messages, response, function_responses)

        return {
            "file_path": file_path,
            "success": len(changes_made) > 0 and all(c.get("success") for c in changes_made),
            "changes_made": changes_made,
        }
    except Exception as e:
        return {
            "file_path": file_path,
            "success": False,
            "changes_made": [],
            "error": str(e),
        }


def batch_edit_files(tasks: List[Dict[str, str]], tool_handler: Any) -> Dict[str, Any]:
    if not tasks:
        return {"success": False, "error": "No tasks provided"}

    seen_files = set()
    for t in tasks:
        fp = t.get("file_path", "")
        if not fp:
            return {"success": False, "error": "Each task must have a 'file_path'"}
        if not t.get("instructions"):
            return {"success": False, "error": f"Task for '{fp}' has no 'instructions'"}
        if fp in seen_files:
            return {"success": False, "error": f"Duplicate file_path: '{fp}'. Only one task per file is allowed."}
        seen_files.add(fp)

    pm = PromptManager()
    print(f"[batch_edit] Spawning {len(tasks)} corrector agents in parallel...")

    results = []
    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as pool:
        future_to_task = {
            pool.submit(_run_one, task, tool_handler, pm): task
            for task in tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
            except Exception as e:
                result = {
                    "file_path": task.get("file_path", "???"),
                    "success": False,
                    "changes_made": [],
                    "error": str(e),
                }
            results.append(result)
            status = "✓" if result.get("success") else "✗"
            print(f"[batch_edit] {status} {result['file_path']}")

    file_order = {t["file_path"]: i for i, t in enumerate(tasks)}
    results.sort(key=lambda r: file_order.get(r["file_path"], 999))

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    return {
        "success": failed == 0,
        "total": len(tasks),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
