"""generate_project_blueprint parses fake model output correctly.

Uses `FakeProvider` from conftest — no real network.
"""

import json

import pytest


VALID_BLUEPRINT_JSON = {
    "software_blueprint_details": {
        "project_name": "hello",
        "version": "0.1.0",
        "summary": "A hello world CLI",
        "key_features": ["prints hello world"],
    },
    "folder_structure": (
        "hello/\n"
        "├── Cargo.toml\n"
        "└── src/\n"
        "    └── main.rs"
    ),
    "file_formats": {
        "Cargo.toml": {"purpose": "manifest"},
        "src/main.rs": {"purpose": "entry"},
    },
}


def test_blueprint_parses_fenced_json(fake_provider):
    from src.generator import generate_project_blueprint
    from src.utils.prompt_manager import PromptManager

    fenced = "```json\n" + json.dumps(VALID_BLUEPRINT_JSON) + "\n```"
    fake_provider.queue(fenced)
    bp = generate_project_blueprint(
        prompt="hello world",
        pm=PromptManager(),
        provider_name="openrouter",
    )
    assert bp is not None
    assert bp.file_formats == VALID_BLUEPRINT_JSON["file_formats"]


def test_blueprint_parses_bare_json_with_prefix(fake_provider):
    from src.generator import generate_project_blueprint
    from src.utils.prompt_manager import PromptManager

    fake_provider.queue("Sure, here you go: " + json.dumps(VALID_BLUEPRINT_JSON))
    bp = generate_project_blueprint(
        prompt="x", pm=PromptManager(), provider_name="openrouter"
    )
    assert bp is not None
    assert len(bp.file_formats) == 2


def test_blueprint_rejects_garbled_response(fake_provider):
    from src.generator import generate_project_blueprint
    from src.utils.prompt_manager import PromptManager

    # Queue two responses since the pipeline retries plain after json-mode.
    fake_provider.queue("I cannot produce JSON, sorry.")
    fake_provider.queue("Still just prose.")
    bp = generate_project_blueprint(
        prompt="x", pm=PromptManager(), provider_name="openrouter"
    )
    assert bp is None


def test_blueprint_rejects_schema_mismatch(fake_provider):
    """Pydantic validation catches wrong-type fields."""
    from src.generator import generate_project_blueprint
    from src.utils.prompt_manager import PromptManager

    bad = json.dumps({"software_blueprint_details": "should be a dict, not a string"})
    fake_provider.queue(bad)
    fake_provider.queue(bad)
    bp = generate_project_blueprint(
        prompt="x", pm=PromptManager(), provider_name="openrouter"
    )
    assert bp is None


def test_empty_blueprint_triggers_guard(fake_provider):
    """The post-validation guard rejects blueprints with no files to generate."""
    from src.generator import generate_project
    from src.utils.prompt_manager import PromptManager

    # architecture, arch critic (no issues), skeleton (small -> single-pass),
    # empty blueprint, blueprint critic (no issues)
    fake_provider.queue("## arch\nplaceholder")
    fake_provider.queue(json.dumps({"issues": []}))
    skeleton = {
        "software_blueprint_details": {"project_name": "x"},
        "folder_structure": "x/\n└── stub.py",
        "files": {"stub.py": "the only file"},
    }
    fake_provider.queue(json.dumps(skeleton))
    empty_blueprint = {
        "software_blueprint_details": {"project_name": "x"},
        "folder_structure": "x/\n└── stub",
        "file_formats": {},
    }
    fake_provider.queue(json.dumps(empty_blueprint))
    fake_provider.queue(json.dumps({"issues": []}))

    emitted = []
    out = generate_project(
        user_prompt="x",
        output_base_dir="/tmp/alphastack_empty_test",
        on_status=lambda t, m, **kw: emitted.append((t, m)),
        provider_name="openrouter",
    )
    assert out is None
    assert any(t == "error" and "empty" in m.lower() for t, m in emitted), emitted
