"""Tests for the new retrieval-aware memory layer (src/utils/memory)."""

from __future__ import annotations

import json
import os
import time

import pytest


# Force the deterministic hashed embedder so tests don't download models.
os.environ.setdefault("ALPHASTACK_EMBED_BACKEND", "hash")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path, role: str = "planner", reflection: bool = False):
    from src.utils.memory import MemoryStore

    return MemoryStore(
        project_root=str(tmp_path),
        role=role,
        enable_reflection=reflection,
    )


# ---------------------------------------------------------------------------
# Retrieval round-trip
# ---------------------------------------------------------------------------


def test_record_and_retrieve_roundtrip(tmp_path):
    store = _make_store(tmp_path)
    try:
        # Many episodes of noise, plus one highly-relevant signal.
        for i in range(50):
            store.record(
                session=1, action="edit", file=f"noise_{i}.py",
                detail=f"unrelated change {i}",
            )
        store.record(
            session=2, action="shell",
            file="pytest -v",
            detail="ModuleNotFoundError: requests\nModuleNotFoundError: No module named 'requests'",
            outcome="FAIL",
        )

        rendered = store.render(query="ModuleNotFoundError requests missing dependency")
        assert "Working" in rendered
        assert "pytest" in rendered or "requests" in rendered or "ModuleNotFoundError" in rendered
    finally:
        store.save()


def test_render_without_query_still_works(tmp_path):
    store = _make_store(tmp_path)
    try:
        store.record(session=1, action="edit", file="foo.py", detail="init")
        rendered = store.render()
        assert "Working" in rendered
        assert "foo.py" in rendered
    finally:
        store.save()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_persistence_across_reopen(tmp_path):
    from src.utils.memory import MemoryStore

    s1 = MemoryStore(project_root=str(tmp_path), role="planner", enable_reflection=False)
    s1.record(session=1, action="edit", file="a.py", detail="sentinel detail 42")
    s1.save()

    # Open a new store against the same dir — should see the old episode.
    s2 = MemoryStore(project_root=str(tmp_path), role="planner", enable_reflection=False)
    try:
        rendered = s2.render(query="sentinel detail 42")
        assert "a.py" in rendered
        assert "sentinel" in rendered
    finally:
        s2.save()


# ---------------------------------------------------------------------------
# Loop detection
# ---------------------------------------------------------------------------


def test_loop_detector_emits_warning(tmp_path):
    store = _make_store(tmp_path)
    try:
        for _ in range(3):
            store.record(session=1, action="edit", file="loopy.py", detail="same change")
        rendered = store.render(query="loopy")
        assert "LoopWarn" in rendered
        assert "loopy.py" in rendered
    finally:
        store.save()


# ---------------------------------------------------------------------------
# Legacy import
# ---------------------------------------------------------------------------


def test_legacy_json_import(tmp_path):
    ald = tmp_path / ".alpha_stack"
    ald.mkdir(parents=True, exist_ok=True)
    legacy_path = ald / "planner_memory.json"
    legacy_path.write_text(json.dumps({
        "previous_summary": "Last run: installed requests.",
        "summaries": ["pytest passed after adding 'requests' to requirements.txt"],
        "entries": [
            {"session": 1, "action": "edit", "file": "requirements.txt",
             "detail": "added requests", "outcome": ""},
            {"session": 1, "action": "shell", "file": "pytest",
             "detail": "1 passed", "outcome": "OK"},
        ],
    }))

    from src.utils.memory import MemoryStore

    store = MemoryStore(project_root=str(tmp_path), role="planner", enable_reflection=False)
    try:
        assert store.db.count_episodes() == 2
        assert store.db.count_insights() >= 1
        assert (ald / "planner_memory.json.imported").exists()
        assert not legacy_path.exists()
    finally:
        store.save()


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


def test_render_respects_token_budget(tmp_path):
    store = _make_store(tmp_path)
    try:
        for i in range(40):
            store.record(
                session=1, action="edit", file=f"bulk_{i}.py",
                detail="X" * 300,  # lots of chars
            )
        rendered = store.render(query="bulk", budget_tokens=500)
        # budget_tokens=500 → ~2000 chars cap; allow some slack from section headers.
        assert len(rendered) < 2400, f"render too large: {len(rendered)} chars"
    finally:
        store.save()


