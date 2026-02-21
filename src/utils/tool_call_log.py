"""
Tool Call Logger for tracking agent tool usage.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


class ToolCallLogger:
    """Logs tool calls to a file for debugging and analysis."""

    def __init__(self, log_path: Optional[str] = None, verbose: bool = False):
        self.log_path = log_path
        self.verbose = verbose
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        if not self.log_path:
            return
        try:
            log_dir = os.path.dirname(self.log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass

    def log(self, agent_name: Optional[str], function_name: str, args: Dict[str, Any], output: Any = None) -> None:
        """Log a tool call to the log file."""
        # Sanitize args to avoid logging large content
        sanitized_args = {}
        for k, v in args.items():
            if k in ('new_content', 'content', 'file_content', 'code'):
                sanitized_args[k] = f"<{len(str(v))} chars>"
            elif isinstance(v, str) and len(v) > 500:
                sanitized_args[k] = v[:500] + "..."
            else:
                sanitized_args[k] = v

        if self.verbose:
            out_str = str(output)[:300] if output is not None else "None"
            print(f"\n>> {agent_name}.{function_name}")
            for k, v in sanitized_args.items():
                print(f"   input  {k}: {v}")
            print(f"   output: {out_str}")

        if not self.log_path:
            return

        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name or "unknown",
                "function": function_name,
                "args": sanitized_args,
                "output": str(output)[:500] if output is not None else None,
            }

            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Don't fail on logging errors

    def get_recent_calls(self, limit: int = 50) -> list:
        """Get recent tool calls from the log file."""
        if not self.log_path or not os.path.exists(self.log_path):
            return []

        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            calls = []
            for line in lines[-limit:]:
                try:
                    calls.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

            return calls
        except Exception:
            return []

    def clear(self) -> None:
        """Clear the log file."""
        if not self.log_path:
            return
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:
                f.write("")
        except Exception:
            pass
