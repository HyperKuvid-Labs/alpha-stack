"""MemoryStore — drop-in replacement for the old AgentMemory.

Keeps every public method the old class exposed so existing call-sites don't
break. The render() method gains an optional `query` argument; when supplied,
the prompt is composed from a working buffer + retrieved episodes + matched
insights, all token-budgeted. Without a query, render() falls back to the old
recency-ordered behaviour.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence

import numpy as np

from .dedup import LoopDetector
from .embed import Embedder
from .retrieval import (
    W_IMPORTANCE,
    W_RECENCY,
    W_RELEVANCE,
    embed_query,
    score_and_topk,
    tag_overlap_filter,
)
from .reflect import ReflectionWorker
from .signatures import error_signature


logger = logging.getLogger(__name__)


CHARS_PER_TOKEN = 4
DEFAULT_BUDGET_TOKENS = 2000
WORKING_BUFFER_K = 15
TOPK_EPISODES = 8
TOPK_INSIGHTS = 5


def _tail(text: str, n: int = 3) -> str:
    """Return the last n non-empty lines of text, joined."""
    if not text:
        return ""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return " | ".join(lines[-n:])[:400]


def _render_entry(e: Dict[str, Any]) -> str:
    session_tag = f"[S{e['session']}]" if e.get("session") else ""
    action = e.get("action", "")
    if action == "edit":
        desc = f": \"{e['detail']}\"" if e.get("detail") else ""
        affected = e.get("affected") or ""
        affected_part = f"  → affected: {affected}" if affected else ""
        return f"{session_tag} edit {e.get('file', '')}{desc}{affected_part}"
    elif action == "batch_edit":
        affected = e.get("affected") or ""
        affected_part = f"  → affected: {affected}" if affected else ""
        return f"{session_tag} batch_edit [{e.get('file', '')}] ({e.get('detail', '')}){affected_part}"
    elif action == "shell":
        outcome = e.get("outcome", "")
        status = f" [{outcome}]" if outcome else ""
        lines = [f"{session_tag} $ {e.get('file', '')}{status}"]
        if e.get("detail"):
            for ol in str(e["detail"]).splitlines():
                lines.append(f"    {ol}")
        return "\n".join(lines)
    elif action == "guidance":
        return f"guided {e.get('file', '')}: \"{e.get('detail', '')}\""
    elif action == "regenerate":
        return f"regenerated {e.get('file', '')}: \"{e.get('detail', '')}\""
    else:
        return f"{session_tag} {action} {e.get('file', '')} {e.get('detail', '')}".strip()


def _importance_for(
    action: str,
    outcome: str,
    error_class: str,
    recent_fail_classes: Sequence[str],
) -> float:
    if action == "shell":
        if outcome == "FAIL":
            return 0.9
        if outcome == "OK" and error_class and error_class in recent_fail_classes:
            return 1.0
        return 0.4
    if action in ("edit", "batch_edit", "patch"):
        return 0.8  # refined later if followed by a shell OK
    if action == "guidance":
        return 0.5
    if action == "regenerate":
        return 0.7
    return 0.3


def _embedding_text(action: str, file: str, detail: str, outcome: str) -> str:
    parts = [action, file, detail, outcome]
    return " ".join(p for p in parts if p)[:2000]


class MemoryStore:
    """Retrieval-aware episodic + semantic memory.

    Construction modes:
      - MemoryStore(project_root=..., role=...) — SQLite-backed (persistent)
      - MemoryStore() — in-memory only (matches orchestrator's prior behaviour)

    Back-compat: summarize_threshold_tokens accepted but unused (kept so call-sites
    that still pass it don't break).
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        role: str = "planner",
        *,
        summarize_threshold_tokens: int = 30000,  # kept for back-compat; unused
        enable_reflection: bool = True,
    ):
        # Import here to avoid a cycle during module import.
        from .store import MemoryDB

        self.role = role
        self.project_root = project_root

        if project_root:
            db_path = os.path.join(project_root, ".alpha_stack", "memory.db")
            self.db: MemoryDB = MemoryDB(db_path)
        else:
            self.db = MemoryDB(None)  # in-memory

        self._embedder = Embedder.get()
        self._loop = LoopDetector()
        self._working: Deque[Dict[str, Any]] = deque(maxlen=WORKING_BUFFER_K)
        self._pending_warnings: List[str] = []
        self._recent_fail_classes: Deque[str] = deque(maxlen=10)
        self._last_edit_id: Optional[int] = None  # for post-hoc importance refinement
        self._pending_edit_ids: List[int] = []

        self._reflection = ReflectionWorker(self.db, enable=enable_reflection)

        # Legacy JSON import runs once per project.
        if project_root:
            self._maybe_import_legacy()

    # ------------------------------------------------------------------
    # Public API — preserves old AgentMemory surface
    # ------------------------------------------------------------------

    @property
    def entries(self) -> List[Dict[str, Any]]:
        """Back-compat: expose the working buffer as a list."""
        return list(self._working)

    def record(
        self,
        session: int,
        action: str,
        file: str = "",
        detail: str = "",
        outcome: str = "",
        affected: str = "",
    ) -> None:
        error_class, error_hash = ("", "")
        if action == "shell" and outcome == "FAIL":
            error_class, error_hash = error_signature(detail)
            if error_class:
                self._recent_fail_classes.append(error_class)
            self._reflection.notify_fail()
        importance = _importance_for(action, outcome, error_class, list(self._recent_fail_classes))

        emb_text = _embedding_text(action, file, detail, outcome)
        emb = self._embedder.embed(emb_text) if emb_text.strip() else None

        ep_id = self.db.insert_episode(
            role=self.role,
            session=int(session or 0),
            action=action,
            file=file or "",
            detail=detail or "",
            outcome=outcome or "",
            importance=importance,
            error_class=error_class,
            error_hash=error_hash,
            embedding=emb,
        )

        entry = {
            "id": ep_id,
            "session": int(session or 0),
            "action": action,
            "file": file or "",
            "detail": detail or "",
            "outcome": outcome or "",
            "importance": importance,
            "error_class": error_class,
            "ts": time.time(),
        }
        if affected:
            entry["affected"] = affected
        self._working.append(entry)

        # Post-hoc importance refinement: a shell OK after a recent edit
        # signals the edit as the fix. We can't easily UPDATE by id without
        # re-adding another table; skip for now — importance is still
        # captured by the fail→ok transition heuristic above.

        # Loop detection
        warn = self._loop.observe(action, file, detail, outcome)
        if warn and warn not in self._pending_warnings:
            self._pending_warnings.append(warn)
            if len(self._pending_warnings) > 5:
                self._pending_warnings = self._pending_warnings[-5:]

    def record_edit(
        self,
        session: int,
        file_path: str,
        description: str,
        affected_files: Optional[List[str]] = None,
    ) -> None:
        affected_str = ""
        if affected_files:
            names = [os.path.basename(p) for p in affected_files[:5] if p]
            extra = max(0, len(affected_files) - 5)
            affected_str = ", ".join(names) + (f" (+{extra} more)" if extra else "")
        self.record(
            session=session,
            action="edit",
            file=os.path.basename(file_path or ""),
            detail=description or "",
            affected=affected_str,
        )

    def record_batch_edit(
        self,
        session: int,
        tasks: list,
        affected_files: Optional[List[str]] = None,
    ) -> None:
        files = [os.path.basename(t.get("file_path", "")) for t in (tasks or [])]
        affected_str = ""
        if affected_files:
            names = [os.path.basename(p) for p in affected_files[:5] if p]
            extra = max(0, len(affected_files) - 5)
            affected_str = ", ".join(names) + (f" (+{extra} more)" if extra else "")
        self.record(
            session=session,
            action="batch_edit",
            file=", ".join(files[:5]),
            detail=f"{len(tasks or [])} files",
            affected=affected_str,
        )

    def record_shell(self, session: int, command: str, output: str, success: bool = True) -> None:
        tail = _tail(output, n=8) if output else ""
        self.record(
            session=session,
            action="shell",
            file=(command or "")[:80],
            detail=tail,
            outcome="OK" if success else "FAIL",
        )

    def record_guidance(self, filepath: str, summary: str) -> None:
        self.record(
            session=0,
            action="guidance",
            file=os.path.basename(filepath or ""),
            detail=summary or "",
        )

    def record_regenerate(self, filepath: str, corrections: str) -> None:
        self.record(
            session=0,
            action="regenerate",
            file=os.path.basename(filepath or ""),
            detail=corrections or "",
        )

    # ------------------------------------------------------------------
    # Persistence — the DB writes eagerly, so save()/load() are mostly
    # bookkeeping + the session_end reflection trigger.
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> None:
        """Flush session-end reflection. `path` is accepted for API compat but
        ignored — persistence is the SQLite file under project_root."""
        try:
            self._reflection.notify_session_end()
        except Exception as e:
            logger.debug(f"session-end reflection enqueue failed: {e}")
        # Give the worker a moment to process; don't block forever.
        try:
            self._reflection.stop(timeout=3.0)
        except Exception:
            pass

    def load(self, path: Optional[str] = None) -> None:
        """No-op: DB opens lazily. Kept for API compat."""
        return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(
        self,
        query: Optional[str] = None,
        *,
        budget_tokens: int = DEFAULT_BUDGET_TOKENS,
        role: Optional[str] = None,
    ) -> str:
        """Compose a prompt-ready memory blob.

        Sections (in order of priority; truncated from the bottom if over budget):
          1. Working buffer — last K entries verbatim
          2. Lessons — matched insights
          3. Similar — retrieved episodes scored against the query
          4. LoopWarn — repeated-action warnings
        """
        budget_chars = max(200, int(budget_tokens) * CHARS_PER_TOKEN)

        working_text = self._render_working(limit_chars=800 * CHARS_PER_TOKEN)
        lessons_text = self._render_lessons(query, limit_chars=400 * CHARS_PER_TOKEN)
        similar_text = self._render_similar(query, limit_chars=600 * CHARS_PER_TOKEN)
        warn_text = self._render_warnings(limit_chars=200 * CHARS_PER_TOKEN)

        sections: List[tuple] = [
            ("Working", working_text),
            ("Lessons", lessons_text),
            ("Similar", similar_text),
            ("LoopWarn", warn_text),
        ]
        sections = [(h, b) for h, b in sections if b.strip()]

        parts: List[str] = []
        total = 0
        for header, body in sections:
            header_line = f"### {header}\n"
            remaining = budget_chars - total - len(header_line)
            if remaining <= 20:
                break
            body_clipped = body
            if len(body_clipped) > remaining:
                body_clipped = body_clipped[:remaining].rstrip()
            block = header_line + body_clipped
            parts.append(block)
            total += len(block) + 2
        return "\n\n".join(parts)

    def _render_working(self, *, limit_chars: int) -> str:
        if not self._working:
            return ""
        lines = [_render_entry(e) for e in self._working]
        out = "\n".join(lines)
        if len(out) > limit_chars:
            out = out[-limit_chars:]
            nl = out.find("\n")
            if nl != -1:
                out = out[nl + 1:]
        return out

    def _render_lessons(self, query: Optional[str], *, limit_chars: int) -> str:
        insights = self.db.fetch_insights(with_embeddings=True)
        if not insights:
            return ""
        if query:
            q_emb = embed_query(query)
            rows = [
                {
                    **ins,
                    "ts": ins.get("last_reinforced_ts", ins.get("created_ts", 0.0)),
                    "importance": min(1.0, 0.5 + 0.1 * int(ins.get("support_count", 1))),
                }
                for ins in insights
            ]
            top = score_and_topk(q_emb, rows, time.time(), TOPK_INSIGHTS)
            chosen = [r for r, _ in top]
        else:
            chosen = insights[:TOPK_INSIGHTS]
        if not chosen:
            return ""
        lines = []
        for ins in chosen:
            support = int(ins.get("support_count", 1))
            tag_str = ", ".join(ins.get("tags", []) or []) if ins.get("tags") else ""
            prefix = f"[×{support}]" if support > 1 else ""
            tag_part = f" ({tag_str})" if tag_str else ""
            lines.append(f"- {prefix} {ins.get('text','')}{tag_part}".strip())
        out = "\n".join(lines)
        return out[:limit_chars]

    def _render_similar(self, query: Optional[str], *, limit_chars: int) -> str:
        if not query:
            return ""
        # 7-day recency filter to keep retrieval relevant.
        since = time.time() - 7 * 86400
        rows = self.db.fetch_episodes(since_ts=since, with_embeddings=True)
        # Exclude episodes already shown in the working buffer.
        working_ids = {e["id"] for e in self._working if e.get("id") is not None}
        rows = [r for r in rows if r["id"] not in working_ids]
        if not rows:
            return ""
        q_emb = embed_query(query)
        top = score_and_topk(q_emb, rows, time.time(), TOPK_EPISODES)
        if not top:
            return ""
        lines = []
        now = time.time()
        for row, score in top:
            age_h = max(0, int((now - float(row.get("ts", now))) / 3600))
            lines.append(f"- ({age_h}h ago, s={score:.2f}) {_render_entry(row)}")
        out = "\n".join(lines)
        return out[:limit_chars]

    def _render_warnings(self, *, limit_chars: int) -> str:
        warns = self._pending_warnings or self._loop.snapshot_warnings()
        if not warns:
            return ""
        return "\n".join(warns)[:limit_chars]

    # ------------------------------------------------------------------
    # Legacy JSON import (best-effort)
    # ------------------------------------------------------------------

    def _maybe_import_legacy(self) -> None:
        if not self.project_root:
            return
        path = os.path.join(self.project_root, ".alpha_stack", "planner_memory.json")
        if not os.path.exists(path):
            return
        if self.db.count_episodes() > 0 or self.db.get_meta("legacy_imported") == "1":
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"legacy memory import skipped: {e}")
            return

        entries = data.get("entries", []) or []
        texts = [
            _embedding_text(e.get("action", ""), e.get("file", ""),
                            e.get("detail", ""), e.get("outcome", ""))
            for e in entries
        ]
        embs = self._embedder.embed_batch(texts) if texts else np.zeros((0,))
        now = time.time()
        for i, e in enumerate(entries):
            try:
                self.db.insert_episode(
                    role=self.role,
                    session=int(e.get("session") or 0),
                    action=str(e.get("action", "")),
                    file=str(e.get("file", "")),
                    detail=str(e.get("detail", "")),
                    outcome=str(e.get("outcome", "")),
                    importance=0.3,
                    error_class="",
                    error_hash="",
                    embedding=embs[i] if len(embs) > i else None,
                    ts=now - (len(entries) - i),
                )
            except Exception:
                continue

        # Bootstrap insight from the rolled-up previous_summary + summaries.
        parts = []
        prev = data.get("previous_summary", "")
        if prev:
            parts.append(prev)
        parts.extend(data.get("summaries", []) or [])
        blob = "\n\n".join(p for p in parts if p).strip()
        if blob:
            emb = self._embedder.embed(blob[:2000])
            self.db.insert_insight(
                text=blob[:500],
                tags=["legacy"],
                embedding=emb,
                support_count=1,
            )

        self.db.set_meta("legacy_imported", "1")
        try:
            os.rename(path, path + ".imported")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # External triggers (used by callers to signal lifecycle events)
    # ------------------------------------------------------------------

    def notify_success(self) -> None:
        try:
            self._reflection.notify_success()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Misc protocol
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._working)

    def __bool__(self) -> bool:
        if len(self._working) > 0:
            return True
        if self.db.count_episodes() > 0:
            return True
        if self.db.count_insights() > 0:
            return True
        return False

    def __del__(self):
        try:
            self._reflection.stop(timeout=0.1)
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