# ---------------------------------------------------------------------------
# Reflection (mocked provider)
# ---------------------------------------------------------------------------


def test_reflection_writes_insight(tmp_path):
    """Run the reflection worker synchronously against a mocked provider."""
    from src.utils.memory.reflect import ReflectionWorker, ReflectionTask
    from src.utils.memory.store import MemoryDB

    db = MemoryDB(str(tmp_path / "reflect.db"))
    # Seed a trajectory: fail → edit → pass.
    db.insert_episode(role="planner", session=1, action="shell",
                      file="pytest", detail="ImportError: requests",
                      outcome="FAIL", importance=0.9, error_class="missing_module",
                      error_hash="abc", embedding=None)
    db.insert_episode(role="planner", session=1, action="edit",
                      file="requirements.txt", detail="added requests",
                      outcome="", importance=0.8, error_class="",
                      error_hash="", embedding=None)
    db.insert_episode(role="planner", session=1, action="shell",
                      file="pytest", detail="1 passed",
                      outcome="OK", importance=1.0, error_class="",
                      error_hash="", embedding=None)

    class MockProvider:
        def create_initial_message(self, prompt):
            return [{"role": "user", "content": prompt}]

        def call_model(self, messages, tools=None, **kwargs):
            return json.dumps([{
                "text": "Add missing Python packages to requirements.txt before running pytest.",
                "tags": ["python", "pytest", "missing_module"],
                "supports_episode_ids": [1, 2, 3],
            }])

        def extract_text(self, resp):
            return resp

    worker = ReflectionWorker(db, provider_getter=lambda: MockProvider(), enable=False)
    # Invoke the private reflect path directly (no thread, synchronous).
    worker._reflect(ReflectionTask("success", db.run_id, time.time()))

    assert db.count_insights() == 1
    insights = db.fetch_insights(with_embeddings=False)
    assert "requirements.txt" in insights[0]["text"] or "pytest" in insights[0]["text"]
    assert "python" in (insights[0].get("tags") or [])


def test_reflection_dedups_similar_lessons(tmp_path):
    from src.utils.memory.reflect import ReflectionWorker, ReflectionTask
    from src.utils.memory.store import MemoryDB

    db = MemoryDB(str(tmp_path / "dup.db"))
    db.insert_episode(role="planner", session=1, action="shell", file="pytest",
                      detail="fail x", outcome="FAIL", importance=0.9,
                      error_class="", error_hash="", embedding=None)
    db.insert_episode(role="planner", session=1, action="edit", file="a.py",
                      detail="fix", outcome="", importance=0.8,
                      error_class="", error_hash="", embedding=None)

    class MockProvider:
        def create_initial_message(self, prompt):
            return [{"role": "user", "content": prompt}]

        def call_model(self, messages, tools=None, **kwargs):
            return json.dumps([{
                "text": "Always run pytest -v after edits.",
                "tags": ["pytest"],
                "supports_episode_ids": [1, 2],
            }])

        def extract_text(self, resp):
            return resp

    worker = ReflectionWorker(db, provider_getter=lambda: MockProvider(), enable=False)
    worker._reflect(ReflectionTask("success", db.run_id, time.time()))
    worker._reflect(ReflectionTask("success", db.run_id, time.time()))

    # Second reflection with identical text should reinforce, not duplicate.
    insights = db.fetch_insights(with_embeddings=False)
    assert len(insights) == 1
    assert insights[0]["support_count"] >= 2


# ---------------------------------------------------------------------------
# API back-compat
# ---------------------------------------------------------------------------


def test_old_agent_memory_import_still_works(tmp_path):
    from src.utils.agent_memory import AgentMemory

    mem = AgentMemory(project_root=str(tmp_path), role="planner", enable_reflection=False)
    try:
        mem.record(session=0, action="edit", file="x.py", detail="hi")
        assert len(mem) == 1
        assert bool(mem) is True
    finally:
        mem.save()


def test_in_memory_mode_no_project_root():
    """Orchestrator used to construct AgentMemory with no args — still works."""
    from src.utils.memory import MemoryStore

    mem = MemoryStore(enable_reflection=False)
    try:
        mem.record(session=0, action="edit", file="x.py", detail="test")
        rendered = mem.render()
        assert "x.py" in rendered
    finally:
        mem.save()
