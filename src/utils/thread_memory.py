"""
Thread Memory for Planner/Executor Agents

Maintains conversation context across iterations with automatic summarization
when token threshold is exceeded.
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ToolCall:
    """Represents a single tool call with its result"""
    agent: str  # "planner" or "executor"
    tool_name: str
    arguments: Dict
    result: Dict
    timestamp: str
    success: bool

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_summary(self) -> str:
        """Compact one-line summary"""
        args_preview = str(self.arguments)[:50] + "..." if len(str(self.arguments)) > 50 else str(self.arguments)
        status = "+" if self.success else "x"
        return f"[{self.agent}] {self.tool_name}({args_preview}) {status}"

    def to_full(self) -> str:
        """Full detail for recent tool calls"""
        result_preview = str(self.result)[:200] + "..." if len(str(self.result)) > 200 else str(self.result)
        return (
            f"  Tool: {self.tool_name}\n"
            f"  Agent: {self.agent}\n"
            f"  Args: {self.arguments}\n"
            f"  Result: {result_preview}\n"
            f"  Success: {self.success}"
        )


@dataclass
class Episode:
    """Represents one iteration cycle: error -> plan -> actions -> outcome"""
    iteration: int
    timestamp: str
    error_type: str  # "build" or "test"
    error_summary: str  # Condensed error description
    error_logs: str  # Full logs (will be summarized if old)
    plan: List[Dict]  # Tasks created by planner
    actions: List[Dict]  # Actions taken by executor
    tool_calls: List[Dict] = field(default_factory=list)  # All tool calls in this episode
    files_changed: List[str] = field(default_factory=list)
    outcome: str = "IN_PROGRESS"  # "SUCCESS", "FAILED", "PARTIAL"
    lesson: str = ""  # What we learned (filled after outcome)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_summary(self) -> str:
        """Compact summary for older episodes"""
        files_str = ", ".join(self.files_changed[:3])
        if len(self.files_changed) > 3:
            files_str += f" (+{len(self.files_changed) - 3} more)"

        return (
            f"[Iter {self.iteration}] {self.error_type.upper()} - {self.outcome}\n"
            f"  Error: {self.error_summary[:100]}\n"
            f"  Files: {files_str}\n"
            f"  Lesson: {self.lesson or 'N/A'}"
        )

    def to_full(self) -> str:
        """Full detail for recent episodes"""
        lines = [
            f"=== Iteration {self.iteration} ({self.error_type.upper()}) ===",
            f"Timestamp: {self.timestamp}",
            f"",
            f"ERROR:",
            f"{self.error_summary}",
        ]

        if self.error_logs:
            # Include last 1500 chars of logs for recent episodes
            logs_preview = self.error_logs[-1500:] if len(self.error_logs) > 1500 else self.error_logs
            lines.append(f"\nLogs (last 1500 chars):\n```\n{logs_preview}\n```")

        lines.append(f"\nPLAN ({len(self.plan)} tasks):")
        for i, task in enumerate(self.plan[:5], 1):  # Max 5 tasks shown
            lines.append(f"  {i}. {task.get('title', 'Untitled')}")
            if task.get('files'):
                lines.append(f"     Files: {', '.join(task['files'][:3])}")

        if len(self.plan) > 5:
            lines.append(f"  ... and {len(self.plan) - 5} more tasks")

        # Tool calls section
        if self.tool_calls:
            lines.append(f"\nTOOL CALLS ({len(self.tool_calls)} total):")
            # Group by agent
            planner_calls = [tc for tc in self.tool_calls if tc.get('agent') == 'planner']
            executor_calls = [tc for tc in self.tool_calls if tc.get('agent') == 'executor']

            if planner_calls:
                lines.append(f"  Planner ({len(planner_calls)} calls):")
                for tc in planner_calls[-3:]:  # Last 3 planner calls
                    status = "+" if tc.get('success') else "x"
                    lines.append(f"    {status} {tc.get('tool_name', '?')}({list(tc.get('arguments', {}).keys())})")
                    if not tc.get('success') and tc.get('result', {}).get('error'):
                        lines.append(f"      Error: {tc['result']['error'][:80]}")

            if executor_calls:
                lines.append(f"  Executor ({len(executor_calls)} calls):")
                for tc in executor_calls[-5:]:  # Last 5 executor calls
                    status = "+" if tc.get('success') else "x"
                    args = tc.get('arguments', {})
                    if tc.get('tool_name') == 'update_file_code':
                        lines.append(f"    {status} update_file_code({args.get('file_path', '?')})")
                    elif tc.get('tool_name') == 'get_file_code':
                        lines.append(f"    {status} get_file_code({args.get('file_path', '?')})")
                    else:
                        lines.append(f"    {status} {tc.get('tool_name', '?')}(...)")

        lines.append(f"\nACTIONS TAKEN:")
        for action in self.actions[-5:]:  # Last 5 actions
            lines.append(f"  - {action.get('type', 'unknown')}: {action.get('message', '')[:80]}")

        lines.append(f"\nFILES CHANGED: {', '.join(self.files_changed)}")
        lines.append(f"OUTCOME: {self.outcome}")

        if self.lesson:
            lines.append(f"LESSON LEARNED: {self.lesson}")

        return "\n".join(lines)


class ThreadMemory:
    """
    Maintains thread memory across iterations with automatic summarization.

    Usage:
        memory = ThreadMemory(token_threshold=8000)

        # Start new episode
        memory.start_episode(iteration=1, error_type="build", error="...", logs="...")

        # Add plan from planner
        memory.add_plan(tasks=[...])

        # Add actions from executor
        memory.add_action(action_type="edit", message="Updated file X")

        # Complete episode with outcome
        memory.complete_episode(outcome="FAILED", files_changed=["a.py"], lesson="Import fix didn't work")

        # Get context for prompt
        context = memory.get_context_for_prompt()
    """

    def __init__(self, token_threshold: int = 25000, summarizer=None):
        self.episodes: List[Episode] = []
        self.current_episode: Optional[Dict] = None
        self.summary_of_old_episodes: str = ""
        self.summarized_up_to: int = 0  # Episode index up to which we've summarized
        self.token_threshold = token_threshold
        self.summarizer = summarizer  # Optional: LLM-based summarizer

        # Track patterns for smarter context
        self.repeated_errors: Dict[str, int] = {}  # error_signature -> count
        self.failed_fixes: List[Dict] = []  # Fixes that didn't work

    def start_episode(self, iteration: int, error_type: str,
                      error_summary: str, error_logs: str = "") -> None:
        """Start a new episode when an error is encountered"""
        self.current_episode = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_summary": error_summary,
            "error_logs": error_logs,
            "plan": [],
            "actions": [],
            "tool_calls": [],  # Track all tool calls in this episode
            "files_changed": [],
            "outcome": "IN_PROGRESS",
            "lesson": ""
        }

        # Track repeated errors
        error_sig = f"{error_type}:{error_summary[:100]}"
        self.repeated_errors[error_sig] = self.repeated_errors.get(error_sig, 0) + 1

    def add_plan(self, tasks: List[Dict]) -> None:
        """Add planner's tasks to current episode"""
        if self.current_episode:
            self.current_episode["plan"] = tasks

    def add_action(self, action_type: str, message: str, **kwargs) -> None:
        """Add an action taken by executor"""
        if self.current_episode:
            self.current_episode["actions"].append({
                "type": action_type,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            })

    def add_tool_call(self, agent: str, tool_name: str, arguments: Dict,
                      result: Dict, success: bool = True) -> None:
        """
        Track a tool call and its result.

        Args:
            agent: "planner" or "executor"
            tool_name: Name of the tool called
            arguments: Arguments passed to the tool
            result: Result returned by the tool
            success: Whether the tool call succeeded
        """
        if self.current_episode:
            # Sanitize arguments - remove large content
            sanitized_args = {}
            for k, v in arguments.items():
                if k in ('new_content', 'content', 'file_content', 'code'):
                    # Don't store full file contents - just note it was provided
                    sanitized_args[k] = f"<{len(str(v))} chars>"
                elif isinstance(v, str) and len(v) > 200:
                    sanitized_args[k] = v[:200] + "..."
                else:
                    sanitized_args[k] = v

            # Sanitize result - remove large content
            sanitized_result = {}
            for k, v in result.items():
                if k in ('content', 'old_content', 'new_content'):
                    sanitized_result[k] = f"<{len(str(v))} chars>" if v else None
                elif isinstance(v, str) and len(v) > 300:
                    sanitized_result[k] = v[:300] + "..."
                else:
                    sanitized_result[k] = v

            tool_call_entry = {
                "agent": agent,
                "tool_name": tool_name,
                "arguments": sanitized_args,
                "result": sanitized_result,
                "success": success,
                "timestamp": datetime.now().isoformat()
            }

            self.current_episode["tool_calls"].append(tool_call_entry)

            # Track file reads for context
            if tool_name == "get_file_code" and success:
                file_path = arguments.get("file_path", "")
                if file_path:
                    self.add_action("read", f"Read {file_path}", file=file_path)

            # Track failed tool calls specially
            if not success:
                error_msg = result.get("error", "Unknown error")
                self.failed_fixes.append({
                    "iteration": self.current_episode["iteration"],
                    "tool": tool_name,
                    "error": error_msg[:200],
                    "agent": agent
                })

    def add_file_change(self, file_path: str) -> None:
        """Track a file that was modified"""
        if self.current_episode and file_path not in self.current_episode["files_changed"]:
            self.current_episode["files_changed"].append(file_path)

    def complete_episode(self, outcome: str, lesson: str = "",
                         files_changed: List[str] = None) -> None:
        """Complete the current episode and add to history"""
        if not self.current_episode:
            return

        self.current_episode["outcome"] = outcome
        self.current_episode["lesson"] = lesson

        if files_changed:
            for f in files_changed:
                if f not in self.current_episode["files_changed"]:
                    self.current_episode["files_changed"].append(f)

        # Create Episode object and add to history
        episode = Episode(**self.current_episode)
        self.episodes.append(episode)

        # Track failed fixes for learning
        if outcome == "FAILED":
            self.failed_fixes.append({
                "iteration": episode.iteration,
                "error": episode.error_summary[:200],
                "attempted_fix": [t.get("title", "") for t in episode.plan[:3]],
                "files": episode.files_changed
            })

        self.current_episode = None

        # Check if we need to summarize
        self._check_and_summarize()

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars = 1 token)"""
        return len(text) // 4

    def _check_and_summarize(self) -> None:
        """Check token count and summarize if over threshold"""
        context = self._build_full_context()
        token_count = self._estimate_tokens(context)

        if token_count > self.token_threshold:
            self._summarize_older_episodes()

    def _summarize_older_episodes(self) -> None:
        """Summarize older episodes to reduce token count"""
        if len(self.episodes) <= 3:
            return  # Keep at least 3 episodes in full detail

        # Episodes to summarize (all except last 3)
        to_summarize = self.episodes[self.summarized_up_to:-3]

        if not to_summarize:
            return

        # Build summary
        summary_lines = []

        if self.summary_of_old_episodes:
            summary_lines.append(self.summary_of_old_episodes)
            summary_lines.append("")

        summary_lines.append(f"--- Summary of iterations {to_summarize[0].iteration}-{to_summarize[-1].iteration} ---")

        # Group by outcome
        failed = [e for e in to_summarize if e.outcome == "FAILED"]

        if failed:
            summary_lines.append(f"\nFAILED attempts ({len(failed)}):")
            for ep in failed:
                summary_lines.append(f"  - Iter {ep.iteration}: {ep.error_summary[:60]}...")
                if ep.lesson:
                    summary_lines.append(f"    Lesson: {ep.lesson}")

        # Key files touched
        all_files = set()
        for ep in to_summarize:
            all_files.update(ep.files_changed)

        if all_files:
            summary_lines.append(f"\nFiles modified: {', '.join(list(all_files)[:10])}")

        # Patterns observed
        error_types = {}
        for ep in to_summarize:
            key = ep.error_summary[:50]
            error_types[key] = error_types.get(key, 0) + 1

        repeated = [(k, v) for k, v in error_types.items() if v > 1]
        if repeated:
            summary_lines.append("\nRepeated errors:")
            for error, count in repeated[:3]:
                summary_lines.append(f"  - '{error}...' occurred {count} times")

        self.summary_of_old_episodes = "\n".join(summary_lines)
        self.summarized_up_to = len(self.episodes) - 3

    def _build_full_context(self) -> str:
        """Build full context string for token estimation"""
        parts = []

        if self.summary_of_old_episodes:
            parts.append(self.summary_of_old_episodes)

        for ep in self.episodes[self.summarized_up_to:]:
            parts.append(ep.to_full())

        return "\n\n".join(parts)

    def get_context_for_prompt(self, max_recent: int = 3) -> str:
        """
        Get formatted context to include in planner/executor prompt.

        Returns context with:
        - Summary of old episodes (if any)
        - Full detail of recent episodes
        - Warnings about repeated errors
        - Failed fixes to avoid
        """
        lines = []

        # Header
        lines.append("## ITERATION HISTORY (Thread Memory)")
        lines.append(f"Total iterations: {len(self.episodes)}")

        # Warnings about repeated errors
        repeated = [(k, v) for k, v in self.repeated_errors.items() if v > 1]
        if repeated:
            lines.append("\n** REPEATED ERRORS (these fixes did NOT work):")
            for error_sig, count in repeated[:5]:
                lines.append(f"  - {error_sig} - attempted {count} times")

        # Failed fixes to avoid
        if self.failed_fixes:
            lines.append("\n** FIXES THAT FAILED (do NOT repeat these):")
            for fix in self.failed_fixes[-5:]:  # Last 5 failed fixes
                lines.append(f"  - Iter {fix['iteration']}: {fix.get('attempted_fix', fix.get('error', 'unknown'))}")
                if fix.get('files'):
                    lines.append(f"    Files: {', '.join(fix['files'][:3])}")

        lines.append("")

        # Summary of older episodes
        if self.summary_of_old_episodes:
            lines.append(self.summary_of_old_episodes)
            lines.append("")

        # Recent episodes in full detail
        recent_start = max(0, len(self.episodes) - max_recent)
        recent_episodes = self.episodes[recent_start:]

        if recent_episodes:
            lines.append(f"### Recent Iterations (Full Detail)")
            for ep in recent_episodes:
                lines.append("")
                lines.append(ep.to_full())

        # Current episode in progress
        if self.current_episode:
            lines.append("")
            lines.append("### CURRENT ITERATION (In Progress)")
            lines.append(f"Error Type: {self.current_episode['error_type']}")
            lines.append(f"Error: {self.current_episode['error_summary']}")

        return "\n".join(lines)

    def get_lessons_learned(self) -> List[str]:
        """Extract all lessons learned from episodes"""
        return [ep.lesson for ep in self.episodes if ep.lesson]

    def get_files_frequently_changed(self, min_count: int = 2) -> Dict[str, int]:
        """Get files that have been changed multiple times (potential problem areas)"""
        file_counts = {}
        for ep in self.episodes:
            for f in ep.files_changed:
                file_counts[f] = file_counts.get(f, 0) + 1

        return {f: c for f, c in file_counts.items() if c >= min_count}

    def to_dict(self) -> Dict:
        """Serialize memory to dict for persistence"""
        return {
            "episodes": [ep.to_dict() for ep in self.episodes],
            "summary_of_old_episodes": self.summary_of_old_episodes,
            "summarized_up_to": self.summarized_up_to,
            "repeated_errors": self.repeated_errors,
            "failed_fixes": self.failed_fixes
        }

    def save_to_file(self, file_path: str) -> None:
        """Save memory to JSON file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str) -> 'ThreadMemory':
        """Load memory from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        memory = cls()
        memory.episodes = [Episode(**ep) for ep in data.get("episodes", [])]
        memory.summary_of_old_episodes = data.get("summary_of_old_episodes", "")
        memory.summarized_up_to = data.get("summarized_up_to", 0)
        memory.repeated_errors = data.get("repeated_errors", {})
        memory.failed_fixes = data.get("failed_fixes", [])

        return memory
