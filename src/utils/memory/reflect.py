"""Reflexion-style background reflection worker.

Triggers:
  - success: after a test-pass event, distill the fix that worked.
  - quiet_fail: after a shell FAIL with no new records in 60s.
  - session_end: on save().

The worker pulls the last N episodes of the active run, asks the LLM for a
strict JSON list of insights, and writes each one. Duplicates (by cosine
≥ 0.92 to an existing insight) increment support_count instead of inserting.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from .embed import Embedder, cosine
from .store import MemoryDB


logger = logging.getLogger(__name__)

REFLECT_EPISODE_WINDOW = 30
DUPLICATE_SIM_THRESHOLD = 0.92


_TRIGGERS = frozenset({"success", "quiet_fail", "session_end", "manual"})


@dataclass
class ReflectionTask:
    trigger: str
    run_id: str
    snapshot_ts: float


def _render_episode_line(ep: dict) -> str:
    """Terse one-line rendering for the reflection prompt."""
    parts = [f"[{ep.get('action','')}]"]
    if ep.get("file"):
        parts.append(str(ep["file"])[:80])
    if ep.get("detail"):
        d = str(ep["detail"])
        if len(d) > 400:
            d = d[:400] + "…"
        parts.append(d)
    if ep.get("outcome"):
        parts.append(f"→ {ep['outcome']}")
    return " ".join(parts)


def _build_prompt(trigger: str, episodes: List[dict]) -> str:
    body = "\n".join(f"- (ep {e['id']}) {_render_episode_line(e)}" for e in episodes)
    trigger_hint = {
        "success": "The task just succeeded. Identify the fix that worked.",
        "quiet_fail": "The last attempted fix did not work. Identify the wrong assumption.",
        "session_end": "Session is ending. Extract any durable lessons.",
        "manual": "Extract any durable lessons from these actions.",
    }.get(trigger, "Extract durable lessons from these actions.")
    return (
        "You are the memory reflector for an AI coding agent. "
        f"{trigger_hint}\n\n"
        "Return STRICT JSON — a list of at most 4 lesson objects. Each lesson must be "
        "GENERAL enough to help on a future unrelated run (not specific to one file). "
        "Schema:\n"
        '[{"text": "<one-sentence lesson>", '
        '"tags": ["<language|tool|error_class>", ...], '
        '"supports_episode_ids": [<int>, ...]}]\n\n'
        "Only return the JSON array — no prose, no code fences.\n\n"
        "### Episodes\n"
        f"{body}\n"
    )


_JSON_ARRAY_RE = re.compile(r"\[\s*(?:\{.*\})?\s*\]", re.DOTALL)


def _extract_json_array(text: str) -> list:
    if not text:
        return []
    # Strip code fences if the model wraps them.
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        val = json.loads(t)
        return val if isinstance(val, list) else []
    except Exception:
        pass
    m = _JSON_ARRAY_RE.search(t)
    if not m:
        return []
    try:
        val = json.loads(m.group(0))
        return val if isinstance(val, list) else []
    except Exception:
        return []


class ReflectionWorker:
    """Owns a daemon thread, a bounded queue, and access to the DB."""

    def __init__(
        self,
        db: MemoryDB,
        provider_getter: Optional[Callable] = None,
        *,
        enable: bool = True,
    ):
        self.db = db
        self._provider_getter = provider_getter
        self._queue: "queue.Queue[ReflectionTask]" = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_fail_ts: float = 0.0
        self._quiet_scheduled = False
        self._lock = threading.Lock()
        if enable:
            self.start()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="memory-reflect", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(ReflectionTask("manual", "__stop__", time.time()))
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    # ------------------------------------------------------------------
    # Public triggers
    # ------------------------------------------------------------------

    def notify_success(self) -> None:
        self._enqueue(ReflectionTask("success", self.db.run_id, time.time()))

    def notify_fail(self) -> None:
        with self._lock:
            self._last_fail_ts = time.time()
            if not self._quiet_scheduled:
                self._quiet_scheduled = True
                threading.Timer(60.0, self._maybe_quiet_reflect).start()

    def notify_session_end(self) -> None:
        self._enqueue(ReflectionTask("session_end", self.db.run_id, time.time()))

    def _maybe_quiet_reflect(self) -> None:
        with self._lock:
            self._quiet_scheduled = False
            elapsed = time.time() - self._last_fail_ts
        if elapsed >= 55.0:  # no new activity in ~60s
            self._enqueue(ReflectionTask("quiet_fail", self.db.run_id, time.time()))

    def _enqueue(self, task: ReflectionTask) -> None:
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            pass

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if task.trigger not in _TRIGGERS or task.run_id == "__stop__":
                continue
            try:
                self._reflect(task)
            except Exception as e:
                logger.debug(f"reflection worker swallowed error: {e}")

    def _reflect(self, task: ReflectionTask) -> None:
        episodes = self.db.recent_episodes_of_run(task.run_id, REFLECT_EPISODE_WINDOW)
        if len(episodes) < 2:
            return
        provider = self._get_provider()
        if provider is None:
            return
        prompt = _build_prompt(task.trigger, episodes)
        try:
            messages = provider.create_initial_message(prompt)
            response = provider.call_model(messages)
            text = provider.extract_text(response) or ""
        except Exception as e:
            logger.debug(f"reflection LLM call failed: {e}")
            return

        lessons = _extract_json_array(text)
        if not lessons:
            return

        embedder = Embedder.get()
        existing = self.db.fetch_insights(with_embeddings=True)
        for lesson in lessons[:4]:
            if not isinstance(lesson, dict):
                continue
            lt = (lesson.get("text") or "").strip()
            if not lt or len(lt) > 500:
                continue
            tags = lesson.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(t)[:40] for t in tags if t][:6]
            emb = embedder.embed(lt)
            # Dedup: cosine against existing insights.
            dup_id = None
            for row in existing:
                if row.get("embedding") is None:
                    continue
                if cosine(emb, row["embedding"]) >= DUPLICATE_SIM_THRESHOLD:
                    dup_id = int(row["id"])
                    break
            if dup_id is not None:
                self.db.reinforce_insight(dup_id)
            else:
                new_id = self.db.insert_insight(
                    text=lt, tags=tags, embedding=emb, support_count=1
                )
                existing.append({"id": new_id, "embedding": emb, "tags": tags})

    def _get_provider(self):
        if self._provider_getter:
            try:
                return self._provider_getter()
            except Exception:
                return None
        try:
            from ..inference import InferenceManager

            return InferenceManager.get_active_provider()
        except Exception:
            return None
