"""Opt-in LLM smoke test. Run with `pytest -m llm`.

Requires OPENROUTER_API_KEY in the environment.
"""

import os

import pytest


pytestmark = pytest.mark.llm


@pytest.fixture(autouse=True)
def _require_key():
    if not (os.getenv("OPENROUTER_API_KEY")
            or os.path.exists(os.path.expanduser("~/.alphastack/config.json"))):
        pytest.skip("OPENROUTER_API_KEY not set and no stored alphastack key")


def test_live_blueprint_with_strong_model():
    """Sanity: a capable model produces a non-empty, schema-valid blueprint."""
    from src.generator import generate_project_blueprint
    from src.utils.prompt_manager import PromptManager
    from src.utils.inference import InferenceManager

    InferenceManager.reset()
    InferenceManager.initialize("openrouter", validate=True, model_override="google/gemini-2.5-pro")
    bp = generate_project_blueprint(
        prompt="A tiny Rust CLI that prints hello world.",
        pm=PromptManager(),
        provider_name="openrouter",
        architecture_content="## Problem\nRust hello world.",
    )
    assert bp is not None
    assert len(bp.file_formats) > 0
    assert bp.folder_structure.strip()
