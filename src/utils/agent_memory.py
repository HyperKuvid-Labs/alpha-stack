"""
Memory for planner and orchestrator agents.

Records tool actions directly from tool call arguments during a run.
Entries accumulate in full detail. When total size crosses a threshold,
an LLM summarizes the older entries — recent entries always stay full.
Summaries are persisted to disk for the next run.
"""

import json
import os
from typing import Dict, List


def _tail(text: str, n: int = 3) -> str:
    """Return the last n non-empty lines of text, joined."""
    if not text:
        return ""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return " | ".join(lines[-n:])[:400]


class AgentMemory:
    """
    Append-only action log with LLM-based compaction.

    Entries are kept in full detail. When the raw size of all entries
    crosses `summarize_threshold`, the older half is sent to the LLM
    for summarization — the summary replaces those entries.
    Recent entries always remain in full detail.
    """

    # ~4 chars per token on average
    CHARS_PER_TOKEN = 4

    def __init__(self, summarize_threshold_tokens: int = 30000):
        self.entries: List[Dict] = []
        self._summaries: List[str] = []       # LLM-generated summaries of compacted entries
        self._previous_summary: str = ""       # Loaded from disk (last run)
        self.summarize_threshold = summarize_threshold_tokens * self.CHARS_PER_TOKEN

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        session: int,
        action: str,
        file: str = "",
        detail: str = "",
        outcome: str = "",
    ):
        entry = {
            "session": session,
            "action": action,
            "file": file,
            "detail": detail,
            "outcome": outcome,
        }
        self.entries.append(entry)
        self._maybe_compact()

    def record_edit(self, session: int, file_path: str, description: str):
        self.record(
            session=session,
            action="edit",
            file=os.path.basename(file_path),
            detail=description,
        )

    def record_batch_edit(self, session: int, tasks: list):
        files = [os.path.basename(t.get("file_path", "")) for t in (tasks or [])]
        self.record(
            session=session,
            action="batch_edit",
            file=", ".join(files[:5]),
            detail=f"{len(tasks)} files",
        )

    def record_shell(self, session: int, command: str, output: str, success: bool = True):
        # Capture the tail of output — test summaries are always at the end
        tail = _tail(output, n=8) if output else ""
        self.record(
            session=session,
            action="shell",
            file=command[:80],
            detail=tail,
            outcome="OK" if success else "FAIL",
        )

    def record_guidance(self, filepath: str, summary: str):
        self.record(
            session=0,
            action="guidance",
            file=os.path.basename(filepath),
            detail=summary,
        )

    def record_regenerate(self, filepath: str, corrections: str):
        self.record(
            session=0,
            action="regenerate",
            file=os.path.basename(filepath),
            detail=corrections,
        )

    # ------------------------------------------------------------------
    # Compaction — triggered when entries get too large
    # ------------------------------------------------------------------

    def _entries_size(self) -> int:
        """Approximate character count of all entries rendered."""
        return sum(len(self._render_entry(e)) for e in self.entries)

    def _maybe_compact(self):
        """If entries exceed threshold, summarize older half with LLM."""
        if self._entries_size() < self.summarize_threshold:
            return
        if len(self.entries) < 4:
            return

        # Split: summarize older half, keep recent half
        split = len(self.entries) // 2
        older = self.entries[:split]
        self.entries = self.entries[split:]

        summary = self._summarize_entries(older)
        if summary:
            self._summaries.append(summary)

    def _summarize_entries(self, entries: List[Dict]) -> str:
        """Call LLM to summarize a batch of entries."""
        raw = "\n".join(self._render_entry(e) for e in entries)
        if not raw.strip():
            return ""

        from .inference import InferenceManager

        provider = InferenceManager.get_active_provider()
        prompt = (
            "You are summarizing part of a debugging/generation session for an AI agent. "
            "Below is a batch of action log entries.\n\n"
            "Summarize the key information in bullet points. Focus on:\n"
            "- What errors were encountered and their root causes\n"
            "- What fixes were applied and to which files\n"
            "- What worked and what didn't\n"
            "- Important shell output or test results\n\n"
            "Keep file names, error messages, and specific details that would help "
            "the agent avoid repeating mistakes. Drop routine actions that didn't "
            "reveal anything.\n\n"
            f"### Entries\n```\n{raw}\n```"
        )

        try:
            messages = provider.create_initial_message(prompt)
            response = provider.call_model(messages)
            text = provider.extract_text(response)
            return (text or "").strip()
        except Exception:
            # Fallback: keep raw entries as-is (trimmed)
            return raw[:2000]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str):
        """Persist memory state to disk."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        data = {
            "previous_summary": self._previous_summary,
            "summaries": self._summaries,
            "entries": self.entries,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str):
        """Load previous run's memory from disk."""
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Build previous run context from saved state
            prev_summary = data.get("previous_summary", "")
            summaries = data.get("summaries", [])
            entries = data.get("entries", [])

            # Render the previous run into a single summary block
            parts = []
            if prev_summary:
                parts.append(prev_summary)
            parts.extend(summaries)
            if entries:
                parts.append("\n".join(self._render_entry(e) for e in entries))

            if parts:
                raw = "\n\n".join(parts)
                self._previous_summary = raw

        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_entry(self, e: Dict) -> str:
        """Render a single entry in full detail."""
        session_tag = f"[S{e['session']}]" if e.get("session") else ""
        action = e.get("action", "")

        if action == "edit":
            desc = f": \"{e['detail']}\"" if e.get("detail") else ""
            return f"{session_tag} edit {e.get('file', '')}{desc}"
        elif action == "batch_edit":
            return f"{session_tag} batch_edit [{e.get('file', '')}] ({e.get('detail', '')})"
        elif action == "shell":
            outcome = e.get("outcome", "")
            status = f" [{outcome}]" if outcome else ""
            lines = [f"{session_tag} $ {e.get('file', '')}{status}"]
            if e.get("detail"):
                for ol in e["detail"].splitlines():
                    lines.append(f"    {ol}")
            return "\n".join(lines)
        elif action == "guidance":
            return f"guided {e.get('file', '')}: \"{e.get('detail', '')}\""
        elif action == "regenerate":
            return f"regenerated {e.get('file', '')}: \"{e.get('detail', '')}\""
        else:
            return f"{session_tag} {action} {e.get('file', '')} {e.get('detail', '')}".strip()

    def render(self) -> str:
        """
        Render full memory for injection into agent prompt.

        Structure:
          - Previous run summary (loaded from disk)
          - Current run summaries (from compaction)
          - Current entries (full detail)
        """
        if not self.entries and not self._summaries and not self._previous_summary:
            return ""

        sections = []

        if self._previous_summary:
            if self._previous_summary.strip():
                sections.append(f"--- previous run ---\n{self._previous_summary}")

        if self._summaries:
            sections.append("--- earlier this run ---\n" + "\n\n".join(self._summaries))

        if self.entries:
            rendered = [
                self._render_entry(e) for e in self.entries
            ]
            if rendered:
                sections.append("\n".join(rendered))

        return "\n\n".join(sections)

    def __len__(self):
        return len(self.entries)

    def __bool__(self):
        return len(self.entries) > 0 or bool(self._summaries) or bool(self._previous_summary)
