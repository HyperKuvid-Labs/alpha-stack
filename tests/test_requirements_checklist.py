"""Requirements checklist: extraction parsing and prompt plumbing.

The checklist is extracted once from the user's prompt (before any phase can
drop a requirement) and handed to the critics and the planner's runtime
verification. Extraction failure must never block the pipeline.
"""

import json

from src import generator
from src.generator import extract_requirements
from src.utils.prompt_manager import PromptManager

VALID = {
    "requirements": [
        {"id": "R1", "requirement": "add stores an expense", "verify": "run add", "expected": "exit 0, record persisted"},
        {"id": "R2", "requirement": "invalid amount exits 1", "verify": "run add --amount abc", "expected": "exit 1, message on stderr"},
    ]
}


def _patch_llm(monkeypatch, response):
    monkeypatch.setattr(generator, "_call_llm_text", lambda *a, **k: response)


def test_extracts_valid_checklist(monkeypatch):
    _patch_llm(monkeypatch, json.dumps(VALID))
    reqs = extract_requirements("prompt", PromptManager())
    assert len(reqs) == 2
    assert reqs[0]["id"] == "R1"


def test_extracts_from_fenced_response(monkeypatch):
    _patch_llm(monkeypatch, "Here you go:\n```json\n" + json.dumps(VALID) + "\n```")
    reqs = extract_requirements("prompt", PromptManager())
    assert len(reqs) == 2


def test_incomplete_items_are_dropped(monkeypatch):
    payload = {
        "requirements": [
            VALID["requirements"][0],
            {"id": "R2", "requirement": "no verify or expected"},
        ]
    }
    _patch_llm(monkeypatch, json.dumps(payload))
    reqs = extract_requirements("prompt", PromptManager())
    assert len(reqs) == 1


def test_garbage_returns_none(monkeypatch):
    _patch_llm(monkeypatch, "sorry, I cannot do that")
    assert extract_requirements("prompt", PromptManager()) is None


def test_llm_failure_returns_none(monkeypatch):
    _patch_llm(monkeypatch, None)
    assert extract_requirements("prompt", PromptManager()) is None


def test_planner_prompt_includes_checklist():
    pm = PromptManager()

    class _State:
        tests_passed = False
        last_test_output = None

    rendered = pm.render(
        "planner_pipeline.j2",
        software_blueprint={"name": "x"},
        folder_structure="x/",
        dependency_graph="",
        project_root="/tmp/x",
        requirements_checklist=json.dumps(VALID["requirements"]),
        state=_State(),
        memory="",
        active_jobs="",
        blast_radius="",
    )
    assert "Acceptance Checklist" in rendered
    assert "R1" in rendered
    assert "per-item status" in rendered


def test_critic_templates_include_checklist():
    pm = PromptManager()
    checklist = json.dumps(VALID["requirements"])
    arch = pm.render_architecture_critic("prompt", "## arch", requirements_checklist=checklist)
    bp = pm.render_blueprint_critic("## arch", "tree", "{}", user_prompt="prompt", requirements_checklist=checklist)
    tc = pm.render_test_critic("prompt", "## arch", "{}", requirements_checklist=checklist)
    for rendered in (arch, bp, tc):
        assert "Acceptance Checklist" in rendered and "R1" in rendered
